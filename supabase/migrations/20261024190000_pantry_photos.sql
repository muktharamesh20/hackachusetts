-- Freely licensed Wikimedia Commons photos for the three demo (fictional) pantries.
-- They show real food-pantry scenes elsewhere; credits are shown on the pantry page.
alter table public.pantries add column if not exists image_credit text;
alter table public.pantries add column if not exists image_credit_url text;
update public.pantries set image_credit = 'Photo: Artaxerxes · CC BY 4.0 · Wikimedia Commons', image_credit_url = 'https://commons.wikimedia.org/wiki/File:Food_distribution_Orford_Congregational_Church_617_NH-10_Orford_NH_October_2025.jpg' where id = 'riverside';
update public.pantries set image_credit = 'Photo: 35mmMan · CC BY 2.0 · Wikimedia Commons', image_credit_url = 'https://commons.wikimedia.org/wiki/File:Loaves_and_Fishes_139_Charlotte_Street_Sydney,_Nova_Scotia_CANADA_September_2018.jpg' where id = 'maple-grove';
update public.pantries set image_credit = 'Photo: USDAgov · Public domain · Wikimedia Commons', image_credit_url = 'https://commons.wikimedia.org/wiki/File:Pennsylvania_Food_Bank_(20241017-USDA-FNS-CDP-1035).jpg' where id = 'lakeside';
-- Real pantries have no licensed photo: the app shows their actual location on a map instead.
update public.pantries set image_key = null where id like 'osm-%';
