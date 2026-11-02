"""Headphones: a pair of cheap over-ear headphones pushed down round the neck, the way people wear them between songs.
The headband lies across the back of the neck, its padded middle resting on the nape; the steel sliders run out of
its ends into the yokes; the oval cups sit either side of the throat with their pads turned in toward the neck, the
bottoms resting on the tops of the shoulders. A short length of cable hangs from the left cup over the collarbone and
down the chest, ending in its plug.

Gloss black plastic scuffed grey and scratched, a faded logo ring on each cup; the faux-leather pads and band cushion
cracked and peeling to the grey backing; the sliders dull and grimy; dried blood flecked over the left side.

Fitted to Joe's real neck and shoulders, not the hit boxes: the head capsule reaches down to z 1.545 and the chest
capsule's dome covers the base of the neck, so the band and the cups' lower halves sit inside those capsules (see the
face proxy fit in the log). The pads stand 0.5 to 1.5 cm off the neck, clear of the jaw when it opens. One part on the
Neck bone: Neck#Headphones.

    blender -b --factory-startup --python headphones.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT = "Headphones", "headphones"
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
HC = Vector((0.0, 0.035, 1.745))  # center of the head hit box's top half-sphere (radius 0.10, top at z 1.845)
# Joe's face (REMNANTS.md): it sits in front of the head hit box (whose front is at y -0.065)
EYES = (Vector((0.032, -0.075, 1.719)), Vector((-0.032, -0.075, 1.719)))
BRIDGE = Vector((0.0, -0.09, 1.725))
JAW_PIVOT = zk.joe().pos("Jaw")


# ---------------------------------------------------------------- mesh helpers

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def sp(x, e):
    """Signed power."""
    return math.copysign(abs(x) ** e, x)


def orient(bm, inside):
    """Turns every face of an open surface to face away from the point `inside`."""
    bm.normal_update()
    if sum((f.calc_center_median() - inside).dot(f.normal) for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])


def grid(name, mat, cols, rows, fn, cyclic=False, inside=HC):
    """A surface from fn(i, j) -> point over cols x rows vertices, closed around i when cyclic."""
    bm = bmesh.new()
    vs = [[bm.verts.new(fn(i, j)) for i in range(cols)] for j in range(rows)]
    for j in range(rows - 1):
        for i in range(cols if cyclic else cols - 1):
            i1 = (i + 1) % cols
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


def profile_sweep(name, pts, profile, mat, up=(0.0, 0.0, 1.0), closed=False, scale=None, caps=True, mats=None,
                  smooth_angle=50):
    """A closed 2D profile [(across, up), ...] swept along a polyline, `up` (a vector or up(i)) kept square to the
    path; scale(i) -> (across, up) factors taper it, mats(i) -> material index for the faces after ring i."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        u = Vector(up(i) if callable(up) else up)
        U = (u - T[i] * u.dot(T[i])).normalized()
        A = U.cross(T[i])
        sa, su = scale(i) if scale else (1.0, 1.0)
        rings.append([bm.verts.new(P[i] + A * (a * sa) + U * (b * su)) for a, b in profile])
    m = len(profile)
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for j in range(m):
            j1 = (j + 1) % m
            f = bm.faces.new((r0[j], r0[j1], r1[j1], r1[j]))
            if mats:
                f.material_index = mats(i)
    if caps and not closed:
        f0 = bm.faces.new(list(reversed(rings[0])))
        f1 = bm.faces.new(rings[-1])
        if mats:
            f0.material_index = mats(0)
            f1.material_index = mats(n - 2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    return tk.smooth(obj, smooth_angle)


def rounded_profile(w, h, r=0.35, n=2):
    """A rounded rectangle w x h (across, up) as a closed profile; r is the corner radius as a fraction of the
    smaller side, n points per corner."""
    rad = min(w, h) * r
    out = []
    for cx, cy, a0 in ((w / 2 - rad, h / 2 - rad, 0.0), (-w / 2 + rad, h / 2 - rad, 90.0),
                       (-w / 2 + rad, -h / 2 + rad, 180.0), (w / 2 - rad, -h / 2 + rad, 270.0)):
        for k in range(n):
            a = math.radians(a0 + 90.0 * k / max(1, n - 1)) if n > 1 else math.radians(a0 + 45.0)
            out.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return out


def tube(name, pts, radius, mat, sides=6, closed=False, caps=True, radius_fn=None):
    """A round wire or rod along a polyline (closed for rings); radius_fn(i) scales it."""
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
        r = radius * (radius_fn(i) if radius_fn else 1.0)
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * j / sides) + B * math.sin(2 * math.pi * j / sides))
                                   * r) for j in range(sides)])
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


