"""Sprinkler: a 1x1x1 block. A sun-faded blue plastic drum on two cinder blocks, a little 12 V pump strapped to its
side, a copper riser up to a manifold with three brass nozzles fanned out to the front (-Y), a rusty junction box
with the power lamp, and a coiled garden hose.

The model carries two empties for the game: SprayOrigin at the middle nozzle's tip and SprayAim a meter along the
spray, so the soak cone turns with the block.

    blender -b --factory-startup --python sprinkler.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

from mathutils import Matrix, Vector  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(2049)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


def along(obj, start, direction):
    """Points an object built along +Z from the origin down `direction`, starting at `start`."""
    d = Vector(direction).normalized()
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(start) @ rot @ obj.matrix_world
    return obj


def fan(yaw_degrees, pitch=0.2):
    """A nozzle direction: forward (-Y), tilted up by `pitch`, turned by yaw."""
    d = Vector((0.0, -1.0, pitch)).normalized()
    return Matrix.Rotation(math.radians(yaw_degrees), 3, "Z") @ d


tk.reset_scene()
tk.preview_stage()

blue = tk.grimy("BluePlastic", (0.03, 0.14, 0.42), roughness=0.5, grime=0.7, stain=(0.1, 0.2, 0.33), grit=0.6,
                dirt_range=(0.1, 0.03))
concrete = tk.grimy("Concrete", (0.44, 0.43, 0.4), roughness=0.92, grime=0.8, bump_scale=140.0, bump=0.3, grit=1.0,
                    dirt_range=(0.16, 0.04))
copper = tk.tarnished_copper("Copper")
brass = tk.tarnished_copper("Brass", bright=(0.78, 0.6, 0.28), dark=(0.5, 0.37, 0.14))
red_box = tk.photo_material("RedBox", "rusty_painted_metal", scale=1.8, sat=1.0, value=1.15, chip=1.0, grime=0.8,
                            patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55, edges=0.8,
                            contrast=0.12)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
hose = tk.grimy("Hose", (0.05, 0.22, 0.05), roughness=0.6, grime=0.6, grit=0.8, dirt_range=(0.1, 0.03))
tape = tk.grimy("DuctTape", (0.42, 0.42, 0.43), roughness=0.45, metallic=0.3, grime=0.6, bump_scale=45.0, bump=0.12,
                grit=0.6)
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append

# ---------------------------------------------------------------- two cinder blocks (top at 0.19)

L, W, H, T = 0.39, 0.19, 0.19, 0.03
for cy in (-0.04, 0.155):
    cx, turn = jitter(0.015), jitter(3.0)
    pieces = [tk.box("CinderWall", (L, T, H), (0.0, -W / 2 + T / 2, H / 2), concrete, 0.006),
              tk.box("CinderWall", (L, T, H), (0.0, W / 2 - T / 2, H / 2), concrete, 0.006)]
    for x in (-L / 2 + T / 2, 0.0, L / 2 - T / 2):
        pieces.append(tk.box("CinderWeb", (T, W - 2 * T + 0.002, H), (x, 0.0, H / 2), concrete, 0.004))
    for piece in pieces:
        piece.matrix_world = Matrix.Translation((cx, cy, Z)) @ Matrix.Rotation(math.radians(turn), 4, "Z") @ piece.matrix_world
        add(tk.dent(piece, 0.003, 0.05, seed=7))

# ---------------------------------------------------------------- the drum (center slightly back)

DX, DY, R = 0.0, 0.06, 0.24
drum = tk.cylinder("Drum", R, z(0.19), z(0.86), blue, segments=40, center=(DX, DY), rings=6)
add(tk.dent(drum, 0.006, 0.12, seed=5))
for h in (0.4, 0.63):
    add(tk.cylinder("Hoop", R + 0.008, z(h), z(h + 0.025), blue, segments=40, center=(DX, DY), bevel_width=0.006))
add(tk.cylinder("Chime", R + 0.006, z(0.86), z(0.885), blue, segments=40, center=(DX, DY), bevel_width=0.008))
add(tk.cylinder("Chime", R + 0.004, z(0.19), z(0.205), blue, segments=40, center=(DX, DY), bevel_width=0.005))
add(tk.cylinder("Bung", 0.034, z(0.885), z(0.9), blue, segments=6, center=(0.1, 0.17), bevel_width=0.003))
add(tk.cylinder("Bung", 0.03, z(0.885), z(0.897), blue, segments=16, center=(0.0, -0.1), bevel_width=0.003))

# A strap holding the pump on the front right
add(tk.cylinder("Strap", R + 0.004, z(0.655), z(0.672), rust, segments=40, center=(DX, DY)))
PUMP = -35
pump = [
    tk.cylinder("PumpBody", 0.04, z(0.6), z(0.72), red_box, segments=20, center=(0.0, -(R + 0.045) + DY),
                bevel_width=0.006),
    tk.cylinder("PumpCap", 0.043, z(0.72), z(0.74), rubber, segments=20, center=(0.0, -(R + 0.045) + DY),
                bevel_width=0.004),
    tk.cylinder("PumpFoot", 0.03, z(0.58), z(0.6), rust, segments=6, center=(0.0, -(R + 0.045) + DY)),
]
for o in pump:
    o.matrix_world = Matrix.Translation((DX, DY, 0)) @ Matrix.Rotation(math.radians(PUMP + 90 - 90), 4, "Z") \
        @ Matrix.Translation((0, -DY, 0)) @ o.matrix_world
    add(tk.orbit(o, 0.0))
pump_top = Vector((DX, DY, 0)) + Matrix.Rotation(math.radians(PUMP), 3, "Z") @ Vector((0.0, -(R + 0.045), z(0.74)))
pump_top.z = z(0.74)

# ---------------------------------------------------------------- riser, manifold and three nozzles

MY, MZ = -0.1, z(0.955)
add(tk.tube("Riser", [(0.0, MY, z(0.89)), (0.0, MY, MZ)], 0.013, copper, resolution=3))
add(tk.cylinder("Tee", 0.018, -0.03, 0.03, brass, segments=16, center=(MY, MZ), axis="X", bevel_width=0.003))
add(tk.tube("Manifold", [(-0.17, MY, MZ), (0.17, MY, MZ)], 0.013, copper, resolution=3))
for sx in (-1, 1):
    add(tk.cylinder("ManifoldCap", 0.014, 0.17 * sx - 0.012, 0.17 * sx + 0.012, brass, segments=14,
                    center=(MY, MZ), axis="X", bevel_width=0.003))
add(tk.cylinder("TapeWrap", 0.0135, z(0.905), z(0.93), tape, segments=14, center=(0.0, MY)))

nozzles = []
for x, yaw in ((-0.13, -25.0), (0.0, 0.0), (0.13, 25.0)):
    d = fan(yaw)
    base = Vector((x, MY, MZ))
    body = along(tk.cylinder("NozzleBody", 0.022, 0.0, 0.045, brass, segments=6, bevel_width=0.003), base, d)
    neck = along(tk.cylinder("NozzleNeck", 0.014, 0.045, 0.06, brass, segments=12), base, d)
    tip = along(tk.cylinder("NozzleTip", 0.02, 0.06, 0.085, brass, segments=14, radius_top=0.009), base, d)
    add(body)
    add(neck)
    add(tip)
    nozzles.append((base + d * 0.085, d))
spray_origin, spray_dir = nozzles[1]

# Pump outlet hose up into the riser
add(tk.tube("PumpHose", [pump_top, pump_top + Vector((0.0, 0.0, 0.06)), Vector((0.02, MY - 0.01, z(0.86))),
                         Vector((0.0, MY, z(0.9)))], 0.009, rubber, resolution=3))

# ---------------------------------------------------------------- junction box with the power lamp (front left)

JB = -140
jb = [
    tk.box("JBox", (0.11, 0.06, 0.1), (0.0, -(R + 0.03), z(0.47)), red_box, 0.006),
    tk.box("JLid", (0.1, 0.006, 0.09), (0.0, -(R + 0.063), z(0.47)), red_box, 0.002),
    tk.cylinder("LampBase", 0.02, -(R + 0.078), -(R + 0.066), rust, segments=16, center=(0.0, z(0.49)), axis="Y",
                bevel_width=0.002),
    tk.cylinder("Lamp", 0.014, -(R + 0.094), -(R + 0.078), lamp, segments=16, center=(0.0, z(0.49)), axis="Y",
                bevel_width=0.005),
]
for o in jb:
    o.matrix_world = Matrix.Translation((DX, DY, 0)) @ Matrix.Rotation(math.radians(JB + 90), 4, "Z") @ o.matrix_world
    add(o)
jb_bottom = Vector((DX, DY, 0)) + Matrix.Rotation(math.radians(JB + 90), 3, "Z") @ Vector((0.03, -(R + 0.03), z(0.42)))
add(tk.tube("PowerCable", [jb_bottom, jb_bottom + Vector((0.0, 0.0, -0.1)), Vector((-0.3, 0.05, z(0.2))),
                           Vector((-0.36, 0.2, z(0.012))), Vector((-0.4, 0.42, z(0.012)))], 0.011, rubber,
            resolution=3))

# ---------------------------------------------------------------- spigot and a coiled garden hose (back right)

SP = -60
spigot = [tk.cylinder("Spigot", 0.014, R - 0.01, R + 0.04, brass, segments=12, center=(0.0, z(0.27)), axis="X"),
          tk.box("Valve", (0.012, 0.05, 0.012), (R + 0.025, 0.0, z(0.295)), brass, 0.002)]
for o in spigot:
    o.matrix_world = Matrix.Translation((DX, DY, 0)) @ Matrix.Rotation(math.radians(SP), 4, "Z") @ o.matrix_world
    add(o)
spout = Vector((DX, DY, 0)) + Matrix.Rotation(math.radians(SP), 3, "Z") @ Vector((R + 0.04, 0.0, z(0.27)))
for k, (r, h) in enumerate(((0.1, 0.013), (0.095, 0.038))):
    add(tk.torus("HoseCoil", r, 0.013, (0.31, 0.3, z(h)), hose, 32, 8))
add(tk.tube("HoseRun", [spout, spout + Vector((0.04, 0.0, -0.03)), Vector((0.33, 0.08, z(0.06))),
                        Vector((0.27, 0.2, z(0.04)))], 0.013, hose, resolution=3))

atlas = tk.triangulate(tk.join(parts, "Sprinkler"))
tk.smart_uvs(atlas)

# ---------------------------------------------------------------- bake and export

paths = tk.bake_atlas(atlas, ASSETS, "Sprinkler_Atlas")
baked = tk.baked_material("Sprinkler_Atlas", paths, emission_strength=4.0)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
model = atlas

import bpy  # noqa: E402

origin = tk.link(bpy.data.objects.new("SprayOrigin", None))
origin.location = spray_origin
origin.parent = model
aim = tk.link(bpy.data.objects.new("SprayAim", None))
aim.location = spray_origin + spray_dir
aim.parent = model

tk.export_fbx([model, origin, aim], os.path.join(ASSETS, "Sprinkler.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[sprinkler] triangles:", tris)

# ---------------------------------------------------------------- previews and icon

water = tk.glow("SprayWater", (0.75, 0.88, 1.0), 2.0, alpha=0.45)
spray = []
for tip, d in nozzles:
    for k in range(9):
        dd = (Matrix.Rotation(rnd.uniform(-0.2, 0.2), 3, "Z") @ d).normalized()
        dd.z += rnd.uniform(-0.05, 0.08)
        length = rnd.uniform(0.35, 0.7)
        pts = [tip + dd * (length * i / 6) + Vector((0.0, 0.0, -0.35 * (length * i / 6) ** 2)) for i in range(7)]
        spray.append(tk.tube("IconSpray", [tuple(p) for p in pts], rnd.uniform(0.002, 0.004), water, resolution=2))
for o in spray:
    o.hide_render = True

tk.render(tk.camera("Front", (1.5, -2.0, 0.75), (0, 0, z(0.5)), lens=45), os.path.join(PREVIEWS, "sprinkler_front.png"))
tk.render(tk.camera("Back", (-1.7, 1.6, 1.1), (0, 0, z(0.45)), lens=45), os.path.join(PREVIEWS, "sprinkler_back.png"))
tk.render(tk.camera("Close", (0.5, -0.75, 0.35), (0.0, -0.05, z(0.8)), lens=50),
          os.path.join(PREVIEWS, "sprinkler_close.png"))
tk.icon(tk.camera("Icon", (1.9, -2.5, 1.5), (0, -0.1, z(0.5)), lens=62), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, extra=spray, target=(0, 0, z(0.5)))
print("[sprinkler] done")
