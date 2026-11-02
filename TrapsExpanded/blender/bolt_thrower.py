"""Bolt Thrower: a 1x1x1 block, powered. A ballista built from car junk: an army-green steel tripod with a car's
steering knuckle on top, the wheel hub and brake rotor turning in it as the yaw bearing (the old caliper still clamped
on), a steel-channel stock bolted to the wheel studs, a three-leaf car leaf spring as the bow with a steel cable for the
string, an ATV winch at the back that draws it, and a sharpened rebar bolt with bottle-plastic fletching loaded and
pointing at the front (-Y). A rusty junction box with the power lamp on the column, and a sandbag weighing a leg down.

Everything that turns (rotor, stock, bow, winch, bolt) is the moving part "Turret", turning about the hub's vertical
axis; the point "Muzzle" at the loaded bolt's tip rides on it.

    blender -b --factory-startup --python bolt_thrower.py -- <unity asset folder> <preview folder> <icon file>
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
rnd = random.Random(1887)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- helpers

def along(obj, start, direction):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(start) @ rot @ obj.matrix_world
    return obj


def bar(name, a, b, size, material, bevel_width=0.0, spin=0.0):
    """A rectangular bar (size = (w, t)) from a to b, turned `spin` degrees about its own axis."""
    a, b = Vector(a), Vector(b)
    obj = tk.box(name, (size[0], size[1], (b - a).length), (0.0, 0.0, (b - a).length / 2), material, bevel_width)
    obj.matrix_world = Matrix.Rotation(math.radians(spin), 4, "Z") @ obj.matrix_world
    return along(obj, a, b - a)


def nut(name, x, y, h, material, radius=0.008, height=0.008):
    """A plain hex nut or bolt head (no bevel, to keep the count down)."""
    return tk.cylinder(name, radius, h, h + height, material, segments=6, center=(x, y))


def tilt(obj, axis, degrees, pivot):
    return tk.orbit(obj, 0.0, tilt=(axis, degrees, pivot))


def spline(points, per=4):
    """Catmull-Rom through the points, for cables that bend smoothly."""
    pts = [Vector(p) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for k in range(per):
            t = k / per
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return [tuple(p) for p in out]


def sack(name, size, center, material, seed=0):
    """A lumpy sandbag: a rounded, subdivided box, flat underneath, dented."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
    for v in bm.verts:
        p = v.co * 2.0
        n = (abs(p.x) ** 3 + abs(p.y) ** 3 + abs(p.z) ** 3) ** (1.0 / 3.0)
        p = p / n
        p = Vector((p.x * size[0] / 2, p.y * size[1] / 2, max(p.z * size[2] / 2, -size[2] * 0.38)))
        v.co = p + Vector(center) + Vector((0.0, 0.0, size[2] * 0.38))
    obj = tk.mesh_object(name, bm, material)
    tk.smooth(obj, 80)
    return tk.dent(obj, 0.012, 0.06, seed=seed)


def vane(name, origin, phi, material, length=0.075, height=0.021, thick=0.0012, r0=0.0075):
    """A fletching vane cut from a plastic bottle, on a bolt along -Y from `origin` (its nock end), at angle phi
    (degrees from straight up)."""
    prof = [(0.004, 0.0), (length, 0.0), (length * 0.78, height * 0.45), (length * 0.18, height), (0.004, height * 0.95)]
    p = math.radians(phi)
    rv = Vector((math.sin(p), 0.0, math.cos(p)))
    tv = Vector((math.cos(p), 0.0, -math.sin(p)))
    o = Vector(origin)
    bm = bmesh.new()
    a = [bm.verts.new(o + Vector((0.0, -s, 0.0)) + rv * (r0 + r) - tv * (thick / 2)) for s, r in prof]
    b = [bm.verts.new(o + Vector((0.0, -s, 0.0)) + rv * (r0 + r) + tv * (thick / 2)) for s, r in prof]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(len(prof)):
        j = (i + 1) % len(prof)
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, material), 30)


