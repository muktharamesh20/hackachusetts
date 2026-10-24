-- Donor drop-offs: donors scan what they bring; pantry staff confirm it into stock.

create table if not exists public.dropoff_items (
    id               bigint generated always as identity primary key,
    pantry_id        text not null references public.pantries (id) on delete cascade,
    donor_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
    name             text not null,
    category         text not null references public.app_categories (key),
    quantity         integer not null check (quantity > 0),
    expiration_date  date,
    barcode          text,
    status           text not null default 'pending' check (status in ('pending', 'accepted', 'rejected')),
    created_at       timestamptz not null default now(),
    reviewed_at      timestamptz,
    reviewed_by      uuid references auth.users (id) on delete set null
);
create index if not exists dropoff_items_pantry_pending_idx
    on public.dropoff_items (pantry_id, status, created_at desc);

alter table public.dropoff_items enable row level security;

drop policy if exists donor_insert on public.dropoff_items;
create policy donor_insert on public.dropoff_items for insert to authenticated
    with check (donor_id = auth.uid() and status = 'pending');
drop policy if exists donor_read_own on public.dropoff_items;
create policy donor_read_own on public.dropoff_items for select to authenticated
    using (donor_id = auth.uid() or public.is_pantry_staff(pantry_id));
drop policy if exists staff_review on public.dropoff_items;
create policy staff_review on public.dropoff_items for update to authenticated
    using (public.is_pantry_staff(pantry_id)) with check (public.is_pantry_staff(pantry_id));

-- Staff accept pending drop-offs: each becomes a lot (own expiry) on a matching
-- item (same barcode or name at that pantry), creating the item if needed.
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

        insert into public.inventory_lots (item_id, pantry_id, quantity, expiration_date, source)
        values (v_item, d.pantry_id, d.quantity, d.expiration_date, 'donor');

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
revoke execute on function public.accept_dropoffs(bigint[]) from public, anon;
grant execute on function public.accept_dropoffs(bigint[]) to authenticated;
