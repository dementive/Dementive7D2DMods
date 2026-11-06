"""PebblesA (ground cover, stones): a tight cluster of 15 rounded stones, fist- to thumb-sized, half sunk in a ragged pad
of dirt: grey and pink granite, tan sandstone and one pale quartz, big ones in the middle and small ones crowding
round them, a few specks of gravel strewn out from the cluster. Dirt clings low on every stone.

    blender -b --factory-startup --python pebbles_a.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "PebblesA", "pebbles_a"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(11)
G = nk.GROUND

grey = ks_.granite("PebGranite")
pink = ks_.granite("PebGranitePink", tint_lo=(0.95, 0.74, 0.66), tint_hi=(1.3, 1.0, 0.88))
sand = ks_.sandstone("PebSandstone")
quartz = ks_.quartz("PebQuartz")
soil = ks_.soil_material("PebSoil")

S = ks_.Set(NAME)
ks_.pad(S.gm(soil), (0.0, 0.0), 0.2, rnd, dome=0.01, lobes=0.4, stretch=(1.2, 0.9), yaw=0.5)
for k in range(3):
    a = rnd.uniform(0, math.tau)
    d = rnd.uniform(0.16, 0.28)
    ks_.pad(S.gm(soil), (math.cos(a) * d, math.sin(a) * d), rnd.uniform(0.03, 0.055), rnd, sides=14, rings=2, dome=0.006,
            lobes=0.35)

# Sizes (radius in meters): a few fist-sized, many smaller down to thumb-sized
sizes = sorted([0.058, 0.05, 0.043, 0.04, 0.036, 0.033, 0.03, 0.028, 0.026, 0.024, 0.022, 0.02, 0.018, 0.016, 0.014],
               reverse=True)
mix = [pink, grey, sand, grey, sand, quartz, grey, sand, pink, sand, grey, sand, grey, pink, sand]
placed = []
for r, mat in zip(sizes, mix):
    for _ in range(400):
        if not placed:
            p = (rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03))
        else:
            sig = 0.055 + 0.012 * len(placed) ** 0.5
            p = (rnd.gauss(0, sig) * 1.2, rnd.gauss(0, sig) * 0.9)
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= (r + qr) * 0.92 for q, qr in placed):
            break
    placed.append((p, r))
    ks_.pebble(S, mat, p[0], p[1], r, rnd, lod=2 if r > 0.02 else 1)
# Gravel strewn out from the cluster
for k in range(9):
    a = rnd.uniform(0, math.tau)
    d = rnd.uniform(0.18, 0.4)
    ks_.pebble(S, rnd.choice((grey, sand, grey, pink)), math.cos(a) * d, math.sin(a) * d, rnd.uniform(0.007, 0.012), rnd,
               lod=1, sub=1, chip=0.0)

pieces = S.objects()
print("[%s] pieces %d" % (SCRIPT, len(pieces)))
model = ks_.export(NAME, pieces, MODELS, size=1024,
                   density={"PebGranite": 1.0, "PebSandstone": 1.0, "PebQuartz": 1.0, "PebSoil": 0.6})
ks_.preview(SCRIPT, model, PREVIEWS, kind="grass", height=0.07)
print("[%s] done" % SCRIPT)
