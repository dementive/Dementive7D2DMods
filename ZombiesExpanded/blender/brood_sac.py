"""Brood sac: the Brood's mutation. A large, taut, veiny purple-red sac swelling out of the belly, its skin stretched
thin enough to show the dark shapes of the crawlers curled inside pressing against it (a skull, a splayed hand, a
curved spine), the belly skin bruised, bunched and split where it gives way to the sac. One solid part,
Spine1#Sac, which the game pulses.

    blender -b --factory-startup --python brood_sac.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "BroodSac"), args[1]
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


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def put_vec(obj, name, values):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.asarray(values, np.float32).ravel())


# The belly the sac roots in. Joe's real belly is at about y = -0.12 by z = 1.15, a little behind the stand-in's
# hip capsule, so the sac is rooted on a belly fitted to that (a torso of elliptic section, 0.32 wide by 0.24 deep)
# rather than on the stand-in: on bigger bellies its base just sinks deeper, it never floats.
BELLY_A, BELLY_B = 0.165, 0.12


def belly(P):
    q = np.stack([P[:, 0] / BELLY_A, P[:, 1] / BELLY_B], 1)
    k = np.linalg.norm(q, axis=1)
    side = (k - 1.0) * min(BELLY_A, BELLY_B)
    cap = np.maximum(np.maximum(0.98 - P[:, 2], P[:, 2] - 1.32), 0.0)
    return np.sqrt(np.maximum(side, 0.0) ** 2 + cap ** 2) + np.minimum(side, 0.0)


SKIN = -0.004   # belly skin level: just under the real belly, so only the swelling at the neck shows
NECK_C = np.array([0.008, -0.12, 1.14])   # where the sac breaks out of the belly
AXIS = unit(np.array([0.03, -1.0, -0.12]))  # the way it swells: out, and sagging a little
FRAME = frame_from(AXIS, up=(0.0, 0.0, 1.0))  # rows: sideways, up-ish, out


class Brood:
    """The sac: two blended ellipsoids (a sagging pear) swelling from the belly with a wide stretched neck, crawler
    shapes pushing out under its skin, and a bunched, ragged collar of belly skin around the neck."""

    def __init__(self):
        o = AXIS
        # Radii are (sideways, up, out)
        self.upper = (NECK_C + o * 0.055 + np.array([0.0, 0.0, 0.045]), (0.1, 0.09, 0.085))
        self.lower = (NECK_C + o * 0.06 + np.array([0.006, 0.0, -0.03]), (0.125, 0.105, 0.105))
        rng = np.random.default_rng(7)
        self.phase = rng.uniform(0, 2 * math.pi, 4)
        # Shapes inside, placed by direction from the sac's middle and how far they push out under the skin
        self.mid = NECK_C + o * 0.065
        self.parts = []

    def shell(self, P):
        up = sd_ellipsoid(P, self.upper[0], self.upper[1], FRAME)
        lo = sd_ellipsoid(P, self.lower[0], self.lower[1], FRAME)
        return smin(up, lo, 0.05)

    def surface_point(self, direction):
        d = unit(direction)
        p = self.mid.copy()
        for _ in range(100):
            e = self.shell(np.array([p]))[0]
            if abs(e) < 1e-5:
                break
            p = p - d * e
        return p

    def push(self, direction, r, depth):
        """A point under the sac's skin in `direction` from its middle, `depth` below the surface for a shape of
        radius r (so the shape bulges the skin out by r - depth), and the outward normal there."""
        p = self.surface_point(FRAME.T @ np.asarray(direction, float))
        n = unit(p - self.mid)
        return p - n * (r - depth), n

    def add_inner(self):
        """The crawlers curled inside, bulging the skin a few millimeters: a skull high on the right and a smaller
        one low on the left front, a splayed hand pressed flat on the left, a spine curving down the right side,
        a knee up top."""
        out = []
        c, n = self.push((-0.42, 0.42, 0.8), 0.04, 0.011)
        out.append(("sphere", c, 0.04))
        c, n = self.push((0.28, -0.62, 0.74), 0.032, 0.008)
        out.append(("sphere", c, 0.032))
        # The hand: palm and four fingers splayed up and out over the curve of the sac, a thumb tucked down
        c, n = self.push((0.62, -0.1, 0.78), 0.012, 0.007)
        f = frame_from(n, up=(-0.3, 0.0, 1.0))
        out.append(("ellipsoid", c, (0.024, 0.028, 0.012), f))
        for i, ang in enumerate((-0.55, -0.2, 0.15, 0.5)):
            dirn = f[0] * math.sin(ang) + f[1] * math.cos(ang)
            L = 0.034 + 0.007 * (i in (1, 2))
            a0 = c + dirn * 0.022 + n * 0.006
            a1 = a0 + dirn * L - n * 0.006
            out.append(("capsule", a0, a1, 0.007))
        t0 = c - f[1] * 0.014 + f[0] * 0.014 + n * 0.005
        out.append(("capsule", t0, t0 + unit(f[0] - f[1] * 0.6) * 0.026 - n * 0.004, 0.0072))
        # A spine: knobs along a curve down the right side
        for i in range(7):
            t = i / 6.0
            c, n = self.push((-0.78 + 0.12 * t, 0.15 - 0.8 * t, 0.6 - 0.1 * math.sin(math.pi * t)), 0.0105, 0.0062)
            out.append(("sphere", c, 0.0105 - 0.0025 * abs(t - 0.4)))
        c, n = self.push((0.12, 0.62, 0.78), 0.022, 0.006)
        out.append(("ellipsoid", c, (0.03, 0.022, 0.022), frame_from(n, up=(1.0, 0.0, 0.3))))
        self.parts = out

    def inner(self, P):
        d = None
        for part in self.parts:
            if part[0] == "sphere":
                e = sd_sphere(P, part[1], part[2])
            elif part[0] == "ellipsoid":
                e = sd_ellipsoid(P, part[1], part[2], part[3])
            else:
                e = sd_capsule(P, part[1], part[2], part[3])
            d = e if d is None else smin(d, e, 0.006)
        return d

    def rho(self, P):
        q = P - NECK_C
        along = q @ AXIS
        return np.linalg.norm(q - along[:, None] * AXIS, axis=1), along, q

    def collar(self, P):
        """The belly skin bunched up around the neck, ragged where it split."""
        rho, along, q = self.rho(P)
        a = np.arctan2(q @ FRAME[1], q @ FRAME[0])
        p = self.phase
        jag = np.clip(0.55 + 0.3 * np.sin(4 * a + p[0]) + 0.2 * np.sin(9 * a + p[1]) + 0.05 * np.sin(17 * a + p[2]),
                      0.15, 1.0)
        return 0.011 * jag * np.exp(-((rho - 0.127) / 0.012) ** 2)

    def offset(self, P):
        rho, along, q = self.rho(P)
        b = np.maximum(rho - 0.118, 0.0)
        off = SKIN + 0.012 * np.exp(-(b / 0.02) ** 2) - 3.0 * np.maximum(b - 0.01, 0.0)
        off = np.maximum(off, -0.08)
        return off + self.collar(P) + waves(P, 0.03, 9, 2) * 0.0015

    def skin(self, P):
        return belly(P) - self.offset(P)

    def sac(self, P):
        d = self.shell(P) + waves(P, 0.07, 3, 2) * 0.004
        d = smin(d, self.inner(P), 0.022)
        return d

    def field(self, P):
        return smin(self.skin(P), self.sac(P), 0.03)

    def mesh(self, name, material, tris):
        lo = NECK_C + np.array([-0.19, -0.27, -0.21])
        hi = NECK_C + np.array([0.19, 0.14, 0.21])
        region = lambda P: self.rho(P)[0] - 0.16  # noqa: E731
        keep = lambda P: np.maximum(smooth01(0.0, 0.006, -self.inner(P) + 0.004),  # noqa: E731
                                    smooth01(0.002, 0.008, self.collar(P)))
        obj = field_mesh(name, self.field, lo, hi, 0.0032, material, tris, inner=-0.06, cut=-0.03, region=region,
                         ground=belly, keep=keep)
        P = mesh_verts(obj)
        rho, along, q = self.rho(P)
        lift = self.skin(P)
        put(obj, "sac", smooth01(0.0, 0.03, lift))
        put(obj, "neck", np.exp(-((rho - 0.125) / 0.025) ** 2) * smooth01(0.03, -0.01, lift))
        put(obj, "collar", smooth01(0.002, 0.008, self.collar(P)))
        depth = self.inner(P)
        put(obj, "inner", smooth01(0.06, 0.0, depth))
        a = np.arctan2(q @ FRAME[1], q @ FRAME[0])
        put_vec(obj, "polar", np.stack([np.cos(a), np.sin(a), along * 12.0], 1))
        put(obj, "taut", smooth01(0.05, 0.13, along))
        put(obj, "edge", smooth01(0.12, 0.15, rho) * smooth01(0.02, 0.0, lift))
        return obj


def brood_material(name):
    """Belly skin bruised toward the neck and split there, raw red in the tears; the sac's skin a wet, mottled
    purple-red, paler and pinker where it's stretched thinnest, laced with fat dark veins and fine red capillaries,
    stretch marks running out from the neck, and the crawlers inside showing through as dark, soft-edged shapes."""
    mat, g = tk.new_material(name)
    sac = attr(g, "sac")
    neck = attr(g, "neck")
    collar = attr(g, "collar")
    inner = attr(g, "inner")
    taut = attr(g, "taut")
    edge = attr(g, "edge")
    polar = vec_attr(g, "polar")

    mott = g.noise(14.0, detail=6.0, roughness=0.62)
    skin = g.mix(g.ramp(mott, 0.3, 0.72), (0.3, 0.27, 0.22), (0.2, 0.18, 0.15))
    bruise = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(edge, 0.2, 0.9)),
                    g.ramp(g.noise(8.0, detail=5.0), 0.2, 0.55))
    skin = g.mix(g.math("MULTIPLY", bruise, 0.8), skin, (0.17, 0.055, 0.075))
    skin = g.mix(g.math("MULTIPLY", g.ramp(neck, 0.3, 0.9), 0.85), skin, (0.08, 0.018, 0.03))

    blot = g.noise(6.0, detail=6.0, roughness=0.6, distortion=0.4)
    flesh = g.mix(g.ramp(blot, 0.3, 0.72), (0.22, 0.045, 0.08), (0.12, 0.025, 0.055))
    flesh = g.mix(g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=3.0), 0.45, 0.75), taut), flesh, (0.36, 0.12, 0.15))
    flesh = g.mix(g.math("MULTIPLY", g.ramp(g.noise(20.0, detail=4.0), 0.6, 0.75), 0.45), flesh, (0.3, 0.2, 0.1))
    # The crawlers showing through as dark, blurred shapes
    shade = g.math("MULTIPLY", inner, g.ramp(g.noise(14.0, detail=3.0), 0.0, 0.7))
    flesh = g.mix(g.math("MULTIPLY", shade, 0.95), flesh, (0.025, 0.007, 0.015))
    big = veins(g, 5.0, 0.045, warp_amount=0.8, broken=0.3, detail=0.8)
    mid = veins(g, 13.0, 0.035, warp_amount=0.9, broken=0.6, detail=1.2)
    cap = veins(g, 45.0, 0.035, warp_amount=1.0, broken=0.8)
    flesh = g.mix(g.math("MULTIPLY", cap, 0.15), flesh, (0.3, 0.03, 0.04))
    flesh = g.mix(g.math("MULTIPLY", mid, 0.7), flesh, (0.07, 0.025, 0.08))
    flesh = g.mix(g.math("MULTIPLY", big, 0.9), flesh, (0.035, 0.018, 0.07))
    # Stretch marks: thin pale streaks running out from the neck along the sac
    m = g.node("ShaderNodeMapping")
    g.links.new(polar, m.inputs["Vector"])
    m.inputs["Scale"].default_value = (14.0, 14.0, 0.25)
    striae = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=2.0, vector=m.outputs[0]), 0.62, 0.68),
                    g.math("SUBTRACT", 1.0, g.ramp(taut, 0.1, 0.7)))
    striae = g.math("MULTIPLY", striae, g.ramp(sac, 0.3, 0.8))
    flesh = g.mix(g.math("MULTIPLY", striae, 0.55), flesh, (0.42, 0.2, 0.22))
    col = g.mix(g.ramp(sac, 0.2, 0.8), skin, flesh)
    col = g.mix(g.math("MULTIPLY", g.ramp(neck, 0.35, 0.95), 0.75), col, (0.07, 0.012, 0.025))
    # Splits in the collar of belly skin, raw and wet
    tear = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=5.0, distortion=0.8), 0.58, 0.66), collar)
    col = g.mix(g.math("MULTIPLY", collar, 0.5), col, (0.22, 0.15, 0.12))
    col = g.mix(tear, col, (0.28, 0.022, 0.022))
    cav = g.cavity(0.02)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.8), col, (0.03, 0.006, 0.012))

    sheen = g.math("ADD", 0.2, g.math("MULTIPLY", g.noise(10.0, detail=3.0), 0.16))
    rough = g.mixf(g.ramp(sac, 0.2, 0.8), 0.6, sheen)
    rough = g.mixf(tear, rough, 0.15)
    rough = g.mixf(g.math("MULTIPLY", striae, 0.6), rough, 0.42)
    height = g.math("MULTIPLY", g.noise(160.0, detail=4.0), 0.2)
    height = g.math("ADD", height, g.math("MULTIPLY", big, 1.1))
    height = g.math("ADD", height, g.math("MULTIPLY", mid, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", cap, 0.1))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", striae, 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", tear, 0.6))
    # A dark, ragged rim of grime and dried blood where the patch meets the zombie's clothes or skin, so it reads
    # as torn through them on any zombie rather than laid on top
    rim = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", g.noise(18.0, detail=5.0, distortion=0.4), 0.5)), 0.6, 0.95)
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, (0.03, 0.02, 0.015))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.65, value=0.62)
    rough = g.math("ADD", rough, 0.12)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.35, 0.002))


tk.reset_scene()
zk.stage()
zk.body()
material = brood_material("Brood")
brood = Brood()
brood.add_inner()
sac = brood.mesh("BroodSac", material, 4800)
# Shrunk by a fifth (about 22 cm across, 14 cm out from the belly) toward a point just inside where it breaks out
ANCHOR = NECK_C - AXIS * 0.02
V = ANCHOR + (mesh_verts(sac) - ANCHOR) * 0.8
sac.data.vertices.foreach_set("co", V.ravel())
sac.data.update()
zk.on(sac, "Spine1", "Sac")
V = mesh_verts(sac)
print("[brood_sac] Spine1#Sac: %d tris, bounds %s .. %s" % (sum(len(f.vertices) - 2 for f in sac.data.polygons),
                                                         np.round(V.min(0), 3), np.round(V.max(0), 3)))
parts = zk.export("BroodSac", [sac], ASSETS)
zk.previews("brood_sac", PREVIEWS, Vector((0.0, -0.12, 1.15)), distance=1.3)
preview("brood_sac_close", (0.3, -0.75, 1.3), (0.0, -0.16, 1.14), lens=55)
preview("brood_sac_profile", (0.9, -0.2, 1.2), (0.0, -0.17, 1.13), lens=55)
print("[brood_sac] done")
