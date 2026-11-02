"""Cryo Vent: a 1x1 floor block, at most 0.25 m tall, that zombies walk across. A rusty steel bar grate on a low
angle-iron frame over a drip tray, with a serpentine copper fridge coil under it; a car A/C compressor shimmed on wood
offcuts beside it (pulley to the front), a chunk of A/C condenser standing on the other side, and the rubber hoses
between them. Frost and ice rime crust the coil and the grate; icicles hang from the front rail. A small rusty
junction box with the power lamp hangs on the front rail.

The model carries one empty for the game: VentPoint at the top center of the grate.

    blender -b --factory-startup --python cryo_vent.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(3301)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


# ---------------------------------------------------------------- local helpers

def turn(obj, axis, degrees, pivot):
    """Rotates an object about an axis through `pivot` (world)."""
    p = Vector(pivot)
    obj.matrix_world = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(degrees), 4, axis)
                        @ Matrix.Translation(-p)) @ obj.matrix_world
    return obj


def along(obj, start, direction):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(start)) @ rot @ obj.matrix_world
    return obj


def plate(name, size, center, mat, bw=0.0015):
    """A box with a single chamfer (cheap on triangles, still catches the edge wear)."""
    obj = tk.box(name, size, center, mat)
    if bw:
        tk.bevel(obj, bw, segments=1)
        tk.smooth(obj)
    return obj


def sag_bar(name, size, center, mat, sag, cuts=8):
    """A box along Y that sags (bent down) in the middle."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    edges = [e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) > 1e-6]
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        t = (v.co.y + size[1] / 2) / size[1]
        v.co.z -= sag * max(0.0, math.sin(math.pi * t)) ** 1.5
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return tk.smooth(tk.mesh_object(name, bm, mat))


def lump(name, center, scale, rot_z, mat, subdiv=1, rough=0.18):
    """A lumpy, faceted crust (ice rime)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        v.co *= 1.0 + rnd.uniform(-rough, rough)
    obj = tk.mesh_object(name, bm, mat)
    obj.matrix_world = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(rot_z), 4, "Z")
                        @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)))
    return tk.smooth(obj, 50)


def icicle(name, x, y, top, length, radius, mat):
    """A tapered icicle hanging from `top`, slightly bent."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=7, radius1=radius * 0.08, radius2=radius,
                          depth=length)
    for v in bm.verts:
        t = (length / 2 - v.co.z) / length  # 0 at the top, 1 at the tip
        v.co.x += 0.002 * t * t + rnd.uniform(-0.0006, 0.0006)
        v.co.y += 0.0015 * t * t
    bmesh.ops.translate(bm, vec=(x, y, top - length / 2), verts=bm.verts)
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


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


def resample(points, step):
    pts = [Vector(p) for p in points]
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        d = step - carry
        while d <= seg:
            out.append(a.lerp(b, d / seg))
            d += step
        carry = seg - (d - step)
    return out


# ---------------------------------------------------------------- frost materials

def frost_layer(g, color, rough, metal, height, amount, scale=5.0, up=0.6, seed=(0.0, 0.0, 0.0), edge=0.7,
                center=0.0):
    """White crystalline frost with a faint blue tint: patches (more on upward faces, and toward the middle of the
    vent with `center`) that are solid in the middle and break up into fine grain at their edges, plus rime growing
    on the sharp edges."""
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Location"].default_value = seed
    blot = g.noise(scale, detail=6.0, roughness=0.62, distortion=0.4, vector=m.outputs[0])
    nz = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    field = g.math("ADD", blot, g.math("MULTIPLY", g.ramp(nz, -0.4, 0.9), up * 0.25))
    if center:
        # the joined model's object space is the block's space, centered on the vent
        x, y, _ = g.separate(g.coords())
        r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
        field = g.math("ADD", field, g.math("MULTIPLY", g.ramp(r, 0.45, 0.05), center * 0.3))
    t = 0.8 - 0.5 * amount
    cover = g.ramp(field, t - 0.08, t + 0.02)
    solid = g.ramp(field, t + 0.0, t + 0.07)
    grain = g.ramp(g.noise(140.0, detail=6.0, roughness=0.75), 0.36, 0.6)
    mask = g.math("MULTIPLY", cover, g.mixf(solid, grain, 1.0))
    if edge:
        rim = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.08, 0.25), g.ramp(g.noise(35.0, detail=4.0), 0.35, 0.6))
        mask = g.math("MAXIMUM", mask, g.math("MULTIPLY", rim, edge * amount, clamp=True))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 260.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    crystal = tk._luma(g, tk._sock(vor.outputs, "Color"))
    glint = g.ramp(crystal, 0.62, 0.8)
    fc = g.mix(crystal, (0.64, 0.68, 0.73), (0.83, 0.86, 0.9))
    fc = g.mix(g.math("MULTIPLY", g.ramp(g.noise(11.0, detail=4.0), 0.45, 0.75), 0.6), fc, (0.6, 0.69, 0.8))
    color = g.mix(mask, color, fc)
    rough = g.mixf(mask, rough, g.mixf(glint, 0.85, 0.45))
    metal = g.mixf(mask, metal, 0.0)
    height = g.mixf(mask, height, g.math("ADD", 0.7, g.math("MULTIPLY", crystal, 0.3)))
    return color, rough, metal, height


