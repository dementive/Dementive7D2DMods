"""Chewed calf (gore, "how they died"): the back of the right calf chewed away: a ragged hollow 12 cm long, its lip
scalloped with bites, wet dark maroon muscle down to a strip of yellowed shin bone along its bottom, short rigid
strips of torn muscle hanging straight down from the lower lip, and dried blood run down the leg below it.

The hollow stands on the calf 1.6 cm outside the shin's hit box, where probes rendered on the vanilla zombies put
Joe's bare calf and the fat cop's trouser leg (the nurse's is 3 cm further in, so on her it stands proud). One part
on the RightLeg bone, RightLeg#Calf (the game sizes it to the shin's thickness).

    blender -b --factory-startup --python chewed_calf.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "ChewedCalf"), args[1]
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


# ---------------------------------------------------------------- gore helpers (same block in every gore script)
# A wound can't be sunk into the zombie: its own opaque mesh would cover anything under its skin. So each wound is a
# torn hole standing on the skin: a ragged lip of torn skin and cloth curling up and out round a pit of wet flesh whose
# floor stays just above the skin, the lip's outside diving steeply into the body so it meets any zombie's skin in a
# dark, ragged edge. Bones, guts and torn strips are swept tubes and sheets.

def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def put_vec(obj, name, values):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.asarray(values, np.float32).ravel())


def unitized(fn, e=2e-4):
    """fn divided by its gradient's length where that is over 1, so steep height fields settle cleanly."""
    def f(P):
        d = fn(P)
        g = np.stack([fn(P + v) - fn(P - v) for v in np.eye(3) * e], 1) / (2 * e)
        return d / np.maximum(np.linalg.norm(g, axis=1), 1.0)
    return f


