"""Burn Barrel: a one-block area trap. A rusty, scorched 55-gallon drum standing a little crooked on two cinder
blocks, rows of holes punched round its lower half with the fire glowing orange through them, soot streaked up from
the holes and caked round the open top, charred wood and embers inside, ash spilled round the base and a bent fire
poker leaning on it.

The glow behind the holes and the embers are emissive, so the game can light them up. FirePoint is at the top of the
drum, 5 cm below the rim, where the flames come out.

    blender -b --factory-startup --python burn_barrel.py -- <unity asset folder> <preview folder> <icon file>
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
rnd = random.Random(5505)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


R = 0.28  # drum radius
D0, D1 = 0.19, 0.975  # drum bottom and top (heights above the ground)
N_HOLES = 15  # holes per row
ROWS = (0.255, 0.315, 0.375)  # hole rows; the middle one is staggered
GLOW_TOP = 0.75  # embers fill the drum to here
# The drum stands a little crooked: tipped 1.2 degrees about its bottom center
DRUM = Matrix.Translation((0.008, 0.01, D0)) @ Matrix.Rotation(math.radians(1.2), 4, Vector((1.0, 0.4, 0.0)).normalized()) \
    @ Matrix.Translation((0.0, 0.0, -D0))


def bake_transform(obj):
    bpy.context.view_layer.update()
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def lump(name, size, center, material, bevel_width, seed, strength):
    """A small chunk (a coal, a cinder) built at the origin, turned at random and set down at `center`."""
    o = tk.box(name, size, (0.0, 0.0, 0.0), material, bevel_width)
    o.matrix_world = Matrix.Translation(Vector(center)) @ Euler((jitter(0.5), jitter(0.5), jitter(3.0))).to_matrix().to_4x4()
    bake_transform(o)
    return tk.dent(o, strength, 0.02, seed=seed)


def push(obj, center, radius, vec):
    """Shoves the vertices near `center` by `vec`, falling off over `radius` (a dent kicked in)."""
    c, v = Vector(center), Vector(vec)
    for vert in obj.data.vertices:
        d = (vert.co - c).length
        if d < radius:
            vert.co += v * (0.5 + 0.5 * math.cos(math.pi * d / radius))
    return obj


def solidify(obj, thickness, offset=-1.0):
    mod = obj.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    return tk.apply_modifiers(obj)


def along(obj, start, end):
    """Stands an object built along +Z from the origin (length |end - start|) between two points."""
    d = Vector(end) - Vector(start)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(start)) @ rot @ obj.matrix_world
    return bake_transform(obj)


def blob(name, cx, cy, rx, ry, th, material, seed, power=0.5, n=40):
    """A lobed mound on the ground (ash, a spill): rings of a wobbly ellipse, highest in the middle."""
    bm = bmesh.new()
    rings = []
    for rho in (1.0, 0.85, 0.65, 0.4, 0.18):
        ring = []
        for i in range(n):
            t = 2 * math.pi * i / n
            rr = 1.0 + 0.16 * math.sin(3 * t + seed) + 0.1 * math.sin(5 * t + 2.3 * seed) + 0.06 * math.sin(11 * t + seed)
            hh = th * (1.0 - rho * rho) ** power + 0.0006 + th * 0.12 * math.sin(7 * t + 3 * rho + seed) * (1 - rho)
            ring.append(bm.verts.new((cx + rx * rr * rho * math.cos(t), cy + ry * rr * rho * math.sin(t), max(hh, 0.0006))))
        rings.append(ring)
    c = bm.verts.new((cx, cy, th + 0.0006))
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    for i in range(n):
        bm.faces.new((rings[-1][i], rings[-1][(i + 1) % n], c))
    return tk.smooth(tk.mesh_object(name, bm, material), 60)


# ---------------------------------------------------------------- materials

def scorched_steel(name):
    """The drum: rust over a few scraps of its old blue paint low down, a band of flaky grey heat scale round the
    holes, soot streaked up from every hole, a black sooty top and a black inside."""
    mat, g = tk.new_material(name)
    x, y, zz = g.separate(g.coords())
    rust = tk.photo(g, "rust_coarse_01", 1.3, (0.1, 0.3, 0.5))
    paint = tk.photo(g, "green_metal_rust", 1.6, (0.6, 0.2, 0.4))
    col = tk.grade(g, rust["color"], 1.1, 1.15)
    rough = rust["rough"]
    metal = g.math("MULTIPLY", rust["metal"], 0.5)
    height = rust["height"]

    paint_col = tk.grade(g, paint["color"], 0.4, 0.4, tint=(0.5, 0.65, 1.0))
    low = g.ramp(zz, Z + 0.36, Z + 0.22)
    pm = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=6.0, distortion=0.5), 0.44, 0.5), g.math("ADD", low, 0.2),
                clamp=True)
    col = g.mix(pm, col, paint_col)
    rough = g.mixf(pm, rough, paint["rough"])

    heat = g.math("MULTIPLY", g.ramp(zz, Z + 0.21, Z + 0.28), g.ramp(zz, Z + 0.62, Z + 0.44))
    heat = g.math("MULTIPLY", heat, g.ramp(g.noise(9.0, detail=8.0, roughness=0.7), 0.46, 0.62))
    col = g.mix(heat, col, (0.1, 0.085, 0.075))
    rough = g.mixf(heat, rough, 0.9)

    ang = g.math("DIVIDE", g.math("ARCTAN2", y, x), 2 * math.pi)
    soot = None
    for row, phase, amount in ((ROWS[2], 0.0, 1.0), (ROWS[1], 0.5, 0.75)):
        f = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", ang, float(N_HOLES)), phase))
        dist = g.math("ABSOLUTE", g.math("SUBTRACT", f, 0.5))
        rise = g.math("SUBTRACT", zz, Z + row)
        width = g.math("MAXIMUM", g.math("ADD", 0.2, g.math("MULTIPLY", rise, 1.1)), 0.08)
        s = g.ramp(g.math("SUBTRACT", 1.0, g.math("DIVIDE", dist, width), clamp=True), 0.0, 0.7)
        s = g.math("MULTIPLY", s, amount)
        s = g.math("MULTIPLY", s, g.ramp(zz, Z + row - 0.014, Z + row + 0.008))
        s = g.math("MULTIPLY", s, g.ramp(zz, Z + row + 0.42, Z + row + 0.06))
        soot = s if soot is None else g.math("MAXIMUM", soot, s)
    soot = g.math("MULTIPLY", soot, g.ramp(g.noise(14.0, detail=6.0), 0.2, 0.5))
    band = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(zz, Z + 0.225, Z + 0.25), g.ramp(zz, Z + 0.41, Z + 0.39)),
                  g.ramp(g.noise(10.0, detail=5.0), 0.35, 0.6))
    soot = g.math("MAXIMUM", soot, g.math("MULTIPLY", band, 0.55))
    top = g.math("MULTIPLY", g.ramp(zz, Z + 0.84, Z + 0.96), g.ramp(g.noise(7.0, detail=6.0, distortion=0.4), 0.15, 0.45))
    top = g.math("MAXIMUM", top, g.math("MULTIPLY", tk._streaks(g, 0.8), g.ramp(zz, Z + 0.62, Z + 0.92)))
    top = g.math("MAXIMUM", top, g.ramp(zz, Z + 0.95, Z + 0.975))
    soot = g.math("MAXIMUM", soot, top)
    geo = g.node("ShaderNodeNewGeometry")
    radial = g.node("ShaderNodeCombineXYZ")
    g.links.new(x, radial.inputs[0])
    g.links.new(y, radial.inputs[1])
    unit = g.node("ShaderNodeVectorMath", operation="NORMALIZE")
    g.links.new(radial.outputs[0], unit.inputs[0])
    dot = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.links.new(tk._sock(geo.outputs, "Normal"), dot.inputs[0])
    g.links.new(unit.outputs[0], dot.inputs[1])
    inside = g.ramp(tk._sock(dot.outputs, "Value"), -0.1, -0.5)
    soot = g.math("MAXIMUM", soot, inside)
    col = g.mix(g.math("MULTIPLY", soot, 0.92), col, (0.022, 0.02, 0.018))
    rough = g.mixf(soot, rough, 0.88)
    metal = g.mixf(soot, metal, 0.0)

    ash = g.math("MULTIPLY", g.ramp(zz, Z + 0.3, Z + 0.19), g.ramp(g.noise(8.0, detail=5.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", ash, 0.6), col, (0.3, 0.29, 0.27))
    col, rough, metal = tk._grit(g, col, rough, metal, 0.6, edges=0.5)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.4, 0.01))


def embers(name):
    """Glowing coals: dark crusted lumps with orange to yellow-hot cracks between them (emissive)."""
    mat, g = tk.new_material(name)
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", 32.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    gaps = g.ramp(tk._sock(vor.outputs, "Distance"), 0.12, 0.02)
    heat = g.ramp(g.noise(9.0, detail=6.0, distortion=0.8), 0.3, 0.72)
    glow = g.math("MAXIMUM", g.math("MULTIPLY", gaps, 0.9), g.math("MULTIPLY", heat, 0.55))
    col = g.mix(glow, (0.035, 0.025, 0.02), (0.3, 0.1, 0.03))
    em = g.mix(heat, (0.55, 0.1, 0.0), (1.0, 0.55, 0.15))
    em = g.mix(glow, (0.05, 0.008, 0.0), em)
    return tk.finish(mat, g, col, 0.0, 0.9, g.bump(g.math("SUBTRACT", 1.0, gaps), 0.4, 0.006), emission=em)


def char_wood(name):
    """Charred wood: black alligator-cracked char with a dull silver sheen, the cracks glowing low in the drum."""
    mat, g = tk.new_material(name)
    zz = g.separate(g.coords())[2]
    p = tk.photo(g, "weathered_planks", 1.4, (0.3, 0.1, 0.6))
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", 50.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    crack = g.ramp(tk._sock(vor.outputs, "Distance"), 0.06, 0.0)
    col = tk.grade(g, p["color"], 0.2, 0.2)
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, (0.008, 0.006, 0.005))
    rough = g.mixf(crack, g.math("ADD", 0.55, g.math("MULTIPLY", p["rough"], 0.3)), 0.95)
    hot = g.math("MULTIPLY", g.ramp(zz, Z + 0.83, Z + 0.775), g.ramp(g.noise(6.0, detail=4.0), 0.35, 0.6))
    hot = g.math("MULTIPLY", hot, g.ramp(zz, Z + 0.6, Z + 0.7))  # dropped cinders on the ground are cold
    em = g.mix(g.math("MULTIPLY", crack, hot), (0.0, 0.0, 0.0), (0.9, 0.3, 0.05))
    height = g.math("ADD", g.math("SUBTRACT", 1.0, crack), g.math("MULTIPLY", p["height"], 0.5))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.6, 0.008), emission=em)


def ember_bed(name):
    """The top of the fire: black char and grey ash crust, glowing orange in patches and cracks (emissive)."""
    mat, g = tk.new_material(name)
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", 45.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    gaps = g.ramp(tk._sock(vor.outputs, "Distance"), 0.1, 0.02)
    hotspots = g.ramp(g.noise(5.0, detail=6.0, distortion=1.0), 0.5, 0.66)
    ashy = g.ramp(g.noise(11.0, detail=5.0), 0.42, 0.66)
    col = g.mix(ashy, (0.03, 0.028, 0.026), (0.24, 0.23, 0.22))
    glow = g.math("MULTIPLY", hotspots, g.math("MAXIMUM", gaps, 0.3))
    col = g.mix(glow, col, (0.25, 0.08, 0.02))
    em = g.mix(glow, (0.0, 0.0, 0.0), g.mix(hotspots, (0.6, 0.12, 0.0), (1.0, 0.5, 0.12)))
    return tk.finish(mat, g, col, 0.0, 0.92, g.bump(g.math("SUBTRACT", 1.0, gaps), 0.5, 0.006), emission=em)


tk.reset_scene()
tk.preview_stage()

steel = scorched_steel("DrumSteel")
coals = embers("Embers")
bed = ember_bed("EmberBed")
char = char_wood("Char")
concrete = tk.grimy("Concrete", (0.44, 0.43, 0.4), roughness=0.92, grime=0.9, bump_scale=140.0, bump=0.3, grit=1.0,
                    dirt_range=(0.16, 0.04), soot_from=z(0.06))
ash = tk.grimy("Ash", (0.3, 0.29, 0.28), roughness=0.97, grime=0.7, bump_scale=110.0, bump=0.4, grit=0.6,
               dirt_range=(0.3, 0.1), stain=(0.1, 0.095, 0.09))
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.1, exposed=None, grime=0.7, metal_floor=0.3,
                         grit=0.7, scratches=0.3, edges=0.5)

parts = []
add = parts.append

# ---------------------------------------------------------------- two cinder blocks on their sides (holes to the front)

L, W, H, T = 0.39, 0.19, 0.19, 0.03
for cx, cy, turn, seed in ((0.0, -0.165, -3.5, 7), (0.012, 0.17, 2.0, 8)):
    pieces = [tk.box("CinderTop", (L, W, T), (0.0, 0.0, H - T / 2), concrete, 0.006),
              tk.box("CinderBottom", (L, W, T), (0.0, 0.0, T / 2), concrete, 0.006)]
    for x in (-L / 2 + T / 2, 0.0, L / 2 - T / 2):
        pieces.append(tk.box("CinderWeb", (T, W - 0.002, H - 2 * T + 0.002), (x, 0.0, H / 2), concrete, 0.004))
    for piece in pieces:
        piece.matrix_world = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(math.radians(turn), 4, "Z") \
            @ piece.matrix_world
        bake_transform(piece)
        add(tk.dent(piece, 0.003, 0.05, seed=seed))

# ---------------------------------------------------------------- the drum, holes punched round its lower half

drum = []
shell = tk.cylinder("Drum", R, D0, D1, steel, segments=48, caps=False, rings=14)
tk.dent(shell, 0.008, 0.15, seed=3)
for a, h, r, depth in ((-70.0, 0.58, 0.09, 0.014), (155.0, 0.86, 0.07, 0.01)):  # kicked in, knocked about
    n = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0))
    push(shell, n * R + Vector((0.0, 0.0, h)), r, -n * depth)
solidify(shell, 0.0035)

holes = []
for i, h in enumerate(ROWS):
    for k in range(N_HOLES):
        if rnd.random() < 0.07:
            continue
        a = 2 * math.pi * (k + 0.5 + (0.5 if i == 1 else 0.0)) / N_HOLES + jitter(0.05)
        holes.append((a, h + jitter(0.007), rnd.uniform(0.011, 0.0145)))
for a, h, r in ((0.7, 0.62, 0.02), (2.95, 0.56, 0.016), (4.5, 0.66, 0.024), (5.6, 0.53, 0.013)):
    holes.append((a, h, r))  # rusted through
bm = bmesh.new()
for a, h, r in holes:
    n = Vector((math.cos(a), math.sin(a), 0.0))
    t = Vector((-math.sin(a), math.cos(a), 0.0))
    up = Vector((0.0, 0.0, 1.0))
    ring = []
    for i in range(7):
        th = 2 * math.pi * i / 7 + jitter(0.25)
        rr = r * rnd.uniform(0.72, 1.15)
        ring.append(t * math.cos(th) * rr + up * math.sin(th) * rr)
    c = n * R + up * h
    inner = [bm.verts.new(c - n * 0.03 + p) for p in ring]
    outer = [bm.verts.new(c + n * 0.025 + p) for p in ring]
    bm.faces.new(inner)
    bm.faces.new(list(reversed(outer)))
    for i in range(7):
        j = (i + 1) % 7
        bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
cutter = tk.mesh_object("HoleCutter", bm, steel)
mod = shell.modifiers.new("Holes", "BOOLEAN")
mod.operation = "DIFFERENCE"
mod.object = cutter
mod.solver = "EXACT"
tk.apply_modifiers(shell)
bpy.data.objects.remove(cutter)
drum.append(shell)

for h in (0.45, 0.71):  # rolling hoops
    drum.append(tk.torus("Hoop", R + 0.0015, 0.0075, (0.0, 0.0, h), steel, 48, 6))
drum.append(tk.torus("ChimeTop", R - 0.002, 0.0095, (0.0, 0.0, D1), steel, 48, 8))
drum.append(tk.torus("ChimeBottom", R - 0.001, 0.009, (0.0, 0.0, D0 + 0.008), steel, 48, 6))

# The fire behind the holes: an emissive sleeve inside the wall, capped by a bed of embers
drum.append(tk.cylinder("Glow", R - 0.024, D0 + 0.01, GLOW_TOP, coals, segments=40, caps=False))
bm = bmesh.new()
rings = []
for rho in (1.0, 0.8, 0.55, 0.3):
    ring = []
    for i in range(32):
        t = 2 * math.pi * i / 32
        hh = GLOW_TOP + 0.012 + 0.025 * (1 - rho) + 0.008 * math.sin(5 * t + 7 * rho) * rho
        ring.append(bm.verts.new(((R - 0.01) * rho * math.cos(t), (R - 0.01) * rho * math.sin(t), hh)))
    rings.append(ring)
c = bm.verts.new((0.0, 0.0, GLOW_TOP + 0.04))
for k in range(len(rings) - 1):
    for i in range(32):
        j = (i + 1) % 32
        bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
for i in range(32):
    bm.faces.new((rings[-1][i], rings[-1][(i + 1) % 32], c))
drum.append(tk.smooth(tk.mesh_object("EmberBed", bm, bed), 50))

# Charred logs and a board on the embers, one end poking up at the rim
for (p0, p1, r, seed) in (((-0.17, -0.08, 0.775), (0.13, 0.13, 0.84), 0.04, 11),
                          ((0.17, -0.12, 0.78), (-0.05, 0.11, 0.9), 0.033, 12),
                          ((-0.2, 0.07, 0.77), (0.02, -0.19, 0.79), 0.036, 13),
                          ((0.05, 0.2, 0.77), (0.19, -0.02, 0.86), 0.018, 15),
                          ((-0.12, -0.17, 0.78), (-0.16, 0.13, 0.88), 0.014, 16)):
    length = (Vector(p1) - Vector(p0)).length
    log = tk.cylinder("Log", r, 0.0, length, char, segments=9, rings=4, radius_top=r * rnd.uniform(0.6, 0.9))
    tk.dent(log, 0.012, 0.04, seed=seed)
    drum.append(along(log, p0, p1))
board =tk.box("Board", (0.07, 0.022, 0.3), (0.0, 0.0, 0.15), char, 0.003)
tk.dent(board, 0.006, 0.04, seed=14)
drum.append(along(board, (-0.1, 0.15, 0.765), (0.03, -0.035, 0.99)))
for k in range(6):
    a = rnd.uniform(0, 2 * math.pi)
    rr = rnd.uniform(0.05, 0.2)
    drum.append(lump("Coal", (rnd.uniform(0.025, 0.045),) * 3, (rr * math.cos(a), rr * math.sin(a), GLOW_TOP + 0.035),
                     char, 0.006, 20 + k, 0.006))

for o in drum:
    bake_transform(o)
    o.data.transform(DRUM)
    add(o)

# ---------------------------------------------------------------- ash round the base, a few dropped coals

add(blob("Ash", 0.02, 0.0, 0.33, 0.32, 0.014, ash, 1.3, power=0.8))
add(blob("AshHeap", 0.01, 0.0, 0.17, 0.085, 0.05, ash, 2.2, power=0.7, n=28))
add(blob("AshFront", 0.07, -0.31, 0.13, 0.07, 0.028, ash, 0.4, power=0.9, n=28))
add(blob("AshSide", -0.3, 0.06, 0.07, 0.12, 0.022, ash, 3.1, power=0.9, n=28))
for k in range(9):
    a = rnd.uniform(0, 2 * math.pi)
    rr = rnd.uniform(0.3, 0.4)
    add(lump("Cinder", (rnd.uniform(0.018, 0.035), rnd.uniform(0.015, 0.03), rnd.uniform(0.012, 0.02)),
             (rr * math.cos(a), rr * math.sin(a) * 0.95, 0.016), char, 0.004, 40 + k, 0.004))

# ---------------------------------------------------------------- a bent fire poker leaning on the drum (front right)

PA = math.radians(-40)
contact = DRUM @ Vector(((R + 0.013) * math.cos(PA), (R + 0.013) * math.sin(PA), 0.86))
tip = Vector((0.37, -0.295, 0.008))
d = (contact - tip).normalized()
kink = tip + (contact - tip) * 0.55 + Vector((0.012, -0.01, 0.0))  # bent where it has been levered on
shaft = [tip + d * -0.0, tip + d * 0.02 + Vector((0.0, 0.0, 0.004)), kink, contact, contact + d * 0.045]
add(tk.tube("Poker", [tuple(p) for p in shaft], 0.0075, rust, resolution=2))
side = d.cross(Vector((0.0, 0.0, 1.0))).normalized()
prong_base = tip + d * 0.07
add(tk.tube("PokerHook", [tuple(prong_base), tuple(prong_base + side * 0.03 + d * 0.012),
                          tuple(prong_base + side * 0.04 - d * 0.02)], 0.0055, rust, resolution=2))
loop_c = contact + d * 0.075
q = (Vector((math.cos(PA), math.sin(PA), 0.0)) - d * d.dot(Vector((math.cos(PA), math.sin(PA), 0.0)))).normalized()
loop = []
for i in range(13):
    th = 2 * math.pi * i / 12
    loop.append(tuple(loop_c + (-d * math.cos(th) + q * math.sin(th)) * 0.03))
add(tk.tube("PokerHandle", [tuple(contact + d * 0.045)] + loop, 0.006, rust, resolution=2))

# ---------------------------------------------------------------- into the block, join

for o in parts:
    bake_transform(o)
    o.data.transform(Matrix.Translation((0.0, 0.0, Z)))

atlas = tk.triangulate(tk.join(parts, "BurnBarrel"))
tk.smart_uvs(atlas)
xs = [v.co.x for v in atlas.data.vertices]
ys = [v.co.y for v in atlas.data.vertices]
zs = [v.co.z for v in atlas.data.vertices]
print("[burn_barrel] bounds x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f" % (min(xs), max(xs), min(ys), max(ys), min(zs),
                                                                      max(zs)))
fire = DRUM @ Vector((0.0, 0.0, D1 + 0.0095 - 0.05)) + Vector((0.0, 0.0, Z))

# ---------------------------------------------------------------- bake and export

paths = tk.bake_atlas(atlas, ASSETS, "BurnBarrel_Atlas")
baked = tk.baked_material("BurnBarrel_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

fire_pt = tk.point("FirePoint", fire, model)
tk.export_fbx([model, fire_pt], os.path.join(ASSETS, "BurnBarrel.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[burn_barrel] triangles:", tris)
print("[burn_barrel] FirePoint", tuple(round(c, 4) for c in fire_pt.matrix_world.translation))

# ---------------------------------------------------------------- previews and icon

tk.render(tk.camera("Front", (1.5, -2.0, 0.75), (0, 0, z(0.5)), lens=45), os.path.join(PREVIEWS, "burn_barrel_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0, 0, z(0.45)), lens=45), os.path.join(PREVIEWS, "burn_barrel_back.png"))
tk.render(tk.camera("Close", (0.55, -0.85, 0.05), (0.02, -0.05, z(0.42)), lens=50),
          os.path.join(PREVIEWS, "burn_barrel_close.png"))
tk.icon(tk.camera("Icon", (1.6, -2.1, 2.2), (0, -0.02, z(0.45)), lens=66), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, target=(0, 0, z(0.5)))
print("[burn_barrel] done")
