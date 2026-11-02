"""Lanyard: a woven work lanyard round the neck with an employee ID badge hanging on the chest. The strap (dark red,
"SHAMWAY FOODS" printed along it, faded and grimy) rests on the base of
the neck and runs down over the collarbones to a steel crimp, a swivel and a lobster clip through the badge's slot.
The badge: a scuffed PVC card with the store's red header and logo, a photo of its owner, his name, a barcode, a crack
across one corner and blood spattered on it.

The strap lies 0.5 cm off the hit boxes; the badge hangs 1.6 cm in front of the chest's hit box, turned a little as if
it had swung, so it still clears a fuller chest. One part on Spine2 ("Spine2#Lanyard").

    blender -b --factory-startup --python lanyard.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PIECE = "Lanyard", "lanyard", "Spine2", "Lanyard"
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




# ---------------------------------------------------------------- printing: text and artwork rasterized to images

FONT = "C:/Windows/Fonts/arialbd.ttf"
FONT_REG = "C:/Windows/Fonts/arial.ttf"


def glyph_tris(body, font=FONT, spacing=1.0):
    cu = bpy.data.curves.new("Glyphs", "FONT")
    cu.body = body
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.resolution_u = 6
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    ob = tk.link(bpy.data.objects.new("Glyphs", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tris = np.array([[(v.co.x, v.co.y) for v in f.verts] for f in bm.faces])
    bm.free()
    bpy.data.meshes.remove(me)
    return tris


def fit(tris, box, align="center"):
    """Scales and moves glyph triangles into box (x0, y0, x1, y1), keeping their aspect."""
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    s = min((box[2] - box[0]) / (hi[0] - lo[0]), (box[3] - box[1]) / (hi[1] - lo[1]))
    c = (lo + hi) / 2
    tx = (box[0] + box[2]) / 2 if align == "center" else box[0] + (hi[0] - lo[0]) * s / 2
    return (tris - c) * s + np.array([tx, (box[1] + box[3]) / 2])


def raster(shape, box, tris, ss=3):
    H, W = shape
    x0, y0, x1, y1 = box
    Hs, Ws = H * ss, W * ss
    img = np.zeros((Hs, Ws), np.float32)
    sx, sy = Ws / (x1 - x0), Hs / (y1 - y0)
    for t in tris:
        P = np.column_stack(((t[:, 0] - x0) * sx, (t[:, 1] - y0) * sy))
        lo = np.maximum(np.floor(P.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(P.max(0)).astype(int), [Ws, Hs])
        if (hi <= lo).any():
            continue
        X, Y = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)

        def ef(a, b):
            return (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
        e0, e1, e2 = ef(P[0], P[1]), ef(P[1], P[2]), ef(P[2], P[0])
        ins = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
        img[lo[1]:hi[1], lo[0]:hi[0]][ins] = 1.0
    return img.reshape(H, ss, W, ss).mean(axis=(1, 3))


def text(shape, box, body, rect, font=FONT, align="center", spacing=1.0):
    return raster(shape, box, fit(glyph_tris(body, font, spacing), rect, align))


def grid_xy(shape, box):
    H, W = shape
    x0, y0, x1, y1 = box
    return np.meshgrid(x0 + (np.arange(W) + 0.5) * (x1 - x0) / W, y0 + (np.arange(H) + 0.5) * (y1 - y0) / H)


def sdf_rect(X, Y, rect, r=0.0):
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    hx, hy = (rect[2] - rect[0]) / 2 - r, (rect[3] - rect[1]) / 2 - r
    qx, qy = np.abs(X - cx) - hx, np.abs(Y - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def cover(d, px):
    """Coverage (0-1) of an SDF at pixel size px."""
    return np.clip(0.5 - d / px, 0.0, 1.0)


def paint(img, mask, color):
    for k in range(3):
        img[..., k] = img[..., k] * (1 - mask) + color[k] * mask


def color_image(name, rgb):
    H, W = rgb.shape[:2]
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.colorspace_settings.name = "Non-Color"  # linear values, as the shader wants them
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., :3] = rgb
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(tempfile.gettempdir(), "zx_%s.png" % name)
    img.file_format = "PNG"
    img.save()
    return img


def image_node(g, img, u, v, box, extension="CLIP"):
    cx = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", u, box[0]), box[2] - box[0]), cx.inputs[0])
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", v, box[1]), box[3] - box[1]), cx.inputs[1])
    n = g.node("ShaderNodeTexImage", interpolation="Linear", extension=extension)
    n.image = img
    g.links.new(cx.outputs[0], n.inputs["Vector"])
    return n.outputs["Color"]


# The badge (54 x 86 mm), in card coordinates (x right, z up, meters from its middle)
CARD_W, CARD_H, CARD_T = 0.054, 0.086, 0.0015
CBOX = (-CARD_W / 2, -CARD_H / 2, CARD_W / 2, CARD_H / 2)
CSHAPE = (430, 270)
WHITE = (0.33, 0.32, 0.285)
RED = (0.15, 0.022, 0.018)
INK = (0.022, 0.02, 0.02)
SLOT = (-0.0068, 0.0355, 0.0068, 0.0385)


def card_front():
    X, Y = grid_xy(CSHAPE, CBOX)
    px = CARD_W / CSHAPE[1]
    img = np.zeros(CSHAPE + (3,), np.float32)
    img[...] = WHITE
    paint(img, cover(-(Y - 0.0205), px) * 1.0, RED)  # the header band
    paint(img, cover(np.maximum(Y + 0.0395, -(Y + 0.043)), px), RED)  # a thin band at the foot
    # the logo: a ring with a cart's wheel in it, and the store's name
    d = np.hypot(X + 0.0175, Y - 0.0283)
    paint(img, cover(np.abs(d - 0.0052) - 0.0009, px), WHITE)
    paint(img, cover(d - 0.0022, px), WHITE)
    paint(img, text(CSHAPE, CBOX, "SHAMWAY", (-0.0095, 0.0245, 0.0245, 0.0322)), WHITE)
    paint(img, text(CSHAPE, CBOX, "FOODS", (0.003, 0.0215, 0.0245, 0.0242), FONT_REG, spacing=1.4), WHITE)
    # the photo: a pale blue backdrop, the man's head and shoulders, a dark frame
    pr = (-0.0235, -0.0095, -0.0035, 0.0165)
    paint(img, cover(sdf_rect(X, Y, pr), px), (0.13, 0.16, 0.19))
    clip = cover(sdf_rect(X, Y, pr), px)
    sh = np.hypot((X + 0.0135) / 0.0115, (Y + 0.0108) / 0.0075) - 1.0
    paint(img, cover(sh * 0.008, px) * clip, (0.045, 0.05, 0.07))
    neck = sdf_rect(X, Y, (-0.0158, -0.004, -0.0112, 0.002), 0.001)
    paint(img, cover(neck, px) * clip, (0.2, 0.12, 0.085))
    head = np.hypot((X + 0.0135) / 0.0052, (Y - 0.0058) / 0.0066) - 1.0
    paint(img, cover(head * 0.005, px) * clip, (0.27, 0.165, 0.115))
    hair = np.maximum(np.hypot((X + 0.0135) / 0.0058, (Y - 0.0086) / 0.005) - 1.0, -(Y - 0.0082) / 0.005)
    paint(img, cover(hair * 0.005, px) * clip, (0.05, 0.035, 0.025))
    for ex in (-0.0154, -0.0116):  # eyes
        paint(img, cover(np.hypot(X - ex, Y - 0.0062) - 0.0006, px) * clip, (0.03, 0.02, 0.02))
    paint(img, cover(np.abs(sdf_rect(X, Y, pr)) - 0.0003, px), (0.08, 0.08, 0.08))
    # name, job, number
    paint(img, text(CSHAPE, CBOX, "DALE", (-0.0015, 0.0085, 0.0235, 0.0155), align="left"), INK)
    paint(img, text(CSHAPE, CBOX, "STOCK CLERK", (-0.0015, 0.0025, 0.0235, 0.006), FONT_REG, align="left"),
          (0.06, 0.055, 0.05))
    paint(img, text(CSHAPE, CBOX, "STORE 217", (-0.0015, -0.003, 0.016, 0.0002), FONT_REG, align="left"),
          (0.06, 0.055, 0.05))
    paint(img, text(CSHAPE, CBOX, "EMPLOYEE", (-0.0225, -0.0185, 0.0225, -0.0135), spacing=1.3), RED)
    # barcode
    rng = np.random.default_rng(217)
    widths = rng.integers(1, 4, 60)
    edges = np.cumsum(widths)
    edges = edges / edges[-1]
    xs = (X + 0.0205) / 0.041
    bar = np.searchsorted(edges, np.clip(xs, 0, 0.9999)) % 2 == 0
    inside = cover(sdf_rect(X, Y, (-0.0205, -0.0365, 0.0205, -0.0235)), px)
    paint(img, bar * inside, INK)
    # the punched slot
    paint(img, cover(sdf_rect(X, Y, SLOT, 0.0014), px), (0.015, 0.012, 0.012))
    return color_image("BadgeFront", img)


def card_back():
    X, Y = grid_xy(CSHAPE, CBOX)
    px = CARD_W / CSHAPE[1]
    img = np.zeros(CSHAPE + (3,), np.float32)
    img[...] = WHITE
    paint(img, cover(sdf_rect(X, Y, (-0.027, 0.012, 0.027, 0.026)), px), (0.02, 0.019, 0.018))  # magnetic stripe
    for k, line in enumerate(("IF FOUND PLEASE RETURN TO", "SHAMWAY FOODS STORE 217", "NOT TRANSFERABLE")):
        y = 0.004 - k * 0.006
        paint(img, text(CSHAPE, CBOX, line, (-0.022, y - 0.0018, 0.022, y + 0.0018), FONT_REG), (0.09, 0.085, 0.08))
    paint(img, text(CSHAPE, CBOX, "SHAMWAY", (-0.016, -0.03, 0.016, -0.022)), RED)
    # the slot, mirrored
    paint(img, cover(sdf_rect(X, Y, (-SLOT[2], SLOT[1], -SLOT[0], SLOT[3]), 0.0014), px), (0.015, 0.012, 0.012))
    return color_image("BadgeBack", img)


# The lanyard's print: "SHAMWAY FOODS" over and over (a tile 12 cm long, the strap's width high)
TILE = 0.12
STRAP_W, STRAP_T = 0.016, 0.0013


def strap_print():
    shape = (40, 600)
    box = (0.0, -STRAP_W / 2, TILE, STRAP_W / 2)
    m = text(shape, box, "SHAMWAY  FOODS", (0.008, -0.0036, TILE - 0.012, 0.0036), spacing=1.15)
    X, Y = grid_xy(shape, box)
    dot = cover(np.hypot(X - (TILE - 0.0045), Y) - 0.0013, TILE / 600)
    rgb = np.zeros(shape + (3,), np.float32)
    rgb[..., 0] = np.maximum(m, dot)
    return color_image("LanyardPrint", rgb)


# ---------------------------------------------------------------- materials

def lanyard_material(name, seed=0.0):
    """Woven polyester strap: dark red, fine ribs across, paler worn edges, the print on the outer face cracked and
    faded, grime where it touches the neck, blood spatter."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    a, s, side = attr(g)
    base = (0.075, 0.011, 0.009)
    col = g.mix(g.ramp(g.noise(5.0, detail=4.0, vector=P), 0.3, 0.7), base, (0.12, 0.024, 0.019))
    rib = g.math("SINE", g.math("DIVIDE", s, 0.00035))
    height = g.math("MULTIPLY", rib, 0.12)
    col = g.mix(g.math("MULTIPLY", g.math("ADD", rib, 1.0), 0.15), col, tk._darker(g, col, 0.6))
    edge = g.ramp(g.math("ABSOLUTE", a), 0.0062, 0.0078)
    col = g.mix(g.math("MULTIPLY", edge, 0.6), col, tk._darker(g, col, 0.55))
    height = g.math("ADD", height, g.math("MULTIPLY", edge, 0.3))
    pr = g.separate(image_node(g, PRINT, g.math("MULTIPLY", g.math("FRACT", g.math("DIVIDE", s, TILE)), TILE),
                               g.math("MULTIPLY", a, -1.0), (0.0, -STRAP_W / 2, TILE, STRAP_W / 2), "REPEAT"))[0]
    cracked = g.ramp(cracks_mask(g, P), 0.5, 0.6)
    pr = g.math("MULTIPLY", g.math("MULTIPLY", pr, g.ramp(side, 0.5, 0.9)), g.math("SUBTRACT", 1.0, cracked))
    pr = g.math("MULTIPLY", pr, g.ramp(g.noise(6.0, detail=5.0, vector=P, distortion=0.4), 0.25, 0.45))
    col = g.mix(pr, col, (0.33, 0.31, 0.27))
    height = g.math("ADD", height, g.math("MULTIPLY", pr, 0.2))
    rough = g.math("ADD", 0.66, g.math("MULTIPLY", pr, -0.15))
    fuzz = g.math("MULTIPLY", g.ramp(g.edges(0.0012), 0.1, 0.4), g.ramp(g.noise(40.0, vector=P), 0.35, 0.6))
    col = g.mix(fuzz, col, (0.2, 0.08, 0.065))
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.6, grime=0.8, dust=0.08, specks=0.5,
                                       blood=0.4, dirt_cols=((0.025, 0.016, 0.012), (0.06, 0.04, 0.03)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.0008))


