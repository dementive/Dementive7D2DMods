"""Ground-cover kit for Nature Expanded's forest-floor patches (PineNeedleMat, BirchLeafLitter, MapleLeafLitter,
OakLeafLitter, MossPatch, TwigPile, PineconeCluster, AcornScatter, LichenStone), on top of naturekit, kit_forest,
kit_shrub and zkit.

A ground-cover block is a patch about 0.9 m across lying on the ground (z = nk.GROUND), mostly under 15 cm tall, that
reads as a real pile of real things, so:

- `Patch` is the irregular outline of the patch, with a density that thins out toward a ragged edge (and holes), so a
  patch fades into the vanilla ground instead of ending in a line.
- `base_layer` is the dark packed layer under the pile: a ragged low disc whose rim sinks into the terrain.
- `Heap` is a height field: every leaf, needle or twig is dropped on it and comes to rest on whatever is already
  there, so the pile builds up in layers and nothing floats or cuts through.
- `add_leaf` (any outline: birch, maple, oak), `needle_bundle`, `tube` (twigs), `lathe` (cones, acorns, mounds),
  `rock`, `cone_scales` put the geometry into a `Ground` builder (kit_shrub's Builder plus the per-vertex
  coordinates the materials draw with, and a far LOD made by dropping parts).
- Materials: `leaf_material` (veined leaves in a palette, pinnate or palmate), `duff` (the packed layer).

Vertex attributes besides naturekit's "t": lx, ly, lz are the part's own coordinates (stored +0.5 so they stay
positive): for a leaf, lx along it (0 at the base to about 1 at the tip, in leaf lengths), ly across it, lz how far
out toward its rim (0 in the middle, 1 on the outline); for a lathe or tube, lx along the axis in meters and ly, lz
the point round the axis (r cos a, r sin a), so noise stretched along lx has no seam. r and r2 are a random per part
(a leaf's color and dampness). Same units as the rest: meters, Z up.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils import noise as mn

import naturekit as nk
import kit_forest as kf
import kit_shrub as ks
import zkit as tk

G = nk.GROUND
TAU = math.tau
UP = Vector((0.0, 0.0, 1.0))
ATTRS = ("lx", "ly", "lz", "r", "r2")


# ---------------------------------------------------------------- builder

class _GMesh(ks._Mesh):
    def __init__(self, builder):
        super().__init__(builder)
        self.ex = {k: [] for k in ATTRS}

    def v(self, co, t=0.0, lx=0.0, ly=0.0, lz=0.0, r=0.0, r2=0.0):
        for k, val in (("lx", lx), ("ly", ly), ("lz", lz), ("r", r), ("r2", r2)):
            self.ex[k].append(val)
        return super().v(co, t)


class Ground(ks.Builder):
    """kit_shrub's Builder, with the extra per-vertex attributes (see the module docstring)."""

    def mesh(self, material):
        entry = self.meshes.get(material.name)
        if entry is None:
            entry = self.meshes[material.name] = (_GMesh(self), material)
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
            me.attributes.new("lod", "INT", "FACE").data.foreach_set("value", m.lods)
            me.attributes.new("lodscale", "FLOAT", "POINT").data.foreach_set("value", m.scales)
            me.attributes.new("pivot", "FLOAT_VECTOR", "POINT").data.foreach_set(
                "vector", [c for p in m.pivots for c in p])
            for k, vals in m.ex.items():
                me.attributes.new(k, "FLOAT", "POINT").data.foreach_set("value", vals)
            out.append(obj)
        self.meshes = {}
        return out


def _smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the patch and the heap

class Patch:
    """The irregular outline of a ground-cover patch: radius `radius` along x, squashed by `stretch`, its rim
    wandering by harmonics. `d(x, y)` is 0 in the middle and 1 on the rim; `density` thins things out toward the rim
    (and around `holes`), `sample` picks points by it."""

    def __init__(self, radius=0.45, seed=0, stretch=(1.0, 0.88), wander=1.0):
        rnd = random.Random(seed)
        self.R0 = radius
        self.stretch = stretch
        self.rot = rnd.uniform(0.0, TAU)
        self.harm = [(k, a * wander, rnd.uniform(0.0, TAU)) for k, a in ((2, 0.1), (3, 0.09), (4, 0.06), (6, 0.045),
                                                                           (9, 0.03), (13, 0.02))]
        self.seed = seed
        self.holes = []
        self.fade = (0.55, 1.18)

    def R(self, ang):
        a = ang - self.rot
        sx, sy = self.stretch
        e = 1.0 / math.sqrt((math.cos(a) / sx) ** 2 + (math.sin(a) / sy) ** 2)
        wob = 1.0 + sum(amp * math.sin(k * a + ph) for k, amp, ph in self.harm)
        return self.R0 * e * wob

    def d(self, x, y):
        return math.hypot(x, y) / max(1e-6, self.R(math.atan2(y, x)))

    def density(self, x, y):
        d = self.d(x, y)
        k = 1.0 - _smoothstep(self.fade[0], self.fade[1], d)
        n = mn.noise(Vector((x * 4.0 + self.seed * 7.0, y * 4.0, 1.7)))
        k *= 0.78 + 0.5 * n + 0.15 * mn.noise(Vector((x * 14.0, y * 14.0 + self.seed, 3.1)))
        for hx, hy, hr in self.holes:
            k *= _smoothstep(0.5 * hr, hr, math.hypot(x - hx, y - hy))
        return max(0.0, min(1.0, k))

    def sample(self, rnd, count, min_gap=0.0, reach=1.3):
        rmax = self.R0 * 1.25 * reach
        pts = []
        tries = 0
        while len(pts) < count and tries < count * 600:
            tries += 1
            a = rnd.uniform(0.0, TAU)
            r = rmax * math.sqrt(rnd.random())
            x, y = r * math.cos(a), r * math.sin(a)
            if rnd.random() > self.density(x, y):
                continue
            if min_gap and any((x - p[0]) ** 2 + (y - p[1]) ** 2 < min_gap * min_gap for p in pts):
                continue
            pts.append((x, y))
        return pts


BASE_PROFILE = ((0.3, 1.0), (0.55, 1.0), (0.8, 0.75), (0.93, 0.3), (1.02, -1.8))


def base_height(patch, x, y, height=0.006, relief=0.0035):
    """The top of the packed layer at (x, y): a low dome, rim sunk under the terrain, a little lumpy."""
    d = patch.d(x, y) / getattr(patch, "base_reach", 1.0)
    if d >= 1.02:
        return G + 0.0
    f = BASE_PROFILE[-1][1]
    pts = BASE_PROFILE
    if d <= pts[0][0]:
        f = pts[0][1]
    else:
        for (d0, f0), (d1, f1) in zip(pts, pts[1:]):
            if d0 <= d <= d1:
                f = f0 + (f1 - f0) * (d - d0) / (d1 - d0)
                break
    lump = mn.noise(Vector((x * 11.0 + patch.seed, y * 11.0, 0.5))) * relief + mn.noise(Vector((x * 33.0, y * 33.0, patch.seed))) * relief * 0.4
    return G + max(f, -2.0) * height + max(0.0, f) * lump


class Heap:
    """A height field the pile is dropped on: `top(x, y)` is how high the ground-plus-pile is there, `stamp` raises it."""

    def __init__(self, patch=None, half=0.62, cell=0.012, height=0.006, relief=0.0035, floor=0.0006, reach=0.74):
        self.cell = cell
        self.half = half
        if patch is not None:
            patch.base_reach = reach
        self.n = int(2 * half / cell) + 1
        self.h = np.full((self.n, self.n), G + floor, dtype=np.float64)
        if patch is not None:
            for i in range(self.n):
                for j in range(self.n):
                    x, y = i * cell - half, j * cell - half
                    if patch.d(x, y) / reach < 1.02:
                        self.h[i, j] = max(G + floor, base_height(patch, x, y, height, relief))

    def _ij(self, x, y):
        i = int(round((x + self.half) / self.cell))
        j = int(round((y + self.half) / self.cell))
        return min(self.n - 1, max(0, i)), min(self.n - 1, max(0, j))

    def top(self, x, y):
        i, j = self._ij(x, y)
        return self.h[i, j]

    def stamp(self, x, y, z):
        i, j = self._ij(x, y)
        if z > self.h[i, j]:
            self.h[i, j] = z

    def stamp_line(self, p, q, z0, z1, step=None):
        step = step or self.cell
        n = max(1, int(math.hypot(q[0] - p[0], q[1] - p[1]) / step))
        for k in range(n + 1):
            f = k / n
            self.stamp(p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f, z0 + (z1 - z0) * f)


