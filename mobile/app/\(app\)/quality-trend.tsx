import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator,
  Dimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as api from "../../lib/api";

type TrendData = {
  audit_date: string;
  audit_count: number;
  avg_quality: number;
  successful_audits: number;
  failed_audits: number;
};

const { width } = Dimensions.get("window");
const CHART_WIDTH = width - 32;

export default function QualityTrendScreen() {
  const [trend, setTrend] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTrend = async () => {
      try {
        const response = await api.getJSON("/reps/me/quality-trend");
        setTrend(response.trend || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load quality trend");
      } finally {
        setLoading(false);
      }
    };

    fetchTrend();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <ActivityIndicator color="#3b82f6" size="large" />
          <Text style={styles.loadingText}>Loading quality trend...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <Text style={styles.error}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const avgQuality = trend.length > 0
    ? Math.round(
        (trend.reduce((sum, d) => sum + d.avg_quality, 0) / trend.length) * 100
      )
    : 0;
  const totalAudits = trend.reduce((sum, d) => sum + d.audit_count, 0);
  const totalSuccessful = trend.reduce((sum, d) => sum + d.successful_audits, 0);

  const maxQuality = Math.max(...trend.map((d) => d.avg_quality), 0.8);
  const chartHeight = 150;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>📈 Quality Trend (14 Days)</Text>

        {/* Summary Stats */}
        <View style={styles.statsContainer}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{avgQuality}%</Text>
            <Text style={styles.statLabel}>Avg Quality</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{totalAudits}</Text>
            <Text style={styles.statLabel}>Total Audits</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{totalSuccessful}</Text>
            <Text style={styles.statLabel}>Completed</Text>
          </View>
        </View>

        {/* Chart */}
        {trend.length > 0 ? (
          <View style={styles.chartContainer}>
            <View style={styles.chartArea}>
              {/* Y-axis labels */}
              <View style={styles.yAxisLabels}>
                <Text style={styles.yLabel}>100%</Text>
                <Text style={styles.yLabel}>75%</Text>
                <Text style={styles.yLabel}>50%</Text>
                <Text style={styles.yLabel}>25%</Text>
                <Text style={styles.yLabel}>0%</Text>
              </View>

              {/* Chart bars */}
              <View style={styles.chart}>
                {trend.map((d, idx) => {
                  const height = (d.avg_quality / maxQuality) * chartHeight;
                  const isPass = d.avg_quality >= 0.8;
                  return (
                    <View key={idx} style={styles.barContainer}>
                      <View
                        style={[
                          styles.bar,
                          {
                            height,
                            backgroundColor: isPass ? "#16a34a" : "#f59e0b",
                          },
                        ]}
                      />
                      <Text style={styles.barLabel}>
                        {new Date(d.audit_date).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </Text>
                    </View>
                  );
                })}
              </View>
            </View>
          </View>
        ) : (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No quality data yet</Text>
          </View>
        )}

        {/* Legend */}
        <View style={styles.legend}>
          <View style={styles.legendItem}>
            <View style={[styles.legendColor, { backgroundColor: "#16a34a" }]} />
            <Text style={styles.legendText}>Good (≥80%)</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendColor, { backgroundColor: "#f59e0b" }]} />
            <Text style={styles.legendText}>Needs Improvement ({'<'}80%)</Text>
          </View>
        </View>

        {/* Insights */}
        <View style={styles.insights}>
          <Text style={styles.insightsTitle}>💡 Insights</Text>
          <Text style={styles.insightText}>
            • Keep lighting consistent for better image quality
          </Text>
          <Text style={styles.insightText}>
            • Avoid glare and motion blur by holding steady
          </Text>
          <Text style={styles.insightText}>
            • Position shelf fully in frame for best extraction
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  scrollContent: { padding: 16, paddingBottom: 32 },
  centerContent: { flex: 1, justifyContent: "center", alignItems: "center", minHeight: 200 },
  loadingText: { marginTop: 12, color: "#64748b", fontSize: 14 },
  error: { color: "#dc2626", fontSize: 16, textAlign: "center" },
  title: { fontSize: 28, fontWeight: "800", color: "#0f172a", marginBottom: 20 },
  statsContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 24,
  },
  statBox: {
    flex: 1,
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  statValue: { fontSize: 20, fontWeight: "800", color: "#3b82f6", marginBottom: 4 },
  statLabel: { fontSize: 11, color: "#94a3b8", fontWeight: "600" },
  chartContainer: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  chartArea: { flexDirection: "row", gap: 12 },
  yAxisLabels: {
    justifyContent: "space-between",
    width: 35,
    paddingRight: 8,
  },
  yLabel: { fontSize: 10, color: "#94a3b8", textAlign: "right" },
  chart: {
    flex: 1,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 4,
    height: 150,
  },
  barContainer: { flex: 1, alignItems: "center" },
  bar: { width: "100%", borderRadius: 4 },
  barLabel: { fontSize: 9, color: "#94a3b8", marginTop: 4, textAlign: "center" },
  emptyState: { alignItems: "center", justifyContent: "center", minHeight: 150 },
  emptyText: { color: "#94a3b8", fontSize: 14 },
  legend: { flexDirection: "row", gap: 16, marginBottom: 20 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendColor: { width: 12, height: 12, borderRadius: 2 },
  legendText: { fontSize: 12, color: "#475569" },
  insights: {
    backgroundColor: "#f0f4f8",
    borderRadius: 12,
    padding: 14,
  },
  insightsTitle: { fontSize: 13, fontWeight: "700", color: "#0f172a", marginBottom: 8 },
  insightText: { fontSize: 12, color: "#475569", lineHeight: 18, marginBottom: 4 },
});
