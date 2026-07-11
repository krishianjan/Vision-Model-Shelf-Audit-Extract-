import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import type { Observation } from "../lib/api";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface Props {
  obs: Observation;
  onConfirm?: (obsId: string) => void;
}

const POSITION_COLOR: Record<string, string> = {
  premium: "#7c3aed",
  standard: "#0284c7",
  value: "#6b7280",
  special: "#d97706",
};

export function ObservationCard({ obs, onConfirm }: Props) {
  const minConf = obs.field_confidence
    ? Math.min(...Object.values(obs.field_confidence).filter((v): v is number => typeof v === "number"))
    : null;
  const rank = obs.enrichment?.position_rank ?? "special";
  const needsReview = obs.status === "low_confidence" || obs.status === "unmatched";

  return (
    <View style={[styles.card, needsReview && styles.cardFlagged]}>
      {/* Header row */}
      <View style={styles.row}>
        <Text style={styles.brand} numberOfLines={1}>
          {obs.brand_read ?? "Unknown Brand"}
        </Text>
        <ConfidenceBadge value={minConf} size="sm" />
      </View>

      {/* Details row */}
      <View style={styles.row}>
        <Text style={styles.detail}>{obs.size_read ?? "—"}</Text>
        <Text style={styles.dot}>·</Text>
        <Text style={styles.detail}>
          {obs.facings != null ? `${obs.facings} facings` : "—"}
        </Text>
        <Text style={styles.dot}>·</Text>
        <Text style={[styles.posChip, { color: POSITION_COLOR[rank] ?? "#374151" }]}>
          {rank.toUpperCase()}
        </Text>
      </View>

      {/* Enrichment chips */}
      <View style={styles.chipRow}>
        {obs.price_value != null && (
          <View style={styles.chip}>
            <Text style={styles.chipText}>${obs.price_value.toFixed(2)}</Text>
          </View>
        )}
        {obs.enrichment?.price_delta_vs_set_avg_pct != null && (
          <View
            style={[
              styles.chip,
              {
                backgroundColor:
                  obs.enrichment.price_delta_vs_set_avg_pct > 0 ? "#fef3c7" : "#dcfce7",
              },
            ]}
          >
            <Text style={styles.chipText}>
              {obs.enrichment.price_delta_vs_set_avg_pct > 0 ? "+" : ""}
              {obs.enrichment.price_delta_vs_set_avg_pct.toFixed(1)}% vs avg
            </Text>
          </View>
        )}
        {obs.enrichment?.facings_share_of_set != null && (
          <View style={styles.chip}>
            <Text style={styles.chipText}>
              {obs.enrichment.facings_share_of_set.toFixed(1)}% shelf
            </Text>
          </View>
        )}
      </View>

      {/* Status and confirm */}
      <View style={styles.footer}>
        <Text
          style={[
            styles.status,
            obs.status === "confirmed" && styles.statusGreen,
            obs.status === "unmatched" && styles.statusAmber,
            obs.status === "low_confidence" && styles.statusRed,
          ]}
        >
          {obs.status.replace("_", " ")}
        </Text>
        {needsReview && onConfirm && (
          <TouchableOpacity
            style={styles.confirmBtn}
            onPress={() => onConfirm(obs.id)}
          >
            <Text style={styles.confirmText}>Confirm</Text>
          </TouchableOpacity>
        )}
      </View>

      {obs.notes ? <Text style={styles.notes}>{obs.notes}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  cardFlagged: { borderColor: "#fbbf24", borderWidth: 1.5 },
  row: { flexDirection: "row", alignItems: "center", marginBottom: 4 },
  brand: { fontSize: 15, fontWeight: "700", color: "#111827", flex: 1 },
  detail: { fontSize: 13, color: "#6b7280" },
  dot: { color: "#9ca3af", marginHorizontal: 4 },
  posChip: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 },
  chip: {
    backgroundColor: "#f3f4f6",
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  chipText: { fontSize: 11, color: "#374151" },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
  },
  status: { fontSize: 12, color: "#6b7280", textTransform: "capitalize" },
  statusGreen: { color: "#16a34a" },
  statusAmber: { color: "#d97706" },
  statusRed: { color: "#dc2626" },
  confirmBtn: {
    backgroundColor: "#1d4ed8",
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  confirmText: { color: "#fff", fontSize: 12, fontWeight: "600" },
  notes: { fontSize: 11, color: "#9ca3af", marginTop: 4, fontStyle: "italic" },
});
