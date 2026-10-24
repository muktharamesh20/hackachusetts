import { MaterialCommunityIcons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "@/context/AuthContext";
import { useProfile } from "@/context/ProfileContext";
import { Colors, ModeColors, ViewMode } from "@/theme/colors";
import { Fonts, Radii, Type } from "@/theme/type";
import type { IconName } from "./ui";

const MODES: { key: ViewMode; label: string; icon: IconName }[] = [
  { key: "pantry", label: "Pantry", icon: "storefront-outline" },
  { key: "neighbor", label: "Neighbor", icon: "home-heart" },
  { key: "donor", label: "Donor", icon: "hand-heart-outline" },
];

export function Avatar({ size = 38 }: { size?: number }) {
  const { session } = useAuth();
  const meta = session?.user.user_metadata ?? {};
  const photo: string | undefined = meta.avatar_url ?? meta.picture;
  const initial = (meta.full_name ?? session?.user.email ?? "?").trim()[0]?.toUpperCase();
  const style = { width: size, height: size, borderRadius: size / 2 };
  if (photo) return <Image source={{ uri: photo }} style={[style, styles.avatarRing]} />;
  return (
    <View style={[style, styles.avatarRing, styles.avatarFallback]}>
      <Text style={styles.avatarText}>{initial}</Text>
    </View>
  );
}

/** Fixed top bar on each view's home: "Stash" + avatar (opens More).
 *  `line` shows a faint divider once the content underneath has scrolled. */
export function TopBar({ line = false }: { line?: boolean }) {
  const router = useRouter();
  const { mode } = useProfile();
  return (
    <SafeAreaView edges={["top"]} style={[styles.bar, line && styles.barLine]}>
      <View style={styles.top}>
        <Text style={Type.logo}>Stash</Text>
        <Pressable onPress={() => router.push(`/${mode}/more`)} hitSlop={8}>
          <Avatar />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

/** Top of each view's home: the Pantry / Neighbor / Donor switcher. */
export function AppHeader() {
  return (
    <View style={styles.wrap}>
      <ViewSwitcher />
    </View>
  );
}

export function ViewSwitcher() {
  const router = useRouter();
  const { mode, setMode } = useProfile();
  return (
    <View style={styles.switcher}>
      {MODES.map((m) => {
        const active = m.key === mode;
        const color = ModeColors[m.key].main;
        return (
          <Pressable
            key={m.key}
            onPress={() => {
              if (active) return;
              Haptics.selectionAsync().catch(() => {});
              setMode(m.key);
              router.replace(`/${m.key}`);
            }}
            style={[styles.seg, active && { backgroundColor: color }]}
          >
            <MaterialCommunityIcons name={m.icon} size={16} color={active ? Colors.white : Colors.textMuted} />
            <Text style={[styles.segText, active && { color: Colors.white }]}>{m.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Shared bottom-tab styling; active color follows the view. */
export function tabOptions(mode: ViewMode) {
  return {
    // Only each view's home shows the TopBar (see the index screens in the tab layouts).
    headerShown: false,
    header: ({ options }: { options: { headerShadowVisible?: boolean } }) => (
      <TopBar line={options.headerShadowVisible === true} />
    ),
    headerShadowVisible: false,
    tabBarActiveTintColor: ModeColors[mode].main,
    tabBarInactiveTintColor: Colors.textMuted,
    tabBarLabelStyle: { fontFamily: Fonts.bodyBold, fontSize: 11 },
    tabBarStyle: {
      backgroundColor: Colors.card,
      borderTopColor: Colors.line,
      borderTopWidth: 1.5,
      height: 88,
      paddingTop: 8,
    },
  };
}

export function tabIcon(name: IconName) {
  return ({ color, size }: { color: string; size: number }) => (
    <MaterialCommunityIcons name={name} size={size} color={color} />
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: Colors.bg, paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "transparent",
  },
  barLine: { borderBottomColor: Colors.line },
  wrap: { paddingTop: 4 },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 8 },
  avatarRing: { borderWidth: 2, borderColor: Colors.card },
  avatarFallback: { backgroundColor: Colors.mustard, alignItems: "center", justifyContent: "center" },
  avatarText: { fontFamily: Fonts.bodyHeavy, color: Colors.white, fontSize: 16 },
  switcher: {
    flexDirection: "row", backgroundColor: Colors.card, borderRadius: Radii.pill,
    borderWidth: 1.5, borderColor: Colors.line, padding: 4, alignSelf: "flex-start",
  },
  seg: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: Radii.pill,
  },
  segText: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.textMuted },
});
