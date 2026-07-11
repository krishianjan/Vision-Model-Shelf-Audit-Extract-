import { useEffect, useState } from "react";
import { getAccounts, getJSON } from "../api";

interface Account { id: string; name: string; }
interface Insight {
  audit_id: string;
  captured_at: string;
  status: string;
  observation_count: number;
  confirmed_count: number;
  unmatched_count: number;
  total_facings: number;
  avg_brand_confidence: number;
  latest_quality_score: number;
}

export default function StoreInsights({ onSelectAudit }: { onSelectAudit: (id: string) => void }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState<Account | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetch = async () => {
      try {
        const acc = await getAccounts();
        setAccounts(acc || []);
        if (acc && acc.length > 0) {
          setSelected(acc[0]);
          fetchInsights(acc[0].id);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  const fetchInsights = async (id: string) => {
    try {
      const data = await getJSON(`/stores/${id}/insights`);
      setInsights(data.insights || []);
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) return <div style={styles.center}>⏳ Loading stores…</div>;
  if (error) return <div style={styles.errBox}>⚠️ {error}</div>;
  if (accounts.length === 0) return <div style={styles.center}>No stores found</div>;

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>🏪 Store Insights</h2>

      <div style={styles.accountTabs}>
        {accounts.map(a => (
          <button
            key={a.id}
            onClick={() => { setSelected(a); fetchInsights(a.id); }}
            style={{ ...styles.tab, ...(selected?.id === a.id ? styles.tabActive : {}) }}
          >
            {a.name.split(" -")[0]}
          </button>
        ))}
      </div>

      {insights.length === 0 ? (
        <div style={styles.empty}>No audits yet</div>
      ) : (
        <div style={styles.insightsList}>
          {insights.map((i, idx) => (
            <div key={idx} style={styles.card}>
              <div style={styles.cardTop}>
                <span style={styles.date}>{new Date(i.captured_at).toLocaleDateString()}</span>
                <span style={{ ...styles.badge, background: i.status === "final" ? "#dcfce7" : "#fee2e2", color: i.status === "final" ? "#15803d" : "#991b1b" }}>
                  {i.status.replace(/_/g, " ")}
                </span>
              </div>
              <div style={styles.stats}>
                <div style={styles.statSmall}><div style={styles.val}>{i.observation_count}</div><div style={styles.lbl}>Items</div></div>
                <div style={styles.statSmall}><div style={styles.val}>{i.confirmed_count}</div><div style={styles.lbl}>Confirmed</div></div>
                <div style={styles.statSmall}><div style={styles.val}>{i.total_facings}</div><div style={styles.lbl}>Facings</div></div>
                <div style={styles.statSmall}><div style={styles.val}>{Math.round(i.latest_quality_score * 100)}%</div><div style={styles.lbl}>Quality</div></div>
              </div>
              <button onClick={() => onSelectAudit(i.audit_id)} style={styles.viewBtn}>View Details →</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 800, margin: "0 auto" },
  center: { textAlign: "center", padding: 60, color: "#64748b" },
  errBox: { background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626", padding: 16, borderRadius: 12 },
  title: { fontSize: 24, fontWeight: 700, color: "#0f172a", marginBottom: 16 },
  accountTabs: { display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" },
  tab: { background: "#e2e8f0", color: "#475569", padding: "6px 12px", borderRadius: 20, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" },
  tabActive: { background: "#3b82f6", color: "#fff" },
  empty: { textAlign: "center", padding: "40px 20px", color: "#94a3b8" },
  insightsList: { display: "flex", flexDirection: "column", gap: 12 },
  card: { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 16 },
  cardTop: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  date: { fontSize: 12, color: "#64748b", fontWeight: 600 },
  badge: { fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 12, textTransform: "capitalize" },
  stats: { display: "flex", justifyContent: "space-around", borderTop: "1px solid #e2e8f0", borderBottom: "1px solid #e2e8f0", paddingY: 12, gap: 8, marginBottom: 12 },
  statSmall: { textAlign: "center", flex: 1, paddingY: 8 },
  val: { fontSize: 16, fontWeight: 800, color: "#0f172a" },
  lbl: { fontSize: 10, color: "#94a3b8", marginTop: 2 },
  viewBtn: { width: "100%", background: "#3b82f6", color: "#fff", border: "none", padding: "10px 16px", borderRadius: 8, fontWeight: 600, fontSize: 14, cursor: "pointer" },
};
