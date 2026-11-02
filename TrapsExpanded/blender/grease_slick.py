"""Grease Slick: a one-block floor trap, at most 12 cm tall. Half a red oil drum cut open lengthwise and hammered
flat into a shallow pan (the drum's rolled chime still along the back, its rolling hoops bulging the cut sides),
brimming with thick black grease that has slopped over a low spot in the front lip onto the ground. A dented quart
of motor oil lies tipped over in the corner, still oozing, and a filthy shop rag hangs over the side.

No points: the game only needs the block.

    blender -b --factory-startup --python grease_slick.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(4417)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


def nz(x, y, seed=0.0):
    return noise.noise(Vector((x, y, seed)))


def bake_transform(obj):
    """Moves an object's transform into its mesh, so later edits work in world space."""
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def solidify(obj, thickness, offset=-1.0, even=True):
    mod = obj.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = even
    return tk.apply_modifiers(obj)


def push(obj, center, radius, vec):
    """Shoves the vertices near `center` by `vec`, falling off over `radius` (a crease or a crushed spot)."""
    c, v = Vector(center), Vector(vec)
    for vert in obj.data.vertices:
        d = (vert.co - c).length
        if d < radius:
            vert.co += v * (0.5 + 0.5 * math.cos(math.pi * d / radius))
    return obj


def grease_material(name):
    """Thick black-brown grease: glossy but lumpy and swirled, skinned over in patches with a few flecks of dust,
    a little amber where it is a thin film on the ground."""
    mat, g = tk.new_material(name)
    zz = g.separate(g.coords())[2]
    body = g.noise(2.5, detail=4.0, distortion=0.5)
    col = g.mix(g.ramp(body, 0.35, 0.7), (0.006, 0.0048, 0.0035), (0.018, 0.011, 0.0055))
    thin = g.ramp(zz, Z + 0.0022, Z + 0.0004)
    col = g.mix(g.math("MULTIPLY", thin, 0.7), col, (0.045, 0.026, 0.01))
    swirl = g.noise(5.0, detail=5.0, distortion=1.5)
    skin = g.ramp(g.noise(6.0, detail=6.0, distortion=0.3), 0.55, 0.78)
    rough = g.mixf(skin, g.math("ADD", 0.13, g.math("MULTIPLY", swirl, 0.1)), 0.32)
    col = g.mix(g.math("MULTIPLY", skin, 0.6), col, (0.02, 0.017, 0.013))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 90.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    flecks = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.12, 0.05),
                    g.ramp(g.noise(4.0, detail=3.0), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", flecks, 0.8), col, (0.12, 0.1, 0.075))
    rough = g.mixf(flecks, rough, 0.9)
    height = g.math("ADD", swirl, g.math("MULTIPLY", g.noise(30.0, detail=3.0), 0.12))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.25, 0.008))


tk.reset_scene()
tk.preview_stage()

drum = tk.photo_material("DrumPaint", "rusty_painted_metal", scale=1.5, sat=1.15, value=1.15, chip=1.0, grime=0.9,
                         streaks=1.5, patches=1.0, metal_floor=0.35, rough_scale=0.85, grit=0.9, scratches=0.3,
                         edges=1.0, contrast=0.2)
grease = grease_material("Grease")
can_paint = tk.grimy("CanPaint", (0.4, 0.28, 0.06), roughness=0.42, metallic=0.25, grime=1.0,
                     grime_set="rust_coarse_01", scale=1.8, stain=(0.07, 0.045, 0.02), grit=0.9, dirt_range=(0.1, 0.03))
can_band = tk.grimy("CanBand", (0.2, 0.03, 0.02), roughness=0.4, metallic=0.2, grime=0.8, grime_set="rust_coarse_01",
                    scale=1.8, grit=0.8, dirt_range=(0.1, 0.03))
tin = tk.photo_material("Tin", "metal_plate_02", scale=2.4, value=1.15, exposed=None, grime=0.9, metal_floor=0.6,
                        grit=0.8, scratches=0.5, edges=0.6)
rag_cloth = tk.grimy("Rag", (0.42, 0.39, 0.33), roughness=0.95, grime=1.0, grime_set="rust_coarse_01", scale=2.0,
                     stain=(0.06, 0.045, 0.03), grit=0.6, dirt_range=(0.18, 0.05), bump_scale=150.0, bump=0.35)

