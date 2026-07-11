"""
Phase 8 end-to-end pipeline tests.

Uses the real local Postgres (docker-compose db).
Mocks: VLM (no API key needed), Storage (no Supabase needed).
CLIP guardrail loads real weights — module-scoped to load once.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import asyncpg
import pytest

from src.agent.graph import ShelfAuditAgent
from src.grounding.judge import Judge
from src.grounding.matcher import SKUMatcher
from src.perception.guardrail import Guardrail
from src.perception.vlm import VLMOrchestrator, VLMExtractionResult, VLMChainExhausted

SCENARIOS = Path(__file__).parent.parent.parent / "tests" / "scenarios"
DB_URL = os.environ.get("DATABASE_URL", "postgresql://kosha:kosha@localhost:5432/kosha")
DB_URL_PG = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


def _load(name: str) -> bytes:
    p = SCENARIOS / name
    if not p.exists():
        pytest.skip(f"Scenario image not found: {name}. Run the test image generation script.")
    return p.read_bytes()


# ─── Module-scoped heavy fixtures ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def guardrail_instance():
    return Guardrail()


@pytest.fixture(scope="module")
def matcher_instance():
    from sentence_transformers import SentenceTransformer
    m = SKUMatcher()
    m.set_embedder(SentenceTransformer("BAAI/bge-small-en-v1.5"))
    return m


@pytest.fixture(scope="module")
def canned_vlm_result() -> VLMExtractionResult:
    """A good shelf VLM result used by most tests (no API call needed)."""
    return VLMExtractionResult(
        observations=[
            __import__("src.perception.vlm", fromlist=["Observation"]).Observation(
                brand_read="Tito's Handmade",
                product_read="Vodka",
                size_read="750ml",
                legibility="fully_readable",
                facings=3,
                shelf_position="eye_level",
                price_read="19.99",
                status="confirmed",
                field_confidence={"brand": 0.95, "size": 0.90, "facings": 0.80, "price": 0.65},
            )
        ],
        fixture_type="gondola",
        image_quality_degraded=False,
        model_used="mock",
        latency_ms=100,
        fallback_chain=["mock"],
    )


# ─── Per-test DB and audit-row fixtures ───────────────────────────────────────

@pytest.fixture
async def db():
    pool = await asyncpg.create_pool(DB_URL_PG, min_size=2, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture
async def account_id(db) -> UUID:
    """Returns the first account in the seed data."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM accounts WHERE org_id = $1 LIMIT 1", TEST_ORG_ID
        )
    if not row:
        pytest.skip("No seeded accounts — run: make seed")
    return row["id"]


