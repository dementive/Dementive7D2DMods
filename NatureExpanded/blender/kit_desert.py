"""Desert plant helpers for Nature Expanded, on top of naturekit.py and zkit.py (read those first).

The desert plants are made of many small parts (thousands of spines, teeth, petals), so rather than one Blender object
per part (nk.blade, nk.disc) these helpers add faces to a `Builder`, one per material, which becomes a single object
at the end: fast to build and to join. Every vertex gets naturekit's "t" attribute (0 at a part's base, 1 at its tip),
so nk.plant and nk.petal materials shade along the parts as usual.

Parts: sheet (a leaf or petal with a free width profile and an optional notched tip), sliver (a one-triangle spine,
or a three-triangle hooked one), tube (a tapered tube along a polyline), blob (a closed egg: fruit, bud), dome (a
flower's center), cone (a tubular flower), pad (a prickly pear pad, its areoles laid out on a lattice the `skin`
material draws as felt dots), barrel (a ribbed barrel cactus body with a "ridge" attribute on the rib crests),
agave_leaf (a thick channeled leaf with marginal teeth and a terminal spine), cup_flower and lobed_leaf.
`skin` is a cactus or agave surface; `previews` frames tall plants and adds a patch on desert sand.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import naturekit as nk
import zkit as tk

GROUND = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
RND = random.Random(11)


# ---------------------------------------------------------------- building

class Builder:
    """Vertices and faces for one material, turned into one object by `obj`. `v` takes the vertex's "t" and any
    extra per-vertex attributes (floats or 3-vectors, by name; vertices that don't give one get zero)."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.t = []
        self.attrs = {}

    def v(self, co, t=0.0, **attrs):
        i = len(self.verts)
        self.verts.append(tuple(co))
        self.t.append(t)
        for k, val in attrs.items():
            col = self.attrs.setdefault(k, {})
            col[i] = val
        return i

    def f(self, *idx):
        self.faces.append(tuple(idx))

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    def obj(self, name, material, smooth=True, closed=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.update()
        if closed:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(me)
            bm.free()
        obj = tk.link(bpy.data.objects.new(name, me))
        obj.data.materials.append(material)
        nk._set_t(obj, self.t)
        n = len(self.verts)
        for k, col in self.attrs.items():
            sample = next(iter(col.values()))
            if isinstance(sample, (tuple, list, Vector)):
                a = me.attributes.new(k, "FLOAT_VECTOR", "POINT")
                for i in range(n):
                    a.data[i].vector = tuple(col.get(i, (0.0, 0.0, 0.0)))
            else:
                a = me.attributes.new(k, "FLOAT", "POINT")
                for i in range(n):
                    a.data[i].value = col.get(i, 0.0)
        for p in me.polygons:
            p.use_smooth = smooth
        return obj


def frame(direction, side=None, roll=0.0):
    """(d, side, up): the direction and two vectors across it; `side` (projected) fixes the across vector."""
    d = Vector(direction).normalized()
    if side is not None:
        sd = Vector(side) - d * Vector(side).dot(d)
        if sd.length < 1e-5:
            side = None
        else:
            sd.normalize()
    if side is None:
        sd = d.cross(UP)
        if sd.length < 1e-4:
            sd = d.cross(Vector((1.0, 0.0, 0.0)))
        sd.normalize()
    up = sd.cross(d).normalized()
    if roll:
        r = Matrix.Rotation(math.radians(roll), 3, d)
        sd, up = r @ sd, r @ up
    return d, sd, up


def rotate(vec, axis, degrees):
    return Matrix.Rotation(math.radians(degrees), 3, Vector(axis)) @ Vector(vec)


def sheet(b, base, direction, length, width, widths, bend=0.0, toward=(0.0, 0.0, -1.0), twist=0.0, roll=0.0,
          side=None, notch=0.0, t0=0.0, t1=1.0, wave=0.0, rnd=None):
    """A leaf or petal: a single sheet from `base` along `direction`, `widths` the relative width at each row (row 0
    at the base, one row more than segments; 0 makes a point). It arches over by `bend` toward `toward` (0 straight, 1
    turned a right angle; negative curls the other way), twists `twist` degrees, and a `notch` pulls the tip's middle
    back (a heart-shaped petal). `wave` jitters the edges up and down (crinkled leaves). Returns the center line."""
    d, sd, up = frame(direction, side, roll)
    tw = Vector(toward) - d * Vector(toward).dot(d)
    tw = tw.normalized() if tw.length > 1e-5 else -up
    seg = len(widths) - 1
    rows, line = [], []
    c = Vector(base)
    along = d
    for i in range(seg + 1):
        s = i / seg
        ang = bend * s * s * math.pi * 0.5
        along = d * math.cos(ang) + tw * math.sin(ang)
        if i > 0:
            c = c + along * (length / seg)
        line.append(c.copy())
        sv = Matrix.Rotation(math.radians(twist * s), 3, d) @ sd
        w = widths[i] * width * 0.5
        t = t0 + (t1 - t0) * s
        if w < 1e-6:
            rows.append((b.v(c, t),))
        else:
            nrm = sv.cross(along).normalized()
            ja = nrm * (wave * w * (rnd.uniform(-1, 1) if rnd else math.sin(i * 2.1))) if wave else Vector()
            jb = nrm * (wave * w * (rnd.uniform(-1, 1) if rnd else math.cos(i * 1.7))) if wave else Vector()
            rows.append((b.v(c - sv * w + ja, t), b.v(c + sv * w + jb, t)))
    for i in range(seg):
        r0, r1 = rows[i], rows[i + 1]
        last = i == seg - 1
        if len(r0) == 2 and len(r1) == 2:
            if last and notch > 0.0:
                m = b.v(line[-1] - along * (notch * length), t1)
                b.f(r0[0], r0[1], m)
                b.f(r0[1], r1[1], m)
                b.f(m, r1[0], r0[0])
            else:
                b.f(r0[0], r0[1], r1[1], r1[0])
        elif len(r0) == 1 and len(r1) == 2:
            b.f(r0[0], r1[1], r1[0])
        elif len(r0) == 2 and len(r1) == 1:
            b.f(r0[0], r0[1], r1[0])
    return line


def sliver(b, base, direction, length, width, roll=None, hook=0.0, hook_dir=None, t0=0.0, t1=1.0):
    """A spine: one thin triangle (or, with `hook` degrees, three, the tip bent toward `hook_dir`). `roll` turns it
    about its own axis (degrees; random if None, so a cluster never vanishes edge-on all at once)."""
    d, sd, up = frame(direction, roll=RND.uniform(0, 180) if roll is None else roll)
    p = Vector(base)
    a = b.v(p - sd * width * 0.5, t0)
    c = b.v(p + sd * width * 0.5, t0)
    if hook <= 0.0:
        b.f(a, c, b.v(p + d * length, t1))
        return
    m = p + d * length * 0.78
    hd = Vector(hook_dir) if hook_dir is not None else -UP
    hd = hd - d * hd.dot(d)
    hd = hd.normalized() if hd.length > 1e-5 else up
    tm = t0 + (t1 - t0) * 0.78
    ma = b.v(m - sd * width * 0.3, tm)
    mc = b.v(m + sd * width * 0.3, tm)
    h = math.radians(hook)
    tip = b.v(m + (d * math.cos(h) + hd * math.sin(h)) * length * 0.25, t1)
    b.f(a, c, mc, ma)
    b.f(ma, mc, tip)


def tube(b, points, radii, sides=6, cap=True, t0=0.0, t1=1.0, phase=0.0, wobble=0.0, rnd=None, attrs=None):
    """A tapered tube along a polyline: `radii` one per point (or one number); a radius of 0 at the end closes it
    to a point. "t" runs along its length. Returns the rings (lists of vertex indices)."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    rs = radii if isinstance(radii, (list, tuple)) else [radii] * n
    seglen = [0.0] + [(pts[i] - pts[i - 1]).length for i in range(1, n)]
    total = sum(seglen) or 1.0
    acc = 0.0
    tans = []
    for i in range(n):
        tans.append((pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized())
    _, sd, _ = frame(tans[0])
    rings = []
    ex = attrs or {}
    for i in range(n):
        acc += seglen[i]
        t = t0 + (t1 - t0) * acc / total
        sd = sd - tans[i] * sd.dot(tans[i])
        sd.normalize()
        up = tans[i].cross(sd)
        r = rs[i]
        if r <= 1e-6:
            rings.append([b.v(pts[i], t, **ex)])
            continue
        ring = []
        for j in range(sides):
            a = math.tau * j / sides + phase
            k = 1.0 + (rnd.uniform(-wobble, wobble) if (wobble and rnd) else 0.0)
            ring.append(b.v(pts[i] + (sd * math.cos(a) + up * math.sin(a)) * r * k, t, **ex))
        rings.append(ring)
    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        if len(r0) > 1 and len(r1) > 1:
            for j in range(sides):
                b.f(r0[j], r0[(j + 1) % sides], r1[(j + 1) % sides], r1[j])
        elif len(r1) == 1:
            for j in range(sides):
                b.f(r0[j], r0[(j + 1) % sides], r1[0])
        elif len(r0) == 1:
            for j in range(sides):
                b.f(r0[0], r1[(j + 1) % sides], r1[j])
    if cap and len(rings[-1]) > 1:
        b.f(*rings[-1])
    return rings


def blob(b, center, axis, radius, length, k=6, rings=3, t=1.0, wobble=0.0, rnd=None, top_dent=0.0, attrs=None):
    """A closed egg (a fruit, a bud, a seed pod) along `axis`, `length` long and `radius` round. `top_dent` sinks
    the top pole (a prickly pear fruit's cupped tip)."""
    ax = Vector(axis).normalized()
    _, sd, up = frame(ax)
    c = Vector(center)
    ex = attrs or {}
    bot = b.v(c - ax * length * 0.5, t * 0.6, **ex)
    top = b.v(c + ax * length * (0.5 - top_dent), t, **ex)
    rs = []
    for i in range(1, rings + 1):
        phi = math.pi * i / (rings + 1)
        z = -math.cos(phi) * length * 0.5
        r = math.sin(phi) * radius
        off = i * 0.5 * math.tau / k
        ring = []
        for j in range(k):
            a = math.tau * j / k + off
            w = 1.0 + (rnd.uniform(-wobble, wobble) if (wobble and rnd) else 0.0)
            ring.append(b.v(c + ax * z + (sd * math.cos(a) + up * math.sin(a)) * r * w, t * (0.6 + 0.4 * i / rings),
                            **ex))
        rs.append(ring)
    for j in range(k):
        b.f(bot, rs[0][(j + 1) % k], rs[0][j])
    for i in range(rings - 1):
        r0, r1 = rs[i], rs[i + 1]
        for j in range(k):
            b.f(r0[j], r0[(j + 1) % k], r1[(j + 1) % k], r1[j])
    for j in range(k):
        b.f(rs[-1][j], rs[-1][(j + 1) % k], top)


def dome(b, center, axis, radius, height, k=7, t=1.0, ring2=False):
    """A flower's center: a low cone of `k` triangles facing `axis` (with `ring2`, a rounder two-ring dome)."""
    ax = Vector(axis).normalized()
    _, sd, up = frame(ax)
    c = Vector(center)
    tip = b.v(c + ax * height, t)
    outer = [b.v(c + (sd * math.cos(a) + up * math.sin(a)) * radius, t)
             for a in (math.tau * j / k for j in range(k))]
    if ring2:
        inner = [b.v(c + ax * height * 0.75 + (sd * math.cos(a) + up * math.sin(a)) * radius * 0.6, t)
                 for a in (math.tau * (j + 0.5) / k for j in range(k))]
        for j in range(k):
            b.f(outer[(j + 1) % k], outer[j], inner[j])
            b.f(outer[(j + 1) % k], inner[j], inner[(j + 1) % k])
            b.f(inner[(j + 1) % k], inner[j], tip)
    else:
        for j in range(k):
            b.f(outer[(j + 1) % k], outer[j], tip)


def cone(b, apex, axis, length, radius, sides=3, flare=0.0, t0=0.0, t1=1.0, roll=0.0):
    """A tubular flower or a thorn: an open cone from `apex` along `axis`; `flare` adds a flared lip ring."""
    d, sd, up = frame(axis, roll=roll)
    a = b.v(apex, t0)
    p = Vector(apex) + d * length
    ring = [b.v(p + (sd * math.cos(x) + up * math.sin(x)) * radius, t0 + (t1 - t0) * 0.85)
            for x in (math.tau * j / sides for j in range(sides))]
    for j in range(sides):
        b.f(a, ring[j], ring[(j + 1) % sides])
    if flare:
        q = p + d * length * 0.18
        lip = [b.v(q + (sd * math.cos(x) + up * math.sin(x)) * radius * (1.0 + flare), t1)
               for x in (math.tau * (j + 0.5) / sides for j in range(sides))]
        for j in range(sides):
            b.f(ring[(j + 1) % sides], ring[j], lip[j])


def cup_flower(b, center, axis, petals, length, width, widths=(0.3, 0.85, 1.0, 0.75), cup=0.5, droop=0.0,
               layers=1, seed=0, jitter=0.15, notch=0.0, twist=0.0):
    """A flower head of `petals` sheets round `center` facing `axis`: `cup` 0 flat to 1 upright, `droop` arches the
    tips back (negative curls them in), `layers` adds smaller, more upright inner rings."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, sd, up = frame(ax)
    for layer in range(layers):
        n = max(3, petals - layer)
        sc = 1.0 - 0.18 * layer
        lift = min(0.95, cup + 0.18 * layer)
        for i in range(n):
            a = (i + rnd.uniform(-jitter, jitter) + layer * 0.5) / n * math.tau
            out = sd * math.cos(a) + up * math.sin(a)
            li = lift + rnd.uniform(-0.08, 0.08)
            dr = (out * math.cos(li * math.pi * 0.5) + ax * math.sin(li * math.pi * 0.5)).normalized()
            sheet(b, Vector(center) + ax * (0.0015 * layer), dr, length * sc * rnd.uniform(0.88, 1.1), width * sc,
                  widths, bend=droop, toward=-ax, side=out.cross(ax), notch=notch,
                  twist=twist * rnd.uniform(-1, 1))


def lobed_leaf(b, base, direction, normal, length, width, lobes=3, crinkle=0.1, rnd=None, t0=0.0, t1=1.0):
    """A palmate leaf (globemallow, mallow): a fan of triangles round its middle, `lobes` 3 or 5 points (or 1: an
    ovate leaf with a scalloped edge), the edge lifted and dropped at random by `crinkle` (a fraction of its width)."""
    d = Vector(direction).normalized()
    n = Vector(normal) - d * Vector(normal).dot(d)
    n = n.normalized() if n.length > 1e-5 else frame(d)[2]
    sd = d.cross(n).normalized()
    rnd = rnd or random.Random(0)
    if lobes == 1:
        outline = [(-0.14, 0.03), (-0.44, 0.22), (-0.47, 0.42), (-0.33, 0.6), (-0.2, 0.8), (0.0, 1.0), (0.2, 0.8),
                   (0.33, 0.6), (0.47, 0.42), (0.44, 0.22), (0.14, 0.03)]
    elif lobes >= 5:
        outline = [(-0.12, 0.05), (-0.5, 0.25), (-0.32, 0.36), (-0.45, 0.68), (-0.16, 0.6), (0.0, 1.0),
                   (0.16, 0.6), (0.45, 0.68), (0.32, 0.36), (0.5, 0.25), (0.12, 0.05)]
    else:
        outline = [(-0.14, 0.04), (-0.5, 0.42), (-0.2, 0.52), (0.0, 1.0), (0.2, 0.52), (0.5, 0.42), (0.14, 0.04)]
    p0 = Vector(base)
    mid = b.v(p0 + d * length * 0.38 + n * length * crinkle * 0.3, t0 + (t1 - t0) * 0.4)
    root = b.v(p0, t0)
    ring = [root]
    for x, y in outline:
        p = p0 + d * (y * length) + sd * (x * width) + n * (rnd.uniform(-1, 1) * crinkle * width)
        ring.append(b.v(p, t0 + (t1 - t0) * y))
    for j in range(len(ring)):
        b.f(mid, ring[(j + 1) % len(ring)], ring[j])


# ---------------------------------------------------------------- cacti and agave

def _obovate(s, widest):
    """0 at both ends, 1 at `widest` (0 to 1): a pad's or leaf's outline along its length."""
    u = s ** (math.log(0.5) / math.log(widest))
    return math.sin(math.pi * u) ** 0.62


def pad(b, base, direction, normal, length, width, thick, k=10, rings=6, widest=0.6, warp=0.0, lattice=0.03,
        offset=(0.0, 0.0), seed=0):
    """A prickly pear pad: a flat, obovate, closed lens from `base` (its joint) along `direction`, faces toward
    `normal`. Each vertex gets a "lattice" attribute: the pad's own surface coordinates on a diagonal grid `lattice`
    apart, which `skin(dots=...)` draws as areoles. Returns (frame, areoles): frame = (base, L, W, N, length,
    half_width(s), half_thick(s)) and areoles a list of (point, outward normal, s) on both faces and the rim."""
    rnd = random.Random(seed)
    L = Vector(direction).normalized()
    N = Vector(normal) - L * Vector(normal).dot(L)
    N = N.normalized() if N.length > 1e-5 else frame(L)[2]
    W = L.cross(N).normalized()
    P = Vector(base)
    c45 = math.sqrt(0.5)
    off = Vector(offset)

    def half_w(s):
        return width * 0.5 * _obovate(min(max(s, 0.0), 1.0), widest)

    def half_t(s):
        return thick * 0.5 * (_obovate(min(max(s, 0.0), 1.0), widest) ** 0.5) * (1.15 - 0.35 * s)

    def center(s):
        return P + L * (length * s) + N * (warp * length * math.sin(math.pi * s))

    def lat(u, v):
        return ((u - v) * c45 / lattice + off.x, (u + v) * c45 / lattice + off.y, 0.0)

    bot = b.v(center(0.0), 0.0, lattice=lat(0.0, 0.0))
    top = b.v(center(1.0), 1.0, lattice=lat(0.0, length))
    rs = []
    for i in range(1, rings):
        s = i / rings
        s = s ** 0.9
        a, th = half_w(s), half_t(s)
        ring = []
        for j in range(k):
            phi = math.tau * j / k
            u = a * math.cos(phi)
            jit = 1.0 + rnd.uniform(-0.03, 0.03)
            p = center(s) + W * (u * jit) + N * (th * math.sin(phi))
            ring.append(b.v(p, s, lattice=lat(u, length * s)))
        rs.append(ring)
    for j in range(k):
        b.f(bot, rs[0][(j + 1) % k], rs[0][j])
    for i in range(len(rs) - 1):
        r0, r1 = rs[i], rs[i + 1]
        for j in range(k):
            b.f(r0[j], r0[(j + 1) % k], r1[(j + 1) % k], r1[j])
    for j in range(k):
        b.f(rs[-1][j], rs[-1][(j + 1) % k], top)

    # The areoles: lattice points that fall inside the outline, on both faces
    areoles = []
    span = int(max(length, width) / lattice) + 3
    for i in range(-span, span + 1):
        for j in range(-span, span + 1):
            qx, qy = i + 0.5 - off.x, j + 0.5 - off.y
            u, v = (qx + qy) * c45 * lattice, (qy - qx) * c45 * lattice
            s = v / length
            if s < 0.08 or s > 0.96:
                continue
            a = half_w(s)
            if abs(u) > a * 0.9:
                continue
            rim = abs(u) > a * 0.72
            th = half_t(s) * math.sqrt(max(0.0, 1.0 - (u / a) ** 2))
            for face in (1.0, -1.0):
                p = center(s) + W * u + N * (th * face)
                nrm = (N * face + W * (u / a) * 0.8).normalized()
                areoles.append((p, nrm, s, rim))
    return (P, L, W, N, length, half_w, half_t, center), areoles


def barrel(b, height, radius, ribs=16, rows=9, depth=0.12, twist=8.0, matrix=None, apex_dip=0.03, seed=0,
           dome_power=3.0):
    """A ribbed barrel cactus body standing on the origin (then moved by `matrix`): `ribs` ridges, a domed top with
    a sunken woolly apex (`dome_power` lower for a rounder top). Vertices carry a "ridge" attribute (1 on the crests, 0 in the grooves) for `skin(ridges=)`
    to pick out. Returns a function (rib, s) -> (point, outward normal) for laying spines along a crest."""
    rnd = random.Random(seed)
    M = matrix if matrix is not None else Matrix.Identity(4)
    M3 = M.to_3x3()
    sink = 0.03

    def prof(s):
        return radius * (1.0 - s ** dome_power) ** 0.45 * (0.86 + 0.14 * math.sin(math.pi * min(1.0, s * 1.2)))

    def z_of(s):
        return -sink + (height + sink) * s

    def ang(j, s):
        return math.tau * j / (2 * ribs) + math.radians(twist) * s

    rs = []
    for i in range(rows):
        s = (i / (rows - 1)) ** 0.85 * 0.965
        ring = []
        for j in range(2 * ribs):
            crest = j % 2 == 0
            r = prof(s) * (1.0 if crest else 1.0 - depth) * (1.0 + rnd.uniform(-0.015, 0.015))
            a = ang(j, s)
            p = M @ Vector((r * math.cos(a), r * math.sin(a), z_of(s)))
            ring.append(b.v(p, s, ridge=1.0 if crest else 0.0))
        rs.append(ring)
    apex = b.v(M @ Vector((0.0, 0.0, height - apex_dip)), 1.0, ridge=0.5)
    n = 2 * ribs
    for i in range(rows - 1):
        r0, r1 = rs[i], rs[i + 1]
        for j in range(n):
            b.f(r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j])
    for j in range(n):
        b.f(rs[-1][j], rs[-1][(j + 1) % n], apex)

    def crest(rib, s):
        a = ang(2 * rib, s)
        r = prof(s)
        eps = 0.01
        dr = (prof(min(1.0, s + eps)) - prof(max(0.0, s - eps))) / (2 * eps) / (height + sink)
        p = Vector((r * math.cos(a), r * math.sin(a), z_of(s)))
        nrm = Vector((math.cos(a), math.sin(a), -dr)).normalized()
        return M @ p, (M3 @ nrm).normalized()
    return crest


def agave_leaf(b, teeth_b, base, direction, length, width, thick, incurve=0.0, channel=0.25, rows=6, teeth=8,
               tooth=0.008, spine=0.025, seed=0, spine_b=None, roll=0.0):
    """A thick agave leaf from `base` along `direction` (closed, four-sided: a cupped upper face and a keel), its
    tip arching up toward vertical by `incurve` (negative: down). Teeth along both margins go to `teeth_b`, the
    terminal spine to `spine_b` (or `teeth_b`). Returns the tip point."""
    rnd = random.Random(seed)
    d, sd, up = frame(direction, roll=roll)
    # "up" is the leaf's upper face; make sure it points skyward-ish
    if up.z < 0:
        sd, up = -sd, -up
    rows_v = []
    c = Vector(base)
    centers, sides, ups = [], [], []
    for i in range(rows + 1):
        s = i / rows
        ang = incurve * s * s * math.pi * 0.5
        along = (d * math.cos(ang) + up * math.sin(ang)).normalized()
        if i > 0:
            c = c + along * (length / rows)
        u = sd.cross(along).normalized()
        centers.append(c.copy())
        sides.append(sd.copy())
        ups.append(u)
        if s < 0.6:
            w = 0.62 + 0.38 * math.sin(math.pi * 0.5 * s / 0.6)
        else:
            w = math.cos(math.pi * 0.5 * (s - 0.6) / 0.4) ** 0.85
        w *= width * 0.5
        th = thick * (1.0 - 0.8 * s)
        if i == rows:
            rows_v.append([b.v(c, 1.0)])
            continue
        lv = b.v(c - sd * w + u * (channel * w * 0.5), s)
        tv = b.v(c - u * (th * 0.1), s)
        rv = b.v(c + sd * w + u * (channel * w * 0.5), s)
        bv = b.v(c - u * th, s)
        rows_v.append([lv, tv, rv, bv])
    for i in range(rows):
        r0, r1 = rows_v[i], rows_v[i + 1]
        if len(r1) == 4:
            for j in range(4):
                b.f(r0[j], r0[(j + 1) % 4], r1[(j + 1) % 4], r1[j])
        else:
            for j in range(4):
                b.f(r0[j], r0[(j + 1) % 4], r1[0])
    # Teeth along both margins, hooked a little toward the tip
    for k in range(teeth):
        s = 0.18 + 0.72 * (k + rnd.uniform(-0.2, 0.2)) / max(1, teeth - 1)
        i = min(rows - 1, int(s * rows))
        f = s * rows - i
        cc = centers[i].lerp(centers[i + 1], f)
        ss = sides[i]
        uu = ups[i].lerp(ups[i + 1], f)
        if s < 0.6:
            w = 0.62 + 0.38 * math.sin(math.pi * 0.5 * s / 0.6)
        else:
            w = math.cos(math.pi * 0.5 * (s - 0.6) / 0.4) ** 0.85
        w *= width * 0.5
        along = (centers[i + 1] - centers[i]).normalized()
        for sg in (-1.0, 1.0):
            edge = cc + ss * (sg * w) + uu * (channel * w * 0.5)
            sz = tooth * rnd.uniform(0.7, 1.2) * (1.0 - 0.3 * s)
            a0 = teeth_b.v(edge - along * sz * 0.5, 0.0)
            a1 = teeth_b.v(edge + along * sz * 0.5, 0.0)
            tip = teeth_b.v(edge + ss * (sg * sz * 1.1) + along * sz * 0.6, 1.0)
            teeth_b.f(a0, a1, tip)
    tipv = centers[-1]
    along = (centers[-1] - centers[-2]).normalized()
    cone(spine_b or teeth_b, tipv - along * spine * 0.3, along, spine, thick * 0.12 + 0.0015, sides=3)
    return tipv


# ---------------------------------------------------------------- materials

def skin(name, color, color2=None, rough=0.55, vary=0.25, scale=10.0, sat=0.85, value=0.85, dots=None,
         ridges=None, streaks=0.0, base_dark=0.7, bump=0.04):
    """A cactus, agave or bark surface, like nk.plant (color drifting between `color` and `color2`, darker toward
    each part's base) with extras: `dots` = (radius, felt color, center color) draws areoles on pad()'s lattice
    (radius as a fraction of the lattice spacing); `ridges` = color lightens the rib crests of barrel();
    `streaks` (0 to 1) adds fine lengthwise grooves (ocotillo canes, shaggy bark)."""
    mat, g = tk.new_material(name)
    c2 = color2 or tuple(c * 0.65 for c in color)
    col = g.mix(g.ramp(g.noise(scale, detail=3.0), 0.5 - vary, 0.5 + vary), color, c2)
    col = g.mix(g.ramp(nk._attr(g, "t"), 0.0, 0.5), tuple(c * base_dark for c in color), col)
    height = g.math("MULTIPLY", g.noise(70.0), 0.3)
    if streaks:
        m = g.node("ShaderNodeMapping")
        g.links.new(g.coords(), m.inputs["Vector"])
        m.inputs["Scale"].default_value = (90.0, 90.0, 4.0)
        st = g.ramp(g.noise(1.0, detail=5.0, vector=m.outputs[0]), 0.35, 0.75)
        col = g.mix(g.math("MULTIPLY", st, streaks), col, tuple(c * 0.55 for c in c2))
        height = g.math("ADD", height, g.math("MULTIPLY", st, -streaks))
    if ridges is not None:
        rid = g.node("ShaderNodeAttribute", attribute_name="ridge").outputs["Fac"]
        col = g.mix(g.ramp(rid, 0.55, 1.0), tuple(c * 0.6 for c in c2), col)
        col = g.mix(g.math("MULTIPLY", g.ramp(rid, 0.8, 1.0), 0.45), col, ridges)
        # The woolly apex
        col = g.mix(g.ramp(nk._attr(g, "t"), 0.97, 1.0), col, (0.36, 0.28, 0.14))
    if dots is not None:
        radius, felt, middle = dots
        lat = g.node("ShaderNodeAttribute", attribute_name="lattice").outputs["Vector"]
        fr = g.node("ShaderNodeVectorMath", operation="FRACTION")
        g.links.new(lat, fr.inputs[0])
        sub = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
        g.links.new(fr.outputs[0], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.0)
        ln = g.node("ShaderNodeVectorMath", operation="LENGTH")
        g.links.new(sub.outputs[0], ln.inputs[0])
        dist = ln.outputs["Value"]
        dot = g.ramp(dist, radius, radius * 0.65)
        core = g.ramp(dist, radius * 0.45, radius * 0.2)
        # A faint pale halo round each areole, the felt, and its darker middle
        col = g.mix(g.math("MULTIPLY", g.ramp(dist, radius * 2.0, radius), 0.18), col, (0.5, 0.52, 0.42))
        col = g.mix(dot, col, felt)
        col = g.mix(core, col, middle)
        height = g.math("ADD", height, g.math("MULTIPLY", dot, 0.6))
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, bump * 3.0, 0.002))


def sand(name="DesertSand"):
    """A sandy floor for the desert previews, with the stage's 1 m grid kept faintly for scale."""
    mat, g = tk.new_material(name)
    x, y, _ = g.separate(g.coords())
    gx = g.ramp(g.math("PINGPONG", x, 0.5), 0.0, 0.012)
    gy = g.ramp(g.math("PINGPONG", y, 0.5), 0.0, 0.012)
    line = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gx, gy))
    col = g.mix(g.ramp(g.noise(3.0, detail=6.0), 0.35, 0.7), (0.5, 0.36, 0.2), (0.42, 0.29, 0.16))
    col = g.mix(g.ramp(g.noise(40.0, detail=4.0), 0.55, 0.75), col, (0.3, 0.22, 0.14))
    col = g.mix(g.math("MULTIPLY", line, 0.25), col, (0.2, 0.15, 0.1))
    return tk.finish(mat, g, col, 0.0, 0.9)


# ---------------------------------------------------------------- previews

def _patch(script, model, out_dir, height, suffix):
    k = max(1.0, (height + 0.3) / 1.5)
    rnd = random.Random(1)
    copies = []
    for _ in range(8):
        c = model.copy()
        tk.link(c)
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.7, 1.9)
        c.location = (r * math.cos(a), r * math.sin(a) + 0.6, 0.0)
        c.rotation_euler = (0.0, 0.0, rnd.uniform(0, math.tau))
        s = rnd.uniform(0.8, 1.15)
        c.scale = (s, s, s)
        copies.append(c)
    cam = tk.camera(script + suffix, (0.4 * k, 0.6 - 4.2 * k, -0.5 + 1.9 * k), (0.0, 0.6, -0.5 + 0.3 * k * k), lens=35)
    tk.render(cam, "%s/%s_%s.png" % (out_dir, script, suffix), samples=48)
    for c in copies:
        bpy.data.objects.remove(c)


def previews(script, model, out_dir, height, focus=None, distance=None):
    """nk.previews framed to the plant's `height` (front, side, top and patch on the stage; for a plant taller than
    1.2 m the patch is re-shot from farther back so the tops are in), then <script>_sand.png: the same patch on desert
    sand, to judge the colors against the ground they grow on."""
    focus = GROUND + height * 0.5 if focus is None else focus
    distance = max(1.3, height * 1.9) if distance is None else distance
    nk.previews(script, model, out_dir, focus_height=focus, distance=distance)
    if height > 1.2:
        _patch(script, model, out_dir, height, "patch")
    floor = bpy.data.objects.get("Floor")
    if floor is not None:
        floor.data.materials[0] = sand()
    _patch(script, model, out_dir, height, "sand")
