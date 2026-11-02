"""Tar Sprayer: a 1x1x1 block, powered. An old two-wheel hand truck standing upright with a 5-gallon bucket of tar
bungeed onto its nose plate, a little airless-sprayer pump (motor over a pump head) hung off its left rail with the
suction tube dipped in the tar, a car battery on the ground with jumper cables up to a junction box (with the power
lamp), and an airless paint-sprayer gun on a swivel post at the top, aimed at the front (-Y). Tar crusted and dripping
over everything.

The gun and its mount are the moving part "Swivel", turning about the post's vertical axis; the point "Muzzle" at the
gun's nozzle tip rides on it.

    blender -b --factory-startup --python tar_sprayer.py -- <unity asset folder> <preview folder> <icon file>
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
rnd = random.Random(1313)


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


def bar(name, a, b, size, material, bevel_width=0.0):
    """A rectangular bar (size = (w, t)) from a to b."""
    a, b = Vector(a), Vector(b)
    obj = tk.box(name, (size[0], size[1], (b - a).length), (0.0, 0.0, (b - a).length / 2), material, bevel_width)
    return along(obj, a, b - a)


def nut(name, x, y, h, material, radius=0.008, height=0.008, axis="Z"):
    """A plain hex nut or bolt head (no bevel, to keep the count down)."""
    if axis == "Z":
        return tk.cylinder(name, radius, h, h + height, material, segments=6, center=(x, y))
    if axis == "Y":
        return tk.cylinder(name, radius, y, y + height, material, segments=6, center=(x, h), axis="Y")
    return tk.cylinder(name, radius, x, x + height, material, segments=6, center=(y, h), axis="X")


def tilt(obj, axis, degrees, pivot):
    return tk.orbit(obj, 0.0, tilt=(axis, degrees, pivot))


def spline(points, per=4):
    """Catmull-Rom through the points, for hoses and cables that bend smoothly."""
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
    """A closed tube through elliptical rings (center, u, v, ru, rv)."""
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


DRIP = ((0.0, 0.7), (0.25, 0.5), (0.5, 0.55), (0.72, 0.8), (0.86, 0.95), (0.95, 0.8), (1.0, 0.3))
HANG = ((0.0, 0.9), (0.35, 0.6), (0.7, 0.62), (0.88, 0.8), (0.96, 0.6), (1.0, 0.2))


def drip(name, surface, length, width, material, flat=0.38, profile=DRIP):
    """A run of tar down a surface: surface(d) gives the surface point d below the top and its outward normal."""
    rings = []
    for t, f in profile:
        p, n = surface(t * length)
        n = Vector(n).normalized()
        u = n.cross(Vector((0.0, 0.0, 1.0))).normalized()
        r = width * f
        rings.append((Vector(p) + n * (r * flat * 0.3), u, n, r, r * flat))
    return loft(name, rings, material, segments=6)


def hanging_drip(name, top, length, width, material):
    """A drop of tar hanging straight down from `top`."""
    rings = [((top[0], top[1], top[2] - t * length), (1, 0, 0), (0, 1, 0), width * f, width * f) for t, f in HANG]
    return loft(name, rings, material, segments=6)


def blob(name, center, radius, height, material, seed=0, rings=3, segments=16, wobble=0.25, stretch=(1.0, 1.0),
         angle=0.0):
    """A puddle or splat: an irregular flat dome sitting on z = center.z."""
    r = random.Random(seed)
    harm = [(k, r.uniform(0, 2 * math.pi), wobble * r.uniform(0.5, 1.0) / k ** 0.5) for k in (2, 3, 5, 7)]
    ca, sa = math.cos(angle), math.sin(angle)
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
            x, y = rr * math.cos(a) * stretch[0], rr * math.sin(a) * stretch[1]
            ring.append(bm.verts.new((cx + x * ca - y * sa, cy + x * sa + y * ca, cz + h)))
        vs.append(ring)
    for j in range(segments):
        bm.faces.new((top, vs[0][j], vs[0][(j + 1) % segments]))
    for a, b in zip(vs, vs[1:]):
        for j in range(segments):
            bm.faces.new((a[j], b[j], b[(j + 1) % segments], a[(j + 1) % segments]))
    bm.faces.new(list(reversed(vs[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, material), 60)


def flat_text(name, body, size, material, location, rotation=(90.0, 0.0, 0.0), font="C:/Windows/Fonts/impact.ttf"):
    """Painted lettering as a single flat, low-resolution face (cheaper than tk.text_mesh)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.resolution_u = 2
    cu.fill_mode = "FRONT"
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    if font and os.path.exists(font):
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
    obj.data.materials.append(material)
    return obj


def stretched_noise(g, scale, offset=(0.0, 0.0, 0.0), detail=3.0):
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Location"].default_value = offset
    return g.noise(1.0, detail=detail, roughness=0.5, vector=m.outputs[0])


def tar_layer(g, color, rough, metal, amount, top=None, seed=0.0):
    """Splashes, specks and (below `top`, model space) runs of black tar over a finished surface."""
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Location"].default_value = (seed * 1.3, seed * 0.7, seed * 2.1)
    blot = g.noise(7.0, detail=7.0, roughness=0.7, distortion=0.9, vector=m.outputs[0])
    mask = g.ramp(blot, 0.71 - 0.14 * amount, 0.73 - 0.14 * amount)
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 38.0)
    g.links.new(m.outputs[0], vor.inputs["Vector"])
    spots = g.ramp(tk._sock(vor.outputs, "Distance"), 0.05 + 0.1 * amount, 0.02 + 0.05 * amount)
    spots = g.math("MULTIPLY", spots, g.ramp(g.noise(5.0, detail=3.0), 0.42, 0.58))
    mask = g.math("MAXIMUM", mask, spots)
    if top is not None:
        zc = g.separate(g.coords())[2]
        runs = stretched_noise(g, (26.0, 26.0, 1.3), (seed, 0.3, 0.0))
        near = g.ramp(zc, top - 0.22, top)
        mask = g.math("MAXIMUM", mask, g.ramp(g.math("ADD", runs, g.math("MULTIPLY", near, 0.38)), 0.82, 0.84))
        mask = g.math("MAXIMUM", mask, g.ramp(zc, top - 0.05, top - 0.025))
    lumps = g.noise(45.0, detail=5.0)
    tar_col = g.mix(g.math("MULTIPLY", lumps, 0.6), (0.009, 0.008, 0.007), (0.032, 0.028, 0.024))
    color = g.mix(mask, color, tar_col)
    rough = g.mixf(mask, rough, g.math("ADD", 0.3, g.math("MULTIPLY", lumps, 0.3)))
    metal = g.mixf(mask, metal, 0.0)
    return color, rough, metal, mask


