from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AuditCreateResponse(BaseModel):
    audit_id: UUID
    status: str


class ObservationOut(BaseModel):
    id: UUID
    matched_sku_id: UUID | None
    sku_guess_text: str | None
    brand_read: str | None
    visual_brand_guess: str | None = None
    visual_brand_confidence: float | None = None
    product_read: str | None = None
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
    # Visual cues
    bottle_shape: str | None = None
    glass_tint: str | None = None
    cap_type: str | None = None
    label_color: str | None = None
    label_design: str | None = None
    damage_flags: str | None = None
    stock_level: str | None = None
    alcohol_subcategory: str | None = None
    created_at: datetime


class AuditImageOut(BaseModel):
    id: UUID
    storage_path: str
    preview_path: str | None
    width_px: int | None
    height_px: int | None
    quality_score: float | None


class AuditDetail(BaseModel):
    id: UUID
    account_id: UUID
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
    observations: list[ObservationOut] = []
    images: list[AuditImageOut] = []
    created_at: datetime

    @classmethod
    def compose(cls, audit: Any, obs: list[Any], images: list[Any]) -> AuditDetail:
        return cls(
            **dict(audit),
            observations=[ObservationOut(**dict(o)) for o in obs],
            images=[AuditImageOut(**dict(i)) for i in images],
        )

    @classmethod
    def summary(cls, audit: Any) -> AuditDetail:
        return cls(**dict(audit))


class AuditSummaryList(BaseModel):
    """Lightweight list item — no observations, no images, no quality blob."""
    id: UUID
    account_id: UUID
    account_name: str | None = None
    org_id: UUID
    captured_by: UUID
    captured_at: datetime
    received_at: datetime
    fixture_type: str | None
    status: str
    version: int
    superseded_by: UUID | None
    model_version: str | None
    latency_ms: int | None
    created_at: datetime
