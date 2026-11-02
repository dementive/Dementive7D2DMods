"""Ram: a powered 1x1x1 block. A log-splitter's hydraulic cylinder in faded yellow paint, laid on a welded steel skid:
a steel saddle with a U-bolt at the front, two scrap 4x4 blocks and a ratchet strap in the middle, clevis ears at the
back. An electric motor and gear pump with the splitter's control valve and lever on one side, an olive jerry can as
the oil tank on the other, hydraulic hoses between them, a junction box with the power lamp, and a battered, dented,
shot-up STOP sign bolted to the end of the piston rod as the striking plate, facing the front (-Y).

The piston rod and the sign are the moving part "RamHead", its origin at the rod's rear end (inside the barrel). Rest
pose: retracted. It strikes by sliding along -Y, up to 0.8 m. "StrikePoint" (on RamHead) is the sign's front center.

    blender -b --factory-startup --python ram.py -- <unity asset folder> <preview folder> <icon file>
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
rnd = random.Random(1984)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- helpers

ATTR = "local_uv"  # per-corner (across, along) coordinates, so wood grain follows each piece


def grain_box(obj, axis=2, scale=1.0, offset=(0.0, 0.0)):
    """Grain along a box's local axis (0 x, 1 y, 2 z); call before the box is moved or turned."""
    me = obj.data
    a = me.attributes.get(ATTR) or me.attributes.new(ATTR, "FLOAT_VECTOR", "CORNER")
    for p in me.polygons:
        k = max(range(3), key=lambda i: abs(p.normal[i]))
        u, v = ([i for i in range(3) if i != k]) if k == axis else (3 - k - axis, axis)
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a.data[li].vector = (co[u] * scale + offset[0], co[v] * scale + offset[1], 0.0)
    return obj


def grain_aligned(mat, set_name="weathered_planks"):
    """Re-maps a photo material's wood photo onto the per-piece grain coordinates."""
    nt = mat.node_tree
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = ATTR
    for n in list(nt.nodes):
        if n.bl_idname == "ShaderNodeTexImage" and n.image and n.image.name.startswith(set_name) \
                and n.projection == "BOX":
            n.projection = "FLAT"
            m = n.inputs["Vector"].links[0].from_node
            nt.links.new(attr.outputs["Vector"], m.inputs["Vector"])
    return mat


def _frames(P, closed):
    n = len(P)
    return [((P[(i + 1) % n] - P[(i - 1) % n]) if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])).normalized()
            for i in range(n)]


def strap(name, pts, width, thick, mat, side=(0.0, 0.0, 1.0), closed=False):
    """A flat bar or webbing swept along a polyline: `width` along `side` (kept square to the path), `thick` across."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = _frames(P, closed)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        s = Vector(side)
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


def hose(name, pts, radius, mat, sides=7, smooth_steps=2):
    """A round hose or cable along a polyline, rounded off with Chaikin smoothing."""
    P = [Vector(p) for p in pts]
    for _ in range(smooth_steps):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [a.lerp(b, 0.25), a.lerp(b, 0.75)]
        Q.append(P[-1])
        P = Q
    n = len(P)
    T = _frames(P, False)
    bm = bmesh.new()
    rings = []
    ref = Vector((0.0, 0.0, 1.0)) if abs(T[0].z) < 0.9 else Vector((1.0, 0.0, 0.0))
    for i in range(n):
        N = (ref - T[i] * ref.dot(T[i])).normalized()
        ref = N
        B = T[i].cross(N)
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * j / sides) + B * math.sin(2 * math.pi * j / sides))
                                   * radius) for j in range(sides)])
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60), P


def place(obj, start, direction, spin=0.0):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(start) @ rot @ Matrix.Rotation(spin, 4, "Z") @ obj.matrix_world
    return obj


def shift_part(model, label, offset):
    """Moves the faces marked as a moving part (in the joined model, before split_part), e.g. to bake it in its
    active pose."""
    idx = tk.PART_LABELS.index(label)
    me = model.data
    attr = me.attributes["trap_part"]
    verts = set()
    for p in me.polygons:
        if attr.data[p.index].value == idx:
            verts.update(p.vertices)
    for vi in verts:
        me.vertices[vi].co += Vector(offset)
    me.update()


def fbx_model_transform(path, name):
    """Reads a model's Lcl Translation and Lcl Rotation back out of an exported FBX file."""
    import addon_utils
    addon_utils.enable("io_scene_fbx")
    from io_scene_fbx import parse_fbx
    root, _ = parse_fbx.parse(path)
    for el in root.elems:
        if el.id != b"Objects":
            continue
        for o in el.elems:
            if o.id == b"Model" and o.props[1].split(bytes(1))[0] == name.encode():
                t, r = Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
                for sub in o.elems:
                    if sub.id == b"Properties70":
                        for prop in sub.elems:
                            if prop.props[0] == b"Lcl Translation":
                                t = Vector(prop.props[4:7])
                            elif prop.props[0] == b"Lcl Rotation":
                                r = Vector(prop.props[4:7])
                return t, r
    raise KeyError(name)


