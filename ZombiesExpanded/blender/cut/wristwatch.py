"""Wristwatch: a cheap steel field watch on the left wrist, its crystal smashed. A round brushed steel case with a
sloped bezel, four lugs and a knurled crown toward the hand; under the glass a black dial with pale lume markers and
hands stopped at 4:37, the crystal crazed out from a hit at four o'clock (a crushed white spot, cracks running out
from it, two broken rings round it). A dark brown leather strap, cracked and gone black with sweat and dirt, its
edges rubbed pale: the short end with the steel buckle, the long end through it with its tail under the keeper.

Worn on the back of the wrist 2.5 cm up from the joint, the strap 3 to 5 mm loose round Joe's wrist (about 6.4 by
5 cm). One part, LeftHand#Watch.

    blender -b --factory-startup --python wristwatch.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PART, SIZE = "Wristwatch", "wristwatch", "LeftHand", "Watch", 512

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
SK = zk.joe()
HC = Vector((0.0, 0.035, 1.745))  # center of the head hit box's top half-sphere (radius 0.10, top at z 1.845)


# ---------------------------------------------------------------- mesh helpers

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def orient(bm, inside):
    """Turns every face of an open surface to face away from the point `inside`."""
    bm.normal_update()
    if sum((f.calc_center_median() - inside).dot(f.normal) for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])


def set_values(obj, name, vals):
    """Stores one 3-vector per vertex as the attribute `name`, which materials read with attr()."""
    at = obj.data.attributes.get(name) or obj.data.attributes.new(name, "FLOAT_VECTOR", "POINT")
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def store(obj, name, fn):
    """Records fn(local vertex position) on every vertex as attribute `name` (pattern coordinates that stay with the
    piece when it's moved into place and joined)."""
    return set_values(obj, name, [fn(v.co.copy()) for v in obj.data.vertices])


def grid(name, mat, cols, rows, fn, cyclic=True, pole=False, end_pole=False, inside=HC, closed=False, values=None,
         attr_name="uvw"):
    """A surface from fn(i, j) -> point over cols x rows vertices, closed around i when cyclic; with pole, row 0 is a
    single point (a dome's top), with end_pole the last row too. Faces turn away from `inside` (or, for a closed
    mesh, outward). values(i, j) -> 3-vector is stored on the vertices as attribute `attr_name`."""
    bm = bmesh.new()
    vs, vals = [], []
    for j in range(rows):
        if (pole and j == 0) or (end_pole and j == rows - 1):
            p = bm.verts.new(fn(0, j))
            vs.append([p] * cols)
            vals.append(values(0, j) if values else None)
        else:
            row = []
            for i in range(cols):
                row.append(bm.verts.new(fn(i, j)))
                vals.append(values(i, j) if values else None)
            vs.append(row)
    for j in range(rows - 1):
        for i in range(cols if cyclic else cols - 1):
            i1 = (i + 1) % cols
            quad = []
            for v in (vs[j][i], vs[j][i1], vs[j + 1][i1], vs[j + 1][i]):
                if v not in quad:
                    quad.append(v)
            if len(quad) >= 3:
                bm.faces.new(quad)
    if closed:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    else:
        orient(bm, inside)
    obj = tk.mesh_object(name, bm, mat)
    if values:
        set_values(obj, attr_name, vals)
    return obj


def thicken(obj, thickness, inner=None, rim=None, offset=-1.0):
    """Solidify inward; `inner` and `rim` are material slots added for the new inside faces and the rim."""
    mod = obj.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    for k, m in ((1, inner), (2, rim)):
        if m is not None:
            if m.name not in obj.data.materials:
                obj.data.materials.append(m)
            idx = list(obj.data.materials).index(m)
            if k == 1:
                mod.material_offset = idx
            else:
                mod.material_offset_rim = idx
    return tk.apply_modifiers(obj)


def push(obj, center, radius, vec):
    """Shoves the vertices near `center` by `vec`, falling off over `radius` (a dent)."""
    c, v = Vector(center), Vector(vec)
    for vert in obj.data.vertices:
        d = (vert.co - c).length
        if d < radius:
            vert.co += v * (0.5 + 0.5 * math.cos(math.pi * d / radius))
    return obj


def _frames(P, closed):
    n = len(P)
    T = []
    for i in range(n):
        d = (P[(i + 1) % n] - P[(i - 1) % n]) if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        T.append(d.normalized())
    return T


def strap(name, pts, width, thick, mat, side=(0.0, 0.0, 1.0), closed=False, values=None, attr_name="uvw"):
    """A flat band swept along a polyline: `width` along `side` (kept square to the path), `thick` across it.
    values(i, k) -> 3-vector (k 0-3 round the section) is stored as attribute `attr_name`."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        s = Vector(side(i) if callable(side) else side)
        W = (s - T[i] * s.dot(T[i])).normalized()
        N = T[i].cross(W)
        ring = []
        for k, (sw, st) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
            ring.append(bm.verts.new(P[i] + W * (sw * width / 2) + N * (st * thick / 2)))
            vals.append(values(i, k) if values else None)
        rings.append(ring)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.smooth(tk.mesh_object(name, bm, mat), 40)
    if values:
        set_values(obj, attr_name, vals)
    return obj


def rope(name, pts, ra, rb, mat, side=(0.0, 0.0, 1.0), sides=6, closed=False, scale=None, values=None,
         attr_name="uvw", caps=True):
    """A tube of elliptical section along a polyline: radius `ra` along `side` (kept square to the path), `rb` across
    it; scale(i) -> factor tapers it. values(i, k) -> 3-vector is stored as attribute `attr_name`."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        s = Vector(side(i) if callable(side) else side)
        W = (s - T[i] * s.dot(T[i])).normalized()
        N = T[i].cross(W)
        k = scale(i) if scale else 1.0
        ka, kb = (k if not isinstance(k, tuple) else k[0]), (k if not isinstance(k, tuple) else k[1])
        ring = []
        for j in range(sides):
            t = 2 * math.pi * j / sides
            ring.append(bm.verts.new(P[i] + W * (math.cos(t) * ra * ka) + N * (math.sin(t) * rb * kb)))
            vals.append(values(i, j) if values else None)
        rings.append(ring)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.smooth(tk.mesh_object(name, bm, mat), 60)
    if values:
        set_values(obj, attr_name, vals)
    return obj


def cut(obj, cutter, slot=0):
    """Boolean-subtracts `cutter` (then deleted) from obj; the cut walls take obj's material `slot`."""
    for p in cutter.data.polygons:
        p.material_index = slot
    mod = obj.modifiers.new("Cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.material_mode = "INDEX"
    mod.object = cutter
    tk.apply_modifiers(obj)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return obj


def prism(name, outline, a, b, mat, d0=-0.3, d1=0.3, origin=(0.0, 0.0, 0.0)):
    """A cutter: the polygon `outline` [(u, v)...] in the plane through `origin` spanned by unit vectors a (u) and
    b (v), reaching from d0 to d1 along a x b."""
    n = a.cross(b).normalized()
    o = Vector(origin)
    bm = bmesh.new()
    front = [bm.verts.new(o + a * u + b * v + n * d0) for u, v in outline]
    back = [bm.verts.new(o + a * u + b * v + n * d1) for u, v in outline]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for k in range(len(outline)):
        k1 = (k + 1) % len(outline)
        bm.faces.new((front[k], back[k], back[k1], front[k1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, mat)


def bake_transform(obj):
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


# ---------------------------------------------------------------- material helpers

def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def attr(g, name):
    """A vector attribute stored on the mesh (see store / set_values)."""
    n = g.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name)
    return tk._sock(n.outputs, "Vector")


def white(g, vec):
    """A random value per point (constant over each cell when vec is floored)."""
    n = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Value")


def floor_vec(g, vec, size):
    """vec snapped down to a grid of cell `size` (per axis)."""
    d = g.node("ShaderNodeVectorMath", operation="DIVIDE")
    g.links.new(vec, d.inputs[0])
    d.inputs[1].default_value = size
    f = g.node("ShaderNodeVectorMath", operation="FLOOR")
    g.links.new(d.outputs[0], f.inputs[0])
    return f.outputs[0]


def combine(g, x, y, z=0.0):
    n = g.node("ShaderNodeCombineXYZ")
    g._in(n, "X", x)
    g._in(n, "Y", y)
    g._in(n, "Z", z)
    return n.outputs[0]


def vdist(g, vec, point):
    n = g.node("ShaderNodeVectorMath", operation="DISTANCE")
    g.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = point
    return tk._sock(n.outputs, "Value")


def voronoi(g, vec, scale, feature="F1"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Distance")


def warp(g, P, scale, amount):
    """P pushed about by noise, so patterns laid on it (cracks, cells) lose their regularity."""
    n = g.node("ShaderNodeTexNoise")
    g._in(n, "Scale", scale)
    g._in(n, "Detail", 3.0)
    g.links.new(P, n.inputs["Vector"])
    s = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(tk._sock(n.outputs, "Color"), s.inputs[0])
    tk._sock(s.inputs, "Scale").default_value = amount
    a = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(P, a.inputs[0])
    g.links.new(s.outputs[0], a.inputs[1])
    return a.outputs[0]


def band(g, x, lo, hi, soft=0.001):
    """1 between lo and hi, soft edges."""
    return g.math("MULTIPLY", g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def rect(g, u, v, hw, hh, soft=0.001):
    return g.math("MULTIPLY", band(g, u, -hw, hw, soft), band(g, v, -hh, hh, soft))


def rotate2(g, a, b, ca, cb, degrees):
    """(a, b) about (ca, cb) turned by `degrees` -> local (u, v)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    da, db = g.math("SUBTRACT", a, ca), g.math("SUBTRACT", b, cb)
    u = g.math("ADD", g.math("MULTIPLY", da, c), g.math("MULTIPLY", db, s))
    v = g.math("SUBTRACT", g.math("MULTIPLY", db, c), g.math("MULTIPLY", da, s))
    return u, v


def frayed(g, soft_mask, P, scale=45.0, amount=0.7):
    """A sticker's outline worn ragged: a soft-edged mask thresholded against noise."""
    n = g.noise(scale, detail=6.0, roughness=0.7, vector=P)
    return g.ramp(g.math("ADD", soft_mask, g.math("MULTIPLY", g.math("SUBTRACT", n, 0.5), amount)), 0.45, 0.55)


def lines(g, vec, scale, rot, loc, width, seg=0.0):
    """Thin scratch lines: contours of stretched noise, broken into short runs when seg (a noise scale) is given."""
    n = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, vec, scale, rot, loc))
    ln = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, width, False))
    if seg:
        ln = g.math("MULTIPLY", ln, g.ramp(g.noise(seg, detail=2.0, vector=mapping(g, vec, loc=loc)), 0.5, 0.58))
    return ln


def scratch_mask(g, P, width=0.015):
    """Straight scratches in five directions (bands of a wave texture, each broken into short runs)."""
    sc = None
    for i, (rot, scale) in enumerate((((0.3, 0.9, 0.2), 38.0), ((1.1, 0.2, 1.4), 55.0), ((0.5, 1.3, 2.7), 30.0),
                                      ((2.3, 0.4, 0.9), 70.0), ((1.7, 2.2, 0.3), 45.0))):
        m = mapping(g, P, rot=rot, loc=(0.13 * i, 0.31 * i, 0.07 * i))
        w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        g._in(w, "Scale", scale)
        g._in(w, "Distortion", 0.8)
        g._in(w, "Detail", 1.0)
        g._in(w, "Detail Scale", 0.5)
        g.links.new(warp(g, m, 2.5 + i, 0.03), w.inputs["Vector"])  # irregular spacing, gentle bends
        line = g.ramp(tk._sock(w.outputs, "Fac"), 1.0 - width, 1.0 - width * 0.15)
        seg = g.ramp(g.noise(16.0 + 7.0 * i, detail=2.0, vector=m), 0.57, 0.64)
        line = g.math("MULTIPLY", line, seg)
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    return sc


def wear(name, paint, rough=0.4, metal=0.0, decals=None, seed=0.0, tone=0.2, fade=0.0, scratches=0.5,
         scratch_col=(0.6, 0.58, 0.52), scratch_metal=0.0, dark_scratches=0.3, scuffs=0.4, scuff_col=None, edges=0.4,
         edge_col=None, chips=0.0, chip_col=(0.5, 0.5, 0.5), chip_rough=0.6, chip_metal=0.0, dirt=0.5,
         dirt_set="rust_coarse_01", dirt_scale=3.0, dirt_range=(0.14, 0.04), grime=0.6, dust=0.4, specks=0.5,
         splatter=0.0, splatter_col=(0.5, 0.49, 0.46), blood=0.0, grease=0.0, scorch=0.0, bump=0.3, grain=0.15,
         grain_scale=90.0, line_width=0.03, dirt_col=((0.04, 0.032, 0.024), (0.12, 0.095, 0.065)), late=None):
    """Worn gear: base paint, cloth or metal with uneven tone and sun fade, decals, chips through to the layer beneath,
    rubbed scuffs, scratches (pale, some packed with dirt), worn edges, photo-patterned dirt and crease grime, dust on
    top, dark specks, and optional paint/concrete splatter, blood, grease and scorch. All amounts 0-1. `late` is a
    second decal pass run after the dirt (stains that sit on top of it)."""
    mat, g = tk.new_material(name)
    W = g.coords()
    S = (seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29)
    P = mapping(g, W, loc=S)

    def nz(scale, detail=4.0, r=0.55, dist=0.0):
        return g.noise(scale, detail=detail, roughness=r, vector=P, distortion=dist)

    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    col = g.mix(g.math("MULTIPLY", nz(5.0, 3.0), tone * 2.0), paint, tk._darker(g, paint, 0.7))
    rgh = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", nz(14.0, 3.0), 0.5), 0.16))
    met = metal
    height = g.math("MULTIPLY", nz(grain_scale, 6.0, 0.6), grain)
    if decals:
        col, rgh, met, height = decals(g, W, P, col, rgh, met, height)
    if fade:
        fm = g.math("MULTIPLY", g.ramp(up, -0.1, 0.9), g.ramp(nz(3.0, 4.0), 0.3, 0.7))
        col = g.mix(g.math("MULTIPLY", fm, fade), col, tk.grade(g, col, 0.55, 1.35))
    if chips:
        cm = g.ramp(nz(16.0, 8.0, 0.7), 0.7 - 0.13 * chips, 0.715 - 0.13 * chips)
        ce = g.math("MULTIPLY", g.ramp(g.edges(0.006), 0.05, 0.25), g.ramp(nz(40.0), 0.42, 0.55))
        cm = g.math("MAXIMUM", cm, g.math("MULTIPLY", ce, chips), clamp=True)
        col = g.mix(cm, col, chip_col)
        rgh = g.mixf(cm, rgh, chip_rough)
        met = g.mixf(cm, met, chip_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", cm, 0.5))
    if scuffs:
        sm = g.math("MULTIPLY", g.ramp(nz(11.0, 6.0, 0.7, 1.2), 0.58, 0.72), scuffs)
        streak = lines(g, P, (30.0, 30.0, 8.0), (0.4, 1.1, 0.3), (0.5, 0.2, 0.9), 0.08)
        sm = g.math("MULTIPLY", sm, g.math("ADD", 0.45, g.math("MULTIPLY", streak, 0.55)))
        col = g.mix(g.math("MULTIPLY", sm, 0.75), col, scuff_col or tk.grade(g, col, 0.45, 1.45))
        rgh = g.mixf(sm, rgh, min(1.0, rough + 0.3))
    if scratches:
        sc = scratch_mask(g, P, line_width)
        dens = g.ramp(nz(3.0, 3.0), 0.42, 0.66)
        sc = g.math("MULTIPLY", g.math("MULTIPLY", sc, dens), scratches, clamp=True)
        dark = g.math("MULTIPLY", g.ramp(nz(7.0, 3.0), 0.48, 0.56), dark_scratches)
        scol = g.mix(dark, scratch_col, (0.05, 0.04, 0.03))
        col = g.mix(sc, col, scol)
        rgh = g.mixf(sc, rgh, 0.6)
        met = g.mixf(sc, met, scratch_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.6))
    if edges:
        wm = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.06, 0.3), g.ramp(nz(30.0, 4.0), 0.36, 0.55))
        wm = g.math("MULTIPLY", wm, edges)
        col = g.mix(wm, col, edge_col or scratch_col)
        rgh = g.mixf(wm, rgh, 0.55)
        met = g.mixf(wm, met, scratch_metal)
    if scorch:
        so = g.math("MULTIPLY", g.ramp(nz(3.5, 8.0, 0.65, 0.9), 0.5, 0.68), scorch)
        col = g.mix(so, col, g.mix(nz(12.0), (0.02, 0.016, 0.014), (0.09, 0.05, 0.025)))
        rgh = g.mixf(so, rgh, 0.85)
        met = g.mixf(so, met, 0.0)
    p = tk.photo(g, dirt_set, dirt_scale, (S[0] * 0.3, 0.5, S[2] * 0.2))
    dm = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1]), dirt)
    dm = g.math("MAXIMUM", dm, tk._grime(g, grime), clamp=True)
    col = g.mix(g.math("MULTIPLY", dm, 0.88), col, g.mix(nz(9.0), dirt_col[0], dirt_col[1]))
    rgh = g.mixf(dm, rgh, 0.85)
    met = g.mixf(dm, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", dm, 0.2))
    if grease:
        gm = g.math("MULTIPLY", g.ramp(nz(5.0, 6.0, 0.6, 1.0), 0.56, 0.68), grease)
        col = g.mix(gm, col, tk._darker(g, col, 0.3))
        rgh = g.mixf(gm, rgh, 0.18)
    if late:
        col, rgh, met, height = late(g, W, P, col, rgh, met, height)
    if dust:
        du = g.math("MULTIPLY", g.ramp(up, 0.25, 0.95), g.ramp(nz(8.0, 6.0, 0.6), 0.35, 0.65))
        du = g.math("MULTIPLY", du, dust)
        col = g.mix(du, col, (0.33, 0.29, 0.23))
        rgh = g.mixf(du, rgh, 0.95)
        met = g.mixf(du, met, 0.0)
    if specks:
        spots = g.ramp(voronoi(g, P, 150.0), 0.16, 0.07)
        sp = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.62)), specks)
        col = g.mix(sp, col, (0.025, 0.02, 0.015))
        rgh = g.mixf(sp, rgh, 0.9)
    if splatter:
        drops = g.math("MAXIMUM", g.ramp(voronoi(g, P, 38.0), 0.09, 0.04),
                       g.ramp(voronoi(g, mapping(g, P, loc=(3.1, 1.7, 2.3)), 85.0), 0.13, 0.06))
        region = g.ramp(nz(2.2, 4.0, 0.6, 0.5), 0.5, 0.62)
        spm = g.math("MULTIPLY", g.math("MULTIPLY", drops, region), splatter, clamp=True)
        col = g.mix(spm, col, g.mix(nz(30.0), splatter_col, tk._darker(g, splatter_col, 0.8)))
        rgh = g.mixf(spm, rgh, 0.92)
        met = g.mixf(spm, met, 0.0)
        height = g.math("ADD", height, g.math("MULTIPLY", spm, 0.7))
    if blood:
        reg = g.ramp(nz(1.6, 5.0, 0.6, 0.6), 0.52, 0.66)
        drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 26.0), 0.16, 0.05),
                       g.ramp(nz(25.0, 4.0), 0.42, 0.6))
        smear = g.ramp(nz(9.0, 8.0, 0.7, 1.5), 0.56, 0.64)
        bm_ = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", drops, smear), reg), blood, clamp=True)
        col = g.mix(bm_, col, g.mix(nz(20.0), (0.06, 0.004, 0.003), (0.15, 0.014, 0.009)))
        rgh = g.mixf(bm_, rgh, 0.3)
        met = g.mixf(bm_, met, 0.0)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, bump, 0.0015))


