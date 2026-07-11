import { useEffect } from "react";
import { Stack } from "expo-router";
import { AppState, AppStateStatus } from "react-native";
import { syncPendingCaptures } from "../lib/sync";

export default function RootLayout() {
  useEffect(() => {
    // Delay sync until app is rendered — prevents crash on startup
    const timer = setTimeout(() => {
      syncPendingCaptures().catch(err => console.error("Sync error:", err));
    }, 500);

    // Sync on every app foreground — handles cooler/no-signal scenario
    const sub = AppState.addEventListener("change", (state: AppStateStatus) => {
      if (state === "active") {
        syncPendingCaptures().catch(err => console.error("Sync error:", err));
      }
    });

    return () => {
      clearTimeout(timer);
      sub.remove();
    };
  }, []);

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="login" />
      <Stack.Screen name="(app)" options={{ headerShown: false }} />
    </Stack>
  );
}
