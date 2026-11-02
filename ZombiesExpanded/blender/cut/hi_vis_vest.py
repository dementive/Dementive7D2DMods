"""Hi-vis vest: a road crew's safety vest, worn open at the front. Fluorescent orange polyester knit, faded by the
sun and filthy: dirt ground in, mud splashed up the hem, grease smears, dried blood down the front. Two bands of
reflective tape round the body, one up each side of the front and over the shoulders, crossed in an X on the back;
the tape is cracked, peeling in places and dull with grime. Bound edges with the velcro tabs open, a ragged hem with
a rip up the left front, and holes torn through the back, the right chest and the left side.

The vest is one pattern piece wrapped round the chest and hips hit boxes (1.4 cm off them, more toward the open
front so a fuller chest pushes it out of the way rather than through it), the wide shoulder pieces laid over the
shoulders. It hangs loose: drape folds at the hem. One part on Spine2 ("Spine2#Vest").

    blender -b --factory-startup --python hi_vis_vest.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PIECE = "HiVisVest", "hi_vis_vest", "Spine2", "Vest"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex (u, z, edge) pattern coordinates (or a strap's across, along, side) the fabric prints by

# ---------------------------------------------------------------- the body: hit-box capsules

def _capsules():
    out = []
    for c in sk.colliders:
        if c["type"] != "capsule":
            continue
        ax = [0.0, 0.0, 0.0]
        ax[c["axis"]] = 1.0
        half = max(0.0, c["height"] / 2 - c["radius"])
        ctr = Vector(c["center"])
        a = sk.point(c["bone"], ctr - Vector(ax) * half)
        b = sk.point(c["bone"], ctr + Vector(ax) * half)
        out.append((c["bone"], np.array(a), np.array(b), c["radius"]))
    return out


CAPS = _capsules()


def sdf(P, bones=None):
    """Distance from points to the nearest hit box (negative inside)."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    d = np.full(len(P), 9.0)
    for bone, a, b, r in CAPS:
        if bones and bone not in bones:
            continue
        ba, pa = b - a, P - a
        h = np.clip(pa @ ba / max(ba @ ba, 1e-12), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(pa - h[:, None] * ba, axis=1) - r)
    return d


# ---------------------------------------------------------------- mesh helpers

def set_attr(obj, values, name=ATTR):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.array(values, np.float32).ravel())


def fix_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def bake_transform(obj):
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def place(obj, origin, x, y, z):
    """Moves an object built about the origin into the frame (origin, x, y, z axes) and bakes it in."""
    m = Matrix((Vector(x), Vector(y), Vector(z))).transposed().to_4x4()
    obj.data.transform(Matrix.Translation(Vector(origin)) @ m)
    return obj


FLAT = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
ROUND = [(-0.5, -0.3), (-0.35, -0.5), (0.35, -0.5), (0.5, -0.3), (0.5, 0.3), (0.35, 0.5), (-0.35, 0.5), (-0.5, 0.3)]


