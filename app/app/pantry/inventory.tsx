import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Badge, Card, Chip, EmptyState, ErrorText, ExpiryBadge, ItemIcon } from "@/components/ui";
import { useStaffPantryId } from "@/context/ProfileContext";
import { CATEGORIES, categoryInfo } from "@/lib/categories";
import { fetchItems, Item, unitsExpiringWithin } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

const SOON_DAYS = 2;

function lotsLabel(item: Item): string {
  const n = item.inventory_lots?.length ?? 0;
  return `${n} ${n === 1 ? "lot" : "lots"}`;
}

/** "3 expire ≤2d" when units are about to expire; otherwise the next expiry date. */
function SoonBadge({ item }: { item: Item }) {
  const soon = unitsExpiringWithin(item, SOON_DAYS);
  if (soon > 0) return <Badge label={`${soon} expiring ≤${SOON_DAYS}d`} color={Colors.tomato} soft={Colors.tomatoSoft} />;
  return <ExpiryBadge date={item.expiration_date} />;
}

export default function Inventory() {
  const router = useRouter();
  const pantryId = useStaffPantryId();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const { data, error, refreshing, refresh } = useLoad(() => fetchItems(pantryId), [pantryId]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter(
      (i) => (!category || i.category === category) && (!q || i.name.toLowerCase().includes(q)),
    );
  }, [data, query, category]);

  const renderItem = ({ item }: { item: Item }) => (
    <Card style={styles.row} onPress={() => router.push(`/items/${item.id}`)}>
      <ItemIcon imageKey={item.image_key} category={item.category} size={48} />
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={Type.h3} numberOfLines={1}>{item.name}</Text>
        <Text style={Type.muted}>
          {item.quantity} on hand · {lotsLabel(item)} · {categoryInfo(item.category).label}
        </Text>
        {item.allergens?.length > 0 && (
          <View style={styles.pills}>
            {item.allergens.map((a) => (
              <Text key={a} style={styles.allergen}>{a[0].toUpperCase() + a.slice(1)}</Text>
            ))}
          </View>
        )}
      </View>
      <SoonBadge item={item} />
    </Card>
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={Type.h1}>Inventory</Text>
        <View style={styles.search}>
          <MaterialCommunityIcons name="magnify" size={20} color={Colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search items"
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={setQuery}
          />
        </View>
      </View>
      <View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          <Chip label="All" active={!category} onPress={() => setCategory(null)} />
          {CATEGORIES.map((c) => (
            <Chip key={c.key} label={c.label} active={category === c.key} onPress={() => setCategory(c.key)} />
          ))}
        </ScrollView>
      </View>
      <ErrorText message={error} />
      <FlatList
        data={items}
        keyExtractor={(i) => i.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        ListEmptyComponent={data ? <EmptyState title="Nothing here yet" body="Scan items in to stash them." /> : null}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  header: { paddingHorizontal: Space.gutter, gap: Space.md, paddingTop: Space.sm },
  search: {
    flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: Colors.card,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.line, paddingHorizontal: 14,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 15, color: Colors.text },
  chips: { gap: 8, paddingHorizontal: Space.gutter, paddingVertical: Space.md },
  list: { paddingHorizontal: Space.gutter, paddingBottom: Space.xxl, gap: 10 },
  row: { flexDirection: "row", alignItems: "center", gap: Space.md, padding: 14 },
  pills: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  allergen: {
    fontFamily: Fonts.bodyBold, fontSize: 11, color: Colors.textMuted, backgroundColor: Colors.cardAlt,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radii.pill, overflow: "hidden",
  },
});