# ---------------------------------------------------------------- export, fit report and previews

def capsule(bone):
    """A bone's capsule hit box as (end, end, radius), in Blender coordinates."""
    c = SK.collider(bone)
    ax = Vector((0.0, 0.0, 0.0))
    ax[c["axis"]] = 1.0
    half = max(0.0, c["height"] / 2 - c["radius"])
    ctr = Vector(c["center"])
    return SK.point(bone, ctr - ax * half), SK.point(bone, ctr + ax * half), c["radius"]


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def export(pieces, fit=("Head",)):
    """Puts every piece on the one part, bakes and writes the model, and prints its triangles, bounds and how close
    it comes to the hit boxes named in `fit` (negative = inside)."""
    for p in pieces:
        zk.on(p, BONE, PART)
    # The stand-in body stays out of the bake: the model's AO and crease grime are its own
    for o in BODY:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=SIZE)
    for o in BODY:
        o.hide_render = False
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    tris = 0
    pts = []
    for part in parts:
        for v in part.data.vertices:
            w = part.matrix_world @ v.co
            pts.append(w)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        tris += sum(len(f.vertices) - 2 for f in part.data.polygons)
    print("[%s] parts %s, %d triangles, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)"
          % (NAME, [p.name for p in parts], tris, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))
    for bone in fit:
        a, b, r = capsule(bone)
        gaps = [seg_distance(p, a, b) - r for p in pts]
        k = min(range(len(gaps)), key=gaps.__getitem__)
        print("[%s] %s hit box: closest %.1f cm at (%.3f, %.3f, %.3f), %d vertices within 1.5 cm"
              % (NAME, bone, 100 * gaps[k], pts[k].x, pts[k].y, pts[k].z, sum(1 for d in gaps if d < 0.015)))
    return parts


