"""Nature Expanded's kit for fallen and standing timber features (windfalls, nurse logs, giant stumps, the hollow
trunk cache, deadfall piles; see ../FEATURES.md), on top of featurekit.py and the mossy log's material work.

What is here:

- Materials: `bark_surface` / `bark_mat` / `moss_shell_mat` (the mossy log's bark, peeling to bare wood, lichen and
  moss film, in the styles "forest" (old grey-brown bark), "fresh" (warm intact bark), "burnt" (alligator char with
  ash) and "bleached" (silver weathered wood), at any trunk size through `bs`), `end_grain` (growth rings by the
  attribute `t` = distance from the cut's axis in meters), `soil_mat` / `soil_moss_mat` (forest soil with clods,
  grit, rootlets, moss), `root_mat`, `fungus_materials`.
- `Trunk`: a closed-looking tapered trunk along a centerline (any lean or bend), with butt flare, bark lumps and knots,
  ragged or flat ends, `surface(s, a)` to place things on it, `capsules()` for its colliders and `moss_cover` for the
  lumpy moss cushions over its top.
- Small things: `limb` (snapped stubs and live branches), `needles` (conifer foliage), `mushroom`, `shelf_tiers`,
  `litter`, `ferns`.
- `preview`: front/side/top renders of a big feature on a bigger stage.

Conventions as featurekit: meters, Z up, the master cell's center at the origin, the ground at z = -0.5 (G). A trunk
runs along +x; materials use object coordinates stretched along x, so keep trunks along the x axis.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mn
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import featurekit as fk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
SNOW = ks.SNOW
RELIEF = 0.006


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


# ================================================================ materials

AXIS = "x"   # the way a trunk's grain runs: "x" for logs, "z" for stumps (set before making the materials)


def stretched(g, v):
    """ks._stretched with the long (grain) component of v on the trunk's axis."""
    return ks._stretched(g, v if AXIS == "x" else (v[1], v[2], v[0]))


def _bark_core(g, style, bs, peel):
    """The log's bark: ridges split by deep furrows that wander, branch and break across; flaky, finely grained,
    crusted with lichen; torn away in patches to weathered wood behind a ragged lip of red-brown inner bark. `bs`
    scales the furrow pattern (1 for a 40 cm log, about 0.4 for a metre-thick trunk)."""
    fresh = style == "fresh"
    st = stretched(g, (0.55, 7.0, 7.0))
    wv = kf._warped(g, 35.0 * bs, 0.0035 / bs, kf._warped(g, 3.0 * bs, 0.03 / bs, st))
    n = g.noise(5.5 * bs, detail=3.0, roughness=0.45, vector=wv)
    crest = g.math("ADD", kf._ridged(g, n), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(20.0 * bs, detail=2.0), 0.5), 0.05))
    crack = g.ramp(crest, 0.9, 1.0)
    _, piece = kf._cells(g, 5.5 * bs, wv)
    cross = g.math("MULTIPLY", g.ramp(kf._voronoi(g, 3.0 * bs, wv, feature="DISTANCE_TO_EDGE"), 0.05, 0.0),
                   g.ramp(g.noise(3.0 * bs, detail=3.0), 0.6, 0.7))
    crack = g.math("MAXIMUM", crack, cross)
    furrow = g.math("SUBTRACT", 1.0, crack)
    sf = bs ** 0.5
    flake = g.noise(1.0, detail=6.0, roughness=0.65, vector=stretched(g, (30.0 * sf, 95.0 * sf, 95.0 * sf)))
    grain = g.noise(1.0, detail=3.0, vector=stretched(g, (90.0, 520.0, 520.0)))
    tone = g.math("ADD", g.math("MULTIPLY", piece, 0.7), g.math("MULTIPLY", g.noise(9.0 * bs, detail=3.0, vector=wv), 0.3))
    if fresh:
        lo, hi, fl, dk = (0.082, 0.042, 0.027), (0.165, 0.092, 0.058), (0.215, 0.125, 0.082), (0.035, 0.022, 0.015)
    else:
        lo, hi, fl, dk = (0.07, 0.056, 0.044), (0.13, 0.108, 0.084), (0.17, 0.155, 0.135), (0.03, 0.024, 0.02)
    col = g.mix(g.ramp(tone, 0.2, 0.9), lo, hi)
    col = g.mix(g.math("MULTIPLY", g.ramp(flake, 0.5, 0.75), 0.7), col, fl)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.55, 0.2), 0.4), col, dk)
    strings = g.ramp(kf._ridged(g, g.noise(1.0, detail=3.0, vector=stretched(g, (12.0 * sf, 180.0 * sf, 180.0 * sf)))), 0.86, 0.98)
    col = g.mix(g.math("MULTIPLY", strings, 0.4), col, (0.025, 0.02, 0.016))
    col = g.mix(g.math("MULTIPLY", g.ramp(crack, 0.05, 0.45), 0.85), col, (0.035, 0.025, 0.018))
    col = g.mix(g.ramp(crack, 0.45, 0.9), col, (0.006, 0.005, 0.004))
    lt0, lt1 = (0.78, 0.82) if fresh else (0.68, 0.72)
    lich = g.math("MULTIPLY", g.ramp(g.math("ADD", g.noise(9.0, detail=5.0, distortion=0.3),
                                              g.math("MULTIPLY", g.noise(120.0, detail=2.0), 0.08)), lt0, lt1),
                  g.ramp(furrow, 0.4, 0.8))
    gran, _ = kf._cells(g, 420.0)
    lichen = g.math("MULTIPLY", lich, g.ramp(gran, 0.75, 0.35))
    col = g.mix(lichen, col, g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.35, 0.7), (0.13, 0.15, 0.1), (0.21, 0.225, 0.17)))
    bark_h = g.math("ADD", g.math("MULTIPLY", furrow, 0.55), g.math("MULTIPLY", flake, 0.3))
    bark_h = g.math("SUBTRACT", bark_h, g.math("MULTIPLY", strings, 0.06))
    bark_h = g.math("ADD", bark_h, g.math("ADD", g.math("MULTIPLY", grain, 0.08), g.math("MULTIPLY", lichen, 0.08)))

    pn = g.math("ADD", g.noise(2.0, detail=5.0, distortion=0.5),
                g.math("MULTIPLY", g.math("SUBTRACT", g.noise(45.0, detail=4.0), 0.5), 0.05))
    pk = g.ramp(pn, peel, peel + 0.006)
    lip = g.math("MULTIPLY", g.ramp(pn, peel - 0.011, peel - 0.004), g.math("SUBTRACT", 1.0, pk))
    fib = g.noise(1.0, detail=5.0, vector=stretched(g, (5.0, 260.0, 260.0)))
    fibre = g.ramp(kf._ridged(g, fib), 0.75, 0.98)
    wood = g.mix(g.ramp(fib, 0.3, 0.7), (0.12, 0.1, 0.078), (0.22, 0.195, 0.155))
    wood = g.mix(g.math("MULTIPLY", fibre, 0.35), wood, (0.27, 0.245, 0.2))
    check = g.ramp(kf._voronoi(g, 1.0, kf._warped(g, 30.0, 0.002, stretched(g, (1.6, 28.0, 28.0))),
                               feature="DISTANCE_TO_EDGE"), 0.03, 0.0)
    gallery = g.math("MULTIPLY", g.ramp(kf._ridged(g, g.noise(26.0, detail=2.0, distortion=1.6)), 0.955, 0.99),
                     g.ramp(g.noise(4.0), 0.5, 0.6))
    wood = g.mix(g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=4.0), 0.55, 0.75), 0.6), wood, (0.08, 0.06, 0.04))
    wood = g.mix(g.math("MULTIPLY", g.ramp(pn, peel + 0.05, peel), 0.7), wood, (0.05, 0.04, 0.03))
    wood = g.mix(g.math("MAXIMUM", check, gallery), wood, (0.025, 0.018, 0.013))
    wood_h = g.math("ADD", 0.2, g.math("MULTIPLY", fibre, 0.08))
    wood_h = g.math("SUBTRACT", wood_h, g.math("MULTIPLY", g.math("MAXIMUM", check, gallery), 0.2))
    col = g.mix(g.math("MULTIPLY", lip, 0.8), col,
                g.mix(g.ramp(g.noise(200.0), 0.3, 0.7), (0.06, 0.032, 0.02), (0.11, 0.06, 0.035)))
    col = g.mix(pk, col, wood)
    height = g.mixf(pk, bark_h, wood_h)
    rough = g.mixf(pk, g.mixf(lichen, 0.88, 0.93), 0.8)
    return col, height, rough


