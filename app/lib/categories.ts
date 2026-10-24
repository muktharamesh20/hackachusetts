import { Colors } from "@/theme/colors";

/**
 * Categories and tunable numbers come from Supabase (app_categories, app_settings)
 * and are loaded once at startup by hydrateAppData() in lib/appData.ts. The values
 * below are fallbacks so the app still renders offline or before that finishes.
 */

export type CategoryKey = string;

export type CategoryInfo = {
  key: CategoryKey;
  label: string;
  /** Image key (bundled or in the 'art' bucket); falls back to `icon`. */
  art: string;
  /** MaterialCommunityIcons name used if the art is missing. */
  icon: string;
  tint: string;
  /** Shown in stock bars / goals (false for "unknown"). */
  onShelf: boolean;
  /** Donor-facing "especially needed" line. */
  donorHint: string;
};

const DEFAULTS: CategoryInfo[] = [
  { key: "protein", label: "Protein", art: "cat-protein", icon: "food-drumstick", tint: Colors.tomato, onShelf: true, donorHint: "" },
  { key: "grains", label: "Grains", art: "cat-grains", icon: "barley", tint: Colors.mustard, onShelf: true, donorHint: "" },
  { key: "fruit_veg", label: "Fruit & Veg", art: "cat-fruit-veg", icon: "food-apple", tint: Colors.olive, onShelf: true, donorHint: "" },
  { key: "cooking_basics", label: "Cooking Basics", art: "cat-cooking", icon: "shaker-outline", tint: Colors.mustard, onShelf: true, donorHint: "" },
  { key: "family_kids", label: "Family & Kids", art: "cat-family", icon: "cup", tint: Colors.sky, onShelf: true, donorHint: "" },
  { key: "drinks", label: "Water & Drinks", art: "cat-drinks", icon: "bottle-soda-classic-outline", tint: Colors.sky, onShelf: true, donorHint: "" },
  { key: "baby", label: "Baby", art: "cat-baby", icon: "baby-bottle-outline", tint: Colors.sky, onShelf: true, donorHint: "" },
  { key: "personal_care", label: "Personal Care", art: "cat-personal-care", icon: "toothbrush", tint: Colors.olive, onShelf: true, donorHint: "" },
  { key: "household", label: "Household", art: "cat-household", icon: "paper-roll", tint: Colors.tomato, onShelf: true, donorHint: "" },
  { key: "unknown", label: "Unsorted", art: "item-unknown", icon: "help-circle-outline", tint: Colors.textMuted, onShelf: false, donorHint: "" },
];

let ALL: CategoryInfo[] = DEFAULTS;
/** Shelf categories in display order (live array; contents replaced on hydrate). */
export const CATEGORIES: CategoryInfo[] = DEFAULTS.filter((c) => c.onShelf);
let BY_KEY: Record<string, CategoryInfo> = Object.fromEntries(ALL.map((c) => [c.key, c]));

export function setCategories(rows: CategoryInfo[]) {
  if (!rows.length) return;
  ALL = rows;
  BY_KEY = Object.fromEntries(rows.map((c) => [c.key, c]));
  CATEGORIES.splice(0, CATEGORIES.length, ...rows.filter((c) => c.onShelf));
}

export function categoryInfo(key: string): CategoryInfo {
  return BY_KEY[key] ?? { ...BY_KEY.unknown, key, label: key };
}

// --- tunable numbers (app_settings) ---

export const Settings = {
  mealsPerDollar: 3,
  levelLowBelow: 0.4,
  levelOkayBelow: 0.75,
  expiringDays: 7,
};

export type StockLevel = "low" | "okay" | "plenty";

export function stockLevel(units: number, target: number): StockLevel {
  const ratio = target > 0 ? units / target : 1;
  if (ratio < Settings.levelLowBelow) return "low";
  if (ratio < Settings.levelOkayBelow) return "okay";
  return "plenty";
}

export const LEVEL_STYLE: Record<StockLevel, { label: string; color: string; soft: string }> = {
  low: { label: "Low", color: Colors.tomato, soft: Colors.tomatoSoft },
  okay: { label: "Okay", color: Colors.mustard, soft: Colors.mustardSoft },
  plenty: { label: "Plenty", color: Colors.olive, soft: Colors.oliveSoft },
};
