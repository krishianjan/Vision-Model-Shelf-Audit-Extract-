import asyncio
import gc
import json
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile

from src.auth import AuthUser, get_current_user
from src.models.audit import AuditCreateResponse, AuditDetail, AuditSummaryList

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("", response_model=AuditCreateResponse, status_code=202)
async def create_audit(
    request: Request,
    background: BackgroundTasks,
    image: UploadFile = File(...),
    account_id: UUID = Form(...),
    captured_at: datetime = Form(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    user: AuthUser = Depends(get_current_user),
):
    image_bytes = await image.read()
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 15MB)")

    audit_id = uuid4()
    db = request.app.state.db
    storage = request.app.state.storage
    agent = request.app.state.agent

    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO shelf_audits
                  (id, account_id, org_id, captured_by, captured_at, status, version)
                VALUES ($1, $2, $3, $4, $5, 'processing', 1)
                """,
                audit_id, account_id, user.org_id, user.user_id, captured_at,
            )

    storage_path = await storage.upload_original(audit_id, account_id, image_bytes)

    initial_state = {
        "audit_id": audit_id,
        "account_id": account_id,
        "org_id": user.org_id,
        "captured_by": user.user_id,
        "image_bytes": image_bytes,
        "storage_path": storage_path,
        "processed_bytes": None,
        "quality": None,
        "guardrail": None,
        "vlm_result": None,
        "match_results": None,
        "judge_result": None,
        "final_observations": None,
        "terminal_status": None,
        "error": None,
        "events": [{"event_type": "created", "payload": {"lat": latitude, "lng": longitude}}],
    }

    db_pool = db  # Capture DB pool in closure for background task

    # Wrap agent invocation with error handling for stuck audits
    async def run_audit_safe(state):
        """Background task wrapper with comprehensive error handling + memory management.

        CRITICAL: Catches ALL exceptions and ensures audit status is persisted.
        If agent.ainvoke() doesn't complete, mark as failed immediately.
        """
        t0 = asyncio.get_event_loop().time()
        try:
            print(f"[INFO] Starting pipeline for audit {audit_id}")
            # Pipeline with generous timeout (280s, leaves 20s for DB persist)
            result = await asyncio.wait_for(agent.ainvoke(state), timeout=280.0)
            t_elapsed = asyncio.get_event_loop().time() - t0
            print(f"[INFO] Pipeline completed for audit {audit_id} in {t_elapsed:.1f}s")

            # Verify terminal_status was set (if not, pipeline stalled)
            if not result.get("terminal_status"):
                print(f"[WARN] Audit {audit_id} completed but no terminal_status set")
                await mark_audit_failed(audit_id, "Pipeline stalled: no terminal_status")

        except asyncio.TimeoutError:
            t_elapsed = asyncio.get_event_loop().time() - t0
            error_msg = f"Pipeline timeout: processing exceeded 280 seconds ({t_elapsed:.1f}s elapsed)"
            print(f"[ERROR] Audit {audit_id}: {error_msg}")
            await mark_audit_failed(audit_id, error_msg)

        except Exception as e:
            t_elapsed = asyncio.get_event_loop().time() - t0
            error_msg = f"Pipeline crashed: {type(e).__name__}: {str(e)[:200]} ({t_elapsed:.1f}s elapsed)"
            print(f"[ERROR] Audit {audit_id}: {error_msg}")
            await mark_audit_failed(audit_id, error_msg)

        finally:
            # CRITICAL: Aggressively free memory after each audit
            # This prevents accumulation of image bytes + model caches
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    print(f"[MEM] CUDA cache cleared for audit {audit_id}")
            except Exception as mem_err:
                print(f"[WARN] CUDA cache clear failed: {mem_err}")

            gc.collect()
            print(f"[MEM] Garbage collection triggered for audit {audit_id}")

    async def mark_audit_failed(aid: str, reason: str) -> None:
        """Mark audit as processing_failed with detailed error reason.

        CRITICAL: This MUST succeed. Retries once if connection fails.
        """
        reason_str = str(reason) if not isinstance(reason, str) else reason

        for attempt in range(2):  # Retry once on failure
            try:
                # Short timeout (5s) for DB operations
                async with asyncio.timeout(5.0):
                    async with db_pool.acquire() as conn:
                        async with conn.transaction():
                            # Update audit status with error details
                            await conn.execute(
                                """UPDATE shelf_audits
                                   SET status=$2, capture_quality=$3::jsonb
                                   WHERE id=$1""",
                                aid,
                                "processing_failed",
                                json.dumps({
                                    "error": reason_str,
                                    "error_time": str(datetime.utcnow()),
                                    "pipeline_failed": True
                                }),
                            )
                            # Log error event for audit trail
                            await conn.execute(
                                """INSERT INTO audit_events (audit_id, event_type, payload)
                                   VALUES ($1, $2, $3::jsonb)""",
                                aid,
                                "pipeline_crash",
                                json.dumps({"error": reason_str, "terminal": True}),
                            )
                print(f"[INFO] Logged audit failure for {aid} on attempt {attempt + 1}")
                return  # Success, exit

            except asyncio.TimeoutError:
                print(f"[WARN] DB operation timeout for audit {aid}, attempt {attempt + 1}/2")
                if attempt == 1:  # Last attempt failed
                    print(f"[CRITICAL] Failed to log audit failure for {aid} (DB timeout)")
                else:
                    await asyncio.sleep(0.5)  # Brief wait before retry

            except Exception as db_error:
                print(f"[WARN] DB error logging audit failure for {aid}, attempt {attempt + 1}/2: {db_error}")
                if attempt == 1:  # Last attempt failed
                    print(f"[CRITICAL] Failed to log audit failure for {aid}: {db_error}")
                else:
                    await asyncio.sleep(0.5)  # Brief wait before retry

    background.add_task(run_audit_safe, initial_state)
    return AuditCreateResponse(audit_id=audit_id, status="processing")


@router.get("", response_model=list[AuditSummaryList])
async def list_audits(
    request: Request,
    account_id: UUID | None = None,
    limit: int = 20,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        query = """
            SELECT sa.*, ac.name AS account_name
            FROM shelf_audits sa
            LEFT JOIN accounts ac ON ac.id = sa.account_id
            WHERE (sa.captured_by = $1 OR sa.org_id = $2) AND sa.superseded_by IS NULL
        """
        params: list = [user.user_id, user.org_id]
        if account_id:
            params.append(account_id)
            query += f" AND sa.account_id = ${len(params)}"
        params.append(limit)
        query += f" ORDER BY sa.captured_at DESC LIMIT ${len(params)}"
        rows = await conn.fetch(query, *params)
    return [AuditSummaryList(**dict(r)) for r in rows]


@router.get("/{audit_id}", response_model=AuditDetail)
async def get_audit_detail(
    request: Request,
    audit_id: UUID,
    user: AuthUser = Depends(get_current_user),
):
    """Get full audit detail with observations and images."""
    db = request.app.state.db
    async with db.acquire() as conn:
        audit = await conn.fetchrow(
            """SELECT sa.*, ac.name AS account_name
               FROM shelf_audits sa
               LEFT JOIN accounts ac ON ac.id = sa.account_id
               WHERE sa.id = $1 AND (sa.captured_by = $2 OR sa.org_id = $3)
               AND sa.superseded_by IS NULL""",
            audit_id, user.user_id, user.org_id,
        )
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")

        obs = await conn.fetch(
            "SELECT * FROM audit_observations WHERE audit_id=$1 ORDER BY created_at",
            audit_id,
        )
        images = await conn.fetch(
            "SELECT * FROM audit_images WHERE audit_id=$1 ORDER BY created_at",
            audit_id,
        )

    # Parse capture_quality from JSON string to dict if needed
    audit_dict = dict(audit)
    if isinstance(audit_dict.get("capture_quality"), str):
        import json
        try:
            audit_dict["capture_quality"] = json.loads(audit_dict["capture_quality"])
        except:
            audit_dict["capture_quality"] = None

    return AuditDetail.compose(audit_dict, obs, images)


@router.delete("/{audit_id}")
async def delete_audit(
    request: Request,
    audit_id: UUID,
    force: bool = False,
    user: AuthUser = Depends(get_current_user),
):
    """
    Delete an audit. Free space + tokens.
    - WITHOUT force: only deletes if status='processing' (stuck) or 'failed' (failed/crashed)
    - WITH force=true: deletes ANY status (final, retake_required, etc.)
    - Cascades: audit_observations, audit_images, audit_events deleted automatically
    - Safe: Foreign keys ensure no orphans; org-scoped
    """
    db = request.app.state.db
    async with db.acquire() as conn:
        async with conn.transaction():
            audit = await conn.fetchrow(
                """SELECT sa.id, sa.status, sa.org_id
                   FROM shelf_audits sa
                   WHERE sa.id = $1 AND sa.org_id = $2""",
                audit_id, user.org_id
            )

            if not audit:
                raise HTTPException(status_code=404, detail="Audit not found")

            # Without force: only allow stuck/failed deletion
            if not force and audit["status"] not in ("processing", "processing_failed", "guardrail_rejected"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete final audits without ?force=true. This audit is '{audit['status']}'"
                )

            # Delete cascade handles: audit_observations, audit_images, audit_events
            await conn.execute(
                "DELETE FROM shelf_audits WHERE id = $1",
                audit_id,
            )

    return {
        "status": "deleted",
        "audit_id": str(audit_id),
        "previous_status": audit["status"],
        "message": f"Audit deleted (freed tokens, storage, DB rows). Use ?force=true to override."
    }


@router.post("/{audit_id}/cancel")
async def cancel_audit_processing(
    request: Request,
    audit_id: UUID,
    user: AuthUser = Depends(get_current_user),
):
    """
    Stop a stuck processing audit without deleting it.
    Marks status='processing_failed' so it leaves the 'processing' queue.
    Useful when background task is stuck or hung.
    """
    db = request.app.state.db
    async with db.acquire() as conn:
        async with conn.transaction():
            audit = await conn.fetchrow(
                """SELECT id, status FROM shelf_audits
                   WHERE id = $1 AND org_id = $2""",
                audit_id, user.org_id,
            )

            if not audit:
                raise HTTPException(status_code=404, detail="Audit not found")

            if audit["status"] != "processing":
                raise HTTPException(
                    status_code=400,
                    detail=f"Audit is not processing (status='{audit['status']}'). Use DELETE to remove."
                )

            await conn.execute(
                """UPDATE shelf_audits SET status='processing_failed',
                   capture_quality = COALESCE(capture_quality, '{}'::jsonb) ||
                                       '{"cancelled_by_user": true}'::jsonb
                   WHERE id = $1""",
                audit_id,
            )

    return {
        "status": "cancelled",
        "audit_id": str(audit_id),
        "message": "Processing stopped. Background task will exit on next event."
    }


@router.get("/{audit_id}/debug")
async def get_audit_debug(
    request: Request,
    audit_id: UUID,
    user: AuthUser = Depends(get_current_user),
):
    """Return raw pipeline events and full audit JSON for debugging/export."""
    db = request.app.state.db
    async with db.acquire() as conn:
        audit = await conn.fetchrow(
            """SELECT * FROM shelf_audits WHERE id = $1 AND org_id = $2""",
            audit_id, user.org_id,
        )
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")

        obs = await conn.fetch(
            "SELECT * FROM audit_observations WHERE audit_id = $1 ORDER BY created_at",
            audit_id,
        )
        events = await conn.fetch(
            "SELECT event_type, payload, created_at FROM audit_events WHERE audit_id = $1 ORDER BY created_at",
            audit_id,
        )

    def safe_json(d):
        if isinstance(d, str):
            try:
                return json.loads(d)
            except:
                return d
        return d

    return {
        "audit": safe_json(dict(audit)),
        "observations": [dict(o) for o in obs],
        "events": [
            {
                "event_type": e["event_type"],
                "payload": safe_json(e["payload"]),
                "timestamp": e["created_at"].isoformat() if e["created_at"] else None,
            }
            for e in events
        ],
    }