def export_with_part_points(objs, path, points):
    """tk.export_fbx, then checks each (point, part) pair in the file. Blender's FBX exporter, with the kit's
    bake_space_transform, writes an empty parented to a moving part (a grandchild of the model) with a wrong local
    transform: it ends up where its *Blender* world position would be in FBX space, turned 90 degrees. If the file
    shows that, the point is pre-compensated (placed at G @ its true transform, G being the export's axis
    conversion), exported again and checked again; its Blender transform is restored afterwards. If the exporter
    gets it right, nothing is changed."""
    from bpy_extras.io_utils import axis_conversion
    G = axis_conversion(to_forward="-Z", to_up="Y").to_4x4()
    true = {pt.name: pt.matrix_world.copy() for pt, _ in points}

    def check():
        bad = []
        for pt, part in points:
            want = G @ (part.matrix_world.inverted() @ true[pt.name]) @ G.inverted()
            t, r = fbx_model_transform(path, pt.name)
            if (t - want.translation).length > 1e-4 or r.length > 1e-3:
                bad.append(pt)
            print("[ram] FBX", pt.name, "local", tuple(round(c, 4) for c in t), "rot", tuple(round(c, 3) for c in r),
                  "want", tuple(round(c, 4) for c in want.translation))
        return bad

    tk.export_fbx(objs, path)
    bad = check()
    if bad:
        for pt in bad:
            pt.matrix_world = G @ true[pt.name]
        bpy.context.view_layer.update()
        tk.export_fbx(objs, path)
        for pt in bad:
            pt.matrix_world = true[pt.name]
        bpy.context.view_layer.update()
        if check():
            raise RuntimeError("FBX points on moving parts are still misplaced")
        print("[ram] compensated the exporter for", [pt.name for pt in bad])


def bake_in(obj):
    """Applies an object's transform to its mesh, so its vertices are in model space."""
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


tk.reset_scene()
tk.preview_stage()

# ---------------------------------------------------------------- materials

cyl_paint = tk.photo_material("CylPaint", "green_metal_rust", scale=1.8, sat=0.0, value=3.4, tint=(1.0, 0.7, 0.13),
                              chip=1.0, grime=0.9, streaks=1.2, patches=0.55, metal_floor=0.35, rough_scale=0.85,
                              grit=0.9, scratches=0.5, edges=0.8, contrast=0.08)
frame = tk.photo_material("Frame", "rusty_painted_metal", scale=2.2, sat=0.08, value=0.55, chip=1.0, grime=0.8,
                          streaks=0.8, patches=0.8, metal_floor=0.4, rough_scale=0.85, grit=0.8, scratches=0.4,
                          edges=0.7, contrast=0.05)
steel = tk.photo_material("Steel", "metal_plate_02", scale=2.4, value=1.0, exposed="rust_coarse_01", chip=1.0,
                          patches=0.5, grime=0.7, metal_floor=0.5, rough_scale=0.8, grit=0.7, scratches=0.5, edges=0.8)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.1, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
chrome = tk.grimy("Chrome", (0.72, 0.72, 0.74), roughness=0.16, metallic=1.0, grime=0.35, grit=0.25,
                  dirt_range=(0.3, 0.1))
motor_paint = tk.photo_material("MotorPaint", "rusty_painted_metal", scale=2.0, sat=0.0, value=1.6,
                                tint=(0.62, 0.72, 0.86), chip=1.0, grime=0.8, streaks=0.6, patches=0.45,
                                metal_floor=0.4, rough_scale=0.85, grit=0.9, scratches=0.5, edges=0.8, contrast=0.05)
olive = tk.photo_material("Olive", "green_metal_rust", scale=1.7, sat=0.45, value=1.25, tint=(1.0, 0.92, 0.55),
                          chip=1.0, grime=0.8, streaks=0.8, patches=0.5, metal_floor=0.35, rough_scale=0.85, grit=0.9,
                          scratches=0.5, edges=0.8, contrast=0.05)
sign_red = tk.photo_material("SignRed", "rusty_painted_metal", scale=1.5, sat=1.1, value=1.15, tint=(1.0, 0.42, 0.5),
                             exposed="metal_plate_02", chip=1.0, grime=0.6, streaks=0.45, patches=0.35,
                             metal_floor=0.2, rough_scale=0.8, grit=0.8, scratches=0.22, edges=0.8, contrast=0.05)
sign_white = tk.grimy("SignWhite", (0.68, 0.66, 0.6), roughness=0.5, grime=0.75, grime_set="rust_coarse_01",
                      scale=1.6, stain=(0.5, 0.42, 0.3), grit=0.8, dirt_range=(0.22, 0.07))
