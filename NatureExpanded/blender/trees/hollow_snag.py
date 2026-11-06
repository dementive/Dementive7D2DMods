"""Hollow snags for the wasteland, the burnt forest and the forest, on treekit.py (charred_snag.py is the nearest
relative; TREES.md has the rules).

Standing dead trees weathered, not burnt: the bark long since sloughed off in sheets and the bleached grey-silver and
tan wood left bare, checked deep along the grain and twisted by its spiral; dark plates of bark still clinging low on
the trunk, moss at the foot; a few broken limb stubs; the top snapped off in a crown of splinters. Woodpeckers have
been at them: columns of round holes (3-8 cm, dark, a pale rim) and one big oval pileated-woodpecker cavity, and in the
fattest a deep rot hollow opening at the foot. Tiered bracket fungus (brown bands above, pale pores beneath) grows on
the sides. Forms: 01 tall straight with the hole column, 02 a thick one with the open hollow at its foot, 03 a
leaning stump-top with a splintered crown, 04 forked (one fork snapped, the other with a few dead limbs). No seedling
or seed (a dead tree has none; vanilla's dead trees drop none).

    blender -b --factory-startup --python trees/hollow_snag.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees` (absolute
paths). Steps: `all`, `textures` (all the maps), `bark` (the trunk's bark and foot), `patches` (holes, hollow and
fungus), `small` (limb and splinter wood), `trees`. It writes Trees/HollowSnag/ (maps, HollowSnag01..04 with their
impostors), the HollowSnag lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size in game.

The holes, the hollow and the fungus are patches added through the kit's scar hook (as wolf_oak.py's knot hollow): a
rectangle of the texture laid over the trunk, lifted a finger's width off it, or small shelves of geometry.
"""
import math
import os
import random
import sys

import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import treekit as tr  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
TREES, PREVIEWS = args[0], args[1]
STEPS = args[2] if len(args) > 2 else "all"
FOLDER = os.path.join(TREES, "HollowSnag")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- textures
#
# HollowSnagBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii, drawn at its size on a
# 32 cm radius trunk (about 20 px per cm), spiralling (TWIST). HollowSnagBarkFoot is the same map with moss, damp and
# more clinging bark over its lower rows (v under .5, a trunk's v counts from the ground), and the main bark untouched
# above, so the change can't be seen. HollowSnagBarkTwig: 512 x 1024, limbs under 3.5 cm radius. HollowSnagBarkSplint:
# the pale wood of a snapped end or a splinter. HollowSnagBarkPeck / PeckB: patches (holes). HollowSnagBarkRot: the
# hollow's patch. HollowSnagBarkFungus: the bracket fungus.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 32.0
PX = WRAPS * W / (TAU * R_DESIGN)
TWIST = 0.2
FOOT_V = 0.52
TWIG_R = 0.035
WOOD_MEAN = (116, 108, 98)
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "foot": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
    "splint": tr.BarkUV(k=4.0 * math.pi),
}


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


def save(name, col, hpx, rough, occ, strength, blur=0.5):
    p = paths(name)
    tr.write_png(p["albedo"], col)
    tr.write_png(p["normal"], tr.normal_map(tr.blur(hpx, blur), strength))
    zero = np.zeros_like(rough)
    tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))


def wrapped(canvas_hw, x, y, hw_, hh_):
    h, w = canvas_hw
    return (np.arange(int(y) - hh_, int(y) + hh_ + 1)) % h, (np.arange(int(x) - hw_, int(x) + hw_ + 1)) % w


def vcrack(canvas, r, x, y, length, thick, cm, value=1.0):
    """A check running up the grain: short vertical lens pieces end to end, wandering a little sideways, thickest in
    the middle and pinching out at both ends."""
    seg = max(2.0, 3.5 * cm)
    n = max(1, int(length / seg))
    for i in range(n):
        t = math.sin(math.pi * (i + 0.5) / n) ** 0.7
        th = max(1.2, thick * t)
        tr.stamp(canvas, x, y, tr.lens(seg * 1.5, th, ends=0.7).T * value)
        x += r.normal(0.0, 0.08 * cm)
        y += seg * 0.85


