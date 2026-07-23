"""
Phase 9 — Fast gatekeep: YOLO lazy (primary) → CLIP (fallback).

Instant reject non-alcoholic/food/non-retail BEFORE VLM is called.
No external API calls — just local ML for speed + reliability.

Architecture:
  1. YOLO (lazy-loaded on first call): Bottle count + restricted objects
  2. CLIP (pre-loaded): Semantic verification if YOLO uncertain
  3. Return verdict instantly (< 10s) without wasting tokens on VLM
"""
import json
import os
import time
from io import BytesIO
import asyncio
import numpy as np
import torch
from PIL import Image, ImageOps
from transformers import CLIPModel, CLIPProcessor
from ultralytics import YOLO

from src.perception.base import GuardrailResult

CLIP_MODEL_ID = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
GUARDRAIL_MIN_CONFIDENCE = 0.65

# YOLO class IDs
ALLOWED_CONTAINERS = {39, 41, 47}  # bottle, cup, glass
RESTRICTED_OBJECTS = {10, 3, 26, 5}  # pizza box, car, backpack, airplane


class Guardrail:
    """Fast gatekeeper: YOLO → CLIP (no external API calls, local only)"""

    def __init__(self, model_id: str = CLIP_MODEL_ID):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.clip_model = CLIPModel.from_pretrained(model_id).to(self.device).eval()
        self.clip_processor = CLIPProcessor.from_pretrained(model_id)

        # Lazy-load YOLO on first call (not in __init__)
        self.yolo = None
        self.yolo_enabled = os.getenv("YOLO_ENABLED", "1") == "1"

        # Pre-encode CLIP prompts for alcohol shelf detection
        # Production-grade semantic separation: store vs e-commerce vs non-alcohol vs garbage
        # Engineered to avoid CLIP confusion (e.g., "person holding" vs "bottle in hand")
        self.shelf_prompts = [
                    # =================================================================
                    # POSITIVE: Real-World Store Captures (Sales Rep Archetypes)
                    # =================================================================
                    "liquor store shelf set with spirits bottles",
                    "retail alcohol aisle facing rows of bottles",
                    "commercial beverage cooler door filled with beer and seltzers",
                    "liquor store promotional endcap display",
                    "freestanding case stack display of liquor boxes and bottles in an aisle",
                    "point of sale counter display with small nips or airline liquor bottles",
                    "close up of liquor bottle price tags on a shelf edge",
                    "organized backbar display of spirits bottles in a tavern or retail store",

                    # =================================================================
                    # POSITIVE: Single Bottle Close-Ups (Common Internet/Testing Images)
                    # =================================================================
                    "single glass whiskey bottle on a table close up photo",
                    "a vodka bottle photographed from above on a counter",
                    "one dark liquor bottle standing alone on a surface",
                    "professional photography of a single spirit bottle isolated",
                    "a tequila or rum bottle snapped with a phone camera in a room",

                    # =================================================================
                    # POSITIVE: E-Commerce & Web Captures (Google Images Archetypes)
                    # =================================================================
                    "clean e-commerce product listing shot of an alcohol bottle on pure white background",
                    "isolated studio photography of a spirits bottle with high contrast lighting",
                    "digital mockup or transparent PNG of a liquor bottle packaging",
                    "close up macro photograph of a pristine wine or spirits bottle label",
                    "bright high-exposure product image of a single alcohol bottle",
                    "manufacturer stock photo of a branded liquor bottle",

                    # =================================================================
                    # POSITIVE: Hand-held single bottle (real rep scenario)
                    # =================================================================
                    "hand holding a whiskey bottle close to camera",
                    "person holding a liquor bottle for shelf audit",
                    "close-up of an alcohol bottle held in hand",
                    "single spirit bottle held up against store shelf",

                    # =================================================================
                    # NEGATIVE: Non-Alcoholic Beverages (The Traps)
                    # =================================================================
            "grocery shelf stacked with plastic water bottles",
            "soda pop and carbonated juice cans on display",
            "energy drinks, sports drinks, or liquid mixers on retail racks",
            "milk jugs and dairy items inside a supermarket cooler",
            "bottled iced coffee, tea, or healthy juice drinks",

            # =================================================================
            # NEGATIVE: Wrong Context / Garbage Images (Unambiguous rejection)
            # =================================================================
            "blurry selfie of a person smiling or posing",
            "crowded bar scene with people drinking or holding cups",
            "interior of a residential kitchen cabinet or home pantry",
            "close up of a computer screen, software interface, or text document",
            "grocery store snack aisle with chips, cookies, and food items",
            "blurry, dark, or unfocused photo of an empty floor or ceiling",
            "close up of a paper receipt or shipping label",
        ]

        with torch.no_grad():
            inputs = self.clip_processor(
                text=self.shelf_prompts, return_tensors="pt", padding=True
            ).to(self.device)
            txt_out = self.clip_model.text_model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )
            text_feats = self.clip_model.text_projection(txt_out.pooler_output)
            self.clip_text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)

        print("[INFO] Guardrail initialized: YOLO (primary) → CLIP (fallback, local only)")

    async def classify_async(self, image_bytes: bytes) -> GuardrailResult:
        """
        Fast gatekeeper: YOLO lazy → CLIP. No external APIs, no token waste.
        """
        t0 = time.perf_counter()
        pil = Image.open(BytesIO(image_bytes))
        pil = ImageOps.exif_transpose(pil).convert("RGB")

        # Free image_bytes immediately after loading into PIL
        # PIL has already decoded it into memory, so raw bytes can be released
        del image_bytes
        import gc
        gc.collect()

        # Stage 1: Try YOLO (fast object detection if available)
        t1 = time.perf_counter()
        bottle_count, yolo_reason = self._detect_shelf_density(pil)
        t_yolo = (time.perf_counter() - t1) * 1000

        # YOLO says "definitely reject"
        if yolo_reason == "RESTRICTED_OBJECT":
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[GATE] Rejected (YOLO restricted) in {elapsed:.0f}ms")
            return GuardrailResult(
                verdict="reject",
                category="restricted_object",
                confidence=0.95,
                top_matches=[("yolo", 0.95)],
                routing="rejected",
                reason="Detected non-alcohol items (not a store shelf)",
                rejection_reason="restricted",
            )

        if yolo_reason == "NO_PRODUCTS_FOUND":
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[GATE] Rejected (no containers) in {elapsed:.0f}ms")
            return GuardrailResult(
                verdict="reject",
                category="empty_shelf",
                confidence=0.9,
                top_matches=[("yolo", 0.9)],
                routing="rejected",
                reason="No beverage containers found",
                rejection_reason="empty",
            )

        # YOLO found 2+ bottles = PASS immediately
        if bottle_count and bottle_count >= 2:
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[GATE] Accepted (YOLO {bottle_count} bottles) in {elapsed:.0f}ms")
            return GuardrailResult(
                verdict="pass",
                category="alcohol_shelf",
                confidence=0.85,
                top_matches=[("yolo", 0.85)],
                routing="shelf_extraction",
                reason=f"Alcohol shelf detected ({bottle_count} containers)",
                rejection_reason=None,
                alcohol_type="alcohol",
                alcohol_confidence=0.85,
            )

        # YOLO found exactly 1 bottle — don't reject outright, try CLIP first
        if bottle_count and bottle_count == 1:
            print(f"[GATE] YOLO found 1 container — deferring to CLIP for single-bottle check")

        # Stage 2: YOLO uncertain/unavailable → Use CLIP as fallback
        t2 = time.perf_counter()
        clip_result = self._verify_with_clip(pil)
        t_clip = (time.perf_counter() - t2) * 1000
        elapsed = (time.perf_counter() - t0) * 1000

        print(f"[GATE] {clip_result['verdict'].upper()} (CLIP {clip_result['confidence']:.2f}) in {elapsed:.0f}ms")
        return GuardrailResult(
            verdict=clip_result["verdict"],
            category=clip_result["category"],
            confidence=clip_result["confidence"],
            top_matches=clip_result["top_matches"],
            routing="shelf_extraction" if clip_result["verdict"] == "pass" else "rejected",
            reason=clip_result["reason"],
            rejection_reason=clip_result["rejection_reason"],
        )

    def _detect_shelf_density(self, pil_image: Image.Image) -> tuple[int | None, str | None]:
        """
        YOLO: Detect bottle/container count and restricted objects (lazy-loaded).

        Returns:
            (bottle_count: int, reason: str|None)
            reason=None if OK, otherwise reason for rejection
        """
        if not self.yolo_enabled:
            print("[YOLO] Disabled, skipping detection")
            return None, None

        try:
            # Lazy load YOLO on first use (with caching)
            if self.yolo is None:
                print("[YOLO] Loading model (first call, this may take 10-15s on first use)...")
                try:
                    # Try to load with auto-download enabled
                    # Note: First call downloads from Ultralytics Hub (~50-100MB)
                    # Subsequent calls use cached model (~10-20s faster)
                    self.yolo = YOLO("yolov11n.pt", verbose=False)
                    self.yolo.to(self.device)
                    print(f"[YOLO] Model loaded on {self.device} (cache will speed up future calls)")
                except Exception as load_err:
                    err_detail = f"{type(load_err).__name__}: {str(load_err)[:100]}"
                    print(f"[YOLO] Load failed ({err_detail}), falling back to CLIP only")
                    print(f"[YOLO] Fix: Set YOLO_ENABLED=0 if you don't need object detection")
                    self.yolo_enabled = False
                    return None, None

            # Run YOLO detection
            results = self.yolo(pil_image, conf=0.25, verbose=False)
            if not results or len(results) == 0:
                print("[YOLO] No detections in frame")
                return 0, "NO_PRODUCTS_FOUND"

            detections = results[0].boxes
            if len(detections) == 0:
                return 0, "NO_PRODUCTS_FOUND"

            # Check for restricted objects (non-alcoholic markers)
            for box in detections:
                cls_id = int(box.cls[0])
                if cls_id in RESTRICTED_OBJECTS:
                    print(f"[YOLO] Detected restricted object: class {cls_id}")
                    return 0, "RESTRICTED_OBJECT"

            # Count beverage containers (bottles, cups, glasses)
            container_count = sum(
                1 for box in detections if int(box.cls[0]) in ALLOWED_CONTAINERS
            )
            print(f"[YOLO] Found {container_count} containers")

            if container_count == 0:
                return 0, "NO_PRODUCTS_FOUND"
            elif container_count < 2:
                return container_count, "LOW_PRODUCT_DENSITY"

            return container_count, None

        except Exception as e:
            print(f"[YOLO] Detection error: {type(e).__name__}: {str(e)[:80]}")
            return None, None

    def _verify_with_clip(self, pil_image: Image.Image) -> dict:
        """
        CLIP verification (local). Simple and reliable.
        """
        return self._verify_with_clip_local(pil_image)

    def _verify_with_clip_local(self, pil_image: Image.Image) -> dict:
        """
        Local CLIP verification with ensemble averaging: Fast, reliable, no API calls.

        Uses 10 positive + 10 negative prompts, averages each group,
        then decides: reject if clearly non-alcohol, pass otherwise (including uncertain).
        """
        try:
            with torch.no_grad():
                img_inputs = self.clip_processor(images=pil_image, return_tensors="pt").to(
                    self.device
                )
                vis_out = self.clip_model.vision_model(
                    pixel_values=img_inputs["pixel_values"]
                )
                img_feat = self.clip_model.visual_projection(vis_out.pooler_output)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                sims = (img_feat @ self.clip_text_feats.T).squeeze(0).cpu().numpy()

            # Split: first 23 = positive (alcohol/spirits), last 17 = negative (non-alcohol/garbage)
            pos_sims = sims[:23]
            neg_sims = sims[23:]

            # ENSEMBLE: Average each group separately
            avg_pos = float(np.mean(pos_sims))
            avg_neg = float(np.mean(neg_sims))

            print(f"[CLIP] avg_pos={avg_pos:.3f}, avg_neg={avg_neg:.3f}, gap={avg_pos-avg_neg:+.3f}")

            # REJECT only if CLEARLY non-alcohol (avg_pos < 0.05)
            # Single bottle images often score 0.05-0.15 on CLIP because they're
            # not "retail aisle" scenes — don't penalize them for that
            if avg_pos < 0.05:
                return {
                    "verdict": "reject",
                    "category": "non_alcohol",
                    "confidence": 1.0 - avg_pos,
                    "top_matches": [("clip_negative", avg_neg)],
                    "reason": "Non-alcoholic content clearly detected",
                    "rejection_reason": "non_alcohol",
                }

            # If it's anything above 0.15, PASS to Qwen.
            # Qwen is smart enough to read the label and reject if it's really non-alcoholic.
            return {
                "verdict": "pass",
                "category": "alcohol_shelf" if avg_pos > 0.40 else "uncertain",
                "confidence": avg_pos,
                "top_matches": [("clip_positive", float(avg_pos))],
                "reason": "Passing to Qwen for final determination",
                "rejection_reason": None,
            }

        except Exception as e:
            print(f"[CLIP] Error: {type(e).__name__}: {str(e)[:60]}")
            # Fallback: pass to VLM (better safe than sorry)
            return {
                "verdict": "pass",
                "category": "unknown",
                "confidence": 0.5,
                "top_matches": [],
                "reason": "CLIP error; proceeding to VLM",
                "rejection_reason": None,
            }
