import { useEffect, useRef, useState } from "react";
import { getAccounts, uploadAudit } from "../api";

export default function Capture({ onUploaded }: { onUploaded: (id: string) => void }) {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getAccounts().then(a => { setAccounts(a); if (a[0]) setSelectedId(a[0].id); });
  }, []);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setMsg("");
  }

  async function handleUpload() {
    if (!file || !selectedId) return;
    setBusy(true); setMsg("Uploading…");
    try {
      const result = await uploadAudit(file, selectedId);
      setBusy(false); setMsg("✅ Uploaded! Redirecting to audit…");
      setTimeout(() => onUploaded(result.audit_id), 1200);
    } catch (err: any) {
      setBusy(false); setMsg(`❌ ${err.message}`);
    }
  }

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>Capture Shelf Photo</h2>
      <p style={styles.sub}>Upload a photo of a beverage shelf to start an AI audit</p>

      {/* Store selector */}
      <div style={styles.field}>
        <label style={styles.label}>Store</label>
        <select style={styles.select} value={selectedId} onChange={e => setSelectedId(e.target.value)}>
          {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>

      {/* Drop zone / preview */}
      <div
        style={styles.dropZone}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) { setFile(f); setPreview(URL.createObjectURL(f)); } }}
      >
        {preview
          ? <img src={preview} style={styles.preview} alt="shelf preview" />
          : (
            <div style={styles.dropPlaceholder}>
              <div style={styles.dropIcon}>📸</div>
              <div style={styles.dropText}>Click or drag a shelf photo here</div>
              <div style={styles.dropSub}>JPEG or PNG, up to 15MB</div>
            </div>
          )
        }
        <input ref={inputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleFile} />
      </div>

      {file && (
        <div style={styles.fileInfo}>
          📎 {file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)
        </div>
      )}

      <button
        style={{ ...styles.uploadBtn, ...((!file || busy) ? styles.uploadBtnDisabled : {}) }}
        onClick={handleUpload}
        disabled={!file || busy || !selectedId}
      >
        {busy ? "Uploading…" : "🚀 Upload & Analyse"}
      </button>

      {msg && (
        <div style={{ ...styles.msg, color: msg.startsWith("✅") ? "#16a34a" : msg.startsWith("❌") ? "#dc2626" : "#0f172a" }}>
          {msg}
        </div>
      )}

      {/* Quality tips */}
      <div style={styles.tips}>
        <div style={styles.tipsTitle}>📋 Photo Guidelines</div>
        <div style={styles.tipRow}>
          <div style={styles.tipGood}>✅ Straight-on, well-lit shelf</div>
          <div style={styles.tipGood}>✅ All labels clearly readable</div>
          <div style={styles.tipBad}>❌ Blurry or dark photos</div>
          <div style={styles.tipBad}>❌ Selfies, food, receipts</div>
        </div>
        <div style={styles.tipsNote}>Images are scored by AI — blurry shots get flagged for retake automatically.</div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 600, margin: "0 auto" },
  title: { fontSize: 22, fontWeight: 800, marginBottom: 6, color: "#0f172a" },
  sub: { fontSize: 14, color: "#64748b", marginBottom: 24 },
  field: { marginBottom: 18 },
  label: { display: "block", fontSize: 13, fontWeight: 600, color: "#475569", marginBottom: 6 },
  select: { width: "100%", padding: "11px 14px", borderRadius: 10, border: "1.5px solid #e2e8f0", fontSize: 15, background: "#fff", outline: "none" },
  dropZone: { border: "2px dashed #cbd5e1", borderRadius: 16, minHeight: 220, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", marginBottom: 12, overflow: "hidden", background: "#fff", transition: "border-color 0.2s" },
  dropPlaceholder: { textAlign: "center", padding: 32 },
  dropIcon: { fontSize: 48, marginBottom: 12 },
  dropText: { fontSize: 16, fontWeight: 600, color: "#475569", marginBottom: 6 },
  dropSub: { fontSize: 13, color: "#94a3b8" },
  preview: { width: "100%", height: "100%", objectFit: "contain", maxHeight: 320 },
  fileInfo: { fontSize: 13, color: "#64748b", marginBottom: 12 },
  uploadBtn: { width: "100%", padding: 15, background: "linear-gradient(135deg, #3b82f6, #1d4ed8)", color: "#fff", borderRadius: 12, fontSize: 16, fontWeight: 700, marginBottom: 12 },
  uploadBtnDisabled: { opacity: 0.5, cursor: "not-allowed" },
  msg: { padding: "12px 16px", borderRadius: 10, background: "#f8fafc", fontSize: 15, marginBottom: 20, textAlign: "center" },
  tips: { background: "#f0fdf4", borderRadius: 14, padding: "16px 18px", border: "1px solid #bbf7d0" },
  tipsTitle: { fontSize: 14, fontWeight: 700, color: "#166534", marginBottom: 10 },
  tipRow: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 },
  tipGood: { fontSize: 13, color: "#15803d" },
  tipBad: { fontSize: 13, color: "#dc2626" },
  tipsNote: { fontSize: 12, color: "#64748b", fontStyle: "italic" },
};
