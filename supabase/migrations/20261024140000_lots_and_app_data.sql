-- Per-unit expiry (lots), product catalog, and app config moved into the database.

-- ---------------------------------------------------------------------------
-- Lots: units of an item that arrived together and share an expiration date.
-- inventory_items.quantity / expiration_date are kept in sync from lots:
--   quantity        = sum of lot quantities
--   expiration_date = soonest lot date ("next to expire")
-- Writers that only touch inventory_items (the robot's Python store) keep
-- working: inserting an item creates a lot; lowering quantity consumes lots
-- soonest-expiring first; raising it adds a lot.
-- ---------------------------------------------------------------------------
create table if not exists public.inventory_lots (
    id               bigint generated always as identity primary key,
    item_id          text not null references public.inventory_items (id) on delete cascade,
    pantry_id        text not null references public.pantries (id) on delete cascade,
    quantity         integer not null check (quantity > 0),
    expiration_date  date,
    lot_code         text,
    source           text not null default 'robot',   -- robot | scan | manual
    received_at      timestamptz not null default now()
);
create index if not exists inventory_lots_item_idx
    on public.inventory_lots (item_id, expiration_date asc nulls last);
create index if not exists inventory_lots_recent_idx
    on public.inventory_lots (pantry_id, received_at desc);

create or replace function public.sync_item_from_lots(p_item text)
returns void
language sql security definer set search_path = public
as $$
    update public.inventory_items i
    set quantity = l.qty, expiration_date = l.soonest
    from (
        select coalesce(sum(quantity), 0)::int as qty, min(expiration_date) as soonest
        from public.inventory_lots where item_id = p_item
    ) l
    where i.id = p_item;
$$;

create or replace function public.on_lot_change()
returns trigger
language plpgsql security definer set search_path = public
as $$
begin
    perform public.sync_item_from_lots(coalesce(new.item_id, old.item_id));
    return null;
end;
$$;

drop trigger if exists lots_sync on public.inventory_lots;
create trigger lots_sync after insert or update or delete on public.inventory_lots
    for each row execute function public.on_lot_change();

-- Direct writes to inventory_items (depth 1 only; nested syncs are ignored).
create or replace function public.on_item_write()
returns trigger
language plpgsql security definer set search_path = public
as $$
declare
    remaining int;
    lot record;
begin
    if pg_trigger_depth() > 1 then
        return null;
    end if;

    if tg_op = 'INSERT' then
        if new.quantity > 0 and not exists (select 1 from public.inventory_lots where item_id = new.id) then
            insert into public.inventory_lots (item_id, pantry_id, quantity, expiration_date, source, received_at)
            values (new.id, new.pantry_id, new.quantity, new.expiration_date, 'robot', new.received_at);
        end if;
    elsif new.quantity < old.quantity then
        remaining := old.quantity - new.quantity;
        for lot in
            select id, quantity from public.inventory_lots
            where item_id = new.id
            order by expiration_date asc nulls last, id
        loop
            exit when remaining <= 0;
            if lot.quantity <= remaining then
                delete from public.inventory_lots where id = lot.id;
                remaining := remaining - lot.quantity;
            else
                update public.inventory_lots set quantity = quantity - remaining where id = lot.id;
                remaining := 0;
            end if;
        end loop;
    elsif new.quantity > old.quantity then
        insert into public.inventory_lots (item_id, pantry_id, quantity, expiration_date, source)
        values (new.id, new.pantry_id, new.quantity - old.quantity, new.expiration_date, 'manual');
    end if;
    return null;
end;
$$;

drop trigger if exists items_to_lots on public.inventory_items;
create trigger items_to_lots after insert or update of quantity on public.inventory_items
    for each row execute function public.on_item_write();

-- Backfill: split existing stock into a few lots with different dates so the
-- demo shows real per-unit expiry (soonest date stays the item's current one).
insert into public.inventory_lots (item_id, pantry_id, quantity, expiration_date, lot_code, source, received_at)
select i.id, i.pantry_id, part.qty,
       case when i.expiration_date is null then null
            else i.expiration_date + part.days end,
       'L' || part.n, part.source,
       now() - part.age
from public.inventory_items i
cross join lateral (
    select * from (values
        (1, greatest(1, i.quantity / 3), 0,
            interval '4 days', 'robot'),
        (2, i.quantity / 3,
            case when i.expiration_date - current_date <= 14 then 5 else 30 end,
            interval '1 day 3 hours', 'robot'),
        (3, i.quantity - greatest(1, i.quantity / 3) - i.quantity / 3,
            case when i.expiration_date - current_date <= 14 then 12 else 90 end,
            (abs(hashtext(i.id)) % 300) * interval '1 minute', 'scan')
    ) as v(n, qty, days, age, source)
) part
where i.quantity > 0
  and part.qty > 0
  and not exists (select 1 from public.inventory_lots l where l.item_id = i.id);

alter table public.inventory_lots enable row level security;
drop policy if exists read_all on public.inventory_lots;
create policy read_all on public.inventory_lots for select using (true);
drop policy if exists staff_write on public.inventory_lots;
create policy staff_write on public.inventory_lots for all to authenticated
    using (public.is_pantry_staff(pantry_id)) with check (public.is_pantry_staff(pantry_id));

-- ---------------------------------------------------------------------------
-- Categories (labels, colors, art) + the "unknown" bucket for unidentified items
-- ---------------------------------------------------------------------------
create table if not exists public.app_categories (
    key         text primary key,
    label       text not null,
    tint        text not null,          -- hex color
    art_key     text not null,          -- image name (bundled or in the 'art' bucket)
    icon        text not null,          -- MaterialCommunityIcons fallback
    sort        integer not null,
    on_shelf    boolean not null default true,   -- shown in stock bars / goals
    donor_hint  text not null default ''
);

insert into public.app_categories (key, label, tint, art_key, icon, sort, on_shelf, donor_hint) values
    ('protein',        'Protein',        '#E2553D', 'cat-protein',       'food-drumstick',      1, true, 'Canned tuna, peanut butter, beans and lentils are especially needed.'),
    ('grains',         'Grains',         '#E8B341', 'cat-grains',        'barley',              2, true, 'Rice, oats and whole-wheat pasta go fast.'),
    ('fruit_veg',      'Fruit & Veg',    '#6E9A3A', 'cat-fruit-veg',     'food-apple',          3, true, 'Canned fruit in juice and low-sodium veggies are great.'),
    ('cooking_basics', 'Cooking Basics', '#E8B341', 'cat-cooking',       'shaker-outline',      4, true, 'Oil, flour and spices help families cook.'),
    ('family_kids',    'Family & Kids',  '#4F8FAE', 'cat-family',        'cup',                 5, true, 'Shelf-stable milk, juice and granola bars are favorites.'),
    ('baby',           'Baby',           '#4F8FAE', 'cat-baby',          'baby-bottle-outline', 6, true, 'Formula, baby food and diapers are always needed.'),
    ('personal_care',  'Personal Care',  '#6E9A3A', 'cat-personal-care', 'toothbrush',          7, true, 'Toothpaste, soap and shampoo aren''t covered by SNAP.'),
    ('household',      'Household',      '#E2553D', 'cat-household',     'paper-roll',          8, true, 'Toilet paper, detergent and feminine products aren''t covered by SNAP.'),
    ('unknown',        'Unsorted',       '#8C7565', 'item-unknown',      'help-circle-outline', 9, false, '')
on conflict (key) do update set
    label = excluded.label, tint = excluded.tint, art_key = excluded.art_key, icon = excluded.icon,
    sort = excluded.sort, on_shelf = excluded.on_shelf, donor_hint = excluded.donor_hint;

-- ---------------------------------------------------------------------------
-- Product catalog: known products (our demo items + the robot's QR skus).
-- New inventory rows get their picture / tags / notes from here.
-- ---------------------------------------------------------------------------
create table if not exists public.catalog_items (
    id            text primary key,
    sku           text unique,             -- QR label sku (robot), if any
    name          text not null,
    category      text not null references public.app_categories (key),
    unit_calories integer,
    allergens     text[] not null default '{}',
    tags          text[] not null default '{}',
    good_to_know  text[] not null default '{}',
    image_key     text
);

insert into public.catalog_items (id, name, category, unit_calories, allergens, tags, good_to_know, image_key)
select distinct on (i.image_key)
       substr(i.image_key, 6), i.name, i.category, i.unit_calories, i.allergens, i.tags, i.good_to_know, i.image_key
from public.inventory_items i
where i.id like 'seed-riverside-%' and i.image_key like 'item-%'
order by i.image_key
on conflict (id) do nothing;

insert into public.catalog_items (id, sku, name, category, unit_calories, allergens, image_key) values
    ('qr-beans-blk-can',   'BEANS-BLK-CAN',   'Black beans (can)',   'protein',        330,  '{}',      'item-canned-beans'),
    ('qr-tuna-can',        'TUNA-CAN',        'Tuna (can)',          'protein',        200,  '{fish}',  'item-canned-tuna'),
    ('qr-spaghetti-box',   'SPAGHETTI-BOX',   'Spaghetti (box)',     'grains',         800,  '{wheat}', 'item-pasta'),
    ('qr-cereal-box',      'CEREAL-BOX',      'Cereal (box)',        'grains',         1600, '{wheat}', 'item-cereal'),
    ('qr-rice-bag',        'RICE-BAG',        'Rice (bag)',          'grains',         3400, '{}',      'item-brown-rice'),
    ('qr-formula-can',     'FORMULA-CAN',     'Infant formula (can)','baby',           2600, '{milk}',  'item-formula'),
    ('qr-olive-oil',       'OLIVE-OIL',       'Olive oil (bottle)',  'cooking_basics', 8000, '{}',      'item-olive-oil'),
    ('qr-salt',            'SALT',            'Salt (shaker)',       'cooking_basics', null, '{}',      'item-spices'),
    ('qr-flour-bag',       'FLOUR-BAG',       'Flour (bag)',         'cooking_basics', 7400, '{wheat}', 'item-flour'),
    ('qr-pb-jar',          'PB-JAR',          'Peanut butter (jar)', 'protein',        2500, '{peanut}','item-peanut-butter'),
    ('qr-apple',           'APPLE',           'Apple',               'fruit_veg',      95,   '{}',      null),
    ('qr-milk-carton',     'MILK-CARTON',     'Milk (carton)',       'family_kids',    600,  '{milk}',  'item-uht-milk'),
    ('qr-peas-frozen-bag', 'PEAS-FROZEN-BAG', 'Frozen peas (bag)',   'fruit_veg',      350,  '{}',      'item-canned-veg'),
    ('qr-toothpaste',      'TOOTHPASTE',      'Toothpaste',          'personal_care',  null, '{}',      'item-toothpaste'),
    ('qr-soap-bar',        'SOAP-BAR',        'Bar soap',            'personal_care',  null, '{}',      'item-soap'),
    ('qr-toilet-paper',    'TOILET-PAPER',    'Toilet paper (roll)', 'household',      null, '{}',      'item-toilet-paper'),
    ('qr-shampoo',         'SHAMPOO',         'Shampoo',             'personal_care',  null, '{}',      'item-shampoo')
on conflict (id) do update set
    sku = excluded.sku, name = excluded.name, category = excluded.category,
    unit_calories = excluded.unit_calories, allergens = excluded.allergens, image_key = excluded.image_key;

alter table public.app_categories enable row level security;
alter table public.catalog_items  enable row level security;
drop policy if exists read_all on public.app_categories;
create policy read_all on public.app_categories for select using (true);
drop policy if exists read_all on public.catalog_items;
create policy read_all on public.catalog_items for select using (true);

-- Fill picture / tags / notes for new items from the catalog (by QR sku or name);
-- anything we can't identify gets the "unknown" picture.
create or replace function public.enrich_item()
returns trigger
language plpgsql security definer set search_path = public
as $$
declare
    c public.catalog_items;
begin
    if new.image_key is null then
        select * into c from public.catalog_items
        where (new.barcode is not null and sku = new.barcode) or lower(name) = lower(new.name)
        order by (sku = new.barcode) desc nulls last
        limit 1;
        if found then
            new.image_key := c.image_key;
            if new.tags = '{}' then new.tags := c.tags; end if;
            if new.good_to_know = '{}' then new.good_to_know := c.good_to_know; end if;
        end if;
        if new.image_key is null and (new.category = 'unknown' or new.name ilike 'unknown%') then
            new.image_key := 'item-unknown';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists items_enrich on public.inventory_items;
create trigger items_enrich before insert on public.inventory_items
    for each row execute function public.enrich_item();

-- ---------------------------------------------------------------------------
-- Help resources shown to neighbors (Massachusetts)
-- ---------------------------------------------------------------------------
create table if not exists public.resources (
    id      text primary key,
    title   text not null,
    body    text not null,
    icon    text not null,
    url     text not null,
    cta     text not null,
    region  text not null default 'MA',
    sort    integer not null default 0
);

insert into public.resources (id, title, body, icon, url, cta, sort) values
    ('foodsource', 'FoodSource Hotline',
     'Project Bread''s free, confidential hotline helps you find food and apply for SNAP. Many languages.',
     'phone-outline', 'tel:18006458333', 'Call 1-800-645-8333', 1),
    ('snap', 'SNAP benefits',
     'Monthly money for groceries. Apply or check your case with DTA Connect.',
     'card-account-details-outline', 'https://dtaconnect.eohhs.mass.gov', 'Open DTA Connect', 2),
    ('wic', 'WIC',
     'Healthy food, formula and support for pregnant people, new parents and kids under 5.',
     'baby-face-outline', 'https://www.mass.gov/wic', 'Learn about WIC', 3),
    ('211', 'Mass 211',
     'Free 24/7 help finding housing, utilities, and other local services.',
     'lifebuoy', 'tel:211', 'Dial 211', 4)
on conflict (id) do update set
    title = excluded.title, body = excluded.body, icon = excluded.icon,
    url = excluded.url, cta = excluded.cta, sort = excluded.sort;

alter table public.resources enable row level security;
drop policy if exists read_all on public.resources;
create policy read_all on public.resources for select using (true);

-- ---------------------------------------------------------------------------
-- Tunable numbers
-- ---------------------------------------------------------------------------
create table if not exists public.app_settings (
    key    text primary key,
    value  jsonb not null,
    note   text not null default ''
);

insert into public.app_settings (key, value, note) values
    ('meals_per_dollar', '3',    'Rough meals funded per donated dollar (estimate shown to donors).'),
    ('level_low_below',  '0.4',  'Category is "Low" below this share of its goal.'),
    ('level_okay_below', '0.75', 'Category is "Okay" below this share of its goal; "Plenty" otherwise.'),
    ('expiring_days',    '7',    'Items within this many days count as "expiring soon".')
on conflict (key) do nothing;

alter table public.app_settings enable row level security;
drop policy if exists read_all on public.app_settings;
create policy read_all on public.app_settings for select using (true);

-- ---------------------------------------------------------------------------
-- Public bucket for app illustrations (anything not bundled loads from here)
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('art', 'art', true)
on conflict (id) do update set public = true;
