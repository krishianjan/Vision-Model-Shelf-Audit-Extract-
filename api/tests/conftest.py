"""
Shared pytest configuration for api/tests/.

Provides:
- sys.path setup for `from src.xxx import yyy`
- Mock API responses (CLIP, Qwen, RAG)
- Test image fixtures
- Async test support
- Database mocks
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Insert the api/ directory so that `src` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Mock API Responses ────────────────────────────────────────────────────

@pytest.fixture
def mock_clip_vodka_pass():
    """CLIP passes a vodka bottle (avg_pos=0.72, confidence high)."""
    return {
        "verdict": "pass",
        "category": "alcohol_shelf",
        "confidence": 0.72,
        "top_matches": [("clip_positive", 0.72)],
        "reason": "Alcohol shelf likely – proceeding to Qwen",
        "rejection_reason": None,
    }


@pytest.fixture
def mock_clip_water_reject():
    """CLIP rejects a water bottle (avg_pos=0.10, clearly non-alcohol)."""
    return {
        "verdict": "reject",
        "category": "non_alcohol",
        "confidence": 0.88,
        "top_matches": [("clip_negative", 0.88)],
        "reason": "Non-alcoholic content clearly detected",
        "rejection_reason": "non_alcohol",
    }


@pytest.fixture
def mock_vlm_vodka_extraction():
    """Qwen successfully extracts a vodka bottle (quality=0.85, confidence=0.91)."""
    return {
        "alcohol_type": "vodka",
        "image_quality_score": 0.85,
        "confidence_overall": 0.91,
        "extraction_confidence": 0.89,
        "fixture_type": "product_shot",
        "observations": [
            {
                "brand_read": "Absolut",
                "product_read": "Premium Vodka",
                "size_read": "750ml",
                "legibility": "fully_readable",
                "facings": 1,
                "shelf_position": "unknown",
                "price_read": None,
                "status": "partial",
                "field_confidence": {
                    "brand": 0.95,
                    "size": 0.92,
                    "facings": 1.0,
                    "price": 0.0,
                },
                "notes": None,
            }
        ],
        "out_of_stock_positions": [],
        "competitor_activity": [],
        "model_used": "qwen-2-vl-7b-instruct",
        "latency_ms": 3200,
    }


@pytest.fixture
def mock_vlm_low_quality():
    """Qwen detects low image quality (0.45 < 0.60 threshold) – trigger retake."""
    return {
        "alcohol_type": "beer",
        "image_quality_score": 0.45,
        "confidence_overall": 0.50,
        "extraction_confidence": 0.48,
        "fixture_type": "gondola",
        "observations": [],
        "degradation_reason": "Image too dark and blurry. Retake with better lighting and flash.",
        "model_used": "qwen-2-vl-7b-instruct",
        "latency_ms": 2800,
    }


# ─── Database/RAG Mocks ────────────────────────────────────────────────────

@pytest.fixture
def mock_product_catalog():
    """Mock SKU product database."""
    return {
        "absolut-750ml": {
            "id": "sku-001",
            "brand": "Absolut",
            "product": "Premium Vodka",
            "size_ml": 750,
            "category": "vodka",
        },
        "stella-500ml": {
            "id": "sku-002",
            "brand": "Stella Artois",
            "product": "Pilsner",
            "size_ml": 500,
            "category": "beer",
        },
    }


# ─── Async Test Support ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Provide event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ─── pytest Configuration ──────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: fast tests using mocks only"
    )
    config.addinivalue_line(
        "markers", "integration: slow tests using real images or APIs"
    )
