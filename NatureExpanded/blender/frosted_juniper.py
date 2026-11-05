"""FrostedJuniper (snow): a low spreading juniper 0.6 m tall and 0.9 m across. A lumpy mound of dense blue-green
scaly sprays (each a feathery plume of scale-leaf strips, frosted pale at the tips and dusted with snow where they
face up) over a dark heart of foliage you can't see through, low branches splaying out at its skirt, dusky blue
berries with a frosted white bloom tucked among the sprays, and patches of snow resting on top.

    blender -b --factory-startup --python frosted_juniper.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

NAME, SCRIPT = "FrostedJuniper", "frosted_juniper"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(51)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
RX, RY, H = 0.43, 0.39, 0.52


def spray_material(name, base, base2):
    """Scale-leaf foliage: blue-green, darker toward each spray's base (t), frosted pale toward its tips, fine
    overlapping scales, snow dusted where it faces up."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col = g.mix(g.ramp(g.noise(16.0, detail=3.0), 0.3, 0.7), base, base2)
    col = g.mix(g.ramp(t, 0.0, 0.55), tuple(c * 0.55 for c in base), col)
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 230.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    scales = g.ramp(tk._sock(vor.outputs, "Distance"), 0.2, 0.6)
    col = g.mix(g.math("MULTIPLY", scales, 0.55), col, tuple(c * 0.5 for c in base))
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.75, 1.0), 0.28), col, (0.5, 0.58, 0.64))
    col, rough, _ = ks._snow_dust(g, col, 0.6, 0.4, scale=12.0)
    col = tk.grade(g, col, sat=0.9, value=0.92)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(scales, 0.4, 0.002))


spray = spray_material("JuniperSpray", (0.1, 0.19, 0.17), (0.15, 0.25, 0.23))
spray2 = spray_material("JuniperSprayGreen", (0.1, 0.18, 0.11), (0.15, 0.23, 0.15))
# The heart is the sprays' own blue-green in shade, so the far LOD (fewer sprays) still reads as one mound
core = spray_material("JuniperCore", (0.065, 0.12, 0.105), (0.085, 0.15, 0.13))
bark = ks.bark("JuniperBark", (0.22, 0.14, 0.1), (0.13, 0.09, 0.07), rough=0.85, grain=50.0)
berry = nk.plant("JuniperBerry", (0.3, 0.4, 0.58), (0.56, 0.62, 0.74), rough=0.75, vary=0.35, sat=1.0, value=1.0)
snow = ks.snow("JuniperSnow")

b = ks.Builder("Juniper")


def mound(phi, zf, scale=1.0):
    """A point on the mound's outer surface at angle phi and height fraction zf (1 = top), lumpy, and its normal."""
    lump = 1.0 + 0.13 * mn.noise(Vector((math.cos(phi) * 1.3, math.sin(phi) * 1.3, zf * 1.5 + 3.0)))
    s = math.sqrt(max(0.0, 1.0 - zf * zf))
    p = Vector((RX * s * math.cos(phi) * lump * scale, RY * s * math.sin(phi) * lump * scale, G + H * zf * scale))
    n = Vector(((p.x) / (RX * RX), p.y / (RY * RY), (p.z - G) / (H * H))).normalized()
    return p, n


# The dark heart: a closed dome inside the sprays
m = b.mesh(core)
m.begin((0.0, 0.0, G))
rows = []
for ri in range(5):
    zf = math.cos(ri / 5 * math.pi * 0.5) if ri else 1.0
    row = []
    for si in range(14 if ri else 1):
        p, n = mound(si / 14 * math.tau, zf, 0.84)
        row.append(m.v(p, 0.4))
    rows.append(row)
ring = []
for si in range(14):
    p, n = mound(si / 14 * math.tau, 0.0, 0.84)
    ring.append(m.v(Vector((p.x, p.y, G - 0.01)), 0.2))
rows.append(ring)
for k in range(14):
    m.f((rows[0][0], rows[1][k], rows[1][(k + 1) % 14]), True)
for A, B in zip(rows[1:], rows[2:]):
    for k in range(14):
        k1 = (k + 1) % 14
        m.f((A[k], B[k], B[k1], A[k1]), True)

# Low branches splaying out under the skirt, curving up at their ends
b.lod = 1
branches = []
for i in range(9):
    a = (i + rnd.uniform(-0.3, 0.3)) / 9 * math.tau
    tilt = math.radians(rnd.uniform(55, 75))
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    br = ks.grow(rnd, (0.02 * math.cos(a), 0.02 * math.sin(a), G), d, rnd.uniform(0.38, 0.5),
                 rnd.uniform(0.012, 0.016), 0.0, segments=4, gravity=-0.6, wander=0.08)
    branches.append(br)
    branches += ks.branch_out(rnd, br, 2, (0.4, 0.85), (0.12, 0.2), (30, 50), 0.6, segments=1, wander=0.0, lift=0.3)
