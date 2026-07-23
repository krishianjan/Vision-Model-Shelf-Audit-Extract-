-- Migration 014: Add visual cue columns to audit_observations
-- These survive when label text is unreadable — visual brand recognition fallback
-- Also adds visual brand columns to products for future visual matching

ALTER TABLE audit_observations
  ADD COLUMN IF NOT EXISTS bottle_shape          TEXT,
  ADD COLUMN IF NOT EXISTS glass_tint            TEXT,
  ADD COLUMN IF NOT EXISTS cap_type              TEXT,
  ADD COLUMN IF NOT EXISTS label_color           TEXT,
  ADD COLUMN IF NOT EXISTS label_design          TEXT,
  ADD COLUMN IF NOT EXISTS damage_flags          TEXT,
  ADD COLUMN IF NOT EXISTS visual_brand_guess     TEXT,
  ADD COLUMN IF NOT EXISTS visual_brand_confidence NUMERIC(3,2) DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS stock_level           TEXT,
  ADD COLUMN IF NOT EXISTS alcohol_subcategory   TEXT;

-- Index for filtering by visual brand guess (unmatched obs with visual clue)
CREATE INDEX IF NOT EXISTS idx_obs_visual_brand
  ON audit_observations(visual_brand_guess) WHERE visual_brand_guess IS NOT NULL;

-- Index for stock level queries
CREATE INDEX IF NOT EXISTS idx_obs_stock_level ON audit_observations(stock_level);

-- Add visual reference columns to products (for future visual matching)
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS bottle_shape    TEXT,
  ADD COLUMN IF NOT EXISTS glass_tint      TEXT,
  ADD COLUMN IF NOT EXISTS cap_type        TEXT,
  ADD COLUMN IF NOT EXISTS label_color     TEXT,
  ADD COLUMN IF NOT EXISTS label_design    TEXT,
  ADD COLUMN IF NOT EXISTS alcohol_subcategory TEXT;
