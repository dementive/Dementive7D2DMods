"""Quaking aspen (Populus tremuloides) in summer, on treekit.py (birch.py is the worked example; TREES.md the rules).

Aspen grows in clone STANDS: dozens of straight, slender trunks of mixed ages rising together from one root system, so
each variant here is itself a stand, not a single tree:
  Aspen01  a dense clump of ten trunks 6 to 16 m (a 4 to 5 m footprint),
  Aspen02  a sparser stand of six trunks leaning toward the light, 8.5 to 15 m,
  Aspen03  one mature trunk about 15.5 m,
  Aspen04  a young thicket of nine whips 3 to 6 m;
  AspenSapling is the planted seed's seedling.
Smooth chalky greenish-white to cream bark with a powdery bloom and a faint green cast, small diamond lenticels, black
horizontal branch scars with raised lips and black knot "eyes", and rough ridged black bark at the foot of old trunks.
A high, small, narrow rounded crown of a few ascending limbs on a long clear trunk. Round-to-heart-shaped, finely
toothed leaves 5 to 7 cm on long petioles, glossy mid-green above and paler beneath, which the Unity builder flutters
hard (NatureTreeBuilder FlutterScales).

    blender -b --factory-startup --python trees/aspen.py -- <unity trees folder> <preview folder> [step]

with absolute paths `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`.
Steps as birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`, plus `skeleton` (the trees
without leaves, previews only). Writes Trees/Aspen/, the Aspen lines of trees.txt and trunks.txt, and the previews.
Built at its size in game (the Unity builder scales only the birch).
"""
import math
import os
import random
import sys

import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import treekit as tr  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
TREES, PREVIEWS = args[0], args[1]
STEPS = args[2] if len(args) > 2 else "all"
FOLDER = os.path.join(TREES, "Aspen")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# AspenBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (75 cm on a 12 cm trunk), so
# its texels stay square on every branch: about 54 px per cm on a 12 cm trunk. AspenBarkFoot: the same mapping, the
# white bark with the rough black foot drawn over its lower rows (as birch's). AspenBarkTwig: 512 x 1024.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 12.0  # cm: the trunk the bark is drawn for
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TILE = K * R_DESIGN / 100.0
TWIST = 0.31
GROUND_V = 0.1
JOIN_V = 0.93
FOOT_END = 0.86
BARK_MEAN = (170, 173, 152)  # greener and creamier than birch's (180, 176, 168)
LEAF_MEAN = (80, 104, 52)
TWIG_R = 0.010
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "foot": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST, floor=0.005),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    if br.level == 0 and "young" not in br.tags and br.turns(s) / K + br.v0 < JOIN_V:
        return "foot"
    return "bark"


def chevron(r, w, t, droop=0.4, rag=0.35):
    """A dark arc scar (an inverted V with drooping arms) `w` pixels across, `t` thick at the apex, thinning outward,
    its edge ragged, with the swollen collar under its apex."""
    kw = (int(w) + 9) | 1
    kh = (int(w * 0.5 * droop + t * 2.5) + 9) | 1
    X, Y = np.meshgrid(np.arange(kw) - (kw - 1) * 0.5, np.arange(kh, dtype=float))
    u = np.abs(X) / (w * 0.5)
    apex = kh - 4.0 - t * 0.6
    yc = apex - w * 0.5 * droop * np.clip(u, 0.0, 1.0) ** 1.35
    noise = tr.blur(r.standard_normal((kh, kw)), 1.2)
    noise /= noise.std() + 1e-9
    ht = t * 0.5 * np.clip(1.0 - 0.72 * u, 0.0, 1.0) ** 0.8 * (1.0 + rag * 0.5 * noise)
    k = np.clip(ht + 0.5 - np.abs(Y - yc), 0.0, 1.0) * np.clip((1.0 - u) * w / max(t, 1.0) + 0.2, 0.0, 1.0)
    collar = tr.lens(w * 0.18, t * 1.1, 0.0, 0.0, 0.9, size=(kh, kw))
    collar = np.roll(collar, int(round(apex - t * 0.55 - (kh - 1) * 0.5)), 0)
    return np.clip(np.maximum(k, collar * 0.9), 0.0, 1.0)


def eye(r, w, t):
    """A knot: a dark almond ring round a greyer heart, `w` by `t` pixels."""
    size = ((int(t) + 9) | 1, (int(w) + 9) | 1)
    outer = tr.lens(w, t, ends=1.0, size=size)
    inner = tr.lens(w * 0.58, t * 0.42, ends=1.0, size=size)
    noise = tr.blur(r.standard_normal(size), 1.0)
    noise /= noise.std() + 1e-9
    return np.clip(outer * (1.0 + 0.2 * noise) - 0.55 * inner, 0.0, 1.0)


