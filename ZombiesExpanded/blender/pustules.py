"""Pustules: the Bloater's mutation. Clusters of swollen, shiny yellow-green pus sacs and boils on the upper back and
both shoulders, in inflamed, bruised and veiny skin that swells up around them and dives under the zombie's own skin
at the edges. Three parts: Spine2#Back, LeftShoulder#Sacs, RightShoulder#Sacs.

    blender -b --factory-startup --python pustules.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], "Pustules"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)


# ---------------------------------------------------------------- growth helpers (same block in every growth script)
# Growths are modeled as signed distance fields (numpy, vectorized over points) on top of a body field built from
# Joe's hit boxes, meshed with surface nets, relaxed onto the surface and decimated to budget. Per-vertex attributes
# (read in the materials with Attribute nodes) carry masks such as "how far above the skin" into the bake.

def _capsules():
    sk = zk.joe()
    out = {}
    for c in sk.colliders:
        if c["type"] != "capsule":
            continue
        ax = [0.0, 0.0, 0.0]
        ax[c["axis"]] = 1.0
        half = max(0.0, c["height"] / 2 - c["radius"])
        ctr = Vector(c["center"])
        a = sk.point(c["bone"], ctr - Vector(ax) * half)
        b = sk.point(c["bone"], ctr + Vector(ax) * half)
        out[c["bone"]] = (np.array(a), np.array(b), c["radius"])
    return out


CAPS = _capsules()
TORSO = ("Spine2", "Hips", "Head", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm")


def sd_capsule(P, a, b, r):
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
    return np.linalg.norm(P - a - t[:, None] * ab, axis=1) - r


def sd_sphere(P, c, r):
    return np.linalg.norm(P - c, axis=1) - r


def sd_ellipsoid(P, c, radii, frame):
    """An ellipsoid with semi-axes `radii` along the rows of `frame` (3x3, orthonormal)."""
    q = (P - c) @ np.asarray(frame).T
    r = np.asarray(radii, float)
    k0 = np.linalg.norm(q / r, axis=1)
    k1 = np.linalg.norm(q / (r * r), axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def smin(a, b, k):
    """Smooth union: k is the fillet size."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def smooth01(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def body(P, bones=TORSO, k=0.03):
    """Distance to the stand-in body (Joe's hit boxes, smoothly joined)."""
    d = None
    for name in bones:
        a, b, r = CAPS[name]
        e = sd_capsule(P, a, b, r)
        d = e if d is None else smin(d, e, k)
    return d


def normals(fn, P, e=4e-4):
    g = np.stack([fn(P + d) - fn(P - d) for d in np.eye(3) * e], 1)
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)


def settle(fn, P, steps=3, level=0.0):
    """Moves points onto the surface fn = level along the field's gradient."""
    P = np.array(P, float)
    for _ in range(steps):
        P = P - (fn(P) - level)[:, None] * normals(fn, P)
    return P


def on_body(start, bones=TORSO, level=0.0, toward=None):
    """The point on the body nearest `start` (or, given a direction `toward`, where a ray from `start` that way
    meets it) and the outward normal there."""
    fn = lambda P: body(P, bones)  # noqa: E731
    p = np.array([start], float)
    if toward is not None:
        step = np.asarray(toward, float) / np.linalg.norm(toward)
        for _ in range(200):
            d = fn(p)[0] - level
            if abs(d) < 1e-5:
                break
            p = p + step * d
    p = settle(fn, p, 8, level)
    return p[0], normals(fn, p)[0]


