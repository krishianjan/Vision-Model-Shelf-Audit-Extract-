"""
Storage backend — switchable via USE_LOCAL_STORAGE env var.

USE_LOCAL_STORAGE=1  → writes to api/uploads/ on disk (local dev, no Supabase needed)
USE_LOCAL_STORAGE=0  → Supabase Storage (production default)

Both backends return the same path string and store it in audit_images.storage_path.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


class StorageClient:
    def __init__(self):
        self._use_local = os.environ.get("USE_LOCAL_STORAGE", "0") == "1"

        if self._use_local:
            self._base = Path(os.environ.get("LOCAL_UPLOAD_DIR", "uploads")).resolve()
            self._base.mkdir(parents=True, exist_ok=True)
            (self._base / "rejected").mkdir(exist_ok=True)
        else:
            from supabase import create_client
            self._client = create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )
            self.audits_bucket = os.environ.get("STORAGE_BUCKET_AUDITS", "audits")
            self.rejected_bucket = os.environ.get("STORAGE_BUCKET_REJECTED", "rejected")

    def _day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def upload_original(self, audit_id: UUID, account_id: UUID, data: bytes) -> str:
        path = f"{self._day()}/{account_id}/{audit_id}/original.jpg"
        if self._use_local:
            dest = self._base / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        else:
            self._client.storage.from_(self.audits_bucket).upload(
                path, data, {"content-type": "image/jpeg", "upsert": "true"}
            )
        return path

    async def upload_preview(self, audit_id: UUID, account_id: UUID, data: bytes) -> str:
        path = f"{self._day()}/{account_id}/{audit_id}/preview_1024.jpg"
        if self._use_local:
            dest = self._base / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        else:
            self._client.storage.from_(self.audits_bucket).upload(
                path, data, {"content-type": "image/jpeg", "upsert": "true"}
            )
        return path

    async def upload_rejected(self, rejection_id: UUID, data: bytes) -> str:
        path = f"rejected/{self._day()}/{rejection_id}.jpg"
        if self._use_local:
            dest = self._base / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        else:
            self._client.storage.from_(self.rejected_bucket).upload(
                path, data, {"content-type": "image/jpeg", "upsert": "true"}
            )
        return path

    def get_public_url(self, bucket: str, path: str) -> str:
        if self._use_local:
            base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
            return f"{base_url}/uploads/{path}"
        return self._client.storage.from_(bucket).get_public_url(path)
