"""Paper birch (Betula papyrifera) in summer: the first tree on treekit.py, and its worked example. Read it, and
TREES.md, before writing a tree.

Chalky white bark with a faint cream-pink cast, crossed by thin dark lenticels, peeling in papery curls that show
salmon inner bark, black chevron scars where branches leave the trunk, and dark fissured bark on the bottom metre or
so. A slender trunk 20 to 35 cm across, often leaning, and a full narrow-oval crown from 35 to 40 % of its height:
upswept limbs whose fine twigs droop at the ends, about the leaf mass of vanilla's small oak with sky showing through
here and there. Small (5 to 8 cm) triangular-ovate, doubly toothed leaves, light green with yellow-green highlights
and paler undersides, graded (like the bark) to means measured beside vanilla's trees in the game's shader.

    blender -b --factory-startup --python trees/birch.py -- <unity trees folder> <preview folder> [textures|bark|trees]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. It writes
Trees/Birch/ (the shared bark and leaf textures, Birch01..04.fbx and their impostor maps), the Birch lines of
Trees/trees.txt, the seed's icon and the previews. `textures` stops after the shared textures; `bark` remakes only
the bark textures and then the variants (`bark-textures` stops after them), `atlas` only the leaf atlas and then the
variants; `trees` builds the variants on the textures already there; `icon` draws only the seed's icon.
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
FOLDER = os.path.join(TREES, "Birch")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# BirchBark: 2048 x 4096, the white bark, wrapping twice round a tube and tiling up it every 2 pi radii (1.13 m on
# a 36 cm trunk), so its texels stay square on every branch (BarkUV k = 2 pi, wraps 2): about 36 px per cm on
# Birch01's trunk. Features are drawn at their size on a 36 cm trunk; on a thin limb the same texture shrinks with
# it, as real lenticels do.
# BirchBarkFoot: the same size and the same mapping (a trunk's bark v counts from the ground, GROUND_V there), the
# white bark itself with the trunk's dark fissured foot drawn over its lower rows. The trunk changes from it to
# BirchBark at JOIN_V, in rows the two share untouched, so the change can't be seen.
# BirchBarkTwig: 512 x 1024, the dark reddish bark of thin branches (under 1.2 cm radius), once round them and
# tiling up every 4 pi radii.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)  # radii per repeat up a tube: 2 pi
R_DESIGN = 18.0  # cm: the trunk the bark is drawn for (Birch01's, before the bundle's 1.35 scale)
PX = WRAPS * W / (TAU * R_DESIGN)  # BirchBark pixels per cm, round and up that trunk
RELIEF = PX / 13.0  # the first bark's 13 px per cm: slopes and cavities keep their size in cm
TILE = K * R_DESIGN / 100.0  # one repeat's height on that trunk, m
TWIST = 0.37
GROUND_V = 0.1  # a trunk's bark v at the ground
JOIN_V = 0.93  # where its foot ends; the foot texture is BirchBark untouched from FOOT_END on
FOOT_END = 0.86
# Mean albedo (sRGB) the textures are graded to, set from the game-shader renders beside vanilla trees: the bark
# still clearly white next to vanilla's grey-brown pines without glowing, the leaves a touch lighter and yellower
# than vanilla's oak foliage (about 72, 80, 58)
BARK_MEAN = (180, 176, 168)
LEAF_MEAN = (84, 98, 58)
TWIG_R = 0.012  # thinner bark is twig bark
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "foot": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST, floor=0.005),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    # Thin first: a seedling's stem is twig bark right down to the ground
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    if br.level == 0 and br.turns(s) / K + br.v0 < JOIN_V:
        return "foot"
    return "bark"


def chevron(r, w, t, droop=0.4, rag=0.35):
    """A birch branch scar, as a kernel for tr.stamp: a dark inverted V with drooping arms `w` pixels across, `t`
    thick at the apex and thinning outward, its edge ragged by `rag`, with the swollen collar under its apex where
    the branch was."""
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
    """An eye scar: a dark almond ring round a greyer heart, `w` by `t` pixels."""
    size = ((int(t) + 9) | 1, (int(w) + 9) | 1)
    outer = tr.lens(w, t, ends=1.0, size=size)
    inner = tr.lens(w * 0.58, t * 0.42, ends=1.0, size=size)
    noise = tr.blur(r.standard_normal(size), 1.0)
    noise /= noise.std() + 1e-9
    return np.clip(outer * (1.0 + 0.2 * noise) - 0.55 * inner, 0.0, 1.0)


def white_bark(r, h, w, px=PX, peel=1.0, scars=True):
    """Paper birch's white bark as (albedo sRGB, height, roughness, occlusion), h x w, tileable both ways, `px`
    pixels per cm: chalky cream-white drifting greyer and pinker, fine horizontal paper layers, peeling strips with
    salmon inner bark and curled lips, thin dark lenticels, a few dark cracks, and (with `scars`) black chevrons
    and eye scars."""
    cm = px
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (40 * cm, 10 * cm), 4)
    col = tr.mix((0.84, 0.825, 0.795), (0.95, 0.935, 0.905), tone)
    warm = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (30 * cm, 8 * cm), 3))
    col = tr.mix(col, (0.95, 0.87, 0.84), warm * 0.5)
    # Fine detail down to the pixel, so the bark holds up an arm's length off: paper fibres running round the trunk
    # and a fine mottle
    fibre = tr.fbm(r, h, w, (1.2 * cm, 0.08 * cm), 3)
    mottle = tr.fbm(r, h, w, (0.35 * cm, 0.25 * cm), 3)
    # Weathered grey patches, crisp-edged and stretched round the trunk, mottled
    grey = tr.smoothstep(0.66, 0.72, tr.fbm(r, h, w, (16 * cm, 5 * cm), 5) + (mottle - 0.5) * 0.04)
    col = tr.mix(col, (0.68, 0.675, 0.66), grey * 0.35 * (0.6 + 0.8 * mottle))
    # Paper layers: fine horizontal lines, stronger in places
    band = tr.fbm(r, h, w, (50 * cm, 0.3 * cm), 3)
    col = col * (0.975 + 0.045 * (band - 0.5) * 2.0 * tr.fbm(r, h, w, (12 * cm, 4 * cm), 2))[..., None]
    grain = tr.fbm(r, h, w, (2.0 * cm, 0.6 * cm), 3)
    height = 0.4 * band + 0.4 * grain
    rough = 0.8 + 0.08 * (tone - 0.5)

    # Peeling strips: the outer paper gone in narrow horizontal patches, a pinkish-cream layer or salmon inner
    # bark beneath
    rag = tr.fbm(r, h, w, (3 * cm, 1 * cm), 3)
    thr = 0.885 - 0.04 * peel
    peeled = tr.smoothstep(thr, thr + 0.012, tr.fbm(r, h, w, (22 * cm, 3 * cm), 5) + (rag - 0.5) * 0.05
                           + (mottle - 0.5) * 0.012)
    deep = tr.smoothstep(0.45, 0.6, tr.fbm(r, h, w, (8 * cm, 2 * cm), 3))
    inner = tr.mix((0.93, 0.82, 0.74), (0.82, 0.57, 0.45), deep)
    inner = inner * ((0.94 + 0.12 * tr.fbm(r, h, w, (4 * cm, 1 * cm), 3)) * (0.92 + 0.16 * fibre))[..., None]
    col = tr.mix(col, inner, peeled)
    rough = tr.mix(rough, 0.55, peeled)
    # The paper's torn edges roll outward: a bright lip along most edges, a dark gap under it
    d = max(2, int(0.7 * cm))
    above = np.clip(np.roll(peeled, d, 0) - peeled, 0.0, 1.0)
    below = np.clip(np.roll(peeled, -d, 0) - peeled, 0.0, 1.0)
    curl = tr.smoothstep(0.35, 0.6, tr.fbm(r, h, w, (10 * cm, 3 * cm), 3))
    lips = np.maximum(above, below * 0.75) * curl
    gap = np.clip(peeled - np.roll(peeled, -max(1, d // 2), 0), 0.0, 1.0) * curl
    gap = np.maximum(gap, np.clip(peeled - np.roll(peeled, max(1, d // 2), 0), 0.0, 1.0) * curl * 0.7)
    col = tr.mix(col, (0.975, 0.965, 0.94), lips * 0.65)
    col = tr.mix(col, (0.3, 0.19, 0.14), gap * 0.7)
    height = height - peeled * 1.2 + tr.blur(lips, 0.8) * 2.2 - gap * 0.8

    # Lenticels: thin dark horizontal dashes, 1 to 6 cm, mostly short
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.05)):
        length = min(7.0, 0.8 + r.exponential(1.6)) * cm
        thick = max(1.2, r.uniform(0.1, 0.25) * cm * (0.6 + 0.5 * min(1.0, length / (4.0 * cm))))
        x, y = r.uniform(0, w), r.uniform(0, h)
        tr.stamp_lens(lent, x, y, length, thick, r.uniform(0.55, 1.0), ends=0.7)
        if r.random() < 0.2:
            # A short run of them along the same line
            tr.stamp_lens(lent, x + length * r.uniform(0.7, 1.3), y + r.uniform(-0.15, 0.15) * cm,
                          length * r.uniform(0.3, 0.8), thick * 0.8, r.uniform(0.5, 0.9), ends=0.7)
    # Ragged edges and uneven darkness: softened a hair, broken by fine noise and cut back to a crisp edge
    lent = tr.smoothstep(0.38, 0.62, tr.blur(lent, 0.05 * cm) * (0.55 + 0.9 * tr.fbm(r, h, w, (0.3 * cm, 0.12 * cm), 2)))
    col = tr.mix(col, tr.mix((0.14, 0.11, 0.1), (0.3, 0.25, 0.22), mottle), lent * 0.9)
    height += lent * 0.8
    rough = tr.mix(rough, 0.88, lent)

    # A few longer, wider dark cracks (old lenticels split open)
    crack = np.zeros((h, w))
    for _ in range(max(2, int(area * 0.0012))):
        tr.stamp_lens(crack, r.uniform(0, w), r.uniform(0, h), r.uniform(4, 11) * cm, r.uniform(0.25, 0.55) * cm,
                      1.0, ends=0.9)
    crack *= tr.smoothstep(0.25, 0.6, rag)
    col = tr.mix(col, (0.09, 0.08, 0.075), crack * 0.95)
    height -= crack * 1.4

    if scars:
        # About one chevron and half an eye per 0.6 square metres of bark
        sc = np.zeros((h, w))
        for _ in range(max(1, int(round(area / 6000.0)))):
            tr.stamp(sc, r.uniform(0, w), r.uniform(0, h),
                     chevron(r, r.uniform(9, 16) * cm, r.uniform(1.0, 1.8) * cm, r.uniform(0.3, 0.5)))
        if r.random() < area / 12000.0:
            tr.stamp(sc, r.uniform(0, w), r.uniform(0, h), eye(r, r.uniform(6, 10) * cm, r.uniform(1.8, 2.8) * cm))
        tex = tr.fbm(r, h, w, (1.2 * cm, 0.8 * cm), 3)
        halo = np.clip(tr.blur(sc, 0.8 * cm) * 1.5, 0.0, 1.0) * (1.0 - sc)
        col = tr.mix(col, (0.55, 0.54, 0.52), halo * 0.45)
        col = tr.mix(col, tr.mix((0.045, 0.04, 0.038), (0.22, 0.2, 0.19), tex * 0.8), sc)
        height += sc * (0.5 + 1.2 * tex)
        rough = tr.mix(rough, 0.95, sc)

    # Grime: fine dark flecks gathered in patches; and the fibres and mottle in the color and the relief
    speck = (tr.smoothstep(0.8, 0.9, tr.fbm(r, h, w, (0.15 * cm, 0.15 * cm), 2))
             * tr.smoothstep(0.45, 0.75, tr.fbm(r, h, w, (8 * cm, 4 * cm), 3)))
    col = tr.mix(col, (0.38, 0.36, 0.33), speck * 0.5)
    detail = 0.6 * fibre + 0.4 * mottle
    col = col * (0.95 + 0.1 * detail)[..., None]
    height = height + 0.7 * detail
    occ = tr.cavity(height, 4.0 * RELIEF, 0.22) * (1.0 - gap * 0.35)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def foot_bark(r, white, h=H, w=W, px=PX):
    """BirchBarkFoot: `white` (BirchBark's albedo, graded, height, roughness and occlusion) with the trunk's foot
    over its lower rows: dark grey bark broken by deep furrows into tall rough plates, finer cracks splitting them,
    flecks of lichen; dark plate by plate up to between 0.3 and 0.5 m (so its edge runs along furrows), single dark
    plates above up to about 0.7 m, and the white near it dirtier and cracked where furrows run on into it (heights
    on Birch01's trunk; a thinner trunk's foot is lower, the bark tiling by radius). From FOOT_END up it is BirchBark
    untouched. The foot is drawn upright on the trunk: each row slid as BarkUV's twist slides it back."""
    col0, h0, rough0, occ0 = white
    cm = px
    v = (np.arange(h) + 0.5) / h
    z = np.broadcast_to(((v - GROUND_V) * TILE)[:, None], (h, w))

    def z_at(row):
        return ((row + 0.5) / h - GROUND_V) * TILE

    # Plates: cells stretched tall and warped so no edge runs straight, V-shaped furrows round plates about 7 by
    # 24 cm, finer cracks splitting some of them about 3 by 10 cm
    warp = ((tr.fbm(r, h, w, (3 * cm, 6 * cm), 3) - 0.5) * 1.6 * cm,
            (tr.fbm(r, h, w, (3 * cm, 6 * cm), 3) - 0.5) * 2.4 * cm)
    edge, big, big_y, _ = tr.cells(r, h, w, 7 * cm, 3.5, warp)
    split, small, small_y, _ = tr.cells(r, h, w, 3 * cm, 3.3, warp)
    del warp
    wobble = tr.fbm(r, h, w, (0.8 * cm, 2 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.3 + 0.4 * wobble) * cm, edge)
    crack = ((1.0 - tr.smoothstep(0.0, (0.06 + 0.1 * wobble) * cm, split))
             * tr.smoothstep(0.35, 0.6, tr.fbm(r, h, w, (2 * cm, 6 * cm), 3)) * 0.8)
    fiss = np.maximum(furrow, crack)
    plate = tr.smoothstep(0.0, 1.5 * cm, edge)  # the plates' rounded shoulders
    grit = tr.fbm(r, h, w, (0.25 * cm, 0.4 * cm), 3)
    flake = tr.fbm(r, h, w, (1.5 * cm, 3 * cm), 4)
    streak = tr.fbm(r, h, w, (0.25 * cm, 2.5 * cm), 3)  # fibrous, up the trunk
    shade = r.random(small.max() + 1)[small]  # each small plate a shade of its own
    dark = tr.mix((0.12, 0.115, 0.106), (0.34, 0.325, 0.3), 0.4 * flake + 0.25 * grit + 0.2 * shade + 0.15 * streak)
    lichen = (tr.smoothstep(0.86, 0.9, tr.fbm(r, h, w, (1.0 * cm, 1.0 * cm), 3))
              * tr.smoothstep(0.55, 0.75, tr.fbm(r, h, w, (12 * cm, 12 * cm), 3)))
    dark = tr.mix(dark, (0.42, 0.44, 0.38), lichen * 0.4)
    dark = tr.mix(dark, (0.025, 0.022, 0.02), fiss)
    dark_h = 2.0 * plate + 0.5 * flake + 0.4 * grit + 0.5 * streak - 2.2 * furrow - 1.0 * crack
    dark_occ = tr.cavity(dark_h, 3.0 * RELIEF, 0.25)
    # Where it's dark: whole big plates up to 0.3-0.52 m, each its own height, a few going grey part-way; single
    # small plates above up to about 0.7 m; all gone by FOOT_END
    keep = tr.smoothstep((FOOT_END - GROUND_V) * TILE, (FOOT_END - GROUND_V - 0.08) * TILE, z)
    top = 0.3 + 0.22 * r.random(big.max() + 1)[big]
    m = tr.smoothstep(0.35, 0.65, tr.smoothstep(top + 0.05, top - 0.05, z_at(big_y)) + (flake - 0.5) * 0.5)
    isl = r.random(small.max() + 1)[small] > 1.0 - 0.35 * tr.smoothstep(0.7, 0.4, z_at(small_y))
    m = np.maximum(m, isl * (0.75 + 0.25 * flake)) * keep
    dirty = tr.smoothstep(0.75, 0.3, z + (flake - 0.5) * 0.15) * keep
    thin = 1.0 - tr.smoothstep(0.0, (0.05 + 0.08 * wobble) * cm, edge)
    reach = thin * tr.smoothstep(0.62, 0.4, z + (wobble - 0.5) * 0.1) * (1.0 - m) * keep

    # Upright on the trunk: BarkUV puts a trunk's angle a round it at u = a + TWIST v, so row v is slid that far
    shift = np.round(TWIST * v * w).astype(int)
    rows, cols = np.arange(h)[:, None], (np.arange(w)[None, :] - shift[:, None]) % w

    def upright(a):
        return a[rows, cols]

    m, dirty, reach = upright(m), upright(dirty), upright(reach)
    dark, dark_h, dark_occ = upright(dark), upright(dark_h), upright(dark_occ)
    col = tr.mix(tr.mix(col0, (0.52, 0.51, 0.49), dirty * 0.35), dark, m)
    col = tr.mix(col, (0.16, 0.15, 0.14), reach * 0.45)
    height = tr.mix(h0, dark_h, m) - reach * 1.5
    rough = tr.mix(rough0, 0.93, np.maximum(m, reach))
    occ = np.minimum(tr.mix(occ0, dark_occ, m), 1.0 - reach * 0.4)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: dark reddish-brown to bronze, glossier than the trunk, greying-white in
    patches where it starts to turn, with short pale lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.25, 0.165, 0.135), (0.42, 0.315, 0.26), tone)
    bloom = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (2.5 * cm, 3.0 * cm), 4))
    col = tr.mix(col, (0.6, 0.575, 0.55), bloom * 0.55)
    lent = np.zeros((h, w))
    for _ in range(int(area * 1.1)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.4) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=0.8)
    col = tr.mix(col, (0.72, 0.66, 0.58), lent * 0.85)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.8
    rough = 0.55 + 0.1 * tone + 0.2 * bloom
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