def _char_surface(g, bs):
    """Burnt wood: near-black blocks split by deep cracks across and along the grain (alligator char), the cracks
    brown where the wood below is only scorched, bare brown-grey wood where the char has fallen away, a dull sheen on
    the blocks, grey ash settled on the up-facing sides. No glow."""
    e = kf._voronoi(g, 1.0, kf._warped(g, 14.0, 0.01 / bs, stretched(g, (7.0 * bs, 30.0 * bs, 30.0 * bs))), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.06, 0.0)
    wide = g.ramp(e, 0.16, 0.0)
    tone = g.noise(9.0, detail=4.0)
    block = g.mix(g.ramp(tone, 0.35, 0.75), (0.012, 0.011, 0.01), (0.04, 0.036, 0.033))
    fine = g.noise(1.0, detail=3.0, vector=stretched(g, (60.0, 300.0, 300.0)))
    block = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.5, 0.8), 0.5), block, (0.1, 0.095, 0.09))
    col = g.mix(wide, block, (0.012, 0.01, 0.009))
    col = g.mix(g.math("MULTIPLY", crack, 0.9), col, (0.04, 0.02, 0.009))
    bare = g.ramp(g.noise(3.0, detail=5.0, distortion=0.4), 0.74, 0.76)
    fibres = g.noise(1.0, detail=5.0, vector=stretched(g, (5.0, 220.0, 220.0)))
    wood = g.mix(g.ramp(fibres, 0.3, 0.7), (0.07, 0.05, 0.035), (0.17, 0.13, 0.095))
    col = g.mix(bare, col, wood)
    rough = g.mixf(crack, g.mixf(wide, 0.62, 0.95), 0.9)
    rough = g.mixf(bare, rough, 0.85)
    height = g.math("SUBTRACT", g.math("ADD", 0.5, g.math("MULTIPLY", fine, 0.12)), g.math("MULTIPLY", wide, 0.55))
    height = g.mixf(bare, height, g.math("ADD", 0.28, g.math("MULTIPLY", fibres, 0.1)))
    # Ash on the tops
    am = g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.2, 0.8), g.ramp(g.noise(8.0, detail=4.0), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", am, 0.1), col, g.mix(g.ramp(g.noise(150.0), 0.3, 0.7), (0.3, 0.29, 0.275), (0.2, 0.195, 0.185)))
    rough = g.mixf(am, rough, 0.95)
    return col, height, rough


def _silver_surface(g, bs):
    """Weathered bare wood gone silver-grey: long raised grain, deep checks along it, a few knots, pale lichen."""
    fib = g.noise(1.0, detail=5.0, roughness=0.6, vector=stretched(g, (3.5, 130.0, 130.0)))
    fibre = g.ramp(kf._ridged(g, fib), 0.72, 0.97)
    broad = g.noise(2.0, detail=3.0, vector=stretched(g, (0.7, 6.0, 6.0)))
    col = g.mix(g.ramp(broad, 0.3, 0.7), (0.15, 0.14, 0.125), (0.29, 0.275, 0.25))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.35, 0.7), 0.55), col, (0.13, 0.12, 0.105))
    col = g.mix(g.math("MULTIPLY", fibre, 0.4), col, (0.48, 0.46, 0.43))
    check = g.ramp(kf._voronoi(g, 1.0, kf._warped(g, 25.0, 0.003, stretched(g, (1.1 * bs, 20.0 * bs, 20.0 * bs))),
                               feature="DISTANCE_TO_EDGE"), 0.025, 0.0)
    check = g.math("MULTIPLY", check, g.ramp(g.noise(3.0, detail=3.0), 0.35, 0.55))
    col = g.mix(g.math("MULTIPLY", check, 0.9), col, (0.03, 0.026, 0.022))
    stain = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=4.0), 0.58, 0.72), 0.45)
    col = g.mix(stain, col, (0.1, 0.085, 0.07))
    lich = g.math("MULTIPLY", g.ramp(g.noise(10.0, detail=5.0, distortion=0.3), 0.7, 0.74), g.ramp(g.noise(130.0), 0.3, 0.7))
    col = g.mix(g.math("MULTIPLY", lich, 0.8), col, (0.4, 0.43, 0.32))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", fib, 0.4), g.math("MULTIPLY", fibre, 0.3)), g.math("MULTIPLY", check, 0.7))
    rough = g.mixf(check, 0.9, 0.97)
    return col, height, rough


