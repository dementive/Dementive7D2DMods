"""Blue flag iris (water's edge): a clump of four fans of stiff grey-green sword leaves 40 to 70 cm, the outer ones
curving out like scimitars and a couple broken over, and seven stalks 50 to 80 cm holding eleven violet-blue irises
about 12 cm across, facing up and out: three broad falls spreading and turning down (a yellow throat and a white,
purple-veined patch at their base), three narrower standards held up between them, three pale style arms over the
falls. A few rolled violet buds in green spathes. No grass: it grows in water.

    blender -b --factory-startup --python blue_flag_iris.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "BlueFlagIris", "blue_flag_iris"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(11)
G = nk.GROUND
UP = Vector((0, 0, 1))

leafm = nk.plant("IrisLeaf", (0.14, 0.2, 0.13), (0.17, 0.23, 0.16), rough=0.5, vary=0.25)
drym = nk.plant("IrisDry", (0.3, 0.25, 0.13), (0.2, 0.16, 0.08), rough=0.8, vary=0.3, sat=0.8)
stalkm = nk.plant("IrisStalk", (0.15, 0.22, 0.12), (0.12, 0.17, 0.09), rough=0.55)
spathem = nk.plant("IrisSpathe", (0.16, 0.22, 0.12), (0.3, 0.28, 0.15), rough=0.6)
fall = kw.throat_petal("IrisFall", (0.85, 0.6, 0.04), (0.78, 0.75, 0.85), (0.17, 0.09, 0.62), tip=(0.12, 0.06, 0.5),
                       throat_end=0.14, white_end=0.32, streaks=0.5)
standard = nk.petal("IrisStandard", (0.2, 0.11, 0.55), (0.24, 0.13, 0.68), rough=0.5, sat=1.0, value=0.92)
style = nk.petal("IrisStyle", (0.5, 0.45, 0.75), (0.36, 0.28, 0.7), rough=0.5, sat=1.0, value=0.92)
budm = nk.petal("IrisBud", (0.14, 0.2, 0.1), (0.18, 0.08, 0.52), mid=(0.2, 0.12, 0.45), rough=0.5, sat=1.0)

pieces = []

# Fans of sword leaves, each flat in its own plane
for k, (x, y) in enumerate(nk.scatter(4, 0.12, seed=3, min_gap=0.09)):
    phi = rnd.uniform(0, math.tau)
    f = Vector((math.cos(phi), math.sin(phi), 0.0))
    n = rnd.randint(6, 7)
    for j in range(n):
        u = (j / (n - 1)) * 2.0 - 1.0  # -1 .. 1 across the fan
        theta = math.radians(u * 22.0 + rnd.uniform(-3, 3))
        d = UP * math.cos(theta) + f * math.sin(theta)
        outer = abs(u) > 0.6
        length = rnd.uniform(0.36, 0.5) if outer else rnd.uniform(0.5, 0.68)
        base = Vector((x, y, G)) + f * (u * 0.018)
        side = f if u >= 0 else -f
        pieces.append(kw.leaf("Leaf%d_%d" % (k, j), base, d, length, rnd.uniform(0.02, 0.026), leafm,
                              arch=rnd.uniform(0.08, 0.3) * (1.6 if outer else 1.0), power=2.0,
                              twist=rnd.uniform(-15, 15), segments=7, profile="sword",
                              roll=90.0 + rnd.uniform(-12, 12), toward=side))
    # One leaf broken and hanging over
    t = Vector((math.cos(phi + 1.6), math.sin(phi + 1.6), 0.0))
    pieces.append(kw.leaf("Broken%d" % k, (x, y, G), (UP + t * 0.15).normalized(), rnd.uniform(0.45, 0.6), 0.022,
                          drym if k % 2 else leafm, arch=rnd.uniform(1.3, 1.7), power=2.5, segments=7,
                          profile="sword", toward=t))

# Flower stalks among the fans
heads = []
for i, (x, y) in enumerate(nk.scatter(7, 0.17, seed=5, min_gap=0.06)):
    h = rnd.uniform(0.5, 0.8)
    out = Vector((x, y, 0.0))
    if out.length < 0.03:
        out = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0))
    out.normalize()
    base = Vector((x, y, G))
    top = base + UP * h + out * rnd.uniform(0.03, 0.07)
    mid = base + UP * (h * 0.5) + out * 0.015 + Vector((rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01), 0))
    pieces.append(kw.rod("Stalk%d" % i, [base, mid, top], 0.0055, 0.0035, stalkm, sides=4))
    axis = (UP + out * rnd.uniform(0.35, 0.7)).normalized()
    # The spathe wrapping the base of the flower
    pieces.append(kw.leaf("Spathe%d" % i, top - UP * 0.05, (UP + out * 0.25).normalized(), 0.07, 0.016, spathem,
                          arch=0.15, segments=3, profile="lance", toward=out))
    ovary_top = top + axis * 0.025
    pieces.append(kw.rod("Ovary%d" % i, [top - UP * 0.005, ovary_top], 0.004, 0.0045, stalkm, sides=5))
    heads.append(ovary_top)
    pieces += kw.iris_flower("Iris%d_" % i, ovary_top, axis, rnd.uniform(0.062, 0.07), fall, standard, style, seed=i)
    # A side branch lower down: a second flower on four, rolled buds on two
    if i in (0, 1, 2, 3, 5, 6):
        b = Vector((math.cos(i * 2.1), math.sin(i * 2.1), 0.0))
        at = base + UP * (h * 0.72) + out * 0.02
        tip = at + (UP * 0.1 + b * 0.04)
        pieces.append(kw.rod("Branch%d" % i, [at, tip], 0.004, 0.003, stalkm, sides=4))
        pieces.append(kw.leaf("BSpathe%d" % i, at, (UP + b * 0.4).normalized(), 0.06, 0.014, spathem, arch=0.2,
                              segments=3, profile="lance", toward=b))
        if i in (0, 2, 3, 5):
            ax2 = (UP + b * 0.6).normalized()
            pieces.append(kw.rod("Ovary2_%d" % i, [tip, tip + ax2 * 0.022], 0.004, 0.0045, stalkm, sides=5))
            pieces += kw.iris_flower("IrisB%d_" % i, tip + ax2 * 0.022, ax2, rnd.uniform(0.056, 0.062), fall,
                                     standard, style, seed=50 + i)
        else:
            ax2 = (UP + b * 0.25).normalized()
            pieces.append(kw.rod("Bud%d" % i, [tip, tip + ax2 * 0.012, tip + ax2 * 0.055], 0.0065, 0.0012, budm,
                                 sides=6))

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.4, distance=2.1)
c = max(heads, key=lambda v: v.z - v.y)
kw.view(SCRIPT, "flower", model, PREVIEWS, tuple(c + Vector((0.12, -0.32, 0.2))), tuple(c))
print("[%s] done" % SCRIPT)
