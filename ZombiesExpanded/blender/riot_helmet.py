"""Riot helmet: a black police riot helmet, satin paint scuffed and scratched, POLICE in worn reflective letters
across the back. A big face shield hangs from two pivot hubs at the temples, wrapping from the brow to below the
chin; it can't be see-through in the game's opaque shader, so it is dark tinted, glossy polycarbonate that catches
the light, scratched, smudged and spotted with blood, a black rubber seal along its top edge where it meets the brow.
A quilted neck guard of thick black ballistic cloth hangs from under the back rim and flares out over the nape.

The liner sits about 2 cm off the head hit box at the sides and 1.4 cm over the top; the shield stands 5-7 cm in
front of the face. One part on the Head bone: the helmet comes off whole.

    blender -b --factory-startup --python riot_helmet.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "RiotHelmet", "riot_helmet"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
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


def grid(name, mat, cols, rows, fn, cyclic=True, pole=False, inside=HC):
    """A surface from fn(i, j) -> point over cols x rows vertices, closed around i when cyclic; with pole, row 0 is a
    single point (a dome's top)."""
    bm = bmesh.new()
    vs = []
    for j in range(rows):
        if pole and j == 0:
            p = bm.verts.new(fn(0, 0))
            vs.append([p] * cols)
        else:
            vs.append([bm.verts.new(fn(i, j)) for i in range(cols)])
    for j in range(rows - 1):
        for i in range(cols if cyclic else cols - 1):
            i1 = (i + 1) % cols
            if pole and j == 0:
                bm.faces.new((vs[0][i], vs[1][i1], vs[1][i]))
            else:
                bm.faces.new((vs[j][i], vs[j][i1], vs[j + 1][i1], vs[j + 1][i]))
    orient(bm, inside)
    return tk.mesh_object(name, bm, mat)


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


def strap(name, pts, width, thick, mat, side=(0.0, 0.0, 1.0), closed=False):
    """A flat band swept along a polyline: `width` along `side` (kept square to the path), `thick` across it."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        s = Vector(side(i) if callable(side) else side)
        W = (s - T[i] * s.dot(T[i])).normalized()
        N = T[i].cross(W)
        rings.append([bm.verts.new(P[i] + W * (sw * width / 2) + N * (st * thick / 2))
                      for sw, st in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 40)


def sweep(name, pts, normals, profile, mat, scale=None, surface=None):
    """An open profile [(across, up), ...] swept along a path, `up` along the given normals, `across` square to the
    path; scale(i) -> (across, up) factors taper it, and surface(q, n) drops each across-offset point back onto a
    curved surface first, so the profile hugs it."""
    P = [Vector(p) for p in pts]
    T = _frames(P, False)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(P):
        N = Vector(normals[i])
        N = (N - T[i] * N.dot(T[i])).normalized()
        B = T[i].cross(N)
        sa, su = scale(i) if scale else (1.0, 1.0)
        ring = []
        for w, h in profile:
            q = p + B * (w * sa)
            if surface:
                q = surface(q, N)
            ring.append(bm.verts.new(q + N * (su(h) if callable(su) else h * su)))
        rings.append(ring)
    for i in range(len(P) - 1):
        for j in range(len(profile) - 1):
            bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
    bm.normal_update()
    mid = rings[len(rings) // 2][len(profile) // 2]
    if mid.normal.dot(Vector(normals[len(rings) // 2])) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 50)


def knob(name, center, axis, radius, length, mat, teeth=12, depth=0.0014):
    """A knurled knob (a ratchet wheel) along `axis` from `center`."""
    bm = bmesh.new()
    n = teeth * 2
    r0, r1 = [], []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = radius if i % 2 == 0 else radius - depth
        r0.append(bm.verts.new((r * math.cos(t), r * math.sin(t), 0.0)))
        r1.append(bm.verts.new((r * 0.94 * math.cos(t), r * 0.94 * math.sin(t), length)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(r0)))
    bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(center)) @ rot
    return tk.smooth(obj, 30)


def tube(name, pts, radius, mat, sides=6, closed=False, caps=True):
    """A round wire or rod along a polyline (closed for rings)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings = []
    ref = Vector((0.0, 0.0, 1.0)) if abs(T[0].z) < 0.9 else Vector((1.0, 0.0, 0.0))
    for i in range(n):
        N = (ref - T[i] * ref.dot(T[i])).normalized()
        ref = N
        B = T[i].cross(N)
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * j / sides) + B * math.sin(2 * math.pi * j / sides))
                                   * radius) for j in range(sides)])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


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


