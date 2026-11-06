"""Nature Expanded's kit for abandoned campsites (CampTent, CampLeanTo, CampChairs, CampFishing; see SPEC_camps.md), on
top of featurekit.py and logkit.py.

A camp is a low scatter of man-made junk on a 5 x 5 m footprint, years old: faded torn fabric, rusted metal, greyed
wood, cold stones, leaf litter and grass pushing through. Conventions as featurekit (meters, Z up, master cell at the
origin, ground at z = -0.5 = G); the game draws a feature with back faces culled, so cloth is built as two sheets a few
millimetres apart (`cloth`, `ribbon`) and everything else as closed shells.

What is here:
- materials, each made for the baker (object coordinates, vertex attribute `t`): `fabric_mat`, `rust_mat`, `enamel_mat`,
  `plastic_mat`, `alu_mat`, `webbing_mat`, `glass_mat`, `rope_mat`, `bone_mat`, wood (`Wood.get`: bark, silver, char, cut
  grain run along any direction because the coordinates are rotated), `stone_mat` (sooted granite), `dirt_mat`, ground
  litter and grass.
- shapes: `cloth` (heightfield or any parametric sheet, double sided, with torn holes), `ribbon` (webbing strips),
  `solid_tube` (a closed log with end grain; returns its body for the colliders), `lathe` (cans, bottles, pots, buckets),
  `shell_box` (cooler), `tuft`, `litter_ring`, `wire` (rods and rope), `ring`.
- `Place`: a rigid transform (yaw, tilt, offset) for building an object in its own frame and standing it in the camp.
- `preview`: the preview renders for a camp.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
UP = Vector((0.0, 0.0, 1.0))
PREV = "."

# Faster debug bakes: CK_BAKE_SAMPLES caps the sample count of every bake pass (the emission passes are deterministic)
_orig_bake = tk._bake


def _capped_bake(obj, kind, img, samples, **kw):
    cap = int(os.environ.get("CK_BAKE_SAMPLES", "0"))
    return _orig_bake(obj, kind, img, min(samples, cap) if cap else samples, **kw)


tk._bake = _capped_bake


def dark(c, f=0.6):
    return tuple(x * f for x in c)


def lift(c, f=1.5):
    return tuple(min(1.0, x * f) for x in c)


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smoothstep(a, b, x):
    t = clamp((x - a) / (b - a)) if a != b else (1.0 if x >= a else 0.0)
    return t * t * (3.0 - 2.0 * t)


# ================================================================ materials

def new_mat(name, direction=None):
    """A material and its graph; g.world is the object-space coordinate. With `direction` the coordinates every helper
    asks for (g.coords()) are rotated so that direction becomes +x: noise stretched along x then runs along it."""
    mat, g = tk.new_material(name)
    world = tk.Graph.coords(g)
    g.world = world
    if direction is None:
        g.coords = lambda: world
        return mat, g
    d = Vector(direction).normalized()
    vertical = abs(d.z) > 0.95
    q = d.to_track_quat("X", "Y" if vertical else "Z")
    e = q.inverted().to_euler("XYZ")
    mp = g.node("ShaderNodeMapping")
    mp.vector_type = "POINT"
    g.links.new(world, mp.inputs["Vector"])
    mp.inputs["Rotation"].default_value = (e.x, e.y, e.z)
    out = mp.outputs[0]
    g.coords = lambda: out
    return mat, g


def _z(g):
    return g.separate(g.world)[2]


def _ground_dirt(g, col, rough, amount=1.0, height=0.16, color=(0.045, 0.036, 0.027)):
    """Mud and soil splashed up the low parts, in patches."""
    low = g.math("MULTIPLY", g.ramp(_z(g), G + height, G - 0.01), g.ramp(g.noise(8.0, detail=4.0), 0.22, 0.65))
    low = g.math("MULTIPLY", low, 0.9 * amount)
    speck = g.ramp(g.noise(200.0, detail=2.0), 0.55, 0.8)
    low = g.math("MAXIMUM", low, g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(_z(g), G + height * 2.0, G), speck), 0.6 * amount))
    return g.mix(low, col, color), g.mixf(low, rough, 0.95), low


def _specks(g, col, scale=420.0, amount=0.5, color=(0.02, 0.018, 0.015), lo=0.6, hi=0.8):
    d, r = kf._cells(g, scale)
    sp = g.math("MULTIPLY", g.ramp(d, 0.35, 0.1), g.ramp(r, lo, hi))
    return g.mix(g.math("MULTIPLY", sp, amount), col, color), sp


def fabric_surface(g, base, base2, fade=0.8, mildew=0.5, stains=0.6, dirt=1.0, seams=0.0, seam_pitch=0.62, slits=0.7,
                   creases=1.0, bleach=None, sheen=0.0):
    """Faded, filthy, rotting cloth as node signals (color, height, roughness): a steady tone with slow drift, thread
    grain, wrinkles that hold dust (in the bump, barely in the colour), sun bleaching and dust on the up-facing parts,
    soft water stains, mildew specks, mud near the ground, sewn seams, a few short splits that read as tears."""
    nz = ks._normal_z(g)
    tone = g.noise(2.2, detail=4.0, roughness=0.5)
    col = g.mix(g.ramp(tone, 0.25, 0.75), base, base2)
    mott = g.noise(15.0, detail=5.0, roughness=0.6)
    col = g.mix(g.math("MULTIPLY", g.ramp(mott, 0.3, 0.8), 0.22), col, dark(base, 0.7))
    # thread grain, two directions, fine
    t2 = g.noise(1.0, detail=2.0, vector=ks._stretched(g, (900.0, 110.0, 900.0)))
    t3 = g.noise(1.0, detail=2.0, vector=ks._stretched(g, (110.0, 900.0, 900.0)))
    t4 = g.noise(1.0, detail=2.0, vector=ks._stretched(g, (900.0, 900.0, 110.0)))
    thread = g.math("MULTIPLY", g.math("ADD", g.math("ADD", t2, t3), t4), 0.34)
    col = g.mix(g.math("MULTIPLY", g.ramp(thread, 0.35, 0.7), 0.2), col, dark(base, 0.72))
    fine = g.noise(300.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.55, 0.9), 0.14), col, lift(base2, 1.35))
    # wrinkles: dust settles in them, mostly shown in the bump
    cr = kf._ridged(g, g.noise(9.0, detail=3.0, distortion=0.8))
    crease = g.ramp(cr, 0.7, 0.95)
    cr2 = kf._ridged(g, g.noise(26.0, detail=3.0, distortion=1.2))
    fine_cr = g.ramp(cr2, 0.72, 0.96)
    col = g.mix(g.math("MULTIPLY", crease, 0.16 * creases), col, (0.15, 0.13, 0.1))
    col = g.mix(g.math("MULTIPLY", fine_cr, 0.12 * creases), col, dark(base, 0.6))
    # sun bleaching and dust on the up-facing parts
    if bleach is None:
        bleach = lift((base2[0] * 0.8 + 0.1, base2[1] * 0.8 + 0.1, base2[2] * 0.8 + 0.08), 1.0)
    fade_m = g.math("MULTIPLY", g.ramp(nz, 0.15, 0.9), g.ramp(g.noise(3.0, detail=3.0), 0.2, 0.8))
    fade_m = g.math("MULTIPLY", fade_m, fade)
    col = g.mix(fade_m, col, bleach)
    dust = g.math("MULTIPLY", g.ramp(nz, 0.4, 0.95), g.ramp(g.noise(7.0, detail=4.0), 0.4, 0.7))
    col = g.mix(g.math("MULTIPLY", dust, 0.18), col, (0.2, 0.18, 0.15))
    # water stains: soft darker blotches with a faint tide edge
    sr = g.noise(2.4, detail=3.0, distortion=0.8)
    edge = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", sr, 0.58)), 0.09, 0.0)
    fill = g.ramp(sr, 0.58, 0.75)
    stain = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", edge, 0.25), g.math("MULTIPLY", fill, 0.3)), stains)
    col = g.mix(g.math("MULTIPLY", stain, g.ramp(g.noise(5.0, detail=3.0), 0.2, 0.6)), col, (0.09, 0.065, 0.04))
    # mildew: dark green-black freckles and a few lichen-like clouds, mostly where the sun doesn't bleach
    mn1 = g.math("ADD", g.noise(6.0, detail=6.0, roughness=0.62, distortion=0.5), g.math("MULTIPLY", g.noise(48.0, detail=3.0), 0.28))
    mm = g.math("MULTIPLY", g.ramp(mn1, 0.66 - 0.1 * mildew, 0.8 - 0.1 * mildew), mildew)
    mm = g.math("MULTIPLY", mm, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", fade_m, 0.5)))
    col = g.mix(g.math("MULTIPLY", mm, 0.55), col, (0.03, 0.042, 0.022))
    msp, _ = _specks(g, col, 190.0, 0.7 * mildew, (0.014, 0.022, 0.012), 0.45, 0.7)
    col = msp
    rough = g.mixf(mm, 0.9, 0.96)
    if sheen:
        rough = g.mixf(g.ramp(mott, 0.5, 0.8), rough, 0.9 - sheen)
    if seams > 0.0:
        x = g.separate(g.world)[0]
        pp = g.math("PINGPONG", x, seam_pitch * 0.5)
        line = g.ramp(pp, 0.010, 0.0)
        hem = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", pp, 0.013)), 0.003, 0.0)
        col = g.mix(g.math("MULTIPLY", line, 0.5 * seams), col, dark(base, 0.5))
        col = g.mix(g.math("MULTIPLY", hem, 0.25 * seams), col, lift(base, 1.2))
    # mud splashed up from the ground
    col, rough, low = _ground_dirt(g, col, rough, amount=dirt, height=0.2)
    # a few short splits, dark and cut deep, only in some places
    sp = g.ramp(kf._ridged(g, g.noise(6.0, detail=3.0, distortion=2.0, vector=kf._warped(g, 20.0, 0.012))), 0.985, 0.999)
    sp = g.math("MULTIPLY", sp, g.ramp(g.noise(1.3, detail=2.0), 0.58, 0.7))
    sp = g.math("MULTIPLY", sp, slits)
    col = g.mix(sp, col, (0.006, 0.005, 0.004))
    height = g.math("MULTIPLY", thread, 0.3)
    height = g.math("ADD", height, g.math("MULTIPLY", crease, 0.6))
    height = g.math("ADD", height, g.math("MULTIPLY", fine_cr, 0.35))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", sp, 0.9))
    height = g.math("ADD", height, g.math("MULTIPLY", mm, 0.1))
    return col, height, rough


def fabric_mat(name, base, base2, **kw):
    mat, g = new_mat(name)
    col, height, rough = fabric_surface(g, base, base2, **kw)
    col = tk.grade(g, col, sat=0.92, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0035))


def rust_surface(g, metal=(0.3, 0.3, 0.29), rust=0.8, paint=None, paint_cover=0.5, scale=1.0, dent=0.0, soot=0.0, label=None,
                 label_band=(0.2, 0.8)):
    """Rusted sheet steel: scratched grey metal (or `paint` that survives in patches), orange-brown rust in blooms
    with vertical rain streaks and more of it low down, dark scabs, flaking pits, a gritty bump. `label` = (color,
    color2) draws the rags of a paper label on the band `label_band` of the vertex attribute t."""
    z = _z(g)
    nz = ks._normal_z(g)
    tone = g.noise(7.0 * scale, detail=4.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), dark(metal, 0.78), metal)
    scr = kf._ridged(g, g.noise(1.0, detail=2.0, vector=ks._stretched(g, (500.0, 45.0, 500.0))))
    col = g.mix(g.math("MULTIPLY", g.ramp(scr, 0.82, 0.97), 0.3), col, lift(metal, 1.6))
    height = g.math("MULTIPLY", scr, 0.08)
    rough = g.mixf(g.ramp(tone, 0.3, 0.7), 0.5, 0.65)
    metalness = 0.75
    if paint is not None:
        pm = g.math("ADD", g.noise(6.5 * scale, detail=5.0, distortion=0.4), g.math("MULTIPLY", g.noise(70.0 * scale, detail=3.0), 0.25))
        pcov = g.ramp(pm, 0.95 - paint_cover * 0.75, 1.0 - paint_cover * 0.75)
        pcol = g.mix(g.ramp(g.noise(12.0, detail=3.0), 0.3, 0.7), paint, dark(paint, 0.72))
        pcol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(220.0, detail=2.0), 0.6, 0.85), 0.3), pcol, lift(paint, 1.4))
        col = g.mix(pcov, col, pcol)
        height = g.math("ADD", height, g.math("MULTIPLY", pcov, 0.3))
        rough = g.mixf(pcov, rough, 0.78)
        metalness = g.mixf(pcov, 0.75, 0.0)
        paint_mask = pcov
    else:
        paint_mask = None
    n1 = g.noise(5.0 * scale, detail=6.0, roughness=0.62, distortion=0.4)
    n2 = g.noise(44.0 * scale, detail=4.0)
    streak = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (34.0 * scale, 34.0 * scale, 2.6 * scale)))
    m = g.math("ADD", g.math("MULTIPLY", n1, 0.62), g.math("ADD", g.math("MULTIPLY", n2, 0.2), g.math("MULTIPLY", streak, 0.3)))
    m = g.math("ADD", m, g.math("MULTIPLY", g.ramp(z, G + 0.3, G), 0.16))
    m = g.math("ADD", m, g.math("MULTIPLY", g.ramp(nz, 0.2, 0.9), 0.08))
    lo = 0.7 - 0.28 * rust
    rustm = g.ramp(m, lo, lo + 0.08)
    if paint_mask is not None:
        rustm = g.math("MULTIPLY", rustm, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", paint_mask, 0.9)))
    deep = g.ramp(m, lo + 0.1, lo + 0.22)
    rcol = g.mix(g.ramp(g.noise(90.0 * scale, detail=3.0), 0.3, 0.7), (0.32, 0.13, 0.05), (0.17, 0.068, 0.028))
    hot = g.math("MULTIPLY", g.ramp(g.noise(30.0 * scale, detail=3.0), 0.65, 0.8), 0.5)
    rcol = g.mix(hot, rcol, (0.42, 0.19, 0.07))
    rcol = g.mix(deep, rcol, (0.06, 0.027, 0.014))
    col = g.mix(rustm, col, rcol)
    pit_d, pit_r = kf._cells(g, 260.0 * scale)
    pits = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(pit_d, 0.4, 0.15), g.ramp(pit_r, 0.4, 0.7)), g.math("MULTIPLY", rustm, 1.0))
    col = g.mix(g.math("MULTIPLY", pits, 0.7), col, (0.025, 0.012, 0.007))
    flake_e = kf._voronoi(g, 38.0 * scale, kf._warped(g, 20.0 * scale, 0.008), feature="DISTANCE_TO_EDGE")
    flake = g.math("MULTIPLY", g.ramp(flake_e, 0.02, 0.0), g.math("MULTIPLY", rustm, g.ramp(g.noise(6.0, detail=3.0), 0.45, 0.65)))
    col = g.mix(g.math("MULTIPLY", flake, 0.7), col, (0.04, 0.02, 0.012))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", rustm, 0.35), g.math("MULTIPLY", deep, 0.25)))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", pits, 0.55), g.math("MULTIPLY", flake, 0.35)))
    rough = g.mixf(rustm, rough, 0.9)
    metalness = g.mixf(rustm, metalness, 0.12)
    if label is not None:
        t = nk._attr(g, "t")
        edge_n = g.math("MULTIPLY", g.noise(30.0, detail=4.0), 0.1)
        band = g.math("MULTIPLY", g.ramp(g.math("ADD", t, edge_n), label_band[0], label_band[0] + 0.02),
                      g.ramp(g.math("ADD", t, edge_n), label_band[1] + 0.02, label_band[1]))
        left = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0, distortion=0.4), 0.38, 0.5), 1.0)
        lab = g.math("MULTIPLY", band, left)
        lcol = g.mix(g.ramp(g.noise(10.0, detail=3.0), 0.3, 0.7), label[0], label[1])
        lcol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=4.0), 0.55, 0.75), 0.6), lcol, (0.09, 0.06, 0.035))
        col = g.mix(lab, col, lcol)
        height = g.math("ADD", height, g.math("MULTIPLY", lab, 0.2))
        rough = g.mixf(lab, rough, 0.9)
        metalness = g.mixf(lab, metalness, 0.0)
    if soot > 0.0:
        sm = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=4.0), 0.3, 0.6), soot)
        col = g.mix(sm, col, (0.012, 0.011, 0.01))
        rough = g.mixf(sm, rough, 0.9)
    col, rough, low = _ground_dirt(g, col, rough, amount=0.7, height=0.1)
    metalness = g.mixf(low, metalness, 0.0)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return col, height, rough, metalness


def rust_mat(name, **kw):
    mat, g = new_mat(name)
    col, height, rough, metal = rust_surface(g, **kw)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 1.0, 0.0035))


def enamel_mat(name, enamel=(0.5, 0.47, 0.4), speck=(0.05, 0.07, 0.1), rim=(0.05, 0.08, 0.14), wear=0.8, rim_t=0.5, foot_t=0.25):
    """An old enamelware pot: speckled enamel crazed with hairlines and chipped through to black iron and rust, a dark
    rim line, soot on the t-low base. t runs 0 at the pot's foot to 1 at its rim."""
    mat, g = new_mat(name)
    t = nk._attr(g, "t")
    tone = g.noise(6.0, detail=4.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), dark(enamel, 0.82), enamel)
    sp_d, sp_r = kf._cells(g, 190.0)
    spk = g.math("MULTIPLY", g.ramp(sp_d, 0.3, 0.1), g.ramp(sp_r, 0.5, 0.7))
    col = g.mix(g.math("MULTIPLY", spk, 0.7), col, speck)
    craze = g.ramp(kf._voronoi(g, 26.0, kf._warped(g, 15.0, 0.01), feature="DISTANCE_TO_EDGE"), 0.01, 0.0)
    col = g.mix(g.math("MULTIPLY", craze, 0.45), col, dark(enamel, 0.45))
    dirtn = g.ramp(g.noise(4.0, detail=5.0, distortion=0.5), 0.5, 0.75)
    col = g.mix(g.math("MULTIPLY", dirtn, 0.55), col, (0.1, 0.075, 0.05))
    # rim band
    rimb = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, rim_t)), 0.03, 0.01)
    col = g.mix(rimb, col, rim)
    # chips: cells
    cd, cr = kf._cells(g, 9.0, kf._warped(g, 22.0, 0.012))
    chip = g.math("MULTIPLY", g.ramp(cd, 0.55, 0.3), g.ramp(g.noise(5.0, detail=4.0), 0.58 - 0.12 * wear, 0.66 - 0.12 * wear))
    chip = g.math("MAXIMUM", chip, g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, rim_t)), 0.05, 0.0), g.ramp(g.noise(30.0, detail=3.0), 0.4, 0.55)))
    iron = g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.3, 0.7), (0.012, 0.011, 0.011), (0.045, 0.04, 0.036))
    rust = g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=5.0), 0.4, 0.6), g.ramp(chip, 0.3, 0.9))
    iron = g.mix(g.math("MULTIPLY", rust, 0.85), iron, (0.25, 0.1, 0.04))
    col = g.mix(g.ramp(chip, 0.35, 0.7), col, iron)
    # rust runs from chips
    run = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (40.0, 40.0, 3.0)))
    runs = g.math("MULTIPLY", g.ramp(run, 0.55, 0.75), g.ramp(g.noise(6.0, detail=3.0), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", runs, 0.4 * wear), col, (0.17, 0.08, 0.035))
    # soot on the foot
    soot = g.math("MULTIPLY", g.ramp(t, foot_t, 0.02), g.ramp(g.noise(8.0, detail=4.0), 0.2, 0.6))
    col = g.mix(g.math("MULTIPLY", soot, 0.95), col, (0.012, 0.011, 0.01))
    rough = g.mixf(g.ramp(chip, 0.3, 0.7), g.mixf(dirtn, 0.35, 0.8), 0.9)
    rough = g.mixf(soot, rough, 0.95)
    col, rough, low = _ground_dirt(g, col, rough, amount=0.8, height=0.1)
    height = g.math("SUBTRACT", g.math("ADD", 0.6, g.math("MULTIPLY", spk, 0.1)), g.math("MULTIPLY", chip, 0.55))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", craze, 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", rust, 0.3))
    metal = g.mixf(g.ramp(chip, 0.35, 0.7), 0.0, 0.5)
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 1.0, 0.0025))


