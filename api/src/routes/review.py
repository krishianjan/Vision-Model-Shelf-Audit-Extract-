from fastapi import APIRouter, Depends, Request
from src.auth import AuthUser, get_current_user

router = APIRouter(prefix="/review", tags=["review"])


@router.get("")
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
            ORDER BY rq.min_confidence ASC, rq.captured_at DESC
            LIMIT $3
            """,
            user.user_id, user.org_id, limit,
        )
    return [dict(r) for r in rows]