def onto(f, q, n, reach=0.03):
    """Slides q along n onto the implicit surface f = 0 (f < 0 inside)."""
    lo, hi = -reach, reach
    for _ in range(32):
        mid = (lo + hi) / 2
        if f(q + n * mid) > 0:
            hi = mid
        else:
            lo = mid
    return q + n * ((lo + hi) / 2)


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


def cracks(g, P, scale=80.0, width=0.03, flakes=0.12):
    """Crazed paint or a cracked decal: thin irregular crack lines (0-1) and the odd flake gone (0-1)."""
    Q = warp(g, P, 40.0, 0.5 / scale)
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", scale)
    g.links.new(Q, vor.inputs["Vector"])
    line = g.ramp(tk._sock(vor.outputs, "Distance"), width, 0.0)
    line = g.math("MULTIPLY", line, g.ramp(g.noise(scale * 0.25, detail=3.0, vector=P), 0.35, 0.5))
    cells = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(cells, "Scale", scale)
    g.links.new(Q, cells.inputs["Vector"])
    gone = g.ramp(g.separate(tk._sock(cells.outputs, "Color"))[0], 1.0 - flakes, 1.0 - flakes + 0.03)
    gone = g.math("MULTIPLY", gone, g.ramp(g.noise(scale * 0.08, vector=P), 0.42, 0.58))
    return line, gone


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
         grain_scale=90.0, line_width=0.03, dirt_col=((0.04, 0.032, 0.024), (0.12, 0.095, 0.065))):
    """Worn gear: base paint or plastic with uneven tone and sun fade, decals, chips through to the layer beneath,
    rubbed scuffs, scratches (pale, some packed with dirt), worn edges, photo-patterned dirt and crease grime, dust on
    top, dark specks, and optional paint/concrete splatter, blood, grease and scorch. All amounts 0-1."""
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
    if fade:
        fm = g.math("MULTIPLY", g.ramp(up, -0.1, 0.9), g.ramp(nz(3.0, 4.0), 0.3, 0.7))
        col = g.mix(g.math("MULTIPLY", fm, fade), col, tk.grade(g, col, 0.55, 1.35))
    if decals:
        col, rgh, met, height = decals(g, W, P, col, rgh, met, height)
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


# ---------------------------------------------------------------- export and previews

def export(pieces):
    for p in pieces:
        zk.on(p, "Head")
    # The stand-in body stays out of the bake: the model's AO and crease grime are its own (it falls off as a prop)
    for o in BODY:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS)
    for o in BODY:
        o.hide_render = False
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    tris = 0
    for part in parts:
        for v in part.data.vertices:
            w = part.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        tris += sum(len(f.vertices) - 2 for f in part.data.polygons)
    print("[%s] parts %s, %d triangles, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)"
          % (NAME, [p.name for p in parts], tris, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))
    # Fit: how close the model comes to the head and chest hit boxes (negative = inside)
    for bone in ("Head", "Spine2"):
        a, b, r = capsule(bone)
        pts = [part.matrix_world @ v.co for part in parts for v in part.data.vertices]
        gaps = [seg_distance(p, a, b) - r for p in pts]
        k = min(range(len(gaps)), key=gaps.__getitem__)
        print("[%s] %s hit box: closest %.1f cm at (%.3f, %.3f, %.3f), %d vertices within 5 mm"
              % (NAME, bone, 100 * gaps[k], pts[k].x, pts[k].y, pts[k].z, sum(1 for d in gaps if d < 0.005)))
    return parts


