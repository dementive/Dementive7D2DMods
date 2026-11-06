"""Blue spruce (Picea pungens, the Colorado spruce), on treekit.py (birch.py is the worked example; TREES.md has the
rules; subalpine_fir.py and douglas_fir.py the other conifers).

A strict pyramid: whorls of five stiff, level limbs in tiers right down to the ground, branchlets hanging from them;
stiff sharp needles 2 to 3 cm long standing all round the twig, silver- to steel-blue with a waxy bloom (the point of
the tree); pale brown papery cones 8 cm long hanging near the top; grey-brown bark in small scaly plates between
shallow furrows.

    blender -b --factory-startup --python trees/blue_spruce.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps as
birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`. It writes Trees/BlueSpruce/ (bark and
needle textures, BlueSpruce01..04 and BlueSpruceSapling with their impostors, BlueSpruceSeed_Icon.png), the BlueSpruce
lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "BlueSpruce")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# BlueSpruceBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii, drawn at its size on
# BlueSpruce01's 28 cm trunk (about 23 px per cm). BlueSpruceBarkTwig: 512 x 1024, the orange-grey twigs and young
# limbs under 2.5 cm radius, with the little pegs the needles grew from.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 28.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.3
# Mean albedo (sRGB graded space): a warm dark grey-brown, a touch purple; needles a steel blue (LEAF_MEAN is in the
# same space as the other firs': Douglas 60,77,54)
BARK_MEAN = (100, 92, 86)
LEAF_MEAN = (62, 84, 92)
TWIG_R = 0.025
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def spruce_bark(r, h=H, w=W, px=PX):
    """Blue spruce bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: thin
    ridges 5 to 9 cm across and 30 cm tall between shallow dark furrows, every ridge broken into small thin scales 2
    to 4 cm across, each its own shade of grey-brown, their lower edges curling away from the trunk and the cracks
    between them dark, a few showing the red-brown inner bark; pale lichen crusts."""
    cm = px
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    warp = ((tr.fbm(r, h, w, (2.5 * cm, 8 * cm), 3) - 0.5) * 1.6 * cm,
            (tr.fbm(r, h, w, (2.5 * cm, 8 * cm), 3) - 0.5) * 5.0 * cm)
    ridge_edge, ridge, _, _ = tr.cells(r, h, w, 7 * cm, 4.5, warp)
    swarp = ((tr.fbm(r, h, w, (1.5 * cm, 1.5 * cm), 3) - 0.5) * 0.9 * cm,
             (tr.fbm(r, h, w, (1.5 * cm, 1.5 * cm), 3) - 0.5) * 0.9 * cm)
    sedge, sidx, sy, _ = tr.cells(r, h, w, 2.8 * cm, 1.6, swarp)
    n = sidx.max() + 1
    sshade, sopen, sred = r.random(n)[sidx], r.random(n)[sidx], r.random(n)[sidx]
    rshade = r.random(ridge.max() + 1)[ridge]
    mottle = tr.fbm(r, h, w, (3 * cm, 6 * cm), 4)
    fine = tr.fbm(r, h, w, (0.5 * cm, 0.5 * cm), 3)
    grit = tr.fbm(r, h, w, (0.08 * cm, 0.08 * cm), 2)
    streak = tr.fbm(r, h, w, (0.3 * cm, 3 * cm), 3)

    wobble = tr.fbm(r, h, w, (1.0 * cm, 4 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.25 + 0.45 * wobble) * cm, ridge_edge)
    body = tr.smoothstep(0.0, 1.0 * cm, ridge_edge)
    gap = (0.05 + 0.12 * sopen) * cm
    crack = (1.0 - tr.smoothstep(gap * 0.4, gap + 0.06 * cm, sedge)) * body
    lift = np.clip((sy - Y) / (1.2 * cm), -1.0, 1.0) * 0.5 + 0.5
    lift = lift * tr.smoothstep(0.0, 0.3 * cm, sedge) * body

    col = tr.mix((0.3, 0.27, 0.25), (0.6, 0.56, 0.53),
                 0.3 * sshade + 0.15 * rshade + 0.2 * mottle + 0.12 * fine + 0.1 * grit + 0.1 * streak)
    # Some scales a warmer purple-brown, a few flaked to the red-brown inner bark
    warm = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (10 * cm, 16 * cm), 3))
    col = tr.mix(col, col * np.array((1.1, 0.96, 0.88)), warm[..., None] * 0.7)
    inner = tr.mix((0.4, 0.2, 0.13), (0.5, 0.28, 0.18), sshade)
    col = tr.mix(col, inner, ((sred > 0.93) * body)[..., None] * 0.85)
    col = tr.mix(col, col * 1.18, (lift * body * 0.55))  # curling edges catch light
    lichen = (tr.smoothstep(0.78, 0.9, tr.fbm(r, h, w, (1.3 * cm, 1.3 * cm), 4))
              * tr.smoothstep(0.5, 0.75, tr.fbm(r, h, w, (14 * cm, 18 * cm), 3)) * body)
    col = tr.mix(col, (0.52, 0.57, 0.48), lichen * 0.45)
    col = tr.mix(col, (0.17, 0.15, 0.14), np.maximum(furrow, crack * 0.85))

    height = (1.4 * body + 0.5 * mottle + 0.4 * fine + 0.3 * grit + 0.25 * streak + 0.9 * lift + 0.35 * sshade * body
              + 0.2 * lichen - 1.9 * furrow - 0.9 * crack)
    rough = 0.86 + 0.06 * (grit - 0.5) + 0.05 * lichen
    occ = tr.cavity(height, 4.0 * RELIEF, 0.25)
    col = col * (0.74 + 0.26 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Limbs and twigs: orange-grey, finely ridged along, with the raised pegs (pulvini) the needles grew on, in
    diagonal rows."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 2 * cm), 4)
    col = tr.mix((0.26, 0.2, 0.16), (0.44, 0.37, 0.3), tone)
    pegs = np.zeros((h, w))
    for _ in range(int(area * 1.4)):
        tr.stamp_lens(pegs, r.uniform(0, w), r.uniform(0, h), r.uniform(0.12, 0.2) * cm, r.uniform(0.07, 0.11) * cm,
                      1.0, ends=0.6)
    col = tr.mix(col, (0.5, 0.42, 0.34), pegs * 0.45)
    col = tr.mix(col, (0.12, 0.09, 0.07), np.clip(tr.blur(pegs, 2.5) - pegs, 0.0, 1.0) * 0.5)
    height = 0.4 * tone + 1.1 * tr.blur(pegs, 1.2)
    return np.clip(col, 0.0, 1.0), height, 0.65 + 0.1 * tone, tr.cavity(height, 3.0, 0.2)


def make_bark():
    r = np.random.default_rng(29)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = spruce_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("BlueSpruceBark", col, height, rough, occ, RELIEF)
    save("BlueSpruceBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the needle atlas
#
# 2048 square, as douglas_fir.py's: four hanging needle sprays (512 x 640), one with cones, two cluster cells
# (1024 x 1280) of a limb's end for LOD2, one small sprig (128 square) for the seedling.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.5, 0.62))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.5, 1.9))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.15, 0.15), pad=8)
    return atlas


def needle(m, base, way, normal, length, width, rv, age):
    """One stiff needle from `base` along `way`: straight, narrow, held at its width nearly to a sharp point."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = nl - d * nl.dot(d)
    nl = nl.normalized() if nl.length > 1e-6 else d.orthogonal().normalized()
    side = nl.cross(d)
    rows = []
    for s, wf in ((0.0, 0.7), (0.3, 1.0), (0.8, 0.8), (1.0, 0.12)):
        c = Vector(base) + d * (s * length)
        rows.append((m.v(c - side * (wf * width * 0.5), leaf=(-1.0, s, rv), age=age),
                     m.v(c + side * (wf * width * 0.5), leaf=(1.0, s, rv), age=age)))
    uv = ((0, 0),) * 4
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        m.quad(a0, a1, b1, b0, uv, "leaf")


