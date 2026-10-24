import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { Dimensions, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  Art, Button, Card, CategoryIcon, ErrorText, ExpiryBadge, ItemIcon, LevelBadge,
} from "@/components/ui";
import { useProfile } from "@/context/ProfileContext";
import { CATEGORIES } from "@/lib/categories";
import { useUserLocation } from "@/lib/location";
import {
  claimPantry, daysUntil, distanceMiles, fetchCategoryStock, fetchItems, fetchPantry, hoursLabel, isOpenNow,
} from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors } from "@/theme/colors";
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

  const directions = () => {
    if (!p) return;
    const q = encodeURIComponent(`${p.name}, ${p.address}, ${p.city}`);
    Linking.openURL(`http://maps.apple.com/?daddr=${q}&ll=${p.lat},${p.lng}`);
  };

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
        <View>
          <Art name={p?.image_key ?? "illus-pantry-storefront"} width={WIDTH} height={280} rounded={0} cover={Boolean(p?.on_stash)} />
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
              <View style={{ gap: 4 }}>
                <Text style={Type.h1}>{p.name}</Text>
                <Text style={Type.body}>{p.address}, {p.city}</Text>
                {origin && <Text style={Type.muted}>{distanceMiles(origin, p).toFixed(1)} miles away</Text>}
              </View>

              <Card style={styles.hours}>
                <MaterialCommunityIcons name="clock-outline" size={22} color={Colors.text} />
                {p.opens_at && <Text style={[Type.bodySemi, { color: Colors.oliveDark }]}>Open today</Text>}
                <Text style={[Type.bodySemi, { flex: 1 }]}>{hoursLabel(p)}</Text>
              </Card>
              {p.website && (
                <Text style={styles.link} onPress={() => Linking.openURL(p.website!)}>Visit website</Text>
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
              {p.id.startsWith("osm-") && (
                <Text style={styles.credit}>Listing data © OpenStreetMap contributors</Text>
              )}

              {p.on_stash && (
              <>
              <View style={styles.sectionRow}>
                <Text style={Type.h2}>What's available</Text>
                <Text style={Type.muted}>updated today</Text>
              </View>
              <View style={styles.grid}>
                {CATEGORIES.map((c) => {
                  const s = data!.stock.find((x) => x.category === c.key);
                  return (
                    <View key={c.key} style={styles.tile}>
                      <CategoryIcon category={c.key} size={34} />
                      <Text style={styles.tileLabel} numberOfLines={1}>{c.label}</Text>
                      <LevelBadge units={s?.units ?? 0} target={s?.target_units ?? 1} />
                    </View>
                  );
                })}
              </View>

              {grabSoon.length > 0 && (
                <>
                  <View style={styles.sectionRow}>
                    <Text style={Type.h2}>Grab it soon</Text>
                    <Text style={Type.muted}>free · expiring this week</Text>
                  </View>
                  {grabSoon.map((i) => (
                    <Card key={i.id} style={styles.grabRow}>
                      <ItemIcon imageKey={i.image_key} category={i.category} size={40} />
                      <Text style={[Type.bodySemi, { flex: 1 }]}>{i.name}</Text>
                      <ExpiryBadge date={i.expiration_date} />
                    </Card>
                  ))}
                </>
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
          <Pressable style={styles.save} onPress={() => toggleSaved(p.id)}>
            <MaterialCommunityIcons name={saved ? "bookmark" : "bookmark-outline"} size={24} color={Colors.sky} />
          </Pressable>
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
    padding: Space.gutter, gap: Space.lg,
  },
  hours: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12 },
  sectionRow: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  tile: {
    width: (WIDTH - Space.gutter * 2 - 20) / 3, backgroundColor: Colors.card, borderRadius: 16,
    borderWidth: 1.5, borderColor: Colors.line, padding: 10, gap: 6, alignItems: "flex-start",
  },
  tileLabel: { fontFamily: Fonts.bodyBold, fontSize: 12, color: Colors.text },
  link: { ...Type.h3, color: Colors.sky, fontSize: 14 },
  notOnStash: { gap: 10, alignItems: "stretch" },
  credit: { ...Type.muted, fontSize: 11, textAlign: "center" },
  grabRow: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  bottom: {
    position: "absolute", left: 0, right: 0, bottom: 0, flexDirection: "row", gap: Space.md,
    paddingHorizontal: Space.gutter, paddingTop: Space.md, backgroundColor: Colors.bg,
  },
  save: {
    width: 56, height: 56, borderRadius: 16, backgroundColor: Colors.card, borderWidth: 1.5,
    borderColor: Colors.line, alignItems: "center", justifyContent: "center",
  },
});
