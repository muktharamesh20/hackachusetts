import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { Dimensions, Pressable, StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { AppHeader } from "@/components/AppHeader";
import { PantryRow, pantryMeta, PantryThumb, sortByDistance, StockChips } from "@/components/PantryBits";
import { Art, Button, Card, ErrorText, Screen } from "@/components/ui";
import { useUserLocation } from "@/lib/location";
import { fetchCategoryStock, fetchPantries, isOpenNow } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Shadow, Space, Type } from "@/theme/type";

export default function NeighborHome() {
  const router = useRouter();
  const map = useRef<MapView>(null);
  const device = useUserLocation();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const origin = device;

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


  return (
    <Screen>
      <AppHeader />

      <ErrorText message={error} />


      <View style={styles.mapFrame}>
      <View style={styles.mapWrap}>
        <MapView
          ref={map}
          style={StyleSheet.absoluteFill}
          showsUserLocation
          showsPointsOfInterest={false}
          showsBuildings={false}
          showsCompass={false}
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
                <View style={[styles.pinWrap, active && styles.pinActive]}>
                  <View style={[styles.pin, { backgroundColor: color }]}>
                    <MaterialCommunityIcons name="home-variant" size={18} color={Colors.white} style={styles.pinIcon} />
                  </View>
                </View>
              </Marker>
            );
          })}
        </MapView>
        {origin && (
          <Pressable
            style={styles.recenter}
            hitSlop={8}
            onPress={() =>
              map.current?.animateToRegion(
                { latitude: origin.lat, longitude: origin.lng, latitudeDelta: 0.06, longitudeDelta: 0.06 },
                400,
              )
            }
          >
            <MaterialCommunityIcons name="crosshairs-gps" size={20} color={Colors.sky} />
          </Pressable>
        )}
      </View>
      </View>

      {selected && data && (
        <Card style={styles.selectedCard}>
          <Pressable style={styles.selectedTop} onPress={() => router.push(`/pantries/${selected.id}`)}>
            <PantryThumb pantry={selected} width={76} height={64} />
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

      <View style={styles.legend}>
        {[
          { color: Colors.olive, label: "Open now" },
          { color: Colors.tomato, label: "Closed now" },
          { color: Colors.textMuted, label: "Not on Stash yet" },
        ].map((l) => (
          <View key={l.label} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: l.color }]} />
            <Text style={styles.legendText}>{l.label}</Text>
          </View>
        ))}
      </View>


      {others.map((p) => (
        <PantryRow key={p.id} pantry={p} origin={origin} onPress={() => router.push(`/pantries/${p.id}`)} />
      ))}
      <Text style={styles.credit}>Pantry listings include data © OpenStreetMap contributors</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  // Same language as cards: thin even border + soft shadow (shadow on the frame,
  // clipping on the inner view so iOS doesn't cut the shadow off).
  mapFrame: { borderRadius: 24, backgroundColor: Colors.card, ...Shadow, shadowOpacity: 0.12, shadowRadius: 16 },
  // Nearly square so the map has real presence on the page.
  mapWrap: {
    height: Math.round((Dimensions.get("window").width - Space.gutter * 2) * 0.92),
    borderRadius: 24, overflow: "hidden", borderWidth: 1.5, borderColor: Colors.line,
  },
  recenter: {
    position: "absolute", right: 12, bottom: 12, width: 40, height: 40, borderRadius: 20,
    backgroundColor: Colors.white, alignItems: "center", justifyContent: "center", ...Shadow,
  },
  // Floats over the bottom of the map, like a sheet for the tapped pin.
  selectedCard: { gap: 12, marginTop: -(Space.lg + 30) },
  legend: { flexDirection: "row", justifyContent: "center", gap: Space.lg },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontFamily: Fonts.bodySemi, fontSize: 12, color: Colors.textMuted },
  pinWrap: { width: 40, height: 48, alignItems: "center" },
  pinIcon: { transform: [{ rotate: "-45deg" }] },
  pin: {
    width: 36, height: 36, borderRadius: 18, borderBottomRightRadius: 3,
    transform: [{ rotate: "45deg" }], alignItems: "center", justifyContent: "center",
    borderWidth: 3, borderColor: Colors.white,
    shadowColor: "#000", shadowOpacity: 0.25, shadowRadius: 4, shadowOffset: { width: 0, height: 2 },
  },
  pinActive: { transform: [{ scale: 1.25 }] },
  selectedTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  credit: { fontFamily: Fonts.body, fontSize: 11, color: Colors.textMuted, textAlign: "center" },
  goodLabel: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.text },
});