def needled(m, rnd, pts, radius, per_m=950, length=(0.02, 0.03)):
    """A twig with stiff needles all round it (a bottlebrush), pointing forward along it at 35 to 60 degrees, more
    of them toward the spray's sides and top, shorter toward the tip, the new growth there bluer."""
    tr.twig(m, pts, [radius * (1.0 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 4)
    tw = tr.Branch(pts, [radius] * len(pts))
    n = max(4, int(tw.length * per_m))
    up = Vector((0.0, 0.0, 1.0))
    for i in range(n):
        f = (i + rnd.random()) / n
        p, tan, _ = tw.at(f)
        lat = Vector((-tan.y, tan.x, 0.0))
        lat = lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))
        side = 1.0 if i % 2 else -1.0
        # All the way round the twig, fewer underneath
        phi = rnd.uniform(-1.9, 2.3)
        radial = (lat * side * math.cos(phi) + up * math.sin(phi)).normalized()
        theta = math.radians(rnd.uniform(35.0, 62.0))
        way = tan * math.cos(theta) + radial * math.sin(theta)
        L = rnd.uniform(*length) * (1.0 - 0.4 * max(0.0, f - 0.8) / 0.2)
        needle(m, p + radial * radius * 0.8, way, up + radial * 0.3, L, 0.0027, rnd.random(), f)