def photo_signals(g, base, scale=0.5, sat=1.0, value=1.0, tint=None, exposed="rust_coarse_01", chip=0.5, grime=0.6,
                  streaks=0.0, offset=(0.0, 0.0, 0.0), metal_scale=1.0, ao=0.6, patches=0.0, metal_floor=0.0,
                  rough_scale=1.0, grit=0.0, scratches=0.0, edges=0.0, contrast=0.0):
    """The signal chain of trapkit.photo_material, returned before it is finished so frost can go on top."""
    p = tk.photo(g, base, scale, offset)
    color = tk.grade(g, p["color"], sat, value, tint)
    if contrast:
        bc = g.node("ShaderNodeBrightContrast")
        g._in(bc, "Color", color)
        g._in(bc, "Contrast", contrast)
        color = bc.outputs[0]
    rough = p["rough"]
    metal = g.math("MULTIPLY", p["metal"], metal_scale)
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
    return color, rough, metal, height


def frosted_photo(name, base, frost, frost_scale=5.0, frost_seed=(0.0, 0.0, 0.0), frost_edge=0.7, frost_center=0.0,
                  frost_up=0.6,
                  bump=0.35, **kw):
    mat, g = tk.new_material(name)
    color, rough, metal, height = photo_signals(g, base, **kw)
    if frost:
        color, rough, metal, height = frost_layer(g, color, rough, metal, height, frost, frost_scale, seed=frost_seed,
                                                  edge=frost_edge, center=frost_center, up=frost_up)
    return tk.finish(mat, g, color, metal, rough, g.bump(height, bump, 0.01))


def frosted_copper(name, frost, bright=(0.92, 0.5, 0.28), dark=(0.66, 0.31, 0.16), up=0.9):
    """trapkit.tarnished_copper with frost on top."""
    mat, g = tk.new_material(name)
    p = tk.photo(g, "rust_coarse_01", 1.2, (0.4, 0.2, 0.9))
    tarnish = g.ramp(tk._luma(g, p["color"]), 0.2, 0.1)
    cav = g.cavity(0.04)
    col = g.mix(g.math("MULTIPLY", g.noise(30.0), 0.4), bright, dark)
    col = g.mix(g.math("MULTIPLY", tarnish, 0.9), col, (0.13, 0.07, 0.04))
    green = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.3, clamp=True)
    col = g.mix(g.math("MULTIPLY", green, 0.75), col, (0.12, 0.24, 0.17))
    metal = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("MAXIMUM", tarnish, green), 0.75))
    rough = g.mixf(tarnish, g.math("ADD", 0.26, g.math("MULTIPLY", g.noise(12.0), 0.2)), 0.7)
    col, rough, metal = tk._grit(g, col, rough, metal, 0.6)
    height = g.math("MULTIPLY", p["height"], 0.5)
    col, rough, metal, height = frost_layer(g, col, rough, metal, height, frost, 6.0, up=up, seed=(0.3, 0.6, 0.1),
                                            edge=0.0, center=0.3)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.004))


def frosted_grimy(name, color, frost, roughness=0.55, metallic=0.0, grime=0.5, grit=0.0, dirt_range=(0.4, 0.12),
                  scale=0.7):
    """trapkit.grimy (no soot or stain) with frost on top."""
    mat, g = tk.new_material(name)
    p = tk.photo(g, "metal_plate_02", scale, (0.21, 0.5, 0.13))
    pattern = g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1])
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", pattern, grime), tk._grime(g, grime * 1.4), clamp=True)
    col = g.mix(g.math("MULTIPLY", g.noise(18.0), 0.25), color, tuple(c * 0.8 for c in color))
    col = g.mix(dirt, col, (0.06, 0.05, 0.04))
    rough = g.mixf(dirt, roughness, 0.85)
    col, rough, metal = tk._grit(g, col, rough, metallic, grit)
    height = g.math("MULTIPLY", g.noise(60.0, detail=6.0), 0.3)
    if frost:
        col, rough, metal, height = frost_layer(g, col, rough, metal, height, frost, 7.0, seed=(0.8, 0.2, 0.5),
                                                edge=0.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.15, 0.003))


