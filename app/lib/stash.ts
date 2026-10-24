import { supabase } from "./supabase";
import type { ViewMode } from "@/theme/colors";

/** Typed queries for the Stash tables (see supabase/migrations/*_stash.sql). */

export type Pantry = {
  id: string;
  name: string;
  address: string;
  city: string;
  lat: number;
  lng: number;
  opens_at: string | null; // "10:00:00"; null for pantries not on Stash
  closes_at: string | null;
  hours_note: string | null; // free-form hours from public listings
  on_stash: boolean;
  website: string | null;
  phone: string | null;
  image_key: string | null;
  donate_url: string | null;
};

export type CategoryStock = {
  pantry_id: string;
  category: string;
  target_units: number;
  units: number;
};

export type Item = {
  id: string;
  pantry_id: string;
  name: string;
  category: string;
  quantity: number;
  unit_calories: number | null;
  expiration_date: string | null;
  allergens: string[];
  tags: string[];
  good_to_know: string[];
  image_key: string | null;
  barcode: string | null;
  received_at: string;
  /** Units grouped by expiry date (only when fetched with lots). */
  inventory_lots?: Lot[];
};

/** Units of an item that arrived together and share an expiration date. */
export type Lot = {
  id: number;
  item_id: string;
  quantity: number;
  expiration_date: string | null;
  lot_code: string | null;
  source: "robot" | "scan" | "manual" | "donor";
  received_at: string;
};

export type RecentLot = Lot & {
  item: Pick<Item, "id" | "name" | "category" | "image_key">;
};

export type CatalogItem = {
  id: string;
  sku: string | null;
  name: string;
  category: string;
  unit_calories: number | null;
  allergens: string[];
  image_key: string | null;
};

export type Activity = {
  id: number;
  item_id: string;
  item_name: string | null;
  note: string;
  transaction_type: "intake" | "distribute" | "discard";
  quantity: number;
  source: "robot" | "scan" | "manual" | "donor";
  timestamp: string;
};

export type RescueBag = {
  id: string;
  pantry_id: string;
  title: string;
  description: string;
  item_count: number;
  weight_lbs: number;
  price_cents: number;
  pickup_by: string;
  status: "available" | "claimed";
};

export type Profile = {
  id: string;
  display_name: string | null;
  default_view: ViewMode;
  pantry_id: string | null;
  saved_pantries: string[];
};

async function run<T>(query: PromiseLike<{ data: T | null; error: { message: string } | null }>): Promise<T> {
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return data as T;
}

// --- pantries ---

export const fetchPantries = () =>
  run<Pantry[]>(supabase.from("pantries").select("*").order("name"));

/** Pantries with a Stash account (live stock, goals, staff). */
export const fetchStashPantries = () =>
  run<Pantry[]>(supabase.from("pantries").select("*").eq("on_stash", true).order("name"));

/** Put a pantry on Stash and make the current user its staff. */
export async function claimPantry(pantryId: string): Promise<void> {
  await run(supabase.rpc("claim_pantry", { p_pantry: pantryId }));
}

export const fetchPantry = (id: string) =>
  run<Pantry>(supabase.from("pantries").select("*").eq("id", id).single());

export const fetchCategoryStock = (pantryId?: string) => {
  let q = supabase.from("category_stock").select("*");
  if (pantryId) q = q.eq("pantry_id", pantryId);
  return run<CategoryStock[]>(q);
};

// --- items ---

export const fetchItems = (pantryId: string) =>
  run<Item[]>(
    supabase
      .from("inventory_items")
      .select("*, inventory_lots(id,quantity,expiration_date)")
      .eq("pantry_id", pantryId)
      .gt("quantity", 0)
      .order("expiration_date", { ascending: true, nullsFirst: false }),
  );

export const fetchItem = (id: string) =>
  run<Item>(
    supabase
      .from("inventory_items")
      .select("*, inventory_lots(*)")
      .eq("id", id)
      .order("expiration_date", { referencedTable: "inventory_lots", ascending: true, nullsFirst: false })
      .single(),
  );