def cone(m, rnd, top, way, length, key="cone"):
    """A blue spruce cone hanging from `top` along `way`, `length` long (6 to 10 cm): a long cylinder blunt at both
    ends of loosely overlapping thin papery scales, each wide with a wavy, ragged lip, spiralling round a core and
    pointing toward the cone's tip."""
    d = Vector(way).normalized()
    _, u, v = tr.basis(d)
    core = [top + d * (length * i / 8) for i in range(9)]
    shape = [0.35, 0.8, 0.95, 1.0, 1.0, 0.95, 0.8, 0.55, 0.2]
    tr.twig(m, core, [0.07 * length * k for k in shape], key, 8)
    tr.twig(m, [top - d * 0.015, top], [0.0016, 0.0019], "twig", 5)
    count = 110
    for i in range(count):
        f = 0.05 + 0.9 * (i + rnd.uniform(-0.3, 0.3)) / count
        a = i * tr.GOLDEN + rnd.uniform(-0.15, 0.15)
        out = u * math.cos(a) + v * math.sin(a)
        k = float(np.interp(f, np.linspace(0.0, 1.0, len(shape)), shape))
        base = top + d * (f * length) + out * (0.07 * length * k)
        sl = length * 0.2 * (0.7 + 0.3 * k)
        tr.blade(m, base, (out * 0.45 + d * 0.89).normalized(), out, sl, sl * 1.1,
                 lambda s: math.sin(math.pi * min(1.0, 0.1 + 0.9 * s)) ** 0.5 * (1.0 + 0.1 * math.sin(s * 40.0)),
                 key, fold=0.1, arch=-0.1, rows=4, rnd_value=rnd.random())


