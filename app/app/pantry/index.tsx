import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppHeader } from "@/components/AppHeader";
import {
  Art, Button, Card, CategoryIcon, ErrorText, ItemIcon, Meter, Screen, SectionHeader, StatTile,
} from "@/components/ui";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useStaffPantryId } from "@/context/ProfileContext";
import { CATEGORIES, Settings } from "@/lib/categories";
import {
  acceptDropoffs, Dropoff, fetchActivity, fetchCategoryStock, fetchItems, fetchPantry, fetchPendingDropoffs,
  fetchRecentLots, timeAgo, unitsExpiringWithin,
} from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, Tint } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const SOURCE_SHORT: Record<string, string> = { robot: "Robot", scan: "Scanned", donor: "Donor", manual: "Added" };

type Bag = { id: string; donor: string; units: number; names: string; at: string };

/** Group pending drop-off rows by donor bag. */
function bags(rows: Dropoff[]): Bag[] {
  const map = new Map<string, Bag>();
  for (const d of rows) {
    const b = map.get(d.batch_id) ?? { id: d.batch_id, donor: d.donor_name ?? "A neighbor", units: 0, names: "", at: d.created_at };
    b.units += d.quantity;
    b.names = b.names ? `${b.names}, ${d.name}` : d.name;
    map.set(d.batch_id, b);
  }
  return [...map.values()];
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function PantryHome() {
  const router = useRouter();
  const { session } = useAuth();
  const pantryId = useStaffPantryId();
  const firstName = (session?.user.user_metadata?.full_name ?? "").split(" ")[0];

  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);
  const { data, error, refreshing, refresh, reload } = useLoad(async () => {
    const [pantry, items, stock, activity, recent, dropoffs] = await Promise.all([
      fetchPantry(pantryId), fetchItems(pantryId), fetchCategoryStock(pantryId),
      fetchActivity(pantryId, 100), fetchRecentLots(pantryId, 12), fetchPendingDropoffs(pantryId),
    ]);
    return { pantry, items, stock, activity, recent, dropoffs };
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

      {data && data.dropoffs.length > 0 && (
        <Card style={styles.dropoffCard}>
          <View style={styles.dropoffTop}>
            <Art name="illus-donate-food" width={56} />
            <View style={{ flex: 1 }}>
              <Text style={Type.h3}>
                {data.dropoffs.reduce((n, d) => n + d.quantity, 0)} items scanned in by donors
              </Text>
              <Text style={Type.muted}>Tap a bag to check it, or scan the slip in its box.</Text>
            </View>
          </View>
          {bags(data.dropoffs).map((bag) => (
            <Pressable key={bag.id} style={styles.bagRow} onPress={() => router.push(`/dropoffs/${bag.id}`)}>
              <View style={{ flex: 1 }}>
                <Text style={Type.bodySemi}>{bag.donor}'s bag · {bag.units} {bag.units === 1 ? "item" : "items"}</Text>
                <Text style={Type.muted} numberOfLines={1}>{bag.names}</Text>
              </View>
              <Text style={Type.muted}>{timeAgo(bag.at)}</Text>
              <MaterialCommunityIcons name="chevron-right" size={22} color={Colors.text} />
            </Pressable>
          ))}
          <ErrorText message={acceptError} />
          <Button
            title="Add all to stock"
            icon="check-all"
            color={Colors.olive}
            dark={Colors.oliveDark}
            loading={accepting}
            onPress={async () => {
              setAccepting(true);
              setAcceptError(null);
              try {
                await acceptDropoffs(data.dropoffs.map((d) => d.id));
                await reload();
              } catch (e: any) {
                setAcceptError(e?.message ?? "Couldn't add them");
              } finally {
                setAccepting(false);
              }
            }}
          />
        </Card>
      )}

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
                    {SOURCE_SHORT[l.source] ?? "Added"} · {timeAgo(l.received_at)}
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
          return (
            <View key={c.key} style={styles.row}>
              <CategoryIcon category={c.key} size={30} />
              <Text style={styles.rowLabel} numberOfLines={1}>{c.label}</Text>
              <Meter units={units} target={target} />
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
  dropoffCard: { gap: 12, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  dropoffTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  bagRow: {
    flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 10,
    borderTopWidth: 1, borderTopColor: Tint.olive.border,
  },
  recentScroll: { marginHorizontal: -Space.gutter },
  recentRow: { gap: 10, paddingHorizontal: Space.gutter, paddingBottom: 6 },
  recentCard: { width: 128, padding: 12, gap: 4 },
  recentName: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.text, minHeight: 34 },
  recentQty: { fontFamily: Fonts.displayHeavy, fontSize: 18, color: Colors.olive },
  rowLabel: { fontFamily: Fonts.bodySemi, fontSize: 14, color: Colors.text, width: 100 },
});