class Gash:
    """A torn hole through the skin around C (on the real skin, outward normal n), an ellipse a along e1 by b across,
    its edge ragged. ground(P) is the distance to the real skin. Heights are above it: the pit's floor at `floor`, the
    lip's crest up to `lip` (ragged), the lip's outer slope `slope` wide, then a dive at `steep` into the body. A bead
    along the crest overhangs outward, so the lip reads as torn skin curling back."""

    def __init__(self, C, n, e1, a, b, seed, ground, floor=0.003, lip=0.012, wall=0.005, slope=0.008, jag=0.16,
                 steep=2.4, deep=-0.07, bumps=0.002, curl=0.0015):
        self.C, self.n = np.asarray(C, float), unit(n)
        e1 = np.asarray(e1, float)
        self.e1 = unit(e1 - self.n * (e1 @ self.n))
        self.e2 = np.cross(self.n, self.e1)
        self.a, self.b, self.seed, self.ground = a, b, seed, ground
        self.floor, self.lip, self.wall, self.slope = floor, lip, wall, slope
        self.jag, self.steep, self.deep, self.bumps, self.curl = jag, steep, deep, bumps, curl
        self.ph = np.random.default_rng(seed).uniform(0, 2 * math.pi, 10)
        self.extra = []  # (kind, fn, k): more shapes joined (smin) to or cut (smax) from the field
        self.cut, self.back = -0.03, 0.035
        self.tongues = []
        self.skirt, self.skirt_dir = 0.0, 0.0  # the outer slope this many times wider toward angle skirt_dir
        self.dents = []

    def uv(self, P):
        q = P - self.C
        return q @ self.e1, q @ self.e2

    def angle(self, P):
        u, v = self.uv(P)
        return np.arctan2(v / self.b, u / self.a)

    def outline(self, th):
        p = self.ph
        x = (0.45 * np.sin(3 * th + p[0]) + 0.25 * np.sin(5 * th + p[1]) + 0.18 * np.sin(9 * th + p[2])
             + 0.3 * (np.abs(np.sin(6.5 * th + p[3])) - 0.6) + 0.18 * (np.abs(np.sin(13.5 * th + p[7])) - 0.6))
        return 1.0 + self.jag * x

    def tear(self, th):
        """The lip's height round the hole (0.35-1): torn higher in places, low where it split."""
        p = self.ph
        x = 0.8 + 0.14 * np.sin(2 * th + p[4]) + 0.08 * np.sin(5 * th + p[5]) + 0.06 * np.sin(11 * th + p[6])
        return np.clip(x, 0.5, 1.0)

    def s(self, P):
        """Distance outside the hole's ragged edge (negative inside), about metric."""
        u, v = self.uv(P)
        th = np.arctan2(v / self.b, u / self.a)
        rho = np.sqrt((u / self.a) ** 2 + (v / self.b) ** 2)
        phi = np.arctan2(v, u)
        rr = 1.0 / np.sqrt((np.cos(phi) / self.a) ** 2 + (np.sin(phi) / self.b) ** 2)
        return (rho - self.outline(th)) * rr

    def crest(self, P):
        return self.lip * self.tear(self.angle(P)) * (1.0 + 0.16 * waves(P, 0.011, self.seed + 5, 2))

    def slope_at(self, th):
        if not self.skirt:
            return self.slope
        return self.slope * (1.0 + self.skirt * np.maximum(np.cos(th - self.skirt_dir), 0.0) ** 3)

    def height(self, P):
        s = self.s(P)
        L = self.crest(P)
        sl = self.slope_at(self.angle(P))
        flo = self.floor + self.bumps * waves(P, 0.018, self.seed + 1, 2)
        h_in = flo + (L - flo) * smooth01(-self.wall, 0.0, s) ** 1.5
        h_out = L * (1.0 - smooth01(0.0, sl, s)) - self.steep * np.maximum(s - sl * 0.6, 0.0)
        return np.maximum(np.where(s < 0.0, h_in, h_out), self.deep)

    def bead(self, P):
        """A rolled bead along the crest, set a little outside the edge, so the lip overhangs."""
        s = self.s(P)
        L = self.crest(P)
        rc = self.curl
        return np.sqrt((s - rc * 0.7) ** 2 + (self.ground(P) - (L - rc)) ** 2) - rc

    def base(self, P):
        return smin(self.ground(P) - self.height(P), self.bead(P), 0.002)

    def field(self, P):
        d = self.base(P)
        for kind, fn, k in self.extra:
            d = smin(d, fn(P), k) if kind == "add" else smax(d, -fn(P), k)
        return d

    def bite_marks(self, arcs, depth=0.0026, size=0.0034, out=0.0012, seed=0):
        """Tooth marks round the lip: for each arc (from angle, to angle, count) a row of rounded dents pressed into
        the crest, the middle ones (incisors) wider, a second fainter row on the skin outside."""
        rng = np.random.default_rng(self.seed + seed)
        for th0, th1, count in arcs:
            for k in range(count):
                f = (k + 0.5) / count
                th = th0 + (th1 - th0) * f
                w = size * (1.25 if abs(f - 0.5) < 0.2 else 0.9) * rng.uniform(0.9, 1.1)
                r_edge = self.outline(th)
                outd = unit(self.e1 * math.cos(th) * self.b + self.e2 * math.sin(th) * self.a)
                root = self.C + self.e1 * (self.a * r_edge * math.cos(th)) + self.e2 * (self.b * r_edge * math.sin(th))
                for ring, s_off, dd in ((0, out, depth), (1, out + 0.0055, depth * 0.55)):
                    q = root + outd * s_off
                    base = project(np.array([q + self.n * 0.05]), self.ground, self.n)[0]
                    h = float(self.height(np.array([base]))[0])
                    tang = unit(np.cross(self.n, outd))
                    c = base + self.n * (max(h, 0.0) + w * 0.35 - dd)
                    F = np.array([tang, outd, self.n])
                    fn = lambda P, c=c, F=F, w=w: sd_ellipsoid(P, c, (w * 0.55, w * 0.42, w * 0.38), F)  # noqa: E731
                    self.extra.append(("cut", fn, 0.0008))
                    self.dents.append(fn)

    def reach(self):
        """How far outside the edge the solid reaches before it is well under `cut`."""
        return self.slope * (1.0 + self.skirt) * 0.6 + (0.012 - self.cut) / self.steep + 0.004

    def region(self, P):
        """Negative under the wound: round the hole, and no deeper than `back` behind it (not the limb's far side)."""
        return np.maximum(self.s(P) - self.reach(), (self.C - P) @ self.n - self.back)

    def box(self, pad=0.03):
        r = max(self.a, self.b) * (1 + self.jag) + self.reach() + pad
        lo = self.C - r
        hi = self.C + r
        return lo, hi

    def mesh(self, name, material, tris, h=0.0018, inner=-0.045, cut=-0.03, keep=None, back=None):
        self.cut = cut
        if back is not None:
            self.back = back
        fn = unitized(self.field)
        lo, hi = self.box()

        def kp(P):
            k = 0.8 * np.exp(-(self.s(P) / 0.006) ** 2)
            return k if keep is None else np.maximum(k, keep(P))
        obj = field_mesh(name, fn, lo, hi, h, material, tris, inner=inner, keep=kp, cut=cut, region=self.region,
                         ground=self.ground)
        self.attrs(obj)
        return obj

    def attrs(self, obj):
        P = mesh_verts(obj)
        s = self.s(P)
        gnd = self.ground(P)
        L = self.crest(P)
        u, v = self.uv(P)
        put(obj, "pit", smooth01(-0.001, -0.006, s) * smooth01(L * 0.85, self.floor + 0.002, gnd))
        put(obj, "lipc", np.exp(-((s - 0.001) / 0.0035) ** 2) * smooth01(L * 0.3, L * 0.8, gnd))
        put(obj, "outer", smooth01(0.0, self.slope * 0.7, s))
        put(obj, "edge", smooth01(self.slope * 0.5, self.slope + 0.008, s))
        fl = np.zeros(len(P))
        for fn in self.tongues:
            fl = np.maximum(fl, smooth01(0.0015, -0.0005, fn(P)))
        put(obj, "flap", fl)
        dn = np.zeros(len(P))
        for fn in self.dents:
            dn = np.maximum(dn, smooth01(0.0015, -0.0005, -fn(P)))
        put(obj, "dent", dn)
        put(obj, "bruise", smooth01(self.slope_at(self.angle(P)) * 1.3, 0.0, s) * (s > -0.002))
        put(obj, "bone", np.zeros(len(P)))
        put_vec(obj, "fib", np.stack([u, v, gnd], 1))
        return obj

    def tongue(self, th0, length, width, thick=0.0032, lift=0.0015, tilt=10.0):
        """A tongue of torn skin and cloth peeled back off the lip at angle th0 (round the hole): a flat, rounded flap
        lying out over the lip's outside, fused to it, its tip lifting a little."""
        r_edge = self.outline(th0)
        root = self.C + self.e1 * (self.a * r_edge * math.cos(th0)) + self.e2 * (self.b * r_edge * math.sin(th0))
        out = unit(self.e1 * math.cos(th0) * self.b + self.e2 * math.sin(th0) * self.a)
        side = np.cross(self.n, out)
        mid = root + out * (length * 0.42)
        base = project(np.array([mid + self.n * 0.05]), self.ground, self.n)[0]
        h = max(float(self.height(np.array([base]))[0]), 0.0)
        c = base + self.n * (h + thick * 0.5 + lift)
        t = math.radians(tilt)
        o2 = out * math.cos(t) + self.n * math.sin(t)
        F = np.array([o2, side, np.cross(o2, side)])
        fn = lambda P, c=c, F=F: sd_ellipsoid(P, c, (length * 0.5, width * 0.5, thick * 0.5), F)  # noqa: E731
        self.extra.append(("add", fn, 0.002))
        self.tongues.append(fn)
        return fn

    def surface_point(self, P0, steps=6):
        """Points moved onto the wound's surface along the normal n (from outside)."""
        P = np.array(P0, float)
        f = unitized(self.field)
        for _ in range(steps):
            P = P - f(P)[:, None] * self.n[None]
        return P


