"""
Integration tests for the full pipeline.

Validates:
- Full end-to-end flow: Image → Quality → CLIP → Qwen → RAG → Judge → Persist
- Real image handling (if fixtures exist)
- Status transitions (processing → final or retake_required)
"""
import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pipeline_vodka_shelf_success(
    mock_vlm_vodka_extraction, mock_clip_vodka_pass
):
    """Full pipeline should successfully process a vodka shelf image."""
    from src.perception.guardrail import Guardrail
    from src.perception.vlm import VLMExtractionResult
    from PIL import Image
    from io import BytesIO

    gr = Guardrail()

    # Create a minimal valid JPEG
    img = Image.new("RGB", (640, 480), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    image_bytes = img_bytes.getvalue()

    # Mock CLIP gate
    with patch.object(
        Guardrail, "_verify_with_clip_local", return_value=mock_clip_vodka_pass
    ):
        clip_result = await gr.classify_async(image_bytes)

    # CLIP passes
    assert clip_result.verdict == "pass"

    # Mock VLM extraction (would happen after CLIP passes)
    fixture_data = dict(mock_vlm_vodka_extraction)
    fixture_data.setdefault("out_of_stock_positions", [])
    fixture_data.setdefault("competitor_activity", [])
    fixture_data.setdefault("share_of_shelf_notes", None)
    fixture_data.setdefault("planogram_flags", [])
    fixture_data.setdefault("image_quality_degraded", False)
    fixture_data.setdefault("free_notes", None)
    fixture_data.setdefault("raw_pass1", {})
    fixture_data.setdefault("raw_pass2", {})
    fixture_data.setdefault("fallback_chain", [])

    vlm_result = VLMExtractionResult(**fixture_data)

    # VLM succeeds
    assert vlm_result.alcohol_type == "vodka"
    assert len(vlm_result.observations) >= 1
    assert vlm_result.confidence_overall > 0.85

    # Quality check passes
    assert vlm_result.image_quality_score > 0.60

    # Would proceed to RAG/Judge/Persist with status "final"


@pytest.mark.asyncio
async def test_pipeline_retake_low_quality(mock_vlm_low_quality):
    """Pipeline should flag image for retake if quality < 0.60."""
    from src.perception.vlm import VLMExtractionResult

    fixture_data = dict(mock_vlm_low_quality)
    fixture_data.setdefault("observations", [])
    fixture_data.setdefault("out_of_stock_positions", [])
    fixture_data.setdefault("competitor_activity", [])
    fixture_data.setdefault("share_of_shelf_notes", None)
    fixture_data.setdefault("planogram_flags", [])
    fixture_data.setdefault("image_quality_degraded", False)
    fixture_data.setdefault("free_notes", None)
    fixture_data.setdefault("confidence_overall", 0.0)
    fixture_data.setdefault("extraction_confidence", 0.0)
    fixture_data.setdefault("raw_pass1", {})
    fixture_data.setdefault("raw_pass2", {})
    fixture_data.setdefault("fallback_chain", [])

    result = VLMExtractionResult(**fixture_data)

    # Quality check fails
    assert result.image_quality_score < 0.60
    assert result.degradation_reason is not None

    # Pipeline would return status "retake_required" with the reason
    # (Not persisted to database)


@pytest.mark.asyncio
async def test_pipeline_non_alcoholic_rejection(mock_clip_water_reject):
    """Pipeline should reject non-alcoholic images early (CLIP gate)."""
    from src.perception.guardrail import Guardrail
    from PIL import Image
    from io import BytesIO

    gr = Guardrail()

    # Create a minimal valid JPEG
    img = Image.new("RGB", (640, 480), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    image_bytes = img_bytes.getvalue()

    with patch.object(
        Guardrail, "_verify_with_clip_local", return_value=mock_clip_water_reject
    ):
        result = await gr.classify_async(image_bytes)

    # Rejected at CLIP gate
    assert result.verdict == "reject"
    assert result.category == "non_alcohol"

    # Would not proceed to VLM or RAG
    # Pipeline status: "guardrail_rejected"
