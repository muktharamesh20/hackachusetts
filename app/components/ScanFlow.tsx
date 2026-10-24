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
import { addDays, findExpiry } from "@/lib/expiry";
import { CatalogItem, findCatalogItem, findItemByBarcode, rememberCode } from "@/lib/stash";
import { recognizeText } from "@/modules/text-reader";
import { Colors, Tint } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

export type ScanDraft = {
  barcode: string | null;
  name: string;
  category: CategoryKey | null;
  quantity: number;
  expirationDate: string; // YYYY-MM-DD or ""
  known: boolean; // matches an item already in this pantry
  inCatalog: boolean; // the code is already in the shared product catalog
  /** Where the date came from: printed label, read off the package, estimated, or typed. */
  expirySource: "label" | "package" | "estimated" | "manual" | null;
  /** True when the date is a shelf-life guess staff should double-check. */
  expiryEstimated: boolean;
  /** Catalog facts for the scanned code (calories, allergens, tags, notes). */
  facts: CatalogItem | null;
};

type Draft = ScanDraft;

/** What the success sheet says after a submit. */
export type ScanDone = { title: string; body: string };

const EMPTY: Draft = {
  barcode: null, name: "", category: null, quantity: 1, expirationDate: "", known: false, inCatalog: false,
  expirySource: null, expiryEstimated: false, facts: null,
};

/** Product facts from the catalog, shown on the form and saved with the item. */
function Facts({ facts }: { facts: CatalogItem }) {
  const pills = [
    facts.unit_calories ? `${facts.unit_calories} kcal` : null,
    facts.allergens.length ? `Contains ${facts.allergens.join(", ")}` : "No listed allergens",
    ...facts.tags,
  ].filter(Boolean) as string[];
  return (
    <View style={styles.facts}>
      <Text style={Type.label}>FROM THE PRODUCT CATALOG</Text>
      <View style={styles.factsRow}>
        {pills.map((p) => <Text key={p} style={styles.factPill}>{p}</Text>)}
      </View>
      {facts.good_to_know.length > 0 && <Text style={Type.muted}>{facts.good_to_know.join("  ·  ")}</Text>}
    </View>
  );
}

/** Snap the current camera frame and look for a printed expiry date. */
async function readExpiryFromPackage(camera: CameraView | null): Promise<string | null> {
  if (!camera) return null;
  try {
    const photo = await camera.takePictureAsync({ quality: 0.6, skipProcessing: true, shutterSound: false });
    if (!photo?.uri) return null;
    return findExpiry(await recognizeText(photo.uri));
  } catch {
    return null;
  }
}

/**
 * Camera + QR/barcode lookup + item form, shared by staff and donor scanning.
 * `onSubmit` decides what saving means; return null to go straight back to the
 * camera (e.g. a donor adding to their bag), or a message for the success sheet.
 */
