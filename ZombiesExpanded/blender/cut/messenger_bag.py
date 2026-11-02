"""Messenger bag: an olive waxed-canvas courier bag slung from the right shoulder to the left hip. The webbing strap
runs from a D-ring at the bag's front corner up across the chest, over a padded shoulder pad on the right shoulder and
down across the back to the D-ring at the bag's back corner, with a steel slider and the doubled-back tail on the front
run. The bag rides behind the left hip: a soft box with a big flap over its top and front, two leather straps buckled
down over the flap, a leather maker's patch. Waxed canvas worn pale on the edges and creases, ground-in dirt, mud up
the bottom, blood smeared on the flap and spattered on the strap.

Two parts: the strap on Spine2 ("Spine2#Strap"), the bag on the hips ("Hips#Bag"), so the bag swings with the hips.
The strap lies 0.6 cm off the hit boxes; the bag rests on the hip and leans out just enough to clear the thigh's.

    blender -b --factory-startup --python messenger_bag.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "MessengerBag", "messenger_bag"
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


def leather(name, base, seed=0.0, stitch=0.0, holes=(), worn=0.6, oil=0.5, blood=0.15, dirt=0.6, sawdust=0.5,
            scale=1.0, seams=False):
    """Oil-tanned leather: blotchy tone, pebbled grain, creases, darker handled patches with a sheen, pale scuffs on
    edges and corners, a stitch line `stitch` from the middle of a strap (from its coordinates), punched holes at the
    given distances along it, the seams of sewn pockets (`seams`), then dirt, sawdust and blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    col = g.mix(g.ramp(g.noise(6.0 * scale, detail=5.0, roughness=0.6, vector=P), 0.3, 0.75), base,
                (base[0] * 1.9, base[1] * 1.75, base[2] * 1.5))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(2.2, detail=4.0, vector=P, distortion=0.6), 0.45, 0.7), 0.7), col,
                tk._darker(g, col, 0.5))
    grain = g.ramp(voronoi(g, P, 700.0 * scale), 0.0, 0.6)
    height = g.math("MULTIPLY", grain, 0.18)
    col = g.mix(g.math("MULTIPLY", grain, 0.25), tk._darker(g, col, 0.75), col)
    crease = lines(g, P, (30.0 * scale, 30.0 * scale, 5.0), (0.2, 1.2, 0.4), (0.3, 0.1, 0.7), 0.05, seg=10.0)
    col = g.mix(g.math("MULTIPLY", crease, 0.55), col, tk._darker(g, col, 0.5))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crease, 0.5))
    rough = g.math("ADD", 0.6, g.math("MULTIPLY", g.noise(14.0, detail=3.0, vector=P), 0.1))
    om = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=6.0, roughness=0.6, vector=P, distortion=0.5), 0.45, 0.68), oil)
    col = g.mix(om, col, tk._darker(g, col, 0.55))
    rough = g.mixf(om, rough, 0.36)
    metal = 0.0
    if stitch or holes or seams:
        a, s, side = attr(g)
        if seams:
            # pockets: (round the outline, from back to front, 2); the front panel is sewn to the gusset near its edge
            near = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", s, 0.8)), 0.05, 0.02)
            st = g.math("MULTIPLY", g.math("MULTIPLY", near, g.ramp(side, 1.5, 1.9)),
                        g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", a, 0.006)), 0.5)),
                               0.3, 0.18))
            col = g.mix(st, col, (0.28, 0.23, 0.15))
            height = g.math("ADD", height, g.math("MULTIPLY", st, 0.5))
            welt = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", s, 1.0)), 0.06, 0.0),
                          g.ramp(side, 1.5, 1.9))
            col = g.mix(g.math("MULTIPLY", welt, 0.5), col, tk._darker(g, col, 0.55))
        if stitch:
            edge_w = g.math("ABSOLUTE", a)
            line = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", edge_w, stitch)), 0.0011, 0.0004)
            dash = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", s, 0.0045)), 0.5)), 0.32,
                          0.2)
            st = g.math("MULTIPLY", line, dash)
            groove = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", edge_w, stitch)), 0.0016, 0.0)
            col = g.mix(g.math("MULTIPLY", groove, 0.5), col, tk._darker(g, col, 0.55))
            height = g.math("SUBTRACT", height, g.math("MULTIPLY", groove, 0.6))
            col = g.mix(st, col, (0.3, 0.25, 0.17))
            rough = g.mixf(st, rough, 0.7)
            height = g.math("ADD", height, g.math("MULTIPLY", st, 0.6))
            # burnished, darker edges
            bur = g.ramp(edge_w, stitch - 0.0015, stitch + 0.0035)
            col = g.mix(g.math("MULTIPLY", bur, 0.6), col, tk._darker(g, col, 0.6))
            rough = g.mixf(bur, rough, 0.45)
        for h in holes:
            cv = g.node("ShaderNodeCombineXYZ")
            g.links.new(a, cv.inputs[0])
            g.links.new(s, cv.inputs[1])
            dist = g.node("ShaderNodeVectorMath", operation="DISTANCE")
            g.links.new(cv.outputs[0], dist.inputs[0])
            dist.inputs[1].default_value = (0.0, h, 0.0)
            dd = tk._sock(dist.outputs, "Value")
            hole = g.ramp(dd, 0.0032, 0.0024)
            ring = g.math("MULTIPLY", g.ramp(dd, 0.0055, 0.0034), g.math("SUBTRACT", 1.0, hole))
            col = g.mix(g.math("MULTIPLY", ring, 0.6), col, tk._darker(g, col, 0.5))
            col = g.mix(hole, col, (0.012, 0.009, 0.007))
            rough = g.mixf(hole, rough, 0.9)
            height = g.math("SUBTRACT", height, g.math("MULTIPLY", hole, 1.5))
    # pale scuffs where it rubs, and the raw edges
    worn_m = g.math("MULTIPLY", g.ramp(g.edges(0.003), 0.08, 0.3), g.ramp(g.noise(30.0, detail=4.0, vector=P), 0.35, 0.55))
    sc = scratches(g, P, 0.03)
    worn_m = g.math("MAXIMUM", g.math("MULTIPLY", worn_m, worn), g.math("MULTIPLY", sc, 0.5 * worn))
    col = g.mix(worn_m, col, tuple(c * 2.3 + 0.025 for c in base))
    rough = g.mixf(worn_m, rough, 0.75)
    col, rough, metal, height = grunge(g, P, col, rough, metal, height, dirt=dirt, grime=0.8, dust=0.1, specks=0.5,
                                       sawdust=sawdust, blood=blood, mud=0.4, mud_top=0.88,
                                       dirt_cols=((0.03, 0.02, 0.012), (0.08, 0.058, 0.036)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.002))



