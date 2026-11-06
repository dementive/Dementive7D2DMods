"""TrailMarker (forest and anywhere hikers once went): a weathered 4x4 post, 1.8 m, leaning a little, its arrow board hanging
from one nail (the other pulled out), a faded painted arrow and two lines of scratched pseudo-writing nobody could read,
lichen on the north side, rot at the ground line, a bindweed vine winding up it, soil heaped round the foot. Solid: a
capsule down the post and a thin box for the board (a pick hits it as wood).

    blender -b --factory-startup --python trail_marker.py -- <features folder> <preview folder> [Name ...]
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

POST_H = 1.82          # above the ground
POST_BELOW = 0.32      # sunk
POST_HALF = (0.047, 0.05)
LEAN_X, LEAN_Y = 3.2, -1.8            # degrees: forward (toward -y) and sideways
RPOST = Matrix.Rotation(math.radians(LEAN_Y), 3, "Y") @ Matrix.Rotation(math.radians(LEAN_X), 3, "X")
PIVOT = Vector((0.0, 0.0, G))
BOARD_HALF = (0.35, 0.0125, 0.11)
NAIL = Vector((0.0, -POST_HALF[1] - 0.0125, 1.545))            # post frame (z above ground)
DROOP, PULL = 9.0, -5.0                                          # degrees: board swings about the top nail
RBOARD = Matrix.Rotation(math.radians(DROOP), 3, "Y") @ Matrix.Rotation(math.radians(PULL), 3, "X")
BOARD_NAIL_LOCAL = Vector((-0.10, 0.0, 0.07))                   # the top nail in the board's frame


def post_frame(p):
    """A point given in the post's upright frame (x, y, height above the ground) as a world point."""
    return PIVOT + RPOST @ Vector((p.x, p.y, p.z))


def board_center_post():
    return NAIL - RBOARD @ BOARD_NAIL_LOCAL


# ---------------------------------------------------------------- materials

def arrow_mask(g, lx, lz, cz=0.05, x0=-0.275, xs=0.01, xt=0.235, hs=0.0185, hh=0.056, soft=0.0016):
    inx = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", lx, x0), 0.0, soft), g.ramp(g.math("SUBTRACT", xs, lx), 0.0, soft))
    dz = g.math("ABSOLUTE", g.math("SUBTRACT", lz, cz))
    shaft = g.math("MULTIPLY", inx, g.ramp(g.math("SUBTRACT", hs, dz), 0.0, soft))
    dx = g.math("SUBTRACT", lx, xs)
    half = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("DIVIDE", dx, xt - xs)), hh)
    head = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(dx, 0.0, soft), g.ramp(g.math("SUBTRACT", xt, lx), 0.0, soft)),
                  g.ramp(g.math("SUBTRACT", half, dz), 0.0, soft))
    return g.math("MAXIMUM", shaft, head)


