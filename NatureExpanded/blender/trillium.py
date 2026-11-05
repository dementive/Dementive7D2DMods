"""Trillium (forest floor and edges): a colony of twelve large-flowered trilliums 20 to 35 cm tall. Each a bare stem
topped by a whorl of three broad, pointed, gently drooping leaves folded along the midrib, and above that on a short
stalk one big white flower (8 to 10 cm across) of three broad wavy petals flaring out from a funnel, three narrow green
sepals between them, yellow stamens in the middle. Two flowers are ageing to pink, as they do. No grass.

    blender -b --factory-startup --python trillium.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Trillium", "trillium"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(41)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf = nk.plant("TrilliumLeaf", (0.06, 0.14, 0.035), (0.09, 0.17, 0.05), rough=0.55, vary=0.2)
stalk = nk.plant("TrilliumStem", (0.12, 0.16, 0.06), (0.2, 0.12, 0.08), rough=0.6)
white = nk.petal("TrilliumPetal", (0.55, 0.64, 0.42), (0.92, 0.92, 0.89), mid=(0.88, 0.89, 0.84), sat=1.0, value=0.97)
pink = nk.petal("TrilliumPink", (0.6, 0.3, 0.4), (0.86, 0.5, 0.63), mid=(0.8, 0.44, 0.57), sat=1.0, value=0.95)
sepal = nk.plant("TrilliumSepal", (0.08, 0.16, 0.04), (0.11, 0.18, 0.05), rough=0.6)
stamen = nk.petal("TrilliumStamen", (0.7, 0.6, 0.15), (0.88, 0.7, 0.1), sat=1.0)
pistil = nk.plant("TrilliumPistil", (0.4, 0.45, 0.3), (0.5, 0.55, 0.38))

pieces = []
spots = nk.scatter(12, 0.34, seed=4, min_gap=0.115)
for i, (x, y) in enumerate(spots):
    h = rnd.uniform(0.2, 0.34)
    whorl = h * rnd.uniform(0.62, 0.7)
    lean = Vector((x, y, 0.0)) * 0.15 + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0.0))
    W = Vector((x, y, G + whorl)) + lean
    mid = Vector((x, y, G + whorl * 0.5)) + lean * 0.35
    pieces.append(kf.taper_tube("Stem%d" % i, [(x, y, G), mid, W], (0.0045, 0.0032), stalk, sides=5))
    # The whorl of three broad leaves, held out flat and drooping a little at the tips
    phi = rnd.uniform(0.0, math.tau)
    size = rnd.uniform(0.09, 0.11) * (0.85 + 0.9 * (h - 0.2))
    for k in range(3):
        a = phi + k * math.tau / 3 + rnd.uniform(-0.15, 0.15)
        e = rnd.uniform(0.05, 0.25)
        d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        pieces.append(kf.leaf("Leaf%d_%d" % (i, k), W, d, size * rnd.uniform(0.92, 1.08), size * 0.74, leaf, "ovate",
                              segments=6, bend=0.4, fold=0.22, wave=0.05, waves=1.5, seed=i * 3 + k))
    # The flower on its short stalk, facing up and a little out
    face_a = rnd.uniform(0.0, math.tau)
    face = Vector((math.cos(face_a), math.sin(face_a), 0.0))
    nod = math.radians(rnd.uniform(12.0, 35.0))
    fa = (Z * math.cos(nod) + face * math.sin(nod)).normalized()
    F = W + (Z * 0.9 + face * 0.25).normalized() * (h - whorl - 0.015)
    pieces.append(kf.taper_tube("Pedicel%d" % i, [W, W.lerp(F, 0.5) + face * 0.004, F], (0.0022, 0.0018), stalk,
                                sides=4))
    ph = rnd.uniform(0.0, math.tau)
    petal_len = rnd.uniform(0.06, 0.07)
    pieces += kf.corolla("Sepal%d_" % i, F, fa, 3, petal_len * 0.72, 0.011, sepal, lift=0.15, bend=0.2,
                         profile="lance", segments=3, cols=2, seed=i, phase=ph + math.pi / 3)
    pieces += kf.corolla("Petal%d_" % i, F + fa * 0.002, fa, 3, petal_len, petal_len * 0.66, pink if i in (3, 8) else white,
                         lift=0.42, bend=0.34, profile="obovate", segments=6, cols=3, fold=0.1, wave=0.06, seed=i + 50,
                         phase=ph, jitter=0.04)
    pieces += kf.corolla("Stamen%d_" % i, F + fa * 0.003, fa, 6, 0.014, 0.003, stamen, lift=0.7, profile="linear",
                         segments=2, cols=2, seed=i + 90)
    pieces.append(kf.revolve("Pistil%d" % i, [(0.0, 0.0), (0.003, 0.003), (0.0018, 0.008), (0.0, 0.011)], F, fa,
                             pistil, segments=5))

kf.report(SCRIPT, pieces)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.17, distance=1.25)
print("[%s] done" % SCRIPT)
