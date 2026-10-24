import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { pantryMeta, StockChips } from "@/components/PantryBits";
import { Art, Card, Chip, ErrorText, Screen } from "@/components/ui";
import { CATEGORIES, stockLevel } from "@/lib/categories";
import { useUserLocation } from "@/lib/location";
import { distanceMiles, fetchCategoryStock, fetchPantries, isOpenNow, Pantry } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

type Sort = "nearest" | "name" | "open";

const SORTS: { key: Sort; label: string }[] = [
  { key: "nearest", label: "Nearest" },
  { key: "open", label: "Open now first" },
  { key: "name", label: "A–Z" },
];

/** Every pantry: search by name or town, sort, and filter by what's in stock. */
export default function Pantries() {
  const router = useRouter();
  const origin = useUserLocation();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("nearest");
  const [openOnly, setOpenOnly] = useState(false);
  const [stashOnly, setStashOnly] = useState(false);
  const [need, setNeed] = useState<string | null>(null);
  const { data, error, refreshing, refresh } = useLoad(async () => {
    const [pantries, stock] = await Promise.all([fetchPantries(), fetchCategoryStock()]);
    return { pantries, stock };
  });

  const hasStock = (p: Pantry, category: string) => {
    const s = data?.stock.find((x) => x.pantry_id === p.id && x.category === category);
    return s ? stockLevel(s.units, s.target_units) !== "low" : false;
  };

  const pantries = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (data?.pantries ?? []).filter(
      (p) =>
        (!q || `${p.name} ${p.address} ${p.city}`.toLowerCase().includes(q)) &&
        (!openOnly || isOpenNow(p)) &&
        (!stashOnly || p.on_stash) &&
        (!need || hasStock(p, need)),
    );
    const dist = (p: Pantry) => (origin ? distanceMiles(origin, p) : 0);
    return list.sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "open" && isOpenNow(a) !== isOpenNow(b)) return isOpenNow(a) ? -1 : 1;
      return origin ? dist(a) - dist(b) : a.name.localeCompare(b.name);
    });
  }, [data, origin, query, sort, openOnly, stashOnly, need]);

  const filtersOn = openOnly || stashOnly || need;

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <Text style={Type.h1}>Pantries</Text>
      <Text style={Type.muted}>Everything is free. No sign-up at the door.</Text>

      <View style={styles.search}>
        <MaterialCommunityIcons name="magnify" size={20} color={Colors.textMuted} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name or town"
          placeholderTextColor={Colors.textMuted}
          value={query}
          onChangeText={setQuery}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>

      <View style={{ gap: 8 }}>
        <Text style={Type.label}>SORT</Text>
        <View style={styles.row}>
          {SORTS.map((s) => (
            <Chip
              key={s.key}
              label={s.key === "nearest" && !origin ? "Nearest (needs location)" : s.label}
              active={sort === s.key}
              color={Colors.sky}
              onPress={() => setSort(s.key)}
            />
          ))}
        </View>
      </View>

      <View style={{ gap: 8 }}>
        <View style={styles.filterHeader}>
          <Text style={Type.label}>FILTER</Text>
          {filtersOn && (
            <Text
              style={styles.clear}
              onPress={() => {
                setOpenOnly(false);
                setStashOnly(false);
                setNeed(null);
              }}
            >
              Clear
            </Text>
          )}
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scrollRow}>
          <Chip label="Open now" active={openOnly} color={Colors.sky} onPress={() => setOpenOnly((v) => !v)} />
          <Chip label="Live stock on Stash" active={stashOnly} color={Colors.sky} onPress={() => setStashOnly((v) => !v)} />
          {CATEGORIES.map((c) => (
            <Chip
              key={c.key}
              label={`Has ${c.label.toLowerCase()}`}
              active={need === c.key}
              color={Colors.sky}
              onPress={() => setNeed(need === c.key ? null : c.key)}
            />
          ))}
        </ScrollView>
      </View>

      <ErrorText message={error} />
      {data && <Text style={Type.muted}>{pantries.length} {pantries.length === 1 ? "pantry" : "pantries"}</Text>}

      {pantries.map((p) => (
        <Card key={p.id} style={{ gap: 10 }} onPress={() => router.push(`/pantries/${p.id}`)}>
          <View style={styles.top}>
            <Art name={p.image_key ?? "illus-pantry-storefront"} width={70} height={58} rounded={12} cover={Boolean(p.image_key)} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={Type.h3}>{p.name}</Text>
              <Text style={Type.muted}>{pantryMeta(p, origin)}</Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
          </View>
          {p.on_stash && <StockChips stock={data!.stock} pantryId={p.id} />}
        </Card>
      ))}
      {data && pantries.length === 0 && (
        <Text style={[Type.muted, { textAlign: "center" }]}>No pantries match. Try clearing a filter.</Text>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  search: {
    flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: Colors.card,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.line, paddingHorizontal: 14,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 15, color: Colors.text },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  scrollRow: { flexDirection: "row", gap: 8 },
  filterHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  clear: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.sky },
  top: { flexDirection: "row", gap: 12, alignItems: "center" },
});
