import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ScanDraft, ScanFlow } from "@/components/ScanFlow";
import { Art, Button, CategoryIcon, ErrorText } from "@/components/ui";
import { useProfile } from "@/context/ProfileContext";
import { fetchStashPantries, Pantry, submitDropoff } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors } from "@/theme/colors";
import { Fonts, Radii, Shadow, Space, Type } from "@/theme/type";

const GREEN = ModeColors.donor;

/**
 * Donor scan: build a drop-off bag by scanning what you brought, then hand it to
 * the pantry. Staff confirm it into stock from their home screen.
 */
export default function DonorScan() {
  const params = useLocalSearchParams<{ pantry?: string }>();
  const { profile } = useProfile();
  const { data: pantries } = useLoad(fetchStashPantries);
  const [pantryId, setPantryId] = useState<string | null>(params.pantry ?? null);
  const [bag, setBag] = useState<ScanDraft[]>([]);
  const [picking, setPicking] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thanks, setThanks] = useState<{ count: number; pantry: string } | null>(null);

  useEffect(() => {
    if (params.pantry) setPantryId(params.pantry);
  }, [params.pantry]);
  // Default to a saved pantry, else the first one on Stash.
  useEffect(() => {
    if (pantryId || !pantries?.length) return;
    const saved = pantries.find((p) => profile?.saved_pantries.includes(p.id));
    setPantryId((saved ?? pantries[0]).id);
  }, [pantries, pantryId, profile]);

  const pantry = pantries?.find((p) => p.id === pantryId) ?? null;
  const units = bag.reduce((n, d) => n + d.quantity, 0);

  const dropOff = async () => {
    if (!pantry || !bag.length) return;
    setBusy(true);
    setError(null);
    try {
      await submitDropoff(
        pantry.id,
        bag.map((d) => ({
          name: d.name,
          category: d.category!,
          quantity: d.quantity,
          expirationDate: d.expirationDate || null,
          barcode: d.barcode,
        })),
      );
      setThanks({ count: units, pantry: pantry.name });
      setBag([]);
      setReviewing(false);
    } catch (e: any) {
      setError(e?.message ?? "Couldn't drop off");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <ScanFlow
        pantryId={pantryId}
        submitLabel="Add to drop-off bag"
        submitIcon="shopping-outline"
        idleTitle="Scan what you're donating"
        onSubmit={async (d) => {
          setBag((b) => [...b, d]);
          return null; // straight back to the camera for the next item
        }}
        topSlot={
          <Pressable style={styles.pantryChip} onPress={() => setPicking(true)}>
            <MaterialCommunityIcons name="storefront-outline" size={16} color={GREEN.dark} />
            <Text style={styles.pantryChipText} numberOfLines={1}>
              Dropping off at {pantry?.name ?? "…"}
            </Text>
            <MaterialCommunityIcons name="chevron-down" size={18} color={GREEN.dark} />
          </Pressable>
        }
        bottomSlot={
          bag.length > 0 ? (
            <Pressable style={styles.bagBar} onPress={() => setReviewing(true)}>
              <MaterialCommunityIcons name="shopping" size={24} color={Colors.white} />
              <Text style={styles.bagText}>
                {units} {units === 1 ? "item" : "items"} in your bag
              </Text>
              <Text style={styles.bagCta}>Review & drop off</Text>
              <MaterialCommunityIcons name="chevron-right" size={22} color={Colors.white} />
            </Pressable>
          ) : null
        }
      />

      {/* Pick the pantry */}
      <Modal visible={picking} transparent animationType="slide" onRequestClose={() => setPicking(false)}>
        <Pressable style={styles.backdrop} onPress={() => setPicking(false)} />
        <View style={styles.sheet}>
          <View style={styles.grabber} />
          <Text style={Type.h2}>Where are you dropping off?</Text>
          {(pantries ?? []).map((p: Pantry) => (
            <Pressable
              key={p.id}
              style={styles.option}
              onPress={() => {
                setPantryId(p.id);
                setPicking(false);
              }}
            >
              <View style={{ flex: 1 }}>
                <Text style={Type.bodySemi}>{p.name}</Text>
                <Text style={Type.muted}>{p.address}, {p.city}</Text>
              </View>
              <MaterialCommunityIcons
                name={p.id === pantryId ? "radiobox-marked" : "radiobox-blank"}
                size={22}
                color={p.id === pantryId ? GREEN.main : Colors.line}
              />
            </Pressable>
          ))}
        </View>
      </Modal>

      {/* Review the bag */}
      <Modal visible={reviewing} transparent animationType="slide" onRequestClose={() => setReviewing(false)}>
        <Pressable style={styles.backdrop} onPress={() => setReviewing(false)} />
        <View style={[styles.sheet, { maxHeight: "80%" }]}>
          <View style={styles.grabber} />
          <Text style={Type.h2}>Your drop-off bag</Text>
          <Text style={Type.muted}>
            {pantry?.name}'s team will check these in. Thanks for doing the scanning!
          </Text>
          <ScrollView style={{ marginVertical: Space.sm }}>
            {bag.map((d, i) => (
              <View key={i} style={[styles.bagRow, i > 0 && styles.divider]}>
                <CategoryIcon category={d.category ?? "unknown"} size={36} />
                <View style={{ flex: 1 }}>
                  <Text style={Type.bodySemi}>{d.quantity > 1 ? `${d.name} (${d.quantity})` : d.name}</Text>
                  <Text style={Type.muted}>{d.expirationDate ? `Expires ${d.expirationDate}` : "No date"}</Text>
                </View>
                <Pressable hitSlop={10} onPress={() => setBag((b) => b.filter((_, j) => j !== i))}>
                  <MaterialCommunityIcons name="close-circle-outline" size={22} color={Colors.textMuted} />
                </Pressable>
              </View>
            ))}
          </ScrollView>
          <ErrorText message={error} />
          <Button
            title={`Drop off ${units} ${units === 1 ? "item" : "items"}`}
            icon="hand-heart"
            color={GREEN.main}
            dark={GREEN.dark}
            loading={busy}
            disabled={!bag.length || !pantry}
            onPress={dropOff}
          />
        </View>
      </Modal>

      {/* Thank-you */}
      <Modal visible={Boolean(thanks)} transparent animationType="fade" onRequestClose={() => setThanks(null)}>
        <View style={styles.thanksWrap}>
          <View style={styles.thanksCard}>
            <Art name="hazel-cheer" width={150} />
            <Text style={[Type.h1, { textAlign: "center" }]}>Thank you!</Text>
            <Text style={[Type.body, { textAlign: "center" }]}>
              {thanks?.count} {thanks?.count === 1 ? "item is" : "items are"} waiting for {thanks?.pantry}'s team to
              check in. Leave them at the drop-off spot.
            </Text>
            <Button title="Done" color={GREEN.main} dark={GREEN.dark} onPress={() => setThanks(null)} style={{ alignSelf: "stretch" }} />
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  pantryChip: {
    flexDirection: "row", alignItems: "center", gap: 6, marginTop: Space.sm, maxWidth: "88%",
    backgroundColor: Colors.card, paddingHorizontal: 14, paddingVertical: 8, borderRadius: Radii.pill, ...Shadow,
  },
  pantryChipText: { fontFamily: Fonts.bodyBold, fontSize: 14, color: GREEN.dark, flexShrink: 1 },
  bagBar: {
    flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: GREEN.main,
    borderRadius: Radii.button, paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 3, borderBottomColor: GREEN.dark,
  },
  bagText: { fontFamily: Fonts.bodyHeavy, fontSize: 15, color: Colors.white, flex: 1 },
  bagCta: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.white },
  backdrop: { flex: 1, backgroundColor: "#0006" },
  sheet: {
    backgroundColor: Colors.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28,
    padding: Space.gutter, paddingBottom: 40, gap: 8,
  },
  grabber: { alignSelf: "center", width: 40, height: 5, borderRadius: 3, backgroundColor: Colors.line, marginBottom: Space.sm },
  option: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  bagRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  divider: { borderTopWidth: 1, borderTopColor: Colors.line },
  thanksWrap: { flex: 1, backgroundColor: "#0007", alignItems: "center", justifyContent: "center", padding: Space.xl },
  thanksCard: {
    backgroundColor: Colors.bg, borderRadius: 28, padding: Space.xl, gap: Space.md,
    alignItems: "center", alignSelf: "stretch",
  },
});
