"""StoneCairnDesert, StoneCairnSnow, StoneCairnForest: trail markers, neat stacks of flat stones a metre or so high
(sandstone slabs in the desert, dark slate under snow, mossy granite in the forest). Solid (voxel colliders).

    blender -b --factory-startup --python stone_cairn.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import formations as fm  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]

# name: (material maker, stones, base radius, seed)
SPECS = {
    "StoneCairnDesert": (lambda n: fm.sandstone(n, lichen=0.4, crack=0.4), 8, 0.46, 5),
    "StoneCairnSnow": (lambda n: fm.slate(n, snow=1.0, ice=0.3, crack=0.4), 9, 0.5, 9),
    "StoneCairnForest": (lambda n: fk.granite(n, moss=0.7, lichen=1.0), 7, 0.48, 14),
}


def build(name):
    maker, count, r0, seed = SPECS[name]
    nk.reset()
    rnd = random.Random(seed)
    body = maker("CairnStone")
    skirt = maker("CairnSkirt")
    b = ks.Builder(name)
    bodies = []
    z = 0.0
    x = y = 0.0
    for i in range(count):
        f = i / max(1, count - 1)
        r = r0 * (1.0 - 0.72 * f ** 0.9) * rnd.uniform(0.88, 1.08)
        t = rnd.uniform(0.09, 0.15) * (1.0 - 0.3 * f)
        x += rnd.uniform(-0.035, 0.035) * (1.0 - f * 0.5)
        y += rnd.uniform(-0.035, 0.035) * (1.0 - f * 0.5)
        sink = fk.SKIRT if i == 0 else -z
        top = z + t + (fk.SKIRT if i == 0 else 0.0) * 0.0
        prof = [(z + 0.002, r), (z + t * 0.5, r * 1.02), (top, r * 0.9)]
        bm = fm.column(prof, seed=seed + i, sides=16, rough=0.1, ellipse=rnd.uniform(1.0, 1.35), yaw=rnd.uniform(0, 360),
                       at=(x, y), sink=sink, steps=1)
        bodies.append(fk.emit_rock(b, bm, body, skirt))
        bm.free()
        z = top - 0.012
    # a small capstone standing on end
    sink = -z
    bm = fm.column([(z + 0.002, 0.1), (z + 0.16, 0.085), (z + 0.2, 0.05)], seed=seed + 99, sides=12, rough=0.12, at=(x, y),
                   sink=sink, steps=2)
    bodies.append(fk.emit_rock(b, bm, body, skirt))
    bm.free()
    top_z = z + 0.2
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    model = fk.export(name, pieces, bodies, FEATURES, size=1024, voxel=0.05, margin=0.012, limit=70,
                      density={"CairnStone": 1.0, "CairnSkirt": 0.1})
    nk.previews(name.lower(), model, PREVIEWS, focus_height=G + top_z * 0.5, distance=3.2)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