def capsule(bone):
    """A bone's capsule hit box as (end, end, radius), in Blender coordinates."""
    sk = zk.joe()
    c = sk.collider(bone)
    ax = Vector((0.0, 0.0, 0.0))
    ax[c["axis"]] = 1.0
    half = max(0.0, c["height"] / 2 - c["radius"])
    ctr = Vector(c["center"])
    return sk.point(bone, ctr - ax * half), sk.point(bone, ctr + ax * half), c["radius"]


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def close_up(view, direction, target, distance=0.55, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


# ---------------------------------------------------------------- the helmet

SC = Vector((0.0, 0.035, 1.72))  # the shell's center
SRX, SRY, SRU, SRD = 0.136, 0.158, 0.155, 0.14
NH, NU, ND = 2.2, 2.3, 3.6
THICK = 0.013
COLS, ROWS = 30, 11


def sp(x, e):
    return math.copysign(abs(x) ** e, x)


def shell_at(a, e):
    nv = NU if e > 0 else ND
    ce, se = sp(math.cos(e), 2 / nv), sp(math.sin(e), 2 / nv)
    hx, hy = sp(math.sin(a), 2 / NH), sp(math.cos(a), 2 / NH)
    return Vector((SRX * hx * ce, SC.y - SRY * hy * ce, SC.z + (SRU if e > 0 else SRD) * se))


def shell_n(a, e):
    p = shell_at(a, e)
    n = (shell_at(a + 0.01, e) - p).cross(shell_at(a, e + 0.01) - p).normalized()
    return n if n.dot(p - SC) > 0 else -n


def shell_f(q):
    X, Y = abs(q.x) / SRX, abs(q.y - SC.y) / SRY
    up = q.z > SC.z
    Z = abs(q.z - SC.z) / (SRU if up else SRD)
    nv = NU if up else ND
    return (X ** NH + Y ** NH) ** (nv / NH) + Z ** nv - 1.0


def e_rim(a):
    """Down over the ears to the jaw line, a little higher at the nape."""
    return math.radians(-37) + math.radians(6) * smoothstep(0.3, 1.0, -math.cos(a))


def shell_point(i, j):
    a = 2 * math.pi * i / COLS
    e = math.radians(90) - (math.radians(90) - e_rim(a)) * j / (ROWS - 1)
    return shell_at(a, e)


def place_on(obj, a, e, lift=0.0, spin=0.0):
    p, n = shell_at(a, e), shell_n(a, e)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(n).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(p + n * lift) @ rot @ Matrix.Rotation(spin, 4, "Z") @ obj.matrix_world
    return bake_transform(obj)


Z_TOP, Z_BOT = 1.797, 1.575  # the shield's top and bottom edges at the front


def shield_point(i, j, cols=20, rows=8):
    t = -1.0 + 2.0 * i / (cols - 1)
    v = j / (rows - 1)
    a = (math.radians(87) - math.radians(27) * v) * t
    ry = 0.152 + 0.022 * v + 0.008 * math.sin(math.pi * v)  # stands further off going down, bellied
    rx = 0.147
    z = Z_TOP + (Z_BOT - Z_TOP) * v + 0.03 * (1 - math.cos(a)) * v  # the lower edge swept up at the sides
    return Vector((rx * sp(math.sin(a), 2 / NH), SC.y - ry * sp(math.cos(a), 2 / NH), z))


def helmet_decals(g, W, P, col, rgh, met, height):
    """A dent-scraped patch, chalky scuffs from a wall, and a strip of reflective tape round the back."""
    x, y, z = g.separate(W)
    tape = g.math("MULTIPLY", band(g, z, 1.705, 1.716, 0.0008), g.ramp(y, 0.06, 0.09))
    tape = frayed(g, tape, mapping(g, P, loc=(0.3, 0.6, 0.2)), 70.0, 0.4)
    col = g.mix(tape, col, (0.45, 0.46, 0.46))
    rgh = g.mixf(tape, rgh, 0.35)
    met = g.mixf(tape, met, 0.3)
    height = g.math("ADD", height, g.math("MULTIPLY", tape, 0.4))
    chalk = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=6.0, distortion=1.2, vector=P), 0.62, 0.7),
                   lines(g, W, (3.0, 30.0, 30.0), (0.2, 0.0, 0.3), (0.1, 0.5, 0.2), 0.15))
    col = g.mix(g.math("MULTIPLY", chalk, 0.6), col, (0.32, 0.3, 0.28))
    rgh = g.mixf(chalk, rgh, 0.85)
    return col, rgh, met, height


