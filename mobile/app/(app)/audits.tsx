import React, { useEffect, useState, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, ActivityIndicator, RefreshControl, ScrollView, Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { getAudits, deleteAudit, cancelAudit, type AuditSummary, getRepDashboard, getShareOfShelf, type RepDashboard, type ShareOfShelfSummary } from "../../lib/api";
import { getAllCaptures, type QueueRow } from "../../lib/db";

const STATUS_COLOR: Record<string, string> = {
  final: "#16a34a",
  processing: "#d97706",
  retake_required: "#dc2626",
  guardrail_rejected: "#6b7280",
  processing_failed: "#dc2626",
  pending: "#d97706",
  synced: "#16a34a",
  failed: "#dc2626",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: STATUS_COLOR[status] ?? "#6b7280" }]}>
      <Text style={styles.badgeText}>{status.replace(/_/g, " ")}</Text>
    </View>
  );
}

function QueueCard({ row }: { row: QueueRow }) {
  return (
    <View style={styles.qCard}>
      <View style={styles.qRow}>
        <Text style={styles.qLabel}>Queued</Text>
        <StatusBadge status={row.status} />
      </View>
      <Text style={styles.qSub}>{row.captured_at.replace("T", " ").slice(0, 16)}</Text>
      {row.error_msg ? <Text style={styles.qErr}>{row.error_msg}</Text> : null}
    </View>
  );
}

