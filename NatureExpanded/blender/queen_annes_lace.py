"""Queen Anne's lace (pine forest meadows): four tall, thin, branching stems 65 to 100 cm, carrying nine flat white lacy
umbels 9 to 12 cm across and two curled-up "bird's nest" seed heads; feathery carrot-like leaves low down, meadow
grass among the stems.

An umbel is 14 to 16 thin rays fanning up and out from the stem's tip to a flat plate of ragged little umbellets
spread evenly over it, the rays showing beneath; about half have the dark purple floret at the center. A bird's nest
is an umbel gone to seed, its rays curled up and in to a brownish-green cup.

The far mesh (kit_lod) keeps every umbellet, grown a little about its own center, and the stems; it drops the rays,
the dark florets, the leaves and the grass.

    blender -b --factory-startup --python queen_annes_lace.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_lod as kl  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "QueenAnnesLace", "queen_annes_lace"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(71)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("LaceStem", (0.16, 0.22, 0.09), (0.12, 0.16, 0.07), rough=0.8)
leaf_mat = nk.plant("LaceLeaf", (0.1, 0.18, 0.06), (0.14, 0.2, 0.08), rough=0.75, vary=0.3)
spoke_mat = nk.plant("LaceSpoke", (0.2, 0.26, 0.12), (0.15, 0.2, 0.09), rough=0.7)
nest_mat = nk.plant("LaceNest", (0.26, 0.22, 0.1), (0.14, 0.13, 0.06), rough=0.85, vary=0.35, scale=60.0)
flower = km.ramp_petal("LaceFlower", [(0.0, (0.8, 0.82, 0.72)), (0.35, (0.86, 0.87, 0.8)), (1.0, (0.93, 0.93, 0.9))],
                       vary=0.3, noise=250.0, rough=0.7)
eye = km.ramp_petal("LaceEye", [(0.0, (0.12, 0.01, 0.05)), (1.0, (0.2, 0.02, 0.1))])
grass = nk.grass()

groups = {"umbels": [], "nests": [], "stems": [], "leaves": [], "grass": []}


def along(pts, s):
    f = s * (len(pts) - 1)
    i = min(len(pts) - 2, int(f))
    return pts[i].lerp(pts[i + 1], f - i), (pts[i + 1] - pts[i]).normalized()


tips = []
for i, (x, y) in enumerate(nk.scatter(4, 0.13, seed=9, min_gap=0.1)):
    h = rnd.uniform(0.68, 0.98)
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-3 else Vector((1.0, 0.0, 0.0))
    lean = out * rnd.uniform(0.08, 0.2) + Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0.0))
    foot = Vector((x, y, G))
    top = foot + lean * h + UP * h
    pts = km.curve(foot, top, bow=(-lean.x * 0.08, -lean.y * 0.08, 0.0), segments=3, wobble=0.012, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0034, stem_mat, sides=4, tip=0.0024))
    tips.append(("main", top, (pts[-1] - pts[-2]).normalized(), rnd.uniform(0.052, 0.06)))
    for b in range(2 if i < 3 else 1):
        s = rnd.uniform(0.55, 0.8)
        p0, tan = along(pts, s)
        a = math.atan2(out.y, out.x) + (b - 0.5) * 2.2 + rnd.uniform(-0.4, 0.4)
        side = Vector((math.cos(a), math.sin(a), 0.0))
        length = h * (1.0 - s) * rnd.uniform(0.75, 1.0) + 0.04
        p1 = km.inside(p0 + side * (length * 0.5) + UP * (length * 0.8), 0.37)
        bpts = km.curve(p0, p1, bow=(side.x * length * 0.1, side.y * length * 0.1, -length * 0.06), segments=2)
        groups["stems"].append(km.stalk("Branch%d_%d" % (i, b), bpts, 0.0022, stem_mat, sides=3, tip=0.0017))
        tips.append(("side", p1, (bpts[-1] - bpts[-2]).normalized(), rnd.uniform(0.042, 0.052)))
    # A small feathery leaf where the stem branches
    p0, tan = along(pts, rnd.uniform(0.3, 0.45))
    a = rnd.uniform(0, math.tau)
    groups["leaves"] += km.pinnate("SLeaf%d" % i, p0, (math.cos(a), math.sin(a), 0.6), 0.08, leaf_mat, stem_mat,
                                   pairs=3, leaflet=0.03, width=0.02, droop=0.3, seed=i + 50)

# Two of the side umbels have gone to seed and curled up into bird's nests
side_tips = [k for k, t in enumerate(tips) if t[0] == "side"]
nests = set(rnd.sample(side_tips, 2))
for j, (kind, top, tan, radius) in enumerate(tips):
    axis = (tan * 0.4 + UP).normalized()
    if j in nests:
        groups["nests"] += km.lace_umbel("Nest%d_" % j, top, axis, radius * 0.85, nest_mat, nest_mat, spokes=12,
                                         lift=0.3, size=0.26, nest=1.0, seed=j + 1, far_scale=1.1)
    else:
        groups["umbels"] += km.lace_umbel("Umbel%d_" % j, top, axis, radius, flower, spoke_mat,
                                          spokes=rnd.choice((15, 16)), lift=0.4, size=0.27, dome_h=0.06,
                                          seed=j + 1, eye_mat=eye if j % 2 == 0 else None,
                                          far_scale=1.15)

# Feathery basal leaves arching out, and meadow grass
for k in range(4):
    a = k / 4 * math.tau + rnd.uniform(-0.4, 0.4)
    at = (rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), G + 0.005)
    groups["leaves"] += km.pinnate("BLeaf%d" % k, at, (math.cos(a), math.sin(a), rnd.uniform(0.9, 1.3)),
                                   rnd.uniform(0.18, 0.24), leaf_mat, stem_mat, pairs=6, leaflet=0.05, width=0.03,
                                   droop=0.45, seed=k)
for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=16, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 6, 0.3, grass, seed=k + 31)

kl.tag(groups["leaves"] + groups["grass"], kl.NEAR)
km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = kl.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.5, distance=2.0)
kl.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.5, distance=2.0)
print("[%s] done" % SCRIPT)
