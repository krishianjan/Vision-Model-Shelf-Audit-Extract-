"""
Phase 5 — VLM client with two-tier fallback chain.

Primary  : OpenRouter (Qwen2.5‑VL‑72B)
Backup   : Groq (Llama‑3.2‑90B‑Vision) - only if Qwen API fails

Two-pass prompting:
  Pass 1 — literal transcription + legibility rating per bottle.
  Pass 2 — SKU identification, facings, shelf position, price, field confidence.

The extraction and honesty logic (status enums, confidence caps on bad images,
no force-matching) lives HERE, not in the managed provider.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Literal

import httpx
from pydantic import BaseModel, Field

# ─── Pydantic output schema ────────────────────────────────────────────────────

class Observation(BaseModel):
    brand_read: str | None = None
    product_read: str | None = None
    size_read: str | None = None
    legibility: Literal["fully_readable", "partial", "unreadable"] = "fully_readable"
    facings: int | None = None
    shelf_position: Literal[
        "top", "eye_level", "reach", "stoop", "bottom", "endcap", "cooler_door", "unknown"
    ] | None = None
    price_read: str | None = None
    status: Literal[
        "confirmed", "partial", "low_confidence", "unmatched", "occluded", "unreadable"
    ] = "confirmed"
    field_confidence: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None
    # ── Visual cues (survive even when label text is unreadable) ──
    bottle_shape: str | None = None       # tall_neck|short_squat|handle|flask|wine|can|custom|unknown
    glass_tint: str | None = None        # clear|green|brown|blue|frosted|opaque|unknown
    cap_type: str | None = None          # screw|cork|crown|plastic|t_top|unknown
    label_color: str | None = None       # dominant color, e.g. "black"
    label_design: str | None = None       # minimal|ornate|vintage|modern|bold_text|illustrated|unknown
    damage_flags: str | None = None      # none|torn_label|dust|broken_seal|faded|dented
    visual_brand_guess: str | None = None     # brand inferred from visual cues, NOT label text
    visual_brand_confidence: float = 0.0       # 0-1 confidence for visual brand guess
    stock_level: str | None = None       # full|partial|low|empty|unknown
    alcohol_subcategory: str | None = None    # e.g. single_malt_scotch, silver_tequila, ipa


class VLMExtractionResult(BaseModel):
    observations: list[Observation] = Field(default_factory=list)
    out_of_stock_positions: list[dict] = Field(default_factory=list)
    competitor_activity: list[dict] = Field(default_factory=list)
    share_of_shelf_notes: str | None = None
    planogram_flags: list[str] = Field(default_factory=list)
    fixture_type: str = "unknown"
    image_quality_degraded: bool = False
    degradation_reason: str | None = None
    free_notes: str | None = None
    alcohol_type: str = "unknown"  # beer|wine|spirits|liqueur|rtd|cider|other|non_alcohol
    confidence_overall: float = 0.0  # Average confidence across all observations
    image_quality_score: float = 0.0  # VLM-rated image quality (0-1)
    extraction_confidence: float = 0.0  # VLM-rated extraction confidence (0-1)
    raw_pass1: dict = Field(default_factory=dict)
    raw_pass2: dict = Field(default_factory=dict)
    model_used: str = ""
    latency_ms: int = 0
    fallback_chain: list[str] = Field(default_factory=list)


class VLMChainExhausted(Exception):
    """All VLM providers failed."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"All VLM providers exhausted. Errors: {errors}")


# ─── Prompts ───────────────────────────────────────────────────────────────────

