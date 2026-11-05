"""Winterberry (snow): a leafless winter holly about a meter tall. Fourteen slender grey-brown stems fan up from the
ground in a loose vase, densely twiggy, and every twig is crowded with clusters of glossy bright red berries (230
of them: the color is the point), a dusting of snow on the up-facing sides of the twigs and little pillows of it
sitting along the slanting ones.

    blender -b --factory-startup --python winterberry.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

NAME, SCRIPT = "Winterberry", "winterberry"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(41)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

bark = ks.bark("WinterberryBark", (0.21, 0.18, 0.15), (0.12, 0.1, 0.085), rough=0.8, grain=50.0, dots=0.4,
               lichen=(0.3, 0.32, 0.26), lichen_amount=0.3, snow=0.9)
red = nk.plant("WinterberryRed", (0.78, 0.022, 0.02), (0.56, 0.012, 0.015), rough=0.4, wax=True, vary=0.2, sat=1.0,
               value=1.0)
snow = ks.snow("WinterberrySnow")

b = ks.Builder("Winterberry")

stems = []
for i in range(14):
    a = (i + rnd.uniform(-0.3, 0.3)) / 14 * math.tau
    lean = rnd.random()
    r0 = 0.02 + 0.12 * lean
    tilt = math.radians(8 + 40 * lean)
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    stems.append(ks.grow(rnd, (r0 * math.cos(a), r0 * math.sin(a), G), d, rnd.uniform(0.85, 1.05) - 0.25 * lean,
                         rnd.uniform(0.007, 0.01), 0.0, segments=5, gravity=0.6 + 0.8 * lean, wander=0.08, arch=True))
for st in stems:
    ks.fit([st], 0.36)
twigs = []
for st in stems:
    twigs += ks.branch_out(rnd, st, 6, (0.3, 0.95), (0.1, 0.26), (35, 70), 0.6, segments=2, wander=0.14, lift=0.1)
ks.wood(b, bark, stems, sides=(4,))
b.lod = 1
ks.wood(b, bark, twigs, sides=(3,))
b.lod = 0

# Berries crowded along the twigs and the upper stems in clusters of two to four, almost stalkless
berries = 0


def cluster(p, d, n):
    global berries
    _, u, v = ks.basis(d)
    for j in range(n):
        a = j / n * math.tau + rnd.uniform(-0.4, 0.4)
        q = p + (u * math.cos(a) + v * math.sin(a)) * 0.009 + d * rnd.uniform(0.004, 0.01)
        far = rnd.random() < 0.4
        b.lod, b.lod_scale = (0, 1.4) if far else (1, 1.0)
        ks.berry(b, red, q, rnd.uniform(0.0065, 0.0075), rnd, sides=3)
        b.lod, b.lod_scale = 0, 1.0
        berries += 1


for tw in twigs:
    for p, d, tan, s in ks.spiral_points(rnd, tw, rnd.choice((1, 2)), (0.35, 1.0), (50, 80), lift=0.1):
        cluster(p, d, rnd.choice((3, 4, 4)))
for st in stems:
    for p, d, tan, s in ks.spiral_points(rnd, st, 1, (0.6, 0.95), (55, 85), lift=0.1):
        cluster(p, d, rnd.choice((2, 3)))

# Snow on the slanting twigs
b.lod = 1
lumps = ks.snow_lumps(b, snow, twigs, rnd, chance=0.35, min_radius=0.0009, length=(0.03, 0.07), thick=3.0,
                      max_slope=0.8)
b.lod = 0
lumps += ks.snow_lumps(b, snow, stems, rnd, chance=0.4, min_radius=0.003, length=(0.04, 0.1), thick=1.8,
                       max_slope=0.9, min_z=G + 0.3)

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] berries %d, snow lumps %d" % (SCRIPT, berries, lumps))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.5, distance=2.5)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.5, distance=2.5)
print("[%s] done" % SCRIPT)
