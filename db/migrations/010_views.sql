CREATE OR REPLACE VIEW review_queue AS
SELECT
  o.id AS observation_id,
  o.audit_id,
  a.account_id,
  a.captured_by,
  o.brand_read,
  o.sku_guess_text,
  o.status,
  o.field_confidence,
  LEAST(
    COALESCE((o.field_confidence->>'sku')::NUMERIC, 1.0),
    COALESCE((o.field_confidence->>'facings')::NUMERIC, 1.0),
    COALESCE((o.field_confidence->>'price')::NUMERIC, 1.0)
  ) AS min_confidence,
  a.captured_at
FROM audit_observations o
JOIN shelf_audits a ON a.id = o.audit_id
WHERE a.superseded_by IS NULL
  AND (
    o.status IN ('low_confidence','unmatched','partial')
    OR LEAST(
      COALESCE((o.field_confidence->>'sku')::NUMERIC, 1.0),
      COALESCE((o.field_confidence->>'facings')::NUMERIC, 1.0)
    ) < 0.8
  );