_HONESTY_CONTRACT = """
HONESTY CONTRACT (GROUNDED EXTRACTION ONLY):
- Transcribe ONLY what is LITERALLY visible on the label. Never guess, never interpolate.
- Never infer a brand from bottle shape/color/silhouette alone. Must be readable text.
- If confidence < 0.70 for ANY field (brand/size/price/facings) → SET THAT FIELD TO NULL (cannot prove from image)
- Do NOT guess missing data. NULL = "I cannot prove this from the image"
- Every extracted field must be grounded in pixel-level evidence:
  * brand: Can you read the brand name clearly on the label?
  * size: Can you read "ml" or "oz" or "L" text on the label?
  * price: Can you see a price tag with numeric value?
  * facings: Can you count individual bottles/cans in this group?
- If data is occluded, blurry, or ambiguous → set field to null + flag legibility status
- Output valid JSON ONLY. No prose. No apologies. No markdown fences.
""".strip()

_PASS1_SYSTEM = f"""You are a bev-alc shelf-audit transcription engine.
{_HONESTY_CONTRACT}

Your task (PASS 1): Transcribe text from alcohol bottles in ANY context:
- Retail shelf (gondola, endcap, floor display)
- Cooler/fridge door
- Single bottle in hand (product photo)
- Stock photo with white background
- Bottle on table/counter

For EVERY visible bottle, transcribe the literal readable text on the label.
Do NOT skip single bottles. Do NOT require a retail shelf context.
Do not attempt brand identification — only report what you can literally read.

ADDITIONALLY — capture visual brand cues that survive even when label text is unreadable:
- bottle_shape: "tall_neck" | "short_squat" | "handle" | "flask" | "wine" | "can" | "custom" | "unknown"
- glass_tint: "clear" | "green" | "brown" | "blue" | "frosted" | "opaque" | "unknown"
- cap_type: "screw" | "cork" | "crown" | "plastic" | "t_top" | "unknown"
- label_color_dominant: e.g. "red", "black", "white", "gold", "blue", "green", "unknown"
- label_design: "minimal" | "ornate" | "vintage" | "modern" | "bold_text" | "illustrated" | "unknown"
- damage_visible: "none" | "torn_label" | "dust" | "broken_seal" | "faded" | "dented"
These visual cues are CRITICAL fallbacks — they MUST be filled for every bottle even when label text is unreadable.

Output JSON matching this exact schema:
{{
  "image_quality_degraded": false,
  "degradation_reason": null,
  "fixture_type": "gondola | cooler | endcap | floor_display | hand_hold | stock_photo | table | unknown",
  "reads": [
    {{
      "raw_text": "[literal text visible on label, exactly as written]",
      "size_text": "[volume and unit if visible, e.g., '750 mL']",
      "price_text": "[price number if visible, e.g., '19.99']",
      "legibility": "fully_readable | partial | unreadable",
      "region": "left | center | right | unknown",
      "shelf_row": "top | eye_level | reach | stoop | bottom | endcap | cooler_door | hand_hold | unknown",
      "bottle_shape": "tall_neck | short_squat | handle | flask | wine | can | custom | unknown",
      "glass_tint": "clear | green | brown | blue | frosted | opaque | unknown",
      "cap_type": "screw | cork | crown | plastic | t_top | unknown",
      "label_color_dominant": "[color name or unknown]",
      "label_design": "minimal | ornate | vintage | modern | bold_text | illustrated | unknown",
      "damage_visible": "none | torn_label | dust | broken_seal | faded | dented"
    }}
  ]
}}"""