def plastic_mat(name, color, color2=None, chalk=0.5, cracks=0.7, mildew=0.4, rough=0.55):
    """Sun-rotted molded plastic: chalky bleached where the sun hit it, an orange-peel grain, scuffs, hairline
    cracks black in the depths, dirt in the hollows, green mildew low down."""
    mat, g = new_mat(name)
    nz = ks._normal_z(g)
    c2 = color2 or dark(color, 0.7)
    col = g.mix(g.ramp(g.noise(3.4, detail=4.0), 0.3, 0.7), color, c2)
    peel = g.noise(380.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(peel, 0.45, 0.8), 0.15), col, dark(color, 0.7))
    chalkm = g.math("MULTIPLY", g.ramp(nz, 0.0, 0.8), g.ramp(g.noise(5.0, detail=4.0), 0.25, 0.7))
    chalkm = g.math("MULTIPLY", chalkm, chalk)
    col = g.mix(chalkm, col, lift((color[0] * 0.5 + 0.28, color[1] * 0.5 + 0.28, color[2] * 0.5 + 0.28), 0.9))
    scuff = g.ramp(kf._ridged(g, g.noise(1.0, detail=2.0, vector=ks._stretched(g, (260.0, 40.0, 260.0)))), 0.84, 0.98)
    scuff = g.math("MULTIPLY", scuff, g.ramp(g.noise(7.0, detail=3.0), 0.4, 0.65))
    col = g.mix(g.math("MULTIPLY", scuff, 0.4), col, (0.28, 0.27, 0.25))
    ce = kf._voronoi(g, 5.5, kf._warped(g, 9.0, 0.03, kf._warped(g, 40.0, 0.004)), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.012, 0.0), g.ramp(g.noise(3.0, detail=2.0), 0.42, 0.55))
    crack = g.math("MULTIPLY", crack, cracks)
    col = g.mix(crack, col, (0.008, 0.007, 0.006))
    dirty = g.ramp(g.noise(9.0, detail=5.0, distortion=0.4), 0.55, 0.75)
    col = g.mix(g.math("MULTIPLY", dirty, 0.45), col, (0.07, 0.055, 0.04))
    mm = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0, distortion=0.5), 0.58, 0.7), g.ramp(_z(g), G + 0.45, G))
    mm = g.math("MULTIPLY", mm, mildew)
    col = g.mix(g.math("MULTIPLY", mm, 0.8), col, (0.03, 0.05, 0.022))
    r = g.mixf(chalkm, rough, 0.88)
    r = g.mixf(dirty, r, 0.9)
    col, r, low = _ground_dirt(g, col, r, amount=1.0, height=0.12)
    height = g.math("ADD", g.math("MULTIPLY", peel, 0.2), g.math("MULTIPLY", scuff, -0.1))
    height = g.math("SUBTRACT", g.math("ADD", height, 0.3), g.math("MULTIPLY", crack, 0.7))
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.002))


