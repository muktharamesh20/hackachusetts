import { Link } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { GoogleButton } from "@/components/GoogleButton";
import { useAuth } from "@/context/AuthContext";
import { isSupabaseConfigured } from "@/lib/supabase";
import { Colors } from "@/theme/colors";

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
        <Text style={styles.logo}>🥫 PantrySort</Text>
        <Text style={styles.subtitle}>Sign in to manage pantry inventory</Text>

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
  logo: { fontSize: 34, fontWeight: "800", color: Colors.primary, textAlign: "center" },
  subtitle: { fontSize: 15, color: Colors.textMuted, textAlign: "center", marginBottom: 18 },
  input: {
    backgroundColor: Colors.card, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: Colors.text,
  },
  button: {
    backgroundColor: Colors.primary, borderRadius: 12, paddingVertical: 16,
    alignItems: "center", marginTop: 6,
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  error: { color: Colors.danger, fontSize: 14, textAlign: "center" },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: 10 },
  footerText: { color: Colors.textMuted, fontSize: 15 },
  link: { color: Colors.primary, fontSize: 15, fontWeight: "700" },
});