def close_up(view, direction, target, distance=0.55, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


def ellipsoid(name, center, radii, mat, u=32, v=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    for vert in bm.verts:
        vert.co = Vector(center) + Vector((vert.co.x * radii[0], vert.co.y * radii[1], vert.co.z * radii[2]))
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def taper(name, a, b, ra, rb, mat, seg=20):
    bm = bmesh.new()
    length = (b - a).length
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=ra, radius2=rb, depth=length)
    for r, z in ((ra, -length / 2), (rb, length / 2)):
        s = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=8, radius=r)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=s["verts"])
    obj = tk.mesh_object(name, bm, mat)
    turn = (b - a).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation((a + b) / 2) @ turn
    return tk.smooth(obj, 60)


def face_marks():
    """Dark dots on the stand-in where Joe's eyes are, to check headwear leaves them clear (previews only)."""
    mat, g = tk.new_material("EyeMark")
    tk.finish(mat, g, (0.03, 0.03, 0.035), 0.0, 0.3)
    for s in (1.0, -1.0):
        ellipsoid("Eye%+d" % s, (0.032 * s, -0.066, 1.719), (0.012, 0.008, 0.008), mat, 12, 8)


# ---------------------------------------------------------------- the wrist's frame

HAND = SK.pos("LeftHand")
FA = (HAND - SK.pos("LeftForeArm")).normalized()  # along the forearm, toward the hand (3 o'clock)
_up = SK.point("LeftHand", (0.0, 1.0, 0.0)) - HAND
DORSAL = (_up - FA * _up.dot(FA)).normalized()  # the back of the wrist (the dial faces this way)
E12 = DORSAL.cross(FA)  # across the wrist, toward the little finger (12 o'clock)
CENTER = HAND - FA * 0.025  # the wrist's middle, 2.5 cm up the forearm from the joint
# The watch is built in its own frame: x toward the hand, y to 12 o'clock, z out of the back of the wrist
WATCH = Matrix.Translation(CENTER) @ Matrix((FA, E12, DORSAL)).transposed().to_4x4()
WRIST = (0.032, 0.0255)  # the wrist's half-width and half-thickness there
A_IN, B_IN = 0.0355, 0.029  # the strap's inside
STRAP_T, STRAP_W = 0.003, 0.019
Z0 = 0.0265  # the case back, resting on the back of the wrist
print("[%s] frame: to the hand %s, to 12 o'clock %s, dial faces %s" % (NAME, tuple(round(c, 3) for c in FA),
                                                                   tuple(round(c, 3) for c in E12),
                                                                   tuple(round(c, 3) for c in DORSAL)))


