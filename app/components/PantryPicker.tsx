import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useMemo, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { PantryThumb } from "@/components/PantryBits";
import { Card } from "@/components/ui";
import { Pantry } from "@/lib/stash";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

/** The chosen pantry as a card with a "Switch" button that opens a searchable picker. */
export function PantrySelect({ pantries, value, onChange, color = Colors.olive, label = "Pantry" }: {
  pantries: Pantry[];
  value: string | null;
  onChange: (id: string) => void;
  color?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const selected = pantries.find((p) => p.id === value);
  return (
    <>
      <Card style={styles.selected} onPress={() => setOpen(true)}>
        <PantryThumb pantry={selected} width={56} height={48} />
        <View style={{ flex: 1 }}>
          <Text style={Type.label}>{label.toUpperCase()}</Text>
          <Text style={Type.h3} numberOfLines={1}>{selected?.name ?? "Choose a pantry"}</Text>
          {selected && <Text style={Type.muted} numberOfLines={1}>{selected.city}</Text>}
        </View>
        <Text style={[styles.switch, { color }]}>Switch</Text>
      </Card>
      <PantryPickerModal
        visible={open}
        pantries={pantries}
        value={value}
        color={color}
        onClose={() => setOpen(false)}
        onPick={(id) => {
          onChange(id);
          setOpen(false);
        }}
      />
    </>
  );
}

/** Full-screen search over pantries. */
export function PantryPickerModal({ visible, pantries, value, color = Colors.olive, onClose, onPick }: {
  visible: boolean;
  pantries: Pantry[];
  value: string | null;
  color?: string;
  onClose: () => void;
  onPick: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? pantries.filter((p) => `${p.name} ${p.address} ${p.city}`.toLowerCase().includes(q)) : pantries;
  }, [pantries, query]);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={styles.page} edges={["bottom"]}>
        <View style={styles.header}>
          <Text style={Type.h2}>Choose a pantry</Text>
          <Pressable onPress={onClose} hitSlop={10}>
            <Text style={[styles.switch, { color }]}>Done</Text>
          </Pressable>
        </View>
        <View style={styles.search}>
          <MaterialCommunityIcons name="magnify" size={20} color={Colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name or town"
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={setQuery}
            autoFocus
            clearButtonMode="while-editing"
          />
        </View>
        <FlatList
          data={list}
          keyExtractor={(p) => p.id}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingHorizontal: Space.gutter, paddingBottom: Space.xl }}
          ItemSeparatorComponent={() => <View style={styles.divider} />}
          ListEmptyComponent={<Text style={[Type.muted, { textAlign: "center", marginTop: Space.xl }]}>No pantries match.</Text>}
          renderItem={({ item: p }) => (
            <Pressable style={styles.row} onPress={() => onPick(p.id)}>
              <PantryThumb pantry={p} width={48} height={40} rounded={10} />
              <View style={{ flex: 1 }}>
                <Text style={Type.bodySemi}>{p.name}</Text>
                <Text style={Type.muted}>{[p.address, p.city].filter(Boolean).join(", ")}</Text>
              </View>
              <MaterialCommunityIcons
                name={p.id === value ? "check-circle" : "circle-outline"}
                size={22}
                color={p.id === value ? color : Colors.line}
              />
            </Pressable>
          )}
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  selected: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  switch: { fontFamily: Fonts.bodyHeavy, fontSize: 15 },
  page: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: Space.gutter, paddingTop: Space.lg, paddingBottom: Space.md,
  },
  search: {
    flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: Colors.card, marginHorizontal: Space.gutter,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.line, paddingHorizontal: 14, marginBottom: Space.sm,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 15, color: Colors.text },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  divider: { height: 1, backgroundColor: Colors.line },
});