def moss_var(g, mcol):
    """Moss colour that drifts over the surface: darker damp patches, paler dry yellow-green ones."""
    dark = tk.grade(g, mcol, sat=1.1, value=0.5)
    light = tk.grade(g, mcol, sat=0.8, value=1.6)
    c = g.mix(g.ramp(g.noise(2.6, detail=4.0), 0.35, 0.65), dark, mcol)
    return g.mix(g.ramp(g.noise(5.5, detail=3.0), 0.5, 0.7), c, light)


def bark_surface(g, style="forest", moss=0.35, bs=1.0, peel=0.64, snow=0.0, ground=True):
    """(color, height 0..1, roughness) of a trunk's skin as node signals. `moss` 0..2 is the share of the top and
    sides under the moss film (0.35 is the mossy log's thin film), `snow` dusts the up-facing parts."""
    if style == "burnt":
        col, height, rough = _char_surface(g, bs)
    elif style == "bleached":
        col, height, rough = _silver_surface(g, bs)
    else:
        col, height, rough = _bark_core(g, style, bs, peel)
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        lo = 0.62 - 0.3 * moss
        reach = g.math("ADD", g.noise(3.5, detail=5.0), g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.3))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(40.0, detail=3.0), 0.5), 0.12))
        slope = (0.3 - 0.35 * (moss - 0.35), 0.8 - 0.4 * (moss - 0.35))
        stain = g.math("MULTIPLY", g.ramp(ks._normal_z(g), slope[0], slope[1]), g.ramp(reach, lo, lo + 0.08))
        col = g.mix(stain, col, moss_var(g, mcol))
        height = g.mixf(stain, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.5)))
        rough = g.mixf(stain, rough, mrough)
    if snow > 0.0:
        col, height, rough = snow_layer(g, col, height, rough, snow)
    if ground:
        z = g.separate(g.coords())[2]
        col = g.mix(g.math("MULTIPLY", g.ramp(z, G + 0.12, G), 0.6), col, (0.022, 0.018, 0.014))
        rough = g.mixf(g.ramp(z, G + 0.1, G), rough, 0.7)
    return tk.grade(g, col, sat=0.95, value=0.95), height, rough


def bark_mat(name, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = bark_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, RELIEF))


def moss_shell_mat(name, **kw):
    """The moss cushions: kf.moss_layer's clumps, giving way toward the rim of each patch (attribute t runs 0 at the
    rim to 1 inside) to exactly the trunk's own surface, so the patch's edge is drawn by the texture."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    bcol, bh, brough = bark_surface(g, **kw)
    mcol, mh, mrough, _ = kf.moss_layer(g)
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.3), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(14.0, detail=5.0), 0.5), 0.6))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.5))
    cover = g.ramp(reach, 0.36, 0.5)
    col = g.mix(cover, bcol, tk.grade(g, moss_var(g, mcol), sat=0.95, value=0.95))
    height = g.mixf(cover, bh, g.math("ADD", 0.25, g.math("MULTIPLY", mh, 0.75)))
    rough = g.mixf(cover, brough, mrough)
    if kw.get("snow", 0.0) > 0.0:
        col, height, rough = snow_layer(g, col, height, rough, kw["snow"])
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, RELIEF))


def end_grain(name, kind="fresh", ring=0.012):
    """Cut or split end grain. The attribute `t` must hold each vertex's distance from the cut's axis in meters (rings
    are drawn from it), `ring` is the period of the main rings. kinds: fresh, rot (dark punk), burnt (char over brown
    wood), bleached (silver)."""
    mat, g = tk.new_material(name)
    r = ks._attr(g, "t")
    k = math.tau / ring
    wob = g.math("ADD", g.math("MULTIPLY", g.noise(5.0, detail=3.0), 3.0), g.math("MULTIPLY", g.noise(23.0, detail=3.0), 0.9))
    main = g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, k), wob))
    rings = g.ramp(main, -0.4, 0.6)
    late = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, k * 0.31), g.math("MULTIPLY", g.noise(4.0), 2.0))), 0.5, 0.95)
    fib = g.noise(1.0, detail=4.0, vector=stretched(g, (5.0, 90.0, 90.0)))
    radial = g.noise(1.0, detail=3.0, vector=stretched(g, (40.0, 40.0, 40.0)))
    if kind == "rot":
        col = g.mix(g.ramp(fib, 0.3, 0.7), (0.035, 0.022, 0.014), (0.1, 0.06, 0.035))
        col = g.mix(g.math("MULTIPLY", rings, 0.3), col, (0.02, 0.012, 0.008))
        rough = 0.95
    elif kind == "hollow":
        col = g.mix(g.ramp(fib, 0.3, 0.7), (0.012, 0.008, 0.005), (0.04, 0.026, 0.016))
        col = g.mix(g.math("MULTIPLY", rings, 0.2), col, (0.006, 0.004, 0.003))
        rough = 0.95
    elif kind == "burnt":
        col = g.mix(g.ramp(fib, 0.3, 0.7), (0.025, 0.02, 0.016), (0.07, 0.05, 0.035))
        col = g.mix(g.math("MULTIPLY", rings, 0.35), col, (0.012, 0.01, 0.009))
        rough = 0.9
    elif kind == "bleached":
        col = g.mix(rings, (0.26, 0.245, 0.22), (0.46, 0.44, 0.4))
        col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.55, 0.75), 0.5), col, (0.14, 0.13, 0.115))
        col = g.mix(g.math("MULTIPLY", late, 0.5), col, (0.17, 0.155, 0.135))
        rough = 0.9
    else:
        col = g.mix(rings, (0.24, 0.18, 0.12), (0.47, 0.385, 0.27))
        col = g.mix(g.math("MULTIPLY", late, 0.55), col, (0.17, 0.11, 0.065))
        col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.55, 0.75), 0.5), col, (0.12, 0.08, 0.05))
        # Fine radial checks opening from the middle, grey weathering at the very surface
        col = g.mix(g.math("MULTIPLY", g.ramp(radial, 0.7, 0.9), 0.4), col, (0.05, 0.035, 0.025))
        rough = 0.85
    height = g.math("ADD", g.math("MULTIPLY", rings, 0.6), g.math("MULTIPLY", late, 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", fib, 0.25))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.0025))


def fungus_top(name="FungusTop"):
    """Bracket fungus cap: concentric growth zones of browns and greys (t runs from the trunk to the rim), each zone a
    low ridge, a velvety grain, a green tinge of algae on the old zones by the trunk, a pale growing rim."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    wob = g.math("ADD", g.math("MULTIPLY", g.noise(12.0), 3.0), g.math("MULTIPLY", g.noise(70.0, detail=3.0), 0.6))
    bands = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 34.0), wob))
    zone = g.ramp(bands, -0.6, 0.6)
    col = g.mix(zone, (0.14, 0.065, 0.03), (0.42, 0.25, 0.1))
    grey = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 11.0), wob)), 0.45, 0.9)
    col = g.mix(g.math("MULTIPLY", grey, 0.55), col, (0.2, 0.18, 0.15))
    col = g.mix(g.ramp(t, 0.55, 0.0), col, (0.07, 0.045, 0.03))
    algae = g.math("MULTIPLY", g.ramp(t, 0.5, 0.1), g.ramp(g.noise(25.0, detail=4.0), 0.45, 0.65))
    col = g.mix(g.math("MULTIPLY", algae, 0.6), col, (0.07, 0.1, 0.035))
    velvet = g.noise(450.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(velvet, 0.6, 0.25), 0.3), col, (0.05, 0.035, 0.025))
    col = g.mix(g.ramp(t, 0.84, 0.97), col, (0.72, 0.62, 0.44))
    height = g.math("ADD", g.math("MULTIPLY", g.math("POWER", zone, 0.5), 0.5), g.math("MULTIPLY", velvet, 0.15))
    return tk.finish(mat, g, col, 0.0, 0.86, g.bump(height, 1.0, 0.0012))