def white_bark(r, h, w, px=PX):
    """Aspen's smooth bark as (albedo sRGB, height, roughness, occlusion), h x w, tileable, `px` pixels per cm:
    chalky greenish-cream with a powdery bloom wiped round the trunk, faint horizontal lenticel lines, small diamond
    lenticels, black arc scars with raised lips, black knots with a pale halo, a little lichen."""
    cm = px
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (22 * cm, 6 * cm), 4)
    col = tr.mix((0.80, 0.82, 0.70), (0.90, 0.91, 0.81), tone)
    green = tr.smoothstep(0.5, 0.8, tr.fbm(r, h, w, (16 * cm, 5 * cm), 4))
    col = tr.mix(col, (0.60, 0.73, 0.54), green * 0.3)
    cream = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (20 * cm, 7 * cm), 3))
    col = tr.mix(col, (0.93, 0.89, 0.76), cream * 0.4)
    mottle = tr.fbm(r, h, w, (0.35 * cm, 0.3 * cm), 3)
    fibre = tr.fbm(r, h, w, (1.0 * cm, 0.07 * cm), 3)
    # The powdery bloom: chalky streaks wiped round the trunk
    bloom = tr.smoothstep(0.5, 0.82, tr.fbm(r, h, w, (9 * cm, 1.2 * cm), 4) + (mottle - 0.5) * 0.06)
    col = tr.mix(col, (0.955, 0.955, 0.925), bloom * 0.45)
    # Faint horizontal lines (rows of lenticels run together)
    band = tr.fbm(r, h, w, (30 * cm, 0.22 * cm), 3)
    col = col * (0.965 + 0.07 * (band - 0.5) * 2.0 * tr.fbm(r, h, w, (10 * cm, 4 * cm), 2))[..., None]
    height = 0.3 * band + 0.3 * mottle
    rough = 0.88 - 0.06 * bloom

    # Diamond lenticels: small, mostly horizontal, olive-grey, many
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.9)):
        length = (0.5 + r.exponential(0.7)) * cm
        thick = max(1.4, r.uniform(0.18, 0.4) * cm * min(1.0, length / (1.5 * cm)))
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), min(length, 3.5 * cm), thick, r.uniform(0.5, 1.0), ends=1.0)
    lent = tr.smoothstep(0.3, 0.65, tr.blur(lent, 0.04 * cm) * (0.6 + 0.8 * tr.fbm(r, h, w, (0.3 * cm, 0.2 * cm), 2)))
    col = tr.mix(col, tr.mix((0.30, 0.34, 0.24), (0.5, 0.54, 0.4), mottle), lent * 0.55)
    height -= lent * 0.5
    rough = tr.mix(rough, 0.95, lent)

    # Arc scars (a fallen branch): flat dark crescents with lips, 5 to 12 cm wide, and knots
    sc = np.zeros((h, w))
    for _ in range(max(2, int(round(area / 650.0)))):
        tr.stamp(sc, r.uniform(0, w), r.uniform(0, h),
                 chevron(r, r.uniform(5, 12) * cm, r.uniform(0.5, 1.1) * cm, r.uniform(0.1, 0.28)))
    for _ in range(max(1, int(round(area / 1100.0)))):
        tr.stamp(sc, r.uniform(0, w), r.uniform(0, h), eye(r, r.uniform(2.5, 5.5) * cm, r.uniform(1.4, 2.8) * cm))
    tex = tr.fbm(r, h, w, (0.8 * cm, 0.5 * cm), 3)
    halo = np.clip(tr.blur(sc, 0.7 * cm) * 1.6, 0.0, 1.0) * (1.0 - sc)
    col = tr.mix(col, (0.55, 0.58, 0.47), halo * 0.4)
    col = tr.mix(col, tr.mix((0.04, 0.04, 0.035), (0.2, 0.2, 0.18), tex * 0.8), sc)
    height += sc * (0.6 + 1.2 * tex)
    rough = tr.mix(rough, 0.95, sc)

    # Lichen: pale grey-green rosettes in patches, and fine dark grime
    lich = (tr.smoothstep(0.84, 0.9, tr.fbm(r, h, w, (0.9 * cm, 0.9 * cm), 3))
            * tr.smoothstep(0.55, 0.75, tr.fbm(r, h, w, (9 * cm, 7 * cm), 3)))
    col = tr.mix(col, (0.66, 0.72, 0.52), lich * 0.5)
    speck = (tr.smoothstep(0.8, 0.9, tr.fbm(r, h, w, (0.15 * cm, 0.15 * cm), 2))
             * tr.smoothstep(0.45, 0.75, tr.fbm(r, h, w, (8 * cm, 4 * cm), 3)))
    col = tr.mix(col, (0.40, 0.42, 0.34), speck * 0.4)
    detail = 0.6 * fibre + 0.4 * mottle
    col = col * (0.95 + 0.1 * detail)[..., None]
    height = height + 0.6 * detail
    occ = tr.cavity(height, 4.0 * RELIEF, 0.22)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def foot_bark(r, white, h=H, w=W, px=PX):
    """AspenBarkFoot: `white` with the old trunk's foot drawn over its lower rows: black-grey bark in tall narrow
    ridged plates split by deep furrows, pale green-grey on the ridge tops, lichen; dark up to 0.25-0.45 m on a 12 cm
    trunk, single dark plates higher, all gone by FOOT_END. Drawn upright (each row slid as BarkUV's twist slides it)."""
    col0, h0, rough0, occ0 = white
    cm = px
    v = (np.arange(h) + 0.5) / h
    z = np.broadcast_to(((v - GROUND_V) * TILE)[:, None], (h, w))

    def z_at(row):
        return ((row + 0.5) / h - GROUND_V) * TILE

    warp = ((tr.fbm(r, h, w, (2 * cm, 5 * cm), 3) - 0.5) * 1.2 * cm,
            (tr.fbm(r, h, w, (2 * cm, 5 * cm), 3) - 0.5) * 2.4 * cm)
    edge, big, big_y, _ = tr.cells(r, h, w, 4 * cm, 4.0, warp)
    split, small, small_y, _ = tr.cells(r, h, w, 1.8 * cm, 3.6, warp)
    del warp
    wobble = tr.fbm(r, h, w, (0.6 * cm, 1.6 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.22 + 0.3 * wobble) * cm, edge)
    crack = ((1.0 - tr.smoothstep(0.0, (0.05 + 0.08 * wobble) * cm, split))
             * tr.smoothstep(0.35, 0.6, tr.fbm(r, h, w, (1.5 * cm, 5 * cm), 3)) * 0.8)
    fiss = np.maximum(furrow, crack)
    plate = tr.smoothstep(0.0, 1.0 * cm, edge)
    grit = tr.fbm(r, h, w, (0.22 * cm, 0.35 * cm), 3)
    flake = tr.fbm(r, h, w, (1.2 * cm, 2.5 * cm), 4)
    streak = tr.fbm(r, h, w, (0.2 * cm, 2.2 * cm), 3)
    shade = r.random(small.max() + 1)[small]
    dark = tr.mix((0.10, 0.10, 0.09), (0.36, 0.37, 0.32), 0.4 * flake + 0.25 * grit + 0.2 * shade + 0.15 * streak)
    ridge_top = tr.smoothstep(0.7, 0.95, plate) * tr.smoothstep(0.45, 0.7, flake)
    dark = tr.mix(dark, (0.52, 0.55, 0.45), ridge_top * 0.45)
    lichen = (tr.smoothstep(0.86, 0.9, tr.fbm(r, h, w, (0.9 * cm, 0.9 * cm), 3))
              * tr.smoothstep(0.55, 0.75, tr.fbm(r, h, w, (10 * cm, 10 * cm), 3)))
    dark = tr.mix(dark, (0.50, 0.55, 0.40), lichen * 0.45)
    dark = tr.mix(dark, (0.02, 0.02, 0.018), fiss)
    dark_h = 2.0 * plate + 0.5 * flake + 0.4 * grit + 0.5 * streak - 2.2 * furrow - 1.0 * crack
    dark_occ = tr.cavity(dark_h, 3.0 * RELIEF, 0.25)
    keep = tr.smoothstep((FOOT_END - GROUND_V) * TILE, (FOOT_END - GROUND_V - 0.08) * TILE, z)
    top = 0.25 + 0.2 * r.random(big.max() + 1)[big]
    m = tr.smoothstep(0.35, 0.65, tr.smoothstep(top + 0.05, top - 0.05, z_at(big_y)) + (flake - 0.5) * 0.5)
    isl = r.random(small.max() + 1)[small] > 1.0 - 0.35 * tr.smoothstep(0.6, 0.35, z_at(small_y))
    m = np.maximum(m, isl * (0.75 + 0.25 * flake)) * keep
    dirty = tr.smoothstep(0.65, 0.25, z + (flake - 0.5) * 0.15) * keep
    thin = 1.0 - tr.smoothstep(0.0, (0.05 + 0.08 * wobble) * cm, edge)
    reach = thin * tr.smoothstep(0.55, 0.35, z + (wobble - 0.5) * 0.1) * (1.0 - m) * keep
    shift = np.round(TWIST * v * w).astype(int)
    rows, cols = np.arange(h)[:, None], (np.arange(w)[None, :] - shift[:, None]) % w

    def upright(a):
        return a[rows, cols]

    m, dirty, reach = upright(m), upright(dirty), upright(reach)
    dark, dark_h, dark_occ = upright(dark), upright(dark_h), upright(dark_occ)
    col = tr.mix(tr.mix(col0, (0.48, 0.5, 0.42), dirty * 0.35), dark, m)
    col = tr.mix(col, (0.14, 0.14, 0.12), reach * 0.45)
    height = tr.mix(h0, dark_h, m) - reach * 1.5
    rough = tr.mix(rough0, 0.93, np.maximum(m, reach))
    occ = np.minimum(tr.mix(occ0, dark_occ, m), 1.0 - reach * 0.4)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: smooth glossy olive-brown to grey-bronze, greyer where it turns, with short
    pale lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.26, 0.21, 0.14), (0.44, 0.38, 0.26), tone)
    bloom = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (2.5 * cm, 3.0 * cm), 4))
    col = tr.mix(col, (0.58, 0.58, 0.5), bloom * 0.5)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.9)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.35) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=1.0)
    col = tr.mix(col, (0.74, 0.7, 0.58), lent * 0.8)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.8
    rough = 0.5 + 0.1 * tone + 0.2 * bloom
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