def surface_at(start, d, ground, steps=200):
    """Where a ray from `start` along d meets ground = 0, and the outward normal there."""
    d = unit(d)
    p = np.array([start], float)
    for _ in range(steps):
        g_ = ground(p)[0]
        if abs(g_) < 1e-6:
            break
        p = p + d * g_ * 0.8
    n = np.array([ground(p + v)[0] - ground(p - v)[0] for v in np.eye(3) * 2e-4])
    return p[0], unit(n)


def project(P, ground, n, steps=8):
    """Points moved onto ground = 0 along the direction n."""
    P = np.array(P, float)
    for _ in range(steps):
        P = P - ground(P)[:, None] * n[None]
    return P


def lift(p, h, ground, n):
    """The point on ground = 0 found along n from p, raised h along the surface's own normal there."""
    q = project(np.array([np.asarray(p, float) + n * 0.05]), ground, n)[0]
    g_ = unit(np.array([ground(np.array([q + v]))[0] - ground(np.array([q - v]))[0] for v in np.eye(3) * 2e-4]))
    return q + g_ * h


def strip(name, mat, pts, width, thick, seed, attrs=None, sides_n=None):
    """A torn ribbon of muscle or skin along pts (its width across `sides_n`, the direction it lies flat against), its
    end ragged and tapered: per-vertex pit 1 (raw meat) and fibers along it."""
    rng = np.random.default_rng(seed)
    P = [np.asarray(p, float) for p in pts]
    n = len(P)
    T = [unit(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]) for i in range(n)]
    W = [unit(np.cross(t, sides_n)) for t in T]
    N = [unit(np.cross(w, t)) for w, t in zip(W, T)]
    bm = bmesh.new()
    rows, fib = [], []
    L = 0.0
    for i, p in enumerate(P):
        if i:
            L += np.linalg.norm(P[i] - P[i - 1])
        f = i / (n - 1)
        w = width * (1.0 - 0.55 * f ** 1.5) * (1.0 + rng.uniform(-0.12, 0.12))
        t = thick * (1.0 - 0.5 * f)
        row = []
        for c in (-1.0, -0.33, 0.33, 1.0):
            jag = rng.uniform(-0.004, 0.004) if i == n - 1 else 0.0
            q = p + W[i] * (c * w * 0.5) + T[i] * jag
            row.append((bm.verts.new(q + N[i] * t * 0.5 * (1.0 - 0.4 * abs(c))),
                        bm.verts.new(q - N[i] * t * 0.5 * (1.0 - 0.4 * abs(c)))))
            fib += [(L, c * w, 0.0), (L, c * w, 0.0)]
        rows.append(row)
    for i in range(n - 1):
        a, b = rows[i], rows[i + 1]
        for k in range(3):
            bm.faces.new((a[k][0], a[k + 1][0], b[k + 1][0], b[k][0]))
            bm.faces.new((a[k][1], b[k][1], b[k + 1][1], a[k + 1][1]))
        bm.faces.new((a[0][0], b[0][0], b[0][1], a[0][1]))
        bm.faces.new((a[3][0], a[3][1], b[3][1], b[3][0]))
    for row, flip in ((rows[0], True), (rows[-1], False)):
        for k in range(3):
            q = (row[k][0], row[k + 1][0], row[k + 1][1], row[k][1])
            bm.faces.new(q[::-1] if flip else q)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    m = len(obj.data.vertices)
    vals = dict(pit=1.0, lipc=0.0, outer=0.0, edge=0.0, flap=1.0, bone=0.0)
    vals.update(attrs or {})
    for k, v in vals.items():
        put(obj, k, np.full(m, v))
    put_vec(obj, "fib", np.array(fib) * np.array([1.0, 3.0, 1.0]))
    return tk.smooth(obj, 60)