def soil_surface(g, moss=0.15, rooty=1.0, stony=1.0, scale=1.0, dark=1.0):
    """Forest soil as it shows in a root plate or a dug pit: dark crumbly clods a few cm across with deep gaps, pale
    mineral subsoil streaks, grit and pebbles, tan rootlets threaded through, damp darker patches, moss gathering
    on the up-facing parts. Returns (color, height 0..1, roughness)."""
    co = kf._warped(g, 9.0 * scale, 0.03)
    d1, r1 = kf._cells(g, 14.0 * scale, co)
    d2, r2 = kf._cells(g, 55.0 * scale, kf._warped(g, 40.0 * scale, 0.006))
    tone = g.noise(2.5 * scale, detail=4.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.036, 0.024, 0.016), (0.078, 0.054, 0.035))
    col = g.mix(g.math("MULTIPLY", r1, 0.55), col, (0.105, 0.072, 0.047))
    sub = g.math("MULTIPLY", g.ramp(g.noise(5.0 * scale, detail=5.0, distortion=0.4), 0.62, 0.72), 0.7)
    col = g.mix(sub, col, (0.16, 0.12, 0.082))
    crumb = g.math("MULTIPLY", g.ramp(d2, 0.28, 0.08), g.ramp(r2, 0.3, 0.7))
    col = g.mix(g.math("MULTIPLY", crumb, 0.4), col, (0.02, 0.014, 0.01))
    d3, r3 = kf._cells(g, 150.0 * scale)
    pebble = g.math("MULTIPLY", g.ramp(d3, 0.2, 0.1), g.ramp(r3, 0.7, 0.78))
    pebble = g.math("MULTIPLY", pebble, stony)
    col = g.mix(g.math("MULTIPLY", pebble, 0.85), col, g.mix(g.ramp(r3, 0.78, 1.0), (0.2, 0.19, 0.17), (0.3, 0.26, 0.2)))
    crev = g.ramp(d1, 0.38, 0.75)
    col = g.mix(g.math("MULTIPLY", crev, 0.65), col, (0.012, 0.009, 0.006))
    damp = g.math("MULTIPLY", g.ramp(g.noise(4.0 * scale, detail=4.0), 0.55, 0.75), 0.4)
    col = g.mix(damp, col, (0.018, 0.013, 0.009))
    root = g.math("MULTIPLY", g.ramp(kf._ridged(g, g.noise(38.0 * scale, detail=3.0, distortion=1.2)), 0.8, 0.96), rooty)
    col = g.mix(g.math("MULTIPLY", root, 0.85), col, g.mix(g.ramp(g.noise(80.0), 0.3, 0.7), (0.19, 0.14, 0.09), (0.12, 0.085, 0.055)))
    height = g.math("ADD", g.math("SUBTRACT", 1.0, g.ramp(d1, 0.0, 0.7)), g.math("MULTIPLY", crumb, 0.25))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", pebble, 0.9), g.math("MULTIPLY", root, 0.35)))
    height = g.math("MULTIPLY", height, 0.55)
    rough = g.mixf(damp, 0.93, 0.8)
    rough = g.mixf(pebble, rough, 0.75)
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        nz = ks._normal_z(g)
        reach = g.math("ADD", g.math("MULTIPLY", g.ramp(nz, -0.2, 0.8), 0.45),
                       g.math("MULTIPLY", g.math("SUBTRACT", g.noise(3.0, detail=5.0), 0.5), 0.9))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.3))
        cover = g.ramp(reach, 0.62 - 0.35 * moss, 0.7 - 0.35 * moss)
        col = g.mix(cover, col, tk.grade(g, mcol, sat=0.95, value=0.95))
        height = g.mixf(cover, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.6)))
        rough = g.mixf(cover, rough, mrough)
    return tk.grade(g, col, sat=0.95, value=0.95 * dark), height, rough


def soil_mat(name, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = soil_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.012))