sign_back = tk.photo_material("SignBack", "metal_plate_02", scale=2.0, value=1.5, exposed=None, grime=0.7,
                              streaks=0.8, metal_floor=0.6, rough_scale=0.7, grit=0.6, scratches=0.6, edges=0.5)
bare = tk.grimy("BareAlu", (0.62, 0.62, 0.63), roughness=0.3, metallic=1.0, grime=0.3)
hole = tk.grimy("Hole", (0.012, 0.01, 0.01), roughness=0.9, grime=0.1)
rubber = tk.grimy("Rubber", (0.022, 0.022, 0.022), roughness=0.62, grime=0.45, grit=0.3)
webbing = tk.grimy("Webbing", (0.55, 0.3, 0.03), roughness=0.75, grime=0.8, grit=0.8, bump_scale=140.0, bump=0.2,
                   dirt_range=(0.1, 0.03))
box_grey = tk.photo_material("BoxGrey", "metal_plate_02", scale=2.2, value=1.45, chip=1.0, grime=0.8, streaks=0.8,
                             patches=0.5, metal_floor=0.5, rough_scale=0.8, grit=0.9, scratches=0.5, edges=0.8)
lumber = grain_aligned(tk.photo_material("Lumber", "weathered_planks", scale=1.2, sat=0.5, value=2.2,
                                         tint=(1.0, 0.95, 0.88), exposed=None, grime=0.8, bump=0.7, grit=0.8,
                                         contrast=0.2))
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append
head = []


def add_head(o):
    tk.mark_part(o, "RamHead")
    head.append(o)
    return o


# ---------------------------------------------------------------- dimensions

AX = z(0.32)  # the cylinder's (and rod's) axis height
BARREL_R, ROD_R = 0.062, 0.022
GLAND_Y = -0.367  # front face of the gland nut
ROD_REAR = 0.44  # the rod's rear end: RamHead's origin
SIGN_Y = -0.445  # the sign's front face
SIGN_F = 0.56  # across the sign's flats
TRAVEL = 0.8


def ycyl(name, r, y0, y1, mat, x=0.0, zz=AX, segments=24, **kw):
    return tk.cylinder(name, r, y0, y1, mat, segments=segments, center=(x, zz), axis="Y", **kw)


# ---------------------------------------------------------------- skid: two runners, angle-iron crossmembers

for sx in (-1, 1):
    add(tk.box("Runner", (0.05, 0.84, 0.05), (sx * 0.3, 0.03, z(0.025)), frame, 0.004))
    tip = tk.box("RunnerTip", (0.05, 0.08, 0.05), (0.0, -0.04, 0.0), frame, 0.004)
    tip.matrix_world = Matrix.Translation((sx * 0.3, -0.39, z(0.025))) @ Matrix.Rotation(math.radians(-28), 4, "X")
    add(tip)
CROSS = (-0.33, 0.06, 0.44)
for y in CROSS:
    add(tk.box("CrossFlange", (0.66, 0.04, 0.005), (jitter(0.006), y, z(0.0525)), frame, 0.0015))
    add(tk.box("CrossWeb", (0.66, 0.005, 0.04), (jitter(0.006), y + 0.0175, z(0.07)), frame, 0.0015))
    for sx in (-1, 1):
        add(tk.box("Weld", (0.012, 0.042, 0.008), (sx * 0.276, y, z(0.053)), rust))
TOP = z(0.09)  # top of the crossmembers

# Front saddle: a square post, a saddle plate and a U-bolt over the barrel
SAD_Y = -0.29
add(tk.box("SaddlePost", (0.05, 0.05, (AX - BARREL_R - 0.012) - TOP), (0.0, SAD_Y, (AX - BARREL_R - 0.012 + TOP) / 2),
           frame, 0.004))
add(tk.box("SaddlePlate", (0.15, 0.06, 0.012), (0.0, SAD_Y, AX - BARREL_R - 0.006), frame, 0.003))
ub = [(0.074, SAD_Y, AX - BARREL_R - 0.03)]
ub += [(0.074 * math.cos(math.radians(d)), SAD_Y, AX + 0.074 * math.sin(math.radians(d))) for d in range(-20, 201, 20)]
ub += [(-0.074, SAD_Y, AX - BARREL_R - 0.03)]
add(hose("UBolt", ub, 0.007, rust, sides=6, smooth_steps=1)[0])
for sx in (-1, 1):
    add(tk.cylinder("UNut", 0.012, AX - BARREL_R - 0.024, AX - BARREL_R - 0.012, steel, segments=6,
                    center=(sx * 0.074, SAD_Y)))