def photo_tar(name, base, scale=0.5, sat=1.0, value=1.0, tint=None, exposed="rust_coarse_01", chip=0.5, grime=0.6,
              streaks=0.0, offset=(0.0, 0.0, 0.0), bump=0.35, ao=0.6, patches=0.0, metal_floor=0.0, rough_scale=1.0,
              grit=0.0, scratches=0.0, edges=0.0, contrast=0.0, tar=0.0, tar_top=None, seed=0.0):
    """tk.photo_material with a layer of tar splashes and runs on top."""
    mat, g = tk.new_material(name)
    p = tk.photo(g, base, scale, offset)
    color = tk.grade(g, p["color"], sat, value, tint)
    if contrast:
        bc = g.node("ShaderNodeBrightContrast")
        g._in(bc, "Color", color)
        g._in(bc, "Contrast", contrast)
        color = bc.outputs[0]
    rough = p["rough"]
    metal = g.math("MULTIPLY", p["metal"], 1.0)
    height = p["height"]
    if exposed:
        e = tk.photo(g, exposed, scale * 1.3, (0.37, 0.11, 0.73))
        edge = g.edges(0.006)
        chips = g.noise(22.0, detail=6.0, roughness=0.7)
        lo = 0.22 - 0.1 * chip
        mask = g.ramp(g.math("MULTIPLY", edge, g.math("ADD", chips, 0.35)), lo, lo + 0.12)
        if patches:
            blotch = g.noise(2.5, detail=8.0, roughness=0.65, distortion=0.4)
            pm = g.ramp(blotch, 0.66 - 0.16 * patches, 0.7 - 0.16 * patches)
            pm = g.math("MAXIMUM", pm, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.05), clamp=True),
                                              patches * 1.5, clamp=True))
            mask = g.math("MAXIMUM", mask, pm)
        color = g.mix(mask, color, e["color"])
        rough = g.mixf(mask, rough, e["rough"])
        metal = g.mixf(mask, metal, e["metal"])
        height = g.mixf(mask, height, g.math("MULTIPLY", e["height"], 0.5))
    dirt = tk._grime(g, grime)
    color = g.mix(dirt, color, (0.035, 0.028, 0.02))
    rough = g.mixf(dirt, rough, 0.85)
    if streaks:
        color = g.mix(tk._streaks(g, streaks), color, (0.2, 0.1, 0.05))
    color = tk._multiply_color(g, color, g.mix(ao, (1.0, 1.0, 1.0), p["ao"]))
    if metal_floor:
        metal = g.math("MAXIMUM", metal, g.math("MULTIPLY", metal_floor, g.math("SUBTRACT", 1.0, dirt, clamp=True)))
    if rough_scale != 1.0:
        rough = g.math("MULTIPLY", rough, rough_scale, clamp=True)
    color, rough, metal = tk._grit(g, color, rough, metal, grit, scratches, edges)
    if tar:
        color, rough, metal, tmask = tar_layer(g, color, rough, metal, tar, tar_top, seed)
        height = g.math("ADD", height, g.math("MULTIPLY", tmask, 0.5))
    return tk.finish(mat, g, color, metal, rough, g.bump(height, bump, 0.01))


def grimy_tar(name, color, roughness=0.55, metallic=0.0, grime=0.5, grime_set="metal_plate_02", scale=0.7,
              bump_scale=60.0, bump=0.08, stain=None, grit=0.0, dirt_range=(0.4, 0.12), tar=0.0, tar_top=None,
              seed=0.0):
    """tk.grimy with a layer of tar splashes and runs on top."""
    mat, g = tk.new_material(name)
    p = tk.photo(g, grime_set, scale, (0.21, 0.5, 0.13))
    pattern = g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1])
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", pattern, grime), tk._grime(g, grime * 1.4), clamp=True)
    col = g.mix(g.math("MULTIPLY", g.noise(18.0), 0.25), color, tk._darker(g, color, 0.8))
    if stain is not None:
        col = g.mix(g.ramp(g.noise(3.0, detail=6.0, distortion=0.5), 0.45, 0.75), col, stain)
    col = g.mix(dirt, col, (0.06, 0.05, 0.04))
    rough = g.mixf(dirt, roughness, 0.85)
    col, rough, metal = tk._grit(g, col, rough, metallic, grit)
    height = g.noise(bump_scale, detail=6.0)
    if tar:
        col, rough, metal, tmask = tar_layer(g, col, rough, metal, tar, tar_top, seed)
        height = g.math("ADD", g.math("MULTIPLY", height, 0.3), g.math("MULTIPLY", tmask, 0.6))
        bump = max(bump, 0.3)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, bump, 0.003))


def tar_material(name, dust=0.05):
    """Black tar: lumpy and wrinkled, dull where it has skinned over into a crust, glossy in a few fresh patches."""
    mat, g = tk.new_material(name)
    lumps = g.noise(26.0, detail=6.0, roughness=0.6, distortion=0.6)
    wrinkles = g.noise(90.0, detail=4.0, roughness=0.7, distortion=1.2)
    fresh = g.ramp(g.noise(4.0, detail=4.0), 0.6, 0.68)
    col = g.mix(g.math("MULTIPLY", lumps, 0.7), (0.006, 0.0055, 0.005), (0.026, 0.023, 0.02))
    rough = g.mixf(fresh, g.math("ADD", 0.72, g.math("MULTIPLY", wrinkles, 0.15)), 0.08)
    col, rough, metal = tk._grit(g, col, rough, 0.0, dust)
    height = g.math("ADD", lumps, g.math("MULTIPLY", wrinkles, 0.35))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.004))


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

