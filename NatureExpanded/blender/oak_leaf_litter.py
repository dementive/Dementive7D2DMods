"""OakLeafLitter (forest floor, ground cover): a ragged patch of fallen white-oak leaves about 0.9 m across lying in a
low pile on a dark packed layer of crumbled leaf: long leaves with rounded lobes and deep sinuses in brown, tan and
rust, a good share of them dark and damp, some curled, the smaller ones with fewer lobes. Real overlapping leaves
resting on each other, thinning out irregularly toward the rim so the patch fades into the grass.

    blender -b --factory-startup --python oak_leaf_litter.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "OakLeafLitter", "oak_leaf_litter"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
rnd = random.Random(37)

patch = kg.Patch(0.45, seed=14, stretch=(1.0, 0.9))
patch.holes = [(0.1, 0.18, 0.06), (-0.22, -0.08, 0.07)]
patch.fade = (0.6, 1.3)
heap = kg.Heap(patch)

floor = kg.duff("OakDuff", (0.05, 0.033, 0.017), (0.1, 0.062, 0.028), (0.22, 0.14, 0.06), scale=110.0)
leaf = kg.leaf_material("OakLeaf", [((0.2, 0.108, 0.04), 3.0),     # brown
                                     ((0.27, 0.19, 0.08), 2.6),     # tan
                                     ((0.3, 0.12, 0.035), 2.0),     # rust
                                     ((0.1, 0.06, 0.028), 2.4)],    # dark, damp brown
                        kind="pinnate", veins=9.0, slope=0.35, edge_brown=0.5, damp=1.0, vein_lift=1.2, spots=0.55)

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd)


def curl_for():
    p = rnd.random()
    if p < 0.45:
        return (rnd.uniform(-0.1, 0.12), rnd.uniform(-0.2, 0.2), rnd.uniform(0.0, 0.6), 0.0), False
    if p < 0.82:
        return (rnd.uniform(0.2, 0.5), rnd.uniform(-0.3, 0.5), rnd.uniform(0.3, 0.9), rnd.uniform(-0.6, 0.6)), False
    return (rnd.choice((-1, 1)) * rnd.uniform(0.6, 0.95), rnd.uniform(0.2, 0.6), rnd.uniform(0.3, 0.9), rnd.uniform(-0.7, 0.7)), True


fill = patch.sample(rnd, 95, min_gap=0.027)
top = patch.sample(rnd, 40, min_gap=0.05)
for k, (x, y) in enumerate(fill):
    curl, mid = curl_for()
    kg.add_leaf(b, leaf, kg.oak_outline(rnd, 2 if k % 4 == 0 else 1), rnd.uniform(0.085, 0.115), (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=curl, tilt=(rnd.uniform(-3, 3), rnd.uniform(-3, 3)), mid=False, r2=rnd.uniform(0.35, 1.0),
                lod=0 if k % 3 == 0 else 1, lod_scale=1.5)
for k, (x, y) in enumerate(top):
    curl, mid = curl_for()
    keep = k % 5 < 4
    kg.add_leaf(b, leaf, kg.oak_outline(rnd, 3), rnd.uniform(0.1, 0.14), (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=curl, tilt=(rnd.uniform(-4, 4), rnd.uniform(-4, 4)), mid=mid and k % 2 == 0,
                r2=rnd.uniform(0.0, 0.9), lod=0 if keep else 1, lod_scale=1.5)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=2048, density={"OakLeaf": 1.0, "OakDuff": 0.5})
print("[%s] done" % SCRIPT)
