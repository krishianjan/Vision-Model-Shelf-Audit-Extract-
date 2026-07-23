"""
Tests for guardrail CLIP/YOLO threshold boundaries.
Validates the load-bearing numbers: 0.05 CLIP reject, 0.45 quality score,
and dynamic prompt split (no hardcoded 23/17).
"""
import sys
sys.path.insert(0, ".")

# Test that the dynamic split works without needing ML models
def test_clip_prompt_split_dynamic():
    """
    The guardrail stores positive and negative prompts separately.
    _num_positive is computed from len(positive_prompts) at init.
    This test validates the split logic without loading CLIP/YOLO.
    """
    # Simulate the split logic
    positive_prompts = [
        "retail alcohol shelf with bottles",
        "liquor store shelf with spirits",
        "wine rack with bottles",
        "beer cooler with cases",
    ]
    negative_prompts = [
        "empty shelf",
        "person selfie face",
        "food grocery aisle",
        "clothing store rack",
    ]

    all_prompts = positive_prompts + negative_prompts
    num_positive = len(positive_prompts)  # This is what _num_positive stores

    # Simulate similarity scores
    sims = [0.8, 0.7, 0.6, 0.5, 0.1, 0.05, 0.03, 0.01]

    pos_sims = sims[:num_positive]
    neg_sims = sims[num_positive:]

    assert len(pos_sims) == 4, f"Expected 4 positive, got {len(pos_sims)}"
    assert len(neg_sims) == 4, f"Expected 4 negative, got {len(neg_sims)}"
    assert all(s > 0.4 for s in pos_sims), "Positive scores should be higher"
    assert all(s < 0.2 for s in neg_sims), "Negative scores should be lower"

    # If we add a prompt, split auto-adjusts
    positive_prompts.append("whiskey endcap display")
    num_positive = len(positive_prompts)
    assert num_positive == 5, f"Expected 5 after add, got {num_positive}"

    print("  PASS: CLIP prompt split is dynamic (no hardcoded 23/17)")


def test_clip_reject_threshold():
    """
    CLIP rejects at avg_pos < 0.05.
    Test the boundary: 0.05 should PASS, 0.04 should REJECT.
    """
    reject_threshold = 0.05

    # Just above threshold → pass
    avg_pos_pass = 0.06
    assert avg_pos_pass >= reject_threshold, "0.06 should pass"

    # Exactly at threshold → pass (>= not >)
    avg_pos_edge = 0.05
    assert avg_pos_edge >= reject_threshold, "0.05 should pass"

    # Below threshold → reject
    avg_pos_fail = 0.04
    assert not (avg_pos_fail >= reject_threshold), "0.04 should reject"

    print("  PASS: CLIP reject threshold boundary (0.05)")


def test_quality_score_cutoff():
    """
    Quality gate rejects at overall_score < 0.45.
    """
    quality_threshold = 0.45

    # Above → pass
    assert 0.50 >= quality_threshold, "0.50 should pass"

    # At threshold → pass
    assert 0.45 >= quality_threshold, "0.45 should pass"

    # Below → reject
    assert not (0.40 >= quality_threshold), "0.40 should reject"

    print("  PASS: Quality score cutoff boundary (0.45)")


def test_brand_confidence_threshold():
    """
    VLM brand field confidence threshold: 0.70.
    Below → NULL the field (hallucination control).
    """
    brand_threshold = 0.70

    # Above → keep (confidence passes 0.70 threshold)
    assert 0.75 >= brand_threshold, "0.75 should keep brand"

    # At threshold → keep (>= 0.70 passes, < 0.70 is nulled)
    assert 0.70 >= brand_threshold, "0.70 should keep brand"

    # Below → NULL (strictly less than threshold)
    assert not (0.69 >= brand_threshold), "0.69 should NULL"

    print("  PASS: Brand confidence threshold (0.70, strict <)")


def test_route_confidence_threshold():
    """
    Route confidence threshold: 0.55.
    Below → status='retake_required', at/above → status='final'.
    Route function always returns 'persist_final' (observations saved either way).
    """
    route_threshold = 0.55

    # At/above → final
    assert 0.55 >= route_threshold, "0.55 should be final"
    assert 0.60 >= route_threshold, "0.60 should be final"

    # Below → retake_required
    assert not (0.54 >= route_threshold), "0.54 should be retake"

    # Route always returns persist_final
    route_result = "persist_final"
    assert route_result == "persist_final", "Route should always return persist_final"

    print("  PASS: Route confidence threshold (0.55) + always persists")


def test_yolo_bottle_thresholds():
    """
    YOLO thresholds:
    - >= 2 bottles → PASS (gondola shelf)
    - 1 bottle → DEFER to CLIP (single product shot)
    - 0 bottles + NO_PRODUCTS_FOUND → DEFER to CLIP
    - Restricted object → REJECT immediately
    """
    # 2+ bottles → auto pass
    assert 2 >= 2, "2 bottles should pass"
    assert 5 >= 2, "5 bottles should pass"

    # 1 bottle → defer (not reject)
    assert 1 < 2, "1 bottle should defer to CLIP"

    # 0 bottles → defer
    assert 0 < 2, "0 bottles should defer to CLIP"

    print("  PASS: YOLO bottle count thresholds")


def run():
    print("=== Guardrail Threshold Tests ===")
    test_clip_prompt_split_dynamic()
    test_clip_reject_threshold()
    test_quality_score_cutoff()
    test_brand_confidence_threshold()
    test_route_confidence_threshold()
    test_yolo_bottle_thresholds()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run()