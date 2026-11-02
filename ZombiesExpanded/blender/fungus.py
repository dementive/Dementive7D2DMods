"""Fungus: the Regenerator's mutation. Knobby fungal masses and tiers of thick bracket shelves bursting out of tight
mounds of rotten flesh, in four optional clusters (each zombie shows a different mix): over the left shoulder blade
(Spine2#BackVar1), low on the right of the back (Spine2#BackVar2), on top of the left deltoid (LeftArm#ShoulderVar)
and out of the left cheek (Head#FaceVar).

    blender -b --factory-startup --python fungus.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "Fungus"), args[1]
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


STEEP = 2.2     # a mound's walls slope at about 65 degrees, so they meet any zombie's skin close to the growths,
DEEP = -0.07    # and dive to here, far under any zombie's skin
UP = np.array([0.0, 0.0, 1.0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class Knob:
    """A rounded fungal knob (a puffball gone wrong), a little squashed along the surface normal n."""

    def __init__(self, c, r, n, seed, squash=0.85):
        self.c, self.r, self.n, self.seed = np.asarray(c, float), r, unit(n), seed
        rng = np.random.default_rng(seed)
        self.frame = frame_from(self.n, up=(rng.uniform(-1, 1), rng.uniform(-1, 1), 1.0))
        self.radii = (r * rng.uniform(0.95, 1.15), r * rng.uniform(0.88, 1.05), r * squash)

    def sdf(self, P):
        d = sd_ellipsoid(P, self.c, self.radii, self.frame)
        return d + waves(P, self.r * 0.9, self.seed, 2) * self.r * 0.07


class Bracket:
    """A thick, fleshy bracket fungus growing out of root point A: a lobed half-disc in plan sticking out `D` along
    `out` (kept near level, as brackets grow), `W` wide, `T` thick at the root, with a domed top, a flatter underside,
    a fat rounded margin that ruffles up and down, and the outer part drooping."""

    def __init__(self, A, out, W, D, T, seed, droop=0.35, rise=0.0, ruffle=0.3):
        rng = np.random.default_rng(seed)
        o = unit(np.array([out[0], out[1], 0.0]))
        o = unit(o + UP * rise)
        side = unit(np.cross(UP, o))
        self.F = np.array([o, side, np.cross(o, side)])
        self.A, self.W, self.D, self.T = np.asarray(A, float), W, D, T
        self.ph = rng.uniform(0, 2 * math.pi, 5)
        self.droop, self.ruffle = droop, ruffle
        self.seed = seed

    def local(self, P):
        q = (P - self.A) @ self.F.T
        u, v, w = q[:, 0], q[:, 1], q[:, 2]
        th = np.arctan2(v / (self.W * 0.5), u / self.D)
        m = 1.0 + 0.13 * np.sin(3 * th + self.ph[0]) + 0.06 * np.sin(6 * th + self.ph[1])
        a, b = self.D * m, self.W * 0.5 * m
        rn = np.sqrt((u / a) ** 2 + (v / b) ** 2)
        return u, v, w, a, b, rn, th

    def sdf(self, P):
        u, v, w, a, b, rn, th = self.local(P)
        r1 = np.minimum(rn, 1.0)
        bend = self.droop + self.ruffle * (0.6 * np.sin(4 * th + self.ph[2]) + 0.4 * np.sin(7 * th + self.ph[3]))
        w = w + bend * self.T * r1 * r1
        thick = self.T * (0.42 + 0.58 * np.sqrt(np.maximum(1.0 - r1 ** 2, 0.0)))
        thick = thick * (1.0 + 0.07 * np.sin(r1 * 17.0 + self.ph[4]) * r1)
        top, bot = thick * 0.7, -thick * 0.3
        dv = np.maximum(w - top, bot - w)
        k1 = np.sqrt((u / (a * a)) ** 2 + (v / (b * b)) ** 2)
        d2 = rn * (rn - 1.0) / np.maximum(k1, 1e-9)
        d = smax(d2, dv, self.T * 0.3)
        return smax(d, -(u + 0.35 * self.D), 0.004)

    def rho(self, P):
        return np.clip(self.local(P)[5], 0.0, 1.0)

    def reach(self):
        return max(self.D, self.W * 0.5) * 1.3 + self.T


class Cluster:
    """A fungal cluster bursting out of the body: a tight, steep mound of rotten flesh crowded with knobby fungal
    masses, and tiers of thick bracket shelves growing out of the masses. One closed surface, so everything grows out
    of everything else with real fillets. `skin` is the mound's top above the stand-in."""

    def __init__(self, seed, bones=TORSO, skin=0.018, inner=-0.065, cut=-0.04, h=0.002):
        self.seed, self.bones = seed, bones
        self.level, self.inner, self.cut, self.h = skin, inner, cut, h
        self.edge = (skin + 0.012) / STEEP  # how far out from the footprint the walls stand above the skin, about
        self.knobs, self.feet, self.shelves = [], [], []

    # -- building
    def knob(self, start, r, lift=0.3, toward=None, foot=0.7, kids=0, squash=0.85):
        base, n = on_body(start, self.bones, toward=toward)
        seed = self.seed * 1000 + len(self.knobs)
        k = Knob(base + n * (self.level + r * lift), r, n, seed, squash)
        self.knobs.append(k)
        self.feet.append((base, r * foot))
        rng = np.random.default_rng(seed + 7)
        for _ in range(kids):
            # Smaller knobs crowding the upper side of a big one, cauliflower-like
            d = unit(k.frame.T @ np.array([rng.normal(), rng.normal(), abs(rng.normal()) * 0.8 + 0.45]))
            kr = r * rng.uniform(0.36, 0.52)
            self.knobs.append(Knob(k.c + d * r * rng.uniform(0.72, 0.86), kr, d, seed + 500 + len(self.knobs), 0.9))
        return k

    def scatter(self, start, toward, size, count, rmax, rmin, angle=0.0, seed=0, kids=2):
        """A crowd of knobs over an elliptic patch `size` (half-widths along and across, turned `angle` from level)
        around the body point where a ray from `start` `toward` meets it: biggest in the middle, smaller and lower
        toward the edge, packed without much overlap."""
        base, n = on_body(start, self.bones, toward=toward)
        f = frame_from(n)
        ca, sa = math.cos(angle), math.sin(angle)
        e1, e2 = f[0] * ca + f[1] * sa, -f[0] * sa + f[1] * ca
        rng = np.random.default_rng(self.seed * 77 + seed)
        placed = []
        tries = 0
        while len(placed) < count and tries < 4000:
            tries += 1
            x, y = rng.uniform(-1, 1, 2)
            rr = x * x + y * y
            if rr > 1:
                continue
            r = (rmin + (rmax - rmin) * (1 - rr) ** 1.5) * rng.uniform(0.8, 1.1)
            p = base + e1 * x * size[0] + e2 * y * size[1]
            if any(np.linalg.norm(p - q) < 0.85 * (r + s) for q, s in placed):
                continue
            placed.append((p, r))
        placed.sort(key=lambda t: -t[1])
        for p, r in placed:
            big = (r - rmin) / max(rmax - rmin, 1e-6)
            self.knob(p + n * 0.25, r, 0.55 * big - 0.05, -n, kids=int(round(kids * big + 0.3)))

    def shelf(self, start, out, W, D, T, toward=None, inset=0.35, foot=0.15, **kw):
        """A bracket growing out of the body point nearest `start` (or where a ray from it `toward` meets it), its
        root sunk `inset` of its depth back into the mound, which spreads under it."""
        base, n = on_body(start, self.bones, toward=toward)
        o = unit(np.array([out[0], out[1], 0.0]))
        A = base + n * (self.level + T * 0.15) - o * D * inset
        s = Bracket(A, out, W, D, T, self.seed * 1000 + 600 + len(self.shelves), **kw)
        self.shelves.append(s)
        self.feet.append((base, W * foot))
        return s

    def tier(self, start, out, sizes, step, spin=0.25, toward=None, **kw):
        """Brackets stacked one over another, like a tier on a trunk: `sizes` (W, D, T) from the bottom up, `step`
        apart, each turned a little."""
        rng = np.random.default_rng(self.seed + len(self.shelves) * 13)
        start = np.asarray(start, float)
        o = np.array([out[0], out[1], 0.0])
        for i, (W, D, T) in enumerate(sizes):
            a = rng.uniform(-spin, spin)
            ca, sa = math.cos(a), math.sin(a)
            oi = np.array([o[0] * ca - o[1] * sa, o[0] * sa + o[1] * ca])
            self.shelf(start + UP * step * i, oi, W, D, T, toward=toward, **kw)

    # -- fields
    def beyond(self, P):
        """Distance outside the mound's footprint (discs around the knobs' and shelves' bases), ragged."""
        bases = np.array([b for b, _ in self.feet])
        rs = np.array([r for _, r in self.feet])
        d = np.min(np.linalg.norm(P[:, None, :] - bases[None], axis=2) - rs[None], axis=1)
        return np.maximum(d + waves(P, 0.04, self.seed + 7, 2) * 0.005, 0.0)

    def offset(self, P):
        b = self.beyond(P)
        s = np.sqrt(b * b + 0.004 ** 2) - 0.004
        off = np.maximum(self.level - STEEP * s, DEEP)
        inside = 1.0 - smooth01(0.0, 0.015, b)
        return off + inside * waves(P, 0.018, self.seed + 3, 2) * 0.004

    def ground(self, P):
        return body(P, self.bones)

    def skin(self, P):
        return self.ground(P) - self.offset(P)

    def mass(self, P):
        d = None
        for k in self.knobs:
            e = k.sdf(P)
            d = e if d is None else smin(d, e, k.r * 0.06)
        return d

    def core(self, P):
        return smin(self.skin(P), self.mass(P), 0.008)

    def brackets(self, P):
        d = None
        for s in self.shelves:
            e = s.sdf(P)
            d = e if d is None else smin(d, e, 0.003)
        return d

    def field(self, P):
        if not self.shelves:
            return self.core(P)
        return smin(self.core(P), self.brackets(P), 0.005)

    # -- mesh
    def box(self):
        pts, rs = [], []
        for b, r in self.feet:
            pts.append(b)
            rs.append(r + self.edge + 0.035)
        for k in self.knobs:
            pts.append(k.c)
            rs.append(k.r * 1.4)
        for s in self.shelves:
            pts.append(s.A)
            rs.append(s.reach())
        pts, rs = np.array(pts), np.array(rs)[:, None]
        return (pts - rs).min(0), (pts + rs).max(0)

    def region(self, P):
        d = self.beyond(P) - (self.edge + 0.03)
        if self.shelves:
            d = np.minimum(d, self.brackets(P) - 0.006)
        return d

    def mesh(self, name, material, tris):
        lo, hi = self.box()

        def keep(P):
            k = 0.8 * smooth01(0.004, -0.002, self.mass(P))
            if self.shelves:
                k = np.maximum(k, smooth01(0.004, -0.001, self.brackets(P)))
            return k

        obj = field_mesh(name, self.field, lo, hi, self.h, material, tris, inner=self.inner, bones=self.bones,
                         keep=keep, cut=self.cut, region=self.region, ground=self.ground)
        P = mesh_verts(obj)
        d_skin, d_mass = self.skin(P), self.mass(P)
        d_shelf = self.brackets(P) if self.shelves else np.full(len(P), 1.0)
        fung = np.minimum(d_mass, d_shelf)
        put(obj, "rot", smooth01(-0.0025, 0.003, fung - d_skin))
        put(obj, "shelf", smooth01(-0.0015, 0.002, np.minimum(d_mass, d_skin) - d_shelf))
        put(obj, "near", np.exp(-(np.maximum(d_mass, 0.0) / 0.009) ** 2))
        put(obj, "edge", np.clip(self.beyond(P) / self.edge, 0.0, 1.0))
        put(obj, "deep", smooth01(0.006, -0.02, self.ground(P)))
        put(obj, "low", smooth01(self.level + 0.016, self.level - 0.002, self.ground(P)))
        # Knobs: how high up the nearest knob a point is (0 underneath, 1 on top)
        ks = np.stack([k.sdf(P) for k in self.knobs], 1)
        tip = np.zeros(len(P))
        near = np.argmin(ks, 1)
        for i, k in enumerate(self.knobs):
            m = near == i
            tip[m] = np.clip(0.5 + 0.5 * ((P[m] - k.c) @ k.n) / (k.r * 0.85), 0.0, 1.0)
        put(obj, "tip", tip)
        # And a random shade per knob, so the crowd isn't all one colour
        put(obj, "kv", np.random.default_rng(self.seed).uniform(0.0, 1.0, len(self.knobs))[near])
        # Shelves: across the nearest shelf (0 at the root, 1 at the margin) and its underside
        rho = np.zeros(len(P))
        under = np.zeros(len(P))
        sv = np.zeros(len(P))
        if self.shelves:
            N = normals(self.field, P)
            ss = np.stack([s.sdf(P) for s in self.shelves], 1)
            near = np.argmin(ss, 1)
            for i, s in enumerate(self.shelves):
                m = near == i
                rho[m] = s.rho(P[m])
                sv[m] = np.random.default_rng(s.seed).uniform()
                under[m] = smooth01(-0.15, -0.55, N[m] @ s.F[2])
        put(obj, "rho", rho)
        put(obj, "under", under)
        put(obj, "sv", sv)
        return obj


