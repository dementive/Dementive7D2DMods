"""Agave bloom (desert): a Parry's agave in its once-in-a-lifetime flowering. A tight artichoke rosette 0.8 m across
of 32 thick, cupped, blue-grey leaves (dark hooked teeth along their edges, a long black spine at each tip; the
outermost few yellowing and slumping, as they do once the plant flowers), and from its heart a 2.8 m stalk with
papery bracts low down and 12 branching arms near the top, each turning up at its end into a dense clump of yellow
flowers with long stamens, red buds still closed at the very top.

    blender -b --factory-startup --python agave_bloom.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "AgaveBloom", "agave_bloom"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(21)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = kd.skin("AgaveLeaf", (0.2, 0.27, 0.27), (0.16, 0.24, 0.19), rough=0.6, vary=0.3, scale=4.0, sat=0.8,
                   value=0.92, base_dark=0.75)
old_mat = kd.skin("AgaveLeafOld", (0.3, 0.29, 0.15), (0.24, 0.2, 0.1), rough=0.7, vary=0.35, scale=5.0, sat=0.8,
                  value=0.9, base_dark=0.8)
tooth_mat = nk.petal("AgaveTooth", (0.22, 0.1, 0.05), (0.06, 0.03, 0.02), sat=0.9, value=0.9)
stalk_mat = kd.skin("AgaveStalk", (0.12, 0.14, 0.06), (0.17, 0.11, 0.05), rough=0.6, vary=0.35, scale=3.0,
                    streaks=0.3, base_dark=0.85)
bract_mat = nk.petal("AgaveBract", (0.3, 0.25, 0.12), (0.45, 0.36, 0.22), sat=0.8, value=0.9)
flower_mat = nk.petal("AgaveFlower", (0.5, 0.45, 0.05), (1.0, 0.82, 0.1), mid=(0.95, 0.72, 0.06), sat=1.0, value=1.0)
stamen_mat = nk.petal("AgaveStamen", (0.95, 0.85, 0.3), (0.85, 0.55, 0.08), sat=1.0, value=1.0)
bud_mat = nk.petal("AgaveBud", (0.55, 0.12, 0.03), (0.85, 0.38, 0.06), sat=1.0, value=0.95)
clump_mat = nk.petal("AgaveClump", (0.55, 0.45, 0.05), (0.92, 0.74, 0.1), sat=1.0, value=1.0)

leaf_b, old_b, tooth_b, stalk_b, bract_b, flower_b, stamen_b, bud_b, clump_b = (kd.Builder() for _ in range(9))

# ---------------------------------------------------------------- the rosette

LEAVES = 36
for k in range(LEAVES):
    f = k / (LEAVES - 1)                         # 0 outermost (oldest) to 1 innermost
    az = k * 2.39996 + rnd.uniform(-0.08, 0.08)
    old = k < 3
    elev = math.radians(15 + 72 * f ** 0.85 + rnd.uniform(-4, 4) - (6 if old else 0))
    length = (0.4 - 0.17 * f) * rnd.uniform(0.92, 1.06)
    width = (0.14 - 0.04 * f) * rnd.uniform(0.92, 1.08)
    out = Vector((math.cos(az), math.sin(az), 0.0))
    d = (out * math.cos(elev) + Z * math.sin(elev)).normalized()
    base = out * (0.08 * (1.0 - f) + 0.015) + Vector((0.0, 0.0, G + 0.015 + 0.1 * f))
    incurve = (-0.18 if old else 0.12 + 0.25 * f) + rnd.uniform(-0.05, 0.05)
    kd.agave_leaf(old_b if old else leaf_b, tooth_b, base, d, length, width, 0.034 - 0.008 * f, incurve=incurve,
                  channel=0.3, rows=6, teeth=8 if f < 0.7 else 5, tooth=0.007, spine=0.03 - 0.008 * f, seed=k,
                  roll=rnd.uniform(-6, 6))

# ---------------------------------------------------------------- the flower stalk

lean = Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), 0.0))
H = 2.8
stalk_pts, stalk_r = [], []
SEG = 12
for i in range(SEG + 1):
    s = i / SEG
    p = Vector((0.0, 0.0, G + 0.06 + (H - 0.06) * s)) + lean * (s * s * 3.0)
    stalk_pts.append(p)
    stalk_r.append(0.05 * (1.0 - s) + 0.012 * s)
kd.tube(stalk_b, stalk_pts, stalk_r, sides=8, cap=True)


def along(s):
    f = s * SEG
    i = min(SEG - 1, int(f))
    return stalk_pts[i].lerp(stalk_pts[i + 1], f - i), stalk_r[i] + (stalk_r[i + 1] - stalk_r[i]) * (f - i)


# Papery bracts clasping the lower stalk
for i in range(7):
    s = 0.08 + i * 0.075
    p, r = along(s)
    a = i * 2.39996
    o = Vector((math.cos(a), math.sin(a), 0.0))
    kd.sheet(bract_b, p + o * r * 0.9, (o * 0.35 + Z).normalized(), 0.08 - 0.006 * i, 0.045 - 0.003 * i,
             (1.0, 0.7, 0.0), bend=-0.1, toward=-o, side=o.cross(Z))


def flower_clump(c, up, size, budding, seed):
    """A dense clump of upright tubular flowers (or red buds) with long stamens, on a little cushion."""
    r = random.Random(seed)
    kd.blob(clump_b, c, up, size * 0.42, size * 0.35, k=6, rings=2, wobble=0.15, rnd=r)
    _, sd, ov = kd.frame(up)
    n = 18
    for j in range(n):
        a = j * 2.39996 + r.uniform(-0.2, 0.2)
        rr = size * 0.45 * math.sqrt((j + 0.5) / n)
        o = sd * math.cos(a) + ov * math.sin(a)
        p = c + o * rr + up * (size * 0.12)
        fd = (up + o * (rr / size) * 1.6 + Vector([r.uniform(-0.15, 0.15) for _ in range(3)])).normalized()
        if budding:
            kd.cone(bud_b, p, fd, size * r.uniform(0.32, 0.45), size * 0.075, sides=3, roll=r.uniform(0, 120))
            continue
        kd.cone(flower_b, p, fd, size * r.uniform(0.38, 0.48), size * 0.085, sides=3, flare=0.5,
                roll=r.uniform(0, 120))
        tip = p + fd * size * 0.4
        for _ in range(2):
            sd2 = (fd + Vector([r.uniform(-0.3, 0.3) for _ in range(3)])).normalized()
            kd.sliver(stamen_b, tip, sd2, size * r.uniform(0.35, 0.55), 0.0045)


# Branching arms near the top, each turning up into a clump; buds at the tip of the stalk
ARMS = 12
for i in range(ARMS):
    f = i / (ARMS - 1)
    s = 0.6 + 0.34 * f
    p, r = along(s)
    a = i * 2.39996 + rnd.uniform(-0.2, 0.2)
    o = Vector((math.cos(a), math.sin(a), 0.0))
    reach = (0.38 - 0.22 * f) * rnd.uniform(0.9, 1.1)
    p1 = p + o * (reach * 0.55) + Z * (reach * 0.12)
    p2 = p1 + o * (reach * 0.4) + Z * (reach * 0.28)
    kd.tube(stalk_b, [p, p1, p2], [r * 0.55, 0.008, 0.006], sides=5, cap=True)
    up = (Z * 1.0 + o * 0.35).normalized()
    flower_clump(p2 + up * 0.01, up, rnd.uniform(0.15, 0.18) * (1.0 - 0.3 * f), budding=f > 0.9, seed=i)
top, _ = along(1.0)
flower_clump(top + Z * 0.005, Z, 0.09, budding=True, seed=99)

pieces = [leaf_b.obj("Leaves", leaf_mat, closed=True), old_b.obj("OldLeaves", old_mat, closed=True),
          tooth_b.obj("Teeth", tooth_mat, smooth=False), stalk_b.obj("Stalk", stalk_mat),
          bract_b.obj("Bracts", bract_mat), flower_b.obj("Flowers", flower_mat, smooth=False),
          stamen_b.obj("Stamens", stamen_mat, smooth=False), bud_b.obj("Buds", bud_mat, smooth=False),
          clump_b.obj("Clumps", clump_mat, closed=True)]
print("[%s] leaves %d, teeth %d, stalk %d, flowers %d triangles" % (
    SCRIPT, leaf_b.tris() + old_b.tris(), tooth_b.tris(), stalk_b.tris(),
    flower_b.tris() + stamen_b.tris() + bud_b.tris() + clump_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=1024)
kd.previews(SCRIPT, model, PREVIEWS, height=2.9, focus=G + 1.45, distance=6.4)
print("[%s] done" % SCRIPT)
