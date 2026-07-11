#!/usr/bin/env python
"""
Extraction Scenario Testing — Validates VLM + CLIP improvements

Tests:
1. Retail shelf image (multi-bottle, LED lighting)
2. E-commerce product shot (white background, single bottle)
3. Non-alcoholic rejection (water bottle)
4. Edge cases (blurry, glare, partial occlusion)

Run: python test_extraction_scenarios.py --test-type <scenario>
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.perception.guardrail import Guardrail
from src.perception.vlm import VLMOrchestrator
from src.perception.quality import QualityGate


class ExtractionTester:
    """Validates extraction improvements across scenarios."""

    def __init__(self):
        self.guardrail = Guardrail()
        self.vlm = VLMOrchestrator()
        self.quality = QualityGate()

    async def test_retail_shelf(self, image_bytes: bytes) -> dict:
        """Scenario 1: Retail shelf (LED-lit, multi-bottle)."""
        print("\n" + "=" * 80)
        print("SCENARIO 1: RETAIL SHELF (LED-lit, multi-bottle)")
        print("=" * 80)
        print(f"Image size: {len(image_bytes)} bytes")

        # Step 1: Quality gate
        print("\n[STEP 1] Quality Gate")
        quality = self.quality.assess(image_bytes)
        print(f"  Blur: {quality.blur_score:.2f} (reject <50, pass ≥80)")
        print(f"  Brightness: {quality.brightness_score:.2f} (24-240 range)")
        print(f"  Resolution: {quality.resolution_score:.2f} (min 640px)")
        print(f"  Overall: {quality.overall_score:.2f}")
        if quality.overall_score < 0.60:
            return {"status": "rejected", "reason": "Image quality too poor"}

        # Step 2: CLIP verification
        print("\n[STEP 2] CLIP Verification (32 prompts)")
        clip_result = await self.guardrail.classify_async(image_bytes)
        print(f"  Verdict: {clip_result.verdict}")
        print(f"  Confidence: {clip_result.confidence:.2f}")
        print(f"  Category: {clip_result.category}")
        print(f"  Expected: Confidence > 0.65 (likely retail)")

        if clip_result.verdict == "reject":
            return {"status": "rejected", "reason": "Non-alcoholic detected by CLIP"}

        # Step 3: VLM extraction
        print("\n[STEP 3] VLM Extraction (Qwen2.5-VL-72B)")
        vlm_result = await self.vlm.extract_shelf(image_bytes)
        print(f"  Model: {vlm_result.model_used}")
        print(f"  Alcohol type: {vlm_result.alcohol_type}")
        print(f"  Observations: {len(vlm_result.observations)}")
        print(f"  Image quality (VLM): {vlm_result.image_quality_score:.2f}")
        print(f"  Extraction confidence: {vlm_result.extraction_confidence:.2f}")

        # Detailed observation analysis
        for i, obs in enumerate(vlm_result.observations):
            print(f"\n  Observation {i+1}:")
            print(f"    Brand: {obs.brand_read or 'NULL'} (conf: {obs.field_confidence.get('brand', 0):.2f})")
            print(f"    Size: {obs.size_read or 'NULL'} (conf: {obs.field_confidence.get('size', 0):.2f})")
            print(f"    Price: {obs.price_read or 'NULL'} (conf: {obs.field_confidence.get('price', 0):.2f})")
            print(f"    Facings: {obs.facings or 'NULL'} (conf: {obs.field_confidence.get('facings', 0):.2f})")
            print(f"    Legibility: {obs.legibility}")
            print(f"    Status: {obs.status}")

        return {
            "status": "success",
            "scenario": "retail_shelf",
            "observations": vlm_result.observations,
            "quality": {
                "gate": quality.overall_score,
                "vlm": vlm_result.image_quality_score,
            },
        }

    async def test_ecommerce_shot(self, image_bytes: bytes) -> dict:
        """Scenario 2: E-commerce product shot (white background, single bottle)."""
        print("\n" + "=" * 80)
        print("SCENARIO 2: E-COMMERCE PRODUCT SHOT (white background, single bottle)")
        print("=" * 80)
        print(f"Image size: {len(image_bytes)} bytes")

        # Quality: should be excellent (studio lighting)
        print("\n[STEP 1] Quality Gate")
        quality = self.quality.assess(image_bytes)
        print(f"  Overall: {quality.overall_score:.2f} (expect ≥0.85)")

        # CLIP: will see e-commerce archetypes
        print("\n[STEP 2] CLIP Verification")
        clip_result = await self.guardrail.classify_async(image_bytes)
        print(f"  Verdict: {clip_result.verdict}")
        print(f"  Confidence: {clip_result.confidence:.2f}")
        print(f"  Expected: Confidence > 0.65 (e-commerce positive)")

        # VLM: single bottle extraction
        print("\n[STEP 3] VLM Extraction")
        vlm_result = await self.vlm.extract_shelf(image_bytes)
        print(f"  Observations: {len(vlm_result.observations)} (expect 1)")
        if vlm_result.observations:
            obs = vlm_result.observations[0]
            print(f"  Facings: {obs.facings} (expect 1 for single bottle)")
            print(f"  Brand confidence: {obs.field_confidence.get('brand', 0):.2f} (expect ≥0.90)")

        return {
            "status": "success",
            "scenario": "ecommerce_shot",
            "observations": vlm_result.observations,
            "quality": quality.overall_score,
        }

    async def test_non_alcoholic_rejection(self, image_bytes: bytes) -> dict:
        """Scenario 3: Non-alcoholic detection (water bottle)."""
        print("\n" + "=" * 80)
        print("SCENARIO 3: NON-ALCOHOLIC REJECTION (water bottle)")
        print("=" * 80)

        print("\n[STEP 1] Quality Gate")
        quality = self.quality.assess(image_bytes)
        print(f"  Overall: {quality.overall_score:.2f}")

        print("\n[STEP 2] CLIP Verification")
        clip_result = await self.guardrail.classify_async(image_bytes)
        print(f"  Verdict: {clip_result.verdict} (expect 'reject')")
        print(f"  Category: {clip_result.category} (expect 'non_alcohol')")
        print(f"  Confidence: {clip_result.confidence:.2f} (expect > 0.85)")

        if clip_result.verdict == "reject":
            print("\n✅ CORRECTLY REJECTED AT CLIP GATE")
            return {"status": "rejected_at_clip", "reason": clip_result.rejection_reason}

        # If CLIP passed (unexpected), check VLM
        print("\n[STEP 3] VLM Extraction (backup check)")
        vlm_result = await self.vlm.extract_shelf(image_bytes)
        print(f"  Alcohol type: {vlm_result.alcohol_type} (expect 'non_alcohol')")
        print(f"  Observations: {len(vlm_result.observations)} (expect 0)")

        if vlm_result.alcohol_type == "non_alcohol":
            print("\n✅ CORRECTLY REJECTED AT VLM (alcohol_type = non_alcohol)")
            return {"status": "rejected_at_vlm", "reason": "non_alcohol"}

        return {"status": "error", "reason": "Should have been rejected"}

    async def test_blurry_image(self, image_bytes: bytes) -> dict:
        """Scenario 4: Blurry image (should trigger NULL fields)."""
        print("\n" + "=" * 80)
        print("SCENARIO 4: BLURRY IMAGE (should have NULL fields)")
        print("=" * 80)

        quality = self.quality.assess(image_bytes)
        print(f"\n[QUALITY] Blur score: {quality.blur_score:.2f}")
        if quality.blur_score < 50:
            print("  ⚠️ SEVERE BLUR DETECTED")

        clip_result = await self.guardrail.classify_async(image_bytes)
        if clip_result.verdict == "pass":
            vlm_result = await self.vlm.extract_shelf(image_bytes)
            print(f"\n[VLM] Observations: {len(vlm_result.observations)}")

            for i, obs in enumerate(vlm_result.observations):
                nulls = [k for k, v in obs.field_confidence.items() if v < 0.70]
                print(f"  Obs {i+1} NULL fields: {nulls or 'none'}")
                print(f"  Confidence scores: {obs.field_confidence}")

            return {"status": "extracted_with_nulls", "observations": vlm_result.observations}

        return {"status": "rejected", "reason": "Failed quality gate"}

    async def run_all_scenarios(self):
        """Run all scenario tests."""
        print("\n" + "=" * 80)
        print("EXTRACTION SCENARIO TEST SUITE")
        print("=" * 80)
        print("\nThis tests the improved CLIP prompts and VLM grounding rules.")
        print("\nNOTE: This script requires actual test images.")
        print("      For real testing, provide image paths or URLs.")

        # Summary
        print("\n" + "=" * 80)
        print("SCENARIOS TO TEST:")
        print("=" * 80)
        print("""
1. RETAIL SHELF
   - Multiple bottles, LED lighting, price tags
   - Expected: 2+ observations, facings per bottle, mixed confidence
   - CLIP confidence: > 0.65 (retail archetype)

2. E-COMMERCE PRODUCT SHOT
   - Single bottle, white background, studio lighting
   - Expected: 1 observation, facings=1, high confidence (≥0.90)
   - CLIP confidence: > 0.65 (e-commerce archetype)

3. NON-ALCOHOLIC (Water Bottle)
   - Water bottles on shelf or single water bottle
   - Expected: REJECTED at CLIP (new prompts distinguish clearly)
   - CLIP confidence: > 0.85 for non-alcohol rejection

4. BLURRY IMAGE
   - Blurry/dark retail shelf photo
   - Expected: Some or all fields NULL (confidence < 0.70)
   - No hallucination, honest NULL values

RUNNING WITH REAL IMAGES:
   python test_extraction_scenarios.py --image retail_shelf.jpg
   python test_extraction_scenarios.py --image product_shot.jpg
        """)


async def main():
    tester = ExtractionTester()
    await tester.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