def wood_layer(r, h, w, cm, checks=1.0, tan=0.3, grain=1.0):
    """Weathered dead wood as (albedo sRGB, height in mm, roughness), tileable, `cm` pixels per cm, the grain running
    up the rows: silver-grey to warm tan in long streaks, thin wavy ridges between worn grooves (grain contour lines),
    shallow wide erosion channels, long deep checks along the grain (the point of it) with medium and hairline ones,
    a few knots, brown rain stains and pixel-level fibre and grit."""
    area = (w / cm) * (h / cm)
    Yi, Xi = np.indices((h, w))
    sway = tr.fbm(r, h, w, (16 * cm, 45 * cm), 3)
    sway2 = tr.fbm(r, h, w, (5 * cm, 20 * cm), 3)

    def wavy(a, amount):
        dx = ((sway - 0.5) * amount * cm + (sway2 - 0.5) * 0.4 * amount * cm).astype(np.int64)
        return a[Yi, (Xi + dx) % w]

    tone = wavy(tr.fbm(r, h, w, (10 * cm, 34 * cm), 3), 7.0)
    tone2 = wavy(tr.fbm(r, h, w, (3.0 * cm, 16 * cm), 4), 5.0)
    g1 = wavy(tr.fbm(r, h, w, (1.5 * cm, 30 * cm), 5, 0.55), 6.0)
    g2 = wavy(tr.fbm(r, h, w, (5.0 * cm, 70 * cm), 4), 8.0)
    g3 = wavy(tr.fbm(r, h, w, (0.6 * cm, 12 * cm), 4), 5.0)
    s1 = np.abs(np.sin(np.pi * g1 * 9.0))
    ridge1 = tr.smoothstep(0.0, 0.7, s1)
    groove1 = 1.0 - tr.smoothstep(0.0, 0.2, s1)
    s2 = np.abs(np.sin(np.pi * g2 * 5.0))
    groove2 = 1.0 - tr.smoothstep(0.0, 0.28, s2)
    ridge2 = tr.smoothstep(0.0, 0.8, s2)
    s3 = np.abs(np.sin(np.pi * g3 * 13.0))
    groove3 = 1.0 - tr.smoothstep(0.0, 0.25, s3)
    ridge3 = tr.smoothstep(0.0, 0.8, s3)
    del s1, s2, s3, g1, g2, g3
    fib = tr.fbm(r, h, w, (0.06 * cm, 1.6 * cm), 3)
    grit = tr.fbm(r, h, w, (0.07 * cm, 0.07 * cm), 2)
    chan = tr.smoothstep(0.6, 0.74, wavy(tr.fbm(r, h, w, (2.8 * cm, 60 * cm), 3), 6.0))
    stain = tr.smoothstep(0.6, 0.8, wavy(tr.fbm(r, h, w, (0.9 * cm, 60 * cm), 4), 5.0)) * tr.smoothstep(0.3, 0.7, tone2)
    del Yi, Xi, sway, sway2

    crack = np.zeros((h, w))
    for lo, hi, n_per_k, thick in ((40, 150, 2.2, (0.2, 0.7)), (8, 40, 9.0, (0.1, 0.4)), (1.5, 8, 24.0, (0.05, 0.2))):
        for _ in range(int(area / 1000.0 * n_per_k * checks)):
            vcrack(crack, r, r.uniform(0, w), r.uniform(0, h), r.uniform(lo, hi) * cm,
                   r.uniform(*thick) * cm, cm, r.uniform(0.7, 1.0))
    kn_bump = np.zeros((h, w))
    kn_core = np.zeros((h, w))
    for _ in range(int(area / 6000.0)):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        rho = r.uniform(1.3, 3.5)
        rx, ry = rho * cm, rho * cm * r.uniform(1.3, 2.0)
        ys, xs = wrapped((h, w), cx, cy, int(rx * 3.0), int(ry * 3.0))
        dx = (np.arange(-int(rx * 3.0), int(rx * 3.0) + 1) + (int(cx) - cx))[None, :] / rx
        dy = (np.arange(-int(ry * 3.0), int(ry * 3.0) + 1) + (int(cy) - cy))[:, None] / ry
        e = np.hypot(dx, dy)
        ix = np.ix_(ys, xs)
        kn_bump[ix] = np.maximum(kn_bump[ix], np.exp(-(e / 0.9) ** 2))
        hole = r.random() < 0.4
        kn_core[ix] = np.maximum(kn_core[ix], tr.smoothstep(0.7, 0.4, e + 0.15 * np.sin(7.0 * np.arctan2(dy, dx))) * (0.7 if hole else 0.3))

    silver, tn = np.array((0.60, 0.58, 0.55)), np.array((0.66, 0.54, 0.40))
    col = tr.mix(silver, tn, tan * tr.smoothstep(0.45, 0.85, tone))
    lum = 0.74 + 0.5 * (0.4 * tone2 + 0.2 * grit + 0.2 * fib + 0.2 * ridge3)
    col = col * lum[..., None]
    col = col * (1.0 + grain * (0.22 * (ridge1 - 0.5) + 0.12 * (ridge2 - 0.5) + 0.14 * (ridge3 - 0.5)))[..., None]
    col = tr.mix(col, col * 0.5, (groove1 * 0.6)[..., None])
    col = tr.mix(col, col * 0.62, groove2 * 0.45)
    col = tr.mix(col, col * 0.7, groove3 * 0.4)
    col = tr.mix(col, (0.36, 0.28, 0.2) * (0.7 + 0.3 * grit)[..., None], chan * 0.5)
    col = tr.mix(col, (0.26, 0.19, 0.13), stain * 0.5)
    crk = np.clip(crack, 0, 1)
    col = tr.mix(col, (0.1, 0.075, 0.055), crk * 0.93)
    col = tr.mix(col, (0.2, 0.14, 0.1), kn_bump * 0.35)
    col = tr.mix(col, (0.1, 0.07, 0.05), kn_core * 0.9)
    col = col * (0.93 + 0.14 * fib)[..., None]
    hmm = (0.5 * ridge1 + 0.9 * ridge2 + 0.35 * ridge3 - 4.5 * chan - 7.0 * crk + 0.7 * fib + 0.3 * grit
           + 2.2 * kn_bump - 3.0 * kn_core)
    rough = 0.88 + 0.1 * chan + 0.05 * (grit - 0.5)
    return np.clip(col, 0.0, 1.0), hmm, np.clip(rough, 0.0, 1.0)


def finish(col, hmm, rough, cm, wood_mask=None, cav=0.5):
    hpx = hmm * cm / 10.0
    occ = tr.cavity(hpx, cav * cm, 0.05)
    col = col * (0.72 + 0.28 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), hpx, np.clip(rough, 0.0, 1.0), occ


