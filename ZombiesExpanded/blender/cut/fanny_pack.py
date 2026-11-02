"""Fanny pack: a 90s nylon bum bag worn at the front of the waist, long faded in the sun. A curved main pouch in teal
ripstop with black gussets and a purple front pocket, a zipper along the top of each with pulls and cord loops hanging,
a little rubber logo patch, and black webbing round the waist to a side-release buckle at the back. Faded where the
sun hit it, grimy in the seams, dusty, splashed with mud from below and smeared with blood.

The webbing is 0.6 cm off the hips' hit box and the pack sits on it, between the hip bones, above the thighs. One part
on the Hips bone ("Hips#Pack").

    blender -b --factory-startup --python fanny_pack.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PIECE = "FannyPack", "fanny_pack", "Hips", "Pack"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex (along, around, kind) coordinates the materials print by

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




# ---------------------------------------------------------------- nylon

TEAL, BLACK, PURPLE = (0.022, 0.07, 0.066), (0.013, 0.013, 0.015), (0.045, 0.02, 0.058)


def band01(g, x, lo, hi, soft=0.0012):
    """1 between lo and hi (sockets or numbers), soft edges."""
    return g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", x, lo), -soft, soft),
                  g.ramp(g.math("SUBTRACT", x, hi), soft, -soft))


def nylon(name, panel, seed=0.0, u_lim=0.12, logo=False, blood=0.35):
    """Faded ripstop nylon over the pack's (along, around-from-the-top, around-to-the-bottom) coordinates: a colored
    front panel between black gussets, a zipper along the top, seams; sun fade, dirt, mud and blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    u, rel, relb = attr(g)
    au = g.math("ABSOLUTE", u)
    front = g.math("MULTIPLY", band01(g, rel, 0.03, g.math("SUBTRACT", relb, 0.016), 0.0015),
                   g.ramp(au, u_lim, u_lim - 0.004))
    col = g.mix(front, BLACK, panel)
    # Sun-faded: lighter, greyer on top and in blotches; worn darker where it rubbed
    up = normal_z(g)
    fade = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", g.ramp(up, -0.2, 0.9), 0.6), 0.25),
                  g.ramp(g.noise(3.0, detail=5.0, vector=P, distortion=0.5), 0.3, 0.7))
    col = g.mix(fade, col, tk.grade(g, col, 0.45, 2.1))
    # Ripstop grid
    gu = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", u, 0.006)), 0.5)), 0.42, 0.48)
    gv = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", rel, 0.006)), 0.5)), 0.42, 0.48)
    grid = g.math("MAXIMUM", gu, gv)
    col = g.mix(g.math("MULTIPLY", grid, 0.25), col, tk._darker(g, col, 0.7))
    height = g.math("MULTIPLY", grid, 0.15)
    rough = g.math("ADD", 0.55, g.math("MULTIPLY", g.noise(20.0, detail=3.0, vector=P), 0.12))
    metal = 0.0
    # Seams round the front panel: a dark welt with a stitch line beside it
    for edge in (0.03, g.math("SUBTRACT", relb, 0.016)):
        dd = g.math("ABSOLUTE", g.math("SUBTRACT", rel, edge))
        welt = g.ramp(dd, 0.0022, 0.0008)
        col = g.mix(g.math("MULTIPLY", welt, 0.7), col, (0.008, 0.008, 0.009))
        height = g.math("ADD", height, g.math("MULTIPLY", welt, 0.5))
        st = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", dd, 0.0045)), 0.0007, 0.0002),
                    g.ramp(g.math("FRACT", g.math("DIVIDE", u, 0.004)), 0.35, 0.5))
        col = g.mix(g.math("MULTIPLY", st, 0.5), col, (0.16, 0.16, 0.15))
    # The zipper along the top: black tape, a row of plastic teeth
    tape = band01(g, rel, 0.006, 0.022, 0.0006)
    teeth = g.math("MULTIPLY", band01(g, rel, 0.0108, 0.0172, 0.0004),
                   g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", u, 0.0026)), 0.5)), 0.3,
                          0.2))
    col = g.mix(tape, col, (0.011, 0.011, 0.012))
    col = g.mix(teeth, col, (0.09, 0.09, 0.085))
    rough = g.mixf(teeth, rough, 0.35)
    height = g.math("ADD", height, g.math("MULTIPLY", teeth, 0.8))
    if logo:
        # A rubber logo patch: a dark rounded rectangle with a pale zigzag mountain
        pu = band01(g, u, -0.024, 0.024, 0.0012)
        pv = band01(g, rel, 0.024, 0.046, 0.0012)
        patch = g.math("MULTIPLY", pu, pv)
        col = g.mix(patch, col, (0.025, 0.025, 0.027))
        rough = g.mixf(patch, rough, 0.45)
        height = g.math("ADD", height, g.math("MULTIPLY", patch, 0.4))
        zig = g.math("ADD", 0.04, g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT",
                     g.math("DIVIDE", g.math("ADD", u, 0.03), 0.02)), 0.5)), -0.022))
        mark = g.math("MULTIPLY", g.math("MULTIPLY", band01(g, rel, g.math("SUBTRACT", zig, 0.0016), zig, 0.0005),
                                         band01(g, u, -0.018, 0.018, 0.001)), patch)
        mark = g.math("MULTIPLY", mark, g.ramp(g.noise(80.0, vector=P), 0.25, 0.4))
        col = g.mix(mark, col, (0.3, 0.29, 0.26))
    # Fuzz and pills where it rubs, then the dirt
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.08, 0.35), g.ramp(g.noise(30.0, vector=P), 0.35, 0.55))
    col = g.mix(g.math("MULTIPLY", worn, 0.7), col, tk.grade(g, col, 0.5, 1.8))
    col, rough, metal, height = grunge(g, P, col, rough, metal, height, dirt=0.65, grime=0.8, dust=0.35, specks=0.6,
                                       blood=blood, mud=0.55, mud_top=1.02)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.0015))