# ---------------------------------------------------------------- material

def knob_cells(g, scale, smoothness=0.4):
    """1 in the middle of rounded cells, 0 in the cracks between them (warped smooth Voronoi)."""
    v = g.node("ShaderNodeTexVoronoi", feature="SMOOTH_F1")
    g._in(v, "Scale", scale)
    g._in(v, "Smoothness", smoothness)
    g.links.new(warp(g, g.coords(), scale * 0.3, 0.4 / scale), v.inputs["Vector"])
    return g.math("SUBTRACT", 1.0, g.math("POWER", tk._sock(v.outputs, "Distance"), 1.5), clamp=True)


def fungus_material(name):
    """Rotten flesh, near black and blood-brown, with pale mycelium creeping over it right around the growths and
    staining the growths' roots where they break out of the zombie; knobby fungal masses, ochre-brown with cracked,
    cauliflower skin, darker down their sides and pale-specked on their crowns, each a little different; bracket
    shelves with dark brown concentric growth zones on top, an ochre band and a narrow pale rim at the margin, and a
    dull tan underside packed with pores. Dark and matte overall: the game's shader shows pale or glossy surfaces much
    brighter and flatter than Blender does."""
    mat, g = tk.new_material(name)
    rot = attr(g, "rot")
    shelf = attr(g, "shelf")
    near = attr(g, "near")
    edge = attr(g, "edge")
    deep = attr(g, "deep")
    low = attr(g, "low")
    tip = attr(g, "tip")
    kv = attr(g, "kv")
    rho = attr(g, "rho")
    sv = attr(g, "sv")
    under = attr(g, "under")

    # ---- rotten flesh
    mott = g.noise(16.0, detail=6.0, roughness=0.6)
    flesh = g.mix(g.ramp(mott, 0.3, 0.72), (0.024, 0.012, 0.009), (0.012, 0.006, 0.005))
    bruise = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=4.0, distortion=0.4), 0.5, 0.7), 0.8)
    flesh = g.mix(bruise, flesh, (0.024, 0.008, 0.011))
    blood = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=5.0, distortion=0.6), 0.48, 0.62), 0.9)
    flesh = g.mix(blood, flesh, (0.04, 0.006, 0.004))
    wrinkle = veins(g, 24.0, 0.04, warp_amount=1.2, broken=0.4)
    flesh = g.mix(g.math("MULTIPLY", wrinkle, 0.6), flesh, (0.006, 0.004, 0.003))
    # Pale mycelium creeping over the rot right around the masses: fuzz, and a few threads reaching out
    fuzz = g.math("MULTIPLY", g.ramp(g.noise(120.0, detail=6.0, roughness=0.8), 0.6, 0.72),
                  g.ramp(near, 0.7, 0.98))
    threads = g.math("MULTIPLY", veins(g, 70.0, 0.03, warp_amount=2.0, broken=0.8), g.ramp(near, 0.1, 0.6))
    myc = g.math("MAXIMUM", fuzz, g.math("MULTIPLY", threads, 0.6))
    flesh = g.mix(g.math("MULTIPLY", myc, 0.5), flesh, (0.09, 0.078, 0.06))
    # Darker and dirtier down the mound's walls into the zombie, so it reads as torn up out of it
    stain = g.math("MAXIMUM", g.ramp(edge, 0.2, 0.9), g.math("MULTIPLY", deep, 0.9))
    stain = g.math("MULTIPLY", stain, g.ramp(g.noise(14.0, detail=4.0), 0.15, 0.5))
    flesh = g.mix(g.math("MULTIPLY", stain, 0.85), flesh, (0.008, 0.005, 0.004))

    # ---- fungal knobs: dirty brown, darker down their sides, pale specks only on the crowns
    cells = knob_cells(g, 150.0)
    big = knob_cells(g, 55.0, 0.6)
    knob = g.mix(g.ramp(tip, 0.3, 0.95), (0.016, 0.01, 0.006), (0.058, 0.034, 0.016))
    ochre = g.math("MULTIPLY", g.ramp(g.noise(13.0, detail=5.0, distortion=0.6), 0.55, 0.7), 0.7)
    knob = g.mix(ochre, knob, (0.075, 0.04, 0.013))
    caps = g.math("MULTIPLY", g.ramp(tip, 0.7, 0.95), g.ramp(g.noise(40.0, detail=5.0, roughness=0.7), 0.55, 0.64))
    knob = g.mix(caps, knob, (0.22, 0.19, 0.14))
    # Some knobs darker and redder, some paler
    dark = g.mix(0.5, knob, (0.03, 0.014, 0.009))
    knob = g.mix(g.math("MULTIPLY", g.ramp(kv, 0.3, 0.0), 0.5), knob, dark)
    knob = g.mix(g.math("MULTIPLY", g.ramp(kv, 0.8, 1.0), 0.3), knob, (0.1, 0.085, 0.06))
    cracks = g.math("MAXIMUM", g.ramp(cells, 0.5, 0.15), g.math("MULTIPLY", g.ramp(big, 0.45, 0.1), 0.9))
    knob = g.mix(g.math("MULTIPLY", cracks, 0.85), knob, (0.022, 0.015, 0.01))
    spots = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(spots, "Scale", 300.0)
    g.links.new(g.coords(), spots.inputs["Vector"])
    pits = g.math("MULTIPLY", g.ramp(tk._sock(spots.outputs, "Distance"), 0.12, 0.05),
                  g.ramp(g.noise(7.0), 0.5, 0.65))
    knob = g.mix(g.math("MULTIPLY", pits, 0.8), knob, (0.025, 0.017, 0.011))

    # ---- bracket shelves
    wob = g.math("ADD", rho, g.math("MULTIPLY", g.noise(14.0, detail=3.0), 0.05))
    zones = g.math("SINE", g.math("MULTIPLY", wob, 38.0))
    broad = g.math("SINE", g.math("MULTIPLY", wob, 11.0))
    top = g.mix(g.ramp(zones, -0.8, 0.8), (0.024, 0.015, 0.009), (0.058, 0.037, 0.019))
    top = g.mix(g.math("MULTIPLY", g.ramp(broad, 0.3, 0.9), 0.65), top, (0.018, 0.012, 0.008))
    grain = g.noise(60.0, detail=6.0, roughness=0.7)
    top = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.35, 0.7), 0.4), top, (0.02, 0.014, 0.009))
    top = g.mix(g.ramp(rho, 0.8, 0.9), top, (0.09, 0.055, 0.022))
    top = g.mix(g.ramp(rho, 0.93, 0.99), top, (0.22, 0.19, 0.14))
    top = g.mix(g.ramp(rho, 0.45, 0.1), top, (0.02, 0.013, 0.009))
    pores = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(pores, "Scale", 280.0)
    g.links.new(g.coords(), pores.inputs["Vector"])
    pore = g.ramp(tk._sock(pores.outputs, "Distance"), 0.3, 0.12)
    bottom = g.mix(g.ramp(g.noise(9.0, detail=3.0), 0.3, 0.7), (0.13, 0.108, 0.075), (0.085, 0.068, 0.045))
    bottom = g.mix(g.math("MULTIPLY", pore, 0.7), bottom, (0.032, 0.025, 0.017))
    bottom = g.mix(g.ramp(rho, 0.5, 0.15), bottom, (0.025, 0.017, 0.011))
    sh = g.mix(under, top, bottom)
    # Each shelf its own shade: some rustier, some darker
    sh = g.mix(g.math("MULTIPLY", g.ramp(sv, 0.6, 1.0), 0.45), sh, g.mix(0.5, sh, (0.09, 0.04, 0.014)))
    sh = g.mix(g.math("MULTIPLY", g.ramp(sv, 0.35, 0.0), 0.5), sh, g.mix(0.6, sh, (0.02, 0.014, 0.01)))

    col = g.mix(g.math("SUBTRACT", 1.0, rot), flesh, knob)
    col = g.mix(shelf, col, sh)
    # Rot climbing the roots of the growths where they break out of the zombie, ragged
    climb = g.ramp(g.math("ADD", low, g.math("MULTIPLY", g.noise(20.0, detail=4.0), 0.5)), 0.6, 0.95)
    climb = g.math("MULTIPLY", climb, g.math("SUBTRACT", 1.0, rot))
    col = g.mix(climb, col, flesh)
    # Grime over everything
    grime = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0), 0.4, 0.75), 0.45)
    col = g.mix(grime, col, (0.02, 0.014, 0.01))
    cav = g.cavity(0.02)
    col = g.mix(g.ramp(cav, 0.85, 0.35), col, (0.008, 0.005, 0.004))

    # The game's shader shows these far brighter than Blender does: darkened to sit with the zombies' own clothes
    # and skin in the Unity renders, so only the shelves' rims and undersides and the knobs' specks read pale
    col = tk.grade(g, col, sat=1.05, value=0.62)

    # Roughness: wet only in the blood and the rot, matte everywhere else
    wet = g.math("MAXIMUM", rot, climb)
    rough = g.mixf(blood, 0.84, 0.62)
    rough = g.mixf(wet, g.math("ADD", 0.8, g.math("MULTIPLY", cells, 0.08)), rough)
    rough = g.mixf(g.math("MULTIPLY", shelf, g.math("SUBTRACT", 1.0, climb)), rough, g.mixf(under, 0.82, 0.9))
    height = g.math("MULTIPLY", g.noise(150.0, detail=4.0), 0.25)
    height = g.math("ADD", height, g.math("MULTIPLY", wrinkle, -0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", myc, 0.3))
    k_h = g.math("ADD", g.math("MULTIPLY", cells, 0.9), g.math("MULTIPLY", big, 1.2))
    k_h = g.math("SUBTRACT", k_h, g.math("MULTIPLY", pits, 0.6))
    height = g.mixf(g.math("SUBTRACT", 1.0, rot), height, k_h)
    s_top = g.math("ADD", g.math("MULTIPLY", zones, 0.45), g.math("MULTIPLY", grain, 0.5))
    s_bot = g.math("SUBTRACT", 0.5, g.math("MULTIPLY", pore, 0.9))
    height = g.mixf(shelf, height, g.mixf(under, s_top, s_bot))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.0015))


