import React, { useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator,
  FlatList, Pressable, Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import * as api from "../../lib/api";

type Account = {
  id: string;
  name: string;
  channel_type: string;
};

type Insight = {
  audit_id: string;
  captured_at: string;
  status: string;
  observation_count: number;
  confirmed_count: number;
  unmatched_count: number;
  total_facings: number;
  avg_brand_confidence: number;
  latest_quality_score: number;
};

export default function StoresInsightsScreen() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const response = await api.getAccounts();
        setAccounts(response || []);
        if (response && response.length > 0) {
          setSelectedAccount(response[0]);
          fetchInsights(response[0].id);
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load stores");
      } finally {
        setLoading(false);
      }
    };

    fetchAccounts();
  }, []);

  const fetchInsights = async (accountId: string) => {
    setLoadingInsights(true);
    try {
      const response = await api.getJSON(`/stores/${accountId}/insights`);
      setInsights(response.insights || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoadingInsights(false);
    }
  };

  const handleSelectAccount = (account: Account) => {
    setSelectedAccount(account);
    fetchInsights(account.id);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <ActivityIndicator color="#3b82f6" size="large" />
          <Text style={styles.loadingText}>Loading stores...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || accounts.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <Text style={styles.error}>{error || "No stores found"}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>🏪 Store Insights</Text>

        {/* Store Selector */}
        <FlatList
          data={accounts}
          horizontal
          scrollEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.storeList}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => handleSelectAccount(item)}
              style={[
                styles.storeTab,
                selectedAccount?.id === item.id && styles.storeTabActive,
              ]}
            >
              <Text
                style={[
                  styles.storeTabText,
                  selectedAccount?.id === item.id && styles.storeTabTextActive,
                ]}
              >
                {item.name.split(" -")[0]}
              </Text>
            </Pressable>
          )}
        />

        {/* Insights */}
        {loadingInsights ? (
          <View style={styles.centerContent}>
            <ActivityIndicator color="#3b82f6" size="small" />
            <Text style={styles.loadingText}>Loading insights...</Text>
          </View>
        ) : insights.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No audits for this store yet</Text>
          </View>
        ) : (
          insights.map((insight, idx) => (
            <View key={idx} style={styles.insightCard}>
              <View style={styles.insightHeader}>
                <Text style={styles.insightDate}>
                  {new Date(insight.captured_at).toLocaleDateString()}
                </Text>
                <View
                  style={[
                    styles.statusBadge,
                    {
                      backgroundColor:
                        insight.status === "final"
                          ? "#dcfce7"
                          : insight.status === "retake_required"
                          ? "#fee2e2"
                          : "#f3f4f6",
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.statusText,
                      {
                        color:
                          insight.status === "final"
                            ? "#15803d"
                            : insight.status === "retake_required"
                            ? "#991b1b"
                            : "#374151",
                      },
                    ]}
                  >
                    {insight.status.replace(/_/g, " ")}
                  </Text>
                </View>
              </View>

              <View style={styles.insightStats}>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{insight.observation_count}</Text>
                  <Text style={styles.statLabel}>Items</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{insight.confirmed_count}</Text>
                  <Text style={styles.statLabel}>Confirmed</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>{insight.total_facings}</Text>
                  <Text style={styles.statLabel}>Facings</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={styles.statValue}>
                    {Math.round(insight.latest_quality_score * 100)}%
                  </Text>
                  <Text style={styles.statLabel}>Quality</Text>
                </View>
              </View>

              <Pressable
                onPress={() =>
                  router.push(`/audit/${insight.audit_id}`)
                }
                style={styles.viewBtn}
              >
                <Text style={styles.viewBtnText}>View Details →</Text>
              </Pressable>
            </View>
          ))
        )}
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
  title: { fontSize: 28, fontWeight: "800", color: "#0f172a", marginBottom: 16 },
  storeList: { marginBottom: 20, paddingRight: 16 },
  storeTab: {
    backgroundColor: "#e2e8f0",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 8,
  },
  storeTabActive: { backgroundColor: "#3b82f6" },
  storeTabText: { color: "#475569", fontSize: 13, fontWeight: "600" },
  storeTabTextActive: { color: "#fff" },
  emptyState: { alignItems: "center", justifyContent: "center", minHeight: 150 },
  emptyText: { color: "#94a3b8", fontSize: 14 },
  insightCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  insightHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  insightDate: { fontSize: 13, color: "#64748b", fontWeight: "600" },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  statusText: { fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  insightStats: {
    flexDirection: "row",
    justifyContent: "space-around",
    paddingVertical: 12,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 12,
  },
  statItem: { alignItems: "center" },
  statValue: { fontSize: 18, fontWeight: "800", color: "#0f172a" },
  statLabel: { fontSize: 10, color: "#94a3b8", marginTop: 2 },
  viewBtn: {
    backgroundColor: "#3b82f6",
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: "center",
  },
  viewBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
