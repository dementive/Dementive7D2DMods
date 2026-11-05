"""Snowdrop (snow): four little clumps of snowdrops, 26 in all, 11 to 16 cm. Each a single nodding white bell on an
arched stem: a green ovary at the top, three pure white outer tepals hanging and flaring round a short inner cup of
three tepals tipped green, a papery spathe at the arch; each plant with a pair of narrow grey-green strap leaves. No
grass.

    blender -b --factory-startup --python snowdrop.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Snowdrop", "snowdrop"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(71)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = nk.plant("SnowdropLeaf", (0.1, 0.17, 0.1), (0.13, 0.2, 0.13), rough=0.6, vary=0.2)
stem_mat = nk.plant("SnowdropStem", (0.1, 0.18, 0.08), (0.14, 0.2, 0.1), rough=0.6)
tepal = nk.petal("SnowdropTepal", (0.78, 0.85, 0.72), (0.96, 0.96, 0.94), mid=(0.95, 0.95, 0.93), sat=1.0, value=1.0)
inner = nk.petal("SnowdropInner", (0.9, 0.92, 0.88), (0.1, 0.4, 0.08), mid=(0.9, 0.92, 0.88), sat=1.0, value=0.95)
ovary_mat = nk.plant("SnowdropOvary", (0.12, 0.25, 0.08), (0.16, 0.28, 0.1), rough=0.5)
spathe_mat = nk.plant("SnowdropSpathe", (0.45, 0.5, 0.35), (0.6, 0.62, 0.5), rough=0.7)

pieces = []
CLUMPS = (((-0.15, 0.1), 7), ((0.13, 0.14), 6), ((0.05, -0.15), 7), ((-0.19, -0.16), 6))
i = 0
for (cx, cy), count in CLUMPS:
    for p in nk.scatter(count, 0.065, seed=i + 3, min_gap=0.022):
        x, y = cx + p[0], cy + p[1]
        base = Vector((x, y, G))
        h = rnd.uniform(0.11, 0.16)
        # Nod away from the clump's middle, give or take
        az = math.atan2(p[1], p[0]) + rnd.uniform(-1.0, 1.0)
        out = Vector((math.cos(az), math.sin(az), 0.0))
        top = base + out * 0.008 + Z * h
        pts = [base, base + out * 0.003 + Z * h * 0.5, top, top + out * 0.008 + Z * 0.003,
               top + out * 0.015 - Z * 0.006]
        pieces.append(kf.taper_tube("Stem%d" % i, pts, [0.0019, 0.0017, 0.0014, 0.0009, 0.0008], stem_mat, sides=4))
        pieces.append(kf.leaf("Spathe%d" % i, top, out * 0.3 + Z, 0.018, 0.005, spathe_mat, "lance", segments=2,
                              bend=0.1, cols=2, seed=i))
        # The flower, hanging from the end of the arch
        fa = (out * rnd.uniform(0.45, 0.8) - Z).normalized()
        P = pts[-1]
        pieces.append(kf.revolve("Ovary%d" % i, [(0.0, 0.0), (0.0028, 0.002), (0.0032, 0.005), (0.0, 0.008)], P, fa,
                                 ovary_mat, segments=5))
        F = P + fa * 0.0075
        ph = rnd.uniform(0.0, math.tau)
        L = rnd.uniform(0.029, 0.034)
        pieces += kf.corolla("Tepal%d_" % i, F, fa, 3, L, L * 0.46, tepal, lift=rnd.uniform(0.38, 0.6), bend=0.12,
                             profile="obovate", segments=4, cols=3, fold=0.25, seed=i, phase=ph, jitter=0.05)
        pieces += kf.corolla("Inner%d_" % i, F + fa * 0.001, fa, 3, L * 0.42, L * 0.3, inner, lift=0.88,
                             profile="obovate", segments=3, cols=2, seed=i + 100, phase=ph + math.pi / 3, jitter=0.03)
        # A pair of strap leaves
        for k in range(2):
            la = az + math.pi * 0.5 + k * math.pi + rnd.uniform(-0.6, 0.6)
            d = Vector((math.cos(la) * 0.4, math.sin(la) * 0.4, 1.0))
            pieces.append(kf.leaf("Leaf%d_%d" % (i, k), base + Vector((math.cos(la), math.sin(la), 0.0)) * 0.002, d,
                                  h * rnd.uniform(0.55, 0.8), rnd.uniform(0.009, 0.012), leaf_mat, "strap",
                                  segments=5, bend=rnd.uniform(0.2, 0.45), twist=rnd.uniform(-25.0, 25.0), cols=2,
                                  seed=i * 2 + k))
        i += 1

kf.report(SCRIPT, pieces)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.08, distance=0.85)
print("[%s] done" % SCRIPT)
