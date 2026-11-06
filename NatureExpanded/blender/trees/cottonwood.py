"""Eastern / Fremont cottonwood (Populus deltoides) in summer, on treekit.py (wolf_oak.py and aspen.py are the closest
examples; TREES.md has the rules).

A big river tree: a massive straight trunk, 1.0 to 1.4 m across at breast height, in very thick, deeply furrowed pale
grey-brown bark (flat-topped ridges 6 to 12 cm wide running up between narrow black furrows that fork and rejoin),
rising to 40 % of its height or more bare but for a few dead stubs, then giving out a few huge limbs that climb at 20
to 40 degrees and fork again and again into a tall, open, irregular vase 15 to 20 m across, some limbs dead. Smoother,
paler greenish-grey bark on the limbs. Leaves 7 to 10 cm, deltoid (a flat or heart-shaped base, a long point, coarse
rounded teeth) on long flat petioles, glossy yellow-green: they tremble in any breeze (NatureTreeBuilder
FlutterScales).

    blender -b --factory-startup --python trees/cottonwood.py -- <unity trees folder> <preview folder> [step] [variants]

with absolute paths `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`.
Steps: `all`, `textures` (bark, limb bark and leaves, then stop), `bark`, `bark-textures`, `atlas`, `trees`, `icon`,
`skeleton` (the trees without leaves, previews only). It writes Trees/Cottonwood/ (bark, limb bark, twig bark and leaf
textures, Cottonwood01..04 and the seedling CottonwoodSapling with their impostors, CottonwoodSeed_Icon.png), the
Cottonwood lines of Trees/trees.txt and trunks.txt (the trunk's, and the low part of every thick limb a player could
walk into) and the previews. Built at its size in game.
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
ONLY = args[3:]
FOLDER = os.path.join(TREES, "Cottonwood")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
UP, DOWN = tr.UP, tr.DOWN

# ---------------------------------------------------------------- bark textures
#
# CottonwoodBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (4 m on the trunk's 65 cm
# radius), drawn at its size on that trunk (10 px per cm round and up): flat-topped ridges 6 to 12 cm wide running
# up between narrow, deep, black furrows that fork and rejoin, a few cross checks, fibrous, pale grey-tan on the ridge
# tops with brown in patches. CottonwoodBarkLimb: 1024 x 2048, once round a limb of 18 cm radius (9 px per cm): the
# younger bark of limbs and young trunks, smoother, greener grey, shallow broken furrows and lenticels.
# CottonwoodBarkTwig: 512 x 1024, the smooth olive-tan bark of thin twigs.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)  # radii per repeat up a tube: 2 pi
R_DESIGN = 65.0  # cm: the trunk the bark is drawn for (Cottonwood01's, 1 m up)
PX = WRAPS * W / (TAU * R_DESIGN)  # pixels per cm round and up that trunk
RELIEF = PX / 13.0
TWIST = 0.31
LW, LH = 1024, 2048
LIMB_R_DESIGN = 18.0
LPX = LW / (TAU * LIMB_R_DESIGN)
LIMB_R = 0.2  # a limb thinner than this (radius, m) has the limb bark
BARK_MEAN = (88, 83, 76)
LIMB_MEAN = (98, 96, 84)
LEAF_MEAN = (82, 98, 56)
TWIG_R = 0.012
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "limb": tr.BarkUV(k=TAU * LH / LW),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    if "stub" in br.tags:
        return "bark"
    if br.level == 0:
        return "limb" if "young" in br.tags else "bark"
    return "bark" if r >= LIMB_R else "limb"


def cotton_bark(r, h=H, w=W, px=PX, scale=1.0, deep=1.0):
    """Cottonwood bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: broad
    flat-topped ridges running up between narrow deep furrows (`deep` 1 on the trunk, less on limbs), cross-cracked
    here and there, fibrous, pale on the ridge tops, brown patches, a little grey lichen. `scale` shrinks every feature."""
    cm = px / scale
    warp = ((tr.fbm(r, h, w, (6 * cm, 30 * cm), 3) - 0.5) * 4.0 * cm,
            (tr.fbm(r, h, w, (8 * cm, 26 * cm), 3) - 0.5) * 12.0 * cm)
    edge, plate, _, _ = tr.cells(r, h, w, 9.5 * cm, 7.0, warp)
    edge2, plate2, _, _ = tr.cells(r, h, w, 16 * cm, 6.0, warp)
    xedge, block, _, _ = tr.cells(r, h, w, 20 * cm, 1.8, warp)
    n = plate.max() + 1
    shade = r.random(n)[plate]
    tilt = (r.random(n) * 2.0 - 1.0)[plate]
    shade2 = r.random(plate2.max() + 1)[plate2]
    bshade = r.random(block.max() + 1)[block]
    wobble = tr.fbm(r, h, w, (1.0 * cm, 6 * cm), 3)
    fork = tr.smoothstep(0.5, 0.62, tr.fbm(r, h, w, (10 * cm, 36 * cm), 3))
    fw = 1.0 + 1.0 * deep
    furrow = 1.0 - tr.smoothstep(0.0, (0.55 + 0.75 * wobble) * fw * cm, edge)
    furrow = np.maximum(furrow, (1.0 - tr.smoothstep(0.0, (0.4 + 0.6 * wobble) * fw * cm, edge2)) * fork)
    gate = tr.smoothstep(0.45, 0.6, tr.fbm(r, h, w, (6 * cm, 16 * cm), 3))
    cross = (1.0 - tr.smoothstep(0.0, (0.25 + 0.35 * wobble) * cm, xedge)) * (0.2 + 0.8 * gate) * 0.7
    shoulder = 1.0 - tr.smoothstep(0.0, 1.6 * cm, edge)
    body = tr.smoothstep(0.0, 1.0 * cm, edge)
    fibre = tr.fbm(r, h, w, (0.12 * cm, 2.6 * cm), 3)
    streak = tr.fbm(r, h, w, (0.3 * cm, 6.0 * cm), 3)
    grit = tr.fbm(r, h, w, (0.18 * cm, 0.18 * cm), 3)
    mottle = tr.fbm(r, h, w, (2.0 * cm, 7.0 * cm), 4)
    coarse = tr.fbm(r, h, w, (14 * cm, 34 * cm), 3)
    flat_top = tr.smoothstep(0.0, 1.3 * cm, edge)  # the ridge top is flat: it rises quickly and stays
    height = (2.4 * flat_top + 0.35 * tilt * shoulder + 0.8 * fibre + 0.5 * streak + 0.4 * grit + 0.3 * mottle
              - (3.6 + 1.2 * deep) * furrow - 1.8 * cross * body + 0.3 * shade)
    col = tr.mix((0.2, 0.19, 0.17), (0.56, 0.54, 0.5),
                 0.3 * shade + 0.2 * mottle + 0.1 * streak + 0.05 * fibre + 0.08 * grit + 0.08 * shade2 + 0.08 * bshade)
    pale = tr.smoothstep(0.5, 0.8, coarse + (mottle - 0.5) * 0.4) * flat_top
    col = tr.mix(col, (0.68, 0.65, 0.59), pale * 0.35)
    brown = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (16 * cm, 30 * cm), 3))
    col = tr.mix(col, col * np.array((1.06, 0.98, 0.88)), brown[..., None] * 0.25)
    col = tr.mix(col, (0.3, 0.19, 0.1), np.clip(shoulder - 0.15, 0.0, 1.0) * (1.0 - furrow) * 0.14 * (0.5 + mottle))
    col = tr.mix(col, (0.035, 0.03, 0.026), np.clip(furrow * 1.25, 0.0, 1.0))
    col = tr.mix(col, (0.07, 0.057, 0.047), np.clip(cross * body * 1.2, 0.0, 1.0) * 0.8)
    lichen = (tr.smoothstep(0.76, 0.9, tr.fbm(r, h, w, (1.7 * cm, 1.7 * cm), 4))
              * tr.smoothstep(0.55, 0.78, tr.fbm(r, h, w, (18 * cm, 26 * cm), 3)) * body)
    col = tr.mix(col, tr.mix((0.5, 0.54, 0.43), (0.66, 0.68, 0.57), grit), lichen * 0.45)
    height += 0.3 * lichen
    col = col * (0.86 + 0.14 * np.clip(flat_top, 0.0, 1.0))[..., None]
    col = col * (0.93 + 0.14 * fibre)[..., None]
    rough = 0.9 + 0.05 * (grit - 0.5) - 0.04 * lichen
    occ = tr.cavity(height, 5.0 * RELIEF / scale, 0.34)
    col = col * (0.64 + 0.36 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def limb_bark(r):
    """CottonwoodBarkLimb: younger bark: smooth greyer-green with a pale bloom, long shallow furrows that fork, raised
    lenticel dashes, a little lichen; the furrows get deeper in places (the bark thickening)."""
    cm = LPX
    col, height, rough, occ = cotton_bark(r, LH, LW, LPX, scale=1.7, deep=0.0)
    col, _ = tr.match_mean(col, LIMB_MEAN)
    smooth = 0.5 + 0.5 * tr.smoothstep(0.3, 0.7, tr.fbm(r, LH, LW, (30 * cm, 60 * cm), 3))  # 0.5 = furrowed, 1 = smooth
    green = tr.smoothstep(0.45, 0.8, tr.fbm(r, LH, LW, (12 * cm, 24 * cm), 3))
    col = tr.mix(col, col * np.array((0.92, 1.04, 0.9)), green[..., None] * 0.5)
    lent = np.zeros((LH, LW))
    for _ in range(int((LW / cm) * (LH / cm) * 0.22)):
        tr.stamp_lens(lent, r.uniform(0, LW), r.uniform(0, LH), r.uniform(0.5, 1.6) * cm,
                      max(1.3, r.uniform(0.12, 0.28) * cm), r.uniform(0.5, 1.0), ends=1.0)
    col = tr.mix(col, (0.36, 0.34, 0.27), lent * 0.55)
    height = height * smooth + 0.8 * lent
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 4.0 * LPX / 13.0, 0.25)


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: smooth olive-tan to grey, with short pale lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.26, 0.21, 0.13), (0.5, 0.43, 0.27), tone)
    bloom = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (2.5 * cm, 3.0 * cm), 4))
    col = tr.mix(col, (0.58, 0.55, 0.45), bloom * 0.35)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.8)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.32) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=1.0)
    col = tr.mix(col, (0.72, 0.66, 0.5), lent * 0.7)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.8
    return np.clip(col, 0.0, 1.0), height, 0.55 + 0.1 * tone, tr.cavity(height, 3.0, 0.2)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


def make_bark():
    """Writes CottonwoodBark_*, CottonwoodBarkLimb_* and CottonwoodBarkTwig_*."""
    r = np.random.default_rng(17)

    def save(name, col, height, rough, occ, relief, blur=0.6):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, blur), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = cotton_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("CottonwoodBark", col, height, rough, occ, 3.4 * RELIEF)
    save("CottonwoodBarkLimb", *limb_bark(r), 1.6 * LPX / 13.0)
    save("CottonwoodBarkTwig", *twig_bark(r), 1.0)


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top: three big sprays (640 x 768 px, about 1.0 x 1.2 m: 640 px per m, an 8 cm leaf is 51 px long) of
# stout twigs hung with long-stalked deltoid leaves; under them two cluster cells (1024 square, 3 m) for LOD2 and one
# leaf (128 square) for the seedling, past the decal strip (u under .375, v under .0625).

SPRAYS = ("Spray0", "Spray1", "Spray2")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"
LEAF_LEN = (0.072, 0.095)


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 640 * i, 1280, 640, 768, (1.0, 1.2))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1024, (3.0, 3.0))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.16, 0.16), pad=8)
    return atlas


def leaf_profile(s):
    """Half-width of a cottonwood blade from base to tip: a broad, nearly flat (truncate) base, widest just above it,
    then a straight-sided taper to a long point (deltoid)."""
    return float(np.interp(s, (0.0, 0.03, 0.12, 0.25, 0.45, 0.65, 0.82, 0.93, 1.0),
                           (0.42, 0.72, 1.0, 0.96, 0.74, 0.5, 0.28, 0.1, 0.0)))


def leaf_materials(vein=0.3, shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): glossy yellow-green leaf with paler midrib
    and veins, paler greyer green beneath; twig; flat petiole."""
    mat, g = tr.tk.new_material("CottonLeafSrc")
    attr = g.node("ShaderNodeAttribute", attribute_name="leaf")
    x, s, rv = g.separate(attr.outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.15, 0.27, 0.04), (0.2, 0.32, 0.05))
    base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.1, 0.18, 0.03))
    hi = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=3.0), 0.5, 0.82), 0.5)
    col = g.mix(hi, base, (0.28, 0.4, 0.06))
    mid = g.ramp(ax, 0.05, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.5)), 6.5))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.44, 0.5),
                 g.math("MULTIPLY", g.ramp(ax, 0.03, 0.12), g.ramp(ax, 0.95, 0.6)))
    veins = g.math("MAXIMUM", mid, lat)
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.3, 0.42, 0.1))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.24, 0.32, 0.14), (0.31, 0.38, 0.19)),
                  (0.38, 0.44, 0.24))
    col = g.mix(back, col, under)
    rough = g.mixf(back, 0.36, 0.62)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.22 + vein - 0.35, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("CottonTwigSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=3.0), 0.3, 0.7), (0.1, 0.07, 0.035), (0.22, 0.17, 0.08))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("CottonPetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    col = g.mix(g.ramp(t, 0.0, 0.8), (0.16, 0.14, 0.05), (0.24, 0.3, 0.08))
    tr.tk.finish(mat, g, col, 0.0, 0.45)
    pet = tr.signals(mat, col, 0.45)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, tan, side, size):
    """A leaf on its long flat petiole at p on a twig heading `tan`, to the twig's `side`: the petiole leaves out and
    down, the blade hangs from its end turned any way; one in six shows its paler back."""
    lat = Vector((-tan.y, tan.x, 0.0))
    lat = (lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))) * side
    pd = (lat * 0.75 + tan * 0.3 + Vector((0.0, -0.4, rnd.uniform(-0.3, 0.3)))).normalized()
    pl = size * rnd.uniform(0.45, 0.7)
    b = p + pd * pl
    tr.twig(m, [p, p + pd * (pl * 0.5) + Vector((0.0, 0.003, 0.0)), b], [0.0012, 0.0010, 0.0009], "petiole", 4)
    dd = (pd * 0.35 + tan * 0.1 + Vector((rnd.gauss(0, 0.35), -0.8, rnd.gauss(0, 0.25)))).normalized()
    nl = Vector((rnd.gauss(0.0, 0.4), 0.3 + rnd.gauss(0.0, 0.25), 1.0))
    if rnd.random() < 0.17:
        nl = Vector((nl.x, nl.y * 0.5, -1.0))
    tr.blade(m, b, dd, nl, size, size * rnd.uniform(0.9, 1.05), leaf_profile, "leaf", teeth=13, tooth=0.045, rows=16,
             fold=rnd.uniform(0.04, 0.14), arch=rnd.uniform(0.04, 0.16), twist=rnd.uniform(-22.0, 22.0),
             rnd_value=rnd.random())


