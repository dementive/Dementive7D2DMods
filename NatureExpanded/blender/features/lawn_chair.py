"""LawnChair (camps, gardens, anywhere): one aluminium folding lawn chair on its side, the tube frame chalky with oxide and bled
with rust from its steel rivets, the striped webbing mildewed, snapped strip by strip, hanging in tatters, bindweed and grass
grown through it. Solid frame (capsules down the tubes), low.

    blender -b --factory-startup --python lawn_chair.py -- <features folder> <preview folder> [Name ...]
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

ROLL, PITCH, YAW = 75.0, -6.0, 4.0
R = Matrix.Rotation(math.radians(YAW), 3, "Z") @ Matrix.Rotation(math.radians(PITCH), 3, "Y") @ Matrix.Rotation(math.radians(ROLL), 3, "X")
HY = 0.275                  # half the width between the side frames
TR = 0.0115                 # tube radius


def webbing_mat(name):
    """Striped vinyl webbing gone to mildew: two stripe colours picked by t (0 or 1), woven grain, brown tide marks, black
    mold blooms, grime in the weave, split edges."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    co = g.coords()
    z = g.separate(co)[2]
    weave1 = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (380.0, 90.0, 380.0)))
    weave2 = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (90.0, 380.0, 380.0)))
    cells, cr = kf._cells(g, 420.0)
    tone = g.noise(5.0, detail=5.0)
    pale = g.mix(g.ramp(tone, 0.3, 0.7), (0.17, 0.2, 0.14), (0.27, 0.3, 0.22))
    deep = g.mix(g.ramp(tone, 0.3, 0.7), (0.035, 0.09, 0.06), (0.07, 0.15, 0.095))
    col = g.mix(g.ramp(t, 0.3, 0.7), pale, deep)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.math("ADD", weave1, weave2), 0.9, 1.15), 0.3), col, (0.02, 0.02, 0.016))
    col = g.mix(g.math("MULTIPLY", g.ramp(cells, 0.5, 0.15), 0.25), col, (0.01, 0.012, 0.009))
    tide = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=ks._stretched(g, (3.0, 3.0, 12.0))), 0.55, 0.72), 0.75)
    col = g.mix(tide, col, (0.13, 0.095, 0.055))
    mold = g.math("MULTIPLY", g.ramp(g.noise(24.0, detail=5.0, distortion=0.3), 0.54, 0.7), g.ramp(g.noise(4.0, detail=3.0), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", mold, 0.85), col, g.mix(g.ramp(g.noise(140.0), 0.3, 0.7), (0.012, 0.014, 0.01), (0.045, 0.06, 0.035)))
    dirt = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0), 0.4, 0.7), 0.6)
    col = g.mix(dirt, col, (0.045, 0.034, 0.022))
    soilm = g.math("MULTIPLY", g.ramp(z, G + 0.14, G - 0.01), g.ramp(g.noise(26.0, detail=5.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", soilm, 0.85), col, (0.045, 0.033, 0.021))
    height = g.math("ADD", g.math("MULTIPLY", g.math("ADD", weave1, weave2), 0.4), g.math("MULTIPLY", g.ramp(cells, 0.5, 0.1), 0.3))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.92), 0.0, 0.93, g.bump(height, 1.0, 0.0012))


def frame_points():
    """Control polylines (upright frame, one side at y = +HY; mirrored for the other)."""
    t1 = [(-0.30, 0.0), (-0.255, 0.14), (-0.208, 0.262), (-0.2, 0.282), (-0.215, 0.33), (-0.30, 0.55), (-0.43, 0.83)]
    t2 = [(0.325, 0.0), (0.285, 0.3), (0.262, 0.545), (0.25, 0.592), (0.2, 0.606), (-0.05, 0.608), (-0.312, 0.602)]
    t3 = [(-0.2, 0.282), (0.04, 0.296), (0.283, 0.31)]
    return t1, t2, t3


def build(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 23 + 11)
    # placement: lowest point sinks 4 cm; centre the bounding box
    samples = [Vector(p) for p in ((-0.43, 0.275, 0.83), (-0.43, -0.275, 0.83), (0.325, 0.275, 0.0), (0.325, -0.275, 0.0), (-0.3, 0.275, 0.0), (-0.3, -0.275, 0.0),
                                   (0.26, 0.275, 0.59), (0.26, -0.275, 0.59), (0.0, 0.0, 0.3))]
    rs = [R @ p for p in samples]
    zmin = min(p.z for p in rs)
    cx = (min(p.x for p in rs) + max(p.x for p in rs)) / 2
    cy = (min(p.y for p in rs) + max(p.y for p in rs)) / 2
    O = Vector((-cx, -cy, G - 0.04 - zmin))
    T = lambda p: O + R @ Vector(p)

    alu = sk.alum_mat("ChairAlu", seed=2.0, bleach=1.3, rust_stain=1.4)
    pins = sk.rust_mat("ChairPin", paint=None, rust=1.0, scale=5.0, streak=0.0, grime=0.3)
    web = webbing_mat("ChairWeb")
    soil = sk.soil_small("ChairSoil", moss=0.3, stony=1.0)
    mossm = sk.moss_clump_mat("ChairMoss")
    bed = sk.litter_bed("ChairBed")
    lits = sk.litter_mats("ChLf")
    gm = nk.plant("ChGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("ChGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    weed = nk.plant("ChDock", (0.06, 0.13, 0.035), (0.1, 0.18, 0.05), rough=0.65, vary=0.35, sat=0.8, value=0.62)
    vinem = ks.bark("ChVine", (0.08, 0.13, 0.04), (0.14, 0.15, 0.06), rough=0.7)
    leafm = nk.plant("ChVineLeaf", (0.07, 0.15, 0.04), (0.11, 0.19, 0.055), rough=0.6, vary=0.3)
    twig = ks.bark("ChTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    b = ks.Builder(name)
    extra = []

    def tube(pts3, r=TR, n=None, end_cap=True, sides=8, kink=None):
        pts = sk.smooth_path(pts3, n or max(6, 5 * (len(pts3) - 1)))
        if kink is not None:
            pts = [kink(p, i / (len(pts) - 1)) for i, p in enumerate(pts)]
        world = [T(p) for p in pts]
        sk.sweep(b, alu, world, [r * (1.0 + 0.03 * math.sin(i * 1.3)) for i in range(len(world))], sides=sides, cap_start=end_cap, cap_end=end_cap)
        return pts

    t1, t2, t3 = frame_points()
    for side in (1, -1):
        y = side * HY
        up_side = side > 0           # the +y frame ends up uppermost: bent about a little more

        def kink_t1(p, f, up_side=up_side):
            if up_side and 0.58 < f < 0.9:
                return p + Vector((0.0, 0.02 * math.sin((f - 0.58) / 0.32 * math.pi), -0.03 * math.sin((f - 0.58) / 0.32 * math.pi)))
            return p

        def kink_t2(p, f, up_side=up_side):
            if up_side and f > 0.62:
                return p + Vector((0.0, 0.0, -0.045 * math.sin((f - 0.62) / 0.38 * math.pi * 0.9)))
            return p
        pa = tube([Vector((a, y, c)) for a, c in t1], kink=lambda p, f: kink_t1(p, f))
        pb = tube([Vector((a, y, c)) for a, c in t2], kink=lambda p, f: kink_t2(p, f))
        pc = tube([Vector((a, y, c)) for a, c in t3], r=TR * 0.95)
        # colliders: down each straight stretch
        for seg in ((t1[0], t1[3]), (t1[3], t1[-1]), (t2[0], t2[3]), (t2[3], t2[-1]), (t3[0], t3[-1])):
            extra.append(sk.ocapsule(T, Vector((seg[0][0], y, seg[0][1])), Vector((seg[1][0], y, seg[1][1])), 0.0105))
        # rivets and pins at the joints, rust bleeding from them
        for (px, pz) in ((-0.2, 0.282), (0.283, 0.31), (-0.31, 0.6), (0.262, 0.545), (-0.255, 0.14), (0.285, 0.3)):
            for sgn in (1, -1):
                q0 = T(Vector((px, y + sgn * (TR - 0.002), pz)))
                q1 = T(Vector((px, y + sgn * (TR + 0.006), pz)))
                sk.sweep(b, pins, [q0, q1], [0.0058, 0.0058], sides=6, cap_start=False, cap_end=True)
    # cross tubes
    for (px, pz, r_) in ((0.283, 0.31, TR * 0.95), (-0.2, 0.282, TR * 0.95), (-0.43, 0.83, TR * 0.95), (-0.285, 0.1, TR * 0.8)):
        a = Vector((px, -HY, pz))
        c = Vector((px, HY, pz))
        pts = [T(a + (c - a) * f + Vector((0, 0, -0.006 * math.sin(f * math.pi) * (1 if pz > 0.2 else 0)))) for f in (0, 0.25, 0.5, 0.75, 1.0)]
        sk.sweep(b, alu, pts, [r_] * 5, sides=8, cap_start=True, cap_end=True)
        extra.append(sk.ocapsule(T, a, c, 0.0105))

    # Webbing: seat strips, back strips; some snapped, some gone
    pitch = 0.058
    seat_dir = Vector((1.0, 0.0, 0.0))
    back_a, back_b = Vector((-0.21, 0.0, 0.31)), Vector((-0.425, 0.0, 0.81))
    back_dir = (back_b - back_a).normalized()
    snapped = {("seat", 3): 0.42, ("seat", 5): 0.64, ("back", 2): 0.5, ("back", 6): 0.3}
    missing = {("back", 4), ("back", 5), ("seat", 0)}

    def strip(kind, i, base, direction, sagv, stripe):
        if (kind, i) in missing:
            return
        cut = snapped.get((kind, i))
        n = 9
        ends = []
        pts = []
        for k in range(n):
            f = k / (n - 1)
            y = -HY - 0.004 + f * (2 * HY + 0.008)
            sag = sagv * math.sin(f * math.pi) + 0.004 * math.sin(f * 17 + i)
            pts.append(Vector((base.x, y, base.z)) + sagv_vec * sag)
        if cut is None:
            sk.sweep(b, web, [T(p) for p in pts], [0.0245] * n, sides=6, aspect=[0.035] * n, up=R @ direction, cap_start=True, cap_end=True, t0=stripe, t1=stripe)
        else:
            # two halves hanging from their rails, torn ends ragged and frayed
            k_cut = max(2, int(cut * (n - 1)))
            hang = Vector((0.0, -0.10, -0.12))     # toward the ground the chair lies on (the -y side), drooping
            first = pts[:k_cut + 1]
            second = pts[k_cut:]
            a_tail = [first[-1] + (hang * (q / 3.0)) * 0.9 + Vector((rnd.uniform(-0.01, 0.01), 0.0, -0.05 * (q / 3.0) ** 2)) for q in range(1, 4)]
            b_tail = [second[0] + (hang * (q / 3.0)) * 0.0 + Vector((rnd.uniform(-0.01, 0.01), 0.05 * (q / 3.0) * -1.0, -0.14 * (q / 3.0) ** 1.5)) for q in range(1, 4)]
            for chain, flip in ((first + a_tail, False), (list(reversed(b_tail)) + second, True)):
                ww = [T(p) for p in chain]
                nn = len(ww)
                sk.sweep(b, web, ww, [0.0245] * nn, sides=6, aspect=[0.035] * nn, up=R @ direction, cap_start=True, cap_end=True, t0=stripe, t1=stripe,
                         shift1=(lambda a, s_=rnd.uniform(0.0, 3.0): 0.012 * (0.5 + 0.5 * math.sin(a * 3 + s_))) if not flip else None,
                         shift0=(lambda a, s_=rnd.uniform(0.0, 3.0): 0.012 * (0.5 + 0.5 * math.sin(a * 3 + s_))) if flip else None)
            # a few loose threads at each tear
            for tip, d in ((T(a_tail[-1]), R @ Vector((0.0, -0.4, -1.0))), (T(b_tail[-1]), R @ Vector((0.0, -0.3, -1.0)))):
                for q in range(4):
                    dd = (d.normalized() + Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.2, 0.2)))).normalized()
                    ln = rnd.uniform(0.02, 0.05)
                    sk.sweep(b, web, [tip, tip + dd * ln * 0.5, tip + dd * ln + Vector((0, 0, -0.01))], [0.0014, 0.0011, 0.0004], sides=3,
                             cap_start=False, cap_end=True, t0=stripe, t1=stripe)

    sagv_vec = Vector((0.0, 0.0, -0.018))
    for i in range(8):
        stripe = float(i % 2)
        sagv_vec = Vector((0.0, 0.0, -0.022))
        base = Vector((-0.172 + i * pitch, 0.0, 0.287 + 0.0032 * (i * pitch) / 0.058))
        strip("seat", i, base, seat_dir, 1.0, stripe)
    for i in range(9):
        stripe = float(i % 2)
        base = back_a + back_dir * (0.045 + i * 0.0615)
        sagv_vec = Vector((-0.02, 0.0, -0.006))
        strip("back", i, base, back_dir, 1.0, stripe)

    # What has grown through and over it: a vine up the back post, grass through the seat, a dock by the feet
    post = [T(Vector((-0.24 - 0.17 * q / 20, HY + 0.0, 0.34 + 0.48 * q / 20))) for q in range(21)]
    vpts = []
    for i in range(46):
        f = i / 45
        k = f * 20
        i0 = min(19, int(k))
        c = post[i0].lerp(post[i0 + 1], k - i0)
        a = f * 6.0 * math.tau
        _, uu, vv = ks.basis(post[i0 + 1] - post[i0])
        vpts.append(c + (uu * math.cos(a) + vv * math.sin(a)) * 0.026)
    sk.vine(b, vinem, leafm, vpts, rnd, r=0.0035, every=3, leaf=(0.04, 0.065), out=lambda p: Vector((0, 0, 1)))
    # a second vine woven through the seat
    vp2 = []
    for i in range(40):
        f = i / 39
        p = Vector((-0.17 + 0.42 * f, -HY + 0.55 * f + 0.05 * math.sin(f * 12), 0.3 + 0.02 * math.sin(f * 9)))
        vp2.append(T(p))
    sk.vine(b, vinem, leafm, vp2, rnd, r=0.003, every=4, leaf=(0.035, 0.055), out=lambda p: Vector((0, 0, 1)))

    hfun = sk.mound(b, bed, (0.0, 0.0), 0.5, rnd, dome=0.05, sides=28, rings=4, sink=0.05, jitter=0.3, lump=0.013, skew=(1.0, 0.9))
    sk.litter(b, lits, 66, rnd, (-0.41, 0.41, -0.41, 0.41), size=(0.05, 0.085), rows=4, ground=hfun)
    sk.twigs(b, twig, 4, rnd, (-0.42, 0.42, -0.42, 0.42), length=(0.1, 0.28), z=G + 0.01)
    for (gx, gy, nbl) in ((-0.34, -0.38, 12), (0.38, -0.36, 11), (0.4, 0.3, 9), (-0.4, 0.34, 10), (0.0, 0.44, 8), (0.05, -0.1, 9)):
        sk.grass(b, gm, gx, gy, rnd, blades=nbl, height=(0.2, 0.55), spread=0.05, lean=0.7, z=hfun(gx, gy), dry=gd, dry_share=0.4, bound=(-0.5, 0.5, -0.5, 0.5))
    sk.rosette(b, weed, 0.3, 0.05, rnd, leaves=9, length=(0.07, 0.12), width=0.042, z=hfun(0.3, 0.05), bound=(-0.5, 0.5, -0.5, 0.5))
    sk.cushion(b, mossm, T(Vector((0.0, -HY, 0.1))), R @ Vector((0, 1, 0.3)), 0.07, 0.02, rnd, sides=14, rings=3, lump=0.5)

    density = {"ChairAlu": 1.5, "ChairPin": 0.25, "ChairWeb": 1.1, "ChairSoil": 0.5, "ChairBed": 0.6, "ChairMoss": 0.5, "ChLf": 0.4, "ChGrass": 0.3,
               "ChGrassDry": 0.3, "ChDock": 0.3, "ChVine": 0.3, "ChVineLeaf": 0.4, "ChTwig": 0.15}
    model = sk.finish_export(name, b, [], FEATURES, 1024, density, extra=extra, coarse=0.5)
    ex, ey, top = sk.bounds_report(name, model)
    c = T(Vector((-0.05, 0.0, 0.4)))
    shots = sk.standard_shots(top, reach=0.4)
    shots.append(("chair", c + Vector((0.5, -1.0, 0.5)), c, 40))
    shots.append(("web", c + Vector((0.2, -0.55, 0.4)), c + Vector((0.0, 0.0, 0.0)), 40))
    shots.append(("frame", c + Vector((-0.7, -0.3, 0.3)), c, 40))
    sk.preview(name, model, shots, PREVIEWS)
    print("[%s] done" % name)


for n in (ONLY or ["LawnChair"]):
    build(n)