def tilted(points, yaw, tilt=(0.0, 0.0)):
    """Rotates local points by `tilt` (degrees about x, y), then `yaw` (radians about z)."""
    rot = Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y")
    return [rot @ Vector(p) for p in points]


def settle(heap, pts, at, gap=0.0012, pad=0.0):
    """Moves local points `pts` (already turned) to x, y = `at` and as low as they can go on the heap: the z offset."""
    z0 = -1e9
    for p in pts:
        z0 = max(z0, heap.top(at[0] + p.x, at[1] + p.y) - p.z)
    return z0 + gap


# ---------------------------------------------------------------- the packed layer

def base_layer(b, mat, patch, rnd, rings=(0.26, 0.5, 0.74, 0.9, 1.0), sectors=28, height=0.006, relief=0.0035,
               edge_sink=0.012, reach=0.74):
    """The dark packed layer under a pile: a ragged low disc (its rim sinks `edge_sink` into the terrain). "t" is 1 in
    the middle and 0 on the rim, for the material to crumble into soil there. Returns nothing."""
    m = b.mesh(mat)
    patch.base_reach = reach
    c = Vector((0.0, 0.0, base_height(patch, 0.0, 0.0, height, relief)))
    m.begin(c)
    center = m.v(c, 1.0, lx=0.5, ly=0.5, lz=0.5, r=0.5, r2=0.5)
    grid = []
    jit = [rnd.uniform(-0.04, 0.04) for _ in range(len(rings) * sectors)]
    for i, rf in enumerate(rings):
        ring = []
        for j in range(sectors):
            a = j / sectors * TAU + rnd.uniform(-0.05, 0.05)
            rr = patch.R(a) * reach * rf * (1.0 + (jit[i * sectors + j] if rf < 0.99 else 0.0))
            x, y = rr * math.cos(a), rr * math.sin(a)
            z = base_height(patch, x, y, height, relief)
            if i == len(rings) - 1:
                z = G - edge_sink
            ring.append(m.v(Vector((x, y, z)), 1.0 - rf, lx=x + 0.5, ly=y + 0.5, lz=0.5, r=rnd.random(), r2=0.5))
        grid.append(ring)
    for j in range(sectors):
        k = (j + 1) % sectors
        m.f((center, grid[0][j], grid[0][k]), True)
    for A, B in zip(grid, grid[1:]):
        for j in range(sectors):
            k = (j + 1) % sectors
            m.f((A[j], B[j], B[k], A[k]), True)


# ---------------------------------------------------------------- leaves

def _curl(x, y, curl, L, ymax, ph):
    """Height of a leaf point (x along, y across in leaf lengths) for `curl` = (taco, tip, wave): edges rolled up (or
    down if negative), the tip curled, and a ripple."""
    taco, tip, wave = curl[:3]
    asym = curl[3] if len(curl) > 3 else 0.0
    z = taco * (1.0 + asym * (1.0 if y > 0 else -1.0)) * (abs(y) / max(ymax, 1e-6)) ** 2 * 0.55 * ymax * L
    z += tip * (x ** 2) * 0.45 * L
    z += wave * 0.1 * L * math.sin(5.0 * x + ph) * (abs(y) / max(ymax, 1e-6))
    return z


def add_leaf(b, mat, outline, length, at, yaw, heap, rnd, curl=(0.0, 0.0, 0.0), tilt=(0.0, 0.0), mid=False, r=None,
             r2=None, lod=0, lod_scale=1.0, gap=0.0012, smooth=True, origin=0.0, max_height=0.045):
    """One leaf: `outline` is a list of (x, y) in leaf lengths, base at the origin of the leaf, x toward the tip,
    wound counter-clockwise; `length` its length in meters; `at` its center's x, y; `yaw` its heading. It's fanned
    from the outline's middle (`mid` adds a ring half way out, for leaves that curl hard), curled by `curl`, turned
    and tilted, dropped onto `heap` and the heap raised under it."""
    r = rnd.random() if r is None else r
    r2 = rnd.random() if r2 is None else r2
    n = len(outline)
    cx = sum(p[0] for p in outline) / n
    cy = sum(p[1] for p in outline) / n
    ymax = max(abs(p[1]) for p in outline)
    ph = rnd.uniform(0.0, TAU)
    shrink = 1.0 - 0.28 * min(1.0, abs(curl[0]))

    def local(x, y):
        return Vector(((x - cx) * length, (y - cy) * shrink * length, _curl(x, y, curl, length, ymax, ph)))

    pts = [local(cx, cy)] + [local(x, y) for x, y in outline]
    ring2 = []
    if mid:
        for x, y in outline:
            mx, my = cx + (x - cx) * 0.55, cy + (y - cy) * 0.55
            ring2.append(local(mx, my))
    allp = pts + ring2
    rot = tilted(allp, yaw, tilt)
    z0 = settle(heap, rot, at, gap)
    if z0 > G + max_height:
        return None
    m = b.mesh(mat)
    old = (b.lod, b.lod_scale)
    b.lod, b.lod_scale = lod, lod_scale
    wc = Vector((at[0], at[1], z0))
    m.begin(wc + rot[0])

    def vert(i, src, e, lxy):
        p = wc + rot[i]
        return m.v(p, max(0.0, min(1.0, lxy[0])), lx=lxy[0] + 0.5 + origin, ly=lxy[1] + 0.5, lz=e, r=r, r2=r2)

    verts = [vert(0, 0, 0.0, (cx, cy))]
    for k, (x, y) in enumerate(outline):
        verts.append(vert(1 + k, 0, 1.0, (x, y)))
    inner = []
    if mid:
        for k, (x, y) in enumerate(outline):
            mx, my = cx + (x - cx) * 0.55, cy + (y - cy) * 0.55
            inner.append(vert(1 + n + k, 0, 0.5, (mx, my)))
    if mid:
        for k in range(n):
            k2 = (k + 1) % n
            m.f((verts[0], inner[k], inner[k2]), smooth)
            m.f((inner[k], verts[1 + k], verts[1 + k2], inner[k2]), smooth)
    else:
        for k in range(n):
            k2 = (k + 1) % n
            m.f((verts[0], verts[1 + k], verts[1 + k2]), smooth)
    # Raise the heap under it
    for i, p in enumerate(rot):
        q = wc + p
        heap.stamp(q.x, q.y, q.z + 0.0012)
    cw = wc + rot[0]
    for k in range(n):
        for f in (0.35, 0.7):
            q = cw.lerp(wc + rot[1 + k], f)
            heap.stamp(q.x, q.y, q.z + 0.0012)
        q = (wc + rot[1 + k]).lerp(wc + rot[1 + (k + 1) % n], 0.5)
        heap.stamp(q.x, q.y, q.z + 0.0012)
    b.lod, b.lod_scale = old
    return wc


def birch_outline(rnd, teeth=4):
    """A birch leaf: ovate-triangular with a truncate base and a long pointed tip, doubly serrated margin (`teeth` teeth
    a side, 2 to 4; alternate points are tooth tips thrown forward). Counter-clockwise from the base."""
    k = rnd.uniform(0.92, 1.08)

    def W(s):
        return k * (0.37 * math.sin(math.pi * s ** 0.62) + 0.13 * (1.0 - s) ** 4)

    if teeth <= 1:
        ss = [0.1, 0.4, 0.75]
    elif teeth >= 4:
        ss = [0.05, 0.15, 0.27, 0.4, 0.53, 0.66, 0.79, 0.9]
    elif teeth == 3:
        ss = [0.06, 0.2, 0.36, 0.52, 0.68, 0.86]
    else:
        ss = [0.08, 0.28, 0.5, 0.74, 0.9]
    sides = {}
    for side in (-1.0, 1.0):
        pts = []
        for n, s in enumerate(ss):
            if n % 2:
                pts.append((s + 0.025 + rnd.uniform(-0.01, 0.01), side * W(s) * rnd.uniform(1.07, 1.17)))
            else:
                pts.append((s, side * W(s) * rnd.uniform(0.9, 0.98)))
        sides[side] = pts
    return [(0.0, 0.0)] + sides[-1.0] + [(1.0, rnd.uniform(-0.01, 0.01))] + list(reversed(sides[1.0]))