/** Newest arrivals at a pantry (each lot = one delivery/scan/robot batch). */
export const fetchRecentLots = (pantryId: string, limit = 10) =>
  run<RecentLot[]>(
    supabase
      .from("inventory_lots")
      .select("*, item:inventory_items(id,name,category,image_key)")
      .eq("pantry_id", pantryId)
      .order("received_at", { ascending: false })
      .limit(limit),
  );

/** Known product for a QR sku (the robot's labels) or exact name. */
export async function findCatalogItem(sku: string | null, name?: string): Promise<CatalogItem | null> {
  if (sku) {
    const rows = await run<CatalogItem[]>(supabase.from("catalog_items").select("*").eq("sku", sku).limit(1));
    if (rows[0]) return rows[0];
  }
  if (name) {
    const rows = await run<CatalogItem[]>(supabase.from("catalog_items").select("*").ilike("name", name).limit(1));
    if (rows[0]) return rows[0];
  }
  return null;
}

/** Units expiring within `days` (from the item's lots). */
export function unitsExpiringWithin(item: Item, days: number): number {
  return (item.inventory_lots ?? []).reduce((n, l) => {
    const d = daysUntil(l.expiration_date);
    return d !== null && d >= 0 && d <= days ? n + l.quantity : n;
  }, 0);
}

export async function findItemByBarcode(pantryId: string, barcode: string): Promise<Item | null> {
  const rows = await run<Item[]>(
    supabase.from("inventory_items").select("*").eq("pantry_id", pantryId).eq("barcode", barcode).limit(1),
  );
  return rows[0] ?? null;
}

/** Add stock from the Scan tab as a new lot (its own expiry), creating the item if needed. */
export async function logItem(input: {
  pantryId: string;
  name: string;
  category: string;
  quantity: number;
  expirationDate: string | null;
  barcode: string | null;
}): Promise<Item> {
  const existing = input.barcode ? await findItemByBarcode(input.pantryId, input.barcode) : null;
  // New items start at 0; the lot insert below sets quantity + next expiry via trigger.
  const item =
    existing ??
    (await run<Item>(
      supabase
        .from("inventory_items")
        .insert({
          id: `scan-${Date.now().toString(36)}`,
          pantry_id: input.pantryId,
          name: input.name,
          category: input.category,
          quantity: 0,
          barcode: input.barcode,
        })
        .select()
        .single(),
    ));
  await run(
    supabase.from("inventory_lots").insert({
      item_id: item.id,
      pantry_id: input.pantryId,
      quantity: input.quantity,
      expiration_date: input.expirationDate,
      source: "scan",
    }),
  );
  await run(
    supabase.from("inventory_transactions").insert({
      item_id: item.id,
      pantry_id: input.pantryId,
      item_name: item.name,
      transaction_type: "intake",
      quantity: input.quantity,
      source: "scan",
      note: item.name,
    }),
  );
  return item;
}

/** Record units leaving the pantry to a neighbor (soonest-expiring first). */
export async function handOut(item: Item, quantity = 1): Promise<void> {
  const remaining = item.quantity - quantity;
  if (remaining < 0) throw new Error(`Only ${item.quantity} on hand`);
  // The database takes units from the soonest-expiring lots (see on_item_write).
  await run(supabase.from("inventory_items").update({ quantity: remaining }).eq("id", item.id));
  await run(
    supabase.from("inventory_transactions").insert({
      item_id: item.id,
      pantry_id: item.pantry_id,
      item_name: item.name,
      transaction_type: "distribute",
      quantity,
      source: "manual",
      note: item.name,
    }),
  );
}

// --- activity ---

export const fetchActivity = (pantryId: string, limit = 30) =>
  run<Activity[]>(
    supabase
      .from("inventory_transactions")
      .select("id,item_id,item_name,note,transaction_type,quantity,source,timestamp")
      .eq("pantry_id", pantryId)
      .order("timestamp", { ascending: false })
      .limit(limit),
  );

// --- donors ---

