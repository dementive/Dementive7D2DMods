"""Wheelbarrow (farms, camps, anywhere): a steel-tubbed wheelbarrow years after its last load, knocked over on its side, the tub
rusted through in places with the old red paint flaking off, one wooden handle rotted and snapped, the other splitting, the
tire flat and cracked, soil and leaves heaped in the tub with weeds growing out of it. Solid: boxes over the tub, the handles
and the wheel.

    blender -b --factory-startup --python wheelbarrow.py -- <features folder> <preview folder> [Name ...]
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

ROLL, PITCH, YAW = 84.0, -6.0, 14.0
R = Matrix.Rotation(math.radians(YAW), 3, "Z") @ Matrix.Rotation(math.radians(PITCH), 3, "Y") @ Matrix.Rotation(math.radians(ROLL), 3, "X")
W = Vector((0.52, 0.0, 0.21))          # wheel center, upright frame
RW = Matrix.Rotation(math.radians(90.0), 3, "X")
ZB, ZT = 0.27, 0.56                    # tub bottom and rim
N = 56


def sm(x, lo, hi):
    return sk.smooth(x, lo, hi)


def tub_loop(f, inset=0.0, lift=0.0, scale=1.0):
    """The tub's horizontal section at fraction f of its height: a squarish loop, wider at the back (-x), narrower in front."""
    hx = (0.205 + 0.2 * f ** 0.85) * scale - inset
    hy = (0.19 + 0.145 * f ** 0.85) * scale - inset
    xc = 0.06 - 0.02 * f
    z = ZB + (ZT - ZB) * f + lift
    pts = []
    for k in range(N):
        a = k / N * math.tau
        c, s = math.cos(a), math.sin(a)
        xr = math.copysign(abs(c) ** (2.0 / 3.2), c)
        yr = math.copysign(abs(s) ** (2.0 / 3.2), s)
        tf = (xr + 1.0) / 2.0
        x = xc + hx * xr
        y = hy * yr * (1.0 - 0.3 * tf ** 1.3)
        pts.append(Vector((x, y, z)))
    return pts


def tub_damage(p, rnd_ph):
    """Dents and a crushed rim corner."""
    n = sk.fbm((p.x * 5, p.y * 5, p.z * 5), 21.0) * 0.012 + sk.fbm((p.x * 14, p.y * 14, p.z * 14), 22.0) * 0.003
    q = Vector((p.x, p.y, p.z))
    c = Vector((-0.26, 0.3, 0.55))
    d = (q - c).length
    push = 0.05 * math.exp(-(d / 0.12) ** 2)
    ctr = Vector((0.04, 0.0, p.z))
    dirv = (ctr - Vector((p.x, p.y, p.z))).normalized() if (ctr - p).length > 1e-4 else Vector((0, 0, 0))
    out = Vector((p.x, p.y, p.z)) + dirv * (push - n)
    out.z -= 0.025 * math.exp(-(d / 0.13) ** 2)
    return out


HOLES = [(Vector((0.0, 0.07, ZB)), 0.05), (Vector((0.15, -0.06, ZB + 0.01)), 0.032), (Vector((-0.1, -0.12, ZB)), 0.055),
         (Vector((0.28, 0.17, ZB + 0.04)), 0.03), (Vector((-0.08, 0.2, ZB + 0.012)), 0.026), (Vector((-0.28, -0.1, ZB + 0.1)), 0.04)]


def is_hole(p):
    for hc, hr in HOLES:
        d = (p - hc).length
        rr = hr * (1.0 + 0.5 * sk.fbm((p.x * 30, p.y * 30, p.z * 30), 23.0))
        if d < rr:
            return True
    return False


