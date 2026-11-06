"""MossPatch (forest floor, ground cover): a cushion of green moss about 0.8 m across on dark soil: dozens of small
overlapping mounds of every size, each with its own rim breaking into tufts over dark gaps, drifting from bright
yellow-green to deep green with a few brown dead patches, a few small stones with lichen sitting in it, and a short
twig half buried. Thinning irregularly at the rim so it fades into the grass.

    blender -b --factory-startup --python moss_patch.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "MossPatch", "moss_patch"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(8)

patch = kg.Patch(0.42, seed=17, stretch=(1.0, 0.88))
patch.holes = [(0.2, -0.1, 0.05)]
patch.fade = (0.55, 1.1)
heap = kg.Heap(patch, height=0.008, reach=0.78)

moss = kf.moss_material("MossCushion", soil=(0.055, 0.04, 0.026))
stone = kg.stone_material("MossStone", lichen=0.7, moss=0.5)
bark = kg.twig_bark("MossTwigBark", mid=(0.13, 0.1, 0.072), light=(0.24, 0.19, 0.13), peel=0.2, lichen=0.6)
wood = kg.twig_wood("MossTwigWood")

b = kg.Ground(NAME)
kg.base_layer(b, moss, patch, rnd, height=0.008, reach=0.78)


def mound(x, y, r, h, k, lod):
    """A low cushion: a rounded dome with a lumpy rim, sunk a little into what's below."""
    ph = [rnd.uniform(0, math.tau) for _ in range(3)]

    def wob(i, a):
        m = 1.0 + 0.2 * math.sin(3 * a + ph[0]) + 0.1 * math.sin(5 * a + ph[1])
        return m, (h * 0.14 * math.sin(2 * a + ph[2]) if i == 1 else 0.0)

    z0 = max(heap.top(x + dx * r * 0.6, y + dy * r * 0.6) for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
    prof = [(0.0, h), (0.68 * r, 0.62 * h), (r, -0.004)]
    kg.lathe(b, moss, prof, (x, y, z0 - 0.003), (0, 0, 1), segments=7, t=(1.0, 0.65, 0.0), wobble=wob,
             phase=rnd.uniform(0, math.tau), lod=lod, lod_scale=1.35, rnd=rnd)
    for a in range(8):
        for f in (0.35, 0.7):
            q = r * f
            heap.stamp(x + q * math.cos(a * math.tau / 8), y + q * math.sin(a * math.tau / 8), z0 - 0.003 + h * (1.0 - f * f) * 0.8)
    heap.stamp(x, y, z0 - 0.003 + h)


# Big cushions first, then smaller ones piled on and between them
spots = patch.sample(rnd, 20, min_gap=0.05)
for k, (x, y) in enumerate(spots):
    d = patch.d(x, y)
    r = rnd.uniform(0.045, 0.075) * (1.0 - 0.25 * d)
    mound(x, y, r, rnd.uniform(0.016, 0.028), k, lod=0 if k % 2 == 0 else 1)
spots = patch.sample(rnd, 62, min_gap=0.022)
for k, (x, y) in enumerate(spots):
    d = patch.d(x, y)
    r = rnd.uniform(0.025, 0.05) * (1.0 - 0.3 * d)
    mound(x, y, r, rnd.uniform(0.012, 0.024), k, lod=0 if k % 4 == 0 else 1)

# A few stones sitting in it
for k, (x, y) in enumerate(((-0.12, 0.1), (0.17, 0.15), (-0.02, -0.2), (0.22, -0.12))[:rnd.choice((3, 4))]):
    a = rnd.uniform(0.028, 0.06)
    kg.rock(b, stone, (x, y, heap.top(x, y) + a * 0.15), (a * 1.2, a, a * 0.55), rnd, subdiv=2, rough=0.2,
            yaw=rnd.uniform(0, math.tau), flat=0.7, lod=0 if k < 2 else 1, lod_scale=1.3)

# A twig half buried
x0, y0 = -0.1, -0.12
hd = 0.6
L = 0.24
d = Vector((math.cos(hd), math.sin(hd), 0.0))
path = []
for q in range(5):
    s = q / 4.0 - 0.5
    px, py = x0 + d.x * L * s + 0.01 * math.sin(q * 2.1), y0 + d.y * L * s + 0.01 * math.cos(q * 1.7)
    path.append((px, py, heap.top(px, py) - 0.002 + (0.003 if q in (1, 2) else 0.0)))
kg.tube(b, bark, path, [0.0065, 0.0075, 0.0072, 0.0068, 0.0058], sides=6, jag=0.006, rnd=rnd, cap_mat=wood,
        caps=(False, True))

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=2048,
         density={"MossCushion": 1.0, "MossStone": 1.2, "MossTwigBark": 1.0, "MossTwigWood": 0.5})
print("[%s] done" % SCRIPT)
