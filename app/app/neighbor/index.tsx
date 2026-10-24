import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { AppHeader } from "@/components/AppHeader";
import { PantryRow, pantryMeta, sortByDistance, StockChips } from "@/components/PantryBits";
import { Art, Button, Card, ErrorText, Screen } from "@/components/ui";
import { geocode, LatLng, useUserLocation } from "@/lib/location";
import { fetchCategoryStock, fetchPantries, isOpenNow } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Space, Type } from "@/theme/type";

export default function NeighborHome() {
  const router = useRouter();
  const map = useRef<MapView>(null);
  const device = useUserLocation();
  const [searched, setSearched] = useState<LatLng | null>(null);
  const [query, setQuery] = useState("");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const origin = searched ?? device;

  const { data, error } = useLoad(async () => {
    const [pantries, stock] = await Promise.all([fetchPantries(), fetchCategoryStock()]);
    return { pantries, stock };
  });

  const pantries = useMemo(() => sortByDistance(data?.pantries ?? [], origin), [data, origin]);
  const selected = pantries.find((p) => p.id === selectedId) ?? pantries[0];
  const others = pantries.filter((p) => p.id !== selected?.id).slice(0, 8);

  // Frame the nearest few pantries (and you) once they load or the origin changes.
  useEffect(() => {
    if (!pantries.length) return;
    const points = pantries.slice(0, origin ? 4 : pantries.length).map((p) => ({ latitude: p.lat, longitude: p.lng }));
    if (origin) points.push({ latitude: origin.lat, longitude: origin.lng });
    setTimeout(() => {
      map.current?.fitToCoordinates(points, {
        edgePadding: { top: 40, right: 40, bottom: 40, left: 40 },
        animated: true,
      });
    }, 300);
  }, [pantries.length, origin?.lat, origin?.lng]);

  const onSearch = async () => {
    const q = query.trim();
    if (!q) {
      setSearched(null);
      return;
    }
    setSearchError(null);
    try {
      const hit = await geocode(q);
      if (hit) setSearched(hit);
      else setSearchError(`Couldn't find "${q}"`);
    } catch {
      setSearchError(`Couldn't find "${q}"`);
    }
  };

  return (
    <Screen>
      <AppHeader />

      <View style={styles.searchRow}>
        <View style={styles.search}>
          <MaterialCommunityIcons name="magnify" size={20} color={Colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by address or zip code"
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={onSearch}
            returnKeyType="search"
          />
        </View>
        <Pressable style={styles.filter} onPress={() => router.push("/neighbor/pantries")}>
          <MaterialCommunityIcons name="tune-variant" size={20} color={Colors.text} />
        </Pressable>
      </View>
      <ErrorText message={searchError ?? error} />

      <View style={styles.mapWrap}>
        <MapView
          ref={map}
          style={StyleSheet.absoluteFill}
          showsUserLocation
          initialRegion={{ latitude: 42.365, longitude: -71.105, latitudeDelta: 0.09, longitudeDelta: 0.09 }}
        >
          {pantries.map((p) => {
            const active = p.id === selected?.id;
            const color = active ? Colors.sky : !p.on_stash ? Colors.textMuted : isOpenNow(p) ? Colors.olive : Colors.tomato;
            return (
              <Marker
                key={p.id}
                coordinate={{ latitude: p.lat, longitude: p.lng }}
                onPress={() => setSelectedId(p.id)}
                tracksViewChanges={false}
              >
                <View style={[styles.pin, { backgroundColor: color }, active && styles.pinActive]}>
                  <MaterialCommunityIcons name="storefront" size={18} color={Colors.white} />
                </View>
              </Marker>
            );
          })}
        </MapView>
      </View>

      {selected && data && (
        <Card style={{ gap: 12, marginTop: -40 }}>
          <Pressable style={styles.selectedTop} onPress={() => router.push(`/pantries/${selected.id}`)}>
            <Art name={selected.image_key ?? "illus-pantry-storefront"} width={76} height={64} rounded={12} cover={Boolean(selected.image_key)} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[Type.h2, { fontSize: 18 }]}>{selected.name}</Text>
              <Text style={Type.muted}>{pantryMeta(selected, origin)}</Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
          </Pressable>
          <Text style={styles.goodLabel}>Good stock in</Text>
          <StockChips stock={data.stock} pantryId={selected.id} />
          <Button title="View details" onPress={() => router.push(`/pantries/${selected.id}`)} />
        </Card>
      )}

      {others.map((p) => (
        <PantryRow key={p.id} pantry={p} origin={origin} onPress={() => router.push(`/pantries/${p.id}`)} />
      ))}
      <Text style={styles.credit}>Pantry listings include data © OpenStreetMap contributors</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  searchRow: { flexDirection: "row", gap: Space.sm },
  search: {
    flex: 1, flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: Colors.card,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.line, paddingHorizontal: 14,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 14, color: Colors.text },
  filter: {
    width: 46, height: 46, borderRadius: 23, backgroundColor: Colors.card, borderWidth: 1.5,
    borderColor: Colors.line, alignItems: "center", justifyContent: "center",
  },
  mapWrap: { height: 260, borderRadius: 24, overflow: "hidden", borderWidth: 1.5, borderColor: Colors.line },
  pin: {
    width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center",
    borderWidth: 3, borderColor: Colors.white,
  },
  pinActive: { transform: [{ scale: 1.2 }] },
  selectedTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  credit: { fontFamily: Fonts.body, fontSize: 11, color: Colors.textMuted, textAlign: "center" },
  goodLabel: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.text },
});