def trunk_bark(seed, foot, k=None):
    """The trunk's bark map (or its foot): weathered wood with plates of the old bark still clinging here and there,
    dark, furrowed, grey on top; around each plate the wood stained and shadowed. The foot has more bark, moss in the
    grooves and a damp darkening over its lower rows. Returns (albedo, height px, roughness, occlusion, graded
    factors, wood mask)."""
    r = np.random.default_rng(seed)
    h, w, cm = H, W, PX
    col, hmm, rough = wood_layer(r, h, w, cm)
    sz = 6.5 * cm
    warp = ((tr.fbm(r, h, w, (1.2 * sz, 3.0 * sz), 3) - 0.5) * 0.55 * sz,
            (tr.fbm(r, h, w, (1.2 * sz, 3.0 * sz), 3) - 0.5) * 1.1 * sz)
    pe, pidx, _, _ = tr.cells(r, h, w, sz, 4.0, warp)
    rnd = r.random(pidx.max() + 1)[pidx]
    region = tr.fbm(r, h, w, (30 * cm, 70 * cm), 3)
    bite = tr.fbm(r, h, w, (2.5 * cm, 9 * cm), 3)
    ragged = (tr.fbm(r, h, w, (0.8 * cm, 3 * cm), 3) - 0.5) * 1.6 * cm
    vv = (np.arange(h) + 0.5) / h
    fall = (1.0 - tr.smoothstep(0.16, 0.48, vv))[:, None]
    fall2 = fall * fall
    cover = 0.075 + (0.3 * fall if foot else 0.0)
    present = (rnd + 0.8 * (region - 0.5)) < cover
    S = tr.smoothstep(0.0, 0.35 * cm, pe + ragged) * present * tr.smoothstep(0.2, 0.3, bite)
    del present, ragged, region
    # the bark
    vary = tr.fbm(r, h, w, (1.5 * sz, 4 * sz), 3)
    fw = (0.04 + 0.12 * vary) * sz
    furrow = 1.0 - tr.smoothstep(0.0, fw, pe)
    dome = tr.smoothstep(0.0, 0.33 * sz, pe)
    fibre = tr.fbm(r, h, w, (0.07 * cm, 2.2 * cm), 3)
    streak = tr.fbm(r, h, w, (0.5 * cm, 9 * cm), 3)
    grit = tr.fbm(r, h, w, (0.07 * cm, 0.07 * cm), 2)
    grey = tr.smoothstep(0.4, 0.75, tr.fbm(r, h, w, (2.5 * sz, 4 * sz), 3))
    # long fibrous ridges up the plates (contours of stretched noise), cross checks, grit
    rwarp = ((tr.fbm(r, h, w, (1.5 * cm, 9 * cm), 3) - 0.5) * 0.9 * cm, (tr.fbm(r, h, w, (3 * cm, 12 * cm), 3) - 0.5) * 3.0 * cm)
    re_, _, _, _ = tr.cells(r, h, w, 1.5 * cm, 9.0, rwarp)
    ridge = tr.smoothstep(0.0, 0.5 * cm, re_) * (1.0 - 0.8 * (1.0 - tr.smoothstep(0.0, 0.14 * cm, re_)))
    rg = None
    xch = np.zeros((h, w))
    for _ in range(int(h / cm * w / cm * 0.05)):
        tr.stamp_lens(xch, r.uniform(0, w), r.uniform(0, h), r.uniform(0.6, 2.2) * cm,
                      max(1.3, r.uniform(0.07, 0.14) * cm), r.uniform(0.6, 1.0), ends=0.8)
    xch = np.clip(xch, 0, 1)
    base = tr.mix((0.2, 0.15, 0.115), (0.4, 0.31, 0.24), 0.1 + 0.75 * rnd)
    base = tr.mix(base, (0.5, 0.47, 0.43), (grey * (0.35 + 0.5 * dome))[..., None] * 0.6)
    bcol = base * (0.38 + 0.2 * streak + 0.35 * fibre + 0.6 * ridge + 0.14 * grit)[..., None]
    bcol = tr.mix(bcol, (0.05, 0.04, 0.035), np.clip(furrow * 1.1 + 0.55 * xch, 0, 1)[..., None])
    bh = 5.0 + 2.6 * dome - 3.5 * furrow - 1.4 * xch + 2.6 * ridge + 0.5 * fibre + 0.6 * streak + 0.2 * grit
    del base, grey, vary, fw, fibre, streak, dome, rg, ridge, xch
    # stain and shadow round each plate on the wood
    halo = tr.blur(S, 0.9 * cm) * (1.0 - S)
    col = col * (1.0 - 0.45 * halo)[..., None]
    col = tr.mix(col, (0.4, 0.3, 0.21), halo * 0.3)
    wmask = (1.0 - S)
    col = tr.mix(col, bcol, S)
    hmm = hmm * (1.0 - S) + S * bh
    rough = rough * (1.0 - S) + S * 0.93
    del bcol, bh, halo, pe, pidx, rnd
    # pale lichen crusts on the wood
    lich = (tr.smoothstep(0.78, 0.9, tr.fbm(r, h, w, (0.5 * cm, 0.5 * cm), 4))
            * tr.smoothstep(0.45, 0.7, tr.fbm(r, h, w, (9 * cm, 12 * cm), 3)) * (1.0 - S))
    col = tr.mix(col, (0.5, 0.54, 0.44), lich * 0.5)
    # moss and damp over the lower rows
    mossn = (tr.smoothstep(0.52, 0.7, tr.fbm(r, h, w, (1.2 * cm, 2.5 * cm), 4))
             * tr.smoothstep(0.42, 0.64, tr.fbm(r, h, w, (12 * cm, 25 * cm), 3)))
    if foot:
        ma = np.clip(mossn * fall * 0.9, 0.0, 1.0)
        col = col * (1.0 - 0.32 * fall2)[..., None]
        col = tr.mix(col, np.array((0.17, 0.22, 0.1)) * (0.6 + 0.8 * grit)[..., None], ma * 0.75)
        hmm = hmm + 0.9 * ma * 1.0
        rough = rough * (1.0 - ma) + 0.95 * ma
        wmask = wmask * (1.0 - ma)
    col, hpx, rough, occ = finish(col, hmm, rough, cm)
    if k is None:
        graded, k = tr.match_mean(col, WOOD_MEAN, wmask > 0.5)
    else:
        graded = np.clip(col * k, 0.0, 1.0)
    return graded, hpx, rough, occ, k


