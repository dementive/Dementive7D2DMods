"""Fungus: the Regenerator's mutation. Pale cream and tan shelf fungus and knobby fungal masses (cordyceps-infected
flesh) bursting out of rotting skin on the left side of the head, the left shoulder and across the upper back, with a few
club-headed stalks and fine white mycelium strands creeping out over the skin. The face stays clear. Three parts:
Head#Fungus, Spine2#Fungus, LeftArm#Fungus.

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


SKIN = 0.012    # the skin's level above the stand-in (which is a little slimmer than the real zombie)
SLOPE = 0.45    # the infected skin slopes down at about 24 degrees, so it meets any skin at an angle,
DIVE = -0.012   # and below this level dives steeply,
DEEP = -0.08    # down to here, so its edges vanish under any zombie's skin
EDGE = (SKIN - DIVE) / SLOPE
UP = np.array([0.0, 0.0, 1.0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class Lump:
    """A knobby fungal mass breaking out of the body point nearest `start`: a squat bulb crowded with rounded knobs,
    like cauliflower or a cluster of puffballs gone wrong."""

    def __init__(self, start, r, seed, rise=0.0, knobs=10, bones=TORSO, squash=0.7, toward=None):
        base, n = on_body(start, bones, toward=toward)
        self.base, self.n, self.r, self.seed = base, n, r, seed
        rng = np.random.default_rng(seed)
        self.frame = frame_from(n, up=(rng.uniform(-1, 1), rng.uniform(-1, 1), 1.0))
        self.c = base + n * (SKIN + r * rise)
        self.radii = (r * rng.uniform(0.95, 1.2), r * rng.uniform(0.85, 1.05), r * squash)
        self.knobs = []
        for _ in range(knobs):
            d = unit(self.frame.T @ np.array([rng.normal(), rng.normal(), abs(rng.normal()) + 0.25]))
            q = self.c + d * np.array(self.radii) * 0.95
            self.knobs.append((q, r * rng.uniform(0.32, 0.55)))

    def sdf(self, P):
        r = self.r
        d = sd_ellipsoid(P, self.c, np.array(self.radii) * 0.85, self.frame)
        for q, kr in self.knobs:
            d = smin(d, sd_sphere(P, q, kr), r * 0.1)
        return d + waves(P, r * 0.8, self.seed, 2) * r * 0.05


class Patch:
    """Rotting skin around fungal lumps: raised to SKIN over their footprint, sloping away under the body."""

    def __init__(self, lumps, seed, bones=TORSO, spread=1.6):
        self.lumps, self.seed, self.bones, self.spread = lumps, seed, bones, spread
        self.bases = np.array([l.base for l in lumps])
        self.rs = np.array([l.r for l in lumps])
        self.shelves = []

    def beyond(self, P):
        d = np.min(np.linalg.norm(P[:, None, :] - self.bases[None], axis=2) - self.rs[None] * self.spread, axis=1)
        return np.maximum(d + waves(P, 0.05, self.seed + 7, 2) * 0.008, 0.0)

    def offset(self, P):
        b = self.beyond(P)
        s = np.sqrt(b * b + 0.008 ** 2) - 0.008
        off = SKIN - SLOPE * s - 1.6 * np.maximum(s - EDGE, 0.0)
        off = np.maximum(off, DEEP)
        inside = 1.0 - smooth01(0.0, 0.025, b)
        return off + inside * waves(P, 0.025, self.seed + 3, 2) * 0.0025

    def skin(self, P):
        return body(P, self.bones) - self.offset(P)

    def field(self, P):
        d = self.skin(P)
        for l in self.lumps:
            d = smin(d, l.sdf(P), l.r * 0.35)
        return d

    def surface(self, start, inset=0.0):
        """The point on the grown surface nearest `start` (sunk by `inset`) and the outward normal there."""
        p = settle(self.field, np.array([start], float), 10)
        n = normals(self.field, p)[0]
        return p[0] - n * inset, n

    def box(self):
        reach = (self.rs * (self.spread + 1.5) + EDGE + 0.06)[:, None]
        return (self.bases - reach).min(0), (self.bases + reach).max(0)

    def mesh(self, name, material, tris, h=0.0025, inner=-0.05, cut=-0.025):
        lo, hi = self.box()
        keep = lambda P: smooth01(0.002, 0.01, self.skin(P))  # noqa: E731
        region = lambda P: self.beyond(P) - (EDGE + 0.02)  # noqa: E731
        obj = field_mesh(name, self.field, lo, hi, h, material, tris, bones=self.bones, keep=keep, region=region,
                         inner=inner, cut=cut)
        P = mesh_verts(obj)
        lift = self.skin(P)
        near = np.zeros(len(P))
        for l in self.lumps:
            d = np.linalg.norm(P - l.base, axis=1)
            near = np.maximum(near, np.exp(-(np.maximum(d - l.r * 1.2, 0.0) / (l.r * 0.9 + 0.006)) ** 2))
        put(obj, "fung", smooth01(0.001, 0.008, lift))
        put(obj, "near", near)
        put(obj, "edge", np.clip(self.beyond(P) / EDGE, 0.0, 1.0))
        return obj


def shelf(name, A, out, W, D, T, seed, material, segs=8, droop=0.2, span=1.35):
    """A bracket fungus growing out sideways from A: a fan-shaped, lobed shelf, thick and domed at the base with
    low ridges, flat underneath, thinning to a rounded margin; `out` is the way it sticks out (kept level), W its
    width, D how far it sticks out, T its thickness at the base."""
    rng = np.random.default_rng(seed)
    out = unit(np.array([out[0], out[1], 0.0]))
    side = np.cross(UP, out)
    ph = rng.uniform(0, 2 * math.pi, 3)
    rhos = [0.3, 0.55, 0.76, 0.92]
    thetas = [-span + 2 * span * j / segs for j in range(segs + 1)]
    bm = bmesh.new()
    rho_v, under_v = [], []

    def spot(rho, th, h_top):
        m = 1 + 0.14 * math.sin(3 * th + ph[0]) + 0.06 * math.sin(7 * th + ph[1])
        flat = (side * math.sin(th) * W * 0.5 + out * math.cos(th) * D) * rho * m
        return A + flat + UP * (h_top - droop * T * rho * rho)

    def top_h(rho):
        return T * (0.16 + 0.84 * (1 - rho * rho) ** 0.6) * (1 + 0.07 * math.sin(rho * 28 + ph[2]) * rho)

    def bot_h(rho):
        return -T * 0.25 * (1 - rho * rho) ** 0.7

    top_c = bm.verts.new(A + UP * T)
    bot_c = bm.verts.new(A - UP * T * 0.25)
    rho_v += [0.0, 0.0]
    under_v += [0.0, 1.0]
    top, bot = [], []
    for rho in rhos:
        top.append([bm.verts.new(spot(rho, th, top_h(rho))) for th in thetas])
        bot.append([bm.verts.new(spot(rho, th, bot_h(rho))) for th in thetas])
        rho_v += [rho] * len(thetas)
        under_v += [0.0] * len(thetas)
        rho_v += [rho] * len(thetas)
        under_v += [1.0] * len(thetas)
    rim = [bm.verts.new(spot(1.0, th, T * 0.05)) for th in thetas]
    rho_v += [1.0] * len(thetas)
    under_v += [0.5] * len(thetas)
    n = len(thetas)
    for j in range(n - 1):
        bm.faces.new((top_c, top[0][j], top[0][j + 1]))
        bm.faces.new((bot_c, bot[0][j + 1], bot[0][j]))
        for i in range(len(rhos) - 1):
            bm.faces.new((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]))
            bm.faces.new((bot[i][j], bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j]))
        bm.faces.new((top[-1][j], rim[j], rim[j + 1], top[-1][j + 1]))
        bm.faces.new((bot[-1][j], bot[-1][j + 1], rim[j + 1], rim[j]))
    for j in (0, n - 1):
        ring = [top_c] + [top[i][j] for i in range(len(rhos))] + [rim[j]]
        ring += [bot[i][j] for i in range(len(rhos) - 1, -1, -1)] + [bot_c]
        try:
            bm.faces.new(ring if j == 0 else list(reversed(ring)))
        except ValueError:
            pass
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, material)
    put(obj, "rho", rho_v)
    put(obj, "under", under_v)
    return tk.smooth(obj, 70.0)


def stalk(name, base, direction, length, radius, seed, material, segs=5):
    """A cordyceps fruiting stalk: thin, a little crooked, swelling into a club at the tip."""
    rng = np.random.default_rng(seed)
    d = unit(direction)
    wob = np.cross(d, unit(rng.normal(size=3))) * length * 0.15
    f = frame_from(d)
    us = [-0.3, 0.0, 0.3, 0.6, 0.75, 0.88, 0.97]
    bm = bmesh.new()
    rings, t_v = [], []
    for u in us:
        p = base + d * length * u + wob * math.sin(math.pi * max(u, 0.0)) * u
        r = radius * (1.0 - 0.3 * u if u < 0.65 else 1.6 - 0.5 * (u - 0.65) / 0.32)
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            ring.append(bm.verts.new(p + (f[0] * math.cos(a) + f[1] * math.sin(a)) * r))
            t_v.append(0.03 + 0.97 * max(u, 0.0))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    tip = bm.verts.new(base + d * length * 1.02 + wob * 0.05)
    t_v.append(1.0)
    for k in range(segs):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % segs], tip))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, material)
    put(obj, "t", t_v)
    return tk.smooth(obj, 80.0)


def strands(name, patch, count, seed, material, length=(0.025, 0.045), radius=0.0007):
    """Fine mycelium threads creeping out from the fungal masses over the skin, here and there lifting off it."""
    rng = np.random.default_rng(seed)
    bm = bmesh.new()
    skin = patch.skin
    for c in range(count):
        l = patch.lumps[rng.integers(len(patch.lumps))]
        a = rng.uniform(0, 2 * math.pi)
        t1, t2 = l.frame[0], l.frame[1]
        heading = t1 * math.cos(a) + t2 * math.sin(a)
        p = l.base + heading * l.r * 1.0
        pts = []
        L = rng.uniform(*length)
        steps = 7
        for i in range(steps + 1):
            q = settle(skin, np.array([p]), 6)[0]
            nrm = normals(skin, np.array([q]))[0]
            lift = 0.0009 + 0.0012 * math.sin(math.pi * i / steps) * rng.uniform(0.0, 1.0)
            pts.append(q + nrm * lift)
            heading = unit(heading + np.cross(nrm, heading) * rng.uniform(-0.6, 0.6))
            heading = unit(heading - nrm * (heading @ nrm))
            p = q + heading * L / steps
        rings = []
        for i, q in enumerate(pts):
            tan = unit(pts[min(i + 1, steps)] - pts[max(i - 1, 0)])
            f = frame_from(tan)
            r = radius * (1.0 - 0.6 * i / steps)
            rings.append([bm.verts.new(q + (f[0] * math.cos(k * 2.094) + f[1] * math.sin(k * 2.094)) * r)
                          for k in range(3)])
        for i in range(steps):
            for k in range(3):
                bm.faces.new((rings[i][k], rings[i][(k + 1) % 3], rings[i + 1][(k + 1) % 3], rings[i + 1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, material)
    return tk.smooth(obj, 80.0)


# ---------------------------------------------------------------- materials

def rot_material(name):
    """Skin going necrotic toward the fungus: bruised, then wet brown-black rot, furred with white mycelium around
    the growths; the fungal masses pale cream and tan, knobbly like cauliflower, with ochre blotches and dark
    crevices between the knobs."""
    mat, g = tk.new_material(name)
    fung = attr(g, "fung")
    near = attr(g, "near")
    edge = attr(g, "edge")
    mott = g.noise(14.0, detail=6.0, roughness=0.62)
    skin = g.mix(g.ramp(mott, 0.3, 0.72), (0.3, 0.27, 0.22), (0.2, 0.18, 0.15))
    inside = g.math("SUBTRACT", 1.0, g.ramp(edge, 0.1, 0.8))
    bz = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(near, 0.05, 0.5), g.math("MULTIPLY", inside, 0.25)),
                g.ramp(g.noise(9.0, detail=5.0), 0.25, 0.6))
    skin = g.mix(bz, skin, (0.15, 0.1, 0.085))
    # Rotten through the whole patch (not just beside the growths): pale dead skin there read as a flat tan slab on
    # the zombie's clothes in game
    rot = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(near, 0.35, 0.85), g.math("MULTIPLY", inside, 0.85)),
                 g.ramp(g.noise(16.0, detail=6.0), 0.15, 0.45))
    skin = g.mix(rot, skin, (0.055, 0.035, 0.022))
    # Mycelium: a white fur of fine fibres right around the growths, a few threads reaching further
    fuzz = g.ramp(g.noise(90.0, detail=8.0, roughness=0.8), 0.5, 0.7)
    furred = g.math("MULTIPLY", fuzz, g.ramp(near, 0.65, 0.97))
    threads = veins(g, 55.0, 0.025, warp_amount=2.0, broken=0.85)
    reach = g.math("MULTIPLY", threads, g.ramp(near, 0.55, 0.9))
    myc = g.math("MAXIMUM", furred, g.math("MULTIPLY", reach, 0.6))
    skin = g.mix(g.math("MULTIPLY", myc, 0.75), skin, (0.66, 0.63, 0.54))

    # Fungal flesh: bulbous knobs (smooth Voronoi cells) at two sizes, darker in the crevices between them
    def knobs(scale):
        v = g.node("ShaderNodeTexVoronoi", feature="SMOOTH_F1")
        g._in(v, "Scale", scale)
        g._in(v, "Smoothness", 0.4)
        g.links.new(warp(g, g.coords(), scale * 0.3, 0.4 / scale), v.inputs["Vector"])
        return g.math("SUBTRACT", 1.0, g.math("POWER", tk._sock(v.outputs, "Distance"), 1.5), clamp=True)

    big_k = knobs(70.0)
    small_k = knobs(190.0)
    lumps = g.math("ADD", g.math("MULTIPLY", big_k, 0.7), g.math("MULTIPLY", small_k, 0.3))
    fungus = g.mix(g.ramp(g.noise(7.0, detail=4.0), 0.3, 0.7), (0.56, 0.5, 0.37), (0.38, 0.29, 0.17))
    fungus = g.mix(g.math("MULTIPLY", g.ramp(g.noise(11.0, detail=5.0, distortion=0.5), 0.58, 0.72), 0.7), fungus,
                   (0.48, 0.32, 0.12))
    fungus = g.mix(g.math("MULTIPLY", g.ramp(lumps, 0.55, 0.25), 0.85), fungus, (0.2, 0.14, 0.08))
    base = g.math("SUBTRACT", 1.0, g.ramp(fung, 0.2, 0.9))
    fungus = g.mix(g.math("MULTIPLY", base, 0.6), fungus, (0.18, 0.11, 0.07))
    col = g.mix(g.ramp(fung, 0.15, 0.7), skin, fungus)
    cav = g.cavity(0.02)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.8), col, (0.06, 0.04, 0.025))

    rough = g.mixf(rot, 0.6, 0.3)
    rough = g.mixf(myc, rough, 0.85)
    rough = g.mixf(g.ramp(fung, 0.15, 0.7), rough, g.math("ADD", 0.48, g.math("MULTIPLY", lumps, 0.2)))
    height = g.math("MULTIPLY", g.noise(170.0, detail=4.0), 0.2)
    height = g.math("ADD", height, g.math("MULTIPLY", myc, 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", g.ramp(fung, 0.1, 0.6), g.math("MULTIPLY", lumps, 1.6)))
    # A dark, ragged rim of grime and dried blood where the patch meets the zombie's clothes or skin, so it reads
    # as torn through them on any zombie rather than laid on top
    rim = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", g.noise(18.0, detail=5.0, distortion=0.4), 0.5)), 0.6, 0.95)
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, (0.03, 0.02, 0.015))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.85, value=0.62)
    # Matte: wet-looking rot turned into a glossy grey sheet in the game's shader, hiding all its detail
    rough = g.math("ADD", g.math("MULTIPLY", rough, 0.5), 0.4)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.002))


def bracket_material(name):
    """Shelf fungus: concentric tan, brown and cream growth zones on top with a pale fresh margin, velvety; a cream
    underside packed with pores."""
    mat, g = tk.new_material(name)
    rho = attr(g, "rho")
    under = attr(g, "under")
    wob = g.math("ADD", rho, g.math("MULTIPLY", g.noise(12.0, detail=3.0), 0.06))
    zones = g.math("SINE", g.math("MULTIPLY", wob, 34.0))
    grain = g.noise(45.0, detail=6.0, roughness=0.7)
    top = g.mix(g.ramp(zones, -0.9, 0.9), (0.15, 0.095, 0.045), (0.3, 0.22, 0.12))
    top = g.mix(g.math("MULTIPLY", g.ramp(g.math("SINE", g.math("MULTIPLY", wob, 9.0)), 0.4, 0.95), 0.6), top,
                (0.09, 0.055, 0.025))
    top = g.mix(g.ramp(g.noise(8.0, detail=4.0), 0.5, 0.72), top, (0.32, 0.22, 0.1))
    top = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.35, 0.65), 0.35), top, (0.1, 0.065, 0.035))
    top = g.mix(g.ramp(rho, 0.8, 0.98), top, (0.56, 0.5, 0.37))
    top = g.mix(g.ramp(rho, 0.45, 0.05), top, (0.08, 0.05, 0.025))
    vor = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(vor, "Scale", 260.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    pores = g.ramp(tk._sock(vor.outputs, "Distance"), 0.28, 0.12)
    bottom = g.mix(g.ramp(g.noise(9.0, detail=3.0), 0.3, 0.7), (0.6, 0.54, 0.38), (0.46, 0.38, 0.23))
    bottom = g.mix(g.math("MULTIPLY", pores, 0.7), bottom, (0.36, 0.28, 0.16))
    col = g.mix(under, top, bottom)
    cav = g.cavity(0.015)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.7), col, (0.08, 0.05, 0.03))
    rough = g.mixf(under, 0.78, 0.68)
    height = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, under),
                    g.math("ADD", g.math("MULTIPLY", zones, 0.35), g.math("MULTIPLY", grain, 0.4)))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(140.0, detail=5.0), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MULTIPLY", pores, under), 0.6))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.85, value=0.6)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.0015))


def thread_material(name):
    """Cordyceps stalks (orange-tan, darkening to a knobbly brown club) and white mycelium strands, told apart by
    the stalks' `t` attribute (strands have none, so read 0)."""
    mat, g = tk.new_material(name)
    t = attr(g, "t")
    is_stalk = g.ramp(t, 0.0, 0.02)
    strand = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.76, 0.73, 0.64), (0.6, 0.56, 0.46))
    stem = g.mix(g.ramp(t, 0.55, 0.8), (0.55, 0.32, 0.12), (0.22, 0.11, 0.05))
    stem = g.mix(g.math("MULTIPLY", g.ramp(g.noise(120.0, detail=3.0), 0.55, 0.7), g.ramp(t, 0.6, 0.8)), stem,
                 (0.4, 0.25, 0.1))
    col = g.mix(is_stalk, strand, stem)
    rough = g.mixf(is_stalk, 0.7, 0.55)
    height = g.math("MULTIPLY", g.noise(150.0, detail=3.0), g.ramp(t, 0.6, 0.8))
    # Toned down to sit with the game's dark, dirty zombies (bright growths read as stuck-on shapes in game)
    col = tk.grade(g, col, sat=0.9, value=0.7)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.001))


