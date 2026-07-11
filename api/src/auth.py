from dataclasses import dataclass
from uuid import UUID
import os

import jwt
from fastapi import Header, HTTPException


@dataclass
class AuthUser:
    user_id: UUID
    org_id: UUID
    email: str


async def get_current_user(authorization: str = Header(...)) -> AuthUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        claims = jwt.decode(
            token,
            os.environ["SUPABASE_JWT_SECRET"],
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")
    return AuthUser(
        user_id=UUID(claims["sub"]),
        org_id=UUID(claims.get("org_id") or claims["sub"]),
        email=claims.get("email", ""),
    )
