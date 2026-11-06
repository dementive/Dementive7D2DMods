"""Driftwood (ground cover, water's edge): three pieces of sun-bleached, silver-grey driftwood on pale shore sand: a
twisted limb 90 cm long with a snapped stub and splintered ends, a crooked 55 cm branch and a short 30 cm chunk with a
sawn end; deep grain, long checks, bore holes; a few ribbons of dried weed tangled round them.

    blender -b --factory-startup --python driftwood.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import kit_shrub as ksh  # noqa: E402
import zkit as tk  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "Driftwood", "driftwood"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(61)
G = nk.GROUND

wood = ks_.weathered_wood("DriftWood")
sand = ks_.sand_material("ShoreSand", color=((0.24, 0.2, 0.15), (0.36, 0.31, 0.24)), wet=0.25, ripple=0.04)
weed_m = nk.plant("DriftWeed", (0.17, 0.12, 0.06), (0.1, 0.075, 0.045), rough=0.9, vary=0.45, sat=0.8, value=0.8)
WEX = ("ws", "ca", "sa", "cap")

S = ks_.Set(NAME)
b = ksh.Builder("Dw")
ks_.pad(S.gm(sand), (0.02, 0.02), 0.44, rnd, sides=34, dome=0.012, lobes=0.25, stretch=(1.1, 0.85), yaw=0.45, rings=3)
gm = S.gm(wood, WEX)


def lay(points, r):
    """Points (x, y, rise) to world points, the axis a little above the ground so the wood is partly sunk."""
    return [Vector((x, y, G + r * 0.78 + z)) for x, y, z in points]


# The big limb: sweeping, a little twisted, lifted at both ends, a snapped stub off its side
main_pts = lay([(-0.4, -0.15, 0.05), (-0.23, -0.1, 0.012), (-0.02, -0.04, 0.0), (0.17, 0.04, 0.004), (0.3, 0.12, 0.03), (0.38, 0.22, 0.08)], 0.04)
path = ks_.wood_tube(gm, main_pts, [(0.0, 0.036), (0.3, 0.046), (0.65, 0.04), (1.0, 0.027)], rnd, sides=11, step=0.042, twist=2.6,
                     lump=0.11, groove=0.06, crack=0.06, ends=("splinter", "splinter"), ws0=rnd.uniform(0, 60), jag=1.0, flat=0.12)
# stub: a snapped branch off the limb
base = path[int(len(path) * 0.38)]
stub_dir = Vector((-0.25, 0.9, 0.35)).normalized()
stub = [base - stub_dir * 0.03, base + stub_dir * 0.04, base + stub_dir * 0.09 + Vector((0.0, 0.0, 0.01))]
ks_.wood_tube(gm, stub, [(0.0, 0.019), (1.0, 0.013)], rnd, sides=8, step=0.03, twist=1.0, lump=0.08, groove=0.04, crack=0.04,
              ends=("buried", "splinter"), ws0=rnd.uniform(0, 60), jag=0.8)
# a second, lighter branch, crooked
br_pts = lay([(-0.3, 0.3, 0.0), (-0.12, 0.34, 0.0), (0.04, 0.3, 0.0), (0.2, 0.34, 0.012), (0.26, 0.4, 0.04)], 0.025)
bpath = ks_.wood_tube(gm, br_pts, [(0.0, 0.026), (0.5, 0.024), (1.0, 0.014)], rnd, sides=9, step=0.04, twist=-2.0, lump=0.12,
                      groove=0.06, crack=0.05, ends=("splinter", "splinter"), ws0=rnd.uniform(0, 60), jag=1.2)
base = bpath[int(len(bpath) * 0.6)]
ks_.wood_tube(gm, [base - Vector((0.0, 0.0, 0.0)) + Vector((0.0, 0.01, 0.0)), base + Vector((0.07, -0.05, 0.02)), base + Vector((0.14, -0.1, 0.045))],
              [(0.0, 0.013), (1.0, 0.008)], rnd, sides=7, step=0.03, twist=0.0, lump=0.06, groove=0.03, crack=0.03,
              ends=("buried", "splinter"), ws0=rnd.uniform(0, 60), jag=1.0)
# the short chunk, one end sawn
ch_pts = lay([(0.14, -0.3, 0.0), (0.26, -0.27, 0.0), (0.4, -0.2, 0.01), (0.46, -0.15, 0.02)], 0.042)
ks_.wood_tube(gm, ch_pts, [(0.0, 0.042), (1.0, 0.036)], rnd, sides=10, step=0.04, twist=1.2, lump=0.1, groove=0.06, crack=0.07,
              ends=("flat", "splinter"), ws0=rnd.uniform(0, 60), jag=0.9)

# Dried weed: tangled wisps of thin dark strands lying on the sand and over the limb
for k in range(5):
    s0 = rnd.uniform(0.1, 0.9)
    i = int(len(path) * s0)
    p = path[i] + Vector((rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), 0.0))
    for j in range(rnd.randint(5, 8)):
        h = rnd.uniform(0, math.tau)
        pt = Vector((p.x, p.y, G + 0.006))
        pts = []
        for q in range(10):
            pts.append(pt.copy())
            h += rnd.uniform(-0.45, 0.45)
            step = rnd.uniform(0.014, 0.026)
            pt = pt + Vector((math.cos(h) * step, math.sin(h) * step, rnd.uniform(-0.001, 0.003)))
            if pt.z < G + 0.004:
                pt.z = G + 0.004
        ks_.strand(b, weed_m, pts, rnd.uniform(0.006, 0.011), t0=0.2, t1=1.0, lod=1)

pieces = S.objects() + b.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024, density={"DriftWood": 1.0, "ShoreSand": 0.5, "DriftWeed": 0.3})
ks_.preview(SCRIPT, model, PREVIEWS, kind="shore", height=0.1)
print("[%s] done" % SCRIPT)