def band(name, pts, nrms, width, thick, mat, profile=FLAT, closed=False, widths=None, smooth_angle=50):
    """A strap swept along pts lying on a surface with outward normals nrms: `width` across, `thick` out. Writes the
    (across, along, outer side) coordinates to the strap's vertices."""
    P = [Vector(p) for p in pts]
    Nn = [Vector(n).normalized() for n in nrms]
    n = len(P)
    s = [0.0]
    for i in range(1, n):
        s.append(s[-1] + (P[i] - P[i - 1]).length)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        if closed:
            T = (P[(i + 1) % n] - P[i - 1]).normalized()
        else:
            T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        N = (Nn[i] - T * Nn[i].dot(T)).normalized()
        W = T.cross(N)
        w = widths[i] if widths is not None else width
        rings.append([bm.verts.new(P[i] + W * (a * w) + N * (b * thick)) for a, b in profile])
        vals += [(a * w, s[i], 1.0 if b > 0 else 0.0) for a, b in profile]
    k = len(profile)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((a[j], a[(j + 1) % k], b[(j + 1) % k], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, smooth_angle)


def tube(name, pts, radius, mat, sides=6, closed=False, radii=None):
    """A round bar or wire along a polyline."""
    P = [Vector(p) for p in pts]
    n = len(P)
    bm = bmesh.new()
    rings = []
    ref = None
    for i in range(n):
        if closed:
            T = (P[(i + 1) % n] - P[i - 1]).normalized()
        else:
            T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        if ref is None:
            ref = Vector((0, 0, 1)) if abs(T.z) < 0.9 else Vector((1, 0, 0))
        N = (ref - T * ref.dot(T)).normalized()
        ref = N
        B = T.cross(N)
        r = radii[i] if radii is not None else radius
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * j / sides) + B * math.sin(2 * math.pi * j / sides)) * r)
                      for j in range(sides)])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            bm.faces.new((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def superbox(name, half, mat, n=4.0, cuts=3, back_squash=1.0):
    """A soft box (a superellipsoid) about the origin: half sizes (x, y, z), edge softness n (higher is boxier); the
    -Y half squashed by back_squash for a flat back."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    a, b, c = half
    for v in bm.verts:
        d = v.co.normalized()
        s = (abs(d.x / a) ** n + abs(d.y / b) ** n + abs(d.z / c) ** n) ** (-1.0 / n)
        p = d * s
        if p.y < 0:
            p.y *= back_squash
        v.co = p
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def tri_count(objs):
    return sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)


# ---------------------------------------------------------------- material helpers

def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def voronoi(g, vec, scale, feature="F1", out="Distance"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, out)


def lines(g, vec, scale, rot, loc, width, seg=0.0):
    """Thin lines: contours of stretched noise, broken into short runs when seg (a noise scale) is given."""
    n = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, vec, scale, rot, loc))
    ln = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, width, False))
    if seg:
        ln = g.math("MULTIPLY", ln, g.ramp(g.noise(seg, detail=2.0, vector=mapping(g, vec, loc=loc)), 0.5, 0.58))
    return ln


def scratches(g, P, width=0.02):
    sc = None
    for i, (rot, scale) in enumerate((((0.3, 0.9, 0.2), (60.0, 60.0, 8.0)), ((1.1, 0.2, 1.4), (90.0, 90.0, 12.0)),
                                      ((0.5, 1.3, 2.7), (45.0, 45.0, 6.0)))):
        ln = lines(g, P, scale, rot, (0.13 * i, 0.31 * i, 0.07 * i), width, seg=14.0 + 6.0 * i)
        sc = ln if sc is None else g.math("MAXIMUM", sc, ln)
    return g.math("MULTIPLY", sc, g.ramp(g.noise(3.0, detail=3.0, vector=P), 0.4, 0.62))


def attr(g):
    a = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    a.attribute_type = "GEOMETRY"
    return g.separate(tk._sock(a.outputs, "Vector"))


def normal_z(g):
    return g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]


def grunge(g, P, col, rough, metal, height, dirt=0.6, dirt_cols=((0.035, 0.028, 0.02), (0.1, 0.08, 0.055)),
           dirt_range=(0.2, 0.06), grime=0.7, dust=0.3, specks=0.5, sawdust=0.0, blood=0.0, mud=0.0, mud_top=0.9):
    """The wear every prop gets: photo-patterned dirt and crease grime, dust and sawdust on top, dark specks, mud
    splashed up from below `mud_top` and blood (smears, drops and spatter)."""
    z = g.separate(g.coords())[2]
    p = tk.photo(g, "rust_coarse_01", 2.6, (0.31, 0.6, 0.17))
    dm = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1]), dirt)
    dm = g.math("MAXIMUM", dm, tk._grime(g, grime), clamp=True)
    col = g.mix(g.math("MULTIPLY", dm, 0.85), col, g.mix(g.noise(9.0, vector=P), dirt_cols[0], dirt_cols[1]))
    rough = g.mixf(dm, rough, 0.88)
    metal = g.mixf(dm, metal, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", dm, 0.15))
    up = normal_z(g)
    if mud:
        drops = g.math("MAXIMUM", g.ramp(voronoi(g, P, 55.0), 0.12, 0.05),
                       g.ramp(voronoi(g, mapping(g, P, loc=(2.1, 0.7, 1.3)), 24.0), 0.1, 0.04))
        cake = g.ramp(g.noise(6.0, detail=6.0, roughness=0.65, vector=P, distortion=0.6), 0.5, 0.62)
        low = g.ramp(z, mud_top, mud_top - 0.12)
        mm = g.math("MULTIPLY", g.math("MAXIMUM", g.math("MULTIPLY", drops, 0.9), cake), low)
        mm = g.math("MULTIPLY", mm, mud, clamp=True)
        col = g.mix(mm, col, g.mix(g.noise(25.0, vector=P), (0.06, 0.047, 0.033), (0.13, 0.105, 0.075)))
        rough = g.mixf(mm, rough, 0.93)
        metal = g.mixf(mm, metal, 0.0)
        height = g.math("ADD", height, g.math("MULTIPLY", mm, 0.5))
    if dust:
        du = g.math("MULTIPLY", g.ramp(up, 0.2, 0.9), g.ramp(g.noise(8.0, detail=6.0, roughness=0.6, vector=P), 0.35, 0.65))
        du = g.math("MULTIPLY", du, dust)
        col = g.mix(du, col, (0.3, 0.26, 0.2))
        rough = g.mixf(du, rough, 0.95)
        metal = g.mixf(du, metal, 0.0)
    if sawdust:
        flecks = g.math("MULTIPLY", g.ramp(voronoi(g, P, 260.0), 0.2, 0.09), g.ramp(g.noise(5.0, vector=P), 0.45, 0.62))
        flecks = g.math("MULTIPLY", g.math("MULTIPLY", flecks, g.ramp(up, -0.2, 0.6)), sawdust)
        col = g.mix(flecks, col, (0.42, 0.33, 0.2))
        rough = g.mixf(flecks, rough, 0.95)
    if specks:
        sp = g.math("MULTIPLY", g.ramp(voronoi(g, P, 150.0), 0.16, 0.07), g.ramp(g.noise(6.0, vector=P), 0.4, 0.62))
        col = g.mix(g.math("MULTIPLY", sp, specks), col, (0.022, 0.018, 0.014))
    if blood:
        reg = g.ramp(g.noise(1.6, detail=5.0, roughness=0.6, vector=P, distortion=0.6), 0.5, 0.64)
        drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 30.0), 0.15, 0.05),
                       g.ramp(g.noise(25.0, vector=P), 0.42, 0.6))
        smear = g.ramp(g.noise(9.0, detail=8.0, roughness=0.7, vector=P, distortion=1.5), 0.56, 0.64)
        bm_ = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", drops, smear), reg), blood, clamp=True)
        col = g.mix(bm_, col, g.mix(g.noise(20.0, vector=P), (0.045, 0.006, 0.004), (0.11, 0.012, 0.008)))
        rough = g.mixf(bm_, rough, 0.35)
        metal = g.mixf(bm_, metal, 0.0)
    return col, rough, metal, height


def seeded(g, seed):
    return mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))



def steel(name, base=(0.2, 0.2, 0.2), seed=0.0, rust=0.5, polish=0.5, blood=0.0):
    """Worn steel: dark, mottled, rusty in the creases and patches, rubbed bright on the edges."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    tone = g.noise(12.0, detail=4.0, vector=P)
    col = g.mix(g.math("MULTIPLY", tone, 0.6), base, tk._darker(g, base, 0.6))
    rough = g.math("ADD", 0.45, g.math("MULTIPLY", tone, 0.15))
    metal = 0.85
    height = g.math("MULTIPLY", g.noise(120.0, detail=4.0, vector=P), 0.2)
    rm = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=8.0, roughness=0.65, vector=P, distortion=0.4), 0.55, 0.68), rust)
    rm = g.math("MAXIMUM", rm, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.02), 0.4, 1.0)), rust))
    col = g.mix(rm, col, g.mix(g.noise(30.0, vector=P), (0.09, 0.035, 0.015), (0.22, 0.09, 0.035)))
    rough = g.mixf(rm, rough, 0.88)
    metal = g.mixf(rm, metal, 0.1)
    height = g.math("ADD", height, g.math("MULTIPLY", rm, g.noise(60.0, detail=6.0, vector=P)))
    edge = g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.05, 0.25), g.ramp(g.noise(25.0, vector=P), 0.3, 0.55))
    edge = g.math("MAXIMUM", g.math("MULTIPLY", edge, polish), g.math("MULTIPLY", scratches(g, P, 0.02), 0.6 * polish))
    col = g.mix(edge, col, (0.5, 0.49, 0.47))
    rough = g.mixf(edge, rough, 0.3)
    metal = g.mixf(edge, metal, 1.0)
    col, rough, metal, height = grunge(g, P, col, rough, metal, height, dirt=0.4, grime=0.8, dust=0.15, specks=0.4,
                                       blood=blood)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.002))