tk.reset_scene()
zk.stage()
zk.body()
rot = rot_material("Rot")
bracket = bracket_material("Bracket")
thread = thread_material("Mycelium")
pieces = []


def part(objs, bone):
    for o in objs:
        zk.on(o, bone, "Fungus")
    pieces.extend(objs)


def shelf_on(patch, name, start, out, W, D, T, seed, inset=0.012, **kw):
    A, n = patch.surface(start, inset)
    return shelf(name, A, out, W, D, T, seed, bracket, **kw)


def stalk_on(patch, name, start, length, radius, seed, lean=(0.0, 0.0, 0.0)):
    A, n = patch.surface(start, 0.006)
    return stalk(name, A, unit(n + np.asarray(lean, float)), length, radius, seed, thread)


# ---- head: the left temple, side and back of the skull, clear of the face
HEAD = ("Head",)
head_lumps = [
    Lump((0.2, 0.06, 1.72), 0.03, 11, rise=-0.1, knobs=7, bones=HEAD),
    Lump((0.2, 0.025, 1.78), 0.022, 12, rise=-0.2, knobs=8, bones=HEAD),
    Lump((0.15, 0.17, 1.68), 0.026, 13, rise=-0.15, knobs=6, bones=HEAD),
    Lump((0.12, 0.08, 1.85), 0.02, 14, rise=-0.25, knobs=5, bones=HEAD),
    Lump((0.2, 0.08, 1.62), 0.017, 15, rise=-0.2, knobs=4, bones=HEAD),
]
head_patch = Patch(head_lumps, 21, bones=HEAD, spread=1.3)
head_mass = head_patch.mesh("HeadRot", rot, 850, inner=-0.04, cut=-0.02)
head_parts = [head_mass,
              shelf_on(head_patch, "HeadShelf0", (0.2, 0.09, 1.685), (1.0, 0.25), 0.085, 0.055, 0.015, 31),
              shelf_on(head_patch, "HeadShelf1", (0.2, 0.1, 1.715), (1.0, 0.45), 0.065, 0.042, 0.012, 37),
              shelf_on(head_patch, "HeadShelf2", (0.2, 0.04, 1.765), (1.0, -0.15), 0.06, 0.04, 0.012, 32),
              shelf_on(head_patch, "HeadShelf3", (0.12, 0.2, 1.64), (0.5, 1.0), 0.07, 0.045, 0.013, 33),
              stalk_on(head_patch, "HeadStalk0", (0.12, 0.08, 1.9), 0.035, 0.0022, 34, lean=(0.2, 0.0, 0.3)),
              stalk_on(head_patch, "HeadStalk1", (0.15, 0.04, 1.86), 0.026, 0.0019, 35, lean=(0.4, -0.2, 0.2)),
              strands("HeadStrands", head_patch, 4, 36, thread, length=(0.03, 0.05))]