def webbing(name, seed=0.0):
    """Black nylon webbing: fine ribs along its length, fuzzy pale edges, dirt."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    a, s, side = attr(g)
    rib = g.math("SINE", g.math("DIVIDE", a, 0.00045))
    tw = g.math("SINE", g.math("DIVIDE", g.math("ADD", s, g.math("MULTIPLY", a, 0.7)), 0.0012))
    col = g.mix(g.math("MULTIPLY", g.math("ADD", rib, 1.0), 0.2), BLACK, tuple(c * 1.6 for c in BLACK))
    height = g.math("ADD", g.math("MULTIPLY", rib, 0.2), g.math("MULTIPLY", tw, 0.1))
    fuzz = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", a), 0.0165, 0.019), g.ramp(g.noise(60.0, vector=P), 0.3, 0.6))
    col = g.mix(fuzz, col, (0.075, 0.072, 0.07))
    rough = g.math("ADD", 0.6, g.math("MULTIPLY", fuzz, 0.3))
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.5, grime=0.7, dust=0.15, specks=0.5,
                                       blood=0.15, mud=0.4, mud_top=1.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.001))


# ---------------------------------------------------------------- the webbing round the waist

HC = np.array([0.0, 0.015])  # the hips' hit box axis (x, y)
HIPS = ("Hips", "LeftUpLeg", "RightUpLeg", "Spine2")
WEB_W, WEB_T, WEB_Z = 0.038, 0.0024, 1.036


def radial(th):
    return np.array([math.sin(th), -math.cos(th), 0.0])


def at(th, r, z):
    return np.array([HC[0] + r * math.sin(th), HC[1] - r * math.cos(th), z])


def inner_radius(th, z0, z1, clear):
    for r in np.arange(0.12, 0.35, 0.0005):
        if sdf([at(th, r, z0), at(th, r, (z0 + z1) / 2), at(th, r, z1)], HIPS).min() >= clear:
            return r
    return 0.35


R_WEB = max(inner_radius(t, WEB_Z - WEB_W / 2, WEB_Z + WEB_W / 2, 0.006) for t in np.linspace(0, 2 * math.pi, 24))
web_mat = webbing("Webbing", 1.0)
pieces = []
THS = np.linspace(0, 2 * math.pi, 28, endpoint=False)
pieces.append(band("Webbing", [at(t, R_WEB + WEB_T / 2, WEB_Z) for t in THS], [radial(t) for t in THS], WEB_W, WEB_T,
                   web_mat, closed=True))

# ---------------------------------------------------------------- the pack: lofted round the waist

R_PACK = R_WEB + WEB_T + 0.0008
TH_E = math.radians(46.0)
D0, H0, ZC0 = 0.072, 0.118, 1.042


def station(t, d0=D0, h0=H0, zc0=ZC0):
    """Depth, height and middle of the pack's section at t = angle / TH_E (the ends are smaller)."""
    s = math.sqrt(max(0.0, 1.0 - t * t))
    return d0 * (0.3 + 0.7 * s), h0 * (0.6 + 0.4 * s), zc0 + 0.004 * (1.0 - s)


def section(d, h, zc, m, o0=0.0, back_frac=0.2):
    """A closed section (o out, z) from the back's middle over the top, down the front, under and back: a rounded
    front, a flatter back on o = o0."""
    pts = []
    for j in range(m):
        phi = 1.5 * math.pi + 2 * math.pi * j / m  # 0 top, pi/2 front, pi bottom, 3pi/2 back
        c, s = math.cos(phi), math.sin(phi)
        if s >= 0:
            o = back_frac * d + (1 - back_frac) * d * abs(s) ** (2 / 2.4)
            z = zc + h / 2 * math.copysign(abs(c) ** (2 / 2.4), c)
        else:
            o = back_frac * d - back_frac * d * abs(s) ** (2 / 6.0)
            z = zc + h / 2 * math.copysign(abs(c) ** (2 / 6.0), c)
        pts.append((o0 + o, z))
    return pts


