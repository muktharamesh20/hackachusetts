import { useRouter } from "expo-router";
import { Text } from "react-native";
import { PantryRow } from "@/components/PantryBits";
import { EmptyState, ErrorText, Screen } from "@/components/ui";
import { useProfile } from "@/context/ProfileContext";
import { useUserLocation } from "@/lib/location";
import { fetchPantries } from "@/lib/stash";
import { useLoad } from "@/lib/useLoad";
import { Space, Type } from "@/theme/type";

export default function Saved() {
  const router = useRouter();
  const origin = useUserLocation();
  const { profile } = useProfile();
  const { data, error } = useLoad(fetchPantries);
  const saved = (data ?? []).filter((p) => profile?.saved_pantries.includes(p.id));

  return (
    <Screen contentStyle={{ paddingTop: Space.sm }}>
      <Text style={Type.h1}>Saved</Text>
      <ErrorText message={error} />
      {data && saved.length === 0 && (
        <EmptyState title="No saved pantries yet" body="Tap the bookmark on a pantry to keep it here." />
      )}
      {saved.map((p) => (
        <PantryRow key={p.id} pantry={p} origin={origin} onPress={() => router.push(`/pantries/${p.id}`)} />
      ))}
    </Screen>
  );
}
