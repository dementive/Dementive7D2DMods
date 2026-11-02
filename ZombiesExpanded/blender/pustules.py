"""Pustules: the Bloater's mutation. Swollen pus sacs, boils, blisters and burst, crusted craters pushing out through
the zombie's clothes, in tight clusters with lone boils around them that thin out into small blisters and dark, wet,
bruised flesh. Every part is optional (`Var`), so each Bloater shows its own mix:

    Spine2#BackVar1      upper back, right of the spine: the big cluster
    Spine2#BackVar2      upper back, left of the spine and lower: a burst boil and a tight knot of boils
    LeftArm#ShoulderVar1 on top of the left shoulder
    RightArm#ShoulderVar2 the back of the right shoulder: a slack, half-drained sac
    LeftArm#ArmVar       down the outside of the left upper arm
    RightForeArm#ArmVar2 the top of the right forearm

There is no skin patch: each sac and boil rises on its own flared, bruised base from below the lowest clothes any of
vanilla Joe, the fat cop and the nurse has there (measured on their real meshes in Unity, in each part's own fitted
space), so the clothes cut every growth at an angle, wherever they lie, and what shows of the base is small, dark and
wet. Places where those three zombies' bodies differ by more than a few cm (the lower back, the flanks, the neck,
the chest) carry none.

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


def drop_crumbs(bm, fraction=0.05, least=12):
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
    crumbs = [f for i in islands if len(i) < max(least, big * fraction) for f in i]
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context="FACES")


def field_mesh(name, fn, lo, hi, h, material, tris, inner=-0.05, bones=TORSO, relax=3, keep=None, cut=-0.025,
               region=None, ground=None, crumbs=0.05):
    """A mesh of the growth surface fn = 0 where it stands above `inner` (a level inside the body). The solid between
    the two is meshed closed with surface nets inside the box lo..hi, relaxed for even triangles and decimated to
    about `tris` triangles above `cut`; then the faces below `cut` are dropped, so the mesh's edges lie deep inside
    the body. keep(points) weights the
    decimation toward detail. region(points), a distance that is negative under the growth, bounds the solid
    sideways (its walls must lie below `cut`), which keeps it from wrapping around thin limbs. `ground` is the
    distance to the body the levels are measured from (default: the stand-in, body(points, bones)). Islands smaller
    than `crumbs` of the biggest are dropped (lower it when the growth is meant to be many separate lumps)."""
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
        drop_crumbs(bm, crumbs, 8)

    bm = bmesh.new()
    bm.from_mesh(me)
    drop_crumbs(bm, crumbs, 8)
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


MARGIN = 0.004  # each growth's floor sits this far below the lowest clothes measured there
SPREAD = 0.026  # no growth where the clothes' levels differ more than this between zombies (it would stand on a stalk)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def sd_torus(P, c, n, major, minor):
    q = P - c
    along = q @ n
    rho = np.linalg.norm(q - along[:, None] * n, axis=1)
    return np.sqrt((rho - major) ** 2 + along ** 2) - minor


def limb_start(bone, child, f, angle, out=0.3):
    """A point `out` m off a limb, `f` of the way from `bone` to `child` and `angle` degrees around it (0 up and out,
    90 the back, -90 the front), and the direction back to the limb's axis."""
    sk = zk.joe()
    a, b = np.array(sk.pos(bone)), np.array(sk.pos(child))
    ax = unit(b - a)
    up = unit(np.array([0.0, 0.0, 1.0]) - ax * ax[2])
    back = np.cross(ax, up)
    if back[1] < 0:
        back = -back
    d = up * math.cos(math.radians(angle)) + back * math.sin(math.radians(angle))
    return a + (b - a) * f + d * out, -d


class Site:
    """The patch of body a part grows on, and how high real clothes lie over it. `low` and `high` are quadratics
    (cm above the stand-in) in the patch's tangent coordinates u, v (cm; u runs across, along up x normal, v roughly
    up), fitted to the lowest and the highest of vanilla Joe's, the fat cop's and the nurse's real surfaces there,
    after the game has fitted the part to each of them (their meshes rendered to position maps in Unity)."""

    def __init__(self, start, toward, low, high, span=8.0):
        self.c, self.n = on_body(start, TORSO, toward=toward)
        self.F = frame_from(self.n)
        self.lo_c, self.hi_c = np.asarray(low, float), np.asarray(high, float)
        self.span = span

    def uv(self, P):
        d = np.atleast_2d(P) - self.c
        return d @ self.F[0] * 100.0, d @ self.F[1] * 100.0

    def _quad(self, c, P):
        u, v = self.uv(P)
        u, v = np.clip(u, -self.span, self.span), np.clip(v, -self.span, self.span)
        return (c[0] + c[1] * u + c[2] * v + c[3] * u * u + c[4] * v * v + c[5] * u * v) / 100.0

    def low(self, P):
        return self._quad(self.lo_c, P)

    def high(self, P):
        return np.maximum(self._quad(self.hi_c, P), self.low(P) + 0.004)

    def floor(self, P):
        return self.low(P) - MARGIN

    def at(self, u, v):
        start = self.c + (self.F[0] * u + self.F[1] * v) / 100.0 + self.n * 0.2
        p, n = on_body(start, TORSO, toward=-self.n)
        if not np.all(np.isfinite(p)) or abs(body(p[None])[0]) > 1e-3:
            p, n = on_body(start, TORSO)  # the ray missed a thin limb: take the nearest point
        return p, n


