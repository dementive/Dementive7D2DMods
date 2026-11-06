"""CrackedMud (ground cover, desert): a patch of dried-out mud 0.85 m across: about thirty curled plates, 6 to 18 cm
each, a tan crust over darker clay, their edges lifted and curling up like drying paint, split by deep cracks (2 to
3 cm wide, 2 to 4 cm deep, undercut) over a floor of dark dust; fine crazing across the plates, salt-white dust on
the high edges, ragged broken plates and flakes round the rim so the patch melts into the sand.

    blender -b --factory-startup --python cracked_mud.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import kit_forest as kf  # noqa: E402
import zkit as tk  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "CrackedMud", "cracked_mud"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(8)
G = nk.GROUND
A = ks_._attr


def mud_top(name):
    """The dry crust of a mud plate: pale dusty tan, each plate its own tone, blotched with salt-white dust, fine
    crazing (hairline cracks in a network a few centimeters wide, gated so only some show), tiny pits and sand grains,
    faint shrinkage rings following the plate's outline, a lighter bleached lip where it curls up."""
    mat, g = tk.new_material(name)
    t, rim = A(g, "t"), A(g, "rim")
    co = g.coords()
    tone = g.noise(3.2, detail=5.0)
    base = g.mix(g.ramp(tone, 0.3, 0.7), (0.34, 0.262, 0.178), (0.455, 0.36, 0.255))
    base = ks_.tint_by(g, base, t, (0.82, 0.82, 0.84), (1.18, 1.12, 1.04))
    ph = g.math("ADD", g.noise(9.0, detail=5.0), g.math("MULTIPLY", g.noise(70.0, detail=3.0), 0.12))
    base = g.mix(g.math("MULTIPLY", g.ramp(ph, 0.58, 0.78), 0.55), base, (0.5, 0.455, 0.385))
    clay = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.55, 0.7), 0.4)
    base = g.mix(clay, base, (0.31, 0.2, 0.12))
    # crazing: the cracks of a finer network, wobbly, only some of them showing
    w1 = kf._warped(g, 14.0, 0.012, kf._warped(g, 3.5, 0.03))
    ce = kf._voronoi(g, 20.0, w1, feature="DISTANCE_TO_EDGE")
    gate = g.ramp(g.noise(4.0, detail=3.0), 0.42, 0.62)
    craze = g.math("MULTIPLY", g.ramp(ce, 0.0125, 0.0), gate)
    ce2 = kf._voronoi(g, 75.0, kf._warped(g, 40.0, 0.004), feature="DISTANCE_TO_EDGE")
    micro = g.math("MULTIPLY", g.ramp(ce2, 0.006, 0.0), g.ramp(g.noise(7.0, detail=3.0), 0.5, 0.72))
    base = g.mix(g.math("MULTIPLY", g.ramp(ce, 0.035, 0.0), 0.28), base, (0.2, 0.15, 0.1))
    base = g.mix(g.math("MULTIPLY", craze, 0.9), base, (0.055, 0.04, 0.028))
    base = g.mix(g.math("MULTIPLY", micro, 0.55), base, (0.1, 0.075, 0.05))
    # grains and pits
    gd, gr = kf._cells(g, 400.0)
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.4), base, (0.5, 0.45, 0.36))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.25, 0.05), 0.4), base, (0.1, 0.075, 0.05))
    pd, pr = kf._cells(g, 130.0, kf._warped(g, 30.0, 0.003))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.2, 0.08), g.ramp(pr, 0.6, 0.85))
    base = g.mix(g.math("MULTIPLY", pit, 0.65), base, (0.08, 0.06, 0.04))
    # shrinkage rings round the outline, and the bleached curling lip
    ring = g.math("SINE", g.math("ADD", g.math("MULTIPLY", rim, 38.0), g.math("MULTIPLY", g.noise(8.0, detail=3.0), 7.0)))
    base = g.mix(g.math("MULTIPLY", g.ramp(ring, 0.6, 1.0), 0.18), base, (0.45, 0.4, 0.32))
    base = g.mix(g.math("MULTIPLY", g.ramp(rim, 0.82, 1.0), g.ramp(g.noise(10.0, detail=4.0), 0.3, 0.6)), base,
                 (0.46, 0.41, 0.33))
    base = g.mix(g.math("MULTIPLY", g.ramp(rim, 0.97, 1.0), 0.6), base, (0.16, 0.115, 0.075))
    col = tk.grade(g, base, sat=1.05, value=0.97)
    height = g.math("ADD", 0.55, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(25.0, detail=4.0), 0.5), 0.35))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("SUBTRACT", ring, 0.0), 0.06))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", craze, 0.7), g.math("ADD", g.math("MULTIPLY", micro, 0.3),
                                                                                              g.math("MULTIPLY", pit, 0.35))))
    height = g.math("ADD", height, g.math("MULTIPLY", gr, 0.12))
    rough = g.mixf(g.ramp(g.noise(8.0, detail=3.0), 0.3, 0.7), 0.88, 0.97)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0035))


