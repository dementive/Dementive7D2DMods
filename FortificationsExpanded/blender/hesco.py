"""Hesco Barrier (Fortifications Expanded): ten block models that share one baked atlas, `Hesco`.

    Hesco{Empty,Third,TwoThirds,Full,Mound}.fbx
    HescoDouble{Empty,Third,TwoThirds,Full,Mound}.fbx

A Hesco unit is a cage of galvanised welded-wire mesh (12 by 26 squares, about 7.8 by 7.6 cm, per wall, 1.97 m tall)
with coil hinges and a joining pin at the corners, lined with tan geotextile felt and filled with earth. The single
unit is 0.94 m square between its corner coils (the walls bulge out to about 0.49 when filled); the double is two cells
over X -0.97..0.97 sharing a coil-hinged middle wall.

The walls are textured, not modelled wire by wire: the mesh over the felt (pillowing out between the wires where the
unit is filled, hanging in wrinkles where it is slack), rust drips, rain streaks, earth stains and mud are baked from
procedural materials onto flat "patches" (three height bands of wall, taut and slack, in two variants; three bands of
inner liner; the rim; the earth top; a spill tongue). Each piece builds its own deformed grids and maps them onto those
patches. The corner coils, pins, the top wire, wires over tears, earth bulging through tears, torn felt flaps, spill
piles, the breach mound and a shovel are kit parts copied with their UVs.

Pieces: Empty (one mesh, DMG0; the single has a shovel leaning on its front), Third, TwoThirds and Full (earth to
0.67, 1.33 and 1.95 m; DMG0 intact, DMG1 torn in two places with earth spilling, dented, a small pile; DMG2 a big tear
pouring into a pile, the earth slumped, the cage sagging and bent; plus an FX empty on the front face at the middle of
the earth) and Mound (what is left after a breach, one mesh).

    blender -b --factory-startup --python hesco.py -- <unity asset folder> <preview folder> <icon file> [mode] [tex]

mode: all (default), export (no renders). tex: atlas size (2048; 1024 for quick looks).
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
TEX = int(args[4]) if len(args) > 4 else 2048
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

Z0 = -0.5  # bottom of every model
H = 1.97  # cage height (top wire) above the ground
NZ = 26  # mesh squares up a wall
PZ = H / NZ
NX = 12  # mesh squares across a wall
WK = 0.92  # wall width in the kit (single cell, corner coil to corner coil)
PX = WK / NX
C = 0.46  # single cell: corner coils at x, y = +-C
CDX = 0.96  # double: end corners at x = +-CDX, middle hinge at x = 0
T = 0.008  # felt and mesh thickness
RW = 0.0025  # wire radius (painted)
RC = 0.016  # corner coil radius
BANDS = (0.0, 9 * PZ, 18 * PZ, H)
FILL = {"Empty": 0.0, "Third": 0.67, "TwoThirds": 1.33, "Full": 1.95}
BULGE = 0.03
RIMW = 0.03
ZMAX = Z0 + 2.0 - 0.0005  # nothing pokes into the cell above the 2 m block
MAT_NAME = "Hesco"


def log(*a):
    print("[hesco]", *a, flush=True)


# ---------------------------------------------------------------- colors (linear)

TAN_L = (0.24, 0.17, 0.09)
TAN_D = (0.128, 0.086, 0.046)
FIBRE = (0.29, 0.225, 0.15)
BLEACH = (0.25, 0.215, 0.165)
GRIME = (0.05, 0.04, 0.028)
EARTH_STAIN = (0.08, 0.052, 0.03)
STREAK = (0.052, 0.045, 0.036)
RUST_STAIN = (0.17, 0.068, 0.026)
MUD = (0.03, 0.022, 0.014)
DUST = (0.27, 0.225, 0.165)
GALV_L = (0.28, 0.283, 0.278)
GALV_D = (0.12, 0.122, 0.12)
WHITE_RUST = (0.4, 0.4, 0.38)
RUST_L = (0.2, 0.085, 0.032)
RUST_D = (0.085, 0.04, 0.02)
EARTH_L = (0.2, 0.148, 0.095)
EARTH_D = (0.075, 0.055, 0.036)
CLAY = (0.23, 0.13, 0.065)
STONE_L = (0.17, 0.15, 0.12)
STONE_D = (0.075, 0.065, 0.055)
STONE_R = (0.18, 0.1, 0.06)
CRACK = (0.03, 0.022, 0.016)
EARTH_DUST = (0.23, 0.19, 0.14)
STRAW = (0.3, 0.25, 0.15)


# ---------------------------------------------------------------- small helpers

def sstep(e0, e1, x):
    """Smoothstep from e0 to e1 (either order), on numpy arrays or floats."""
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def pnoise(p, seed, freq=1.0):
    return noise.noise(Vector((p[0] * freq + seed * 7.31, p[1] * freq - seed * 3.17, p[2] * freq + seed * 1.93)))


def nvec(P, freq, seed):
    """Smooth noise vectors (-1..1) at points P (N, 3)."""
    o = np.array((seed * 3.7, seed * 1.3, seed * 5.1))
    return np.array([noise.noise_vector(Vector(p)) for p in (np.asarray(P) * freq + o)])


def nscal(P, freq, seed):
    o = np.array((seed * 2.9, seed * 4.1, seed * 0.7))
    return np.array([noise.noise(Vector(p)) for p in (np.asarray(P) * freq + o)])


def rotz(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-9)


def bm_from(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    return bm


# ---------------------------------------------------------------- node helpers

def attr_vec(g, name):
    return tk._sock(g.node("ShaderNodeAttribute", attribute_name=name).outputs, "Vector")


def mapped(g, vec, scale=(1.0, 1.0, 1.0), loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Location"].default_value = loc
    m.inputs["Rotation"].default_value = rot
    return m.outputs[0]


def voronoi(g, vec, scale, feature="F1"):
    v = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(v, "Scale", scale)
    g.links.new(vec, v.inputs["Vector"])
    return v


def white(g, vec):
    n = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Value")


def combine(g, x, y, z):
    n = g.node("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        g._in(n, n.inputs[i].identifier, v)
    return n.outputs[0]


def eq(g, x, k):
    return g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", x, k)), 0.4, 0.1)


def roundp(g, d, r):
    """Round profile of a wire of radius r at distance d from its centre line (1 on the line, 0 off it)."""
    q = g.math("MINIMUM", g.math("DIVIDE", d, r), 1.0)
    return g.math("SQRT", g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", q, q)), 0.0))


def warped(g, vec, scale, amount):
    """vec pushed about by smooth noise (for irregular cells)."""
    n = g.node("ShaderNodeTexNoise")
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    sub = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(tk._sock(n.outputs, "Color"), sub.inputs[0])
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(sub.outputs[0], sc.inputs[0])
    g._in(sc, "Scale", amount)
    add = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(vec, add.inputs[0])
    g.links.new(sc.outputs[0], add.inputs[1])
    return add.outputs[0]


def scale_col(g, col, s):
    n = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(col, n.inputs[0])
    g._in(n, "Scale", s)
    return n.outputs["Vector"]


def local_normal(g):
    geo = g.node("ShaderNodeNewGeometry")
    vt = g.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="WORLD", convert_to="OBJECT")
    g.links.new(tk._sock(geo.outputs, "Normal"), vt.inputs[0])
    return g.separate(vt.outputs[0])


def photo_at(g, set_name, vec, scale, offset=(0.0, 0.0, 0.0), kinds=("diff",)):
    """A photo set box-projected from `vec` (the parts' own coordinates, so patterns run on across patches)."""
    out = {}
    for kind in kinds:
        path = os.path.join(tk.TEXTURES, set_name, "{0}_{1}_2k.jpg".format(set_name, kind))
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "sRGB" if kind == "diff" else "Non-Color"
        n = g.node("ShaderNodeTexImage", projection="BOX", projection_blend=0.3, interpolation="Cubic")
        n.image = img
        m = g.node("ShaderNodeMapping")
        g.links.new(vec, m.inputs["Vector"])
        m.inputs["Location"].default_value = offset
        m.inputs["Scale"].default_value = (scale, scale, scale)
        g.links.new(m.outputs[0], n.inputs["Vector"])
        out[kind] = n.outputs["Color"]
    return out


# ---------------------------------------------------------------- materials

def galv(g, lco, rust_bias, low):
    """Old galvanised wire: dull mottled zinc, white rust blooms, red rust in spots and at the welds, mud low down.
    Returns color, metallic, roughness."""
    M = g.math
    mott = g.noise(1.0, 4.0, 0.6, vector=mapped(g, lco, (30.0, 30.0, 30.0)))
    col = g.mix(mott, GALV_D, GALV_L)
    wr = M("MULTIPLY", g.ramp(g.noise(1.0, 6.0, 0.6, vector=mapped(g, lco, (8.0, 8.0, 8.0), (5.1, 2.2, 0.7)),
                                      distortion=0.5), 0.52, 0.68), 0.7)
    col = g.mix(wr, col, WHITE_RUST)
    rn = g.noise(1.0, 8.0, 0.65, vector=mapped(g, lco, (5.0, 5.0, 5.0), (1.3, 7.7, 2.9)), distortion=0.6)
    rust = M("MAXIMUM", g.ramp(rn, 0.58, 0.68), rust_bias)
    rust = M("MULTIPLY", rust, g.ramp(g.noise(1.0, 4.0, vector=mapped(g, lco, (60.0, 60.0, 60.0))), 0.25, 0.55),
             clamp=True)
    col = g.mix(rust, col, g.mix(g.noise(1.0, 3.0, vector=mapped(g, lco, (25.0, 25.0, 25.0))), RUST_D, RUST_L))
    col = g.mix(M("MULTIPLY", low, 0.8), col, MUD)
    metal = M("MULTIPLY", M("SUBTRACT", 0.85, M("MULTIPLY", rust, 0.7)), M("SUBTRACT", 1.0, M("MULTIPLY", low, 0.7)))
    rough = g.mixf(rust, M("ADD", 0.4, M("MULTIPLY", mott, 0.15)), 0.85)
    rough = g.mixf(wr, rough, 0.72)
    rough = g.mixf(low, rough, 0.9)
    return col, metal, rough


def liner_material():
    """Geotextile felt behind welded mesh. Reads lco (the patch's own coordinates: along the wall, out, height),
    kd (style: 0 outer wall, 1 inner liner, 2 rim, 3 torn flap; taut 0-1; dirt 0-1) and kx (kit scale)."""
    mat, g = tk.new_material("Liner")
    M = g.math
    lco = attr_vec(g, "lco")
    a, _b, h = g.separate(lco)
    style, taut, dirt = g.separate(attr_vec(g, "kd"))
    ks = g.separate(attr_vec(g, "kx"))[0]
    outer, inner, rim, flap = (eq(g, style, k) for k in (0.0, 1.0, 2.0, 3.0))
    slack = M("SUBTRACT", 1.0, taut)

    # ---- the welded mesh: each wire bent its own way, round in section, weld blobs at the crossings
    wa = M("ADD", M("MULTIPLY", M("SUBTRACT", g.noise(1.0, 2.0, vector=mapped(g, lco, (7.0, 7.0, 2.2))), 0.5), 0.011),
           M("MULTIPLY", M("SUBTRACT", g.noise(1.0, 2.0, vector=mapped(g, lco, (1.2, 1.2, 1.2), (3.0, 0.0, 1.0))), 0.5),
             0.01))
    wz = M("ADD", M("MULTIPLY", M("SUBTRACT", g.noise(1.0, 2.0, vector=mapped(g, lco, (2.2, 2.2, 7.0), (4.2, 1.1, 7.3))),
                                  0.5), 0.011),
           M("MULTIPLY", M("SUBTRACT", g.noise(1.0, 2.0, vector=mapped(g, lco, (1.2, 1.2, 1.2), (8.0, 2.0, 5.0))), 0.5),
             0.01))
    gx = M("DIVIDE", M("ADD", a, wa), PX)
    gz = M("DIVIDE", M("ADD", h, wz), PZ)
    fx, fz = M("FRACT", gx), M("FRACT", gz)
    dx = M("MULTIPLY", M("SUBTRACT", 0.5, M("ABSOLUTE", M("SUBTRACT", fx, 0.5))), PX)
    dz = M("MULTIPLY", M("SUBTRACT", 0.5, M("ABSOLUTE", M("SUBTRACT", fz, 0.5))), PZ)
    wv = roundp(g, dx, RW)
    wh = M("MULTIPLY", roundp(g, dz, RW), 0.92)
    dc = M("SQRT", M("ADD", M("MULTIPLY", dx, dx), M("MULTIPLY", dz, dz)))
    weld = M("MULTIPLY", roundp(g, dc, RW * 1.7), 1.1)
    wire_h = M("MAXIMUM", M("MAXIMUM", wv, wh), weld)
    wire_m = M("MULTIPLY", g.ramp(wire_h, 0.05, 0.4), outer)
    cell = combine(g, M("FLOOR", gx), M("FLOOR", gz), 0.0)
    cr = white(g, cell)  # per square
    cr2 = white(g, mapped(g, cell, loc=(17.0, 3.0, 5.0)))
    dr = white(g, combine(g, M("ROUND", gx), M("FLOOR", gz), 1.0))  # per crossing (the one above the square)
    big = g.noise(1.0, 3.0, vector=mapped(g, lco, (1.6, 1.6, 1.6), (9.1, 0.0, 2.2)))

    # ---- felt shape: pillows pushed out between the wires, uneven, sagging in each square, lumpy where stones press
    # (taut); drapes, creases and crinkles (slack)
    fzs = M("POWER", fz, 1.3)
    pil = M("POWER", M("MULTIPLY", M("SINE", M("MULTIPLY", fx, math.pi)), M("SINE", M("MULTIPLY", fzs, math.pi))), 0.5)
    pil = M("MULTIPLY", M("MULTIPLY", pil, M("ADD", 0.4, M("MULTIPLY", cr, 0.9))), M("ADD", 0.55, M("MULTIPLY", big, 0.9)))
    lump = M("SUBTRACT", g.noise(1.0, 3.0, 0.6, vector=mapped(g, lco, (24.0, 24.0, 24.0)), distortion=0.3), 0.5)
    rn = g.noise(1.0, 2.0, 0.5, vector=mapped(g, lco, (4.5, 4.5, 4.5), (2.0, 7.0, 1.0)), distortion=0.8)
    ridge = g.ramp(M("SUBTRACT", 1.0, M("ABSOLUTE", M("SUBTRACT", M("MULTIPLY", rn, 2.0), 1.0))), 0.9, 0.99)
    drape = M("SUBTRACT", g.noise(1.0, 3.0, 0.55, vector=mapped(g, lco, (5.5, 5.5, 1.1)), distortion=0.4), 0.5)
    crease = M("SUBTRACT", g.noise(1.0, 3.0, 0.5, vector=mapped(g, lco, (3.0, 3.0, 10.0), rot=(0.0, 0.7, 0.0))), 0.5)
    crink = M("SUBTRACT", g.noise(1.0, 5.0, 0.6, vector=mapped(g, lco, (13.0, 13.0, 13.0)), distortion=0.9), 0.5)
    folds = M("ADD", M("MULTIPLY", drape, 2.8), M("ADD", M("MULTIPLY", crink, 0.8), M("MULTIPLY", crease, 1.1)))
    felt_t = M("ADD", M("ADD", M("MULTIPLY", pil, 1.3), M("MULTIPLY", lump, 0.7)),
               M("SUBTRACT", M("MULTIPLY", crink, 0.3), M("MULTIPLY", ridge, 0.25)))
    felt_s = M("ADD", -0.55, folds)
    felt = g.mixf(taut, felt_s, felt_t)
    outer_h = M("MAXIMUM", felt, M("MULTIPLY", wire_h, 1.1))
    imprint = M("MAXIMUM", g.ramp(dx, RW * 3.0, RW * 0.5), g.ramp(dz, RW * 3.0, RW * 0.5))
    inner_h = M("SUBTRACT", folds, M("MULTIPLY", imprint, 0.12))
    soft_h = M("ADD", M("MULTIPLY", crink, 0.9), M("MULTIPLY", crease, 0.5))
    macro = M("ADD", M("ADD", M("MULTIPLY", outer, outer_h), M("MULTIPLY", inner, inner_h)),
              M("MULTIPLY", M("ADD", rim, flap), soft_h))

    # ---- fibres of the non-woven felt
    f1 = g.noise(1.0, 3.0, 0.6, vector=mapped(g, lco, (30.0, 240.0, 240.0)))
    f2 = g.noise(1.0, 3.0, 0.6, vector=mapped(g, lco, (240.0, 240.0, 30.0)))
    f3 = g.noise(1.0, 3.0, 0.6, vector=mapped(g, lco, (35.0, 220.0, 220.0), rot=(0.0, 0.8, 0.0)))
    fib = g.ramp(M("MAXIMUM", M("MAXIMUM", f1, f2), f3), 0.58, 0.82)
    fuzz = g.noise(1.0, 4.0, 0.7, vector=mapped(g, lco, (180.0, 180.0, 180.0)))
    micro = M("MULTIPLY", M("ADD", M("MULTIPLY", fib, 0.6), M("MULTIPLY", fuzz, 0.5)), M("SUBTRACT", 1.0, wire_m))

    # ---- felt color: photo-mottled tan, each square its own shade, fibres, sun-bleached toward the top
    ph = photo_at(g, "rust_coarse_01", lco, 0.75, (0.31, 0.77, 0.19))["diff"]
    lum = tk._luma(g, ph)
    tone = g.noise(1.0, 6.0, 0.6, vector=mapped(g, lco, (2.0, 2.0, 2.0)))
    t = M("ADD", M("ADD", M("MULTIPLY", tone, 0.55), M("MULTIPLY", g.ramp(lum, 0.05, 0.22), 0.6)),
          M("MULTIPLY", M("SUBTRACT", fuzz, 0.5), 0.4))
    col = g.mix(g.ramp(t, 0.35, 0.95), TAN_D, TAN_L)
    col = scale_col(g, col, M("ADD", 0.86, M("MULTIPLY", cr2, M("ADD", 0.12, M("MULTIPLY", taut, 0.16)))))
    cloud = g.noise(1.0, 3.0, 0.5, vector=mapped(g, lco, (24.0, 24.0, 24.0)))
    col = scale_col(g, col, M("ADD", 0.88, M("MULTIPLY", cloud, 0.24)))
    col = g.mix(M("MULTIPLY", fib, 0.35), col, FIBRE)
    bleach = M("MULTIPLY", g.ramp(h, 0.7, 1.9), M("ADD", M("MULTIPLY", outer, 0.4), M("MULTIPLY", rim, 0.55)))
    col = g.mix(bleach, col, BLEACH)
    # grime: photo blotches and patches, heavier on the dirty variants
    blot = g.ramp(lum, 0.15, 0.06)
    pat = g.ramp(g.noise(1.0, 8.0, 0.62, vector=mapped(g, lco, (3.0, 3.0, 3.0)), distortion=0.5), 0.52, 0.68)
    grime = M("MULTIPLY", M("MAXIMUM", blot, pat), M("ADD", 0.45, M("MULTIPLY", dirt, 0.45)))
    col = g.mix(grime, col, GRIME)
    # crevices: dirt packed along the wires where taut, shadow behind them where slack
    near = g.ramp(M("MINIMUM", dx, dz), RW * 4.0, RW * 1.0)
    col = g.mix(M("MULTIPLY", M("MULTIPLY", near, g.mixf(taut, 0.6, 0.45)), outer), col, GRIME)
    # earth stains seeping out from the fill, with darker tide marks
    sn = g.noise(1.0, 6.0, 0.6, vector=mapped(g, lco, (3.2, 3.2, 3.2), (2.2, 0.3, 5.1)), distortion=0.6)
    seep = g.ramp(sn, 0.48, 0.6)
    tide = M("MULTIPLY", g.ramp(M("ABSOLUTE", M("SUBTRACT", sn, 0.48)), 0.012, 0.0), 0.6)
    seepw = M("MULTIPLY", M("ADD", 0.3, M("MULTIPLY", taut, 0.7)), M("ADD", 0.35, M("MULTIPLY", g.ramp(h, 1.6, 0.2), 0.65)))
    seepw = M("MULTIPLY", seepw, M("ADD", M("ADD", outer, M("MULTIPLY", flap, 1.5)), M("MULTIPLY", inner, 0.5)), clamp=True)
    col = g.mix(M("MULTIPLY", M("MULTIPLY", seep, 0.7), seepw), col, EARTH_STAIN)
    col = g.mix(M("MULTIPLY", tide, seepw), col, GRIME)
    # rain streaks: from the top and from every horizontal wire
    st = g.ramp(g.noise(1.0, 4.0, 0.6, vector=mapped(g, lco, (22.0, 22.0, 0.8))), 0.54, 0.74)
    st2 = g.ramp(g.noise(1.0, 2.0, 0.5, vector=mapped(g, lco, (80.0, 80.0, 1.6), (1.7, 0.0, 3.3))), 0.6, 0.78)
    topdrip = M("MULTIPLY", g.ramp(h, 1.4, 1.95), g.ramp(g.noise(1.0, 3.0, vector=mapped(g, lco, (35.0, 35.0, 3.0))),
                                                         0.45, 0.65))
    streak = M("MAXIMUM", M("MAXIMUM", st, M("MULTIPLY", st2, 0.8)), topdrip)
    streak = M("MULTIPLY", streak, M("ADD", 0.45, M("MULTIPLY", g.ramp(h, 0.4, 1.95), 0.55)))
    streak = M("MULTIPLY", streak, M("ADD", outer, M("MULTIPLY", rim, 0.5)))
    col = g.mix(M("MULTIPLY", streak, 0.65), col, STREAK)
    # rust run down from the crossings
    below = M("MULTIPLY", M("SUBTRACT", 1.0, fz), PZ)
    run_len = M("ADD", 0.01, M("MULTIPLY", dr, 0.07))
    run = g.ramp(below, run_len, 0.0, False)
    width = M("ADD", 0.0018, M("MULTIPLY", run, 0.0028))
    drip = M("MULTIPLY", M("MULTIPLY", g.ramp(dx, width, 0.0006), run), g.ramp(dr, 0.45, 0.53))
    col = g.mix(M("MULTIPLY", M("MULTIPLY", drip, outer), 0.85), col, RUST_STAIN)
    # mud: a caked band at the foot and splashes up to half a meter
    splat = M("MULTIPLY", g.ramp(tk._sock(voronoi(g, lco, 75.0).outputs, "Distance"), 0.24, 0.08),
              g.ramp(g.noise(1.0, 4.0, vector=mapped(g, lco, (9.0, 9.0, 9.0))), 0.3, 0.55))
    mudn = g.ramp(g.noise(1.0, 6.0, 0.65, vector=mapped(g, lco, (5.0, 5.0, 5.0))), 0.4, 0.62)
    mudz = g.ramp(h, 0.62, 0.03)
    edge = M("ADD", 0.12, M("MULTIPLY", g.noise(1.0, 3.0, vector=mapped(g, lco, (6.0, 6.0, 6.0), (1.0, 4.0, 0.0))), 0.14))
    mud = M("MAXIMUM", M("MULTIPLY", g.ramp(h, edge, 0.02), 0.95),
            M("MULTIPLY", mudz, M("MAXIMUM", splat, M("MULTIPLY", mudn, mudz))))
    foot = M("ADD", M("ADD", outer, M("MULTIPLY", inner, 0.5)), M("MULTIPLY", flap, 0.3))
    mud = M("MULTIPLY", mud, foot)
    col = scale_col(g, col, M("SUBTRACT", 1.0, M("MULTIPLY", M("MULTIPLY", g.ramp(h, 0.6, 0.0), 0.4), foot)))
    col = g.mix(M("MULTIPLY", mud, 0.92), col, MUD)
    # dust settled on the upper halves of the pillows, and on the rim
    dmask = g.ramp(g.noise(1.0, 5.0, vector=mapped(g, lco, (7.0, 7.0, 7.0))), 0.3, 0.7)
    dust = M("MULTIPLY", M("MULTIPLY", taut, g.ramp(fz, 0.45, 0.9)), M("MULTIPLY", pil, 0.55))
    dust = M("MULTIPLY", M("ADD", M("MULTIPLY", dust, outer), M("MULTIPLY", rim, 0.5)), dmask)
    dust = M("MULTIPLY", dust, M("SUBTRACT", 1.0, mud))
    col = g.mix(dust, col, DUST)
    # inner liner: shovelled earth specks and smears low down
    specks = M("MULTIPLY", M("MAXIMUM", splat, M("MULTIPLY", pat, 0.5)), M("MULTIPLY", g.ramp(h, 0.8, 0.0), inner))
    col = g.mix(M("MULTIPLY", specks, 0.85), col, EARTH_STAIN)
    # flaps: earth-soaked
    col = g.mix(M("MULTIPLY", flap, M("ADD", 0.3, M("MULTIPLY", dirt, 0.45))), col, EARTH_STAIN)
    # shading: under the wires where slack, the slack felt behind the mesh, inside the cage, fold hollows
    under = M("MULTIPLY", g.ramp(below, RW * 4.5, RW * 1.1), M("MULTIPLY", slack, 0.35))
    shade = M("MULTIPLY", under, outer)
    shade = M("ADD", shade, M("MULTIPLY", M("MULTIPLY", slack, outer), 0.14))
    shade = M("ADD", shade, M("MULTIPLY", inner, 0.16))
    col = scale_col(g, col, M("SUBTRACT", 1.0, shade, clamp=True))
    fshade = M("MULTIPLY", g.ramp(drape, 0.45, -0.45), M("MULTIPLY", M("ADD", M("MULTIPLY", slack, outer), inner), 0.3))
    col = scale_col(g, col, M("SUBTRACT", 1.0, fshade))

    # ---- the wires
    low = g.ramp(h, 0.45, 0.02)
    wcol, wmet, wrough = galv(g, lco, M("MULTIPLY", g.ramp(weld, 0.2, 0.6), M("MULTIPLY", dr, 1.2)), low)
    wcol = g.mix(M("MULTIPLY", M("MULTIPLY", streak, 0.5), M("SUBTRACT", 1.0, low)), wcol, STREAK)
    col = g.mix(wire_m, col, wcol)
    metal = M("MULTIPLY", wire_m, wmet)
    rough = g.mixf(wire_m, M("ADD", 0.88, M("MULTIPLY", fuzz, 0.1)), wrough)

    b1 = g.bump(macro, 1.0, M("MULTIPLY", ks, 0.006))
    b2 = g.bump(micro, 0.4, M("MULTIPLY", ks, 0.0012), normal=b1)
    return tk.finish(mat, g, col, metal, rough, b2)


def galv_material():
    """Corner coils (style 0: a tight helix round the pin, dark between the turns), plain wire and pins (style 1)."""
    mat, g = tk.new_material("Galv")
    M = g.math
    lco = attr_vec(g, "lco")
    x, y, z = g.separate(lco)
    style, rustb, _d = g.separate(attr_vec(g, "kd"))
    ks = g.separate(attr_vec(g, "kx"))[0]
    coil = eq(g, style, 0.0)
    pitch = PZ / 3.0
    ang = M("DIVIDE", M("ARCTAN2", y, x), 2 * math.pi)
    ft = M("FRACT", M("SUBTRACT", M("DIVIDE", z, pitch), ang))
    cw = roundp(g, M("MULTIPLY", M("ABSOLUTE", M("SUBTRACT", ft, 0.5)), pitch), 0.0045)
    gap = M("MULTIPLY", M("SUBTRACT", 1.0, g.ramp(cw, 0.05, 0.35)), coil)
    low = M("MULTIPLY", g.ramp(z, 0.35, 0.02), coil)
    col, metal, rough = galv(g, lco, M("MULTIPLY", rustb, g.ramp(g.noise(1.0, 5.0, vector=mapped(
        g, lco, (7.0, 7.0, 7.0))), 0.35, 0.55)), low)
    col = g.mix(M("MULTIPLY", gap, 0.88), col, (0.03, 0.029, 0.027))
    metal = M("MULTIPLY", metal, M("SUBTRACT", 1.0, gap))
    rough = g.mixf(gap, rough, 0.9)
    height = M("ADD", M("MULTIPLY", cw, coil), M("MULTIPLY", g.noise(1.0, 4.0, vector=mapped(g, lco, (90.0,) * 3)), 0.15))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 1.0, M("MULTIPLY", ks, 0.004)))


