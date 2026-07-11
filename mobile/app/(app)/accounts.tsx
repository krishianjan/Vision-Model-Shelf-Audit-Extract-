import React, { useEffect, useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { getAccounts, type Account } from "../../lib/api";
import { useStore } from "../../lib/store";

export default function AccountsScreen() {
  const router = useRouter();
  const { setSelectedAccount } = useStore();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAccounts()
      .then(setAccounts)
      .catch((err) => console.error("Failed to load accounts:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleSelectAccount = (account: Account) => {
    setSelectedAccount(account);
    router.push("/(app)/capture");
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#3b82f6" size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Select Store</Text>
      </View>
      <FlatList
        data={accounts}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.accountButton}
            onPress={() => handleSelectAccount(item)}
          >
            <View style={styles.accountContent}>
              <Text style={styles.accountName}>{item.name}</Text>
              {item.address && <Text style={styles.accountAddress}>{item.address}</Text>}
            </View>
            <Text style={styles.arrow}>→</Text>
          </TouchableOpacity>
        )}
        contentContainerStyle={styles.listContent}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  header: { paddingHorizontal: 16, paddingVertical: 12, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#e5e7eb" },
  title: { fontSize: 20, fontWeight: "700", color: "#111827" },
  listContent: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  accountButton: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: "#fff", padding: 14, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb" },
  accountContent: { flex: 1 },
  accountName: { fontSize: 16, fontWeight: "600", color: "#111827" },
  accountAddress: { fontSize: 12, color: "#6b7280", marginTop: 4 },
  arrow: { fontSize: 18, color: "#9ca3af" },
});
