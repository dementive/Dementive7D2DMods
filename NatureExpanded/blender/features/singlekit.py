"""Shared helpers for Nature Expanded's "single find" props (SingleFinds B: BrokenCooler, ShoppingCart, RustyBucketCans,
FirewoodStack, AbandonedPack, RustedBicycle; script singles_b.py), on top of featurekit.py and logkit.py.

What is here:

- Mesh builders on bmesh: `sweep` (a closed profile loop revolved or lofted round a ring function: lathe bodies, rounded
  boxes, hollow shells, tires; the result is a closed solid), `tube_loop`, `box`, `blob` (a lumpy superellipsoid), `warp`
  and `xform`. `emit` hands a bmesh to a ks.Builder with its own smoothing groups (hard edges stay hard).
- Small plants: `blade` (a double-sided grass blade: the game culls back faces of feature materials), `tuft`, `dock`.
- Materials as node signals baked to the atlas: weathered metal in several kinds (`metal_mat`: galvanized, wire, tin,
  chrome, painted), faded plastic, rubber, leather, canvas and nylon with mould, rope, paper labels, mossy wood.
- `finish`: footprint report, export (logkit's tight UV packing) and previews at 8 m, 2.5 m and arm's length.

Conventions as featurekit: meters, Z up, the master cell's center at the origin, the ground at z = -0.5 (G).
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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G

_orig_bake = tk._bake


def _cheap_bake(obj, kind, img, samples, **kw):
    """The materials are deterministic and costly per sample: a handful of samples is plenty (AO keeps its own)."""
    if kind != "AO":
        samples = min(samples, int(os.environ.get("SB_BAKE", "6")))
    return _orig_bake(obj, kind, img, samples, **kw)


tk._bake = _cheap_bake
UP = Vector((0.0, 0.0, 1.0))


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smoothstep(a, b, x):
    t = clamp((x - a) / (b - a)) if b != a else 0.0
    return t * t * (3.0 - 2.0 * t)


def noise3(p, scale=1.0, seed=0.0):
    return mn.noise(Vector((p.x * scale + seed * 7.1, p.y * scale + seed * 3.3, p.z * scale + seed * 1.7)))


def fbm3(p, scale=1.0, seed=0.0, octaves=3):
    s, a, tot = 0.0, 1.0, 0.0
    for i in range(octaves):
        s += a * noise3(p, scale * (2.0 ** i), seed + i)
        tot += a
        a *= 0.5
    return s / tot


# ================================================================ mesh builders

def sweep(profile, ring, n):
    """A closed solid: `profile` is a closed loop of (u, z) points (u None = a pole on the axis), `ring(u, z, k, a)` gives
    the point k of n at angle a. The loop's cross-section is swept round the ring, so the mesh needs no caps."""
    bm = bmesh.new()
    rows = []
    for u, z in profile:
        if u is None:
            rows.append([bm.verts.new(ring(None, z, 0, 0.0))])
        else:
            rows.append([bm.verts.new(ring(u, z, k, k / n * math.tau)) for k in range(n)])
    P = len(rows)
    for i in range(P):
        A, B = rows[i], rows[(i + 1) % P]
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(n):
            k1 = (k + 1) % n
            try:
                if len(A) == 1:
                    bm.faces.new((A[0], B[k1], B[k]))
                elif len(B) == 1:
                    bm.faces.new((A[k], A[k1], B[0]))
                else:
                    bm.faces.new((A[k], A[k1], B[k1], B[k]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def lathe_ring(cx=0.0, cy=0.0):
    def ring(u, z, k, a):
        if u is None:
            return Vector((cx, cy, z))
        return Vector((cx + u * math.cos(a), cy + u * math.sin(a), z))
    return ring


def rrect_ring(hx, hy, p=7.0):
    """Rounded rectangle half sizes (hx, hy) shrunk by the profile's `u` (an inset in meters)."""
    e = 2.0 / p

    def ring(u, z, k, a):
        if u is None:
            return Vector((0.0, 0.0, z))
        c, s = math.cos(a), math.sin(a)
        x = math.copysign(abs(c) ** e, c) * max(hx - u, 0.002)
        y = math.copysign(abs(s) ** e, s) * max(hy - u, 0.002)
        return Vector((x, y, z))
    return ring


def tube_loop(points, radii, sides, closed=True, squash=1.0):
    """A closed solid tube along a polyline (loop if `closed`), parallel-transport frames, round caps flat."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    fr = ks.frames(pts)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        tan, nr, bn = fr[i]
        rings.append([bm.verts.new(p + (nr * math.cos(k / sides * math.tau) + bn * math.sin(k / sides * math.tau) * squash) * radii[i])
                      for k in range(sides)])
    last = n if closed else n - 1
    for i in range(last):
        A, B = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            k1 = (k + 1) % sides
            try:
                bm.faces.new((A[k], A[k1], B[k1], B[k]))
            except ValueError:
                pass
    if not closed:
        try:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm



def loft_rings(rings, tags=None, cap_tag=2):
    """A closed solid from rings of points (all with the same count, each a closed polygon, consecutive rings joined by
    quads, both ends capped). Face material_index: `tags[i]` for the quads along polygon edge i, `cap_tag` for the caps."""
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(vr[0])
    for j in range(len(vr) - 1):
        for i in range(n):
            i1 = (i + 1) % n
            try:
                f = bm.faces.new((vr[j][i], vr[j][i1], vr[j + 1][i1], vr[j + 1][i]))
                f.material_index = tags[i] if tags else 0
            except ValueError:
                pass
    for ring, rev in ((vr[0], True), (vr[-1], False)):
        try:
            f = bm.faces.new(list(reversed(ring)) if rev else list(ring))
            f.material_index = cap_tag
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def box(size, center=(0.0, 0.0, 0.0), bevel=0.0, segments=1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segments, affect="EDGES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def blob(radii, seed=0, power=2.4, rough=0.06, subdiv=3, fn=None):
    """A lumpy closed superellipsoid with radii (a, b, c) centered at the origin; `fn(p)` may reshape each point."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    a, b, c = radii
    size = (a * b * c) ** (1.0 / 3.0)
    for v in bm.verts:
        u = v.co.normalized()
        s = (abs(u.x) ** power + abs(u.y) ** power + abs(u.z) ** power) ** (-1.0 / power)
        p = Vector((u.x * s * a, u.y * s * b, u.z * s * c))
        p += u * (fbm3(p, 2.4 / size, seed) * rough * size)
        v.co = fn(p) if fn else p
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def xform(bm, matrix):
    bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    return bm


def euler_matrix(rx=0.0, ry=0.0, rz=0.0, loc=(0.0, 0.0, 0.0)):
    m = Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X")
    m.translation = Vector(loc)
    return m


def warp(bm, fn):
    for v in bm.verts:
        v.co = fn(v.co.copy())
    bm.normal_update()
    return bm


def lowest(bms):
    return min(v.co.z for bm in bms for v in bm.verts)


def rest_on_ground(bm, sink=0.01):
    """Moves a bmesh down or up so its lowest point is `sink` meters below the ground."""
    dz = (G - sink) - min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, dz), verts=bm.verts)
    return dz