def soil_moss_mat(name, **kw):
    """Moss cushions over soil (attribute t 0 at the rim to 1 inside), as granite_moss does for rock."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    bcol, bh, brough = soil_surface(g, **kw)
    mcol, mh, mrough, _ = kf.moss_layer(g)
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.3), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(14.0, detail=5.0), 0.5), 0.6))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.5))
    cover = g.ramp(reach, 0.36, 0.5)
    col = g.mix(cover, bcol, tk.grade(g, mcol, sat=0.95, value=0.95))
    height = g.mixf(cover, bh, g.math("ADD", 0.25, g.math("MULTIPLY", mh, 0.75)))
    rough = g.mixf(cover, brough, mrough)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.012))


def root_mat(name, style="fresh"):
    """A root: reddish-brown to grey bark that peels to pale wood, caked with dirt in patches."""
    mat, g = tk.new_material(name)
    col, height, rough = _bark_core(g, "fresh" if style == "fresh" else "forest", 0.7, 0.58)
    dirt = g.math("MULTIPLY", g.ramp(g.noise(12.0, detail=4.0), 0.4, 0.62), 0.85)
    col = g.mix(dirt, col, g.mix(g.ramp(g.noise(90.0, detail=3.0), 0.3, 0.7), (0.05, 0.034, 0.022), (0.1, 0.07, 0.045)))
    rough = g.mixf(dirt, rough, 0.95)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, RELIEF))


def fungus_materials():
    return fungus_top("FungusTop"), kf.pores("FungusPores", (0.72, 0.65, 0.5), (0.5, 0.43, 0.31), scale=900.0)


def mushroom_materials():
    cap = kf.bolete_cap("MushCap", (0.085, 0.032, 0.011), (0.2, 0.098, 0.038), (0.46, 0.37, 0.25))
    pores = kf.pores("MushPores", (0.66, 0.6, 0.26), (0.45, 0.4, 0.14))
    stem = kf.reticulate("MushStem", (0.5, 0.4, 0.26), (0.76, 0.68, 0.52), (0.86, 0.83, 0.74), scale=230.0, soil=(0.05, 0.035, 0.02))
    return cap, pores, stem


# ================================================================ the trunk

def _catmull(pts, u):
    n = len(pts)
    i = max(0, min(int(u), n - 2))
    f = u - i
    p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
    return 0.5 * ((2.0 * p1) + (-p0 + p2) * f + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f * f + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * f ** 3)


class Trunk:
    """A tapered trunk along a centerline: `ctrl` control points (Catmull-Rom) with a radius each. Rings every `step`
    meters, `sides` round. The bark surface has lumps, butt flare with root buttresses (`flare` x radius over
    `flare_len` m), and knots ((s, angle, size) bumps; angle 0 = +y, 90 = up). `surface(s, a)` is a point on it."""

    def __init__(self, ctrl, radii, seed=0, sides=24, step=0.3, flare=0.0, flare_len=1.2, knots=(), lump=0.07, buttress=5):
        self.ctrl = [Vector(p) for p in ctrl]
        self.cr = [Vector((r, 0.0, 0.0)) for r in radii]
        self.seed = seed
        self.sides = sides
        self.flare, self.flare_len, self.knots, self.lump, self.buttress = flare, flare_len, list(knots), lump, buttress
        n = len(self.ctrl)
        pts, us = [], []
        N = max(60, n * 60)
        for i in range(N + 1):
            u = i / N * (n - 1)
            pts.append(_catmull(self.ctrl, u))
            us.append(u)
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + (pts[i] - pts[i - 1]).length)
        self.cum, self.pts, self.us = cum, pts, us
        self.length = cum[-1]
        self.ph = random.Random(seed).uniform(0.0, 6.28)
        count = max(2, int(math.ceil(self.length / step)))
        self.ss = [self.length * i / count for i in range(count + 1)]
        self.rings = []

    def _u(self, s):
        s = clamp(s, 0.0, self.length)
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        f = (s - self.cum[lo]) / max(1e-9, self.cum[hi] - self.cum[lo])
        return self.us[lo] + (self.us[hi] - self.us[lo]) * f

    def frame(self, s):
        """(center, tangent, side, up, radius) at arc length s; `side` is horizontal (+y for a trunk along +x)."""
        u = self._u(s)
        n = len(self.ctrl) - 1
        c = _catmull(self.ctrl, u)
        T = (_catmull(self.ctrl, min(n, u + 0.02)) - _catmull(self.ctrl, max(0.0, u - 0.02))).normalized()
        S = UP.cross(T)
        if S.length < 1e-3:
            S = Vector((0.0, 1.0, 0.0))
        S.normalize()
        U = T.cross(S).normalized()
        r = _catmull(self.cr, u).x
        return c, T, S, U, r

    def _bump(self, s, a, r):
        q = Vector((s * 2.2 + self.seed * 3.1, math.cos(a) * r * 7.0, math.sin(a) * r * 7.0))
        k = 1.0 + self.lump * mn.noise(q) + self.lump * 0.4 * mn.noise(q * 4.0) + self.lump * 0.15 * mn.noise(q * 11.0)
        for ks_, ka, size in self.knots:
            da = math.atan2(math.sin(a - ka), math.cos(a - ka))
            k += size * math.exp(-((s - ks_) / (0.35 * r + 0.05)) ** 2 - (da / 0.4) ** 2)
        if self.flare > 0.0:
            e = math.exp(-s / (self.flare_len * 0.45))
            lobes = 0.55 + 0.45 * math.cos(self.buttress * a + self.ph + 2.0 * mn.noise(Vector((s * 0.5, self.seed, 0.0))))
            k += self.flare * e * lobes
        return k

    def surface(self, s, a, scale=1.0):
        c, T, S, U, r = self.frame(s)
        n = S * math.cos(a) + U * math.sin(a)
        return c + n * r * self._bump(s, a, r) * scale, n

    def build(self, b, bark, under=None, ragged=(False, False), rnd=None, lod=2, keep_under_ground=False):
        """Meshes the trunk into Builder `b`: bark (and `under`, a cheap material, for faces looking down). Returns
        self. `ragged` tears the two end rings off at different lengths."""
        rnd = rnd or random.Random(self.seed)
        m = b.mesh(bark)
        mu = b.mesh(under) if under is not None else None
        m.begin((0.0, 0.0, G))
        if mu is not None:
            mu.begin((0.0, 0.0, G))
        jag = [[rnd.uniform(-0.03, 0.04) + (rnd.uniform(0.1, 0.22) if rnd.random() < 0.25 else 0.0) for _ in range(self.sides)] for _ in range(2)]
        self.rings = []
        last = len(self.ss) - 1
        for i, s in enumerate(self.ss):
            c, T, S, U, r = self.frame(s)
            row = []
            for k in range(self.sides):
                a = k / self.sides * math.tau
                p, n = self.surface(s, a)
                if ragged[0] and i == 0:
                    p = p + T * (jag[0][k] * r)
                if ragged[1] and i == last:
                    p = p - T * (jag[1][k] * r)
                row.append([p, n, None, None])
            self.rings.append(row)
        b.lod = lod
        for i in range(last):
            for k in range(self.sides):
                k1 = (k + 1) % self.sides
                quad = (self.rings[i][k], self.rings[i][k1], self.rings[i + 1][k1], self.rings[i + 1][k])
                if not keep_under_ground and max(q[0].z for q in quad) < G - 0.02:
                    continue
                nz = sum(q[1].z for q in quad) / 4.0
                mesh = mu if (mu is not None and nz < -0.35) else m
                vs = []
                for q in quad:
                    if mesh is m:
                        if q[2] is None:
                            q[2] = m.v(q[0], 0.5 + 0.5 * q[1].z)
                        vs.append(q[2])
                    else:
                        if q[3] is None:
                            q[3] = mu.v(q[0], 0.5)
                        vs.append(q[3])
                mesh.f(vs, True)
        b.lod = 0
        return self

    def cap(self, b, wood, which, kind="flat", rnd=None, hollow=None, rot=None):
        """The trunk's end at ring 0 (which=0) or the last ring: `flat` a clean saw cut, `break` a sunken splintered
        face with splinters sticking out. Needs build() first. The `t` attribute holds the distance from the axis
        in meters, for end_grain."""
        rnd = rnd or random.Random(self.seed + which)
        row = self.rings[0 if which == 0 else -1]
        s = self.ss[0 if which == 0 else -1]
        c, T, S, U, r = self.frame(s)
        out = -T if which == 0 else T
        mw = b.mesh(wood)
        mw.begin(c)
        rim = [mw.v(q[0], (q[0] - c).length) for q in row]
        n = self.sides
        if kind == "flat":
            cv = mw.v(c + out * 0.004, 0.0)
            for k in range(n):
                mw.f((cv, rim[(k + 1) % n], rim[k]) if which == 0 else (cv, rim[k], rim[(k + 1) % n]), False)
            return
        inner = []
        for k in range(n):
            a = (k + 0.5) / n * math.tau
            sp = rnd.uniform(-0.05, 0.1) + (rnd.uniform(0.15, 0.45) if rnd.random() < 0.22 else 0.0)
            p, nn = self.surface(s, a, 0.5)
            inner.append(mw.v(p - out * (r * 0.12) + out * (sp * r), (p - c).length))
        cv = mw.v(c - out * (r * 0.1), 0.0)
        for k in range(n):
            k1 = (k + 1) % n
            if which == 0:
                mw.f((cv, inner[k1], inner[k]), False)
                mw.f((inner[k], inner[k1], rim[k1], rim[k]), False)
            else:
                mw.f((cv, inner[k], inner[k1]), False)
                mw.f((inner[k], rim[k], rim[k1], inner[k1]), False)

    def capsules(self, spacing=1.6, shrink=0.84, s0=0.0, s1=None, rmin=0.09, floor=G - 0.5):
        """Collider lines: a chain of capsules down the trunk, each 0.84 of the radius so it lies inside the bumpy
        bark. Returns ["capsule x1 y1 z1 x2 y2 z2 r"]."""
        s1 = self.length if s1 is None else s1
        count = max(1, int(math.ceil((s1 - s0) / spacing)))
        lines = []
        for i in range(count):
            a, b = s0 + (s1 - s0) * i / count, s0 + (s1 - s0) * (i + 1) / count
            r = min(self.frame(a)[4], self.frame(b)[4], self.frame((a + b) / 2)[4]) * shrink
            if r < rmin:
                continue
            ca, cb = self.frame(a + r)[0], self.frame(b - r)[0] if b - r > a + r else self.frame(b)[0]
            if i == 0 and s0 <= 0.0:
                ca = self.frame(r)[0]
            lines.append("capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (ca.x, ca.y, ca.z, cb.x, cb.y, cb.z, r))
        return lines


def moss_depth(s, a, seed=0, amount=0.35, thick=0.022, ends=(0.0, 0.0)):
    top = math.sin(a)
    t0 = 0.05 - 0.55 * (amount - 0.35)
    if top < t0:
        return 0.0
    q = Vector((s * 2.4 + 7.0 + seed, math.cos(a) * 1.8, top * 1.8))
    mask = min(1.0, (top - t0) / 0.45) * (0.55 + 0.8 * mn.noise(q) + 0.25 * mn.noise(q * 3.0)) + 0.5 * max(0.0, amount - 0.35)
    d = clamp((mask - 0.42) / 0.3)
    return d * (0.4 * thick + thick * max(0.0, 0.5 + 0.7 * mn.noise(q * 6.0)))


def moss_cover(b, tr, mat, amount=0.35, thick=0.022, seed=0, fade=0.0):
    """Lumpy moss cushions over the trunk's top. `fade` (m) thins them toward the trunk's two ends."""
    m = b.mesh(mat)
    m.begin((0.0, 0.0, G))
    shell = {}
    last = len(tr.ss) - 1

    def depth(i, k):
        s = tr.ss[i]
        d = moss_depth(s, k / tr.sides * math.tau, seed, amount, thick)
        if fade > 0.0:
            d *= clamp(min(s, tr.length - s) / fade)
        return d

    def vert(i, k):
        if (i, k) not in shell:
            p, n, _, _ = tr.rings[i][k]
            d = depth(i, k)
            c = tr.frame(tr.ss[i])[0]
            out = (p - c).normalized()
            shell[(i, k)] = m.v(p + out * (d + 0.0015 if d > 0.0 else -0.006), min(1.0, d / (0.55 * thick)))
        return shell[(i, k)]

    for i in range(last):
        for k in range(tr.sides):
            k1 = (k + 1) % tr.sides
            corners = ((i, k), (i, k1), (i + 1, k1), (i + 1, k))
            if max(depth(a, c) for a, c in corners) < 0.004:
                continue
            if max(tr.rings[a][c][0].z for a, c in corners) < G + 0.03:
                continue
            m.f([vert(a, c) for a, c in corners], True)


# ================================================================ limbs, foliage, small things

def tube_broken(b, bark, wood, pts, radii, sides, rnd, jag=1.6):
    """A bark tube along `pts` whose end is torn off ragged, with a pale splintered face (material `wood`, whose end
    grain reads the attribute t as the radius) closing it."""
    rings = ks.tube(b, bark, pts, radii, sides=sides, cap=False, jag=jag, rnd=rnd)
    if wood is not None and len(rings[-1]) > 2:
        mw = b.mesh(wood)
        mw.begin(pts[-1])
        rimv = [mw.v(v.co.copy(), radii[-1]) for v in rings[-1]]
        cv = mw.v(pts[-1] - (pts[-1] - pts[-2]).normalized() * 0.015, 0.0)
        for k in range(sides):
            mw.f((cv, rimv[k], rimv[(k + 1) % sides]), False)
    return rings


def limb(b, bark, wood, p, d, length, r0, r1, rnd, sides=6, bend=(0.0, 0.0, 0.0), broken=True, kink=0.0, floor=G - 0.05):
    """A branch or a snapped stub from `p` along `d`: a bark tube tapering r0 to r1, ending in a ragged break with a
    pale splintered face (when `broken`). Returns the polyline of its centerline (its tip is the last point)."""
    d = Vector(d).normalized()
    pts = []
    n = max(3, int(length / 0.35) + 2)
    cur = Vector(p)
    for i in range(n):
        pts.append(cur.copy())
        step = d * (length / (n - 1))
        cur = cur + step
        d = (d + Vector(bend) * (length / (n - 1)) + Vector((rnd.gauss(0, kink), rnd.gauss(0, kink), rnd.gauss(0, kink)))).normalized()
    for q in pts:
        q.z = max(q.z, floor)
    radii = [r0 + (r1 - r0) * (i / (n - 1)) ** 0.9 for i in range(n)]
    if broken:
        tube_broken(b, bark, wood, pts, radii, sides, rnd)
    else:
        ks.tube(b, bark, pts, radii, sides=sides, cap=True)
    return pts


def needles(b, mat, branch_pts, rnd, spacing=0.06, length=0.075, width=0.012, spread=1.0, skip=0.25):
    """Conifer foliage on a twig polyline: little tufts of needle cards along it, all round, swept forward."""
    pts = [Vector(p) for p in branch_pts]
    tot = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
    count = int(tot / spacing)
    for j in range(count):
        s = (j + rnd.uniform(0.0, 1.0)) / count
        if s < skip:
            continue
        idx = min(len(pts) - 2, int(s * (len(pts) - 1)))
        f = s * (len(pts) - 1) - idx
        p = pts[idx].lerp(pts[idx + 1], f)
        tan = (pts[idx + 1] - pts[idx]).normalized()
        _, u, v = ks.basis(tan)
        for k in range(rnd.choice((3, 4))):
            a = rnd.uniform(0, math.tau)
            out = u * math.cos(a) + v * math.sin(a)
            d = (tan * 0.7 + out * spread).normalized()
            ks.leaf(b, mat, p, d, length * rnd.uniform(0.8, 1.25), width, bend=rnd.uniform(0.0, 0.25), fold=0.3, profile="lance",
                    normal=UP)


def shelf_tiers(b, top, pores, tr, rnd, spots, rad=(0.07, 0.11), thick=0.3):
    """Tiers of bracket fungus up a trunk's side: spots = [(s, angle (deg), tiers)]."""
    for s, ang, tiers in spots:
        for j in range(tiers):
            a = math.radians(ang + rnd.uniform(-8, 8) + 15 * j)
            x = s + rnd.uniform(-0.08, 0.08)
            p, n = tr.surface(x, a)
            out = Vector((n.x, n.y, 0.0))
            if out.length < 0.2:
                continue
            rr = rnd.uniform(*rad) * (1.0 - 0.15 * j)
            b.lod = 1 if rr < 0.065 else 0
            ks.shelf_fungus(b, top, pores, p - out.normalized() * 0.02, out, rr, rnd, thickness=rr * thick, depth=0.85, segs=8)
            b.lod = 0


