"""Swinging Log: a 1x1x2 block (two tall). A sawbuck A-frame of rough, weathered 2x4s on each side, scissored and
lashed where the legs cross, standing on 2x4 skids; a rusty steel pipe laid in the two crotches as the crossbar; a heavy
weathered log studded with sharpened stakes and rusty rebar, hung from the pipe on two ropes; and a tripwire with a
scrap of flagging tape across the front at shin height.

The log, its spikes and its ropes are the moving part "Log", pivoting on the pipe's axis. Rest pose: hanging straight
down. Rotating it about +X by a positive angle pulls it back (+Y); a negative angle swings it forward through the front
(-Y).

    blender -b --factory-startup --python swinging_log.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

from mathutils import Matrix, Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(1873)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- helpers: grain-aligned photo wood, rope, pipe

ATTR = "local_uv"  # per-corner (across, along) coordinates, so wood grain and rope twist follow each piece


def _attr(obj):
    me = obj.data
    return me.attributes.get(ATTR) or me.attributes.new(ATTR, "FLOAT_VECTOR", "CORNER")


def grain_box(obj, axis=2, scale=1.0, offset=(0.0, 0.0)):
    """Grain along a box's local axis (0 x, 1 y, 2 z); call before the box is moved or turned."""
    me = obj.data
    a = _attr(obj)
    for p in me.polygons:
        k = max(range(3), key=lambda i: abs(p.normal[i]))
        if k == axis:
            u, v = [i for i in range(3) if i != k]
        else:
            u, v = 3 - k - axis, axis
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a.data[li].vector = (co[u] * scale + offset[0], co[v] * scale + offset[1], 0.0)
    return obj


def grain_cyl(obj, axis=2, center=(0.0, 0.0), radius=0.1, scale=1.0, offset=(0.0, 0.0)):
    """Grain along a cylinder's axis (0 x, 1 y, 2 z, center as tk.cylinder takes it); around maps to arc length."""
    me = obj.data
    a = _attr(obj)
    o = [i for i in range(3) if i != axis]
    for p in me.polygons:
        vals = []
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            vals.append([math.atan2(co[o[1]] - center[1], co[o[0]] - center[0]), co[axis]])
        angs = [v[0] for v in vals]
        if max(angs) - min(angs) > math.pi:
            for v in vals:
                if v[0] < 0:
                    v[0] += 2 * math.pi
        for li, (ang, al) in zip(p.loop_indices, vals):
            a.data[li].vector = (ang * radius * scale + offset[0], al * scale + offset[1], 0.0)
    return obj


def _attr_photo_nodes(nt, set_name, across=1.0):
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = ATTR
    vec = attr.outputs["Vector"]
    if across != 1.0:
        sc = nt.nodes.new("ShaderNodeMapping")
        sc.inputs["Scale"].default_value = (across, 1.0, 1.0)
        nt.links.new(vec, sc.inputs["Vector"])
        vec = sc.outputs[0]
    for n in list(nt.nodes):
        if n.bl_idname == "ShaderNodeTexImage" and n.image and n.image.name.startswith(set_name) \
                and n.projection == "BOX":
            n.projection = "FLAT"
            m = n.inputs["Vector"].links[0].from_node
            nt.links.new(vec, m.inputs["Vector"])


def grain_aligned(mat, set_name="weathered_planks"):
    """Re-maps a photo material's wood photo onto the per-piece grain coordinates."""
    _attr_photo_nodes(mat.node_tree, set_name)
    return mat


def place(obj, start, direction, spin=0.0):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(start) @ rot @ Matrix.Rotation(spin, 4, "Z") @ obj.matrix_world
    return obj


