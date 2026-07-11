"""CRM enrichment response models."""
from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class PositionRank(str):
    pass


class ObservationEnrichment(BaseModel):
    price_delta_vs_set_avg_pct: float | None   # e.g. +12.3 means 12.3% above set avg
    facings_share_of_set: float | None         # 0-100
    position_rank: str | None                  # "premium" | "standard" | "value" | "special"
    set_avg_price: float | None
    set_total_facings: int | None


class EnrichedObservation(BaseModel):
    id: UUID
    matched_sku_id: UUID | None
    sku_guess_text: str | None
    brand_read: str | None
    size_read: str | None
    facings: int | None
    shelf_position: str | None
    price_value: float | None
    price_confidence: float | None
    field_confidence: dict[str, Any]
    status: str
    match_method: str | None
    match_similarity: float | None
    notes: str | None
    created_at: datetime
    enrichment: ObservationEnrichment


class EnrichedAuditDetail(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str | None
    org_id: UUID
    captured_by: UUID
    captured_at: datetime
    received_at: datetime
    fixture_type: str | None
    capture_quality: dict[str, Any] | None
    status: str
    version: int
    superseded_by: UUID | None
    model_version: str | None
    latency_ms: int | None
    created_at: datetime
    observations: list[EnrichedObservation]
    images: list[dict]
    share_of_shelf: dict[str, float]          # brand → % of total facings
    summary: dict[str, Any]                   # total_obs, confirmed, unmatched, avg_confidence


class SKUDelta(BaseModel):
    matched_sku_id: UUID | None
    brand_read: str | None
    sku_guess_text: str | None
    current_facings: int | None
    previous_facings: int | None
    facings_delta: int | None
    current_shelf_position: str | None
    current_price: float | None
    days_since_previous: int | None
    first_seen: bool


class AccountHistoryEntry(BaseModel):
    audit_id: UUID
    captured_at: datetime
    status: str
    fixture_type: str | None
    sku_deltas: list[SKUDelta]


class CompetitorSignal(BaseModel):
    brand_read: str
    occurrence_count: int
    latest_seen_at: datetime
    account_ids: list[UUID]
    sample_guess_texts: list[str]


class ReviewQueueItem(BaseModel):
    observation_id: UUID
    audit_id: UUID
    account_id: UUID
    captured_by: UUID
    brand_read: str | None
    sku_guess_text: str | None
    status: str
    field_confidence: dict[str, Any]
    min_confidence: float | None
    captured_at: datetime
