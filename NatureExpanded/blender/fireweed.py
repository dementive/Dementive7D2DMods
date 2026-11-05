"""Fireweed (burnt forest): a stand of seven reddish stems 90 to 130 cm, each ending in a long spike of magenta-pink
four-petal flowers 3 cm across: open ones facing out round the lower half on long thin ovaries, dark sepals between
the petals and a white cross of a stigma in each; a tapering cone of deep pink buds above them, nodding a little at
the tip; and below them the oldest flowers turned to long thin red seed pods, a couple split and spilling white fluff.
Narrow willow-like leaves with pale midribs spiral up the stems. No grass: it's the first thing back after a fire.

    blender -b --factory-startup --python fireweed.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "Fireweed", "fireweed"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(17)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stemm = nk.plant("FireweedStem", (0.24, 0.09, 0.07), (0.16, 0.15, 0.08), rough=0.7, vary=0.3)
leafm = ww.leaf_mat("FireweedLeaf", (0.09, 0.17, 0.05), (0.12, 0.19, 0.07), rib=(0.36, 0.38, 0.28), rough=0.65)
petalm = nk.petal("FireweedPetal", (0.55, 0.05, 0.26), (0.76, 0.09, 0.36), mid=(0.72, 0.06, 0.33), streaks=0.12,
                  sat=1.0, value=0.95)
sepalm = nk.petal("FireweedSepal", (0.2, 0.03, 0.08), (0.38, 0.04, 0.16), sat=1.0, value=0.9)
budm = nk.petal("FireweedBud", (0.25, 0.04, 0.1), (0.55, 0.07, 0.26), sat=1.0, value=0.9)
podm = nk.plant("FireweedPod", (0.28, 0.07, 0.09), (0.2, 0.1, 0.08), rough=0.6, sat=0.95)
fluff = nk.petal("FireweedFluff", (0.78, 0.75, 0.7), (0.96, 0.95, 0.93), sat=0.8, value=1.0)

sheets = {k: ww.Sheet("Fireweed" + k, m) for k, m in (("Stem", stemm), ("Leaf", leafm), ("Petal", petalm),
                                                     ("Sepal", sepalm), ("Bud", budm), ("Pod", podm),
                                                     ("Fluff", fluff))}
count = {"flowers": 0, "buds": 0, "pods": 0}


def flower(at, stem_dir, angle, seed, reach=0.02, size=1.0):
    """An open flower on its long ovary, facing out from the stem."""
    r = random.Random(seed)
    out = ww.perpendicular(stem_dir, angle)
    ovary = (out + Vector(stem_dir) * 0.7).normalized()
    c = Vector(at) + ovary * reach * r.uniform(0.9, 1.1)
    ww.needle(sheets["Pod"], at, c - Vector(at), (c - Vector(at)).length, 0.0026, seed=seed)
    axis = (out + UP * r.uniform(0.3, 0.7)).normalized()
    a0 = r.uniform(0, math.tau)
    ww.ring(sheets["Petal"], c, axis, 4, r.uniform(0.021, 0.023) * size, 0.02 * size, cup=0.18, droop=0.05,
            profile="spoon", segments=2, jitter=0.06, start=a0, seed=seed)
    # Narrow dark sepals between the petals, a white style standing out of the middle
    ww.ring(sheets["Sepal"], c - axis * 0.001, axis, 4, 0.013 * size, 0.003, cup=0.05, profile="needle", segments=1,
            jitter=0.03, start=a0 + math.pi / 4, seed=seed + 1)
    ww.needle(sheets["Fluff"], c, axis, 0.014 * size, 0.003, seed=seed + 2)
    count["flowers"] += 1


def spike(pts, seed):
    """The raceme up the top of a stem: pods, then open flowers, then buds."""
    r = random.Random(seed)
    a = r.uniform(0, math.tau)
    # The oldest flowers, at the bottom, gone to long thin pods angling up; a couple split with white fluff
    for k in range(3):
        a += 2.4
        p, d = ww.along(pts, 0.56 + 0.03 * k)
        out = ww.perpendicular(d, a)
        pd = (out * 0.45 + d).normalized()
        ln = r.uniform(0.05, 0.065)
        ww.leaf(sheets["Pod"], p, pd, ln, 0.0035, profile="taper", segments=2, rib=False, bend=0.05, seed=seed + k)
        count["pods"] += 1
        if k == 0 and seed % 2 == 0:
            # Silky down drooping out of the split pod
            ww.pompom(sheets["Fluff"], p + pd * ln, pd, 0.002, 10, 0.042, 0.0035, cutoff=-0.3, profile="taper",
                      segments=2, bend=0.35, lean_up=0.6, seed=seed + 50)
    # Open flowers spiraling up the middle of the spike
    n_open = 14
    for k in range(n_open):
        a += 2.39996 + r.uniform(-0.25, 0.25)
        f = k / n_open
        p, d = ww.along(pts, 0.64 + 0.22 * f)
        flower(p, d, a, seed * 31 + k, reach=0.026 - 0.012 * f, size=1.0 - 0.2 * f)
    # A tapering cone of buds above, shrinking to the tip
    n_bud = 6
    for k in range(n_bud):
        a += 2.39996
        s = 0.87 + 0.13 * k / n_bud
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, a)
        size = 1.0 - 0.6 * k / n_bud
        ww.bud(sheets["Bud"], p + out * 0.003, (out * 0.5 + d).normalized(), 0.016 * size, 0.0042 * size,
               seed=seed * 7 + k)
        count["buds"] += 1


crowns = nk.scatter(7, 0.2, seed=3, min_gap=0.07)
for i, (x, y) in enumerate(crowns):
    h = rnd.uniform(0.9, 1.3)
    a = math.atan2(y, x) + rnd.uniform(-0.5, 0.5)
    lean = rnd.uniform(0.04, 0.16)
    pts = ww.path((x, y, G), (math.cos(a) * lean, math.sin(a) * lean, 1.0), h * 0.94, 6, bend=-0.02, wobble=0.025,
                  seed=i)
    # The tip nods over a little
    tip_dir = (Vector(pts[-1]) - Vector(pts[-2])).normalized()
    side = ww.perpendicular(tip_dir, rnd.uniform(0, math.tau))
    pts.append(pts[-1] + (tip_dir + side * 0.35).normalized() * h * 0.06)
    ww.stalk(sheets["Stem"], pts, 0.0045, 0.0016)
    spike(pts, seed=i)
    # Narrow willow-like leaves spiraling up the lower half, smaller higher up
    la = rnd.uniform(0, math.tau)
    for j in range(7):
        s = 0.04 + 0.54 * j / 7
        p, d = ww.along(pts, s)
        la += 2.39996
        out = ww.perpendicular(d, la)
        ww.leaf(sheets["Leaf"], p, (out + d * 0.5).normalized(), rnd.uniform(0.13, 0.16) * (1.0 - s * 0.5),
                rnd.uniform(0.022, 0.026) * (1.0 - s * 0.35), profile="willow", segments=3, bend=0.35, fold=0.2,
                twist=rnd.uniform(-20, 20), seed=200 + i * 10 + j)

pieces = ww.build(sheets.values())
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.6, distance=2.1)
print("[%s] done (%d flowers, %d buds, %d pods)" % (SCRIPT, count["flowers"], count["buds"], count["pods"]))