def plastic(name, base, seed=0.0, rough=0.42, scuff=0.5, edge_col=None, decals=None, dirt=0.6, blood=0.1, mud=0.3,
            sawdust=0.4):
    """Molded plastic or rubber: uneven tone, scratches and scuffs, worn edges, then the shared dirt."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    col = g.mix(g.math("MULTIPLY", g.noise(5.0, detail=3.0, vector=P), 0.5), base, tk._darker(g, base, 0.72))
    rgh = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(14.0, detail=3.0, vector=P), 0.5), 0.15))
    metal = 0.0
    height = g.math("MULTIPLY", g.noise(90.0, detail=6.0, roughness=0.6, vector=P), 0.12)
    if decals:
        col, rgh, metal, height = decals(g, P, col, rgh, metal, height)
    sc = g.math("MULTIPLY", scratches(g, P, 0.025), scuff)
    ec = edge_col or tuple(min(1.0, c * 1.6 + 0.06) for c in base)
    col = g.mix(g.math("MULTIPLY", sc, 0.8), col, ec)
    rgh = g.mixf(sc, rgh, 0.6)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.4))
    wm = g.math("MULTIPLY", g.ramp(g.edges(0.003), 0.06, 0.3), g.ramp(g.noise(30.0, vector=P), 0.36, 0.55))
    col = g.mix(g.math("MULTIPLY", wm, scuff), col, ec)
    rgh = g.mixf(wm, rgh, 0.55)
    col, rgh, metal, height = grunge(g, P, col, rgh, metal, height, dirt=dirt, grime=0.7, dust=0.3, specks=0.5,
                                     sawdust=sawdust, blood=blood, mud=mud, mud_top=0.86)
    return tk.finish(mat, g, col, metal, rgh, g.bump(height, 0.3, 0.0015))


def wood(name, base=(0.2, 0.11, 0.05), seed=0.0, blood=0.1):
    """A varnished hickory handle, the varnish worn off where it's held, dark with grime."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    grain = g.noise(1.0, detail=3.0, roughness=0.5, vector=mapping(g, P, (120.0, 120.0, 6.0)), distortion=1.5)
    col = g.mix(g.ramp(grain, 0.3, 0.7), base, tk._darker(g, base, 0.55))
    rough = g.math("ADD", 0.38, g.math("MULTIPLY", grain, 0.1))
    height = g.math("MULTIPLY", grain, 0.25)
    worn = g.ramp(g.noise(4.0, detail=5.0, vector=P, distortion=0.4), 0.5, 0.62)
    col = g.mix(worn, col, g.mix(g.ramp(grain, 0.3, 0.7), (0.3, 0.21, 0.13), (0.2, 0.13, 0.07)))
    rough = g.mixf(worn, rough, 0.7)
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.7, grime=0.9, dust=0.15, specks=0.5,
                                       blood=blood)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.0015))




def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the torso's envelope (as the kevlar vest)

AXIS = np.array([0.0, 0.05])  # the chest hit box's vertical axis (x, y)
R0 = 0.175  # pattern u (meters along the vest) to angle round the axis


def _ray_exit(theta, z):
    """Where a level ray from the chest axis at angle theta (0 = front, -Y; +90 = the zombie's left, +X) leaves the
    torso's vertical capsules (chest and hips)."""
    theta, z = np.broadcast_arrays(np.asarray(theta, float), np.asarray(z, float))
    dx, dy = np.sin(theta), -np.cos(theta)
    best = np.zeros(theta.shape)
    for bone, a, b, r in CAPS:
        if bone not in ("Spine2", "Hips"):
            continue
        za, zb = min(a[2], b[2]), max(a[2], b[2])
        dz = np.where(z > zb, z - zb, np.where(z < za, za - z, 0.0))
        rz2 = r * r - dz * dz
        wx, wy = AXIS[0] - a[0], AXIS[1] - a[1]
        wd = wx * dx + wy * dy
        disc = wd * wd - (wx * wx + wy * wy - rz2)
        t = np.where((rz2 > 0) & (disc > 0), -wd + np.sqrt(np.maximum(disc, 0.0)), 0.0)
        best = np.maximum(best, t)
    return best


def _upper_hull(x, y):
    hull = []
    for p in zip(x, y):
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) >= 0:
            hull.pop()
        hull.append(p)
    hx, hy = zip(*hull)
    return np.interp(x, hx, hy)


TH = np.linspace(-math.pi, math.pi, 361)
ZS = np.arange(0.96, 1.74, 0.005)
_T, _Z = np.meshgrid(TH, ZS, indexing="ij")
ENV = np.array([_upper_hull(ZS, row) for row in _ray_exit(_T, _Z)])  # taut: a vest hangs straight over hollows


def env(theta, z):
    theta = (np.asarray(theta, float) + math.pi) % (2 * math.pi) - math.pi
    fi = np.clip((theta + math.pi) / (2 * math.pi) * (len(TH) - 1), 0, len(TH) - 1.001)
    fj = np.clip((np.asarray(z, float) - ZS[0]) / 0.005, 0, len(ZS) - 1.001)
    i, j = fi.astype(int), fj.astype(int)
    a, b = fi - i, fj - j
    return ((ENV[i, j] * (1 - b) + ENV[i, j + 1] * b) * (1 - a) + (ENV[i + 1, j] * (1 - b) + ENV[i + 1, j + 1] * b) * a)


def squarish(theta, p=2.3):
    c, s = np.abs(np.cos(theta)), np.abs(np.sin(theta))
    return (c ** p + s ** p) ** (-1.0 / p)