export const fetchRescueBags = () =>
  run<RescueBag[]>(
    supabase
      .from("rescue_bags")
      .select("*")
      .eq("status", "available")
      .gte("pickup_by", new Date().toISOString())
      .order("pickup_by"),
  );

export async function claimRescueBag(id: string, userId: string): Promise<void> {
  await run(supabase.from("rescue_bags").update({ status: "claimed", claimed_by: userId }).eq("id", id));
}

export async function donate(pantryId: string, amountCents: number, category: string | null) {
  await run(supabase.from("donations").insert({ pantry_id: pantryId, amount_cents: amountCents, category }));
}

export const fetchMyDonations = () =>
  run<{ amount_cents: number; pantry_id: string; created_at: string }[]>(
    supabase.from("donations").select("amount_cents,pantry_id,created_at").order("created_at", { ascending: false }),
  );

// --- donor drop-offs (donors scan; staff confirm into stock) ---

export type Dropoff = {
  id: number;
  pantry_id: string;
  name: string;
  category: string;
  quantity: number;
  expiration_date: string | null;
  barcode: string | null;
  created_at: string;
};

export async function submitDropoff(
  pantryId: string,
  items: { name: string; category: string; quantity: number; expirationDate: string | null; barcode: string | null }[],
): Promise<void> {
  await run(
    supabase.from("dropoff_items").insert(
      items.map((i) => ({
        pantry_id: pantryId,
        name: i.name,
        category: i.category,
        quantity: i.quantity,
        expiration_date: i.expirationDate,
        barcode: i.barcode,
      })),
    ),
  );
}

export const fetchPendingDropoffs = (pantryId: string) =>
  run<Dropoff[]>(
    supabase
      .from("dropoff_items")
      .select("id,pantry_id,name,category,quantity,expiration_date,barcode,created_at")
      .eq("pantry_id", pantryId)
      .eq("status", "pending")
      .order("created_at", { ascending: false }),
  );

/** Staff: turn pending drop-offs into stock (each becomes a lot). */
export const acceptDropoffs = (ids: number[]) =>
  run<number>(supabase.rpc("accept_dropoffs", { p_ids: ids }));

// --- help resources ---

export type Resource = { id: string; title: string; body: string; icon: string; url: string; cta: string };

export const fetchResources = () =>
  run<Resource[]>(supabase.from("resources").select("*").order("sort"));

// --- profiles ---

export async function fetchProfile(userId: string): Promise<Profile | null> {
  const rows = await run<Profile[]>(supabase.from("profiles").select("*").eq("id", userId).limit(1));
  return rows[0] ?? null;
}

export const upsertProfile = (profile: Partial<Profile> & { id: string }) =>
  run<Profile>(supabase.from("profiles").upsert(profile).select().single());

// --- helpers ---

const hhmm = (t: string) => t.slice(0, 5);

function formatTime(t: string): string {
  const [h, m] = hhmm(t).split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  const hour = h % 12 || 12;
  return m ? `${hour}:${String(m).padStart(2, "0")}${suffix}` : `${hour}${suffix}`;
}

export function hoursLabel(p: Pantry): string {
  if (p.opens_at && p.closes_at) return `${formatTime(p.opens_at)} – ${formatTime(p.closes_at)}`;
  return p.hours_note ? p.hours_note.replace(/"/g, "") : "Call ahead for hours";
}

export function isOpenNow(p: Pantry, now = new Date()): boolean {
  if (!p.opens_at || !p.closes_at) return false;
  const cur = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return cur >= hhmm(p.opens_at) && cur < hhmm(p.closes_at);
}

export function distanceMiles(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 3958.8 * 2 * Math.asin(Math.sqrt(h));
}

export function daysUntil(dateIso: string | null): number | null {
  if (!dateIso) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const [y, m, d] = dateIso.slice(0, 10).split("-").map(Number);
  return Math.round((new Date(y, m - 1, d).getTime() - today.getTime()) / 86400000);
}

export function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

export const money = (cents: number) => `$${(cents / 100).toFixed(cents % 100 ? 2 : 0)}`;
