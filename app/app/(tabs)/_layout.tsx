import { Tabs } from "expo-router";
import { Text } from "react-native";
import { Colors } from "@/theme/colors";

function Icon({ emoji, color }: { emoji: string; color: string }) {
  return <Text style={{ fontSize: 22, color }}>{emoji}</Text>;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: Colors.primary },
        headerTintColor: "#fff",
        headerTitleStyle: { fontWeight: "800" },
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textMuted,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Inventory",
          tabBarIcon: ({ color }) => <Icon emoji="📦" color={color} />,
        }}
      />
      <Tabs.Screen
        name="distribute"
        options={{
          title: "Distribute",
          tabBarIcon: ({ color }) => <Icon emoji="⏳" color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ color }) => <Icon emoji="⚙️" color={color} />,
        }}
      />
    </Tabs>
  );
}