def make_bark():
    col, hpx, rough, occ, k = trunk_bark(41, False)
    print("[hollow_snag] bark graded by %s" % np.round(k, 3))
    save("HollowSnagBark", col, hpx, rough, occ, 1.6)
    h, w = col.shape[:2]
    tr.write_png(os.path.join(PREVIEWS, "hollow_snag_bark_all.png"), col[::4, ::4])
    tr.write_png(os.path.join(PREVIEWS, "hollow_snag_bark_1to1.png"), col[h // 2 - 400:h // 2 + 400, 300:1500])
    del col, hpx, rough, occ
    col, hpx, rough, occ, _ = trunk_bark(41, True, k)
    save("HollowSnagBarkFoot", col, hpx, rough, occ, 1.6)
    tr.write_png(os.path.join(PREVIEWS, "hollow_snag_foot_1to1.png"), col[300:1100, 300:1500])
    return k


def small_wood(seed, h, w, radius_cm, checks, tan, light=1.0):
    r = np.random.default_rng(seed)
    cm = w / (TAU * radius_cm)
    col, hmm, rough = wood_layer(r, h, w, cm, checks=checks, tan=tan)
    col = np.clip(col * light, 0.0, 1.0)
    col, _ = tr.match_mean(col, np.array(WOOD_MEAN) * light)
    return finish(col, hmm, rough, cm, cav=0.4)


def make_small():
    c, hpx, rough, occ = small_wood(53, 1024, 512, 3.0, 0.8, 0.3)
    save("HollowSnagBarkTwig", c, hpx, rough, occ, 1.3)
    c, hpx, rough, occ = small_wood(59, 1024, 512, 2.0, 0.9, 0.7, 1.12)
    save("HollowSnagBarkSplint", c, hpx, rough, occ, 1.4)


# ---------------------------------------------------------------- patches

PCM = 16.0  # px per cm of the holes' patch
PECK = {"BarkPeck": (704, 1792), "BarkPeckB": (704, 1152)}
RW, RH, RCM = 1120, 2240, 14.0  # the hollow's patch: 80 x 160 cm


def wavy_edge(r, h, w, cm, amount):
    return (tr.fbm(r, h, w, (3 * cm, 3 * cm), 4) - 0.5) * amount


def hole(col, hmm, rough, occ, X, Y, cx, cy, rx, ry, jitter, dark=1.0, rim=0.9):
    """One round hole into the wood at (cx, cy) cm, half-sizes rx, ry: the inside soot-dark, a pale fresh-cut rim
    round it, a lighter crescent at the bottom lip where the sky reaches in."""
    d = np.hypot((X - cx) / rx, (Y - cy) / ry) + jitter
    inner = 1.0 - tr.smoothstep(0.88, 1.0, d)
    ring = tr.smoothstep(0.82, 1.0, d) * (1.0 - tr.smoothstep(1.0, 1.0 + rim / min(rx, ry) * 1.0, d))
    halo = tr.smoothstep(1.0, 1.0 + 3.0 * rim / min(rx, ry), d) * 0.0
    depth = np.clip(1.0 - d, 0.0, 1.0)
    inside = (0.028 + 0.03 * np.clip((Y - cy) / ry * -0.5 + 0.5, 0, 1)) * dark
    col[:] = tr.mix(col, (0.58, 0.46, 0.3), ring * 0.8)
    col[:] = tr.mix(col, np.stack([inside, inside * 0.82, inside * 0.65], -1), inner)
    crescent = inner * tr.smoothstep(-0.45, -0.85, (Y - cy) / ry) * 0.6
    col[:] = tr.mix(col, (0.3, 0.23, 0.15), crescent * 0.5)
    hmm[:] = hmm - 8.0 * inner * (0.6 + 0.4 * depth) + 1.8 * ring
    rough[:] = np.where(inner > 0.3, 0.97, rough)
    occ[:] = np.clip(occ * (1.0 - 0.92 * inner * (0.5 + 0.5 * depth)), 0.0, 1.0)


def peck_patch(name, seed, layout):
    w, h = PECK[name]
    r = np.random.default_rng(seed)
    cm = PCM
    col, hmm, rough = wood_layer(r, h, w, cm, checks=0.9)
    col, _ = tr.match_mean(col, WOOD_MEAN)
    occ = np.ones((h, w))
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    X = (X + 0.5 - w / 2) / cm
    Y = (Y + 0.5 - h / 2) / cm
    jit = (tr.fbm(r, h, w, (4 * cm, 4 * cm), 4) - 0.5) * 0.16
    for (cx, cy, rx, ry) in layout:
        hole(col, hmm, rough, occ, X, Y, cx, cy, rx, ry, jit)
    # a little fresh sawdust and chips under the holes' column is not on a standing trunk: just darker grime below
    col, hpx, rough, occ2 = finish(col, hmm, rough, cm, cav=0.4)
    return col, hpx, rough, np.minimum(occ, occ2)


def peck_layouts():
    """The holes of the two patch maps ((x, y, half width, half height) in cm from the map's middle), the same every
    time: the column (with the big oval cavity first) and the loose cluster."""
    r = np.random.default_rng(7)
    col_layout = [(0.3, 36.0, 5.4, 11.0)]
    y = 12.0
    for i, rr in enumerate((3.4, 2.2, 3.8, 1.8, 2.9, 2.0, 3.2)):
        col_layout.append((r.normal(0.0, 1.1), y, rr, rr * r.uniform(0.95, 1.2)))
        y -= rr + 5.5 + r.uniform(0.5, 3.5)
    clus = []
    for _ in range(40):
        a, rad = r.uniform(0, TAU), 20.0 * math.sqrt(r.random())
        rr = r.uniform(1.4, 3.6)
        p = (rad * math.cos(a), 6.0 + rad * 0.9 * math.sin(a))
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) > rr + q[2] + 3.5 for q in clus):
            clus.append((p[0], p[1], rr, rr * r.uniform(0.9, 1.25)))
        if len(clus) >= 9:
            break
    return col_layout, clus


def make_patches():
    col_layout, clus = peck_layouts()
    c, hpx, rough, occ = peck_patch("BarkPeck", 61, col_layout)
    save("HollowSnagBarkPeck", c, hpx, rough, occ, 1.6)
    tr.write_png(os.path.join(PREVIEWS, "hollow_snag_peck_view.png"), c[::2, ::2])
    c, hpx, rough, occ = peck_patch("BarkPeckB", 67, clus)
    save("HollowSnagBarkPeckB", c, hpx, rough, occ, 1.6)
    make_rot()
    make_fungus()