def alu_mat(name, corrode=0.8, rust=0.3):
    """Tubular aluminum chair frame gone dull: pitted grey-white oxide, dark grime, orange rust stains bleeding from
    the joints."""
    mat, g = new_mat(name)
    tone = g.noise(8.0, detail=4.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.28, 0.285, 0.29), (0.17, 0.172, 0.175))
    pit_d, pit_r = kf._cells(g, 280.0)
    pits = g.math("MULTIPLY", g.ramp(pit_d, 0.42, 0.18), g.ramp(pit_r, 0.35, 0.65))
    ox = g.ramp(g.noise(5.0, detail=5.0, distortion=0.4), 0.4, 0.65)
    col = g.mix(g.math("MULTIPLY", ox, 0.6 * corrode), col, (0.38, 0.385, 0.37))
    col = g.mix(g.math("MULTIPLY", pits, 0.7 * corrode), col, (0.08, 0.08, 0.075))
    grime = g.math("MULTIPLY", g.ramp(g.noise(10.0, detail=5.0), 0.5, 0.72), 0.55)
    col = g.mix(grime, col, (0.045, 0.04, 0.035))
    runs = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (30.0, 30.0, 4.0)))
    rr = g.math("MULTIPLY", g.ramp(runs, 0.55, 0.78), g.ramp(g.noise(4.0, detail=3.0), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", rr, rust), col, (0.2, 0.09, 0.04))
    r = g.mixf(ox, 0.4, 0.72)
    metal = g.mixf(ox, 0.85, 0.3)
    col, r, low = _ground_dirt(g, col, r, amount=0.7, height=0.1)
    height = g.math("SUBTRACT", g.math("ADD", 0.5, g.math("MULTIPLY", ox, 0.2)), g.math("MULTIPLY", pits, 0.4))
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, metal, r, g.bump(height, 1.0, 0.0015))


def webbing_mat(name, stripe_a=(0.045, 0.1, 0.07), stripe_b=(0.3, 0.29, 0.25), stripe_c=None, fray=0.5):
    """Lawn-chair webbing: t is 0..1 across the strap; stripes of faded plastic, woven grain along it, mildew, mud and
    sun rot."""
    mat, g = new_mat(name)
    t = nk._attr(g, "t")
    s = g.math("SINE", g.math("MULTIPLY", t, math.tau * 2.5))
    stripe = g.ramp(s, -0.15, 0.15)
    col = g.mix(stripe, stripe_b, stripe_a)
    if stripe_c is not None:
        mid = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, 0.5)), 0.12, 0.05)
        col = g.mix(mid, col, stripe_c)
    edge = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, 0.5)), 0.44, 0.5)
    col = g.mix(g.math("MULTIPLY", edge, 0.5), col, dark(stripe_b, 0.5))
    weave = g.noise(1.0, detail=3.0, vector=ks._stretched(g, (900.0, 900.0, 900.0)))
    lines = g.math("MULTIPLY", g.math("ADD", g.math("SINE", g.math("MULTIPLY", g.separate(g.world)[0], 900.0)),
                                      g.math("SINE", g.math("MULTIPLY", g.separate(g.world)[1], 900.0))), 0.25)
    col = g.mix(g.math("MULTIPLY", g.ramp(weave, 0.4, 0.8), 0.28), col, dark(stripe_b, 0.55))
    fadem = g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.1, 0.9), 0.5)
    col = g.mix(fadem, col, lift(stripe_b, 1.1))
    mm = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=5.0, distortion=0.4), 0.55, 0.68), 0.7)
    col = g.mix(mm, col, (0.03, 0.045, 0.02))
    dirty = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.4, 0.7), 0.5)
    col = g.mix(dirty, col, (0.06, 0.047, 0.032))
    r = 0.9
    col, r2, low = _ground_dirt(g, col, r, amount=1.0, height=0.12)
    height = g.math("ADD", g.math("MULTIPLY", weave, 0.5), g.math("MULTIPLY", lines, 0.3))
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, r2, g.bump(height, 1.0, 0.0012))