def pocket(name, w, h, d, mat, top_mat, bulge=0.01, r_bot=0.022, taper=0.005, step=0.042, sag=0.0):
    """A sewn pocket in local coordinates (x across, y out, z up): its back on y = 0 from z = 0 to h, straight gusset
    sides, the bottom corners rounded, the front bulging (and sagging `sag` at its top edge, open); the top strip, the
    opening, takes top_mat."""
    out = []

    def run(a, b, n, top=False):
        for t in range(n):
            out.append((a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n, top))

    def arc(cx, cz, a0, a1, n):
        for t in range(n):
            a = a0 + (a1 - a0) * t / n
            out.append((cx + r_bot * math.cos(a), cz + r_bot * math.sin(a), False))
    n_top = max(2, round(w / step))
    n_side = max(1, round((h - r_bot) / step))
    n_bot = max(1, round((w - 2 * r_bot) / step))
    run((w / 2, h), (-w / 2, h), n_top, True)
    run((-w / 2, h), (-w / 2, r_bot), n_side)
    arc(-w / 2 + r_bot, r_bot, math.pi, 1.5 * math.pi, 3)
    run((-w / 2 + r_bot, 0.0), (w / 2 - r_bot, 0.0), n_bot)
    arc(w / 2 - r_bot, r_bot, 1.5 * math.pi, 2 * math.pi, 3)
    run((w / 2, r_bot), (w / 2, h), n_side)
    cz = h * 0.45
    bm = bmesh.new()
    back, front, inner = [], [], []
    for x, z, top in out:
        back.append(bm.verts.new((x, 0.0, z)))  # created back, front, inner per point (the attribute order)
        fx = x * (1 - taper / (w / 2))
        fz = cz + (z - cz) * (1 - taper / (h / 2))
        if top or abs(z - h) < 1e-6:
            fz -= sag * (1 - (2 * x / w) ** 2)
        front.append(bm.verts.new((fx, d, fz)))
        inner.append(bm.verts.new((x * 0.55, d + bulge * 0.8, cz + (z - cz) * 0.55)))
    c_front = bm.verts.new((0.0, d + bulge, cz))
    c_back = bm.verts.new((0.0, 0.0, cz))
    n = len(out)
    along = [0.0]
    for i in range(1, n):
        along.append(along[-1] + math.dist(out[i][:2], out[i - 1][:2]))
    vals = [v for i in range(n) for v in ((along[i], 0.0, 2.0), (along[i], 1.0, 2.0), (along[i], 1.5, 2.0))]
    vals += [(0.0, 2.0, 2.0), (0.0, -1.0, 2.0)]
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((back[i], back[j], front[j], front[i]))
        if i < n_top:
            f.material_index = 1
        bm.faces.new((front[i], front[j], inner[j], inner[i]))
        bm.faces.new((inner[i], inner[j], c_front))
        bm.faces.new((back[j], back[i], c_back))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    obj.data.materials.append(top_mat)
    set_attr(obj, vals)
    return tk.smooth(obj, 62)