ELONG = {"sac": 1.1, "slack": 0.6, "boil": 0.62, "crater": 0.8, "blister": 0.34}
PUS = {"sac": 1.0, "slack": 0.7, "boil": 0.6, "crater": 0.5, "blister": 0.25}
FOOT = 0.012     # the flared skirts start this far below the floor, out of sight
SLOPE = 0.9      # skirt width per unit of height: their flanks rise at about 50 degrees at the steepest


class Mound:
    """One growth pushing out at the patch point (u, v) (cm): a swollen head of radius R (cm) whose top stands `rise`
    cm above the clothes there (q = 1: above the highest clothes, so it shows on every zombie; q = 0: above the
    lowest, so it only breaks the surface where the clothes lie low), on a flared skirt of bruised flesh reaching down
    below the floor, so wherever a zombie's clothes cut it, it rises out of them at an angle with no undercut; `lift`
    raises the skirt that far (cm) above the highest clothes, for the swollen flesh around the big ones. Kinds: 'sac' (big, sagging like a pear, maybe lobed), 'slack' (half drained and wrinkled), 'boil' (a low dome
    with a pointed pus head), 'crater' (burst: a ragged rim around a crusted pit), 'blister' (low and flat)."""

    def __init__(self, site, u, v, R, rise, seed, kind="boil", q=1.0, elong=None, lean=(0.0, 0.0, 0.0), lobes=0,
                 sag=None, head=None, weep=0.0, lift=None):
        base, n0 = site.at(u, v)
        self.site = site
        self.n = unit(n0 + np.asarray(lean, float))
        self.base, self.kind, self.seed, self.weep = base, kind, seed, weep
        self.uv = (u, v)
        rng = np.random.default_rng(seed)
        self.R = R = R / 100.0
        self.C = C = R * (elong if elong is not None else ELONG[kind]) * rng.uniform(0.92, 1.08)
        lo, hi = site.low(base[None])[0], site.high(base[None])[0]
        self.floor = lo - MARGIN
        self.q = q
        self.top = lo + q * (hi - lo) + rise / 100.0
        self.hc = self.top - C
        self.frame = frame_from(self.n, up=(rng.uniform(-0.4, 0.4), 0.3, 1.0))
        self.radii = (R * rng.uniform(0.9, 1.1), R * rng.uniform(0.82, 1.0), C)
        sag = (0.18 if kind == "sac" else 0.06) if sag is None else sag
        self.c = base + self.n * self.hc + np.array([0.0, 0.0, -R * sag])
        self.tip = base + self.n * self.top + np.array([0.0, 0.0, -R * sag * 0.6])
        self.hs = max(self.hc + C * (0.15 if kind == "blister" else 0.3), self.floor + 0.002)
        if lift is not None:
            self.hs = max(self.hs, hi + lift / 100.0)
        self.Rs = max(R * (1.15 if kind == "blister" else 1.35), (self.hs - self.floor + FOOT) * SLOPE)
        self.head = (0.24 if kind == "boil" else 0.0) if head is None else head
        self.hue = rng.uniform()
        self.pus = PUS[kind] * rng.uniform(0.75, 1.0)
        self.phase = rng.uniform(0, 2 * math.pi, 3)
        t1, t2 = self.frame[0], self.frame[1]
        self.lobes = []
        for _ in range(lobes):
            a = rng.uniform(0, 2 * math.pi)
            self.lobes.append((self.c + (t1 * math.cos(a) + t2 * math.sin(a)) * R * 0.72 - self.n * C * 0.3,
                               R * rng.uniform(0.48, 0.62)))
        self.reach = max(self.Rs * 2.4, R * 2.2) + 0.006

    def near(self, P):
        return np.linalg.norm(P - self.base, axis=1) < self.reach

    def lateral(self, P):
        q = P - self.base
        along = q @ self.n
        return np.linalg.norm(q - along[:, None] * self.n, axis=1), along

    def skirt(self, P, wob):
        """The height (above the stand-in) of the flared flesh around the head."""
        rho, _ = self.lateral(P)
        s = np.exp(-1.6 * (rho / self.Rs) ** 2)
        f0 = np.minimum(self.site.floor(P), self.floor) - FOOT  # follows the floor down where the body falls away
        return f0 + (self.hs - f0) * s * (1.0 + 0.1 * wob)

    def sdf(self, P, wob, fine):
        R = self.R
        d = sd_ellipsoid(P, self.c, self.radii, self.frame)
        for c, r in self.lobes:
            d = smin(d, sd_sphere(P, c, r), R * 0.28)
        if self.head:
            # A pointed pus head on top
            d = smin(d, sd_sphere(P, self.tip - self.n * R * self.head * 0.85, R * self.head), R * 0.16)
        if self.kind == "slack":
            d = d + fine * R * 0.11 + wob * R * 0.07
        else:
            d = d + wob * R * 0.06 + fine * R * 0.012
        if self.kind == "crater":
            # Burst: a ragged, swollen rim around a pit
            q = P - self.tip
            ang = np.arctan2(q @ self.frame[1], q @ self.frame[0])
            ragged = 1.0 + 0.18 * np.sin(3 * ang + self.phase[0]) + 0.1 * np.sin(7 * ang + self.phase[1])
            rim = sd_torus(P, self.tip - self.n * R * 0.3, self.n, R * 0.62, R * 0.2 * ragged)
            d = smin(d, rim, R * 0.15)
            d = smax(d, -sd_sphere(P, self.tip + self.n * R * 0.12, R * 0.58), R * 0.1)
        return d


