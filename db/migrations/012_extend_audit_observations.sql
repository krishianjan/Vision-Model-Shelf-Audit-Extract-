-- Migration 012: Extend audit_observations with product fields + org_id
-- Adds: product_read, flavor_variant, legibility, object_type, org_id
-- Validation moved to Python (Pydantic) - no DB CHECK constraints

ALTER TABLE audit_observations
  ADD COLUMN IF NOT EXISTS product_read TEXT,
  ADD COLUMN IF NOT EXISTS flavor_variant TEXT,
  ADD COLUMN IF NOT EXISTS legibility TEXT DEFAULT 'fully_readable',
  ADD COLUMN IF NOT EXISTS object_type TEXT DEFAULT 'bottle',
  ADD COLUMN IF NOT EXISTS org_id UUID;

-- Create index on org_id for multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_obs_org ON audit_observations(org_id);
CREATE INDEX IF NOT EXISTS idx_obs_flavor ON audit_observations(flavor_variant);
CREATE INDEX IF NOT EXISTS idx_obs_legibility ON audit_observations(legibility);
CREATE INDEX IF NOT EXISTS idx_obs_object_type ON audit_observations(object_type);
