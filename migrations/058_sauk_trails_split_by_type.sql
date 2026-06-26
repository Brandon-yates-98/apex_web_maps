-- ============================================================
-- Devil's Lake Mapping Project — split Sauk County trails into per-type layers
-- Apply via Supabase MCP TOGETHER with merging feature/sauk-trails-format to main
-- and re-running scripts/import_sauk_trails.py. (The DB is shared with the live
-- site, so applying this before the new frontend ships would leave main looking
-- for the removed `sauk_trails` source.)
--
-- Replaces the single combined `sauk_trails` layer (migration 057) with one layer
-- per TRAILTYPE, grouped under "Sauk County Trails" in the sidebar. Colors mirror
-- SAUK_TRAIL_TYPES in docs/index.html (the popup + line styling use the same map).
-- The import script buckets layer 9 ("All Trails") into these per-type sources.
-- ============================================================

-- Drop the combined layer (template, experience links, and its data).
delete from experience_layers where template_slug = 'sauk_trails';
delete from layer_templates   where slug          = 'sauk_trails';
delete from osm_geometries    where source        = 'sauk_trails';

-- Per-type templates (line; color per type; grouped together; off by default).
insert into layer_templates (slug, label, geom_type, default_style, layer_group, sort_order) values
  ('sauk_trail_hiking',       'Hiking Trails',         'line', '{"color":"#2e7d32"}'::jsonb, 'Sauk County Trails', 110),
  ('sauk_trail_hike_bike',    'Hiking & Biking Trails','line', '{"color":"#00897b"}'::jsonb, 'Sauk County Trails', 111),
  ('sauk_trail_mtb',          'Mountain Bike Trails',  'line', '{"color":"#e65100"}'::jsonb, 'Sauk County Trails', 112),
  ('sauk_trail_bike_road',    'Bike Routes (On-Road)', 'line', '{"color":"#1565c0"}'::jsonb, 'Sauk County Trails', 113),
  ('sauk_trail_horse',        'Horseback Trails',      'line', '{"color":"#6d4c41"}'::jsonb, 'Sauk County Trails', 114),
  ('sauk_trail_snowmobile',   'Snowmobile Trails',     'line', '{"color":"#7b1fa2"}'::jsonb, 'Sauk County Trails', 115),
  ('sauk_trail_rescue_road',  'Rescue Roads',          'line', '{"color":"#c62828"}'::jsonb, 'Sauk County Trails', 116),
  ('sauk_trail_rescue_path',  'Rescue Paths',          'line', '{"color":"#ad1457"}'::jsonb, 'Sauk County Trails', 117)
on conflict (slug) do update
  set label = excluded.label, geom_type = excluded.geom_type,
      default_style = excluded.default_style, layer_group = excluded.layer_group;

-- Add each per-type layer to both experiences (public campsites + private default),
-- off by default (opt-in overlays).
insert into experience_layers (experience_id, template_slug, visible_by_default, sort_order)
select e.id, t.slug, false, t.sort_order
from experiences e
cross join (values
  ('sauk_trail_hiking', 110), ('sauk_trail_hike_bike', 111), ('sauk_trail_mtb', 112),
  ('sauk_trail_bike_road', 113), ('sauk_trail_horse', 114), ('sauk_trail_snowmobile', 115),
  ('sauk_trail_rescue_road', 116), ('sauk_trail_rescue_path', 117)
) as t(slug, sort_order)
where e.slug in ('campsites', 'default')
  and not exists (
    select 1 from experience_layers el
    where el.experience_id = e.id and el.template_slug = t.slug);
