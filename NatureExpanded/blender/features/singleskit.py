"""Shared kit for Nature Expanded's "single find" props (TrailMarker, Antlers, LoneBoot, OldTire, Wheelbarrow, LawnChair):
small abandoned things half swallowed by the ground and the weeds (see SPEC_singlesA.md). On top of featurekit.py,
logkit.py and the plant kits.

- Geometry: `block` (a rounded box on a lattice, any size, noise through a `deform` callback), `sweep` (a tube along a
  polyline with its own radius, flattening and bumps per ring), `loft` (rings to quads), `emit` (any of them into a
  ks.Builder, per-face materials, per-vertex `ang`).
- The `ang` vertex attribute: a second per-vertex value next to ks's `t` (set `m.cur_aux` before making vertices, or
  pass aux= to emit/sweep). Materials read it with ks._attr(g, "ang").
- Ground cover: `mound` (a soil heap), `litter` (fallen leaves with lobed outlines), `grass`, `rosette`, `twigs`.
- Materials: `wood_mat` (silvered timber with checks, lichen, mildew), `rust_mat` (painted or bare steel), `alum_mat`
  (oxidised aluminium), `scribble` (pseudo-handwriting that reads as text and isn't), `local_coords`.
- `finish_export` / `preview` for the scripts.

Conventions as featurekit: meters, Z up, the block's center at the origin, the ground at z = G = -0.5.
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
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
UP = Vector((0.0, 0.0, 1.0))


# ================================================================ the `ang` vertex attribute

_orig_v = ks._Mesh.v


def _v_aux(self, co, t):
    if not hasattr(self, "aux"):
        self.aux = []
    self.aux.append(getattr(self, "cur_aux", 0.0))
    return _orig_v(self, co, t)


ks._Mesh.v = _v_aux
_orig_objects = ks.Builder.objects


def _objects_aux(self):
    auxs = [getattr(m, "aux", None) for m, _ in self.meshes.values() if m.bm.faces]
    out = _orig_objects(self)
    for obj, aux in zip(out, auxs):
        if aux is not None and len(aux) == len(obj.data.vertices):
            a = obj.data.attributes.new("ang", "FLOAT", "POINT")
            a.data.foreach_set("value", aux)
    return out


ks.Builder.objects = _objects_aux


_orig_reset = tk.reset_scene


def _reset_cpu():
    """The shared machine's GPU is somebody else's game: CPU only."""
    scene = _orig_reset()
    scene.cycles.device = "CPU"
    return scene


tk.reset_scene = _reset_cpu
LIVE = bool(os.environ.get("SK_LIVE"))     # SK_LIVE=1: render the procedural materials directly, no bake and no export (the quickest look)
FAST = bool(os.environ.get("SK_FAST"))     # SK_FAST=1: quick look (small atlas, few bake and render samples), not for export
if FAST:
    _orig_bake = tk._bake

    def _fast_bake(obj, kind, img, samples, **kw):
        return _orig_bake(obj, kind, img, min(samples, 4), **kw)

    tk._bake = _fast_bake
else:
    # The kit's 64 and 128 sample bakes, trimmed (a shared machine; the procedural signals are smooth and the AO is soft)
    _orig_bake = tk._bake

    def _q_bake(obj, kind, img, samples, **kw):
        return _orig_bake(obj, kind, img, min(samples, 24 if kind == "AO" else 16), **kw)

    tk._bake = _q_bake


def fbm(p, seed=0.0, octaves=3):
    return mn.fractal(Vector(p) + Vector((seed * 7.31, seed * 3.17, seed * 1.91)), 0.5, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smooth(x, lo, hi):
    t = clamp((x - lo) / (hi - lo)) if hi != lo else (1.0 if x >= hi else 0.0)
    return t * t * (3.0 - 2.0 * t)


def euler_matrix(deg):
    """Rotation matrix for an XYZ Euler in degrees (what a Mapping node's Rotation of the same angles undoes)."""
    return Matrix.Rotation(math.radians(deg[2]), 3, "Z") @ Matrix.Rotation(math.radians(deg[1]), 3, "Y") @ Matrix.Rotation(math.radians(deg[0]), 3, "X")


# ================================================================ geometry

class Shape:
    """verts [Vector], polys [index tuples], info (per polygon: whatever the maker recorded, e.g. (axis, sign))."""

    def __init__(self, verts, polys, info=None):
        self.verts = verts
        self.polys = polys
        self.info = info or [None] * len(polys)

    def body(self):
        return ([v.copy() for v in self.verts], list(self.polys))

    def bounds(self):
        xs = [v.x for v in self.verts]
        ys = [v.y for v in self.verts]
        zs = [v.z for v in self.verts]
        return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def _coords_list(h, r, step, nr):
    r = min(r, h * 0.49)
    ro = [r * k / nr for k in range(nr + 1)]
    lo = [-h + x for x in ro]
    hi = [h - x for x in reversed(ro)]
    a, b = -h + r, h - r
    n = max(1, int(round((b - a) / step)))
    mid = [a + (b - a) * k / n for k in range(1, n)]
    return lo + mid + hi


def block(center, half, rot=None, r=0.006, step=0.08, nr=3, deform=None, steps=None):
    """A rounded box (edge radius `r`) on a lattice with rounded edges sampled in `nr` steps and flat faces at about
    `step` spacing (or `steps` per axis). `deform(q, n)` may move each local point q (n: its local outward normal).
    Returns a Shape; info per polygon is (axis, sign) of the box face it belongs to."""
    hx, hy, hz = half
    rr = min(r, hx * 0.49, hy * 0.49, hz * 0.49)
    st = steps or (step, step, step)
    xs, ys, zs = (_coords_list(hx, rr, st[0], nr), _coords_list(hy, rr, st[1], nr), _coords_list(hz, rr, st[2], nr))
    nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
    inner = (hx - rr, hy - rr, hz - rr)
    center = Vector(center)
    cache, verts = {}, []

    def vid(i, j, k):
        key = (i, j, k)
        if key in cache:
            return cache[key]
        P = Vector((xs[i], ys[j], zs[k]))
        I = Vector((max(-inner[0], min(inner[0], P.x)), max(-inner[1], min(inner[1], P.y)), max(-inner[2], min(inner[2], P.z))))
        d = P - I
        if d.length > 1e-9:
            n = d.normalized()
            q = I + n * rr
        else:
            n = Vector((0.0, 0.0, 1.0))
            q = P
        if deform is not None:
            q = deform(q, n)
        w = center + (rot @ q if rot is not None else q)
        verts.append(w)
        cache[key] = len(verts) - 1
        return cache[key]

    polys, info = [], []

    def quad(a, b, c, d, flip, tag):
        q = (a, b, c, d)
        polys.append(tuple(reversed(q)) if flip else q)
        info.append(tag)

    for i in (0, nx):
        for j in range(ny):
            for k in range(nz):
                quad(vid(i, j, k), vid(i, j + 1, k), vid(i, j + 1, k + 1), vid(i, j, k + 1), i == 0, (0, -1 if i == 0 else 1))
    for j in (0, ny):
        for i in range(nx):
            for k in range(nz):
                quad(vid(i, j, k), vid(i, j, k + 1), vid(i + 1, j, k + 1), vid(i + 1, j, k), j == 0, (1, -1 if j == 0 else 1))
    for k in (0, nz):
        for i in range(nx):
            for j in range(ny):
                quad(vid(i, j, k), vid(i + 1, j, k), vid(i + 1, j + 1, k), vid(i, j + 1, k), k == 0, (2, -1 if k == 0 else 1))
    return Shape(verts, polys, info)


def loft(rings, close_u=True, close_v=False, cap_start=False, cap_end=False, flip=False):
    """Quads between consecutive rings (lists of Vectors, same length). close_u wraps within a ring, close_v wraps from
    the last ring to the first (a torus). cap_start/cap_end close open ends with a center vertex."""
    n = len(rings[0])
    verts = [Vector(p) for ring in rings for p in ring]
    polys = []
    rows = len(rings)
    last = rows if close_v else rows - 1
    for i in range(last):
        i1 = (i + 1) % rows
        for k in range(n if close_u else n - 1):
            k1 = (k + 1) % n
            q = (i * n + k, i * n + k1, i1 * n + k1, i1 * n + k)
            polys.append(tuple(reversed(q)) if flip else q)
    for cap, ring_i, rev in ((cap_start, 0, True), (cap_end, rows - 1, False)):
        if cap:
            c = sum((verts[ring_i * n + k] for k in range(n)), Vector()) / n
            verts.append(c)
            ci = len(verts) - 1
            for k in range(n):
                k1 = (k + 1) % n
                t = (ci, ring_i * n + k1, ring_i * n + k) if rev else (ci, ring_i * n + k, ring_i * n + k1)
                polys.append(tuple(reversed(t)) if flip else t)
    return Shape(verts, polys)


def emit(b, shape, mat, mats=None, t=0.5, smooth_=True, lod=None, aux=0.0, tfun=None, auxfun=None, mat_of=None, below=None):
    """Adds a Shape to Builder `b`. `mats`: per-polygon materials (or mat_of(info) -> material). tfun(vertex_index,
    point) -> t, auxfun likewise -> ang."""
    saved = b.lod
    if lod is not None:
        b.lod = lod
    caches = {}
    started = set()
    for pi, poly in enumerate(shape.polys):
        if below is not None and max(shape.verts[vi].z for vi in poly) < below:
            continue
        mt = mats[pi] if mats is not None else (mat_of(shape.info[pi]) if mat_of is not None else mat)
        m = b.mesh(mt)
        if mt.name not in started:
            m.begin((0.0, 0.0, G))
            started.add(mt.name)
        cache = caches.setdefault(mt.name, {})
        vs = []
        for vi in poly:
            if vi not in cache:
                p = shape.verts[vi]
                m.cur_aux = auxfun(vi, p) if auxfun else aux
                cache[vi] = m.v(p.copy(), tfun(vi, p) if tfun else t)
            vs.append(cache[vi])
        m.f(vs, smooth_)
    b.lod = saved


def sweep(b, mat, pts, radii, sides=8, aspect=None, mod=None, cap_start=True, cap_end=True, smooth_=True, t0=0.0, t1=1.0,
          close_loop=False, power=None, twist=0.0, up=None, ang0=0.0, end_mat=None, shift0=None, shift1=None):
    """A tube along the polyline `pts` (radius per point, `aspect` per point flattens the second axis, `mod(i, a, s)`
    scales the radius of ring i at angle a (radians) for bites and bumps, `power` a superellipse exponent for squarish
    sections). Vertex attribute ang = angle / tau. Returns the rings (lists of Vectors)."""
    pts = [Vector(p) for p in pts]
    fr = ks.frames(pts)
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    total = acc[-1] or 1.0
    m = b.mesh(mat)
    m.begin(pts[0])
    rings, rows = [], []
    for i, p in enumerate(pts):
        r = radii[i]
        if r <= 1e-6:
            m.cur_aux = 0.0
            rows.append([m.v(p, t0 + (t1 - t0) * acc[i] / total)])
            rings.append([p.copy()])
            continue
        tan, nr, bn = fr[i]
        if up is not None:
            u = Vector(up)
            nr = (u - tan * u.dot(tan))
            if nr.length > 1e-4:
                nr.normalize()
                bn = tan.cross(nr)
        asp = aspect[i] if aspect is not None else 1.0
        tw = twist * acc[i] / total
        ring, row = [], []
        for k in range(sides):
            a = ang0 + k / sides * math.tau + tw
            ca, sa = math.cos(a), math.sin(a)
            if power is not None:
                ca = math.copysign(abs(ca) ** (2.0 / power), ca)
                sa = math.copysign(abs(sa) ** (2.0 / power), sa)
            f = mod(i, a, acc[i] / total) if mod is not None else 1.0
            q = p + (nr * ca * r + bn * sa * r * asp) * f
            if i == 0 and shift0 is not None:
                q = q + tan * shift0(a)
            if i == len(pts) - 1 and shift1 is not None:
                q = q + tan * shift1(a)
            m.cur_aux = (a / math.tau) % 1.0
            row.append(m.v(q, t0 + (t1 - t0) * acc[i] / total))
            ring.append(q)
        rows.append(row)
        rings.append(ring)
    for i in range(len(rows) - 1):
        A, B = rows[i], rows[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(sides):
            k1 = (k + 1) % sides
            if len(B) == 1:
                m.f((A[k], A[k1], B[0]), smooth_)
            elif len(A) == 1:
                m.f((A[0], B[k1], B[k]), smooth_)
            else:
                m.f((A[k], A[k1], B[k1], B[k]), smooth_)
    if close_loop:
        A, B = rows[-1], rows[0]
        for k in range(sides):
            k1 = (k + 1) % sides
            m.f((A[k], A[k1], B[k1], B[k]), smooth_)
    else:
        mc = b.mesh(end_mat) if end_mat is not None else m
        for cap, ring_i, rev in ((cap_start, 0, True), (cap_end, len(rows) - 1, False)):
            if cap and len(rows[ring_i]) > 2:
                if end_mat is not None:
                    mc.begin(pts[ring_i])
                    vs = [mc.v(q.copy(), 0.0) for q in rings[ring_i]]
                else:
                    vs = rows[ring_i]
                mc.f(list(reversed(vs)) if rev else vs, False)
    m.cur_aux = 0.0
    return rings


def ring_pts(center, n, nr, bn, ra, rb=None, a0=0.0):
    rb = ra if rb is None else rb
    return [Vector(center) + nr * (math.cos(a0 + k / n * math.tau) * ra) + bn * (math.sin(a0 + k / n * math.tau) * rb) for k in range(n)]


def tube_body(rings):
    """A closed sweep (rings of equal count, first and last capped by their own polygons) as Shape for the colliders."""
    return loft(rings, cap_start=True, cap_end=True)


# ================================================================ ground cover

def litter_mats(prefix="Lf"):
    return [kf.litter_material(prefix + "A", (0.12, 0.075, 0.035), (0.075, 0.05, 0.025), 0.4),
            kf.litter_material(prefix + "B", (0.19, 0.12, 0.04), (0.12, 0.07, 0.025), 0.35),
            kf.litter_material(prefix + "C", (0.075, 0.06, 0.035), (0.045, 0.035, 0.02), 0.5),
            kf.litter_material(prefix + "D", (0.15, 0.085, 0.03), (0.09, 0.05, 0.02), 0.35)]


def _outline(kind, s, ph):
    base = math.sin(math.pi * clamp(s)) ** 0.75
    if kind == "oak":
        return base * (0.7 + 0.3 * abs(math.cos(2.4 * math.pi * s + ph)) ** 1.5)
    if kind == "maple":
        return base * (0.55 + 0.45 * abs(math.cos(1.5 * math.pi * s + ph)) ** 1.2) * (1.0 + 0.2 * (1.0 - s))
    if kind == "narrow":
        return base * 0.7
    return base


def leaf_shape(b, mat, base, d, length, width, kind="oval", rows=5, bend=0.1, fold=0.2, roll=0.0, normal=None, ph=0.0,
               rnd=None, t0=0.0, t1=1.0):
    """A leaf with a shaped outline (oak, maple lobes, narrow) as `rows` rows of quads, a little folded and bent along its
    midrib. Faces `normal` (default up)."""
    d, side, up = ks._leaf_frame(d, normal if normal is not None else UP, roll)
    m = b.mesh(mat)
    base = Vector(base)
    m.begin(base)
    hw = width * 0.5
    B = m.v(base, t0)
    rowsv = []
    for i in range(rows):
        s = (i + 1) / (rows + 1)
        c = ks.bent(base, d, length, bend, s)
        w = _outline(kind, s, ph) * hw
        tt = t0 + (t1 - t0) * s
        rowsv.append((m.v(c - side * w + up * (fold * w), tt), m.v(c, tt), m.v(c + side * w + up * (fold * w), tt)))
    T = m.v(ks.bent(base, d, length, bend, 1.0), t1)
    L1, C1, R1 = rowsv[0]
    m.f((B, R1, C1))
    m.f((B, C1, L1))
    for (La, Ca, Ra), (Lb, Cb, Rb) in zip(rowsv, rowsv[1:]):
        m.f((La, Ca, Cb, Lb))
        m.f((Ca, Ra, Rb, Cb))
    Ln, Cn, Rn = rowsv[-1]
    m.f((Ln, Cn, T))
    m.f((Cn, Rn, T))


def litter(b, mats, count, rnd, area, keep=lambda x, y: True, size=(0.05, 0.085), lift=0.0, rows=4, lod=1, ground=None):
    """Fallen leaves lying about on the ground over area = (x0, x1, y0, y1), a few curled."""
    saved = b.lod
    n = tries = 0
    while n < count and tries < count * 30:
        tries += 1
        x, y = rnd.uniform(area[0], area[1]), rnd.uniform(area[2], area[3])
        if not keep(x, y):
            continue
        n += 1
        a = rnd.uniform(0, math.tau)
        z = (ground(x, y) if ground else G) + 0.004 + lift * rnd.random()
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.04, 0.16)))
        ln = rnd.uniform(*size)
        b.lod = lod if n % 3 else 0
        leaf_shape(b, rnd.choice(mats), (x, y, z), d, ln, ln * rnd.uniform(0.5, 0.8), kind=rnd.choice(("oak", "maple", "oval", "oval", "narrow")),
                   rows=rows, bend=rnd.uniform(-0.25, 0.35), fold=rnd.uniform(0.1, 0.5), roll=rnd.uniform(-25, 25), ph=rnd.uniform(0, 6.28))
    b.lod = saved


