import { useRouter } from "expo-router";
import { RefreshControl, Share, StyleSheet, Text, View } from "react-native";
import { Art, Button, Card, CategoryIcon, EmptyState, ErrorText, Meter, Screen } from "@/components/ui";
import { computeNeeds, Need } from "@/lib/needs";
import { fetchCategoryStock, fetchPantries } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors } from "@/theme/colors";
import { Space, Type } from "@/theme/type";

function shareNeed(n: Need) {
  return Share.share({
    message:
      `${n.pantry.name} is running low on ${n.category.label.toLowerCase()}: ${n.short} items short this week. ` +
      `Drop off at ${n.pantry.address}, ${n.pantry.city}, or find it on Stash.`,
  });
}

export default function Needs() {
  const router = useRouter();
  const { data, error, refreshing, refresh } = useLoad(async () => {
    const [pantries, stock] = await Promise.all([fetchPantries(), fetchCategoryStock()]);
    return computeNeeds(pantries, stock);
  });

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <View style={styles.hero}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={Type.h1}>What's needed</Text>
          <Text style={Type.muted}>Live from pantry shelves. Most urgent first.</Text>
        </View>
        <Art name="hazel-worried" width={96} />
      </View>
      <ErrorText message={error} />
      {data?.length === 0 && <EmptyState art="hazel-cheer" title="Every shelf is stocked!" body="Check back soon." />}
      {data?.map((n) => (
        <Card key={`${n.pantry.id}-${n.category.key}`} style={{ gap: 12 }}>
          <View style={styles.top}>
            <CategoryIcon category={n.category.key} size={44} />
            <View style={{ flex: 1 }}>
              <Text style={Type.h3}>{n.pantry.name} needs {n.category.label}</Text>
              <Text style={Type.muted}>{n.short} items short of this week's goal</Text>
            </View>
          </View>
          <Meter units={n.units} target={n.target} />
          <View style={styles.actions}>
            <Button
              title="Give $"
              color={ModeColors.donor.main}
              dark={ModeColors.donor.dark}
              style={{ flex: 1 }}
              onPress={() => router.push({ pathname: "/donor/give", params: { pantry: n.pantry.id, category: n.category.key } })}
            />
            <Button title="Share" variant="outline" icon="share-variant-outline" color={Colors.sky} style={{ flex: 1 }} onPress={() => shareNeed(n)} />
          </View>
          <Text style={styles.link} onPress={() => router.push(`/pantries/${n.pantry.id}`)}>Drop off food here</Text>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: Space.md },
  top: { flexDirection: "row", alignItems: "center", gap: 12 },
  actions: { flexDirection: "row", gap: 10 },
  link: { ...Type.h3, fontSize: 14, color: Colors.sky, textAlign: "center" },
});