# ---------------------------------------------------------------- materials

OLIVE = (0.04, 0.044, 0.022)


def canvas(name, base, seed=0.0, flap=False, blood=0.3, mud=0.6, wax=0.5):
    """Waxed cotton canvas: blotchy wax (darker, with a sheen), a fine weave, creases worn pale, seams round the
    pockets' gussets, the maker's leather patch on the flap; then dirt, mud up the bottom, dust and blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    col = g.mix(g.ramp(g.noise(5.0, detail=5.0, vector=P, distortion=0.4), 0.3, 0.75), base, tuple(c * 1.6 for c in base))
    wm = g.math("MULTIPLY", g.ramp(g.noise(2.5, detail=6.0, roughness=0.6, vector=P, distortion=0.8), 0.45, 0.65), wax)
    col = g.mix(wm, col, tk._darker(g, col, 0.6))
    rough = g.mixf(wm, 0.78, 0.46)
    weave = g.math("ADD", g.math("SINE", g.math("MULTIPLY", g.separate(P)[0], 2600.0)),
                   g.math("SINE", g.math("MULTIPLY", g.separate(P)[2], 2600.0)))
    height = g.math("ADD", g.math("MULTIPLY", weave, 0.06), g.math("MULTIPLY", g.noise(300.0, detail=3.0, vector=P), 0.15))
    crease = lines(g, P, (26.0, 26.0, 6.0), (0.3, 1.1, 0.5), (0.2, 0.4, 0.1), 0.06, seg=9.0)
    crease2 = lines(g, P, (9.0, 9.0, 40.0), (1.2, 0.2, 0.9), (0.6, 0.1, 0.3), 0.05, seg=7.0)
    cr = g.math("MAXIMUM", crease, crease2)
    col = g.mix(g.math("MULTIPLY", cr, 0.7), col, tk.grade(g, col, 0.55, 1.9))  # wax cracked pale along creases
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", cr, 0.6))
    rough = g.mixf(cr, rough, 0.85)
    metal = 0.0
    a, s, kind = attr(g)
    # pockets (kind 2): stitched seams where the gussets meet the front and back panels
    pk = g.ramp(kind, 1.5, 1.9)
    for at_ in (0.06, 0.94):
        st = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", s, at_)), 0.03, 0.012),
                    g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", a, 0.006)), 0.5)),
                           0.3, 0.18))
        st = g.math("MULTIPLY", st, pk)
        col = g.mix(st, col, (0.12, 0.11, 0.075))
    if flap:
        # the flap (kind 3): a bound edge and the leather patch
        fl = g.ramp(kind, 2.5, 2.9)
        patch = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", a), 0.037, 0.035),
                                          g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", s, PATCH_S)), 0.022, 0.02)), fl)
        lc = g.mix(g.ramp(g.noise(30.0, vector=P), 0.3, 0.7), (0.06, 0.03, 0.014), (0.1, 0.055, 0.028))
        cx = g.node("ShaderNodeCombineXYZ")
        g.links.new(a, cx.inputs[0])
        g.links.new(g.math("SUBTRACT", s, PATCH_S), cx.inputs[1])
        rr = tk._sock(g.node("ShaderNodeVectorMath", operation="LENGTH").outputs, "Value")
        ln = rr.node
        g.links.new(cx.outputs[0], ln.inputs[0])
        ring = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", rr, 0.012)), 0.0018, 0.0008)
        border = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", a), 0.031, 0.0325),
                                           g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", s, PATCH_S)), 0.0165, 0.018)),
                        g.ramp(g.math("FRACT", g.math("DIVIDE", g.math("ADD", a, s), 0.005)), 0.35, 0.5))
        lc = g.mix(g.math("MULTIPLY", ring, 0.8), lc, (0.03, 0.015, 0.008))
        lc = g.mix(g.math("MULTIPLY", border, 0.8), lc, (0.2, 0.16, 0.1))
        col = g.mix(patch, col, lc)
        rough = g.mixf(patch, rough, 0.55)
        height = g.math("ADD", height, g.math("MULTIPLY", patch, g.math("SUBTRACT", 0.6, g.math("MULTIPLY", ring, 0.8))))
        binding = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", a), FLAP_HW - 0.009, FLAP_HW - 0.006), fl)
        binding = g.math("MAXIMUM", binding, g.math("MULTIPLY", g.ramp(s, FLAP_S1 - 0.009, FLAP_S1 - 0.006), fl))
        col = g.mix(binding, col, tk._darker(g, col, 0.55))
        height = g.math("ADD", height, g.math("MULTIPLY", binding, 0.3))
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.08, 0.32), g.ramp(g.noise(28.0, vector=P), 0.33, 0.55))
    col = g.mix(worn, col, (0.12, 0.115, 0.08))
    rough = g.mixf(worn, rough, 0.88)
    col, rough, metal, height = grunge(g, P, col, rough, metal, height, dirt=0.7, grime=0.9, dust=0.3, specks=0.6,
                                       blood=blood, mud=mud, mud_top=0.92,
                                       dirt_cols=((0.03, 0.027, 0.018), (0.075, 0.065, 0.045)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.0015))


def webbing(name, base, seed=0.0, blood=0.3):
    """Nylon webbing: fine ribs down its length, fuzzy paler edges, grime and blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    a, s, side = attr(g)
    rib = g.math("SINE", g.math("DIVIDE", a, 0.0005))
    tw = g.math("SINE", g.math("DIVIDE", g.math("ADD", s, g.math("MULTIPLY", a, 0.7)), 0.0012))
    col = g.mix(g.math("MULTIPLY", g.math("ADD", rib, 1.0), 0.2), base, tuple(c * 1.5 for c in base))
    col = g.mix(g.ramp(g.noise(4.0, detail=4.0, vector=P), 0.3, 0.7), col, tk._darker(g, col, 0.75))
    height = g.math("ADD", g.math("MULTIPLY", rib, 0.2), g.math("MULTIPLY", tw, 0.1))
    fuzz = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", a), STRAP_W / 2 - 0.003, STRAP_W / 2),
                  g.ramp(g.noise(60.0, vector=P), 0.3, 0.6))
    col = g.mix(fuzz, col, tuple(c * 2.4 + 0.02 for c in base))
    rough = g.math("ADD", 0.62, g.math("MULTIPLY", fuzz, 0.25))
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.6, grime=0.8, dust=0.2, specks=0.5,
                                       blood=blood, mud=0.4, mud_top=0.95)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.001))


