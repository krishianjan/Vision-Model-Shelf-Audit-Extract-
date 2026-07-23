/**
 * Universal API client — works on web and native.
 * Uses storage.ts (no static native imports).
 */
import { getItem } from "./storage";

export const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getToken(): Promise<string | null> {
  return getItem("kosha_access_token");
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return token
    ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Account {
  id: string; name: string; chain: string | null;
  channel_type: string | null; address: string | null;
  latitude: number | null; longitude: number | null;
}
export interface FieldConfidence { brand?: number; size?: number; facings?: number; price?: number; }
export interface ObservationEnrichment {
  price_delta_vs_set_avg_pct: number | null;
  facings_share_of_set: number | null;
  position_rank: "premium" | "standard" | "value" | "special" | null;
  set_avg_price: number | null; set_total_facings: number | null;
}
export interface Observation {
  id: string; matched_sku_id: string | null; sku_guess_text: string | null;
  brand_read: string | null; visual_brand_guess: string | null; visual_brand_confidence: number | null;
  product_read: string | null; size_read: string | null; facings: number | null;
  shelf_position: string | null; price_value: number | null; price_confidence: number | null;
  field_confidence: FieldConfidence; status: string; match_method: string | null;
  notes: string | null; created_at: string;
  // Visual cues
  bottle_shape: string | null; glass_tint: string | null; cap_type: string | null;
  label_color: string | null; label_design: string | null; damage_flags: string | null;
  stock_level: string | null; alcohol_subcategory: string | null;
}
export interface AuditSummary {
  id: string; account_id: string; account_name: string | null;
  captured_at: string; status: string; fixture_type: string | null; version: number;
}
export interface AuditDetail extends AuditSummary {
  capture_quality: Record<string, unknown> | null;
  model_version: string | null; latency_ms: number | null;
  observations: Observation[];
  images: Array<{ id: string; storage_path: string; quality_score: number | null }>;
  share_of_shelf: Record<string, number>;
  summary: { total_observations: number; confirmed: number; unmatched: number; low_confidence: number; avg_min_confidence: number | null };
}

export const getAccounts = () => req<Account[]>("GET", "/accounts");
export const getAudits = (account_id?: string) =>
  req<AuditSummary[]>("GET", `/audits${account_id ? `?account_id=${account_id}` : ""}`);
export const getAudit = (id: string) => req<AuditDetail>("GET", `/audits/${id}`);
export const getAuditDebug = (id: string) => getJSON(`/audits/${id}/debug`);
export const patchObservation = (audit_id: string, obs_id: string, patch: { status: string; notes?: string }) =>
  req("PATCH", `/audits/${audit_id}/observations/${obs_id}`, patch);

export async function deleteAudit(audit_id: string, force: boolean = false): Promise<{ status: string; audit_id: string }> {
  const token = await getToken();
  const res = await fetch(`${BASE_URL}/audits/${audit_id}${force ? "?force=true" : ""}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  return res.json();
}

export async function cancelAudit(audit_id: string): Promise<{ status: string }> {
  const token = await getToken();
  const res = await fetch(`${BASE_URL}/audits/${audit_id}/cancel`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Cancel failed: ${res.status}`);
  return res.json();
}

export interface UploadResponse {
  audit_id: string;
  status: string;
  observations?: Array<{ id: string; brand_read: string | null }>;
}

export async function uploadAudit(
  imageUri: string,
  accountId: string,
  capturedAt: string,
  storeName?: string,
): Promise<UploadResponse> {
  const token = await getToken();
  const form = new FormData();

  // Web: imageUri is a blob/data URL → fetch blob
  // Native: imageUri is a file:// URI → use as-is with type hint
  if (imageUri.startsWith("data:") || imageUri.startsWith("blob:")) {
    const imgRes = await fetch(imageUri);
    const blob = await imgRes.blob();
    form.append("image", blob, "shelf.jpg");
  } else {
    form.append("image", { uri: imageUri, type: "image/jpeg", name: "shelf.jpg" } as any);
  }

  form.append("account_id", accountId);
  form.append("captured_at", capturedAt);
  if (storeName) {
    form.append("store_name", storeName);
  }

  const res = await fetch(`${BASE_URL}/audits`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function getJSON(path: string): Promise<any> {
  return req("GET", path);
}