def gut_material(name, seed=0.0, value=0.85):
    """Intestine: wet, dark grey-purple and dusky red, mottled, laced with fine dark red vessels and a few yellowish
    streaks of fat along it, glossy."""
    mat, g = tk.new_material(name)
    P = mapping(g, g.coords(), loc=(seed * 0.41, seed * 0.17, seed * 0.83))
    tt = attr(g, "tt")
    mott = g.noise(45.0, detail=5.0, roughness=0.6, vector=P)
    col = g.mix(g.ramp(mott, 0.3, 0.75), (0.045, 0.022, 0.025), (0.085, 0.042, 0.044))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=4.0, vector=P), 0.45, 0.7), 0.7), col,
                (0.075, 0.018, 0.015))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=3.0, vector=P), 0.6, 0.75), 0.6), col,
                (0.04, 0.038, 0.042))
    vessels = veins(g, 60.0, 0.03, warp_amount=1.0, broken=0.6, vector=P)
    col = g.mix(g.math("MULTIPLY", vessels, 0.45), col, (0.035, 0.006, 0.007))
    fat = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(30.0, 30.0, 30.0))), 0.66,
                                    0.72), 0.5)
    col = g.mix(fat, col, (0.1, 0.075, 0.042))
    # Blood and grime caked on where it drags against the body
    dirt = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0, distortion=0.6, vector=P), 0.48, 0.66), 0.9)
    col = g.mix(dirt, col, (0.035, 0.006, 0.005))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.cavity(0.01), 0.9, 0.4), 0.7), col, (0.02, 0.006, 0.007))
    col = tk.grade(g, col, sat=0.85, value=value)
    rough = g.math("ADD", 0.26, g.math("MULTIPLY", mott, 0.14))
    rough = g.mixf(dirt, rough, 0.5)
    height = g.math("ADD", g.math("MULTIPLY", g.noise(200.0, detail=4.0, vector=P), 0.25),
                    g.math("MULTIPLY", vessels, 0.4))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.55, 0.0012))


def bone_field(name, fn, ground, mat, tris, lo, hi, h=0.0014, inner=-0.02, cut=-0.012, region=None):
    """Bone shapes as a distance field (vertebrae, rib ends), meshed above `cut` like the wounds, with the per-vertex
    signals bone_material reads (tt from how far it stands out of the flesh)."""
    obj = field_mesh(name, unitized(fn), lo, hi, h, mat, tris, inner=inner, cut=cut, region=region, ground=ground)
    P = mesh_verts(obj)
    gnd = ground(P)
    put(obj, "tt", smooth01(0.002, 0.016, gnd))
    put(obj, "brk", np.zeros(len(P)))
    put(obj, "cup", np.zeros(len(P)))
    put(obj, "ang", np.zeros(len(P)))
    return obj


def frames(P, x0):
    """Tangents and twist-free cross-section axes along a polyline."""
    n = len(P)
    T = [unit(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]) for i in range(n)]
    X, ref = [], np.asarray(x0, float)
    for t in T:
        x = unit(ref - t * (ref @ t))
        X.append(x)
        ref = x
    return T, X, [np.cross(t, x) for t, x in zip(T, X)]


