"""
LangGraph pipeline state. Pydantic-compatible TypedDict.
events uses operator.add reducer — each node appends its events,
all are flushed in a single DB transaction at the persist node.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict
from uuid import UUID


class PipelineState(TypedDict):
    # Inputs
    audit_id: UUID
    account_id: UUID
    org_id: UUID
    captured_by: UUID
    image_bytes: bytes
    storage_path: str

    # Intermediate — set as pipeline progresses
    processed_bytes: bytes | None       # CLAHE-rescued image if quality warn
    quality: dict | None                # QualityResult.to_json()
    guardrail: dict | None              # GuardrailResult.to_json()
    vlm_result: dict | None             # VLMExtractionResult serialised
    match_results: list[dict] | None    # per-observation MatchResult dicts
    judge_result: dict | None           # JudgeResult serialised

    # Final
    final_observations: list[dict] | None
    terminal_status: str | None         # set by any terminal branch
    error: str | None                   # VLMChainExhausted or other fatal errors

    # Append-only event log — all events flushed in one transaction at persist
    events: Annotated[list[dict], operator.add]
