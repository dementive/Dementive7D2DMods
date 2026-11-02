"""Bone spurs: the Spiked mutation. Yellowed, sharp bone spurs erupting from the spine (a ridge down the back), the
tops of both shoulders and along the outside of both forearms, each out of a swollen mound of torn, bloody skin.
Five parts: Spine2#Spine, LeftArm#Spurs, RightArm#Spurs, LeftForeArm#Spurs, RightForeArm#Spurs.

    blender -b --factory-startup --python bone_spurs.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "BoneSpurs"), args[1]
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


SKIN = 0.01     # the skin's level above the stand-in (which is a little slimmer than the real zombie)
SLOPE = 0.5     # the mounds slope down at about 27 degrees, so they meet any skin at an angle,
DIVE = -0.012   # and below this level dive steeply,
DEEP = -0.08    # down to here, so their edges vanish under any zombie's skin
EDGE = (SKIN - DIVE) / SLOPE


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def put_vec(obj, name, values):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.asarray(values, np.float32).ravel())


class Spur:
    """A bone spur breaking out of the body point nearest `start`: tilted off the surface normal by `tilt`, curving
    by `bend` (a direction, scaled by its length), flattened into a blade along `row`."""

    def __init__(self, start, length, rb, seed, tilt=(0.0, 0.0, 0.0), bend=(0.0, 0.0, 0.0), row=(0.0, 0.0, 1.0),
                 bones=TORSO, flat=0.7, toward=None):
        base, n = on_body(start, bones, toward=toward)
        self.n = n
        self.d = unit(n + np.asarray(tilt, float))
        self.base = base + n * SKIN
        self.L, self.rb, self.seed = length, rb, seed
        self.bend = np.asarray(bend, float)
        self.row = np.asarray(row, float)
        self.flat = flat
        f = frame_from(self.d, up=self.row)
        self.e1, self.e2 = f[0], f[1]
        rng = np.random.default_rng(seed)
        self.phase = rng.uniform(0, 2 * math.pi, 4)
        self.gore = rng.uniform(0.45, 1.0)

    def rho(self, P):
        q = P - self.base
        along = q @ self.d
        return np.linalg.norm(q - along[:, None] * self.d, axis=1), along, q

    def angle(self, q):
        return np.arctan2(q @ self.e2, q @ self.e1)

    def tear(self, a):
        """How high the torn skin stands around the hole (0.1-1), ragged."""
        p = self.phase
        x = 0.5 + 0.35 * np.sin(3 * a + p[0]) + 0.25 * np.sin(7 * a + p[1]) + 0.15 * np.sin(11 * a + p[2])
        return np.clip(x, 0.05, 1.0) ** 1.4

    def mesh(self, name, material, segs=7):
        """The spur: rings along a crooked, curving path from 2 cm under the skin to a sharp tip, ridged and knobbly
        near the root; the big ones fork a small prong off one side."""
        sink = 0.022
        P0 = self.base - self.d * sink
        span = self.L + sink
        t0 = sink / span
        rng = np.random.default_rng(self.seed + 5)
        kink = np.cross(self.d, unit(rng.normal(size=3))) * self.L * 0.08
        knob = rng.uniform(0, 2 * math.pi, 3)

        def at(t):
            p = P0 + self.d * span * t + self.bend * self.L * t * t + kink * math.sin(math.pi * t)
            tan = unit(self.d * span + 2 * self.bend * self.L * t + kink * math.pi * math.cos(math.pi * t))
            return p, tan

        def radius(u):
            if u < 0:
                return self.rb * 1.3
            return self.rb * (1 - u) ** 0.8 * (1 + 0.3 * math.exp(-(u / 0.14) ** 2))

        bm = bmesh.new()
        ts, sps = [], []

        def tube(path, us, rad, segs, flat, ridge, t_of_u, cap):
            rings = []
            for u in us:
                p, tan = path(u)
                e1 = unit(self.row - (self.row @ tan) * tan)
                e2 = np.cross(tan, e1)
                r = rad(u)
                twist = 0.4 * max(u, 0.0)
                ring = []
                for k in range(segs):
                    a = 2 * math.pi * k / segs
                    rr = r * (1 + ridge * math.sin(3 * a + self.phase[3]) + ridge * 0.5 * math.sin(5 * a + knob[0]))
                    if u < 0.35:
                        rr *= 1 + 0.3 * (1 - max(u, 0.0) / 0.35) * max(0.0, math.sin(2 * a + knob[1])) ** 2
                    ca, sa = math.cos(a + twist), math.sin(a + twist)
                    ring.append(bm.verts.new(p + (e1 * ca + e2 * sa * flat) * rr))
                    ts.append(t_of_u(u))
                    sps.append((math.cos(a), math.sin(a), max(u, -0.2)))
                rings.append(ring)
            for i in range(len(rings) - 1):
                r0, r1 = rings[i], rings[i + 1]
                for k in range(segs):
                    bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
            tip = bm.verts.new(path(1.0)[0])
            ts.append(t_of_u(1.0))
            sps.append((0.0, 0.0, 1.0))
            for k in range(segs):
                bm.faces.new((rings[-1][k], rings[-1][(k + 1) % segs], tip))
            if cap:
                p, tan = path(us[0])
                bottom = bm.verts.new(p - tan * 0.002)
                ts.append(t_of_u(us[0]))
                sps.append((0.0, 0.0, -0.2))
                for k in range(segs):
                    bm.faces.new((rings[0][(k + 1) % segs], rings[0][k], bottom))

        def main(u):
            t = t0 + (1 - t0) * u if u >= 0 else t0 * (1 + u)
            return at(t)

        us = [-0.6, -0.15, 0.0, 0.1, 0.24, 0.4, 0.57, 0.73, 0.87]
        if self.L < 0.045:
            us = [-0.6, -0.1, 0.0, 0.14, 0.35, 0.58, 0.8]
        tube(main, us, radius, segs, self.flat, 0.11, lambda u: max(u, 0.0), True)
        if self.L > 0.06:
            # A small prong forking off partway up
            ua = 0.3
            pa, tan = main(ua)
            side = unit(np.cross(tan, self.e2 if rng.uniform() < 0.5 else -self.e2) + tan * 0.15)
            plen = self.L * 0.3
            ra = radius(ua) * 0.42
            start = pa + side * radius(ua) * 0.2
            pdir = unit(tan * 0.8 + side)

            def prong(u):
                return start + pdir * plen * u + tan * plen * 0.35 * u * u, pdir

            tube(prong, [0.0, 0.35, 0.7], lambda u: ra * (1 - u) ** 0.8, 5, 0.85, 0.06,
                 lambda u: ua + 0.6 * u, True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        obj = tk.mesh_object(name, bm, material)
        put(obj, "t", ts)
        put_vec(obj, "sp", sps)
        put(obj, "gore", [self.gore] * len(ts))
        return tk.smooth(obj, 75.0)


class Roots:
    """The swollen mounds of torn skin the spurs break out of: skin raised around each base, a ragged lip of torn
    skin standing up around a hole the bone comes through, an optional swollen ridge (the spine)."""

    def __init__(self, spurs, seed, bones=TORSO, ridge=None, inner=-0.05, cut=-0.025):
        self.spurs, self.seed, self.bones, self.ridge = spurs, seed, bones, ridge
        self.inner, self.cut = inner, cut
        self.bases = np.array([s.base for s in spurs])
        self.rbs = np.array([s.rb for s in spurs])

    def beyond(self, P):
        d = np.min(np.linalg.norm(P[:, None, :] - self.bases[None], axis=2) - self.rbs[None] * 1.5, axis=1)
        if self.ridge is not None:
            a, b, w = self.ridge
            d = np.minimum(d, sd_capsule(P, a, b, w))
        return np.maximum(d + waves(P, 0.05, self.seed + 7, 2) * 0.006, 0.0)

    def offset(self, P):
        b = self.beyond(P)
        s = np.sqrt(b * b + 0.008 ** 2) - 0.008
        off = SKIN - SLOPE * s - 1.6 * np.maximum(s - EDGE, 0.0)
        off = np.maximum(off, DEEP)
        inside = 1.0 - smooth01(0.0, 0.025, b)
        off += inside * waves(P, 0.03, self.seed + 3, 2) * 0.002
        for sp in self.spurs:
            rho, along, q = sp.rho(P)
            near = np.exp(-(np.linalg.norm(q, axis=1) / (sp.rb * 2.6)) ** 2)
            off += inside * near * sp.rb * 0.45
            lip = np.exp(-((rho - sp.rb * 1.2) / (sp.rb * 0.5)) ** 2) * sp.tear(sp.angle(q))
            off += lip * sp.rb * 1.1 * (np.abs(along) < 0.05)
        return off

    def skin(self, P):
        return body(P, self.bones) - self.offset(P)

    def field(self, P):
        d = self.skin(P)
        for sp in self.spurs:
            rho, along, q = sp.rho(P)
            hole = np.where(np.abs(along) < 0.06, sp.rb * 0.92 - rho, -1.0)
            d = smax(d, hole, sp.rb * 0.15)
        return d

    def box(self):
        reach = (self.rbs * 2.0 + EDGE + 0.07)[:, None]
        lo, hi = (self.bases - reach).min(0), (self.bases + reach).max(0)
        if self.ridge is not None:
            a, b, w = self.ridge
            lo = np.minimum(lo, np.minimum(a, b) - w - EDGE - 0.07)
            hi = np.maximum(hi, np.maximum(a, b) + w + EDGE + 0.07)
        return lo, hi

    def mesh(self, name, material, tris, h=0.0026):
        lo, hi = self.box()
        def keep(P):
            k = np.zeros(len(P))
            for sp in self.spurs:
                rho, along, q = sp.rho(P)
                k = np.maximum(k, np.exp(-(np.maximum(rho - sp.rb * 1.1, 0.0) / sp.rb) ** 2) * (np.abs(along) < 0.03))
            return k

        region = lambda P: self.beyond(P) - (EDGE + 0.016)  # noqa: E731
        obj = field_mesh(name, self.field, lo, hi, h, material, tris, bones=self.bones, keep=keep, inner=self.inner,
                         cut=self.cut, region=region)
        P = mesh_verts(obj)
        wound = np.zeros(len(P))
        hole = np.zeros(len(P))
        bruise = np.zeros(len(P))
        drip = np.zeros(len(P))
        for sp in self.spurs:
            rho, along, q = sp.rho(P)
            dist = np.linalg.norm(q, axis=1)
            wound = np.maximum(wound, np.exp(-(np.maximum(rho - sp.rb * 1.1, 0.0) / (sp.rb * 0.8)) ** 2))
            hole = np.maximum(hole, smooth01(sp.rb * 1.25, sp.rb * 0.95, rho) * smooth01(0.004, -0.004, along))
            bruise = np.maximum(bruise, np.exp(-(dist / (sp.rb * 4.0)) ** 2))
            # Blood runs down from the hole
            drop = sp.base[2] - P[:, 2]
            side = np.abs((P - sp.base) @ unit(np.cross((0.0, 0.0, 1.0), sp.n) + 1e-9))
            drip = np.maximum(drip, smooth01(-0.004, 0.006, drop) * np.exp(-drop / 0.08)
                              * np.exp(-(side / (sp.rb * 1.6)) ** 2))
        put(obj, "wound", wound)
        put(obj, "hole", hole)
        put(obj, "bruise", bruise)
        put(obj, "drip", drip)
        put(obj, "edge", np.clip(self.beyond(P) / EDGE, 0.0, 1.0))
        return obj


def skin_material(name):
    """Dead skin swelling into bruised purple, then raw, wet red flesh at the torn lips, black blood down the holes,
    and trickles of blood running down from them."""
    mat, g = tk.new_material(name)
    wound = attr(g, "wound")
    hole = attr(g, "hole")
    bruise = attr(g, "bruise")
    drip = attr(g, "drip")
    edge = attr(g, "edge")

    mott = g.noise(14.0, detail=6.0, roughness=0.62)
    skin = g.mix(g.ramp(mott, 0.3, 0.72), (0.3, 0.27, 0.22), (0.2, 0.18, 0.15))
    skin = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0, distortion=0.5), 0.55, 0.75), 0.6), skin,
                 (0.19, 0.12, 0.15))
    inside = g.math("SUBTRACT", 1.0, g.ramp(edge, 0.1, 0.8))
    bz = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(bruise, 0.1, 0.7), g.math("MULTIPLY", inside, 0.6)),
                g.ramp(g.noise(10.0, detail=5.0), 0.2, 0.55))
    skin = g.mix(g.math("MULTIPLY", bz, 0.9), skin, (0.17, 0.045, 0.07))
    vein = veins(g, 10.0, 0.03, warp_amount=1.5, broken=0.6)
    skin = g.mix(g.math("MULTIPLY", vein, g.math("MULTIPLY", g.math("ADD", bruise, inside), 0.45)), skin,
                 (0.08, 0.03, 0.08))
    # Raw flesh and blood
    raw = g.mix(g.ramp(g.noise(30.0, detail=5.0), 0.3, 0.7), (0.36, 0.035, 0.03), (0.2, 0.015, 0.02))
    torn = g.ramp(g.math("ADD", wound, g.math("MULTIPLY", g.noise(25.0, detail=4.0), 0.3)), 0.55, 0.85)
    col = g.mix(torn, skin, raw)
    col = g.mix(hole, col, (0.05, 0.004, 0.006))
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (45.0, 45.0, 3.0)
    trickle = g.ramp(g.noise(1.0, detail=3.0, vector=m.outputs[0]), 0.55, 0.62)
    trickle = g.math("MULTIPLY", trickle, g.ramp(drip, 0.15, 0.5))
    blood = g.math("MAXIMUM", trickle, g.math("MULTIPLY", g.ramp(wound, 0.3, 0.55), 0.6))
    col = g.mix(g.math("MULTIPLY", blood, 0.85), col, (0.12, 0.006, 0.008))
    cav = g.cavity(0.02)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.7), col, (0.04, 0.008, 0.01))

    rough = g.mixf(g.ramp(bruise, 0.2, 0.8), 0.62, 0.42)
    rough = g.mixf(g.math("MAXIMUM", torn, blood), rough, 0.16)
    rough = g.mixf(hole, rough, 0.1)
    height = g.math("MULTIPLY", g.noise(170.0, detail=4.0), 0.25)
    height = g.math("ADD", height, g.math("MULTIPLY", vein, 0.4))
    height = g.math("ADD", height, g.math("MULTIPLY", torn, g.noise(60.0, detail=6.0)))
    height = g.math("ADD", height, g.math("MULTIPLY", trickle, 0.25))
    # A dark, ragged rim of grime and dried blood where the patch meets the zombie's clothes or skin, so it reads
    # as torn through them on any zombie rather than laid on top
    rim = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", g.noise(18.0, detail=5.0, distortion=0.4), 0.5)), 0.6, 0.95)
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, (0.03, 0.02, 0.015))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.75, value=0.75)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.002))


def bone_material(name):
    """Old yellowed bone: ivory near the sharp tips, stained brown toward the base, with fine grain running along
    each spur, hairline cracks and pits, and blood caked up from the root (some spurs bloodier than others)."""
    mat, g = tk.new_material(name)
    t = attr(g, "t")
    gore = attr(g, "gore")
    sp = vec_attr(g, "sp")
    grain_v = g.node("ShaderNodeMapping")
    g.links.new(sp, grain_v.inputs["Vector"])
    grain_v.inputs["Scale"].default_value = (5.0, 5.0, 0.35)
    grain = g.noise(3.0, detail=5.0, roughness=0.6, vector=grain_v.outputs[0])
    co = g.coords()

    bone = g.mix(g.ramp(g.noise(9.0, detail=5.0), 0.3, 0.7), (0.56, 0.46, 0.27), (0.42, 0.32, 0.16))
    bone = g.mix(g.ramp(t, 0.6, 0.97), bone, (0.68, 0.61, 0.44))
    bone = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.4, 0.62), 0.7), bone, (0.27, 0.18, 0.08))
    blotch = g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=5.0, distortion=0.6), 0.55, 0.72), 0.7)
    bone = g.mix(blotch, bone, (0.3, 0.2, 0.09))
    stain = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(t, 0.05, 0.55)), 0.85)
    bone = g.mix(stain, bone, (0.24, 0.13, 0.06))
    crack = veins(g, 22.0, 0.018, warp_amount=0.6, broken=0.7)
    bone = g.mix(g.math("MULTIPLY", crack, 0.85), bone, (0.12, 0.07, 0.035))
    vor = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(vor, "Scale", 160.0)
    g.links.new(co, vor.inputs["Vector"])
    pits = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.16, 0.06), g.ramp(g.noise(8.0), 0.5, 0.65))
    bone = g.mix(g.math("MULTIPLY", pits, 0.8), bone, (0.16, 0.1, 0.05))

    # Blood: caked thick at the root, a ragged line partway up, a few runs toward the tip
    reach = g.math("ADD", g.math("MULTIPLY", gore, 0.16), g.math("MULTIPLY", g.noise(6.0, detail=4.0), 0.14))
    coat = g.ramp(g.math("SUBTRACT", reach, t), -0.04, 0.04)
    runs = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=2.0, vector=grain_v.outputs[0]), 0.64, 0.68),
                  g.math("SUBTRACT", 1.0, g.ramp(t, 0.15, 0.6)))
    blood = g.math("MAXIMUM", coat, g.math("MULTIPLY", runs, g.math("MULTIPLY", gore, 0.7)))
    fresh = g.mix(g.ramp(g.noise(20.0, detail=4.0), 0.35, 0.7), (0.24, 0.015, 0.015), (0.09, 0.006, 0.008))
    col = g.mix(blood, bone, fresh)
    col = g.mix(g.ramp(g.separate(sp)[2], 0.0, -0.1), col, (0.07, 0.005, 0.007))

    rough = g.math("ADD", 0.42, g.math("MULTIPLY", g.ramp(grain, 0.3, 0.7), 0.16))
    rough = g.mixf(g.ramp(t, 0.6, 1.0), rough, 0.3)
    rough = g.mixf(blood, rough, 0.14)
    height = g.math("MULTIPLY", grain, 0.6)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.5))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", pits, 0.4))
    height = g.math("ADD", height, g.math("MULTIPLY", coat, 0.25))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.85, value=0.85)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.0015))


tk.reset_scene()
zk.stage()
zk.body()
skin_mat = skin_material("TornSkin")
bone_mat = bone_material("Bone")

# ---- the spine: a ridge of spurs down the back, biggest between the shoulder blades, flanked by smaller ones
B = 0.6
spine = []
for i, (z, L, rb, tz) in enumerate([(1.235, 0.045, 0.0095, -0.3), (1.29, 0.068, 0.0115, -0.22),
                                    (1.345, 0.092, 0.0135, -0.12), (1.4, 0.11, 0.015, -0.04),
                                    (1.455, 0.1, 0.014, 0.06), (1.51, 0.075, 0.012, 0.16),
                                    (1.555, 0.048, 0.0095, 0.26)]):
    jitter = np.random.default_rng(300 + i).uniform(-0.06, 0.06)
    spine.append(Spur((0.0, B, z), L, rb, 300 + i, tilt=(jitter, 0.0, tz), bend=(jitter * 0.5, 0.0, 0.22),
                      toward=(0.0, -1.0, 0.0)))
for i, (x, z, L, rb) in enumerate([(0.04, 1.32, 0.03, 0.0075), (-0.043, 1.37, 0.034, 0.008),
                                   (0.045, 1.43, 0.036, 0.008), (-0.042, 1.485, 0.028, 0.007)]):
    s = 1 if x > 0 else -1
    spine.append(Spur((x, B, z), L, rb, 320 + i, tilt=(0.55 * s, 0.0, 0.05), bend=(0.1 * s, 0.0, 0.25),
                      toward=(0.0, -1.0, 0.0)))
spine_roots = Roots(spine, 41)
pieces = []
root = spine_roots.mesh("SpineRoots", skin_mat, 720)
zk.on(root, "Spine2", "Spine")
pieces.append(root)
for i, s in enumerate(spine):
    pieces.append(zk.on(s.mesh("SpineSpur%d" % i, bone_mat, segs=7 if s.L > 0.08 else 6), "Spine2", "Spine"))

# ---- shoulders: three spurs breaking out of the top of each shoulder, sweeping up and out
SHOULDER = ("Spine2", "LeftArm", "RightArm")


def shoulder(side, seed):
    s = side
    arm = unit(CAPS["LeftArm" if s > 0 else "RightArm"][0] - CAPS["LeftArm" if s > 0 else "RightArm"][1]) * -1
    spurs = [
        Spur((0.17 * s, 0.08, 1.66), 0.075, 0.0135, seed + 1, tilt=(0.2 * s, 0.12, 0.15), bend=(0.12 * s, 0.1, 0.1),
             row=arm, bones=SHOULDER),
        Spur((0.215 * s, 0.13, 1.62), 0.055, 0.011, seed + 2, tilt=(0.3 * s, 0.2, 0.0), bend=(0.15 * s, 0.1, 0.12),
             row=arm, bones=SHOULDER),
        Spur((0.135 * s, 0.15, 1.67), 0.038, 0.009, seed + 3, tilt=(0.05 * s, 0.3, 0.1), bend=(0.05 * s, 0.1, 0.15),
             row=arm, bones=SHOULDER),
    ]
    roots = Roots(spurs, seed + 10, bones=SHOULDER, inner=-0.038, cut=-0.022)
    bone = "LeftArm" if s > 0 else "RightArm"
    out = [zk.on(roots.mesh("ShoulderRoots%d" % s, skin_mat, 320), bone, "Spurs")]
    for i, sp in enumerate(spurs):
        out.append(zk.on(sp.mesh("ShoulderSpur%d_%d" % (s, i), bone_mat, segs=7 if sp.L > 0.07 else 6), bone,
                         "Spurs"))
    return out


# ---- forearms: a row of swept-back blades along the outside of each forearm, biggest by the elbow
def forearm(side, seed):
    s = side
    bone = "LeftForeArm" if s > 0 else "RightForeArm"
    elbow = np.array(zk.joe().pos(bone))
    wrist = np.array(zk.joe().pos("LeftHand" if s > 0 else "RightHand"))
    axis = unit(wrist - elbow)
    out_dir = unit(np.array([0.707 * s, 0.35, 0.707]))
    spurs = []
    for i, (f, L, rb) in enumerate([(0.12, 0.065, 0.0115), (0.36, 0.058, 0.0105), (0.58, 0.046, 0.0095),
                                    (0.78, 0.032, 0.0075)]):
        start = elbow + (wrist - elbow) * f + out_dir * 0.2
        spurs.append(Spur(start, L, rb, seed + i, tilt=-axis * 0.45, bend=-axis * 0.35, row=axis,
                          bones=(bone,), flat=0.6))
    roots = Roots(spurs, seed + 10, bones=TORSO, inner=-0.03, cut=-0.016)
    out = [zk.on(roots.mesh("ForearmRoots%d" % s, skin_mat, 300, h=0.0024), bone, "Spurs")]
    for i, sp in enumerate(spurs):
        out.append(zk.on(sp.mesh("ForearmSpur%d_%d" % (s, i), bone_mat, segs=6), bone, "Spurs"))
    return out


pieces += shoulder(1, 400) + shoulder(-1, 420) + forearm(1, 500) + forearm(-1, 520)
for label in ("Spine2#Spine", "LeftArm#Spurs", "RightArm#Spurs", "LeftForeArm#Spurs", "RightForeArm#Spurs"):
    objs = [p for p in pieces if p["zbone"] == label]
    V = np.vstack([mesh_verts(p) for p in objs])
    print("[bone_spurs] %s: %d tris, bounds %s .. %s" % (
        label, sum(len(f.vertices) - 2 for p in objs for f in p.data.polygons), np.round(V.min(0), 3),
        np.round(V.max(0), 3)))
parts = zk.export("BoneSpurs", pieces, ASSETS)
zk.previews("bone_spurs", PREVIEWS, Vector((0.0, 0.1, 1.35)), distance=1.6)
preview("bone_spurs_close_back", (0.45, 0.85, 1.5), (0.0, 0.2, 1.4), lens=55)
preview("bone_spurs_close_forearm", (0.95, -0.25, 1.5), (0.46, 0.08, 1.2), lens=55)
for o in bpy.context.scene.objects:
    if o.name in ("Body_9", "Body_10", "BodyRightHand"):
        o.hide_render = True
preview("bone_spurs_profile", (-1.1, 0.3, 1.42), (0.0, 0.25, 1.4), lens=55)
print("[bone_spurs] done")
