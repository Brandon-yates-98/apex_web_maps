"""
Render OCR points back onto the map so they can be ground-truthed by eye.

Draws each ocr_sites.json point as a dot (green=standard, orange=electrical)
with its label, then saves zoomed regional crops where the printed map number
and the OCR dot/label are both legible side by side.

Usage:
  .venv/Scripts/python.exe scripts/overlay_ocr_points.py
"""
import argparse, json, os
from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
IMG   = os.path.join(_ROOT, 'Campsite Maps', 'Quartzite and Northern Lights Campground.png')

ap = argparse.ArgumentParser()
ap.add_argument('--pts', default=os.path.join(_ROOT, 'campsite_maps', 'ocr_sites.json'))
ap.add_argument('--out', default=os.path.join(_ROOT, 'campsite_maps', 'overlay'))
_a = ap.parse_args()
PTS = _a.pts if os.path.isabs(_a.pts) else os.path.join(_ROOT, _a.pts)
OUT = _a.out if os.path.isabs(_a.out) else os.path.join(_ROOT, _a.out)
os.makedirs(OUT, exist_ok=True)

with open(PTS) as f:
    pts = json.load(f)

base = Image.open(IMG).convert('RGB')
draw = ImageDraw.Draw(base)
try:
    font = ImageFont.truetype('arial.ttf', 9)
except Exception:
    font = ImageFont.load_default()

for p in pts:
    x, y = p['px'], p['py']
    elec = p['site_type'] == 'electrical'
    color = (255, 140, 0) if elec else (0, 170, 0)
    r = 2
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=(0, 0, 0))
    draw.text((x + 3, y - 5), p['name'], fill=color, font=font)

full = os.path.join(OUT, 'overlay_full.png')
base.save(full)
print(f'  {full}')

# Zoomed regional crops (overlap; large zoom so labels are readable).
REGIONS = [
    ('q_westcol',  150,  60, 360, 320, 4),
    ('q_south',    150, 300, 420, 520, 4),
    ('q_toploop',  150,  60, 420, 200, 4),
    ('q_innerE',   270, 120, 500, 320, 4),
    ('nl_entrance',420, 100, 660, 270, 4),
    ('nl_north',   600, 120, 880, 270, 4),
    ('nl_east',    780, 190, 1015, 400, 4),
    ('nl_innerN',  490, 230, 820, 360, 4),
    ('nl_innerS',  490, 350, 830, 480, 4),
    ('nl_midrow',  640, 320, 1010, 400, 4),
]
for name, x0, y0, x1, y1, z in REGIONS:
    x1 = min(x1, base.width); y1 = min(y1, base.height)
    crop = base.crop((x0, y0, x1, y1)).resize(((x1 - x0) * z, (y1 - y0) * z),
                                               Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(crop)
    d.rectangle([(0, 0), (crop.width, 14)], fill=(0, 0, 0))
    d.text((3, 2), f'{name}  ({x0},{y0})-({x1},{y1})  {z}x', fill=(255, 255, 0))
    path = os.path.join(OUT, f'{name}.png')
    crop.save(path)
    print(f'  {path}  ({crop.width}x{crop.height})')
print('Done.')
