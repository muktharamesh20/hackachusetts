import { useState } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useAuth } from "@/context/AuthContext";
import { Colors } from "@/theme/colors";
import { Fonts } from "@/theme/type";

/** "or" divider + Continue with Google. Errors are reported via onError. */
export function GoogleButton({ onError }: { onError: (message: string | null) => void }) {
  const { signInWithGoogle } = useAuth();
  const [busy, setBusy] = useState(false);

  const onPress = async () => {
    onError(null);
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch (e: any) {
      onError(e?.message ?? "Google sign in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <View style={styles.dividerRow}>
        <View style={styles.line} />
        <Text style={styles.or}>or</Text>
        <View style={styles.line} />
      </View>
      <TouchableOpacity style={styles.button} onPress={onPress} disabled={busy}>
        {busy ? (
          <ActivityIndicator color={Colors.text} />
        ) : (
          <>
            <Text style={styles.g}>G</Text>
            <Text style={styles.buttonText}>Continue with Google</Text>
          </>
        )}
      </TouchableOpacity>
    </>
  );
}

const styles = StyleSheet.create({
  dividerRow: { flexDirection: "row", alignItems: "center", gap: 10, marginVertical: 2 },
  line: { flex: 1, height: 1, backgroundColor: Colors.border },
  or: { color: Colors.textMuted, fontSize: 14, fontFamily: Fonts.body },
  button: {
    flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 10,
    backgroundColor: Colors.card, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 16, paddingVertical: 15, borderBottomWidth: 3,
  },
  g: { fontSize: 18, fontWeight: "800", color: "#4285F4" },
  buttonText: { color: Colors.text, fontSize: 16, fontFamily: Fonts.bodyBold },
});
