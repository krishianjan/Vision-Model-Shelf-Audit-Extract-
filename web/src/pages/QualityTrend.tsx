import { useEffect, useState } from "react";
import { getJSON } from "../api";

interface TrendData {
  audit_date: string;
  audit_count: number;
  avg_quality: number;
  successful_audits: number;
  failed_audits: number;
}

export default function QualityTrend() {
  const [trend, setTrend] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await getJSON("/reps/me/quality-trend");
        setTrend(data.trend || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  if (loading) return <div style={styles.center}>⏳ Loading trend…</div>;
  if (error) return <div style={styles.errBox}>⚠️ {error}</div>;
  if (trend.length === 0) return <div style={styles.center}>No data yet</div>;

  const avgQuality = Math.round((trend.reduce((s, d) => s + d.avg_quality, 0) / trend.length) * 100);
  const totalAudits = trend.reduce((s, d) => s + d.audit_count, 0);
  const maxQ = Math.max(...trend.map(d => d.avg_quality), 0.8);

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>📈 Quality Trend (14 Days)</h2>

      <div style={styles.stats}>
        <div style={styles.stat}>
          <div style={styles.statVal}>{avgQuality}%</div>
          <div style={styles.statLbl}>Avg Quality</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statVal}>{totalAudits}</div>
          <div style={styles.statLbl}>Audits</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statVal}>{trend.reduce((s, d) => s + d.successful_audits, 0)}</div>
          <div style={styles.statLbl}>Completed</div>
        </div>
      </div>

      <div style={styles.chartBox}>
        <div style={styles.chart}>
          {trend.map((d, i) => (
            <div key={i} style={styles.barWrap}>
              <div
                title={`${new Date(d.audit_date).toLocaleDateString()}: ${Math.round(d.avg_quality * 100)}%`}
                style={{
                  ...styles.bar,
                  height: `${(d.avg_quality / maxQ) * 200}px`,
                  backgroundColor: d.avg_quality >= 0.8 ? "#16a34a" : "#f59e0b",
                }}
              />
              <div style={styles.barLbl}>
                {new Date(d.audit_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={styles.legend}>
        <div style={styles.legItem}>
          <div style={{ width: 12, height: 12, background: "#16a34a", borderRadius: 2 }} />
          <span>Good (≥80%)</span>
        </div>
        <div style={styles.legItem}>
          <div style={{ width: 12, height: 12, background: "#f59e0b", borderRadius: 2 }} />
          <span>Needs Improvement</span>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 800, margin: "0 auto" },
  center: { textAlign: "center", padding: 60, color: "#64748b" },
  errBox: { background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626", padding: 16, borderRadius: 12 },
  title: { fontSize: 24, fontWeight: 700, color: "#0f172a", marginBottom: 20 },
  stats: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 },
  stat: { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, textAlign: "center" },
  statVal: { fontSize: 22, fontWeight: 800, color: "#3b82f6", marginBottom: 4 },
  statLbl: { fontSize: 12, color: "#94a3b8" },
  chartBox: { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 20, marginBottom: 20 },
  chart: { display: "flex", alignItems: "flex-end", gap: 6, height: 200 },
  barWrap: { flex: 1, display: "flex", flexDirection: "column", alignItems: "center" },
  bar: { width: "100%", borderRadius: 4, minHeight: 4 },
  barLbl: { fontSize: 10, color: "#94a3b8", marginTop: 6, textAlign: "center", whiteSpace: "nowrap" },
  legend: { display: "flex", gap: 20 },
  legItem: { display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#475569" },
};
