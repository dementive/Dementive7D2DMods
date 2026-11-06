"""Weeping willow (Salix babylonica) in summer, on treekit.py (birch.py is the worked example; TREES.md has the rules).

A short stout trunk, often leaning, with deep interlacing grey-brown ridges, forking at 3 to 5 m into a few big arching
limbs that make a wide dome; from every limb hang hundreds of long, thin, whip-like pale yellow-green twigs, 3 to 6 m,
in curtains that almost reach the ground. Leaves 8 to 12 cm long and about 1 cm wide, lance-shaped, finely toothed,
yellow-green above and silvery beneath, hanging from the twigs.

The curtain is the point, so the leaves are not sprays on twigs but tall hanging STRAND cards: each card is a cell of
the leaf atlas 0.65 m wide and 1.85 m (Short) or 3.7 m (Long) tall showing two or three whole hanging twigs with every
leaf on them, and a card hangs straight down from its limb or branch, its length cut to the clearance below it, so the
curtain reaches the ground without going into it, and shortened round the trunk so no strand clips into a trunk. The
Unity builder sways a card that tall from its top like a rope (NatureTreeBuilder, "hanging strands"). The strand
cards are placed here (`strands`), through a place_cards and card_quads of this module patched into treekit.

    blender -b --factory-startup --python trees/willow.py -- <unity trees folder> <preview folder> [step]

with absolute paths `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`.
Steps as birch.py's: `all`, `textures` (bark and leaves, then stop), `bark`, `bark-textures`, `atlas`, `trees`, `icon`;
also `skeleton` (the trees without leaves, previews only). It writes Trees/Willow/ (the bark and leaf textures,
Willow01..04 and the seedling WillowSapling with their impostors, WillowSeed_Icon.png), the Willow lines of
Trees/trees.txt and trunks.txt and the previews. Built at its size in game (the Unity builder scales only the birch).
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
FOLDER = os.path.join(TREES, "Willow")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
UP, DOWN = tr.UP, tr.DOWN

# ---------------------------------------------------------------- bark textures
#
# WillowBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (2.5 m on a 40 cm trunk),
# drawn at its size on that trunk (about 16 px per cm): long narrow ridges 4 to 7 cm wide and 30 to 60 cm tall that
# fork, rejoin and cross each other (the interlacing), between deep dark furrows. WillowBarkTwig: 512 x 1024, the
# olive-yellow smooth bark of the hanging twigs and thin limbs (under 1.2 cm radius), once round them.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)  # radii per repeat up a tube: 2 pi
R_DESIGN = 40.0  # cm: the trunk the bark is drawn for (Willow01's, 1 m up)
PX = WRAPS * W / (TAU * R_DESIGN)  # pixels per cm round and up that trunk
RELIEF = PX / 13.0  # birch's first bark's 13 px per cm: slopes and cavities keep their size in cm
TWIST = 0.33
BARK_MEAN = (96, 86, 76)
LEAF_MEAN = (88, 104, 60)
TWIG_R = 0.012
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def willow_bark(r, h=H, w=W, px=PX):
    """Old willow bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm:
    narrow rounded ridges (stringy, fibrous along their length) between deep dark furrows that wander, fork and
    rejoin, so the ridges interlace; here and there a ridge cross-cracked into blocks, grey lichen crusts, pale
    weathered ridge tops and orange-brown inner bark deep in the furrows."""
    cm = px
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    # The furrows wander: a big slow warp across, a smaller one up, so the ridges snake and cross
    warp = ((tr.fbm(r, h, w, (6 * cm, 40 * cm), 3) - 0.5) * 8.0 * cm,
            (tr.fbm(r, h, w, (8 * cm, 30 * cm), 3) - 0.5) * 14.0 * cm)
    edge, plate, _, _ = tr.cells(r, h, w, 5.5 * cm, 6.0, warp)
    # A second, coarser network used only here and there: ridges that fork
    edge2, plate2, _, _ = tr.cells(r, h, w, 9 * cm, 5.0, warp)
    split, piece, _, _ = tr.cells(r, h, w, 3.0 * cm, 2.4, warp)
    del X, Y
    n = plate.max() + 1
    shade = r.random(n)[plate]
    tilt = (r.random(n) * 2.0 - 1.0)[plate]
    shade2 = r.random(plate2.max() + 1)[plate2]
    wobble = tr.fbm(r, h, w, (1.0 * cm, 5 * cm), 3)
    fork = tr.smoothstep(0.52, 0.64, tr.fbm(r, h, w, (10 * cm, 30 * cm), 3))
    furrow = 1.0 - tr.smoothstep(0.0, (0.35 + 0.55 * wobble) * cm, edge)
    furrow = np.maximum(furrow, (1.0 - tr.smoothstep(0.0, (0.25 + 0.4 * wobble) * cm, edge2)) * fork)
    shoulder = 1.0 - tr.smoothstep(0.0, 2.0 * cm, edge)
    crack = ((1.0 - tr.smoothstep(0.0, (0.08 + 0.12 * wobble) * cm, split))
             * tr.smoothstep(0.55, 0.7, tr.fbm(r, h, w, (3 * cm, 8 * cm), 3)) * 0.8)
    body = tr.smoothstep(0.0, 1.4 * cm, edge)
    # Stringy fibres along the ridges, fine up to the pixel, and a broader streak, grit and mottle
    fibre = tr.fbm(r, h, w, (0.12 * cm, 2.0 * cm), 3)
    streak = tr.fbm(r, h, w, (0.3 * cm, 4.0 * cm), 3)
    grit = tr.fbm(r, h, w, (0.18 * cm, 0.18 * cm), 3)
    mottle = tr.fbm(r, h, w, (2.0 * cm, 5.0 * cm), 4)
    coarse = tr.fbm(r, h, w, (12 * cm, 30 * cm), 3)
    # Rounded ridge tops: highest along the middle, a ridge's tilt lifting one side
    round_top = tr.smoothstep(0.0, 2.4 * cm, edge)
    height = (2.2 * round_top + 0.45 * tilt * shoulder + 0.7 * fibre + 0.4 * streak + 0.35 * grit + 0.3 * mottle
              - 3.4 * furrow - 1.2 * crack)
    col = tr.mix((0.2, 0.17, 0.145), (0.5, 0.45, 0.395),
                 0.28 * shade + 0.2 * mottle + 0.2 * streak + 0.12 * fibre + 0.1 * grit + 0.1 * shade2)
    # Greyer and paler ridge tops where the weather got at them, browner in patches
    pale = tr.smoothstep(0.5, 0.8, coarse + (mottle - 0.5) * 0.4) * round_top
    col = tr.mix(col, (0.58, 0.55, 0.51), pale * 0.4)
    brown = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (14 * cm, 24 * cm), 3))
    col = tr.mix(col, col * np.array((1.1, 0.96, 0.82)), brown[..., None] * 0.8)
    # Orange-brown inner bark on the furrow walls, black deep in them
    walls = np.clip(furrow * (1.0 - tr.smoothstep(0.0, 0.5 * cm, edge)) * 0.0 + shoulder * furrow, 0.0, 1.0)
    col = tr.mix(col, (0.29, 0.17, 0.095), np.clip(shoulder - 0.15, 0.0, 1.0) * (1.0 - furrow) * 0.18 * (0.5 + mottle))
    col = tr.mix(col, (0.045, 0.036, 0.03), np.clip(furrow * 1.15, 0.0, 1.0))
    col = tr.mix(col, (0.1, 0.07, 0.05), np.clip(crack, 0.0, 1.0) * 0.9)
    lichen = (tr.smoothstep(0.74, 0.88, tr.fbm(r, h, w, (1.6 * cm, 1.6 * cm), 4))
              * tr.smoothstep(0.5, 0.75, tr.fbm(r, h, w, (16 * cm, 22 * cm), 3)) * body)
    col = tr.mix(col, tr.mix((0.49, 0.53, 0.43), (0.64, 0.66, 0.55), grit), lichen * 0.5)
    height += 0.35 * lichen
    col = col * (0.86 + 0.14 * np.clip(round_top, 0.0, 1.0))[..., None]
    col = col * (0.94 + 0.12 * fibre)[..., None]
    rough = 0.9 + 0.05 * (grit - 0.5) - 0.04 * lichen
    occ = tr.cavity(height, 5.0 * RELIEF, 0.3)
    col = col * (0.7 + 0.3 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: smooth olive-yellow to golden-brown, a little glossy, with short pale
    lenticels and the odd darker patch where it is turning to the ridged grey."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.3, 0.25, 0.1), (0.52, 0.46, 0.2), tone)
    dark = tr.smoothstep(0.62, 0.85, tr.fbm(r, h, w, (4 * cm, 4.0 * cm), 3))
    col = tr.mix(col, (0.27, 0.21, 0.13), dark * 0.5)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.8)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.35) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=0.8)
    col = tr.mix(col, (0.7, 0.66, 0.5), lent * 0.75)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.7
    rough = 0.55 + 0.12 * tone
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


def make_bark():
    """Writes WillowBark_* and WillowBarkTwig_*, the bark graded to BARK_MEAN."""
    r = np.random.default_rng(13)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = willow_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("WillowBark", col, height, rough, occ, 1.7 * RELIEF)
    save("WillowBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top: nine LONG strand cells 224 x 1280 px showing about 0.65 x 3.7 m (about 345 px/m: a leaf 12 cm
# long and 1.4 cm wide is 41 x 5 px). Under them nine SHORT cells 224 x 640 showing about 0.65 x 1.85 m, and a
# single leaf (128 square) for the seedling, past the decal strip (u under .375, v under .0625). A strand cell is two
# or three whole hanging twigs with every leaf; the card hangs from the cell's top, its attach point.

LONG = tuple("Long%d" % i for i in range(9))
SHORT = tuple("Short%d" % i for i in range(9))
LEAF = "Leaf"
LONG_H, SHORT_H = 3.55, 1.7  # the twigs' lengths in the cells, m
LEAF_LEN = (0.095, 0.125)


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(LONG):
        atlas.cell(name, 224 * i, 768, 224, 1280, (0.65, 3.7), pad=8)
    for i, name in enumerate(SHORT):
        atlas.cell(name, 224 * i, 128, 224, 640, (0.65, 1.85), pad=8)
    atlas.cell(LEAF, 768, 0, 128, 128, (0.12, 0.12), pad=8)
    return atlas


def leaf_profile(s):
    """Half-width of a willow blade at fraction s from base to tip: a narrow lance, widest a third of the way, long
    drawn-out tip."""
    return float(np.interp(s, (0.0, 0.04, 0.12, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0),
                           (0.0, 0.4, 0.75, 1.0, 0.88, 0.58, 0.3, 0.1, 0.0)))


def leaf_materials(vein=0.3, shade=0.0):
    """The strands' own materials (rendered into the atlas, not exported): leaf, twig. Pale yellow-green above, silvery
    grey-green beneath. `vein` is how much paler the midrib is, `shade` darkens (the icon, drawn small)."""
    mat, g = tr.tk.new_material("WillowLeafSrc")
    attr = g.node("ShaderNodeAttribute", attribute_name="leaf")
    x, s, rv = g.separate(attr.outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Each leaf its own shade: mostly a light yellow-green, some yellower, a few deeper
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.17, 0.29, 0.05), (0.27, 0.38, 0.065))
    base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.1, 0.19, 0.035))
    hi = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=3.0), 0.5, 0.82), 0.5)
    col = g.mix(hi, base, (0.34, 0.42, 0.08))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.6, 1.0), 0.2), col, (0.3, 0.38, 0.08))
    mid = g.ramp(ax, 0.07, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.4)), 7.0))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.44, 0.5),
                 g.math("MULTIPLY", g.ramp(ax, 0.05, 0.2), g.ramp(ax, 0.92, 0.6)))
    veins = g.math("MAXIMUM", mid, g.math("MULTIPLY", lat, 0.45))
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.34, 0.42, 0.13))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    # Silvery undersides: pale grey-green with a hint of white bloom
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.27, 0.34, 0.23), (0.36, 0.42, 0.31)),
                  (0.47, 0.51, 0.4))
    col = g.mix(back, col, under)
    rough = g.mixf(back, 0.45, 0.6)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.2 + vein - 0.3, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("WillowTwigSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=3.0), 0.3, 0.7), (0.115, 0.09, 0.022), (0.2, 0.16, 0.04))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)
    return {"leaf": leaf, "twig": twig, "petiole": twig}


def add_leaf(m, rnd, p, tan, size, side, dir_bias):
    """One willow leaf on a hanging twig at p heading `tan` (down the card): short stalk, then a long narrow blade
    leaving to the twig's `side` (+1 right in the card, -1 left; the card's depth when `dir_bias` is small) at 20-45
    degrees to it, hanging, arched and a little twisted; one in five turned over to show its silver back."""
    lat = Vector((side, 0.0, 0.0)) if rnd.random() < dir_bias else Vector((0.0, 0.0, rnd.choice((-1.0, 1.0))))
    lat = (lat + Vector((rnd.gauss(0, 0.25), 0.0, rnd.gauss(0, 0.25)))).normalized()
    ang = rnd.uniform(0.3, 0.8)
    d = (tan * math.cos(ang) + lat * math.sin(ang)).normalized()
    d.y -= 0.15  # hangs
    d.normalize()
    pl = 0.004
    b = p + d * pl
    tr.twig(m, [p, b], [0.0006, 0.0005], "petiole", 3)
    nl = Vector((rnd.gauss(0.0, 0.5), rnd.gauss(0.0, 0.3), 1.0)) if abs(lat.x) > 0.5 else Vector((1.0, rnd.gauss(0.0, 0.3), rnd.gauss(0.0, 0.5)))
    if rnd.random() < 0.2:
        nl = -nl
    tr.blade(m, b, d, nl, size, size * rnd.uniform(0.11, 0.14), leaf_profile, "leaf", teeth=0, tooth=0.0,
             fold=rnd.uniform(0.1, 0.35), arch=rnd.uniform(0.08, 0.28), twist=rnd.uniform(-35.0, 35.0), rows=6,
             rnd_value=rnd.random())


def strand(m, rnd, x0, length, sway, lean, first=0.045, gap=(0.022, 0.034), thin=0.0016):
    """One whole hanging twig from (x0, 0, 0) down `length`: a slow S in the card's plane (`sway`) and a lean
    (`lean` m over its length), leaves alternating along it every `gap` m and a leaf at its tip, the last 8 per cent
    only sparse."""
    steps = 24
    ph = rnd.uniform(0.0, TAU)
    pts = []
    for i in range(steps + 1):
        f = i / steps
        pts.append(Vector((x0 + lean * f + sway * math.sin(ph + 2.2 * f * math.pi) * min(1.0, f * 3.0),
                           -f * length, 0.03 * math.sin(ph * 1.7 + f * 5.0) * f)))
    tr.twig(m, pts, [thin * (1.0 - 0.7 * i / steps) for i in range(steps + 1)], "twig", 4)
    br = tr.Branch(pts, [thin] * len(pts))
    f = first / length
    side = rnd.choice((-1, 1))
    while f < 0.985:
        p, tan, _ = br.at(f)
        near_tip = f > 0.9
        if not (near_tip and rnd.random() < 0.55):
            size = rnd.uniform(*LEAF_LEN) * (1.0 - 0.3 * max(0.0, f - 0.8) / 0.2) * (0.9 + 0.2 * (1.0 - f))
            add_leaf(m, rnd, p, tan, size, side, 0.78)
        f += rnd.uniform(*gap) / length
        side = -side
    p, tan, _ = br.at(1.0)
    add_leaf(m, rnd, p, tan, rnd.uniform(0.07, 0.1), side, 0.8)


def build_cell(rnd, mats, length, twigs, leafy=1.0):
    """A strand cell's geometry: `twigs` hanging twigs side by side of about `length` (a few shorter), with their
    leaves, in the card's plane (x right, y up, facing +z, the attach point at the origin)."""
    m = tr.Mesh()
    xs = [(-0.14 + 0.28 * (i + rnd.uniform(0.25, 0.75)) / twigs) for i in range(twigs)]
    rnd.shuffle(xs)
    for i, x0 in enumerate(xs):
        L = length * rnd.uniform(0.82, 1.0) if i else length
        strand(m, rnd, x0, L, rnd.uniform(0.012, 0.035), rnd.uniform(-0.05, 0.05),
               gap=(0.022 / leafy, 0.034 / leafy))
    return m.build("StrandSrc", mats)