class Drip:
    """Pus weeping down from a mound: a narrow, meandering ridge running down the body that sinks into the clothes,
    so it shows for a cm or two where they lie high and further where they lie low."""

    def __init__(self, site, mound, length, width, seed, fall=0.06):
        rng = np.random.default_rng(seed)
        m = mound
        g = np.array([0.0, 0.0, -1.0])
        self.d = unit(g - (g @ m.n) * m.n + np.array([rng.uniform(-0.15, 0.15), 0.0, 0.0]))
        self.h = unit(np.cross(m.n, self.d))
        self.s0 = m.base + self.d * m.R * 0.85
        self.length, self.w, self.fall = length / 100.0, width / 100.0, fall
        self.amp = rng.uniform(0.15, 0.3) * self.w * 2.5
        self.k, self.phase = rng.uniform(80.0, 140.0), rng.uniform(0, 2 * math.pi)
        lo, hi = site.low(self.s0[None])[0], site.high(self.s0[None])[0]
        self.floor = lo - MARGIN
        self.rise = 0.011  # its crest starts this far above the lowest clothes and sinks along the trail: it only
        # shows where the clothes lie low, as a tall fin would stand out of the others
        self.site = site
        self.reach = self.length + 0.03

    def frame(self, P):
        q = P - self.s0
        along = q @ self.d
        side = q @ self.h - self.amp * np.sin(along * self.k + self.phase)
        return along, side

    def cross(self, P):
        along, side = self.frame(P)
        w = self.w * (1.0 + 0.35 * np.sin(along * 210.0 + self.phase)) * (1.0 - 0.4 * np.clip(along / self.length, 0, 1))
        return (np.exp(-(side / w) ** 2) * smooth01(-0.008, 0.002, along)
                * (1.0 - smooth01(self.length * 0.7, self.length, along))), along

    def profile(self, P):
        c, along = self.cross(P)
        return c * np.exp(-np.maximum(along, 0.0) / self.fall)

    def height(self, P):
        c, along = self.cross(P)
        lo = self.site.low(P)
        crest = lo + self.rise * np.exp(-np.maximum(along, 0.0) / self.fall) - 0.001
        f0 = lo - MARGIN - FOOT
        return f0 + (crest - f0) * c

    def near(self, P):
        return np.linalg.norm(P - self.s0, axis=1) < self.reach

    def region(self, P):
        along, side = self.frame(P)
        return np.maximum(np.abs(side) - self.w * 3.0, np.maximum(-along - 0.012, along - self.length - 0.004))