def loft(name, mat, th_e, n_th, m, station_fn, o0_fn):
    """Lofts sections round the hips axis from -th_e to th_e and closes the ends; writes (along, around from the top,
    bottom's around) to the vertices."""
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n_th):
        t = -1.0 + 2.0 * i / (n_th - 1)
        th = t * th_e
        d, h, zc = station_fn(t)
        sec = section(d, h, zc, m, o0_fn(t, d, h, zc))
        # arc length round the section, measured from its top point
        L = [0.0]
        for j in range(1, m):
            L.append(L[-1] + math.dist(sec[j], sec[j - 1]))
        top, bot = L[m // 4], L[3 * m // 4]
        rings.append([bm.verts.new(at(th, R_PACK + o, z)) for o, z in sec])
        vals += [(th * R_PACK, L[j] - top, bot - top) for j in range(m)]
    for i in range(n_th - 1):
        for j in range(m):
            a, b = rings[i], rings[i + 1]
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    for i, sign in ((0, -1), (n_th - 1, 1)):
        d, h, zc = station_fn(float(sign))
        o0 = o0_fn(float(sign), d, h, zc)
        c = bm.verts.new(at(sign * (th_e + 0.012 / R_PACK), R_PACK + o0 + d * 0.3, zc))
        vals.append((sign * th_e * R_PACK + sign * 0.012, -0.08, 0.2))
        for j in range(m):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % m], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, 55)


main_mat = nylon("PackNylon", TEAL, seed=2.0, u_lim=TH_E * R_PACK - 0.012)
pocket_mat = nylon("PocketNylon", PURPLE, seed=3.0, u_lim=0.62 * TH_E * R_PACK - 0.008, logo=True, blood=0.25)
pieces.append(loft("Pack", main_mat, TH_E, 15, 16, station, lambda t, d, h, zc: 0.0))


def main_front(t, z):
    """How far out (o) the main pouch's front is at height z on station t."""
    d, h, zc = station(t)
    q = min(1.0, abs(z - zc) / (h / 2))
    return 0.2 * d + 0.8 * d * (1.0 - q ** 2.4) ** (1 / 2.4)


PK_E, PK_H, PK_D = 0.62, 0.064, 0.03


def pocket_station(t):
    d, h, zc = station(t * PK_E)
    s = math.sqrt(max(0.0, 1.0 - t * t))
    return PK_D * (0.35 + 0.65 * s), PK_H * (0.65 + 0.35 * s), zc - 0.013


def pocket_back(t, d, h, zc):
    return min(main_front(t * PK_E, zc - h / 2), main_front(t * PK_E, zc + h / 2)) - 0.004


pieces.append(loft("Pocket", pocket_mat, TH_E * PK_E, 11, 14, pocket_station, pocket_back))


# ---------------------------------------------------------------- zipper pulls, buckle

def surf(t, rel, lift, front_fn=None):
    """A point and its outward normal on the main pouch's section at t, `rel` round from the top, lifted off it."""
    d, h, zc = station(t)
    sec = section(d, h, zc, 96)
    L = [0.0]
    for j in range(1, 96):
        L.append(L[-1] + math.dist(sec[j], sec[j - 1]))
    target = L[24] + rel
    j = max(1, min(94, int(np.searchsorted(L, target))))
    f = (target - L[j - 1]) / max(1e-9, L[j] - L[j - 1])
    o = sec[j - 1][0] + (sec[j][0] - sec[j - 1][0]) * f
    z = sec[j - 1][1] + (sec[j][1] - sec[j - 1][1]) * f
    to, tz = sec[j][0] - sec[j - 1][0], sec[j][1] - sec[j - 1][1]
    n2 = np.array([-tz, to]) / math.hypot(to, tz)  # outward in (o, z)
    th = t * TH_E
    p = at(th, R_PACK + o + n2[0] * lift, z + n2[1] * lift)
    nrm = radial(th) * n2[0] + np.array([0, 0, n2[1]])
    return p, nrm


zip_mat = plastic("ZipperPull", (0.024, 0.024, 0.025), seed=5.0, rough=0.32, scuff=0.9, edge_col=(0.2, 0.2, 0.19),
                  dirt=0.5, mud=0.3, sawdust=0.0)
cord_mat = plastic("PullCord", (0.022, 0.021, 0.02), seed=6.0, rough=0.75, scuff=0.3, dirt=0.8, mud=0.6, sawdust=0.0)


