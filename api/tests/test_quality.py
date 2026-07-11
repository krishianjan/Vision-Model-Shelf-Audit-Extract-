"""
Phase 3 — Quality gate tests (OpenCV, deterministic).

Run:  pytest api/tests/test_quality.py -v
Prereq: place test images in tests/scenarios/ (see README for sourcing guide).
"""
import pytest
from pathlib import Path

from src.perception.quality import check_quality

SCENARIOS = Path(__file__).parent.parent.parent / "tests" / "scenarios"


def _load(name: str) -> bytes:
    path = SCENARIOS / name
    if not path.exists():
        pytest.skip(f"Scenario image not found: {path}. Source it and place it there.")
    return path.read_bytes()


def test_good_shelf_passes():
    """A clean, well-lit shelf photo must pass with score > 0.6."""
    result, _ = check_quality(_load("good_shelf.jpg"))
    assert result.verdict == "pass"
    assert result.overall_score > 0.6
    assert result.retake_reason is None


def test_blurry_rejects():
    """A heavily blurred shelf must be rejected with a blur-related retake message."""
    result, _ = check_quality(_load("blurry_shelf.jpg"))
    assert result.verdict == "reject"
    assert result.retake_reason is not None
    assert "blur" in result.retake_reason.lower()


def test_dark_may_rescue_or_reject():
    """
    A dark shelf is either:
      - rejected (too dark to rescue), OR
      - warned + CLAHE rescue applied (borderline dark but sharp enough).

    If rescued, the returned bytes must differ from the original (CLAHE was applied).
    """
    raw = _load("dark_shelf.jpg")
    result, processed = check_quality(raw)

    assert result.verdict in ("reject", "warn"), (
        f"Expected reject or warn for dark image, got {result.verdict!r}"
    )
    if result.verdict == "warn":
        assert "clahe_rescue_applied" in result.issues, (
            "warn verdict on dark image should have clahe_rescue_applied in issues"
        )
        assert processed != raw, (
            "processed bytes should differ from raw when CLAHE rescue is applied"
        )


def test_deterministic():
    """Same input must always produce identical hash and score — no randomness."""
    raw = _load("good_shelf.jpg")
    r1, _ = check_quality(raw)
    r2, _ = check_quality(raw)
    assert r1.content_hash == r2.content_hash
    assert r1.overall_score == r2.overall_score
    assert r1.verdict == r2.verdict


# ── Additional scenario coverage ──────────────────────────────────────────────

def test_overexposed_rejects():
    """Blown-out / glare-heavy shot should be rejected."""
    result, _ = check_quality(_load("glare_shelf.jpg"))
    assert result.verdict == "reject"


def test_angled_shelf_may_warn():
    """An angled shelf is low-risk; we allow pass or warn but not reject on angle alone."""
    result, _ = check_quality(_load("angled_shelf.jpg"))
    # We don't reject on angle — only on blur/exposure/resolution
    assert result.verdict in ("pass", "warn")


def test_content_hash_differs_across_images():
    """Two different images must have different content hashes."""
    r1, _ = check_quality(_load("good_shelf.jpg"))
    r2, _ = check_quality(_load("blurry_shelf.jpg"))
    assert r1.content_hash != r2.content_hash