# Middle: two scrap 4x4 blocks stacked under the barrel, cinched with a ratchet strap
MID_Y = CROSS[1]
h0 = TOP
for k, h in enumerate((0.086, AX - BARREL_R - TOP - 0.086)):
    b = tk.box("Block", (0.14, 0.089, h), (0.0, 0.0, 0.0), lumber, 0.005)
    grain_box(b, 0, 1.0, (rnd.uniform(0, 4), rnd.uniform(0, 4)))
    b.matrix_world = Matrix.Translation((jitter(0.01), MID_Y + jitter(0.006), h0 + h / 2)) @ \
        Matrix.Rotation(math.radians(jitter(5)), 4, "Z")
    add(b)
    h0 += h
strap_pts = []
for k in range(13):
    a = math.radians(-10 + 200 * k / 12)
    strap_pts.append((0.068 * math.cos(a), MID_Y, AX + 0.068 * math.sin(a)))
strap_pts = [(0.078, MID_Y, TOP - 0.035)] + strap_pts + [(-0.078, MID_Y, TOP - 0.035)]
strap_pts += [(-0.06, MID_Y, TOP - 0.044), (0.06, MID_Y, TOP - 0.044)]
add(strap("Strap", strap_pts, 0.032, 0.003, webbing, side=(0, 1, 0), closed=True))
add(tk.box("Ratchet", (0.016, 0.045, 0.075), (0.088, MID_Y, AX - 0.1), steel, 0.004))
add(tk.cylinder("RatchetSpool", 0.012, 0.075, 0.11, steel, segments=10, center=(MID_Y, AX - 0.075), axis="X"))

# Rear: clevis ears on the back crossmember
for sx in (-1, 1):
    add(tk.box("Ear", (0.012, 0.03, AX + 0.03 - TOP), (sx * 0.024, 0.463, (AX + 0.03 + TOP) / 2), frame, 0.003))
add(tk.cylinder("ClevisPin", 0.009, -0.04, 0.04, steel, segments=10, center=(0.463, AX), axis="X"))
for sx in (-1, 1):
    add(tk.cylinder("PinHead", 0.014, min(sx * 0.03, sx * 0.036), max(sx * 0.03, sx * 0.036), steel, segments=6,
                    center=(0.463, AX), axis="X"))

# ---------------------------------------------------------------- the cylinder

barrel = ycyl("Barrel", BARREL_R, -0.333, 0.432, cyl_paint, segments=32, rings=5)
add(tk.dent(barrel, 0.004, 0.1, seed=3))
add(ycyl("FrontCollar", BARREL_R + 0.006, -0.345, -0.323, steel, segments=24, bevel_width=0.003))
add(ycyl("Gland", 0.056, GLAND_Y + 0.004, -0.345, steel, segments=6, bevel_width=0.003))
add(ycyl("Wiper", ROD_R + 0.007, GLAND_Y, GLAND_Y + 0.004, rubber, segments=20))
add(ycyl("RearCap", BARREL_R + 0.005, 0.428, 0.452, steel, segments=24, bevel_width=0.004))
add(tk.box("ClevisLug", (0.03, 0.03, 0.05), (0.0, 0.463, AX), steel, 0.004))
for y in (-0.3, 0.385):
    add(tk.cylinder("PortBoss", 0.018, AX + BARREL_R - 0.01, AX + BARREL_R + 0.014, steel, segments=12, center=(0.0, y)))
    add(tk.cylinder("PortFit", 0.014, AX + BARREL_R + 0.014, AX + BARREL_R + 0.03, steel, segments=6, center=(0.0, y)))
for y in (-0.31, 0.415):
    add(tk.torus("WeldBead", BARREL_R + 0.002, 0.004, (0.0, 0.0, 0.0), rust, 28, 4))
    parts[-1].matrix_world = Matrix.Translation((0.0, y, AX)) @ Matrix.Rotation(math.radians(90), 4, "X")

# ---------------------------------------------------------------- motor, pump and valve (right side)

PLATE_Z = TOP + 0.008
add(tk.box("MotorPlate", (0.22, 0.42, 0.008), (0.31, 0.25, TOP + 0.004), frame, 0.002))
MX, MZ, MR = 0.31, PLATE_Z + 0.09, 0.075
motor = ycyl("Motor", MR, 0.13, 0.33, motor_paint, x=MX, zz=MZ, segments=24, rings=2)
add(tk.dent(motor, 0.003, 0.08, seed=6))
add(ycyl("EndBell", MR - 0.006, 0.105, 0.13, motor_paint, x=MX, zz=MZ, segments=24, bevel_width=0.004))
add(ycyl("EndBell", MR - 0.006, 0.33, 0.355, motor_paint, x=MX, zz=MZ, segments=24, bevel_width=0.004))
add(ycyl("FanCover", MR - 0.002, 0.355, 0.43, box_grey, x=MX, zz=MZ, segments=24, bevel_width=0.006))
for k in range(5):
    add(ycyl("FanSlot", MR - 0.0005, 0.372 + 0.011 * k, 0.377 + 0.011 * k, rubber, x=MX, zz=MZ, segments=24,
             caps=False))