def make_bark():
    r = np.random.default_rng(17)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = white_bark(r, H, W)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("AspenBark", col, height, rough, occ, RELIEF)
    save("AspenBarkFoot", *foot_bark(r, (col, height, rough, occ)), RELIEF)
    save("AspenBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top: four hanging twig sprays, 512 x 640 cells. Bottom: two cluster cells (a branchlet hung with sprays,
# for LOD2), and a single leaf, 128 square, for the seedling's cards (past the decal strip, so it flutters).

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.45, 0.56))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.2, 1.5))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.09, 0.09), pad=8)
    return atlas


def leaf_profile(s):
    """Half-width of an aspen blade from base to tip: broad and rounded (heart-shaped to round), widest a third of
    the way, ending in a short abrupt point."""
    return float(np.interp(s, (0.0, 0.02, 0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 0.96, 1.0),
                           (0.0, 0.42, 0.8, 0.97, 1.0, 0.96, 0.83, 0.6, 0.3, 0.1, 0.0)))


def leaf_materials(vein=0.35, shade=0.0):
    """The spray's own materials (rendered into the atlas): glossy mid-green leaf with pale veins and a paler, greyer
    underside; twig; flat petiole."""
    mat, g = tr.tk.new_material("AspenLeafSrc")
    attr = g.node("ShaderNodeAttribute", attribute_name="leaf")
    x, s, rv = g.separate(attr.outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.13, 0.27, 0.045), (0.2, 0.33, 0.055))
    base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.085, 0.18, 0.035))
    hi = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=3.0), 0.5, 0.82), 0.5)
    col = g.mix(hi, base, (0.27, 0.4, 0.07))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.6, 1.0), 0.2), col, (0.25, 0.38, 0.07))
    mid = g.ramp(ax, 0.05, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.55)), 7.0))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.43, 0.5),
                 g.math("MULTIPLY", g.ramp(ax, 0.02, 0.1), g.ramp(ax, 0.92, 0.65)))
    veins = g.math("MAXIMUM", mid, lat)
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.27, 0.4, 0.12))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.26, 0.34, 0.16), (0.33, 0.4, 0.21)),
                  (0.4, 0.46, 0.27))
    col = g.mix(back, col, under)
    spot = g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=2.0), 0.76, 0.8), g.ramp(rv, 0.9, 0.92))
    col = g.mix(spot, col, (0.12, 0.08, 0.03))
    rough = g.mixf(back, 0.36, 0.62)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.25 + vein - 0.35, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("AspenTwigSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=3.0), 0.3, 0.7), (0.07, 0.045, 0.025), (0.15, 0.1, 0.05))
    tr.tk.finish(mat, g, col, 0.0, 0.45)
    twig = tr.signals(mat, col, 0.45)

    mat, g = tr.tk.new_material("AspenPetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    col = g.mix(g.ramp(t, 0.0, 0.8), (0.1, 0.09, 0.035), (0.2, 0.26, 0.08))
    tr.tk.finish(mat, g, col, 0.0, 0.45)
    pet = tr.signals(mat, col, 0.45)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, tan, side, size):
    """A leaf on its long petiole at p on a twig heading `tan`, to the twig's `side`: the petiole hangs out and down,
    the blade turned any way (aspen leaves are loose on their flat stalks), one in five showing its paler back."""
    lat = Vector((-tan.y, tan.x, 0.0))
    lat = (lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))) * side
    pd = (lat * 0.75 + tan * 0.3 + Vector((0.0, -0.45, rnd.uniform(-0.3, 0.3)))).normalized()
    pl = size * rnd.uniform(0.55, 0.85)
    b = p + pd * pl
    tr.twig(m, [p, p + pd * (pl * 0.5) + Vector((0.0, 0.003, 0.0)), b], [0.0009, 0.0008, 0.0007], "petiole", 4)
    dd = (pd * 0.35 + tan * 0.1 + Vector((rnd.gauss(0, 0.35), -0.8, rnd.gauss(0, 0.25)))).normalized()
    nl = Vector((rnd.gauss(0.0, 0.4), 0.3 + rnd.gauss(0.0, 0.25), 1.0))
    if rnd.random() < 0.2:
        nl = Vector((nl.x, nl.y * 0.5, -1.0))
    tr.blade(m, b, dd, nl, size, size * rnd.uniform(0.88, 1.0), leaf_profile, "leaf", teeth=20, tooth=0.022,
             fold=rnd.uniform(0.04, 0.14), arch=rnd.uniform(0.04, 0.16), twist=rnd.uniform(-22.0, 22.0), rows=16,
             rnd_value=rnd.random())


