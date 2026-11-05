"""Chicory (pine forest meadows, along roads): five stiff, nearly leafless grey-green stems 60 to 100 cm from one
crown, forking into stiff side branches, with 30 sky-blue flowers 3.5 to 4 cm across dotted along them, singly or in
pairs, all facing out: each a flat ring of 14 strap-shaped rays with square, notched tips round a little dark blue
center. Green buds wait at the other nodes, tiny clasping leaves at the forks, and a rosette of dandelion-like leaves
with back-pointing lobes sits at the base among meadow grass.

    blender -b --factory-startup --python chicory.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "Chicory", "chicory"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(21)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stemm = nk.plant("ChicoryStem", (0.21, 0.25, 0.15), (0.17, 0.2, 0.12), rough=0.75, sat=0.7)
leafm = ww.leaf_mat("ChicoryLeaf", (0.12, 0.2, 0.08), (0.16, 0.21, 0.1), rib=(0.3, 0.24, 0.16), rough=0.7)
ray = nk.petal("ChicoryRay", (0.16, 0.3, 0.82), (0.36, 0.53, 0.95), mid=(0.27, 0.45, 0.92), streaks=0.12, sat=1.0,
               value=1.0)
eye = nk.petal("ChicoryEye", (0.05, 0.08, 0.45), (0.2, 0.25, 0.7), sat=1.0, value=0.95)
budm = nk.petal("ChicoryBud", (0.15, 0.22, 0.1), (0.2, 0.3, 0.55), sat=0.9, value=0.85)
grass = nk.grass()

sheets = {k: ww.Sheet("Chicory" + k, m) for k, m in (("Stem", stemm), ("Leaf", leafm), ("Ray", ray), ("Eye", eye),
                                                    ("Bud", budm))}
count = {"flowers": 0, "buds": 0}


def flower(at, stem_dir, seed):
    r = random.Random(seed)
    out = ww.perpendicular(stem_dir, r.uniform(0, math.tau))
    axis = (out + UP * r.uniform(0.6, 1.4)).normalized()
    c = Vector(at) + out * 0.006
    ww.ring(sheets["Ray"], c, axis, 13, r.uniform(0.02, 0.023), 0.0108, cup=0.05, droop=0.06, profile="square",
            segments=1, rib=True, notch=0.1, jitter=0.06, seed=seed)
    ww.dome(sheets["Eye"], c + axis * 0.001, axis, 0.003, 0.004, segs=5, seed=seed)
    count["flowers"] += 1


def buds(at, stem_dir, n, seed):
    r = random.Random(seed)
    for k in range(n):
        out = ww.perpendicular(stem_dir, r.uniform(0, math.tau))
        ww.bud(sheets["Bud"], Vector(at) + out * 0.003, (out + UP * 0.8).normalized(), r.uniform(0.01, 0.014),
               0.0042, seed=seed + k)
        count["buds"] += 1


def node(at, stem_dir, seed):
    """A node along a stem: one or two flowers, maybe a bud or two, a tiny clasping leaf."""
    r = random.Random(seed)
    roll = r.random()
    if roll < 0.15:
        buds(at, stem_dir, 2, seed)
    else:
        flower(at, stem_dir, seed)
        if roll > 0.72:
            flower(at, stem_dir, seed + 1000)
        if r.random() < 0.15:
            buds(at, stem_dir, 1, seed + 2000)
    side = ww.perpendicular(stem_dir, r.uniform(0, math.tau))
    ww.leaf(sheets["Leaf"], at, (side + Vector(stem_dir) * 1.2).normalized(), r.uniform(0.018, 0.03), 0.007,
            profile="lance", segments=2, rib=False, bend=0.1, seed=seed)


crowns = nk.scatter(5, 0.09, seed=4, min_gap=0.04)
for i, (x, y) in enumerate(crowns):
    h = rnd.uniform(0.62, 1.0)
    a = math.atan2(y, x) + rnd.uniform(-0.4, 0.4)
    lean = rnd.uniform(0.2, 0.42)
    direction = Vector((math.cos(a) * lean, math.sin(a) * lean, 1.0)).normalized()
    pts = ww.path((x, y, G), direction, h, 4, bend=0.02, wobble=0.05, seed=i)
    ww.stalk(sheets["Stem"], pts, 0.0034, 0.0018)
    for j, s in enumerate((0.55, 0.72, 0.88)):
        at, d = ww.along(pts, s)
        node(at, d, seed=i * 50 + j)
    top, d = ww.along(pts, 1.0)
    flower(top, d, seed=i * 50 + 9)
    buds(top, d, 1, seed=i * 50 + 19)
    # Stiff side branches angling up and out
    for b in range(2):
        s_b = rnd.uniform(0.3, 0.7)
        fork, fd = ww.along(pts, s_b)
        side = ww.perpendicular(fd, rnd.uniform(0, math.tau))
        bd = (fd + side * rnd.uniform(0.7, 1.0)).normalized()
        blen = rnd.uniform(0.18, 0.32) * (1.0 - s_b * 0.5)
        bpts = ww.path(fork, bd, blen, 2, bend=-0.15, wobble=0.06, seed=100 + i * 5 + b)
        ww.stalk(sheets["Stem"], bpts, 0.0022, 0.0014, t_range=(0.5, 1.0))
        for j, s in enumerate((0.55, 1.0) if b == 0 else (1.0,)):
            at, d = ww.along(bpts, s)
            node(at, d, seed=300 + i * 20 + b * 5 + j)

# A rosette of dandelion-like leaves with back-pointing lobes
for k in range(9):
    a = k / 9 * math.tau + rnd.uniform(-0.25, 0.25)
    d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.25, 0.6)))
    ww.leaf(sheets["Leaf"], (rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), G + 0.01), d,
            rnd.uniform(0.15, 0.24), rnd.uniform(0.04, 0.05), profile="lance", lobes=4, lobe_depth=0.55, hook=-0.6,
            bend=rnd.uniform(0.3, 0.6), fold=0.12, twist=rnd.uniform(-20, 20), seed=700 + k)

pieces = ww.build(sheets.values())
for k, (x, y) in enumerate(nk.scatter(3, 0.36, seed=6, min_gap=0.25)):
    pieces += nk.tuft("Grass%d_" % k, (x, y), 6, 0.3, grass, seed=k)

model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.5, distance=1.9)
print("[%s] done (%d flowers, %d buds)" % (SCRIPT, count["flowers"], count["buds"]))