def body_of(bm):
    c = bm.copy()
    bmesh.ops.triangulate(c, faces=c.faces)
    out = ([v.co.copy() for v in c.verts], [tuple(v.index for v in f.verts) for f in c.faces])
    c.free()
    return out


def emit(b, bm, mat, lod=0, angle=40.0, t=0.5, mat_of=None, both=False):
    """Adds `bm` to Builder `b` in material `mat` (or `mat_of(face)` per face). Faces are smoothed within groups whose
    neighbours differ by less than `angle` degrees, so hard edges stay hard. `t(v)` or a number is the vertex attribute
    (many materials read it). `both` also adds the reversed faces (thin sheets, which the game draws one-sided)."""
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    bm.verts.index_update()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    lim = math.radians(angle)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            fa, fb = e.link_faces
            if fa.normal.angle(fb.normal, 3.0) < lim:
                parent[find(fa.index)] = find(fb.index)
    cache = {}
    saved = b.lod
    b.lod = lod
    for f in bm.faces:
        mt = mat_of(f) if mat_of else mat
        if mt is None:
            continue
        m = b.mesh(mt)
        m.begin(f.calc_center_median())
        for flip in ((False, True) if both else (False,)):
            vs = []
            for v in f.verts:
                key = (mt.name, find(f.index), v.index, flip)
                if key not in cache:
                    cache[key] = m.v(v.co.copy(), t(v) if callable(t) else t)
                vs.append(cache[key])
            if flip:
                vs.reverse()
            m.f(vs, True)
    b.lod = saved


# ================================================================ small plants (double-sided: the game culls back faces)

def blade(b, mat, base, d, length, width, bend, rnd, rows=3, fold=0.25, lod=1):
    """A grass blade (strap tapering to a tip) arching along `bend`, both faces."""
    d = Vector(d).normalized()
    side = d.cross(UP)
    if side.length < 1e-3:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    up = side.cross(d).normalized()
    bm = bmesh.new()
    rowv = []
    for i in range(rows + 1):
        s = i / rows
        c = ks.bent(base, d, length, bend, s)
        w = width * 0.5 * (1.0 - s ** 1.6) if s < 1.0 else 0.0
        w = max(w, 0.0)
        if i == rows:
            rowv.append((bm.verts.new(c),))
        else:
            rowv.append((bm.verts.new(c - side * w + up * fold * w), bm.verts.new(c), bm.verts.new(c + side * w + up * fold * w)))
    for A, B in zip(rowv, rowv[1:]):
        if len(B) == 1:
            bm.faces.new((A[0], A[1], B[0]))
            bm.faces.new((A[1], A[2], B[0]))
        else:
            bm.faces.new((A[0], A[1], B[1], B[0]))
            bm.faces.new((A[1], A[2], B[2], B[1]))
    emit(b, bm, mat, lod=lod, angle=179.0, t=lambda v: clamp(0.15 + 0.8 * (v.co - Vector(base)).length / max(length, 1e-3)), both=True)
    bm.free()


def tuft(b, mats, rnd, center, count, height, spread=0.05, width=0.02, lean=0.35, bend=(0.25, 0.7), limit=0.47):
    """A grass tuft at `center` (x, y); blades fan out and arch. `mats` is [green, dry]."""
    for i in range(count):
        a = rnd.uniform(0, math.tau)
        r = spread * math.sqrt(rnd.random())
        x, y = center[0] + r * math.cos(a), center[1] + r * math.sin(a)
        d = Vector((math.cos(a) * rnd.uniform(0.1, lean), math.sin(a) * rnd.uniform(0.1, lean), 1.0))
        h = height * rnd.uniform(0.55, 1.1)
        bd = rnd.uniform(*bend)
        # keep the blade tips inside the footprint limit
        tip = ks.bent(Vector((x, y, G)), d, h, bd, 1.0)
        while max(abs(tip.x), abs(tip.y)) > limit and h > 0.06:
            h *= 0.85
            tip = ks.bent(Vector((x, y, G)), d, h, bd, 1.0)
        mat = mats[0] if rnd.random() < 0.55 else mats[1]
        blade(b, mat, Vector((x, y, G - 0.01)), d, h, width * rnd.uniform(0.8, 1.3), bd, rnd, lod=(1 if i % 2 else 0))


def dock(b, mat, rnd, center, leaves=6, length=0.22, width=0.075, limit=0.47, lift=0.5):
    """A rosette of broad leaves (dock or plantain) lying out and up."""
    cz = center[2] if len(center) > 2 else G - 0.005
    c3 = Vector((center[0], center[1], cz))
    for i in range(leaves):
        a = i / leaves * math.tau + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), lift * rnd.uniform(0.5, 1.2)))
        ln = length * rnd.uniform(0.7, 1.15)
        tip = c3 + d.normalized() * ln
        while max(abs(tip.x), abs(tip.y)) > limit and ln > 0.06:
            ln *= 0.85
            tip = c3 + d.normalized() * ln
        base = c3.copy()
        bm = bmesh.new()
        dn = d.normalized()
        side = dn.cross(UP).normalized()
        upv = side.cross(dn).normalized()
        rowsv = []
        N = 4
        for k in range(N + 1):
            s = k / N
            c = ks.bent(base, dn, ln, rnd.uniform(0.5, 1.1), s)
            w = width * 0.5 * (math.sin(math.pi * min(0.999, s)) ** 0.7)
            if k == N:
                rowsv.append((bm.verts.new(c),))
            else:
                rowsv.append((bm.verts.new(c - side * w + upv * 0.3 * w), bm.verts.new(c), bm.verts.new(c + side * w + upv * 0.3 * w)))
        for A, B in zip(rowsv, rowsv[1:]):
            if len(B) == 1:
                bm.faces.new((A[0], A[1], B[0]))
                bm.faces.new((A[1], A[2], B[0]))
            else:
                bm.faces.new((A[0], A[1], B[1], B[0]))
                bm.faces.new((A[1], A[2], B[2], B[1]))
        emit(b, bm, mat, lod=0, angle=179.0, t=lambda v, base=base, ln=ln: clamp((v.co - base).length / ln), both=True)
        bm.free()


