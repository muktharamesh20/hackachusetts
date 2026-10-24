import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Art, Card, ErrorText, Screen } from "@/components/ui";
import { useProfile } from "@/context/ProfileContext";
import { fetchStashPantries, Pantry } from "@/lib/stash";
import { useAuth } from "@/context/AuthContext";
import { Colors, ViewMode } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const CHOICES: { mode: ViewMode; art: string; title: string; body: string }[] = [
  { mode: "pantry", art: "onboard-pantry", title: "I run or volunteer at a pantry", body: "Track stock, see what's expiring, and more." },
  { mode: "neighbor", art: "onboard-neighbor", title: "I'm a neighbor looking for food", body: "See what's available near you. Always free." },
  { mode: "donor", art: "onboard-donor", title: "I want to donate or support", body: "See what's needed and make an impact." },
];

export default function Onboarding() {
  const { update } = useProfile();
  const { signOut } = useAuth();
  const [step, setStep] = useState<"role" | "pantry">("role");
  const [pantries, setPantries] = useState<Pantry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStashPantries().then(setPantries).catch(() => {});
  }, []);

  const finish = async (mode: ViewMode, pantryId: string | null = null) => {
    setError(null);
    try {
      await update({ default_view: mode, pantry_id: pantryId });
    } catch (e: any) {
      setError(e?.message ?? "Couldn't save your choice");
    }
  };

  if (step === "pantry") {
    return (
      <Screen contentStyle={styles.content}>
        <Art name="hazel-wave" width={150} style={styles.center} />
        <Text style={[Type.h1, styles.centerText]}>Which pantry?</Text>
        <Text style={[Type.muted, styles.centerText]}>You can change this later in Settings.</Text>
        {pantries.map((p) => (
          <Card key={p.id} onPress={() => finish("pantry", p.id)} style={styles.choice}>
            <Art name={p.image_key ?? "illus-pantry-storefront"} width={64} />
            <View style={{ flex: 1 }}>
              <Text style={Type.h3}>{p.name}</Text>
              <Text style={Type.muted}>{p.address}, {p.city}</Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
          </Card>
        ))}
        <ErrorText message={error} />
        <Text style={[Type.muted, styles.centerText]}>
          Don't see yours? Find it in the Neighbor map and tap "Claim this pantry".
        </Text>
        <Text style={styles.back} onPress={() => setStep("role")}>Back</Text>
      </Screen>
    );
  }

  return (
    <Screen contentStyle={styles.content}>
      <View style={styles.center}>
        <Text style={styles.logo}>Stash</Text>
        <Text style={Type.muted}>Good food. Stronger neighbors.</Text>
      </View>
      <Art name="hazel-wave" width={190} style={styles.center} />
      <Text style={[Type.h1, styles.centerText]}>What brings you here?</Text>
      <Text style={[Type.body, styles.centerText, { color: Colors.textMuted }]}>
        One account. All three views.{"\n"}You can switch anytime.
      </Text>
      {CHOICES.map((c) => (
        <Card
          key={c.mode}
          style={styles.choice}
          onPress={() => (c.mode === "pantry" ? setStep("pantry") : finish(c.mode))}
        >
          <Art name={c.art} width={76} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.choiceTitle}>{c.title}</Text>
            <Text style={Type.muted}>{c.body}</Text>
          </View>
          <MaterialCommunityIcons name="chevron-right" size={24} color={Colors.text} />
        </Card>
      ))}
      <ErrorText message={error} />
      <Text style={styles.back} onPress={signOut}>Not you? Sign out</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: Space.xl, gap: Space.md },
  center: { alignSelf: "center", alignItems: "center" },
  centerText: { textAlign: "center" },
  logo: { fontFamily: Fonts.displayHeavy, fontSize: 48, color: Colors.text, letterSpacing: -1 },
  choice: { flexDirection: "row", alignItems: "center", gap: Space.md },
  choiceTitle: { fontFamily: Fonts.display, fontSize: 17, color: Colors.text },
  back: { fontFamily: Fonts.bodyBold, color: Colors.textMuted, textAlign: "center", padding: Space.md },
});