def leafy_twig(m, rnd, start, direction, length, bend, down, radius, first=0.05, gap=(0.05, 0.075), size=1.0,
               side_twigs=0):
    """A twig from `start` with alternate long-stalked leaves every `gap` of its length (fractions), `side_twigs`
    leafy side twigs, and a leaf at its tip."""
    pts = tr.bend_path(start, direction, length, bend, steps=14, down=down)
    tr.twig(m, pts, [radius * (1.0 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 5)
    tw = tr.Branch(pts, [radius] * len(pts))
    sides = set(rnd.sample(range(2, 15), side_twigs)) if side_twigs else set()
    f, i, side = first, 0, rnd.choice((-1, 1))
    while f < 0.96:
        p, tan, _ = tw.at(f)
        leaf = size * rnd.uniform(0.054, 0.068) * (1.0 - 0.22 * f)
        if i in sides:
            d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(28.0, 42.0))
            d.z += rnd.uniform(-0.2, 0.2)
            leafy_twig(m, rnd, p, d, length * rnd.uniform(0.25, 0.4), rnd.uniform(0.8, 1.2), (0.0, -1.0, 0.0),
                       radius * 0.6, first=0.12, gap=(0.1, 0.14), size=size * 0.92)
        else:
            add_leaf(m, rnd, p, tan, side, leaf)
        f += rnd.uniform(*gap)
        i += 1
        side = -side
    p, tan, _ = tw.at(1.0)
    add_leaf(m, rnd, pts[-1], tan, side, size * 0.05)


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(23)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        direction = Vector((side * rnd.uniform(0.2, 0.45), -1.0, rnd.uniform(-0.15, 0.15)))
        down = Vector((-side * (0.15, 0.5, 0.0, 0.35)[i], -1.0, 0.0))
        leafy_twig(m, rnd, Vector((0.0, 0.0, 0.0)), direction, rnd.uniform(0.5, 0.58), rnd.uniform(0.4, 0.9), down,
                   0.002, first=0.05, gap=(0.05, 0.072), side_twigs=(4, 5, 4, 5)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        m = tr.Mesh()
        side = (1, -1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.5, -1.0, 0.1)), rnd.uniform(0.75, 0.85), 0.4, steps=10,
                              down=(0.0, -1.0, 0.0))]
        main_stem = tr.Branch(stems[0], [0.006] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.65, -side)):
            p, tan, _ = main_stem.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.35, 0.5), 0.5, steps=8, down=(0.0, -1.0, 0.0)))
        for k, st in enumerate(stems):
            r0 = 0.007 if k == 0 else 0.0045
            tr.twig(m, st, [r0 * (1.0 - 0.6 * i / (len(st) - 1)) for i in range(len(st))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        for k, st in enumerate(stems):
            br = tr.Branch(st, [0.006] * len(st))
            count = 10 if k == 0 else 6
            for j in range(count):
                f = 0.08 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / count
                p, tan, _ = br.at(f)
                c = sprays[rnd.randrange(len(sprays))].copy()
                tr.tk.link(c)
                spin = (j % 2 * 2 - 1) * rnd.uniform(10.0, 70.0)
                rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-55, 55)), 4, "Y")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 4, "X"))
                c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.75, 1.0), 4)
                objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    m = tr.Mesh()
    stalk = Vector((0.002, -0.014, 0.0))
    tr.twig(m, [Vector(), Vector((0.0015, -0.007, 0.0005)), stalk], [0.0008, 0.0007, 0.0006], "petiole", 4)
    tr.blade(m, stalk, Vector((0.1, -1.0, 0.0)), Vector((0.0, 0.15, 1.0)), 0.065, 0.06, leaf_profile, "leaf",
             teeth=20, tooth=0.022, fold=0.1, arch=0.1, twist=8.0, rows=16, rnd_value=0.55)
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "AspenLeaves")
    atlas.preview(os.path.join(PREVIEWS, "aspen_atlas.png"))
    for c in atlas.cells.values():
        print("[aspen] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("AspenLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """The limbs' length up their span: short at the very bottom of the crown, fullest a third of the way, then
    narrowing to the top: a small, narrow, rounded crown."""
    return (0.4 + 0.6 * math.sin(math.pi * min(1.0, t) ** 0.85)) * (1.0 - 0.45 * t * t)


def aspen(trunks, crown=0.52, limbs=1.1, reach=1.0, twigs=1.9, favor=None, inner=0.0, budget=8000, stubs=None,
          card_scale=(0.95, 1.3), limb_sides=(4, 3, 3), whip=False):
    """An aspen stand's TreeSpec: `trunks` (tr.Trunk), limbs per metre of the crown span (from `crown` of each trunk's
    height), `reach` scaling their length, `inner` shortening limbs toward the stand's middle, `favor` the sunny side."""
    limbs_lv = tr.Level(per_meter=limbs, span=(crown, 0.97), length=(1.0 * reach, 2.3 * reach), shape=crown_shape,
                        angle=54.0, angle_tip=30.0, angle_vary=10.0, radius=0.5, radius_length=0.7, radius_max=0.035,
                        tip_radius=0.004, step=0.3, gravitropism=0.45, droop=0.25, wander=0.25, outward=0.15,
                        favor=favor, inner=inner, floor=0.5, sides=limb_sides, seg=(1.4, 2.0, 2.8),
                        min_len=(0.0, 0.0, 1.0))
    twigs_lv = tr.Level(per_meter=twigs, span=(0.12, 0.97), length=(0.5 * reach ** 0.5, 1.1 * reach ** 0.5),
                        shape="tapered", angle=58.0, angle_tip=40.0, angle_vary=10.0, planar=0.3, radius=0.5,
                        radius_length=0.6, radius_max=0.008, tip_radius=0.0025, step=0.2, gravitropism=0.2,
                        droop=0.45, wander=0.5, outward=0.3, floor=0.5, sides=(3, 3, 0), seg=(1.0, 1.4, 9.0),
                        min_len=(0.0, 0.7, 99.0))
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs_lv, twigs_lv], stubs=stubs, budget=budget,
        foliage=tr.Foliage(levels={2: (0.1, 1.0), 1: (0.4, 1.0)}, trunk_top=(0.9, 1.0), spacing=0.03,
                           cells=SPRAYS, scale=card_scale, hang=0.3, spread=0.5, out=0.5, face=0.7, up=0.35,
                           roll=45.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.35, 1.0)}, trunk_top=(0.85, 1.0), spacing=0.9, cells=CLUSTERS,
                           scale=(0.85, 1.15), hang=0.45, spread=0.25, out=0.5, face=0.85, up=0.15, roll=25.0,
                           bend=20.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V)


