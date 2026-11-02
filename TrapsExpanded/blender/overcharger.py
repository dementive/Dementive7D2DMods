"""Overcharger: a 1x1x1 block. A rusty, bent shopping cart (handle to +X, its side to the front) loaded with car
batteries of different makes, a bank of big can capacitors on a wood block, red and black jumper cables with clamps
running everywhere, and a board hung on the cart's side with an old panel voltmeter, the power lamp and a big knife
switch. One more battery rides on the cart's bottom rack.

The model carries one empty for the game: ArcPoint at the top of the capacitor bank, where the sparks come from.

    blender -b --factory-startup --python overcharger.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(7717)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- local helpers

def V(*c):
    return Vector(c)


def turn(obj, axis, degrees, pivot):
    p = Vector(pivot)
    obj.matrix_world = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(degrees), 4, axis)
                        @ Matrix.Translation(-p)) @ obj.matrix_world
    return obj


def plate(name, size, center, mat, bw=0.0015):
    """A box with a single chamfer (cheap on triangles, still catches the edge wear)."""
    obj = tk.box(name, size, center, mat)
    if bw:
        tk.bevel(obj, bw, segments=1)
        tk.smooth(obj)
    return obj


def taper_box(name, size, center, mat, taper=0.6):
    """A box along X whose +X end is narrowed (a clamp jaw)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    for v in bm.verts:
        if v.co.x > 0:
            v.co.y *= taper
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return tk.smooth(tk.mesh_object(name, bm, mat))