def maple_outline(rnd, lobes=5):
    """A sugar maple leaf, stalk end at x = 0: a blade of 5 (or 3) pointed lobes, about as wide as long, rounded U
    sinuses between them, the lowest lobes small. Counter-clockwise from the stalk."""
    ox = 0.17
    if lobes >= 5:
        #  (angle of the vertex from the blade's base, radius)
        table = [(-150, 0.15), (-124, 0.3), (-99, 0.47), (-80, 0.31), (-71, 0.22), (-61, 0.46), (-48, 0.76), (-35, 0.5),
                 (-24, 0.36), (-13, 0.58), (0, 0.9), (13, 0.58), (24, 0.36), (35, 0.5), (48, 0.76), (61, 0.46),
                 (71, 0.22), (80, 0.31), (99, 0.47), (124, 0.3), (150, 0.15)]
    elif lobes <= 3:
        table = [(-135, 0.2), (-92, 0.42), (-52, 0.74), (-26, 0.38), (0, 0.9), (26, 0.38), (52, 0.74), (92, 0.42),
                 (135, 0.2)]
    else:
        table = [(-140, 0.17), (-105, 0.34), (-80, 0.5), (-60, 0.55), (-52, 0.72), (-34, 0.5), (-24, 0.38),
                 (-11, 0.62), (0, 0.88), (11, 0.62), (24, 0.38), (34, 0.5), (52, 0.72), (60, 0.55), (80, 0.5),
                 (105, 0.34), (140, 0.17)]
    out = []
    for a, rr in table:
        rr *= rnd.uniform(0.93, 1.07)
        t = math.radians(a + rnd.uniform(-2.0, 2.0))
        out.append((ox + rr * math.cos(t), rr * math.sin(t)))
    # The stalk: a thin spike back from the notch
    out.append((0.07, 0.012))
    out.append((0.0, 0.0))
    out.append((0.07, -0.012))
    return out


def oak_outline(rnd, lobes=3):
    """A white oak leaf: narrow at the base, widest two thirds up, `lobes` (3, or 2 on small ones) rounded lobes a
    side (flat-topped in outline) with deep sinuses, a broad rounded tip lobe. Counter-clockwise from the base."""
    if lobes >= 3:
        table = [(0.05, 0.05), (0.13, 0.1), (0.19, 0.17), (0.29, 0.18), (0.345, 0.13), (0.40, 0.235), (0.49, 0.245),
                 (0.545, 0.15), (0.60, 0.27), (0.69, 0.27), (0.745, 0.16), (0.80, 0.2), (0.90, 0.185)]
    elif lobes == 2:
        table = [(0.05, 0.06), (0.3, 0.1), (0.37, 0.215), (0.49, 0.23), (0.55, 0.14), (0.62, 0.25), (0.74, 0.25),
                 (0.8, 0.15), (0.9, 0.14)]
    else:
        table = [(0.05, 0.08), (0.3, 0.17), (0.38, 0.2), (0.6, 0.25), (0.82, 0.19)]
    sides = {}
    for side in (-1.0, 1.0):
        sides[side] = [(s + rnd.uniform(-0.012, 0.012), side * w * rnd.uniform(0.9, 1.1)) for s, w in table]
    return [(0.0, 0.0)] + sides[-1.0] + [(1.0, rnd.uniform(-0.01, 0.01))] + list(reversed(sides[1.0]))


# ---------------------------------------------------------------- needles, twigs, lathes, rocks

def needle_bundle(b, mat, heap, at, heading, length, count, rnd, width=0.0028, lod=0, lod_scale=1.0, r=None,
                  spread=0.1, arch=0.006, bowed=0.3):
    """A bundle of `count` pine needles joined at a brown sheath at `at` (x, y), fanning out toward `heading`
    (radians): each a flat ribbon tapering to a point, straight (two triangles) or, in `bowed` of them, bent sideways
    and arching (four), lying on the heap."""
    r = rnd.random() if r is None else r
    needles = []
    for k in range(count):
        hd = heading + (k - (count - 1) / 2.0) * spread + rnd.uniform(-0.04, 0.04)
        L = length * rnd.uniform(0.88, 1.1)
        bow = rnd.uniform(-0.12, 0.12) * L
        d = Vector((math.cos(hd), math.sin(hd), 0.0))
        side = Vector((-d.y, d.x, 0.0))
        rows = (0.0, 0.5, 1.0) if rnd.random() < bowed else (0.0, 1.0)
        lift = arch * rnd.uniform(0.3, 1.2)
        row = []
        for s in rows:
            p = d * (L * s) + side * (bow * math.sin(math.pi * s)) + Vector((0.0, 0.0, lift * math.sin(math.pi * s * 0.9) if len(rows) > 2 else lift * s * 0.6))
            row.append((s, p))
        needles.append((hd, row, side, L))
    z0 = -1e9
    for hd, row, side, L in needles:
        for s, p in row:
            z0 = max(z0, heap.top(at[0] + p.x, at[1] + p.y) - p.z)
    z0 += 0.0008
    m = b.mesh(mat)
    old = (b.lod, b.lod_scale)
    b.lod, b.lod_scale = lod, lod_scale
    base = Vector((at[0], at[1], z0))
    m.begin(base)
    for hd, row, side, L in needles:
        vs = []
        wr = rnd.random()
        n = len(row)
        for idx, (s, p) in enumerate(row):
            w = width * (1.5 if idx == 0 else (0.12 if idx == n - 1 else 1.0)) * rnd.uniform(0.9, 1.15)
            c = base + p
            vs.append((m.v(c - side * (w * 0.5), s, lx=s + 0.5, ly=0.0, r=r, r2=wr),
                       m.v(c + side * (w * 0.5), s, lx=s + 0.5, ly=1.0, r=r, r2=wr)))
            heap.stamp(c.x, c.y, c.z + 0.0013)
        for (a0, b0), (a1, b1) in zip(vs, vs[1:]):
            m.f((a0, a1, b1, b0), False)
        q = base + 0.5 * (row[0][1] + row[-1][1])
        heap.stamp(q.x, q.y, q.z + 0.0013)
    b.lod, b.lod_scale = old
    return base


def _frames(points):
    pts = [Vector(p) for p in points]
    n = len(pts)
    tans = [(pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]).normalized() for i in range(n)]
    nrm = tans[0].cross(UP)
    if nrm.length < 1e-4:
        nrm = tans[0].cross(Vector((1.0, 0.0, 0.0)))
    nrm.normalize()
    out = []
    for T in tans:
        nrm = (nrm - T * nrm.dot(T)).normalized()
        out.append((T, nrm, T.cross(nrm)))
    return pts, out


