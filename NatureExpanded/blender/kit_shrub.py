"""Shrub kit: what Nature Expanded's bushes and logs need on top of naturekit.py (WildRose, Elderberry, Sumac,
MossyLog, CharredShrub, Winterberry, FrostedJuniper, DeadBrush).

A bush is thousands of small parts, so this kit doesn't make an object per leaf: a Builder collects the geometry per
material into one mesh each (`b.mesh(material)`), and `b.objects()` hands them to `export`. Every vertex still gets
naturekit's "t" (0 at a part's base, 1 at its tip), so nk.plant / nk.petal shade as usual.

- `export` is nk.export with a far LOD made by leaving parts out instead of decimating (nk.export's decimate collapses
  every 2-triangle leaf to a sliver, so a bush's LOD1 is bare sticks): while building, `b.lod = 1` marks parts the far
  LOD drops (thorns, twigs, most leaflets), `b.lod_scale` grows the parts it keeps about their own base so fewer
  still cover the bush, and `b.lod = 2` marks big smooth surfaces (a log's trunk) that are decimated on their own.
  `lod_preview` renders that LOD.
- Woody skeletons: `grow` one branch (a wandering polyline that arches under `gravity`), `branch_out` side branches
  off it, `fit` keeps them in the footprint, `wood` meshes them as tapered bark tubes (`tube`), `thorn`.
- Cheap foliage: `leaf` (2 triangles folded along the midrib, or rows for longer leaves), `petal` (a broad notched
  petal), `flower` (a ring of them round a center), `compound_leaf` (pinnate: rose, elder, sumac), `fern` fronds.
  They arch with `bent`, which rotates the midline, so upright leaves keep their length (nk.blade's bend shrinks them).
- Fruit and flowers: `berry` (a smooth low-poly ball), `flat_cyme` (an elderflower plate).
- Snow, ground and fungi: `snow_lumps` along branches, `ground_patch` (ash, soil, snow), `shelf_fungus`.
- Materials: `bark`, `char`, `snow`, `moss`, `ash`.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import naturekit as nk
import zkit as tk

G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))
SNOW = (0.86, 0.89, 0.95)


# ---------------------------------------------------------------- mesh builder

class _Mesh:
    def __init__(self, builder):
        self.b = builder
        self.bm = bmesh.new()
        self.ts = []
        self.pivots = []
        self.scales = []
        self.lods = []
        self.pivot = Vector()

    def begin(self, pivot):
        """Starts a part (a leaf, a petal, a berry): its vertices grow about `pivot` in the far LOD."""
        self.pivot = Vector(pivot)

    def v(self, co, t):
        self.ts.append(t)
        self.pivots.append(self.pivot)
        self.scales.append(self.b.lod_scale)
        return self.bm.verts.new(co)

    def f(self, verts, smooth=False):
        try:
            face = self.bm.faces.new(verts)
        except ValueError:
            return None
        face.smooth = smooth
        self.lods.append(self.b.lod)
        return face


class Builder:
    """Collects a plant's geometry per material, so a bush is a handful of meshes rather than thousands of objects.

    The far LOD (see `export`) is made by leaving parts out rather than decimating (which collapses every small leaf
    to a sliver): set `b.lod = 1` while making parts the far LOD can do without (thorns, twigs, some of the leaves),
    and `b.lod_scale` > 1 to enlarge the parts it keeps there, so fewer leaves still cover the bush."""

    def __init__(self, name):
        self.name = name
        self.meshes = {}
        self.lod = 0
        self.lod_scale = 1.0

    def mesh(self, material):
        entry = self.meshes.get(material.name)
        if entry is None:
            entry = self.meshes[material.name] = (_Mesh(self), material)
        return entry[0]

    def objects(self):
        out = []
        for key, (m, material) in self.meshes.items():
            if not m.bm.faces:
                m.bm.free()
                continue
            obj = tk.mesh_object(self.name + key, m.bm, material)
            nk._set_t(obj, m.ts)
            me = obj.data
            lod = me.attributes.new("lod", "INT", "FACE")
            lod.data.foreach_set("value", m.lods)
            sc = me.attributes.new("lodscale", "FLOAT", "POINT")
            sc.data.foreach_set("value", m.scales)
            pv = me.attributes.new("pivot", "FLOAT_VECTOR", "POINT")
            pv.data.foreach_set("vector", [c for p in m.pivots for c in p])
            out.append(obj)
        self.meshes = {}
        return out


def triangles(objs):
    return sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in objs)


# ---------------------------------------------------------------- frames

def basis(axis):
    """(axis, u, v) with u x v = axis: a ring u*cos(a) + v*sin(a) runs counter-clockwise round the axis."""
    ax = Vector(axis).normalized()
    u = ax.cross(UP)
    if u.length < 1e-4:
        u = ax.cross(Vector((1.0, 0.0, 0.0)))
    u.normalize()
    return ax, u, ax.cross(u)


def _leaf_frame(direction, normal=None, roll=0.0):
    """(d, side, up) for a sheet along `direction` whose face points `up` (toward `normal` if given, else up-ish),
    with side x d = up, the winding naturekit's blades use."""
    d = Vector(direction).normalized()
    side = d.cross(Vector(normal) if normal is not None else UP)
    if side.length < 1e-4:
        side = d.cross(Vector((1.0, 0.0, 0.0)))
    side.normalize()
    up = side.cross(d).normalized()
    if roll:
        rot = Matrix.Rotation(math.radians(roll), 3, d)
        side, up = rot @ side, rot @ up
    return d, side, up


def frames(points):
    """Parallel-transport frames (tangent, normal, binormal) along a polyline, for tubes that don't twist."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    tans = []
    for i in range(n):
        d = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        tans.append(d.normalized() if d.length > 1e-9 else UP.copy())
    nrm = tans[0].cross(UP)
    if nrm.length < 1e-4:
        nrm = tans[0].cross(Vector((1.0, 0.0, 0.0)))
    nrm.normalize()
    out = []
    for i, t in enumerate(tans):
        if i:
            nrm = tans[i - 1].rotation_difference(t) @ nrm
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


def _bend_axis(d):
    """The horizontal axis a midline along `d` turns about to arch outward and down (square to d)."""
    h = Vector((d.x, d.y, 0.0))
    if h.length < 1e-4:
        h = Vector((1.0, 0.0, 0.0))
    return UP.cross(h.normalized()).normalized()


def bent(base, d, length, bend, s):
    """The point at fraction s along a midline from `base` along `d`, arching outward and down by `bend` quarter
    turns at the tip (negative curls it up). It rotates the midline rather than pulling it toward -Z (naturekit's
    blade does that, which shortens near-upright blades), so a leaf keeps its length however upright it starts."""
    d = Vector(d).normalized()
    axis = _bend_axis(d)
    p = Vector(base)
    n = 8
    k = s * n
    i = 0
    while i < k - 1e-9:
        step = min(1.0, k - i)
        u = (i + 0.5 * step) / n
        ang = bend * u * u * math.pi * 0.5
        p = p + (Matrix.Rotation(ang, 3, axis) @ d) * (length / n) * step
        i += 1
    return p


def bent_tangent(base, d, length, bend, s):
    a, b = bent(base, d, length, bend, max(0.0, s - 0.02)), bent(base, d, length, bend, min(1.0, s + 0.02))
    return (b - a).normalized()


# ---------------------------------------------------------------- tubes and branches

def tube(b, material, points, radii, sides=4, t0=0.0, t1=1.0, cap=True, squash=1.0, smooth=True, start_cap=False,
         jag=0.0, rnd=None):
    """A tapered tube along a polyline, one radius per point; a radius of 0 closes it to a point there. `squash`
    flattens it vertically (snow on a twig). `jag` makes the end ring ragged (a broken stick)."""
    pts = [Vector(p) for p in points]
    fr = frames(pts)
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    total = acc[-1] or 1.0
    m = b.mesh(material)
    m.begin(pts[0])
    saved, b.lod_scale = b.lod_scale, 1.0
    rings = []
    last = len(pts) - 1
    for i, p in enumerate(pts):
        t = t0 + (t1 - t0) * acc[i] / total
        r = radii[i]
        if r <= 1e-6:
            rings.append([m.v(p, t)])
            continue
        tan, nr, bn = fr[i]
        ring = []
        for k in range(sides):
            a = k / sides * math.tau
            off = nr * math.cos(a) + bn * math.sin(a)
            if squash != 1.0:
                off.z *= squash
            q = p + off * r
            if jag and i == last and rnd is not None:
                q = q + tan * (r * jag * rnd.uniform(-1.0, 1.0))
            ring.append(m.v(q, t))
        rings.append(ring)
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for k in range(sides):
            k1 = (k + 1) % sides
            if len(B) == 1:
                m.f((A[k], A[k1], B[0]), smooth)
            elif len(A) == 1:
                m.f((A[0], B[k1], B[k]), smooth)
            else:
                m.f((A[k], A[k1], B[k1], B[k]), smooth)
    if cap and len(rings[-1]) > 2:
        m.f(rings[-1])
    if start_cap and len(rings[0]) > 2:
        m.f(list(reversed(rings[0])))
    b.lod_scale = saved
    return rings


class Branch:
    """A branch's polyline and radii; `at(s)` gives position, direction, radius and t at fraction s along it."""

    def __init__(self, points, radii, level=0, t0=0.0, t1=1.0):
        self.points = [Vector(p) for p in points]
        self.radii = list(radii)
        self.level = level
        self.t0, self.t1 = t0, t1
        self.cum = [0.0]
        for i in range(1, len(self.points)):
            self.cum.append(self.cum[-1] + (self.points[i] - self.points[i - 1]).length)
        self.length = self.cum[-1]
        self.broken = False

    def at(self, s):
        target = max(0.0, min(1.0, s)) * self.length
        for i in range(1, len(self.points)):
            if self.cum[i] >= target or i == len(self.points) - 1:
                seg = self.cum[i] - self.cum[i - 1]
                f = max(0.0, min(1.0, (target - self.cum[i - 1]) / seg)) if seg > 1e-9 else 0.0
                p = self.points[i - 1].lerp(self.points[i], f)
                d = (self.points[i] - self.points[i - 1]).normalized()
                r = self.radii[i - 1] + (self.radii[i] - self.radii[i - 1]) * f
                return p, d, r, self.t0 + (self.t1 - self.t0) * s
        return self.points[-1], self.tip_dir, self.radii[-1], self.t1

    @property
    def tip(self):
        return self.points[-1]

    @property
    def tip_dir(self):
        return (self.points[-1] - self.points[-2]).normalized()