def frame_from(n, up=(0.0, 0.0, 1.0)):
    """Rows: two tangents and the normal n."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    t = np.cross(up, n)
    if np.linalg.norm(t) < 1e-6:
        t = np.cross((0.0, 1.0, 0.0), n)
    t /= np.linalg.norm(t)
    return np.array([t, np.cross(n, t), n])


def waves(P, scale, seed, octaves=3):
    """Smooth band-limited noise in about -1..1: sums of sine waves in random directions."""
    rng = np.random.default_rng(seed)
    out = np.zeros(len(P))
    amp, freq, total = 1.0, 2 * math.pi / scale, 0.0
    for _ in range(octaves):
        for _ in range(7):
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            out += amp * np.sin(P @ d * freq * rng.uniform(0.8, 1.25) + rng.uniform(0, 2 * math.pi))
            total += amp
        amp *= 0.5
        freq *= 2.1
    return out * (2.2 / total)


_EDGES = [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0)), ((0, 0, 1), (1, 0, 1)), ((0, 1, 1), (1, 1, 1)),
          ((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0)), ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1)),
          ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1))]


def surface_nets(fn, lo, hi, h):
    """Meshes the surface fn = 0 inside the box lo..hi at grid spacing h. Returns vertices and outward quads."""
    lo = np.asarray(lo, float)
    n = np.maximum(np.ceil((np.asarray(hi, float) - lo) / h).astype(int) + 1, 3)
    axes = [lo[i] + h * np.arange(n[i]) for i in range(3)]
    F = fn(np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)).reshape(tuple(n))
    s = F < 0
    nc = n - 1
    cnt = np.zeros(tuple(nc), np.int8)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                cnt += s[dx:dx + nc[0], dy:dy + nc[1], dz:dz + nc[2]]
    cells = np.argwhere((cnt > 0) & (cnt < 8))
    index = np.full(tuple(nc), -1, np.int64)
    index[tuple(cells.T)] = np.arange(len(cells))
    acc = np.zeros((len(cells), 3))
    num = np.zeros(len(cells))
    for o1, o2 in _EDGES:
        o1, o2 = np.array(o1), np.array(o2)
        i1, i2 = cells + o1, cells + o2
        f1, f2 = F[tuple(i1.T)], F[tuple(i2.T)]
        m = (f1 < 0) != (f2 < 0)
        t = f1[m] / (f1[m] - f2[m])
        acc[m] += i1[m] + t[:, None] * (o2 - o1)
        num[m] += 1
    V = lo + h * acc / np.maximum(num, 1)[:, None]
    quads = []
    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        s0, s1 = [slice(None)] * 3, [slice(None)] * 3
        s0[a], s1[a] = slice(0, n[a] - 1), slice(1, n[a])
        for x in (b, c):
            s0[x] = s1[x] = slice(1, n[x] - 1)
        g = np.argwhere(s[tuple(s0)] != s[tuple(s1)])
        g[:, b] += 1
        g[:, c] += 1
        inside = s[tuple(g.T)]

        def cell(db, dc):
            q = g.copy()
            q[:, b] += db
            q[:, c] += dc
            return index[tuple(q.T)]

        qd = np.stack([cell(-1, -1), cell(0, -1), cell(0, 0), cell(-1, 0)], 1)
        qd[~inside] = qd[~inside][:, ::-1]
        quads.append(qd)
    return V, np.concatenate(quads)


def mesh_verts(obj):
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def put(obj, name, values):
    """Stores a per-vertex float the materials read with an Attribute node."""
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", np.asarray(values, np.float32))


def decimate(obj, tris, keep=None, factor=0.08):
    """Collapses the mesh to about `tris` triangles; keep (0-1 per vertex) makes those vertices costlier to remove,
    so detailed shapes keep more of the budget than plain skin."""
    now = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if now > tris:
        mod = obj.modifiers.new("Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = tris / now
        mod.use_collapse_triangulate = True
        if keep is not None:
            grp = obj.vertex_groups.new(name="decimate")
            k = np.asarray(keep, float)
            w = np.where(k < 0, 0.0, 1.0 - 0.8 * np.clip(k, 0.0, 1.0))  # keep < 0: never collapse
            for i, x in enumerate(w):
                grp.add([i], float(x), "REPLACE")
            mod.vertex_group = grp.name
            mod.vertex_group_factor = factor
        tk.apply_modifiers(obj)
        obj.vertex_groups.clear()
    return obj


def drop_crumbs(bm, fraction=0.05):
    """Deletes the mesh islands far smaller than the biggest (bits of thin wedges deep inside the body)."""
    bm.faces.index_update()
    seen, islands = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isle = [f], []
        seen.add(f.index)
        while stack:
            x = stack.pop()
            isle.append(x)
            for e in x.edges:
                for y in e.link_faces:
                    if y.index not in seen:
                        seen.add(y.index)
                        stack.append(y)
        islands.append(isle)
    if not islands:
        return
    big = max(len(i) for i in islands)
    crumbs = [f for i in islands if len(i) < max(12, big * fraction) for f in i]
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context="FACES")


def field_mesh(name, fn, lo, hi, h, material, tris, inner=-0.05, bones=TORSO, relax=3, keep=None, cut=-0.025,
               region=None, ground=None):
    """A mesh of the growth surface fn = 0 where it stands above `inner` (a level inside the body). The solid between
    the two is meshed closed with surface nets inside the box lo..hi, relaxed for even triangles and decimated to
    about `tris` triangles above `cut`; then the faces below `cut` are dropped, so the mesh's edges lie deep inside
    the body. keep(points) weights the
    decimation toward detail. region(points), a distance that is negative under the growth, bounds the solid
    sideways (its walls must lie below `cut`), which keeps it from wrapping around thin limbs. `ground` is the
    distance to the body the levels are measured from (default: the stand-in, body(points, bones))."""
    from mathutils import Matrix
    if ground is None:
        ground = lambda P: body(P, bones)  # noqa: E731
    if region is None:
        solid = lambda P: smax(fn(P), inner - ground(P), 0.008)  # noqa: E731
    else:
        solid = lambda P: smax(smax(fn(P), inner - ground(P), 0.008), region(P), 0.004)  # noqa: E731
    V, Q = surface_nets(solid, lo, hi, h)
    V = settle(solid, V, 2)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], Q.tolist())
    me.validate()
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.append(material)

    def relaxed(bm, factor):
        # Only clearly above the cut: smoothing across the creases where the shell pinches off throws spikes
        for _ in range(relax):
            free = [v for v in bm.verts if not v.is_boundary]
            P0 = np.array([v.co for v in free])
            free = [v for v, ok in zip(free, ground(P0) > cut + 0.004) if ok]
            bmesh.ops.smooth_vert(bm, verts=free, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
            P0 = np.array([v.co for v in free])
            step = settle(solid, P0, 2) - P0
            size = np.linalg.norm(step, axis=1, keepdims=True)
            P = P0 + step * np.minimum(1.0, 0.006 / np.maximum(size, 1e-9))
            for v, p in zip(free, P):
                v.co = p

    def below(bm, level, any_vertex=False):
        if any_vertex:
            V = np.array([v.co for v in bm.verts])
            low = ground(V) < level
            bm.verts.index_update()
            deep = [any(low[v.index] for v in f.verts) for f in bm.faces]
        else:
            deep = ground(np.array([f.calc_center_median() for f in bm.faces])) < level
        bmesh.ops.delete(bm, geom=[f for f, x in zip(bm.faces, deep) if x], context="FACES")
        drop_crumbs(bm)

    bm = bmesh.new()
    bm.from_mesh(me)
    drop_crumbs(bm)
    relaxed(bm, 0.6)
    bm.to_mesh(me)
    bm.free()
    dense = obj.data
    # Decimate the closed shell (an open edge would throw spikes): hidden faces go first, then plain skin, and the
    # detail keep() marks goes last. Blender ignores the weights where its error metric is tiny, as it is at this
    # scale, so it works on a copy scaled up 100 times.
    Vd = mesh_verts(obj)
    shown = ground(Vd) > cut
    weights = 0.3 * shown
    if keep is not None:
        weights = np.maximum(weights, keep(Vd) * shown)
    centers = np.array([p.center for p in dense.polygons])
    target = tris / max(np.mean(ground(centers) > cut), 0.2)
    best = None
    for _ in range(8):
        obj.data = dense.copy()
        obj.data.transform(Matrix.Scale(100.0, 4))
        decimate(obj, target, weights, factor=1000.0)
        obj.data.transform(Matrix.Scale(0.01, 4))
        centers = np.array([p.center for p in obj.data.polygons])
        shown = np.sum(ground(centers) > cut)
        miss = abs(shown - tris) + 3 * max(shown - tris, 0)  # going over the budget counts more
        if best is None or miss < best[0]:
            best = (miss, obj.data)
        if abs(shown - tris) < 0.03 * tris:
            break
        target *= (tris / max(shown, 1)) ** 0.8
    obj.data = best[1]
    # Even out the decimated triangles (slivers shade badly) without leaving the surface, then drop the hidden wall
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    relaxed(bm, 0.4)
    below(bm, cut)
    bm.to_mesh(obj.data)
    bm.free()
    return tk.smooth(obj, 180.0)


def attr(g, name):
    n = g.node("ShaderNodeAttribute")
    n.attribute_type = "GEOMETRY"
    n.attribute_name = name
    return n.outputs["Fac"]


def vec_attr(g, name):
    n = g.node("ShaderNodeAttribute")
    n.attribute_type = "GEOMETRY"
    n.attribute_name = name
    return n.outputs["Vector"]


def warp(g, vector, scale, amount):
    """Shifts a vector by colored noise, for organic, non-cellular patterns."""
    n = g.node("ShaderNodeTexNoise")
    g._in(n, "Scale", scale)
    g._in(n, "Detail", 3.0)
    g._in(n, "Vector", vector)
    sub = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(tk._sock(n.outputs, "Color"), sub.inputs[0])
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(sub.outputs[0], sc.inputs[0])
    g._in(sc, "Scale", amount)
    add = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(vector, add.inputs[0])
    g.links.new(sc.outputs[0], add.inputs[1])
    return add.outputs[0]


def veins(g, scale, width, warp_amount=0.6, vector=None, broken=0.5, detail=2.5):
    """Wandering, forking veins: 1 on the thin ridges of warped noise (where it crosses its middle), partly faded;
    less detail makes them longer and smoother."""
    v = warp(g, vector if vector is not None else g.coords(), scale * 0.5, warp_amount / scale)
    n = g.noise(scale, detail=detail, roughness=0.45, vector=v)
    line = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), width, 0.0)
    if broken:
        line = g.math("MULTIPLY", line, g.ramp(g.noise(scale * 0.3, detail=2.0), 0.5 - 0.25 * broken, 0.62))
    return line


def preview(name, cam_at, look_at, lens=50, res=(900, 900)):
    tk.render(tk.camera(name, cam_at, look_at, lens=lens), os.path.join(PREVIEWS, name + ".png"), res=res,
              samples=64)

# ---------------------------------------------------------------- end of growth helpers


SKIN = 0.012    # the infected skin's level above the stand-in (which is a little slimmer than the real zombie)
SLOPE = 0.42    # around the sacs the swelling slopes down at about 23 degrees, so it meets any skin at an angle,
DIVE = -0.012   # and below this level it dives steeply,
DEEP = -0.08    # down to here, so its edges vanish under any zombie's skin
EDGE = (SKIN - DIVE) / SLOPE  # the width of the visible slope


class Sac:
    """One swollen pus sac (or a small boil) pushing out of the skin at the body point nearest `start`: a lumpy,
    sagging bulb on a flared, inflamed base, optionally with extra lobes, a pus head, or burst open."""

    def __init__(self, start, R, seed, rise=0.45, elong=1.1, sag=0.18, head=0.0, lean=(0.0, 0.0, 0.0), lobes=0,
                 burst=False, bones=TORSO):
        base, n = on_body(start, bones)
        n = n + np.asarray(lean, float)
        n /= np.linalg.norm(n)
        rng = np.random.default_rng(seed)
        self.base, self.n, self.R, self.seed = base, n, R, seed
        self.frame = frame_from(n, up=(rng.uniform(-0.4, 0.4), 0.3, 1.0))
        t1, t2 = self.frame[0], self.frame[1]
        self.c = base + n * (SKIN + R * rise) + np.array([0.0, 0.0, -R * sag])
        self.radii = (R * rng.uniform(0.88, 1.08), R * rng.uniform(0.9, 1.05), R * elong)
        self.top = self.c + n * R * elong
        self.head, self.burst = head, burst
        self.lobes = []
        for i in range(lobes):
            a = rng.uniform(0, 2 * math.pi)
            r = R * rng.uniform(0.5, 0.7)
            self.lobes.append((self.c + (t1 * math.cos(a) + t2 * math.sin(a)) * R * 0.8 - n * R * 0.15, r))

    def sdf(self, P):
        R = self.R
        d = sd_ellipsoid(P, self.c, self.radii, self.frame)
        for c, r in self.lobes:
            d = smin(d, sd_sphere(P, c, r), R * 0.3)
        flare = sd_ellipsoid(P, self.base + self.n * SKIN * 0.6, (R * 1.5, R * 1.5, R * 0.45), self.frame)
        d = smin(d, flare, R * 0.5)
        if self.head:
            d = smin(d, sd_sphere(P, self.top - self.n * R * 0.1, R * self.head), R * 0.2)
        d = d + waves(P, R * 1.1, self.seed, 2) * R * 0.11
        if self.burst:
            d = smax(d, -sd_sphere(P, self.top + self.n * R * 0.15, R * 0.62), R * 0.15)
        return d


def scatter(region, count, rmin, rmax, seed, avoid, tries=400, bones=TORSO):
    """Small boils at random body points in region = (center, half sizes), clear of the sacs in `avoid`."""
    rng = np.random.default_rng(seed)
    out = []
    c, half = np.asarray(region[0], float), np.asarray(region[1], float)
    for _ in range(tries):
        if len(out) >= count:
            break
        start = c + rng.uniform(-1, 1, 3) * half
        R = rng.uniform(rmin, rmax)
        base, n = on_body(start, bones)
        if any(np.linalg.norm(base - s.base) < (s.R + R) * 1.3 + 0.005 for s in avoid + out):
            continue
        out.append(Sac(start, R, seed * 100 + len(out), rise=rng.uniform(0.0, 0.2), elong=0.85, sag=0.05,
                       head=rng.uniform(0.3, 0.45), bones=bones))
    return out


class Cluster:
    """Sacs on a patch of swollen, infected skin: the skin sits at SKIN over the sacs' footprint (puffing up around
    them and over an optional broad swelling) and slopes away under the body over EDGE."""

    def __init__(self, sacs, seed, swell_at=None, swell=0.0, swell_r=(0.07, 0.07, 0.07), bones=TORSO):
        self.sacs, self.seed, self.bones = sacs, seed, bones
        self.bases = np.array([s.base for s in sacs])
        self.radii = np.array([s.R for s in sacs])
        self.swell_at, self.swell, self.swell_r = swell_at, swell, np.asarray(swell_r, float)

    def beyond(self, P):
        """How far outside the sacs' footprint a point is (0 inside)."""
        d = np.min(np.linalg.norm(P[:, None, :] - self.bases[None], axis=2) - self.radii[None] * 1.0 - 0.002,
                   axis=1)
        return np.maximum(d + waves(P, 0.06, self.seed + 7, 2) * 0.01, 0.0)

    def offset(self, P):
        b = self.beyond(P)
        s = np.sqrt(b * b + 0.01 ** 2) - 0.01
        off = SKIN - SLOPE * s - 1.6 * np.maximum(s - EDGE, 0.0)
        off = np.maximum(off, DEEP)
        inside = 1.0 - smooth01(0.0, 0.03, b)
        off += inside * waves(P, 0.03, self.seed + 3, 2) * 0.0035
        near = np.linalg.norm(P[:, None, :] - self.bases[None], axis=2) / (self.radii[None] * 1.8 + 0.006)
        off += inside * 0.011 * np.max(np.exp(-near ** 2 * 1.5) * np.minimum(self.radii[None] / 0.02, 1.3), axis=1)
        if self.swell_at is not None:
            q = (P - self.swell_at) / self.swell_r
            off += inside * self.swell * np.exp(-np.sum(q * q, axis=1))
        return off

    def skin(self, P):
        return body(P, self.bones) - self.offset(P)

    def field(self, P):
        d = self.skin(P)
        for s in self.sacs:
            d = smin(d, s.sdf(P), s.R * 0.35)
        return d

    def box(self):
        reach = (self.radii * 1.0 + EDGE + 0.07)[:, None]
        tops = np.array([s.base + s.n * (SKIN + s.R * 2.6) for s in self.sacs])
        lo = np.minimum((self.bases - reach).min(0), tops.min(0) - 0.01)
        hi = np.maximum((self.bases + reach).max(0), tops.max(0) + 0.01)
        return lo, hi

    def mesh(self, name, material, tris, h=0.003, inner=-0.05, cut=-0.025):
        lo, hi = self.box()
        keep = lambda P: smooth01(0.003, 0.012, self.skin(P))  # noqa: E731
        region = lambda P: self.beyond(P) - (EDGE + 0.02)  # noqa: E731
        obj = field_mesh(name, self.field, lo, hi, h, material, tris, bones=self.bones, keep=keep, region=region,
                         inner=inner, cut=cut)
        P = mesh_verts(obj)
        lift = self.skin(P)
        put(obj, "sac", smooth01(0.0015, 0.009, lift))
        near = np.zeros(len(P))
        tip = np.zeros(len(P))
        burst = np.zeros(len(P))
        best = np.full(len(P), 1e9)
        hue = np.zeros(len(P))
        for s in self.sacs:
            d = np.linalg.norm(P - s.base, axis=1)
            near = np.maximum(near, np.exp(-(np.maximum(d - s.R * 1.1, 0.0) / (s.R * 0.6 + 0.004)) ** 2))
            sd = np.abs(s.sdf(P))
            closer = sd < best
            best = np.where(closer, sd, best)
            up = np.clip((P - s.c) @ s.n / s.radii[2], 0.0, 1.0)
            tip = np.where(closer, up, tip)
            hue = np.where(closer, np.random.default_rng(s.seed + 999).uniform(), hue)
            burst = np.where(closer, up * float(s.burst), burst)
        on_sac = smooth01(0.002, 0.01, lift)
        put(obj, "near", near)
        put(obj, "hue", hue)
        put(obj, "tip", tip * on_sac)
        put(obj, "burst", smooth01(0.4, 0.75, burst) * on_sac)
        put(obj, "edge", np.clip(self.beyond(P) / EDGE, 0.0, 1.0))
        return obj