def trunk_radius(height):
    """Radius 1 m up for a trunk of this height: 0.06 at 3 m, 0.086 at 6 m, 0.12 at 10 m, 0.17 at 16 m."""
    return 0.035 + 0.0085 * height


def trunk(height, base=(0.0, 0.0), lean=(0.0, 0.0), bow=0.3, young=False, **kw):
    r = trunk_radius(height)
    sides = (8, 6, 4) if r > 0.065 else (6, 5, 4)
    d = dict(height=height, radius=r, base=base, lean=lean, bow=bow, flare=0.1 if young else 0.16, flare_height=0.3,
             lobes=(0, 0.0), taper=0.8, tip_radius=0.006, wander=0.025, sides=sides, seg=(2.4, 3.6, 5.5),
             rings=((0.0, 0.3, 1.0), (0.0,), (0.0,)), tags=("young",) if young else ())
    d.update(kw)
    return tr.Trunk(**d)


def stand(seed, heights, radius, lean_out=0.06, light=None, light_amt=0.0, gap=0.7, young=False):
    """Trunks for a clone stand: bases scattered over a disc of `radius` m (no two within `gap`), taller trunks nearer
    the middle, centred on the origin, each leaning a little outward (`lean_out` of its height) and, if `light` is
    given, toward that direction by `light_amt` of its height."""
    rnd = random.Random(seed)
    n = len(heights)
    pts, tries, g = [], 0, gap
    while len(pts) < n:
        a, d = rnd.uniform(0.0, TAU), radius * math.sqrt(rnd.random())
        p = (d * math.cos(a), d * math.sin(a))
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= g for q in pts):
            pts.append(p)
        tries += 1
        if tries % 300 == 0:
            g *= 0.9
    cx, cy = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    pts = [(x - cx, y - cy) for x, y in pts]
    pts.sort(key=lambda p: math.hypot(*p) + rnd.uniform(-0.5, 0.5))
    out = []
    for h, p in zip(sorted(heights, reverse=True), pts):
        d = math.hypot(*p)
        o = (p[0] / d, p[1] / d) if d > 0.15 else (0.0, 0.0)
        lean = [o[0] * lean_out * h * rnd.uniform(0.5, 1.3) + rnd.gauss(0.0, 0.025 * h),
                o[1] * lean_out * h * rnd.uniform(0.5, 1.3) + rnd.gauss(0.0, 0.025 * h)]
        if light is not None:
            lean[0] += light[0] * light_amt * h * rnd.uniform(0.7, 1.2)
            lean[1] += light[1] * light_amt * h * rnd.uniform(0.7, 1.2)
        out.append(trunk(h, base=(round(p[0], 3), round(p[1], 3)), lean=tuple(lean), bow=rnd.uniform(0.15, 0.6),
                         young=young))
    return out


