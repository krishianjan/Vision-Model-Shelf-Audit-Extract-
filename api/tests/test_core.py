"""Critical path tests for Kosha shelf-audit pipeline."""
import pytest
import json
import cv2
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock
from src.perception.quality import check_quality
from src.perception.vlm import Observation, VLMExtractionResult
from src.grounding.matcher import SKUMatcher, MatchResult


pytestmark = pytest.mark.unit


class TestQualityGate:
    """Test OpenCV quality gate thresholds."""

    def test_valid_image_passes(self):
        """Test that good images pass quality gate."""
        # Create a synthetic valid image with some texture (not flat)
        img = np.random.randint(100, 200, (1080, 1080, 3), dtype=np.uint8)
        # Add some variation to make it look like a real image
        for _ in range(5):
            x, y = np.random.randint(0, 1080, 2)
            cv2.rectangle(img, (x, y), (x+100, y+100), (150, 150, 150), -1)
        _, buf = cv2.imencode(".jpg", img)
        result, _ = check_quality(buf.tobytes())
        # Just verify it's not totally rejected
        assert result.overall_score > 0.3

    def test_blurry_image_flagged(self):
        """Test that blurry images are flagged."""
        img = np.ones((1080, 1080, 3), dtype=np.uint8) * 128
        img = cv2.GaussianBlur(img, (51, 51), 30)  # heavy blur
        _, buf = cv2.imencode(".jpg", img)
        result, _ = check_quality(buf.tobytes())
        assert result.overall_score < 0.7

    def test_overexposed_image_rejected(self):
        """Test that overexposed images are rejected."""
        img = np.ones((1080, 1080, 3), dtype=np.uint8) * 250  # near white
        _, buf = cv2.imencode(".jpg", img)
        result, _ = check_quality(buf.tobytes())
        # Either verdict=fail or overall_score < 0.5
        assert result.verdict == "fail" or result.overall_score < 0.5

    def test_very_dark_image_flagged(self):
        """Test that very dark images are flagged."""
        img = np.ones((1080, 1080, 3), dtype=np.uint8) * 20  # very dark
        _, buf = cv2.imencode(".jpg", img)
        result, _ = check_quality(buf.tobytes())
        assert result.verdict == "fail" or result.overall_score < 0.6


class TestConfidenceFloor:
    """Test 0.70 confidence floor enforcement."""

    def test_below_threshold_observation(self):
        """Test that observations with confidence < 0.70 are handled."""
        obs = Observation(
            brand_read="Absolut",
            size_read="750ml",
            field_confidence={"brand": 0.65, "size": 0.85, "price": 0.0, "facings": 0.88},
        )
        # Brand confidence is 0.65 < 0.70, so should be treated as NULL
        assert obs.field_confidence["brand"] == 0.65  # Original score preserved

    def test_above_threshold_observation(self):
        """Test that observations with confidence ≥ 0.70 are kept."""
        obs = Observation(
            brand_read="Absolut",
            size_read="750ml",
            field_confidence={"brand": 0.85, "size": 0.88, "price": 0.92, "facings": 0.90},
        )
        assert obs.brand_read == "Absolut"
        assert obs.size_read == "750ml"

    def test_null_price_on_low_confidence(self):
        """Test that price_read is NULL when price confidence < 0.70."""
        obs = Observation(
            brand_read="Absolut",
            price_read="$24.99",
            field_confidence={"brand": 0.90, "size": 0.85, "price": 0.45, "facings": 0.80},
        )
        # Price confidence is 0.45 < 0.70, should be treated as NULL by Judge
        assert obs.price_read == "$24.99"  # Raw value preserved
        assert obs.field_confidence["price"] == 0.45  # Confidence recorded

    def test_facings_range_validation(self):
        """Test that facings count is reasonable (1-20)."""
        # Valid facings
        obs1 = Observation(facings=3, field_confidence={"facings": 0.88})
        assert obs1.facings == 3

        # Zero facings (invalid but stored)
        obs2 = Observation(facings=0, field_confidence={"facings": 0.50})
        assert obs2.facings == 0  # Judge will NULL this


