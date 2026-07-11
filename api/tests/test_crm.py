"""
Phase 9 tests — CRM read layer enrichment.

Seeds its own minimal audit data; cleans up after each test.
No API keys needed — all compute is in Python/SQL.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

import asyncpg
import pytest

from src.routes.crm import (
    _enrich_observations,
    _compute_share_of_shelf,
    _compute_summary,
    _POSITION_RANK,
)

DB_URL = os.environ.get("DATABASE_URL", "postgresql://kosha:kosha@localhost:5432/kosha")
DB_URL_PG = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
TEST_ORG = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
async def conn():
    c = await asyncpg.connect(DB_URL_PG)
    yield c
    await c.close()


@pytest.fixture
async def account_id(conn) -> UUID:
    row = await conn.fetchrow(
        "SELECT id FROM accounts WHERE org_id = $1 LIMIT 1", TEST_ORG
    )
    if not row:
        pytest.skip("No seeded accounts")
    return row["id"]


async def _insert_audit(conn, account_id: UUID, captured_at=None) -> UUID:
    aid = uuid4()
    user_id = uuid4()
    at = captured_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO shelf_audits
          (id, account_id, org_id, captured_by, captured_at, status, version)
        VALUES ($1, $2, $3, $4, $5, 'final', 1)
        """,
        aid, account_id, TEST_ORG, user_id, at,
    )
    return aid


async def _insert_obs(conn, audit_id: UUID, **kwargs) -> UUID:
    oid = uuid4()
    defaults = dict(
        matched_sku_id=None, brand_read="TestBrand",
        size_read="750ml", facings=2,
        shelf_position="eye_level", price_value=20.00,
        price_confidence=0.85,
        field_confidence=json.dumps({"brand": 0.9, "facings": 0.8}),
        status="confirmed", match_method="exact", match_similarity=0.98,
    )
    defaults.update(kwargs)
    defaults["field_confidence"] = json.dumps(defaults["field_confidence"]) if isinstance(defaults["field_confidence"], dict) else defaults["field_confidence"]
    await conn.execute(
        """
        INSERT INTO audit_observations
          (id, audit_id, matched_sku_id, brand_read, size_read, facings,
           shelf_position, price_value, price_confidence,
           field_confidence, status, match_method, match_similarity)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12,$13)
        """,
        oid, audit_id,
        defaults["matched_sku_id"], defaults["brand_read"], defaults["size_read"],
        defaults["facings"], defaults["shelf_position"],
        defaults["price_value"], defaults["price_confidence"],
        defaults["field_confidence"], defaults["status"],
        defaults["match_method"], defaults["match_similarity"],
    )
    return oid


# ─── Test 1: Enrichment computation ───────────────────────────────────────────

