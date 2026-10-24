-- Water & Drinks category, and remembering barcode -> product names from scans.

-- ---------------------------------------------------------------------------
-- Water & Drinks (after Family & Kids)
-- ---------------------------------------------------------------------------
update public.app_categories set sort = sort + 1 where sort >= 6;

insert into public.app_categories (key, label, tint, art_key, icon, sort, on_shelf, donor_hint) values
    ('drinks', 'Water & Drinks', '#4F8FAE', 'cat-drinks', 'bottle-soda-classic-outline', 6, true,
     'Bottled water is always useful, especially in summer and for families without safe tap water.')
on conflict (key) do update set
    label = excluded.label, tint = excluded.tint, art_key = excluded.art_key, icon = excluded.icon,
    sort = excluded.sort, on_shelf = excluded.on_shelf, donor_hint = excluded.donor_hint;

-- New pantries get a drinks goal too.
create or replace function public.seed_category_goals(p_pantry text)
returns void
language sql security definer set search_path = public
as $$
    insert into public.category_goals (pantry_id, category, target_units)
    select p_pantry, c.category, c.target
    from (values
        ('protein', 80), ('grains', 70), ('fruit_veg', 60), ('cooking_basics', 40),
        ('family_kids', 50), ('drinks', 40), ('baby', 30), ('personal_care', 40), ('household', 40)
    ) as c(category, target)
    on conflict do nothing;
$$;
select public.seed_category_goals(id) from public.pantries where on_stash;

insert into public.catalog_items (id, name, category, unit_calories, tags, good_to_know) values
    ('bottled-water',   'Bottled water (24-pack)', 'drinks', 0,   '{Gluten free,Vegan,No allergens}', '{Shelf stable,No fridge needed}'),
    ('sparkling-water', 'Sparkling water',         'drinks', 0,   '{Gluten free,Vegan,No allergens}', '{Shelf stable}'),
    ('sports-drink',    'Electrolyte drink',       'drinks', 140, '{Gluten free,Vegan}',              '{Good for hot days}')
on conflict (id) do nothing;

-- Demo stock so the new bar isn't empty (lots + pictures come from triggers).
insert into public.inventory_items (id, pantry_id, name, category, quantity, expiration_date, tags, good_to_know)
values
    ('seed-riverside-water',   'riverside',   'Bottled water (24-pack)', 'drinks', 18, current_date + 540, '{Gluten free,Vegan,No allergens}', '{Shelf stable,No fridge needed}'),
    ('seed-maple-grove-water', 'maple-grove', 'Bottled water (24-pack)', 'drinks', 6,  current_date + 480, '{Gluten free,Vegan,No allergens}', '{Shelf stable,No fridge needed}'),
    ('seed-lakeside-water',    'lakeside',    'Bottled water (24-pack)', 'drinks', 34, current_date + 600, '{Gluten free,Vegan,No allergens}', '{Shelf stable,No fridge needed}'),
    ('seed-lakeside-sparkling','lakeside',    'Sparkling water',         'drinks', 8,  current_date + 300, '{Gluten free,Vegan,No allergens}', '{Shelf stable}')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Learned codes: the first person to name an unknown barcode teaches the catalog.
-- Existing codes are never overwritten (so nobody can rename a known product).
-- ---------------------------------------------------------------------------
create or replace function public.remember_code(p_code text, p_name text, p_category text)
returns void
language plpgsql security definer set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Sign in to save product codes';
    end if;
    if coalesce(trim(p_code), '') = '' or coalesce(trim(p_name), '') = '' then
        return;
    end if;
    if not exists (select 1 from public.app_categories where key = p_category) then
        p_category := 'unknown';
    end if;
    insert into public.catalog_items (id, sku, name, category)
    values ('code-' || trim(p_code), trim(p_code), trim(p_name), p_category)
    on conflict do nothing;
end;
$$;
revoke execute on function public.remember_code(text, text, text) from public, anon;
grant execute on function public.remember_code(text, text, text) to authenticated;

-- Backfill: codes already on inventory items become catalog entries.
insert into public.catalog_items (id, sku, name, category, image_key)
select distinct on (barcode) 'code-' || barcode, barcode, name, category, image_key
from public.inventory_items
where barcode is not null and barcode <> ''
order by barcode, received_at
on conflict do nothing;
