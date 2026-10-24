import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useAuth } from "@/context/AuthContext";
import { Colors } from "@/theme/colors";

export default function SettingsScreen() {
  const { session, signOut } = useAuth();
  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.label}>Signed in as</Text>
        <Text style={styles.value}>{session?.user?.email ?? "unknown"}</Text>
      </View>
      <TouchableOpacity style={styles.signOut} onPress={signOut}>
        <Text style={styles.signOutText}>Sign out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: 16, gap: 16 },
  card: { backgroundColor: Colors.card, borderRadius: 14, padding: 16, borderWidth: 1, borderColor: Colors.border },
  label: { fontSize: 13, color: Colors.textMuted },
  value: { fontSize: 16, fontWeight: "700", color: Colors.text, marginTop: 4 },
  signOut: { backgroundColor: Colors.danger, borderRadius: 12, paddingVertical: 16, alignItems: "center" },
  signOutText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