_PASS2_SYSTEM = f"""You are an expert retail intelligence model auditing spirit, wine, and beer portfolios.
{_HONESTY_CONTRACT}

⚠️ CRITICAL FILTER: This audit ONLY processes ALCOHOLIC BEVERAGES (beer, wine, spirits, liqueur, RTD, cider, vodka, rum, gin, flavored beer).
If this image contains NON-ALCOHOLIC beverages (water, juice, soda, coffee, tea), set alcohol_type="non_alcohol" and return EMPTY observations list.

⚠️ CRITICAL: SINGLE BOTTLE IMAGES ARE VALID
- This image may show a SINGLE bottle in hand, on a table, or as a stock photo
- DO NOT require multiple bottles or a retail shelf context
- Extract data from EVERY visible alcohol bottle, even if only 1 bottle is present
- A single clear bottle observation is a SUCCESS - do not skip it

Your task (PASS 2): Extract bottle data with GROUNDED CONFIDENCE SCORES based on pixel evidence.
The image source may be a highly polished e-commerce product shot (with ultra-bright, studio-white backgrounds)
OR a raw, unevenly lit physical store shelf captured via mobile camera. Adapt to both environments.

═══════════════════════════════════════════════════════════
TIERED BRAND RECOGNITION SYSTEM (CRITICAL — replaces single-tier text-only)
═══════════════════════════════════════════════════════════
Every observation MUST go through all 3 tiers. Fill whatever you can.

TIER 1 — TEXT (brand_read + field_confidence.brand):
- Brand name readable from label text → fill brand_read, confidence 0.85+
- Partially readable (some chars blurry) → confidence 0.70-0.84
- Unreadable text → brand_read = NULL, proceed to TIER 2

TIER 2 — VISUAL (visual_brand_guess + visual_brand_confidence):
- Label unreadable BUT bottle is visually recognizable from shape, color, cap, label design
- Use your training knowledge of iconic bottle shapes and label color schemes
- Examples of the METHOD (not a list to match):
  * A uniquely shaped bottle (e.g. skull, square, flask) is recognizable by silhouette alone
  * A distinct color + label pattern combination narrows the brand
  * Cap style (cork vs screw vs crown) indicates category
- Set visual_brand_guess to your best guess based on VISUAL evidence only
- Set visual_brand_confidence honestly:
  * 0.80+ = unmistakable iconic design (unique silhouette, no alternatives)
  * 0.60-0.79 = strong visual match but could be 1-2 alternatives
  * 0.40-0.59 = partial match (right category, uncertain brand)
  * <0.40 = leave NULL, you truly cannot tell
- This does NOT override the honesty contract for brand_read — if text is unreadable, brand_read stays NULL
- visual_brand_guess is SEPARATE data that helps downstream matching

TIER 3 — UNKNOWN:
- Cannot identify from text or visual cues → brand_read=NULL, visual_brand_guess=NULL, legibility="unreadable"
- STILL fill all visual cue fields (bottle_shape, glass_tint, etc.) and stock_level

═══════════════════════════════════════════════════════════
VISUAL CUE EXTRACTION (MANDATORY for EVERY observation)
═══════════════════════════════════════════════════════════
Even when label text is fully unreadable, you MUST still fill:
- bottle_shape: "tall_neck" | "short_squat" | "handle" | "flask" | "wine" | "can" | "custom" | "unknown"
  * tall_neck: standard spirits bottle, long neck
  * short_squat: wide round bottle (e.g. Patron)
  * handle: 1.75L with handle
  * flask: flat rectangular (e.g. Johnnie Walker)
  * wine: tall with sloped shoulders + cork
  * can: aluminum can (beer/seltzer)
- glass_tint: "clear" | "green" | "brown" | "blue" | "frosted" | "opaque" | "unknown"
- cap_type: "screw" | "cork" | "crown" | "plastic" | "t_top" | "unknown"
  * crown = beer bottle cap
  * t_top = T-shaped stopper (premium spirits)
- label_color: dominant color of label (e.g. "black", "white", "red", "gold", "blue")
- label_design: "minimal" | "ornate" | "vintage" | "modern" | "bold_text" | "illustrated" | "unknown"
- damage_flags: "none" | "torn_label" | "dust" | "broken_seal" | "faded" | "dented"
  * Combine with comma if multiple, e.g. "dust,torn_label"
These survive when text doesn't — they are your fallback for brand identification.

═══════════════════════════════════════════════════════════
STOCK LEVEL ESTIMATION
═══════════════════════════════════════════════════════════
- "full": >80% of facing space occupied by bottles
- "partial": 20-80% occupied
- "low": <20% occupied (1-2 bottles left)
- "empty": 0 bottles but shelf tag/price label still visible
- "unknown": cannot determine (single bottle photo, e-commerce shot)

═══════════════════════════════════════════════════════════
ALCOHOL SUBCATEGORY (more specific than alcohol_type)
═══════════════════════════════════════════════════════════
Fill alcohol_subcategory when you can determine it:
- Spirits: single_malt_scotch, blended_scotch, irish_whiskey, bourbon, tennessee_whiskey,
  canadian_whisky, japanese_whisky, silver_tequila, blanco_tequila, reposado_tequila,
  anejo_tequila, extra_anejo_tequila, white_rum, dark_rum, spiced_rum, london_dry_gin,
  old_tom_gin, american_gin, unflavored_vodka, flavored_vodka
- Wine: cabernet_sauvignon, chardonnay, sauvignon_blanc, pinot_noir, merlot, rose,
  sparkling, prosecco, champagne, moscato
- Beer: lager, pilsner, ipa, wheat, stout, porter, belgian, amber
- RTD: hard_seltzer, hard_tea, hard_lemonade
- Liqueur: coffee_liqueur, cream_liqueur, amaro, aperitivo
If uncertain, set to NULL.

═══════════════════════════════════════════════════════════
STANDARD FIELD EXTRACTION (unchanged rules)
═══════════════════════════════════════════════════════════
EXTRACTION STRATEGY:
1. Identify each distinct alcoholic item visible in the frame.
2. Determine the exact Brand and SKU details (Name, Flavor, Liquid Volume/Size like 750ml, 1.75L, 20oz).
3. Count the number of visible "facings" (identical bottles standing side-by-side on shelf).
   For isolated e-commerce images, facings will always be 1.
4. Extract the numeric shelf price if a clear price tag is located directly beneath or adjacent to the product.

EXTRACTION RULES (MANDATORY - NON-NEGOTIABLE):
1. BRAND confidence scoring:
   - 0.95+: Brand name fully readable, crisp text, no occlusion
   - 0.85-0.94: Brand visible but 1-2 chars slightly unclear or minor glare
   - 0.70-0.84: Brand partially visible, some letters cut off or blurry, but identifiable
   - <0.70: Cannot read brand text clearly → SET brand_read = NULL (proceed to TIER 2 visual)

2. SIZE confidence scoring:
   - 0.95+: "750ml" or "1.5L" text fully visible and clear (common in e-commerce)
   - 0.85-0.94: Size text visible but format slightly unclear
   - 0.70-0.84: Size partially visible or degraded quality (store shelf shadows)
   - <0.70: Cannot read size → SET size_read = NULL

3. PRICE confidence scoring:
   - 0.95+: Price tag fully visible, clear numeric value, high contrast
   - 0.85-0.94: Price visible but slightly blurry or minor glare
   - 0.70-0.84: Price degraded, LED shelf glare, or partially obscured
   - <0.70: Cannot read price → SET price_read = NULL

4. FACINGS confidence scoring:
   - 0.95+: All bottles in group clearly visible, countable without ambiguity
   - 0.85-0.94: Count clear but 1-2 bottles partially obscured at edge
   - 0.70-0.84: Count uncertain, some bottles cut off by frame
   - <0.70: Cannot count bottles accurately → SET facings = NULL

5. LEGIBILITY status (independent from confidence):
   - fully_readable: All text on label is clear, high contrast
   - partial: Some text visible, some obscured by angle, glare, or shadow
   - unreadable: Label mostly obscured, intense glare, or too blurry to read

CRITICAL RULES (NON-NEGOTIABLE):
- NEVER guess or interpolate TEXT fields (brand_read, product_read, size_read, price_read)
- visual_brand_guess is ALLOWED to use visual knowledge — it is SEPARATE from brand_read
- If field confidence < 0.70 → ALWAYS SET THAT TEXT FIELD TO NULL
- Each field is independently scored: one field can be NULL while others are filled
- If price_read is NULL → also set price_confidence to NULL/0
- NEVER "correct" or normalize text: transcribe EXACTLY what you see on the label
- Visual cue fields (bottle_shape, glass_tint, cap_type, label_color, label_design, damage_flags,
  stock_level) are NOT subject to the 0.70 confidence threshold — fill them ALWAYS

IMAGE DEGRADATION CONTEXT:
If the image has glare, bad lighting, or angle issues, you MUST:
1. Reduce confidence for ALL TEXT fields by 0.15
2. Set image_quality_degraded=true
3. Note the specific degradation in degradation_reason
4. Visual cue fields remain unaffected by degradation — still fill them
5. If glare covers >30% of a bottle label, set ALL TEXT field confidences < 0.70 (NULL)
   but STILL fill visual cues and visual_brand_guess

NEAR-IDENTICAL SKU DIFFERENTIATION:
When multiple bottles look similar (e.g., same brand, different flavors):
1. Look for flavor text (citron, raspberry, original) on each bottle
2. Look for size differences (750ml vs 1L) in label text
3. If you cannot differentiate, create ONE observation with brand but NULL product_read
4. Do NOT duplicate observations by guessing flavor variants you cannot read

Output JSON matching this exact schema:
{{
  "alcohol_type": "beer | wine | spirits | liqueur | rtd | cider | non_alcohol | unknown",
  "confidence_overall": 0.0,  // Overall extraction confidence (0-1)
  "image_quality_score": 0.0,  // 0.95+ = professional, 0.85-0.94 = good, 0.70-0.84 = acceptable, <0.70 = poor
  "extraction_confidence": 0.0,  // How confident are you in the extracted data?
  "observations": [
    {{
      "brand_read": "[brand name from label TEXT, or null if unreadable]",
      "visual_brand_guess": "[brand inferred from VISUAL cues, or null]",
      "visual_brand_confidence": 0.0,  // 0-1, confidence in visual brand guess
      "product_read": "[product type from label, or null if unreadable]",
      "size_read": "[volume + unit if visible, e.g., '750ml']",
      "legibility": "fully_readable | partial | unreadable",
      "facings": [count of bottles in this group, or null if uncertain],
      "shelf_position": "top | eye_level | reach | stoop | bottom | endcap | cooler_door | unknown",
      "price_read": "[price number if visible, or null]",
      "status": "confirmed | partial | low_confidence | unmatched | occluded | unreadable",
      "field_confidence": {{
        "brand": [0.0-1.0],
        "size": [0.0-1.0],
        "facings": [0.0-1.0],
        "price": [0.0-1.0]
      }},
      "bottle_shape": "tall_neck | short_squat | handle | flask | wine | can | custom | unknown",
      "glass_tint": "clear | green | brown | blue | frosted | opaque | unknown",
      "cap_type": "screw | cork | crown | plastic | t_top | unknown",
      "label_color": "[dominant color, or unknown]",
      "label_design": "minimal | ornate | vintage | modern | bold_text | illustrated | unknown",
      "damage_flags": "none | torn_label | dust | broken_seal | faded | dented",
      "stock_level": "full | partial | low | empty | unknown",
      "alcohol_subcategory": "[e.g. single_malt_scotch, silver_tequila, ipa, or null]",
      "notes": "[optional]"
    }}
  ],
  "out_of_stock_positions": [],
  "competitor_activity": [],
  "share_of_shelf_notes": null,
  "planogram_flags": [],
  "fixture_type": "gondola | cooler | endcap | floor_display | unknown",
  "image_quality_degraded": false,
  "degradation_reason": null,
  "free_notes": null
}}"""


