"""BleachedBranch (ground cover, desert): a dead desert branch about 1.1 m long lying along the diagonal, bone-white and
grey in the sun, half buried in a drift of sand: a thick base sunk in the sand, a crooked middle, a fork near the end
with a shorter prong, long cracks (checking) along the grain, torn splintered tips and a snapped twig stub.

    blender -b --factory-startup --python bleached_branch.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import zkit as tk  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "BleachedBranch", "bleached_branch"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(77)
G = nk.GROUND

wood = ks_.weathered_wood("BleachedWood", light=(0.53, 0.5, 0.44), dark=(0.38, 0.35, 0.3), groove=(0.2, 0.15, 0.1),
                          warm=0.6, stain=0.3, inner=(0.34, 0.28, 0.2))
sand = ks_.sand_material("DesertSand", color=((0.42, 0.31, 0.19), (0.57, 0.44, 0.28)), ripple=0.1, relief=0.004)
WEX = ("ws", "ca", "sa", "cap")

S = ks_.Set(NAME)
gm = S.gm(wood, WEX)
D = Vector((0.7, 0.7, 0.0)).normalized()
SIDE = Vector((-D.y, D.x, 0.0))


def at(u, v, z):
    """A point u along the diagonal (from the middle), v sideways, z above the ground."""
    p = D * u + SIDE * v
    return Vector((p.x, p.y, G + z))


# The sand drift first: a long low dune heaped over the middle of the branch, rippled
ks_.pad(S.gm(sand), (0.0, 0.0), 0.4, rnd, sides=40, dome=0.03, lobes=0.18, stretch=(1.35, 0.62), yaw=0.78, rings=4, lump=0.004)
ks_.pad(S.gm(sand), (0.18, -0.2), 0.14, rnd, sides=18, dome=0.012, lobes=0.3, stretch=(1.4, 0.7), yaw=0.78, rings=2)

# The branch: thick base sunk in the sand, sloping up to a kink and the fork
pts = [at(-0.52, 0.04, 0.01), at(-0.34, -0.01, 0.018), at(-0.14, 0.03, 0.026), at(0.06, 0.0, 0.034), at(0.22, -0.045, 0.04),
       at(0.34, -0.03, 0.055)]
path = ks_.wood_tube(gm, pts, [(0.0, 0.034), (0.35, 0.031), (0.75, 0.024), (1.0, 0.02)], rnd, sides=11, step=0.04, twist=1.6,
                     lump=0.09, groove=0.07, crack=0.09, ends=("buried", "stub"), ws0=rnd.uniform(0, 60), flat=0.1)
fork = path[-1]
tan = (path[-1] - path[-4]).normalized()
# two prongs: the long one carries on, the short one splays off and up
p1 = [fork - tan * 0.02, fork + tan * 0.08 + Vector((0.0, 0.0, 0.02)) + SIDE * 0.03, fork + tan * 0.17 + Vector((0.0, 0.0, 0.05)) + SIDE * 0.05,
      fork + tan * 0.24 + Vector((0.0, 0.0, 0.065)) + SIDE * 0.04]
ks_.wood_tube(gm, p1, [(0.0, 0.02), (0.5, 0.015), (1.0, 0.007)], rnd, sides=9, step=0.035, twist=1.0, lump=0.1, groove=0.06, crack=0.07,
              ends=("buried", "splinter"), ws0=rnd.uniform(0, 60), jag=1.2)
p2 = [fork - tan * 0.02, fork + tan * 0.04 - SIDE * 0.05 + Vector((0.0, 0.0, 0.03)), fork + tan * 0.07 - SIDE * 0.12 + Vector((0.0, 0.0, 0.07)),
      fork + tan * 0.07 - SIDE * 0.17 + Vector((0.0, 0.0, 0.055))]
ks_.wood_tube(gm, p2, [(0.0, 0.016), (0.5, 0.012), (1.0, 0.006)], rnd, sides=8, step=0.03, twist=-1.2, lump=0.1, groove=0.05, crack=0.06,
              ends=("buried", "splinter"), ws0=rnd.uniform(0, 60), jag=1.3)
# a snapped twig stub on the upper side of the middle
base = path[int(len(path) * 0.45)]
stub = [base + Vector((0.0, 0.0, 0.0)), base + Vector((-0.01, 0.02, 0.04)) + SIDE * 0.015, base + Vector((-0.02, 0.03, 0.075)) + SIDE * 0.03]
ks_.wood_tube(gm, stub, [(0.0, 0.011), (1.0, 0.007)], rnd, sides=7, step=0.03, twist=0.5, lump=0.06, groove=0.03, crack=0.03,
              ends=("buried", "splinter"), ws0=rnd.uniform(0, 60), jag=0.8)

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024, density={"BleachedWood": 1.0, "DesertSand": 0.5})
ks_.preview(SCRIPT, model, PREVIEWS, kind="sand", height=0.08)
print("[%s] done" % SCRIPT)