truck_red = photo_tar("TruckPaint", "rusty_painted_metal", scale=1.8, sat=0.8, value=1.05, chip=1.0, grime=0.9,
                      streaks=1.2, patches=0.7, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.6, edges=0.9,
                      contrast=0.12, tar=0.3, seed=1.0)
nose_red = photo_tar("NosePaint", "rusty_painted_metal", scale=1.8, sat=0.7, value=0.95, chip=1.0, grime=1.0,
                     patches=0.9, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.6, edges=0.9, contrast=0.12,
                     tar=0.85, seed=2.0)
plate = photo_tar("Plate", "metal_plate_02", scale=1.9, value=1.2, exposed=None, grime=0.7, streaks=0.5,
                  metal_floor=0.55, rough_scale=0.85, grit=0.9, scratches=0.45, edges=0.6, contrast=0.12, tar=0.35,
                  seed=3.0)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
alu = photo_tar("PumpHead", "metal_plate_02", scale=2.4, value=1.45, sat=0.6, exposed=None, grime=0.9,
                metal_floor=0.6, rough_scale=0.8, grit=1.0, scratches=0.6, edges=0.7, contrast=0.1, tar=0.55,
                seed=4.0)
motor_paint = photo_tar("MotorPaint", "green_metal_rust", scale=1.7, sat=0.55, value=1.05, chip=1.0, grime=0.9,
                        streaks=1.0, patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.5,
                        edges=0.8, contrast=0.12, tar=0.3, seed=5.0)
box_grey = tk.photo_material("BoxPaint", "green_metal_rust", scale=1.8, sat=0.18, value=1.25, chip=1.0, grime=0.9,
                             streaks=1.2, patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55,
                             edges=0.8, contrast=0.12)
bucket = grimy_tar("BucketPlastic", (0.62, 0.59, 0.52), roughness=0.55, grime=0.7, stain=(0.47, 0.43, 0.34), grit=0.9,
                   dirt_range=(0.22, 0.07), tar=0.3, tar_top=z(0.33), seed=6.0)
tar = tar_material("Tar")
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
tire = tk.grimy("Tire", (0.03, 0.03, 0.03), roughness=0.85, grime=0.9, grit=1.0, bump_scale=140.0, bump=0.2)
hose = grimy_tar("Hose", (0.03, 0.035, 0.045), roughness=0.5, grime=0.7, grit=0.8, tar=0.5, seed=7.0)
tape = tk.grimy("Tape", (0.02, 0.02, 0.022), roughness=0.42, grime=0.25, bump_scale=35.0)
battery_case = grimy_tar("BatteryCase", (0.035, 0.035, 0.037), roughness=0.5, grime=0.7, grit=1.0, tar=0.2, seed=8.0)
label = tk.grimy("Label", (0.62, 0.42, 0.05), roughness=0.6, grime=0.8, grime_set="rust_coarse_01", scale=1.4,
                 grit=0.6, dirt_range=(0.1, 0.03))
ink = tk.grimy("Ink", (0.03, 0.03, 0.03), roughness=0.6, grime=0.3)
lead = tk.grimy("Lead", (0.34, 0.34, 0.35), roughness=0.45, metallic=0.6, grime=0.6, stain=(0.55, 0.58, 0.5), grit=0.5)
red_plastic = tk.grimy("RedPlastic", (0.42, 0.03, 0.02), roughness=0.45, grime=0.6, grit=0.8, dirt_range=(0.1, 0.03))
copper = tk.tarnished_copper("Copper")
bungee_red = tk.grimy("BungeeRed", (0.38, 0.05, 0.03), roughness=0.7, grime=0.8, grit=0.8, bump_scale=200.0,
                      bump=0.2, dirt_range=(0.1, 0.03))
cord = tk.grimy("Cord", (0.32, 0.31, 0.28), roughness=0.6, grime=0.8, grit=0.8)
gun_blue = grimy_tar("GunPlastic", (0.03, 0.075, 0.22), roughness=0.42, grime=0.6, grit=0.8, dirt_range=(0.1, 0.03),
                     tar=0.4, seed=9.0)
gun_metal = photo_tar("GunMetal", "metal_plate_02", scale=2.6, value=1.35, sat=0.7, exposed=None, grime=0.8,
                      metal_floor=0.6, rough_scale=0.75, grit=0.8, scratches=0.6, edges=0.8, contrast=0.1, tar=0.5,
                      seed=10.0)
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append
swivel = []

# ---------------------------------------------------------------- hand truck

RX, RY = 0.19, 0.15  # rails
left = [(-RX, RY, z(0.012)), (-RX + jitter(0.004), RY, z(0.33)), (-RX, RY, z(0.64)), (-RX, RY + 0.012, z(0.71)),
        (-RX + 0.005, RY + 0.04, z(0.76)), (-RX + 0.025, RY + 0.065, z(0.79)), (-0.12, RY + 0.075, z(0.8))]
right = [(-x + jitter(0.003), y, h) for x, y, h in reversed(left)]
add(tk.tube("Frame", spline(left + right, per=2), 0.0135, truck_red, resolution=2))
for sx in (-1, 1):
    add(tk.cylinder("GripTape", 0.0165, 0.07 * sx - 0.03, 0.07 * sx + 0.03, tape, segments=10,
                    center=(RY + 0.075, z(0.8)), axis="X"))
for h in (0.22, 0.47, 0.66):
    cb = tk.box("Crossbar", (2 * RX + 0.012, 0.012, 0.026), (0.0, RY + 0.014, z(h)), truck_red, 0.003)
    add(tilt(cb, "Y", jitter(1.5), (0.0, RY, z(h))))
nose = tk.box("NosePlate", (0.4, 0.32, 0.012), (0.0, -0.005, z(0.006)), nose_red, 0.003)
add(tk.dent(nose, 0.002, 0.08, seed=1))
add(tk.box("NoseBack", (0.4, 0.01, 0.06), (0.0, RY + 0.004, z(0.035)), nose_red))
for sx in (-1, 1):
    add(bar("Gusset", (0.15 * sx, RY - 0.002, z(0.07)), (0.15 * sx, RY - 0.09, z(0.012)), (0.008, 0.03), nose_red))