def glass_mat(name, color=(0.05, 0.025, 0.008), label=None, dirt=0.8):
    """Dirty bottle glass (opaque, glossy): dark tinted, clouded with grime film, a few scuffs; `label` = (c1, c2)
    puts the rags of a paper label on the middle band of t."""
    mat, g = new_mat(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(g.noise(6.0, detail=3.0), 0.3, 0.7), dark(color, 0.8), lift(color, 1.2))
    film = g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=5.0, distortion=0.5), 0.45, 0.7), dirt)
    col = g.mix(g.math("MULTIPLY", film, 0.7), col, (0.09, 0.075, 0.055))
    r = g.mixf(film, 0.12, 0.7)
    height = g.math("MULTIPLY", g.noise(300.0, detail=2.0), 0.1)
    if label is not None:
        en = g.math("MULTIPLY", g.noise(26.0, detail=4.0), 0.12)
        band = g.math("MULTIPLY", g.ramp(g.math("ADD", t, en), 0.3, 0.33), g.ramp(g.math("ADD", t, en), 0.62, 0.59))
        left = g.ramp(g.noise(6.0, detail=5.0, distortion=0.4), 0.35, 0.47)
        lab = g.math("MULTIPLY", band, left)
        lcol = g.mix(g.ramp(g.noise(11.0, detail=3.0), 0.3, 0.7), label[0], label[1])
        lcol = g.mix(g.math("MULTIPLY", g.ramp(g.noise(24.0, detail=4.0), 0.5, 0.7), 0.7), lcol, (0.1, 0.075, 0.05))
        col = g.mix(lab, col, lcol)
        r = g.mixf(lab, r, 0.9)
        height = g.math("ADD", height, g.math("MULTIPLY", lab, 0.2))
    col, r, low = _ground_dirt(g, col, r, amount=1.0, height=0.1)
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.001))


def rope_mat(name, color=(0.2, 0.17, 0.12), fray=1.0):
    """Old rope, pale dirty fibre; the strands are drawn by the vertex attribute t (0..1 along it) twisted by noise."""
    mat, g = new_mat(name)
    t = nk._attr(g, "t")
    tone = g.noise(6.0, detail=4.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), dark(color, 0.6), color)
    fib = g.noise(1.0, detail=4.0, vector=ks._stretched(g, (500.0, 500.0, 500.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.8), 0.45), col, lift(color, 1.6))
    twist = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 900.0), g.math("MULTIPLY", g.noise(300.0, detail=2.0), 3.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(twist, 0.0, 0.8), 0.35), col, dark(color, 0.45))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(8.0, detail=4.0), 0.5, 0.75), 0.5), col, (0.05, 0.045, 0.035))
    mm = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=4.0), 0.58, 0.7), 0.5)
    col = g.mix(mm, col, (0.04, 0.055, 0.025))
    col, r, low = _ground_dirt(g, col, 0.95, amount=1.0, height=0.08)
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, r, g.bump(g.math("ADD", fib, g.math("MULTIPLY", twist, 0.5)), 1.0, 0.0012))