def make_bark():
    """Writes BirchBark_*, BirchBarkFoot_* and BirchBarkTwig_*, the white graded to BARK_MEAN."""
    r = np.random.default_rng(7)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = white_bark(r, H, W)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("BirchBark", col, height, rough, occ, RELIEF)
    save("BirchBarkFoot", *foot_bark(r, (col, height, rough, occ)), RELIEF)
    save("BirchBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top: four hanging twig sprays, 512 x 896 cells showing 0.44 x 0.77 m (about 1160 px/m, a leaf some
# 70 px). Bottom: two cluster cells, 896 x 1152 showing 1.25 x 1.6 m (a branchlet hung with sprays, for LOD2), a row
# of scar cells 256 x 128 (chevrons and an eye; no tree wears them now: as cards they stood off the round trunk) and
# a single leaf, 128 square, for the seedling's cards.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
SCARS = ("Scar0", "Scar1", "Scar2")
LEAF = "Leaf"


def layout():
    """The cells; Atlas.frame later fits each spray's and cluster's world size and attach point to what it shows."""
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.45, 0.56))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.2, 1.5))
    for i, name in enumerate(SCARS):
        atlas.cell(name, 256 * i, 0, 256, 128, (0.24, 0.12), attach=(0.5, 0.5), pad=8)
    # Past the decal strip (u under .375), so its cards flutter like leaves
    atlas.cell(LEAF, 768, 0, 128, 128, (0.09, 0.09), pad=8)
    return atlas


