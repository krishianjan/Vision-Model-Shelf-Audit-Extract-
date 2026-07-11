import { useEffect, useState, forwardRef, useImperativeHandle } from "react";
import { getAudits, getDashboard } from "../api";

const STATUS_COLOR: Record<string, string> = {
  final: "#16a34a", processing: "#d97706",
  retake_required: "#dc2626", guardrail_rejected: "#6b7280", processing_failed: "#dc2626",
};

const Audits = forwardRef<{ refresh: () => void }, { onSelect: (id: string) => void }>(({ onSelect }, ref) => {
  const [audits, setAudits] = useState<any[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function doRefresh() {
    setLoading(true);
    Promise.all([getAudits(), getDashboard()])
      .then(([a, d]) => { setAudits(a); setDashboard(d); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  useImperativeHandle(ref, () => ({ refresh: doRefresh }), []);

  useEffect(() => {
    doRefresh();
  }, []);

  if (loading) return <div style={styles.center}><div style={styles.spinner} /></div>;
  if (error) return <div style={styles.error}>⚠️ {error}</div>;

  return (
    <div>
      {/* Dashboard summary cards */}
      {dashboard && (
        <div style={styles.statsRow}>
          {[
            { label: "Stores Visited", value: dashboard.summary?.stores_visited ?? 0, color: "#3b82f6" },
            { label: "Total Audits", value: dashboard.summary?.total_audits ?? 0, color: "#8b5cf6" },
            { label: "Completed", value: dashboard.summary?.completed_audits ?? 0, color: "#16a34a" },
            { label: "Avg Quality", value: `${Math.round((dashboard.summary?.avg_quality_score ?? 0) * 100)}%`, color: "#f59e0b" },
            { label: "Pending Review", value: dashboard.summary?.pending_review_count ?? 0, color: "#dc2626" },
          ].map(s => (
            <div key={s.label} style={styles.statCard}>
              <div style={{ ...styles.statValue, color: s.color }}>{s.value}</div>
              <div style={styles.statLabel}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Audit list */}
      <div style={styles.sectionHeader}>
        <h2 style={styles.sectionTitle}>Recent Audits</h2>
        <span style={styles.sectionCount}>{audits.length} audits</span>
      </div>

      {audits.length === 0 && (
        <div style={styles.empty}>No audits yet. Go to Capture to upload your first shelf photo.</div>
      )}

      {audits.map(a => (
        <div key={a.id} style={styles.card} onClick={() => onSelect(a.id)}>
          <div style={styles.cardRow}>
            <div style={styles.cardLeft}>
              <div style={styles.storeName}>{a.account_name ?? a.account_id?.slice(0, 8)}</div>
              <div style={styles.cardMeta}>
                {new Date(a.captured_at).toLocaleString()} · v{a.version}
                {a.fixture_type ? ` · ${a.fixture_type}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ ...styles.badge, background: STATUS_COLOR[a.status] ?? "#6b7280" }}>
                {a.status.replace(/_/g, " ")}
              </span>
              <span style={styles.arrow}>›</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
});

Audits.displayName = "Audits";

export default Audits;

const styles: Record<string, React.CSSProperties> = {
  center: { display: "flex", justifyContent: "center", padding: 60 },
  spinner: { width: 36, height: 36, border: "3px solid #e2e8f0", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.8s linear infinite" },
  error: { background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626", padding: 16, borderRadius: 12 },
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12, marginBottom: 28 },
  statCard: { background: "#fff", borderRadius: 14, padding: "18px 16px", textAlign: "center", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", border: "1px solid #e2e8f0" },
  statValue: { fontSize: 26, fontWeight: 800, marginBottom: 4 },
  statLabel: { fontSize: 12, color: "#94a3b8", fontWeight: 500 },
  sectionHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: 700, color: "#0f172a" },
  sectionCount: { fontSize: 13, color: "#94a3b8" },
  empty: { textAlign: "center", color: "#94a3b8", padding: "48px 0", fontSize: 15 },
  card: { background: "#fff", borderRadius: 14, padding: "16px 18px", marginBottom: 10, cursor: "pointer", border: "1px solid #e2e8f0", boxShadow: "0 1px 4px rgba(0,0,0,0.05)", transition: "box-shadow 0.2s" },
  cardRow: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  cardLeft: { flex: 1 },
  storeName: { fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 4 },
  cardMeta: { fontSize: 12, color: "#94a3b8" },
  badge: { color: "#fff", fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20 },
  arrow: { color: "#94a3b8", fontSize: 22 },
};
