CREATE TABLE IF NOT EXISTS store_entry_captures (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id      UUID REFERENCES accounts(id),
  org_id          UUID NOT NULL,
  captured_by     UUID NOT NULL,
  storage_path    TEXT NOT NULL,
  ocr_store_name  TEXT,
  ocr_confidence  NUMERIC(3,2),
  latitude        DOUBLE PRECISION,
  longitude       DOUBLE PRECISION,
  captured_at     TIMESTAMPTZ NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
