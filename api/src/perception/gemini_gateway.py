"""
Gemini Flash - PRIMARY GATEKEEPER for alcohol vs non-alcohol detection.

This is the FIRST gate that runs. It must:
1. Instantly reject non-alcoholic beverages (water, soda, juice, coffee, tea)
2. Instantly reject food, non-beverages, selfies, screenshots
3. Accept ONLY retail alcohol shelves
4. Return REAL reasoning from LLM, not hardcoded messages

Fails gracefully to YOLO+CLIP fallback if API times out.
"""
import asyncio
import base64
import json
import os
from io import BytesIO
from typing import Tuple

import httpx
from PIL import Image

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_FLASH_ENABLED = bool(GEMINI_API_KEY)
GEMINI_TIMEOUT = 10.0
GEMINI_ACCEPTANCE_THRESHOLD = 0.75
GEMINI_REJECTION_THRESHOLD = 0.60


class GeminiGateway:
    """Gemini Flash 2.0 classifier for alcohol shelf detection."""

    SYSTEM_PROMPT = """You are a STRICT gatekeeper for retail alcohol shelf photography.

Your ONLY job: Determine if this image is a RETAIL ALCOHOL SHELF for business inventory.

ACCEPT CRITERIA (ALL must be true):
✅ Shows BEER, WINE, SPIRITS, LIQUEUR, RTD COCKTAILS, or similar alcoholic beverages
✅ Items are on a RETAIL SHELF or cooler display (NOT in someone's hand)
✅ Professional retail setting (liquor store, supermarket alcohol aisle, bar, warehouse)
✅ At least 3+ beverage bottles/cans/items visible on shelf
✅ Image quality is sufficient (labels somewhat legible, not completely blurry/dark)

REJECT CRITERIA (reject if ANY of these):
❌ NON-ALCOHOLIC beverages: water, soda, juice, sports drinks, coffee, tea, energy drinks
❌ Food items: snacks, chips, candy, groceries, prepared food
❌ Non-beverage items: books, electronics, clothing, household goods, personal items
❌ Wrong context: office, home, car, outdoor scene, person at desk/counter
❌ Selfie or portrait: person's face in photo
❌ Technology: screenshot, computer screen, phone screen
❌ Document: receipt, invoice, printed text
❌ Single item in hand: personal drink bottle (not retail)
❌ Empty shelf with no products
❌ Severe quality issues: completely dark, severe blur, overexposed

IMAGE QUALITY CHECKS:
- Darkness: Is histogram mean < 40? (too dark, can't read labels)
- Brightness: Is histogram mean > 220? (overexposed, washed out)
- Blur: Are edges sharp enough to read brand names?
- Distance: Can you reasonably see bottle labels? (not from 20+ feet away)
- Obstruction: Are key labels visible or fully blocked?

RESPOND WITH VALID JSON ONLY (no markdown, no explanation, just JSON):
{
  "verdict": "accept" | "reject" | "uncertain",
  "confidence": <float 0.0-1.0>,
  "reason": "<clear explanation of decision>",
  "detected_content": "<what you actually see in image>",
  "quality_issues": ["<issue1>", "<issue2>"] or [],
  "alcohol_type": "<beer|wine|spirits|rtd|unknown|non_alcohol>",
  "product_count": <estimated visible items>,
  "setting_type": "<retail_shelf|hand_held|home|office|outdoor|unknown>"
}

Be STRICT. Better to reject borderline cases than waste processing on non-retail images.
"""

    async def classify(self, image_bytes: bytes) -> Tuple[str, float, str]:
        """
        Classify image as accept/reject/fallback.

        Returns:
            (verdict: str, confidence: float, reason: str)
            verdict: "accept" | "reject" | "fallback_to_clip"
        """
        if not GEMINI_FLASH_ENABLED:
            return "fallback_to_clip", 0.0, "Gemini Flash API key not configured"

        try:
            # Encode image to base64
            pil = Image.open(BytesIO(image_bytes))
            pil = pil.convert("RGB")
            buffered = BytesIO()
            pil.save(buffered, format="JPEG", quality=85)
            b64_image = base64.b64encode(buffered.getvalue()).decode()

            # Call Gemini Flash API with async timeout
            async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                    json={
                        "system_instruction": {"parts": [{"text": self.SYSTEM_PROMPT}]},
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": "image/jpeg",
                                            "data": b64_image,
                                        }
                                    }
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.1,  # Low temp for consistent decisions
                            "max_output_tokens": 300,
                            "response_mime_type": "application/json",
                        },
                    },
                )
                response.raise_for_status()

            # Parse response
            result = response.json()
            content = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "{}")
            )

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                print(f"[WARN] Gemini response not JSON: {content[:100]}")
                return "fallback_to_clip", 0.0, "Gemini Flash parse error"

            verdict = parsed.get("verdict", "uncertain").lower()
            confidence = float(parsed.get("confidence", 0.0))
            reason = parsed.get("reason", "No reason provided")
            detected_content = parsed.get("detected_content", "Unknown")
            quality_issues = parsed.get("quality_issues", [])
            alcohol_type = parsed.get("alcohol_type", "unknown")

            # STRICT DECISION LOGIC
            if verdict == "reject" and confidence >= GEMINI_REJECTION_THRESHOLD:
                # High confidence rejection - return immediately
                issue_str = ", ".join(quality_issues) if quality_issues else reason
                return (
                    "reject",
                    confidence,
                    f"{reason} | Issues: {issue_str}" if quality_issues else reason,
                )

            elif verdict == "accept" and confidence >= GEMINI_ACCEPTANCE_THRESHOLD:
                # High confidence acceptance - proceed to YOLO/CLIP
                return "accept", confidence, reason

            else:
                # Uncertain or low confidence - fallback to YOLO+CLIP for verification
                return (
                    "fallback_to_clip",
                    confidence,
                    f"Gemini uncertain (conf={confidence:.2f}). Content: {detected_content}",
                )

        except asyncio.TimeoutError:
            print("[WARN] Gemini Flash timeout")
            return "fallback_to_clip", 0.0, "Gemini Flash timeout (10s). Using fallback."
        except httpx.HTTPError as e:
            print(f"[WARN] Gemini Flash HTTP error: {e}")
            return "fallback_to_clip", 0.0, f"Gemini Flash API error: {str(e)[:50]}"
        except Exception as e:
            print(f"[ERROR] Gemini Flash unexpected error: {e}")
            return "fallback_to_clip", 0.0, f"Unexpected error. Using fallback: {str(e)[:50]}"


# Singleton instance
_gemini = None


def get_gemini_gateway() -> GeminiGateway:
    global _gemini
    if _gemini is None:
        _gemini = GeminiGateway()
    return _gemini
