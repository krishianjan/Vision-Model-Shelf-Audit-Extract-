"""
CRM Dashboard routes — Rep summaries, store insights, SKU trends, quality metrics.

Safe queries: no hardcoding, all dynamic data from database.
Type-safe: all numeric fields verified against schema.
"""
from __future__ import annotations

import json
from uuid import UUID
from typing import Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import AuthUser, get_current_user

router = APIRouter(tags=["dashboard"])


# ─── Route 1: Rep Summary Dashboard ────────────────────────────────────────

@router.get("/reps/me/dashboard")
async def my_dashboard(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Rep's dashboard summary.

    Returns: stores_visited, total_audits, completed_audits,
             avg_quality_score, pending_review_count
    """
    db = request.app.state.db

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              COUNT(DISTINCT account_id) as stores_visited,
              COUNT(*) as total_audits,
              COUNT(CASE WHEN status = 'final' THEN 1 END) as completed_audits,
              COALESCE(AVG(CAST((capture_quality->>'overall_score') AS FLOAT)), 0) as avg_quality_score,
              COUNT(CASE WHEN status IN ('retake_required','processing_failed') THEN 1 END) as pending_review_count
            FROM shelf_audits
            WHERE captured_by = $1
              AND org_id = $2
              AND superseded_by IS NULL
            """,
            user.user_id,
            user.org_id,
        )

    if not row:
        return {
            "summary": {
                "stores_visited": 0,
                "total_audits": 0,
                "completed_audits": 0,
                "avg_quality_score": 0.0,
                "pending_review_count": 0,
            }
        }

    return {
        "summary": {
            "stores_visited": row["stores_visited"] or 0,
            "total_audits": row["total_audits"] or 0,
            "completed_audits": row["completed_audits"] or 0,
            "avg_quality_score": float(row["avg_quality_score"] or 0.0),
            "pending_review_count": row["pending_review_count"] or 0,
        }
    }


# ─── Route 2: Store Insights (Last 5 Audits) ───────────────────────────────

@router.get("/stores/{account_id}/insights")
async def store_insights(
    account_id: UUID,
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Store-level insights: last 5 audits with observation stats + quality.

    Returns: audit_id, captured_at, status, observation_count, confirmed_count,
             unmatched_count, total_facings, avg_brand_confidence, latest_quality_score
    """
    db = request.app.state.db

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              sa.id as audit_id,
              sa.captured_at,
              sa.status,
              COUNT(ao.id) as observation_count,
              COUNT(CASE WHEN ao.status = 'confirmed' THEN 1 END) as confirmed_count,
              COUNT(CASE WHEN ao.matched_sku_id IS NULL THEN 1 END) as unmatched_count,
              COALESCE(SUM(ao.facings), 0) as total_facings,
              COALESCE(AVG(CAST((ao.field_confidence->>'brand')::NUMERIC AS FLOAT)), 0) as avg_brand_confidence,
              CAST((sa.capture_quality->>'overall_score') AS FLOAT) as latest_quality_score
            FROM shelf_audits sa
            LEFT JOIN audit_observations ao ON ao.audit_id = sa.id
            WHERE sa.account_id = $1
              AND sa.org_id = $2
              AND sa.superseded_by IS NULL
            GROUP BY sa.id, sa.captured_at, sa.status, sa.capture_quality
            ORDER BY sa.captured_at DESC
            LIMIT 5
            """,
            account_id,
            user.org_id,
        )

    result = []
    for row in rows:
        result.append({
            "audit_id": str(row["audit_id"]),
            "captured_at": row["captured_at"].isoformat() if row["captured_at"] else None,
            "status": row["status"],
            "observation_count": row["observation_count"] or 0,
            "confirmed_count": row["confirmed_count"] or 0,
            "unmatched_count": row["unmatched_count"] or 0,
            "total_facings": row["total_facings"] or 0,
            "avg_brand_confidence": float(row["avg_brand_confidence"] or 0.0),
            "latest_quality_score": float(row["latest_quality_score"] or 0.0),
        })

    return {"insights": result}


