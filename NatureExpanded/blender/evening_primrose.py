"""Evening primrose (desert): a low sprawl 15 to 25 cm high of the desert's white evening primrose. A loose rosette
of long, narrow, wavy-edged grey-green leaves lying out over the sand, and among them 14 big white flowers 7 to 8
cm across on their long floral tubes, each four broad notched petals (veined, faintly yellow at the base) round
yellow stamens and a cross-shaped white stigma; three of them fading to pink and going limp, and a few slender buds.

    blender -b --factory-startup --python evening_primrose.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "EveningPrimrose", "evening_primrose"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(51)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = nk.plant("PrimroseLeaf", (0.15, 0.22, 0.12), (0.2, 0.25, 0.15), rough=0.75, vary=0.3, sat=0.7, value=0.95)
tube_mat = nk.plant("PrimroseTube", (0.42, 0.44, 0.3), (0.5, 0.4, 0.34), rough=0.7, sat=0.8, value=1.0)
white = nk.petal("PrimrosePetal", (0.82, 0.78, 0.4), (0.96, 0.96, 0.93), mid=(0.94, 0.94, 0.88), streaks=0.12,
                 sat=1.0, value=0.97)
pink = nk.petal("PrimroseFaded", (0.85, 0.45, 0.42), (0.95, 0.58, 0.7), mid=(0.93, 0.62, 0.7), streaks=0.12, sat=1.0,
                value=0.95)
stamen_mat = nk.petal("PrimroseStamen", (0.9, 0.8, 0.4), (0.95, 0.7, 0.08), sat=1.0, value=1.0)
stigma_mat = nk.petal("PrimroseStigma", (0.85, 0.85, 0.7), (0.97, 0.97, 0.92), sat=1.0, value=1.0)
center_mat = nk.petal("PrimroseCenter", (0.6, 0.6, 0.2), (0.9, 0.8, 0.3), sat=1.0)
bud_mat = nk.plant("PrimroseBud", (0.25, 0.3, 0.14), (0.45, 0.22, 0.15), rough=0.6, sat=0.9, value=1.0)

leaf_b, tube_b, white_b, pink_b, stamen_b, stigma_b, center_b, bud_b = (kd.Builder() for _ in range(8))

# The rosette of long narrow leaves sprawling over the sand
for k in range(44):
    a = k * 2.39996 + rnd.uniform(-0.25, 0.25)
    out = Vector((math.cos(a), math.sin(a), 0.0))
    f = k / 43
    elev = math.radians(rnd.uniform(8, 30) + 25 * f)
    d = (out * math.cos(elev) + Z * math.sin(elev)).normalized()
    base = out * rnd.uniform(0.0, 0.05) + Vector((0, 0, G + 0.004))
    kd.sheet(leaf_b, base, d, rnd.uniform(0.11, 0.19) * (1.0 - 0.3 * f), rnd.uniform(0.018, 0.026),
             (0.25, 0.75, 1.0, 0.95, 0.75, 0.45, 0.0), bend=rnd.uniform(0.25, 0.55), twist=rnd.uniform(-25, 25),
             wave=0.22, rnd=rnd)


def flower(c, face, mat, petal_b, seed, faded=False):
    r = random.Random(seed)
    if faded:
        kd.cup_flower(petal_b, c, face, 4, r.uniform(0.026, 0.032), 0.032, widths=(0.2, 0.7, 1.0, 0.9, 0.7),
                      cup=0.05, droop=0.55, seed=seed, jitter=0.12, notch=0.06, twist=40.0)
        kd.dome(center_b, c, face, 0.004, 0.004, k=5)
        return
    kd.cup_flower(petal_b, c, face, 4, r.uniform(0.035, 0.04), 0.05, widths=(0.22, 0.8, 1.08, 1.12, 1.0),
                  cup=r.uniform(0.15, 0.26), droop=0.06, seed=seed, jitter=0.03, notch=0.05, twist=6.0)
    kd.dome(center_b, c, face, 0.005, 0.004, k=6)
    _, sd, up = kd.frame(face)
    for j in range(8):
        a = (j + r.uniform(-0.2, 0.2)) / 8 * math.tau
        o = sd * math.cos(a) + up * math.sin(a)
        kd.sliver(stamen_b, c + face * 0.002, (face + o * 0.75).normalized(), r.uniform(0.016, 0.021), 0.0022)
    style = c + face * 0.022
    kd.sliver(stigma_b, c, face, 0.023, 0.0016)
    for j in range(4):
        a = (j + 0.5) / 4 * math.tau + r.uniform(-0.1, 0.1)
        o = sd * math.cos(a) + up * math.sin(a)
        kd.sliver(stigma_b, style, (o + face * 0.25).normalized(), 0.008, 0.0022)


# Flowers on long floral tubes from the crown, facing up and out; three fading pink, a few buds
spots = nk.scatter(20, 0.21, seed=6, min_gap=0.07)
for i, (x, y) in enumerate(spots):
    out = Vector((x, y, 0.0))
    h = rnd.uniform(0.07, 0.16)
    foot = out * 0.2 + Vector((0, 0, G + 0.01))
    top = Vector((x, y, G + h))
    mid = foot.lerp(top, 0.4) + Vector((0, 0, h * 0.18))
    if i >= 17:
        # A slender bud nodding out from the crown
        nod = (out.normalized() * 0.8 + Vector((0, 0, -0.35))).normalized() if out.length > 1e-3 else Vector((1, 0, 0))
        kd.tube(tube_b, [foot, mid, top], 0.0016, sides=3, cap=False)
        kd.blob(bud_b, top + nod * 0.016, nod, 0.0055, 0.032, k=6, rings=2)
        continue
    kd.tube(tube_b, [foot, mid, top], 0.0016, sides=3, cap=False)
    face = (out.normalized() * rnd.uniform(0.25, 0.6) + Z).normalized() if out.length > 1e-3 else Z
    if i in (3, 9, 14):
        flower(top, (face + out * 0.8).normalized(), pink, pink_b, i, faded=True)
    else:
        flower(top, face, white, white_b, i)

pieces = [leaf_b.obj("Leaves", leaf_mat), tube_b.obj("Tubes", tube_mat), white_b.obj("Petals", white),
          pink_b.obj("Faded", pink), stamen_b.obj("Stamens", stamen_mat, smooth=False),
          stigma_b.obj("Stigmas", stigma_mat, smooth=False), center_b.obj("Centers", center_mat),
          bud_b.obj("Buds", bud_mat, closed=True)]
print("[%s] leaves %d, petals %d triangles" % (SCRIPT, leaf_b.tris(), white_b.tris() + pink_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=512)
kd.previews(SCRIPT, model, PREVIEWS, height=0.25, focus=G + 0.1, distance=1.0)
print("[%s] done" % SCRIPT)