def bone_mat(name, tone=(0.4, 0.36, 0.28), dark_c=(0.2, 0.15, 0.1)):
    """Weathered bone, as bone_remains.py makes it."""
    mat, g = new_mat(name)
    co = g.coords()
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (60.0, 60.0, 60.0)))
    cells, r1 = kf._cells(g, 160.0)
    tonal = g.noise(5.0, detail=4.0)
    col = g.mix(g.ramp(tonal, 0.3, 0.7), tone, tuple(c * 0.78 for c in tone))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.85), 0.35), col, dark_c)
    pores = g.math("MULTIPLY", g.ramp(cells, 0.5, 0.15), g.ramp(g.noise(8.0, detail=3.0), 0.45, 0.7))
    col = g.mix(g.math("MULTIPLY", pores, 0.5), col, tuple(c * 0.45 for c in dark_c))
    ce = kf._voronoi(g, 14.0, kf._warped(g, 20.0, 0.01), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.02, 0.0), g.ramp(g.noise(6.0), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", crack, 0.8), col, tuple(c * 0.3 for c in dark_c))
    stain = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0), 0.55, 0.75), 0.5)
    col = g.mix(stain, col, (0.1, 0.075, 0.045))
    col, r, low = _ground_dirt(g, col, 0.8, amount=1.0, height=0.1)
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", fib, 0.4), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, pores), 0.3)),
                    g.math("MULTIPLY", crack, 0.5))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.004))


def paint_mat(name, paint=(0.06, 0.1, 0.07), wear=0.7):
    return rust_mat(name, metal=(0.26, 0.26, 0.25), rust=0.55 + 0.3 * wear, paint=paint, paint_cover=1.0 - 0.7 * wear)


class Wood:
    """Wood materials by kind and grain direction. The coordinates are rotated so the grain runs along the piece, so
    the direction is snapped to a handful of bins (6 headings x level or slanted, or upright) and a material made
    for each bin the first time it is asked for. Kinds: "bark" (old grey-brown bark), "silver" (bare weathered wood),
    "char" (burnt)."""

    def __init__(self, tag="CampWood", moss=0.0):
        self.cache = {}
        self.tag = tag
        self.moss = moss

    @staticmethod
    def snap(direction):
        d = Vector(direction).normalized()
        if d.z < 0:
            d = -d
        el = math.degrees(math.asin(clamp(d.z, -1.0, 1.0)))
        if el > 68.0:
            return (0, 90)
        head = math.degrees(math.atan2(d.y, d.x)) % 180.0
        hb = int(round(head / 30.0)) % 6
        return (hb, 0 if el < 22.0 else 45)

    def get(self, kind, direction, **kw):
        key = (kind,) + self.snap(direction)
        if key not in self.cache:
            hb, el = key[1], key[2]
            if el == 90:
                dv = Vector((0.0, 0.0, 1.0))
            else:
                h = math.radians(hb * 30.0)
                e = math.radians(el)
                dv = Vector((math.cos(h) * math.cos(e), math.sin(h) * math.cos(e), math.sin(e)))
            name = "%s_%s_%d_%d" % (self.tag, kind, hb, el)
            self.cache[key] = wood_mat(name, kind, dv, **kw)
        return self.cache[key]


def wood_mat(name, kind, direction, bs=0.7, peel=0.62, moss=0.0):
    mat, g = new_mat(name, direction)
    if kind == "char":
        col, height, rough = lk._char_surface(g, bs)
    elif kind == "silver":
        col, height, rough = lk._silver_surface(g, bs)
    else:
        col, height, rough = lk._bark_core(g, "forest", bs, peel)
    col = tk.grade(g, col, sat=0.9, value=0.95)
    col, rough, low = _ground_dirt(g, col, rough, amount=0.9, height=0.1)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, lk.RELIEF))


def stone_mat(name, sooty=None, moss=0.25, lichen=0.8, stain=1.0, tint=(1.0, 1.0, 1.0)):
    """Granite for the fire ring: lk's granite, blackened where the flames reached when `sooty` = (cx, cy, radius) (soot
    on the inner and upper parts, fading outward)."""
    mat, g = new_mat(name)
    col, height, rough = fk.granite_surface(g, moss=moss, lichen=lichen, stain=stain, tint=tint)
    if sooty is not None:
        cx, cy, rad = sooty
        x, y, z = g.separate(g.world)
        d = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", x, cx), g.math("SUBTRACT", x, cx)),
                                    g.math("MULTIPLY", g.math("SUBTRACT", y, cy), g.math("SUBTRACT", y, cy))))
        near = g.ramp(d, rad + 0.2, rad - 0.08)
        sm = g.math("MULTIPLY", g.math("MULTIPLY", near, g.ramp(g.noise(10.0, detail=5.0), 0.3, 0.6)), 0.85)
        sm = g.math("MULTIPLY", sm, g.ramp(z, G + 0.02, G + 0.08))
        col = g.mix(g.math("MULTIPLY", sm, 1.0, clamp=True), col, (0.012, 0.011, 0.01))
        rough = g.mixf(sm, rough, 0.92)
    col, rough, low = _ground_dirt(g, col, rough, amount=0.6, height=0.08)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.012))


def dirt_mat(name, ash=0.0):
    """Bare trampled earth, pale where it dried and cracked, litter threaded through; with `ash` grey ash and charcoal
    flecks."""
    mat, g = new_mat(name)
    col, height, rough = lk.soil_surface(g, moss=0.0, rooty=0.6, stony=1.2, dark=1.15)
    crack = g.ramp(kf._voronoi(g, 5.0, kf._warped(g, 12.0, 0.03), feature="DISTANCE_TO_EDGE"), 0.03, 0.0)
    col = g.mix(g.math("MULTIPLY", crack, 0.6), col, (0.012, 0.009, 0.006))
    dry = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0), 0.5, 0.75), 0.45)
    col = g.mix(dry, col, (0.17, 0.13, 0.09))
    if ash > 0.0:
        am = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=5.0, distortion=0.5), 0.4, 0.62), ash)
        flecks = g.ramp(kf._cells(g, 140.0)[0], 0.3, 0.1)
        ac = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.16, 0.155, 0.15), (0.3, 0.29, 0.275))
        ac = g.mix(g.math("MULTIPLY", flecks, 0.7), ac, (0.015, 0.014, 0.013))
        col = g.mix(am, col, ac)
        height = g.mixf(am, height, g.math("ADD", 0.3, g.math("MULTIPLY", g.noise(120.0, detail=3.0), 0.3)))
        rough = g.mixf(am, rough, 0.96)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.012))


def litter_mat(name, c1, c2, rot=0.5):
    """A dead leaf: mottled brown, a net of paler veins, rot freckles and holes darker, darker toward the stalk (t)."""
    mat, g = new_mat(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), c1, c2)
    d, r = kf._cells(g, 140.0, kf._warped(g, 60.0, 0.004))
    e = kf._voronoi(g, 150.0, kf._warped(g, 55.0, 0.004), feature="DISTANCE_TO_EDGE")
    veins = g.ramp(e, 0.03, 0.0)
    col = g.mix(g.math("MULTIPLY", veins, 0.4), col, lift(c2, 1.5))
    fre = g.math("MULTIPLY", g.ramp(d, 0.35, 0.1), g.ramp(r, 0.45, 0.8))
    col = g.mix(g.math("MULTIPLY", fre, 0.7 * rot), col, dark(c1, 0.3))
    blot = g.math("MULTIPLY", g.ramp(g.noise(12.0, detail=4.0), 0.5, 0.72), rot * 0.6)
    col = g.mix(blot, col, dark(c1, 0.45))
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.25, 0.0), 0.5), col, dark(c1, 0.5))
    col = tk.grade(g, col, sat=0.85, value=0.9)
    return tk.finish(mat, g, col, 0.0, 0.85, g.bump(g.math("ADD", veins, g.math("MULTIPLY", fre, -0.5)), 0.5, 0.0015))