def sapling():
    """The seedling a planted seed shows: a slender olive-brown whip about 0.7 m with a few short side shoots, hung
    with single leaves."""
    shoots = tr.Level(count=(3, 5), span=(0.3, 0.85), length=(0.1, 0.22), shape="tapered", angle=55.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.5, droop=0.2, wander=0.4, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.72, radius=0.0045, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0012,
                         lean=(0.04, 0.03), bow=0.3, wander=0.02, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.35, 1.0), spacing=0.03, cells=(LEAF,),
                           scale=(0.65, 1.0), hang=0.2, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.06, cells=(LEAF,), scale=(0.9, 1.2),
                           hang=0.25, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V, budget=500, lod_share=(0.55, 0.3))


def whips_spec():
    """The young thicket: nine thin whips, each with short leafy side shoots from a third of the way up."""
    trunks = stand(61, [5.9, 5.4, 5.0, 4.6, 4.3, 3.9, 3.5, 3.2, 3.0], 1.4, lean_out=0.05, gap=0.45, young=True)
    shoots = tr.Level(per_meter=2.7, span=(0.3, 0.98), length=(0.4, 0.95), shape="tapered", angle=52.0, angle_tip=36.0,
                      angle_vary=10.0, radius=0.35, radius_length=0.6, radius_max=0.012, tip_radius=0.003, step=0.15,
                      gravitropism=0.4, droop=0.35, wander=0.35, outward=0.25, floor=0.5, sides=(4, 3, 0),
                      seg=(0.8, 1.2, 9.0), min_len=(0.0, 0.7, 99.0))
    twigs = tr.Level(per_meter=2.0, span=(0.15, 0.97), length=(0.25, 0.5), shape="tapered", angle=58.0, angle_tip=42.0,
                     radius=0.5, radius_length=0.5, radius_max=0.004, tip_radius=0.002, step=0.12, gravitropism=0.2,
                     droop=0.5, wander=0.4, floor=0.5, sides=(3, 3, 0), seg=(0.6, 1.0, 9.0), min_len=(0.0, 0.5, 99.0))
    spec = aspen(trunks, budget=6000, card_scale=(0.9, 1.2))
    spec.levels = [shoots, twigs]
    spec.foliage = tr.Foliage(levels={2: (0.1, 1.0), 1: (0.35, 1.0)}, trunk_top=(0.82, 1.0), spacing=0.032,
                              cells=SPRAYS, scale=(0.8, 1.1), hang=0.3, spread=0.5, out=0.5, face=0.7, up=0.35,
                              roll=45.0, bend=0.0)
    return spec