def place(obj):
    """Moves a piece built in the watch's frame onto the wrist, recording its watch-frame coordinates as "loc"."""
    store(obj, "loc", lambda co: (co.x, co.y, co.z))
    obj.matrix_world = WATCH @ obj.matrix_world
    return bake_transform(obj)


def ellipse(theta, off=0.0):
    """A point on the strap's middle line round the wrist (theta 90 on top, 0 toward 12 o'clock), `off` outward."""
    a, b = A_IN + STRAP_T / 2, B_IN + STRAP_T / 2
    p = Vector((0.0, a * math.cos(theta), b * math.sin(theta)))
    n = Vector((0.0, b * math.cos(theta), a * math.sin(theta))).normalized()
    return p + n * off


def knob(name, center, axis, radius, length, mat, teeth=12, depth=0.0014):
    """A knurled knob along `axis` from `center`."""
    bm = bmesh.new()
    n = teeth * 2
    r0, r1 = [], []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = radius if i % 2 == 0 else radius - depth
        r0.append(bm.verts.new((r * math.cos(t), r * math.sin(t), 0.0)))
        r1.append(bm.verts.new((r * 0.9 * math.cos(t), r * 0.9 * math.sin(t), length)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(r0)))
    bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(center)) @ rot
    return tk.smooth(bake_transform(obj), 30)