# Axle, struts and wheels behind the frame
AY, AH, WX = 0.255, 0.102, 0.265
add(tk.cylinder("Axle", 0.012, -0.245, 0.245, rust, segments=8, center=(AY, z(AH)), axis="X"))
for sx in (-1, 1):
    add(bar("Strut", (RX * sx, RY + 0.01, z(0.03)), (0.215 * sx, AY, z(AH)), (0.026, 0.01), truck_red))
    add(bar("Strut", (RX * sx, RY + 0.01, z(0.27)), (0.215 * sx, AY, z(AH)), (0.026, 0.01), truck_red))
    c = (WX * sx, AY, z(AH))
    t = tk.torus("Tire", 0.072, 0.03, c, tire, 24, 8)
    tilt(t, "Y", 90, c)
    add(tk.dent(tilt(t, "X", jitter(20), c), 0.004, 0.05, seed=2 + sx))
    add(tk.cylinder("Hub", 0.05, WX * sx - 0.025, WX * sx + 0.025, rust, segments=16, center=(AY, z(AH)), axis="X"))
    add(tk.cylinder("HubCap", 0.022, WX * sx - 0.033, WX * sx + 0.033, plate, segments=10, center=(AY, z(AH)),
                    axis="X"))

# ---------------------------------------------------------------- the tar bucket

BX, BY = 0.0, -0.02
B0, B1, BTOP = 0.014, 0.375, 0.39


def brad(h):
    return 0.137 + 0.015 * (h - B0) / (BTOP - B0)


def on_bucket(a, h0):
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    return lambda d: ((BX + brad(h0 - d) * ca, BY + brad(h0 - d) * sa, z(h0 - d)), (ca, sa, 0.0))


body = tk.cylinder("Bucket", 0.137, z(B0), z(B1), bucket, segments=32, center=(BX, BY), rings=4,
                   radius_top=brad(B1))
add(tk.dent(body, 0.004, 0.1, seed=3))
for h in (0.27,):
    add(tk.cylinder("BucketHoop", brad(h) + 0.004, z(h), z(h + 0.012), bucket, segments=32, center=(BX, BY)))
add(tk.cylinder("BucketFoot", 0.139, z(0.012), z(0.03), bucket, segments=32, center=(BX, BY)))
add(tk.torus("BucketLip", brad(0.378) + 0.002, 0.009, (BX, BY, z(0.378)), bucket, 36, 6))
top = blob("TarTop", (BX, BY, z(0.376)), brad(0.376) - 0.003, 0.012, tar, seed=4, rings=4, segments=28, wobble=0.0)
add(tk.dent(top, 0.006, 0.03, seed=5))

# Tar welling over the rim, caked in a crust under it and running down
for k, (a0, sweep) in enumerate(((128, 72), (212, 66), (290, 58), (0, 52), (60, 44))):
    s, w = math.radians(a0 + jitter(4)), math.radians(sweep)
    add(tk.torus("Overflow", brad(0.38) + 0.004, 0.011, (BX, BY, z(0.378)), tar, 14, 6, sweep=w, start=s,
                 minor_fn=lambda a, s=s, w=w: 0.0045 + 0.006 * max(0.0, math.sin(math.pi * (a - s) / w)) ** 0.4))


def band_bottom(a):
    return 0.322 + 0.014 * math.sin(3 * a + 0.7) + 0.009 * math.sin(7 * a + 2.1) + 0.005 * math.sin(13 * a)


def band_thick(a):
    return 0.0045 + 0.0018 * math.sin(5 * a + 1.3) + 0.0012 * math.sin(11 * a + 0.4)


bm = bmesh.new()
SEG, LEV = 40, 4
rings = []
for i in range(LEV + 1):
    t = i / LEV
    ring = []
    for j in range(SEG):
        a = 2 * math.pi * j / SEG
        h = 0.379 + (band_bottom(a) - 0.379) * t
        r = brad(h) + band_thick(a) * (1.0 - 0.75 * t ** 3)
        ring.append(bm.verts.new((BX + r * math.cos(a), BY + r * math.sin(a), z(h))))
    rings.append(ring)
ring = []
for j in range(SEG):
    a = 2 * math.pi * j / SEG
    r = brad(band_bottom(a)) - 0.002
    ring.append(bm.verts.new((BX + r * math.cos(a), BY + r * math.sin(a), z(band_bottom(a)))))
rings.append(ring)
for ra, rb in zip(rings, rings[1:]):
    for j in range(SEG):
        k = (j + 1) % SEG
        bm.faces.new((ra[j], rb[j], rb[k], ra[k]))
band = tk.smooth(tk.mesh_object("Crust", bm, tar), 60)
add(tk.dent(band, 0.0025, 0.03, seed=7))
runs = ((158, 0.25, 0.026), (208, 0.29, 0.032), (226, 0.1, 0.022), (262, 0.31, 0.034), (300, 0.18, 0.028),
        (318, 0.3, 0.026), (356, 0.12, 0.024), (42, 0.19, 0.026), (92, 0.08, 0.022))
for k, (a, length, width) in enumerate(runs):
    a += jitter(3)
    h0 = band_bottom(math.radians(a)) + 0.012
    length = min(length, h0 - 0.03)
    add(drip("TarRun", on_bucket(a, h0), length, width, tar, flat=0.32))
    if length > h0 - 0.07:  # long runs pool on the nose plate
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        add(blob("TarPool", (BX + 0.152 * ca, BY + 0.152 * sa, z(0.012)), 0.036, 0.007, tar, seed=10 + k,
                 segments=12, rings=2, wobble=0.3))

# Wire bail handle flopped down over the front, with its plastic grip
for sx in (-1, 1):
    add(tk.box("BailEar", (0.012, 0.03, 0.035), (BX + (brad(0.345) + 0.003) * sx, BY, z(0.345)), bucket))
