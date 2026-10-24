-- Demo data for Stash: stock for three pantries, recent activity, rescue bags.
-- Re-runnable: items upsert by id; activity/bags only seed once.

with catalog (key, name, category, kcal, allergens, tags, good_to_know, days, q_riv, q_maple, q_lake) as (
    values
    -- protein
    ('canned-tuna',    'Canned tuna',            'protein',        120, '{fish}'::text[],         '{Gluten free}'::text[],                 '{High in protein,Shelf stable}'::text[],     540,  8, 20, 12),
    ('peanut-butter',  'Peanut butter',          'protein',       2500, '{peanut}',               '{Vegan,Gluten free}',                   '{High in protein,Kid favorite}',             300,  4, 15,  8),
    ('canned-chicken', 'Canned chicken',         'protein',        360, '{}',                     '{Gluten free,No allergens}',            '{High in protein,Shelf stable}',             600,  3, 12,  7),
    ('canned-beans',   'Canned beans',           'protein',        330, '{}',                     '{Gluten free,Vegan,No allergens}',      '{Shelf stable,High in fiber,Great for meals}', 540, 6, 18, 10),
    ('lentils',        'Dried lentils',          'protein',       1600, '{}',                     '{Gluten free,Vegan,No allergens}',      '{High in fiber,Cooks in 20 min}',            700,  4, 10,  8),
    -- grains
    ('brown-rice',     'Brown rice',             'grains',        3400, '{}',                     '{Gluten free,Vegan}',                   '{Whole grain,Shelf stable}',                 365, 12,  8, 18),
    ('pasta',          'Whole-wheat pasta',      'grains',         800, '{wheat}',                '{Vegan}',                               '{Whole grain,Great for meals}',              365, 10,  5, 15),
    ('oats',           'Old-fashioned oats',     'grains',        1900, '{}',                     '{Vegan}',                               '{Whole grain,Quick breakfast}',              300,  8,  6, 12),
    ('cereal',         'Whole-grain cereal',     'grains',        1400, '{wheat}',                '{Low sugar}',                           '{Whole grain,Kid favorite}',                  25, 10,  6, 15),
    -- fruit & veg
    ('canned-veg',     'Canned green beans',     'fruit_veg',      70, '{}',                     '{Gluten free,Vegan,Low sodium}',        '{Shelf stable,Low sodium}',                  540, 20, 12,  6),
    ('canned-peaches', 'Canned peaches',         'fruit_veg',     220, '{}',                     '{Gluten free,Vegan}',                   '{Packed in juice,Shelf stable}',               5, 15, 10,  6),
    ('applesauce',     'Applesauce cups',        'fruit_veg',      50, '{}',                     '{Gluten free,Vegan,No allergens}',      '{Unsweetened,Pop-top lid}',                   40, 20, 12,  6),
    -- cooking basics
    ('olive-oil',      'Olive oil',              'cooking_basics', 8000, '{}',                    '{Vegan,Gluten free}',                   '{Cooking staple}',                           500,  6, 12,  3),
    ('flour',          'All-purpose flour',      'cooking_basics', 7400, '{wheat}',               '{Vegan}',                               '{Baking staple}',                            240,  8, 12,  4),
    ('spices',         'Spice packets',          'cooking_basics',    0, '{}',                    '{Vegan,Gluten free}',                   '{Makes meals tastier}',                      700,  8, 10,  3),
    -- family & kids
    ('uht-milk',       'Shelf-stable milk',      'family_kids',    600, '{milk}',                 '{Gluten free}',                         '{No fridge needed until opened}',              1, 10,  4,  6),
    ('juice',          '100% apple juice',       'family_kids',    440, '{}',                     '{Vegan,Gluten free}',                   '{No added sugar}',                             6, 10,  3,  6),
    ('granola-bars',   'Granola bars',           'family_kids',    190, '{wheat}',                '{}',                                    '{Lunchbox friendly}',                         12, 12,  5,  8),
    ('crackers',       'Crackers',               'family_kids',    700, '{wheat}',                '{Vegan}',                               '{Lunchbox friendly}',                         20,  8,  4,  6),
    ('pancake-mix',    'Pancake mix',            'family_kids',   1800, '{wheat,milk}',           '{}',                                    '{Just add water}',                           200,  5,  2,  4),
    -- baby
    ('formula',        'Infant formula',         'baby',          2600, '{milk}',                 '{Gluten free}',                         '{Check age range on label}',                 120,  5, 10,  2),
    ('baby-food',      'Baby food pouches',      'baby',            80, '{}',                     '{Gluten free,Vegan,No allergens}',      '{Stage 2,No added sugar}',                    10,  8,  8,  4),
    ('diapers',        'Diapers',                'baby',              0, '{}',                    '{}',                                    '{Size 3}',                                  null,  4,  8,  2),
    -- personal care
    ('toothpaste',     'Toothpaste',             'personal_care',     0, '{}',                    '{}',                                    '{Fluoride}',                                 null, 12,  4,  8),
    ('soap',           'Bar soap',               'personal_care',     0, '{}',                    '{}',                                    '{Unscented}',                                null, 14,  4,  8),
    ('shampoo',        'Shampoo',                'personal_care',     0, '{}',                    '{}',                                    '{Family size}',                              null, 10,  3,  8),
    -- household
    ('toilet-paper',   'Toilet paper',           'household',         0, '{}',                    '{}',                                    '{4-roll pack}',                              null,  4,  8, 12),
    ('detergent',      'Laundry detergent',      'household',         0, '{}',                    '{}',                                    '{HE compatible}',                            null,  2,  6, 10),
    ('feminine',       'Feminine pads',          'household',         0, '{}',                    '{}',                                    '{Regular absorbency}',                       null,  4,  8, 12)
),
stock as (
    select c.*, p.pantry_id, p.qty
    from catalog c
    cross join lateral (values ('riverside', c.q_riv), ('maple-grove', c.q_maple), ('lakeside', c.q_lake)) as p(pantry_id, qty)
)
insert into public.inventory_items
    (id, pantry_id, name, category, quantity, unit_calories, expiration_date,
     allergens, tags, good_to_know, image_key, received_at)
