ALTER TABLE shelf_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- RLS policies below use auth.uid() / auth.jwt() which are Supabase-provided functions.
-- On local Docker Postgres these are skipped; apply via Supabase dashboard or supabase CLI.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth') THEN

    EXECUTE 'DROP POLICY IF EXISTS audit_rep_read ON shelf_audits';
    EXECUTE 'DROP POLICY IF EXISTS audit_rep_write ON shelf_audits';
    EXECUTE 'DROP POLICY IF EXISTS obs_via_audit ON audit_observations';
    EXECUTE 'DROP POLICY IF EXISTS images_via_audit ON audit_images';
    EXECUTE 'DROP POLICY IF EXISTS events_via_audit ON audit_events';

    EXECUTE $pol$
      CREATE POLICY audit_rep_read ON shelf_audits FOR SELECT
        USING (captured_by = auth.uid() OR org_id = (auth.jwt() ->> 'org_id')::UUID)
    $pol$;

    EXECUTE $pol$
      CREATE POLICY audit_rep_write ON shelf_audits FOR INSERT
        WITH CHECK (captured_by = auth.uid())
    $pol$;

    EXECUTE $pol$
      CREATE POLICY obs_via_audit ON audit_observations FOR SELECT
        USING (EXISTS (
          SELECT 1 FROM shelf_audits a
          WHERE a.id = audit_observations.audit_id
            AND (a.captured_by = auth.uid() OR a.org_id = (auth.jwt() ->> 'org_id')::UUID)
        ))
    $pol$;

    EXECUTE $pol$
      CREATE POLICY images_via_audit ON audit_images FOR SELECT
        USING (EXISTS (
          SELECT 1 FROM shelf_audits a
          WHERE a.id = audit_images.audit_id
            AND (a.captured_by = auth.uid() OR a.org_id = (auth.jwt() ->> 'org_id')::UUID)
        ))
    $pol$;

    EXECUTE $pol$
      CREATE POLICY events_via_audit ON audit_events FOR SELECT
        USING (EXISTS (
          SELECT 1 FROM shelf_audits a
          WHERE a.id = audit_events.audit_id
            AND (a.captured_by = auth.uid() OR a.org_id = (auth.jwt() ->> 'org_id')::UUID)
        ))
    $pol$;

    RAISE NOTICE 'RLS policies applied (Supabase environment)';
  ELSE
    RAISE NOTICE 'auth schema not found — skipping RLS policies (local dev). Apply on Supabase.';
  END IF;
END $$;
