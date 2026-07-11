import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator,
  SectionList, Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as api from "../../lib/api";

type DashboardSummary = {
  stores_visited: number;
  total_audits: number;
  completed_audits: number;
  avg_quality_score: number;
  pending_review_count: number;
};

export default function DashboardScreen() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await api.getJSON("/reps/me/dashboard");
        setSummary(response.summary);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <ActivityIndicator color="#3b82f6" size="large" />
          <Text style={styles.loadingText}>Loading dashboard...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !summary) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <Text style={styles.error}>{error || "Failed to load dashboard"}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const cards = [
    { label: "Stores Visited", value: summary.stores_visited, color: "#3b82f6" },
    { label: "Total Audits", value: summary.total_audits, color: "#8b5cf6" },
    { label: "Completed", value: summary.completed_audits, color: "#16a34a" },
    {
      label: "Avg Quality",
      value: `${Math.round(summary.avg_quality_score * 100)}%`,
      color: summary.avg_quality_score >= 0.8 ? "#16a34a" : "#f59e0b",
    },
    { label: "Pending Review", value: summary.pending_review_count, color: "#dc2626" },
  ];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>📊 Your Dashboard</Text>

        <View style={styles.cardsContainer}>
          {cards.map((card, idx) => (
            <View key={idx} style={styles.card}>
              <Text style={[styles.cardValue, { color: card.color }]}>
                {card.value}
              </Text>
              <Text style={styles.cardLabel}>{card.label}</Text>
            </View>
          ))}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ℹ️ How It Works</Text>
          <Text style={styles.helpText}>
            Your dashboard updates as you capture and complete audits. Upload shelf
            photos to see statistics appear here.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  scrollContent: { padding: 16, paddingBottom: 32 },
  centerContent: { flex: 1, justifyContent: "center", alignItems: "center" },
  loadingText: { marginTop: 12, color: "#64748b", fontSize: 16 },
  error: { color: "#dc2626", fontSize: 16, textAlign: "center" },
  title: { fontSize: 28, fontWeight: "800", color: "#0f172a", marginBottom: 20 },
  cardsContainer: {
    display: "flex",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginBottom: 24,
  },
  card: {
    flex: 1,
    minWidth: "48%",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardValue: { fontSize: 24, fontWeight: "800", marginBottom: 4 },
  cardLabel: { fontSize: 12, color: "#94a3b8", fontWeight: "600" },
  section: { backgroundColor: "#f0f4f8", borderRadius: 12, padding: 16 },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: "#0f172a", marginBottom: 8 },
  helpText: { fontSize: 13, color: "#475569", lineHeight: 20 },
});
