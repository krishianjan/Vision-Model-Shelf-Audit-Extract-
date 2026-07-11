/**
 * Native offline queue — iOS/Android only (expo-sqlite).
 * Metro picks db.web.ts for web builds automatically.
 */
import * as SQLite from "expo-sqlite";

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

const db = SQLite.openDatabaseSync("kosha_queue.db");

db.execSync(`
  CREATE TABLE IF NOT EXISTS capture_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id        TEXT    NOT NULL UNIQUE,
    image_uri       TEXT    NOT NULL,
    voice_note_uri  TEXT,
    account_id      TEXT    NOT NULL,
    captured_at     TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    server_audit_id TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    error_msg       TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_queue_status ON capture_queue(status);
`);

export function enqueueCapture(
  local_id: string,
  image_uri: string,
  account_id: string,
  captured_at: string,
  voice_note_uri?: string
): void {
  db.runSync(
    `INSERT OR IGNORE INTO capture_queue (local_id, image_uri, voice_note_uri, account_id, captured_at)
     VALUES (?, ?, ?, ?, ?)`,
    local_id, image_uri, voice_note_uri ?? null, account_id, captured_at
  );
}

export function getPendingCaptures(): QueueRow[] {
  return db.getAllSync<QueueRow>(
    `SELECT * FROM capture_queue WHERE status IN ('pending','failed') AND retry_count < 5 ORDER BY created_at ASC LIMIT 20`
  );
}

export function markUploading(id: number): void {
  db.runSync("UPDATE capture_queue SET status='uploading' WHERE id=?", id);
}

export function markSynced(id: number, server_audit_id: string): void {
  db.runSync(
    "UPDATE capture_queue SET status='synced', server_audit_id=?, error_msg=NULL WHERE id=?",
    server_audit_id, id
  );
}

export function markFailed(id: number, error: string): void {
  db.runSync(
    `UPDATE capture_queue SET status='failed', retry_count=retry_count+1, error_msg=? WHERE id=?`,
    error, id
  );
}

export function getAllCaptures(): QueueRow[] {
  return db.getAllSync<QueueRow>(
    "SELECT * FROM capture_queue ORDER BY created_at DESC LIMIT 100"
  );
}
