import { Tabs } from "expo-router";
import { tabIcon, tabOptions } from "@/components/AppHeader";

export default function NeighborTabs() {
  return (
    <Tabs screenOptions={tabOptions("neighbor")}>
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: tabIcon("home-variant-outline"), headerShown: true }} />
      <Tabs.Screen name="pantries" options={{ title: "Pantries", tabBarIcon: tabIcon("storefront-outline") }} />
      <Tabs.Screen name="resources" options={{ title: "Resources", tabBarIcon: tabIcon("book-open-variant") }} />
      <Tabs.Screen name="saved" options={{ title: "Saved", tabBarIcon: tabIcon("bookmark-outline") }} />
      <Tabs.Screen name="more" options={{ title: "More", tabBarIcon: tabIcon("menu") }} />
    </Tabs>
  );
}
