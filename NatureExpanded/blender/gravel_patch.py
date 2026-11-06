"""GravelPatch (wasteland): a 0.9 m patch of coarse gravel and rubble over packed dust: some fifty angular chips of
grey, brown and tan stone, a dozen pieces of crushed concrete (pale cement with aggregate and air pits, one with a stub of
rusted rebar), a brick end, three bigger chunks, a tongue of wind-blown dust drifting over one side and burying the
smaller stones, and a tuft of dry weed pushing up at the edge with a couple of seed stalks. The rim is a scatter of loose
stones giving out into the dust.

    blender -b --factory-startup --python gravel_patch.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "GravelPatch", "gravel_patch"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(88)
SEED = 11.0


# ---------------------------------------------------------------- materials

def _palette(g, r, colors):
    """Picks among `colors` by the 0..1 value r (hard steps, so each stone is one color)."""
    n = len(colors)
    col = colors[-1]
    for i in range(n - 2, -1, -1):
        col = g.mix(g.ramp(r, (i + 1) / n - 0.002, (i + 1) / n + 0.002), colors[i], col)
    return col


STONES = [(0.2, 0.19, 0.18), (0.27, 0.22, 0.16), (0.14, 0.135, 0.13), (0.34, 0.29, 0.21), (0.24, 0.235, 0.22),
          (0.3, 0.25, 0.2)]


def gravel_bed(name):
    """Packed gravel as ground: three sizes of chip heaped over one another (each its own grey, brown or tan, each a
    rounded dome of a different height so the lower ones are half buried), dust in the gaps, wind streaks of pale dust
    across the tops, dissolving into dust at the rim."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    wv = kf._warped(g, 55.0, 0.0055, kf._warped(g, 8.0, 0.025))
    scales = (30.0, 62.0, 125.0)
    cells = [kf._cells(g, sc, wv) for sc in scales]
    edges = [kf._voronoi(g, sc, wv, feature="DISTANCE_TO_EDGE") for sc in scales]
    zone1 = g.ramp(g.noise(4.0, detail=3.0), 0.36, 0.52)
    zone2 = g.ramp(g.noise(7.5, detail=3.0), 0.55, 0.7)
    cols = [_palette(g, c[1], STONES) for c in cells]
    col = g.mix(zone2, g.mix(zone1, cols[2], cols[1]), cols[0])
    d = g.mixf(zone2, g.mixf(zone1, cells[2][0], cells[1][0]), cells[0][0])
    e = g.mixf(zone2, g.mixf(zone1, edges[2], edges[1]), edges[0])
    rr = g.mixf(zone2, g.mixf(zone1, cells[2][1], cells[1][1]), cells[0][1])
    # Each chip a dome of its own height; shade by that height so the heaped look comes through
    dome = g.ramp(d, 0.8, 0.0)
    level = g.math("ADD", g.math("MULTIPLY", rr, 0.7), 0.3)
    shade = g.math("ADD", g.math("MULTIPLY", level, 0.55), 0.45)
    col = g.mix(g.math("SUBTRACT", 1.0, shade), col, tuple(c * 0.45 for c in STONES[0]))
    grain, gr = kf._cells(g, 420.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.4), col, (0.38, 0.34, 0.28))
    col = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.25, 0.05), 0.35), col, (0.05, 0.047, 0.044))
    gap = g.math("MULTIPLY", g.ramp(e, 0.14, 0.01), g.ramp(rr, 0.7, 0.2))
    col = g.mix(g.math("MULTIPLY", gap, 0.8), col, g.mix(g.ramp(g.noise(80.0, detail=3.0), 0.3, 0.7), (0.07, 0.058, 0.045), (0.2, 0.165, 0.12)))
    streak = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (3.0, 14.0, 4.0)))
    dust = g.math("MULTIPLY", g.ramp(streak, 0.45, 0.68), g.ramp(g.noise(20.0, detail=4.0), 0.35, 0.62))
    dust = g.math("MULTIPLY", dust, g.ramp(rr, 0.8, 0.2))
    col = g.mix(g.math("MULTIPLY", dust, 0.6), col, (0.36, 0.3, 0.21))
    edge = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(35.0, detail=4.0), 0.5), 0.35))
    col = g.mix(g.ramp(edge, 0.3, 0.04), col, g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), (0.26, 0.21, 0.15), (0.34, 0.28, 0.2)))
    height = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", dome, 0.6), g.math("MULTIPLY", level, 0.5)), g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gap, 0.6)))
    height = g.math("ADD", height, g.math("MULTIPLY", grain, 0.12))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(500.0, detail=2.0), 0.1))
    rough = g.mixf(gap, 0.85, 0.95)
    return tk.finish(mat, g, tk.grade(g, col, sat=1.0, value=0.97), 0.0, rough, g.bump(height, 1.0, 0.007))


