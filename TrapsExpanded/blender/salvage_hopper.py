"""Salvage Hopper: a 1x1x1 block, not powered. A 55-gallon drum cut down to a bin, over-full with scrap, a riveted
sheet-metal funnel on three straps above it, and a car alternator wound with extra copper wire and bolted to an iron
plate as an electromagnet, hanging on a chain from a bent pipe arm clamped to the drum. Bolts, nails, nuts and
chunks cling to the magnet; more spill in the bin, the funnel and on the ground. A hand-painted SCRAP on the drum.

The model carries one empty for the game: MagnetPoint at the magnet's underside.

    blender -b --factory-startup --python salvage_hopper.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector, noise  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(5150)


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
    obj = tk.box(name, size, center, mat)
    if bw:
        tk.bevel(obj, bw, segments=1)
        tk.smooth(obj)
    return obj


def random_rot():
    return Euler((rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 2 * math.pi))).to_matrix()


def lathe(name, profile, segments, mat, center=(0.0, 0.0), shape=None, smooth_angle=40.0):
    """A closed surface of revolution: `profile` is a closed loop of (radius, height) points (heights above the
    block's bottom). shape(i, a, r, h) can move each profile point per angle (cut edges, flares)."""
    bm = bmesh.new()
    rings = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        ring = []
        for i, (r, h) in enumerate(profile):
            if shape:
                r, h = shape(i, a, r, h)
            ring.append(bm.verts.new((center[0] + r * math.cos(a), center[1] + r * math.sin(a), z(h))))
        rings.append(ring)
    n = len(profile)
    for k in range(segments):
        ra, rb = rings[k], rings[(k + 1) % segments]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ra[i], rb[i], rb[j], ra[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), smooth_angle)


def warp_radial(obj, center, amp, scale, seed=0.0):
    """Dents a drum-like shell in and out (inner and outer walls move together, so it stays one sheet)."""
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        d = Vector((p.x - center[0], p.y - center[1], 0.0))
        if d.length < 1e-6:
            continue
        n = noise.noise(Vector((p.x * scale, p.y * scale, p.z * scale + seed)))
        v.co += obj.matrix_world.inverted().to_3x3() @ (d.normalized() * n * amp)
    return obj


def wire(name, points, radius, mat, res=1, caps=True):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = res
    curve.use_fill_caps = caps
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (co[0], co[1], co[2], 1.0)
    cobj = tk.link(bpy.data.objects.new(name + "Curve", curve))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(cobj)
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return tk.smooth(obj, 50)


