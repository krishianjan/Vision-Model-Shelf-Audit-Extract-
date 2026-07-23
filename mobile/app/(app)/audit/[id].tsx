import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet,
  ActivityIndicator, SectionList, Pressable, Share,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams } from "expo-router";
import { getAudit, getAuditDebug, type AuditDetail } from "../../../lib/api";

const STATUS_LABELS: Record<string, string> = {
  "processing": "⏳ Processing",
  "final": "✅ Capture Successful",
  "retake_required": "⚠️ Retake Required",
  "guardrail_rejected": "❌ Not Accepted",
};

export default function AuditDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [audit, setAudit] = useState<AuditDetail | null>(null);
  const [debugData, setDebugData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    let interval: NodeJS.Timeout;

    const fetchAudit = async () => {
      try {
        const data = await getAudit(id);
        setAudit(data);

        // If still processing, keep polling
        if (data.status === "processing") {
          setError(null);
        } else {
          // Done processing, stop polling
          if (interval) clearInterval(interval);
          // Fetch debug data (events + raw json) for logs/export
          if (!debugData) {
            getAuditDebug(id).then(setDebugData).catch(() => {});
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    };

    fetchAudit();

    // Poll every 2 seconds while processing
    interval = setInterval(fetchAudit, 2000);

    return () => clearInterval(interval);
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <ActivityIndicator color="#3b82f6" size="large" />
          <Text style={styles.loadingText}>Loading audit details...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!audit) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <Text style={styles.error}>{error || "Audit not found"}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const statusLabel = STATUS_LABELS[audit.status] || audit.status;
  const statusColor =
    audit.status === "final" ? "#16a34a" :
    audit.status === "retake_required" ? "#dc2626" :
    audit.status === "guardrail_rejected" ? "#6b7280" :
    "#d97706";

  const sections = [];

  // Section 1: Audit Summary
  sections.push({
    title: "AUDIT SUMMARY",
    data: [{ type: "summary" }],
  });

  // Section 2: Status & Feedback
  if (audit.status === "processing") {
    sections.push({
      title: "STATUS",
      data: [{ type: "processing" }],
    });
  } else if (audit.status === "guardrail_rejected") {
    sections.push({
      title: "REJECTION REASON",
      data: [{ type: "rejection", reason: "Image rejected by guardrail (CLIP model). Not recognized as a retail shelf." }],
    });
  } else if (audit.status === "retake_required") {
    sections.push({
      title: "IMAGE QUALITY ISSUE",
      data: [{
        type: "retake",
        reason: audit.capture_quality?.issues?.[0]?.reason
               || (audit.capture_quality as any)?.retake_reason
               || "Image quality too low",
        details: audit.capture_quality
      }],
    });
  }

  // Section 3: Extracted Observations (if final)
  if (audit.status === "final" && audit.observations && audit.observations.length > 0) {
    sections.push({
      title: `ITEMS DETECTED (${audit.observations.length})`,
      data: audit.observations.map((obs, idx) => ({ type: "observation", obs, idx })),
    });
  }

  // Section 4: CRM Summary (if final or retake)
  if ((audit.status === "final" || audit.status === "retake_required") && audit.observations && audit.observations.length > 0) {
    const totalFacings = audit.observations.reduce((sum, o) => sum + (o.facings || 0), 0);
    const confirmedCount = audit.observations.filter(o => o.status === "confirmed" || o.match_method === "exact").length;
    const unmatchedCount = audit.observations.filter(o => o.status === "unmatched" || !o.matched_sku_id).length;

    sections.push({
      title: "SET SUMMARY",
      data: [{
        type: "crm_summary",
        totalFacings,
        confirmedCount,
        unmatchedCount,
        totalCount: audit.observations.length,
      }],
    });
  }

  // Section 5: Pipeline Events (Debug Logs)
  if (debugData && debugData.events && debugData.events.length > 0) {
    sections.push({
      title: "PIPELINE EVENTS (DEBUG)",
      data: debugData.events.map((e: any, idx: number) => ({ type: "event", e, idx })),
    });
  }

  // Section 6: Export Raw JSON
  sections.push({
    title: "EXPORT",
    data: [{ type: "export_json", audit, debugData }],
  });

  // Section 4: No Data State
  if ((audit.status === "final" || audit.status === "retake_required") && (!audit.observations || audit.observations.length === 0)) {
    sections.push({
      title: "EXTRACTED DATA",
      data: [{ type: "empty" }],
    });
  }

  return (
    <SafeAreaView style={styles.container}>
      <SectionList
        sections={sections}
        keyExtractor={(item, idx) => `${idx}`}
        renderItem={({ item }) => {
          if (item.type === "summary") {
            return (
              <View style={styles.card}>
                <View style={{ marginBottom: 12 }}>
                  <Text style={styles.storeName}>{audit.account_name || "Unknown Store"}</Text>
                  <Text style={styles.timestamp}>
                    {new Date(audit.captured_at).toLocaleString()}
                  </Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: statusColor + "25", borderColor: statusColor }]}>
                  <Text style={[styles.statusText, { color: statusColor }]}>{statusLabel}</Text>
                </View>
              </View>
            );
          }

          if (item.type === "processing") {
            return (
              <View style={styles.card}>
                <ActivityIndicator color="#3b82f6" size="large" />
                <Text style={styles.processingText}>Processing image...</Text>
                <Text style={styles.processingSubtext}>Checking quality, reading labels (can take 5-10 seconds)</Text>
              </View>
            );
          }

          if (item.type === "rejection") {
            return (
              <View style={[styles.card, styles.rejectionCard]}>
                <Text style={styles.rejectionTitle}>❌ Image Not Accepted</Text>
                <Text style={styles.rejectionText}>{item.reason}</Text>
                <Text style={styles.rejectionTip}>💡 Try: Point at a store shelf with multiple bottles visible</Text>
              </View>
            );
          }

          if (item.type === "retake") {
            return (
              <View style={[styles.card, styles.retakeCard]}>
                <Text style={styles.retakeTitle}>⚠️ Image Quality Issue</Text>
                <Text style={styles.retakeReason}>{item.reason}</Text>
                {item.details?.issues && item.details.issues.length > 0 && (
                  <View style={styles.detailsBox}>
                    <Text style={styles.detailsLabel}>Technical Details:</Text>
                    {item.details.issues.map((issue: any, idx: number) => (
                      <Text key={idx} style={styles.detailsText}>
                        • {issue.type}: {issue.reason}
                      </Text>
                    ))}
                  </View>
                )}
                <Text style={styles.retakeTip}>💡 Try: Better lighting, steady hand, avoid glare</Text>
              </View>
            );
          }

          if (item.type === "observation") {
            const obs = item.obs;
            if (!obs.brand_read && !obs.sku_guess_text) return null;

            const skuConf = obs.field_confidence?.sku || 0;
            const brandConf = obs.field_confidence?.brand || 0;
            const priceConf = obs.field_confidence?.price || 0;
            const facingsConf = obs.field_confidence?.facings || 0;

            return (
              <View style={styles.obsCard}>
                <View style={styles.obsHeader}>
                  <View style={{ flex: 1 }}>
                    {obs.brand_read && <Text style={styles.brand}>{obs.brand_read}</Text>}
                    {obs.product_read && <Text style={styles.product}>{obs.product_read}</Text>}
                    {obs.size_read && <Text style={styles.size}>{obs.size_read}</Text>}
                    {obs.sku_guess_text && <Text style={styles.sku}>{obs.sku_guess_text}</Text>}
                  </View>
                  <View style={[styles.confidenceBadge, {
                    backgroundColor: skuConf >= 0.9 ? "#dcfce7" : skuConf >= 0.85 ? "#fef3c7" : "#fee2e2"
                  }]}>
                    <Text style={[styles.confidenceNum, {
                      color: skuConf >= 0.9 ? "#166534" : skuConf >= 0.85 ? "#b45309" : "#991b1b"
                    }]}>
                      {Math.round(skuConf * 100)}%
                    </Text>
                  </View>
                </View>

                <View style={styles.fieldGrid}>
                  {obs.price_value !== null && (
                    <View style={styles.fieldBox}>
                      <Text style={styles.fieldLabel}>Price</Text>
                      <Text style={styles.fieldValue}>${obs.price_value.toFixed(2)}</Text>
                      <Text style={styles.fieldConf}>{Math.round((priceConf || 0) * 100)}%</Text>
                    </View>
                  )}
                  {obs.facings !== null && (
                    <View style={styles.fieldBox}>
                      <Text style={styles.fieldLabel}>Facings</Text>
                      <Text style={styles.fieldValue}>{obs.facings}</Text>
                      <Text style={styles.fieldConf}>{Math.round((facingsConf || 0) * 100)}%</Text>
                    </View>
                  )}
                  {obs.shelf_position && (
                    <View style={styles.fieldBox}>
                      <Text style={styles.fieldLabel}>Position</Text>
                      <Text style={styles.fieldValue}>{obs.shelf_position.replace(/_/g, " ")}</Text>
                      <Text style={styles.fieldConf}>Read</Text>
                    </View>
                  )}
                </View>

                <View style={styles.confidenceTable}>
                  <Text style={styles.confTableTitle}>Field Confidence</Text>
                  <View style={styles.confRow}>
                    <Text style={styles.confLabel}>Brand</Text>
                    <Text style={styles.confValue}>{Math.round((brandConf || 0) * 100)}%</Text>
                  </View>
                  <View style={styles.confRow}>
                    <Text style={styles.confLabel}>Size</Text>
                    <Text style={styles.confValue}>{Math.round((obs.field_confidence?.size || 0) * 100)}%</Text>
                  </View>
                  <View style={styles.confRow}>
                    <Text style={styles.confLabel}>Price</Text>
                    <Text style={styles.confValue}>{Math.round((priceConf || 0) * 100)}%</Text>
                  </View>
                  <View style={styles.confRow}>
                    <Text style={styles.confLabel}>Facings</Text>
                    <Text style={styles.confValue}>{Math.round((facingsConf || 0) * 100)}%</Text>
                  </View>
                </View>
              </View>
            );
          }

          if (item.type === "empty") {
            return (
              <View style={styles.emptyCard}>
                <Text style={styles.emptyText}>No items extracted with high confidence</Text>
              </View>
            );
          }

          if (item.type === "crm_summary") {
            return (
              <View style={styles.crmCard}>
                <View style={styles.crmRow}>
                  <Text style={styles.crmLabel}>Total Facings</Text>
                  <Text style={styles.crmValue}>{item.totalFacings}</Text>
                </View>
                <View style={styles.crmRow}>
                  <Text style={styles.crmLabel}>Items Detected</Text>
                  <Text style={styles.crmValue}>{item.totalCount}</Text>
                </View>
                <View style={styles.crmRow}>
                  <Text style={styles.crmLabel}>Confirmed Matches</Text>
                  <Text style={[styles.crmValue, { color: "#16a34a" }]}>{item.confirmedCount}</Text>
                </View>
                <View style={styles.crmRow}>
                  <Text style={styles.crmLabel}>Unmatched SKUs</Text>
                  <Text style={[styles.crmValue, { color: item.unmatchedCount > 0 ? "#dc2626" : "#475569" }]}>{item.unmatchedCount}</Text>
                </View>
              </View>
            );
          }

          if (item.type === "event") {
            const e = item.e;
            return (
              <View style={styles.eventCard}>
                <View style={styles.eventHeader}>
                  <Text style={styles.eventType}>{e.event_type}</Text>
                  <Text style={styles.eventTime}>{e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""}</Text>
                </View>
                {e.payload ? (
                  <Text style={styles.eventPayload} numberOfLines={4}>
                    {JSON.stringify(e.payload, null, 2)}
                  </Text>
                ) : null}
              </View>
            );
          }

          if (item.type === "export_json") {
            const rawJson = JSON.stringify({ audit: item.audit, debug: item.debugData }, null, 2);
            return (
              <Pressable
                style={styles.exportBtn}
                onPress={() => Share.share({ message: rawJson })}
              >
                <Text style={styles.exportBtnText}>Share Raw JSON</Text>
              </Pressable>
            );
          }

          return null;
        }}
        renderSectionHeader={({ section: { title } }) => (
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>{title}</Text>
          </View>
        )}
        contentContainerStyle={styles.listContent}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  centerContent: { flex: 1, justifyContent: "center", alignItems: "center", padding: 20 },
  listContent: { padding: 16, gap: 12, paddingBottom: 32 },

  sectionHeader: { backgroundColor: "#e5e7eb", paddingHorizontal: 12, paddingVertical: 6, marginTop: 12, marginBottom: 8, borderRadius: 6 },
  sectionTitle: { fontSize: 11, fontWeight: "700", color: "#475569", textTransform: "uppercase", letterSpacing: 0.5 },

  card: { backgroundColor: "#fff", borderRadius: 12, padding: 16, borderWidth: 1, borderColor: "#e5e7eb" },
  storeName: { fontSize: 16, fontWeight: "700", color: "#111827" },
  timestamp: { fontSize: 12, color: "#6b7280", marginTop: 4 },
  statusBadge: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, alignSelf: "flex-start", marginTop: 8 },
  statusText: { fontSize: 13, fontWeight: "600" },

  processingText: { fontSize: 14, fontWeight: "600", color: "#111827", marginTop: 12, textAlign: "center" },
  processingSubtext: { fontSize: 11, color: "#6b7280", textAlign: "center", marginTop: 4 },
  loadingText: { fontSize: 12, color: "#6b7280", marginTop: 8 },

  rejectionCard: { backgroundColor: "#fef2f2", borderColor: "#fecaca" },
  rejectionTitle: { fontSize: 14, fontWeight: "700", color: "#dc2626", marginBottom: 6 },
  rejectionText: { fontSize: 12, color: "#7f1d1d", lineHeight: 18, marginBottom: 8 },
  rejectionTip: { fontSize: 11, color: "#991b1b", fontStyle: "italic", marginTop: 8 },

  retakeCard: { backgroundColor: "#fef3c7", borderColor: "#fcd34d" },
  retakeTitle: { fontSize: 14, fontWeight: "700", color: "#d97706", marginBottom: 6 },
  retakeReason: { fontSize: 12, color: "#92400e", lineHeight: 18 },
  detailsBox: { backgroundColor: "#fff7ed", borderRadius: 6, padding: 8, marginTop: 8 },
  detailsLabel: { fontSize: 10, fontWeight: "600", color: "#b45309", marginBottom: 4 },
  detailsText: { fontSize: 10, color: "#92400e", marginBottom: 2 },
  retakeTip: { fontSize: 11, color: "#b45309", fontStyle: "italic", marginTop: 8 },

  obsCard: { backgroundColor: "#fff", borderRadius: 10, padding: 14, borderWidth: 1, borderColor: "#e5e7eb", marginTop: 8 },
  obsHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  brand: { fontSize: 15, fontWeight: "700", color: "#111827" },
  product: { fontSize: 13, fontWeight: "500", color: "#374151", marginTop: 2 },
  size: { fontSize: 12, fontWeight: "400", color: "#6b7280", marginTop: 1 },
  sku: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  confidenceBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 },
  confidenceNum: { fontSize: 11, fontWeight: "700" },

  fieldGrid: { flexDirection: "row", gap: 8, marginBottom: 12, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  fieldBox: { flex: 1, backgroundColor: "#f9fafb", borderRadius: 6, padding: 8, alignItems: "center" },
  fieldLabel: { fontSize: 9, color: "#6b7280", fontWeight: "600", marginBottom: 2 },
  fieldValue: { fontSize: 13, fontWeight: "700", color: "#111827" },
  fieldConf: { fontSize: 8, color: "#9ca3af", marginTop: 2 },

  confidenceTable: { backgroundColor: "#f9fafb", borderRadius: 8, padding: 10 },
  confTableTitle: { fontSize: 10, fontWeight: "700", color: "#475569", marginBottom: 6, textTransform: "uppercase" },
  confRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: "#e5e7eb" },
  confLabel: { fontSize: 11, color: "#6b7280" },
  confValue: { fontSize: 11, fontWeight: "700", color: "#111827" },

  emptyCard: { backgroundColor: "#f3f4f6", borderRadius: 10, padding: 20, alignItems: "center" },
  emptyText: { fontSize: 12, color: "#6b7280", textAlign: "center" },

  error: { color: "#dc2626", fontSize: 16, textAlign: "center" },

  // CRM Summary Styles
  crmCard: { backgroundColor: "#0f172a", borderRadius: 12, padding: 16, marginTop: 8 },
  crmRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  crmLabel: { color: "#94a3b8", fontSize: 14, fontWeight: "500" },
  crmValue: { color: "#f8fafc", fontSize: 16, fontWeight: "800" },

  // Event Styles
  eventCard: { backgroundColor: "#1e293b", borderRadius: 8, padding: 10, marginTop: 6 },
  eventHeader: { flexDirection: "row", justifyContent: "space-between", marginBottom: 4 },
  eventType: { color: "#3b82f6", fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  eventTime: { color: "#64748b", fontSize: 10 },
  eventPayload: { color: "#94a3b8", fontSize: 10, fontFamily: "monospace", lineHeight: 14 },

  // Export Styles
  exportBtn: { backgroundColor: "#3b82f6", paddingVertical: 12, borderRadius: 8, alignItems: "center", marginTop: 12 },
  exportBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },

});