def leaf_profile(s):
    """Half-width of a paper birch blade at fraction s from base to tip: a broad, rounded base, widest a third of
    the way, tapering straight to a pointed tip (triangular-ovate)."""
    return float(np.interp(s, (0.0, 0.03, 0.1, 0.22, 0.34, 0.5, 0.68, 0.84, 0.94, 1.0),
                           (0.0, 0.38, 0.72, 0.94, 1.0, 0.9, 0.64, 0.36, 0.14, 0.0)))


def leaf_materials(vein=0.35, shade=0.0):
    """The spray's own materials (rendered into the atlas, not exported): leaf, twig and petiole. `vein` is how much
    paler the veins are and `shade` darkens the leaf (the seed's icon, drawn small, wants both stronger)."""
    mat, g = tr.tk.new_material("BirchLeafSrc")
    attr = g.node("ShaderNodeAttribute", attribute_name="leaf")
    x, s, rv = g.separate(attr.outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Each leaf its own shade: mostly a clear light green, some yellower, a few darker
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.15, 0.27, 0.045), (0.26, 0.36, 0.06))
    base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.095, 0.175, 0.035))
    hi = g.math("MULTIPLY", g.ramp(g.noise(28.0, detail=3.0), 0.5, 0.82), 0.55)
    col = g.mix(hi, base, (0.33, 0.41, 0.075))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.6, 1.0), 0.25), col, (0.3, 0.39, 0.07))
    # Veins: the midrib and straight parallel side veins, paler
    mid = g.ramp(ax, 0.055, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.5)), 10.0))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.43, 0.5),
                 g.math("MULTIPLY", g.ramp(ax, 0.02, 0.1), g.ramp(ax, 0.92, 0.65)))
    veins = g.math("MAXIMUM", mid, lat)
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.29, 0.37, 0.11))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    # Undersides paler, greyer and more clearly veined
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.23, 0.31, 0.13), (0.3, 0.37, 0.18)),
                  (0.37, 0.43, 0.23))
    col = g.mix(back, col, under)
    # A few leaves with small brown spots
    spot = g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=2.0), 0.72, 0.78), g.ramp(rv, 0.86, 0.88))
    col = g.mix(spot, col, (0.12, 0.08, 0.03))
    rough = g.mixf(back, 0.42, 0.66)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.25 + vein - 0.35, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("BirchTwigSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=3.0), 0.3, 0.7), (0.07, 0.032, 0.02), (0.15, 0.075, 0.045))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("BirchPetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    col = g.mix(g.ramp(t, 0.0, 0.8), (0.12, 0.07, 0.03), (0.17, 0.2, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    pet = tr.signals(mat, col, 0.5)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, tan, side, size):
    """A leaf on its petiole at p on a twig heading `tan`, to the twig's `side` (+1 right, -1 left in the card),
    hanging and facing the card's front (+z) and a little up, one in six turned over to show its paler back."""
    lat = Vector((-tan.y, tan.x, 0.0))
    lat = (lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))) * side
    pd = (lat * 0.8 + tan * 0.35 + Vector((0.0, -0.3, rnd.uniform(-0.25, 0.25)))).normalized()
    pl = size * rnd.uniform(0.24, 0.34)
    b = p + pd * pl
    tr.twig(m, [p, p + pd * (pl * 0.5) + Vector((0.0, -0.002, 0.0)), b], [0.0008, 0.0007, 0.0006], "petiole", 4)
    dd = (pd * 0.5 + tan * 0.2 + Vector((rnd.gauss(0, 0.25), -0.75, rnd.gauss(0, 0.2)))).normalized()
    nl = Vector((rnd.gauss(0.0, 0.35), 0.35 + rnd.gauss(0.0, 0.2), 1.0))
    if rnd.random() < 0.16:
        nl = Vector((nl.x, nl.y * 0.5, -1.0))
    tr.blade(m, b, dd, nl, size, size * rnd.uniform(0.66, 0.76), leaf_profile, "leaf", teeth=13, tooth=0.05,
             fold=rnd.uniform(0.08, 0.22), arch=rnd.uniform(0.05, 0.2), twist=rnd.uniform(-25.0, 25.0), rows=16,
             rnd_value=rnd.random())


