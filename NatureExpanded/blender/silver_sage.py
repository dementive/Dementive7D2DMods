"""Silver sage (wasteland): a soft round mound 40 to 60 cm of white sagebrush, 32 felted silver-grey stems bowing out
from one crown into a dome, each crowded to the tip with soft drooping woolly lance leaves (silver at the tips, greyer
toward the stem), and five stems in the middle rising over the mound into narrow branched spikes of tiny pale yellow
flower heads. No grass: it
grows on dry wasteland.

    blender -b --factory-startup --python silver_sage.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "SilverSage", "silver_sage"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(37)
G = nk.GROUND
UP = Vector((0, 0, 1))
R = 0.42

leafm = nk.plant("SageLeaf", (0.46, 0.5, 0.44), (0.38, 0.42, 0.37), rough=0.92, vary=0.25, sat=0.55, value=0.95)
stemm = nk.plant("SageStem", (0.4, 0.42, 0.37), (0.3, 0.3, 0.26), rough=0.9, sat=0.6)
flowerm = nk.petal("SageFlower", (0.74, 0.67, 0.3), (0.95, 0.88, 0.5), rough=0.85, vary=0.12, sat=0.95)

pieces = []


def point_on(pts, s):
    """The point a fraction `s` of the way along a three-point stem."""
    if s < 0.5:
        return pts[0].lerp(pts[1], s * 2.0)
    return pts[1].lerp(pts[2], (s - 0.5) * 2.0)


bases = nk.scatter(32, 0.09, seed=2, min_gap=0.012)
tips = nk.scatter(32, 0.36, seed=5, min_gap=0.075)
# Pair each stem's base with the tip on its own side, so the stems arch out instead of crossing
tips.sort(key=lambda p: math.atan2(p[1], p[0]))
bases.sort(key=lambda p: math.atan2(p[1], p[0]))
centre = sorted(range(32), key=lambda k: math.hypot(*tips[k]))[:5]
for i, ((bx, by), (x, y)) in enumerate(zip(bases, tips)):
    r = math.hypot(x, y)
    flowering = i in centre
    top = Vector((x, y, G + 0.12 + 0.34 * max(0.0, 1.0 - (r / R) ** 2) ** 0.6 * rnd.uniform(0.9, 1.06)))
    base = Vector((bx, by, G))
    # Bowed out: the middle of the stem is pushed outward and up, so the clump is a dome, not a vase
    mid = base.lerp(top, 0.5) + Vector((x, y, 0.0)) * 0.25 + UP * 0.05
    pts = [base, mid, top]
    pieces.append(kw.rod("Stem%d" % i, pts, 0.0028, 0.0012, stemm, sides=3))

    # Felted lance leaves crowded up the stem, longest low down, drooping softly
    count = 14
    for k in range(count):
        s = 0.16 + 0.82 * k / (count - 1)
        at = point_on(pts, s)
        d_stem = (pts[2] - pts[1]).normalized() if s > 0.5 else (pts[1] - pts[0]).normalized()
        a = i * 1.3 + k * 2.39996 + rnd.uniform(-0.3, 0.3)
        side = kw._perp(d_stem)
        up = d_stem.cross(side)
        o = side * math.cos(a) + up * math.sin(a)
        sp = math.radians(rnd.uniform(30, 55))
        d = (d_stem * math.cos(sp) + o * math.sin(sp)).normalized()
        o.z = 0.0
        pieces.append(kw.leaf("Leaf%d_%d" % (i, k), at, d, rnd.uniform(0.06, 0.09) * (1.2 - 0.5 * s),
                              rnd.uniform(0.017, 0.024) * (1.1 - 0.3 * s), leafm, arch=rnd.uniform(0.4, 0.85),
                              power=1.5, twist=rnd.uniform(-30, 30), segments=3, profile="lance",
                              toward=o if o.length > 1e-3 else None))

    if flowering:
        # The stem goes on up over the mound into a narrow, nodding, branched spike crowded with tiny pale yellow heads
        sl = rnd.uniform(0.12, 0.17)
        n = (UP + Vector((x, y, 0.0)) * 0.6).normalized()
        nod = Vector((x, y, 0.0)).normalized() * 0.04 if r > 0.02 else Vector((0.03, 0.0, 0.0))
        spine = [top, top + n * (sl * 0.55), top + n * sl + nod]
        pieces.append(kw.rod("Spike%d" % i, spine, 0.0018, 0.0008, flowerm, sides=3))
        pieces.append(kw.florets("Heads%d" % i, [spine[0] + n * (sl * 0.12), spine[1], spine[2]], 30,
                                 rnd.uniform(0.009, 0.011), flowerm, seed=i, out=0.5, nod=0.05))
        for j in range(3):
            at = top + n * (sl * (0.15 + 0.15 * j))
            b = Vector((math.cos(i + j * 2.1), math.sin(i + j * 2.1), 0.0))
            end = at + (n + b * 0.9).normalized() * rnd.uniform(0.05, 0.07) - UP * 0.01
            pieces.append(kw.rod("Arm%d_%d" % (i, j), [at, end], 0.0011, 0.0007, flowerm, sides=3))
            pieces.append(kw.florets("ArmHeads%d_%d" % (i, j), [at.lerp(end, 0.25), end], 10, 0.009, flowerm,
                                     seed=i * 7 + j, out=0.5, nod=0.05))

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.25, distance=1.45)
kw.view(SCRIPT, "close", model, PREVIEWS, (0.1, -0.45, G + 0.75), (0.0, -0.03, G + 0.48))
print("[%s] done" % SCRIPT)