def make_rot():
    """The foot hollow's patch: a tall opening, widest at the ground and narrowing to a point, its edge ragged and
    splintering, the inside black with the rotted wood showing in long fibres, punky pale floor and litter at the
    bottom; the rim around it silver splinters standing up."""
    r = np.random.default_rng(71)
    h, w, cm = RH, RW, RCM
    col, hmm, rough = wood_layer(r, h, w, cm, checks=1.1)
    col, _ = tr.match_mean(col, WOOD_MEAN)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    X = (X + 0.5 - w / 2) / cm
    Y = (Y + 0.5 - h / 2) / cm
    t = np.clip((Y + 72.0) / 134.0, 0.0, 1.0)
    half = 23.0 * np.sqrt(np.clip(1.0 - t ** 1.5, 0.0, 1.0)) + 1.0
    lean_x = 3.0 * t * t
    rag = (tr.fbm(r, h, w, (2.0 * cm, 6 * cm), 4) - 0.5) * 7.0 + (tr.fbm(r, h, w, (0.5 * cm, 1.5 * cm), 3) - 0.5) * 3.0
    dx = np.abs(X - lean_x)
    sd = dx - (half + rag)                       # signed distance-ish: < 0 inside the opening
    top = (Y - 62.0) / 6.0
    inner = (1.0 - tr.smoothstep(-0.6, 0.6, sd)) * (1.0 - tr.smoothstep(0.0, 1.0, top)) * tr.smoothstep(-80.0, -70.0, Y)
    rim = tr.smoothstep(-0.5, 0.5, sd) * (1.0 - tr.smoothstep(2.0, 7.0, sd))
    # the rim: lighter splinters running up
    spl = tr.fbm(r, h, w, (0.15 * cm, 5.0 * cm), 4)
    col = tr.mix(col, tr.mix((0.5, 0.45, 0.38), (0.68, 0.62, 0.52), spl), rim * 0.85)
    shadow = np.clip(1.0 - tr.smoothstep(0.0, 5.0, -sd), 0.0, 1.0)
    # inside: black, long fibres of rotted wood, lighter punky floor and litter low down
    fib = tr.fbm(r, h, w, (0.2 * cm, 6 * cm), 4)
    punk = tr.mix((0.07, 0.05, 0.035), (0.3, 0.22, 0.14), tr.smoothstep(0.35, 0.8, fib))
    floorm = tr.smoothstep(-48.0, -72.0, Y) * (0.5 + 0.5 * tr.fbm(r, h, w, (1.5 * cm, 3 * cm), 3))
    ins = tr.mix(punk, (0.3, 0.23, 0.16) * (0.6 + 0.6 * fib)[..., None], floorm[..., None] * 0.9)
    dark = np.clip(0.1 + 0.9 * tr.smoothstep(0.0, 12.0, -sd), 0.0, 1.0) * tr.smoothstep(-70.0, 30.0, Y)
    ins = ins * (1.0 - 0.72 * dark[..., None] * (1.0 - 0.6 * floorm)[..., None])
    col = tr.mix(col, ins, inner)
    hmm = hmm + 8.0 * rim * (0.6 + 0.8 * spl) - 24.0 * inner + 3.0 * inner * fib
    rough = np.where(inner > 0.3, 0.98, rough)
    occ = np.clip(1.0 - 0.95 * inner * (0.3 + 0.7 * tr.smoothstep(0.0, 6.0, -sd)) - 0.2 * shadow * (1 - inner), 0.0, 1.0)
    c, hpx, rough, occ2 = finish(col, hmm, rough, cm, cav=0.5)
    save("HollowSnagBarkRot", c, hpx, rough, np.minimum(occ, occ2), 1.5 * cm / 16.0)
    tr.write_png(os.path.join(PREVIEWS, "hollow_snag_rot_view.png"), c[::2, ::2])


def make_fungus():
    """512 x 512: the top of a bracket in the upper half (v 1 at the trunk, .52 at the rim): concentric zones of dark
    brown, rust and tan, finely furrowed, a pale tan growing edge; the rim band at v .5; and the cream pored underside
    below (v .45 at the trunk, 0 at the rim)."""
    r = np.random.default_rng(83)
    h = w = 512
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    v = (Y + 0.5) / h
    u = (X + 0.5) / w
    top = v > 0.5
    d = np.clip((1.0 - v) / 0.5, 0.0, 1.0)      # 0 at the trunk, 1 at the rim (top half)
    noise = (r.standard_normal((h, w)))
    fine = tr.fbm(r, h, w, (3, 3), 3)
    band = tr.fbm(r, h, w, (60, 6), 3) - 0.5
    z = d * 7.5 + band * 1.6 + (fine - 0.5) * 0.4
    zone = 0.5 + 0.5 * np.sin(z * math.pi * 1.0)
    zi = np.floor(z)
    shade = (np.sin(zi * 12.9898) * 43758.5453) % 1.0
    topc = tr.mix((0.07, 0.045, 0.032), (0.27, 0.15, 0.08), 0.25 + 0.6 * shade)
    topc = tr.mix(topc, (0.55, 0.4, 0.24), tr.smoothstep(0.85, 1.0, zone) * 0.5)
    topc = topc * (0.8 + 0.4 * fine)[..., None]
    topc = tr.mix(topc, (0.5, 0.4, 0.26), tr.smoothstep(0.92, 0.99, d))
    topc = tr.mix(topc, (0.07, 0.055, 0.045), (1 - tr.smoothstep(0.0, 0.12, d)))
    under = tr.mix((0.72, 0.64, 0.5), (0.82, 0.76, 0.62), tr.fbm(r, h, w, (4, 4), 3))
    pores = tr.smoothstep(0.55, 0.7, tr.fbm(r, h, w, (3, 3), 2))
    under = under * (0.88 + 0.12 * pores)[..., None]
    rim_band = (v >= 0.455) & (v <= 0.5)
    col = np.where(top[..., None], topc, under)
    col = np.where(rim_band[..., None], np.array((0.34, 0.25, 0.15)) * (0.85 + 0.3 * fine)[..., None], col)
    hmm = np.where(top, 2.0 * zone + 1.5 * fine - 1.5 * (1 - tr.smoothstep(0.0, 0.12, d)), 0.6 * pores)
    rough = np.where(top, 0.82, 0.9) * np.ones((h, w))
    occ = np.ones((h, w))
    c, hpx, rough, occ = finish(col, hmm, rough, 14.0, cav=0.5)
    save("HollowSnagBarkFungus", c, hpx, rough, occ, 1.0)


# ---------------------------------------------------------------- patch and bracket geometry
#
# PATCHES: tree name -> [(kind ("col" holes, "clus" holes, "rot" hollow), trunk index, height of the centre, azimuth, flip)]
# FUNGUS: tree name -> [(trunk index, height of the lowest bracket, azimuth, tiers, radius of the lowest bracket)]

PATCHES = {}
FUNGUS = {}