def flat_curve(name, outlines, depth, mat, bevel=0.0):
    """Closed 2D outlines [(x, y), ...] in the XY plane filled (inner outlines become holes) and extruded `depth`
    along Z (centered on z = 0), the edges chamfered by `bevel`. Returns a mesh object."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = max(0.0, depth / 2 - bevel)
    cu.bevel_depth = bevel
    cu.bevel_resolution = 0
    for pts in outlines:
        s = cu.splines.new("POLY")
        s.points.add(len(pts) - 1)
        for p, co in zip(s.points, pts):
            p.co = (co[0], co[1], 0.0, 1.0)
        s.use_cyclic_u = True
    cobj = tk.link(bpy.data.objects.new(name + "Curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(cobj)
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(obj.data)
    bm.free()
    return tk.smooth(obj, 40)


def catmull(pts, n):
    """The polyline smoothed: n points per span on a Catmull-Rom curve through the points."""
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def deform(obj, fn):
    """Moves every vertex through fn(Vector) -> Vector."""
    for v in obj.data.vertices:
        v.co = fn(v.co.copy())
    obj.data.update()
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


def bake_transform(obj):
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def transform(obj, m):
    """Applies the matrix m to the mesh in place (world = mesh coordinates)."""
    obj.data.transform(m)
    obj.data.update()
    return obj


def about(pivot, rot):
    """A 4x4 matrix turning by `rot` (a 3x3 or 4x4 rotation) about `pivot`."""
    p = Vector(pivot)
    return Matrix.Translation(p) @ rot.to_4x4() @ Matrix.Translation(-p)


def blob(name, center, radii, mat, exps=(2.0, 2.0), rot_x=0.0, segs=28, rings=18):
    """A superellipsoid: exps = (around, up) exponents, 2 for an ellipsoid, higher for boxier."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    nh, nv = exps
    for v in bm.verts:
        d = v.co.normalized()
        f = ((abs(d.x) / radii[0]) ** nh + (abs(d.y) / radii[1]) ** nh) ** (nv / nh) + (abs(d.z) / radii[2]) ** nv
        v.co = d * f ** (-1.0 / nv)
    if rot_x:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot_x), 3, "X"))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return tk.mesh_object(name, bm, mat)


# ---------------------------------------------------------------- the face proxy (fitting and previews only)

