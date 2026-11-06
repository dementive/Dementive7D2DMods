"""DeadTumbleweed (wasteland): a dead Russian thistle 41 cm across lying where the wind left it, a loose hollow sphere
made of its own tangled stems: fourteen main stems springing from a knot at the middle and sweeping round the shell, two dozen
more arcing round it on their own, a few cutting across the inside, two or three side sprigs on each with spiny little awl leaves, dry papery seed
pods in twos and threes, all grey-tan and bleached, with the red-brown of the living plant left at the stem bases. You can
see through it. A few seed husks and snapped twigs lie round it. Static. The far LOD keeps the main stems and adds a cheap
opaque stand-in shell, so it reads as a ball at a distance; the near mesh has none of it.

    blender -b --factory-startup --python dead_tumbleweed.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
import gckit as gc  # noqa: E402
import kit_lod  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "DeadTumbleweed", "dead_tumbleweed"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(19)

R = 0.205
SQ = 0.92
C = Vector((0.0, 0.0, G + R * SQ + 0.0015))


# ---------------------------------------------------------------- materials

def stem_material(name, light, dark, red=0.6, bleach=0.5):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col = g.mix(g.ramp(g.noise(45.0, detail=5.0), 0.3, 0.7), dark, light)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=4.0), 0.4, 0.7), 0.5), col, tuple(c * 0.7 for c in dark))
    # The living plant's red-brown pigment, left near the stem bases and in streaks
    streak = g.math("MULTIPLY", g.ramp(t, 0.65, 0.0), g.ramp(g.noise(30.0, detail=4.0), 0.4, 0.68))
    col = g.mix(g.math("MULTIPLY", streak, red), col, (0.27, 0.11, 0.08))
    # Bleached tips
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.55, 1.0), bleach), col, (0.64, 0.58, 0.48))
    # Fine fibres and splits
    fib = kf._ridged(g, g.noise(420.0, detail=3.0, roughness=0.6))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.75, 0.98), 0.45), col, tuple(c * 0.45 for c in dark))
    sp = g.ramp(kf._voronoi(g, 230.0), 0.1, 0.03)
    col = g.mix(g.math("MULTIPLY", sp, 0.5), col, (0.05, 0.04, 0.03))
    height = g.math("ADD", g.math("MULTIPLY", fib, 0.5), g.math("MULTIPLY", g.noise(900.0, detail=2.0), 0.25))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.85, value=0.98), 0.0, 0.88, g.bump(height, 1.0, 0.0008))


def pod_material(name):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col = g.mix(g.ramp(g.noise(160.0, detail=4.0), 0.3, 0.7), (0.4, 0.28, 0.15), (0.6, 0.47, 0.28))
    veins = kf._ridged(g, g.noise(700.0, detail=2.0, distortion=1.2))
    col = g.mix(g.math("MULTIPLY", g.ramp(veins, 0.8, 0.97), 0.5), col, (0.24, 0.15, 0.08))
    col = g.mix(g.ramp(t, 0.3, 0.0), col, (0.2, 0.12, 0.07))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.98), 0.0, 0.8, g.bump(veins, 0.8, 0.0006))


def shell_material(name):
    """The far stand-in: an opaque tangle painted on a ball (pale stems over dark gaps)."""
    mat, g = tk.new_material(name)
    v = kf._warped(g, 40.0, 0.01, kf._warped(g, 8.0, 0.04))
    ln = g.math("MAXIMUM", g.ramp(kf._ridged(g, g.noise(55.0, detail=2.0, vector=v)), 0.7, 0.9),
                g.ramp(kf._ridged(g, g.noise(95.0, detail=2.0, vector=kf._warped(g, 40.0, 0.008))), 0.74, 0.92))
    col = g.mix(ln, (0.1, 0.085, 0.065), g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), (0.3, 0.25, 0.18), (0.4, 0.34, 0.26)))
    return tk.finish(mat, g, col, 0.0, 0.9, None)


stem = stem_material("TumbleStem", (0.5, 0.43, 0.32), (0.3, 0.25, 0.18))
twig = stem_material("TumbleTwig", (0.56, 0.5, 0.38), (0.36, 0.3, 0.22), red=0.3, bleach=0.7)
awl = stem_material("TumbleAwl", (0.5, 0.42, 0.28), (0.34, 0.27, 0.17), red=0.35, bleach=0.3)
pod = pod_material("TumblePod")
shell = shell_material("TumbleShell")
husk = kf.litter_material("Husk", (0.4, 0.31, 0.19), (0.27, 0.2, 0.12), spots=0.3)

b = ks.Builder("Tumble")
FAR = ks.FAR


def at_surface(v, rad):
    """A point `rad` along unit direction v from the middle, the ball squashed a little by its own weight."""
    return C + Vector((v.x * rad, v.y * rad, v.z * rad * SQ))


def catmull(pts, n):
    """`n` points along a Catmull-Rom curve through pts (so stems bend smoothly rather than in kinked segments)."""
    k = len(pts) - 1
    out = []
    for i in range(n):
        u = i / (n - 1) * k
        j = min(int(u), k - 1)
        f = u - j
        p0, p1, p2, p3 = pts[max(0, j - 1)], pts[j], pts[j + 1], pts[min(k, j + 2)]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3))
    return out


def fib_dirs(n):
    out = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        r = math.sqrt(1.0 - z * z)
        a = i * 2.39996 + rnd.uniform(-0.25, 0.25)
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def main_stem(d0):
    """A stem from the knot at the middle out to the shell (reaching it early), then sweeping round it."""
    axis = d0.cross(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)))).normalized()
    turn = rnd.uniform(1.1, 2.4) * rnd.choice((-1, 1))
    reach = rnd.uniform(0.86, 1.0)
    n = 6
    pts = []
    for i in range(n + 1):
        s = i / n
        rad = R * (0.05 + (reach - 0.05) * gc.smoothstep(0.0, 0.3, s)) * (1.0 + 0.045 * gc.fbm(d0.x * 5 + s * 3, d0.y * 5, 2.0))
        v = Matrix.Rotation(turn * max(0.0, s - 0.22) / 0.78, 3, axis) @ d0
        pts.append(at_surface(v, rad) + (Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.005 if 0 < i < n else Vector()))
    return pts


def shell_arc(v0, sweep, rad0):
    """A stem that runs along the shell on a great circle, wandering in and out."""
    axis = v0.cross(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)))).normalized()
    n = 6
    pts = []
    for i in range(n + 1):
        s = i / n
        v = Matrix.Rotation(sweep * s, 3, axis) @ v0
        rad = R * rad0 * (1.0 + 0.05 * gc.fbm(v0.x * 3 + s * 4, v0.y * 3, 7.0) + 0.02 * math.sin(s * 9 + rad0 * 20))
        pts.append(at_surface(v, rad) + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.009)
    return pts


mains = []
b.lod = 0
for d0 in fib_dirs(14):
    pts = catmull(main_stem(d0), 9)
    r0 = rnd.uniform(0.0026, 0.0034)
    radii = [r0 * (1.0 - 0.8 * (i / 8) ** 1.3) for i in range(9)]
    ks.tube(b, stem, pts, radii, sides=3, cap=False, t0=0.0, t1=1.0)
    mains.append((pts, radii))
for k, d0 in enumerate(fib_dirs(20)):
    d0 = (d0 + Vector((rnd.gauss(0, 0.3), rnd.gauss(0, 0.3), rnd.gauss(0, 0.3)))).normalized()
    pts = catmull(shell_arc(d0, rnd.uniform(1.3, 2.7) * rnd.choice((-1, 1)), rnd.uniform(0.84, 1.0)), 8)
    r0 = rnd.uniform(0.0016, 0.0026)
    radii = [r0 * (0.8 + 0.2 * math.sin(i / 7 * math.pi) - 0.5 * (i / 7) ** 3) for i in range(8)]
    b.lod = 0 if k < 12 else 1
    ks.tube(b, stem if k % 3 else twig, pts, radii, sides=3, cap=False, t0=0.1, t1=1.0)
    mains.append((pts, radii))
b.lod = 0

# A few stems that cut across the inside, tangling the shell together
for k in range(5):
    d1, d2 = fib_dirs(2)[0], Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
    p1, p2 = at_surface(d1, R * rnd.uniform(0.8, 0.97)), at_surface(d2, R * rnd.uniform(0.8, 0.97))
    mid = (p1 + p2) * 0.5 + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.035
    pts = [p1, p1.lerp(mid, 0.55), mid, mid.lerp(p2, 0.45), p2]
    b.lod = 1
    ks.tube(b, twig, pts, [0.0016, 0.0017, 0.0016, 0.0013, 0.0008], sides=3, cap=False, t0=0.2, t1=1.0)
b.lod = 0

# A mesh of thin dry twigs crossing between the stems (cheap strips)
b.lod = 1
for k in range(55):
    p0 = at_surface(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized(), R * rnd.uniform(0.55, 1.0))
    d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
    L = rnd.uniform(0.05, 0.12)
    if (p0 + d * L - C).length > R * 1.04:
        d = (-(p0 - C).normalized() * 0.5 + d).normalized()
    ks.leaf(b, twig, p0, d, L, rnd.uniform(0.0016, 0.0026), bend=rnd.uniform(-0.5, 0.5), fold=0.0, profile="strap", rows=3,
            roll=rnd.uniform(0, 180))
b.lod = 0

# Side sprigs with awl leaves, on the main stems
sprigs = []
b.lod = 1
for pts, radii in mains:
    for _ in range(rnd.randint(1, 2)):
        i = rnd.randint(2, len(pts) - 4)
        p = pts[i].lerp(pts[i + 1], rnd.random())
        tan = (pts[i + 1] - pts[i]).normalized()
        out = (p - C).normalized()
        side = tan.cross(out)
        if side.length < 1e-4:
            continue
        d = (tan * rnd.uniform(0.4, 1.0) + side.normalized() * rnd.uniform(-0.8, 0.8) + out * rnd.uniform(-0.1, 0.5)).normalized()
        L = rnd.uniform(0.05, 0.11)
        q = [p, p + d * L * 0.5, p + d * L * 0.5 + (d + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.5).normalized() * L * 0.5]
        # keep the tip on the shell
        tip = q[2] - C
        if tip.length > R * 1.03:
            q[2] = C + tip.normalized() * R * 1.0
        ks.tube(b, twig, q, [0.0012, 0.001, 0.0], sides=3, cap=False, t0=0.4, t1=1.0)
        sprigs.append(q)
        # spiny awl leaves along it
        for j in range(3):
            s = (j + 0.5) / 3
            base = q[0].lerp(q[1], s * 2) if s < 0.5 else q[1].lerp(q[2], (s - 0.5) * 2)
            ld = (d + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.9).normalized()
            ks.leaf(b, awl, base, ld, rnd.uniform(0.012, 0.022), 0.0035, bend=0.2, fold=0.3, profile="lance", rows=1)
b.lod = 0

# Dry papery seed pods
pods = 0
b.lod = 1
for pts, radii in mains:
    if rnd.random() < 0.7:
        continue
    i = rnd.randint(2, len(pts) - 4)
    p = pts[i].lerp(pts[i + 1], rnd.random())
    out = (p - C).normalized()
    for j in range(rnd.randint(2, 3)):
        q = p + (out * 0.006 + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.006)
        ks.berry(b, pod, q, rnd.uniform(0.003, 0.0045), rnd, sides=5, stretch=1.5, axis=(out + Vector((rnd.gauss(0, .5), rnd.gauss(0, .5), rnd.gauss(0, .5)))))
        pods += 1
for q in sprigs[::3]:
    ks.berry(b, pod, q[2], rnd.uniform(0.003, 0.0042), rnd, sides=5, stretch=1.4, axis=(q[2] - q[1]))
    pods += 1
b.lod = 0

# Husks and snapped twigs on the ground round it
b.lod = 1
for k in range(14):
    a = rnd.uniform(0, gc.TAU)
    r = rnd.uniform(0.12, 0.26)
    x, y = r * math.cos(a), r * math.sin(a)
    h = rnd.uniform(0, gc.TAU)
    d = Vector((math.cos(h), math.sin(h), 0.0))
    L = rnd.uniform(0.02, 0.05)
    ks.leaf(b, husk if k % 2 else twig, (x - d.x * L * 0.5, y - d.y * L * 0.5, G + 0.0025), d, L, L * 0.35, bend=0.0, fold=0.3,
            profile="oval", rows=1)
for k in range(4):
    a = rnd.uniform(0, gc.TAU)
    r = rnd.uniform(0.14, 0.3)
    x, y = r * math.cos(a), r * math.sin(a)
    h = rnd.uniform(0, gc.TAU)
    d = Vector((math.cos(h), math.sin(h), 0.0))
    L = rnd.uniform(0.06, 0.12)
    ks.tube(b, twig, [Vector((x, y, G + 0.003)) - d * L * 0.5, Vector((x, y, G + 0.004)), Vector((x, y, G + 0.003)) + d * L * 0.5],
            [0.0016, 0.0017, 0.0012], sides=3, cap=True, start_cap=True, jag=1.0, rnd=rnd)
b.lod = 0

# The far stand-in shell, only in the far mesh
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
for v in bm.verts:
    v.co = C + Vector((v.co.x * R * 0.9, v.co.y * R * 0.9, v.co.z * R * 0.9 * SQ))
m = b.mesh(shell)
b.lod = FAR
cache = {}
for f in bm.faces:
    m.begin(C)
    vs = []
    for v in f.verts:
        if v.index not in cache:
            cache[v.index] = m.v(v.co.copy(), 0.5)
        vs.append(cache[v.index])
    m.f(vs, True)
b.lod = 0
bm.free()

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] pods %d" % (SCRIPT, pods))
gc.stats(SCRIPT, pieces)
model = kit_lod.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4)
gc.previews(SCRIPT, model, PREVIEWS, kind="waste", lod_name=NAME + "_LOD1", macro=((0.12, -0.3), (0.0, 0.0)), neighbors=False)
print("[%s] done" % SCRIPT)
