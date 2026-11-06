"""Bristlecone pine (Pinus longaeva) for the snow biome, on treekit.py (birch.py is the worked example; TREES.md has
the rules; subalpine_fir.py and charred_snag.py the nearest relatives).

The oldest trees there are: short, massive, wind-sculpted trunks twisted by spiral grain, most of the wood long dead and
polished silver-grey to warm tan by ice and sand, deep twisting grain, checks and erosion channels, and one narrow strip
of living reddish bark spiralling up it to the few limbs still alive. Those carry dense bottle-brush "foxtails" of short
stiff dark blue-green needles at their ends, often on one side only. Dead snags and splinters, roots gripping rock.

    blender -b --factory-startup --python trees/bristlecone.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees` (absolute
paths). Steps: `all`, `textures` (bark + foxtail atlas), `bark`, `atlas`, `trees`, `icon`. It writes
Trees/Bristlecone/ (bark textures, the foxtail atlas, Bristlecone01..04 and BristleconeSapling with their impostors,
BristleconeSeed_Icon.png), the Bristlecone lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size
in game.
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
FOLDER = os.path.join(TREES, "Bristlecone")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# BristleconeBark: 4096 x 2048, once round a tube, tiling up it every pi radii (square texels), drawn at its size on a
# 45 cm radius trunk (about 14.5 px per cm): silver wood with the living strip down the middle (u = 0.5), twisted by
# UV (TWIST turns per repeat). BristleconeBarkWood: 1024 x 2048 of the same wood for dead limbs and splinters (no
# strip), drawn for a 6 cm radius limb. BristleconeBarkLive: 1024 x 2048 living bark for the live limbs and twigs.

TW, TH = 4096, 2048
K_TRUNK = TAU * TH / TW
TWIST = 0.17
STRIP_U = 0.5
LW, LH = 1024, 2048
K_LIMB = TAU * LH / LW
R_TRUNK = 45.0
R_LIMB = 6.0
PX_TRUNK = TW / (TAU * R_TRUNK)
PX_LIMB = LW / (TAU * R_LIMB)
WOOD_MEAN = (141, 130, 114)
FLUTES = 4
FLUTE_RATE = FLUTES * TAU * TWIST / K_TRUNK
UV = {
    "bark": tr.BarkUV(k=K_TRUNK, wraps=1, twist=TWIST),
    "wood": tr.BarkUV(k=K_LIMB, wraps=1, twist=0.12),
    "live": tr.BarkUV(k=K_LIMB, wraps=1),
}


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


def wrapped(canvas_hw, x, y, hw_, hh_):
    """Index arrays of a window centred on (x, y), wrapping round the edges."""
    h, w = canvas_hw
    ys = (np.arange(int(y) - hh_, int(y) + hh_ + 1)) % h
    xs = (np.arange(int(x) - hw_, int(x) + hw_ + 1)) % w
    return ys, xs


def vcrack(canvas, r, x, y, length, thick, cm, value=1.0):
    """A crack running up the grain (rows): short vertical lens pieces end to end, wandering a little sideways,
    thickest in the middle and pinching out at both ends."""
    seg = max(2.0, 3.5 * cm)
    n = max(1, int(length / seg))
    for i in range(n):
        t = math.sin(math.pi * (i + 0.5) / n) ** 0.7
        th = max(1.2, thick * t)
        k = tr.lens(seg * 1.5, th, ends=0.7).T
        tr.stamp(canvas, x, y, k * value)
        x += r.normal(0.0, 0.07 * cm)
        y += seg * 0.85


def wood(r, h, w, cm, strip=False):
    """Weathered bristlecone wood as (albedo sRGB, height in mm, roughness, occlusion, strip mask), tileable both
    ways, `cm` pixels per cm, the grain running up the rows: silver-grey to warm tan in long streaks, the hard latewood
    standing in thin wavy ridges between worn grooves (the grain's contour lines, so they crowd and part), wide
    shallow erosion channels with darker floors, long checks that follow the grain, knots ringed by their own swirl,
    polished patches where ice has scoured it smooth, brown drip stains, and pixel-level fibre and grit. With `strip`
    a narrow band of living bark (reddish plates between dark furrows) climbs the middle, raised off the wood,
    meandering, its edge ragged."""
    area = (w / cm) * (h / cm)
    Yi, Xi = np.indices((h, w))
    sway = tr.fbm(r, h, w, (16 * cm, 45 * cm), 3)
    sway2 = tr.fbm(r, h, w, (5 * cm, 20 * cm), 3)

    def wavy(a, amount):
        """The grain not quite straight: the field read through a slow sideways sway."""
        dx = ((sway - 0.5) * amount * cm + (sway2 - 0.5) * 0.4 * amount * cm).astype(np.int64)
        return a[Yi, (Xi + dx) % w]

    tone = wavy(tr.fbm(r, h, w, (10 * cm, 34 * cm), 3), 7.0)
    tone2 = wavy(tr.fbm(r, h, w, (3.0 * cm, 16 * cm), 4), 5.0)
    g1 = wavy(tr.fbm(r, h, w, (1.5 * cm, 30 * cm), 5, 0.55), 6.0)
    g2 = wavy(tr.fbm(r, h, w, (5.0 * cm, 70 * cm), 4), 8.0)
    g3 = wavy(tr.fbm(r, h, w, (0.6 * cm, 12 * cm), 4), 5.0)
    # The grain: thin ridges and grooves as the contour lines of three stretched noise fields
    s1 = np.abs(np.sin(np.pi * g1 * 9.0))
    ridge1 = tr.smoothstep(0.0, 0.7, s1)  # 0 in the groove lines, 1 on the ridges
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
    # Erosion channels: wide, long, shallow, softly edged
    chan = tr.smoothstep(0.6, 0.74, wavy(tr.fbm(r, h, w, (2.8 * cm, 60 * cm), 3), 6.0))
    polish = tr.smoothstep(0.56, 0.72, wavy(tr.fbm(r, h, w, (8 * cm, 38 * cm), 3), 6.0)) * (1.0 - chan)
    stain = tr.smoothstep(0.62, 0.8, wavy(tr.fbm(r, h, w, (0.9 * cm, 60 * cm), 4), 5.0)) * tr.smoothstep(0.3, 0.7, tone2)
    del Yi, Xi, sway, sway2

    # Checks along the grain: a few long, many medium, a fuzz of hairlines
    crack = np.zeros((h, w))
    for lo, hi, n_per_k, thick in ((30, 110, 1.6, (0.15, 0.55)), (7, 30, 8.0, (0.1, 0.35)), (1.5, 7, 22.0, (0.05, 0.2))):
        for _ in range(int(area / 1000.0 * n_per_k)):
            vcrack(crack, r, r.uniform(0, w), r.uniform(0, h), r.uniform(lo, hi) * cm,
                   r.uniform(*thick) * cm, cm, r.uniform(0.7, 1.0))
    # Knots: a hole or a bump ringed by the grain swirling round it
    kn_bump = np.zeros((h, w))
    kn_ring = np.zeros((h, w))
    kn_core = np.zeros((h, w))
    for _ in range(int(area / 4500.0)):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        rho = r.uniform(1.3, 4.0)
        rx, ry = rho * cm, rho * cm * r.uniform(1.4, 2.2)
        hw_, hh_ = int(rx * 3.2), int(ry * 3.2)
        ys, xs = wrapped((h, w), cx, cy, hw_, hh_)
        dx = (np.arange(-hw_, hw_ + 1) + (int(cx) - cx))[None, :] / rx
        dy = (np.arange(-hh_, hh_ + 1) + (int(cy) - cy))[:, None] / ry
        e = np.hypot(dx, dy)
        env = np.exp(-(e / 1.9) ** 2)
        rings = 0.5 + 0.5 * np.cos(TAU * e * r.uniform(2.5, 4.5) + r.uniform(0, 6.28))
        ix = np.ix_(ys, xs)
        kn_bump[ix] = np.maximum(kn_bump[ix], np.exp(-(e / 0.9) ** 2))
        kn_ring[ix] = np.maximum(kn_ring[ix], rings * env * (e > 0.55))
        hole = r.random() < 0.45
        kn_core[ix] = np.maximum(kn_core[ix], tr.smoothstep(0.7, 0.4, e + 0.15 * np.sin(7.0 * np.arctan2(dy, dx))) * (0.75 if hole else 0.3))

    # --- the living strip
    S = np.zeros((h, w))
    dout = np.full((h, w), 1e4)
    pb = None
    if strip:
        X = np.arange(w)[None, :].astype(np.float64)
        Yv = np.arange(h).astype(np.float64)
        shift = sum(a * np.sin(TAU * kk * Yv / h + r.uniform(0, TAU)) for kk, a in ((1, 5.0), (2, 2.4), (3, 1.0))) * cm
        halfw = (0.058 * w + sum(a * np.sin(TAU * kk * Yv / h + r.uniform(0, TAU)) for kk, a in ((1, 0.004), (2, 0.003), (4, 0.0015))) * w)
        ragged = (tr.fbm(r, h, w, (1.0 * cm, 4.0 * cm), 3) - 0.5) * 2.4 * cm
        dist = np.abs(X - (w * STRIP_U + shift[:, None]))
        dout = dist - (halfw[:, None] + ragged)
        S = 1.0 - tr.smoothstep(-0.12 * cm, 0.12 * cm, dout)
        pb = plate_bark(r, h, w, cm, 2.7, 6.5)

    # --- colour (sRGB)
    silver, tan = np.array((0.60, 0.59, 0.57)), np.array((0.66, 0.54, 0.40))
    col = tr.mix(silver, tan, 0.45 * tr.smoothstep(0.5, 0.85, tone))
    lum = 0.74 + 0.5 * (0.4 * tone2 + 0.2 * grit + 0.2 * fib + 0.2 * ridge3)
    col = col * lum[..., None]
    col = col * (1.0 + 0.22 * (ridge1 - 0.5) * (1.0 - 0.6 * polish) + 0.12 * (ridge2 - 0.5) + 0.14 * (ridge3 - 0.5))[..., None]
    col = tr.mix(col, col * 0.5, (groove1 * 0.6 * (1.0 - 0.7 * polish))[..., None])
    col = tr.mix(col, col * 0.62, groove2 * 0.45)
    col = tr.mix(col, col * 0.7, groove3 * 0.4)
    col = tr.mix(col, silver * 1.1, polish * 0.4)
    col = tr.mix(col, (0.36, 0.28, 0.2) * (0.7 + 0.3 * grit)[..., None], chan * 0.5)
    col = tr.mix(col, (0.26, 0.19, 0.13), stain * 0.55)
    col = tr.mix(col, (0.12, 0.09, 0.065), np.clip(crack, 0, 1) * 0.92)
    col = tr.mix(col, col * 0.68, kn_ring * 0.55)
    col = tr.mix(col, (0.2, 0.14, 0.1), kn_bump * 0.4)
    col = tr.mix(col, (0.12, 0.085, 0.06), kn_core * 0.9)
    col = col * (0.93 + 0.14 * fib)[..., None]
    if strip:
        # Wood just outside the strip: darkened, sap-stained
        near = np.exp(-np.maximum(dout, 0.0) / (1.6 * cm))
        col = col * (1.0 - 0.38 * near)[..., None]
        col = tr.mix(col, (0.3, 0.2, 0.13), (near * 0.25)[..., None])
        col = tr.mix(col, pb["col"], S[..., None])

    # --- height (mm), roughness, occlusion
    hmm = (0.5 * ridge1 + 0.9 * ridge2 + 0.35 * ridge3 - 4.5 * chan - 6.0 * np.clip(crack, 0, 1) + 0.7 * fib + 0.3 * grit
           + 2.2 * kn_bump + 0.5 * kn_ring - 3.0 * kn_core)
    rough = 0.86 - 0.28 * polish + 0.1 * chan + 0.05 * (grit - 0.5)
    if strip:
        hmm = hmm * (1.0 - S) + S * (6.0 + pb["hmm"])
        rough = rough * (1.0 - S) + S * pb["rough"]
    px_per_mm = cm / 10.0
    hpx = hmm * px_per_mm
    occ = tr.cavity(hpx, 0.5 * cm, 0.05)
    col = col * (0.72 + 0.28 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), hpx, np.clip(rough, 0.0, 1.0), occ, S


def plate_bark(r, h, w, cm, size, stretch):
    """Living bark: long plates `size` cm across (`stretch` times as long) in a muted red-brown going grey where they
    weather, dark furrows between them of every width, fibrous streaks up the plates, short checks across, a few
    pale lichen crusts. Returns dict(col, hmm, rough)."""
    sz = size * cm
    warp = ((tr.fbm(r, h, w, (1.2 * sz, 3.0 * sz), 3) - 0.5) * 0.55 * sz,
            (tr.fbm(r, h, w, (1.2 * sz, 3.0 * sz), 3) - 0.5) * 1.1 * sz)
    pe, pidx, _, _ = tr.cells(r, h, w, sz, stretch, warp)
    shade = r.random(pidx.max() + 1)[pidx]
    vary = tr.fbm(r, h, w, (1.5 * sz, 4 * sz), 3)
    fw = (0.03 + 0.1 * vary) * sz
    furrow = 1.0 - tr.smoothstep(0.0, fw, pe)
    dome = tr.smoothstep(0.0, 0.33 * sz, pe)
    fibre = tr.fbm(r, h, w, (0.07 * cm, 2.2 * cm), 3)
    streak = tr.fbm(r, h, w, (0.5 * cm, 9 * cm), 3)
    grit = tr.fbm(r, h, w, (0.07 * cm, 0.07 * cm), 2)
    grey = tr.smoothstep(0.4, 0.75, tr.fbm(r, h, w, (2.5 * sz, 4 * sz), 3))
    checks = np.zeros((h, w))
    for _ in range(int(h / cm * w / cm * 0.04 * (2.7 / size) ** 2)):
        tr.stamp_lens(checks, r.uniform(0, w), r.uniform(0, h), r.uniform(0.35, 1.2) * size / 2.7 * cm,
                      max(1.3, r.uniform(0.05, 0.1) * cm), r.uniform(0.5, 1.0), ends=0.8)
    lichen = (tr.smoothstep(0.8, 0.9, tr.fbm(r, h, w, (0.4 * cm, 0.4 * cm), 4))
              * tr.smoothstep(0.45, 0.7, tr.fbm(r, h, w, (8 * cm, 10 * cm), 3)))
    base = tr.mix((0.2, 0.125, 0.1), (0.4, 0.265, 0.21), 0.1 + 0.75 * shade)
    base = tr.mix(base, (0.44, 0.4, 0.375), (grey * (0.35 + 0.5 * dome))[..., None] * 0.7)
    col = base * (0.62 + 0.22 * streak + 0.36 * fibre + 0.14 * grit)[..., None]
    col = tr.mix(col, col * 1.12, (dome * 0.5)[..., None])
    col = tr.mix(col, (0.07, 0.045, 0.04), np.clip(furrow * 1.1, 0, 1)[..., None])
    col = tr.mix(col, (0.1, 0.065, 0.055), np.clip(checks, 0, 1)[..., None] * 0.8)
    col = tr.mix(col, (0.5, 0.54, 0.45), (lichen * 0.45)[..., None])
    hmm = 2.6 * dome - 3.5 * furrow - 1.3 * np.clip(checks, 0, 1) + 0.5 * fibre + 0.6 * streak + 0.2 * grit
    rough = 0.92 - 0.05 * dome + 0.04 * (grit - 0.5)
    return dict(col=col, hmm=hmm, rough=rough)


def live_bark(r, h, w, cm):
    """Living bark for limbs and twigs (plate_bark all over)."""
    pb = plate_bark(r, h, w, cm, 1.6, 4.0)
    hpx = pb["hmm"] * cm / 10.0
    occ = tr.cavity(hpx, 0.4 * cm, 0.05)
    col = pb["col"] * (0.74 + 0.26 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), hpx, np.clip(pb["rough"], 0.0, 1.0), occ


def make_bark(only=None):
    r = np.random.default_rng(31)

    def save(name, col, hpx, rough, occ, strength):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(hpx, 0.5), strength))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, hpx, rough, occ, S = wood(r, TH, TW, PX_TRUNK, strip=True)
    graded, k = tr.match_mean(col, WOOD_MEAN, S < 0.5)
    col = graded
    print("[bristlecone] trunk bark graded by %s, mean wood %s, strip share %.3f" % (
        np.round(k, 3), np.round(col[S < 0.5].mean(0) * 255).astype(int), float(S.mean())))
    save("BristleconeBark", col, hpx, rough, occ, 1.5)
    crop(col, PX_TRUNK, "bristlecone_bark_crop")
    del col, hpx, rough, occ, S
    col, hpx, rough, occ, S = wood(r, LH, LW, PX_LIMB, strip=False)
    graded, k = tr.match_mean(col, WOOD_MEAN)
    save("BristleconeBarkWood", graded, hpx, rough, occ, 1.5)
    col, hpx, rough, occ = live_bark(r, LH, LW, PX_LIMB)
    save("BristleconeBarkLive", col, hpx, rough, occ, 1.4)


def crop(col, cm, name):
    """Overview (a quarter size) and a 1:1 crop of a bark texture, for review."""
    h, w = col.shape[:2]
    tr.write_png(os.path.join(PREVIEWS, name + "_all.png"), col[::4, ::4])
    c0 = int(w * 0.5 - 600)
    tr.write_png(os.path.join(PREVIEWS, name + "_1to1.png"), col[h // 2 - 400:h // 2 + 400, max(0, c0):max(0, c0) + 1200])
    tr.write_png(os.path.join(PREVIEWS, name + "_1to1_wood.png"), col[h // 2 - 400:h // 2 + 400, 300:1500])


# ---------------------------------------------------------------- the foxtail atlas
#
# Five foxtail cells (320 x 1024: a bottle-brush of needles round a twig, hanging down the card from where it starts),
# two cluster cells (1024 square, a limb's end bristling with foxtails: LOD2) and a small sprig for the seedling.

FOXES = ("Fox0", "Fox1", "Fox2", "Fox3", "Fox4")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"
NEEDLE_MEAN = (63, 80, 71)


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(FOXES):
        atlas.cell(name, 320 * i, 1024, 320, 1024, (0.14, 0.42))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 0, 1024, 1024, (1.0, 1.0))
    atlas.cell(LEAF, 1664, 1024, 128, 256, (0.06, 0.12), pad=8)
    return atlas


def needle(m, base, way, normal, length, width, rv, age):
    """One flat needle: "leaf" = (across, along, random), "age" = how near its twig's tip."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = nl - d * nl.dot(d)
    nl = nl.normalized() if nl.length > 1e-6 else d.orthogonal().normalized()
    side = nl.cross(d)
    rows = []
    for s, wf in ((0.0, 0.6), (0.4, 1.0), (0.85, 0.7), (1.0, 0.0)):
        c = Vector(base) + d * (s * length) + nl * (0.07 * length * s * s)
        rows.append((m.v(c - side * (wf * width * 0.5), leaf=(-1.0, s, rv), age=age),
                     m.v(c + side * (wf * width * 0.5), leaf=(1.0, s, rv), age=age)))
    uv = ((0, 0),) * 4
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        m.quad(a0, a1, b1, b0, uv, "leaf")


def foxtail(m, rnd, length, start=None, way=(0.0, -1.0, 0.0), bend=0.3, spacing=0.0016, nlen=(0.034, 0.046),
            width=0.002):
    """A foxtail: a stout twig `length` long from `start` along `way`, curving a little, its needles (fascicles of
    five, 3 to 4 cm) crowding all round it, swept forward along it, shorter and brighter toward the growing tip."""
    start = Vector(start) if start is not None else Vector()
    side = Vector((rnd.choice((-1.0, 1.0)), 0.0, 0.0))
    pts = tr.bend_path(start, way, length, bend, steps=10, down=(side.x * 0.6, -0.2, 0.3))
    rad = [0.0042 * (1.0 - 0.35 * i / (len(pts) - 1)) for i in range(len(pts))]
    tr.twig(m, pts, rad, "twig", 5)
    tw = tr.Branch(pts, rad)
    n = int(tw.length / spacing)
    for i in range(n):
        f = 0.03 + 0.97 * (i + rnd.random()) / n
        p, tan, rr = tw.at(min(f, 0.999))
        _, u, v = tr.basis(tan)
        ph = i * tr.GOLDEN + rnd.uniform(-0.2, 0.2)
        radial = u * math.cos(ph) + v * math.sin(ph)
        sidev = tan.cross(radial)
        tip = tr.smoothstep(0.82, 1.0, f)
        for j in range(5):
            fan = math.radians(rnd.uniform(-24.0, 24.0))
            theta = math.radians(rnd.uniform(9.0, 30.0) * (1.0 - 0.45 * tip) + 3.0)
            wy = tan * math.cos(theta) + (radial * math.cos(fan) + sidev * math.sin(fan)) * math.sin(theta)
            L = rnd.uniform(*nlen) * (1.0 - 0.55 * tip) * (0.8 + 0.2 * min(1.0, f * 8.0))
            needle(m, p + radial * rr * 0.9, wy, radial, L, width, rnd.random(), f)


def leaf_materials(shade=0.0):
    """The foxtails' own materials (rendered into the atlas, not exported): needles ("leaf"), twig, cone, prickle."""
    mat, g = tr.tk.new_material("BristleNeedleSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    age = g.node("ShaderNodeAttribute", attribute_name="age").outputs["Fac"]
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Dark blue-green, some needles bluer, some greener; the newest growth at the tip a shade lighter; a waxy pale
    # fleck here and there (the resin dots)
    base = g.mix(g.ramp(rv, 0.15, 0.95), (0.018, 0.05, 0.04), (0.035, 0.085, 0.07))
    base = g.mix(g.ramp(rv, 0.82, 1.0), base, (0.03, 0.075, 0.09))
    col = g.mix(g.math("MULTIPLY", g.ramp(age, 0.85, 0.98), 0.4), base, (0.07, 0.13, 0.09))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.0, 0.25), 0.5), col, (0.06, 0.1, 0.07))
    col = g.mix(g.ramp(g.noise(700.0, detail=1.0), 0.7, 0.74), col, (0.35, 0.37, 0.34))
    col = g.mix(back, col, g.mix(0.3, col, (0.1, 0.16, 0.14)))
    if shade:
        col = g.mix(shade, col, (0.01, 0.02, 0.015))
    rough = g.mixf(back, 0.5, 0.6)
    tr.tk.finish(mat, g, col, 0.0, rough)
    leaf = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("BristleTwigSrc")
    col = g.mix(g.ramp(g.noise(160.0, detail=3.0), 0.3, 0.7), (0.1, 0.05, 0.035), (0.2, 0.11, 0.07))
    tr.tk.finish(mat, g, col, 0.0, 0.7)
    twig = tr.signals(mat, col, 0.7)

    mat, g = tr.tk.new_material("BristleConeSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(g.noise(300.0, detail=3.0), 0.3, 0.7), (0.1, 0.055, 0.04), (0.2, 0.12, 0.085))
    col = g.mix(g.math("MULTIPLY", g.ramp(rv, 0.2, 1.0), 0.5), col, (0.16, 0.09, 0.065))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.7, 1.0), 0.5), col, (0.3, 0.2, 0.13))
    tr.tk.finish(mat, g, col, 0.0, 0.55, g.bump(g.noise(400.0, detail=3.0), 0.3, 0.0003))
    cone_mat = tr.signals(mat, col, 0.55)

    mat, g = tr.tk.new_material("BristlePrickleSrc")
    col = g.mix(g.ramp(g.noise(200.0, detail=2.0), 0.3, 0.7), (0.2, 0.13, 0.08), (0.34, 0.24, 0.15))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    prickle = tr.signals(mat, col, 0.6)
    return {"leaf": leaf, "twig": twig, "petiole": twig, "cone": cone_mat, "prickle": prickle}


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(61)
    foxes = []
    for i, name in enumerate(FOXES):
        m = tr.Mesh()
        foxtail(m, rnd, rnd.uniform(0.3, 0.42), bend=rnd.uniform(0.0, 0.5))
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        foxes.append(obj)
    if render:
        for name, o in zip(FOXES, foxes):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        m = tr.Mesh()
        stem = tr.bend_path(Vector(), Vector(((1, -1)[ci] * 0.25, -1.0, 0.0)), 0.8, 0.5, steps=10, down=(0.0, -1.0, 0.0))
        tr.twig(m, stem, [0.012 * (1.0 - 0.6 * i / (len(stem) - 1)) for i in range(len(stem))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        br = tr.Branch(stem, [0.01] * len(stem))
        for j in range(18):
            f = 0.1 + 0.9 * (j + rnd.uniform(0.2, 0.8)) / 18
            p, tan, _ = br.at(min(0.999, f))
            c = foxes[rnd.randrange(len(foxes))].copy()
            tr.tk.link(c)
            spin = (j % 2 * 2 - 1) * rnd.uniform(15.0, 62.0)
            rot = (Matrix.Rotation(math.radians(spin), 4, "Z") @ Matrix.Rotation(math.radians(rnd.uniform(-30, 30)), 4, "Y")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-10, 10)), 4, "X"))
            c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.8, 1.05) * (1.0 - 0.3 * f), 4)
            objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    m = tr.Mesh()
    foxtail(m, random.Random(9), 0.1, bend=0.3, spacing=0.0014, nlen=(0.014, 0.02), width=0.0012)
    sprig = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [sprig])
    if render:
        atlas.render(atlas.cells[LEAF], [sprig])
    if not render:
        return None
    atlas.grade(list(FOXES) + list(CLUSTERS) + [LEAF], NEEDLE_MEAN)
    out = atlas.save(FOLDER, "BristleconeLeaves")
    atlas.preview(os.path.join(PREVIEWS, "bristlecone_atlas.png"))
    for c in atlas.cells.values():
        print("[bristlecone] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("BristleconeLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- trunk: spiral axis

_grow_trunk = tr.grow_trunk


def twisted_trunk(rnd, t):
    """tr.grow_trunk, then the axis corkscrewed round (t.helix = (amplitude m, pitch m, phase)): the massive twisted
    trunks of the oldest trees. Nothing moves below the ground."""
    br = _grow_trunk(rnd, t)
    amp, pitch, phase = getattr(t, "helix", (0.0, 1.0, 0.0))
    if amp:
        for p in br.points:
            z = max(0.0, p.z)
            a = amp * tr.smoothstep(0.0, 1.4, z) * (0.55 + 0.45 * min(1.0, z / (t.height * 0.6)))
            ang = TAU * z / pitch + phase
            p.x += a * (math.cos(ang) - math.cos(phase))
            p.y += a * (math.sin(ang) - math.sin(phase))
        br.measure()
    return br


tr.grow_trunk = twisted_trunk


# ---------------------------------------------------------------- the trees

def az_of(b):
    d = b.points[-1] - b.points[0]
    return math.atan2(d.y, d.x)


def live_test(az0, n_dead):
    """Level.on for the twigs: the limb that faces the least toward `az0` (the way the living strip runs), `n_dead` of
    them, are dead and bear nothing."""
    def on(parent):
        kids = [b for b in parent.root.children if b.level == 1]
        order = sorted(kids, key=lambda b: math.cos(az_of(b) - az0))
        return parent not in order[:n_dead]
    return on


def bark_key_for(young):
    def bark_key(br, s, r, z):
        if br.level == 0:
            return "live" if young else "bark"
        if br.tags & {"stub", "dead", "splinter"}:
            return "wood"
        return "live"
    return bark_key


def trunk(**kw):
    helix = kw.pop("helix", (0.0, 1.0, 0.0))
    flutes = kw.pop("flutes", None)
    base = dict(flare=0.9, flare_height=0.6, lobes=(5, 0.3), taper=0.5, tip_radius=0.1, wander=0.3, broken=True,
                step=0.3, sides=(20, 12, 8), seg=(0.16, 0.45, 1.2), rings=((0.0, 0.2, 0.5, 1.0), (0.0, 0.5), (0.0,)))
    base.update(kw)
    t = tr.Trunk(**base)
    t.helix = helix
    if flutes:
        t.flutes = flutes
    return t


def bristlecone(trunks, n_live=3, n_dead=0, az0=0.0, reach=1.0, young=False, stubs=(6, 9), budget=5600, twigs=6.0,
                limb_len=(1.3, 2.6), limb_span=(0.35, 0.85), favor=None, spacing=0.03, card_scale=(1.0, 1.35)):
    """A bristlecone's TreeSpec: `trunks`; `n_live` limbs (and `n_dead` more that died: bare, silver) off the trunk,
    wrenched upward and sideways by the wind (wander, gravitropism), each with twigs that end in foxtails; dead limb
    stubs and splinters (`stubs`) all over the trunk, thin spikes near the broken top."""
    limbs = tr.Level(count=n_live + n_dead, span=limb_span, length=(limb_len[0] * reach, limb_len[1] * reach),
                     shape="flat", angle=62.0, angle_tip=42.0, angle_vary=14.0, radius=0.38, radius_length=0.4,
                     radius_max=0.17, tip_radius=0.012, taper=0.9, step=0.2, gravitropism=0.45, droop=0.12,
                     wander=0.6, floor=0.6, favor=favor, sides=(8, 5, 4), seg=(0.35, 0.9, 1.8),
                     min_len=(0.0, 0.4, 1.0))
    tw = tr.Level(per_meter=twigs, span=(0.15, 1.0), length=(0.3, 0.75), shape="flat", angle=55.0, angle_tip=35.0,
                  angle_vary=18.0, radius=0.45, radius_length=0.4, radius_max=0.025, tip_radius=0.004, taper=0.8,
                  step=0.12, gravitropism=0.55, droop=0.1, wander=0.7, floor=0.6, sides=(4, 3, 0), seg=(0.3, 0.7, 9.0),
                  min_len=(0.0, 0.0, 99.0), on=live_test(az0, n_dead))
    stubs_lv = tr.Level(count=stubs, span=(0.16, 0.995), length=(0.35, 1.5), shape="flat", angle=72.0, angle_tip=18.0,
                        angle_vary=12.0, radius=0.4, radius_length=0.5, radius_max=0.12, tip_radius=0.012,
                        broken=True, step=0.1, gravitropism=0.1, droop=0.3, wander=0.5, floor=0.3, sides=(7, 5, 0),
                        seg=(0.3, 0.8, 9.0), min_length=0.1, min_len=(0.0, 0.3, 99.0))
    fol = tr.Foliage(levels={2: (0.2, 1.0), 1: (0.6, 1.0)}, spacing=spacing, cells=FOXES, scale=card_scale,
                     hang=0.08, spread=0.22, out=0.3, face=0.4, up=0.25, roll=90.0, bend=0.0,
                     on=lambda br: not (br.tags & {"dead", "stub", "splinter"}))
    cluster = tr.Foliage(levels={1: (0.3, 1.0)}, spacing=0.7, cells=CLUSTERS, scale=(0.85, 1.1), hang=0.12,
                         spread=0.25, out=0.5, face=0.5, up=0.2, roll=40.0, bend=15.0,
                         on=lambda br: not (br.tags & {"dead", "stub", "splinter"}))
    spec = tr.TreeSpec(trunks=trunks, levels=[limbs, tw], stubs=stubs_lv, budget=budget, bark_budget=3600,
                       bark_key=bark_key_for(young), bark_uv=UV, ground_v=0.0, lod_share=(0.45, 0.2))
    spec.bristle = (fol, cluster)
    return spec


def sapling():
    """The planted seed's seedling: a 0.45 m stem with a few short twigs, each with a small foxtail (the Leaf cell)."""
    shoots = tr.Level(per_meter=9.0, whorl=1, span=(0.3, 0.95), length=(0.05, 0.12), shape="tapered", angle=65.0,
                      angle_tip=50.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0008, step=0.03,
                      gravitropism=0.2, wander=0.4, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.03, min_len=(0.0, 0.0, 99.0))
    spec = tr.TreeSpec(
        trunks=[tr.Trunk(height=0.45, radius=0.006, flare=0.2, flare_height=0.04, taper=0.8, tip_radius=0.002,
                         lean=(0.03, 0.01), bow=0.3, wander=0.015, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.08, cells=(LEAF,), scale=(0.9, 1.1),
                           hang=0.15, spread=0.3, out=0.7, face=0.4, up=0.2, roll=20.0, bend=0.0),
        bark_key=lambda br, s, r, z: "live", bark_uv=UV, budget=700, lod_share=(0.55, 0.3), ground_v=0.0)
    spec.bristle = (tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.5, 1.0), spacing=0.05, cells=(LEAF,), scale=(0.8, 1.1),
                               hang=0.12, spread=0.3, out=0.6, face=0.4, up=0.2, roll=45.0, bend=0.0), None)
    return spec


