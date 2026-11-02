"""Tar (item icon only): a dented old gallon paint can, brim-full of shiny black tar oozing over the rim and running
down its sides, with a wire handle. Builds the can and renders only the inventory icon.

    blender -b --factory-startup --python tar_item.py -- <unity asset folder, unused> <preview folder, unused> <icon file>
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

from mathutils import Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ICON = args[2]

Z = -0.5
rnd = random.Random(77)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


def tilt(obj, axis, degrees, pivot):
    return tk.orbit(obj, 0.0, tilt=(axis, degrees, pivot))


def spline(points, per=4):
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


def loft(name, rings, material, segments=8):
    bm = bmesh.new()
    vs = []
    for c, u, v, ru, rv in rings:
        c, u, v = Vector(c), Vector(u), Vector(v)
        vs.append([bm.verts.new(c + u * (ru * math.cos(2 * math.pi * j / segments))
                                + v * (rv * math.sin(2 * math.pi * j / segments))) for j in range(segments)])
    for a, b in zip(vs, vs[1:]):
        for j in range(segments):
            bm.faces.new((a[j], a[(j + 1) % segments], b[(j + 1) % segments], b[j]))
    bm.faces.new(list(reversed(vs[0])))
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, material), 70)


DRIP = ((0.0, 0.6), (0.3, 0.5), (0.55, 0.58), (0.75, 0.82), (0.87, 0.97), (0.95, 0.82), (1.0, 0.3))


def drip(name, surface, length, width, material, flat=0.55):
    rings = []
    for t, f in DRIP:
        p, n = surface(t * length)
        n = Vector(n).normalized()
        u = n.cross(Vector((0.0, 0.0, 1.0))).normalized()
        r = width * f
        rings.append((Vector(p) + n * (r * flat * 0.3), u, n, r, r * flat))
    return loft(name, rings, material, segments=8)


def blob(name, center, radius, height, material, seed=0, rings=4, segments=24, wobble=0.25, stretch=(1.0, 1.0)):
    r = random.Random(seed)
    harm = [(k, r.uniform(0, 2 * math.pi), wobble * r.uniform(0.5, 1.0) / k ** 0.5) for k in (2, 3, 5, 7)]
    cx, cy, cz = center
    bm = bmesh.new()
    top = bm.verts.new((cx, cy, cz + height))
    vs = []
    for i in range(1, rings + 1):
        t = i / rings
        h = height * math.sqrt(max(0.0, 1.0 - t ** 4))
        ring = []
        for j in range(segments):
            a = 2 * math.pi * j / segments
            rr = radius * t * (1.0 + sum(amp * math.sin(k * a + ph) for k, ph, amp in harm))
            ring.append(bm.verts.new((cx + rr * math.cos(a) * stretch[0], cy + rr * math.sin(a) * stretch[1], cz + h)))
        vs.append(ring)
    for j in range(segments):
        bm.faces.new((top, vs[0][j], vs[0][(j + 1) % segments]))
    for a, b in zip(vs, vs[1:]):
        for j in range(segments):
            bm.faces.new((a[j], b[j], b[(j + 1) % segments], a[(j + 1) % segments]))
    bm.faces.new(list(reversed(vs[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, material), 60)


def wrap_on_can(obj, radius, facing_deg):
    """Bends flat lettering (built facing -Y at the can's front) around the can's surface."""
    obj.data.transform(obj.matrix_world)
    obj.matrix_world.identity()
    f = math.radians(facing_deg)
    for v in obj.data.vertices:
        x, y, h = v.co
        a = f + x / radius
        r = radius + (-radius - y)
        v.co = (r * math.cos(a), r * math.sin(a), h)
    return obj


def tar_material(name, dust=0.03):
    mat, g = tk.new_material(name)
    lumps = g.noise(60.0, detail=6.0, roughness=0.6, distortion=0.4)
    wet = g.ramp(g.noise(9.0, detail=4.0), 0.4, 0.6)
    col = g.mix(g.math("MULTIPLY", lumps, 0.7), (0.004, 0.0037, 0.0034), (0.018, 0.016, 0.014))
    rough = g.mixf(wet, 0.14, 0.035)
    col, rough, metal = tk._grit(g, col, rough, 0.0, dust)
    return tk.finish(mat, g, col, metal, rough, g.bump(lumps, 0.2, 0.002))


def frame_icon(cam, objs, target, direction, fill=0.9):
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

tin = tk.photo_material("Tin", "metal_plate_02", scale=3.5, value=2.0, sat=0.45, chip=1.0, grime=0.7, streaks=0.8,
                        patches=0.4, metal_floor=0.6, rough_scale=0.75, grit=1.0, scratches=0.6, edges=0.8,
                        contrast=0.12)
paper = tk.grimy("Label", (0.66, 0.56, 0.36), roughness=0.75, grime=0.7, grime_set="rust_coarse_01", scale=2.6,
                 grit=1.0, stain=(0.5, 0.37, 0.2), dirt_range=(0.22, 0.07))
stripe = tk.grimy("LabelStripe", (0.45, 0.08, 0.03), roughness=0.7, grime=0.8, grime_set="rust_coarse_01", scale=2.6,
                  grit=0.8, dirt_range=(0.1, 0.03))
ink = tk.grimy("Ink", (0.03, 0.03, 0.03), roughness=0.6, grime=0.3)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=4.0, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
wood = tk.photo_material("Wood", "weathered_planks", scale=2.0, value=1.1, exposed=None, grime=0.8, bump=0.5,
                         grit=0.6, contrast=0.2)
tar = tar_material("Tar")

parts = []
add = parts.append

R, H = 0.083, 0.185
body = tk.cylinder("Can", R, z(0.004), z(H), tin, segments=48, rings=8)
add(tk.dent(body, 0.0035, 0.045, seed=3))
# a big dent knocked into the side
for v in body.data.vertices:
    a = math.atan2(v.co.y, v.co.x)
    d = math.exp(-((a - math.radians(-25)) / 0.35) ** 2 - ((v.co.z - z(0.07)) / 0.04) ** 2)
    r = math.hypot(v.co.x, v.co.y)
    if r > 0.05:
        s = (r - 0.009 * d) / r
        v.co.x *= s
        v.co.y *= s
add(tk.torus("TopChime", R + 0.001, 0.0045, (0.0, 0.0, z(H)), tin, 48, 8))
add(tk.torus("BottomChime", R + 0.001, 0.0045, (0.0, 0.0, z(0.0045)), tin, 48, 8))
add(tk.cylinder("Bead", R + 0.0015, z(0.155), z(0.159), tin, segments=48))

# Faded paper label, half torn off, a hand-lettered TAR on it
lab = tk.cylinder("Label", R + 0.0008, z(0.04), z(0.142), paper, segments=48, caps=False, radius_top=R + 0.0008)
bm = bmesh.new()
bm.from_mesh(lab.data)
torn = [f for f in bm.faces if -0.2 < math.atan2(f.calc_center_median().y, f.calc_center_median().x) < 1.9]
bmesh.ops.delete(bm, geom=torn, context="FACES")
bm.to_mesh(lab.data)
bm.free()
add(lab)
band = tk.cylinder("Stripe", R + 0.0012, z(0.118), z(0.132), stripe, segments=48, caps=False)
bm = bmesh.new()
bm.from_mesh(band.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if -0.2 < math.atan2(f.calc_center_median().y,
                                                                    f.calc_center_median().x) < 1.9], context="FACES")
bm.to_mesh(band.data)
bm.free()
add(band)
word = tk.text_mesh("Word", "TAR", 0.05, ink, (0.0, -R - 0.0016, z(0.075)), extrude=0.0004)
add(wrap_on_can(word, R + 0.0016, -72))

# Tar heaped in the can, welling over the rim and running down
top = blob("TarTop", (0.0, 0.0, z(H - 0.002)), R + 0.002, 0.02, tar, seed=5, rings=5, segments=40, wobble=0.04)
add(tk.dent(top, 0.004, 0.025, seed=6))
for k, (a0, sweep) in enumerate(((-150, 55), (-80, 40), (-28, 32), (25, 30), (95, 50))):
    s, w = math.radians(a0), math.radians(sweep)
    add(tk.torus("Overflow", R + 0.004, 0.012, (0.0, 0.0, z(H + 0.002)), tar, 14, 10, sweep=w, start=s,
                 minor_fn=lambda a, s=s, w=w: 0.003 + 0.0095 * max(0.0, math.sin(math.pi * (a - s) / w)) ** 0.6))


def on_can(a):
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    return lambda d: ((R * ca, R * sa, z(H - d)), (ca, sa, 0.0))


runs = ((-140, 0.17, 0.012), (-122, 0.07, 0.01), (-70, 0.13, 0.013), (-58, 0.05, 0.009), (-20, 0.178, 0.014),
        (-8, 0.09, 0.01), (30, 0.06, 0.011), (40, 0.15, 0.012), (105, 0.11, 0.012), (125, 0.04, 0.01),
        (160, 0.14, 0.012), (-165, 0.08, 0.01))
for a, length, width in runs:
    add(drip("TarRun", on_can(a + jitter(3)), length, width, tar))
add(blob("Puddle", (0.035, -0.07, z(0.0005)), 0.06, 0.006, tar, seed=9, stretch=(1.5, 1.0), wobble=0.3))

# Wire handle standing up, tipped back a little, with a wooden grip
for sx in (-1, 1):
    add(tk.cylinder("Ear", 0.011, R - 0.002, R + 0.004, tin, segments=12, center=(0.0, z(0.165)), axis="X"))
    parts[-1].location.x = 0.0 if sx > 0 else -2 * R - 0.002
    add(tk.cylinder("EarRivet", 0.004, R + 0.004, R + 0.008, rust, segments=8, center=(0.0, z(0.165)), axis="X"))
    parts[-1].location.x = 0.0 if sx > 0 else -2 * R - 0.012
bail = []
for k in range(25):
    th = math.radians(7.5 * k)
    bail.append((-(R + 0.009) * math.cos(th), 0.0, z(0.165) + 0.115 * math.sin(th)))
wire = tk.tube("Bail", spline(bail, per=1), 0.0022, rust, resolution=2)
grip = tk.cylinder("Grip", 0.009, -0.032, 0.032, wood, segments=12, center=(0.0, z(0.165) + 0.115), axis="X",
                   bevel_width=0.003)
for o in (wire, grip):
    add(tilt(o, "X", -24.0, (0.0, 0.0, z(0.165))))
add(blob("GripSplat", (0.0, 0.0, 0.0), 0.006, 0.002, tar, seed=12, segments=10, rings=2))
tilt(parts[-1], "X", 66.0, (0.0, 0.0, 0.0))
parts[-1].location = (0.008, 0.115 * math.sin(math.radians(24)) + 0.004, z(0.165) + 0.115 * math.cos(math.radians(24)))

can = tk.join(parts, "TarCan")
print("[tar_item] triangles:", sum(len(p.vertices) - 2 for p in can.data.polygons))

d = Vector((1.3, -2.6, 1.55))
cam = tk.camera("Icon", tuple(Vector((0, 0, z(0.12))) + d), (0, 0, z(0.12)), lens=70)
frame_icon(cam, [can], (0, 0, z(0.12)), d, fill=0.9)
tk.icon(cam, ICON, hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.12)))
print("[tar_item] done")
