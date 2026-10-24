import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Avatar, ViewSwitcher } from "@/components/AppHeader";
import { Button, Card, Screen } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useProfile } from "@/context/ProfileContext";
import { fetchStashPantries } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors, ViewMode } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const VIEW_LABELS: Record<ViewMode, string> = {
  pantry: "Pantry staff",
  neighbor: "Neighbor",
  donor: "Donor",
};

function Option({ label, selected, color, onPress }: {
  label: string; selected: boolean; color: string; onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={styles.option}>
      <Text style={Type.bodySemi}>{label}</Text>
      <MaterialCommunityIcons
        name={selected ? "radiobox-marked" : "radiobox-blank"}
        size={22}
        color={selected ? color : Colors.line}
      />
    </Pressable>
  );
}

/** Account + preferences; shared by the More tab of every view. */
export default function MoreScreen() {
  const { session, signOut } = useAuth();
  const { profile, update } = useProfile();
  const { data: pantries } = useLoad(fetchStashPantries);
  const meta = session?.user.user_metadata ?? {};

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <Text style={Type.h1}>More</Text>

      <Card style={styles.account}>
        <Avatar size={52} />
        <View style={{ flex: 1 }}>
          <Text style={Type.h3}>{meta.full_name ?? "Your account"}</Text>
          <Text style={Type.muted}>{session?.user.email}</Text>
        </View>
      </Card>

      <Text style={Type.label}>SWITCH VIEW</Text>
      <ViewSwitcher />

      <Text style={Type.label}>DEFAULT VIEW WHEN YOU OPEN STASH</Text>
      <Card style={styles.group}>
        {(Object.keys(VIEW_LABELS) as ViewMode[]).map((v) => (
          <Option
            key={v}
            label={VIEW_LABELS[v]}
            selected={profile?.default_view === v}
            color={ModeColors[v].main}
            onPress={() => update({ default_view: v })}
          />
        ))}
      </Card>

      <Text style={Type.label}>PANTRY YOU WORK AT</Text>
      <Card style={styles.group}>
        {(pantries ?? []).map((p) => (
          <Option
            key={p.id}
            label={p.name}
            selected={profile?.pantry_id === p.id}
            color={Colors.tomato}
            onPress={() => update({ pantry_id: p.id })}
          />
        ))}
        <Option
          label="I don't work at a pantry"
          selected={!profile?.pantry_id}
          color={Colors.tomato}
          onPress={() => update({ pantry_id: null })}
        />
      </Card>

      <Button title="Sign out" variant="outline" icon="logout" color={Colors.danger} onPress={signOut} />
      <Text style={styles.footer}>Stash · Good food. Stronger neighbors.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  account: { flexDirection: "row", alignItems: "center", gap: Space.md },
  group: { paddingVertical: 4 },
  option: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 12,
  },
  footer: { fontFamily: Fonts.bodySemi, color: Colors.textMuted, textAlign: "center", fontSize: 12 },
});
