"""RustFlakes (wasteland): wasteland junk on dusty ground, a 0.9 m patch: three scraps of corrugated iron (one with its end
curled up, one folded along a crease, one a torn little piece with rust holes), their paint faded and flaking, the rust
scaling off in plates; a hex bolt, a washer, a crown bottle cap (plain faded enamel, no lettering), three nails, a few
turns of rusty wire, and scores of loose orange and brown flakes that have dropped from them. The dust round them is
stained orange where the rust has bled into it, cracked into curling plates, and the rim gives out into plain dust.

    blender -b --factory-startup --python rust_flakes.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
import gckit as gc  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "RustFlakes", "rust_flakes"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(41)
SEED = 5.0

# Where the junk lies (for the stains on the ground): (x, y, reach)
SPOTS = [(-0.1, 0.05, 0.19), (0.17, -0.12, 0.16), (0.05, 0.25, 0.1), (-0.27, -0.17, 0.07), (0.3, 0.1, 0.05),
         (-0.02, -0.28, 0.06), (0.24, 0.22, 0.08)]


# ---------------------------------------------------------------- materials

def dust_crust(name, spots):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    big = g.noise(4.5, detail=6.0, roughness=0.6)
    col = g.mix(g.ramp(big, 0.3, 0.72), (0.27, 0.2, 0.13), (0.4, 0.31, 0.2))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(40.0, detail=4.0), 0.4, 0.72), 0.4), col, (0.15, 0.12, 0.085))
    # Curling plates of dried crust, dark cracks between, pale dust lying in streaks
    e = kf._voronoi(g, 7.5, kf._warped(g, 22.0, 0.012, kf._warped(g, 4.0, 0.03)), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(e, 0.04, 0.01), g.ramp(g.noise(3.0, detail=3.0), 0.3, 0.55))
    lip = g.math("MULTIPLY", g.ramp(e, 0.16, 0.05), g.math("SUBTRACT", 1.0, g.ramp(e, 0.05, 0.02)))
    col = g.mix(g.math("MULTIPLY", lip, 0.3), col, (0.42, 0.35, 0.26))
    col = g.mix(g.math("MULTIPLY", crack, 0.8), col, (0.1, 0.075, 0.05))
    streak = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (3.0, 12.0, 4.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(streak, 0.55, 0.75), 0.35), col, (0.42, 0.35, 0.26))
    # Fine grit
    gd, gr = kf._cells(g, 260.0)
    grit = g.math("MULTIPLY", g.ramp(gd, 0.34, 0.16), g.ramp(gr, 0.5, 0.58))
    col = g.mix(g.math("MULTIPLY", grit, 0.7), col, g.mix(g.ramp(gr, 0.5, 1.0), (0.12, 0.105, 0.09), (0.4, 0.36, 0.3)))
    # Rust bled into the dust round each piece of junk, with orange flecks
    x, y, z = g.separate(g.coords())
    stain = None
    for (cx, cy, rr) in spots:
        dx = g.math("SUBTRACT", x, cx)
        dy = g.math("SUBTRACT", y, cy)
        d = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy)))
        m = g.ramp(g.math("ADD", g.math("DIVIDE", d, rr), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(12.0, detail=4.0), 0.5), 0.7)), 1.0, 0.25)
        stain = m if stain is None else g.math("MAXIMUM", stain, m)
    col = g.mix(g.math("MULTIPLY", stain, 0.8), col, g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), (0.2, 0.09, 0.04), (0.34, 0.15, 0.06)))
    fd, fr = kf._cells(g, 330.0)
    fleck = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(fd, 0.36, 0.16), g.ramp(fr, 0.4, 0.5)), g.math("MULTIPLY", stain, 1.4))
    col = g.mix(g.math("MULTIPLY", fleck, 0.9), col, (0.42, 0.19, 0.07))
    # Rim: thin pale dust, then plain ground
    edge = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(35.0, detail=4.0), 0.5), 0.3))
    col = g.mix(g.ramp(edge, 0.25, 0.03), col, g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), (0.27, 0.22, 0.16), (0.34, 0.285, 0.21)))
    height = g.math("ADD", g.math("MULTIPLY", big, 0.3), g.math("MULTIPLY", lip, 0.35))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.7))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", grit, 0.25), g.math("MULTIPLY", g.noise(420.0, detail=2.0), 0.12)))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.98), 0.0, g.mixf(crack, 0.95, 0.88), g.bump(height, 1.0, 0.0045))


def cap_paint(name, color):
    """A crown cap in plain faded enamel (no lettering): a pressed ring, chips down to rust, a rusted fluted skirt."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    paint = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), color, tuple(c * 0.7 for c in color))
    paint = g.mix(g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=4.0), 0.55, 0.75), 0.5), paint, tuple(min(1.0, c * 1.5 + 0.05) for c in color))
    ring = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, 0.34)), 0.05, 0.0), 0.5)
    paint = g.mix(ring, paint, tuple(c * 0.55 for c in color))
    rust = g.mix(g.ramp(g.noise(60.0, detail=5.0), 0.3, 0.7), (0.3, 0.12, 0.05), (0.16, 0.07, 0.035))
    chip = g.math("MAXIMUM", g.ramp(g.noise(24.0, detail=6.0, distortion=0.4), 0.6, 0.66), g.ramp(t, 0.12, 0.0))
    chip = g.math("MULTIPLY", chip, g.ramp(g.noise(5.0, detail=3.0), 0.25, 0.5))
    col = g.mix(chip, paint, rust)
    pit = g.ramp(kf._voronoi(g, 350.0), 0.14, 0.06)
    col = g.mix(g.math("MULTIPLY", pit, 0.6), col, (0.04, 0.025, 0.018))
    dust = g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=5.0), 0.45, 0.7), 0.5)
    col = g.mix(dust, col, (0.3, 0.24, 0.17))
    height = g.math("ADD", g.math("MULTIPLY", chip, -0.3), g.math("MULTIPLY", g.noise(260.0, detail=3.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pit, 0.3))
    height = g.math("ADD", height, ring)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.98), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, chip), 0.15), 0.62,
                     g.bump(height, 1.0, 0.0012))


