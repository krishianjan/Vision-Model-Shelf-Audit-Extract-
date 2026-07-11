CREATE TABLE IF NOT EXISTS shelf_audits (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id         UUID NOT NULL REFERENCES accounts(id),
  org_id             UUID NOT NULL,
  captured_by        UUID NOT NULL,
  captured_at        TIMESTAMPTZ NOT NULL,
  received_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fixture_type       TEXT CHECK (fixture_type IN ('gondola','cooler','endcap','floor_display','unknown')),
  capture_quality    JSONB,
  status             TEXT NOT NULL CHECK (status IN (
                       'processing','final','retake_required','guardrail_rejected',
                       'processing_failed','superseded'
                     )),
  version            INTEGER NOT NULL DEFAULT 1,
  superseded_by      UUID REFERENCES shelf_audits(id),
  model_version      TEXT,
  latency_ms         INTEGER,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audits_account_current
  ON shelf_audits(account_id, captured_at DESC)
  WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_audits_org ON shelf_audits(org_id);
CREATE INDEX IF NOT EXISTS idx_audits_status ON shelf_audits(status);
CREATE INDEX IF NOT EXISTS idx_audits_superseded ON shelf_audits(superseded_by);
