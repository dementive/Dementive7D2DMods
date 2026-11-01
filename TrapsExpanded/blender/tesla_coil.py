"""Tesla Coil: a 1x2x1 block, built from scrap the way the vanilla traps are. A pole transformer can bolted to a
pallet, a primary bent from copper plumbing pipe on wooden blocks, a secondary wound on a length of PVC pipe, and a
dryer-duct ring on a pie pan at the top that the arcs jump from. A rusty junction box with the power lamp, and a
hand-painted warning sign.

    blender -b --factory-startup --python tesla_coil.py -- <unity asset folder> <preview folder> <icon file>
"""
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = args[0], args[1], args[2]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

Z = -0.5  # bottom of the model
rnd = random.Random(1971)


def z(h):
    return Z + h


def jitter(amount):
    return rnd.uniform(-amount, amount)


tk.reset_scene()
tk.preview_stage()

can_paint = tk.photo_material("CanPaint", "green_metal_rust", scale=1.7, sat=0.14, value=1.3, tint=(0.95, 0.97, 1.0),
                              chip=1.0, grime=0.9, streaks=1.6, patches=0.7, metal_floor=0.4, rough_scale=0.8,
                              grit=1.0, scratches=0.55, edges=0.8, contrast=0.12)
plate = tk.photo_material("Plate", "metal_plate_02", scale=1.9, value=1.2, exposed=None, grime=0.7, streaks=0.5,
                          metal_floor=0.55, rough_scale=0.85, grit=0.9, scratches=0.45, edges=0.6, contrast=0.12)
rust = tk.photo_material("Rust", "rust_coarse_01", scale=2.6, value=1.15, exposed=None, grime=0.6, metal_floor=0.3,
                         grit=0.7)
red_box = tk.photo_material("RedBox", "rusty_painted_metal", scale=1.8, sat=1.0, value=1.15, chip=1.0, grime=0.8,
                            patches=0.6, metal_floor=0.4, rough_scale=0.8, grit=1.0, scratches=0.55, edges=0.8,
                            contrast=0.12)
wood = tk.photo_material("Wood", "weathered_planks", scale=0.8, value=1.2, exposed=None, grime=0.7, bump=0.6, grit=0.55,
                         contrast=0.2)
copper = tk.tarnished_copper("Copper")
pvc = tk.grimy("PVC", (0.56, 0.55, 0.5), roughness=0.5, grime=1.0, soot_from=0.75, stain=(0.42, 0.37, 0.27),
               grit=0.9)
tape = tk.grimy("Tape", (0.02, 0.02, 0.022), roughness=0.42, grime=0.25, bump_scale=35.0)
porcelain = tk.grimy("Porcelain", (0.52, 0.5, 0.46), roughness=0.18, grime=0.8, bump=0.03, grit=0.8)
duct = tk.foil("Duct", ridges=110, scorch=1.0)
foil_tape = tk.foil("FoilTape", scorch=0.4, smooth_tape=True)
pan = tk.photo_material("Pan", "metal_plate_02", scale=2.2, value=1.2, exposed=None, grime=0.8, metal_floor=0.5,
                        grit=0.8, scratches=0.5)
rubber = tk.grimy("Rubber", (0.025, 0.025, 0.025), roughness=0.75, grime=0.4, grit=0.8)
red_cable = tk.grimy("RedCable", (0.33, 0.03, 0.02), roughness=0.5, grime=0.6, grit=0.8)
sign_paint = tk.grimy("SignPaint", (0.75, 0.66, 0.36), roughness=0.65, grime=0.75, grime_set="rust_coarse_01",
                      scale=1.4)
lamp = tk.grimy("Lamp", (0.45, 0.04, 0.02), roughness=0.15, grime=0.3, emission=(1.0, 0.12, 0.04))

parts = []
add = parts.append

# ---------------------------------------------------------------- pallet (top at 0.122)

for x in (-0.4, 0.0, 0.4):
    add(tk.box("PalletFoot", (0.12, 0.95, 0.02), (x + jitter(0.01), jitter(0.01), z(0.01)), wood, 0.003))
for y in (-0.4, 0.0, 0.4):
    add(tk.box("Stringer", (0.95, 0.07, 0.08), (jitter(0.01), y, z(0.06)), wood, 0.004))