def rebar_bolt(nock, rebar, point, plastic, tape, length=0.6, r=0.0075, spin=0.0):
    """A bolt: a length of rebar along -Y from `nock`, ribbed, ground to a point, with three vanes cut from a bottle
    taped on at the back."""
    x, y0, h = nock
    tip = y0 - length
    out = [tk.cylinder("Rebar", r, tip + 0.05, y0, rebar, segments=8, center=(x, h), axis="Y"),
           tk.cylinder("RebarPoint", r, tip, tip + 0.05, point, segments=8, center=(x, h), axis="Y",
                       radius_top=0.0009)]
    y = tip + 0.065
    while y < y0 - 0.095:
        rib = tk.cylinder("Rib", r + 0.0015, y, y + 0.0035, rebar, segments=6, center=(x, h), axis="Y")
        out.append(tilt(rib, "Z", 14.0, (x, y, h)))
        y += 0.019
    for s in (-1, 1):
        rib = tk.box("RibLong", (0.0022, y0 - 0.09 - (tip + 0.06), 0.0022),
                     (x + s * (r + 0.0004), (y0 - 0.09 + tip + 0.06) / 2, h), rebar)
        out.append(tilt(rib, "Y", spin, (x, 0.0, h)))
    for k in range(3):
        out.append(vane("Vane", (x, y0 - 0.006, h), spin + 120 * k + jitter(4), plastic))
    for y1, y2 in ((y0 - 0.086, y0 - 0.066), (y0 - 0.02, y0)):
        out.append(tk.cylinder("BoltTape", r + 0.0028, y1 + jitter(0.002), y2, tape, segments=12, center=(x, h),
                               axis="Y"))
    return out