def grass(b, mat, x, y, rnd, blades=14, height=(0.18, 0.42), spread=0.08, width=0.011, lean=0.5, z=G, dry=None, dry_share=0.25,
          bound=None, lod=1):
    """A tuft of grass blades (4-row lance leaves arching outward). `dry` is an optional second material for dead blades;
    `bound` = (xmin, xmax, ymin, ymax) keeps the tips inside."""
    saved = b.lod
    for i in range(blades):
        a = rnd.uniform(0, math.tau)
        r0 = rnd.uniform(0.0, spread)
        px, py = x + math.cos(a) * r0, y + math.sin(a) * r0
        h = rnd.uniform(*height)
        tilt = math.radians(rnd.uniform(5, 38) * (0.5 + lean))
        ho = rnd.uniform(0, math.tau) if rnd.random() < 0.5 else a
        d = Vector((math.cos(ho) * math.sin(tilt), math.sin(ho) * math.sin(tilt), math.cos(tilt)))
        bd = rnd.uniform(0.25, 0.9) * lean * 1.5
        if bound is not None:
            tip = ks.bent(Vector((px, py, z)), d, h, bd, 1.0)
            if not (bound[0] < tip.x < bound[1] and bound[2] < tip.y < bound[3]):
                continue
        use = dry if (dry is not None and rnd.random() < dry_share) else mat
        b.lod = lod if i % 2 else 0
        ks.leaf(b, use, (px, py, z), d, h, width * rnd.uniform(0.7, 1.3), bend=bd, fold=0.6, profile="lance", rows=4, normal=UP)
    b.lod = saved