# ─── Helpers ───────────────────────────────────────────────────────────────────

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def _b64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode()


def _compress_for_vlm(image_bytes: bytes, max_edge: int = 1280, quality: int = 82) -> bytes:
    """Resize and recompress to keep base64 payload under 800 KB for VLM APIs."""
    import cv2
    import numpy as np
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    h, w = img.shape[:2]
    longest = max(w, h)
    if longest > max_edge:
        scale = max_edge / longest
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    compressed = buf.tobytes()
    return compressed if len(compressed) < len(image_bytes) else image_bytes


def _compress_for_fallback(image_bytes: bytes) -> bytes:
    """Aggressive compression for fallback models with strict context limits.
    
    Reduces to 768px max edge, quality 70, to fit Groq's context window.
    Typically produces ~200-300KB JPEGs vs 500-800KB from standard compression.
    """
    import cv2
    import numpy as np
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    h, w = img.shape[:2]
    longest = max(w, h)
    max_edge = 768
    quality = 70
    if longest > max_edge:
        scale = max_edge / longest
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def _clean_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


# ─── Abstract base ─────────────────────────────────────────────────────────────

class VLMClient(ABC):
    name: str = "base"

    @abstractmethod
    async def _call(
        self,
        system: str,
        user_text: str,
        image_bytes: bytes | None,
        prior_context: str | None,
    ) -> str:
        """Return raw string response from the provider."""

    async def pass1(self, image_bytes: bytes, catalog: list[dict] | None = None) -> dict:
        compressed = _compress_for_vlm(image_bytes)
        raw = await self._call(
            system=_PASS1_SYSTEM,
            user_text="Transcribe all visible labels on this shelf. Output JSON only.",
            image_bytes=compressed,
            prior_context=None,
        )
        return _clean_json(raw)

    async def pass2(self, image_bytes: bytes, pass1_result: dict, catalog: list[dict] | None = None) -> dict:
        compressed = _compress_for_vlm(image_bytes)
        catalog_text = ""
        if catalog:
            catalog_text = "\n\nKNOWN CATALOG (for size-aware resolution, not source of truth):\n" + json.dumps(catalog[:80], indent=None)
        raw = await self._call(
            system=_PASS2_SYSTEM,
            user_text=(
                "Pass 1 literal reads:\n"
                + json.dumps(pass1_result, indent=2)
                + catalog_text
                + "\n\nNow produce the full structured audit. Output JSON only."
            ),
            image_bytes=compressed,
            prior_context=None,
        )
        return _clean_json(raw)