def grow(rnd, root, direction, length, radius, tip_radius=0.0, segments=5, gravity=0.0, wander=0.1, level=0, t0=0.0,
         t1=1.0, floor=G + 0.012, arch=False, kink=0.0):
    """One branch from `root` heading along `direction`: `segments` steps that wander at random and bend toward the
    ground by `gravity` per meter (negative lifts). `arch` makes the bending grow toward the tip, like a cane bowed by
    its own leaves; `kink` adds sudden zig-zags (dead brush). It tapers from `radius` to `tip_radius`."""
    d = Vector(direction).normalized()
    p = Vector(root)
    pts = [p.copy()]
    step = length / segments
    for i in range(segments):
        if i:
            j = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * wander
            if kink and rnd.random() < kink:
                j = j + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5))) * 0.6
            g = gravity * step * ((2.0 * i / segments) if arch else 1.0)
            d = (d + j + DOWN * g).normalized()
        p = p + d * step
        if p.z < floor:
            p.z = floor
            d.z = max(d.z, 0.05)
            d.normalize()
        pts.append(p.copy())
    radii = [radius + (tip_radius - radius) * (i / segments) ** 0.85 for i in range(segments + 1)]
    return Branch(pts, radii, level, t0, t1)


def branch_out(rnd, parent, count, s_range=(0.3, 0.95), length=(0.1, 0.2), angle=(35.0, 60.0), radius_ratio=0.6,
               segments=3, gravity=0.0, wander=0.1, tip_radius=0.0, lift=0.0, shrink=0.0, arch=False, kink=0.0):
    """`count` side branches spiraling off `parent` between fractions s_range, each `angle` degrees off it, lifted
    toward the sky by `lift`; `shrink` shortens the ones near the tip."""
    kids = []
    phase = rnd.uniform(0, math.tau)
    for i in range(count):
        s = s_range[0] + (s_range[1] - s_range[0]) * (i + rnd.uniform(0.15, 0.85)) / count
        p, tan, r, t = parent.at(s)
        _, u, v = basis(tan)
        a = phase + i * 2.39996 + rnd.uniform(-0.3, 0.3)
        out = u * math.cos(a) + v * math.sin(a)
        ang = math.radians(rnd.uniform(*angle))
        d = (tan * math.cos(ang) + out * math.sin(ang) + UP * lift).normalized()
        L = rnd.uniform(*length) * (1.0 - shrink * s)
        kids.append(grow(rnd, p, d, L, max(r * radius_ratio, 0.0008), tip_radius, segments, gravity, wander,
                         parent.level + 1, t, min(1.0, t + 0.4), arch=arch, kink=kink))
    return kids


def fit(branches, radius):
    """Squeezes branches toward the Z axis so none reaches past `radius` (keeps a bush inside its footprint)."""
    far = max(math.hypot(p.x, p.y) for br in branches for p in br.points)
    if far > radius:
        k = radius / far
        for br in branches:
            for p in br.points:
                p.x *= k
                p.y *= k
            br.__init__(br.points, br.radii, br.level, br.t0, br.t1)
    return branches


def wood(b, material, branches, sides=(5, 4, 3, 3), jag=0.0, rnd=None):
    """Meshes branches as bark tubes, `sides` by level. Branches whose tip radius isn't 0 get a cap (broken ends,
    ragged by `jag`)."""
    for br in branches:
        n = sides[min(br.level, len(sides) - 1)]
        tube(b, material, br.points, br.radii, n, br.t0, br.t1, cap=br.radii[-1] > 1e-6,
             jag=jag if br.radii[-1] > 1e-6 else 0.0, rnd=rnd)


def thorn(b, material, branch, s, size, rnd):
    """A prickle on a branch at fraction s, hooked back toward the base (3 triangles)."""
    p, tan, r, t = branch.at(s)
    _, u, v = basis(tan)
    a = rnd.uniform(0, math.tau)
    out = u * math.cos(a) + v * math.sin(a)
    ax, u2, v2 = basis(out)
    m = b.mesh(material)
    base = p + out * (r * 0.8)
    m.begin(base)
    tip = m.v(base + (out - tan * 0.45).normalized() * size, 1.0)
    ring = [m.v(base + (u2 * math.cos(k / 3 * math.tau) + v2 * math.sin(k / 3 * math.tau)) * size * 0.32, 0.2)
            for k in range(3)]
    for k in range(3):
        m.f((tip, ring[k], ring[(k + 1) % 3]), True)


def spiral_points(rnd, branch, count, s_range=(0.2, 1.0), angle=(40.0, 70.0), lift=0.3):
    """`count` points spiraling along a branch, each with a direction leaning out from it (for leaves, flowers and
    fruit): [(position, direction, tangent, s)]."""
    out = []
    phase = rnd.uniform(0, math.tau)
    for i in range(count):
        s = s_range[0] + (s_range[1] - s_range[0]) * (i + rnd.uniform(0.2, 0.8)) / max(1, count)
        p, tan, r, t = branch.at(s)
        _, u, v = basis(tan)
        a = phase + i * 2.39996 + rnd.uniform(-0.25, 0.25)
        o = u * math.cos(a) + v * math.sin(a)
        ang = math.radians(rnd.uniform(*angle))
        d = (tan * math.cos(ang) + o * math.sin(ang) + UP * lift).normalized()
        out.append((p, d, tan, s))
    return out


# ---------------------------------------------------------------- leaves, petals, flowers

def _width(profile, s):
    if profile == "lance":
        return max(0.0, (1.0 - s) ** 0.8 * min(1.0, s * 3.0 + 0.15))
    if profile == "spoon":
        return min(1.0, 0.25 + s * 1.2) * (math.sin(math.pi * min(s, 0.999)) ** 0.25 if s > 0.6 else 1.0)
    if profile == "heart":
        return (1.0 - s) ** 0.6
    if profile == "strap":
        return 1.0 if s < 0.85 else (1.0 - s) / 0.15
    return math.sin(math.pi * s) ** 0.7


_ROW = {"oval": 0.5, "lance": 0.33, "spoon": 0.62, "heart": 0.25, "strap": 0.6, "needle": 0.15}


def leaf(b, material, base, direction, length, width, bend=0.15, fold=0.25, profile="oval", rows=1, roll=0.0,
         normal=None, t0=0.0, t1=1.0):
    """A single-sheet leaf. rows=1 is a diamond of 2 triangles folded along its midrib by `fold` (small leaves,
    leaflets, needles); rows>1 follows the profile with that many rows (2 triangles a row, 4 when folded). `normal`
    is the way its face should point (default: up-ish)."""
    d, side, up = _leaf_frame(direction, normal, roll)
    m = b.mesh(material)
    base = Vector(base)
    m.begin(base)
    B = m.v(base, t0)
    T = m.v(bent(base, d, length, bend, 1.0), t1)
    hw = width * 0.5
    if rows == 1:
        s = _ROW.get(profile, 0.5)
        c = bent(base, d, length, bend, s)
        tt = t0 + (t1 - t0) * s
        L = m.v(c - side * hw + up * (fold * hw), tt)
        R = m.v(c + side * hw + up * (fold * hw), tt)
        m.f((B, R, T))
        m.f((B, T, L))
        return
    rowsv = []
    for i in range(rows):
        s = (i + 1) / (rows + 1)
        c = bent(base, d, length, bend, s)
        w = _width(profile, s) * hw
        tt = t0 + (t1 - t0) * s
        if fold:
            rowsv.append((m.v(c - side * w + up * (fold * w), tt), m.v(c, tt), m.v(c + side * w + up * (fold * w), tt)))
        else:
            rowsv.append((m.v(c - side * w, tt), None, m.v(c + side * w, tt)))
    L1, C1, R1 = rowsv[0]
    if C1:
        m.f((B, R1, C1))
        m.f((B, C1, L1))
    else:
        m.f((B, R1, L1))
    for (La, Ca, Ra), (Lb, Cb, Rb) in zip(rowsv, rowsv[1:]):
        if Ca:
            m.f((La, Ca, Cb, Lb))
            m.f((Ca, Ra, Rb, Cb))
        else:
            m.f((La, Ra, Rb, Lb))
    Ln, Cn, Rn = rowsv[-1]
    if Cn:
        m.f((Ln, Cn, T))
        m.f((Cn, Rn, T))
    else:
        m.f((Ln, Rn, T))


def petal(b, material, base, direction, length, width, normal=None, bend=0.0, notch=0.08, cup=0.0):
    """A broad petal (rose, mallow, buttercup) in 4 triangles: narrow at the base, widest near its end, with a
    shallow notch in the middle of the end. `cup` lifts its sides."""
    d, side, up = _leaf_frame(direction, normal)
    m = b.mesh(material)
    base = Vector(base)
    m.begin(base)
    hw = width * 0.5
    B = m.v(base, 0.0)
    c1 = bent(base, d, length, bend, 0.42)
    c2 = bent(base, d, length, bend, 0.92)
    L1 = m.v(c1 - side * hw * 0.8 + up * cup * hw, 0.42)
    R1 = m.v(c1 + side * hw * 0.8 + up * cup * hw, 0.42)
    L2 = m.v(c2 - side * hw + up * cup * hw * 1.2, 0.95)
    R2 = m.v(c2 + side * hw + up * cup * hw * 1.2, 0.95)
    N = m.v(bent(base, d, length, bend, 0.92 + 0.08 - notch), 1.0)
    m.f((B, R1, L1))
    m.f((L1, R1, N))
    m.f((L1, N, L2))
    m.f((R1, R2, N))


def disc_fan(b, material, center, axis, radius, sides=6, dome=0.0, t=1.0, smooth=True):
    """A flat polygon facing `axis`, its middle raised by `dome`: a flower's center, a seed head's face."""
    ax, u, v = basis(axis)
    m = b.mesh(material)
    m.begin(center)
    c = m.v(Vector(center) + ax * dome, t)
    rim = [m.v(Vector(center) + (u * math.cos(k / sides * math.tau) + v * math.sin(k / sides * math.tau)) * radius,
               t * 0.85) for k in range(sides)]
    for k in range(sides):
        m.f((c, rim[k], rim[(k + 1) % sides]), smooth)