def tube(b, mat, points, radii, sides=5, t=(0.0, 1.0), jag=0.0, rnd=None, cap_mat=None, caps=(False, False), lod=0,
         lod_scale=1.0, r=None, bend_noise=0.0, along0=0.0):
    """A round tube along `points` (a twig, a branch) with the radius at each point in `radii`. `jag` splinters the
    ends (each end-ring vertex pushed along the axis by up to `jag`); `caps` closes an end (start, end) with a cap in
    `cap_mat` (a pale snapped face). lx is the distance along the tube."""
    rnd = rnd or random
    r = rnd.random() if r is None else r
    pts, fr = _frames(points)
    n = len(pts)
    m = b.mesh(mat)
    old = (b.lod, b.lod_scale)
    b.lod, b.lod_scale = lod, lod_scale
    m.begin(pts[n // 2])
    rings = []
    dist = along0
    rot0 = rnd.uniform(0.0, TAU)
    ends = []
    for i, (p, (T, nr, bi)) in enumerate(zip(pts, fr)):
        if i:
            dist += (p - pts[i - 1]).length
        ring = []
        for j in range(sides):
            a = rot0 + j / sides * TAU
            rad = radii[i] * (1.0 + (rnd.uniform(-0.12, 0.12) if bend_noise else 0.0))
            shift = 0.0
            if jag and i in (0, n - 1):
                shift = rnd.uniform(-jag, jag * 0.25) * (1.0 if i == n - 1 else -1.0)
            pos = p + (nr * math.cos(a) + bi * math.sin(a)) * rad + T * shift
            ring.append(m.v(pos, t[0] + (t[1] - t[0]) * i / max(1, n - 1), lx=dist + 0.5, ly=rad * math.cos(a) + 0.5,
                            lz=rad * math.sin(a) + 0.5, r=r, r2=0.5))
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        for j in range(sides):
            k = (j + 1) % sides
            m.f((A[j], A[k], B[k], B[j]), True)
    for end, idx in ((0, 0), (1, n - 1)):
        if not caps[end] or cap_mat is None:
            continue
        mc = b.mesh(cap_mat)
        mc.begin(pts[idx])
        T = fr[idx][0] * (-1.0 if end == 0 else 1.0)
        ctr = pts[idx] + T * (rnd.uniform(-jag, jag) * 0.5 if jag else 0.0)
        cv = mc.v(ctr, 0.5, lx=0.5, ly=0.5, lz=0.5, r=rnd.random(), r2=0.5)
        rad = radii[idx]
        ring = [mc.v(rings[idx][j].co.copy(), 0.8, lx=0.5 + math.cos(j / sides * TAU) * rad,
                     ly=0.5 + math.sin(j / sides * TAU) * rad, lz=0.5, r=rnd.random(), r2=0.5) for j in range(sides)]
        for j in range(sides):
            k = (j + 1) % sides
            f = mc.f((cv, ring[j], ring[k]) if end == 1 else (cv, ring[k], ring[j]), False)
    b.lod, b.lod_scale = old
    return rings


def lathe(b, mat, profile, center, axis, segments=7, t=None, wobble=None, phase=0.0, smooth=True, lod=0,
          lod_scale=1.0, r=None, r2=None, rnd=None, inward=False, span=TAU):
    """A surface of revolution about `axis` through `center` (kf.revolve's profile: (radius, height along the axis),
    a radius of 0 closes it), in the builder, with faces out (`inward` flips them). lx is the height along the axis."""
    rnd = rnd or random
    r = rnd.random() if r is None else r
    r2 = rnd.random() if r2 is None else r2
    ax, s, u = kf.basis(axis)
    c = Vector(center)
    m = b.mesh(mat)
    old = (b.lod, b.lod_scale)
    b.lod, b.lod_scale = lod, lod_scale
    m.begin(c)
    rings = []
    n = len(profile)
    for i, (rad, h) in enumerate(profile):
        tt = t[i] if t is not None else i / max(1, n - 1)
        if rad <= 1e-6:
            dh = wobble(i, 0.0)[1] if wobble else 0.0
            rings.append([m.v(c + ax * (h + dh), tt, lx=h + dh + 0.5, ly=0.5, lz=0.5, r=r, r2=r2)])
            continue
        ring = []
        full = span >= TAU - 1e-6
        for j in range(segments if full else segments + 1):
            a = phase + j / segments * span
            mult, dh = wobble(i, a) if wobble else (1.0, 0.0)
            rr = rad * mult
            ring.append(m.v(c + ax * (h + dh) + (s * math.cos(a) + u * math.sin(a)) * rr, tt, lx=h + dh + 0.5,
                            ly=rr * math.cos(a) + 0.5, lz=rr * math.sin(a) + 0.5, r=r, r2=r2))
        rings.append(ring)
    k = segments
    full = span >= TAU - 1e-6
    nx = (lambda j: (j + 1) % k) if full else (lambda j: j + 1)
    for A, B in zip(rings, rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            faces = [(A[0], B[nx(j)], B[j]) for j in range(k)]
        elif len(B) == 1:
            faces = [(A[j], A[nx(j)], B[0]) for j in range(k)]
        else:
            faces = [(A[j], A[nx(j)], B[nx(j)], B[j]) for j in range(k)]
        for vs in faces:
            f = m.f(vs, smooth)
            if f is None:
                continue
            f.normal_update()
            pc = f.calc_center_median()
            out = pc - (c + ax * (pc - c).dot(ax))
            if (f.normal.dot(out) < 0.0) != inward:
                f.normal_flip()
    b.lod, b.lod_scale = old
    return rings


def rock(b, mat, center, radii, rnd, subdiv=2, rough=0.14, yaw=0.0, flat=0.0, lod=0, lod_scale=1.0, sink=0.3,
         cut_top=None, planes=(), smooth=True):
    """A small stone: a lumpy ellipsoid of `radii` (a, b, c) centered at `center`, flattened underneath and cut off
    at the ground (the part below it is never made). Faces are flat-shaded planes with noise, like split rock."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    a, bb, c = radii
    size = (a * bb * c) ** (1.0 / 3.0)
    seed = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    rot = Matrix.Rotation(yaw, 3, "Z")
    cen = Vector(center)
    for v in bm.verts:
        u = v.co.normalized()
        p = Vector((u.x * a, u.y * bb, u.z * c))
        q = p / size * 1.4 + seed
        p += u * (mn.fractal(q, 0.5, 2.0, 3, noise_basis="PERLIN_ORIGINAL") * rough * size
                  + 0.3 * mn.noise(q * 4.0) * rough * size)
        # Planar flats: sand down the sharp ellipsoid
        if flat:
            p.z = max(p.z, -c * (1.0 - flat))
        if cut_top is not None:
            p.z = min(p.z, cut_top * c)
        for nrm, d in planes:
            nv = Vector(nrm).normalized()
            over = p.dot(nv) - d
            if over > 0.0:
                p -= nv * over
        v.co = rot @ p + cen
        v.co.z = max(v.co.z, G - 0.004)
    bm.verts.ensure_lookup_table()
    m = b.mesh(mat)
    old = (b.lod, b.lod_scale)
    b.lod, b.lod_scale = lod, lod_scale
    m.begin(cen)
    cache = {}
    top = max(v.co.z for v in bm.verts)
    for f in bm.faces:
        if max(v.co.z for v in f.verts) < G + 0.0015 and min(v.co.z for v in f.verts) <= G - 0.0039:
            continue
        vs = []
        for v in f.verts:
            if v.index not in cache:
                cache[v.index] = m.v(v.co.copy(), (v.co.z - G) / max(1e-3, top - G), r=rnd.random(), r2=rnd.random())
            vs.append(cache[v.index])
        face = m.f(vs, smooth)
        if face is not None:
            face.normal_update()
            if face.normal.dot(face.calc_center_median() - cen) < 0:
                face.normal_flip()
    bm.free()
    b.lod, b.lod_scale = old


# ---------------------------------------------------------------- materials

def _shade(g, col, f):
    return tk._multiply_color(g, col, (f, f, f))


def palette(g, r, stops):
    """A color picked by the random `r` (0..1): `stops` = [(color, weight)], each leaf one of them."""
    total = float(sum(w for _, w in stops))
    acc = stops[0][1] / total
    col = stops[0][0]
    for c, w in stops[1:]:
        col = g.mix(g.ramp(r, acc - 0.018, acc + 0.018), col, c)
        acc += w / total
    return col


def leaf_material(name, stops, kind="pinnate", veins=9.0, slope=0.55, vein_lift=1.35, edge_brown=0.6, spots=0.45,
                  rough=0.8, sat=0.92, value=0.92, ox=0.16, lobes=(0, -50, 50, -103, 103), damp=0.7, bump=0.0016,
                  net=300.0, bleach=0.0):
    """Dead leaves, veined: each leaf one of the palette `stops` ([(color, weight)], picked by its random r), a
    mottle over it, paler veins (a midrib and lateral veins running toward the tip for "pinnate", main veins fanning
    from the stalk for "palmate"), a fine net of veinlets, browned and darker toward the rim, a few rot spots,
    some leaves darker and damp (r2). Needs a leaf made with add_leaf (lx, ly, lz, r, r2)."""
    mat, g = tk.new_material(name)
    lx, ly, e = nk._attr(g, "lx"), nk._attr(g, "ly"), nk._attr(g, "lz")
    r, r2 = nk._attr(g, "r"), nk._attr(g, "r2")
    y = g.math("SUBTRACT", ly, 0.5)
    x = g.math("SUBTRACT", lx, 0.5)
    col = palette(g, r, stops)
    # Mottle: low-frequency tone changes over each leaf, a finer cloudiness
    tone = g.noise(34.0, detail=4.0, roughness=0.6)
    col = g.mix(g.ramp(tone, 0.32, 0.72), col, _shade(g, col, 0.68))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(110.0, detail=3.0), 0.55, 0.8), 0.35), col, _shade(g, col, 1.25))
    # Veins
    if kind == "pinnate":
        ay = g.math("ABSOLUTE", y)
        q = g.math("SUBTRACT", g.math("MULTIPLY", x, veins), g.math("MULTIPLY", ay, veins * slope * 2.0))
        q = g.math("ADD", q, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(70.0, detail=2.0), 0.5), 0.6))
        fr = g.math("FRACT", q)
        dist = g.math("MINIMUM", fr, g.math("SUBTRACT", 1.0, fr))
        lat = g.math("MULTIPLY", g.ramp(dist, 0.1, 0.025), g.ramp(e, 1.0, 0.55))
        lat = g.math("MULTIPLY", lat, g.ramp(x, 0.0, 0.06))
        midrib = g.math("MULTIPLY", g.ramp(ay, 0.026, 0.008), g.ramp(x, 1.0, 0.85))
        vein = g.math("MAXIMUM", g.math("MULTIPLY", lat, 0.85), midrib)
    else:
        vein = None
        for ang in lobes:
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            dx = g.math("SUBTRACT", x, ox)
            perp = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", dx, sa), g.math("MULTIPLY", y, ca)))
            along = g.math("ADD", g.math("MULTIPLY", dx, ca), g.math("MULTIPLY", y, sa))
            line = g.math("MULTIPLY", g.ramp(perp, 0.02, 0.006), g.ramp(along, 0.0, 0.06))
            line = g.math("MULTIPLY", line, g.ramp(e, 1.02, 0.62))
            vein = line if vein is None else g.math("MAXIMUM", vein, line)
        # Fine side veins, branching off the main ones: stripes of distance along the ray field
        ang_f = g.math("ARCTAN2", y, g.math("SUBTRACT", x, ox))
        rad_f = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", y, y), g.math("MULTIPLY", g.math("SUBTRACT", x, ox), g.math("SUBTRACT", x, ox))))
        sec = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", rad_f, 22.0), g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", ang_f, 7.0))), 3.0)))
        sec_l = g.math("MULTIPLY", g.ramp(g.math("MINIMUM", sec, g.math("SUBTRACT", 1.0, sec)), 0.07, 0.015), g.ramp(e, 0.95, 0.5))
        vein = g.math("MAXIMUM", vein, g.math("MULTIPLY", sec_l, 0.45))
    # Fine net of veinlets
    nd = kf._voronoi(g, net, kf._warped(g, 40.0, 0.002), feature="DISTANCE_TO_EDGE")
    netl = g.ramp(nd, 0.07, 0.015)
    col = g.mix(g.math("MULTIPLY", netl, 0.22), col, _shade(g, col, 0.72))
    veinc = g.mix(0.18, _shade(g, col, vein_lift), (0.28, 0.2, 0.08))
    col = g.mix(g.math("MULTIPLY", vein, 0.9), col, veinc)
    # Rot spots and a browned, darker rim
    sd, sr = kf._cells(g, 70.0, kf._warped(g, 80.0, 0.003))
    spot = g.math("MULTIPLY", g.ramp(sd, 0.34, 0.15), g.math("MULTIPLY", g.ramp(sr, 0.5, 0.78),
                                                           g.ramp(g.noise(7.0, detail=3.0), 0.45, 0.7)))
    col = g.mix(g.math("MULTIPLY", spot, spots), col, (0.04, 0.027, 0.014))
    rim = g.math("MULTIPLY", g.ramp(g.math("ADD", e, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(90.0, detail=3.0), 0.5), 0.5)),
                                    0.82, 1.0), edge_brown)
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, _shade(g, col, 0.42))
    # Damp leaves: darker and less rough
    wet = g.math("MULTIPLY", g.ramp(r2, 0.62, 0.9), damp)
    col = g.mix(wet, col, _shade(g, col, 0.5))
    # Fine grain
    grain = g.noise(520.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.6, 0.25), 0.3), col, _shade(g, col, 0.7))
    col = tk.grade(g, col, sat=sat, value=value)
    crinkle = g.noise(75.0, detail=3.0, roughness=0.55)
    height = g.math("ADD", 0.55, g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", grain, 0.5), 0.16),
                                         g.math("MULTIPLY", g.math("SUBTRACT", crinkle, 0.5), 0.7)))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", vein, 0.34), g.math("MULTIPLY", netl, 0.1)))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", spot, 0.15))
    rg = g.mixf(wet, rough, rough - 0.28)
    return tk.finish(mat, g, col, 0.0, rg, g.bump(height, 1.0, bump))


def duff(name, dark, mid, light, soil=(0.032, 0.024, 0.016), scale=100.0, strands=0.0, strand_cols=None, rough=0.92,
         fleck=(0.2, 0.13, 0.055), chips=0.5, bump=0.003):
    """The packed layer under a pile: a dark mottled mulch of crumbled leaf, curved fine lines (stems, veins and edges
    of fragments, drawn as wandering crests), `chips` of lighter fragments of every size (a fraction of cells lit up,
    each its own color), grit and specks, and optional needle strands (`strands` 0..1, lying every which way). "t" is 1
    in the middle and 0 on the rim, where the cover breaks up into bare soil specks."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    base = g.mix(g.ramp(g.noise(16.0, detail=5.0, roughness=0.6), 0.3, 0.72), dark, mid)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=4.0), 0.5, 0.78), 0.5), base, _dark(dark, 0.6))
    # Wandering fine lines, dark and light
    warp = kf._warped(g, 40.0, 0.006)
    ln = kf._ridged(g, g.noise(180.0, detail=3.0, roughness=0.55, vector=warp))
    dark_ln = g.ramp(ln, 0.9, 0.985)
    col = g.mix(g.math("MULTIPLY", dark_ln, 0.45), col, _dark(dark, 0.55))
    ln2 = kf._ridged(g, g.noise(110.0, detail=3.0, roughness=0.55, vector=kf._warped(g, 25.0, 0.01)))
    light_ln = g.math("MULTIPLY", g.ramp(ln2, 0.92, 0.99), g.ramp(g.noise(9.0), 0.4, 0.65))
    col = g.mix(g.math("MULTIPLY", light_ln, 0.5), col, light)
    # Lighter fragments, a fraction of the cells at two sizes
    d1, r1 = kf._cells(g, scale, kf._warped(g, 30.0, 0.004))
    d2, r2 = kf._cells(g, scale * 2.6, kf._warped(g, 70.0, 0.003))
    chip1 = g.math("MULTIPLY", g.ramp(d1, 0.5, 0.2), g.ramp(r1, 1.0 - chips * 0.5, 1.0 - chips * 0.5 + 0.05))
    chip2 = g.math("MULTIPLY", g.ramp(d2, 0.5, 0.18), g.ramp(r2, 1.0 - chips * 0.45, 1.0 - chips * 0.45 + 0.05))
    cc = g.mix(g.ramp(r1, 0.0, 1.0), mid, light)
    col = g.mix(g.math("MULTIPLY", chip1, 0.8), col, cc)
    col = g.mix(g.math("MULTIPLY", chip2, 0.75), col, g.mix(g.ramp(r2, 0.0, 1.0), light, fleck))
    sp, spr = kf._cells(g, 340.0)
    specks = g.math("MULTIPLY", g.ramp(sp, 0.2, 0.08), g.ramp(spr, 0.55, 0.7))
    col = g.mix(g.math("MULTIPLY", specks, 0.35), col, _dark(dark, 0.5))
    height = g.math("ADD", g.math("MULTIPLY", g.noise(60.0, detail=4.0), 0.5), g.math("MULTIPLY", g.math("ADD", chip1, chip2), 0.45))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", dark_ln, 0.35))
    if strands > 0.0 and strand_cols is not None:
        zone = g.noise(5.0, detail=1.0)
        sdr = None
        for k, ang in enumerate((0.0, 1.05, 2.1)):
            mp = g.node("ShaderNodeMapping")
            g.links.new(g.coords(), mp.inputs["Vector"])
            mp.inputs["Rotation"].default_value = (0.0, 0.0, ang + 0.3 * k)
            wv = kf._warped(g, 7.0, 0.014, mp.outputs[0])
            sc = g.node("ShaderNodeMapping")
            g.links.new(wv, sc.inputs["Vector"])
            sc.inputs["Scale"].default_value = (14.0, 380.0, 380.0)
            n = g.noise(1.0, detail=2.0, roughness=0.4, vector=sc.outputs[0])
            line = g.ramp(kf._ridged(g, n), 0.8, 0.97)
            if k == 0:
                mask = g.ramp(zone, 0.42, 0.34)
            elif k == 1:
                mask = g.math("MULTIPLY", g.ramp(zone, 0.3, 0.38), g.ramp(zone, 0.7, 0.62))
            else:
                mask = g.ramp(zone, 0.58, 0.66)
            line = g.math("MULTIPLY", line, mask)
            sdr = line if sdr is None else g.math("MAXIMUM", sdr, line)
        col = g.mix(g.math("MULTIPLY", sdr, strands), col, g.mix(g.ramp(g.noise(30.0), 0.3, 0.7), strand_cols[0], strand_cols[1]))
        height = g.math("ADD", height, g.math("MULTIPLY", sdr, 0.25))
    # Edge: breaks up into specks of soil
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.7), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(26.0, detail=4.0), 0.5), 0.9))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", r1, 0.5), 0.3))
    cover = g.ramp(reach, 0.05, 0.4)
    soilc = g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.3, 0.7), soil, _dark(soil, 2.0))
    col = g.mix(cover, soilc, col)
    height = g.math("MULTIPLY", height, g.math("ADD", 0.35, g.math("MULTIPLY", cover, 0.65)))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, bump))


