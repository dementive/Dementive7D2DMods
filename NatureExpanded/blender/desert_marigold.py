"""Desert marigold (desert): a woolly, pale grey-green mound about 15 cm high and 50 cm across of deeply lobed
leaves, and held just above it on thin woolly stems, 20 to 30 cm up, 23 bright yellow daisies 5 cm across (14 broad rays notched at their
tips round a golden disc), a couple of spent ones gone papery and pale, and a few nodding buds.

    blender -b --factory-startup --python desert_marigold.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "DesertMarigold", "desert_marigold"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(31)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = nk.plant("MarigoldLeaf", (0.36, 0.41, 0.31), (0.44, 0.47, 0.38), rough=0.95, vary=0.3, sat=0.45, value=1.0)
stem_mat = nk.plant("MarigoldStem", (0.3, 0.34, 0.26), (0.36, 0.38, 0.31), rough=0.9, sat=0.5, value=1.0)
ray_mat = nk.petal("MarigoldRay", (0.95, 0.7, 0.02), (1.0, 0.86, 0.1), mid=(1.0, 0.8, 0.04), sat=1.0, value=1.0)
disc_mat = nk.petal("MarigoldDisc", (0.75, 0.48, 0.02), (0.95, 0.72, 0.05), sat=1.0, value=0.95)
spent_mat = nk.petal("MarigoldSpent", (0.6, 0.52, 0.3), (0.85, 0.8, 0.6), sat=0.8, value=0.95)
bud_mat = nk.plant("MarigoldBud", (0.3, 0.32, 0.18), (0.55, 0.45, 0.1), rough=0.8, sat=0.8, value=1.0)

leaf_b, stem_b, ray_b, disc_b, spent_b, bud_b = (kd.Builder() for _ in range(6))

# The woolly mound: small lobed leaves laid over a low dome, each facing out of it, so it reads as one soft cushion
MOUND_R, MOUND_H = 0.21, 0.13
for k in range(62):
    u = (k + 0.5) / 62
    theta = math.radians(8 + 80 * math.sqrt(u))
    phi = k * 2.39996 + rnd.uniform(-0.15, 0.15)
    out = Vector((math.cos(phi), math.sin(phi), 0.0))
    p = out * (MOUND_R * math.sin(theta)) + Vector((0, 0, G + MOUND_H * math.cos(theta)))
    nrm = (out * (math.sin(theta) / MOUND_R) + Z * (math.cos(theta) / MOUND_H)).normalized()
    d = (out * 0.9 + nrm * 0.5 + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0.0))).normalized()
    ln = rnd.uniform(0.08, 0.115)
    kd.lobed_leaf(leaf_b, p - d * ln * 0.45 - nrm * 0.01, d, nrm, ln, ln * rnd.uniform(0.6, 0.75), lobes=5,
                  crinkle=0.1, rnd=rnd)

# Flower stems and heads
heads = []
pts = nk.scatter(28, 0.18, seed=4, min_gap=0.042)
for i, (x, y) in enumerate(pts):
    h = rnd.uniform(0.2, 0.3)
    lean = Vector((x, y, 0.0)) * rnd.uniform(0.3, 0.6) + Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0))
    foot = Vector((x * 0.5, y * 0.5, G + 0.05))
    top = Vector((x, y, G + h)) + lean
    mid = foot.lerp(top, 0.55) + Vector((rnd.uniform(-0.015, 0.015), rnd.uniform(-0.015, 0.015), 0.0))
    if i >= 25:
        # A nodding bud
        hook = top + Vector((lean.x, lean.y, 0.0)).normalized() * 0.02 + Vector((0, 0, -0.015))
        kd.tube(stem_b, [foot, mid, top, hook], 0.0018, sides=3, cap=False)
        kd.blob(bud_b, hook + Vector((0, 0, -0.006)), (hook - top).normalized(), 0.008, 0.016, k=6, rings=2)
        continue
    kd.tube(stem_b, [foot, mid, top], 0.0019, sides=3, cap=False)
    face = (Vector((lean.x, lean.y, 0.0)) * 1.4 + Z).normalized()
    if i >= 23:
        # Spent: papery rays turned down round a seedy disc
        kd.cup_flower(spent_b, top, face, 14, 0.017, 0.008, widths=(0.4, 1.0, 0.7), cup=-0.1, droop=0.7, seed=i,
                      jitter=0.25)
        kd.dome(disc_b, top, face, 0.007, 0.007, k=6)
        continue
    kd.cup_flower(ray_b, top, face, 14, rnd.uniform(0.022, 0.026), 0.0125, widths=(0.45, 1.0, 0.95), cup=0.06,
                  droop=0.18, seed=i, jitter=0.18, notch=0.12)
    kd.dome(disc_b, top + face * 0.001, face, 0.0075, 0.005, k=7, ring2=True)
    heads.append(top)

pieces = [leaf_b.obj("Leaves", leaf_mat), stem_b.obj("Stems", stem_mat), ray_b.obj("Rays", ray_mat),
          disc_b.obj("Discs", disc_mat), spent_b.obj("Spent", spent_mat), bud_b.obj("Buds", bud_mat, closed=True)]
print("[%s] %d heads; leaves %d, stems %d, rays %d triangles" % (SCRIPT, len(heads), leaf_b.tris(), stem_b.tris(),
                                                             ray_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=512)
kd.previews(SCRIPT, model, PREVIEWS, height=0.35, focus=G + 0.17, distance=1.1)
print("[%s] done" % SCRIPT)
