"""Barrel cactus (desert): three fishhook barrel cacti (Ferocactus) 28 to 56 cm tall standing together, all leaning a
little the same way as the real ones do toward the sun. Deep green ribbed bodies (14 to 18 ribs, paler crests, a
tan woolly apex), every crest set with areoles 5 cm apart, each with a long red-to-yellow central spine hooked at the
tip and pale radial spines spread round it. A ring of red-orange funnel flowers round each crown, with a few yellow
fruits among them.

    blender -b --factory-startup --python barrel_cactus.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "BarrelCactus", "barrel_cactus"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(4)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

body_mat = kd.skin("BarrelBody", (0.07, 0.15, 0.04), (0.1, 0.17, 0.05), rough=0.45, vary=0.25, scale=5.0,
                   ridges=(0.2, 0.26, 0.13), sat=0.9, value=0.9)
central_mat = nk.petal("BarrelSpine", (0.4, 0.04, 0.02), (0.92, 0.72, 0.3), mid=(0.75, 0.2, 0.05), sat=1.0, value=0.95)
radial_mat = nk.petal("BarrelRadial", (0.5, 0.3, 0.2), (0.9, 0.85, 0.7), sat=0.8, value=0.95)
flower_mat = nk.petal("BarrelFlower", (0.85, 0.07, 0.02), (1.0, 0.36, 0.06), mid=(0.98, 0.16, 0.025), sat=1.0,
                      value=1.0)
center_mat = nk.petal("BarrelStamen", (0.8, 0.55, 0.1), (0.95, 0.8, 0.3), sat=1.0)
fruit_mat = kd.skin("BarrelFruit", (0.8, 0.6, 0.08), (0.65, 0.5, 0.06), rough=0.45, vary=0.2, sat=1.0, value=0.95,
                    base_dark=0.8)

body_b, central_b, radial_b, petal_b, center_b, fruit_b = (kd.Builder() for _ in range(6))

# The compass lean: every barrel tips toward the same side
lean_az = math.radians(205.0)
lean_axis = Vector((-math.sin(lean_az), math.cos(lean_az), 0.0))

barrels = [  # x, y, height, radius, ribs, rows, lean (degrees)
    (-0.07, 0.08, 0.52, 0.19, 18, 8, 9.0),
    (0.24, -0.1, 0.38, 0.155, 16, 7, 13.0),
    (-0.17, -0.27, 0.27, 0.125, 14, 6, 6.0),
]

flowers = 0
for bi, (x, y, h, r, ribs, rows, lean) in enumerate(barrels):
    M = Matrix.Translation((x, y, G)) @ Matrix.Rotation(math.radians(lean), 4, lean_axis) @ \
        Matrix.Rotation(rnd.uniform(0, math.tau), 4, "Z")
    crest = kd.barrel(body_b, h, r, ribs=ribs, rows=rows, depth=0.13, twist=rnd.uniform(-12, 12), matrix=M, seed=bi,
                      dome_power=2.6)

    # Areoles every ~5 cm along each crest, from just above the sand to the crown
    for rib in range(ribs):
        s = rnd.uniform(0.03, 0.08)
        while s < 0.93:
            p, n = crest(rib, s)
            p2, _ = crest(rib, min(0.99, s + 0.01))
            along = (p2 - p).normalized()
            across = n.cross(along).normalized()
            # The long central spine, out and down, hooked at its tip
            d = (n + along * rnd.uniform(-0.7, -0.2) + across * rnd.uniform(-0.2, 0.2)).normalized()
            if s > 0.8:
                d = (n + along * rnd.uniform(0.3, 0.9)).normalized()
            kd.sliver(central_b, p - n * 0.002, d, rnd.uniform(0.045, 0.065) * (0.85 + 0.3 * h), 0.0042, hook=110.0,
                      hook_dir=-along if s <= 0.8 else -Z)
            # Often a second, straight central spreading up and out
            if rnd.random() < 0.6:
                d = (n + along * rnd.uniform(0.1, 0.6) + across * rnd.uniform(-0.6, 0.6)).normalized()
                kd.sliver(central_b, p - n * 0.002, d, rnd.uniform(0.03, 0.045), 0.003)
            # Pale radials spread along the crest
            for sg in (-1.0, 1.0):
                if rnd.random() < 0.8:
                    d = (n * 0.5 + along * sg + across * rnd.uniform(-0.6, 0.6)).normalized()
                    kd.sliver(radial_b, p - n * 0.002, d, rnd.uniform(0.02, 0.035), 0.0016)
            step = 0.046 / (h + 0.05) * (0.75 if s > 0.75 else 1.0)
            s += step * rnd.uniform(0.85, 1.15)

    # A ring of flowers round the crown, fruit among them
    count = (7, 6, 5)[bi]
    nfruit = (2, 2, 1)[bi]
    top = M @ Vector((0.0, 0.0, h))
    up = (M.to_3x3() @ Z).normalized()
    for k in range(count + nfruit):
        a = (k + rnd.uniform(-0.2, 0.2)) / (count + nfruit) * math.tau
        s = rnd.uniform(0.86, 0.92)
        rib = int(a / math.tau * ribs) % ribs
        p, n = crest(rib, s)
        ax = (n * 0.45 + up * 1.0).normalized()
        if k < count:
            head = p + ax * 0.012
            kd.cup_flower(petal_b, head, ax, 11, rnd.uniform(0.046, 0.055) * (0.85 + 0.3 * h), 0.024,
                          widths=(0.4, 1.0, 0.7), cup=rnd.uniform(0.36, 0.5), droop=0.05, seed=flowers, jitter=0.2)
            kd.dome(center_b, head + ax * 0.004, ax, 0.009, 0.012, k=7)
            flowers += 1
        else:
            kd.blob(fruit_b, p + ax * 0.018, ax, 0.014, 0.036, k=7, rings=2, wobble=0.08, rnd=rnd, top_dent=0.08)

pieces = [body_b.obj("Bodies", body_mat, closed=True), central_b.obj("Centrals", central_mat, smooth=False),
          radial_b.obj("Radials", radial_mat, smooth=False), petal_b.obj("Petals", flower_mat),
          center_b.obj("Centers", center_mat), fruit_b.obj("Fruit", fruit_mat, closed=True)]
print("[%s] body %d, centrals %d, radials %d, petals %d triangles, %d flowers" % (
    SCRIPT, body_b.tris(), central_b.tris(), radial_b.tris(), petal_b.tris(), flowers))

model = nk.export(NAME, pieces, MODELS, size=1024)
kd.previews(SCRIPT, model, PREVIEWS, height=0.6, focus=G + 0.28, distance=1.5)
print("[%s] done" % SCRIPT)