# ---------------------------------------------------------------- materials

IMPACT = (0.0055, -0.0046)  # where the crystal was hit, about four o'clock
HOUR, MINUTE, SECOND = (4 + 37 / 60) * 30.0, 37 * 6.0, 13 * 6.0  # stopped at 4:37:13


def hand_mask(g, x, y, degrees, length, width, tail=0.002, taper=0.5):
    """A clock hand at `degrees` clockwise from 12."""
    s, c = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
    u = g.math("ADD", g.math("MULTIPLY", x, s), g.math("MULTIPLY", y, c))
    v = g.math("SUBTRACT", g.math("MULTIPLY", x, c), g.math("MULTIPLY", y, s))
    w = g.math("MULTIPLY", width, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("DIVIDE", g.math("MAXIMUM", u, 0.0),
                                                                                         length), taper)))
    along = band(g, u, -tail, length, 0.0002)
    return g.math("MULTIPLY", along, g.ramp(g.math("SUBTRACT", g.math("ABSOLUTE", v), w), 0.00012, -0.00005))


def crystal_material():
    """The dial seen through the glass (the game draws no see-through, so it's all one opaque surface): black dial,
    lume markers and hands, and the crystal's cracks, crush and grime over it, glossy where the glass is whole."""
    mat, g = tk.new_material("Crystal")
    L = attr(g, "loc")
    x, y, _ = g.separate(L)
    P = mapping(g, L, scale=(60.0, 60.0, 60.0))
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    phi = g.math("ARCTAN2", x, y)
    # Dial: black with a faint sunburst, the minute track and the hour markers
    sun = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", phi, 90.0)), 0.5)
    col = g.mix(g.math("ADD", 0.5, g.math("MULTIPLY", sun, 0.3)), (0.012, 0.012, 0.013), (0.03, 0.03, 0.032))
    f = g.math("MULTIPLY", phi, 12.0 / (2 * math.pi))
    dm = g.math("MULTIPLY", g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", f, g.math("ROUND", f))),
                                   2 * math.pi / 12.0), r)
    f60 = g.math("MULTIPLY", phi, 60.0 / (2 * math.pi))
    d60 = g.math("MULTIPLY", g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", f60, g.math("ROUND", f60))),
                                    2 * math.pi / 60.0), r)
    quarter = g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("DIVIDE", f, 3.0),
                                                           g.math("ROUND", g.math("DIVIDE", f, 3.0)))), 3.0)
    big = g.ramp(quarter, 0.2, 0.1)
    r_in = g.math("SUBTRACT", 0.0112, g.math("MULTIPLY", big, 0.0015))
    radial = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", r, r_in), -0.0002, 0.0002), g.ramp(r, 0.0138, 0.0134))
    markers = g.math("MULTIPLY", radial, g.ramp(dm, g.math("ADD", 0.0007, g.math("MULTIPLY", big, 0.0004)), 0.0004))
    ticks = g.math("MULTIPLY", band(g, r, 0.0139, 0.0146, 0.0001), g.ramp(d60, 0.00022, 0.0001))
    lume = (0.4, 0.39, 0.32)
    col = g.mix(g.math("MAXIMUM", markers, g.math("MULTIPLY", ticks, 0.7)), col, lume)
    # The hands, 4:37:13, and the center pin
    hh = hand_mask(g, x, y, HOUR, 0.0078, 0.0009)
    mh = hand_mask(g, x, y, MINUTE, 0.0122, 0.00065)
    sh = hand_mask(g, x, y, SECOND, 0.013, 0.00022, tail=0.003, taper=0.2)
    hands = g.math("MAXIMUM", hh, mh)
    col = g.mix(hands, col, (0.36, 0.36, 0.33))
    col = g.mix(sh, col, (0.22, 0.03, 0.02))
    col = g.mix(g.ramp(r, 0.001, 0.0006), col, (0.3, 0.3, 0.29))
    # Cracks: spokes out from the hit, two broken rings round it, a crushed white spot where it landed
    dx, dy = g.math("SUBTRACT", x, IMPACT[0]), g.math("SUBTRACT", y, IMPACT[1])
    rho = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy)))
    psi = g.math("ARCTAN2", dy, dx)
    jit = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(3.0, detail=3.0, vector=P), 0.5), 0.5)
    sp = g.math("ADD", g.math("MULTIPLY", psi, 11.0 / (2 * math.pi)), jit)
    spoke_i = g.math("ROUND", sp)
    dsp = g.math("MULTIPLY", g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", sp, spoke_i)), 2 * math.pi / 11.0),
                 rho)
    reach = g.math("ADD", 0.007, g.math("MULTIPLY", white(g, combine(g, spoke_i, 1.7, 0.3)), 0.018))
    spokes = g.math("MULTIPLY", g.ramp(dsp, 0.00028, 0.00009), g.ramp(rho, reach, g.math("SUBTRACT", reach, 0.003)))
    rings = None
    for rr, seed in ((0.0028, 0.2), (0.0062, 1.4)):
        wob = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(2.0, detail=3.0, vector=mapping(g, P, loc=(seed, 0.0, 0.0))),
                                        0.5), 0.0016)
        ring = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ADD", rho, wob), rr)), 0.00022, 0.00008)
        ring = g.math("MULTIPLY", ring, g.ramp(g.noise(1.2, detail=2.0, vector=mapping(g, P, loc=(0.0, seed, 0.0))),
                                               0.42, 0.5))
        rings = ring if rings is None else g.math("MAXIMUM", rings, ring)
    crush = g.ramp(g.math("ADD", rho, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(9.0, vector=P), 0.5), 0.001)),
                   0.0019, 0.0011)
    crack = g.math("MAXIMUM", g.math("MAXIMUM", spokes, rings), crush)
    col = g.mix(g.math("MULTIPLY", crack, 0.85), col, (0.55, 0.56, 0.56))
    # Grime round the edge of the glass and smeared across it
    edge = g.ramp(r, 0.0135, 0.0152)
    smear = g.ramp(g.noise(1.5, detail=5.0, distortion=0.6, vector=P), 0.5, 0.68)
    dirt = g.math("MAXIMUM", edge, g.math("MULTIPLY", smear, 0.6))
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.06, 0.05, 0.04))
    rgh = g.mixf(dirt, 0.06, 0.6)
    rgh = g.mixf(crack, rgh, 0.35)
    height = g.math("ADD", g.math("MULTIPLY", crack, -1.0), g.math("MULTIPLY", g.math("MAXIMUM", markers, hands), 0.4))
    return tk.finish(mat, g, col, 0.0, rgh, g.bump(height, 0.35, 0.0006))