# ================================================================ material helpers

SOIL_DARK = (0.03, 0.022, 0.015)


def _ground_dirt(g, col, rough, reach=0.14, amount=0.8):
    """Soil splashed and settled low on a thing that lies on the ground (the ground is z = G)."""
    z = g.separate(g.coords())[2]
    low = g.ramp(z, G + reach, G - 0.01)
    mask = g.math("MULTIPLY", low, g.ramp(g.noise(9.0, detail=5.0), 0.2, 0.65))
    mask = g.math("MULTIPLY", mask, amount, clamp=True)
    dirt = g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), (0.035, 0.026, 0.017), (0.075, 0.056, 0.036))
    return g.mix(mask, col, dirt), g.mixf(mask, rough, 0.95), mask


def _cav_dirt(g, col, rough, amount=0.8, dist=0.05):
    cav = g.ramp(g.cavity(dist), 0.35, 1.0)
    mask = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), amount, clamp=True)
    mask = g.math("MULTIPLY", mask, g.ramp(g.noise(7.0, detail=4.0), 0.2, 0.6))
    return g.mix(mask, col, (0.03, 0.024, 0.018)), g.mixf(mask, rough, 0.9), mask


def _stretched_noise(g, sx, sy, sz, detail=4.0):
    return g.noise(1.0, detail=detail, vector=ks._stretched(g, (sx, sy, sz)))


def rust_color(g, scale=1.0):
    """Rust as it looks up close: dark and bright red-brown granules, orange blooms, black pits. Returns (color, height)."""
    d1, r1 = kf._cells(g, 330.0 * scale, kf._warped(g, 90.0, 0.003))
    d2, r2 = kf._cells(g, 70.0 * scale, kf._warped(g, 30.0, 0.008))
    tone = g.noise(26.0 * scale, detail=5.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.05, 0.024, 0.013), (0.125, 0.055, 0.026))
    col = g.mix(g.math("MULTIPLY", g.ramp(r2, 0.55, 0.95), 0.5), col, (0.19, 0.085, 0.036))
    col = g.mix(g.math("MULTIPLY", g.ramp(r1, 0.7, 0.98), 0.45), col, (0.23, 0.11, 0.046))
    col = g.mix(g.math("MULTIPLY", g.ramp(d1, 0.5, 0.12), 0.45), col, (0.022, 0.012, 0.007))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(8.0 * scale, detail=4.0), 0.62, 0.76), 0.4), col, (0.24, 0.16, 0.07))
    height = g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(d1, 0.0, 0.5)), 0.5),
                    g.math("MULTIPLY", g.ramp(d2, 0.6, 0.1), 0.4))
    return col, height


def rust_cover(g, amount, scale=1.0, low=0.5, edge=0.4, streak=0.5, seams=None):
    """A 0..1 mask of how rusted each spot is: blotches, more low down and along edges, long streaks running down."""
    co = g.coords()
    z = g.separate(co)[2]
    n = g.math("ADD", g.noise(3.2 * scale, detail=6.0, distortion=0.5),
               g.math("MULTIPLY", g.math("SUBTRACT", g.noise(33.0 * scale, detail=4.0), 0.5), 0.2))
    st = _stretched_noise(g, 7.0 * scale, 7.0 * scale, 0.7 * scale, 4.0)
    s = g.math("MULTIPLY", g.ramp(st, 0.5, 0.72), g.ramp(g.noise(2.0 * scale, detail=3.0), 0.35, 0.65))
    lowz = g.ramp(z, G + 0.45, G - 0.02)
    tot = g.math("ADD", n, g.math("MULTIPLY", lowz, 0.35 * low * 2.0))
    tot = g.math("ADD", tot, g.math("MULTIPLY", s, streak * 0.45))
    if seams is not None:
        tot = g.math("ADD", tot, g.math("MULTIPLY", seams, 0.5))
    lo = 1.0 - 0.55 * amount
    return g.ramp(tot, lo, lo + 0.12)