def earth_material():
    """Shovelled earth and clay with gravel: crusty, clodded, damp where fresh (kd: style 0 fill top, 1 pile, 2 pour,
    3 bulging through a tear, 4 breach mound; damp 0-1)."""
    mat, g = tk.new_material("Earth")
    M = g.math
    lco = attr_vec(g, "lco")
    _x, _y, z = g.separate(lco)
    style, damp, _d = g.separate(attr_vec(g, "kd"))
    ks = g.separate(attr_vec(g, "kx"))[0]
    _nx, _ny, nzz = local_normal(g)
    top, pile, pour, mound = eq(g, style, 0.0), eq(g, style, 1.0), eq(g, style, 2.0), eq(g, style, 4.0)
    ph = photo_at(g, "rust_coarse_01", lco, 0.8, (0.6, 0.2, 0.9), kinds=("diff", "disp"))
    crust = g.ramp(tk._luma(g, ph["diff"]), 0.07, 0.2)
    tone = g.noise(1.0, 6.0, 0.6, vector=mapped(g, lco, (2.0, 2.0, 2.0)))
    t = M("ADD", M("MULTIPLY", tone, 0.6), M("MULTIPLY", crust, 0.5))
    col = g.mix(g.ramp(t, 0.35, 0.8), EARTH_D, EARTH_L)
    clayp = g.ramp(g.noise(1.0, 6.0, 0.6, vector=mapped(g, lco, (3.5, 3.5, 3.5), (8.1, 3.3, 1.2)), distortion=0.4),
                   0.55, 0.7)
    col = g.mix(M("MULTIPLY", clayp, 0.6), col, CLAY)
    clod = g.ramp(g.noise(1.0, 5.0, 0.6, vector=mapped(g, lco, (16.0, 16.0, 16.0)), distortion=0.8), 0.45, 0.78)
    col = scale_col(g, col, M("ADD", 0.85, M("MULTIPLY", clod, 0.27)))
    grain = g.noise(1.0, 3.0, 0.5, vector=mapped(g, lco, (300.0, 300.0, 300.0)))
    col = scale_col(g, col, M("ADD", 0.8, M("MULTIPLY", grain, 0.38)))
    # stones and gravel
    v1 = voronoi(g, lco, 34.0)
    r1 = g.separate(tk._sock(v1.outputs, "Color"))
    stone = M("MULTIPLY", g.ramp(tk._sock(v1.outputs, "Distance"), 0.32, 0.22), g.ramp(r1[0], 0.8, 0.84))
    scol = g.mix(r1[1], STONE_D, STONE_L)
    scol = g.mix(g.ramp(r1[2], 0.7, 0.75), scol, STONE_R)
    col = g.mix(stone, col, scol)
    v2 = voronoi(g, mapped(g, lco, loc=(3.3, 1.1, 0.4)), 95.0)
    r2 = g.separate(tk._sock(v2.outputs, "Color"))
    stone2 = M("MULTIPLY", g.ramp(tk._sock(v2.outputs, "Distance"), 0.28, 0.18), g.ramp(r2[0], 0.82, 0.86))
    col = g.mix(M("MULTIPLY", stone2, 0.4), col, g.mix(r2[1], STONE_D, EARTH_L))
    # damp: fresh earth out of a tear, and where piles meet the ground
    groundc = M("MULTIPLY", g.ramp(z, 0.04, 0.0), M("ADD", M("ADD", pile, mound), pour))
    wet = M("ADD", M("MULTIPLY", damp, 0.7), M("MULTIPLY", groundc, 0.5), clamp=True)
    col = scale_col(g, col, M("SUBTRACT", 1.0, M("MULTIPLY", wet, 0.45)))
    # dried crust cracks on the fill top
    vc = voronoi(g, warped(g, lco, 4.0, 0.035), 10.0, "DISTANCE_TO_EDGE")
    crack = M("MULTIPLY", g.ramp(tk._sock(vc.outputs, "Distance"), 0.025, 0.004), M("MULTIPLY", top, 0.35))
    crack = M("MULTIPLY", crack, g.ramp(g.noise(1.0, 4.0, vector=mapped(g, lco, (2.5,) * 3, (3.0, 1.0, 0.0))),
                                        0.5, 0.65))
    dry = M("MULTIPLY", g.ramp(g.noise(1.0, 5.0, vector=mapped(g, lco, (2.5,) * 3, (1.0, 6.0, 2.0))), 0.52, 0.72),
            M("MULTIPLY", M("ADD", top, mound), 0.4))
    col = g.mix(dry, col, EARTH_DUST)
    col = g.mix(crack, col, CRACK)
    # dust on upward faces, where dry
    up = M("MULTIPLY", g.ramp(nzz, 0.55, 0.95), g.ramp(g.noise(1.0, 5.0, vector=mapped(g, lco, (4.0,) * 3)), 0.3, 0.7))
    up = M("MULTIPLY", up, M("MULTIPLY", M("SUBTRACT", 1.0, wet), 0.4))
    col = g.mix(up, col, EARTH_DUST)
    # pour: streaked along the flow
    flow = M("MULTIPLY", g.ramp(g.noise(1.0, 3.0, vector=mapped(g, lco, (30.0, 30.0, 2.0))), 0.4, 0.7), pour)
    col = scale_col(g, col, M("SUBTRACT", 1.0, M("MULTIPLY", flow, 0.25)))
    # dead grass and roots on the old fill top and the mound
    straw = None
    for k, rot in enumerate(((0.0, 0.0, 0.3), (0.0, 0.0, 1.4), (0.0, 0.0, 2.5))):
        s = g.ramp(g.noise(1.0, 2.0, vector=mapped(g, lco, (220.0, 6.0, 220.0), (k * 1.7, k * 0.3, 0.0), rot)),
                   0.68, 0.72)
        straw = s if straw is None else M("MAXIMUM", straw, s)
    straw = M("MULTIPLY", straw, g.ramp(g.noise(1.0, 4.0, vector=mapped(g, lco, (3.0,) * 3, (5.5, 2.0, 1.0))),
                                        0.5, 0.65))
    straw = M("MULTIPLY", straw, M("MULTIPLY", M("ADD", top, mound), 0.6))
    col = g.mix(straw, col, STRAW)
    rough = M("SUBTRACT", M("SUBTRACT", 0.95, M("MULTIPLY", stone, 0.25)), M("MULTIPLY", wet, 0.15))
    height = M("ADD", M("ADD", M("MULTIPLY", clod, 0.7), M("MULTIPLY", stone, 0.9)),
               M("ADD", M("MULTIPLY", stone2, 0.5), M("MULTIPLY", ph["disp"], 0.4)))
    height = M("SUBTRACT", height, M("MULTIPLY", crack, 0.5))
    b1 = g.bump(height, 1.0, M("MULTIPLY", ks, 0.012))
    b2 = g.bump(M("ADD", grain, M("MULTIPLY", straw, 0.6)), 0.3, M("MULTIPLY", ks, 0.0015), normal=b1)
    return tk.finish(mat, g, col, 0.0, rough, b2)


