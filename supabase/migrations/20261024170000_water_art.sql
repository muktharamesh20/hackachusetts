-- Pictures for the Water & Drinks items (cat-drinks / item-bottled-water in the art bucket).
update public.catalog_items set image_key = 'item-bottled-water' where id = 'bottled-water';
update public.catalog_items set image_key = 'cat-drinks' where id in ('sparkling-water', 'sports-drink');
update public.inventory_items set image_key = 'item-bottled-water' where lower(name) = 'bottled water (24-pack)';
update public.inventory_items set image_key = 'cat-drinks' where lower(name) in ('sparkling water', 'electrolyte drink');
