"""BirchLeafLitter (forest floor, ground cover): a ragged patch of fallen birch leaves about 0.9 m across, lying in a
low pile on a dark packed layer of crumbled leaf: small doubly serrated, pointed ovals in yellow-gold and tan, some
paler, some gone brown and damp, a good share curled at the edges. Real overlapping leaves resting on each other, thinning
out irregularly toward the rim so the patch fades into the grass.

    blender -b --factory-startup --python birch_leaf_litter.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "BirchLeafLitter", "birch_leaf_litter"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
rnd = random.Random(11)

patch = kg.Patch(0.44, seed=5, stretch=(1.0, 0.86))
patch.holes = [(0.12, -0.16, 0.07), (-0.2, 0.1, 0.06)]
patch.fade = (0.6, 1.3)
heap = kg.Heap(patch)

floor = kg.duff("BirchDuff", (0.055, 0.037, 0.018), (0.115, 0.074, 0.032), (0.26, 0.17, 0.07), scale=110.0)
leaf = kg.leaf_material("BirchLeaf", [((0.5, 0.35, 0.045), 3.4),    # yellow-gold
                                       ((0.3, 0.185, 0.06), 3.0),    # tan
                                       ((0.52, 0.43, 0.19), 1.2),    # pale straw
                                       ((0.22, 0.12, 0.04), 1.6),    # gone brown
                                       ((0.3, 0.26, 0.05), 0.5)],    # a last olive one
                        kind="pinnate", veins=10.0, slope=0.5, edge_brown=0.55, damp=0.55)

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd)


def curl_for(k):
    """Mostly flat or mildly bowed; some curled hard with their edges rolled up and the tip turned."""
    p = rnd.random()
    if p < 0.5:
        return (rnd.uniform(-0.1, 0.12), rnd.uniform(-0.2, 0.2), rnd.uniform(0.0, 0.5), 0.0), False
    if p < 0.85:
        return (rnd.uniform(0.15, 0.45), rnd.uniform(-0.3, 0.5), rnd.uniform(0.2, 0.8), rnd.uniform(-0.6, 0.6)), False
    return (rnd.choice((-1, 1)) * rnd.uniform(0.6, 0.95), rnd.uniform(0.2, 0.6), rnd.uniform(0.3, 0.9), rnd.uniform(-0.7, 0.7)), True


# Bottom layer first: simple filler leaves, darker and damper, then the detailed ones on top
fill = patch.sample(rnd, 150, min_gap=0.016)
top = patch.sample(rnd, 58, min_gap=0.03)
for k, (x, y) in enumerate(fill):
    outline = kg.birch_outline(rnd, teeth=1 if k % 5 < 3 else 2)
    curl, mid = curl_for(k)
    kg.add_leaf(b, leaf, outline, rnd.uniform(0.058, 0.088), (x, y), rnd.uniform(0, math.tau), heap, rnd, curl=curl,
                tilt=(rnd.uniform(-3, 3), rnd.uniform(-3, 3)), mid=False, r2=rnd.uniform(0.3, 1.0),
                lod=0 if k % 3 == 0 else 1, lod_scale=1.5)
for k, (x, y) in enumerate(top):
    outline = kg.birch_outline(rnd, teeth=4 if k % 3 else 3)
    curl, mid = curl_for(k)
    keep = k % 5 < 4
    kg.add_leaf(b, leaf, outline, rnd.uniform(0.064, 0.095), (x, y), rnd.uniform(0, math.tau), heap, rnd, curl=curl,
                tilt=(rnd.uniform(-4, 4), rnd.uniform(-4, 4)), mid=mid, r2=rnd.uniform(0.0, 0.8),
                lod=0 if keep else 1, lod_scale=1.5)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=2048, density={"BirchLeaf": 1.0, "BirchDuff": 0.5})
print("[%s] done" % SCRIPT)