def face_proxy():
    """A mannequin head, neck and shoulders where Joe's face really is (in front of his head hit box: eyes, nose,
    lips and chin at the REMNANTS.md face points), to fit face gear against and to show it on in the previews. The
    hit box capsules overstate the neck (the head capsule reaches down to z 1.545 and the chest capsule's dome
    covers the base of the neck), so neck pieces are fitted to this too. Not exported."""
    mat, g = tk.new_material("ProxySkin")
    tk.finish(mat, g, (0.46, 0.38, 0.34), 0.0, 0.65)
    eye_mat, g = tk.new_material("ProxyEye")
    tk.finish(eye_mat, g, (0.06, 0.05, 0.045), 0.0, 0.15)
    parts = [
        blob("Cranium", (0.0, 0.02, 1.737), (0.076, 0.1, 0.107), mat, (2.8, 2.6)),
        blob("Brow", (0.0, -0.062, 1.745), (0.052, 0.024, 0.011), mat, (2.4, 2.0)),
        blob("Midface", (0.0, -0.03, 1.674), (0.062, 0.064, 0.06), mat, (2.4, 2.0)),
        blob("Jaw", (0.0, -0.02, 1.628), (0.053, 0.066, 0.045), mat, (2.4, 2.0)),
        blob("Chin", (0.0, -0.077, 1.611), (0.022, 0.017, 0.017), mat),
        blob("Lips", (0.0, -0.083, 1.646), (0.025, 0.017, 0.013), mat),
        blob("Neck", (0.0, 0.035, 1.56), (0.054, 0.058, 0.11), mat, (2.0, 3.0), rot_x=8.0),
        blob("Torso", (0.0, 0.04, 1.35), (0.165, 0.135, 0.19), mat, (2.3, 2.6)),  # chest ~2 cm inside the hit box
    ]
    for s in (1.0, -1.0):
        parts.append(blob("Cheek", (s * 0.047, -0.056, 1.699), (0.02, 0.022, 0.015), mat))
        parts.append(blob("Arch", (s * 0.06, -0.025, 1.694), (0.012, 0.035, 0.01), mat))
        parts.append(blob("Ear", (s * 0.076, 0.03, 1.70), (0.011, 0.02, 0.03), mat, rot_x=-10.0))
    nose = [(0.0, -0.087, 1.735), (0.0, -0.092, 1.722), (0.0, -0.112, 1.69), (0.0, -0.12, 1.683),
            (0.0, -0.116, 1.672), (0.0, -0.098, 1.664)]
    for s in (1.0, -1.0):
        nose += [(s * 0.016, -0.098, 1.671), (s * 0.018, -0.088, 1.676), (s * 0.009, -0.088, 1.716),
                 (s * 0.013, -0.08, 1.70), (s * 0.007, -0.112, 1.683), (s * 0.006, -0.08, 1.73)]
    bm = bmesh.new()
    for p in nose:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    parts.append(tk.mesh_object("Nose", bm, mat))
    obj = tk.join(parts, "FaceProxy")
    mod = obj.modifiers.new("Remesh", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = 0.0025
    tk.apply_modifiers(obj)
    mod = obj.modifiers.new("Smooth", "SMOOTH")
    mod.factor = 0.8
    mod.iterations = 6
    tk.apply_modifiers(obj)
    for s in (1.0, -1.0):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.0165)
        bmesh.ops.translate(bm, vec=(s * 0.032, -0.089, 1.723), verts=bm.verts)
        cut(obj, tk.mesh_object("Socket", bm, mat), 0)
    obj.data.materials.append(eye_mat)
    eyes = []
    for e in EYES:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.0125)
        bmesh.ops.translate(bm, vec=e + Vector((0.0, 0.0125, 0.0)), verts=bm.verts)
        eye = tk.mesh_object("Eye", bm, eye_mat)
        eyes.append(eye)
    obj = tk.join([obj] + eyes, "FaceProxy")
    tk.smooth(obj, 60)
    obj["zbody"] = True
    return obj


PROXY = face_proxy()


def body_part(bone):
    """The stand-in's capsule on `bone`."""
    for i, c in enumerate(zk.joe().colliders):
        if c["bone"] == bone:
            return BODY[i]
    return None


HEAD_CAPSULE, CHEST_CAPSULE = body_part("Head"), body_part("Spine2")


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


def dist3(g, W, c):
    """Distance from the shading point to the point c."""
    d = g.node("ShaderNodeVectorMath", operation="DISTANCE")
    g.links.new(W, d.inputs[0])
    d.inputs[1].default_value = tuple(c)
    return tk._sock(d.outputs, "Value")


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


def scratch_mask(g, P, width=0.015, scale=1.0):
    """Straight scratches in five directions (bands of a wave texture, each broken into short runs)."""
    sc = None
    for i, (rot, s) in enumerate((((0.3, 0.9, 0.2), 38.0), ((1.1, 0.2, 1.4), 55.0), ((0.5, 1.3, 2.7), 30.0),
                                  ((2.3, 0.4, 0.9), 70.0), ((1.7, 2.2, 0.3), 45.0))):
        m = mapping(g, P, rot=rot, loc=(0.13 * i, 0.31 * i, 0.07 * i))
        w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        g._in(w, "Scale", s * scale)
        g._in(w, "Distortion", 0.8)
        g._in(w, "Detail", 1.0)
        g._in(w, "Detail Scale", 0.5)
        g.links.new(warp(g, m, 2.5 + i, 0.03), w.inputs["Vector"])  # irregular spacing, gentle bends
        line = g.ramp(tk._sock(w.outputs, "Fac"), 1.0 - width, 1.0 - width * 0.15)
        seg = g.ramp(g.noise((16.0 + 7.0 * i) * scale, detail=2.0, vector=m), 0.57, 0.64)
        line = g.math("MULTIPLY", line, seg)
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    return sc