CLEAR = 0.014


def clearance(theta, z):
    """Off the hit boxes: 1.4 cm, more toward the open front (a fuller chest pushes it aside) and at the loose hem."""
    tw = np.abs((np.asarray(theta, float) + math.pi) % (2 * math.pi) - math.pi)
    return CLEAR + 0.013 * smoothstep(math.radians(58), math.radians(16), tw) + 0.004 * smoothstep(1.17, 1.03, z)


def folds(u, z):
    """Drape folds: the knit hangs in soft vertical folds toward the hem (outward only)."""
    hang = smoothstep(1.36, 1.05, z)
    w = 0.5 + 0.3 * np.sin(u * 2 * math.pi / 0.13 + 1.3) + 0.2 * np.sin(u * 2 * math.pi / 0.072 + 0.4 + 9.0 * z)
    return 0.0075 * hang * np.clip(w, 0.0, 1.0)


def to3d(P):
    """Pattern (u, z) to the panel's inner face."""
    P = np.atleast_2d(P)
    u, z = P[:, 0], P[:, 1]
    th = u / R0
    r = env(th, z) * squarish(th) + clearance(th, z) + folds(u, z)
    return np.stack([AXIS[0] + r * np.sin(th), AXIS[1] - r * np.cos(th), z], axis=-1)


# ---------------------------------------------------------------- 2D pattern pieces (as the kevlar vest, with holes)

def _dense(poly, step=0.003):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = np.array(poly[i]), np.array(poly[(i + 1) % n])
        k = max(1, int(np.linalg.norm(b - a) / step))
        for t in range(k):
            out.append(a + (b - a) * t / k)
    return np.array(out)


def _smooth_closed(P, sigma_pts):
    k = max(1, int(3 * sigma_pts))
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / max(sigma_pts, 1e-3)) ** 2)
    w /= w.sum()
    out = np.zeros_like(P)
    for o, wt in zip(range(-k, k + 1), w):
        out += wt * np.roll(P, o, axis=0)
    return out


def _adaptive(P, step, angle):
    n = len(P)
    keep, cost = [0], 0.0
    for i in range(1, n):
        d0 = P[i] - P[i - 1]
        d1 = P[(i + 1) % n] - P[i]
        turn = abs(math.atan2(d0[0] * d1[1] - d0[1] * d1[0], d0 @ d1))
        cost += np.linalg.norm(d0) / step + turn / angle
        if cost >= 1.0:
            keep.append(i)
            cost = 0.0
    if np.linalg.norm(P[keep[-1]] - P[0]) < 0.4 * step:
        keep.pop()
    return P[keep]


def outline(poly, step=0.03, round_r=0.006, angle=math.radians(30)):
    D = _dense(poly)
    D = _smooth_closed(D, round_r / 0.003)
    O = _adaptive(D, step, angle)
    area = 0.5 * np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1])
    return O if area > 0 else O[::-1]


def _seg_dist(P, O):
    A, B = O, np.roll(O, -1, axis=0)
    AB = B - A
    AP = P[:, None, :] - A[None]
    t = np.clip(np.einsum("ijk,jk->ij", AP, AB) / np.maximum(np.einsum("jk,jk->j", AB, AB), 1e-12), 0, 1)
    return np.linalg.norm(AP - t[..., None] * AB[None], axis=2).min(axis=1)


def _inside(P, O):
    x, y = P[:, 0][:, None], P[:, 1][:, None]
    x1, y1 = O[:, 0][None], O[:, 1][None]
    x2, y2 = np.roll(O[:, 0], -1)[None], np.roll(O[:, 1], -1)[None]
    cond = (y1 > y) != (y2 > y)
    xi = x1 + (y - y1) * (x2 - x1) / np.where(y2 - y1 == 0, 1e-12, y2 - y1)
    return (np.sum(cond & (x < xi), axis=1) % 2) == 1


def _lattice(O, spacing, margin):
    lo, hi = O.min(0), O.max(0)
    pts = []
    row = 0
    z = lo[1] + spacing * 0.5
    while z < hi[1]:
        off = (spacing * 0.5) if row % 2 else 0.0
        u = lo[0] + off + spacing * 0.25
        while u < hi[0]:
            pts.append((u, z))
            u += spacing
        z += spacing * 0.866
        row += 1
    P = np.array(pts)
    P = P[_inside(P, O)]
    return P[_seg_dist(P, O) > margin]


def _cdt(pts, loops):
    edges, start = [], 0
    for n in loops:
        edges += [(start + i, start + (i + 1) % n) for i in range(n)]
        start += n
    vs, es, fs, orig, _, _ = delaunay_2d_cdt([Vector((p[0], p[1])) for p in pts], edges, [list(range(loops[0]))], 1,
                                             1e-7)
    src = [o[0] if o else -1 for o in orig]
    return np.array([(v.x, v.y) for v in vs]), fs, src