tk.reset_scene()
zk.stage()
zk.body()
fungus = fungus_material("Fungus")
pieces = []


def part(cluster, bone, piece, tris):
    obj = cluster.mesh(piece, fungus, tris)
    zk.on(obj, bone, piece)
    pieces.append(obj)
    return obj


BACK = (0.0, -1.0, 0.0)
B = 0.6

# ---- BackVar1: the big one, over the left shoulder blade toward the spine, where Joe's, the cop's and the nurse's
# backs all sit within about 2 cm of the stand-in once fitted (higher up the cop's back falls away, lower down it
# bulges). A diagonal crowd of knobs with a tier of three shelves down its outer side and two toward the spine.
c = Cluster(1, skin=0.014)
for x, z, r, lift, kids in ((0.088, 1.39, 0.026, 0.3, 4), (0.115, 1.415, 0.02, 0.2, 3), (0.06, 1.365, 0.021, 0.2, 3),
                            (0.1, 1.355, 0.016, 0.1, 2), (0.068, 1.42, 0.016, 0.1, 2), (0.132, 1.385, 0.014, 0.05, 1),
                            (0.04, 1.343, 0.014, 0.05, 1), (0.125, 1.442, 0.012, 0.0, 1), (0.047, 1.395, 0.012, 0.0, 1),
                            (0.08, 1.333, 0.011, 0.0, 0), (0.147, 1.41, 0.009, -0.05, 0), (0.095, 1.443, 0.01, 0.0, 0)):
    c.knob((x, B, z), r, lift + 0.004 / r, BACK, kids=kids)