def metal_surface(g, kind="galv", rust=0.5, paint=None, paint2=None, flake=0.5, white=0.4, scale=1.0, base=None):
    """Weathered steel as node signals (color, metallic, roughness, height).
    kinds: galv (spangled zinc, white corrosion, rust blooms), wire (zinc-plated wire rusted nearly through), tin (a tin
    can's dull grey-blue steel), chrome (rusted chrome rim), paint (faded paint flaking to rust: `paint`, `paint2`)."""
    co = g.coords()
    z = g.separate(co)[2]
    sp_d, sp_r = kf._cells(g, 90.0 * scale, kf._warped(g, 30.0, 0.004))
    tone = g.noise(5.0 * scale, detail=4.0)
    fine = g.noise(500.0, detail=2.0)
    if kind == "galv":
        lo, hi = (0.15, 0.155, 0.16), (0.3, 0.305, 0.31)
        col = g.mix(g.ramp(sp_r, 0.0, 1.0), lo, hi)
        col = g.mix(g.math("MULTIPLY", g.ramp(sp_d, 0.55, 0.9), 0.25), col, (0.09, 0.09, 0.095))
        col = g.mix(g.ramp(tone, 0.3, 0.7), tuple(c * 0.8 for c in (0.2, 0.2, 0.2)), col)
        metal = 0.55
        rough = g.mixf(g.ramp(sp_r, 0.2, 0.9), 0.62, 0.42)
    elif kind == "wire":
        lo, hi = (0.08, 0.082, 0.085), (0.17, 0.172, 0.175)
        col = g.mix(g.ramp(sp_r, 0.0, 1.0), lo, hi)
        col = g.mix(g.math("MULTIPLY", g.ramp(tone, 0.4, 0.8), 0.5), col, (0.07, 0.07, 0.075))
        metal = 0.5
        rough = 0.55
    elif kind == "tin":
        lo, hi = (0.17, 0.18, 0.19), (0.31, 0.32, 0.33)
        col = g.mix(g.ramp(tone, 0.3, 0.7), lo, hi)
        col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.55, 0.85), 0.25), col, (0.1, 0.1, 0.105))
        metal = 0.55
        rough = 0.5
    elif kind == "chrome":
        col = g.mix(g.ramp(tone, 0.3, 0.7), (0.26, 0.265, 0.27), (0.46, 0.46, 0.47))
        col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.55, 0.85), 0.3), col, (0.14, 0.14, 0.145))
        metal = 0.8
        rough = 0.38
    else:
        col = g.rgb(base or (0.2, 0.2, 0.2))
        metal = 0.4
        rough = 0.6
    height = g.math("ADD", g.math("MULTIPLY", g.noise(240.0, detail=3.0), 0.18), g.math("MULTIPLY", sp_d, 0.1))
    # white corrosion (zinc oxide) and dusty bloom
    if white > 0.0 and kind in ("galv", "wire", "tin"):
        wm = g.math("MULTIPLY", g.ramp(g.noise(4.5 * scale, detail=6.0, distortion=0.4), 0.58, 0.75), white)
        wm = g.math("MULTIPLY", wm, g.ramp(g.noise(120.0, detail=3.0), 0.25, 0.6))
        col = g.mix(wm, col, g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), (0.42, 0.41, 0.37), (0.55, 0.54, 0.5)))
        rough = g.mixf(wm, rough, 0.92)
        metal = g.mixf(wm, metal, 0.0)
    # paint over the metal, faded and chalky, flaking away
    pm = None
    if paint is not None:
        p2 = paint2 or tuple(c * 1.7 for c in paint)
        pcol = g.mix(g.ramp(g.noise(7.0, detail=4.0), 0.3, 0.75), paint, p2)
        chalk = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0), 0.4, 0.8), 0.4)
        pcol = g.mix(chalk, pcol, tuple(min(1.0, c * 1.5 + 0.05) for c in p2))
        pcol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(300.0, detail=3.0), 0.55, 0.8), 0.18), pcol, tuple(c * 0.6 for c in paint))
        scr = _stretched_noise(g, 90.0, 20.0, 60.0, 2.0)
        pcol = g.mix(g.math("MULTIPLY", g.ramp(scr, 0.66, 0.8), 0.35), pcol, (0.3, 0.29, 0.27))
        # flaking: big irregular patches, edges first, crazed rim around each flake
        fl = g.math("ADD", g.noise(4.0 * scale, detail=7.0, distortion=0.6), g.math("MULTIPLY", g.ramp(g.noise(45.0, detail=3.0), 0.5, 0.9), 0.3 * flake))
        fl = g.math("ADD", fl, g.math("MULTIPLY", g.ramp(z, G + 0.4, G), 0.25))
        t0 = 0.74 - 0.34 * flake
        gone = g.ramp(fl, t0, t0 + 0.02)
        rim = g.math("MULTIPLY", g.ramp(fl, t0 - 0.045, t0), g.math("SUBTRACT", 1.0, gone))
        pm = g.math("SUBTRACT", 1.0, gone)
        col = g.mix(pm, col, pcol)
        col = g.mix(g.math("MULTIPLY", rim, 0.7), col, tuple(c * 0.5 for c in paint))
        rough = g.mixf(pm, rough, 0.62)
        metal = g.mixf(pm, metal, 0.12)
        height = g.mixf(pm, height, g.math("ADD", 0.7, g.math("MULTIPLY", height, 0.1)))
    # rust over everything not painted over (more where the paint has gone)
    cover = rust_cover(g, rust, scale)
    if pm is not None:
        cover = g.math("MAXIMUM", g.math("MULTIPLY", cover, g.math("ADD", 0.25, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, pm), 0.75))),
                       g.math("MULTIPLY", g.math("SUBTRACT", 1.0, pm), g.ramp(g.noise(6.0, detail=5.0), 0.3, 0.55)))
    rcol, rh = rust_color(g, scale)
    col = g.mix(cover, col, rcol)
    rough = g.mixf(cover, rough, 0.88)
    metal = g.mixf(cover, metal, 0.0)
    height = g.mixf(cover, height, g.math("ADD", 0.45, g.math("MULTIPLY", rh, 0.8)))
    # grime in the cracks and soil low down
    col, rough, _ = _cav_dirt(g, col, rough, 0.9, 0.04)
    col, rough, _ = _ground_dirt(g, col, rough, 0.12, 0.8)
    return tk.grade(g, col, sat=0.95, value=0.95), metal, rough, height


def metal_mat(name, relief=0.0016, **kw):
    mat, g = tk.new_material(name)
    col, metal, rough, height = metal_surface(g, **kw)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 1.0, relief))