def pustule_material(name):
    """Dead, sickly skin going bruised and veiny toward the sacs, peppered with small pimples; the sacs stretched
    thin and shiny over yellow-green pus, red at the base, red capillaries, creamy heads, crusted burst craters."""
    mat, g = tk.new_material(name)
    sac = attr(g, "sac")
    near = attr(g, "near")
    tip = attr(g, "tip")
    burst = attr(g, "burst")
    edge = attr(g, "edge")

    mott = g.noise(14.0, detail=6.0, roughness=0.62)
    skin = g.mix(g.ramp(mott, 0.3, 0.72), (0.3, 0.27, 0.22), (0.2, 0.18, 0.15))
    skin = g.mix(g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=3.0), 0.45, 0.7), 0.6), skin, (0.27, 0.27, 0.16))
    blot = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0, distortion=0.5), 0.55, 0.75), 0.7)
    skin = g.mix(blot, skin, (0.19, 0.12, 0.15))
    inside = g.math("SUBTRACT", 1.0, g.ramp(edge, 0.1, 0.8))
    inflamed = g.math("MAXIMUM", g.ramp(near, 0.05, 0.6), g.math("MULTIPLY", inside, 0.45))
    inflamed = g.math("MULTIPLY", inflamed, g.ramp(g.noise(11.0, detail=5.0), 0.2, 0.55))
    skin = g.mix(g.math("MULTIPLY", inflamed, 0.85), skin, (0.2, 0.05, 0.075))
    skin = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", inside, g.ramp(g.noise(5.0, detail=4.0), 0.5, 0.7)), 0.7),
                 skin, (0.11, 0.035, 0.06))
    skin = g.mix(g.ramp(near, 0.65, 0.98), skin, (0.09, 0.018, 0.025))
    big = veins(g, 9.0, 0.03, warp_amount=1.5, broken=0.6)
    fine = veins(g, 30.0, 0.035, warp_amount=1.5, broken=0.75)
    reach = g.math("ADD", g.math("MULTIPLY", inside, 0.5), g.math("MULTIPLY", near, 0.5))
    vmask = g.math("MAXIMUM", g.math("MULTIPLY", big, reach), g.math("MULTIPLY", fine, g.math("MULTIPLY", near, 0.9)))
    vmask = g.math("MULTIPLY", vmask, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", edge, 0.8)))
    skin = g.mix(g.math("MULTIPLY", vmask, 0.85), skin, (0.07, 0.035, 0.09))
    # Small pimples with yellow heads, crowded near the sacs
    vor = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(vor, "Scale", 95.0)
    g._in(vor, "Randomness", 0.9)
    g.links.new(g.coords(), vor.inputs["Vector"])
    dist = tk._sock(vor.outputs, "Distance")
    pick = g.ramp(g.noise(30.0, detail=2.0), 0.52, 0.6)
    pimple = g.math("MULTIPLY", g.ramp(dist, 0.3, 0.05), g.math("MULTIPLY", pick, g.ramp(near, 0.02, 0.4)))
    pimple = g.math("MULTIPLY", pimple, g.math("SUBTRACT", 1.0, g.ramp(sac, 0.2, 0.6)))
    skin = g.mix(g.math("MULTIPLY", pimple, 0.9), skin, (0.32, 0.07, 0.05))
    skin = g.mix(g.math("MULTIPLY", g.ramp(dist, 0.12, 0.04), pimple), skin, (0.75, 0.66, 0.3))

    hue = attr(g, "hue")
    yellow = g.mix(g.ramp(hue, 0.0, 0.5), (0.55, 0.36, 0.05), (0.5, 0.45, 0.07))
    yellow = g.mix(g.ramp(hue, 0.6, 1.0), yellow, (0.34, 0.4, 0.05))
    pus = g.mix(g.ramp(g.noise(6.0, detail=4.0, distortion=0.4), 0.3, 0.72), yellow, (0.24, 0.28, 0.035))
    pus = g.mix(g.math("MULTIPLY", g.ramp(g.noise(18.0, detail=4.0), 0.5, 0.75), 0.7), pus, (0.16, 0.16, 0.025))
    pus = g.mix(g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=3.0), 0.6, 0.75), 0.5), pus, (0.55, 0.3, 0.06))
    # The stretched skin over the sac: fleshy and bruised low down, thinning to show the pus toward the top
    flesh = g.mix(g.ramp(g.noise(12.0, detail=4.0), 0.3, 0.7), (0.3, 0.09, 0.08), (0.2, 0.06, 0.09))
    thin = g.ramp(g.math("ADD", tip, g.math("MULTIPLY", g.noise(9.0, detail=3.0), 0.25)), 0.25, 0.75)
    pus = g.mix(g.math("SUBTRACT", 1.0, thin), pus, flesh)
    ring = g.math("SUBTRACT", 1.0, g.ramp(sac, 0.1, 0.9))
    pus = g.mix(ring, pus, (0.14, 0.03, 0.04))
    cap = veins(g, 45.0, 0.04, warp_amount=1.5, broken=0.5)
    cap = g.math("MULTIPLY", cap, g.math("SUBTRACT", 1.0, g.ramp(tip, 0.6, 0.9)))
    pus = g.mix(g.math("MULTIPLY", cap, 0.85), pus, (0.2, 0.025, 0.04))
    head = g.ramp(tip, 0.86, 0.98)
    pus = g.mix(g.math("MULTIPLY", head, g.ramp(g.noise(25.0, detail=3.0), 0.3, 0.5)), pus, (0.75, 0.65, 0.35))
    crater = g.mix(g.ramp(g.noise(40.0, detail=5.0), 0.4, 0.6), (0.2, 0.13, 0.03), (0.08, 0.04, 0.015))
    pus = g.mix(burst, pus, crater)
    col = g.mix(g.ramp(sac, 0.25, 0.75), skin, pus)

    # Dried pus crusted around the sacs, and weeping streaks running down
    crust = g.math("MULTIPLY", g.ramp(g.noise(26.0, detail=6.0), 0.6, 0.68), g.ramp(near, 0.25, 0.6))
    crust = g.math("MULTIPLY", crust, g.math("SUBTRACT", 1.0, g.ramp(sac, 0.3, 0.6)))
    col = g.mix(crust, col, (0.25, 0.17, 0.04))
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (30.0, 30.0, 2.5)
    streak = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=3.0, vector=m.outputs[0]), 0.62, 0.72),
                    g.ramp(near, 0.15, 0.5))
    streak = g.math("MULTIPLY", streak, g.math("SUBTRACT", 1.0, g.ramp(sac, 0.2, 0.5)))
    col = g.mix(g.math("MULTIPLY", streak, 0.7), col, (0.3, 0.24, 0.06))
    cav = g.cavity(0.025)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.75), col, (0.05, 0.012, 0.012))

    rough = g.mixf(g.ramp(near, 0.15, 0.85), 0.66, 0.34)
    rough = g.mixf(streak, rough, 0.15)
    sheen = g.math("ADD", 0.12, g.math("MULTIPLY", g.noise(14.0, detail=3.0), 0.12))
    rough = g.mixf(g.ramp(sac, 0.25, 0.75), rough, g.math("ADD", sheen, g.math("MULTIPLY", head, 0.15)))
    rough = g.mixf(g.math("MAXIMUM", crust, g.math("MULTIPLY", burst, 0.7)), rough, 0.8)
    height = g.math("MULTIPLY", g.noise(170.0, detail=4.0), 0.22)
    height = g.math("ADD", height, g.math("MULTIPLY", big, g.math("SUBTRACT", 0.55, g.math("MULTIPLY", sac, 0.45))))
    height = g.math("ADD", height, g.math("MULTIPLY", cap, 0.12))
    height = g.math("ADD", height, g.math("MULTIPLY", pimple, 0.9))
    height = g.math("ADD", height, g.math("MULTIPLY", crust, 0.45))
    height = g.math("ADD", height, g.math("MULTIPLY", burst, g.noise(45.0, detail=5.0)))
    # A dark, ragged rim of grime and dried blood where the patch meets the zombie's clothes or skin, so it reads
    # as torn through them on any zombie rather than laid on top
    rim = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", g.noise(18.0, detail=5.0, distortion=0.4), 0.5)), 0.6, 0.95)
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, (0.03, 0.02, 0.015))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.7, value=0.68)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.25, 0.002))


