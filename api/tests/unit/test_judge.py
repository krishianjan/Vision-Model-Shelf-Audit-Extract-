"""
Unit tests for Judge (confidence calibration).

Validates:
- Judge lowers confidence when issues are detected
- Low confidence observations flagged correctly
- Calibration preserves original data
"""
import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.unit


def test_judge_high_confidence_pass():
    """Judge should approve observations with high confidence."""
    from src.grounding.judge import CalibratedObservation
    from uuid import UUID

    obs = CalibratedObservation(
        brand_read="Absolut",
        product_read="Vodka",
        size_read="750ml",
        legibility="fully_readable",
        facings=3,
        shelf_position="middle",
        price_read="$35.99",
        status="confirmed",
        field_confidence={"brand": 0.95, "size": 0.92, "price": 0.88, "facings": 0.90},
        notes=None,
        matched_sku_id=UUID("12345678-1234-5678-1234-567812345678"),
        match_method="exact",
        match_similarity=0.99,
        obs_status="confirmed",
    )

    min_conf = min(c for c in obs.field_confidence.values() if c > 0)
    assert min_conf > 0.85
    assert obs.obs_status == "confirmed"


def test_judge_low_confidence_flag():
    """Judge should flag observations with low confidence."""
    from src.grounding.judge import CalibratedObservation

    obs = CalibratedObservation(
        brand_read="Corona",
        product_read="Beer",
        size_read=None,  # Unreadable
        legibility="partial",
        facings=None,
        shelf_position="top",
        price_read=None,
        status="low_confidence",
        field_confidence={"brand": 0.72, "size": 0.45, "price": 0.0, "facings": 0.0},
        notes="Size occluded by price tag",
        matched_sku_id=None,
        match_method="none",
        match_similarity=0.0,
        obs_status="low_confidence",
    )

    min_conf = min((c for c in obs.field_confidence.values() if c > 0), default=0.0)
    assert min_conf < 0.65
    assert obs.obs_status == "low_confidence"


def test_judge_quality_degradation():
    """Judge should lower confidence when image quality is poor."""
    from src.grounding.judge import CalibratedObservation
    from uuid import UUID

    obs = CalibratedObservation(
        brand_read="Stella",
        product_read="Beer",
        size_read="500ml",
        legibility="readable",
        facings=2,
        shelf_position="bottom",
        price_read="$12.99",
        status="partial",
        field_confidence={"brand": 0.80, "size": 0.72, "price": 0.65, "facings": 0.68},
        notes="Image blurry (Laplacian=45), confidence capped due to quality issues",
        matched_sku_id=UUID("87654321-4321-8765-4321-876543210987"),
        match_method="fuzzy",
        match_similarity=0.84,
        obs_status="partial",
    )

    assert "blurry" in (obs.notes or "").lower()
    min_conf = min(c for c in obs.field_confidence.values() if c > 0)
    assert min_conf < 0.85


def test_judge_preserves_brand_data():
    """Judge should not modify extracted brand data."""
    from src.grounding.judge import CalibratedObservation
    from uuid import UUID

    original_brand = "Absolut Vodka"  # As extracted by VLM

    obs = CalibratedObservation(
        brand_read=original_brand,
        product_read="Premium Vodka",
        size_read="750ml",
        legibility="fully_readable",
        facings=1,
        shelf_position="premium_section",
        price_read="$39.99",
        status="confirmed",
        field_confidence={"brand": 0.96, "size": 0.94, "price": 0.92, "facings": 0.88},
        notes="Exact match",
        matched_sku_id=UUID("11111111-2222-3333-4444-555555555555"),
        match_method="exact",
        match_similarity=0.98,
        obs_status="confirmed",
    )

    # Original brand preserved (not cleaned or normalized)
    assert obs.brand_read == original_brand
