"""Baseball cap: a six-panel cotton-twill cap in a red long since sun-faded to a dusty brick on top, worn pale on the
seams and the edge of the peak, a feed-store patch on the front gone grey with dirt. Each panel has its seam and
top-stitching and an embroidered eyelet; a fabric button sits on top. The pre-curved peak has rows of stitching
along its edge and the old grey-green underside. Round the back an arched opening shows the hair over a black
plastic snap strap. Inside, a sweatband gone brown, and on the crown a dark sweat line with salt rings above it.

The cap sits with its front edge 1.7 cm over the brows (the peak shades the eyes, which stay clear under it), the
inside about 2 cm off the head hit box at the sides, 2.5 to 3 cm over the top. One part, Head#Cap.

    blender -b --factory-startup --python baseball_cap.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PART, SIZE = "BaseballCap", "baseball_cap", "Head", "Cap", 512

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


# ---------------------------------------------------------------- the cap's shape

CY = HC.y + 0.002  # crown center, front to back
RX, RY = 0.123, 0.131  # outer half-width and half-length at the band: the inside 2 cm off the head hit box
TOP = 1.874  # outer top of the crown
EXP = 2.5  # the crown's profile: fuller than an ellipse
THICK = 0.003
COLS, ROWS = 28, 8
BC, BR = 15, 5  # the peak's grid, across and out
PEAK = 0.072  # how far the peak reaches out in front
BRIM_A = math.radians(80)  # it runs round to here either side


def band_z(a):
    """The crown's bottom edge (a: 0 front, + left): on the forehead in front, over the ears, down at the back."""
    return 1.738 + 0.024 * math.cos(a)


def dome(a, phi):
    """The crown's outside: phi 0 at the button, pi/2 at the band."""
    zb = band_z(a)
    s = max(0.0, math.sin(phi)) ** (2.0 / EXP)
    c = max(0.0, math.cos(phi)) ** (2.0 / EXP)
    k = 1.0 + 0.035 * max(0.0, math.cos(a)) ** 2 * math.sin(2 * phi)  # the front panels stand up fuller
    return Vector((RX * s * k * math.sin(a), CY - RY * s * k * math.cos(a), zb + (TOP - zb) * c))


def crown_point(i, j):
    return dome(2 * math.pi * i / COLS, (math.pi / 2) * j / (ROWS - 1))


def brim_len(u):
    return 0.006 + (PEAK - 0.006) * max(0.0, 1.0 - abs(u) ** 2.4) ** 0.55


def brim_point(i, j):
    u = -1.0 + 2.0 * i / (BC - 1)
    a = u * BRIM_A
    w = j / (BR - 1)
    base = dome(a, math.pi / 2)
    n = Vector((math.sin(a) / RX, -math.cos(a) / RY, 0.0)).normalized()
    fwd = (n + Vector((0.0, -0.7, 0.0))).normalized()
    L = brim_len(u)
    d = w * L
    p = base - n * 0.002 + fwd * d  # tucked 2 mm into the crown's edge
    # Tipped down 13 degrees, bent down at the sides (a pre-curved peak) and a little more toward the tip
    p.z += 0.0015 - d * math.tan(math.radians(12)) - 0.032 * u * u * w * (L / PEAK) - 0.007 * (d / PEAK) ** 2
    return p


def brim_values(i, j):
    u = -1.0 + 2.0 * i / (BC - 1)
    return (u, brim_len(u) * (1.0 - j / (BR - 1)), 1.0)  # across, distance from the edge, "on the peak"


# ---------------------------------------------------------------- materials

