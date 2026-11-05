"""WildRose (forest floor and edges): a rounded thorny bush about a meter tall and 0.8 m across. Fourteen reddish
canes rise from a spreading crown and arch over under their own weight, the outer ones bowing out and down so the
bush is a mound rather than a vase; side shoots carry pinnate leaves of five oval leaflets, and the outside of the
mound is dotted with 30 single pink five-petal roses (paler at the base of each petal, a boss of yellow stamens), a
few pink buds and some glossy red-orange hips left from last year.

    blender -b --factory-startup --python wild_rose.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

NAME, SCRIPT = "WildRose", "wild_rose"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(7)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
HEIGHT, RADIUS = 0.98, 0.38

cane = ks.bark("RoseCane", (0.22, 0.08, 0.04), (0.13, 0.13, 0.05), rough=0.55, grain=60.0, sat=0.95)
thorn = nk.plant("RoseThorn", (0.36, 0.15, 0.07), (0.24, 0.09, 0.04), rough=0.45)
leaf = nk.plant("RoseLeaf", (0.1, 0.18, 0.055), (0.14, 0.21, 0.07), rough=0.55, wax=True, vary=0.3)
young = nk.plant("RoseLeafYoung", (0.2, 0.22, 0.06), (0.25, 0.13, 0.06), rough=0.55)
pink = nk.petal("RosePetal", (0.92, 0.84, 0.6), (0.76, 0.16, 0.36), mid=(0.84, 0.28, 0.48), sat=1.0, value=0.95)
pale = nk.petal("RosePetalPale", (0.95, 0.9, 0.72), (0.86, 0.4, 0.58), mid=(0.9, 0.52, 0.68), sat=1.0, value=0.95)
stamen = nk.petal("RoseStamen", (0.45, 0.42, 0.05), (0.95, 0.72, 0.08), sat=1.0, value=0.95)
hip = nk.plant("RoseHip", (0.8, 0.14, 0.02), (0.62, 0.06, 0.02), rough=0.4, wax=True, sat=1.0, value=1.0)
bud = nk.petal("RoseBud", (0.14, 0.2, 0.05), (0.82, 0.22, 0.45), mid=(0.5, 0.25, 0.25), sat=1.0, value=0.95)

b = ks.Builder("Rose")

# Canes from a spreading crown: the middle ones nearly upright, the outer ones leaning out and arching right over
canes = []
n_canes = 14
for i in range(n_canes):
    a = (i + rnd.uniform(-0.3, 0.3)) / n_canes * math.tau
    lean = rnd.random()
    r0 = 0.02 + 0.13 * lean * rnd.uniform(0.5, 1.0)
    tilt = math.radians(10 + 35 * lean)
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    canes.append(ks.grow(rnd, (r0 * math.cos(a), r0 * math.sin(a), G), d, rnd.uniform(1.0, 1.12) - 0.3 * lean,
                         rnd.uniform(0.006, 0.008), 0.0, segments=6, gravity=1.5 + 1.3 * lean, wander=0.07,
                         arch=True))
ks.fit(canes, RADIUS - 0.06)
shoots = []
for c in canes:
    shoots += ks.branch_out(rnd, c, 7, (0.12, 0.95), (0.08, 0.2), (50, 90), 0.5, segments=1, wander=0.0)
ks.wood(b, cane, canes)
b.lod = 1
ks.wood(b, cane, shoots, sides=(3, 3))
for c in canes:
    for k in range(5):
        ks.thorn(b, thorn, c, rnd.uniform(0.05, 0.75), 0.006, rnd)
b.lod = 0


def depth(p):
    """How far a point is inside the mound's outer surface (an ellipsoid HEIGHT tall and RADIUS wide)."""
    q = math.hypot(p.x / RADIUS, p.y / RADIUS, (p.z - G) / HEIGHT)
    return 1.0 - q


leaves = 0


def rose_leaf(p, d):
    global leaves
    # Leaves deep inside the mound can't be seen; a third of the rest carry the far LOD, grown to cover for the others
    if depth(p) > 0.5 and rnd.random() < 0.5:
        return
    far = rnd.random() < 0.36
    b.lod, b.lod_scale = (0, 1.5) if far else (1, 1.0)
    ks.compound_leaf(b, young if rnd.random() < 0.12 else leaf, p, d, rnd.uniform(0.09, 0.105), 5, 0.045, 0.027, rnd,
                     bend=0.25, spread=62, fold=0.3, profile="oval", taper=0.25)
    b.lod, b.lod_scale = 0, 1.0
    leaves += 1


for c in canes:
    for p, d, tan, s in ks.spiral_points(rnd, c, 4, (0.2, 0.97), (45, 75), lift=0.2):
        rose_leaf(p, d)
for sh in shoots:
    for p, d, tan, s in ks.spiral_points(rnd, sh, 2, (0.35, 1.0), (30, 60), lift=0.2):
        rose_leaf(p, d)


# Flowers on the outside of the mound, facing up and out; hips and buds among them
def outer(sh):
    t = sh.tip
    return t.z - G + 1.2 * math.hypot(t.x, t.y)


order = sorted(shoots, key=outer, reverse=True)
flowers = 0
for k, sh in enumerate(order):
    t, td = sh.tip, sh.tip_dir
    out = Vector((t.x, t.y, 0.0))
    out = out.normalized() if out.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    if k < 27:
        axis = (out * 0.7 + UP + td * 0.3).normalized()
        b.lod_scale = 1.2
        ks.flower(b, pale if rnd.random() < 0.2 else pink, stamen, t + td * 0.008, axis, rnd, petals=5,
                  length=rnd.uniform(0.028, 0.033), width=0.034, cup=0.12, center_r=0.009, center_h=0.004)
        b.lod_scale = 1.0
        flowers += 1
        if k % 3 == 0:
            # A second flower or a bud in the cluster
            p, tan, r, _ = sh.at(0.55)
            side = tan.cross(UP).normalized()
            if k % 2 == 0:
                ks.flower(b, pink, stamen, p + side * 0.02 + UP * 0.01, (side + UP * 1.2).normalized(), rnd,
                          length=0.027, width=0.032)
                flowers += 1
            else:
                ks.berry(b, bud, p + side * 0.012 + UP * 0.012, 0.0055, rnd, sides=5, stretch=1.6,
                         axis=(side * 0.4 + UP).normalized())
    elif k < 34:
        # Hips, hanging a little on their stalks, with a dark crown of dried sepals
        axis = (td + Vector((0, 0, -0.6))).normalized()
        c = t + axis * 0.013
        ks.berry(b, hip, c, 0.0085, rnd, sides=6, stretch=1.35, axis=axis)
        tip = c + axis * 0.0085 * 1.35
        b.lod = 1
        _, u, v = ks.basis(axis)
        for j in range(4):
            a = j / 4 * math.tau
            ks.leaf(b, cane, tip, (axis + (u * math.cos(a) + v * math.sin(a)) * 0.9).normalized(), 0.011, 0.003,
                    fold=0.0, profile="lance")
        b.lod = 0
    elif k < 39:
        ks.berry(b, bud, t + td * 0.01, 0.006, rnd, sides=5, stretch=1.6, axis=(td + UP).normalized())

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] flowers %d, leaves %d" % (SCRIPT, flowers, leaves))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.48, distance=2.3)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.48, distance=2.3)
print("[%s] done" % SCRIPT)
