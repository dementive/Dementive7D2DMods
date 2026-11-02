"""Hard hat: a cap-style construction helmet (an MSA V-Gard type) in sun-faded yellow HDPE, scuffed and scratched,
dirty in every crease and flecked with concrete. A raised ridge runs front to back over the crown, a peak shades
the eyes and a short rain-gutter lip runs round the sides and back; a first-aid sticker on the left, a peeling flag on
the right, a strip of reflective tape on the back. Underneath hangs the black suspension: a headband with a sweatband
at the brow, two crown straps crossing under the top, the keys clipped into the shell and a ratchet knob at the nape
that shows below the rim.

It sits level with the rim just above the brows (the eyes stay clear under the peak), about 2 cm off the head hit box
at the sides and 1 cm at the headband. One part on the Head bone: the hat comes off whole.

    blender -b --factory-startup --python hard_hat.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "HardHat", "hard_hat"
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


# ---------------------------------------------------------------- the hat

CY = HC.y + 0.003  # shell center, front to back
RX, RY = 0.125, 0.136  # outer half-width and half-length at the rim
TOP = 1.872  # outer top of the dome (the ridge stands above it)
EXP = 2.4  # the dome's profile: a little fuller than an ellipse
THICK = 0.0035
COLS, DOME_ROWS = 36, 10


def rim_z(a):
    """The shell's bottom edge, level but a touch higher over the ears and lower at the nape (a: 0 front, pi/2 left)."""
    return 1.757 + 0.008 * math.sin(a) ** 2 - 0.005 * max(0.0, -math.cos(a)) ** 2


def dome(a, phi):
    """A point on the dome's outside: phi 0 at the top, pi/2 at the rim."""
    zr = rim_z(a)
    s = max(0.0, math.sin(phi)) ** (2.0 / EXP)
    c = max(0.0, math.cos(phi)) ** (2.0 / EXP)
    k = 1.0 + 0.03 * smoothstep(0.55, 1.0, phi / (math.pi / 2)) ** 2  # flares out a little toward the rim
    return Vector((RX * s * k * math.sin(a), CY - RY * s * k * math.cos(a), zr + (TOP - zr) * c))


def dome_f(q):
    """The dome as an implicit surface: < 0 inside, > 0 outside."""
    dy = q.y - CY
    zr = rim_z(math.atan2(q.x, -dy))
    hz = min(1.0, max(0.0, (q.z - zr) / (TOP - zr)))
    phi = math.acos(hz ** (EXP / 2.0))
    k = 1.0 + 0.03 * smoothstep(0.55, 1.0, phi / (math.pi / 2)) ** 2
    rh = math.sqrt((q.x / (RX * k)) ** 2 + (dy / (RY * k)) ** 2)
    return rh ** EXP + hz ** EXP - 1.0


def onto_dome(q, n):
    """Slides q along n onto the dome's outer surface."""
    return onto(dome_f, q, n)


def peak(a):
    """How much of the front peak there is at azimuth a (1 at the front, 0 past the temples)."""
    return max(0.0, (math.cos(a) - 0.25) / 0.75) ** 1.2


BRIM_ROWS = 4


def shell_point(i, j):
    a = 2 * math.pi * i / COLS
    if j < DOME_ROWS:
        return dome(a, (math.pi / 2) * j / (DOME_ROWS - 1))
    # The brim: a rounded corner off the rim, then the peak at the front and a narrow rain-gutter lip round the
    # rest, its edge rolled down
    base = dome(a, math.pi / 2)
    n = Vector((math.sin(a) / RX, -math.cos(a) / RY, 0.0)).normalized()
    f = peak(a)
    w = 0.008 + 0.05 * f
    k = j - DOME_ROWS
    out = (0.0035, 0.0035 + 0.5 * (w - 0.0035), w - 0.0015, w)[k]
    down = 0.004 + (out - 0.0035) * (0.36 * f + 0.12 * (1 - f)) + (0.0045 + 0.002 * f if k == 3 else 0.0)
    return base + n * out - Vector((0.0, 0.0, down))


