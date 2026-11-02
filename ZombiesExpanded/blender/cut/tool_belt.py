"""Tool belt: a carpenter's oil-tanned leather tool belt round the zombie's hips, buckled at the front with a heavy
double-prong roller buckle, the tongue held in a keeper. Two leather pouches hang at the hips, each a main pocket with
a smaller one sewn on its front: a carpenter's pencil and a screwdriver stick out of the right one, a chisel out of
the left. Behind the left pouch a steel hammer loop holds a claw hammer by its head, the handle hanging down the outside
of the thigh; behind the right one a tape measure is clipped on the belt. Dark sweat-stained leather, pale scuffed edges,
waxed stitching, dirt, sawdust and a little blood.

The belt is 0.7 cm off the hips' hit box; the pouches and the hammer hang tilted out just enough to clear the thighs'
hit boxes. One part on the Hips bone ("Hips#Belt").

    blender -b --factory-startup --python tool_belt.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PIECE = "ToolBelt", "tool_belt", "Hips", "Belt"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex (across, along, side) strap coordinates the materials print by


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



# ---------------------------------------------------------------- the belt round the hips

HC = np.array([0.0, 0.015])  # the hips' hit box axis (x, y)
HIPS = ("Hips", "LeftUpLeg", "RightUpLeg", "Spine2")
CLEAR = 0.007
BELT_W, BELT_T = 0.052, 0.0055


def belt_z(th):
    """The belt's middle height round the waist (th: 0 front, +90 the zombie's left): it sags at the front."""
    return 0.998 - 0.009 * math.cos(th)


def radial(th):
    return np.array([math.sin(th), -math.cos(th), 0.0])


def at(th, r, z):
    return np.array([HC[0] + r * math.sin(th), HC[1] - r * math.cos(th), z])


def inner_radius(th, z0, z1, clear=CLEAR):
    """The smallest radius round the hips axis at which a band between heights z0 and z1 clears the hit boxes."""
    for r in np.arange(0.12, 0.35, 0.0005):
        if sdf([at(th, r, z0), at(th, r, (z0 + z1) / 2), at(th, r, z1)], HIPS).min() >= clear:
            return r
    return 0.35


N_BELT = 26
THS = np.linspace(0, 2 * math.pi, N_BELT, endpoint=False)
R_IN = np.array([inner_radius(t, belt_z(t) - BELT_W / 2, belt_z(t) + BELT_W / 2) for t in THS])
R_IN = np.maximum(R_IN, np.convolve(np.r_[R_IN[-2:], R_IN, R_IN[:2]], np.ones(5) / 5, "valid"))
R_BELT = float(R_IN.mean())  # nearly round: the hips' box is a vertical capsule


def belt_r(th):
    return float(np.interp(th % (2 * math.pi), np.r_[THS, 2 * math.pi], np.r_[R_IN, R_IN[0]]))


BROWN = (0.058, 0.026, 0.01)
pieces = []
belt_mat = leather("BeltLeather", BROWN, seed=1.0, stitch=BELT_W / 2 - 0.0045, worn=0.7)
tongue_mat = leather("BeltTongue", BROWN, seed=1.6, stitch=BELT_W / 2 - 0.0045, worn=0.8,
                     holes=(0.052, 0.077, 0.102, 0.127))
pouch_mat = leather("PouchLeather", (0.068, 0.032, 0.012), seed=2.0, worn=0.75, oil=0.6, blood=0.25, sawdust=0.7,
                    scale=1.3, seams=True)
inside_mat = leather("PouchInside", (0.022, 0.012, 0.007), seed=2.5, worn=0.2, oil=0.2, blood=0.0, sawdust=1.0)
steel_mat = steel("BeltSteel", (0.16, 0.16, 0.155), seed=3.0, rust=0.55)

belt_pts = [at(t, belt_r(t) + BELT_T / 2, belt_z(t)) for t in THS]
belt = band("Belt", belt_pts, [radial(t) for t in THS], BELT_W, BELT_T, belt_mat, closed=True)
pieces.append(belt)

# The tongue: the belt's free end, through the buckle at the front and on to the left, laid over the belt
tth = np.radians(np.linspace(-6.0, 40.0, 9))
tw = [BELT_W * 0.985] * 7 + [BELT_W * 0.7, BELT_W * 0.22]
tongue = band("Tongue", [at(t, belt_r(t) + BELT_T * 1.5 + 0.0004, belt_z(t)) for t in tth], [radial(t) for t in tth],
              BELT_W, BELT_T * 0.9, tongue_mat, widths=tw)
pieces.append(tongue)


def keeper(th):
    """A leather loop round the belt and its tongue."""
    r0, r1 = belt_r(th) - 0.0018, belt_r(th) + BELT_T * 2.0 + 0.0025
    z0, z1 = belt_z(th) - BELT_W / 2 - 0.0022, belt_z(th) + BELT_W / 2 + 0.0022
    c = 0.003
    rz = [(r1 - c, z0), (r1, z0 + c), (r1, z1 - c), (r1 - c, z1), (r0 + c, z1), (r0, z1 - c), (r0, z0 + c), (r0 + c, z0)]
    rc, zc = (r0 + r1) / 2, (z0 + z1) / 2
    pts = [at(th, r, z) for r, z in rz]
    nrm = [radial(th) * (r - rc) / 0.01 + np.array([0, 0, (z - zc) / 0.03]) for r, z in rz]
    return band("Keeper", pts, nrm, 0.016, 0.0028, belt_mat, closed=True, smooth_angle=60)


pieces.append(keeper(math.radians(15.0)))


def buckle():
    """A heavy double-prong roller buckle at the front."""
    th = math.radians(-1.5)
    r = belt_r(th) + BELT_T * 2.0 + 0.0035
    o = Vector(at(th, r, belt_z(th)))
    side = Vector((math.cos(th), math.sin(th), 0.0))
    out = Vector(radial(th))
    up = Vector((0.0, 0.0, 1.0))
    w, h, c = 0.05, 0.072, 0.008
    loop = [(-w / 2 + c, -h / 2), (w / 2 - c, -h / 2), (w / 2, -h / 2 + c), (w / 2, h / 2 - c), (w / 2 - c, h / 2),
            (-w / 2 + c, h / 2), (-w / 2, h / 2 - c), (-w / 2, -h / 2 + c)]

    def p(a, b, d=0.0):
        # the frame curves a little with the belt
        return o + side * a + up * b + out * (d - a * a / (2 * r))
    frame = tube("BuckleFrame", [p(a, b) for a, b in loop], 0.0032, steel_mat, sides=5, closed=True)
    roller = tk.cylinder("BuckleRoller", 0.0058, -h / 2 + 0.006, h / 2 - 0.006, steel_mat, segments=6)
    place(roller, p(w / 2, 0.0, 0.001), side, out, up)
    prongs = []
    for k, b in enumerate((-0.014, 0.014)):
        prongs.append(tube("BuckleProng%d" % k, [p(-w / 2, b, 0.001), p(0.0, b, 0.0035), p(w / 2 + 0.004, b, 0.0012)],
                           0.0024, steel_mat, sides=4))
    return [frame, roller] + prongs


pieces += buckle()


# ---------------------------------------------------------------- pouches, hammer loop, tape (bent round the hips)

def lean_out(o, z, tilt, z_hinge):
    if z_hinge is not None and z < z_hinge:
        o += (z_hinge - z) * math.tan(tilt)
    return o


def bend(obj, th_c, r_ref, tilt=0.0, z_hinge=None):
    """Bends an object built in local coordinates (x along the belt at radius r_ref, y out, z up) round the hips at
    angle th_c; below z_hinge everything leans out by `tilt` (radians), to hang clear of the thighs."""
    for v in obj.data.vertices:
        u, o, z = v.co
        v.co = Vector(at(th_c + u / r_ref, r_ref + lean_out(o, z, tilt, z_hinge), z))
    obj.data.update()
    return obj


def bent_frame(th_c, r_ref, u, o, z, tilt=0.0, z_hinge=None):
    """The world point and axes (along, out, up) at local (u, o, z) of the same bend."""
    e = 1e-4

    def f(uu, oo, zz):
        return Vector(at(th_c + uu / r_ref, r_ref + lean_out(oo, zz, tilt, z_hinge), zz))
    p = f(u, o, z)
    a = (f(u + e, o, z) - f(u - e, o, z)).normalized()
    up = (f(u, o, z + e) - f(u, o, z - e)).normalized()
    out = a.cross(up).normalized()
    up = out.cross(a).normalized()
    return p, a, out, up


def lean_needed(th_c, r_ref, half_w, z_top, z_bot, o_back, clear=0.008):
    """The smallest outward lean (radians, hinged at z_top) that keeps a panel's back clear of the thighs."""
    for deg in np.arange(0.0, 30.0, 0.5):
        tilt = math.radians(deg)
        pts = [at(th_c + u / r_ref, r_ref + lean_out(o_back, z, tilt, z_top), z)
               for u in np.linspace(-half_w, half_w, 7) for z in np.linspace(z_bot, z_top, 6)]
        if sdf(pts, HIPS).min() >= clear:
            return tilt
    return math.radians(30.0)


