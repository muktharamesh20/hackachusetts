import { Tabs } from "expo-router";
import { tabIcon, tabOptions } from "@/components/AppHeader";

export default function PantryTabs() {
  return (
    <Tabs screenOptions={tabOptions("pantry")}>
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: tabIcon("home-variant-outline"), headerShown: true }} />
      <Tabs.Screen name="inventory" options={{ title: "Inventory", tabBarIcon: tabIcon("clipboard-text-outline") }} />
      <Tabs.Screen name="scan" options={{ title: "Scan", tabBarIcon: tabIcon("barcode-scan") }} />
      <Tabs.Screen name="activity" options={{ title: "Activity", tabBarIcon: tabIcon("pulse") }} />
      <Tabs.Screen name="more" options={{ title: "More", tabBarIcon: tabIcon("menu") }} />
    </Tabs>
  );
}