# ---------------------------------------------------------------- the body round the hips

HC = np.array([0.0, 0.015])  # the hips' hit box axis (x, y)
HIPS = ("Hips", "LeftUpLeg", "RightUpLeg", "Spine2")
STRAP_BONES = ("Spine2", "Hips", "LeftArm", "RightArm", "Head", "LeftUpLeg", "RightUpLeg")


def radial(th):
    return np.array([math.sin(th), -math.cos(th), 0.0])


def at(th, r, z):
    return np.array([HC[0] + r * math.sin(th), HC[1] - r * math.cos(th), z])


def lean_out(o, z, tilt, z_hinge):
    if z < z_hinge:
        o += (z_hinge - z) * math.tan(tilt)
    return o


# The bag: a soft box resting on the hip behind the left side; its back curves round a radius flatter than the
# body's, so it touches at its middle and its ends stand off
TH_BAG = math.radians(104.0)
R_CONTACT = 0.159 + 0.009
R_BEND = 0.3
BAG_W, BAG_H, BAG_D = 0.31, 0.24, 0.078
BAG_TOP = 1.07
BAG_BOT = BAG_TOP - BAG_H
HINGE = 1.0
BEND_C = HC + radial(TH_BAG)[:2] * (R_CONTACT - R_BEND)


def bag_point(u, o, z, tilt):
    phi = TH_BAG + u / R_BEND
    r = R_BEND + lean_out(o, z, tilt, HINGE)
    return np.array([BEND_C[0] + r * math.sin(phi), BEND_C[1] - r * math.cos(phi), z])