# ---------------------------------------------------------------- kit shapes

def outline(t, seed):
    return 1.0 + 0.15 * math.sin(3 * t + seed) + 0.08 * math.sin(5 * t + 2.3 * seed)


def bulge_bm(rx, rz, depth, seed, drop=0.0, segs=14, rings=(1.0, 0.8, 0.56, 0.3)):
    """Earth pushing out through a tear: a lobed mound in XZ bulging toward -y, base ring on y = 0."""
    vs, ids = [], []
    for rho in rings:
        row = []
        for i in range(segs):
            t = 2 * math.pi * i / segs
            rr = outline(t, seed)
            a = rx * rr * rho * math.cos(t)
            b = rz * rr * rho * math.sin(t)
            if b < 0:
                b *= 1.0 + drop
            d = depth * (1.0 - rho * rho) ** 0.55 + 0.002
            d += depth * 0.22 * pnoise((a, b, 0.0), seed, 16.0) * (1.0 - rho)
            d *= 1.0 + 0.2 * max(0.0, -math.sin(t))
            row.append(len(vs))
            vs.append((a, -d, b))
        ids.append(row)
    ci = len(vs)
    vs.append((0.0, -depth * 1.06, -rz * 0.08))
    faces = []
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([ids[k][i], ids[k][j], ids[k + 1][j], ids[k + 1][i]])
    for i in range(segs):
        faces.append([ids[-1][i], ids[-1][(i + 1) % segs], ci])
    bm = bm_from(vs, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    return bm


def pile_bm(seed, segs=12):
    """A heap of spilled earth, radius 0.5 m, 0.25 m high, open underneath."""
    rings = (1.0, 0.84, 0.64, 0.42, 0.2)
    vs, ids = [], []
    for rho in rings:
        row = []
        for i in range(segs):
            t = 2 * math.pi * i / segs
            rr = 1.0 + 0.11 * math.sin(3 * t + seed) + 0.07 * math.sin(5 * t + 1.7 * seed) + 0.04 * math.sin(9 * t)
            x, y = 0.5 * rr * rho * math.cos(t), 0.5 * rr * rho * math.sin(t)
            z = 0.25 * (1.0 - rho ** 1.7) ** 1.25 + 0.002
            z += 0.03 * pnoise((x, y, 0.0), seed, 9.0) * (1.0 - rho ** 3)
            row.append(len(vs))
            vs.append((x, y, max(z, 0.0015)))
        ids.append(row)
    ci = len(vs)
    vs.append((0.0, 0.0, 0.255))
    faces = []
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([ids[k][i], ids[k][j], ids[k + 1][j], ids[k + 1][i]])
    for i in range(segs):
        faces.append([ids[-1][i], ids[-1][(i + 1) % segs], ci])
    bm = bm_from(vs, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return bm


def mound_height(rho):
    return (1.0 - rho ** 2.6) ** 0.9


def mound_bm(seed, segs=28):
    """The breach mound: about 1 m high, square-ish to fill its cell (a superellipse footprint), slumped and spread
    a little to the front, lumpy. Open underneath."""
    rings = (1.0, 0.92, 0.82, 0.7, 0.57, 0.44, 0.3, 0.16)
    vs, ids = [], []
    p = 3.2
    for rho in rings:
        row = []
        for i in range(segs):
            t = 2 * math.pi * i / segs
            se = (abs(math.cos(t)) ** p + abs(math.sin(t)) ** p) ** (-1.0 / p)
            r = 0.56 * se * (1.0 + 0.06 * math.sin(3 * t + seed) + 0.035 * math.sin(7 * t + 2 * seed)) * rho
            if math.sin(t) < 0:
                r *= 1.0 + 0.08 * -math.sin(t)
            x, y = r * math.cos(t), r * math.sin(t)
            z = mound_height(rho) + 0.002
            z += 0.045 * pnoise((x, y, 0.0), seed, 4.0) * (1.0 - rho ** 4) + 0.015 * pnoise((x, y, 0.0), seed + 3, 13.0)
            row.append(len(vs))
            vs.append((x, y, max(z, 0.0015)))
        ids.append(row)
    ci = len(vs)
    vs.append((0.0, -0.02, 1.0))
    faces = []
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([ids[k][i], ids[k][j], ids[k + 1][j], ids[k + 1][i]])
    for i in range(segs):
        faces.append([ids[-1][i], ids[-1][(i + 1) % segs], ci])
    bm = bm_from(vs, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return bm


def flap_bm(seed, w=0.12, h=0.09):
    """A torn felt flap: a jagged strip hanging from its top edge (z = 0 down to -h), curling toward -y."""
    rnd = random.Random(seed)
    nx, nz = 3, 2
    verts = []
    for k in range(nz + 1):
        f = k / nz
        for i in range(nx + 1):
            x = -w / 2 + w * i / nx
            zz = -h * f
            if k == nz:
                zz += rnd.uniform(0.0, 0.04) * (1.0 + (i % 2))
            if i in (0, nx):
                x *= 1.0 - 0.3 * f * rnd.uniform(0.3, 1.0)
            y = -0.022 * f * f - 0.008 * math.sin(i * 1.7 + seed) * f
            verts.append((x, y, zz))
    faces = []
    for k in range(nz):
        for i in range(nx):
            a = k * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
    bm = bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.004)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def tube_bm(points, radius, sides, uv=True):
    """A tube along a polyline with flat caps, UVs unwrapped (u round, v along) when uv is set."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    tang = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tang.append((b - a).normalized())
    up = Vector((0.0, 0.0, 1.0)) if abs(tang[0].z) < 0.9 else Vector((1.0, 0.0, 0.0))
    bm = bmesh.new()
    rings, lengths = [], [0.0]
    for i in range(1, n):
        lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
    nrm = (up - tang[0] * up.dot(tang[0])).normalized()
    for i in range(n):
        t = tang[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        bin_ = t.cross(nrm)
        ring = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            ring.append(bm.verts.new(pts[i] + (nrm * math.cos(a) + bin_ * math.sin(a)) * radius))
        rings.append(ring)
    uvl = bm.loops.layers.uv.new("UVMap") if uv else None
    circ = 2 * math.pi * radius
    for i in range(n - 1):
        for k in range(sides):
            f = bm.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][k + 1], rings[i][k + 1]))
            if uvl:
                for loop, (kk, ii) in zip(f.loops, ((k, i), (k, i + 1), (k + 1, i + 1), (k + 1, i))):
                    loop[uvl].uv = (circ * kk / sides, lengths[ii])
    for i, sign in ((0, -1), (n - 1, 1)):
        vs = rings[i][:sides]
        f = bm.faces.new(vs if sign > 0 else list(reversed(vs)))
        if uvl:
            for loop in f.loops:
                kk = vs.index(loop.vert)
                a = 2 * math.pi * kk / sides
                loop[uvl].uv = (circ * 2 + radius * (1 + math.cos(a)) + (0.0 if sign < 0 else 3 * radius),
                                -0.02 - radius * (1 + math.sin(a)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rod_bm(sides=6, rings=5):
    """The corner coil: a cylinder of radius RC from h = 0 to H + 0.008, with a cap, unwrapped round and along."""
    top = H + 0.008
    pts = [(0.0, 0.0, top * k / (rings - 1)) for k in range(rings)]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    circ = 2 * math.pi * RC
    for (_, _, z) in pts:
        row = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            row.append(bm.verts.new((RC * math.cos(a), RC * math.sin(a), z)))
        grid.append(row)
    for i in range(rings - 1):
        for k in range(sides):
            f = bm.faces.new((grid[i][k], grid[i][k + 1], grid[i + 1][k + 1], grid[i + 1][k]))
            for loop, (kk, ii) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                loop[uvl].uv = (circ * kk / sides, pts[ii][2])
    cap = grid[-1][:sides]
    f = bm.faces.new(cap)
    for loop in f.loops:
        loop[uvl].uv = (circ + 0.03 + loop.vert.co.x, top + 0.03 + loop.vert.co.y)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def shovel_bms():
    """A round-point shovel along +z (blade tip at the origin): the steel blade and socket, and the wooden handle
    with a T grip."""
    bm = bmesh.new()
    nu, nv = 6, 7
    grid = []
    for j in range(nv):
        t = j / (nv - 1)
        w = 0.112 * (1.0 - (1.0 - min(t / 0.62, 1.0)) ** 2) ** 0.5
        w = max(w, 0.006)
        row = []
        for i in range(nu):
            s = 2.0 * i / (nu - 1) - 1.0
            x = w * s
            y = 0.024 * (x / 0.112) ** 2 - 0.012 * t
            row.append(bm.verts.new((x, y, 0.3 * t)))
        grid.append(row)
    for j in range(nv - 1):
        for i in range(nu - 1):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.0035)
    sock = tube_bm([(0.0, -0.01, 0.27), (0.0, -0.006, 0.36), (0.0, 0.0, 0.44)], 0.024, 7, uv=False)
    for v in sock.verts:  # flattened where it meets the blade
        if v.co.z < 0.33:
            v.co.y = v.co.y * 0.55 - 0.004
    me = bpy.data.meshes.new("tmp")
    sock.to_mesh(me)
    sock.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    blade = bm
    handle = tube_bm([(0.0, 0.0, 0.4), (0.0, 0.0, 0.9), (0.0, 0.0, 1.32)], 0.0175, 7, uv=False)
    grip = tube_bm([(-0.065, 0.0, 1.335), (0.065, 0.0, 1.335)], 0.016, 7, uv=False)
    me = bpy.data.meshes.new("tmp")
    grip.to_mesh(me)
    grip.free()
    handle.from_mesh(me)
    bpy.data.meshes.remove(me)
    return blade, handle


# ---------------------------------------------------------------- the kit

KIT = []
META = {}
CONTEXT = []


def set_attr(me, name, domain, kind, values):
    a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
    a.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", values)


def kit_part(name, bm, mat, style=0.0, a1=0.0, a2=0.5, kscale=1.0, dom=None, context=None, **meta):
    """A kit part from a bmesh in its real coordinates (stored as lco); its kit copy is scaled by kscale, which sets
    its share of the atlas. Custom UVs (patches, tubes) come in the bmesh's UVMap layer, in meters."""
    bm.verts.ensure_lookup_table()
    lco = np.array([v.co[:] for v in bm.verts], np.float32)
    custom = bm.loops.layers.uv.get("UVMap") is not None
    for v in bm.verts:
        v.co *= kscale
    if custom:
        uvl = bm.loops.layers.uv["UVMap"]
        for f in bm.faces:
            for loop in f.loops:
                loop[uvl].uv = loop[uvl].uv * kscale
    obj = tk.mesh_object("Kit_" + name, bm, mat)
    me = obj.data
    n = len(me.vertices)
    set_attr(me, "lco", "POINT", "FLOAT_VECTOR", lco.ravel())
    set_attr(me, "kd", "POINT", "FLOAT_VECTOR", np.tile(np.array([style, a1, a2], np.float32), n))
    set_attr(me, "kx", "POINT", "FLOAT_VECTOR", np.tile(np.array([kscale, 0.0, 0.0], np.float32), n))
    d = np.zeros((n, 3), np.float32) if dom is None else np.array(dom, np.float32)
    set_attr(me, "dom", "POINT", "FLOAT_VECTOR", d.ravel())
    set_attr(me, "kpart", "FACE", "INT", np.full(len(me.polygons), len(KIT), np.int32))
    for p in me.polygons:
        p.use_smooth = True
    META[name] = dict(index=len(KIT), custom=custom, kscale=kscale, context=context, **meta)
    KIT.append(obj)
    return obj


def patch_part(name, mat, dom, to3d, style, a1=0.0, a2=0.5, kscale=1.0, context=None):
    """A flat rectangular patch: domain (u0, u1, v0, v1) in meters, to3d(u, v) its real position."""
    u0, u1, v0, v1 = dom
    corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    bm = bmesh.new()
    vs = [bm.verts.new(to3d(u, v)) for u, v in corners]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.new("UVMap")
    for loop, (u, v) in zip(f.loops, corners):
        loop[uvl].uv = (u, v)
    return kit_part(name, bm, mat, style, a1, a2, kscale, dom=[(u, v, 0.0) for u, v in corners], context=context,
                    patch=dom)


def build_kit():
    liner = liner_material()
    earth = earth_material()
    galvm = galv_material()
    wood = tk.photo_material("ShovelWood", "weathered_planks", scale=3.0, sat=0.55, value=0.75, exposed=None,
                             grime=0.9, grit=0.6, scratches=0.2)
    steel = tk.photo_material("ShovelSteel", "rusty_painted_metal", scale=2.0, sat=0.35, value=0.45,
                              exposed="rust_coarse_01", chip=0.9, patches=0.6, grime=0.8, metal_floor=0.3, grit=0.7,
                              scratches=0.5, edges=0.6)

    def wall_xyz(u, v):
        return (u, 0.0, v)

    # outer wall bands: taut and slack, two variants; inner liner bands
    for b in range(3):
        dom = (0.0, WK, BANDS[b], BANDS[b + 1])
        for var in ("", "B"):
            patch_part("WT%d%s" % (b, var), liner, dom, wall_xyz, 0.0, a1=1.0, a2=0.55 if var else 0.4)
        patch_part("WS%d" % b, liner, dom, wall_xyz, 0.0, a1=0.0, a2=0.4)
        patch_part("WI%d" % b, liner, dom, wall_xyz, 1.0, a1=0.0, a2=0.3, kscale=0.5)
    patch_part("RIM", liner, (0.0, WK, 0.0, RIMW), lambda u, v: (u, 0.0, H + v), 2.0, a2=0.3)
    patch_part("TOP", earth, (-0.46, 0.46, -0.46, 0.46), lambda u, v: (u, v, 0.0), 0.0, a1=0.05, kscale=0.75,
               context="top")
    patch_part("POUR", earth, (-0.2, 0.2, 0.0, 1.2), lambda u, v: (u, 0.0, 1.2 - v), 2.0, a1=0.55, kscale=0.65)
    # earth: piles, the mound, bulges through tears
    for k, seed in enumerate((3, 8)):
        kit_part("PILE%d" % k, pile_bm(seed), earth, 1.0, a1=0.25, kscale=0.6, context="ground")
    kit_part("MOUND", mound_bm(5), earth, 4.0, a1=0.1, kscale=0.6, context="ground")
    for name, rx, rz, depth, seed, drop, ksc in (("BUL0", 0.085, 0.11, 0.032, 11, 0.3, 1.0),
                                                 ("BUL1", 0.07, 0.085, 0.026, 12, 0.2, 1.0),
                                                 ("BUL2", 0.2, 0.25, 0.065, 13, 0.45, 0.9)):
        kit_part(name, bulge_bm(rx, rz, depth, seed, drop), earth, 3.0, a1=0.6, kscale=ksc, context="wall",
                 rx=rx, rz=rz, depth=depth, seed=seed, drop=drop)
    # felt flaps
    for k, (seed, w, h) in enumerate(((71, 0.12, 0.09), (72, 0.1, 0.07), (73, 0.15, 0.12))):
        kit_part("FL%d" % k, flap_bm(seed, w, h), liner, 3.0, a1=0.0, a2=0.6 + 0.15 * k, w=w, h=h)
    # metal: corner coil, plain wire, pin
    kit_part("ROD", rod_bm(), galvm, 0.0, a1=0.35)
    kit_part("WIRE", tube_bm([(i / 6.0, 0.0, 0.0) for i in range(7)], 0.003, 3), galvm, 1.0, a1=0.3)
    kit_part("STUB", tube_bm([(i / 3.0, 0.0, 0.0) for i in range(4)], 0.003, 3), galvm, 1.0, a1=0.5)
    kit_part("PIN", tube_bm([(0.0, 0.0, -0.008), (0.0, 0.0, 0.01), (0.008, 0.0, 0.0165), (0.016, 0.0, 0.006)],
                            0.0045, 4), galvm, 1.0, a1=0.6)
    blade, handle = shovel_bms()
    kit_part("SHB", blade, steel)
    kit_part("SHH", handle, wood)
    return dict(liner=liner, earth=earth, galv=galvm)


def layout_kit():
    """Spreads the parts on shelves far enough apart that the AO bake only sees each part (and its context)."""
    x, y, row_d = 0.0, 0.0, 0.0
    occ = None
    for obj in KIT:
        name = obj.name[4:]
        co = np.array([v.co[:] for v in obj.data.vertices])
        lo, hi = co.min(axis=0), co.max(axis=0)
        w, d = hi[0] - lo[0], hi[1] - lo[1]
        if x + w > 6.5:
            x, y, row_d = 0.0, y + row_d + 0.45, 0.0
        obj.location = (x - lo[0], y - lo[1], 0.0)
        ctx = META[name]["context"]
        if ctx is not None:
            if occ is None:
                occ, _g = tk.new_material("Occluder")
                tk.finish(occ, _g, (0.5, 0.5, 0.5), 0.0, 0.8)
            cx, cy = x + w / 2, y + d / 2
            if ctx == "ground":
                CONTEXT.append(tk.box("Ctx_" + name, (w + 0.3, d + 0.3, 0.02), (cx, cy, lo[2] - 0.012), occ))
            elif ctx == "wall":
                CONTEXT.append(tk.box("Ctx_" + name, (w + 0.2, 0.02, hi[2] - lo[2] + 0.2),
                                      (cx, y + d + 0.012, (lo[2] + hi[2]) / 2), occ))
            elif ctx == "top":
                for sx, sy, ox, oy in ((w + 0.04, 0.02, 0.0, -d / 2 - 0.012), (w + 0.04, 0.02, 0.0, d / 2 + 0.012),
                                       (0.02, d + 0.04, -w / 2 - 0.012, 0.0), (0.02, d + 0.04, w / 2 + 0.012, 0.0)):
                    CONTEXT.append(tk.box("Ctx_" + name, (sx, sy, 0.25), (cx + ox, cy + oy, 0.1), occ))
        x += w + 0.45
        row_d = max(row_d, d)
    bpy.context.view_layer.update()


def kit_uvs():
    smart = [o for o in KIT if not META[o.name[4:]]["custom"]]
    for o in bpy.context.scene.objects:
        o.select_set(o in smart)
    bpy.context.view_layer.objects.active = smart[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def pack_uvs(obj):
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    try:
        bpy.ops.uv.pack_islands(rotate=True, rotate_method="CARDINAL", margin_method="FRACTION", margin=0.006,
                                shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_kit():
    kit_uvs()
    kit = tk.join(list(KIT), "HescoKit")
    kit = tk.triangulate(kit)
    pack_uvs(kit)
    if os.environ.get("HESCO_CPU"):
        bpy.context.scene.cycles.device = "CPU"
    try:
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME, size=TEX)
        ok = image_mean(paths["albedo"]) > 0.02
    except Exception as e:  # GPU out of memory (other Blender jobs share the card)
        log("bake failed on the GPU:", e)
        ok = False
    if not ok:
        log("baking again on the CPU")
        bpy.context.scene.cycles.device = "CPU"
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME, size=TEX)
    brighten(paths["albedo"])
    for o in CONTEXT:
        bpy.data.objects.remove(o)
    return kit, paths


# In the game's shader the flat liner walls came out much darker in shade than vanilla sandbags (a flat vertical face
# only gets the horizon's ambient light), and real Hesco liners are a lighter tan, so the baked albedo is lifted.
ALBEDO_GAIN = 1.25


def brighten(path):
    img = bpy.data.images.load(path, check_existing=False)
    px = np.empty(len(img.pixels), np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    px[:, :3] = np.clip(px[:, :3] * ALBEDO_GAIN, 0.0, 1.0)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    log("albedo lifted x%.2f" % ALBEDO_GAIN)


# ---------------------------------------------------------------- templates and patches

class Tpl:
    def __init__(self, name, V, F, UV, meta):
        self.name, self.V, self.F, self.UV, self.meta = name, V, F, UV, meta
        self.lo, self.hi = V.min(axis=0), V.max(axis=0)


class Patch:
    """A baked rectangle: maps domain coordinates (meters) to the atlas by its corner UVs."""

    def __init__(self, name, dom, c00, c10, c01, c11):
        self.name, self.dom = name, dom
        self.c = [np.array(c) for c in (c00, c10, c01, c11)]

    def uv(self, u, v):
        u0, u1, v0, v1 = self.dom
        eu, ev = (u1 - u0) * 0.002, (v1 - v0) * 0.002
        tu = (np.clip(u, u0 + eu, u1 - eu) - u0) / (u1 - u0)
        tv = (np.clip(v, v0 + ev, v1 - ev) - v0) / (v1 - v0)
        tu, tv = np.asarray(tu)[..., None], np.asarray(tv)[..., None]
        c00, c10, c01, c11 = self.c
        return (1 - tu) * (1 - tv) * c00 + tu * (1 - tv) * c10 + (1 - tu) * tv * c01 + tu * tv * c11


def extract(kit):
    me = kit.data
    nv, nf = len(me.vertices), len(me.polygons)

    def vattr(name):
        a = np.empty(nv * 3, np.float32)
        me.attributes[name].data.foreach_get("vector", a)
        return a.reshape(-1, 3).astype(np.float64)

    lco, dom = vattr("lco"), vattr("dom")
    loops = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loops)
    ls = np.empty(nf, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(nf, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    assert (lt == 3).all(), "kit is not triangulated"
    idx = ls[:, None] + np.arange(3)[None, :]
    F = loops[idx]
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    UV = uv.reshape(-1, 2)[idx].astype(np.float64)
    kp = np.empty(nf, np.int32)
    me.attributes["kpart"].data.foreach_get("value", kp)
    tpls, patches = {}, {}
    for name, m in META.items():
        sel = np.nonzero(kp == m["index"])[0]
        f = F[sel]
        used = np.unique(f)
        remap = np.full(nv, -1, np.int64)
        remap[used] = np.arange(len(used))
        tpls[name] = Tpl(name, lco[used], remap[f], UV[sel], m)
        if "patch" in m:
            u0, u1, v0, v1 = m["patch"]
            cd = dom[f].reshape(-1, 3)[:, :2]
            cu = UV[sel].reshape(-1, 2)
            got = []
            for c in ((u0, v0), (u1, v0), (u0, v1), (u1, v1)):
                k = np.argmin(np.linalg.norm(cd - np.array(c), axis=1))
                got.append(cu[k])
            patches[name] = Patch(name, m["patch"], *got)
    return tpls, patches


# ---------------------------------------------------------------- mesh accumulation

class Acc:
    def __init__(self):
        self.V, self.F, self.UV, self.n, self.tags, self.ext = [], [], [], 0, {}, {}

    def add(self, V, F, UV, tag="misc"):
        V = np.asarray(V, float).reshape(-1, 3)
        F = np.asarray(F, np.int64).reshape(-1, 3)
        if len(F) == 0:
            return
        self.V.append(V)
        self.F.append(F + self.n)
        self.UV.append(np.asarray(UV, float).reshape(-1, 3, 2))
        self.n += len(V)
        self.tags[tag] = self.tags.get(tag, 0) + len(F)
        used = V[np.unique(F)]
        lo, hi = used.min(axis=0), used.max(axis=0)
        if tag in self.ext:
            lo, hi = np.minimum(lo, self.ext[tag][0]), np.maximum(hi, self.ext[tag][1])
        self.ext[tag] = (lo, hi)

    def tris(self):
        return sum(len(f) for f in self.F)


def grid_add(acc, P, U, Vd, row_patches, flip=False, tag="grid"):
    """Adds a (R, C) grid of points; quad row r is textured by row_patches[r] at domain coordinates (U, Vd)."""
    R, Cn = U.shape
    idx = np.arange(R * Cn).reshape(R, Cn)
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    if not flip:
        t1, t2 = np.stack([a, b, c], -1), np.stack([a, c, d], -1)
    else:
        t1, t2 = np.stack([a, c, b], -1), np.stack([a, d, c], -1)
    F = np.stack([t1, t2], 2).reshape(-1, 3)
    UVr = np.zeros((R - 1, Cn - 1, 2, 3, 2))
    for r in range(R - 1):
        p = row_patches[r]
        lo, hi = p.uv(U[r], Vd[r]), p.uv(U[r + 1], Vd[r + 1])
        A_, B_, C_, D_ = lo[:-1], lo[1:], hi[1:], hi[:-1]
        if not flip:
            UVr[r, :, 0], UVr[r, :, 1] = np.stack([A_, B_, C_], 1), np.stack([A_, C_, D_], 1)
        else:
            UVr[r, :, 0], UVr[r, :, 1] = np.stack([A_, C_, B_], 1), np.stack([A_, D_, C_], 1)
    acc.add(np.asarray(P).reshape(-1, 3), F, UVr.reshape(-1, 3, 2), tag)


def add_tpl(acc, tpl, R, t, hidden=None, tag="tpl", V=None):
    """A kit template moved by rotation/scale matrix R (3x3, det > 0) and offset t (or given vertices V); faces whose
    three corners are all hidden(V) are left out."""
    if V is None:
        V = tpl.V @ np.asarray(R).T + np.asarray(t)
    F, UV = tpl.F, tpl.UV
    if hidden is not None:
        hmask = hidden(V)
        keep = ~hmask[F].all(axis=1)
        F, UV = F[keep], UV[keep]
    acc.add(V, F, UV, tag)
    return V


def sweep(tpl, pts, up=(0.0, 0.0, 1.0), axis=0):
    """Bends a straight template (along x from 0 to 1, or along z from 0 for the coil with axis=2) along a polyline;
    its cross-section keeps its orientation relative to `up`."""
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    V = tpl.V
    if axis == 0:
        tpar = (V[:, 0] - tpl.lo[0]) / max(tpl.hi[0] - tpl.lo[0], 1e-9) * total
        o1, o2 = V[:, 1], V[:, 2]
    else:
        tpar = np.clip(V[:, 2], 0.0, None) / max(tpl.hi[2], 1e-9) * total
        o1, o2 = V[:, 0], V[:, 1]
    out = np.zeros_like(V)
    upv = unit(up)
    for i in range(len(V)):
        k = min(np.searchsorted(cum, tpar[i], side="right") - 1, len(seg) - 1)
        k = max(k, 0)
        f = (tpar[i] - cum[k]) / max(seg[k], 1e-9)
        p = pts[k] + (pts[k + 1] - pts[k]) * f
        tg = unit(pts[k + 1] - pts[k])
        if axis == 0:
            n2 = unit(upv - tg * upv.dot(tg))
            n1 = np.cross(n2, tg)
            out[i] = p + n1 * o1[i] + n2 * o2[i]
        else:
            ref = np.array((1.0, 0.0, 0.0)) if abs(tg[0]) < 0.9 else np.array((0.0, 1.0, 0.0))
            n1 = unit(ref - tg * ref.dot(tg))
            n2 = np.cross(tg, n1)
            out[i] = p + n1 * o1[i] + n2 * o2[i]
    return out


# ---------------------------------------------------------------- the cage

class Cell:
    def __init__(self, cx, hx, shared_l=False, shared_r=False):
        self.cx, self.hx, self.hy = cx, hx, C
        self.shared_l, self.shared_r = shared_l, shared_r


class Wall:
    def __init__(self, A, B, cell, kind="outer", variant=0, mirror=False):
        self.A, self.B = np.array(A, float), np.array(B, float)
        self.L = float(np.linalg.norm(self.B - self.A))
        self.d = (self.B - self.A) / self.L
        self.n = np.array([self.d[1], -self.d[0]])
        self.cell, self.kind, self.variant, self.mirror = cell, kind, variant, mirror

    def p0(self, s, h, off=0.0):
        s, h = np.asarray(s, float), np.asarray(h, float)
        off = np.broadcast_to(np.asarray(off, float), s.shape)
        x = self.A[0] + self.d[0] * s + self.n[0] * off
        y = self.A[1] + self.d[1] * s + self.n[1] * off
        return np.stack([x, y, Z0 + h + 0.0 * s], -1)

    def u(self, s):
        u = np.asarray(s) * WK / self.L
        return WK - u if self.mirror else u


def layout(double):
    if not double:
        P = [(-C, -C), (C, -C), (C, C), (-C, C)]
        cells = [Cell(0.0, C)]
        walls = [Wall(P[0], P[1], 0, "outer", 0, False), Wall(P[1], P[2], 0, "outer", 1, True),
                 Wall(P[2], P[3], 0, "outer", 1, False), Wall(P[3], P[0], 0, "outer", 0, True)]
        return cells, walls, P
    X, hx = CDX, CDX / 2
    cells = [Cell(-hx, hx, shared_r=True), Cell(hx, hx, shared_l=True)]
    walls = [Wall((-X, -C), (0, -C), 0, "outer", 0, False), Wall((0, -C), (X, -C), 1, "outer", 1, True),
             Wall((X, -C), (X, C), 1, "outer", 0, True), Wall((X, C), (0, C), 1, "outer", 1, False),
             Wall((0, C), (-X, C), 0, "outer", 0, True), Wall((-X, C), (-X, -C), 0, "outer", 1, False),
             Wall((0, -C), (0, C), None, "shared")]
    rods = [(-X, -C), (0, -C), (X, -C), (X, C), (0, C), (-X, C)]
    return cells, walls, rods


def prof(h, f):
    """Outward bulge of a wall at height h above the ground with earth to f: pressure all the way up the fill, fading
    out above it, the empty part above pulled in a little."""
    h = np.asarray(h, float)
    if f <= 0.0:
        return np.zeros_like(h)
    t = np.clip(h / f, 0.0, 1.0)
    base = BULGE * (0.5 + 0.5 * min(f, 1.95) / 1.95) * (0.6 + 0.4 * np.sin(np.pi * t))
    fade = sstep(f + 0.18, f - 0.02, h)
    pull = -0.005 * sstep(f, f + 0.3, h) * sstep(H, H - 0.25, h)
    return base * fade + pull


class Shape:
    """One variant's deformation of its cage: earth levels, bulges, waviness and damage fields, applied to points
    given in the undeformed cage."""

    def __init__(self, cells, fills, seed):
        self.cells, self.fills, self.seed = cells, list(fills), seed
        self.amp = [dict(f=1.0, b=1.0, l=1.0, r=1.0) for _ in cells]
        self.fields = []

    def deform(self, P):
        P = np.asarray(P, float)
        shp = P.shape
        P = P.reshape(-1, 3)
        out = P.copy()
        x, y, h = P[:, 0], P[:, 1], P[:, 2] - Z0
        nv = nvec(P, 2.2, self.seed)
        for ci, c in enumerate(self.cells):
            if len(self.cells) == 1:
                m = np.ones(len(P), bool)
            else:
                m = (x < 0) if ci == 0 else (x >= 0)
            u = np.clip((x - c.cx) / c.hx, -1.0, 1.0)
            v = np.clip(y / c.hy, -1.0, 1.0)
            A = prof(h, self.fills[ci])
            a = self.amp[ci]
            su = np.cos(u * np.pi / 2) ** 0.85
            sv = np.cos(v * np.pi / 2) ** 0.85
            dy = (-a["f"] * (1 - v) / 2 + a["b"] * (1 + v) / 2) * A * su
            al = 0.0 if c.shared_l else a["l"]
            ar = 0.0 if c.shared_r else a["r"]
            dx = (-al * (1 - u) / 2 + ar * (1 + u) / 2) * A * sv
            wv = np.maximum(su, sv) * 0.003
            out[m, 0] += dx[m] + wv[m] * nv[m, 0]
            out[m, 1] += dy[m] + wv[m] * nv[m, 1]
        for fn in self.fields:
            out += fn(P)
        return out.reshape(shp)


def f_dent(center, r, vec):
    c, v = np.array(center, float), np.array(vec, float)

    def f(P):
        d = np.linalg.norm(P - c, axis=1)
        w = np.where(d < r, 0.5 + 0.5 * np.cos(np.pi * np.minimum(d / r, 1.0)), 0.0)
        return w[:, None] * v
    return f


def f_slump(cell, h0, out, drop, side=-1.0):
    """The top of a cell's front (side -1) leaning out and drooping, most in the middle of the wall."""
    def f(P):
        x, y, h = P[:, 0], P[:, 1], P[:, 2] - Z0
        t = np.clip((h - h0) / (H - h0), 0.0, 1.0) ** 1.6
        wy = np.clip((side * y / cell.hy + 1) / 2, 0.0, 1.0) ** 1.5
        u = (x - cell.cx) / cell.hx
        wx = np.where(np.abs(u) <= 1.0, 0.3 + 0.7 * np.cos(np.clip(u, -1, 1) * np.pi / 2),
                      0.3 * np.clip((1.25 - np.abs(u)) / 0.25, 0.0, 1.0))
        o = np.zeros_like(P)
        o[:, 1] = side * out * t * wy * wx
        o[:, 2] = -drop * t * wy * wx
        return o
    return f


def f_lean(dx, dy):
    def f(P):
        t = np.clip((P[:, 2] - Z0) / H, 0.0, 1.0) ** 2
        o = np.zeros_like(P)
        o[:, 0], o[:, 1] = dx * t, dy * t
        return o
    return f


def rows_between(h0, h1, dz, breaks=()):
    edges = sorted(set([h0, h1] + [b for b in breaks if h0 + 0.02 < b < h1 - 0.02]))
    rows = [edges[0]]
    for a, b in zip(edges[:-1], edges[1:]):
        n = max(1, int(math.ceil((b - a) / dz - 1e-6)))
        rows += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.array(rows)


def band_of(hm):
    return 0 if hm < BANDS[1] else (1 if hm < BANDS[2] else 2)


def frame(shape, wall, s, h, off=0.0):
    """Deformed point, along-wall tangent, up tangent and outward normal at (s, h) of a wall (arrays allowed)."""
    s, h = np.asarray(s, float), np.asarray(h, float)
    e = 0.005
    Q = shape.deform(wall.p0(s, h, off))
    ts = shape.deform(wall.p0(s + e, h, off)) - shape.deform(wall.p0(s - e, h, off))
    th = shape.deform(wall.p0(s, h + e, off)) - shape.deform(wall.p0(s, h - e, off))
    ts /= np.linalg.norm(ts, axis=-1, keepdims=True)
    n = np.cross(ts, th)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    th = np.cross(n, ts)
    return Q, ts, th, n


# ---------------------------------------------------------------- the plan of one variant

class Plan:
    def __init__(self, double, stage, level):
        self.double, self.stage, self.level = double, stage, level
        self.cells, self.walls, self.rods = layout(double)
        f0 = FILL[stage]
        seed = (7 if double else 3) + 13 * level + int(f0 * 100)
        self.rnd = random.Random(seed)
        self.shape = Shape(self.cells, [f0] * len(self.cells), seed)
        self.tears, self.piles = [], []
        self.tops = [dict(heap=0.045 if stage == "Full" else 0.018, tilt=0.0, crater=None, lumps=0.012)
                     for _ in self.cells]
        self.shovel = stage == "Empty" and not double
        if level == 0 or stage == "Empty":
            return
        if not double:
            self._single(f0, level)
        else:
            self._double(f0, level)

    @property
    def fills(self):
        return self.shape.fills

    def taut(self, wall, band):
        if wall.cell is None:
            return False
        f = self.fills[wall.cell]
        return f >= BANDS[band] + 0.6 * (BANDS[band + 1] - BANDS[band])

    def tear(self, wall, s, h, kind, pour=None, pile=None, scl=1.0):
        w = self.walls[wall]
        self.tears.append(dict(wall=wall, s=s * w.L, h=h, kind=kind, pour=pour, pile=pile, scl=scl))

    def dent(self, wall, s, h, r, inward, down=0.0):
        w = self.walls[wall]
        p = w.p0(np.array(s * w.L), np.array(h))
        v = np.array([-w.n[0] * inward, -w.n[1] * inward, -down])
        self.shape.fields.append(f_dent(p, r, v))

    def _single(self, f0, level):
        sh = self.shape
        if level == 1:
            f = f0 - 0.03
            sh.fills[0] = f
            sh.amp[0]["f"] = 1.25
            ta = float(np.clip(0.3 * f + 0.12, 0.2, f - 0.16))
            tb = float(np.clip(0.62 * f + 0.05, 0.3, f - 0.12))
            self.tear(0, 0.29, ta, 0, pour=(0.06, 0.14, 0.006), pile=(0.22, 0.13, 0.08, 0.0))
            self.tear(0, 0.7, tb, 1, pour=None, pile=(0.15, 0.09, 0.05, 0.0))
            self.dent(0, 0.55, 1.55 if f0 > 1.9 else min(f + 0.4, 1.65), 0.2, 0.03)
            self.dent(1, 0.35, 1.15 if f0 > 1.2 else 0.95, 0.18, 0.022)
            self.dent(0, 0.22, H, 0.2, 0.012, 0.022)
            sh.fields.append(f_dent(self.walls[0].p0(np.array(0.29 * C * 2), np.array(ta)), 0.3,
                                    (0.0, -0.015, 0.0)))
            for t in self.tops:
                t["lumps"] = 0.016
        else:
            drop = {0.67: 0.2, 1.33: 0.42, 1.95: 0.45}[f0]
            fe = f0 - drop
            sh.fills[0] = fe
            sh.amp[0]["f"], sh.amp[0]["r"] = 1.6, 1.2
            scl = float(np.clip(fe / 0.9, 0.65, 1.0))
            hb = max(0.25 * scl + 0.01, min(0.38 * fe, fe - 0.26 * scl))
            self.tear(0, 0.42, hb, 2, pour=(0.11 * scl, 0.27 * scl + 0.04, 0.02 * scl + 0.006),
                      pile=(0.38, 0.24, 0.18 + 0.08 * scl, 0.05), scl=scl)
            tb = 0.62 * fe + 0.05
            if tb < fe - 0.1:
                self.tear(0, 0.78, tb, 1, pour=None, pile=(0.15, 0.09, 0.05, 0.0))
            self.tear(1, 0.3, max(0.18, 0.5 * fe), 0, pour=(0.05, 0.11, 0.005), pile=(0.16, 0.07, 0.06, -0.01))
            sh.fields.append(f_slump(self.cells[0], max(0.3, fe * 0.75), 0.05, 0.08 + (0.04 if f0 < 1.5 else 0.0)))
            sh.fields.append(f_lean(0.015, -0.01))
            self.dent(0, 0.7, min(fe + 0.45, 1.7), 0.25, 0.045)
            self.dent(1, 0.88, 1.85, 0.25, 0.04, 0.02)
            self.dent(3, 0.4, 1.3, 0.2, 0.025)
            self.dent(0, 0.22, H, 0.2, 0.012, 0.03)
            self.tops[0].update(tilt=0.1, crater=(-0.1, -0.35, 0.45, 0.07), lumps=0.02, heap=0.01)

    def _double(self, f0, level):
        sh = self.shape
        if level == 1:
            fl, fr = f0 - 0.03, f0 - 0.02
            sh.fills[0], sh.fills[1] = fl, fr
            sh.amp[0]["f"] = 1.25
            ta = float(np.clip(0.3 * fl + 0.12, 0.2, fl - 0.16))
            tb = float(np.clip(0.62 * fr + 0.05, 0.3, fr - 0.12))
            self.tear(0, 0.35, ta, 0, pour=(0.06, 0.14, 0.006), pile=(0.22, 0.13, 0.08, 0.0))
            self.tear(1, 0.62, tb, 1, pour=None, pile=(0.15, 0.09, 0.05, 0.0))
            self.dent(1, 0.45, 1.55 if f0 > 1.9 else min(fr + 0.4, 1.65), 0.2, 0.03)
            self.dent(3, 0.5, 1.2 if f0 > 1.2 else 1.0, 0.18, 0.02)
            self.dent(0, 0.3, H, 0.2, 0.012, 0.022)
            for t in self.tops:
                t["lumps"] = 0.016
        else:
            drop = {0.67: 0.2, 1.33: 0.42, 1.95: 0.45}[f0]
            fl, fr = f0 - drop, f0 - drop * 0.35
            sh.fills[0], sh.fills[1] = fl, fr
            sh.amp[0]["f"], sh.amp[1]["f"] = 1.6, 1.25
            scl = float(np.clip(fl / 0.9, 0.65, 1.0))
            hb = max(0.25 * scl + 0.01, min(0.38 * fl, fl - 0.26 * scl))
            self.tear(0, 0.5, hb, 2, pour=(0.11 * scl, 0.27 * scl + 0.04, 0.02 * scl + 0.006),
                      pile=(0.4, 0.24, 0.18 + 0.08 * scl, 0.05), scl=scl)
            tb = float(np.clip(0.62 * fr + 0.05, 0.3, fr - 0.12))
            self.tear(1, 0.62, tb, 1, pour=None, pile=(0.15, 0.09, 0.05, 0.0))
            self.tear(5, 0.7, max(0.18, 0.45 * fl), 0, pour=(0.05, 0.11, 0.005), pile=(0.16, 0.07, 0.06, -0.01))
            sh.fields.append(f_slump(self.cells[0], max(0.3, fl * 0.75), 0.05, 0.08 + (0.04 if f0 < 1.5 else 0.0)))
            sh.fields.append(f_slump(self.cells[1], max(0.3, fr * 0.8), 0.02, 0.03))
            sh.fields.append(f_lean(-0.012, -0.008))
            self.dent(0, 0.75, min(fl + 0.45, 1.7), 0.25, 0.045)
            self.dent(2, 0.2, 1.8, 0.22, 0.035, 0.015)
            self.dent(4, 0.6, 1.3, 0.2, 0.025)
            self.dent(1, 0.3, H, 0.2, 0.012, 0.025)
            self.tops[0].update(tilt=0.1, crater=(0.05, -0.35, 0.45, 0.07), lumps=0.02, heap=0.01)
            self.tops[1].update(tilt=0.04, lumps=0.018, heap=0.02)


# ---------------------------------------------------------------- building the pieces

class Q:
    """Mesh density for a piece."""

    def __init__(self, double):
        self.ns = 7 if double else 8  # outer wall columns
        self.dz = 0.175 if double else 0.14  # outer wall row height
        self.ns_in = 4 if double else 6
        self.dz_in = 0.3 if double else 0.22
        self.ns_rim = 5 if double else 8
        self.ntop = 6 if double else 8


def inside_fill(plan):
    """Points buried in a cell's earth (well inside its walls and below its earth level): faces of spill parts there
    are left out."""
    def hidden(V):
        out = np.zeros(len(V), bool)
        for ci, c in enumerate(plan.cells):
            f = plan.fills[ci]
            if f <= 0:
                continue
            m = (np.abs(V[:, 0] - c.cx) < c.hx - 0.015) & (np.abs(V[:, 1]) < c.hy - 0.015) & (V[:, 2] < Z0 + f - 0.02)
            out |= m
        return out
    return hidden


def add_walls(acc, plan, q):
    sh = plan.shape
    for wi, w in enumerate(plan.walls):
        if w.kind == "outer":
            f = plan.fills[w.cell]
            S = np.linspace(0.0, w.L, q.ns + 1)
            Hs = rows_between(0.0, H, q.dz, [BANDS[1], BANDS[2]] + ([f] if 0.05 < f < H - 0.1 else []))
            SS, HH = np.meshgrid(S, Hs)
            P = sh.deform(w.p0(SS, HH))
            pats = []
            for r in range(len(Hs) - 1):
                b = band_of((Hs[r] + Hs[r + 1]) / 2)
                pats.append(PATCH["WT%d%s" % (b, "B" if w.variant else "")] if plan.taut(w, b) else PATCH["WS%d" % b])
            grid_add(acc, P, w.u(SS), HH, pats, tag="outer")
            p = plan.tops[w.cell]
            dip = 0.65 * p["tilt"] + (p["crater"][3] if p["crater"] else 0.0) + 2.0 * p["lumps"]
            add_inner(acc, plan, q, w, -T, True, f, dip)
            add_rim(acc, plan, q, w, (0.0015, -T / 2, -T - 0.0015))
            add_top_wire(acc, plan, w, 0.0035, H - 0.004)
        else:
            dips = [0.65 * p["tilt"] + (p["crater"][3] if p["crater"] else 0.0) + 2.0 * p["lumps"] for p in plan.tops]
            add_inner(acc, plan, q, w, T / 2, False, plan.fills[1], dips[1])
            add_inner(acc, plan, q, w, -T / 2, True, plan.fills[0], dips[0])
            add_rim(acc, plan, q, w, (T / 2 + 0.0015, 0.0, -T / 2 - 0.0015))
            add_top_wire(acc, plan, w, 0.0, H + 0.0075)


def add_inner(acc, plan, q, w, off, flip, f, dip=0.0):
    h0 = max(0.0, f - 0.03 - dip) if f > 0 else 0.0
    h1 = H - 0.012
    if h1 - h0 < 0.01:
        return
    S = np.linspace(0.0, w.L, q.ns_in + 1)
    Hs = rows_between(h0, h1, q.dz_in, [BANDS[1], BANDS[2]])
    SS, HH = np.meshgrid(S, Hs)
    amp = 0.011 if f <= 0 else 0.007
    ph = plan.rnd.uniform(0, 6.28)
    lam = plan.rnd.uniform(0.24, 0.3)
    env = np.clip(np.sin(np.pi * (HH - h0) / (h1 - h0)), 0.0, 1.0) ** 0.7
    edge = np.clip(np.minimum(SS, w.L - SS) / 0.08, 0.0, 1.0)
    fold = amp * env * edge * (0.5 + 0.5 * np.sin(2 * np.pi * SS / lam + ph + 1.3 * np.sin(2.1 * HH)))
    sign = -1.0 if off < 0 else 1.0
    P = plan.shape.deform(w.p0(SS, HH, off + sign * fold))
    pats = [PATCH["WI%d" % band_of((Hs[r] + Hs[r + 1]) / 2)] for r in range(len(Hs) - 1)]
    U = np.asarray(SS) * WK / w.L
    grid_add(acc, P, (WK - U) if flip else U, HH, pats, flip=flip, tag="inner")


def add_rim(acc, plan, q, w, offs):
    S = np.linspace(0.0, w.L, q.ns_rim + 1)
    dh = (-0.014, 0.007, -0.014)
    W = np.linspace(0.0, RIMW, 3)
    rows = [plan.shape.deform(w.p0(S, np.full_like(S, H + dh[r]), offs[r])) for r in range(3)]
    P = np.stack(rows, 0)
    U = np.tile(w.u(S), (3, 1))
    Vd = np.tile(W[:, None], (1, len(S)))
    grid_add(acc, P, U, Vd, [PATCH["RIM"]] * 2, tag="rim")


def add_top_wire(acc, plan, w, off, hz):
    tpl = TPL["WIRE"]
    V = tpl.V
    s = (V[:, 0] - tpl.lo[0]) / (tpl.hi[0] - tpl.lo[0]) * w.L
    P = plan.shape.deform(w.p0(s, hz + V[:, 2], off - V[:, 1]))
    acc.add(P, tpl.F, tpl.UV, "wire")


def add_rods(acc, plan):
    rnd = plan.rnd
    for (x, y) in plan.rods:
        R = rotz(rnd.uniform(0, 360))
        V = TPL["ROD"].V @ R.T + np.array((x, y, Z0))
        acc.add(plan.shape.deform(V), TPL["ROD"].F, TPL["ROD"].UV, "rod")
        R = rotz(rnd.uniform(0, 360))
        V = TPL["PIN"].V @ R.T + np.array((x, y, Z0 + H + 0.008))
        acc.add(plan.shape.deform(V), TPL["PIN"].F, TPL["PIN"].UV, "pin")


def add_tops(acc, plan, q):
    for ci, c in enumerate(plan.cells):
        f = plan.fills[ci]
        if f <= 0:
            continue
        p = plan.tops[ci]
        n = q.ntop
        u = np.linspace(-1.0, 1.0, n + 1)
        UU, VV = np.meshgrid(u, u)
        X = c.cx + UU * (c.hx - T * 0.5)
        Y = VV * (c.hy - T * 0.5)
        r = np.sqrt(UU ** 2 + VV ** 2) / 1.25
        Z = f + p["heap"] * np.clip(1.0 - r * r, 0.0, 1.0) ** 1.3
        pts = np.stack([X, Y, np.zeros_like(X)], -1).reshape(-1, 3)
        Z = Z + p["lumps"] * nscal(pts, 7.0, plan.shape.seed + ci).reshape(Z.shape)
        Z = Z + 0.5 * p["lumps"] * nscal(pts, 17.0, plan.shape.seed + 5 + ci).reshape(Z.shape)
        Z = Z + p["tilt"] * (VV - 0.3) * 0.5
        if p["crater"] is not None:
            cu, cv, cr, cd = p["crater"]
            d = np.sqrt((UU - cu) ** 2 + (VV - cv) ** 2) / cr
            Z = Z - cd * np.clip(1.0 - d * d, 0.0, 1.0) ** 1.5
        Z = np.minimum(Z, ZMAX - Z0 - 0.004)
        P = plan.shape.deform(np.stack([X, Y, Z0 + Z], -1))
        DU, DV = UU * 0.46, VV * 0.46
        if ci == 1:
            DU, DV = VV * 0.46, -UU * 0.46
        grid_add(acc, P, DU, DV, [PATCH["TOP"]] * n, tag="top")


def add_tear(acc, plan, t, hidden):
    sh, w, rnd = plan.shape, plan.walls[t["wall"]], plan.rnd
    s, h, kind, scl = t["s"], t["h"], t["kind"], t["scl"]
    Q0, ts, th, n = frame(sh, w, s, h)
    tpl = TPL["BUL%d" % kind]
    m = tpl.meta
    R = np.column_stack([ts, -n, th]) @ np.diag([scl, 1.0, scl])
    Vb = add_tpl(acc, tpl, R, Q0 - n * 0.003, tag="bulge")
    bvh = BVHTree.FromPolygons(Vb.tolist(), tpl.F.tolist(), all_triangles=True)
    rx, rz = m["rx"] * scl, m["rz"] * scl
    # torn felt flaps round the hole, peeled outward
    count = 5 if kind == 2 else 3
    start = rnd.uniform(0, 1)
    for k in range(count):
        th_ = 2 * math.pi * (k + start + rnd.uniform(-0.15, 0.15)) / count
        rr = outline(th_, m["seed"])
        zf = 1.0 + m["drop"] if math.sin(th_) < 0 else 1.0
        o = Q0 + (ts * math.cos(th_) * rx + th * math.sin(th_) * rz * zf) * rr * 0.97
        rdir = unit(ts * math.cos(th_) * rz + th * math.sin(th_) * rx)
        upper = math.sin(th_) > 0.35
        if not upper:
            rdir = unit(rdir - th * 0.7)  # limp: hanging down and out
        tdir = np.cross(n, rdir)
        fl = TPL["FL%d" % rnd.randint(0, 2 if kind == 2 else 1)]
        sc = rnd.uniform(0.75, 1.0) if kind == 2 else rnd.uniform(0.75, 1.05)
        if upper:
            sc *= 0.6
        Rf = np.column_stack([tdir, -n, -rdir]) @ np.diag([sc, 1.0, sc * rnd.uniform(0.8, 1.2)])
        add_tpl(acc, fl, Rf, o + n * 0.003, tag="flap")
    # the mesh over the bulge: intact wires on small tears, broken stubs bent out on the big one
    Lg = w.L / NX
    if kind != 2:
        hz = round(h / PZ) * PZ
        if abs(hz - h) > rz * 0.8:
            hz = h
        ss = np.linspace(s - rx * 1.5, s + rx * 1.5, 11)
        sx = round(s / Lg) * Lg
        hh = np.linspace(h - rz * 1.5, h + rz * 1.5, 11)
        for S_, H_ in ((ss, np.full_like(ss, hz)), (np.full_like(hh, sx), hh)):
            base, _, _, nn = frame(sh, w, S_, H_)
            pts = []
            for b_, n_ in zip(base, nn):
                hit = bvh.ray_cast(Vector(b_ + n_ * 0.3), Vector(-n_), 0.4)
                pts.append(np.array(hit[0][:]) + n_ * 0.0035 if hit[0] is not None else b_ + n_ * 0.0035)
            V = sweep(TPL["WIRE"], pts, up=n)
            acc.add(V, TPL["WIRE"].F, TPL["WIRE"].UV, "wire")
    else:
        for k in range(4):
            th_ = 2 * math.pi * (k + 0.3) / 4 + rnd.uniform(-0.2, 0.2)
            o = Q0 + (ts * math.cos(th_) * rx + th * math.sin(th_) * rz) * 0.9
            rdir = unit(ts * math.cos(th_) + th * math.sin(th_))
            ln = rnd.uniform(0.06, 0.11) * (0.6 + 0.4 * scl)
            pts = [o - rdir * 0.03 + n * 0.002, o + n * 0.02, o + n * ln * 0.8 + rdir * ln * 0.3,
                   o + n * ln + rdir * ln * 0.25 - th * ln * 0.35]
            V = sweep(TPL["STUB"], pts, up=th)
            acc.add(V, TPL["STUB"].F, TPL["STUB"].UV, "wire")
    if t["pour"] is not None:
        add_pour(acc, plan, w, s, h - rz * 0.3, t["pour"], t["pile"])
    if t["pile"] is not None:
        rxp, ryp, hzp, out = t["pile"]
        add_pile(acc, plan, w, s, rxp, ryp, hzp, out, hidden)


def add_pour(acc, plan, w, s_c, h_top, pour, pile):
    """Earth run down from a tear: a tongue lying on the wall, widening and thickening down to the ground and out
    over it into the pile."""
    w0, w1, thick = pour
    ground = (pile[3] + pile[1] * 0.5) if pile else 0.1
    Lp = h_top + ground
    nr = max(4, int(math.ceil(Lp / 0.09)) + 1)
    v = np.linspace(0.0, Lp, nr)
    xr = np.linspace(-1.0, 1.0, 5)
    VV, XR = np.meshgrid(v, xr, indexing="ij")
    seed = plan.rnd.uniform(0, 10)
    width = (w0 + (w1 - w0) * (VV / Lp) ** 1.1) * (1.0 + 0.22 * np.sin(VV * 9.0 + seed) * XR
                                                    + 0.15 * np.sin(VV * 23.0 + 2.0 * seed))
    mean = 0.012 * np.sin(VV * 7.0 + seed)
    th_ = thick * (0.45 + 0.55 * VV / Lp) * np.clip(1.0 - XR ** 2, 0.0, 1.0) ** 0.6 + 0.0025
    S = s_c + mean + XR * width
    on_wall = VV <= h_top
    hh = np.where(on_wall, h_top - VV, 0.0)
    Qp, _, _, n = frame(plan.shape, w, S, hh)
    nh = n.copy()
    nh[..., 2] = 0.0
    nh /= np.linalg.norm(nh, axis=-1, keepdims=True)
    d = np.where(on_wall, 0.0, VV - h_top)
    P = np.where(on_wall[..., None], Qp + n * th_[..., None],
                 Qp + nh * d[..., None] + np.array((0.0, 0.0, 1.0)) * (th_[..., None] * 0.7))
    P[..., 2] = np.maximum(P[..., 2], Z0 + 0.002)
    grid_add(acc, P, XR * width, VV, [PATCH["POUR"]] * (nr - 1), flip=True, tag="pour")


def add_pile(acc, plan, w, s, rx, ry, hz, out, hidden):
    Q0, ts, _, n = frame(plan.shape, w, s, 0.0)
    nh = unit((n[0], n[1], 0.0))
    dh = unit((ts[0], ts[1], 0.0))
    tpl = TPL["PILE%d" % plan.rnd.randint(0, 1)]
    R = np.column_stack([dh * rx / 0.5, -nh * ry / 0.5, np.array((0.0, 0.0, hz / 0.25))]) @ rotz(plan.rnd.uniform(0, 360))
    c = Q0 + nh * out
    c[2] = Z0
    add_tpl(acc, tpl, R, c, hidden=hidden, tag="pile")


def add_shovel(acc):
    tip = np.array((0.27, -0.64, Z0 + 0.003))
    contact = np.array((0.34, -C - 0.0175 - 0.004, Z0 + 1.24))
    z = unit(contact - tip)
    x = unit(np.cross((0.0, 1.0, 0.0), z))
    y = np.cross(z, x)
    R = np.column_stack([x, y, z]) @ np.array(Matrix.Rotation(math.radians(14), 3, "Z"))
    for name in ("SHB", "SHH"):
        add_tpl(acc, TPL[name], R, tip, tag="shovel")


def finish_mesh(name, acc, material):
    V = np.concatenate(acc.V)
    F = np.concatenate(acc.F)
    UV = np.concatenate(acc.UV)
    V[:, 2] = np.clip(V[:, 2], Z0, ZMAX)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", UV.reshape(-1).astype(np.float32))
    me.shade_smooth()
    me.materials.append(material)
    return tk.link(bpy.data.objects.new(name, me))


def build_cage(double, stage, level, material):
    plan = Plan(double, stage, level)
    q = Q(double)
    acc = Acc()
    add_walls(acc, plan, q)
    add_rods(acc, plan)
    add_tops(acc, plan, q)
    hidden = inside_fill(plan)
    for t in plan.tears:
        add_tear(acc, plan, t, hidden)
    if plan.shovel:
        add_shovel(acc)
    name = "%s%s_DMG%d" % ("Double" if double else "", stage, level)
    obj = finish_mesh(name, acc, material)
    log("%s: tris %d %s" % (name, acc.tris(), acc.tags))
    return obj


def drape_rows(bvh, x0, y0, yaw, width, length, ncol, nrow, lift, rnd, seed):
    """A sheet laid over the mound from (x0, y0) running downhill along yaw (degrees from -y), keeping its length
    along the surface: (R, C, 3) points and the arc length of each row."""
    Rz = rotz(yaw)
    across = Rz @ np.array((1.0, 0.0, 0.0))
    along = Rz @ np.array((0.0, -1.0, 0.0))
    xs = np.linspace(-width / 2, width / 2, ncol)
    targets = np.linspace(0.0, length, nrow)
    P = np.zeros((nrow, ncol, 3))
    for ci, xc in enumerate(xs):
        base = np.array((x0, y0, 0.0)) + across * xc
        samples, arc, prev = [], 0.0, None
        for k in range(160):
            p2 = base + along * (k * 0.012)
            hit = bvh.ray_cast(Vector((p2[0], p2[1], 3.0)), Vector((0.0, 0.0, -1.0)), 6.0)
            z = max(hit[0][2] if hit[0] is not None else Z0, Z0)
            p3 = np.array((p2[0], p2[1], z))
            if prev is not None:
                arc += np.linalg.norm(p3 - prev)
            samples.append((arc, p3))
            prev = p3
        arcs = np.array([a for a, _ in samples])
        pts = np.array([p for _, p in samples])
        for ri, tl in enumerate(targets):
            k = min(np.searchsorted(arcs, tl), len(arcs) - 1)
            p = pts[k].copy()
            crumple = 0.02 * pnoise(p, seed, 6.0) + 0.012 * pnoise(p, seed + 2, 14.0)
            p[2] += lift + crumple
            P[ri, ci] = p
    return P, xs, targets


def ragged(base, seed, amp=0.11):
    """A torn top edge: s (meters along a wall) -> height."""
    def f(s):
        s = np.asarray(s, float)
        flat = s.ravel()
        a = np.array([noise.noise(Vector((x * 2.6 + seed * 3.1, seed * 1.7, 0.0))) for x in flat])
        b = np.array([noise.noise(Vector((x * 11.0 + seed, seed * 0.3, 1.0))) for x in flat])
        return np.clip(base + amp * a + 0.35 * amp * b, 0.18, 0.9).reshape(s.shape)
    return f


def build_mound(double, material):
    """What is left after a breach: the bottom of the cage, burst and bulging, its walls torn off ragged at 0.3 to
    0.7 m, the coils snapped or bent over, earth heaped in it to about 1 m and spilled over the low front wall into a
    pile, and the front wall's upper part folded back over the heap."""
    rnd = random.Random(91 if double else 19)
    plan = Plan(double, "Third", 0)
    sh = plan.shape
    for ci in range(len(plan.cells)):
        sh.fills[ci] = 0.55
        sh.amp[ci] = dict(f=2.2, b=1.6, l=1.8, r=1.8)
    sh.fields.append(f_lean(0.012 if double else -0.012, -0.015))
    q = Q(double)
    acc = Acc()
    tops = {}
    for wi, w in enumerate(plan.walls):
        front = w.n[1] < -0.5
        base = 0.62 if w.kind == "shared" else (rnd.uniform(0.27, 0.33) if front else rnd.uniform(0.62, 0.72))
        ht = ragged(base, wi + (10 if double else 0))
        tops[wi] = ht
        S = np.linspace(0.0, w.L, q.ns + 1)
        SS, TT = np.meshgrid(S, np.linspace(0.0, 1.0, 5))
        HH = TT * ht(SS)
        U = SS * WK / w.L
        if w.kind == "outer":
            grid_add(acc, sh.deform(w.p0(SS, HH)), w.u(SS), HH, [PATCH["WT0%s" % ("B" if w.variant else "")]] * 4,
                     tag="outer")
            grid_add(acc, sh.deform(w.p0(SS, HH, -T)), WK - U, HH, [PATCH["WI0"]] * 4, flip=True, tag="inner")
            offs = (0.0015, -T / 2, -T - 0.0015)
        else:
            grid_add(acc, sh.deform(w.p0(SS, HH, T / 2)), U, HH, [PATCH["WI0"]] * 4, tag="inner")
            grid_add(acc, sh.deform(w.p0(SS, HH, -T / 2)), WK - U, HH, [PATCH["WI0"]] * 4, flip=True, tag="inner")
            offs = (T / 2 + 0.0015, 0.0, -T / 2 - 0.0015)
        hs = ht(S)
        rows = [sh.deform(w.p0(S, hs + dh, o)) for dh, o in zip((-0.01, 0.004, -0.01), offs)]
        grid_add(acc, np.stack(rows, 0), np.tile(w.u(S), (3, 1)),
                 np.tile(np.linspace(0.0, RIMW, 3)[:, None], (1, len(S))), [PATCH["RIM"]] * 2, tag="rim")
        # torn felt standing up from the edge, curling out; wire ends sticking up out of it
        for k in range(2 if w.kind == "outer" else 1):
            s = rnd.uniform(0.15, 0.85) * w.L
            Q0, ts, th, n = frame(sh, w, s, float(ht(np.array([s]))[0]) - 0.012)
            sc = rnd.uniform(0.9, 1.3)
            R = np.column_stack([-ts, -n, -th]) @ np.diag([sc, 1.0, sc])
            add_tpl(acc, TPL["FL%d" % rnd.randint(0, 2)], R, Q0 + n * 0.002, tag="flap")
        for k in range(2):
            lg = w.L / NX
            s = round(rnd.uniform(0.1, 0.9) * w.L / lg) * lg
            Q0, ts, th, n = frame(sh, w, s, float(ht(np.array([s]))[0]) - 0.04)
            ln = rnd.uniform(0.06, 0.12)
            pts = [Q0 + n * 0.003, Q0 + th * (0.04 + ln * 0.5) + n * 0.006,
                   Q0 + th * (0.04 + ln) + n * (ln * 0.4) + ts * rnd.uniform(-0.03, 0.03)]
            acc.add(sweep(TPL["STUB"], pts, up=n), TPL["STUB"].F, TPL["STUB"].UV, "wire")
    # the corner coils: snapped off, or bent over outward
    for (x, y) in plan.rods:
        hcut = rnd.uniform(0.5, 0.85)
        out = unit(np.array((x if abs(x) > 0.1 else 0.0, y, 0.0)))
        pts = [np.array((x, y, Z0)), np.array((x, y, Z0 + hcut * 0.55)), np.array((x, y, Z0 + hcut))]
        if rnd.random() < 0.6:
            pts.append(pts[-1] + out * 0.04 + np.array((0.0, 0.0, 0.04)))
            pts.append(pts[-1] + out * 0.03 - np.array((0.0, 0.0, 0.05)))
        acc.add(sweep(TPL["ROD"], sh.deform(np.array(pts)), axis=2), TPL["ROD"].F, TPL["ROD"].UV, "rod")
    # the earth heaped in the cage (the mound part squared up to fit, rising from inside the walls to 1 m)
    tpl = TPL["MOUND"]
    Vs = []

    def se(t, p):
        return (np.abs(np.cos(t)) ** p + np.abs(np.sin(t)) ** p) ** (-1.0 / p)

    for ci, c in enumerate(plan.cells):
        V = tpl.V.copy()
        if ci == 1:
            V[:, :2] *= -1.0
        ang = np.arctan2(V[:, 1], V[:, 0])
        V[:, :2] *= (se(ang, 7.0) / se(ang, 3.2))[:, None]
        zt = np.clip(V[:, 2], 0.0, 1.0)
        rho = (1.0 - zt ** (1.0 / 0.9)) ** (1.0 / 2.6)  # inverts mound_height
        yn = np.clip(-V[:, 1] / 0.56, 0.0, 1.0)
        rim_h = 0.5 - 0.4 * yn ** 1.5  # held up by the walls; spilled out over the low front
        V[:, 1] *= 1.0 + 0.25 * yn * (1.0 - zt)
        cone = np.clip(1.0 - rho ** 1.5, 0.0, 1.0)
        hh = rim_h + cone * (1.0 - rim_h)
        lumps = np.array([noise.noise(Vector((x * 3.5 + ci * 5.0, y * 3.5, 0.7))) for x, y in V[:, :2]])
        lumps += 0.5 * np.array([noise.noise(Vector((x * 9.0, y * 9.0 + ci * 3.0, 2.1))) for x, y in V[:, :2]])
        hh = hh + 0.06 * lumps * np.clip(4.0 * cone * (1.0 - cone) + 0.3, 0.0, 1.0)
        V = np.stack([c.cx + V[:, 0] * (c.hx - 0.03) / 0.56, V[:, 1] * (c.hy - 0.03) / 0.56, Z0 + hh], -1)
        Vs.append(V)
    for i, V in enumerate(Vs):
        F, UV = tpl.F, tpl.UV
        if double:
            other = BVHTree.FromPolygons(Vs[1 - i].tolist(), tpl.F.tolist(), all_triangles=True)
            cen = V[F].mean(axis=1)
            keep = []
            for c in cen:
                hit = other.ray_cast(Vector((c[0], c[1], 3.0)), Vector((0.0, 0.0, -1.0)), 6.0)
                keep.append(not (hit[0] is not None and hit[0][2] > c[2] + 0.01))
            keep = np.array(keep)
            F, UV = F[keep], UV[keep]
        acc.add(V, F, UV, "mound")
    allV = np.concatenate(Vs)
    allF = np.concatenate([tpl.F + i * len(tpl.V) for i in range(len(Vs))])
    bvh = BVHTree.FromPolygons(allV.tolist(), allF.tolist(), all_triangles=True)

    def buried(V):
        out = np.zeros(len(V), bool)
        for i, p in enumerate(V):
            hit = bvh.ray_cast(Vector((p[0], p[1], 3.0)), Vector((0.0, 0.0, -1.0)), 6.0)
            out[i] = hit[0] is not None and hit[0][2] > p[2] + 0.006
        return out

    # earth spilled over the low front wall into a pile
    hidden = inside_fill(plan)
    fronts = [wi for wi, w in enumerate(plan.walls) if w.kind == "outer" and w.n[1] < -0.5]
    for wi in fronts:
        w = plan.walls[wi]
        s = w.L * rnd.uniform(0.4, 0.6)
        htop = float(tops[wi](np.array([s]))[0]) + 0.01
        pile = (0.36 if not double else 0.4, 0.2, 0.2, 0.0)
        add_pour(acc, plan, w, s, htop, (0.16, 0.28, 0.018), pile)
        add_pile(acc, plan, w, s, pile[0], pile[1], pile[2], pile[3], hidden)
    # the front wall's upper part folded back over the heap
    sheets = [(0.0, -0.4, 180.0 + 6.0, 0.8, 0.72)] if not double else [(-0.48, -0.4, 186.0, 0.8, 0.7),
                                                                         (0.5, -0.4, 172.0, 0.76, 0.6)]
    for k, (x0, y0, yaw, width, length) in enumerate(sheets):
        P, xs, arcs = drape_rows(bvh, x0, y0, yaw, width, length, 7, 9, 0.016, rnd, 31 + k)
        U = np.tile((xs - xs[0])[None, :], (len(arcs), 1)) * WK / width
        Vd = np.tile((0.45 + arcs)[:, None], (1, len(xs)))
        pats = [PATCH["WS%d" % band_of((Vd[r, 0] + Vd[r + 1, 0]) / 2)] for r in range(len(arcs) - 1)]
        sub = Acc()
        grid_add(sub, P, U, Vd, pats, flip=True, tag="sheet")
        V, F, UV = sub.V[0], sub.F[0], sub.UV[0]
        nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        if (nrm[:, 2] < 0).mean() > 0.5:
            F, UV = F[:, ::-1], UV[:, ::-1]
        hm = buried(V)
        keep = ~hm[F].all(axis=1)
        acc.add(V, F[keep], UV[keep], "sheet")
        far = P[-1] + np.array((0.0, 0.0, 0.004))
        acc.add(sweep(TPL["WIRE"], far, up=(0.0, 0.0, 1.0)), TPL["WIRE"].F, TPL["WIRE"].UV, "wire")
    hit = bvh.ray_cast(Vector((0.22, 0.18, 3.0)), Vector((0.0, 0.0, -1.0)), 6.0)
    zp = hit[0][2] if hit[0] is not None else Z0
    Rp = np.array(Matrix.Rotation(math.radians(80), 3, "Y")) @ rotz(30)
    add_tpl(acc, TPL["PIN"], Rp, np.array((0.22, 0.18, zp + 0.004)), tag="pin")
    name = "%sMound_DMG0" % ("Double" if double else "")
    obj = finish_mesh(name, acc, material)
    log("%s extents: %s" % (name, "; ".join("%s x %.2f..%.2f y %.2f..%.2f" % (t, lo[0], hi[0], lo[1], hi[1])
                                            for t, (lo, hi) in acc.ext.items())))
    log("%s: tris %d %s" % (name, acc.tris(), acc.tags))
    return obj


# ---------------------------------------------------------------- reports, export

def stats(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0), len(me.polygons)


def fx_point(double, stage):
    return (0.0, -(C + BULGE * 0.9), Z0 + FILL[stage] / 2.0)


def export_piece(fname, meshes, fx):
    """Exports meshes renamed DMG0.. (and an FX empty at the root) to one FBX, then restores the names."""
    saved, objs = [], []
    for i, m in enumerate(meshes):
        saved.append((m, m.name, m.data.name))
        m.name = "DMG%d" % i
        m.data.name = "DMG%d" % i
        objs.append(m)
    empty = None
    if fx is not None:
        empty = tk.link(bpy.data.objects.new("FX", None))
        empty.empty_display_size = 0.1
        empty.location = fx
        objs.append(empty)
    tk.export_fbx(objs, os.path.join(ASSETS, fname))
    if empty is not None:
        bpy.data.objects.remove(empty)
    for m, n, dn in saved:
        m.name = n
        m.data.name = dn


# ---------------------------------------------------------------- previews

ALL = []


def image_mean(path):
    img = bpy.data.images.load(path, check_existing=False)
    ch = img.channels or 4
    a = np.empty(img.size[0] * img.size[1] * ch, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return float(a.reshape(-1, ch)[:, :3].mean()) if len(a) else 0.0


def stage():
    tk.preview_stage()
    floor = bpy.data.objects["Floor"]
    floor.data.transform(Matrix.Translation((0.5, 0.5, 0.0)) @ Matrix.Scale(4.0, 4))
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (0.0, 0.0, 0.0)


def figure_at(x, y):
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)


def safe_render(cam, path, res, samples, transparent=False):
    tk.render(cam, path, res=res, samples=samples, transparent=transparent)
    if not transparent and (not os.path.exists(path) or image_mean(path) < 0.01):
        log("render came out black on the GPU; again on the CPU")
        bpy.context.scene.cycles.device = "CPU"
        tk.render(cam, path, res=res, samples=samples, transparent=transparent)


def lineup(entries, cam, path, res=(1800, 900), samples=80):
    """entries: (object, (x, y), z rotation in degrees). Renders copies of them, everything else in ALL hidden."""
    for o in ALL:
        o.hide_render = True
    temps = []
    for obj, (x, y), rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = (x, y, 0.0)
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    safe_render(cam, path, res, samples)
    for t in temps:
        bpy.data.objects.remove(t)
    log("render", os.path.basename(path))


# ================================================================ main

tk.reset_scene()
MATS = build_kit()
layout_kit()
bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
kit, PATHS = bake_kit()
TPL, PATCH = extract(kit)
for _n in ("WT0", "WIRE", "MOUND"):
    _t = TPL[_n]
    _uva = 0.5 * np.abs(np.cross(_t.UV[:, 1] - _t.UV[:, 0], _t.UV[:, 2] - _t.UV[:, 0])).sum()
    _a3 = 0.5 * np.linalg.norm(np.cross(_t.V[_t.F[:, 1]] - _t.V[_t.F[:, 0]], _t.V[_t.F[:, 2]] - _t.V[_t.F[:, 0]]),
                               axis=1).sum()
    log("texel density %s: %.0f px/m" % (_n, math.sqrt(_uva / _a3) * TEX))
bpy.data.objects.remove(kit)


def probe():
    """Logs the baked albedo (sRGB 0-255) up the middle of the first taut and slack wall bands, and on the earth top."""
    img = bpy.data.images.load(PATHS["albedo"], check_existing=False)
    w, h = img.size
    px = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, img.channels)
    bpy.data.images.remove(img)

    def at(p, u, v):
        uv = p.uv(np.array([u]), np.array([v]))[0]
        x, y = int(uv[0] * w), int(uv[1] * h)
        c = px[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3, :3].reshape(-1, 3).mean(axis=0)
        return tuple(int(round(255 * cc)) for cc in c)  # byte images come back as stored (sRGB)

    for name in ("WT0", "WS0", "WT2"):
        p = PATCH[name]
        log("albedo %s:" % name, " ".join("h%.2f=%s" % (v, at(p, 0.43, v)) for v in
                                          np.linspace(p.dom[2] + 0.01, p.dom[3] - 0.01, 6)))
    log("albedo TOP:", at(PATCH["TOP"], 0.1, 0.1), at(PATCH["TOP"], -0.2, 0.25))


probe()
MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
log("baked", PATHS)

BUILT = {}
for dbl in (False, True):
    BUILT[(dbl, "Empty")] = [build_cage(dbl, "Empty", 0, MATERIAL)]
    for stg in ("Third", "TwoThirds", "Full"):
        BUILT[(dbl, stg)] = [build_cage(dbl, stg, lvl, MATERIAL) for lvl in range(3)]
    BUILT[(dbl, "Mound")] = [build_mound(dbl, MATERIAL)]
for v in BUILT.values():
    ALL.extend(v)

REPORT = []
for dbl in (False, True):
    for stg in ("Empty", "Third", "TwoThirds", "Full", "Mound"):
        fname = "Hesco%s%s.fbx" % ("Double" if dbl else "", stg)
        meshes = BUILT[(dbl, stg)]
        fx = fx_point(dbl, stg) if len(meshes) == 3 else None
        export_piece(fname, meshes, fx)
        for i, m in enumerate(meshes):
            lo, hi, tris = stats(m)
            REPORT.append("%s: DMG%d tris %d bounds %s..%s" % (fname, i, tris, lo.round(3), hi.round(3)))
        if fx:
            REPORT.append("%s: FX at %s" % (fname, tuple(round(c, 3) for c in fx)))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
stage()
S = {k: v for k, v in BUILT.items()}
figure_at(3.4, 0.5)
lineup([(S[(False, "Empty")][0], (-2.4, 0.0), 0), (S[(False, "Third")][0], (-0.8, 0.0), 0),
        (S[(False, "TwoThirds")][0], (0.8, 0.0), 0), (S[(False, "Full")][0], (2.4, 0.0), 0)],
       tk.camera("Fill", (1.6, -7.6, 4.2), (0.0, 0.0, 0.3), lens=36), os.path.join(PREVIEWS, "hesco_fill_stages.png"))
figure_at(4.9, 0.5)
lineup([(S[(True, "Empty")][0], (-3.45, 0.0), 0), (S[(True, "Third")][0], (-1.15, 0.0), 0),
        (S[(True, "TwoThirds")][0], (1.15, 0.0), 0), (S[(True, "Full")][0], (3.45, 0.0), 0)],
       tk.camera("FillD", (2.0, -10.5, 5.4), (0.0, 0.0, 0.3), lens=36),
       os.path.join(PREVIEWS, "hesco_double_fill_stages.png"))
figure_at(2.6, 0.6)
for stg in ("Full", "TwoThirds", "Third"):
    m = S[(False, stg)]
    lineup([(m[0], (-1.45, 0.0), 0), (m[1], (0.0, 0.0), 0), (m[2], (1.45, 0.0), 0)],
           tk.camera("Dmg" + stg, (1.2, -5.6, 2.6), (0.0, 0.0, 0.35), lens=36),
           os.path.join(PREVIEWS, "hesco_%s_damage.png" % stg.lower()), res=(1600, 900))
figure_at(4.0, 0.6)
for stg in ("Full", "Third"):
    m = S[(True, stg)]
    lineup([(m[0], (-2.35, 0.0), 0), (m[1], (0.0, 0.0), 0), (m[2], (2.35, 0.0), 0)],
           tk.camera("DmgD" + stg, (1.6, -8.4, 3.4), (0.0, 0.0, 0.35), lens=36),
           os.path.join(PREVIEWS, "hesco_double_%s_damage.png" % stg.lower()), res=(1800, 900))
figure_at(2.4, 0.8)
lineup([(S[(False, "Mound")][0], (-1.3, 0.0), 0), (S[(True, "Mound")][0], (0.8, 0.0), 0)],
       tk.camera("Mounds", (1.0, -4.6, 2.4), (0.0, 0.0, -0.1), lens=36), os.path.join(PREVIEWS, "hesco_mounds.png"),
       res=(1600, 900))
F0, D0 = S[(False, "Full")][0], S[(True, "Full")][0]
run = [(F0, (0.0, 0.0), 0), (F0, (1.0, 0.0), 90), (F0, (2.0, 0.0), 180), (D0, (3.5, 0.0), 0)]
figure_at(-1.0, -0.6)
lineup(run, tk.camera("Run", (0.2, -6.2, 2.6), (1.8, 0.0, 0.45), lens=32), os.path.join(PREVIEWS, "hesco_run.png"))
lineup(run, tk.camera("RunTop", (1.8, -2.6, 4.4), (1.8, 0.0, 1.2), lens=26), os.path.join(PREVIEWS, "hesco_run_top.png"))
lineup(run, tk.camera("RunBack", (3.6, 6.0, 2.6), (1.8, 0.0, 0.45), lens=32),
       os.path.join(PREVIEWS, "hesco_run_back.png"))
figure_at(1.6, 0.2)
lineup([(F0, (0.0, 0.0), 0)], tk.camera("Close", (0.75, -1.9, 0.9), (0.0, -0.4, 0.35), lens=40),
       os.path.join(PREVIEWS, "hesco_close.png"), res=(1200, 1000))
lineup([(S[(False, "Full")][2], (0.0, 0.0), 0)], tk.camera("Close2", (0.8, -2.2, 1.0), (0.0, -0.3, 0.2), lens=40),
       os.path.join(PREVIEWS, "hesco_full_dmg2_close.png"), res=(1200, 1000))
lineup([(S[(False, "Empty")][0], (-0.7, 0.0), 0), (S[(False, "Third")][0], (0.7, 0.0), 0)],
       tk.camera("Top", (0.3, -2.4, 3.6), (0.0, 0.0, 0.4), lens=34), os.path.join(PREVIEWS, "hesco_top.png"),
       res=(1400, 1000))



def unity_light():
    """The light the vanilla reference renders were made with in Unity (as in sandbags.py): a warm sun from 40/-30
    degrees, trilight ambient, a dark floor. Returns the sun and the floor."""
    world = bpy.context.scene.world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.03, 0.028, 0.025, 1.0)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.17, 0.21, 0.32, 1.0)
    cr.elements.new(0.5).color = (0.1, 0.1, 0.1, 1.0)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs[2], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    sun = tk.link(bpy.data.objects.new("CmpSun", bpy.data.lights.new("CmpSun", "SUN")))
    sun.data.color = (1.0, 0.93, 0.84)
    sun.data.energy = 9.0
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = Vector((-0.38, 0.66, -0.64)).to_track_quat("-Z", "Y").to_euler()
    mat, g = tk.new_material("CmpFloor")
    tk.finish(mat, g, (0.073, 0.069, 0.06), 0.0, 0.9)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20.0)
    bmesh.ops.translate(bm, vec=(0, 0, Z0), verts=bm.verts)
    return sun, tk.mesh_object("CmpFloor", bm, mat)


