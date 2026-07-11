const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function token() { return localStorage.getItem("kosha_token"); }

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const tk = token();
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(tk ? { Authorization: `Bearer ${tk}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export async function login(email: string, password: string) {
  const d = await req<any>("POST", "/auth/token", { email, password });
  localStorage.setItem("kosha_token", d.access_token);
  localStorage.setItem("kosha_user", JSON.stringify({ email: d.email, name: d.name }));
  return d;
}

export function logout() {
  localStorage.removeItem("kosha_token");
  localStorage.removeItem("kosha_user");
}

export function getUser() {
  const raw = localStorage.getItem("kosha_user");
  return raw ? JSON.parse(raw) : null;
}

export function isLoggedIn() { return !!token(); }

export const getAccounts = () => req<any[]>("GET", "/accounts");
export const getAudits = () => req<any[]>("GET", "/audits");
export const getAudit = (id: string) => req<any>("GET", `/audits/${id}`);
export const getDashboard = () => req<any>("GET", "/reps/me/dashboard");
export const getCompetitorIntel = () => req<any[]>("GET", "/competitive-intel");
export const getQualityTrend = () => req<any>("GET", "/reps/me/quality-trend");
export const getStoreInsights = (accountId: string) => req<any>(`GET`, `/stores/${accountId}/insights`);
export const getJSON = (path: string) => req<any>("GET", path);

export async function uploadAudit(file: File, accountId: string) {
  const tk = token();
  const form = new FormData();
  form.append("image", file, "shelf.jpg");
  form.append("account_id", accountId);
  form.append("captured_at", new Date().toISOString());
  const res = await fetch(`${BASE}/audits`, {
    method: "POST",
    headers: tk ? { Authorization: `Bearer ${tk}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function askAI(question: string) {
  const tk = token();
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(tk ? { Authorization: `Bearer ${tk}` } : {}) },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}