ks.wood(b, bark, branches, sides=(4, 3))
b.lod = 0

# Sprays all over the mound, lying along it like shingles: each points up the slope (outward on top), its face
# turned out, overlapping its neighbours so the dark heart only shows in the gaps
N = 262
sprays = 0
for i in range(N):
    zf = 1.0 - (i + 0.5) / N
    phi = i * 2.39996
    p, n = mound(phi, zf, rnd.uniform(0.9, 0.98))
    up_t = UP - n * UP.dot(n)
    if up_t.length < 0.25:
        up_t = Vector((p.x, p.y, 0.0)) if math.hypot(p.x, p.y) > 1e-3 else Vector((1.0, 0.0, 0.0))
    up_t.normalize()
    side_t = n.cross(up_t)
    ang = math.radians(rnd.uniform(-70, 70))
    d = (up_t * math.cos(ang) + side_t * math.sin(ang) + n * 0.4).normalized()
    L = rnd.uniform(0.13, 0.17)
    mat = spray2 if rnd.random() < 0.25 else spray
    base = p - d * 0.05
    far = rnd.random() < 0.45
    b.lod, b.lod_scale = (0, 1.35) if far else (1, 1.0)
    ks.leaf(b, mat, base, d, L, 0.026, bend=0.15, fold=0.0, profile="lance", rows=2, normal=n,
            roll=rnd.uniform(-15, 15))
    _, side, up = ks._leaf_frame(d, n)
    for j in range(4):
        sj = 0.25 + 0.17 * j
        q = ks.bent(base, d, L, 0.15, sj)
        sgn = 1.0 if j % 2 else -1.0
        sd = (d * 0.7 + side * sgn * 0.75 + up * 0.1).normalized()
        ks.leaf(b, mat, q, sd, L * (0.55 - 0.07 * j), 0.013, bend=0.15, fold=0.2, profile="lance", rows=1, normal=up)
    b.lod, b.lod_scale = 0, 1.0
    sprays += 1

# Berries tucked among the sprays
berries = 0
for i in range(80):
    zf = rnd.uniform(0.15, 0.9)
    p, n = mound(rnd.uniform(0, math.tau), zf, rnd.uniform(0.9, 1.0))
    far = rnd.random() < 0.4
    b.lod, b.lod_scale = (0, 1.4) if far else (1, 1.0)
    ks.berry(b, berry, p + n * 0.022, rnd.uniform(0.0055, 0.0065), rnd, sides=4)
    b.lod, b.lod_scale = 0, 1.0
    berries += 1

# Snow resting on top in patches, its edges sinking in among the sprays
ms = b.mesh(snow)
ms.begin((0.0, 0.0, G + H))
SECT, RINGS = 34, 9


def snow_depth(p):
    q = Vector((p.x * 7.0 + 11.0, p.y * 7.0, p.z * 3.0))
    top = max(0.0, min(1.0, (p.z - G - H * 0.5) / (H * 0.35)))
    mask = top * (0.45 + 0.85 * mn.noise(q)) + 0.2 * mn.noise(q * 2.5)
    return max(0.0, min(1.0, (mask - 0.45) / 0.2))


grid = []
for ri in range(RINGS + 1):
    zf = math.cos(ri / RINGS * math.radians(72))
    row = []
    for si in range(SECT if ri else 1):
        p, n = mound(si / SECT * math.tau + ri * 0.1, zf, 1.0)
        d = snow_depth(p)
        off = 0.022 + 0.012 * d * (0.6 + 0.4 * mn.noise(p * 30.0)) if d > 0.0 else -0.03
        row.append((ms.v(p + n * off + UP * 0.012 * d, 1.0), d))
    grid.append(row)
snow_faces = 0
for k in range(SECT):
    k1 = (k + 1) % SECT
    tri = (grid[0][0], grid[1][k], grid[1][k1])
    if max(v[1] for v in tri) > 0.0:
        ms.f([v[0] for v in tri], True)
        snow_faces += 1
for A, B in zip(grid[1:], grid[2:]):
    for k in range(SECT):
        k1 = (k + 1) % SECT
        quad = (A[k], B[k], B[k1], A[k1])
        if max(v[1] for v in quad) > 0.0:
            ms.f([v[0] for v in quad], True)
            snow_faces += 1

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] sprays %d, berries %d, snow faces %d" % (SCRIPT, sprays, berries, snow_faces))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.28, distance=2.0)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.28, distance=2.0)
print("[%s] done" % SCRIPT)