def rosette(b, mat, x, y, rnd, leaves=7, length=(0.1, 0.17), width=0.07, z=G, tilt=(20, 55), bound=None, profile="spoon"):
    """A low rosette of broad leaves (plantain, dock, dandelion)."""
    for i in range(leaves):
        a = i / leaves * math.tau + rnd.uniform(-0.3, 0.3)
        tl = math.radians(rnd.uniform(*tilt))
        d = Vector((math.cos(a) * math.sin(tl), math.sin(a) * math.sin(tl), math.cos(tl)))
        ln = rnd.uniform(*length)
        if bound is not None:
            tip = ks.bent(Vector((x, y, z)), d, ln, 0.4, 1.0)
            if not (bound[0] < tip.x < bound[1] and bound[2] < tip.y < bound[3]):
                continue
        ks.leaf(b, mat, (x, y, z), d, ln, width * rnd.uniform(0.8, 1.2), bend=rnd.uniform(0.2, 0.6), fold=0.35, profile=profile, rows=4)


def twigs(b, mat, count, rnd, area, keep=lambda x, y: True, length=(0.1, 0.3), radius=(0.003, 0.008), z=G, limit=(0.5, 0.5)):
    for _ in range(count):
        ok = False
        for _t in range(30):
            x, y = rnd.uniform(area[0], area[1]), rnd.uniform(area[2], area[3])
            a = rnd.uniform(0, math.tau)
            ln = rnd.uniform(*length)
            if keep(x, y) and abs(x + math.cos(a) * ln) < limit[0] and abs(y + math.sin(a) * ln) < limit[1]:
                ok = True
                break
        if not ok:
            continue
        r = rnd.uniform(*radius)
        pts = []
        for k in range(4):
            f = k / 3
            pts.append(Vector((x + math.cos(a) * ln * f + rnd.gauss(0, 0.004), y + math.sin(a) * ln * f + rnd.gauss(0, 0.004),
                               z + r + 0.003 + rnd.uniform(0, 0.012) * (1.0 - abs(f - 0.5)))))
        ks.tube(b, mat, pts, [r, r * 0.9, r * 0.75, r * 0.5], sides=4, cap=True, jag=0.6, rnd=rnd)