# ---------------------------------------------------------------- the pan, built in its own frame (h = height)

PA, PB, PR = 0.405, 0.395, 0.07  # half sizes and corner radius of the rim
T = 0.003  # sheet thickness
PROFILE = [(0.0, 0.062), (0.005, 0.056), (0.010, 0.040), (0.016, 0.02), (0.022, 0.008), (0.04, 0.004)]
WALL = 0.022  # inset where the wall meets the floor
GL = 0.026  # grease level
SPILL_X = -0.12  # where the front lip is bent low and the grease slops over
HOOPS = (-0.13, 0.17)  # the drum's rolling hoops cross the pan here
PAN = Matrix.Translation((-0.01, 0.02, Z)) @ Matrix.Rotation(math.radians(3.0), 4, "Z")


def rr_point(u, a, b, r):
    """A rounded rectangle walked counterclockwise: u in [0, 8), each unit an edge or a corner. Returns the point
    and the outward direction."""
    k = int(math.floor(u)) % 8
    f = u - math.floor(u)
    ca, cb = a - r, b - r
    if k == 0:
        return (a, -cb + 2 * cb * f), (1.0, 0.0)
    if k == 2:
        return (ca - 2 * ca * f, b), (0.0, 1.0)
    if k == 4:
        return (-a, cb - 2 * cb * f), (-1.0, 0.0)
    if k == 6:
        return (-ca + 2 * ca * f, -b), (0.0, -1.0)
    centers = {1: (ca, cb), 3: (-ca, cb), 5: (-ca, -cb), 7: (ca, -cb)}
    ang = math.pi / 2 * ((k - 1) / 2 + f)
    cx, cy = centers[k]
    return (cx + r * math.cos(ang), cy + r * math.sin(ang)), (math.cos(ang), math.sin(ang))


def side_amt(u):
    """1 along the cut sides (left and right), 0 along the drum's ends (front and back), blended round corners."""
    k = int(math.floor(u)) % 8
    f = u - math.floor(u)
    sm = f * f * (3 - 2 * f)
    return {0: 1.0, 1: 1.0 - sm, 2: 0.0, 3: sm, 4: 1.0, 5: 1.0 - sm, 6: 0.0, 7: sm}[k]


def wall_w(u):
    """The cut sides flare out in a long curve (what is left of the drum's roundness); the ends are short walls."""
    return WALL * (1.0 + 1.4 * side_amt(u))


def profile_h(d):
    if d >= PROFILE[-1][0]:
        return PROFILE[-1][1]
    for (d0, h0), (d1, h1) in zip(PROFILE, PROFILE[1:]):
        if d <= d1:
            return h0 + (h1 - h0) * (d - d0) / (d1 - d0)
    return PROFILE[-1][1]


def rim_scale(x, y, side):
    s = 1.0 + 0.24 * nz(x * 5.0 + 1.3, y * 5.0, 0.7)
    s += 0.42 * side  # the cut sides curl up higher
    s -= 0.42 * math.exp(-((x - SPILL_X) / 0.075) ** 2) * math.exp(-((y + PB) / 0.08) ** 2)
    s -= 0.25 * math.exp(-((x - 0.36) ** 2 + (y - 0.35) ** 2) / 0.012)  # a corner hammered down
    side = min(1.0, max(0.0, (abs(x) - 0.3) / 0.08))
    for y0 in HOOPS:
        s += 0.2 * side * math.exp(-((y - y0) / 0.03) ** 2)
    return s


def pan_xy(u, d):
    a, b = PA - d, PB - d
    return rr_point(u, a, b, max(PR - d, 0.015))