def zipper_pull(name, t, rel0, front_fn=surf, lift=0.003):
    out = []
    p0, n0 = front_fn(t, rel0, lift)
    slider = tk.box(name + "Slider", (0.014, 0.008, 0.005), (0, 0, 0), zip_mat)
    tng = np.cross(n0, radial(t * TH_E + math.pi / 2))
    th = t * TH_E
    along = np.array([math.cos(th), math.sin(th), 0.0])
    out.append(place(slider, p0, Vector(along), Vector(np.cross(n0, along)), Vector(n0)))
    pts, nrms = [], []
    for k, rel in enumerate((rel0 + 0.002, rel0 + 0.01, rel0 + 0.018, rel0 + 0.025)):
        p, n = front_fn(t, rel, lift + 0.0015 + 0.0012 * k)
        pts.append(p)
        nrms.append(n)
    out.append(band(name + "Tab", pts, nrms, 0.0075, 0.0015, zip_mat))
    # a short cord loop knotted through the tab
    c = []
    for k, (rel, sx) in enumerate(((0.023, -0.003), (0.034, -0.0045), (0.045, -0.0025), (0.05, 0.0), (0.045, 0.0025),
                                    (0.034, 0.0045), (0.023, 0.003))):
        p, n = front_fn(t, rel0 + rel, lift + 0.004 + 0.002 * math.sin(k / 6 * math.pi))
        c.append(p + along * sx)
    out.append(tube(name + "Cord", c, 0.0021, cord_mat, sides=4))
    return out


pieces += zipper_pull("PullA", -0.05, 0.014)
pieces += zipper_pull("PullB", 0.05, 0.014)


def pocket_surf(t, rel, lift):
    """Like surf, on the front pocket (t over the whole pack)."""
    tp = t / PK_E
    d, h, zc = pocket_station(tp)
    o0 = pocket_back(tp, d, h, zc)
    sec = section(d, h, zc, 96, o0)
    L = [0.0]
    for j in range(1, 96):
        L.append(L[-1] + math.dist(sec[j], sec[j - 1]))
    target = L[24] + rel
    j = max(1, min(94, int(np.searchsorted(L, target))))
    f = (target - L[j - 1]) / max(1e-9, L[j] - L[j - 1])
    o = sec[j - 1][0] + (sec[j][0] - sec[j - 1][0]) * f
    z = sec[j - 1][1] + (sec[j][1] - sec[j - 1][1]) * f
    to, tz = sec[j][0] - sec[j - 1][0], sec[j][1] - sec[j - 1][1]
    n2 = np.array([-tz, to]) / math.hypot(to, tz)
    th = t * TH_E
    return at(th, R_PACK + o + n2[0] * lift, z + n2[1] * lift), radial(th) * n2[0] + np.array([0, 0, n2[1]])


pieces += zipper_pull("PullC", 0.3, 0.014, pocket_surf, 0.0025)

buckle_mat = plastic("Buckle", (0.02, 0.02, 0.021), seed=7.0, rough=0.4, scuff=0.6, edge_col=(0.07, 0.07, 0.068),
                     dirt=0.7, mud=0.5, sawdust=0.0)


def buckle():
    """A side-release buckle at the back, a little to the left, and the webbing's loose tail."""
    out = []
    th = math.radians(165.0)
    p = at(th, R_WEB + WEB_T + 0.0058, WEB_Z)
    along = Vector((math.cos(th), math.sin(th), 0.0))
    o = Vector(radial(th))
    up = Vector((0.0, 0.0, 1.0))
    female = superbox("BuckleFemale", (0.024, 0.0058, 0.022), buckle_mat, n=5.0, cuts=1)
    out.append(place(female, Vector(p) - along * 0.022, along, o, up))
    male = superbox("BuckleMale", (0.017, 0.0045, 0.02), buckle_mat, n=4.0, cuts=1)
    out.append(place(male, Vector(p) + along * 0.016 - o * 0.001, along, o, up))
    # the tail: the webbing's free end through the male's ladder, hanging down
    tail = []
    nrm = []
    for k in range(5):
        tth = th + (0.03 + 0.012 * k) / R_WEB
        tail.append(at(tth, R_WEB + WEB_T * 2.2 + 0.0004 * k, WEB_Z - 0.004 - 0.016 * k * k / 4))
        nrm.append(radial(tth))
    out.append(band("WebTail", tail, nrm, WEB_W * 0.96, WEB_T, web_mat))
    return out


pieces += buckle()

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
focus = Vector((0.0, -0.05, 1.0))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.1)
for view, loc, tgt, lens in (("close", (0.2, -0.62, 1.16), (0.0, -0.17, 1.03), 50),
                             ("top", (0.3, -0.45, 1.4), (0.0, -0.16, 1.04), 50)):
    tk.render(tk.camera("fp_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