def mound(b, mat, center, radius, rnd, dome=0.05, sides=22, rings=4, sink=0.05, jitter=0.3, lump=0.012, skew=(1.0, 1.0), limit=(0.505, 0.505)):
    """A heap of soil: rings of vertices round a raised middle, lumpy, the rim sunk below the ground so it melts into the
    terrain. Returns a function z(x, y) giving its height there (for standing things on it)."""
    cx, cy = center
    m = b.mesh(mat)
    m.begin((cx, cy, G))
    m.cur_aux = 0.0
    rows = []
    ph = rnd.uniform(0, 6.28)
    prof = {}
    centerv = m.v((cx, cy, G + dome), 1.0)
    for ring in range(1, rings + 1):
        f = ring / rings
        row = []
        for k in range(sides):
            a = k / sides * math.tau
            rr = radius * f * (1.0 + jitter * 0.6 * math.sin(a * 3 + ph) * f + rnd.uniform(-jitter, jitter) * 0.25 * f)
            x, y = cx + rr * math.cos(a) * skew[0], cy + rr * math.sin(a) * skew[1]
            x, y = max(-limit[0], min(limit[0], x)), max(-limit[1], min(limit[1], y))
            h = dome * (1.0 - f * f) ** 0.8 + lump * fbm((x * 14, y * 14, 0.5), ph) * (1.0 - f * 0.6)
            z = G + max(0.0, h) - (sink if ring == rings else 0.0)
            row.append(m.v((x, y, z), 1.0 - 0.5 * f))
            prof[(ring, k)] = (x, y, z)
        rows.append(row)
    for k in range(sides):
        m.f((centerv, rows[0][k], rows[0][(k + 1) % sides]), True)
    for A, Bw in zip(rows, rows[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            m.f((A[k], Bw[k], Bw[k1], A[k1]), True)

    def height(x, y):
        dx, dy = (x - cx) / skew[0], (y - cy) / skew[1]
        f = math.hypot(dx, dy) / radius
        if f >= 1.0:
            return G
        return G + dome * (1.0 - f * f) ** 0.8

    return height


def cushion(b, mat, center, normal, radius, height, rnd, sides=16, rings=3, lump=0.4, sink=0.006, squash=(1.0, 1.0)):
    """A low dome of moss (or any cushion) on a surface: rings of vertices round the middle, along `normal`, the rim sunk a
    little into the surface so it melts in. Attribute t runs 1 in the middle to 0.5 at the rim (as mound)."""
    ax, u, v = ks.basis(normal)
    c = Vector(center)
    m = b.mesh(mat)
    m.begin(c)
    m.cur_aux = 0.0
    top = m.v(c + ax * height, 1.0)
    ph = rnd.uniform(0, 6.28)
    rows = []
    for ring in range(1, rings + 1):
        f = ring / rings
        row = []
        for k in range(sides):
            a = k / sides * math.tau
            rr = radius * f * (1.0 + 0.22 * math.sin(a * 3 + ph) * f + rnd.uniform(-0.12, 0.12) * f)
            h = height * (1.0 - f * f) ** 0.7 * (1.0 + lump * fbm((math.cos(a) * f * 3 + ph, math.sin(a) * f * 3, f), 1.0))
            if ring == rings:
                h = -sink
            row.append(m.v(c + u * (math.cos(a) * rr * squash[0]) + v * (math.sin(a) * rr * squash[1]) + ax * h, 1.0 - 0.5 * f))
        rows.append(row)
    for k in range(sides):
        m.f((top, rows[0][k], rows[0][(k + 1) % sides]), True)
    for A, Bw in zip(rows, rows[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            m.f((A[k], Bw[k], Bw[k1], A[k1]), True)


def soil_small(name, scale=2.3, relief=0.0045, **kw):
    """Forest soil at the grain a small prop's mound needs (lk.soil_mat is made for big root plates)."""
    mat, g = tk.new_material(name)
    col, height, rough = lk.soil_surface(g, scale=scale, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))



def litter_bed(name, scale=1.0, moss=0.18, bare=0.18, relief=0.004):
    """A carpet of fallen leaves, needles and soil as a texture (for the mound under a prop): leaf-sized cells each a random
    shade of ochre, rust, brown or grey, dark gaps between them, bare soil showing, pine needles and the odd moss patch."""
    mat, g = tk.new_material(name)
    co = kf._warped(g, 9.0, 0.03)
    d1, r1 = kf._cells(g, 15.0 * scale, co)
    d2, r2 = kf._cells(g, 52.0 * scale, kf._warped(g, 30.0, 0.006))
    col = g.mix(g.ramp(r1, 0.15, 0.38), (0.052, 0.036, 0.022), (0.075, 0.047, 0.026))
    col = g.mix(g.ramp(r1, 0.38, 0.5), col, (0.125, 0.073, 0.03))
    col = g.mix(g.ramp(r1, 0.62, 0.72), col, (0.2, 0.125, 0.045))
    col = g.mix(g.ramp(r1, 0.85, 0.93), col, (0.115, 0.097, 0.072))
    soilc = g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.3, 0.7), (0.034, 0.024, 0.015), (0.06, 0.043, 0.028))
    col = g.mix(g.ramp(r1, bare, bare - 0.05), col, soilc)
    sub = g.math("MULTIPLY", g.ramp(r2, 0.55, 0.8), g.ramp(d2, 0.35, 0.1))
    col = g.mix(g.math("MULTIPLY", sub, 0.45), col, g.mix(g.ramp(r2, 0.3, 0.9), (0.09, 0.055, 0.025), (0.16, 0.1, 0.04)))
    gap = g.ramp(d1, 0.22, 0.46)
    col = g.mix(g.math("MULTIPLY", gap, 0.8), col, (0.014, 0.01, 0.007))
    needle = g.ramp(kf._ridged(g, g.noise(1.0, detail=2.0, vector=ks._stretched(g, (500.0, 24.0, 500.0)))), 0.9, 0.99)
    needle = g.math("MULTIPLY", needle, g.ramp(g.noise(7.0, detail=3.0), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", needle, 0.55), col, (0.15, 0.1, 0.05))
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g, 0.9)
        cover = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=5.0, distortion=0.4), 0.58, 0.72), moss * 3.0)
        col = g.mix(g.math("MULTIPLY", cover, 0.9), col, tk.grade(g, mcol, sat=0.9, value=0.9))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(d1, 0.5, 0.0), 0.8), g.math("MULTIPLY", g.noise(150.0, detail=3.0), 0.25))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", gap, 0.3))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.92, value=0.95), 0.0, 0.93, g.bump(height, 1.0, relief))


def moss_clump_mat(name, soil=(0.035, 0.025, 0.016)):
    return kf.moss_material(name, soil)



def revolve(profile, n, T, close_profile=True, wobble=None):
    """A solid of revolution about the local z axis: `profile` [(r, h)] in order (counter-clockwise seen with r to the right
    and h up gives outward faces going up the outside), `n` segments, T(Vector) places each local point. wobble(theta, r, h)
    -> (r, h) may deform. Closed round and, with close_profile, along the profile."""
    rings = []
    for i in range(n):
        th = i / n * math.tau
        c, s = math.cos(th), math.sin(th)
        ring = []
        for r, h in profile:
            if wobble is not None:
                r, h = wobble(th, r, h)
            ring.append(T(Vector((r * c, r * s, h))))
        rings.append(ring)
    return loft(rings, close_u=close_profile, close_v=True)



def smooth_path(pts, n):
    """n+1 points along the Catmull-Rom spline through pts."""
    pts = [Vector(p) for p in pts]
    m = len(pts) - 1
    return [lk._catmull(pts, i / n * m) for i in range(n + 1)]


def vine(b, vmat, lmat, pts, rnd, r=0.0035, every=3, leaf=(0.04, 0.065), out=None, kind="heart"):
    """A thin twining stem along `pts` with a leaf every few points (heart-shaped bindweed). `out(p)` gives the direction
    leaves point away from the support (default: up)."""
    n = len(pts)
    ks.tube(b, vmat, pts, [r * (1.0 - 0.5 * i / max(1, n - 1)) for i in range(n)], sides=4, cap=True)
    for i in range(1, n - 1, every):
        p = pts[i]
        o = Vector(out(p)) if out is not None else Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.3))
        if o.length < 1e-4:
            o = Vector((0, 0, 1))
        d = (o.normalized() * 0.8 + Vector((0, 0, 0.35)) + Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 0))).normalized()
        ln = rnd.uniform(*leaf)
        ks.leaf(b, lmat, p, d, ln, ln * rnd.uniform(0.8, 1.0), bend=rnd.uniform(0.2, 0.7), fold=0.3, profile=kind, rows=3, normal=Vector((0, 0, 1)) + o.normalized() * 0.3)


def obox(T, R, center, size):
    """A collider line for a box given in an object's own frame: center and size in that frame, T places points, R is the
    rotation of the frame (its columns are the box axes)."""
    c = T(Vector(center))
    ux, uy, uz = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0)), R @ Vector((0, 0, 1))
    return "box %.3f %.3f %.3f %.3f %.3f %.3f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (
        c.x, c.y, c.z, size[0], size[1], size[2], ux.x, ux.y, ux.z, uy.x, uy.y, uy.z, uz.x, uz.y, uz.z)


def ocapsule(T, p0, p1, r):
    a, b_ = T(Vector(p0)), T(Vector(p1))
    return "capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (a.x, a.y, a.z, b_.x, b_.y, b_.z, r)


# ================================================================ materials

def local_coords(g, center, euler_deg=(0.0, 0.0, 0.0)):
    """Object coordinates in a part's own frame (the frame whose origin is `center` and whose axes are turned by the XYZ
    Euler `euler_deg`, the same one used to place it): lets a pattern drawn flat on a board follow the board."""
    m = g.node("ShaderNodeMapping")
    m.vector_type = "TEXTURE"
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Location"].default_value = tuple(center)
    m.inputs["Rotation"].default_value = tuple(math.radians(a) for a in euler_deg)
    return m.outputs[0]


def _ax(g, axis, v):
    """Mapping scales with the long (grain) component first, on the given axis."""
    if axis == "x":
        s = (v[0], v[1], v[2])
    elif axis == "y":
        s = (v[1], v[0], v[2])
    else:
        s = (v[1], v[2], v[0])
    return ks._stretched(g, s)