def make_atlas(atlas, render=True):
    """Builds the strand cells, fits each to what it shows and, with `render`, renders them into the atlas, grades
    and saves it (without, the cells are only measured: the geometry is the same every run)."""
    mats = leaf_materials()
    rnd = random.Random(23)
    objs = {}
    for name in LONG + SHORT:
        long = name.startswith("Long")
        objs[name] = build_cell(rnd, mats, LONG_H if long else SHORT_H, 3 if long else (2 if rnd.random() < 0.4 else 3),
                                1.0)
        atlas.frame(atlas.cells[name], [objs[name]])
    # One leaf hanging from the cell's top, as a strand's leaf hangs from its twig
    m = tr.Mesh()
    tr.twig(m, [Vector(), Vector((0.0, -0.006, 0.0))], [0.0006, 0.0005], "petiole", 4)
    tr.blade(m, Vector((0.0, -0.006, 0.0)), Vector((0.12, -1.0, 0.0)), Vector((0.0, 0.2, 1.0)), 0.1, 0.013,
             leaf_profile, "leaf", teeth=0, fold=0.2, arch=0.18, twist=10.0, rows=10, rnd_value=0.5)
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    for name in LONG + SHORT:
        atlas.render(atlas.cells[name], [objs[name]], samples=24)
    atlas.render(atlas.cells[LEAF], [leaf])
    atlas.grade(LONG + SHORT + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "WillowLeaves")
    atlas.preview(os.path.join(PREVIEWS, "willow_atlas.png"))
    for c in atlas.cells.values():
        print("[willow] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("WillowLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the strand cards
#
# A card of the Long or Short family hangs straight down from a point on a limb or branch. Its length is cut to the
# clearance: it ends 0.1 to 0.7 m above the ground at most, and is kept clear of every trunk. The card keeps the
# cell's width; a card cut short shows only the top part of the cell.

class Strand(tr.Card):
    """A hanging card: `length` m of the cell's top (`frac` of its height), `wk` times the cell's width, `lift`..."""

    def __init__(self, p, a, n, cell, scale, host, s, length=None, wk=1.0, frac=1.0):
        super().__init__(p, a, n, cell, scale, host, s)
        self.length = length if length is not None else cell.world[1] * scale * frac
        self.wk = wk
        self.frac = frac

    @property
    def area(self):
        return cell_width(self.cell) * self.wk * self.length * self.cell.coverage

    def scaled(self, k):
        return Strand(self.p, self.a, self.n, self.cell, self.scale * k, self.host, self.s, self.length * k,
                      self.wk * k, self.frac)

    def on(self, lod):
        p = self.host.tip if self.s >= 1.0 else self.host.drawn_at(self.s, lod)
        return Strand(p, self.a, self.n, self.cell, self.scale, self.host, self.s, self.length, self.wk, self.frac)


def cell_width(cell):
    return cell.world[0]


_card_quads = tr.card_quads


def strand_quads(m, card, rows=1, bend=0.0, key="leaves"):
    """A Strand's quad (2 triangles): `wk` times the cell's width, `length` long, showing the top `frac` of the
    cell; plain cards as treekit draws them."""
    if not isinstance(card, Strand):
        return _card_quads(m, card, rows, bend, key)
    cell = card.cell
    w = cell.world[0] * card.scale * card.wk
    ax, ay = cell.attach
    right = card.n.cross(card.a).normalized()
    u0, v0, u1, v1 = cell.uv
    full = cell.world[1] * card.scale  # the whole cell's height at this scale
    vb = v0 + (v1 - v0) * (1.0 - card.frac)
    a = card.a
    # The cell's top edge is (1 - ay) of its height above the attach point, its shown bottom (ay - 1 + frac) below it
    d_top, d_bot = (ay - 1.0) * full, (ay - 1.0 + card.frac) * full
    lt, lb, rt, rb = [m.v(card.p + right * ((x - ax) * w) + a * d) for x in (0.0, 1.0) for d in (d_top, d_bot)]
    m.quad(lb, rb, rt, lt, ((u0, vb), (u1, vb), (u1, v1), (u0, v1)), key)


tr.card_quads = strand_quads

_place_cards = tr.place_cards


def clearance(tree, p, half, top_z):
    """How far down (m) a card of half-width `half` hanging at p may go: above the ground, and above the highest part
    of any trunk it would otherwise touch (the trunks' radius plus a hand's width of air)."""
    low = 0.0
    for t in tree.trunks:
        for i in range(0, len(t.points) - 1):
            a, b = t.points[i], t.points[i + 1]
            for f in (0.0, 0.25, 0.5, 0.75):
                q = a.lerp(b, f)
                if q.z > p.z + 0.2 or q.z < -0.2:
                    continue
                r = t.spec.radius_at(max(0.0, q.z))
                if math.hypot(q.x - p.x, q.y - p.y) < r + half + 0.2:
                    low = max(low, q.z + 0.12)
    return low


def strands(rnd, tree, fol, lod, spacing):
    """Strand cards along every branch `fol` names: one every `spacing` m, hanging straight down (a few degrees
    off), facing out from the trunk or any way, each as long as the clearance below it allows (a bare share of the
    thin branches carry none, to show their structure)."""
    P = fol.strands
    longs = [tr.ATLAS_CELLS[n] for n in LONG]
    shorts = [tr.ATLAS_CELLS[n] for n in SHORT]
    cards = []
    for br, (s0, s1) in tr._host_spans(tree, fol, lod):
        if br.level >= 2 and rnd.random() < P["bare"]:
            continue
        n = int((s1 - s0) * br.length / spacing)
        ss = [s0 + (s1 - s0) * (i + rnd.uniform(0.15, 0.85)) / max(n, 1) for i in range(n)]
        if fol.tip and (s1 >= 0.999 or not ss):
            ss.append(1.0)
        for s in ss:
            p, tan, _ = br.at(min(s, 0.999))
            if s >= 1.0:
                p = br.tip.copy()
            if p.z < 1.3:
                continue
            wk = rnd.uniform(*P["wk"])
            floor_gap = rnd.uniform(*P["gap"])
            low = max(floor_gap, clearance(tree, p, cell_width(longs[0]) * wk * 0.5, p.z))
            room = p.z - low
            if room < 0.8:
                continue
            if room >= 2.7:
                cell = rnd.choice(longs)
                scale = max(0.75, min(rnd.uniform(*P["scale"]), room / cell.world[1]))
            else:
                cell = rnd.choice(shorts)
                scale = rnd.uniform(*P["scale"])
            length = min(cell.world[1] * scale, room)
            frac = length / (cell.world[1] * scale)
            if frac < 0.45:
                continue
            a = (DOWN + Vector((rnd.gauss(0, 0.04), rnd.gauss(0, 0.04), 0.0))).normalized()
            radial = tree.radial(p, br)
            if rnd.random() < P["face"]:
                ang = rnd.gauss(0.0, 28.0)
                n0 = tr.rotate(radial, UP, ang)
                n0 = Vector((n0.x, n0.y, 0.0)).normalized()
            else:
                b = rnd.uniform(0.0, TAU)
                n0 = Vector((math.cos(b), math.sin(b), 0.0))
            nrm = (n0 - a * n0.dot(a)).normalized()
            cards.append(Strand(p, a, nrm, cell, scale, br, s, length, wk, frac))
    return cards


def place_cards(rnd, tree, fol, lod=0, spacing=None, atlas_cells=None):
    if getattr(fol, "strands", None) is None:
        return _place_cards(rnd, tree, fol, lod, spacing, atlas_cells)
    return strands(rnd, tree, fol, lod, spacing or fol.spacing)


tr.place_cards = place_cards


# ---------------------------------------------------------------- the trees

def limb_shape(t):
    """The limbs' envelope: nearly even, a little longer low down (the dome's skirt)."""
    return 1.0 - 0.18 * t


def strand_foliage(spacing, bare=0.12, scale=(0.9, 1.15), wk=(0.85, 1.25), gap=(0.05, 0.6), face=0.6, level2=(0.08, 1.0),
                   limb=(0.22, 1.0)):
    fol = tr.Foliage(levels={2: level2, 1: limb}, trunk_top=None, spacing=spacing, cells=LONG, tip=True, bend=0.0)
    fol.strands = dict(bare=bare, scale=scale, wk=wk, gap=gap, face=face)
    return fol


def willow(trunks, limbs=(5, 7), reach=1.0, crown=0.5, favor=None, inner=0.0, budget=7600, density=1.7, spacing=0.12,
           limb_sides=8, whips=0.25, bare=0.1, droop=0.3, branch_len=(2.0, 3.8), scale=(0.9, 1.15),
           cluster_spacing=0.9, gap=(0.05, 0.6), limb_len=(7.0, 9.6), angle=40.0):
    """A weeping willow's TreeSpec: `trunks` (tr.Trunk), `limbs` big arching limbs per trunk (from `crown` of its
    height), `reach` scaling their length, level 2 the drooping branches (`density` per meter of limb, `branch_len`)
    that carry the curtain, level 3 a few bare whips hanging straight down (`whips` per meter of branch)."""
    L = tr.Level(count=limbs, span=(crown, 0.98), length=(limb_len[0] * reach, limb_len[1] * reach), shape=limb_shape,
                 angle=angle, angle_tip=angle - 8.0, angle_vary=9.0, radius=0.85, radius_length=0.5, radius_max=0.26,
                 tip_radius=0.03, step=0.45, gravitropism=0.16, droop=droop, wander=0.22, outward=0.25, favor=favor,
                 inner=inner, floor=0.6, sides=(limb_sides, 6, 4), seg=(1.0, 1.8, 3.0), min_len=(0.0, 0.0, 0.0))
    B = tr.Level(per_meter=density, span=(0.1, 0.98), length=branch_len, shape="tapered", angle=62.0, angle_tip=50.0,
                 angle_vary=12.0, radius=0.45, radius_length=0.5, radius_max=0.045, tip_radius=0.005, step=0.35,
                 gravitropism=-0.05, droop=0.3, wander=0.3, outward=0.3, floor=0.5, sides=(5, 3, 0),
                 seg=(0.9, 1.6, 9.0), min_len=(0.0, 1.0, 99.0))
    W = tr.Level(per_meter=whips, span=(0.2, 0.95), length=(1.8, 3.4), angle=78.0, angle_tip=70.0, angle_vary=8.0,
                 radius=0.5, radius_length=0.4, radius_max=0.006, tip_radius=0.0015, step=0.7, gravitropism=-0.25,
                 droop=0.5, wander=0.1, outward=0.1, floor=0.8, sides=(3, 0, 0), seg=(1.1, 9.0, 9.0),
                 min_len=(0.0, 99.0, 99.0), min_length=0.8)
    stubs = tr.Level(count=(2, 4), span=(0.08, crown - 0.05), length=(0.05, 0.2), angle=72.0, angle_vary=12.0,
                     radius=0.2, radius_length=0.0, radius_max=0.04, tip_radius=0.01, broken=True, step=0.05,
                     droop=0.3, wander=0.2, sides=(9, 6, 0), seg=(0.3, 1.0, 1.0), min_length=0.03)
    cl = tr.Foliage(levels={1: (0.35, 1.0)}, trunk_top=None, spacing=cluster_spacing, cells=LONG, tip=True, bend=0.0)
    cl.strands = dict(bare=0.0, scale=(1.0, 1.25), wk=(1.0, 1.45), gap=gap, face=0.5)
    return tr.TreeSpec(
        trunks=trunks, levels=[L, B, W], stubs=stubs, budget=budget, lod_share=(0.5, 0.2),
        foliage=strand_foliage(spacing, bare, scale, gap=gap), cluster=cl,
        bark_key=bark_key, bark_uv=UV, ground_v=0.1)


def trunk(**kw):
    base = dict(flare=0.4, flare_height=0.6, lobes=(6, 0.14), taper=0.4, tip_radius=0.1, wander=0.14,
                sides=(12, 8, 6), seg=(0.8, 1.6, 3.0), rings=((0.0, 0.15, 0.4, 0.8, 1.6), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeWillowSeed in game): a yellowish whip about 0.8 m tall with a
    few thin side shoots, hung with single narrow leaves (the atlas's Leaf cell)."""
    shoots = tr.Level(count=(3, 5), span=(0.3, 0.9), length=(0.1, 0.25), shape="tapered", angle=55.0, angle_tip=40.0,
                      radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.2, droop=0.3, wander=0.4, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.8, radius=0.0055, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0012,
                         lean=(0.06, -0.04), bow=0.4, wander=0.02, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.8, 1.15), hang=0.6, spread=0.3, out=0.6, face=0.5, up=0.2, roll=35.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.1, cells=(LEAF,), scale=(1.0, 1.3),
                           hang=0.6, spread=0.3, out=0.6, face=0.5, up=0.2, roll=35.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=0.1, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # Typical mature tree, about 14 m, crown about 14 m wide
    ("Willow01", 5, lambda: willow([trunk(height=6.0, radius=0.4, lean=(0.5, 0.25), bow=0.3)])),
    # Leaning about 25 degrees over the water, about 12.5 m, the crown fuller on the water side
    ("Willow02", 17, lambda: willow([trunk(height=5.4, radius=0.36, lean=(2.5, 0.8), bow=0.15, wander=0.18)],
                                    limbs=(5, 6), favor=((1.0, 0.3), 0.5), reach=0.95)),
    # An old big multi-trunk tree, about 16 m: three trunks from one base
    ("Willow03", 29, lambda: willow([trunk(height=5.6, radius=0.34, base=(0.15, 0.05), lean=(1.3, 0.4), bow=0.4,
                                          sides=(10, 7, 5)),
                                     trunk(height=5.2, radius=0.3, base=(-0.12, 0.2), lean=(-1.2, 1.0), bow=0.5,
                                           sides=(10, 7, 5)),
                                     trunk(height=4.6, radius=0.25, base=(-0.05, -0.2), lean=(-0.2, -1.5), bow=0.5,
                                           sides=(9, 6, 5))],
                                    limbs=(3, 4), reach=1.0, inner=0.5, budget=8000, density=0.95, spacing=0.2,
                                    limb_len=(8.0, 11.0), limb_sides=7)),
    # Young tree, about 7 m
    ("Willow04", 41, lambda: willow([trunk(height=2.6, radius=0.11, lean=(-0.2, 0.3), bow=0.2, flare=0.25,
                                          lobes=(5, 0.08), tip_radius=0.04, sides=(9, 6, 5))],
                                    limbs=(4, 5), reach=0.5, budget=5200, density=1.4, spacing=0.14, limb_sides=6,
                                    branch_len=(1.2, 2.4), scale=(0.7, 0.95), cluster_spacing=0.7, whips=0.2,
                                    limb_len=(7.5, 10.5), angle=44.0, droop=0.14)),
    ("WillowSapling", 53, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """WillowSeed_Icon.png (160 x 160, in Trees/Willow): a ripe willow catkin shedding its cottony seed, lying across
    one of its narrow leaves, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.5, shade=0.25)
    mat, g = tr.tk.new_material("WillowFluffSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(s, 0.0, 1.0), (0.72, 0.7, 0.62), (0.9, 0.9, 0.86))
    tr.tk.finish(mat, g, col, 0.0, 0.9)
    mats["fluff"] = mat
    mat, g = tr.tk.new_material("WillowCapsuleSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(g.noise(300.0, detail=3.0), 0.3, 0.7), (0.17, 0.2, 0.04), (0.3, 0.28, 0.08))
    tr.tk.finish(mat, g, col, 0.0, 0.7, g.bump(g.noise(260.0, detail=4.0), 0.3, 0.0004))
    mats["capsule"] = mat

    m = tr.Mesh()
    # The leaf, long and narrow, from the bottom right up to the left
    stalk = Vector((0.04, 0.004, -0.04))
    tr.twig(m, [Vector((0.046, 0.004, -0.048)), stalk], [0.0009, 0.0008], "petiole", 5)
    tr.blade(m, stalk, Vector((-0.85, 0.0, 0.5)), Vector((0.2, -1.0, 0.2)), 0.2, 0.026, leaf_profile, "leaf",
             fold=0.3, arch=0.22, twist=-14.0, rows=14, rnd_value=0.4)
    # The catkin, 6 cm: a core of green capsules, each splitting to put out a tuft of white down, fluffier toward
    # the lower end
    top, tip = Vector((0.034, -0.012, 0.038)), Vector((-0.008, -0.016, -0.014))
    axis = (tip - top).normalized()
    tr.twig(m, [top - axis * 0.012, top], [0.0013, 0.0013], "twig", 5)
    core = [top.lerp(tip, i / 8) for i in range(9)]
    tr.twig(m, core, [0.0034] * 9, "capsule", 8)
    _, u, v = tr.basis(axis)
    rnd = random.Random(7)
    for i in range(150):
        f = min(0.97, 0.04 + 0.92 * (i + rnd.uniform(-0.4, 0.4)) / 150)
        a = i * tr.GOLDEN + rnd.uniform(-0.25, 0.25)
        out = u * math.cos(a) + v * math.sin(a)
        base = top.lerp(tip, f) + out * 0.0034
        # A tuft: several fine curved strands out from the capsule
        for _ in range(3):
            d = (out * rnd.uniform(0.6, 1.3) + axis * rnd.uniform(0.3, 0.8)
                 + (u * rnd.gauss(0, 0.4) + v * rnd.gauss(0, 0.4))).normalized()
            pts = [base, base + d * 0.007 + Vector((0.0, 0.0, -0.001)), base + d * 0.014 + Vector((0.0, 0.0, -0.004))]
            tr.twig(m, pts, [0.00045, 0.00038, 0.0003], "fluff", 3)
    obj = m.build("WillowSeedIcon", mats)
    obj.scale = (7.0, 7.0, 7.0)
    obj.location = (-0.05, 0.0, 0.31)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.62)
    tr.tk.icon(cam, os.path.join(FOLDER, "WillowSeed_Icon.png"), hide=())
    print("[willow] icon written")


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
    mats = {"bark": tr.textured("WillowBark", paths("WillowBark")),
            "twig": tr.textured("WillowBarkTwig", paths("WillowBarkTwig")),
            "leaves": tr.textured("WillowLeaves", paths("WillowLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    only = [a for a in args[3:]]
    for name, seed, make in VARIANTS:
        if only and name not in only:
            continue
        spec = make()
        if STEPS == "skeleton" and spec.foliage is not None:
            spec.foliage = None
            spec.cluster = None
        tree = tr.grow(spec, seed, name)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[willow] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("willow01", lods[0], PREVIEWS, figure)
    tr.preview_lods("willow01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("willow", [b[2][0] for b in built if b[0] != "WillowSapling"], PREVIEWS, figure,
                     spots=[(-9.0, 5.0), (3.0, 10.0), (10.0, 3.0), (-1.0, -3.5)])
    if STEPS == "all":
        make_icon()
    print("[willow] done")


main()
