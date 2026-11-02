"""Trip Bow: a one-block damage trap. A weathered 2x4 sawhorse with a camo compound hunting bow lashed flat across
the front end of its beam with rope and duct tape, drawn, an arrow nocked and pointing to the front (-Y). The string
is held back by a bent-rod hook on a bolt through the beam; a yellow cord runs from the hook down to a pulley on a
back leg, forward along the ground to a stake and across the front as the tripwire. Spare arrows stand in a length
of PVC pipe tied to a back leg.

ArrowOrigin is the nocked arrow's tip and ArrowAim is a meter straight ahead of it, level.

    blender -b --factory-startup --python trip_bow.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(3119)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# Everything is built with h = height above the ground and moved down by Z at the end
BX = -0.03  # the beam's center line (x)
BEAM_TOP = 0.64
YR = -0.33  # the bow's riser
HB = 0.681  # the bow's plane (riser center height)
HA = 0.694  # the arrow's height, a little above the riser where it passes through the sight window
XA = 0.035  # the arrow's line (x)
YN = 0.27  # the nock, where the hook holds the string
TIP = Vector((XA, -0.452, HA))  # the broadhead's point


def bake_transform(obj):
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def sweep(name, pts, widths, depths, material, up=(0.0, 0.0, 1.0), bevel_width=0.0, smooth_angle=40.0):
    """A rectangular section swept along a polyline: `widths` across it along `up`, `depths` the other way."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    widths = widths if hasattr(widths, "__len__") else [widths] * n
    depths = depths if hasattr(depths, "__len__") else [depths] * n
    bm = bmesh.new()
    rings = []
    upv = Vector(up)
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - p
        elif i == n - 1:
            t = p - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        t.normalize()
        u = (upv - t * upv.dot(t)).normalized()
        s = t.cross(u)
        w, d = widths[i] / 2, depths[i] / 2
        rings.append([bm.verts.new(p + u * w + s * d), bm.verts.new(p - u * w + s * d),
                      bm.verts.new(p - u * w - s * d), bm.verts.new(p + u * w - s * d)])
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, material)
    if bevel_width:
        tk.bevel(obj, bevel_width)
    return tk.smooth(obj, smooth_angle)


