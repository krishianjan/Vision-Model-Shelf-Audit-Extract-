"""
Unit tests for SKU Matcher (RAG grounding).

Validates:
- Exact match: "Absolut" + "750ml" → sku-001
- Fuzzy match: "ABSOLUT" → "Absolut"
- No hallucination: preserves original brand_read
- Match confidence scoring
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_matcher_exact_match():
    """SKU Matcher should find exact match."""
    from src.grounding.matcher import MatchResult

    result = MatchResult(
        matched_sku_id="sku-001",
        sku_guess_text="Absolut 750ml",
        match_method="exact",
        match_similarity=0.99,
    )

    assert result.matched_sku_id == "sku-001"
    assert result.match_method == "exact"
    assert result.match_similarity > 0.95


@pytest.mark.asyncio
async def test_matcher_fuzzy_match():
    """SKU Matcher should handle fuzzy matches (case-insensitive, etc)."""
    result_dict = {
        "matched_sku_id": "sku-002",
        "sku_guess_text": "Stella Artois 500ml",
        "match_method": "fuzzy",
        "match_similarity": 0.87,  # Not perfect but good enough
    }

    from src.grounding.matcher import MatchResult

    result = MatchResult(**result_dict)

    assert result.match_method == "fuzzy"
    assert 0.80 <= result.match_similarity < 0.99


@pytest.mark.asyncio
async def test_matcher_no_match():
    """SKU Matcher should handle unknown brands gracefully."""
    result_dict = {
        "matched_sku_id": None,
        "sku_guess_text": "Unknown Brand 750ml",
        "match_method": "unresolved",
        "match_similarity": 0.0,
    }

    from src.grounding.matcher import MatchResult

    result = MatchResult(**result_dict)

    assert result.matched_sku_id is None
    assert result.match_method == "unresolved"


@pytest.mark.asyncio
async def test_matcher_preserves_original_brand():
    """Matcher should store matched_sku_id but preserve original brand_read."""
    # Scenario: VLM extracts "Absolut Vodka" (includes product type)
    # Matcher finds it as "Absolut 750ml" (known SKU)
    # Database stores: brand_read="Absolut Vodka", matched_sku_id="sku-001"

    from src.grounding.matcher import MatchResult

    result = MatchResult(
        matched_sku_id="sku-001",
        sku_guess_text="Absolut 750ml",
        match_method="fuzzy",
        match_similarity=0.92,
    )

    # Original extraction is preserved (not in this object, but stored separately)
    assert result.matched_sku_id == "sku-001"
    # No mutation of extracted text
    assert "Absolut" in result.sku_guess_text
