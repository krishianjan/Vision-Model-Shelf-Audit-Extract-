"""
Concurrent upload test — requires a running server at localhost:8000
and valid TOKEN_A + ACCT_1 env vars.
Run manually: TOKEN_A=<jwt> ACCT_1=<uuid> pytest tests/test_multi_user.py -v
"""
import asyncio
import os
import pytest
import httpx

TOKEN_A = os.environ.get("TOKEN_A", "")
ACCT_1 = os.environ.get("ACCT_1", "")
BASE = "http://localhost:8000"


@pytest.mark.skipif(not TOKEN_A or not ACCT_1, reason="TOKEN_A and ACCT_1 env vars required")
@pytest.mark.asyncio
async def test_concurrent_uploads():
    async def upload():
        async with httpx.AsyncClient(timeout=30) as client:
            img_path = os.path.join(os.path.dirname(__file__), "../../tests/scenarios/good_shelf.jpg")
            if not os.path.exists(img_path):
                pytest.skip("No test image at tests/scenarios/good_shelf.jpg")
            with open(img_path, "rb") as f:
                return await client.post(
                    f"{BASE}/audits",
                    headers={"Authorization": f"Bearer {TOKEN_A}"},
                    files={"image": ("shelf.jpg", f, "image/jpeg")},
                    data={"account_id": ACCT_1, "captured_at": "2026-07-03T14:00:00Z"},
                )

    results = await asyncio.gather(*[upload() for _ in range(10)])
    assert all(r.status_code == 202 for r in results), [r.text for r in results]
    audit_ids = {r.json()["audit_id"] for r in results}
    assert len(audit_ids) == 10, "Duplicate audit_ids — concurrency bug"
