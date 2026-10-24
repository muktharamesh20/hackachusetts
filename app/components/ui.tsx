import { MaterialCommunityIcons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { HeaderShownContext } from "@react-navigation/elements";
import { useNavigation } from "@react-navigation/native";
import { ReactNode, useContext, useRef } from "react";
import {
  ActivityIndicator, Image, NativeScrollEvent, NativeSyntheticEvent, Pressable, ScrollView, ScrollViewProps, StyleProp,
  StyleSheet, Text, View, ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ART, artSource } from "@/lib/art";
import { categoryInfo, LEVEL_STYLE, stockLevel } from "@/lib/categories";
import { daysUntil } from "@/lib/stash";
import { Colors } from "@/theme/colors";
import { Fonts, Radii, Shadow, Space, Type } from "@/theme/type";

export type IconName = keyof typeof MaterialCommunityIcons.glyphMap;

// --- layout ---

export function Screen({
  children, scroll = true, edges = ["top"], contentStyle, ...rest
}: {
  children: ReactNode;
  scroll?: boolean;
  edges?: ("top" | "bottom")[];
  contentStyle?: StyleProp<ViewStyle>;
} & ScrollViewProps) {
  // Under a navigator header (the home TopBar), the header already handles the top inset.
  const headerShown = useContext(HeaderShownContext);
  // Tell the header to show its divider once content scrolls under it.
  const navigation = useNavigation();
  const scrolled = useRef(false);
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    rest.onScroll?.(e);
    if (!headerShown) return;
    const next = e.nativeEvent.contentOffset.y > 2;
    if (next !== scrolled.current) {
      scrolled.current = next;
      navigation.setOptions({ headerShadowVisible: next });
    }
  };
  return (
    <SafeAreaView style={styles.screen} edges={headerShown ? edges.filter((e) => e !== "top") : edges}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={[styles.screenContent, contentStyle]}
          showsVerticalScrollIndicator={false}
          {...rest}
          onScroll={onScroll}
          scrollEventThrottle={16}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.screenContent, { flex: 1 }, contentStyle]}>{children}</View>
      )}
    </SafeAreaView>
  );
}

export function Card({ children, style, onPress }: {
  children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void;
}) {
  if (!onPress) return <View style={[styles.card, style]}>{children}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, style, pressed && styles.pressed]}>
      {children}
    </Pressable>
  );
}

export function SectionHeader({ title, action, onAction }: {
  title: string; action?: string; onAction?: () => void;
}) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={Type.h2}>{title}</Text>
      {action && (
        <Pressable onPress={onAction} hitSlop={8}>
          <Text style={styles.sectionAction}>{action}</Text>
        </Pressable>
      )}
    </View>
  );
}

// --- art ---

/** A generated illustration, or a labeled placeholder until it exists. */
export function Art({ name, width, height, style, rounded = 16, cover = false }: {
  name: string; width: number; height?: number; style?: StyleProp<ViewStyle>; rounded?: number;
  /** Fill the box (cropping) instead of fitting inside it; for photos/scenes. */
  cover?: boolean;
}) {
  const h = height ?? width;
  const src = artSource(name);
  if (src) {
    return (
      <Image
        source={src}
        style={[{ width, height: h }, cover && { borderRadius: rounded }, style as any]}
        resizeMode={cover ? "cover" : "contain"}
      />
    );
  }
  return (
    <View style={[styles.artPlaceholder, { width, height: h, borderRadius: rounded }, style]}>
      <MaterialCommunityIcons name="image-outline" size={Math.min(28, width / 3)} color={Colors.textMuted} />
      {width >= 72 && <Text style={styles.artLabel} numberOfLines={2}>{name}</Text>}
    </View>
  );
}

export function CategoryIcon({ category, size = 36 }: { category: string; size?: number }) {
  const info = categoryInfo(category);
  const src = artSource(info.art);
  if (src) {
    return (
      <View style={[styles.catIcon, { width: size, height: size, borderRadius: size / 2, backgroundColor: info.tint + "26" }]}>
        <Image source={src} style={{ width: size * 0.78, height: size * 0.78 }} resizeMode="contain" />
      </View>
    );
  }
  return (
    <View style={[styles.catIcon, { width: size, height: size, borderRadius: size / 2, backgroundColor: info.tint + "22" }]}>
      <MaterialCommunityIcons name={info.icon as IconName} size={size * 0.55} color={info.tint} />
    </View>
  );
}

/** An item's own illustration (e.g. item-canned-beans), else its category icon. */
export function ItemIcon({ imageKey, category, size = 44 }: { imageKey: string | null; category: string; size?: number }) {
  const src = imageKey ? artSource(imageKey) : null;
  if (!src) return <CategoryIcon category={category} size={size} />;
  return <Image source={src} style={{ width: size, height: size }} resizeMode="contain" />;
}

// --- controls ---