def rime(name):
    """Thick ice rime: grey-blue ice crusted over with white frost."""
    mat, g = tk.new_material(name)
    base = g.mix(g.ramp(g.noise(9.0, detail=5.0), 0.3, 0.7), (0.34, 0.41, 0.48), (0.5, 0.56, 0.62))
    height = g.math("MULTIPLY", g.noise(40.0, detail=6.0), 0.5)
    color, rough, metal, height = frost_layer(g, base, 0.3, 0.0, height, 0.8, 9.0, up=1.0, seed=(0.5, 0.5, 0.5),
                                              edge=1.0)
    color, rough, metal = tk._grit(g, color, rough, metal, 0.2)
    return tk.finish(mat, g, color, metal, rough, g.bump(height, 0.5, 0.004))


# ---------------------------------------------------------------- scene and materials

tk.reset_scene()
tk.preview_stage()

frame = frosted_photo("Frame", "green_metal_rust", 0.2, frost_scale=4.0, frost_seed=(0.1, 0.4, 0.0), frost_edge=0.3,
                      frost_center=0.6, scale=1.9,
                      sat=0.25, value=1.0, chip=1.0, grime=0.9, streaks=1.2, patches=0.9, metal_floor=0.4,
                      rough_scale=0.85, grit=1.0, scratches=0.5, edges=0.35, contrast=0.12)
grate_mat = frosted_photo("Grate", "rust_coarse_01", -0.1, frost_scale=4.5, frost_seed=(0.7, 0.2, 0.3), frost_edge=0.0,
                          frost_up=1.4,
                          frost_center=0.5, scale=2.2, sat=0.85, value=0.8, exposed=None, grime=0.9, metal_floor=0.1,
                          rough_scale=0.95, grit=0.9, scratches=0.15, edges=0.0, contrast=0.15)
tray_mat = frosted_photo("Tray", "rust_coarse_01", 0.12, frost_scale=3.5, frost_center=0.6, scale=2.3, value=0.95,
                         exposed=None, grime=0.9, metal_floor=0.3, grit=0.9, streaks=0.6)
alu = frosted_photo("Alu", "metal_plate_02", 0.15, frost_scale=6.0, frost_seed=(0.2, 0.9, 0.4), frost_edge=0.3,
                    scale=2.6, sat=0.0, value=1.3, exposed="rust_coarse_01", chip=0.3, patches=0.15, grime=1.0,
                    metal_floor=0.5, rough_scale=0.9, grit=1.0, scratches=0.35, edges=0.6, contrast=0.1)
fins_mat = frosted_photo("Fins", "metal_plate_02", 0.4, frost_scale=6.0, frost_seed=(0.9, 0.1, 0.7), frost_edge=0.2,
                         scale=3.0, sat=0.0, value=1.3, exposed="rust_coarse_01", chip=0.2, patches=0.3, grime=1.0,
                         metal_floor=0.55, grit=1.0, scratches=0.3, edges=0.5)
copper = frosted_copper("CoilCopper", -0.1, up=1.4)
hose = frosted_grimy("Hose", (0.03, 0.03, 0.03), 0.3, roughness=0.7, grime=0.5, grit=0.9)
ice = rime("Rime")
steel = tk.photo_material("Steel", "metal_plate_02", scale=2.4, sat=0.3, value=0.8, exposed="rust_coarse_01",
                          chip=1.0, patches=0.45, grime=0.9, metal_floor=0.55, grit=0.9, scratches=0.5, edges=0.8)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
wood = tk.photo_material("Wood", "weathered_planks", scale=0.8, value=1.1, exposed=None, grime=0.8, bump=0.6, grit=0.6,
                         contrast=0.2)
red_box = tk.photo_material("RedBox", "rusty_painted_metal", scale=1.8, sat=1.0, value=1.15, chip=1.0, grime=0.8,
                            patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55, edges=0.8,
                            contrast=0.12)
blue_cap = tk.grimy("BlueCap", (0.04, 0.12, 0.42), roughness=0.45, grime=0.5, grit=0.5, dirt_range=(0.1, 0.03))
red_cap = tk.grimy("RedCap", (0.42, 0.04, 0.03), roughness=0.45, grime=0.5, grit=0.5, dirt_range=(0.1, 0.03))
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
tape = tk.grimy("Tape", (0.02, 0.02, 0.022), roughness=0.42, grime=0.25, bump_scale=35.0)
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append

G = 0.33      # frame and grate half size
TOP = 0.17    # top of the frame rails: the grate sits on them
GT = 0.025    # grate bar height
GRATE_TOP = TOP + GT
ANG = 0.035   # angle iron flange

# ---------------------------------------------------------------- drip tray under the grate

