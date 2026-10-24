import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Share, StyleSheet, Text, View } from "react-native";
import { Art, Card, ErrorText, Screen } from "@/components/ui";
import { categoryInfo, stockLevel } from "@/lib/categories";
import { CategoryStock, fetchCategoryStock, fetchStashPantries, Pantry } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Space, Type } from "@/theme/type";

function message(p: Pantry, stock: CategoryStock[]): string {
  const low = stock
    .filter((s) => s.pantry_id === p.id && stockLevel(s.units, s.target_units) === "low")
    .map((s) => categoryInfo(s.category).label.toLowerCase());
  const ask = low.length ? ` They're running low on ${low.join(" and ")}, so donations help too.` : "";
  return `${p.name} has free food for anyone who needs it, no questions asked. ${p.address}, ${p.city}.${ask} Find it on Stash.`;
}

export default function ShareTab() {
  const { data, error } = useLoad(async () => {
    const [pantries, stock] = await Promise.all([fetchStashPantries(), fetchCategoryStock()]);
    return { pantries, stock };
  });

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <View style={styles.hero}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={Type.h1}>Spread the word</Text>
          <Text style={Type.muted}>
            Lots of neighbors don't know free food is nearby. One share can change someone's week.
          </Text>
        </View>
        <Art name="illus-megaphone" width={96} />
      </View>
      <ErrorText message={error} />
      {data?.pantries.map((p) => (
        <Card key={p.id} style={styles.row} onPress={() => Share.share({ message: message(p, data.stock) })}>
          <Art name={p.image_key ?? "illus-pantry-storefront"} width={60} height={50} rounded={12} cover={Boolean(p.image_key)} />
          <View style={{ flex: 1 }}>
            <Text style={Type.h3}>{p.name}</Text>
            <Text style={Type.muted}>{p.city}</Text>
          </View>
          <MaterialCommunityIcons name="share-variant" size={22} color={Colors.sky} />
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: Space.md },
  row: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
});