def strap_decals(g, W, P, col, rgh, met, height):
    """Stitching round the strap's edge, holes in the long end, sweat gone black where it lies on the skin."""
    s = g.separate(attr(g, "strapv"))  # arc length, across (-1 to 1), 1 on the long end
    on = g.ramp(g.math("ABSOLUTE", s[2]), 0.5, 0.6)
    across = g.math("ABSOLUTE", s[1])
    dash = g.ramp(g.math("SINE", g.math("MULTIPLY", s[0], 1800.0)), -0.1, 0.5)
    stitch = g.math("MULTIPLY", g.math("MULTIPLY", band(g, across, 0.74, 0.86, 0.03), dash), on)
    col = g.mix(g.math("MULTIPLY", stitch, 0.6), col, (0.11, 0.085, 0.06))
    height = g.math("ADD", height, g.math("MULTIPLY", stitch, 0.5))
    longend = g.ramp(s[2], 1.5, 1.6)
    holes = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(across, 0.17, 0.11),
                                      g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", s[0],
                                                                                                           0.0065)), 0.5)),
                                             0.13, 0.07)), longend)
    holes = g.math("MULTIPLY", holes, band(g, s[0], 0.1, 0.14, 0.002))
    col = g.mix(holes, col, (0.01, 0.008, 0.006))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", holes, 1.5))
    crack = lines(g, P, (120.0, 120.0, 25.0), (0.3, 0.7, 0.2), (0.4, 0.1, 0.2), 0.07, 30.0)
    col = g.mix(g.math("MULTIPLY", crack, 0.6), col, (0.015, 0.01, 0.007))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.5))
    return col, rgh, met, height