def cracks_mask(g, P):
    v = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(v, "Scale", 220.0)
    g.links.new(P, v.inputs["Vector"])
    return g.math("SUBTRACT", 1.0, g.ramp(tk._sock(v.outputs, "Distance"), 0.0, 0.06))


def badge_material(name, seed=0.0):
    """The PVC card: the printed front and back, scuffed and scratched, grime worked into the edges, a crack across
    one corner, blood spatter."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    x, z, face = attr(g)
    front = g.ramp(face, -0.2, 0.2)
    col = g.mix(front, image_node(g, BACK, g.math("MULTIPLY", x, -1.0), z, CBOX), image_node(g, FRONT, x, z, CBOX))
    rough = g.math("ADD", 0.3, g.math("MULTIPLY", g.noise(12.0, detail=3.0, vector=P), 0.15))
    height = g.math("MULTIPLY", g.noise(200.0, detail=3.0, vector=P), 0.05)
    # Scuffs and fine scratches, worse on the front (it rubbed on the shirt)
    sc = g.math("MULTIPLY", scratches(g, P, 0.03), g.mixf(front, 0.5, 1.0))
    col = g.mix(g.math("MULTIPLY", sc, 0.5), col, tk.grade(g, col, 0.6, 1.25))
    rough = g.mixf(sc, rough, 0.55)
    scuff = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=6.0, roughness=0.7, vector=P, distortion=1.0), 0.58, 0.72),
                   0.6)
    col = g.mix(scuff, col, tk.grade(g, col, 0.5, 0.8))
    rough = g.mixf(scuff, rough, 0.65)
    # A crack across the top-left corner (dark line, the print chipped beside it)
    crack_d = g.math("ABSOLUTE", g.math("ADD", g.math("ADD", g.math("MULTIPLY", x, 0.8), g.math("MULTIPLY", z, -1.0)),
                                          g.math("ADD", 0.0545, g.math("MULTIPLY", g.noise(160.0, vector=P), 0.003))))
    crack = g.math("MULTIPLY", g.ramp(crack_d, 0.0007, 0.0002), g.ramp(x, -0.008, -0.012))
    chip = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(crack_d, 0.0022, 0.0009), g.ramp(x, -0.008, -0.012)),
                  g.ramp(g.noise(90.0, vector=P), 0.45, 0.6))
    col = g.mix(chip, col, (0.3, 0.29, 0.26))
    col = g.mix(crack, col, (0.02, 0.018, 0.017))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.8))
    # Grime worked in round the edges
    rim = g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", x), CARD_W / 2 - 0.004, CARD_W / 2),
                 g.ramp(g.math("ABSOLUTE", z), CARD_H / 2 - 0.004, CARD_H / 2))
    rim = g.math("MULTIPLY", rim, g.ramp(g.noise(30.0, detail=4.0, vector=P), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", rim, 0.8), col, (0.06, 0.05, 0.04))
    col, rough, metal, height = grunge(g, P, col, rough, 0.0, height, dirt=0.6, grime=0.6, dust=0.1, specks=0.7,
                                       blood=0.6, dirt_range=(0.18, 0.05))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.2, 0.0006))


FRONT, BACK, PRINT = card_front(), card_back(), strap_print()
strap_mat = lanyard_material("LanyardStrap", 1.0)
card_mat = badge_material("Badge", 2.0)
metal_mat = steel("ClipSteel", (0.32, 0.32, 0.31), seed=3.0, rust=0.25, polish=0.8, blood=0.2)


# ---------------------------------------------------------------- the strap's path round the neck

BONES = ("Spine2", "Head", "LeftArm", "RightArm")
CLR = 0.005 + STRAP_T / 2  # the strap's middle off the hit boxes


def grad(P, bones):
    e = 1e-4
    P = np.atleast_2d(P)
    gr = np.stack([sdf(P + dv, bones) - sdf(P - dv, bones) for dv in np.eye(3) * e], axis=1)
    return gr / np.maximum(np.linalg.norm(gr, axis=1), 1e-9)[:, None]


def push_out(P, clear, bones=BONES, iters=12):
    P = np.array(P, float)
    for _ in range(iters):
        d = sdf(P, bones)
        m = d < clear
        if not m.any():
            break
        P[m] += grad(P[m], bones) * (clear - d[m])[:, None]
    return P


def neck_pt(psi, r=0.097):
    """A point round the back of the neck (psi 0 at the front, +90 the zombie's left) resting on the chest's box."""
    x, y = r * math.sin(psi), 0.04 - r * math.cos(psi)
    lo, hi = 1.45, 1.75
    for _ in range(40):
        mid = (lo + hi) / 2
        if sdf([[x, y, mid]], ("Spine2", "LeftArm", "RightArm"))[0] > CLR:
            hi = mid
        else:
            lo = mid
    return np.array([x, y, hi])


def resample(P, step):
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(round(L[-1] / step)) + 1)
    t = np.linspace(0.0, L[-1], n)
    return np.stack([np.interp(t, L, P[:, k]) for k in range(3)], axis=1)


# The badge hangs from a swivel 1.6 cm in front of the chest's box; its clip and the strap's crimp above that
CHEST_FRONT = 0.05 - 0.158
SWIVEL = np.array([0.0, CHEST_FRONT - 0.0195, 1.393])
CRIMP = SWIVEL + np.array([0.0, 0.0, 0.0145])
ends = (CRIMP + np.array([0.0, -STRAP_T * 0.6, 0.004]), CRIMP + np.array([0.0, STRAP_T * 0.6, 0.004]))

back = [neck_pt(math.radians(p)) for p in np.linspace(118, 242, 9)]
path = np.vstack([np.linspace(ends[0], back[0], 14)[:-1], back, np.linspace(back[-1], ends[1], 14)[1:]])
path = resample(path, 0.012)
fixed = np.zeros(len(path), bool)
fixed[[0, -1]] = True
for i, p in enumerate(path):  # pin the part behind the neck
    if p[1] > 0.075:
        fixed[i] = True
anchor = path.copy()
for it in range(500):
    Q = path.copy()
    Q[1:-1] = 0.5 * (path[:-2] + path[2:])
    Q[fixed] = anchor[fixed]
    path = push_out(Q, CLR)
    path[fixed] = anchor[fixed]
    if it % 50 == 49:
        path = resample(path, 0.012)
        fixed = np.zeros(len(path), bool)
        fixed[[0, -1]] = True
        fixed |= path[:, 1] > 0.075
        anchor = path.copy()
path = resample(path, 0.011)
path[0], path[-1] = ends
path = push_out(path, CLR)
nrm = grad(path, BONES)
# Near the crimp the two strands lie flat on each other, facing forward
s_all = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
L_all = s_all[-1]
for i in range(len(path)):
    w = max(0.0, 1.0 - min(s_all[i], L_all - s_all[i]) / 0.05)
    nrm[i] = nrm[i] * (1 - w) + np.array([0.0, -1.0, 0.0]) * w
nrm /= np.linalg.norm(nrm, axis=1)[:, None]


# Lift the strap wherever an edge of it dips into the hit boxes (it's flat; the neck and chest are round)
for rnd_ in range(4):
    for i in range(1, len(path) - 1):
        T = path[i + 1] - path[i - 1]
        T /= np.linalg.norm(T)
        Nn = nrm[i] - T * (nrm[i] @ T)
        Nn /= np.linalg.norm(Nn)
        W = np.cross(T, Nn)
        probe = np.array([path[i] + W * k * STRAP_W / 2 - Nn * STRAP_T / 2 for k in (-1, -0.5, 0, 0.5, 1)])
        short = 0.004 - sdf(probe, BONES).min()
        if short > 0:
            path[i] = path[i] + Nn * short
    if rnd_ < 3:
        path[1:-1] = 0.25 * path[:-2] + 0.5 * path[1:-1] + 0.25 * path[2:]
pieces = [band("Strap", path, nrm, STRAP_W, STRAP_T, strap_mat)]

# ---------------------------------------------------------------- crimp, swivel, clip and badge

crimp = tk.box("Crimp", (0.0195, 0.0048, 0.012), tuple(CRIMP + np.array([0.0, 0.0, 0.001])), metal_mat,
               bevel_width=0.0008)
pieces.append(crimp)
swv = tk.cylinder("Swivel", 0.0033, SWIVEL[2] - 0.001, CRIMP[2] - 0.005, metal_mat, segments=8, center=SWIVEL[:2])
pieces.append(swv)

# The badge assembly hangs from the swivel, turned and tilted a little as if it had swung
SW = Vector(SWIVEL)
turn = Matrix.Rotation(math.radians(-9.0), 4, "Z") @ Matrix.Rotation(math.radians(5.0), 4, "Y")
about = Matrix.Translation(SW) @ turn @ Matrix.Translation(-SW)

# Lobster clip: a teardrop loop through the card's slot, in the plane square to the card
card_c = SWIVEL + np.array([0.0, 0.0, -0.0185 - CARD_H / 2 + 0.0])
slot_z = card_c[2] + (SLOT[1] + SLOT[3]) / 2
loop = []
for k in range(14):
    a = 2 * math.pi * k / 14
    zz = SWIVEL[2] - 0.003 + (slot_z - 0.0005 - (SWIVEL[2] - 0.003)) * (0.5 - 0.5 * math.cos(a))
    rr = 0.0058 * math.sin(a) * (0.55 + 0.45 * (0.5 - 0.5 * math.cos(a)))
    loop.append((SWIVEL[0], SWIVEL[1] + rr, zz))
clip = tube("Clip", loop, 0.0014, metal_mat, sides=5, closed=True)
clip.data.transform(about)
pieces.append(clip)
gate = tk.box("ClipGate", (0.0035, 0.0032, 0.007), (SWIVEL[0], SWIVEL[1] - 0.0052, SWIVEL[2] - 0.0115), metal_mat)
gate.data.transform(about)
pieces.append(gate)


def card():
    """The card: a rounded rectangle, CARD_T thick, its face toward -Y."""
    r = 0.0032
    outline = []
    for cx, cz, a0 in ((CARD_W / 2 - r, CARD_H / 2 - r, 0.0), (-CARD_W / 2 + r, CARD_H / 2 - r, 90.0),
                       (-CARD_W / 2 + r, -CARD_H / 2 + r, 180.0), (CARD_W / 2 - r, -CARD_H / 2 + r, 270.0)):
        for k in range(4):
            a = math.radians(a0 + 90.0 * k / 3)
            outline.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    bm = bmesh.new()
    vals = []
    rings = []
    for sgn in (-1, 1):  # -1 front (toward -Y), +1 back
        ring = [bm.verts.new((card_c[0] + x, card_c[1] + sgn * CARD_T / 2, card_c[2] + z)) for x, z in outline]
        vals += [(x, z, -sgn) for x, z in outline]
        rings.append(ring)
    cf = bm.verts.new((card_c[0], card_c[1] - CARD_T / 2, card_c[2]))
    cb = bm.verts.new((card_c[0], card_c[1] + CARD_T / 2, card_c[2]))
    vals += [(0.0, 0.0, 1.0), (0.0, 0.0, -1.0)]
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((rings[0][i], rings[0][j], cf))
        bm.faces.new((rings[1][j], rings[1][i], cb))
        bm.faces.new((rings[0][j], rings[0][i], rings[1][i], rings[1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Badge", bm, card_mat)
    set_attr(obj, vals)
    obj.data.transform(about)
    return tk.smooth(obj, 30)


pieces.append(card())

# ---------------------------------------------------------------- checks, export, previews

for o in pieces:
    bake_transform(o)
    fix_normals(o)
    zk.on(o, BONE, PIECE)
for o in pieces:
    V = np.array([v.co[:] for v in o.data.vertices])
    print("[%s] %-20s %4d tris, %.1f mm off the hit boxes (chest %.1f mm)" % (
        SCRIPT, o.name, tri_count([o]), sdf(V).min() * 1000, sdf(V, ("Spine2",)).min() * 1000))
allv = np.array([v.co[:] for o in pieces for v in o.data.vertices])
print("[%s] %d triangles, bounds %s to %s, closest %.1f mm" % (SCRIPT, tri_count(pieces), np.round(allv.min(0), 3),
                                                               np.round(allv.max(0), 3), sdf(allv).min() * 1000))

for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS, size=512)
for o in BODY:
    o.hide_render = False
focus = Vector((0.0, 0.0, 1.47))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.0)
for view, loc, tgt, lens in (("badge", (0.07, -0.42, 1.36), (0.0, -0.12, 1.335), 50),
                             ("neck", (0.42, 0.42, 1.78), (0.0, 0.04, 1.56), 50)):
    tk.render(tk.camera("ly_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=48)
print("[%s] done" % SCRIPT)