def rotate_subtree(branch, pivot, degrees):
    ang = math.radians(degrees)
    c, s = math.cos(ang), math.sin(ang)
    stack = [branch]
    while stack:
        b = stack.pop()
        for p in b.points:
            dx, dy = p.x - pivot.x, p.y - pivot.y
            p.x, p.y = pivot.x + dx * c - dy * s, pivot.y + dx * s + dy * c
        stack.extend(b.children)


def sweep(tree, wind, k, spread=50.0):
    """Wind-flag the tree: every limb that heads upwind is swung round its base to leeward (to within `spread`
    degrees of the wind), then every branch is bent downwind more the farther it reaches from the trunk."""
    w = Vector(wind).normalized()
    rnd = random.Random(tree.seed + 5)
    trunk0 = tree.trunks[0]
    for limb in [b for b in tree.branches if b.level == 1 and b.parent is trunk0]:
        d = limb.points[-1] - limb.points[0]
        hz = Vector((d.x, d.y, 0.0))
        if hz.length < 1e-3:
            continue
        hz.normalize()
        if hz.dot(w) < 0.3:
            target = math.atan2(w.y, w.x) + math.radians(rnd.uniform(-spread, spread))
            rotate_subtree(limb, limb.points[0], math.degrees(target - math.atan2(hz.y, hz.x)))
    for b in tree.branches:
        if b.level == 0:
            continue
        for p in b.points:
            q = trunk0.point_at_height(p.z)
            hdist = math.hypot(p.x - q.x, p.y - q.y)
            p += w * (k * hdist ** 1.4)
    for b in tree.branches:
        b.measure()