def flower(b, petal_mat, center_mat, center, axis, rnd, petals=5, length=0.03, width=0.032, cup=0.12, bend=0.0,
           center_r=0.009, center_h=0.004, notch=0.08):
    """An open single flower (wild rose, mallow, strawberry): a ring of broad notched petals facing `axis` around a
    domed center. Each petal sits a hair higher than the last so overlaps don't flicker."""
    ax, u, v = basis(axis)
    a0 = rnd.uniform(0, math.tau)
    c = Vector(center)
    for i in range(petals):
        a = a0 + (i + rnd.uniform(-0.08, 0.08)) / petals * math.tau
        out = u * math.cos(a) + v * math.sin(a)
        lift = (cup + rnd.uniform(-0.05, 0.05)) * math.pi * 0.5
        d = (out * math.cos(lift) + ax * math.sin(lift)).normalized()
        petal(b, petal_mat, c + ax * (0.0007 * i), d, length * rnd.uniform(0.88, 1.08), width, normal=ax, bend=bend,
              notch=notch, cup=0.12)
    disc_fan(b, center_mat, c + ax * 0.004, ax, center_r, sides=6, dome=center_h)


def compound_leaf(b, material, base, direction, length, leaflets, leaflet_len, leaflet_w, rnd, rachis_mat=None,
                  rachis_r=0.0015, bend=0.25, spread=60.0, droop=0.08, fold=0.3, profile="lance", rows=1, taper=0.3,
                  start=0.22, leaflet_bend=0.12, terminal=True, normal=None, rachis_segs=4, far=None):
    """A pinnate leaf (rose, elder, sumac, ash): opposite pairs of leaflets along a rachis `length` long that arches by
    `bend`, plus a terminal leaflet; leaflets near the base smaller by `taper`. The leaflets lie in the leaf's plane.
    `far` = (share, scale): the far LOD keeps that share of the leaflets, grown by scale, and drops the rachis."""
    d, side, up = _leaf_frame(direction, normal)
    pairs = (leaflets - 1) // 2 if terminal else leaflets // 2
    saved = b.lod, b.lod_scale

    def pick():
        if far is not None:
            b.lod, b.lod_scale = (saved[0], far[1]) if rnd.random() < far[0] else (1, 1.0)

    if far is not None:
        b.lod = 1
    if rachis_mat is not None:
        pts = [bent(base, d, length, bend, i / rachis_segs) for i in range(rachis_segs + 1)]
        tube(b, rachis_mat, pts, [rachis_r * (1.0 - 0.6 * i / rachis_segs) for i in range(rachis_segs + 1)], sides=3,
             cap=False)
    for j in range(pairs):
        s = start + (0.94 - start) * (j / max(1, pairs - 1)) if pairs > 1 else 0.6
        p = bent(base, d, length, bend, s)
        tan = bent_tangent(base, d, length, bend, s)
        lup = side.cross(tan).normalized()
        size = 1.0 - taper * (1.0 - s)
        sp = math.radians(spread + rnd.uniform(-8, 8))
        for sgn in (-1.0, 1.0):
            ld = (tan * math.cos(sp) + side * (sgn * math.sin(sp)) + DOWN * droop).normalized()
            pick()
            leaf(b, material, p, ld, leaflet_len * size * rnd.uniform(0.9, 1.1), leaflet_w * size, bend=leaflet_bend,
                 fold=fold, profile=profile, rows=rows, normal=lup, roll=rnd.uniform(-10, 10))
    if terminal:
        p = bent(base, d, length, bend, 1.0)
        tan = bent_tangent(base, d, length, bend, 1.0)
        pick()
        leaf(b, material, p - tan * (leaflet_len * 0.05), tan, leaflet_len * 1.05, leaflet_w, bend=leaflet_bend,
             fold=fold, profile=profile, rows=rows, normal=side.cross(tan))
    b.lod, b.lod_scale = saved


def fern(b, material, root, rnd, fronds=7, length=(0.35, 0.55), pinnae=14, pinna_len=0.075, pinna_w=0.02,
         rachis_mat=None, tilt=(30.0, 65.0), bend=(0.5, 0.9), away=None, arc=220.0, far=None):
    """A clump of arching fern fronds from `root`: each a rachis with pairs of pinnae, longest a third of the way
    up and shrinking to the tip. `away` (an angle in degrees) fans the fronds over `arc` degrees round that way
    (a fern beside a log leans away from it). `far` = (share, scale) as in compound_leaf."""
    root = Vector(root)
    saved = b.lod, b.lod_scale
    for i in range(fronds):
        if away is None:
            a = i / fronds * math.tau + rnd.uniform(-0.3, 0.3)
        else:
            a = math.radians(away + arc * ((i + 0.5) / fronds - 0.5) + rnd.uniform(-8, 8))
        tl = math.radians(rnd.uniform(*tilt))
        d = Vector((math.cos(a) * math.sin(tl), math.sin(a) * math.sin(tl), math.cos(tl)))
        L = rnd.uniform(*length)
        bd = rnd.uniform(*bend)
        _, side, _ = _leaf_frame(d)
        pts = [bent(root, d, L, bd, k / 5) for k in range(6)]
        if far is not None:
            b.lod = 1
        tube(b, rachis_mat or material, pts, [0.0028, 0.0024, 0.002, 0.0015, 0.001, 0.0], sides=3, cap=False)
        for j in range(pinnae):
            s = 0.14 + 0.82 * j / (pinnae - 1)
            p = bent(root, d, L, bd, s)
            tan = bent_tangent(root, d, L, bd, s)
            up = side.cross(tan).normalized()
            size = (1.0 - s) ** 0.6 * min(1.0, (s + 0.12) * 2.6) + 0.12
            for sgn in (-1.0, 1.0):
                ld = (tan * 0.4 + side * sgn).normalized()
                if far is not None:
                    b.lod, b.lod_scale = (saved[0], far[1]) if rnd.random() < far[0] else (1, 1.0)
                leaf(b, material, p, ld, pinna_len * size * L / 0.45, pinna_w * (0.6 + 0.4 * size), bend=0.12,
                     fold=0.2, profile="lance", normal=up)
    b.lod, b.lod_scale = saved


# ---------------------------------------------------------------- fruit and flower heads

def berry(b, material, center, radius, rnd=None, sides=5, stretch=1.0, axis=(0.0, 0.0, 1.0)):
    """A small round fruit: a ring of `sides` between two poles (2*sides triangles), smooth shaded so it reads
    round; `stretch` lengthens it along `axis` (rose hips)."""
    ax, u, v = basis(axis)
    m = b.mesh(material)
    c = Vector(center)
    m.begin(c)
    a0 = rnd.uniform(0, math.tau) if rnd else 0.0
    top = m.v(c + ax * radius * stretch, 1.0)
    bot = m.v(c - ax * radius * stretch, 0.3)
    ring = [m.v(c + (u * math.cos(a0 + k / sides * math.tau) + v * math.sin(a0 + k / sides * math.tau)) * radius
                + ax * radius * 0.1, 0.75) for k in range(sides)]
    for k in range(sides):
        k1 = (k + 1) % sides
        m.f((top, ring[k], ring[k1]), True)
        m.f((bot, ring[k1], ring[k]), True)


def floret(b, material, center, axis, size, rnd, sides=5):
    """A tiny flat flower (a polygon of `sides`, sides-2 triangles), tilted a little at random."""
    tilt = Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35)))
    ax, u, v = basis(Vector(axis).normalized() + tilt)
    m = b.mesh(material)
    m.begin(center)
    a0 = rnd.uniform(0, math.tau)
    vs = [m.v(Vector(center) + (u * math.cos(a0 + k / sides * math.tau) + v * math.sin(a0 + k / sides * math.tau))
              * size * 0.5, 1.0) for k in range(sides)]
    for k in range(1, sides - 1):
        m.f((vs[0], vs[k], vs[k + 1]))


def flat_cyme(b, floret_mat, plate_mat, ray_mat, top, axis, radius, rnd, florets=40, size=0.008, rays=5, dome=0.12,
              plate=True, forks=3, floret_sides=5, far_florets=0.3):
    """A flat-topped head of tiny flowers on branching rays (elderflower, yarrow): `rays` stalks from `top` fork into
    secondaries whose ends carry the florets, over a shadowed plate (so it reads solid from afar). Returns the ray
    ends (for berries instead of florets, pass florets=0)."""
    ax, u, v = basis(axis)
    top = Vector(top)
    h = radius * 0.5
    ends = []
    lod = b.lod
    b.lod = 1
    for i in range(rays):
        a = (i + rnd.uniform(-0.15, 0.15)) / rays * math.tau
        out = u * math.cos(a) + v * math.sin(a)
        node = top + out * radius * rnd.uniform(0.3, 0.45) + ax * h * 0.55
        tube(b, ray_mat, [top, node], [0.0016, 0.0012], sides=3, cap=False)
        for j in range(forks):
            a2 = a + (j - (forks - 1) * 0.5) * 0.55 + rnd.uniform(-0.15, 0.15)
            o2 = u * math.cos(a2) + v * math.sin(a2)
            rr = radius * rnd.uniform(0.55, 0.95)
            end = top + o2 * rr + ax * h * (1.0 + dome * (1.0 - (rr / radius) ** 2))
            tube(b, ray_mat, [node, end], [0.0011, 0.0008], sides=3, cap=False)
            ends.append(end)
    b.lod = lod
    if plate:
        m = b.mesh(plate_mat)
        c = top + ax * (h * (1.0 + dome) - 0.004)
        m.begin(c)
        cv = m.v(c, 0.6)
        n = 10
        rim = []
        for k in range(n):
            a = k / n * math.tau
            rr = radius * 0.82 * rnd.uniform(0.85, 1.05)
            rim.append(m.v(top + (u * math.cos(a) + v * math.sin(a)) * rr + ax * (h - 0.006), 0.5))
        for k in range(n):
            m.f((cv, rim[k], rim[(k + 1) % n]), True)
    for k in range(florets):
        e = ends[k % len(ends)]
        a = rnd.uniform(0, math.tau)
        q = radius * 0.2 * math.sqrt(rnd.random())
        at = e + (u * math.cos(a) + v * math.sin(a)) * q + ax * rnd.uniform(-0.002, 0.004)
        # The far LOD keeps a share of the florets, grown, over the plate
        far = rnd.random() < far_florets
        b.lod, scale, b.lod_scale = (lod, b.lod_scale, 1.6) if far else (1, b.lod_scale, 1.0)
        floret(b, floret_mat, at, ax, size * rnd.uniform(0.8, 1.15), rnd, sides=floret_sides)
        b.lod, b.lod_scale = lod, scale
    return ends