PHI = math.radians(32)
bail = []
for k in range(13):
    th = math.radians(15 * k)
    bail.append((BX + 0.158 * math.cos(th), BY - 0.18 * math.sin(th) * math.cos(PHI),
                 z(0.345) - 0.18 * math.sin(th) * math.sin(PHI)))
add(tk.tube("Bail", bail, 0.0028, rust, resolution=1))
add(tk.cylinder("BailGrip", 0.0095, -0.035, 0.035, bucket, segments=8, center=(bail[6][1] - 0.007, bail[6][2]),
                axis="X"))

# A bungee cord around the bucket, hooked on the rails
h = 0.17
R = brad(h) + 0.009
pts = [(-RX - 0.006, RY + 0.012, z(h + 0.012)), (-RX + 0.02, RY - 0.03, z(h + 0.004))]
pts += [(BX + R * math.cos(math.radians(a)), BY + R * math.sin(math.radians(a)), z(h)) for a in range(150, 391, 20)]
pts += [(RX - 0.02, RY - 0.03, z(h + 0.004)), (RX + 0.006, RY + 0.012, z(h + 0.012))]
add(tk.tube("Bungee", pts, 0.006, bungee_red, resolution=1))
for sx in (-1, 1):
    add(tk.tube("BungeeHook", [(RX * sx + 0.006 * sx, RY + 0.012, z(h + 0.012)),
                               (RX * sx + 0.02 * sx, RY + 0.02, z(h + 0.03)),
                               (RX * sx + 0.012 * sx, RY + 0.032, z(h + 0.045))], 0.0025, plate, resolution=1))

# Tar puddles on the ground in front and splats on the nose plate
add(blob("Puddle", (0.0, -0.25, z(0.0012)), 0.085, 0.007, tar, seed=21, stretch=(1.45, 1.0), wobble=0.3, angle=0.3,
         segments=20))
add(blob("Puddle", (-0.15, -0.21, z(0.0012)), 0.035, 0.005, tar, seed=22, segments=12, wobble=0.35))
add(blob("Splat", (-0.17, 0.05, z(0.012)), 0.022, 0.004, tar, seed=24, segments=10, rings=2, wobble=0.35))

# ---------------------------------------------------------------- pump: motor over a pump head, off the left rail

PX, PYm = -0.28, 0.07
add(tk.box("PumpPlate", (0.008, 0.05, 0.29), (-RX - 0.018, 0.125, z(0.475)), plate))
for h in (0.4, 0.58):
    add(tk.cylinder("RailClamp", 0.02, z(h), z(h + 0.012), rust, segments=10, center=(-RX - 0.004, RY - 0.008)))
add(tk.box("Shelf", (0.13, 0.12, 0.008), (PX + 0.005, PYm, z(0.416)), plate))
add(bar("Brace", (-RX - 0.022, 0.115, z(0.34)), (PX - 0.05, 0.115, z(0.412)), (0.02, 0.006), plate))
add(tk.box("PumpHead", (0.1, 0.085, 0.075), (PX, PYm - 0.005, z(0.4585)), alu, 0.006))
add(tk.cylinder("PressureKnob", 0.017, 0.003, PYm - 0.0475, rubber, segments=10, center=(PX - 0.025, z(0.47)),
                axis="Y"))
add(tk.box("PrimeLever", (0.012, 0.045, 0.008), (PX + 0.02, PYm - 0.06, z(0.488)), red_plastic))
add(tk.cylinder("PrimeValve", 0.009, PYm - 0.06, PYm - 0.0475, alu, segments=8, center=(PX + 0.02, z(0.488)),
                axis="Y"))
add(tk.cylinder("MotorFlange", 0.064, z(0.4955), z(0.505), motor_paint, segments=24, center=(PX, PYm)))
mot = tk.cylinder("Motor", 0.06, z(0.505), z(0.655), motor_paint, segments=24, center=(PX, PYm), rings=2)
add(tk.dent(mot, 0.002, 0.06, seed=6))
for h in (0.54, 0.6):
    add(tk.cylinder("MotorRib", 0.063, z(h), z(h + 0.008), motor_paint, segments=24, center=(PX, PYm)))
add(tk.cylinder("EndBell", 0.06, z(0.655), z(0.675), motor_paint, segments=24, center=(PX, PYm), radius_top=0.05))
add(tk.cylinder("FanCover", 0.048, z(0.675), z(0.69), plate, segments=16, center=(PX, PYm)))
add(tk.box("CapHump", (0.04, 0.06, 0.08), (PX - 0.065, PYm, z(0.58)), motor_paint, 0.01))
add(tk.box("ConduitBox", (0.03, 0.04, 0.05), (PX + 0.05, PYm + 0.03, z(0.62)), motor_paint))
for a in (40, 160, 280):
    add(nut("BellBolt", PX + 0.052 * math.cos(math.radians(a)), PYm + 0.052 * math.sin(math.radians(a)), z(0.662),
            rust, radius=0.006, height=0.01))

# Suction tube dipped in the tar, crusted where it goes in
suction = [(PX + 0.035, PYm - 0.05, z(0.44)), (-0.23, -0.01, z(0.448)), (-0.19, -0.035, z(0.455)),
           (-0.13, -0.048, z(0.455)), (-0.09, -0.052, z(0.445)), (-0.075, -0.052, z(0.415)),
           (-0.072, -0.052, z(0.36))]
add(tk.tube("Suction", spline(suction, per=2), 0.012, plate, resolution=2))
add(nut("SuctionNut", PX + 0.035, PYm - 0.06, z(0.44), alu, radius=0.017, height=0.0125, axis="Y"))
crust = []
for k, (h, r) in enumerate(((0.381, 0.026), (0.388, 0.021), (0.396, 0.018), (0.405, 0.015), (0.414, 0.0125))):
    crust.append(((-0.072 + jitter(0.002), -0.052 + jitter(0.002), z(h)), (1, 0, 0), (0, 1, 0), r + jitter(0.002),
                  r + jitter(0.002)))
add(loft("SuctionCrust", crust, tar, segments=8))

