"""Cattail (water's edge): a stand of broadleaf cattail filling a block, 14 tall flat strap leaves 1.2 to 1.6 m (their
tops arching over and twisting), a few younger shorter ones and a couple of dead brown ones flopped at the base, and
six stalks carrying the brown velvet sausage heads, 15 cm long, each with the thin bare spike of the spent male
flowers above it. One head is younger and greener, its spike still gold with pollen; one of last year's is bursting
into cream seed fluff. No grass: it grows in water.

    blender -b --factory-startup --python cattail.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wetland as kw  # noqa: E402

NAME, SCRIPT = "Cattail", "cattail"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(5)
G = nk.GROUND

leafm = nk.plant("CattailLeaf", (0.15, 0.21, 0.1), (0.2, 0.24, 0.13), rough=0.55, vary=0.3)
youngm = nk.plant("CattailYoung", (0.17, 0.25, 0.1), (0.14, 0.2, 0.09), rough=0.55, vary=0.25)
deadm = nk.plant("CattailDead", (0.34, 0.25, 0.13), (0.2, 0.14, 0.07), rough=0.8, vary=0.35, sat=0.8)
stalkm = nk.plant("CattailStalk", (0.17, 0.22, 0.1), (0.13, 0.17, 0.08), rough=0.6)
headm = nk.plant("CattailHead", (0.095, 0.042, 0.016), (0.055, 0.026, 0.011), rough=0.95, vary=0.3, scale=40.0, sat=1.0,
                 value=0.95)
younghead = nk.plant("CattailYoungHead", (0.1, 0.07, 0.025), (0.07, 0.07, 0.03), rough=0.9, vary=0.3, scale=40.0)
spikem = nk.plant("CattailSpike", (0.3, 0.24, 0.13), (0.18, 0.14, 0.07), rough=0.85)
pollen = nk.petal("CattailPollen", (0.45, 0.32, 0.06), (0.75, 0.55, 0.1), rough=0.9, sat=0.9)
fluff = nk.plant("CattailFluff", (0.42, 0.37, 0.28), (0.3, 0.26, 0.19), rough=1.0, vary=0.35, sat=0.6, value=0.95)

pieces = []

# Stalks with their heads, close together in the middle of the stand
spots = nk.scatter(6, 0.2, seed=4, min_gap=0.09)
for i, (x, y) in enumerate(spots):
    young = i == 5
    h = rnd.uniform(1.05, 1.15) if young else rnd.uniform(1.2, 1.5)
    lean = Vector((x, y, 0.0)) * 0.3 + Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0.0))
    base = Vector((x, y, G))
    mid = base + Vector((0, 0, h * 0.55)) + lean * 0.3
    hl = (rnd.uniform(0.11, 0.13) if young else rnd.uniform(0.14, 0.17))
    head_base = base + Vector((0, 0, h - hl)) + lean
    axis = (head_base - mid).normalized()
    pieces.append(kw.rod("Stalk%d" % i, [base, mid, head_base + axis * 0.01], 0.0065, 0.0045, stalkm, sides=4))
    pieces.append(kw.sausage("Head%d" % i, head_base, axis, hl, rnd.uniform(0.012, 0.014) if young else
                             rnd.uniform(0.0155, 0.018), younghead if young else headm, sides=12, seed=i))
    top = head_base + axis * hl
    if i == 2:
        # Last year's head, bursting: a ragged cream wad of seed fluff breaking out of its upper half
        pieces.append(kw.sausage("Fluff%d" % i, head_base + axis * (hl * 0.5), axis, hl * 0.55, 0.0195, fluff, sides=8,
                                 seed=40 + i))
        pieces.append(kw.florets("FluffTufts%d" % i, [head_base + axis * (hl * 0.5), top + axis * 0.015], 16, 0.032,
                                 fluff, seed=i, out=1.0, nod=0.0))
    sl = rnd.uniform(0.09, 0.15)
    bend = Vector((rnd.uniform(-0.015, 0.015), rnd.uniform(-0.015, 0.015), 0.0))
    if young:
        # Still in flower: a fatter gold spike of pollen
        pieces.append(kw.rod("Spike%d" % i, [top - axis * 0.004, top + axis * sl * 0.5, top + axis * sl + bend],
                             0.0065, 0.003, pollen, sides=6))
    else:
        pieces.append(kw.rod("Spike%d" % i, [top - axis * 0.004, top + axis * sl * 0.55 + bend * 0.3,
                                             top + axis * sl + bend], 0.0026, 0.0007, spikem, sides=3))


def strap(tag, x, y, length, width, mat, arch, lean_deg, twist, segs=14, power=3.0):
    # Leaves near the rim arch sideways or back across the stand, so the tops stay over the block
    r = math.hypot(x, y)
    a = math.atan2(y, x) + (rnd.choice((-1, 1)) * rnd.uniform(1.2, 2.6) if r > 0.14 else rnd.uniform(-2.0, 2.0))
    out = Vector((math.cos(a), math.sin(a), 0.0))
    lr = math.radians(lean_deg)
    d = out * math.sin(lr) + Vector((0, 0, 1)) * math.cos(lr)
    return kw.leaf(tag, (x, y, G), d, length, width, mat, arch=arch, power=power, twist=twist, segments=segs,
                   profile="strap", roll=rnd.uniform(-25, 25), toward=out)


# Tall strap leaves: some sheathing the stalks, the rest round them
leaf_spots = list(spots) + nk.scatter(8, 0.27, seed=9, min_gap=0.07)
for i, (x, y) in enumerate(leaf_spots):
    x += rnd.uniform(-0.012, 0.012)
    y += rnd.uniform(-0.012, 0.012)
    pieces.append(strap("Leaf%d" % i, x, y, rnd.uniform(1.15, 1.6), rnd.uniform(0.018, 0.025), leafm,
                        rnd.uniform(0.2, 0.75), rnd.uniform(2.0, 7.0), rnd.choice((-1, 1)) * rnd.uniform(40, 170)))
# Younger leaves coming up
for i, (x, y) in enumerate(nk.scatter(14, 0.3, seed=13, min_gap=0.05)):
    pieces.append(strap("Young%d" % i, x, y, rnd.uniform(0.55, 1.0), rnd.uniform(0.014, 0.02), youngm,
                        rnd.uniform(0.1, 0.5), rnd.uniform(3.0, 10.0), rnd.uniform(-90, 90), segs=8))
# Dead leaves from last year, broken and flopped over at the base
for i, (x, y) in enumerate(nk.scatter(4, 0.12, seed=21, min_gap=0.08)):
    pieces.append(strap("Dead%d" % i, x, y, rnd.uniform(0.35, 0.55), rnd.uniform(0.016, 0.022), deadm,
                        rnd.uniform(1.4, 1.9), rnd.uniform(5.0, 15.0), rnd.uniform(-60, 60), segs=6, power=2.2))

kw.bounds(pieces, NAME)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.8, distance=3.8)
kw.view(SCRIPT, "heads", model, PREVIEWS, (0.45, -1.1, 1.15), (0.0, 0.0, 0.8))
kw.wide_patch(SCRIPT, model, PREVIEWS, height=1.6)
print("[%s] done" % SCRIPT)
