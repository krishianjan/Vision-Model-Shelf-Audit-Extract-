import { useEffect, useState } from "react";
import { getAccounts, getCompetitorIntel } from "../api";

export default function Stores() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [intel, setIntel] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAccounts(), getCompetitorIntel()])
      .then(([a, ci]) => { setAccounts(a); setIntel(ci); })
      .finally(() => setLoading(false));
  }, []);

  const filtered = accounts.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    (a.address ?? "").toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>Loading…</div>;

  return (
    <div>
      <input
        style={styles.search}
        placeholder="🔍 Search stores…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />

      <div style={styles.grid}>
        {filtered.map(a => (
          <div key={a.id} style={styles.card}>
            <div style={styles.cardTop}>
              <div style={styles.storeName}>{a.name}</div>
              <span style={{ ...styles.typeBadge, background: TYPE_COLOR[a.channel_type ?? ""] ?? "#e2e8f0" }}>
                {a.channel_type ?? "store"}
              </span>
            </div>
            {a.address && <div style={styles.addr}>📍 {a.address}</div>}
          </div>
        ))}
      </div>

      {/* Competitive intel */}
      {intel.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>🔍 Competitive Intelligence</h3>
          <p style={styles.sectionSub}>Unmatched brands spotted on shelves — potential new competitors or products</p>
          {intel.slice(0, 10).map((item, i) => (
            <div key={i} style={styles.intelCard}>
              <div style={styles.intelBrand}>{item.brand_read}</div>
              <div style={styles.intelMeta}>
                Seen {item.occurrence_count}× · Last: {new Date(item.latest_seen_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const TYPE_COLOR: Record<string, string> = {
  liquor: "#dbeafe", bigbox: "#f3e8ff", convenience: "#dcfce7", grocery: "#fef9c3",
};

const styles: Record<string, React.CSSProperties> = {
  search: { width: "100%", padding: "12px 16px", borderRadius: 12, border: "1.5px solid #e2e8f0", fontSize: 15, marginBottom: 20, outline: "none", background: "#fff" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12, marginBottom: 32 },
  card: { background: "#fff", borderRadius: 14, padding: "16px 18px", border: "1px solid #e2e8f0", boxShadow: "0 1px 4px rgba(0,0,0,0.05)" },
  cardTop: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  storeName: { fontSize: 15, fontWeight: 700, color: "#0f172a" },
  typeBadge: { fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20, color: "#475569" },
  addr: { fontSize: 12, color: "#94a3b8" },
  section: { marginTop: 32 },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#0f172a", marginBottom: 6 },
  sectionSub: { fontSize: 13, color: "#64748b", marginBottom: 14 },
  intelCard: { background: "#fff", borderRadius: 12, padding: "12px 16px", marginBottom: 8, border: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" },
  intelBrand: { fontSize: 14, fontWeight: 600, color: "#0f172a" },
  intelMeta: { fontSize: 12, color: "#94a3b8" },
};
