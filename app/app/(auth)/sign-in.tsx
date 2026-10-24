import { Link } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { GoogleButton } from "@/components/GoogleButton";
import { Art } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { isSupabaseConfigured } from "@/lib/supabase";
import { Colors } from "@/theme/colors";
import { Fonts } from "@/theme/type";

export default function SignIn() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!isSupabaseConfigured) {
      setError("Supabase isn't configured. Set EXPO_PUBLIC_SUPABASE_URL and _ANON_KEY in app/.env");
      return;
    }
    setBusy(true);
    try {
      await signIn(email.trim(), password);
    } catch (e: any) {
      setError(e?.message ?? "Sign in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.container}
      >
        <Art name="hazel-wave" width={130} style={{ alignSelf: "center" }} />
        <Text style={styles.logo}>Stash</Text>
        <Text style={styles.subtitle}>Good food. Stronger neighbors.</Text>

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={Colors.textMuted}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={Colors.textMuted}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity style={styles.button} onPress={onSubmit} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign in</Text>}
        </TouchableOpacity>

        <GoogleButton onError={setError} />

        <View style={styles.footer}>
          <Text style={styles.footerText}>No account? </Text>
          <Link href="/(auth)/sign-up" style={styles.link}>Create one</Link>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  container: { flex: 1, justifyContent: "center", paddingHorizontal: 28, gap: 14 },
  logo: { fontFamily: Fonts.displayHeavy, fontSize: 44, color: Colors.text, textAlign: "center", letterSpacing: -1 },
  subtitle: { fontFamily: Fonts.body, fontSize: 15, color: Colors.textMuted, textAlign: "center", marginBottom: 14 },
  input: {
    backgroundColor: Colors.card, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 14, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: Colors.text, fontFamily: Fonts.body,
  },
  button: {
    backgroundColor: Colors.primary, borderRadius: 16, paddingVertical: 16, borderBottomWidth: 3, borderBottomColor: Colors.tomatoDark,
    alignItems: "center", marginTop: 6,
  },
  buttonText: { color: "#fff", fontSize: 16, fontFamily: Fonts.bodyHeavy },
  error: { color: Colors.danger, fontSize: 14, textAlign: "center", fontFamily: Fonts.bodySemi },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: 10 },
  footerText: { color: Colors.textMuted, fontSize: 15, fontFamily: Fonts.body },
  link: { color: Colors.primary, fontSize: 15, fontFamily: Fonts.bodyHeavy },
});