# The head's hit box is wider than the real skull (radius 0.10 against about 0.075 at the temples), so a patch
# rooted on it floated in the hair: move each head piece 2 cm in toward the head's axis
for o in head_parts:
    V = mesh_verts(o)
    c = V.mean(0)
    d = np.array([c[0], c[1] - 0.035, 0.0])
    V -= unit(d) * 0.02
    o.data.vertices.foreach_set("co", V.ravel())
    o.data.update()
part(head_parts, "Head")

# ---- upper back: a band of masses from the left shoulder blade across the spine, continuing the infection down the
# left side. Not the front of the chest: that differs too much between zombies (Joe's chest is well inside its hit
# box, a nurse's or fat cop's pushes past it), so a patch there floated off one and sank into the others; the back
# matches the hit box on all of them
B = 0.6
BACK = (0.0, -1.0, 0.0)
chest_lumps = [
    Lump((0.11, B, 1.43), 0.032, 41, rise=-0.1, knobs=7, toward=BACK),
    Lump((0.06, B, 1.38), 0.026, 42, rise=-0.15, knobs=6, toward=BACK),
    Lump((0.0, B, 1.34), 0.024, 43, rise=-0.15, knobs=6, toward=BACK),
    Lump((-0.055, B, 1.3), 0.02, 44, rise=-0.2, knobs=5, toward=BACK),
    Lump((0.135, B, 1.36), 0.016, 45, rise=-0.2, knobs=4, toward=BACK),
    Lump((-0.095, B, 1.27), 0.013, 46, rise=-0.25, knobs=4, toward=BACK),
]
chest_patch = Patch(chest_lumps, 51, spread=1.4)
chest_mass = chest_patch.mesh("ChestRot", rot, 1000)
chest_parts = [chest_mass,
               shelf_on(chest_patch, "ChestShelf0", (0.1, B, 1.4), (0.3, 1.0), 0.09, 0.055, 0.016, 61),
               shelf_on(chest_patch, "ChestShelf1", (0.09, B, 1.44), (0.4, 1.0), 0.065, 0.04, 0.012, 66),
               shelf_on(chest_patch, "ChestShelf2", (0.02, B, 1.32), (-0.1, 1.0), 0.07, 0.044, 0.013, 62),
               shelf_on(chest_patch, "ChestShelf3", (-0.06, B, 1.28), (-0.3, 1.0), 0.05, 0.034, 0.01, 63),
               strands("ChestStrands", chest_patch, 5, 65, thread)]