def _vec(g, x, y, z):
    n = g.node("ShaderNodeCombineXYZ")
    for k, v in enumerate((x, y, z)):
        if hasattr(v, "is_output"):
            g.links.new(v, n.inputs[k])
        else:
            n.inputs[k].default_value = v
    return n.outputs[0]


def _scaled(g, vec, scale):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    return m.outputs[0]


def needle_material(name, light=(0.27, 0.145, 0.055), dark=(0.13, 0.066, 0.028), sheath=(0.06, 0.04, 0.026),
                    tip=(0.27, 0.19, 0.1), rough=0.78):
    """A fallen pine needle (needle_bundle: lx 0 at the sheath to 1 at the tip, ly 0..1 across): russet to tan by r,
    fine streaks along its length, a groove down the middle, a dark papery sheath at the base, bleached tips."""
    mat, g = tk.new_material(name)
    lx, ly = nk._attr(g, "lx"), nk._attr(g, "ly")
    r, r2 = nk._attr(g, "r"), nk._attr(g, "r2")
    s = g.math("SUBTRACT", lx, 0.5)
    across = g.math("ABSOLUTE", g.math("SUBTRACT", ly, 0.5))
    streak = g.noise(1.0, detail=3.0, roughness=0.55, vector=_vec(g, g.math("MULTIPLY", s, 6.0), g.math("MULTIPLY", ly, 36.0), g.math("MULTIPLY", r2, 40.0)))
    col = g.mix(g.ramp(g.math("ADD", r, g.math("MULTIPLY", g.math("SUBTRACT", r2, 0.5), 0.5)), 0.2, 0.8), dark, light)
    col = g.mix(g.math("MULTIPLY", g.ramp(streak, 0.4, 0.72), 0.5), col, _dark(dark, 0.7))
    col = g.mix(g.math("MULTIPLY", g.ramp(across, 0.25, 0.5), 0.4), col, _dark(dark, 0.55))
    col = g.mix(g.ramp(s, 0.78, 1.0), col, tip)
    col = g.mix(g.ramp(s, 0.12, 0.04), col, sheath)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", g.math("MULTIPLY", streak, 0.4), g.math("MULTIPLY", g.ramp(across, 0.0, 0.2), -0.2))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0004))