c.tier((0.13, B, 1.34), (0.7, 1.0), [(0.11, 0.072, 0.028), (0.1, 0.066, 0.026), (0.085, 0.056, 0.022)], 0.031,
       toward=BACK)
c.tier((0.035, B, 1.335), (-0.5, 1.0), [(0.075, 0.05, 0.021), (0.06, 0.04, 0.017)], 0.026, toward=BACK)
part(c, "Spine2", "BackVar1", 2000)

# ---- BackVar2: smaller, on the right of the back a little lower
c = Cluster(2, skin=0.014)
for x, z, r, lift, kids in ((-0.085, 1.31, 0.022, 0.3, 3), (-0.06, 1.29, 0.016, 0.15, 2),
                            (-0.105, 1.335, 0.015, 0.1, 2), (-0.11, 1.29, 0.013, 0.05, 1),
                            (-0.068, 1.335, 0.012, 0.0, 1), (-0.047, 1.31, 0.01, 0.0, 0),
                            (-0.092, 1.272, 0.011, 0.0, 1), (-0.127, 1.315, 0.009, -0.05, 0)):
    c.knob((x, B, z), r, lift + 0.004 / r, BACK, kids=kids)
c.tier((-0.12, B, 1.27), (-0.75, 1.0), [(0.09, 0.06, 0.024), (0.075, 0.05, 0.02), (0.058, 0.04, 0.016)], 0.028,
       toward=BACK)
