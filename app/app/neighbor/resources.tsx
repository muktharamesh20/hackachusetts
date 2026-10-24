import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Linking, StyleSheet, Text, View } from "react-native";
import { Art, Card, ErrorText, IconName, Screen } from "@/components/ui";
import { fetchResources } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors } from "@/theme/colors";
import { Space, Type } from "@/theme/type";

export default function Resources() {
  const { data, error } = useLoad(fetchResources);
  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 4 }}>
        <Text style={Type.h1}>Resources</Text>
        <Text style={[Type.body, styles.subtitle]}>More help beyond the pantry shelf. All free.</Text>
        </View>
        <Art name="hazel-wave" width={84} />
      </View>
      <ErrorText message={error} />
      {(data ?? []).map((r) => (
        <Card key={r.title} style={{ gap: 8 }} onPress={() => Linking.openURL(r.url)}>
          <View style={styles.titleRow}>
            <MaterialCommunityIcons name={r.icon as IconName} size={24} color={Colors.sky} />
            <Text style={[Type.h3, { flex: 1 }]}>{r.title}</Text>
          </View>
          <Text style={Type.muted}>{r.body}</Text>
          <Text style={styles.cta}>{r.cta}</Text>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  // Hazel sized to the title + tagline block, beside it.
  header: { flexDirection: "row", alignItems: "center", gap: Space.md },
  subtitle: { color: Colors.textMuted },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  cta: { ...Type.h3, color: Colors.sky, fontSize: 14 },
});
