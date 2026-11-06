"""MapleLeafLitter (forest floor, ground cover): a ragged patch of fallen sugar-maple leaves about 0.9 m across lying
in a low pile on a dark packed layer of crumbled leaf: broad five-lobed leaves with rounded U sinuses and pointed
tips, in russet red, orange, gold and brown, the smaller ones three-lobed, some curled up at the lobes, some darker
and damp. Real overlapping leaves resting on each other, thinning out irregularly toward the rim so the patch fades
into the grass.

    blender -b --factory-startup --python maple_leaf_litter.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "MapleLeafLitter", "maple_leaf_litter"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
rnd = random.Random(23)

patch = kg.Patch(0.45, seed=9, stretch=(0.92, 1.0))
patch.holes = [(-0.14, -0.12, 0.07), (0.22, 0.14, 0.06)]
patch.fade = (0.6, 1.3)
heap = kg.Heap(patch)

floor = kg.duff("MapleDuff", (0.055, 0.032, 0.016), (0.115, 0.064, 0.028), (0.25, 0.14, 0.055), scale=110.0)
leaf = kg.leaf_material("MapleLeaf", [((0.28, 0.035, 0.016), 2.4),     # russet red
                                       ((0.19, 0.025, 0.014), 1.0),    # deep red-brown
                                       ((0.42, 0.15, 0.02), 3.0),       # orange
                                       ((0.42, 0.28, 0.04), 3.0),       # gold
                                       ((0.24, 0.125, 0.045), 2.6)],   # brown
                        kind="palmate", ox=0.17, lobes=(0, -48, 48, -99, 99), edge_brown=0.7, damp=0.7, vein_lift=1.18)

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd)


def curl_for():
    """Mostly lying flat, some with the lobes turned up, a few rolled hard."""
    p = rnd.random()
    if p < 0.5:
        return (rnd.uniform(-0.1, 0.1), rnd.uniform(-0.2, 0.2), rnd.uniform(0.0, 0.6), 0.0), False
    if p < 0.85:
        return (rnd.uniform(0.2, 0.55), rnd.uniform(-0.2, 0.5), rnd.uniform(0.3, 0.9), rnd.uniform(-0.6, 0.6)), False
    return (rnd.choice((-1, 1)) * rnd.uniform(0.6, 0.9), rnd.uniform(0.2, 0.6), rnd.uniform(0.3, 0.9), rnd.uniform(-0.7, 0.7)), True


fill = patch.sample(rnd, 125, min_gap=0.022)
top = patch.sample(rnd, 46, min_gap=0.05)
for k, (x, y) in enumerate(fill):
    curl, mid = curl_for()
    kg.add_leaf(b, leaf, kg.maple_outline(rnd, 3), rnd.uniform(0.085, 0.12), (x, y), rnd.uniform(0, math.tau), heap,
                rnd, curl=curl, tilt=(rnd.uniform(-3, 3), rnd.uniform(-3, 3)), mid=False, r2=rnd.uniform(0.3, 1.0),
                lod=0 if k % 3 == 0 else 1, lod_scale=1.5)
for k, (x, y) in enumerate(top):
    curl, mid = curl_for()
    keep = k % 5 < 4
    kg.add_leaf(b, leaf, kg.maple_outline(rnd, 5), rnd.uniform(0.1, 0.145), (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=curl, tilt=(rnd.uniform(-4, 4), rnd.uniform(-4, 4)), mid=mid and k % 2 == 0,
                r2=rnd.uniform(0.0, 0.8), lod=0 if keep else 1, lod_scale=1.5)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=2048, density={"MapleLeaf": 1.0, "MapleDuff": 0.5})
print("[%s] done" % SCRIPT)