def slab(name, half_w, z_top, z_bot, thick, mat, nu=5, nz=4, top_round=0.006):
    """A flat leather panel in local coordinates (x across, y out, z up), its back at y = 0, the top corners rounded."""
    bm = bmesh.new()
    us = np.linspace(-half_w, half_w, nu)
    zs = np.linspace(z_bot, z_top, nz)
    grid = {}
    for side, y in ((0, 0.0), (1, thick)):
        for i, u in enumerate(us):
            for j, z in enumerate(zs):
                zz = z
                if j == nz - 1:
                    zz -= top_round * (abs(u) / half_w) ** 6
                grid[side, i, j] = bm.verts.new((u, y, zz))
    for i in range(nu - 1):
        for j in range(nz - 1):
            bm.faces.new([grid[1, i, j], grid[1, i + 1, j], grid[1, i + 1, j + 1], grid[1, i, j + 1]])
            bm.faces.new([grid[0, i, j + 1], grid[0, i + 1, j + 1], grid[0, i + 1, j], grid[0, i, j]])
    ring = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nz)] + \
        [(i, nz - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nz - 2, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        bm.faces.new([grid[0, a[0], a[1]], grid[0, b[0], b[1]], grid[1, b[0], b[1]], grid[1, a[0], a[1]]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 40)


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


R_OUT = R_BELT + BELT_T + 0.001  # the belt's outer face


def pouch(side):
    """A leather pouch hanging from the belt at a hip: a back panel over the belt, a main pocket and a front pocket."""
    th = side * math.radians(73.0)
    hinge = belt_z(th) - BELT_W / 2
    zt = belt_z(th) + BELT_W / 2 + 0.006
    zb = 0.835
    hw = 0.084
    tilt = lean_needed(th, R_OUT, hw, hinge, zb, 0.0)
    out = []
    back = slab("PouchBack%+d" % side, hw, zt, zb, 0.0032, pouch_mat)
    out.append(bend(back, th, R_OUT, tilt, hinge))
    main = pocket("PouchMain%+d" % side, 0.156, 0.135, 0.042, pouch_mat, inside_mat, bulge=0.012, sag=0.008)
    main.data.transform(Matrix.Translation((0.0, 0.0034, zb + 0.004)))
    out.append(bend(main, th, R_OUT, tilt, hinge))
    front = pocket("PouchFront%+d" % side, 0.118, 0.078, 0.02, pouch_mat, inside_mat, bulge=0.006, r_bot=0.016,
                   step=0.05, sag=0.004)
    front.data.transform(Matrix.Translation((0.006 * side, 0.0034 + 0.042 + 0.006, zb + 0.016)))
    out.append(bend(front, th, R_OUT, tilt, hinge))
    return out, (th, tilt, hinge)


right, rframe = pouch(-1)
left, lframe = pouch(1)
pieces += right + left

pencil_mat = plastic("Pencil", (0.2, 0.035, 0.02), seed=4.0, rough=0.5, scuff=0.6, edge_col=(0.32, 0.2, 0.1))
handle_mat = plastic("ScrewdriverHandle", (0.32, 0.2, 0.02), seed=5.0, rough=0.35, scuff=0.5)
wood_mat = wood("HickoryHandle", (0.16, 0.085, 0.035), seed=6.0)


def sticking_out(name, frame_args, length, radius, mat, lean=(0.0, 0.0), sides=8, radius_top=None, flat=1.0):
    p, a, o, up = bent_frame(*frame_args)
    d = (up + a * lean[0] + o * lean[1]).normalized()
    cyl = tk.cylinder(name, radius, 0.0, length, mat, segments=sides, radius_top=radius_top)
    for v in cyl.data.vertices:
        v.co.y *= flat
    x = a.cross(d).normalized()
    y = d.cross(x).normalized()
    return place(cyl, p, y, x, d)


th, tilt, hinge = rframe
pieces.append(sticking_out("Pencil", (th, R_OUT, 0.04, 0.025, 0.905, tilt, hinge), 0.13, 0.0065, pencil_mat,
                           (0.12, 0.06), sides=4, flat=0.45))
pieces.append(sticking_out("Screwdriver", (th, R_OUT, -0.03, 0.022, 0.9, tilt, hinge), 0.135, 0.0125, handle_mat,
                           (-0.1, 0.08), sides=7, radius_top=0.0105))
th, tilt, hinge = lframe
pieces.append(sticking_out("Chisel", (th, R_OUT, -0.025, 0.022, 0.9, tilt, hinge), 0.13, 0.0115, wood_mat,
                           (0.1, 0.1), sides=7, radius_top=0.0095))


def hammer_loop():
    """A leather tab behind the left pouch with a steel loop at its foot, a claw hammer hanging in it by the head."""
    th = math.radians(118.0)
    hinge = belt_z(th) - BELT_W / 2
    zt = belt_z(th) + BELT_W / 2 + 0.005
    zb = hinge - 0.03
    tilt = lean_needed(th, R_OUT, 0.016, hinge, 0.68, 0.012)
    out = []
    tab = slab("HammerTab", 0.024, zt, zb, 0.0032, pouch_mat, nu=3, nz=4)
    out.append(bend(tab, th, R_OUT, tilt, hinge))
    # The loop: a rounded steel rectangle standing out level from the tab's foot
    p, a, o, up = bent_frame(th, R_OUT, 0.0, 0.0032, zb + 0.008, tilt, hinge)
    o = Vector((o.x, o.y, 0.0)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    lw, ld, c = 0.05, 0.044, 0.01
    rect = [(-lw / 2 + c, 0.0), (lw / 2 - c, 0.0), (lw / 2, c), (lw / 2, ld - c), (lw / 2 - c, ld), (-lw / 2 + c, ld),
            (-lw / 2, ld - c), (-lw / 2, c)]
    out.append(tube("HammerLoop", [p + a * x + o * y for x, y in rect], 0.0034, steel_mat, sides=5, closed=True))
    # The hammer: the handle down through the loop leaning out like the tab, the head resting on the loop
    hc = p + o * (ld / 2 + 0.002)
    hd = (-up + o * math.tan(tilt)).normalized()
    head_c = hc - hd * 0.03
    fwd = -a if math.sin(th) > 0 else a  # toward the zombie's front
    fwd = (fwd - hd * fwd.dot(hd)).normalized()
    side_v = hd.cross(fwd).normalized()
    handle = tk.cylinder("HammerHandle", 0.0135, 0.0, 0.29, wood_mat, segments=7, radius_top=0.0115)
    for v in handle.data.vertices:  # oval, swelling toward the grip
        t = v.co.z / 0.29
        k = 1.0 + 0.14 * math.sin(math.pi * min(1.0, t * 1.25))
        v.co.x *= 0.72 * k
        v.co.y *= k
    out.append(place(handle, head_c, side_v, fwd, hd))
    # The head in one piece: curved claw at the back, the eye round the handle, the neck and the round face forward
    path = [(-0.07, 0.024, 0.004), (-0.052, 0.01, 0.0078), (-0.031, 0.0, 0.0112), (-0.013, -0.003, 0.0148),
            (0.013, -0.003, 0.0148), (0.027, 0.0, 0.0102), (0.04, 0.0, 0.0158), (0.053, 0.0, 0.0158)]
    head = tube("HammerHead", [head_c + fwd * f + hd * dz for f, dz, r in path], 0.01, hammer_mat, sides=6,
                radii=[r for f, dz, r in path])
    for v in head.data.vertices:  # the claw and eye are thinner sideways than tall
        w = Vector(v.co) - head_c
        f = w.dot(fwd)
        if f < 0.02:
            v.co = Vector(v.co) - side_v * w.dot(side_v) * (0.5 if f < -0.025 else 0.3)
    out.append(head)
    return out


hammer_mat = steel("HammerSteel", (0.14, 0.14, 0.14), seed=7.0, rust=0.6, polish=0.8, blood=0.25)
pieces += hammer_loop()


def tape_decals(g, P, col, rgh, metal, height):
    """Black rubber round the case's edge, a dark label band across the faces."""
    th = TAPE_TH
    nrm = tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal")
    dot = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.links.new(nrm, dot.inputs[0])
    dot.inputs[1].default_value = (math.sin(th), -math.cos(th), 0.0)
    face = g.ramp(g.math("ABSOLUTE", tk._sock(dot.outputs, "Value")), 0.55, 0.8)
    rubber = g.math("SUBTRACT", 1.0, face)
    col = g.mix(rubber, col, (0.018, 0.018, 0.018))
    rgh = g.mixf(rubber, rgh, 0.7)
    height = g.math("ADD", height, g.math("MULTIPLY", rubber, g.noise(200.0, vector=P)))
    x, y, z = g.separate(g.coords())
    lab = g.math("MULTIPLY", face, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", z, TAPE_Z - 0.004)), 0.011, 0.009))
    col = g.mix(g.math("MULTIPLY", lab, 0.85), col, (0.03, 0.03, 0.03))
    return col, rgh, metal, height


TAPE_TH = math.radians(-116.0)
TAPE_Z = belt_z(TAPE_TH) - 0.012
tape_mat = plastic("TapeCase", (0.34, 0.2, 0.012), seed=8.0, rough=0.38, scuff=0.7, edge_col=(0.42, 0.33, 0.12),
                   decals=tape_decals, dirt=0.75)
brass_mat = steel("TapeHook", (0.3, 0.2, 0.08), seed=9.0, rust=0.2, polish=0.6)


def tape_measure():
    """A tape measure clipped on the belt behind the right pouch: yellow case, black rubber round its edge."""
    th = TAPE_TH
    p, a, o, up = bent_frame(th, R_OUT, 0.0, 0.0, belt_z(th))
    out = []
    # The belt clip: a steel strip from behind the belt, over its top and down the back of the case
    clip_pts = [p - o * (BELT_T + 0.0034) + up * (BELT_W / 2 - 0.006),
                p - o * (BELT_T * 0.5 + 0.001) + up * (BELT_W / 2 + 0.003),
                p + o * 0.0016 + up * (BELT_W / 2 - 0.002), p + o * 0.0016 - up * 0.012]
    out.append(band("TapeClip", clip_pts, [o, up, o + up * 0.5, o], 0.018, 0.0016, steel_mat))
    c = p - up * 0.012 + o * (0.0034 + 0.0185)
    case = superbox("TapeCase", (0.036, 0.0185, 0.035), tape_mat, n=3.4, cuts=2)
    out.append(place(case, c, a, o, up))
    # The blade's end hook peeking out of the slot at the bottom front
    fwd = a if math.sin(th) < 0 else -a
    hook = tk.box("TapeHook", (0.02, 0.0035, 0.008), (0, 0, 0), brass_mat)
    out.append(place(hook, c + fwd * 0.028 - up * 0.031, a, o, up))
    return out


pieces += tape_measure()

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
focus = Vector((0.0, 0.0, 0.93))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.25)
for view, loc, tgt, lens in (("close", (0.45, -0.5, 1.1), (0.08, -0.04, 0.94), 50),
                             ("hammer", (0.75, 0.35, 1.0), (0.18, 0.1, 0.9), 50),
                             ("tape", (-0.7, 0.25, 1.05), (-0.17, 0.0, 0.95), 50)):
    tk.render(tk.camera("tb_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