inside = wear("HatInside", (0.5, 0.31, 0.03), rough=0.55, seed=2.0, tone=0.3, scratches=0.4,
              scratch_col=(0.7, 0.58, 0.32), scuffs=0.2, edges=0.3, dirt=0.9, dirt_range=(0.16, 0.05), grime=1.0,
              dust=0.0, specks=0.8, bump=0.25)
black = wear("Suspension", (0.022, 0.021, 0.02), rough=0.45, seed=3.0, tone=0.2, scratches=0.25,
             scratch_col=(0.12, 0.115, 0.11), scuffs=0.3, scuff_col=(0.06, 0.057, 0.054), edges=0.6,
             edge_col=(0.14, 0.135, 0.13), dirt=0.5, dirt_range=(0.2, 0.06), grime=0.6, dust=0.15, specks=0.3,
             bump=0.3)
sweat = wear("Sweatband", (0.22, 0.19, 0.15), rough=0.9, seed=4.0, tone=0.35, scratches=0.0, scuffs=0.0, edges=0.0,
             dirt=1.0, dirt_set="metal_plate_02", dirt_scale=4.0, dirt_range=(0.4, 0.1), grime=0.9, dust=0.0,
             specks=0.6, blood=0.3, bump=0.6, grain=0.5, grain_scale=300.0)


def hat_decals(g, W, P, col, rgh, met, height):
    """A first-aid sticker on the left, a flag sticker on the right, reflective tape on the back, the accessory
    slots over the ears and the maker's oval molded into the front."""
    x, y, z = g.separate(W)
    ax = g.math("ABSOLUTE", x)
    # First-aid sticker (left side, tilted, the back corner peeling)
    u, v = rotate2(g, y, z, 0.0, 1.815, 9.0)
    soft = g.math("MULTIPLY", rect(g, u, v, 0.019, 0.016, 0.004), g.ramp(x, 0.04, 0.07))
    st = frayed(g, soft, P, 50.0, 0.6)
    peel = g.ramp(g.math("ADD", g.math("SUBTRACT", u, v), g.math("MULTIPLY", g.noise(80.0, vector=P), 0.004)),
                  0.024, 0.022)
    glue = g.math("MULTIPLY", st, g.math("SUBTRACT", 1.0, peel))
    st = g.math("MULTIPLY", st, peel)
    cross = g.math("MAXIMUM", rect(g, u, v, 0.0042, 0.012, 0.0006), rect(g, u, v, 0.012, 0.0042, 0.0006))
    sticker = g.mix(cross, (0.66, 0.64, 0.56), (0.03, 0.2, 0.06))
    col = g.mix(st, col, sticker)
    col = g.mix(g.math("MULTIPLY", glue, 0.6), col, (0.16, 0.12, 0.05))
    rgh = g.mixf(st, rgh, 0.5)
    height = g.math("ADD", height, g.math("MULTIPLY", st, 0.4))
    # Flag sticker (right side)
    u, v = rotate2(g, y, z, 0.006, 1.81, -6.0)
    soft = g.math("MULTIPLY", rect(g, u, v, 0.024, 0.0145, 0.004), g.ramp(x, -0.04, -0.07))
    fl = frayed(g, soft, mapping(g, P, loc=(0.4, 0.1, 0.3)), 45.0, 0.7)
    stripes = g.ramp(g.math("FRACT", g.math("MULTIPLY", g.math("ADD", v, 0.0145), 13.0 / 0.029 / 2.0)), 0.47, 0.53)
    flag = g.mix(stripes, (0.3, 0.03, 0.025), (0.64, 0.6, 0.52))
    canton = rect(g, g.math("ADD", u, 0.012), g.math("SUBTRACT", v, 0.0068), 0.012, 0.0078, 0.0004)
    stars = g.ramp(voronoi(g, W, 320.0), 0.24, 0.13)
    flag = g.mix(canton, flag, g.mix(stars, (0.03, 0.045, 0.13), (0.6, 0.58, 0.5)))
    col = g.mix(fl, col, flag)
    rgh = g.mixf(fl, rgh, 0.48)
    height = g.math("ADD", height, g.math("MULTIPLY", fl, 0.4))
    # Reflective tape across the back
    tape = g.math("MULTIPLY", g.math("MULTIPLY", band(g, z, 1.788, 1.803, 0.0007), g.ramp(ax, 0.047, 0.044)),
                  g.ramp(y, 0.09, 0.12))
    tape = frayed(g, tape, mapping(g, P, loc=(0.9, 0.3, 0.1)), 70.0, 0.5)
    prism = g.ramp(voronoi(g, W, 900.0), 0.35, 0.1)
    col = g.mix(tape, col, g.mix(prism, (0.42, 0.43, 0.43), (0.62, 0.63, 0.62)))
    rgh = g.mixf(tape, rgh, 0.32)
    met = g.mixf(tape, met, 0.35)
    height = g.math("ADD", height, g.math("MULTIPLY", tape, 0.5))
    # Accessory slots just above the rim over each ear
    slot = g.math("MULTIPLY", g.math("MULTIPLY", band(g, y, -0.012, 0.01, 0.0008), band(g, z, 1.769, 1.782, 0.0008)),
                  g.ramp(ax, 0.105, 0.115))
    col = g.mix(slot, col, (0.03, 0.022, 0.01))
    rgh = g.mixf(slot, rgh, 0.8)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", slot, 2.0))
    # The maker's oval, molded into the front above the peak
    ex = g.math("DIVIDE", x, 0.026)
    ez = g.math("DIVIDE", g.math("SUBTRACT", z, 1.781), 0.012)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", ex, ex), g.math("MULTIPLY", ez, ez)))
    oval = g.math("MULTIPLY", band(g, r, 0.82, 1.0, 0.04), g.ramp(y, -0.07, -0.1))
    height = g.math("ADD", height, g.math("MULTIPLY", oval, 1.2))
    col = g.mix(g.math("MULTIPLY", oval, 0.25), col, (0.1, 0.07, 0.02))
    return col, rgh, met, height


