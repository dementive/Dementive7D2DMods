"""Old wolf oak (Quercus robur, an open-grown "wolf tree") in summer, on treekit.py (maple.py is the closest example,
willow.py the newest; TREES.md has the rules).

A lone, ancient oak standing by itself in a meadow, the landmark of the country round it: a very short, massive,
flared and buttressed trunk a metre across and more (deep dark grey-brown ridges in blocky plates), splitting at 2 to 4 m
into a few huge limbs that sweep out nearly level and arch up and over, 10 to 13 m from the trunk, some sagging to rest
on the ground, under a wide flat-topped dome of lobed oak leaves in layered masses with the sky showing between. A few
dead limb stubs, one big knot-hollow in the trunk, moss along the upper side of the limbs.

    blender -b --factory-startup --python trees/wolf_oak.py -- <unity trees folder> <preview folder> [step] [variants]

with absolute paths `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`.
Steps: `all`, `textures` (bark, limb bark, hollow and leaves, then stop), `bark`, `bark-textures`, `atlas`, `trees`,
`icon`, `skeleton` (the trees without leaves, previews only). It writes Trees/WolfOak/ (the bark, limb, hollow, twig
and leaf textures, WolfOak01..04 and the seedling WolfOakSapling with their impostors, WolfOakSeed_Icon.png), the
WolfOak lines of Trees/trees.txt and trunks.txt (the trunk's, and the low part of every thick limb a player could walk
into) and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "WolfOak")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
UP, DOWN = tr.UP, tr.DOWN

# ---------------------------------------------------------------- bark textures
#
# WolfOakBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (6.3 m on the trunk's metre
# radius), drawn at its size on that trunk (6.5 px per cm round and up): ridges 6 to 12 cm wide running up between
# deep dark furrows that fork and rejoin, checked across into blocks and plates, flaked, lichened.
# WolfOakBarkLimb: 1024 x 2048, once round a limb of about 18 cm radius (9 px per cm): the same bark finer, and a band
# of moss along the middle of its width: BarkUV maps u once round, and the limbs are turned (Branch.rot) so that
# middle is the limb's upper side.
# WolfOakBarkHollow: the knot-hollow patch on the trunk, drawn on its own (an oval, so the cavity's edge is the
# patch's rim). WolfOakBarkTwig: 512 x 1024, the dark smooth-to-scaly bark of thin twigs (under 1.2 cm radius).

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)  # radii per repeat up a tube: 2 pi
R_DESIGN = 100.0  # cm: the trunk the bark is drawn for (WolfOak01's, 1 m up)
PX = WRAPS * W / (TAU * R_DESIGN)  # pixels per cm round and up that trunk
RELIEF = PX / 13.0  # birch's first bark's 13 px per cm: slopes and cavities keep their size in cm
TWIST = 0.31
LW, LH = 1024, 2048
LIMB_R_DESIGN = 18.0
LPX = LW / (TAU * LIMB_R_DESIGN)
LIMB_R = 0.28  # a limb thinner than this (radius, m) has the limb bark
BARK_MEAN = (88, 79, 70)
LEAF_MEAN = (73, 83, 55)
TWIG_R = 0.012
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "limb": tr.BarkUV(k=TAU * LH / LW),
    "twig": tr.BarkUV(k=4.0 * math.pi),
    "hollow": tr.BarkUV(),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    if br.level == 0 or "stub" in br.tags or r >= LIMB_R:
        return "bark"
    return "limb"


def oak_bark(r, h=H, w=W, px=PX, scale=1.0):
    """Old oak bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: ridges 8 to
    12 cm wide running up, forking and rejoining between deep furrows 1 to 2 cm wide and dark, each ridge cross-checked
    into blocks 15 to 40 cm tall, rounded on top, fibrous, weathered grey on the tops and brown in patches, with grey
    lichen crusts. `scale` shrinks every feature (limb bark)."""
    cm = px / scale
    warp = ((tr.fbm(r, h, w, (6 * cm, 30 * cm), 3) - 0.5) * 4.0 * cm,
            (tr.fbm(r, h, w, (8 * cm, 24 * cm), 3) - 0.5) * 10.0 * cm)
    edge, plate, _, _ = tr.cells(r, h, w, 9.0 * cm, 5.5, warp)
    edge2, plate2, _, _ = tr.cells(r, h, w, 15 * cm, 4.5, warp)
    # Cross checks: a coarser, rounder network whose edges cut the ridges into blocks
    xedge, block, _, _ = tr.cells(r, h, w, 16 * cm, 1.6, warp)
    n = plate.max() + 1
    shade = r.random(n)[plate]
    tilt = (r.random(n) * 2.0 - 1.0)[plate]
    shade2 = r.random(plate2.max() + 1)[plate2]
    bshade = r.random(block.max() + 1)[block]
    btilt = (r.random(block.max() + 1) * 2.0 - 1.0)[block]
    wobble = tr.fbm(r, h, w, (1.0 * cm, 5 * cm), 3)
    fork = tr.smoothstep(0.5, 0.62, tr.fbm(r, h, w, (10 * cm, 34 * cm), 3))
    furrow = 1.0 - tr.smoothstep(0.0, (0.55 + 0.75 * wobble) * cm, edge)
    furrow = np.maximum(furrow, (1.0 - tr.smoothstep(0.0, (0.4 + 0.6 * wobble) * cm, edge2)) * fork)
    gate = tr.smoothstep(0.42, 0.58, tr.fbm(r, h, w, (6 * cm, 14 * cm), 3))
    cross = (1.0 - tr.smoothstep(0.0, (0.28 + 0.4 * wobble) * cm, xedge)) * (0.35 + 0.65 * gate)
    shoulder = 1.0 - tr.smoothstep(0.0, 1.8 * cm, edge)
    body = tr.smoothstep(0.0, 1.2 * cm, edge)
    fibre = tr.fbm(r, h, w, (0.12 * cm, 2.2 * cm), 3)
    streak = tr.fbm(r, h, w, (0.3 * cm, 5.0 * cm), 3)
    grit = tr.fbm(r, h, w, (0.18 * cm, 0.18 * cm), 3)
    mottle = tr.fbm(r, h, w, (2.0 * cm, 6.0 * cm), 4)
    coarse = tr.fbm(r, h, w, (14 * cm, 32 * cm), 3)
    # Short checks across the ridge tops
    checks = np.zeros((h, w))
    for _ in range(int((w / cm) * (h / cm) * 0.011)):
        tr.stamp_lens(checks, r.uniform(0, w), r.uniform(0, h), r.uniform(3.0, 9.0) * cm,
                      max(1.2, r.uniform(0.35, 0.8) * cm), r.uniform(0.5, 1.0), ends=0.8)
    checks *= body
    round_top = tr.smoothstep(0.0, 2.8 * cm, edge)
    height = (2.0 * round_top + 0.5 * tilt * shoulder + 0.6 * btilt * tr.smoothstep(0.0, 4 * cm, xedge) * body
              + 0.75 * fibre + 0.45 * streak + 0.4 * grit + 0.35 * mottle - 3.4 * furrow - 2.0 * cross * body
              - 1.4 * checks + 0.35 * bshade)
    col = tr.mix((0.2, 0.17, 0.145), (0.5, 0.455, 0.41),
                 0.26 * shade + 0.2 * mottle + 0.18 * streak + 0.1 * fibre + 0.08 * grit + 0.08 * shade2 + 0.12 * bshade)
    pale = tr.smoothstep(0.5, 0.8, coarse + (mottle - 0.5) * 0.4) * round_top
    col = tr.mix(col, (0.6, 0.57, 0.52), pale * 0.32)
    brown = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (16 * cm, 28 * cm), 3))
    col = tr.mix(col, col * np.array((1.12, 0.96, 0.8)), brown[..., None] * 0.8)
    # Orange-brown inner bark on the furrow shoulders, black deep in them and in the cross cracks
    col = tr.mix(col, (0.3, 0.17, 0.09), np.clip(shoulder - 0.15, 0.0, 1.0) * (1.0 - furrow) * 0.16 * (0.5 + mottle))
    col = tr.mix(col, (0.04, 0.033, 0.028), np.clip(furrow * 1.2, 0.0, 1.0))
    col = tr.mix(col, (0.07, 0.055, 0.045), np.clip(cross * body * 1.2, 0.0, 1.0) * 0.9)
    col = tr.mix(col, (0.1, 0.08, 0.065), np.clip(checks, 0.0, 1.0) * 0.8)
    lichen = (tr.smoothstep(0.74, 0.88, tr.fbm(r, h, w, (1.7 * cm, 1.7 * cm), 4))
              * tr.smoothstep(0.52, 0.76, tr.fbm(r, h, w, (18 * cm, 26 * cm), 3)) * body)
    col = tr.mix(col, tr.mix((0.5, 0.54, 0.43), (0.64, 0.66, 0.55), grit), lichen * 0.5)
    height += 0.35 * lichen
    col = col * (0.84 + 0.16 * np.clip(round_top, 0.0, 1.0))[..., None]
    col = col * (0.94 + 0.12 * fibre)[..., None]
    rough = 0.9 + 0.05 * (grit - 0.5) - 0.04 * lichen
    occ = tr.cavity(height, 5.0 * RELIEF / scale, 0.3)
    col = col * (0.68 + 0.32 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def moss_band(r, h, w, cm):
    """A mask (0-1) of moss along the middle of a limb texture's width (its upper side, see the module doc): thick on
    the top, ragged at its edges, broken into cushions."""
    x = np.abs((np.arange(w) + 0.5) / w - 0.5)[None, :]
    edge = 0.2 + (tr.fbm(r, h, w, (5 * cm, 22 * cm), 4) - 0.5) * 0.26
    band = 1.0 - tr.smoothstep(edge - 0.07, edge, x)
    cush = tr.smoothstep(0.32, 0.55, tr.fbm(r, h, w, (1.6 * cm, 2.4 * cm), 4))
    return np.clip(band * (0.35 + 0.65 * cush) * 1.25, 0.0, 1.0), cush


def limb_bark(r):
    """The limb bark, WolfOakBarkLimb: the oak bark at limb size, with a band of moss along its middle: bright yellowgreen cushions with darker green between, lit-looking tips."""
    col, height, rough, occ = oak_bark(r, LH, LW, LPX, scale=1.0)
    col, k = tr.match_mean(col, BARK_MEAN)
    cm = LPX
    moss, cush = moss_band(r, LH, LW, cm)
    fine = tr.fbm(r, LH, LW, (0.3 * cm, 0.3 * cm), 3)
    mcol = tr.mix((0.1, 0.17, 0.05), (0.27, 0.36, 0.1), 0.45 * cush + 0.35 * fine + 0.2 * tr.fbm(r, LH, LW, (3 * cm, 3 * cm), 3))
    col = tr.mix(col, mcol, moss[..., None] * 0.92)
    height = height + 2.2 * moss * (0.5 + 0.5 * cush) + 0.5 * moss * fine
    rough = np.where(moss > 0.3, 0.95, rough)
    occ = np.clip(occ * (1.0 - 0.15 * moss * (1.0 - cush)), 0.0, 1.0)
    return np.clip(col, 0.0, 1.0), height, rough, occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: dark brown-grey, finely scaly, with short pale lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.14, 0.115, 0.095), (0.3, 0.26, 0.22), tone)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.7)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.34) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=0.8)
    col = tr.mix(col, (0.55, 0.5, 0.42), lent * 0.7)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.5 * grain + lent * 0.7
    rough = 0.65 + 0.1 * tone
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


HW, HH = 768, 1280  # the hollow patch: 0.78 x 1.3 m, 10 px per cm


def hollow_bark(r):
    """The knot-hollow patch, an oval of bark with a dark cavity in it (the patch is cut to the oval, so the texture's
    outer ring is bark all round): a raised, burled and cracked rim, then a deep black hollow, charred-looking old
    wood and splintered heartwood fibres at its edges, a cobweb of paler dead wood at the bottom of the opening."""
    cm = HW / 78.0
    col, height, rough, occ = oak_bark(r, HH, HW, cm, scale=1.0)
    col, _ = tr.match_mean(col, BARK_MEAN)
    Y, X = np.mgrid[0:HH, 0:HW].astype(np.float64)
    x = (X + 0.5 - HW * 0.5) / (HW * 0.5)
    y = (Y + 0.5 - HH * 0.5) / (HH * 0.5)
    jit = (tr.fbm(r, HH, HW, (7 * cm, 7 * cm), 4) - 0.5) * 0.22
    # the oval cavity sits low and to the middle, a taller opening than wide, pointed at the top
    d = np.sqrt((x / 0.86) ** 2 + ((y + 0.02 - 0.1 * x * x) / 0.88) ** 2) + jit
    inner = 1.0 - tr.smoothstep(0.9, 1.0, d)
    lip = tr.smoothstep(0.7, 1.0, d) * (1.0 - tr.smoothstep(1.0, 1.42, d))
    # beyond d 1.42 the oval's ordinary bark: blend into the bark (burl swelling)
    swell = (1.0 - tr.smoothstep(1.05, 1.9, d))
    wood = tr.fbm(r, HH, HW, (0.35 * cm, 8 * cm), 4)
    splinters = tr.smoothstep(0.55, 0.75, tr.fbm(r, HH, HW, (0.5 * cm, 5 * cm), 3)) * (1.0 - inner * 0.6)
    cavity = np.clip(inner * 1.15, 0.0, 1.0)
    depth = (1.0 - d.clip(0.0, 1.0))
    wcol = tr.mix((0.22, 0.17, 0.12), (0.46, 0.38, 0.3), 0.5 * wood + 0.5 * splinters)
    col = tr.mix(col, (0.12, 0.09, 0.07), lip * 0.55)
    col = tr.mix(col, wcol, np.clip(lip * 0.0 + tr.smoothstep(0.85, 1.0, d) * (1.0 - tr.smoothstep(1.02, 1.2, d)), 0.0, 1.0) * 0.8)
    col = tr.mix(col, (0.02, 0.016, 0.013), cavity * (0.55 + 0.45 * tr.smoothstep(0.0, 0.55, 1.0 - d.clip(0, 1))))
    # a patch of pale dead wood low in the opening, lit by the sky
    floor = cavity * tr.smoothstep(-0.35, -0.65, y) * (0.5 + 0.5 * wood)
    col = tr.mix(col, (0.3, 0.25, 0.19), floor * 0.55)
    height = height + 3.0 * lip + 1.2 * swell * (0.6 + 0.4 * wood) - 6.0 * cavity * (0.6 + 0.4 * depth) + 1.6 * splinters * lip
    rough = np.where(cavity > 0.3, 0.97, rough)
    occ = np.clip(occ * (1.0 - 0.9 * cavity * (0.4 + 0.6 * depth)), 0.0, 1.0)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def make_bark():
    """Writes WolfOakBark_*, WolfOakBarkLimb_*, WolfOakBarkHollow_* and WolfOakBarkTwig_*, the bark graded to BARK_MEAN."""
    r = np.random.default_rng(17)

    def save(name, col, height, rough, occ, relief, blur=0.6):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, blur), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = oak_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("WolfOakBark", col, height, rough, occ, 1.5 * RELIEF)
    save("WolfOakBarkLimb", *limb_bark(r), 1.5 * LPX / 13.0)
    save("WolfOakBarkHollow", *hollow_bark(r), 1.5 * (HW / 78.0) / 13.0)
    save("WolfOakBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top: three big sprays (640 x 768 px, about 1.3 x 1.56 m: 490 px per m, an 11 cm leaf is 54 px long)
# of oak twigs thick with leaves; under them two cluster cells (1024 square, 3.4 m) for LOD2 and one leaf (128
# square) for the seedling, past the decal strip (u under .375, v under .0625).

SPRAYS = ("Spray0", "Spray1", "Spray2")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"
LEAF_LEN = (0.085, 0.115)


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 640 * i, 1280, 640, 768, (1.3, 1.56))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1024, (3.4, 3.4))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.14, 0.14), pad=8)
    return atlas


def envelope(s):
    """Half-width of an oak blade (before lobing) at fraction s from base to tip: obovate, widest about 62 %."""
    return float(np.interp(s, (0.0, 0.03, 0.1, 0.3, 0.5, 0.64, 0.8, 0.92, 1.0),
                           (0.0, 0.3, 0.45, 0.72, 0.92, 1.0, 0.88, 0.55, 0.0)))


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def oak_leaf(m, base, direction, normal, length, rnd, key="leaf", rows=34):
    """A lobed oak leaf of real geometry from its stalk's end `base` along `direction`, facing `normal`, `length`
    long: an obovate blade with 5 to 6 rounded lobes a side (the left and right sets out of step, as a real leaf's
    are), deep narrow sinuses, a short fold along the midrib, an arched tip, a little twist. "leaf" = (across, along,
    a per-leaf random) for the material's veins."""
    d = Vector(direction).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    hw = length * rnd.uniform(0.44, 0.54) * 0.5
    depth, lobes = rnd.uniform(0.5, 0.64), rnd.uniform(5.0, 6.2)
    pl, pr = rnd.uniform(0.0, 1.0), rnd.uniform(0.0, 1.0)
    fold, arch, twist = rnd.uniform(0.08, 0.3), rnd.uniform(0.05, 0.18), rnd.uniform(-30.0, 30.0)
    rv = rnd.random()
    mid, left, right = [], [], []
    for i in range(rows + 1):
        s = i / rows
        e = envelope(s)
        fade = smooth(0.05, 0.2, s) * (1.0 - smooth(0.9, 1.0, s))

        def lobe(ph):
            return 1.0 - depth * (1.0 - abs(math.sin(math.pi * (lobes * s + ph))) ** 0.55) * fade

        wl, wr = e * lobe(pl), e * lobe(pr + 0.5)
        rot = Matrix.Rotation(math.radians(twist * s), 3, d)
        sd, up = rot @ side, rot @ nl
        c = Vector(base) + d * (s * length) - nl * (arch * s * s * length)
        mid.append(m.v(c, leaf=(0.0, s, rv)))
        left.append(m.v(c - sd * (wl * hw) + up * (fold * wl * hw), leaf=(-wl, s, rv)))
        right.append(m.v(c + sd * (wr * hw) + up * (fold * wr * hw), leaf=(wr, s, rv)))
    uv = ((0, 0),) * 4
    for i in range(rows):
        m.quad(mid[i], mid[i + 1], right[i + 1], right[i], uv, key)
        m.quad(mid[i], left[i], left[i + 1], mid[i + 1], uv, key)