def clip_floor(obj, h=0.0):
    """Cuts off whatever is below height h and caps the cut (leg and stake ends standing on the ground)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0.0, 0.0, h),
                                 plane_no=(0.0, 0.0, 1.0), clear_inner=True)
    edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def plate(name, pts, normal, thickness, material):
    """A flat polygon (3D points in one plane) given a thickness along `normal`, centered on the points."""
    nv = Vector(normal).normalized()
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p) - nv * thickness / 2) for p in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=nv * thickness, verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, material)


def along(obj, start, end):
    """Stands an object built along +Z from the origin between two points."""
    d = Vector(end) - Vector(start)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(start)) @ rot @ obj.matrix_world
    return bake_transform(obj)


def camo_material(name):
    """A hunting bow's faded camo dip (tan, olive and near-black blotches), dirty, scratched, worn to bare
    aluminum on the edges."""
    mat, g = tk.new_material(name)
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (5.0, 9.0, 5.0)
    v = m.outputs[0]
    n1 = g.noise(3.0, detail=3.0, distortion=1.4, vector=v)
    n2 = g.noise(4.7, detail=2.0, distortion=1.0, vector=v)
    col = g.mix(g.ramp(n1, 0.5, 0.53), (0.21, 0.165, 0.1), (0.05, 0.058, 0.03))
    col = g.mix(g.ramp(n2, 0.56, 0.59), col, (0.018, 0.016, 0.013))
    p = tk.photo(g, "metal_plate_02", 2.0, (0.2, 0.4, 0.1))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.3, 0.1), 0.35)
    col = g.mix(dirt, col, (0.05, 0.045, 0.035))
    col, rough, metal = tk._grit(g, col, 0.55, 0.0, 0.35, scratches=0.12, edges=0.35)
    return tk.finish(mat, g, col, metal, rough, g.bump(g.noise(80.0), 0.05, 0.002))


tk.reset_scene()
tk.preview_stage()

wood = tk.photo_material("Wood", "weathered_planks", scale=0.8, sat=0.7, value=1.6, exposed=None, grime=0.75, bump=0.6,
                         grit=0.6, contrast=0.2)
ply = tk.photo_material("Plywood", "weathered_planks", scale=1.6, sat=0.8, value=1.3, tint=(1.0, 0.95, 0.85),
                        exposed=None, grime=0.8, bump=0.4, grit=0.7, contrast=0.15, offset=(0.3, 0.6, 0.1))
camo = camo_material("Camo")
cam_metal = tk.photo_material("CamMetal", "metal_plate_02", scale=2.4, value=1.25, exposed=None, grime=0.8,
                              metal_floor=0.7, rough_scale=0.8, grit=0.8, scratches=0.6, edges=0.8)
steel = tk.photo_material("Steel", "metal_plate_02", scale=3.0, value=1.3, exposed="rust_coarse_01", chip=0.8,
                          grime=0.6, metal_floor=0.8, rough_scale=0.7, grit=0.5, scratches=0.6, edges=0.9)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.1, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
string = tk.grimy("String", (0.05, 0.048, 0.045), roughness=0.55, grime=0.4, grit=0.5)
carbon = tk.grimy("Carbon", (0.025, 0.025, 0.028), roughness=0.3, metallic=0.1, grime=0.5, grit=0.6)
vane = tk.grimy("Vane", (0.5, 0.17, 0.04), roughness=0.4, grime=0.6, grit=0.6, dirt_range=(0.1, 0.03))
vane_white = tk.grimy("VaneWhite", (0.55, 0.53, 0.48), roughness=0.4, grime=0.8, grit=0.7)
rubber = tk.grimy("Rubber", (0.03, 0.03, 0.03), roughness=0.8, grime=0.5, grit=0.8)
rope = tk.grimy("Rope", (0.1, 0.17, 0.32), roughness=0.9, grime=0.85, bump_scale=160.0, bump=0.5, grit=0.8,
                stain=(0.12, 0.15, 0.2), dirt_range=(0.1, 0.03))
tape = tk.grimy("DuctTape", (0.42, 0.42, 0.43), roughness=0.45, metallic=0.3, grime=0.6, bump_scale=45.0, bump=0.12,
                grit=0.6)
pvc = tk.grimy("PVC", (0.56, 0.55, 0.5), roughness=0.5, grime=1.0, stain=(0.42, 0.37, 0.27), grit=0.9)
cord = tk.grimy("Cord", (0.55, 0.38, 0.08), roughness=0.7, grime=0.7, grit=0.6, dirt_range=(0.1, 0.03))

parts = []
add = parts.append

# ---------------------------------------------------------------- the sawhorse: a 2x4 beam on four splayed legs


def leg_at(sx, sy, h):
    """The center of a leg at height h (legs run from the beam's sides out to the ground)."""
    t = (0.6 - h) / 0.6
    return Vector((BX + sx * (0.0415 + 0.2585 * t), sy * (0.36 + 0.04 * t), h))


beam = tk.box("Beam", (0.045, 0.84, 0.09), (BX, 0.0, BEAM_TOP - 0.045), wood, 0.004)
add(tk.orbit(beam, 0.0, tilt=("Z", 0.6, (BX, 0.0, 0.6))))
for sx in (-1, 1):
    for sy in (-1, 1):
        top, bottom = leg_at(sx, sy, 0.6), leg_at(sx, sy, 0.0)
        d = (bottom - top).normalized()
        leg = sweep("Leg", [top + d * -0.015 + Vector((jitter(0.004), 0, 0)), bottom + d * 0.05], 0.085, 0.038, wood,
                    up=(0.0, 1.0, 0.0), bevel_width=0.003)
        add(clip_floor(leg))
# Plywood gussets nailed across the outside of each leg pair, a 1x4 spreader lower down
for sy in (-1, 1):
    pts = []
    for sx, h in ((-1, 0.545), (1, 0.545), (1, 0.4), (-1, 0.4)):
        c = leg_at(sx, sy, h)
        pts.append(Vector((c.x + sx * 0.02, sy * (abs(c.y) + 0.0425 + 0.006), h)))
    pts[2].x += jitter(0.01)
    add(plate("Gusset", pts, (0.0, 1.0, 0.0), 0.012, ply))
    for sx in (-1, 1):
        for h in (0.43, 0.51):
            c = leg_at(sx, sy, h)
            yn = sy * (abs(c.y) + 0.0425 + 0.012)
            add(tk.cylinder("Nail", 0.0035, yn - 0.002, yn + 0.002, rust, segments=6, center=(c.x, h), axis="Y"))
    a, b = leg_at(-1, sy, 0.2), leg_at(1, sy, 0.2)
    ys = sy * (abs(a.y) + 0.0425 + 0.009)
    add(sweep("Spreader", [(a.x - 0.03, ys, 0.2 + jitter(0.01)), (b.x + 0.03, ys, 0.2 + jitter(0.01))], 0.085, 0.018,
              wood, up=(0.0, 0.0, 1.0), bevel_width=0.002))

# ---------------------------------------------------------------- the bow, lashed flat across the front of the beam

add(tk.box("Shim", (0.07, 0.06, 0.03), (BX - 0.005, YR + 0.018, BEAM_TOP + 0.015), wood, 0.003))


def riser_y(x):
    return YR + 0.028 * (1.0 - (x / 0.25) ** 2) - 0.006


def riser_drop(x):
    """The sight window: the riser is cut away (offset down) where the arrow passes."""
    lo, hi = 0.005, 0.12
    ramp = min(1.0, max(0.0, (x - lo + 0.02) / 0.02)) * min(1.0, max(0.0, (hi + 0.02 - x) / 0.02))
    return 0.013 * ramp


xs = [-0.25, -0.21, -0.16, -0.12, -0.09, -0.05, -0.015, 0.005, 0.03, 0.07, 0.11, 0.135, 0.17, 0.21, 0.25]
riser_pts = [(x, riser_y(x), HB - riser_drop(x)) for x in xs]
riser_w = [0.022 - 0.006 * riser_drop(x) / 0.013 for x in xs]
riser_d = [0.032 + 0.018 * math.exp(-((x + 0.05) / 0.05) ** 2) for x in xs]
add(sweep("Riser", riser_pts, riser_w, riser_d, camo, up=(0.0, 0.0, 1.0), bevel_width=0.003))
add(tk.box("Grip", (0.075, 0.05, 0.027), (-0.048, riser_y(-0.048) + 0.006, HB), rubber, 0.008))
for sx in (-1, 1):
    add(tk.box("Pocket", (0.04, 0.042, 0.03), (sx * 0.24, riser_y(0.24) - 0.002, HB), cam_metal, 0.004))
    limb = [(sx * 0.245, riser_y(0.245) - 0.004), (sx * 0.29, YR - 0.006), (sx * 0.34, YR + 0.008),
            (sx * 0.395, YR + 0.044)]
    for dz in (-0.011, 0.011):
        add(sweep("Limb", [(x, y, HB + dz) for x, y in limb], [0.016, 0.015, 0.013, 0.012], [0.013, 0.012, 0.011, 0.01],
                  camo, up=(0.0, 0.0, 1.0), bevel_width=0.002))
    cam_c = Vector((sx * 0.40, YR + 0.05, HB))
    add(tk.cylinder("Cam", 0.033, HB - 0.005, HB + 0.005, cam_metal, segments=18, center=(cam_c.x - sx * 0.004,
                                                                                            cam_c.y + 0.006),
                    bevel_width=0.0015))
    add(tk.cylinder("CamModule", 0.019, HB - 0.006, HB + 0.006, cam_metal, segments=12,
                    center=(cam_c.x + sx * 0.012, cam_c.y - 0.014), bevel_width=0.0015))
    add(tk.cylinder("Axle", 0.0045, HB - 0.02, HB + 0.02, steel, segments=8, center=(cam_c.x, cam_c.y)))
    # the string, drawn back to the hook
    add(tk.tube("String", [(cam_c.x - sx * 0.031, cam_c.y + 0.012, HB), (XA, YN, HA)], 0.0022, string, resolution=1))
    # the buss cable, through the cable guard slide to the far axle
    add(tk.tube("Cable", [(cam_c.x - sx * 0.006, cam_c.y - 0.03, HB + sx * 0.004), (0.06, YR + 0.1, HB - 0.03),
                          (-sx * 0.39, YR + 0.04, HB - sx * 0.004)], 0.0019, string, resolution=1))
add(tk.tube("CableGuard", [(0.06, riser_y(0.06) + 0.01, HB - 0.012), (0.06, YR + 0.12, HB - 0.03)], 0.004, cam_metal,
            resolution=1))
add(tk.box("Slide", (0.012, 0.018, 0.012), (0.06, YR + 0.1, HB - 0.03), rubber, 0.002))

# Whisker-biscuit rest round the arrow and a pin sight in front of the riser
rest = tk.torus("Rest", 0.016, 0.0045, (0.0, 0.0, 0.0), rubber, 18, 6)
rest.matrix_world = Matrix.Translation((XA, riser_y(XA) - 0.004, HA)) @ Matrix.Rotation(math.radians(90), 4, "X")
add(bake_transform(rest))
add(tk.box("RestMount", (0.03, 0.012, 0.006), (XA + 0.025, riser_y(XA) - 0.004, HB - 0.002), cam_metal, 0.002))
add(sweep("SightBar", [(0.135, riser_y(0.135) - 0.01, HB + 0.004), (0.135, YR - 0.07, HB + 0.006)], 0.006, 0.012,
          cam_metal, up=(0.0, 0.0, 1.0), bevel_width=0.0015))
sight = tk.torus("Sight", 0.021, 0.005, (0.0, 0.0, 0.0), cam_metal, 18, 6)
sight.matrix_world = Matrix.Translation((0.135, YR - 0.082, HB + 0.006)) @ Matrix.Rotation(math.radians(90), 4, "X")
add(bake_transform(sight))
for k, dz in enumerate((-0.006, 0.0, 0.006)):
    add(tk.cylinder("Pin", 0.0012, 0.135 - 0.02, 0.135 - 0.004 - 0.003 * k, steel, segments=6,
                    center=(YR - 0.082, HB + 0.006 + dz), axis="X"))

# ---------------------------------------------------------------- the arrow, nocked


def arrow(start_nock, direction, name, cock=vane, hen=vane_white, length=0.72):
    """An arrow lying along `direction` from its nock end: carbon shaft, three vanes, a broadhead."""
    d = Vector(direction).normalized()
    side = d.cross(Vector((0.0, 0.0, 1.0)))
    if side.length < 0.1:
        side = d.cross(Vector((1.0, 0.0, 0.0)))
    side.normalize()
    up = side.cross(d).normalized()
    n0 = Vector(start_nock)
    objs = []
    shaft = tk.cylinder(name + "Shaft", 0.0042, 0.012, length - 0.05, carbon, segments=8)
    objs.append(along(shaft, n0, n0 + d))
    nock = tk.cylinder(name + "Nock", 0.0046, 0.0, 0.014, cock, segments=8)
    objs.append(along(nock, n0, n0 + d))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        radial = up * math.cos(a) + side * math.sin(a)
        prof = [(0.025, 0.004), (0.025, 0.012), (0.04, 0.0155), (0.065, 0.013), (0.095, 0.004)]
        pts = [n0 + d * t + radial * r for t, r in prof]
        objs.append(plate(name + "Vane", pts, d.cross(radial), 0.0009, cock if k == 0 else hen))
    f0 = n0 + d * (length - 0.05)
    ferrule = tk.cylinder(name + "Ferrule", 0.0048, 0.0, 0.032, steel, segments=8, radius_top=0.0022)
    objs.append(along(ferrule, f0, f0 + d))
    point = tk.cylinder(name + "Point", 0.0022, 0.032, 0.05, steel, segments=6, radius_top=0.0002)
    objs.append(along(point, f0, f0 + d))
    for k in range(3):
        a = math.radians(30 + 120 * k)
        radial = up * math.cos(a) + side * math.sin(a)
        pts = [f0 + d * 0.004 + radial * 0.003, f0 + d * 0.008 + radial * 0.016, f0 + d * 0.046 + radial * 0.002]
        objs.append(plate(name + "Blade", pts, d.cross(radial), 0.0008, steel))
    return objs


nock_end = Vector((XA, YN - 0.008, HA))
for o in arrow(nock_end, (0.0, -1.0, 0.0), "Arrow", length=(nock_end - TIP).length):
    add(o)

# ---------------------------------------------------------------- the hook holding the string, on a bolt through the beam

LX = BX + 0.0225 + 0.0055  # the hook rod runs up the beam's right side
add(tk.cylinder("PivotBolt", 0.006, BX - 0.03, LX + 0.012, steel, segments=8, center=(0.29, 0.6), axis="X"))
for x0 in (BX - 0.03, LX + 0.006):
    add(tk.cylinder("PivotNut", 0.011, x0, x0 + 0.007, rust, segments=6, center=(0.29, 0.6), axis="X"))
hook = [(LX, 0.306, 0.515), (LX, 0.296, 0.57), (LX, 0.29, 0.6), (LX, 0.284, 0.65), (LX, 0.279, 0.69),
        (LX + 0.004, 0.272, 0.705), (XA - 0.012, 0.262, 0.709), (XA + 0.004, 0.258, 0.703),
        (XA + 0.007, 0.261, 0.689), (XA + 0.003, 0.268, 0.683)]
add(tk.tube("Hook", hook, 0.0042, rust, resolution=2))
add(tk.cylinder("HookEnd", 0.0055, 0.505, 0.517, rust, segments=8, center=(LX, 0.306)))

# ---------------------------------------------------------------- the trip cord: hook, pulley on a back leg, stake, tripwire

pul = leg_at(1, 1, 0.13)
PC = Vector((pul.x, pul.y - 0.0425 - 0.022, 0.125))  # pulley wheel center, hung off the leg's front face
add(tk.cylinder("PulleyWheel", 0.021, PC.x - 0.006, PC.x + 0.006, cam_metal, segments=16, center=(PC.y, PC.z),
                axis="X", bevel_width=0.002))
for sx in (-1, 1):
    add(plate("PulleyCheek", [(PC.x + sx * 0.009, PC.y - 0.024, PC.z - 0.02), (PC.x + sx * 0.009, PC.y + 0.024, PC.z - 0.02),
                              (PC.x + sx * 0.009, PC.y + 0.018, PC.z + 0.03), (PC.x + sx * 0.009, PC.y - 0.006, PC.z + 0.04)],
              (1.0, 0.0, 0.0), 0.003, rust))
add(tk.cylinder("PulleyAxle", 0.004, PC.x - 0.014, PC.x + 0.014, steel, segments=6, center=(PC.y, PC.z), axis="X"))
eye = tk.torus("ScrewEye", 0.01, 0.0025, (0.0, 0.0, 0.0), rust, 12, 6)
eye.matrix_world = Matrix.Translation((PC.x, PC.y + 0.012, PC.z + 0.05)) @ Matrix.Rotation(math.radians(90), 4, "Y")
add(bake_transform(eye))
add(tk.cylinder("ScrewShank", 0.003, PC.y + 0.02, pul.y - 0.03, rust, segments=6, center=(PC.x, PC.z + 0.05), axis="Y"))

STAKE_R = Vector((0.41, -0.455, 0.0))
STAKE_L = Vector((-0.43, -0.452, 0.0))
for c, lean in ((STAKE_R, (0.012, 0.004)), (STAKE_L, (-0.01, 0.006))):
    st = sweep("Stake", [c + Vector((0, 0, -0.03)), c + Vector((lean[0], lean[1], 0.14))], 0.022, 0.022, wood,
               up=(0.0, 1.0, 0.0), bevel_width=0.002)
    add(clip_floor(st))
    add(tk.cylinder("StakeNail", 0.0025, c.y - 0.02, c.y - 0.008, rust, segments=6,
                    center=(c.x + lean[0] * 0.7, 0.1), axis="Y"))
r_top = Vector((STAKE_R.x + 0.008, STAKE_R.y - 0.014, 0.1))
l_top = Vector((STAKE_L.x - 0.007, STAKE_L.y - 0.014, 0.1))
cord_pts = [(LX, 0.306, 0.505), (LX + 0.03, 0.31, 0.45), (PC.x, PC.y + 0.019, PC.z + 0.023),
            (PC.x, PC.y + 0.006, PC.z + 0.024), (PC.x, PC.y - 0.013, PC.z + 0.018), (PC.x, PC.y - 0.022, PC.z + 0.002),
            (PC.x, PC.y - 0.02, PC.z - 0.012), tuple(r_top + Vector((0.0, 0.02, 0.003))), tuple(r_top),
            tuple(r_top + Vector((-0.02, -0.002, 0.0))), (0.0, -0.468, 0.094), tuple(l_top + Vector((0.02, 0.0, 0.0))),
            tuple(l_top)]
add(tk.tube("TripCord", cord_pts, 0.0021, cord, resolution=1))
for c in (r_top, l_top):
    add(tk.torus("CordKnot", 0.013, 0.0035, (c.x - 0.003 if c.x > 0 else c.x + 0.003, c.y + 0.012, c.z), cord, 12, 6))

# ---------------------------------------------------------------- lashings: rope turns and duct tape


def loop_pts(y, x0, x1, h0, h1, r=0.006):
    """A rectangular loop with rounded corners round a stack, in the plane at y."""
    pts = []
    corners = ((x1, h1, 0), (x1, h0, -90), (x0, h0, 180), (x0, h1, 90))
    for (cx, ch, start), (sx, sh) in zip(corners, ((-1, -1), (-1, 1), (1, 1), (1, -1))):
        for k in range(3):
            a = math.radians(start - 45 * k)
            pts.append((cx + sx * r + r * math.cos(a), y + jitter(0.0015), ch + sh * r + r * math.sin(a)))
    pts.append(pts[0])
    pts.append((pts[1][0], pts[1][1] + 0.003, pts[1][2]))
    return pts


x0, x1 = BX - 0.0225 - 0.005, BX + 0.0225 + 0.036
for k, y in enumerate((YR - 0.004, YR + 0.006, YR + 0.016, YR + 0.026)):
    add(tk.tube("Lashing", loop_pts(y, x0 - 0.003 * (k % 2), x1 + 0.003 * (k % 2), BEAM_TOP - 0.09 - 0.006,
                                    HB + 0.018 + 0.002 * (k % 2)), 0.0065, rope, resolution=2))
add(tk.tube("LashingTail", [(x1 + 0.006, YR + 0.01, HB + 0.008), (x1 + 0.03, YR + 0.004, HB - 0.02),
                            (x1 + 0.038, YR - 0.01, HB - 0.075), (x1 + 0.03, YR - 0.016, HB - 0.1)], 0.0055, rope,
            resolution=2))
tape_pts = loop_pts(YR + 0.05, BX - 0.0225 - 0.002, BX + 0.0225 + 0.018, BEAM_TOP - 0.09 - 0.002, HB + 0.016)
add(sweep("Tape", tape_pts, 0.034, 0.0018, tape, up=(0.0, 1.0, 0.0), smooth_angle=60.0))
for xt in (-0.175, 0.19):  # tape wrapped round the riser where it cracked
    add(tk.cylinder("RiserTape", 0.0215, xt - 0.018, xt + 0.018, tape, segments=12, center=(riser_y(xt), HB),
                    axis="X", bevel_width=0.003))

# ---------------------------------------------------------------- spare arrows in a length of PVC pipe tied to a back leg

QB, QT = Vector((-0.395, 0.405, 0.0)), Vector((-0.372, 0.398, 0.42))
pipe = tk.cylinder("Quiver", 0.026, 0.0, (QT - QB).length, pvc, segments=16, caps=False)
add(along(pipe, QB, QT))
inner = tk.cylinder("QuiverInside", 0.0235, 0.004, (QT - QB).length - 0.002, pvc, segments=16, caps=False)
for p in inner.data.polygons:
    p.flip()
add(along(inner, QB, QT))
cap = tk.cylinder("QuiverCap", 0.029, 0.0, 0.03, pvc, segments=16, bevel_width=0.004)
add(along(cap, QB, QT))
qd = (QT - QB).normalized()
for k, lean in enumerate(((0.04, -0.015), (-0.012, 0.04), (0.05, 0.022))):
    # leaning on the pipe's rim, their points down at the bottom inside it
    d = (qd + Vector((lean[0], lean[1], 0.0))).normalized()
    top = QT + Vector((lean[0], lean[1], 0.0)) * 0.2 + d * 0.34
    for o in arrow(top, -d, "Spare%d" % k, cock=vane if k != 1 else vane_white,
                   hen=vane_white if k != 1 else vane, length=0.72):
        add(o)
legq = leg_at(-1, 1, 0.07)
add(tk.tube("QuiverTie", [
    (QB.x + 0.003, QB.y - 0.03, 0.06), (legq.x + 0.02, legq.y - 0.03, 0.07), (legq.x + 0.03, legq.y + 0.0, 0.072),
    (legq.x + 0.015, legq.y + 0.03, 0.074), (QB.x + 0.0, QB.y + 0.03, 0.064), (QB.x - 0.03, QB.y + 0.0, 0.06),
    (QB.x + 0.003, QB.y - 0.03, 0.06), (QB.x + 0.02, QB.y - 0.03, 0.058)], 0.004, rope, resolution=2))
add(along(tk.cylinder("QuiverTape", 0.0272, 0.25, 0.29, tape, segments=16, caps=False), QB, QT))

# ---------------------------------------------------------------- into the block, join

for o in parts:
    bake_transform(o)
    o.data.transform(Matrix.Translation((0.0, 0.0, Z)))

atlas = tk.triangulate(tk.join(parts, "TripBow"))
tk.smart_uvs(atlas)
xs_ = [v.co.x for v in atlas.data.vertices]
ys_ = [v.co.y for v in atlas.data.vertices]
zs_ = [v.co.z for v in atlas.data.vertices]
print("[trip_bow] bounds x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (min(xs_), max(xs_), min(ys_), max(ys_), min(zs_),
                                                                   max(zs_)))