def compare_vanilla(obj, ref_path, out_path):
    """The Full barrier under the vanilla reference's light and camera, beside that reference (vanilla sandbags)."""
    scene = bpy.context.scene
    for o in ALL:
        o.hide_render = o is not obj
    hidden = [o for o in scene.objects if o.type == "LIGHT" or o.name in ("Floor", "ScaleFigure", "ScaleHead")]
    for o in hidden:
        o.hide_render = True
    old_world = scene.world
    scene.world = bpy.data.worlds.new("Cmp")
    sun, fl = unity_light()
    cam = tk.camera("CmpCam", (1.8, -4.6, 2.2), (0.0, 0.4, 0.6), lens=50)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle_y = math.radians(34.0)
    ours = os.path.join(PREVIEWS, "_cmp_ours.png")
    safe_render(cam, ours, (1300, 1000), 96)
    img = bpy.data.images.load(ours)
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    fl.hide_render = True
    mpath = os.path.join(PREVIEWS, "_cmp_mask.png")
    tk.render(cam, mpath, res=(1300, 1000), samples=4, transparent=True)
    img = bpy.data.images.load(mpath)
    m = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(m)
    m = m.reshape(img.size[1], img.size[0], 4)[..., 3] > 0.5
    bpy.data.images.remove(img)
    os.remove(mpath)
    px = a[..., :3][m]
    log("compare: ours mean sRGB", (px.mean(axis=0) * 255).round(1), "p25/p75 luma",
        (np.percentile(px @ np.array([0.2126, 0.7152, 0.0722]), [25, 75]) * 255).round(1),
        "| vanilla sandbags in the reference: mean ~ (114, 97, 82)")
    img = bpy.data.images.load(ref_path)
    r = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(r)
    r = r.reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    both = np.concatenate([r[:a.shape[0], :1300, :3], a[..., :3]], axis=1)
    h, w = both.shape[:2]
    out = bpy.data.images.new("cmp", w, h, alpha=True)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = both
    out.pixels.foreach_set(rgba.ravel())
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    os.remove(ours)
    bpy.data.objects.remove(sun)
    bpy.data.objects.remove(fl)
    scene.world = old_world
    for o in hidden:
        o.hide_render = False
    log("render", os.path.basename(out_path))