# ---------------------------------------------------------------- snow, ground, fungi

def snow_lumps(b, material, branches, rnd, chance=0.5, min_radius=0.0015, length=(0.04, 0.12), thick=1.8,
               max_slope=0.65, min_z=-1.0):
    """Little pillows of snow lying along the flatter branch segments (each 20 triangles)."""
    count = 0
    for br in branches:
        for i in range(len(br.points) - 1):
            p0, p1 = br.points[i], br.points[i + 1]
            dv = p1 - p0
            if dv.length < 0.02:
                continue
            t = dv.normalized()
            if abs(t.z) > max_slope or rnd.random() > chance or min(p0.z, p1.z) < min_z:
                continue
            r = (br.radii[i] + br.radii[i + 1]) * 0.5
            if r < min_radius:
                continue
            L = min(dv.length * 0.95, rnd.uniform(*length))
            s0 = rnd.uniform(0.0, max(0.0, dv.length - L)) / dv.length
            a = p0 + dv * s0
            e = a + t * L
            w = max(r * thick, 0.005)
            lift = Vector((0.0, 0.0, r * 0.75 + w * 0.2))
            pts = [a + lift, a.lerp(e, 0.2) + lift, a.lerp(e, 0.75) + lift, e + lift]
            tube(b, material, pts, [0.0, w, w * 0.85, 0.0], sides=5, squash=0.55, t0=1.0, t1=1.0)
            count += 1
    return count


def ground_patch(b, material, center, radius, rnd, sides=14, dome=0.015, jitter=0.25, sink=0.004, rings=2):
    """A low irregular mound lying on the ground (ash, soil, snow, leaf litter): a fan round a raised middle,
    its rim sunk just below the ground so it blends."""
    m = b.mesh(material)
    cx, cy = center
    m.begin((cx, cy, G))
    c = m.v((cx, cy, G + dome), 1.0)
    prev = None
    rows = []
    for ring in range(1, rings + 1):
        f = ring / rings
        row = []
        for k in range(sides):
            a = k / sides * math.tau
            rr = radius * f * (1.0 + rnd.uniform(-jitter, jitter) * f)
            z = G + dome * (1.0 - f * f) * rnd.uniform(0.6, 1.3) - (sink if ring == rings else 0.0)
            row.append(m.v((cx + rr * math.cos(a), cy + rr * math.sin(a), z), 1.0 - 0.5 * f))
        rows.append(row)
    for k in range(sides):
        m.f((c, rows[0][k], rows[0][(k + 1) % sides]), True)
    for A, B in zip(rows, rows[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            m.f((A[k], B[k], B[k1], A[k1]), True)


def shelf_fungus(b, top_mat, under_mat, attach, outward, radius, rnd, thickness=0.02, depth=0.75, segs=7):
    """A bracket fungus on a trunk's side: a half-round shelf `radius` wide sticking out `depth` x radius along
    `outward` (horizontal), domed on top (t runs 0 at the trunk to 1 at the rim, for growth bands), flat and pale
    underneath."""
    o = Vector((outward[0], outward[1], 0.0)).normalized()
    s = UP.cross(o)
    attach = Vector(attach)
    phase = rnd.uniform(0, math.tau)
    mt, mb = b.mesh(top_mat), b.mesh(under_mat)
    mt.begin(attach)
    mb.begin(attach)

    def rim_point(a, f, z):
        wav = 1.0 + 0.07 * math.sin(3.0 * a + phase)
        return attach + (o * (math.cos(a) * depth) + s * math.sin(a)) * radius * f * wav + UP * z

    angles = [-math.pi * 0.5 + math.pi * k / segs for k in range(segs + 1)]
    droop = [rnd.uniform(-0.25, 0.25) * thickness for _ in angles]
    c = mt.v(attach + UP * thickness, 0.0)
    inner = [mt.v(rim_point(a, 0.55, thickness * 0.8), 0.55) for a in angles]
    rim = [mt.v(rim_point(a, 1.0, thickness * 0.25 + dz), 1.0) for a, dz in zip(angles, droop)]
    for k in range(segs):
        mt.f((c, inner[k], inner[k + 1]), True)
        mt.f((inner[k], rim[k], rim[k + 1], inner[k + 1]), True)
    cb = mb.v(attach, 0.0)
    bot = [mb.v(rim_point(a, 0.97, dz * 0.5), 1.0) for a, dz in zip(angles, droop)]
    edge = [mb.v(rim_point(a, 1.0, thickness * 0.25 + dz), 1.0) for a, dz in zip(angles, droop)]
    for k in range(segs):
        mb.f((cb, bot[k + 1], bot[k]), True)
        mb.f((bot[k], bot[k + 1], edge[k + 1], edge[k]), True)


# ---------------------------------------------------------------- materials

def _attr(g, name):
    return g.node("ShaderNodeAttribute", attribute_name=name).outputs["Fac"]


def _normal_z(g):
    return g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]


def _stretched(g, scale):
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    return m.outputs[0]


def _snow_dust(g, col, rough, amount, scale=18.0):
    mask = g.math("MULTIPLY", g.ramp(_normal_z(g), 0.3, 0.75), g.ramp(g.noise(scale, detail=3.0), 0.28, 0.5))
    mask = g.math("MULTIPLY", mask, amount, clamp=True)
    return g.mix(mask, col, SNOW), g.mixf(mask, rough, 0.6), mask


def bark(name, color, color2=None, rough=0.85, grain=40.0, lichen=None, lichen_amount=0.0, snow=0.0, dots=0.0,
         dot_color=None, base_dark=0.65, sat=0.9, value=0.9, fuzz=0.0):
    """Bark for stems and twigs: fibrous streaks running up the stem, blotches, darker toward each stem's base (t),
    optional pale lenticel `dots`, `lichen` patches, `snow` dusting on the up-facing sides, and `fuzz` (a velvety
    sheen, staghorn sumac)."""
    mat, g = tk.new_material(name)
    c2 = color2 or tuple(c * 0.6 for c in color)
    fib = g.noise(1.0, detail=5.0, roughness=0.6, vector=_stretched(g, (grain, grain, grain * 0.12)))
    col = g.mix(g.ramp(fib, 0.3, 0.7), color, c2)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=3.0), 0.45, 0.75), 0.5), col,
                tuple(c * 0.6 for c in color))
    col = g.mix(g.ramp(_attr(g, "t"), 0.0, 0.5), tuple(c * base_dark for c in c2), col)
    height = g.math("MULTIPLY", fib, 0.6)
    if dots:
        vor = g.node("ShaderNodeTexVoronoi")
        g._in(vor, "Scale", 1.0)
        g.links.new(_stretched(g, (260.0, 260.0, 90.0)), vor.inputs["Vector"])
        dot = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.16, 0.08), dots)
        col = g.mix(dot, col, dot_color or tuple(min(1.0, c * 1.9 + 0.06) for c in color))
        height = g.math("ADD", height, g.math("MULTIPLY", dot, 0.5))
    if lichen is not None and lichen_amount:
        lm = g.math("MULTIPLY", g.ramp(g.noise(11.0, detail=6.0, distortion=0.3), 0.62 - 0.2 * lichen_amount, 0.68 -
                                       0.2 * lichen_amount), lichen_amount * 1.5, clamp=True)
        col = g.mix(lm, col, lichen)
        height = g.math("ADD", height, g.math("MULTIPLY", lm, 0.4))
    r = rough
    if fuzz:
        # Velvet can't be view-dependent once baked: lighten the surface a touch in a fine fuzzy grain instead
        hair = g.ramp(g.noise(300.0, detail=2.0), 0.4, 0.7)
        col = g.mix(g.math("MULTIPLY", hair, fuzz * 0.5), col, tuple(min(1.0, c * 1.7 + 0.05) for c in color))
        r = min(1.0, rough + 0.1)
    rr = r
    if snow:
        col, rr, _ = _snow_dust(g, col, r, snow)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rr, g.bump(height, 0.3, 0.002))


def char(name, ash_amount=0.5):
    """Charred wood: near-black blocks split by deep cracks across and along the grain (alligator char), a dull
    sheen on the blocks, grey ash settled on the up-facing sides. No glow."""
    mat, g = tk.new_material(name)
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", 1.0)
    g.links.new(_stretched(g, (95.0, 95.0, 45.0)), vor.inputs["Vector"])
    crack = g.ramp(tk._sock(vor.outputs, "Distance"), 0.0, 0.09)
    tone = g.noise(9.0, detail=4.0)
    block = g.mix(g.ramp(tone, 0.35, 0.75), (0.028, 0.025, 0.023), (0.07, 0.062, 0.055))
    col = g.mix(crack, (0.006, 0.005, 0.005), block)
    # Brown, half-burnt wood showing low on the stems
    brown = g.math("MULTIPLY", g.ramp(_attr(g, "t"), 0.25, 0.0), g.ramp(g.noise(6.0, detail=5.0), 0.5, 0.7))
    col = g.mix(brown, col, (0.12, 0.07, 0.04))
    rough = g.mixf(crack, 0.95, 0.5)
    if ash_amount:
        m = g.math("MULTIPLY", g.ramp(_normal_z(g), 0.4, 0.85), g.ramp(g.noise(14.0, detail=4.0), 0.4, 0.62))
        m = g.math("MULTIPLY", m, ash_amount, clamp=True)
        col = g.mix(m, col, (0.32, 0.31, 0.3))
        rough = g.mixf(m, rough, 0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(crack, 0.6, 0.002))


def snow(name, shade=SNOW):
    """Fresh snow: white going faintly blue in the dips, soft grain."""
    mat, g = tk.new_material(name)
    n = g.noise(22.0, detail=3.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), tuple(c * 0.86 for c in shade), shade)
    return tk.finish(mat, g, col, 0.0, 0.55, g.bump(g.noise(140.0), 0.2, 0.002))


def moss(name, color=(0.1, 0.18, 0.03), color2=(0.2, 0.25, 0.05), sat=0.95, value=0.85):
    """A cushion of moss: fine fuzz in two greens, brighter on top, very rough."""
    mat, g = tk.new_material(name)
    fine = g.noise(160.0, detail=6.0, roughness=0.7)
    patch = g.noise(9.0, detail=4.0)
    col = g.mix(g.ramp(patch, 0.35, 0.7), color, color2)
    col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.4, 0.7), 0.6), col, tuple(c * 0.55 for c in color))
    col = g.mix(g.math("MULTIPLY", g.ramp(_normal_z(g), 0.2, 0.9), 0.4), tuple(c * 0.75 for c in color), col)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(fine, 0.5, 0.002))