for i, x in enumerate((-0.405, -0.243, -0.081, 0.081, 0.243, 0.405)):
    length = 0.95 if i != 4 else 0.74  # one broken board
    board = tk.box("Board", (0.12, length, 0.022), (x, (0.95 - length) / 2 if i == 4 else 0.0, z(0.111)), wood, 0.004)
    tk.orbit(board, 0.0, tilt=("Z", jitter(1.6), (x, 0.0, z(0.11))))
    add(board)
    for y in (-0.4, 0.0, 0.4):
        if i == 4 and y < -0.2:
            continue
        for dx in (-0.03, 0.03):
            add(tk.cylinder("Nail", 0.0045, z(0.121), z(0.124), rust, segments=6, center=(x + dx, y + jitter(0.01))))

# ---------------------------------------------------------------- transformer can (pole transformer)

add(tk.cylinder("Skid", 0.27, z(0.122), z(0.148), rust, segments=40, bevel_width=0.004))
body = tk.cylinder("Can", 0.26, z(0.14), z(0.62), can_paint, segments=40, rings=6)
add(tk.dent(body, 0.007, 0.14, seed=1))
for h in (0.3, 0.48):
    add(tk.cylinder("Seam", 0.265, z(h), z(h + 0.012), can_paint, segments=40, bevel_width=0.003))
add(tk.cylinder("Rim", 0.272, z(0.62), z(0.645), can_paint, segments=40, bevel_width=0.005))
lid = tk.cylinder("Lid", 0.262, z(0.645), z(0.672), can_paint, segments=40, rings=2, radius_top=0.11)
add(tk.dent(lid, 0.004, 0.1, seed=2))
add(tk.cylinder("LidBand", 0.276, z(0.616), z(0.63), rust, segments=40))
clamp = tk.box("BandClamp", (0.03, 0.02, 0.03), (0.0, -0.284, z(0.623)), rust, 0.003)
add(tk.orbit(clamp, 110))
for a in (0, 180):
    lug = tk.torus("Lug", 0.022, 0.006, (0.0, -0.268, z(0.665)), rust, 16, 8)
    tk.orbit(lug, 0.0, tilt=("X", 90, (0.0, -0.268, z(0.665))))
    add(tk.orbit(lug, a + 90))

# Hanger bracket on the back, where it hung on its pole
for x in (-0.09, 0.09):
    ch = tk.box("Channel", (0.04, 0.025, 0.42), (x, 0.272, z(0.39)), plate, 0.004)
    add(tk.dent(ch, 0.002, 0.08, seed=3))
    for h in (0.24, 0.54):
        add(tk.cylinder("BracketBolt", 0.009, 0.284, 0.296, rust, segments=6, center=(x, z(h)), axis="Y"))
for h in (0.24, 0.54):
    add(tk.box("Strap", (0.24, 0.012, 0.035), (0.0, 0.287, z(h)), plate, 0.003))

# High-voltage bushing on the lid rim, low-voltage bushing on the side
hv = (0.245 * math.cos(math.radians(135)), 0.245 * math.sin(math.radians(135)))
h = 0.648
add(tk.cylinder("HVBase", 0.035, z(h), z(h + 0.016), plate, segments=16, center=hv, bevel_width=0.003))
h += 0.016
for _ in range(3):
    add(tk.cylinder("HVCore", 0.024, z(h), z(h + 0.022), porcelain, segments=16, center=hv))
    h += 0.022
    add(tk.cylinder("HVShed", 0.046, z(h), z(h + 0.012), porcelain, segments=20, center=hv, bevel_width=0.004))
    h += 0.012
add(tk.cylinder("HVStud", 0.007, z(h), z(h + 0.04), rust, segments=8, center=hv))
add(tk.cylinder("HVNut", 0.013, z(h + 0.01), z(h + 0.02), rust, segments=6, center=hv))
hv_top = (hv[0], hv[1], z(h + 0.035))

lv = []
r = 0.26
for k in range(2):
    lv.append(tk.cylinder("LVCore", 0.018, r, r + 0.02, porcelain, segments=14, center=(0.0, z(0.55)), axis="X"))
    r += 0.02
    lv.append(tk.cylinder("LVShed", 0.032, r, r + 0.01, porcelain, segments=16, center=(0.0, z(0.55)), axis="X",
                          bevel_width=0.003))
    r += 0.01
lv.append(tk.cylinder("LVStud", 0.006, r, r + 0.035, rust, segments=8, center=(0.0, z(0.55)), axis="X"))
for o in lv:
    add(tk.orbit(o, 20))
lv_end = (0.33 * math.cos(math.radians(20)), 0.33 * math.sin(math.radians(20)), z(0.55))

# ---------------------------------------------------------------- junction box with the power lamp (front right)

