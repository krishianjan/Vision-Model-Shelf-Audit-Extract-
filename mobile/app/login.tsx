import React, { useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { signIn, type AuthUser } from "../lib/auth";
import { useStore } from "../lib/store";

export default function LoginScreen() {
  const router = useRouter();
  const { setUser } = useStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin() {
    setError(null);
    setLoading(true);
    try {
      const user = await signIn(email.trim(), password);
      setUser({
        user_id: user.user_id,
        org_id: user.org_id,
        email: user.email,
        token: "", // Token is stored separately in secure storage
      });
      router.replace("/(app)/accounts");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Text style={styles.title}>Kosha</Text>
      <Text style={styles.subtitle}>Shelf Audit</Text>

      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor="#9ca3af"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#9ca3af"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="password"
      />

      {error && <Text style={styles.error}>{error}</Text>}

      <TouchableOpacity
        style={[styles.btn, loading && styles.btnDisabled]}
        onPress={handleLogin}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>Sign In</Text>
        )}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1, backgroundColor: "#111827",
    justifyContent: "center", padding: 28,
  },
  title: {
    fontSize: 40, fontWeight: "800", color: "#fff",
    textAlign: "center", letterSpacing: 2,
  },
  subtitle: {
    fontSize: 16, color: "#9ca3af", textAlign: "center", marginBottom: 40,
  },
  input: {
    backgroundColor: "#1f2937", borderRadius: 10,
    color: "#fff", paddingHorizontal: 16, paddingVertical: 14,
    fontSize: 16, marginBottom: 12,
    borderWidth: 1, borderColor: "#374151",
  },
  error: { color: "#f87171", textAlign: "center", marginBottom: 8 },
  btn: {
    backgroundColor: "#2563eb", borderRadius: 10,
    paddingVertical: 15, alignItems: "center", marginTop: 8,
  },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