tk.reset_scene()
zk.stage()
zk.body()
material = pustule_material("Pustule")

# ---- upper back: a swollen hump with a heavy cluster over the right shoulder blade, sacs climbing toward the neck
B = 0.6  # start points behind the back; on_body pulls them onto it
back_sacs = [
    Sac((-0.04, B, 1.42), 0.034, 11, rise=0.5, lobes=2, head=0.25),
    Sac((0.042, B, 1.46), 0.027, 12, rise=0.45, lobes=1),
    Sac((0.025, B, 1.375), 0.022, 13, head=0.3),
    Sac((-0.01, B, 1.5), 0.017, 14, burst=True),
    Sac((-0.085, B, 1.36), 0.017, 15, head=0.35),
    Sac((0.082, B, 1.41), 0.018, 16, lobes=1),
    Sac((0.062, B, 1.335), 0.014, 17, head=0.4),
    Sac((-0.022, B, 1.34), 0.016, 18, burst=True),
    Sac((-0.045, B, 1.505), 0.013, 19, head=0.35),
    Sac((0.035, B, 1.525), 0.011, 20, head=0.3),
]
back_sacs += scatter(((0.0, 0.3, 1.41), (0.085, 0.0, 0.1)), 5, 0.008, 0.012, 5, back_sacs)
back_cluster = Cluster(back_sacs, 31, swell_at=np.array([-0.01, 0.22, 1.43]), swell=0.012, swell_r=(0.08, 0.08, 0.08))
back = back_cluster.mesh("PustulesBack", material, 2700)

