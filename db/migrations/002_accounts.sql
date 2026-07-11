CREATE TABLE IF NOT EXISTS accounts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL,
  name          TEXT NOT NULL,
  chain         TEXT,
  channel_type  TEXT CHECK (channel_type IN ('liquor','grocery','convenience','bigbox')),
  address       TEXT,
  latitude      DOUBLE PRECISION,
  longitude     DOUBLE PRECISION,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_org ON accounts(org_id);
CREATE INDEX IF NOT EXISTS idx_accounts_name_trgm ON accounts USING gin (name gin_trgm_ops);