def align_strip(tree):
    """Turns the main trunk's bark so the living strip passes where its thickest live limb leaves."""
    t = tree.trunks[0]
    limbs = [b for b in t.children if b.level == 1 and b.children and "stub" not in b.tags]
    if not limbs:
        return
    limb = max(limbs, key=lambda b: b.radii[0] * b.length)
    s = limb.s_parent
    fr = tr.frames(t.points)
    target = s * t.length
    i = min(max(next((j for j, c in enumerate(t.cum) if c >= target), len(t.cum) - 1), 0), len(fr) - 1)
    _, nr, bn = fr[i]
    d = limb.points[1] - limb.points[0]
    theta = math.atan2(d.dot(bn), d.dot(nr))
    v = t.turns(s) / K_TRUNK + 0.0
    fu = STRIP_U - TWIST * v
    t.rot = theta - fu * TAU


def tag_dead(tree):
    for b in tree.branches:
        if b.level == 1 and not b.children and "stub" not in b.tags:
            b.tags.add("dead")


def make_tree(name, seed, spec, wind=None, wind_k=0.0, young=False):
    fol, cluster = spec.bristle
    tree = tr.grow(spec, seed, name)
    if wind is not None:
        sweep(tree, wind, wind_k)
    if not young and len(spec.levels) > 1:
        tag_dead(tree)
    if not young and name != "BristleconeSapling":
        align_strip(tree)
    spec.foliage, spec.cluster = fol, cluster
    tree.cards = tr.place_cards(random.Random(seed + 7), tree, fol)
    return tree


