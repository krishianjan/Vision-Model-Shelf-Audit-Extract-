import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface Props {
  value: number | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

function tier(v: number) {
  if (v >= 0.8) return { bg: "#16a34a", text: "#fff", label: "HIGH" };
  if (v >= 0.6) return { bg: "#d97706", text: "#fff", label: "MED" };
  return { bg: "#dc2626", text: "#fff", label: "LOW" };
}

export function ConfidenceBadge({ value, label, size = "md" }: Props) {
  if (value == null) return null;
  const { bg, text, label: tier_label } = tier(value);
  const pct = Math.round(value * 100);
  const isSmall = size === "sm";

  return (
    <View style={[styles.badge, { backgroundColor: bg }, isSmall && styles.sm]}>
      <Text style={[styles.text, { color: text }, isSmall && styles.smText]}>
        {label ?? tier_label} {pct}%
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  sm: { paddingHorizontal: 5, paddingVertical: 2, borderRadius: 4 },
  text: { fontSize: 12, fontWeight: "600" },
  smText: { fontSize: 10 },
});
