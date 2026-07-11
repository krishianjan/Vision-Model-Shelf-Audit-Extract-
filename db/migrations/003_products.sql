CREATE TABLE IF NOT EXISTS products (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand         TEXT NOT NULL,
  product_name  TEXT NOT NULL,
  size_ml       INTEGER,
  pack_count    INTEGER DEFAULT 1,
  category      TEXT CHECK (category IN ('vodka','whiskey','tequila','rum','gin','wine','beer','rtd','liqueur','other')),
  upc           TEXT UNIQUE,
  embedding     VECTOR(384),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_brand_trgm ON products USING gin (brand gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_embedding
  ON products USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