JB = -15
jb = [
    tk.box("JBox", (0.15, 0.09, 0.13), (0.0, -0.305, z(0.37)), red_box, 0.008),
    tk.box("JLid", (0.135, 0.008, 0.115), (0.0, -0.352, z(0.37)), red_box, 0.003),
    tk.cylinder("LampBase", 0.026, -0.37, -0.356, rust, segments=16, center=(0.0, z(0.395)), axis="Y",
                bevel_width=0.002),
    tk.cylinder("Lamp", 0.018, -0.392, -0.37, lamp, segments=16, center=(0.0, z(0.395)), axis="Y",
                bevel_width=0.006),
    tk.cylinder("Conduit", 0.016, z(0.122), z(0.31), plate, segments=12, center=(0.045, -0.31)),
]
for k in range(3):
    ring = tk.torus("Cage", 0.021, 0.0018, (0.0, -0.375 - 0.007 * k, z(0.395)), rust, 16, 6)
    tk.orbit(ring, 0.0, tilt=("X", 90, (0.0, -0.375 - 0.007 * k, z(0.395))))
    jb.append(ring)
for sx in (-1, 1):
    for sz in (-1, 1):
        jb.append(tk.cylinder("JScrew", 0.006, -0.36, -0.355, rust, segments=6, center=(0.055 * sx, z(0.37 + 0.045 * sz)),
                              axis="Y"))
for o in jb:
    add(tk.orbit(o, JB + 90))

# ---------------------------------------------------------------- hand-painted warning sign (front left)

SIGN = -100
sign = [tk.box("SignPlate", (0.2, 0.004, 0.13), (0.0, -0.278, z(0.395)), plate, 0.002)]
sign.append(tk.text_mesh("SignDanger", "DANGER", 0.052, sign_paint, (0.0, -0.2805, z(0.418))))
sign.append(tk.text_mesh("SignVolts", "HIGH VOLTAGE", 0.03, sign_paint, (0.0, -0.2805, z(0.37))))
for sx in (-1, 1):
    sign.append(tk.tube("SignWire", [(0.085 * sx, -0.279, z(0.455)), (0.07 * sx, -0.275, z(0.47)),
                                     (0.05 * sx, -0.266, z(0.486))], 0.0018, rust, resolution=2))
for o in sign:
    tk.orbit(o, 0.0, tilt=("Y", 4.0, (0.0, -0.278, z(0.395))))
    add(tk.orbit(o, SIGN + 90))

# ---------------------------------------------------------------- primary: copper pipe on wooden blocks

for a in (25, 115, 205, 295):
    blk = tk.box("Block", (0.06, 0.04, 0.05), (0.17, 0.0, z(0.668)), wood, 0.004)
    tk.orbit(blk, 0.0, tilt=("Z", jitter(8), (0.17, 0.0, z(0.668))))
    add(tk.orbit(blk, a))
pts = []
turns, steps = 2.75, 150
start = math.radians(115) - 2 * math.pi * turns
for k in range(steps + 1):
    t = k / steps
    a = start + 2 * math.pi * turns * t
    r = 0.1 + 0.11 * t + 0.005 * math.sin(5 * a + 1.0)
    pts.append((r * math.cos(a), r * math.sin(a), z(0.705 + 0.003 * math.sin(3 * a))))
add(tk.tube("Primary", pts, 0.011, copper, resolution=4))
inner = pts[0]
add(tk.tube("PrimaryTail", [inner, (inner[0] * 0.95, inner[1] * 0.95, z(0.69)), (inner[0] * 0.9, inner[1] * 0.9,
                                                                                  z(0.672))], 0.011, copper))
end = pts[-1]
clip = tk.box("Clamp", (0.03, 0.022, 0.026), end, rust, 0.003)
add(clip)
mid = ((end[0] + hv_top[0]) / 2 * 1.15, (end[1] + hv_top[1]) / 2 * 1.15, z(0.83))
add(tk.tube("Jumper", [end, (end[0] * 1.08, end[1] * 1.08, z(0.76)), mid, (hv_top[0], hv_top[1], hv_top[2] + 0.02),
                       hv_top], 0.0075, red_cable, resolution=3))

# Low-voltage bushing to the junction box, and the power cable off the pallet
jb_side = (0.36 * math.cos(math.radians(JB + 12)), 0.36 * math.sin(math.radians(JB + 12)), z(0.42))
add(tk.tube("LVCable", [lv_end, (lv_end[0] + 0.03, lv_end[1] - 0.02, z(0.52)), (0.33, -0.12, z(0.47)), jb_side],
            0.009, rubber, resolution=3))
