import { useState, useRef } from "react";
import { logout, getUser } from "../api";
import Audits from "./Audits";
import Capture from "./Capture";
import Stores from "./Stores";
import AuditDetail from "./AuditDetail";
import Chat from "./Chat";
import QualityTrend from "./QualityTrend";
import StoreInsights from "./StoreInsights";

type Tab = "audits" | "capture" | "stores" | "chat" | "quality" | "insights";

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("audits");
  const [auditId, setAuditId] = useState<string | null>(null);
  const auditsRef = useRef<{ refresh: () => void } | null>(null);
  const user = getUser();

  function handleLogout() { logout(); onLogout(); }

  function handleUploaded(id: string) {
    setAuditId(id);
    setTimeout(() => auditsRef.current?.refresh(), 1500);
  }

  if (auditId) {
    return <AuditDetail id={auditId} onBack={() => setAuditId(null)} />;
  }

  return (
    <div style={styles.shell}>
      {/* Top nav */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.logoMini}>K</div>
          <span style={styles.headerTitle}>Kosha Shelf Audit</span>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.userName}>{user?.name ?? user?.email}</span>
          <button onClick={handleLogout} style={styles.logoutBtn}>Sign Out</button>
        </div>
      </header>

      {/* Tab bar */}
      <nav style={styles.nav}>
        {(["audits", "capture", "quality", "insights", "stores", "chat"] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{ ...styles.navBtn, ...(tab === t ? styles.navBtnActive : {}) }}
          >
            {tabIcon(t)} {tabLabel(t)}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main style={styles.main}>
        {tab === "audits"  && <Audits ref={auditsRef} onSelect={setAuditId} />}
        {tab === "capture" && <Capture onUploaded={handleUploaded} />}
        {tab === "quality" && <QualityTrend />}
        {tab === "insights" && <StoreInsights onSelectAudit={setAuditId} />}
        {tab === "stores"  && <Stores />}
        {tab === "chat"    && <Chat />}
      </main>
    </div>
  );
}

function tabIcon(t: Tab) {
  return { audits: "📋", capture: "📷", quality: "📈", insights: "🏪", stores: "🏪", chat: "🤖" }[t];
}
function tabLabel(t: Tab) {
  return { audits: "Audits", capture: "Capture", quality: "Quality", insights: "Stores", stores: "Stores", chat: "Ask AI" }[t];
}

const styles: Record<string, React.CSSProperties> = {
  shell: { minHeight: "100vh", display: "flex", flexDirection: "column", background: "#f8fafc" },
  header: { background: "#0f172a", padding: "0 20px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 100 },
  headerLeft: { display: "flex", alignItems: "center", gap: 12 },
  logoMini: { width: 32, height: 32, borderRadius: 8, background: "#3b82f6", color: "#fff", fontWeight: 800, fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" },
  headerTitle: { color: "#f8fafc", fontWeight: 700, fontSize: 16 },
  headerRight: { display: "flex", alignItems: "center", gap: 12 },
  userName: { color: "#94a3b8", fontSize: 13 },
  logoutBtn: { background: "transparent", color: "#ef4444", fontSize: 13, fontWeight: 600, padding: "4px 10px", borderRadius: 6, border: "1px solid #ef4444" },
  nav: { background: "#fff", borderBottom: "1px solid #e2e8f0", display: "flex", padding: "0 16px", overflowX: "auto" },
  navBtn: { padding: "14px 18px", background: "none", color: "#64748b", fontSize: 14, fontWeight: 500, borderBottom: "3px solid transparent", display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" },
  navBtnActive: { color: "#3b82f6", borderBottomColor: "#3b82f6", fontWeight: 700 },
  main: { flex: 1, padding: "24px 20px", maxWidth: 900, width: "100%", margin: "0 auto" },
};
