import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useIsFocused } from "@react-navigation/native";
import { BarcodeScanningResult, CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import { ReactNode, useRef, useState } from "react";
import {
  KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Art, Button, CategoryIcon, Chip, ErrorText } from "@/components/ui";
import { CATEGORIES, CategoryKey } from "@/lib/categories";
import { parseLabel } from "@/lib/qr";
import { findCatalogItem, findItemByBarcode } from "@/lib/stash";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

export type ScanDraft = {
  barcode: string | null;
  name: string;
  category: CategoryKey | null;
  quantity: number;
  expirationDate: string; // YYYY-MM-DD or ""
  known: boolean; // matches an item already in this pantry
};

type Draft = ScanDraft;

/** What the success sheet says after a submit. */
export type ScanDone = { title: string; body: string };

const EMPTY: Draft = { barcode: null, name: "", category: null, quantity: 1, expirationDate: "", known: false };

/**
 * Camera + QR/barcode lookup + item form, shared by staff and donor scanning.
 * `onSubmit` decides what saving means; return null to go straight back to the
 * camera (e.g. a donor adding to their bag), or a message for the success sheet.
 */
export function ScanFlow({ pantryId, submitLabel, submitIcon = "package-variant-closed", onSubmit, topSlot, bottomSlot, idleTitle }: {
  /** Pantry to match scanned codes against existing items (null: skip). */
  pantryId: string | null;
  submitLabel: string;
  submitIcon?: React.ComponentProps<typeof Button>["icon"];
  onSubmit: (draft: ScanDraft) => Promise<ScanDone | null>;
  /** Shown under the hint while the camera is up (e.g. a pantry picker). */
  topSlot?: ReactNode;
  /** Shown above "Type it in instead" while the camera is up (e.g. a bag bar). */
  bottomSlot?: ReactNode;
  idleTitle?: string;
}) {
  const focused = useIsFocused();
  const [permission, requestPermission] = useCameraPermissions();
  const [stage, setStage] = useState<"camera" | "form" | "done">("camera");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [done, setDone] = useState<ScanDone | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);

  const onScanned = async ({ data }: BarcodeScanningResult) => {
    if (lock.current || stage !== "camera") return;
    lock.current = true;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    const label = parseLabel(data);
    const [existing, known] = await Promise.all([
      pantryId ? findItemByBarcode(pantryId, label.code).catch(() => null) : null,
      findCatalogItem(label.sku ?? label.code).catch(() => null),
    ]);
    setDraft({
      barcode: label.code,
      name: existing?.name ?? known?.name ?? "",
      category: (existing?.category as CategoryKey) ?? (known?.category as CategoryKey) ?? label.category,
      quantity: 1,
      expirationDate: label.expirationDate ?? existing?.expiration_date ?? "",
      known: Boolean(existing),
    });
    setStage("form");
  };

  const save = async () => {
    if (!draft.name.trim() || !draft.category) {
      setError("Add a name and pick a category.");
      return;
    }
    if (draft.expirationDate && !/^\d{4}-\d{2}-\d{2}$/.test(draft.expirationDate)) {
      setError("Expiry should look like 2026-12-31.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const result = await onSubmit({ ...draft, name: draft.name.trim() });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      if (result) {
        setDone(result);
        setStage("done");
      } else {
        reset();
      }
    } catch (e: any) {
      setError(e?.message ?? "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setDraft(EMPTY);
    setError(null);
    setStage("camera");
    lock.current = false;
  };

  return (
    <View style={styles.root}>
      {permission?.granted ? (
        <CameraView
          style={StyleSheet.absoluteFill}
          active={focused && stage === "camera"}
          barcodeScannerSettings={{ barcodeTypes: ["qr", "ean13", "ean8", "upc_a", "upc_e", "code128"] }}
          onBarcodeScanned={stage === "camera" ? onScanned : undefined}
        />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.noCamera]}>
          <Art name="illus-scan" width={180} />
          <Text style={[Type.h2, { color: Colors.white, textAlign: "center" }]}>{idleTitle ?? "Scan items into the stash"}</Text>
          {permission && !permission.granted && (
            <Button title="Allow camera" icon="camera-outline" onPress={requestPermission} />
          )}
        </View>
      )}

      <SafeAreaView style={styles.overlay} edges={["top"]} pointerEvents="box-none">
        <Text style={styles.hint}>
          {stage === "camera" ? "Point at a QR label or barcode" : " "}
        </Text>
        {stage === "camera" && topSlot}
        {stage === "camera" && permission?.granted && <View style={styles.frame} pointerEvents="none" />}
      </SafeAreaView>

      {stage === "camera" && (
        <View style={styles.bottomBar}>
          {bottomSlot}
          <Button
            title="Type it in instead"
            variant="outline"
            icon="keyboard-outline"
            onPress={() => {
              lock.current = true;
              setDraft(EMPTY);
              setStage("form");
            }}
          />
        </View>
      )}

      {stage === "form" && (
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.sheetWrap}>
          <ScrollView style={styles.sheet} contentContainerStyle={styles.sheetContent} keyboardShouldPersistTaps="handled">
            <View style={styles.sheetHeader}>
              {draft.category ? <CategoryIcon category={draft.category} size={44} /> : null}
              <View style={{ flex: 1 }}>
                <Text style={Type.h2}>{draft.known ? "Add more?" : "New item"}</Text>
                {draft.barcode && <Text style={Type.muted}>Code {draft.barcode}</Text>}
              </View>
              <Pressable onPress={reset} hitSlop={10}>
                <MaterialCommunityIcons name="close" size={24} color={Colors.textMuted} />
              </Pressable>
            </View>

            <TextInput
              style={styles.input}
              placeholder="Item name (e.g. Canned beans)"
              placeholderTextColor={Colors.textMuted}
              value={draft.name}
              onChangeText={(name) => setDraft((d) => ({ ...d, name }))}
            />

            <Text style={Type.label}>CATEGORY</Text>
            <View style={styles.chipWrap}>
              {CATEGORIES.map((c) => (
                <Chip
                  key={c.key}
                  label={c.label}
                  active={draft.category === c.key}
                  onPress={() => setDraft((d) => ({ ...d, category: c.key }))}
                />
              ))}
            </View>

            <View style={styles.qtyRow}>
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={Type.label}>QUANTITY</Text>
                <View style={styles.stepper}>
                  <Pressable onPress={() => setDraft((d) => ({ ...d, quantity: Math.max(1, d.quantity - 1) }))} hitSlop={8}>
                    <MaterialCommunityIcons name="minus-circle-outline" size={28} color={Colors.tomato} />
                  </Pressable>
                  <Text style={styles.qty}>{draft.quantity}</Text>
                  <Pressable onPress={() => setDraft((d) => ({ ...d, quantity: d.quantity + 1 }))} hitSlop={8}>
                    <MaterialCommunityIcons name="plus-circle-outline" size={28} color={Colors.tomato} />
                  </Pressable>
                </View>
              </View>
              <View style={{ flex: 1.3, gap: 6 }}>
                <Text style={Type.label}>EXPIRES</Text>
                <TextInput
                  style={styles.input}
                  placeholder="YYYY-MM-DD"
                  placeholderTextColor={Colors.textMuted}
                  value={draft.expirationDate}
                  onChangeText={(expirationDate) => setDraft((d) => ({ ...d, expirationDate }))}
                  keyboardType="numbers-and-punctuation"
                />
              </View>
            </View>

            <ErrorText message={error} />
            <Button title={submitLabel} icon={submitIcon} onPress={save} loading={busy} />
          </ScrollView>
        </KeyboardAvoidingView>
      )}

      {stage === "done" && (
        <View style={styles.sheetWrap}>
          <View style={[styles.sheet, styles.doneSheet]}>
            <View style={styles.check}>
              <MaterialCommunityIcons name="check" size={30} color={Colors.white} />
            </View>
            <View style={styles.doneRow}>
              <Art name="hazel-cheer" width={120} />
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={[Type.h1, { color: Colors.oliveDark }]}>{done?.title}</Text>
                <Text style={Type.body}>{done?.body}</Text>
              </View>
            </View>
            <Button title="Scan next item" onPress={reset} />
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#2A1E16" },
  noCamera: { alignItems: "center", justifyContent: "center", gap: Space.lg, padding: Space.xl },
  overlay: { ...StyleSheet.absoluteFillObject, alignItems: "center" },
  hint: {
    marginTop: Space.lg, fontFamily: Fonts.bodyBold, color: Colors.white, fontSize: 15,
    textShadowColor: "#0008", textShadowRadius: 6,
  },
  frame: {
    marginTop: 70, width: 250, height: 250, borderRadius: 28,
    borderWidth: 4, borderColor: Colors.white,
  },
  bottomBar: { position: "absolute", left: Space.gutter, right: Space.gutter, bottom: Space.xl, gap: Space.md },
  sheetWrap: { flex: 1, justifyContent: "flex-end" },
  sheet: {
    backgroundColor: Colors.bg, borderTopLeftRadius: 32, borderTopRightRadius: 32, maxHeight: "80%",
  },
  sheetContent: { padding: Space.gutter, gap: Space.md, paddingBottom: Space.xxl },
  sheetHeader: { flexDirection: "row", alignItems: "center", gap: Space.md },
  input: {
    backgroundColor: Colors.card, borderWidth: 1.5, borderColor: Colors.line, borderRadius: 14,
    paddingHorizontal: 14, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 16, color: Colors.text,
  },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  qtyRow: { flexDirection: "row", gap: Space.md },
  stepper: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: Colors.card, borderRadius: 14, borderWidth: 1.5, borderColor: Colors.line,
    paddingHorizontal: 10, paddingVertical: 8,
  },
  qty: { fontFamily: Fonts.bodyHeavy, fontSize: 20, color: Colors.text },
  doneSheet: { padding: Space.gutter, paddingBottom: Space.xxl, gap: Space.lg, alignItems: "stretch" },
  check: {
    alignSelf: "center", marginTop: -50, width: 64, height: 64, borderRadius: 32,
    backgroundColor: Colors.olive, borderWidth: 4, borderColor: Colors.bg,
    alignItems: "center", justifyContent: "center",
  },
  doneRow: { flexDirection: "row", alignItems: "center", gap: Space.md },
});
