"""Chain necklace: a soldier's dog tags on a steel ball chain. The chain lies round the base of the neck on the
trapezius, comes forward over the collarbones and runs down the chest in a V to the tags at the breastbone. One tag
hangs on the long chain, the other a little lower on its short loop, swung aside behind the first, a black rubber
silencer round its edge. Stainless tags with rolled rims and embossed lines of lettering, scratched dull, dirt in the
letters and the chain's links, blood dried on the lower ends.

Fitted to Joe's neck and chest as the other neck pieces assume them (a neck column 5.5 cm in radius, the chest hit
box with its top lowered 5 cm to the real shoulder line): the chain 3.5 mm off them, the tags 3 to 6 mm off the
chest hit box. One part, Spine2#Chain.

    blender -b --factory-startup --python chain_necklace.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PART, SIZE = "ChainNecklace", "chain_necklace", "Spine2", "Chain", 512

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


# ---------------------------------------------------------------- Joe's neck and chest, as the chain lies on them

NECK_AXIS, NECK_R = Vector((0.0, 0.032, 0.0)), 0.055
_ca, _cb, CHEST_R = capsule("Spine2")
CHEST_A, CHEST_B = _ca, _cb - Vector((0.0, 0.0, 0.05))  # the hit box's top half-sphere lowered to the shoulders
CHAIN_R = 0.0016  # ball chain, 3.2 mm
OFF = CHAIN_R + 0.0035  # the chain's center off the skin


def chest_sd(q):
    ab = CHEST_B - CHEST_A
    t = max(0.0, min(1.0, (q - CHEST_A).dot(ab) / ab.length_squared))
    c = CHEST_A + ab * t
    return (q - c).length - CHEST_R, (q - c).normalized()


def neck_sd(q):
    d = Vector((q.x - NECK_AXIS.x, q.y - NECK_AXIS.y, 0.0))
    return d.length - NECK_R, d.normalized()


def drape(q, off=OFF):
    """Moves q onto the surface `off` outside the neck and chest (whichever it lies on)."""
    q = q.copy()
    for _ in range(12):
        sc, nc = chest_sd(q)
        sn, nn = neck_sd(q)
        if sn < sc:
            if sn < off:  # inside the neck's clearance: out sideways
                q += nn * (off - sn)
                continue
        q += nc * (off - sc)
    return q


def neck_ring(b):
    """Where the chain sits round the back of the neck (b: 0 front, + left): in the crease between the neck and the
    trapezius."""
    d = Vector((math.sin(b), -math.cos(b), 0.0))
    # a little further out behind, so it stays clear of the head's hit box (which reaches down the back of the neck)
    p = NECK_AXIS + d * (NECK_R + OFF + 0.0015 + 0.004 * max(0.0, -math.cos(b)))
    c = CHEST_B
    h = math.hypot(p.x - c.x, p.y - c.y)
    p.z = c.z + math.sqrt(max(0.0, (CHEST_R + OFF) ** 2 - h * h))
    return p


B_OFF = math.radians(68)  # where the chain leaves the neck and heads down the chest
RING = drape(Vector((0.0, -0.2, 1.432)))
RING.y -= 0.0012  # pulled out a touch by the tags' weight


def chain_path():
    """The closed loop: round the back of the neck, down the left side of the chest to the tags, back up the right."""
    back = [neck_ring(B_OFF + (2 * math.pi - 2 * B_OFF) * k / 13) for k in range(14)]  # left front, round, right
    left = []
    p0 = neck_ring(B_OFF)
    t0 = (neck_ring(B_OFF - 0.05) - p0).normalized()
    ctrl = p0 + t0 * 0.05
    end = RING + Vector((0.007, 0.0, 0.0045))
    for k in range(1, 11):
        t = k / 11
        q = p0 * (1 - t) ** 2 + ctrl * (2 * (1 - t) * t) + end * (t * t)
        left.append(drape(q))
    right = [Vector((-q.x, q.y, q.z)) for q in left]
    bottom = [end, RING, Vector((-end.x, end.y, end.z))]
    # The back arc runs from the left of the neck round to the right: then down the right, through the tags, and up
    # the left back to the start
    return back + right + bottom[::-1] + list(reversed(left))


def body_normal(p):
    sc, nc = chest_sd(p)
    sn, nn = neck_sd(p)
    return nn if sn < sc else nc


# ---------------------------------------------------------------- materials

def ball_chain(g, W, P, col, rgh, met, height):
    """Balls on the chain (along its length, from the stored arc length), dirt packed between them."""
    c = g.separate(attr(g, "chain"))
    f = g.math("FRACT", g.math("DIVIDE", c[0], 0.0032))
    x = g.math("SUBTRACT", g.math("MULTIPLY", f, 2.0), 1.0)
    ball = g.math("SQRT", g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", x, x)), 0.0))
    on = g.ramp(c[2], 0.5, 0.6)
    gap = g.math("MULTIPLY", g.ramp(ball, 0.45, 0.2), on)
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("MULTIPLY", ball, on), 2.0))
    col = g.mix(gap, col, (0.03, 0.025, 0.02))
    rgh = g.mixf(gap, rgh, 0.85)
    met = g.mixf(gap, met, 0.0)
    return col, rgh, met, height


def tag_decals(g, W, P, col, rgh, met, height):
    """The rolled rim, five lines of embossed lettering (raised on the front, sunk on the back), dirt in them."""
    t = g.separate(attr(g, "tag"))  # across, along (hole end +), through (front +); 4th tag flag in z beyond
    x, y = t[0], t[1]
    on = g.ramp(g.separate(attr(g, "tagon"))[0], 0.5, 0.6)
    hw, hh, r = 0.0143, 0.0254, 0.004
    qx = g.math("MAXIMUM", g.math("SUBTRACT", g.math("ABSOLUTE", x), hw - r), 0.0)
    qy = g.math("MAXIMUM", g.math("SUBTRACT", g.math("ABSOLUTE", y), hh - r), 0.0)
    d = g.math("SUBTRACT", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", qx, qx), g.math("MULTIPLY", qy, qy))), r)
    rim = g.math("MULTIPLY", band(g, d, -0.0019, -0.0007, 0.0003), on)
    text = None
    for k, (xc, length) in enumerate(((-0.0085, 0.031), (-0.0042, 0.026), (0.0, 0.034), (0.0042, 0.021),
                                      (0.0085, 0.028))):
        y0 = -0.0185
        row = g.math("MULTIPLY", band(g, x, xc - 0.0013, xc + 0.0013, 0.0002), band(g, y, y0, y0 + length, 0.0002))
        cell = g.math("FRACT", g.math("DIVIDE", g.math("SUBTRACT", y, y0), 0.0022))
        pix = g.ramp(white(g, floor_vec(g, combine(g, x, y, 3.0 + k), (0.00052, 0.0006, 1.0))), 0.4, 0.42)
        ln = g.math("MULTIPLY", g.math("MULTIPLY", row, g.ramp(cell, 0.84, 0.8)), pix)
        text = ln if text is None else g.math("MAXIMUM", text, ln)
    text = g.math("MULTIPLY", text, on)
    side = g.math("SUBTRACT", g.math("MULTIPLY", g.ramp(t[2], -0.0002, 0.0002), 2.0), 1.0)  # +1 front, -1 back
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("ADD", rim, g.math("MULTIPLY", text, side)), 1.5))
    grime = g.math("MULTIPLY", text, g.ramp(g.noise(60.0, vector=P), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", grime, 0.7), col, (0.05, 0.042, 0.032))
    col = g.mix(g.math("MULTIPLY", rim, 0.4), col, tk.grade(g, col, 0.8, 1.25))
    # Blood dried on the lower ends
    low = g.math("MULTIPLY", g.ramp(y, -0.008, -0.024), on)
    low = g.math("MULTIPLY", low, g.ramp(g.noise(40.0, detail=6.0, distortion=0.8, vector=P), 0.38, 0.55))
    col = g.mix(g.math("MULTIPLY", low, 0.85), col, (0.07, 0.008, 0.005))
    rgh = g.mixf(low, rgh, 0.35)
    met = g.mixf(low, met, 0.0)
    return col, rgh, met, height


steel_chain = wear("BallChain", (0.34, 0.34, 0.33), rough=0.42, metal=0.9, seed=101.0, tone=0.35, scratches=0.3,
                   scratch_col=(0.5, 0.5, 0.49), scratch_metal=1.0, scuffs=0.3, edges=0.0, dirt=0.9,
                   dirt_range=(0.16, 0.05), grime=0.8, dust=0.2, specks=0.6, blood=0.3, bump=0.5, grain=0.05,
                   decals=ball_chain, dirt_col=((0.03, 0.025, 0.02), (0.08, 0.065, 0.05)))
tag_steel = wear("DogTag", (0.34, 0.34, 0.33), rough=0.45, metal=0.85, seed=102.0, tone=0.35, scratches=0.9,
                 scratch_col=(0.55, 0.55, 0.54), scratch_metal=1.0, dark_scratches=0.5, scuffs=0.5,
                 scuff_col=(0.24, 0.24, 0.23), edges=0.6, edge_col=(0.55, 0.55, 0.53), dirt=0.85,
                 dirt_range=(0.16, 0.05), grime=1.0, dust=0.15, specks=0.7, blood=0.45, grease=0.3, bump=0.45, grain=0.08, line_width=0.02,
                 decals=tag_decals, dirt_col=((0.035, 0.03, 0.024), (0.09, 0.075, 0.055)))
rubber = wear("Silencer", (0.022, 0.021, 0.02), rough=0.75, seed=103.0, tone=0.25, scratches=0.2,
              scratch_col=(0.08, 0.08, 0.075), scuffs=0.4, scuff_col=(0.06, 0.058, 0.055), edges=0.5,
              edge_col=(0.1, 0.098, 0.093), dirt=0.6, dirt_range=(0.2, 0.06), grime=0.8, dust=0.2, specks=0.4,
              bump=0.3)


# ---------------------------------------------------------------- the pieces

def chain_loop(name, pts, side, closed=True):
    cum = [0.0]
    for k in range(1, len(pts)):
        cum.append(cum[-1] + (pts[k] - pts[k - 1]).length)
    return rope(name, pts, CHAIN_R, CHAIN_R, steel_chain, side=side, sides=5, closed=closed,
                values=lambda i, k: (cum[i], 0.0, 1.0), attr_name="chain")


TAG_W, TAG_L, TAG_T = 0.0286, 0.0508, 0.0009
HOLE_Y = TAG_L / 2 - 0.0045


def tag(name, top, swing, depth):
    """A dog tag hanging from the point `top` (its hole's center), swung `swing` degrees about the chest's normal,
    its middle plane at y = depth."""
    hw, hh, r = TAG_W / 2, TAG_L / 2, 0.004
    outline = []
    for cx, cy, a0 in ((hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180), (hw - r, -hh + r, 270)):
        for k in range(4):
            a = math.radians(a0 + 90 * k / 3)
            outline.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, -TAG_T / 2)) for x, y in outline]
    hi = [bm.verts.new((x, y, TAG_T / 2)) for x, y in outline]
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    n = len(outline)
    for k in range(n):
        k1 = (k + 1) % n
        bm.faces.new((lo[k], lo[k1], hi[k1], hi[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, tag_steel)
    hole = tk.cylinder(name + "Hole", 0.0023, -0.01, 0.01, tag_steel, segments=8, center=(0.0, HOLE_Y))
    cut(obj, hole, 0)
    store(obj, "tag", lambda co: (co.x, co.y, co.z))
    store(obj, "tagon", lambda co: (1.0, 0.0, 0.0))
    # Local x across, y up the tag (hole up), z out of the chest; swung about the hole
    rot = Matrix.Rotation(math.radians(swing), 4, Vector((0.0, -1.0, 0.0)))
    frame = Matrix(((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, -1.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
    hole_c = Vector((top.x, depth, top.z))
    obj.matrix_world = Matrix.Translation(hole_c) @ rot @ frame @ Matrix.Translation((0.0, -HOLE_Y, 0.0))
    bake_transform(obj)
    return tk.smooth(obj, 30)


def silencer(name, swing, top, depth):
    """A rubber ring round the edge of a tag (placed the same way)."""
    hw, hh, r = TAG_W / 2 + 0.0007, TAG_L / 2 + 0.0007, 0.0047
    pts = []
    for cx, cy, a0 in ((hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180), (hw - r, -hh + r, 270)):
        for k in range(4):
            a = math.radians(a0 + 90 * k / 3)
            pts.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a), 0.0)))
    obj = strap(name, pts, 0.0024, 0.0016, rubber, (0.0, 0.0, 1.0), closed=True)
    rot = Matrix.Rotation(math.radians(swing), 4, Vector((0.0, -1.0, 0.0)))
    frame = Matrix(((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, -1.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
    obj.matrix_world = Matrix.Translation(Vector((top.x, depth, top.z))) @ rot @ frame @ \
        Matrix.Translation((0.0, -HOLE_Y, 0.0))
    return bake_transform(obj)


path = chain_path()
normals = [body_normal(p) for p in path]
main = chain_loop("Chain", path, lambda i: normals[i])
# Tag A on the long chain, its hole round the chain at the bottom of the V; tag B on its short loop, lower, behind
top_a = RING + Vector((0.0, 0.0, -0.0006))
depth_a = RING.y - 0.0012
tag_a = tag("TagA", top_a, -4.0, depth_a)
top_b = RING + Vector((0.0045, 0.0, -0.016))
depth_b = RING.y + 0.0016
tag_b = tag("TagB", top_b, 13.0, depth_b)
ring_b = silencer("SilencerB", 13.0, top_b, depth_b)
# The short loop from the main chain down through tag B's hole
loop_pts = []
for k in range(10):
    t = 2 * math.pi * k / 10
    loop_pts.append(Vector((RING.x + 0.0025 + 0.0025 * math.sin(t), RING.y + 0.0004,
                            RING.z - 0.0085 + 0.0085 * math.cos(t))))
short = chain_loop("ShortChain", loop_pts, (0.0, 1.0, 0.0))
pieces = [main, tag_a, tag_b, ring_b, short]
export(pieces, fit=("Spine2", "Head"))

# How close it all comes to the neck and lowered chest it was fitted to (negative = inside)
pts = [o.matrix_world @ v.co for o in bpy.data.objects if o.name.startswith("Spine2") for v in o.data.vertices]
gaps = [min(chest_sd(p)[0], neck_sd(p)[0] if 1.44 < p.z < 1.69 else 1.0) for p in pts]
k = min(range(len(gaps)), key=gaps.__getitem__)
print("[%s] fitted neck and chest: closest %.1f cm at (%.3f, %.3f, %.3f)" % (NAME, 100 * gaps[k], *pts[k]))


def standin_neck():
    """The stand-in's head capsule reaches down over the neck and its chest capsule up past the base of the neck, so
    for these previews they're swapped for a skull, jaw, neck column and the lowered chest the chain was fitted to."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(SK.colliders):
        if c["bone"] in ("Head", "Spine2"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    zk._capsule("PreChest", CHEST_A, CHEST_B, CHEST_R, mat)
    ellipsoid("PreSkull", (0.0, 0.03, 1.738), (0.079, 0.1, 0.104), mat)
    ellipsoid("PreJaw", (0.0, -0.022, 1.652), (0.062, 0.066, 0.055), mat)
    tk.cylinder("PreNeck", NECK_R, 1.44, 1.69, mat, segments=32, center=(NECK_AXIS.x, NECK_AXIS.y))


standin_neck()
focus = Vector((0.0, -0.02, 1.47))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.85)
close_up("close", (-0.35, -1.0, 0.15), Vector((0.0, -0.1, 1.42)), distance=0.22)
close_up("neck", (0.7, 0.9, 0.5), Vector((0.0, 0.03, 1.54)), distance=0.42)
close_up("profile", (1.0, -0.2, 0.0), Vector((0.0, -0.03, 1.48)), distance=0.4)
print("[%s] done" % SCRIPT)
