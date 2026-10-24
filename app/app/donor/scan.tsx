import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { PantryPickerModal } from "@/components/PantryPicker";
import { ScanDraft, ScanFlow } from "@/components/ScanFlow";
import { Art, Button, CategoryIcon, ErrorText } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useProfile } from "@/context/ProfileContext";
import { emailSlip, printSlip, Slip } from "@/lib/slip";
import { fetchStashPantries, submitDropoff } from "@/lib/stash";
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
  const { session } = useAuth();
  const email = session?.user.email ?? undefined;
  const donorName: string = session?.user.user_metadata?.full_name ?? email?.split("@")[0] ?? "A neighbor";
  const { data: pantries } = useLoad(fetchStashPantries);
  const [pantryId, setPantryId] = useState<string | null>(params.pantry ?? null);
  const [bag, setBag] = useState<ScanDraft[]>([]);
  const [picking, setPicking] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thanks, setThanks] = useState<{ count: number; pantry: string; slip: Slip } | null>(null);
  const [slipError, setSlipError] = useState<string | null>(null);
  // Explain why donors scan, every time they open this tab.
  const [intro, setIntro] = useState(true);
  useFocusEffect(useCallback(() => setIntro(true), []));

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
      const items = bag.map((d) => ({
          name: d.name,
          category: d.category!,
          quantity: d.quantity,
          expirationDate: d.expirationDate || null,
          barcode: d.barcode,
        }));
      const batchId = await submitDropoff(pantry.id, donorName, items);
      const slip: Slip = {
        batchId,
        pantryName: pantry.name,
        pantryAddress: [pantry.address, pantry.city].filter(Boolean).join(", "),
        donorName,
        items: items.map((i) => ({ name: i.name, quantity: i.quantity, expirationDate: i.expirationDate })),
        createdAt: new Date(),
      };
      setThanks({ count: units, pantry: pantry.name, slip });
      setBag([]);
      setReviewing(false);
      // Email the printable slip to the donor right away.
      emailSlip(slip, email).catch((e) => setSlipError(e?.message ?? "Couldn't open email"));
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

      <PantryPickerModal
        visible={picking}
        pantries={pantries ?? []}
        value={pantryId}
        color={GREEN.main}
        onClose={() => setPicking(false)}
        onPick={(id) => {
          setPantryId(id);
          setPicking(false);
        }}
      />

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

      {/* Why scan? (shown each time the tab opens) */}
      <Modal visible={intro} transparent animationType="fade" onRequestClose={() => setIntro(false)}>
        <View style={styles.thanksWrap}>
          <View style={styles.thanksCard}>
            <Art name="hazel-heart" width={140} />
            <Text style={[Type.h1, { textAlign: "center" }]}>Giving food? Thank you!</Text>
            <Text style={[Type.body, { textAlign: "center" }]}>
              Help the volunteers out: scan each item (or type in its name and expiration date) before you drop
              it off. They'll just confirm it instead of logging everything by hand.
            </Text>
            <View style={styles.steps}>
              {[
                { icon: "storefront-outline", text: "Pick the pantry you're dropping off at" },
                { icon: "barcode-scan", text: "Scan each item, or type it in if it has no barcode (like apples)" },
                { icon: "shopping-outline", text: "Review your bag and drop it off" },
                { icon: "printer-outline", text: "Print the slip we email you and put it in your box" },
              ].map((s) => (
                <View key={s.text} style={styles.step}>
                  <MaterialCommunityIcons name={s.icon as any} size={20} color={GREEN.main} />
                  <Text style={[Type.bodySemi, { flex: 1 }]}>{s.text}</Text>
                </View>
              ))}
            </View>
            <Button
              title="Start scanning"
              icon="barcode-scan"
              color={GREEN.main}
              dark={GREEN.dark}
              onPress={() => setIntro(false)}
              style={{ alignSelf: "stretch" }}
            />
          </View>
        </View>
      </Modal>

      {/* Thank-you */}
      <Modal visible={Boolean(thanks)} transparent animationType="fade" onRequestClose={() => setThanks(null)}>
        <View style={styles.thanksWrap}>
          <View style={styles.thanksCard}>
            <Art name="hazel-cheer" width={150} />
            <Text style={[Type.h1, { textAlign: "center" }]}>Thank you!</Text>
            <Text style={[Type.body, { textAlign: "center" }]}>
              {thanks?.count} {thanks?.count === 1 ? "item is" : "items are"} waiting for {thanks?.pantry}'s team.
              We've emailed your drop-off slip{email ? ` to ${email}` : ""}. Print it and put it in your box so
              volunteers know whose donation is whose.
            </Text>
            <ErrorText message={slipError} />
            <View style={styles.slipButtons}>
              <Button
                title="Print slip"
                icon="printer-outline"
                color={GREEN.main}
                dark={GREEN.dark}
                style={{ flex: 1 }}
                onPress={() => thanks && printSlip(thanks.slip).catch(() => {})}
              />
              <Button
                title="Email again"
                icon="email-outline"
                variant="outline"
                color={GREEN.main}
                style={{ flex: 1 }}
                onPress={() => thanks && emailSlip(thanks.slip, email).catch(() => {})}
              />
            </View>
            <Text style={styles.done} onPress={() => setThanks(null)}>Done</Text>
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
  bagRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  divider: { borderTopWidth: 1, borderTopColor: Colors.line },
  slipButtons: { flexDirection: "row", gap: 10, alignSelf: "stretch" },
  done: { fontFamily: Fonts.bodyBold, fontSize: 15, color: Colors.textMuted, padding: Space.sm },
  steps: { alignSelf: "stretch", gap: 10, paddingVertical: Space.xs },
  step: { flexDirection: "row", alignItems: "center", gap: 10 },
  thanksWrap: { flex: 1, backgroundColor: "#0007", alignItems: "center", justifyContent: "center", padding: Space.xl },
  thanksCard: {
    backgroundColor: Colors.bg, borderRadius: 28, padding: Space.xl, gap: Space.md,
    alignItems: "center", alignSelf: "stretch",
  },
});
