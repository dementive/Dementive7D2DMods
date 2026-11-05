"""Purple coneflower (pine forest meadows): a clump of stout stems 60 to 90 cm tall, a few branching, carrying 11
pink-purple heads, one bud and one old head going over; dark lance leaves up the stems and round the base, meadow
grass among them.

Each head is 9 to 10 cm across: 13 to 16 long pink-purple rays (deeper magenta at their base, notched at their tips)
starting a little below level and drooping well down, back behind the head, round a big spiky orange-brown cone, a
green cup of bracts beneath.

    blender -b --factory-startup --python coneflower.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "Coneflower", "coneflower"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(61)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("ConeflowerStem", (0.15, 0.2, 0.07), (0.2, 0.1, 0.08), rough=0.8)
leaf_mat = nk.plant("ConeflowerLeaf", (0.06, 0.12, 0.035), (0.09, 0.15, 0.05), rough=0.75, vary=0.3)
cup_mat = nk.plant("ConeflowerCup", (0.1, 0.17, 0.05), (0.07, 0.1, 0.04), rough=0.7, scale=50.0)
ray = km.ramp_petal("ConeflowerRay", [(0.0, (0.36, 0.025, 0.19)), (0.35, (0.55, 0.08, 0.33)),
                                      (1.0, (0.63, 0.15, 0.43))], vary=0.12)
old_ray = km.ramp_petal("ConeflowerOldRay", [(0.0, (0.3, 0.06, 0.14)), (1.0, (0.5, 0.3, 0.38))], sat=0.75)
cone = km.ramp_petal("ConeflowerCone", [(0.0, (0.07, 0.018, 0.006)), (0.35, (0.1, 0.025, 0.008)),
                                        (1.0, (0.74, 0.27, 0.02))], rough=0.7, vary=0.2, noise=120.0)
bud_cone = km.ramp_petal("ConeflowerBudCone", [(0.0, (0.08, 0.12, 0.03)), (0.35, (0.1, 0.14, 0.04)),
                                               (1.0, (0.45, 0.35, 0.05))], rough=0.7, sat=0.85)
grass = nk.grass()

groups = {"heads": [], "stems": [], "leaves": [], "grass": []}
RAY_ROWS = [(0.0, 0.3), (0.3, 0.85), (0.9, 0.95)]
LEAF_ROWS = [(0.0, 0.25), (0.3, 1.0), (0.7, 0.7), (1.0, 0.0)]


def head(name, top, axis, seed):
    r = random.Random(seed)
    parts = [km.stalk(name + "Cup", [top - axis * 0.008, top], 0.0, cup_mat, sides=6, radii=[0.004, 0.013])]
    parts += km.ray_ring(name + "R", top + axis * 0.002, axis, r.randint(13, 16), 0.045, 0.012, ray, RAY_ROWS,
                         cup=r.uniform(-0.12, -0.04), droop=r.uniform(0.32, 0.45), reflex=0.6, offset=0.011, seed=seed,
                         jitter=0.18, vary=0.1, teeth=2, tooth=0.1, notch=0.3, twist=20.0)
    parts.append(km.dome(name + "Cone", top + axis * 0.001, axis, 0.0155, 0.017, cone, sides=12, rings=3, jag=0.2,
                         seed=seed))
    return parts


def old(name, top, axis, seed):
    parts = [km.stalk(name + "Cup", [top - axis * 0.008, top], 0.0, cup_mat, sides=6, radii=[0.004, 0.012])]
    parts += km.ray_ring(name + "R", top, axis, 11, 0.036, 0.009, old_ray, RAY_ROWS, cup=-0.7, droop=0.2,
                         reflex=0.8, offset=0.01, seed=seed, jitter=0.35, vary=0.15, teeth=2, tooth=0.1, twist=40.0)
    parts.append(km.dome(name + "Cone", top, axis, 0.015, 0.019, cone, sides=12, rings=3, jag=0.24, seed=seed))
    return parts


def bud(name, top, axis, seed):
    return [km.stalk(name + "Cup", [top - axis * 0.007, top], 0.0, cup_mat, sides=6, radii=[0.004, 0.011]),
            km.dome(name + "Cone", top, axis, 0.011, 0.012, bud_cone, sides=8, rings=2, jag=0.25, seed=seed)]


def along(pts, s):
    f = s * (len(pts) - 1)
    i = min(len(pts) - 2, int(f))
    return pts[i].lerp(pts[i + 1], f - i), (pts[i + 1] - pts[i]).normalized()


tips = []
for i, (x, y) in enumerate(nk.scatter(5, 0.14, seed=5, min_gap=0.08)):
    h = rnd.uniform(0.6, 0.88)
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-3 else Vector((0.0, 1.0, 0.0))
    lean = out * rnd.uniform(0.08, 0.2) + Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0.0))
    foot = Vector((x, y, G))
    top = foot + lean * h + UP * h
    pts = km.curve(foot, top, bow=(-lean.x * 0.06, -lean.y * 0.06, 0.0), segments=3, wobble=0.01, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0046, stem_mat, sides=4, tip=0.0036))
    tips.append((top, (pts[-1] - pts[-2]).normalized(), out))
    for b in range(rnd.choice((1, 2, 2))):
        s = rnd.uniform(0.45, 0.75)
        p0, tan = along(pts, s)
        a = math.atan2(out.y, out.x) + (b - 0.5) * 2.0 + rnd.uniform(-0.5, 0.5)
        side = Vector((math.cos(a), math.sin(a), 0.0))
        length = h * (1.0 - s) * rnd.uniform(0.7, 1.0) + 0.05
        p1 = km.inside(p0 + side * (length * 0.5) + UP * (length * 0.8), 0.37)
        bpts = km.curve(p0, p1, bow=(side.x * length * 0.1, side.y * length * 0.1, -length * 0.08), segments=2)
        groups["stems"].append(km.stalk("Branch%d_%d" % (i, b), bpts, 0.0035, stem_mat, sides=4, tip=0.003))
        tips.append((p1, (bpts[-1] - bpts[-2]).normalized(), side))
        groups["leaves"].append(km.sheet("BrLeaf%d_%d" % (i, b), p0, (side * 0.8 + tan).normalized(),
                                         rnd.uniform(0.06, 0.08), 0.017, leaf_mat, LEAF_ROWS, bend=0.35,
                                         twist=rnd.uniform(-30, 30)))
    for k in range(3):
        s = 0.12 + k * 0.15 + rnd.uniform(-0.03, 0.03)
        p0, tan = along(pts, s)
        a = rnd.uniform(0, math.tau)
        d = (Vector((math.cos(a), math.sin(a), 0.0)) * 0.8 + tan).normalized()
        groups["leaves"].append(km.sheet("SLeaf%d_%d" % (i, k), p0, d, rnd.uniform(0.08, 0.11), 0.024, leaf_mat,
                                         LEAF_ROWS, bend=0.4, twist=rnd.uniform(-30, 30)))

rnd.shuffle(tips)
for j, (top, tan, out) in enumerate(tips):
    axis = (tan * 0.5 + UP * 0.8 + out * rnd.uniform(0.2, 0.5)).normalized()
    if j < 11:
        groups["heads"] += head("Head%d_" % j, top, axis, seed=j * 11 + 4)
    elif j == 11:
        groups["heads"] += old("Old%d_" % j, top, axis, seed=j)
    else:
        groups["heads"] += bud("Bud%d_" % j, top, tan, seed=j)

for k in range(7):
    a = k / 7 * math.tau + rnd.uniform(-0.3, 0.3)
    at = (rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), G + 0.005)
    groups["leaves"].append(km.sheet("BLeaf%d" % k, at, (math.cos(a), math.sin(a), rnd.uniform(0.6, 1.0)),
                                     rnd.uniform(0.12, 0.16), 0.04, leaf_mat, LEAF_ROWS, bend=0.5,
                                     twist=rnd.uniform(-20, 20)))
for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=15, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 7, 0.3, grass, seed=k + 21)

km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.42, distance=1.8)
print("[%s] done" % SCRIPT)
