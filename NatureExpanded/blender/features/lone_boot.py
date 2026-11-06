"""LoneBoot (forest, wasteland, anywhere): one old leather work boot, lying on its side with the toe tipped up out of the dirt,
the heel and the lower half sunk, the leather dried and cracked into a net, scuffed pale at the toe, mold and salt bloom,
the laces rotted to a few cords, the shaft slumped, moss and earth filling the heel and the opening. Walk-through (Collide
melee) with one box.

    blender -b --factory-startup --python lone_boot.py -- <features folder> <preview folder> [Name ...]
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

# The boot upright, sole down, toe +x, in meters from the heel's bottom (z = 0); tables by height above the sole bottom
ZB = 0.026                                                  # the forefoot sole's bottom (the heel block reaches lower)
TZ = [0.0, 0.012, 0.03, 0.045, 0.06, 0.08, 0.10, 0.125, 0.15, 0.175]     # above ZB
TXB = [-0.052, -0.051, -0.049, -0.048, -0.047, -0.046, -0.045, -0.044, -0.043, -0.042]
TXF = [0.268, 0.264, 0.243, 0.205, 0.152, 0.125, 0.105, 0.092, 0.085, 0.081]
THW = [0.057, 0.058, 0.058, 0.056, 0.053, 0.051, 0.05, 0.05, 0.05, 0.051]
TPP = [2.8, 2.7, 2.6, 2.5, 2.4, 2.3, 2.2, 2.15, 2.1, 2.1]
C0 = Vector((0.1, 0.0, 0.1))
ROLL, PITCH, YAW = 58.0, -26.0, -28.0
R = Matrix.Rotation(math.radians(YAW), 3, "Z") @ Matrix.Rotation(math.radians(PITCH), 3, "Y") @ Matrix.Rotation(math.radians(ROLL), 3, "X")
N = 40


def interp(z, tab):
    z = max(TZ[0], min(TZ[-1], z))
    for i in range(len(TZ) - 1):
        if z <= TZ[i + 1]:
            f = (z - TZ[i]) / (TZ[i + 1] - TZ[i])
            return tab[i] + (tab[i + 1] - tab[i]) * f
    return tab[-1]


def sgn_pow(x, e):
    return math.copysign(abs(x) ** e, x)


def smooth(x, lo, hi):
    return sk.smooth(x, lo, hi)


def loop(zr, scale=1.0, grow=0.0, k_deform=True, rnd_seed=0.0):
    """The boot's horizontal section at height zr above the forefoot sole bottom, as N points (z is boot-frame height)."""
    xb, xf, hw, pp = interp(zr, TXB), interp(zr, TXF), interp(zr, THW), interp(zr, TPP)
    xc, hx = (xb + xf) / 2.0, (xf - xb) / 2.0
    pts = []
    for k in range(N):
        a = k / N * math.tau
        c, s = math.cos(a), math.sin(a)
        xr, yr = sgn_pow(c, 2.0 / pp), sgn_pow(s, 2.0 / pp)
        x = xc + hx * xr * scale + grow * c
        taper = 0.78 + 0.22 * smooth(xc + hx * xr - xb, 0.0, 0.15)
        y = hw * yr * taper * scale + grow * s
        z = ZB + zr
        if k_deform:
            # the slumped shaft: the side that ends up uppermost sinks in, the top squashes
            top = smooth(zr, 0.06, 0.17)
            if y > 0:
                y *= 1.0 - 0.28 * top * smooth(y, 0.0, 0.03)
            x = xc + (x - xc) * (1.0 - 0.14 * top)
            y += 0.012 * top
            # creases across the ankle and the toe, and a sagging vamp
            w = 0.0
            if 0.05 < zr < 0.15 and c > 0.1:
                w = 0.0042 * max(0.0, math.sin(zr * 230.0 + 5.0 * sk.fbm((x * 20, y * 20, zr * 8), 1.0))) * smooth(zr, 0.05, 0.08) * smooth(0.15, zr, 0.12)
            if zr < 0.06 and c > 0.2:
                w += 0.003 * max(0.0, math.sin(x * 160.0 + 3.0 * sk.fbm((x * 12, y * 12, 0.0), 2.0)))
            x -= w * c
            y -= w * s
            # the lacing groove down the front
            if c > 0.15 and zr > 0.045:
                gd = 0.0125 * math.exp(-(y / 0.0125) ** 2) * smooth(zr, 0.045, 0.075)
                x -= gd
            # leather lumps
            n = sk.fbm((x * 24, y * 24, z * 24), 3.0) * 0.0026 + sk.fbm((x * 7, y * 7, z * 7), 4.0) * 0.0036
            x += n * c
            y += n * s
            z += 0.011 * smooth(x, 0.12, 0.27) ** 2 * (1.0 if zr < 0.07 else 0.0)
        pts.append(Vector((x, y, z)))
    return pts


