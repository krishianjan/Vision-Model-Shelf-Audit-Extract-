from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal smoke test — no DB required
def test_health_no_db():
    from src.main import app
    # Check /health route exists (FastAPI 0.111+ stores routes differently)
    paths = []
    for r in app.routes:
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "routes"):
            paths.extend(sr.path for sr in r.routes if hasattr(sr, "path"))
    assert "/health" in paths
