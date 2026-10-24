import { useMemo, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Art, Chip, EmptyState, ErrorText, ItemIcon } from "@/components/ui";
import { useStaffPantryId } from "@/context/ProfileContext";
import { Activity, fetchActivity, fetchItems, timeLabel } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

type Filter = "all" | "robot" | "added" | "handed";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "robot", label: "Robot" },
  { key: "added", label: "Added" },
  { key: "handed", label: "Handed out" },
];

function describe(a: Activity): string {
  if (a.transaction_type === "distribute") return "handed out to a neighbor";
  if (a.transaction_type === "discard") return "removed from stock";
  if (a.source === "donor") return "scanned in by a donor";
  return a.source === "robot" ? "sorted by the robot" : "added to inventory";
}

export default function ActivityScreen() {
  const pantryId = useStaffPantryId();
  const [filter, setFilter] = useState<Filter>("all");
  const { data, error, refreshing, refresh } = useLoad(async () => {
    const [activity, items] = await Promise.all([fetchActivity(pantryId, 60), fetchItems(pantryId)]);
    return { activity, items: Object.fromEntries(items.map((i) => [i.id, i])) };
  }, [pantryId]);

  const rows = useMemo(
    () =>
      (data?.activity ?? []).filter((a) => {
        if (filter === "robot") return a.source === "robot";
        if (filter === "added") return a.transaction_type === "intake";
        if (filter === "handed") return a.transaction_type === "distribute";
        return true;
      }),
    [data, filter],
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={Type.h1}>Recent activity</Text>
        <View style={styles.chips}>
          {FILTERS.map((f) => (
            <Chip key={f.key} label={f.label} active={filter === f.key} onPress={() => setFilter(f.key)} />
          ))}
        </View>
      </View>
      <ErrorText message={error} />
      <FlatList
        data={rows}
        keyExtractor={(a) => String(a.id)}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        ListEmptyComponent={data ? <EmptyState title="All quiet" body="Sorted, scanned and handed-out items show up here." /> : null}
        renderItem={({ item: a }) => {
          const name = a.item_name || a.note || "Item";
          return (
            <View style={styles.row}>
              {a.source === "robot" ? (
                <Art name="illus-robot-arm" width={46} />
              ) : (
                <ItemIcon
                  imageKey={data?.items[a.item_id]?.image_key ?? null}
                  category={data?.items[a.item_id]?.category ?? "household"}
                  size={46}
                />
              )}
              <View style={{ flex: 1 }}>
                <Text style={Type.h3}>{a.quantity > 1 ? `${name} (${a.quantity})` : name}</Text>
                <Text style={Type.muted}>{describe(a)}</Text>
              </View>
              <Text style={styles.time}>{timeLabel(a.timestamp)}</Text>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  header: { paddingHorizontal: Space.gutter, paddingTop: Space.sm, gap: Space.md },
  chips: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  list: { padding: Space.gutter, paddingBottom: Space.xxl },
  row: { flexDirection: "row", alignItems: "center", gap: Space.md, paddingVertical: 12 },
  sep: { height: 1.5, backgroundColor: Colors.line },
  time: { fontFamily: Fonts.bodySemi, fontSize: 12, color: Colors.textMuted },
});