TR = 0.3
tray_floor = plate("TrayFloor", (2 * TR, 2 * TR, 0.004), (0.0, 0.0, z(0.0045)), tray_mat, 0.001)
add(tk.dent(tray_floor, 0.0015, 0.15, seed=2))
for s in (-1, 1):
    w = plate("TrayWall", (0.004, 2 * TR, 0.026), (TR * s, 0.0, z(0.015)), tray_mat, 0.001)
    add(turn(w, "Y", 8 * s, (TR * s, 0.0, z(0.004))))
    w = plate("TrayWall", (2 * TR, 0.004, 0.026), (0.0, TR * s, z(0.015)), tray_mat, 0.001)
    add(turn(w, "X", -8 * s, (0.0, TR * s, z(0.004))))

# ---------------------------------------------------------------- angle-iron frame

for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = G * sx, G * sy
        h = TOP - 0.005
        add(plate("LegA", (0.004, ANG, h), (cx - 0.002 * sx, cy - ANG / 2 * sy, z(0.005 + h / 2)), frame))
        add(plate("LegB", (ANG, 0.004, h), (cx - ANG / 2 * sx, cy - 0.002 * sy, z(0.005 + h / 2)), frame))
        foot = plate("Foot", (0.06, 0.06, 0.005), (cx - 0.022 * sx, cy - 0.022 * sy, z(0.0025)), frame, 0.001)
        add(turn(foot, "Z", jitter(6), (cx, cy, Z)))
for s in (-1, 1):
    add(plate("RailTop", (2 * G, ANG, 0.004), (0.0, (G - ANG / 2) * s, z(TOP - 0.002)), frame))
    add(plate("RailSide", (2 * G, 0.004, 0.016), (0.0, (G - 0.002) * s, z(TOP - 0.008)), frame))
    add(plate("RailTop", (ANG, 2 * G - 0.01, 0.004), ((G - ANG / 2) * s, 0.0, z(TOP - 0.0055)), frame))
    add(plate("RailSide", (0.004, 2 * G - 0.01, 0.016), ((G - 0.002) * s, 0.0, z(TOP - 0.0095)), frame))

# ---------------------------------------------------------------- bar grate (bars run front to back)

grate = []
for s in (-1, 1):
    grate.append(plate("GrateBorder", (2 * G, 0.006, GT), (0.0, (G - 0.003) * s, z(TOP + GT / 2)), grate_mat, 0.0012))
    grate.append(plate("GrateBorder", (0.006, 2 * G - 0.012, GT), ((G - 0.003) * s, 0.0, z(TOP + GT / 2)), grate_mat,
                       0.0012))
bar_xs = [-0.3 + 0.05 * i for i in range(13)]
for i, x in enumerate(bar_xs):
    if i in (5, 6):  # two bars bent down where something heavy landed on them
        grate.append(sag_bar("GrateBar", (0.006, 2 * G - 0.008, GT), (x, 0.0, z(TOP + GT / 2)), grate_mat,
                             0.011 if i == 5 else 0.007))
    else:
        grate.append(plate("GrateBar", (0.006, 2 * G - 0.008, GT), (x + jitter(0.0015), 0.0, z(TOP + GT / 2)),
                           grate_mat, 0.001))
for y in (-0.165, 0.0, 0.165):
    grate.append(tk.cylinder("CrossRod", 0.004, -G, G, grate_mat, segments=6, center=(y, z(GRATE_TOP - 0.0045)),
                             axis="X"))
# Rime crusted along some bar tops
for k in range(10):
    bx = rnd.choice(bar_xs[1:12])
    y0 = rnd.uniform(-0.3, 0.22)
    crust = tk.tube("BarRime", [(bx, y, z(GRATE_TOP + 0.0004)) for y in (y0, y0 + 0.02, y0 + 0.04, y0 + 0.06)],
                    0.0042, ice, resolution=1)
    grate.append(tk.dent(crust, 0.0015, 0.006, seed=40 + k))
for o in grate:
    turn(o, "Z", 1.4, (0.0, 0.0, z(GRATE_TOP)))
    turn(o, "X", 0.4, (0.0, 0.0, z(GRATE_TOP)))
    add(o)

# Icicles hanging from the front rail and a crust of rime along its lower edge
for x in (-0.27, -0.252, -0.17, -0.06, -0.042, -0.03, 0.06, 0.12, 0.137, 0.23):
    add(icicle("Icicle", x + jitter(0.005), -G - 0.0005, z(TOP - 0.014), rnd.uniform(0.018, 0.05),
               rnd.uniform(0.006, 0.0095), ice))

# ---------------------------------------------------------------- serpentine copper fridge coil under the grate

CH = z(0.145)
for x in (-0.15, 0.15):
    add(plate("CoilBar", (0.025, 0.6, 0.005), (x + jitter(0.01), 0.0, z(0.135)), frame, 0.001))
    for y in (-0.28, 0.28):
        add(plate("CoilPost", (0.02, 0.02, 0.128), (x, y, z(0.07)), frame, 0.001))
