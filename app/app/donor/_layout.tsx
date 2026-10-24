import { Tabs } from "expo-router";
import { tabIcon, tabOptions } from "@/components/AppHeader";

export default function DonorTabs() {
  return (
    <Tabs screenOptions={tabOptions("donor")}>
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: tabIcon("home-variant-outline"), headerShown: true }} />
      <Tabs.Screen name="needs" options={{ title: "Needs", tabBarIcon: tabIcon("heart-outline") }} />
      <Tabs.Screen name="give" options={{ title: "Give", tabBarIcon: tabIcon("hand-heart-outline") }} />
      <Tabs.Screen name="scan" options={{ title: "Scan", tabBarIcon: tabIcon("barcode-scan") }} />
      {/* Share lives behind the "Spread the word" card on Home. */}
      <Tabs.Screen name="share" options={{ href: null }} />
      <Tabs.Screen name="more" options={{ title: "More", tabBarIcon: tabIcon("menu") }} />
    </Tabs>
  );
}
