"""Oxeye daisy (pine forest meadows): a drift of 24 classic white daisies on thin stems 30 to 60 cm tall, two buds and
one spent head among them; dark green toothed leaves low down (spoon-shaped basal rosettes, a few small ones up the
stems), meadow grass among the stems.

Each head is about 5.5 cm across: a ring of 18 to 22 narrow white rays round a flat golden-yellow disc that greens a
little at its middle, a green cup of bracts beneath.

The far mesh (kit_lod) can't afford 20 rays a head, so each open head there is a flat ten-pointed star of white
where its rays are, under its own disc grown a little; it keeps the stems, the buds and one basal rosette, and drops
the cups, the other leaves and the grass.

    blender -b --factory-startup --python oxeye_daisy.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "OxeyeDaisy", "oxeye_daisy"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(31)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stem_mat = nk.plant("DaisyStem", (0.14, 0.22, 0.08), (0.1, 0.16, 0.06), rough=0.7)
leaf_mat = nk.plant("DaisyLeaf", (0.07, 0.15, 0.04), (0.11, 0.19, 0.07), rough=0.6, vary=0.3, wax=True)
cup_mat = nk.plant("DaisyCup", (0.13, 0.2, 0.07), (0.08, 0.1, 0.05), rough=0.6, scale=50.0)
ray = km.ramp_petal("DaisyRay", [(0.0, (0.7, 0.72, 0.55)), (0.22, (0.9, 0.9, 0.86)), (1.0, (0.94, 0.94, 0.91))],
                    vary=0.08)
disc = km.ramp_petal("DaisyDisc", [(0.0, (0.95, 0.58, 0.02)), (0.65, (0.92, 0.62, 0.02)), (1.0, (0.5, 0.52, 0.05))],
                     rough=0.7, vary=0.2, noise=120.0)
spent_disc = km.ramp_petal("DaisySpentDisc", [(0.0, (0.45, 0.3, 0.05)), (1.0, (0.35, 0.32, 0.08))], rough=0.8,
                           sat=0.8)
spent_ray = km.ramp_petal("DaisySpentRay", [(0.0, (0.45, 0.4, 0.25)), (1.0, (0.62, 0.58, 0.48))], sat=0.7)
grass = nk.grass()

groups = {"heads": [], "stems": [], "leaves": [], "grass": []}
RAY_ROWS = [(0.0, 0.45), (0.25, 1.0), (1.0, 0.75)]


def head(name, top, axis, seed):
    r = random.Random(seed)
    cup = km.stalk(name + "Cup", [top - axis * 0.006, top], 0.0, cup_mat, sides=4, radii=[0.0018, 0.0082])
    rays = km.ray_ring(name + "R", top + axis * 0.0015, axis, r.randint(18, 22), 0.021, 0.0068, ray, RAY_ROWS,
                       cup=r.uniform(0.0, 0.1), droop=r.uniform(0.08, 0.25), offset=0.0065, seed=seed, jitter=0.25,
                       vary=0.12, twist=20.0)
    centre = km.dome(name + "D", top + axis * 0.0015, axis, 0.0092, 0.0025, disc, sides=10, rings=1)
    # The far mesh's stand-in for the rays: a flat star of white just under the disc, a touch wider than the rays
    star = km.dome(name + "Star", top + axis * 0.0008, axis, 0.026, 0.0, ray, sides=20, rings=1, jag=0.2, seed=seed)
    kl.tag([cup] + rays, kl.NEAR)
    kl.tag([centre], kl.BOTH, scale=1.1, pivot=top)
    kl.tag([star], kl.FAR)
    return [cup] + rays + [centre, star]


def spent(name, top, axis, seed):
    parts = [km.stalk(name + "Cup", [top - axis * 0.006, top], 0.0, cup_mat, sides=4, radii=[0.0018, 0.0075])]
    parts += km.ray_ring(name + "R", top, axis, 5, 0.017, 0.005, spent_ray, RAY_ROWS, cup=-0.85, droop=0.1,
                         offset=0.006, seed=seed, jitter=0.4, vary=0.2, twist=40.0)
    kl.tag(parts, kl.NEAR)
    parts.append(km.dome(name + "D", top + axis * 0.001, axis, 0.0078, 0.006, spent_disc, sides=9, rings=1))
    return parts


def bud(name, top, axis):
    return [kl.tag([km.stalk(name + "Cup", [top - axis * 0.005, top], 0.0, cup_mat, sides=4,
                             radii=[0.0018, 0.0062])], kl.NEAR)[0],
            kl.tag([km.dome(name + "D", top, axis, 0.0062, 0.0055, cup_mat, sides=7, rings=2)], scale=1.15)[0]]


# Heads spread over the block, each stem rising from nearer the middle, so the stems lean out under them
spots = nk.scatter(27, 0.37, seed=6, min_gap=0.055)
for i, (x, y) in enumerate(spots):
    h = rnd.uniform(0.28, 0.55)
    top = Vector((x, y, G + h))
    foot = Vector((x * rnd.uniform(0.35, 0.6) + rnd.uniform(-0.03, 0.03),
                   y * rnd.uniform(0.35, 0.6) + rnd.uniform(-0.03, 0.03), G))
    lean = Vector((top.x - foot.x, top.y - foot.y, 0.0))
    pts = km.curve(foot, top, bow=(-lean.x * 0.25, -lean.y * 0.25, 0.0), segments=3, wobble=0.008, rnd=rnd)
    groups["stems"].append(km.stalk("Stem%d" % i, pts, 0.0017, stem_mat, sides=3, tip=0.0012))
    tan = (pts[-1] - pts[-2]).normalized()
    # Facing up, tipped 10 to 35 degrees outward: tipped further, the ones facing away show their shaded backs
    flat = lean.normalized() if lean.length > 1e-3 else Vector((1.0, 0.0, 0.0))
    tilt = math.radians(rnd.uniform(10, 35))
    axis = (UP * math.cos(tilt) + flat * math.sin(tilt)).normalized()
    if i == 24:
        groups["heads"] += spent("Spent%d" % i, top, (tan + UP).normalized(), seed=i)
    elif i > 24:
        groups["heads"] += bud("Bud%d" % i, top, tan)
    else:
        groups["heads"] += head("Head%d_" % i, top, axis, seed=i * 3 + 1)
    # A small clasping toothed leaf low on a few stems
    if i % 4 == 0:
        p0 = pts[0].lerp(pts[1], rnd.uniform(0.4, 0.9))
        a = rnd.uniform(0, math.tau)
        d = (Vector((math.cos(a), math.sin(a), 0.0)) * 0.7 + tan).normalized()
        groups["leaves"] += kl.tag([km.sheet("SLeaf%d" % i, p0, d, rnd.uniform(0.03, 0.045), 0.011, leaf_mat,
                                             [(0.0, 0.55), (0.3, 1.0), (0.55, 0.72), (0.72, 0.85), (1.0, 0.0)],
                                             bend=0.25, twist=rnd.uniform(-30, 30))], kl.NEAR)

# Basal rosettes of long-stalked, spoon-shaped, toothed leaves
LEAF_ROWS = [(0.0, 0.12), (0.35, 0.18), (0.48, 0.62), (0.56, 0.48), (0.65, 0.88), (0.73, 0.68), (0.82, 0.98),
             (0.9, 0.72), (1.0, 0.0)]
for k, (x, y) in enumerate(((-0.1, 0.08), (0.12, 0.02), (-0.02, -0.13))):
    for j in range(4):
        a = j / 4 * math.tau + rnd.uniform(-0.4, 0.4)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.3, 0.6)))
        groups["leaves"] += kl.tag([km.sheet("Leaf%d_%d" % (k, j), (x, y, G + 0.005), d, rnd.uniform(0.08, 0.12),
                                             0.024, leaf_mat, LEAF_ROWS, bend=0.45, twist=rnd.uniform(-20, 20))],
                                   kl.BOTH if k == 0 else kl.NEAR)

for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=12, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 6, 0.26, grass, seed=k + 7)

kl.tag(groups["grass"], kl.NEAR)
km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = kl.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.28, distance=1.3)
kl.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.28, distance=1.3)
print("[%s] done" % SCRIPT)