# ---- shoulders: a big sac on top of each, smaller ones spilling toward the back; not mirror images
SHOULDER = ("Spine2", "LeftArm", "RightArm")


def shoulder(side, seed):
    s = side
    sacs = [
        Sac((0.155 * s, 0.13, 1.75), 0.027, seed + 1, rise=0.45, lean=(0.15 * s, 0.12, 0.0), lobes=1, bones=SHOULDER),
        Sac((0.19 * s, 0.3, 1.66), 0.018, seed + 2, head=0.3, lobes=1, bones=SHOULDER),
        Sac((0.125 * s, 0.25, 1.72), 0.014, seed + 3, bones=SHOULDER),
        Sac((0.21 * s, 0.12, 1.75), 0.013, seed + 4, burst=side > 0, head=0.0 if side > 0 else 0.35, bones=SHOULDER),
    ]
    sacs += scatter(((0.17 * s, 0.17, 1.58), (0.03, 0.04, 0.02)), 2, 0.008, 0.01, seed + 9, sacs, bones=SHOULDER)
    cluster = Cluster(sacs, seed + 20, bones=SHOULDER)
    return cluster.mesh("Pustules%s" % ("Left" if side > 0 else "Right"), material, 1050, h=0.0028, inner=-0.038,
                        cut=-0.022)