plastic = wear("HatPlastic", (0.8, 0.5, 0.02), rough=0.36, seed=1.0, tone=0.2, fade=0.35, scratches=0.75,
               scratch_col=(0.88, 0.74, 0.42), dark_scratches=0.5, scuffs=0.45, scuff_col=(0.8, 0.66, 0.34),
               edges=0.6, edge_col=(0.9, 0.78, 0.48), dirt=0.75, dirt_set="rust_coarse_01", dirt_scale=3.2,
               dirt_range=(0.12, 0.035), grime=0.9, dust=0.45, specks=0.7, splatter=0.8,
               splatter_col=(0.52, 0.5, 0.46), blood=0.35, bump=0.35, grain=0.12, decals=hat_decals)


def shell():
    obj = grid("Shell", plastic, COLS, DOME_ROWS + BRIM_ROWS, shell_point, pole=True)
    thicken(obj, THICK, inner=inside)
    # A knock on the upper left front and a scrape-flattened spot at the back
    a, phi = 0.75, 0.62
    p = dome(a, phi)
    push(obj, p, 0.032, (p - Vector((0.0, CY, 1.76))).normalized() * -0.0032)
    a, phi = 2.7, 0.95
    p = dome(a, phi)
    push(obj, p, 0.026, (p - Vector((0.0, CY, 1.76))).normalized() * -0.002)
    return tk.smooth(obj, 50)


def ridge():
    """The raised rib from the peak over the crown to the back."""
    n = 20
    pts, nrm = [], []
    for k in range(n + 1):
        t = -1.0 + 2.0 * k / n
        a = 0.0 if t < 0 else math.pi
        phi = abs(t) * (math.pi / 2) * (0.7 if t < 0 else 0.92)
        p = dome(a, phi)
        pts.append(p)
        nrm.append((p - Vector((0.0, CY, rim_z(a) - 0.03))).normalized())
    # A low crest with soft shoulders, its edges sunk under the shell so it grows out of it
    profile = [(-0.019, -0.0024), (-0.0145, 0.001), (-0.0095, 0.0042), (-0.0038, 0.006), (0.0038, 0.006),
               (0.0095, 0.0042), (0.0145, 0.001), (0.019, -0.0024)]

    def scale(i):
        t = abs(-1.0 + 2.0 * i / n)
        taper = smoothstep(1.0, 0.6, t)
        return 0.7 + 0.3 * taper, lambda h: (h + 0.0024) * taper - 0.0024

    return sweep("Ridge", pts, nrm, profile, plastic, scale, surface=onto_dome)


