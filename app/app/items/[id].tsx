import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  Art, Badge, Button, Card, Chip, ErrorText, ExpiryBadge, Meter, Screen,
} from "@/components/ui";
import { categoryInfo } from "@/lib/categories";
import { fetchCategoryStock, fetchItem, handOut, timeAgo } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const SOURCE_LABEL: Record<string, string> = {
  robot: "Sorted by the robot",
  scan: "Scanned in",
  manual: "Added by hand",
  donor: "Scanned in by a donor",
};

function formatDate(iso: string | null): string {
  if (!iso) return "No expiration date";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `Expires ${new Date(y, m - 1, d).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`;
}

export default function ItemDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, error, reload } = useLoad(async () => {
    const item = await fetchItem(id);
    const stock = await fetchCategoryStock(item.pantry_id);
    return { item, goal: stock.find((s) => s.category === item.category) };
  }, [id]);

  const item = data?.item;
  const lots = item?.inventory_lots ?? [];
  const info = categoryInfo(item?.category ?? "");
  const goalPct = data?.goal ? Math.round((data.goal.units / data.goal.target_units) * 100) : null;

  const onHandOut = async () => {
    if (!item) return;
    setBusy(true);
    setActionError(null);
    try {
      await handOut(item, 1);
      await reload();
    } catch (e: any) {
      setActionError(e?.message ?? "Couldn't hand out");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <View style={styles.nav}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <MaterialCommunityIcons name="chevron-left" size={30} color={Colors.text} />
        </Pressable>
        <Text style={[Type.h2, styles.title]} numberOfLines={1}>{item?.name ?? ""}</Text>
        <View style={{ width: 30 }} />
      </View>

      <ErrorText message={error} />
      {item && (
        <>
          <Art name={item.image_key ?? info.art} width={240} height={190} style={{ alignSelf: "center" }} />
          <Badge label={info.label} color={Colors.white} soft={info.tint} />

          <Card style={{ gap: 12 }}>
            <View style={styles.stockRow}>
              <MaterialCommunityIcons name="check-circle" size={28} color={Colors.olive} />
              <Text style={[Type.h3, { flex: 1, fontSize: 18 }]}>In stock</Text>
              <Text style={Type.bodySemi}>{item.quantity > 0 ? `${item.quantity} items` : "Out of stock"}</Text>
            </View>
            {data?.goal && (
              <View style={styles.stockRow}>
                <Meter units={data.goal.units} target={data.goal.target_units} />
                <Text style={Type.muted}>{goalPct}% of {info.label.toLowerCase()} goal</Text>
              </View>
            )}
          </Card>

          {lots.length > 0 && (
            <Card style={{ gap: 4 }}>
              <View style={styles.lotsHeader}>
                <Text style={Type.h2}>Expiration dates</Text>
                <Text style={Type.muted}>{lots.length} {lots.length === 1 ? "lot" : "lots"}</Text>
              </View>
              <Text style={Type.muted}>Each batch has its own date. Hand-outs use the soonest first.</Text>
              {lots.map((l, i) => (
                <View key={l.id} style={[styles.lotRow, i > 0 && styles.lotDivider]}>
                  <Text style={styles.lotQty}>{l.quantity}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={Type.bodySemi}>{formatDate(l.expiration_date)}</Text>
                    <Text style={Type.muted}>
                      {SOURCE_LABEL[l.source] ?? "Added"} · {timeAgo(l.received_at)}
                    </Text>
                  </View>
                  <ExpiryBadge date={l.expiration_date} />
                </View>
              ))}
            </Card>
          )}

          {(item.tags.length > 0 || item.allergens.length > 0) && (
            <View style={styles.tags}>
              {item.tags.map((t) => <Chip key={t} label={t} />)}
              {item.allergens.map((a) => (
                <Chip key={a} label={`Contains ${a}`} soft={Colors.tomatoSoft} />
              ))}
            </View>
          )}

          {item.good_to_know.length > 0 && (
            <View style={{ gap: 6 }}>
              <Text style={Type.h2}>Good to know</Text>
              <Text style={Type.muted}>{item.good_to_know.join("  ·  ")}</Text>
            </View>
          )}

          <ErrorText message={actionError} />
          <Button title="Log new items" icon="package-variant-closed" onPress={() => router.push("/pantry/scan")} />
          {item.quantity > 0 && (
            <Button title="Hand out one" variant="outline" icon="hand-heart-outline" onPress={onHandOut} loading={busy} />
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  nav: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { flex: 1, textAlign: "center", fontFamily: Fonts.displayHeavy },
  stockRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  lotsHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  lotRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  lotDivider: { borderTopWidth: 1.5, borderTopColor: Colors.line },
  lotQty: { fontFamily: Fonts.displayHeavy, fontSize: 22, color: Colors.text, width: 34, textAlign: "center" },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
