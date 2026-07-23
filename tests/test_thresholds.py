"""
Tests for RAG matcher + guardrail thresholds.
Runs without DB — validates the logic and edge cases.
"""
import sys
sys.path.insert(0, ".")

from src.grounding.matcher import _normalize, _parse_size_to_ml, _make_query_text
from src.agent.graph import _normalize_fixture_type
from src.perception.vlm import _validate_field


def test_normalize_text():
    """Normalize handles accents, punctuation, case."""
    assert _normalize("Tito's Handmade") == "tito s handmade"
    assert _normalize("José Cuervo") == "jose cuervo"
    assert _normalize("Jack Daniel's") == "jack daniel s"
    assert _normalize("   EXTRA   SPACES   ") == "extra spaces"
    assert _normalize("") == ""
    assert _normalize(None) == ""
    print("  PASS: text normalization")


def test_size_parsing():
    """Parse volume strings to ml."""
    assert _parse_size_to_ml("750ml") == 750
    assert _parse_size_to_ml("1.75L") == 1750
    assert _parse_size_to_ml("200oz") == 5914  # ~5915
    assert _parse_size_to_ml("50cl") == 500
    assert _parse_size_to_ml(None) is None
    assert _parse_size_to_ml("") is None
    assert _parse_size_to_ml("garbage") is None
    print("  PASS: size parsing")


def test_make_query_text():
    """Query text construction for RAG matching."""
    assert _make_query_text("Absolut", "750ml", None) == "Absolut 750ml"
    assert _make_query_text(None, None, None) == ""
    assert _make_query_text("Tito's", None, "Handmade Vodka") == "Tito's Handmade Vodka"
    print("  PASS: query text construction")


def test_fixture_type_normalization():
    """VLM returns arbitrary strings → normalize to DB-valid."""
    # Valid values pass through
    assert _normalize_fixture_type("gondola") == "gondola"
    assert _normalize_fixture_type("cooler") == "cooler"
    assert _normalize_fixture_type("endcap") == "endcap"
    assert _normalize_fixture_type("floor_display") == "floor_display"
    assert _normalize_fixture_type("unknown") == "unknown"

    # Invalid → unknown
    assert _normalize_fixture_type("table") == "unknown"
    assert _normalize_fixture_type("hand_hold") == "unknown"
    assert _normalize_fixture_type("stock_photo") == "unknown"
    assert _normalize_fixture_type(None) == "unknown"
    assert _normalize_fixture_type("") == "unknown"

    # Case-insensitive
    assert _normalize_fixture_type("GONDOLA") == "gondola"
    assert _normalize_fixture_type("Cooler") == "cooler"

    print("  PASS: fixture_type normalization")


def test_confidence_thresholds():
    """Load-bearing confidence thresholds."""
    # 0.70 brand threshold: confidence < 0.70 → NULL
    val, _ = _validate_field("brand", "test", 0.71)
    assert val is not None, "0.71 should pass"
    val, _ = _validate_field("brand", "test", 0.69)
    assert val is None, "0.69 should fail"

    # CLIP threshold (0.05) — tested conceptually
    # Guardrail CLIP rejects at avg_pos < 0.05
    # This is tested in test_guardrail_thresholds.py

    # Judge confidence threshold (0.55)
    # Route always goes to persist_final regardless of confidence
    # Status determined inside persist_final: >=0.55 → "final", else "retake_required"
    print("  PASS: confidence threshold boundaries")


def run():
    print("=== RAG + Guardrail Threshold Tests ===")
    test_normalize_text()
    test_size_parsing()
    test_make_query_text()
    test_fixture_type_normalization()
    test_confidence_thresholds()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run()