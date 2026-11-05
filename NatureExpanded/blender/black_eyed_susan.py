"""Black-eyed Susan (pine forest meadows): a clump of rough, branching stems 40 to 70 cm tall carrying 18 golden-orange
heads and a couple of green buds; lance leaves up the stems and round the base, meadow grass among them.

Each head is about 7.5 cm across: 12 to 14 broad golden-orange rays, deeper orange at their base and notched at their
tips, drooping a little, round a raised dark chocolate-brown dome, a green cup of bracts beneath.

    blender -b --factory-startup --python black_eyed_susan.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "BlackEyedSusan", "black_eyed_susan"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(51)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("SusanStem", (0.14, 0.2, 0.07), (0.13, 0.14, 0.06), rough=0.85)
leaf_mat = nk.plant("SusanLeaf", (0.1, 0.17, 0.05), (0.14, 0.2, 0.08), rough=0.85, vary=0.3)
cup_mat = nk.plant("SusanCup", (0.12, 0.19, 0.06), (0.08, 0.11, 0.04), rough=0.8, scale=50.0)
ray = km.ramp_petal("SusanRay", [(0.0, (0.74, 0.15, 0.0)), (0.3, (0.93, 0.32, 0.0)), (1.0, (0.95, 0.42, 0.005))],
                    vary=0.1)
eye = km.ramp_petal("SusanEye", [(0.0, (0.022, 0.009, 0.004)), (0.35, (0.03, 0.012, 0.005)),
                                 (1.0, (0.075, 0.032, 0.012))], rough=0.8, vary=0.25, noise=150.0)
grass = nk.grass()

groups = {"heads": [], "buds": [], "stems": [], "leaves": [], "grass": []}
RAY_ROWS = [(0.0, 0.35), (0.25, 0.85), (0.88, 1.0)]
LEAF_ROWS = [(0.0, 0.3), (0.3, 1.0), (0.7, 0.7), (1.0, 0.0)]


def head(name, top, axis, seed):
    r = random.Random(seed)
    parts = [km.stalk(name + "Cup", [top - axis * 0.007, top], 0.0, cup_mat, sides=5, radii=[0.0025, 0.009])]
    parts += km.ray_ring(name + "R", top + axis * 0.001, axis, r.randint(12, 14), 0.031, 0.0118, ray, RAY_ROWS,
                         cup=r.uniform(-0.08, 0.02), droop=r.uniform(0.25, 0.4), offset=0.0075, seed=seed,
                         jitter=0.15, vary=0.08, teeth=2, tooth=0.12, notch=0.3, twist=15.0)
    parts.append(km.dome(name + "Eye", top + axis * 0.001, axis, 0.0098, 0.0095, eye, sides=9, rings=2, jag=0.08,
                         seed=seed))
    return parts


def bud(name, top, axis, seed):
    return [km.stalk(name + "Cup", [top - axis * 0.006, top], 0.0, cup_mat, sides=5, radii=[0.0025, 0.007]),
            km.dome(name + "D", top, axis, 0.0075, 0.007, cup_mat, sides=7, rings=2, jag=0.3, seed=seed)]


def along(pts, s):
    f = s * (len(pts) - 1)
    i = min(len(pts) - 2, int(f))
    return pts[i].lerp(pts[i + 1], f - i), (pts[i + 1] - pts[i]).normalized()


tips = []
for i, (x, y) in enumerate(nk.scatter(6, 0.15, seed=7, min_gap=0.07)):
    h = rnd.uniform(0.42, 0.68)
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-3 else Vector((0.0, 1.0, 0.0))
    lean = out * rnd.uniform(0.1, 0.22) + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0.0))
    foot = Vector((x, y, G))
    top = foot + lean * h + UP * h
    pts = km.curve(foot, top, bow=(-lean.x * 0.08, -lean.y * 0.08, 0.0), segments=3, wobble=0.01, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0032, stem_mat, sides=3, tip=0.0024))
    tips.append((top, (pts[-1] - pts[-2]).normalized(), out))
    for b in range(rnd.choice((2, 2, 3))):
        s = rnd.uniform(0.5, 0.8)
        p0, tan = along(pts, s)
        a = math.atan2(out.y, out.x) + (b - 0.5) * 1.8 + rnd.uniform(-0.5, 0.5)
        side = Vector((math.cos(a), math.sin(a), 0.0))
        length = h * (1.0 - s) * rnd.uniform(0.75, 1.1) + 0.05
        p1 = km.inside(p0 + side * (length * 0.5) + UP * (length * 0.8), 0.37)
        bpts = km.curve(p0, p1, bow=(side.x * length * 0.1, side.y * length * 0.1, -length * 0.08), segments=2)
        groups["stems"].append(km.stalk("Branch%d_%d" % (i, b), bpts, 0.0024, stem_mat, sides=3, tip=0.002))
        tips.append((p1, (bpts[-1] - bpts[-2]).normalized(), side))
        groups["leaves"].append(km.sheet("BrLeaf%d_%d" % (i, b), p0, (side * 0.8 + tan).normalized(),
                                         rnd.uniform(0.04, 0.06), 0.014, leaf_mat, LEAF_ROWS, bend=0.3,
                                         twist=rnd.uniform(-30, 30)))
    for k in range(3):
        s = 0.12 + k * 0.17 + rnd.uniform(-0.03, 0.03)
        p0, tan = along(pts, s)
        a = rnd.uniform(0, math.tau)
        d = (Vector((math.cos(a), math.sin(a), 0.0)) * 0.8 + tan).normalized()
        groups["leaves"].append(km.sheet("SLeaf%d_%d" % (i, k), p0, d, rnd.uniform(0.06, 0.09), 0.018, leaf_mat,
                                         LEAF_ROWS, bend=0.35, twist=rnd.uniform(-30, 30)))

rnd.shuffle(tips)
for j, (top, tan, out) in enumerate(tips):
    axis = (tan * 0.5 + UP * 0.8 + out * rnd.uniform(0.25, 0.6)).normalized()
    if j >= 18:
        groups["buds"] += bud("Bud%d" % j, top, tan, seed=j)
    else:
        groups["heads"] += head("Head%d_" % j, top, axis, seed=j * 7 + 3)

for k in range(8):
    a = k / 8 * math.tau + rnd.uniform(-0.3, 0.3)
    at = (rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), G + 0.005)
    groups["leaves"].append(km.sheet("BLeaf%d" % k, at, (math.cos(a), math.sin(a), rnd.uniform(0.5, 0.9)),
                                     rnd.uniform(0.1, 0.14), 0.026, leaf_mat, LEAF_ROWS, bend=0.5,
                                     twist=rnd.uniform(-20, 20)))
for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=13, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 7, 0.28, grass, seed=k + 17)

km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.33, distance=1.5)
print("[%s] done" % SCRIPT)
