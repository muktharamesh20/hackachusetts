import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View,
} from "react-native";
import { fetchDistributionQueue, daysUntil, InventoryItem } from "@/lib/inventory";
import { isSupabaseConfigured } from "@/lib/supabase";
import { Colors } from "@/theme/colors";

/** First-Expired-First-Out queue — what to hand out next. */
export default function DistributeScreen() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    if (!isSupabaseConfigured) {
      setError("Connect Supabase to see the FEFO queue.");
      setLoading(false);
      return;
    }
    try {
      setItems(await fetchDistributionQueue());
    } catch (e: any) {
      setError(e?.message ?? "Failed to load queue");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, [load]));

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color={Colors.primary} /></View>;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Hand out soonest-expiring first (FEFO)</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={items}
        keyExtractor={(i) => i.id}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />
        }
        ListEmptyComponent={!error ? <Text style={styles.empty}>Nothing to distribute.</Text> : null}
        renderItem={({ item, index }) => {
          const d = daysUntil(item.expiration_date);
          return (
            <View style={styles.card}>
              <Text style={styles.rank}>{index + 1}</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.meta}>{item.category} · qty {item.quantity}</Text>
              </View>
              <Text style={styles.exp}>{d !== null ? `${d}d left` : "no expiry"}</Text>
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
  header: { fontSize: 14, color: Colors.textMuted, padding: 16, paddingBottom: 0 },
  card: {
    flexDirection: "row", alignItems: "center", gap: 14, backgroundColor: Colors.card,
    borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border,
  },
  rank: { fontSize: 18, fontWeight: "800", color: Colors.primary, width: 24, textAlign: "center" },
  name: { fontSize: 16, fontWeight: "700", color: Colors.text },
  meta: { fontSize: 13, color: Colors.textMuted, marginTop: 3 },
  exp: { fontSize: 13, fontWeight: "700", color: Colors.accent },
  empty: { textAlign: "center", color: Colors.textMuted, marginTop: 40 },
  error: { color: Colors.danger, fontSize: 13, textAlign: "center", padding: 12 },
});
