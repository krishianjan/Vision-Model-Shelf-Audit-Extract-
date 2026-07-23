# Test Scenarios

Place test images here named by scenario. The test runner loads images from this directory
and runs them through the pipeline end-to-end.

## Required Images

1. **good_shelf_multi.jpg** — Clear liquor shelf with 5+ bottles, readable labels
2. **good_single_bottle.jpg** — Single bottle product shot (e-commerce style)
3. **bad_selfie.jpg** — Selfie/portrait (should be rejected by guardrail)
4. **water_bottles.jpg** — Non-alcoholic beverages (should be rejected)
5. **blurry_shelf.jpg** — Shelf photo with motion blur or bad lighting
6. **unlabeled_bottle.jpg** — Bottle with torn/missing label (visual cues only)
7. **cooler_door.jpg** — Cooler/fridge with glass door
8. **endcap_display.jpg** — Promotional endcap display

## How to Run Tests

```bash
cd api
source .venv/bin/activate

# Individual tests
PYTHONPATH=. python tests/test_generated_fix.py

# Full pipeline test (requires API server running)
# Coming soon
```

## Image Requirements

- JPEG format preferred (what mobile app captures)
- Resolution: 640-1920px recommended
- Keep file sizes under 2MB
- No confidential/store-identifiable information in filenames