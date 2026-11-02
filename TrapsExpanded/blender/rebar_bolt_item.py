"""Rebar Bolt (item icon only): three bolts for the Bolt Thrower, bundled with duct tape. Each is a 0.6 m length of
rebar ground to a point, with three vanes cut from plastic bottles taped on at the back. Builds the bundle and renders
only the inventory icon.

    blender -b --factory-startup --python rebar_bolt_item.py -- <unity asset folder, unused> <preview folder, unused> <icon file>
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

from mathutils import Euler, Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ICON = args[2]

rnd = random.Random(61)


def jitter(amount):
    return rnd.uniform(-amount, amount)


def tilt(obj, axis, degrees, pivot):
    return tk.orbit(obj, 0.0, tilt=(axis, degrees, pivot))


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

rust = tk.photo_material("Rebar", "rust_coarse_01", scale=4.0, value=1.15, exposed=None, grime=0.6, metal_floor=0.35,
                         grit=0.7)
ground = tk.photo_material("Ground", "metal_plate_02", scale=4.0, value=1.6, sat=0.4, exposed=None, grime=0.3,
                           metal_floor=0.8, rough_scale=0.6, grit=0.3, scratches=0.8)
green = tk.grimy("BottleGreen", (0.06, 0.24, 0.11), roughness=0.22, grime=0.5, grit=0.5, dirt_range=(0.1, 0.03))
blue = tk.grimy("BottleBlue", (0.1, 0.22, 0.38), roughness=0.22, grime=0.5, grit=0.5, dirt_range=(0.1, 0.03))
duct = tk.grimy("DuctTape", (0.42, 0.42, 0.43), roughness=0.45, metallic=0.3, grime=0.6, bump_scale=45.0, bump=0.12,
                grit=0.6)

# Three bolts taped together in the middle, fanned a little so they read as a sheaf, staggered so their vanes clear
# each other; built along Y around the origin
YB = -0.06  # the binding
parts = []
for (x, h, dy, spin, fan, plastic) in ((0.0, -0.0105, 0.0, 0.0, 4.5, green), (0.0, 0.0105, 0.075, 40.0, -4.5, blue),
                                        (0.017, 0.0, -0.07, 80.0, 0.0, green)):
    for o in rebar_bolt((x, 0.3 + dy, h), rust, ground, plastic, duct, spin=spin):
        parts.append(tilt(o, "X", fan, (0.0, YB, 0.0)))
band = tk.cylinder("Binding", 0.0225, YB - 0.026, YB + 0.026, duct, segments=16, center=(0.006, 0.0), axis="Y",
                   rings=2)
parts.append(tk.dent(band, 0.0018, 0.012, seed=3))
tail = tk.box("TapeTail", (0.032, 0.034, 0.0012), (0.03, YB + 0.004, -0.024), duct)
parts.append(tilt(tilt(tail, "X", 30.0, (0.0, YB, -0.015)), "Y", -25.0, (0.0, YB, 0.0)))

bundle = tk.join(parts, "RebarBolts")
print("[rebar_bolt_item] triangles:", sum(len(p.vertices) - 2 for p in bundle.data.polygons))
# Lay it across the icon: points up and to the right, like the vanilla arrow icons
bundle.location = (0.0, 0.0, -0.2)
bundle.rotation_mode = "ZYX"
bundle.rotation_euler = Euler((math.radians(-8.0), math.radians(-38.0), math.radians(90.0)), "ZYX")
bpy.context.view_layer.update()

d = Vector((0.5, -2.6, 1.0))
cam = tk.camera("Icon", tuple(d), (0, 0, -0.2), lens=70)
frame_icon(cam, [bundle], (0, 0, -0.2), d, fill=0.94)
tk.icon(cam, ICON, hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, -0.2))
print("[rebar_bolt_item] done")
