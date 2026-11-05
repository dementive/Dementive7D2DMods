"""Cornflower (pine forest meadows): a clump of wiry, branching grey-green stems 40 to 60 cm tall carrying 22 ragged
bright blue heads and a few scaly buds, narrow grey-green leaves, meadow grass among them.

Each head is a ring of seven to nine frilled florets (funnels flaring into a toothed trumpet mouth) spreading round a
darker purple-blue tuft of inner florets, on a grey-green scaly urn.

    blender -b --factory-startup --python cornflower.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "Cornflower", "cornflower"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(21)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("CornflowerStem", (0.22, 0.28, 0.17), (0.15, 0.19, 0.12), rough=0.75, sat=0.7)
leaf_mat = nk.plant("CornflowerLeaf", (0.2, 0.27, 0.16), (0.25, 0.3, 0.21), rough=0.75, vary=0.3, sat=0.7)
urn_mat = nk.plant("CornflowerUrn", (0.2, 0.25, 0.15), (0.07, 0.08, 0.05), rough=0.6, vary=0.4, scale=60.0, sat=0.75)
floret = km.ramp_petal("CornflowerFloret", [(0.0, (0.4, 0.48, 0.78)), (0.3, (0.07, 0.17, 0.78)),
                                            (1.0, (0.03, 0.11, 0.86))], vary=0.15)
center = km.ramp_petal("CornflowerCenter", [(0.0, (0.02, 0.015, 0.07)), (0.35, (0.03, 0.02, 0.12)),
                                            (1.0, (0.08, 0.05, 0.33))])
grass = nk.grass()

groups = {"heads": [], "buds": [], "stems": [], "leaves": [], "grass": []}


def head(name, top, axis, seed):
    r = random.Random(seed)
    parts = [km.stalk(name + "Urn", [top - axis * 0.013, top + axis * 0.002], 0.0, urn_mat, sides=5,
                      radii=[0.0032, 0.0068])]
    parts += km.ray_ring(name + "F", top + axis * 0.002, axis, r.choice((8, 8, 9)), 0.021, 0.0145, floret,
                         [(0.0, 0.15), (0.7, 1.0)], cup=r.uniform(0.1, 0.25), droop=0.12, offset=0.0035, seed=seed,
                         jitter=0.25, vary=0.15, fold=0.7, teeth=4, tooth=0.3, notch=0.3, twist=25.0)
    parts.append(km.dome(name + "C", top + axis * 0.004, axis, 0.0078, 0.0055, center, sides=7, rings=1, jag=0.35,
                         seed=seed))
    return parts


def bud(name, top, axis):
    return [km.stalk(name, [top - axis * 0.01, top, top + axis * 0.009], 0.0, urn_mat, sides=5,
                     radii=[0.003, 0.0055, 0.0])]


def along(pts, s):
    """A point and the direction a fraction `s` of the way up a polyline."""
    f = s * (len(pts) - 1)
    i = min(len(pts) - 2, int(f))
    return pts[i].lerp(pts[i + 1], f - i), (pts[i + 1] - pts[i]).normalized()


tips = []
crowns = nk.scatter(6, 0.15, seed=4, min_gap=0.07)
for i, (x, y) in enumerate(crowns):
    h = rnd.uniform(0.42, 0.58)
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-3 else Vector((0.0, 1.0, 0.0))
    lean = out * rnd.uniform(0.08, 0.2) + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0.0))
    foot = Vector((x, y, G))
    top = foot + lean * h + UP * h
    pts = km.curve(foot, top, bow=(-lean.x * 0.08, -lean.y * 0.08, 0.0), segments=3, wobble=0.01, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0024, stem_mat, sides=3, tip=0.0017))
    tips.append((top, (pts[-1] - pts[-2]).normalized(), out))
    # Branches from the upper half, each curving up to its own head
    nb = rnd.choice((3, 3, 4))
    for b in range(nb):
        s = rnd.uniform(0.5, 0.85)
        p0, tan = along(pts, s)
        a = math.atan2(out.y, out.x) + (b - (nb - 1) / 2) * 1.5 + rnd.uniform(-0.4, 0.4)
        side = Vector((math.cos(a), math.sin(a), 0.0))
        length = h * (1.0 - s) * rnd.uniform(0.7, 1.1) + 0.04
        p1 = km.inside(p0 + side * (length * 0.45) + UP * (length * 0.85), 0.39)
        bpts = km.curve(p0, p1, bow=(side.x * length * 0.12, side.y * length * 0.12, -length * 0.08), segments=2)
        groups["stems"].append(km.stalk("Branch%d_%d" % (i, b), bpts, 0.0017, stem_mat, sides=3, tip=0.0013))
        tips.append((p1, (bpts[-1] - bpts[-2]).normalized(), side))
        # A narrow leaf where the branch leaves the stem
        ld = (side * 0.8 + tan).normalized()
        groups["leaves"].append(km.sheet("BrLeaf%d_%d" % (i, b), p0, ld, rnd.uniform(0.035, 0.06), 0.006, leaf_mat,
                                         [(0.0, 0.6), (0.35, 1.0), (1.0, 0.0)], bend=0.3,
                                         twist=rnd.uniform(-40, 40)))
    # Narrow leaves up the main stem, longer low down
    for k in range(5):
        s = 0.12 + k * 0.15 + rnd.uniform(-0.03, 0.03)
        p0, tan = along(pts, s)
        a = rnd.uniform(0, math.tau)
        d = (Vector((math.cos(a), math.sin(a), 0.0)) * 0.6 + tan).normalized()
        groups["leaves"].append(km.sheet("SLeaf%d_%d" % (i, k), p0, d, rnd.uniform(0.05, 0.1) * (1.2 - s), 0.007,
                                         leaf_mat, [(0.0, 0.6), (0.35, 1.0), (1.0, 0.0)], bend=0.3,
                                         twist=rnd.uniform(-40, 40)))

# Heads on most tips (facing up, tipped out with the stem), buds on a few
rnd.shuffle(tips)
for j, (top, tan, out) in enumerate(tips):
    axis = (tan * 0.5 + UP * 0.8 + out * rnd.uniform(0.2, 0.5)).normalized()
    if j >= 22:
        groups["buds"] += bud("Bud%d" % j, top, tan)
    else:
        groups["heads"] += head("Head%d_" % j, top, axis, seed=j * 5 + 2)

# Long narrow basal leaves and meadow grass
for k in range(9):
    a = k / 9 * math.tau + rnd.uniform(-0.3, 0.3)
    at = (rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), G + 0.005)
    groups["leaves"].append(km.sheet("BLeaf%d" % k, at, (math.cos(a), math.sin(a), rnd.uniform(0.6, 1.2)),
                                     rnd.uniform(0.09, 0.14), 0.009, leaf_mat, [(0.0, 0.5), (0.3, 1.0), (1.0, 0.0)],
                                     bend=0.5, twist=rnd.uniform(-30, 30)))
for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=8, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 6, 0.26, grass, seed=k + 5)

km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.3, distance=1.4)
print("[%s] done" % SCRIPT)