def frame_icon(cam, objs, target, direction, fill=0.9):
    """Moves the camera along `direction` from `target` until the objects fill `fill` of the square icon, then
    shifts the frame so they sit in the middle."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = 480
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        me = o.evaluated_get(dg).data
        pts += [o.matrix_world @ v.co for v in me.vertices]
    d = Vector(direction).normalized()
    dist = (cam.location - Vector(target)).length
    cam.data.shift_x = cam.data.shift_y = 0.0
    for _ in range(6):
        cam.location = Vector(target) + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        co = [world_to_camera_view(scene, cam, p) for p in pts]
        span = max(max(c.x for c in co) - min(c.x for c in co), max(c.y for c in co) - min(c.y for c in co))
        dist *= span / fill
    cam.location = Vector(target) + d * dist
    bpy.context.view_layer.update()
    co = [world_to_camera_view(scene, cam, p) for p in pts]
    cam.data.shift_x = ((max(c.x for c in co) + min(c.x for c in co)) / 2 - 0.5)
    cam.data.shift_y = ((max(c.y for c in co) + min(c.y for c in co)) / 2 - 0.5)
    return cam


tk.reset_scene()
tk.preview_stage()

# ---------------------------------------------------------------- materials

olive = tk.photo_material("TripodPaint", "green_metal_rust", scale=1.7, sat=0.6, value=0.95, chip=1.0, grime=0.9,
                          streaks=1.4, patches=0.75, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55,
                          edges=0.85, contrast=0.12)
steel = tk.photo_material("Channel", "metal_plate_02", scale=1.9, value=1.05, chip=1.0, grime=0.8, streaks=1.0,
                          patches=0.85, metal_floor=0.5, rough_scale=0.85, grit=0.9, scratches=0.3, edges=0.7,
                          contrast=0.12)
plate = tk.photo_material("Plate", "metal_plate_02", scale=1.9, value=1.2, exposed=None, grime=0.7, streaks=0.5,
                          metal_floor=0.55, rough_scale=0.85, grit=0.9, scratches=0.45, edges=0.6, contrast=0.12)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
rotor_rust = tk.photo_material("Rotor", "rust_coarse_01", scale=3.2, value=1.0, exposed=None, grime=0.8,
                               metal_floor=0.35, grit=0.8, scratches=0.3)
spring_steel = tk.photo_material("SpringSteel", "metal_plate_02", scale=2.2, value=0.5, sat=0.5, chip=1.0, grime=0.8,
                                 streaks=0.9, patches=0.65, metal_floor=0.5, rough_scale=0.85, grit=0.9,
                                 scratches=0.18, edges=0.6, contrast=0.15)
caliper_red = tk.photo_material("CaliperPaint", "rusty_painted_metal", scale=2.2, sat=1.0, value=1.1, chip=1.0,
                                grime=0.9, patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55,
                                edges=0.8, contrast=0.12)
winch_black = tk.photo_material("WinchPaint", "metal_plate_02", scale=2.0, value=0.42, sat=0.4, chip=1.0, grime=0.8,
                                patches=0.45, metal_floor=0.45, rough_scale=0.8, grit=1.0, scratches=0.6, edges=0.85,
                                contrast=0.15)
box_red = tk.photo_material("RedBox", "rusty_painted_metal", scale=1.8, sat=1.0, value=1.15, chip=1.0, grime=0.8,
                            patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55, edges=0.8,
                            contrast=0.12)
wood = tk.photo_material("Wood", "weathered_planks", scale=0.8, value=1.2, exposed=None, grime=0.7, bump=0.6,
                         grit=0.55, contrast=0.2)
burlap = tk.grimy("Burlap", (0.46, 0.37, 0.22), roughness=0.92, grime=0.6, grit=1.0, bump_scale=260.0, bump=0.35,
                  stain=(0.33, 0.26, 0.15), dirt_range=(0.2, 0.06))
cable_steel = tk.grimy("Cable", (0.2, 0.2, 0.21), roughness=0.45, metallic=0.7, grime=0.7, grit=0.6,
                       bump_scale=300.0, bump=0.4, stain=(0.2, 0.11, 0.06))
bright = tk.photo_material("Ground", "metal_plate_02", scale=3.0, value=1.6, sat=0.4, exposed=None, grime=0.3,
                           metal_floor=0.8, rough_scale=0.6, grit=0.3, scratches=0.8)
bottle = tk.grimy("BottlePlastic", (0.06, 0.24, 0.11), roughness=0.22, grime=0.5, grit=0.5, dirt_range=(0.1, 0.03))
duct = tk.grimy("DuctTape", (0.42, 0.42, 0.43), roughness=0.45, metallic=0.3, grime=0.6, bump_scale=45.0, bump=0.12,
                grit=0.6)
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
red_cable = tk.grimy("RedCable", (0.33, 0.03, 0.02), roughness=0.5, grime=0.6, grit=0.8, dirt_range=(0.1, 0.03))
label = tk.grimy("Label", (0.62, 0.45, 0.06), roughness=0.6, grime=0.8, grime_set="rust_coarse_01", scale=1.4,
                 grit=0.6, dirt_range=(0.1, 0.03))
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append
turret = []
tu = turret.append

# ---------------------------------------------------------------- tripod (static)

COL_R = 0.042
add(tk.cylinder("Column", COL_R, z(0.1), z(0.5), olive, segments=20))
add(tk.cylinder("ColumnCap", COL_R + 0.003, z(0.09), z(0.1), rust, segments=16))
add(tk.cylinder("Collar", 0.058, z(0.31), z(0.38), olive, segments=20))
LEGS = (90.0, 210.0, 330.0)
feet = []
for k, a in enumerate(LEGS):
    ra = math.radians(a + jitter(3))
    A = Vector((0.05 * math.cos(ra), 0.05 * math.sin(ra), z(0.355)))
    F = Vector((0.4 * math.cos(ra), 0.4 * math.sin(ra), z(0.035)))
    add(bar("Leg", A, F, (0.04, 0.04), olive, 0.003, spin=math.degrees(ra)))
    foot = tk.box("Foot", (0.09, 0.09, 0.01), (F.x, F.y, z(0.005)), plate)
    add(tk.orbit(foot, 0.0, tilt=("Z", math.degrees(ra), (F.x, F.y, 0.0))))
    for s in (-1, 1):
        bx = F.x + 0.03 * math.cos(ra + math.pi / 2) * s
        by = F.y + 0.03 * math.sin(ra + math.pi / 2) * s
        add(nut("FootBolt", bx, by, z(0.01), rust, radius=0.008, height=0.008))
    add(bar("FootWeld", (F.x, F.y, z(0.01)), (F.x, F.y, z(0.06)), (0.05, 0.05), olive, 0.0,
            spin=math.degrees(ra)))
    feet.append((A, F))
# Rebar braces welded between the legs
for k in range(3):
    (A1, F1), (A2, F2) = feet[k], feet[(k + 1) % 3]
    p1, p2 = A1.lerp(F1, 0.62), A2.lerp(F2, 0.62)
    add(tk.tube("Brace", [tuple(p1), tuple(p1.lerp(p2, 0.5) + Vector((0, 0, jitter(0.01)))), tuple(p2)], 0.0065, rust,
                resolution=2))

# Steering knuckle on the column: the hub and rotor turn in it
add(tk.torus("Weld", COL_R + 0.004, 0.005, (0.0, 0.0, z(0.488)), rust, 20, 4))
kn = tk.cylinder("Knuckle", 0.064, z(0.49), z(0.545), rust, segments=24, bevel_width=0.006)
add(tk.dent(kn, 0.003, 0.05, seed=1))
for sx in (-1, 1):
    add(tk.box("KnuckleEar", (0.05, 0.034, 0.04), (0.082 * sx, 0.0, z(0.505)), rust))
    add(tk.cylinder("BallJoint", 0.016, z(0.47), z(0.505), rubber, segments=10, center=(0.1 * sx, 0.0)))
add(tk.box("SteerArm", (0.03, 0.07, 0.025), (-0.03, -0.085, z(0.51)), rust))

# The old brake caliper, still clamped on the back of the rotor, with its hose cut off
CAL = (0.0, 0.138, 0.56)
add(tk.box("Caliper", (0.095, 0.05, 0.072), (CAL[0], CAL[1], z(CAL[2])), caliper_red, 0.012))
add(tk.cylinder("CaliperPiston", 0.026, z(0.508), z(0.53), caliper_red, segments=14, center=(0.0, CAL[1] - 0.004)))
add(bar("CaliperBracket", (0.0, CAL[1] - 0.02, z(0.52)), (0.0, 0.045, z(0.505)), (0.05, 0.012), rust))
add(tk.cylinder("Bleeder", 0.004, z(0.596), z(0.606), plate, segments=6, center=(0.03, CAL[1] + 0.012)))
add(tk.tube("BrakeHose", spline([(-0.03, CAL[1] + 0.02, z(0.53)), (-0.06, CAL[1] + 0.05, z(0.5)),
                                 (-0.065, CAL[1] + 0.07, z(0.43)), (-0.05, CAL[1] + 0.08, z(0.39))], per=3), 0.006,
            rubber, resolution=2))

# ---------------------------------------------------------------- junction box with the power lamp on the column

JY, JH = -0.072, 0.22
add(tk.box("JBox", (0.1, 0.06, 0.1), (0.0, JY, z(JH)), box_red, 0.006))
add(tk.box("JLid", (0.088, 0.006, 0.088), (0.0, JY - 0.032, z(JH)), box_red))
add(tk.cylinder("LampBase", 0.019, JY - 0.045, JY - 0.035, rust, segments=12, center=(0.0, z(JH + 0.018)),
                axis="Y"))
add(tk.cylinder("Lamp", 0.0135, JY - 0.062, JY - 0.045, lamp, segments=16, center=(0.0, z(JH + 0.018)), axis="Y",
                bevel_width=0.005))
for k in range(2):
    ring = tk.torus("Cage", 0.016, 0.0016, (0.0, JY - 0.05 - 0.008 * k, z(JH + 0.018)), rust, 12, 4)
    add(tilt(ring, "X", 90, (0.0, JY - 0.05 - 0.008 * k, z(JH + 0.018))))
for sx in (-1, 1):
    for sz in (-1, 1):
        add(tk.cylinder("JScrew", 0.0045, JY - 0.037, JY - 0.034, rust, segments=6,
                        center=(0.036 * sx, z(JH + 0.036 * sz)), axis="Y"))
for h in (JH - 0.035, JH + 0.035):
    add(tk.cylinder("JStrap", COL_R + 0.003, z(h - 0.007), z(h + 0.007), plate, segments=14))
LAMP = (0.0, JY - 0.062, z(JH + 0.018))
add(tk.tube("PowerCable", spline([(0.02, JY, z(JH - 0.05)), (0.03, JY + 0.005, z(0.12)), (0.06, 0.0, z(0.012)),
                                  (0.2, 0.17, z(0.012)), (0.29, 0.32, z(0.012)), (0.31, 0.45, z(0.012))], per=3),
            0.009, rubber, resolution=3))
add(tk.tube("RiserCable", spline([(-0.02, JY + 0.004, z(JH + 0.05)), (-0.008, -0.064, z(0.3)),
                                  (-0.006, -0.066, z(0.4)), (-0.004, -0.05, z(0.48)), (0.0, -0.045, z(0.495))],
                                 per=3), 0.006, rubber, resolution=2))
add(tk.cylinder("CableTape", COL_R + 0.012, z(0.43), z(0.45), duct, segments=16))

# Sandbag weighing the back leg down
add(sack("Sandbag", (0.27, 0.15, 0.1), (jitter(0.01), 0.315, z(0.0)), burlap, seed=4))
add(tk.cylinder("SackTie", 0.012, 0.13, 0.155, burlap, segments=8, center=(0.315, z(0.04)), axis="X"))

# ---------------------------------------------------------------- turret: rotor and hub, mount plate, stock

PIV_H = 0.548
tu(tk.cylinder("Rotor", 0.14, z(PIV_H), z(0.572), rotor_rust, segments=36, bevel_width=0.003))
tu(tk.cylinder("RotorHat", 0.075, z(0.572), z(0.6), rotor_rust, segments=24))
tu(tk.box("MountPlate", (0.2, 0.17, 0.012), (0.0, 0.0, z(0.606)), steel, 0.003))
for k in range(5):
    a = math.radians(90 + 72 * k)
    sx, sy = 0.046 * math.cos(a), 0.046 * math.sin(a)
    tu(tk.cylinder("Stud", 0.005, z(0.612), z(0.632), plate, segments=6, center=(sx, sy)))
    tu(tk.cylinder("LugNut", 0.0105, z(0.612), z(0.627), plate, segments=6, center=(sx, sy)))

CH_Y0, CH_Y1 = -0.21, 0.38
for sx in (-1, 1):
    tu(tk.box("ChannelFlange", (0.008, CH_Y1 - CH_Y0, 0.05), (0.061 * sx, (CH_Y0 + CH_Y1) / 2, z(0.637)), steel,
              0.002))
web = tk.box("ChannelWeb", (0.13, CH_Y1 - CH_Y0, 0.008), (0.0, (CH_Y0 + CH_Y1) / 2, z(0.658)), steel, 0.002)
tu(tk.dent(web, 0.0015, 0.08, seed=2))
for sx in (-1, 1):
    tu(tk.box("Weld", (0.006, 0.16, 0.006), (0.0665 * sx, 0.0, z(0.614)), rust))

# Wooden deck the bolt rides on, with two strap-iron guides
DECK = 0.70
tu(tk.box("Deck", (0.09, 0.255, DECK - 0.662), (0.0, -0.0625, z((DECK + 0.662) / 2)), wood, 0.004))
for sx in (-1, 1):
    tu(tk.box("Guide", (0.006, 0.24, 0.006), (0.0135 * sx, -0.065, z(DECK + 0.003)), rust))
    for y in (-0.15, 0.03):
        tu(tk.cylinder("CarriageBolt", 0.007, z(DECK), z(DECK + 0.004), rust, segments=8, center=(0.033 * sx, y),
                       radius_top=0.004))

# ---------------------------------------------------------------- the bow: a three-leaf car spring

YC, K = -0.227, 0.7
SH = 0.674  # spring mid height (the bolt rides just over it)
SW, ST = 0.05, 0.008


def spring_y(x):
    return YC + K * x * x


def leaf(name, half, offset, material, segs=28, taper=0.55):
    bm = bmesh.new()
    rings = []
    for i in range(segs + 1):
        x = -half + 2 * half * i / segs
        tx, ty = 1.0, 2 * K * x
        n = math.hypot(tx, ty)
        tx, ty = tx / n, ty / n
        nx, ny = ty, -tx
        t = abs(x) / half
        th = ST * (1.0 - taper * max(0.0, (t - 0.65) / 0.35))
        cx, cy = x + nx * offset, spring_y(x) + ny * offset
        ring = [(cx - nx * th / 2, cy - ny * th / 2, z(SH - SW / 2)), (cx + nx * th / 2, cy + ny * th / 2, z(SH - SW / 2)),
                (cx + nx * th / 2, cy + ny * th / 2, z(SH + SW / 2)), (cx - nx * th / 2, cy - ny * th / 2, z(SH + SW / 2))]
        rings.append([bm.verts.new(p) for p in ring])
    for a, b in zip(rings, rings[1:]):
        for j in range(4):
            bm.faces.new((a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, material), 35)


for k, half in enumerate((0.415, 0.31, 0.2)):
    tu(leaf("Leaf", half + jitter(0.006), k * (ST + 0.0006), spring_steel, segs=28 - 6 * k, taper=0.0 if k == 0 else 0.55))
for x in (-0.25, -0.15, 0.15, 0.25):
    clip = tk.box("ReboundClip", (0.014, 3 * ST + 0.008, SW + 0.008),
                  (x, spring_y(x) + 0.011, z(SH)), rust)
    tu(tilt(clip, "Z", math.degrees(math.atan(2 * K * x)), (x, spring_y(x), z(SH))))
tu(tk.box("SpringBracket", (0.13, 0.012, 0.07), (0.0, -0.216, z(0.655)), steel, 0.003))
for sx in (-1, 1):
    x = 0.051 * sx
    tu(tk.tube("UBolt", spline([(x, -0.19, z(0.703)), (x, -0.235, z(0.703)), (x, -0.252, z(0.695)),
                                (x, -0.256, z(0.674)), (x, -0.252, z(0.653)), (x, -0.235, z(0.645)),
                                (x, -0.19, z(0.645))], per=2), 0.0045, rust, resolution=2))
    for h in (0.703, 0.645):
        tu(tk.cylinder("UNut", 0.009, -0.209, -0.197, rust, segments=6, center=(x, z(h)), axis="Y"))

# Rolled eyes at the main leaf's ends, bolts sticking up for the cable loops
eyes = []
for sx in (-1, 1):
    x = 0.415 * sx
    tx, ty = 1.0, 2 * K * x
    n = math.hypot(tx, ty)
    tx, ty = tx / n * sx, ty / n * sx  # pointing outward along the leaf
    nx, ny = 2 * K * x / n, -1.0 / n
    ex, ey = x + tx * 0.006 - nx * 0.012, spring_y(x) + ty * 0.006 - ny * 0.012
    tu(tk.cylinder("Eye", 0.016, z(SH - SW / 2), z(SH + SW / 2), spring_steel, segments=14, center=(ex, ey)))
    tu(tk.cylinder("Bushing", 0.0105, z(SH - SW / 2 - 0.004), z(SH + SW / 2 + 0.004), rubber, segments=12,
                   center=(ex, ey)))
    tu(tk.cylinder("EyeBolt", 0.0052, z(SH - SW / 2 - 0.016), z(0.722), plate, segments=8, center=(ex, ey)))
    for h in (SH - SW / 2 - 0.014, 0.713):
        tu(tk.cylinder("EyeNut", 0.0095, z(h), z(h + 0.008), rust, segments=6, center=(ex, ey)))
    eyes.append(Vector((ex, ey, z(0.708))))

# ---------------------------------------------------------------- string, latch and the winch

BOLT_H = DECK + 0.009
NOCK_Y = 0.157
nock = Vector((0.0, NOCK_Y + 0.005, z(BOLT_H)))
for e in eyes:
    loop = tk.torus("CableLoop", 0.0095, 0.0032, tuple(e), cable_steel, 10, 4)
    tu(loop)
    d = (nock - e).normalized()
    tu(tk.tube("String", [tuple(e + d * 0.008), tuple(nock)], 0.0034, cable_steel, resolution=2))
    for s in (0.035, 0.06):
        clip = tk.box("CableClip", (0.012, 0.016, 0.014), tuple(e + d * s + Vector((0, 0, 0.003))), rust)
        tu(tilt(clip, "Z", math.degrees(math.atan2(d.y, d.x)) - 90.0, tuple(e + d * s)))

# A gate latch on a riser block holds the string; a solenoid trips it
tu(tk.box("LatchRiser", (0.06, 0.06, DECK - 0.662), (0.0, 0.198, z((DECK + 0.662) / 2)), wood))
tu(tk.box("Latch", (0.04, 0.042, 0.022), (0.0, 0.192, z(DECK + 0.011)), rust))
for sx in (-1, 1):
    tu(tk.tube("LatchHook", spline([(0.014 * sx, 0.176, z(DECK + 0.018)), (0.014 * sx, 0.158, z(DECK + 0.02)),
                                     (0.014 * sx, 0.152, z(BOLT_H)), (0.014 * sx, 0.157, z(DECK + 0.002))], per=2),
               0.0035, plate, resolution=2))
tu(tk.cylinder("TripSolenoid", 0.011, 0.18, 0.226, winch_black, segments=12, center=(0.034, z(DECK + 0.012)),
               axis="Y", bevel_width=0.002))
tu(tk.tube("TripWire", spline([(0.034, 0.226, z(DECK + 0.012)), (0.05, 0.245, z(DECK + 0.004)),
                               (0.07, 0.27, z(0.69)), (0.1, 0.29, z(0.72)), (0.12, 0.3, z(0.725))], per=2), 0.0022,
           red_cable, resolution=1))

# ATV winch on a plate at the back: drum between end plates, motor on the right, gearbox and crank on the left
WY, WH = 0.305, 0.712
tu(tk.box("WinchBase", (0.25, 0.1, 0.008), (0.0, WY, z(0.666)), winch_black, 0.002))
for sx in (-1, 1):
    tu(tk.box("EndPlate", (0.008, 0.085, 0.088), (0.048 * sx, WY, z(0.714)), winch_black))
tu(tk.cylinder("Drum", 0.022, -0.044, 0.044, plate, segments=16, center=(WY, z(WH)), axis="X"))
tu(tk.cylinder("CableWrap", 0.033, -0.04, 0.04, cable_steel, segments=20, center=(WY, z(WH)), axis="X", rings=3))
for y in (WY - 0.035, WY + 0.035):
    tu(tk.cylinder("TieRod", 0.005, -0.052, 0.052, plate, segments=8, center=(y, z(0.75)), axis="X"))
tu(tk.cylinder("WinchMotor", 0.036, 0.052, 0.155, winch_black, segments=16, center=(WY, z(WH)), axis="X",
               bevel_width=0.005))
tu(tk.cylinder("MotorLabel", 0.0365, 0.075, 0.115, label, segments=16, center=(WY, z(WH)), axis="X"))
tu(tk.cylinder("MotorCap", 0.03, 0.155, 0.165, rust, segments=14, center=(WY, z(WH)), axis="X"))
for k, (dy, mat) in enumerate(((-0.012, red_cable), (0.012, rubber))):
    tu(tk.cylinder("MotorStud", 0.004, 0.165, 0.178, plate, segments=6, center=(WY + dy, z(WH + 0.012)), axis="X"))
    tu(tk.tube("MotorLead", spline([(0.176, WY + dy, z(WH + 0.012)), (0.19, WY + dy + 0.01, z(WH - 0.01)),
                                    (0.17, WY - 0.05 + dy, z(0.63)), (0.075, 0.2 + dy, z(0.6)),
                                    (0.07, 0.06 + dy, z(0.595)), (0.045, 0.05 + dy, z(0.598))], per=2), 0.0045, mat,
               resolution=2))
tu(tk.box("Gearbox", (0.05, 0.075, 0.08), (-0.077, WY, z(WH)), winch_black, 0.008))
tu(tk.box("ClutchLever", (0.012, 0.012, 0.04), (-0.077, WY + 0.02, z(WH + 0.055)), red_cable))
tu(tk.cylinder("CrankShaft", 0.006, -0.12, -0.1, plate, segments=8, center=(WY - 0.015, z(WH - 0.01)), axis="X"))
tu(bar("CrankArm", (-0.118, WY - 0.015, z(WH - 0.01)), (-0.118, WY - 0.015 + 0.02, z(WH - 0.075)), (0.008, 0.016),
       plate, 0.002))
tu(tk.cylinder("CrankKnob", 0.009, -0.15, -0.122, rubber, segments=8, center=(WY + 0.005, z(WH - 0.075)),
               axis="X"))
tu(tk.tube("WinchCable", [(0.0, WY - 0.02, z(WH - 0.031)), (0.0, 0.25, z(DECK + 0.006)),
                          (0.0, 0.214, z(DECK + 0.011))], 0.003, cable_steel, resolution=1))
for sx in (-1, 1):
    for y in (WY - 0.035, WY + 0.035):
        tu(nut("BaseBolt", 0.105 * sx, y, z(0.67), rust, radius=0.007, height=0.006))

# ---------------------------------------------------------------- the loaded bolt

for o in rebar_bolt((0.0, NOCK_Y, z(BOLT_H)), rust, bright, bottle, duct):
    tu(o)
MUZZLE = (0.0, NOCK_Y - 0.6, z(BOLT_H))

# ---------------------------------------------------------------- join, bake, split the turret off

for o in turret:
    tk.mark_part(o, "Turret")
atlas = tk.triangulate(tk.join(parts + turret, "BoltThrower"))
tk.smart_uvs(atlas)

paths = tk.bake_atlas(atlas, ASSETS, "BoltThrower_Atlas")
baked = tk.baked_material("BoltThrower_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

PIVOT = (0.0, 0.0, z(PIV_H))
part = tk.split_part(model, "Turret", PIVOT)
muzzle = tk.point("Muzzle", MUZZLE, part)

tk.export_fbx([model, part, muzzle], os.path.join(ASSETS, "BoltThrower.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons) + sum(len(p.vertices) - 2 for p in part.data.polygons)
print("[bolt_thrower] triangles:", tris, "(base", len(model.data.polygons), "turret", len(part.data.polygons), ")")
co = [model.matrix_world @ v.co for v in model.data.vertices] + [part.matrix_world @ v.co for v in part.data.vertices]
print("[bolt_thrower] bounds min", tuple(round(min(c[i] for c in co), 4) for i in range(3)),
      "max", tuple(round(max(c[i] for c in co), 4) for i in range(3)))
pr = max(math.hypot(v.co.x, v.co.y) for v in part.data.vertices)
print("[bolt_thrower] turret reach from the pivot axis", round(pr, 4))
bpy.context.view_layer.update()
print("[bolt_thrower] Turret pivot", tuple(round(c, 4) for c in part.matrix_world.translation))
print("[bolt_thrower] Muzzle", tuple(round(c, 4) for c in muzzle.matrix_world.translation), "parent", muzzle.parent.name)
print("[bolt_thrower] lamp lens front", tuple(round(c, 4) for c in LAMP))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.5, -2.0, 0.75), (0, 0, z(0.45)), lens=45),
          os.path.join(PREVIEWS, "bolt_thrower_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0, 0, z(0.45)), lens=45), os.path.join(PREVIEWS, "bolt_thrower_back.png"))
tk.render(tk.camera("Close", (0.62, -0.9, 0.5), (0.0, -0.12, z(0.66)), lens=45),
          os.path.join(PREVIEWS, "bolt_thrower_close.png"))
part.rotation_euler.z = math.radians(40)
bpy.context.view_layer.update()
print("[bolt_thrower] Muzzle turned 40", tuple(round(c, 4) for c in muzzle.matrix_world.translation))
tk.render(tk.camera("Turned", (0.9, -1.7, 1.45), (0, 0, z(0.5)), lens=45),
          os.path.join(PREVIEWS, "bolt_thrower_turned.png"))
part.rotation_euler.z = 0.0
bpy.context.view_layer.update()

d = Vector((1.9, -2.5, 1.5))
cam = tk.camera("Icon", tuple(Vector((0, 0, z(0.45))) + d), (0, 0, z(0.45)), lens=62)
frame_icon(cam, [model, part], (0, 0, z(0.45)), d, fill=0.92)
tk.icon(cam, ICON, hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.45)))
print("[bolt_thrower] done")