arrow_origin = TIP + Vector((0.0, 0.0, Z))
arrow_aim = arrow_origin + Vector((0.0, -1.0, 0.0))

# ---------------------------------------------------------------- bake and export

paths = tk.bake_atlas(atlas, ASSETS, "TripBow_Atlas")
baked = tk.baked_material("TripBow_Atlas", paths)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

origin_pt = tk.point("ArrowOrigin", arrow_origin, model)
aim_pt = tk.point("ArrowAim", arrow_aim, model)
tk.export_fbx([model, origin_pt, aim_pt], os.path.join(ASSETS, "TripBow.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[trip_bow] triangles:", tris)
for pt in (origin_pt, aim_pt):
    print("[trip_bow]", pt.name, tuple(round(c, 4) for c in pt.matrix_world.translation))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.6, -2.0, 0.9), (0, -0.05, z(0.45)), lens=45), os.path.join(PREVIEWS, "trip_bow_front.png"))
tk.render(tk.camera("Back", (-1.6, 1.7, 1.1), (0, 0, z(0.45)), lens=45), os.path.join(PREVIEWS, "trip_bow_back.png"))
tk.render(tk.camera("Close", (0.62, -0.85, 0.42), (0.03, -0.12, z(0.64)), lens=45),
          os.path.join(PREVIEWS, "trip_bow_close.png"))
tk.icon(tk.camera("Icon", (1.9, -2.4, 1.7), (0, -0.05, z(0.45)), lens=62), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.45)))
print("[trip_bow] done")
