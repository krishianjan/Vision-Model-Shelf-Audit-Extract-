/**
 * Web sync stub — no background sync on web (no offline queue persistence).
 * Metro picks this automatically on web platform.
 */
export async function syncPendingCaptures(): Promise<void> {
  // No-op on web — no persistent queue
}