dust = dust_crust("DustCrust", SPOTS)
sheet = gc.rust_surface("RustSheet", paint=(0.17, 0.25, 0.24), rust=1.0)
galv = gc.rust_surface("RustGalv", paint=None, rust=0.9, galv=0.8)
iron = gc.rust_surface("RustIron", paint=None, rust=1.4, flake_scale=70.0, relief=0.0028)
flake_mat = gc.rust_flake("RustFlake")
cap_mat = cap_paint("CapEnamel", (0.3, 0.1, 0.07))

b = ks.Builder("Rust")


def hf(x, y):
    return 0.006 * (0.5 + gc.fbm(x * 6.0, y * 6.0, SEED)) + 0.0025 * gc.fbm(x * 22.0, y * 22.0, SEED + 2.0)


R = gc.patch(b, dust, rnd, radius=0.4, cell=0.05, height=hf, sink=0.012, seed=SEED, rough=0.26, floor=0.66)
gc.islands(b, dust, rnd, R, 5, hf=hf, seed=SEED)


def smooth_step(a, b2, x):
    return gc.smoothstep(a, b2, x)


# ---------------------------------------------------------------- corrugated iron

def corrugated(mat, center, L, W, yaw, curl=0.0, crease=0.0, period=0.05, amp=0.011, rows=7, tilt=(0.0, 0.0), holes=0):
    """A scrap of corrugated sheet: W across the ridges, L along them; the end curled up by `curl` radians or folded by
    `crease` radians half way, ragged torn ends and sides, a few rust holes."""
    nu = max(8, int(W / period * 4))
    m = b.mesh(mat)
    rot = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X")
           @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y"))
    # profile along v: angle of the sheet
    dv = L / (rows - 1)
    theta = []
    for j in range(rows):
        s = j / (rows - 1)
        th = curl * smooth_step(0.55, 1.0, s) + crease * smooth_step(0.46, 0.54, s)
        theta.append(th)
    pos = [(0.0, 0.0)]
    for j in range(1, rows):
        a = 0.5 * (theta[j - 1] + theta[j])
        pos.append((pos[-1][0] + math.cos(a) * dv, pos[-1][1] + math.sin(a) * dv))
    grid = []
    for i in range(nu + 1):
        u = (i / nu - 0.5) * W
        col = []
        for j in range(rows):
            wave = amp * math.cos(2 * math.pi * u / period) * (0.7 + 0.3 * smooth_step(0.0, 0.5, j / (rows - 1)) if False else 1.0)
            th = theta[j]
            y = pos[j][0] - math.sin(th) * wave
            z = pos[j][1] + math.cos(th) * wave
            # tear the ends and sides
            if j in (0, rows - 1):
                y += rnd.uniform(-1, 1) * L * 0.05 * (1.0 if j else -1.0) * (1.0 if rnd.random() < 0.6 else 0.2)
            uu = u + (rnd.uniform(-1, 1) * period * 0.12 if i in (0, nu) else 0.0)
            col.append(Vector((uu, y - L * 0.5, z)))
        grid.append(col)
    pts = [[rot @ p for p in col] for col in grid]
    lo = min(p.z for col in pts for p in col)
    gz = G + hf(center[0], center[1]) + 0.0015
    shift = Vector((center[0], center[1], gz - lo))
    b.lod = 2
    m.begin(shift)
    verts = [[m.v(p + shift, 0.5) for p in col] for col in pts]
    up = rot @ Vector((0, 0, 1))
    skip = set()
    for _ in range(holes):
        skip.add((rnd.randint(1, nu - 2), rnd.randint(1, rows - 3)))
    for i in range(nu):
        for j in range(rows - 1):
            if (i, j) in skip or ((i in (0, nu - 1) or j in (0, rows - 2)) and rnd.random() < 0.13):
                continue
            gc._oriented(m, [verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]], up, True)
    b.lod = 0
    return [(verts[0][0].co + verts[-1][-1].co) * 0.5]


