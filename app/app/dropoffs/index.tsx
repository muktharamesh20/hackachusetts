import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { Art, Button, Card, EmptyState, ErrorText, Screen } from "@/components/ui";
import { useStaffPantryId } from "@/context/ProfileContext";
import {
  acceptDropoffs, Bag, fetchAcceptedDropoffs, fetchPendingDropoffs, groupBags, timeAgo,
} from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, Tint } from "@/theme/colors";
import { Space, Type } from "@/theme/type";

/** Staff: every donor bag at this pantry, waiting first, then recently checked in. */
export default function Dropoffs() {
  const router = useRouter();
  const pantryId = useStaffPantryId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, refreshing, refresh, reload } = useLoad(async () => {
    const [pending, accepted] = await Promise.all([fetchPendingDropoffs(pantryId), fetchAcceptedDropoffs(pantryId)]);
    return { pending, waiting: groupBags(pending), done: groupBags(accepted) };
  }, [pantryId]);

  const acceptAll = async () => {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await acceptDropoffs(data.pending.map((d) => d.id));
      await reload();
    } catch (e: any) {
      setError(e?.message ?? "Couldn't add them");
    } finally {
      setBusy(false);
    }
  };

  const row = (b: Bag, i: number, checked: boolean) => (
    <Pressable key={b.id} style={[styles.row, i > 0 && styles.divider]} onPress={() => router.push(`/dropoffs/${b.id}`)}>
      <MaterialCommunityIcons
        name={checked ? "check-circle" : "package-variant"}
        size={24}
        color={checked ? Colors.olive : Tint.olive.ink}
      />
      <View style={{ flex: 1 }}>
        <Text style={Type.bodySemi}>{b.donor}'s bag · {b.units} {b.units === 1 ? "item" : "items"}</Text>
        <Text style={Type.muted} numberOfLines={1}>{b.names}</Text>
      </View>
      <Text style={Type.muted}>{timeAgo(b.at)}</Text>
      <MaterialCommunityIcons name="chevron-right" size={22} color={Colors.text} />
    </Pressable>
  );

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <Pressable onPress={() => router.back()} hitSlop={12}>
        <MaterialCommunityIcons name="chevron-left" size={30} color={Colors.text} />
      </Pressable>
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={Type.h1}>Drop-offs</Text>
          <Text style={[Type.body, { color: Colors.textMuted }]}>
            Bags donors scanned in. Check one, or scan the slip in its box from the Scan tab.
          </Text>
        </View>
        <Art name="illus-donate-food" width={84} />
      </View>

      <ErrorText message={loadError} />

      <Text style={Type.h2}>Waiting to check in</Text>
      {data && data.waiting.length === 0 && <Text style={Type.muted}>Nothing waiting right now.</Text>}
      {data && data.waiting.length > 0 && (
        <>
          <Card style={styles.waitingCard}>{data.waiting.map((b, i) => row(b, i, false))}</Card>
          <ErrorText message={error} />
          <Button
            title={`Add all ${data.pending.reduce((n, d) => n + d.quantity, 0)} to stock`}
            icon="check-all"
            color={Colors.olive}
            dark={Colors.oliveDark}
            loading={busy}
            onPress={acceptAll}
          />
        </>
      )}

      <Text style={[Type.h2, { marginTop: Space.sm }]}>Recently checked in</Text>
      {data && data.done.length === 0 && (
        <EmptyState art="hazel-acorn-hug" title="No drop-offs yet" body="When donors scan what they bring, their bags land here." />
      )}
      {data && data.done.length > 0 && <Card style={{ paddingVertical: 4 }}>{data.done.map((b, i) => row(b, i, true))}</Card>}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: Space.md },
  waitingCard: { paddingVertical: 4, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  row: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12 },
  divider: { borderTopWidth: 1, borderTopColor: Colors.line },
});
