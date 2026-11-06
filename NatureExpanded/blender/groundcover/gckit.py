"""Ground-cover kit: what the seven small walk-through patches (IceCrust, FrostHeavedStones, AshPatch, CharredSticks,
GravelPatch, RustFlakes, DeadTumbleweed) share, on top of naturekit / kit_forest / kit_shrub / zkit.

A ground-cover patch is a block decoration about 0.9 m across lying on the ground (ground at z = nk.GROUND). It is never
a flat textured card: the ground under it is a RAGGED, gently heaved height-field (`patch`), its rim sunk a little below
the terrain so the edge dissolves into the surrounding ground, and the things on it (stones, plates, sticks, scraps) are
real objects with real relief. Everything is built into a ks.Builder so the far LOD is chosen by leaving parts out
(`b.lod = 1`) or decimating the big smooth ones (`b.lod = 2`).

- `patch`: the ragged height-field (t = 1 in the middle, 0 at the rim).
- `stone`: a closed, faceted stone with flat cut faces and a flattened bottom.
- `spike`, `blob`: needle-ice spikes, charcoal lumps, seed pods.
- `scatter_in`: points inside an outline, spaced.
- `previews`: stand / crouch / macro / 3 m / top / LOD shots on a biome ground.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
TAU = math.tau


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    os.makedirs(a[1], exist_ok=True)
    return a[0], a[1]


def reset():
    """nk.reset, then render and bake on the CPU unless GC_CPU=0: the GPU is shared with other jobs and a queue there is
    slower than 24 cores."""
    nk.reset()
    if os.environ.get("GC_CPU", "1") != "0":
        bpy.context.scene.cycles.device = "CPU"


def atlas_size(default):
    return int(os.environ.get("GC_SIZE", default))


# ---------------------------------------------------------------- noise

def fbm(x, y, seed=0.0, octaves=3, z=0.0):
    s = 0.0
    amp = 1.0
    f = 1.0
    tot = 0.0
    for _ in range(octaves):
        s += amp * mn.noise(Vector((x * f + seed * 13.17, y * f + seed * 7.71, z * f + seed * 3.31)))
        tot += amp
        amp *= 0.5
        f *= 2.03
    return s / tot


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the ground: a ragged height-field

def outline(seed, radius, rough=0.3, floor=0.55):
    """R(angle): a ragged outline round the middle of a patch, `rough` how far it wanders (fraction of radius)."""
    def R(a):
        c, s = math.cos(a), math.sin(a)
        n = fbm(c * 1.5, s * 1.5, seed) * 1.6 + fbm(c * 5.0, s * 5.0, seed + 9.0) * 0.7
        return radius * max(floor, min(1.12, 1.0 + rough * n))
    return R


def _tri(m, a, b, c, smooth=True):
    if a is b or b is c or a is c:
        return None
    pa, pb, pc = a.co, b.co, c.co
    area = (pb.x - pa.x) * (pc.y - pa.y) - (pb.y - pa.y) * (pc.x - pa.x)
    if abs(area) < 1e-12:
        return None
    if area < 0.0:
        b, c = c, b
    return m.f((a, b, c), smooth)


def _stitch(m, A, B, smooth=True):
    """Triangles between two rings [(angle, vert)] (ascending angles, different counts) so a polar grid can thin out
    toward the middle."""
    na, nb = len(A), len(B)
    # B starts at the vertex just at or before A[0]
    a0 = A[0][0]
    k = 0
    for j in range(nb):
        if B[j][0] <= a0 + 1e-9:
            k = j
    B = B[k:] + B[:k]

    def ang_a(i):
        return A[i % na][0] + TAU * (i // na)

    # unwrap B so it is ascending from its start
    ub = []
    for j in range(nb):
        v = B[j][0]
        while ub and v < ub[-1]:
            v += TAU
        ub.append(v)

    def angb(j):
        return ub[j % nb] + TAU * (j // nb)

    i = j = 0
    while i < na or j < nb:
        if i >= na:
            adv_a = False
        elif j >= nb:
            adv_a = True
        else:
            adv_a = ang_a(i + 1) <= angb(j + 1)
        if adv_a:
            _tri(m, A[i % na][1], A[(i + 1) % na][1], B[j % nb][1], smooth)
            i += 1
        else:
            _tri(m, A[i % na][1], B[(j + 1) % nb][1], B[j % nb][1], smooth)
            j += 1


def patch(b, mat, rnd, radius=0.42, cell=0.04, height=None, sink=0.012, seed=1.0, rough=0.3, floor=0.55, lod=2,
          center=(0.0, 0.0), fade=0.22, t_curve=1.0, smooth=True, offset_z=0.0, t_scale=1.0):
    """A ragged height-field lying on the ground: polar rings of vertices (thinning toward the middle), the outline
    wandering (`outline`), `height(x, y)` meters above the ground, fading to nothing over the outer `fade` of the
    radius where the rim is sunk `sink` below the ground. t is 1 in the middle and falls to 0 at the rim. Returns the
    outline function R(angle) (for scattering things inside)."""
    m = b.mesh(mat)
    R = outline(seed, radius, rough, floor)
    n = max(3, int(round(radius / cell)))
    b.lod = lod
    m.begin((center[0], center[1], G))
    rings = []
    cx, cy = center

    def z_at(x, y, f):
        h = height(x, y) if height else 0.0
        k = smoothstep(1.0, 1.0 - fade, f)
        return G + offset_z + h * k - (sink * smoothstep(1.0 - fade * 0.8, 1.0, f))

    c = m.v((cx, cy, z_at(cx, cy, 0.0)), t_scale)
    rings.append([(0.0, c)])
    for i in range(1, n + 1):
        f = i / n
        k = max(6, int(round(TAU * f * radius / cell)))
        off = rnd.uniform(0.0, TAU)
        row = []
        for j in range(k):
            a = (j + rnd.uniform(-0.18, 0.18)) / k * TAU
            rr = f * R(a) * (1.0 + (rnd.uniform(-0.04, 0.04) if i == n else 0.0))
            x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
            row.append((a, m.v((x, y, z_at(x, y, f)), (1.0 - f ** t_curve) * t_scale)))
        row.sort(key=lambda p: p[0])
        rings.append(row)
    # inner fan
    A, B = rings[0], rings[1]
    for j in range(len(B)):
        _tri(m, A[0][1], B[j][1], B[(j + 1) % len(B)][1], smooth)
    for A, B in zip(rings[1:], rings[2:]):
        _stitch(m, A, B, smooth)
    b.lod = 0
    return R


def scatter_in(R, count, rnd, gap, inset=0.9, center=(0.0, 0.0), tries=60):
    """`count` points inside the outline R spaced `gap` apart (gap can be a function of the point)."""
    pts = []
    t = 0
    while len(pts) < count and t < count * tries:
        t += 1
        a = rnd.uniform(0.0, TAU)
        r = math.sqrt(rnd.random()) * R(a) * inset
        p = (center[0] + r * math.cos(a), center[1] + r * math.sin(a))
        ok = True
        for q in pts:
            if math.hypot(p[0] - q[0], p[1] - q[1]) < (gap(p) if callable(gap) else gap):
                ok = False
                break
        if ok:
            pts.append(p)
    return pts


# ---------------------------------------------------------------- stones and lumps

def stone(b, mat, center, radii, rnd, subdiv=2, power=2.5, rough=0.1, cuts=2, base_z=None, t=0.5, tilt=8.0, yaw=None,
          lod=2, smooth=True, cut_depth=(0.6, 0.85), grain=0.0, flat_top=False):
    """A closed faceted stone (a super-ellipsoid with noise and `cuts` flat split faces), the underside flattened at
    `base_z` and left open (it sits on the ground or a pedestal). `t` is the stone's value for the "t" attribute (a
    number, or a function of the world position): materials use it for height-based dirt or per-stone color."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    a, bb, c = radii
    size = (a * bb * c) ** (1.0 / 3.0)
    seed = rnd.uniform(0.0, 100.0)
    planes = []
    for _ in range(cuts):
        nrm = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.7)))
        if nrm.length < 1e-3:
            continue
        planes.append((nrm.normalized(), rnd.uniform(*cut_depth) * size))
    if flat_top:
        planes.append((Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1.0)).normalized(), 0.62 * c))
    rot = (Matrix.Rotation(math.radians(yaw if yaw is not None else rnd.uniform(0, 360)), 3, "Z")
           @ Matrix.Rotation(math.radians(rnd.uniform(-tilt, tilt)), 3, "X")
           @ Matrix.Rotation(math.radians(rnd.uniform(-tilt, tilt)), 3, "Y"))
    center = Vector(center)
    n = power
    for v in bm.verts:
        u = v.co.normalized()
        s = (abs(u.x) ** n + abs(u.y) ** n + abs(u.z) ** n) ** (-1.0 / n)
        p = Vector((u.x * s * a, u.y * s * bb, u.z * s * c))
        q = p / size * 1.3 + Vector((seed, seed * 0.53, seed * 0.31))
        p += u * ((mn.fractal(q, 0.5, 2.0, 3, noise_basis="PERLIN_ORIGINAL") * 0.75 + 0.3 * mn.noise(q * 5.0)) * rough * size)
        for nrm, d in planes:
            over = p.dot(nrm) - d
            if over > 0.0:
                p -= nrm * over
        v.co = rot @ p + center
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0012)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0008, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-6], context="FACES_ONLY")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if base_z is not None:
        for v in bm.verts:
            if v.co.z < base_z:
                v.co.z = base_z
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if max(v.co.z for v in f.verts) <= base_z + 1e-5],
                         context="FACES_ONLY")
    bm.verts.ensure_lookup_table()
    saved = b.lod
    b.lod = lod
    m = b.mesh(mat)
    cache = {}
    for f in bm.faces:
        m.begin(f.calc_center_median())
        vs = []
        for v in f.verts:
            if v.index not in cache:
                tv = t(v.co) if callable(t) else t
                cache[v.index] = m.v(v.co.copy(), tv)
            vs.append(cache[v.index])
        m.f(vs, smooth)
    b.lod = saved
    bm.free()


