import React, { useEffect, useState, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, ActivityIndicator, RefreshControl, ScrollView, Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { getAudits, deleteAudit, cancelAudit, type AuditSummary } from "../../lib/api";
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

function CRMDashboard({ audits }: { audits: AuditSummary[] }) {
  const total = audits.length;
  const completed = audits.filter(a => a.status === "final").length;
  const avgQuality = audits.length > 0 
    ? Math.round((audits.reduce((sum, a) => sum + ((a as any).capture_quality?.overall_score ?? 0), 0) / audits.length) * 100)
    : 0;
  const retakeRequired = audits.filter(a => a.status === "retake_required").length;

  return (
    <View style={styles.dashboard}>
      <Text style={styles.dashboardTitle}>📊 Your Shelf Audit Summary</Text>
      
      <View style={styles.statsGrid}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{total}</Text>
          <Text style={styles.statLabel}>Total Audits</Text>
        </View>
        
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: "#16a34a" }]}>{completed}</Text>
          <Text style={styles.statLabel}>Completed</Text>
        </View>
        
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{avgQuality}%</Text>
          <Text style={styles.statLabel}>Avg Quality</Text>
        </View>
        
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: "#dc2626" }]}>{retakeRequired}</Text>
          <Text style={styles.statLabel}>Retakes</Text>
        </View>
      </View>
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
            <CRMDashboard audits={audits} />
            
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
});
