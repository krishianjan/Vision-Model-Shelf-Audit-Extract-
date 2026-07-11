CREATE TABLE IF NOT EXISTS guardrail_rejections (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL,
  captured_by     UUID NOT NULL,
  account_id      UUID REFERENCES accounts(id),
  storage_path    TEXT NOT NULL,
  content_hash    TEXT,
  category        TEXT NOT NULL,
  clip_confidence NUMERIC(4,3),
  reason          TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rejections_captured_by
  ON guardrail_rejections(captured_by, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rejections_category ON guardrail_rejections(category);
