"""MossyLog (forest floor and edges): a fallen, half-rotten trunk 2.25 m long and 40 cm thick lying along x, sunk a
little into the ground. Furrowed dark grey-brown bark peeling away in patches to bare silver-tan wood, lumpy
cushions of green moss over its top, two tiers of brown banded shelf fungi with pale
undersides on its sides, a snapped-off branch stub, one end broken and splintered, the other rotted hollow; two ferns
growing by the hollow end and dead leaves on the ground around it.

    blender -b --factory-startup --python mossy_log.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

NAME, SCRIPT = "MossyLog", "mossy_log"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(21)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
X0, X1 = -1.12, 1.12
RINGS, SIDES = 40, 22


# ---------------------------------------------------------------- materials

RELIEF = 0.006  # meters of bump for a height of 1: bark furrows and moss clumps a few millimeters deep


def log_surface(g):
    """The log's skin as node signals (color, height 0..1, roughness), shared by the bark and the moss shell, whose
    rim shows exactly this so the shell's edge can't be seen. Bark of long ridges split by deep furrows that wander,
    branch and merge along the log and break across here and there, each stretch of ridge its own shade, flaky and
    finely grained, crusted with pale lichen in places; torn away in patches to weathered grey-tan wood (fibers, long
    checks, a few beetle galleries) behind a ragged lip of red-brown inner bark; a thin film of moss creeping over the
    top in clumps; darker and damp toward the ground. Everything has structure down to a few millimeters: smooth
    noise alone reads as smeared paint up close, and Voronoi cells alone as crazy paving."""
    # Furrows: the crest lines of a noise stretched along the log (fibrous, ragged-edged), plus a few cross breaks
    st = ks._stretched(g, (1.0, 6.5, 6.5))
    wv = kf._warped(g, 35.0, 0.0035, kf._warped(g, 3.0, 0.03, st))
    n = g.noise(5.5, detail=3.0, roughness=0.45, vector=wv)
    crest = g.math("ADD", kf._ridged(g, n), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(20.0, detail=2.0), 0.5), 0.05))
    crack = g.ramp(crest, 0.93, 1.0)
    _, piece = kf._cells(g, 5.5, wv)
    cross = g.math("MULTIPLY", g.ramp(kf._voronoi(g, 5.5, wv, feature="DISTANCE_TO_EDGE"), 0.04, 0.0),
                   g.ramp(g.noise(5.0, detail=3.0), 0.5, 0.62))
    crack = g.math("MAXIMUM", crack, cross)
    furrow = g.math("SUBTRACT", 1.0, crack)
    flake = g.noise(1.0, detail=6.0, roughness=0.65, vector=ks._stretched(g, (30.0, 95.0, 95.0)))
    grain = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (90.0, 520.0, 520.0)))
    tone = g.math("ADD", g.math("MULTIPLY", piece, 0.7), g.math("MULTIPLY", g.noise(9.0, detail=3.0, vector=wv), 0.3))
    col = g.mix(g.ramp(tone, 0.2, 0.9), (0.07, 0.056, 0.044), (0.13, 0.108, 0.084))
    col = g.mix(g.math("MULTIPLY", g.ramp(flake, 0.5, 0.75), 0.7), col, (0.17, 0.155, 0.135))
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.55, 0.2), 0.4), col, (0.03, 0.024, 0.02))
    # Stringy fibres along the ridges
    strings = g.ramp(kf._ridged(g, g.noise(1.0, detail=3.0, vector=ks._stretched(g, (12.0, 180.0, 180.0)))), 0.86, 0.98)
    col = g.mix(g.math("MULTIPLY", strings, 0.4), col, (0.025, 0.02, 0.016))
    # The furrows: narrow, steep brown walls going black at the bottom
    col = g.mix(g.math("MULTIPLY", g.ramp(crack, 0.05, 0.45), 0.85), col, (0.035, 0.025, 0.018))
    col = g.mix(g.ramp(crack, 0.45, 0.9), col, (0.006, 0.005, 0.004))
    # Lichen: pale grey-green crusts, granular, on the ridges here and there
    lich = g.math("MULTIPLY", g.ramp(g.math("ADD", g.noise(9.0, detail=5.0, distortion=0.3),
                                              g.math("MULTIPLY", g.noise(120.0, detail=2.0), 0.08)), 0.68, 0.72),
                  g.ramp(furrow, 0.4, 0.8))
    gran, _ = kf._cells(g, 420.0)
    lichen = g.math("MULTIPLY", lich, g.ramp(gran, 0.75, 0.35))
    col = g.mix(lichen, col, g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.35, 0.7), (0.13, 0.15, 0.1), (0.21, 0.225, 0.17)))
    bark_h = g.math("ADD", g.math("MULTIPLY", furrow, 0.55), g.math("MULTIPLY", flake, 0.3))
    bark_h = g.math("SUBTRACT", bark_h, g.math("MULTIPLY", strings, 0.06))
    bark_h = g.math("ADD", bark_h, g.math("ADD", g.math("MULTIPLY", grain, 0.08), g.math("MULTIPLY", lichen, 0.08)))

    # Bare wood where the bark has fallen away, behind a ragged lip of red-brown inner bark
    pn = g.math("ADD", g.noise(2.0, detail=5.0, distortion=0.5),
                g.math("MULTIPLY", g.math("SUBTRACT", g.noise(45.0, detail=4.0), 0.5), 0.05))
    peel = g.ramp(pn, 0.64, 0.646)
    lip = g.math("MULTIPLY", g.ramp(pn, 0.633, 0.64), g.math("SUBTRACT", 1.0, peel))
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (5.0, 260.0, 260.0)))
    fibre = g.ramp(kf._ridged(g, fib), 0.75, 0.98)
    wood = g.mix(g.ramp(fib, 0.3, 0.7), (0.12, 0.1, 0.078), (0.22, 0.195, 0.155))
    wood = g.mix(g.math("MULTIPLY", fibre, 0.35), wood, (0.27, 0.245, 0.2))
    check = g.ramp(kf._voronoi(g, 1.0, kf._warped(g, 30.0, 0.002, ks._stretched(g, (1.6, 28.0, 28.0))),
                               feature="DISTANCE_TO_EDGE"), 0.03, 0.0)
    gallery = g.math("MULTIPLY", g.ramp(kf._ridged(g, g.noise(26.0, detail=2.0, distortion=1.6)), 0.955, 0.99),
                     g.ramp(g.noise(4.0), 0.5, 0.6))
    wood = g.mix(g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=4.0), 0.55, 0.75), 0.6), wood, (0.08, 0.06, 0.04))
    # Grime gathered along the torn edge
    wood = g.mix(g.math("MULTIPLY", g.ramp(pn, 0.69, 0.646), 0.7), wood, (0.05, 0.04, 0.03))
    wood = g.mix(g.math("MAXIMUM", check, gallery), wood, (0.025, 0.018, 0.013))
    wood_h = g.math("ADD", 0.2, g.math("MULTIPLY", fibre, 0.08))
    wood_h = g.math("SUBTRACT", wood_h, g.math("MULTIPLY", g.math("MAXIMUM", check, gallery), 0.2))
    col = g.mix(g.math("MULTIPLY", lip, 0.8), col,
                g.mix(g.ramp(g.noise(200.0), 0.3, 0.7), (0.06, 0.032, 0.02), (0.11, 0.06, 0.035)))
    col = g.mix(peel, col, wood)
    height = g.mixf(peel, bark_h, wood_h)
    rough = g.mixf(peel, g.mixf(lichen, 0.88, 0.93), 0.8)

    # A thin film of moss creeping over the top, in clumps at its edge
    mcol, mh, mrough, _ = kf.moss_layer(g)
    reach = g.math("ADD", g.noise(3.5, detail=5.0), g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.3))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(40.0, detail=3.0), 0.5), 0.12))
    stain = g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.3, 0.8), g.ramp(reach, 0.52, 0.6))
    col = g.mix(stain, col, mcol)
    height = g.mixf(stain, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.5)))
    rough = g.mixf(stain, rough, mrough)

    z = g.separate(g.coords())[2]
    col = g.mix(g.math("MULTIPLY", g.ramp(z, G + 0.12, G), 0.6), col, (0.022, 0.018, 0.014))
    rough = g.mixf(g.ramp(z, G + 0.1, G), rough, 0.7)
    return tk.grade(g, col, sat=0.95, value=0.95), height, rough


def log_bark():
    mat, g = tk.new_material("LogBark")
    col, height, rough = log_surface(g)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, RELIEF))


def end_wood(name, rot=False):
    """Split end grain: growth rings round the log's axis, splintery streaks; `rot` makes it dark crumbling punk."""
    mat, g = tk.new_material(name)
    co = g.coords()
    x, y, z = g.separate(co)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", y, y),
                              g.math("MULTIPLY", g.math("SUBTRACT", z, G + 0.165), g.math("SUBTRACT", z, G + 0.165))))
    rings = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, 140.0), g.math("MULTIPLY", g.noise(6.0), 4.0))),
                   -0.4, 0.6)
    fib = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (5.0, 90.0, 90.0)))
    if rot:
        col = g.mix(g.ramp(fib, 0.3, 0.7), (0.07, 0.035, 0.018), (0.2, 0.1, 0.045))
        col = g.mix(g.math("MULTIPLY", rings, 0.3), col, (0.04, 0.02, 0.012))
        rough = 0.95
    else:
        col = g.mix(rings, (0.24, 0.18, 0.12), (0.46, 0.38, 0.27))
        col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.55, 0.75), 0.6), col, (0.12, 0.08, 0.05))
        rough = 0.85
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.math("ADD", rings, fib), 0.4, 0.003))


