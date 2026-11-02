"""Ankle monitor: a house-arrest GPS tag locked round the right leg just above the ankle. A thick black rubber strap
with a fibre-optic tamper line inside it, a rounded black box on the outside of the ankle with steel clamp plates and
security screws where the strap goes in, a peeling white serial-number label with a barcode, and a little status LED
that still glows a dim green. Scuffed, mud-caked from below, a smear of blood.

The strap is 0.5 cm off the shin's hit box. One part on the RightLeg bone ("RightLeg#Monitor").

    blender -b --factory-startup --python ankle_monitor.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PIECE = "AnkleMonitor", "ankle_monitor", "RightLeg", "Monitor"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex local coordinates the materials print by

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




# ---------------------------------------------------------------- the leg

LEG_A, LEG_B, LEG_R = next((a, b, r) for bone, a, b, r in CAPS if bone == "RightLeg")
D = (LEG_B - LEG_A) / np.linalg.norm(LEG_B - LEG_A)  # up the shin
C = LEG_A + D * ((0.158 - LEG_A[2]) / D[2])  # the strap's middle, just above the ankle
lat = np.array([-1.0, -0.42, 0.0])  # the outside of the right ankle, a little to the front
U1 = lat - D * (lat @ D)
U1 /= np.linalg.norm(U1)
U2 = np.cross(D, U1)

STRAP_W, STRAP_T = 0.027, 0.0036
R_IN = LEG_R + 0.005
R_MID = R_IN + STRAP_T / 2
R_OUT = R_IN + STRAP_T


def ring_pt(phi, r):
    return C + (U1 * math.cos(phi) + U2 * math.sin(phi)) * r


def ring_n(phi):
    return U1 * math.cos(phi) + U2 * math.sin(phi)


def ring_t(phi):
    return -U1 * math.sin(phi) + U2 * math.cos(phi)


# ---------------------------------------------------------------- materials

def rubber(name, base, seed=0.0):
    """The strap: matte black rubber, a faint moulded ridge down the middle, scuffed paler, caked with mud."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    a, s, side = attr(g)
    col = g.mix(g.math("MULTIPLY", g.noise(6.0, detail=3.0, vector=P), 0.5), base, tk._darker(g, base, 0.7))
    ridge = g.ramp(g.math("ABSOLUTE", a), 0.004, 0.0015)
    groove = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", a), 0.0095)), 0.0008, 0.0002)
    height = g.math("ADD", g.math("MULTIPLY", ridge, 0.3), g.math("MULTIPLY", groove, -0.6))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(300.0, detail=3.0, vector=P), 0.15))
    rough = g.math("ADD", 0.62, g.math("MULTIPLY", g.noise(15.0, vector=P), 0.1))
    sc = g.math("MULTIPLY", scratches(g, P, 0.03), 0.8)
    col = g.mix(sc, col, (0.07, 0.068, 0.065))
    rough = g.mixf(sc, rough, 0.75)
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.06, 0.3), g.ramp(g.noise(30.0, vector=P), 0.35, 0.55))
    col = g.mix(worn, col, (0.08, 0.077, 0.072))
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.55, grime=0.9, dust=0.12, specks=0.6,
                                       blood=0.25, mud=0.8, mud_top=0.23,
                                       dirt_cols=((0.022, 0.019, 0.016), (0.05, 0.042, 0.032)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.001))