class Cluster:
    """The mounds of one part, meshed together: their skirts merge into swollen flesh where they crowd."""

    def __init__(self, site, mounds, seed, drips=()):
        self.site, self.mounds, self.seed, self.drips = site, mounds, seed, list(drips)

    def noise(self, P):
        return waves(P, 0.022, self.seed, 2), waves(P, 0.0065, self.seed + 1, 2)

    def height(self, P, wob):
        H = self.site.floor(P) - FOOT
        for m in self.mounds:
            k = m.near(P)
            if k.any():
                H[k] = smax(H[k], m.skirt(P[k], wob[k]), 0.004)
        for dr in self.drips:
            k = dr.near(P)
            if k.any():
                H[k] = smax(H[k], dr.height(P[k]), 0.002)
        return H

    def field(self, P):
        wob, fine = self.noise(P)
        d = body(P) - self.height(P, wob)
        for m in self.mounds:
            k = m.near(P)
            if k.any():
                d[k] = smin(d[k], m.sdf(P[k], wob[k], fine[k]), m.R * 0.32)
        return d

    def ground(self, P):
        """Height above this part's floor."""
        return body(P) - self.site.floor(P)

    def region(self, P):
        r = np.full(len(P), 1.0)
        for m in self.mounds:
            r = np.minimum(r, np.linalg.norm(P - m.base, axis=1) - m.Rs * 1.5)
        for dr in self.drips:
            r = np.minimum(r, dr.region(P))
        return r

    def box(self):
        B = np.array([m.base for m in self.mounds])
        Rs = np.array([m.Rs for m in self.mounds])[:, None]
        tops = np.array([m.tip + m.n * m.R * 0.4 for m in self.mounds])
        lo = np.minimum((B - Rs * 1.7).min(0), tops.min(0)) - 0.01
        hi = np.maximum((B + Rs * 1.7).max(0), tops.max(0)) + 0.01
        for dr in self.drips:
            end = dr.s0 + dr.d * dr.length
            lo = np.minimum(lo, end - 0.015)
            hi = np.maximum(hi, end + 0.015)
        return lo, hi

    def mesh(self, name, material, tris, h=0.0022):
        lo, hi = self.box()

        def keep(P):
            k = smooth01(0.004, 0.018, self.ground(P))
            for dr in self.drips:
                near = dr.near(P)
                if near.any():
                    k[near] = np.maximum(k[near], 0.8 * dr.profile(P[near]))
            return k

        obj = field_mesh(name, self.field, lo, hi, h, material, tris, keep=keep, region=self.region, inner=-0.008,
                         cut=-0.002, ground=self.ground, crumbs=0.003)
        self.paint(obj)
        return obj

    def paint(self, obj):
        """The per-vertex masks the material reads."""
        P = mesh_verts(obj)
        wob, fine = self.noise(P)
        lo, hi = self.site.low(P), self.site.high(P)
        put(obj, "h01", np.clip((body(P) - lo) / (hi - lo + 0.006), 0.0, 1.0))
        M = len(self.mounds)
        heads = np.full((M, len(P)), 1.0)
        skirts = np.full((M, len(P)), -1.0)
        for i, m in enumerate(self.mounds):
            k = m.near(P)
            if k.any():
                heads[i, k] = m.sdf(P[k], wob[k], fine[k])
                skirts[i, k] = m.skirt(P[k], wob[k])
        dh = heads.min(0)
        dome = 1.0 - smooth01(0.0008, 0.0045, dh)
        reach = np.zeros(len(P))
        for m in self.mounds:
            k = m.near(P)
            if k.any():
                rho, _ = m.lateral(P[k])
                reach[k] = np.maximum(reach[k], np.exp(-1.6 * (rho / m.Rs) ** 2) * min(1.0, m.R / 0.008))
        put(obj, "outer", 1.0 - reach)
        owner = np.where(dome > 0.5, heads.argmin(0), skirts.argmax(0))
        tip, pus, burst, hue = (np.zeros(len(P)) for _ in range(4))
        near, drip, rim = np.zeros(len(P)), np.zeros(len(P)), np.zeros(len(P))
        for i, m in enumerate(self.mounds):
            sel = owner == i
            if sel.any():
                rho, along = m.lateral(P[sel])
                tip[sel] = np.clip((along - m.floor) / max(m.top - m.floor, 1e-3), 0.0, 1.0)
                pus[sel] = m.pus
                hue[sel] = m.hue
                if m.kind == "crater":
                    burst[sel] = smooth01(m.R * 0.6, m.R * 0.42, rho) * smooth01(m.top - m.C * 0.9, m.top - m.C * 0.5,
                                                                               along)
                    rim[sel] = np.exp(-((rho - m.R * 0.62) / (m.R * 0.25)) ** 2) * smooth01(
                        m.top - m.C * 0.9, m.top - m.C * 0.4, along)
            if m.kind in ("sac", "slack"):
                d = np.linalg.norm(P - m.base, axis=1)
                near = np.maximum(near, np.exp(-(np.maximum(d - m.R, 0.0) / (m.R * 1.3)) ** 2))
            if m.weep:
                # Pus weeping down its flanks
                src = m.c
                drop = src[2] - P[:, 2]
                side = np.abs((P - src) @ unit(np.cross((0.0, 0.0, 1.0), m.n) + 1e-9))
                drip = np.maximum(drip, m.weep * smooth01(-0.006, 0.004, drop) * np.exp(-np.maximum(drop, 0) / 0.04)
                                  * np.exp(-(side / (m.R * 0.8)) ** 2))
        for dr in self.drips:
            k = dr.near(P)
            if k.any():
                drip[k] = np.maximum(drip[k], smooth01(0.05, 0.4, dr.profile(P[k])))
        put(obj, "dome", dome)
        put(obj, "tip", tip)
        put(obj, "pus", pus)
        put(obj, "burst", burst)
        put(obj, "rim", rim)
        put(obj, "hue", hue)
        put(obj, "near", near)
        put(obj, "drip", drip)


def scatter(site, avoid, center, r0, r1, count, seed, rmin=0.4, rmax=0.8, rise=(0.45, -0.7), bounds=None,
            kinds=(("boil", 0.45), ("blister", 0.35), ("crater", 0.2)), stretch=1.0, angle=0.0):
    """Lone boils, blisters and small burst ones around a cluster, between r0 and r1 cm from `center` (u, v):
    smaller, lower and fewer of them the farther out, so they thin out into the clothes; the outer ones only break
    the surface where a zombie's clothes lie low. `stretch` draws the ring out into an ellipse along `angle` (degrees
    from u toward v), so the cluster trails off one way."""
    rng = np.random.default_rng(seed)
    out = []
    names, weights = zip(*kinds)
    weights = np.array(weights) / sum(weights)
    for _ in range(count * 80):
        if len(out) >= count:
            break
        a = rng.uniform(0, 2 * math.pi)
        r = r0 + (r1 - r0) * math.sqrt(rng.uniform())
        x, y = r * math.cos(a) * stretch, r * math.sin(a) / stretch
        ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        u, v = center[0] + x * ca - y * sa, center[1] + x * sa + y * ca
        if bounds and not (bounds[0] <= u <= bounds[1] and bounds[2] <= v <= bounds[3]):
            continue
        t = (r - r0) / max(r1 - r0, 1e-6)
        R = rng.uniform(rmin, rmax) * (1.0 - 0.3 * t)
        base, _ = site.at(u, v)
        q = float(np.clip(1.0 - 0.8 * t, 0.2, 1.0))
        spread = site.high(base[None])[0] - site.low(base[None])[0]
        if spread * q > SPREAD * 0.7 or spread > 0.045:
            continue  # it would stand tall on whichever zombie's clothes lie lowest here
        if any(np.linalg.norm(base - m.base) < (m.R + R / 100.0) * 1.5 + 0.004 for m in avoid + out):
            continue
        kind = names[rng.choice(len(names), p=weights)]
        if kind == "crater":
            R = max(R, 0.65)
        out.append(Mound(site, u, v, R, rise[0] + (rise[1] - rise[0]) * t + rng.uniform(-0.25, 0.25),
                         seed * 100 + len(out), kind=kind, q=q,
                         head=rng.uniform(0.18, 0.3) if kind == "boil" else None))
    return out


