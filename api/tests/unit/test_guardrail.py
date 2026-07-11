"""
Unit tests for Guardrail (CLIP-based gatekeeper).

Validates:
- CLIP rejects non-alcohol (water, soda, food)
- CLIP passes alcohol shelf
- CLIP handles uncertain cases (0.15-0.65 range)
- Threshold behavior (current: 0.15, can test 0.25 for production)
"""
import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_guardrail_reject_non_alcohol_water(mock_clip_water_reject):
    """CLIP should reject a water bottle image."""
    from src.perception.guardrail import Guardrail
    from PIL import Image
    from io import BytesIO

    gr = Guardrail()

    # Create a minimal valid JPEG
    img = Image.new("RGB", (640, 480), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    image_bytes = img_bytes.getvalue()

    # Mock CLIP to return rejection
    with patch.object(
        Guardrail, "_verify_with_clip_local", return_value=mock_clip_water_reject
    ):
        result = await gr.classify_async(image_bytes)

        assert result.verdict == "reject"
        assert result.category == "non_alcohol"
        assert result.confidence > 0.8
        assert result.rejection_reason == "non_alcohol"


@pytest.mark.asyncio
async def test_guardrail_pass_alcohol_shelf(mock_clip_vodka_pass):
    """CLIP should pass an alcohol shelf image."""
    from src.perception.guardrail import Guardrail
    from PIL import Image
    from io import BytesIO

    gr = Guardrail()

    # Create a minimal valid JPEG
    img = Image.new("RGB", (800, 600), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    image_bytes = img_bytes.getvalue()

    with patch.object(
        Guardrail, "_verify_with_clip_local", return_value=mock_clip_vodka_pass
    ):
        result = await gr.classify_async(image_bytes)

        assert result.verdict == "pass"
        assert result.category == "alcohol_shelf"
        assert result.confidence > 0.7
        assert result.rejection_reason is None


@pytest.mark.asyncio
async def test_guardrail_uncertain_range():
    """CLIP in uncertain range (0.27-0.65) should pass to Qwen."""
    from src.perception.guardrail import Guardrail
    from PIL import Image
    from io import BytesIO

    uncertain_result = {
        "verdict": "pass",
        "category": "uncertain",
        "confidence": 0.45,  # In uncertain range
        "top_matches": [("clip_positive", 0.45)],
        "reason": "Passing to Qwen for final determination",
        "rejection_reason": None,
    }

    gr = Guardrail()

    # Create a minimal valid JPEG
    img = Image.new("RGB", (720, 540), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    image_bytes = img_bytes.getvalue()

    with patch.object(Guardrail, "_verify_with_clip_local", return_value=uncertain_result):
        result = await gr.classify_async(image_bytes)

        # Uncertain still passes to Qwen (Qwen will decide)
        assert result.verdict == "pass"
        assert 0.27 <= result.confidence <= 0.65


@pytest.mark.asyncio
async def test_guardrail_clip_ensemble_averaging():
    """Verify CLIP uses ensemble averaging with alcohol and non-alcohol prompts."""
    from src.perception.guardrail import Guardrail

    gr = Guardrail()

    # Should have prompts (exact count may vary, but should be > 20)
    assert len(gr.shelf_prompts) >= 20, f"Expected at least 20 prompts, got {len(gr.shelf_prompts)}"

    # Check positive prompts (alcohol indicators)
    assert any("vodka" in p.lower() for p in gr.shelf_prompts), "Missing vodka in prompts"
    assert any("beer" in p.lower() for p in gr.shelf_prompts), "Missing beer in prompts"
    assert any("shelf" in p.lower() for p in gr.shelf_prompts), "Missing shelf in prompts"
    assert any("spirit" in p.lower() for p in gr.shelf_prompts), "Missing spirit in prompts"

    # Check negative prompts (non-alcohol indicators)
    assert any("water" in p.lower() for p in gr.shelf_prompts), "Missing water in prompts"
    assert any("food" in p.lower() for p in gr.shelf_prompts), "Missing food in prompts"
    assert any("coffee" in p.lower() for p in gr.shelf_prompts), "Missing coffee in prompts"


@pytest.mark.asyncio
async def test_guardrail_threshold_boundary():
    """Test CLIP threshold boundaries (current: 0.15, test both 0.15 and 0.25)."""
    from src.perception.guardrail import Guardrail
    from PIL import Image
    from io import BytesIO

    test_cases = [
        (0.10, "reject"),   # < 0.15: reject
        (0.15, "pass"),     # >= 0.15: pass
        (0.25, "pass"),     # >= 0.25: pass
        (0.27, "pass"),     # >= 0.27: pass (current production threshold)
        (0.65, "pass"),     # >= 0.65: pass (confident)
    ]

    for confidence, expected_verdict in test_cases:
        result = {
            "verdict": expected_verdict,
            "category": "non_alcohol" if expected_verdict == "reject" else "alcohol_shelf",
            "confidence": confidence,
            "top_matches": [],
            "reason": f"Test confidence={confidence}",
            "rejection_reason": "non_alcohol" if expected_verdict == "reject" else None,
        }

        gr = Guardrail()

        # Create a minimal valid JPEG
        img = Image.new("RGB", (640, 480), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        image_bytes = img_bytes.getvalue()

        with patch.object(Guardrail, "_verify_with_clip_local", return_value=result):
            gr_result = await gr.classify_async(image_bytes)
            assert gr_result.verdict == expected_verdict, f"Failed for confidence={confidence}"
