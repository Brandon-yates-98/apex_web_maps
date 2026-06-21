-- ============================================================
-- Devil's Lake Mapping Project — campsite Street View camera (stand on road, face site)
-- Applied via Supabase MCP; recorded for the repo log.
--
-- Precomputes, for every campsite_sites point, where a Street View camera should
-- stand and which way it should face so the first frame looks AT the campsite:
--   * sv_lng / sv_lat : the closest point on the nearest real road (the spur/road
--     intersection for spurred sites; the nearest road point otherwise).
--   * sv_heading       : bearing from that standing point toward the campsite
--     (degrees, 0=N clockwise — same convention as the Maps Embed API `heading`).
--
-- Standing point = the spur's actual road end when a spur exists (the literal
-- spur/road intersection the user sees on the map), else the closest point on the
-- nearest real road. On-road sites (standing point == campsite, azimuth undefined)
-- get no heading -> default facing. Heading is reset each run so it never goes stale.
--
-- Re-runnable: re-invoke after roads/spurs change. service_role-only.
-- ============================================================

create or replace function public.set_campsite_streetview_camera()
returns int language sql security definer set search_path = public, extensions as $fn$
  with spur as (
    select properties->>'campsite' as campsite, st_endpoint(geometry) as endpt
    from osm_geometries
    where source = 'roads' and (properties->>'_spur')::bool is true
  ),
  cam as (
    select cs.id, cs.geometry as site,
      coalesce(
        (select sp.endpt from spur sp where sp.campsite = cs.name limit 1),  -- spur/road intersection
        st_closestpoint(r.geom, cs.geometry)                                 -- else nearest road point
      ) as stand
    from osm_geometries cs
    cross join lateral (
      select r2.geometry as geom
      from osm_geometries r2
      where r2.source = 'roads'
        and coalesce((r2.properties->>'_spur')::bool, false) = false  -- aim at real roads, not spurs
        and r2.geometry is not null
      order by r2.geometry <-> cs.geometry   -- KNN nearest road
      limit 1
    ) r
    where cs.source = 'campsite_sites' and cs.geometry is not null
  ),
  upd as (
    update osm_geometries o
    set properties = (o.properties - 'sv_heading') || jsonb_strip_nulls(jsonb_build_object(
          'sv_lng', round(st_x(cam.stand)::numeric, 7),
          'sv_lat', round(st_y(cam.stand)::numeric, 7),
          'sv_heading', case when st_distance(cam.stand::geography, cam.site::geography) > 1
                             then round(degrees(st_azimuth(cam.stand::geography, cam.site::geography))::numeric, 1)
                             else null end))   -- omit heading for on-road sites (azimuth undefined)
    from cam
    where o.id = cam.id
    returning 1
  )
  select count(*)::int from upd;
$fn$;

revoke execute on function public.set_campsite_streetview_camera() from public, anon, authenticated;
grant  execute on function public.set_campsite_streetview_camera() to service_role;

select public.set_campsite_streetview_camera();