def board_mat(name):
    mat, g = tk.new_material(name)
    cb = board_center_post()
    centre = post_frame(cb)
    # The board's own frame: the post's lean and the droop, as an XYZ Euler
    rot = RPOST @ RBOARD
    e = rot.to_euler("XYZ")
    L = sk.local_coords(g, centre, tuple(math.degrees(a) for a in e))
    lx, ly, lz = g.separate(L)
    col, height, rough = sk.wood_surface(g, axis="x", lo=(0.12, 0.112, 0.1), hi=(0.28, 0.268, 0.24), checks=0.9, mildew=0.7,
                                         lichen=0.18, algae=0.0, brown=0.35)
    # Wobble: the painter's hand
    wob = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(38.0, detail=2.0, vector=L), 0.5), 0.0065)
    wx = g.math("ADD", lx, wob)
    wz = g.math("ADD", lz, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(41.0, detail=2.0, vector=L), 0.5), 0.0055))
    # Remaining paint: coverage follows the grain (flakes long along the board), cracks through it
    flk = g.noise(1.0, detail=6.0, roughness=0.6, vector=ks._stretched(g, (6.0, 22.0, 22.0)))
    flk = g.math("ADD", flk, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(60.0, detail=3.0), 0.5), 0.22))
    ccrack = g.ramp(kf._voronoi(g, 1.0, kf._warped(g, 25.0, 0.002, ks._stretched(g, (4.0, 70.0, 70.0))), feature="DISTANCE_TO_EDGE"), 0.012, 0.0)
    bg_rem = g.ramp(flk, 0.58, 0.66)
    bg_rem = g.math("MULTIPLY", bg_rem, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", ccrack, 0.7)))
    edge_near = g.ramp(g.math("SUBTRACT", 0.105, g.math("ABSOLUTE", lz)), 0.0, 0.012)
    bg_rem = g.math("MULTIPLY", bg_rem, g.math("ADD", 0.25, g.math("MULTIPLY", edge_near, 0.75)))
    paint_col = g.mix(g.ramp(g.noise(6.0, detail=4.0), 0.3, 0.7), (0.30, 0.285, 0.215), (0.38, 0.36, 0.28))
    chalk = g.math("MULTIPLY", g.ramp(g.noise(120.0, detail=2.0), 0.5, 0.85), 0.18)
    paint_col = g.mix(chalk, paint_col, (0.5, 0.48, 0.4))
    grime = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0), 0.45, 0.7), 0.5)
    paint_col = g.mix(grime, paint_col, (0.13, 0.12, 0.09))
    col = g.mix(bg_rem, col, paint_col)
    height = g.mixf(bg_rem, height, g.math("ADD", 0.58, g.math("MULTIPLY", flk, 0.12)))
    rough = g.mixf(bg_rem, rough, 0.62)
    # The arrow, in a faded red, wearing off in patches and along cracks
    arr = arrow_mask(g, wx, wz)
    arem = g.ramp(g.math("ADD", flk, 0.12), 0.5, 0.58)
    arem = g.math("MULTIPLY", arem, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", ccrack, 0.85)))
    arr = g.math("MULTIPLY", arr, arem)
    acol = g.mix(g.ramp(g.noise(10.0, detail=4.0), 0.3, 0.7), (0.10, 0.027, 0.016), (0.17, 0.05, 0.028))
    acol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(140.0, detail=2.0), 0.55, 0.85), 0.25), acol, (0.4, 0.2, 0.15))
    col = g.mix(g.math("MULTIPLY", arr, 0.88), col, acol)
    height = g.mixf(arr, height, g.math("ADD", 0.62, g.math("MULTIPLY", flk, 0.1)))
    rough = g.mixf(arr, rough, 0.55)
    # Two lines of scratched scribble, ink remnants and gouges
    r1 = g.math("MULTIPLY", g.ramp(g.math("ADD", lx, 0.30), 0.0, 0.004), g.ramp(g.math("SUBTRACT", 0.07, lx), 0.0, 0.004))
    s1 = sk.scribble(g, g.math("ADD", wx, 0.30), g.math("ADD", wz, 0.047), cell=0.0125, height=0.030, seed=3.0, stroke=0.0034, density=0.85)
    r2 = g.math("MULTIPLY", g.ramp(g.math("ADD", lx, 0.26), 0.0, 0.004), g.ramp(g.math("SUBTRACT", -0.04, lx), 0.0, 0.004))
    s2 = sk.scribble(g, g.math("ADD", wx, 0.26), g.math("ADD", wz, 0.097), cell=0.0125, height=0.028, seed=7.0, stroke=0.0034, density=0.8)
    scr = g.math("MAXIMUM", g.math("MULTIPLY", s1, r1), g.math("MULTIPLY", s2, r2))
    ink = g.math("MULTIPLY", scr, g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.55))
    col = g.mix(g.math("MULTIPLY", scr, 0.5), col, (0.02, 0.018, 0.016))
    col = g.mix(g.math("MULTIPLY", ink, 0.4), col, (0.01, 0.01, 0.01))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", scr, 0.6))
    # Nails: the top one holds, rust bleeding down from it; the bottom one is gone, its hole and stain left
    for nx, nz, tag in ((-0.10, 0.07, 1.0), (-0.10, -0.075, 0.6)):
        dxn = g.math("SUBTRACT", lx, nx + 0.0)
        dzn = g.math("SUBTRACT", lz, nz)
        head = g.ramp(g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dxn, dxn), g.math("MULTIPLY", dzn, dzn))), 0.0062, 0.004)
        streak_w = g.ramp(g.math("SUBTRACT", 0.011, g.math("ABSOLUTE", g.math("ADD", dxn, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(30.0, detail=3.0), 0.5), 0.012)))), 0.0, 0.008)
        below = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", nz, lz), -0.005, 0.01), g.ramp(g.math("SUBTRACT", lz, nz - 0.14), 0.0, 0.1))
        streak = g.math("MULTIPLY", g.math("MULTIPLY", streak_w, below), 0.75 * tag)
        col = g.mix(streak, col, (0.14, 0.058, 0.025))
        if tag < 1.0:
            col = g.mix(head, col, (0.012, 0.01, 0.008))
            height = g.math("SUBTRACT", height, g.math("MULTIPLY", head, 0.5))
    # Splash soil and dust on the upper edge
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0035))


