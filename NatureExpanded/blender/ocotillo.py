"""Ocotillo (desert): 12 tall whip canes 1.8 to 2.5 m fanning up and out from one knobby crown, like an opened
fan. Each cane grey-olive and furrowed, tapering from 2 cm to a finger, set all along with grey spines and little
clusters of green leaves in their axils (an ocotillo after rain), and tipped with a 20 cm flame of scarlet tubular
flowers, buds at the very tip. The tips spill well past the block (about 1.6 m across), as the real ones do.

    blender -b --factory-startup --python ocotillo.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "Ocotillo", "ocotillo"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(12)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

cane_mat = kd.skin("OcotilloCane", (0.17, 0.165, 0.105), (0.12, 0.13, 0.085), rough=0.7, vary=0.3, scale=8.0,
                   streaks=0.55, base_dark=0.65)
crown_mat = kd.skin("OcotilloCrown", (0.14, 0.12, 0.08), (0.09, 0.08, 0.06), rough=0.8, streaks=0.4)
spine_mat = nk.petal("OcotilloSpine", (0.22, 0.18, 0.13), (0.55, 0.5, 0.42), sat=0.6, value=0.9)
leaf_mat = nk.plant("OcotilloLeaf", (0.12, 0.22, 0.05), (0.16, 0.24, 0.06), rough=0.6, vary=0.3)
flower_mat = nk.petal("OcotilloFlower", (0.75, 0.025, 0.01), (1.0, 0.16, 0.025), mid=(0.95, 0.05, 0.012), sat=1.0,
                      value=1.0)
bud_mat = nk.petal("OcotilloBud", (0.45, 0.04, 0.02), (0.8, 0.1, 0.03), sat=1.0, value=0.95)

cane_b, crown_b, spine_b, leaf_b, flower_b, bud_b = (kd.Builder() for _ in range(6))

# The knobby crown the canes rise from
kd.tube(crown_b, [(0, 0, G - 0.03), (0.0, 0.0, G + 0.03), (0.0, 0.0, G + 0.07)], [0.085, 0.075, 0.05], sides=9,
        wobble=0.15, rnd=rnd)

CANES = 12
for i in range(CANES):
    a = (i + rnd.uniform(-0.3, 0.3)) / CANES * math.tau
    outer = i % 3 != 0
    tilt = math.radians(rnd.uniform(14, 26) if outer else rnd.uniform(3, 12))
    length = rnd.uniform(1.85, 2.5) * (0.95 if outer else 1.05)
    out = Vector((math.cos(a), math.sin(a), 0.0))
    d0 = (out * math.sin(tilt) + Z * math.cos(tilt)).normalized()
    base = Vector((math.cos(a) * 0.035, math.sin(a) * 0.035, G + 0.03))
    bow = rnd.uniform(0.02, 0.08)
    wig = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 0.02
    panicle = rnd.uniform(0.17, 0.24)
    stem_len = length - panicle
    pts, radii = [], []
    seg = 9
    for k in range(seg + 1):
        s = k / seg
        p = base + d0 * (stem_len * s) + out * (bow * s * s * stem_len * 0.5) + wig * math.sin(math.pi * s * 2.0)
        pts.append(p)
        radii.append(0.019 * (1.0 - s) + 0.0055 * s)
    kd.tube(cane_b, pts, radii, sides=6, cap=False, phase=rnd.uniform(0, 1))

    def at(s):
        """A point along the cane (0 at its foot, 1 where the flowers start) and the direction there."""
        f = s * seg
        k = min(seg - 1, int(f))
        return pts[k].lerp(pts[k + 1], f - k), (pts[k + 1] - pts[k]).normalized(), radii[k] + (radii[k + 1] - radii[k]) * (f - k)

    # Spines spiraling up, a leaf cluster in every other one's axil
    s = rnd.uniform(0.04, 0.07)
    turn = rnd.uniform(0, math.tau)
    node = 0
    while s < 0.97:
        p, d, r = at(s)
        _, sd, up = kd.frame(d)
        turn += 2.4
        o = sd * math.cos(turn) + up * math.sin(turn)
        kd.sliver(spine_b, p + o * (r * 0.7), (o + d * 0.9).normalized(), rnd.uniform(0.014, 0.024), 0.0024)
        if node % 2 == 0 and s < 0.94:
            for j in range(3):
                ld = (o * 1.0 + d * rnd.uniform(0.3, 1.2) + Vector([rnd.uniform(-0.45, 0.45) for _ in range(3)])).normalized()
                kd.sheet(leaf_b, p + o * (r * 0.8), ld, rnd.uniform(0.022, 0.034), rnd.uniform(0.011, 0.016),
                         (0.0, 1.0, 0.45), bend=rnd.uniform(0.0, 0.3), roll=rnd.uniform(-40, 40))
        node += 1
        s += rnd.uniform(0.05, 0.075) / stem_len

    # The flower panicle: the cane goes on as a thin stalk crowded with scarlet tubes, buds at the top
    tip, d, _ = at(1.0)
    curl = (d + Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 0.15))).normalized()
    axis_pts = [tip, tip + d * panicle * 0.5, tip + d * panicle * 0.5 + curl * panicle * 0.5]
    kd.tube(cane_b, axis_pts, [0.0055, 0.0035, 0.0], sides=4, cap=False, t0=0.9, t1=1.0)
    n = rnd.randint(26, 32)
    for k in range(n):
        s = (k + rnd.uniform(0.0, 0.6)) / n
        q = axis_pts[0].lerp(axis_pts[1], s * 2) if s < 0.5 else axis_pts[1].lerp(axis_pts[2], s * 2 - 1)
        ax = d if s < 0.5 else curl
        _, sd, up = kd.frame(ax)
        b = k * 2.39996 + rnd.uniform(-0.3, 0.3)
        o = sd * math.cos(b) + up * math.sin(b)
        if s > 0.8:
            kd.cone(bud_b, q + o * 0.003, (o * 0.6 + ax).normalized(), rnd.uniform(0.012, 0.018), 0.0035, sides=3,
                    roll=rnd.uniform(0, 120))
        else:
            fd = (o * rnd.uniform(0.7, 1.1) + ax * rnd.uniform(0.3, 0.8) - Z * rnd.uniform(0.0, 0.35)).normalized()
            kd.cone(flower_b, q + o * 0.004, fd, rnd.uniform(0.03, 0.036), rnd.uniform(0.0068, 0.0085), sides=3,
                    roll=rnd.uniform(0, 120))

pieces = [cane_b.obj("Canes", cane_mat), crown_b.obj("Crown", crown_mat), spine_b.obj("Spines", spine_mat, smooth=False),
          leaf_b.obj("Leaves", leaf_mat), flower_b.obj("Flowers", flower_mat, smooth=False),
          bud_b.obj("Buds", bud_mat, smooth=False)]
print("[%s] canes %d, spines %d, leaves %d, flowers %d triangles" % (
    SCRIPT, cane_b.tris(), spine_b.tris(), leaf_b.tris(), flower_b.tris() + bud_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=1024)
kd.previews(SCRIPT, model, PREVIEWS, height=2.5, focus=G + 1.2, distance=5.6)
print("[%s] done" % SCRIPT)
