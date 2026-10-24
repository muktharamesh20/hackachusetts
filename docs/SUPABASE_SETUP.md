# Supabase Setup

PantrySort and the Stash mobile app share a pantry-scoped, lot-aware Supabase
Postgres backend. The latest migration chain is the production source of truth.

See the full integration contract in
[`.kiro/specs/pantry-app-integration/`](../.kiro/specs/pantry-app-integration/).

## 1. Create a project

1. Create a project at https://supabase.com.
2. Open **Project Settings → API** and copy the project URL and anon public key.
3. Keep the service-role key server-side only. Never put it in the Expo app or
   commit it to git.

## 2. Apply the current migrations

Apply the SQL files under [`supabase/migrations/`](../supabase/migrations/) in
filename order using the Supabase CLI or the dashboard SQL Editor. The current
migration chain creates and seeds the app-facing contract, including:

- `pantries`, `profiles`, and role/pantry authorization helpers.
- `inventory_items` for aggregate product rows.
- `inventory_lots` for per-expiration quantities and source provenance.
- `inventory_transactions` for the append-only lifecycle audit.
- `app_categories` and `catalog_items` for canonical product facts.
- Drop-off bags, resources, goals, settings, and related app data.
- FEFO/lot synchronization triggers and inventory RPCs.
- Row-level security policies.

The older [`db/schema.sql`](../db/schema.sql) three-table schema is a legacy
contract retained for reference. Do not use it for new robot/app integration
work unless the integration spec explicitly says so.

## 3. Configure the Python backend

The Python robot/server process can use the service-role key only when it runs
outside the mobile bundle and requires elevated server-side access. Prefer a
scoped authenticated operation/RPC when available.

In the repository root `.env`:

```text
PANTRYSORT_INVENTORY_BACKEND=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your-server-side-key
```

Leave `PANTRYSORT_INVENTORY_BACKEND=memory` for logic-only tests and demos.

The Python integration currently has a legacy adapter in
`src/pantrysort/inventory/supabase_store.py`. Its lot/pantry/category
reconciliation is tracked by the pantry-app-integration spec; do not add a
parallel schema.

## 4. Configure the mobile app

In `app/.env`, use only the anon key:

```text
EXPO_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

The mobile client is implemented in `app/lib/supabase.ts` and the typed app data
service is `app/lib/stash.ts`. The app uses SecureStore session persistence and
RLS-scoped authenticated requests.

## 5. Verify the backend

For the legacy Python demo path:

```bash
pip install -e .
python scripts/supabase_demo.py
```

For the mobile app:

```bash
cd app
npm install
npx tsc --noEmit
npx expo run:ios --device --configuration Release
```

Verify sign-in, role routing, a QR/barcode scan, lot-level expiry display, FEFO
handout, and activity history. A successful Release build must work without
Metro.

## Current table/service reference

| Area | Current source |
|---|---|
| Database schema | `supabase/migrations/` |
| Python robot entry point | `src/pantrysort/pipeline/sort_loop.py` |
| Python Supabase adapter | `src/pantrysort/inventory/supabase_store.py` |
| Mobile Supabase client | `app/lib/supabase.ts` |
| Mobile data service | `app/lib/stash.ts` |
| QR/catalog fixtures | `assets/qr/`, `assets/catalog.yaml`, `assets/barcodes/` |
| Integration requirements | `.kiro/specs/pantry-app-integration/` |