def build(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 13 + 1)
    # placement: the lowest point of the boot sinks 4 cm below the ground; centre the bounding box
    probe = [R @ (p - C0) for zr in (0.0, 0.05, 0.1, 0.175) for p in loop(zr)] + [R @ (Vector((-0.05, 0.0, 0.0)) - C0), R @ (Vector((0.27, 0.0, ZB)) - C0)]
    zmin = min(p.z for p in probe)
    cx = (min(p.x for p in probe) + max(p.x for p in probe)) / 2
    cy = (min(p.y for p in probe) + max(p.y for p in probe)) / 2
    O = Vector((-cx + 0.02, -cy, G - 0.03 - zmin))
    P = lambda p: O + R @ (Vector(p) - C0)
    eul = tuple(math.degrees(a) for a in R.to_euler("XYZ"))
    ground_cut = G - 0.06

    leather = leather_mat("BootLeather", O, eul)
    sole = sole_mat("BootSole", O, eul)
    lining = lining_mat("BootLining")
    cord = cord_mat("BootCord")
    eyelet = sk.rust_mat("BootEyelet", rust=1.0, scale=4.0, streak=0.0, grime=0.3, paint=None)
    soil = sk.soil_small("BootSoil", moss=0.2, stony=0.8)
    mossm = sk.moss_clump_mat("BootMoss")
    bed = sk.litter_bed("BootBed")
    lits = sk.litter_mats("BtLf")
    gm = nk.plant("BtGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("BtGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    weed = nk.plant("BtPlantain", (0.06, 0.13, 0.035), (0.1, 0.18, 0.05), rough=0.65, vary=0.35, sat=0.8, value=0.62)
    twig = ks.bark("BtTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    b = ks.Builder(name)

    # The upper: slices from the welt to the collar, over the lip, down the inside
    zs = [0.0, 0.008, 0.02, 0.034, 0.048, 0.062, 0.076, 0.09, 0.105, 0.12, 0.135, 0.15, 0.165, 0.178]
    rings = [[P(p) for p in loop(zr)] for zr in zs]
    top = zs[-1]
    lip = [(0.003, 1.02, 0.004), (0.01, 1.055, 0.003), (0.016, 1.0, -0.002), (0.016, 0.93, -0.01), (0.008, 0.9, -0.008)]
    outer_n = len(rings)
    base = loop(top)
    cen = sum(base, Vector()) / N
    for dz, sc, gr in lip:
        rings.append([P(cen + (p - cen) * sc + Vector((0, 0, dz))) for p in base])
    inner_start = len(rings)
    for f, dz, sc in ((0.0, -0.03, 0.9), (0.0, -0.065, 0.86), (0.0, -0.1, 0.8), (0.0, -0.13, 0.5)):
        rings.append([P(cen + (p - cen) * sc + Vector((0.0, 0.0, dz - 0.0))) for p in base])
    up = sk.loft(rings, cap_end=True)
    mats = []
    for pi in range(len(up.polys)):
        ri = pi // N
        mats.append(lining if ri >= inner_start - 2 else leather)
    # cap polygons (the fan at the end) belong to the lining
    sk.emit(b, up, None, mats=mats, below=ground_cut, lod=0)

    # The sole and welt
    srings = []
    for dz, sc in ((-0.014, 0.94), (-0.011, 0.99), (-0.004, 1.03), (0.0, 1.04), (0.006, 1.01)):
        srings.append([P(Vector((p.x, p.y, p.z + dz))) for p in loop(0.0, sc, 0.0, k_deform=False)])
    so = sk.loft(srings, cap_start=True)
    sk.emit(b, so, sole, below=ground_cut)
    # The heel block under the heel
    hblock = sk.block(P(Vector((-0.012, 0.0, 0.0175))), (0.04, 0.036, 0.0175), R, r=0.004, step=0.02, nr=2)
    sk.emit(b, hblock, sole, below=ground_cut)

    # Eyelets and what is left of the laces, on the front slope either side of the groove
    eyes = []
    for zr in (0.06, 0.088, 0.116, 0.144, 0.17):
        row = loop(zr)
        for sign in (1, -1):
            best = min(range(N), key=lambda k: abs(row[k].y - sign * 0.021) + (0.0 if row[k].x > interp(zr, TXB) + 0.05 else 1.0))
            p = row[best]
            nrm = Vector((p.x - (interp(zr, TXB) + interp(zr, TXF)) / 2, p.y * 0.3, 0.0))
            if nrm.length < 1e-4:
                nrm = Vector((1, 0, 0))
            nrm = (nrm.normalized() + Vector((0, 0, 0.55))).normalized() if zr < 0.07 else (nrm.normalized() + Vector((0, 0, 0.12))).normalized()
            eyes.append((P(p), R @ nrm, sign, zr))
    for pw, nw, sign, zr in eyes:
        ax, u, v = ks.basis(nw)
        rr = 0.0046
        pts = [pw + u * (math.cos(a) * rr) + v * (math.sin(a) * rr) + nw * 0.0012 for a in [k / 9 * math.tau for k in range(10)]]
        sk.sweep(b, eyelet, pts, [0.0017] * 10, sides=5, close_loop=False, cap_start=True, cap_end=True)
    # laces: two surviving crossings, loose ends hanging, one frayed
    def lace(pa, pb, sag=0.01, r=0.0017):
        mid = (pa + pb) / 2 + Vector((0, 0, 0.0)) - (R @ Vector((1, 0, 0))) * sag
        pts = [pa + (mid - pa) * 0.5 * 0 + (pb - pa) * f + (mid - (pa + pb) / 2) * (1 - (2 * f - 1) ** 2) for f in (0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        sk.sweep(b, cord, pts, [r, r, r * 1.1, r, r, r * 0.9], sides=5, cap_start=True, cap_end=True)
    byz = {}
    for pw, nw, sign, zr in eyes:
        byz.setdefault(zr, {})[sign] = pw
    zlist = sorted(byz)
    lace(byz[zlist[0]][1], byz[zlist[1]][-1])
    lace(byz[zlist[1]][1], byz[zlist[2]][-1], sag=0.012)
    lace(byz[zlist[3]][-1], byz[zlist[4]][1], sag=0.008)
    # dangling ends from the top pair
    for sign, ln, dr in ((1, 0.085, (0.2, 0.7, -0.4)), (-1, 0.05, (-0.1, -0.8, -0.3))):
        p0 = byz[zlist[-1]][sign]
        d = Vector(dr).normalized()
        d = R @ d
        d.z = min(d.z, -0.1)
        d.normalize()
        pts = [p0 + d * (ln * f) + Vector((0, 0, -0.03 * f * f)) for f in (0, 0.25, 0.5, 0.75, 1.0)]
        sk.sweep(b, cord, pts, [0.0018, 0.0017, 0.0016, 0.0014, 0.0008], sides=5, cap_start=False, cap_end=True, shift1=lambda a: 0.0)
    # the tongue lolling out at the collar
    tc = P(Vector((0.082, 0.0, top + ZB + 0.012)))
    tg = sk.block(tc, (0.022, 0.0026, 0.04), R @ Matrix.Rotation(math.radians(-58.0), 3, "Y"), r=0.002, step=0.015, nr=2,
                  deform=lambda q, n: q + Vector((0.0, 0.004 * math.sin(q.z * 70.0), 0.0)) + n * sk.fbm((q.x * 40, q.y * 40, q.z * 40), 7.0) * 0.0015)
    sk.emit(b, tg, leather, below=ground_cut)

    # Moss in the heel and the opening, earth fill, a mound round the boot
    rimc = P(cen + Vector((0.0, 0.0, top + ZB - 0.02)))
    nrm_up = R @ Vector((0.0, 0.0, 1.0))
    sk.cushion(b, soil, rimc - nrm_up * 0.01, nrm_up, 0.05, 0.025, rnd, sides=14, squash=(1.0, 0.8))
    heel_moss_c = P(Vector((-0.043, 0.0, ZB + top - 0.02)))
    sk.cushion(b, mossm, heel_moss_c, R @ Vector((-0.3, 0.0, 1.0)), 0.048, 0.03, rnd, sides=16, rings=4, lump=0.5)
    sk.cushion(b, mossm, rimc + (R @ Vector((0.012, 0.0, 0.0))), nrm_up, 0.035, 0.022, rnd, sides=14, rings=4, lump=0.5)
    sk.cushion(b, mossm, P(Vector((0.02, 0.06, ZB + 0.02))), R @ Vector((0.0, 1.0, 0.3)), 0.03, 0.015, rnd, sides=12, rings=3)
    hfun = sk.mound(b, bed, (0.0, 0.0), 0.4, rnd, dome=0.04, sides=26, rings=4, sink=0.05, jitter=0.35, lump=0.01, skew=(1.1, 0.9))
    lim = 0.41
    keep = lambda x, y: True
    sk.litter(b, lits, 72, rnd, (-lim, lim, -lim, lim), keep=keep, size=(0.05, 0.085), rows=4, ground=hfun)
    sk.litter(b, lits, 12, rnd, (-0.25, 0.25, -0.2, 0.2), keep=keep, size=(0.05, 0.08), rows=4, lift=0.08, ground=hfun)
    sk.twigs(b, twig, 4, rnd, (-lim, lim, -lim, lim), length=(0.1, 0.25), z=G + 0.01)
    for (gx, gy, n) in ((-0.36, 0.28, 12), (0.38, -0.3, 11), (0.3, 0.38, 7), (-0.4, -0.36, 7), (0.0, 0.42, 6)):
        sk.grass(b, gm, gx, gy, rnd, blades=n, height=(0.2, 0.5), spread=0.06, lean=0.7, z=hfun(gx, gy), dry=gd, dry_share=0.4, bound=(-0.5, 0.5, -0.5, 0.5))
    sk.rosette(b, weed, 0.3, 0.16, rnd, leaves=8, length=(0.07, 0.12), width=0.04, z=hfun(0.3, 0.16), bound=(-0.5, 0.5, -0.5, 0.5))

    # Collider: one box over the boot
    allp = [p for r in rings for p in r]
    xs, ys, zs_ = [p.x for p in allp], [p.y for p in allp], [p.z for p in allp]
    lo_z = max(G, min(zs_))
    extra = ["box %.3f %.3f %.3f %.3f %.3f %.3f" % ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (lo_z + max(zs_)) / 2,
                                                     (max(xs) - min(xs)) * 0.9, (max(ys) - min(ys)) * 0.9, (max(zs_) - lo_z) * 0.9)]
    density = {"BootLeather": 1.7, "BootSole": 0.9, "BootLining": 0.35, "BootCord": 0.25, "BootEyelet": 0.2, "BootSoil": 0.5, "BootBed": 0.6,
               "BootMoss": 0.8, "BtLf": 0.35, "BtGrass": 0.3, "BtGrassDry": 0.3, "BtPlantain": 0.3, "BtTwig": 0.15}
    model = sk.finish_export(name, b, [], FEATURES, 1024, density, extra=extra, coarse=0.5)
    ex, ey, topz = sk.bounds_report(name, model)
    c = P(C0 - Vector((0, 0, 0.0)))
    shots = sk.standard_shots(topz, reach=0.25)
    shots.append(("boot", c + Vector((0.3, -0.5, 0.35)), c, 40))
    shots.append(("toe", c + Vector((0.45, -0.1, 0.25)), c + Vector((0.12, 0.0, 0.0)), 40))
    shots.append(("heel", c + Vector((-0.4, 0.2, 0.4)), c + Vector((-0.04, 0.0, 0.0)), 40))
    sk.preview(name, model, shots, PREVIEWS)
    print("[%s] done" % name)


# ---------------------------------------------------------------- materials

def leather_mat(name, O, eul):
    mat, g = tk.new_material(name)
    L = sk.local_coords(g, O, eul)
    lcx, lcy, lcz = g.separate(L)
    lx = g.math("ADD", lcx, C0.x)
    ly = lcy
    lz = g.math("ADD", lcz, C0.z)
    co = g.coords()
    z = g.separate(co)[2]
    tone = g.noise(4.0, detail=5.0, distortion=0.3)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.034, 0.02, 0.012), (0.085, 0.049, 0.028))
    # dried out, greying
    dry = g.math("MULTIPLY", g.ramp(g.noise(5.5, detail=5.0, distortion=0.4), 0.62, 0.78), 0.5)
    col = g.mix(dry, col, g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.3, 0.7), (0.095, 0.07, 0.05), (0.15, 0.115, 0.082)))
    # pebbled grain
    gc, gr_ = kf._cells(g, 340.0, kf._warped(g, 30.0, 0.0015))
    col = g.mix(g.math("MULTIPLY", g.ramp(gc, 0.45, 0.18), 0.35), col, (0.02, 0.012, 0.007))
    # a net of cracks: wide ones and fine crazing
    ce = kf._voronoi(g, 30.0, kf._warped(g, 9.0, 0.012), feature="DISTANCE_TO_EDGE")
    wide = g.math("MULTIPLY", g.ramp(ce, 0.07, 0.0), g.ramp(g.noise(4.0, detail=3.0), 0.3, 0.55))
    ce2 = kf._voronoi(g, 130.0, kf._warped(g, 22.0, 0.004), feature="DISTANCE_TO_EDGE")
    fine = g.math("MULTIPLY", g.ramp(ce2, 0.08, 0.0), g.ramp(g.noise(8.0, detail=3.0), 0.35, 0.62))
    col = g.mix(g.math("MULTIPLY", g.math("MAXIMUM", wide, fine), 0.75), col, g.mix(g.ramp(g.noise(40.0, detail=3.0), 0.3, 0.7), (0.15, 0.108, 0.075), (0.21, 0.16, 0.11)))
    col = g.mix(g.math("MULTIPLY", g.math("MAXIMUM", wide, fine), g.ramp(ce, 0.012, 0.0)), col, (0.008, 0.005, 0.003))
    # scuffed pale at the toe cap, along the welt, over the creases
    toe = g.math("MULTIPLY", g.ramp(lx, 0.15, 0.22), g.ramp(lz, 0.14, 0.05))
    sc = g.ramp(g.noise(55.0, detail=5.0, distortion=0.2), 0.45, 0.66)
    scuff = g.math("MULTIPLY", g.math("ADD", toe, g.math("MULTIPLY", g.ramp(lz, 0.07, 0.03), 0.6)), sc)
    col = g.mix(g.math("MULTIPLY", scuff, 0.8), col, g.mix(g.ramp(g.noise(200.0), 0.3, 0.7), (0.19, 0.145, 0.095), (0.3, 0.24, 0.17)))
    # salt tide-marks and mold
    tide = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=ks._stretched(g, (3.5, 3.5, 30.0))), 0.62, 0.72), 0.5)
    col = g.mix(tide, col, (0.26, 0.245, 0.21))
    mold = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=5.0, distortion=0.3), 0.6, 0.74), g.ramp(g.noise(4.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", mold, 0.6), col, g.mix(g.ramp(g.noise(150.0), 0.3, 0.7), (0.12, 0.15, 0.09), (0.22, 0.24, 0.19)))
    # welt stitching row, toe-cap seam stitching
    for sx, sz0, sz1 in ((0.155, 0.032, 0.12),):
        seam = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", 0.0016, g.math("ABSOLUTE", g.math("SUBTRACT", lx, sx))), 0.0, 0.0009),
                      g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", ly, 0.8), g.math("MULTIPLY", lz, 0.6)), 230.0)), 0.5)), 0.5, 0.2))
        col = g.mix(g.math("MULTIPLY", seam, 0.7), col, (0.2, 0.17, 0.12))
    # earth: splashed from the ground, caked in the creases
    cav = g.cavity(0.012)
    caked = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), g.ramp(g.noise(9.0, detail=5.0), 0.3, 0.62))
    col = g.mix(g.math("MULTIPLY", caked, 0.8), col, (0.034, 0.024, 0.015))
    soilm = g.math("MULTIPLY", g.ramp(z, G + 0.08, G - 0.02), g.ramp(g.noise(26.0, detail=5.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", soilm, 0.9), col, g.mix(g.ramp(g.noise(110.0), 0.3, 0.7), (0.032, 0.023, 0.015), (0.07, 0.05, 0.033)))
    height = g.math("ADD", g.math("SUBTRACT", 1.0, g.ramp(gc, 0.0, 0.5)), g.math("MULTIPLY", g.noise(80.0, detail=4.0), 0.4))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MAXIMUM", wide, fine), 1.1))
    height = g.math("ADD", height, g.math("MULTIPLY", mold, 0.3))
    rough = g.mixf(dry, 0.72, 0.9)
    rough = g.mixf(scuff, rough, 0.6)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.95), 0.0, rough, g.bump(height, 1.0, 0.0022))


def sole_mat(name, O, eul):
    mat, g = tk.new_material(name)
    L = sk.local_coords(g, O, eul)
    lcx, lcy, lcz = g.separate(L)
    lx = g.math("ADD", lcx, C0.x)
    ly = lcy
    lz = g.math("ADD", lcz, C0.z)
    co = g.coords()
    z = g.separate(co)[2]
    tone = g.noise(5.0, detail=5.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.022, 0.02, 0.018), (0.05, 0.043, 0.036))
    # lug pattern on the bottom (facing -z in the boot's frame), worn away at heel and ball
    fx = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", lx, 62.0)), 0.5))
    fy = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", ly, 62.0)), 0.5))
    lug = g.math("MULTIPLY", g.ramp(fx, 0.5, 0.36), g.ramp(fy, 0.5, 0.36))
    worn = g.ramp(g.noise(7.0, detail=4.0), 0.4, 0.62)
    lug = g.math("MULTIPLY", lug, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", worn, 0.7)))
    layers = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", lz, 240.0)), 0.5)), 0.5, 0.42), 0.5)
    col = g.mix(g.math("MULTIPLY", layers, 0.5), col, (0.1, 0.075, 0.05))
    ce = kf._voronoi(g, 45.0, kf._warped(g, 12.0, 0.006), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.05, 0.0), g.ramp(g.noise(5.0, detail=3.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, (0.006, 0.005, 0.004))
    grime = g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=5.0), 0.35, 0.62), 0.6)
    col = g.mix(grime, col, (0.075, 0.055, 0.035))
    soilm = g.math("MULTIPLY", g.ramp(z, G + 0.08, G - 0.02), g.ramp(g.noise(26.0, detail=5.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", soilm, 0.9), col, (0.045, 0.033, 0.021))
    height = g.math("ADD", g.math("MULTIPLY", lug, 0.8), g.math("MULTIPLY", g.noise(120.0, detail=3.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.8))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.95), 0.0, 0.88, g.bump(height, 1.0, 0.0035))


def lining_mat(name):
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(9.0, detail=4.0), 0.3, 0.7), (0.025, 0.02, 0.016), (0.07, 0.058, 0.045))
    fib = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (140.0, 140.0, 140.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.75), 0.35), col, (0.15, 0.13, 0.1))
    mold = g.math("MULTIPLY", g.ramp(g.noise(28.0, detail=5.0), 0.55, 0.7), 0.7)
    col = g.mix(mold, col, (0.13, 0.15, 0.1))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.9), 0.0, 0.95, g.bump(fib, 1.0, 0.002))


def cord_mat(name):
    mat, g = tk.new_material(name)
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (500.0, 500.0, 90.0)))
    col = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.11, 0.095, 0.07), (0.22, 0.2, 0.15))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.4, 0.8), 0.5), col, (0.04, 0.032, 0.022))
    soilm = g.ramp(g.noise(12.0, detail=4.0), 0.45, 0.65)
    col = g.mix(g.math("MULTIPLY", soilm, 0.6), col, (0.05, 0.04, 0.028))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), 0.0, 0.95, g.bump(fib, 1.0, 0.0015))


for n in (ONLY or ["LoneBoot"]):
    build(n)
