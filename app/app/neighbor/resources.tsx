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
      <Text style={Type.h1}>Resources</Text>
      <View style={styles.hero}>
        <Text style={[Type.body, { flex: 1, color: Colors.textMuted }]}>
          More help beyond the pantry shelf. All free.
        </Text>
        <Art name="hazel-wave" width={90} />
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
  hero: { flexDirection: "row", alignItems: "center", gap: Space.md },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  cta: { ...Type.h3, color: Colors.sky, fontSize: 14 },
});