# ─── Concrete clients ──────────────────────────────────────────────────────────

class OpenRouterClient(VLMClient):
    """Primary: Qwen2.5-VL-72B via OpenRouter (better OCR + object detection)."""
    name = "qwen2.5-vl-72b@openrouter"
    _model = "qwen/qwen2.5-vl-72b-instruct"
    _base_url = "https://openrouter.ai/api/v1"

    async def _call(self, system, user_text, image_bytes, prior_context):
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")

        content: list[dict] = []
        if image_bytes:
            b64 = _b64(image_bytes)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        content.append({"type": "text", "text": user_text})

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_tokens": 2048,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            for attempt in range(2):
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://kosha.ai",
                        "X-Title": "Kosha Shelf Audit",
                    },
                    json=payload,
                )
                if resp.status_code in _TRANSIENT_STATUS and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                resp.raise_for_status()
                break
        return resp.json()["choices"][0]["message"]["content"]


class GroqQwenClient(VLMClient):
    """Fallback: Qwen3-32B via Groq (same family as primary, native Groq support).
    
    Groq's Qwen models support vision via single-string content format.
    Model: qwen/qwen3-32b (32B params, strong OCR, fast on Groq)
    """
    name = "qwen3-32b@groq"
    _model = "qwen/qwen3-32b"
    _base_url = "https://api.groq.com/openai/v1"

    async def pass1(self, image_bytes: bytes, catalog: list[dict] | None = None) -> dict:
        # Use AGGRESSIVE compression to stay within Groq's context limits
        compressed = _compress_for_fallback(image_bytes)
        raw = await self._call(
            system=_PASS1_SYSTEM,
            user_text="Transcribe all visible labels. JSON only.",
            image_bytes=compressed,
            prior_context=None,
        )
        return _clean_json(raw)

    async def pass2(self, image_bytes: bytes, pass1_result: dict, catalog: list[dict] | None = None) -> dict:
        # Use AGGRESSIVE compression + truncate PASS1 JSON to fit context
        compressed = _compress_for_fallback(image_bytes)
        # Truncate PASS1 JSON to first 500 chars max to save tokens
        pass1_truncated = json.dumps(pass1_result, indent=None)[:500]
        catalog_text = ""
        if catalog:
            catalog_text = "\n\nCATALOG:" + json.dumps(catalog[:50], indent=None)[:400]
        raw = await self._call(
            system=_PASS2_SYSTEM,
            user_text=f"Pass1 reads:{pass1_truncated}{catalog_text}\n\nProduce structured audit. JSON only.",
            image_bytes=compressed,
            prior_context=None,
        )
        return _clean_json(raw)

    async def _call(self, system, user_text, image_bytes, prior_context):
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set")

        # Groq vision API: single string with inline base64 image
        # Format: "data:image/jpeg;base64,<b64>\n\n<text>"
        content_str = user_text
        if image_bytes:
            b64 = _b64(image_bytes)
            content_str = f"data:image/jpeg;base64,{b64}\n\n{user_text}"
        elif prior_context:
            content_str = f"{user_text}\n\nContext: {prior_context}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content_str},
            ],
            "max_tokens": 4096,
            "temperature": 0.0,
            "top_p": 0.95,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            for attempt in range(2):
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code in _TRANSIENT_STATUS and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                resp.raise_for_status()
                break
        return resp.json()["choices"][0]["message"]["content"]


