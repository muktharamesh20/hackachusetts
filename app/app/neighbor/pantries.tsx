import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Modal, Pressable, RefreshControl, StyleSheet, Text, TextInput, View } from "react-native";
import { pantryMeta, StockChips } from "@/components/PantryBits";
import { Art, Button, Card, Chip, ErrorText, Screen } from "@/components/ui";
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

function OptionRow({ label, selected, radio, onPress }: {
  label: string; selected: boolean; radio?: boolean; onPress: () => void;
}) {
  const icon = radio
    ? selected ? "radiobox-marked" : "radiobox-blank"
    : selected ? "checkbox-marked" : "checkbox-blank-outline";
  return (
    <Pressable style={styles.option} onPress={onPress}>
      <Text style={Type.bodySemi}>{label}</Text>
      <MaterialCommunityIcons name={icon} size={22} color={selected ? Colors.sky : Colors.line} />
    </Pressable>
  );
}

/** Every pantry: search by name or town; sort + filter live in a bottom sheet. */
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

  const [sheetOpen, setSheetOpen] = useState(false);
  const filterCount = Number(openOnly) + Number(stashOnly) + Number(Boolean(need));
  const clearFilters = () => {
    setOpenOnly(false);
    setStashOnly(false);
    setNeed(null);
  };

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 4 }}>
        <Text style={Type.h1}>Pantries</Text>
        <Text style={[Type.body, { color: Colors.textMuted }]}>Everything is free. No sign-up at the door.</Text>
        </View>
        <Art name="hazel-acorn-hug" width={84} />
      </View>

      <View style={styles.searchRow}>
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
        <Pressable style={styles.sheetButton} onPress={() => setSheetOpen(true)} hitSlop={6}>
          <MaterialCommunityIcons name="tune-variant" size={22} color={Colors.text} />
          {filterCount > 0 && (
            <View style={styles.countBadge}>
              <Text style={styles.countText}>{filterCount}</Text>
            </View>
          )}
        </Pressable>
      </View>

      <Modal visible={sheetOpen} transparent animationType="slide" onRequestClose={() => setSheetOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setSheetOpen(false)} />
        <View style={styles.sheet}>
          <View style={styles.grabber} />
          <View style={styles.sheetHeader}>
            <Text style={Type.h2}>Sort & filter</Text>
            {filterCount > 0 && <Text style={styles.clear} onPress={clearFilters}>Clear filters</Text>}
          </View>

          <Text style={Type.label}>SORT BY</Text>
          {SORTS.map((o) => (
            <OptionRow
              key={o.key}
              label={o.key === "nearest" && !origin ? "Nearest (turn on location)" : o.label}
              selected={sort === o.key}
              radio
              onPress={() => setSort(o.key)}
            />
          ))}

          <Text style={[Type.label, { marginTop: Space.md }]}>SHOW ONLY</Text>
          <OptionRow label="Open now" selected={openOnly} onPress={() => setOpenOnly((v) => !v)} />
          <OptionRow label="Live stock on Stash" selected={stashOnly} onPress={() => setStashOnly((v) => !v)} />

          <Text style={[Type.label, { marginTop: Space.md }]}>HAS IN STOCK</Text>
          <View style={styles.wrap}>
            {CATEGORIES.map((c) => (
              <Chip
                key={c.key}
                label={c.label}
                active={need === c.key}
                color={Colors.sky}
                onPress={() => setNeed(need === c.key ? null : c.key)}
              />
            ))}
          </View>

          <Button
            title={`Show ${pantries.length} ${pantries.length === 1 ? "pantry" : "pantries"}`}
            color={Colors.sky}
            dark={Colors.skyDark}
            onPress={() => setSheetOpen(false)}
            style={{ marginTop: Space.lg }}
          />
        </View>
      </Modal>

      <ErrorText message={error} />
      {data && (
        <Text style={Type.muted}>
          {pantries.length} {pantries.length === 1 ? "pantry" : "pantries"} · {SORTS.find((o) => o.key === sort)?.label.toLowerCase()}
          {filterCount > 0 ? ` · ${filterCount} ${filterCount === 1 ? "filter" : "filters"}` : ""}
        </Text>
      )}

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
  // Hazel sized to the title + tagline block, beside it.
  header: { flexDirection: "row", alignItems: "center", gap: Space.md },
  searchRow: { flexDirection: "row", gap: Space.sm, alignItems: "center" },
  search: {
    flex: 1, flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: Colors.card,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.line, paddingHorizontal: 14,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 15, color: Colors.text },
  sheetButton: {
    width: 48, height: 48, borderRadius: 24, backgroundColor: Colors.card, borderWidth: 1.5,
    borderColor: Colors.line, alignItems: "center", justifyContent: "center",
  },
  countBadge: {
    position: "absolute", top: -2, right: -2, minWidth: 20, height: 20, borderRadius: 10,
    backgroundColor: Colors.sky, alignItems: "center", justifyContent: "center", paddingHorizontal: 5,
  },
  countText: { fontFamily: Fonts.bodyHeavy, fontSize: 11, color: Colors.white },
  backdrop: { flex: 1, backgroundColor: "#0006" },
  sheet: {
    backgroundColor: Colors.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28,
    padding: Space.gutter, paddingBottom: 40, gap: 4,
  },
  grabber: { alignSelf: "center", width: 40, height: 5, borderRadius: 3, backgroundColor: Colors.line, marginBottom: Space.sm },
  sheetHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: Space.sm },
  option: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  clear: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.sky },
  top: { flexDirection: "row", gap: 12, alignItems: "center" },
});