def _normal_comp(g, i):
    geo = g.node("ShaderNodeNewGeometry")
    return g.separate(tk._sock(geo.outputs, "Normal"))[i]


def grade(g, col, sat=0.95, value=0.95):
    return tk.grade(g, col, sat=sat, value=value)


def white_rand(g, a, b=0.0, c=0.0):
    """Three independent randoms 0..1 from the numbers a, b, c (white noise): returns (r1, r2, r3)."""
    vec = g.node("ShaderNodeCombineXYZ")
    for i, x in enumerate((a, b, c)):
        if hasattr(x, "is_output"):
            g.links.new(x, vec.inputs[i])
        else:
            vec.inputs[i].default_value = x
    wn = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    g.links.new(vec.outputs[0], tk._sock(wn.inputs, "Vector"))
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tk._sock(wn.outputs, "Color"), sep.inputs[0])
    return sep.outputs[0], sep.outputs[1], sep.outputs[2]


def scribble(g, u, v, cell=0.012, height=0.02, seed=1.0, stroke=0.0022, density=0.8, wobble=0.0):
    """Pseudo-handwriting: a row of glyph-like marks (stems, bars, diagonals in random combinations, gaps for spaces) in
    the (u, v) plane, u along the line and v the height above the baseline, both in meters. Reads as text from a
    distance and as nothing from close. Returns a 0..1 mask."""
    cu = g.math("DIVIDE", u, cell)
    ci = g.math("FLOOR", cu)
    fu = g.math("FRACT", cu)
    fv = g.math("DIVIDE", v, height)
    r1, r2, r3 = white_rand(g, ci, seed, 0.37)
    wu, wv = stroke / cell, stroke / height
    exists = g.math("GREATER_THAN", r1, 1.0 - density)
    gap = g.math("GREATER_THAN", r2, 0.16)
    within = g.math("MULTIPLY", g.ramp(fv, -0.02, 0.0), g.ramp(fv, 1.04, 1.0))
    # stem
    stem_x = g.math("ADD", 0.18, g.math("MULTIPLY", r2, 0.6))
    stem = g.ramp(g.math("SUBTRACT", wu, g.math("ABSOLUTE", g.math("SUBTRACT", fu, stem_x))), 0.0, wu * 0.45)
    stem_h = g.math("ADD", 0.55, g.math("MULTIPLY", r3, 0.45))
    stem = g.math("MULTIPLY", stem, g.ramp(g.math("SUBTRACT", stem_h, fv), 0.0, 0.1))
    use1 = g.math("LESS_THAN", r3, 0.62)
    # bar
    bar_y = g.math("ADD", 0.28, g.math("MULTIPLY", r3, 0.5))
    bar = g.ramp(g.math("SUBTRACT", wv, g.math("ABSOLUTE", g.math("SUBTRACT", fv, bar_y))), 0.0, wv * 0.45)
    bar = g.math("MULTIPLY", bar, g.math("MULTIPLY", g.ramp(fu, 0.08, 0.16), g.ramp(fu, 0.94, 0.86)))
    use2 = g.math("MULTIPLY", g.math("GREATER_THAN", r1, 0.4), g.math("LESS_THAN", r1, 0.9))
    # diagonal
    flip = g.math("GREATER_THAN", r2, 0.55)
    dpos = g.mixf(flip, g.math("ADD", 0.12, g.math("MULTIPLY", fv, 0.76)), g.math("SUBTRACT", 0.88, g.math("MULTIPLY", fv, 0.76)))
    diag = g.ramp(g.math("SUBTRACT", wu * 1.3, g.math("ABSOLUTE", g.math("SUBTRACT", fu, dpos))), 0.0, wu * 0.5)
    use3 = g.math("GREATER_THAN", r3, 0.38)
    m = g.math("MAXIMUM", g.math("MULTIPLY", stem, use1), g.math("MAXIMUM", g.math("MULTIPLY", bar, use2), g.math("MULTIPLY", diag, use3)))
    m = g.math("MULTIPLY", m, g.math("MULTIPLY", g.math("MULTIPLY", exists, gap), within))
    return m


def wood_surface(g, axis="z", lo=(0.12, 0.108, 0.092), hi=(0.27, 0.255, 0.225), checks=1.0, grain=1.0, mildew=0.5, lichen=0.4,
                 lichen_side=(1.0, 0.0), algae=0.5, rot=0.0, ground=G, soil=(0.04, 0.03, 0.02), vec=None, brown=0.3):
    """Silvered weathered timber as node signals (color, height 0..1, roughness): fibres and raised grain along `axis`,
    dark grain lines, deep checks along the grain, tonal drift between silver-grey and damp brown, black mildew
    specks, crusty lichen on one side, green algae and splashed soil toward the ground, punky rot at the foot."""
    fib = g.noise(1.0, detail=5.0, roughness=0.62, vector=_ax(g, axis, (3.5, 170.0 * grain, 170.0 * grain)))
    fibre = g.ramp(kf._ridged(g, fib), 0.68, 0.96)
    fine = g.noise(1.0, detail=3.0, vector=_ax(g, axis, (14.0, 700.0, 700.0)))
    broad = g.noise(2.0, detail=4.0, vector=_ax(g, axis, (0.8, 8.0, 8.0)))
    ringn = g.noise(1.0, detail=2.0, distortion=2.6, vector=_ax(g, axis, (0.45, 30.0 * grain, 30.0 * grain)))
    col = g.mix(g.ramp(broad, 0.28, 0.72), lo, hi)
    col = g.mix(g.math("MULTIPLY", g.ramp(ringn, 0.45, 0.8), 0.4), col, tuple(c * 0.55 for c in lo))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.4, 0.75), 0.45), col, tuple(c * 0.66 for c in lo))
    col = g.mix(g.math("MULTIPLY", fibre, 0.4), col, tuple(min(1.0, c * 1.5) for c in hi))
    wet = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0, distortion=0.4), 0.55, 0.78), brown)
    col = g.mix(wet, col, (0.13, 0.085, 0.052))
    # Checks: thin deep splits along the grain
    warp = kf._warped(g, 22.0, 0.003, _ax(g, axis, (1.1, 24.0 * checks, 24.0 * checks)))
    ce = kf._voronoi(g, 1.0, warp, feature="DISTANCE_TO_EDGE")
    check = g.math("MULTIPLY", g.ramp(ce, 0.028, 0.0), g.ramp(g.noise(3.0, detail=3.0), 0.32, 0.55))
    col = g.mix(g.math("MULTIPLY", check, 0.92), col, (0.022, 0.018, 0.014))
    # Mildew specks and blotches
    mil = g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=5.0, roughness=0.7), 0.56, 0.74), g.ramp(g.noise(5.0, detail=3.0), 0.3, 0.62))
    col = g.mix(g.math("MULTIPLY", mil, 0.7 * mildew), col, (0.032, 0.034, 0.028))
    # Lichen rosettes and grey crusts, mostly on one side
    if lichen > 0.0:
        sx = _normal_comp(g, 0)
        sy = _normal_comp(g, 1)
        side = g.math("ADD", g.math("MULTIPLY", sx, lichen_side[0]), g.math("MULTIPLY", sy, lichen_side[1]))
        lc, lr = kf._cells(g, 52.0, kf._warped(g, 8.0, 0.012))
        gate = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0, distortion=0.3), 0.55, 0.7), g.ramp(side, -0.2, 0.7))
        disc = g.math("MULTIPLY", g.ramp(lc, 0.5, 0.3), g.math("MULTIPLY", g.ramp(lr, 0.1, 0.55), gate))
        gran, _ = kf._cells(g, 420.0)
        disc = g.math("MULTIPLY", g.math("MULTIPLY", disc, g.ramp(gran, 0.8, 0.3)), lichen)
        col = g.mix(g.math("MULTIPLY", disc, 0.9), col, g.mix(g.ramp(lr, 0.4, 0.9), (0.17, 0.2, 0.14), (0.36, 0.31, 0.11)))
    z = g.separate(g.coords())[2]
    if algae > 0.0:
        al = g.math("MULTIPLY", g.ramp(z, ground + 0.55, ground + 0.05), g.ramp(g.noise(7.0, detail=5.0), 0.38, 0.62))
        mcol, mh, mrough, _ = kf.moss_layer(g, 0.7)
        al = g.math("MULTIPLY", al, algae)
        col = g.mix(g.math("MULTIPLY", al, 0.75), col, tk.grade(g, mcol, sat=0.85, value=0.8))
    col = g.mix(g.math("MULTIPLY", g.ramp(z, ground + 0.22, ground - 0.02), g.ramp(g.noise(30.0, detail=4.0), 0.25, 0.6)), col, soil)
    if rot > 0.0:
        punk = g.math("MULTIPLY", g.ramp(z, ground + 0.13, ground + 0.02), rot)
        pit, pr = kf._cells(g, 120.0)
        col = g.mix(g.math("MULTIPLY", punk, 0.8), col, g.mix(g.ramp(pr, 0.3, 0.8), (0.035, 0.022, 0.013), (0.075, 0.048, 0.027)))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", fib, 0.4), g.math("MULTIPLY", fibre, 0.35)), g.math("MULTIPLY", check, 0.8))
    height = g.math("ADD", height, g.math("MULTIPLY", fine, 0.12))
    rough = g.mixf(check, 0.91, 0.98)
    return grade(g, col), height, rough