def surf(u, d):
    """The pan's inner surface at perimeter position u and inset d (0 at the rim)."""
    (x, y), (ox, oy) = pan_xy(u, d)
    side = side_amt(u)
    dn = d * WALL / wall_w(u)
    h0 = profile_h(dn)
    wall = max(0.0, 1.0 - dn / WALL)
    if dn < WALL:
        h0 = 0.006 + (h0 - 0.006) * rim_scale(x, y, side)
    wob = 0.011 * nz(x * 7.0, y * 7.0, 2.1) * wall
    for y0 in HOOPS:
        wob += 0.011 * side * wall * math.exp(-((y - y0) / 0.028) ** 2)
    if d < 0.003 and abs(ox) > 0.5:
        h0 += 0.0025 * nz(0.0, y * 55.0, 3.3)  # the cut edge is ragged
    h0 += 0.0022 * nz(x * 8.0 + 5.0, y * 8.0, 0.3) * (1.0 - wall)
    return Vector((x + ox * wob, y + oy * wob, h0))


def surf_n(u, d):
    du, dd = 0.002, 0.001
    tu = surf(u + du, d) - surf(u - du, d)
    td = surf(u, d + dd) - surf(u, d)
    return tu.cross(td).normalized()


def drape_point(u, s, off, out_len):
    p = _drape_point(u, s, off, out_len)
    p.z = max(p.z, 0.0005)
    return p


def _drape_point(u, s, off, out_len):
    """A point on a sheet draped over the pan: s < 0 inside (inset -s), 0..1 round the rim, 1..2 down the outside
    of the wall, 2..3 out along the ground."""
    if s <= 0.0:
        return surf(u, -s) + surf_n(u, -s) * off
    if s <= 1.0:
        p0, n = surf(u, 0.0), surf_n(u, 0.0)
        w = (p0 - surf(u, 0.003)).normalized()
        c = p0 - n * (T / 2)
        phi = math.pi * s
        return c + (n * math.cos(phi) + w * math.sin(phi)) * (T / 2 + off)
    ww = wall_w(u)
    if s <= 2.0:
        d = (s - 1.0) * ww
        return surf(u, d) - surf_n(u, d) * (T + off)
    pb = surf(u, ww) - surf_n(u, ww) * T
    (_, _), (ox, oy) = pan_xy(u, ww)
    dist = (s - 2.0) * out_len
    fade = max(0.0, 1.0 - dist / 0.025)
    return Vector((pb.x + ox * dist, pb.y + oy * dist, max(pb.z, 0.0) * fade + off))


def drape(name, u0, hw, s_values, th, material, out_len=0.03, across=9, th_fn=None, hw_fn=None):
    bm = bmesh.new()
    rows = []
    for s in s_values:
        w = hw * (hw_fn(s) if hw_fn else 1.0)
        row = []
        for j in range(across):
            a = -1.0 + 2.0 * j / (across - 1)
            off = th * max(0.0, 1.0 - a * a) ** 0.35 + 0.0007
            if th_fn:
                off = th_fn(a, s, off)
            row.append(bm.verts.new(drape_point(u0 + a * w, s, off, out_len)))
        rows.append(row)
    for i in range(len(rows) - 1):
        for j in range(across - 1):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    return tk.smooth(tk.mesh_object(name, bm, material), 70)