def shield_decals(g, W, P, col, rgh, met, height):
    """A hazy smear where it was wiped with a sleeve, and blood run down from a splash on the left."""
    x, y, z = g.separate(W)
    smear = g.math("MULTIPLY", g.ramp(g.noise(2.5, detail=5.0, distortion=0.8, vector=P), 0.55, 0.68),
                   lines(g, W, (25.0, 25.0, 6.0), (0.0, 0.3, 1.2), (0.2, 0.1, 0.3), 0.25))
    col = g.mix(g.math("MULTIPLY", smear, 0.4), col, (0.05, 0.052, 0.056))
    rgh = g.mixf(smear, rgh, 0.2)
    runs = g.math("MULTIPLY", lines(g, W, (90.0, 90.0, 2.5), (0.0, 0.0, 0.0), (0.4, 0.2, 0.0), 0.07),
                  g.math("MULTIPLY", band(g, x, 0.01, 0.07, 0.01), g.ramp(z, 1.77, 1.71)))
    runs = g.math("MULTIPLY", runs, g.ramp(g.noise(12.0, vector=P), 0.5, 0.58))
    splash = g.math("MULTIPLY", g.ramp(voronoi(g, P, 70.0), 0.12, 0.05),
                    g.math("MULTIPLY", band(g, x, 0.0, 0.08, 0.01), band(g, z, 1.73, 1.79, 0.01)))
    runs = g.math("MAXIMUM", runs, splash)
    col = g.mix(runs, col, (0.09, 0.006, 0.004))
    rgh = g.mixf(runs, rgh, 0.3)
    height = g.math("ADD", height, g.math("MULTIPLY", runs, 0.4))
    return col, rgh, met, height


def quilting(g, W, P, col, rgh, met, height):
    """The neck guard's stitched channels: seams fanning down round the nape, padding puffed between them."""
    x, y, z = g.separate(W)
    ang = g.math("ARCTAN2", x, g.math("SUBTRACT", y, SC.y))
    s = g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", ang, 13.0)))
    seam = g.ramp(s, 0.12, 0.0)
    puff = g.math("SQRT", s)
    hem = band(g, z, 1.585, 1.592, 0.0015)
    seam = g.math("MAXIMUM", seam, hem)
    col = g.mix(g.math("MULTIPLY", seam, 0.8), col, (0.008, 0.007, 0.006))
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, puff), 0.5), col, tk._darker(g, col, 0.6))
    height = g.math("ADD", height, g.math("SUBTRACT", g.math("MULTIPLY", puff, 1.6), g.math("MULTIPLY", seam, 1.0)))
    return col, rgh, met, height


shell_mat = wear("RiotShell", (0.016, 0.016, 0.017), rough=0.42, seed=31.0, tone=0.3, scratches=0.55,
                 scratch_col=(0.16, 0.16, 0.16), dark_scratches=0.0, scuffs=0.5, scuff_col=(0.06, 0.06, 0.062),
                 edges=0.6, edge_col=(0.2, 0.2, 0.2), chips=0.2, chip_col=(0.24, 0.24, 0.23), dirt=0.55,
                 dirt_set="metal_plate_02", dirt_scale=3.0, dirt_range=(0.2, 0.06), grime=0.8, dust=0.35,
                 specks=0.4, blood=0.35, bump=0.3, decals=helmet_decals,
                 dirt_col=((0.014, 0.012, 0.01), (0.05, 0.042, 0.032)))
