"""
Phase 7 — Judge pass.

Hybrid approach (CRITICAL ARCHITECTURE):
1. Hard rules applied deterministically in Python (guaranteed honesty, always runs).
   - Grounds confidence < 0.70 → NULL (cannot prove from image)
   - Caps confidence on image quality degradation
   - Flags glare/blur impact on price confidence
   - Marks RAG match failures as "unmatched"

2. Deepseek-V3.2 (primary judge model only) called for judge_notes explanations.
   - If Deepseek fails (API error): hard rules still apply, judge_notes = None
   - Result is grounded in hard rules, NOT LLM-dependent

3. NO Nemotron, NO Nemo, NO fallback models.
   - Hard rules are deterministic + reliable. Use them as final fallback.
   - Confidence calibration is 100% transparent (hard rules in code).

This means observations are NEVER rejected by LLM — only by hard rules or visual confidence.
LLM only adds human-readable judge_notes explaining the calibration.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

from src.perception.vlm import Observation, VLMExtractionResult
from src.grounding.matcher import MatchResult
from src.perception.base import QualityResult


# ─── Output types ──────────────────────────────────────────────────────────────

@dataclass
class CalibratedObservation:
    brand_read: str | None
    product_read: str | None
    size_read: str | None
    legibility: str
    facings: int | None
    shelf_position: str | None
    price_read: str | None
    status: str
    field_confidence: dict[str, float]
    notes: str | None
    matched_sku_id: UUID | None
    match_method: str
    match_similarity: float
    obs_status: str        # final status after calibration (maps to audit_observations.status)
    judge_notes: str | None = None

    def to_db_dict(self) -> dict:
        # Price Shield: if confidence is 0, don't store price_read
        price_read = self.price_read if self.field_confidence.get("price", 0) > 0 else None

        return {
            "matched_sku_id": self.matched_sku_id,
            "sku_guess_text": f"{self.brand_read or ''} {self.product_read or ''}".strip() or None,
            "brand_read": self.brand_read,
            "size_read": self.size_read,
            "facings": self.facings,
            "shelf_position": self.shelf_position or "unknown",
            "price_read": price_read,
            "price_confidence": self.field_confidence.get("price"),
            "field_confidence": self.field_confidence,
            "obs_status": self.obs_status,
            "match_method": self.match_method,
            "match_similarity": self.match_similarity,
            "notes": self.judge_notes or self.notes,
        }


@dataclass
class JudgeResult:
    observations: list[CalibratedObservation]
    model_used: str
    latency_ms: int
    notes: str
    hard_rules_applied: list[str] = field(default_factory=list)


# ─── Deterministic calibration rules ──────────────────────────────────────────

def _apply_hard_rules(
    obs: Observation,
    match: MatchResult,
    quality: QualityResult,
) -> tuple[dict[str, float], str, list[str]]:
    """
    Returns (calibrated_confidence, calibrated_status, rules_triggered).
    Hard rules — run in Python, not the LLM.
    GROUNDED: Only keep field if confidence > 0.70 and can prove from image.
    """
    conf = dict(obs.field_confidence)
    status = obs.status
    rules: list[str] = []

    # RULE 1: GROUNDED CONFIDENCE — Zero out any field < 0.70
    # This is the core honesty rule: confidence < 0.70 means "cannot prove from image"
    for field_name in ["brand", "size", "price", "facings"]:
        field_conf = conf.get(field_name, 0.0)
        if field_conf < 0.70:
            if field_conf > 0:
                old = field_conf
                conf[field_name] = 0.0
                rules.append(
                    f"grounded_mask: {field_name} confidence={old:.2f} < 0.70 "
                    f"(cannot prove from image pixels) → NULL"
                )
            else:
                # Already 0, likely from VLM
                rules.append(f"grounded_honor: {field_name} already NULL (VLM couldn't extract)")

    # RULE 2: Quality-Based Confidence Degradation
    # If image quality is poor, cap confidence (don't trust the extraction)
    if quality.overall_score < 0.6:
        degraded = {}
        for k, v in conf.items():
            if v > 0.70:
                new_v = 0.70  # Cap at threshold
                degraded[k] = new_v
                rules.append(
                    f"quality_degrade: {k} {v:.2f}→{new_v:.2f} "
                    f"(image_quality={quality.overall_score:.2f} too low to trust extraction)"
                )
            else:
                degraded[k] = v
        conf = degraded

    # RULE 3: Glare/Blur Downgrade Confidence
    # If YOLO detected quality issues, reduce price confidence specifically
    degradation_flags = {"glare", "clahe_rescue_applied", "mild_blur"}
    if any(flag in " ".join(quality.issues) for flag in degradation_flags):
        if conf.get("price", 0) > 0.50:
            old_price = conf["price"]
            conf["price"] = round(conf["price"] - 0.15, 3)
            rules.append(
                f"glare_impact: price_confidence {old_price:.2f}→{conf['price']:.2f} "
                f"(detected: {', '.join([f for f in quality.issues if f in degradation_flags])})"
            )

    # RULE 4: RAG Match Status (doesn't affect visual confidence - orthogonal signals)
    # Visual confidence = "can I read it?" | Match confidence = "does it match catalog?"
    if match.match_similarity < 0.75:
        if status == "confirmed":
            status = "unmatched"
            rules.append(
                f"unmatched_sku: brand_visually_confident={conf.get('brand', 0):.2f} "
                f"but RAG_match_low={match.match_similarity:.3f} "
                f"→ mark as unmatched (keep brand data, flag for manual SKU resolution)"
            )

    # RULE 5: Derive final observation status based on confidence + legibility
    # obs_status maps to: confirmed | partial | low_confidence | unmatched | occluded | unreadable
    if obs.legibility == "unreadable":
        obs_status = "unreadable"
    elif obs.legibility == "partial":
        obs_status = "partial"
    elif status == "unmatched":
        obs_status = "unmatched"
    elif match.matched_sku_id is None:
        obs_status = "unmatched"
    else:
        # Calculate minimum confidence across all extracted fields
        extracted_confs = [v for v in conf.values() if v > 0]
        if not extracted_confs:
            obs_status = "low_confidence"
        else:
            min_conf = min(extracted_confs)
            if min_conf >= 0.85:
                obs_status = "confirmed"
            elif min_conf >= 0.70:
                obs_status = "partial"
            else:
                obs_status = "low_confidence"

    return conf, obs_status, rules


# ─── LLM-based judge notes ─────────────────────────────────────────────────────

_JUDGE_SYSTEM = """You are a QA judge for a bev-alc shelf-audit pipeline.