def log_moss():
    """The moss cushions: kf.moss_layer's clumps, giving way toward the rim of each patch (t runs 0 at the rim to 1
    inside) to exactly the log's own surface, through a ragged line of separate clumps; so the patch's edge is drawn
    by the texture, not by where the shell happens to cut through the bark's faces."""
    mat, g = tk.new_material("LogMoss")
    t = ks._attr(g, "t")
    bcol, bh, brough = log_surface(g)
    mcol, mh, mrough, _ = kf.moss_layer(g)
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.3), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(14.0, detail=5.0), 0.5), 0.6))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.5))
    cover = g.ramp(reach, 0.36, 0.5)
    col = g.mix(cover, bcol, tk.grade(g, mcol, sat=0.95, value=0.95))
    height = g.mixf(cover, bh, g.math("ADD", 0.25, g.math("MULTIPLY", mh, 0.75)))
    rough = g.mixf(cover, brough, mrough)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, RELIEF))


def fungus_top():
    """Bracket fungus cap: concentric growth zones of browns and greys (t runs from the trunk to the rim), each zone a
    low ridge, a velvety grain, a green tinge of algae on the old zones by the trunk, a pale growing rim."""
    mat, g = tk.new_material("FungusTop")
    t = ks._attr(g, "t")
    wob = g.math("ADD", g.math("MULTIPLY", g.noise(12.0), 3.0), g.math("MULTIPLY", g.noise(70.0, detail=3.0), 0.6))
    bands = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 34.0), wob))
    zone = g.ramp(bands, -0.6, 0.6)
    col = g.mix(zone, (0.14, 0.065, 0.03), (0.42, 0.25, 0.1))
    grey = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 11.0), wob)), 0.45, 0.9)
    col = g.mix(g.math("MULTIPLY", grey, 0.55), col, (0.2, 0.18, 0.15))
    col = g.mix(g.ramp(t, 0.55, 0.0), col, (0.07, 0.045, 0.03))
    algae = g.math("MULTIPLY", g.ramp(t, 0.5, 0.1), g.ramp(g.noise(25.0, detail=4.0), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", algae, 0.6), col, (0.07, 0.1, 0.035))
    velvet = g.noise(450.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(velvet, 0.6, 0.25), 0.3), col, (0.05, 0.035, 0.025))
    col = g.mix(g.ramp(t, 0.84, 0.97), col, (0.72, 0.62, 0.44))
    height = g.math("ADD", g.math("MULTIPLY", g.math("POWER", zone, 0.5), 0.5), g.math("MULTIPLY", velvet, 0.15))
    return tk.finish(mat, g, col, 0.0, 0.86, g.bump(height, 1.0, 0.0012))


bark = log_bark()
wood = end_wood("LogEnd")
rot = end_wood("LogRot", rot=True)
moss = log_moss()
cap = fungus_top()
pores = kf.pores("FungusPores", (0.72, 0.65, 0.5), (0.5, 0.43, 0.31), scale=900.0)
fern_mat = nk.plant("LogFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
litter = [nk.plant("Litter", (0.16, 0.09, 0.04), (0.1, 0.06, 0.03), vary=0.4),
          nk.plant("LitterGold", (0.3, 0.17, 0.05), (0.2, 0.09, 0.03), vary=0.4)]

b = ks.Builder("Log")


# ---------------------------------------------------------------- the trunk

def radius_at(x):
    return 0.205 - 0.022 * (x - X0) / (X1 - X0)


def center_at(x):
    return Vector((x, 0.05 * math.sin(x * 1.4 + 0.5), G + radius_at(x) * 0.8 + 0.02 * math.sin(x * 2.1 + 0.3)))


KNOTS = [(0.3, math.radians(70)), (-0.45, math.radians(-25)), (0.8, math.radians(200)), (-0.85, math.radians(130))]


def surface(x, a, r_scale=1.0):
    """A point on the bark at x and angle a round the axis (0 = +y, 90 = up), with lumps and knot bulges."""
    c = center_at(x)
    n = Vector((0.0, math.cos(a), math.sin(a)))
    q = Vector((x * 2.2, math.cos(a) * 1.4, math.sin(a) * 1.4))
    bump = 1.0 + 0.08 * mn.noise(q) + 0.03 * mn.noise(q * 4.0) + 0.012 * mn.noise(q * 11.0)
    for kx, ka in KNOTS:
        da = math.atan2(math.sin(a - ka), math.cos(a - ka))
        bump += 0.09 * math.exp(-((x - kx) / 0.07) ** 2 - (da / 0.35) ** 2)
    return c + n * radius_at(x) * bump * r_scale, n


# Ragged break at +x: each vertex of the last ring torn off at a different length
jag = [rnd.uniform(-0.03, 0.04) + (rnd.uniform(0.08, 0.16) if rnd.random() < 0.25 else 0.0) for _ in range(SIDES)]
xs = [X0 + (X1 - X0) * i / (RINGS - 1) for i in range(RINGS)]
m = b.mesh(bark)
m.begin((0.0, 0.0, G))
grid = []
for i, x in enumerate(xs):
    row = []
    for k in range(SIDES):
        a = k / SIDES * math.tau
        xx = x + (jag[k] if i == RINGS - 1 else 0.0)
        p, n = surface(xx, a)
        row.append((m.v(p, 0.5 + 0.5 * math.sin(a)), p, n))
    grid.append(row)
b.lod = 2
for i in range(RINGS - 1):
    for k in range(SIDES):
        k1 = (k + 1) % SIDES
        quad = (grid[i][k], grid[i][k1], grid[i + 1][k1], grid[i + 1][k])
        if max(q[1].z for q in quad) < G - 0.012:
            continue  # under the ground
        m.f([q[0] for q in quad], True)
b.lod = 0

# The splintered end: a jagged, sunken face of torn wood
mw = b.mesh(wood)
mw.begin((X1, 0.0, G))
c_end = center_at(X1)
center = mw.v(c_end + Vector((-0.015, 0.0, 0.0)), 1.0)
inner = []
for k in range(SIDES):
    a = (k + 0.5) / SIDES * math.tau
    p, n = surface(X1 + rnd.uniform(-0.02, 0.06) + (0.1 if rnd.random() < 0.2 else 0.0), a, 0.55)
    inner.append(mw.v(p, 0.8))
rim = [mw.v(grid[-1][k][1], 1.0) for k in range(SIDES)]
for k in range(SIDES):
    k1 = (k + 1) % SIDES
    mw.f((center, inner[k], inner[k1]), False)
    mw.f((inner[k], rim[k1], inner[k1]), False)
    mw.f((inner[k], rim[k], rim[k1]), False)

# The hollow end: a ring of sapwood round a rotted-out core running back into the log
mr = b.mesh(rot)
mr.begin((X0, 0.0, G))
rim = [mw.v(grid[0][k][1], 1.0) for k in range(SIDES)]
lip = []
for k in range(SIDES):
    a = k / SIDES * math.tau
    p, n = surface(X0 + 0.015, a, 0.62 + rnd.uniform(-0.05, 0.05))
    lip.append(p)
lip_w = [mw.v(p, 1.0) for p in lip]
for k in range(SIDES):
    k1 = (k + 1) % SIDES
    mw.f((rim[k], lip_w[k], lip_w[k1], rim[k1]), False)
hollow = []
for depth, scale in ((0.015, 0.62), (0.16, 0.5), (0.32, 0.32)):
    ring = []
    for k in range(SIDES):
        a = k / SIDES * math.tau
        p, n = surface(X0 + depth, a, scale * (1.0 if depth > 0.02 else 1.0))
        ring.append(mr.v(lip[k] if depth < 0.02 else p, 0.3))
    hollow.append(ring)
apex = mr.v(center_at(X0 + 0.42), 0.0)
for A, B in zip(hollow, hollow[1:]):
    for k in range(SIDES):
        k1 = (k + 1) % SIDES
        mr.f((A[k], B[k], B[k1], A[k1]), True)
for k in range(SIDES):
    k1 = (k + 1) % SIDES
    mr.f((hollow[-1][k], apex, hollow[-1][k1]), True)

# ---------------------------------------------------------------- moss: a thick lumpy cushion over the top


def moss_depth(x, a):
    top = math.sin(a)
    if top < 0.05:
        return 0.0
    q = Vector((x * 2.4 + 7.0, math.cos(a) * 1.8, top * 1.8))
    mask = min(1.0, (top - 0.05) / 0.45) * (0.55 + 0.8 * mn.noise(q) + 0.25 * mn.noise(q * 3.0))
    if x > X1 - 0.12:
        mask *= max(0.0, (X1 - x) / 0.12)
    d = max(0.0, min(1.0, (mask - 0.42) / 0.3))
    return d * (0.008 + 0.022 * max(0.0, 0.5 + 0.7 * mn.noise(q * 6.0)))


mm = b.mesh(moss)
mm.begin((0.0, 0.0, G))
shell = {}


def shell_vert(i, k):
    if (i, k) not in shell:
        _, p, n = grid[i][k]
        d = moss_depth(p.x, k / SIDES * math.tau)
        out = Vector((0.0, n.y, n.z))
        # Outside the patch the shell dips under the bark, so its edge follows the noise rather than the quads
        shell[(i, k)] = mm.v(p + out * (d + 0.0015 if d > 0.0 else -0.006), min(1.0, d / 0.012))
    return shell[(i, k)]


for i in range(RINGS - 1):
    for k in range(SIDES):
        k1 = (k + 1) % SIDES
        corners = ((i, k), (i, k1), (i + 1, k1), (i + 1, k))
        if max(moss_depth(grid[a][c][1].x, c / SIDES * math.tau) for a, c in corners) < 0.004:
            continue
        mm.f([shell_vert(a, c) for a, c in corners], True)

# ---------------------------------------------------------------- branch stubs

for sx, sa, length, r0, lean in ((0.3, math.radians(70), 0.3, 0.042, 0.35), (-0.45, math.radians(-25), 0.11, 0.03, 0.0)):
    p, n = surface(sx, sa)
    d = (Vector((lean, n.y, n.z)) + Vector((0.0, 0.0, 0.25))).normalized()
    start = p - n * 0.06
    pts = [start + d * (length * s) for s in (0.0, 0.35, 0.7, 1.0)]
    rings = ks.tube(b, bark, pts, [r0, r0 * 0.9, r0 * 0.8, r0 * 0.72], sides=6, cap=False, jag=1.6, rnd=rnd)
    mw = b.mesh(wood)
    mw.begin(pts[-1])
    rimv = [mw.v(v.co.copy(), 1.0) for v in rings[-1]]
    cv = mw.v(pts[-1] - d * 0.012, 1.0)
    for k in range(6):
        mw.f((cv, rimv[k], rimv[(k + 1) % 6]), False)

# ---------------------------------------------------------------- shelf fungi in tiers on the sides

for gx, ga, tiers in ((0.62, math.radians(185), 3), (-0.12, math.radians(170), 3), (0.95, math.radians(-5), 2)):
    for j in range(tiers):
        a = ga + math.radians(rnd.uniform(-8, 8)) + math.radians(14) * j
        x = gx + rnd.uniform(-0.06, 0.06)
        p, n = surface(x, a)
        out = Vector((0.0, n.y, 0.0))
        rad = rnd.uniform(0.07, 0.1) * (1.0 - 0.15 * j)
        b.lod = 1 if rad < 0.065 else 0
        ks.shelf_fungus(b, cap, pores, p - out * 0.015, out, rad, rnd, thickness=rad * 0.3, depth=0.85, segs=8)
        b.lod = 0

# ---------------------------------------------------------------- ferns by the hollow end, leaf litter round it

ks.fern(b, fern_mat, (X0 + 0.05, 0.3, G), rnd, fronds=8, length=(0.48, 0.62), pinnae=13, pinna_len=0.09,
        pinna_w=0.024, away=70.0, arc=200.0, tilt=(18.0, 50.0), bend=(0.35, 0.7), far=(0.4, 1.4))
ks.fern(b, fern_mat, (X0 - 0.12, -0.22, G), rnd, fronds=7, length=(0.4, 0.52), pinnae=12, pinna_len=0.09,
        pinna_w=0.024, away=-120.0, arc=210.0, tilt=(18.0, 50.0), bend=(0.35, 0.7), far=(0.4, 1.4))

b.lod = 1
for k in range(36):
    x = rnd.uniform(X0 - 0.15, X1 + 0.1)
    side = rnd.choice((-1.0, 1.0))
    y = center_at(x).y + side * rnd.uniform(0.2, 0.5)
    a = rnd.uniform(0, math.tau)
    d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.05, 0.12)))
    ks.leaf(b, rnd.choice(litter), (x, y, G + 0.004), d, rnd.uniform(0.06, 0.09), rnd.uniform(0.035, 0.05),
            bend=-0.1, fold=0.3, profile="oval", roll=rnd.uniform(-20, 20))
b.lod = 0

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
# The atlas goes mostly to the bark and moss, seen up close; ferns and litter only need their color
model = ks.export(NAME, pieces, MODELS, size=2048, coarse_ratio=0.35,
                  density={"LogBark": 1.0, "LogMoss": 1.0, "FungusTop": 1.3, "FungusPores": 0.6, "LogEnd": 0.7,
                           "LogRot": 0.6, "LogFern": 0.4, "Litter": 0.4})
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.2, distance=3.4)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.2, distance=3.4)
print("[%s] done" % SCRIPT)
