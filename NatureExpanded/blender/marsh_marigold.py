"""Marsh marigold (water's edge): a low glossy mound 25 to 35 cm from four crowns, 30 round, heart- to
kidney-shaped dark green leaves on fleshy stalks, shingled over a dome, and 26 buttery yellow cup flowers about
6 cm across (five broad glossy sepals round a boss of yellow stamens) sitting just over the leaves, with a few round
green buds. No grass: it grows in water.

    blender -b --factory-startup --python marsh_marigold.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "MarshMarigold", "marsh_marigold"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(17)
G = nk.GROUND
UP = Vector((0, 0, 1))

leafm = nk.plant("MarigoldLeaf", (0.06, 0.14, 0.04), (0.09, 0.18, 0.055), rough=0.58, vary=0.25, wax=True)
stalkm = nk.plant("MarigoldStalk", (0.12, 0.2, 0.07), (0.16, 0.2, 0.08), rough=0.45, wax=True)
sepal = nk.petal("MarigoldSepal", (0.85, 0.52, 0.008), (1.0, 0.74, 0.03), rough=0.42, vary=0.06, sat=1.0, value=1.0)
boss = nk.petal("MarigoldBoss", (0.55, 0.42, 0.02), (0.9, 0.62, 0.02), rough=0.5, sat=1.0)
budm = nk.plant("MarigoldBud", (0.2, 0.26, 0.05), (0.32, 0.3, 0.04), rough=0.4, wax=True)

crowns = [Vector((x, y, G)) for x, y in nk.scatter(4, 0.12, seed=2, min_gap=0.08)]
pieces = []


def nearest_crown(p):
    return min(crowns, key=lambda c: (c.x - p.x) ** 2 + (c.y - p.y) ** 2)


def dome_z(r):
    """Height of the leaf mound over the ground at `r` from the middle."""
    return 0.035 + 0.2 * max(0.0, 1.0 - (r / 0.42) ** 2)


# Leaves shingled over a dome: each blade's center on the mound's surface, its stalk back to the nearest crown
for i, (x, y) in enumerate(nk.scatter(30, 0.32, seed=6, min_gap=0.075)):
    r = math.hypot(x, y)
    crown = nearest_crown(Vector((x, y, 0)))
    fwd = Vector((x - crown.x, y - crown.y, 0.0))
    if fwd.length < 0.03:
        fwd = Vector((math.cos(i * 2.4), math.sin(i * 2.4), 0.0))
    fwd.normalize()
    radius = rnd.uniform(0.05, 0.072)
    att = Vector((x, y, 0.0)) - fwd * (radius * 0.45)
    att.z = G + dome_z(r) * rnd.uniform(0.85, 1.05)
    tilt = 15.0 - 45.0 * min(1.0, r / 0.32) + rnd.uniform(-8, 8)
    mid = crown.lerp(att, 0.3) + UP * ((att.z - G) * 0.5)
    pieces.append(kw.rod("Petiole%d" % i, [crown, mid, att], 0.0042, 0.0028, stalkm, sides=3))
    pieces.append(kw.round_leaf("Leaf%d" % i, att, fwd, radius, leafm, tilt=tilt, cup=rnd.uniform(0.08, 0.18),
                                notch=rnd.uniform(0.55, 0.8), seed=i, points=12))

# Flowers sitting just over the leaves, open cups facing up and out
for i, (x, y) in enumerate(nk.scatter(26, 0.31, seed=12, min_gap=0.068)):
    r = math.hypot(x, y)
    top = Vector((x, y, G + dome_z(r) + rnd.uniform(0.025, 0.05)))
    crown = nearest_crown(top)
    out = Vector((x, y, 0.0)).normalized() if r > 0.02 else Vector((1, 0, 0))
    mid = crown.lerp(top, 0.5) + UP * 0.03 + Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0))
    pieces.append(kw.rod("Stem%d" % i, [crown, mid, top], 0.003, 0.0022, stalkm, sides=3))
    axis = (UP + out * (0.25 + 0.8 * r / 0.3) + Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0))
            ).normalized()
    size = rnd.uniform(0.028, 0.032)
    a0 = rnd.uniform(0, math.tau)
    side = kw._perp(axis)
    up = axis.cross(side)
    for k in range(5):
        a = a0 + k * math.tau / 5 + rnd.uniform(-0.15, 0.15)
        o = side * math.cos(a) + up * math.sin(a)
        d = (o * math.cos(math.radians(14)) + axis * math.sin(math.radians(14))).normalized()
        pieces.append(kw.leaf("Sepal%d_%d" % (i, k), top, d, size * rnd.uniform(0.92, 1.08), size * 0.95, sepal,
                              arch=-0.12, power=1.5, segments=4, profile="oval", toward=o))
    pieces.append(kw.dome("Boss%d" % i, top + axis * 0.001, axis, size * 0.34, size * 0.26, boss, segments=8))

# Round buds on short stalks
for i, (x, y) in enumerate(nk.scatter(3, 0.26, seed=31, min_gap=0.12)):
    r = math.hypot(x, y)
    top = Vector((x, y, G + dome_z(r) + 0.02))
    crown = nearest_crown(top)
    pieces.append(kw.rod("BudStem%d" % i, [crown, crown.lerp(top, 0.5) + UP * 0.02, top], 0.0026, 0.002, stalkm,
                         sides=3))
    ax = (UP + Vector((x, y, 0.0)) * 1.5).normalized()
    pieces.append(kw.sausage("Bud%d" % i, top - ax * 0.002, ax, 0.016, 0.0075, budm, sides=6, seed=i))

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.15, distance=1.25)
kw.view(SCRIPT, "close", model, PREVIEWS, (0.15, -0.45, 0.0), (0.0, 0.0, G + 0.25))
print("[%s] done" % SCRIPT)
