"""Globemallow (desert): desert globemallow, 7 upright wands 40 to 70 cm rising from a woody base and leaning a
little outward, their upper halves crowded with small apricot-orange cup flowers (five broad petals round a pale
stamen column, about 40 in all) and grey buds toward the tips; soft, crinkled, three-lobed grey-green leaves up the
lower wands and in a tuft at the base.

    blender -b --factory-startup --python globemallow.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "Globemallow", "globemallow"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(41)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("MallowStem", (0.25, 0.27, 0.19), (0.3, 0.28, 0.2), rough=0.85, vary=0.3, sat=0.6, value=1.0)
leaf_mat = nk.plant("MallowLeaf", (0.23, 0.28, 0.19), (0.29, 0.32, 0.24), rough=0.9, vary=0.3, sat=0.55, value=1.0)
petal_mat = nk.petal("MallowPetal", (0.88, 0.2, 0.04), (1.0, 0.45, 0.14), mid=(0.98, 0.33, 0.08), sat=1.0, value=1.0)
column_mat = nk.petal("MallowColumn", (0.85, 0.55, 0.15), (0.95, 0.75, 0.3), sat=1.0, value=1.0)
bud_mat = nk.plant("MallowBud", (0.3, 0.32, 0.22), (0.55, 0.3, 0.12), rough=0.85, sat=0.7, value=1.0)

stem_b, leaf_b, petal_b, column_b, bud_b = (kd.Builder() for _ in range(5))

flowers = 0
WANDS = 7
for i in range(WANDS):
    a = (i + rnd.uniform(-0.3, 0.3)) / WANDS * math.tau
    out = Vector((math.cos(a), math.sin(a), 0.0))
    h = rnd.uniform(0.42, 0.7)
    tilt = math.radians(rnd.uniform(6, 20))
    foot = out * rnd.uniform(0.01, 0.05) + Vector((0, 0, G))
    d = (out * math.sin(tilt) + Z * math.cos(tilt)).normalized()
    pts = []
    for k in range(7):
        s = k / 6
        p = foot + d * (h * s) + out * (0.04 * s * s) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.008 * s
        pts.append(p)
    kd.tube(stem_b, pts, [0.0042 - 0.0025 * k / 6 for k in range(7)], sides=4, cap=False)

    def at(s):
        f = s * 6
        k = min(5, int(f))
        return pts[k].lerp(pts[k + 1], f - k), (pts[k + 1] - pts[k]).normalized()

    # Leaves up the lower wand
    for k in range(rnd.randint(6, 8)):
        s = 0.05 + 0.55 * k / 7 + rnd.uniform(-0.03, 0.03)
        p, dd = at(s)
        b = k * 2.4 + rnd.uniform(-0.3, 0.3)
        _, sd, up = kd.frame(dd)
        o = sd * math.cos(b) + up * math.sin(b)
        stalk_end = p + (o * 0.9 + dd * 0.4).normalized() * 0.018
        kd.tube(stem_b, [p, stalk_end], 0.0012, sides=3, cap=False)
        ld = (o + Z * rnd.uniform(0.1, 0.5)).normalized()
        ln = rnd.uniform(0.042, 0.058) * (1.0 - 0.3 * s)
        kd.lobed_leaf(leaf_b, stalk_end, ld, (Z - ld * ld.z).normalized(), ln, ln * 0.95,
                      lobes=rnd.choice((1, 3)), crinkle=0.2, rnd=rnd)

    # Flowers crowded up the upper half, in ones and twos at each node; buds at the tip
    s = rnd.uniform(0.5, 0.56)
    node = 0
    while s < 0.98:
        p, dd = at(s)
        _, sd, up = kd.frame(dd)
        b = node * 2.4 + rnd.uniform(-0.3, 0.3)
        if s > 0.86:
            o = sd * math.cos(b) + up * math.sin(b)
            kd.blob(bud_b, p + o * 0.006, (o * 0.4 + dd).normalized(), 0.0045, 0.011, k=4, rings=2)
        else:
            for j in range(rnd.choice((1, 1, 1, 2))):
                bb = b + j * math.pi
                o = sd * math.cos(bb) + up * math.sin(bb)
                c = p + o * rnd.uniform(0.008, 0.014) + dd * 0.004
                face = (o * rnd.uniform(0.8, 1.2) + dd * 0.6 + Z * 0.45).normalized()
                kd.cup_flower(petal_b, c, face, 5, rnd.uniform(0.016, 0.019), 0.019, widths=(0.3, 0.9, 1.0, 0.75),
                              cup=rnd.uniform(0.22, 0.36), droop=0.05, seed=flowers, jitter=0.08)
                kd.dome(column_b, c, face, 0.0028, 0.008, k=4)
                flowers += 1
        node += 1
        s += rnd.uniform(0.055, 0.07) / (h / 0.55)

# A tuft of leaves at the base
for k in range(16):
    a = k * 2.4 + rnd.uniform(-0.2, 0.2)
    o = Vector((math.cos(a), math.sin(a), 0.0))
    p = o * rnd.uniform(0.02, 0.05) + Vector((0, 0, G + 0.01))
    ld = (o + Z * rnd.uniform(0.3, 0.8)).normalized()
    ln = rnd.uniform(0.05, 0.068)
    kd.lobed_leaf(leaf_b, p, ld, (Z - ld * ld.z).normalized(), ln, ln * 0.95, lobes=rnd.choice((1, 3)), crinkle=0.2,
                  rnd=rnd)

pieces = [stem_b.obj("Stems", stem_mat), leaf_b.obj("Leaves", leaf_mat), petal_b.obj("Petals", petal_mat),
          column_b.obj("Columns", column_mat), bud_b.obj("Buds", bud_mat, closed=True)]
print("[%s] %d flowers; stems %d, leaves %d, petals %d, buds %d triangles" % (
    SCRIPT, flowers, stem_b.tris(), leaf_b.tris(), petal_b.tris(), bud_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=512)
kd.previews(SCRIPT, model, PREVIEWS, height=0.7, focus=G + 0.33, distance=1.5)
print("[%s] done" % SCRIPT)