VARIANTS = [
    # A dense clone clump: ten trunks 6 to 16 m on a 4 to 5 m footprint
    ("Aspen01", 11, lambda: aspen(stand(5, [16.0, 15.2, 14.1, 13.0, 12.2, 11.0, 10.2, 8.8, 7.4, 6.2], 2.0, gap=0.62),
                                  inner=0.5, limbs=0.9, reach=0.85, budget=8000, twigs=1.5, card_scale=(1.05, 1.5))),
    # A sparser stand of six, leaning toward the light (+x, a little -y)
    ("Aspen02", 23, lambda: aspen(stand(9, [15.0, 14.0, 12.6, 11.6, 10.0, 8.6], 2.4, lean_out=0.03,
                                        light=(0.9, -0.43), light_amt=0.075, gap=1.1),
                                  limbs=1.0, reach=0.95, favor=((0.9, -0.43), 0.35), inner=0.35, budget=7500,
                                  twigs=1.7, card_scale=(1.05, 1.5))),
    # One mature trunk
    ("Aspen03", 37, lambda: aspen([trunk(15.6, lean=(0.5, -0.3), bow=0.35, radius=0.19, sides=(12, 8, 5),
                                         seg=(1.2, 2.4, 4.5), flare=0.2, flare_height=0.4)],
                                  crown=0.5, limbs=1.45, reach=1.15, budget=6500, twigs=2.2, limb_sides=(6, 4, 3),
                                  stubs=tr.Level(count=(2, 4), span=(0.1, 0.46), length=(0.04, 0.14), angle=72.0,
                                                 angle_vary=12.0, radius=0.2, radius_length=0.0, radius_max=0.03,
                                                 tip_radius=0.008, broken=True, step=0.05, droop=0.3, wander=0.2,
                                                 sides=(9, 6, 0), seg=(0.3, 1.0, 1.0), min_length=0.03))),
    # A young thicket of whips
    ("Aspen04", 41, whips_spec),
    ("AspenSapling", 53, sapling),
]


