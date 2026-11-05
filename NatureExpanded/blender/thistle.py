"""Thistle (wasteland): a bull thistle, four stout spiny stems 60 to 100 cm from a rosette of big deeply lobed, spine
tipped grey-green leaves, forking near the top. Ten heads: eight fat purple shaving brushes (a flaring tuft of florets
out of a spiny green bulb), two gone over to white fluff on browning bulbs, and a couple of tight spiny buds. Smaller
lobed spiny leaves up the stems, spines along the stems themselves. No grass: it grows on bare waste ground.

    blender -b --factory-startup --python thistle.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "Thistle", "thistle"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(8)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stemm = nk.plant("ThistleStem", (0.18, 0.22, 0.12), (0.22, 0.24, 0.15), rough=0.7, sat=0.75)
leafm = ww.leaf_mat("ThistleLeaf", (0.13, 0.19, 0.1), (0.2, 0.24, 0.15), rib=(0.38, 0.4, 0.3), rough=0.7, sat=0.75)
spine = nk.petal("ThistleSpine", (0.2, 0.24, 0.1), (0.72, 0.62, 0.32), sat=0.85, value=0.9)
bulb = nk.plant("ThistleBulb", (0.15, 0.22, 0.09), (0.26, 0.26, 0.12), rough=0.6, vary=0.35, sat=0.85)
dry = nk.plant("ThistleDryBulb", (0.25, 0.2, 0.1), (0.32, 0.26, 0.14), rough=0.7, vary=0.35)
floret = nk.petal("ThistleFloret", (0.55, 0.3, 0.5), (0.5, 0.05, 0.42), mid=(0.47, 0.06, 0.4), sat=1.0, value=0.95)
down = nk.petal("ThistleDown", (0.72, 0.68, 0.6), (0.95, 0.94, 0.9), sat=0.8, value=1.0)

sheets = {k: ww.Sheet("Thistle" + k, m) for k, m in (("Stem", stemm), ("Leaf", leafm), ("Spine", spine),
                                                    ("Bulb", bulb), ("Dry", dry), ("Floret", floret),
                                                    ("Down", down))}
count = {"flowers": 0, "fluff": 0, "buds": 0}


def spiny_bulb(at, axis, radius, length, sheet, seed, spines=16):
    """The involucre: an urn of bracts, each ending in a spine pointing out and up."""
    r = random.Random(seed)
    c = Vector(at) + axis * length * 0.5
    ww.ball(sheets[sheet], c, axis, radius, length, segs=6, rings=3, seed=seed, rough=0.08)
    for k, n in enumerate(ww.sphere_dirs(axis, spines, cutoff=-0.5, seed=seed)):
        z = n.dot(axis)
        base = c + (n - axis * z) * radius * 0.95 + axis * z * length * 0.45
        ww.needle(sheets["Spine"], base, (n + axis * 0.6).normalized(), r.uniform(0.008, 0.013), 0.0022,
                  seed=seed * 7 + k)
    return c + axis * length * 0.42


def head(at, axis, seed, kind="flower"):
    r = random.Random(seed)
    axis = Vector(axis).normalized()
    if kind == "bud":
        spiny_bulb(at, axis, 0.009, 0.02, "Bulb", seed, spines=10)
        count["buds"] += 1
        return
    rim = spiny_bulb(at, axis, r.uniform(0.018, 0.02), r.uniform(0.036, 0.04),
                     "Dry" if kind == "fluff" else "Bulb", seed)
    if kind == "fluff":
        # Gone to seed: a loose white tuft spilling out of the bulb
        ww.pompom(sheets["Down"], rim, axis, 0.01, 22, 0.038, 0.008, cutoff=-0.2, profile="taper", segments=2,
                  bend=0.45, lean_up=0.5, seed=seed, t_range=(0.0, 1.0))
        ww.dome(sheets["Down"], rim, axis, 0.015, 0.018, segs=6, seed=seed)
        count["fluff"] += 1
        return
    # The shaving brush: an outer ring of florets flaring up and out, an upright tuft inside, a purple top
    ww.ring(sheets["Floret"], rim, axis, 24, r.uniform(0.04, 0.045), 0.009, cup=0.45, droop=0.12, profile="taper",
            segments=2, spread=0.12, seed=seed)
    ww.pompom(sheets["Floret"], rim, axis, 0.011, 12, 0.036, 0.0085, cutoff=0.35, profile="taper", segments=1,
              lean_up=0.6, seed=seed + 1, t_range=(0.3, 1.0))
    ww.dome(sheets["Floret"], rim, axis, 0.02, 0.026, segs=6, t_range=(0.5, 1.0), seed=seed)
    count["flowers"] += 1


def spiny_leaf(at, direction, length, width, lobes, seed, bend=0.35):
    r = random.Random(seed)
    tips = ww.leaf(sheets["Leaf"], at, direction, length, width, profile="lance", lobes=lobes, lobe_depth=0.48,
                   hook=0.6, bend=bend, fold=0.2, wave=width * 0.12, waves=lobes, twist=r.uniform(-25, 25),
                   seed=seed)
    for k, (p, outward) in enumerate(tips):
        ww.needle(sheets["Spine"], p, outward, r.uniform(0.007, 0.012), 0.0018, seed=seed * 5 + k,
                  t_range=(0.5, 1.0))


crowns = nk.scatter(4, 0.09, seed=2, min_gap=0.06)
kinds = ["flower"] * 10 + ["fluff"] * 2
rnd.shuffle(kinds)
heads = 0
for i, (x, y) in enumerate(crowns):
    h = rnd.uniform(0.6, 1.0)
    a = math.atan2(y, x) + rnd.uniform(-0.5, 0.5)
    lean = rnd.uniform(0.16, 0.34)
    pts = ww.path((x, y, G), (math.cos(a) * lean, math.sin(a) * lean, 1.0), h, 4, bend=0.03, wobble=0.05, seed=i)
    ww.stalk(sheets["Stem"], pts, 0.0062, 0.003, sides=4)
    # Spines along the stem (the real thing has spiny wings)
    for k in range(9):
        p, d = ww.along(pts, rnd.uniform(0.1, 0.9))
        out = ww.perpendicular(d, rnd.uniform(0, math.tau))
        ww.needle(sheets["Spine"], p + out * 0.004, (out + d * 0.7).normalized(), rnd.uniform(0.008, 0.014), 0.002,
                  seed=900 + i * 20 + k)
    # Lobed spiny leaves up the stem, alternate, smaller higher up
    a0 = rnd.uniform(0, math.tau)
    for j, s in enumerate((0.2, 0.36, 0.52, 0.68)):
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, a0 + j * 2.4)
        spiny_leaf(p, (out + d * 0.5).normalized(), 0.17 * (1.0 - s * 0.55), 0.085 * (1.0 - s * 0.4), 3,
                   seed=100 + i * 10 + j)
    top, d = ww.along(pts, 1.0)
    head(top, (d + UP).normalized(), seed=i, kind=kinds[heads])
    heads += 1
    # Forks near the top, each with a head (or a bud)
    for b in range(2):
        s_b = rnd.uniform(0.62, 0.82)
        fork, fd = ww.along(pts, s_b)
        side = ww.perpendicular(fd, rnd.uniform(0, math.tau))
        bpts = ww.path(fork, (fd + side * 0.8).normalized(), rnd.uniform(0.12, 0.22), 2, bend=-0.3, wobble=0.04,
                       seed=40 + i * 3 + b)
        ww.stalk(sheets["Stem"], bpts, 0.0036, 0.0024, t_range=(0.6, 1.0))
        btop, bd = ww.along(bpts, 1.0)
        head(btop, (bd + UP * 1.2).normalized(), seed=20 + i * 3 + b, kind=kinds[heads])
        heads += 1
    # A tight bud on a short stalk off the top of two stems
    if i in (1, 3):
        fork, fd = ww.along(pts, 0.9)
        side = ww.perpendicular(fd, rnd.uniform(0, math.tau))
        bpts = [fork, fork + (fd + side).normalized() * 0.05]
        ww.stalk(sheets["Stem"], bpts, 0.0026, 0.002, t_range=(0.8, 1.0))
        head(bpts[-1], (fd + side * 0.5).normalized(), seed=60 + i, kind="bud")

# The basal rosette: big deeply lobed spiny leaves lying out over the ground
for k in range(7):
    a = k / 7 * math.tau + rnd.uniform(-0.25, 0.25)
    d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.25, 0.55)))
    spiny_leaf((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), G + 0.015), d, rnd.uniform(0.26, 0.34),
               rnd.uniform(0.11, 0.13), 5, seed=500 + k, bend=rnd.uniform(0.4, 0.6))

pieces = ww.build(sheets.values())
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.5, distance=1.9)
print("[%s] done (%d flowers, %d fluff, %d buds)" % (SCRIPT, count["flowers"], count["fluff"], count["buds"]))
