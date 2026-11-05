"""Poppy (pine forest meadows): a dense clump of wild red poppies filling most of a block, a dozen open heads and a
few drooping buds on thin, slightly crooked stalks 30 to 55 cm tall, with meadow grass among them. Each head is a
loose cup of four crumpled scarlet petals with a near-black smudge at their base around a grey-green seed capsule.
The worked example of the kit: read it before writing a plant.

A drift only reads from far off as a mass of color, so a flower block is a full clump, not one stem: a dozen or more
heads, most of them facing up, big enough to see (a real poppy is 5 to 10 cm across), in the real flower's color at
full strength. Grass tufts among the stalks keep the ground under a drift from looking bare.

    blender -b --factory-startup --python poppy.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402

NAME, SCRIPT = "Poppy", "poppy"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(3)
G = nk.GROUND

stalk = nk.plant("PoppyStalk", (0.18, 0.26, 0.12), (0.12, 0.17, 0.08), rough=0.7)
leaf = nk.plant("PoppyLeaf", (0.16, 0.22, 0.12), (0.2, 0.25, 0.16), rough=0.7, vary=0.3)
red = nk.petal("PoppyPetal", (0.03, 0.01, 0.01), (0.8, 0.05, 0.02), mid=(0.72, 0.03, 0.02), streaks=0.3, sat=1.0,
               value=0.95)
pod = nk.plant("PoppyPod", (0.2, 0.24, 0.16), (0.1, 0.12, 0.08), rough=0.5)
bud = nk.plant("PoppyBud", (0.17, 0.24, 0.12), (0.3, 0.12, 0.08), rough=0.6)
grass = nk.grass()

pieces = []
for i, (x, y) in enumerate(nk.scatter(15, 0.36, seed=2, min_gap=0.07)):
    h = rnd.uniform(0.3, 0.55)
    lean = Vector((x, y, 0.0)) * 0.25 + Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), 0.0))
    top = Vector((x, y, G + h)) + lean
    mid = Vector((x, y, G + h * 0.55)) + lean * 0.4 + Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0))
    if i >= 12:
        # A closed bud, nodding on its crook
        hook = top + Vector((lean.x * 0.3, lean.y * 0.3, -0.04))
        pieces.append(nk.stem("Stalk%d" % i, [(x, y, G), tuple(mid), tuple(top), tuple(hook)], 0.0028, stalk))
        pieces.append(nk.disc("Bud%d" % i, hook + Vector((0, 0, -0.012)), (0, 0, -1), 0.012, bud, height=0.02,
                              segments=8))
        continue
    pieces.append(nk.stem("Stalk%d" % i, [(x, y, G), tuple(mid), tuple(top)], 0.003, stalk))
    # Mostly facing up, so the red shows from far off and from above
    face = (Vector((lean.x, lean.y, 0.0)) * 1.2 + Vector((0, 0, 1))).normalized()
    pieces += nk.petal_ring("Petals%d" % i, top, face, 4, rnd.uniform(0.05, 0.062), 0.072, red, cup=0.35, droop=0.12,
                            profile="spoon", seed=i, jitter=0.18)
    pieces.append(nk.disc("Pod%d" % i, top + face * 0.008, face, 0.01, pod, height=0.013, segments=8))

# Rosettes of jagged leaves low down, and meadow grass among the stalks
for k, (x, y) in enumerate(((-0.12, 0.08), (0.14, -0.06), (0.02, -0.2))):
    for j in range(6):
        a = j / 6 * math.tau + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0.35))
        pieces.append(nk.blade("Leaf%d_%d" % (k, j), (x, y, G + 0.01), d, rnd.uniform(0.1, 0.16), 0.035, leaf,
                               bend=0.55, twist=rnd.uniform(-20, 20), profile="lance"))
for k, (x, y) in enumerate(nk.scatter(5, 0.38, seed=7, min_gap=0.15)):
    pieces += nk.tuft("Grass%d_" % k, (x, y), 8, 0.28, grass, seed=k)

model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.3, distance=1.3)
print("[%s] done" % SCRIPT)
