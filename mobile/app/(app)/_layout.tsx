import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarStyle: { backgroundColor: "#0f172a", borderTopColor: "#1e293b", height: 60 },
        tabBarActiveTintColor: "#3b82f6",
        tabBarInactiveTintColor: "#475569",
        tabBarLabelStyle: { fontSize: 10, marginBottom: 3 },
        headerStyle: { backgroundColor: "#0f172a" },
        headerTintColor: "#f8fafc",
        headerTitleStyle: { fontWeight: "700", fontSize: 17 },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: "Dashboard",
          headerTitle: "Your Dashboard",
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="capture"
        options={{
          title: "Capture",
          headerTitle: "Capture Shelf",
          tabBarIcon: ({ color, size }) => <Ionicons name="camera-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="audits"
        options={{
          title: "Audits",
          headerTitle: "My Audits",
          tabBarIcon: ({ color, size }) => <Ionicons name="list-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen name="audit/[id]" options={{ href: null }} />
    </Tabs>
  );
}
