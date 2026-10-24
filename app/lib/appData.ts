import { setCategories, Settings } from "./categories";
import { supabase } from "./supabase";

/** Load categories + settings from Supabase. Keeps the bundled defaults on failure. */
export async function hydrateAppData(): Promise<void> {
  const [cats, settings] = await Promise.all([
    supabase.from("app_categories").select("*").order("sort"),
    supabase.from("app_settings").select("key,value"),
  ]);
  if (cats.data?.length) {
    setCategories(
      cats.data.map((c: any) => ({
        key: c.key,
        label: c.label,
        art: c.art_key,
        icon: c.icon,
        tint: c.tint,
        onShelf: c.on_shelf,
        donorHint: c.donor_hint,
      })),
    );
  }
  const map = Object.fromEntries((settings.data ?? []).map((s: any) => [s.key, s.value]));
  if (typeof map.meals_per_dollar === "number") Settings.mealsPerDollar = map.meals_per_dollar;
  if (typeof map.level_low_below === "number") Settings.levelLowBelow = map.level_low_below;
  if (typeof map.level_okay_below === "number") Settings.levelOkayBelow = map.level_okay_below;
  if (typeof map.expiring_days === "number") Settings.expiringDays = map.expiring_days;
}