def sweep(name, P, radius, mat, sides=10, x0=(0.0, 0.0, 1.0), cap0=True, end=None, attrs=None, smooth=60):
    """A tube through the points P with radius(i, angle) (or one number); its start closed flat (cap0) and its end
    closed round, or broken (end = dict(spikes=[per side], cup=depth, inner=fraction)): a jagged crown of the wall
    round a cup going down into the marrow. Per-vertex: 'tt' 0-1 along, 'brk' 1 on the break, 'cup' 1 in the marrow,
    'ang' the angle round (0-1)."""
    P = [np.asarray(p, float) for p in P]
    T, X, Y = frames(P, x0)
    rf = radius if callable(radius) else (lambda i, a: radius)
    bm = bmesh.new()
    rings, tt, brk, cup, ang = [], [], [], [], []
    L = [0.0]
    for i in range(1, len(P)):
        L.append(L[-1] + np.linalg.norm(P[i] - P[i - 1]))
    for i, p in enumerate(P):
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            r = rf(i, a)
            ring.append(bm.verts.new(p + (X[i] * math.cos(a) + Y[i] * math.sin(a)) * r))
            tt.append(L[i] / L[-1])
            brk.append(0.0)
            cup.append(0.0)
            ang.append(j / sides)
        rings.append(ring)
    for i in range(len(rings) - 1):
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
    if cap0:
        bm.faces.new(list(reversed(rings[0])))
    p, t = P[-1], T[-1]
    if end is None:
        c = bm.verts.new(p + t * rf(len(P) - 1, 0.0) * 0.8)
        tt.append(1.0)
        brk.append(0.0)
        cup.append(0.0)
        ang.append(0.0)
        for j in range(sides):
            bm.faces.new((rings[-1][j], rings[-1][(j + 1) % sides], c))
    else:
        sp = end["spikes"]
        crown, inner = [], []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            r = rf(len(P) - 1, a)
            k = sp[j] / max(max(sp), 1e-6)
            d = X[-1] * math.cos(a) + Y[-1] * math.sin(a)
            crown.append(bm.verts.new(p + t * sp[j] + d * r * (0.97 - 0.22 * k)))
            inner.append(bm.verts.new(p + t * (sp[j] * 0.15) + d * r * end.get("inner", 0.6)))
            tt += [1.0, 1.0]
            brk += [1.0, 1.0]
            cup += [0.0, 1.0]
            ang += [j / sides, j / sides]
        c = bm.verts.new(p - t * end.get("cup", r * 0.8))
        tt.append(1.0)
        brk.append(1.0)
        cup.append(1.0)
        ang.append(0.0)
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((rings[-1][j], rings[-1][k], crown[k], crown[j]))
            bm.faces.new((crown[j], crown[k], inner[k], inner[j]))
            bm.faces.new((inner[j], inner[k], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    put(obj, "tt", tt)
    put(obj, "brk", brk)
    put(obj, "cup", cup)
    put(obj, "ang", ang)
    if attrs:
        for k, v in attrs.items():
            put(obj, k, [v] * len(tt))
    return tk.smooth(obj, smooth)


def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def voronoi(g, vec, scale, feature="F1"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Distance")


def flesh_material(name, seed=0.0, fiber=(60.0, 6.0, 6.0), bruise=False, value=0.74, drips=False):
    """The wound: wet dark maroon muscle in the pit, its fibers running along the wound, black clots and a few specks
    of yellow fat; the torn lip raw red-brown; its outside torn skin and cloth soaked dark with dried blood, darkest at
    the ragged edge where it meets the zombie. Wet in the pit, dull outside. bruise=True stains the swollen
    skin round it (an infected bite); drips=True runs dried blood down below it."""
    mat, g = tk.new_material(name)
    pit, lipc, outer, edge, flap = (attr(g, k) for k in ("pit", "lipc", "outer", "edge", "flap"))
    fib = vec_attr(g, "fib")
    P = mapping(g, g.coords(), loc=(seed * 0.37, seed * 0.71, seed * 0.13))
    # ---- muscle: maroon, fibrous, clotted
    strands = g.noise(1.0, detail=4.0, roughness=0.55, vector=mapping(g, fib, scale=fiber, loc=(seed, 0.3, 0.1)))
    mott = g.noise(40.0, detail=5.0, roughness=0.6, vector=P)
    meat = g.mix(g.ramp(mott, 0.3, 0.75), (0.05, 0.0065, 0.0055), (0.115, 0.013, 0.01))
    meat = g.mix(g.math("MULTIPLY", g.ramp(strands, 0.45, 0.75), 0.6), meat, (0.15, 0.02, 0.014))
    meat = g.mix(g.math("MULTIPLY", g.ramp(strands, 0.4, 0.2), 0.7), meat, (0.022, 0.0045, 0.0035))
    clot = g.math("MULTIPLY", g.ramp(voronoi(g, P, 140.0), 0.22, 0.08), g.ramp(g.noise(9.0, detail=3.0, vector=P), 0.4, 0.6))
    meat = g.mix(clot, meat, (0.012, 0.0028, 0.0022))
    fat = g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=4.0, distortion=1.0, vector=P), 0.7, 0.76), 0.55)
    meat = g.mix(g.math("MULTIPLY", fat, 0.6), meat, (0.11, 0.075, 0.038))
    cav = g.cavity(0.012)
    meat = g.mix(g.math("MULTIPLY", g.ramp(cav, 0.9, 0.4), 0.75), meat, (0.01, 0.0022, 0.0018))
    # ---- the torn lip: raw skin and fat, red-brown
    raw = g.mix(g.ramp(g.noise(55.0, detail=5.0, vector=P), 0.3, 0.7), (0.07, 0.014, 0.011), (0.13, 0.03, 0.022))
    raw = g.mix(g.math("MULTIPLY", fat, 0.4), raw, (0.12, 0.085, 0.05))
    # ---- outside: torn skin and cloth soaked with dried blood
    weave = g.noise(1.0, detail=2.0, vector=mapping(g, P, scale=(420.0, 420.0, 420.0)))
    cloth = g.mix(g.ramp(g.noise(12.0, detail=5.0, vector=P), 0.3, 0.75), (0.035, 0.009, 0.007), (0.07, 0.02, 0.014))
    cloth = g.mix(g.math("MULTIPLY", weave, 0.25), cloth, (0.018, 0.009, 0.007))
    soak = g.ramp(g.math("ADD", g.math("MULTIPLY", outer, -0.7), g.noise(6.0, detail=5.0, distortion=0.5, vector=P)),
                  0.15, 0.45)
    cloth = g.mix(g.math("MULTIPLY", soak, 0.85), cloth, (0.06, 0.008, 0.006))
    col = g.mix(g.math("MAXIMUM", g.ramp(outer, 0.05, 0.6), g.math("MULTIPLY", flap, 0.85)), raw, cloth)
    col = g.mix(g.ramp(g.math("ADD", lipc, g.math("MULTIPLY", g.noise(30.0, detail=4.0, vector=P), 0.3)), 0.55, 0.85),
                col, raw)
    col = g.mix(g.ramp(pit, 0.15, 0.6), col, meat)
    if bruise:
        # An infected bite: the skin round it swollen, bruised dark purple going sickly green-yellow at its edge,
        # dark veins creeping out of it; the tooth marks dark with dried blood
        b = attr(g, "bruise")
        bn = g.noise(9.0, detail=5.0, vector=P)
        reachb = g.math("ADD", b, g.math("MULTIPLY", bn, 0.35))
        bm_ = g.math("MULTIPLY", g.ramp(reachb, 0.15, 0.6), g.math("SUBTRACT", 1.0, g.ramp(pit, 0.1, 0.4)))
        bcol = g.mix(g.ramp(reachb, 0.35, 0.8), (0.07, 0.075, 0.03), (0.075, 0.022, 0.055))
        bcol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=4.0, vector=P), 0.5, 0.7), 0.6), bcol,
                     (0.11, 0.1, 0.045))
        vn = g.math("MULTIPLY", veins(g, 30.0, 0.035, warp_amount=1.2, broken=0.5, vector=P), g.ramp(reachb, 0.05, 0.4))
        bcol = g.mix(g.math("MULTIPLY", vn, 0.8), bcol, (0.025, 0.012, 0.03))
        col = g.mix(g.math("MULTIPLY", bm_, 0.95), col, bcol)
        dent = attr(g, "dent")
        col = g.mix(g.math("MULTIPLY", g.ramp(dent, 0.2, 0.8), 0.9), col, (0.045, 0.008, 0.007))
    if drips:
        # Dried blood run down the outside below the wound (e1, the fibers' first axis, points up)
        fu = g.separate(fib)[0]
        runs = g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, fib, scale=(6.0, 160.0, 6.0), loc=(seed, 0.4, 0.2))),
                      0.56, 0.64)
        below = g.math("MULTIPLY", g.ramp(fu, 0.0, -0.03), g.ramp(outer, 0.05, 0.4))
        dm = g.math("MULTIPLY", g.math("MAXIMUM", runs, g.math("MULTIPLY", below, 0.5)), below)
        col = g.mix(g.math("MULTIPLY", dm, 0.95), col, (0.035, 0.005, 0.004))
    # The ragged dark edge where it meets the zombie
    rim = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", g.noise(22.0, detail=5.0, distortion=0.4, vector=P), 0.45)),
                 0.55, 0.9)
    col = g.mix(g.math("MULTIPLY", rim, 0.8), col, (0.014, 0.009, 0.007))
    col = tk.grade(g, col, sat=0.92, value=value)
    wet = g.math("MAXIMUM", g.ramp(pit, 0.1, 0.5), g.math("MULTIPLY", g.ramp(lipc, 0.4, 0.9), 0.6))
    rough = g.mixf(wet, g.mixf(g.ramp(outer, 0.1, 0.7), 0.5, 0.8), g.math("ADD", 0.3, g.math("MULTIPLY", mott, 0.14)))
    rough = g.mixf(g.math("MULTIPLY", clot, g.ramp(pit, 0.1, 0.5)), rough, 0.22)
    rough = g.mixf(rim, rough, 0.88)
    pores = g.ramp(voronoi(g, mapping(g, P, loc=(0.2, 0.6, 0.1)), 420.0), 0.05, 0.3)
    height = g.math("MULTIPLY", g.noise(260.0, detail=5.0, vector=P), 0.35)
    height = g.math("ADD", height, g.math("MULTIPLY", pores, 0.25))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("MULTIPLY", strands, pit), 0.8))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("MULTIPLY", weave, outer), 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", clot, 0.4))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.7, 0.0012))