def build_tub(rnd):
    f_list = [0.0, 0.07, 0.18, 0.32, 0.47, 0.62, 0.78, 0.9, 1.0]
    outer = [[tub_damage(p, 0.0) for p in tub_loop(f)] for f in f_list]
    lip = [(0.003, 1.02, 0.004), (0.011, 1.035, 0.0), (0.016, 1.0, 0.0), (0.011, 0.97, 0.0)]
    top = tub_loop(1.0)
    cen = sum(top, Vector()) / N
    lips = []
    for dz, sc, _ in lip:
        lips.append([tub_damage(Vector((cen.x + (p.x - cen.x) * sc, cen.y + (p.y - cen.y) * sc, p.z + dz)), 0.0) for p in top])
    inner = [[tub_damage(p, 0.0) for p in tub_loop(f, inset=0.006, lift=0.005 * (1.0 - f))] for f in reversed(f_list)]
    rings = outer + lips + inner
    shape = sk.loft(rings, cap_start=True, cap_end=True)
    no, nl = len(outer), len(lips)
    keep, tags = [], []
    for pi, poly in enumerate(shape.polys):
        c = sum((shape.verts[i] for i in poly), Vector()) / len(poly)
        ri = pi // N if pi < (len(rings) - 1) * N else None       # None: the two bottom fans
        wall = ri is None or ri < no - 1 or ri >= no + nl
        if wall and is_hole(c):
            continue
        if ri is not None and no - 1 <= ri <= no + nl and sk.fbm((c.x * 7, c.y * 7, 0.0), 24.0) > 0.42:
            continue                                               # the rim rusted away in places
        keep.append(pi)
        tags.append("outer" if (ri is not None and ri < no + nl - 1) or (ri is None and pi < N * 2) else "inner")
    return sk.Shape(shape.verts, [shape.polys[i] for i in keep], tags)


def handle_pts(side, broken=False):
    pts = [Vector(p) for p in ((0.34, 0.12, 0.225), (0.0, 0.16, 0.235), (-0.34, 0.22, 0.29), (-0.62, 0.262, 0.37), (-0.86, 0.29, 0.455))]
    pts = [Vector((p.x, p.y * side, p.z)) for p in pts]
    if broken:
        pts = pts[:4]
        pts.append(Vector((-0.71, 0.275 * side, 0.405)))
    return pts