def blob(b, mat, center, radii, rnd, sides=5, rings=2, t=0.5, rough=0.25, axis=None, lod=1, smooth=True, squash_bottom=0.5):
    """A cheap lumpy lump (charcoal, a seed pod, a small chunk): a squashed rough dome of `sides` x `rings`, bottom
    open. Radii are (x, y, z) half sizes; `axis` (a direction) turns its z that way."""
    ax = Vector(axis).normalized() if axis is not None else UP
    _, u, v = ks.basis(ax)
    saved = b.lod
    b.lod = lod
    m = b.mesh(mat)
    c = Vector(center)
    m.begin(c)
    ph = rnd.uniform(0, TAU)
    rowsv = []
    for r in range(rings):
        th = (r + 0.5) / (rings + 0.5) * math.pi * 0.5  # from the pole down toward the equator
        row = []
        for k in range(sides):
            a = ph + k / sides * TAU
            j = 1.0 + rough * rnd.uniform(-1.0, 1.0)
            ca, sa = math.cos(a), math.sin(a)
            p = (u * (ca * math.sin(th) * radii[0]) + v * (sa * math.sin(th) * radii[1]) + ax * (math.cos(th) * radii[2])) * j
            row.append(m.v(c + p, t))
        rowsv.append(row)
    top = m.v(c + ax * (radii[2] * (1.0 + rough * rnd.uniform(-0.5, 0.5))), t)
    # bottom ring at the equator, pushed in a touch
    row = []
    for k in range(sides):
        a = ph + k / sides * TAU
        j = 1.0 + rough * rnd.uniform(-1.0, 1.0)
        p = (u * math.cos(a) * radii[0] + v * math.sin(a) * radii[1]) * j
        row.append(m.v(c + p - ax * radii[2] * squash_bottom * 0.2, t))
    rowsv.append(row)
    for k in range(sides):
        k1 = (k + 1) % sides
        m.f((top, rowsv[0][k], rowsv[0][k1]), smooth)
    for A, B in zip(rowsv, rowsv[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            m.f((A[k], B[k], B[k1], A[k1]), smooth)
    b.lod = saved


def spike(b, mat, base, d, length, r, sides=3, bend=None, lod=1, t0=0.0, t1=1.0):
    """A thin spike (needle ice, a thorn, a splinter), tapering to a point; sides=3 is 3 triangles."""
    base = Vector(base)
    d = Vector(d).normalized()
    saved = b.lod
    b.lod = lod
    if bend is None:
        ks.tube(b, mat, [base, base + d * length], [r, 0.0], sides=sides, cap=False, t0=t0, t1=t1)
    else:
        mid = base + d * length * 0.5 + Vector(bend) * length
        tip = base + d * length + Vector(bend) * length * 1.6
        ks.tube(b, mat, [base, mid, tip], [r, r * 0.6, 0.0], sides=sides, cap=False, t0=t0, t1=t1)
    b.lod = saved


def needles(b, mat, rnd, R, count, hf=None, length=(0.03, 0.055), width=0.0016, lod=1, center=(0.0, 0.0), lift=0.0015,
            inset=0.97, keep=None, t=0.6):
    """Fallen needles, twigs-in-miniature, husks: `count` thin strips lying on the height-field `hf` inside outline R
    (2 triangles each)."""
    saved = b.lod
    b.lod = lod
    m = b.mesh(mat)
    n = 0
    tries = 0
    while n < count and tries < count * 30:
        tries += 1
        a = rnd.uniform(0.0, TAU)
        r = math.sqrt(rnd.random()) * R(a) * inset
        x, y = center[0] + r * math.cos(a), center[1] + r * math.sin(a)
        if keep is not None and not keep(x, y):
            continue
        h = rnd.uniform(0.0, TAU)
        L = rnd.uniform(*length)
        d = Vector((math.cos(h), math.sin(h), 0.0))
        s = Vector((-d.y, d.x, 0.0)) * width
        p0 = Vector((x, y, 0.0)) - d * L * 0.5
        p1 = Vector((x, y, 0.0)) + d * L * 0.5
        z0 = G + lift + (hf(p0.x, p0.y) if hf else 0.0)
        z1 = G + lift + (hf(p1.x, p1.y) if hf else 0.0) + rnd.uniform(0.0, 0.003)
        m.begin((x, y, z0))
        v = [m.v((p0.x - s.x, p0.y - s.y, z0), t), m.v((p0.x + s.x, p0.y + s.y, z0), t),
             m.v((p1.x + s.x * 0.3, p1.y + s.y * 0.3, z1), t), m.v((p1.x - s.x * 0.3, p1.y - s.y * 0.3, z1), t)]
        _tri(m, v[0], v[1], v[2], False)
        _tri(m, v[0], v[2], v[3], False)
        n += 1
    b.lod = saved


# ---------------------------------------------------------------- generic polygon plates

def _clip(pts, nx, ny, d):
    out = []
    n = len(pts)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        sp = p[0] * nx + p[1] * ny - d
        sq = q[0] * nx + q[1] * ny - d
        if sp <= 0:
            out.append(p)
        if (sp < 0 < sq) or (sq < 0 < sp):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def shard_poly(rnd, rad, cuts=(4, 6), elong=(1.0, 1.5), jag=0.012, step=0.04, near=0.62):
    """The outline of a broken sheet: a circle cut by `cuts` random straight breaks (each `near` to 1 x rad from the
    middle), stretched by `elong`, every break then made ragged (`jag` meters, a vertex every `step`). CCW (x, y)."""
    pts = [(rad * 1.8 * math.cos(k / 28 * TAU), rad * 1.8 * math.sin(k / 28 * TAU)) for k in range(28)]
    k = rnd.randint(*cuts)
    base = rnd.uniform(0, TAU)
    for i in range(k):
        phi = base + (i + rnd.uniform(-0.32, 0.32)) / k * TAU
        pts = _clip(pts, math.cos(phi), math.sin(phi), rad * rnd.uniform(near, 1.0))
    sx = rnd.uniform(*elong)
    sy = 1.0 / math.sqrt(sx)
    sx = math.sqrt(sx)
    pts = [(x * sx, y * sy) for x, y in pts]
    out = []
    n = len(pts)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        out.append(p)
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        m = int(L / step)
        if L < 1e-4:
            continue
        nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
        for j in range(1, m + 1):
            f = j / (m + 1)
            o = rnd.uniform(-1.0, 1.0) * min(jag, L * 0.09)
            out.append((p[0] + (q[0] - p[0]) * f + nx * o, p[1] + (q[1] - p[1]) * f + ny * o))
    return out


def _oriented(m, verts, want, smooth=False):
    n = Vector()
    k = len(verts)
    for i in range(k):
        a, b = verts[i].co, verts[(i + 1) % k].co
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    if n.dot(want) < 0.0:
        verts = list(reversed(verts))
    return m.f(verts, smooth)


def plate(b, mat, side_mat, center, poly, thick, rnd, tilt=(0.0, 0.0), yaw=0.0, rings=2, warp=None, lod=2,
          bottom_mat=None, inner=0.55, t_edge=0.05):
    """A thin broken plate (ice sheet, crust, slab) with outline `poly` (x, y in its own frame), tilted about X then Y by
    `tilt` degrees and turned `yaw`, `thick` meters thick, `warp(x, y)` an optional height offset. Top = a fan (rings=1)
    or a fan and an annulus (rings=2) with t 1 in the middle to `t_edge` at the rim; a vertical skirt in `side_mat`
    (t 0); a bottom fan. Returns the world-space top rim points."""
    saved = b.lod
    b.lod = lod
    rot = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X")
           @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y"))
    c = Vector(center)
    mt, ms = b.mesh(mat), b.mesh(side_mat or mat)
    mb = b.mesh(bottom_mat or side_mat or mat)
    for mm in (mt, ms, mb):
        mm.begin(c)
    w = (lambda x, y: warp(x, y)) if warp else (lambda x, y: 0.0)

    def to_w(x, y, z):
        return c + rot @ Vector((x, y, z))

    up = rot @ Vector((0, 0, 1))
    n = len(poly)
    top_c = mt.v(to_w(0.0, 0.0, thick * 0.5 + w(0.0, 0.0)), 1.0)
    ring_in = None
    if rings >= 2:
        ring_in = [mt.v(to_w(x * inner, y * inner, thick * 0.5 + w(x * inner, y * inner)), 0.5) for x, y in poly]
    rim = [mt.v(to_w(x, y, thick * 0.5 + w(x, y)), t_edge) for x, y in poly]
    for k in range(n):
        k1 = (k + 1) % n
        if ring_in:
            _oriented(mt, [top_c, ring_in[k], ring_in[k1]], up, True)
            _oriented(mt, [ring_in[k], rim[k], rim[k1], ring_in[k1]], up, True)
        else:
            _oriented(mt, [top_c, rim[k], rim[k1]], up, True)
    topw = [v.co.copy() for v in rim]
    s_top = [ms.v(v.co.copy(), 0.0) for v in rim]
    s_bot = [ms.v(to_w(x, y, -thick * 0.5 + w(x, y)), 0.0) for x, y in poly]
    for k in range(n):
        k1 = (k + 1) % n
        mid = (s_top[k].co + s_top[k1].co) * 0.5
        out = Vector((mid.x - c.x, mid.y - c.y, 0.0))
        _oriented(ms, [s_top[k], s_top[k1], s_bot[k1], s_bot[k]], out, False)
    bc = mb.v(to_w(0.0, 0.0, -thick * 0.5 + w(0.0, 0.0)), 0.5)
    bot = [mb.v(v.co.copy(), 0.5) for v in s_bot]
    for k in range(n):
        _oriented(mb, [bc, bot[k], bot[(k + 1) % n]], -up, False)
    b.lod = saved
    return topw


# ---------------------------------------------------------------- shared materials

def frozen_ground(name, dark=(0.04, 0.032, 0.026), light=(0.1, 0.078, 0.06), pebbles=1.0, glaze=1.0, snow_reach=1.0,
                  crack_scale=8.0):
    """Frozen soil: lumps in two browns, grit and little stones frozen in, frost-crack polygons rimed along their edges,
    rime crystals frosting the lumps, a thin black ice skin in the low places (`glaze`), and snow creeping in from the rim
    (t = 0) in ragged tongues (`snow_reach`)."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    big = g.noise(12.0, detail=6.0, roughness=0.62)
    col = g.mix(g.ramp(big, 0.3, 0.72), dark, light)
    gd, gr = kf._cells(g, 190.0, kf._warped(g, 90.0, 0.002))
    stones = g.math("MULTIPLY", g.ramp(gd, 0.34, 0.2), g.ramp(gr, 0.55 - 0.1 * pebbles, 0.62 - 0.1 * pebbles))
    col = g.mix(g.math("MULTIPLY", stones, 0.8), col, g.mix(g.ramp(gr, 0.5, 1.0), (0.1, 0.09, 0.08), (0.27, 0.24, 0.21)))
    e = kf._voronoi(g, crack_scale, kf._warped(g, 22.0, 0.012, kf._warped(g, 4.0, 0.03)), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.014, 0.003)
    rime_line = g.math("MULTIPLY", g.ramp(e, 0.03, 0.012), g.ramp(g.noise(12.0, detail=4.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", rime_line, 0.7), col, (0.62, 0.7, 0.76))
    col = g.mix(crack, col, (0.012, 0.01, 0.008))
    cd, cr = kf._cells(g, 420.0)
    sparkle = g.math("MULTIPLY", g.ramp(cd, 0.34, 0.14), g.ramp(g.noise(9.0, detail=3.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", sparkle, 0.8), col, (0.78, 0.85, 0.9))
    skin = g.math("MULTIPLY", g.ramp(g.noise(6.5, detail=5.0, distortion=0.5), 0.6, 0.66), glaze)
    col = g.mix(g.math("MULTIPLY", skin, 0.75), col, (0.05, 0.07, 0.085))
    reach = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(9.0, detail=5.0, distortion=0.4), 0.5), 0.55))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(55.0, detail=3.0), 0.5), 0.12))
    snow = g.ramp(reach, 0.2 + 0.08 * snow_reach, 0.06)
    scol = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.5, 0.56, 0.64), (0.64, 0.69, 0.76))
    col = g.mix(snow, col, scol)
    rough = g.mixf(skin, 0.88, 0.18)
    rough = g.mixf(sparkle, rough, 0.4)
    rough = g.mixf(snow, rough, 0.6)
    height = g.math("ADD", g.math("MULTIPLY", big, 0.4), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, crack), 0.3))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", stones, 0.25), g.math("MULTIPLY", snow, 0.3)))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(300.0, detail=3.0), 0.1))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.97), 0.0, rough, g.bump(height, 1.0, 0.004))


def islands(b, mat, rnd, R, count, radius=(0.022, 0.055), hf=None, reach=(0.9, 1.08), cell=0.02, lod=1, seed=0.0):
    """Little ragged outliers of the patch's own material scattered round (and just over) its rim, so the outline is a
    scatter of bits rather than one clean edge. They use the patch's t gradient, so they fade into the ground the same way."""
    for k in range(count):
        a = rnd.uniform(0, TAU)
        r = R(a) * rnd.uniform(*reach)
        patch(b, mat, rnd, radius=rnd.uniform(*radius), cell=cell, height=hf, sink=0.006, seed=seed + k * 1.7,
              rough=0.45, floor=0.45, lod=lod, center=(r * math.cos(a), r * math.sin(a)), fade=0.4, t_scale=0.42)


def slab(b, mat, edge_mat, center, size, thick, rnd, yaw=0.0, curl=0.5, bow=0.15, nu=4, nv=3, jag=0.12, tilt=(0.0, 0.0),
         convex=True, lod=1, hf=None, t=0.5, rest=0.002, bottom_mat=None):
    """A curved slab lying on the ground (a flake of bark, a scrap of sheet): a nu x nv grid of size (L, W) with ragged
    edges, arched across its width by `curl` and along its length by `bow`, `thick` meters thick (top, bottom and a rim
    of faces), tilted, turned `yaw` and lowered until its lowest point rests `rest` above the ground (`hf` is the
    ground height-field). Returns the world positions of its top vertices."""
    L, W = size
    rot = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X")
           @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y"))
    sign = 1.0 if convex else -1.0
    top = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        for j in range(nv + 1):
            u = (i / nu - 0.5) * L
            v = (j / nv - 0.5) * W
            edge = i in (0, nu) or j in (0, nv)
            jj = jag if edge else jag * 0.3
            u += rnd.uniform(-1, 1) * jj * L / nu
            v += rnd.uniform(-1, 1) * jj * W / nv
            vv = v / (W * 0.5)
            uu = u / (L * 0.5)
            z = sign * (curl * W * 0.25 * (1.0 - vv * vv) + bow * L * 0.2 * (1.0 - uu * uu))
            top[i][j] = Vector((u, v, z))
    nrm = Vector((0, 0, 1))
    pts_t = [[rot @ p for p in row] for row in top]
    pts_b = [[rot @ (p - nrm * thick) for p in row] for row in top]
    lo = min(p.z for row in pts_b for p in row)
    gz = G + (hf(center[0], center[1]) if hf else 0.0) + rest
    c = Vector(center)
    shift = Vector((c.x, c.y, gz - lo))
    saved = b.lod
    b.lod = lod
    mt, me = b.mesh(mat), b.mesh(edge_mat or mat)
    mb = b.mesh(bottom_mat or edge_mat or mat)
    for mm in (mt, me, mb):
        mm.begin(shift)
    up = rot @ nrm
    vt = [[mt.v(p + shift, t) for p in row] for row in pts_t]
    vb = [[mb.v(p + shift, 0.2) for p in row] for row in pts_b]
    for i in range(nu):
        for j in range(nv):
            _oriented(mt, [vt[i][j], vt[i + 1][j], vt[i + 1][j + 1], vt[i][j + 1]], up, True)
            _oriented(mb, [vb[i][j], vb[i + 1][j], vb[i + 1][j + 1], vb[i][j + 1]], -up, True)
    ring = ([(i, 0) for i in range(nu)] + [(nu, j) for j in range(nv)] + [(i, nv) for i in range(nu, 0, -1)]
            + [(0, j) for j in range(nv, 0, -1)])
    et = {}
    eb = {}
    for (i, j) in ring:
        et[(i, j)] = me.v(pts_t[i][j] + shift, 0.0)
        eb[(i, j)] = me.v(pts_b[i][j] + shift, 0.0)
    cm = sum((pts_t[i][j] for i in range(nu + 1) for j in range(nv + 1)), Vector()) / ((nu + 1) * (nv + 1)) + shift
    for k in range(len(ring)):
        p0, p1 = ring[k], ring[(k + 1) % len(ring)]
        mid = (et[p0].co + et[p1].co) * 0.5
        out = Vector((mid.x - cm.x, mid.y - cm.y, 0.0))
        _oriented(me, [et[p0], et[p1], eb[p1], eb[p0]], out, False)
    b.lod = saved
    return [p + shift for row in pts_t for p in row]


def ash_surface(name, ripple=1.0, cracks=1.0, light=(0.5, 0.49, 0.47), dark=(0.2, 0.195, 0.19), soil=(0.04, 0.034, 0.029),
                crack_scale=6.0, specks=1.0, rim=((0.1, 0.088, 0.075), (0.2, 0.18, 0.16))):
    """Wood ash lying in drifts: soft greys, a powdery grain, crumbs and flakes of ash and charcoal, fine wind ripples
    (`ripple`) running along x in patches, dry cracks (`cracks`) showing the dark soil under it, and a ragged rim (t = 0)
    thinning to scorched soil and soot."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    drift = g.noise(7.0, detail=6.0, roughness=0.65)
    col = g.mix(g.ramp(drift, 0.22, 0.78), g.mix(0.35, dark, light), light)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(45.0, detail=4.0), 0.42, 0.75), 0.45), col, dark)
    powder = g.noise(750.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(powder, 0.6, 0.25), 0.4), col, tuple(c * 0.7 for c in dark))
    # Wind ripples: two sets of fine crests running across x, strongest in patches
    rv = kf._warped(g, 14.0, 0.006, ks._stretched(g, (16.0, 1.7, 16.0)))
    rv2 = kf._warped(g, 25.0, 0.003, ks._stretched(g, (36.0, 4.0, 36.0)))
    r1 = kf._ridged(g, g.noise(1.0, detail=2.0, roughness=0.5, vector=rv))
    r2 = kf._ridged(g, g.noise(1.0, detail=2.0, roughness=0.5, vector=rv2))
    zone = g.math("MULTIPLY", g.ramp(g.noise(3.4, detail=3.0), 0.35, 0.62), ripple)
    crest = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(r1, 0.7, 1.0), g.math("MULTIPLY", g.ramp(r2, 0.72, 1.0), 0.6)), zone)
    col = g.mix(g.math("MULTIPLY", crest, 0.55), col, tuple(min(1.0, c * 1.3) for c in light))
    trough = g.math("MULTIPLY", g.ramp(r1, 0.45, 0.1), zone)
    col = g.mix(g.math("MULTIPLY", trough, 0.35), col, tuple(c * 0.75 for c in dark))
    # Crumbs of charcoal and flakes of pale ash
    d, r = kf._cells(g, 90.0, kf._warped(g, 160.0, 0.003))
    crumb = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", d, g.math("MULTIPLY", r, 0.22)), 0.05, 0.0), g.ramp(g.noise(7.0, detail=3.0), 0.52, 0.62))
    col = g.mix(g.math("MULTIPLY", crumb, specks), col, g.mix(g.ramp(r, 0.9, 0.95), (0.014, 0.013, 0.012), (0.1, 0.05, 0.022)))
    sp = g.ramp(kf._voronoi(g, 240.0), 0.12, 0.05)
    col = g.mix(g.math("MULTIPLY", sp, 0.9 * specks), col, (0.015, 0.014, 0.013))
    fd, fr = kf._cells(g, 160.0)
    flake = g.math("MULTIPLY", g.ramp(fd, 0.16, 0.08), g.ramp(fr, 0.9, 0.93))
    col = g.mix(flake, col, tuple(min(1.0, c * 1.3) for c in light))
    # Dry cracks: the ash shrinks and splits, showing dark soil, with crumbled, raised lips
    e = kf._voronoi(g, crack_scale, kf._warped(g, 20.0, 0.01, kf._warped(g, 3.5, 0.03)), feature="DISTANCE_TO_EDGE")
    gate = g.ramp(g.noise(2.6, detail=3.0), 0.4, 0.56)
    crack = g.math("MULTIPLY", g.ramp(e, 0.06, 0.02), g.math("MULTIPLY", gate, cracks))
    lip = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(e, 0.16, 0.06), g.ramp(e, 0.015, 0.05)), g.math("MULTIPLY", gate, cracks))
    col = g.mix(g.math("MULTIPLY", crack, 0.97), col, g.mix(g.ramp(g.noise(140.0, detail=3.0), 0.3, 0.7), soil, tuple(c * 2.2 for c in soil)))
    col = g.mix(g.math("MULTIPLY", lip, 0.25), col, tuple(c * 0.55 for c in light))
    # Ragged rim: thin ash over scorched soil, soot, then the ground
    edge = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(55.0, detail=4.0), 0.5), 0.3))
    edge = g.math("ADD", edge, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(8.0, detail=4.0), 0.5), 0.25))
    soot = tuple(c * 0.8 for c in soil)
    col = g.mix(g.ramp(edge, 0.55, 0.18), col, g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), rim[0], rim[1]))
    col = g.mix(g.ramp(edge, 0.2, 0.02), col, soot)
    height = g.math("ADD", g.math("MULTIPLY", drift, 0.35), g.math("MULTIPLY", powder, 0.12))
    height = g.math("ADD", height, g.math("MULTIPLY", crest, 0.9))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", crumb, 0.45), g.math("MULTIPLY", flake, 0.2)))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.7))
    height = g.math("ADD", height, g.math("MULTIPLY", lip, 0.15))
    rough = g.mixf(crumb, 0.96, 0.7)
    rough = g.mixf(crack, rough, 0.9)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.97), 0.0, rough, g.bump(height, 1.0, 0.0042))


def burnt_rock(name):
    """A rock a fire passed over: dark grey going black, crazed with heat cracks haloed in rusty oxide, spalled flakes of
    fresher grey, soot low on it and ash settled on the tops."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    tone = g.noise(5.0, detail=5.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.05, 0.048, 0.046), (0.13, 0.125, 0.12))
    d1, r1 = kf._cells(g, 190.0, kf._warped(g, 40.0, 0.002))
    col = g.mix(g.math("MULTIPLY", g.ramp(r1, 0.6, 0.85), 0.5), col, (0.18, 0.17, 0.16))
    col = g.mix(g.math("MULTIPLY", g.ramp(r1, 0.12, 0.0), 0.7), col, (0.015, 0.015, 0.015))
    e = kf._voronoi(g, 9.0, kf._warped(g, 26.0, 0.006, kf._warped(g, 5.0, 0.03)), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.04, 0.008)
    halo = g.math("MULTIPLY", g.ramp(e, 0.12, 0.03), g.ramp(g.noise(6.0, detail=4.0), 0.4, 0.64))
    col = g.mix(g.math("MULTIPLY", halo, 0.55), col, (0.17, 0.085, 0.045))
    col = g.mix(crack, col, (0.008, 0.007, 0.006))
    spall = g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=5.0, distortion=0.4), 0.62, 0.66), g.ramp(g.noise(40.0, detail=3.0), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", spall, 0.75), col, (0.2, 0.19, 0.18))
    nz = ks._normal_z(g)
    ash = g.math("MULTIPLY", g.ramp(nz, 0.4, 0.85), g.ramp(g.noise(20.0, detail=5.0), 0.3, 0.55))
    ac, ar = kf._cells(g, 380.0)
    col = g.mix(g.math("MULTIPLY", ash, 0.85), col, g.mix(g.ramp(ac, 0.5, 0.2), (0.3, 0.29, 0.28), (0.45, 0.44, 0.42)))
    low = g.math("MULTIPLY", g.ramp(t, 0.3, 0.0), g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", low, 0.8), col, (0.02, 0.018, 0.016))
    height = g.math("ADD", g.math("MULTIPLY", r1, 0.25), g.math("MULTIPLY", g.noise(450.0, detail=2.0), 0.15))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", spall, -0.18))
    height = g.math("ADD", height, g.math("MULTIPLY", ash, 0.2))
    rough = g.mixf(ash, g.mixf(crack, 0.78, 0.95), 0.95)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=1.0), 0.0, rough, g.bump(height, 1.0, 0.006))


