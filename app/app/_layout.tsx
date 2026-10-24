import {
  Fraunces_700Bold, Fraunces_800ExtraBold,
} from "@expo-google-fonts/fraunces";
import {
  Nunito_400Regular, Nunito_600SemiBold, Nunito_700Bold, Nunito_800ExtraBold, useFonts,
} from "@expo-google-fonts/nunito";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ProfileProvider, useProfile } from "@/context/ProfileContext";
import { hydrateAppData } from "@/lib/appData";
import { Colors } from "@/theme/colors";

const VIEW_ROOTS = ["pantry", "neighbor", "donor", "items", "pantries", "rescue"];

function RootNavigator() {
  const { session, loading: authLoading } = useAuth();
  const { profile, loading: profileLoading, mode } = useProfile();
  const segments = useSegments();
  const router = useRouter();
  const loading = authLoading || (session && profileLoading);

  useEffect(() => {
    if (loading) return;
    const root = segments[0] as string | undefined;
    if (!root) return; // app/index.tsx redirects from "/"
    if (!session) {
      if (root !== "(auth)") router.replace("/(auth)/sign-in");
    } else if (!profile) {
      if (root !== "onboarding") router.replace("/onboarding");
    } else if (!VIEW_ROOTS.includes(root)) {
      router.replace(`/${mode}`);
    }
  }, [session, profile, loading, segments]);

  // Keep the navigator mounted while loading so redirects always have a target.
  return (
    <>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: Colors.bg } }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="onboarding" />
        <Stack.Screen name="pantry" options={{ animation: "fade" }} />
        <Stack.Screen name="neighbor" options={{ animation: "fade" }} />
        <Stack.Screen name="donor" options={{ animation: "fade" }} />
      </Stack>
      {loading && (
        <View style={[StyleSheet.absoluteFill, styles.loading]}>
          <ActivityIndicator size="large" color={Colors.tomato} />
        </View>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  loading: { justifyContent: "center", alignItems: "center", backgroundColor: Colors.bg },
});

export default function RootLayout() {
  // Categories + settings from Supabase; fall back to bundled defaults after 3s.
  const [dataReady, setDataReady] = useState(false);
  useEffect(() => {
    const timeout = new Promise((resolve) => setTimeout(resolve, 3000));
    Promise.race([hydrateAppData().catch(() => {}), timeout]).finally(() => setDataReady(true));
  }, []);
  const [fontsLoaded] = useFonts({
    Fraunces_700Bold, Fraunces_800ExtraBold,
    Nunito_400Regular, Nunito_600SemiBold, Nunito_700Bold, Nunito_800ExtraBold,
  });
  if (!fontsLoaded || !dataReady) return <View style={{ flex: 1, backgroundColor: Colors.bg }} />;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <StatusBar style="dark" />
      <AuthProvider>
        <ProfileProvider>
          <RootNavigator />
        </ProfileProvider>
      </AuthProvider>
    </GestureHandlerRootView>
  );
}
