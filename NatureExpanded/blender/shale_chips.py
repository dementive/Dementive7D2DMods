"""ShaleChips (ground cover, stones): a slumped heap of broken shale about 0.8 m across: seven big thin plates 13 to 20
cm, twenty-odd medium ones and dozens of small chips and crumbs, angular and sharp-edged, each tipped at its own angle,
lying on and against one another and leaning on the biggest, over a skirt of grey scree. Dark grey, brown-grey, rust
stained and bleached plates; flaky terraced faces with mica glints; edges that show their fine layers.

    blender -b --factory-startup --python shale_chips.py -- <unity models folder> <preview folder>
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
from mathutils import Matrix, Vector  # noqa: E402

NAME, SCRIPT = "ShaleChips", "shale_chips"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(52)
G = nk.GROUND
A = ks_._attr


def shale_top(name):
    """A plate's face: dark grey, brown-grey, rust-stained or bleached grey by its own number; stepped flakes with sharp
    pale edges, fine bedding lines, mica glints, pits, dust and rust blooms."""
    mat, g = tk.new_material(name)
    t, L = ks_.stone_frame(g)
    fam = g.math("FRACT", g.math("MULTIPLY", t, 11.7))
    base = g.mix(g.ramp(fam, 0.0, 0.3), (0.062, 0.066, 0.072), (0.1, 0.092, 0.082))
    base = g.mix(g.ramp(fam, 0.5, 0.75), base, (0.15, 0.108, 0.07))
    base = g.mix(g.ramp(fam, 0.8, 0.95), base, (0.19, 0.185, 0.175))
    mott = g.noise(6.0, detail=5.0, vector=L)
    base = g.mix(g.math("MULTIPLY", g.ramp(mott, 0.35, 0.75), 0.45), base, tuple(c * 0.6 for c in (0.1, 0.1, 0.1)))
    # flake terraces: cells whose borders are sharp steps
    fd = kf._voronoi(g, 24.0, kf._warped(g, 9.0, 0.012, L), feature="DISTANCE_TO_EDGE")
    step = g.ramp(fd, 0.012, 0.0)
    fdd, fr = kf._cells(g, 24.0, kf._warped(g, 9.0, 0.012, L))
    base = g.mix(g.math("MULTIPLY", g.ramp(fr, 0.2, 0.95), 0.5), base, tuple(c * 1.5 for c in (0.1, 0.1, 0.1)))
    base = g.mix(g.math("MULTIPLY", step, 0.55), base, (0.26, 0.25, 0.235))
    # bedding lines
    bed = g.noise(1.0, detail=4.0, roughness=0.55, vector=ks_._stretch(g, L, (420.0, 30.0, 30.0)))
    base = g.mix(g.math("MULTIPLY", g.ramp(kf._ridged(g, bed), 0.75, 0.98), 0.4), base, tuple(c * 0.4 for c in (0.1, 0.1, 0.1)))
    # mica, grit, pits
    md, mr = kf._cells(g, 640.0, L)
    mica = g.math("MULTIPLY", g.ramp(md, 0.4, 0.15), g.ramp(mr, 0.9, 0.97))
    base = g.mix(g.math("MULTIPLY", mica, 0.9), base, (0.5, 0.49, 0.46))
    gd, gr = kf._cells(g, 300.0, L)
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.28, 0.04), 0.5), base, (0.02, 0.02, 0.022))
    pd, pr = kf._cells(g, 90.0, kf._warped(g, 30.0, 0.003, L))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.18, 0.07), g.ramp(pr, 0.5, 0.8))
    base = g.mix(g.math("MULTIPLY", pit, 0.8), base, (0.02, 0.019, 0.018))
    # rust bloom and dust
    rust = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.6, vector=L), 0.58, 0.72), 0.55)
    base = g.mix(rust, base, (0.2, 0.1, 0.05))
    dust = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0, vector=L), 0.62, 0.78), 0.4)
    base = g.mix(dust, base, (0.2, 0.18, 0.15))
    col = ks_.tint_by(g, base, t, (0.85, 0.85, 0.87), (1.2, 1.12, 1.04))
    # soil low down
    col2, height, rough = ks_.over_soil(g, col, g.math("ADD", g.math("MULTIPLY", fr, 0.25), g.math("ADD", g.math("MULTIPLY", step, 0.5), g.math("SUBTRACT", 0.4, g.math("MULTIPLY", pit, 0.4)))),
                                       g.mixf(mica, 0.78, 0.35), 0.5, z_lo=0.008, z_hi=0.03, splotch=0.35)
    col2 = tk.grade(g, col2, sat=0.95, value=1.0)
    return tk.finish(mat, g, col2, 0.0, rough, g.bump(height, 1.0, 0.004))


def shale_edge(name):
    """The broken edge of a plate: fine layers (lz is the distance across the plate's thickness), light and dark grey
    and brown, a rust film between some of them, ragged and gritty."""
    mat, g = tk.new_material(name)
    t, L = ks_.stone_frame(g)
    lz = A(g, "lz")
    wob = g.math("MULTIPLY", g.noise(30.0, detail=3.0, vector=L), 5.0)
    lam = g.math("SINE", g.math("ADD", g.math("MULTIPLY", lz, 3900.0), wob))
    lam2 = g.math("SINE", g.math("ADD", g.math("MULTIPLY", lz, 1100.0), g.math("MULTIPLY", g.noise(14.0, detail=3.0, vector=L), 4.0)))
    fam = g.math("FRACT", g.math("MULTIPLY", t, 11.7))
    base = g.mix(g.ramp(fam, 0.0, 0.3), (0.075, 0.078, 0.082), (0.12, 0.105, 0.09))
    base = g.mix(g.ramp(fam, 0.8, 0.95), base, (0.2, 0.19, 0.18))
    base = g.mix(g.math("MULTIPLY", g.ramp(lam, -0.2, 0.9), 0.5), base, tuple(c * 1.9 for c in (0.075, 0.075, 0.075)))
    base = g.mix(g.math("MULTIPLY", g.ramp(lam2, 0.4, 1.0), 0.45), base, (0.2, 0.12, 0.07))
    gd, gr = kf._cells(g, 420.0)
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.4), base, (0.3, 0.29, 0.27))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.3, 0.05), 0.5), base, (0.02, 0.02, 0.02))
    col = ks_.tint_by(g, base, t, (0.85, 0.85, 0.87), (1.2, 1.12, 1.04))
    height = g.math("ADD", g.math("MULTIPLY", lam, 0.25), g.math("ADD", 0.4, g.math("MULTIPLY", gr, 0.3)))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=1.0), 0.0, 0.9, g.bump(height, 1.0, 0.003))


def scree(name):
    """The skirt of crushed shale round the heap: grey and brown gravel, sharp little chips, dust."""
    mat, g = tk.new_material(name)
    cd, cr = kf._cells(g, 140.0, kf._warped(g, 40.0, 0.004))
    gd, gr = kf._cells(g, 420.0)
    base = g.mix(g.ramp(cr, 0.1, 0.95), (0.05, 0.05, 0.054), (0.16, 0.145, 0.125))
    base = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.5, 0.95), 0.6), base, (0.02, 0.019, 0.018))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.4), base, (0.25, 0.23, 0.2))
    base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0), 0.55, 0.75), 0.35), base, (0.14, 0.115, 0.09))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(cd, 0.85, 0.05), 0.6), g.math("MULTIPLY", gr, 0.2))
    return tk.finish(mat, g, tk.grade(g, base, sat=0.95, value=1.0), 0.0, 0.95, g.bump(height, 1.0, 0.005))


top_m, edge_m, scree_m = shale_top("ShaleTop"), shale_edge("ShaleEdge"), scree("ShaleScree")
EX = ks_.STONE_ATTRS
S = ks_.Set(NAME)
ks_.pad(S.gm(scree_m), (0.0, 0.0), 0.37, rnd, sides=30, dome=0.006, lobes=0.3, stretch=(1.1, 0.9), yaw=0.3, rings=3)

CELL = 0.02
heights = {}


def hgrid(x, y):
    return heights.get((int(math.floor(x / CELL)), int(math.floor(y / CELL))), 0.0)


def raise_grid(cx, cy, cz, n, rad, h):
    """The heap's surface under a plate: cells within `rad` of it, at the plane of its top."""
    nx = max(0.2, n.z)
    for ix in range(int((cx - rad) / CELL) - 1, int((cx + rad) / CELL) + 2):
        for iy in range(int((cy - rad) / CELL) - 1, int((cy + rad) / CELL) + 2):
            x, y = (ix + 0.5) * CELL, (iy + 0.5) * CELL
            if (x - cx) ** 2 + (y - cy) ** 2 > rad * rad:
                continue
            z = cz - (n.x * (x - cx) + n.y * (y - cy)) / nx + h / nx - G
            heights[(ix, iy)] = max(heights.get((ix, iy), 0.0), z)


def angular(width, rnd, sides=None, elong=None):
    """A sharp-cornered outline, `width` across the long way: 4 to 6 corners at uneven angles and distances."""
    k = sides or rnd.choice((4, 5, 5, 6))
    el = elong or rnd.uniform(1.0, 1.8)
    steps = [rnd.uniform(0.7, 1.3) for _ in range(k)]
    tot = sum(steps)
    ang, pts = rnd.uniform(0, math.tau), []
    for s in steps:
        r = rnd.uniform(0.62, 1.0) * width * 0.5
        pts.append(Vector((math.cos(ang) * r * el, math.sin(ang) * r / (el ** 0.5))))
        ang += s / tot * math.tau
    rot = rnd.uniform(0, math.tau)
    c, s_ = math.cos(rot), math.sin(rot)
    pts = [Vector((p.x * c - p.y * s_, p.x * s_ + p.y * c)) for p in pts]
    return pts


def place(width, thick, sigma, tilt_max, lod=2, lean=False):
    poly = angular(width, rnd)
    c = ks_.centroid(poly)
    rad = max((p - c).length for p in poly)
    best = None
    for _ in range(16):
        cx, cy = rnd.gauss(0, sigma) * 1.1, rnd.gauss(0, sigma) * 0.9
        if math.hypot(cx / 1.1, cy / 0.9) > 0.33:
            continue
        # the highest point of the heap under its footprint
        support = 0.0
        for ix in range(-3, 4):
            for iy in range(-3, 4):
                if ix * ix + iy * iy <= 10:
                    support = max(support, hgrid(cx + ix * rad / 3.0, cy + iy * rad / 3.0))
        score = support + 0.12 * math.hypot(cx / 1.1, cy / 0.9)
        if best is None or score < best[0]:
            best = (score, cx, cy, support)
    if best is None:
        return
    _, cx, cy, support = best
    az = rnd.uniform(0, math.tau)
    tilt = rnd.uniform(0.03, tilt_max) * (rnd.choice((1, -1)))
    rot = Matrix.Rotation(az, 3, "Z") @ Matrix.Rotation(tilt, 3, "X") @ Matrix.Rotation(-az, 3, "Z")
    h = thick * 0.5
    minz = min((rot @ Vector((p.x - c.x, p.y - c.y, -h))).z for p in poly)
    cz = G + support - minz + 0.0008
    ks_.shale(S.gm(top_m, EX), S.gm(edge_m, EX + ("lz",)), poly, rnd, rnd.random(), (cx, cy, cz), thick, rot, lod=lod)
    n = rot @ Vector((0.0, 0.0, 1.0))
    raise_grid(cx, cy, cz, n, rad * 0.9, h)


for i in range(7):
    place(rnd.uniform(0.13, 0.2), rnd.uniform(0.009, 0.017), 0.15, 0.2)
for i in range(22):
    place(rnd.uniform(0.07, 0.12), rnd.uniform(0.006, 0.012), 0.2, 0.35)
for i in range(36):
    place(rnd.uniform(0.025, 0.06), rnd.uniform(0.003, 0.008), 0.24, 0.5, lod=2)
for i in range(24):
    place(rnd.uniform(0.012, 0.026), rnd.uniform(0.003, 0.006), 0.28, 0.5, lod=1)

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024, density={"ShaleTop": 1.0, "ShaleEdge": 0.8, "ShaleScree": 0.4})
ks_.preview(SCRIPT, model, PREVIEWS, kind="dirt", height=0.07)
print("[%s] done" % SCRIPT)
