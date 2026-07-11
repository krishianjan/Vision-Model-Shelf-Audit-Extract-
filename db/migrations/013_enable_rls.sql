-- Migration 013: Enable RLS on sensitive tables
-- Restricts data access by organization

-- Enable RLS on accounts table
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see accounts in their organization
-- Note: Adjust based on your actual auth schema
-- Assuming: auth.jwt() returns org_id claim
DROP POLICY IF EXISTS accounts_org_policy ON accounts;
CREATE POLICY accounts_org_policy ON accounts
  FOR ALL
  USING (org_id = current_setting('app.current_org_id')::uuid);

-- Enable RLS on products table
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Policy: Products visible to org if used in org's audits
DROP POLICY IF EXISTS products_org_policy ON products;
CREATE POLICY products_org_policy ON products
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM audit_observations ao
      WHERE ao.matched_sku_id = products.id
        AND ao.org_id = current_setting('app.current_org_id')::uuid
    )
  );

-- Enable RLS on guardrail_rejections table
ALTER TABLE guardrail_rejections ENABLE ROW LEVEL SECURITY;

-- Policy: Rejections visible only to org that owns the audit
DROP POLICY IF EXISTS guardrail_org_policy ON guardrail_rejections;
CREATE POLICY guardrail_org_policy ON guardrail_rejections
  FOR SELECT
  USING (
    audit_id IN (
      SELECT id FROM shelf_audits
      WHERE org_id = current_setting('app.current_org_id')::uuid
    )
  );

-- Grant necessary permissions
-- Note: Adjust based on your actual role setup
GRANT SELECT, INSERT, UPDATE ON accounts TO authenticated;
GRANT SELECT ON products TO authenticated;
GRANT SELECT ON guardrail_rejections TO authenticated;
