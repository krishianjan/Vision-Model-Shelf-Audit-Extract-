/**
 * Web stub for offline queue — uses in-memory store.
 * Metro automatically picks this file on web platform.
 * On iOS/Android, db.ts (native SQLite) is used instead.
 */

export type QueueStatus = "pending" | "uploading" | "synced" | "failed";

export interface QueueRow {
  id: number;
  local_id: string;
  image_uri: string;
  voice_note_uri: string | null;
  account_id: string;
  captured_at: string;
  status: QueueStatus;
  server_audit_id: string | null;
  retry_count: number;
  created_at: string;
  error_msg: string | null;
}

const queue: QueueRow[] = [];
let nextId = 1;

export function enqueueCapture(
  local_id: string,
  image_uri: string,
  account_id: string,
  captured_at: string,
  voice_note_uri?: string
): void {
  queue.push({
    id: nextId++,
    local_id,
    image_uri,
    voice_note_uri: voice_note_uri ?? null,
    account_id,
    captured_at,
    status: "pending",
    server_audit_id: null,
    retry_count: 0,
    created_at: new Date().toISOString(),
    error_msg: null,
  });
}

export function getPendingCaptures(): QueueRow[] {
  return queue.filter((r) => r.status === "pending" || r.status === "failed");
}

export function markUploading(id: number): void {
  const r = queue.find((x) => x.id === id);
  if (r) r.status = "uploading";
}

export function markSynced(id: number, server_audit_id: string): void {
  const r = queue.find((x) => x.id === id);
  if (r) { r.status = "synced"; r.server_audit_id = server_audit_id; }
}

export function markFailed(id: number, error: string): void {
  const r = queue.find((x) => x.id === id);
  if (r) { r.status = "failed"; r.retry_count++; r.error_msg = error; }
}

export function getAllCaptures(): QueueRow[] {
  return [...queue].reverse();
}