def surface(t, z, a):
    """Centre of trunk `t` at height z and its horizontal radius toward azimuth `a` (the tube's circle, stretched in a
    leaning trunk's horizontal section)."""
    s = t.s_at_height(z)
    p, d, r = t.at(s)
    lobes = getattr(t.spec, "lobes", (0, 0.0))
    fade = math.exp(-max(0.0, p.z) / max(t.spec.flare_height, 1e-3))
    swell = 0.65 * math.cos(lobes[0] * a) + 0.35 * math.cos((lobes[0] + 2) * a + 1.3) if lobes[0] else 0.0
    rr = r * (1.0 + lobes[1] * fade * swell)
    cz = max(abs(d.z), 0.3)
    sin2 = 1.0 - cz * cz
    phi = a - math.atan2(d.y, d.x)
    rr = rr / math.sqrt(max(1e-3, 1.0 - sin2 * math.cos(phi) ** 2))
    return Vector((p.x, p.y, z)), rr


def hole_patch(m, t, key, z0, az, hole, flip, lod):
    """An oval patch round one hole (3 cm past its rim), cut from the holes' map, laid on the trunk: the seam is a
    small ring round the hole, which reads as its chiselled rim."""
    cx, cy, rx, ry = hole
    name = "BarkPeck" if key == "peck" else "BarkPeckB"
    tw, th = PECK[name][0] / PCM, PECK[name][1] / PCM
    a, b = (rx + 3.0) / 100.0, (ry + 3.0) / 100.0
    sg = -1.0 if flip else 1.0
    zc = z0 + cy / 100.0
    _, rrc = surface(t, zc, az)
    azc = az + sg * cx / 100.0 / rrc
    ring_n, rings = (12, 2) if lod == 0 else (8, 1)
    lift = 0.012 if lod == 0 else 0.04
    grid = []
    for ri in range(rings + 1):
        f = ri / rings
        ring = []
        for k in range(ring_n if ri else 1):
            ph = TAU * k / ring_n
            dx, dz = math.cos(ph) * f * a, math.sin(ph) * f * b
            z = max(0.02, zc + dz)
            _, rr0 = surface(t, z, azc)
            ang = azc + dx / rr0
            p, rr = surface(t, z, ang)
            pos = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * (rr + lift)
            uv = (0.5 + (cx + sg * dx * 100.0) / tw, 0.5 + (cy + dz * 100.0) / th)
            ring.append((m.v(pos), uv))
        grid.append(ring)
    c0 = grid[0][0]
    for ri in range(1, rings + 1):
        prev, cur = grid[ri - 1], grid[ri]
        for k in range(ring_n):
            k1 = (k + 1) % ring_n
            if ri == 1:
                m.tri(c0[0], cur[k][0], cur[k1][0], (c0[1], cur[k][1], cur[k1][1]), key)
            else:
                m.quad(prev[k][0], cur[k][0], cur[k1][0], prev[k1][0], (prev[k][1], cur[k][1], cur[k1][1], prev[k1][1]), key)


def rot_patch(m, t, z0, az, lod):
    """The foot hollow's patch, cut to the opening's outline (a pointed arch, widest at the ground) plus a hand's
    width of rim, so its edge is the splintered rim."""
    cols, rows = (6, 12) if lod == 0 else (3, 6)
    lift = 0.012 if lod == 0 else 0.04
    tw, th = RW / RCM, RH / RCM
    grid = []
    for j in range(rows + 1):
        y = -76.0 + 140.0 * j / rows
        tt = min(1.0, max(0.0, (y + 72.0) / 134.0))
        half = 23.0 * math.sqrt(max(0.0, 1.0 - tt ** 1.5)) + 1.0 + 7.0
        lean = 3.0 * tt * tt
        z = max(0.02, z0 + y / 100.0)
        _, rr0 = surface(t, z, az)
        row = []
        for i in range(cols + 1):
            x = lean + (i / cols - 0.5) * 2.0 * half
            ang = az + x / 100.0 / rr0
            p, rr = surface(t, z, ang)
            pos = p + Vector((math.cos(ang), math.sin(ang), 0.0)) * (rr + lift)
            row.append((m.v(pos), (0.5 + x / tw, 0.5 + y / th)))
        grid.append(row)
    for j in range(rows):
        for i in range(cols):
            a, b, c, d = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
            m.quad(a[0], b[0], c[0], d[0], (a[1], b[1], c[1], d[1]), "rot")


def patch_quads(m, tree, lod):
    col, clus = peck_layouts()
    for kind, ti, z0, az, flip in PATCHES.get(tree.name, ()):
        t = tree.trunks[ti]
        if kind == "rot":
            rot_patch(m, t, z0, az, lod)
        else:
            for hole in (col if kind == "col" else clus):
                hole_patch(m, t, "peck" if kind == "col" else "peckb", z0, az, hole, flip, lod)


def oquad(m, a, b, c, d, uv, key, want):
    pa, pb, pc = (Vector(m.co[i]) for i in (a, b, c))
    if (pb - pa).cross(pc - pa).dot(want) < 0:
        a, b, c, d = a, d, c, b
        uv = (uv[0], uv[3], uv[2], uv[1])
    m.quad(a, b, c, d, uv, key)


def bracket(m, t, z, az, R, T, lod):
    """One shelf of bracket fungus on trunk `t`: a half-disc (about 1.3 R wide, R deep) hugging the trunk's curve."""
    n = 5 if lod == 0 else 3
    _, rr0 = surface(t, z, az)
    sv = [-1.0 + 2.0 * k / n for k in range(n + 1)]
    tilt = 0.1
    inner, outer = [], []
    for s in sv:
        a = az + s * R * 1.3 / rr0
        p, rr = surface(t, z, a)
        out = Vector((math.cos(a), math.sin(a), 0.0))
        depth = R * math.sqrt(max(0.0, 1.0 - s * s))
        i_pos = p + out * (rr - 0.012)
        o_pos = p + out * (rr + depth)
        inner.append((i_pos + Vector((0, 0, T * 0.6)), i_pos + Vector((0, 0, -T * 0.2)), out))
        outer.append((o_pos + Vector((0, 0, T * 0.12 - tilt * depth)), o_pos + Vector((0, 0, -T * 0.12 - tilt * depth)), out))
    ti = [m.v(i[0]) for i in inner]
    ib = [m.v(i[1]) for i in inner]
    to = [m.v(o[0]) for o in outer]
    ob = [m.v(o[1]) for o in outer]
    for k in range(n):
        u0, u1 = (sv[k] + 1) / 2, (sv[k + 1] + 1) / 2
        out = (inner[k][2] + inner[k + 1][2]).normalized()
        oquad(m, ti[k], ti[k + 1], to[k + 1], to[k], ((u0, 1.0), (u1, 1.0), (u1, 0.53), (u0, 0.53)), "fungus", Vector((0, 0, 1)))
        oquad(m, to[k], to[k + 1], ob[k + 1], ob[k], ((u0, 0.5), (u1, 0.5), (u1, 0.46), (u0, 0.46)), "fungus", out)
        oquad(m, ib[k], ib[k + 1], ob[k + 1], ob[k], ((u0, 0.44), (u1, 0.44), (u1, 0.03), (u0, 0.03)), "fungus", Vector((0, 0, -1)))