# Suspension: a headband 1 cm off the head hit box at the temples, dipping to the nape behind
BRX, BRY = 0.114, 0.123


def band_z(a):
    return 1.756 - 0.04 * smoothstep(0.25, 1.0, -math.cos(a))


def band_point(a, inset=0.0):
    return Vector(((BRX - inset) * math.sin(a), HC.y - (BRY - inset) * math.cos(a), band_z(a)))


def headband():
    pts = [band_point(2 * math.pi * k / 32) for k in range(32)]
    return strap("Headband", pts, 0.024, 0.0026, black, (0.0, 0.0, 1.0), closed=True)


def sweatband():
    pts = [band_point(math.radians(-55 + 110 * k / 12), 0.0028) for k in range(13)]
    return strap("Sweatband", pts, 0.026, 0.003, sweat, (0.0, 0.0, 1.0))


def crown_strap(name, a, lift):
    """An arc from the headband's top edge at azimuth a, over the crown, to the opposite side."""
    d = Vector((math.sin(a), -math.cos(a), 0.0))
    p0 = band_point(a) + Vector((0.0, 0.0, 0.011))
    p1 = band_point(a + math.pi) + Vector((0.0, 0.0, 0.011))
    top = 1.861 + lift
    pts = []
    for k in range(12):
        th = math.pi * k / 11
        h = math.cos(th)
        base = p0.lerp(p1, (1 - h) / 2)
        r = (p0 - Vector((0.0, HC.y, p0.z))).length if h >= 0 else (p1 - Vector((0.0, HC.y, p1.z))).length
        rise = (top - (p0.z + p1.z) / 2) * math.sin(th) ** 0.8  # a full arc, to clear the crown
        q = Vector((0.0, HC.y, base.z)) + d * (r * h) + Vector((0.0, 0.0, rise))
        pts.append(q)
    side = Vector((math.cos(a), math.sin(a), 0.0))
    return strap(name, pts, 0.017, 0.0022, black, side)


def keys():
    """The four suspension keys clipped into the shell's slots, the headband hanging from them."""
    out = []
    for k, a in enumerate((math.radians(48), math.radians(-48), math.radians(132), math.radians(-132))):
        z0, z1 = band_z(a) - 0.002, rim_z(a) + 0.018
        o = tk.box("Key%d" % k, (0.012, 0.0075, z1 - z0), (0.0, 0.0, 0.0), black)
        r = Vector((math.sin(a), -math.cos(a), 0.0))
        p = band_point(a)
        shell_in = dome(a, math.pi / 2)
        mid = p.lerp(Vector((shell_in.x, shell_in.y, p.z)), 0.55)
        o.matrix_world = Matrix.Translation(Vector((mid.x, mid.y, (z0 + z1) / 2))) @ \
            Matrix.Rotation(math.atan2(r.x, -r.y), 4, "Z")
        out.append(bake_transform(o))
    return out


def ratchet():
    """The nape adjuster: a housing on the back of the headband and a knurled knob pointing back."""
    back = band_point(math.pi)
    housing = tk.box("RatchetHousing", (0.066, 0.009, 0.027), (0.0, back.y + 0.004, back.z), black, bevel_width=0.003)
    wheel = knob("RatchetKnob", (0.0, back.y + 0.008, back.z), (0.0, 1.0, 0.0), 0.0165, 0.014, black)
    cap = tk.cylinder("RatchetCap", 0.009, back.y + 0.021, back.y + 0.0235, black, segments=12, axis="Y",
                      center=(0.0, back.z))
    return [housing, wheel, cap]


pieces = [shell(), ridge(), headband(), sweatband(), crown_strap("CrownA", math.radians(48), 0.0),
          crown_strap("CrownB", math.radians(-48), 0.0025)] + keys() + ratchet()
export(pieces)
focus = Vector((0.0, HC.y, 1.78))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.9)
close_up("close", (-0.75, -0.9, 0.25), focus, distance=0.5)
close_up("under", (0.55, 0.8, -0.55), Vector((0.0, HC.y + 0.04, 1.74)), distance=0.5)
print("[%s] done" % SCRIPT)