for k in range(14):
    a = math.radians(-60 + 300 * k / 13)
    if abs(math.degrees(a) - 270) < 30:
        continue
    fin = tk.box("Fin", (0.014, 0.2, 0.004), (0.0, 0.0, 0.0), motor_paint)
    fin.matrix_world = Matrix.Translation((MX, 0.23, MZ)) @ Matrix.Rotation(-a, 4, "Y") @ Matrix.Translation((MR + 0.004, 0.0, 0.0))
    add(fin)
for y in (0.16, 0.3):
    add(tk.box("MotorFoot", (0.15, 0.03, 0.03), (MX, y, PLATE_Z + 0.015), motor_paint, 0.003))
    for sx in (-1, 1):
        add(tk.cylinder("FootBolt", 0.008, PLATE_Z, PLATE_Z + 0.036, steel, segments=6, center=(MX + sx * 0.06, y)))
add(tk.box("TermBox", (0.07, 0.085, 0.045), (MX - 0.01, 0.24, MZ + MR + 0.018), motor_paint, 0.005))
add(tk.box("TermLid", (0.074, 0.089, 0.006), (MX - 0.01, 0.24, MZ + MR + 0.043), box_grey, 0.002))
add(tk.box("NamePlate", (0.003, 0.07, 0.04), (MX + MR + 0.012, 0.2, MZ + 0.01), bare, 0.0008))
# coupling bell, gear pump and the splitter's control valve with its lever
add(ycyl("Bell", 0.048, 0.05, 0.105, steel, x=MX, zz=MZ, segments=20, bevel_width=0.003))
add(tk.box("Pump", (0.08, 0.06, 0.09), (MX, 0.02, MZ), steel, 0.006))
for sx in (-1, 1):
    add(tk.cylinder("PumpBolt", 0.006, -0.012, 0.0, steel, segments=6, center=(MX + sx * 0.028, MZ + 0.03), axis="Y"))
VX, VY, VZ = MX, -0.065, MZ + 0.005
add(tk.box("Valve", (0.065, 0.11, 0.075), (VX, VY, VZ), cyl_paint, 0.005))
add(tk.box("ValveCap", (0.07, 0.02, 0.08), (VX, VY - 0.06, VZ), steel, 0.004))
add(tk.box("LeverMount", (0.03, 0.02, 0.02), (VX, VY - 0.035, VZ + 0.045), steel, 0.003))
lev_a, lev_b = Vector((VX, VY - 0.035, VZ + 0.05)), Vector((VX + 0.02, VY - 0.12, VZ + 0.24))
add(place(tk.cylinder("Lever", 0.0065, 0.0, (lev_b - lev_a).length, steel, segments=8), lev_a, lev_b - lev_a))
add(place(tk.cylinder("Knob", 0.017, 0.0, 0.045, rubber, segments=12, bevel_width=0.006), lev_b - (lev_b - lev_a).normalized() * 0.01,
          lev_b - lev_a))
for k, x in enumerate((VX - 0.018, VX + 0.018)):
    add(tk.cylinder("ValvePort", 0.011, VZ + 0.0375, VZ + 0.055, steel, segments=6, center=(x, VY + 0.025)))

# ---------------------------------------------------------------- jerry can oil tank (left side)

add(tk.box("TankPlate", (0.2, 0.42, 0.008), (-0.31, 0.25, TOP + 0.004), frame, 0.002))
CX, CY, CW, CD, CH = -0.315, 0.235, 0.14, 0.27, 0.33
cz0 = PLATE_Z
can = tk.box("Can", (CW, CD, CH), (0.0, 0.0, 0.0), olive, 0.012)
can.matrix_world = Matrix.Translation((CX, CY, cz0 + CH / 2)) @ Matrix.Rotation(math.radians(3), 4, "Z")
add(tk.dent(can, 0.004, 0.08, seed=8))
seam = tk.box("CanSeam", (0.008, CD + 0.008, CH + 0.008), (0.0, 0.0, 0.0), olive, 0.003)
seam.matrix_world = can.matrix_world.copy()
add(seam)
for sx in (-1, 1):
    for sgn in (-1, 1):
        rib = tk.box("CanRib", (0.006, 0.34, 0.022), (0.0, 0.0, 0.0), olive)
        rib.matrix_world = can.matrix_world @ Matrix.Translation((sx * (CW / 2 + 0.001), 0.0, -0.01)) @ \
            Matrix.Rotation(sgn * math.atan2(CH - 0.07, CD - 0.06), 4, "X")
        add(rib)
for y in (-0.08, 0.0, 0.08):
    add(tk.box("CanHandlePost", (0.014, 0.012, 0.03), (CX, CY + y + 0.01, cz0 + CH + 0.012), olive))