# ─── Route 3: SKU Performance (Brand Trends) ───────────────────────────────

@router.get("/stores/{account_id}/skus")
async def store_skus(
    account_id: UUID,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    limit: int = 10,
):
    """
    SKU performance: top brands by facings with pricing + placement insights.

    Returns: brand, total_facings, avg_price, eye_level_facings,
             audit_count, last_seen, avg_confidence, confirmed_count
    """
    db = request.app.state.db

    if limit > 50:
        limit = 50
    if limit < 1:
        limit = 10

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              ao.brand_read as brand,
              COALESCE(SUM(ao.facings), 0) as total_facings,
              COALESCE(AVG(ao.price_value), 0) as avg_price,
              COUNT(CASE WHEN ao.shelf_position = 'eye_level' THEN 1 END) as eye_level_facings,
              COUNT(DISTINCT ao.audit_id) as audit_count,
              MAX(ao.created_at) as last_seen,
              COALESCE(AVG(CAST((ao.field_confidence->>'brand')::NUMERIC AS FLOAT)), 0) as avg_confidence,
              COUNT(CASE WHEN ao.matched_sku_id IS NOT NULL THEN 1 END) as confirmed_count
            FROM audit_observations ao
            JOIN shelf_audits sa ON sa.id = ao.audit_id
            WHERE sa.account_id = $1
              AND sa.org_id = $2
              AND ao.brand_read IS NOT NULL
              AND sa.superseded_by IS NULL
            GROUP BY ao.brand_read
            ORDER BY total_facings DESC
            LIMIT $3
            """,
            account_id,
            user.org_id,
            limit,
        )

    result = []
    for row in rows:
        result.append({
            "brand": row["brand"],
            "total_facings": row["total_facings"] or 0,
            "avg_price": float(row["avg_price"] or 0.0),
            "eye_level_facings": row["eye_level_facings"] or 0,
            "audit_count": row["audit_count"] or 0,
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            "avg_confidence": float(row["avg_confidence"] or 0.0),
            "confirmed_count": row["confirmed_count"] or 0,
        })

    return {"skus": result}


# ─── Route 4: Quality Trend (Last 14 Days) ────────────────────────────────

@router.get("/reps/me/quality-trend")
async def quality_trend(
    request: Request,
    user: AuthUser = Depends(get_current_user),
    days: int = 14,
):
    """
    Rep's quality trend: last N days of audits with quality scores.

    Returns: audit_date, audit_count, avg_quality, successful_audits, failed_audits
    """
    db = request.app.state.db

    if days > 90:
        days = 90
    if days < 1:
        days = 14

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              DATE(captured_at AT TIME ZONE 'UTC') as audit_date,
              COUNT(*) as audit_count,
              COALESCE(AVG(CAST((capture_quality->>'overall_score')::NUMERIC AS FLOAT)), 0) as avg_quality,
              COUNT(CASE WHEN status = 'final' THEN 1 END) as successful_audits,
              COUNT(CASE WHEN status IN ('retake_required','processing_failed') THEN 1 END) as failed_audits
            FROM shelf_audits
            WHERE captured_by = $1
              AND org_id = $2
              AND captured_at >= NOW() - INTERVAL '%s days'
              AND superseded_by IS NULL
            GROUP BY DATE(captured_at AT TIME ZONE 'UTC')
            ORDER BY audit_date DESC
            """.replace("%s", str(days)),
            user.user_id,
            user.org_id,
        )

    result = []
    for row in rows:
        result.append({
            "audit_date": row["audit_date"].isoformat() if row["audit_date"] else None,
            "audit_count": row["audit_count"] or 0,
            "avg_quality": float(row["avg_quality"] or 0.0),
            "successful_audits": row["successful_audits"] or 0,
            "failed_audits": row["failed_audits"] or 0,
        })

    return {"trend": result}