def ash(name, rim=(0.1, 0.085, 0.07)):
    """Grey wood ash with darker charcoal specks and pale flakes, thinning to soil (`rim`) at the edge of a
    ground_patch (t runs 1 in the middle to 0.5 at the rim) so the mound melts into the ground."""
    mat, g = tk.new_material(name)
    n = g.noise(14.0, detail=5.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), (0.2, 0.195, 0.19), (0.4, 0.39, 0.37))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 70.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    specks = g.ramp(tk._sock(vor.outputs, "Distance"), 0.14, 0.06)
    col = g.mix(g.math("MULTIPLY", specks, g.ramp(g.noise(5.0), 0.45, 0.6)), col, (0.025, 0.022, 0.02))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(45.0, detail=3.0), 0.66, 0.75), 0.7), col, (0.62, 0.61, 0.58))
    if rim is not None:
        edge = g.ramp(g.math("ADD", _attr(g, "t"), g.math("MULTIPLY", g.noise(9.0, detail=4.0), 0.25)), 0.72, 0.9)
        col = g.mix(edge, rim, col)
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(g.noise(60.0, detail=5.0), 0.4, 0.002))


# ---------------------------------------------------------------- export

def _far_lod(obj, coarse_ratio=0.4):
    """Turns a copy of the baked plant into its far LOD: drops the faces marked lod=1, grows each kept part about
    its pivot by its lodscale, and decimates the faces marked lod=2 to `coarse_ratio`. It shares the atlas."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lod = bm.faces.layers.int.get("lod")
    sc = bm.verts.layers.float.get("lodscale")
    pv = bm.verts.layers.float_vector.get("pivot")
    if sc is not None and pv is not None:
        for v in bm.verts:
            k = v[sc]
            if k > 0.0 and abs(k - 1.0) > 1e-4:
                p = Vector(v[pv])
                v.co = p + (v.co - p) * k
    coarse = False
    if lod is not None:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lod] == 1], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        coarse = any(f[lod] == 2 for f in bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    if not coarse:
        return obj
    # Faces marked lod=2 (a log's body, a trunk) are decimated on their own, so the small parts keep their shape
    dup = obj.copy()
    dup.data = obj.data.copy()
    tk.link(dup)
    for o, keep in ((obj, lambda v: v != 2), (dup, lambda v: v == 2)):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        layer = bm.faces.layers.int.get("lod")
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f[layer])], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
    mod = dup.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = coarse_ratio
    tk.apply_modifiers(dup)
    tk.triangulate(dup)
    name = obj.name
    return tk.join([obj, dup], name)


def _strip(obj):
    for name in ("lod", "lodscale", "pivot"):
        a = obj.data.attributes.get(name)
        if a is not None:
            obj.data.attributes.remove(a)


def export(name, pieces, out_dir, size=1024, coarse_ratio=0.4, density=None):
    """nk.export with a far LOD made by leaving parts out (see Builder) instead of decimating: bakes every piece into
    one atlas (<name>_Albedo/_Normal/_RMOM.png) and writes <name>.fbx with <name> and <name>_LOD1 (same atlas).
    `density` weights the atlas between materials (nk.weighted_uvs)."""
    folder = os.path.join(out_dir, name)
    os.makedirs(folder, exist_ok=True)
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("Bake")
    atlas = tk.triangulate(tk.join(pieces, name))
    if density:
        nk.weighted_uvs(atlas, density)
    else:
        tk.smart_uvs(atlas)
    nk.texel_report(atlas, size)
    paths = tk.bake_atlas(atlas, folder, name, size=size)
    baked = tk.baked_material(name, paths)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    lod = atlas.copy()
    lod.data = atlas.data.copy()
    lod.name = name + "_LOD1"
    tk.link(lod)
    lod = _far_lod(lod, coarse_ratio)
    _strip(atlas)
    _strip(lod)
    tk.export_fbx([atlas, lod], os.path.join(folder, name + ".fbx"))
    print("[%s] %d triangles, LOD1 %d" % (name, triangles([atlas]), triangles([lod])))
    lod.hide_render = True
    return atlas


# ---------------------------------------------------------------- previews

def lod_preview(script, name, out_dir, focus_height=0.0, distance=1.6):
    """A front render of the far LOD (nk.export hides it), to check that the decimation kept the color."""
    model = bpy.data.objects.get(name)
    lod = bpy.data.objects.get(name + "_LOD1")
    if model is None or lod is None:
        return
    model.hide_render = True
    lod.hide_render = False
    f = Vector((0.0, 0.0, focus_height))
    loc = f + Vector((0.25, -1.0, 0.3)).normalized() * distance
    tk.render(tk.camera(script + "lod", loc, f, lens=50), os.path.join(out_dir, "%s_lod.png" % script), samples=32)
    model.hide_render = False
    lod.hide_render = True


# ---------------------------------------------------------------- lacy heads, smooth leaves, checks
# Added for Elderberry and QueenAnnesLace; nothing above uses them. Parts made while `b.lod = FAR` exist only in the
# far LOD (cheap stand-ins: fewer, bigger florets or berries): export such plants with kit_lod.export, which knows the
# value and moves those parts aside while the atlas bakes (this kit's own `export` only drops lod 1).

FAR = 3


def _across(d, face=None):
    """A unit vector square to `d`, as near to `face` as it can be (horizontal if `face` is None or runs along d)."""
    d = Vector(d).normalized()
    if face is not None:
        f = Vector(face)
        w = f - d * f.dot(d)
        if w.length > 0.2 * f.length:
            return w.normalized()
    w = d.cross(UP)
    if w.length < 1e-4:
        w = d.cross(Vector((1.0, 0.0, 0.0)))
    return w.normalized()


def ribbon(b, material, points, widths, face=None, t0=0.0, t1=1.0):
    """A flat strip along a polyline, one width per point (0 closes it to a point): a pedicel, ray or rachis at 2
    triangles a segment, which unlike a very thin tube doesn't shrink to a flickering hairline. Its width lies across
    the line toward `face` (give a head's axis: it then shows from the side and from below; a leaf's side vector: it
    lies in the leaf). A strip running nearly along `face` has no good way to lie, and any fixed one is edge-on from
    some side, so that one is made a 3-sided tube as wide instead."""
    pts = [Vector(p) for p in points]
    chord = pts[-1] - pts[0]
    if face is not None and chord.length > 1e-7:
        f = Vector(face).normalized()
        if (f - chord.normalized() * f.dot(chord.normalized())).length < 0.35:
            tube(b, material, pts, [w * 0.58 for w in widths], sides=3, cap=False, t0=t0, t1=t1)
            return
    w0 = _across(chord if chord.length > 1e-7 else UP, face)
    m = b.mesh(material)
    m.begin(pts[0])
    saved, b.lod_scale = b.lod_scale, 1.0
    n = len(pts)
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    total = acc[-1] or 1.0
    rows = []
    for i, p in enumerate(pts):
        tan = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        tan = tan.normalized() if tan.length > 1e-9 else UP
        w = w0 - tan * w0.dot(tan)
        w = w.normalized() if w.length > 1e-4 else w0
        t = t0 + (t1 - t0) * acc[i] / total
        hw = widths[i] * 0.5
        rows.append([m.v(p, t)] if hw <= 1e-6 else [m.v(p - w * hw, t), m.v(p + w * hw, t)])
    for A, B in zip(rows, rows[1:]):
        if len(A) == 2 and len(B) == 2:
            m.f((A[0], A[1], B[1], B[0]), True)
        elif len(A) == 2:
            m.f((A[0], A[1], B[0]), True)
        elif len(B) == 2:
            m.f((A[0], B[1], B[0]), True)
    b.lod_scale = saved


def star_floret(b, material, center, axis, radius, rnd, petals=5, gap=0.2, cup=0.12, anchor=None, reach=0.7):
    """A tiny open flower: `petals` wedge petals, one triangle each, round a middle vertex, `gap` of each petal's
    share of the circle left open between them, the rim lifted `cup` of the radius toward `axis`. The middle carries
    t 0 and the rim t 1, so a ramp material gives it a colored eye. With `anchor` it is moved so that the anchor lies
    on its first petal, `reach` of the way out (`center` then only says which side of the anchor it sits on): a floret
    at the side of a cluster touching the pedicel end that carries it. Returns its center."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    half = math.pi / petals * (1.0 - gap)
    c = Vector(center)
    a0 = rnd.uniform(0.0, math.tau)
    if anchor is not None:
        e = Vector(anchor) - c
        e = e - ax * e.dot(ax)
        if e.length > 1e-7:
            e.normalize()
            a0 = math.atan2(e.dot(v), e.dot(u))
            c = Vector(anchor) - e * (reach * radius * math.cos(half)) - ax * (reach * cup * radius)
    m = b.mesh(material)
    m.begin(c)
    mid = m.v(c, 0.0)
    for k in range(petals):
        a = a0 + k / petals * math.tau + (rnd.uniform(-0.1, 0.1) if k else 0.0)
        r = radius * (rnd.uniform(0.86, 1.08) if k else 1.0)
        lift = ax * (cup * r)
        A = m.v(c + (u * math.cos(a - half) + v * math.sin(a - half)) * r + lift, 1.0)
        B = m.v(c + (u * math.cos(a + half) + v * math.sin(a + half)) * r + lift, 1.0)
        m.f((mid, A, B), True)
    return c