part(chest_parts, "Spine2")

# ---- left shoulder: masses on the deltoid with shelves standing out sideways
ARM = ("Spine2", "LeftArm")
arm_lumps = [
    Lump((0.3, 0.05, 1.55), 0.03, 71, rise=-0.1, knobs=7, bones=ARM),
    Lump((0.33, 0.12, 1.46), 0.022, 72, rise=-0.15, knobs=5, bones=ARM),
    Lump((0.25, -0.05, 1.53), 0.018, 73, rise=-0.2, knobs=4, bones=ARM),
]
arm_patch = Patch(arm_lumps, 81, bones=ARM, spread=1.4)
arm_mass = arm_patch.mesh("ArmRot", rot, 600, inner=-0.035, cut=-0.02)
arm_parts = [arm_mass,
             shelf_on(arm_patch, "ArmShelf0", (0.32, 0.06, 1.5), (1.0, 0.2), 0.08, 0.052, 0.015, 91),
             shelf_on(arm_patch, "ArmShelf1", (0.32, 0.07, 1.535), (1.0, 0.0), 0.06, 0.038, 0.012, 95),
             shelf_on(arm_patch, "ArmShelf2", (0.33, 0.12, 1.43), (1.0, 0.6), 0.055, 0.036, 0.011, 92),
             stalk_on(arm_patch, "ArmStalk0", (0.27, 0.0, 1.62), 0.03, 0.002, 93, lean=(0.1, 0.0, 0.4)),
             strands("ArmStrands", arm_patch, 3, 94, thread)]