def bone_material(name, seed=0.0, value=0.62):
    """Old yellowed bone, darker and browner toward where it leaves the flesh and caked with dried blood there; the
    snapped end paler and raw, the marrow dark red-brown and wet; grain running along it, hairline cracks."""
    mat, g = tk.new_material(name)
    tt, brk, cupm = attr(g, "tt"), attr(g, "brk"), attr(g, "cup")
    P = mapping(g, g.coords(), loc=(seed * 0.3, seed * 0.9, seed * 0.5))
    grain = g.noise(1.0, detail=5.0, roughness=0.6, vector=mapping(g, P, scale=(260.0, 260.0, 260.0)))
    bone = g.mix(g.ramp(g.noise(18.0, detail=5.0, vector=P), 0.3, 0.7), (0.13, 0.095, 0.045), (0.085, 0.058, 0.027))
    bone = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.45, 0.65), 0.5), bone, (0.17, 0.11, 0.05))
    crack = veins(g, 40.0, 0.02, warp_amount=0.7, broken=0.7, vector=P)
    bone = g.mix(g.math("MULTIPLY", crack, 0.4), bone, (0.07, 0.045, 0.022))
    bone = g.mix(g.ramp(brk, 0.3, 0.9), bone, (0.16, 0.12, 0.065))
    marrow = g.mix(g.ramp(voronoi(g, P, 300.0), 0.05, 0.25), (0.02, 0.004, 0.003), (0.07, 0.018, 0.01))
    bone = g.mix(g.ramp(cupm, 0.3, 0.8), bone, marrow)
    # Blood: caked thick where it leaves the flesh, a ragged line up the shaft, runs and spatter on the break
    reach = g.math("ADD", 0.45, g.math("MULTIPLY", g.noise(7.0, detail=4.0, vector=P), 0.4))
    coat = g.ramp(g.math("SUBTRACT", reach, tt), -0.05, 0.05)
    spat = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.4, 0.2, 0.9)), 160.0), 0.3, 0.07),
                  g.ramp(g.noise(11.0, detail=3.0, vector=P), 0.45, 0.6))
    blood = g.math("MAXIMUM", coat, spat)
    bc = g.mix(g.ramp(g.noise(25.0, detail=4.0, vector=P), 0.3, 0.7), (0.03, 0.006, 0.0045), (0.075, 0.012, 0.009))
    col = g.mix(g.math("MULTIPLY", blood, 0.92), bone, bc)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.cavity(0.006), 0.9, 0.4), 0.7), col, (0.03, 0.012, 0.007))
    col = tk.grade(g, col, sat=0.85, value=value)
    rough = g.math("ADD", 0.4, g.math("MULTIPLY", grain, 0.15))
    rough = g.mixf(blood, rough, 0.22)
    rough = g.mixf(cupm, rough, 0.12)
    height = g.math("SUBTRACT", g.math("MULTIPLY", grain, 0.5), g.math("MULTIPLY", crack, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", coat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.0012))


def proxy_mesh(name, fn, lo, hi, h=0.003):
    """The real body surface the wound is fitted to, as a mesh for the previews (never exported)."""
    V, Q = surface_nets(fn, lo, hi, h)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], Q.tolist())
    me.validate()
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.append(bpy.data.materials["BodySkin"])
    obj["zbody"] = True
    return tk.smooth(obj, 180.0)


