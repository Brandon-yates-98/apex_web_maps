"""
De-duplicate migrations/026_campsite_sites_data.sql before applying.

For each (campground, ref) group with more than one row, keep the row whose
pixel position is closest to that site's reference position in SITES_DATA, and
drop the rest (these are OCR-misread strays and accidental double-adds). Also
flags any surviving site that sits >100px from its reference, as a heads-up for
possible bad matches the reviewer may have missed.

Writes the cleaned SQL back in place. Prints a report.
"""
import re, json, os, sys, numpy as np, collections

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
SQL = os.path.join(_ROOT, 'migrations', '026_campsite_sites_data.sql')
sys.path.insert(0, _HERE)
from ocr_campsites import SITES_DATA

def num_of(n): return re.sub(r'[eE]$', '', str(n)).lstrip('0') or '0'

# reference position keyed by bare number
ref_pos = {}
for name, cg, px, py in SITES_DATA:
    ref_pos.setdefault(num_of(name), (px, py))

# inverse affine: lon/lat -> px,py
c = json.load(open(os.path.join(_ROOT, 'Campsite Maps', 'overlay_gcps.json'))); iw, ih = 1105, 802
g = [(0,0,*c['TL']),(iw,0,*c['TR']),(iw,ih,*c['BR']),(0,ih,*c['BL'])]
A = np.column_stack([[p[0] for p in g],[p[1] for p in g],np.ones(4)])
lc,*_ = np.linalg.lstsq(A, np.array([p[2] for p in g]), rcond=None)
ac,*_ = np.linalg.lstsq(A, np.array([p[3] for p in g]), rcond=None)
M = np.array([[lc[0],lc[1]],[ac[0],ac[1]]]); b = np.array([lc[2],ac[2]]); Minv = np.linalg.inv(M)

lines = open(SQL).read().splitlines()
header = [l for l in lines if not l.startswith('insert into')]
inserts = [l for l in lines if l.startswith('insert into')]

rows = []
for l in inserts:
    p = json.loads(re.search(r"'(\{.*\})'::jsonb", l).group(1).replace("''", "'"))
    lon, lat = map(float, re.search(r'st_makepoint\(([-\d.]+),([-\d.]+)\)', l).groups())
    px, py = Minv @ (np.array([lon, lat]) - b)
    rows.append({'line': l, 'cg': p['campground'], 'ref': p['ref'],
                 'name': p['name'], 'px': px, 'py': py})

groups = collections.defaultdict(list)
for r in rows:
    groups[(r['cg'], r['ref'])].append(r)

kept, dropped = [], []
for key, grp in groups.items():
    if len(grp) == 1:
        kept.append(grp[0]); continue
    rp = ref_pos.get(key[1])
    def dist(r):
        if not rp: return 0
        return (r['px'] - rp[0]) ** 2 + (r['py'] - rp[1]) ** 2
    grp.sort(key=dist)
    kept.append(grp[0])
    dropped.extend(grp[1:])

# flag far-from-reference survivors
far = []
for r in kept:
    rp = ref_pos.get(r['ref'])
    if rp and ((r['px'] - rp[0]) ** 2 + (r['py'] - rp[1]) ** 2) ** 0.5 > 100:
        far.append((r['name'], round(r['px']), round(r['py']), round(rp[0]), round(rp[1])))

kept_lines = [r['line'] for r in kept]
out = header + [''] + kept_lines if header and header[-1] != '' else header + kept_lines
with open(SQL, 'w') as f:
    f.write('\n'.join(out) + '\n')

print(f'kept {len(kept)} inserts, dropped {len(dropped)} duplicates')
for r in dropped:
    print(f'  DROP {r["name"]:6s} at px={r["px"]:.0f} py={r["py"]:.0f}')
if far:
    print(f'FAR FROM REFERENCE (>100px, check in GUI if wrong): {far}')
