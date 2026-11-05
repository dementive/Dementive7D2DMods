"""Reeds (water's edge): a dense stand of common reed filling a block, 32 thin straw-green stems 1.2 to 1.8 m, each
with three or four long narrow grey-green leaves sticking out at an angle and drooping at their tips, half of them
topped by a soft purple-brown plume 20 to 30 cm long, sweeping over to one side the way the wind leaves them. The
others end in a young leaf. No grass: it grows in water.

    blender -b --factory-startup --python reeds.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "Reeds", "reeds"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(8)
G = nk.GROUND
UP = Vector((0, 0, 1))

stemm = nk.plant("ReedStem", (0.24, 0.25, 0.12), (0.32, 0.27, 0.14), rough=0.5, vary=0.3)
leafm = nk.plant("ReedLeaf", (0.15, 0.2, 0.11), (0.19, 0.23, 0.15), rough=0.6, vary=0.3)
drym = nk.plant("ReedDry", (0.33, 0.27, 0.15), (0.24, 0.19, 0.1), rough=0.8, vary=0.3, sat=0.8)
plumem = nk.petal("ReedPlume", (0.1, 0.045, 0.05), (0.34, 0.24, 0.17), mid=(0.2, 0.09, 0.1), rough=0.95, vary=0.25,
                  sat=0.95, value=0.95)

wind = Vector((1.0, 0.25, 0.0)).normalized()
pieces = []
for i, (x, y) in enumerate(nk.scatter(32, 0.28, seed=6, min_gap=0.03)):
    h = rnd.uniform(1.2, 1.8)
    out = Vector((x, y, 0.0))
    lean = out * 0.25 + wind * rnd.uniform(0.0, 0.06) + Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0))
    base = Vector((x, y, G))
    pts = [base]
    for s in (0.35, 0.7, 1.0):
        pts.append(base + UP * (h * s) + lean * (s ** 1.6) +
                   Vector((rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01), 0.0)) * (s > 0.2))
    plumed = i % 2 == 0
    pieces.append(kw.rod("Stem%d" % i, pts, 0.0042, 0.0016, stemm, sides=3))
    top = pts[-1]
    axis = (pts[-1] - pts[-2]).normalized()

    # Leaves alternating up the stem, sticking out and drooping
    count = rnd.choice((3, 4, 4))
    a = rnd.uniform(0, math.tau)
    for k in range(count):
        s = 0.18 + (0.68 if plumed else 0.62) * (k + rnd.uniform(0.0, 0.5)) / count
        # Position on the polyline
        seg = min(2, int(s / 0.35))
        f = (s - (0.0, 0.35, 0.7)[seg]) / (0.35, 0.35, 0.3)[seg]
        at = pts[seg].lerp(pts[seg + 1], min(1.0, f))
        a += math.pi + rnd.uniform(-0.6, 0.6)
        o = Vector((math.cos(a), math.sin(a), 0.0))
        if out.length > 0.12 and o.dot(out.normalized()) > 0.35:
            # Leaves on the rim turn along it rather than out over the next block
            o = Vector((-o.y, o.x, 0.0)) * rnd.choice((-1, 1))
        sp = math.radians(rnd.uniform(25, 42))
        d = (UP * math.cos(sp) + o * math.sin(sp)).normalized()
        dry = s < 0.3 and rnd.random() < 0.5
        pieces.append(kw.leaf("Leaf%d_%d" % (i, k), at, d, rnd.uniform(0.25, 0.4), rnd.uniform(0.018, 0.026),
                              drym if dry else leafm, arch=rnd.uniform(0.6, 1.2), power=1.5,
                              twist=rnd.uniform(-60, 60), segments=4, profile="linear", toward=o))
    if plumed:
        lv = Matrix.Rotation(rnd.uniform(-1.2, 1.2), 3, UP) @ wind
        # The top of the stalk nods over with the weight of the plume
        pl = rnd.uniform(0.2, 0.3)
        r1 = top + axis * (pl * 0.55) + lv * (pl * 0.12)
        r2 = r1 + (axis * 0.6 + lv * 0.8).normalized() * (pl * 0.4)
        pieces.append(kw.rod("Rachis%d" % i, [top, r1, r2], 0.0016, 0.0008, stemm, sides=3))
        pieces += kw.plume("Plume%d_" % i, r1, (r1 - top).normalized(), pl * 0.9, plumem, lv, seed=i, branches=14,
                           width=rnd.uniform(0.013, 0.017))
    else:
        # A young leaf still rolled round the tip
        o = Vector((math.cos(a + 2.0), math.sin(a + 2.0), 0.0))
        pieces.append(kw.leaf("Tip%d" % i, top - axis * 0.06, (axis + o * 0.3).normalized(), rnd.uniform(0.18, 0.28),
                              0.012, leafm, arch=rnd.uniform(0.3, 0.8), power=1.6, segments=4, profile="linear",
                              toward=o))

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.95, distance=4.3)
kw.view(SCRIPT, "plumes", model, PREVIEWS, (0.5, -1.2, 1.6), (0.0, 0.0, 1.05))
kw.wide_patch(SCRIPT, model, PREVIEWS, height=1.9)
print("[%s] done" % SCRIPT)
