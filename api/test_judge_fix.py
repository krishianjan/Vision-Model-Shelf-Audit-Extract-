import json
from src.grounding.judge import _apply_hard_rules
from src.perception.vlm import Observation
from src.grounding.matcher import MatchResult
from src.perception.base import QualityResult

# Simulate the old broken scenario
obs = Observation(
    brand_read="MOUNTAIN Dew",
    product_read="",
    size_read="170",
    price_read="1.70",
    facings=1,
    shelf_position="top",
    field_confidence={"brand": 0.95, "size": 0.90, "price": 0.60, "facings": 0.80},
    status="confirmed"
)

# RAG found no match
match = MatchResult(
    matched_sku_id=None,
    match_method="unresolved",
    match_similarity=0.0,
    top_candidates=[],
    sku_guess_text="MOUNTAIN Dew"
)

quality = QualityResult(
    overall_score=0.937,
    blur_score=1.0,
    exposure_score=0.791,
    resolution_ok=True,
    aspect_ratio_ok=True,
    verdict="pass",
    issues=[],
    retake_reason=None,
    content_hash="test",
    width=1080,
    height=1680
)

conf, obs_status, rules = _apply_hard_rules(obs, match, quality)

print("=== NEW BEHAVIOR ===")
print(f"Brand Confidence: {conf.get('brand')} (should be 0.95, NOT 0.0)")
print(f"Price Confidence: {conf.get('price')} (should be 0.0 due to price shield)")
print(f"Obs Status: {obs_status} (should be 'unmatched')")
print(f"\nRules Applied:")
for rule in rules:
    print(f"  - {rule}")

# Verify
assert conf.get('brand') == 0.95, "❌ Brand confidence was downgraded!"
assert conf.get('price') == 0.0, "❌ Price was not shielded!"
assert obs_status == "unmatched", "❌ Status should be unmatched"
assert any("unresolved_competitor" in r for r in rules), "❌ Missing unresolved_competitor rule"
assert any("price_shield" in r for r in rules), "❌ Missing price_shield rule"

print("\n✅ All tests passed! Logic is correct.")