def twig_bark(name, dark=(0.06, 0.042, 0.028), mid=(0.17, 0.125, 0.085), light=(0.3, 0.23, 0.16),
              inner=(0.3, 0.2, 0.11), peel=0.3, lichen=0.3, rough=0.88, fissure=1.0):
    """Twig and branch bark (a tube made with kg.tube: lx along it, ly and lz round it, in meters): grey-brown with
    long wandering fissures, a stringy grain along it, pale lichen crusts, a few patches peeled to the pale wood under
    (`peel` 0..1) behind a dark lip. Relief in the normal map."""
    mat, g = tk.new_material(name)
    lx, ly, lz = nk._attr(g, "lx"), nk._attr(g, "ly"), nk._attr(g, "lz")
    r = nk._attr(g, "r")
    v = _vec(g, lx, ly, lz)
    # Fissures: crest lines of noise stretched along the twig
    st = _scaled(g, v, (38.0, 520.0, 520.0))
    fis = kf._ridged(g, g.noise(1.0, detail=3.0, roughness=0.5, vector=kf._warped(g, 30.0, 0.004, st)))
    crack = g.ramp(fis, 0.93, 0.995)
    grain = g.noise(1.0, detail=4.0, roughness=0.6, vector=_scaled(g, v, (60.0, 1200.0, 1200.0)))
    tone = g.math("ADD", g.noise(26.0, detail=3.0), g.math("MULTIPLY", g.math("SUBTRACT", r, 0.5), 0.5))
    col = g.mix(g.ramp(tone, 0.3, 0.75), mid, light)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.45, 0.8), 0.55), col, _dark(mid, 0.62))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, dark)
    # Lichen: pale grey-green granular crusts
    lc, lr = kf._cells(g, 420.0, v)
    lich = g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=3.0, vector=v), 0.58, 0.7), g.ramp(lc, 0.55, 0.25))
    lich = g.math("MULTIPLY", lich, lichen)
    col = g.mix(g.math("MULTIPLY", lich, 0.85), col, g.mix(g.ramp(lr, 0.0, 1.0), (0.22, 0.21, 0.14), (0.3, 0.28, 0.18)))
    # Peeled patches: pale inner wood, fibrous, behind a dark lip
    pn = g.math("ADD", g.noise(1.0, detail=4.0, distortion=0.4, vector=_scaled(g, v, (24.0, 160.0, 160.0))),
                g.math("MULTIPLY", g.math("SUBTRACT", g.noise(500.0, detail=2.0), 0.5), 0.05))
    thr = 0.76 - 0.14 * peel
    pe = g.ramp(pn, thr, thr + 0.01)
    lip = g.math("MULTIPLY", g.ramp(pn, thr - 0.03, thr), g.math("SUBTRACT", 1.0, pe))
    fib = g.noise(1.0, detail=3.0, vector=_scaled(g, v, (30.0, 900.0, 900.0)))
    wood = g.mix(g.ramp(fib, 0.35, 0.7), _dark(inner, 0.8), inner)
    wood = g.mix(g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=3.0), 0.5, 0.75), 0.5), wood, _dark(inner, 0.5))
    col = g.mix(g.math("MULTIPLY", lip, 0.85), col, dark)
    col = g.mix(pe, col, wood)
    height = g.math("SUBTRACT", g.math("ADD", 0.6, g.math("MULTIPLY", grain, 0.25)), g.math("MULTIPLY", crack, 0.55 * fissure))
    height = g.mixf(pe, height, g.math("ADD", 0.28, g.math("MULTIPLY", fib, 0.1)))
    height = g.math("ADD", height, g.math("MULTIPLY", lich, 0.1))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0011))


def twig_wood(name, pale=(0.4, 0.3, 0.19), dark=(0.2, 0.13, 0.07), rough=0.9):
    """A snapped end of a twig (the cap of kg.tube): pale wood with growth rings round a darker pith, splintery."""
    mat, g = tk.new_material(name)
    lx, ly = nk._attr(g, "lx"), nk._attr(g, "ly")
    x, y = g.math("SUBTRACT", lx, 0.5), g.math("SUBTRACT", ly, 0.5)
    rr = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    rings = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", rr, 1500.0), g.math("MULTIPLY", g.noise(200.0), 3.0))), -0.3, 0.7)
    fib = g.noise(300.0, detail=4.0)
    col = g.mix(rings, pale, dark)
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.8), 0.35), col, _dark(dark, 0.7))
    col = g.mix(g.ramp(rr, 0.0015, 0.0), col, (0.07, 0.045, 0.03))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.math("ADD", rings, fib), 0.5, 0.0008))


def cone_scale_outline(rnd=None):
    """One pine-cone scale lying loose (leaf units, base at 0): a spatulate woody plate, broad and rounded at the tip."""
    j = (lambda: rnd.uniform(0.92, 1.08)) if rnd else (lambda: 1.0)
    half = [(0.0, 0.13), (0.3, 0.22), (0.68, 0.27), (0.92, 0.21), (1.0, 0.07)]
    lo = [(x, -w * j()) for x, w in half]
    hi = [(x, w * j()) for x, w in reversed(half)]
    return lo + hi