liner = wear("Liner", (0.032, 0.032, 0.034), rough=0.85, seed=32.0, tone=0.3, scratches=0.0, scuffs=0.3,
             scuff_col=(0.07, 0.07, 0.075), edges=0.0, dirt=0.8, dirt_set="metal_plate_02", dirt_range=(0.35, 0.1),
             grime=1.0, dust=0.0, specks=0.5, blood=0.3, bump=0.5, grain=0.6, grain_scale=220.0,
             dirt_col=((0.015, 0.012, 0.01), (0.05, 0.04, 0.03)))
rubber = wear("Rubber", (0.018, 0.018, 0.019), rough=0.7, seed=33.0, tone=0.2, scratches=0.25,
              scratch_col=(0.09, 0.09, 0.09), scuffs=0.4, scuff_col=(0.05, 0.05, 0.05), edges=0.4,
              edge_col=(0.11, 0.11, 0.11), dirt=0.6, dirt_range=(0.2, 0.06), grime=0.8, dust=0.3, specks=0.4,
              bump=0.4, dirt_col=((0.02, 0.016, 0.012), (0.06, 0.05, 0.035)))
shield_mat = wear("Shield", (0.01, 0.012, 0.016), rough=0.03, seed=34.0, tone=0.25, scratches=0.4,
                  scratch_col=(0.2, 0.21, 0.22), dark_scratches=0.0, scuffs=0.2, scuff_col=(0.035, 0.038, 0.042),
                  edges=0.5, edge_col=(0.14, 0.15, 0.16), dirt=0.2, dirt_set="metal_plate_02", dirt_scale=4.0,
                  dirt_range=(0.14, 0.05), grime=0.4, dust=0.1, specks=0.3, blood=0.3, grease=0.35, bump=0.12,
                  grain=0.02, decals=shield_decals, dirt_col=((0.02, 0.017, 0.013), (0.07, 0.06, 0.045)))
cloth = wear("NeckGuard", (0.03, 0.028, 0.026), rough=0.9, seed=35.0, tone=0.3, scratches=0.0, scuffs=0.45,
             scuff_col=(0.06, 0.06, 0.065), edges=0.5, edge_col=(0.08, 0.08, 0.085), dirt=0.7,
             dirt_set="metal_plate_02", dirt_scale=4.0, dirt_range=(0.35, 0.1), grime=0.9, dust=0.35, specks=0.5,
             blood=0.4, bump=0.6, grain=0.5, grain_scale=320.0, decals=quilting,
             dirt_col=((0.02, 0.017, 0.013), (0.07, 0.06, 0.045)))
letters = wear("Lettering", (0.58, 0.58, 0.56), rough=0.4, metal=0.2, seed=36.0, tone=0.3, scratches=0.5,
               scratch_col=(0.3, 0.3, 0.29), dark_scratches=0.0, scuffs=0.7, scuff_col=(0.25, 0.25, 0.24), edges=0.0,
               chips=0.0, chip_col=(0.03, 0.03, 0.03), dirt=0.7, dirt_range=(0.16, 0.05), grime=0.6, dust=0.3, specks=0.0, bump=0.2)