def preview_proxy(ground, bones, lo, hi, h=0.004):
    """For the previews: the stand-in's hit boxes on `bones` swapped for the real body the wound is fitted to."""
    for i, c in enumerate(zk.joe().colliders):
        if c["bone"] in bones:
            o = bpy.data.objects.get("Body_%d" % i)
            if o is not None:
                o.hide_render = True
    return proxy_mesh("Proxy", ground, lo, hi, h)


def catmull(points, k=4):
    """A smooth curve through the points (Catmull-Rom), k samples per span."""
    P = [np.asarray(p, float) for p in points]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(k):
            t = j / k
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return out


def report(name, pieces):
    groups = {}
    for p in pieces:
        groups.setdefault(p["zbone"], []).append(p)
    total = 0
    for label, objs in groups.items():
        V = np.vstack([mesh_verts(o) for o in objs])
        tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
        total += tris
        print("[%s] %s: %d tris, bounds %s .. %s" % (name, label, tris, np.round(V.min(0), 3), np.round(V.max(0), 3)))
    print("[%s] %d tris in all" % (name, total))

# ---------------------------------------------------------------- end of gore helpers


# ---------------------------------------------------------------- the calf

SK = zk.joe()
LEG = ("RightLeg",)
# The real calf a little outside the shin's hit box (probes rendered on the vanilla zombies: Joe's bare calf and the
# cop's trouser leg about 1.5 to 2 cm out, the nurse's 1.5 cm in, so on her it stands proud)
SKIN_OUT = 0.016