crystal = crystal_material()
case_steel = wear("CaseSteel", (0.3, 0.3, 0.29), rough=0.42, metal=0.9, seed=111.0, tone=0.3, scratches=0.8,
                  scratch_col=(0.55, 0.55, 0.54), scratch_metal=1.0, scuffs=0.4, scuff_col=(0.25, 0.25, 0.24),
                  edges=0.6, edge_col=(0.6, 0.6, 0.58), dirt=0.9, dirt_range=(0.16, 0.05), grime=1.0, dust=0.1,
                  specks=0.6, blood=0.4, bump=0.35, grain=0.05, line_width=0.02,
                  dirt_col=((0.03, 0.025, 0.02), (0.08, 0.065, 0.05)))
leather = wear("WatchStrap", (0.045, 0.026, 0.015), rough=0.62, seed=112.0, tone=0.35, scratches=0.4,
               scratch_col=(0.1, 0.07, 0.045), scuffs=0.5, scuff_col=(0.08, 0.055, 0.035), edges=0.9,
               edge_col=(0.12, 0.085, 0.055), dirt=0.8, dirt_range=(0.2, 0.06), grime=1.0, dust=0.1, specks=0.5,
               grease=0.5, blood=0.4, bump=0.45, grain=0.4, grain_scale=220.0, decals=strap_decals,
               dirt_col=((0.018, 0.012, 0.008), (0.045, 0.03, 0.02)))


# ---------------------------------------------------------------- the pieces

CASE_PROFILE = [(0.0, Z0), (0.0165, Z0), (0.0186, Z0 + 0.001), (0.0196, Z0 + 0.003), (0.0196, Z0 + 0.0062),
                (0.019, Z0 + 0.0072), (0.0177, Z0 + 0.0093), (0.0158, Z0 + 0.0095), (0.0153, Z0 + 0.0088),
                (0.0105, Z0 + 0.0096), (0.0055, Z0 + 0.0099), (0.0, Z0 + 0.01)]
CRYSTAL_ROW = 8  # rows from here in are glass


def case():
    cols = 20

    def fn(i, j):
        t = 2 * math.pi * i / cols
        r, z = CASE_PROFILE[j]
        return Vector((r * math.cos(t), r * math.sin(t), z))

    obj = grid("Case", case_steel, cols, len(CASE_PROFILE), fn, pole=True, end_pole=True, closed=True)
    obj.data.materials.append(crystal)
    zc = CASE_PROFILE[CRYSTAL_ROW][1] - 0.0002
    for p in obj.data.polygons:
        c = p.center
        if c.z > zc and math.hypot(c.x, c.y) < CASE_PROFILE[CRYSTAL_ROW][0] + 1e-4:
            p.material_index = 1
    tk.smooth(obj, 35)
    return place(obj)


def lugs():
    out = []
    for sy in (1.0, -1.0):
        for sx in (1.0, -1.0):
            o = tk.box("Lug", (0.0026, 0.0072, 0.0036), (0.0, 0.0, 0.0), case_steel)
            o.matrix_world = Matrix.Translation((sx * 0.0108, sy * 0.0213, Z0 + 0.0032)) @ \
                Matrix.Rotation(math.radians(-22 * sy), 4, "X")
            out.append(place(bake_transform(o)))
    return out


def crown():
    o = knob("Crown", (0.0193, 0.0, Z0 + 0.0046), (1.0, 0.0, 0.0), 0.0029, 0.0036, case_steel, teeth=8, depth=0.0005)
    return place(o)


def strap_piece(name, pts, flag):
    cum = [0.0]
    for k in range(1, len(pts)):
        cum.append(cum[-1] + (pts[k] - pts[k - 1]).length)

    def values(i, k):
        return (cum[i], -1.0 if k in (0, 3) else 1.0, flag)

    o = strap(name, pts, STRAP_W, STRAP_T, leather, (1.0, 0.0, 0.0), values=values, attr_name="strapv")
    return place(o)


def straps():
    lug = Z0 + 0.0022
    deg = math.radians
    short = [Vector((0.0, 0.0236, lug)), Vector((0.0, 0.0268, lug - 0.0032))] + \
        [ellipse(deg(t)) for t in (42, 22, 2, -18, -36, -48)]
    long_ = [Vector((0.0, -0.0236, lug)), Vector((0.0, -0.0268, lug - 0.0032))] + \
        [ellipse(deg(t)) for t in (138, 160, 182, 205, 228, 252, 276, 298)] + \
        [ellipse(deg(312), STRAP_T * 0.6), ellipse(deg(322), STRAP_T * 1.05)] + \
        [ellipse(deg(t), STRAP_T * 1.05) for t in (336, 350, 362)]
    return [strap_piece("StrapShort", short, 1.0), strap_piece("StrapLong", long_, 2.0)]