def plastic_surface(g, base, chalk, crack=0.5, fade=0.7, dirt=0.8, scale=1.0, band=None):
    """Molded plastic after years in the sun: colour bleached toward `chalk` in patches, matt chalky skin, dirt
    streaks, hairline cracks, scuffs, algae film and soil low down."""
    co = g.coords()
    z = g.separate(co)[2]
    n1 = g.noise(3.0 * scale, detail=5.0)
    n2 = g.noise(11.0 * scale, detail=4.0)
    col = g.mix(g.ramp(n1, 0.3, 0.7), tuple(c * 0.8 for c in base), base)
    bleach = g.math("MULTIPLY", g.math("ADD", g.ramp(g.noise(2.0 * scale, detail=3.0), 0.3, 0.7),
                                       g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.1, 0.9), 0.5)), fade * 0.6, clamp=True)
    col = g.mix(bleach, col, chalk)
    surv = None
    if band is not None:
        # a faded printed label band on the long sides (plain stripes, no lettering), peeling off in patches
        z0, z1, c1, c2 = band
        ny = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[1]
        side = g.ramp(g.math("ABSOLUTE", ny), 0.5, 0.8)
        inb = g.math("MULTIPLY", g.ramp(z, z0 - 0.002, z0 + 0.002), g.ramp(z, z1 + 0.002, z1 - 0.002))
        peel = g.ramp(g.noise(11.0, detail=5.0, distortion=0.5), 0.36, 0.5)
        peel = g.math("MULTIPLY", peel, g.ramp(g.noise(60.0, detail=3.0), 0.12, 0.3))
        band_m = g.math("MULTIPLY", inb, side)
        surv = g.math("MULTIPLY", band_m, peel)
        zm = (z0 + z1) * 0.5
        pin = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", z, zm)), 0.0105, 0.0085)
        pin = g.math("MULTIPLY", pin, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", z, zm)), 0.006, 0.0075))
        lc = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), c1, c2)
        lc = g.mix(g.math("MULTIPLY", pin, 0.8), lc, (0.3, 0.29, 0.26))
        col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", band_m, g.math("SUBTRACT", 1.0, peel)), 0.45), col, (0.12, 0.1, 0.07))
        col = g.mix(surv, col, lc)
    # moulded surface grain and scuffs
    grain = g.noise(420.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.5, 0.85), 0.14), col, tuple(c * 0.55 for c in base))
    scr = _stretched_noise(g, 80.0, 25.0, 55.0, 2.0)
    scr2 = _stretched_noise(g, 30.0, 110.0, 50.0, 2.0)
    scuff = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(scr, 0.66, 0.8), g.ramp(scr2, 0.68, 0.82)), g.ramp(g.noise(5.0, detail=3.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", scuff, 0.55), col, tuple(min(1.0, c * 1.5 + 0.05) for c in chalk))
    # crazing and cracks
    ce = kf._voronoi(g, 2.6 * scale, kf._warped(g, 2.0, 0.12, kf._warped(g, 9.0, 0.035)), feature="DISTANCE_TO_EDGE")
    cr = g.math("MULTIPLY", g.ramp(ce, 0.0075, 0.0), g.ramp(g.noise(2.2 * scale, detail=3.0), 0.5, 0.64))
    cr = g.math("MULTIPLY", cr, crack)
    craze = g.math("MULTIPLY", g.ramp(kf._voronoi(g, 34.0 * scale, kf._warped(g, 15.0, 0.01), feature="DISTANCE_TO_EDGE"), 0.012, 0.0),
                   g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=3.0), 0.55, 0.7), crack * 0.6))
    col = g.mix(g.math("MAXIMUM", cr, g.math("MULTIPLY", craze, 0.5)), col, (0.012, 0.011, 0.009))
    # streaks of dirt running down, algae film
    st = _stretched_noise(g, 9.0 * scale, 9.0 * scale, 0.8 * scale, 4.0)
    ds = g.math("MULTIPLY", g.ramp(st, 0.45, 0.68), min(1.0, 0.6 * dirt))
    col = g.mix(ds, col, (0.06, 0.05, 0.036))
    alg = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=5.0), 0.58, 0.72), g.ramp(z, G + 0.45, G + 0.05))
    alg = g.math("MULTIPLY", alg, 0.8 * dirt)
    col = g.mix(alg, col, (0.045, 0.07, 0.03))
    rough = g.mixf(bleach, 0.5, 0.78)
    rough = g.mixf(cr, rough, 0.95)
    height = g.math("ADD", g.math("MULTIPLY", grain, 0.35), g.math("MULTIPLY", n2, 0.15))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MAXIMUM", cr, craze), 0.9))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", scuff, 0.2))
    if surv is not None:
        height = g.math("ADD", height, g.math("MULTIPLY", surv, 0.35))
        rough = g.mixf(surv, rough, 0.6)
    col, rough, _ = _cav_dirt(g, col, rough, 1.0, 0.05)
    col, rough, _ = _ground_dirt(g, col, rough, 0.2 + 0.06 * dirt, min(1.0, 0.9))
    return col, rough, height


def plastic_mat(name, base, chalk, **kw):
    mat, g = tk.new_material(name)
    col, rough, height = plastic_surface(g, base, chalk, **kw)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0012))


def rubber_mat(name, cracked=1.0, tone=(0.035, 0.035, 0.037)):
    """Old tire rubber: dark grey, dried and checked with fine cracks, dusty, a pale rim of oxidation."""
    mat, g = tk.new_material(name)
    z = g.separate(g.coords())[2]
    n = g.noise(6.0, detail=4.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), tone, tuple(c * 1.9 for c in tone))
    grain = g.noise(380.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.5, 0.85), 0.2), col, tuple(c * 0.5 for c in tone))
    ce = kf._voronoi(g, 22.0, kf._warped(g, 12.0, 0.01), feature="DISTANCE_TO_EDGE")
    ck = g.math("MULTIPLY", g.ramp(ce, 0.016, 0.0), g.ramp(g.noise(4.0, detail=3.0), 0.35, 0.6))
    ck = g.math("MULTIPLY", ck, cracked)
    col = g.mix(g.math("MULTIPLY", ck, 0.9), col, (0.008, 0.008, 0.008))
    dust = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0), 0.5, 0.75), 0.3)
    col = g.mix(dust, col, (0.09, 0.08, 0.065))
    col, rough, _ = _ground_dirt(g, col, 0.9, 0.2, 0.9)
    col, rough, _ = _cav_dirt(g, col, rough, 0.7, 0.04)
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", grain, 0.3), 0.5), g.math("MULTIPLY", ck, 0.8))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, g.mixf(dust, 0.82, 0.95), g.bump(height, 1.0, 0.0015))


def leather_mat(name, tone=(0.07, 0.04, 0.022)):
    """A cracked, dried, grey-brown saddle cover: crazed cells, scuffed edges, dirt in the cracks."""
    mat, g = tk.new_material(name)
    n = g.noise(5.0, detail=4.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), tone, tuple(c * 1.8 for c in tone))
    ce = kf._voronoi(g, 40.0, kf._warped(g, 20.0, 0.006), feature="DISTANCE_TO_EDGE")
    big = kf._voronoi(g, 7.0, kf._warped(g, 6.0, 0.02), feature="DISTANCE_TO_EDGE")
    crack = g.math("MAXIMUM", g.ramp(ce, 0.01, 0.0), g.math("MULTIPLY", g.ramp(big, 0.02, 0.0), 1.0))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, (0.012, 0.009, 0.007))
    worn = g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=5.0), 0.58, 0.72), 0.7)
    col = g.mix(worn, col, g.mix(g.ramp(g.noise(80.0), 0.3, 0.7), (0.17, 0.15, 0.12), (0.26, 0.23, 0.19)))
    col, rough, _ = _ground_dirt(g, col, 0.8, 0.2, 0.8)
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", g.noise(300.0, detail=3.0), 0.2), 0.6), g.math("MULTIPLY", crack, 0.8))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, g.mixf(worn, 0.7, 0.9), g.bump(height, 1.0, 0.0018))


