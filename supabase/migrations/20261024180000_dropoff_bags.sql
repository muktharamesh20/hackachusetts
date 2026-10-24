-- Group drop-off items into bags so a printed slip (QR = bag id) identifies one donor's box.

alter table public.dropoff_items
    add column if not exists batch_id   uuid,
    add column if not exists donor_name text;

-- Existing rows (pre-bags): each donor's pending items at a pantry become one bag.
update public.dropoff_items d
set batch_id = b.batch
from (
    select donor_id, pantry_id, gen_random_uuid() as batch
    from public.dropoff_items where batch_id is null
    group by donor_id, pantry_id
) b
where d.batch_id is null and d.donor_id = b.donor_id and d.pantry_id = b.pantry_id;

alter table public.dropoff_items alter column batch_id set not null;
alter table public.dropoff_items alter column batch_id set default gen_random_uuid();

create index if not exists dropoff_items_batch_idx on public.dropoff_items (batch_id);