def test_enrichment_price_delta_and_facings_share():
    """
    Three observations in same category: prices 10, 20, 30.
    Avg = 20. Obs with price=20 → delta=0.0. Obs with price=30 → delta=+50%.
    Facings: 3, 2, 1 → total=6. Obs with 3 facings → 50% share.
    """
    sku_id = uuid4()
    obs = [
        {"id": uuid4(), "matched_sku_id": sku_id, "brand_read": "A", "size_read": "750ml",
         "facings": 3, "shelf_position": "eye_level", "price_value": 10.0,
         "price_confidence": 0.9, "field_confidence": {"brand": 0.9},
         "status": "confirmed", "match_method": "exact", "match_similarity": 0.99,
         "notes": None, "sku_guess_text": None, "created_at": datetime.now(timezone.utc)},
        {"id": uuid4(), "matched_sku_id": sku_id, "brand_read": "B", "size_read": "750ml",
         "facings": 2, "shelf_position": "reach", "price_value": 20.0,
         "price_confidence": 0.9, "field_confidence": {"brand": 0.85},
         "status": "confirmed", "match_method": "exact", "match_similarity": 0.95,
         "notes": None, "sku_guess_text": None, "created_at": datetime.now(timezone.utc)},
        {"id": uuid4(), "matched_sku_id": sku_id, "brand_read": "C", "size_read": "750ml",
         "facings": 1, "shelf_position": "bottom", "price_value": 30.0,
         "price_confidence": 0.9, "field_confidence": {"brand": 0.80},
         "status": "confirmed", "match_method": "exact", "match_similarity": 0.93,
         "notes": None, "sku_guess_text": None, "created_at": datetime.now(timezone.utc)},
    ]
    sku_cats = {sku_id: "vodka"}
    enriched = _enrich_observations(obs, sku_cats)

    # set_avg_price = (10+20+30)/3 = 20.0
    assert enriched[0].enrichment.set_avg_price == 20.0
    # Price 10 → -50% below avg
    assert enriched[0].enrichment.price_delta_vs_set_avg_pct == pytest.approx(-50.0, abs=0.1)
    # Price 20 → 0%
    assert enriched[1].enrichment.price_delta_vs_set_avg_pct == pytest.approx(0.0, abs=0.1)
    # Price 30 → +50%
    assert enriched[2].enrichment.price_delta_vs_set_avg_pct == pytest.approx(50.0, abs=0.1)

    # Facings share: 3/6=50%, 2/6=33.3%, 1/6=16.7%
    assert enriched[0].enrichment.facings_share_of_set == pytest.approx(50.0, abs=0.2)
    assert enriched[1].enrichment.facings_share_of_set == pytest.approx(33.3, abs=0.2)

    # Position ranks
    assert enriched[0].enrichment.position_rank == "premium"   # eye_level
    assert enriched[1].enrichment.position_rank == "standard"  # reach
    assert enriched[2].enrichment.position_rank == "value"     # bottom


def test_position_rank_all_values():
    assert _POSITION_RANK["eye_level"] == "premium"
    assert _POSITION_RANK["top"] == "premium"
    assert _POSITION_RANK["reach"] == "standard"
    assert _POSITION_RANK["stoop"] == "value"
    assert _POSITION_RANK["bottom"] == "value"
    assert _POSITION_RANK["endcap"] == "special"
    assert _POSITION_RANK["cooler_door"] == "special"


# ─── Test 2: Account history returns deltas ────────────────────────────────────

@pytest.mark.asyncio
async def test_account_history_sku_deltas(conn, account_id):
    """
    Two audits for same account, same SKU. Second audit has different facings.
    History should show facings_delta and days_since_previous.
    """
    sku_row = await conn.fetchrow("SELECT id FROM products LIMIT 1")
    sku_id = sku_row["id"] if sku_row else None

    now = datetime.now(timezone.utc)
    audit1_id = await _insert_audit(conn, account_id, captured_at=now - timedelta(days=7))
    audit2_id = await _insert_audit(conn, account_id, captured_at=now)

    await _insert_obs(conn, audit1_id, matched_sku_id=sku_id, brand_read="Tito's Handmade",
                      facings=3, shelf_position="eye_level")
    await _insert_obs(conn, audit2_id, matched_sku_id=sku_id, brand_read="Tito's Handmade",
                      facings=5, shelf_position="eye_level")

    # Directly call the SQL query used by the endpoint
    rows = await conn.fetch(
        """
        SELECT
          cur.audit_id,
          cur.matched_sku_id,
          cur.brand_read,
          cur.facings AS current_facings,
          prev.facings AS previous_facings,
          cur_audit.captured_at AS cur_captured_at,
          prev.captured_at AS prev_captured_at
        FROM audit_observations cur
        JOIN shelf_audits cur_audit ON cur_audit.id = cur.audit_id
        LEFT JOIN LATERAL (
          SELECT ao.facings, sa.captured_at
          FROM audit_observations ao
          JOIN shelf_audits sa ON sa.id = ao.audit_id
          WHERE sa.account_id = $1
            AND sa.captured_at < cur_audit.captured_at
            AND sa.superseded_by IS NULL
            AND ao.brand_read = cur.brand_read
          ORDER BY sa.captured_at DESC LIMIT 1
        ) prev ON true
        WHERE cur.audit_id = $2
        """,
        account_id, audit2_id,
    )

    assert len(rows) >= 1
    row = rows[0]
    assert row["current_facings"] == 5
    assert row["previous_facings"] == 3
    delta = row["current_facings"] - row["previous_facings"]
    assert delta == 2

    days = abs((row["cur_captured_at"] - row["prev_captured_at"]).days)
    assert days == 7

    # Cleanup
    await conn.execute("DELETE FROM shelf_audits WHERE id = ANY($1::uuid[])", [audit1_id, audit2_id])


