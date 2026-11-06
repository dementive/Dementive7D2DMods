"""Saguaro (Carnegiea gigantea) for the desert, on treekit.py (joshua_tree.py is the closest worked example; TREES.md
has the rules).

A tall thick column of pleated green flesh, 40-75 cm across, with 0 to 5 arms that leave the trunk horizontally and
turn sharply up in an elbow; every column ends in a rounded cap, and in spring a crown of creamy white waxy flowers
(and later red split fruits) opens round the top. The surface is a ring of RIBS (pleats): straight vertical ridges
between narrow deep grooves, and every ridge carries a line of areoles, small felt pads each bristling with pale
grey-tan spines. Old trunks darken and scar toward the base and keep a few woodpecker holes. Forms: a classic
three-armed adult, a tall old five-armed giant, a young pole with no arms, and a leaning two-armed tree with a crested
(fan-shaped) top; the seedling a small ribbed globe.

    blender -b --factory-startup --python trees/saguaro.py -- <unity trees folder> <preview folder> [step]

with absolute paths to `NatureExpanded/unity/Assets/NatureExpanded/Trees` and
`NatureExpanded/unity/Build/previews/trees`. Steps: `all`, `textures`, `bark-textures`, `atlas`, `trees`, `icon`. It
writes Trees/Saguaro/ (bark and foot textures, flower atlas, Saguaro01..04 and SaguaroSapling with their impostors,
SaguaroSeed_Icon.png), the Saguaro lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size in
game.

The ribs are real geometry (a ring is RIBS ribs of VPR vertices each; see `ribbed_tube`, which replaces treekit's round
tube for this species) and the bark texture draws the same ribs on the same u, so the grooves, areoles and light
banding line up. The skeleton is built here (`column`, `arm`) rather than grown from Levels: arms leave the trunk
horizontally and bend up in an arc.
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
FOLDER = os.path.join(TREES, "Saguaro")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))

# ---------------------------------------------------------------- the ribs (geometry and texture share these)

RIBS = 14
# One rib period as (fraction across it, how far out): the valley at 0, then the ridge's shoulders. VPR vertices per rib
# at LOD0 (trunk 3, arms 2), 2 and 1 after; `depth` is how deep the groove cuts (fraction of the radius).
PROFILE = {
    3: ((0.0, 1.0), (0.29, 0.02), (0.71, 0.02)),
    2: ((0.0, 1.0), (0.5, 0.0)),
    1: ((0.5, 0.35),),
}
DEPTH = 0.13

# ---------------------------------------------------------------- bark textures
#
# SaguaroBark: 2048 x 4096, once round a tube (RIBS ribs of 146 px), tiling up it every 4 pi radii (square texels),
# drawn at its size on SaguaroBark01's 27 cm trunk (about 12 px per cm). SaguaroBarkFoot is the same texture with its
# lower rows (v under FOOT_END) turned to the dark corky scarred base, so the trunk changes between them (at JOIN_V,
# where they are identical) without a seam.

W, H, WRAPS = 2048, 4096, 1
K = TAU * H / (WRAPS * W)
R_DESIGN = 27.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
FOOT_END = 0.325
JOIN_V = 0.335
GROUND_V = 0.0
# Mean albedo (sRGB): a grey-green a little bluer and paler than vanilla's yellower olive saguaro (121, 121, 83 over
# its atlas, flowers and all)
BARK_MEAN = (104, 114, 78)
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS),
    "foot": tr.BarkUV(k=K, wraps=WRAPS),
}


def bark_key(br, s, r, z):
    """The dark corky foot on the lowest part of a trunk (until its bark's v reaches JOIN_V), ribbed green flesh
    everywhere else."""
    if br.level == 0 and br.turns(s) / K + br.v0 < JOIN_V:
        return "foot"
    return "bark"


def areole_kernel(rng, S=73):
    """One areole as a small RGBA+height image: a woolly felt pad with a starburst of spines, a few long thick central
    ones pointing mostly down, many shorter radial ones, all slightly curved and crossing; pale grey-tan, dark at
    their base."""
    c = S // 2
    Y, X = np.mgrid[0:S, 0:S].astype(np.float64) - c
    d = np.hypot(X, Y)
    scale = rng.uniform(0.85, 1.2)
    pad_r = rng.uniform(4.2, 5.8) * scale
    ragged = 1.0 + 0.25 * np.sin(np.arctan2(Y, X) * rng.integers(3, 7) + rng.uniform(0, 6.0))
    pad = 1.0 - tr.smoothstep(pad_r * ragged - 1.6, pad_r * ragged + 0.6, d)
    col = np.zeros((S, S, 3))
    col[:] = tr.mix((0.58, 0.54, 0.47), (0.27, 0.23, 0.19), tr.smoothstep(0.0, pad_r * 1.1, d))
    alpha = pad.copy()
    hgt = pad * 1.6
    spines = []
    for _ in range(int(rng.integers(3, 6))):
        spines.append((math.radians(-90.0 + rng.uniform(-60.0, 60.0)), rng.uniform(20.0, 31.0) * scale, 2.5, rng.uniform(-0.18, 0.18)))
    for _ in range(int(rng.integers(11, 17))):
        spines.append((rng.uniform(0.0, TAU), rng.uniform(8.0, 17.0) * scale, 1.7, rng.uniform(-0.3, 0.3)))
    for ang, length, width, bend in spines:
        # A slightly curved spine: its path bows sideways by `bend` of its length
        t = np.linspace(0.0, 1.0, 24)
        px_ = (np.cos(ang) * t - np.sin(ang) * bend * t * t) * length
        py_ = (np.sin(ang) * t + np.cos(ang) * bend * t * t) * length
        dist = np.full((S, S), 1e9)
        tt = np.zeros((S, S))
        for i in range(len(t) - 1):
            ax_, ay_, bx_, by_ = px_[i], py_[i], px_[i + 1], py_[i + 1]
            vx, vy = bx_ - ax_, by_ - ay_
            ll = vx * vx + vy * vy
            q = np.clip(((X - ax_) * vx + (Y - ay_) * vy) / ll, 0.0, 1.0)
            dd = np.hypot(X - ax_ - q * vx, Y - ay_ - q * vy)
            better = dd < dist
            dist = np.where(better, dd, dist)
            tt = np.where(better, t[i] + q * (t[i + 1] - t[i]), tt)
        w = width * (1.0 - 0.6 * tt) * 0.5
        m = 1.0 - tr.smoothstep(w * 0.5, w * 0.5 + 1.1, dist)
        tone = tr.mix((0.30, 0.25, 0.20), (0.86, 0.82, 0.72), tr.smoothstep(0.0, 0.45, tt)) * rng.uniform(0.85, 1.05)
        tone = tr.mix(tone, (0.5, 0.42, 0.33), 0.35 * (1.0 - tr.smoothstep(0.55, 1.0, tt)) * rng.random())
        win = m > alpha * 0.9
        col = np.where(win[..., None], tone, col)
        alpha = np.maximum(alpha, m)
        hgt = np.maximum(hgt, m * 0.7)
    # A faint dark shadow ring under the whole cluster seats it on the skin
    shadow = tr.blur(alpha, 2.0) * 0.35
    return alpha, col, hgt, shadow


def stamp_over(col, height, rough, cx, cy, k, weight=1.0):
    """Composites an areole kernel (alpha, color, height) into the texture at (cx, cy), wrapping round the edges."""
    a, c, hh, sh = k
    S = a.shape[0]
    h, w = height.shape
    ys = (np.arange(S) + int(cy) - S // 2) % h
    xs = (np.arange(S) + int(cx) - S // 2) % w
    ix = np.ix_(ys, xs)
    al = a * weight
    col[ix] = col[ix] * (1.0 - 0.5 * sh * weight)[..., None]
    col[ix] = col[ix] * (1.0 - al[..., None]) + c * al[..., None]
    height[ix] += hh * weight
    rough[ix] = rough[ix] * (1.0 - al) + 0.82 * al


def oval(h, w, cx, cy, rx, ry, soft=1.5):
    """A soft-edged ellipse mask over the whole texture (wrapping), computed on its bounding window only."""
    mask = np.zeros((h, w))
    sx, sy = int(rx + soft * 3 + 2), int(ry + soft * 3 + 2)
    ys = (np.arange(-sy, sy + 1) + int(cy)) % h
    xs = (np.arange(-sx, sx + 1) + int(cx)) % w
    Y, X = np.mgrid[-sy:sy + 1, -sx:sx + 1].astype(np.float64)
    e = np.hypot(X / rx, Y / ry)
    m = 1.0 - tr.smoothstep(1.0 - soft / min(rx, ry), 1.0 + soft / min(rx, ry), e)
    mask[np.ix_(ys, xs)] = m
    return mask


def saguaro_bark(r, h=H, w=W, px=PX):
    """The saguaro's flesh as (albedo sRGB, height, roughness, occlusion, foot weight), tileable both ways, `px` pixels
    per cm: RIBS ribs round it, each a wide waxy ridge between a narrow deep groove (dark green); soft accordion
    creases across the ridges; down every ridge's crest a line of areoles with their spines; a woodpecker hole and a
    healed scar; a bluish bloom and mottle."""
    cm = px
    P = w / RIBS
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    phi = (X / P) % 1.0
    dv = np.minimum(phi, 1.0 - phi) * P  # pixels to the groove's centre line
    wob = tr.fbm(r, h, w, (1.2 * cm, 9 * cm), 3)
    mott = tr.fbm(r, h, w, (6 * cm, 10 * cm), 4)
    mott2 = tr.fbm(r, h, w, (2.0 * cm, 3.5 * cm), 3)
    fiber = tr.fbm(r, h, w, (0.15 * cm, 3.0 * cm), 3)
    grit = tr.fbm(r, h, w, (0.07 * cm, 0.07 * cm), 2)
    phase = tr.fbm(r, h, w, (6 * cm, 12 * cm), 2)
    # Soft irregular accordion creases across the ridges (the flesh folds a little between rains)
    pleat = 0.5 + 0.5 * np.sin((Y / (2.6 * cm)) * TAU + 9.0 * phase + 2.0 * mott)
    # The waxy skin's own fine grain: tiny cells and specks
    skin_e, skin_b, _, _ = tr.cells(r, h, w, 0.22 * cm, 1.0)
    skin = r.random(skin_b.max() + 1)[skin_b]
    skin_edge = 1.0 - tr.smoothstep(0.0, 0.05 * cm + 0.6, skin_e)

    ridge = tr.mix((0.30, 0.37, 0.265), (0.45, 0.51, 0.36), 0.4 * mott + 0.2 * mott2 + 0.15 * fiber + 0.1 * grit + 0.15 * skin)
    bloom = tr.smoothstep(0.55, 0.8, tr.fbm(r, h, w, (10 * cm, 14 * cm), 3))
    ridge = tr.mix(ridge, (0.45, 0.51, 0.45), bloom * 0.5)
    ridge = tr.mix(ridge, (0.5, 0.49, 0.29), 0.28 * tr.smoothstep(0.6, 0.86, mott2))
    # Grey-green lichen blotches and the odd dark blemish
    lich = tr.smoothstep(0.66, 0.74, tr.fbm(r, h, w, (1.6 * cm, 2.4 * cm), 4)) * tr.smoothstep(0.35, 0.7, mott)
    ridge = tr.mix(ridge, (0.6, 0.62, 0.52), lich * 0.5)
    blem = tr.smoothstep(0.7, 0.76, tr.fbm(r, h, w, (0.8 * cm, 0.8 * cm), 3))
    ridge = tr.mix(ridge, (0.17, 0.2, 0.12), blem * 0.28)
    groove_w = 0.2 * P * (0.8 + 0.5 * wob)
    groove = 1.0 - tr.smoothstep(2.0, groove_w, dv)
    shade = 0.74 + 0.26 * tr.smoothstep(0.0, 0.3 * P, dv)
    col = ridge * shade[..., None]
    col = col * (1.0 + 0.07 * (pleat[..., None] - 0.5) * (1.0 - groove)[..., None])
    col = col * (1.0 - 0.1 * skin_edge)[..., None]
    col = tr.mix(col, (0.07, 0.11, 0.07), groove * 0.92)
    height = (-2.2 * groove + 0.55 * tr.smoothstep(0.1 * P, 0.32 * P, dv) + 0.25 * (pleat - 0.5) * (1.0 - groove)
              + 0.2 * fiber + 0.15 * grit + 0.3 * skin - 0.5 * skin_edge + 0.4 * lich)
    rough = 0.62 + 0.06 * (grit - 0.5) + 0.06 * groove + 0.2 * lich

    # Areoles down every ridge's crest line, about 2.6 cm apart
    rng = np.random.default_rng(71)
    kernels = [areole_kernel(rng) for _ in range(10)]
    step = 2.6 * cm
    rows = int(round(h / step))
    for rib in range(RIBS):
        for j in range(rows):
            x = (rib + 0.5) * P + rng.normal(0.0, 0.035) * P
            y = (j + 0.5 * (rib % 2) + rng.uniform(-0.2, 0.2)) * h / rows
            stamp_over(col, height, rough, x, y, kernels[rng.integers(len(kernels))], rng.uniform(0.75, 1.0))

    # Marks on the flesh: a woodpecker hole (dark, rimmed with scar tissue) and an old healed scar
    holes = [((5 + 0.5) * P, 0.63 * h, 0.3 * P, 0.5 * P)]
    for cx, cy, rx, ry in holes:
        rim = np.clip(oval(h, w, cx, cy, rx * 1.4, ry * 1.3, 2.5) * (0.75 + 0.5 * mott2), 0.0, 1.0)
        inner = oval(h, w, cx, cy + 0.04 * ry, rx, ry, 2.0)
        deep = tr.smoothstep(0.3, 0.9, tr.blur(inner, 0.22 * rx))
        scar = tr.mix((0.34, 0.27, 0.19), (0.52, 0.43, 0.31), 0.5 * mott2 + 0.5 * fiber)
        col = tr.mix(col, scar, rim * 0.9)
        col = tr.mix(col, (0.2, 0.14, 0.09), inner)
        col = tr.mix(col, (0.012, 0.009, 0.007), deep * inner)
        height += rim * 1.6 - inner * 3.0 - deep * 1.5
        rough = rough * (1.0 - rim) + 0.9 * rim
        drip = oval(h, w, cx, cy - 0.9 * ry, rx * 0.45, ry * 0.9, 3.0) * 0.3 * tr.smoothstep(0.3, 0.7, fiber)
        col = tr.mix(col, (0.12, 0.09, 0.06), drip)
    scar_mask = oval(h, w, (9 + 0.5) * P, 0.47 * h, 0.4 * P, 0.7 * P, 3.0) * tr.smoothstep(0.45, 0.6, mott2 + 0.25 * grit)
    scar_col = tr.mix((0.46, 0.30, 0.14), (0.62, 0.48, 0.26), fiber)
    col = tr.mix(col, scar_col, scar_mask * 0.8)
    height += scar_mask * (0.9 * fiber - 0.4)
    rough = rough * (1.0 - scar_mask) + 0.88 * scar_mask

    wf = 1.0 - tr.smoothstep(0.205 * h, FOOT_END * h, Y)
    return col, height, rough, wf, (mott, mott2, fiber, grit, groove, dv)


def foot_texture(r, col, height, rough, wf, aux, h=H, w=W, px=PX):
    """The same flesh with its lowest rows aged to dark grey-brown cork: the ribs still run up it as broad furrows,
    split into long irregular plates and scales that lift at their edges, the grooves and areoles half lost in it,
    fading back to the green flesh by FOOT_END (where the two are identical)."""
    cm = px
    mott, mott2, fiber, grit, groove, dv = aux
    warp = ((tr.fbm(r, h, w, (2.5 * cm, 9 * cm), 3) - 0.5) * 1.6 * cm,
            (tr.fbm(r, h, w, (2.5 * cm, 9 * cm), 3) - 0.5) * 2.4 * cm)
    edge, block, by, _ = tr.cells(r, h, w, 2.6 * cm, 4.5, warp)
    n = block.max() + 1
    bshade, braise = r.random(n)[block], r.random(n)[block]
    tilt = np.clip((np.mgrid[0:h, 0:w][0] - by) / (6.0 * cm), -1.0, 1.0) * (r.random(n) * 2.0 - 1.0)[block]
    crack = (1.0 - tr.smoothstep(0.0, 0.3 * cm, edge)) * tr.smoothstep(0.35, 0.55, tr.fbm(r, h, w, (4 * cm, 8 * cm), 3))
    fine = tr.fbm(r, h, w, (0.1 * cm, 1.5 * cm), 4)
    cork = tr.mix((0.22, 0.195, 0.16), (0.42, 0.37, 0.31), 0.3 * bshade + 0.2 * mott2 + 0.3 * fine + 0.1 * grit + 0.1 * (tilt * 0.5 + 0.5))
    cork = tr.mix(cork, (0.5, 0.45, 0.36), 0.25 * tr.smoothstep(0.7, 0.9, mott))
    cork = tr.mix(cork, (0.06, 0.05, 0.04), crack * 0.8)
    cork = cork * (1.0 - 0.5 * groove)[..., None]
    k = np.clip(wf * 0.95, 0.0, 1.0)
    fcol = tr.mix(col, cork, k)
    cork_h = 1.8 * tr.smoothstep(0.0, 0.7 * cm, edge) + 0.6 * braise + 0.5 * tilt + 0.5 * fine - 1.0 * groove - 1.2 * crack
    fheight = height * (1.0 - k) + k * cork_h
    frough = rough * (1.0 - k) + 0.93 * k
    return fcol, fheight, frough


def make_bark():
    r = np.random.default_rng(31)
    col, height, rough, wf, aux = saguaro_bark(r)
    graded, k = tr.match_mean(col, BARK_MEAN)
    print("[saguaro] bark graded by %s to %s" % (np.round(k, 2), BARK_MEAN))

    def save(name, c, hh, rr, relief):
        p = paths(name)
        occ = tr.cavity(hh, 4.0 * RELIEF, 0.3)
        c = c * (0.72 + 0.28 * occ)[..., None]
        tr.write_png(p["albedo"], np.clip(c, 0.0, 1.0))
        tr.write_png(p["normal"], tr.normal_map(tr.blur(hh, 0.6), 0.9 * relief))
        zero = np.zeros_like(rr)
        tr.write_png(p["rmom"], np.dstack([np.clip(rr, 0.0, 1.0), zero, occ, zero]))
        return c

    fcol, fheight, frough = foot_texture(r, graded, height, rough, wf, aux)
    main = save("SaguaroBark", graded, height, rough, RELIEF * 1.7)
    foot = save("SaguaroBarkFoot", fcol, fheight, frough, RELIEF * 1.7)
    cm = PX
    # Crops at full size for review: a rib and a half near the foot, mid trunk, the hole
    P = W // RIBS
    tr.write_png(os.path.join(PREVIEWS, "saguaro_bark_main.png"), main[1800:2800, 0:1024])
    tr.write_png(os.path.join(PREVIEWS, "saguaro_bark_foot.png"), foot[0:1400, 0:1024])
    tr.write_png(os.path.join(PREVIEWS, "saguaro_bark_hole.png"), main[int(0.63 * H) - 500:int(0.63 * H) + 500, 5 * P - 200:5 * P + 800])


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the flower atlas
#
# 2048 square: eight 256 cells along the top (four open flowers, two buds, two fruits), each alone with its base at the
# cell's attach point and its axis lying down the cell (a card's `a` runs from the attach point along the flower), and
# two 1024 crown cells (a whole crown of flowers, buds and a fruit, seen from the side) for LOD2.

FLOWERS = tuple("Flower%d" % i for i in range(4))
BUDS = tuple("Bud%d" % i for i in range(2))
FRUITS = tuple("Fruit%d" % i for i in range(2))
CROWNS = ("Crown0", "Crown1")


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(FLOWERS + BUDS + FRUITS):
        atlas.cell(name, 256 * i, 1792, 256, 256, (0.12, 0.12))
    atlas.cell(CROWNS[0], 0, 512, 1024, 1024, (0.5, 0.5))
    atlas.cell(CROWNS[1], 1024, 512, 1024, 1024, (0.5, 0.5))
    return atlas


def petal_profile(s):
    """A saguaro petal's half-width along it: narrow at the base, widest past the middle, a rounded blunt tip."""
    return max(0.0, math.sin(math.pi * min(1.0, 0.04 + 0.96 * s)) ** 0.55) * (0.55 + 0.45 * min(1.0, s * 1.8))


def flower_materials():
    """The materials the flowers and fruits are drawn in for the atlas and the seed's icon (not exported)."""
    mats = {}
    mat, g = tr.tk.new_material("SagPetalSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    base = g.mix(g.ramp(rv, 0.0, 1.0), (0.80, 0.76, 0.60), (0.86, 0.82, 0.68))
    base = g.mix(g.ramp(along, 0.3, 0.0), base, (0.5, 0.56, 0.24))
    base = g.mix(g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", across), 0.25, 0.0), g.ramp(along, 0.1, 0.5)), base,
                 (0.66, 0.66, 0.46))
    vein = g.ramp(g.math("SINE", g.math("MULTIPLY", across, 26.0)), 0.4, 1.0)
    base = g.mix(g.math("MULTIPLY", vein, 0.12), base, (0.66, 0.62, 0.46))
    col = g.mix(g.math("MULTIPLY", back, 0.12), base, (0.72, 0.68, 0.52))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    mats["petal"] = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("SagTubeSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(g.noise(160.0, detail=3.0), 0.3, 0.7), (0.07, 0.12, 0.05), (0.2, 0.18, 0.08))
    col = g.mix(g.ramp(along, 0.7, 1.0), col, (0.5, 0.48, 0.3))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    mats["tube"] = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("SagStamenSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(along, 0.7, 0.95), (0.62, 0.5, 0.2), (0.75, 0.52, 0.03))
    tr.tk.finish(mat, g, col, 0.0, 0.7)
    mats["stamen"] = tr.signals(mat, col, 0.7)

    mat, g = tr.tk.new_material("SagBudSrc")
    lobe, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.07, 0.13, 0.05), (0.2, 0.2, 0.08))
    col = g.mix(g.ramp(along, 0.72, 0.95), col, (0.72, 0.68, 0.5))
    tr.tk.finish(mat, g, col, 0.0, 0.55)
    mats["bud"] = tr.signals(mat, col, 0.55)

    mat, g = tr.tk.new_material("SagFruitSrc")
    lobe, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    out = g.mix(g.ramp(g.noise(70.0, detail=3.0), 0.35, 0.65), (0.09, 0.17, 0.05), (0.32, 0.1, 0.05))
    out = g.mix(g.ramp(along, 0.4, 1.0), out, (0.32, 0.07, 0.04))
    col = g.mix(back, out, (0.42, 0.015, 0.02))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    mats["fruit"] = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("SagPulpSrc")
    col = g.mix(g.ramp(g.noise(90.0, detail=3.0), 0.3, 0.7), (0.28, 0.008, 0.015), (0.5, 0.025, 0.03))
    tr.tk.finish(mat, g, col, 0.0, 0.3)
    mats["pulp"] = tr.signals(mat, col, 0.3)

    mat, g = tr.tk.new_material("SagSeedSrc")
    tr.tk.finish(mat, g, (0.012, 0.011, 0.01), 0.0, 0.3)
    mats["seed"] = tr.signals(mat, (0.012, 0.011, 0.01), 0.3)
    return mats


def flower(m, rnd, base, axis, size=1.0):
    """One open flower (real geometry for the atlas): a green funnel tube opening into two whorls of broad creamy
    white petals, the outer spread wide, the inner standing; a tuft of yellow-tipped stamens at the middle."""
    ax, u, v = tr.basis(axis)
    base = Vector(base)
    L = 0.042 * size
    pts = [base + ax * (L * t) for t in (0.0, 0.3, 0.6, 0.85, 1.0)]
    tr.twig(m, pts, [r * size for r in (0.0055, 0.0085, 0.012, 0.0155, 0.0175)], "tube", 9)
    mouth = base + ax * L
    for ring, (n, ang, length, width) in enumerate(((9, 66.0, 0.036, 0.0125), (8, 38.0, 0.032, 0.0115))):
        for i in range(n):
            az = ((i + 0.5 * ring) / n + rnd.uniform(-0.03, 0.03)) * TAU + ring * 0.35
            out = u * math.cos(az) + v * math.sin(az)
            th = math.radians(ang + rnd.gauss(0.0, 7.0))
            d = ax * math.cos(th) + out * math.sin(th)
            nl = ax * math.sin(th) - out * math.cos(th)
            tr.blade(m, mouth + out * 0.004 * size, d, nl, length * size * rnd.uniform(0.9, 1.1),
                     width * size * rnd.uniform(0.9, 1.1), petal_profile, "petal", fold=0.3, arch=0.22 if ring == 0 else 0.1,
                     twist=rnd.uniform(-14.0, 14.0), rows=8, rnd_value=rnd.random())
    for _ in range(64):
        az = rnd.uniform(0.0, TAU)
        out = u * math.cos(az) + v * math.sin(az)
        th = math.radians(rnd.uniform(4.0, 40.0))
        d = ax * math.cos(th) + out * math.sin(th)
        a0 = mouth + out * rnd.uniform(0.002, 0.012) * size - ax * 0.004 * size
        ln = rnd.uniform(0.014, 0.024) * size
        tr.twig(m, [a0, a0 + d * ln * 0.5, a0 + d * ln], [0.0007 * size, 0.0006 * size, 0.0007 * size], "stamen", 3)
    tr.twig(m, [mouth - ax * 0.004 * size, mouth + ax * 0.016 * size, mouth + ax * 0.03 * size],
            [0.0022 * size, 0.0018 * size, 0.0026 * size], "stamen", 5)


def loft(m, base, axis, length, profile, key, rings=10, segs=12, lobes=0):
    """A lathed solid along `axis` (radius profile(t), t 0 to 1) with the "leaf" attribute (lobe, t, 0.5)."""
    ax, u, v = tr.basis(axis)
    rows = []
    for j in range(rings + 1):
        t = j / rings
        row = []
        for k in range(segs):
            a = k / segs * TAU
            rr = profile(t) * (1.0 + (0.06 * math.cos(lobes * a) if lobes else 0.0))
            p = Vector(base) + ax * (t * length) + (u * math.cos(a) + v * math.sin(a)) * rr
            row.append(m.v(p, leaf=(math.cos(a), t, 0.5)))
        rows.append(row)
    uv = ((0, 0),) * 4
    for a, b in zip(rows, rows[1:]):
        for k in range(segs):
            k1 = (k + 1) % segs
            m.quad(a[k], a[k1], b[k1], b[k], uv, key)
    top = m.v(Vector(base) + ax * length, leaf=(0.0, 1.0, 0.5))
    for k in range(segs):
        m.tri(rows[-1][k], rows[-1][(k + 1) % segs], top, uv[:3], key)


def bud(m, rnd, base, axis, size=1.0):
    """A closed flower bud: a ribbed green egg with a pale cream point."""
    L = 0.056 * size
    loft(m, base, axis, L, lambda t: size * 0.0155 * math.sin(math.pi * min(1.0, 0.08 + 0.92 * t ** 0.85)) ** 0.7
         * (0.55 + 0.45 * min(1.0, t * 3.0)), "bud", 10, 10, lobes=5)


def fruit(m, rnd, base, axis, size=1.0, flaps=4, seeds=22):
    """A ripe fruit split open: a green ovoid (tinged red) whose top has peeled back in flaps to show the crimson pulp
    studded with black seeds."""
    ax, u, v = tr.basis(axis)
    base = Vector(base)
    L = 0.052 * size
    R = 0.021 * size
    loft(m, base, ax, L * 0.85, lambda t: max(0.003, R * math.sqrt(t * (2.0 - t)) * (1.0 - 0.1 * t)), "fruit", 9, 12)
    rim = base + ax * L * 0.85
    # The pulp: a red dome rising from the open top, seeds scattered on it
    loft(m, rim - ax * 0.004 * size, ax, 0.016 * size, lambda t: R * 0.84 * math.cos(0.5 * math.pi * t) ** 0.6 + 0.001, "pulp", 5, 12)
    for _ in range(seeds):
        az = rnd.uniform(0.0, TAU)
        rr = R * 0.8 * math.sqrt(rnd.random())
        hh = 0.014 * size * (1.0 - (rr / (R * 0.84)) ** 2) ** 0.6
        c = rim + ax * hh + (u * math.cos(az) + v * math.sin(az)) * rr
        sd, su, sv = tr.basis(ax + (u * math.cos(az) + v * math.sin(az)) * rr / R * 0.5)
        pts = [c + su * 0.0011 * size * math.cos(a) + sv * 0.0011 * size * math.sin(a) for a in (k / 6 * TAU for k in range(6))]
        ids = [m.v(p, leaf=(0.0, 0.0, 0.0)) for p in pts]
        tip = m.v(c + sd * 0.0007 * size, leaf=(0.0, 0.0, 0.0))
        for k in range(6):
            m.tri(ids[k], ids[(k + 1) % 6], tip, ((0, 0),) * 3, "seed")
    for i in range(flaps):
        az = (i + rnd.uniform(-0.1, 0.1)) / flaps * TAU
        out = u * math.cos(az) + v * math.sin(az)
        th = math.radians(rnd.uniform(52.0, 78.0))
        d = ax * math.cos(th) + out * math.sin(th)
        nl = out * math.cos(th) - ax * math.sin(th)
        tr.blade(m, rim + out * R * 0.88, d, nl, 0.03 * size * rnd.uniform(0.9, 1.15), (TAU * R / flaps) * 0.95,
                 lambda s: max(0.0, math.sin(math.pi * (0.06 + 0.94 * s)) ** 0.5) ** 0.8 * (1.0 - 0.3 * s), "fruit", fold=-0.15,
                 arch=0.12, twist=rnd.uniform(-10, 10), rows=8, rnd_value=rnd.random())


def crown_mesh(m, rnd, fruiting=0.0):
    """A whole crown, for the LOD2 cells: flowers, buds (and some fruit) standing round the top of a column, in the
    card's frame (x right, y up), the dome's top at the origin."""
    ax = Vector((0.0, 1.0, 0.0))
    for i in range(18):
        az = i * tr.GOLDEN + rnd.uniform(-0.3, 0.3)
        th = math.radians(10.0 + 52.0 * math.sqrt(rnd.random()))
        outv = Vector((math.cos(az), 0.0, math.sin(az)))
        dirn = ax * math.cos(th) + outv * math.sin(th)
        base = Vector((0.0, -0.17, 0.0)) + dirn * 0.17
        a = (dirn * 0.6 + ax * 0.5 + Vector((rnd.gauss(0, 0.15), rnd.gauss(0, 0.15), rnd.gauss(0, 0.15)))).normalized()
        k = rnd.random()
        if k < fruiting:
            fruit(m, rnd, base, a, 1.0)
        elif k < fruiting + 0.14:
            bud(m, rnd, base, a, 1.0)
        else:
            flower(m, rnd, base, a, rnd.uniform(0.9, 1.1))


def make_atlas(atlas, render=True):
    mats = flower_materials()
    rnd = random.Random(23)
    for name in FLOWERS + BUDS + FRUITS:
        m = tr.Mesh()
        # Lying down the cell from its attach point, tilted toward the camera so the opening shows
        tilt = Vector((rnd.uniform(-0.15, 0.15), -0.77, 0.64)).normalized()
        if name in FLOWERS:
            flower(m, rnd, Vector(), tilt, rnd.uniform(0.92, 1.08))
        elif name in BUDS:
            bud(m, rnd, Vector(), Vector((rnd.uniform(-0.1, 0.1), -0.95, 0.25)).normalized(), rnd.uniform(0.95, 1.1))
        else:
            fruit(m, rnd, Vector(), Vector((rnd.uniform(-0.1, 0.1), -0.8, 0.55)).normalized(), rnd.uniform(1.0, 1.15))
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        if render:
            atlas.render(atlas.cells[name], [obj], samples=48)
    for name, fruiting in zip(CROWNS, (0.0, 0.25)):
        m = tr.Mesh()
        crown_mesh(m, rnd, fruiting)
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        if render:
            atlas.render(atlas.cells[name], [obj], samples=48)
    if not render:
        return None
    out = atlas.save(FOLDER, "SaguaroLeaves")
    atlas.preview(os.path.join(PREVIEWS, "saguaro_atlas.png"))
    for c in atlas.cells.values():
        print("[saguaro] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("SaguaroLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the skeleton
#
# Every column (the trunk, each arm) is a polyline from its base (a trunk's a little under the ground, an arm's on the
# trunk's axis) up to the apex of its rounded cap: the last points shrink in radius along a quarter circle. Rings of
# the ribbed tube are a subset of the points; `br.cap` is the index where the cap starts, `br.nominal` the radius
# the column would have without the cap (what the texture's v counts by).

def trunk_spec(height, radius, sides=(42, 28, 14), seg=(0.7, 1.6, 3.0)):
    return tr.Trunk(height=height, radius=radius, flare=0.22, flare_height=0.45, taper=0.0, sides=sides, seg=seg,
                    min_len=(0.0, 0.0, 0.0))


def arm_spec(sides=(28, 14, 14), seg=(0.6, 1.5, 3.0)):
    return tr.Level(sides=sides, seg=seg, min_len=(0.0, 0.0, 0.0))


CAP_ANGLES = (28.0, 52.0, 74.0, 90.0)


def cap_points(p, t, r, up_out=None):
    """The rounded end: `p` is the cap's start (a full radius `r`), `t` the way up; points up a quarter circle."""
    pts, rad = [], []
    for a in CAP_ANGLES:
        ar = math.radians(a)
        pts.append(p + t * (r * math.sin(ar)))
        rad.append(r * math.cos(ar))
    return pts, rad


def column(rnd, height, r1, lean=(0.0, 0.0), bow=0.0, wander=0.04, join=True, depth=DEPTH, sides=(42, 28, 14)):
    """A trunk: from just under the ground to `height`, radius `r1` a metre up, flaring a little at the foot, a hair
    narrower toward the top, leaning and crooked a little; ends in a hemisphere."""
    waves = [(rnd.uniform(0.5, 1.4), rnd.uniform(0.0, TAU), rnd.uniform(0.4, 1.0)) for _ in range(4)]

    def radius(z):
        zz = max(0.0, z)
        return r1 * (1.0 + 0.24 * math.exp(-zz / 0.4)) * (1.0 - 0.1 * (zz / height) ** 1.6) / 1.03

    r_top = radius(height) * 0.97
    z_cs = height - r_top
    zs = [zz for zz in (-0.3, 0.0, 0.12, 0.3, 0.6, 1.0) if zz < z_cs - 0.15]
    z = 1.0
    while z + 0.8 < z_cs - 0.2:
        z += 0.8
        zs.append(z)
    zs.append(z_cs)
    zs = sorted(set(zs))

    def place(zz):
        f = max(0.0, min(1.0, zz / height))
        crook = Vector((sum(a * math.sin(TAU * c * f + ph) for c, ph, a in waves[:2]),
                        sum(a * math.sin(TAU * c * f + ph) for c, ph, a in waves[2:]), 0.0)) * (wander * f ** 0.6)
        return Vector((0.0, 0.0, zz)) + Vector((lean[0], lean[1], 0.0)) * (f + bow * f * (1.0 - f)) + crook

    pts = [place(zz) for zz in zs]
    rad = [radius(zz) for zz in zs]
    nominal = list(rad)
    cap_start = len(pts) - 1
    t = (pts[-1] - pts[-2]).normalized()
    cp, cr = cap_points(pts[-1], t, rad[-1])
    pts += cp
    rad += cr
    nominal += [rad[cap_start]] * len(cp)
    spec = trunk_spec(height, r1, sides)
    br = tr.Branch(pts, rad, 0, None, 0.0, spec, rnd)
    br.v0 = GROUND_V
    br.cap = cap_start
    br.nominal = nominal
    br.depth = depth
    br.tags.add("tip")
    if join:
        # A ring right where the bark's v reaches JOIN_V, so the foot changes to the plain bark exactly there
        s = _s_where_v(br, JOIN_V)
        if s is not None:
            z_j = br.at(s)[0].z
            zs = sorted(set(zs + [z_j]))
            pts = [place(zz) for zz in zs]
            rad = [radius(zz) for zz in zs]
            nominal = list(rad)
            cap_start = len(pts) - 1
            t = (pts[-1] - pts[-2]).normalized()
            cp, cr = cap_points(pts[-1], t, rad[-1])
            pts += cp
            rad += cr
            nominal += [rad[cap_start]] * len(cp)
            br = tr.Branch(pts, rad, 0, None, 0.0, spec, rnd)
            br.v0 = GROUND_V
            br.cap = cap_start
            br.nominal = nominal
            br.depth = depth
            br.tags.add("tip")
            br.force = {zs.index(z_j)}
    return br


def _s_where_v(br, v):
    """The fraction along a trunk where its bark's v reaches `v` (by bisection of turns(s) / K + v0), or None."""
    if br.turns(1.0) / K + br.v0 < v:
        return None
    lo, hi = br.s_at_height(0.0), 1.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if br.turns(mid) / K + br.v0 < v:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def arm(rnd, trunk, z, az_deg, reach, top, r, rise=8.0, lean_out=0.04, elbow=None, depth=DEPTH * 0.9, wobble=0.05,
        sides=(28, 14, 14)):
    """An arm: leaves the trunk's axis at height `z` heading `az_deg` (degrees about the vertical), nearly horizontal
    (`rise` degrees up) for `reach` m beyond the trunk's surface, bends up through an elbow (radius `elbow`, default
    2.4 radii) and climbs to a rounded top at height `top`, its radius `r` hardly narrowing."""
    s0 = trunk.s_at_height(z)
    S0, _, rt = trunk.at(s0)
    az = math.radians(az_deg)
    h = Vector((math.cos(az), math.sin(az), 0.0))
    slope = math.tan(math.radians(rise))
    D = rt + reach
    nh = max(2, int(math.ceil(D / 0.4)))
    pts = [S0 + h * (D * i / nh) + UP * (D * i / nh * slope) for i in range(nh + 1)]
    head0 = (h + UP * slope).normalized()
    head1 = (UP + h * lean_out).normalized()
    Re = elbow if elbow is not None else max(4.2 * r, 0.8)
    axis = head0.cross(head1)
    ang = math.acos(max(-1.0, min(1.0, head0.dot(head1))))
    centre = pts[-1] + (head1 - head0 * head0.dot(head1)).normalized() * Re
    p0 = pts[-1]
    steps = max(5, int(math.ceil(math.degrees(ang) / 12.0)))
    for i in range(1, steps + 1):
        pts.append(centre + tr.rotate(p0 - centre, axis, math.degrees(ang) * i / steps))
    pe = pts[-1]
    z_cs = top - r
    n_up = max(1, int(math.ceil((z_cs - pe.z) / 0.5)))
    ph = rnd.uniform(0.0, TAU)
    drift = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)).normalized() * rnd.uniform(0.0, 0.25)
    for i in range(1, n_up + 1):
        f = i / n_up
        q = pe + (head1 * ((z_cs - pe.z) / max(head1.z, 0.3)) * f) + drift * f * f
        q += Vector((math.sin(ph + 3.0 * f), math.cos(ph * 1.3 + 2.0 * f), 0.0)) * wobble * math.sin(math.pi * f)
        pts.append(q)
    t = (pts[-1] - pts[-2]).normalized()
    rad = [r * (1.0 - 0.06 * i / max(1, len(pts) - 1)) for i in range(len(pts))]
    nominal = list(rad)
    cap_start = len(pts) - 1
    cp, cr = cap_points(pts[-1], t, rad[-1])
    pts += cp
    rad += cr
    nominal += [rad[cap_start]] * len(cp)
    br = tr.Branch(pts, rad, 1, trunk, s0, arm_spec(sides), rnd)
    br.cap = cap_start
    br.nominal = nominal
    br.depth = depth
    br.tags.add("tip")
    return br


def assemble(spec, seed, name, trunk, arms):
    """A Tree of `trunk` and its `arms`, as tr.grow would leave one."""
    tree = tr.Tree(name, spec, seed)
    tree.trunks = [trunk]
    tree.branches = [trunk] + list(arms)
    for br in tree.branches:
        for lod in range(3):
            ok = br.spec.sides[lod] >= 3 and br.length >= br.spec.min_len[lod]
            br.keep[lod] = ok and (br.parent is None or br.parent.keep[lod])
    return tree


# ---------------------------------------------------------------- the ribbed tube

RULES = ((0.7, 12.0, 0.04), (1.6, 24.0, 0.09), (3.0, 40.0, 0.16))  # ring spacing, turn (degrees), radius change by LOD


def ring_indices(br, lod):
    """Which of a column's polyline points get a ring at this LOD: far enough from the last, or turned enough, or
    changed enough in radius; always the ends; the cap's last rings where they change the radius."""
    pts, rad = br.points, br.radii
    fr = tr.frames(pts)
    seg, turn, dr = RULES[lod]
    keep = [0]
    last = 0
    for i in range(1, len(pts) - 1):
        d = (pts[i] - pts[last]).length
        ang = math.degrees(math.acos(max(-1.0, min(1.0, fr[i][0].dot(fr[last][0])))))
        ch = abs(rad[i] - rad[last]) / max(rad[last], 1e-3)
        if d >= seg or ang >= turn or ch >= dr or i in getattr(br, "force", ()):
            keep.append(i)
            last = i
    keep.append(len(pts) - 1)
    return keep, fr


def ribbed_tube(m, tree, br, lod):
    """Replaces treekit._tube: a column's bark as a ring of RIBS ribs (the grooves are real geometry), u running once
    round with the texture's ribs on the same u, v by length over the column's radius."""
    spec = br.spec
    sides = spec.sides[lod]
    vpr = max(1, min(3, sides // RIBS))
    n = RIBS * vpr
    prof = PROFILE[vpr]
    depth = getattr(br, "depth", DEPTH)
    keyfn, maps = tree.spec.bark_key, tree.spec.bark_uv
    pts, rad = br.points, br.radii
    nominal = getattr(br, "nominal", rad)
    keep, fr = ring_indices(br, lod)
    L = max(br.length, 1e-6)
    br.drawn[lod] = ([br.cum[i] / L for i in keep], [pts[i].copy() for i in keep])
    crest = getattr(br, "crest", None)
    # u of every vertex round a ring
    us = []
    for k in range(n):
        rib, j = divmod(k, vpr)
        us.append((rib + prof[j][0]) / RIBS)
    # v by length over radius, the trunk's from the ground
    acc = [0.0]
    for a, b in zip(keep, keep[1:]):
        ds = (pts[b] - pts[a]).length
        acc.append(acc[-1] + ds / max(0.5 * (nominal[a] + nominal[b]), 0.004))
    if br.level == 0:
        j = next((i for i in range(1, len(keep)) if pts[keep[i]].z >= 0.0), None)
        if j is not None:
            a, b = keep[j - 1], keep[j]
            f = max(0.0, min(1.0, -pts[a].z / max(pts[b].z - pts[a].z, 1e-9)))
            g = acc[j - 1] + (acc[j] - acc[j - 1]) * f
            acc = [x - g for x in acc]

    def widths(i):
        if crest is None:
            return 1.0, 1.0
        i0, wide, thick = crest
        if i < i0:
            return 1.0, 1.0
        f = min(1.0, (br.cum[i] - br.cum[i0]) / max(br.cum[br.cap] - br.cum[i0], 1e-6))
        f = f * f * (3.0 - 2.0 * f)
        return 1.0 + (thick - 1.0) * f, 1.0 + (wide - 1.0) * f

    rings = []
    apex = None
    for idx, i in enumerate(keep):
        p, r = pts[i], rad[i]
        if r < 0.004:
            apex = m.v(p)
            rings.append(None)
            continue
        t, nr, bn = fr[i]
        thick, wide = widths(i)
        ring = []
        for k in range(n):
            rib, j = divmod(k, vpr)
            mult = 1.0 - depth * prof[j][1] if vpr > 1 else 1.0 - depth * prof[j][1]
            a = br.rot + us[k] * TAU
            ring.append(m.v(p + (nr * (math.cos(a) * thick) + bn * (math.sin(a) * wide)) * (r * mult)))
        rings.append(ring)
    for idx in range(len(keep) - 1):
        a_i, b_i = keep[idx], keep[idx + 1]
        sm = 0.5 * (br.cum[a_i] + br.cum[b_i]) / L
        key = keyfn(br, sm, rad[a_i], pts[a_i].z)
        bm = maps[key]
        ra, rb = rings[idx], rings[idx + 1]
        za, zb = pts[a_i].z, pts[b_i].z
        for k in range(n):
            k1 = k + 1
            u0, u1 = us[k], (us[k1] if k1 < n else 1.0)
            if rb is None:
                m.tri(ra[k], ra[k1 % n], apex,
                      (bm.uv(u0, acc[idx], za, br), bm.uv(u1, acc[idx], za, br),
                       bm.uv(0.5 * (u0 + u1), acc[idx + 1], zb, br)), key)
            else:
                m.quad(ra[k], ra[k1 % n], rb[k1 % n], rb[k],
                       (bm.uv(u0, acc[idx], za, br), bm.uv(u1, acc[idx], za, br),
                        bm.uv(u1, acc[idx + 1], zb, br), bm.uv(u0, acc[idx + 1], zb, br)), key)
    if br.parent is None:
        # A trunk's buried end, closed
        key = keyfn(br, 0.0, rad[0], pts[0].z)
        bm = maps[key]
        bottom = m.v(pts[0] - fr[0][0] * rad[0])
        for k in range(n):
            k1 = k + 1
            u0, u1 = us[k], (us[k1] if k1 < n else 1.0)
            m.tri(rings[0][k1 % n], rings[0][k], bottom,
                  (bm.uv(u1, acc[0], pts[0].z, br), bm.uv(u0, acc[0], pts[0].z, br),
                   bm.uv(0.5 * (u0 + u1), acc[0] - 0.3, pts[0].z, br)), key)


tr._tube = ribbed_tube


# ---------------------------------------------------------------- the crown: flowers and fruit

class FixedCard(tr.Card):
    """A flower card at an exact place on its column's cap: it hangs from there at every LOD (the cap is a dome the
    polyline only reaches at its apex)."""

    def scaled(self, k):
        return FixedCard(self.p, self.a, self.n, self.cell, self.scale * k, self.host, self.s)

    def on(self, lod):
        return self


def crown_cards(tree, rnd, scale=2.7, density=1.0):
    """Cards round the top of every column: flowers (and buds, and some red fruit) set on its dome, their bases on
    its surface, their mouths up and out, the commonest near the top."""
    cells = tr.ATLAS_CELLS
    cards = []
    for br in tree.branches:
        if "tip" not in br.tags:
            continue
        cs = br.points[br.cap]
        rt = br.radii[br.cap]
        t = (br.points[-1] - br.points[br.cap]).normalized()
        _, u, v = tr.basis(t)
        thick, wide = 1.0, 1.0
        crest = getattr(br, "crest", None)
        if crest:
            thick, wide = crest[2], crest[1]
        fruit_share = rnd.choice((0.0, 0.05, 0.12, 0.3))
        count = int((18 + 90 * rt) * density)
        for i in range(count):
            az = i * tr.GOLDEN + rnd.uniform(-0.3, 0.3)
            th = math.radians(8.0 + 56.0 * math.sqrt(rnd.random()))
            dirn = t * math.cos(th) + (u * (math.cos(az) * thick) + v * (math.sin(az) * wide)) * math.sin(th)
            base = cs + dirn * (rt * 0.97)
            nrm_out = (u * math.cos(az) + v * math.sin(az)) * math.sin(th) + t * math.cos(th)
            a = (nrm_out * 0.6 + t * 0.55 + Vector((rnd.gauss(0, 0.18), rnd.gauss(0, 0.18), rnd.gauss(0, 0.18)))).normalized()
            k = rnd.random()
            if k < fruit_share:
                cell = cells[rnd.choice(FRUITS)]
                sc = scale * rnd.uniform(0.95, 1.15)
            elif k < fruit_share + 0.13:
                cell = cells[rnd.choice(BUDS)]
                sc = scale * rnd.uniform(0.9, 1.1)
            else:
                cell = cells[rnd.choice(FLOWERS)]
                sc = scale * rnd.uniform(0.9, 1.2)
            horiz = Vector((nrm_out.x, nrm_out.y, 0.0))
            n0 = horiz.normalized() if horiz.length > 0.2 else Vector((math.cos(az), math.sin(az), 0.0))
            if rnd.random() < 0.35:
                b = rnd.uniform(0.0, TAU)
                n0 = Vector((math.cos(b), math.sin(b), 0.0))
            nrm = n0 - a * n0.dot(a)
            if nrm.length < 1e-3:
                nrm = tr.basis(a)[1]
            nrm = tr.rotate(nrm.normalized(), a, rnd.uniform(-25.0, 25.0))
            cards.append(FixedCard(base, a, nrm, cell, sc, br, rnd.uniform(0.5, 0.95)))
    return cards


# ---------------------------------------------------------------- colliders

def write_colliders(path, name, tree):
    """Trunks.txt lines for the builder's capsule chains. The first line is the trunk's lowest metres (it is what the
    builder reads as the main trunk); the rest of the trunk and every arm follow as separate two-point lines (one
    capsule each: the builder merges the points of a longer line into chords up to 3 m, which would cut the arms'
    elbows), their ends at most 1.5 m apart and turning no more than 20 degrees. Radii are the ridges' (the capsule
    sits a hair inside them)."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() and ln.split()[0] != name]

    def fmt(p, r):
        return "%.3f %.3f %.3f %.4f" % (p.x, p.y, p.z, r)

    def chords(br, start, stop, step=1.5, turn=20.0):
        fr = tr.frames(br.points)
        idx = [start]
        last = start
        for i in range(start + 1, stop):
            d = (br.points[i] - br.points[last]).length
            ang = math.degrees(math.acos(max(-1.0, min(1.0, fr[i][0].dot(fr[last][0])))))
            if d >= step or ang >= turn:
                idx.append(i)
                last = i
        if idx[-1] != stop:
            idx.append(stop)
        return idx

    t = tree.trunks[0]
    low = [i for i, p in enumerate(t.points) if p.z <= 1.6]
    first = low + ([low[-1] + 1] if low[-1] + 1 <= t.cap else [])
    out = [name + " " + " ".join(fmt(t.points[i], t.radii[i]) for i in first)]
    idx = chords(t, first[-1], t.cap)
    for a, b in zip(idx, idx[1:]):
        out.append(name + " " + fmt(t.points[a], t.radii[a]) + " " + fmt(t.points[b], t.radii[b]))
    for br in tree.branches[1:]:
        idx = chords(br, 0, br.cap)
        for a, b in zip(idx, idx[1:]):
            out.append(name + " " + fmt(br.points[a], br.radii[a]) + " " + fmt(br.points[b], br.radii[b]))
    lines += out
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return len(out)


# ---------------------------------------------------------------- the trees

def make_spec(budget=7000, sides_unused=None):
    return tr.TreeSpec(
        trunks=[], levels=[], budget=budget, bark_budget=2500,
        foliage=tr.Foliage(levels={}, trunk_top=None, cells=FLOWERS + BUDS + FRUITS, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.965, 1.0)}, trunk_top=(0.965, 1.0), spacing=0.05, cells=CROWNS, scale=(0.62, 0.74),
                           hang=1.0, spread=0.06, out=0.0, face=0.0, up=0.0, roll=0.0, bend=0.0,
                           on=lambda br: "tip" in br.tags),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V, lod_share=(0.55, 0.22))


def tree_01(rnd):
    """The classic: a 9 m trunk, three arms, one on each side and one between."""
    t = column(rnd, 9.0, 0.27, lean=(0.28, 0.16), bow=0.2, wander=0.05)
    return t, [arm(rnd, t, 4.1, 25.0, 1.15, 7.3, 0.205), arm(rnd, t, 4.8, 205.0, 1.35, 8.1, 0.2, rise=12.0),
               arm(rnd, t, 5.9, 110.0, 0.95, 7.9, 0.17)]


def tree_02(rnd):
    """The old giant: 12 m, five arms of very different height, one low and long."""
    t = column(rnd, 12.0, 0.36, lean=(-0.3, 0.35), bow=0.25, wander=0.06)
    return t, [arm(rnd, t, 2.7, 135.0, 2.0, 6.3, 0.25, rise=10.0, elbow=1.1),
               arm(rnd, t, 3.5, 12.0, 1.7, 8.8, 0.26), arm(rnd, t, 4.6, 195.0, 1.55, 10.3, 0.25, rise=14.0),
               arm(rnd, t, 6.1, 95.0, 1.4, 10.9, 0.22), arm(rnd, t, 6.9, 285.0, 1.15, 9.9, 0.2, rise=6.0)]


def tree_03(rnd):
    """A young pole: 4.5 m, no arms yet."""
    t = column(rnd, 4.5, 0.16, lean=(0.3, -0.12), bow=0.3, wander=0.04, depth=DEPTH * 0.8, sides=(42, 28, 14))
    return t, []


def tree_04(rnd):
    """Odd: leaning 7 m, two arms (a heavy low one, a small high one), the trunk's top a fan-shaped crest."""
    t = column(rnd, 7.0, 0.23, lean=(1.2, 0.45), bow=0.7, wander=0.08)
    arms = [arm(rnd, t, 1.7, 215.0, 1.9, 5.2, 0.19, rise=5.0, elbow=0.85), arm(rnd, t, 4.4, 40.0, 0.85, 6.0, 0.14)]
    # The crest: the last 1.3 m of the trunk widen into a fan (3.4 times as wide, 0.6 as thick)
    i0 = max(i for i, p in enumerate(t.points[:t.cap + 1]) if t.cum[t.cap] - t.cum[i] >= 1.2)
    t.crest = (i0, 3.4, 0.62)
    return t, arms


def tree_sapling(rnd):
    t = column(rnd, 0.5, 0.05, lean=(0.03, -0.02), wander=0.01, join=False, depth=DEPTH * 0.7, sides=(28, 14, 14))
    return t, []


VARIANTS = [
    ("Saguaro01", 11, tree_01, 7000),
    ("Saguaro02", 23, tree_02, 8500),
    ("Saguaro03", 37, tree_03, 4000),
    ("Saguaro04", 41, tree_04, 7500),
    ("SaguaroSapling", 53, tree_sapling, 1500),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """SaguaroSeed_Icon.png (160 x 160): a ripe saguaro fruit split open, crimson pulp and black seeds, a few seeds
    lying before it, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = flower_materials()
    rnd = random.Random(9)
    m = tr.Mesh()
    fruit(m, rnd, Vector((-0.03, -0.05, 0.0)), Vector((0.55, 0.62, 0.55)).normalized(), 1.55, flaps=5, seeds=34)
    for x, y, tilt in ((-0.048, -0.065, 0.25), (-0.015, -0.074, -0.2), (0.018, -0.066, 0.1), (0.045, -0.07, -0.1)):
        seed_disc(m, Vector((x, y, 0.06)), Vector((tilt, 1.0, 0.55)), 0.0042)
    obj = m.build("SaguaroSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (0.0, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "SaguaroSeed_Icon.png"), hide=())
    print("[saguaro] icon written")


def seed_disc(m, centre, normal, radius, segs=10):
    """A small black seed: a flattened teardrop disc."""
    nrm = Vector(normal).normalized()
    _, u, v = tr.basis(nrm)
    ring = [m.v(centre + (u * math.cos(a) * (1.0 + 0.25 * math.cos(a)) + v * math.sin(a) * 0.75) * radius, leaf=(0.0, 0.0, 0.0))
            for a in (k / segs * TAU for k in range(segs))]
    top, bottom = m.v(centre + nrm * radius * 0.4), m.v(centre - nrm * radius * 0.4)
    for k in range(segs):
        k1 = (k + 1) % segs
        m.tri(ring[k], ring[k1], top, ((0, 0),) * 3, "seed")
        m.tri(ring[k1], ring[k], bottom, ((0, 0),) * 3, "seed")


# ---------------------------------------------------------------- main

def main():
    tr.reset()
    atlas = layout()
    if STEPS == "icon":
        make_icon()
        return
    if STEPS in ("all", "textures", "bark", "bark-textures"):
        make_bark()
        if STEPS in ("bark", "bark-textures"):
            return
    if STEPS in ("all", "textures", "atlas"):
        make_atlas(atlas)
        if STEPS in ("textures", "atlas"):
            return
        tr.reset()
    else:
        make_atlas(atlas, render=False)
        load_coverage(atlas)
        tr.reset()
    tr.use_atlas(atlas)
    mats = {"bark": tr.textured("SaguaroBark", paths("SaguaroBark")),
            "foot": tr.textured("SaguaroBarkFoot", paths("SaguaroBarkFoot")),
            "leaves": tr.textured("SaguaroLeaves", paths("SaguaroLeaves"), cutout=True, translucent=0.15)}
    figure = tr.stage()
    built = []
    for name, seed_, make, budget in VARIANTS:
        rnd = random.Random(seed_)
        trunk, arms = make(rnd)
        spec = make_spec(budget)
        if name == "SaguaroSapling":
            spec.foliage = None
            spec.cluster = None
        tree = assemble(spec, seed_, name, trunk, arms)
        if name != "SaguaroSapling":
            tree.cards = crown_cards(tree, random.Random(seed_ + 7), density=1.0 if name != "Saguaro03" else 0.8)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        caps = write_colliders(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[saguaro] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f, %d arms, %d cards, %d collider lines" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1], len(arms), len(tree.cards), caps))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("saguaro01", lods[0], PREVIEWS, figure)
    tr.preview_lods("saguaro01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("saguaro", [b[2][0] for b in built[:4]], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[saguaro] done")


main()