RUNS = [0.27 - 0.054 * i for i in range(11)]   # back to front
XA, XB, BR = -0.25, 0.25, 0.027
coil = [(-0.315, RUNS[0], CH), (XA, RUNS[0], CH)]
bends = []
for i, y in enumerate(RUNS):
    xa, xb = (XA, XB) if i % 2 == 0 else (XB, XA)
    for t in (0.33, 0.67):
        coil.append((xa + (xb - xa) * t, y + jitter(0.0025), CH + jitter(0.002)))
    coil.append((xb, y, CH))
    if i < len(RUNS) - 1:
        s = 1 if xb > 0 else -1
        for k in range(1, 6):
            a = math.pi / 2 - math.pi * k / 6
            p = (xb + s * BR * math.cos(a), y - BR + BR * math.sin(a), CH)
            coil.append(p)
            if k == 3:
                bends.append(p)
        coil.append((xb, RUNS[i + 1], CH))
# Tail out the right side, under the rail, into the condenser's side stub
coil += [(0.3, RUNS[-1], CH), (0.33, RUNS[-1] - 0.004, z(0.142)), (0.35, RUNS[-1] - 0.014, z(0.142)),
         (0.358, RUNS[-1] - 0.017, z(0.142))]
coil[0] = (-0.34, RUNS[0], CH)
add(tk.tube("Coil", coil, 0.0075, copper, resolution=2))
add(tk.cylinder("FlareNut", 0.012, -0.36, -0.338, steel, segments=6, center=(RUNS[0], CH), axis="X"))
add(tk.cylinder("FlareNut", 0.011, 0.344, 0.36, steel, segments=6, center=(RUNS[-1] - 0.016, z(0.142)), axis="X"))
COIL_IN = Vector((-0.36, RUNS[0], CH))
# Rime crusted along the coil in sleeves, and icicles under the bends
dense = resample(coil[:-4], 0.007)
used = set()
for k in range(16):
    n = rnd.randint(8, 26)
    start = rnd.randint(2, len(dense) - n - 2)
    if any(i in used for i in range(start - 3, start + n + 3)):
        continue
    used.update(range(start, start + n))
    seg = [tuple(p + Vector((0.0, 0.0, 0.0018))) for p in dense[start:start + n]]
    sleeve = tk.tube("CoilRime", seg, rnd.uniform(0.0088, 0.0098), ice, resolution=1)
    add(tk.dent(sleeve, 0.002, 0.005, seed=10 + k))
for p in bends[::2]:
    add(icicle("Icicle", p[0] + jitter(0.004), p[1] + jitter(0.004), CH - 0.005, rnd.uniform(0.014, 0.03),
               rnd.uniform(0.0035, 0.005), ice))

# ---------------------------------------------------------------- car A/C compressor (left strip, pulley to the front)

CX, CZ = -0.4, z(0.072)
F = -0.138  # shifts the compressor (built with its rear face at y = 0) back to the front


def comp_cyl(name, r, y0, y1, mat, seg=28, bw=0.0, rings=0, caps=True):
    return tk.cylinder(name, r, y0 + F, y1 + F, mat, segments=seg, center=(CX, CZ), axis="Y", bevel_width=bw,
                       rings=rings, caps=caps)


comp = [
    comp_cyl("CompBody", 0.057, -0.205, -0.03, alu, rings=3),
    comp_cyl("CompRear", 0.06, -0.036, 0.0, alu, bw=0.005),
    comp_cyl("CompFront", 0.063, -0.24, -0.2, alu, bw=0.005),
    comp_cyl("CompNose", 0.03, -0.255, -0.238, alu, seg=16),
    comp_cyl("Pulley", 0.056, -0.296, -0.252, steel, bw=0.002),
    comp_cyl("PulleyLip", 0.065, -0.299, -0.294, steel),
    comp_cyl("PulleyLip", 0.065, -0.255, -0.25, steel),
    comp_cyl("Clutch", 0.05, -0.307, -0.299, steel, bw=0.002),
    comp_cyl("Hub", 0.017, -0.316, -0.306, steel, seg=16),
    tk.cylinder("HubNut", 0.009, -0.322 + F, -0.315 + F, rust, segments=6, center=(CX, CZ), axis="Y"),
]
tk.dent(comp[0], 0.0015, 0.05, seed=3)
for k in range(5):
    y = -0.29 + k * 0.0075
    comp.append(comp_cyl("PulleyRib", 0.062, y, y + 0.0035, steel, seg=28))
for k in range(3):
    a = math.radians(90 + 120 * k)
    comp.append(tk.cylinder("Rivet", 0.0045, -0.311 + F, -0.306 + F, steel, segments=8,
                            center=(CX + 0.034 * math.cos(a), CZ + 0.034 * math.sin(a)), axis="Y"))