def rope(name, pts, radius, mat, sides=8, closed=False, up=None):
    """A rope (or wire) tube along a polyline, with (around, along) coordinates for the twisted-strand material."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = []
    for i in range(n):
        d = (P[(i + 1) % n] - P[(i - 1) % n]) if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        T.append(d.normalized())
    N = []
    for i in range(n):
        if up is not None:
            ref = Vector(up)
        elif i == 0:
            ref = Vector((0.0, 0.0, 1.0)) if abs(T[0].z) < 0.9 else Vector((1.0, 0.0, 0.0))
        else:
            ref = N[-1]
        N.append((ref - T[i] * ref.dot(T[i])).normalized())
    bm = bmesh.new()
    rings = []
    for i in range(n):
        B = T[i].cross(N[i])
        rings.append([bm.verts.new(P[i] + (N[i] * math.cos(2 * math.pi * j / sides)
                                           + B * math.sin(2 * math.pi * j / sides)) * radius) for j in range(sides)])
    s = [0.0]
    for i in range(1, n + (1 if closed else 0)):
        s.append(s[-1] + (P[i % n] - P[i - 1]).length)
    corners = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
            u0, u1 = j / sides, (j + 1) / sides
            corners.append([(u0, s[i]), (u1, s[i]), (u1, s[i + 1]), (u0, s[i + 1])])
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        corners.append([(0.0, 0.0)] * sides)
        bm.faces.new(rings[-1])
        corners.append([(0.0, s[-1])] * sides)
    obj = tk.mesh_object(name, bm, mat)
    a = _attr(obj)
    for p, cs in zip(obj.data.polygons, corners):
        for li, (u, v) in zip(p.loop_indices, cs):
            a.data[li].vector = (u, v, 0.0)
    return tk.smooth(obj, 50)


def rope_material(name, color=(0.3, 0.235, 0.15), pitch=0.034, grime=0.85, grit=1.0):
    """Three-strand laid rope: strands twisting along the tube, fibers along the strands, grime and dust."""
    mat, g = tk.new_material(name)
    attr = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    u, v, _ = g.separate(attr.outputs["Vector"])
    a = g.math("ADD", g.math("MULTIPLY", u, 3.0), g.math("DIVIDE", v, pitch))
    t = g.math("FRACT", a)
    prof = g.math("SUBTRACT", 1.0, g.math("POWER", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", t, 2.0),
                                                                                 1.0)), 2.5))
    fv = g.node("ShaderNodeCombineXYZ")
    g._in(fv, "X", g.math("MULTIPLY", a, 9.0))
    g._in(fv, "Y", g.math("MULTIPLY", v, 6.0))
    fib = g.noise(1.0, detail=5.0, roughness=0.7, vector=fv.outputs[0])
    col = g.mix(g.ramp(prof, 0.05, 0.7), (0.06, 0.045, 0.03), color)
    col = g.mix(g.math("MULTIPLY", fib, 0.6), col, tuple(c * 0.6 for c in color))
    col = g.mix(g.ramp(g.noise(7.0, detail=4.0), 0.45, 0.75), col, (0.2, 0.17, 0.13))
    dirt = tk._grime(g, grime)
    col = g.mix(dirt, col, (0.05, 0.04, 0.03))
    rough = g.mixf(dirt, 0.88, 0.95)
    col, rough, metal = tk._grit(g, col, rough, 0.0, grit)
    height = g.math("ADD", g.math("MULTIPLY", prof, 0.8), g.math("MULTIPLY", fib, 0.3))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.7, 0.004))


def _uv2(g, u, v, su, sv, ofs=0.0):
    c = g.node("ShaderNodeCombineXYZ")
    g._in(c, "X", g.math("MULTIPLY", u, su))
    g._in(c, "Y", g.math("MULTIPLY", v, sv))
    g._in(c, "Z", ofs)
    return c.outputs[0]


def log_material(name, value=3.0, bark=0.3, across=0.35, grit=0.3):
    """Weathered timber with the bark half peeled: silver-grey checked wood (the planks photo along the grain,
    stretched round the log so its board seams become a few long checks) under patches of dark, deeply fissured bark
    with a dark torn rim."""
    mat, g = tk.new_material(name)
    p = tk.photo(g, "weathered_planks", 1.0)
    _attr_photo_nodes(mat.node_tree, "weathered_planks", across)
    col = tk.grade(g, p["color"], 0.45, value, (0.97, 0.92, 0.84))
    bc = g.node("ShaderNodeBrightContrast")
    g._in(bc, "Color", col)
    g._in(bc, "Contrast", 0.15)
    col = bc.outputs[0]
    rough = p["rough"]
    height = p["height"]
    attr = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    u, v, _ = g.separate(attr.outputs["Vector"])
    blot = g.noise(1.0, detail=6.0, roughness=0.62, vector=_uv2(g, u, v, 4.0, 1.6, 0.37), distortion=0.3)
    lo = 0.62 - 0.24 * bark
    patch = g.ramp(blot, lo, lo + 0.012)
    rim = g.math("SUBTRACT", g.ramp(blot, lo - 0.035, lo - 0.005), patch, clamp=True)
    # long drying checks in the bare wood: contour lines of noise stretched along the log
    def lines(su, sv, ofs, width):
        n = g.noise(1.0, detail=2.0, roughness=0.5, vector=_uv2(g, u, v, su, sv, ofs), distortion=0.2)
        return g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, width, False))
    checks = g.math("MAXIMUM", lines(2.4, 0.45, 0.2, 0.02), g.math("MULTIPLY", lines(5.0, 0.9, 2.6, 0.014), 0.8))
    col = g.mix(checks, col, (0.012, 0.01, 0.008))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", checks, 1.2))
    # bark left on in patches: dark brown, ridged along the grain
    ridge = g.noise(1.0, detail=5.0, roughness=0.65, vector=_uv2(g, u, v, 45.0, 4.0, 1.3), distortion=0.4)
    fiss = g.ramp(ridge, 0.36, 0.64)
    bark_col = g.mix(fiss, (0.008, 0.006, 0.004), (0.05, 0.034, 0.022))
    bark_col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.45, 0.8), g.math("MULTIPLY", fiss, 0.35)),
                     bark_col, (0.07, 0.06, 0.05))
    col = g.mix(g.math("MULTIPLY", rim, 0.85), col, (0.05, 0.035, 0.025))
    col = g.mix(patch, col, bark_col)
    rough = g.mixf(patch, rough, 0.93)
    height = g.mixf(patch, height, g.math("ADD", g.math("MULTIPLY", fiss, 2.4), 0.8))
    lichen = g.math("MULTIPLY", g.ramp(g.noise(11.0, detail=6.0, roughness=0.7), 0.66, 0.72), 0.6)
    col = g.mix(lichen, col, (0.3, 0.31, 0.24))
    dirt = tk._grime(g, 0.7)
    col = g.mix(dirt, col, (0.04, 0.032, 0.024))
    rough = g.mixf(dirt, rough, 0.88)
    col = tk._multiply_color(g, col, g.mix(0.6, (1.0, 1.0, 1.0), p["ao"]))
    col, rough, metal = tk._grit(g, col, rough, 0.0, grit)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.6, 0.01))


def end_grain_material(name, cy, cz, radius):
    """A sawn log end: growth rings around the log's axis (along X through (cy, cz)), drying checks, dark bark rim."""
    mat, g = tk.new_material(name)
    _, y, zz = g.separate(g.coords())
    dy = g.math("SUBTRACT", y, cy)
    dz = g.math("SUBTRACT", zz, cz)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dy, dy), g.math("MULTIPLY", dz, dz)))
    rr = g.math("ADD", r, g.math("MULTIPLY", g.noise(5.0, detail=3.0), 0.02))
    rings = g.ramp(g.math("FRACT", g.math("MULTIPLY", rr, 70.0)), 0.7, 0.95)
    ang = g.math("ARCTAN2", dz, dy)
    cv = g.node("ShaderNodeCombineXYZ")
    g._in(cv, "X", g.math("MULTIPLY", ang, 2.0))
    g._in(cv, "Y", g.math("MULTIPLY", r, 3.0))
    cracks = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=3.0, roughness=0.5, vector=cv.outputs[0]), 0.62, 0.66),
                    g.ramp(r, 0.01, radius * 0.6))
    col = g.mix(g.math("MULTIPLY", g.noise(9.0, detail=4.0), 0.5), (0.36, 0.31, 0.24), (0.27, 0.23, 0.18))
    col = g.mix(g.math("MULTIPLY", rings, 0.7), col, (0.15, 0.12, 0.09))
    col = g.mix(g.ramp(r, radius * 0.86, radius * 0.93), col, (0.06, 0.045, 0.03))
    col = g.mix(cracks, col, (0.03, 0.025, 0.02))
    col = g.mix(g.ramp(g.noise(3.0, detail=6.0), 0.5, 0.75), col, (0.2, 0.2, 0.19))
    dirt = tk._grime(g, 0.6)
    col = g.mix(dirt, col, (0.05, 0.04, 0.03))
    rough = g.mixf(dirt, 0.8, 0.9)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.7)
    height = g.math("SUBTRACT", g.math("MULTIPLY", rings, 0.3), cracks)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.4, 0.003))


