import { supabase } from "./supabase";

/** Mirrors the pantrysort inventory_items table (see db/schema.sql at repo root). */
export type InventoryItem = {
  id: string;
  name: string;
  category: string;
  quantity: number;
  unit_calories: number | null;
  weight_grams: number | null;
  expiration_date: string | null; // ISO date
  allergens: string[] | null;
  barcode: string | null;
  location_id: string | null;
  received_at: string;
};

export type StorageLocation = {
  id: string;
  name: string;
  storage_type: string;
  accepts: string[];
};

export async function fetchItems(): Promise<InventoryItem[]> {
  const { data, error } = await supabase
    .from("inventory_items")
    .select("*")
    .order("received_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as InventoryItem[];
}

/** FEFO queue via the distribution_queue view defined in db/schema.sql. */
export async function fetchDistributionQueue(): Promise<InventoryItem[]> {
  const { data, error } = await supabase.from("distribution_queue").select("*");
  if (error) throw error;
  return (data ?? []) as InventoryItem[];
}

export async function fetchLocations(): Promise<StorageLocation[]> {
  const { data, error } = await supabase.from("storage_locations").select("*");
  if (error) throw error;
  return (data ?? []) as StorageLocation[];
}

export function daysUntil(dateIso: string | null): number | null {
  if (!dateIso) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(dateIso);
  exp.setHours(0, 0, 0, 0);
  return Math.round((exp.getTime() - today.getTime()) / 86400000);
}
