"""LichenStone (forest floor, ground cover): a flat-topped weathered stone about 38 cm long and 9 cm high sunk in the
ground, its sunny top and sides crusted with grey-green and orange lichen (tiny cracked plates, dark-rimmed patches and round
orange rosettes), moss in clumps along its shady lower side and round its foot, two smaller stones beside it, a scatter
of dead leaves and soil. Rock, relief and lichen are in the geometry and the texture down to the texel.

    blender -b --factory-startup --python lichen_stone.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "LichenStone", "lichen_stone"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(61)

patch = kg.Patch(0.42, seed=52, stretch=(1.0, 0.85))
patch.fade = (0.55, 1.2)
heap = kg.Heap(patch, reach=0.62)

floor = kg.duff("StoneDuff", (0.055, 0.04, 0.024), (0.11, 0.08, 0.046), (0.19, 0.145, 0.085), scale=110.0, chips=0.35,
                soil=(0.05, 0.036, 0.022))
stone = kg.stone_material("Fieldstone", lichen=1.0, moss=0.85)
moss = kf.moss_material("StoneMoss", soil=(0.055, 0.04, 0.026))
oak = kg.leaf_material("StoneOakLeaf", [((0.2, 0.108, 0.04), 3.0), ((0.27, 0.19, 0.08), 2.4), ((0.1, 0.06, 0.028), 2.4)],
                       kind="pinnate", veins=9.0, slope=0.35, damp=1.0, vein_lift=1.2)
birch = kg.leaf_material("StoneBirchLeaf", [((0.36, 0.25, 0.04), 2.0), ((0.26, 0.16, 0.05), 3.0), ((0.2, 0.11, 0.04), 2.0)],
                         kind="pinnate", veins=10.0, slope=0.5, damp=0.8)

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd, reach=0.62)

# The stones: a big flat-topped one and two small ones beside it
MAIN = (0.02, 0.0)
kg.rock(b, stone, (MAIN[0], MAIN[1], G + 0.022), (0.2, 0.15, 0.085), rnd, subdiv=3, rough=0.17, yaw=0.45, cut_top=0.82,
        flat=0.0, smooth=False,
        planes=[((1.0, 0.3, 0.35), 0.15), ((-0.9, 0.5, 0.4), 0.14), ((0.2, -1.0, 0.35), 0.105), ((-0.3, 1.0, 0.3), 0.11),
                ((0.8, -0.7, 0.45), 0.145), ((-0.7, -0.6, 0.5), 0.14)])
SMALL = [((-0.29, -0.13), (0.085, 0.065, 0.045), 0.9, 0.7), ((0.27, 0.19), (0.07, 0.06, 0.04), -0.5, 0.75)]
for (x, y), radii, yaw, cut in SMALL:
    kg.rock(b, stone, (x, y, G + 0.012), radii, rnd, subdiv=2, rough=0.2, yaw=yaw, cut_top=cut, lod=0, smooth=False,
            planes=[((1.0, 0.2, 0.4), radii[0] * 0.8), ((-0.6, 0.8, 0.4), radii[1] * 0.8)])
# Stamp the stones onto the heap so things dropped later don't sink into them
for (x, y), (a, bb, c) in [(MAIN, (0.2, 0.15, 0.085))] + [(p, r) for p, r, _, _ in SMALL]:
    for i in range(-12, 13):
        for j in range(-12, 13):
            dx, dy = i * 0.012, j * 0.012
            if (dx / a) ** 2 + (dy / bb) ** 2 < 0.9:
                heap.stamp(x + dx, y + dy, G + 0.02 + c * 0.8)


def mound(x, y, r, h, lod):
    ph = [rnd.uniform(0, math.tau) for _ in range(3)]

    def wob(i, a):
        return 1.0 + 0.2 * math.sin(3 * a + ph[0]) + 0.1 * math.sin(5 * a + ph[1]), (h * 0.14 * math.sin(2 * a + ph[2]) if i == 1 else 0.0)

    z0 = G + 0.001
    prof = [(0.0, h), (0.68 * r, 0.62 * h), (r, -0.004)]
    kg.lathe(b, moss, prof, (x, y, z0), (0, 0, 1), segments=7, t=(1.0, 0.65, 0.0), wobble=lambda i, a: wob(i, a),
             phase=rnd.uniform(0, math.tau), lod=lod, lod_scale=1.35, rnd=rnd)


# Moss hugging the foot, thickest on the shady (north, +y) side
for k in range(15):
    a = rnd.uniform(0.15, math.pi - 0.15) if k < 11 else rnd.uniform(math.pi, math.tau)
    rr = 1.02 + rnd.uniform(-0.03, 0.12)
    x = MAIN[0] + math.cos(a + 0.45) * 0.2 * rr * math.cos(0.45) - math.sin(a + 0.45) * 0.15 * rr * math.sin(0.45)
    y = MAIN[1] + math.cos(a + 0.45) * 0.2 * rr * math.sin(0.45) + math.sin(a + 0.45) * 0.15 * rr * math.cos(0.45)
    mound(x, y, rnd.uniform(0.025, 0.05), rnd.uniform(0.014, 0.026), 0 if k % 2 == 0 else 1)
for (x, y), r, _, _ in SMALL:
    for k in range(4):
        a = rnd.uniform(0, math.tau)
        mound(x + math.cos(a) * r[0] * 1.05, y + math.sin(a) * r[1] * 1.05, rnd.uniform(0.02, 0.035), rnd.uniform(0.01, 0.02), 1)

# Dead leaves on the ground round it
for k, (x, y) in enumerate(patch.sample(rnd, 22, min_gap=0.05, reach=0.9)):
    if (x - MAIN[0]) ** 2 / 0.22 ** 2 + (y - MAIN[1]) ** 2 / 0.17 ** 2 < 1.0:
        continue
    if k % 2:
        outline, mat, L = kg.oak_outline(rnd, 1), oak, rnd.uniform(0.07, 0.1)
    else:
        outline, mat, L = kg.birch_outline(rnd, 1), birch, rnd.uniform(0.05, 0.075)
    kg.add_leaf(b, mat, outline, L, (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=(rnd.uniform(-0.2, 0.5), rnd.uniform(-0.2, 0.4), 0.4, rnd.uniform(-0.5, 0.5)),
                tilt=(rnd.uniform(-5, 5), rnd.uniform(-5, 5)), lod=1, max_height=0.12)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=1024,
         density={"Fieldstone": 1.6, "StoneMoss": 1.0, "StoneDuff": 0.4, "StoneOakLeaf": 0.6, "StoneBirchLeaf": 0.6})
print("[%s] done" % SCRIPT)