def leafy_twig(m, rnd, start, direction, length, bend, down, radius, first=0.05, gap=(0.055, 0.085), size=1.0,
               spurs=0.0, side_twigs=0):
    """A twig from `start` with alternate leaves every `gap` of its length (fractions), short spur shoots of two
    leaves at a `spurs` share of the older nodes, `side_twigs` leafy side twigs, and a leaf at its tip."""
    pts = tr.bend_path(start, direction, length, bend, steps=14, down=down)
    tr.twig(m, pts, [radius * (1.0 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 5)
    tw = tr.Branch(pts, [radius] * len(pts))
    sides = set(rnd.sample(range(2, 22), side_twigs)) if side_twigs else set()
    f, i, side = first, 0, rnd.choice((-1, 1))
    while f < 0.96:
        p, tan, _ = tw.at(f)
        leaf = size * rnd.uniform(0.052, 0.07) * (1.0 - 0.28 * f)
        if i in sides:
            d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(28.0, 42.0))
            d.z += rnd.uniform(-0.2, 0.2)
            leafy_twig(m, rnd, p, d, length * rnd.uniform(0.25, 0.42), rnd.uniform(0.8, 1.2), (0.0, -1.0, 0.0),
                       radius * 0.6, first=0.1, gap=(0.06, 0.09), size=size * 0.92, spurs=spurs * 0.6)
        elif f < 0.55 and rnd.random() < spurs:
            lat = Vector((-tan.y, tan.x, 0.0)).normalized() * side
            q = p + (lat * 0.7 + tan * 0.5).normalized() * 0.012
            tr.twig(m, [p, q], [radius * 0.7, radius * 0.6], "twig", 4)
            for s2 in (-1, 1):
                add_leaf(m, rnd, q, (lat + tan * 0.6).normalized(), s2, leaf * rnd.uniform(0.9, 1.05))
        else:
            add_leaf(m, rnd, p, tan, side, leaf)
        f += rnd.uniform(*gap)
        i += 1
        side = -side
    p, tan, _ = tw.at(1.0)
    add_leaf(m, rnd, pts[-1], tan, side, size * 0.045)


def make_atlas(atlas, render=True):
    """Builds the sprays and clusters and fits their cells to them; with `render`, renders them into the atlas,
    paints the scars and saves it (without, the cells are only measured: the geometry is the same every run)."""
    mats = leaf_materials()
    rnd = random.Random(19)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        direction = Vector((side * rnd.uniform(0.2, 0.45), -1.0, rnd.uniform(-0.15, 0.15)))
        down = Vector((-side * (0.15, 0.5, 0.0, 0.35)[i], -1.0, 0.0))
        leafy_twig(m, rnd, Vector((0.0, 0.0, 0.0)), direction, rnd.uniform(0.55, 0.62), rnd.uniform(0.5, 1.0), down,
                   0.0022, first=0.04, gap=(0.03, 0.045), spurs=(0.65, 0.55, 0.7, 0.6)[i],
                   side_twigs=(6, 7, 6, 7)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        # A branchlet: a stem and three side stems thick with sprays turned every way
        m = tr.Mesh()
        side = (1, -1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.5, -1.0, 0.1)), rnd.uniform(0.75, 0.85), 0.5, steps=10,
                              down=(0.0, -1.0, 0.0))]
        main_stem = tr.Branch(stems[0], [0.006] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.65, -side)):
            p, tan, _ = main_stem.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.35, 0.5), 0.6, steps=8, down=(0.0, -1.0, 0.0)))
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
    # One leaf on its petiole, hanging from the cell's top as a spray hangs from its twig
    m = tr.Mesh()
    stalk = Vector((0.002, -0.014, 0.0))
    tr.twig(m, [Vector(), Vector((0.0015, -0.007, 0.0005)), stalk], [0.0008, 0.0007, 0.0006], "petiole", 4)
    tr.blade(m, stalk, Vector((0.1, -1.0, 0.0)), Vector((0.0, 0.15, 1.0)), 0.065, 0.046, leaf_profile, "leaf",
             teeth=13, tooth=0.05, fold=0.12, arch=0.1, twist=8.0, rows=16, rnd_value=0.55)
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    paint_scars(atlas)
    out = atlas.save(FOLDER, "BirchLeaves")
    atlas.preview(os.path.join(PREVIEWS, "birch_atlas.png"))
    for c in atlas.cells.values():
        print("[birch] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def paint_scars(atlas):
    """The scar cells: two black chevrons (one wide and drooping, one narrower) and an eye, on transparency."""
    r = np.random.default_rng(3)
    for name, kind in zip(SCARS, ("wide", "narrow", "eye")):
        c = atlas.cells[name]
        h, w = c.h, c.w
        a = np.zeros((h, w))
        if kind == "eye":
            k = eye(r, w * 0.8, h * 0.62)
        else:
            k = chevron(r, w * (0.8 if kind == "wide" else 0.62), h * (0.16 if kind == "wide" else 0.2),
                        0.45 if kind == "wide" else 0.42)
        tr.stamp(a, w * 0.5, h * 0.5, k)
        tex = tr.normalize(tr.blur(r.standard_normal((h, w)), 1.3))
        col = tr.mix((0.04, 0.036, 0.034), (0.2, 0.185, 0.175), tex * 0.85)
        height = a * (1.0 + 1.5 * tex)
        atlas.paint(c, col, np.clip(a * 1.15, 0.0, 1.0), tr.normal_map(tr.blur(height, 0.7), 1.2), 0.94,
                    tr.cavity(height, 3.0, 0.2))


def load_coverage(atlas):
    a = tr.read_image(paths("BirchLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """The birch crown's envelope up the limbs' span: long limbs from the very bottom (the crown starts low, not as
    a tuft on a pole), widest a third of the way up, narrowing to the top: a full narrow oval."""
    return (0.55 + 0.45 * math.sin(math.pi * min(1.0, t) ** 0.8)) * (1.0 - 0.6 * t * t)


def birch(trunks, limbs=26, reach=1.0, crown=0.38, favor=None, inner=0.0, budget=8600, twig_density=1.9,
          limb_sides=6, stubs=(3, 6), card_scale=(0.95, 1.25)):
    """A paper birch's TreeSpec: `trunks` (tr.Trunk), `limbs` per trunk spiraling up its crown (from `crown` of
    its height), `reach` scaling the limbs' length, `favor` the sunny side, `inner` shortening limbs into a
    clump, `card_scale` the spray cards' size range (leaves 5 to 8 cm or so). Its chevrons and eyes are in the bark
    texture: scar cards on a round trunk stood off it as flat black patches."""
    limbs_lv = tr.Level(count=limbs, span=(crown, 0.97), length=(3.0 * reach, 4.5 * reach), shape=crown_shape,
                        angle=66.0, angle_tip=32.0, angle_vary=12.0, radius=0.55, radius_length=0.7, radius_max=0.08,
                        tip_radius=0.005, step=0.35, gravitropism=0.3, droop=0.5, wander=0.3, outward=0.2,
                        favor=favor, inner=inner, sides=(limb_sides, 5, 3), seg=(0.9, 1.4, 2.2),
                        min_len=(0.0, 0.0, 0.9))
    branches = tr.Level(per_meter=twig_density, span=(0.1, 0.97), length=(0.7 * reach ** 0.5, 1.6 * reach ** 0.5),
                        shape="tapered", angle=60.0, angle_tip=45.0, angle_vary=10.0, planar=0.35, radius=0.55,
                        radius_length=0.6, radius_max=0.015, tip_radius=0.0025, step=0.18, gravitropism=0.35,
                        droop=0.8, wander=0.6, outward=0.35, sides=(3, 3, 0), seg=(0.8, 1.2, 9.0),
                        min_len=(0.0, 0.7, 99.0))
    # Short round stubs of old limbs, snapped off
    stubs = tr.Level(count=stubs, span=(0.06, crown - 0.03), length=(0.04, 0.16), angle=72.0, angle_vary=12.0,
                     radius=0.2, radius_length=0.0, radius_max=0.03, tip_radius=0.008, broken=True, step=0.05,
                     droop=0.3, wander=0.2, sides=(9, 6, 0), seg=(0.3, 1.0, 1.0), min_length=0.03)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs_lv, branches], stubs=stubs, budget=budget,
        # Flat cards at LOD0 (2 triangles each, twice as many as folded ones) for a dense crown, spaced closer than
        # the budget allows and thinned evenly to it
        foliage=tr.Foliage(levels={2: (0.08, 1.0), 1: (0.3, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.04,
                           cells=SPRAYS, scale=card_scale, hang=0.35, spread=0.5, out=0.5, face=0.7, up=0.35,
                           roll=45.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.3, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.9, cells=CLUSTERS,
                           scale=(0.85, 1.15), hang=0.5, spread=0.25, out=0.5, face=0.85, up=0.15, roll=25.0,
                           bend=20.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V)


def trunk(**kw):
    base = dict(flare=0.28, flare_height=0.35, lobes=(5, 0.1), taper=0.95, tip_radius=0.007, wander=0.06,
                sides=(12, 8, 6), seg=(0.85, 1.6, 3.0), rings=((0.0, 0.12, 0.35, 0.7), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeBirchSeed in game): a red-brown whip about 0.75 m tall (1 m in
    game) with a few short side shoots, hung with single leaves (the atlas's Leaf cell). Thin as it is, its bark is
    twig bark from a couple of centimetres up."""
    shoots = tr.Level(count=(3, 5), span=(0.3, 0.85), length=(0.1, 0.22), shape="tapered", angle=55.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.5, droop=0.2, wander=0.4, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.75, radius=0.0045, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0012,
                         lean=(0.05, -0.03), bow=0.4, wander=0.02, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.35, 1.0), spacing=0.03, cells=(LEAF,),
                           scale=(0.65, 1.0), hang=0.2, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.06, cells=(LEAF,), scale=(0.9, 1.2),
                           hang=0.25, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V, budget=500, lod_share=(0.55, 0.3))


# Trunks as stout as vanilla's pines of the same height (about 0.25 m radius in game, after the bundle's 1.35 scale)
VARIANTS = [
    # Single and fairly straight, about 15 m
    ("Birch01", 11, lambda: birch([trunk(height=14.7, radius=0.18, lean=(0.35, 0.2), bow=0.3)], reach=0.92)),
    # Leaning and curved (it leans low and its top turns back up), about 13 m, the crown fuller on the open side
    ("Birch02", 23, lambda: birch([trunk(height=12.8, radius=0.165, lean=(2.3, -0.9), bow=0.6, wander=0.08)],
                                  limbs=23, crown=0.4, reach=0.9, favor=((1.0, -0.4), 0.35))),
    # A clump of three trunks from one base, splaying, about 16 m: three crowns share the budget, so a little
    # bigger cards
    ("Birch03", 37, lambda: birch([trunk(height=15.8, radius=0.15, base=(0.1, 0.04), lean=(1.3, 0.4), bow=0.4,
                                         sides=(10, 7, 5), seg=(1.25, 2.0, 3.6)),
                                   trunk(height=14.4, radius=0.13, base=(-0.085, 0.1), lean=(-1.1, 1.0), bow=0.5,
                                         sides=(10, 7, 5), seg=(1.25, 2.0, 3.6)),
                                   trunk(height=12.6, radius=0.11, base=(-0.015, -0.11), lean=(0.1, -1.4), bow=0.6,
                                         sides=(9, 6, 5), seg=(1.25, 2.0, 3.6))],
                                  limbs=12, reach=0.76, inner=0.6, twig_density=1.45, stubs=(1, 3),
                                  card_scale=(1.0, 1.3))),
    # Young and slender, about 9.5 m, its crown lower
    ("Birch04", 41, lambda: birch([trunk(height=9.4, radius=0.095, lean=(-0.4, 0.5), bow=0.2, flare=0.2)],
                                  limbs=24, reach=0.4, crown=0.3, budget=5400, twig_density=2.8)),
    # The seedling a planted seed shows before it grows into Birch04
    ("BirchSapling", 53, sapling),
]


def trilobe(s):
    """Half-width of a birch catkin's scale from base to tip: a narrow claw widening into two spreading side lobes,
    a notch, and the middle lobe."""
    return float(np.interp(s, (0.0, 0.25, 0.5, 0.62, 0.7, 0.78, 0.9, 1.0), (0.25, 0.4, 0.95, 1.0, 0.45, 0.42, 0.3, 0.0)))


def make_icon():
    """BirchSeed_Icon.png (160 x 160, in Trees/Birch; gen_nature.py copies it into the mod's item icons), drawn like
    vanilla's tree seeds (acorns on an oak leaf, a pine cone): a ripe paper birch catkin, the cone of winged seeds the
    tree sheds, lying across one of its leaves, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.6, shade=0.3)
    mat, g = tr.tk.new_material("BirchCatkinSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Brown scales, some a shade greener or redder, paler and drier toward their lobes' tips, darker deep down
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.27, 0.17, 0.09), (0.42, 0.3, 0.16))
    col = g.mix(g.ramp(rv, 0.82, 0.95), col, (0.33, 0.3, 0.13))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.45, 1.0), 0.7), col, (0.62, 0.5, 0.33))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.35, 0.0), 0.6), col, (0.1, 0.06, 0.035))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(400.0, detail=3.0), 0.55, 0.8), 0.35), col, (0.15, 0.1, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.75, g.bump(g.noise(300.0, detail=4.0), 0.3, 0.0004))
    mats["catkin"] = mat

    m = tr.Mesh()
    # The leaf, leaning back up to the left, its stalk at the bottom right, turned and curled so the light rakes it
    stalk = Vector((0.03, 0.004, -0.032))
    tr.twig(m, [Vector((0.038, 0.004, -0.044)), stalk], [0.0009, 0.0008], "petiole", 5)
    tr.blade(m, stalk, Vector((-0.5, 0.0, 0.85)), Vector((0.35, -1.0, 0.1)), 0.075, 0.053, leaf_profile, "leaf",
             teeth=13, tooth=0.05, fold=0.24, arch=0.22, twist=-18.0, rows=16, rnd_value=0.45)
    # The catkin, 6 cm on a short stalk (a big one: it's the seed), crossing in front from the top right: scales in
    # a tight spiral round a core, each pointing down the cone and overlapping the next
    top, tip = Vector((0.033, -0.016, 0.034)), Vector((-0.01, -0.022, -0.016))
    axis = (tip - top).normalized()
    tr.twig(m, [top - axis * 0.012 + Vector((0.0, 0.0, 0.004)), top - axis * 0.004, top], [0.0013, 0.0012, 0.0014],
            "twig", 6)
    core = [top.lerp(tip, i / 8) for i in range(9)]
    tr.twig(m, core, [0.0042 * (1.0 - 0.5 * (i / 8) ** 3) for i in range(9)], "catkin", 8)
    _, u, v = tr.basis(axis)
    rnd = random.Random(7)
    count = 210
    for i in range(count):
        # Not quite regular: each scale a little off its place in the spiral, its own size, splay and tilt
        f = min(0.97, 0.03 + 0.94 * (i + rnd.uniform(-0.4, 0.4)) / count)
        a = i * tr.GOLDEN + rnd.uniform(-0.25, 0.25)
        out = u * math.cos(a) + v * math.sin(a)
        r = 0.0042 * (1.0 - 0.45 * max(0.0, f - 0.75) / 0.25) * (1.0 - 0.35 * max(0.0, 0.12 - f) / 0.12)
        base = top.lerp(tip, f) + out * r * rnd.uniform(0.7, 0.9)
        splay = rnd.uniform(0.45, 0.7)
        side = out.cross(axis) * rnd.uniform(-0.15, 0.15)
        tr.blade(m, base, (out * splay + axis * 0.83 + side).normalized(), out, 0.0068 * rnd.uniform(0.85, 1.15),
                 0.0075 * rnd.uniform(0.85, 1.1), trilobe, "catkin", fold=rnd.uniform(0.15, 0.35),
                 arch=rnd.uniform(-0.25, -0.05), twist=rnd.uniform(-15.0, 15.0), rows=4, rnd_value=rnd.random())
    obj = m.build("BirchSeedIcon", mats)
    # zkit's icon lights are set for something half a metre across round (0, 0, 0.3); centered on the leaf and catkin
    obj.scale = (7.0, 7.0, 7.0)
    obj.location = (-0.05, 0.0, 0.31)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.62)
    tr.tk.icon(cam, os.path.join(FOLDER, "BirchSeed_Icon.png"), hide=())
    print("[birch] icon written")


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
    mats = {name: tr.textured(name, paths(name)) for name in ("BirchBark", "BirchBarkFoot", "BirchBarkTwig")}
    mats = {"bark": mats["BirchBark"], "foot": mats["BirchBarkFoot"], "twig": mats["BirchBarkTwig"],
            "leaves": tr.textured("BirchLeaves", paths("BirchLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    for name, seed, make in VARIANTS:
        tree = tr.grow(make(), seed, name)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[birch] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("birch01", lods[0], PREVIEWS, figure)
    tr.preview_lods("birch01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("birch", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[birch] done")


main()
