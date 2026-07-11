from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import AuthUser, get_current_user
from src.models.account import AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM accounts WHERE org_id = $1 ORDER BY name",
            user.org_id,
        )
    return [AccountOut(**dict(r)) for r in rows]


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: UUID,
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    db = request.app.state.db
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM accounts WHERE id = $1 AND org_id = $2",
            account_id, user.org_id,
        )
    if not row:
        raise HTTPException(404, "Account not found")
    return AccountOut(**dict(row))