def mushroom(b, cap, pores, stem, base, height, radius, rnd, lean=0.1):
    """A small bolete: tapered stem, domed cap with pores beneath (3 rings of 9 around)."""
    base = Vector(base)
    top = base + Vector((rnd.uniform(-lean, lean) * height, rnd.uniform(-lean, lean) * height, height))
    pts = [base, base.lerp(top, 0.5), top]
    saved = b.lod
    b.lod = 1 if radius < 0.03 else 0
    ks.tube(b, stem, pts, [radius * 0.38, radius * 0.3, radius * 0.27], sides=6, cap=False)
    mc, mp = b.mesh(cap), b.mesh(pores)
    mc.begin(top)
    mp.begin(top)
    prof = [(0.0, 0.0, 0.0), (0.4, -0.12, 0.25), (0.8, -0.38, 0.6), (1.0, -0.62, 1.0)]
    rows = []
    sides = 9
    ph = rnd.uniform(0, math.tau)
    for r_, z_, t_ in prof:
        if r_ == 0.0:
            rows.append([mc.v(top + Vector((0, 0, radius * 0.45)), 0.0)])
        else:
            rows.append([mc.v(top + Vector((math.cos(ph + k / sides * math.tau) * r_ * radius * rnd.uniform(0.92, 1.08),
                                            math.sin(ph + k / sides * math.tau) * r_ * radius * rnd.uniform(0.92, 1.08),
                                            z_ * radius + radius * 0.45 * (1.0 - r_) )), t_) for k in range(sides)])
    for A, B_ in zip(rows, rows[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            if len(A) == 1:
                mc.f((A[0], B_[k1], B_[k]), True)
            else:
                mc.f((A[k], A[k1], B_[k1], B_[k]), True)
    rim = rows[-1]
    under = [mp.v(Vector((v.co.x, v.co.y, v.co.z + 0.0005)), 0.5) for v in rim]
    cv = mp.v(top + Vector((0, 0, -radius * 0.17)), 0.5)
    for k in range(sides):
        mp.f((cv, under[k], under[(k + 1) % sides]), True)
    b.lod = saved


def ferns(b, mat, spots, rnd, big=1.0):
    """spots: [(x, y, z, away_degrees)]."""
    for x, y, z, away in spots:
        ks.fern(b, mat, (x, y, z), rnd, fronds=rnd.randint(6, 8), length=(0.4 * big, 0.62 * big), pinnae=13, pinna_len=0.09 * big,
                pinna_w=0.024 * big, away=away, arc=rnd.uniform(150, 210), tilt=(18.0, 52.0), bend=(0.35, 0.7), far=(0.4, 1.4))


def litter(b, mats, count, rnd, area, keep=lambda x, y: True):
    """Fallen leaves on the ground over area = (x0, x1, y0, y1)."""
    b.lod = 1
    n = 0
    tries = 0
    while n < count and tries < count * 20:
        tries += 1
        x, y = rnd.uniform(area[0], area[1]), rnd.uniform(area[2], area[3])
        if not keep(x, y):
            continue
        n += 1
        a = rnd.uniform(0, math.tau)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.05, 0.12)))
        ks.leaf(b, rnd.choice(mats), (x, y, G + 0.004), d, rnd.uniform(0.06, 0.09), rnd.uniform(0.035, 0.05), bend=-0.1, fold=0.3,
                profile="oval", roll=rnd.uniform(-20, 20))
    b.lod = 0