def leafy_twig(m, rnd, start, direction, length, bend, down, radius, first=0.05, gap=(0.07, 0.1), side_twigs=0):
    """A stout twig from `start` with alternate long-stalked leaves, `side_twigs` leafy side twigs, a leaf at its tip."""
    pts = tr.bend_path(start, direction, length, bend, steps=14, down=down)
    tr.twig(m, pts, [radius * (1.0 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 5)
    tw = tr.Branch(pts, [radius] * len(pts))
    sides = set(rnd.sample(range(2, 12), side_twigs)) if side_twigs else set()
    f, i, side = first, 0, rnd.choice((-1, 1))
    while f < 0.94:
        p, tan, _ = tw.at(f)
        if i in sides:
            d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(28.0, 42.0))
            d.z += rnd.uniform(-0.2, 0.2)
            leafy_twig(m, rnd, p, d, length * rnd.uniform(0.3, 0.45), rnd.uniform(0.8, 1.2), (0.0, -1.0, 0.0),
                       radius * 0.6, first=0.15, gap=(0.2, 0.28))
        else:
            add_leaf(m, rnd, p, tan, side, rnd.uniform(*LEAF_LEN) * (1.0 - 0.15 * f))
        f += rnd.uniform(*gap)
        i += 1
        side = -side
    p, tan, _ = tw.at(1.0)
    add_leaf(m, rnd, pts[-1], tan, side, rnd.uniform(*LEAF_LEN) * 0.8)


def make_atlas(atlas, render=True):
    """Builds the sprays, clusters and the single leaf, fits their cells; with `render`, renders them into the atlas,
    grades the leaves and saves it (without, the cells are only measured: the geometry is the same every run)."""
    mats = leaf_materials()
    rnd = random.Random(23)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1)[i]
        direction = Vector((side * rnd.uniform(0.2, 0.45), -1.0, rnd.uniform(-0.15, 0.15)))
        down = Vector((-side * (0.15, 0.5, 0.3)[i], -1.0, 0.0))
        leafy_twig(m, rnd, Vector(), direction, rnd.uniform(0.78, 0.9), rnd.uniform(0.4, 0.9), down, 0.0034,
                   first=0.05, gap=(0.05, 0.07), side_twigs=(5, 6, 5)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        m = tr.Mesh()
        side = (1, -1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.5, -1.0, 0.1)), rnd.uniform(1.6, 1.9), 0.4, steps=10,
                              down=(0.0, -1.0, 0.0))]
        main_stem = tr.Branch(stems[0], [0.008] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.68, -side)):
            p, tan, _ = main_stem.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.8, 1.05), 0.5, steps=8, down=(0.0, -1.0, 0.0)))
        for k, st in enumerate(stems):
            r0 = 0.011 if k == 0 else 0.007
            tr.twig(m, st, [r0 * (1.0 - 0.6 * i / (len(st) - 1)) for i in range(len(st))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        for k, st in enumerate(stems):
            br = tr.Branch(st, [0.006] * len(st))
            count = 7 if k == 0 else 4
            for j in range(count):
                f = 0.1 + 0.9 * (j + rnd.uniform(0.2, 0.8)) / count
                p, tan, _ = br.at(f)
                c = sprays[rnd.randrange(len(sprays))].copy()
                tr.tk.link(c)
                spin = (j % 2 * 2 - 1) * rnd.uniform(10.0, 70.0)
                rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-50, 50)), 4, "Y")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 4, "X"))
                c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.6, 0.85), 4)
                objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs, samples=24)
    # One leaf on its stalk, hanging from the cell's top
    m = tr.Mesh()
    stalk = Vector((0.003, -0.03, 0.0))
    tr.twig(m, [Vector(), Vector((0.0015, -0.015, 0.0005)), stalk], [0.0012, 0.001, 0.0009], "petiole", 4)
    tr.blade(m, stalk, Vector((0.1, -1.0, 0.0)), Vector((0.0, 0.15, 1.0)), 0.09, 0.088, leaf_profile, "leaf",
             teeth=13, tooth=0.045, fold=0.1, arch=0.1, twist=8.0, rows=16, rnd_value=0.55)
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "CottonwoodLeaves")
    atlas.preview(os.path.join(PREVIEWS, "cottonwood_atlas.png"))
    for c in atlas.cells.values():
        print("[cottonwood] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("CottonwoodLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- growing: a tree with an optional huge fork

def grow_cw(spec, seed, name, fork=None):
    """treekit.grow, plus `fork` (a Level): extra limbs off each trunk (a huge low fork)."""
    rnd = random.Random(seed)
    tree = tr.Tree(name, spec, seed)
    for t in spec.trunks:
        tree.trunks.append(tr.grow_trunk(rnd, t))
        if spec.ground_v is not None:
            tree.trunks[-1].v0 = spec.ground_v
    tree.branches = list(tree.trunks)
    current = list(tree.trunks)
    for li, lv in enumerate(spec.levels):
        nxt = []
        for br in current:
            if lv.on is None or lv.on(br):
                nxt += tr.grow_children(rnd, tree, br, lv, li + 1)
                if li == 0 and fork is not None:
                    nxt += tr.grow_children(rnd, tree, br, fork, 1)
        tree.branches += nxt
        current = nxt
    if spec.stubs is not None:
        for t in tree.trunks:
            stubs = tr.grow_children(rnd, tree, t, spec.stubs, 1)
            for s in stubs:
                s.tags.add("stub")
            tree.branches += stubs
    for br in tree.branches:
        for lod in range(3):
            ok = br.spec.sides[lod] >= 3 and br.length >= br.spec.min_len[lod]
            br.keep[lod] = ok and (br.parent is None or br.parent.keep[lod])
    if spec.foliage is not None:
        tree.cards = tr.place_cards(rnd, tree, spec.foliage)
    return tree


# ---------------------------------------------------------------- the trees

def limb_env(t):
    """The big limbs' length over the crown span: long in the lower middle, shorter toward the top (a tall vase)."""
    return 1.0 - 0.4 * t


def secondary_env(t):
    return 1.0 - 0.4 * t


def cottonwood(trunks, limbs=10, reach=1.0, crown=0.32, favor=None, inner=0.0, budget=8000, twig_density=1.3,
               card_scale=(1.3, 1.7), angle=(54.0, 26.0), limb_length=(9.0, 14.0), grav=0.14, droop=0.03,
               secondaries=0.8, spacing=0.1, cluster_spacing=1.6, split=0.1, stubs=(3, 5), fork=0, young=False):
    """A cottonwood's TreeSpec. Each trunk (tr.Trunk) stands bare from the ground to `crown` of its height (a few dead
    stubs), then gives out `limbs` huge limbs that climb at `angle` (off the trunk, at the base and tip of the span),
    arch up (`grav`) and fork now and then (`split`); level 2 are big secondary limbs (`secondaries` per metre) that
    fork the crown out, level 3 the leafy twigs. `fork` adds that many near-equal huge limbs low on the trunk."""
    prim = tr.Level(count=limbs, span=(crown, 0.97), length=(limb_length[0] * reach, limb_length[1] * reach),
                    shape=limb_env, angle=angle[0], angle_tip=angle[1], angle_vary=8.0, radius=0.8,
                    radius_length=0.3, radius_max=0.5, tip_radius=0.04, taper=0.65, step=0.5, gravitropism=grav,
                    droop=droop, wander=0.2, outward=0.12, split=split, split_angle=30.0, favor=favor, inner=inner,
                    floor=0.6, sides=(7, 5, 4), seg=(3.0, 4.0, 5.0), min_len=(0.0, 0.0, 0.0))
    sec = tr.Level(per_meter=secondaries, span=(0.12, 0.97), length=(4.0 * reach ** 0.5, 7.5 * reach ** 0.5),
                   shape=secondary_env, angle=50.0, angle_tip=36.0, angle_vary=10.0, planar=0.1, outward=0.25,
                   radius=0.55, radius_length=0.45, radius_max=0.2, tip_radius=0.012, taper=0.8, step=0.4,
                   gravitropism=0.1, droop=0.08, wander=0.3, split=0.06, floor=1.0, sides=(4, 3, 3),
                   seg=(4.5, 5.0, 7.0), min_len=(0.0, 2.0, 4.0))
    leafy = tr.Level(per_meter=twig_density, span=(0.12, 0.98), length=(1.0, 2.2), shape="tapered", angle=60.0,
                     angle_tip=44.0, angle_vary=12.0, planar=0.3, outward=0.3, radius=0.42, radius_length=0.5,
                     radius_max=0.022, tip_radius=0.005, taper=1.0, step=0.4, gravitropism=0.08, droop=0.3,
                     wander=0.45, floor=1.0, sides=(3, 3, 0), seg=(1.6, 3.0, 9.0), min_len=(0.0, 1.5, 99.0))
    dead = tr.Level(count=stubs, span=(0.1, crown + 0.08), length=(0.3, 1.0), angle=72.0, angle_vary=10.0,
                    radius=0.22, radius_length=0.0, radius_max=0.12, tip_radius=0.05, broken=True, step=0.1,
                    droop=0.0, gravitropism=0.2, wander=0.2, floor=0.8, sides=(9, 6, 0), seg=(0.5, 1.2, 1.0),
                    min_length=0.2)
    fork_lv = None
    if fork:
        fork_lv = tr.Level(count=fork, span=(0.3, 0.36), length=(13.0 * reach, 17.0 * reach), shape="flat",
                           angle=34.0, angle_vary=5.0, radius=0.92, radius_length=0.1, radius_max=0.6,
                           tip_radius=0.05, taper=0.6, step=0.5, gravitropism=0.12, droop=0.03, wander=0.15,
                           outward=0.2, split=0.06, split_angle=30.0, floor=0.6, sides=(9, 6, 4),
                           seg=(2.0, 3.0, 4.0), min_len=(0.0, 0.0, 0.0), favor=favor)
    spec = tr.TreeSpec(
        trunks=trunks, levels=[prim, sec], stubs=dead if stubs else None, budget=budget, bark_budget=3500,
        foliage=tr.Foliage(levels={2: (0.12, 1.0)}, trunk_top=None, spacing=spacing, cells=SPRAYS,
                           scale=card_scale, hang=0.35, spread=0.4, out=0.5, face=0.5, up=0.45, roll=40.0, bend=0),
        cluster=tr.Foliage(levels={2: (0.35, 1.0)}, trunk_top=None, spacing=cluster_spacing, cells=CLUSTERS,
                           scale=(0.85, 1.15), hang=0.3, spread=0.3, out=0.5, face=0.5, up=0.4, roll=25.0, bend=20.0),
        bark_key=bark_key, bark_uv=UV, ground_v=0.1, lod_share=(0.45, 0.2))
    spec.fork = fork_lv
    return spec


def trunk(**kw):
    base = dict(flare=0.5, flare_height=0.9, lobes=(6, 0.14), taper=0.75, tip_radius=0.1, wander=0.1,
                sides=(16, 10, 7), seg=(0.8, 1.5, 2.6), rings=((0.0, 0.2, 0.5, 0.9, 1.5, 2.2), (0.0, 0.6), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeCottonwoodSeed in game): a stout little stem about 0.8 m tall
    with a couple of short side shoots, hung with single deltoid leaves (the atlas's Leaf cell), all twig bark."""
    shoots = tr.Level(count=(2, 4), span=(0.35, 0.85), length=(0.08, 0.2), shape="tapered", angle=55.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0009, step=0.03,
                      gravitropism=0.3, droop=0.25, wander=0.4, floor=0.02, sides=(4, 3, 0),
                      seg=(0.05, 0.1, 9.0), min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.8, radius=0.0065, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0016,
                         lean=(0.04, -0.03), bow=0.3, wander=0.03, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.8, 1.1), hang=0.2, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.1, cells=(LEAF,), scale=(0.9, 1.2),
                           hang=0.2, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        bark_key=lambda br, s, r, z: "twig", bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # Mature: about 28 m, a vase 16 m across
    ("Cottonwood01", 3, lambda: cottonwood([trunk(height=21.0, radius=0.65, lean=(0.5, 0.3), bow=0.1, taper=0.75)], limbs=12, reach=1.05)),
    # Big and leaning: about 24 m, a huge low fork
    ("Cottonwood02", 11, lambda: cottonwood([trunk(height=18.0, radius=0.7, lean=(2.4, 0.9), bow=0.4, wander=0.14, taper=0.75)],
                                            limbs=6, crown=0.42, fork=2, favor=((1.0, 0.35), 0.25), reach=0.9,
                                            budget=8000, limb_length=(8.0, 12.0))),
    # Twin trunk: two stout trunks from one base, about 26 m
    ("Cottonwood03", 23, lambda: cottonwood([trunk(height=19.5, radius=0.5, base=(0.4, 0.0), lean=(1.6, 0.3), bow=0.3,
                                                   sides=(14, 9, 7)),
                                             trunk(height=18.0, radius=0.48, base=(-0.4, 0.1), lean=(-1.5, -0.4),
                                                   bow=0.3, sides=(14, 9, 7))],
                                            limbs=6, crown=0.4, inner=0.4, reach=0.92, budget=8000)),
    # Young: about 13 m, smoother, a narrower crown low to the ground
    ("Cottonwood04", 41, lambda: cottonwood([trunk(height=10.5, radius=0.2, lean=(-0.3, 0.4), bow=0.2, flare=0.35,
                                                   lobes=(0, 0.0), tip_radius=0.04, taper=0.9, sides=(12, 8, 6),
                                                   tags=("young",))],
                                            limbs=9, crown=0.3, reach=0.45, budget=6000, twig_density=1.5,
                                            card_scale=(0.85, 1.1), spacing=0.38, cluster_spacing=1.1,
                                            limb_length=(6.0, 9.0), secondaries=1.7, angle=(52.0, 28.0),
                                            stubs=(1, 2), split=0.04)),
    ("CottonwoodSapling", 61, sapling),
]


# ---------------------------------------------------------------- trunks.txt: the trunk and the low thick limbs

def write_trunks_ext(path, name, tree, limb_height=4.5, min_r=0.12, step=0.5):
    """The trunk's chain (the first line) to 80 % of its length, and a line for each limb's stretch below
    `limb_height` m that is still thicker than `min_r`, so a player can't walk into a big low limb (a vanilla tree's
    limbs can be clipped into, a trunk never)."""
    tr.write_trunks(path, name, tree, top=0.8, step=step)
    lines = [ln.rstrip("\n") for ln in open(path, encoding="utf-8") if ln.strip()]
    for br in tree.branches:
        if br.level != 1 or "stub" in br.tags:
            continue
        pts = []
        s = 0.0
        while s <= 1.0001:
            p, _, r = br.at(min(s, 1.0))
            if p.z > limb_height or r < min_r:
                break
            pts.append("%.3f %.3f %.3f %.4f" % (p.x, p.y, p.z, r))
            s += step / max(br.length, 1e-3)
        if len(pts) >= 2:
            lines.append(name + " " + " ".join(pts))
    lines.sort(key=lambda ln: ln.split()[0])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- previews of a big tree

def big_previews(name, obj, size, figure, samples=40):
    """Wide views for a big crown: the whole tree from 62 m, from 105 m, from 14 m (under it), and a side view."""
    low = name.lower()
    saved = tr._only([obj])
    tr.place(figure, -2.4, -2.0)
    h = size[0]
    for tag, loc, tgt, lens, res in (
            ("w", (4.0, -70.0, h * 0.42), (0.0, 0.0, h * 0.46), 35, (1400, 900)),
            ("far", (-20.0, -105.0, 4.0), (0.0, 0.0, h * 0.4), 35, (1400, 900)),
            ("under", (-7.0, -13.0, 1.7), (0.0, 0.0, 9.0), 24, (1400, 900)),
            ("side", (70.0, 12.0, h * 0.42), (0.0, 0.0, h * 0.46), 35, (1400, 900))):
        tr._shot(low + "_" + tag, loc, tgt, os.path.join(PREVIEWS, "%s_%s.png" % (low, tag)), lens=lens, res=res,
                 samples=samples)
    tr._restore(saved)


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """CottonwoodSeed_Icon.png (160 x 160, in Trees/Cottonwood; gen_nature.py copies it into the mod's item icons): a
    seed tuft of white cotton fluff: a string of ripe capsules split open on a catkin stalk, each bursting into a
    cloud of long silky hairs, lying across a cottonwood leaf, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.6, shade=0.3)
    mat, g = tr.tk.new_material("CottonFluffSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.86, 0.85, 0.81), (1.0, 1.0, 0.97))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.0, 0.35), 0.5), col, (0.5, 0.49, 0.45))
    tr.tk.finish(mat, g, col, 0.0, 0.95)
    mats["fluff"] = mat
    mat, g = tr.tk.new_material("CottonCapsuleSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.22, 0.17, 0.08), (0.36, 0.3, 0.14))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    mats["capsule"] = mat

    m = tr.Mesh()
    stalk = Vector((0.034, 0.004, -0.034))
    tr.twig(m, [Vector((0.042, 0.004, -0.046)), stalk], [0.001, 0.0009], "petiole", 5)
    tr.blade(m, stalk, Vector((-0.5, 0.0, 0.85)), Vector((0.35, -1.0, 0.1)), 0.08, 0.078, leaf_profile, "leaf",
             teeth=13, tooth=0.045, fold=0.22, arch=0.2, twist=-18.0, rows=16, rnd_value=0.45)
    # The catkin: a drooping stalk from the top right to the lower left, with split capsules and clouds of hairs
    top, tip = Vector((0.036, -0.016, 0.038)), Vector((-0.016, -0.022, -0.02))
    axis = (tip - top).normalized()
    pts = [top.lerp(tip, i / 8) + Vector((0.0, 0.0, 0.0035 * math.sin(math.pi * i / 8))) for i in range(9)]
    tr.twig(m, pts, [0.0012 * (1.0 - 0.3 * i / 8) for i in range(9)], "capsule", 6)
    rnd = random.Random(11)
    _, u, v = tr.basis(axis)
    for i in range(7):
        f = 0.14 + 0.8 * (i + rnd.uniform(-0.2, 0.2)) / 6
        c = top.lerp(tip, f) + Vector((0.0, 0.0, 0.0035 * math.sin(math.pi * f)))
        a = rnd.uniform(0, TAU)
        out = (u * math.cos(a) + v * math.sin(a))
        base = c + out * 0.0014
        tr.blade(m, base, (out * 0.6 + axis * 0.3).normalized(), out, 0.0055, 0.003,
                 lambda q: float(np.interp(q, (0, 0.3, 0.7, 1.0), (0.3, 1.0, 0.8, 0.0))), "capsule", rows=5,
                 rnd_value=rnd.random(), fold=0.3)
        for _ in range(150):
            d = (out * rnd.uniform(0.3, 1.0) + u * rnd.gauss(0, 0.55) + v * rnd.gauss(0, 0.55)
                 + axis * rnd.gauss(0, 0.5) + Vector((0, -0.25, 0.1))).normalized()
            ln = rnd.uniform(0.014, 0.034) * (0.65 + 0.35 * math.sin(math.pi * f))
            hair = tr.bend_path(base, d, ln, rnd.uniform(0.3, 1.2), steps=4,
                                down=(rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)))
            tr.twig(m, hair, [0.0006, 0.00048, 0.00036, 0.00026, 0.00016], "fluff", 3)
    obj = m.build("CottonwoodSeedIcon", mats)
    obj.scale = (6.8, 6.8, 6.8)
    obj.location = (-0.05, 0.0, 0.31)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.66)
    tr.tk.icon(cam, os.path.join(FOLDER, "CottonwoodSeed_Icon.png"), hide=())
    print("[cottonwood] icon written")


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
    mats = {"bark": tr.textured("CottonwoodBark", paths("CottonwoodBark")),
            "limb": tr.textured("CottonwoodBarkLimb", paths("CottonwoodBarkLimb")),
            "twig": tr.textured("CottonwoodBarkTwig", paths("CottonwoodBarkTwig")),
            "leaves": tr.textured("CottonwoodLeaves", paths("CottonwoodLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    for name, seed, make in VARIANTS:
        if ONLY and name not in ONLY:
            continue
        spec = make()
        if STEPS == "skeleton" and spec.foliage is not None:
            spec.foliage = None
            spec.cluster = None
        tree = grow_cw(spec, seed, name, getattr(spec, "fork", None))
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        if name.endswith("Sapling"):
            tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        else:
            write_trunks_ext(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[cottonwood] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        if name.endswith("Sapling"):
            tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
        else:
            big_previews(name, lods[0], size, figure)
    big = [b for b in built if not b[0].endswith("Sapling")]
    if big:
        name, tree, lods, size = big[0]
        tr.preview_bark("cottonwood01", lods[0], PREVIEWS, figure)
        tr.preview_lods("cottonwood01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
        tr.preview_grove("cottonwood", [b[2][0] for b in big], PREVIEWS, figure,
                         spots=[(-24.0, 8.0), (0.0, 30.0), (24.0, 4.0), (0.0, -4.0)], distance=90.0)
    if STEPS == "all":
        make_icon()
    print("[cottonwood] done")


main()
