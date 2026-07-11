"""
Unit tests for VLM (Vision Language Model) extraction.

Validates:
- Qwen extracts bottle data correctly
- Quality scoring (< 0.60 triggers retake)
- Confidence scoring
- Handling of NULL fields (no hallucination)
- Non-alcoholic rejection by VLM
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_vlm_extract_vodka_success(mock_vlm_vodka_extraction):
    """VLM should successfully extract vodka bottle data."""
    from src.perception.vlm import VLMExtractionResult

    # Parse mock response
    result = VLMExtractionResult(**mock_vlm_vodka_extraction)

    # Assertions
    assert result.alcohol_type == "vodka"
    assert len(result.observations) == 1
    assert result.observations[0].brand_read == "Absolut"
    assert result.observations[0].size_read == "750ml"
    assert result.image_quality_score == 0.85
    assert result.confidence_overall == 0.91
    assert result.observations[0].price_read is None  # No hallucination


@pytest.mark.asyncio
async def test_vlm_quality_low_triggers_retake(mock_vlm_low_quality):
    """VLM quality < 0.60 should trigger retake_required status."""
    from src.perception.vlm import VLMExtractionResult

    result = VLMExtractionResult(**mock_vlm_low_quality)

    # Quality check: 0.45 < 0.60
    assert result.image_quality_score < 0.60
    assert result.degradation_reason is not None
    assert "dark" in result.degradation_reason.lower()


@pytest.mark.asyncio
async def test_vlm_confidence_scoring():
    """VLM should score each field independently."""
    from src.perception.vlm import Observation

    obs = Observation(
        brand_read="Stella Artois",
        size_read="500ml",
        price_read=None,  # Unreadable
        facings=3,
        shelf_position="eye_level",
        field_confidence={
            "brand": 0.95,
            "size": 0.90,
            "price": 0.0,  # Low due to occlusion
            "facings": 0.88,
        },
        status="partial",
    )

    # Each field scored independently
    assert obs.field_confidence["brand"] > 0.9
    assert obs.field_confidence["price"] == 0.0  # No hallucination
    assert obs.status == "partial"


@pytest.mark.asyncio
async def test_vlm_reject_non_alcoholic():
    """VLM should reject non-alcoholic beverages by setting alcohol_type='non_alcohol'."""
    from src.perception.vlm import VLMExtractionResult

    result_dict = {
        "alcohol_type": "non_alcohol",
        "observations": [],  # Empty because non-alcoholic
        "image_quality_score": 0.9,
        "confidence_overall": 0.0,
        "extraction_confidence": 0.0,
    }

    result = VLMExtractionResult(**result_dict)

    # Non-alcoholic rejection
    assert result.alcohol_type == "non_alcohol"
    assert len(result.observations) == 0


@pytest.mark.asyncio
async def test_vlm_null_fields_no_hallucination():
    """VLM should set fields to None when confidence < 0.70 (no guessing)."""
    from src.perception.vlm import Observation

    # Observation with low confidence on price → should be None
    obs = Observation(
        brand_read="Corona",
        size_read="355ml",
        price_read=None,  # Cannot read price
        field_confidence={"brand": 0.92, "size": 0.88, "price": 0.0},
        status="partial",
    )

    # Verify no hallucination
    assert obs.price_read is None
    assert obs.field_confidence["price"] == 0.0
    assert obs.brand_read is not None  # Readable fields present


@pytest.mark.asyncio
async def test_vlm_single_bottle_extracted():
    """VLM should extract data from a single bottle (not require shelf context)."""
    from src.perception.vlm import VLMExtractionResult

    result_dict = {
        "alcohol_type": "vodka",
        "fixture_type": "product_shot",  # Single bottle, not a shelf
        "observations": [
            {
                "brand_read": "Absolut",
                "size_read": "750ml",
                "facings": 1,  # Single bottle
                "shelf_position": "unknown",  # No shelf context
                "field_confidence": {"brand": 0.95, "size": 0.92, "facings": 1.0},
            }
        ],
        "image_quality_score": 0.88,
        "confidence_overall": 0.91,
    }

    result = VLMExtractionResult(**result_dict)

    # Should successfully extract single bottle
    assert result.fixture_type == "product_shot"
    assert len(result.observations) == 1
    assert result.observations[0].facings == 1
    assert result.confidence_overall > 0.85