pc0 = (0.31 * math.cos(math.radians(JB - 10)), 0.31 * math.sin(math.radians(JB - 10)), z(0.135))
add(tk.tube("PowerCable", [(pc0[0], pc0[1], z(0.31)), pc0, (0.36, -0.36, z(0.134)), (0.42, -0.42, z(0.134)),
                           (0.455, -0.455, z(0.118)), (0.468, -0.468, z(0.06)), (0.47, -0.47, z(0.012))], 0.012, rubber,
            resolution=3))
for k in range(2):
    wrap = tk.cylinder("TapeWrap", 0.0135, -0.015, 0.015, tape, segments=12)
    wrap.location = (0.36 + 0.035 * k, -0.36 - 0.04 * k, z(0.134))
    wrap.rotation_euler = (math.radians(90), 0.0, math.radians(45))
    add(wrap)

# ---------------------------------------------------------------- secondary: winding on PVC pipe

TILT = ("X", 1.2, (0.0, 0.0, z(0.67)))
secondary = [
    tk.cylinder("Flange", 0.09, z(0.668), z(0.678), plate, segments=28, bevel_width=0.003),
    tk.cylinder("PVC", 0.065, z(0.672), z(1.47), pvc, segments=28),
    tk.cylinder("TapeLow", 0.0695, z(0.765), z(0.788), tape, segments=28),
    tk.cylinder("TapeHigh", 0.0695, z(1.352), z(1.375), tape, segments=28),
    tk.cylinder("PVCCap", 0.073, z(1.47), z(1.505), pvc, segments=28, bevel_width=0.006),
    tk.cylinder("Rod", 0.007, z(1.505), z(1.665), rust, segments=8),
    tk.cylinder("RodNut", 0.014, z(1.505), z(1.516), rust, segments=6),
    tk.cylinder("PanNut", 0.014, z(1.618), z(1.629), rust, segments=6),
]
for k in range(3):
    a = math.radians(30 + 120 * k)
    secondary.append(tk.cylinder("FlangeBolt", 0.008, z(0.678), z(0.688), rust, segments=6,
                                 center=(0.078 * math.cos(a), 0.078 * math.sin(a))))
for o in secondary:
    add(tk.orbit(o, 0.0, tilt=TILT))

# ---------------------------------------------------------------- top: dryer duct ring on a pie pan

TOP_TILT = ("Y", 1.6, (0.0, 0.0, z(1.62)))
top = [tk.cylinder("Pan", 0.13, z(1.588), z(1.618), pan, segments=40, radius_top=0.166, bevel_width=0.004)]
ring = tk.torus("Duct", 0.22, 0.062, (0.0, 0.0, z(1.62)), duct, 96, 14)
top.append(tk.dent(ring, 0.006, 0.08, seed=4))
top.append(tk.torus("FoilTape", 0.22, 0.0665, (0.0, 0.0, z(1.62)), foil_tape, 10, 14, sweep=0.17, start=0.7))
nail = tk.cylinder("Breakout", 0.003, 0.27, 0.33, rust, segments=6, center=(0.0, z(1.625)), axis="X")
top.append(tk.orbit(nail, 30))
for o in top:
    add(tk.orbit(o, 0.0, tilt=TOP_TILT))

atlas = tk.triangulate(tk.join(parts, "TeslaCoil"))
tk.smart_uvs(atlas)

# The secondary winding, with its own tiling texture
WINDING_TILES = 16
winding_mat = tk.plain("WindingPreview", (0.6, 0.33, 0.17))
coil = tk.cylinder("Winding", 0.0675, z(0.788), z(1.352), winding_mat, segments=28, caps=False)
tk.cylinder_uvs(coil, z(0.788), z(1.352), WINDING_TILES)
tk.orbit(coil, 0.0, tilt=TILT)
coil = tk.triangulate(coil)

# ---------------------------------------------------------------- bake

paths = tk.bake_atlas(atlas, ASSETS, "TeslaCoil_Atlas")

