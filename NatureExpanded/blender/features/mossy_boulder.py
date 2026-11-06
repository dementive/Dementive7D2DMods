"""MossyBoulder01..04 and GlacialErratic01..02 (pine forest and meadows): rounded granite boulders, knee-high to 4 m,
sunk into the ground, moss on the tops and the north side, lichen crusts, hairline cracks, rain streaks, ferns at the
base. 01 a mid boulder with a split face, 02 a low wide one, 03 a tall angular one, 04 a tumble of four; the erratics
are the big lone ones for meadows (3 and 4 m). All solid: colliders are voxelized from the meshes (featurekit).

    blender -b --factory-startup --python mossy_boulder.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]

# name: (rocks [Rock kwargs], atlas size, moss amount, ferns [(x, y)], voxel)
SPECS = {
    "MossyBoulder01": (
        [dict(radii=(0.95, 0.8, 0.62), height=0.95, seed=3, power=2.8, yaw=20, rough=0.11,
              planes=[((0.9, 0.25, 0.35), 0.62), ((-0.5, 0.8, 0.45), 0.62)], cracks=[((0.3, 1.0, 0.1), 0.1, 0.07, 0.05)])],
        2048, 1.0, [(0.55, 0.75), (-0.8, -0.2)], 0.1),
    "MossyBoulder02": (
        [dict(radii=(1.4, 1.05, 0.72), height=1.15, seed=11, power=2.4, yaw=-35, rough=0.08,
              planes=[((-0.4, 0.9, 0.3), 0.85), ((0.8, -0.2, 0.5), 1.0)],
              cracks=[((1.0, 0.2, 0.0), -0.2, 0.08, 0.06)])],
        2048, 1.0, [(-1.0, 0.8), (1.2, -0.7)], 0.12),
    "MossyBoulder03": (
        [dict(radii=(0.82, 0.74, 1.12), height=1.85, seed=23, power=3.0, yaw=55, rough=0.06,
              planes=[((0.7, 0.6, 0.35), 0.62), ((-0.8, 0.2, 0.5), 0.6), ((0.0, -1.0, 0.6), 0.6)],
              cracks=[((0.2, 1.0, 0.0), 0.0, 0.06, 0.05)])],
        2048, 0.85, [(0.7, -0.8)], 0.1),
    "MossyBoulder04": (
        [dict(radii=(1.1, 0.95, 0.8), height=1.45, seed=31, power=2.5, yaw=10, planes=[((0.8, 0.3, 0.5), 0.9)]),
         dict(radii=(0.7, 0.6, 0.5), height=0.85, seed=41, power=2.6, yaw=70, at=(1.55, 0.7)),
         dict(radii=(0.5, 0.45, 0.42), height=0.62, seed=51, power=2.7, yaw=30, at=(-1.35, 0.95)),
         dict(radii=(0.55, 0.5, 0.36), height=0.5, seed=61, power=2.5, yaw=-20, at=(0.55, -1.45))],
        2048, 1.0, [(-0.4, -1.1), (1.2, -0.5), (-1.0, 1.7)], 0.12),
    "GlacialErratic01": (
        [dict(radii=(2.3, 1.8, 1.7), height=3.2, seed=71, power=2.7, yaw=25, rough=0.1, subdiv=5,
              planes=[((0.75, 0.2, 0.45), 1.9), ((-0.5, 0.8, 0.3), 1.5), ((0.1, -0.9, 0.5), 1.4)],
              cracks=[((0.4, 1.0, 0.0), 0.2, 0.1, 0.1), ((1.0, -0.1, 0.0), -0.5, 0.09, 0.09)])],
        2048, 0.8, [(1.8, -1.6), (-2.1, 1.0), (0.4, 2.1)], 0.16),
    "GraniteOutcrop01": (
        [dict(radii=(2.7, 1.7, 1.0), height=1.55, seed=91, power=3.4, yaw=15, rough=0.09, subdiv=5,
              planes=[((0.6, 0.7, 0.4), 1.6), ((-0.8, 0.3, 0.5), 1.9), ((0.0, -1.0, 0.3), 1.3)],
              cracks=[((0.1, 1.0, 0.0), 0.3, 0.14, 0.4), ((1.0, 0.1, 0.0), -0.7, 0.12, 0.35), ((0.7, 0.7, 0.0), 0.5, 0.1, 0.3)])],
        2048, 1.0, [(0.3, 0.9), (-0.9, 0.5), (1.1, -0.2), (-1.6, -1.0)], 0.16),
    "GlacialErratic02": (
        [dict(radii=(1.7, 1.35, 1.2), height=2.3, seed=83, power=2.8, yaw=-50, rough=0.06, subdiv=5,
              planes=[((0.6, 0.6, 0.5), 1.25), ((-0.9, 0.1, 0.4), 1.2)], cracks=[((0.0, 1.0, 0.1), 0.0, 0.08, 0.08)])],
        2048, 0.7, [(1.4, 0.9), (-1.3, -1.1)], 0.14),
}


def build(name):
    rocks, size, moss, ferns, voxel = SPECS[name]
    nk.reset()
    rnd = random.Random(sum(map(ord, name)))
    rock = fk.granite("BoulderRock", moss=moss, lichen=1.0)
    skirt = fk.granite("BoulderSkirt", moss=0.0, lichen=0.0)
    mossy = fk.granite_moss("BoulderMoss", moss=moss, lichen=1.0)
    fern_mat = nk.plant("BoulderFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    b = ks.Builder(name)
    bodies = []
    for i, kw in enumerate(rocks):
        bm = fk.Rock(**kw).build()
        bodies.append(fk.emit_rock(b, bm, rock, skirt, (mossy, fk.moss_depth(kw["seed"], moss, 0.03 if size >= 2048 else 0.022))))
        bm.free()
    b.lod = 0
    for x, y in ferns:
        ks.fern(b, fern_mat, (x, y, G), rnd, fronds=6, length=(0.38, 0.55), pinnae=12, pinna_len=0.09, pinna_w=0.024,
                away=math.degrees(math.atan2(y, x)), arc=170.0, tilt=(20.0, 52.0), bend=(0.35, 0.7), far=(0.4, 1.4))
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    model = fk.export(name, pieces, bodies, FEATURES, size=size, voxel=voxel,
                      density={"BoulderRock": 1.0, "BoulderSkirt": 0.12, "BoulderMoss": 1.0, "BoulderFern": 0.4})
    reach = max(max(abs(v.x), abs(v.y)) for vs, _ in bodies for v in vs)
    top = max(v.z for vs, _ in bodies for v in vs)
    nk.previews(name.lower(), model, PREVIEWS, focus_height=(G + top) * 0.5, distance=3.2 + 2.2 * reach)
    ks.lod_preview(name.lower(), name, PREVIEWS, focus_height=(G + top) * 0.5, distance=3.2 + 2.2 * reach)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
