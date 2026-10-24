import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { Art, Button, Card, Chip, ErrorText, Screen } from "@/components/ui";
import { CATEGORIES } from "@/lib/categories";
import { mealsPerDollar } from "@/lib/needs";
import { donate, fetchStashPantries, money } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Colors, ModeColors } from "@/theme/colors";
import { Fonts, Space, Type } from "@/theme/type";

const AMOUNTS = [5, 10, 25, 50];
const GREEN = ModeColors.donor;

export default function Give() {
  const params = useLocalSearchParams<{ pantry?: string; category?: string }>();
  const { data: pantries } = useLoad(fetchStashPantries);
  const [pantryId, setPantryId] = useState<string | null>(params.pantry ?? null);
  const [category, setCategory] = useState<string | null>(params.category ?? null);
  const [amount, setAmount] = useState(10);
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thanks, setThanks] = useState<{ cents: number; pantry: string } | null>(null);

  // Deep links from Needs / pantry detail preselect the pantry + category.
  useEffect(() => {
    if (params.pantry) setPantryId(params.pantry);
    if (params.category) setCategory(params.category);
    setThanks(null);
  }, [params.pantry, params.category]);

  useEffect(() => {
    if (!pantryId && pantries?.length) setPantryId(pantries[0].id);
  }, [pantries, pantryId]);

  const dollars = custom ? Number(custom) : amount;
  const valid = Number.isFinite(dollars) && dollars >= 1;
  const pantry = pantries?.find((p) => p.id === pantryId);

  const give = async () => {
    if (!pantryId || !valid) return;
    setBusy(true);
    setError(null);
    try {
      const cents = Math.round(dollars * 100);
      await donate(pantryId, cents, category);
      setThanks({ cents, pantry: pantry?.name ?? "the pantry" });
    } catch (e: any) {
      setError(e?.message ?? "Couldn't complete the gift");
    } finally {
      setBusy(false);
    }
  };

  if (thanks) {
    return (
      <Screen contentStyle={styles.thanks}>
        <Art name="hazel-cheer" width={200} />
        <Text style={[Type.h1, { textAlign: "center" }]}>Thank you!</Text>
        <Text style={[Type.body, { textAlign: "center" }]}>
          Your {money(thanks.cents)} gift to {thanks.pantry} funds about{" "}
          {Math.round((thanks.cents / 100) * mealsPerDollar())} meals.
        </Text>
        <Button title="Give again" color={GREEN.main} dark={GREEN.dark} onPress={() => setThanks(null)} />
      </Screen>
    );
  }

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <Text style={Type.h1}>Give money</Text>
      <Text style={Type.muted}>100% goes to the pantry you pick.</Text>

      <Text style={Type.label}>PANTRY</Text>
      <View style={styles.wrap}>
        {(pantries ?? []).map((p) => (
          <Chip key={p.id} label={p.name} active={pantryId === p.id} color={GREEN.main} onPress={() => setPantryId(p.id)} />
        ))}
      </View>

      <Text style={Type.label}>AMOUNT</Text>
      <View style={styles.amounts}>
        {AMOUNTS.map((a) => (
          <Chip
            key={a}
            label={`$${a}`}
            active={!custom && amount === a}
            color={GREEN.main}
            onPress={() => {
              setCustom("");
              setAmount(a);
            }}
          />
        ))}
        <TextInput
          style={styles.custom}
          placeholder="Other"
          placeholderTextColor={Colors.textMuted}
          keyboardType="decimal-pad"
          value={custom}
          onChangeText={(t) => setCustom(t.replace(/[^0-9.]/g, ""))}
        />
      </View>

      <Card style={styles.estimate}>
        <Text style={styles.estimateNum}>≈ {valid ? Math.round(dollars * mealsPerDollar()) : 0}</Text>
        <Text style={Type.muted}>meals for neighbors</Text>
      </Card>

      <Text style={Type.label}>PUT IT TOWARD (OPTIONAL)</Text>
      <View style={styles.wrap}>
        {CATEGORIES.map((c) => (
          <Chip
            key={c.key}
            label={c.label}
            active={category === c.key}
            color={GREEN.main}
            onPress={() => setCategory(category === c.key ? null : c.key)}
          />
        ))}
      </View>

      <ErrorText message={error} />
      <Button
        title={valid ? `Give ${money(Math.round(dollars * 100))}` : "Give"}
        icon="hand-heart"
        color={GREEN.main}
        dark={GREEN.dark}
        disabled={!valid || !pantryId}
        loading={busy}
        onPress={give}
      />
      <Text style={styles.demo}>Demo checkout: no card is charged.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  amounts: { flexDirection: "row", gap: 8, alignItems: "center" },
  custom: {
    flex: 1, backgroundColor: Colors.card, borderWidth: 1.5, borderColor: Colors.line, borderRadius: 999,
    paddingHorizontal: 14, paddingVertical: 8, fontFamily: Fonts.bodyBold, fontSize: 13, color: Colors.text,
  },
  estimate: { alignItems: "center", backgroundColor: Colors.oliveSoft, borderColor: Colors.oliveSoft },
  estimateNum: { fontFamily: Fonts.displayHeavy, fontSize: 36, color: Colors.oliveDark },
  thanks: { flexGrow: 1, justifyContent: "center", alignItems: "center", gap: Space.lg },
  demo: { fontFamily: Fonts.bodySemi, fontSize: 12, color: Colors.textMuted, textAlign: "center" },
});