def shell():
    obj = grid("Shell", shell_mat, COLS, ROWS, shell_point, pole=True, inside=SC)
    thicken(obj, THICK, inner=liner, rim=rubber)
    # The face opening, from the brow down
    top = [(0.06 * t, 1.776 - 0.004 * t * t) for t in (-1.0 + 2.0 * k / 8 for k in range(9))]
    corner = [(0.06 + 0.03 * math.sin(math.radians(d)), 1.772 - 0.03 * (1 - math.cos(math.radians(d))))
              for d in (30, 60, 90)]
    pts = [(-px, pz) for px, pz in reversed(corner)] + top + corner + [(0.09, 1.45), (-0.09, 1.45)]
    bm = bmesh.new()
    front = [bm.verts.new((px, -0.3, pz)) for px, pz in pts]
    back = [bm.verts.new((px, -0.005, pz)) for px, pz in pts]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for k in range(len(pts)):
        k1 = (k + 1) % len(pts)
        bm.faces.new((front[k], back[k], back[k1], front[k1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cut(obj, tk.mesh_object("FaceCut", bm, shell_mat), 2)
    for a, e, r, d in ((0.9, 0.7, 0.03, 0.003), (-2.4, 0.3, 0.028, 0.0025)):
        push(obj, shell_at(a, e), r, shell_n(a, e) * -d)
    return tk.smooth(obj, 40)


def shield():
    cols, rows = 20, 8
    obj = grid("Shield", shield_mat, cols, rows, shield_point, cyclic=False, inside=SC)
    thicken(obj, 0.004, rim=rubber)
    out = [tk.smooth(obj, 40)]
    # The rubber seal along the top edge, meeting the brow
    seal = [shield_point(i, 0) + Vector((0.0, 0.0, 0.002)) for i in range(2, cols - 2)]
    out.append(tube("Seal", seal, 0.0045, rubber, sides=5))
    # Pivot hubs at the temples, a bracket from each to the shield's edge
    for s in (1.0, -1.0):
        a, e = math.radians(86) * s, math.radians(7)
        hub = knob("PivotHub", shell_at(a, e) - shell_n(a, e) * 0.001, shell_n(a, e), 0.021, 0.012, rubber,
                   teeth=10, depth=0.0015)
        out.append(bake_transform(hub))
        p0 = shell_at(a, e) + shell_n(a, e) * 0.006
        p1 = shield_point(0 if s < 0 else cols - 1, 2) + Vector((0.0, 0.0, 0.0))
        out.append(strap("Bracket", [p0, p0.lerp(p1, 0.5) + Vector((0.0, 0.0, 0.004)), p1], 0.022, 0.004, rubber,
                         (0.0, 0.0, 1.0)))
    return out


def neck_guard():
    """Quilted ballistic cloth hanging from inside the back rim, flaring out over the nape."""
    cols, rows = 15, 4

    def gp(i, j):
        t = -1.0 + 2.0 * i / (cols - 1)
        a = math.pi + math.radians(68) * t
        e0 = e_rim(a)
        top = shell_at(a, e0 + math.radians(6)) - shell_n(a, e0 + math.radians(6)) * 0.012
        v = j / (rows - 1)
        drop = 0.085 * (1 - 0.35 * t * t) + 0.008 * math.cos(3 * math.pi * t)  # shorter at the ends, three lobes
        out = 0.028 * v ** 1.4
        d = Vector((math.sin(a), -math.cos(a), 0.0))
        return top + d * out - Vector((0.0, 0.0, drop * v))

    obj = grid("NeckGuard", cloth, cols, rows, gp, cyclic=False, inside=SC)
    thicken(obj, 0.006)
    return tk.smooth(obj, 45)


def police(shell_obj):
    """POLICE across the back in reflective letters, shrink-wrapped onto the shell."""
    p = onto(shell_f, Vector((0.0, 0.17, 1.772)), Vector((0.0, 1.0, 0.0)), reach=0.05)
    txt = tk.text_mesh("Police", "POLICE", 0.044, letters, (0.0, p.y + 0.004, 1.772), rotation=(90.0, 0.0, 180.0),
                       extrude=0.0)
    bake_transform(txt)
    # Bend the flat word round the shell before wrapping it on
    for v in txt.data.vertices:
        v.co.y -= (v.co.x ** 2) / (2 * 0.14)
    mod = txt.modifiers.new("Wrap", "SHRINKWRAP")
    mod.target = shell_obj
    mod.wrap_method = "NEAREST_SURFACEPOINT"
    mod.offset = 0.0016  # the tall flat glyphs (the I) would dip into the curve between their corners
    tk.apply_modifiers(txt)
    return tk.smooth(txt, 60)


shell_obj = shell()
pieces = [shell_obj] + shield() + [neck_guard(), police(shell_obj)]
export(pieces)
focus = Vector((0.0, 0.0, 1.72))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.95)
close_up("close", (-0.75, -1.0, 0.1), focus, distance=0.55)
close_up("back_close", (0.5, 1.0, 0.25), Vector((0.0, 0.08, 1.72)), distance=0.55)
print("[%s] done" % SCRIPT)
