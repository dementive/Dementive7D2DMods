"""CharredShrub (burnt forest): what a fire left of a bush, 50 to 80 cm. A knot of charred root crown, seven twisted
black stems with alligator-cracked char and blunt burnt-off tips, a tangle of black twigs, all standing in a low
mound of grey ash with lumps of charcoal; and coming up through the ash round its base, two dozen bright fresh green
shoots with soft new leaves, the first thing back after a fire.

    blender -b --factory-startup --python charred_shrub.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

NAME, SCRIPT = "CharredShrub", "charred_shrub"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(31)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

char = ks.char("Char", ash_amount=0.55)
ash = ks.ash("Ash")
shoot_leaf = nk.plant("ShootLeaf", (0.2, 0.46, 0.04), (0.33, 0.56, 0.07), rough=0.55, vary=0.3, sat=1.0, value=1.0)
shoot_young = nk.plant("ShootYoung", (0.42, 0.55, 0.08), (0.45, 0.3, 0.08), rough=0.55, vary=0.3, sat=1.0, value=1.0)
shoot_stem = nk.plant("ShootStem", (0.38, 0.14, 0.07), (0.22, 0.34, 0.07), rough=0.6, sat=1.0)

b = ks.Builder("Char")

# Root crown: thick charred stubs splaying out at the ground
for k in range(5):
    a = k / 5 * math.tau + rnd.uniform(-0.3, 0.3)
    d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.15, 0.1)))
    root = ks.grow(rnd, (0.0, 0.0, G + 0.03), d, rnd.uniform(0.1, 0.18), rnd.uniform(0.018, 0.025), 0.006,
                   segments=2, wander=0.1)
    ks.wood(b, char, [root], sides=(5,))

# Burnt stems, twisted, their tips burnt off blunt
stems = []
for i in range(7):
    a = (i + rnd.uniform(-0.3, 0.3)) / 7 * math.tau
    lean = rnd.random()
    r0 = 0.015 + 0.05 * lean
    tilt = math.radians(8 + 32 * lean)
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    stems.append(ks.grow(rnd, (r0 * math.cos(a), r0 * math.sin(a), G), d, rnd.uniform(0.55, 0.75) - 0.15 * lean,
                         rnd.uniform(0.012, 0.016), 0.004, segments=4, gravity=0.2, wander=0.14, kink=0.2))
ks.fit(stems, 0.3)
branches = []
for st in stems:
    branches += ks.branch_out(rnd, st, 3, (0.3, 0.9), (0.12, 0.28), (30, 60), 0.6, segments=2, wander=0.18,
                              tip_radius=0.0025, lift=0.1, kink=0.3)
twigs = []
for br in branches:
    twigs += ks.branch_out(rnd, br, 3, (0.3, 1.0), (0.04, 0.11), (30, 70), 0.6, segments=1, wander=0.0,
                           tip_radius=0.0013)
ks.wood(b, char, stems, sides=(4,))
ks.wood(b, char, branches, sides=(3,))
b.lod = 1
ks.wood(b, char, twigs, sides=(3,))
b.lod = 0

# Ash mound and charcoal lumps
ks.ground_patch(b, ash, (0.0, 0.0), 0.38, rnd, sides=22, dome=0.035, jitter=0.15, sink=0.012, rings=3)
b.lod = 1
for k in range(9):
    a = rnd.uniform(0, math.tau)
    r = rnd.uniform(0.06, 0.3)
    ks.berry(b, char, (r * math.cos(a), r * math.sin(a), G + 0.022), rnd.uniform(0.008, 0.016), rnd, sides=4,
             stretch=0.6, axis=(rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 1.0))
b.lod = 0

# Fresh shoots through the ash round the base: red-green stems with soft bright leaves spiraling up them
shoots = 0
for i, (x, y) in enumerate(nk.scatter(32, 0.28, seed=4, min_gap=0.04)):
    if math.hypot(x, y) < 0.05:
        continue
    out = Vector((x, y, 0.0)).normalized()
    h = rnd.uniform(0.1, 0.3)
    d = (UP + out * rnd.uniform(0.1, 0.45)).normalized()
    sh = ks.grow(rnd, (x, y, G + 0.01), d, h, 0.0028, 0.0, segments=2, wander=0.12, gravity=-0.3)
    b.lod = 1
    ks.wood(b, shoot_stem, [sh], sides=(3,))
    b.lod = 0
    count = 5 + int(h * 26)
    for p, ld, tan, s in ks.spiral_points(rnd, sh, count, (0.25, 1.0), (55, 80), lift=0.25):
        far = rnd.random() < 0.5
        b.lod, b.lod_scale = (0, 1.35) if far else (1, 1.0)
        size = 1.0 - 0.45 * s
        ks.leaf(b, shoot_young if s > 0.8 else shoot_leaf, p, ld, 0.055 * size + 0.014, 0.032 * size + 0.007,
                bend=0.3, fold=0.35, profile="oval", rows=1)
        b.lod, b.lod_scale = 0, 1.0
    shoots += 1

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] shoots %d" % (SCRIPT, shoots))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.3, distance=1.8)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.3, distance=1.8)
print("[%s] done" % SCRIPT)
