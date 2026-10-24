import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { RefreshControl, StyleSheet, Text, View } from "react-native";
import { AppHeader } from "@/components/AppHeader";
import { Art, Card, ErrorText, Screen, StatTile } from "@/components/ui";
import { computeNeeds, mealsPerDollar, topShortage } from "@/lib/needs";
import { fetchCategoryStock, fetchMyDonations, fetchPantries, money } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, Tint } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const WAYS = [
  { title: "Donate\nFood", art: "illus-donate-food", href: "/donor/needs" },
  { title: "Give\nMoney", art: "illus-give-money", href: "/donor/give" },
] as const;

export default function DonorHome() {
  const router = useRouter();
  const { data, error, refreshing, refresh } = useLoad(async () => {
    const [pantries, stock, donations] = await Promise.all([fetchPantries(), fetchCategoryStock(), fetchMyDonations()]);
    return { needs: computeNeeds(pantries, stock), donations };
  });

  const shortage = data ? topShortage(data.needs) : null;
  const examples = shortage?.category.donorHint ?? "";
  const givenCents = data?.donations.reduce((n, d) => n + d.amount_cents, 0) ?? 0;

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <AppHeader />

      <View style={styles.hero}>
        <View style={{ flex: 1, gap: 8 }}>
          <Text style={Type.h1}>Neighbors need your support.</Text>
          <Text style={Type.muted}>Give food, give funds, or spread the word. Every little bit helps.</Text>
        </View>
        <Art name="hazel-heart" width={120} />
      </View>

      <ErrorText message={error} />

      <Card style={styles.scanCard} onPress={() => router.push("/donor/scan")}>
        <View style={styles.scanIcon}>
          <MaterialCommunityIcons name="barcode-scan" size={26} color={Colors.white} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={Type.h3}>Bringing food? Scan it in yourself</Text>
          <Text style={Type.muted}>Saves volunteers time. Scan each item, then drop off your bag.</Text>
        </View>
        <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
      </Card>

      {shortage && (
        <Card style={styles.alert} onPress={() => router.push("/donor/needs")}>
          <MaterialCommunityIcons name="alert-circle-outline" size={30} color={Tint.mustard.ink} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={Type.h3}>Running low on {shortage.category.label.toLowerCase()}</Text>
            <Text style={Type.muted}>
              {shortage.pantries} {shortage.pantries === 1 ? "pantry needs" : "pantries need"} it right now. {examples}
            </Text>
          </View>
          <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
        </Card>
      )}

      <Text style={Type.h2}>Ways to help</Text>
      <View style={styles.ways}>
        {WAYS.map((w) => (
          <Card key={w.title} style={styles.way} onPress={() => router.push(w.href)}>
            <Art name={w.art} width={72} />
            <View style={styles.wayRow}>
              <Text style={styles.wayTitle}>{w.title}</Text>
              <MaterialCommunityIcons name="chevron-right" size={20} color={Colors.text} />
            </View>
          </Card>
        ))}
      </View>

      <Card style={styles.share} onPress={() => router.push("/donor/share")}>
        <Art name="illus-megaphone" width={64} />
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={Type.h3}>Spread the word</Text>
          <Text style={Type.muted}>Help more neighbors find free food pantries near them.</Text>
        </View>
        <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
      </Card>

      {givenCents > 0 && (
        <>
          <Text style={Type.h2}>Your impact</Text>
          <View style={styles.stats}>
            <StatTile value={money(givenCents)} label="given" color={Colors.olive} />
            <StatTile value={Math.round((givenCents / 100) * mealsPerDollar())} label="meals funded" color={Colors.tomato} />
            <StatTile value={data!.donations.length} label="gifts" color={Colors.sky} />
          </View>
        </>
      )}
    </Screen>
  );
}


const styles = StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: Space.md, marginTop: Space.sm },
  alert: {
    flexDirection: "row", alignItems: "center", gap: 12,
    backgroundColor: Tint.mustard.bg, borderColor: Tint.mustard.border,
  },
  scanCard: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: Tint.olive.bg, borderColor: Tint.olive.border },
  scanIcon: {
    width: 48, height: 48, borderRadius: 16, backgroundColor: Tint.olive.ink,
    alignItems: "center", justifyContent: "center",
  },
  ways: { flexDirection: "row", gap: 10 },
  way: { flex: 1, padding: 12, gap: 6 },
  wayRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 4 },
  wayTitle: { fontFamily: Fonts.display, fontSize: 15, color: Colors.text, flexShrink: 1 },
  share: { flexDirection: "row", alignItems: "center", gap: 12 },
  stats: { flexDirection: "row", gap: Space.sm },
});