def wire(name, points, radius, mat, res=1, caps=False, closed=False):
    """trapkit.tube without end caps (the cart's wires end inside the rims)."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = res
    curve.use_fill_caps = caps
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (co[0], co[1], co[2], 1.0)
    spline.use_cyclic_u = closed
    cobj = tk.link(bpy.data.objects.new(name + "Curve", curve))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(cobj)
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return tk.smooth(obj, 50)


def text(name, body, size, mat, location, rotation=(90.0, 0.0, 0.0), font="C:/Windows/Fonts/impact.ttf"):
    """Flat painted lettering (trapkit.text_mesh with coarse curves, to keep the triangle count down)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 2
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cobj = tk.link(bpy.data.objects.new(name + "Curve", cu))
    cobj.location = location
    cobj.rotation_euler = [math.radians(r) for r in rotation]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.matrix_world = cobj.matrix_world.copy()
    bpy.data.objects.remove(cobj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def smooth_path(ctrl, per=6):
    """Catmull-Rom through the control points."""
    pts = [Vector(p) for p in ctrl]
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return [tuple(p) for p in out]


def line(a, b, n):
    return [tuple(Vector(a).lerp(Vector(b), k / (n - 1))) for k in range(n)]


def basis(direction, up):
    """A 4x4 rotation whose X axis is `direction` and Z axis is `up` (made orthogonal)."""
    x = Vector(direction).normalized()
    zz = Vector(up)
    zz = (zz - x * zz.dot(x)).normalized()
    y = zz.cross(x)
    m = Matrix((x, y, zz)).transposed()
    return m.to_4x4()


def bake_transform(obj):
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def bend(objs, amp, scale, seed, dents=()):
    """Bends and warps a group of parts in world space with one smooth noise field (so joined wires stay joined),
    plus local dents (center, radius, push vector)."""
    off = Vector(seed)
    for o in objs:
        bake_transform(o)
        for v in o.data.vertices:
            p = v.co.copy()
            d = noise.noise_vector(p / scale + off) * amp
            for c, r, push in dents:
                d += Vector(push) * math.exp(-((p - Vector(c)).length / r) ** 2)
            v.co = p + d


# ---------------------------------------------------------------- materials

tk.reset_scene()
tk.preview_stage()

cart_metal = tk.photo_material("CartMetal", "metal_plate_02", scale=2.2, sat=0.3, value=1.1, exposed="rust_coarse_01",
                               chip=1.0, patches=0.95, grime=0.9, streaks=0.8, metal_floor=0.5, rough_scale=0.9,
                               grit=1.0, scratches=0.4, edges=0.7, contrast=0.12)
steel = tk.photo_material("Steel", "metal_plate_02", scale=2.4, sat=0.3, value=0.85, exposed="rust_coarse_01",
                          chip=1.0, patches=0.5, grime=0.9, metal_floor=0.55, grit=0.9, scratches=0.5, edges=0.8)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
alu = tk.photo_material("Alu", "metal_plate_02", scale=2.6, sat=0.0, value=1.3, exposed="rust_coarse_01", chip=0.3,
                        patches=0.2, grime=1.0, metal_floor=0.5, rough_scale=0.9, grit=1.0, scratches=0.35, edges=0.6,
                        contrast=0.1)
wood = tk.photo_material("Wood", "weathered_planks", scale=0.8, value=1.15, exposed=None, grime=0.8, bump=0.6, grit=0.6,
                         contrast=0.2)
copper = tk.tarnished_copper("Copper")
handle_red = tk.grimy("HandleRed", (0.36, 0.04, 0.025), roughness=0.5, grime=0.8, grit=0.9, dirt_range=(0.1, 0.03),
                      stain=(0.2, 0.06, 0.03))
tyre = tk.grimy("Tyre", (0.05, 0.05, 0.05), roughness=0.8, grime=0.7, grit=1.0)
case_black = tk.grimy("CaseBlack", (0.03, 0.03, 0.032), roughness=0.45, grime=0.8, grit=1.0, stain=(0.1, 0.08, 0.06))
case_grey = tk.grimy("CaseGrey", (0.38, 0.37, 0.33), roughness=0.5, grime=1.0, grit=1.0, stain=(0.26, 0.2, 0.12))
case_blue = tk.grimy("CaseBlue", (0.03, 0.07, 0.2), roughness=0.5, grime=0.8, grit=1.0, dirt_range=(0.12, 0.035),
                     stain=(0.08, 0.1, 0.12))
lid_red = tk.grimy("LidRed", (0.33, 0.03, 0.02), roughness=0.5, grime=0.8, grit=0.9, dirt_range=(0.1, 0.03))
label_yellow = tk.grimy("LabelYellow", (0.6, 0.38, 0.03), roughness=0.55, grime=0.9, grit=0.8, dirt_range=(0.1, 0.03))
label_white = tk.grimy("LabelWhite", (0.55, 0.53, 0.47), roughness=0.6, grime=0.9, grit=0.8, dirt_range=(0.16, 0.05))
label_blue = tk.grimy("LabelBlue", (0.04, 0.12, 0.38), roughness=0.55, grime=0.7, grit=0.8, dirt_range=(0.1, 0.03))
ink_black = tk.grimy("InkBlack", (0.02, 0.02, 0.02), roughness=0.6, grime=0.3)
ink_white = tk.grimy("InkWhite", (0.6, 0.58, 0.52), roughness=0.6, grime=0.6, dirt_range=(0.16, 0.05))
lead = tk.grimy("Lead", (0.3, 0.3, 0.31), roughness=0.5, metallic=0.6, grime=0.8, grit=0.7)
sleeve_blue = tk.grimy("SleeveBlue", (0.03, 0.05, 0.16), roughness=0.4, grime=0.7, grit=0.9, dirt_range=(0.1, 0.03))
sleeve_black = tk.grimy("SleeveBlack", (0.025, 0.025, 0.028), roughness=0.4, grime=0.6, grit=0.9)
sleeve_brown = tk.grimy("SleeveBrown", (0.2, 0.15, 0.09), roughness=0.45, grime=0.8, grit=0.9, dirt_range=(0.14, 0.04))
cream = tk.grimy("Cream", (0.62, 0.57, 0.44), roughness=0.55, grime=0.8, grit=0.6, dirt_range=(0.18, 0.05))
bakelite = tk.grimy("Bakelite", (0.03, 0.025, 0.022), roughness=0.3, grime=0.6, grit=0.8)
knob_red = tk.grimy("KnobRed", (0.4, 0.05, 0.03), roughness=0.25, grime=0.6, grit=0.6, dirt_range=(0.1, 0.03))
slate = tk.grimy("Slate", (0.07, 0.07, 0.075), roughness=0.7, grime=0.8, grit=0.9, bump_scale=120.0, bump=0.2)
cable_red = tk.grimy("CableRed", (0.36, 0.035, 0.025), roughness=0.5, grime=0.7, grit=0.9, dirt_range=(0.1, 0.03))
cable_black = tk.grimy("CableBlack", (0.025, 0.025, 0.025), roughness=0.55, grime=0.6, grit=0.9)
tape = tk.grimy("Tape", (0.02, 0.02, 0.022), roughness=0.42, grime=0.25, bump_scale=35.0)
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append

# ---------------------------------------------------------------- shopping cart (handle to +X)

HB, HT = 0.5, 0.86                    # basket bottom and rim heights
XNB, XBB, YB = -0.2, 0.33, 0.22       # bottom: nose x, back x, half width
XNT, XBT, YT = -0.41, 0.35, 0.27      # rim: nose x, back x, half width

cart = []
WR = 0.0028


def grid(c00, c10, c01, c11, nu, nv, pu, pv):
    """Interior wires of one wall: c00/c10 the bottom (start/end), c01/c11 the top."""
    c00, c10, c01, c11 = V(*c00), V(*c10), V(*c01), V(*c11)

    def P(u, v):
        return c00.lerp(c10, u).lerp(c01.lerp(c11, u), v)

    for i in range(1, nu - 1):
        u = i / (nu - 1)
        cart.append(wire("Wire", [tuple(P(u, k / (pv - 1))) for k in range(pv)], WR, cart_metal))
    for j in range(1, nv - 1):
        v = j / (nv - 1)
        cart.append(wire("Wire", [tuple(P(k / (pu - 1), v)) for k in range(pu)], WR, cart_metal))


for s in (-1, 1):  # sides
    grid((XNB, s * YB, HB), (XBB, s * YB, HB), (XNT, s * YT, HT), (XBT, s * YT, HT), 12, 6, 6, 3)
grid((XNB, -YB, HB), (XNB, YB, HB), (XNT, -YT, HT), (XNT, YT, HT), 8, 6, 4, 3)   # nose
grid((XBB, -YB, HB), (XBB, YB, HB), (XBT, -YT, HT), (XBT, YT, HT), 8, 6, 4, 3)   # back gate
grid((XNB, -YB, HB), (XBB, -YB, HB), (XNB, YB, HB), (XBB, YB, HB), 8, 7, 5, 4)   # floor


def rounded_rect(x0, x1, y0, y1, h, r, n=3):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a), h))
    return pts