def fungus_quads(m, tree, lod):
    rnd = random.Random(tree.seed + 5)
    for ti, z, az, tiers, R in FUNGUS.get(tree.name, ()):
        t = tree.trunks[ti]
        for i in range(tiers):
            rr = R * (0.9 ** i) * rnd.uniform(0.85, 1.1)
            bracket(m, t, z + i * (0.1 + 0.04 * rnd.random()), az + rnd.uniform(-0.28, 0.28),
                    rr, rr * 0.4, lod)


_scar_quads = tr._scar_quads


def scar_quads(m, tree, lod, key="leaves"):
    _scar_quads(m, tree, lod, key)
    if lod <= 1:
        patch_quads(m, tree, lod)
        fungus_quads(m, tree, lod)


tr._scar_quads = scar_quads


# ---------------------------------------------------------------- the snags

def bark_key(br, s, r, z):
    """Splinters and the last stretch of a snapped end are pale bare wood; thin limbs get the twig map; a trunk's
    lower rows (v under FOOT_V) the foot map; the rest the main bark."""
    if "splinter" in br.tags:
        return "splint"
    if getattr(br.spec, "broken", False) and s > 1.0 - min(0.35, 0.5 * r / max(br.length, 1e-3)):
        return "splint"
    if br.level > 0 and r < TWIG_R:
        return "twig"
    if br.level == 0 and br.turns(s) / K + br.v0 < FOOT_V:
        return "foot"
    return "bark"


def limb_level(per_meter, length, span, radius_max=0.09, sides=(6, 5, 0), droop=0.15, name=None):
    return tr.Level(per_meter=per_meter, span=span, length=length, shape="conical", angle=78.0, angle_tip=58.0,
                    angle_vary=14.0, radius=0.3, radius_length=0.8, radius_max=radius_max, tip_radius=0.01,
                    broken=True, step=0.15, gravitropism=0.04, droop=droop, wander=0.3, floor=0.5, sides=sides,
                    seg=(0.5, 1.0, 9.0), min_length=0.1, min_len=(0.0, 0.3, 99.0))


def twig_level(per_meter):
    return tr.Level(per_meter=per_meter, span=(0.15, 0.85), length=(0.15, 0.7), shape="tapered", angle=50.0,
                    angle_vary=15.0, radius=0.45, radius_length=0.6, radius_max=0.014, tip_radius=0.002, step=0.08,
                    gravitropism=0.1, wander=0.5, sides=(4, 3, 0), seg=(0.25, 0.6, 9.0), min_length=0.1,
                    min_len=(0.0, 99.0, 99.0))


def splinter_level(count, length, span=(0.92, 0.995), angle=12.0, vary=12.0, radius=0.4):
    return tr.Level(count=count, span=span, length=length, angle=angle, angle_vary=vary, radius=radius,
                    radius_length=0.5, radius_max=0.09, tip_radius=0.004, step=0.1, wander=0.18,
                    tags=("splinter",), sides=(4, 3, 0), seg=(0.3, 0.6, 9.0), min_length=0.15,
                    min_len=(0.0, 0.5, 99.0))