def wood_mat(name, relief=0.0035, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = wood_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def rust_surface(g, paint=None, paint_left=0.45, rust=0.8, steel=(0.055, 0.05, 0.047), streak=1.0, grime=0.6, ground=G,
                 scale=1.0, seed=0.0, flake=1.0, moss=0.0):
    """Corroded sheet steel as node signals (color, metal, roughness, height): a base of dark steel, rust in three
    tones in patches with pitted blisters and cracked crusts, flaking remains of `paint` (a color or None) with raised
    chipped edges, rust runs down the surface, grime in the crevices, earth splashed up from the ground, dust on tops.
    Texture detail down to the texel."""
    co = g.coords()
    z = g.separate(co)[2]
    sd = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    off = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(co, off.inputs[0])
    off.inputs[1].default_value = tuple(sd)
    cs = off.outputs[0]
    tone = g.noise(3.0 * scale, detail=5.0, distortion=0.4, vector=cs)
    patch = g.math("ADD", g.noise(5.0 * scale, detail=6.0, roughness=0.65, distortion=0.5, vector=cs),
                   g.math("MULTIPLY", g.math("SUBTRACT", g.noise(38.0 * scale, detail=4.0, vector=cs), 0.5), 0.35))
    cover = g.ramp(patch, 0.62 - 0.42 * rust, 0.7 - 0.42 * rust)
    # Rust: three tones, clumped
    t1 = g.noise(11.0 * scale, detail=5.0, vector=cs)
    t2 = g.noise(70.0 * scale, detail=4.0, vector=cs)
    rcol = g.mix(g.ramp(t1, 0.3, 0.62), (0.07, 0.027, 0.014), (0.17, 0.068, 0.028))
    rcol = g.mix(g.math("MULTIPLY", g.ramp(t2, 0.55, 0.8), 0.7), rcol, (0.3, 0.135, 0.045))
    cells, cr = kf._cells(g, 160.0 * scale, kf._warped(g, 20.0, 0.004, cs))
    pits = g.math("MULTIPLY", g.ramp(cells, 0.26, 0.08), g.ramp(g.noise(9.0 * scale, vector=cs), 0.3, 0.6))
    rcol = g.mix(g.math("MULTIPLY", pits, 0.75), rcol, (0.022, 0.011, 0.008))
    ce = kf._voronoi(g, 7.0 * scale, kf._warped(g, 14.0, 0.01, cs), feature="DISTANCE_TO_EDGE")
    crust = g.math("MULTIPLY", g.ramp(ce, 0.04, 0.0), g.ramp(t1, 0.4, 0.6))
    rcol = g.mix(g.math("MULTIPLY", crust, 0.6), rcol, (0.025, 0.014, 0.01))
    col = g.mix(g.ramp(tone, 0.3, 0.7), steel, tuple(c * 1.5 for c in steel))
    col = g.mix(cover, col, rcol)
    height = g.math("ADD", g.math("MULTIPLY", cover, 0.4), g.math("MULTIPLY", g.math("ADD", g.math("SUBTRACT", 1.0, pits), g.math("MULTIPLY", t2, 0.6)), 0.25 * 1.0))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crust, 0.5))
    rough = g.mixf(cover, 0.62, 0.93)
    metal = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cover), 0.55)
    # Paint
    if paint is not None:
        pa = g.math("ADD", g.noise(4.0 * scale, detail=6.0, roughness=0.65, distortion=0.6, vector=cs),
                    g.math("MULTIPLY", g.math("SUBTRACT", g.noise(55.0 * scale, detail=4.0, vector=cs), 0.5), 0.3 * flake))
        pcov = g.ramp(pa, 0.74 - 0.5 * paint_left, 0.8 - 0.5 * paint_left)
        pedge = g.math("MULTIPLY", g.ramp(pa, 0.7 - 0.5 * paint_left, 0.74 - 0.5 * paint_left), g.math("SUBTRACT", 1.0, pcov))
        pc = g.mix(g.ramp(g.noise(8.0 * scale, detail=4.0, vector=cs), 0.3, 0.7), tuple(c * 0.78 for c in paint), paint)
        chalk = g.math("MULTIPLY", g.ramp(g.noise(30.0 * scale, detail=3.0, vector=cs), 0.45, 0.8), 0.35)
        pc = g.mix(chalk, pc, tuple(min(1.0, c * 1.5 + 0.03) for c in paint))
        col = g.mix(g.math("MULTIPLY", pedge, 0.6), col, tuple(c * 0.4 for c in paint))
        col = g.mix(pcov, col, pc)
        height = g.mixf(pcov, height, g.math("ADD", 0.55, g.math("MULTIPLY", t2, 0.1)))
        rough = g.mixf(pcov, rough, 0.58)
        metal = g.math("MULTIPLY", metal, g.math("SUBTRACT", 1.0, pcov))
    # Rust runs
    st = ks._stretched(g, (3.4 * scale, 3.4 * scale, 0.32 * scale))
    run = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=st), 0.5, 0.72), g.ramp(ks._normal_z(g), 0.9, 0.2))
    run = g.math("MULTIPLY", run, 0.55 * streak)
    col = g.mix(run, col, (0.14, 0.058, 0.024))
    # Grime in the crevices, earth near the ground, dust on tops
    cav = g.cavity(0.05)
    dirt = g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.3), grime)
    dirt = g.math("MULTIPLY", dirt, g.ramp(g.noise(8.0, detail=5.0), 0.25, 0.62))
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, (0.026, 0.02, 0.015))
    low = g.math("MULTIPLY", g.ramp(z, ground + 0.2, ground - 0.02), g.ramp(g.noise(25.0, detail=5.0), 0.22, 0.58))
    col = g.mix(g.math("MULTIPLY", low, 0.9), col, g.mix(g.ramp(g.noise(120.0), 0.3, 0.7), (0.035, 0.026, 0.017), (0.075, 0.055, 0.035)))
    dust = g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.55, 0.95), g.ramp(g.noise(12.0, detail=5.0), 0.38, 0.66))
    col = g.mix(g.math("MULTIPLY", dust, 0.4), col, (0.12, 0.1, 0.075))
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        mm = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.math("ADD", g.math("MULTIPLY", ks._normal_z(g), 0.6), g.noise(6.0, detail=5.0)), 0.7, 1.0), g.ramp(z, ground + 0.5, ground)), moss)
        col = g.mix(mm, col, tk.grade(g, mcol, sat=0.9, value=0.9))
        height = g.mixf(mm, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.6)))
        rough = g.mixf(mm, rough, mrough)
        metal = g.math("MULTIPLY", metal, g.math("SUBTRACT", 1.0, mm))
    rough = g.mixf(dirt, rough, 0.9)
    return grade(g, col), metal, rough, height