add(tk.box("CanHandle", (0.016, 0.19, 0.016), (CX, CY + 0.01, cz0 + CH + 0.032), olive, 0.005))
SP = Vector((CX, CY - CD / 2 + 0.035, cz0 + CH - 0.005))
add(place(tk.cylinder("Spout", 0.019, 0.0, 0.035, steel, segments=14, bevel_width=0.002), SP, (0.0, -0.45, 1.0)))
add(place(tk.cylinder("SpoutCap", 0.024, 0.032, 0.045, olive, segments=14, bevel_width=0.003), SP, (0.0, -0.45, 1.0)))

# ---------------------------------------------------------------- hoses

FERRULE = []


def hydraulic(name, pts, radius=0.011):
    obj, P = hose(name, pts, radius, rubber)
    add(obj)
    for end, d in ((P[0], P[1] - P[0]), (P[-1], P[-2] - P[-1])):
        add(place(tk.cylinder(name + "Ferrule", radius + 0.004, 0.0, 0.035, steel, segments=8), end, d))


fp = Vector((0.0, -0.3, AX + BARREL_R + 0.03))
rp = Vector((0.0, 0.385, AX + BARREL_R + 0.03))
v1 = Vector((VX - 0.018, VY + 0.025, VZ + 0.055))
v2 = Vector((VX + 0.018, VY + 0.025, VZ + 0.055))
hydraulic("HoseFront", [v1, v1 + Vector((0.0, 0.0, 0.06)), Vector((0.2, -0.16, AX + 0.17)), Vector((0.06, -0.27, AX + 0.15)),
                        fp + Vector((0.0, 0.0, 0.07)), fp])
hydraulic("HoseRear", [v2, v2 + Vector((0.01, 0.0, 0.07)), Vector((0.25, 0.02, AX + 0.2)), Vector((0.14, 0.26, AX + 0.17)),
                       rp + Vector((0.0, 0.0, 0.07)), rp])
inlet = Vector((MX - 0.04, 0.02, MZ - 0.02))
spout_end = SP + Vector((0.0, -0.45, 1.0)).normalized() * 0.03
hydraulic("HoseSuction", [spout_end, spout_end + Vector((0.0, -0.04, 0.02)), Vector((CX + 0.01, CY - CD / 2 - 0.05, AX + 0.05)),
                          Vector((-0.22, -0.12, TOP + 0.05)), Vector((0.0, -0.13, TOP + 0.035)),
                          Vector((0.17, -0.07, TOP + 0.05)), inlet + Vector((-0.06, 0.0, 0.0)), inlet], 0.013)

# ---------------------------------------------------------------- junction box with the power lamp (front right)

JX, JY, JZ = 0.36, -0.36, z(0.24)
add(tk.box("JPost", (0.03, 0.03, JZ - 0.03 - z(0.05)), (0.3, JY + 0.02, (JZ - 0.03 + z(0.05)) / 2), frame, 0.003))
add(tk.box("JBracket", (0.07, 0.03, 0.006), (0.33, JY + 0.02, JZ - 0.05), frame, 0.002))
add(tk.box("JBox", (0.11, 0.07, 0.1), (JX, JY, JZ), box_grey, 0.007))
add(tk.box("JLid", (0.1, 0.006, 0.09), (JX, JY - 0.037, JZ), box_grey, 0.002))
add(tk.cylinder("LampBase", 0.021, JY - 0.054, JY - 0.04, rust, segments=16, center=(JX + 0.01, JZ + 0.015), axis="Y",
                bevel_width=0.002))
add(tk.cylinder("Lamp", 0.015, JY - 0.072, JY - 0.054, lamp, segments=16, center=(JX + 0.01, JZ + 0.015), axis="Y",
                bevel_width=0.005))
for k in range(3):
    ring = tk.torus("Cage", 0.018, 0.0016, (0.0, 0.0, 0.0), rust, 12, 4)
    ring.matrix_world = Matrix.Translation((JX + 0.01, JY - 0.058 - 0.006 * k, JZ + 0.015)) @ \
        Matrix.Rotation(math.radians(90), 4, "X")
    add(ring)
for sx in (-1, 1):
    for sz in (-1, 1):
        add(tk.cylinder("JScrew", 0.005, JY - 0.042, JY - 0.038, rust, segments=6, center=(JX + 0.04 * sx, JZ + 0.035 * sz),
                        axis="Y"))
LAMP_POS = Vector((JX + 0.01, JY - 0.072, JZ + 0.015))
add(hose("Conduit", [(JX + 0.02, JY + 0.035, JZ - 0.02), (JX + 0.04, JY + 0.1, JZ - 0.06), (0.425, 0.05, MZ - 0.06),
                     (0.425, 0.2, MZ + 0.05), (MX + 0.02, 0.24, MZ + MR + 0.03), (MX - 0.01, 0.24, MZ + MR + 0.04)],
         0.009, rubber)[0])