def leaf_materials(vein=0.3, shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): leaf, twig, petiole. Dark green above with
    paler yellow-green midrib and veins, greyer green beneath."""
    mat, g = tr.tk.new_material("OakLeafSrc")
    attr = g.node("ShaderNodeAttribute", attribute_name="leaf")
    x, s, rv = g.separate(attr.outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.075, 0.17, 0.03), (0.12, 0.24, 0.04))
    base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.05, 0.11, 0.02))
    hi = g.math("MULTIPLY", g.ramp(g.noise(26.0, detail=3.0), 0.5, 0.82), 0.5)
    col = g.mix(hi, base, (0.15, 0.27, 0.05))
    mid = g.ramp(ax, 0.06, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.4)), 6.5))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.45, 0.5),
                 g.math("MULTIPLY", g.ramp(ax, 0.05, 0.2), g.ramp(ax, 0.95, 0.5)))
    veins = g.math("MAXIMUM", mid, g.math("MULTIPLY", lat, 0.45))
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.27, 0.36, 0.1))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.17, 0.24, 0.11), (0.23, 0.3, 0.15)),
                  (0.33, 0.39, 0.2))
    col = g.mix(back, col, under)
    rough = g.mixf(back, 0.5, 0.7)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.2 + vein - 0.3, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("OakTwigSrc")
    col = g.mix(g.ramp(g.noise(140.0, detail=3.0), 0.3, 0.7), (0.05, 0.04, 0.03), (0.1, 0.085, 0.065))
    tr.tk.finish(mat, g, col, 0.0, 0.55)
    twig = tr.signals(mat, col, 0.55)

    mat, g = tr.tk.new_material("OakPetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    col = g.mix(g.ramp(t, 0.0, 0.85), (0.14, 0.1, 0.04), (0.13, 0.2, 0.05))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    pet = tr.signals(mat, col, 0.5)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, way, size):
    """A leaf on a very short stalk at p heading `way` (in the card's plane, x right, y up, facing +z), held out
    nearly flat to the card and tilted at random; one in nine turned to show its paler back."""
    w = Vector(way).normalized()
    q = p + w * (size * rnd.uniform(0.04, 0.09))
    tr.twig(m, [p, q], [0.0012, 0.0010], "petiole", 4)
    nl = Vector((rnd.gauss(0.0, 0.3), rnd.gauss(0.0, 0.3) + 0.1, 1.0))
    if rnd.random() < 0.11:
        nl = Vector((nl.x, nl.y, -0.6))
    oak_leaf(m, q, (w + Vector((rnd.gauss(0.0, 0.2), rnd.gauss(0.0, 0.2), rnd.gauss(0.0, 0.1)))).normalized(), nl, size, rnd)


def spray(m, rnd, start, direction, length, depth=2):
    """An oak shoot hanging from `start`: a leaf every 3 to 5 cm alternating sides along it, a couple of leafy side
    shoots (to `depth` levels), and a tuft of six or seven leaves round its tip, as oak carries them."""
    pts = tr.bend_path(start, direction, length, 0.55, steps=14, down=(0.0, -1.0, 0.0))
    tr.twig(m, pts, [0.0042 * (1.0 - 0.55 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 6)
    tw = tr.Branch(pts, [0.004] * len(pts))
    f, side = rnd.uniform(0.04, 0.09), rnd.choice((-1, 1))
    while f < 0.9:
        p, tan, _ = tw.at(f)
        lat = Vector((-tan.y, tan.x, 0.0)).normalized()
        if depth > 0 and f > 0.12 and rnd.random() < 0.3:
            spray(m, rnd, p, (lat * side * 0.85 + tan * 0.55).normalized(), length * rnd.uniform(0.35, 0.5), depth - 1)
        else:
            way = lat * side * 0.9 + tan * 0.55 + Vector((0.0, 0.0, rnd.uniform(-0.15, 0.3)))
            add_leaf(m, rnd, p, way, rnd.uniform(*LEAF_LEN))
        if rnd.random() < 0.7:
            way = -lat * side * 0.9 + tan * 0.55 + Vector((0.0, 0.0, rnd.uniform(-0.15, 0.3)))
            add_leaf(m, rnd, p, way, rnd.uniform(*LEAF_LEN))
        f += rnd.uniform(0.016, 0.026) / length * (1.0 + 0.3 * f)
        side = -side
    p, tan, _ = tw.at(1.0)
    for k in range(rnd.randint(5, 7)):
        way = tr.rotate(tan, (0.0, 0.0, 1.0), (k - 3) * rnd.uniform(26.0, 38.0)) + Vector((0.0, 0.0, rnd.uniform(0.0, 0.3)))
        add_leaf(m, rnd, p, way, rnd.uniform(*LEAF_LEN) * (0.8 if abs(k - 3) > 2 else 1.0))


def make_atlas(atlas, render=True):
    """Builds the sprays, clusters and the single leaf, fits their cells; with `render`, renders them into the atlas,
    grades the leaves and saves it (without, the cells are only measured: the geometry is the same every run)."""
    mats = leaf_materials()
    rnd = random.Random(23)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.18, 0.4), -1.0, rnd.uniform(-0.1, 0.1))),
              rnd.uniform(0.82, 0.98))
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        # A leafy branchlet: a stem and three side stems thick with sprays turned every way
        m = tr.Mesh()
        side = (1, -1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.45, -1.0, 0.1)), rnd.uniform(1.6, 1.9), 0.4, steps=10,
                              down=(0.0, -1.0, 0.0))]
        main_stem = tr.Branch(stems[0], [0.008] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.68, -side)):
            p, tan, _ = main_stem.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.8, 1.05), 0.5, steps=8, down=(0.0, -1.0, 0.0)))
        for k, st in enumerate(stems):
            r0 = 0.012 if k == 0 else 0.008
            tr.twig(m, st, [r0 * (1.0 - 0.6 * i / (len(st) - 1)) for i in range(len(st))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        for k, st in enumerate(stems):
            br = tr.Branch(st, [0.006] * len(st))
            for j in range(8 if k == 0 else 4):
                f = 0.1 + 0.9 * (j + rnd.uniform(0.2, 0.8)) / (8 if k == 0 else 4)
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
    end = Vector((0.003, -0.012, 0.0))
    tr.twig(m, [Vector(), end], [0.0014, 0.0012], "petiole", 4)
    oak_leaf(m, end, Vector((0.05, -1.0, 0.0)), Vector((0.0, 0.2, 1.0)), 0.1, random.Random(5))
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "WolfOakLeaves")
    atlas.preview(os.path.join(PREVIEWS, "wolf_oak_atlas.png"))
    for c in atlas.cells.values():
        print("[wolf_oak] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("WolfOakLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- growing: a tree with sagging limbs

def grow_oak(spec, seed, name, sag=None):
    """treekit.grow, plus `sag` (a Level): extra limbs off each trunk, drooping to rest on the ground. Limbs then get
    turned so the limb bark's moss band lies on their upper side."""
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
                if li == 0 and sag is not None:
                    nxt += tr.grow_children(rnd, tree, br, sag, 1)
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
        if br.level >= 1 and "stub" not in br.tags:
            br.rot = math.pi * 0.5 + rnd.uniform(-0.2, 0.2)
    if spec.foliage is not None:
        tree.cards = tr.place_cards(rnd, tree, spec.foliage)
    return tree


# ---------------------------------------------------------------- the knot-hollow patch
#
# An oval patch of the hollow texture laid on the lowest trunk, facing the way HOLLOW says: a fan of rings round its
# middle following the trunk's surface (with the trunk's flare and buttress lobes), its rim lifted a hand's width off
# the bark and the middle laid nearly flush, so the lip stands out round the dark cavity. Added through the kit's
# scar hook, so LOD0 and LOD1 draw it.

HOLLOW = {}  # tree name -> (trunk index, height, azimuth, width, height of the oval)


def hollow_quads(m, tree, lod):
    spec = HOLLOW.get(tree.name)
    if spec is None:
        return
    ti, z0, az, wid, hgt = spec
    t = tree.trunks[ti]
    ring_n = 14 if lod == 0 else 8
    rings = 4 if lod == 0 else 3
    lobes = getattr(t.spec, "lobes", (0, 0.0))
    # the trunk's mean radius there and its centre: sample the tube like _tube does
    cache = {}

    def surface(z, a):
        s = t.s_at_height(z)
        p, _, r = t.at(s)
        fade = math.exp(-max(0.0, p.z) / max(t.spec.flare_height, 1e-3))
        swell = 0.65 * math.cos(lobes[0] * a) + 0.35 * math.cos((lobes[0] + 2) * a + 1.3) if lobes[0] else 0.0
        rr = r * (1.0 + lobes[1] * fade * swell)
        return p, rr

    ux = Vector((math.cos(az), math.sin(az), 0.0))
    uy = Vector((-math.sin(az), math.cos(az), 0.0))
    # LOD1's coarser tube lies inside the true circle; lift the patch more there
    lift_edge = 0.055 if lod == 0 else 0.09
    lift_mid = 0.015 if lod == 0 else 0.05
    centre = None
    grid = []
    for ri in range(rings + 1):
        f = ri / rings
        ring = []
        for k in range(ring_n if ri else 1):
            th = TAU * k / ring_n
            dx, dz = math.cos(th) * f * wid * 0.5, math.sin(th) * f * hgt * 0.5
            # the arc length across the trunk is dx: angle = dx / radius
            z = z0 + dz
            p, rr = surface(z, az)
            ang = az + dx / max(rr, 0.1)
            p, rr = surface(z, ang)
            out = Vector((math.cos(ang), math.sin(ang), 0.0))
            pos = Vector((p.x, p.y, z)) + out * (rr + lift_mid + (lift_edge - lift_mid) * f ** 2)
            u = 0.5 + dx / wid
            v = 0.5 + dz / hgt
            ring.append(m.v(pos))
            ring[-1] = (ring[-1], (u, v))
        grid.append(ring)
    c0 = grid[0][0]
    for ri in range(1, rings + 1):
        prev, cur = grid[ri - 1], grid[ri]
        for k in range(ring_n):
            k1 = (k + 1) % ring_n
            if ri == 1:
                a, b, c = c0, cur[k], cur[k1]
                m.tri(a[0], b[0], c[0], (a[1], b[1], c[1]), "hollow")
            else:
                a, b, c, d = prev[k], prev[k1], cur[k1], cur[k]
                m.quad(a[0], d[0], c[0], b[0], (a[1], d[1], c[1], b[1]), "hollow")


_scar_quads = tr._scar_quads


def scar_quads(m, tree, lod, key="leaves"):
    _scar_quads(m, tree, lod, key)
    if lod <= 1:
        hollow_quads(m, tree, lod)


tr._scar_quads = scar_quads


# ---------------------------------------------------------------- the trees

def limb_len(t):
    """The primary limbs' envelope over the trunk's crown span: the low ones longest (they sweep out level), the top
    ones shorter but steeper."""
    return 1.0 - 0.18 * t


def secondary_len(t):
    return 1.0 - 0.35 * t


def oak(trunks, limbs=7, reach=1.0, crown=0.42, favor=None, inner=0.0, budget=8000, twig_density=0.5, sag=1,
        card_scale=(1.0, 1.25), angle=(76.0, 26.0), limb_len=(9.5, 13.0), grav=0.1, droop=0.04, up_boost=0.0,
        secondaries=0.8, spacing=0.3, cluster_spacing=1.6, split=0.05, stubs=(2, 3), top_secondary=1.2):
    """A wolf oak's TreeSpec. Each trunk (tr.Trunk, one or a pair) is short and stout and gives out among `limbs`
    huge limbs from `crown` of its height up: the lowest nearly level (82 degrees off the trunk) and sweeping 10 to
    13 m, the highest climbing steeply (32 degrees) and a little shorter; they arch up (`grav`) and sag at the ends
    (`droop`), fork now and then, and carry level 2, the big secondary limbs (`secondaries` per metre) that fill the dome
    out and up, then level 3, leafy branches thick with cards. `sag` limbs per trunk droop to rest on the ground."""
    prim = tr.Level(count=limbs, span=(crown, 1.0), length=(limb_len[0] * reach, limb_len[1] * reach), shape=limb_len_fn,
                    angle=angle[0], angle_tip=angle[1], angle_vary=8.0, radius=0.85, radius_length=0.35, radius_max=0.6,
                    tip_radius=0.05, taper=0.55, step=0.5, gravitropism=grav, droop=droop, wander=0.22, outward=0.12,
                    lift=up_boost, split=split, split_angle=30.0, favor=favor, inner=inner, floor=0.6, sides=(7, 5, 4),
                    seg=(2.4, 3.2, 4.0), min_len=(0.0, 0.0, 0.0))
    sec = tr.Level(per_meter=secondaries, span=(0.15, 0.97), length=(3.8 * top_secondary, 7.6 * top_secondary),
                   shape=secondary_len, angle=52.0, angle_tip=38.0, angle_vary=10.0, planar=0.1, outward=0.3,
                   radius=0.5, radius_length=0.45, radius_max=0.14, tip_radius=0.012, taper=0.8, step=0.4,
                   gravitropism=0.07, droop=0.07, wander=0.32, floor=1.0, sides=(4, 3, 3), seg=(3.4, 4.0, 6.0),
                   min_len=(0.0, 2.0, 4.0))
    leafy = tr.Level(per_meter=twig_density, span=(0.12, 0.98), length=(1.3, 2.7), shape="tapered", angle=62.0,
                     angle_tip=46.0, angle_vary=12.0, planar=0.3, outward=0.3, radius=0.42, radius_length=0.5,
                     radius_max=0.03, tip_radius=0.005, taper=1.0, step=0.4, gravitropism=0.05, droop=0.35, wander=0.45,
                     floor=1.0, sides=(3, 3, 0), seg=(1.6, 3.0, 9.0), min_len=(0.0, 1.8, 99.0))
    dead = tr.Level(count=stubs, span=(0.1, crown + 0.1), length=(0.3, 0.9), angle=75.0, angle_vary=10.0,
                    radius=0.2, radius_length=0.0, radius_max=0.15, tip_radius=0.07, broken=True, step=0.1,
                    droop=0.0, gravitropism=0.25, wander=0.2, floor=0.8, sides=(10, 6, 0), seg=(0.5, 1.2, 1.0), min_length=0.2)
    sag_lv = None
    if sag:
        sag_lv = tr.Level(count=sag, span=(crown, crown + 0.22), length=(6.0 * reach, 7.5 * reach), shape="flat",
                          angle=80.0, angle_vary=5.0, radius=0.8, radius_length=0.3, radius_max=0.5, tip_radius=0.06,
                          taper=0.6, step=0.5, gravitropism=0.0, droop=0.45, wander=0.15, outward=0.1, floor=0.35,
                          sides=(9, 6, 4), seg=(1.5, 2.6, 4.0), min_len=(0.0, 0.0, 0.0), favor=favor)
    spec = tr.TreeSpec(
        trunks=trunks, levels=[prim, sec, leafy], stubs=dead, budget=budget, bark_budget=3600,
        foliage=tr.Foliage(levels={3: (0.12, 1.0), 2: (0.3, 1.0)}, trunk_top=None, spacing=spacing, cells=SPRAYS,
                           scale=card_scale, hang=0.1, spread=0.35, out=0.5, face=0.4, up=0.55, roll=35.0, bend=0),
        cluster=tr.Foliage(levels={2: (0.35, 1.0)}, trunk_top=None, spacing=cluster_spacing, cells=CLUSTERS,
                           scale=(0.85, 1.15), hang=0.2, spread=0.3, out=0.5, face=0.5, up=0.5, roll=25.0, bend=20.0),
        bark_key=bark_key, bark_uv=UV, ground_v=0.1, lod_share=(0.45, 0.2))
    spec.sag = sag_lv
    return spec


limb_len_fn = limb_len


def trunk(**kw):
    base = dict(flare=0.55, flare_height=0.9, lobes=(7, 0.2), taper=0.4, tip_radius=0.25, wander=0.12,
                sides=(16, 10, 8), seg=(0.7, 1.4, 2.4), rings=((0.0, 0.2, 0.5, 0.9, 1.5, 2.2), (0.0, 0.6), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeWolfOakSeed in game): a stout little stem about 0.7 m tall with a
    couple of short side shoots, hung with single lobed leaves (the atlas's Leaf cell), all twig bark."""
    shoots = tr.Level(count=(2, 4), span=(0.35, 0.85), length=(0.08, 0.2), shape="tapered", angle=55.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0009, step=0.03,
                      gravitropism=0.3, droop=0.25, wander=0.4, floor=0.02, sides=(4, 3, 0),
                      seg=(0.05, 0.1, 9.0), min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.7, radius=0.0065, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0016,
                         lean=(0.04, -0.03), bow=0.3, wander=0.03, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.8, 1.1), hang=0.2, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.1, cells=(LEAF,), scale=(0.9, 1.2),
                           hang=0.2, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        bark_key=lambda br, s, r, z: "twig", bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # The landmark: about 22 m tall, 25 m across; one hollow
    ("WolfOak01", 3, lambda: oak([trunk(height=9.0, radius=1.0, lean=(0.3, 0.2), bow=0.1)], limbs=11, sag=1, budget=9200, twig_density=0.42),
     dict(hollow=(0, 1.45, -1.9, 0.78, 1.3))),
    # Smaller and leaning: about 17 m, 20 m across, the crown fuller on the lee side
    ("WolfOak02", 11, lambda: oak([trunk(height=6.2, radius=0.8, lean=(1.8, 0.7), bow=0.35, wander=0.16)], limbs=7,
                                  reach=0.8, favor=((1.0, 0.35), 0.25), crown=0.4, sag=1, limb_len=(12.0, 14.5)),
     dict(hollow=None)),
    # A split-trunk twin: two stout trunks from one base, about 19 m
    ("WolfOak03", 23, lambda: oak([trunk(height=8.4, radius=0.72, base=(0.4, 0.0), lean=(1.5, 0.3), bow=0.3,
                                         sides=(14, 9, 7)),
                                   trunk(height=7.8, radius=0.7, base=(-0.4, 0.1), lean=(-1.4, -0.4), bow=0.3,
                                         sides=(14, 9, 7))],
                                  limbs=5, reach=0.9, crown=0.4, inner=0.45, sag=1, budget=8600, limb_len=(12.0, 14.0)),
     dict(hollow=(0, 1.3, -2.2, 0.6, 1.0))),
    # A younger tree: about 11 m, rounder, a trunk still only 35 cm
    ("WolfOak04", 41, lambda: oak([trunk(height=3.2, radius=0.34, lean=(-0.2, 0.3), bow=0.2, flare=0.4,
                                         lobes=(6, 0.12), tip_radius=0.1, sides=(12, 8, 6))],
                                  limbs=7, reach=0.42, crown=0.4, budget=6000, twig_density=1.7, sag=0,
                                  card_scale=(0.8, 1.05), spacing=0.4, cluster_spacing=1.1, limb_len=(10.0, 12.5),
                                  secondaries=0.7, angle=(70.0, 28.0), stubs=(1, 2)),
     dict(hollow=None)),
    ("WolfOakSapling", 61, sapling, dict(hollow=None, plain=True)),
]


# ---------------------------------------------------------------- trunks.txt: the trunk and the low thick limbs

def write_trunks_ext(path, name, tree, limb_height=4.5, min_r=0.12, step=0.5):
    """The trunk's chain (the first line) to 80 % of its length, and a line for each limb's stretch below
    `limb_height` m that is still thicker than `min_r`, so a player can't walk into the big low limbs or the ones
    resting on the ground (the limbs of a vanilla tree can be clipped into, a trunk never)."""
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
    # sort is stable per name, so the trunk's line(s) stay ahead of the limbs'
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- previews of a big tree

def big_previews(name, obj, size, figure, samples=40):
    """Wide views for a 25 m crown: the whole tree from 62 m, from 105 m, and from 14 m (under it), each from the
    front and at an angle."""
    low = name.lower()
    saved = tr._only([obj])
    tr.place(figure, -2.4, -2.0)
    h = size[0]
    for tag, loc, tgt, lens, res in (
            ("w", (4.0, -62.0, h * 0.42), (0.0, 0.0, h * 0.44), 35, (1400, 900)),
            ("far", (-20.0, -105.0, 4.0), (0.0, 0.0, h * 0.4), 35, (1400, 900)),
            ("under", (-7.0, -13.0, 1.7), (0.0, 0.0, 8.0), 24, (1400, 900)),
            ("side", (60.0, 12.0, h * 0.42), (0.0, 0.0, h * 0.44), 35, (1400, 900))):
        tr._shot(low + "_" + tag, loc, tgt, os.path.join(PREVIEWS, "%s_%s.png" % (low, tag)), lens=lens, res=res,
                 samples=samples)
    tr._restore(saved)


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """WolfOakSeed_Icon.png (160 x 160, in Trees/WolfOak; gen_nature.py copies it into the mod's item icons), drawn
    like vanilla's tree seeds: an acorn (a glossy brown nut in a scaly cup) lying across an oak leaf, under zkit's
    icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.5, shade=0.25)
    mat, g = tr.tk.new_material("AcornNutSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Glossy chestnut brown, paler and greener toward the cup, fine dark stripes down it
    col = g.mix(g.ramp(s, 0.85, 0.2), (0.28, 0.12, 0.035), (0.5, 0.31, 0.1))
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.35, 0.75), col, (0.2, 0.085, 0.028))
    tr.tk.finish(mat, g, col, 0.0, 0.32, g.bump(g.noise(300.0, detail=4.0), 0.12, 0.0003))
    mats["nut"] = mat
    mat, g = tr.tk.new_material("AcornCupSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Grey-brown cup of overlapping scales: a bumpy cobbled look
    cobble = g.noise(70.0, detail=2.0)
    col = g.mix(g.ramp(cobble, 0.35, 0.65), (0.17, 0.12, 0.075), (0.36, 0.28, 0.18))
    tr.tk.finish(mat, g, col, 0.0, 0.75, g.bump(g.ramp(g.noise(55.0, detail=1.0), 0.3, 0.7), 0.7, 0.0012))
    mats["cup"] = mat

    m = tr.Mesh()
    # The leaf, long axis toward the upper left, its stalk bottom right
    end = Vector((0.04, 0.012, -0.04))
    tr.twig(m, [Vector((0.048, 0.012, -0.05)), end], [0.0011, 0.001], "petiole", 5)
    oak_leaf(m, end, Vector((-0.62, 0.0, 0.78)), Vector((0.1, -1.0, 0.2)), 0.1, random.Random(8), rows=42)
    # The acorn: a nut 2.4 cm long and 1.3 wide lying at an angle in front, tip lower left, its cup at the upper right
    axis = Vector((-0.55, 0.0, -0.35)).normalized()
    base = Vector((0.012, -0.03, 0.012))
    nut_pts, nut_r = [], []
    for i in range(13):
        f = i / 12
        nut_pts.append(base + axis * (0.024 * f))
        # a rounded egg that ends in a small point: full near 35 %, a nipple at the tip
        rr = 0.0068 * (math.sin(math.pi * min(1.0, 0.04 + 0.96 * (1 - f) ** 0.8)) ** 0.6) * (0.35 + 0.65 * smooth(0.0, 0.4, 1 - f))
        nut_r.append(max(rr, 0.0006))
    nut_r[-1] = 0.0005
    tr.twig(m, nut_pts, nut_r, "nut", 14)
    # the cup: a squat bowl round the nut's top end, scaly
    cup_pts, cup_r = [], []
    for i in range(7):
        f = i / 6
        cup_pts.append(base - axis * (0.0095 - 0.0145 * f))
        cup_r.append(0.0045 + 0.0036 * math.sin(math.pi * min(1.0, 0.1 + 0.9 * f) * 0.9))
    cup_r[0] = 0.0016
    cup_r[-1] = 0.0072
    tr.twig(m, cup_pts, cup_r, "cup", 14)
    # a small stem at the cup's end
    tr.twig(m, [base - axis * 0.0112, base - axis * 0.0165], [0.0011, 0.0009], "petiole", 5)
    obj = m.build("WolfOakSeedIcon", mats)
    obj.scale = (6.5, 6.5, 6.5)
    obj.location = (-0.06, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.78)
    tr.tk.icon(cam, os.path.join(FOLDER, "WolfOakSeed_Icon.png"), hide=())
    print("[wolf_oak] icon written")


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
    mats = {"bark": tr.textured("WolfOakBark", paths("WolfOakBark")),
            "limb": tr.textured("WolfOakBarkLimb", paths("WolfOakBarkLimb")),
            "twig": tr.textured("WolfOakBarkTwig", paths("WolfOakBarkTwig")),
            "hollow": tr.textured("WolfOakBarkHollow", paths("WolfOakBarkHollow")),
            "leaves": tr.textured("WolfOakLeaves", paths("WolfOakLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    for name, seed, make, extra in VARIANTS:
        if ONLY and name not in ONLY:
            continue
        HOLLOW.pop(name, None)
        if extra.get("hollow"):
            HOLLOW[name] = extra["hollow"]
        spec = make()
        if STEPS == "skeleton" and spec.foliage is not None:
            spec.foliage = None
            spec.cluster = None
        tree = grow_oak(spec, seed, name, getattr(spec, "sag", None))
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        if extra.get("plain"):
            tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        else:
            write_trunks_ext(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[wolf_oak] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
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
        tr.preview_bark("wolf_oak01", lods[0], PREVIEWS, figure)
        tr.preview_lods("wolf_oak01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
        tr.preview_grove("wolf_oak", [b[2][0] for b in big], PREVIEWS, figure,
                         spots=[(-26.0, 8.0), (0.0, 30.0), (26.0, 4.0), (0.0, -4.0)], distance=90.0)
    if STEPS == "all":
        make_icon()
    print("[wolf_oak] done")


main()
