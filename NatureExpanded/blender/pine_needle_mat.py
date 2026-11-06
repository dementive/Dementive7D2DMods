"""PineNeedleMat (forest floor, ground cover): a ragged patch of fallen pine needles about 0.9 m across lying in a
low mat on a dark packed layer of old needle duff: long russet and tan needles in bundles of two and three, still
joined at their dark papery sheaths, lying in swirls and crossing each other, a few short snapped twigs and a loose cone
scale or two. Needles are real flat ribbons resting on each other, thinning out irregularly toward the rim so the
patch fades into the grass.

    blender -b --factory-startup --python pine_needle_mat.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "PineNeedleMat", "pine_needle_mat"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(5)

patch = kg.Patch(0.45, seed=3, stretch=(1.0, 0.9))
patch.holes = [(0.18, -0.12, 0.06)]
patch.fade = (0.6, 1.3)
heap = kg.Heap(patch)

floor = kg.duff("NeedleDuff", (0.035, 0.021, 0.011), (0.085, 0.048, 0.02), (0.2, 0.11, 0.045), scale=95.0,
                strands=0.75, strand_cols=((0.22, 0.12, 0.045), (0.12, 0.062, 0.025)), chips=0.3)
needle = kg.needle_material("Needle")
bark = kg.twig_bark("TwigBark", peel=0.35)
wood = kg.twig_wood("TwigWood")
scale_mat = kg.cone_scale_material("ConeScale")

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd)

# ---------------------------------------------------------------- needles: swirls of bundles, bottom layer first
bundles = patch.sample(rnd, 270, min_gap=0.008)
for k, (x, y) in enumerate(bundles):
    swirl = mn.noise(Vector((x * 2.6 + 3.0, y * 2.6, 0.7))) * math.tau * 1.3
    heading = swirl + rnd.gauss(0.0, 0.9)
    count = 3 if rnd.random() < 0.7 else 2
    kg.needle_bundle(b, needle, heap, (x, y), heading, rnd.uniform(0.11, 0.17), count, rnd,
                     lod=0 if k % 5 < 2 else 1, lod_scale=1.3, spread=rnd.uniform(0.05, 0.12), arch=rnd.uniform(0.001, 0.004))

# ---------------------------------------------------------------- a few short snapped twigs
for k in range(5):
    x, y = patch.sample(rnd, 1)[0]
    L = rnd.uniform(0.1, 0.22)
    hd = rnd.uniform(0, math.tau)
    rad = rnd.uniform(0.0022, 0.0038)
    d = Vector((math.cos(hd), math.sin(hd), 0.0))
    side = Vector((-d.y, d.x, 0.0))
    pts = []
    for q in range(4):
        s = q / 3.0 - 0.5
        p = d * (L * s) + side * (0.012 * math.sin(q * 1.9 + k)) 
        pts.append((x + p.x, y + p.y))
    zs = []
    for q, (px, py) in enumerate(pts):
        zs.append(max(heap.top(px + dx, py + dy) for dx in (-0.01, 0.0, 0.01) for dy in (-0.01, 0.0, 0.01)) + rad * 0.9)
    path = [(px, py, z + (0.002 if 0 < q < 3 else 0.0)) for q, ((px, py), z) in enumerate(zip(pts, zs))]
    kg.tube(b, bark, path, [rad * 1.15, rad, rad * 0.9, rad * 0.75], sides=5, jag=0.004, rnd=rnd, cap_mat=wood,
            caps=(True, True), lod=0 if k < 3 else 1, lod_scale=1.2)
    for (px, py, z) in path:
        heap.stamp(px, py, z + rad)

# ---------------------------------------------------------------- loose cone scales
for k, (x, y) in enumerate(patch.sample(rnd, 3, min_gap=0.15)):
    curl = (rnd.uniform(0.1, 0.4), rnd.uniform(0.3, 0.7), rnd.uniform(0.0, 0.3), 0.0)
    kg.add_leaf(b, scale_mat, kg.cone_scale_outline(rnd), rnd.uniform(0.032, 0.046), (x, y), rnd.uniform(0, math.tau), heap,
                rnd, curl=curl, tilt=(rnd.uniform(-8, 8), rnd.uniform(-8, 8)), lod=0 if k < 2 else 1, lod_scale=1.3)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=2048,
         density={"Needle": 1.0, "NeedleDuff": 0.5, "TwigBark": 1.1, "TwigWood": 0.5, "ConeScale": 1.1})
print("[%s] done" % SCRIPT)