def build(name):
    sk_ = sk
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 7 + 3)
    post_mat = sk.wood_mat("PostWood", axis="z", lichen=1.0, lichen_side=(0.7, 0.7), algae=1.0, rot=1.3, mildew=0.8, brown=0.4,
                           lo=(0.11, 0.1, 0.086), hi=(0.265, 0.25, 0.22))
    top_mat = lk.end_grain("PostTop", "bleached", 0.004)
    skirt = sk.soil_small("PostSkirt", moss=0.0)
    board = board_mat("BoardWood")
    nail = sk.rust_mat("NailRust", rust=1.0, scale=3.0, streak=0.0, grime=0.2)
    soil = sk.soil_small("TmSoil", moss=0.3, stony=1.0)
    bed = sk.litter_bed("TmBed")
    gm = nk.plant("TmGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("TmGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    leafm = nk.plant("TmVineLeaf", (0.07, 0.15, 0.04), (0.11, 0.19, 0.055), rough=0.6, vary=0.3)
    vine = ks.bark("TmVine", (0.08, 0.13, 0.04), (0.14, 0.15, 0.06), rough=0.7)
    weed = nk.plant("TmPlantain", (0.06, 0.13, 0.035), (0.1, 0.18, 0.05), rough=0.65, vary=0.35, sat=0.8, value=0.62)
    twig = ks.bark("TmTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    lits = sk.litter_mats("TmLf")
    b = ks.Builder(name)

    # The post
    zc = (POST_H - POST_BELOW) / 2.0
    half = (POST_HALF[0], POST_HALF[1], (POST_H + POST_BELOW) / 2.0)
    ph = rnd.uniform(0, 6.28)

    def deform(q, n):
        h = q.z + zc                                           # height above the ground
        out = q.copy()
        waist = 0.2 * math.exp(-((h - 0.05) / 0.1) ** 2) * (0.7 + 0.5 * sk.fbm((q.x * 20, q.y * 20, h * 6), 1.0))
        sh = 1.0 - waist - 0.1 * math.exp(-((h - 0.3) / 0.35) ** 2) * max(0.0, sk.fbm((q.x * 9, q.y * 9, h * 2), 2.0) + 0.2)
        out.x *= sh
        out.y *= sh
        bow = 0.012 * math.sin(math.pi * clamp01(h / POST_H)) + 0.006 * math.sin(h * 4.0 + ph)
        out.x += bow
        d = (sk.fbm((q.x * 16, q.y * 16, h * 5), 3.0) * 0.0028 + sk.fbm((q.x * 4, q.y * 4, h * 3), 4.0) * 0.0035)
        d += 0.0016 * max(0.0, sk.fbm((q.x * 40, q.y * 40, h * 14), 5.0))
        out += n * d
        if h > POST_H - 0.14:
            k = (h - (POST_H - 0.14)) / 0.14
            out.z -= 0.075 * k * k * (0.6 + 0.4 * (q.x / POST_HALF[0] + 0.3 * sk.fbm((q.x * 15, q.y * 15, 0.0), 6.0))) * 0.5
            out.z += 0.012 * sk.fbm((q.x * 25, q.y * 25, 0.0), 7.0)
        return out

    center = PIVOT + RPOST @ Vector((0.0, 0.0, zc))
    post = sk.block(center, half, RPOST, r=0.0125, step=0.065, nr=3, deform=deform)

    def p_mat(info, vi_polys=post):
        return post_mat
    mats = []
    for pi, poly in enumerate(post.polys):
        zs = [post.verts[i].z for i in poly]
        axis, sign = post.info[pi]
        if max(zs) < G - 0.015:
            mats.append(skirt)
        elif axis == 2 and sign > 0:
            mats.append(top_mat)
        else:
            mats.append(post_mat)
    Rinv = RPOST.inverted()

    def tfun(vi, p):
        l = Rinv @ (p - center)
        return math.hypot(l.x, l.y)
    sk.emit(b, post, None, mats=mats, tfun=tfun, lod=2)

    # The board
    bc = board_center_post()
    bcw = post_frame(bc)
    rot_b = RPOST @ RBOARD

    def bdeform(q, n):
        out = q.copy()
        if q.x > 0.15:
            k = (q.x - 0.15) / 0.2
            out.z = q.z * max(0.0, 1.0 - k) + (1.0 - k) * 0.0
            if k > 0.9:
                out.z *= 0.6
        out.y += 0.004 * math.sin(q.x * 9 + 1.0) + 0.0035 * q.x
        d = sk.fbm((q.x * 22, q.z * 22, q.y * 40), 11.0) * 0.0024
        out += n * d
        # chipped lower-left corner and split end
        if q.x < -0.3 and q.z < -0.07:
            out.z += 0.018 * sk.fbm((q.x * 30, q.z * 30, 0.0), 12.0) + 0.012
        out.z += 0.003 * sk.fbm((q.x * 18, 0.0, q.z * 18), 13.0)
        return out

    bshape = sk.block(bcw, BOARD_HALF, rot_b, r=0.0045, steps=(0.028, 0.02, 0.028), nr=2, deform=bdeform)
    sk.emit(b, bshape, board)

    # Nails
    for nx, nz, present in ((-0.10, 0.07, True),):
        base = bcw + rot_b @ Vector((nx, -BOARD_HALF[1], nz - 0.0))
        out = rot_b @ Vector((0.0, -1.0, 0.0))
        ks.tube(b, nail, [base - out * 0.0, base + out * 0.0035, base + out * 0.0055], [0.0058, 0.0058, 0.0035], sides=7, cap=True)
        # a bent nail end sticking out of the pulled hole
    pull_base = bcw + rot_b @ Vector((-0.10, -BOARD_HALF[1], -0.075))

    # Bindweed: a vine winding up the post with heart-shaped leaves
    t = rnd.uniform(0, 6.28)
    pts, leafs = [], []
    turns = 3.2
    for i in range(46):
        f = i / 45
        h = 0.02 + f * 0.95
        a = t + f * turns * math.tau
        rr = 0.058 + 0.01 * math.sin(f * 17) + 0.01 * (1.0 - f)
        pts.append(post_frame(Vector((math.cos(a) * rr, math.sin(a) * rr, h))))
        if i % 2 == 1:
            leafs.append((pts[-1], a, h))
    ks.tube(b, vine, pts, [0.0036 * (1.0 - 0.5 * i / 45) for i in range(46)], sides=4, cap=True)
    for p, a, h in leafs:
        out = Vector((math.cos(a), math.sin(a), 0.0))
        out = RPOST @ out
        d = (out * 0.8 + Vector((0, 0, 0.4 + rnd.uniform(-0.3, 0.3)))).normalized()
        ks.leaf(b, leafm, p, d, rnd.uniform(0.05, 0.08), rnd.uniform(0.045, 0.07), bend=rnd.uniform(0.2, 0.7), fold=0.3, profile="heart", rows=3, normal=out)

    # Ground: soil heaped round the foot, litter, grass, plantain, sticks
    box = (-0.5, 0.5, -0.5, 0.5)
    hfun = sk.mound(b, bed, (0.02, 0.01), 0.44, rnd, dome=0.07, sides=24, rings=4, sink=0.06, jitter=0.35)
    keep = lambda x, y: math.hypot(x, y) > 0.06
    sk.litter(b, lits, 52, rnd, (-0.41, 0.41, -0.41, 0.41), keep=lambda x, y: math.hypot(x, y) > 0.07, size=(0.05, 0.09), rows=4,
              ground=hfun)
    sk.twigs(b, twig, 4, rnd, (-0.4, 0.4, -0.4, 0.4), keep=lambda x, y: math.hypot(x, y) > 0.08, z=G + 0.01)
    for (gx, gy, n) in ((0.12, -0.08, 15), (-0.1, 0.1, 16), (0.2, 0.2, 9), (-0.24, -0.16, 8), (0.02, 0.2, 7)):
        sk.grass(b, gm, gx, gy, rnd, blades=n, height=(0.22, 0.6), spread=0.06, lean=0.55, z=hfun(gx, gy), dry=gd, dry_share=0.35, bound=(-0.5, 0.5, -0.5, 0.5))
    sk.rosette(b, weed, -0.2, 0.2, rnd, leaves=8, length=(0.07, 0.12), width=0.04, z=hfun(-0.2, 0.2), bound=(-0.5, 0.5, -0.5, 0.5))
    sk.rosette(b, weed, 0.25, -0.12, rnd, leaves=7, length=(0.06, 0.11), width=0.038, z=hfun(0.25, -0.12), bound=(-0.5, 0.5, -0.5, 0.5))

    # Colliders: a capsule down the post, a thin box for the board
    a0 = post_frame(Vector((0.0, 0.0, -0.2)))
    a1 = post_frame(Vector((0.0, 0.0, POST_H - 0.14)))
    extra = ["capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (a0.x, a0.y, a0.z, a1.x, a1.y, a1.z, 0.04)]
    ux, uy, uz = rot_b @ Vector((1, 0, 0)), rot_b @ Vector((0, 1, 0)), rot_b @ Vector((0, 0, 1))
    extra.append("box %.3f %.3f %.3f %.3f %.3f %.3f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (
        bcw.x, bcw.y, bcw.z, 0.62, 0.02, 0.14, ux.x, ux.y, ux.z, uy.x, uy.y, uy.z, uz.x, uz.y, uz.z))
    density = {"PostWood": 1.25, "PostTop": 0.25, "PostSkirt": 0.08, "BoardWood": 1.7, "NailRust": 0.12, "TmSoil": 0.5, "TmBed": 0.6, "TmGrass": 0.35,
               "TmGrassDry": 0.3, "TmVineLeaf": 0.4, "TmVine": 0.3, "TmPlantain": 0.35, "TmTwig": 0.15, "TmLf": 0.3}
    model = sk.finish_export(name, b, [], FEATURES, 1024, density, extra=extra, coarse=0.5)
    ex, ey, top = sk.bounds_report(name, model)
    shots = sk.standard_shots(top, reach=0.4)
    shots.append(("board", bcw + Vector((0.25, -0.75, 0.12)), bcw + Vector((0.0, 0.0, -0.02)), 40))
    shots.append(("foot", Vector((0.5, -0.7, G + 0.3)), Vector((0.0, 0.0, G + 0.15)), 40))
    sk.preview(name, model, shots, PREVIEWS)
    print("[%s] done" % name)


def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


for n in (ONLY or ["TrailMarker"]):
    build(n)