def cone_scale_material(name, dark=(0.08, 0.042, 0.02), light=(0.27, 0.155, 0.07), tip=(0.2, 0.115, 0.055), rough=0.7):
    """A pine-cone scale (lx 0 at the base, 1 at the tip, ly across, r per scale): woody brown, striated along its
    length, the base shaded dark where the scale above covered it, a paler worn tip with a darker raised pad (the umbo)
    and a few resin flecks."""
    mat, g = tk.new_material(name)
    lx, ly, e = nk._attr(g, "lx"), nk._attr(g, "ly"), nk._attr(g, "lz")
    r = nk._attr(g, "r")
    s = g.math("SUBTRACT", lx, 0.5)
    y = g.math("SUBTRACT", ly, 0.5)
    ay = g.math("ABSOLUTE", y)
    stri = g.noise(1.0, detail=3.0, roughness=0.55, vector=_vec(g, g.math("MULTIPLY", s, 3.0), g.math("MULTIPLY", y, 85.0), g.math("MULTIPLY", r, 30.0)))
    ridge = kf._ridged(g, stri)
    col = g.mix(g.ramp(g.math("ADD", g.noise(30.0, detail=3.0), g.math("MULTIPLY", g.math("SUBTRACT", r, 0.5), 0.6)), 0.25, 0.75), tip, light)
    col = g.mix(g.math("MULTIPLY", g.ramp(ridge, 0.7, 0.96), 0.55), col, _dark(dark, 1.3))
    col = g.mix(g.ramp(s, 0.5, 0.0), col, dark)
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.78, 0.95), 0.45), col, tip)
    pad = g.math("MULTIPLY", g.ramp(s, 0.74, 0.82), g.ramp(ay, 0.17, 0.08))
    col = g.mix(g.math("MULTIPLY", pad, 0.8), col, _dark(dark, 1.25))
    chip = g.math("MULTIPLY", g.ramp(e, 0.85, 1.0), g.ramp(g.noise(150.0, detail=3.0), 0.5, 0.72))
    col = g.mix(g.math("MULTIPLY", chip, 0.7), col, _dark(light, 1.1))
    resin_d, resin_r = kf._cells(g, 160.0)
    resin = g.math("MULTIPLY", g.ramp(resin_d, 0.2, 0.08), g.ramp(resin_r, 0.8, 0.88))
    col = g.mix(g.math("MULTIPLY", resin, 0.6), col, (0.34, 0.24, 0.1))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, ridge), 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", pad, 0.35))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0009))


def stone_material(name, light=(0.13, 0.123, 0.112), dark=(0.055, 0.05, 0.045), lichen=1.0, moss=0.0, scale=1.0,
                   rough=0.82, relief=0.0016):
    """A weathered fieldstone, up close (object coordinates): fine crystals and grains, soft blocks of tone, faint
    bedding, pits, hairline cracks, rain-dark streaks, then crustose lichen: grey-green areolate crusts (tiny cracked
    plates, a dark line round their rim) and round orange rosettes, both on the sunny upward sides, and (`moss` 0..1)
    clumps of moss low down and on the north side, as kf.moss_layer."""
    mat, g = tk.new_material(name)
    co = g.coords()
    x, y, z = g.separate(co)
    d1, r1 = kf._cells(g, 240.0 * scale, kf._warped(g, 55.0, 0.0018))
    d2, r2 = kf._cells(g, 55.0 * scale, kf._warped(g, 22.0, 0.004))
    tone = g.noise(4.0 * scale, detail=5.0, roughness=0.6)
    col = g.mix(g.ramp(tone, 0.25, 0.75), dark, light)
    col = g.mix(g.math("MULTIPLY", g.ramp(r2, 0.35, 0.8), 0.5), col, _dark(light, 1.18))
    rust = g.math("MULTIPLY", g.ramp(g.noise(3.2 * scale, detail=5.0, distortion=0.5), 0.58, 0.72), 0.55)
    col = g.mix(rust, col, (0.13, 0.08, 0.045))
    damp = g.math("MULTIPLY", g.ramp(g.noise(5.0 * scale, detail=4.0), 0.55, 0.7), 0.5)
    col = g.mix(damp, col, _dark(dark, 0.7))
    col = g.mix(g.math("MULTIPLY", g.ramp(d2, 0.5, 0.95), 0.25), col, _dark(dark, 0.8))
    grains = g.math("MULTIPLY", g.ramp(d1, 0.5, 0.18), g.ramp(r1, 0.62, 0.9))
    col = g.mix(g.math("MULTIPLY", grains, 0.55), col, _dark(light, 1.35))
    darkg = g.math("MULTIPLY", g.ramp(d1, 0.5, 0.18), g.ramp(r1, 0.05, 0.3))
    col = g.mix(g.math("MULTIPLY", darkg, 0.5), col, _dark(dark, 0.55))
    # Bedding: faint bands across the stone
    bands = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 95.0 * scale), g.math("MULTIPLY", g.noise(7.0, detail=3.0), 5.0))), 0.3, 0.9)
    col = g.mix(g.math("MULTIPLY", bands, 0.22), col, _dark(dark, 0.7))
    # Pits and hairline cracks
    pd, pr = kf._cells(g, 75.0 * scale, kf._warped(g, 40.0, 0.003))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.25, 0.1), g.ramp(pr, 0.7, 0.85))
    col = g.mix(g.math("MULTIPLY", pit, 0.8), col, _dark(dark, 0.3))
    ce = kf._voronoi(g, 7.0 * scale, kf._warped(g, 3.0, 0.1, kf._warped(g, 14.0, 0.02)), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.012, 0.0), g.ramp(g.noise(2.5, detail=2.0), 0.45, 0.62))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, (0.012, 0.011, 0.01))
    # Rain-dark streaks running down the sides
    nz = ks._normal_z(g)
    streak = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=_scaled(g, co, (22.0, 22.0, 2.0))), 0.5, 0.72),
                    g.ramp(nz, 0.85, 0.3))
    col = g.mix(g.math("MULTIPLY", streak, 0.5), col, _dark(dark, 0.55))
    height = g.math("ADD", g.math("MULTIPLY", g.math("ADD", r1, g.noise(400.0 * scale, detail=2.0)), 0.18),
                    g.math("MULTIPLY", g.ramp(d2, 0.9, 0.2), 0.12))
    height = g.math("SUBTRACT", g.math("ADD", height, 0.45), g.math("ADD", g.math("MULTIPLY", pit, 0.35), g.math("MULTIPLY", crack, 0.5)))
    rg = g.mixf(grains, rough, rough - 0.12)
    geo = g.node("ShaderNodeNewGeometry")
    n_y = g.separate(tk._sock(geo.outputs, "Normal"))[1]
    if lichen > 0.0:
        # Grey-green areolate crusts: big wandering patches of tiny plates
        pn = g.math("ADD", g.noise(7.0 * scale, detail=5.0, distortion=0.45),
                    g.math("MULTIPLY", g.math("SUBTRACT", g.noise(70.0 * scale, detail=3.0), 0.5), 0.1))
        sunny = g.ramp(g.math("ADD", g.math("MULTIPLY", nz, 0.7), 0.3), 0.15, 0.55)
        gate = g.math("MULTIPLY", sunny, lichen)
        thr = 0.6 - 0.05 * lichen
        patch = g.math("MULTIPLY", g.ramp(pn, thr, thr + 0.012), g.ramp(g.noise(3.0 * scale, detail=2.0), 0.3, 0.5))
        patch = g.math("MULTIPLY", patch, gate)
        rim = g.math("MULTIPLY", g.ramp(pn, thr - 0.03, thr), g.math("SUBTRACT", 1.0, g.ramp(pn, thr, thr + 0.012)))
        rim = g.math("MULTIPLY", rim, gate)
        ad, ar = kf._cells(g, 420.0 * scale, kf._warped(g, 160.0, 0.0012))
        plate = g.ramp(ad, 0.62, 0.3)
        lc = g.mix(g.ramp(ar, 0.0, 1.0), (0.17, 0.2, 0.125), (0.27, 0.285, 0.19))
        lc = g.mix(g.math("MULTIPLY", g.ramp(g.noise(30.0 * scale, detail=3.0), 0.4, 0.7), 0.6), lc, (0.12, 0.15, 0.085))
        lc = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, plate), 0.85), lc, (0.045, 0.05, 0.03))
        col = g.mix(g.math("MULTIPLY", rim, 0.8), col, (0.025, 0.025, 0.02))
        col = g.mix(patch, col, lc)
        height = g.mixf(patch, height, g.math("ADD", 0.62, g.math("MULTIPLY", plate, 0.22)))
        rg = g.mixf(patch, rg, 0.92)
        # Orange rosettes: round crusts with a bright disc and a dark ring, each cell of a coarse field maybe one
        ovec = kf._warped(g, 6.0, 0.05)
        vn = g.node("ShaderNodeTexVoronoi")
        vn.voronoi_dimensions = "3D"
        vn.feature = "F1"
        g._in(vn, "Scale", 15.0 * scale)
        g._in(vn, "Randomness", 1.0)
        g.links.new(ovec, tk._sock(vn.inputs, "Vector"))
        oc = tk._sock(vn.outputs, "Distance")
        osep = g.node("ShaderNodeSeparateColor")
        g.links.new(tk._sock(vn.outputs, "Color"), osep.inputs[0])
        orr = osep.outputs[0]
        dl = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
        g.links.new(ovec, dl.inputs[0])
        g.links.new(tk._sock(vn.outputs, "Position"), dl.inputs[1])
        dx, dy, dz = g.separate(dl.outputs[0])
        ang = g.math("ARCTAN2", dy, dx)
        lobes = g.math("MULTIPLY", g.math("SINE", g.math("ADD", g.math("MULTIPLY", ang, 6.0), g.math("MULTIPLY", orr, 40.0))), 0.045)
        rad = g.math("ADD", g.math("ADD", 0.14, g.math("MULTIPLY", orr, 0.12)), lobes)
        ragged = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(90.0 * scale, detail=3.0), 0.5), 0.08)
        disc = g.ramp(g.math("ADD", oc, ragged), rad, g.math("SUBTRACT", rad, 0.018))
        disc = g.math("MULTIPLY", disc, g.ramp(orr, 0.18, 0.3))
        disc = g.math("MULTIPLY", g.math("MULTIPLY", disc, g.ramp(g.noise(2.0 * scale, detail=2.0), 0.3, 0.55)), gate)
        ring = g.math("MULTIPLY", g.ramp(g.math("ADD", oc, ragged), g.math("ADD", rad, 0.02), rad), g.math("SUBTRACT", 1.0, disc))
        ring = g.math("MULTIPLY", ring, gate)
        od, orn = kf._cells(g, 700.0 * scale, kf._warped(g, 200.0, 0.0007))
        oplate = g.ramp(od, 0.55, 0.2)
        oc_col = g.mix(g.ramp(orn, 0.0, 1.0), (0.52, 0.24, 0.035), (0.68, 0.36, 0.06))
        oc_col = g.mix(g.ramp(oc, 0.0, rad), _dark((0.6, 0.3, 0.05), 1.0), oc_col)
        oc_col = g.mix(g.math("SUBTRACT", 1.0, oplate), oc_col, (0.2, 0.08, 0.015))
        col = g.mix(g.math("MULTIPLY", ring, 0.55), col, (0.07, 0.06, 0.03))
        col = g.mix(disc, col, oc_col)
        height = g.mixf(disc, height, g.math("ADD", 0.66, g.math("MULTIPLY", oplate, 0.2)))
        rg = g.mixf(disc, rg, 0.9)
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        shade = g.math("ADD", g.math("MULTIPLY", g.math("MAXIMUM", n_y, 0.0), 0.8), g.ramp(z, G + 0.07, G + 0.0))
        reach = g.math("ADD", g.math("MULTIPLY", shade, 0.8 * moss), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(6.0 * scale, detail=5.0), 0.5), 0.8))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.3))
        cover = g.ramp(reach, 0.5, 0.62)
        col = g.mix(cover, col, tk.grade(g, mcol, sat=0.95, value=0.95))
        height = g.mixf(cover, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.7)))
        rg = g.mixf(cover, rg, mrough)
    col = g.mix(g.math("MULTIPLY", g.ramp(z, G + 0.012, G - 0.004), 0.7), col, (0.02, 0.016, 0.012))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rg, g.bump(height, 1.0, relief))


