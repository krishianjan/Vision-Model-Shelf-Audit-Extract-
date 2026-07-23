#!/usr/bin/env python3
"""
Run all unit tests.
Usage: cd api && python ../tests/run_all.py
"""
import subprocess
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(os.path.dirname(BASE), "api")

tests = [
    "test_vlm_parse.py",
    "test_thresholds.py",
    "test_guardrail.py",
]

passed = 0
failed = 0

for t in tests:
    path = os.path.join(BASE, t)
    print(f"\n{'='*50}")
    print(f"  Running {t}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, path],
        cwd=API_DIR,
        capture_output=False,
    )
    if result.returncode == 0:
        passed += 1
    else:
        failed += 1

print(f"\n{'='*50}")
print(f"  RESULTS: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)