def make_icon():
    """AspenSeed_Icon.png (160 x 160): a ripe catkin of capsules splitting open into tufts of white cottony fluff,
    lying across an aspen leaf, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.6, shade=0.3)
    mat, g = tr.tk.new_material("AspenFluffSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.85, 0.84, 0.8), (1.0, 1.0, 0.97))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.0, 0.35), 0.5), col, (0.5, 0.49, 0.45))
    tr.tk.finish(mat, g, col, 0.0, 0.95)
    mats["fluff"] = mat
    mat, g = tr.tk.new_material("AspenCapsuleSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.2, 0.14, 0.07), (0.34, 0.27, 0.12))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    mats["capsule"] = mat

    m = tr.Mesh()
    stalk = Vector((0.03, 0.004, -0.032))
    tr.twig(m, [Vector((0.038, 0.004, -0.044)), stalk], [0.0009, 0.0008], "petiole", 5)
    tr.blade(m, stalk, Vector((-0.5, 0.0, 0.85)), Vector((0.35, -1.0, 0.1)), 0.07, 0.066, leaf_profile, "leaf",
             teeth=20, tooth=0.022, fold=0.22, arch=0.2, twist=-18.0, rows=16, rnd_value=0.45)
    # The catkin: a drooping stalk from the top right to the lower left, studded with little splitting capsules, each
    # with a cloud of long silky hairs
    top, tip = Vector((0.036, -0.016, 0.036)), Vector((-0.014, -0.022, -0.02))
    axis = (tip - top).normalized()
    pts = [top.lerp(tip, i / 8) + Vector((0.0, 0.0, 0.0035 * math.sin(math.pi * i / 8))) for i in range(9)]
    tr.twig(m, pts, [0.0012 * (1.0 - 0.3 * i / 8) for i in range(9)], "capsule", 6)
    rnd = random.Random(11)
    _, u, v = tr.basis(axis)
    for i in range(10):
        f = 0.12 + 0.82 * (i + rnd.uniform(-0.2, 0.2)) / 9
        c = top.lerp(tip, f) + Vector((0.0, 0.0, 0.0035 * math.sin(math.pi * f)))
        a = rnd.uniform(0, TAU)
        out = (u * math.cos(a) + v * math.sin(a))
        base = c + out * 0.0014
        tr.blade(m, base, (out * 0.6 + axis * 0.3).normalized(), out, 0.0046, 0.0026,
                 lambda q: float(np.interp(q, (0, 0.3, 0.7, 1.0), (0.3, 1.0, 0.8, 0.0))), "capsule", rows=5,
                 rnd_value=rnd.random(), fold=0.3)
        for _ in range(95):
            d = (out * rnd.uniform(0.3, 1.0) + u * rnd.gauss(0, 0.5) + v * rnd.gauss(0, 0.5)
                 + axis * rnd.gauss(0, 0.45) + Vector((0, -0.25, 0.1))).normalized()
            ln = rnd.uniform(0.012, 0.03) * (0.65 + 0.35 * math.sin(math.pi * f))
            hair = tr.bend_path(base, d, ln, rnd.uniform(0.3, 1.2), steps=4,
                                down=(rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)))
            tr.twig(m, hair, [0.0006, 0.00048, 0.00036, 0.00026, 0.00016], "fluff", 3)
    obj = m.build("AspenSeedIcon", mats)
    obj.scale = (7.0, 7.0, 7.0)
    obj.location = (-0.05, 0.0, 0.31)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.62)
    tr.tk.icon(cam, os.path.join(FOLDER, "AspenSeed_Icon.png"), hide=())
    print("[aspen] icon written")


def main():
    tr.reset()
    atlas = layout()
    if STEPS == "icon":
        make_icon()
        return
    if STEPS in ("all", "textures", "bark", "bark-textures"):
        make_bark()
        if STEPS == "bark-textures":
            return
    if STEPS in ("all", "textures", "atlas"):
        make_atlas(atlas)
        if STEPS == "textures":
            return
        tr.reset()
    else:
        make_atlas(atlas, render=False)
        load_coverage(atlas)
        tr.reset()
    tr.use_atlas(atlas)
    mats = {name: tr.textured(name, paths(name)) for name in ("AspenBark", "AspenBarkFoot", "AspenBarkTwig")}
    mats = {"bark": mats["AspenBark"], "foot": mats["AspenBarkFoot"], "twig": mats["AspenBarkTwig"],
            "leaves": tr.textured("AspenLeaves", paths("AspenLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    for name, seed, make in VARIANTS:
        spec = make()
        if STEPS == "skeleton":
            spec.foliage = None
        tree = tr.grow(spec, seed, name)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        extent = max(math.hypot(t.points[0].x, t.points[0].y) + t.radii[3] for t in tree.trunks)
        print("[aspen] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f; %d trunks, bases within %.2f m"
              % (name, size[0], size[1], size[2], size[3][0], size[3][1], len(tree.trunks), extent))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[2]
    tr.preview_bark("aspen03", lods[0], PREVIEWS, figure)
    name, tree, lods, size = built[0]
    tr.preview_lods("aspen01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("aspen", [b[2][0] for b in built[:4]], PREVIEWS, figure,
                     spots=[(-9.0, 5.0), (3.0, 12.0), (11.0, 3.0), (-1.0, -3.0)])
    if STEPS == "all":
        make_icon()
    print("[aspen] done")


main()
