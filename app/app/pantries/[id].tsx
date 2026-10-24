import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Dimensions, Linking, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  Art, Button, Card, CategoryIcon, ErrorText, ExpiryBadge, ItemIcon, Meter,
} from "@/components/ui";
import { useProfile } from "@/context/ProfileContext";
import { CATEGORIES } from "@/lib/categories";
import { useUserLocation } from "@/lib/location";
import {
  claimPantry, daysUntil, distanceMiles, fetchCategoryStock, fetchItems, fetchPantry, hoursLabel, isOpenNow,
} from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors, Tint } from "@/theme/colors";
import { Fonts, Radii, Shadow, Space, Type } from "@/theme/type";

const WIDTH = Dimensions.get("window").width;

export default function PantryDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const origin = useUserLocation();
  const { profile, toggleSaved, mode, setMode, refresh } = useProfile();
  const [claiming, setClaiming] = useState(false);
  const [claimError, setClaimError] = useState<string | null>(null);
  const saved = profile?.saved_pantries.includes(id) ?? false;

  const { data, error } = useLoad(async () => {
    const [pantry, stock, items] = await Promise.all([fetchPantry(id), fetchCategoryStock(id), fetchItems(id)]);
    return { pantry, stock, items };
  }, [id]);

  const p = data?.pantry;
  const grabSoon = (data?.items ?? [])
    .filter((i) => {
      const d = daysUntil(i.expiration_date);
      return d !== null && d >= 0 && d <= 7;
    })
    .slice(0, 6);

  const claim = async () => {
    setClaiming(true);
    setClaimError(null);
    try {
      await claimPantry(id);
      await refresh();
      setMode("pantry");
      router.replace("/pantry");
    } catch (e: any) {
      setClaimError(e?.message ?? "Couldn't claim this pantry");
    } finally {
      setClaiming(false);
    }
  };

  const share = () => {
    if (!p) return;
    const where = [p.address, p.city].filter(Boolean).join(", ");
    Share.share({ message: `${p.name}: free food for anyone who needs it. ${where}. Find it on Stash.` });
  };

  const directions = () => {
    if (!p) return;
    const q = encodeURIComponent(`${p.name}, ${p.address}, ${p.city}`);
    Linking.openURL(`http://maps.apple.com/?daddr=${q}&ll=${p.lat},${p.lng}`);
  };

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View>
          {p?.image_key ? (
            <Art name={p.image_key} width={WIDTH} height={280} rounded={0} cover />
          ) : p ? (
            // No licensed photo: show the pantry's real location instead.
            <MapView
              style={{ width: WIDTH, height: 280 }}
              pointerEvents="none"
              showsPointsOfInterest={false}
              initialRegion={{ latitude: p.lat - 0.0012, longitude: p.lng, latitudeDelta: 0.008, longitudeDelta: 0.008 }}
            >
              <Marker coordinate={{ latitude: p.lat, longitude: p.lng }} pinColor={Colors.tomato} />
            </MapView>
          ) : (
            <View style={{ width: WIDTH, height: 280, backgroundColor: Colors.cardAlt }} />
          )}
          <SafeAreaView edges={["top"]} style={styles.heroBar}>
            <Pressable onPress={() => router.back()} style={styles.circleBtn} hitSlop={8}>
              <MaterialCommunityIcons name="chevron-left" size={26} color={Colors.text} />
            </Pressable>
            {p && (
              <Text style={[styles.openPill, !isOpenNow(p) && { color: Colors.textMuted }]}>
                {isOpenNow(p) ? "Open now" : "Closed now"}
              </Text>
            )}
          </SafeAreaView>
        </View>

        <View style={styles.body}>
          <ErrorText message={error} />
          {p && (
            <>
              <View style={{ gap: 6 }}>
                <View style={styles.titleRow}>
                  <Text style={[Type.h1, { flex: 1 }]}>{p.name}</Text>
                  <Pressable onPress={() => toggleSaved(p.id)} hitSlop={10} style={styles.iconBtn}>
                    <MaterialCommunityIcons name={saved ? "bookmark" : "bookmark-outline"} size={24} color={Colors.sky} />
                  </Pressable>
                  <Pressable onPress={share} hitSlop={10} style={styles.iconBtn}>
                    <MaterialCommunityIcons name="share-variant-outline" size={23} color={Colors.sky} />
                  </Pressable>
                </View>
                <Text style={Type.muted}>
                  {[p.address, p.city].filter(Boolean).join(", ")}
                  {origin ? `  ·  ${distanceMiles(origin, p).toFixed(1)} mi` : ""}
                </Text>
                <View style={styles.hours}>
                  <MaterialCommunityIcons name="clock-outline" size={18} color={Colors.textMuted} />
                  {p.opens_at && <Text style={Type.bodySemi}>Today</Text>}
                  <Text style={[Type.body, { flexShrink: 1 }]}>{hoursLabel(p)}</Text>
                  {p.website && (
                    <Text style={styles.link} onPress={() => Linking.openURL(p.website!)}>Website</Text>
                  )}
                </View>
              </View>

              {p.on_stash && (
                <Card
                  style={styles.dropCard}
                  onPress={() => {
                    setMode("donor");
                    router.push({ pathname: "/donor/scan", params: { pantry: p.id } });
                  }}
                >
                  <View style={styles.dropIcon}>
                    <MaterialCommunityIcons name="barcode-scan" size={22} color={Colors.white} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={Type.h3}>Bringing food here?</Text>
                    <Text style={Type.muted}>Scan your drop-off so volunteers don't have to.</Text>
                  </View>
                  <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
                </Card>
              )}

              {!p.on_stash && (
                <Card style={styles.notOnStash}>
                  <Art name="hazel-acorn-hug" width={110} style={{ alignSelf: "center" }} />
                  <Text style={[Type.h2, { textAlign: "center" }]}>This pantry isn't on Stash yet</Text>
                  <Text style={[Type.muted, { textAlign: "center" }]}>
                    So we can't show live stock here. Hours and details come from public listings; check
                    before you go. Work or volunteer at {p.name}? Set it up in a minute.
                  </Text>
                  <ErrorText message={claimError} />
                  <Button title="Claim this pantry" icon="storefront-outline" onPress={claim} loading={claiming} />
                </Card>
              )}
              {p.image_credit && (
                <Text
                  style={styles.credit}
                  onPress={() => p.image_credit_url && Linking.openURL(p.image_credit_url)}
                >
                  Representative photo. {p.image_credit}
                </Text>
              )}
              {p.id.startsWith("osm-") && (
                <Text style={styles.credit}>Listing data © OpenStreetMap contributors</Text>
              )}

              {p.on_stash && (
              <>
              <View style={{ gap: 12 }}>
                <View style={styles.sectionRow}>
                  <Text style={Type.h2}>What's available</Text>
                  <Text style={Type.muted}>updated today</Text>
                </View>
                {CATEGORIES.map((c) => {
                  const st = data!.stock.find((x) => x.category === c.key);
                  const units = st?.units ?? 0;
                  const target = st?.target_units ?? 1;
                  return (
                    <View key={c.key} style={styles.stockRow}>
                      <CategoryIcon category={c.key} size={28} plain />
                      <Text style={styles.stockLabel} numberOfLines={1}>{c.label}</Text>
                      <Meter units={units} target={target} height={8} />
                    </View>
                  );
                })}
              </View>

              {grabSoon.length > 0 && (
                <View>
                  <View style={[styles.sectionRow, { marginBottom: 4 }]}>
                    <Text style={Type.h2}>Grab it soon</Text>
                    <Text style={Type.muted}>free · this week</Text>
                  </View>
                  {grabSoon.map((i, n) => (
                    <View key={i.id} style={[styles.grabRow, n > 0 && styles.divider]}>
                      <ItemIcon imageKey={i.image_key} category={i.category} size={36} />
                      <Text style={[Type.bodySemi, { flex: 1 }]}>{i.name}</Text>
                      <ExpiryBadge date={i.expiration_date} />
                    </View>
                  ))}
                </View>
              )}
              </>
              )}
            </>
          )}
        </View>
      </ScrollView>

      {p && (
        <SafeAreaView edges={["bottom"]} style={styles.bottom}>
          {mode === "donor" && p.on_stash ? (
            <Button
              title="Give to this pantry"
              icon="hand-heart"
              color={ModeColors.donor.main}
              dark={ModeColors.donor.dark}
              style={{ flex: 1 }}
              onPress={() => router.push({ pathname: "/donor/give", params: { pantry: p.id } })}
            />
          ) : (
            <Button
              title="Get directions"
              icon="navigation-variant"
              color={Colors.sky}
              dark={Colors.skyDark}
              style={{ flex: 1 }}
              onPress={directions}
            />
          )}
        </SafeAreaView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  heroBar: {
    position: "absolute", left: Space.gutter, right: Space.gutter, top: 0,
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
  },
  circleBtn: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: Colors.card,
    alignItems: "center", justifyContent: "center", ...Shadow,
  },
  openPill: {
    fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.oliveDark, backgroundColor: Colors.card,
    paddingHorizontal: 14, paddingVertical: 7, borderRadius: Radii.pill, overflow: "hidden",
  },
  body: {
    marginTop: -24, backgroundColor: Colors.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28,
    padding: Space.gutter, gap: Space.xl,
  },
  titleRow: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
  iconBtn: { paddingTop: 6 },
  hours: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 4 },
  sectionRow: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  stockRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  stockLabel: { fontFamily: Fonts.bodySemi, fontSize: 14, color: Colors.text, width: 108 },
  divider: { borderTopWidth: 1, borderTopColor: Colors.line },
  link: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.sky, marginLeft: 4 },
  notOnStash: { gap: 10, alignItems: "stretch" },
  dropCard: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  dropIcon: {
    width: 42, height: 42, borderRadius: 14, backgroundColor: Tint.olive.ink,
    alignItems: "center", justifyContent: "center",
  },
  credit: { ...Type.muted, fontSize: 11, textAlign: "center" },
  grabRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10 },
  bottom: {
    position: "absolute", left: 0, right: 0, bottom: 0, flexDirection: "row", gap: Space.md,
    paddingHorizontal: Space.gutter, paddingTop: Space.md, backgroundColor: Colors.bg,
  },
});
