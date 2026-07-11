/**
 * Sync — uploads pending queue rows to /audits.
 * Called on app foreground via AppState listener.
 * Background fetch removed (requires native build via EAS).
 * For Expo Go testing, foreground sync is sufficient.
 */
import {
  getPendingCaptures,
  markUploading,
  markSynced,
  markFailed,
} from "./db";
import { uploadAudit } from "./api";

let _syncing = false;

export async function syncPendingCaptures(): Promise<void> {
  if (_syncing) return;
  _syncing = true;
  try {
    const pending = getPendingCaptures();
    for (const row of pending) {
      markUploading(row.id);
      try {
        const result = await uploadAudit(
          row.image_uri,
          row.account_id,
          row.captured_at,
        );
        markSynced(row.id, result.audit_id);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        markFailed(row.id, msg);
      }
    }
  } finally {
    _syncing = false;
  }
}
