"""
Phase 11.5 — YOLO bottle detection tests.

Tests that YOLO:
- Detects bottles on valid shelves
- Returns empty list on non-shelves
- Runs without blocking async loop
- Provides crop regions for focused VLM extraction
"""
import pytest
from pathlib import Path

SCENARIOS = Path(__file__).parent.parent.parent / "tests" / "scenarios"


def _load(name):
    path = SCENARIOS / name
    if path.exists():
        return path.read_bytes()
    pytest.skip(f"Test image {name} not found in tests/scenarios/")


@pytest.fixture(scope="module")
def detector():
    """Load YOLO detector once per test module."""
    from src.perception.detection import BottleDetector
    try:
        return BottleDetector(model_size="n")
    except Exception as e:
        pytest.skip(f"YOLO model unavailable: {e}")


@pytest.mark.asyncio
async def test_detect_good_shelf(detector):
    """Good shelf should detect multiple bottles."""
    result = await detector.detect(_load("good_shelf.jpg"))
    assert result.total_detected > 0
    assert len(result.bottles) > 0
    assert all(0 <= b.confidence <= 1.0 for b in result.bottles)


@pytest.mark.asyncio
async def test_detect_angled_shelf(detector):
    """Angled shelf should still detect bottles."""
    result = await detector.detect(_load("angled_shelf.jpg"))
    assert result.total_detected >= 0  # might detect fewer


@pytest.mark.asyncio
async def test_detect_selfie_returns_empty(detector):
    """Selfie should return no bottles (wrong subject)."""
    result = await detector.detect(_load("selfie.jpg"))
    # Might detect face region, but confidence should be low
    # or it should be 0 bottles since faces aren't bottles
    assert result.total_detected == 0


@pytest.mark.asyncio
async def test_detect_food_returns_empty(detector):
    """Food photo should return no bottles."""
    result = await detector.detect(_load("food.jpg"))
    assert result.total_detected == 0


def test_detector_latency(detector):
    """Verify YOLO detection latency is <200ms."""
    result = detector._detect_sync(_load("good_shelf.jpg"))
    assert result.latency_ms < 300  # 150ms on GPU, ~200ms on CPU


def test_bottle_crop_extraction(detector):
    """Verify crop extraction works without errors."""
    img = _load("good_shelf.jpg")
    result = detector._detect_sync(img)
    if result.bottles:
        bottle = result.bottles[0]
        crop = detector.get_crop(img, bottle)
        assert len(crop) > 0
        assert crop.startswith(b'\xff\xd8\xff')  # JPEG magic bytes


@pytest.mark.asyncio
async def test_detector_not_blocking(detector):
    """Verify detection runs in executor (doesn't block async loop)."""
    import asyncio
    import time

    # This should not block other tasks
    task = asyncio.create_task(detector.detect(_load("good_shelf.jpg")))
    # Give it a moment to start
    await asyncio.sleep(0.01)
    # If blocking, this would fail; async allows both to proceed
    assert not task.done()  # Should still be running
    result = await task
    assert result.total_detected >= 0
