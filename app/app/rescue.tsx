import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { Art, Badge, Button, Card, EmptyState, ErrorText, Screen } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { claimRescueBag, fetchPantries, fetchRescueBags, money, RescueBag, timeLabel } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors, Tint } from "@/theme/colors";
import { Space, Type } from "@/theme/type";

/** Food within a day of its date that neighbors didn't claim; buying it funds the pantry. */
export default function Rescue() {
  const router = useRouter();
  const { session } = useAuth();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [claimed, setClaimed] = useState<RescueBag | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, refreshing, refresh } = useLoad(async () => {
    const [bags, pantries] = await Promise.all([fetchRescueBags(), fetchPantries()]);
    return { bags, names: Object.fromEntries(pantries.map((p) => [p.id, p.name])) };
  });

  const rescue = async (bag: RescueBag) => {
    if (!session) return;
    setBusyId(bag.id);
    setError(null);
    try {
      await claimRescueBag(bag.id, session.user.id);
      setClaimed(bag);
      refresh();
    } catch (e: any) {
      setError(e?.message ?? "Someone may have just rescued this bag");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <Pressable onPress={() => router.back()} hitSlop={12} style={{ marginTop: Space.sm }}>
        <MaterialCommunityIcons name="chevron-left" size={30} color={Colors.text} />
      </Pressable>
      <Text style={Type.h1}>Rescue Bags</Text>
      <Text style={Type.muted}>
        Food is always free to neighbors. On its last day, anything unclaimed becomes a Rescue Bag, so it
        feeds someone instead of the trash. 100% of what you pay goes back to the pantry.
      </Text>

      {claimed && (
        <Card style={styles.claimed}>
          <Art name="hazel-cheer" width={90} />
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={Type.h3}>Bag rescued!</Text>
            <Text style={Type.muted}>
              Pick up at {data?.names[claimed.pantry_id]} by {timeLabel(claimed.pickup_by)}. You saved{" "}
              {claimed.weight_lbs} lbs of food.
            </Text>
          </View>
        </Card>
      )}

      <ErrorText message={error ?? loadError} />
      {data?.bags.length === 0 && !claimed && (
        <EmptyState title="No bags right now" body="Neighbors claimed everything. Nice! Check back tomorrow." />
      )}
      {data?.bags.map((b) => (
        <Card key={b.id} style={{ gap: 12 }}>
          <View style={styles.top}>
            <Art name="illus-rescue-bag" width={84} />
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={Type.h3}>{b.title}</Text>
              <Text style={Type.muted}>{data.names[b.pantry_id]}</Text>
              <Text style={Type.muted}>
                {b.item_count} items · pick up by {timeLabel(b.pickup_by)}
              </Text>
              <Badge label={`Saves ${b.weight_lbs} lbs of food`} color="#A97A12" soft={Colors.mustardSoft} />
            </View>
          </View>
          <Text style={Type.body}>{b.description}</Text>
          <Button
            title={`Rescue it · ${money(b.price_cents)}`}
            color={ModeColors.donor.main}
            dark={ModeColors.donor.dark}
            loading={busyId === b.id}
            onPress={() => rescue(b)}
          />
        </Card>
      ))}
      <Text style={styles.demo}>Demo checkout: no card is charged.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", gap: 12, alignItems: "center" },
  claimed: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  demo: { ...Type.muted, textAlign: "center", fontSize: 12 },
});