def poly_floret(b, material, center, axis, radius, rnd, sides=5, anchor=None, reach=0.6, t=1.0, wobble=0.15):
    """A very small flower as one flat, slightly uneven polygon (sides-2 triangles): Queen Anne's lace florets.
    `anchor` as in star_floret: it then sits so the anchor lies `reach` of the way from its middle to its first
    corner. Returns its center."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    c = Vector(center)
    a0 = rnd.uniform(0.0, math.tau)
    if anchor is not None:
        e = Vector(anchor) - c
        e = e - ax * e.dot(ax)
        if e.length > 1e-7:
            e.normalize()
            a0 = math.atan2(e.dot(v), e.dot(u))
            c = Vector(anchor) - e * (reach * radius)
    m = b.mesh(material)
    m.begin(c)
    vs = []
    for k in range(sides):
        a = a0 + (k + (rnd.uniform(-wobble, wobble) if k else 0.0)) / sides * math.tau
        r = radius * (rnd.uniform(1.0 - wobble, 1.0 + wobble * 0.5) if k else 1.0)
        vs.append(m.v(c + (u * math.cos(a) + v * math.sin(a)) * r, t))
    for k in range(1, sides - 1):
        m.f((vs[0], vs[k], vs[k + 1]), True)
    return c


def leaflet(b, material, base, direction, length, width, normal=None, bend=0.15, sweep=0.0, fold=0.3, twist=0.0,
            rows=((0.1, 0.55), (0.3, 0.96), (0.55, 0.9), (0.8, 0.5)), t0=0.0, t1=1.0):
    """A smooth single-sheet leaflet (or simple leaf) with a soft fold along its midrib: an outline through `rows`
    ((s, w): w of `width` at s of the way along) closing to a pointed tip, the edges lifted `fold` of the half width
    toward its face, the midline arching down by `bend` (quarter turns at the tip, as `bent`) and curving sideways by
    `sweep` (of its length, at the tip; positive toward its side vector), twisted `twist` degrees. One smooth-shaded
    fan of triangles round the midrib at the widest row: 2 * len(rows) + 2 triangles."""
    d, side, up = _leaf_frame(direction, normal)
    base = Vector(base)

    def mid(s):
        return bent(base, d, length, bend, s) + side * (sweep * length * s * s)

    def frame(s):
        tan = (mid(min(1.0, s + 0.02)) - mid(max(0.0, s - 0.02))).normalized()
        sd = side - tan * side.dot(tan)
        sd = sd.normalized() if sd.length > 1e-5 else side
        if twist:
            sd = Matrix.Rotation(math.radians(twist * s), 3, tan) @ sd
        return sd, sd.cross(tan).normalized()

    m = b.mesh(material)
    m.begin(base)
    k = max(range(len(rows)), key=lambda i: rows[i][1])
    M = m.v(mid(rows[k][0]), t0 + (t1 - t0) * rows[k][0])
    right, left = [], []
    for s, w in rows:
        sd, upv = frame(s)
        c = mid(s)
        hw = width * 0.5 * w
        tt = t0 + (t1 - t0) * s
        right.append(m.v(c + sd * hw + upv * (fold * hw), tt))
        left.append(m.v(c - sd * hw + upv * (fold * hw), tt))
    B = m.v(base, t0)
    T = m.v(mid(1.0), t1)
    ring = [B] + right + [T] + list(reversed(left))
    for i in range(len(ring)):
        m.f((M, ring[i], ring[(i + 1) % len(ring)]), True)


def pinnate_leaf(b, leaf_mat, rachis_mat, base, direction, length, leaflets, leaflet_len, leaflet_w, rnd,
                 normal=None, bend=0.25, petiole=0.2, spread=(55.0, 70.0), droop=0.12, taper=0.22, fold=0.3,
                 leaflet_bend=0.2, sweep=0.06, width=0.0034, far=None, rows=None):
    """A big pinnate leaf (elder, ash, walnut): a rachis strip `length` long arching by `bend`, bare for its first
    `petiole`, then opposite pairs of smooth `leaflet`s spaced evenly and one at the tip (`leaflets` odd). The rachis
    stops at the tip leaflet's base, so nothing pokes out past the last leaflet; the leaflets curve a little toward
    the tip. `far` = (keep, scale): with chance `keep` the far LOD keeps this leaf (its rachis,
    the tip leaflet and every other pair, grown `scale` about their bases, all still on the rachis), otherwise it
    drops it whole. `rows` is the leaflets' outline (see `leaflet`)."""
    d, side, up = _leaf_frame(direction, normal)
    base = Vector(base)
    pairs = max(0, (leaflets - 1) // 2)
    saved = b.lod, b.lod_scale
    kept = far is not None and rnd.random() < far[0]
    shape = {"rows": rows} if rows else {}

    def mode(keep):
        if far is None:
            b.lod, b.lod_scale = saved
        elif kept and keep:
            b.lod, b.lod_scale = saved[0], far[1]
        else:
            b.lod, b.lod_scale = 1, 1.0

    over = min(0.3, 0.24 * leaflet_len / length)
    s_tip = 1.0 - over
    step = (s_tip - petiole) / max(1, pairs) if pairs else 0.0
    # The rachis is a few straight segments from the base to the tip leaflet's base, where it stops; the leaflets sit
    # on them, not on the curve they cut across. Its strip is tilted half out of the leaf's plane, so it keeps its
    # width seen from the side as well as from above (flat in the leaf, it thins to a hairline edge-on)
    seg = 3
    pts = [bent(base, d, length, bend, s_tip * i / seg) for i in range(seg + 1)]

    def on(s):
        f = min(1.0, s / s_tip) * seg
        i = min(seg - 1, int(f))
        return pts[i].lerp(pts[i + 1], f - i), (pts[i + 1] - pts[i]).normalized()

    mode(True)
    ribbon(b, rachis_mat, pts, [width, width * 0.85, width * 0.7, width * 0.45], face=(side + up).normalized())
    for j in range(pairs):
        s = petiole + j * step
        p, tan = on(s)
        lup = side.cross(tan).normalized()
        size = 1.0 - taper * (1.0 - j / max(1, pairs))
        sp = math.radians(rnd.uniform(*spread))
        for sgn in (-1.0, 1.0):
            ld = (tan * math.cos(sp) + side * (sgn * math.sin(sp)) + DOWN * droop).normalized()
            mode((pairs - 1 - j) % 2 == 0)
            leaflet(b, leaf_mat, p, ld, leaflet_len * size * rnd.uniform(0.92, 1.06), leaflet_w * size, normal=lup,
                    bend=leaflet_bend * rnd.uniform(0.7, 1.3), sweep=-sgn * sweep * rnd.uniform(0.5, 1.4), fold=fold,
                    twist=rnd.uniform(-12, 12), **shape)
    p, tan = on(s_tip)
    mode(True)
    leaflet(b, leaf_mat, p, tan, leaflet_len * 1.08, leaflet_w * 1.02, normal=side.cross(tan), bend=bend * 0.5,
            sweep=rnd.uniform(-0.04, 0.04), fold=fold, twist=rnd.uniform(-8, 8), **shape)
    b.lod, b.lod_scale = saved


def cyme_layout(rnd, top, axis, radius, height, ends, rays=5, dome=0.15, node=(0.3, 0.42), node_h=(0.38, 0.52),
                split=3.0, depth=0.0, rim=0.94):
    """The branching of a compound cyme (elderflower, an elderberry bunch), without geometry: `rays` primary rays
    from `top` out to nodes `node` of the radius out and `node_h` of the height up, each forking into secondaries
    that end under groups of about `split` of the `ends` end points. The ends are spread evenly over a disc `radius`
    across, `height` up `axis`, domed by `dome` (the middle that much higher); `depth` scatters them up to that
    fraction of the height back down into the head (a bunch of berries rather than a flat top). Returns the
    primaries: [{"points": polyline, "node": its end, "groups": [{"node": secondary end, "ends": [points],
    "centroid": point on the top over the group's middle, "spread": its radius}]}]."""
    ax, u, v = basis(axis)
    top = Vector(top)
    R = radius

    def lift(r):
        return height * (1.0 + dome * (1.0 - min(1.0, r / R) ** 2))

    def at(x, y, z):
        return top + u * x + v * y + ax * z

    gap = R * math.sqrt(math.pi / max(1, ends)) * 0.82
    pts = []
    tries = 0
    while len(pts) < ends and tries < ends * 400:
        tries += 1
        a = rnd.uniform(0.0, math.tau)
        r = R * rim * math.sqrt(rnd.random())
        p = (r * math.cos(a), r * math.sin(a))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= gap * gap for q in pts):
            pts.append(p)
    phase = rnd.uniform(0.0, math.tau)
    prims = []
    for i in range(rays):
        a = phase + (i + rnd.uniform(-0.12, 0.12)) / rays * math.tau
        rr = R * rnd.uniform(*node)
        z = height * rnd.uniform(*node_h)
        out = u * math.cos(a) + v * math.sin(a)
        N = top + out * rr + ax * z
        ctrl = top + out * (rr * 0.62) + ax * (z * 0.18)
        mid = top * 0.25 + ctrl * 0.5 + N * 0.25
        prims.append({"xy": (rr * math.cos(a), rr * math.sin(a)), "z": z, "points": [top, mid, N], "node": N,
                      "ends": [], "groups": []})
    for p in pts:
        k = min(range(rays), key=lambda i: (p[0] - prims[i]["xy"][0]) ** 2 + (p[1] - prims[i]["xy"][1]) ** 2)
        prims[k]["ends"].append(p)
    for P in prims:
        es = P["ends"]
        if not es:
            continue
        nx, ny = P["xy"]
        k = max(1, min(4, int(round(len(es) / split))))
        es.sort(key=lambda q: math.atan2(q[1] - ny, q[0] - nx))
        cs = [es[int((j + 0.5) * len(es) / k)] for j in range(k)]
        gs = [es]
        for _ in range(8):
            gs = [[] for _ in cs]
            for q in es:
                j = min(range(len(cs)), key=lambda c: (q[0] - cs[c][0]) ** 2 + (q[1] - cs[c][1]) ** 2)
                gs[j].append(q)
            cs = [(sum(q[0] for q in g) / len(g), sum(q[1] for q in g) / len(g)) if g else c for g, c in zip(gs, cs)]
        for g, c in zip(gs, cs):
            if not g:
                continue
            f = rnd.uniform(0.45, 0.6)
            mx, my = nx + (c[0] - nx) * f, ny + (c[1] - ny) * f
            ztop = lift(math.hypot(c[0], c[1]))
            mz = P["z"] + (ztop - P["z"]) * rnd.uniform(0.45, 0.6)
            ends3 = []
            for q in g:
                z = lift(math.hypot(q[0], q[1]))
                if depth:
                    z -= height * depth * rnd.random() ** 1.5
                ends3.append(at(q[0], q[1], max(z, mz + 0.004)))
            spread = max(math.hypot(q[0] - c[0], q[1] - c[1]) for q in g)
            P["groups"].append({"node": at(mx, my, mz), "ends": ends3, "centroid": at(c[0], c[1], ztop),
                                "spread": spread})
    return prims