for k in range(8):  # cast ribs along the body
    a = math.radians(22.5 + 45 * k)
    rib = tk.box("CompRib", (0.006, 0.165, 0.008), (0.0, -0.118 + F, 0.057), alu)
    rib.matrix_world = (Matrix.Translation((CX, 0.0, CZ)) @ Matrix.Rotation(a, 4, "Y")) @ rib.matrix_world
    comp.append(rib)
for s in (-1, 1):
    for y in (-0.222, -0.018):
        comp.append(plate("Ear", (0.024, 0.026, 0.02), (CX + 0.056 * s, y + F, CZ + 0.034), alu, 0.003))
        comp.append(tk.cylinder("EarBolt", 0.0055, y + F - 0.02, y + F + 0.02, rust, segments=6,
                                center=(CX + 0.06 * s, CZ + 0.036), axis="Y"))
# Suction and discharge ports on the rear head, with service valves (blue cap low side, red cap high side)
PORTS = []
for s, cap in ((-1, blue_cap), (1, red_cap)):
    px = CX + 0.024 * s
    comp.append(plate("PortBlock", (0.026, 0.032, 0.022), (px, -0.045 + F, CZ + 0.068), alu, 0.003))
    comp.append(tk.cylinder("PortBolt", 0.005, CZ + 0.079, CZ + 0.084, rust, segments=6, center=(px, -0.034 + F)))
    comp.append(tk.cylinder("Valve", 0.0055, CZ + 0.076, CZ + 0.09, alu, segments=10, center=(px + 0.014 * s, -0.062 + F)))
    comp.append(tk.cylinder("ValveCap", 0.0075, CZ + 0.09, CZ + 0.101, cap, segments=12,
                            center=(px + 0.014 * s, -0.062 + F), bevel_width=0.0015))
    PORTS.append(Vector((px, -0.045 + F, CZ + 0.079)))
# Hold-down strap and the wood shims it sits on
comp.append(comp_cyl("Strap", 0.0595, -0.13, -0.112, rust, caps=False))
for s in (-1, 1):
    comp.append(plate("StrapTab", (0.02, 0.018, 0.004), (CX + 0.064 * s, -0.121 + F, z(0.003)), rust, 0.001))
for y in (-0.17, -0.06):
    shim = plate("Shim", (0.12, 0.04, 0.013), (CX + jitter(0.005), y + F, z(0.0085)), wood, 0.002)
    comp.append(turn(shim, "Z", jitter(6), (CX, y + F, Z)))
comp.append(plate("ClutchPlug", (0.014, 0.02, 0.018), (CX + 0.066, -0.225 + F, CZ - 0.02), rubber, 0.002))
for o in comp:  # rolled a little on its shims (the shims and strap tabs stay flat on the floor)
    add(o if o.name.startswith(("Shim", "StrapTab")) else turn(o, "Y", 5.0, (CX, 0.0, CZ)))
roll = Matrix.Translation((CX, 0, CZ)) @ Matrix.Rotation(math.radians(5.0), 4, "Y") @ Matrix.Translation((-CX, 0, -CZ))
PORTS = [roll @ p for p in PORTS]
clutch_lead = roll @ Vector((CX + 0.074, -0.225 + F, CZ - 0.02))

# ---------------------------------------------------------------- chunk of car A/C condenser (right strip, standing)

W = 0.56
cond = []
for s in (-1, 1):
    cond.append(plate("Tank", (0.026, 0.036, 0.205), ((W / 2 - 0.013) * s, 0.0, 0.0), alu, 0.004))
for k in range(7):
    cond.append(tk.box("FlatTube", (W - 0.04, 0.022, 0.0035), (0.0, 0.0, -0.09 + 0.03 * k), fins_mat))
NF = 50
for k in range(NF):
    x = -(W / 2 - 0.03) + (W - 0.06) * k / (NF - 1)
    if k < NF - 6:
        cond.append(tk.box("Fin", (0.0012, 0.021, 0.196), (x, 0.0, 0.0), fins_mat))
    else:  # a crushed corner: the tops of the last fins folded over
        cond.append(tk.box("Fin", (0.0012, 0.021, 0.136), (x, 0.0, -0.03), fins_mat))
        f = tk.box("FinBent", (0.0012, 0.021, 0.06), (x, 0.0, 0.068), fins_mat)
        cond.append(turn(f, "Y", -(28 + 8 * (k - NF + 6)), (x, 0.0, 0.038)))
for s in (-1, 1):
    cond.append(tk.cylinder("Stub", 0.008, 0.1, 0.13, alu, segments=10, center=((W / 2 - 0.013) * s, 0.0)))
    cond.append(tk.cylinder("StubNut", 0.011, 0.122, 0.134, steel, segments=6, center=((W / 2 - 0.013) * s, 0.0)))