def rust_mat(name, relief=0.0025, **kw):
    mat, g = tk.new_material(name)
    col, metal, rough, height = rust_surface(g, **kw)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 1.0, relief))


def alum_mat(name, bleach=1.0, rust_stain=1.0, ground=G, seed=0.0, relief=0.0018, moss=0.5):
    """Old anodised-aluminium tube: dull grey with white powdery oxide in blotches and pits, dark road-dirt grime, orange
    rust bleeding from the steel rivets, scratches, green algae toward the ground."""
    mat, g = tk.new_material(name)
    co = g.coords()
    z = g.separate(co)[2]
    sh = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(co, sh.inputs[0])
    sh.inputs[1].default_value = (seed * 2.7, seed * 1.3, seed * 3.9)
    cs = sh.outputs[0]
    tone = g.noise(4.0, detail=5.0, vector=cs)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.1, 0.103, 0.105), (0.2, 0.205, 0.21))
    scr = g.math("MULTIPLY", g.ramp(kf._ridged(g, g.noise(1.0, detail=2.0, vector=ks._stretched(g, (500.0, 36.0, 36.0)))), 0.82, 0.96), 0.4)
    col = g.mix(scr, col, (0.5, 0.5, 0.5))
    cells, cr = kf._cells(g, 190.0, kf._warped(g, 16.0, 0.004, cs))
    bloom = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0, distortion=0.5, vector=cs), 0.42, 0.66), bleach)
    powder = g.math("MULTIPLY", g.ramp(cells, 0.5, 0.18), bloom)
    col = g.mix(g.math("MULTIPLY", powder, 0.9), col, g.mix(g.ramp(cr, 0.2, 0.9), (0.42, 0.42, 0.4), (0.58, 0.58, 0.55)))
    pit = g.math("MULTIPLY", g.ramp(cells, 0.2, 0.05), g.ramp(g.noise(14.0, detail=4.0, vector=cs), 0.45, 0.7))
    col = g.mix(g.math("MULTIPLY", pit, 0.85), col, (0.03, 0.03, 0.03))
    st = ks._stretched(g, (4.0, 4.0, 0.4))
    run = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=st), 0.5, 0.72), g.ramp(ks._normal_z(g), 0.95, 0.15))
    col = g.mix(g.math("MULTIPLY", run, 0.5), col, (0.075, 0.07, 0.065))
    rs = g.math("MULTIPLY", g.ramp(g.noise(20.0, detail=5.0, distortion=0.5, vector=cs), 0.62, 0.78), rust_stain)
    rs = g.math("MULTIPLY", rs, g.ramp(g.noise(3.0, vector=cs), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", rs, 0.8), col, g.mix(g.ramp(g.noise(110.0), 0.3, 0.7), (0.15, 0.062, 0.026), (0.26, 0.12, 0.045)))
    cav = g.cavity(0.04)
    dirt = g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.4), g.ramp(g.noise(8.0, detail=5.0), 0.25, 0.6))
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, (0.03, 0.026, 0.02))
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g, 0.8)
        mm = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0), 0.5, 0.72), g.ramp(z, ground + 0.4, ground)), moss)
        col = g.mix(g.math("MULTIPLY", mm, 0.8), col, tk.grade(g, mcol, sat=0.85, value=0.85))
    low = g.math("MULTIPLY", g.ramp(z, ground + 0.12, ground - 0.02), g.ramp(g.noise(30.0, detail=4.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", low, 0.9), col, (0.045, 0.033, 0.022))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", powder, 0.5), g.math("MULTIPLY", g.noise(300.0, detail=2.0), 0.2)), g.math("MULTIPLY", pit, 0.7))
    rough = g.mixf(powder, 0.5, 0.88)
    metal = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("MAXIMUM", powder, g.math("MAXIMUM", rs, pit))), 0.4)
    return tk.finish(mat, g, grade(g, col), metal, rough, g.bump(height, 1.0, relief))


def rubber_mat(name, center, euler_deg, k=1.0, lettering=1.0, treadw=1.0, bald_amount=1.0, relief=0.0045, nb=37.0):
    """Old tire rubber (axis = the local z of the frame given by center and euler_deg; radii in meters scaled by k from a car tire's 0.29 m)."""
    mat, g = tk.new_material(name)
    L = local_coords(g, center, euler_deg)
    lx, ly, lz = g.separate(L)
    co = g.coords()
    z = g.separate(co)[2]
    nz = ks._normal_z(g)
    rho = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", lx, lx), g.math("MULTIPLY", ly, ly)))
    th = g.math("ARCTAN2", ly, lx)
    arc = g.math("MULTIPLY", th, 0.25 * k)
    az = g.math("ABSOLUTE", lz)
    sidew = g.math("MULTIPLY", g.ramp(az, 0.062 * k, 0.078 * k), g.ramp(rho, 0.2 * k, 0.215 * k))          # the sidewall proper
    treadm = g.math("MULTIPLY", g.ramp(rho, 0.282 * k, 0.289 * k), g.ramp(az, 0.066 * k * treadw, 0.052 * k * treadw))
    # base: black rubber, UV-bloomed brown-grey on the sunny parts, crazed
    tone = g.noise(4.0, detail=5.0, distortion=0.3)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.014, 0.014, 0.013), (0.03, 0.028, 0.025))
    bloom = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.5), 0.4, 0.68), g.ramp(nz, -0.2, 0.8))
    bloom = g.math("MULTIPLY", bloom, 0.6)
    col = g.mix(bloom, col, g.mix(g.ramp(g.noise(90.0, detail=3.0), 0.3, 0.7), (0.08, 0.07, 0.06), (0.14, 0.12, 0.1)))
    # ozone cracking: a net of fine splits, long round the wheel
    vec = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("MULTIPLY", arc, 95.0 / k), vec.inputs[0])
    g.links.new(g.math("MULTIPLY", rho, 210.0 / k), vec.inputs[1])
    g.links.new(g.math("MULTIPLY", lz, 210.0 / k), vec.inputs[2])
    ce = kf._voronoi(g, 1.0, kf._warped(g, 18.0, 0.0035, vec.outputs[0]), feature="DISTANCE_TO_EDGE")
    crazing = g.math("MULTIPLY", g.ramp(ce, 0.045, 0.0), g.math("ADD", g.math("MULTIPLY", sidew, 0.7), 0.3))
    crazing = g.math("MULTIPLY", crazing, g.ramp(g.noise(3.5, detail=3.0), 0.28, 0.5))
    ce2 = kf._voronoi(g, 9.0, kf._warped(g, 8.0, 0.012), feature="DISTANCE_TO_EDGE")
    deep = g.math("MULTIPLY", g.ramp(ce2, 0.035, 0.0), g.ramp(g.noise(2.5, detail=3.0), 0.5, 0.7))
    deep = g.math("MULTIPLY", deep, g.math("ADD", sidew, g.math("MULTIPLY", treadm, 0.4)))
    col = g.mix(g.math("MULTIPLY", g.math("MAXIMUM", crazing, deep), 0.9), col, (0.004, 0.004, 0.004))
    # moulded lettering and ribs on the sidewall, worn and dusty
    word = scribble(g, arc, g.math("SUBTRACT", rho, 0.236 * k), cell=0.0165 * k, height=0.0235 * k, seed=5.0, stroke=0.0034 * max(k, 0.7), density=0.9 * lettering)
    wband = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", rho, 0.234 * k), 0.0, 0.002), g.ramp(g.math("SUBTRACT", 0.262 * k, rho), 0.0, 0.002))
    wmask = g.math("MULTIPLY", g.math("MULTIPLY", word, wband), g.math("MULTIPLY", g.ramp(az, 0.06 * k, 0.07 * k), g.ramp(g.noise(3.0, detail=3.0), 0.2, 0.5)))
    ribs = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", rho, 190.0 / k)), 0.5)), 0.5, 0.3), g.ramp(rho, 0.207 * k, 0.213 * k))
    ribs = g.math("MULTIPLY", ribs, g.ramp(rho, 0.236 * k, 0.222 * k))
    col = g.mix(g.math("MULTIPLY", wmask, 0.55), col, (0.1, 0.09, 0.08))
    # tread: transverse blocks and lengthwise grooves, worn bald in the middle, packed with mud
    phase = g.math("ADD", g.math("MULTIPLY", g.math("DIVIDE", th, math.tau), nb), g.math("MULTIPLY", lz, 3.2 / k))
    fr = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", phase), 0.5))
    groove_t = g.ramp(fr, 0.36, 0.46)
    groove_c = g.ramp(g.math("SUBTRACT", 0.0085 * k, g.math("ABSOLUTE", g.math("SUBTRACT", az, 0.043 * k))), 0.0, 0.004 * k)
    bald = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.35, 0.55), g.ramp(az, 0.05 * k, 0.015 * k)), bald_amount)
    groove = g.math("MAXIMUM", groove_t, groove_c)
    groove = g.math("MULTIPLY", groove, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", bald, 0.85)))
    groove = g.math("MULTIPLY", groove, treadm)
    mud = g.math("MULTIPLY", groove, g.ramp(g.noise(12.0, detail=4.0), 0.25, 0.6))
    col = g.mix(g.math("MULTIPLY", treadm, g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=4.0), 0.4, 0.7), 0.5)), col, (0.045, 0.04, 0.034))
    col = g.mix(g.math("MULTIPLY", mud, 0.8), col, (0.045, 0.032, 0.02))
    col = g.mix(g.math("MULTIPLY", groove, 0.5), col, (0.006, 0.006, 0.005))
    # steel cord showing through the worn crown
    cord = g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=4.0), 0.68, 0.76), g.math("MULTIPLY", bald, g.ramp(az, 0.025 * k, 0.0)))
    col = g.mix(g.math("MULTIPLY", cord, 0.8), col, (0.2, 0.085, 0.035))
    # moss in the cracks of the lower sidewall and the bead, damp soil
    mcol, mh, mrough, _ = kf.moss_layer(g, 0.8)
    low = g.ramp(z, G + 0.2, G + 0.0)
    mm = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.4), 0.52, 0.7), g.math("MAXIMUM", low, g.ramp(rho, 0.205 * k, 0.18 * k))), 0.9)
    col = g.mix(g.math("MULTIPLY", mm, 0.75), col, tk.grade(g, mcol, sat=0.85, value=0.9))
    cav = g.cavity(0.02)
    caked = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), g.ramp(g.noise(8.0, detail=5.0), 0.28, 0.6))
    col = g.mix(g.math("MULTIPLY", caked, 0.8), col, (0.035, 0.025, 0.016))
    soilm = g.math("MULTIPLY", g.ramp(z, G + 0.13, G - 0.01), g.ramp(g.noise(24.0, detail=5.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", soilm, 0.95), col, g.mix(g.ramp(g.noise(110.0), 0.3, 0.7), (0.033, 0.024, 0.015), (0.07, 0.05, 0.033)))
    dust = g.math("MULTIPLY", g.ramp(nz, 0.45, 0.95), g.ramp(g.noise(10.0, detail=5.0), 0.4, 0.68))
    col = g.mix(g.math("MULTIPLY", dust, 0.4), col, (0.1, 0.085, 0.065))
    # height: tread blocks, cracks, lettering, ribs
    height = g.math("ADD", 0.55, g.math("MULTIPLY", g.noise(160.0, detail=3.0), 0.12))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", groove, 0.5))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MAXIMUM", crazing, deep), 0.5))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", wmask, 0.35), g.math("MULTIPLY", ribs, 0.18)))
    height = g.mixf(mm, height, g.math("ADD", 0.45, g.math("MULTIPLY", mh, 0.5)))
    rough = g.mixf(bloom, 0.8, 0.94)
    rough = g.mixf(mm, rough, mrough)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.95), 0.0, rough, g.bump(height, 1.0, relief))