def ground_mats():
    """Litter and grass for the clutter: dead leaves in a few browns, living grass, straw."""
    return dict(
        litter=[litter_mat("CampLitter", (0.1, 0.06, 0.03), (0.17, 0.1, 0.045)),
                litter_mat("CampLitterGold", (0.21, 0.13, 0.05), (0.14, 0.08, 0.03), rot=0.4),
                litter_mat("CampLitterGrey", (0.07, 0.058, 0.042), (0.11, 0.09, 0.065), rot=0.8)],
        grass=nk.plant("CampGrass", (0.1, 0.14, 0.045), (0.17, 0.2, 0.07), rough=0.75, vary=0.35),
        straw=nk.plant("CampStraw", (0.2, 0.16, 0.075), (0.12, 0.09, 0.045), rough=0.8, vary=0.3),
        leaf=nk.plant("CampLeaf", (0.07, 0.13, 0.035), (0.12, 0.17, 0.05), rough=0.65, vary=0.3))


# ================================================================ the transform

class Place:
    """A rigid transform for building an object in its own frame: yaw (degrees about Z), pitch and roll (degrees about
    Y and X, applied first), then moved to `at`. Call it on a Vector (or tuple); `.dir()` turns a direction. `rest(points)`
    shifts it so the lowest of `points` just touches the ground. `child(...)` is a Place expressed in this one's frame
    (a lid on its hinge)."""

    def __init__(self, at=(0.0, 0.0, 0.0), yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, matrix=None):
        if matrix is not None:
            self.M = matrix.copy()
            return
        R = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "Y")
             @ Matrix.Rotation(math.radians(roll), 3, "X")) * scale
        self.M = Matrix.Translation(Vector(at)) @ R.to_4x4()

    def __call__(self, p):
        return self.M @ Vector(p)

    @property
    def at(self):
        return self.M.translation

    def dir(self, d):
        return self.M.to_3x3() @ Vector(d)

    def rest(self, local_points, clearance=0.0):
        low = min(self(p).z for p in local_points)
        t = self.M.translation
        t.z += (G + clearance) - low
        self.M.translation = t
        return self

    def child(self, at=(0.0, 0.0, 0.0), yaw=0.0, pitch=0.0, roll=0.0):
        return Place(matrix=self.M @ Place(at, yaw, pitch, roll).M)


# ================================================================ shapes

def ring_basis(axis):
    return ks.basis(axis)


def _noise3(p, scale, seed):
    return mn.noise(Vector((p.x * scale + seed * 7.1, p.y * scale + seed * 3.7, p.z * scale + seed * 1.3)))


def solid_tube(b, bark, endm, p0, p1, r, rnd, under=None, sides=14, lump=0.05, flare=0.0, r1=None, flat=None, seed=0,
               ragged=0.0, lod=2, sink_cull=True, cut=None):
    """A closed rough log from p0 to p1, radius r (to r1 at the far end), `lump` bark lumpiness (fraction of r), `flare`
    root swelling at p0, `flat` = (normal, offset): everything beyond that plane is pressed flat (a split log or a
    seat cut), `ragged` jaggedness of the end faces. Faces looking down go to `under` (cheap). Returns the body
    (vertices, polygons) for the colliders; the render is bark on the sides and `endm` (t = distance from the axis,
    meters) on the ends; faces lying on the `flat` plane take material `cut`."""
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    L = axis.length
    ax, u, v = ks.basis(axis)
    r1 = r if r1 is None else r1
    n = max(2, int(math.ceil(L / 0.12)))
    ring_pts = []
    onplane = set()
    for i in range(n + 1):
        s = i / n
        c = p0 + ax * (L * s)
        rr = r + (r1 - r) * s
        if flare > 0.0:
            rr *= 1.0 + flare * math.exp(-s * L / 0.1)
        row = []
        for k in range(sides):
            a = k / sides * math.tau
            out = u * math.cos(a) + v * math.sin(a)
            kk = 1.0 + lump * (_noise3(c + out * rr, 7.0, seed) + 0.5 * _noise3(c + out * rr, 21.0, seed + 1))
            p = c + out * rr * kk
            if ragged and (i == 0 or i == n):
                p = p + ax * (rnd.uniform(-1.0, 1.0) * ragged) * (1 if i else -1) * 1.0
            if flat is not None:
                nrm, off = Vector(flat[0]).normalized(), flat[1]
                d = (p - p0).dot(nrm) - off
                if d > 0.0:
                    p = p - nrm * d
                    onplane.add(i * sides + k)
            row.append(p)
        ring_pts.append(row)
    cs = [p0 - ax * 0.0, p1]
    verts = [p for row in ring_pts for p in row] + cs
    polys = []
    for i in range(n):
        for k in range(sides):
            k1 = (k + 1) % sides
            polys.append((i * sides + k, i * sides + k1, (i + 1) * sides + k1, (i + 1) * sides + k))
    c0, c1 = len(verts) - 2, len(verts) - 1
    for k in range(sides):
        k1 = (k + 1) % sides
        polys.append((c0, k1, k))
        polys.append((c1, n * sides + k, n * sides + k1))
    # render
    mb = b.mesh(bark)
    mb.begin(p0 + ax * (L * 0.5))
    mu = b.mesh(under) if under is not None else None
    mc = b.mesh(cut) if cut is not None else None
    me = b.mesh(endm)
    vb, vu, vc = {}, {}, {}
    saved = b.lod
    b.lod = lod
    mid = p0 + ax * (L * 0.5)
    for i in range(n):
        for k in range(sides):
            k1 = (k + 1) % sides
            idx = (i * sides + k, i * sides + k1, (i + 1) * sides + k1, (i + 1) * sides + k)
            pts = [verts[j] for j in idx]
            if sink_cull and max(q.z for q in pts) < G - 0.03:
                continue
            nrm = (pts[1] - pts[0]).cross(pts[3] - pts[0])
            use_under = mu is not None and nrm.z < -0.35 * nrm.length and max(q.z for q in pts) < G + 0.12
            on_cut = mc is not None and all(j in onplane for j in idx)
            mesh, cache = (mu, vu) if use_under else (mc, vc) if on_cut else (mb, vb)
            mesh.begin(mid)
            vs = []
            for j, q in zip(idx, pts):
                if j not in cache:
                    cache[j] = mesh.v(q, 0.5)
                vs.append(cache[j])
            mesh.f(vs, True)
    b.lod = 0
    for which, row_i, cen in ((0, 0, p0), (1, n, p1)):
        me.begin(cen)
        cv = me.v(verts[c0 if which == 0 else c1] + ax * (-0.002 if which == 0 else 0.002), 0.0)
        rim = []
        for k in range(sides):
            q = verts[row_i * sides + k]
            rim.append(me.v(q, (q - cen).length))
        for k in range(sides):
            k1 = (k + 1) % sides
            if which == 0:
                me.f((cv, rim[k1], rim[k]), False)
            else:
                me.f((cv, rim[k], rim[k1]), False)
    b.lod = saved
    return verts, polys