def device_material(name, seed=0.0):
    """The box: glossy black plastic, scratched, a dirty serial label with a barcode peeling off the face, the status
    LED behind a little lens (a dim green glow)."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    x, z, face = attr(g)
    base = (0.02, 0.02, 0.022)
    col = g.mix(g.math("MULTIPLY", g.noise(5.0, detail=3.0, vector=P), 0.5), base, tk._darker(g, base, 0.7))
    rough = g.math("ADD", 0.34, g.math("MULTIPLY", g.noise(14.0, detail=3.0, vector=P), 0.12))
    height = g.math("MULTIPLY", g.noise(120.0, detail=4.0, vector=P), 0.08)
    metal = 0.0
    front = g.ramp(face, 0.62, 0.75)

    def box(lo_x, hi_x, lo_z, hi_z, soft=0.0006):
        bx = g.math("MULTIPLY", g.ramp(x, lo_x - soft, lo_x + soft), g.ramp(x, hi_x + soft, hi_x - soft))
        bz = g.math("MULTIPLY", g.ramp(z, lo_z - soft, lo_z + soft), g.ramp(z, hi_z + soft, hi_z - soft))
        return g.math("MULTIPLY", bx, bz)
    # A moulded seam line round the face and a recessed panel
    panel = box(-0.026, 0.026, -0.019, 0.019, 0.0005)
    rim = g.math("SUBTRACT", panel, box(-0.0248, 0.0248, -0.0178, 0.0178, 0.0005))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MULTIPLY", rim, front), 0.8))
    col = g.mix(g.math("MULTIPLY", rim, front), col, (0.008, 0.008, 0.009))
    # The label: off-white, a barcode, lines of print, a torn corner and frayed edges
    lab = box(-0.022, 0.006, -0.015, 0.013, 0.0008)
    torn = g.ramp(g.math("ADD", g.math("SUBTRACT", x, z), g.math("MULTIPLY", g.noise(90.0, vector=P), 0.006)), -0.009,
                  -0.011)
    lab = g.math("MULTIPLY", g.math("MULTIPLY", lab, front), torn)
    lab = g.math("MULTIPLY", lab, g.ramp(g.noise(70.0, detail=5.0, vector=P), 0.25, 0.35))
    paper = g.mix(g.ramp(g.noise(9.0, vector=P), 0.3, 0.7), (0.27, 0.26, 0.225), (0.19, 0.17, 0.135))
    bars = g.ramp(g.noise(1.0, detail=0.0, vector=mapping(g, P, (900.0, 0.0, 0.0))), 0.48, 0.52)
    bars = g.math("MULTIPLY", bars, box(-0.019, 0.003, -0.012, -0.002, 0.0003))
    text = g.math("MULTIPLY", box(-0.019, 0.003, 0.001, 0.0105, 0.0003),
                  g.math("MULTIPLY", g.ramp(g.math("FRACT", g.math("DIVIDE", z, 0.0032)), 0.55, 0.62),
                         g.ramp(g.noise(450.0, vector=P), 0.42, 0.5)))
    ink = g.math("MAXIMUM", bars, text)
    paper = g.mix(ink, paper, (0.03, 0.03, 0.032))
    col = g.mix(lab, col, paper)
    rough = g.mixf(lab, rough, 0.75)
    height = g.math("ADD", height, g.math("MULTIPLY", lab, 0.3))
    glue = g.math("MULTIPLY", g.math("MULTIPLY", box(-0.022, 0.006, -0.015, 0.013, 0.0008), front),
                  g.math("SUBTRACT", 1.0, torn))
    col = g.mix(g.math("MULTIPLY", glue, 0.7), col, (0.09, 0.08, 0.06))
    # The LED lens and its glow
    cx = g.node("ShaderNodeCombineXYZ")
    g.links.new(x, cx.inputs[0])
    g.links.new(z, cx.inputs[1])
    dist = g.node("ShaderNodeVectorMath", operation="DISTANCE")
    g.links.new(cx.outputs[0], dist.inputs[0])
    dist.inputs[1].default_value = (0.0175, 0.0095, 0.0)
    dd = tk._sock(dist.outputs, "Value")
    lens = g.math("MULTIPLY", g.ramp(dd, 0.0032, 0.0024), front)
    bezel = g.math("MULTIPLY", g.math("SUBTRACT", g.ramp(dd, 0.0042, 0.0034), lens), front)
    col = g.mix(bezel, col, (0.06, 0.06, 0.058))
    col = g.mix(lens, col, (0.02, 0.08, 0.03))
    rough = g.mixf(lens, rough, 0.15)
    height = g.math("ADD", height, g.math("MULTIPLY", lens, 0.6))
    glow = g.math("MULTIPLY", g.ramp(dd, 0.0026, 0.0008), front)
    emission = g.mix(glow, (0.0, 0.0, 0.0), (0.015, 0.16, 0.036))
    # Wear and dirt (kept off the lens)
    sc = g.math("MULTIPLY", scratches(g, P, 0.025), 0.9)
    col = g.mix(g.math("MULTIPLY", sc, 0.8), col, (0.11, 0.11, 0.105))
    rough = g.mixf(sc, rough, 0.6)
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.0025), 0.06, 0.3), g.ramp(g.noise(30.0, vector=P), 0.36, 0.55))
    col = g.mix(worn, col, (0.1, 0.1, 0.097))
    col2, rough2, metal, height = grunge(g, P, col, rough, metal, height, dirt=0.5, grime=0.9, dust=0.15, specks=0.6,
                                         blood=0.3, mud=0.7, mud_top=0.21,
                                         dirt_cols=((0.022, 0.019, 0.016), (0.055, 0.046, 0.035)))
    col = g.mix(g.math("MULTIPLY", lens, 0.8), col2, col)
    return tk.finish(mat, g, col, metal, rough2, g.bump(height, 0.3, 0.001), emission=emission)


strap_mat = rubber("StrapRubber", (0.016, 0.016, 0.018), seed=1.0)
box_mat = device_material("MonitorBox", seed=2.0)
steel_mat = steel("ClampSteel", (0.2, 0.2, 0.2), seed=3.0, rust=0.4, polish=0.7)

# ---------------------------------------------------------------- the strap, the box, the clamps

pieces = []
STRAP_PROFILE = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.25), (0.38, 0.5), (-0.38, 0.5), (-0.5, 0.25)]
phis = np.linspace(0, 2 * math.pi, 30, endpoint=False)
pieces.append(band("Strap", [ring_pt(p, R_MID) for p in phis], [ring_n(p) for p in phis], STRAP_W, STRAP_T, strap_mat,
                   profile=STRAP_PROFILE, closed=True, smooth_angle=60))

HX, HY, HZ = 0.031, 0.0135, 0.0245
box = superbox("MonitorBox", (HX, HY, HZ), box_mat, n=4.2, cuts=3, back_squash=0.55)
set_attr(box, [(v.co.x, v.co.z, v.co.y / HY) for v in box.data.vertices])
# Hug the strap's curve: the back's ends curl in toward the leg
for v in box.data.vertices:
    if v.co.y < 0:
        v.co.y -= 0.006 * (v.co.x / HX) ** 2
pieces.append(place(box, ring_pt(0.0, R_OUT + HY * 0.55 - 0.0025), ring_t(0.0), ring_n(0.0), D))

for side in (-1, 1):
    phi = side * (HX + 0.0045) / R_OUT
    plate = tk.box("Clamp%+d" % side, (0.011, 0.0022, STRAP_W + 0.004), (0, 0, 0), steel_mat)
    pieces.append(place(plate, ring_pt(phi, R_OUT + 0.0011), ring_t(phi), ring_n(phi), D))
    for k, dz in enumerate((-0.0075, 0.0075)):
        sc = tk.cylinder("Screw%+d_%d" % (side, k), 0.0021, 0.0, 0.0013, steel_mat, segments=6)
        pieces.append(place(sc, ring_pt(phi, R_OUT + 0.0022) + D * dz, ring_t(phi), D, ring_n(phi)))

# ---------------------------------------------------------------- checks, export, previews

for o in pieces:
    bake_transform(o)
    fix_normals(o)
    zk.on(o, BONE, PIECE)
for o in pieces:
    V = np.array([v.co[:] for v in o.data.vertices])
    print("[%s] %-20s %4d tris, %.1f mm off the hit boxes" % (SCRIPT, o.name, tri_count([o]), sdf(V).min() * 1000))
allv = np.array([v.co[:] for o in pieces for v in o.data.vertices])
print("[%s] %d triangles, bounds %s to %s, closest %.1f mm" % (SCRIPT, tri_count(pieces), np.round(allv.min(0), 3),
                                                               np.round(allv.max(0), 3), sdf(allv).min() * 1000))

for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS, size=512)
for o in BODY:
    o.hide_render = False
focus = Vector(C)
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.75)
for view, d, lens in (("close", (-0.8, -0.55, 0.3), 50), ("front", (0.1, -1.0, 0.25), 50)):
    loc = Vector(C) + Vector(d).normalized() * 0.32
    tk.render(tk.camera("am_" + view, loc, Vector(C), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, "close" if view == "close" else "closefront")),
              res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