# Winding texture: 16 turns of dull, uneven enameled wire per tile, made directly
N = 256
v = (np.arange(N) + 0.5) / N
t = (v * 16) % 1.0
c = (t - 0.5) * 2.0
h = np.sqrt(np.clip(1.0 - c * c, 0.0, 1.0))
rng = np.random.default_rng(7)
grain = rng.normal(0.0, 0.03, (N, N))
turn = np.floor(v * 16).astype(int)
per_turn = rng.uniform(0.75, 1.05, 16)[turn][:, None]
albedo = np.zeros((N, N, 4))
grime = np.clip(rng.normal(0.0, 1.0, (N, N)) * 0.5 + 0.35, 0.0, 1.0) ** 3
specks = (rng.random((N, N)) > 0.985) * rng.uniform(0.4, 0.8, (N, N))
shade = (0.3 + 0.7 * h)[:, None] * (1.0 + grain) * per_turn * (1.0 - 0.45 * grime) * (1.0 - specks)
albedo[..., 0] = 0.72 * shade
albedo[..., 1] = 0.4 * shade
albedo[..., 2] = 0.22 * shade
albedo[..., 3] = 1.0
nrm = np.zeros((N, N, 4))
ny = np.clip(c * 0.9, -1, 1)
nz = np.sqrt(np.clip(1.0 - ny * ny, 0.0, 1.0))
nrm[..., 0] = 0.5 + grain * 0.5
nrm[..., 1] = (ny * 0.5 + 0.5)[:, None]
nrm[..., 2] = (nz * 0.5 + 0.5)[:, None]
nrm[..., 3] = 1.0
smooth = np.repeat((0.35 + 0.3 * h)[:, None] * per_turn, N, axis=1)
wpaths = {
    "albedo": os.path.join(ASSETS, "TeslaCoil_Winding_Albedo.png"),
    "normal": os.path.join(ASSETS, "TeslaCoil_Winding_Normal.png"),
    "rmom": os.path.join(ASSETS, "TeslaCoil_Winding_RMOM.png"),
}
tk.save_array("WindingAlbedo", albedo, wpaths["albedo"], False)
tk.save_array("WindingNormal", nrm, wpaths["normal"], True)
tk.save_array("WindingRMOM", tk.rmom(1.0 - smooth, np.full((N, N), 0.85), np.repeat((0.55 + 0.45 * h)[:, None], N, axis=1)),
              wpaths["rmom"], True)

# ---------------------------------------------------------------- final mesh: two materials

baked = tk.baked_material("TeslaCoil_Atlas", paths, emission_strength=4.0)
wbaked = tk.baked_material("TeslaCoil_Winding", wpaths)
atlas.data.materials.clear()
atlas.data.materials.append(baked)
coil.data.materials.clear()
coil.data.materials.append(wbaked)
model = tk.join([atlas, coil], "TeslaCoil")

import bpy  # noqa: E402

arc_origin = tk.link(bpy.data.objects.new("ArcOrigin", None))
arc_origin.location = (0, 0, z(1.62))
arc_origin.parent = model
lamp_pt = tk.link(bpy.data.objects.new("LampPoint", None))
lamp_pt.location = (0.39 * math.cos(math.radians(JB)), 0.39 * math.sin(math.radians(JB)), z(0.395))
lamp_pt.parent = model

tk.export_fbx([model, arc_origin, lamp_pt], os.path.join(ASSETS, "TeslaCoil.fbx"))
tris = sum(len(p.vertices) - 2 for p in model.data.polygons)
print("[tesla_coil] triangles:", tris)

# ---------------------------------------------------------------- previews and icon

core = tk.glow("ArcCore", (0.6, 0.78, 1.0), 14.0)
halo = tk.glow("ArcHalo", (0.12, 0.35, 1.0), 5.0, alpha=0.4)
arcs = []
for k, (a, end_pt) in enumerate(((200, (-0.5, -0.2, z(1.3))), (320, (0.42, -0.42, z(1.35))),
                                  (60, (0.4, 0.2, z(1.8))))):
    ra = math.radians(a)
    arcs += tk.bolt("IconArc%d" % k, (0.27 * math.cos(ra), 0.27 * math.sin(ra), z(1.63)), end_pt, 11 + k, core, halo,
                    radius=0.0045, roughness=0.16, branches=2)
for o in arcs:
    o.hide_render = True

tk.render(tk.camera("Front", (2.0, -2.7, 1.15), (0, 0, z(0.85)), lens=45), os.path.join(PREVIEWS, "tesla_front.png"))
tk.render(tk.camera("Back", (-2.3, 2.1, 1.7), (0, 0, z(0.8)), lens=45), os.path.join(PREVIEWS, "tesla_back.png"))
tk.render(tk.camera("Close", (0.62, -0.95, 0.35), (0.05, -0.1, z(0.5)), lens=50),
          os.path.join(PREVIEWS, "tesla_close.png"))
tk.render(tk.camera("Top", (0.55, -0.7, 1.75), (0, 0, z(1.55)), lens=50), os.path.join(PREVIEWS, "tesla_top.png"))
tk.icon(tk.camera("Icon", (2.4, -3.1, 1.85), (0, 0, z(0.86)), lens=70), ICON,
        hide={"Floor", "ScaleFigure", "ScaleHead"}, extra=arcs, target=(0, 0, z(0.86)))
print("[tesla_coil] done")