def variants():
    return [
        # The classic: about 6.5 m, a massive trunk wrung into a corkscrew, most of its wood dead and silver, the
        # strip of living bark spiralling up to three live limbs
        ("Bristlecone01", 5, False, lambda: bristlecone(
            [trunk(height=6.6, radius=0.58, lean=(0.7, -0.3), bow=0.35, wander=0.35, taper=0.5, tip_radius=0.13,
                   helix=(0.17, 3.0, 0.6), flutes=(FLUTES, 0.13, FLUTE_RATE))],
            n_live=3, n_dead=1, az0=0.4, stubs=(7, 10)), None, 0.0),
        # The tallest: about 9 m, leaning, one limb dead and bleached, the rest living
        ("Bristlecone02", 17, False, lambda: bristlecone(
            [trunk(height=9.0, radius=0.46, lean=(2.3, 0.9), bow=0.5, wander=0.3, taper=0.45, tip_radius=0.1,
                   helix=(0.14, 3.6, 2.0), flutes=(FLUTES, 0.12, FLUTE_RATE), lobes=(5, 0.25))],
            n_live=4, n_dead=1, az0=2.2, reach=1.1, stubs=(8, 11), budget=5600, limb_span=(0.3, 0.9)), None, 0.0),
        # A low gnarled flag: about 4 m, a huge short trunk, every limb swept to leeward by the wind (+x)
        ("Bristlecone03", 29, False, lambda: bristlecone(
            [trunk(height=4.1, radius=0.8, lean=(0.9, 0.2), bow=0.3, wander=0.25, taper=0.45, tip_radius=0.2,
                   helix=(0.2, 2.6, 4.0), flutes=(FLUTES, 0.14, FLUTE_RATE), lobes=(6, 0.3), flare=0.7)],
            n_live=4, n_dead=0, az0=0.0, reach=1.0, stubs=(5, 7), limb_len=(1.4, 2.4), limb_span=(0.4, 0.92),
            favor=((1.0, 0.0), 0.5), budget=4800), (1.0, 0.1, 0.0), 0.35),
        # Young: about 3.5 m, bushy and mostly alive, living bark all over
        ("Bristlecone04", 41, True, lambda: bristlecone(
            [trunk(height=3.6, radius=0.2, lean=(0.35, 0.2), bow=0.3, wander=0.18, taper=0.8, tip_radius=0.02,
                   flare=0.5, lobes=(4, 0.1), broken=False, sides=(14, 9, 6), seg=(0.2, 0.5, 1.2))],
            n_live=10, n_dead=0, az0=0.0, reach=0.6, young=True, stubs=(1, 2), limb_len=(0.7, 1.3),
            limb_span=(0.14, 0.97), twigs=7.0, budget=5600, spacing=0.03, card_scale=(0.95, 1.25)), None, 0.0),
        ("BristleconeSapling", 53, True, sapling, None, 0.0),
    ]


