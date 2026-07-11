"""
Transactional writer — persists a completed audit pipeline result to Postgres.
Insert-only (append-only versioning). Never updates existing rows.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any

import asyncpg


async def write_audit_result(
    conn: asyncpg.Connection,
    audit_id: UUID,
    account_id: UUID,
    storage_path: str,
    preview_path: str | None,
    image_bytes: bytes,
    quality_result: Any,
    vlm_json: dict,
    judged_json: dict,
    model_version: str,
    latency_ms: int,
    observations: list[dict],
) -> None:
    content_hash = hashlib.sha256(image_bytes).hexdigest()

    async with conn.transaction():
        # 1. Update audit row to final status
        status = "retake_required" if not quality_result.passed else "final"
        await conn.execute(
            """
            UPDATE shelf_audits SET
              status = $1,
              fixture_type = $2,
              capture_quality = $3::jsonb,
              model_version = $4,
              latency_ms = $5
            WHERE id = $6
            """,
            status,
            judged_json.get("fixture_type", "unknown"),
            json.dumps(quality_result.to_jsonb()),
            model_version,
            latency_ms,
            audit_id,
        )

        # 2. Insert audit_images row
        await conn.execute(
            """
            INSERT INTO audit_images
              (audit_id, storage_path, preview_path, content_hash,
               width_px, height_px, size_bytes, quality_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            audit_id,
            storage_path,
            preview_path,
            content_hash,
            quality_result.width_px,
            quality_result.height_px,
            len(image_bytes),
            quality_result.overall_score,
        )

        # 3. Insert raw VLM output as event
        await conn.execute(
            """
            INSERT INTO audit_events (audit_id, event_type, payload)
            VALUES ($1, 'vlm_raw_output', $2::jsonb)
            """,
            audit_id,
            json.dumps({"vlm": vlm_json, "judged": judged_json}),
        )

        # 4. Insert observations
        for obs in observations:
            await conn.execute(
                """
                INSERT INTO audit_observations (
                  id, audit_id, matched_sku_id, sku_guess_text,
                  brand_read, size_read, facings, shelf_position,
                  price_value, price_confidence,
                  field_confidence, status,
                  match_method, match_similarity, notes
                ) VALUES (
                  $1, $2, $3, $4, $5, $6, $7, $8,
                  $9, $10, $11::jsonb, $12, $13, $14, $15
                )
                """,
                uuid4(),
                audit_id,
                obs.get("matched_sku_id"),
                obs.get("sku_guess_text"),
                obs.get("brand_read"),
                obs.get("size_read"),
                obs.get("facings"),
                obs.get("shelf_position"),
                _parse_price(obs.get("price_read")),
                obs.get("price_confidence"),
                json.dumps(obs.get("field_confidence", {})),
                obs.get("obs_status", "confirmed"),
                obs.get("match_method"),
                obs.get("match_similarity"),
                obs.get("notes"),
            )

        # 5. Flag judge_adjusted event if judge changed anything
        if judged_json.get("judge_summary"):
            await conn.execute(
                """
                INSERT INTO audit_events (audit_id, event_type, payload)
                VALUES ($1, 'judge_adjusted', $2::jsonb)
                """,
                audit_id,
                json.dumps({"summary": judged_json["judge_summary"]}),
            )


def _parse_price(price_str: str | None) -> float | None:
    if not price_str:
        return None
    try:
        return float(str(price_str).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None