def buckle():
    """The steel frame at the short end, its prong across the long end, and the keeper round both."""
    deg = math.radians
    th = deg(-49)
    p = ellipse(th, STRAP_T * 0.5)
    tan = (ellipse(th + 0.01) - ellipse(th - 0.01)).normalized()
    nrm = Vector((0.0, -tan.z, tan.y))
    if nrm.dot(p) < 0:
        nrm = -nrm
    xs, ts = 0.0115, 0.0045
    corners = []
    for cx, ct in ((1, -1), (1, 1), (-1, 1), (-1, -1)):
        corners.append(p + Vector((cx * xs, 0.0, 0.0)) + tan * (ct * ts))
    frame = strap("Buckle", corners, 0.0022, 0.0016, case_steel, nrm, closed=True)
    prong = tk.box("Prong", (0.0014, 0.0014, 0.0115), (0.0, 0.0, 0.0), case_steel)
    prong.matrix_world = Matrix.Translation(p + nrm * 0.0024 + tan * 0.0015) @ \
        Matrix((Vector((1.0, 0.0, 0.0)), nrm, tan)).transposed().to_4x4()
    bake_transform(prong)
    th = deg(-28)
    q = ellipse(th, STRAP_T * 0.5)
    tan = (ellipse(th + 0.01) - ellipse(th - 0.01)).normalized()
    nrm = Vector((0.0, -tan.z, tan.y))
    if nrm.dot(q) < 0:
        nrm = -nrm
    lo, hi = -STRAP_T * 0.5 - 0.0007, STRAP_T * 1.6 + 0.0007
    loop = [q + Vector((cx * 0.0103, 0.0, 0.0)) + nrm * h for cx, h in ((1, lo), (1, hi), (-1, hi), (-1, lo))]
    keeper = strap("Keeper", loop, 0.0055, 0.0011, leather, tan, closed=True)
    return [place(frame), place(prong), place(keeper)]


pieces = [case(), crown()] + lugs() + straps() + buckle()
export(pieces, fit=())

# Clearance round the wrist assumed here (an ellipse of WRIST, tapering up the forearm): negative = inside
inv = WATCH.inverted()
worst = 1.0
for o in bpy.data.objects:
    if o.name.startswith("LeftHand#"):
        for v in o.data.vertices:
            q = inv @ (o.matrix_world @ v.co)
            k = (WRIST[0] ** -2 * q.y ** 2 + WRIST[1] ** -2 * q.z ** 2) ** 0.5
            worst = min(worst, (1.0 - 1.0 / max(k, 1e-6)) * math.hypot(q.y, q.z))
print("[%s] closest to the assumed wrist: %.1f mm" % (NAME, 1000 * worst))


def standin_arm():
    """The stand-in's forearm capsule is fat (5 cm) and its hand a single capsule, so for these previews the left
    arm gets a slimmer, flattened forearm, a palm and fingers."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(SK.colliders):
        if c["bone"] == "LeftForeArm":
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    bpy.data.objects.remove(bpy.data.objects["BodyLeftHand"])
    elbow = SK.pos("LeftForeArm")
    rings = 8
    bm = bmesh.new()
    vs = []
    for k in range(rings):
        t = k / (rings - 1)
        c = elbow.lerp(HAND + FA * 0.01, t)
        a = 0.042 + (WRIST[0] - 0.042) * t ** 0.8
        b = 0.036 + (WRIST[1] - 0.036) * t ** 0.8
        vs.append([bm.verts.new(c + E12 * (a * math.cos(2 * math.pi * j / 20)) + DORSAL * (b * math.sin(2 * math.pi * j / 20)))
                   for j in range(20)])
    for k in range(rings - 1):
        for j in range(20):
            j1 = (j + 1) % 20
            bm.faces.new((vs[k][j], vs[k][j1], vs[k + 1][j1], vs[k + 1][j]))
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tk.smooth(tk.mesh_object("PreForeArm", bm, mat), 60)
    ax = (SK.pos("LeftHandMiddle1") - HAND).normalized()
    nh = (DORSAL - ax * DORSAL.dot(ax)).normalized()
    lat = nh.cross(ax)
    palm = tk.box("PrePalm", (0.1, 0.075, 0.03), (0.0, 0.0, 0.0), mat, bevel_width=0.01)
    palm.matrix_world = Matrix.Translation(HAND + ax * 0.045 - nh * 0.004) @ Matrix((ax, lat, nh)).transposed().to_4x4()
    for f in ("Index", "Middle", "Ring", "Pinky", "Thumb"):
        r = 0.0115 if f == "Thumb" else 0.0095
        taper("Pre" + f, SK.pos("LeftHand%s1" % f), SK.pos("LeftHand%s4" % f), r, r * 0.8, mat, seg=12)


standin_arm()
wrist = CENTER + DORSAL * 0.02
zk.previews(SCRIPT, PREVIEWS, wrist, distance=0.5)
close_up("dial", DORSAL + E12 * 0.15 - FA * 0.1, CENTER + DORSAL * 0.03, distance=0.13)
close_up("close", DORSAL * 0.8 - Vector((0.0, 1.0, 0.0)) + FA * 0.2, CENTER + DORSAL * 0.01, distance=0.2)
close_up("under", -DORSAL * 0.9 - Vector((0.0, 0.6, 0.0)), CENTER - DORSAL * 0.02, distance=0.22)
print("[%s] done" % SCRIPT)