# ---------------------------------------------------------------- the seed's icon

def bcone(m, rnd, base, length, up, scales=80):
    """A bristlecone cone: egg-shaped, dark purple-brown, each scale ending in a slender curved prickle."""
    up = Vector(up).normalized()
    R = length * 0.34
    shape = [0.55, 0.85, 1.0, 1.0, 0.95, 0.85, 0.7, 0.5, 0.2]
    core = [base + up * (length * i / 8) for i in range(9)]
    tr.twig(m, core, [R * 0.78 * k for k in shape], "cone", 14)
    _, u, v = tr.basis(up)
    for i in range(scales):
        f = 0.05 + 0.88 * (i + 0.5) / scales
        a = i * tr.GOLDEN + rnd.uniform(-0.1, 0.1)
        out = u * math.cos(a) + v * math.sin(a)
        k = float(np.interp(f, np.linspace(0.0, 1.0, len(shape)), shape))
        p = base + up * (f * length) + out * (R * 0.7 * k)
        sl = length * rnd.uniform(0.16, 0.2) * (0.6 + 0.4 * k)
        way = (out * 0.55 + up * 0.83).normalized()
        tr.blade(m, p, way, out, sl, sl * 1.3, lambda s: math.sin(math.pi * min(1.0, 0.12 + 0.88 * s)) ** 0.5, "cone",
                 fold=-0.1, arch=0.25, rows=5, rnd_value=rnd.random())
        # The prickle, from the scale's pale outer lip, curving out and up
        tip = p + way * sl * 0.92 + out * (sl * 0.08)
        pl = length * 0.075
        pts = [tip, tip + (out * 0.9 + up * 0.3) * pl * 0.5, tip + (out * 0.8 + up * 0.55) * pl]
        tr.twig(m, pts, [length * 0.012, length * 0.008, length * 0.002], "prickle", 3)


