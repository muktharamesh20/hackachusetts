import { MaterialCommunityIcons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import { Art, Card } from "@/components/ui";
import { CATEGORIES, stockLevel } from "@/lib/categories";
import { LatLng } from "@/lib/location";
import { CategoryStock, distanceMiles, hoursLabel, isOpenNow, Pantry } from "@/lib/stash";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Type } from "@/theme/type";

export function pantryMeta(p: Pantry, origin: LatLng | null): string {
  const parts = [];
  if (origin) parts.push(`${distanceMiles(origin, p).toFixed(1)} mi`);
  if (p.opens_at) parts.push(`${isOpenNow(p) ? "Open now" : "Open today"} ${hoursLabel(p)}`);
  else parts.push(p.on_stash ? hoursLabel(p) : "Not on Stash yet");
  return parts.join("  ·  ");
}

export function sortByDistance(pantries: Pantry[], origin: LatLng | null): Pantry[] {
  if (!origin) return pantries;
  return [...pantries].sort((a, b) => distanceMiles(origin, a) - distanceMiles(origin, b));
}

/** Categories at "plenty" for this pantry, best-stocked first. */
export function goodStock(stock: CategoryStock[], pantryId: string) {
  return stock
    .filter((s) => s.pantry_id === pantryId && stockLevel(s.units, s.target_units) === "plenty")
    .sort((a, b) => b.units / b.target_units - a.units / a.target_units)
    .map((s) => CATEGORIES.find((c) => c.key === s.category)!)
    .filter(Boolean);
}

export function StockChips({ stock, pantryId, max = 3 }: { stock: CategoryStock[]; pantryId: string; max?: number }) {
  if (!stock.some((s) => s.pantry_id === pantryId)) return <Text style={Type.muted}>No live stock info yet</Text>;
  const cats = goodStock(stock, pantryId).slice(0, max);
  if (!cats.length) return <Text style={Type.muted}>Restocking soon</Text>;
  const softs = [Colors.oliveSoft, Colors.mustardSoft, Colors.skySoft];
  return (
    <View style={styles.chips}>
      {cats.map((c, i) => (
        <Text key={c.key} style={[styles.chip, { backgroundColor: softs[i % softs.length] }]}>{c.label}</Text>
      ))}
    </View>
  );
}

/** Pantry photo if it has a licensed one; otherwise a map-pin tile (never a stand-in photo). */
export function PantryThumb({ pantry, width, height, rounded = 12 }: {
  pantry: Pick<Pantry, "image_key"> | null | undefined; width: number; height: number; rounded?: number;
}) {
  if (pantry?.image_key) return <Art name={pantry.image_key} width={width} height={height} rounded={rounded} cover />;
  return (
    <View style={[styles.pinTile, { width, height, borderRadius: rounded }]}>
      <MaterialCommunityIcons name="map-marker" size={Math.min(width, height) * 0.5} color={Colors.sky} />
    </View>
  );
}

export function PantryRow({ pantry, origin, onPress }: { pantry: Pantry; origin: LatLng | null; onPress: () => void }) {
  return (
    <Card style={styles.row} onPress={onPress}>
      <PantryThumb pantry={pantry} width={64} height={52} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={Type.h3}>{pantry.name}</Text>
        <View style={styles.metaRow}>
          <View style={[styles.dot, { backgroundColor: isOpenNow(pantry) ? Colors.olive : Colors.line }]} />
          <Text style={Type.muted}>{pantryMeta(pantry, origin)}</Text>
        </View>
      </View>
      <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
    </Card>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  chip: {
    fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.text, paddingHorizontal: 14,
    paddingVertical: 7, borderRadius: Radii.pill, overflow: "hidden",
  },
  pinTile: { backgroundColor: Colors.skySoft, alignItems: "center", justifyContent: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