def fabric_surface(g, lo, hi, weave=330.0, mould=0.7, dirt=0.7, tears=(), thread_stretch=True, quilt=None, ground=0.12):
    """Woven cloth gone to ruin: a coarse weave (checker cells with thread-noise), faded mottling, tide-marked stains,
    black and white and green mould in the folds and low down, soil, rust bleed. Returns (color, roughness, height)."""
    co = g.coords()
    z = g.separate(co)[2]
    ck = g.node("ShaderNodeTexChecker")
    g._in(ck, "Scale", weave)
    g.links.new(co, ck.inputs["Vector"])
    chk = tk._sock(ck.outputs, "Fac")
    thr = g.noise(1.0, detail=2.0, vector=ks._stretched(g, (weave * 0.55, weave * 0.55, weave * 0.55)))
    fib = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (weave * 2.5, weave * 2.5, weave * 2.5)))
    tone = g.noise(4.0, detail=5.0)
    col = g.mix(g.ramp(tone, 0.25, 0.75), lo, hi)
    col = g.mix(g.math("MULTIPLY", chk, 0.1), col, tuple(c * 0.8 for c in lo))
    col = g.mix(g.math("MULTIPLY", g.ramp(thr, 0.35, 0.8), 0.28), col, tuple(c * 0.62 for c in lo))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.85), 0.16), col, tuple(min(1.0, c * 1.5) for c in hi))
    # faded patches (sun side) and stains with tide marks
    fade = g.math("MULTIPLY", g.ramp(g.noise(2.4, detail=4.0), 0.5, 0.78), 0.55)
    col = g.mix(fade, col, tuple(min(1.0, c * 1.55 + 0.03) for c in hi))
    sn = g.noise(5.0, detail=6.0, distortion=0.5)
    stain = g.ramp(sn, 0.56, 0.58)
    tide = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", sn, 0.575)), 0.02, 0.0), 1.0)
    col = g.mix(g.math("MULTIPLY", stain, 0.35 * dirt), col, (0.045, 0.035, 0.025))
    col = g.mix(g.math("MULTIPLY", tide, 0.5 * dirt), col, (0.035, 0.026, 0.018))
    # mould: black speckle and bloom, grey-white fur, a green tint, thickest low down and in folds
    cavm = g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.05), 0.3, 1.0), clamp=True)
    lowz = g.ramp(z, G + 0.35, G + 0.0)
    mreach = g.math("ADD", g.noise(7.0, detail=6.0, distortion=0.4), g.math("MULTIPLY", g.math("ADD", lowz, cavm), 0.35))
    mm = g.ramp(mreach, 0.78 - 0.25 * mould, 0.86 - 0.25 * mould)
    d1, r1 = kf._cells(g, 90.0, kf._warped(g, 45.0, 0.004))
    spots = g.math("MULTIPLY", g.ramp(d1, 0.6, 0.15), g.ramp(g.noise(10.0, detail=3.0), 0.4, 0.6))
    black = g.math("MULTIPLY", g.math("MAXIMUM", mm, g.math("MULTIPLY", spots, 0.3 * mould)), 0.7 * mould, clamp=True)
    col = g.mix(black, col, g.mix(g.ramp(r1, 0.2, 0.9), (0.012, 0.014, 0.011), (0.035, 0.045, 0.028)))
    fur = g.math("MULTIPLY", g.ramp(g.noise(16.0, detail=6.0, distortion=0.3), 0.6, 0.72), g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.65))
    fur = g.math("MULTIPLY", fur, g.math("ADD", 0.2, g.math("MULTIPLY", g.math("ADD", lowz, cavm), 0.6)))
    fur = g.math("MULTIPLY", fur, 0.75 * mould, clamp=True)
    col = g.mix(fur, col, g.mix(g.ramp(g.noise(50.0, detail=3.0), 0.3, 0.7), (0.34, 0.35, 0.31), (0.2, 0.24, 0.16)))
    hole_all = None
    for (tx, ty, tz, tr) in tears:
        vd = g.node("ShaderNodeVectorMath", operation="DISTANCE")
        g.links.new(co, vd.inputs[0])
        vd.inputs[1].default_value = (tx, ty, tz)
        d = g.math("ADD", tk._sock(vd.outputs, "Value"), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(55.0, detail=4.0), 0.5), tr * 0.7))
        hole = g.ramp(d, tr, tr * 0.8)
        rim = g.math("MULTIPLY", g.ramp(d, tr * 1.3, tr), g.math("SUBTRACT", 1.0, hole))
        col = g.mix(g.math("MULTIPLY", rim, 0.8), col, g.mix(g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.7), (0.17, 0.15, 0.1), (0.07, 0.06, 0.04)))
        col = g.mix(hole, col, g.mix(g.ramp(g.noise(80.0, detail=3.0), 0.3, 0.7), (0.008, 0.008, 0.007), (0.03, 0.026, 0.02)))
        hole_all = hole if hole_all is None else g.math("MAXIMUM", hole_all, hole)
    if quilt is not None:
        col = quilt(col)
    rough = g.mixf(fur, 0.9, 0.97)
    height = g.math("ADD", g.math("MULTIPLY", chk, 0.4), g.math("MULTIPLY", thr, 0.45))
    height = g.math("ADD", height, g.math("MULTIPLY", fur, 0.5))
    if hole_all is not None:
        height = g.mixf(hole_all, height, 0.1)
    col, rough, _ = _ground_dirt(g, col, rough, ground + 0.05, 0.95)
    return col, rough, height


