"""Beanie: a dark charcoal knit watch cap pulled down over the ears, its cuff turned up. The crown is stockinette (the
little V stitches in columns that close in toward the top), the cuff a 2x2 rib; the yarn is heathered with lighter
fibers, pilled and fuzzed with lint, a hole worn through at the back with the yarn round it broken. A small woven
label on the cuff, dust settled on top, dried blood and dirt.

One closed knit surface: the inside layer against the hair, folded round at the bottom edge into the cuff, which
overlaps the crown and tucks back into it. The bottom edge sits 1.3 cm over the brows in front, sweeps down past
the temples and covers the ears, and the inside is 2 cm off the head hit box (2.3 cm over the top). One part,
Head#Beanie.

    blender -b --factory-startup --python beanie.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PART, SIZE = "Beanie", "beanie", "Head", "Beanie", 512

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


# ---------------------------------------------------------------- the beanie's shape

CY = HC.y + 0.003
RXI, RYI = 0.121, 0.127  # the inside's half-width and half-length at the bottom edge: 2 cm off the head hit box
TOP_IN = 1.868  # the inside's top
EXP = 2.2
KNIT = 0.0042  # one layer of knit
CUFF = 0.052  # the turned-up cuff's height
COLS = 28
SAMPLES = 160


def edge_z(a):
    """The bottom edge: just over the brows in front, down past the temples, over the ears, a little lower behind."""
    aa = abs(math.atan2(math.sin(a), math.cos(a)))
    return 1.758 - 0.09 * smoothstep(math.radians(12), math.radians(80), aa) \
        - 0.008 * smoothstep(math.radians(90), math.pi, aa)


Z_EQ = 1.745  # where the head hit box's wall meets its top half-sphere


def inside_curve(a):
    """The inside surface's full profile at azimuth a, bottom up: a straight wall 2 cm out from the hit box's, then a
    dome 2.3 cm over its top half-sphere. The top sags back a little."""
    pts = []
    for k in range(40):
        z = 1.6 + (Z_EQ - 1.6) * k / 40
        pts.append(Vector((RXI * math.sin(a), CY - RYI * math.cos(a), z)))
    for k in range(SAMPLES):
        phi = (math.pi / 2) * (1.0 - k / (SAMPLES - 1))
        s = max(0.0, math.sin(phi)) ** (2.0 / EXP)
        c = max(0.0, math.cos(phi)) ** (2.0 / EXP)
        sag = 0.014 * (1.0 - phi / (math.pi / 2)) ** 2
        pts.append(Vector((RXI * s * math.sin(a), CY + sag - RYI * s * math.cos(a), Z_EQ + (TOP_IN - Z_EQ) * c)))
    return pts


class Meridian:
    """The inside surface along one azimuth, by arc length s up from the bottom edge."""

    def __init__(self, a):
        self.a = a
        full = inside_curve(a)
        zb = edge_z(a)
        k = next(i for i in range(len(full) - 1) if full[i + 1].z > zb)
        t = (zb - full[k].z) / max(full[k + 1].z - full[k].z, 1e-9)
        self.pts = [full[k].lerp(full[k + 1], t)] + full[k + 1:]
        self.cum = [0.0]
        for k in range(1, len(self.pts)):
            self.cum.append(self.cum[-1] + (self.pts[k] - self.pts[k - 1]).length)
        self.length = self.cum[-1]
        self.side = Vector((RXI * math.cos(a), RYI * math.sin(a), 0.0)).normalized()

    def frame(self, s):
        """Point, upward tangent and outward normal at arc length s (below the edge, s < 0, it carries on straight)."""
        n = len(self.pts)
        if s <= 0.0:
            k = 0
        else:
            k = next((i for i in range(n - 1) if self.cum[i + 1] >= s), n - 2)
        seg = self.pts[k + 1] - self.pts[k]
        t = (s - self.cum[k]) / max(seg.length, 1e-9)
        p = self.pts[k] + seg * t
        T = seg.normalized()
        N = self.side.cross(T).normalized()
        return p, T, N

    def at(self, s, off):
        p, T, N = self.frame(s)
        return p + N * off


MER = [Meridian(2 * math.pi * i / COLS) for i in range(COLS)]
LEN = sum(m.length for m in MER) / COLS


def profile():
    """Rows from the outside top round to the inside top: (s as a fraction of the meridian or in meters, offset off
    the inside surface, region: 0 crown, 1 cuff, -1 inside)."""
    rows = [("pole", KNIT, 0.0)]
    body0 = CUFF + 0.004
    for k in range(1, 7):
        rows.append((("frac", 1.0 - k / 7.0, body0), KNIT, 0.0))  # crown, top down to just over the cuff
    rows += [(CUFF + 0.0035, KNIT, 0.0), (CUFF + 0.001, KNIT + 0.0022, 1.0), (CUFF - 0.002, 2 * KNIT + 0.0008, 1.0)]
    rows += [(CUFF * 0.66, 2 * KNIT + 0.0012, 1.0), (CUFF * 0.33, 2 * KNIT + 0.0012, 1.0),
             (0.004, 2 * KNIT + 0.0006, 1.0)]
    c = KNIT + 0.0004
    for th in (45, 90, 135):  # rolled round the bottom edge
        t = math.radians(th)
        rows.append((-c * math.sin(t), c + c * math.cos(t), 1.0))
    rows += [(0.0, 0.0, -1.0), (0.03, 0.0, -1.0)]
    for q in (0.35, 0.62, 0.86):
        rows.append((("frac", q, 0.03), 0.0, -1.0))
    rows.append(("pole", 0.0, -1.0))
    return rows


ROWS = profile()


def row_s(m, spec):
    if isinstance(spec, tuple):  # ("frac", q, s0): q of the way from s0 to the top
        _, q, s0 = spec
        return s0 + (m.length - s0) * q
    return spec


def knit_point(i, j):
    spec, off, _ = ROWS[j]
    if spec == "pole":
        top = sum((m.pts[-1] for m in MER), Vector()) / COLS
        return top + Vector((0.0, 0.0, off))
    m = MER[i]
    return m.at(row_s(m, spec), off)


def knit_values(i, j):
    spec, off, region = ROWS[j]
    s = LEN if spec == "pole" else row_s(MER[i], spec)
    return (s, region, off)


# ---------------------------------------------------------------- material

def knit_decals(g, W, P, col, rgh, met, height):
    """Stockinette on the crown, 2x2 rib on the cuff, heathered yarn and lint, the woven label, and the worn hole."""
    x, y, z = g.separate(W)
    k = g.separate(attr(g, "knit"))  # arc length up from the bottom edge, region (1 cuff, 0 crown, -1 inside)
    cuff = g.ramp(k[1], 0.5, 0.6)
    crown = g.math("MULTIPLY", g.ramp(k[1], -0.5, -0.4), g.ramp(k[1], 0.6, 0.5))
    dy = g.math("SUBTRACT", y, CY)
    rh = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", dy, dy)))
    ang = g.math("ARCTAN2", x, g.math("MULTIPLY", dy, -1.0))
    # The cuff's rib: raised knit columns and sunk purl ones, with the stitches stacked up them
    rib = g.ramp(g.math("SINE", g.math("MULTIPLY", ang, 92.0)), -0.35, 0.45)
    loops = g.math("SUBTRACT", 0.5, g.math("MULTIPLY", g.math("COSINE", g.math("MULTIPLY", k[0], 2 * math.pi / 0.004)),
                                           0.5))
    rib_h = g.math("MULTIPLY", rib, g.math("ADD", 0.75, g.math("MULTIPLY", loops, 0.25)))
    # The crown's stockinette: columns of Vs, the columns closing in toward the top
    u = g.math("MULTIPLY", ang, 150.0 / (2 * math.pi))
    fu = g.math("FRACT", u)
    vv = g.math("ADD", g.math("DIVIDE", k[0], 0.0045), g.math("MULTIPLY", g.math("ABSOLUTE", g.math("SUBTRACT", fu, 0.5)),
                                                                      1.4))
    st = g.math("SUBTRACT", 0.5, g.math("MULTIPLY", g.math("COSINE", g.math("MULTIPLY", g.math("FRACT", vv),
                                                                                     2 * math.pi)), 0.5))
    gap = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", fu, 0.5)), 0.4, 0.5)
    st_h = g.math("MULTIPLY", st, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gap, 0.75)))
    st_h = g.math("MULTIPLY", st_h, g.ramp(rh, 0.03, 0.065))
    knit_h = g.math("ADD", g.math("MULTIPLY", rib_h, cuff), g.math("MULTIPLY", st_h, crown))
    height = g.math("ADD", height, g.math("MULTIPLY", knit_h, 1.3))
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, knit_h), g.math("MAXIMUM", cuff, crown)), col,
                tk._darker(g, col, 0.6))
    # Heathered yarn: lighter fibers through it, and pilled lint
    heather = g.ramp(g.noise(300.0, detail=2.0, vector=P), 0.6, 0.72)
    col = g.mix(g.math("MULTIPLY", heather, 0.6), col, tk.grade(g, col, 0.7, 2.2))
    lint = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.7, 0.2, 0.4)), 260.0), 0.09, 0.03),
                  g.ramp(g.noise(5.0, vector=P), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", lint, 0.7), col, (0.16, 0.15, 0.135))
    height = g.math("ADD", height, g.math("MULTIPLY", lint, 0.6))
    # A woven label on the cuff, front left
    ds = g.math("SUBTRACT", k[0], CUFF * 0.5)
    dx = g.math("MULTIPLY", g.math("SUBTRACT", ang, 0.55), rh)
    lab = g.math("MULTIPLY", rect(g, dx, ds, 0.017, 0.0075, 0.0006), cuff)
    lab = frayed(g, lab, mapping(g, P, loc=(1.1, 0.3, 0.6)), 90.0, 0.25)
    letters = g.math("MULTIPLY", g.ramp(white(g, floor_vec(g, combine(g, dx, ds, 5.0), (0.0016, 0.0019, 1.0))), 0.45,
                                        0.47), rect(g, dx, ds, 0.012, 0.0028, 0.0003))
    lcol = g.mix(letters, (0.15, 0.125, 0.08), (0.03, 0.025, 0.02))
    lcol = g.mix(band(g, g.math("ABSOLUTE", ds), 0.0055, 0.0075, 0.0004), lcol, (0.05, 0.04, 0.03))
    col = g.mix(lab, col, lcol)
    rgh = g.mixf(lab, rgh, 0.75)
    height = g.math("ADD", height, g.math("MULTIPLY", lab, 0.8))
    # A hole worn through at the back left, the yarn round it broken and pale
    m = MER[int(COLS * 0.37)]
    hp = m.at(m.length * 0.5, KNIT)
    rag = g.math("ADD", vdist(g, W, tuple(hp)), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(260.0, detail=4.0,
                                                                                            vector=P), 0.5), 0.006))
    hole = g.math("MULTIPLY", g.ramp(rag, 0.0085, 0.0065), crown)
    torn = g.math("MULTIPLY", band(g, rag, 0.0075, 0.011, 0.001), crown)
    col = g.mix(g.math("MULTIPLY", torn, 0.6), col, (0.12, 0.11, 0.1))
    col = g.mix(hole, col, (0.008, 0.007, 0.006))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", hole, 2.0))
    rgh = g.mixf(hole, rgh, 0.95)
    return col, rgh, met, height


knit = wear("Knit", (0.036, 0.034, 0.033), rough=0.95, seed=71.0, tone=0.3, fade=0.25, scratches=0.0, scuffs=0.5,
            scuff_col=(0.07, 0.066, 0.06), edges=0.6, edge_col=(0.09, 0.085, 0.078), dirt=0.7,
            dirt_set="rust_coarse_01", dirt_scale=3.0, dirt_range=(0.14, 0.045), grime=0.9, dust=0.25, specks=0.4,
            blood=0.35, bump=0.7, grain=0.3, grain_scale=420.0, decals=knit_decals,
            dirt_col=((0.03, 0.024, 0.018), (0.09, 0.075, 0.055)))


def beanie():
    obj = grid("Beanie", knit, COLS, len(ROWS), knit_point, pole=True, end_pole=True, closed=True,
               values=knit_values, attr_name="knit")
    # Slack knit: soft lumps, and the crown pushed in a little on the right where it's been grabbed
    tk.dent(obj, 0.0025, 0.04, seed=6)
    m = MER[int(COLS * 0.8)]
    p, T, N = m.frame(m.length * 0.45)
    push(obj, p, 0.045, N * -0.004)
    return tk.smooth(obj, 60)


pieces = [beanie()]
export(pieces, fit=("Head",))
face_marks()
focus = Vector((0.0, 0.0, 1.76))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.9)
close_up("close", (-0.75, -0.9, 0.25), focus, distance=0.45)
close_up("back_close", (0.55, 1.0, 0.3), Vector((0.0, 0.06, 1.77)), distance=0.42)
print("[%s] done" % SCRIPT)