def flower_cyme(b, floret_mat, ray_mat, prims, axis, rnd, floret_r=0.0045, per=(2, 4), ray_r=0.0022, sec_r=0.0018,
                ped_w=0.003, far=True, far_ped=0.0045, sec_w=None, gap=0.2, reach=0.8, splay=(0.35, 0.6)):
    """Meshes a cyme_layout as a lacy flower head: primary and secondary rays as 3-sided tubes (kept in the far LOD),
    a flat pedicel to each end point carrying a little cluster of `per` star florets, the middle one on the pedicel's
    end and the others leaning out round it, each touching that end (near only); `sec_w` makes the secondaries flat
    strips that wide instead of tubes; `gap` and `reach` go to star_floret, `splay` is how far the side florets lean
    out (as a fraction of the axis). With `far`, the far LOD gets one
    bigger floret per secondary on its own coarser pedicel, as much white as the group's florets. Returns the floret
    count."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    saved = b.lod, b.lod_scale
    count = 0
    for P in prims:
        b.lod, b.lod_scale = saved[0], 1.0
        tube(b, ray_mat, P["points"], [ray_r, ray_r * 0.92, ray_r * 0.84], sides=3, cap=False, t0=0.2, t1=0.6)
        for g in P["groups"]:
            b.lod, b.lod_scale = saved[0], 1.0
            if sec_w:
                ribbon(b, ray_mat, [P["node"], g["node"]], [sec_w, sec_w * 0.9], face=ax, t0=0.6, t1=0.8)
            else:
                tube(b, ray_mat, [P["node"], g["node"]], [sec_r, sec_r * 0.9], sides=3, cap=False, t0=0.6, t1=0.8)
            b.lod = 1
            n_group = 0
            for E in g["ends"]:
                ribbon(b, ray_mat, [g["node"], E], [ped_w, ped_w * 0.9], face=ax, t0=0.8, t1=1.0)
                r0 = floret_r * rnd.uniform(0.9, 1.1)
                tilt = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.2
                star_floret(b, floret_mat, E, ax + tilt, r0, rnd, gap=gap)
                n = rnd.randint(per[0], per[1]) - 1
                a0 = rnd.uniform(0.0, math.tau)
                for k in range(n):
                    a = a0 + (k + rnd.uniform(-0.15, 0.15)) / max(1, n) * math.tau
                    o = u * math.cos(a) + v * math.sin(a)
                    star_floret(b, floret_mat, E + o * r0, (ax + o * rnd.uniform(*splay)).normalized(),
                                floret_r * rnd.uniform(0.85, 1.05), rnd, gap=gap, anchor=E, reach=reach)
                n_group += 1 + n
            count += n_group
            if far:
                b.lod = FAR
                C = g["centroid"]
                ribbon(b, ray_mat, [g["node"], C], [far_ped, far_ped * 0.85], face=ax, t0=0.8, t1=1.0)
                big = min(floret_r * math.sqrt(n_group) * 1.1, g["spread"] + floret_r * 1.5)
                star_floret(b, floret_mat, C, ax, big, rnd, gap=0.08, cup=0.1)
    b.lod, b.lod_scale = saved
    return count


def berry_bunch(b, berry_mats, stalk_mat, prims, axis, rnd, berry_r=0.0032, ray_r=0.0022, sec_r=0.0018,
                ped_w=0.003, far=True, far_ped=0.0042, far_size=1.9, sec_w=None, per=(1, 1), sides=4):
    """Meshes a cyme_layout as a bunch of berries hanging along `axis` (point it at the ground): rays as 3-sided
    tubes (kept in the far LOD), a flat pedicel to each end point with `per` berries hanging from it, each with its
    top on the pedicel's end (near only), each a ring of `sides` (2 * sides triangles). `berry_mats` is a list of (material, weight): ripe first, then unripe and so on. With
    `far`, the far LOD gets one bigger ripe berry per secondary on its own coarser pedicel. Returns the berry count."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    saved = b.lod, b.lod_scale
    total = sum(w for _, w in berry_mats)

    def pick():
        x = rnd.uniform(0.0, total)
        for mat, w in berry_mats:
            x -= w
            if x <= 0.0:
                return mat
        return berry_mats[0][0]

    count = 0
    for P in prims:
        b.lod, b.lod_scale = saved[0], 1.0
        tube(b, stalk_mat, P["points"], [ray_r, ray_r * 0.92, ray_r * 0.84], sides=3, cap=False, t0=0.2, t1=0.6)
        for g in P["groups"]:
            b.lod, b.lod_scale = saved[0], 1.0
            if sec_w:
                ribbon(b, stalk_mat, [P["node"], g["node"]], [sec_w, sec_w * 0.9], face=ax, t0=0.6, t1=0.8)
            else:
                tube(b, stalk_mat, [P["node"], g["node"]], [sec_r, sec_r * 0.9], sides=3, cap=False, t0=0.6, t1=0.8)
            b.lod = 1
            for E in g["ends"]:
                ribbon(b, stalk_mat, [g["node"], E], [ped_w, ped_w * 0.85], face=ax, t0=0.8, t1=1.0)
                k = rnd.randint(per[0], per[1])
                if k == 1:
                    hangs = [(ax + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.25)]
                else:
                    # A little cluster: each berry hangs off the pedicel's end at a slant, all touching it there
                    a0 = rnd.uniform(0.0, math.tau)
                    hangs = []
                    for j in range(k):
                        a = a0 + (j + rnd.uniform(-0.1, 0.1)) / k * math.tau
                        phi = math.radians(rnd.uniform(38.0, 52.0))
                        hangs.append(ax * math.cos(phi) + (u * math.cos(a) + v * math.sin(a)) * math.sin(phi))
                for hang in hangs:
                    hang = hang.normalized()
                    r = berry_r * rnd.uniform(0.85, 1.1)
                    berry(b, pick(), E + hang * r, r, rnd, sides=sides, axis=-hang)
                    count += 1
            if far:
                b.lod = FAR
                C = g["centroid"]
                ribbon(b, stalk_mat, [g["node"], C], [far_ped, far_ped * 0.85], face=ax, t0=0.8, t1=1.0)
                r = berry_r * min(far_size * 1.25, far_size * math.sqrt(len(g["ends"]) * sum(per) / 6.0))
                berry(b, berry_mats[0][0], C + ax * r, r, rnd, sides=sides, axis=-ax)
    b.lod, b.lod_scale = saved
    return count