# Outlet: a stub off the front tank pointing in at the coil; inlet: a stub off the back end of the back tank
cond.append(tk.cylinder("SideStub", 0.008, 0.016, 0.05, alu, segments=10, center=(-(W / 2 - 0.013), 0.03), axis="Y"))
cond.append(tk.cylinder("EndStub", 0.008, W / 2, W / 2 + 0.03, alu, segments=10, center=(0.0, 0.06), axis="X"))
cond.append(tk.cylinder("EndNut", 0.011, W / 2 + 0.018, W / 2 + 0.03, steel, segments=6, center=(0.0, 0.06), axis="X"))
COND_M = (Matrix.Translation((0.405, -0.02, z(0.112))) @ Matrix.Rotation(math.radians(-7), 4, "Y")
          @ Matrix.Rotation(math.radians(90), 4, "Z"))
for o in cond:
    o.matrix_world = COND_M @ o.matrix_world
    add(o)
cond_in = COND_M @ Vector((W / 2 + 0.03, 0.0, 0.06))
cond_dir = (COND_M.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
print("[cryo_vent] condenser outlet stub end:", tuple(round(c, 3) for c in COND_M @ Vector((-(W / 2 - 0.013), 0.05,
                                                                                               0.03))))
for y in (-0.22, 0.18):  # wood blocks it stands on
    add(plate("CondBlock", (0.07, 0.05, 0.016), (0.4, y - 0.02, z(0.0082)), wood, 0.002))
for y, ly in ((-0.29, -G + 0.004), (0.25, G - 0.004)):  # bent straps to the frame legs
    add(tk.tube("CondStrap", [(0.392, y, z(0.15)), (0.36, (y + ly) / 2, z(0.152)), (G + 0.002, ly, z(0.15))],
                0.003, rust, resolution=1))

# ---------------------------------------------------------------- hoses with crimped fittings


def hose_run(name, ctrl, radius=0.011, per=5):
    pts = smooth_path(ctrl, per)
    add(tk.tube(name, pts, radius, hose, resolution=2))
    for p, q in ((pts[0], pts[1]), (pts[-1], pts[-2])):
        d = Vector(q) - Vector(p)
        add(along(tk.cylinder("Ferrule", radius + 0.003, 0.0, 0.028, alu, segments=10), p, d))


p_lo, p_hi = PORTS
hose_run("SuctionHose", [p_lo, p_lo + Vector((0.0, 0.0, 0.015)), Vector((-0.43, -0.09, z(0.17))),
                         Vector((-0.42, 0.14, z(0.16))), Vector((-0.385, RUNS[0], CH + 0.004)), COIL_IN])
hose_run("DischargeHose", [p_hi, p_hi + Vector((0.0, 0.0, 0.012)), Vector((-0.35, -0.11, z(0.12))),
                           Vector((-0.39, 0.12, z(0.04))), Vector((-0.38, 0.4, z(0.03))), Vector((-0.05, 0.415, z(0.03))),
                           Vector((0.28, 0.41, z(0.04))), Vector((0.39, 0.38, z(0.1))), cond_in + cond_dir * 0.045,
                           cond_in])
add(tk.cylinder("HoseTape", 0.0135, -0.015, 0.015, tape, segments=12, center=(0.415, z(0.03)), axis="X"))
add(tk.cylinder("HoseTape", 0.0135, 0.1, 0.13, tape, segments=12, center=(0.414, z(0.03)), axis="X"))

# ---------------------------------------------------------------- junction box with the power lamp (front rail)

JX, JY, JZ = 0.17, -0.357, z(0.118)
jb = [
    plate("JBox", (0.078, 0.044, 0.064), (JX, JY, JZ), red_box, 0.005),
    plate("JTab", (0.03, 0.004, 0.03), (JX + 0.012, -G - 0.003, z(0.158)), rust, 0.001),
    tk.cylinder("LampBase", 0.015, JY - 0.03, JY - 0.022, rust, segments=16, center=(JX - 0.012, JZ + 0.006), axis="Y",
                bevel_width=0.002),
    tk.cylinder("Lamp", 0.0105, JY - 0.042, JY - 0.03, lamp, segments=16, center=(JX - 0.012, JZ + 0.006), axis="Y",
                bevel_width=0.004),
]
for k in range(2):
    c = (JX - 0.012, JY - 0.035 - 0.005 * k, JZ + 0.006)
    ring = tk.torus("Cage", 0.012, 0.0013, c, rust, 14, 5)
    jb.append(turn(ring, "X", 90, c))
for sx in (-1, 1):
    for sz in (-1, 1):
        jb.append(tk.cylinder("JScrew", 0.0045, JY - 0.026, JY - 0.022, rust, segments=6,
                              center=(JX + 0.03 * sx, JZ + 0.023 * sz), axis="Y"))
jb.append(tk.cylinder("Gland", 0.009, JZ - 0.046, JZ - 0.03, rubber, segments=10, center=(JX + 0.02, JY)))
for o in jb:
    add(turn(o, "Z", 3.0, (JX, -G, JZ)))
LAMP = Vector((JX - 0.012, JY - 0.042, JZ + 0.006))

# Clutch lead along the front to the box, and the power cable off to the right
add(tk.tube("ClutchWire", smooth_path([clutch_lead, clutch_lead + Vector((0.006, -0.012, -0.03)),
                                       Vector((-0.3, -0.4, z(0.009))), Vector((-0.05, -0.395, z(0.009))),
                                       Vector((0.1, -0.38, z(0.02))), Vector((JX - 0.025, JY + 0.002, JZ - 0.036))], 4),
            0.003, rubber, resolution=1))
add(tk.tube("PowerCable", smooth_path([Vector((JX + 0.02, JY, JZ - 0.045)), Vector((JX + 0.03, JY - 0.01, z(0.03))),
                                       Vector((0.28, -0.42, z(0.011))), Vector((0.38, -0.44, z(0.011))),
                                       Vector((0.468, -0.43, z(0.011)))], 4), 0.009, rubber, resolution=2))
add(tk.cylinder("CableTape", 0.0115, 0.33, 0.36, tape, segments=12, center=(-0.432, z(0.011)), axis="X"))

# ---------------------------------------------------------------- join, bake, export

tris = {}
for o in parts:
    key = o.name.split(".")[0]
    tris[key] = tris.get(key, 0) + sum(len(p.vertices) - 2 for p in o.data.polygons)
print("[cryo_vent] parts:", sorted(tris.items(), key=lambda kv: -kv[1])[:14])
for o in parts:
    w = [o.matrix_world @ v.co for v in o.data.vertices]
    if w and (max(abs(c.x) for c in w) > 0.47 or max(abs(c.y) for c in w) > 0.47 or min(c.z for c in w) < Z
              or max(c.z for c in w) > z(0.25)):
        print("[cryo_vent] near/over bounds:", o.name, "x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (
            min(c.x for c in w), max(c.x for c in w), min(c.y for c in w), max(c.y for c in w),
            min(c.z for c in w), max(c.z for c in w)))

