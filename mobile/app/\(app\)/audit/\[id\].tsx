import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet,
  ActivityIndicator, SectionList, Pressable, Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { getAudit, cancelAudit, deleteAudit, type AuditDetail } from "../../../lib/api";

const STATUS_LABELS: Record<string, string> = {
  "processing": "⏳ Processing",
  "final": "✅ Capture Successful",
  "retake_required": "⚠️ Retake Required",
  "guardrail_rejected": "❌ Not Accepted",
};

export default function AuditDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [audit, setAudit] = useState<AuditDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

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

  const cancelProcessing = async () => {
    if (!id) return;
    Alert.alert(
      "Stop Processing?",
      "This will stop the current processing and mark it as failed. You can retake the image.",
      [
        { text: "Keep Processing", onPress: () => {} },
        {
          text: "Stop",
          onPress: async () => {
            setActionLoading(true);
            try {
              await cancelAudit(id);
              setAudit(prev => prev ? { ...prev, status: "processing_failed" } : null);
              Alert.alert("Success", "Processing stopped.");
            } catch (err) {
              Alert.alert("Error", err instanceof Error ? err.message : "Failed to stop processing");
            } finally {
              setActionLoading(false);
            }
          },
        },
      ]
    );
  };

  const onDeleteAudit = async () => {
    if (!id) return;
    Alert.alert(
      "Delete Image?",
      "This will permanently delete this audit and free up storage. This cannot be undone.",
      [
        { text: "Keep Image", onPress: () => {} },
        {
          text: "Delete",
          onPress: async () => {
            setActionLoading(true);
            try {
              await deleteAudit(id);
              Alert.alert("Success", "Audit deleted.");
              router.back();
            } catch (err) {
              Alert.alert("Error", err instanceof Error ? err.message : "Failed to delete audit");
            } finally {
              setActionLoading(false);
            }
          },
          style: "destructive",
        },
      ]
    );
  };

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
      data: [{ type: "rejection", reason: "Image rejected by guardrail. Not recognized as a retail alcohol shelf." }],
    });
  } else if (audit.status === "retake_required") {
    sections.push({
      title: "IMAGE QUALITY ISSUE",
      data: [{
        type: "retake",
        reason: audit.capture_quality?.issues?.[0]?.reason || "Image quality too low",
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
                <Text style={styles.processingText}>Image is being analyzed...</Text>
                <Text style={styles.processingSubtext}>Checking quality → Detecting shelf type → Extracting data</Text>
                <View style={styles.actionButtonsContainer}>
                  <Pressable
                    style={[styles.actionButton, styles.cancelButton]}
                    onPress={cancelProcessing}
                    disabled={actionLoading}
                  >
                    <Text style={[styles.actionButtonText, { color: "#d97706" }]}>
                      {actionLoading ? "..." : "Stop Processing"}
                    </Text>
                  </Pressable>
                  <Pressable
                    style={[styles.actionButton, styles.deleteButton]}
                    onPress={onDeleteAudit}
                    disabled={actionLoading}
                  >
                    <Text style={[styles.actionButtonText, { color: "#dc2626" }]}>
                      {actionLoading ? "..." : "Delete Image"}
                    </Text>
                  </Pressable>
                </View>
              </View>
            );
          }

          if (item.type === "rejection") {
            return (
              <View style={[styles.card, styles.rejectionCard]}>
                <Text style={styles.rejectionTitle}>❌ Rejected by Guardrail</Text>
                <Text style={styles.rejectionText}>{item.reason}</Text>
                <Text style={styles.rejectionTip}>💡 Make sure you're capturing an alcohol shelf in a retail store.</Text>
                <Pressable
                  style={[styles.actionButton, styles.deleteButton]}
                  onPress={deleteAudit}
                  disabled={actionLoading}
                >
                  <Text style={[styles.actionButtonText, { color: "#dc2626" }]}>
                    {actionLoading ? "..." : "Delete Image"}
                  </Text>
                </Pressable>
              </View>
            );
          }

          if (item.type === "retake") {
            return (
              <View style={[styles.card, styles.retakeCard]}>
                <Text style={styles.retakeTitle}>⚠️ Image Quality Issue</Text>
                <Text style={styles.retakeReason}>{item.reason}</Text>
                {item.details && (
                  <View style={styles.detailsBox}>
                    <Text style={styles.detailsLabel}>Issues Detected:</Text>
                    {item.details.issues?.map((issue: any, idx: number) => (
                      <Text key={idx} style={styles.detailsText}>• {issue.type}: {issue.reason}</Text>
                    ))}
                  </View>
                )}
                <Text style={styles.retakeTip}>💡 Try a well-lit photo with clear focus on the bottles.</Text>
                <Pressable
                  style={[styles.actionButton, styles.deleteButton]}
                  onPress={deleteAudit}
                  disabled={actionLoading}
                >
                  <Text style={[styles.actionButtonText, { color: "#dc2626" }]}>
                    {actionLoading ? "..." : "Delete Image"}
                  </Text>
                </Pressable>
              </View>
            );
          }

          if (item.type === "observation") {
            const obs = item.obs;
            const brandConf = obs.field_confidence?.brand;
            const priceConf = obs.field_confidence?.price;
            const facingsConf = obs.field_confidence?.facings;

            return (
              <View style={styles.obsCard}>
                <View style={styles.obsHeader}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.brand}>{obs.brand_read || "Unknown Brand"}</Text>
                    <Text style={styles.sku}>{obs.product_read || "No product info"}</Text>
                  </View>
                  <View style={[styles.confidenceBadge, { backgroundColor: (brandConf || 0) >= 0.7 ? "#d1fae5" : "#fee2e2" }]}>
                    <Text style={[styles.confidenceNum, { color: (brandConf || 0) >= 0.7 ? "#059669" : "#dc2626" }]}>
                      {Math.round((brandConf || 0) * 100)}%
                    </Text>
                  </View>
                </View>

                <View style={styles.fieldGrid}>
                  <View style={styles.fieldBox}>
                    <Text style={styles.fieldLabel}>Size</Text>
                    <Text style={styles.fieldValue}>{obs.size_read || "—"}</Text>
                    <Text style={styles.fieldConf}>{Math.round((obs.field_confidence?.size || 0) * 100)}%</Text>
                  </View>
                  <View style={styles.fieldBox}>
                    <Text style={styles.fieldLabel}>Position</Text>
                    <Text style={styles.fieldValue}>{obs.shelf_position || "—"}</Text>
                    <Text style={styles.fieldConf}>—</Text>
                  </View>
                  <View style={styles.fieldBox}>
                    <Text style={styles.fieldLabel}>Price</Text>
                    <Text style={styles.fieldValue}>{obs.price_read || "—"}</Text>
                    <Text style={styles.fieldConf}>{Math.round((priceConf || 0) * 100)}%</Text>
                  </View>
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

  actionButtonsContainer: { flexDirection: "row", gap: 10, marginTop: 16 },
  actionButton: { flex: 1, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1.5, alignItems: "center" },
  cancelButton: { borderColor: "#fed7aa", backgroundColor: "#fffbeb" },
  deleteButton: { borderColor: "#fecaca", backgroundColor: "#fef2f2" },
  actionButtonText: { fontSize: 12, fontWeight: "600" },

  rejectionCard: { backgroundColor: "#fef2f2", borderColor: "#fecaca" },
  rejectionTitle: { fontSize: 14, fontWeight: "700", color: "#dc2626", marginBottom: 6 },
  rejectionText: { fontSize: 12, color: "#7f1d1d", lineHeight: 18, marginBottom: 8 },
  rejectionTip: { fontSize: 11, color: "#991b1b", fontStyle: "italic", marginTop: 8, marginBottom: 12 },

  retakeCard: { backgroundColor: "#fef3c7", borderColor: "#fcd34d" },
  retakeTitle: { fontSize: 14, fontWeight: "700", color: "#d97706", marginBottom: 6 },
  retakeReason: { fontSize: 12, color: "#92400e", lineHeight: 18 },
  detailsBox: { backgroundColor: "#fff7ed", borderRadius: 6, padding: 8, marginTop: 8, marginBottom: 8 },
  detailsLabel: { fontSize: 10, fontWeight: "600", color: "#b45309", marginBottom: 4 },
  detailsText: { fontSize: 10, color: "#92400e", marginBottom: 2 },
  retakeTip: { fontSize: 11, color: "#b45309", fontStyle: "italic", marginTop: 8, marginBottom: 12 },

  obsCard: { backgroundColor: "#fff", borderRadius: 10, padding: 14, borderWidth: 1, borderColor: "#e5e7eb", marginTop: 8 },
  obsHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  brand: { fontSize: 15, fontWeight: "700", color: "#111827" },
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
});