def lace_umbel(b, floret_mat, ray_mat, top, axis, radius, rnd, rays=20, height=0.55, concave=0.12, floret_r=0.0026,
               florets=(3, 7), rim_size=0.3, ray_w=0.003, eye_mat=None, far=True, far_size=0.9, reach=0.95,
               ring_petals=0):
    """A Queen Anne's lace umbel without a plate: `rays` flat rays from `top` spread up and out (sunflower order) to
    umbellets over a disc `radius` across, `height` of the radius up `axis`, the rim `concave` higher than the middle.
    Each umbellet is a rosette of tiny florets round its ray's end, one on the end and the rest touching it, more and
    bigger toward the rim (`florets` from middle to rim; rim florets `rim_size` bigger). `eye_mat` adds the dark
    floret on a short ray in the middle. The far LOD keeps the rays and gets one bigger floret per umbellet in place
    of its rosette (`far_size` of the umbellet's span). `reach` is how far out the rosette's florets sit (see
    poly_floret). With `ring_petals` the middle floret is a five-petaled star_floret with an eye and the others
    star_florets of that many petals (as cheap as a polygon at 3, and lacier); otherwise all are flat polygons.
    Returns the floret count."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    top = Vector(top)
    saved = b.lod, b.lod_scale
    turn = rnd.uniform(0.0, math.tau)
    count = 0
    for i in range(rays):
        f = math.sqrt((i + 0.55) / rays)
        a = i * 2.39996 + turn + rnd.uniform(-0.12, 0.12)
        out = u * math.cos(a) + v * math.sin(a)
        r = radius * f * rnd.uniform(0.93, 1.03)
        h = radius * (height + concave * f * f) * rnd.uniform(0.96, 1.04)
        E = top + out * r + ax * h
        if f > 0.55:
            # Outer rays leave the stem more steeply and bow out, the way the umbel's cup forms
            bow = top.lerp(E, 0.5) + out * (r * 0.06) - ax * (h * 0.1)
            path = [top, bow, E]
        else:
            path = [top, E]
        b.lod, b.lod_scale = saved[0], 1.0
        ribbon(b, ray_mat, path, [ray_w] * (len(path) - 1) + [ray_w * 0.85], face=ax, t0=0.2, t1=1.0)
        n = int(round(florets[0] + (florets[1] - florets[0]) * f * f))
        fr = floret_r * (1.0 + rim_size * f * f)
        b.lod = 1
        uax = (ax + out * 0.25 * f).normalized()
        if ring_petals:
            star_floret(b, floret_mat, E, uax, fr, rnd, gap=0.16, cup=0.15)
        else:
            poly_floret(b, floret_mat, E, uax, fr * 0.9, rnd, t=rnd.uniform(0.75, 1.0))
        a0 = rnd.uniform(0.0, math.tau)
        for k in range(n - 1):
            ak = a0 + (k + rnd.uniform(-0.12, 0.12)) / max(1, n - 1) * math.tau
            o = u * math.cos(ak) + v * math.sin(ak)
            # Rim florets of the outer umbellets are the big ones (the lace edge)
            outer = f > 0.7 and o.dot(out) > 0.3
            if ring_petals:
                star_floret(b, floret_mat, E + o * fr, (uax + o * 0.45).normalized(), fr * (1.25 if outer else 1.0),
                            rnd, petals=ring_petals, gap=0.22, cup=0.1, anchor=E, reach=reach)
            else:
                poly_floret(b, floret_mat, E + o * fr, (uax + o * 0.45).normalized(), fr * (1.25 if outer else 1.0),
                            rnd, anchor=E, reach=reach, t=rnd.uniform(0.8, 1.0))
        count += n
        if far:
            b.lod = FAR
            poly_floret(b, floret_mat, E + ax * 0.0005, uax, fr * 2.0 * far_size, rnd, sides=6, wobble=0.1)
    if eye_mat is not None:
        b.lod = 1
        E = top + ax * (radius * height * 1.03)
        ribbon(b, ray_mat, [top, E], [ray_w, ray_w * 0.8], face=None, t0=0.2, t1=1.0)
        star_floret(b, eye_mat, E, ax, floret_r * 1.25, rnd, gap=0.12, cup=0.25)
    b.lod, b.lod_scale = saved
    return count


def bird_nest(b, ray_mat, seed_mat, top, axis, radius, rnd, rays=18, height=1.0, ray_w=0.003, seed_len=0.007,
              rim=0.68):
    """A Queen Anne's lace umbel gone to seed: its rays curled up and in to a hollow cup `radius` across and `height`
    of the radius tall (the "bird's nest"). The outer rays bow out from `top` and curl back in to a rim `rim` of the
    radius out, a bristly seed spike on each end leaning in over the hollow; the inner third stay short inside the
    cup with their spikes pointing up. Every part is kept in the far LOD (it is small and cheap)."""
    ax = Vector(axis).normalized()
    _, u, v = basis(ax)
    top = Vector(top)
    turn = rnd.uniform(0.0, math.tau)
    H = radius * height
    for i in range(rays):
        a = turn + (i + rnd.uniform(-0.3, 0.3)) / rays * math.tau
        out = u * math.cos(a) + v * math.sin(a)
        k = rnd.uniform(0.88, 1.08)
        if i % 3 == 2:
            path = [top, top + out * (radius * 0.35 * k) + ax * (H * 0.3),
                    top + out * (radius * 0.3 * k) + ax * (H * rnd.uniform(0.55, 0.7))]
            lean = ax * 1.5
        else:
            path = [top,
                    top + out * (radius * 0.72 * k) + ax * (H * 0.2),
                    top + out * (radius * 0.98 * k) + ax * (H * 0.6),
                    top + out * (radius * rim * k) + ax * (H * rnd.uniform(0.94, 1.06))]
            lean = ax * 0.4
        # Width round the cup (its face looks out), so the basket shows from the side
        ribbon(b, ray_mat, path, [ray_w] * (len(path) - 1) + [ray_w * 0.85], face=ax.cross(out), t0=0.2, t1=1.0)
        E = path[-1]
        inward = (path[-1] - path[-2]).normalized()
        d = (inward + lean + (u * rnd.uniform(-1, 1) + v * rnd.uniform(-1, 1)) * 0.3).normalized()
        L = seed_len * rnd.uniform(0.8, 1.2)
        tube(b, seed_mat, [E - d * (L * 0.15), E + d * L], [L * 0.32, 0.0], sides=3, cap=False, t0=0.3, t1=1.0)


def floating(obj, ground=G + 0.03, tol=0.0015, inside=0.02):
    """Checks a finished mesh for floating parts: splits it into its loose pieces, links two pieces when a vertex of
    one comes within `tol` of the other's surface (or sits inside a tube of it, up to `inside` from its wall), and
    returns the pieces that no chain of links joins to the ground, as [(center, size)]. Run it on the near and the
    far mesh after export."""
    from mathutils.bvhtree import BVHTree
    me = obj.data
    mw = obj.matrix_world
    co = [mw @ v.co for v in me.vertices]
    parent = list(range(len(co)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in me.polygons:
        vs = list(p.vertices)
        r0 = find(vs[0])
        for w in vs[1:]:
            r1 = find(w)
            if r1 != r0:
                parent[r1] = r0
    ids = {}
    isl_of = [0] * len(co)
    for i in range(len(co)):
        isl_of[i] = ids.setdefault(find(i), len(ids))
    n = len(ids)
    verts = [[] for _ in range(n)]
    for i, k in enumerate(isl_of):
        verts[k].append(i)
    poly_isl = [isl_of[p.vertices[0]] for p in me.polygons]
    tree = BVHTree.FromPolygons(co, [list(p.vertices) for p in me.polygons])
    links = [set() for _ in range(n)]
    for i, c in enumerate(co):
        a = isl_of[i]
        for loc, nrm, fi, dist in tree.find_nearest_range(c, inside):
            bb = poly_isl[fi]
            if bb == a or bb in links[a]:
                continue
            ok = dist < tol
            if not ok and (c - loc).dot(nrm) < 0.0:
                # Behind that face: inside a tube when a ray the other way meets the same piece too
                hit = tree.ray_cast(c + nrm * 1e-5, -nrm, 2.5 * inside)
                ok = hit[0] is not None and poly_isl[hit[2]] == bb
            if ok:
                links[a].add(bb)
                links[bb].add(a)
    seen = [False] * n

    def spread(stack):
        for k in stack:
            seen[k] = True
        while stack:
            k = stack.pop()
            for j in links[k]:
                if not seen[j]:
                    seen[j] = True
                    stack.append(j)

    spread([k for k in range(n) if min(co[vi].z for vi in verts[k]) < ground])
    # A piece no vertex links may still pass right through another (a leaflet's base edge across its rachis)
    loose = [k for k in range(n) if not seen[k]]
    if loose:
        polys_of = [[] for _ in range(n)]
        for fi, k in enumerate(poly_isl):
            polys_of[k].append(fi)
        for k in loose:
            local = {vi: j for j, vi in enumerate(verts[k])}
            sub = BVHTree.FromPolygons([co[vi] for vi in verts[k]],
                                       [[local[vi] for vi in me.polygons[fi].vertices] for fi in polys_of[k]])
            for _, fi in sub.overlap(tree):
                bb = poly_isl[fi]
                if bb != k:
                    links[k].add(bb)
                    links[bb].add(k)
        spread([k for k in range(n) if seen[k]])
    out = []
    for k in range(n):
        if not seen[k]:
            pts = [co[vi] for vi in verts[k]]
            lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            out.append(((lo + hi) * 0.5, (hi - lo).length))
    return out


def export_stacked(name, pieces, out_dir, size=1024, stacked=(), strip=0.1, ao=0.95, coarse_ratio=0.4):
    """kit_lod.export (far LOD from the parts' lod tags, FAR stand-ins and all) for plants with hundreds of tiny
    repeated parts. Unwrapped with the rest, a floret, berry or pedicel gets a few texels of the atlas and bakes to
    mush that bleeds into its neighbors. So the faces of each material named in `stacked` all share one small square
    in a strip down the atlas's right side instead, laid out along their "t" (0 at the bottom of the square, 1 at the
    top), so a floret's eye or a stalk's darker base still bakes; the occlusion there is set to `ao` (a shared square
    can't hold each part's own). Everything else is unwrapped as usual into the rest of the atlas. Returns the near
    mesh."""
    import kit_lod as kl
    folder = os.path.join(out_dir, name)
    os.makedirs(folder, exist_ok=True)
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("Bake")
    for o in pieces:
        kl._ensure(o)
    atlas = tk.triangulate(tk.join(pieces, name))
    me = atlas.data
    names = [s.material.name for s in atlas.material_slots]
    order = [m for m in stacked if m in names]
    if len(order) > int(1.0 / strip):
        raise ValueError("too many stacked materials for the strip")
    cell_of = {names.index(m): k for k, m in enumerate(order)}
    # Unwrap only the rest
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    for v in me.vertices:
        v.select = False
    for e in me.edges:
        e.select = False
    for p in me.polygons:
        p.select = p.material_index not in cell_of
        if p.select:
            for vi in p.vertices:
                me.vertices[vi].select = True
    for e in me.edges:
        e.select = me.vertices[e.vertices[0]].select and me.vertices[e.vertices[1]].select
    for o in bpy.context.scene.objects:
        o.select_set(o == atlas)
    bpy.context.view_layer.objects.active = atlas
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = me.uv_layers.active.data
    tv = me.attributes["t"].data
    k = 1.0 - strip
    pad = strip * 0.1
    cs = strip - 2.0 * pad
    for p in me.polygons:
        cell = cell_of.get(p.material_index)
        if cell is None:
            for li in p.loop_indices:
                u, v = uv[li].uv
                uv[li].uv = (u * k, v * k)
            continue
        x0, y0 = k + pad, cell * strip + pad
        for role, li in enumerate(p.loop_indices):
            t = min(1.0, max(0.0, tv[me.loops[li].vertex_index].value))
            uu = (0.08, 0.5, 0.92)[role % 3]
            vv = min(0.97, 0.03 + 0.86 * t + (0.08 if role % 3 == 1 else 0.0))
            uv[li].uv = (x0 + uu * cs, y0 + vv * cs)
    kl._shift_far(atlas, kl._AWAY)
    paths = tk.bake_atlas(atlas, folder, name, size=size)
    kl._shift_far(atlas, -kl._AWAY)
    if order:
        import numpy as np
        img = bpy.data.images.load(paths["rmom"], check_existing=True)
        img.reload()
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px.reshape(h, w, 4)[:, int(k * w):, 2] = ao
        img.pixels.foreach_set(px)
        img.filepath_raw = paths["rmom"]
        img.file_format = "PNG"
        img.save()
    baked = tk.baked_material(name, paths)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    lod = atlas.copy()
    lod.data = atlas.data.copy()
    lod.name = name + "_LOD1"
    tk.link(lod)
    lod = kl._far(lod, coarse_ratio)
    kl._keep(atlas, lambda v: v != kl.FAR)
    kl._strip(atlas)
    kl._strip(lod)
    tk.export_fbx([atlas, lod], os.path.join(folder, name + ".fbx"))
    near, far = kl.triangles(atlas), kl.triangles(lod)
    print("[%s] %d triangles, LOD1 %d (%d %%)" % (name, near, far, round(100.0 * far / max(1, near))))
    lod.hide_render = True
    return atlas


def report_floating(script, name):
    """Runs `floating` on <name> and <name>_LOD1 and prints what floats."""
    for nm in (name, name + "_LOD1"):
        obj = bpy.data.objects.get(nm)
        if obj is None:
            continue
        bad = floating(obj)
        print("[%s] %s: %d floating pieces" % (script, nm, len(bad)))
        for c, s in bad[:12]:
            print("    at (%.3f, %.3f, %.3f) size %.4f" % (c.x, c.y, c.z, s))


def closeups(script, name, out_dir, shots, lod=False, samples=48):
    """Close renders for checking a plant up close (call after nk.previews, which sets up the stage): `shots` is a
    list of (tag, eye, target, lens), each written to <script>_<tag>.png; with `lod` the far mesh is shown instead."""
    model = bpy.data.objects.get(name)
    far = bpy.data.objects.get(name + "_LOD1")
    if model is None:
        return
    if lod and far is not None:
        model.hide_render, far.hide_render = True, False
    for tag, eye, target, lens in shots:
        tk.render(tk.camera(script + tag, eye, target, lens=lens), os.path.join(out_dir, "%s_%s.png" % (script, tag)),
                  samples=samples)
    model.hide_render = False
    if far is not None:
        far.hide_render = True