def pustule_material(name):
    """Dead flesh bruised purple and sickly yellow-green, inflamed red toward the sacs, veined, with small pimples;
    down where it meets the zombie's clothes, a ragged band of torn, soaked fabric. The heads are skin stretched thin
    and veined over dark mustard and olive pus with small creamy tips; the burst ones a swollen rim around a crusted,
    bloody pit; pus weeps down from them in glossy trails. Kept as dark and dirty as the zombies: the game's shader
    shows pale or saturated colors much brighter."""
    mat, g = tk.new_material(name)
    h01 = attr(g, "h01")
    tip = attr(g, "tip")
    dome = attr(g, "dome")
    pus = attr(g, "pus")
    burst = attr(g, "burst")
    rim = attr(g, "rim")
    hue = attr(g, "hue")
    near = attr(g, "near")
    drip = attr(g, "drip")
    outer = attr(g, "outer")
    co = g.coords()

    # Flesh around the growths: mottled dead skin, purple and yellow-green bruising, inflamed toward the sacs
    mott = g.noise(14.0, detail=6.0, roughness=0.62)
    skin = g.mix(g.ramp(mott, 0.3, 0.72), (0.036, 0.02, 0.016), (0.021, 0.013, 0.011))
    blot = g.ramp(g.noise(6.0, detail=4.0, distortion=0.5), 0.42, 0.66)
    skin = g.mix(g.math("MULTIPLY", blot, 0.9), skin, (0.03, 0.009, 0.017))
    sick = g.ramp(g.noise(4.5, detail=3.0, distortion=0.8), 0.6, 0.75)
    skin = g.mix(g.math("MULTIPLY", sick, 0.7), skin, (0.034, 0.031, 0.011))
    hot = g.math("MULTIPLY", g.ramp(near, 0.1, 0.7), g.ramp(g.noise(11.0, detail=5.0), 0.25, 0.6))
    skin = g.mix(g.math("MULTIPLY", hot, 0.85), skin, (0.06, 0.012, 0.009))
    big = veins(g, 9.0, 0.035, warp_amount=1.5, broken=0.5)
    small = veins(g, 26.0, 0.04, warp_amount=1.5, broken=0.65)
    vmask = g.math("MAXIMUM", g.math("MULTIPLY", big, 0.9), g.math("MULTIPLY", small, g.math("MULTIPLY", near, 0.9)))
    skin = g.mix(vmask, skin, (0.016, 0.004, 0.01))
    vor = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(vor, "Scale", 95.0)
    g._in(vor, "Randomness", 0.9)
    g.links.new(co, vor.inputs["Vector"])
    dist = tk._sock(vor.outputs, "Distance")
    pick = g.ramp(g.noise(30.0, detail=2.0), 0.48, 0.56)
    pimple = g.math("MULTIPLY", g.ramp(dist, 0.32, 0.05), g.math("MULTIPLY", pick, g.ramp(near, 0.0, 0.4)))
    skin = g.mix(g.math("MULTIPLY", pimple, 0.85), skin, (0.05, 0.012, 0.009))
    skin = g.mix(g.math("MULTIPLY", g.ramp(dist, 0.12, 0.04), pimple), skin, (0.1, 0.075, 0.024))

    # Torn, soaked clothes low down: a ragged tear line, dark wet weave stained with pus and blood below it
    edge = g.math("ADD", h01, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(7.0, detail=3.0), 0.5), 0.9))
    edge = g.math("ADD", edge, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(45.0, detail=2.0), 0.5), 0.35))
    cloth = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(edge, 0.26, 0.34)),
                   g.math("SUBTRACT", 1.0, g.ramp(drip, 0.2, 0.6)))
    wx = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
    g._in(wx, "Scale", 420.0)
    g._in(wx, "Distortion", 0.6)
    g.links.new(co, wx.inputs["Vector"])
    wz = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    g._in(wz, "Scale", 420.0)
    g._in(wz, "Distortion", 0.6)
    g.links.new(co, wz.inputs["Vector"])
    weave = g.math("MULTIPLY", tk._sock(wx.outputs, "Fac"), tk._sock(wz.outputs, "Fac"))
    fabric = g.mix(g.ramp(g.noise(16.0, detail=4.0), 0.3, 0.7), (0.02, 0.017, 0.014), (0.011, 0.009, 0.008))
    fabric = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=3.0, distortion=0.6), 0.55, 0.7), 0.8), fabric,
                   (0.03, 0.021, 0.007))
    fabric = g.mix(g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=3.0), 0.6, 0.72), 0.8), fabric, (0.03, 0.006, 0.005))
    fabric = g.mix(g.math("MULTIPLY", weave, 0.25), fabric, (0.012, 0.01, 0.008))
    # Wet, dark seep just above the tear, and all down the outer flanks, where any zombie's clothes cut them
    seep = g.math("MULTIPLY", g.ramp(edge, 0.3, 0.55), g.math("SUBTRACT", 1.0, g.ramp(edge, 0.55, 0.85)))
    flank = g.ramp(g.math("ADD", outer, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(8.0, detail=4.0), 0.5), 0.6)),
                   0.3, 0.62)
    seep = g.math("MAXIMUM", g.math("MULTIPLY", seep, 0.75), g.math("MULTIPLY", flank, 0.9))
    skin = g.mix(seep, skin, (0.018, 0.009, 0.008))
    skin = g.mix(cloth, skin, fabric)

    # The heads: stretched, veined skin over pus
    flesh = g.mix(g.ramp(g.noise(12.0, detail=4.0), 0.3, 0.7), (0.05, 0.014, 0.01), (0.03, 0.01, 0.011))
    yellow = g.mix(g.ramp(hue, 0.0, 0.5), (0.085, 0.055, 0.011), (0.054, 0.052, 0.011))
    yellow = g.mix(g.ramp(hue, 0.62, 1.0), yellow, (0.07, 0.034, 0.011))
    pusc = g.mix(g.ramp(g.noise(6.0, detail=4.0, distortion=0.4), 0.3, 0.72), yellow, (0.032, 0.026, 0.007))
    pusc = g.mix(g.math("MULTIPLY", g.ramp(g.noise(18.0, detail=4.0), 0.5, 0.75), 0.6), pusc, (0.024, 0.02, 0.006))
    thin = g.math("MULTIPLY", g.ramp(g.math("ADD", tip, g.math("MULTIPLY", g.math(
        "SUBTRACT", g.noise(9.0, detail=3.0), 0.5), 0.35)), 0.45, 0.88), pus)
    headc = g.mix(thin, flesh, pusc)
    cap = veins(g, 34.0, 0.06, warp_amount=1.5, broken=0.35)
    cap = g.math("MULTIPLY", cap, g.math("SUBTRACT", 1.0, g.ramp(tip, 0.8, 0.97)))
    headc = g.mix(g.math("MULTIPLY", cap, 0.9), headc, (0.03, 0.004, 0.007))
    crown = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(tip, 0.92, 0.99), pus),
                   g.ramp(g.noise(25.0, detail=3.0), 0.3, 0.5))
    headc = g.mix(crown, headc, (0.13, 0.1, 0.034))
    # Burst: crusted yellow-brown rim, a black-red pit with pus left in it
    rimc = g.mix(g.ramp(g.noise(35.0, detail=5.0), 0.35, 0.65), (0.08, 0.05, 0.014), (0.04, 0.02, 0.008))
    headc = g.mix(g.math("MULTIPLY", rim, 0.85), headc, rimc)
    crater = g.mix(g.ramp(g.noise(40.0, detail=5.0), 0.45, 0.65), (0.022, 0.005, 0.004), (0.009, 0.004, 0.003))
    crater = g.mix(g.math("MULTIPLY", g.ramp(g.noise(15.0, detail=3.0), 0.55, 0.7), 0.8), crater, (0.07, 0.045, 0.01))
    headc = g.mix(burst, headc, crater)
    col = g.mix(dome, skin, headc)

    # Pus weeping down in glossy trails, and dried crust around them
    m = g.node("ShaderNodeMapping")
    g.links.new(co, m.inputs["Vector"])
    m.inputs["Scale"].default_value = (30.0, 30.0, 2.5)
    streak = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=3.0, vector=m.outputs[0]), 0.5, 0.64),
                    g.ramp(drip, 0.05, 0.4))
    streak = g.math("MAXIMUM", streak, g.ramp(drip, 0.5, 0.9))
    trail = g.mix(g.ramp(g.noise(20.0, detail=3.0), 0.35, 0.65), (0.062, 0.043, 0.01), (0.035, 0.016, 0.007))
    col = g.mix(g.math("MULTIPLY", streak, 0.9), col, trail)
    crust = g.math("MULTIPLY", g.ramp(g.noise(26.0, detail=6.0), 0.58, 0.68),
                   g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(near, 0.2, 0.6), 0.6), g.ramp(drip, 0.05, 0.3)))
    crust = g.math("MAXIMUM", g.math("MULTIPLY", crust, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", dome, 0.7))),
                   g.math("MULTIPLY", rim, g.ramp(g.noise(30.0, detail=5.0), 0.45, 0.6)))
    col = g.mix(crust, col, (0.05, 0.031, 0.009))
    cav = g.cavity(0.02)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 0.8), col, (0.01, 0.005, 0.004))

    rough = g.mixf(g.ramp(near, 0.2, 0.8), 0.44, 0.34)
    rough = g.mixf(seep, rough, 0.3)
    rough = g.mixf(cloth, rough, 0.4)
    rough = g.mixf(dome, rough, g.math("ADD", 0.28, g.math("MULTIPLY", g.noise(14.0, detail=3.0), 0.14)))
    rough = g.mixf(crown, rough, 0.45)
    rough = g.mixf(g.math("MAXIMUM", crust, g.math("MULTIPLY", burst, 0.8)), rough, 0.62)
    rough = g.mixf(streak, rough, 0.24)
    height = g.math("MULTIPLY", g.noise(170.0, detail=4.0), 0.22)
    height = g.math("ADD", height, g.math("MULTIPLY", big, g.math("SUBTRACT", 0.55, g.math("MULTIPLY", dome, 0.3))))
    height = g.math("ADD", height, g.math("MULTIPLY", cap, 0.45))
    height = g.math("ADD", height, g.math("MULTIPLY", pimple, 0.9))
    height = g.math("ADD", height, g.math("MULTIPLY", crust, 0.6))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("MAXIMUM", burst, rim), g.noise(45.0, detail=5.0)))
    height = g.math("ADD", height, g.math("MULTIPLY", streak, 0.25))
    height = g.math("ADD", height, g.math("MULTIPLY", cloth, g.math("MULTIPLY", weave, 0.5)))
    col = tk.grade(g, col, sat=0.85, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.002))


