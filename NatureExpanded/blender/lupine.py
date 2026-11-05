"""Lupine (pine forest meadows): a clump of seven dense conical spikes of pea flowers, 50 to 80 cm tall, most of them
purple-blue, one pink and one white, closed buds at their tips; palmate leaves (eight narrow fingers on a long stalk)
low down, meadow grass among them.

Each open flower is an upright banner (pale at its base, the lupine's white blotch) over a folded keel pointing out;
they spiral up the spike, largest at the bottom, round a dark core so the spike reads solid from far off.

    blender -b --factory-startup --python lupine.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "Lupine", "lupine"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(11)
G = nk.GROUND

stem_mat = nk.plant("LupineStem", (0.16, 0.24, 0.1), (0.12, 0.18, 0.08), rough=0.7)
leaf_mat = nk.plant("LupineLeaf", (0.12, 0.21, 0.1), (0.17, 0.25, 0.14), rough=0.7, vary=0.3)
core_mat = nk.plant("LupineCore", (0.12, 0.09, 0.32), (0.08, 0.1, 0.07), rough=0.6, sat=0.9)
grass = nk.grass()

COLORS = {
    "purple": (
        km.ramp_petal("LupineWing", [(0.0, (0.13, 0.09, 0.52)), (1.0, (0.2, 0.17, 0.8))]),
        km.ramp_petal("LupineBanner", [(0.0, (0.8, 0.8, 0.88)), (0.2, (0.5, 0.42, 0.85)), (0.42, (0.2, 0.12, 0.62)),
                                       (1.0, (0.22, 0.13, 0.64))]),
        km.ramp_petal("LupineBud", [(0.0, (0.1, 0.14, 0.07)), (0.55, (0.17, 0.12, 0.38)), (1.0, (0.2, 0.15, 0.5))],
                      sat=0.9),
    ),
    "pink": (
        km.ramp_petal("LupinePinkWing", [(0.0, (0.55, 0.1, 0.26)), (1.0, (0.85, 0.28, 0.48))]),
        km.ramp_petal("LupinePinkBanner", [(0.0, (0.9, 0.86, 0.86)), (0.22, (0.85, 0.45, 0.6)), (0.42, (0.78, 0.18, 0.4)),
                                           (1.0, (0.82, 0.24, 0.45))]),
        km.ramp_petal("LupinePinkBud", [(0.0, (0.12, 0.15, 0.07)), (0.6, (0.5, 0.15, 0.28)), (1.0, (0.6, 0.2, 0.35))],
                      sat=0.9),
    ),
    "white": (
        km.ramp_petal("LupineWhiteWing", [(0.0, (0.66, 0.7, 0.62)), (1.0, (0.9, 0.9, 0.88))]),
        km.ramp_petal("LupineWhiteBanner", [(0.0, (0.88, 0.8, 0.45)), (0.25, (0.88, 0.88, 0.82)), (1.0, (0.93, 0.93, 0.9))]),
        km.ramp_petal("LupineWhiteBud", [(0.0, (0.14, 0.2, 0.08)), (1.0, (0.62, 0.68, 0.55))], sat=0.9),
    ),
}
PLAN = ["purple", "purple", "white", "purple", "pink", "purple", "purple"]

groups = {"spikes": [], "cores": [], "stems": [], "leaves": [], "grass": []}

# The spikes rise from a loose crown near the middle and lean outward, so the color spreads over the block
bases = nk.scatter(len(PLAN), 0.16, seed=5, min_gap=0.06)
for i, ((x, y), color) in enumerate(zip(bases, PLAN)):
    wing, banner, bud = COLORS[color]
    h = rnd.uniform(0.5, 0.8)
    spike = h * rnd.uniform(0.38, 0.46)
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-3 else Vector((1.0, 0.0, 0.0))
    lean = out * rnd.uniform(0.16, 0.28) + Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0.0))
    foot = Vector((x, y, G))
    start = km.inside(foot + lean * (h - spike) * 1.2 + Vector((0.0, 0.0, h - spike)), 0.3)
    pts = km.curve(foot, start, bow=(-lean.x * 0.05, -lean.y * 0.05, 0.0), segments=3, wobble=0.008, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0048, stem_mat, sides=4, tip=0.0036))
    axis = (pts[-1] - pts[-2]).normalized().lerp(Vector((0.0, 0.0, 1.0)), 0.35).normalized()
    count = int(58 + (spike - 0.2) * 120)
    groups["spikes"] += km.pea_spike("Spike%d_" % i, start, axis, spike, wing, banner, bud, count=count,
                                     radius=rnd.uniform(0.036, 0.042), size=rnd.uniform(0.02, 0.023),
                                     open_to=rnd.uniform(0.66, 0.76), seed=i * 7 + 1)
    groups["cores"].append(km.stalk("Core%d" % i, [start - axis * 0.01, start + axis * (spike * 0.5),
                                                   start + axis * (spike * 1.03)], 0.0, core_mat, sides=5,
                                    radii=[0.003, 0.006, 0.0]))
    # A small leaf partway up some stems
    if i % 2 == 0:
        at = pts[1].lerp(pts[2], 0.3)
        a = rnd.uniform(0, math.tau)
        groups["leaves"] += km.palmate("StemLeaf%d" % i, at, (math.cos(a), math.sin(a), 0.5), 0.05, leaf_mat, stem_mat,
                                       fingers=7, finger_len=0.05, finger_w=0.011, seed=i + 40)

# Palmate leaves on long stalks round the crown, low down
for k in range(8):
    a = k / 8 * math.tau + rnd.uniform(-0.3, 0.3)
    at = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), G)
    d = (math.cos(a), math.sin(a), rnd.uniform(0.9, 1.6))
    groups["leaves"] += km.palmate("Leaf%d" % k, at, d, rnd.uniform(0.15, 0.24), leaf_mat, stem_mat,
                                   fingers=rnd.choice((7, 8, 9)), finger_len=rnd.uniform(0.065, 0.09),
                                   finger_w=0.014, droop=0.35, seed=k)

for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=9, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 7, 0.3, grass, seed=k + 3)

km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.38, distance=1.8)
print("[%s] done" % SCRIPT)
