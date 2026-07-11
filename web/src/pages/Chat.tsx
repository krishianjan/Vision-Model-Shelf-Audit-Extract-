import { useEffect, useRef, useState } from "react";
import { askAI, getAudits } from "../api";

export default function Chat() {
  const [messages, setMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [audits, setAudits] = useState<any[]>([]);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAudits().then(a => setAudits(a)).catch(() => {});
    setMessages([
      {
        role: "assistant",
        text: audits.length === 0
          ? "👋 No audits yet. Upload a shelf photo first, then I can answer questions about your data."
          : "👋 Ask me anything about your audits! I can help you find insights about your shelf data.",
      },
    ]);
  }, []);

  useEffect(() => messagesEnd.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function handleSend() {
    if (!question.trim()) return;
    if (audits.length === 0) {
      setMessages(prev => [...prev, { role: "user", text: question }, { role: "assistant", text: "❌ No audits uploaded yet. Please capture a shelf photo first, then I can analyze your data." }]);
      setQuestion("");
      return;
    }

    const userMsg = question;
    setMessages(prev => [...prev, { role: "user", text: userMsg }]);
    setQuestion("");
    setBusy(true);

    try {
      const result = await askAI(userMsg);
      setMessages(prev => [...prev, { role: "assistant", text: result.response || "No response from AI" }]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to get response";
      setMessages(prev => [...prev, { role: "assistant", text: `⚠️ ${errorMsg}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>Ask AI Assistant</h2>
      <p style={styles.sub}>Query your audit data using natural language</p>

      <div style={styles.chatBox}>
        <div style={styles.messagesContainer}>
          {messages.map((msg, i) => (
            <div key={i} style={{ ...styles.messageRow, justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
              <div style={{ ...styles.messageBubble, ...(msg.role === "user" ? styles.userBubble : styles.assistantBubble) }}>
                {msg.text}
              </div>
            </div>
          ))}
          {busy && (
            <div style={{ ...styles.messageRow, justifyContent: "flex-start" }}>
              <div style={styles.assistantBubble}>
                <div style={styles.spinner} />
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        <div style={styles.inputRow}>
          <input
            type="text"
            placeholder={audits.length === 0 ? "Upload a photo first..." : "Ask about your audits..."}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyPress={e => e.key === "Enter" && !busy && handleSend()}
            disabled={busy || audits.length === 0}
            style={styles.inputField}
          />
          <button onClick={handleSend} disabled={busy || !question.trim() || audits.length === 0} style={styles.sendBtn}>
            {busy ? "…" : "Send"}
          </button>
        </div>
      </div>

      <div style={styles.hints}>
        <div style={styles.hintsTitle}>💡 Try asking:</div>
        <div style={styles.hintList}>
          <div>• "What stores have I visited?"</div>
          <div>• "Show me audits with low confidence"</div>
          <div>• "What brands did I find last week?"</div>
          <div>• "Which audits need retakes?"</div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 700, margin: "0 auto", display: "flex", flexDirection: "column", height: "calc(100vh - 140px)" },
  title: { fontSize: 22, fontWeight: 800, marginBottom: 6, color: "#0f172a" },
  sub: { fontSize: 14, color: "#64748b", marginBottom: 16 },
  chatBox: { flex: 1, background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", display: "flex", flexDirection: "column" },
  messagesContainer: { flex: 1, padding: 20, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 },
  messageRow: { display: "flex" },
  messageBubble: { maxWidth: "70%", padding: "12px 16px", borderRadius: 14, fontSize: 14, lineHeight: 1.4 },
  userBubble: { background: "#3b82f6", color: "#fff", borderBottomRightRadius: 4 },
  assistantBubble: { background: "#f1f5f9", color: "#0f172a", borderBottomLeftRadius: 4 },
  spinner: { width: 16, height: 16, border: "2px solid #e2e8f0", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.6s linear infinite" },
  inputRow: { display: "flex", gap: 10, padding: 16, borderTop: "1px solid #e2e8f0" },
  inputField: { flex: 1, padding: "10px 14px", borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 14, outline: "none" },
  sendBtn: { padding: "10px 20px", background: "#3b82f6", color: "#fff", borderRadius: 10, fontWeight: 600, fontSize: 14 },
  hints: { background: "#f0f4f8", borderRadius: 12, padding: 16, marginTop: 16 },
  hintsTitle: { fontSize: 13, fontWeight: 700, color: "#475569", marginBottom: 8 },
  hintList: { fontSize: 13, color: "#64748b", lineHeight: 1.6 },
};