def build(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 19 + 3)
    # placement of the tipped barrow: its lowest point sinks a little, the middle sits on the block's center
    samples = [Vector(p) for p in ((-0.86, 0.29, 0.455), (-0.86, -0.29, 0.455), (0.72, 0.0, 0.21), (0.72, 0.0, 0.0), (-0.25, 0.4, 0.56), (-0.25, -0.4, 0.56),
                                   (0.3, 0.3, 0.27), (0.3, -0.3, 0.27), (0.25, 0.0, 0.0), (-0.5, 0.26, 0.0), (-0.5, -0.26, 0.0))]
    rs = [R @ p for p in samples]
    zmin = min(p.z for p in rs)
    cx = (min(p.x for p in rs) + max(p.x for p in rs)) / 2
    cy = (min(p.y for p in rs) + max(p.y for p in rs)) / 2
    O = Vector((-cx, -cy, G - 0.07 - zmin))
    T = lambda p: O + R @ Vector(p)
    eul = tuple(math.degrees(a) for a in R.to_euler("XYZ"))
    outer = sk.rust_mat("BarrowOuter", paint=(0.2, 0.05, 0.034), paint_left=0.42, rust=0.9, moss=0.5, seed=1.0, scale=1.3)
    innerm = sk.rust_mat("BarrowInner", paint=(0.2, 0.05, 0.034), paint_left=0.14, rust=1.0, moss=0.7, grime=0.9, seed=2.0, scale=1.3)
    steel = sk.rust_mat("BarrowSteel", paint=None, rust=0.95, seed=3.0, scale=2.2)
    rimm = sk.rust_mat("BarrowRim", paint=(0.2, 0.2, 0.19), paint_left=0.15, rust=0.95, seed=4.0, scale=2.2)
    wood = sk.wood_mat("BarrowWood", axis="x", lo=(0.1, 0.082, 0.062), hi=(0.24, 0.2, 0.15), checks=1.4, lichen=0.3, algae=0.9, rot=0.9, ground=G, brown=0.5,
                       soil=(0.035, 0.026, 0.017))
    endg = lk.end_grain("BarrowEnd", "rot", 0.005)
    wc = T(W)
    wframe = R @ RW
    wtire = sk.rubber_mat("BarrowTire", wc, tuple(math.degrees(a) for a in wframe.to_euler("XYZ")), k=0.7, lettering=0.9, treadw=1.0, bald_amount=1.2, relief=0.003, nb=26.0)
    soil = sk.soil_small("BarrowSoil", moss=0.35, stony=1.0)
    mossm = sk.moss_clump_mat("BarrowMoss")
    bed = sk.litter_bed("BarrowBed")
    lits = sk.litter_mats("WbLf")
    gm = nk.plant("WbGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("WbGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    weed = nk.plant("WbDock", (0.06, 0.13, 0.035), (0.1, 0.18, 0.05), rough=0.65, vary=0.35, sat=0.8, value=0.62)
    vinem = ks.bark("WbVine", (0.08, 0.13, 0.04), (0.14, 0.15, 0.06), rough=0.7)
    leafm = nk.plant("WbVineLeaf", (0.07, 0.15, 0.04), (0.11, 0.19, 0.055), rough=0.6, vary=0.3)
    twig = ks.bark("WbTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    b = ks.Builder(name)

    # The tub
    tub = build_tub(rnd)
    tub_w = sk.Shape([T(v) for v in tub.verts], tub.polys, tub.info)
    sk.emit(b, tub_w, None, mat_of=lambda info: outer if info == "outer" else innerm, lod=0)

    # The wheel: steel rim disc, the flat cracked tire, the axle
    rim_prof = [(0.011, 0.047), (0.035, 0.052), (0.06, 0.04), (0.118, 0.041), (0.124, 0.03), (0.124, -0.03), (0.118, -0.041), (0.06, -0.04), (0.035, -0.052), (0.011, -0.047)]
    rim = sk.revolve(list(reversed(rim_prof)), 36, lambda p: T(W + RW @ p))
    sk.emit(b, rim, rimm)
    ph = rnd.uniform(0, 6.28)
    half = [(0.205, 0.0), (0.2035, 0.03), (0.196, 0.043), (0.178, 0.05), (0.15, 0.049), (0.13, 0.04), (0.122, 0.03), (0.12, 0.0)]
    prof = [(r, -h) for r, h in half] + [(r, h) for r, h in reversed(half[1:-1])]
    prof = [Vector(p) for p in prof]
    tp = []
    n = len(prof)
    for i in range(n):
        p0, p1, p2, p3 = prof[(i - 1) % n], prof[i], prof[(i + 1) % n], prof[(i + 2) % n]
        for s in range(2):
            ff = s / 2
            tp.append(0.5 * ((2 * p1) + (-p0 + p2) * ff + (2 * p0 - 5 * p1 + 4 * p2 - p3) * ff * ff + (-p0 + 3 * p1 - 3 * p2 + p3) * ff ** 3))

    def wob(th, r, h):
        sag = 1.0 - 0.03 * max(0.0, math.cos(th - 1.2)) ** 2 * (r / 0.205)
        wide = 1.0 + 0.2 * max(0.0, math.cos(th - 1.2)) ** 2
        return r * sag + 0.003 * sk.fbm((math.cos(th) * 3, math.sin(th) * 3, h * 20), 31.0), h * wide
    tire = sk.revolve([(p.x, p.y) for p in tp], 44, lambda p: T(W + RW @ p), wobble=wob)
    sk.emit(b, tire, wtire, lod=2)
    sk.sweep(b, steel, [T(W + Vector((0.0, -0.11, 0.0))), T(W + Vector((0.0, 0.11, 0.0)))], [0.0085, 0.0085], sides=7)
    for sy in (1, -1):
        sk.sweep(b, steel, [T(W + Vector((0.0, sy * 0.108, 0.0))), T(W + Vector((0.0, sy * 0.122, 0.0)))], [0.016, 0.016], sides=6)

    # Fork straps from the axle up to the frame, the tub's mounting straps, the legs and their brace
    for sy in (1, -1):
        pts = [T(W + Vector((0.0, sy * 0.066, 0.0))), T(Vector((0.46, sy * 0.1, 0.24))), T(Vector((0.34, sy * 0.123, 0.236)))]
        sk.sweep(b, steel, pts, [0.0035] * 3, sides=6, aspect=[4.6] * 3, up=R @ Vector((0, 1, 0)), cap_start=True, cap_end=True)
        leg = [T(Vector((-0.44, sy * 0.236, 0.33))), T(Vector((-0.475, sy * 0.246, 0.2))), T(Vector((-0.5, sy * 0.254, 0.02)))]
        sk.sweep(b, steel, leg, [0.0045] * 3, sides=6, aspect=[4.2] * 3, up=R @ Vector((0, 1, 0)), cap_start=True, cap_end=True)
        foot = [T(Vector((-0.47, sy * 0.254, 0.012))), T(Vector((-0.55, sy * 0.254, 0.012)))]
        sk.sweep(b, steel, foot, [0.0045, 0.0045], sides=6, aspect=[4.0] * 2, up=Vector((0, 0, 1)), cap_start=True, cap_end=True)
    sk.sweep(b, steel, [T(Vector((-0.48, -0.25, 0.15))), T(Vector((-0.48, 0.25, 0.15)))], [0.0105, 0.0105], sides=7)
    sk.sweep(b, steel, [T(Vector((0.2, -0.16, 0.235))), T(Vector((0.2, 0.16, 0.235)))], [0.01, 0.01], sides=7)

    # Wooden handles: one snapped and gnawed to a stub, one with its grip rotting
    for side, broken in ((1, False), (-1, True)):
        pts = handle_pts(side, broken)
        d = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
        stn = []
        for i in range(len(pts) - 1):
            for q in range(4):
                stn.append(pts[i].lerp(pts[i + 1], q / 4))
        stn.append(pts[-1])
        stn = [T(p) for p in stn]
        nst = len(stn)
        rad = [0.027 - 0.004 * i / nst for i in range(nst)]
        cr = 0.0 if not broken else 1.0

        def mod(i, a, s, side=side, broken=broken):
            m = 1.0 + 0.1 * sk.fbm((math.cos(a) * 2 + side, math.sin(a) * 2, i * 0.5), 41.0)
            if i > nst * 0.8:
                m -= 0.25 * max(0.0, sk.fbm((a * 2, i * 0.2, side), 42.0)) * (i - nst * 0.8) / (nst * 0.2)
            return m

        sk.sweep(b, wood, stn, rad, sides=8, aspect=[1.0 + 0.2 * 0] * nst, mod=mod, power=3.0, cap_start=True, cap_end=True, end_mat=endg,
                 shift1=(lambda a: 0.02 * (0.5 + 0.5 * math.sin(a * 3 + 1))) if broken else None, up=R @ Vector((0, 1, 0)))

    # What has grown and settled in: soil and leaves on the tub's floor (the old side wall), a vine up a handle, weeds
    fl_n = R @ Vector((0.0, 1.0, 0.0))           # into the tub from its lower side
    floor_c = T(Vector((0.06, -0.255, 0.4)))
    sk.cushion(b, soil, floor_c, fl_n, 0.26, 0.085, rnd, sides=24, rings=4, sink=0.0, lump=0.25, squash=(1.0, 0.8))
    ax, u, v = ks.basis(fl_n)
    for i in range(60):
        a = rnd.uniform(0, math.tau)
        rr = 0.24 * math.sqrt(rnd.random())
        p = floor_c + u * (math.cos(a) * rr) + v * (math.sin(a) * rr * 0.75) + fl_n * (0.085 * (1.0 - (rr / 0.26) ** 2) ** 0.7 + 0.006 + 0.02 * rnd.random())
        d = (u * rnd.uniform(-1, 1) + v * rnd.uniform(-1, 1) + fl_n * 0.1).normalized()
        ln = rnd.uniform(0.05, 0.085)
        sk.leaf_shape(b, rnd.choice(lits), p, d, ln, ln * rnd.uniform(0.5, 0.8), kind=rnd.choice(("oak", "maple", "oval", "narrow")), rows=4,
                      bend=rnd.uniform(-0.25, 0.35), fold=rnd.uniform(0.1, 0.5), roll=rnd.uniform(-25, 25), ph=rnd.uniform(0, 6.28), normal=fl_n)
    sk.cushion(b, mossm, floor_c + fl_n * 0.04 - u * 0.12, fl_n, 0.075, 0.02, rnd, sides=14, rings=3, lump=0.5)
    # weeds rooted in the tub
    for (lx_, lz_, nbl) in ((0.0, 0.34, 14), (0.18, 0.46, 10), (-0.12, 0.5, 9)):
        base = floor_c + fl_n * 0.075 + (R @ Vector((lx_ - 0.06, 0.0, lz_ - 0.4)))
        sk.grass(b, gm, base.x, base.y, rnd, blades=nbl, height=(0.2, 0.5), spread=0.05, lean=0.8, z=base.z, dry=gd, dry_share=0.4, bound=(-0.78, 0.78, -0.5, 0.5))
    base = floor_c + fl_n * 0.07
    sk.rosette(b, weed, base.x, base.y, rnd, leaves=10, length=(0.08, 0.14), width=0.05, z=base.z, tilt=(25, 62), bound=(-0.78, 0.78, -0.5, 0.5))
    # a vine round the intact handle and through the wheel spokes' place
    hp = [T(p) for p in handle_pts(1)]
    vpts = []
    for i in range(36):
        f = i / 35
        k = f * (len(hp) - 1)
        i0 = min(len(hp) - 2, int(k))
        c = hp[i0].lerp(hp[i0 + 1], k - i0)
        a = f * 5.0 * math.tau
        _, uu, vv = ks.basis((hp[i0 + 1] - hp[i0]))
        vpts.append(c + (uu * math.cos(a) + vv * math.sin(a)) * 0.034)
    sk.vine(b, vinem, leafm, vpts, rnd, r=0.0035, every=3, leaf=(0.04, 0.06), out=lambda p: Vector((0, 0, 1)))

    hfun = sk.mound(b, bed, (0.0, 0.0), 0.55, rnd, dome=0.05, sides=30, rings=4, sink=0.05, jitter=0.3, lump=0.014, skew=(1.45, 0.78), limit=(0.8, 0.505))
    sk.litter(b, lits, 70, rnd, (-0.7, 0.7, -0.41, 0.41), size=(0.05, 0.085), rows=4, ground=hfun, keep=lambda x, y: True)
    sk.twigs(b, twig, 4, rnd, (-0.7, 0.7, -0.4, 0.4), length=(0.1, 0.3), z=G + 0.01, limit=(0.8, 0.5))
    for (gx, gy, nbl) in ((-0.66, 0.34, 12), (0.62, 0.3, 11), (0.66, -0.34, 9), (-0.7, -0.3, 9), (0.0, 0.42, 10)):
        sk.grass(b, gm, gx, gy, rnd, blades=nbl, height=(0.2, 0.5), spread=0.05, lean=0.7, z=hfun(gx, gy), dry=gd, dry_share=0.4, bound=(-0.8, 0.8, -0.5, 0.5))

    # Colliders: tub, handles, wheel
    extra = [sk.obox(T, R, (0.06, 0.0, 0.42), (0.58, 0.46, 0.27))]
    for side, broken in ((1, False), (-1, True)):
        pts = handle_pts(side, broken)
        extra.append(sk.ocapsule(T, pts[1], pts[-1], 0.022))
    extra.append(sk.obox(T, R, (W.x, 0.0, W.z), (0.36, 0.09, 0.36)))
    density = {"BarrowOuter": 1.5, "BarrowInner": 1.3, "BarrowSteel": 0.8, "BarrowRim": 0.8, "BarrowWood": 1.2, "BarrowEnd": 0.3, "BarrowTire": 1.1,
               "BarrowSoil": 0.5, "BarrowBed": 0.7, "BarrowMoss": 0.5, "WbLf": 0.4, "WbGrass": 0.3, "WbGrassDry": 0.3, "WbDock": 0.3, "WbVine": 0.3, "WbVineLeaf": 0.4, "WbTwig": 0.15}
    model = sk.finish_export(name, b, [], FEATURES, 2048, density, extra=extra, coarse=0.5, rect=True)
    ex, ey, top = sk.bounds_report(name, model)
    shots = sk.standard_shots(top, reach=0.6)
    shots.append(("tub", Vector((0.5, -1.6, G + 0.5)), Vector((0.0, 0.0, G + 0.3)), 40))
    shots.append(("wheel", T(W) + Vector((0.4, -0.7, 0.3)), T(W), 40))
    shots.append(("handle", T(Vector((-0.7, 0.27, 0.4))) + Vector((-0.2, -0.6, 0.35)), T(Vector((-0.7, 0.27, 0.4))), 40))
    sk.preview(name, model, shots, PREVIEWS, floor=0.7)
    print("[%s] done" % name)


for n in (ONLY or ["Wheelbarrow"]):
    build(n)
