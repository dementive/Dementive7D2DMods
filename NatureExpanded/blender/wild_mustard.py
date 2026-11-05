"""WildMustard (wasteland): a clump of wild mustard, five branching stems 50 to 90 cm ending in 14 loose rounded
clusters of small bright yellow four-petal flowers (open round the sides on short stalks, a knot of green-yellow buds
on top), thin seed pods angling up the stalk below each cluster. Coarse lobed leaves low on the stems, small lance
leaves higher up, and some grass among them.

    blender -b --factory-startup --python wild_mustard.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "WildMustard", "wild_mustard"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(14)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stemm = nk.plant("MustardStem", (0.16, 0.24, 0.09), (0.2, 0.25, 0.12), rough=0.7)
leafm = ww.leaf_mat("MustardLeaf", (0.11, 0.19, 0.06), (0.15, 0.21, 0.08), rib=(0.22, 0.28, 0.12), rough=0.7)
podm = nk.plant("MustardPod", (0.17, 0.27, 0.08), (0.22, 0.28, 0.1), rough=0.6)
petalm = nk.petal("MustardPetal", (0.8, 0.4, 0.0), (0.93, 0.64, 0.0), mid=(0.9, 0.56, 0.0), sat=1.0, value=1.0)
budm = nk.petal("MustardBud", (0.3, 0.38, 0.05), (0.72, 0.62, 0.04), sat=1.0, value=0.9)
grass = nk.grass()

sheets = {k: ww.Sheet("Mustard" + k, m) for k, m in (("Stem", stemm), ("Leaf", leafm), ("Pod", podm),
                                                    ("Petal", petalm), ("Bud", budm))}
count = {"clusters": 0, "flowers": 0}


def cluster(pts, seed, flowers=13):
    """A raceme's top: buds in the middle, open flowers round them on short stalks, pods down the stalk below."""
    r = random.Random(seed)
    tip, axis = ww.along(pts, 1.0)
    axis = (axis + UP * 0.5).normalized()
    for k in range(3):
        out = ww.perpendicular(axis, k * 2.1 + r.uniform(-0.3, 0.3))
        ww.bud(sheets["Bud"], tip + out * 0.003 * (k > 0), (axis + out * 0.35 * (k > 0)).normalized(),
               r.uniform(0.005, 0.007), 0.0026, seed=seed + k)
    for k in range(flowers):
        tier = (k + 0.5) / flowers
        out = ww.perpendicular(axis, k * 2.39996 + r.uniform(-0.3, 0.3))
        c = tip + out * (0.01 + 0.02 * math.sqrt(tier)) - axis * (0.002 + 0.03 * tier)
        base = tip - axis * (0.006 + 0.034 * tier)
        ww.needle(sheets["Stem"], base, c - base, (c - base).length, 0.0016, seed=seed * 3 + k, t_range=(0.7, 1.0))
        # Inner flowers face up, outer ones turn out to the side, so the cluster shows from any angle
        fax = (axis * 0.7 + out * (0.35 + 0.9 * tier)).normalized()
        ww.ring(sheets["Petal"], c, fax, 4, r.uniform(0.011, 0.0125), 0.0105, cup=0.18, droop=0.04, profile="square",
                segments=1, jitter=0.05, spread=0.04, seed=seed * 17 + k)
        count["flowers"] += 1
    # Seed pods angling up the stalk below the flowers
    for k in range(5):
        p, d = ww.along(pts, 0.96 - 0.04 * k - r.uniform(0.0, 0.015))
        out = ww.perpendicular(d, k * 2.2 + r.uniform(-0.4, 0.4))
        ww.leaf(sheets["Pod"], p + out * 0.002, (d + out * 0.55).normalized(), r.uniform(0.024, 0.034), 0.0026,
                profile="taper", segments=1, rib=False, bend=-0.1, seed=seed * 5 + k)
    count["clusters"] += 1


bases = nk.scatter(6, 0.18, seed=6, min_gap=0.06)
for i, (x, y) in enumerate(bases):
    h = rnd.uniform(0.55, 0.88)
    a = math.atan2(y, x) + rnd.uniform(-0.5, 0.5)
    lean = rnd.uniform(0.12, 0.3)
    pts = ww.path((x, y, G), (math.cos(a) * lean, math.sin(a) * lean, 1.0), h, 5, bend=-0.05, wobble=0.05, seed=i)
    ww.stalk(sheets["Stem"], pts, 0.0042, 0.0018)
    cluster(pts, seed=i)
    # Coarse lobed leaves low on the stem, small lance leaves higher up
    for j, s in enumerate((0.06, 0.16, 0.27)):
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, rnd.uniform(0, math.tau))
        ww.leaf(sheets["Leaf"], p, (out + d * 0.35).normalized(), rnd.uniform(0.11, 0.16) * (1.0 - s), 0.06 * (1.0 - s),
                profile="obovate", lobes=2, lobe_depth=0.55, hook=0.3, bend=0.45, fold=0.15, wave=0.004, waves=3,
                twist=rnd.uniform(-25, 25), seed=200 + i * 10 + j)
    for j, s in enumerate((0.42, 0.58)):
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, rnd.uniform(0, math.tau))
        ww.leaf(sheets["Leaf"], p, (out + d * 0.6).normalized(), rnd.uniform(0.04, 0.06), 0.014, profile="lance",
                segments=2, rib=False, bend=0.2, seed=300 + i * 10 + j)
    # Side branches curving up from the middle of the stem, each ending in its own cluster
    for b in range(2 if i < 4 else 1):
        s_b = rnd.uniform(0.38, 0.68)
        fork, fd = ww.along(pts, s_b)
        side = ww.perpendicular(fd, rnd.uniform(0, math.tau))
        blen = rnd.uniform(0.2, 0.32) * (1.0 - s_b * 0.4)
        bpts = ww.path(fork, (fd + side * 0.85).normalized(), blen, 3, bend=-0.35, wobble=0.04, seed=40 + i * 3 + b)
        ww.stalk(sheets["Stem"], bpts, 0.0026, 0.0015, t_range=(0.5, 1.0))
        cluster(bpts, seed=60 + i * 3 + b, flowers=11)
        p, d = ww.along(bpts, 0.1)
        ww.leaf(sheets["Leaf"], p, (ww.perpendicular(d, rnd.uniform(0, math.tau)) + d * 0.6).normalized(), 0.045,
                0.013, profile="lance", segments=2, rib=False, bend=0.2, seed=400 + i * 3 + b)

pieces = ww.build(sheets.values())
for k, (x, y) in enumerate(nk.scatter(4, 0.38, seed=3, min_gap=0.2)):
    pieces += nk.tuft("Grass%d_" % k, (x, y), 6, 0.3, grass, seed=k)

model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.45, distance=1.7)
print("[%s] done (%d clusters, %d flowers)" % (SCRIPT, count["clusters"], count["flowers"]))
