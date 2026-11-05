"""Heather (snow): a dense low mound 25 to 40 cm and most of a block across: a few gnarled woody stems at the base,
sixty sprays of fine dark green needle foliage filling the dome, and crowded over it 150 flowering tips, each a 6 to
10 cm spike of tiny purple-pink bells (a few paler ones among them), so the whole mound reads as a cushion of
purple-pink. Spikes and sprays are crossed narrow blades, so they read solid from any side with no alpha. No grass: it grows on the high moors and snowy ground.

    blender -b --factory-startup --python heather.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "Heather", "heather"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(29)
G = nk.GROUND
UP = Vector((0, 0, 1))
R, H = 0.42, 0.33

woodm = nk.plant("HeatherWood", (0.12, 0.08, 0.05), (0.08, 0.055, 0.035), rough=0.85, sat=0.8)
needlem = nk.plant("HeatherNeedle", (0.09, 0.15, 0.06), (0.12, 0.16, 0.07), rough=0.75, vary=0.35)
bellm = nk.petal("HeatherBell", (0.3, 0.07, 0.25), (0.72, 0.3, 0.64), mid=(0.56, 0.18, 0.48),
                   rough=0.6, vary=0.2, sat=1.0, value=0.95)
palem = nk.petal("HeatherPale", (0.36, 0.14, 0.32), (0.8, 0.5, 0.74), mid=(0.62, 0.32, 0.56),
                   rough=0.6, vary=0.2, sat=1.0, value=0.95)


def dome(r):
    return H * max(0.0, 1.0 - (r / R) ** 2) ** 0.6


def normal(x, y):
    return (Vector((x / R * 0.8, y / R * 0.8, 1.0)) + Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 0.0))
            ).normalized()


pieces = []

# Gnarled woody stems, seen only round the base
for k in range(8):
    az = k / 8 * math.tau + rnd.uniform(-0.3, 0.3)
    o = Vector((math.cos(az), math.sin(az), 0.0))
    base = o * rnd.uniform(0.0, 0.06) + Vector((0, 0, G))
    end = o * rnd.uniform(0.2, 0.3) + Vector((0, 0, G + rnd.uniform(0.06, 0.12)))
    mid = base.lerp(end, 0.5) + UP * 0.025 + Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0.0))
    pieces.append(kw.rod("Wood%d" % k, [base, mid, end], 0.008, 0.004, woodm, sides=3))

# Sprays of needle foliage filling the dome under the flowers
for i, (x, y) in enumerate(nk.scatter(60, 0.39, seed=4, min_gap=0.045)):
    r = math.hypot(x, y)
    n = normal(x, y)
    length = rnd.uniform(0.08, 0.12)
    top = Vector((x, y, G + 0.015 + dome(r) * rnd.uniform(0.55, 0.9)))
    pieces += kw.brush("Spray%d_" % i, top - n * length, n, length, rnd.uniform(0.01, 0.014), needlem, blades=3,
                       arch=rnd.uniform(0.1, 0.35), seed=i, profile="linear", segments=2)

# Flowering tips crowded over the whole dome: each a spike of tiny bells, seen as one solid shape (three crossed
# blades), darker at the base where the bells are older and shaded
for i, (x, y) in enumerate(nk.scatter(150, 0.39, seed=8, min_gap=0.028)):
    r = math.hypot(x, y)
    n = normal(x, y)
    length = rnd.uniform(0.06, 0.1)
    tip = Vector((x, y, G + 0.025 + dome(r) * rnd.uniform(0.86, 1.04)))
    base = tip - n * length
    pieces += kw.brush("Spike%d_" % i, base, n, length, rnd.uniform(0.018, 0.024), palem if i % 8 == 3 else bellm,
                       blades=3, arch=rnd.uniform(0.05, 0.3), seed=100 + i, profile="raceme", segments=3)

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.17, distance=1.3)
kw.view(SCRIPT, "close", model, PREVIEWS, (0.08, -0.38, G + 0.5), (0.0, -0.05, G + 0.3))
print("[%s] done" % SCRIPT)
