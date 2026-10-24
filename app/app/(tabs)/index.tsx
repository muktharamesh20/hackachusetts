import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View,
} from "react-native";
import { fetchItems, daysUntil, InventoryItem } from "@/lib/inventory";
import { isSupabaseConfigured } from "@/lib/supabase";
import { Colors } from "@/theme/colors";

export default function InventoryScreen() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    if (!isSupabaseConfigured) {
      setError("Connect Supabase: set EXPO_PUBLIC_SUPABASE_URL and _ANON_KEY in app/.env, then run db/schema.sql.");
      setLoading(false);
      return;
    }
    try {
      setItems(await fetchItems());
    } catch (e: any) {
      setError(e?.message ?? "Failed to load inventory");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, [load]));

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color={Colors.primary} /></View>;
  }

  const totalCalories = items.reduce(
    (sum, i) => sum + (i.unit_calories ?? 0) * i.quantity, 0
  );

  return (
    <View style={styles.container}>
      <View style={styles.summary}>
        <Text style={styles.summaryNum}>{items.length}</Text>
        <Text style={styles.summaryLabel}>items</Text>
        <View style={styles.divider} />
        <Text style={styles.summaryNum}>{totalCalories.toLocaleString()}</Text>
        <Text style={styles.summaryLabel}>kcal on hand</Text>
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        data={items}
        keyExtractor={(i) => i.id}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />
        }
        ListEmptyComponent={
          !error ? <Text style={styles.empty}>No items yet. Run the sorter or add items in Supabase.</Text> : null
        }
        renderItem={({ item }) => {
          const d = daysUntil(item.expiration_date);
          const expSoon = d !== null && d <= 14;
          const expired = d !== null && d < 0;
          return (
            <View style={styles.card}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.meta}>
                  {item.category} · qty {item.quantity}
                  {item.unit_calories ? ` · ${item.unit_calories} kcal` : ""}
                </Text>
              </View>
              {d !== null && (
                <View style={[styles.badge, expired ? styles.badgeExpired : expSoon ? styles.badgeSoon : styles.badgeOk]}>
                  <Text style={styles.badgeText}>
                    {expired ? "expired" : `${d}d`}
                  </Text>
                </View>
              )}
            </View>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: Colors.bg },
  summary: {
    flexDirection: "row", alignItems: "baseline", gap: 8,
    backgroundColor: Colors.primary, paddingHorizontal: 20, paddingVertical: 16,
  },
  summaryNum: { color: "#fff", fontSize: 24, fontWeight: "800" },
  summaryLabel: { color: "#d1fae5", fontSize: 13 },
  divider: { width: 1, height: 24, backgroundColor: "#ffffff44", marginHorizontal: 10 },
  card: {
    flexDirection: "row", alignItems: "center", backgroundColor: Colors.card,
    borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border,
  },
  name: { fontSize: 16, fontWeight: "700", color: Colors.text },
  meta: { fontSize: 13, color: Colors.textMuted, marginTop: 3 },
  badge: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  badgeOk: { backgroundColor: "#d1fae5" },
  badgeSoon: { backgroundColor: "#fef3c7" },
  badgeExpired: { backgroundColor: "#fee2e2" },
  badgeText: { fontSize: 12, fontWeight: "700", color: Colors.text },
  empty: { textAlign: "center", color: Colors.textMuted, marginTop: 40, paddingHorizontal: 24 },
  error: { color: Colors.danger, fontSize: 13, textAlign: "center", padding: 12 },
});