def bar_between(name, p0, p1, width, thick, mat, up=(0.0, 0.0, 1.0)):
    """A flat bar from p0 to p1, its width across `up`."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    x = d.normalized()
    u = Vector(up)
    zz = (u - x * u.dot(x)).normalized()
    y = zz.cross(x)
    obj = tk.box(name, (d.length, width, thick), (0.0, 0.0, 0.0), mat)
    m = Matrix((x, y, zz)).transposed().to_4x4()
    obj.matrix_world = Matrix.Translation((p0 + p1) / 2) @ m
    return obj


def text_on_drum(name, body, size, mat, center, radius, angle_deg, h):
    """Painted lettering wrapped onto a drum (facing out at angle_deg, centered at height h)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 3
    font = "C:/Windows/Fonts/impact.ttf"
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cobj = tk.link(bpy.data.objects.new(name + "Curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(cobj)
    a0 = math.radians(angle_deg)
    for v in me.vertices:
        u, w = v.co.x, v.co.y          # along the drum, up
        a = a0 + u / radius
        r = radius + 0.0015
        v.co = Vector((center[0] + r * math.cos(a), center[1] + r * math.sin(a), z(h) + w))
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    # face the lettering outward
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for f in bm.faces:
        c = f.calc_center_median()
        out = Vector((c.x - center[0], c.y - center[1], 0.0))
        if f.normal.dot(out) < 0:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def smooth_path(ctrl, per=6):
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


# ---------------------------------------------------------------- materials

tk.reset_scene()
tk.preview_stage()

drum_paint = tk.photo_material("DrumPaint", "rusty_painted_metal", scale=1.6, sat=0.75, value=1.05,
                               tint=(1.0, 0.86, 0.7), chip=1.0, grime=0.9, streaks=1.4, patches=0.8, metal_floor=0.4,
                               rough_scale=0.85, grit=1.0, scratches=0.55, edges=0.8, contrast=0.12)
drum_inside = tk.photo_material("DrumInside", "rust_coarse_01", scale=2.2, value=0.8, exposed=None, grime=1.0,
                                metal_floor=0.3, grit=0.8)
galv = tk.photo_material("Galvanized", "metal_plate_02", scale=2.0, sat=0.15, value=1.25, exposed="rust_coarse_01",
                         chip=0.8, patches=0.55, grime=0.9, streaks=0.9, metal_floor=0.5, rough_scale=0.9, grit=1.0,
                         scratches=0.5, edges=0.7, contrast=0.12)
pipe_mat = tk.photo_material("Pipe", "metal_plate_02", scale=2.4, sat=0.4, value=0.7, exposed="rust_coarse_01",
                             chip=1.0, patches=0.8, grime=0.9, streaks=0.8, metal_floor=0.45, grit=1.0, scratches=0.5,
                             edges=0.8, contrast=0.12)
alu = tk.photo_material("Alu", "metal_plate_02", scale=2.6, sat=0.0, value=1.55, exposed="rust_coarse_01", chip=0.3,
                        patches=0.2, grime=1.0, metal_floor=0.5, rough_scale=0.9, grit=1.0, scratches=0.35, edges=0.6,
                        contrast=0.1)
steel = tk.photo_material("Steel", "metal_plate_02", scale=2.4, sat=0.3, value=0.9, exposed="rust_coarse_01",
                          chip=1.0, patches=0.45, grime=0.9, metal_floor=0.55, grit=0.9, scratches=0.6, edges=0.9)
dark_steel = tk.photo_material("DarkSteel", "metal_plate_02", scale=2.4, sat=0.2, value=0.5, exposed="rust_coarse_01",
                               chip=0.6, patches=0.4, grime=0.9, metal_floor=0.5, grit=0.8, scratches=0.4, edges=0.7)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
heap_mat = tk.photo_material("Heap", "rust_coarse_01", scale=4.0, value=1.15, exposed=None, grime=0.5, metal_floor=0.35,
                             grit=0.12, bump=1.2, contrast=0.3)
copper = tk.tarnished_copper("Copper", bright=(0.95, 0.52, 0.28), dark=(0.72, 0.34, 0.17))
brass = tk.tarnished_copper("Brass", bright=(0.78, 0.6, 0.28), dark=(0.5, 0.37, 0.14))
paint = tk.grimy("SignPaint", (0.62, 0.6, 0.52), roughness=0.65, grime=0.8, grime_set="rust_coarse_01", scale=1.4,
                 dirt_range=(0.2, 0.06))
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
red_wire = tk.grimy("RedWire", (0.36, 0.035, 0.025), roughness=0.5, grime=0.7, grit=0.9, dirt_range=(0.1, 0.03))
tape = tk.grimy("Tape", (0.02, 0.02, 0.022), roughness=0.42, grime=0.25, bump_scale=35.0)

parts = []
add = parts.append

DX, DY, R = -0.03, -0.03, 0.285     # drum center and radius
RIM = 0.46                          # cut height of the drum

# ---------------------------------------------------------------- the cut-down drum


def drum_shape(i, a, r, h):
    """Rough cut along the top (profile points 0 and 1 are the inner and outer top edge), bent out in two places."""
    if i in (0, 1, 2, 18, 19):
        cut = 0.006 * noise.noise(V(math.cos(a) * 2.0, math.sin(a) * 2.0, 3.3)) + 0.004 * math.sin(a * 23.0)
        notch = 0.03 * max(0.0, math.cos(a - 1.9)) ** 30
        lift = 1.0 if i in (0, 1, 19) else 0.5
        h = h - lift * (abs(cut) + notch)
        flare = 0.03 * max(0.0, math.cos(a + 2.4)) ** 6 + 0.015 * max(0.0, math.cos(a - 0.4)) ** 10
        r = r + flare * (1.0 if i in (0, 1, 19) else 0.35)
    return r, h


T = 0.0045
prof = [(R - T, RIM), (R, RIM), (R, RIM - 0.04), (R, 0.33), (R + 0.007, 0.32), (R + 0.007, 0.3), (R, 0.29),
        (R, 0.16), (R + 0.004, 0.15), (R, 0.14), (R, 0.04), (R + 0.006, 0.03), (R + 0.006, 0.006), (R, 0.002),
        (R - T, 0.02), (R - T, 0.15), (R - T, 0.3), (R - T, 0.4), (R - T, RIM - 0.04)]
drum = lathe("Drum", prof, 36, drum_paint, (DX, DY), drum_shape)
warp_radial(drum, (DX, DY), 0.009, 5.0, seed=1.7)
# The inner wall shows rust, not paint: give its faces the inside material
drum.data.materials.append(drum_inside)
for poly in drum.data.polygons:
    c = poly.center
    if poly.normal.dot(Vector((c.x - DX, c.y - DY, 0.0)).normalized()) < -0.5:
        poly.material_index = 1
add(drum)
add(text_on_drum("Scrap", "SCRAP", 0.085, paint, (DX, DY), R + 0.001, -74.0, 0.21))


def heap_height(x, y):
    rr = math.hypot(x - DX, y - DY)
    return (0.478 - 0.05 * (rr / R) ** 1.6 + 0.026 * noise.noise(V(x * 12.0, y * 12.0, 2.0))
            + 0.012 * noise.noise(V(x * 38.0, y * 38.0, 5.0)))


# Over-full: a heap of rusty scrap rising above the rim
heap_bm = bmesh.new()
center_v = heap_bm.verts.new((DX, DY, z(heap_height(DX, DY))))
RINGS, SEG = 8, 34
ring_vs = []
for i in range(1, RINGS + 1):
    rr = (R - T - 0.004) * i / RINGS
    ring = []
    for k in range(SEG):
        a = 2 * math.pi * (k + 0.5 * (i % 2)) / SEG
        x, y = DX + rr * math.cos(a), DY + rr * math.sin(a)
        hh = heap_height(x, y) if i < RINGS else heap_height(x, y) - 0.02
        ring.append(heap_bm.verts.new((x, y, z(hh))))
    ring_vs.append(ring)
for k in range(SEG):
    heap_bm.faces.new((center_v, ring_vs[0][k], ring_vs[0][(k + 1) % SEG]))
for i in range(RINGS - 1):
    a_r, b_r = ring_vs[i], ring_vs[i + 1]
    for k in range(SEG):
        heap_bm.faces.new((a_r[k], b_r[k], b_r[(k + 1) % SEG], a_r[(k + 1) % SEG]))
bmesh.ops.recalc_face_normals(heap_bm, faces=heap_bm.faces[:])
for f in heap_bm.faces:
    if f.normal.z < 0:
        f.normal_flip()
heap = tk.smooth(tk.mesh_object("Heap", heap_bm, heap_mat), 18)
add(heap)

# ---------------------------------------------------------------- riveted sheet-metal funnel on three straps

FB, FT, RB, RT = 0.485, 0.64, 0.046, 0.2   # cone bottom/top heights and radii
th = 0.003
fprof = [(RB, 0.4), (RB, FB), (RT, FT), (RT + 0.007, FT + 0.002), (RT + 0.008, FT + 0.01), (RT + 0.001, FT + 0.014),
         (RT - 0.006, FT + 0.008), (RT - 0.004, FT + 0.003), (RB - th, FB + 0.003), (RB - th, 0.4)]
FTILT = ("X", -2.5, (DX, DY, z(FB)))
funnel = [lathe("Funnel", fprof, 36, galv, (DX, DY), smooth_angle=50.0)]
warp_radial(funnel[0], (DX, DY), 0.005, 9.0, seed=4.2)


def cone_point(r, a, out=0.0):
    hh = FB + (r - RB) / (RT - RB) * (FT - FB)
    return V(DX + (r + out) * math.cos(a), DY + (r + out) * math.sin(a), z(hh))


SEAM = math.radians(200)
for k in range(5):
    r = RB + 0.02 + (RT - RB - 0.04) * k / 4
    p = cone_point(r, SEAM, 0.002)
    funnel.append(tk.cylinder("Rivet", 0.0045, -0.002, 0.002, steel, segments=6))
    d = (p - V(DX, DY, p.z)).normalized()
    nrm = (d - V(0.0, 0.0, (RT - RB) / (FT - FB))).normalized() * -1.0
    funnel[-1].matrix_world = Matrix.Translation(p) @ Vector((0.0, 0.0, 1.0)).rotation_difference(-nrm).to_matrix().to_4x4()
funnel.append(bar_between("Seam", cone_point(RB + 0.01, SEAM, 0.001), cone_point(RT - 0.01, SEAM, 0.001), 0.022, 0.002,
                          galv, up=V(math.cos(SEAM), math.sin(SEAM), -(RT - RB) / (FT - FB))))
for k, a in enumerate((math.radians(a) for a in (30, 150, 270))):
    top = cone_point(0.17, a, 0.004)
    foot = V(DX + (R + 0.004) * math.cos(a), DY + (R + 0.004) * math.sin(a), z(RIM - 0.035))
    knee = V(DX + (R + 0.012) * math.cos(a), DY + (R + 0.012) * math.sin(a), z(RIM + 0.02))
    side = V(-math.sin(a), math.cos(a), 0.0)
    for p0, p1 in ((top, knee), (knee, foot)):
        funnel.append(bar_between("FunnelStrap", p0, p1, 0.022, 0.004, rust, up=side.cross(p1 - p0)))
    for p in (top, foot):
        funnel.append(tk.cylinder("StrapBolt", 0.0055, -0.003, 0.004, steel, segments=6))
        funnel[-1].matrix_world = (Matrix.Translation(p) @ V(0, 0, 1).rotation_difference(
            V(math.cos(a), math.sin(a), 0.0)).to_matrix().to_4x4())
for o in funnel:
    turn(o, *FTILT)
    add(o)

# ---------------------------------------------------------------- scrap pieces


def piece(kind):
    """A scrap piece built around the origin; returns its objects and how far it reaches below its origin."""
    if kind == "bolt":
        L, r = rnd.uniform(0.03, 0.06), rnd.uniform(0.0035, 0.0055)
        m = rnd.choice((steel, rust, rust))
        return [tk.cylinder("BoltHead", r * 1.8, 0.0, r * 1.3, m, segments=6),
                tk.cylinder("BoltShank", r, -L, 0.0, m, segments=6)], L
    if kind == "nut":
        r = rnd.uniform(0.006, 0.011)
        return [tk.cylinder("Nut", r, -r * 0.45, r * 0.45, rnd.choice((steel, rust)), segments=6)], r * 0.45
    if kind == "nail":
        L = rnd.uniform(0.04, 0.075)
        m = rnd.choice((steel, rust))
        return [tk.cylinder("NailHead", 0.0042, -0.0012, 0.0, m, segments=6),
                tk.cylinder("Nail", 0.0017, -L, -0.0012, m, segments=4)], L
    if kind == "washer":
        r = rnd.uniform(0.007, 0.013)
        return [tk.cylinder("Washer", r, -0.0012, 0.0012, rnd.choice((steel, rust)), segments=10)], 0.0012
    if kind == "casing":
        return [tk.cylinder("Casing", 0.0056, 0.0, 0.024, brass, segments=8),
                tk.cylinder("CasingNeck", 0.0044, 0.024, 0.033, brass, segments=8)], 0.0
    if kind == "strip":
        L = rnd.uniform(0.05, 0.09)
        pts = [(-L / 2, 0.0, 0.0), (0.0, 0.0, rnd.uniform(0.005, 0.02)), (L / 2, 0.0, rnd.uniform(-0.01, 0.01))]
        s = bar_between("Strip", pts[0], pts[1], 0.012, 0.002, rnd.choice((rust, steel)))
        t = bar_between("Strip", pts[1], pts[2], 0.012, 0.002, rnd.choice((rust, steel)))
        return [s, t], 0.01
    if kind == "spring":
        pts = [(0.008 * math.cos(t * 0.6), 0.008 * math.sin(t * 0.6), -0.0028 * t) for t in range(0, 26)]
        return [wire("Spring", pts, 0.0014, steel, res=0)], 0.07
    # chunk: an angular lump of steel or a cut piece of plate
    bm = bmesh.new()
    s = rnd.uniform(0.012, 0.022)
    flat = rnd.choice((0.35, 0.6, 1.0))
    for _ in range(9):
        bm.verts.new((rnd.uniform(-1, 1) * s * 1.4, rnd.uniform(-1, 1) * s, rnd.uniform(-1, 1) * s * flat))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    return [tk.mesh_object("Chunk", bm, rnd.choice((rust, rust, dark_steel, copper)))], s * flat


def put(objs, m):
    for o in objs:
        o.matrix_world = m @ o.matrix_world
    return objs


KINDS = ["bolt", "bolt", "nut", "nut", "nail", "nail", "washer", "chunk", "chunk", "chunk", "strip", "casing"]

# On the heap: lots of small stuff, plus a few big pieces poking out
for k in range(92):
    rr = (R - 0.025) * math.sqrt(rnd.random())
    a = rnd.uniform(0, 2 * math.pi)
    x, y = DX + rr * math.cos(a), DY + rr * math.sin(a)
    if rr < RB + 0.01:
        continue
    kind = rnd.choice(KINDS + ["spring"] if k in (7, 41) else KINDS)
    objs, _ = piece(kind)
    s = rnd.uniform(1.15, 1.7)
    m = Matrix.Translation((x, y, z(heap_height(x, y) + 0.002))) @ random_rot().to_4x4() @ Matrix.Diagonal((s, s, s, 1.0))
    for o in put(objs, m):
        add(o)
for k, (a, rr, lean, length) in enumerate(((-2.2, 0.17, 35, 0.16), (0.4, 0.2, -40, 0.13))):  # pipe offcuts
    x, y = DX + rr * math.cos(a), DY + rr * math.sin(a)
    p = tk.cylinder("PipeOffcut", 0.013, 0.0, length, pipe_mat if k == 0 else rust, segments=10)
    p.matrix_world = (Matrix.Translation((x, y, z(heap_height(x, y) - 0.03))) @ Matrix.Rotation(a + 1.2, 4, "Z")
                      @ Matrix.Rotation(math.radians(lean), 4, "X"))
    add(p)
rebar = [(-0.03, 0.0, 0.0), (0.02, 0.01, 0.07), (0.06, 0.0, 0.1), (0.13, -0.02, 0.11)]
rb = wire("Rebar", rebar, 0.005, rust, res=1)
x, y = DX - 0.12, DY + 0.1
rb.matrix_world = Matrix.Translation((x, y, z(heap_height(x, y) - 0.01))) @ Matrix.Rotation(0.7, 4, "Z")
add(rb)
sheet = [(0.0, 0.0, 0.0), (0.06, 0.0, 0.02), (0.1, 0.0, 0.0)]
for k, (x, y, rz) in enumerate(((DX + 0.13, DY - 0.12, 0.4), (DX - 0.17, DY - 0.08, 2.3))):  # bent sheet scraps
    s0 = bar_between("SheetScrap", sheet[0], sheet[1], 0.07, 0.002, galv if k == 0 else drum_paint)
    s1 = bar_between("SheetScrap", sheet[1], sheet[2], 0.07, 0.002, galv if k == 0 else drum_paint)
    m = (Matrix.Translation((x, y, z(heap_height(x, y) + 0.004))) @ Matrix.Rotation(rz, 4, "Z")
         @ Matrix.Rotation(0.35, 4, "X"))
    for o in (s0, s1):
        o.matrix_world = m @ o.matrix_world
        add(o)
# In the funnel's throat
for k in range(9):
    rr = rnd.uniform(RB + 0.012, RB + 0.07)
    a = rnd.uniform(0, 2 * math.pi)
    p = cone_point(rr, a, -0.004)
    objs, _ = piece(rnd.choice(("bolt", "nut", "washer", "chunk", "casing", "nail")))
    m = Matrix.Translation(p) @ random_rot().to_4x4()
    for o in put(objs, m):
        add(turn(o, *FTILT))
# Spilled on the ground in front
for k in range(13):
    a = math.radians(rnd.uniform(-170, -10))
    rr = rnd.uniform(R + 0.03, R + 0.15)
    x, y = DX + rr * math.cos(a), DY + rr * math.sin(a)
    if abs(x) > 0.44 or abs(y) > 0.44:
        continue
    kind = rnd.choice(("bolt", "nut", "washer", "chunk", "casing", "nail", "strip"))
    objs, reach = piece(kind)
    lie = Matrix.Rotation(math.radians(90), 4, "X") if kind in ("bolt", "nail", "casing") else Matrix.Identity(4)
    rest = {"bolt": 0.0095, "nail": 0.0045, "casing": 0.006, "strip": 0.012}.get(kind, reach * 1.02)
    m = Matrix.Translation((x, y, z(rest))) @ Matrix.Rotation(rnd.uniform(0, 6.28), 4, "Z") @ lie
    for o in put(objs, m):
        add(o)

# ---------------------------------------------------------------- bent pipe arm, chain and the alternator magnet

arm = []
PY = DY + R + 0.022           # pipe stands against the back of the drum (built on +Y, then turned)
TOPH = 0.962
bend_pts = [(DX, PY, z(0.012)), (DX, PY, z(0.35)), (DX, PY - 0.004, z(0.7)), (DX, PY - 0.006, z(0.82))]
for k in range(1, 8):
    a = math.radians(90 * k / 8)
    bend_pts.append((DX, PY - 0.006 - 0.11 * (1 - math.cos(a)), z(0.82 + 0.11 * math.sin(a) + 0.002 * k)))
bend_pts += [(DX, DY + 0.12, z(TOPH - 0.004)), (DX, DY - 0.02, z(TOPH - 0.018))]
arm.append(wire("ArmPipe", bend_pts, 0.021, pipe_mat, res=2))
arm.append(tk.cylinder("PipeCap", 0.026, -0.03, 0.0, pipe_mat, segments=14, center=(DX, z(TOPH - 0.019)), axis="Y",
                       bevel_width=0.004))
parts_cap = arm[-1]
parts_cap.matrix_world = Matrix.Translation((0.0, DY - 0.02, 0.0)) @ parts_cap.matrix_world
arm.append(tk.cylinder("Coupling", 0.027, z(0.5), z(0.56), pipe_mat, segments=14, center=(DX, PY), bevel_width=0.004))
arm.append(tk.cylinder("Flange", 0.055, z(0.0), z(0.014), dark_steel, segments=18, center=(DX, PY), bevel_width=0.003))
for k in range(4):
    a = math.radians(45 + 90 * k)
    arm.append(tk.cylinder("FlangeBolt", 0.007, z(0.014), z(0.022), steel, segments=6,
                           center=(DX + 0.04 * math.cos(a), PY + 0.04 * math.sin(a))))
# Clamped to the drum with two U-bolt straps
for h in (0.12, 0.38):
    u = [(DX - 0.03, PY - 0.022, z(h)), (DX - 0.026, PY + 0.012, z(h)), (DX, PY + 0.028, z(h)),
         (DX + 0.026, PY + 0.012, z(h)), (DX + 0.03, PY - 0.022, z(h))]
    arm.append(wire("UBolt", u, 0.004, rust, res=1))
    arm.append(plate("UPlate", (0.085, 0.006, 0.022), (DX, PY - 0.022, z(h)), rust, 0.001))
    for s in (-1, 1):
        arm.append(tk.cylinder("UNut", 0.007, PY - 0.03, PY - 0.024, steel, segments=6, center=(DX + 0.03 * s, z(h)),
                               axis="Y"))
# A diagonal brace bolted between the riser and the boom
arm.append(bar_between("Brace", V(DX, PY - 0.02, z(0.66)), V(DX, DY + 0.1, z(TOPH - 0.03)), 0.028, 0.005, rust,
                       up=V(1.0, 0.0, 0.0)))
for p in (V(DX, PY - 0.02, z(0.66)), V(DX, DY + 0.1, z(TOPH - 0.03))):
    arm.append(tk.cylinder("BraceBolt", 0.006, -0.02, 0.02, steel, segments=6, center=(p.y, p.z), axis="X"))
    arm[-1].matrix_world = Matrix.Translation((DX, 0.0, 0.0)) @ arm[-1].matrix_world
# Eye bolt and chain
EYE = V(DX, DY, z(TOPH - 0.05))
arm.append(tk.cylinder("EyeShank", 0.004, z(TOPH - 0.04), z(TOPH + 0.004), steel, segments=6, center=(DX, DY)))
eye = tk.torus("Eye", 0.011, 0.003, (0.0, 0.0, 0.0), steel, 12, 5)
eye.matrix_world = Matrix.Translation(EYE) @ Matrix.Rotation(math.radians(90), 4, "X")
arm.append(eye)
AC = V(DX, DY, z(0.772))      # alternator center
link_top = EYE.z - 0.011
for k in range(2):
    c = V(DX, DY, link_top - 0.017 - 0.024 * k)
    link = tk.torus("ChainLink", 0.0105, 0.0028, (0.0, 0.0, 0.0), rust, 12, 5)
    link.matrix_world = (Matrix.Translation(c) @ Matrix.Rotation(math.radians(90 * k), 4, "Z")
                         @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Diagonal((0.75, 1.3, 1.0, 1.0)))
    arm.append(link)
chain_end = link_top - 0.017 - 0.024 - 0.013

# The alternator, axis along X, pulley to +X
alt = []


def alt_cyl(name, r, x0, x1, mat, seg=24, bw=0.0, caps=True):
    return tk.cylinder(name, r, AC.x + x0, AC.x + x1, mat, segments=seg, center=(AC.y, AC.z), axis="X", bevel_width=bw,
                       caps=caps)


alt += [alt_cyl("RearCover", 0.05, -0.088, -0.06, dark_steel, seg=20, bw=0.006),
        alt_cyl("RearHousing", 0.064, -0.062, -0.01, alu, bw=0.006),
        alt_cyl("Stator", 0.069, -0.012, 0.012, dark_steel),
        alt_cyl("FrontHousing", 0.064, 0.01, 0.052, alu, bw=0.006),
        alt_cyl("Fan", 0.056, 0.054, 0.06, steel, seg=20),
        alt_cyl("Pulley", 0.032, 0.06, 0.084, steel, seg=18, bw=0.002),
        alt_cyl("PulleyNut", 0.012, 0.084, 0.092, rust, seg=6)]
for k in range(2):
    alt.append(alt_cyl("PulleyGroove", 0.0285, 0.067 + 0.009 * k, 0.07 + 0.009 * k, rust, seg=18, caps=False))
for k in range(10):  # fan blades
    a = 2 * math.pi * k / 10
    bl = tk.box("FanBlade", (0.006, 0.002, 0.024), (AC.x + 0.057, 0.0, 0.0), steel)
    bl.matrix_world = (Matrix.Translation((0.0, AC.y, AC.z)) @ Matrix.Rotation(a, 4, "X")
                       @ Matrix.Translation((0.0, 0.0, 0.04)) @ Matrix.Rotation(math.radians(25), 4, "Z")) @ bl.matrix_world
    alt.append(bl)
for x0 in (-0.05, 0.022):  # cast ribs / vent bars around the housings
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        rib = tk.box("HousingRib", (0.028, 0.006, 0.006), (AC.x + x0 + 0.014, 0.0, 0.0), alu)
        rib.matrix_world = (Matrix.Translation((0.0, AC.y, AC.z)) @ Matrix.Rotation(a, 4, "X")
                            @ Matrix.Translation((0.0, 0.0, 0.065))) @ rib.matrix_world
        alt.append(rib)
# Mounting ear on top (the chain's shackle) and the adjuster ear at the side
alt.append(plate("TopEar", (0.03, 0.02, 0.03), (AC.x, AC.y, AC.z + 0.072), alu, 0.004))
alt.append(tk.cylinder("EarBushing", 0.008, AC.x - 0.02, AC.x + 0.02, steel, segments=8, center=(AC.y, AC.z + 0.078),
                       axis="X"))
alt.append(wire("Shackle", [(AC.x, AC.y - 0.012, AC.z + 0.078), (AC.x, AC.y - 0.012, chain_end + 0.004),
                            (AC.x, AC.y, chain_end - 0.004), (AC.x, AC.y + 0.012, chain_end + 0.004),
                            (AC.x, AC.y + 0.012, AC.z + 0.078)], 0.0025, steel, res=1))
side_ear = plate("SideEar", (0.026, 0.024, 0.022), (AC.x - 0.03, AC.y - 0.075, AC.z + 0.0), alu, 0.004)
alt.append(side_ear)
# Extra copper wound round the stator: the electromagnet hack, taped over
for k in range(4):
    ring = tk.torus("Winding", 0.0735, 0.0052, (0.0, 0.0, 0.0), copper, 18, 5)
    ring.matrix_world = Matrix.Translation((AC.x - 0.015 + 0.01 * k, AC.y, AC.z)) @ Matrix.Rotation(math.radians(90),
                                                                                                     4, "Y")
    alt.append(ring)
alt.append(alt_cyl("WindingTape", 0.0795, -0.004, 0.004, tape, seg=22, caps=False))
# Iron pole plate strapped underneath: the magnet's face
PLATE_H = AC.z - 0.069 - 0.007
alt.append(plate("PolePlate", (0.2, 0.13, 0.014), (AC.x, AC.y, PLATE_H), dark_steel, 0.003))
for s in (-1, 1):
    x = AC.x + 0.05 * s
    loop = [(x, AC.y + 0.067 * math.cos(math.radians(a)), AC.z + 0.067 * math.sin(math.radians(a)))
            for a in range(-30, 211, 30)]
    loop = [(x, AC.y + 0.057, PLATE_H - 0.009)] + loop + [(x, AC.y - 0.057, PLATE_H - 0.009),
                                                           (x, AC.y + 0.057, PLATE_H - 0.009)]
    alt.append(wire("HoseClamp", loop, 0.0028, steel, res=1))
    alt.append(tk.cylinder("ClampScrew", 0.005, AC.y + 0.058, AC.y + 0.07, steel, segments=6,
                           center=(x, PLATE_H - 0.004), axis="Y"))
# Rear terminal stud and a red lead up the chain, taped along the boom
alt.append(alt_cyl("Stud", 0.005, -0.1, -0.086, steel, seg=6))
lead = [(AC.x - 0.1, AC.y, AC.z + 0.01), (AC.x - 0.11, AC.y + 0.01, AC.z + 0.06), (AC.x - 0.03, AC.y + 0.01,
                                                                                   chain_end + 0.02),
        (DX - 0.01, DY + 0.006, z(TOPH - 0.04)), (DX - 0.016, DY + 0.05, z(TOPH - 0.018)),
        (DX - 0.018, DY + 0.16, z(TOPH - 0.006)), (DX - 0.02, PY - 0.08, z(0.89)), (DX - 0.022, PY - 0.004, z(0.7)),
        (DX - 0.022, PY + 0.004, z(0.45))]
alt.append(wire("Lead", smooth_path(lead, 3), 0.0035, red_wire, res=1))
for h in (0.86, 0.6):
    alt.append(tk.cylinder("LeadTape", 0.024, z(h) - 0.012, z(h) + 0.012, tape, segments=12, center=(DX, PY)))
alt.append(tk.cylinder("BoomTape", 0.024, DY + 0.06, DY + 0.085, tape, segments=12, center=(DX, z(TOPH - 0.012)),
                       axis="Y"))

# Scrap stuck to the magnet: hanging off the plate, and clinging round the housing
MAGNET = V(AC.x, AC.y, PLATE_H - 0.007)
stuck = []
# An open-end wrench hanging off the plate by its ring end
wr = [plate("WrenchHandle", (0.012, 0.004, 0.11), (0.0, 0.0, -0.068), steel, 0.0012),
      plate("WrenchHead", (0.03, 0.005, 0.024), (0.0, 0.0, -0.13), steel, 0.0015)]
for s in (-1, 1):
    wr.append(plate("WrenchJaw", (0.008, 0.005, 0.022), (0.012 * s, 0.0, -0.151), steel, 0.0012))
ring = tk.torus("WrenchRing", 0.0115, 0.0038, (0.0, 0.0, 0.0), steel, 14, 5)
ring.matrix_world = Matrix.Translation((0.0, 0.0, -0.0125)) @ Matrix.Rotation(math.radians(90), 4, "X")
wr.append(ring)
stuck += put(wr, Matrix.Translation((AC.x + 0.055, AC.y - 0.035, MAGNET.z)) @ Matrix.Rotation(0.5, 4, "Z")
             @ Matrix.Rotation(math.radians(24), 4, "Y"))
for k in range(22):
    kind = rnd.choice(("nail", "nail", "bolt", "bolt", "nut", "washer", "chunk", "chunk", "casing", "strip"))
    objs, reach = piece(kind)
    x, y = AC.x + rnd.uniform(-0.095, 0.095), AC.y + rnd.uniform(-0.06, 0.06)
    if kind in ("nail", "bolt"):
        rot = (Matrix.Rotation(rnd.uniform(-0.45, 0.45), 4, "X") @ Matrix.Rotation(rnd.uniform(-0.45, 0.45), 4, "Y"))
        m = Matrix.Translation((x, y, MAGNET.z - (0.0 if kind == "nail" else 0.006))) @ rot
    elif kind == "casing":
        m = Matrix.Translation((x, y, MAGNET.z - 0.034)) @ Matrix.Rotation(rnd.uniform(-0.3, 0.3), 4, "X")
    else:
        m = Matrix.Translation((x, y, MAGNET.z - reach * 0.8)) @ Matrix.Rotation(rnd.uniform(0, 6.3), 4, "Z") \
            @ Matrix.Rotation(rnd.uniform(-0.4, 0.4), 4, "X")
    stuck += put(objs, m @ Matrix.Diagonal((1.3, 1.3, 1.3, 1.0)))
# a second rank hanging off the first (nails on nails)
for k in range(6):
    objs, _ = piece(rnd.choice(("nail", "nut", "washer")))
    x, y = AC.x + rnd.uniform(-0.06, 0.06), AC.y + rnd.uniform(-0.035, 0.035)
    m = Matrix.Translation((x, y, MAGNET.z - rnd.uniform(0.022, 0.032))) @ Matrix.Rotation(rnd.uniform(-0.5, 0.5), 4, "Y")
    stuck += put(objs, m @ Matrix.Diagonal((1.3, 1.3, 1.3, 1.0)))
for k in range(7):  # round the housing's lower sides
    a = math.radians(rnd.uniform(200, 340))
    objs, reach = piece(rnd.choice(("nut", "washer", "chunk", "nail")))
    p = V(AC.x + rnd.uniform(-0.05, 0.045), AC.y + 0.067 * math.cos(a), AC.z + 0.067 * math.sin(a))
    nrm = V(0.0, math.cos(a), math.sin(a))
    m = Matrix.Translation(p + nrm * reach * 0.6) @ V(0, 0, 1).rotation_difference(nrm).to_matrix().to_4x4()
    stuck += put(objs, m @ Matrix.Diagonal((1.3, 1.3, 1.3, 1.0)))
for k in range(14):  # bristling off the plate's edges, standing out like filings round a magnet
    sx, sy = rnd.choice(((1, 0), (-1, 0), (0, 1), (0, -1), (1, 0), (-1, 0)))
    if sx:
        x, y = AC.x + sx * 0.1, AC.y + rnd.uniform(-0.055, 0.055)
    else:
        x, y = AC.x + rnd.uniform(-0.09, 0.09), AC.y + sy * 0.065
    out = V(sx + jitter(0.3), sy + jitter(0.3), -rnd.uniform(0.6, 1.3)).normalized()
    kind = rnd.choice(("nail", "nail", "bolt", "bolt", "strip", "nail"))
    objs, reach = piece(kind)
    m = (Matrix.Translation((x, y, PLATE_H - 0.004)) @ V(0, 0, -1).rotation_difference(out).to_matrix().to_4x4()
         @ Matrix.Diagonal((1.3, 1.3, 1.3, 1.0)))
    stuck += put(objs, m)
alt += stuck

# Turn the arm round to the back right, magnet and all, so it shows in profile from the front
ARM_TURN = -28.0
for o in arm + alt:
    turn(o, "Z", ARM_TURN, (DX, DY, 0.0))
    add(o)

# ---------------------------------------------------------------- join, bake, export

tris = {}
for o in parts:
    key = o.name.split(".")[0]
    tris[key] = tris.get(key, 0) + sum(len(p.vertices) - 2 for p in o.data.polygons)
print("[salvage_hopper] parts:", sorted(tris.items(), key=lambda kv: -kv[1])[:16])
for o in parts:
    w = [o.matrix_world @ v.co for v in o.data.vertices]
    if w and (max(abs(c.x) for c in w) > 0.47 or max(abs(c.y) for c in w) > 0.47 or min(c.z for c in w) < Z
              or max(c.z for c in w) > 0.5):
        print("[salvage_hopper] near/over bounds:", o.name, "x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (
            min(c.x for c in w), max(c.x for c in w), min(c.y for c in w), max(c.y for c in w),
            min(c.z for c in w), max(c.z for c in w)))

atlas = tk.triangulate(tk.join(parts, "SalvageHopper"))
tk.smart_uvs(atlas)
paths = tk.bake_atlas(atlas, ASSETS, "SalvageHopper_Atlas")
baked = tk.baked_material("SalvageHopper_Atlas", paths)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

magnet_pt = tk.point("MagnetPoint", MAGNET, model)
tk.export_fbx([model, magnet_pt], os.path.join(ASSETS, "SalvageHopper.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[salvage_hopper] triangles:", tris)
co = [model.matrix_world @ v.co for v in model.data.vertices]
print("[salvage_hopper] bounds: x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f" % (
    min(c.x for c in co), max(c.x for c in co), min(c.y for c in co), max(c.y for c in co),
    min(c.z for c in co), max(c.z for c in co)))
print("[salvage_hopper] MagnetPoint:", tuple(round(c, 4) for c in magnet_pt.matrix_world.translation))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.5, -2.0, 0.7), (0.0, 0.0, z(0.47)), lens=45),
          os.path.join(PREVIEWS, "salvage_hopper_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0.0, 0.0, z(0.45)), lens=45),
          os.path.join(PREVIEWS, "salvage_hopper_back.png"))
tk.render(tk.camera("Close", (0.42, -0.85, 0.42), (DX, DY - 0.02, z(0.62)), lens=45),
          os.path.join(PREVIEWS, "salvage_hopper_close.png"))
tk.icon(tk.camera("Icon", (2.0, -2.65, 1.55), (0.0, 0.0, z(0.47)), lens=66), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0.0, 0.0, z(0.47)))
print("[salvage_hopper] done")
