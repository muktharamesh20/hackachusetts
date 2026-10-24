import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Art, Button, Card, CategoryIcon, EmptyState, ErrorText, Screen } from "@/components/ui";
import { acceptDropoffs, fetchDropoffBag, timeAgo } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, Tint } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

/** One donor's bag, opened from Pantry home or by scanning the printed slip's QR. */
export default function DropoffBag() {
  const { batch } = useLocalSearchParams<{ batch: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, reload } = useLoad(() => fetchDropoffBag(batch), [batch]);

  const pending = (data ?? []).filter((d) => d.status === "pending");
  const first = data?.[0];
  const units = (data ?? []).reduce((n, d) => n + d.quantity, 0);

  const accept = async () => {
    setBusy(true);
    setError(null);
    try {
      await acceptDropoffs(pending.map((d) => d.id));
      await reload();
    } catch (e: any) {
      setError(e?.message ?? "Couldn't add these to stock");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <Pressable onPress={() => router.back()} hitSlop={12}>
        <MaterialCommunityIcons name="chevron-left" size={30} color={Colors.text} />
      </Pressable>

      <ErrorText message={loadError} />
      {data && data.length === 0 && (
        <EmptyState
          title="Bag not found"
          body="This slip is for a different pantry, or the bag was removed. Check you're signed in as staff at the right pantry."
        />
      )}

      {first && (
        <>
          <View style={styles.header}>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={Type.h1}>{first.donor_name ?? "A neighbor"}'s bag</Text>
              <Text style={Type.muted}>
                {units} {units === 1 ? "item" : "items"} · scanned {timeAgo(first.created_at)} · bag {first.batch_id.slice(0, 8)}
              </Text>
            </View>
            <Art name="illus-donate-food" width={84} />
          </View>

          <Card style={{ paddingVertical: 4 }}>
            {data!.map((d, i) => (
              <View key={d.id} style={[styles.row, i > 0 && styles.divider]}>
                <CategoryIcon category={d.category} size={36} />
                <View style={{ flex: 1 }}>
                  <Text style={Type.bodySemi}>{d.quantity > 1 ? `${d.name} (${d.quantity})` : d.name}</Text>
                  <Text style={[Type.muted, d.expiry_estimated && { color: Tint.mustard.ink }]}>
                    {d.expiration_date ? `Expires ${d.expiration_date}` : "No date"}
                    {d.expiry_estimated ? " · estimated, check the package" : ""}
                  </Text>
                </View>
                {d.status !== "pending" && (
                  <MaterialCommunityIcons name="check-circle" size={22} color={Colors.olive} />
                )}
              </View>
            ))}
          </Card>

          <ErrorText message={error} />
          {pending.length > 0 ? (
            <Button
              title={`Add ${pending.reduce((n, d) => n + d.quantity, 0)} to stock`}
              icon="check-all"
              color={Colors.olive}
              dark={Colors.oliveDark}
              loading={busy}
              onPress={accept}
            />
          ) : (
            <Card style={styles.doneCard}>
              <MaterialCommunityIcons name="check-circle" size={26} color={Tint.olive.ink} />
              <Text style={[Type.h3, { flex: 1 }]}>Checked in. Everything's in stock.</Text>
            </Card>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: Space.md },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  divider: { borderTopWidth: 1, borderTopColor: Colors.line },
  doneCard: { flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  label: { fontFamily: Fonts.bodyBold },
});
