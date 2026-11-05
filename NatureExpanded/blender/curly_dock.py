"""CurlyDock (wasteland): curly dock gone to seed, three stout stalks 60 to 100 cm rising from a rosette of long
wavy-edged leaves that go red at the base (a couple of older ones turning red-brown all over). The top half of each
stalk is a narrow panicle: upright branches crowded with whorls of papery seeds, rust-red at the top darkening to
chocolate lower down, the color the plant is for. No grass: it grows on bare waste ground.

    blender -b --factory-startup --python curly_dock.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "CurlyDock", "curly_dock"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(31)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stalkm = nk.plant("DockStalk", (0.24, 0.1, 0.05), (0.16, 0.14, 0.07), rough=0.7, vary=0.35)
leafm = ww.leaf_mat("DockLeaf", (0.11, 0.19, 0.06), (0.15, 0.2, 0.08), base=(0.32, 0.06, 0.03), base_to=0.35,
                    rib=(0.36, 0.1, 0.05), rough=0.6)
oldm = ww.leaf_mat("DockLeafOld", (0.3, 0.12, 0.04), (0.22, 0.16, 0.06), base=(0.3, 0.05, 0.03), base_to=0.4,
                   rib=(0.35, 0.08, 0.04), rough=0.7)
seedm = nk.petal("DockSeed", (0.09, 0.03, 0.012), (0.42, 0.065, 0.022), mid=(0.24, 0.045, 0.018), vary=0.25,
                 sat=1.0, value=0.95)

sheets = {k: ww.Sheet("Dock" + k, m) for k, m in (("Stalk", stalkm), ("Leaf", leafm), ("Old", oldm),
                                                 ("Seed", seedm))}
count = {"whorls": 0}


def seeds(pts, s0, spacing, ripe, seed, size=1.0):
    """Whorls of seeds every `spacing` meters along a stem from `s0` to its tip; `ripe` 0 (chocolate) to 1 (rust)
    at the tip, darker further down."""
    r = random.Random(seed)
    length = sum((Vector(b) - Vector(a)).length for a, b in zip(pts, pts[1:]))
    n = max(2, int(length * (1.0 - s0) / spacing))
    for k in range(n):
        s = s0 + (1.0 - s0) * (k + r.uniform(0.2, 0.8)) / n
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, r.uniform(0, math.tau))
        t = max(0.0, min(1.0, ripe - (1.0 - s) * 0.9 + r.uniform(-0.18, 0.18)))
        k_size = size * (1.0 - 0.25 * s) * r.uniform(0.85, 1.15)
        ww.ball(sheets["Seed"], p + out * 0.003, (d + out * 0.3).normalized(), 0.0095 * k_size, 0.014 * k_size,
                segs=3, rings=1, t_range=(t, t), seed=seed * 13 + k, rough=0.15)
        count["whorls"] += 1


def wavy_leaf(at, direction, length, width, seed, old=False, bend=0.5):
    r = random.Random(seed)
    ww.leaf(sheets["Old" if old else "Leaf"], at, direction, length, width, profile="willow", segments=10,
            bend=bend, fold=0.12, wave=width * r.uniform(0.09, 0.12), waves=r.uniform(3.0, 3.4),
            twist=r.uniform(-8, 8), seed=seed)


crowns = nk.scatter(3, 0.06, seed=5, min_gap=0.04)
for i, (x, y) in enumerate(crowns):
    h = (0.98, 0.78, 0.64)[i] * rnd.uniform(0.95, 1.03)
    a = math.atan2(y, x) + rnd.uniform(-0.4, 0.4)
    lean = rnd.uniform(0.08, 0.2)
    pts = ww.path((x, y, G), (math.cos(a) * lean, math.sin(a) * lean, 1.0), h, 6, bend=0.03, wobble=0.04, seed=i)
    ww.stalk(sheets["Stalk"], pts, 0.0055, 0.0022, sides=4)
    # The panicle: seeds crowding the main stalk's top half and its upright branches
    seeds(pts, 0.5, 0.0085, 1.0, seed=i, size=1.1)
    nb = 8
    for b in range(nb):
        s_b = 0.44 + 0.42 * (b + rnd.uniform(0.0, 0.6)) / nb
        fork, fd = ww.along(pts, s_b)
        side = ww.perpendicular(fd, b * 2.4 + rnd.uniform(-0.4, 0.4))
        blen = rnd.uniform(0.15, 0.24) * (1.2 - s_b)
        bpts = ww.path(fork, (fd + side * rnd.uniform(0.4, 0.6)).normalized(), blen, 2, bend=-0.15, wobble=0.04,
                       seed=40 + i * 10 + b)
        ww.stalk(sheets["Stalk"], bpts, 0.0022, 0.0012, t_range=(0.6, 1.0))
        seeds(bpts, 0.1, 0.0088, 0.85 + 0.15 * s_b, seed=100 + i * 10 + b)
    # A few narrow wavy leaves low on the stalk
    for j, s in enumerate((0.1, 0.24)):
        p, d = ww.along(pts, s)
        out = ww.perpendicular(d, rnd.uniform(0, math.tau))
        wavy_leaf(p, (out + d * 0.6).normalized(), 0.2 * (1.0 - s), 0.05 * (1.0 - s), seed=200 + i * 10 + j,
                  bend=0.35)

# The rosette: long wavy-edged leaves arching out over the ground, red at the base, two old ones red all over
for k in range(8):
    a = k / 8 * math.tau + rnd.uniform(-0.25, 0.25)
    d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.35, 0.7)))
    wavy_leaf((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), G + 0.01), d, rnd.uniform(0.28, 0.36),
              rnd.uniform(0.07, 0.085), seed=500 + k, old=k in (2, 6), bend=rnd.uniform(0.4, 0.6))

pieces = ww.build(sheets.values())
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.45, distance=1.8)
print("[%s] done (%d seed whorls)" % (SCRIPT, count["whorls"]))