c.shelf((-0.05, B, 1.27), (-0.1, 1.0), 0.055, 0.036, 0.015, toward=BACK)
part(c, "Spine2", "BackVar2", 1250)

# ---- ShoulderVar: on top of the left deltoid (the real arm sits 1 to 2 cm outside the stand-in there on all three),
# knobs on top and tiers of shelves standing out to the side and back
ARM = ("Spine2", "LeftArm")
a0, a1, ar = CAPS["LeftArm"]
OUTUP = unit(np.cross(unit(a0 - a1), (0.0, 1.0, 0.0)))  # the outside-top of the upper arm


def deltoid(t, around=0.0):
    """A point well off the upper arm `t` of the way along its hit box from the shoulder end, turned `around`
    (radians) from the top toward the back, and the direction back to it."""
    p = a1 + (a0 - a1) * t
    d = OUTUP * math.cos(around) + np.array([0.0, 1.0, 0.0]) * math.sin(around)
    return p + d * 0.3, -d


c = Cluster(3, bones=ARM, skin=0.02, inner=-0.04, cut=-0.022)
c.scatter(*deltoid(0.27, 0.15), (0.028, 0.038), 7, 0.018, 0.009, kids=3)
for t, around, out, size in ((0.6, 0.05, (1.0, -0.1), (0.095, 0.065, 0.025)),
                             (0.5, 0.15, (1.0, 0.1), (0.085, 0.058, 0.023)),
                             (0.41, 0.25, (1.0, 0.3), (0.07, 0.048, 0.019)),
                             (0.47, 0.95, (0.45, 1.0), (0.065, 0.044, 0.018)),
                             (0.37, 1.0, (0.3, 1.0), (0.05, 0.034, 0.014))):
    s, d = deltoid(t, around)
    c.shelf(s, out, *size, toward=d, rise=0.1)
