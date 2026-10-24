-- Barcode scans fill in every product fact; expiry is read from the package or
-- estimated from typical shelf life and flagged for staff to double-check.

alter table public.catalog_items add column if not exists shelf_life_days integer;
alter table public.inventory_lots add column if not exists expiry_estimated boolean not null default false;
alter table public.dropoff_items add column if not exists expiry_estimated boolean not null default false;

-- Typical shelf life for the robot's products (assets/catalog.yaml).
update public.catalog_items set shelf_life_days = 30 where sku = 'APPLE';
update public.catalog_items set shelf_life_days = 540 where sku = 'BEANS-BLK-CAN';
update public.catalog_items set shelf_life_days = 270 where sku = 'CEREAL-BOX';
update public.catalog_items set shelf_life_days = 240 where sku = 'FLOUR-BAG';
update public.catalog_items set shelf_life_days = 120 where sku = 'FORMULA-CAN';
update public.catalog_items set shelf_life_days = 10 where sku = 'MILK-CARTON';
update public.catalog_items set shelf_life_days = 540 where sku = 'OLIVE-OIL';
update public.catalog_items set shelf_life_days = 300 where sku = 'PB-JAR';
update public.catalog_items set shelf_life_days = 200 where sku = 'PEAS-FROZEN-BAG';
update public.catalog_items set shelf_life_days = 730 where sku = 'RICE-BAG';
update public.catalog_items set shelf_life_days = 1825 where sku = 'SALT';
update public.catalog_items set shelf_life_days = 365 where sku = 'SPAGHETTI-BOX';
update public.catalog_items set shelf_life_days = 900 where sku = 'TUNA-CAN';

-- Everything else: typical shelf life by category.
update public.catalog_items set shelf_life_days = case category
    when 'protein' then 540 when 'grains' then 365 when 'fruit_veg' then 540
    when 'cooking_basics' then 500 when 'family_kids' then 180 when 'drinks' then 540
    when 'baby' then 180 else null end
where shelf_life_days is null;

-- New items copy all product facts from the catalog (calories + allergens too).
create or replace function public.enrich_item()
returns trigger
language plpgsql security definer set search_path = public
as $$
declare
    c public.catalog_items;
begin
    select * into c from public.catalog_items
    where (new.barcode is not null and sku = new.barcode) or lower(name) = lower(new.name)
    order by (sku = new.barcode) desc nulls last
    limit 1;
    if found then
        new.image_key := coalesce(new.image_key, c.image_key);
        new.unit_calories := coalesce(new.unit_calories, c.unit_calories);
        if new.allergens = '{}' then new.allergens := c.allergens; end if;
        if new.tags = '{}' then new.tags := c.tags; end if;
        if new.good_to_know = '{}' then new.good_to_know := c.good_to_know; end if;
    end if;
    if new.image_key is null and (new.category = 'unknown' or new.name ilike 'unknown%') then
        new.image_key := 'item-unknown';
    end if;
    return new;
end;
$$;

-- Accepting a drop-off keeps the "estimated" flag on the new lot.
create or replace function public.accept_dropoffs(p_ids bigint[])
returns integer
language plpgsql security definer set search_path = public
as $$
declare
    d public.dropoff_items;
    v_item text;
    accepted integer := 0;
begin
    for d in
        select * from public.dropoff_items
        where id = any (p_ids) and status = 'pending'
        for update
    loop
        if not public.is_pantry_staff(d.pantry_id) then
            raise exception 'Only staff at this pantry can accept drop-offs';
        end if;

        select id into v_item from public.inventory_items
        where pantry_id = d.pantry_id
          and ((d.barcode is not null and barcode = d.barcode) or lower(name) = lower(d.name))
        order by (barcode = d.barcode) desc nulls last
        limit 1;

        if v_item is null then
            v_item := 'donor-' || d.id;
            insert into public.inventory_items (id, pantry_id, name, category, quantity, barcode)
            values (v_item, d.pantry_id, d.name, d.category, 0, d.barcode);
        end if;

        insert into public.inventory_lots (item_id, pantry_id, quantity, expiration_date, source, expiry_estimated)
        values (v_item, d.pantry_id, d.quantity, d.expiration_date, 'donor', d.expiry_estimated);

        insert into public.inventory_transactions
            (item_id, pantry_id, item_name, transaction_type, quantity, source, note)
        values (v_item, d.pantry_id, d.name, 'intake', d.quantity, 'donor', d.name);

        update public.dropoff_items
        set status = 'accepted', reviewed_at = now(), reviewed_by = auth.uid()
        where id = d.id;
        accepted := accepted + 1;
    end loop;
    return accepted;
end;
$$;