atlas = tk.triangulate(tk.join(parts, "CryoVent"))
tk.smart_uvs(atlas)
paths = tk.bake_atlas(atlas, ASSETS, "CryoVent_Atlas")
baked = tk.baked_material("CryoVent_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

vent = tk.point("VentPoint", (0.0, 0.0, z(GRATE_TOP)), model)
tk.export_fbx([model, vent], os.path.join(ASSETS, "CryoVent.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[cryo_vent] triangles:", tris)
co = [model.matrix_world @ v.co for v in model.data.vertices]
print("[cryo_vent] bounds: x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f" % (
    min(c.x for c in co), max(c.x for c in co), min(c.y for c in co), max(c.y for c in co),
    min(c.z for c in co), max(c.z for c in co)))
print("[cryo_vent] VentPoint:", tuple(round(c, 4) for c in vent.matrix_world.translation))
print("[cryo_vent] lamp lens front:", tuple(round(c, 4) for c in LAMP))

# ---------------------------------------------------------------- previews and icon

# Icon only: wisps of cold vapor curling up off the grate
mist = tk.glow("ColdMist", (0.75, 0.88, 1.0), 1.6, alpha=0.3)
wisps = []
for k in range(14):
    x0, y0 = rnd.uniform(-0.24, 0.24), rnd.uniform(-0.24, 0.24)
    height = rnd.uniform(0.12, 0.3)
    phase, swirl = rnd.uniform(0, 6.3), rnd.uniform(0.015, 0.04)
    pts = [(x0 + swirl * math.sin(phase + 5.0 * t) + 0.04 * t, y0 + swirl * math.cos(phase + 4.0 * t),
            z(GRATE_TOP + 0.005 + height * t)) for t in (i / 10 for i in range(11))]
    wisps.append(tk.tube("IconMist", pts, rnd.uniform(0.004, 0.009), mist, resolution=2))
for o in wisps:
    o.hide_render = True

tk.render(tk.camera("Front", (1.15, -1.55, 0.35), (0.0, -0.02, z(0.1)), lens=42),
          os.path.join(PREVIEWS, "cryo_vent_front.png"))
tk.render(tk.camera("Back", (-1.3, 1.25, 0.45), (0.0, 0.0, z(0.1)), lens=42),
          os.path.join(PREVIEWS, "cryo_vent_back.png"))
tk.render(tk.camera("Close", (0.3, -0.95, 0.05), (-0.05, -0.1, z(0.1)), lens=40),
          os.path.join(PREVIEWS, "cryo_vent_close.png"))
tk.icon(tk.camera("Icon", (1.6, -2.2, 1.05), (0.0, -0.02, z(0.1)), lens=66), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, extra=wisps, target=(0.0, 0.0, z(0.1)))
print("[cryo_vent] done")