left = shoulder(1, 40)
right = shoulder(-1, 60)

zk.on(back, "Spine2", "Back")
zk.on(left, "LeftShoulder", "Sacs")
zk.on(right, "RightShoulder", "Sacs")
pieces = [back, left, right]
for p in pieces:
    V = mesh_verts(p)
    print("[pustules] %s: %d tris, bounds %s .. %s" % (p.name, sum(len(f.vertices) - 2 for f in p.data.polygons),
                                                      np.round(V.min(0), 3), np.round(V.max(0), 3)))
parts = zk.export("Pustules", pieces, ASSETS)
focus = Vector((0.0, 0.12, 1.42))
zk.previews("pustules", PREVIEWS, focus, distance=1.25)
preview("pustules_close_back", (0.12, 0.95, 1.55), (0.0, 0.2, 1.42), lens=60)
preview("pustules_close_shoulder", (0.55, 0.45, 1.75), (0.16, 0.12, 1.53), lens=60)
# Straight across the back with the near arm hidden, to see the swelling meet the body
for o in bpy.context.scene.objects:
    if o.name in ("Body_9", "Body_10", "BodyRightHand"):
        o.hide_render = True
preview("pustules_profile", (-1.0, 0.24, 1.45), (0.0, 0.24, 1.42), lens=70)
print("[pustules] done")
