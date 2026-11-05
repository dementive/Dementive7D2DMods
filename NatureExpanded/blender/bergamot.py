"""Bergamot (pine forest meadows): a clump of wild bergamot (Monarda fistulosa), seven square stems 50 to 80 cm, some
forking near the top, ending in 11 shaggy lavender-pink heads 5 to 6 cm across: a ragged ball of long curving tubular
florets bursting from a green-purple dome, a ruff of leafy bracts under it, one head still young and tight. Pairs of
opposite lance leaves up the stems, each pair turned a quarter from the last; meadow grass among them.

    blender -b --factory-startup --python bergamot.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "Bergamot", "bergamot"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(5)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stemm = nk.plant("BergamotStem", (0.2, 0.21, 0.11), (0.26, 0.15, 0.13), rough=0.7)
leafm = ww.leaf_mat("BergamotLeaf", (0.12, 0.19, 0.08), (0.16, 0.2, 0.11), rib=(0.24, 0.28, 0.16), rough=0.7)
bract = nk.plant("BergamotBract", (0.22, 0.23, 0.15), (0.38, 0.24, 0.32), rough=0.6, vary=0.35)
corem = nk.plant("BergamotCore", (0.3, 0.2, 0.28), (0.36, 0.16, 0.34), rough=0.6, sat=1.0)
floret = nk.petal("BergamotFloret", (0.72, 0.48, 0.74), (0.66, 0.2, 0.6), mid=(0.63, 0.27, 0.66), sat=1.0, value=0.95)
grass = nk.grass()

sheets = {k: ww.Sheet("Bergamot" + k, m) for k, m in (("Stem", stemm), ("Leaf", leafm), ("Bract", bract),
                                                     ("Core", corem), ("Floret", floret))}


def head(at, axis, seed, young=False):
    """A shaggy head: florets bursting from a dome, a ruff of bracts under it."""
    r = random.Random(seed)
    axis = Vector(axis).normalized()
    core = 0.008 if young else r.uniform(0.0125, 0.0145)
    center = at + axis * core * 0.5
    if young:
        ww.ball(sheets["Core"], center, axis, core, core * 1.5, segs=6, rings=2, seed=seed)
        ww.pompom(sheets["Floret"], center, axis, core, 12, 0.009, 0.005, cutoff=0.1, profile="taper",
                  segments=1, lean_up=0.8, seed=seed, core_length=core * 1.5, t_range=(0.3, 0.8))
    else:
        # A lavender ball under the florets, so the head reads as a solid pompom from far off
        ww.ball(sheets["Floret"], center, axis, core * 1.25, core * 1.9, segs=6, rings=2, seed=seed,
                t_range=(0.25, 0.6))
        ww.pompom(sheets["Floret"], center, axis, core * 1.1, 28, r.uniform(0.027, 0.031), 0.0078, cutoff=-0.3,
                  profile="linear", segments=2, bend=0.3, lean_up=0.25, seed=seed, core_length=core * 1.7,
                  t_range=(0.1, 1.0))
    ww.ring(sheets["Bract"], at - axis * 0.002, axis, 6, 0.02 if not young else 0.014, 0.009, cup=-0.15, droop=0.3,
            seed=seed, profile="lance", segments=2)


def leaf_pair(at, direction, angle, size, seed):
    for k, a in enumerate((angle, angle + math.pi)):
        out = ww.perpendicular(direction, a)
        d = (out + Vector(direction) * 0.55).normalized()
        ww.leaf(sheets["Leaf"], at, d, size * random.Random(seed + k).uniform(0.9, 1.1), size * 0.36,
                profile="lance", segments=3, bend=0.28, fold=0.18, twist=random.Random(seed - k).uniform(-25, 25),
                seed=seed * 3 + k)


bases = nk.scatter(9, 0.24, seed=3, min_gap=0.06)
n_head = 0
for i, (x, y) in enumerate(bases):
    h = rnd.uniform(0.46, 0.75)
    out = Vector((x, y, 0.0)) * 1.0 + Vector((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), 0.0))
    direction = (UP + out).normalized()
    pts = ww.path((x, y, G), direction, h, 5, bend=-0.08, wobble=0.04, seed=i)
    ww.stalk(sheets["Stem"], pts, 0.0036, 0.0022, sides=4)
    # Opposite leaf pairs up the stem, each turned a quarter from the last, smaller higher up
    a0 = rnd.uniform(0, math.pi)
    for j, s in enumerate((0.12, 0.29, 0.46, 0.63)):
        at, d = ww.along(pts, s)
        leaf_pair(at, d, a0 + j * math.pi * 0.5, 0.115 * (1.0 - s * 0.45), seed=i * 20 + j)
    top, d = ww.along(pts, 1.0)
    head(top, (d + UP * 0.6).normalized(), seed=i, young=(i == 8))
    n_head += 1
    if i < 4:
        # A fork near the top, carrying its own head
        fork, fd = ww.along(pts, 0.78)
        side = ww.perpendicular(fd, rnd.uniform(0, math.tau))
        bd = (fd + side * 0.75).normalized()
        bpts = ww.path(fork, bd, rnd.uniform(0.09, 0.15), 3, bend=-0.35, seed=50 + i)
        ww.stalk(sheets["Stem"], bpts, 0.0024, 0.0017, sides=4, t_range=(0.75, 1.0))
        btop, bdir = ww.along(bpts, 1.0)
        head(btop, (bdir + UP * 0.8).normalized(), seed=30 + i)
        leaf_pair(fork, fd, rnd.uniform(0, math.pi), 0.045, seed=90 + i)
        n_head += 1

pieces = ww.build(sheets.values())
for k, (x, y) in enumerate(nk.scatter(4, 0.38, seed=8, min_gap=0.2)):
    pieces += nk.tuft("Grass%d_" % k, (x, y), 6, 0.28, grass, seed=k)

model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.42, distance=1.6)
print("[%s] done (%d heads)" % (SCRIPT, n_head))