corrugated(sheet, (-0.1, 0.05), 0.27, 0.22, 25.0, curl=2.1, tilt=(2.0, -3.0), holes=0)
corrugated(galv, (0.17, -0.12), 0.21, 0.18, -50.0, crease=0.8, tilt=(0.0, 2.0), holes=0)
corrugated(sheet, (0.05, 0.25), 0.13, 0.11, 100.0, rows=5, holes=0)


# ---------------------------------------------------------------- hardware

def hex_bolt(at, yaw, tilt=14.0):
    d = Vector((math.cos(math.radians(yaw)) * math.cos(math.radians(tilt)), math.sin(math.radians(yaw)) * math.cos(math.radians(tilt)),
                math.sin(math.radians(tilt))))
    p = Vector((at[0], at[1], G + hf(at[0], at[1]) + 0.0045))
    b.lod = 2
    ks.tube(b, iron, [p - d * 0.012, p + d * 0.0], [0.0105, 0.0105], sides=6, cap=True, start_cap=True)
    ks.tube(b, iron, [p + d * 0.0, p + d * 0.002, p + d * 0.06], [0.0062, 0.0058, 0.0056], sides=6, cap=True)
    b.lod = 0


def washer(at, ro=0.016, ri=0.0072, thick=0.002, tilt=(6.0, 4.0), segs=9):
    rot = Matrix.Rotation(math.radians(tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y")
    c = Vector((at[0], at[1], G + hf(at[0], at[1]) + 0.004))
    m = b.mesh(iron)
    b.lod = 1
    m.begin(c)
    rings = {}
    for name, r, z in (("to", ro, thick), ("ti", ri, thick), ("bo", ro, 0.0), ("bi", ri, 0.0)):
        rings[name] = [m.v(c + rot @ Vector((r * math.cos(k / segs * gc.TAU) * (1 + 0.04 * math.sin(k * 3.1)),
                                             r * math.sin(k / segs * gc.TAU), z)), 0.5) for k in range(segs)]
    up = rot @ Vector((0, 0, 1))
    for k in range(segs):
        k1 = (k + 1) % segs
        to, ti, bo, bi = rings["to"], rings["ti"], rings["bo"], rings["bi"]
        gc._oriented(m, [to[k], to[k1], ti[k1], ti[k]], up, True)
        gc._oriented(m, [bo[k], bo[k1], bi[k1], bi[k]], -up, True)
        mid = (to[k].co + to[k1].co) * 0.5
        gc._oriented(m, [to[k], to[k1], bo[k1], bo[k]], Vector((mid.x - c.x, mid.y - c.y, 0)), True)
        mid = (ti[k].co + ti[k1].co) * 0.5
        gc._oriented(m, [ti[k], ti[k1], bi[k1], bi[k]], Vector((c.x - mid.x, c.y - mid.y, 0)), True)
    b.lod = 0


def crown_cap(at, tilt=(24.0, 8.0), yaw=0.0, flutes=12, radius=0.0165, height=0.0055):
    rot = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y")
    c = Vector((at[0], at[1], G + hf(at[0], at[1]) + 0.008))
    m = b.mesh(cap_mat)
    b.lod = 2
    m.begin(c)
    n = flutes * 2
    top = []
    skirt = []
    for k in range(n):
        a = k / n * gc.TAU
        dent = 1.0 + 0.05 * math.sin(a * 2.0 + 1.0)
        top.append(m.v(c + rot @ Vector((radius * 0.9 * math.cos(a) * dent, radius * 0.9 * math.sin(a), height)), 0.34))
        rr = radius * (1.0 if k % 2 == 0 else 0.93) * dent
        skirt.append(m.v(c + rot @ Vector((rr * math.cos(a), rr * math.sin(a), 0.0 if k % 2 == 0 else 0.0006)), 0.0))
    cv = m.v(c + rot @ Vector((0, 0, height * 0.97)), 1.0)
    up = rot @ Vector((0, 0, 1))
    for k in range(n):
        k1 = (k + 1) % n
        gc._oriented(m, [cv, top[k], top[k1]], up, True)
        mid = (top[k].co + top[k1].co) * 0.5
        gc._oriented(m, [top[k], top[k1], skirt[k1], skirt[k]], Vector((mid.x - c.x, mid.y - c.y, 0.2)), False)
    b.lod = 0


def nail(at, yaw, tilt=8.0, L=0.05):
    d = Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.tan(math.radians(tilt)) * 0.5)).normalized()
    p = Vector((at[0], at[1], G + hf(at[0], at[1]) + 0.0025))
    b.lod = 1
    ks.tube(b, iron, [p, p + d * 0.0012, p + d * 0.0016, p + d * L], [0.0033, 0.0033, 0.0012, 0.0], sides=4, cap=False,
            start_cap=True)
    b.lod = 0


