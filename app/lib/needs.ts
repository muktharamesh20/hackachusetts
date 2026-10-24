import { categoryInfo, CategoryInfo, Settings, stockLevel } from "./categories";
import { CategoryStock, Pantry } from "./stash";

export type Need = {
  pantry: Pantry;
  category: CategoryInfo;
  units: number;
  target: number;
  short: number;
};

/** Low categories across pantries, most urgent (lowest % of goal) first. */
export function computeNeeds(pantries: Pantry[], stock: CategoryStock[]): Need[] {
  const byId = Object.fromEntries(pantries.map((p) => [p.id, p]));
  return stock
    .filter((s) => byId[s.pantry_id] && stockLevel(s.units, s.target_units) === "low")
    .map((s) => ({
      pantry: byId[s.pantry_id],
      category: categoryInfo(s.category),
      units: s.units,
      target: s.target_units,
      short: s.target_units - s.units,
    }))
    .sort((a, b) => a.units / a.target - b.units / b.target);
}

/** The category most pantries are short on (for the donor headline card). */
export function topShortage(needs: Need[]): { category: CategoryInfo; pantries: number } | null {
  const counts = new Map<string, { category: CategoryInfo; pantries: number }>();
  for (const n of needs) {
    const cur = counts.get(n.category.key) ?? { category: n.category, pantries: 0 };
    cur.pantries += 1;
    counts.set(n.category.key, cur);
  }
  return [...counts.values()].sort((a, b) => b.pantries - a.pantries)[0] ?? null;
}

/** Rough meals-per-dollar for the donation estimate (app_settings.meals_per_dollar). */
export const mealsPerDollar = () => Settings.mealsPerDollar;