# ─── Orchestrator ──────────────────────────────────────────────────────────────

class VLMOrchestrator:
    """
    Two-tier chain: Qwen (primary) → Groq (fallback on API failure only)

    CRITICAL: Qwen's result is FINAL — even if 0 observations or non-alcohol detected.
    Groq is ONLY used if Qwen API fails (rate limit, auth error, network failure).
    Result from either model is returned immediately — no result-based fallback.

    Latency: ~3-5s per call (network-bound).
    Cost: Qwen 72B ≈ $0.25/image, Llama 3.3 70B ≈ free tier (fallback only).
    """

    def __init__(self):
        self._chain: list[VLMClient] = [
            OpenRouterClient(),    # Primary: Qwen2.5-VL-72B (best OCR)
            GroqQwenClient(),      # Fallback: Qwen3-32B via Groq (same family, fast)
        ]

    async def extract_shelf(self, image_bytes: bytes) -> VLMExtractionResult:
        t0 = time.perf_counter()
        errors: list[str] = []
        fallback_chain: list[str] = []

        for client in self._chain:
            fallback_chain.append(client.name)
            try:
                pass1 = await client.pass1(image_bytes)
                pass2 = await client.pass2(image_bytes, pass1)

                observations = _parse_observations(pass2)
                latency_ms = int((time.perf_counter() - t0) * 1000)

                # CHECK 1: If VLM explicitly says non-alcohol → FINAL REJECTION
                alcohol_type = pass2.get("alcohol_type", "unknown").lower()
                if alcohol_type == "non_alcohol":
                    print(f"[VLM] {client.name} detected NON-ALCOHOLIC content - FINAL REJECTION")
                    return VLMExtractionResult(
                        observations=[],
                        alcohol_type="non_alcohol",
                        confidence_overall=0.0,
                        raw_pass1=pass1,
                        raw_pass2=pass2,
                        model_used=client.name,
                        latency_ms=latency_ms,
                        fallback_chain=fallback_chain,
                    )

                # CHECK 2: Zero observations → return empty result (valid detection)
                if len(observations) == 0:
                    print(f"[VLM] {client.name} extracted 0 observations - returning empty result")
                    return VLMExtractionResult(
                        observations=[],
                        alcohol_type="unknown",
                        confidence_overall=0.0,
                        raw_pass1=pass1,
                        raw_pass2=pass2,
                        model_used=client.name,
                        latency_ms=latency_ms,
                        fallback_chain=fallback_chain,
                    )

                # Calculate overall confidence from RAW pass2 (before _validate_field nulls low-conf fields)
                raw_obs = pass2.get("observations") or []
                all_confs = []
                for o in raw_obs:
                    if isinstance(o, dict):
                        confs = o.get("field_confidence", {})
                        all_confs.extend(confs.values())
                confidence_overall = sum(all_confs) / len(all_confs) if all_confs else 0.0

                print(f"[VLM] {client.name}: alcohol_type={alcohol_type}, obs={len(observations)}, conf={confidence_overall:.2f}, img_quality={float(pass2.get('image_quality_score', 0)):.2f}, extraction_conf={float(pass2.get('extraction_confidence', 0)):.2f}, latency={latency_ms}ms")
                return VLMExtractionResult(
                    observations=observations,
                    out_of_stock_positions=pass2.get("out_of_stock_positions") or [],
                    competitor_activity=pass2.get("competitor_activity") or [],
                    share_of_shelf_notes=pass2.get("share_of_shelf_notes"),
                    planogram_flags=pass2.get("planogram_flags") or [],
                    fixture_type=pass2.get("fixture_type", "unknown"),
                    image_quality_degraded=bool(pass2.get("image_quality_degraded", False)),
                    degradation_reason=pass2.get("degradation_reason"),
                    free_notes=pass2.get("free_notes"),
                    alcohol_type=alcohol_type,
                    confidence_overall=confidence_overall,
                    image_quality_score=float(pass2.get("image_quality_score", 0.0)),
                    extraction_confidence=float(pass2.get("extraction_confidence", 0.0)),
                    raw_pass1=pass1,
                    raw_pass2=pass2,
                    model_used=client.name,
                    latency_ms=latency_ms,
                    fallback_chain=fallback_chain,
                )
            except Exception as e:
                err_detail = f"{client.name}: {type(e).__name__}: {e}"
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        body = e.response.text[:300]
                        err_detail += f" | body: {body}"
                    except:
                        pass
                print(f"[VLM] {err_detail}")
                errors.append(err_detail)
                continue

        raise VLMChainExhausted(errors)