def fabric_mat(name, lo, hi, relief=0.0014, weave=330.0, **kw):
    mat, g = tk.new_material(name)
    col, rough, height = fabric_surface(g, lo, hi, weave, **kw)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def rope_mat(name, tone=(0.2, 0.16, 0.1)):
    """Old hemp or sisal rope: pale fibre in dark furrows, fuzzed, grey with age, dirt."""
    mat, g = tk.new_material(name)
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (500.0, 500.0, 500.0)))
    n = g.noise(14.0, detail=4.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), tuple(c * 0.55 for c in tone), tone)
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.85), 0.35), col, tuple(min(1.0, c * 1.5 + 0.04) for c in tone))
    d1, r1 = kf._cells(g, 160.0, kf._warped(g, 60.0, 0.004))
    col = g.mix(g.math("MULTIPLY", g.ramp(d1, 0.6, 0.25), 0.4), col, tuple(c * 0.35 for c in tone))
    grey = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.4, 0.7), 0.5)
    col = g.mix(grey, col, (0.16, 0.15, 0.13))
    col, rough, _ = _ground_dirt(g, col, 0.95, 0.15, 0.9)
    col, rough, _ = _cav_dirt(g, col, rough, 0.9, 0.03)
    height = g.math("ADD", g.math("MULTIPLY", fib, 0.5), g.math("SUBTRACT", 1.0, g.ramp(d1, 0.0, 0.6)))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0012))


def webbing_mat(name, tone=(0.06, 0.07, 0.045)):
    mat, g = tk.new_material(name)
    col, rough, height = fabric_surface(g, tuple(c * 0.8 for c in tone), tuple(c * 1.5 for c in tone), weave=420.0, mould=0.6)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0012))


def wood_surface(g, style="forest", moss_low=0.0, peel=0.6, bs=1.0, sat=1.0, value=1.0):
    """lk.bark_surface plus moss and damp-green algae creeping up from the ground (`moss_low` 0..1.5)."""
    col, height, rough = lk.bark_surface(g, style=style, moss=0.0, bs=bs, peel=peel, ground=True)
    if moss_low > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        z = g.separate(g.coords())[2]
        reach = g.math("ADD", g.noise(5.0, detail=5.0), g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.35))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.ramp(z, G + 0.3 * moss_low, G), 0.4))
        cover = g.ramp(reach, 0.7, 0.8)
        col = g.mix(cover, col, lk.moss_var(g, mcol))
        height = g.mixf(cover, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.5)))
        rough = g.mixf(cover, rough, mrough)
    if sat != 1.0 or value != 1.0:
        col = tk.grade(g, col, sat=sat, value=value)
    return col, height, rough


def wood_mat(name, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = wood_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, lk.RELIEF))


def label_mat(name, color, color2, tear=1.0):
    """A faded paper or plastic label: a printed field in two colours with plain stripes (no lettering), sun-bleached,
    stained, scuffed, blotched with rust bleeding through. Torn edges are cut in the geometry."""
    mat, g = tk.new_material(name)
    co = g.coords()
    z = g.separate(co)[2]
    n = g.noise(7.0, detail=4.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), color, color2)
    stripe = g.ramp(g.math("SINE", g.math("MULTIPLY", z, 260.0)), 0.7, 0.8)
    col = g.mix(g.math("MULTIPLY", stripe, 0.3), col, tuple(min(1.0, c * 1.5 + 0.1) for c in color2))
    bleach = g.math("MULTIPLY", g.ramp(g.noise(2.5, detail=4.0), 0.4, 0.75), 0.55)
    col = g.mix(bleach, col, (0.36, 0.34, 0.3))
    fib = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (300.0, 300.0, 300.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.85), 0.2), col, (0.2, 0.19, 0.17))
    rb = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=6.0, distortion=0.5), 0.55, 0.68), 0.75)
    col = g.mix(rb, col, (0.12, 0.05, 0.022))
    mold = g.math("MULTIPLY", g.ramp(g.noise(12.0, detail=5.0), 0.58, 0.7), 0.6)
    col = g.mix(mold, col, (0.03, 0.035, 0.026))
    col, rough, _ = _ground_dirt(g, col, 0.9, 0.12, 0.8)
    col, rough, _ = _cav_dirt(g, col, rough, 0.6, 0.03)
    height = g.math("ADD", g.math("MULTIPLY", fib, 0.4), g.math("MULTIPLY", rb, 0.3))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.001))


def dead_leaf_mats():
    return [nk.plant("LeafBrown", (0.16, 0.09, 0.04), (0.1, 0.06, 0.03), vary=0.4),
            nk.plant("LeafGold", (0.26, 0.15, 0.05), (0.17, 0.09, 0.03), vary=0.4)]


def grass_mats():
    return [nk.plant("GrassGreen", (0.1, 0.19, 0.045), (0.16, 0.23, 0.06), rough=0.7, vary=0.3),
            nk.plant("GrassDry", (0.26, 0.21, 0.09), (0.17, 0.13, 0.05), rough=0.8, vary=0.3)]


# ================================================================ rope and misc geometry

def helix_rope(b, mat, pts, radius, rnd, strands=3, pitch=0.04, sides=3, lod=2, per_pitch=5):
    """Rope along polyline `pts` (a smooth path): `strands` twisted strands of a closed solid each."""
    pts = [Vector(p) for p in pts]
    # resample the polyline at an even spacing
    seg = []
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    total = acc[-1]
    n = max(4, int(total / (pitch / per_pitch)))
    path = []
    j = 0
    for i in range(n + 1):
        s = total * i / n
        while j < len(pts) - 2 and acc[j + 1] < s:
            j += 1
        f = (s - acc[j]) / max(1e-9, acc[j + 1] - acc[j])
        path.append(pts[j].lerp(pts[j + 1], f))
    fr = ks.frames(path)
    r_strand = radius * 0.5
    for sdx in range(strands):
        sp = []
        for i, p in enumerate(path):
            tan, nr, bn = fr[i]
            ang = (i / per_pitch) * math.tau + sdx / strands * math.tau
            sp.append(p + (nr * math.cos(ang) + bn * math.sin(ang)) * radius * 0.52)
        bm = tube_loop(sp, [r_strand] * len(sp), sides, closed=False)
        emit(b, bm, mat, lod=lod, angle=60.0, t=0.5)
        bm.free()