def _dark(c, f):
    return tuple(x * f for x in c)


# ---------------------------------------------------------------- export and previews

QUICK = bool(os.environ.get("NK_QUICK"))

# Bakes are expensive on a shared machine: cap the sample counts zkit asks for (AO asks for 128)
_bake_orig = tk._bake


def _bake_capped(obj, kind, img, samples, **kw):
    return _bake_orig(obj, kind, img, min(samples, 24), **kw)


tk._bake = _bake_capped


def start():
    """nk.reset(), then renders and bakes on the CPU (the GPU is shared with other jobs; set NK_GPU=1 to use it)."""
    nk.reset()
    if not os.environ.get("NK_GPU"):
        bpy.context.scene.cycles.device = "CPU"
        bpy.context.scene.cycles.use_denoising = True
        bpy.context.scene.render.threads_mode = "FIXED"
        bpy.context.scene.render.threads = 2


def export(name, pieces, out_dir, size=1024, coarse=0.4, density=None):
    return ks.export(name, pieces, out_dir, size=size, coarse_ratio=coarse, density=density)


def _ground_floor():
    """Replaces the preview stage's grid floor with a patch of vanilla-looking ground, to judge the patch's edge."""
    floor = bpy.data.objects.get("Floor")
    if floor is None:
        return
    mat, g = tk.new_material("GroundFloor")
    n = g.noise(30.0, detail=5.0)
    n2 = g.noise(3.0, detail=3.0)
    col = g.mix(g.ramp(n, 0.35, 0.7), (0.03, 0.036, 0.016), (0.07, 0.07, 0.03))
    col = g.mix(g.ramp(n2, 0.4, 0.7), col, (0.05, 0.035, 0.02))
    tk.finish(mat, g, col, 0.0, 0.95, g.bump(g.noise(300.0, detail=3.0), 0.15, 0.002))
    floor.data.materials.clear()
    floor.data.materials.append(mat)
    for o in list(bpy.context.scene.objects):
        if o.name.startswith("Scale"):
            bpy.data.objects.remove(o)


VIEWS = {
    "stand": ((0.9, -1.1, G + 1.7), (0.0, 0.0, G), 45),
    "crouch": ((0.55, -0.8, G + 0.85), (0.0, 0.0, G), 40),
    "m3": ((0.0, -3.0, G + 1.7), (0.0, 0.0, G), 50),
    "close": ((0.2, -0.3, G + 0.26), (0.0, 0.0, G), 35),
    "top": ((0.0, -0.01, G + 1.5), (0.0, 0.0, G), 45),
}


def previews(script, name, out_dir, patch=True, shots=None, only=None):
    """Renders the patch as a player would see it: from standing height, crouched, 3 m away, a macro of the middle,
    straight down, the far LOD, and a field of copies on ground-colored terrain. (NK_QUICK=1 skips the bake and
    renders the pieces with their procedural materials, fewer views, for iterating on the look.)"""
    model = bpy.data.objects.get(name) if name else None
    lod = bpy.data.objects.get(name + "_LOD1") if name else None
    tk.preview_stage()
    _ground_floor()
    views = dict(VIEWS)
    if shots:
        views.update(shots)
    tag = script + ("_q" if QUICK else "")
    samples = 12 if QUICK else 16
    res = (800, 600) if QUICK else (1000, 750)
    if QUICK and not only:
        only = ("crouch", "close")
    for v, (loc, tgt, lens) in views.items():
        if only and v not in only:
            continue
        tk.render(tk.camera(script + v, loc, tgt, lens=lens), os.path.join(out_dir, "%s_%s.png" % (tag, v)), res=res,
                  samples=samples)
    if QUICK:
        return
    if lod is not None:
        model.hide_render = True
        lod.hide_render = False
        tk.render(tk.camera(script + "lod", (0.9, -1.1, G + 1.7), (0.0, 0.0, G), lens=45),
                  os.path.join(out_dir, "%s_lod.png" % script), samples=24)
        model.hide_render = False
        lod.hide_render = True
    if patch:
        rnd = random.Random(1)
        copies = []
        for i in range(9):
            c = model.copy()
            tk.link(c)
            c.location = ((i % 3 - 1) * 1.0 + rnd.uniform(-0.1, 0.1), (i // 3 - 1) * 1.0 + rnd.uniform(-0.1, 0.1), 0.0)
            c.rotation_euler = (0.0, 0.0, rnd.uniform(0, TAU))
            copies.append(c)
        tk.render(tk.camera(script + "patch", (0.0, -4.4, G + 2.3), (0.0, 0.0, G), lens=40),
                  os.path.join(out_dir, "%s_patch.png" % script), samples=24)
        for c in copies:
            bpy.data.objects.remove(c)


def build(script, name, pieces, models, previews_dir, size=1024, coarse=0.4, density=None, shots=None, only=None):
    """The end of a piece script: report, then (unless NK_QUICK) bake and export, then previews."""
    report(script, pieces)
    if QUICK:
        previews(script, None, previews_dir, shots=shots, only=only)
        return None
    model = export(name, pieces, models, size=size, coarse=coarse, density=density)
    previews(script, name, previews_dir, shots=shots)
    return model


def report(script, pieces):
    kf.report(script, pieces)