def vest_panel(name, poly, holes, mat_out, mat_in, torn, thick=0.0028, edge_thick=0.0042, inset=0.011, spacing=0.047):
    """A thin fabric panel cut to the pattern `poly` (u, z) with `holes` torn through it, laid on the body by to3d.
    Outer and inner faces share one triangulation (so the drape folds can't poke the inside through the outside); the
    bound edges are rolled a little thicker, torn ones (torn(point) is true) are left thin and frayed."""
    O = outline(poly, step=0.028, round_r=0.004, angle=math.radians(25))
    n0 = len(O)
    T = np.roll(O, -1, axis=0) - np.roll(O, 1, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    I = O + np.stack([-T[:, 1], T[:, 0]], axis=1) * inset
    HL = [outline(h, step=0.011, round_r=0.0015, angle=math.radians(30)) for h in holes]
    lat = _lattice(O, spacing, max(0.7 * spacing, inset + 0.012))
    keep = np.ones(len(lat), bool)
    for H in HL:
        keep &= ~_inside(lat, H)
        keep &= _seg_dist(lat, H) > 0.55 * spacing
    lat = lat[keep]
    pts = np.vstack([O, I] + HL + [lat])
    V, F, src = _cdt(pts, [n0, n0] + [len(H) for H in HL])
    cen = np.array([V[f].mean(0) for f in F])
    drop = np.zeros(len(F), bool)
    for H in HL:
        drop |= _inside(cen, H)
    F = [f for f, d in zip(F, drop) if not d]
    h_lo = 2 * n0
    h_hi = h_lo + sum(len(H) for H in HL)
    kind = np.ones(len(V))
    for i, s in enumerate(src):
        if 0 <= s < n0:
            kind[i] = 2.0 if torn(O[s]) else 0.0
        elif h_lo <= s < h_hi:
            kind[i] = 2.0
    Pin = to3d(V)
    bm = bmesh.new()
    vv = [bm.verts.new(p) for p in Pin]
    for f in F:
        bm.faces.new([vv[i] for i in f])
    bm.normal_update()
    N = np.array([v.normal[:] for v in vv])
    radial = Pin.copy()
    radial[:, 0] -= AXIS[0]
    radial[:, 1] -= AXIS[1]
    radial[:, 2] = 0
    if np.sum(np.einsum("ij,ij->i", N, radial)) < 0:
        N = -N
    bm.free()
    Pout = Pin + N * np.where(kind == 0, edge_thick, thick)[:, None]
    bm = bmesh.new()
    outer = [bm.verts.new(p) for p in Pout]
    inner = [bm.verts.new(p) for p in Pin]
    vals = [(V[i, 0], V[i, 1], kind[i]) for i in range(len(V))] * 2
    for f in F:
        bm.faces.new([outer[i] for i in f])
        fi = bm.faces.new([inner[i] for i in reversed(f)])
        fi.material_index = 1
    at = {s: i for i, s in enumerate(src) if s >= 0}
    loops = [[at[k] for k in range(n0)]]
    start = h_lo
    for H in HL:
        loops.append([at[k] for k in range(start, start + len(H))])
        start += len(H)
    for L in loops:
        for k in range(len(L)):
            a, b = L[k], L[(k + 1) % len(L)]
            bm.faces.new((outer[a], outer[b], inner[b], inner[a]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat_out)
    obj.data.materials.append(mat_in)
    set_attr(obj, vals)
    return tk.smooth(obj, 55)


# ---------------------------------------------------------------- the pattern

rnd = random.Random(4471)
ZB = 1.035  # the hem
U = lambda deg: math.radians(deg) * R0  # noqa: E731


def ragged(deg):
    """Where the hem is torn ragged (not the bound edge)."""
    return 20.0 <= deg <= 125.0 or 196.0 <= deg <= 262.0


def hem():
    pts = []
    for deg in np.arange(17.0, 343.1, 2.5):
        z = ZB + 0.0025 * math.sin(deg * 0.21)
        if ragged(deg):
            z += rnd.uniform(-0.007, 0.004)
        if 28.0 <= deg <= 36.0:  # a rip up the left front
            f = 1.0 - abs(deg - 32.0) / 4.0
            z = ZB + 0.085 * f ** 1.6 + rnd.uniform(-0.004, 0.004) * f
        pts.append((U(deg), z))
    return pts


def armhole(d0, d1, top0, top1, bottom=1.285, n=12):
    """A deep, loose armhole from (d0, top0) down to `bottom` under the arm and up to (d1, top1)."""
    out = []
    for t in np.linspace(0.0, math.pi, n)[1:-1]:
        f = 0.5 - 0.5 * math.cos(t)
        top = top0 + (top1 - top0) * f
        out.append((U(d0 + (d1 - d0) * f), top - (top - bottom) * math.sin(t) ** 0.85))
    return out


FRONT_TOP, BACK_TOP = 1.505, 1.525
pattern = hem() + [(U(344.5), ZB + 0.003), (U(345.5), 1.12), (U(346.0), 1.4), (U(333.0), FRONT_TOP),
                   (U(299.0), FRONT_TOP)]
pattern += armhole(299.0, 239.0, FRONT_TOP, BACK_TOP)
pattern += [(U(239.0), BACK_TOP), (U(207.0), BACK_TOP + 0.003), (U(180.0), BACK_TOP - 0.01),
            (U(153.0), BACK_TOP + 0.003), (U(121.0), BACK_TOP)]
pattern += armhole(121.0, 61.0, BACK_TOP, FRONT_TOP)
pattern += [(U(61.0), FRONT_TOP), (U(27.0), FRONT_TOP), (U(14.0), 1.4), (U(14.5), 1.12), (U(15.5), ZB + 0.003)]


def ragged_hole(cdeg, cz, rx, rz, seed, n=15, spike=None):
    r = random.Random(seed)
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        f = r.uniform(0.6, 1.15)
        if spike is not None and abs(math.atan2(math.sin(a - spike), math.cos(a - spike))) < 0.3:
            f *= 1.9
        pts.append((U(cdeg) + rx * f * math.cos(a), cz + rz * f * math.sin(a)))
    return pts


holes = [ragged_hole(213.0, 1.165, 0.028, 0.021, 7, spike=2.4),
         ragged_hole(319.0, 1.33, 0.014, 0.012, 8, n=12, spike=-1.2),
         ragged_hole(97.0, 1.105, 0.012, 0.016, 9, n=11, spike=1.6)]


def torn(p):
    deg = math.degrees(p[0] / R0)
    return p[1] < ZB + 0.095 and ragged(deg)


# ---------------------------------------------------------------- materials

ORANGE = (0.37, 0.092, 0.012)


def band01(g, x, lo, hi, soft=0.0012):
    return g.math("MULTIPLY", g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def line_dist(g, u, z, a, b):
    """Distance in the pattern plane from (u, z) to the line through a and b."""
    du, dz = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(du, dz)
    c = g.math("SUBTRACT", g.math("MULTIPLY", g.math("SUBTRACT", u, a[0]), dz / ln),
               g.math("MULTIPLY", g.math("SUBTRACT", z, a[1]), du / ln))
    return g.math("ABSOLUTE", c)


def blood_run(g, P, col, rough, height, region):
    """Dried and tacky blood: spatter, smears and drips run down (as the kevlar vest)."""
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 70.0)
    g.links.new(P, vor.inputs["Vector"])
    dots = g.ramp(tk._sock(vor.outputs, "Distance"), 0.2, 0.09)
    dots = g.math("MULTIPLY", dots, g.ramp(g.noise(5.0, detail=3.0, vector=P), 0.45, 0.55))
    drips = g.ramp(g.noise(1.0, detail=5.0, vector=mapping(g, P, (24.0, 24.0, 2.0))), 0.6, 0.66)
    smear = g.ramp(g.noise(2.6, detail=7.0, roughness=0.6, distortion=0.8, vector=P), 0.56, 0.62)
    b = g.math("MAXIMUM", g.math("MAXIMUM", dots, drips), smear)
    b = g.math("MULTIPLY", b, region, clamp=True)
    fresh = g.ramp(g.noise(9.0, detail=4.0, vector=P), 0.42, 0.7)
    bc = g.mix(fresh, (0.03, 0.006, 0.004), (0.075, 0.009, 0.006))
    col = g.mix(b, col, bc)
    rough = g.mixf(b, rough, g.mixf(fresh, 0.62, 0.4))
    height = g.math("ADD", height, g.math("MULTIPLY", b, 0.12))
    return col, rough, height


def hivis(name, mode, seed=0.0):
    """Fluorescent knit (mode "panel" from the pattern coordinates, "strap" from a strap's, "inner" the inside):
    blotchy dye, sun fade, the knit, wrinkles; the reflective tape, bindings, velcro and frayed tears; grease, dirt,
    mud up the hem, dust and blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    x, y, z = g.separate(g.coords())
    a1, a2, a3 = attr(g)
    up = normal_z(g)
    col = g.mix(g.ramp(g.noise(4.0, detail=4.0, vector=P), 0.3, 0.7), ORANGE, (0.3, 0.07, 0.009))
    if mode == "inner":
        col = tk._darker(g, col, 0.75)
    else:
        fade = g.math("ADD", g.math("ADD", g.math("MULTIPLY", g.ramp(up, -0.1, 0.9), 0.45),
                                    g.math("MULTIPLY", g.ramp(z, 1.3, 1.55), 0.35)), 0.15)
        fade = g.math("MULTIPLY", fade, g.ramp(g.noise(2.5, detail=5.0, vector=P, distortion=0.5), 0.3, 0.75))
        col = g.mix(fade, col, (0.37, 0.16, 0.065))
    knit = g.ramp(voronoi(g, P, 360.0), 0.22, 0.45)
    col = g.mix(g.math("MULTIPLY", knit, 0.3), tk._darker(g, col, 0.55), col)
    height = g.math("MULTIPLY", knit, 0.15)
    rough = g.math("ADD", 0.72, g.math("MULTIPLY", g.noise(12.0, vector=P), 0.08))
    metal = 0.0
    # Wrinkles: soft creases round the waist and down the drape
    wr = g.noise(1.0, detail=3.0, roughness=0.5, vector=mapping(g, P, (22.0, 22.0, 3.5)), distortion=0.6)
    wr2 = g.noise(1.0, detail=3.0, roughness=0.5, vector=mapping(g, P, (4.0, 4.0, 30.0), loc=(0.3, 0.2, 0.1)))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", wr, 0.8), g.math("MULTIPLY", wr2, 0.5)))
    tape = None
    if mode == "panel":
        u, v, e = a1, a2, a3
        h1 = band01(g, v, 1.075, 1.125)
        h2 = band01(g, v, 1.175, 1.225)
        vf = g.math("MAXIMUM", band01(g, u, U_STRIPE - 0.025, U_STRIPE + 0.025),
                    band01(g, u, U(360.0) - U_STRIPE - 0.025, U(360.0) - U_STRIPE + 0.025))
        vf = g.math("MULTIPLY", vf, band01(g, v, 1.2, 1.6))
        xb = None
        for a, b in (((U(180.0 + DEG_BACK), 1.56), (U(117.0), 1.2)), ((U(180.0 - DEG_BACK), 1.56), (U(243.0), 1.2))):
            d = g.ramp(line_dist(g, u, v, a, b), 0.0262, 0.0238)
            xb = d if xb is None else g.math("MAXIMUM", xb, d)
        xb = g.math("MULTIPLY", g.math("MULTIPLY", xb, band01(g, v, 1.2, 1.6)), band01(g, u, U(105.0), U(255.0)))
        tape = g.math("MAXIMUM", g.math("MAXIMUM", h1, h2), g.math("MAXIMUM", vf, xb))
        # bound edges: a smoother, darker tape with a stitch line
        bind = g.ramp(e, 0.8, 0.5)
        col = g.mix(bind, col, tk._darker(g, col, 0.8))
        rough = g.mixf(bind, rough, 0.6)
        height = g.math("ADD", height, g.math("MULTIPLY", bind, 0.4))
        st = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", e, 0.55)), 0.06, 0.02),
                    g.ramp(g.math("FRACT", g.math("DIVIDE", g.math("ADD", u, v), 0.005)), 0.3, 0.5))
        col = g.mix(g.math("MULTIPLY", st, 0.5), col, tk._darker(g, col, 0.5))
        # velcro tabs along the open front edges
        vel = g.math("MAXIMUM", band01(g, u, U(14.5), U(14.5) + 0.03), band01(g, u, U(345.5) - 0.03, U(345.5)))
        vel = g.math("MULTIPLY", vel, g.math("MAXIMUM", band01(g, v, 1.235, 1.29), band01(g, v, 1.31, 1.37)))
        col = g.mix(vel, col, tk._darker(g, col, 0.6))
        height = g.math("ADD", height, g.math("MULTIPLY", g.math("MULTIPLY", vel, g.noise(500.0, vector=P)), 0.6))
        rough = g.mixf(vel, rough, 0.9)
        # frayed tears: dark threads and a fringe
        fray = g.math("MULTIPLY", g.ramp(e, 1.55, 1.95), g.ramp(g.noise(260.0, detail=3.0, vector=P), 0.3, 0.6))
        col = g.mix(fray, col, (0.13, 0.05, 0.02))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", fray, 0.6))
    elif mode == "strap":
        a, s, side = a1, a2, a3
        tape = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", a), 0.0262, 0.0238), g.ramp(side, 0.5, 0.9))
    if tape is not None:
        # Reflective tape: grey with a fine glassy sparkle, cracked, peeling off in patches, dulled with grime
        micro = g.ramp(voronoi(g, P, 1200.0), 0.1, 0.5)
        tcol = g.mix(g.ramp(g.noise(7.0, vector=P), 0.3, 0.7), (0.12, 0.12, 0.118), (0.19, 0.19, 0.185))
        tcol = g.mix(g.math("MULTIPLY", micro, 0.4), tcol, tk._darker(g, tcol, 0.7))
        crk = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        g._in(crk, "Scale", 90.0)
        g.links.new(P, crk.inputs["Vector"])
        crack = g.math("MULTIPLY", g.ramp(tk._sock(crk.outputs, "Distance"), 0.035, 0.0),
                       g.ramp(g.noise(10.0, vector=P), 0.35, 0.55))
        tcol = g.mix(crack, tcol, (0.05, 0.045, 0.04))
        peel = g.ramp(g.noise(5.0, detail=6.0, roughness=0.7, vector=P, distortion=0.5), 0.64, 0.68)
        on = g.math("MULTIPLY", tape, g.math("SUBTRACT", 1.0, peel))
        col = g.mix(on, col, tcol)
        col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", tape, peel), 0.7), col, (0.17, 0.09, 0.045))
        rough = g.mixf(on, rough, g.mixf(crack, 0.34, 0.8))
        metal = g.mixf(on, metal, 0.3)
        height = g.math("ADD", height, g.math("MULTIPLY", on, g.math("SUBTRACT", 0.35, g.math("MULTIPLY", crack, 0.6))))
    # Grease smears and sweat stains
    gm = g.ramp(g.noise(3.2, detail=6.0, roughness=0.6, vector=P, distortion=1.1), 0.62, 0.72)
    col = g.mix(g.math("MULTIPLY", gm, 0.75), col, (0.035, 0.022, 0.012))
    rough = g.mixf(gm, rough, 0.38)
    # Blood: down the front from the mouth, a little everywhere
    front = g.ramp(y, 0.0, -0.06)
    region = g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(z, 1.12, 1.45), front), 1.0), 0.15)
    col, rough, height = blood_run(g, P, col, rough, height, region)
    col, rough, metal, height = grunge(g, P, col, rough, metal, height, dirt=0.7, grime=0.9, dust=0.3, specks=0.7,
                                       mud=0.85, mud_top=1.14, dirt_cols=((0.04, 0.03, 0.02), (0.1, 0.075, 0.05)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.0015))


# The reflective stripes line up with the shoulder pieces (x = +-SX)
SX = 0.122


def angle_for_x(x, z, back=False):
    lo, hi = 0.0, 90.0
    for _ in range(40):
        mid = (lo + hi) / 2
        deg = 180.0 - mid if back else mid
        p = to3d(np.array([[U(deg), z]]))[0]
        if p[0] > x:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


U_STRIPE = U(angle_for_x(SX, 1.45))
DEG_BACK = angle_for_x(SX, 1.48, back=True)

outer_mat = hivis("VestOuter", "panel", 1.0)
inner_mat = hivis("VestInner", "inner", 2.0)
strap_mat = hivis("VestShoulder", "strap", 3.0)

panel = vest_panel("Vest", pattern, holes, outer_mat, inner_mat, torn, spacing=0.053)
pieces = [panel]


# ---------------------------------------------------------------- shoulder pieces (as the kevlar vest's straps)

def bvh(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def far_hit(tree, origin, d, maxd=0.6):
    o = Vector(origin)
    d = Vector(d).normalized()
    travelled, best = 0.0, 0.0
    for _ in range(12):
        loc, nrm, idx, dist = tree.ray_cast(o, d, maxd - travelled)
        if loc is None:
            break
        travelled += dist + 1e-4
        best = travelled
        o = loc + d * 1e-4
    return best


def shell_exit(origin, d, clear, bones=None, maxd=0.45):
    t = np.arange(0.0, maxd, 0.0015)
    P = np.asarray(origin)[None] + t[:, None] * np.asarray(d)[None]
    inside = np.nonzero(sdf(P, bones) < clear)[0]
    return t[inside[-1]] if len(inside) else 0.0


def taut(origin2, dirs2, ts):
    P = [origin2 + d * t for d, t in zip(dirs2, ts)] + [origin2]
    pts = sorted(set((round(p[0], 7), round(p[1], 7)) for p in P))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    H = [np.array(p) for p in lower[:-1] + upper[:-1]]
    out = []
    for d, t0 in zip(dirs2, ts):
        best = t0
        for i in range(len(H)):
            a, b = H[i], H[(i + 1) % len(H)]
            e = b - a
            den = d[0] * (-e[1]) - d[1] * (-e[0])
            if abs(den) < 1e-12:
                continue
            w = a - origin2
            t = (w[0] * (-e[1]) - w[1] * (-e[0])) / den
            s = (d[0] * w[1] - d[1] * w[0]) / den
            if -1e-6 <= s <= 1 + 1e-6 and t > best:
                best = t
        out.append(best)
    return np.array(out)


def smooth1d(a, passes=2):
    a = np.array(a, float)
    for _ in range(passes):
        a[1:-1] = 0.25 * a[:-2] + 0.5 * a[1:-1] + 0.25 * a[2:]
    return a


def band2(name, pts, nrms, width, thick, mat, inner):
    """band() with its underside in the inner material."""
    obj = band(name, pts, nrms, width, thick, mat)
    obj.data.materials.append(inner)
    me = obj.data
    side = me.attributes[ATTR]
    for poly in me.polygons:
        if all(side.data[i].vector[2] < 0.5 for i in poly.vertices):
            poly.material_index = 1
    return obj


panel_tree = bvh([panel])


def conform_strap(name, pts, nrms, width, thick, mat, inner, bones, tree, nk=4):
    """A wide strap that lies across its width on whatever is under it: every point across it rests on the hit boxes
    (S_CLEAR off) or on the panel, whichever is higher. Writes (across, along, outer side) to its vertices."""
    P, N = np.array(pts, float), np.array(nrms, float)
    n = len(P)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    across = np.linspace(-width / 2, width / 2, nk)
    mid = np.zeros((n, nk, 3))
    nn = np.zeros((n, nk, 3))
    ts = np.linspace(-0.03, 0.05, 161)
    th = np.full(n, thick)
    th[[0, -1]] = thick * 0.3  # the ends thin out onto the panel, so they don't stand up as a step
    for i in range(n):
        T = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T /= np.linalg.norm(T)
        Ni = N[i] - T * (N[i] @ T)
        Ni /= np.linalg.norm(Ni)
        W = np.cross(T, Ni)
        for k, a in enumerate(across):
            q = P[i] + W * a
            bad = np.nonzero(sdf(q[None] + ts[:, None] * Ni[None], bones) < S_CLEAR)[0]
            t = ts[min(bad[-1] + 1, len(ts) - 1)] if len(bad) else ts[0]
            hit = far_hit(tree, Vector(q - Ni * 0.03), Vector(Ni), 0.08)
            if hit:
                t = max(t, hit - 0.03 + 0.0008)
            mid[i, k] = q + Ni * (t + th[i] / 2)
            nn[i, k] = Ni
    for _ in range(2):  # soften the steps between neighbours
        mid[1:-1] = 0.25 * mid[:-2] + 0.5 * mid[1:-1] + 0.25 * mid[2:]
    bm = bmesh.new()
    top = [[bm.verts.new(mid[i, k] + nn[i, k] * th[i] / 2) for k in range(nk)] for i in range(n)]
    bot = [[bm.verts.new(mid[i, k] - nn[i, k] * th[i] / 2) for k in range(nk)] for i in range(n)]
    vals = [(across[k], s[i], 1.0) for i in range(n) for k in range(nk)] +         [(across[k], s[i], 0.0) for i in range(n) for k in range(nk)]
    for i in range(n - 1):
        for k in range(nk - 1):
            bm.faces.new((top[i][k], top[i + 1][k], top[i + 1][k + 1], top[i][k + 1]))
            f = bm.faces.new((bot[i][k + 1], bot[i + 1][k + 1], bot[i + 1][k], bot[i][k]))
            f.material_index = 1
        for k in (0, nk - 1):
            bm.faces.new((top[i][k], bot[i][k], bot[i + 1][k], top[i + 1][k]))
    for i in (0, n - 1):
        for k in range(nk - 1):
            bm.faces.new((top[i][k], top[i][k + 1], bot[i][k + 1], bot[i][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    obj.data.materials.append(inner)
    set_attr(obj, vals)
    return tk.smooth(obj, 50)
S_W, S_T, S_CLEAR = 0.066, 0.003, 0.009


def shoulder_piece(sgn):
    x = SX * sgn
    c = np.array([x, 0.06, 1.45])
    psis = np.radians(np.linspace(-76.5, 67.0, 16))  # ending a little way down the tabs, not past their corners
    dirs = [np.array([0.0, math.sin(p), math.cos(p)]) for p in psis]
    bones = ("Spine2", "LeftArm", "RightArm")
    ts = []
    for d in dirs:
        tb = shell_exit(c, d, S_CLEAR, bones)
        tp = far_hit(panel_tree, Vector(c), Vector(d))
        ts.append(max(tb, tp + 0.001 if tp else 0.0))
    ts = taut(np.array([0.06, 1.45]), [np.array([d[1], d[2]]) for d in dirs], ts)
    ts = smooth1d(ts, 2) + S_T / 2 + 0.0004
    pts = np.array([c + d * t for d, t in zip(dirs, ts)])
    e = 1e-3
    gr = np.stack([sdf(pts + dv, bones) - sdf(pts - dv, bones) for dv in np.eye(3) * e], axis=1)
    gr /= np.linalg.norm(gr, axis=1)[:, None]
    nrms = np.array(dirs) + gr
    nrms /= np.linalg.norm(nrms, axis=1)[:, None]
    for _ in range(3):  # lift it wherever an edge digs in
        for i in range(len(pts)):
            tng = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            tng /= np.linalg.norm(tng)
            W = np.cross(tng, nrms[i])
            W /= np.linalg.norm(W)
            probe = np.array([pts[i] + W * k * S_W / 2 - nrms[i] * S_T / 2 for k in (-1, -0.5, 0, 0.5, 1)])
            short = S_CLEAR - sdf(probe, bones).min()
            if short > 0:
                pts[i] = pts[i] + nrms[i] * short
    return conform_strap("Shoulder%+d" % sgn, pts, nrms, S_W, S_T, strap_mat, inner_mat, bones, panel_tree)


pieces += [shoulder_piece(1), shoulder_piece(-1)]

# ---------------------------------------------------------------- checks, export, previews

for o in pieces:
    bake_transform(o)
    fix_normals(o)
    zk.on(o, BONE, PIECE)
for o in pieces:
    V = np.array([v.co[:] for v in o.data.vertices])
    print("[%s] %-14s %4d tris, %.1f mm off the hit boxes (arms %.1f, head %.1f, hips %.1f)" % (
        SCRIPT, o.name, tri_count([o]), sdf(V).min() * 1000, sdf(V, ("LeftArm", "RightArm")).min() * 1000,
        sdf(V, ("Head",)).min() * 1000, sdf(V, ("Hips",)).min() * 1000))
    k = int(np.argmin(sdf(V, ("LeftArm", "RightArm"))))
    print("[%s]   nearest the arms at %s" % (SCRIPT, np.round(V[k], 3)))
allv = np.array([v.co[:] for o in pieces for v in o.data.vertices])
print("[%s] %d triangles, bounds %s to %s, closest %.1f mm" % (SCRIPT, tri_count(pieces), np.round(allv.min(0), 3),
                                                               np.round(allv.max(0), 3), sdf(allv).min() * 1000))

for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS)
for o in BODY:
    o.hide_render = False
focus = Vector((0.0, 0.03, 1.28))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.45)
for view, loc, tgt, lens in (("close", (0.25, -0.6, 1.42), (0.0, -0.08, 1.3), 45),
                             ("backclose", (-0.2, 0.75, 1.45), (0.0, 0.12, 1.32), 45),
                             ("top", (0.42, -0.3, 2.0), (0.08, 0.05, 1.5), 45),
                             ("armpit", (0.75, 0.05, 1.12), (0.12, 0.05, 1.35), 50)):
    tk.render(tk.camera("hv_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
