-- Base PantrySort inventory schema (copied from db/schema.sql so migrations are self-contained).
-- PantrySort inventory schema for Supabase (Postgres).
-- Paste into the Supabase dashboard SQL Editor and run once.
-- Safe to re-run: uses IF NOT EXISTS / idempotent policies.

-- ---------------------------------------------------------------------------
-- Storage locations: where sorted items go (shelf, fridge, freezer, bin).
-- `accepts` is an array of category strings (matches FoodCategory enum values).
-- ---------------------------------------------------------------------------
create table if not exists public.storage_locations (
    id            text primary key,
    name          text not null,
    storage_type  text not null,            -- shelf | refrigerator | freezer | bin
    accepts       text[] not null default '{}'
);

-- ---------------------------------------------------------------------------
-- Inventory items currently on hand. Removing the last unit deletes the row;
-- the full lifecycle is preserved in inventory_transactions.
-- ---------------------------------------------------------------------------
create table if not exists public.inventory_items (
    id               text primary key,
    name             text not null,
    category         text not null,         -- FoodCategory enum value
    quantity         integer not null default 1 check (quantity >= 0),
    unit_calories    integer,               -- kcal per unit (nullable)
    weight_grams     double precision,
    expiration_date  date,
    allergens        text[] not null default '{}',
    barcode          text,
    location_id      text references public.storage_locations (id) on delete set null,
    received_at      timestamptz not null default now()
);

create index if not exists inventory_items_category_idx
    on public.inventory_items (category);
create index if not exists inventory_items_expiration_idx
    on public.inventory_items (expiration_date);
create index if not exists inventory_items_location_idx
    on public.inventory_items (location_id);

-- ---------------------------------------------------------------------------
-- Append-only lifecycle log: every intake / distribute / discard event.
-- ---------------------------------------------------------------------------
create table if not exists public.inventory_transactions (
    id                bigint generated always as identity primary key,
    item_id           text not null,
    transaction_type  text not null,        -- intake | distribute | discard
    quantity          integer not null check (quantity > 0),
    "timestamp"       timestamptz not null default now(),
    note              text not null default ''
);

create index if not exists inventory_transactions_item_idx
    on public.inventory_transactions (item_id);
create index if not exists inventory_transactions_type_idx
    on public.inventory_transactions (transaction_type);

-- ---------------------------------------------------------------------------
-- Convenience views for an app/dashboard.
-- ---------------------------------------------------------------------------

-- FEFO queue: fresh (non-expired) items, soonest expiry first; nulls last.
create or replace view public.distribution_queue as
    select *
    from public.inventory_items
    where expiration_date is null or expiration_date >= current_date
    order by expiration_date asc nulls last;

-- Nutrition totals per category.
create or replace view public.nutrition_by_category as
    select
        category,
        sum(quantity)                                         as total_units,
        sum(coalesce(unit_calories, 0) * quantity)            as total_calories
    from public.inventory_items
    group by category;

-- ---------------------------------------------------------------------------
-- Row Level Security.
-- Enabled below. The service_role key bypasses RLS (use it server-side for the
-- robot/seed scripts). For an app using the anon key, add explicit policies.
-- The permissive policies below let you start fast; TIGHTEN before production.
-- ---------------------------------------------------------------------------
alter table public.storage_locations     enable row level security;
alter table public.inventory_items        enable row level security;
alter table public.inventory_transactions enable row level security;

-- DEV-ONLY permissive policies (anon + authenticated can read/write).
-- Replace with auth-scoped policies when you add Supabase Auth.
do $$
begin
    if not exists (select 1 from pg_policies where tablename = 'storage_locations' and policyname = 'dev_all_storage_locations') then
        create policy dev_all_storage_locations on public.storage_locations
            for all using (true) with check (true);
    end if;
    if not exists (select 1 from pg_policies where tablename = 'inventory_items' and policyname = 'dev_all_inventory_items') then
        create policy dev_all_inventory_items on public.inventory_items
            for all using (true) with check (true);
    end if;
    if not exists (select 1 from pg_policies where tablename = 'inventory_transactions' and policyname = 'dev_all_inventory_transactions') then
        create policy dev_all_inventory_transactions on public.inventory_transactions
            for all using (true) with check (true);
    end if;
end $$;
