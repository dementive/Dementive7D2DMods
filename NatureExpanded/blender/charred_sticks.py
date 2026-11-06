"""CharredSticks (burnt forest): nine burnt sticks and branch stubs, 15 to 50 cm long and 1.3 to 4 cm thick, lying criss-cross
on a bed of grey ash, each resting on the ones below it. The wood is crazed into the black blocks of alligator-skin char,
with silver-white weathered wood showing where the char has flaked or burnt right off (grain running along the stick),
ash settled on the top sides; the broken ends are fresh splits of brown wood with splinters standing off them, and a few
short branch stubs stick up. A scatter of charcoal crumbs and the ragged ash bed round them.

    blender -b --factory-startup --python charred_sticks.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
import gckit as gc  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "CharredSticks", "charred_sticks"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(77)
SEED = 3.0


# ---------------------------------------------------------------- materials

def _grain_space(g, k):
    """Object coordinates squeezed `k` times along each vertex's "grain" direction (the stick's own axis), so noise and
    cells drawn in them are stretched along the stick, whatever way it lies."""
    co = g.coords()
    gd = g.node("ShaderNodeAttribute", attribute_name="grain").outputs["Vector"]
    dot = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.links.new(co, dot.inputs[0])
    g.links.new(gd, dot.inputs[1])
    sc = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(gd, sc.inputs[0])
    g.links.new(tk._sock(dot.outputs, "Value"), tk._sock(sc.inputs, "Scale"))
    sc2 = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(sc.outputs[0], sc2.inputs[0])
    sc2.inputs["Scale"].default_value = 1.0 - 1.0 / k
    sub = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(co, sub.inputs[0])
    g.links.new(sc2.outputs[0], sub.inputs[1])
    return sub.outputs[0]


def stick_surface(name):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    v2 = _grain_space(g, 2.0)
    v6 = _grain_space(g, 7.0)
    # Alligator-skin char: blocks cracked across and along, deep black fissures
    wv = kf._warped(g, 55.0, 0.0028, v2)
    d, r = kf._cells(g, 95.0, wv)
    e = kf._voronoi(g, 95.0, wv, feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.1, 0.018)
    block = g.mix(g.ramp(g.noise(9.0, detail=4.0), 0.3, 0.7), (0.012, 0.011, 0.01), (0.04, 0.036, 0.032))
    block = g.mix(g.math("MULTIPLY", g.ramp(r, 0.3, 1.0), 0.35), block, (0.1, 0.092, 0.084))
    # Dull silver sheen on the raised blocks, and a fine grain
    fine = g.noise(1.0, detail=3.0, vector=_grain_space(g, 12.0))
    block = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.5, 0.8), 0.3), block, (0.12, 0.115, 0.11))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), block, (0.006, 0.0055, 0.005))
    # Browny half-burnt wood in the deep cracks
    brown = g.math("MULTIPLY", g.ramp(e, 0.05, 0.005), g.ramp(g.noise(12.0, detail=3.0), 0.5, 0.7))
    col = g.mix(g.math("MULTIPLY", brown, 0.4), col, (0.1, 0.055, 0.03))
    # Silver-white weathered wood where the char has flaked or burnt away: long grain, checks, a charred lip
    bn = g.math("ADD", g.noise(5.5, detail=5.0, distortion=0.5), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(60.0, detail=3.0), 0.5), 0.07))
    bleach = g.ramp(bn, 0.5, 0.52)
    lip = g.math("MULTIPLY", g.ramp(bn, 0.48, 0.5), g.math("SUBTRACT", 1.0, bleach))
    fib = g.noise(1.0, detail=5.0, vector=v6)
    fibre = g.ramp(kf._ridged(g, fib), 0.7, 0.97)
    wood = g.mix(g.ramp(fib, 0.3, 0.7), (0.26, 0.245, 0.225), (0.46, 0.43, 0.395))
    wood = g.mix(g.math("MULTIPLY", fibre, 0.5), wood, (0.13, 0.12, 0.11))
    chk = g.ramp(kf._voronoi(g, 1.0, kf._warped(g, 28.0, 0.0018, _grain_space(g, 18.0)), feature="DISTANCE_TO_EDGE"), 0.05, 0.0)
    wood = g.mix(g.math("MULTIPLY", chk, 0.9), wood, (0.04, 0.035, 0.03))
    col = g.mix(g.math("MULTIPLY", lip, 0.7), col, (0.05, 0.035, 0.025))
    col = g.mix(bleach, col, wood)
    # Ash settled on the upward side
    nz = ks._normal_z(g)
    ash = g.math("MULTIPLY", g.ramp(nz, 0.5, 0.9), g.ramp(g.noise(17.0, detail=5.0), 0.5, 0.7))
    ac, ar = kf._cells(g, 420.0)
    col = g.mix(g.math("MULTIPLY", ash, 0.8), col, g.mix(g.ramp(ac, 0.6, 0.25), (0.2, 0.19, 0.18), (0.34, 0.33, 0.31)))
    # A little dirt toward the ends
    height = g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, crack), 0.65), g.math("MULTIPLY", r, 0.18))
    height = g.mixf(bleach, height, g.math("ADD", 0.28, g.math("MULTIPLY", g.math("SUBTRACT", fibre, chk), 0.12)))
    height = g.math("ADD", height, g.math("MULTIPLY", ash, 0.12))
    rough = g.mixf(bleach, g.mixf(crack, 0.55, 0.95), 0.88)
    rough = g.mixf(ash, rough, 0.95)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=1.0), 0.0, rough, g.bump(height, 1.0, 0.0035))


def split_wood(name):
    """Fresh-split wood: brown fibers, pale where the splinters tear, darkened at the charred rim."""
    mat, g = tk.new_material(name)
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (180.0, 180.0, 24.0)))
    col = g.mix(g.ramp(fib, 0.3, 0.7), (0.17, 0.095, 0.05), (0.38, 0.24, 0.13))
    col = g.mix(g.math("MULTIPLY", g.ramp(kf._ridged(g, fib), 0.8, 0.98), 0.5), col, (0.5, 0.38, 0.25))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=4.0), 0.55, 0.75), 0.55), col, (0.05, 0.035, 0.025))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), 0.0, 0.9,
                     g.bump(g.math("ADD", fib, g.noise(400.0, detail=2.0)), 0.8, 0.0016))


ash_mat = gc.ash_surface("AshBed", ripple=1.2, cracks=0.3, crack_scale=12.0, light=(0.3, 0.29, 0.28), dark=(0.11, 0.105, 0.1))
stick_mat = stick_surface("StickChar")
split_mat = split_wood("SplitWood")
char = gc.char_surface("Char", ash_amount=0.4)
burnt = kf.litter_material("BurntNeedles", (0.02, 0.018, 0.016), (0.07, 0.05, 0.04), spots=0.0)

b = ks.Builder("Stick")
R0 = gc.outline(SEED, 0.4, 0.28, 0.62)


def hf(x, y):
    return 0.011 * (0.5 + gc.fbm(x * 5.0, y * 5.0, SEED)) + 0.003 * gc.fbm(x * 16.0, y * 16.0, SEED + 2.0)


R = gc.patch(b, ash_mat, rnd, radius=0.4, cell=0.04, height=hf, sink=0.012, seed=SEED, rough=0.28, floor=0.62)
gc.islands(b, ash_mat, rnd, R, 6, hf=hf, seed=SEED)

# ---------------------------------------------------------------- the sticks

placed = []          # (points, radii) of sticks already down, for the later ones to rest on
grain = {}           # vertex index -> axis direction, for the stick material's stretched grain


def support(x, y, r):
    best = None
    for pts, radii in placed:
        for i in range(len(pts) - 1):
            a, c = pts[i], pts[i + 1]
            abx, aby = c.x - a.x, c.y - a.y
            l2 = abx * abx + aby * aby
            if l2 < 1e-9:
                continue
            tt = max(0.0, min(1.0, ((x - a.x) * abx + (y - a.y) * aby) / l2))
            d = math.hypot(x - (a.x + abx * tt), y - (a.y + aby * tt))
            re = radii[i] + (radii[i + 1] - radii[i]) * tt
            if d < r + re:
                z = a.z + (c.z - a.z) * tt + math.sqrt((r + re) ** 2 - d * d)
                if best is None or z > best:
                    best = z
    return best


def stick(cx, cy, yaw, length, r0, split_ends=(True, False), bend=0.0, stubs=1):
    step = 0.028
    n = max(5, int(length / step))
    ang = yaw
    x, y = cx - math.cos(yaw) * length * 0.5, cy - math.sin(yaw) * length * 0.5
    xy = [(x, y)]
    for i in range(n):
        ang += bend / n + rnd.gauss(0.0, 0.05)
        x += math.cos(ang) * length / n
        y += math.sin(ang) * length / n
        xy.append((x, y))
    # radii: thick at the base, thinning, lumpy; the fire ate the thin end
    radii = [r0 * (1.0 - 0.38 * (i / n)) * (1.0 + 0.08 * math.sin(i * 1.7 + yaw) + rnd.uniform(-0.07, 0.07)) for i in range(n + 1)]
    z = []
    for (px, py), r in zip(xy, radii):
        need = G + hf(px, py) + r * 0.72
        sup = support(px, py, r)
        if sup is not None:
            need = max(need, sup)
        z.append(need)
    req = list(z)
    for _ in range(3):
        z = [z[0]] + [0.25 * z[i - 1] + 0.5 * z[i] + 0.25 * z[i + 1] for i in range(1, n)] + [z[-1]]
        z = [max(a, b2) for a, b2 in zip(z, req)]
    pts = [Vector((px, py, zz)) for (px, py), zz in zip(xy, z)]
    placed.append((pts, radii))
    m = b.mesh(stick_mat)
    start = len(m.bm.verts)
    saved = b.lod
    b.lod = 2
    rings = ks.tube(b, stick_mat, pts, radii, sides=5, cap=False, start_cap=False, jag=0.0)
    b.lod = saved
    tans = ks.frames(pts)
    for i, (ring, (tan, _, _)) in enumerate(zip(rings, tans)):
        for k in range(len(ring)):
            grain[start + i * 5 + k] = tuple(tan)
    # broken ends: a split face of fresh wood with splinters standing off it
    for end, flag in ((1, split_ends[1]), (0, split_ends[0])):
        if not flag:
            continue
        ring = rings[-1] if end else rings[0]
        tan = tans[-1][0] if end else -tans[0][0]
        mw = b.mesh(split_mat)
        mw.begin(pts[-1] if end else pts[0])
        cen = sum((v.co for v in ring), Vector()) / len(ring)
        rim = [mw.v(v.co + tan * rnd.uniform(-0.006, 0.006), 1.0) for v in ring]
        cv = mw.v(cen + tan * 0.006, 1.0)
        saved = b.lod
        b.lod = 1
        for k in range(len(rim)):
            gc._oriented(mw, [cv, rim[k], rim[(k + 1) % len(rim)]], tan, False)
        for k in range(rnd.randint(2, 4)):
            q = ring[k % len(ring)].co
            d = (tan + Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0.0, 0.5)))).normalized()
            gc.spike(b, split_mat, q, d, rnd.uniform(0.012, 0.03), radii[-1 if end else 0] * rnd.uniform(0.18, 0.3), sides=3,
                     lod=1, bend=(0, 0, 0.1))
        b.lod = saved
    # short branch stubs
    for k in range(stubs):
        s = rnd.uniform(0.2, 0.8)
        i = int(s * n)
        a = rnd.uniform(0.4, 1.0) * rnd.choice((-1, 1))
        side = Vector((-math.sin(ang), math.cos(ang), 0.0))
        d = (side * math.sin(a) + Vector((0, 0, math.cos(a) * 0.6 + 0.35)) + tans[i][0] * 0.3).normalized()
        L = rnd.uniform(0.04, 0.09)
        rs = radii[i] * rnd.uniform(0.35, 0.5)
        p0 = pts[i] + d * radii[i] * 0.4
        sp = [p0, p0 + d * L * 0.5, p0 + d * L]
        s_start = len(m.bm.verts)
        saved = b.lod
        b.lod = 1
        rr = ks.tube(b, stick_mat, sp, [rs * 1.15, rs, rs * 0.85], sides=4, cap=False)
        for i, ring in enumerate(rr):
            for k in range(len(ring)):
                grain[s_start + i * 4 + k] = tuple(d)
        mw = b.mesh(split_mat)
        mw.begin(sp[-1])
        rim = [mw.v(v.co.copy(), 1.0) for v in rr[-1]]
        cv = mw.v(sp[-1] + d * 0.004, 1.0)
        for kk in range(len(rim)):
            gc._oriented(mw, [cv, rim[kk], rim[(kk + 1) % len(rim)]], d, False)
        b.lod = saved


# Big ones first, crossing near the middle; the smaller lie over them
spec = [(0.50, 0.021, (True, False), 0.25, 2), (0.42, 0.018, (True, True), -0.2, 1), (0.37, 0.015, (False, True), 0.3, 1),
        (0.33, 0.0125, (True, False), -0.15, 1), (0.30, 0.0115, (True, True), 0.1, 1), (0.26, 0.01, (False, True), 0.2, 0),
        (0.22, 0.0085, (True, False), 0.0, 1), (0.19, 0.0075, (True, True), -0.2, 0), (0.15, 0.0065, (True, False), 0.0, 0)]
yaws = [rnd.uniform(0, math.pi)]
for i in range(1, len(spec)):
    yaws.append(yaws[-1] + rnd.uniform(0.6, 1.2) * rnd.choice((-1, 1)) + 0.3)
for i, ((L, r0, ends, bend, stubs), yaw) in enumerate(zip(spec, yaws)):
    spread = 0.1 + 0.03 * i
    a = rnd.uniform(0, gc.TAU)
    cx, cy = math.cos(a) * spread * rnd.random(), math.sin(a) * spread * rnd.random()
    stick(cx, cy, yaw, L, r0, split_ends=ends, bend=bend, stubs=stubs)

# Charcoal crumbs and burnt needles
for k in range(14):
    a = rnd.uniform(0, gc.TAU)
    d = math.sqrt(rnd.random()) * R(a) * 0.9
    x, y = d * math.cos(a), d * math.sin(a)
    r = rnd.uniform(0.008, 0.02)
    if support(x, y, r) is not None:
        continue
    gc.blob(b, char, (x, y, G + hf(x, y) + 0.001), (r, r * rnd.uniform(0.6, 1.0), r * rnd.uniform(0.4, 0.7)), rnd, sides=5,
            rings=1, rough=0.3, lod=1)
gc.needles(b, burnt, rnd, R, 70, hf=hf, length=(0.025, 0.05), width=0.0013, lift=0.0012)

pieces = b.objects()
for o in pieces:
    if o.name == "Stick" + stick_mat.name:
        attr = o.data.attributes.new("grain", "FLOAT_VECTOR", "POINT")
        vals = []
        for i in range(len(o.data.vertices)):
            vals.extend(grain.get(i, (0.0, 0.0, 1.0)))
        attr.data.foreach_set("vector", vals)
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"AshBed": 0.8, "StickChar": 1.6, "SplitWood": 0.8, "Char": 0.8, "BurntNeedles": 0.3})
gc.previews(SCRIPT, model, PREVIEWS, kind="burnt", lod_name=NAME + "_LOD1", macro=((0.1, -0.2), (0.0, 0.0)))
print("[%s] done" % SCRIPT)
