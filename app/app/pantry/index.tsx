import { useRouter } from "expo-router";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppHeader } from "@/components/AppHeader";
import {
  Art, Card, CategoryIcon, ErrorText, ItemIcon, Meter, Screen, SectionHeader, StatTile,
} from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useStaffPantryId } from "@/context/ProfileContext";
import { CATEGORIES, LEVEL_STYLE, Settings, stockLevel } from "@/lib/categories";
import {
  fetchActivity, fetchCategoryStock, fetchItems, fetchPantry, fetchRecentLots, timeAgo, unitsExpiringWithin,
} from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function PantryHome() {
  const router = useRouter();
  const { session } = useAuth();
  const pantryId = useStaffPantryId();
  const firstName = (session?.user.user_metadata?.full_name ?? "").split(" ")[0];

  const { data, error, refreshing, refresh } = useLoad(async () => {
    const [pantry, items, stock, activity, recent] = await Promise.all([
      fetchPantry(pantryId), fetchItems(pantryId), fetchCategoryStock(pantryId),
      fetchActivity(pantryId, 100), fetchRecentLots(pantryId, 12),
    ]);
    return { pantry, items, stock, activity, recent };
  }, [pantryId]);

  const today = new Date().toDateString();
  const inStock = data?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  const expiring = data?.items.reduce((n, i) => n + unitsExpiringWithin(i, Settings.expiringDays), 0) ?? 0;
  const justSorted = data?.activity
    .filter((a) => a.source === "robot" && a.transaction_type === "intake" && new Date(a.timestamp).toDateString() === today)
    .reduce((n, a) => n + a.quantity, 0) ?? 0;

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <AppHeader />

      <View style={styles.hero}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={Type.h1}>{greeting()}{firstName ? `,\n${firstName}!` : "!"}</Text>
          <Text style={Type.muted}>Here's what's happening at {data?.pantry.name ?? "your pantry"}.</Text>
        </View>
        <Art name="hazel-robot-hat" width={110} />
      </View>

      <View style={styles.stats}>
        <StatTile value={inStock} label="items in stock" />
        <StatTile value={expiring} label="expiring soon" color={Colors.tomato} />
        <StatTile value={justSorted} label="just sorted" color={Colors.sky} />
      </View>

      <ErrorText message={error} />

      {data && data.recent.length > 0 && (
        <View style={{ gap: 10 }}>
          <SectionHeader title="Recently added" action="See all" onAction={() => router.push("/pantry/activity")} />
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.recentRow}
            style={styles.recentScroll}
          >
            {data.recent.map((l) => (
              <Pressable key={l.id} onPress={() => router.push(`/items/${l.item.id}`)}>
                <Card style={styles.recentCard}>
                  <ItemIcon imageKey={l.item.image_key} category={l.item.category} size={56} />
                  <Text style={styles.recentName} numberOfLines={2}>{l.item.name}</Text>
                  <Text style={styles.recentQty}>+{l.quantity}</Text>
                  <Text style={Type.muted}>
                    {l.source === "robot" ? "Robot" : l.source === "scan" ? "Scanned" : "Added"} · {timeAgo(l.received_at)}
                  </Text>
                </Card>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}

      <Card style={{ gap: 14 }}>
        <SectionHeader title="Stock by category" action="See all" onAction={() => router.push("/pantry/inventory")} />
        {CATEGORIES.map((c) => {
          const row = data?.stock.find((s) => s.category === c.key);
          const units = row?.units ?? 0;
          const target = row?.target_units ?? 1;
          const level = LEVEL_STYLE[stockLevel(units, target)];
          return (
            <View key={c.key} style={styles.row}>
              <CategoryIcon category={c.key} size={30} />
              <Text style={styles.rowLabel} numberOfLines={1}>{c.label}</Text>
              <Meter units={units} target={target} />
              <Text style={[styles.level, { color: level.color === Colors.mustard ? "#A97A12" : level.color }]}>
                {level.label}
              </Text>
            </View>
          );
        })}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: Space.md, marginTop: Space.sm },
  stats: { flexDirection: "row", gap: Space.sm },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  recentScroll: { marginHorizontal: -Space.gutter },
  recentRow: { gap: 10, paddingHorizontal: Space.gutter, paddingBottom: 6 },
  recentCard: { width: 128, padding: 12, gap: 4 },
  recentName: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.text, minHeight: 34 },
  recentQty: { fontFamily: Fonts.displayHeavy, fontSize: 18, color: Colors.olive },
  rowLabel: { fontFamily: Fonts.bodySemi, fontSize: 14, color: Colors.text, width: 100 },
  level: { fontFamily: Fonts.bodyBold, fontSize: 13, width: 46, textAlign: "right" },
});
