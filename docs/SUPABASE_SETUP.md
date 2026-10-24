# Supabase Setup

PantrySort can persist its inventory in Supabase (Postgres) instead of memory.
The code is backend-agnostic: callers use `InventoryStoreProtocol`, and
`make_store()` picks `InMemoryInventoryStore` or `SupabaseInventoryStore` based
on config. You can build an app directly against the same tables.

## 1. Create a project

1. Go to https://supabase.com and create a new project (~2 min to provision).
2. Open **Project Settings -> API** and copy:
   - **Project URL** -> `SUPABASE_URL` (e.g. `https://xxxxx.supabase.co`)
   - **anon public** key -> `SUPABASE_KEY` (for app/client use), and/or
   - **service_role** key -> `SUPABASE_SERVICE_ROLE_KEY` (server-side only;
     bypasses Row Level Security — never ship it to a browser/app client).

## 2. Create the tables

Open the Supabase dashboard **SQL Editor**, paste the contents of
[`db/schema.sql`](../db/schema.sql), and run it. It creates:

- `storage_locations` — where sorted items go (shelf, fridge, freezer, bin)
- `inventory_items` — items currently on hand
- `inventory_transactions` — append-only intake / distribute / discard log
- views `distribution_queue` (FEFO) and `nutrition_by_category`

> The schema enables Row Level Security with **dev-only permissive policies** so
> you can start fast. Tighten these before production (and add Supabase Auth).

## 3. Configure credentials

Put real values in `.env` (gitignored — never commit secrets). `.env.example`
is the committed template and should stay blank.

```
PANTRYSORT_INVENTORY_BACKEND=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

Leave `PANTRYSORT_INVENTORY_BACKEND=memory` to run without a connection.

## 4. Install the client + verify

```bash
pip install supabase          # or: pip install -e .
python scripts/supabase_demo.py
```

The demo seeds the default storage locations, takes in a few sample items,
and prints the FEFO distribution queue and a nutrition summary read back from
Supabase. If it prints rows, you're connected.

## 5. Use it from your app

Any app (web, mobile, scripts) can talk to the same tables:

- **Via supabase-js / supabase-py** against `inventory_items`,
  `storage_locations`, `inventory_transactions`.
- **Via the SQL views** `distribution_queue` and `nutrition_by_category` for
  ready-made reporting.
- **Row shape** is defined once in `src/pantrysort/inventory/serde.py` — match
  it in your app so both sides agree on column names/types.

## Table reference

| Table | Key columns |
|-------|-------------|
| `storage_locations` | `id`, `name`, `storage_type`, `accepts` (text[]) |
| `inventory_items` | `id`, `name`, `category`, `quantity`, `unit_calories`, `weight_grams`, `expiration_date`, `allergens` (text[]), `barcode`, `location_id`, `received_at` |
| `inventory_transactions` | `item_id`, `transaction_type` (intake/distribute/discard), `quantity`, `timestamp`, `note` |
