-- Seed org_id used across all accounts (matches test JWT claims)
DO $$
DECLARE
  org UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
  INSERT INTO accounts (org_id, name, chain, channel_type, address, latitude, longitude) VALUES
    (org, 'Total Wine & More - Midtown', 'Total Wine', 'bigbox',     '100 Peachtree St NW, Atlanta, GA 30303',  33.7540, -84.3858),
    (org, 'BevMo! - Sunset',            'BevMo',      'liquor',     '1220 Sunset Blvd, Los Angeles, CA 90026', 34.0771, -118.2608),
    (org, 'Corner Spirits - Brooklyn',   NULL,         'liquor',     '450 Court St, Brooklyn, NY 11231',        40.6751, -73.9971),
    (org, 'Costco Liquor - Burbank',     'Costco',     'bigbox',     '1051 W Burbank Blvd, Burbank, CA 91506',  34.1820, -118.3148),
    (org, 'QuickStop Deli & Spirits',    NULL,         'convenience','22 W 34th St, New York, NY 10001',        40.7484, -73.9856)
  ON CONFLICT DO NOTHING;
END $$;