def cap_decals(g, W, P, col, rgh, met, height):
    """Panel seams and top-stitching, eyelets, the sweat line and salt rings, the front patch, and the rows of
    stitching on the peak."""
    x, y, z = g.separate(W)
    b = g.separate(attr(g, "brim"))  # across, distance from the edge, 1 on the peak
    on_brim = g.ramp(b[2], 0.5, 0.6)
    crown = g.math("SUBTRACT", 1.0, on_brim)
    dy = g.math("SUBTRACT", y, CY)
    rh = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", dy, dy)))
    ang = g.math("ARCTAN2", x, g.math("MULTIPLY", dy, -1.0))
    # Six panel seams from the button to the band, top-stitched either side
    t = g.math("MULTIPLY", ang, 3.0 / math.pi)
    f = g.math("SUBTRACT", t, g.math("ROUND", t))
    d = g.math("MULTIPLY", g.math("MULTIPLY", g.math("ABSOLUTE", f), math.pi / 3.0), rh)
    near = g.math("MULTIPLY", g.ramp(rh, 0.012, 0.03), crown)
    seam = g.math("MULTIPLY", g.ramp(d, 0.0016, 0.0005), near)
    along = g.math("ADD", rh, g.math("SUBTRACT", TOP, z))
    dash = g.ramp(g.math("SINE", g.math("MULTIPLY", along, 1500.0)), -0.1, 0.5)
    stitch = g.math("MULTIPLY", g.math("MULTIPLY", band(g, d, 0.0033, 0.0047, 0.0004), dash), near)
    col = g.mix(g.math("MULTIPLY", seam, 0.75), col, tk._darker(g, col, 0.3))
    col = g.mix(g.math("MULTIPLY", stitch, 0.45), col, tk._darker(g, col, 0.55))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", seam, 1.4))
    height = g.math("ADD", height, g.math("MULTIPLY", stitch, 0.5))
    # Ridges beside each seam (the folded seam allowance underneath), worn pale
    ridge = g.math("MULTIPLY", band(g, d, 0.0012, 0.006, 0.0015), near)
    height = g.math("ADD", height, g.math("MULTIPLY", ridge, 0.5))
    col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", ridge, g.ramp(g.noise(30.0, vector=P), 0.45, 0.65)), 0.35),
                col, tk.grade(g, col, 0.6, 1.6))
    # An embroidered eyelet on each panel
    for k in range(6):
        e = dome(math.radians(30 + 60 * k), 0.62)
        de = vdist(g, W, tuple(e))
        ring = band(g, de, 0.0021, 0.0042, 0.0005)
        hole = g.ramp(de, 0.0023, 0.0015)
        col = g.mix(g.math("MULTIPLY", ring, 0.8), col, tk._darker(g, col, 0.45))
        col = g.mix(hole, col, (0.012, 0.01, 0.009))
        rgh = g.mixf(hole, rgh, 0.95)
        height = g.math("ADD", height, g.math("MULTIPLY", ring, 0.6))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", hole, 1.2))
    # Sweat soaked up from the band, a pale salt line along its wavy top and an older fainter one above
    cosa = g.math("DIVIDE", g.math("MULTIPLY", dy, -1.0), g.math("MAXIMUM", rh, 0.001))
    hb = g.math("SUBTRACT", z, g.math("ADD", 1.738, g.math("MULTIPLY", cosa, 0.024)))
    hw = g.math("ADD", hb, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(9.0, detail=4.0, vector=P), 0.5), 0.03))
    soak = g.math("MULTIPLY", g.ramp(hw, 0.04, 0.024), crown)
    salt = g.math("MULTIPLY", band(g, hw, 0.037, 0.041, 0.0015), crown)
    salt2 = g.math("MULTIPLY", g.math("MULTIPLY", band(g, hw, 0.054, 0.0565, 0.0012), crown),
                   g.ramp(g.noise(6.0, vector=P), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", soak, 0.65), col, tk._darker(g, col, 0.45))
    rgh = g.mixf(soak, rgh, 0.72)
    salt = g.math("MULTIPLY", g.math("MAXIMUM", salt, g.math("MULTIPLY", salt2, 0.6)),
                  g.ramp(g.noise(14.0, detail=5.0, vector=P), 0.3, 0.62))
    col = g.mix(g.math("MULTIPLY", salt, 0.38), col, (0.26, 0.23, 0.19))
    # The patch on the front: a rounded canvas oblong, a stitched border, two lines of lettering
    zc, ph, pw = 1.81, 0.019, 0.031
    dz = g.math("SUBTRACT", z, zc)
    pe = g.math("ADD", g.math("POWER", g.math("ABSOLUTE", g.math("DIVIDE", x, pw)), 4.0),
                g.math("POWER", g.math("ABSOLUTE", g.math("DIVIDE", dz, ph)), 4.0))
    front = g.math("MULTIPLY", g.ramp(y, CY - 0.07, CY - 0.09), crown)
    patch = g.math("MULTIPLY", g.ramp(pe, 1.0, 0.9), front)
    patch = frayed(g, patch, mapping(g, P, loc=(0.3, 0.7, 0.1)), 60.0, 0.25)
    border = g.math("MULTIPLY", band(g, pe, 0.62, 0.8, 0.03), patch)
    glyphs = None
    for zlo, zhi, half, cw, seed in ((0.0012, 0.0098, 0.024, 0.0053, 3.0), (-0.0112, -0.0042, 0.018, 0.0041, 7.0)):
        cell = g.math("FRACT", g.math("DIVIDE", g.math("ADD", x, 1.0), cw))
        fv = floor_vec(g, combine(g, x, dz, seed), (cw / 3.0, (zhi - zlo) / 5.0, 1.0))
        pix = g.ramp(white(g, fv), 0.42, 0.44)
        on = g.math("MULTIPLY", g.math("MULTIPLY", band(g, dz, zlo, zhi, 0.0002), band(g, x, -half, half, 0.0002)),
                    g.ramp(cell, 0.78, 0.74))
        gl = g.math("MULTIPLY", pix, on)
        glyphs = gl if glyphs is None else g.math("MAXIMUM", glyphs, gl)
    glyphs = g.math("MULTIPLY", glyphs, patch)
    pcol = g.mix(g.noise(40.0, vector=P), (0.3, 0.28, 0.23), (0.36, 0.33, 0.27))
    pcol = g.mix(g.math("MAXIMUM", border, glyphs), pcol, (0.07, 0.022, 0.018))
    col = g.mix(patch, col, pcol)
    rgh = g.mixf(patch, rgh, 0.85)
    height = g.math("ADD", height, g.math("MULTIPLY", patch, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", g.math("MAXIMUM", border, glyphs), 0.6))
    # Rows of stitching round the peak, parallel to its edge
    rows = band(g, g.math("FRACT", g.math("DIVIDE", b[1], 0.0062)), 0.4, 0.6, 0.06)
    rows = g.math("MULTIPLY", g.math("MULTIPLY", rows, on_brim), g.ramp(b[1], 0.042, 0.036))
    rows = g.math("MULTIPLY", rows, g.ramp(g.math("SINE", g.math("MULTIPLY", b[0], 520.0)), -0.1, 0.5))
    col = g.mix(g.math("MULTIPLY", rows, 0.55), col, tk._darker(g, col, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", rows, 0.5))
    return col, rgh, met, height


def cap_late(g, W, P, col, rgh, met, height):
    """Over the dirt: blotches of old grime, and the front of the peak blackened where it's been grabbed."""
    blot = g.ramp(g.noise(3.2, detail=6.0, roughness=0.65, distortion=0.7, vector=P), 0.54, 0.7)
    col = g.mix(g.math("MULTIPLY", blot, 0.55), col, tk._darker(g, col, 0.5))
    rgh = g.mixf(blot, rgh, 0.8)
    b = g.separate(attr(g, "brim"))
    grab = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(b[2], 0.5, 0.6), g.ramp(b[1], 0.03, 0.008)),
                  g.ramp(g.math("ABSOLUTE", b[0]), 0.55, 0.25))
    grab = g.math("MULTIPLY", grab, g.ramp(g.noise(18.0, detail=5.0, vector=P), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", grab, 0.8), col, (0.035, 0.026, 0.02))
    rgh = g.mixf(grab, rgh, 0.55)
    return col, rgh, met, height


fabric = wear("CapTwill", (0.13, 0.036, 0.03), rough=0.92, seed=61.0, tone=0.3, fade=0.4, scratches=0.0,
              scuffs=0.55, scuff_col=(0.17, 0.09, 0.075), edges=0.75, edge_col=(0.22, 0.15, 0.12), dirt=0.9,
              dirt_set="rust_coarse_01", dirt_scale=2.6, dirt_range=(0.13, 0.04), grime=1.0, dust=0.2, specks=0.8,
              grease=0.4, blood=0.4, bump=0.5, grain=0.35, grain_scale=260.0, decals=cap_decals, late=cap_late,
              dirt_col=((0.04, 0.03, 0.022), (0.11, 0.085, 0.06)))
lining = wear("CapLining", (0.08, 0.026, 0.022), rough=0.92, seed=62.0, tone=0.35, scratches=0.0, scuffs=0.3,
              edges=0.3, edge_col=(0.12, 0.07, 0.05), dirt=0.9, dirt_range=(0.2, 0.06), grime=1.0, dust=0.0,
              specks=0.7, blood=0.2, bump=0.4, grain=0.35, grain_scale=260.0,
              dirt_col=((0.03, 0.022, 0.015), (0.08, 0.06, 0.04)))
under = wear("PeakUnder", (0.045, 0.056, 0.042), rough=0.92, seed=63.0, tone=0.4, scratches=0.0, scuffs=0.5,
             scuff_col=(0.08, 0.085, 0.065), edges=0.6, edge_col=(0.12, 0.11, 0.09), dirt=1.0,
             dirt_range=(0.24, 0.07), grime=1.0, dust=0.0, specks=0.8, grease=0.5, blood=0.25, bump=0.4, grain=0.35,
             grain_scale=260.0,
             dirt_col=((0.025, 0.022, 0.016), (0.07, 0.06, 0.045)))
sweat = wear("CapSweatband", (0.2, 0.18, 0.15), rough=0.9, seed=64.0, tone=0.35, scratches=0.0, scuffs=0.0,
             edges=0.3, dirt=1.0, dirt_set="metal_plate_02", dirt_scale=4.0, dirt_range=(0.42, 0.12), grime=1.0,
             dust=0.0, specks=0.7, blood=0.35, bump=0.6, grain=0.5, grain_scale=300.0,
             dirt_col=((0.05, 0.035, 0.02), (0.12, 0.085, 0.045)))
snap = wear("CapSnap", (0.022, 0.021, 0.02), rough=0.42, seed=65.0, tone=0.2, scratches=0.4,
            scratch_col=(0.1, 0.1, 0.095), scuffs=0.3, scuff_col=(0.06, 0.058, 0.055), edges=0.6,
            edge_col=(0.12, 0.118, 0.11), dirt=0.6, dirt_range=(0.2, 0.06), grime=0.8, dust=0.2, specks=0.4,
            bump=0.3)


# ---------------------------------------------------------------- the pieces

def crown():
    obj = grid("Crown", fabric, COLS, ROWS, crown_point, pole=True)
    tk.dent(obj, 0.0022, 0.035, seed=3)  # soft cloth, crumpled
    # The left front panel pushed in, a crease across the right side
    push(obj, dome(0.55, 0.75), 0.04, (dome(0.55, 0.75) - Vector((0.0, CY, 1.76))).normalized() * -0.004)
    push(obj, dome(-1.9, 0.6), 0.03, (dome(-1.9, 0.6) - Vector((0.0, CY, 1.76))).normalized() * -0.0025)
    thicken(obj, THICK, inner=lining)
    # The arched opening over the snap strap at the back
    zb = band_z(math.pi)
    hw, z1, arch = 0.03, zb + 0.016, 0.022
    outline = [(-hw, zb - 0.02), (hw, zb - 0.02), (hw, z1)]
    for k in range(1, 8):
        t = math.pi * k / 8
        outline.append((hw * math.cos(t), z1 + arch * math.sin(t)))
    outline.append((-hw, z1))
    cutter = prism("Opening", outline, Vector((-1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)), fabric,
                   d0=CY + 0.06, d1=CY + 0.3)
    cut(obj, cutter, 0)
    return tk.smooth(obj, 50)


def peak():
    obj = grid("Peak", fabric, BC, BR, brim_point, cyclic=False, inside=Vector((0.0, -0.12, 1.6)),
               values=brim_values, attr_name="brim")
    tk.dent(obj, 0.0012, 0.03, seed=5)
    thicken(obj, 0.0045, inner=under, rim=fabric)
    return tk.smooth(obj, 50)


def button():
    def fn(i, j):
        t = 2 * math.pi * i / 10
        r = (0.0, 0.0062, 0.0088)[j]
        return Vector((r * math.cos(t), CY + r * math.sin(t), TOP - 0.001 + (0.0045, 0.0034, 0.0004)[j]))
    return tk.smooth(grid("Button", fabric, 10, 3, fn, pole=True, inside=Vector((0.0, CY, TOP - 0.05))), 70)


def snap_strap():
    """The plastic adjuster across the bottom of the opening, its ends sunk in the crown's cut edges, and the
    overlapping tab with the snaps."""
    def ring(a, inset, lift):
        return Vector(((RX - inset) * math.sin(a), CY - (RY - inset) * math.cos(a), band_z(a) + lift))
    pts = [ring(math.radians(163 + 34 * k / 6), THICK * 0.5, 0.008) for k in range(7)]
    tab = [ring(math.radians(168 + 22 * k / 4), -0.0012, 0.0078) for k in range(5)]
    return [strap("Strap", pts, 0.016, 0.0022, snap), strap("StrapTab", tab, 0.0125, 0.002, snap)]


def sweatband():
    pts = []
    for k in range(15):
        a = math.radians(-163 + 326 * k / 14)
        inset = THICK + 0.002
        pts.append(Vector(((RX - inset) * math.sin(a), CY - (RY - inset) * math.cos(a), band_z(a) + 0.0135)))
    return strap("Sweatband", pts, 0.026, 0.0018, sweat)


pieces = [crown(), peak(), button(), sweatband()] + snap_strap()
export(pieces, fit=("Head",))
face_marks()
focus = Vector((0.0, 0.0, 1.77))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.9)
close_up("close", (-0.75, -0.9, 0.25), focus, distance=0.5)
close_up("back_close", (0.45, 1.0, 0.35), Vector((0.0, 0.08, 1.76)), distance=0.45)
close_up("under", (0.3, -1.0, -0.45), Vector((0.0, -0.05, 1.74)), distance=0.42)
print("[%s] done" % SCRIPT)
