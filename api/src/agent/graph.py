"""
 LangGraph orchestration.

Nodes:
  quality_gate → guardrail → vlm_extract → rag_ground → judge → persist_final
               ↘ persist_terminal (quality reject / vlm exhausted)
               ↘ persist_rejected (guardrail reject)
               ↘ store_entry_flow (storefront photo stub)

All DB writes are deferred to the persist nodes and executed in a single transaction.
"""
from __future__ import annotations

import json
import re
import time
from uuid import UUID, uuid4
import asyncio
import asyncpg
from langgraph.graph import StateGraph, END

from src.agent.state import PipelineState
from src.perception.quality import check_quality
from src.perception.base import QualityResult, GuardrailResult
from src.perception.vlm import VLMOrchestrator, VLMExtractionResult, VLMChainExhausted, Observation
from src.perception.enhance import enhance_image
from src.grounding.matcher import SKUMatcher, MatchResult
from src.grounding.judge import Judge, JudgeResult, CalibratedObservation


def _ser(obj) -> dict:
    """Recursively convert dataclasses / Pydantic models to dicts for state storage.
    Also converts numpy scalars to native python types."""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "model_dump"):
        return {k: _ser(v) for k, v in obj.model_dump().items()}
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        return {k: _ser(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ser(v) for v in obj]
    return obj


class ShelfAuditAgent:
    """
    Dependency-injected LangGraph agent.
    Instantiate once at startup; call ainvoke(initial_state) per request.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        storage,
        guardrail,
        matcher: SKUMatcher,
        vlm: VLMOrchestrator,
        judge: Judge,
    ):
        self._db = db_pool
        self._storage = storage
        self._guardrail = guardrail
        self._matcher = matcher
        self._vlm = vlm
        self._judge = judge
        self._graph = self._build_graph()

    # ─── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        g = StateGraph(PipelineState)

        g.add_node("quality_gate", self._quality_gate)
        g.add_node("guardrail", self._guardrail_node)
        g.add_node("vlm_extract", self._vlm_extract)
        g.add_node("rag_ground", self._rag_ground)
        g.add_node("judge", self._judge_node)
        g.add_node("persist_final", self._persist_final)
        g.add_node("persist_terminal", self._persist_terminal)
        g.add_node("persist_rejected", self._persist_rejected)
        g.add_node("store_entry_flow", self._store_entry_flow)

        g.set_entry_point("quality_gate")

        g.add_conditional_edges(
            "quality_gate",
            _route_quality,
            {"persist_terminal": "persist_terminal", "guardrail": "guardrail"},
        )
        g.add_conditional_edges(
            "guardrail",
            _route_guardrail,
            {
                "persist_rejected": "persist_rejected",
                "persist_terminal": "persist_terminal",  # For retakes (flagged images)
                "store_entry_flow": "store_entry_flow",
                "vlm_extract": "vlm_extract",
            },
        )
        g.add_conditional_edges(
            "vlm_extract",
            _route_vlm,
            {"persist_terminal": "persist_terminal", "rag_ground": "rag_ground"},
        )
        g.add_edge("rag_ground", "judge")
        g.add_conditional_edges(
            "judge",
            _route_confidence,
            {
                "persist_final": "persist_final",
                "persist_terminal": "persist_terminal",
            },
        )
        g.add_edge("persist_final", END)
        g.add_edge("persist_terminal", END)
        g.add_edge("persist_rejected", END)
        g.add_edge("store_entry_flow", END)

        return g.compile()

    async def ainvoke(self, initial_state: dict):
        audit_id = initial_state.get("audit_id")
        try:
            # Set heartbeat timeout: if graph takes >60s per node, abort
            return await self._graph.ainvoke(initial_state)
        except TimeoutError:
            print(f"[ERROR] Pipeline timed out for audit {audit_id}")
            if audit_id:
                try:
                    import json
                    async with self._db.acquire() as conn:
                        await conn.execute(
                            "UPDATE shelf_audits SET status='processing_failed' WHERE id=$1 AND status='processing'",
                            audit_id,
                        )
                        await conn.execute(
                            "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1, 'vlm_failed', $2::jsonb)",
                            audit_id, json.dumps({"reason": "pipeline_timeout_60s"}),
                        )
                except Exception:
                    pass
            raise
        except asyncio.TimeoutError:
            print(f"[ERROR] Pipeline async timeout for audit {audit_id}")
            if audit_id:
                try:
                    import json
                    async with self._db.acquire() as conn:
                        await conn.execute(
                            "UPDATE shelf_audits SET status='processing_failed' WHERE id=$1 AND status='processing'",
                            audit_id,
                        )
                        await conn.execute(
                            "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1, 'vlm_failed', $2::jsonb)",
                            audit_id, json.dumps({"reason": "async_timeout_120s"}),
                        )
                except Exception:
                    pass
            raise
        except Exception as e:
            # Crash protection: update audit to failed so it doesn't stay stuck
            print(f"[ERROR] Pipeline crashed for audit {audit_id}: {e}")
            if audit_id:
                try:
                    import json
                    async with self._db.acquire() as conn:
                        await conn.execute(
                            "UPDATE shelf_audits SET status='processing_failed' WHERE id=$1 AND status='processing'",
                            audit_id,
                        )
                        await conn.execute(
                            "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1, 'vlm_failed', $2::jsonb)",
                            audit_id, json.dumps({"reason": "pipeline_crash", "error": str(e)[:500]}),
                        )
                except Exception:
                    pass
            raise

    # ─── Nodes ─────────────────────────────────────────────────────────────────

    async def _quality_gate(self, state: PipelineState) -> dict:
        quality, processed = check_quality(state["image_bytes"])
        event_type = "quality_check_fail" if quality.verdict == "reject" else "quality_check_pass"
        return {
            "quality": quality.to_json(),
            "processed_bytes": processed,
            "terminal_status": "retake_required" if quality.verdict == "reject" else None,
            "events": [{"event_type": event_type, "payload": quality.to_json()}],
        }

    async def _guardrail_node(self, state: PipelineState) -> dict:
        """
        STAGE 1: FAST GATEKEEPER (YOLO lazy → CLIP ensemble).

        Rejects non-alcoholic/food/non-retail before expensive VLM extraction.
        Returns instantly with verdict (reject/pass) in <10s.
        Uncertain cases (0.35-0.65) are passed to Qwen for quality/extraction assessment.
        """
        image = state.get("processed_bytes") or state["image_bytes"]

        # Call async guardrail (YOLO + CLIP ensemble)
        gr: GuardrailResult = await self._guardrail.classify_async(image)

        # Log detailed rejection/acceptance reasons (use valid event_type values from DB)
        event_type = (
            "guardrail_reject"
            if gr.verdict == "reject"
            else "guardrail_pass"
        )
        event_payload = gr.to_json()

        # Add explicit reasoning for audit trail
        if gr.verdict == "reject":
            event_payload["audit_reason"] = f"REJECTED: {gr.rejection_reason or gr.reason}"
        else:
            event_payload["audit_reason"] = f"PASSED: {gr.reason}"

        # Merge with existing events (quality_gate events) to maintain full pipeline trail
        existing_events = state.get("events") or []
        new_event = {"event_type": event_type, "payload": event_payload}
        all_events = existing_events + [new_event]

        return {
            "guardrail": gr.to_json(),
            "events": all_events,
        }

    async def _vlm_extract(self, state: PipelineState) -> dict:
        image = state.get("processed_bytes") or state["image_bytes"]
        try:
            # Enhance image before VLM (handles glare, angle, thumb, dark coolers)
            # TEMPORARILY BYPASSED — numpy type bug in HoughLinesP
            # enhanced_bytes, enh_report = enhance_image(image)
            enhanced_bytes = image
            enh_report = {"applied": []}
            if enh_report["applied"]:
                print(f"[ENHANCE] Applied: {', '.join(enh_report['applied'])}")
                events = state.get("events") or []
                events.append({"event_type": "image_enhanced", "payload": enh_report})
                state["events"] = events

            result: VLMExtractionResult = await self._vlm.extract_shelf(enhanced_bytes)

            # CHECK: VLM says non-alcohol → reject (no tokens wasted on RAG/judge)
            if result.alcohol_type == "non_alcohol":
                return {
                    "error": "Non-alcoholic beverages detected by VLM",
                    "terminal_status": "guardrail_rejected",
                    "events": [{"event_type": "guardrail_reject", "payload": {
                        "source": "vlm_post_check",
                        "model": result.model_used,
                        "alcohol_type": result.alcohol_type,
                    }}],
                }

            # CHECK: Image quality too low → retake (from Qwen's quality rating)
            if result.image_quality_score < 0.45:
                return {
                    "error": f"Image quality too low ({result.image_quality_score:.2f})",
                    "terminal_status": "retake_required",
                    "retake_reason": result.degradation_reason or f"Poor image quality (score: {result.image_quality_score:.2f}). {result.degradation_reason if result.degradation_reason else 'Retake with better lighting/angle.'}",
                    "events": [{"event_type": "flagged_for_review", "payload": {
                        "reason": "low_image_quality",
                        "model": result.model_used,
                        "quality_score": result.image_quality_score,
                        "degradation_reason": result.degradation_reason,
                    }}],
                }

            # CHECK: Low confidence on alcohol shelf → flag for retake
            if result.alcohol_type != "non_alcohol" and result.confidence_overall < 0.45 and len(result.observations) < 2:
                return {
                    "error": f"Low extraction confidence ({result.confidence_overall:.2f})",
                    "terminal_status": "retake_required",
                    "retake_reason": f"Alcohol shelf detected but extraction confidence too low ({result.confidence_overall:.2f}). Retake with better lighting.",
                    "events": [{"event_type": "flagged_for_review", "payload": {
                        "reason": "low_extraction_confidence",
                        "model": result.model_used,
                        "confidence": result.confidence_overall,
                        "obs_count": len(result.observations),
                    }}],
                }

            return {
                "vlm_result": result.model_dump(),
                "events": [{"event_type": "vlm_raw_output", "payload": {
                    "model": result.model_used,
                    "fallback_chain": result.fallback_chain,
                    "latency_ms": result.latency_ms,
                    "obs_count": len(result.observations),
                    "image_quality_score": result.image_quality_score,
                }}],
            }
        except VLMChainExhausted as e:
            return {
                "error": str(e),
                "terminal_status": "processing_failed",
                "events": [{"event_type": "vlm_failed", "payload": {"errors": e.errors}}],
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "terminal_status": "processing_failed",
                "events": [{"event_type": "vlm_failed", "payload": {
                    "error": str(e),
                    "traceback": traceback.format_exc()[-300:],
                }}],
            }

    async def _rag_ground(self, state: PipelineState) -> dict:
        vlm_dict = state["vlm_result"]
        observations = vlm_dict.get("observations") or []

        async with self._db.acquire() as conn:
            match_results = []
            for obs in observations:
                mr = await self._matcher.match(
                    conn,
                    obs.get("brand_read"),
                    obs.get("size_read"),
                    obs.get("product_read"),
                )
                match_results.append(_ser(mr))

        return {
            "match_results": match_results,
            "events": [{"event_type": "rag_matched", "payload": {
                "total": len(match_results),
                "matched": sum(1 for m in match_results if m.get("matched_sku_id")),
                "unresolved": sum(1 for m in match_results if not m.get("matched_sku_id")),
            }}],
        }

    async def _judge_node(self, state: PipelineState) -> dict:
        from src.perception.vlm import VLMExtractionResult, Observation
        from src.grounding.matcher import MatchResult
        from src.perception.base import QualityResult

        vlm_result = VLMExtractionResult(**state["vlm_result"])

        raw_matches = state["match_results"] or []
        match_results = []
        for m in raw_matches:
            raw_id = m.get("matched_sku_id")
            if raw_id is None:
                sku_id = None
            elif isinstance(raw_id, UUID):
                sku_id = raw_id
            else:
                sku_id = UUID(str(raw_id))
            match_results.append(MatchResult(
                matched_sku_id=sku_id,
                match_method=m.get("match_method", "unresolved"),
                match_similarity=float(m.get("match_similarity", 0.0)),
                top_candidates=m.get("top_candidates") or [],
                sku_guess_text=m.get("sku_guess_text"),
            ))

        quality_dict = state["quality"]
        quality = QualityResult(
            overall_score=quality_dict.get("overall_score", 0.0),
            blur_score=quality_dict.get("blur_score", 0.0),
            exposure_score=quality_dict.get("exposure_score", 0.0),
            resolution_ok=quality_dict.get("resolution_ok", True),
            aspect_ratio_ok=quality_dict.get("aspect_ratio_ok", True),
            verdict=quality_dict.get("verdict", "pass"),
            issues=quality_dict.get("issues", []),
            retake_reason=quality_dict.get("retake_reason"),
            content_hash=quality_dict.get("content_hash"),
            width=quality_dict.get("width", 0),
            height=quality_dict.get("height", 0),
        )

        judge_result: JudgeResult = await self._judge.calibrate(vlm_result, match_results, quality)

        final_obs = [o.to_db_dict() for o in judge_result.observations]

        event_payload = {
            "model": judge_result.model_used,
            "latency_ms": judge_result.latency_ms,
            "notes": judge_result.notes,
            "hard_rules": judge_result.hard_rules_applied,
        }

        return {
            "judge_result": {
                "model_used": judge_result.model_used,
                "latency_ms": judge_result.latency_ms,
                "notes": judge_result.notes,
                "hard_rules_applied": judge_result.hard_rules_applied,
            },
            "final_observations": final_obs,
            "events": [{"event_type": "judge_adjusted", "payload": event_payload}],
        }

    async def _persist_final(self, state: PipelineState) -> dict:
        audit_id = state["audit_id"]
        account_id = state["account_id"]
        image_bytes = state["image_bytes"]
        storage_path = state["storage_path"]
        quality_dict = state["quality"] or {}
        vlm_dict = state.get("vlm_result") or {}
        judge_dict = state.get("judge_result") or {}
        final_obs = state.get("final_observations") or []
        events = state.get("events") or []

        import hashlib
        content_hash = quality_dict.get("content_hash") or hashlib.sha256(image_bytes).hexdigest()
        model_version = vlm_dict.get("model_used") or "unknown"
        vlm_latency = vlm_dict.get("latency_ms", 0)
        judge_latency = judge_dict.get("latency_ms", 0)
        total_latency = vlm_latency + judge_latency

        async with self._db.acquire() as conn:
            async with conn.transaction():
                # Determine status based on confidence
                confidence = vlm_dict.get("confidence_overall", 0.0)
                status = "final" if confidence >= 0.55 else "retake_required"
                
                # Update shelf_audit
                await conn.execute(
                    """
                    UPDATE shelf_audits SET
                      status = $2,
                      fixture_type = COALESCE($3, 'unknown'),
                      capture_quality = $4::jsonb,
                      model_version = $5,
                      latency_ms = $6
                    WHERE id = $1
                    """,
                    audit_id,
                    status,
                    vlm_dict.get("fixture_type"),
                    json.dumps(quality_dict),
                    model_version,
                    total_latency,
                )

                # Insert audit_images record
                await conn.execute(
                    """
                    INSERT INTO audit_images
                      (audit_id, storage_path, content_hash, width_px, height_px,
                       size_bytes, quality_score)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                    """,
                    audit_id, storage_path, content_hash,
                    quality_dict.get("width"), quality_dict.get("height"),
                    len(image_bytes),
                    quality_dict.get("overall_score"),
                )

                # Bulk insert all accumulated events
                for ev in events:
                    await conn.execute(
                        "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1, $2, $3::jsonb)",
                        audit_id, ev["event_type"], json.dumps(ev["payload"]),
                    )

                # Get org_id from shelf_audits
                audit_row = await conn.fetchrow(
                    "SELECT org_id FROM shelf_audits WHERE id = $1",
                    audit_id
                )
                org_id = audit_row["org_id"] if audit_row else None

                # Bulk insert observations
                for obs in final_obs:
                    price_val = _parse_price(obs.get("price_read"))
                    await conn.execute(
                        """
                        INSERT INTO audit_observations (
                          id, audit_id, matched_sku_id, sku_guess_text,
                          brand_read, product_read, size_read, flavor_variant,
                          facings, shelf_position, legibility, object_type,
                          price_value, price_confidence,
                          field_confidence, status,
                          match_method, match_similarity, notes, org_id
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16,$17,$18,$19,$20)
                        """,
                        uuid4(), audit_id,
                        (obs["matched_sku_id"] if isinstance(obs["matched_sku_id"], UUID)
                         else UUID(str(obs["matched_sku_id"]))) if obs.get("matched_sku_id") else None,
                        obs.get("sku_guess_text"),
                        obs.get("brand_read"), obs.get("product_read"),
                        obs.get("size_read"), obs.get("flavor_variant"),
                        obs.get("facings"),
                        obs.get("shelf_position", "unknown"),
                        obs.get("legibility", "fully_readable"),
                        obs.get("object_type", "bottle"),
                        price_val, obs.get("price_confidence"),
                        json.dumps(obs.get("field_confidence", {})),
                        obs.get("obs_status", "confirmed"),
                        obs.get("match_method"), obs.get("match_similarity"),
                        obs.get("notes"), org_id,
                    )

        return {}

    async def _persist_terminal(self, state: PipelineState) -> dict:
        audit_id = state["audit_id"]
        status = state.get("terminal_status") or "processing_failed"
        quality_dict = state.get("quality") or {}
        
        # Merge VLM-rated quality scores into capture_quality
        vlm_result = state.get("vlm_result") or {}
        if vlm_result.get("image_quality_score"):
            quality_dict["vlm_image_quality_score"] = vlm_result["image_quality_score"]
        if vlm_result.get("extraction_confidence"):
            quality_dict["vlm_extraction_confidence"] = vlm_result["extraction_confidence"]
        if vlm_result.get("alcohol_type"):
            quality_dict["alcohol_type"] = vlm_result["alcohol_type"]
        
        events = state.get("events") or []

        async with self._db.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE shelf_audits SET status=$1, capture_quality=$2::jsonb WHERE id=$3",
                    status, json.dumps(quality_dict), audit_id,
                )
                for ev in events:
                    await conn.execute(
                        "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1,$2,$3::jsonb)",
                        audit_id, ev["event_type"], json.dumps(ev["payload"]),
                    )
        return {}

    async def _persist_rejected(self, state: PipelineState) -> dict:
        audit_id = state["audit_id"]
        quality_dict = state.get("quality") or {}
        gr_dict = state.get("guardrail") or {}
        storage_path = state["storage_path"]
        events = state.get("events") or []
        
        # Merge guardrail + VLM alcohol type into capture_quality
        if gr_dict.get("alcohol_type"):
            quality_dict["alcohol_type"] = gr_dict["alcohol_type"]
        if gr_dict.get("alcohol_confidence"):
            quality_dict["guardrail_alcohol_confidence"] = gr_dict["alcohol_confidence"]
        quality_dict["guardrail_verdict"] = gr_dict.get("verdict", "reject")
        quality_dict["rejection_reason"] = gr_dict.get("rejection_reason") or gr_dict.get("reason")

        import hashlib
        content_hash = quality_dict.get("content_hash") or hashlib.sha256(state["image_bytes"]).hexdigest()

        async with self._db.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE shelf_audits SET status='guardrail_rejected' WHERE id=$1",
                    audit_id,
                )
                for ev in events:
                    await conn.execute(
                        "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1,$2,$3::jsonb)",
                        audit_id, ev["event_type"], json.dumps(ev["payload"]),
                    )
                await conn.execute(
                    """
                    INSERT INTO guardrail_rejections
                      (org_id, captured_by, account_id, storage_path, content_hash,
                       category, clip_confidence, reason)
                    SELECT org_id, captured_by, account_id, $2, $3, $4, $5, $6
                    FROM shelf_audits WHERE id = $1
                    """,
                    audit_id, storage_path, content_hash,
                    gr_dict.get("category", "no_shelf"),
                    gr_dict.get("confidence", 0.0),
                    gr_dict.get("reason"),
                )
        return {}

    async def _store_entry_flow(self, state: PipelineState) -> dict:
        """Stub — Phase 9+ will add OCR for storefront signage."""
        audit_id = state["audit_id"]
        events = state.get("events") or []
        async with self._db.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE shelf_audits SET status='final', fixture_type='unknown' WHERE id=$1",
                    audit_id,
                )
                for ev in events:
                    await conn.execute(
                        "INSERT INTO audit_events (audit_id, event_type, payload) VALUES ($1,$2,$3::jsonb)",
                        audit_id, ev["event_type"], json.dumps(ev["payload"]),
                    )
        return {}


# ─── Routing functions ─────────────────────────────────────────────────────────

def _route_quality(state: PipelineState) -> str:
    return "persist_terminal" if state.get("terminal_status") else "guardrail"


def _route_guardrail(state: PipelineState) -> str:
    gr = state.get("guardrail") or {}

    # REJECT: instant stop, guardrail_rejected status
    if gr.get("verdict") == "reject":
        return "persist_rejected"

    # WARN: instant stop, retake_required (terminal_status set by guardrail_node)
    if gr.get("verdict") == "warn":
        return "persist_terminal"

    # STORE_ENTRY: special flow
    if gr.get("routing") == "store_entry":
        return "store_entry_flow"

    # PASS: continue to extraction
    return "vlm_extract"


def _route_vlm(state: PipelineState) -> str:
    return "persist_terminal" if state.get("error") else "rag_ground"


def _route_confidence(state: PipelineState) -> str:
    """
    After judge calibration, check confidence score:
    - >= 0.55: ACCEPT (persist_final — observations saved)
    - < 0.55: FLAG (persist_final with status='retake_required' — observations still saved)
    
    Observations are ALWAYS persisted so the UI can show extracted data
    even when the audit is flagged for retake.
    """
    vlm_dict = state.get("vlm_result") or {}
    confidence = vlm_dict.get("confidence_overall", 0.0)

    if confidence >= 0.55:
        print(f"[ROUTE] Confidence {confidence:.2f} >= 0.55 → ACCEPT (final)")
    else:
        print(f"[ROUTE] Confidence {confidence:.2f} < 0.55 → FLAG (retake_required — observations saved)")
    
    # Always route to persist_final so observations are saved
    return "persist_final"


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(price_str: str | None) -> float | None:
    """Parse price from various formats.
    Handles: "$19.99", "19.99 (on sale)", "€19,99", "19,99 EUR", etc.
    Returns float or None if unparseable.
    """
    if not price_str:
        return None

    try:
        text = str(price_str).strip()

        # Remove currency symbols, text in parens, and common words
        text = text.split("(")[0].strip()  # Remove "(on sale)" etc
        text = re.sub(r"[A-Z]{3}$|^[A-Z]{3}", "", text).strip()  # Remove "EUR", "USD" etc
        text = re.sub(r"[^\d.,\-]", "", text)  # Keep only digits, dots, commas, minus

        # Handle both US (19.99) and EU (19,99) formats
        # If it has both comma and dot, assume last one is decimal
        if "," in text and "." in text:
            last_comma = text.rfind(",")
            last_dot = text.rfind(".")
            if last_dot > last_comma:
                text = text.replace(",", "")  # US format: 1,234.99
            else:
                text = text.replace(".", "").replace(",", ".")  # EU format: 1.234,99
        elif "," in text:
            # Only comma - could be thousands or decimal separator
            # If comma is in last 3 positions, likely decimal (EU format)
            if len(text) - text.rfind(",") <= 3:
                text = text.replace(",", ".")  # EU: 19,99 → 19.99
            else:
                text = text.replace(",", "")  # US thousands: 1,234

        value = float(text)
        # Sanity check: prices should be 0.01 - 10000
        if 0.01 <= value <= 10000:
            return round(value, 2)
        return None
    except (ValueError, TypeError, AttributeError):
        return None