def litter_materials():
    return [nk.plant("Litter", (0.16, 0.09, 0.04), (0.1, 0.06, 0.03), vary=0.4),
            nk.plant("LitterGold", (0.3, 0.17, 0.05), (0.2, 0.09, 0.03), vary=0.4)]


# ================================================================ previews

def preview(name, model, views, floor=3.0):
    """Renders `views` ([(label, camera position, target)]) on the preview stage (floor scaled `floor` times), with the
    1.8 m figure moved to the first view's foreground."""
    tk.preview_stage()
    fl = bpy.data.objects.get("Floor")
    if fl is not None:
        fl.scale = (floor, floor, 1.0)
    for n in ("ScaleFigure", "ScaleHead"):
        o = bpy.data.objects.get(n)
        if o is not None:
            o.location = (-1.1 + 3.0, -0.6 - 3.0, 0.0)
    for label, loc, tgt in views:
        tk.render(tk.camera(name + label, loc, tgt, lens=40), os.path.join(PREV, "%s_%s.png" % (name, label)), samples=40)


PREV = "."


def set_preview_dir(path):
    global PREV
    PREV = path
    os.makedirs(path, exist_ok=True)


def only():
    """Feature names after the two path arguments (all when none)."""
    return sys.argv[sys.argv.index("--") + 3:]