part(arm_parts, "LeftArm")

# The face must stay clear: nothing in front of the head near the eyes
eye_zone = 0
for o in head_parts:
    V = mesh_verts(o)
    eye_zone += int(np.sum((V[:, 1] < -0.03) & (np.abs(V[:, 0]) < 0.075) & (V[:, 2] > 1.66) & (V[:, 2] < 1.78)))
print("[fungus] vertices in front of the face: %d" % eye_zone)
for label in ("Head#Fungus", "Spine2#Fungus", "LeftArm#Fungus"):
    objs = [p for p in pieces if p["zbone"] == label]
    V = np.vstack([mesh_verts(p) for p in objs])
    print("[fungus] %s: %d tris, bounds %s .. %s" % (
        label, sum(len(f.vertices) - 2 for p in objs for f in p.data.polygons), np.round(V.min(0), 3),
        np.round(V.max(0), 3)))
parts = zk.export("Fungus", pieces, ASSETS)
zk.previews("fungus", PREVIEWS, Vector((0.05, 0.0, 1.5)), distance=1.3)
preview("fungus_close_head", (0.55, -0.35, 1.8), (0.06, 0.04, 1.7), lens=60)
preview("fungus_close_back", (0.25, 0.75, 1.5), (0.03, 0.2, 1.38), lens=60)
preview("fungus_face", (0.0, -0.8, 1.73), (0.02, 0.0, 1.7), lens=60)
print("[fungus] done")