def ground(P):
    return body(np.atleast_2d(P), LEG) - SKIN_OUT


UP = unit(np.array(SK.pos("RightLeg")) - np.array(SK.pos("RightFoot")))
C, N = surface_at((-0.158, 0.6, 0.37), (0.0, -1.0, 0.0), ground)

tk.reset_scene()
zk.stage()
BODY = zk.body()
flesh = flesh_material("CalfFlesh", seed=19.0, fiber=(70.0, 9.0, 9.0), drips=True)
bone = bone_material("Shin", seed=21.0)

# A ragged hollow chewed out of the back of the calf, 12 cm long, its lower lip running out into dried blood
wound = Gash(C, N, UP, 0.058, 0.026, 61, ground, floor=0.004, lip=0.014, wall=0.006, slope=0.008, jag=0.22,
             steep=2.4, bumps=0.0032)
wound.skirt, wound.skirt_dir = 1.6, math.pi
# Bites taken out of it all round: scalloped notches in the lip
wound.bite_marks(((0.2, 1.2, 4), (1.9, 2.8, 3), (3.5, 4.3, 3), (4.9, 5.9, 4)), depth=0.004, size=0.0065,
                 out=0.0005, seed=3)
E2 = wound.e2


def at(u, v, h):
    return lift(C + wound.e1 * u + E2 * v, h, ground, N)


# ---------------------------------------------------------------- the shin bone and the torn strips

# A strip of yellowed bone along the bottom of the hollow, its ends running on under the flesh
bpts = []
for j in range(9):
    f = j / 8
    u = -0.036 + 0.066 * f
    rise = math.sin(math.pi * f) ** 0.6
    bpts.append(at(u, -0.004 + 0.002 * math.sin(5.0 * f), -0.004 + 0.0105 * rise))


def shin_r(i, a):
    return (1.0 + 0.06 * math.sin(1.9 * i)) / math.sqrt((math.cos(a) / 0.0032) ** 2 + (math.sin(a) / 0.0058) ** 2)


shin = sweep("Shin", bpts, shin_r, bone, sides=8, x0=N, cap0=True)
put(shin, "tt", np.full(len(shin.data.vertices), 0.3))
for a_, b_ in zip(bpts[:-1], bpts[1:]):
    wound.extra.append(("add", lambda P, a_=a_, b_=b_: sd_capsule(P, a_ - N * 0.006, b_ - N * 0.006, 0.0058), 0.004))

# Short torn strips of muscle hanging from the lower lip, rigid, straight down off the leg
DOWN = np.array([0.0, 0.0, -1.0])
strips = []
for k, (th, ln, w, out) in enumerate(((math.pi - 0.45, 0.038, 0.012, 0.004), (math.pi + 0.05, 0.052, 0.014, 0.006),
                                       (math.pi + 0.5, 0.032, 0.01, 0.003))):
    r_edge = wound.outline(th)
    root2d = C + wound.e1 * (wound.a * r_edge * math.cos(th)) + E2 * (wound.b * r_edge * math.sin(th))
    root = lift(root2d, wound.lip * 0.75, ground, N)
    pts = [root - N * 0.003]
    for j in range(1, 6):
        f = j / 5
        p = root + DOWN * ln * f + N * (out * math.sin(math.pi * f * 0.8) + 0.002 * f)
        pts.append(p)
    strips.append(strip("Strip%d" % k, flesh, pts, w, 0.0035, 70 + k, sides_n=N))

for th, ln, w in ((0.4, 0.013, 0.012), (1.7, 0.012, 0.011), (4.6, 0.014, 0.012)):
    wound.tongue(th, ln, w, thick=0.0028)
flesh_obj = wound.mesh("Hollow", flesh, 1650, h=0.0016, inner=-0.025, cut=-0.015, back=0.03)

pieces = [flesh_obj, shin] + strips
for p in pieces:
    zk.on(p, "RightLeg", "Calf")
print("[chewed_calf] hollow at (%.3f, %.3f, %.3f) facing (%.2f, %.2f, %.2f)" % (*C, *N))
report("chewed_calf", pieces)
parts = zk.export("ChewedCalf", pieces, ASSETS)
preview_proxy(ground, LEG, (-0.26, -0.1, 0.08), (-0.06, 0.13, 0.6), h=0.003)
zk.previews("chewed_calf", PREVIEWS, Vector((-0.16, 0.06, 0.36)), distance=0.9)
focus = C + N * 0.008
preview("chewed_calf_close", tuple(focus + unit(N * 1.0 + np.array([-0.35, 0.0, 0.1])) * 0.3), tuple(focus), lens=50)
preview("chewed_calf_side", tuple(focus + unit(N * 0.5 + np.array([-0.85, 0.0, -0.1])) * 0.3), tuple(focus), lens=50)
print("[chewed_calf] done")
