import { useEffect, useState } from "react";
import { getAudit } from "../api";

const CONF_COLOR = (v: number) => v >= 0.8 ? "#16a34a" : v >= 0.6 ? "#d97706" : "#dc2626";
const CONF_BG   = (v: number) => v >= 0.8 ? "#f0fdf4" : v >= 0.6 ? "#fffbeb" : "#fef2f2";

const STATUS_COLOR: Record<string, string> = {
  final: "#16a34a", processing: "#d97706",
  retake_required: "#dc2626", guardrail_rejected: "#6b7280", processing_failed: "#dc2626",
};

export default function AuditDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const [audit, setAudit] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const poll = async () => {
      try {
        const d = await getAudit(id);
        setAudit(d);
        if (d.status === "processing") {
          setTimeout(poll, 3000);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    poll();
  }, [id]);

  if (loading) return (
    <div style={styles.center}>
      <div style={styles.spinner} />
      <div style={styles.loadingText}>Loading audit…</div>
    </div>
  );
  if (error) return <div style={styles.errBox}>⚠️ {error} <button onClick={onBack} style={styles.backBtn}>← Back</button></div>;
  if (!audit) return null;

  const quality = audit.capture_quality ?? {};
  const obs: any[] = audit.observations ?? [];

  return (
    <div style={styles.page}>
      {/* Back */}
      <button onClick={onBack} style={styles.backBtn}>← Back to Audits</button>

      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.storeName}>{audit.account_name ?? "Unknown Store"}</h1>
          <div style={styles.meta}>
            {new Date(audit.captured_at).toLocaleString()}
            {audit.model_version ? ` · ${audit.model_version}` : ""}
            {audit.latency_ms ? ` · ${(audit.latency_ms / 1000).toFixed(1)}s` : ""}
          </div>
        </div>
        <span style={{ ...styles.statusBadge, background: STATUS_COLOR[audit.status] ?? "#6b7280" }}>
          {audit.status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Summary chips */}
      <div style={styles.chips}>
        {[
          { label: "SKUs Found", value: audit.summary?.total_observations ?? 0, color: "#3b82f6" },
          { label: "Confirmed", value: audit.summary?.confirmed ?? 0, color: "#16a34a" },
          { label: "Unmatched", value: audit.summary?.unmatched ?? 0, color: "#f59e0b" },
          { label: "Quality", value: `${Math.round((quality.overall_score ?? 0) * 100)}%`, color: quality.verdict === "pass" ? "#16a34a" : "#dc2626" },
        ].map(c => (
          <div key={c.label} style={styles.chip}>
            <div style={{ ...styles.chipVal, color: c.color }}>{c.value}</div>
            <div style={styles.chipLabel}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Quality issues */}
      {(quality.issues ?? []).length > 0 && (
        <div style={styles.qualityAlert}>
          ⚠️ Quality issues: {quality.issues.join(", ")}
          {quality.retake_reason && <div style={{ marginTop: 4 }}>{quality.retake_reason}</div>}
        </div>
      )}

      {/* Share of shelf */}
      {Object.keys(audit.share_of_shelf ?? {}).length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Share of Shelf</h3>
          <div style={styles.shareBar}>
            {Object.entries(audit.share_of_shelf).slice(0, 5).map(([brand, pct]: any, i) => (
              <div key={brand} title={`${brand}: ${pct.toFixed(1)}%`}
                style={{ flex: pct, background: SHARE_COLORS[i % SHARE_COLORS.length], height: "100%", minWidth: 4 }} />
            ))}
          </div>
          <div style={styles.shareLegend}>
            {Object.entries(audit.share_of_shelf).slice(0, 5).map(([brand, pct]: any, i) => (
              <div key={brand} style={styles.shareLegendItem}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: SHARE_COLORS[i % SHARE_COLORS.length] }} />
                <span>{brand}</span>
                <span style={{ color: "#64748b" }}>{pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Observations */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Observations ({obs.length})</h3>
        {obs.length === 0 && (
          <div style={styles.empty}>
            {audit.status === "processing"
              ? "⏳ Processing… refresh in a moment"
              : "No observations extracted from this image."}
          </div>
        )}
        {obs.map(o => {
          const minConf = Math.min(...Object.values(o.field_confidence ?? {}).filter((v): v is number => typeof v === "number").filter(v => v > 0), 1);
          const enr = o.enrichment ?? {};
          return (
            <div key={o.id} style={{ ...styles.obsCard, borderLeft: `4px solid ${CONF_COLOR(minConf)}` }}>
              <div style={styles.obsTop}>
                <div style={styles.obsBrand}>{o.brand_read || "Unknown Brand"}</div>
                <div style={{ ...styles.confBadge, background: CONF_BG(minConf), color: CONF_COLOR(minConf) }}>
                  {Math.round(minConf * 100)}% confidence
                </div>
              </div>
              <div style={styles.obsRow}>
                {o.size_read && <span style={styles.obsPill}>📦 {o.size_read}</span>}
                {o.facings != null && <span style={styles.obsPill}>×{o.facings} facings</span>}
                {o.shelf_position && <span style={styles.obsPill}>📍 {o.shelf_position}</span>}
                {o.price_value != null && <span style={styles.obsPill}>💵 ${o.price_value}</span>}
                <span style={{ ...styles.obsPill, background: o.status === "confirmed" ? "#dcfce7" : "#fef9c3", color: o.status === "confirmed" ? "#15803d" : "#92400e" }}>
                  {o.status}
                </span>
              </div>
              {(enr.price_delta_vs_set_avg_pct != null || enr.facings_share_of_set != null || enr.position_rank) && (
                <div style={styles.enrichRow}>
                  {enr.price_delta_vs_set_avg_pct != null && (
                    <span style={{ color: enr.price_delta_vs_set_avg_pct > 0 ? "#dc2626" : "#16a34a" }}>
                      {enr.price_delta_vs_set_avg_pct > 0 ? "↑" : "↓"} {Math.abs(enr.price_delta_vs_set_avg_pct).toFixed(1)}% vs avg
                    </span>
                  )}
                  {enr.facings_share_of_set != null && <span>🥧 {enr.facings_share_of_set.toFixed(1)}% shelf share</span>}
                  {enr.position_rank && <span>📊 {enr.position_rank}</span>}
                </div>
              )}
              {o.notes && <div style={styles.obsNotes}>💬 {o.notes}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const SHARE_COLORS = ["#3b82f6","#8b5cf6","#ec4899","#f59e0b","#10b981"];

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 700, margin: "0 auto" },
  center: { textAlign: "center", padding: 60 },
  spinner: { width: 40, height: 40, border: "3px solid #e2e8f0", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 12px" },
  loadingText: { color: "#64748b", fontSize: 15 },
  errBox: { background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626", padding: 16, borderRadius: 12 },
  backBtn: { background: "none", color: "#3b82f6", fontWeight: 600, fontSize: 14, marginBottom: 20, padding: "6px 0" },
  header: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, gap: 12 },
  storeName: { fontSize: 22, fontWeight: 800, color: "#0f172a", marginBottom: 4 },
  meta: { fontSize: 12, color: "#94a3b8" },
  statusBadge: { color: "#fff", fontSize: 12, fontWeight: 600, padding: "5px 12px", borderRadius: 20, whiteSpace: "nowrap" },
  chips: { display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" },
  chip: { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: "12px 16px", textAlign: "center", minWidth: 80 },
  chipVal: { fontSize: 22, fontWeight: 800, marginBottom: 2 },
  chipLabel: { fontSize: 11, color: "#94a3b8" },
  qualityAlert: { background: "#fef9c3", border: "1px solid #fde68a", borderRadius: 10, padding: "12px 14px", marginBottom: 20, fontSize: 14, color: "#92400e" },
  section: { marginBottom: 28 },
  sectionTitle: { fontSize: 14, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 },
  shareBar: { height: 12, borderRadius: 6, overflow: "hidden", display: "flex", marginBottom: 10 },
  shareLegend: { display: "flex", flexWrap: "wrap", gap: "8px 16px" },
  shareLegendItem: { display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#0f172a" },
  empty: { color: "#94a3b8", padding: "32px 0", textAlign: "center" },
  obsCard: { background: "#fff", borderRadius: 14, padding: "16px 18px", marginBottom: 10, border: "1px solid #e2e8f0" },
  obsTop: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  obsBrand: { fontSize: 16, fontWeight: 700, color: "#0f172a" },
  confBadge: { fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 20 },
  obsRow: { display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 },
  obsPill: { background: "#f1f5f9", color: "#475569", fontSize: 12, padding: "3px 10px", borderRadius: 20 },
  enrichRow: { display: "flex", gap: 14, fontSize: 13, color: "#64748b", marginBottom: 6, flexWrap: "wrap" },
  obsNotes: { fontSize: 12, color: "#94a3b8", fontStyle: "italic" },
};