def wire(at, rnd_seed):
    r2 = random.Random(rnd_seed)
    pts = []
    x, y = at
    a = r2.uniform(0, gc.TAU)
    for k in range(13):
        a += 0.55 + r2.uniform(-0.15, 0.2)
        rad = 0.045 * (1.0 - 0.04 * k)
        px, py = x + rad * math.cos(a) * 1.1, y + rad * math.sin(a)
        pts.append(Vector((px, py, G + hf(px, py) + 0.002 + 0.002 * math.sin(k * 0.9) + (0.004 if k in (5, 6) else 0.0))))
    b.lod = 1
    ks.tube(b, iron, pts, [0.0016] * 13, sides=3, cap=True, start_cap=True)
    b.lod = 0


hex_bolt((-0.27, -0.17), 70.0)
washer((0.3, 0.1))
crown_cap((-0.02, -0.28), yaw=40.0)
for at, yaw in (((0.3, -0.04), 200.0), ((-0.3, 0.12), 30.0), ((0.12, 0.05), 110.0)):
    nail(at, yaw)
wire((0.24, 0.22), 7)

# ---------------------------------------------------------------- loose flakes that fell from the junk
cx = [(-0.1, 0.05, 0.2), (0.17, -0.12, 0.17), (0.05, 0.25, 0.1), (-0.27, -0.17, 0.07), (0.3, 0.1, 0.06), (0.0, 0.0, 0.4)]
m = b.mesh(flake_mat)
b.lod = 1
count = 0
tries = 0
while count < 46 and tries < 400:
    tries += 1
    sx, sy, sr = rnd.choice(cx)
    a = rnd.uniform(0, gc.TAU)
    d = math.sqrt(rnd.random()) * sr * 1.1
    x, y = sx + d * math.cos(a), sy + d * math.sin(a)
    if math.hypot(x, y) > R(math.atan2(y, x)) * 0.95:
        continue
    size = rnd.uniform(0.007, 0.022) * (1.4 if rnd.random() < 0.15 else 1.0)
    n = rnd.randint(5, 7)
    cup = size * rnd.uniform(-0.35, 0.45)
    tv = rnd.random()
    z0 = G + hf(x, y) + 0.0018
    rot = Matrix.Rotation(rnd.uniform(0, gc.TAU), 3, "Z") @ Matrix.Rotation(math.radians(rnd.uniform(-14, 14)), 3, "X") @ Matrix.Rotation(math.radians(rnd.uniform(-14, 14)), 3, "Y")
    m.begin((x, y, z0))
    c = Vector((x, y, z0))
    cv = m.v(c + rot @ Vector((0, 0, cup)), tv)
    ring = []
    for k in range(n):
        ang = k / n * gc.TAU + rnd.uniform(-0.3, 0.3)
        rr = size * rnd.uniform(0.55, 1.1) * (1.0 if k % 2 else rnd.uniform(0.8, 1.2))
        ring.append(m.v(c + rot @ Vector((rr * math.cos(ang), rr * math.sin(ang), rnd.uniform(0.0, 0.0015))), tv))
    for k in range(n):
        gc._oriented(m, [cv, ring[k], ring[(k + 1) % n]], Vector((0, 0, 1)), False)
    count += 1
b.lod = 0

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"DustCrust": 0.6, "RustSheet": 1.2, "RustGalv": 1.2, "RustIron": 1.8, "RustFlake": 1.0, "CapEnamel": 2.2})
gc.previews(SCRIPT, model, PREVIEWS, kind="waste", lod_name=NAME + "_LOD1", macro=((0.1, -0.2), (0.05, 0.0)))
print("[%s] done" % SCRIPT)
