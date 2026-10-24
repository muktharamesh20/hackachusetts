-- Stash: multi-pantry, three-view app (pantry / neighbor / donor).
-- Builds on db/schema.sql (inventory_items, storage_locations, inventory_transactions).
-- Idempotent where practical so it can be re-run during development.

-- ---------------------------------------------------------------------------
-- Pantries
-- ---------------------------------------------------------------------------
create table if not exists public.pantries (
    id          text primary key,
    name        text not null,
    address     text not null,
    city        text not null,
    lat         double precision not null,
    lng         double precision not null,
    opens_at    time,                       -- structured hours (Stash pantries)
    closes_at   time,
    hours_note  text,                       -- free-form hours from public listings
    on_stash    boolean not null default false,  -- has a staff account + live stock
    website     text,
    phone       text,
    image_key   text,
    donate_url  text,
    created_at  timestamptz not null default now()
);

-- Demo pantries (fictional) that are on Stash with live stock.
insert into public.pantries (id, name, address, city, lat, lng, opens_at, closes_at, on_stash, image_key) values
    ('riverside',   'Riverside Community Pantry', '123 Maple St',      'Cambridge, MA 02139',  42.3613, -71.0960, '10:00', '16:00', true, 'pantry-riverside'),
    ('maple-grove', 'Maple Grove Pantry',         '48 Elm St',         'Somerville, MA 02144', 42.3954, -71.1215, '09:00', '15:00', true, 'pantry-maple-grove'),
    ('lakeside',    'Lakeside Food Hub',          '210 Brookline Ave', 'Boston, MA 02215',     42.3445, -71.1033, '11:00', '17:00', true, 'pantry-lakeside')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Existing tables: scope to a pantry, new category set, extra display fields
-- ---------------------------------------------------------------------------
alter table public.inventory_items
    add column if not exists pantry_id     text not null default 'riverside' references public.pantries (id) on delete cascade,
    add column if not exists image_key     text,
    add column if not exists tags          text[] not null default '{}',
    add column if not exists good_to_know  text[] not null default '{}';

alter table public.storage_locations
    add column if not exists pantry_id text not null default 'riverside' references public.pantries (id) on delete cascade;

alter table public.inventory_transactions
    add column if not exists pantry_id  text not null default 'riverside' references public.pantries (id) on delete cascade,
    add column if not exists item_name  text,
    add column if not exists source     text not null default 'robot';   -- robot | scan | manual

create index if not exists inventory_items_pantry_idx on public.inventory_items (pantry_id);
create index if not exists inventory_transactions_pantry_time_idx
    on public.inventory_transactions (pantry_id, "timestamp" desc);

-- Old category values -> new ones (protein, grains, fruit_veg, cooking_basics,
-- family_kids, baby, personal_care, household).
update public.inventory_items set category = case category
    when 'canned'    then 'protein'
    when 'condiment' then case when lower(name) like '%peanut butter%' then 'protein' else 'cooking_basics' end
    when 'dry_goods' then 'grains'
    when 'bakery'    then 'grains'
    when 'produce'   then 'fruit_veg'
    when 'frozen'    then 'fruit_veg'
    when 'dairy'     then 'family_kids'
    when 'beverage'  then 'family_kids'
    when 'snack'     then 'family_kids'
    when 'non_food'  then case when lower(name) ~ '(toothpaste|toothbrush|soap|shampoo|conditioner|deodorant|body wash)' then 'personal_care' else 'household' end
    when 'unknown'   then 'household'
    else category end;

update public.inventory_transactions t
    set item_name = coalesce(t.item_name, nullif(t.note, ''))
    where t.item_name is null;

-- ---------------------------------------------------------------------------
-- Category goals (what "Low / Okay / Plenty" is measured against)
-- ---------------------------------------------------------------------------
create table if not exists public.category_goals (
    pantry_id     text not null references public.pantries (id) on delete cascade,
    category      text not null,
    target_units  integer not null check (target_units > 0),
    primary key (pantry_id, category)
);

-- Default weekly goals for a pantry that joins Stash.
create or replace function public.seed_category_goals(p_pantry text)
returns void
language sql security definer set search_path = public
as $$
    insert into public.category_goals (pantry_id, category, target_units)
    select p_pantry, c.category, c.target
    from (values
        ('protein', 80), ('grains', 70), ('fruit_veg', 60), ('cooking_basics', 40),
        ('family_kids', 50), ('baby', 30), ('personal_care', 40), ('household', 40)
    ) as c(category, target)
    on conflict do nothing;
$$;
revoke execute on function public.seed_category_goals(text) from public, anon, authenticated;

select public.seed_category_goals(id) from public.pantries where on_stash;