def wear(name, paint, rough=0.4, metal=0.0, decals=None, seed=0.0, tone=0.2, fade=0.0, scratches=0.5,
         scratch_col=(0.6, 0.58, 0.52), scratch_metal=0.0, dark_scratches=0.3, scuffs=0.4, scuff_col=None, edges=0.4,
         edge_col=None, chips=0.0, chip_col=(0.5, 0.5, 0.5), chip_rough=0.6, chip_metal=0.0, dirt=0.5,
         dirt_set="rust_coarse_01", dirt_scale=3.0, dirt_range=(0.14, 0.04), grime=0.6, dust=0.4, specks=0.5,
         splatter=0.0, splatter_col=(0.5, 0.49, 0.46), blood=0.0, grease=0.0, scorch=0.0, bump=0.3, grain=0.15,
         grain_scale=90.0, line_width=0.03, scratch_scale=1.0, edge_width=0.004, after=None,
         dirt_col=((0.04, 0.032, 0.024), (0.12, 0.095, 0.065))):
    """Worn gear: base paint or plastic with uneven tone and sun fade, decals, chips through to the layer beneath,
    rubbed scuffs, scratches (pale, some packed with dirt), worn edges, photo-patterned dirt and crease grime, dust on
    top, dark specks, and optional paint/concrete splatter, blood, grease and scorch. All amounts 0-1. `after`
    (like decals) gets the last word, over the dirt."""
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
        sc = scratch_mask(g, P, line_width, scratch_scale)
        dens = g.ramp(nz(3.0, 3.0), 0.42, 0.66)
        sc = g.math("MULTIPLY", g.math("MULTIPLY", sc, dens), scratches, clamp=True)
        dark = g.math("MULTIPLY", g.ramp(nz(7.0, 3.0), 0.48, 0.56), dark_scratches)
        scol = g.mix(dark, scratch_col, (0.05, 0.04, 0.03))
        col = g.mix(sc, col, scol)
        rgh = g.mixf(sc, rgh, 0.6)
        met = g.mixf(sc, met, scratch_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.6))
    if edges:
        wm = g.math("MULTIPLY", g.ramp(g.edges(edge_width), 0.06, 0.3), g.ramp(nz(30.0, 4.0), 0.36, 0.55))
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
        sp_ = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.62)), specks)
        col = g.mix(sp_, col, (0.025, 0.02, 0.015))
        rgh = g.mixf(sp_, rgh, 0.9)
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
    if after:
        col, rgh, met, height = after(g, W, P, col, rgh, met, height)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, bump, 0.0015))


# ---------------------------------------------------------------- export, fit report and previews

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