cart.append(wire("Rim", rounded_rect(XNT, XBT, -YT, YT, HT, 0.03), 0.0075, cart_metal, res=1, closed=True))
cart.append(wire("Rim", rounded_rect(XNT + 0.008, XBT - 0.008, -YT + 0.008, YT - 0.008, HT - 0.035, 0.03), 0.004,
                 cart_metal, res=1, closed=True))
cart.append(wire("BottomFrame", rounded_rect(XNB, XBB, -YB, YB, HB, 0.015, 2), 0.0045, cart_metal, res=1, closed=True))
for sx, sy in ((0, -1), (0, 1), (1, -1), (1, 1)):
    b = (XNB if sx == 0 else XBB, sy * YB, HB)
    t = (XNT if sx == 0 else XBT, sy * YT, HT)
    cart.append(wire("Corner", line(b, t, 4), 0.0045, cart_metal, res=1))

# Chassis: a U-shaped base tube, rear legs up to the handle, front legs to the basket, bottom rack
HR = 0.105
base = [(0.34, -0.19, HR), (-0.25, -0.16, HR), (-0.33, -0.14, HR), (-0.365, -0.07, HR), (-0.37, 0.0, HR),
        (-0.365, 0.07, HR), (-0.33, 0.14, HR), (-0.25, 0.16, HR), (0.34, 0.19, HR)]
cart.append(wire("Base", smooth_path(base, 3), 0.011, cart_metal, res=1, caps=True))
cart.append(wire("BaseBack", line((0.34, -0.19, HR), (0.34, 0.19, HR), 4), 0.009, cart_metal, res=1))
for s in (-1, 1):
    cart.append(wire("RearLeg", smooth_path([(0.34, 0.19 * s, HR), (0.36, 0.225 * s, 0.45), (0.395, 0.25 * s, 0.82),
                                             (0.44, 0.255 * s, 0.925)], 3), 0.0105, cart_metal, res=2))
    cart.append(wire("FrontLeg", smooth_path([(-0.31, 0.15 * s, HR), (-0.27, 0.18 * s, 0.3), (XNB + 0.01, 0.2 * s, HB)],
                                             3), 0.008, cart_metal, res=1))
    cart.append(wire("HandleArm", smooth_path([(XBT, (YT - 0.02) * s, HT), (0.4, 0.258 * s, 0.9),
                                               (0.44, 0.255 * s, 0.925)], 2), 0.007, cart_metal, res=1))
cart.append(wire("HandleBar", line((0.44, -0.262, 0.925), (0.44, 0.262, 0.925), 6), 0.011, cart_metal, res=2,
                 caps=True))
for y in (-0.12, -0.06, 0.0, 0.06, 0.12):
    cart.append(wire("RackWire", line((-0.33, y, HR + 0.013), (0.34, y * 1.2, HR + 0.013), 5), WR, cart_metal))
for x in (-0.25, -0.05, 0.15):
    cart.append(wire("RackWire", line((x, -0.165, HR + 0.016), (x, 0.165, HR + 0.016), 4), WR, cart_metal))
cart.append(tk.cylinder("HandleGrip", 0.0165, -0.215, 0.215, handle_red, segments=14, center=(0.44, 0.925), axis="Y",
                        bevel_width=0.004))

# The cart was laid out in heights above the floor; drop it onto the block's bottom
for o in cart:
    o.matrix_world = Matrix.Translation((0.0, 0.0, Z)) @ o.matrix_world
