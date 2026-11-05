"""WildStrawberry (forest floor and edges, food): a low mat of wild strawberry 10 to 15 cm high from three crowns.
Eighteen trefoil leaves on hairy reddish stalks, each of three toothed leaflets folded along the midrib; four small
white five-petalled flowers with yellow centers held just above; and fourteen small, glossy, bright red berries
(a couple still pale) dangling on thin arching stalks round the edge of the mat, where they show, and one truss held up
through the leaves. No grass.

The far mesh (kit_lod) keeps every berry and flower, grown a little about their centers, and the berry trusses and
flower stalks; of the leaves it keeps the middle leaflet of most trefoils, grown to cover for the other two, and drops
the side leaflets, the leaf stalks, the calyxes and the berries' own thin stalks.

    blender -b --factory-startup --python wild_strawberry.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_lod as kl  # noqa: E402

NAME, SCRIPT = "WildStrawberry", "wild_strawberry"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(51)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = nk.plant("StrawberryLeaf", (0.06, 0.15, 0.035), (0.09, 0.18, 0.05), rough=0.55, vary=0.25)
stalk = nk.plant("StrawberryStalk", (0.14, 0.15, 0.06), (0.22, 0.09, 0.05), rough=0.65)
ripe = kf.berry("StrawberryRipe", (0.6, 0.012, 0.01), (0.7, 0.09, 0.035))
unripe = kf.berry("StrawberryUnripe", (0.62, 0.66, 0.42), (0.45, 0.55, 0.3), seed_color=(0.5, 0.45, 0.15))
calyx = nk.plant("StrawberryCalyx", (0.08, 0.17, 0.04), (0.1, 0.19, 0.05))
petal = nk.petal("StrawberryPetal", (0.82, 0.84, 0.74), (0.94, 0.94, 0.92), sat=1.0, value=0.97)
center = kf.fungus("StrawberryCenter", (0.55, 0.5, 0.08), (0.78, 0.62, 0.06), rough=0.7, vary=0.3, scale=200.0,
                   bump=0.3)

pieces = []


def trefoil(name, crown, heading, height, reach, leaflet, seed):
    r = random.Random(seed)
    hd = Vector((math.cos(heading), math.sin(heading), 0.0))
    c = Vector(crown)
    tip = c + hd * reach + Z * (height * 0.9)
    pts = [c, c + hd * reach * 0.15 + Z * height * 0.65, c + hd * reach * 0.6 + Z * height, tip]
    parts = [kf.taper_tube(name + "Stalk", pts, (0.0018, 0.0013), stalk, sides=4)]
    for k, ang in enumerate((-60.0, 0.0, 60.0)):
        a = heading + math.radians(ang + r.uniform(-8.0, 8.0))
        e = math.radians(r.uniform(0.0, 16.0))
        d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        L = leaflet * (1.0 if k == 1 else 0.88) * r.uniform(0.92, 1.08)
        parts.append(kf.leaf(name + "Leaflet%d" % k, tip, d, L, L * 0.68, leaf_mat, "obovate", segments=8, bend=0.2,
                             fold=0.32, teeth=0.22, seed=seed * 7 + k))
    return parts


def strawberry(name, at, down, L, R, mat):
    prof = [(0.0, 0.0), (0.75 * R, 0.06 * L), (R, 0.36 * L), (0.72 * R, 0.7 * L), (0.0, L)]
    parts = kl.tag([kf.revolve(name, prof, at, down, mat, segments=7, t=(0.0, 0.1, 0.4, 0.75, 1.0))], scale=1.25)
    parts += kl.tag(kf.corolla(name + "Calyx", at - Vector(down) * 0.0015, -Vector(down), 5, R * 1.15, R * 0.5,
                               calyx, lift=0.18, profile="lance", segments=2, cols=2, seed=len(pieces)), kl.NEAR)
    return parts


crowns = [Vector((-0.1, 0.07, G)), Vector((0.1, 0.06, G)), Vector((0.0, -0.11, G))]
# Leaves arching out of three crowns, overlapping into one low mat
for ci, c in enumerate(crowns):
    for j in range(6):
        heading = ci * 0.7 + j / 6 * math.tau + rnd.uniform(-0.3, 0.3)
        stalk_, side0, middle, side2 = trefoil("Leaf%d_%d" % (ci, j), c, heading, rnd.uniform(0.05, 0.1),
                                               rnd.uniform(0.06, 0.14), rnd.uniform(0.048, 0.06), seed=ci * 10 + j)
        # Far mesh: the middle leaflet of five trefoils in six, grown about its base to cover for the other two
        kl.tag([stalk_, side0, side2], kl.NEAR)
        if j == 5:
            kl.tag([middle], kl.NEAR)
        else:
            kl.tag([middle], scale=1.35, pivot=middle.data.vertices[0].co.copy())
        pieces += [stalk_, side0, middle, side2]

# Berries in small trusses: most hanging round the edge of the mat, one held up through the leaves
n_berry = 0
for k, (ci, heading, rho, height, berries) in enumerate(((0, 2.4, 0.2, 0.07, 3), (2, 4.0, 0.19, 0.065, 3),
                                                       (2, 5.6, 0.2, 0.07, 3), (1, 0.5, 0.2, 0.075, 2),
                                                       (1, 1.9, 0.06, 0.12, 3))):
    c = crowns[ci]
    out = Vector((math.cos(heading), math.sin(heading), 0.0))
    top = c + out * rho + Z * (height * 0.95)
    pieces.append(kf.taper_tube("Truss%d" % k, [c, c + out * rho * 0.15 + Z * height * 0.6,
                                                c + out * rho * 0.5 + Z * height, c + out * rho * 0.85 + Z * height * 1.02,
                                                top], (0.0016, 0.0011), stalk, sides=4))
    for b in range(berries):
        side = Vector((-out.y, out.x, 0.0)) * rnd.uniform(-0.025, 0.025)
        L = rnd.uniform(0.017, 0.021)
        R = L * rnd.uniform(0.38, 0.44)
        attach = top + out * rnd.uniform(0.008, 0.02) + side + Z * rnd.uniform(-0.025, -0.01)
        attach.z = max(attach.z, G + L + 0.004)
        down = (out * rnd.uniform(0.1, 0.35) + side * 4.0 - Z).normalized()
        pieces += kl.tag([kf.taper_tube("Pedicel%d_%d" % (k, b), [top, top.lerp(attach, 0.5) + out * 0.004 + Z * 0.006,
                                                                 attach], (0.001, 0.0008), stalk, sides=4)], kl.NEAR)
        pieces += strawberry("Berry%d_%d" % (k, b), attach, down, L, R, unripe if n_berry in (4, 11) else ripe)
        n_berry += 1

# Flowers held just above the leaves
for k in range(4):
    c = crowns[k % 3]
    a = k * 1.7 + rnd.uniform(-0.3, 0.3)
    out = Vector((math.cos(a), math.sin(a), 0.0))
    F = c + out * rnd.uniform(0.06, 0.12) + Z * rnd.uniform(0.125, 0.15)
    fa = (Z + out * rnd.uniform(0.3, 0.6)).normalized()
    pieces.append(kf.taper_tube("FlowerStalk%d" % k, [c, c + out * 0.02 + Z * 0.07, F - fa * 0.004, F],
                                (0.0015, 0.0011), stalk, sides=4))
    pieces += kl.tag(kf.corolla("Petal%d_" % k, F, fa, 5, 0.0105, 0.0105, petal, lift=0.08, profile="round",
                                segments=3, cols=2, seed=k, jitter=0.05), scale=1.2, pivot=F)
    pieces += kl.tag([kf.revolve("Center%d" % k, [(0.0, 0.003), (0.0032, 0.0022), (0.0048, 0.0)], F, fa, center,
                                 segments=7)], scale=1.2, pivot=F)

kf.report(SCRIPT, pieces)
model = kl.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.05, distance=0.9)
kl.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.05, distance=0.9)
print("[%s] done" % SCRIPT)
