import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchProfile, Profile, upsertProfile } from "@/lib/stash";
import type { ViewMode } from "@/theme/colors";

type ProfileState = {
  profile: Profile | null;
  loading: boolean;
  /** View currently shown; starts at the profile's default and changes via the switcher. */
  mode: ViewMode;
  setMode: (mode: ViewMode) => void;
  /** Persist profile fields (onboarding, settings, saved pantries). */
  update: (fields: Partial<Omit<Profile, "id">>) => Promise<void>;
  toggleSaved: (pantryId: string) => Promise<void>;
  /** Re-read the profile (e.g. after a server-side change like claiming a pantry). */
  refresh: () => Promise<Profile | null>;
};

const ProfileContext = createContext<ProfileState | undefined>(undefined);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const userId = session?.user.id;
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<ViewMode>("neighbor");

  useEffect(() => {
    if (!userId) {
      setProfile(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchProfile(userId)
      .then((p) => {
        setProfile(p);
        if (p) setMode(p.default_view);
      })
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [userId]);

  const update = useCallback(
    async (fields: Partial<Omit<Profile, "id">>) => {
      if (!userId) return;
      const saved = await upsertProfile({ ...profile, ...fields, id: userId });
      setProfile(saved);
      if (!profile && saved) setMode(saved.default_view);
    },
    [userId, profile],
  );

  const toggleSaved = useCallback(
    async (pantryId: string) => {
      const current = profile?.saved_pantries ?? [];
      const next = current.includes(pantryId) ? current.filter((id) => id !== pantryId) : [...current, pantryId];
      await update({ saved_pantries: next });
    },
    [profile, update],
  );

  const refresh = useCallback(async () => {
    if (!userId) return null;
    const p = await fetchProfile(userId);
    setProfile(p);
    return p;
  }, [userId]);

  return (
    <ProfileContext.Provider value={{ profile, loading, mode, setMode, update, toggleSaved, refresh }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}

/** Pantry the staff views operate on. */
export function useStaffPantryId(): string {
  return useProfile().profile?.pantry_id ?? "riverside";
}