def ring_mesh(name, rings, center, material):
    """Concentric rings (outer first, all the same count, counterclockwise) closed with a fan to `center`."""
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    c = bm.verts.new(center)
    n = len(rings[0])
    for k in range(len(vr) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((vr[k][i], vr[k][j], vr[k + 1][j], vr[k + 1][i]))
    for i in range(n):
        bm.faces.new((vr[-1][i], vr[-1][(i + 1) % n], c))
    return tk.mesh_object(name, bm, material)


def puddle(name, cx, cy, rx, ry, th, material, seed):
    rings = []
    for rho in (1.0, 0.86, 0.66, 0.4):
        ring = []
        for i in range(40):
            t = 2 * math.pi * i / 40
            rr = 1.0 + 0.2 * math.sin(3 * t + seed) + 0.12 * math.sin(5 * t + 2.1 * seed) + 0.07 * math.sin(9 * t + seed)
            ring.append((cx + rx * rr * rho * math.cos(t), cy + ry * rr * rho * math.sin(t),
                         th * (1.0 - rho * rho) ** 0.5 + 0.0004))
        rings.append(ring)
    return tk.smooth(ring_mesh(name, rings, (cx, cy, th + 0.0004), material), 70)


U = []
for k, count in enumerate((24, 6, 16, 6, 24, 6, 16, 6)):
    U += [k + j / count for j in range(count)]


def u_front(x):
    ca = PA - PR
    return 6.0 + (x + ca) / (2 * ca)


def u_left(y):
    cb = PB - PR
    return 4.0 + (cb - y) / (2 * cb)


def u_right(y):
    cb = PB - PR
    return (y + cb) / (2 * cb)


def u_back(x):
    ca = PA - PR
    return 2.0 + (ca - x) / (2 * ca)


group = []  # everything in the pan's frame

D_RINGS = [0.0, 0.005, 0.010, 0.016, 0.022, 0.03, 0.042, 0.055, 0.08, 0.12, 0.17, 0.23, 0.29, 0.335]
pan = ring_mesh("Pan", [[surf(u, d) for u in U] for d in D_RINGS], (0.0, 0.0, 0.004), drum)
tk.smooth(pan, 50)
group.append(solidify(pan, T))

# The drum's rolled chime along the back edge and the right half of the front
for name, u0, u1 in (("ChimeBack", u_back(0.33), u_back(-0.33)), ("ChimeFront", u_front(0.02), u_front(0.33))):
    pts = []
    for i in range(25):
        u = u0 + (u1 - u0) * i / 24
        p, n = surf(u, 0.0), surf_n(u, 0.0)
        pts.append(tuple(p - n * 0.0025 + Vector((0, 0, 0.0015))))
    group.append(tk.tube(name, pts, 0.0055, drum, resolution=3))

# The grease: a slightly rippled surface meeting the walls just below the rim
G_RINGS = [0.004, 0.012, 0.025, 0.04, 0.06, 0.09, 0.13, 0.18, 0.23, 0.28, 0.32]
grings = []
for d in G_RINGS:
    ring = []
    for u in U:
        p = surf(u, d)
        meniscus = 0.0012 * math.exp(-d / 0.01)
        h = GL + meniscus + 0.002 * nz(p.x * 6.0, p.y * 6.0, 7.0) + 0.0008 * nz(p.x * 17.0, p.y * 17.0, 1.0)
        ring.append((p.x, p.y, h))
    grings.append(ring)
group.append(tk.smooth(ring_mesh("GreaseTop", grings, (0.0, 0.0, GL + 0.0008), grease), 80))

# Slopped over the low spot in the front lip and spreading on the ground
S_SLOP = [-0.05, -0.035, -0.022, -0.014, -0.008, -0.003, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25,
          2.5, 2.75, 3.0]
u0 = u_front(SPILL_X)
hw = 0.07 / (2 * (PA - PR))
group.append(drape("GreaseSlop", u0, hw, S_SLOP, 0.0055, grease, out_len=0.035, across=11,
                   hw_fn=lambda s: 1.0 + 0.2 * math.sin(s * 2.7 + 0.4) + (0.25 * (s - 2.0) if s > 2.0 else 0.0)))
group.append(puddle("GreasePuddle", SPILL_X - 0.012, -PB - 0.012, 0.105, 0.052, 0.0035, grease, 1.7))
# Drips down the outside, and a smear over the right lip
for name, u, w, s_end in (("Drip", u_front(-0.31), 0.009, 2.2),
                          ("Drip", u_right(-0.05), 0.011, 2.3)):
    group.append(drape(name, u, w / (2 * (PA - PR)), [-0.02, -0.01, -0.004, 0.0, 0.33, 0.66, 1.0, 1.3, 1.6, 1.9,
                                                      2.0, s_end], 0.0028, grease, out_len=0.02, across=5,
                       hw_fn=lambda s: 1.0 + 0.6 * max(0.0, s - 1.8)))

# A filthy shop rag hung over the left side, its inner end soaking in the grease
S_RAG = [-0.07, -0.055, -0.04, -0.028, -0.018, -0.01, -0.004, 0.0, 0.25, 0.5, 0.75, 1.0, 1.3, 1.6, 2.0, 2.3, 2.6]


def rag_th(a, s, off):
    crumple = 0.007 * (0.6 + noise.noise(Vector((a * 2.4, s * 3.3, 4.2)))) + 0.003 * math.sin(a * 8.0 + s * 5.0)
    return 0.0025 + max(0.0, crumple)


rag = drape("Rag", u_left(-0.06), 0.09 / (2 * (PB - PR)), S_RAG, 0.0, rag_cloth, out_len=0.018, across=9,
            th_fn=rag_th, hw_fn=lambda s: 1.0 + 0.15 * math.sin(s * 4.0) - (0.12 * (s + 0.07) / 0.07 if s < 0 else 0))
group.append(solidify(rag, 0.002, 1.0, even=False))

# ---------------------------------------------------------------- a dented quart of motor oil, tipped over

CR, CL = 0.047, 0.0675
can = []
body = tk.cylinder("CanBody", CR, -CL, CL, can_paint, segments=24, axis="X", rings=5, caps=False)
tk.dent(body, 0.004, 0.03, seed=2)
push(body, (0.012, 0.0, CR), 0.035, (0.0, 0.0, -0.011))  # stepped on
push(body, (-0.04, -CR, 0.0), 0.03, (0.0, 0.007, 0.0))
can.append(body)
body.data.materials.append(can_band)
for poly in body.data.polygons:
    if -0.0225 < poly.center.x < 0.0225:
        poly.material_index = 1
for sx in (-1, 1):
    can.append(tk.cylinder("CanLid", CR - 0.002, sx * CL - 0.001, sx * CL + 0.001, tin, segments=24, axis="X"))
    chime = tk.torus("CanChime", CR - 0.001, 0.0032, (0.0, 0.0, 0.0), tin, 24, 6)
    chime.matrix_world = Matrix.Translation((sx * (CL + 0.0005), 0, 0)) @ Matrix.Rotation(math.radians(90), 4, "Y")
    can.append(chime)
hole = tk.flat_shape("CanHole", [(-0.022, 0.0), (-0.037, -0.012), (-0.037, 0.012)], 0.0012, grease,
                     (CL + 0.001, 0.0, 0.0), rotation=(0.0, 90.0, 0.0))
can.append(hole)
CAN = Matrix.Translation((0.255, -0.245, 0.004 + CR - 0.001)) @ Matrix.Rotation(math.radians(132), 4, "Z") \
    @ Matrix.Rotation(math.radians(-14), 4, "X")
for o in can:
    bake_transform(o)
    o.data.transform(CAN)
    group.append(o)
mouth = CAN @ Vector((CL + 0.002, 0.0, 0.03))
spout_dir = (CAN.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
land = mouth + spout_dir * 0.03
land.z = GL - 0.003
group.append(tk.tube("Ooze", [tuple(mouth), tuple(mouth + spout_dir * 0.012 + Vector((0, 0, -0.008))), tuple(land)],
                     0.0065, grease, resolution=3))

# ---------------------------------------------------------------- into the block, join

for o in group:
    bake_transform(o)
    o.data.transform(PAN)

model = tk.triangulate(tk.join(group, "GreaseSlick"))
tk.smart_uvs(model)

xs = [v.co.x for v in model.data.vertices]
ys = [v.co.y for v in model.data.vertices]
zs = [v.co.z for v in model.data.vertices]
print("[grease_slick] bounds x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (min(xs), max(xs), min(ys), max(ys), min(zs),
                                                                       max(zs)))

# ---------------------------------------------------------------- bake and export

paths = tk.bake_atlas(model, ASSETS, "GreaseSlick_Atlas")
baked = tk.baked_material("GreaseSlick_Atlas", paths)
model.data.materials.clear()
model.data.materials.append(baked)

tk.export_fbx([model], os.path.join(ASSETS, "GreaseSlick.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[grease_slick] triangles:", tris)

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.15, -1.55, 0.45), (0, -0.04, z(0.02)), lens=45),
          os.path.join(PREVIEWS, "grease_slick_front.png"))
tk.render(tk.camera("Back", (-1.25, 1.35, 0.55), (0, 0, z(0.02)), lens=45), os.path.join(PREVIEWS, "grease_slick_back.png"))
tk.render(tk.camera("Close", (0.32, -0.78, -0.2), (0.02, -0.22, z(0.02)), lens=50),
          os.path.join(PREVIEWS, "grease_slick_close.png"))
tk.icon(tk.camera("Icon", (1.25, -1.8, 0.52), (0, -0.03, z(0.02)), lens=72), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.03)))
print("[grease_slick] done")