def cloth(b, mat, fn, nu, nv, hint=UP, thick=0.003, skip=None, rnd=None, tfn=None, lod=0, back=None, sgn=None):
    """A double-sided sheet: fn(i, j) is the position of grid point (i, j), 0 <= i <= nu, 0 <= j <= nv. `skip(i, j, k)`
    drops triangle k (0 or 1) of cell (i, j) (holes, torn edges). Faces turn to face `hint` on the side that looks up
    (the other side is the same sheet `thick` lower, the other way round, since the game culls back faces). `back` is
    an optional second material for the underside. Returns the grid of points."""
    P = [[Vector(fn(i, j)) for j in range(nv + 1)] for i in range(nu + 1)]
    N = [[None] * (nv + 1) for _ in range(nu + 1)]
    flip = 0.0
    for i in range(nu + 1):
        for j in range(nv + 1):
            a = P[min(nu, i + 1)][j] - P[max(0, i - 1)][j]
            c = P[i][min(nv, j + 1)] - P[i][max(0, j - 1)]
            nrm = a.cross(c)
            nrm = nrm.normalized() if nrm.length > 1e-9 else Vector(UP)
            N[i][j] = nrm
            flip += nrm.dot(hint)
    if sgn is None:
        sgn = 1.0 if flip >= 0.0 else -1.0
    m = b.mesh(mat)
    mb = b.mesh(back or mat)
    vf, vb = {}, {}
    saved = b.lod
    b.lod = lod

    def vert(cache, mesh, i, j, side):
        key = (i, j)
        if key not in cache:
            nrm = N[i][j] * sgn
            p = P[i][j] if side > 0 else P[i][j] - nrm * thick
            t = tfn(i, j) if tfn else 0.5
            cache[key] = mesh.v(p, t)
        return cache[key]

    for i in range(nu):
        for j in range(nv):
            quad = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            tris = ((0, 1, 2), (0, 2, 3)) if (i + j) % 2 == 0 else ((0, 1, 3), (1, 2, 3))
            for k, tri in enumerate(tris):
                if skip is not None and skip(i, j, k):
                    continue
                ids = [quad[q] for q in tri]
                if sgn < 0:
                    ids = ids[::-1]
                m.begin(P[i][j])
                m.f([vert(vf, m, a, c, 1) for a, c in ids], True)
                mb.begin(P[i][j])
                mb.f([vert(vb, mb, a, c, -1) for a, c in ids[::-1]], True)
    b.lod = saved
    return P


def ribbon(b, mat, pts, width, rnd=None, thick=0.002, up=UP, tfn=True, lod=0):
    """A flat strap along a polyline, `width` wide, lying in the plane of `up` (its face looks along `up`), double
    sided; t runs 0..1 across the strap (for webbing stripes). `width` may be a list per point."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    ws = width if isinstance(width, (list, tuple)) else [width] * n
    rows = []
    for i, p in enumerate(pts):
        tan = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        tan = tan.normalized() if tan.length > 1e-9 else Vector((1.0, 0.0, 0.0))
        side = tan.cross(up)
        if side.length < 1e-4:
            side = tan.cross(Vector((1.0, 0.0, 0.0)))
        side.normalize()
        rows.append((p - side * ws[i] * 0.5, p + side * ws[i] * 0.5, side))
    # face direction: side x tan, which is `up`-ish
    m = b.mesh(mat)
    saved = b.lod
    b.lod = lod
    m.begin(pts[0])
    fr, bk = [], []
    for i, (l, r_, side) in enumerate(rows):
        tan = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        nrm = side.cross(tan).normalized()
        if nrm.dot(up) < 0:
            nrm = -nrm
        fr.append((m.v(l, 0.0), m.v(r_, 1.0)))
        bk.append((m.v(l - nrm * thick, 0.0), m.v(r_ - nrm * thick, 1.0)))
    for i in range(n - 1):
        a, c = fr[i], fr[i + 1]
        tan = pts[i + 1] - pts[i]
        side = rows[i][2]
        nrm = side.cross(tan)
        if nrm.dot(up) >= 0:
            m.f((a[0], a[1], c[1], c[0]), True)
            m.f((bk[i][1], bk[i][0], bk[i + 1][0], bk[i + 1][1]), True)
        else:
            m.f((a[0], c[0], c[1], a[1]), True)
            m.f((bk[i][0], bk[i][1], bk[i + 1][1], bk[i + 1][0]), True)
    b.lod = saved


def lathe(b, mat, profile, place=None, sides=16, closed=True, rnd=None, dent=None, jag=0.0, cap_bottom=True, axis_t=True,
          mats_by_range=None, lod=0, smooth=True, start_angle=0.0, sweep=math.tau, shape=None):
    """A surface of revolution about local Z: profile [(radius, z)] bottom to top (an open can goes up the outside, over
    the rim and down the inside). t runs 0..1 along the profile. `place` is a Place; `dent(p)` returns a displaced
    local point; `jag` roughens the last ring (a torn rim). A radius of 0 closes it to a point. `shape` = (hx, hy, n)
    swaps the round cross-section for a superellipse of those half sizes (a cooler: n 6); the profile's radius is
    then a scale on it. Returns the world points of the surface (list) and the rings."""
    place = place or Place()
    m = b.mesh(mat)
    saved = b.lod
    b.lod = lod
    n = len(profile)
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + math.hypot(profile[i][0] - profile[i - 1][0], profile[i][1] - profile[i - 1][1]))
    tot = acc[-1] or 1.0
    full = abs(sweep - math.tau) < 1e-6
    cols = sides if full else sides + 1
    rings = []
    allpts = []
    for i, (rad, z) in enumerate(profile):
        t = acc[i] / tot
        row = []
        if rad <= 1e-6:
            q = Vector((0.0, 0.0, z))
            if dent:
                q = dent(q)
            w = place(q)
            allpts.append(w)
            row = [m.v(w, t)]
        else:
            for k in range(cols):
                a = start_angle + sweep * k / sides
                if shape is None:
                    q = Vector((math.cos(a) * rad, math.sin(a) * rad, z))
                else:
                    ca, sa = math.cos(a), math.sin(a)
                    ex = 2.0 / shape[2]
                    q = Vector((math.copysign(abs(ca) ** ex, ca) * rad * shape[0], math.copysign(abs(sa) ** ex, sa) * rad * shape[1], z))
                if jag and i == n - 1:
                    q.z += rnd.uniform(-jag, jag)
                    q.x *= 1.0 + rnd.uniform(-jag, jag)
                if dent:
                    q = dent(q)
                w = place(q)
                allpts.append(w)
                row.append(m.v(w, t))
        rings.append(row)
    m.begin(place((0.0, 0.0, profile[0][1])))
    for i in range(n - 1):
        A, B = rings[i], rings[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        rng = sides if full else sides
        for k in range(rng):
            k1 = (k + 1) % sides if full else k + 1
            if len(B) == 1:
                m.f((A[k], A[k1], B[0]), smooth)
            elif len(A) == 1:
                m.f((A[0], B[k1], B[k]), smooth)
            else:
                m.f((A[k], A[k1], B[k1], B[k]), smooth)
    b.lod = saved
    return allpts, rings


def disc(b, mat, center, radius, place=None, sides=16, up=True, t=0.5):
    """A flat disc (a can's bottom, a lid) at local z, facing +Z when up else -Z."""
    place = place or Place()
    m = b.mesh(mat)
    m.begin(place(center))
    c = m.v(place(center), 0.0)
    ring = [m.v(place(Vector(center) + Vector((math.cos(k / sides * math.tau) * radius, math.sin(k / sides * math.tau) * radius, 0.0))), 1.0)
            for k in range(sides)]
    for k in range(sides):
        k1 = (k + 1) % sides
        m.f((c, ring[k], ring[k1]) if up else (c, ring[k1], ring[k]), False)


def wire(b, mat, pts, r, sides=4, cap=True, rnd=None, jag=0.0, lod=0):
    """A thin rod or cord along a polyline, constant radius."""
    saved = b.lod
    b.lod = lod
    ks.tube(b, mat, pts, [r] * len(pts), sides=sides, cap=cap, jag=jag, rnd=rnd)
    b.lod = saved


def tapered(b, mat, pts, r0, r1, sides=5, cap=True, rnd=None, jag=0.0, lod=0):
    n = len(pts)
    saved = b.lod
    b.lod = lod
    ks.tube(b, mat, pts, [r0 + (r1 - r0) * i / (n - 1) for i in range(n)], sides=sides, cap=cap, jag=jag, rnd=rnd)
    b.lod = saved


def catenary(p0, p1, sag, n=10, side=None):
    """A sagging cord between two points (parabola), `sag` meters low in the middle."""
    p0, p1 = Vector(p0), Vector(p1)
    out = []
    for i in range(n + 1):
        s = i / n
        q = p0.lerp(p1, s)
        q.z -= sag * 4.0 * s * (1.0 - s)
        out.append(q)
    return out


def box_solid(b, mat, size, place=None, bevel=0.0, lod=0, rnd=None, jitter=0.0, tvals=None):
    """A solid box mesh (planks, a box lid, a crate) with optionally ragged corners; returns the world points."""
    place = place or Place()
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = b.mesh(mat)
    saved = b.lod
    b.lod = lod
    cache = {}
    pts = []
    for f in bm.faces:
        m.begin(place(f.calc_center_median()))
        vs = []
        for v in f.verts:
            if v.index not in cache:
                q = v.co.copy()
                if jitter and rnd is not None:
                    q += Vector((rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter)))
                w = place(q)
                pts.append(w)
                cache[v.index] = m.v(w, 0.5)
            vs.append(cache[v.index])
        m.f(vs, False)
    b.lod = saved
    bm.free()
    return pts