@pytest.fixture
async def audit_row(db, account_id) -> UUID:
    """Inserts a processing audit row and yields its id; cleans up after test."""
    aid = uuid4()
    user_id = uuid4()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO shelf_audits
              (id, account_id, org_id, captured_by, captured_at, status, version)
            VALUES ($1, $2, $3, $4, NOW(), 'processing', 1)
            """,
            aid, account_id, TEST_ORG_ID, user_id,
        )
    yield aid, user_id
    async with db.acquire() as conn:
        await conn.execute("DELETE FROM shelf_audits WHERE id = $1", aid)


def _mock_storage():
    storage = MagicMock()
    storage.upload_original = AsyncMock(return_value="test/path/original.jpg")
    storage.upload_preview = AsyncMock(return_value="test/path/preview.jpg")
    return storage


def _make_agent(db, guardrail, matcher, vlm_mock=None, account_id=None) -> ShelfAuditAgent:
    vlm = vlm_mock or VLMOrchestrator()
    judge = Judge()
    return ShelfAuditAgent(
        db_pool=db,
        storage=_mock_storage(),
        guardrail=guardrail,
        matcher=matcher,
        vlm=vlm,
        judge=judge,
    )


def _initial_state(audit_id: UUID, account_id: UUID, user_id: UUID, image_bytes: bytes) -> dict:
    return {
        "audit_id": audit_id,
        "account_id": account_id,
        "org_id": TEST_ORG_ID,
        "captured_by": user_id,
        "image_bytes": image_bytes,
        "storage_path": "test/path/original.jpg",
        "processed_bytes": None,
        "quality": None,
        "guardrail": None,
        "vlm_result": None,
        "match_results": None,
        "judge_result": None,
        "final_observations": None,
        "terminal_status": None,
        "error": None,
        "events": [{"event_type": "created", "payload": {"lat": None, "lng": None}}],
    }


# ─── Test 1: Good shelf → status=final, observations populated ────────────────

@pytest.mark.asyncio
async def test_good_shelf_pipeline(
    db, audit_row, account_id,
    guardrail_instance, matcher_instance, canned_vlm_result
):
    audit_id, user_id = audit_row
    image_bytes = _load("good_shelf.jpg")

    vlm_mock = MagicMock(spec=VLMOrchestrator)
    vlm_mock.extract_shelf = AsyncMock(return_value=canned_vlm_result)

    agent = _make_agent(db, guardrail_instance, matcher_instance, vlm_mock=vlm_mock)

    # Also patch judge LLM so no NIM key needed
    with patch("src.grounding.judge._call_nim", side_effect=RuntimeError("no key in test")):
        await agent.ainvoke(_initial_state(audit_id, account_id, user_id, image_bytes))

    async with db.acquire() as conn:
        audit = await conn.fetchrow("SELECT * FROM shelf_audits WHERE id = $1", audit_id)
        obs = await conn.fetch("SELECT * FROM audit_observations WHERE audit_id = $1", audit_id)
        events = await conn.fetch("SELECT event_type FROM audit_events WHERE audit_id = $1", audit_id)

    assert audit["status"] == "final", f"Expected 'final', got '{audit['status']}'"
    assert len(obs) >= 1, "Expected at least one observation"
    event_types = [r["event_type"] for r in events]
    assert "quality_check_pass" in event_types
    assert "guardrail_pass" in event_types
    assert "rag_matched" in event_types


# ─── Test 2: Selfie → guardrail_rejected, row in guardrail_rejections ─────────

@pytest.mark.asyncio
async def test_selfie_rejected(
    db, audit_row, account_id,
    guardrail_instance, matcher_instance
):
    audit_id, user_id = audit_row
    image_bytes = _load("selfie.jpg")

    agent = _make_agent(db, guardrail_instance, matcher_instance)

    await agent.ainvoke(_initial_state(audit_id, account_id, user_id, image_bytes))

    async with db.acquire() as conn:
        audit = await conn.fetchrow("SELECT * FROM shelf_audits WHERE id = $1", audit_id)
        rejection = await conn.fetchrow(
            "SELECT * FROM guardrail_rejections WHERE storage_path = 'test/path/original.jpg'"
        )

    assert audit["status"] == "guardrail_rejected", (
        f"Expected 'guardrail_rejected', got '{audit['status']}'"
    )
    assert rejection is not None, "Expected a row in guardrail_rejections"


# ─── Test 3: Blurry shelf → retake_required, VLM never called ─────────────────

@pytest.mark.asyncio
async def test_blurry_retake_required_no_vlm_call(
    db, audit_row, account_id,
    guardrail_instance, matcher_instance
):
    audit_id, user_id = audit_row
    image_bytes = _load("blurry_shelf.jpg")

    vlm_mock = MagicMock(spec=VLMOrchestrator)
    vlm_mock.extract_shelf = AsyncMock()

    agent = _make_agent(db, guardrail_instance, matcher_instance, vlm_mock=vlm_mock)

    await agent.ainvoke(_initial_state(audit_id, account_id, user_id, image_bytes))

    async with db.acquire() as conn:
        audit = await conn.fetchrow("SELECT * FROM shelf_audits WHERE id = $1", audit_id)

    assert audit["status"] == "retake_required", (
        f"Expected 'retake_required', got '{audit['status']}'"
    )
    vlm_mock.extract_shelf.assert_not_called()


# ─── Test 4: Concurrent uploads — 10 pipelines run cleanly ────────────────────

@pytest.mark.asyncio
async def test_concurrent_pipelines(
    db, account_id,
    guardrail_instance, matcher_instance, canned_vlm_result
):
    """10 concurrent blurry uploads (fast quality-gate path) — no deadlocks."""
    image_bytes = _load("blurry_shelf.jpg")
    n = 10

    # Create 10 audit rows
    user_id = uuid4()
    audit_ids = [uuid4() for _ in range(n)]
    async with db.acquire() as conn:
        for aid in audit_ids:
            await conn.execute(
                """
                INSERT INTO shelf_audits
                  (id, account_id, org_id, captured_by, captured_at, status, version)
                VALUES ($1, $2, $3, $4, NOW(), 'processing', 1)
                """,
                aid, account_id, TEST_ORG_ID, user_id,
            )

    vlm_mock = MagicMock(spec=VLMOrchestrator)
    vlm_mock.extract_shelf = AsyncMock(return_value=canned_vlm_result)
    agent = _make_agent(db, guardrail_instance, matcher_instance, vlm_mock=vlm_mock)

    with patch("src.grounding.judge._call_nim", side_effect=RuntimeError("no key")):
        tasks = [
            agent.ainvoke(_initial_state(aid, account_id, user_id, image_bytes))
            for aid in audit_ids
        ]
        await asyncio.gather(*tasks)

    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, status FROM shelf_audits WHERE id = ANY($1::uuid[])",
            audit_ids,
        )

    statuses = {str(r["id"]): r["status"] for r in rows}
    assert len(statuses) == n
    for aid in audit_ids:
        assert statuses[str(aid)] in ("retake_required", "final", "guardrail_rejected"), (
            f"Audit {aid} stuck in: {statuses[str(aid)]}"
        )

    # Cleanup
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM shelf_audits WHERE id = ANY($1::uuid[])", audit_ids
        )