select
    'seed-' || pantry_id || '-' || key,
    pantry_id, name, category, qty, nullif(kcal, 0),
    case when days is null then null else current_date + days end,
    allergens, tags, good_to_know, 'item-' || key, now() - interval '2 days'
from stock
on conflict (id) do update set
    quantity = excluded.quantity,
    expiration_date = excluded.expiration_date,
    category = excluded.category,
    tags = excluded.tags,
    good_to_know = excluded.good_to_know,
    image_key = excluded.image_key;

-- Today's activity at Riverside (robot sorting, scans, hand-outs).
insert into public.inventory_transactions
    (item_id, pantry_id, item_name, transaction_type, quantity, source, note, "timestamp")
select v.item_id, 'riverside', v.item_name, v.ttype, v.qty, v.source, 'seed',
       date_trunc('day', now()) + v.at
from (values
    ('seed-riverside-canned-beans',  'Canned beans',  'intake',     6, 'robot', interval '10 hours 24 minutes'),
    ('seed-riverside-canned-beans',  'Canned beans',  'intake',     1, 'scan',  interval '10 hours 18 minutes'),
    ('seed-riverside-pasta',         'Pasta',         'intake',     8, 'robot', interval '9 hours 42 minutes'),
    ('seed-riverside-peanut-butter', 'Peanut butter', 'intake',     4, 'robot', interval '9 hours 41 minutes'),
    ('seed-riverside-granola-bars',  'Granola bars',  'distribute', 2, 'manual', interval '9 hours 15 minutes'),
    ('seed-riverside-diapers',       'Diapers',       'distribute', 1, 'manual', interval '9 hours 12 minutes'),
    ('seed-riverside-olive-oil',     'Olive oil',     'intake',     2, 'robot', interval '8 hours 54 minutes')
) as v(item_id, item_name, ttype, qty, source, at)
where not exists (select 1 from public.inventory_transactions where note = 'seed');

-- Rescue bags: about to expire, unclaimed by neighbors.
insert into public.rescue_bags (pantry_id, title, description, item_count, weight_lbs, price_cents, pickup_by)
select * from (values
    ('riverside',   'Breakfast rescue bag', 'Shelf-stable milk, cereal and juice that expire tomorrow.', 6, 4.5, 500, date_trunc('day', now()) + interval '19 hours'),
    ('maple-grove', 'Pantry staples bag',   'Canned fruit, crackers and granola bars near their date.',  8, 5.0, 700, date_trunc('day', now()) + interval '17 hours'),
    ('lakeside',    'Snack pack bag',       'Juice boxes and snack bars expiring soon.',                  5, 2.5, 400, date_trunc('day', now()) + interval '18 hours')
) as v(pantry_id, title, description, item_count, weight_lbs, price_cents, pickup_by)
where not exists (select 1 from public.rescue_bags);
