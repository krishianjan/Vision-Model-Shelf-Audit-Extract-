"""
Local auth endpoint — issues JWTs without Supabase.
Used for local dev and mobile testing when Supabase is not configured.
"""
from __future__ import annotations

import os
import time
from uuid import uuid5, UUID, NAMESPACE_URL

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

# Hardcoded dev users — in production this would be a real user table
_DEV_USERS = {
    "rep@kosha.ai": {
        "password": "test123",
        "user_id": "00000000-0000-0000-0000-000000000099",
        "org_id": "00000000-0000-0000-0000-000000000001",
        "name": "Field Rep",
    },
    "manager@kosha.ai": {
        "password": "test123",
        "user_id": "00000000-0000-0000-0000-000000000098",
        "org_id": "00000000-0000-0000-0000-000000000001",
        "name": "Manager",
    },
    "rep2@kosha.ai": {
        "password": "test123",
        "user_id": "00000000-0000-0000-0000-000000000097",
        "org_id": "00000000-0000-0000-0000-000000000001",
        "name": "Rep 2",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str
    email: str
    name: str


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = _DEV_USERS.get(body.email.strip().lower())
    if not user or user["password"] != body.password:
        raise HTTPException(401, "Invalid email or password")

    secret = os.environ.get("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-at-least-32-characters")

    payload = {
        "sub": user["user_id"],
        "org_id": user["org_id"],
        "email": body.email,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 24 * 30,  # 30 days
    }

    token = jwt.encode(payload, secret, algorithm="HS256")

    return TokenResponse(
        access_token=token,
        user_id=user["user_id"],
        org_id=user["org_id"],
        email=body.email,
        name=user["name"],
    )


@router.get("/me")
async def me(authorization: str = "") -> dict:
    """Quick health check for auth — returns user info from token."""
    from src.auth import get_current_user
    from fastapi import Header
    try:
        user = await get_current_user(authorization)
        return {"user_id": str(user.user_id), "org_id": str(user.org_id), "email": user.email}
    except Exception as e:
        raise HTTPException(401, str(e))