# High-pressure hose from the pump up to the tee on the swivel post
PY, PH = 0.105, 0.72  # post axis and the top of its bearing
TEE = 0.62
hp = [(PX + 0.05, PYm - 0.01, z(0.465)), (-0.205, 0.066, z(0.48)), (-0.14, 0.09, z(0.52)), (-0.08, 0.106, z(0.565)),
      (-0.062, 0.107, z(TEE - 0.02)), (-0.05, PY, z(TEE))]
add(tk.tube("HPHose", spline(hp, per=3), 0.009, hose, resolution=2))
add(nut("HoseNut", PX + 0.05, PYm - 0.01, z(0.465), alu, radius=0.013, height=0.012, axis="X"))

# ---------------------------------------------------------------- swivel post (static) on the frame

add(tk.cylinder("Post", 0.017, z(0.455), z(PH - 0.022), plate, segments=12, center=(0.0, PY)))
add(tk.cylinder("PostPlug", 0.019, z(0.447), z(0.46), rust, segments=10, center=(0.0, PY)))
for h in (0.47, 0.66):
    add(tk.box("PostBlock", (0.045, 0.05, 0.024), (0.0, PY + 0.035, z(h)), rust))
    add(tk.cylinder("PostClamp", 0.0195, z(h - 0.006), z(h + 0.006), plate, segments=12, center=(0.0, PY)))
add(tk.cylinder("Tee", 0.014, -0.036, 0.0, plate, segments=10, center=(PY, z(TEE)), axis="X"))
add(nut("TeeNut", -0.05, PY, z(TEE), alu, radius=0.0145, height=0.014, axis="X"))
add(tk.cylinder("TeeBody", 0.021, z(TEE - 0.015), z(TEE + 0.015), plate, segments=12, center=(0.0, PY)))
add(tk.cylinder("Bearing", 0.034, z(PH - 0.022), z(PH), rust, segments=20, center=(0.0, PY), bevel_width=0.003))
add(tk.cylinder("GreaseNipple", 0.004, 0.032, 0.046, plate, segments=6, center=(PY, z(PH - 0.011)), axis="X"))

# ---------------------------------------------------------------- the swivel: turntable, bracket arm and the gun

sw = swivel.append
T1 = PH + 0.012  # top of the turntable
sw(tk.cylinder("Turntable", 0.046, z(PH), z(T1), rust, segments=20, center=(0.0, PY), bevel_width=0.002))
for k in range(4):
    a = math.radians(45 + 90 * k)
    sw(nut("TableBolt", 0.036 * math.cos(a), PY + 0.036 * math.sin(a), z(T1), rust, radius=0.006, height=0.006))
sw(tk.cylinder("Union", 0.013, z(T1), z(T1 + 0.03), alu, segments=6, center=(0.0, PY)))
sw(tk.cylinder("UnionElbow", 0.009, -0.032, 0.0, alu, segments=8, center=(PY, z(T1 + 0.022)), axis="X"))

# Angle-iron arm up the back and over the top, hose-clamped to the gun's head
AX = 0.03
sw(bar("Arm", (AX, PY + 0.03, z(T1)), (AX, PY + 0.03, z(0.975)), (0.012, 0.03), plate))
sw(bar("ArmGusset", (AX, PY + 0.035, z(T1)), (AX, PY - 0.01, z(T1)), (0.012, 0.006), plate))
sw(bar("ArmTop", (AX + 0.003, PY + 0.04, z(0.975)), (0.0, PY - 0.13, z(0.972)), (0.03, 0.006), plate))
# The gun: a metal head with a blue grip hanging under it, trigger and guard, a short extension and the blue tip guard
HY, HH = PY - 0.1, 0.94  # head center
sw(tk.box("Head", (0.046, 0.13, 0.05), (0.0, HY, z(HH)), gun_metal, 0.012))
for y in (HY - 0.035, HY + 0.035):
    sw(tk.box("HoseClamp", (0.052, 0.01, 0.062), (0.0, y, z(HH + 0.003)), plate))
    sw(nut("ClampScrew", 0.026, y - 0.004, z(HH + 0.015), rust, radius=0.005, height=0.008, axis="X"))
G0 = (0.0, HY + 0.045, z(HH - 0.025))  # grip top
grip = [tk.box("Grip", (0.038, 0.052, 0.12), (0.0, G0[1], G0[2] - 0.06), gun_blue, 0.01),
        tk.cylinder("HoseSwivel", 0.013, G0[2] - 0.138, G0[2] - 0.118, alu, segments=6, center=(0.0, G0[1]))]
for o in grip:
    sw(tilt(o, "X", 14.0, G0))
gb = Vector(G0) + Matrix.Rotation(math.radians(14.0), 3, "X") @ Vector((0.0, 0.0, -0.138))  # grip foot
sw(tk.cylinder("Nose", 0.021, HY - 0.095, HY - 0.06, gun_metal, segments=14, center=(0.0, z(HH + 0.004)), axis="Y"))
sw(nut("FrontNut", 0.0, HY - 0.11, z(HH + 0.004), gun_metal, radius=0.018, height=0.016, axis="Y"))
TIP = HY - 0.17
sw(tk.cylinder("Extension", 0.008, TIP, HY - 0.11, plate, segments=8, center=(0.0, z(HH + 0.004)), axis="Y"))
sw(tk.cylinder("TipHousing", 0.02, TIP - 0.028, TIP + 0.004, gun_blue, segments=12, center=(0.0, z(HH + 0.004)),
               axis="Y"))
guard = tk.box("TipGuard", (0.105, 0.012, 0.032), (0.0, TIP - 0.03, z(HH + 0.004)), gun_blue, 0.005)
sw(tilt(guard, "Y", 5.0, (0.0, TIP, z(HH + 0.004))))
sw(tk.cylinder("TipStem", 0.006, z(HH + 0.004), z(HH + 0.034), gun_metal, segments=6, center=(0.0, TIP - 0.017)))
sw(tk.box("TipHandle", (0.034, 0.008, 0.01), (0.0, TIP - 0.017, z(HH + 0.036)), gun_blue))
NOZ_Y = TIP - 0.044
sw(tk.cylinder("Nozzle", 0.005, NOZ_Y, TIP - 0.028, gun_metal, segments=8, center=(0.0, z(HH + 0.004)), axis="Y"))
sw(tk.tube("Trigger", spline([(0.0, HY - 0.008, z(HH - 0.026)), (0.0, HY - 0.025, z(HH - 0.05)),
                              (0.0, HY - 0.028, z(HH - 0.085)), (0.0, HY - 0.018, z(HH - 0.108))], per=2), 0.006,
           gun_metal, resolution=1))