part(c, "LeftArm", "ShoulderVar", 1450)

# ---- FaceVar: bursting out of the left cheekbone, below the eye and in front of the ear (Joe's hair hides the sides
# and back of his head, the cop's cap the top): a few knobs and a little rosette of shelves under them
HEAD = ("Head",)
HEAD_AXIS = np.array([0.0, 0.035, 0.0])


def cheek(deg, z):
    """A point well off the head `deg` degrees round from the front toward its left, at height z, and the direction
    back to it."""
    d = np.array([math.sin(math.radians(deg)), -math.cos(math.radians(deg)), 0.0])
    return HEAD_AXIS + np.array([0.0, 0.0, z]) + d * 0.3, -d


c = Cluster(4, bones=HEAD, skin=0.008, inner=-0.04, cut=-0.025, h=0.0016)
c.scatter(*cheek(42, 1.672), (0.016, 0.014), 5, 0.012, 0.007, kids=2)
for deg, z, out, size in ((50, 1.646, (1.0, -0.7), (0.05, 0.034, 0.015)),
                          (56, 1.664, (1.0, -0.35), (0.042, 0.029, 0.013)),
                          (44, 1.655, (0.6, -1.0), (0.036, 0.025, 0.012))):
    s, d = cheek(deg, z)
    c.shelf(s, out, *size, toward=d)
