"""
Tests for VLM observation parsing + confidence thresholds.
Runs without ML models — unit tests on parsing logic.
"""
import json
import sys
sys.path.insert(0, ".")

from src.perception.vlm import (
    Observation, _validate_field, _parse_observations, _clean_json
)


def test_validate_field_threshold():
    """Grounding rules: confidence < 0.70 → NULL."""
    # Above threshold — keep
    val, note = _validate_field("brand", "Absolut", 0.85)
    assert val == "Absolut", f"Expected 'Absolut', got {val}"
    assert note is None, f"Expected None note, got {note}"

    # Below threshold — NULL
    val, note = _validate_field("brand", "Smirnoff", 0.65)
    assert val is None, f"Expected None, got {val}"
    assert note and "low_confidence" in note, f"Expected low_confidence note, got {note}"

    # Exactly at 0.70 — KEPT (confidence < 0.70 is the check, 0.70 is not < 0.70)
    val, note = _validate_field("brand", "Tito's", 0.70)
    assert val is not None, f"Expected Tito's at 0.70, got None"

    # Null input — null output
    val, note = _validate_field("brand", None, 0.90)
    assert val is None

    print("  PASS: _validate_field thresholds")


def test_price_parse():
    """Price field must be numeric."""
    val, note = _validate_field("price", "19.99", 0.95)
    assert val == "19.99", f"Expected '19.99', got {val}"

    val, note = _validate_field("price", "not_a_price", 0.95)
    assert val is None
    assert "not_numeric" in note

    val, note = _validate_field("price", "$29.99", 0.80)
    assert val is None  # $ prefix causes float() to fail
    assert "parse_failed" in note

    print("  PASS: price parsing")


def test_facings_range():
    """Facings must be 1-99 integer."""
    val, note = _validate_field("facings", 5, 0.95)
    assert val == 5

    val, note = _validate_field("facings", 0, 0.95)
    assert val is None
    assert "out_of_range" in note

    val, note = _validate_field("facings", 150, 0.95)
    assert val is None
    assert "out_of_range" in note

    print("  PASS: facings range check")


def test_parse_observations_handles_new_fields():
    """Visual cue fields survive independent of text confidence."""
    pass2 = {
        "observations": [
            {
                "brand_read": "Absolut",
                "field_confidence": {"brand": 0.90, "size": 0.85, "facings": 0.80, "price": 0.75},
                "legibility": "fully_readable",
                "bottle_shape": "tall_neck",
                "glass_tint": "clear",
                "cap_type": "screw",
                "label_color": "black",
                "visual_brand_guess": None,
                "visual_brand_confidence": None,
                "stock_level": "full",
                "alcohol_subcategory": "unflavored_vodka",
            }
        ]
    }
    obs = _parse_observations(pass2)
    assert len(obs) == 1
    o = obs[0]
    assert o.brand_read == "Absolut"
    assert o.bottle_shape == "tall_neck"
    assert o.glass_tint == "clear"
    assert o.cap_type == "screw"
    assert o.label_color == "black"
    assert o.stock_level == "full"
    assert o.alcohol_subcategory == "unflavored_vodka"
    assert o.visual_brand_confidence == 0.0  # None → default 0.0

    print("  PASS: new visual cue fields surviving parse")


def test_parse_unreadable_label():
    """Label unreadable → brand NULL but visual cues still filled."""
    pass2 = {
        "observations": [
            {
                "brand_read": None,
                "field_confidence": {"brand": 0.55, "size": 0.60},
                "legibility": "unreadable",
                "bottle_shape": "short_squat",
                "glass_tint": "clear",
                "cap_type": "screw",
                "visual_brand_guess": "Patron",
                "visual_brand_confidence": 0.75,
                "stock_level": "low",
            }
        ]
    }
    obs = _parse_observations(pass2)
    assert len(obs) == 1
    o = obs[0]
    assert o.brand_read is None  # Low confidence → nulled
    assert o.visual_brand_guess == "Patron"  # Visual survives
    assert o.visual_brand_confidence == 0.75
    assert o.bottle_shape == "short_squat"
    assert o.stock_level == "low"

    print("  PASS: unreadable label with visual fallback")


def test_clean_json_fences():
    """Backtick fences stripped."""
    raw = '```json\n{"foo": "bar"}\n```'
    result = _clean_json(raw)
    assert result == {"foo": "bar"}

    raw2 = '{"no": "fences"}'
    assert _clean_json(raw2) == {"no": "fences"}

    print("  PASS: JSON fence cleaning")


def run():
    print("=== VLM Parse Tests ===")
    test_validate_field_threshold()
    test_price_parse()
    test_facings_range()
    test_parse_observations_handles_new_fields()
    test_parse_unreadable_label()
    test_clean_json_fences()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run()