REF = os.path.join(os.path.dirname(PREVIEWS), "ref-sandbag_straight_01prefab.png")
if os.path.exists(REF):
    compare_vanilla(F0, REF, os.path.join(PREVIEWS, "hesco_vs_vanilla.png"))

# ---------------------------------------------------------------- icon
for o in ALL:
    o.hide_render = o is not F0
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not F0}
tk.icon(tk.camera("Icon", (2.15, -3.3, 2.35), (0.0, 0.0, 0.47), lens=62), ICON, hide=hide, target=(0.0, 0.0, 0.5))
log("icon", ICON)

# ---------------------------------------------------------------- check the files as the importer sees them
bpy.ops.wm.read_factory_settings(use_empty=True)
for fname in sorted(os.listdir(ASSETS)):
    if not fname.endswith(".fbx"):
        continue
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=os.path.join(ASSETS, fname))
    parts = []
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type == "MESH":
            co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            parts.append("%s mesh tris %d mat %s z %.3f..%.3f x %.3f..%.3f y %.3f..%.3f parent %s" % (
                o.name, tris, [m.name for m in o.data.materials], co[:, 2].min(), co[:, 2].max(), co[:, 0].min(),
                co[:, 0].max(), co[:, 1].min(), co[:, 1].max(), o.parent.name if o.parent else None))
        else:
            parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation),
                                                    o.parent.name if o.parent else None))
    log("reimport", fname, "|", " || ".join(parts))
log("done")