function StatCard({ value, label, color }: { value: string | number; label: string; color?: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={[styles.statValue, color ? { color } : undefined]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function CRMDashboard() {
  const [dash, setDash] = useState<RepDashboard | null>(null);
  const [sos, setSos] = useState<ShareOfShelfSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([
        getRepDashboard().catch(() => null),
        getShareOfShelf().catch(() => null),
      ]);
      setDash(d);
      setSos(s);
    } catch {
      // silent — dashboard is secondary to audit list
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <View style={styles.dashboard}>
        <Text style={styles.dashboardTitle}>📊 CRM Dashboard</Text>
        <ActivityIndicator color="#3b82f6" size="small" style={{ marginVertical: 12 }} />
      </View>
    );
  }

  const summary = dash?.summary;
  const total = summary?.total_audits ?? 0;
  const completed = summary?.completed_audits ?? 0;
  const retakes = summary?.retake_count ?? 0;
  const rejected = summary?.rejected_count ?? 0;
  const stores = summary?.stores_visited ?? 0;
  const quality = summary?.avg_quality_score ?? 0;
  const pending = summary?.pending_review_count ?? 0;

  const topBrands = (sos?.brands ?? []).slice(0, 5);
  const totalFacings = sos?.total_facings ?? 0;

  return (
    <View style={styles.dashboard}>
      <Text style={styles.dashboardTitle}>📊 CRM Dashboard</Text>

      {/* Row 1: Core stats */}
      <View style={styles.statsGrid}>
        <StatCard value={total} label="Total Audits" />
        <StatCard value={completed} label="Completed" color="#16a34a" />
        <StatCard value={retakes} label="Retakes" color="#dc2626" />
        <StatCard value={rejected} label="Rejected" color="#6b7280" />
      </View>

      {/* Row 2: Quality + stores + pending */}
      <View style={styles.statsGrid}>
        <StatCard value={`${Math.round(quality * 100)}%`} label="Avg Quality" />
        <StatCard value={stores} label="Stores Visited" />
        <StatCard value={pending} label="Pending Review" color={pending > 0 ? "#d97706" : undefined} />
        <StatCard value={totalFacings} label="Total Facings" />
      </View>

      {/* Share of Shelf */}
      {topBrands.length > 0 && (
        <View style={styles.sosContainer}>
          <Text style={styles.sosTitle}>📈 Share of Shelf (Top 5 Brands)</Text>
          {topBrands.map((b, i) => {
            const maxPct = topBrands[0]?.share_pct || 1;
            return (
              <View key={b.brand + i} style={styles.sosRow}>
                <Text style={styles.sosBrand} numberOfLines={1}>{b.brand}</Text>
                <View style={styles.sosBarBg}>
                  <View style={[styles.sosBarFill, { width: `${(b.share_pct / maxPct) * 100}%` }]} />
                </View>
                <Text style={styles.sosPct}>{b.share_pct}%</Text>
              </View>
            );
          })}
        </View>
      )}

      {/* Top Unmatched (Competitive Intel) */}
      {(dash?.top_unmatched_brands ?? []).length > 0 && (
        <View style={styles.sosContainer}>
          <Text style={styles.sosTitle}>🔍 Unmatched Brands (Competitor Signals)</Text>
          {(dash!.top_unmatched_brands).slice(0, 3).map((u, i) => (
            <View key={u.brand_read + i} style={styles.unmatchedRow}>
              <Text style={styles.unmatchedBrand}>{u.brand_read}</Text>
              <Text style={styles.unmatchedCount}>seen {u.times_seen}x</Text>
            </View>
          ))}
        </View>
      )}

      {/* Last Activity */}
      {summary?.last_activity && (
        <Text style={styles.lastActivity}>
          Last activity: {summary.last_activity.replace("T", " ").slice(0, 16)}
        </Text>
      )}
    </View>
  );
}

export default function AuditsScreen() {
  const router = useRouter();
  const [audits, setAudits] = useState<AuditSummary[]>([]);
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const serverAudits = await getAudits();
      const localQueue = getAllCaptures();
      setAudits(serverAudits);
      setQueue(localQueue.filter((r) => r.status !== "synced"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const showActions = useCallback((item: AuditSummary) => {
    const isProcessing = item.status === "processing";

    const options: Array<{ text: string; onPress?: () => void; style?: "cancel" | "destructive" }> = [];

    if (isProcessing) {
      options.push({
        text: "🛑 Stop Processing",
        onPress: async () => {
          try {
            await cancelAudit(item.id);
            await load();
          } catch (e) {
            Alert.alert("Error", e instanceof Error ? e.message : "Cancel failed");
          }
        },
      });
    }

    options.push({
      text: isProcessing ? "🗑 Delete (stuck)" : "🗑 Delete",
      style: "destructive",
      onPress: async () => {
        try {
          await deleteAudit(item.id, false);
          await load();
        } catch (e: any) {
          // 400 means we need force=true (final audit)
          if (e?.message?.includes("400")) {
            Alert.alert(
              "Force delete?",
              "This is a completed audit. Delete it permanently?",
              [
                { text: "Cancel", style: "cancel" },
                {
                  text: "Yes, delete",
                  style: "destructive",
                  onPress: async () => {
                    try {
                      await deleteAudit(item.id, true);
                      await load();
                    } catch (e2) {
                      Alert.alert("Error", e2 instanceof Error ? e2.message : "Delete failed");
                    }
                  },
                },
              ]
            );
          } else {
            Alert.alert("Error", e instanceof Error ? e.message : "Delete failed");
          }
        }
      },
    });

    options.push({ text: "Cancel", style: "cancel" });

    Alert.alert(
      `Audit ${item.id.slice(0, 8)}`,
      `${item.status}${isProcessing ? " — using tokens while stuck" : ""}`,
      options
    );
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#3b82f6" size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={audits}
        keyExtractor={(i) => i.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
        ListHeaderComponent={
          <>
            {/* CRM Dashboard */}
            <CRMDashboard />
            
            {/* Offline Queue */}
            {queue.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>⚠️ Offline Queue ({queue.length})</Text>
                {queue.map((r) => <QueueCard key={r.id} row={r} />)}
              </View>
            )}
            
            {/* Audits List Header */}
            {audits.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>📋 Recent Audits</Text>
              </View>
            )}
          </>
        }
        ListEmptyComponent={
          <Text style={styles.empty}>No audits yet. Tap Capture to start auditing shelves.</Text>
        }
        renderItem={({ item }) => {
          const quality = (item as any).capture_quality?.overall_score ?? 0;
          const observations = (item as any).summary?.total_observations ?? 0;
          const confirmed = (item as any).summary?.confirmed ?? 0;
          
          return (
            <TouchableOpacity
              style={styles.card}
              onPress={() => router.push(`/(app)/audit/${item.id}`)}
              onLongPress={() => showActions(item)}
              delayLongPress={400}
            >
              {/* Store + Status */}
              <View style={styles.cardRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {item.account_name ?? item.account_id.slice(0, 8)}
                  </Text>
                  <Text style={styles.cardSub}>
                    {item.captured_at.replace("T", " ").slice(0, 16)}
                    {item.fixture_type ? ` · ${item.fixture_type}` : ""}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end", gap: 4 }}>
                  <StatusBadge status={item.status} />
                  {item.status === "processing" && (
                    <TouchableOpacity
                      style={styles.stopBtn}
                      onPress={() => showActions(item)}
                    >
                      <Text style={styles.stopBtnText}>🛑 Stop</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>

              {/* CRM Insights (only if observations extracted) */}
              {item.status === "final" && observations > 0 && (
                <View style={styles.insightsRow}>
                  <View style={styles.insight}>
                    <Text style={styles.insightLabel}>SKUs</Text>
                    <Text style={styles.insightValue}>{observations}</Text>
                  </View>
                  <View style={styles.insight}>
                    <Text style={styles.insightLabel}>Confirmed</Text>
                    <Text style={[styles.insightValue, { color: "#16a34a" }]}>{confirmed}</Text>
                  </View>
                  <View style={styles.insight}>
                    <Text style={styles.insightLabel}>Quality</Text>
                    <Text style={styles.insightValue}>{Math.round(quality * 100)}%</Text>
                  </View>
                </View>
              )}
            </TouchableOpacity>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#f9fafb" },
  
  dashboard: { backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#e5e7eb", padding: 16 },
  dashboardTitle: { fontSize: 16, fontWeight: "800", color: "#111827", marginBottom: 12 },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  statCard: {
    flex: 0.45,
    backgroundColor: "#f3f4f6", borderRadius: 10, padding: 12,
    alignItems: "center", borderWidth: 1, borderColor: "#e5e7eb",
  },
  statValue: { fontSize: 22, fontWeight: "800", color: "#3b82f6", marginBottom: 2 },
  statLabel: { fontSize: 11, color: "#6b7280", fontWeight: "600" },
  
  card: {
    backgroundColor: "#fff", marginHorizontal: 16, marginTop: 10,
    borderRadius: 10, padding: 14,
    borderWidth: 1, borderColor: "#e5e7eb",
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 3, elevation: 1,
  },
  cardRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 8 },
  cardTitle: { fontSize: 15, fontWeight: "700", color: "#111827" },
  cardSub: { fontSize: 12, color: "#6b7280", marginTop: 3 },

  stopBtn: {
    backgroundColor: "#dc2626", borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  stopBtnText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  
  insightsRow: { flexDirection: "row", gap: 12, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: "#e5e7eb" },
  insight: { flex: 1, alignItems: "center" },
  insightLabel: { fontSize: 10, color: "#6b7280", fontWeight: "600", marginBottom: 2 },
  insightValue: { fontSize: 16, fontWeight: "800", color: "#111827" },
  
  badge: { borderRadius: 5, paddingHorizontal: 8, paddingVertical: 4 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  
  section: { marginHorizontal: 16, marginTop: 12 },
  sectionTitle: { fontSize: 13, fontWeight: "700", color: "#6b7280", marginBottom: 6 },
  
  qCard: {
    backgroundColor: "#fef9c3", borderRadius: 8, padding: 10,
    marginBottom: 6, borderWidth: 1, borderColor: "#fde68a",
  },
  qRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  qLabel: { fontSize: 13, fontWeight: "600", color: "#92400e" },
  qSub: { fontSize: 11, color: "#78716c", marginTop: 2 },
  qErr: { fontSize: 10, color: "#dc2626", marginTop: 2 },
  
  empty: { textAlign: "center", color: "#9ca3af", marginTop: 60, fontSize: 15 },

  sosContainer: { marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: "#e5e7eb" },
  sosTitle: { fontSize: 13, fontWeight: "700", color: "#374151", marginBottom: 8 },
  sosRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  sosBrand: { fontSize: 12, fontWeight: "600", color: "#111827", width: 80 },
  sosBarBg: { flex: 1, height: 8, backgroundColor: "#e5e7eb", borderRadius: 4 },
  sosBarFill: { height: 8, backgroundColor: "#3b82f6", borderRadius: 4 },
  sosPct: { fontSize: 12, fontWeight: "700", color: "#3b82f6", width: 40, textAlign: "right" },

  unmatchedRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  unmatchedBrand: { fontSize: 12, fontWeight: "600", color: "#92400e" },
  unmatchedCount: { fontSize: 11, color: "#78716c" },

  lastActivity: { fontSize: 11, color: "#9ca3af", marginTop: 10, textAlign: "center" },
});
