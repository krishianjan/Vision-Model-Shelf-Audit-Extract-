from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class AccountOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    chain: str | None
    channel_type: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