tk.reset_scene()
zk.stage()
zk.body()
material = pustule_material("Pustule")

# ---- the sites, with the clothes' levels measured on vanilla Joe, the fat cop and the nurse
B = 0.6  # back start points sit behind the back; Site pulls them onto it
BACK1 = Site((-0.03, B, 1.375), (0.0, -1.0, 0.0),
             low=(-1.095, 0.132, -0.036, 0.0151, -0.0376, 0.0008), high=(-0.090, 0.139, 0.005, 0.0231, 0.0122, 0.0064))
BACK2 = Site((0.05, B, 1.35), (0.0, -1.0, 0.0),
             low=(-1.432, -0.170, 0.084, 0.0205, -0.0245, 0.0073), high=(0.429, -0.194, -0.031, 0.0203, 0.0129, -0.0089))
SHOULDER1 = Site(*limb_start("LeftArm", "LeftForeArm", 0.1, 30),
                 low=(0.924, 0.204, -0.050, -0.0031, -0.0107, -0.0181), high=(2.582, 0.263, 0.002, -0.005, 0.002, -0.0013))
SHOULDER2 = Site(*limb_start("RightArm", "RightForeArm", 0.12, 50),
                 low=(0.626, -0.215, -0.093, -0.0019, -0.0018, -0.0032),
                 high=(2.994, -0.424, -0.244, -0.0041, -0.003, -0.0088))