def gravel_stone(name):
    """A single chip of rock: color picked by t, a speckled crystalline grain, a few pale veins, dust on the up faces."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col = _palette(g, t, STONES)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(28.0, detail=4.0), 0.4, 0.7), 0.35), col, (0.1, 0.095, 0.09))
    gd, gr = kf._cells(g, 330.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.72, 0.95), 0.45), col, (0.42, 0.38, 0.32))
    col = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.2, 0.02), 0.45), col, (0.04, 0.038, 0.035))
    vein = g.ramp(kf._voronoi(g, 7.0, kf._warped(g, 20.0, 0.01), feature="DISTANCE_TO_EDGE"), 0.006, 0.0)
    vein = g.math("MULTIPLY", vein, g.ramp(g.noise(3.0, detail=3.0), 0.5, 0.62))
    col = g.mix(g.math("MULTIPLY", vein, 0.7), col, (0.04, 0.038, 0.035))
    nz = ks._normal_z(g)
    dust = g.math("MULTIPLY", g.ramp(nz, 0.35, 0.85), g.ramp(g.noise(22.0, detail=5.0), 0.3, 0.55))
    col = g.mix(g.math("MULTIPLY", dust, 0.7), col, (0.35, 0.29, 0.21))
    height = g.math("ADD", g.math("MULTIPLY", gr, 0.4), g.math("MULTIPLY", g.noise(60.0, detail=4.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", vein, 0.2))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.98), 0.0, g.mixf(dust, 0.82, 0.95), g.bump(height, 1.0, 0.0028))


def concrete(name):
    """Broken concrete: grey cement paste with a fine grain, small angular aggregate of grey, tan and dark stone showing in
    a spray, air pits, weathered and stained, dust in the hollows."""
    mat, g = tk.new_material(name)
    paste = g.mix(g.ramp(g.noise(10.0, detail=5.0), 0.3, 0.7), (0.3, 0.29, 0.275), (0.42, 0.41, 0.39))
    paste = g.mix(g.math("MULTIPLY", g.ramp(g.noise(300.0, detail=3.0), 0.4, 0.75), 0.3), paste, (0.2, 0.195, 0.185))
    wv = kf._warped(g, 70.0, 0.004, kf._warped(g, 12.0, 0.012))
    d, r = kf._cells(g, 150.0, wv)
    d2, r2 = kf._cells(g, 280.0, wv)
    peb = g.ramp(d, 0.4, 0.3)
    peb2 = g.ramp(d2, 0.38, 0.28)
    spray = g.ramp(g.noise(9.0, detail=4.0), 0.36, 0.55)
    peb = g.math("MULTIPLY", g.math("MULTIPLY", peb, g.ramp(r, 0.35, 0.5)), spray)
    peb2 = g.math("MULTIPLY", g.math("MULTIPLY", peb2, g.ramp(r2, 0.4, 0.55)), g.ramp(g.noise(7.0, detail=4.0), 0.3, 0.5))
    peb_col = g.mix(g.ramp(r, 0.0, 1.0), (0.14, 0.135, 0.125), (0.42, 0.36, 0.27))
    peb_col = g.mix(g.ramp(r, 0.5, 0.6), peb_col, (0.24, 0.24, 0.25))
    peb2_col = g.mix(g.ramp(r2, 0.0, 1.0), (0.2, 0.19, 0.18), (0.36, 0.31, 0.24))
    col = g.mix(g.math("MULTIPLY", peb2, 0.85), paste, peb2_col)
    col = g.mix(g.math("MULTIPLY", peb, 0.9), col, peb_col)
    pits = g.ramp(kf._voronoi(g, 170.0, kf._warped(g, 70.0, 0.003)), 0.12, 0.05)
    col = g.mix(g.math("MULTIPLY", pits, 0.85), col, (0.05, 0.045, 0.04))
    stain = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.5), 0.58, 0.75), 0.55)
    col = g.mix(stain, col, (0.17, 0.115, 0.075))
    soot = g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=5.0), 0.62, 0.74), 0.5)
    col = g.mix(soot, col, (0.1, 0.095, 0.09))
    nz = ks._normal_z(g)
    dust = g.math("MULTIPLY", g.ramp(nz, 0.4, 0.85), g.ramp(g.noise(18.0, detail=5.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", dust, 0.6), col, (0.34, 0.29, 0.22))
    height = g.math("ADD", g.math("MULTIPLY", g.math("MAXIMUM", peb, peb2), 0.3), g.math("MULTIPLY", g.noise(260.0, detail=3.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pits, 0.45))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), 0.0, 0.93, g.bump(height, 1.0, 0.004))


def brick(name):
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(12.0, detail=5.0), 0.3, 0.7), (0.2, 0.085, 0.06), (0.3, 0.14, 0.095))
    d, r = kf._cells(g, 240.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(r, 0.8, 0.95), 0.5), col, (0.5, 0.4, 0.3))
    pits = g.ramp(kf._voronoi(g, 160.0), 0.14, 0.05)
    col = g.mix(g.math("MULTIPLY", pits, 0.8), col, (0.07, 0.03, 0.02))
    nz = ks._normal_z(g)
    dust = g.math("MULTIPLY", g.ramp(nz, 0.4, 0.85), g.ramp(g.noise(18.0, detail=5.0), 0.3, 0.55))
    col = g.mix(g.math("MULTIPLY", dust, 0.3), col, (0.3, 0.22, 0.15))
    height = g.math("ADD", g.math("MULTIPLY", r, 0.35), g.math("MULTIPLY", g.noise(200.0, detail=3.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pits, 0.4))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.98), 0.0, 0.92, g.bump(height, 1.0, 0.0035))


bed = gravel_bed("GravelBed")
chip = gravel_stone("GravelChip")
conc = concrete("CrushedConcrete")
brk = brick("BrickEnd")
bar = gc.rust_surface("Rebar", paint=None, rust=1.2, flake_scale=70.0, relief=0.0025)
dust_mat = gc.ash_surface("DustDrift", ripple=1.8, cracks=0.2, light=(0.4, 0.33, 0.24), dark=(0.28, 0.23, 0.17),
                          soil=(0.12, 0.095, 0.07), specks=0.35, crack_scale=7.0,
                          rim=((0.26, 0.21, 0.15), (0.34, 0.28, 0.2)))
weed = nk.plant("DryWeed", (0.5, 0.43, 0.26), (0.34, 0.29, 0.17), rough=0.8, vary=0.3, sat=0.85)
weed_d = nk.plant("DryWeedGrey", (0.36, 0.34, 0.28), (0.25, 0.22, 0.17), rough=0.8, vary=0.3, sat=0.8)
seed = nk.plant("WeedSeed", (0.45, 0.33, 0.17), (0.32, 0.22, 0.11), rough=0.8, vary=0.3, sat=0.9)

b = ks.Builder("Grav")
R0 = gc.outline(SEED, 0.4, 0.26, 0.64)


def hf(x, y):
    return 0.007 * (0.5 + gc.fbm(x * 6.0, y * 6.0, SEED)) + 0.003 * gc.fbm(x * 20.0, y * 20.0, SEED + 2.0)


R = gc.patch(b, bed, rnd, radius=0.4, cell=0.044, height=hf, sink=0.014, seed=SEED, rough=0.26, floor=0.64)
placed = []   # (x, y, r)


def free(x, y, r, gap=0.0):
    return all(math.hypot(x - px, y - py) > r + pr + gap for px, py, pr in placed)


def spot(r, inset=0.92, tries=60, gap=0.0):
    for _ in range(tries):
        a = rnd.uniform(0, gc.TAU)
        d = math.sqrt(rnd.random()) * R0(a) * inset
        x, y = d * math.cos(a), d * math.sin(a)
        if free(x, y, r, gap):
            placed.append((x, y, r))
            return x, y
    return None


# Dust tongue first, so what lies on it can be sunk
dust_c = (0.13, -0.07)
Rdust = gc.patch(b, dust_mat, rnd, radius=0.2, cell=0.034, height=lambda x, y: hf(x, y) + 0.011 * max(0.0, 1.0 - math.hypot(x - dust_c[0], y - dust_c[1]) / 0.2),
                 sink=0.006, seed=SEED + 4.0, rough=0.34, floor=0.55, center=dust_c, offset_z=0.003, fade=0.4)

# ---------------------------------------------------------------- big chunks
# A slab of concrete with rebar sticking out of it
p = spot(0.075)
if p:
    x, y = p
    base = G + hf(x, y) - 0.008
    gc.stone(b, conc, (x, y, base + 0.026), (0.085, 0.062, 0.034), rnd, subdiv=2, power=3.4, rough=0.06, cuts=4, base_z=base,
             t=0.5, tilt=7.0, lod=2)
    a = rnd.uniform(0, gc.TAU)
    d = Vector((math.cos(a), math.sin(a), 0.35)).normalized()
    p0 = Vector((x, y, base + 0.03)) + Vector((math.cos(a), math.sin(a), 0)) * 0.035
    pts = [p0, p0 + d * 0.04 + Vector((0, 0, 0.004)), p0 + d * 0.085 + Vector((math.cos(a + 1.4) * 0.012, math.sin(a + 1.4) * 0.012, -0.012))]
    saved = b.lod
    b.lod = 2
    ks.tube(b, bar, pts, [0.0058, 0.0056, 0.0054], sides=6, cap=True, jag=0.0)
    b.lod = saved
# A grey-brown boulder, half sunk
p = spot(0.065)
if p:
    x, y = p
    base = G + hf(x, y) - 0.02
    gc.stone(b, chip, (x, y, base + 0.03), (0.075, 0.058, 0.04), rnd, subdiv=2, power=2.5, rough=0.1, cuts=3, base_z=base,
             t=0.58, tilt=9.0, lod=2)
# A brick end
p = spot(0.04)
if p:
    x, y = p
    base = G + hf(x, y) - 0.006
    gc.stone(b, brk, (x, y, base + 0.016), (0.052, 0.03, 0.021), rnd, subdiv=1, power=5.0, rough=0.05, cuts=1, base_z=base,
             t=0.5, tilt=12.0, lod=2)

# ---------------------------------------------------------------- crushed concrete
for k in range(12):
    rr = rnd.uniform(0.016, 0.038)
    p = spot(rr * 1.1, gap=0.004)
    if not p:
        continue
    x, y = p
    base = G + hf(x, y) - 0.004
    gc.stone(b, conc, (x, y, base + rr * 0.55), (rr, rr * rnd.uniform(0.65, 1.0), rr * rnd.uniform(0.45, 0.75)), rnd,
             subdiv=1, power=rnd.uniform(2.8, 4.0), rough=0.08, cuts=2, base_z=base, t=0.5, tilt=15.0, lod=2 if rr > 0.028 else 1)

# ---------------------------------------------------------------- gravel chips
for k in range(54):
    rr = rnd.uniform(0.008, 0.021)
    p = spot(rr, inset=0.97, gap=-0.002)
    if not p:
        continue
    x, y = p
    gc.blob(b, chip, (x, y, G + hf(x, y) + rr * 0.1), (rr, rr * rnd.uniform(0.65, 1.0), rr * rnd.uniform(0.45, 0.8)), rnd,
            sides=rnd.choice((5, 6)), rings=1, t=rnd.random(), rough=0.28, axis=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 1.0), lod=1)

# ---------------------------------------------------------------- the weed tuft
wx, wy = -0.2, 0.2
if math.hypot(wx, wy) > R0(math.atan2(wy, wx)) * 0.85:
    wx, wy = wx * 0.7, wy * 0.7
for k in range(14):
    a = k / 14 * gc.TAU + rnd.uniform(-0.3, 0.3)
    d = Vector((math.cos(a) * rnd.uniform(0.25, 0.7), math.sin(a) * rnd.uniform(0.25, 0.7), 1.0))
    mat = weed if k % 3 else weed_d
    saved = b.lod
    b.lod = 0 if k % 2 == 0 else 1
    b.lod_scale = 1.3 if b.lod == 0 else 1.0
    ks.leaf(b, mat, (wx + rnd.uniform(-0.012, 0.012), wy + rnd.uniform(-0.012, 0.012), G + hf(wx, wy)), d, rnd.uniform(0.1, 0.22),
            rnd.uniform(0.008, 0.014), bend=rnd.uniform(0.4, 1.1), fold=0.25, profile="lance", rows=3, roll=rnd.uniform(-30, 30))
    b.lod_scale = 1.0
    b.lod = saved
for k in range(3):
    a = rnd.uniform(0, gc.TAU)
    d = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 1.0))
    h = rnd.uniform(0.2, 0.3)
    base = (wx + rnd.uniform(-0.01, 0.01), wy + rnd.uniform(-0.01, 0.01), G + hf(wx, wy))
    pts = [ks.bent(base, d, h, 0.5, s) for s in (0.0, 0.4, 0.75, 1.0)]
    saved = b.lod
    b.lod = 1
    ks.tube(b, weed_d, pts, [0.0018, 0.0014, 0.001, 0.0], sides=3, cap=False)
    for j in range(7):
        q = ks.bent(base, d, h, 0.5, 0.58 + 0.4 * j / 6)
        ks.berry(b, seed, q + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5))) * 0.005, rnd.uniform(0.0032, 0.0048),
                 rnd, sides=4, stretch=1.3, axis=(0, 0, 1))
    b.lod = saved

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"GravelBed": 0.8, "GravelChip": 1.6, "CrushedConcrete": 1.5, "BrickEnd": 1.0, "Rebar": 1.0,
                           "DustDrift": 0.7, "DryWeed": 0.5, "DryWeedGrey": 0.5, "WeedSeed": 0.4})
gc.previews(SCRIPT, model, PREVIEWS, kind="waste", lod_name=NAME + "_LOD1", macro=((0.12, -0.26), (0.0, 0.0)))
print("[%s] done" % SCRIPT)