def atlas_size(default=2048):
    return int(os.environ.get("LK_SIZE", default))


def place(bm, dx=0.0, dy=0.0, dz=0.0):
    bmesh.ops.translate(bm, vec=(dx, dy, dz), verts=bm.verts)
    return bm


# ================================================================ saplings and snow

def fir_sapling(b, needle, bark, base, height, rnd, lean=0.08, droop=0.0, branches=4, spread=1.0, dead=None):
    """A young fir or hemlock seedling: a thin leader, whorls of short branches in a cone, needle tufts along them.
    `droop` > 0 bends the branches down (hemlock). `dead` is an optional brown needle material for a few twigs."""
    base = Vector(base)
    up = Vector((rnd.uniform(-lean, lean), rnd.uniform(-lean, lean), 1.0)).normalized()
    sc = max(0.5, min(1.4, height))
    stem = [base + up * height * f + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 0.004 * height * f for f in (0.0, 0.34, 0.67, 1.0)]
    r0 = 0.004 + height * 0.014
    ks.tube(b, bark, stem, [r0, r0 * 0.75, r0 * 0.5, 0.0015], sides=4, cap=True)
    n = max(3, int(height / 0.11))
    for i in range(n):
        f = 0.1 + 0.85 * i / max(1, n - 1)
        c = base + up * height * f
        cone = (1.0 - f) ** 0.9 * 0.46 + 0.05
        ln = height * cone * spread
        a0 = rnd.uniform(0, math.tau)
        for k in range(branches):
            a = a0 + k / branches * math.tau + rnd.uniform(-0.25, 0.25)
            out = Vector((math.cos(a), math.sin(a), 0.0))
            lift = 0.28 - 0.5 * (1.0 - f) - droop
            d = (out + UP * lift).normalized()
            pts = [c, c + d * ln * 0.5 + UP * (-0.02 * droop * ln), c + d * ln + UP * (-droop * ln * 0.45)]
            ks.tube(b, bark, pts, [0.0032 * sc, 0.0024 * sc, 0.0008], sides=3, cap=True)
            mat = dead if (dead is not None and rnd.random() < 0.08) else needle
            needles(b, mat, pts, rnd, spacing=0.026 * sc, length=0.07 * sc, width=0.013 * sc, spread=1.0, skip=0.15)
    tip = base + up * height
    for k in range(5):
        a = k / 5 * math.tau
        ks.leaf(b, needle, tip, Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, 1.0)), 0.06 * sc, 0.011 * sc, bend=0.05, fold=0.3,
                profile="lance", normal=UP)


def snow_layer(g, col, height, rough, snow):
    """Dusts up-facing parts with snow (amount 0..1.2), broken up by noise."""
    mask = g.math("MULTIPLY", g.ramp(ks._normal_z(g), 0.25, 0.7), g.ramp(g.noise(11.0, detail=4.0), 0.5 - 0.3 * snow, 0.62 - 0.3 * snow))
    mask = g.math("MULTIPLY", mask, g.ramp(g.noise(60.0, detail=3.0), 0.1, 0.35))
    col = g.mix(mask, col, SNOW)
    height = g.mixf(mask, height, g.math("ADD", 0.55, g.math("MULTIPLY", g.noise(90.0), 0.1)))
    rough = g.mixf(mask, rough, 0.6)
    return col, height, rough


# ================================================================ export with tight UV packing

def export(name, pieces, bodies, out_dir, size=2048, density=None, voxel=0.16, extra=(), rect=True, limit=120, uv_margin=0.0006,
           coarse=0.3, probes=(), boxes=None):
    """fk.export, but the UV islands are packed with a 1 px margin: a feature with thousands of leaf and needle
    cards wastes most of the atlas on the default margin round every island."""
    boxes_ = list(boxes or []) + (fk.voxel_boxes(bodies, voxel, 0.03, limit=limit) if bodies else [])
    folder = os.path.join(out_dir, name)
    os.makedirs(folder, exist_ok=True)
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("Bake")
    atlas = tk.triangulate(tk.join(pieces, name))
    nk.weighted_uvs(atlas, density or {}, margin=uv_margin)
    nk.texel_report(atlas, size)
    paths = tk.bake_atlas(atlas, folder, name, size=size)
    baked = tk.baked_material(name, paths)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    lod = atlas.copy()
    lod.data = atlas.data.copy()
    lod.name = name + "_LOD1"
    tk.link(lod)
    lod = ks._far_lod(lod, coarse)
    ks._strip(atlas)
    ks._strip(lod)
    tk.export_fbx([atlas, lod], os.path.join(folder, name + ".fbx"))
    print("[%s] %d triangles, LOD1 %d" % (name, ks.triangles([atlas]), ks.triangles([lod])))
    lod.hide_render = True
    fk.write_colliders(out_dir, name, boxes_, size, probes, extra, rect)
    return atlas
