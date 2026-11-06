"""PebblesB (ground cover, stones): a loose scatter over 0.85 m with one big stone: a pink-grey granite boulder 24 cm
long, chipped and half sunk in a skirt of dirt, with a dozen thumb- to fist-sized stones lying around it at their own
distances (granite, tan sandstone, a dark one) and gravel between. Dirt clings low on every stone.

    blender -b --factory-startup --python pebbles_b.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "PebblesB", "pebbles_b"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(23)
G = nk.GROUND

grey = ks_.granite("PebGranite")
pink = ks_.granite("PebGranitePink", tint_lo=(0.95, 0.74, 0.66), tint_hi=(1.3, 1.0, 0.88))
dark = ks_.granite("PebGraniteDark", tint_lo=(0.5, 0.52, 0.56), tint_hi=(0.75, 0.75, 0.78), soil=0.8)
sand = ks_.sandstone("PebSandstone")
soil = ks_.soil_material("PebSoil")

S = ks_.Set(NAME)
# The big stone, with a skirt of dirt pushed up round it
bx, by = -0.1, 0.06
ks_.pad(S.gm(soil), (bx, by), 0.2, rnd, dome=0.01, lobes=0.35, stretch=(1.2, 0.95), yaw=0.4)
ks_.pebble(S, pink, bx, by, 0.1, rnd, flat=0.62, elong=1.3, tv=0.55, chip=1.0, power=2.6, rough=0.1, sub=4, tilt=0.12, height=0.075)

# The scatter: points spread over the block, none on the big stone
pts = ks_.poisson(13, 0.4, 0.12, rnd, stretch=(1.05, 0.95))
sizes = sorted([rnd.uniform(0.02, 0.05) for _ in pts], reverse=True)
mats = [sand, grey, sand, dark, grey, pink, sand, grey, sand, dark, grey, sand, grey]
k = 0
for p, r in zip(pts, sizes):
    if math.hypot(p.x - bx, p.y - by) < 0.17 + r:
        continue
    ks_.pebble(S, mats[k % len(mats)], p.x, p.y, r, rnd, lod=2 if r > 0.03 else 1)
    if rnd.random() < 0.5:
        ks_.pad(S.gm(soil), (p.x, p.y), r * rnd.uniform(1.6, 2.4), rnd, sides=12, rings=2, dome=0.004, lobes=0.4)
    k += 1
# Gravel, and a few small stones tucked against the big one
for i in range(14):
    a = rnd.uniform(0, math.tau)
    d = rnd.uniform(0.08, 0.42)
    x, y = math.cos(a) * d * 1.05, math.sin(a) * d * 0.95
    if math.hypot(x - bx, y - by) < 0.15:
        continue
    ks_.pebble(S, rnd.choice((grey, sand, dark, pink)), x, y, rnd.uniform(0.007, 0.014), rnd, lod=1, sub=1, chip=0.0)
for i in range(3):
    a = rnd.uniform(0, math.tau)
    ks_.pebble(S, rnd.choice((sand, grey)), bx + math.cos(a) * 0.15, by + math.sin(a) * 0.12, rnd.uniform(0.015, 0.025), rnd, lod=1)

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024,
                   density={"PebGranite": 1.0, "PebSandstone": 1.0, "PebSoil": 0.6})
ks_.preview(SCRIPT, model, PREVIEWS, kind="grass", height=0.08)
print("[%s] done" % SCRIPT)