export function ScanFlow({ pantryId, submitLabel, submitIcon = "package-variant-closed", onSubmit, onCode, topSlot, bottomSlot, idleTitle, hint = "Point at a QR label or barcode" }: {
  /** Pantry to match scanned codes against existing items (null: skip). */
  pantryId: string | null;
  submitLabel: string;
  submitIcon?: React.ComponentProps<typeof Button>["icon"];
  onSubmit: (draft: ScanDraft) => Promise<ScanDone | null>;
  /** Handle special codes (e.g. a drop-off slip) before the item form; return true if handled. */
  onCode?: (code: string) => boolean;
  /** Shown under the hint while the camera is up (e.g. a pantry picker). */
  topSlot?: ReactNode;
  /** Shown above "Type it in instead" while the camera is up (e.g. a bag bar). */
  bottomSlot?: ReactNode;
  idleTitle?: string;
  /** Line over the camera. */
  hint?: string;
}) {
  const focused = useIsFocused();
  const [permission, requestPermission] = useCameraPermissions();
  const [stage, setStage] = useState<"camera" | "form" | "done">("camera");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [done, setDone] = useState<ScanDone | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const camera = useRef<CameraView>(null);
  const [reading, setReading] = useState(false);

  const onScanned = async ({ data }: BarcodeScanningResult) => {
    if (lock.current || stage !== "camera") return;
    lock.current = true;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    if (onCode?.(data)) {
      setTimeout(() => (lock.current = false), 1500); // don't re-fire while navigating away
      return;
    }
    const label = parseLabel(data);
    setReading(true);
    // Look the code up and, unless the label printed a date, read one off the package.
    const [existing, known, packageDate] = await Promise.all([
      pantryId ? findItemByBarcode(pantryId, label.code).catch(() => null) : null,
      findCatalogItem(label.sku ?? label.code).catch(() => null),
      label.expirationDate ? null : readExpiryFromPackage(camera.current),
    ]);
    setReading(false);
    // Expiry: printed on our label > read off the package > estimated from shelf life.
    let expirationDate = "";
    let expirySource: Draft["expirySource"] = null;
    if (label.expirationDate) [expirationDate, expirySource] = [label.expirationDate, "label"];
    else if (packageDate) [expirationDate, expirySource] = [packageDate, "package"];
    else if (known?.shelf_life_days) [expirationDate, expirySource] = [addDays(known.shelf_life_days), "estimated"];
    setDraft({
      barcode: label.code,
      name: existing?.name ?? known?.name ?? "",
      category: (existing?.category as CategoryKey) ?? (known?.category as CategoryKey) ?? label.category,
      quantity: 1,
      expirationDate,
      known: Boolean(existing),
      inCatalog: Boolean(known),
      expirySource,
      expiryEstimated: expirySource === "estimated",
      facts: known,
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
      // First time anyone names this code: remember it so the next scan fills in.
      if (draft.barcode && !draft.inCatalog) {
        rememberCode(draft.barcode, draft.name.trim(), draft.category).catch(() => {});
      }
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
          ref={camera}
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
          {reading ? "Reading the package…" : stage === "camera" ? hint : " "}
        </Text>
        {stage === "camera" && topSlot}
        {stage === "camera" && permission?.granted && <View style={styles.frame} pointerEvents="none" />}
      </SafeAreaView>

      {stage === "camera" && (
        <View style={styles.bottomBar}>
          {bottomSlot}
          <Button
            title="No barcode? Type it in"
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
                  onChangeText={(expirationDate) =>
                    setDraft((d) => ({ ...d, expirationDate, expirySource: "manual", expiryEstimated: false }))
                  }
                  keyboardType="numbers-and-punctuation"
                />
              </View>
            </View>
            {draft.expirySource && draft.expirySource !== "manual" && (
              <View style={[styles.dateNote, draft.expiryEstimated && styles.dateNoteWarn]}>
                <MaterialCommunityIcons
                  name={draft.expiryEstimated ? "alert-circle-outline" : "check-circle-outline"}
                  size={18}
                  color={draft.expiryEstimated ? Tint.mustard.ink : Tint.olive.ink}
                />
                <Text style={styles.dateNoteText}>
                  {draft.expirySource === "package"
                    ? "Date read from the package. Glance to make sure it's right."
                    : draft.expirySource === "label"
                      ? "Date from the Stash label."
                      : `Estimated from typical shelf life (${draft.facts?.shelf_life_days} days). Check the package and fix it if needed; staff will double-check.`}
                </Text>
              </View>
            )}

            {draft.facts && <Facts facts={draft.facts} />}

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
  dateNote: {
    flexDirection: "row", gap: 8, alignItems: "flex-start", padding: 10, borderRadius: 12,
    backgroundColor: Tint.olive.bg, borderWidth: 1, borderColor: Tint.olive.border,
  },
  dateNoteWarn: { backgroundColor: Tint.mustard.bg, borderColor: Tint.mustard.border },
  dateNoteText: { flex: 1, fontFamily: Fonts.bodySemi, fontSize: 13, color: Colors.text },
  facts: { gap: 8, padding: 12, borderRadius: 14, backgroundColor: Colors.card, borderWidth: 1.5, borderColor: Colors.line },
  factsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  factPill: {
    fontFamily: Fonts.bodyBold, fontSize: 12, color: Colors.text, backgroundColor: Colors.cardAlt,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: Radii.pill, overflow: "hidden",
  },
  bottomBar: { position: "absolute", left: Space.gutter, right: Space.gutter, bottom: Space.xl, gap: Space.md },
  sheetWrap: { flex: 1, justifyContent: "flex-end" },
  // flexGrow 0: size the sheet to its content instead of stretching to maxHeight.
  sheet: {
    backgroundColor: Colors.bg, borderTopLeftRadius: 32, borderTopRightRadius: 32, maxHeight: "85%", flexGrow: 0,
  },
  sheetContent: { padding: Space.gutter, gap: Space.md, paddingBottom: Space.lg },
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