def bend_bag(obj, tilt):
    for v in obj.data.vertices:
        v.co = Vector(bag_point(v.co.x, v.co.y, v.co.z, tilt))
    obj.data.update()
    return obj


def bag_frame(u, o, z, tilt):
    e = 1e-4
    p = Vector(bag_point(u, o, z, tilt))
    a = (Vector(bag_point(u + e, o, z, tilt)) - Vector(bag_point(u - e, o, z, tilt))).normalized()
    up = (Vector(bag_point(u, o, z + e, tilt)) - Vector(bag_point(u, o, z - e, tilt))).normalized()
    out = a.cross(up).normalized()
    up = out.cross(a).normalized()
    return p, a, out, up


def bag_lean(clear=0.008):
    for deg in np.arange(0.0, 30.0, 0.5):
        tilt = math.radians(deg)
        pts = [bag_point(u, 0.0, z, tilt) for u in np.linspace(-BAG_W / 2, BAG_W / 2, 9)
               for z in np.linspace(BAG_BOT, BAG_TOP, 8)]
        if sdf(pts, HIPS).min() >= clear:
            return tilt
    return math.radians(30.0)


TILT = bag_lean()
print("[%s] the bag leans out %.1f degrees below the hip" % (SCRIPT, math.degrees(TILT)))

canvas_mat = canvas("BagCanvas", OLIVE, seed=1.0)
FLAP_HW = BAG_W / 2 + 0.005
FLAP_S1 = 0.255  # the flap's length from where it's sewn at the back, over the top and down the front
PATCH_S = 0.165
flap_mat = canvas("BagFlap", OLIVE, seed=2.0, flap=True, blood=0.45)
STRAP_W, STRAP_T = 0.045, 0.0032
web_mat = webbing("StrapWebbing", (0.028, 0.03, 0.017), seed=3.0)
pad_mat = canvas("ShoulderPad", (0.02, 0.021, 0.014), seed=4.0, mud=0.0, wax=0.2, blood=0.4)
leather_mat = leather("BagLeather", (0.05, 0.024, 0.01), seed=5.0, worn=0.7, sawdust=0.0, blood=0.2)
steel_mat = steel("BagSteel", (0.2, 0.2, 0.195), seed=6.0, rust=0.5, polish=0.7)

bag_pieces, strap_pieces = [], []

# ---------------------------------------------------------------- the bag

body = pocket("BagBody", BAG_W, BAG_H, BAG_D, canvas_mat, canvas_mat, bulge=0.016, r_bot=0.04, taper=0.007, step=0.05)
body.data.transform(Matrix.Translation((0.0, 0.0, BAG_BOT)))
bag_pieces.append(bend_bag(body, TILT))


def front_o(u, z):
    """How far out the body's bulging front is at (u, z) (a fair match to pocket()'s shape)."""
    hw, hh = BAG_W / 2, BAG_H / 2
    cz = BAG_BOT + BAG_H * 0.45
    fu = min(1.0, max(0.0, (1.0 - abs(u) / hw) / 0.45))
    fz = min(1.0, max(0.0, (1.0 - abs(z - cz) / hh) / 0.45))
    return BAG_D + 0.016 * fu * fz * 0.85