-- ---------------------------------------------------------------------------
-- Profiles: default view + which pantry a staff member works at
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    id              uuid primary key references auth.users (id) on delete cascade,
    display_name    text,
    default_view    text not null default 'neighbor'
                    check (default_view in ('pantry', 'neighbor', 'donor')),
    pantry_id       text references public.pantries (id) on delete set null,
    saved_pantries  text[] not null default '{}',
    created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Rescue bags: food within ~1 day of going bad (free to neighbors until then)
-- ---------------------------------------------------------------------------
create table if not exists public.rescue_bags (
    id           uuid primary key default gen_random_uuid(),
    pantry_id    text not null references public.pantries (id) on delete cascade,
    title        text not null,
    description  text not null default '',
    item_count   integer not null default 1,
    weight_lbs   numeric(5, 1) not null default 1,
    price_cents  integer not null check (price_cents >= 0),
    pickup_by    timestamptz not null,
    status       text not null default 'available' check (status in ('available', 'claimed')),
    claimed_by   uuid references auth.users (id) on delete set null,
    created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Donations (mock checkout for the demo; no real payments)
-- ---------------------------------------------------------------------------
create table if not exists public.donations (
    id            bigint generated always as identity primary key,
    pantry_id     text not null references public.pantries (id) on delete cascade,
    user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
    amount_cents  integer not null check (amount_cents > 0),
    category      text,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------
-- Units on hand (non-expired) vs goal, per pantry + category.
create or replace view public.category_stock with (security_invoker = on) as
    select
        g.pantry_id,
        g.category,
        g.target_units,
        coalesce(sum(i.quantity) filter (
            where i.expiration_date is null or i.expiration_date >= current_date
        ), 0)::int as units
    from public.category_goals g
    left join public.inventory_items i
        on i.pantry_id = g.pantry_id and i.category = g.category
    group by g.pantry_id, g.category, g.target_units;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- Robot/seed scripts use the service-role key and bypass RLS.
-- NOTE: any signed-in user can set profiles.pantry_id, so "staff" is
-- self-declared. Fine for the demo; add an invite/approval flow before launch.
-- ---------------------------------------------------------------------------
alter table public.pantries        enable row level security;
alter table public.category_goals  enable row level security;
alter table public.profiles        enable row level security;
alter table public.rescue_bags     enable row level security;
alter table public.donations       enable row level security;

drop policy if exists dev_all_storage_locations      on public.storage_locations;
drop policy if exists dev_all_inventory_items        on public.inventory_items;
drop policy if exists dev_all_inventory_transactions on public.inventory_transactions;

create or replace function public.is_pantry_staff(p_pantry text)
returns boolean
language sql stable security definer set search_path = public
as $$
    select exists (
        select 1 from public.profiles
        where id = auth.uid() and pantry_id = p_pantry
    );
$$;

do $$
declare t text;
begin
    -- Public read for everything neighbors/donors browse.
    foreach t in array array['pantries', 'category_goals', 'inventory_items',
                             'storage_locations', 'inventory_transactions', 'rescue_bags']
    loop
        execute format('drop policy if exists read_all on public.%I', t);
        execute format('create policy read_all on public.%I for select using (true)', t);
    end loop;

    -- Staff write access, scoped to their pantry.
    foreach t in array array['inventory_items', 'storage_locations', 'inventory_transactions', 'category_goals']
    loop
        execute format('drop policy if exists staff_write on public.%I', t);
        execute format(
            'create policy staff_write on public.%I for all to authenticated '
            'using (public.is_pantry_staff(pantry_id)) with check (public.is_pantry_staff(pantry_id))', t);
    end loop;
end $$;

drop policy if exists own_profile on public.profiles;
create policy own_profile on public.profiles for all to authenticated
    using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists claim_rescue on public.rescue_bags;
create policy claim_rescue on public.rescue_bags for update to authenticated
    using (status = 'available') with check (status = 'claimed' and claimed_by = auth.uid());

drop policy if exists own_donations on public.donations;
create policy own_donations on public.donations for select to authenticated
    using (user_id = auth.uid());
drop policy if exists give on public.donations;
create policy give on public.donations for insert to authenticated
    with check (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Claim a pantry that isn't on Stash yet: marks it on Stash, sets default
-- goals, and makes the caller its staff. Demo-grade (no verification).
-- ---------------------------------------------------------------------------
create or replace function public.claim_pantry(p_pantry text)
returns void
language plpgsql security definer set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Sign in to claim a pantry';
    end if;
    update public.pantries set on_stash = true where id = p_pantry and not on_stash;
    if not found then
        raise exception 'This pantry is already on Stash or does not exist';
    end if;
    perform public.seed_category_goals(p_pantry);
    insert into public.profiles (id, default_view, pantry_id)
    values (auth.uid(), 'pantry', p_pantry)
    on conflict (id) do update set pantry_id = excluded.pantry_id, default_view = 'pantry';
end;
$$;
revoke execute on function public.claim_pantry(text) from public, anon;
grant execute on function public.claim_pantry(text) to authenticated;
