"""TwigPile (forest floor, ground cover): a loose heap of fallen twigs and small branches 20 to 60 cm long, grey-brown
and silvery with age, snapped ends of pale wood, a fork here and there, a bit of bark peeling off in flakes, a few dead
leaves caught between them, lying criss-cross on a dark bed of rotted litter, about 12 cm high at its crown. Every stick
rests on the ones beneath it.

    blender -b --factory-startup --python twig_pile.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402
import zkit as tk  # noqa: E402

NAME, SCRIPT = "TwigPile", "twig_pile"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(29)

patch = kg.Patch(0.42, seed=21, stretch=(1.0, 0.85))
patch.fade = (0.6, 1.2)
heap = kg.Heap(patch, reach=0.7)

floor = kg.duff("TwigDuff", (0.05, 0.034, 0.018), (0.1, 0.066, 0.032), (0.21, 0.15, 0.075), scale=105.0, chips=0.4)
bark = kg.twig_bark("TwigBark", dark=(0.05, 0.036, 0.024), mid=(0.17, 0.128, 0.088), light=(0.3, 0.25, 0.19), peel=0.4,
                    lichen=0.4)
wood = kg.twig_wood("TwigWood")
oak = kg.leaf_material("TwigOakLeaf", [((0.2, 0.108, 0.04), 3.0), ((0.27, 0.19, 0.08), 2.0), ((0.1, 0.06, 0.028), 2.0)],
                       kind="pinnate", veins=9.0, slope=0.35, damp=1.0, vein_lift=1.2)
birch = kg.leaf_material("TwigBirchLeaf", [((0.36, 0.25, 0.04), 2.0), ((0.26, 0.16, 0.05), 3.0), ((0.2, 0.11, 0.04), 2.0)],
                         kind="pinnate", veins=10.0, slope=0.5, damp=0.8)


def flake_material():
    """Curled flakes of bark: dark grey-brown outside, fine fibers along the flake, a paler torn edge."""
    mat, g = tk.new_material("BarkFlake")
    lx, ly, e = nk._attr(g, "lx"), nk._attr(g, "ly"), nk._attr(g, "lz")
    r = nk._attr(g, "r")
    x = g.math("SUBTRACT", lx, 0.5)
    fib = g.noise(1.0, detail=4.0, roughness=0.6, vector=kg._vec(g, g.math("MULTIPLY", x, 4.0), g.math("MULTIPLY", ly, 110.0), g.math("MULTIPLY", r, 30.0)))
    col = g.mix(g.ramp(g.math("ADD", g.noise(40.0, detail=3.0), g.math("MULTIPLY", r, 0.4)), 0.3, 0.9), (0.07, 0.052, 0.037), (0.2, 0.16, 0.115))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.8), 0.5), col, (0.04, 0.03, 0.022))
    col = g.mix(g.math("MULTIPLY", g.ramp(e, 0.8, 1.0), 0.7), col, (0.32, 0.22, 0.13))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, 0.85, g.bump(fib, 1.0, 0.0011))


flake = flake_material()

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd, reach=0.7)


def stick(x0, y0, heading, length, rad, taper, bendy, sides, npts, lod, fork=0, crown=1.0):
    """A stick lying on the heap: a gently bent path, riding over whatever is below it."""
    d = Vector((math.cos(heading), math.sin(heading), 0.0))
    side = Vector((-d.y, d.x, 0.0))
    xy = []
    for q in range(npts):
        s = q / (npts - 1) - 0.5
        off = bendy * (math.sin(q * 1.7 + heading * 3.0)) * length
        xy.append((x0 + d.x * length * s + side.x * off, y0 + d.y * length * s + side.y * off))
    raw = []
    for (px, py) in xy:
        raw.append(max(heap.top(px + dx, py + dy) for dx in (-0.012, 0.0, 0.012) for dy in (-0.012, 0.0, 0.012)))
    # A stick spans its supports: ride the highest neighbour, lean toward the higher end a little
    zs = []
    for q in range(npts):
        lo, hi = max(0, q - 1), min(npts, q + 2)
        zs.append(max(raw[lo:hi]) + rad * 0.95 + 0.001)
    path = [(px, py, z) for (px, py), z in zip(xy, zs)]
    radii = [rad * (1.0 + taper * (1.0 - q / (npts - 1)) * 0.5 - taper * 0.5 * q / (npts - 1)) for q in range(npts)]
    radii = [rad * (1.0 - taper * q / (npts - 1)) for q in range(npts)]
    kg.tube(b, bark, path, radii, sides=sides, jag=min(0.006, rad * 0.9), rnd=rnd, cap_mat=wood, caps=(True, True),
            lod=lod, lod_scale=1.25, bend_noise=0.0)
    for i in range(npts - 1):
        kg.Heap.stamp_line(heap, xy[i], xy[i + 1], zs[i] + rad, zs[i + 1] + rad)
        # widen the stamp across the stick
        for sgn in (-1, 1):
            p = (xy[i][0] + side.x * rad * sgn, xy[i][1] + side.y * rad * sgn)
            q = (xy[i + 1][0] + side.x * rad * sgn, xy[i + 1][1] + side.y * rad * sgn)
            kg.Heap.stamp_line(heap, p, q, zs[i] + rad * 0.8, zs[i + 1] + rad * 0.8)
    out = []
    for k in range(fork):
        q = rnd.randint(1, npts - 2)
        hd = heading + rnd.choice((-1, 1)) * rnd.uniform(0.5, 0.9)
        out.append((xy[q][0], xy[q][1], zs[q], hd, rad * 0.55))
    return out


# Thick branches first (the bottom of the pile), then thinner sticks across them, forks, and the finest on top
spots = patch.sample(rnd, 8, min_gap=0.07, reach=0.6)
forks = []
for k, (x, y) in enumerate(spots):
    L = rnd.uniform(0.3, 0.5)
    forks += stick(x, y, rnd.uniform(0, math.tau), L, rnd.uniform(0.0065, 0.011), 0.4, 0.09, 6, 4, 0, fork=2)
spots = patch.sample(rnd, 24, min_gap=0.03, reach=0.6)
for k, (x, y) in enumerate(spots):
    L = rnd.uniform(0.2, 0.4)
    forks += stick(x, y, rnd.uniform(0, math.tau), L, rnd.uniform(0.0028, 0.0055), 0.35, 0.1, 4, 4, 0 if k % 3 == 0 else 1,
                   fork=1 if k % 4 == 0 else 0)
for (x, y, z, hd, rad) in forks:
    L = rnd.uniform(0.08, 0.2)
    d = Vector((math.cos(hd), math.sin(hd), 0.0))
    stick(x + d.x * L * 0.5, y + d.y * L * 0.5, hd, L, rad, 0.5, 0.05, 3, 3, 1)
spots = patch.sample(rnd, 26, min_gap=0.025, reach=0.6)
for k, (x, y) in enumerate(spots):
    stick(x, y, rnd.uniform(0, math.tau), rnd.uniform(0.15, 0.3), rnd.uniform(0.002, 0.003), 0.4, 0.12, 3, 3, 1)

# Bark flakes: curled strips lying about, a few caught on the sticks
strip = [(0.0, -0.1), (0.5, -0.17), (0.95, -0.12), (1.0, 0.0), (0.95, 0.12), (0.5, 0.17), (0.0, 0.1)]
for k, (x, y) in enumerate(patch.sample(rnd, 9, min_gap=0.05, reach=0.6)):
    kg.add_leaf(b, flake, strip, rnd.uniform(0.03, 0.06), (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=(rnd.uniform(0.5, 1.2) * rnd.choice((-1, 1)), rnd.uniform(0.2, 0.7), 0.2, 0.0), mid=True,
                tilt=(rnd.uniform(-10, 10), rnd.uniform(-10, 10)), lod=1)

# Leaves caught in it
for k, (x, y) in enumerate(patch.sample(rnd, 12, min_gap=0.05, reach=0.7)):
    if k % 2:
        outline, mat, L = kg.oak_outline(rnd, 1), oak, rnd.uniform(0.07, 0.1)
    else:
        outline, mat, L = kg.birch_outline(rnd, 1), birch, rnd.uniform(0.05, 0.07)
    kg.add_leaf(b, mat, outline, L, (x, y), rnd.uniform(0, math.tau), heap, rnd,
                curl=(rnd.uniform(-0.3, 0.5), rnd.uniform(-0.2, 0.4), 0.4, rnd.uniform(-0.5, 0.5)),
                tilt=(rnd.uniform(-8, 8), rnd.uniform(-8, 8)), lod=1, max_height=0.15)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=1024,
         density={"TwigBark": 1.1, "TwigWood": 0.5, "TwigDuff": 0.5, "BarkFlake": 0.8, "TwigOakLeaf": 0.7, "TwigBirchLeaf": 0.7})
print("[%s] done" % SCRIPT)