def flap():
    """The flap: sewn along the back's top edge, over the top and down two thirds of the front, the corners rounded."""
    path = [(0.003, BAG_TOP + 0.0), (0.02, BAG_TOP + 0.004), (BAG_D * 0.6, BAG_TOP + 0.005), (BAG_D - 0.004, BAG_TOP),
            (BAG_D + 0.006, BAG_TOP - 0.014)]
    for z in np.linspace(BAG_TOP - 0.03, BAG_TOP - 0.16, 5):
        path.append((None, z))
    us = np.linspace(-FLAP_HW, FLAP_HW, 9)
    thick = 0.0035
    rows = []
    for o, z in path:
        rows.append([(u, (front_o(u, z) + 0.005 if o is None else o), z) for u in us])
    # rounded bottom corners
    last = rows[-1]
    rows[-1] = [(u, o, z + 0.03 * (abs(u) / FLAP_HW) ** 6) for u, o, z in last]
    s_of = [0.0]
    for j in range(1, len(rows)):
        mid0, mid1 = rows[j - 1][4], rows[j][4]
        s_of.append(s_of[-1] + math.dist(mid0[1:], mid1[1:]))
    bm = bmesh.new()
    nu, nv = len(us), len(rows)
    out_v, in_v, vals = [], [], []
    for j in range(nv):
        # the outward normal of the path (o, z) here
        a = np.array(rows[max(j - 1, 0)][4][1:])
        b = np.array(rows[min(j + 1, nv - 1)][4][1:])
        t = (b - a) / np.linalg.norm(b - a)
        n2 = np.array([-t[1], t[0]])
        if n2[0] + n2[1] < 0:
            n2 = -n2
        o_row, i_row = [], []
        for i, (u, o, z) in enumerate(rows[j]):
            o_row.append(bm.verts.new((u, o + n2[0] * thick, z + n2[1] * thick)))
            i_row.append(bm.verts.new((u, o, z)))
            vals.append((u, s_of[j], 3.0))
            vals.append((u, s_of[j], 3.0))
        out_v.append(o_row)
        in_v.append(i_row)
    for j in range(nv - 1):
        for i in range(nu - 1):
            bm.faces.new((out_v[j][i], out_v[j][i + 1], out_v[j + 1][i + 1], out_v[j + 1][i]))
            bm.faces.new((in_v[j][i], in_v[j + 1][i], in_v[j + 1][i + 1], in_v[j][i + 1]))
    ring = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)] + \
        [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)]
    for k in range(len(ring)):
        (i0, j0), (i1, j1) = ring[k], ring[(k + 1) % len(ring)]
        bm.faces.new((out_v[j0][i0], out_v[j1][i1], in_v[j1][i1], in_v[j0][i0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("BagFlap", bm, flap_mat)
    set_attr(obj, vals)
    tk.smooth(obj, 50)
    return bend_bag(obj, TILT)


bag_pieces.append(flap())


def buckle_strap(k, u):
    """A leather strap riveted to the flap and buckled down onto the bag's front."""
    zs = np.linspace(BAG_TOP - 0.1, BAG_TOP - 0.205, 6)
    pts, nrm = [], []
    for z in zs:
        on_flap = z > BAG_TOP - 0.155
        o = front_o(u, z) + (0.0113 if on_flap else 0.0028)
        pts.append((u, o, z))
        nrm.append((0.0, 1.0, 0.0))
    st = band("BuckleStrap%d" % k, pts, nrm, 0.024, 0.0035, leather_mat)
    out = [bend_bag(st, TILT)]
    # the buckle: a steel frame round the strap below the flap, its prong over the strap
    zc = BAG_TOP - 0.178
    oc = front_o(u, zc) + 0.004
    w, h, c = 0.032, 0.024, 0.005
    loop = [(-w / 2 + c, -h / 2), (w / 2 - c, -h / 2), (w / 2, -h / 2 + c), (w / 2, h / 2 - c), (w / 2 - c, h / 2),
            (-w / 2 + c, h / 2), (-w / 2, h / 2 - c), (-w / 2, -h / 2 + c)]
    fr = tube("Buckle%d" % k, [(u + a, oc, zc + b) for a, b in loop], 0.0022, steel_mat, sides=4, closed=True)
    out.append(bend_bag(fr, TILT))
    pr = tube("Prong%d" % k, [(u, oc, zc - h / 2), (u, oc + 0.003, zc), (u, oc + 0.001, zc + h / 2 + 0.004)], 0.0016,
              steel_mat, sides=4)
    out.append(bend_bag(pr, TILT))
    return out


for k, u in enumerate((-0.085, 0.085)):
    bag_pieces += buckle_strap(k, u)

# ---------------------------------------------------------------- the strap's path: front corner, right shoulder, back corner


def grad(P, bones):
    e = 1e-4
    P = np.atleast_2d(P)
    gr = np.stack([sdf(P + dv, bones) - sdf(P - dv, bones) for dv in np.eye(3) * e], axis=1)
    return gr / np.maximum(np.linalg.norm(gr, axis=1), 1e-9)[:, None]


def push_out(P, clear, bones, iters=12):
    P = np.array(P, float)
    for _ in range(iters):
        d = sdf(P, bones)
        m = d < clear
        if not m.any():
            break
        P[m] += grad(P[m], bones) * (clear - d[m])[:, None]
    return P


def resample(P, step):
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(round(L[-1] / step)) + 1)
    t = np.linspace(0.0, L[-1], n)
    return np.stack([np.interp(t, L, P[:, k]) for k in range(3)], axis=1)


CLR = 0.006 + STRAP_T / 2


def relax(p0, p1, step=0.012, iters=600):
    """A strap pulled taut between p0 and p1 over the hit boxes."""
    P = push_out(resample(np.linspace(p0, p1, 30), step), CLR, STRAP_BONES)
    for it in range(iters):
        Q = P.copy()
        Q[1:-1] = 0.5 * (P[:-2] + P[2:])
        P = push_out(Q, CLR, STRAP_BONES)
        P[0], P[-1] = p0, p1
        if it % 60 == 59:
            P = resample(P, step)
    return resample(P, step)


def shoulder_top(x, y):
    lo, hi = 1.4, 1.75
    for _ in range(40):
        mid = (lo + hi) / 2
        if sdf([[x, y, mid]], STRAP_BONES)[0] > CLR:
            hi = mid
        else:
            lo = mid
    return np.array([x, y, hi])


# The rings at the bag's top corners, and where the strap comes into them
RING_U = BAG_W / 2 - 0.016
ring_f = bag_frame(-RING_U, BAG_D * 0.5, BAG_TOP + 0.024, TILT)
ring_b = bag_frame(RING_U, BAG_D * 0.5, BAG_TOP + 0.024, TILT)
SH = shoulder_top(-0.125, 0.055)
front_run = relax(np.array(ring_f[0]) + np.array([0, 0, 0.004]), SH)
back_run = relax(SH, np.array(ring_b[0]) + np.array([0, 0, 0.004]))
path = np.vstack([front_run, back_run[1:]])
i_sh = len(front_run) - 1
# Pull the whole strap taut together: over the shoulder it may slide front to back and settle, but not toward the
# neck or off the shoulder (its x there stays put), so it rounds the shoulder instead of kinking on it
for it in range(800):
    Q = path.copy()
    Q[1:-1] = 0.5 * (path[:-2] + path[2:])
    Q[i_sh, 0] = SH[0]
    path = push_out(Q, CLR, STRAP_BONES)
    path[0], path[-1] = front_run[0], back_run[-1]
nrm = grad(path, STRAP_BONES)


def lift_edges(P, N, width, thick, clear, bones):
    """Lifts a strap off the body wherever an edge of it digs in (a flat strap over a rounded body), then evens it."""
    P = P.copy()
    for rnd_ in range(4):
        for i in range(len(P)):
            T = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            T /= np.linalg.norm(T)
            Nn = N[i] - T * (N[i] @ T)
            Nn /= np.linalg.norm(Nn)
            W = np.cross(T, Nn)
            probe = np.array([P[i] + W * k * width / 2 - Nn * thick / 2 for k in (-1, -0.5, 0, 0.5, 1)])
            short = clear - sdf(probe, bones).min()
            if short > 0:
                P[i] = P[i] + Nn * short
        if rnd_ < 3:  # even out the bumps the lifting made (the last pass only lifts)
            P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
    return P


path = lift_edges(path, nrm, STRAP_W, STRAP_T, 0.005, STRAP_BONES)
nrm = grad(path, STRAP_BONES)
for _ in range(6):  # the nearest hit box changes along the strap; ease the strap's roll between them
    nrm[1:-1] = 0.25 * nrm[:-2] + 0.5 * nrm[1:-1] + 0.25 * nrm[2:]
nrm /= np.linalg.norm(nrm, axis=1)[:, None]
s_all = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
strap_pieces.append(band("Strap", path, nrm, STRAP_W, STRAP_T, web_mat))


def path_frame(i):
    T = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
    T /= np.linalg.norm(T)
    N = nrm[i] - T * (nrm[i] @ T)
    N /= np.linalg.norm(N)
    return path[i], T, N, np.cross(T, N)


# The shoulder pad: a padded sleeve round the strap where it crosses the shoulder, lifted where its edges dig in
PAD_W, PAD_T = 0.06, 0.01
lo_i = int(np.searchsorted(s_all, s_all[i_sh] - 0.1))
hi_i = int(np.searchsorted(s_all, s_all[i_sh] + 0.1))
pp, pn = [], []
for i in range(lo_i, hi_i + 1):
    p, T, N, W = path_frame(i)
    q = p + N * (PAD_T / 2 - STRAP_T / 2 + 0.0005)
    probe = np.array([q + W * k * PAD_W / 2 - N * PAD_T / 2 for k in (-1, -0.5, 0, 0.5, 1)])
    short = 0.005 - sdf(probe, STRAP_BONES).min()
    if short > 0:
        q = q + N * short
    pp.append(q)
    pn.append(N)
PADDED = [(-0.5, 0.0), (-0.42, -0.5), (0.42, -0.5), (0.5, 0.0), (0.42, 0.5), (-0.42, 0.5)]
strap_pieces.append(band("ShoulderPad", pp, pn, PAD_W, PAD_T, pad_mat, profile=PADDED))

# The slider on the front run and the strap's doubled-back tail below it
i_sl = int(np.searchsorted(s_all, 0.2))
p, T, N, W = path_frame(i_sl)
w, h, c = STRAP_W + 0.008, 0.012, 0.003
loop = [(-w / 2 + c, -h / 2), (w / 2 - c, -h / 2), (w / 2, -h / 2 + c), (w / 2, h / 2 - c), (w / 2 - c, h / 2),
        (-w / 2 + c, h / 2), (-w / 2, h / 2 - c), (-w / 2, -h / 2 + c)]
strap_pieces.append(tube("Slider", [p + W * a + N * (b + STRAP_T * 0.5) for a, b in loop], 0.0024, steel_mat, sides=4,
                         closed=True))
bar = tube("SliderBar", [p - W * (w / 2) + N * STRAP_T * 1.5, p + W * (w / 2) + N * STRAP_T * 1.5], 0.0024, steel_mat,
           sides=4)
strap_pieces.append(bar)
i_t0 = int(np.searchsorted(s_all, 0.2 - 0.13))
tail = [path[i] + nrm[i] * (STRAP_T * 1.1) for i in range(i_t0, i_sl + 1)]
strap_pieces.append(band("StrapTail", tail, [nrm[i] for i in range(i_t0, i_sl + 1)], STRAP_W * 0.98, STRAP_T, web_mat))

# ---------------------------------------------------------------- the rings and the tabs that hold them (on the bag)


def ring_at(name, frame, end_dir):
    """A steel D-ring round the strap's end (its plane square to the strap), with a webbing tab down to the bag."""
    p, a, o, up = frame
    T = Vector(end_dir).normalized()
    N = (o - T * o.dot(T)).normalized()
    W = T.cross(N)
    w, h, c = STRAP_W + 0.008, 0.016, 0.004
    loop = [(-w / 2 + c, -h / 2), (w / 2 - c, -h / 2), (w / 2, -h / 2 + c), (w / 2, h / 2 - c), (w / 2 - c, h / 2),
            (-w / 2 + c, h / 2), (-w / 2, h / 2 - c), (-w / 2, -h / 2 + c)]
    ring = tube(name, [p + W * x + N * y for x, y in loop], 0.0028, steel_mat, sides=5, closed=True)
    # the tab: a doubled webbing loop through the ring, sewn into the bag's top corner under the flap
    tab_pts = [p + up * 0.004, p - up * 0.012, p - up * 0.03]
    tab = band(name + "Tab", tab_pts, [o, o, o], 0.026, 0.0035, web_mat)
    return [ring, tab]


bag_pieces += ring_at("RingFront", ring_f, front_run[1] - front_run[0])
bag_pieces += ring_at("RingBack", ring_b, back_run[-2] - back_run[-1])

# ---------------------------------------------------------------- checks, export, previews

pieces = []
for o in bag_pieces:
    bake_transform(o)
    fix_normals(o)
    pieces.append(zk.on(o, "Hips", "Bag"))
for o in strap_pieces:
    bake_transform(o)
    fix_normals(o)
    pieces.append(zk.on(o, "Spine2", "Strap"))
for o in pieces:
    V = np.array([v.co[:] for v in o.data.vertices])
    print("[%s] %-14s %4d tris, %.1f mm off the hit boxes" % (SCRIPT, o.name, tri_count([o]), sdf(V).min() * 1000))
for label, group in (("bag", bag_pieces), ("strap", strap_pieces)):
    V = np.array([v.co[:] for o in group for v in o.data.vertices])
    print("[%s] %s: %d triangles, bounds %s to %s, closest %.1f mm" % (
        SCRIPT, label, tri_count(group), np.round(V.min(0), 3), np.round(V.max(0), 3), sdf(V).min() * 1000))

for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS)
for o in BODY:
    o.hide_render = False
focus = Vector((0.03, 0.03, 1.2))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.6)
for view, loc, tgt, lens in (("bag", (0.85, -0.25, 1.15), (0.17, 0.06, 0.96), 45),
                             ("bagback", (0.55, 0.75, 1.2), (0.12, 0.12, 0.98), 45),
                             ("shoulder", (-0.55, -0.45, 1.85), (-0.1, 0.03, 1.5), 45)):
    tk.render(tk.camera("mb_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