sw(tk.tube("TriggerGuard", spline([(0.0, HY - 0.045, z(HH - 0.024)), (0.0, HY - 0.06, z(HH - 0.07)),
                                   (0.0, HY - 0.048, z(HH - 0.12)), (0.0, gb.y - 0.03, gb.z + 0.012),
                                   (0.0, gb.y - 0.008, gb.z + 0.01)], per=2), 0.0045, gun_blue, resolution=1))
# Hose loop from the grip foot down into the union on the turntable
sw(tk.tube("GunHose", spline([tuple(gb), (0.0, gb.y - 0.012, gb.z - 0.012), (-0.03, gb.y - 0.035, z(T1 + 0.034)),
                              (-0.062, PY - 0.03, z(T1 + 0.03)), (-0.052, PY, z(T1 + 0.023)),
                              (-0.032, PY, z(T1 + 0.022))], per=3), 0.0085, hose, resolution=2))
# A scrapped door-lock solenoid zip-tied to the arm, its rod wired to the trigger
sw(tk.box("Solenoid", (0.022, 0.06, 0.03), (AX + 0.017, PY + 0.0, z(0.87)), battery_case, 0.004))
for y in (PY - 0.015, PY + 0.015):
    sw(tk.box("ZipTie", (0.036, 0.004, 0.034), (AX + 0.011, y, z(0.87)), ink))
sw(tk.tube("TriggerWire", [(AX + 0.017, PY - 0.03, z(0.87)), (AX + 0.01, HY + 0.02, z(0.875)),
                           (0.004, HY - 0.024, z(HH - 0.06))], 0.0018, rust, resolution=1))
sw(tk.tube("SolenoidWire", spline([(AX + 0.017, PY + 0.03, z(0.87)), (AX + 0.02, PY + 0.04, z(0.83)),
                                   (0.012, PY + 0.012, z(T1 + 0.004))], per=2), 0.0022, red_plastic, resolution=1))
# Tar caked on the extension and the guard, dripping
crust = []
for k in range(5):
    y = TIP + 0.004 + 0.012 * k
    r = 0.0135 - 0.0008 * k + jitter(0.0015)
    crust.append(((jitter(0.001), y, z(HH + 0.0025)), (1, 0, 0), (0, 0, 1), r, r * 0.9))
sw(loft("ExtCrust", crust, tar, segments=8))
sw(hanging_drip("TipDrip", (0.014, TIP - 0.028, z(HH - 0.01)), 0.04, 0.0065, tar))
sw(hanging_drip("TipDrip", (-0.03, TIP - 0.032, z(HH - 0.011)), 0.02, 0.0055, tar))
sw(blob("HeadSplat", (0.004, HY - 0.03, z(HH + 0.025)), 0.016, 0.003, tar, seed=31, segments=10, rings=2))

MUZZLE = (0.0, NOZ_Y, z(HH + 0.004))

# ---------------------------------------------------------------- junction box with the power lamp (right rail)

JX, JY, JH = 0.245, 0.11, 0.555
add(tk.box("JBox", (0.08, 0.06, 0.1), (JX, JY, z(JH)), box_grey, 0.006))
add(tk.box("JLid", (0.07, 0.006, 0.088), (JX, JY - 0.032, z(JH)), box_grey))
add(tk.box("JBracket", (0.04, 0.03, 0.05), (JX - 0.045, JY + 0.02, z(JH)), rust))
add(tk.cylinder("LampBase", 0.019, JY - 0.045, JY - 0.035, rust, segments=12, center=(JX, z(JH + 0.02)), axis="Y"))
add(tk.cylinder("Lamp", 0.0135, JY - 0.062, JY - 0.045, lamp, segments=12, center=(JX, z(JH + 0.02)), axis="Y",
                bevel_width=0.005))
for k in range(2):
    ring = tk.torus("Cage", 0.016, 0.0016, (JX, JY - 0.05 - 0.008 * k, z(JH + 0.02)), rust, 12, 4)
    add(tilt(ring, "X", 90, (JX, JY - 0.05 - 0.008 * k, z(JH + 0.02))))
add(tk.cylinder("Toggle", 0.008, JY - 0.042, JY - 0.035, plate, segments=6, center=(JX, z(JH - 0.025)), axis="Y"))
add(bar("ToggleLever", (JX, JY - 0.04, z(JH - 0.025)), (JX, JY - 0.058, z(JH - 0.012)), (0.004, 0.004), plate))
for sx in (-1, 1):
    for sz in (-1, 1):
        add(nut("JScrew", JX + 0.028 * sx, JY - 0.037, z(JH + 0.036 * sz), rust, radius=0.0045, height=0.003,
                axis="Y"))
LAMP = (JX, JY - 0.062, z(JH + 0.02))

# Cord from the junction box along the back crossbar to the motor
add(tk.tube("MotorCord", spline([(JX - 0.035, JY + 0.03, z(JH - 0.02)), (0.17, 0.178, z(0.5)), (0.0, 0.181, z(0.502)),
                                 (-0.17, 0.181, z(0.56)), (-RX - 0.01, 0.172, z(0.62)), (-0.225, 0.12, z(0.632)),
                                 (PX + 0.05, PYm + 0.03, z(0.625))], per=2), 0.006, cord, resolution=1))

# ---------------------------------------------------------------- car battery on the ground, front right

BC, YAW = Vector((0.3, -0.265, 0.0)), -12.0
bat = [tk.box("BatteryCase", (0.17, 0.25, 0.175), (BC.x, BC.y, z(0.0875)), battery_case, 0.008),
       tk.box("BatteryLid", (0.174, 0.254, 0.022), (BC.x, BC.y, z(0.186)), battery_case, 0.005)]
for dx in (0.0, 0.045):
    bat.append(tk.box("VentStrip", (0.03, 0.17, 0.006), (BC.x + dx, BC.y, z(0.198)), battery_case))