def leaf_materials(shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): needles ("leaf"), twig, cone."""
    mat, g = tr.tk.new_material("SpruceNeedleSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    age = g.node("ShaderNodeAttribute", attribute_name="age").outputs["Fac"]
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Steel blue with a grey waxy bloom, needle to needle bluer or greener; this year's growth at the tips silvery
    base = g.mix(g.ramp(rv, 0.1, 0.9), (0.032, 0.085, 0.1), (0.05, 0.1, 0.125))
    base = g.mix(g.ramp(rv, 0.82, 1.0), base, (0.06, 0.08, 0.075))
    col = g.mix(g.math("MULTIPLY", g.ramp(age, 0.66, 0.92), 0.7), base, (0.14, 0.2, 0.25))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.5, 1.0), 0.12), col, (0.13, 0.17, 0.2))
    if shade:
        col = g.mix(shade, col, (0.012, 0.03, 0.035))
    rough = g.mixf(back, 0.4, 0.55)
    tr.tk.finish(mat, g, col, 0.0, rough)
    leaf = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("SpruceTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.08, 0.055, 0.04), (0.17, 0.12, 0.08))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    twig = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("SpruceConeSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Pale papery tan-brown, the scale lips lighter, each scale's base in shadow, ragged edges a little darker
    col = g.mix(g.ramp(rv, 0.05, 0.95), (0.2, 0.115, 0.055), (0.32, 0.2, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.55, 1.0), 0.6), col, (0.5, 0.36, 0.2))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.35, 0.0), 0.6), col, (0.07, 0.04, 0.02))
    tr.tk.finish(mat, g, col, 0.0, 0.7, g.bump(g.noise(300.0, detail=3.0), 0.2, 0.0003))
    cone_mat = tr.signals(mat, col, 0.7)
    return {"leaf": leaf, "twig": twig, "petiole": twig, "cone": cone_mat}


def spray(m, rnd, start, direction, length, cones=0, order=2):
    """A stiff spruce branchlet hanging from `start`: a main twig (little bend, stiff) with side twigs alternately left
    and right at 50 to 70 degrees, shorter toward the tip, theirs again (`order` 2), every one a bottlebrush of
    needles; `cones` cones hanging below it."""
    pts = tr.bend_path(start, direction, length, rnd.uniform(0.2, 0.45), steps=12, down=(0.0, -1.0, 0.0))
    needled(m, rnd, pts, 0.0028 if order == 2 else 0.002)
    tw = tr.Branch(pts, [0.003] * len(pts))
    f, side = rnd.uniform(0.08, 0.14), rnd.choice((-1, 1))
    while f < 0.86 and order > 0:
        p, tan, _ = tw.at(f)
        d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(45.0, 68.0))
        d.z += rnd.uniform(-0.1, 0.1)
        L = length * rnd.uniform(0.3, 0.45) * (1.0 - 0.55 * f)
        if L > 0.04:
            spray(m, rnd, p, d, L, 0, order - 1)
        f += rnd.uniform(0.07, 0.11)
        side = -side
    for _ in range(cones):
        p, tan, _ = tw.at(rnd.uniform(0.15, 0.4))
        cone(m, rnd, p + Vector((0.0, 0.0, -0.004)), Vector((rnd.uniform(-0.25, 0.25), -1.0, rnd.uniform(-0.2, 0.0))),
             rnd.uniform(0.07, 0.095))


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(53)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.1, 0.3), -1.0, 0.0)), rnd.uniform(0.44, 0.52),
              cones=(0, 0, 1, 2)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        m = tr.Mesh()
        side = (1, -1)[ci]
        stem = tr.bend_path(Vector(), Vector((side * 0.35, -1.0, 0.05)), rnd.uniform(1.3, 1.5), 0.3, steps=12,
                            down=(0.0, -1.0, 0.0))
        tr.twig(m, stem, [0.011 * (1.0 - 0.7 * i / (len(stem) - 1)) for i in range(len(stem))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        br = tr.Branch(stem, [0.01] * len(stem))
        for j in range(16):
            f = 0.04 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / 16
            p, tan, _ = br.at(f)
            c = sprays[rnd.randrange(len(sprays) - 2)].copy()  # no cones in the clusters
            tr.tk.link(c)
            spin = (j % 2 * 2 - 1) * rnd.uniform(35.0, 70.0)
            rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-35, 35)), 4, "Y")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-15, 15)), 4, "X"))
            c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.8, 1.05) * (1.0 - 0.3 * f), 4)
            objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    m = tr.Mesh()
    spray(m, random.Random(5), Vector(), Vector((0.1, -1.0, 0.0)), 0.13, 0, 1)
    sprig = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [sprig])
    if render:
        atlas.render(atlas.cells[LEAF], [sprig])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "BlueSpruceLeaves")
    atlas.preview(os.path.join(PREVIEWS, "blue_spruce_atlas.png"))
    for c in atlas.cells.values():
        print("[blue_spruce] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("BlueSpruceLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def pyramid(t):
    """The crown's envelope up the trunk: a strict cone, the lowest limbs longest, tapering in a straight line, the
    very lowest tier a little shortened by shade."""
    return (1.0 - 0.94 * t) * (0.88 + 0.12 * min(1.0, t * 8.0))


def spruce(trunks, crown=0.05, reach=1.0, whorl_gap=0.9, budget=11000, stubs=(0, 3), card_scale=(1.7, 2.2),
           angle=(90.0, 72.0), spacing=0.075):
    """A blue spruce's TreeSpec: `trunks`, whorls of five stiff, level limbs every `whorl_gap` m from `crown` of the
    height (0: to the ground) up, rising a little toward the top; `reach` scales them; branchlets hang off both sides
    of every limb; needle sprays all along them."""
    limbs = tr.Level(per_meter=5.0 / whorl_gap, whorl=5, span=(crown, 0.985), length=(3.3 * reach, 4.3 * reach),
                     shape=pyramid, angle=angle[0], angle_tip=angle[1], angle_vary=5.0, radius=0.2, radius_length=0.7,
                     radius_max=0.06, tip_radius=0.004, step=0.3, gravitropism=0.1, droop=0.22, wander=0.1,
                     floor=0.12, sides=(3, 3, 3), seg=(1.6, 2.4, 3.2), min_len=(0.0, 0.4, 1.5))
    branchlets = tr.Level(per_meter=1.2, min_length=0.35, span=(0.12, 0.96), length=(0.45 * reach ** 0.5, 1.1 * reach ** 0.5),
                          shape="tapered", angle=62.0, angle_tip=48.0, angle_vary=9.0, planar=0.55, radius=0.5,
                          radius_length=0.5, radius_max=0.012, tip_radius=0.002, step=0.15, gravitropism=0.04,
                          droop=0.55, wander=0.25, sides=(3, 0, 0), seg=(1.0, 9.0, 9.0), min_len=(0.0, 99.0, 99.0))
    stubs_lv = tr.Level(count=stubs, span=(0.02, 0.2), length=(0.06, 0.3), angle=85.0, angle_vary=8.0,
                        radius=0.12, radius_length=0.4, radius_max=0.025, tip_radius=0.008, broken=True, step=0.06,
                        droop=0.3, wander=0.15, sides=(6, 4, 0), seg=(0.3, 1.0, 1.0), min_length=0.04)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs, branchlets], stubs=stubs_lv, budget=budget, bark_budget=4500,
        foliage=tr.Foliage(levels={2: (0.0, 1.0), 1: (0.0, 1.0)}, trunk_top=(0.9, 1.0), spacing=spacing,
                           cells=SPRAYS, scale=card_scale, hang=0.3, spread=0.3, out=0.65, face=0.4, up=0.5,
                           roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.12, 1.0)}, trunk_top=(0.85, 1.0), spacing=0.55, cells=CLUSTERS,
                           scale=(0.9, 1.15), hang=0.2, spread=0.25, out=0.7, face=0.5, up=0.5, roll=15.0,
                           bend=15.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.3, flare_height=0.4, lobes=(6, 0.1), taper=1.0, tip_radius=0.006, wander=0.03,
                sides=(14, 9, 6), seg=(0.9, 1.8, 3.2), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeBlueSpruceSeed in game): a stem about 0.5 m tall with three
    whorls of short stiff twigs, hung with small needle sprigs (the atlas's Leaf cell)."""
    shoots = tr.Level(per_meter=9.0, whorl=5, span=(0.25, 0.92), length=(0.07, 0.15), shape="tapered", angle=78.0,
                      angle_tip=60.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0008, step=0.03,
                      gravitropism=0.1, droop=0.25, wander=0.2, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.03, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.5, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0015,
                         lean=(0.02, 0.01), bow=0.2, wander=0.01, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.55, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.7, 1.0), hang=0.1, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.09, cells=(LEAF,), scale=(0.9, 1.1),
                           hang=0.1, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # Mature, about 20 m: a strict pyramid of level tiers, the lowest limbs 1.3 m off the snow
    ("BlueSpruce01", 5, lambda: spruce([trunk(height=20.0, radius=0.3, lean=(0.2, -0.15), bow=0.1)], crown=0.06,
                                       budget=11000)),
    # Taller and narrower, about 22 m: short limbs, closer tiers
    ("BlueSpruce02", 17, lambda: spruce([trunk(height=22.0, radius=0.28, lean=(-0.3, 0.3), bow=0.1)], crown=0.07,
                                        reach=0.68, whorl_gap=0.8, budget=11000)),
    # Short and broad, about 15 m: limbs to the ground
    ("BlueSpruce03", 29, lambda: spruce([trunk(height=15.0, radius=0.3, lean=(0.3, 0.2), bow=0.1, flare=0.35)],
                                        crown=0.0, reach=1.3, whorl_gap=0.85, budget=11000, stubs=(0, 0))),
    # Young, about 8 m, very regular, limbs to the ground
    ("BlueSpruce04", 41, lambda: spruce([trunk(height=8.0, radius=0.1, lean=(0.1, 0.1), bow=0.05, flare=0.25)],
                                        crown=0.0, reach=0.55, whorl_gap=0.55, budget=7000, stubs=(0, 0),
                                        card_scale=(1.4, 1.8))),
    # The seedling a planted seed shows before it grows into BlueSpruce04
    ("BlueSpruceSapling", 59, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """BlueSpruceSeed_Icon.png (160 x 160, in Trees/BlueSpruce; gen_nature.py copies it into the mod's item icons),
    drawn like vanilla's pine cone seed: a long pale brown spruce cone hanging from a blue needle sprig, under zkit's
    icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(shade=0.15)
    rnd = random.Random(3)
    m = tr.Mesh()
    spray(m, rnd, Vector((0.07, 0.05, 0.0)), Vector((-1.0, 0.15, 0.0)), 0.2, 0, 1)
    cone(m, rnd, Vector((0.0, 0.045, 0.02)), Vector((-0.15, -1.0, 0.1)), 0.095)
    obj = m.build("BlueSpruceSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (-0.03, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "BlueSpruceSeed_Icon.png"), hide=())
    print("[blue_spruce] icon written")


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
    mats = {"bark": tr.textured("BlueSpruceBark", paths("BlueSpruceBark")),
            "twig": tr.textured("BlueSpruceBarkTwig", paths("BlueSpruceBarkTwig")),
            "leaves": tr.textured("BlueSpruceLeaves", paths("BlueSpruceLeaves"), cutout=True, translucent=0.25)}
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
        print("[blue_spruce] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("bluespruce01", lods[0], PREVIEWS, figure)
    tr.preview_lods("bluespruce01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("blue_spruce", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[blue_spruce] done")


main()
