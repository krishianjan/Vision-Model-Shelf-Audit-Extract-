import { useState } from "react";
import { login } from "../api";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("rep@kosha.ai");
  const [password, setPassword] = useState("test123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(email, password);
      onLogin();
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>K</div>
          <div>
            <div style={styles.logoTitle}>Kosha</div>
            <div style={styles.logoSub}>Shelf Audit</div>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <label style={styles.label}>Email</label>
          <input
            style={styles.input}
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="rep@kosha.ai"
            required
          />
          <label style={styles.label}>Password</label>
          <input
            style={styles.input}
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
          {error && <div style={styles.error}>{error}</div>}
          <button style={styles.btn} disabled={loading}>
            {loading ? "Signing in…" : "Sign In →"}
          </button>
        </form>

        <div style={styles.hint}>
          <b>Demo:</b> rep@kosha.ai / test123
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)", padding: 20 },
  card: { background: "#fff", borderRadius: 20, padding: "40px 36px", width: "100%", maxWidth: 400, boxShadow: "0 24px 80px rgba(0,0,0,0.2)" },
  logo: { display: "flex", alignItems: "center", gap: 14, marginBottom: 32 },
  logoIcon: { width: 48, height: 48, borderRadius: 14, background: "linear-gradient(135deg, #3b82f6, #1d4ed8)", color: "#fff", fontSize: 24, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" },
  logoTitle: { fontSize: 22, fontWeight: 800, color: "#0f172a" },
  logoSub: { fontSize: 13, color: "#64748b" },
  label: { display: "block", fontSize: 13, fontWeight: 600, color: "#475569", marginBottom: 6 },
  input: { width: "100%", padding: "12px 14px", borderRadius: 10, border: "1.5px solid #e2e8f0", fontSize: 15, outline: "none", marginBottom: 16, transition: "border-color 0.2s" },
  error: { background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626", borderRadius: 8, padding: "10px 14px", fontSize: 14, marginBottom: 16 },
  btn: { width: "100%", padding: "14px", background: "linear-gradient(135deg, #3b82f6, #1d4ed8)", color: "#fff", borderRadius: 12, fontSize: 16, fontWeight: 700, marginTop: 4 },
  hint: { marginTop: 20, padding: "12px 14px", background: "#f8fafc", borderRadius: 10, fontSize: 13, color: "#64748b", textAlign: "center" },
};