# ================================================================ export and previews

def forest_floor(name="PreviewFloor"):
    """A dark litter-and-soil floor for the previews, so a mound's blend into the ground can be judged."""
    mat, g = tk.new_material(name)
    t = g.noise(6.0, detail=5.0)
    col = g.mix(g.ramp(t, 0.3, 0.7), (0.03, 0.022, 0.014), (0.07, 0.05, 0.03))
    cells, r = kf._cells(g, 34.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(r, 0.6, 0.9), 0.5), col, (0.16, 0.085, 0.035))
    gr = g.math("MULTIPLY", g.ramp(g.noise(2.5, detail=4.0), 0.5, 0.72), 0.7)
    col = g.mix(gr, col, (0.05, 0.085, 0.025))
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(g.noise(120.0, detail=4.0), 0.5, 0.01))


def preview(name, model, shots, out_dir, floor=0.45, figure=(1.1, 0.6)):
    """Renders `shots` ([(label, camera location, target, lens)]) on the preview stage (a soil floor, the 1.8 m figure)."""
    tk.preview_stage()
    fl = bpy.data.objects.get("Floor")
    if fl is not None:
        fl.scale = (floor * 3.0, floor * 3.0, 1.0)
        fl.data.materials.clear()
        fl.data.materials.append(forest_floor())
    for n in ("ScaleFigure", "ScaleHead"):
        o = bpy.data.objects.get(n)
        if o is not None:
            o.location.x, o.location.y = figure[0], figure[1]
    os.makedirs(out_dir, exist_ok=True)
    only = os.environ.get("SK_SHOTS")
    for label, loc, tgt, lens in shots:
        if only and label not in only.split(","):
            continue
        tk.render(tk.camera(name + label, loc, tgt, lens=lens), os.path.join(out_dir, "%s_%s.png" % (name.lower(), label)),
                  res=(800, 600) if FAST else (1000, 750), samples=10 if FAST else 16)


def standard_shots(top, reach=0.55, cx=0.0, cy=0.0):
    """Far (7 m), mid (3 m), close (1 m), two angles, and a top view for a prop of height `top` m above the ground."""
    f = Vector((cx, cy, G + top * 0.45))
    return [
        ("far", Vector((5.0, -5.0, G + 1.7)), Vector((0.0, 0.0, G + top * 0.4)), 40),
        ("mid", f + Vector((1.1, -2.3, 0.7)), f, 40),
        ("close", f + Vector((0.45, -0.85, 0.4)).normalized() * (0.55 + reach), f, 40),
        ("back", f + Vector((-0.6, 1.0, 0.4)).normalized() * (0.8 + reach), f, 40),
        ("top", Vector((cx + 0.15, cy - 0.25, G + 1.9 + reach)), Vector((cx, cy, G)), 40),
    ]


def finish_export(name, b, bodies, out_dir, size, density, boxes=None, extra=(), voxel=0.06, margin=0.012, limit=100, coarse=0.5,
                  rect=False, probes=()):
    pieces = b.objects()
    tris = 0
    if FAST:
        size = 512
    for o in pieces:
        n = ks.triangles([o])
        tris += n
        print("  %s %d" % (o.name, n))
    if LIVE:
        return tk.join(pieces, name)
    boxes = list(boxes or [])
    if bodies:
        boxes += fk.voxel_boxes(bodies, voxel, margin, limit=limit)
    model = lk.export(name, pieces, [], out_dir, size=size, density=density, voxel=voxel, extra=extra, rect=rect, limit=limit,
                      coarse=coarse, probes=probes, boxes=boxes)
    return model


def bounds_report(name, model):
    vs = [model.matrix_world @ v.co for v in model.data.vertices]
    xs, ys, zs = [v.x for v in vs], [v.y for v in vs], [v.z for v in vs]
    print("[%s] mesh extents x %.2f..%.2f y %.2f..%.2f height %.2f m above the ground" % (name, min(xs), max(xs), min(ys), max(ys), max(zs) - G))
    return max(abs(min(xs)), abs(max(xs))), max(abs(min(ys)), abs(max(ys))), max(zs) - G