clamps = []
for k, dy in enumerate((-0.085, 0.085)):
    c = (BC.x - 0.05, BC.y + dy)
    bat.append(tk.cylinder("Post", 0.0095, z(0.197), z(0.218), lead, segments=10, center=c, radius_top=0.0078))
    clamp_mat = red_plastic if k == 0 else rubber
    jaw = tk.box("ClampJaw", (0.03, 0.022, 0.026), (c[0], c[1], z(0.222)), copper)
    handle = tk.box("ClampHandle", (0.075, 0.022, 0.016), (c[0] - 0.05, c[1], z(0.232)), clamp_mat, 0.004)
    grip2 = tk.box("ClampHandle", (0.06, 0.02, 0.012), (c[0] - 0.045, c[1], z(0.252)), clamp_mat)
    for o in (jaw, handle, grip2):
        bat.append(tilt(o, "Y", 14.0, (c[0], c[1], z(0.222))))
    clamps.append(Vector((c[0] - 0.088, c[1], z(0.226 + 0.088 * math.sin(math.radians(14))))))
bat.append(tk.box("Label", (0.003, 0.15, 0.08), (BC.x + 0.0865, BC.y, z(0.1)), label))
bat.append(flat_text("LabelText", "12V", 0.05, ink, (BC.x + 0.0885, BC.y - 0.02, z(0.104)), rotation=(90, 0, 90)))
bat.append(tk.box("LabelStripe", (0.002, 0.15, 0.012), (BC.x + 0.0885, BC.y, z(0.067)), red_plastic))
bat.append(blob("BatterySplat", (BC.x + 0.035, BC.y + 0.03, z(0.197)), 0.032, 0.005, tar, seed=41, segments=12,
                rings=2, wobble=0.35))
yaw = Matrix.Translation(BC) @ Matrix.Rotation(math.radians(YAW), 4, "Z") @ Matrix.Translation(-BC)
for o in bat:
    o.matrix_world = yaw @ o.matrix_world
    add(o)
clamps = [yaw @ p for p in clamps]

# Jumper cables down to the ground, back along the bucket and up the right rail to the junction box
for k, (p, mat) in enumerate(zip(clamps, (red_plastic, rubber))):
    off = 0.016 * k
    path = [p, p + Vector((-0.02, 0.005, -0.03)), Vector((p.x - 0.03, p.y + 0.015, z(0.1))),
            Vector((p.x - 0.02, p.y + 0.05, z(0.011))), Vector((0.215 + off, -0.04, z(0.011))),
            Vector((0.24 + off, 0.08, z(0.011))), Vector((0.218 + off, 0.13, z(0.04))),
            Vector((0.208 + off, 0.128, z(0.2))), Vector((0.212 + off, 0.12, z(0.42))),
            Vector((JX - 0.015 + 0.03 * k, JY, z(JH - 0.05)))]
    add(tk.tube("JumperCable", spline(path, per=2), 0.0065, mat, resolution=1))
for h in (0.26, 0.38):
    add(tk.cylinder("CableTape", 0.026, z(h), z(h + 0.02), tape, segments=10, center=(RX + 0.012, RY - 0.012)))

# ---------------------------------------------------------------- join, bake, split the swivel off

for o in swivel:
    tk.mark_part(o, "Swivel")
atlas = tk.triangulate(tk.join(parts + swivel, "TarSprayer"))
tk.smart_uvs(atlas)

paths = tk.bake_atlas(atlas, ASSETS, "TarSprayer_Atlas")
baked = tk.baked_material("TarSprayer_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

PIVOT = (0.0, PY, z(PH))
part = tk.split_part(model, "Swivel", PIVOT)
muzzle = tk.point("Muzzle", MUZZLE, part)

tk.export_fbx([model, part, muzzle], os.path.join(ASSETS, "TarSprayer.fbx"))
tris = len(model.data.polygons) + len(part.data.polygons)
print("[tar_sprayer] triangles:", tris, "(body", len(model.data.polygons), "swivel", len(part.data.polygons), ")")
co = [model.matrix_world @ v.co for v in model.data.vertices] + [part.matrix_world @ v.co for v in part.data.vertices]
print("[tar_sprayer] bounds min", tuple(round(min(c[i] for c in co), 4) for i in range(3)),
      "max", tuple(round(max(c[i] for c in co), 4) for i in range(3)))
bpy.context.view_layer.update()
print("[tar_sprayer] Swivel pivot", tuple(round(c, 4) for c in part.matrix_world.translation), "parent",
      part.parent.name)
print("[tar_sprayer] Muzzle", tuple(round(c, 4) for c in muzzle.matrix_world.translation), "parent", muzzle.parent.name)
print("[tar_sprayer] lamp lens front", tuple(round(c, 4) for c in LAMP))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.5, -2.0, 0.75), (0, 0, z(0.5)), lens=45), os.path.join(PREVIEWS, "tar_sprayer_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0, 0, z(0.45)), lens=45), os.path.join(PREVIEWS, "tar_sprayer_back.png"))
tk.render(tk.camera("Close", (0.75, -0.95, 0.55), (0.0, -0.02, z(0.62)), lens=45),
          os.path.join(PREVIEWS, "tar_sprayer_close.png"))
part.rotation_euler.z = math.radians(40)
bpy.context.view_layer.update()
print("[tar_sprayer] Muzzle turned 40", tuple(round(c, 4) for c in muzzle.matrix_world.translation))
tk.render(tk.camera("Turned", (0.9, -1.7, 1.45), (0, 0, z(0.7)), lens=45),
          os.path.join(PREVIEWS, "tar_sprayer_turned.png"))
part.rotation_euler.z = 0.0
bpy.context.view_layer.update()

d = Vector((1.9, -2.5, 1.5))
cam = tk.camera("Icon", tuple(Vector((0, 0, z(0.5))) + d), (0, 0, z(0.5)), lens=62)
frame_icon(cam, [model, part], (0, 0, z(0.5)), d, fill=0.92)
tk.icon(cam, ICON, hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.5)))
print("[tar_sprayer] done")