def hollow_x(name, r_out, r_in, x0, x1, cy, cz, mat, segs=24):
    """An open pipe along X."""
    bm = bmesh.new()

    def ring(x, r):
        return [bm.verts.new((x, cy + r * math.cos(2 * math.pi * j / segs), cz + r * math.sin(2 * math.pi * j / segs)))
                for j in range(segs)]
    o0, o1, i0, i1 = ring(x0, r_out), ring(x1, r_out), ring(x0, r_in), ring(x1, r_in)
    for j in range(segs):
        j1 = (j + 1) % segs
        bm.faces.new((o0[j], o0[j1], o1[j1], o1[j]))
        bm.faces.new((i0[j], i1[j], i1[j1], i0[j1]))
        bm.faces.new((o0[j], i0[j], i0[j1], o0[j1]))
        bm.faces.new((o1[j], o1[j1], i1[j1], i1[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 40)


def blob(name, radius, center, scale, mat, segs=(10, 6)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs[0], v_segments=segs[1], radius=radius)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    obj = tk.mesh_object(name, bm, mat)
    grain_cyl(obj, 2, (center[0], center[1]), radius)
    return tk.smooth(obj, 60)


tk.reset_scene()
tk.preview_stage()

# ---------------------------------------------------------------- materials

lumber = grain_aligned(tk.photo_material("Lumber", "weathered_planks", scale=1.0, sat=0.42, value=2.3,
                                         tint=(1.0, 0.96, 0.9), exposed=None, grime=0.8, bump=0.7, grit=0.8,
                                         contrast=0.22))
log_wood = log_material("LogWood", bark=0.3)
stick = log_material("StakeWood", value=3.0, bark=0.35, across=1.0)
cut = grain_aligned(tk.photo_material("CutWood", "weathered_planks", scale=1.6, sat=0.85, value=3.4,
                                      tint=(1.0, 0.86, 0.64), exposed=None, grime=0.6, bump=0.5, grit=0.6,
                                      contrast=0.1))
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
pipe_mat = tk.photo_material("Pipe", "metal_plate_02", scale=2.0, value=1.15, chip=1.0, grime=0.8, streaks=1.0,
                             patches=0.9, metal_floor=0.5, rough_scale=0.85, grit=0.9, scratches=0.45, edges=0.6,
                             contrast=0.12)
steel = tk.photo_material("Steel", "metal_plate_02", scale=2.6, value=1.35, exposed=None, grime=0.4,
                          metal_floor=0.6, rough_scale=0.75, grit=0.5, scratches=0.6, edges=0.8)
hemp = rope_material("Rope")
flag = tk.grimy("Flagging", (0.62, 0.14, 0.03), roughness=0.55, grime=0.6, grit=0.7, dirt_range=(0.1, 0.03))

parts = []
add = parts.append
log_parts = []


def add_log(o):
    tk.mark_part(o, "Log")
    log_parts.append(o)
    return o


# ---------------------------------------------------------------- the frame

W2, T2 = 0.0445, 0.019  # half the width and half the thickness of a 2x4
PIPE_R = 0.034
PIVOT = Vector((0.0, 0.0, z(1.85)))  # the pipe's axis: the log's pivot
FOOT_Y, FOOT_Z = 0.4, z(0.038)


def crotch(zc):
    a = math.atan2(FOOT_Y, zc - FOOT_Z)
    return zc + (W2 + PIPE_R) / math.sin(a), a


lo, hi = z(0.9), z(1.8)
for _ in range(60):
    mid = (lo + hi) / 2
    if crotch(mid)[0] > PIVOT.z:
        hi = mid
    else:
        lo = mid
ZC = lo  # where the legs cross
ALPHA = crotch(ZC)[1]
TOP = z(1.955)  # the legs' centerline ends here


def leg_y(sign_front, h):
    """Centerline y of a leg at height h (world z): the front leg climbs from -FOOT_Y to +, the back one the other
    way."""
    return sign_front * (-FOOT_Y + (h - FOOT_Z) * math.tan(ALPHA))


def lumber_board(name, size, axis, center, rot=None, offset=None):
    b = tk.box(name, size, (0.0, 0.0, 0.0), lumber, 0.004)
    grain_box(b, axis, 1.0, offset or (rnd.uniform(0, 5), rnd.uniform(0, 5)))
    m = Matrix.Translation(center)
    if rot is not None:
        m = m @ rot
    b.matrix_world = m
    return b


LEGS = {}
for side in (-1, 1):
    inner_front = side > 0  # the front leg is inside on the right, outside on the left
    for front in (1, -1):
        inner = inner_front if front == 1 else not inner_front
        x = side * (0.398 if inner else 0.436)
        top_h = TOP + rnd.uniform(-0.04, 0.02)
        foot = Vector((x, -front * FOOT_Y, FOOT_Z))
        top = Vector((x, leg_y(front, top_h), top_h))
        center = (foot + top) / 2
        rot = Matrix.Rotation(-front * ALPHA + math.radians(jitter(0.4)), 4, "X")
        add(lumber_board("Leg", (2 * T2, 2 * W2, (top_h - FOOT_Z) / math.cos(ALPHA)), 2, center, rot))
        LEGS[(side, front)] = x

# a scab nailed over a split in the left front leg
SC = z(1.25)
scab_c = Vector((-(0.436 + T2 + 0.0095), leg_y(1, SC), SC))
add(lumber_board("Scab", (0.019, 0.08, 0.34), 2, scab_c,
                 Matrix.Rotation(-ALPHA + math.radians(2.5), 4, "X")))
for k, t in enumerate((-0.13, -0.06, 0.07, 0.14)):
    nail = tk.cylinder("NailHead", 0.0055, 0.0, 0.004, rust, segments=8)
    h = SC + t * math.cos(ALPHA)
    place(nail, Vector((scab_c.x - 0.0095, leg_y(1, h) + (0.018 if k % 2 else -0.016), h)), (-1, 0, 0))
    add(nail)

    # skid under the feet, a 1x4 spreader on the outside (with a spacer block for the inner leg)
    add(lumber_board("Skid", (2 * W2, 0.94, 2 * T2), 1, (side * 0.417 + jitter(0.004), jitter(0.01), z(0.019)),
                     Matrix.Rotation(math.radians(jitter(1.2)), 4, "Z")))
    hs = z(0.62 if side > 0 else 0.7)
    x_out = side * 0.436
    sp_x = side * (0.436 + T2 + 0.0095)
    tilt = Matrix.Rotation(math.radians(jitter(3.0)), 4, "X")
    add(lumber_board("Spreader", (0.019, 0.66, 0.089), 1, (sp_x, jitter(0.02), hs), tilt))
    for front in (1, -1):
        x_leg = LEGS[(side, front)]
        y = leg_y(front, hs)
        if abs(x_leg) < 0.42:
            add(lumber_board("Spacer", (0.038, 0.1, 0.075), 2, (side * 0.436, y, hs),
                             Matrix.Rotation(math.radians(jitter(6)), 4, "X")))
        for dz in (-0.022, 0.024):
            nail = tk.cylinder("NailHead", 0.0055, 0.0, 0.004, rust, segments=8)
            place(nail, Vector((sp_x + side * 0.0095, y + jitter(0.012), hs + dz)), (side, 0, 0))
            add(nail)
    # toe nails at the feet, a carriage bolt where the legs cross
    for front in (1, -1):
        x_leg = LEGS[(side, front)]
        for k in range(2):
            h = FOOT_Z + 0.05 + 0.02 * k
            nail = tk.cylinder("ToeNail", 0.005, 0.0, 0.004, rust, segments=8)
            place(nail, Vector((x_leg + side * (T2 + 0.0005) * (1 if abs(x_leg) > 0.42 else -1),
                                leg_y(front, h) + 0.02 * front * (k - 0.5), h)), (side * (1 if abs(x_leg) > 0.42 else -1), 0, 0))
            add(nail)
    bolt = tk.cylinder("CrossBolt", 0.012, 0.0, 0.008, rust, segments=6, bevel_width=0.002)
    place(bolt, Vector((side * (0.436 + T2), 0.0, ZC - 0.07)), (side, 0, 0))
    add(bolt)
    washer = tk.cylinder("Washer", 0.02, 0.0, 0.003, rust, segments=16)
    place(washer, Vector((side * (0.398 - T2), 0.0, ZC - 0.07)), (-side, 0, 0))
    add(washer)
    nut = tk.cylinder("Nut", 0.012, 0.003, 0.012, rust, segments=6, bevel_width=0.0015)
    place(nut, Vector((side * (0.398 - T2), 0.0, ZC - 0.07)), (-side, 0, 0))
    add(nut)
    # rope lashing round the crossing
    for k, dz in enumerate((-0.03, 0.0, 0.03)):
        hx = 0.038 + 0.008
        hy = W2 / math.cos(ALPHA) + abs(dz) * math.tan(ALPHA) + 0.009
        cx = side * 0.417
        pts = []
        for i in range(28):
            t = 2 * math.pi * i / 28
            c, s = math.cos(t), math.sin(t)
            pts.append((cx + hx * math.copysign(abs(c) ** 0.3, c), hy * math.copysign(abs(s) ** 0.3, s),
                        ZC + dz + 0.006 * math.sin(t + k)))
        add(rope("Lashing", pts, 0.0075, hemp, sides=6, closed=True, up=(0, 0, 1)))

# a 1x4 tie board across the back skids
add(lumber_board("TieBoard", (0.9, 0.089, 0.019), 0, (0.0, 0.24, z(0.038 + 0.0095)),
                 Matrix.Rotation(math.radians(4.0), 4, "Z")))
for x in (-0.42, 0.41):
    for dy in (-0.025, 0.02):
        nail = tk.cylinder("NailHead", 0.0055, 0.0, 0.004, rust, segments=8)
        place(nail, Vector((x, 0.24 + dy + x * 0.07, z(0.057))), (0, 0, 1))
        add(nail)

# the pipe crossbar, lying in the two crotches
add(hollow_x("Pipe", PIPE_R, PIPE_R - 0.005, -0.474, 0.47, PIVOT.y, PIVOT.z, pipe_mat))
add(tk.cylinder("PipeCap", PIPE_R + 0.006, 0.459, 0.478, rust, segments=24, center=(PIVOT.y, PIVOT.z), axis="X",
                bevel_width=0.004))
add(tk.cylinder("PipeCoupling", PIPE_R + 0.006, 0.125, 0.175, rust, segments=24, center=(PIVOT.y, PIVOT.z),
                axis="X", bevel_width=0.003))

# ---------------------------------------------------------------- the log and its spikes

LOG_R, LOG_HALF = 0.13, 0.36
LOG_Z = z(1.05)
ROPE_R = 0.011


def log_scale(x, ang):
    return 1.0 + 0.05 * x + 0.035 * math.sin(2 * ang + 1.3 + 3 * x) + 0.02 * math.sin(3 * ang - 0.7)


def log_bow(x):
    return 0.012 * math.sin(x * 3.0)


log = tk.cylinder("Log", LOG_R, -LOG_HALF, LOG_HALF, log_wood, segments=26, center=(0.0, LOG_Z), axis="X", rings=8)
for v in log.data.vertices:
    x, y, zz = v.co
    dz = zz - LOG_Z
    ang = math.atan2(dz, y)
    s = log_scale(x, ang)
    v.co.y = y * s
    v.co.z = LOG_Z + dz * s + log_bow(x)
    if x > LOG_HALF - 1e-4:  # chainsaw cuts, a little off square (and only ever inward, clear of the legs)
        v.co.x += 0.012 * dz / LOG_R - 0.014
    elif x < -LOG_HALF + 1e-4:
        v.co.x += 0.009 * y / LOG_R + 0.011
grain_cyl(log, 0, (0.0, LOG_Z), LOG_R, 1.0, (0.3, 0.0))
log_end = end_grain_material("LogEnd", 0.0, LOG_Z, LOG_R)
log.data.materials.append(log_end)
for p in log.data.polygons:
    if abs(p.normal.x) > 0.8:
        p.material_index = 1
add_log(tk.dent(log, 0.006, 0.07, seed=3))


def surface(x, phi):
    """A point on the log's skin at angle phi around X (0 front -Y, 90 down, 180 back, 270 up) and its normal."""
    d = Vector((0.0, -math.cos(phi), -math.sin(phi)))
    ang = math.atan2(d.z, d.y)
    r = LOG_R * log_scale(x, ang)
    return Vector((x, d.y * r, LOG_Z + d.z * r + log_bow(x))), d


# Sawn-off branch stubs
for x, phi in ((-0.12, 300), (0.21, 235)):
    p, d = surface(x, math.radians(phi))
    stub = tk.cylinder("Stub", 0.03, -0.02, 0.03, log_wood, segments=10, radius_top=0.024)
    grain_cyl(stub, 2, (0, 0), 0.03)
    stub.data.materials.append(log_end)
    for f in stub.data.polygons:
        if f.normal.z > 0.9:
            f.material_index = 1
    add_log(place(stub, p, d, spin=rnd.uniform(0, 6)))

# Sharpened stakes (x, angle, length out) and rusty rebar
STAKES = [(-0.29, -8, 0.2), (-0.11, 14, 0.22), (0.07, -22, 0.19), (0.27, 6, 0.21), (-0.21, 58, 0.18), (0.15, 72, 0.2),
          (-0.04, 108, 0.17), (0.29, 128, 0.18), (-0.3, 158, 0.17), (0.02, 176, 0.2), (0.2, 200, 0.16),
          (-0.16, 318, 0.15)]
REBAR = [(-0.18, -36, 0.17), (0.18, 32, 0.19), (-0.33, 92, 0.15), (0.25, 100, 0.16), (0.1, 150, 0.15),
         (-0.12, 212, 0.14), (0.33, -30, 0.14)]
for x, phi, length in STAKES:
    p, d = surface(x, math.radians(phi + jitter(4)))
    d = (Matrix.Rotation(math.radians(jitter(9)), 3, "Z") @ Matrix.Rotation(math.radians(jitter(6)), 3, "X") @ d)
    r = rnd.uniform(0.019, 0.025)
    tip = rnd.uniform(0.07, 0.09)
    shaft = tk.cylinder("Stake", r, -0.05, length - tip, stick, segments=7)
    point = tk.cylinder("StakeTip", r, length - tip, length, cut, segments=7, radius_top=0.0018)
    off = (rnd.uniform(0, 5), rnd.uniform(0, 5))
    grain_cyl(shaft, 2, (0, 0), r, 1.0, off)
    grain_cyl(point, 2, (0, 0), r, 1.0, off)
    spin = rnd.uniform(0, 6)
    add_log(place(shaft, p, d, spin))
    add_log(place(point, p, d, spin))
for x, phi, length in REBAR:
    p, d = surface(x, math.radians(phi + jitter(4)))
    d = (Matrix.Rotation(math.radians(jitter(10)), 3, "Z") @ Matrix.Rotation(math.radians(jitter(8)), 3, "X") @ d)
    bar = tk.cylinder("Rebar", 0.009, -0.05, length - 0.035, rust, segments=8)
    for k in range(int((length - 0.05) / 0.016)):
        h = 0.004 + 0.016 * k
        add_log(place(tk.cylinder("RebarRib", 0.0104, h, h + 0.004, rust, segments=8), p, d))
    add_log(place(bar, p, d))
    add_log(place(tk.cylinder("RebarTip", 0.009, length - 0.035, length, steel, segments=8, radius_top=0.0012), p, d))

# ---------------------------------------------------------------- the ropes

ROPES = (-0.235, 0.245)
for xr in ROPES:
    for dx in (-0.012, 0.012):
        # wraps round the pipe
        pts = [(xr + dx, PIVOT.y + (PIPE_R + ROPE_R * 0.8) * math.cos(2 * math.pi * i / 20),
                PIVOT.z + (PIPE_R + ROPE_R * 0.8) * math.sin(2 * math.pi * i / 20)) for i in range(20)]
        add_log(rope("PipeWrap", pts, ROPE_R, hemp, closed=True, up=(1, 0, 0)))
        # wraps round the log, following its skin
        pts = []
        for i in range(28):
            t = 2 * math.pi * i / 28
            r = LOG_R * log_scale(xr + dx, t) + ROPE_R * 0.6
            pts.append((xr + dx, r * math.cos(t), LOG_Z + log_bow(xr + dx) + r * math.sin(t)))
        add_log(rope("LogWrap", pts, ROPE_R, hemp, closed=True, up=(1, 0, 0)))
    top = PIVOT.z - PIPE_R - ROPE_R
    bottom = LOG_Z + log_bow(xr) + LOG_R * log_scale(xr, math.pi / 2) + ROPE_R
    add_log(rope("Rope", [(xr, 0.0, top), (xr, 0.0, (top + bottom) / 2), (xr, 0.0, bottom)], ROPE_R, hemp,
                 up=(1, 0, 0)))
    add_log(rope("Rope2", [(xr + 0.006, 0.004, top), (xr + 0.004, 0.006, (top + bottom) / 2),
                           (xr + 0.006, 0.004, bottom)], ROPE_R * 0.9, hemp, up=(1, 0, 0)))
    add_log(blob("KnotTop", 0.022, (xr, 0.0, top - 0.008), (1.3, 1.1, 0.9), hemp))
    add_log(blob("KnotLog", 0.024, (xr, 0.0, bottom + 0.004), (1.4, 1.2, 0.85), hemp))
    tail = [(xr + 0.01, -0.02, bottom), (xr + 0.02, -0.06, bottom - 0.02), (xr + 0.025, -0.1, bottom - 0.06),
            (xr + 0.03, -0.115, bottom - 0.11)]
    add_log(rope("RopeTail", tail, ROPE_R * 0.85, hemp, up=(1, 0, 0)))

# ---------------------------------------------------------------- tripwire across the front at shin height

TW = z(0.3)
eyes = []
for side in (-1, 1):
    x_leg = LEGS[(side, 1)]
    y_edge = leg_y(1, TW) - W2 / math.cos(ALPHA)
    shank = tk.cylinder("EyeShank", 0.003, 0.0, 0.03, steel, segments=6)
    place(shank, Vector((x_leg, y_edge + 0.012, TW)), (0, -1, 0))
    add(shank)
    eye = tk.torus("Eye", 0.009, 0.0022, (0.0, 0.0, 0.0), steel, 16, 6)
    eye.matrix_world = Matrix.Translation((x_leg, y_edge - 0.026, TW)) @ Matrix.Rotation(math.radians(90), 4, "Y")
    add(eye)
    eyes.append(Vector((x_leg, y_edge - 0.026, TW - 0.009)))
a, b = eyes
wire = [a.lerp(b, t) + Vector((0.0, 0.0, -0.012 * math.sin(math.pi * t))) for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
add(rope("Tripwire", [tuple(p) for p in wire], 0.0022, steel, sides=6))
for p in (a, b):
    add(tk.torus("WireTwist", 0.006, 0.0025, (p.x, p.y, p.z + 0.004), steel, 12, 6))
fx = 0.1
fp = a.lerp(b, (fx - a.x) / (b.x - a.x)) + Vector((0.0, 0.0, -0.012 * math.sin(math.pi * (fx - a.x) / (b.x - a.x))))
for k, (dx, ln, tw) in enumerate(((0.0, 0.085, 12.0), (0.012, 0.065, -18.0))):
    strip = tk.box("Flag", (0.016, 0.0012, ln), (0.0, 0.0, -ln / 2), flag)
    strip.matrix_world = (Matrix.Translation(fp + Vector((dx, 0.0, 0.0))) @ Matrix.Rotation(math.radians(tw), 4, "Z")
                          @ Matrix.Rotation(math.radians(8 + 6 * k), 4, "X"))
    add(strip)
add(tk.torus("FlagKnot", 0.008, 0.004, (fp.x + 0.006, fp.y, fp.z), flag, 12, 6))

# ---------------------------------------------------------------- bake and export

atlas = tk.triangulate(tk.join(parts + log_parts, "SwingingLog"))
tk.smart_uvs(atlas)
paths = tk.bake_atlas(atlas, ASSETS, "SwingingLog_Atlas")
baked = tk.baked_material("SwingingLog_Atlas", paths)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
if ATTR in atlas.data.attributes:
    atlas.data.attributes.remove(atlas.data.attributes[ATTR])
model = atlas
log_part = tk.split_part(model, "Log", PIVOT)

tk.export_fbx([model, log_part], os.path.join(ASSETS, "SwingingLog.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons) + sum(len(p.vertices) - 2 for p in log_part.data.polygons)
print("[swinging_log] triangles:", tris)


def bounds(objs):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


bpy.context.view_layer.update()
print("[swinging_log] bounds:", tuple(round(c, 4) for c in bounds([model, log_part])[0]),
      tuple(round(c, 4) for c in bounds([model, log_part])[1]))
print("[swinging_log] Log pivot:", tuple(round(c, 4) for c in log_part.matrix_world.translation),
      "log bounds:", [tuple(round(c, 3) for c in b) for b in bounds([log_part])])
print("[swinging_log] legs cross at z", round(ZC, 4), "alpha", round(math.degrees(ALPHA), 2))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (2.3, -3.2, 1.9), (0, 0, 0.45), lens=40), os.path.join(PREVIEWS, "swinging_log_front.png"))
tk.render(tk.camera("Back", (-2.5, 2.7, 2.3), (0, 0, 0.45), lens=40), os.path.join(PREVIEWS, "swinging_log_back.png"))
tk.render(tk.camera("Close", (0.75, -1.15, 0.95), (0.0, -0.05, 0.55), lens=45),
          os.path.join(PREVIEWS, "swinging_log_close.png"))
side_cam = tk.camera("Side", (3.6, -0.6, 1.0), (0, -0.25, 0.6), lens=38)
log_part.rotation_euler = (math.radians(-60), 0.0, 0.0)
tk.render(side_cam, os.path.join(PREVIEWS, "swinging_log_active.png"))
log_part.rotation_euler = (math.radians(55), 0.0, 0.0)
tk.render(side_cam, os.path.join(PREVIEWS, "swinging_log_pulled.png"))
log_part.rotation_euler = (0.0, 0.0, 0.0)
tk.icon(tk.camera("Icon", (2.5, -3.3, 2.3), (0, 0, 0.5), lens=58), ICON, hide={"Floor", "ScaleFigure", "ScaleHead"},
        target=(0, 0, 0.5))
print("[swinging_log] done")