# Bent and battered: an overall warp, the near nose corner caved in, one end of the handle knocked down
bend(cart, 0.011, 0.3, (3.1, 7.2, 1.3),
     dents=(((XNT, -YT, z(HT)), 0.15, (0.04, 0.05, -0.05)),
            ((0.44, -0.26, z(0.925)), 0.12, (0.0, 0.0, -0.028)),
            ((0.0, -0.245, z(0.68)), 0.12, (0.0, 0.016, 0.0))))
for o in cart:
    add(o)

# Casters (swivel forks turned every which way)
for (x, y), yaw in zip(((0.33, -0.185), (0.33, 0.185), (-0.33, -0.15), (-0.33, 0.15)), (12, -25, 70, 100)):
    cst = [tk.box("Swivel", (0.05, 0.045, 0.006), (0.0, 0.0, 0.091), rust),
           tk.cylinder("SwivelBolt", 0.007, 0.075, 0.097, rust, segments=6)]
    for s in (-1, 1):
        cst.append(tk.box("Fork", (0.05, 0.004, 0.058), (0.02, 0.019 * s, 0.062), rust))
    cst.append(tk.cylinder("Wheel", 0.042, -0.0125, 0.0125, tyre, segments=16, center=(0.03, 0.042), axis="Y"))
    cst.append(tk.cylinder("Hub", 0.02, -0.016, 0.016, steel, segments=8, center=(0.03, 0.042), axis="Y"))
    m = Matrix.Translation((x, y, Z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    for o in cst:
        o.matrix_world = m @ o.matrix_world
        add(o)


# ---------------------------------------------------------------- batteries

def battery(name, size, case, lid, label, ink, label_text, center, yaw, tilt=0.0, pos_right=True, handle=False,
            caps=None):
    L, W, H = size
    objs = [plate(name + "Case", (L, W, H - 0.022), (0.0, 0.0, (H - 0.022) / 2), case, 0.006),
            plate(name + "Lid", (L + 0.006, W + 0.006, 0.024), (0.0, 0.0, H - 0.012), lid, 0.004)]
    ps = 1 if pos_right else -1
    tp = V(ps * (L / 2 - 0.035), -(W / 2 - 0.032), H + 0.02)
    tn = V(-ps * (L / 2 - 0.035), -(W / 2 - 0.032), H + 0.02)
    for t in (tp, tn):
        objs.append(tk.cylinder("Post", 0.0095, H - 0.002, H + 0.02, lead, segments=10, center=(t.x, t.y),
                                radius_top=0.0078))
    if caps:
        objs.append(tk.cylinder("PostCap", 0.016, H - 0.001, H + 0.012, caps, segments=12, center=(tn.x, tn.y + 0.04),
                                bevel_width=0.003))
    for sx in (-1, 1):
        objs.append(tk.box("Vent", (L * 0.34, 0.03, 0.006), (sx * L * 0.2, 0.028, H + 0.002), lid))
    objs.append(plate("Label", (L * 0.66, 0.003, H * 0.34), (0.0, -W / 2 - 0.0012, H * 0.47), label, 0.0))
    objs.append(text(name + "Text", label_text, H * 0.11, ink, (0.0, -W / 2 - 0.0032, H * 0.48)))
    if handle:
        objs.append(wire("BatHandle", smooth_path([(-L * 0.28, 0.0, H + 0.004), (-L * 0.2, 0.0, H + 0.035),
                                                   (L * 0.2, 0.0, H + 0.035), (L * 0.28, 0.0, H + 0.004)], 3),
                         0.004, case, res=1, caps=True))
    m = (Matrix.Translation(center) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
         @ Matrix.Rotation(math.radians(tilt), 4, "X"))
    for o in objs:
        o.matrix_world = m @ o.matrix_world
        add(o)
    return m @ tp, m @ tn, m


F0 = HB + 0.004
A_pos, A_neg, A_m = battery("BatA", (0.25, 0.175, 0.19), case_black, case_black, lid_red, ink_white, "HEAVY DUTY",
                            V(0.19, -0.105, z(F0)), 3.0, pos_right=True, handle=True)
B_pos, B_neg, B_m = battery("BatB", (0.24, 0.17, 0.2), case_grey, case_grey, label_blue, ink_white, "12 VOLT",
                            V(0.18, 0.1, z(F0)), 176.0, pos_right=False)
C_pos, C_neg, C_m = battery("BatC", (0.25, 0.17, 0.18), case_black, lid_red, label_yellow, ink_black, "DEEP CYCLE",
                            V(0.2, 0.0, z(F0 + 0.2)), -86.0, tilt=3.0, pos_right=True, caps=lid_red)
D_pos, D_neg, D_m = battery("BatD", (0.26, 0.17, 0.19), case_blue, case_blue, label_white, ink_black, "MARINE",
                            V(0.03, 0.0, z(HR + 0.017)), 1.5, pos_right=False)

# ---------------------------------------------------------------- capacitor bank on a wood block (nose half)

add(plate("CapBlock", (0.2, 0.3, 0.1), (-0.085, 0.0, z(F0 + 0.05)), wood, 0.004))
add(tk.dent(parts[-1], 0.003, 0.05, seed=5))
BASE_H = F0 + 0.1
rows = ((-0.13, 0.26), (-0.04, 0.275))
caps_top = {}
sleeves = (sleeve_blue, sleeve_black, sleeve_blue, sleeve_brown, sleeve_blue, sleeve_black)
k = 0
for x, h in rows:
    for y in (-0.09, 0.0, 0.09):
        c = (x + jitter(0.003), y + jitter(0.003))
        top = BASE_H + h
        add(tk.cylinder("Can", 0.04, z(BASE_H), z(top), alu, segments=14, center=c))
        add(tk.cylinder("Sleeve", 0.0412, z(BASE_H + 0.012), z(top - 0.014), sleeves[k], segments=14, center=c,
                        caps=False))
        add(tk.cylinder("Stripe", 0.0418, z(top - 0.07), z(top - 0.05), cream, segments=14, center=c, caps=False))
        add(tk.cylinder("CapTop", 0.035, z(top - 0.002), z(top + 0.007), bakelite, segments=12, center=c))
        for s in (-1, 1):
            add(tk.cylinder("Terminal", 0.0075, z(top + 0.007), z(top + 0.018), lead, segments=6,
                            center=(c[0] + 0.016 * s, c[1])))
        caps_top[(x, y)] = top + 0.018
        k += 1
BUS = {}
for x, h in rows:
    top = BASE_H + h + 0.018
    for s, key in ((1, "P"), (-1, "N")):
        bx = x + 0.016 * s
        add(plate("BusBar", (0.014, 0.23, 0.004), (bx, 0.0, z(top + 0.002)), copper, 0.001))
        for y in (-0.09, 0.0, 0.09):
            add(tk.cylinder("BusNut", 0.008, z(top + 0.004), z(top + 0.01), steel, segments=6, center=(bx, y)))
        BUS[(x, key)] = (bx, top + 0.004)
# Parallel links between the rows, tilted to meet the higher row
for y, key in ((-0.112, "P"), (0.112, "N")):
    (x0, h0), (x1, h1) = BUS[(rows[0][0], key)], BUS[(rows[1][0], key)]
    add(wire("BusLink", [(x0, y, z(h0)), (x1, y, z(h1))], 0.004, copper, res=1, caps=True))
for hh in (0.06, 0.15):
    band = rounded_rect(-0.177, 0.007, -0.137, 0.137, z(BASE_H + hh), 0.042, 2)
    add(wire("CapBand", band, 0.0028, rust, res=1, closed=True))
add(tk.cylinder("BandScrew", 0.007, -0.03, 0.0, rust, segments=6, center=(-0.153, z(BASE_H + 0.06)), axis="Y"))
ARC = V(-0.085, 0.0, z(max(BUS[(rows[1][0], "P")][1], BUS[(rows[1][0], "N")][1]) + 0.004))


# ---------------------------------------------------------------- jumper cables and clamps

def clamp(name, tip, direction, up, grip, open_deg=8.0):
    """A jumper-cable clamp whose jaw tips are at `tip`, pointing along `direction`; returns where the cable leaves."""
    objs = [tk.cylinder("ClampSpring", 0.0075, -0.014, 0.014, rust, segments=8, center=(0.0, 0.0), axis="Y")]
    for s in (1, -1):
        jaw = taper_box("Jaw", (0.064, 0.02, 0.005), (0.032, 0.0, 0.006 * s), steel, 0.55)
        teeth = tk.box("Teeth", (0.026, 0.013, 0.003), (0.046, 0.0, 0.0028 * s), copper)
        for o in (jaw, teeth):
            objs.append(turn(o, "Y", -s * open_deg, (0.0, 0.0, 0.0)))
        arm = tk.box("ClampArm", (0.06, 0.017, 0.004), (-0.028, 0.0, 0.007 * s), steel)
        grip_box = tk.box("Grip", (0.052, 0.022, 0.011), (-0.04, 0.0, 0.012 * s), grip)
        for o in (arm, grip_box):
            objs.append(turn(o, "Y", s * 9.0, (0.0, 0.0, 0.0)))
    m = Matrix.Translation(Vector(tip)) @ basis(direction, up) @ Matrix.Translation((-0.064, 0.0, 0.0))
    for o in objs:
        o.matrix_world = m @ o.matrix_world
        add(o)
    return m @ V(-0.07, 0.0, 0.0), (m.to_3x3() @ V(-1.0, 0.0, 0.0)).normalized()


def cable(name, ctrl, mat, radius=0.0065, per=5):
    add(wire(name, smooth_path(ctrl, per), radius, mat, res=1, caps=True))


def on_post(post, away, grip, up=(0.0, 0.0, 1.0)):
    """A clamp biting a battery post from the side, its body lying back along `away`."""
    a = Vector(away).normalized()
    return clamp("Clamp", post + V(0.0, 0.0, -0.01) - a * 0.004, -a, up, grip)


# 1 red: battery C (+) to the capacitors' + bus, clamped on the bar's front end
c1a, d1a = on_post(C_pos, V(-0.6, -0.5, 0.15), handle_red)
p = BUS[(rows[1][0], "P")]
c1b, d1b = clamp("Clamp", V(p[0], -0.118, z(p[1] + 0.0)), V(0.0, 1.0, -0.15), V(1.0, 0.0, 0.0), handle_red)
cable("Cable1", [c1a, c1a + d1a * 0.04, V(0.0, -0.24, z(0.97)), c1b + d1b * 0.05, c1b], cable_red, per=6)
# 2 black: the capacitors' - bus (back end) to battery A (-)
p = BUS[(rows[0][0], "N")]
c2a, d2a = clamp("Clamp", V(p[0], 0.118, z(p[1])), V(0.0, -1.0, -0.15), V(1.0, 0.0, 0.0), ink_black)
c2b, d2b = on_post(A_neg, V(-0.4, -0.6, 0.3), ink_black)
cable("Cable2", [c2a, c2a + d2a * 0.05, V(-0.17, 0.21, z(0.91)), V(-0.02, 0.17, z(0.9)), V(0.035, 0.0, z(0.8)),
                 c2b + d2b * 0.05, c2b], cable_black)

# ---------------------------------------------------------------- the board hung on the cart's front side

SLOPE = math.degrees(math.atan2(YT - YB, HT - HB))
BC = V(0.175, -0.258, z(0.64))
BM = Matrix.Translation(BC) @ Matrix.Rotation(math.radians(SLOPE), 4, "X")
board = [plate("Board", (0.27, 0.014, 0.19), (0.0, 0.0, 0.0), wood, 0.003)]
# Old panel voltmeter
MX, MZ = -0.07, 0.015
board += [plate("MeterFlange", (0.1, 0.006, 0.1), (MX, -0.01, MZ), bakelite, 0.004),
          tk.cylinder("MeterBody", 0.043, -0.03, -0.012, bakelite, segments=20, center=(MX, MZ), axis="Y",
                      bevel_width=0.004),
          tk.cylinder("Dial", 0.036, -0.032, -0.029, cream, segments=20, center=(MX, MZ), axis="Y")]
bez = tk.torus("Bezel", 0.039, 0.0035, (MX, -0.031, MZ), steel, 24, 6)
board.append(turn(bez, "X", 90, (MX, -0.031, MZ)))
PV = V(MX, -0.0325, MZ - 0.02)
for kk in range(9):
    a = math.radians(-50 + 100 * kk / 8)
    tick = tk.box("Tick", (0.0012, 0.0008, 0.006 if kk % 2 == 0 else 0.004), (0.0, 0.0, 0.0), ink_black)
    tick.matrix_world = (Matrix.Translation(PV) @ Matrix.Rotation(-a, 4, "Y")
                         @ Matrix.Translation((0.0, 0.0, 0.043))) @ tick.matrix_world
    board.append(tick)
needle = tk.box("Needle", (0.0014, 0.0008, 0.042), (0.0, -0.0006, 0.021), knob_red)
needle.matrix_world = Matrix.Translation(PV) @ Matrix.Rotation(math.radians(-31), 4, "Y") @ needle.matrix_world
board.append(needle)
board.append(text("MeterV", "V", 0.011, ink_black, (MX, -0.0329, MZ - 0.004)))
for s in (-1, 1):
    board.append(tk.cylinder("MeterStud", 0.005, -0.012, -0.004, steel, segments=6, center=(MX + 0.036 * s, MZ - 0.036),
                             axis="Y"))
# Power lamp under the meter
LX, LZ = -0.07, -0.068
board += [tk.cylinder("LampBase", 0.015, -0.017, -0.007, rust, segments=16, center=(LX, LZ), axis="Y",
                      bevel_width=0.002),
          tk.cylinder("Lamp", 0.0105, -0.029, -0.017, lamp, segments=16, center=(LX, LZ), axis="Y", bevel_width=0.004)]
for kk in range(2):
    c = (LX, -0.022 - 0.005 * kk, LZ)
    ring = tk.torus("Cage", 0.012, 0.0013, c, rust, 14, 5)
    board.append(turn(ring, "X", 90, c))
# Big double-pole knife switch on a slate base, closed
SX = 0.065
board.append(plate("SwitchBase", (0.11, 0.01, 0.17), (SX, -0.012, 0.0), slate, 0.003))
for pole in (-0.024, 0.024):
    x = SX + pole
    for s in (-1, 1):
        board.append(plate("Hinge", (0.004, 0.02, 0.022), (x + 0.0065 * s, -0.027, -0.058), copper, 0.001))
        board.append(plate("Jaw", (0.004, 0.022, 0.026), (x + 0.0065 * s, -0.028, 0.058), copper, 0.001))
    board.append(tk.cylinder("HingePin", 0.003, x - 0.012, x + 0.012, steel, segments=6, center=(-0.03, -0.058),
                             axis="X"))
    board.append(plate("Blade", (0.0065, 0.004, 0.14), (x, -0.031, 0.006), copper, 0.001))
    for zz in (-0.074, 0.074):
        board.append(tk.cylinder("Lug", 0.0055, -0.024, -0.017, steel, segments=6, center=(x, zz), axis="Y"))
board += [plate("CrossBar", (0.07, 0.012, 0.014), (SX, -0.038, 0.05), bakelite, 0.003),
          tk.cylinder("HandleStalk", 0.0055, -0.085, -0.044, steel, segments=8, center=(SX, 0.05), axis="Y"),
          tk.cylinder("Knob", 0.0125, -0.115, -0.08, knob_red, segments=12, center=(SX, 0.05), axis="Y",
                      bevel_width=0.005)]
for o in board:
    o.matrix_world = BM @ o.matrix_world
    add(o)
LAMP = BM @ V(LX, -0.029, LZ)
SW_TOP = BM @ V(SX + 0.024, -0.024, 0.074)
SW_BOT = BM @ V(SX - 0.024, -0.024, -0.074)
# Wire hooks over the rim
for x in (-0.1, 0.1):
    p0 = BM @ V(x, 0.0, 0.095)
    add(wire("Hook", smooth_path([p0, V(p0.x, -YT - 0.006, z(HT - 0.01)), V(p0.x, -YT + 0.004, z(HT + 0.014)),
                                  V(p0.x, -YT + 0.02, z(HT - 0.015))], 3), 0.0022, rust, res=1, caps=True))
    add(tk.cylinder("HookScrew", 0.005, -0.001, 0.004, steel, segments=6, center=(0.0, 0.0)))
    parts[-1].matrix_world = BM @ Matrix.Translation((x, -0.008, 0.08)) @ Matrix.Rotation(math.radians(90), 4, "X")

# 3 red: battery A (+) over the rim to the switch's top lug
c3a, d3a = on_post(A_pos, V(0.3, -0.9, 0.3), handle_red)
cable("Cable3", [c3a, c3a + d3a * 0.04, V(0.3, -0.26, z(0.9)), V(0.27, -0.29, z(0.85)),
                 V(0.255, -0.31, z(0.79)), SW_TOP + V(0.0, -0.012, 0.03), SW_TOP], cable_red, per=4)
# 4 red: the switch's bottom lug, sagging along the cart's side, over the rim to the capacitors' other row
p = BUS[(rows[0][0], "P")]
c4b, d4b = clamp("Clamp", V(p[0], -0.118, z(p[1])), V(0.0, 1.0, -0.2), V(1.0, 0.0, 0.0), handle_red)
cable("Cable4", [SW_BOT, SW_BOT + V(0.0, -0.015, -0.03), V(0.02, -0.285, z(0.5)), V(-0.12, -0.272, z(0.55)),
                 V(-0.2, -0.29, z(0.75)), V(-0.19, -0.285, z(0.9)), V(-0.15, -0.22, z(0.93)), c4b + d4b * 0.05, c4b],
      cable_red, per=4)
# 5 black: battery C (-) over the back side and down to the battery on the bottom rack
c5a, d5a = on_post(C_neg, V(0.3, 0.8, 0.15), ink_black)
c5b, d5b = on_post(D_neg, V(0.2, 0.8, 0.3), ink_black)
cable("Cable5", [c5a, c5a + d5a * 0.05, V(0.18, 0.3, z(0.92)), V(0.2, 0.32, z(0.8)), V(0.2, 0.31, z(0.45)),
                 V(0.12, 0.24, z(0.32)), c5b + d5b * 0.05, c5b], cable_black, per=4)
# 6 and 7: a pair off battery B over the back gate, down to the floor, clamps lying loose at the front right
c6a, d6a = on_post(B_pos, V(0.2, 0.9, 0.3), handle_red)
c7a, d7a = on_post(B_neg, V(-0.2, 0.9, 0.3), ink_black)


def on_floor(tip, direction, grip, open_deg):
    d = Vector(direction).normalized()
    return clamp("Clamp", tip, d, V(0.0, 0.0, 1.0).cross(d), grip, open_deg)


g6, g6d = on_floor(V(0.25, -0.43, z(0.0155)), V(-1.0, -0.15, 0.0), handle_red, 16.0)
g7, g7d = on_floor(V(0.15, -0.38, z(0.0155)), V(-0.9, -0.45, 0.0), ink_black, 12.0)
cable("Cable6", [c6a, c6a + d6a * 0.04, V(0.3, 0.27, z(0.93)), V(0.37, 0.2, z(0.91)), V(0.42, 0.08, z(0.7)),
                 V(0.435, -0.06, z(0.4)), V(0.44, -0.18, z(0.1)), V(0.43, -0.31, z(0.013)), g6 + g6d * 0.05, g6],
      cable_red, per=4)
cable("Cable7", [c7a, c7a + d7a * 0.04, V(0.12, 0.29, z(0.92)), V(0.36, 0.15, z(0.915)), V(0.41, 0.04, z(0.72)),
                 V(0.425, -0.08, z(0.42)), V(0.42, -0.22, z(0.09)), V(0.36, -0.31, z(0.013)), g7 + g7d * 0.05, g7],
      cable_black, per=4)
add(tk.cylinder("CableTape", 0.016, -0.02, 0.02, tape, segments=12, center=(0.0, 0.0), axis="Z"))
parts[-1].matrix_world = (Matrix.Translation((0.434, -0.01, z(0.55))) @ Matrix.Rotation(math.radians(-8), 4, "X")
                          @ parts[-1].matrix_world)

# ---------------------------------------------------------------- join, bake, export

tris = {}
for o in parts:
    key = o.name.split(".")[0]
    tris[key] = tris.get(key, 0) + sum(len(p.vertices) - 2 for p in o.data.polygons)
print("[overcharger] parts:", sorted(tris.items(), key=lambda kv: -kv[1])[:16])
for o in parts:
    w = [o.matrix_world @ v.co for v in o.data.vertices]
    if w and (max(abs(c.x) for c in w) > 0.47 or max(abs(c.y) for c in w) > 0.47 or min(c.z for c in w) < Z
              or max(c.z for c in w) > 0.5):
        print("[overcharger] near/over bounds:", o.name, "x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (
            min(c.x for c in w), max(c.x for c in w), min(c.y for c in w), max(c.y for c in w),
            min(c.z for c in w), max(c.z for c in w)))

atlas = tk.triangulate(tk.join(parts, "Overcharger"))
tk.smart_uvs(atlas)
paths = tk.bake_atlas(atlas, ASSETS, "Overcharger_Atlas")
baked = tk.baked_material("Overcharger_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

arc_pt = tk.point("ArcPoint", ARC, model)
tk.export_fbx([model, arc_pt], os.path.join(ASSETS, "Overcharger.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[overcharger] triangles:", tris)
co = [model.matrix_world @ v.co for v in model.data.vertices]
print("[overcharger] bounds: x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f" % (
    min(c.x for c in co), max(c.x for c in co), min(c.y for c in co), max(c.y for c in co),
    min(c.z for c in co), max(c.z for c in co)))
print("[overcharger] ArcPoint:", tuple(round(c, 4) for c in arc_pt.matrix_world.translation))
print("[overcharger] lamp lens front:", tuple(round(c, 4) for c in LAMP))

# ---------------------------------------------------------------- previews and icon

core = tk.glow("ArcCore", (0.6, 0.78, 1.0), 14.0)
halo = tk.glow("ArcHalo", (0.12, 0.35, 1.0), 5.0, alpha=0.4)
arcs = []
t0 = V(rows[0][0] + 0.016, -0.09, z(caps_top[(rows[0][0], -0.09)] + 0.01))
for kk, (a, b) in enumerate(((ARC + V(0.0, -0.05, 0.0), ARC + V(-0.12, -0.2, 0.16)),
                             (ARC + V(0.02, 0.06, 0.0), ARC + V(0.08, 0.2, 0.2)),
                             (t0, ARC + V(-0.2, 0.05, 0.12)))):
    arcs += tk.bolt("IconArc%d" % kk, a, b, 21 + kk, core, halo, radius=0.005, roughness=0.18, branches=2)
for o in arcs:
    o.hide_render = True

tk.render(tk.camera("Front", (1.6, -2.15, 0.85), (0.0, 0.0, z(0.5)), lens=45),
          os.path.join(PREVIEWS, "overcharger_front.png"))
tk.render(tk.camera("Back", (-1.8, 1.7, 1.2), (0.0, 0.0, z(0.48)), lens=45),
          os.path.join(PREVIEWS, "overcharger_back.png"))
tk.render(tk.camera("Close", (0.55, -1.0, 0.55), (0.02, -0.1, z(0.72)), lens=45),
          os.path.join(PREVIEWS, "overcharger_close.png"))
tk.icon(tk.camera("Icon", (2.1, -2.8, 1.6), (0.0, 0.0, z(0.47)), lens=70), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, extra=arcs, target=(0.0, 0.0, z(0.5)))
print("[overcharger] done")
