"""
Build the final campsite set by combining the two sources for what each is best at:

  * Inventory + electrical flag  <- vision SITES_DATA (knowing WHICH sites exist
    and which are electrical doesn't need pixel precision, and vision is complete).
  * Position                     <- OCR (coordinates come from real ink on this
    exact image, so they're accurate). For sites OCR missed, the rough vision
    position is corrected by the LOCAL OCR-vs-vision offset of nearby anchored
    sites -- i.e. the OCR points ground-truth the vision locations.

Output: campsite_maps/merged_sites.json  (picker format for ocr_campsites.py --load)

Usage:
  .venv/Scripts/python.exe scripts/build_sites.py
"""
import json, os, re, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
OCR   = os.path.join(_ROOT, 'campsite_maps', 'ocr_sites.json')
OUT   = os.path.join(_ROOT, 'campsite_maps', 'merged_sites.json')

sys.path.insert(0, _HERE)
from ocr_campsites import SITES_DATA   # inventory + e-flags + rough positions

def num_of(name): return re.sub(r'[eE]$', '', str(name)).lstrip('0') or '0'

# ── Reference inventory (vision): name -> (campground, ref_px, ref_py) ─────────
ref = {}
for name, cg, px, py in SITES_DATA:
    ref[str(name)] = (cg, float(px), float(py))

# ── OCR detections, keyed by bare number -> list of candidates ─────────────────
with open(OCR) as f:
    ocr = json.load(f)
ocr_by_num = {}
for d in ocr:
    ocr_by_num.setdefault(num_of(d['name']), []).append(d)

# ── Match each ref site to its OCR detection (by number; nearest ref if dup) ───
# OCR position wins where available (it's tied to real ink). Where OCR missed the
# site, fall back to the vision position as-is -- attempts to "correct" it from
# neighbouring anchors drag clustered-missing rows badly, and the raw vision
# position (±10-20px) is the better automated guess for the reviewer to nudge.
positions = {}   # ref name -> (px, py, source)
matched_count = 0
for name, (cg, rx, ry) in ref.items():
    cands = ocr_by_num.get(num_of(name), [])
    if cands:
        best = min(cands, key=lambda d: (d['px'] - rx) ** 2 + (d['py'] - ry) ** 2)
        positions[name] = (best['px'], best['py'], 'ocr')
        matched_count += 1
    else:
        positions[name] = (rx, ry, 'vision')

# ── Emit ───────────────────────────────────────────────────────────────────────
sites = []
for name, (cg, rx, ry) in ref.items():
    px, py, src = positions[name]
    sites.append({
        'name': name,
        'campground': cg,
        'site_type': 'electrical' if str(name).lower().endswith('e') else 'standard',
        'px': round(px, 1), 'py': round(py, 1),
        'source': src,
    })
sites.sort(key=lambda s: (s['campground'], int(num_of(s['name']))))

# Dedup exact (campground, name) repeats; warn on ref collisions (N vs Ne).
seen = set(); deduped = []
for s in sites:
    key = (s['campground'], s['name'])
    if key in seen:
        continue
    seen.add(key); deduped.append(s)
sites = deduped
import collections as _c
ref_groups = _c.defaultdict(list)
for s in sites:
    ref_groups[(s['campground'], num_of(s['name']))].append(s['name'])
collisions = {k: v for k, v in ref_groups.items() if len(v) > 1}

with open(OUT, 'w') as f:
    json.dump(sites, f, indent=2)

vision = sum(1 for s in sites if s['source'] == 'vision')
q  = sum(1 for s in sites if s['campground'] == 'quartzite')
nl = sum(1 for s in sites if s['campground'] == 'northern_lights')
el = sum(1 for s in sites if s['site_type'] == 'electrical')
print(f'{len(sites)} sites  (Q={q}  NL={nl}  electrical={el})')
print(f'  OCR-accurate positions: {matched_count}   vision fallback (nudge in GUI): {vision}')
if collisions:
    print(f'  WARNING ref collisions (same number, std+elec): {dict(collisions)}')
print(f'  vision-positioned sites: {sorted([s["name"] for s in sites if s["source"]=="vision"], key=lambda n: int(num_of(n)))}')
print(f'Wrote {OUT}')