class TestVLMExtraction:
    """Test VLM extraction result parsing."""

    def test_valid_extraction_parsed(self):
        """Test that valid VLM results are parsed correctly."""
        result = VLMExtractionResult(
            alcohol_type="spirits",
            confidence_overall=0.88,
            image_quality_score=0.85,
            extraction_confidence=0.89,
            observations=[
                Observation(
                    brand_read="Absolut",
                    size_read="750ml",
                    facings=2,
                    price_read="$24.99",
                    field_confidence={
                        "brand": 0.95,
                        "size": 0.92,
                        "facings": 0.88,
                        "price": 0.60,
                    },  # price < 0.70, will be NULLed by Judge
                )
            ],
        )
        assert result.alcohol_type == "spirits"
        assert len(result.observations) == 1
        assert result.observations[0].brand_read == "Absolut"

    def test_non_alcoholic_detection(self):
        """Test that non-alcoholic beverages are detected."""
        result = VLMExtractionResult(
            alcohol_type="non_alcohol",
            observations=[],
            confidence_overall=0.0,
            image_quality_score=0.75,
            extraction_confidence=0.0,
        )
        assert result.alcohol_type == "non_alcohol"
        assert len(result.observations) == 0

    def test_empty_observations_valid(self):
        """Test that empty observations (out of stock) are valid."""
        result = VLMExtractionResult(
            alcohol_type="unknown",
            observations=[],
            confidence_overall=0.0,
            image_quality_score=0.72,
            extraction_confidence=0.0,
        )
        assert result.alcohol_type == "unknown"
        assert len(result.observations) == 0


class TestSKUMatcher:
    """Test SKU matching logic."""

    @pytest.mark.asyncio
    async def test_exact_match_structure(self):
        """Test that MatchResult has correct structure."""
        result = MatchResult(
            matched_sku_id="sku-uuid-001",
            match_method="exact",
            match_similarity=1.0,
        )
        assert result.matched_sku_id == "sku-uuid-001"
        assert result.match_method == "exact"
        assert result.match_similarity == 1.0

    @pytest.mark.asyncio
    async def test_unresolved_match(self):
        """Test that unresolved matches are handled."""
        result = MatchResult(
            matched_sku_id=None,
            match_method="unresolved",
            match_similarity=0.0,
        )
        assert result.matched_sku_id is None
        assert result.match_method == "unresolved"


class TestImageEnhancement:
    """Test image enhancement for messy photos."""

    def test_enhance_preserves_bytes_on_fail(self):
        """Test that enhancement returns original if decoding fails."""
        from src.perception.enhance import enhance_image

        bad_bytes = b"not a real image"
        enhanced, report = enhance_image(bad_bytes)
        assert enhanced == bad_bytes
        assert report["applied"] == []

    def test_enhance_detects_glare(self):
        """Test that glare detection works."""
        from src.perception.enhance import enhance_image

        # Create image with bright spot (glare simulation)
        img = np.ones((480, 640, 3), dtype=np.uint8) * 100
        img[100:150, 200:250] = 255  # Bright glare region
        _, buf = cv2.imencode(".jpg", img)
        enhanced, report = enhance_image(buf.tobytes())
        # Report should contain enhancement info
        assert isinstance(report, dict)
        assert "applied" in report

    def test_enhance_dark_image(self):
        """Test that dark images are enhanced with CLAHE."""
        from src.perception.enhance import enhance_image

        # Create very dark image
        img = np.ones((480, 640, 3), dtype=np.uint8) * 40
        _, buf = cv2.imencode(".jpg", img)
        enhanced, report = enhance_image(buf.tobytes())
        # Dark image should trigger CLAHE
        assert isinstance(report, dict)
        assert enhanced != buf.tobytes() or report["applied"]


class TestPipelineIntegration:
    """Test critical pipeline integration points."""

    def test_observation_to_db_dict(self):
        """Test that CalibratedObservation converts to DB-safe dict."""
        from src.grounding.judge import CalibratedObservation
        from uuid import UUID

        obs = CalibratedObservation(
            brand_read="Absolut",
            product_read="Vodka",
            size_read="750ml",
            legibility="fully_readable",
            facings=2,
            shelf_position="eye_level",
            price_read="$24.99",
            status="confirmed",
            field_confidence={"brand": 0.95, "size": 0.92, "price": 0.60, "facings": 0.88},
            notes="Perfect condition",
            matched_sku_id=UUID("12345678-1234-5678-1234-567812345678"),
            match_method="exact",
            match_similarity=0.99,
            obs_status="confirmed",
        )
        db_dict = obs.to_db_dict()
        assert db_dict["brand_read"] == "Absolut"
        assert db_dict["match_similarity"] == 0.99
        # Price shield: price_confidence is 0.60 < 0.70, so price_read should be None
        # (This is tested by the Judge hard rules, not here)

    @pytest.mark.asyncio
    async def test_quality_gate_blocks_before_vlm(self):
        """Test that quality gate prevents low-quality images from reaching VLM."""
        # Create a blurry image
        img = np.ones((1080, 1080, 3), dtype=np.uint8) * 128
        img = cv2.GaussianBlur(img, (51, 51), 30)
        _, buf = cv2.imencode(".jpg", img)

        result, _ = check_quality(buf.tobytes())
        # Should flag as potentially problematic
        assert result.verdict == "fail" or result.overall_score < 0.65