def tuft(b, mat, x, y, rnd, count=9, height=0.28, spread=0.09, width=0.011, z=None, lean=0.25, lod=1):
    """A tuft of grass blades fanning up and out from (x, y), standing on the ground (or at z)."""
    z = G + 0.002 if z is None else z
    saved = b.lod
    for i in range(count):
        a = rnd.uniform(0, math.tau)
        r = spread * math.sqrt(rnd.random())
        base = Vector((x + r * math.cos(a), y + r * math.sin(a), z))
        d = Vector((math.cos(a) * rnd.uniform(0.1, 0.5) * lean * 2, math.sin(a) * rnd.uniform(0.1, 0.5) * lean * 2, 1.0))
        b.lod = lod if i % 2 else 0
        ks.leaf(b, mat, base, d, height * rnd.uniform(0.55, 1.1), width * rnd.uniform(0.8, 1.3), bend=rnd.uniform(0.15, 0.55),
                fold=0.25, profile="lance", rows=2, roll=rnd.uniform(-40, 40))
    b.lod = saved


def litter_ring(b, mats, rnd, count, center, radius_range, keep=lambda x, y: True, size=(0.055, 0.085), flat=True, zfn=None):
    """Fallen leaves in a ring/blob: `count` leaf cards lying on the ground (or on a surface `keep` allows)."""
    saved = b.lod
    b.lod = 1
    n = tries = 0
    while n < count and tries < count * 30:
        tries += 1
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(*radius_range)
        x, y = center[0] + rr * math.cos(a), center[1] + rr * math.sin(a)
        if not keep(x, y):
            continue
        n += 1
        ang = rnd.uniform(0, math.tau)
        d = Vector((math.cos(ang), math.sin(ang), rnd.uniform(-0.05, 0.14)))
        ln = rnd.uniform(*size) * (1.0 if rnd.random() < 0.8 else 0.6)
        ks.leaf(b, rnd.choice(mats), (x, y, G + 0.004 + (zfn(x, y) if zfn else 0.0)), d, ln, ln * rnd.uniform(0.45, 0.8),
                bend=rnd.uniform(-0.45, 0.1), fold=rnd.uniform(0.15, 0.5), profile=rnd.choice(("oval", "oval", "lance", "heart")), rows=2,
                roll=rnd.uniform(-25, 25))
    b.lod = saved


def box_line(center, size, yaw=0.0):
    """A collider line for an oriented box standing on the ground (axes: u along `yaw` heading)."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return "box %.3f %.3f %.3f %.3f %.3f %.3f %.4f %.4f 0 %.4f %.4f 0 0 0 1" % (center[0], center[1], center[2], size[0], size[1], size[2],
                                                                                c, s, -s, c)


def body_from_bm(bm):
    return [v.co.copy() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces]


# ================================================================ export and previews

def set_preview_dir(path):
    global PREV
    PREV = path
    os.makedirs(path, exist_ok=True)


def preview(name, model, views, floor=1.0, figure=(2.8, 2.6)):
    """Renders `views` ([(label, camera position, target, lens)]) on the stage (a 1.8 m figure moved to `figure`)."""
    tk.preview_stage()
    fl = bpy.data.objects.get("Floor")
    if fl is not None:
        fl.scale = (floor, floor, 1.0)
    for n in ("ScaleFigure", "ScaleHead"):
        o = bpy.data.objects.get(n)
        if o is not None:
            o.location = (figure[0] - 1.1, figure[1] - 0.6, 0.0)
    wanted = [v for v in os.environ.get("CK_VIEWS", "").split(",") if v]
    res = int(os.environ.get("CK_RES", "1000"))
    samples = int(os.environ.get("CK_SAMPLES", "40"))
    for label, loc, tgt, *lens in views:
        if wanted and label not in wanted:
            continue
        tk.render(tk.camera(name + label, loc, tgt, lens=lens[0] if lens else 40), os.path.join(PREV, "%s_%s.png" % (name, label)),
                  res=(res, res * 3 // 4), samples=samples)


def only():
    return sys.argv[sys.argv.index("--") + 3:]


def atlas_size(default=2048):
    return int(os.environ.get("LK_SIZE", default))


def export(name, pieces, bodies, out_dir, size=2048, density=None, voxel=0.04, extra=(), limit=120, margin=0.012, boxes=None,
           coarse=0.3, rect=False):
    """lk.export (tight UV packing), with the camp's collider settings: bodies are voxelized finely (small solids)."""
    bx = list(boxes or [])
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in pieces:
        for v in o.data.vertices:
            for k in range(3):
                lo[k] = min(lo[k], v.co[k])
                hi[k] = max(hi[k], v.co[k])
    half = max(abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y))
    cells = 2 * max(0, int(math.ceil(half - 0.5 - 0.02))) + 1
    print("[extent] x %.2f..%.2f  y %.2f..%.2f  height %.2f  -> footprint %dx%d cells, %d high" % (
        lo.x, hi.x, lo.y, hi.y, hi.z - G, cells, cells, max(1, int(math.ceil(hi.z - G - 0.02)))))
    if os.environ.get("CK_NEUTRAL"):
        # Cheapest look: one grey material, for checking the geometry
        atlas = tk.triangulate(tk.join(pieces, name))
        m = bpy.data.materials.new("Neutral")
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.33, 0.3, 1.0)
        atlas.data.materials.clear()
        atlas.data.materials.append(m)
        print("[%s] %d triangles (neutral)" % (name, ks.triangles([atlas])))
        return atlas
    if os.environ.get("CK_NOBAKE"):
        # Quick look: the joined model with its procedural materials, no UVs, bake, colliders or files
        atlas = tk.triangulate(tk.join(pieces, name))
        print("[%s] %d triangles (not baked)" % (name, ks.triangles([atlas])))
        return atlas
    if bodies:
        bx += fk.voxel_boxes(bodies, voxel, margin, limit=limit)
    return lk.export(name, pieces, [], out_dir, size=size, density=density, extra=extra, rect=rect, coarse=coarse, boxes=bx)
