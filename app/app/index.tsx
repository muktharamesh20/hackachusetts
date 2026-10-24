import { Redirect } from "expo-router";
import { useAuth } from "@/context/AuthContext";
import { useProfile } from "@/context/ProfileContext";

/** Entry route: send people to sign-in, onboarding, or their current view. */
export default function Index() {
  const { session, loading: authLoading } = useAuth();
  const { profile, mode, loading: profileLoading } = useProfile();
  if (authLoading || (session && profileLoading)) return null;
  if (!session) return <Redirect href="/(auth)/sign-in" />;
  if (!profile) return <Redirect href="/onboarding" />;
  return <Redirect href={`/${mode}`} />;
}