def trunk(**kw):
    base = dict(flare=0.45, flare_height=0.5, lobes=(5, 0.08), taper=0.9, broken=True, wander=0.09,
                sides=(14, 9, 6), seg=(0.7, 1.4, 3.0), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    t = tr.Trunk(**base)
    t.flutes = (4, 0.035, 4 * TAU * TWIST / K)  # the spiral grain's ridges and hollows
    return t


def snag(trunks, limbs=1.1, reach=1.2, splinters=(9, 13), spl_len=(0.4, 2.2), twigs=0.5, budget=3800,
         span=(0.12, 0.93), spl_kw=None):
    lv = limb_level(limbs, (0.1 * reach, 1.4 * reach), span)
    return tr.TreeSpec(trunks=trunks, levels=[lv, twig_level(twigs)],
                       stubs=splinter_level(splinters, spl_len, **(spl_kw or {})), budget=budget,
                       bark_budget=budget, bark_key=bark_key, bark_uv=UV, ground_v=0.0)


FORKS = {}  # variant name -> fork spec for post_grow


def add_fork(tree, z, az, length, tip, base_factor=0.85, angle=24.0, grav=0.2, limbs=None):
    """A second leader forking off trunk 0 at height z (a real fork, which the kit's trunks can't make): grown after
    the tree, snapped off at the top with splinters, optionally with dead limbs."""
    rnd = random.Random(tree.seed + 77)
    t = tree.trunks[0]
    s = t.s_at_height(z)
    p, tan, r = t.at(s)
    out = Vector((math.cos(az), math.sin(az), 0.0))
    d = (tan * math.cos(math.radians(angle)) + out * math.sin(math.radians(angle))).normalized()
    pts = tr.grow_path(rnd, p, d, length, 0.4, grav, 0.0, 0.05, 0.5)
    lv = tr.Level(sides=(12, 8, 5), seg=(0.7, 1.4, 3.0), min_len=(0.0, 0.0, 0.0), broken=True)
    fork = tr.Branch(pts, tr._radii(r * base_factor, tip, len(pts), 0.9), 1, t, s, lv, rnd)
    fork.tags.add("fork")
    new = [fork]
    new += tr.grow_children(rnd, tree, fork, splinter_level((6, 9), (0.3, 1.3)), 2)
    if limbs is not None:
        new += tr.grow_children(rnd, tree, fork, limbs, 2)
    for b in new:
        for lod in range(3):
            ok = b.spec.sides[lod] >= 3 and b.length >= b.spec.min_len[lod]
            b.keep[lod] = ok and (b.parent is None or b.parent.keep[lod])
    tree.branches += new
    return fork


def v01():
    return snag([trunk(height=19.0, radius=0.27, tip_radius=0.1, lean=(0.5, -0.3), bow=0.05)])


def v02():
    return snag([trunk(height=12.0, radius=0.42, tip_radius=0.2, taper=0.7, lean=(0.2, 0.1), lobes=(0, 0.0),
                       flare=0.55, sides=(16, 10, 7), seg=(0.6, 1.2, 3.0))],
                limbs=0.9, reach=1.0, splinters=(8, 12), spl_len=(0.3, 1.6), budget=3800)


def v03():
    return snag([trunk(height=9.0, radius=0.3, tip_radius=0.2, taper=0.45, lean=(2.4, 0.9), bow=0.1)],
                limbs=0.9, reach=1.0, splinters=(11, 15), spl_len=(0.2, 1.6), budget=3600,
                spl_kw=dict(angle=16.0, vary=18.0, radius=0.42, span=(0.88, 0.995)))


def v04():
    return snag([trunk(height=14.0, radius=0.3, tip_radius=0.08, lean=(-0.4, 0.5), bow=0.1)],
                limbs=0.8, reach=1.1, splinters=(8, 12), budget=4200, span=(0.12, 0.3))


def post04(tree):
    # the snapped fork at 4.6 m, 8 m long; the dead-limbed leader above the fork carries longer dead limbs
    rnd = random.Random(tree.seed + 31)
    t = tree.trunks[0]
    # limbs on the main leader above the fork (the stubs level only covers its lower part)
    lv2 = tr.Level(count=7, span=(0.42, 0.93), length=(0.5, 2.4), shape="tapered", angle=70.0, angle_tip=50.0,
                   angle_vary=14.0, radius=0.3, radius_length=0.6, radius_max=0.06, tip_radius=0.01, broken=True,
                   step=0.15, gravitropism=0.08, droop=0.12, wander=0.3, floor=0.5, sides=(6, 5, 4),
                   seg=(0.5, 1.0, 2.0), min_length=0.1, min_len=(0.0, 0.3, 1.0))
    kids = tr.grow_children(rnd, tree, t, lv2, 1)
    for k in kids:
        for lod in range(3):
            k.keep[lod] = k.spec.sides[lod] >= 3 and k.length >= k.spec.min_len[lod] and t.keep[lod]
    tree.branches += kids
    for k in kids[:5]:
        tw = tr.grow_children(rnd, tree, k, twig_level(1.0), 2)
        for b in tw:
            for lod in range(3):
                b.keep[lod] = b.spec.sides[lod] >= 3 and b.length >= b.spec.min_len[lod] and k.keep[lod]
        tree.branches += tw
    fork = add_fork(tree, 4.6, 2.2, 8.2, 0.07, 0.8, 26.0, 0.2)
    tree.trunks.append(fork)  # for the colliders: write_trunks reads tree.trunks
    return tree


# (name, seed, spec factory, patches, fungus, post)
VARIANTS = [
    # Tall straight snag: a column of woodpecker holes with the big oval cavity above it (the column at 6.3-7.5 m, the
    # oval a metre over), a cluster higher up, bracket fungus low
    ("HollowSnag01", 7, v01,
     [("col", 0, 7.3, -1.35, False), ("clus", 0, 12.4, 1.7, True)],
     [(0, 2.1, -1.2, 4, 0.19), (0, 3.9, 2.4, 3, 0.15)], None),
    # Thick snag with the hollow open at its foot and shelves of fungus up the other side
    ("HollowSnag02", 19, v02,
     [("rot", 0, 0.82, -1.4, False), ("clus", 0, 6.2, 0.6, False)],
     [(0, 1.7, 0.5, 4, 0.2), (0, 3.4, -2.4, 4, 0.18), (0, 5.2, 2.8, 3, 0.14)], None),
    # Leaning stump-top
    ("HollowSnag03", 31, v03,
     [("clus", 0, 3.6, -1.5, False)],
     [(0, 1.2, -0.9, 4, 0.17), (0, 2.8, 2.5, 3, 0.14)], None),
    # Forked: one fork snapped, the other with a few dead limbs
    ("HollowSnag04", 43, v04,
     [("col", 0, 7.4, -1.2, True)],
     [(0, 1.5, -1.6, 4, 0.19), (0, 3.2, 1.0, 3, 0.15)], post04),
]


def main():
    tr.reset()
    if STEPS in ("all", "textures", "bark"):
        make_bark()
    if STEPS in ("all", "textures", "small"):
        make_small()
    if STEPS in ("all", "textures", "patches"):
        make_patches()
    if STEPS in ("textures", "bark", "small", "patches"):
        return
    mats = {k: tr.textured("HollowSnagBark" + n, paths("HollowSnagBark" + n)) for k, n in
            (("bark", ""), ("foot", "Foot"), ("twig", "Twig"), ("splint", "Splint"), ("peck", "Peck"),
             ("peckb", "PeckB"), ("rot", "Rot"), ("fungus", "Fungus"))}
    figure = tr.stage()
    built = []
    for name, seed, make, patches, fungus, post in VARIANTS:
        PATCHES[name] = patches
        FUNGUS[name] = fungus
        tree = tr.grow(make(), seed, name)
        if post is not None:
            post(tree)
        main_trunks = tree.trunks[:1] if post is None else tree.trunks
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[hollow_snag] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("hollowsnag01", lods[0], PREVIEWS, figure)
    tr.preview_bark("hollowsnag02", built[1][2][0], PREVIEWS, figure)
    tr.preview_lods("hollowsnag01", lods, PREVIEWS, figure, size[0], 6.0)
    tr.preview_grove("hollow_snag", [b[2][0] for b in built], PREVIEWS, figure)
    print("[hollow_snag] done")


main()