part(c, "Head", "FaceVar", 850)

# The face must stay clear: nothing in front of the eyes or over the mouth
face = [p for p in pieces if p["zbone"] == "Head#FaceVar"][0]
V = mesh_verts(face)
eyes = np.sum((np.abs(V[:, 0]) < 0.06) & (V[:, 1] < -0.04) & (V[:, 2] > 1.695) & (V[:, 2] < 1.75))
mouth = np.sum((np.abs(V[:, 0]) < 0.035) & (V[:, 1] < -0.05) & (V[:, 2] < 1.66))
print("[fungus] vertices over the eyes: %d, over the mouth: %d" % (eyes, mouth))
for p in pieces:
    V = mesh_verts(p)
    print("[fungus] %s: %d tris, bounds %s .. %s" % (
        p["zbone"], sum(len(f.vertices) - 2 for f in p.data.polygons), np.round(V.min(0), 3), np.round(V.max(0), 3)))
parts = zk.export("Fungus", pieces, ASSETS)
zk.previews("fungus", PREVIEWS, Vector((0.05, 0.05, 1.45)), distance=1.3)
preview("fungus_close_back", (0.3, 0.75, 1.5), (0.03, 0.2, 1.36), lens=60)
preview("fungus_close_shoulder", (0.75, -0.35, 1.75), (0.28, 0.05, 1.55), lens=60)
preview("fungus_face", (0.35, -0.6, 1.72), (0.05, -0.03, 1.66), lens=60)
print("[fungus] done")