def rust_surface(name, paint=None, rust=1.0, flake_scale=46.0, relief=0.0036, galv=0.0):
    """Corroded sheet iron, built from noise rather than tiles: mottled dark-brown to orange rust at several scales with a
    gritty fine speckle, powdery pale blooms, irregular lifted blisters whose rims catch the light and whose lifted
    centers have scaled away to a dark under-layer with glints of steel, crazing in the rust, pits; `paint` = a faded
    paint color left in patches the rust hasn't eaten; `galv` leaves patches of dull grey galvanizing."""
    mat, g = tk.new_material(name)
    big = g.noise(4.5, detail=6.0, roughness=0.62, distortion=0.35)
    mid = g.noise(17.0, detail=7.0, roughness=0.65)
    fine = g.noise(210.0 * flake_scale / 46.0, detail=4.0, roughness=0.7)
    grit = g.noise(620.0, detail=2.0)
    col = g.mix(g.ramp(mid, 0.3, 0.7), (0.075, 0.04, 0.028), (0.22, 0.1, 0.05))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.math("ADD", big, g.math("MULTIPLY", g.math("SUBTRACT", fine, 0.5), 0.5)), 0.5, 0.7), 0.8), col, (0.34, 0.15, 0.06))
    bloom = g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=5.0, distortion=0.5), 0.6, 0.72), g.ramp(fine, 0.4, 0.7))
    col = g.mix(g.math("MULTIPLY", bloom, 0.65), col, (0.46, 0.27, 0.11))
    col = g.mix(g.math("MULTIPLY", g.ramp(grit, 0.6, 0.85), 0.35), col, (0.3, 0.17, 0.09))
    col = g.mix(g.math("MULTIPLY", g.ramp(grit, 0.4, 0.15), 0.45), col, (0.02, 0.013, 0.01))
    # Blisters of lifted rust: irregular blobs, a light rim, a scaled-away dark middle with steel glinting
    bn = g.math("ADD", g.noise(9.0, detail=6.0, roughness=0.6, distortion=0.45), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(70.0, detail=3.0), 0.5), 0.08))
    lifted = g.ramp(bn, 0.6, 0.615)
    rim = g.math("MULTIPLY", g.ramp(bn, 0.585, 0.6), g.math("SUBTRACT", 1.0, lifted))
    under = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.05, 0.028, 0.02), (0.12, 0.062, 0.04))
    bare = g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=4.0), 0.62, 0.74), lifted)
    under = g.mix(g.math("MULTIPLY", bare, 0.75), under, (0.24, 0.23, 0.22))
    col = g.mix(g.math("MULTIPLY", rim, 0.6), col, (0.52, 0.28, 0.1))
    col = g.mix(lifted, col, under)
    # Fine crazing in the rust skin
    craze = g.ramp(kf._voronoi(g, 95.0, kf._warped(g, 150.0, 0.004, kf._warped(g, 12.0, 0.015)), feature="DISTANCE_TO_EDGE"), 0.06, 0.0)
    craze = g.math("MULTIPLY", g.math("MULTIPLY", craze, g.ramp(g.noise(6.0, detail=3.0), 0.4, 0.6)), g.math("SUBTRACT", 1.0, lifted))
    col = g.mix(g.math("MULTIPLY", craze, 0.7), col, (0.03, 0.017, 0.012))
    # Faded paint or galvanizing where the rust hasn't got to
    keep = g.ramp(g.noise(4.2, detail=6.0, distortion=0.5), 0.52 + 0.2 * rust, 0.58 + 0.2 * rust)
    if paint is not None:
        pt = g.mix(g.ramp(g.noise(22.0, detail=4.0), 0.3, 0.7), paint, tuple(c * 0.7 for c in paint))
        pt = g.mix(g.math("MULTIPLY", g.ramp(g.noise(160.0, detail=3.0), 0.55, 0.8), 0.4), pt, (0.3, 0.3, 0.28))
        pm = g.math("MULTIPLY", keep, g.math("SUBTRACT", 1.0, lifted))
        col = g.mix(g.math("MULTIPLY", pm, 0.95), col, pt)
    if galv > 0.0:
        gm = g.math("MULTIPLY", g.math("MULTIPLY", keep, galv), g.math("SUBTRACT", 1.0, lifted))
        gcol = g.mix(g.ramp(g.noise(9.0, detail=4.0), 0.3, 0.7), (0.2, 0.205, 0.205), (0.32, 0.32, 0.31))
        col = g.mix(gm, col, gcol)
    # Dust in the hollows, pits
    dust = g.math("MULTIPLY", g.ramp(bn, 0.7, 0.62), g.ramp(g.noise(10.0, detail=4.0), 0.45, 0.68))
    col = g.mix(g.math("MULTIPLY", dust, 0.3), col, (0.3, 0.22, 0.14))
    pit = g.ramp(kf._voronoi(g, 380.0), 0.14, 0.06)
    col = g.mix(g.math("MULTIPLY", pit, 0.7), col, (0.025, 0.017, 0.013))
    height = g.math("ADD", g.math("MULTIPLY", mid, 0.35), g.math("MULTIPLY", g.math("SUBTRACT", fine, 0.3), 0.35))
    height = g.math("ADD", height, g.math("MULTIPLY", rim, 0.35))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", lifted, 0.55))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", craze, 0.25))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pit, 0.25))
    height = g.math("ADD", height, g.math("MULTIPLY", grit, 0.15))
    metal = g.math("MULTIPLY", bare, 0.85)
    rough = g.mixf(bare, g.math("ADD", 0.72, g.math("MULTIPLY", g.noise(40.0), 0.2)), 0.38)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), metal, rough, g.bump(height, 1.0, relief))


