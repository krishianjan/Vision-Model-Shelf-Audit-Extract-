"""
Phase 9 — CRM read layer with enrichment.

GET /audits/{id}          — enriched audit with per-observation price delta, facings share, position rank
GET /accounts/{id}/history — N audits + per-SKU facings deltas
GET /review-queue          — low-confidence observations from review_queue view
GET /competitive-intel     — unmatched brand_read grouped as competitor signals
"""
from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import AuthUser, get_current_user
from src.models.crm import (
    EnrichedAuditDetail,
    EnrichedObservation,
    ObservationEnrichment,
    AccountHistoryEntry,
    SKUDelta,
    CompetitorSignal,
    ReviewQueueItem,
)

router = APIRouter(tags=["crm"])

_POSITION_RANK = {
    "eye_level": "premium",
    "top": "premium",
    "reach": "standard",
    "stoop": "value",
    "bottom": "value",
    "endcap": "special",
    "cooler_door": "special",
    "unknown": "special",
}


# ─── Enriched GET /audits/{id} ────────────────────────────────────────────────

@router.get("/audits/{audit_id}", response_model=EnrichedAuditDetail)
async def get_enriched_audit(
    audit_id: UUID,
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        audit = await conn.fetchrow(
            """
            SELECT sa.*, ac.name AS account_name
            FROM shelf_audits sa
            LEFT JOIN accounts ac ON ac.id = sa.account_id
            WHERE sa.id = $1 AND (sa.captured_by = $2 OR sa.org_id = $3)
            """,
            audit_id, user.user_id, user.org_id,
        )
        if not audit:
            raise HTTPException(404, "Audit not found")

        obs_rows = await conn.fetch(
            "SELECT * FROM audit_observations WHERE audit_id = $1 ORDER BY created_at",
            audit_id,
        )
        images = await conn.fetch(
            "SELECT id, storage_path, preview_path, width_px, height_px, quality_score FROM audit_images WHERE audit_id = $1",
            audit_id,
        )

        # Fetch categories for matched SKUs in one query
        matched_ids = [o["matched_sku_id"] for o in obs_rows if o["matched_sku_id"]]
        sku_categories: dict[UUID, str] = {}
        if matched_ids:
            cat_rows = await conn.fetch(
                "SELECT id, category FROM products WHERE id = ANY($1::uuid[])",
                matched_ids,
            )
            sku_categories = {r["id"]: r["category"] for r in cat_rows}

    observations = [dict(o) for o in obs_rows]
    # Deserialize JSONB fields that asyncpg returns as strings
    for obs in observations:
        if isinstance(obs.get("field_confidence"), str):
            obs["field_confidence"] = json.loads(obs["field_confidence"])
    enriched_obs = _enrich_observations(observations, sku_categories)
    share_of_shelf = _compute_share_of_shelf(observations)
    summary = _compute_summary(observations)

    audit_dict = dict(audit)
    if isinstance(audit_dict.get("capture_quality"), str):
        audit_dict["capture_quality"] = json.loads(audit_dict["capture_quality"])

    return EnrichedAuditDetail(
        **{k: v for k, v in audit_dict.items() if k != "account_name"},
        account_name=audit["account_name"],
        observations=enriched_obs,
        images=[dict(i) for i in images],
        share_of_shelf=share_of_shelf,
        summary=summary,
    )


def _enrich_observations(
    observations: list[dict],
    sku_categories: dict[UUID, str],
) -> list[EnrichedObservation]:
    # Build per-category price lists and total facings for enrichment
    total_facings = sum(o.get("facings") or 0 for o in observations)
    category_prices: dict[str, list[float]] = defaultdict(list)

    for o in observations:
        cat = sku_categories.get(o.get("matched_sku_id")) or "other"
        price = o.get("price_value")
        if price:
            category_prices[cat].append(float(price))

    result = []
    for o in observations:
        cat = sku_categories.get(o.get("matched_sku_id")) or "other"
        prices = category_prices.get(cat, [])
        set_avg = (sum(prices) / len(prices)) if prices else None
        price = o.get("price_value")

        if price and set_avg and set_avg > 0:
            delta_pct = round((float(price) - set_avg) / set_avg * 100, 1)
        else:
            delta_pct = None

        facings = o.get("facings")
        facings_share = (
            round(facings / total_facings * 100, 1)
            if facings and total_facings > 0 else None
        )

        position = o.get("shelf_position") or "unknown"
        position_rank = _POSITION_RANK.get(position, "special")

        enrichment = ObservationEnrichment(
            price_delta_vs_set_avg_pct=delta_pct,
            facings_share_of_set=facings_share,
            position_rank=position_rank,
            set_avg_price=round(set_avg, 2) if set_avg else None,
            set_total_facings=total_facings or None,
        )

        result.append(EnrichedObservation(
            **{k: v for k, v in o.items() if k in EnrichedObservation.model_fields and k != "enrichment"},
            enrichment=enrichment,
        ))
    return result


def _compute_share_of_shelf(observations: list[dict]) -> dict[str, float]:
    brand_facings: dict[str, int] = defaultdict(int)
    total = 0
    for o in observations:
        f = o.get("facings") or 0
        brand = o.get("brand_read") or "Unknown"
        brand_facings[brand] += f
        total += f
    if not total:
        return {}
    return {brand: round(f / total * 100, 1) for brand, f in sorted(brand_facings.items(), key=lambda x: -x[1])}


def _compute_summary(observations: list[dict]) -> dict[str, Any]:
    statuses = [o.get("status", "") for o in observations]
    confs = []
    for o in observations:
        fc = o.get("field_confidence") or {}
        if isinstance(fc, dict) and fc:
            confs.append(min(fc.values()))
    return {
        "total_observations": len(observations),
        "confirmed": statuses.count("confirmed"),
        "unmatched": statuses.count("unmatched"),
        "low_confidence": statuses.count("low_confidence"),
        "avg_min_confidence": round(sum(confs) / len(confs), 3) if confs else None,
    }


# ─── Account history with per-SKU deltas ──────────────────────────────────────

@router.get("/accounts/{account_id}/history", response_model=list[AccountHistoryEntry])
async def account_history(
    account_id: UUID,
    request: Request,
    limit: int = 5,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        # Verify account belongs to org
        acct = await conn.fetchrow(
            "SELECT id FROM accounts WHERE id = $1 AND org_id = $2",
            account_id, user.org_id,
        )
        if not acct:
            raise HTTPException(404, "Account not found")

        # Fetch last N non-superseded audits for this account
        audit_rows = await conn.fetch(
            """
            SELECT id, captured_at, status, fixture_type
            FROM shelf_audits
            WHERE account_id = $1 AND superseded_by IS NULL
            ORDER BY captured_at DESC
            LIMIT $2
            """,
            account_id, limit,
        )
        if not audit_rows:
            return []

        audit_ids = [r["id"] for r in audit_rows]

        # Single query: current observations + LATERAL join to most recent prior match
        sku_delta_rows = await conn.fetch(
            """
            SELECT
              cur.audit_id,
              cur.matched_sku_id,
              cur.brand_read,
              cur.sku_guess_text,
              cur.facings            AS current_facings,
              cur.shelf_position     AS current_shelf_position,
              cur.price_value        AS current_price,
              prev.facings           AS previous_facings,
              prev.captured_at       AS prev_captured_at,
              cur_audit.captured_at  AS cur_captured_at
            FROM audit_observations cur
            JOIN shelf_audits cur_audit ON cur_audit.id = cur.audit_id
            LEFT JOIN LATERAL (
              SELECT ao.facings, sa.captured_at
              FROM audit_observations ao
              JOIN shelf_audits sa ON sa.id = ao.audit_id
              WHERE sa.account_id = $1
                AND sa.captured_at < cur_audit.captured_at
                AND sa.superseded_by IS NULL
                AND (
                  (ao.matched_sku_id IS NOT NULL AND ao.matched_sku_id = cur.matched_sku_id)
                  OR (ao.brand_read IS NOT NULL AND ao.brand_read = cur.brand_read)
                )
              ORDER BY sa.captured_at DESC
              LIMIT 1
            ) prev ON true
            WHERE cur.audit_id = ANY($2::uuid[])
            ORDER BY cur.audit_id, cur.brand_read
            """,
            account_id, audit_ids,
        )

    # Group deltas by audit_id
    deltas_by_audit: dict[UUID, list[SKUDelta]] = defaultdict(list)
    for r in sku_delta_rows:
        days = None
        if r["prev_captured_at"]:
            diff = r["cur_captured_at"] - r["prev_captured_at"]
            days = abs(diff.days)

        facings_delta = None
        if r["current_facings"] is not None and r["previous_facings"] is not None:
            facings_delta = r["current_facings"] - r["previous_facings"]

        deltas_by_audit[r["audit_id"]].append(SKUDelta(
            matched_sku_id=r["matched_sku_id"],
            brand_read=r["brand_read"],
            sku_guess_text=r["sku_guess_text"],
            current_facings=r["current_facings"],
            previous_facings=r["previous_facings"],
            facings_delta=facings_delta,
            current_shelf_position=r["current_shelf_position"],
            current_price=float(r["current_price"]) if r["current_price"] else None,
            days_since_previous=days,
            first_seen=r["prev_captured_at"] is None,
        ))

    return [
        AccountHistoryEntry(
            audit_id=a["id"],
            captured_at=a["captured_at"],
            status=a["status"],
            fixture_type=a["fixture_type"],
            sku_deltas=deltas_by_audit.get(a["id"], []),
        )
        for a in audit_rows
    ]


# ─── Review queue ──────────────────────────────────────────────────────────────

@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def review_queue(
    request: Request,
    limit: int = 50,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT rq.*
            FROM review_queue rq
            JOIN shelf_audits sa ON sa.id = rq.audit_id
            WHERE sa.captured_by = $1 OR sa.org_id = $2
            ORDER BY rq.min_confidence ASC NULLS LAST, rq.captured_at DESC
            LIMIT $3
            """,
            user.user_id, user.org_id, limit,
        )
    return [ReviewQueueItem(**dict(r)) for r in rows]


# ─── Competitive intel ─────────────────────────────────────────────────────────

@router.get("/competitive-intel", response_model=list[CompetitorSignal])
async def competitive_intel(
    request: Request,
    limit: int = 50,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              ao.brand_read,
              COUNT(*)                                      AS occurrence_count,
              MAX(sa.captured_at)                          AS latest_seen_at,
              ARRAY_AGG(DISTINCT sa.account_id)            AS account_ids,
              ARRAY_AGG(DISTINCT ao.sku_guess_text)
                FILTER (WHERE ao.sku_guess_text IS NOT NULL)
                                                            AS sample_guess_texts
            FROM audit_observations ao
            JOIN shelf_audits sa ON sa.id = ao.audit_id
            WHERE ao.matched_sku_id IS NULL
              AND ao.brand_read IS NOT NULL
              AND sa.superseded_by IS NULL
              AND (sa.captured_by = $1 OR sa.org_id = $2)
            GROUP BY ao.brand_read
            ORDER BY occurrence_count DESC, latest_seen_at DESC
            LIMIT $3
            """,
            user.user_id, user.org_id, limit,
        )
    return [
        CompetitorSignal(
            brand_read=r["brand_read"],
            occurrence_count=r["occurrence_count"],
            latest_seen_at=r["latest_seen_at"],
            account_ids=list(r["account_ids"] or []),
            sample_guess_texts=list(r["sample_guess_texts"] or [])[:3],
        )
        for r in rows
    ]


# ─── Rep-level CRM dashboard ───────────────────────────────────────────────────

@router.get("/reps/me/dashboard")
async def my_dashboard(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Personal rep dashboard — scoped to captured_by = me.
    Returns: stores visited (count + last visit), total audits, avg quality,
    observations pending review, top unmatched brands seen.
    """
    db = request.app.state.db
    async with db.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
              COUNT(DISTINCT sa.account_id)          AS stores_visited,
              COUNT(*)                                AS total_audits,
              COUNT(*) FILTER (WHERE sa.status='final') AS completed_audits,
              COUNT(*) FILTER (WHERE sa.status='retake_required') AS retake_count,
              COUNT(*) FILTER (WHERE sa.status='guardrail_rejected') AS rejected_count,
              AVG((sa.capture_quality->>'overall_score')::float) AS avg_quality_score,
              MAX(sa.captured_at)                    AS last_activity
            FROM shelf_audits sa
            WHERE sa.captured_by = $1 AND sa.superseded_by IS NULL
            """,
            user.user_id,
        )
        recent_stores = await conn.fetch(
            """
            SELECT ac.name, ac.channel_type, MAX(sa.captured_at) AS last_visit,
                   COUNT(*) AS visit_count
            FROM shelf_audits sa
            JOIN accounts ac ON ac.id = sa.account_id
            WHERE sa.captured_by = $1 AND sa.superseded_by IS NULL
            GROUP BY ac.id, ac.name, ac.channel_type
            ORDER BY last_visit DESC
            LIMIT 10
            """,
            user.user_id,
        )
        pending_review = await conn.fetchval(
            """
            SELECT COUNT(*) FROM review_queue rq
            JOIN shelf_audits sa ON sa.id = rq.audit_id
            WHERE sa.captured_by = $1
            """,
            user.user_id,
        )
        top_unmatched = await conn.fetch(
            """
            SELECT ao.brand_read, COUNT(*) AS times_seen
            FROM audit_observations ao
            JOIN shelf_audits sa ON sa.id = ao.audit_id
            WHERE sa.captured_by = $1
              AND ao.matched_sku_id IS NULL
              AND ao.brand_read IS NOT NULL
            GROUP BY ao.brand_read
            ORDER BY times_seen DESC
            LIMIT 5
            """,
            user.user_id,
        )

    return {
        "rep_id": str(user.user_id),
        "summary": {
            "stores_visited": stats["stores_visited"],
            "total_audits": stats["total_audits"],
            "completed_audits": stats["completed_audits"],
            "retake_count": stats["retake_count"],
            "rejected_count": stats["rejected_count"],
            "avg_quality_score": round(float(stats["avg_quality_score"] or 0), 3),
            "last_activity": stats["last_activity"].isoformat() if stats["last_activity"] else None,
            "pending_review_count": pending_review,
        },
        "stores": [
            {
                "name": r["name"],
                "channel_type": r["channel_type"],
                "last_visit": r["last_visit"].isoformat(),
                "visit_count": r["visit_count"],
            }
            for r in recent_stores
        ],
        "top_unmatched_brands": [
            {"brand_read": r["brand_read"], "times_seen": r["times_seen"]}
            for r in top_unmatched
        ],
    }


@router.get("/org/dashboard")
async def org_dashboard(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Org-level dashboard — all reps in the same org_id.
    Shows per-rep activity breakdown so managers can track field coverage.
    """
    db = request.app.state.db
    async with db.acquire() as conn:
        per_rep = await conn.fetch(
            """
            SELECT
              sa.captured_by                                AS rep_id,
              COUNT(DISTINCT sa.account_id)                 AS stores_visited,
              COUNT(*)                                      AS total_audits,
              COUNT(*) FILTER (WHERE sa.status = 'final')  AS completed,
              MAX(sa.captured_at)                          AS last_active,
              ROUND(AVG((sa.capture_quality->>'overall_score')::float)::numeric, 3)
                                                           AS avg_quality
            FROM shelf_audits sa
            WHERE sa.org_id = $1 AND sa.superseded_by IS NULL
            GROUP BY sa.captured_by
            ORDER BY last_active DESC
            """,
            user.org_id,
        )
        coverage = await conn.fetch(
            """
            SELECT ac.name, ac.channel_type,
                   MAX(sa.captured_at) AS last_audited,
                   COUNT(*) AS audit_count
            FROM shelf_audits sa
            JOIN accounts ac ON ac.id = sa.account_id
            WHERE sa.org_id = $1 AND sa.superseded_by IS NULL
            GROUP BY ac.id, ac.name, ac.channel_type
            ORDER BY last_audited DESC
            """,
            user.org_id,
        )

    return {
        "org_id": str(user.org_id),
        "reps": [
            {
                "rep_id": str(r["rep_id"]),
                "stores_visited": r["stores_visited"],
                "total_audits": r["total_audits"],
                "completed": r["completed"],
                "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                "avg_quality": float(r["avg_quality"] or 0),
            }
            for r in per_rep
        ],
        "store_coverage": [
            {
                "name": r["name"],
                "channel_type": r["channel_type"],
                "last_audited": r["last_audited"].isoformat() if r["last_audited"] else None,
                "audit_count": r["audit_count"],
            }
            for r in coverage
        ],
    }


# ─── Share-of-Shelf Summary (cross-audit) ─────────────────────────────────────

@router.get("/share-of-shelf/summary")
async def share_of_shelf_summary(
    request: Request,
    account_id: UUID | None = None,
    limit: int = 15,
    user: AuthUser = Depends(get_current_user),
):
    """
    Aggregate share-of-shelf across audits.
    Groups by brand_read (or visual_brand_guess fallback), sums facings,
    computes percentage of total facings.

    Optional account_id filter to scope to single store.
    Returns: total_facings, total_audits, brands: [{brand, facings, share_pct, audit_count, avg_price, eye_level_count}]
    """
    db = request.app.state.db
    if limit > 50:
        limit = 50

    where = ["sa.superseded_by IS NULL", "(sa.captured_by = $1 OR sa.org_id = $2)"]
    params = [user.user_id, user.org_id]

    if account_id:
        where.append("sa.account_id = $" + str(len(params) + 1))
        params.append(account_id)

    where_sql = " AND ".join(where)

    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
              COALESCE(ao.brand_read, ao.visual_brand_guess, 'Unknown') AS brand,
              COALESCE(SUM(ao.facings), 0) AS total_facings,
              COUNT(DISTINCT ao.audit_id) AS audit_count,
              AVG(ao.price_value) AS avg_price,
              COUNT(CASE WHEN ao.shelf_position IN ('eye_level','top') THEN 1 END) AS eye_level_count,
              COUNT(CASE WHEN ao.matched_sku_id IS NOT NULL THEN 1 END) AS confirmed_count
            FROM audit_observations ao
            JOIN shelf_audits sa ON sa.id = ao.audit_id
            WHERE {where_sql}
            GROUP BY COALESCE(ao.brand_read, ao.visual_brand_guess, 'Unknown')
            ORDER BY total_facings DESC
            LIMIT {limit}
            """,
            *params,
        )

        total_row = await conn.fetchrow(
            f"""
            SELECT COALESCE(SUM(ao.facings), 0) AS grand_total
            FROM audit_observations ao
            JOIN shelf_audits sa ON sa.id = ao.audit_id
            WHERE {where_sql}
            """,
            *params,
        )

    grand_total = total_row["grand_total"] if total_row else 0

    brands = []
    for r in rows:
        facings = r["total_facings"] or 0
        brands.append({
            "brand": r["brand"],
            "facings": facings,
            "share_pct": round(facings / grand_total * 100, 1) if grand_total > 0 else 0.0,
            "audit_count": r["audit_count"] or 0,
            "avg_price": round(float(r["avg_price"]), 2) if r["avg_price"] else None,
            "eye_level_count": r["eye_level_count"] or 0,
            "confirmed_count": r["confirmed_count"] or 0,
        })

    return {
        "total_facings": grand_total,
        "brand_count": len(brands),
        "brands": brands,
    }
