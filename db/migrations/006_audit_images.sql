CREATE TABLE IF NOT EXISTS audit_images (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id      UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
  storage_path  TEXT NOT NULL,
  preview_path  TEXT,
  content_hash  TEXT NOT NULL,
  width_px      INTEGER,
  height_px     INTEGER,
  size_bytes    INTEGER,
  quality_score NUMERIC(3,2),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_images_audit ON audit_images(audit_id);
CREATE INDEX IF NOT EXISTS idx_images_hash ON audit_images(content_hash);
