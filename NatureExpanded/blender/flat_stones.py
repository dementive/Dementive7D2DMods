"""FlatStones (ground cover, stones): a fragment of a flagstone path: five flat slabs 25 to 45 cm across, laid edge to
edge with cracks of 3 to 4 cm between them, each tilted a little and at its own height, their edges rounded and
chipped, their tops pitted, mottled and crusted with pale lichen; soil in the cracks with cushions of moss and tufts of
grass growing along them. The ragged outer edge lets it melt into grass.

    blender -b --factory-startup --python flat_stones.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ksh  # noqa: E402
import zkit as tk  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "FlatStones", "flat_stones"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(14)
G = nk.GROUND
A = ks_._attr


def flag(name, wall):
    """A flagstone: grey, warm tan or brown-grey by its own number, mottled, a faint bedding that runs its own way,
    sand grains, pits that hold dirt, hairline cracks, crusts of pale grey-green lichen, darker and greener low on its
    sides where it meets the soil, layered strata on the cut edge."""
    mat, g = tk.new_material(name)
    t, L = ks_.stone_frame(g)
    rim = A(g, "rim")
    wd = A(g, "wd")
    fam = g.math("FRACT", g.math("MULTIPLY", t, 9.3))
    base = g.mix(g.ramp(fam, 0.0, 0.5), (0.2, 0.19, 0.17), (0.3, 0.255, 0.19))
    base = g.mix(g.ramp(fam, 0.5, 1.0), base, (0.2, 0.185, 0.165))
    mott = g.noise(5.0, detail=5.0, vector=L)
    base = g.mix(g.ramp(mott, 0.3, 0.7), tuple(c * 0.55 for c in (0.24, 0.225, 0.2)), base)
    z = g.separate(L)[2]
    bed = g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 320.0), g.math("MULTIPLY", g.noise(9.0, detail=3.0, vector=L), 6.0)))
    base = g.mix(g.math("MULTIPLY", g.ramp(bed, 0.2, 1.0), 0.3), base, (0.3, 0.28, 0.24))
    gd, gr = kf._cells(g, 380.0, L)
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.62, 0.95), 0.5), base, (0.36, 0.34, 0.3))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.3, 0.05), 0.5), base, (0.07, 0.065, 0.058))
    pd, pr = kf._cells(g, 70.0, kf._warped(g, 28.0, 0.004, L))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.18, 0.06), g.ramp(pr, 0.4, 0.8))
    base = g.mix(g.math("MULTIPLY", pit, 0.8), base, (0.07, 0.055, 0.04))
    ce = kf._voronoi(g, 2.6, kf._warped(g, 7.0, 0.04, kf._warped(g, 2.0, 0.1, L)), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.0045, 0.0), g.ramp(g.noise(5.0, detail=3.0, vector=L), 0.42, 0.58))
    base = g.mix(g.math("MULTIPLY", g.ramp(ce, 0.03, 0.0), 0.3), base, (0.08, 0.07, 0.06))
    base = g.mix(g.math("MULTIPLY", crack, 0.95), base, (0.015, 0.013, 0.011))
    # lichen: grey-green rosettes and crusts
    lc, lr = kf._cells(g, 8.0, kf._warped(g, 6.0, 0.06, L))
    gate = g.ramp(g.noise(2.2, detail=3.0, vector=L), 0.42, 0.56)
    disc = g.math("MULTIPLY", g.ramp(lc, 0.5, 0.34), g.math("MULTIPLY", g.ramp(lr, 0.3, 0.55), gate))
    gran, _ = kf._cells(g, 420.0)
    disc = g.math("MULTIPLY", disc, g.ramp(gran, 0.8, 0.3))
    base = g.mix(g.math("MULTIPLY", disc, 0.85), base, g.mix(g.ramp(lr, 0.5, 0.95), (0.22, 0.235, 0.17), (0.4, 0.38, 0.24)))
    # dust, and rim wear
    base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(10.0, detail=5.0, vector=L), 0.6, 0.78), 0.3), base, (0.1, 0.082, 0.06))
    base = g.mix(g.math("MULTIPLY", g.ramp(rim, 0.78, 1.0), 0.4), base, (0.135, 0.12, 0.1))
    col = ks_.tint_by(g, base, t, (0.88, 0.88, 0.9), (1.14, 1.08, 1.02))
    height = g.math("ADD", g.math("MULTIPLY", gr, 0.22), g.math("SUBTRACT", 0.5, g.math("MULTIPLY", pit, 0.45)))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.55))
    height = g.math("ADD", height, g.math("MULTIPLY", disc, 0.2))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(30.0, detail=4.0, vector=L), 0.5), 0.35))
    rough = g.mixf(disc, 0.9, 0.95)
    if wall:
        zz = g.separate(g.coords())[2]
        st = g.math("SINE", g.math("ADD", g.math("MULTIPLY", zz, 520.0), g.math("MULTIPLY", g.noise(12.0, detail=3.0), 5.0)))
        col = g.mix(g.math("MULTIPLY", g.ramp(st, 0.0, 1.0), 0.28), col, (0.075, 0.065, 0.055))
        col = tk._multiply_color(g, col, g.mix(wd, (0.82, 0.82, 0.82), (0.5, 0.5, 0.48)))
        height = g.math("ADD", height, g.math("MULTIPLY", st, 0.12))
    # moss stain low on the sides, dirt packed against the ground
    mcol, mh, mrough, _ = kf.moss_layer(g)
    zg = g.separate(g.coords())[2]
    low = g.ramp(zg, G + 0.028, G + 0.004)
    stain = g.math("MULTIPLY", low, g.ramp(g.noise(18.0, detail=5.0), 0.38, 0.6))
    col = g.mix(g.math("MULTIPLY", stain, 0.55), col, tk.grade(g, mcol, sat=0.9, value=0.85))
    col, height, rough = ks_.over_soil(g, col, height, rough, 0.8, z_lo=0.006, z_hi=0.022, splotch=0.45)
    col = tk.grade(g, col, sat=0.92, value=0.98)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0045))


top_m, wall_m = flag("FlagTop", False), flag("FlagEdge", True)
moss_m = ks_.moss_mound("FlagMoss")
soil_m = ks_.soil_material("FlagSoil", relief=0.005)
grass_m = nk.plant("FlagGrass", (0.2, 0.25, 0.09), (0.3, 0.3, 0.13), rough=0.75, vary=0.35)
EX = ks_.STONE_ATTRS + ("rim", "wd")

S = ks_.Set(NAME)
b = ksh.Builder("Fg")

# soil under and between the slabs, ragged at the rim
ks_.pad(S.gm(soil_m), (0.0, 0.0), 0.43, rnd, sides=34, dome=0.0, lobes=0.16, rings=2, floor=G + 0.003, stretch=(1.05, 0.86),
        yaw=0.15, lump=0.0, sink=0.012)

YAW = 0.15
seeds = [Vector(p) for p in ((-0.2, -0.13), (0.17, -0.18), (0.3, 0.12), (-0.04, 0.12), (-0.3, 0.25))]
seeds = [s * 0.93 + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03))) for s in seeds]
bound = ks_.circle_poly(0.455, 30, stretch=(1.0, 0.85), yaw=YAW, rnd=rnd, wob=0.05)
GAP = 0.04
cells = ks_.voronoi_cells(seeds, bound, GAP)


def _contains(poly, p):
    inside = False
    for k, a in enumerate(poly):
        bb = poly[(k + 1) % len(poly)]
        if (a.y > p.y) != (bb.y > p.y) and p.x < (bb.x - a.x) * (p.y - a.y) / (bb.y - a.y + 1e-12) + a.x:
            inside = not inside
    return inside


def inside_any(p, skip):
    return any(j != skip and len(c) >= 3 and _contains(c, p) for j, c in enumerate(cells))


outlines = []
for i, poly in enumerate(cells):
    if len(poly) < 3:
        continue
    out = ks_.rounded(poly, rnd, rounds=1, wobble=0.03, inset=0.0, cut=0.22)
    outlines.append((i, poly, out))
    ztop = rnd.uniform(0.022, 0.042)
    ks_.plate(S.gm(top_m, EX), S.gm(wall_m, EX), out, rnd, rnd.random(), ztop, -0.02, curl=rnd.uniform(0.0, 0.006),
              curl_phase=rnd.uniform(0, math.tau), dome=rnd.uniform(0.0, 0.006), shoulder=0.016, lump=0.0035, lump_scale=9.0,
              tilt=(rnd.uniform(-0.07, 0.07), rnd.uniform(-0.07, 0.07)), rings=(0.0, 0.5, 0.82, 0.95), undercut=0.0,
              lod=2, seed=rnd.uniform(0, 30))

# Moss cushions and grass along the cracks
mossG = S.gm(moss_m)
spots = []
for i, poly, out in outlines:
    c = ks_.centroid(poly)
    for k, a in enumerate(poly):
        q = poly[(k + 1) % len(poly)]
        e = q - a
        if e.length < 0.07:
            continue
        nrm = Vector((e.y, -e.x)).normalized()
        if (a - c).dot(nrm) < 0:
            nrm = -nrm
        m = (a + q) * 0.5
        shared = inside_any(m + nrm * (GAP * 0.9), i)
        n = int(e.length / (0.11 if shared else 0.18))
        for s in range(n):
            f = (s + rnd.uniform(0.2, 0.8)) / max(1, n)
            p = a + e * f + nrm * (GAP * 0.45 if shared else 0.0)
            if rnd.random() < (0.85 if shared else 0.45):
                spots.append((p, shared))
for p, shared in spots:
    r = rnd.uniform(0.04, 0.075) if shared else rnd.uniform(0.03, 0.055)
    ks_.mound(mossG, (p.x, p.y), r, rnd.uniform(0.022, 0.04), rnd, sides=10, rings=2, sink=0.012)
    if rnd.random() < 0.4:
        for j in range(rnd.randint(4, 7)):
            ang = rnd.uniform(0, math.tau)
            base = (p.x + rnd.uniform(-0.02, 0.02), p.y + rnd.uniform(-0.02, 0.02), G + 0.008)
            d = Vector((math.cos(ang) * rnd.uniform(0.2, 0.5), math.sin(ang) * rnd.uniform(0.2, 0.5), 1.0))
            ksh.leaf(b, grass_m, base, d, rnd.uniform(0.06, 0.15), rnd.uniform(0.01, 0.016), bend=rnd.uniform(0.3, 0.9), fold=0.2,
                     profile="lance", rows=2)

pieces = S.objects() + b.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024,
                   density={"FlagTop": 1.0, "FlagEdge": 0.8, "FlagMoss": 0.9, "FlagSoil": 0.35, "FlagGrass": 0.3})
ks_.preview(SCRIPT, model, PREVIEWS, kind="grass", height=0.06)
print("[%s] done" % SCRIPT)
