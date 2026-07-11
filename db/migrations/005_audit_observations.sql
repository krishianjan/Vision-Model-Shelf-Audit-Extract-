CREATE TABLE IF NOT EXISTS audit_observations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id            UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
  matched_sku_id      UUID REFERENCES products(id),
  sku_guess_text      TEXT,
  brand_read          TEXT,
  size_read           TEXT,
  facings             INTEGER,
  shelf_position      TEXT,
  price_value         NUMERIC(10,2),
  price_confidence    NUMERIC(3,2),
  field_confidence    JSONB NOT NULL DEFAULT '{}'::JSONB,
  status              TEXT NOT NULL,
  match_method        TEXT CHECK (match_method IN ('exact','fuzzy','embedding','unresolved')),
  match_similarity    NUMERIC(4,3),
  notes               TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_obs_audit ON audit_observations(audit_id);
CREATE INDEX IF NOT EXISTS idx_obs_sku
  ON audit_observations(matched_sku_id) WHERE matched_sku_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_obs_status ON audit_observations(status);
CREATE INDEX IF NOT EXISTS idx_obs_unmatched
  ON audit_observations(brand_read) WHERE matched_sku_id IS NULL;
