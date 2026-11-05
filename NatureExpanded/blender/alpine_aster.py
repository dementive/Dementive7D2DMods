"""Alpine aster (snow): a low cushion 15 to 25 cm of eleven overlapping rosettes of soft grey-green spoon leaves, with 30
blue-violet asters 5 to 6 cm across held just over it on short, nearly upright stems, most facing the sky: a ring of 20
thin rays round a golden yellow disc. A few heads are aging paler, a few still closed buds. No grass: it grows
above the tree line.

    blender -b --factory-startup --python alpine_aster.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "AlpineAster", "alpine_aster"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(23)
G = nk.GROUND
UP = Vector((0, 0, 1))

leafm = nk.plant("AsterLeaf", (0.13, 0.18, 0.1), (0.18, 0.21, 0.14), rough=0.8, vary=0.3)
stemm = nk.plant("AsterStem", (0.15, 0.19, 0.1), (0.2, 0.17, 0.1), rough=0.75)
ray = nk.petal("AsterRay", (0.16, 0.08, 0.6), (0.28, 0.16, 0.88), rough=0.55, sat=1.0, value=0.92)
pale = nk.petal("AsterPale", (0.3, 0.22, 0.62), (0.48, 0.4, 0.8), rough=0.55, sat=1.0, value=0.92)
disc = nk.petal("AsterDisc", (0.55, 0.3, 0.01), (0.95, 0.62, 0.02), rough=0.7, sat=1.0)
budm = nk.petal("AsterBud", (0.14, 0.18, 0.08), (0.25, 0.14, 0.5), rough=0.6, sat=1.0)

pieces = []
rosettes = [Vector((x, y, G)) for x, y in nk.scatter(11, 0.3, seed=4, min_gap=0.1)]

# Rosettes of spoon leaves standing up and arching over, overlapping into a cushion that hides the stems
for k, c in enumerate(rosettes):
    for j in range(8):
        a = j / 8 * math.tau + rnd.uniform(-0.3, 0.3)
        o = Vector((math.cos(a), math.sin(a), 0.0))
        d = (o + UP * rnd.uniform(1.0, 2.2)).normalized()
        pieces.append(kw.leaf("Leaf%d_%d" % (k, j), c + UP * 0.005, d, rnd.uniform(0.07, 0.11),
                              rnd.uniform(0.016, 0.022), leafm, arch=rnd.uniform(0.6, 1.0), power=1.5,
                              twist=rnd.uniform(-25, 25), segments=3, profile="spoon", toward=o))

# Flower heads on short, nearly upright stems from each rosette, most facing the sky
n = 0
for k, c in enumerate(rosettes):
    for j in range(3):
        a = rnd.uniform(0, math.tau)
        off = Vector((math.cos(a), math.sin(a), 0.0)) * rnd.uniform(0.015, 0.06)
        base = c + off * 0.3
        x, y = c.x + off.x, c.y + off.y
        r = math.hypot(x, y)
        out = Vector((x, y, 0.0)).normalized() if r > 0.02 else Vector((1, 0, 0))
        top = Vector((x, y, G + 0.12 + 0.08 * max(0.0, 1.0 - (r / 0.38) ** 2) * rnd.uniform(0.7, 1.15))) + out * 0.03
        mid = base.lerp(top, 0.5) + Vector((rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01), 0.0))
        pieces.append(kw.rod("Stem%d" % n, [base, mid, top], 0.0022, 0.0016, stemm, sides=3))
        axis = (UP + out * rnd.uniform(0.15, 0.5) + Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 0))
                ).normalized()
        if n % 11 == 5:
            # A closed bud, purple showing at its tip
            pieces.append(kw.sausage("Bud%d" % n, top - axis * 0.002, axis, 0.012, 0.0055, budm, sides=6, seed=n))
        else:
            pieces.append(kw.rays("Rays%d" % n, top, axis, 20, rnd.uniform(0.023, 0.027), rnd.uniform(0.0038, 0.0045),
                                  pale if n % 8 == 3 else ray, cup=rnd.uniform(0.04, 0.12),
                                  droop=rnd.uniform(0.0, 0.1), seed=n, inner=0.005))
            pieces.append(kw.dome("Disc%d" % n, top, axis, 0.0085, 0.005, disc, segments=6))
        n += 1

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.1, distance=1.0)
kw.view(SCRIPT, "close", model, PREVIEWS, (0.1, -0.32, G + 0.33), (0.0, 0.0, G + 0.17))
print("[%s] done" % SCRIPT)