ARM = Site(*limb_start("LeftArm", "LeftForeArm", 0.58, 25),
           low=(-1.025, 0.247, -0.014, -0.0106, -0.003, 0.0157), high=(1.360, 0.248, -0.048, 0.0166, 0.0005, -0.0053))
FOREARM = Site(*limb_start("RightForeArm", "RightHand", 0.55, 20),
               low=(-1.941, -0.138, 0.049, 0.0255, 0.0013, 0.0102), high=(0.716, -0.215, 0.147, 0.0103, 0.0022, 0.0169))

# ---- upper back, right of the spine (u runs to the zombie's right, v up): one big sagging, lobed sac weeping a long
# trail, two smaller sacs, a half-drained one, a burst crater, a knot of boils above, flat blisters, lone boils
# thinning out
S = BACK1
back1 = [
    Mound(S, 2.6, -0.3, 3.0, 2.6, 101, "sac", lobes=2, sag=0.22, weep=1.0, lift=0.7),
    Mound(S, 6.9, 1.7, 1.7, 1.6, 102, "sac", sag=0.15, lift=0.5),
    Mound(S, -0.9, 2.6, 1.3, 1.2, 103, "sac", sag=0.1, lift=0.4),
    Mound(S, 6.4, -3.5, 1.5, 0.7, 104, "slack", lift=0.3),
    Mound(S, -0.2, -3.4, 1.3, 0.6, 105, "crater", weep=0.8, lift=0.3),
    Mound(S, 5.2, 3.0, 0.75, 0.6, 106, "boil", head=0.25),
    Mound(S, 6.4, 3.4, 0.55, 0.45, 107, "boil", head=0.31),
    Mound(S, 4.4, 4.0, 0.5, 0.4, 108, "boil"),
    Mound(S, -1.8, -0.4, 0.9, 0.25, 109, "blister"),
    Mound(S, 3.6, -4.7, 0.7, 0.2, 110, "blister"),
    Mound(S, 8.8, -1.2, 0.8, 0.6, 111, "boil", head=0.20),
]
back1 += scatter(S, back1, (3.0, 0.0), 5.5, 9.0, 8, 120, rmin=0.4, rmax=0.9, bounds=(-3.0, 10.5, -7.5, 3.5),
                 stretch=1.45, angle=-35.0)
back1_drips = [Drip(S, back1[0], 7.0, 0.45, 131), Drip(S, back1[4], 4.5, 0.32, 132)]

# ---- upper back, left of the spine and lower (u runs toward the spine): a big burst boil weeping, a tight knot of
# boils, a lone sac, a blister
S = BACK2
back2 = [
    Mound(S, -1.5, 1.2, 2.0, 1.0, 201, "crater", elong=0.9, weep=1.0, lift=0.5),
    Mound(S, 1.6, -1.8, 0.9, 0.8, 202, "boil", head=0.26, lift=0.2),
    Mound(S, 2.6, -0.5, 0.7, 0.6, 203, "boil"),
    Mound(S, 0.6, -2.9, 0.8, 0.7, 204, "boil", head=0.23),
    Mound(S, 2.0, -3.2, 0.55, 0.5, 205, "boil", head=0.33),
    Mound(S, -0.3, -1.3, 0.6, 0.5, 206, "boil"),
    Mound(S, -4.6, 2.0, 1.3, 1.1, 207, "sac", head=0.25, lift=0.3),
    Mound(S, 0.8, 3.6, 1.0, 0.25, 208, "blister"),
]
back2 += scatter(S, back1 + back2, (-0.5, 0.5), 4.5, 8.0, 6, 220, rmin=0.4, rmax=0.85, bounds=(-7.0, 2.8, -6.0, 4.5),
                 stretch=1.5, angle=100.0)
back2_drips = [Drip(S, back2[0], 6.0, 0.42, 231)]

