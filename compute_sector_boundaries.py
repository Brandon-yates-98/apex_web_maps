#!/usr/bin/env python3
"""
compute_sector_boundaries.py
Compute a boundary polygon for every climbing sector (an area that is the
immediate parent of at least one route/boulder) from its climbs' coordinates,
and emit a SQL migration that loads them as the `climbing_sectors` layer.

Shape: convex hull of the sector's climbs, buffered ~35 m with round joins
(single climbs become circles), computed in a locally-scaled space so the
buffer is metrically round at Devil's Lake latitude, then lightly simplified.

Each polygon carries the same OpenBeta association properties as the area
markers (area_id / parent_id / area_path), so the public map's climb lists,
sub-tree filtering, and popups work on sectors out of the box.

Writes:
  migrations/015_climbing_sectors.sql   — run in Supabase SQL Editor
  _sectors_preview.geojson              — local visual QA (not committed)

Run:  .venv/Scripts/python.exe compute_sector_boundaries.py
Reads are anon (RLS-allowed); the write happens via the SQL file you run.
"""
import json
import math
import urllib.request

from shapely.geometry import MultiPoint, mapping
from shapely.affinity import scale as shp_scale

SUPABASE_URL = "https://lcenhesezodgrjrymngg.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxj"
    "ZW5oZXNlem9kZ3JqcnltbmdnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk0Mjk2MDksImV4"
    "cCI6MjA5NTAwNTYwOX0.HD9iIKp267i3t2csvLA68TBZ4ASDBL14xznlSQumn30"
)

BUFFER_DEG = 35 / 111_000          # ~35 m in latitude degrees
SIMPLIFY_DEG = 4 / 111_000         # ~4 m — keeps vertices low, shape smooth
OUT_SQL = "migrations/015_climbing_sectors.sql"
OUT_PREVIEW = "_sectors_preview.geojson"


def rpc(fn, args):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(args).encode(),
        headers={"Content-Type": "application/json", "apikey": ANON_KEY},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    routes = rpc("get_layer_geojson", {"p_source": "climbing_routes"})["features"]
    boulders = rpc("get_layer_geojson", {"p_source": "climbing_boulders"})["features"]
    areas = rpc("get_layer_geojson", {"p_source": "climbing_areas"})["features"]
    print(f"routes={len(routes)} boulders={len(boulders)} areas={len(areas)}")

    area_by_id = {}
    for f in areas:
        p = f["properties"]
        if p.get("area_id"):
            area_by_id[p["area_id"]] = p

    # Group climb coordinates by immediate parent sector
    by_sector = {}
    for f in routes + boulders:
        p = f["properties"]
        aid = p.get("area_id")
        if not aid or f["geometry"]["type"] != "Point":
            continue
        by_sector.setdefault(aid, []).append(tuple(f["geometry"]["coordinates"]))

    lat0 = 43.43
    kx = math.cos(math.radians(lat0))   # lon degrees are shorter than lat degrees

    features = []
    for aid, coords in sorted(by_sector.items()):
        meta = area_by_id.get(aid)
        if meta is None:
            continue  # climb references an area that has no marker — skip
        pts = MultiPoint(list(set(coords)))
        # locally-scaled space → metric-ish round buffer → back to degrees
        scaled = shp_scale(pts, xfact=kx, yfact=1.0, origin=(0, 0))
        poly = scaled.convex_hull.buffer(BUFFER_DEG, quad_segs=12).simplify(SIMPLIFY_DEG)
        poly = shp_scale(poly, xfact=1.0 / kx, yfact=1.0, origin=(0, 0))
        features.append({
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": {
                "_draw_id": "ob-sector-" + aid,
                "name": meta.get("name") or "(unnamed sector)",
                "area_id": aid,
                "parent_id": meta.get("parent_id") or "",
                "area_path": meta.get("area_path") or [],
                "depth": meta.get("depth") or 0,
                "climb_count": len(coords),
            },
            "custom_data": {"openbeta_id": aid},
        })
    print(f"sectors with boundaries: {len(features)}")

    with open(OUT_PREVIEW, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "features": [{k: v for k, v in feat.items() if k != "custom_data"}
                                for feat in features]}, f)

    def sq(s):  # SQL single-quote escape
        return str(s).replace("'", "''")

    rows = []
    for feat in features:
        props = dict(feat["properties"])
        geom = json.dumps(feat["geometry"], separators=(",", ":"))
        rows.append(
            "('climbing_sectors', '%s', st_setsrid(st_geomfromgeojson('%s'), 4326), "
            "'%s'::jsonb, '%s'::jsonb)" % (
                sq(props["name"]), sq(geom),
                sq(json.dumps(props, separators=(",", ":"))),
                sq(json.dumps(feat["custom_data"], separators=(",", ":"))),
            )
        )

    values_sql = ",\n".join(rows)
    sql = f"""-- ============================================================
-- Apex Web Maps — Climbing sector boundaries (generated)
-- Run in Supabase: Dashboard → SQL Editor → New query
-- Generated by compute_sector_boundaries.py — safe to re-run (replaces all).
-- ============================================================

insert into layer_templates (slug, label, geom_type, layer_group, default_style, is_custom)
values ('climbing_sectors', 'Climbing Sectors', 'polygon', 'Climbing',
        '{{"color":"#8e6fc1","fill_opacity":0.12}}'::jsonb, false)
on conflict (slug) do update
  set geom_type = excluded.geom_type, default_style = excluded.default_style;

delete from osm_geometries where source = 'climbing_sectors';

insert into osm_geometries (source, name, geometry, properties, custom_data) values
{values_sql};
"""
    with open(OUT_SQL, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"wrote {OUT_SQL} ({len(sql) // 1024} KB) and {OUT_PREVIEW}")


if __name__ == "__main__":
    main()