def mud_wall(name):
    """The cut edge of a plate, where the cracks show its layers: darker orange-brown clay in thin tan and brown
    strata that follow the edge, crumbling grains, darker deeper down (wd) and grey with dust at the bottom."""
    mat, g = tk.new_material(name)
    t, wd = A(g, "t"), A(g, "wd")
    z = g.separate(g.coords())[2]
    wob = g.math("MULTIPLY", g.noise(14.0, detail=4.0), 6.0)
    strata = g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 650.0), wob))
    fine = g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 2400.0), g.math("MULTIPLY", g.noise(40.0, detail=3.0), 9.0)))
    base = g.mix(g.ramp(g.noise(6.0, detail=4.0), 0.3, 0.7), (0.27, 0.185, 0.115), (0.4, 0.29, 0.19))
    base = g.mix(g.math("MULTIPLY", g.ramp(strata, -0.2, 0.9), 0.5), base, (0.36, 0.29, 0.21))
    base = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.3, 1.0), 0.3), base, (0.12, 0.08, 0.05))
    gd, gr = kf._cells(g, 360.0)
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.4), base, (0.45, 0.38, 0.29))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.25, 0.05), 0.4), base, (0.06, 0.04, 0.03))
    cd, cr = kf._cells(g, 60.0, kf._warped(g, 25.0, 0.004))
    crumb = g.ramp(cd, 0.5, 0.1)
    base = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.5, 0.9), 0.45), base, (0.05, 0.035, 0.024))
    base = tk._multiply_color(g, base, g.mix(g.ramp(wd, 0.0, 1.0), (1.0, 1.0, 1.0), (0.62, 0.58, 0.54)))
    base = g.mix(g.math("MULTIPLY", g.ramp(wd, 0.55, 1.0), g.ramp(g.noise(25.0, detail=4.0), 0.35, 0.65)), base, (0.17, 0.15, 0.12))
    base = ks_.tint_by(g, base, t, (0.88, 0.88, 0.9), (1.12, 1.08, 1.02))
    col = tk.grade(g, base, sat=0.9, value=0.95)
    height = g.math("ADD", g.math("MULTIPLY", crumb, 0.5), g.math("ADD", g.math("MULTIPLY", strata, 0.12), g.math("MULTIPLY", gr, 0.15)))
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(height, 1.0, 0.004))


def mud_floor(name):
    """The floor of the cracks: dark grey-brown dust and silt with tiny flakes of crust and fallen grains."""
    mat, g = tk.new_material(name)
    cd, cr = kf._cells(g, 90.0, kf._warped(g, 30.0, 0.004))
    gd, gr = kf._cells(g, 420.0)
    base = g.mix(g.ramp(g.noise(8.0, detail=5.0), 0.3, 0.7), (0.2, 0.145, 0.09), (0.31, 0.235, 0.155))
    base = g.mix(g.math("MULTIPLY", g.ramp(cr, 0.2, 0.9), 0.5), base, (0.2, 0.165, 0.12))
    base = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.5, 0.9), 0.5), base, (0.07, 0.05, 0.035))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.45), base, (0.4, 0.33, 0.24))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(cd, 0.8, 0.0), 0.6), g.math("MULTIPLY", gr, 0.2))
    return tk.finish(mat, g, tk.grade(g, base, sat=1.05, value=0.95), 0.0, 1.0, g.bump(height, 1.0, 0.004))


top_m, wall_m, floor_m = mud_top("MudTop"), mud_wall("MudWall"), mud_floor("MudFloor")
EX = ks_.STONE_ATTRS + ("rim", "wd")
S = ks_.Set(NAME)
FLOOR = 0.009

# Floor of dust under it all, ragged-edged
ks_.pad(S.gm(floor_m), (0.0, 0.0), 0.44, rnd, sides=32, dome=0.0, lobes=0.16, rings=2, floor=G + FLOOR, stretch=(1.0, 0.9),
        yaw=0.3, lump=0.0, sink=0.012)

# The plates: Voronoi cells of random seeds, pulled back from their neighbors to leave the cracks
YAW = 0.3
seeds = ks_.poisson(40, 0.43, 0.092, rnd, stretch=(1.0, 0.9))
seeds = [Vector((s.x * math.cos(YAW) - s.y * math.sin(YAW), s.x * math.sin(YAW) + s.y * math.cos(YAW))) for s in seeds]
bound = ks_.circle_poly(0.455, 30, stretch=(1.0, 0.92), yaw=YAW, rnd=rnd, wob=0.06)
cells = ks_.voronoi_cells(seeds, bound, 0.02)
count = 0
for seed, poly in zip(seeds, cells):
    if len(poly) < 3 or ks_.area(poly) < 0.0012:
        continue
    c = ks_.centroid(poly)
    rho = math.hypot(c.x * math.cos(YAW) + c.y * math.sin(YAW), (-c.x * math.sin(YAW) + c.y * math.cos(YAW)) / 0.9) / 0.47
    if rho > 0.78 and rnd.random() < 0.42:
        continue
    shrink = 0.0 if rho < 0.7 else rnd.uniform(0.0, 0.03) * (rho - 0.55) * 3.0
    outline = ks_.rounded(poly, rnd, rounds=2 if ks_.area(poly) > 0.011 else 1, wobble=0.0, inset=0.0 + shrink, cut=0.22)
    if ks_.area(outline) < 0.0007:
        continue
    edge = max(0.0, (rho - 0.6) / 0.4)
    ztop = rnd.uniform(0.016, 0.026) * (1.0 - 0.45 * edge)
    curl = rnd.uniform(0.014, 0.034) * (1.0 - 0.35 * edge)
    ks_.plate(S.gm(top_m, EX), S.gm(wall_m, EX), outline, rnd, rnd.random(), ztop, FLOOR, curl=curl,
              curl_phase=rnd.uniform(0, math.tau), dome=-0.002, shoulder=0.006, lump=0.0018, lump_scale=22.0,
              tilt=(rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05)), rings=(0.0, 0.72), undercut=0.008,
              lod=2, seed=rnd.uniform(0, 30))
    count += 1
print("[%s] plates %d" % (SCRIPT, count))

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024, density={"MudTop": 1.0, "MudWall": 1.1, "MudFloor": 0.4})
ks_.preview(SCRIPT, model, PREVIEWS, kind="sand", height=0.05)
print("[%s] done" % SCRIPT)