# ---- top of the left shoulder (u runs toward the back, v up toward the neck)
S = SHOULDER1
shoulder1 = [
    Mound(S, 0.2, -0.3, 2.1, 1.6, 301, "sac", lobes=1, sag=0.12, lift=0.5),
    Mound(S, 3.0, 2.0, 1.2, 0.5, 302, "crater", weep=0.8, lift=0.2),
    Mound(S, -2.3, 1.3, 0.8, 0.6, 303, "boil", head=0.26),
    Mound(S, 2.2, -2.8, 0.85, 0.2, 304, "blister"),
    Mound(S, -1.2, -2.8, 0.6, 0.45, 305, "boil", head=0.29),
]
shoulder1 += scatter(S, shoulder1, (0.5, 0.0), 3.6, 6.5, 5, 320, rmin=0.4, rmax=0.8, stretch=1.4, angle=20.0)

# ---- back of the right shoulder (u runs toward the front): a slack, half-drained sac, a tight trio of boils, a
# lone boil, a small burst one
S = SHOULDER2
shoulder2 = [
    Mound(S, 1.8, 0.4, 2.0, 0.9, 401, "slack", lift=0.5),
    Mound(S, 4.8, 1.9, 0.65, 0.5, 402, "boil", head=0.26),
    Mound(S, 5.6, 0.7, 0.55, 0.4, 403, "boil"),
    Mound(S, 5.4, 2.9, 0.48, 0.35, 404, "boil", head=0.33),
    Mound(S, 2.0, -3.6, 0.9, 0.7, 405, "boil", head=0.23),
    Mound(S, -0.6, 2.8, 1.0, 0.35, 406, "crater", weep=0.7),
]
shoulder2 += scatter(S, shoulder2, (2.0, 0.0), 3.8, 6.5, 4, 420, rmin=0.4, rmax=0.8, bounds=(-1.5, 7.0, -7.0, 6.5),
                     stretch=1.4, angle=-80.0)

# ---- outside of the left upper arm (v runs up the arm)
S = ARM
arm = [
    Mound(S, 0.0, 1.2, 1.5, 1.1, 501, "sac", lobes=1, sag=0.15, lift=0.4),
    Mound(S, 0.7, -2.0, 0.85, 0.6, 502, "boil", head=0.26),
    Mound(S, -0.6, -4.0, 0.95, 0.35, 503, "crater", weep=0.8),
    Mound(S, -1.6, 3.4, 0.75, 0.15, 504, "blister"),
]
arm += scatter(S, arm, (0.0, 0.0), 3.2, 5.8, 4, 520, rmin=0.4, rmax=0.75, stretch=1.5, angle=90.0)
arm_drips = [Drip(S, arm[2], 3.5, 0.3, 531)]

# ---- top of the right forearm
S = FOREARM
forearm = [
    Mound(S, 0.0, 0.8, 1.25, 0.9, 601, "crater", weep=0.8, lift=0.35),
    Mound(S, 1.7, -1.3, 0.8, 0.8, 602, "boil", head=0.26),
    Mound(S, -1.3, -1.7, 0.6, 0.6, 603, "boil"),
    Mound(S, -0.9, 3.0, 0.8, 0.45, 604, "blister"),
]
forearm += scatter(S, forearm, (0.0, 0.0), 3.0, 5.2, 3, 620, rmin=0.4, rmax=0.7, stretch=1.4, angle=80.0)

for _m in back1 + back2 + shoulder1 + shoulder2 + arm + forearm:
    _s = _m.site.high(_m.base[None])[0] - _m.site.low(_m.base[None])[0]
    if _s * _m.q > SPREAD + 0.004:
        print("[pustules] note: mound %d stands where the clothes' levels differ by %.1f cm" % (_m.seed, _s * 100))

PARTS = [
    ("PustulesBack1", "Spine2", "BackVar1", Cluster(BACK1, back1, 11, back1_drips), 1650),
    ("PustulesBack2", "Spine2", "BackVar2", Cluster(BACK2, back2, 21, back2_drips), 1150),
    ("PustulesShoulder1", "LeftArm", "ShoulderVar1", Cluster(SHOULDER1, shoulder1, 31), 850),
    ("PustulesShoulder2", "RightArm", "ShoulderVar2", Cluster(SHOULDER2, shoulder2, 41), 850),
    ("PustulesArm", "LeftArm", "ArmVar", Cluster(ARM, arm, 51, arm_drips), 750),
    ("PustulesForeArm", "RightForeArm", "ArmVar2", Cluster(FOREARM, forearm, 61), 600),
]
pieces = []
for name, bone, piece, cluster, tris in PARTS:
    obj = cluster.mesh(name, material, tris)
    zk.on(obj, bone, piece)
    pieces.append(obj)
    V = mesh_verts(obj)
    print("[pustules] %s#%s: %d mounds, %d tris, bounds %s .. %s" % (
        bone, piece, len(cluster.mounds), sum(len(f.vertices) - 2 for f in obj.data.polygons), np.round(V.min(0), 3),
        np.round(V.max(0), 3)))
parts = zk.export("Pustules", pieces, ASSETS)
zk.previews("pustules", PREVIEWS, Vector((0.0, 0.12, 1.38)), distance=1.5)
preview("pustules_close_back", (0.1, 0.9, 1.47), (0.0, 0.2, 1.37), lens=60)
preview("pustules_close_left", (0.8, 0.65, 1.6), (0.27, 0.1, 1.42), lens=55)
preview("pustules_close_right", (-0.85, 0.45, 1.5), (-0.33, 0.1, 1.33), lens=50)
print("[pustules] done")