def make_icon():
    """BristleconeSeed_Icon.png (160 x 160, in Trees/Bristlecone): a spiny cone on a sprig of foxtail, drawn like
    vanilla's pine cone seed under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials()
    rnd = random.Random(11)
    m = tr.Mesh()
    foxtail(m, rnd, 0.17, start=Vector((0.07, -0.01, -0.01)), way=(-1.0, 0.18, 0.0), bend=0.1, spacing=0.0032,
            nlen=(0.022, 0.03), width=0.0017)
    bcone(m, rnd, Vector((-0.02, -0.03, 0.03)), 0.085, (0.12, 1.0, 0.2), 90)
    obj = m.build("BristleconeSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (0.0, 0.0, 0.2)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "BristleconeSeed_Icon.png"), hide=())
    print("[bristlecone] icon written")


# ---------------------------------------------------------------- main

def main():
    tr.reset()
    atlas = layout()
    if STEPS == "icon":
        make_icon()
        return
    if STEPS in ("all", "textures", "bark"):
        make_bark()
        if STEPS == "bark":
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
    mats = {"bark": tr.textured("BristleconeBark", paths("BristleconeBark")),
            "wood": tr.textured("BristleconeBarkWood", paths("BristleconeBarkWood")),
            "live": tr.textured("BristleconeBarkLive", paths("BristleconeBarkLive")),
            "leaves": tr.textured("BristleconeLeaves", paths("BristleconeLeaves"), cutout=True, translucent=0.2)}
    figure = tr.stage()
    built = []
    for name, seed, young, make, wind, wk in variants():
        spec = make()
        tree = make_tree(name, seed, spec, wind, wk, young)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        # Colliders: the whole trunk, a little fat for its ridges, so no part of it can be walked into
        t0 = tree.trunks[0]
        depth = getattr(t0.spec, "flutes", (0, 0.0, 0))[1]
        for tt in tree.trunks:
            tt.radii = [x * (1.0 + 0.9 * depth) * (1.0 + 0.5 * getattr(tt.spec, 'lobes', (0, 0.0))[1] * math.exp(-max(0.0, p.z) / 0.6))
                        for x, p in zip(tt.radii, tt.points)]
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree, top=0.98, step=0.35)
        print("[bristlecone] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    real = [b for b in built if b[0] != "BristleconeSapling"]
    for name, tree, lods, size in real:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = real[0]
    tr.preview_bark("bristlecone01", lods[0], PREVIEWS, figure)
    tr.preview_lods("bristlecone01", lods, PREVIEWS, figure, size[0], max(size[2] * 2.0, 4.0))
    tr.preview_grove("bristlecone", [b[2][0] for b in real], PREVIEWS, figure,
                     spots=[(-6.0, 4.0), (0.5, 9.0), (6.5, 2.0), (-1.5, -2.5)])
    if STEPS == "all":
        make_icon()
    print("[bristlecone] done")


main()