add(hose("PowerCable", [(JX - 0.02, JY, JZ - 0.05), (JX - 0.03, JY - 0.01, z(0.08)), (0.44, -0.3, z(0.012)),
                        (0.455, 0.0, z(0.012)), (0.46, 0.3, z(0.012)), (0.468, 0.465, z(0.012))], 0.011, rubber)[0])

# ---------------------------------------------------------------- the ram head: rod, push plate, braces and the sign

add_head(ycyl("Rod", ROD_R, -0.418, ROD_REAR, chrome, segments=20))
add_head(ycyl("RodFlange", 0.042, -0.431, -0.417, steel, segments=20, bevel_width=0.003))
add_head(ycyl("RodNut", 0.03, -0.417, -0.404, steel, segments=6, bevel_width=0.002))
BACKING = [tk.box("PushPlate", (0.2, 0.012, 0.2), (0.0, SIGN_Y + 0.003 + 0.006, AX), steel, 0.003)]
BR = 0.19
for sz in (-1, 1):
    zz = AX + sz * 0.13
    BACKING.append(tk.box("BraceFlange", (2 * BR, 0.005, 0.032), (0.0, SIGN_Y + 0.0055, zz), steel, 0.0015))
    BACKING.append(tk.box("BraceWeb", (2 * BR, 0.03, 0.005), (0.0, SIGN_Y + 0.018, zz + sz * 0.0135), steel, 0.0015))


def sign_warp(x, zz):
    """How far (along +Y, pushed back) the sign is bent at (x, z): dents, a warp and a corner bent back."""
    zr = zz - AX
    d = 0.003 * math.sin(x * 7.0 + 0.5) * math.cos(zr * 6.0)
    for cx, cz, amp, rad in ((-0.07, 0.235, 0.011, 0.05), (0.2, -0.03, 0.008, 0.045), (-0.22, -0.04, 0.005, 0.035),
                             (0.09, -0.235, 0.006, 0.045)):
        d += amp * math.exp(-((x - cx) ** 2 + (zr - cz) ** 2) / (rad * rad))
    s = x - zr
    if s > 0.335:
        d += (s - 0.335) * math.tan(math.radians(28))
    return d


def warp(obj):
    bake_in(obj)
    for v in obj.data.vertices:
        v.co.y += sign_warp(v.co.x, v.co.z)
    obj.data.update()
    return obj


# Sign plate: a grid cut to an octagon (flats on the axes), red face, bare back
half = SIGN_F / 2
N = 12
bm = bmesh.new()
grid = [[bm.verts.new((-half + 2 * half * i / N, 0.0, -half + 2 * half * j / N)) for j in range(N + 1)] for i in range(N + 1)]
for i in range(N):
    for j in range(N):
        bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