def _validate_field(field_name: str, value: str | int | float | None, confidence: float) -> tuple[str | int | float | None, str | None]:
    if value is None or confidence is None:
        return None, None
    if confidence < 0.70:
        return None, f"{field_name}_low_confidence"
    if field_name == "price":
        try:
            price_str = str(value).strip()
            if not any(c.isdigit() for c in price_str):
                return None, f"{field_name}_not_numeric"
            float(price_str.replace(",", ""))
            return price_str, None
        except (ValueError, AttributeError):
            return None, f"{field_name}_parse_failed"
    elif field_name == "facings":
        try:
            facings_int = int(value) if not isinstance(value, int) else value
            if facings_int < 1 or facings_int > 99:
                return None, f"{field_name}_out_of_range"
            return facings_int, None
        except (ValueError, TypeError):
            return None, f"{field_name}_not_integer"
    return value, None


def _parse_observations(pass2: dict) -> list[Observation]:
    raw_obs = pass2.get("observations") or []
    result = []
    for o in raw_obs:
        if not isinstance(o, dict):
            continue
        try:
            field_conf = o.get("field_confidence") or {}
            brand_read, _ = _validate_field("brand", o.get("brand_read"), field_conf.get("brand", 0.0))
            size_read, _ = _validate_field("size", o.get("size_read"), field_conf.get("size", 0.0))
            price_read, _ = _validate_field("price", o.get("price_read"), field_conf.get("price", 0.0))
            facings, _ = _validate_field("facings", o.get("facings"), field_conf.get("facings", 0.0))

            obs_dict = {k: v for k, v in o.items() if k in Observation.model_fields}
            obs_dict["brand_read"] = brand_read
            obs_dict["size_read"] = size_read
            obs_dict["price_read"] = price_read
            obs_dict["facings"] = facings
            if "visual_brand_confidence" not in obs_dict or obs_dict.get("visual_brand_confidence") is None:
                obs_dict["visual_brand_confidence"] = 0.0

            result.append(Observation(**obs_dict))
        except Exception:
            pass
    return result