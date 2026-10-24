import { GoogleSignin } from "@react-native-google-signin/google-signin";
import { Platform } from "react-native";
import { supabase } from "./supabase";

/**
 * Native Google Sign-In -> Supabase session via signInWithIdToken.
 * (Pattern adapted from a prior Expo + Supabase app.)
 *
 * iOS client ID: Google Cloud OAuth client of type iOS, bundle com.muktha.pantrysort.
 * Web client ID: required on Android for an idToken; optional on iOS.
 */
const IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID?.trim() ?? "";
const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID?.trim() ?? "";

export const isGoogleConfigured =
  Platform.OS === "ios" ? Boolean(IOS_CLIENT_ID) : Boolean(WEB_CLIENT_ID);

let configured = false;
function ensureConfigured() {
  if (configured) return;
  GoogleSignin.configure({
    ...(IOS_CLIENT_ID ? { iosClientId: IOS_CLIENT_ID } : {}),
    ...(WEB_CLIENT_ID ? { webClientId: WEB_CLIENT_ID } : {}),
  });
  configured = true;
}

/** Returns null on success or user cancel, otherwise an error message. */
export async function signInWithGoogle(): Promise<string | null> {
  if (Platform.OS !== "ios" && Platform.OS !== "android") {
    return "Google Sign-In is only available on mobile.";
  }
  if (!isGoogleConfigured) {
    return Platform.OS === "ios"
      ? "Google Sign-In isn't configured. Set EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID in app/.env and rebuild."
      : "Google Sign-In isn't configured. Set EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID in app/.env and rebuild.";
  }
  ensureConfigured();
  await GoogleSignin.hasPlayServices();
  const response = await GoogleSignin.signIn();
  if (response.type === "cancelled") return null;

  const idToken = response.data?.idToken;
  if (!idToken) return "No ID token from Google.";

  const { error } = await supabase.auth.signInWithIdToken({
    provider: "google",
    token: idToken,
  });
  return error ? error.message : null;
}

/** Clears the cached Google account so the picker shows on next sign-in. */
export async function signOutOfGoogle(): Promise<void> {
  if (!configured) return;
  await GoogleSignin.signOut().catch(() => {});
}
