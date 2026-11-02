"""Bear Trap: a floor trap on a 1x1x1 block, at most 0.12 tall. A big old rusty double-longspring leg-hold trap: two
toothed semicircular jaws lying open on a cross-shaped base, the pan in the middle with the dog laid over the near jaw,
two flat leaf springs out to the sides with their eyes round the jaw posts, and a chain from one spring to a wooden
stake driven into the ground.

The jaws are the moving parts "JawA" (the -Y jaw) and "JawB" (the +Y jaw), both pivoting on the hinge line through the
two jaw posts: along X at y = 0, at the height of the posts' pivot holes. Rest pose: open, lying flat. Closed: JawA
turns -90 degrees about +X and JawB +90 degrees; they stand up and meet in the middle with their teeth interlocking.

    blender -b --factory-startup --python bear_trap.py -- <unity asset folder> <preview folder> <icon file>
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

Z = -0.5  # bottom of the model (the ground)
rnd = random.Random(1906)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- helpers

ATTR = "local_uv"  # per-corner (across, along) coordinates, so wood grain follows each piece


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
    T = []
    for i in range(n):
        d = (P[(i + 1) % n] - P[(i - 1) % n]) if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        T.append(d.normalized())
    return T


def strap(name, pts, width, thick, mat, side=(0.0, 0.0, 1.0), closed=False, bevel=0.0):
    """A flat bar swept along a polyline: `width` along `side` (kept square to the path), `thick` across it."""
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
    obj = tk.mesh_object(name, bm, mat)
    if bevel:
        tk.bevel(obj, bevel, 1, 50)
    return tk.smooth(obj, 40)


def tube(name, pts, radius, mat, sides=6, closed=False):
    """A round wire along a polyline (closed for rings and chain links)."""
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
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * j / sides) + B * math.sin(2 * math.pi * j / sides))
                                   * radius) for j in range(sides)])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def prism(name, base, tangent, normal, up, outline, thick, mat):
    """An outline (in tangent/up coordinates) extruded `thick` along `normal`, centered: a tooth, a tab."""
    bm = bmesh.new()
    front = [bm.verts.new(base + tangent * a + up * b + normal * (thick / 2)) for a, b in outline]
    back = [bm.verts.new(base + tangent * a + up * b - normal * (thick / 2)) for a, b in outline]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    k = len(outline)
    for j in range(k):
        j1 = (j + 1) % k
        bm.faces.new((front[j], back[j], back[j1], front[j1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 30)


def shift_part(model, label, offset):
    """Moves the faces marked as a moving part (in the joined model, before split_part), e.g. out of the way for the
    bake."""
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


def place(obj, start, direction, spin=0.0):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(start) @ rot @ Matrix.Rotation(spin, 4, "Z") @ obj.matrix_world
    return obj


tk.reset_scene()
tk.preview_stage()

# ---------------------------------------------------------------- materials

jaw_steel = tk.photo_material("JawSteel", "metal_plate_02", scale=3.0, value=0.8, sat=0.6, exposed="rust_coarse_01",
                              chip=1.0, patches=0.9, grime=0.6, streaks=0.4, metal_floor=0.4, rough_scale=0.9,
                              grit=0.3, scratches=0.08, edges=1.0, contrast=0.05)
spring_steel = tk.photo_material("SpringSteel", "metal_plate_02", scale=3.4, value=0.7, sat=0.6,
                                 exposed="rust_coarse_01", chip=1.0, patches=0.8, grime=0.5, streaks=0.4,
                                 metal_floor=0.4, rough_scale=0.9, grit=0.3, scratches=0.08, edges=0.8, contrast=0.05,
                                 offset=(0.3, 0.6, 0.1))
rust = tk.photo_material("Rust", "rust_coarse_01", scale=3.0, value=0.95, exposed=None, grime=0.5, metal_floor=0.3,
                         grit=0.8, edges=0.5)
pan_mat = tk.photo_material("Pan", "metal_plate_02", scale=4.0, value=0.8, sat=0.6, exposed="rust_coarse_01",
                            chip=1.0, patches=0.85, grime=0.6, metal_floor=0.35, grit=0.5, scratches=0.15, edges=0.9,
                            contrast=0.05)
lumber = grain_aligned(tk.photo_material("Lumber", "weathered_planks", scale=1.4, sat=0.5, value=2.4,
                                         tint=(1.0, 0.95, 0.88), exposed=None, grime=0.6, bump=0.7, grit=0.8,
                                         contrast=0.2))
cut = grain_aligned(tk.photo_material("CutWood", "weathered_planks", scale=2.0, sat=0.7, value=3.3,
                                      tint=(1.0, 0.88, 0.7), exposed=None, grime=0.5, bump=0.5, grit=0.8,
                                      contrast=0.1))

parts = []
add = parts.append
jaw_parts = {"JawA": [], "JawB": []}


def add_jaw(label, o):
    tk.mark_part(o, label)
    jaw_parts[label].append(o)
    return o


# ---------------------------------------------------------------- dimensions

BASE_T = 0.008
JAW_H, JAW_T, TOOTH = 0.026, 0.015, 0.022
ZP = z(BASE_T + JAW_H + TOOTH / 2)  # the hinge line's height: the middle of the teeth
JAW_Z = z(BASE_T + JAW_H / 2)
RX, RY = 0.235, 0.214  # the jaws' half span along X and reach along Y (strip centerline)
POST_X = 0.264
PHI0 = math.radians(5.0)
PIVOT = Vector((0.0, 0.0, ZP))

# ---------------------------------------------------------------- base: a cross of flat bar, jaw posts, pan and dog

add(tk.box("BaseBar", (2 * (POST_X + 0.012), 0.032, BASE_T), (0.0, 0.0, z(BASE_T / 2)), spring_steel, 0.0015))
add(tk.box("CrossBar", (0.03, 0.49, BASE_T), (0.0, -0.017, z(BASE_T / 2)), spring_steel, 0.0015))
POST_TOP = ZP + 0.017
for sx in (-1, 1):
    add(tk.box("Post", (0.012, 0.032, POST_TOP - z(BASE_T)), (sx * POST_X, 0.0, (POST_TOP + z(BASE_T)) / 2),
               spring_steel, 0.002))
    rivet = tk.cylinder("Rivet", 0.0075, 0.0, 0.004, rust, segments=10, radius_top=0.005)
    add(place(rivet, Vector((sx * (POST_X + 0.006), 0.0, ZP)), (sx, 0, 0)))
    add(tk.cylinder("Pin", 0.0045, POST_X - 0.03, POST_X + 0.006, rust, segments=8, center=(0.0, ZP), axis="X")
        if sx > 0 else tk.cylinder("Pin", 0.0045, -POST_X - 0.006, -POST_X + 0.03, rust, segments=8, center=(0.0, ZP),
                                   axis="X"))

# The pan on its post, with the tongue the dog catches on
DOG_Z = z(BASE_T + JAW_H + 0.003)  # the dog lies across the top of JawA's strip
add(tk.cylinder("PanPost", 0.009, z(BASE_T), z(0.029), rust, segments=8))
pan = tk.cylinder("Pan", 0.056, z(0.028), z(0.034), pan_mat, segments=28, bevel_width=0.0018)
add(tk.dent(pan, 0.0015, 0.03, seed=2))
add(tk.cylinder("PanBoss", 0.016, z(0.034), z(0.037), pan_mat, segments=16, bevel_width=0.001))
add(tk.text_mesh("PanStamp", "No 5", 0.02, pan_mat, (0.0, 0.031, z(0.0342)), rotation=(0.0, 0.0, 0.0),
                 extrude=0.0005))
add(tk.box("PanTongue", (0.016, 0.03, 0.004), (0.0, -0.066, z(0.032)), pan_mat, 0.001))
for sx in (-1, 1):
    add(tk.box("DogLug", (0.006, 0.016, DOG_Z + 0.008 - z(BASE_T)), (sx * 0.0155, -0.257, (DOG_Z + 0.008 + z(BASE_T)) / 2),
               spring_steel, 0.0015))
add(tk.cylinder("DogPin", 0.004, -0.02, 0.02, rust, segments=8, center=(-0.257, DOG_Z), axis="X"))
add(tk.box("Dog", (0.022, 0.198, 0.006), (0.0, -0.157, DOG_Z), spring_steel, 0.0015))
add(tk.cylinder("DogEye", 0.0075, -0.011, 0.011, spring_steel, segments=10, center=(-0.257, DOG_Z), axis="X"))

# ---------------------------------------------------------------- the two leaf springs, eyes round the posts

SPRING_END = 0.41
for sx in (-1, 1):
    pts = [(sx * 0.27, 0.0, z(0.0035)), (sx * SPRING_END, 0.0, z(0.0035))]
    for k in range(1, 8):
        a = -math.pi / 2 + math.pi * k / 8
        pts.append((sx * (SPRING_END + 0.016 * math.cos(a)), 0.0, z(0.0195) + 0.016 * math.sin(a)))
    pts += [(sx * SPRING_END, 0.0, z(0.0355)), (sx * 0.36, 0.0, z(0.031)), (sx * 0.32, 0.0, z(0.025)),
            (sx * (POST_X + 0.02), 0.0, z(0.018))]
    add(strap("Spring", pts, 0.03, 0.007, spring_steel, side=(0, 1, 0), bevel=0.0012))
    eye = []
    for k in range(16):
        a = 2 * math.pi * k / 16
        c, s = math.cos(a), math.sin(a)
        eye.append((sx * POST_X + 0.016 * math.copysign(abs(c) ** 0.4, c), 0.026 * math.copysign(abs(s) ** 0.4, s),
                    z(0.018)))
    add(strap("SpringEye", eye, 0.012, 0.006, spring_steel, side=(0, 0, 1), closed=True))
    for dx in (0.3, 0.37):
        rv = tk.cylinder("SpringRivet", 0.005, z(0.007), z(0.0105), rust, segments=8, radius_top=0.003)
        rv.location.x = sx * dx
        add(rv)

# ---------------------------------------------------------------- the jaws


def jaw_point(phi, sy, zz):
    return Vector((RX * math.cos(phi), sy * RY * math.sin(phi), zz))


def jaw_tangent(phi, sy):
    return Vector((-RX * math.sin(phi), sy * RY * math.cos(phi), 0.0)).normalized()


UP = Vector((0.0, 0.0, 1.0))
TOOTH_OUTLINE = [(-0.0135, -0.003), (0.0135, -0.003), (0.002, TOOTH), (-0.002, TOOTH)]
for label, sy in (("JawA", -1), ("JawB", 1)):
    pts = [jaw_point(PHI0 + (math.pi - 2 * PHI0) * k / 36, sy, JAW_Z) for k in range(37)]
    add_jaw(label, strap(label + "Strip", pts, JAW_H, JAW_T, jaw_steel, side=(0, 0, 1), bevel=0.0015))
    # interlocking teeth: JawA 8, JawB 7 set half a pitch over, leaving a gap at the middle of JawA for the dog
    count = 8 if sy < 0 else 7
    for k in range(count):
        f = (k + 0.5) / 8 if sy < 0 else (k + 1) / 8
        phi = PHI0 + (math.pi - 2 * PHI0) * f
        t = jaw_tangent(phi, sy)
        n = t.cross(UP)
        base = jaw_point(phi, sy, JAW_Z + JAW_H / 2)
        outline = [(a * rnd.uniform(0.92, 1.05), b * (rnd.uniform(0.85, 1.0) if b > 0 else 1.0)) for a, b in
                   TOOTH_OUTLINE]
        add_jaw(label, prism(label + "Tooth", base, t, n, UP, outline, JAW_T * 0.92, jaw_steel))
    # ends: a tab bent up from the strip to a knuckle on the hinge line
    for sx in (-1, 1):
        phi = PHI0 if sx > 0 else math.pi - PHI0
        end = jaw_point(phi, sy, JAW_Z)
        kx = sx * (0.24 if sy < 0 else 0.252)
        add_jaw(label, strap(label + "Tab", [end + Vector((0.0, -sy * 0.004, 0.0)), Vector((kx, sy * 0.006, ZP - 0.004)),
                                             Vector((kx, 0.0, ZP))], 0.011, 0.007, jaw_steel, side=(1, 0, 0)))
        add_jaw(label, tk.cylinder(label + "Knuckle", 0.0095, kx - 0.006, kx + 0.006, jaw_steel, segments=12,
                                   center=(0.0, ZP), axis="X", bevel_width=0.0012))

# ---------------------------------------------------------------- the chain and the stake

STAKE = Vector((0.335, 0.355, 0.0))
add(tk.torus("ChainRing", 0.014, 0.004, (0.0, 0.0, 0.0), rust, 16, 6))
parts[-1].matrix_world = Matrix.Translation((SPRING_END + 0.016, 0.0, z(0.0195))) @ Matrix.Rotation(math.radians(90), 4,
                                                                                                     "X")
path = [Vector((SPRING_END + 0.024, 0.014, 0.0)), Vector((0.445, 0.07, 0.0)), Vector((0.44, 0.15, 0.0)),
        Vector((0.415, 0.23, 0.0)), Vector((0.38, 0.29, 0.0)), STAKE + Vector((0.025, -0.03, 0.0))]
seg = [(path[i + 1] - path[i]).length for i in range(len(path) - 1)]
total = sum(seg)
WR, LA, LB = 0.0045, 0.011, 0.0105  # wire radius, straight half-length and end radius of a link's centerline
PITCH = 2 * LA + 2 * LB - 2 * WR - 0.004
s = 0.0
k = 0
while s <= total:
    i, rem = 0, s
    while i < len(seg) - 1 and rem > seg[i]:
        rem -= seg[i]
        i += 1
    p = path[i].lerp(path[i + 1], min(rem / seg[i], 1.0))
    d = (path[i + 1] - path[i]).normalized()
    stand = k % 2 == 1
    side = Vector((0.0, 0.0, 1.0)) if stand else Vector((0.0, 0.0, 1.0)).cross(d).normalized()
    if stand:
        cz = z(LB + WR) + 0.001
    else:
        cz = z(WR) + 0.0012 + (LA + LB) * math.sin(math.radians(3)) * 0.0
    loop = []
    for j in range(18):
        a = 2 * math.pi * j / 18
        # stadium: straight sides along d, round ends
        c, sn = math.cos(a), math.sin(a)
        loop.append(Vector((LA * (1 if c >= 0 else -1) + LB * c, LB * sn, 0.0)) if abs(c) > 1e-6
                    else Vector((0.0, LB * sn, 0.0)))
    m = Matrix((d, side, d.cross(side))).transposed()
    tilt = Matrix.Rotation(math.radians(jitter(10 if stand else 3)), 3, d)
    pts = [Vector((p.x, p.y, cz)) + tilt @ (m @ q) for q in loop]
    add(tube("Link", pts, WR, rust, sides=6, closed=True))
    s += PITCH
    k += 1

# Wooden stake, battered on top, with a steel ring round it
st = tk.box("Stake", (0.046, 0.046, 0.1), (0.0, 0.0, 0.0), lumber, 0.004)
grain_box(st, 2, 1.0, (0.7, 0.3))
st.matrix_world = Matrix.Translation((STAKE.x, STAKE.y, z(0.053))) @ Matrix.Rotation(math.radians(4), 4, "X") \
    @ Matrix.Rotation(math.radians(20), 4, "Z")
add(st)
cap = tk.box("StakeTop", (0.054, 0.052, 0.011), (0.0, 0.0, 0.0), cut, 0.003)
grain_box(cap, 0, 1.0, (0.1, 0.4))
cap.matrix_world = Matrix.Translation((STAKE.x, STAKE.y + 0.004, z(0.104))) @ Matrix.Rotation(math.radians(4), 4, "X") \
    @ Matrix.Rotation(math.radians(24), 4, "Z")
add(tk.dent(cap, 0.003, 0.012, seed=4))
ring = tk.torus("StakeRing", 0.041, 0.0055, (0.0, 0.0, 0.0), rust, 24, 8)
ring.matrix_world = Matrix.Translation((STAKE.x, STAKE.y, z(0.017))) @ Matrix.Rotation(math.radians(14), 4, "Y")
add(ring)

# ---------------------------------------------------------------- bake and export

all_parts = parts + jaw_parts["JawA"] + jaw_parts["JawB"]
atlas = tk.triangulate(tk.join(all_parts, "BearTrap"))
tk.smart_uvs(atlas)
# Bake with the jaws lifted clear of the ground and the base, so the faces that show when they stand up closed
# aren't baked dark with the ground's occlusion
LIFT = Vector((0.0, 0.0, 1.0))
shift_part(atlas, "JawA", LIFT)
shift_part(atlas, "JawB", LIFT)
paths = tk.bake_atlas(atlas, ASSETS, "BearTrap_Atlas")
shift_part(atlas, "JawA", -LIFT)
shift_part(atlas, "JawB", -LIFT)
baked = tk.baked_material("BearTrap_Atlas", paths)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
if ATTR in atlas.data.attributes:
    atlas.data.attributes.remove(atlas.data.attributes[ATTR])
model = atlas
jaw_a = tk.split_part(model, "JawA", PIVOT)
jaw_b = tk.split_part(model, "JawB", PIVOT)

tk.export_fbx([model, jaw_a, jaw_b], os.path.join(ASSETS, "BearTrap.fbx"))
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (model, jaw_a, jaw_b))
print("[bear_trap] triangles:", tris)


def bounds(objs):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return [tuple(round(c, 4) for c in b) for b in (lo, hi)]


bpy.context.view_layer.update()
print("[bear_trap] bounds:", bounds([model, jaw_a, jaw_b]))
for o in (jaw_a, jaw_b):
    print("[bear_trap]", o.name, "pivot:", tuple(round(c, 4) for c in o.matrix_world.translation), "bounds:", bounds([o]))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.2, -1.6, 0.55), (0, 0, z(0.02)), lens=45), os.path.join(PREVIEWS, "bear_trap_front.png"))
tk.render(tk.camera("Back", (-1.3, 1.4, 0.75), (0, 0, z(0.02)), lens=45), os.path.join(PREVIEWS, "bear_trap_back.png"))
tk.render(tk.camera("Close", (0.42, -0.55, -0.18), (0.08, -0.08, z(0.02)), lens=45),
          os.path.join(PREVIEWS, "bear_trap_close.png"))
jaw_a.rotation_euler = (math.radians(-90), 0.0, 0.0)
jaw_b.rotation_euler = (math.radians(90), 0.0, 0.0)
bpy.context.view_layer.update()
print("[bear_trap] closed bounds:", bounds([jaw_a, jaw_b]))
tk.render(tk.camera("Closed", (1.0, -1.25, 0.45), (0, 0, z(0.1)), lens=45), os.path.join(PREVIEWS, "bear_trap_closed.png"))
tk.render(tk.camera("ClosedSide", (1.3, 0.0, z(0.15)), (0, 0, z(0.15)), lens=50),
          os.path.join(PREVIEWS, "bear_trap_closed_side.png"))
jaw_a.rotation_euler = (0.0, 0.0, 0.0)
jaw_b.rotation_euler = (0.0, 0.0, 0.0)
tk.icon(tk.camera("Icon", (0.78, -1.02, 0.62), (0.05, 0.03, z(0.03)), lens=60), ICON, hide={"Floor", "ScaleFigure", "ScaleHead"},
        target=(0, 0, z(0.03)))
print("[bear_trap] done")