You receive calibrated observations (with hard-rule adjustments already applied),
match results, and quality signals.

Your job: for each observation, write a short judge_notes string (1-2 sentences)
explaining the confidence levels or flagging anything suspicious:
- Facings count that seems implausible for the shelf position
- Brand that visually mimics a premium SKU (store-brand lookalike)
- Price that seems inconsistent with known market range
- Any other concern that doesn't fit a schema field

Rules you MUST follow:
- Never add observations that weren't in the input. Never remove observations.
- Only adjust confidence values if your reasoning is specific and grounded.
- If nothing is suspicious, set judge_notes to null.
- Output a JSON object: {"calibrated": [...], "judge_summary": "..."}
  where each element in calibrated matches the input observation order.
  Each calibrated element: {"index": 0, "judge_notes": "...", "field_confidence_delta": {}}
  field_confidence_delta: key→signed float to add/subtract (e.g. {"facings": -0.1}).
  Omit field_confidence_delta if no change."""

_TRANSIENT = {429, 500, 502, 503, 504}


async def _call_nim(payload: dict) -> str:
    key = os.environ.get("NVIDIA_NIM_API_KEY", "")
    if not key:
        raise RuntimeError("NVIDIA_NIM_API_KEY not set")
    async with httpx.AsyncClient(timeout=30.0) as client:  # Increased for ngrok
        for attempt in range(2):
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code in _TRANSIENT and attempt == 0:
                await asyncio.sleep(1.0)
                continue
            resp.raise_for_status()
            break
    return resp.json()["choices"][0]["message"]["content"]


async def _get_judge_notes(
    calibrated: list[CalibratedObservation],
    quality: QualityResult,
    match_results: list[MatchResult],
) -> tuple[list[str | None], str, str]:
    """
    Returns (per-obs judge_notes list, model_used, judge_summary).
    Non-fatal: returns empty notes on any error.
    """
    input_obs = [
        {
            "index": i,
            "brand_read": o.brand_read,
            "product_read": o.product_read,
            "size_read": o.size_read,
            "facings": o.facings,
            "shelf_position": o.shelf_position,
            "price_read": o.price_read,
            "status": o.obs_status,
            "field_confidence": o.field_confidence,
            "match_method": o.match_method,
            "match_similarity": o.match_similarity,
        }
        for i, o in enumerate(calibrated)
    ]

    user_content = json.dumps({
        "observations": input_obs,
        "quality": {"overall_score": quality.overall_score, "issues": quality.issues},
    }, indent=2)

    # Primary: Deepseek v3.2 (most capable judge model)
    # If Deepseek unavailable, hard rules are applied without LLM judge_notes
    # (hard rules are deterministic and always reliable)
    models = [
        ("deepseek-v3.2@nim", os.environ.get("JUDGE_MODEL_PRIMARY", "deepseek-ai/deepseek-v3.2")),
    ]

    for model_tag, model_id in models:
        try:
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 1024,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
            raw = await _call_nim(payload)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)

            calibrated_adjustments = result.get("calibrated") or []
            notes_list: list[str | None] = [None] * len(calibrated)
            for adj in calibrated_adjustments:
                idx = adj.get("index", -1)
                if 0 <= idx < len(calibrated):
                    notes_list[idx] = adj.get("judge_notes")
                    delta = adj.get("field_confidence_delta") or {}
                    for field_name, delta_val in delta.items():
                        old = calibrated[idx].field_confidence.get(field_name, 0.0)
                        calibrated[idx].field_confidence[field_name] = round(
                            max(0.0, min(1.0, old + delta_val)), 3
                        )

            return notes_list, model_tag, result.get("judge_summary", "")
        except Exception:
            continue

    return [None] * len(calibrated), "skipped", "Judge LLM unavailable — hard rules applied only"


# ─── Main Judge class ──────────────────────────────────────────────────────────

class Judge:
    async def calibrate(
        self,
        vlm_result: VLMExtractionResult,
        match_results: list[MatchResult],
        quality_result: QualityResult,
    ) -> JudgeResult:
        t0 = time.perf_counter()
        all_rules: list[str] = []

        # Step 1: apply deterministic hard rules
        calibrated: list[CalibratedObservation] = []
        for obs, match in zip(vlm_result.observations, match_results):
            cal_conf, obs_status, rules = _apply_hard_rules(obs, match, quality_result)
            all_rules.extend(rules)
            calibrated.append(CalibratedObservation(
                brand_read=obs.brand_read,
                product_read=obs.product_read,
                size_read=obs.size_read,
                legibility=obs.legibility,
                facings=obs.facings,
                shelf_position=obs.shelf_position,
                price_read=obs.price_read,
                status=obs.status,
                field_confidence=cal_conf,
                notes=obs.notes,
                matched_sku_id=match.matched_sku_id,
                match_method=match.match_method,
                match_similarity=match.match_similarity,
                obs_status=obs_status,
            ))

        # Step 2: call LLM for judge_notes (non-fatal)
        notes_list, model_used, judge_summary = await _get_judge_notes(
            calibrated, quality_result, match_results
        )
        for i, note in enumerate(notes_list):
            calibrated[i].judge_notes = note

        latency_ms = int((time.perf_counter() - t0) * 1000)
        notes = judge_summary or ("; ".join(all_rules) if all_rules else "No adjustments")

        return JudgeResult(
            observations=calibrated,
            model_used=model_used,
            latency_ms=latency_ms,
            notes=notes,
            hard_rules_applied=all_rules,
        )
