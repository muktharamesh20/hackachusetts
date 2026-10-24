import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { createClient } from "@supabase/supabase-js";
import { AppState, Platform } from "react-native";

/**
 * SecureStore has a ~2KB per-key limit and Supabase session JSON can exceed it,
 * so large values are chunked. If the keychain is unavailable we fall back to
 * AsyncStorage. On web, SecureStore doesn't exist, so use AsyncStorage directly.
 * (Pattern adapted from a prior Expo + Supabase app.)
 */
const CHUNK_SIZE = 1800;
let useFallback = Platform.OS === "web";

const SecureStoreAdapter = {
  getItem: async (key: string): Promise<string | null> => {
    if (useFallback) return AsyncStorage.getItem(key);
    try {
      const countStr = await SecureStore.getItemAsync(`${key}__count`);
      if (!countStr) return await SecureStore.getItemAsync(key);
      const chunks: string[] = [];
      for (let i = 0; i < parseInt(countStr, 10); i++) {
        const c = await SecureStore.getItemAsync(`${key}__chunk_${i}`);
        if (c === null) return null;
        chunks.push(c);
      }
      return chunks.join("");
    } catch {
      return AsyncStorage.getItem(key);
    }
  },
  setItem: async (key: string, value: string): Promise<void> => {
    if (useFallback) return AsyncStorage.setItem(key, value);
    try {
      if (value.length <= CHUNK_SIZE) {
        await SecureStore.setItemAsync(key, value);
        await SecureStore.deleteItemAsync(`${key}__count`).catch(() => {});
        return;
      }
      const chunks: string[] = [];
      for (let i = 0; i < value.length; i += CHUNK_SIZE) chunks.push(value.slice(i, i + CHUNK_SIZE));
      for (let i = 0; i < chunks.length; i++) await SecureStore.setItemAsync(`${key}__chunk_${i}`, chunks[i]);
      await SecureStore.setItemAsync(`${key}__count`, String(chunks.length));
      await SecureStore.deleteItemAsync(key).catch(() => {});
    } catch {
      useFallback = true;
      await AsyncStorage.setItem(key, value);
    }
  },
  removeItem: async (key: string): Promise<void> => {
    if (useFallback) return AsyncStorage.removeItem(key);
    try {
      const countStr = await SecureStore.getItemAsync(`${key}__count`);
      if (countStr) {
        for (let i = 0; i < parseInt(countStr, 10); i++) {
          await SecureStore.deleteItemAsync(`${key}__chunk_${i}`).catch(() => {});
        }
        await SecureStore.deleteItemAsync(`${key}__count`).catch(() => {});
      }
      await SecureStore.deleteItemAsync(key).catch(() => {});
    } catch {
      useFallback = true;
      await AsyncStorage.removeItem(key);
    }
  },
};

const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const isSupabaseConfigured = Boolean(url && anonKey);

export const supabase = createClient(url, anonKey, {
  auth: {
    storage: SecureStoreAdapter,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// Resume token refresh when the app returns to the foreground.
AppState.addEventListener("change", (state) => {
  if (state === "active") supabase.auth.startAutoRefresh();
  else supabase.auth.stopAutoRefresh();
});