def rust_flake(name):
    """Loose flakes of rust: a palette picked by t (orange, brown, near-black, a pale powdery one), mottled, crazed with
    fine cracks, brighter at the lifted edges, a dark underside showing."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    pal = g.mix(g.ramp(t, 0.5, 0.52), g.mix(g.ramp(t, 0.25, 0.27), (0.4, 0.17, 0.065), (0.22, 0.1, 0.05)),
                g.mix(g.ramp(t, 0.75, 0.77), (0.08, 0.045, 0.03), (0.5, 0.28, 0.11)))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=5.0), 0.35, 0.7), 0.5), pal, tuple(c * 0.55 for c in (0.4, 0.17, 0.065)))
    e = kf._voronoi(g, 130.0, kf._warped(g, 80.0, 0.0015), feature="DISTANCE_TO_EDGE")
    col = g.mix(g.math("MULTIPLY", g.ramp(e, 0.1, 0.0), 0.85), col, (0.02, 0.012, 0.009))
    d, r = kf._cells(g, 300.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(d, 0.3, 0.1), 0.35), col, (0.55, 0.3, 0.12))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(e, 0.0, 0.1), 0.5), g.math("MULTIPLY", g.noise(260.0, detail=3.0), 0.3))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.98), 0.0, 0.9, g.bump(height, 1.0, 0.0014))


def char_surface(name, ash_amount=0.4, scale=1.0, brown=0.5):
    """Burnt wood as a surface (bark flakes, wood chunks, charcoal lumps): near-black blocks of every size crazed with
    thin fissures (alligator skin), each block a low dome with its own shade and a dull silver grain, brown unburnt wood
    in the deepest splits, a few larger plates outlined by bigger cracks, ash dust settled on the faces that look up."""
    mat, g = tk.new_material(name)
    wv = kf._warped(g, 50.0 * scale, 0.0035 / scale, kf._warped(g, 7.0 * scale, 0.02 / scale))
    d, r = kf._cells(g, 80.0 * scale, wv)
    e = kf._voronoi(g, 80.0 * scale, wv, feature="DISTANCE_TO_EDGE")
    d2, r2 = kf._cells(g, 26.0 * scale, kf._warped(g, 12.0 * scale, 0.01 / scale))
    e2 = kf._voronoi(g, 26.0 * scale, kf._warped(g, 12.0 * scale, 0.01 / scale), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.075, 0.012)
    big = g.math("MULTIPLY", g.ramp(e2, 0.06, 0.008), g.ramp(r2, 0.2, 0.6))
    block = g.mix(g.ramp(g.noise(10.0 * scale, detail=4.0), 0.3, 0.7), (0.02, 0.018, 0.017), (0.055, 0.05, 0.045))
    block = g.mix(g.math("MULTIPLY", g.ramp(r, 0.2, 1.0), 0.6), block, (0.095, 0.088, 0.08))
    sheen = g.math("MULTIPLY", g.ramp(g.noise(260.0 * scale, detail=3.0), 0.55, 0.85), g.ramp(d, 0.7, 0.2))
    col = g.mix(g.math("MULTIPLY", sheen, 0.35), block, (0.15, 0.145, 0.14))
    col = g.mix(g.math("MULTIPLY", crack, 0.92), col, (0.005, 0.0045, 0.004))
    col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", big, g.ramp(g.noise(5.0, detail=3.0), 0.5, 0.65)), brown), col, (0.13, 0.07, 0.04))
    col = g.mix(g.math("MULTIPLY", big, 0.7), col, (0.004, 0.004, 0.004))
    nz = ks._normal_z(g)
    ash = g.math("MULTIPLY", g.ramp(nz, 0.35, 0.85), g.ramp(g.noise(15.0, detail=5.0), 0.4, 0.62))
    ac, ar = kf._cells(g, 400.0)
    ash = g.math("MULTIPLY", ash, ash_amount * 2.0)
    col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", ash, g.ramp(ac, 0.6, 0.2)), 0.85), col, (0.38, 0.37, 0.355))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(d, 0.85, 0.0), 0.55), g.math("MULTIPLY", r, 0.3))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", crack, 0.7), g.math("MULTIPLY", big, 0.5)))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(500.0, detail=2.0), 0.1))
    rough = g.mixf(sheen, 0.9, 0.6)
    rough = g.mixf(crack, rough, 0.98)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=1.0), 0.0, rough, g.bump(height, 1.0, 0.0035))


# ---------------------------------------------------------------- checks and export

def stats(script, b_pieces):
    lo, hi = kf.bounds(b_pieces)
    tris = ks.triangles(b_pieces)
    print("[%s] footprint x %.3f..%.3f y %.3f..%.3f, height above ground %.3f m, ~%d triangles" %
          (script, lo.x, hi.x, lo.y, hi.y, hi.z - G, tris))
    return lo, hi, tris


# ---------------------------------------------------------------- preview ground and shots

def _floor(kind):
    mat, g = tk.new_material("PreviewGround")
    if kind == "snow":
        col = g.mix(g.ramp(g.noise(3.0, detail=6.0), 0.35, 0.65), (0.3, 0.34, 0.41), (0.4, 0.44, 0.51))
        col = g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.5, 0.7), col, (0.5, 0.54, 0.6))
        tk.finish(mat, g, col, 0.0, 0.55, g.bump(g.noise(150.0, detail=4.0), 0.2, 0.002))
    elif kind == "burnt":
        col = g.mix(g.ramp(g.noise(4.0, detail=6.0), 0.35, 0.65), (0.05, 0.043, 0.037), (0.085, 0.076, 0.067))
        col = g.mix(g.ramp(g.noise(50.0, detail=4.0), 0.55, 0.75), col, (0.03, 0.027, 0.024))
        tk.finish(mat, g, col, 0.0, 0.92, g.bump(g.noise(180.0, detail=4.0), 0.4, 0.002))
    else:
        col = g.mix(g.ramp(g.noise(3.0, detail=6.0), 0.35, 0.65), (0.27, 0.215, 0.15), (0.34, 0.285, 0.21))
        col = g.mix(g.ramp(g.noise(55.0, detail=4.0), 0.5, 0.72), col, (0.19, 0.15, 0.105))
        tk.finish(mat, g, col, 0.0, 0.95, g.bump(g.noise(200.0, detail=4.0), 0.4, 0.002))
    return mat


def previews(script, model, out_dir, kind="snow", lod_name=None, macro=((0.16, -0.26), (0.0, 0.0)), neighbors=True,
             far_height=1.6):
    """Renders on a biome ground: stand (a player 1.1 m off, eyes 1.65 m up), crouch (0.55 m off, eyes 0.55 m up), macro
    (about 25 cm over `macro` = (camera xy, target xy)), top, far (3 m off with four neighbors) and lod (the far mesh at
    crouch distance)."""
    tk.preview_stage()
    if kind == "snow":
        bpy.data.lights["Sun"].energy = 2.4
    floor = bpy.data.objects.get("Floor")
    floor.data.materials[0] = _floor(kind)
    for n in ("ScaleFigure", "ScaleHead"):
        o = bpy.data.objects.get(n)
        if o is not None:
            o.hide_render = True

    want = os.environ.get("GC_VIEWS")
    k_samples = int(os.environ.get("GC_SAMPLES", "48"))

    def shot(name, loc, target, lens=30, samples=64, res=(1000, 750)):
        if want and name not in want.split(","):
            return
        tk.render(tk.camera(script + name, loc, target, lens=lens), os.path.join(out_dir, "%s_%s.png" % (script, name)),
                  samples=min(samples, k_samples), res=res)

    shot("stand", (0.45, -0.95, G + 1.65), (0.0, 0.0, G))
    shot("crouch", (0.4, -0.55, G + 0.5), (0.0, 0.0, G + 0.02), lens=28)
    (cx, cy), (tx, ty) = macro
    shot("macro", (cx, cy, G + 0.3), (tx, ty, G), lens=35)
    shot("top", (0.0, -0.001, G + 1.7), (0.0, 0.0, G), lens=32)
    if neighbors:
        rnd = random.Random(5)
        copies = []
        for (x, y) in ((1.0, 0.0), (-1.0, 0.2), (0.1, 1.0), (-0.1, -1.0), (1.0, 1.0), (-1.0, 1.0)):
            cpy = model.copy()
            tk.link(cpy)
            cpy.location = (x + rnd.uniform(-0.08, 0.08), y + rnd.uniform(-0.08, 0.08), 0.0)
            cpy.rotation_euler = (0.0, 0.0, rnd.uniform(0, TAU))
            copies.append(cpy)
        shot("far", (0.3, -3.0, G + far_height), (0.0, 0.1, G + 0.02), lens=35)
        for cpy in copies:
            bpy.data.objects.remove(cpy)
    else:
        shot("far", (0.3, -3.0, G + far_height), (0.0, 0.1, G + 0.02), lens=35)
    lod = bpy.data.objects.get(lod_name) if lod_name else None
    if lod is not None:
        model.hide_render = True
        lod.hide_render = False
        shot("lod", (0.4, -0.55, G + 0.5), (0.0, 0.0, G + 0.02), lens=28, samples=32)
        shot("lodfar", (0.3, -3.0, G + far_height), (0.0, 0.1, G + 0.02), lens=35, samples=32)
        model.hide_render = False
        lod.hide_render = True