def part_bvh(parts):
    verts, polys = [], []
    for part in parts:
        base = len(verts)
        verts += [part.matrix_world @ v.co for v in part.data.vertices]
        polys += [[base + i for i in f.vertices] for f in part.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def proxy_bvh():
    dg = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(PROXY, dg)


def signed(bvh, p):
    loc, n, _i, d = bvh.find_nearest(p)
    if loc is None:
        return 1e9
    return d if (p - loc).dot(n) >= 0 else -d


def report(parts):
    """Triangles, bounds, and how the model sits: against the head and chest hit boxes, and against the face proxy
    (negative = inside)."""
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
    for bone in ("Head", "Spine2"):
        a, b, r = capsule(bone)
        gaps = [seg_distance(p, a, b) - r for p in pts]
        k = min(range(len(gaps)), key=gaps.__getitem__)
        print("[%s] %s hit box: closest %.1f cm at (%.3f, %.3f, %.3f), %d vertices inside"
              % (NAME, bone, 100 * gaps[k], pts[k].x, pts[k].y, pts[k].z, sum(1 for d in gaps if d < 0.0)))
    bvh = proxy_bvh()
    gaps = [signed(bvh, p) for p in pts]
    k = min(range(len(gaps)), key=gaps.__getitem__)
    print("[%s] face proxy: closest %.1f cm at (%.3f, %.3f, %.3f), %d vertices inside, %d within 3 mm"
          % (NAME, 100 * gaps[k], pts[k].x, pts[k].y, pts[k].z, sum(1 for d in gaps if d < 0.0),
             sum(1 for d in gaps if d < 0.003)))
    return tris, lo, hi


def eye_report(parts):
    """What each eye looks out at: the distance to the model straight ahead (a lens should be 1-2.5 cm off), and
    how many vertices sit within 2 cm of its line of sight (masks should have none)."""
    bvh = part_bvh(parts)
    pts = [part.matrix_world @ v.co for part in parts for v in part.data.vertices]
    for side, e in zip(("left", "right"), EYES):
        hit = bvh.ray_cast(e, Vector((0.0, -1.0, 0.0)), 0.5)
        near = sum(1 for p in pts if p.y < e.y and math.hypot(p.x - e.x, p.z - e.z) < 0.02)
        print("[%s] %s eye: model %s ahead, %d vertices within 2 cm of its line of sight"
              % (NAME, side, "%.1f cm" % (100 * hit[3]) if hit[0] else "nothing", near))


def jaw_report(parts, degrees=18.0):
    """Opens the proxy's jaw `degrees` about the Jaw bone (the zombie's attack) and counts lower-face points that
    end up through the model (on the far side of it from inside the mouth)."""
    bvh = part_bvh(parts)
    rot = about(JAW_PIVOT, Matrix.Rotation(math.radians(degrees), 3, "X"))
    worst, hits, total = 0.0, 0, 0
    for v in PROXY.data.vertices:
        p = v.co
        if not (1.575 < p.z < 1.652 and p.y < -0.03):
            continue
        q = rot @ p
        total += 1
        o = Vector((q.x, 0.0, q.z))
        d = q - o
        hit = bvh.ray_cast(o, d.normalized(), d.length)
        if hit[0] is not None:
            hits += 1
            worst = max(worst, d.length - hit[3])
    print("[%s] jaw opened %.0f deg: %d of %d chin and jaw points through the model (deepest %.1f cm)"
          % (NAME, degrees, hits, total, 100 * worst))


def export(pieces, bone, piece, size=512):
    for p in pieces:
        zk.on(p, bone, piece)
    # The stand-in stays out of the bake: the model's AO and crease grime are its own (it falls off as a prop)
    hidden = BODY + [PROXY]
    for o in hidden:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=size)
    for o in hidden:
        o.hide_render = False
    report(parts)
    return parts