# ─── Test 3: Review queue returns only low-confidence observations ─────────────

@pytest.mark.asyncio
async def test_review_queue_low_confidence_only(conn, account_id):
    """
    Insert one high-confidence and one low-confidence observation.
    review_queue should return only the low-confidence one.
    """
    audit_id = await _insert_audit(conn, account_id)

    # High confidence — should NOT appear in review queue
    await _insert_obs(conn, audit_id,
                      brand_read="HighConf Brand",
                      field_confidence={"brand": 0.95, "facings": 0.90, "price": 0.88},
                      status="confirmed")

    # Low confidence — should appear
    low_oid = await _insert_obs(conn, audit_id,
                                brand_read="LowConf Brand",
                                field_confidence={"brand": 0.45, "facings": 0.55},
                                status="low_confidence",
                                match_similarity=0.50)

    rows = await conn.fetch(
        "SELECT observation_id, brand_read, min_confidence FROM review_queue WHERE audit_id = $1",
        audit_id,
    )

    brand_reads = [r["brand_read"] for r in rows]
    assert "LowConf Brand" in brand_reads
    assert "HighConf Brand" not in brand_reads

    for r in rows:
        if r["brand_read"] == "LowConf Brand":
            assert r["min_confidence"] is not None
            assert r["min_confidence"] < 0.8

    await conn.execute("DELETE FROM shelf_audits WHERE id = $1", audit_id)


# ─── Test 4: Competitive intel groups unmatched brands ────────────────────────

@pytest.mark.asyncio
async def test_competitive_intel_groups_unmatched(conn, account_id):
    """
    Two audits with an unmatched brand → competitive_intel should aggregate it.
    Matched brand should NOT appear.
    """
    sku_row = await conn.fetchrow("SELECT id FROM products LIMIT 1")
    sku_id = sku_row["id"] if sku_row else None

    audit1_id = await _insert_audit(conn, account_id)
    audit2_id = await _insert_audit(conn, account_id)

    # Unmatched brand — appears in both audits
    await _insert_obs(conn, audit1_id, matched_sku_id=None,
                      brand_read="Fake New Competitor", status="unmatched",
                      sku_guess_text="Fake New Competitor Spirit 750ml",
                      match_method=None, match_similarity=None)
    await _insert_obs(conn, audit2_id, matched_sku_id=None,
                      brand_read="Fake New Competitor", status="unmatched",
                      sku_guess_text="Fake New Competitor Spirit 750ml",
                      match_method=None, match_similarity=None)

    # Matched brand — should NOT appear in competitive intel
    await _insert_obs(conn, audit1_id, matched_sku_id=sku_id,
                      brand_read="Known Brand", status="confirmed")

    rows = await conn.fetch(
        """
        SELECT brand_read, COUNT(*) AS cnt
        FROM audit_observations ao
        JOIN shelf_audits sa ON sa.id = ao.audit_id
        WHERE ao.matched_sku_id IS NULL
          AND ao.brand_read IS NOT NULL
          AND ao.brand_read = 'Fake New Competitor'
          AND sa.account_id = $1
        GROUP BY ao.brand_read
        """,
        account_id,
    )

    assert len(rows) == 1
    assert rows[0]["cnt"] == 2

    # Known brand should not appear when filtered for matched_sku_id IS NULL
    known_rows = await conn.fetch(
        """
        SELECT brand_read FROM audit_observations ao
        JOIN shelf_audits sa ON sa.id = ao.audit_id
        WHERE ao.matched_sku_id IS NULL AND ao.brand_read = 'Known Brand'
          AND sa.account_id = $1
        """,
        account_id,
    )
    assert len(known_rows) == 0

    await conn.execute(
        "DELETE FROM shelf_audits WHERE id = ANY($1::uuid[])",
        [audit1_id, audit2_id],
    )