for sx in (-1, 1):
    for sz in (-1, 1):
        no = Vector((sx, 0.0, sz)).normalized()
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=no * half, plane_no=no,
                               clear_outer=True)
ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
bmesh.ops.translate(bm, vec=(0.0, 0.003, 0.0), verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bmesh.ops.translate(bm, vec=(0.0, SIGN_Y, AX), verts=bm.verts)
plate = tk.mesh_object("SignPlate", bm, sign_red)
plate.data.materials.append(sign_back)
for p in plate.data.polygons:
    p.material_index = 0 if p.normal.y < -0.9 else 1
add_head(warp(plate))


def flat_text(name, body, size, mat, location, font, resolution=4):
    """Painted lettering standing up facing -Y: a single filled face (no extrusion), at a low curve resolution."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = resolution
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cobj = tk.link(bpy.data.objects.new(name + "Curve", cu))
    cobj.location = location
    cobj.rotation_euler = (math.radians(90), 0.0, 0.0)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.matrix_world = cobj.matrix_world.copy()
    bpy.data.objects.remove(cobj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def octagon_ring(name, r_out, r_in, y, thick, mat, per_edge=4):
    """A flat octagonal band (flats at r from the center), subdivided along its edges so it can follow the sign."""
    bm = bmesh.new()

    def corner(r, k):
        a = math.radians(22.5 + 45 * k)
        return Vector((r / math.cos(math.radians(22.5)) * math.cos(a), 0.0, r / math.cos(math.radians(22.5)) * math.sin(a)))
    outer, inner = [], []
    for k in range(8):
        for t in range(per_edge):
            f = t / per_edge
            outer.append(corner(r_out, k).lerp(corner(r_out, k + 1), f))
            inner.append(corner(r_in, k).lerp(corner(r_in, k + 1), f))
    n = len(outer)
    fo = [bm.verts.new((p.x, y - thick, AX + p.z)) for p in outer]
    fi = [bm.verts.new((p.x, y - thick, AX + p.z)) for p in inner]
    bo = [bm.verts.new((p.x, y, AX + p.z)) for p in outer]
    bi = [bm.verts.new((p.x, y, AX + p.z)) for p in inner]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((fo[i], fo[j], fi[j], fi[i]))
        bm.faces.new((bo[i], bi[i], bi[j], bo[j]))
        bm.faces.new((fo[i], bo[i], bo[j], fo[j]))
        bm.faces.new((fi[i], fi[j], bi[j], bi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, mat)


for o in BACKING:
    add_head(warp(o))
add_head(warp(octagon_ring("SignBorder", half - 0.011, half - 0.03, SIGN_Y - 0.0002, 0.001, sign_white)))
text = flat_text("SignText", "STOP", 0.2, sign_white, (0.0, SIGN_Y - 0.0007, AX - 0.004),
                 "C:/Windows/Fonts/ARIALNB.TTF")
add_head(warp(text))

# Bolts through the sign into the push plate and the braces, and a few bullet holes
for x, zr in ((-0.075, 0.075), (0.075, 0.075), (-0.075, -0.075), (0.075, -0.075), (-0.17, 0.13), (0.17, 0.13),
              (-0.17, -0.13), (0.17, -0.13)):
    yb = SIGN_Y - 0.001 + sign_warp(x, AX + zr)
    add_head(tk.cylinder("SignBolt", 0.011, yb - 0.006, yb, steel, segments=10, center=(x, AX + zr), axis="Y",
                         radius_top=0.0075))
for x, zr in ((0.16, 0.19), (-0.21, -0.07), (0.045, 0.012), (-0.11, -0.2), (0.23, -0.12)):
    yb = SIGN_Y + sign_warp(x, AX + zr)
    add_head(tk.cylinder("Crater", 0.012, yb - 0.0016, yb - 0.0004, bare, segments=12, center=(x, AX + zr), axis="Y"))
    add_head(tk.cylinder("Hole", 0.0062, yb - 0.0022, yb - 0.0016, hole, segments=10, center=(x, AX + zr), axis="Y"))

# ---------------------------------------------------------------- bake (with the ram out) and export

atlas = tk.triangulate(tk.join(parts + head, "Ram"))
tk.smart_uvs(atlas)
OUT = Vector((0.0, -TRAVEL, 0.0))
shift_part(atlas, "RamHead", OUT)  # bake extended, so the rod's hidden length isn't baked dark inside the barrel
paths = tk.bake_atlas(atlas, ASSETS, "Ram_Atlas")
shift_part(atlas, "RamHead", -OUT)
baked = tk.baked_material("Ram_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
if ATTR in atlas.data.attributes:
    atlas.data.attributes.remove(atlas.data.attributes[ATTR])
model = atlas
PIVOT = Vector((0.0, ROD_REAR, AX))
ram_head = tk.split_part(model, "RamHead", PIVOT)
strike = tk.point("StrikePoint", (0.0, SIGN_Y, AX), ram_head)

export_with_part_points([model, ram_head, strike], os.path.join(ASSETS, "Ram.fbx"), [(strike, ram_head)])
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (model, ram_head))
print("[ram] triangles:", tris)


def bounds(objs):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return [tuple(round(c, 4) for c in b) for b in (lo, hi)]


bpy.context.view_layer.update()
print("[ram] bounds:", bounds([model, ram_head]))
print("[ram] RamHead pivot:", tuple(round(c, 4) for c in ram_head.matrix_world.translation), "bounds:", bounds([ram_head]))
print("[ram] StrikePoint:", tuple(round(c, 4) for c in strike.matrix_world.translation), "lamp:",
      tuple(round(c, 4) for c in LAMP_POS))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.5, -2.0, 0.75), (0, 0, z(0.4)), lens=45), os.path.join(PREVIEWS, "ram_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0, 0, z(0.35)), lens=45), os.path.join(PREVIEWS, "ram_back.png"))
tk.render(tk.camera("Close", (0.75, -0.95, 0.2), (0.12, -0.05, z(0.35)), lens=45), os.path.join(PREVIEWS, "ram_close.png"))
ram_head.location.y -= TRAVEL
bpy.context.view_layer.update()
print("[ram] extended StrikePoint:", tuple(round(c, 4) for c in strike.matrix_world.translation))
tk.render(tk.camera("Extended", (2.3, -1.6, 0.7), (0, -0.45, z(0.35)), lens=40), os.path.join(PREVIEWS, "ram_extended.png"))
ram_head.location.y += TRAVEL
tk.icon(tk.camera("Icon", (1.55, -2.05, 0.95), (0, -0.02, z(0.36)), lens=62), ICON, hide={"Floor", "ScaleFigure", "ScaleHead"},
        target=(0, 0, z(0.36)))
print("[ram] done")