def ghost_material():
    mat = bpy.data.materials.new("Ghost")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (0.3, 0.45, 0.7, 1.0)
    mix.inputs[0].default_value = 0.22
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(pr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def show_capsules(mode):
    """'hide' the head and chest capsules (the proxy stands in), 'ghost' them, or 'solid' (as built)."""
    for o in (HEAD_CAPSULE, CHEST_CAPSULE):
        if o is None:
            continue
        if "_solid" not in o:
            o["_solid"] = o.data.materials[0].name
        o.hide_render = mode == "hide"
        o.data.materials[0] = GHOST if mode == "ghost" else bpy.data.materials[o["_solid"]]


GHOST = ghost_material()


def close_up(view, direction, target, distance=0.5, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


# ---------------------------------------------------------------- shape

CA, CB = 0.047, 0.04  # cup outline half-axes: long (front to back along the neck) and short (up and down)
TILT_DEG = 12.0  # the pads face in toward the neck, tipped this much downward


def cup_frame(side):
    """The cup's frame: origin at the pad face's center, x the short axis (pointing down and out), y the long axis
    (to the back, where the yoke is), z out of the cup away from the neck."""
    t = math.radians(TILT_DEG)
    out = Vector((side * math.cos(t), 0.0, math.sin(t)))
    long_ = Vector((0.0, 1.0, 0.0))
    short = Vector((side * math.sin(t), 0.0, -math.cos(t)))
    origin = Vector((side * 0.066, -0.002, 1.566))
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0], m[r][1], m[r][2], m[r][3] = short[r], long_[r], out[r], origin[r]
    return m


def oval(k, n, scale=1.0):
    a = 2 * math.pi * k / n
    # a rounded oval, a touch fuller than an ellipse
    return (CB * scale * sp(math.cos(a), 0.85), CA * scale * sp(math.sin(a), 0.85))


def placed(obj, m, flip):
    transform(obj, m)
    if flip:
        for p in obj.data.polygons:
            p.flip()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


# ---------------------------------------------------------------- materials

def cup_logo(g, W, P, col, rgh, met, height):
    """A faded logo on the outside of each cup: a muted red ring round a short silver word, half rubbed away."""
    out = []
    for side in (1.0, -1.0):
        m = cup_frame(side)
        c = m @ Vector((0.0, 0.0, 0.0455))
        out.append(c)
    d = g.math("MINIMUM", dist3(g, W, out[0]), dist3(g, W, out[1]))
    ring = band(g, d, 0.0135, 0.0165, 0.0006)
    _x, y, z = g.separate(W)
    word = g.math("MULTIPLY", g.ramp(d, 0.0085, 0.0075),
                  g.math("MULTIPLY", band(g, g.math("SUBTRACT", y, -0.002), -0.0012, 0.0012, 0.0003),
                         g.ramp(g.math("FRACT", g.math("MULTIPLY", z, 650.0)), 0.25, 0.4)))
    rub = g.ramp(g.noise(90.0, detail=4.0, vector=P), 0.36, 0.52)
    col = g.mix(g.math("MULTIPLY", ring, rub), col, (0.13, 0.03, 0.026))
    col = g.mix(g.math("MULTIPLY", word, rub), col, (0.34, 0.34, 0.33))
    rgh = g.mixf(g.math("MULTIPLY", ring, rub), rgh, 0.35)
    return col, rgh, met, height


def peeling(g, W, P, col, rgh, met, height):
    """Faux leather crazed with fine cracks and peeled off in patches to the grey fabric backing."""
    line, gone = cracks(g, P, 260.0, 0.05, 0.12)
    patch = g.ramp(g.noise(7.0, detail=6.0, roughness=0.7, vector=P, distortion=0.6), 0.7, 0.73)
    worn = g.ramp(g.noise(3.0, detail=3.0, vector=P), 0.5, 0.6)  # peeling only where the pads rub
    bare = g.math("MULTIPLY", g.math("MAXIMUM", g.math("MULTIPLY", gone, 0.85), patch), worn)
    col = g.mix(g.math("MULTIPLY", line, 0.7), col, (0.09, 0.085, 0.08))
    col = g.mix(bare, col, g.mix(g.noise(120.0, vector=P), (0.11, 0.1, 0.09), (0.17, 0.155, 0.135)))
    rgh = g.mixf(bare, rgh, 0.92)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MAXIMUM", bare, line), 0.8))
    return col, rgh, met, height


plastic = wear("CupPlastic", (0.016, 0.016, 0.017), rough=0.28, seed=51.0, tone=0.25, decals=cup_logo,
               scratches=0.4, scratch_scale=1.7, line_width=0.02, scratch_col=(0.16, 0.16, 0.16), dark_scratches=0.2, scuffs=0.55,
               scuff_col=(0.06, 0.06, 0.062), edges=0.45, edge_col=(0.13, 0.13, 0.13), edge_width=0.0015,
               dirt=0.5, dirt_range=(0.2, 0.06), grime=0.9, dust=0.4, specks=0.45, grease=0.4, blood=0.35,
               bump=0.3, grain=0.08, dirt_col=((0.012, 0.01, 0.008), (0.05, 0.04, 0.03)))
leather = wear("Pads", (0.026, 0.024, 0.023), rough=0.42, seed=52.0, tone=0.3, decals=peeling, scratches=0.15,
               scratch_col=(0.09, 0.085, 0.08), scuffs=0.4, scuff_col=(0.055, 0.05, 0.048), edges=0.3,
               edge_col=(0.08, 0.075, 0.07), dirt=0.6, dirt_range=(0.25, 0.08), grime=1.0, dust=0.25, specks=0.5,
               grease=0.6, blood=0.25, bump=0.45, grain=0.35, grain_scale=260.0,
               dirt_col=((0.012, 0.01, 0.008), (0.045, 0.036, 0.026)))
steel = wear("Slider", (0.42, 0.42, 0.43), rough=0.38, metal=1.0, seed=53.0, tone=0.25, scratches=0.6,
             scratch_col=(0.6, 0.6, 0.6), scratch_metal=1.0, dark_scratches=0.4, scuffs=0.3,
             scuff_col=(0.3, 0.3, 0.3), edges=0.0, dirt=0.7, dirt_range=(0.3, 0.1), grime=1.0, dust=0.2, specks=0.6,
             grease=0.6, bump=0.2, grain=0.05)
rubber = wear("Cable", (0.02, 0.02, 0.021), rough=0.55, seed=54.0, tone=0.25, scratches=0.2,
              scratch_col=(0.09, 0.09, 0.09), scuffs=0.4, scuff_col=(0.06, 0.06, 0.06), edges=0.0, dirt=0.6,
              dirt_range=(0.25, 0.08), grime=0.8, dust=0.3, specks=0.5, grease=0.4, blood=0.3, bump=0.3, grain=0.1,
              dirt_col=((0.012, 0.01, 0.008), (0.05, 0.04, 0.03)))
pin = wear("Plug", (0.55, 0.53, 0.5), rough=0.3, metal=1.0, seed=55.0, tone=0.2, scratches=0.4,
           scratch_col=(0.7, 0.7, 0.7), scratch_metal=1.0, scuffs=0.2, scuff_col=(0.4, 0.4, 0.4), edges=0.0,
           dirt=0.6, dirt_range=(0.3, 0.1), grime=0.8, dust=0.1, specks=0.5, grease=0.5, bump=0.15, grain=0.03)
cloth = wear("Grille", (0.03, 0.03, 0.032), rough=0.85, seed=56.0, tone=0.2, scratches=0.0, scuffs=0.2,
             scuff_col=(0.06, 0.06, 0.06), edges=0.0, dirt=0.6, dirt_range=(0.3, 0.1), grime=1.0, dust=0.0,
             specks=0.4, bump=0.4, grain=0.5, grain_scale=400.0)


# ---------------------------------------------------------------- the cups

def cup_shell(side):
    """The cup's shell, lathed round the oval: from under the pad out to a domed back."""
    n = 16
    rings = [(0.015, 0.92), (0.019, 1.0), (0.031, 1.0), (0.039, 0.92), (0.0435, 0.72), (0.0455, 0.38)]
    bm = bmesh.new()
    vs = []
    for d, s in rings:
        vs.append([bm.verts.new((oval(k, n, s)[0], oval(k, n, s)[1], d)) for k in range(n)])
    c = bm.verts.new((0.0, 0.0, 0.046))
    for j in range(len(rings) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            bm.faces.new((vs[j][k], vs[j][k1], vs[j + 1][k1], vs[j + 1][k]))
    for k in range(n):
        bm.faces.new((vs[-1][k], vs[-1][(k + 1) % n], c))
    obj = tk.mesh_object("Cup", bm, plastic)
    return tk.smooth(placed(obj, cup_frame(side), side < 0), 50)


def cup_pad(side):
    """The ear cushion: a fat oval ring of faux leather, the speaker cloth inside it."""
    n = 16
    prof = [(0.6, 0.0175), (0.63, 0.006), (0.7, 0.0005), (0.86, 0.0, ), (0.97, 0.004), (0.98, 0.012), (0.93, 0.0185)]
    bm = bmesh.new()
    vs = [[bm.verts.new((oval(k, n, s)[0], oval(k, n, s)[1], d)) for k in range(n)] for s, d in prof]
    for j in range(len(prof) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            bm.faces.new((vs[j][k], vs[j][k1], vs[j + 1][k1], vs[j + 1][k]))
    pad = tk.mesh_object("Pad", bm, leather)
    bm = bmesh.new()
    grille = [bm.verts.new((oval(k, n, 0.61)[0], oval(k, n, 0.61)[1], 0.0165)) for k in range(n)]
    bm.faces.new(grille)
    cl = tk.mesh_object("Grille", bm, cloth)
    return [tk.smooth(placed(pad, cup_frame(side), side < 0), 60), placed(cl, cup_frame(side), side < 0)]


def yoke(side):
    """The block on the back of the cup the sliders run into."""
    m = cup_frame(side)
    pts = [m @ Vector((0.0, CA - 0.004, 0.03)), m @ Vector((0.0, CA + 0.006, 0.03)),
           m @ Vector((0.0, CA + 0.0105, 0.03))]
    up = (m.to_3x3() @ Vector((0.0, 0.0, 1.0)))
    return profile_sweep("Yoke", pts, rounded_profile(0.019, 0.011, 0.35, 2), plastic, up=up,
                         scale=lambda i: (1.0, 1.0) if i < 2 else (0.85, 0.85))


# ---------------------------------------------------------------- the band, sliders and cable

BAND_C = Vector((0.0, 0.035, 0.0))
BAX, BAY = 0.104, 0.077


def band_point(psi):
    """The band's middle line at angle psi (degrees; 90 at the back of the neck, 0 to the zombie's left)."""
    a = math.radians(psi)
    return Vector((BAX * math.cos(a), BAND_C.y + BAY * math.sin(a), 1.553 + 0.016 * math.cos(a) ** 2))


def band_out(psi):
    p = band_point(psi)
    return Vector((p.x / BAX ** 2, (p.y - BAND_C.y) / BAY ** 2, 0.0)).normalized()


def headband():
    psis = [30.0 + 120.0 * k / 14 for k in range(15)]
    pts = [band_point(a) for a in psis]
    strip = profile_sweep("Band", pts, rounded_profile(0.024, 0.0042, 0.3, 1), plastic,
                          up=lambda i: band_out(psis[i]))
    cps = [55.0 + 70.0 * k / 7 for k in range(8)]
    cpts = [band_point(a) - band_out(a) * 0.0062 for a in cps]

    def cscale(i):
        t = abs(i / 7 - 0.5) * 2
        return (1.0 - 0.15 * t * t, 1.0 - 0.35 * t ** 3)

    cushion = profile_sweep("Cushion", cpts, [(0.0105, -0.002), (0.0085, 0.0025), (0.0, 0.0034), (-0.0085, 0.0025),
                                              (-0.0105, -0.002), (0.0, -0.0026)], leather,
                            up=lambda i: -band_out(cps[i]), scale=cscale)
    return [strip, cushion]


def sliders(side):
    """Two steel bars from the band's end into the yoke."""
    psi = 30.0 if side > 0 else 150.0
    end = band_point(psi)
    m = cup_frame(side)
    into = m @ Vector((0.0, CA + 0.004, 0.03))
    t = (end - into).normalized()
    out = []
    for dz in (-0.006, 0.006):
        off = Vector((0.0, 0.0, dz))
        out.append(tube("Slider", [into + off, end + off + t * 0.004], 0.0013, steel, sides=5))
    return out


def cable():
    """The cable out of the bottom front of the left cup, over the collarbone and down the chest, ending in its
    plug."""
    m = cup_frame(1.0)
    start = m @ Vector((0.033, -0.026, 0.024))
    pts = [m @ Vector((0.025, -0.022, 0.024)), start,
           Vector((0.099, -0.037, 1.521)), Vector((0.1, -0.053, 1.499)), Vector((0.0995, -0.065, 1.472)),
           Vector((0.098, -0.072, 1.445)), Vector((0.0965, -0.076, 1.418))]
    wire = tube("Cable", pts, 0.0019, rubber, sides=6, radius_fn=lambda i: 1.6 if i < 2 else 1.0)
    end = pts[-1]
    d = (pts[-1] - pts[-2]).normalized()
    housing = tube("PlugHousing", [end - d * 0.006, end + d * 0.012, end + d * 0.017], 0.0034, rubber, sides=8,
                   radius_fn=lambda i: 1.0 if i < 2 else 0.8)
    jack = tube("Jack", [end + d * 0.017, end + d * 0.029, end + d * 0.0315], 0.0017, pin, sides=6,
                radius_fn=lambda i: 1.0 if i < 2 else 0.6)
    return [wire, housing, jack]


pieces = [cup_shell(1.0), cup_shell(-1.0)] + cup_pad(1.0) + cup_pad(-1.0) + [yoke(1.0), yoke(-1.0)]
pieces += headband() + sliders(1.0) + sliders(-1.0) + cable()
parts = export(pieces, "Neck", "Headphones")
jaw_report(parts)

show_capsules("hide")
focus = Vector((0.0, 0.02, 1.56))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.65)
close_up("close", (-0.7, -1.0, 0.25), Vector((0.0, -0.01, 1.56)), distance=0.42)
close_up("cup", (1.0, -0.35, 0.15), Vector((0.08, 0.0, 1.565)), distance=0.26)
close_up("nape", (0.35, 1.0, 0.35), Vector((0.0, 0.06, 1.57)), distance=0.4)
show_capsules("ghost")
close_up("hitbox", (0.75, -1.0, 0.3), Vector((0.0, 0.02, 1.56)), distance=0.6)
show_capsules("solid")
print("[%s] done" % SCRIPT)
