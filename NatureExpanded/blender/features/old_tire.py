"""OldTire (anywhere roads or farms once were): a rimless car tire, years dead, tipped on its edge and half sunk in the ground,
the sidewall crazed with ozone cracks and moulded with worn pseudo-lettering, the tread bald in the middle, grey UV bloom on
the rubber, soil and leaf litter heaped in the well, a weed growing out of it. Solid (voxelized closed mesh), about 0.3 m
high above the ground: short enough to step over.

    blender -b --factory-startup --python old_tire.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import singleskit as sk  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]

TILT, YAW = 41.0, 24.0
R = Matrix.Rotation(math.radians(YAW), 3, "Z") @ Matrix.Rotation(math.radians(TILT), 3, "X")
CENTER = Vector((0.02, -0.01, G + 0.075))
RO = 0.292                       # outer radius
HALF = [(0.2935, 0.0), (0.2925, 0.04), (0.289, 0.066), (0.278, 0.083), (0.255, 0.093), (0.222, 0.098), (0.205, 0.092), (0.178, 0.086),
        (0.172, 0.074), (0.179, 0.06), (0.18, 0.0)]
NSEG = 72


def closed_catmull(pts, sub=2):
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for s in range(sub):
            f = s / sub
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3))
    return out


def profile():
    prof = [Vector((r, -h)) for r, h in HALF] + [Vector((r, h)) for r, h in reversed(HALF[1:-1])]
    return closed_catmull(prof, 2)


def T(p):
    return CENTER + R @ Vector(p)


def tire_shape(rnd):
    prof = profile()
    ph = rnd.uniform(0, 6.28)
    rings = []
    for i in range(NSEG):
        th = i / NSEG * math.tau
        c, s = math.cos(th), math.sin(th)
        ring = []
        # out of round, sagging, a flat spot and dents where it lay
        sag = 1.0 + 0.012 * math.sin(th * 2 + ph) + 0.008 * math.sin(th * 3 + 2 * ph)
        for q in prof:
            r, h = q.x, q.y
            n = sk.fbm((c * r * 9, s * r * 9, h * 9), 3.0) * 0.004 + sk.fbm((c * r * 3, s * r * 3, h * 3), 4.0) * 0.006
            r2 = (r + n) * sag
            h2 = h * (1.0 + 0.04 * math.sin(th * 5 + ph)) + 0.004 * sk.fbm((c * 4, s * 4, h * 6), 5.0)
            ring.append(T(Vector((r2 * c, r2 * s, h2))))
        rings.append(ring)
    return sk.loft(rings, close_u=True, close_v=True)


def build(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 17 + 9)
    rub = sk.rubber_mat("TireRubber", CENTER, tuple(math.degrees(a) for a in R.to_euler("XYZ")))
    skirt = sk.soil_small("TireSkirt", moss=0.0)
    soil = sk.soil_small("TireSoil", moss=0.35, stony=1.0)
    mossm = sk.moss_clump_mat("TireMoss")
    bed = sk.litter_bed("TireBed")
    lits = sk.litter_mats("TrLf")
    gm = nk.plant("TrGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("TrGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    weed = nk.plant("TrPlantain", (0.06, 0.13, 0.035), (0.1, 0.18, 0.05), rough=0.65, vary=0.35, sat=0.8, value=0.62)
    twig = ks.bark("TrTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    b = ks.Builder(name)

    shape = tire_shape(rnd)
    mats = [skirt if max(shape.verts[i].z for i in poly) < G - 0.04 else rub for poly in shape.polys]
    sk.emit(b, shape, None, mats=mats, lod=2, below=G - 0.2)

    axis = R @ Vector((0.0, 0.0, 1.0))                  # the way the well faces
    # The well: earth heaped in, leaves and a weed in it
    well_c = CENTER + axis * 0.0
    fill_top = 0.045
    sk.cushion(b, soil, well_c - axis * 0.01, axis, 0.185, fill_top, rnd, sides=22, rings=4, sink=0.0, lump=0.25)
    ax, u, v = ks.basis(axis)
    for i in range(46):
        a = rnd.uniform(0, math.tau)
        rr = 0.165 * math.sqrt(rnd.random())
        p = well_c + u * (math.cos(a) * rr) + v * (math.sin(a) * rr) + axis * (fill_top * (1.0 - (rr / 0.185) ** 2) ** 0.7 + 0.006 + 0.03 * rnd.random() * (i > 36))
        d = u * math.cos(rnd.uniform(0, 6.28)) + v * math.sin(rnd.uniform(0, 6.28))
        d = (d + axis * 0.1).normalized()
        ln = rnd.uniform(0.05, 0.085)
        sk.leaf_shape(b, rnd.choice(lits), p, d, ln, ln * rnd.uniform(0.5, 0.8), kind=rnd.choice(("oak", "maple", "oval", "narrow")), rows=4,
                      bend=rnd.uniform(-0.25, 0.35), fold=rnd.uniform(0.1, 0.5), roll=rnd.uniform(-25, 25), ph=rnd.uniform(0, 6.28), normal=axis)
    sk.cushion(b, mossm, well_c + axis * 0.02 + u * 0.1, axis, 0.06, 0.02, rnd, sides=14, rings=3, lump=0.5)
    # a weed rooted in the well
    wroot = well_c + axis * 0.05 - u * 0.05
    sk.rosette(b, weed, wroot.x, wroot.y, rnd, leaves=9, length=(0.07, 0.12), width=0.045, z=wroot.z, tilt=(25, 60), bound=(-0.5, 0.5, -0.5, 0.5))
    sk.grass(b, gm, wroot.x + 0.04, wroot.y + 0.03, rnd, blades=12, height=(0.2, 0.42), spread=0.04, lean=0.6, z=wroot.z, dry=gd, dry_share=0.4,
             bound=(-0.5, 0.5, -0.5, 0.5))

    # The ground round it
    hfun = sk.mound(b, bed, (0.0, 0.0), 0.46, rnd, dome=0.05, sides=26, rings=4, sink=0.05, jitter=0.35, lump=0.012)
    lim = 0.41
    sk.litter(b, lits, 70, rnd, (-lim, lim, -lim, lim), keep=lambda x, y: math.hypot(x, y) > 0.3, size=(0.05, 0.085), rows=4, ground=hfun)
    sk.twigs(b, twig, 3, rnd, (-lim, lim, -lim, lim), keep=lambda x, y: math.hypot(x, y) > 0.3, length=(0.1, 0.25), z=G + 0.01)
    for (gx, gy, n) in ((-0.36, 0.3, 12), (0.38, -0.32, 11), (0.3, 0.38, 8), (-0.4, -0.3, 8)):
        sk.grass(b, gm, gx, gy, rnd, blades=n, height=(0.2, 0.5), spread=0.05, lean=0.7, z=hfun(gx, gy), dry=gd, dry_share=0.4, bound=(-0.5, 0.5, -0.5, 0.5))

    density = {"TireRubber": 1.7, "TireSkirt": 0.08, "TireSoil": 0.55, "TireBed": 0.6, "TireMoss": 0.6, "TrLf": 0.4, "TrGrass": 0.3, "TrGrassDry": 0.3,
               "TrPlantain": 0.3, "TrTwig": 0.15}
    model = sk.finish_export(name, b, [shape.body()], FEATURES, 1024, density, voxel=0.045, margin=0.012, limit=110, coarse=0.5)
    ex, ey, top = sk.bounds_report(name, model)
    shots = sk.standard_shots(top, reach=0.3)
    shots.append(("tread", CENTER + Vector((0.3, -0.4, 0.45)), CENTER + Vector((0.0, -0.12, 0.2)), 40))
    shots.append(("side", CENTER + Vector((-0.45, -0.5, 0.2)), CENTER + Vector((0.0, 0.0, 0.05)), 40))
    sk.preview(name, model, shots, PREVIEWS)
    print("[%s] done" % name)


for n in (ONLY or ["OldTire"]):
    build(n)