def hull_prism(profile_xz, y0, y1):
    """A closed prism: polygon `profile_xz` [(x, z)] counter-clockwise seen from -y, extruded from y0 to y1."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in profile_xz]
    c = [bm.verts.new((x, y1, z)) for x, z in profile_xz]
    n = len(a)
    bm.faces.new(list(reversed(a)))
    bm.faces.new(c)
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], c[(i + 1) % n], c[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def extent(pieces):
    xs, ys, zs = [], [], []
    for o in pieces:
        for v in o.data.vertices:
            xs.append(v.co.x)
            ys.append(v.co.y)
            zs.append(v.co.z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def footprint(name, pieces):
    x0, x1, y0, y1, z0, z1 = extent(pieces)
    r = max(abs(x0), abs(x1), abs(y0), abs(y1))
    cells = 1
    while cells < 2.0 * r:
        cells += 2
    print("[%s] extent x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (ground -0.50) -> footprint %dx%d cells, height %.2f m above ground"
          % (name, x0, x1, y0, y1, z0, z1, cells, cells, z1 - G))
    return cells, z1 - G


def finish(name, b, bodies, out_dir, previews, size, density, extra=(), voxel=0.1, limit=90, coarse=0.35, views=None,
           boxes=None):
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    cells, height = footprint(name, pieces)
    size = int(os.environ.get("SB_SIZE", size))
    lk.set_preview_dir(previews)
    only = os.environ.get("SB_VIEWS")
    if views and only:
        views = [v for v in views if v[0] in only.split(",")]
    if os.environ.get("SB_GEO"):
        # geometry check: one neutral material, small low-sample renders on two threads
        import bpy
        model = tk.triangulate(tk.join(pieces, name))
        model.data.materials.clear()
        gm, gg = tk.new_material("Geo")
        tk.finish(gm, gg, (0.3, 0.28, 0.25), 0.0, 0.7)
        model.data.materials.append(gm)
        for pl in model.data.polygons:
            pl.use_smooth = True
        sc = bpy.context.scene
        sc.render.threads_mode = "FIXED"
        sc.render.threads = 2
        orig = tk.render
        tk.render = lambda cam, path, res=(800, 600), samples=10, transparent=False: orig(cam, path, (800, 600), 10, transparent)
        if views:
            lk.preview(name.lower() + "_geo", model, views, floor=1.0)
        return model
    if os.environ.get("SB_FAST"):
        # development: render the procedural materials directly, small and noisy, no atlas bake or export
        model = tk.triangulate(tk.join(pieces, name))
        orig = tk.render
        tk.render = lambda cam, path, res=(800, 600), samples=12, transparent=False: orig(cam, path, (800, 600), 12, transparent)
        if views:
            lk.preview(name.lower(), model, views, floor=1.0)
        tk.render = orig
        return model
    model = lk.export(name, pieces, bodies, out_dir, size=size, density=density, voxel=voxel, extra=extra, rect=False,
                      limit=limit, coarse=coarse, boxes=boxes)
    if views:
        if os.environ.get("SB_DEV"):
            orig = tk.render
            tk.render = lambda cam, path, res=(900, 675), samples=20, transparent=False: orig(cam, path, (900, 675), 20, transparent)
        lk.preview(name.lower(), model, views, floor=1.0)
    return model


def standard_views(h, reach=0.8, far=8.0):
    """Preview cameras: far (5 to 10 m, eye height), mid (2.5 m), close (arm's length), and from the other side."""
    c = (0.0, 0.0, G + h * 0.4)
    return [
        ("far", (-far * 0.55, -far * 0.8, G + 1.7), (0.0, 0.0, G + h * 0.4)),
        ("mid", (-1.7, -2.1, G + 1.6), c),
        ("close", (-0.55 - reach * 0.5, -0.75 - reach * 0.4, G + 0.75), c),
        ("back", (1.7, 2.0, G + 1.4), c),
    ]


def layers_mat(name, color, color2):
    """The end of a rolled sleeping bag: wound layers seen edge on, rings round the axis (attribute t = distance from it in
    meters), light and dark by layer, dark where the fabric folds, soil and mould in the creases."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    wob = g.math("ADD", g.math("MULTIPLY", g.noise(4.0, detail=3.0), 2.5), g.math("MULTIPLY", g.noise(30.0, detail=3.0), 0.5))
    ring = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 520.0), wob))
    lay = g.ramp(ring, -0.3, 0.7)
    col = g.mix(lay, color, color2)
    fold = g.ramp(ring, -0.7, -1.0)
    col = g.mix(g.math("MULTIPLY", fold, 0.8), col, (0.012, 0.01, 0.01))
    fib = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (350.0, 350.0, 350.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.85), 0.2), col, tuple(min(1.0, c * 1.5) for c in color2))
    mo = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0), 0.55, 0.7), 0.7)
    col = g.mix(mo, col, (0.03, 0.04, 0.026))
    fur = g.math("MULTIPLY", g.ramp(g.noise(22.0, detail=5.0), 0.62, 0.72), 0.6)
    col = g.mix(fur, col, (0.3, 0.31, 0.27))
    col, rough, _ = _ground_dirt(g, col, 0.95, 0.14, 0.9)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", g.math("MULTIPLY", lay, 0.5), g.math("SUBTRACT", 1.0, fold))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.002))


def end_grain_old(name, ring=0.0065):
    """Sawn end grain gone grey-brown with age (attribute t = distance from the pith in meters): weathered rings, deep
    radial checks, soil and algae in the checks."""
    mat, g = tk.new_material(name)
    r = ks._attr(g, "t")
    k = math.tau / ring
    wob = g.math("ADD", g.math("MULTIPLY", g.noise(5.0, detail=3.0), 3.0), g.math("MULTIPLY", g.noise(23.0, detail=3.0), 0.9))
    rings = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, k), wob)), -0.4, 0.6)
    fib = g.noise(1.0, detail=4.0, vector=lk.stretched(g, (5.0, 90.0, 90.0)))
    col = g.mix(rings, (0.12, 0.105, 0.085), (0.25, 0.225, 0.19))
    grey = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=4.0), 0.4, 0.7), 0.5)
    col = g.mix(grey, col, (0.2, 0.195, 0.18))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.55, 0.8), 0.4), col, (0.06, 0.05, 0.04))
    radial = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (40.0, 40.0, 40.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(radial, 0.62, 0.85), 0.7), col, (0.02, 0.016, 0.012))
    al = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0), 0.58, 0.72), 0.45)
    col = g.mix(al, col, (0.05, 0.075, 0.035))
    col, rough, _ = _ground_dirt(g, col, 0.9, 0.14, 0.8)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", g.math("MULTIPLY", rings, 0.6), g.math("MULTIPLY", fib, 0.25))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.ramp(radial, 0.62, 0.85), 0.5))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.0025))
