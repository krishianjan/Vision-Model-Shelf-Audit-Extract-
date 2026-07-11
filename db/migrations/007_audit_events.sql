CREATE TABLE IF NOT EXISTS audit_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id     UUID NOT NULL REFERENCES shelf_audits(id) ON DELETE CASCADE,
  event_type   TEXT NOT NULL CHECK (event_type IN (
                 'created','quality_check_pass','quality_check_fail',
                 'guardrail_pass','guardrail_reject',
                 'vlm_raw_output','vlm_fallback','vlm_failed',
                 'rag_matched','judge_adjusted',
                 'flagged_for_review','human_confirmed',
                 'rescored','superseded'
               )),
  payload      JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_audit ON audit_events(audit_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON audit_events(event_type);