export function Button({ title, onPress, color = Colors.tomato, dark = Colors.tomatoDark, icon, loading, disabled, variant = "solid", style }: {
  title: string;
  onPress: () => void;
  color?: string;
  dark?: string;
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  variant?: "solid" | "outline";
  style?: StyleProp<ViewStyle>;
}) {
  const solid = variant === "solid";
  return (
    <Pressable
      disabled={disabled || loading}
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        onPress();
      }}
      style={({ pressed }) => [
        styles.button,
        solid
          ? { backgroundColor: color, borderBottomColor: dark }
          : { backgroundColor: Colors.card, borderColor: Colors.line, borderWidth: 1.5, borderBottomWidth: 3, borderBottomColor: Colors.line },
        (disabled || loading) && { opacity: 0.6 },
        pressed && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={solid ? Colors.white : Colors.text} />
      ) : (
        <>
          {icon && <MaterialCommunityIcons name={icon} size={20} color={solid ? Colors.white : color} />}
          <Text style={[styles.buttonText, { color: solid ? Colors.white : Colors.text }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

export function Chip({ label, active, onPress, color = Colors.tomato, soft }: {
  label: string; active?: boolean; onPress?: () => void; color?: string; soft?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        active ? { backgroundColor: color, borderColor: color } : soft ? { backgroundColor: soft, borderColor: soft } : null,
      ]}
    >
      <Text style={[styles.chipText, active && { color: Colors.white }]}>{label}</Text>
    </Pressable>
  );
}

export function Badge({ label, color, soft }: { label: string; color: string; soft: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: soft }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

// --- stock ---

export function Meter({ units, target, height = 14 }: { units: number; target: number; height?: number }) {
  const level = LEVEL_STYLE[stockLevel(units, target)];
  const pct = Math.max(0.06, Math.min(1, target ? units / target : 1));
  return (
    <View style={[styles.meterTrack, { height, borderRadius: height / 2 }]}>
      <View style={{ width: `${pct * 100}%`, height, borderRadius: height / 2, backgroundColor: level.color }} />
    </View>
  );
}

export function LevelBadge({ units, target }: { units: number; target: number }) {
  const level = LEVEL_STYLE[stockLevel(units, target)];
  return <Badge label={level.label} color={level.color === Colors.mustard ? "#A97A12" : level.color} soft={level.soft} />;
}

/** Expiry sticker: olive > 14 days, mustard <= 14, tomato <= 2. */
export function ExpiryBadge({ date }: { date: string | null }) {
  const d = daysUntil(date);
  if (d === null) return <Badge label="No expiry" color={Colors.textMuted} soft={Colors.cardAlt} />;
  if (d < 0) return <Badge label="Expired" color={Colors.white} soft={Colors.danger} />;
  const label = d === 0 ? "Today" : d === 1 ? "1 day" : d > 60 ? `${Math.round(d / 30)} mo` : `${d} days`;
  if (d <= 2) return <Badge label={label} color={Colors.tomato} soft={Colors.tomatoSoft} />;
  if (d <= 14) return <Badge label={label} color="#A97A12" soft={Colors.mustardSoft} />;
  return <Badge label={label} color={Colors.oliveDark} soft={Colors.oliveSoft} />;
}

export function StatTile({ value, label, color = Colors.text }: { value: string | number; label: string; color?: string }) {
  return (
    <View style={styles.statTile}>
      <Text style={[Type.stat, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export function EmptyState({ art = "hazel-acorn-hug", title, body }: { art?: string; title: string; body?: string }) {
  return (
    <View style={styles.empty}>
      <Art name={art} width={120} />
      <Text style={[Type.h2, { textAlign: "center" }]}>{title}</Text>
      {body && <Text style={[Type.muted, { textAlign: "center" }]}>{body}</Text>}
    </View>
  );
}

export function ErrorText({ message }: { message: string | null }) {
  if (!message) return null;
  return <Text style={styles.error}>{message}</Text>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.bg },
  screenContent: { paddingHorizontal: Space.gutter, paddingBottom: Space.xxl, gap: Space.lg },
  card: {
    backgroundColor: Colors.card, borderRadius: Radii.card, borderWidth: 1.5,
    borderColor: Colors.line, padding: Space.lg, ...Shadow,
  },
  pressed: { transform: [{ scale: 0.97 }] },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: Space.sm },
  sectionAction: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.sky },
  artPlaceholder: {
    backgroundColor: Colors.cardAlt, borderWidth: 1.5, borderStyle: "dashed", borderColor: Colors.line,
    alignItems: "center", justifyContent: "center", padding: 6, gap: 2,
  },
  artLabel: { fontFamily: Fonts.bodySemi, fontSize: 10, color: Colors.textMuted, textAlign: "center" },
  catIcon: { alignItems: "center", justifyContent: "center" },
  button: {
    flexDirection: "row", gap: 10, alignItems: "center", justifyContent: "center",
    borderRadius: Radii.button, paddingVertical: 15, paddingHorizontal: 20, borderBottomWidth: 3,
  },
  buttonText: { fontFamily: Fonts.bodyHeavy, fontSize: 16 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: Radii.pill,
    borderWidth: 1.5, borderColor: Colors.line, backgroundColor: Colors.card,
  },
  chipText: { fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.text },
  badge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: Radii.pill, alignSelf: "flex-start" },
  badgeText: { fontFamily: Fonts.bodyHeavy, fontSize: 12 },
  meterTrack: { flex: 1, backgroundColor: Colors.cardAlt, overflow: "hidden" },
  statTile: {
    flex: 1, backgroundColor: Colors.card, borderRadius: Radii.card, borderWidth: 1.5,
    borderColor: Colors.line, paddingVertical: 14, alignItems: "center", ...Shadow,
  },
  statLabel: { fontFamily: Fonts.bodySemi, fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  empty: { alignItems: "center", gap: Space.sm, paddingVertical: Space.xxl, paddingHorizontal: Space.xl },
  error: { fontFamily: Fonts.bodySemi, color: Colors.danger, fontSize: 14, textAlign: "center" },
});
