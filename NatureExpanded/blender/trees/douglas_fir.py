"""Douglas fir (Pseudotsuga menziesii), on treekit.py (birch.py is the worked example; TREES.md has the rules).

Thick corky bark in long interlacing ridges between deep furrows, grey-brown on the ridges and orange-brown down the
furrows' walls; a single straight leader to the top with whorls of near-horizontal limbs, drooping a little, in a
narrow cone, dead stubs below the live crown; soft flat needles 2 to 3 cm all round the twigs of flat sprays, and
hanging cones with three-pointed bracts poking out between their scales (the seed and its icon).

    blender -b --factory-startup --python trees/douglas_fir.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps as
birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`. It writes Trees/DouglasFir/ (bark and
needle textures, DouglasFir01..04 and the seedling DouglasFirSapling with their impostors, DouglasFirSeed_Icon.png),
the DouglasFir lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "DouglasFir")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# DouglasFirBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (2.5 m on DouglasFir01's
# 80 cm trunk), drawn at its size on that trunk (about 16 px per cm). DouglasFirBarkTwig: 512 x 1024, the smooth grey
# bark of limbs under 4 cm radius, with resin blisters, once round them.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 40.0  # cm: DouglasFir01's trunk 1 m up
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.25
# Mean albedo (sRGB): a dark brown-grey, darker and redder than vanilla's pines; needles a deep green a little bluer
# and darker than vanilla's pine needles (about 78, 86, 68)
BARK_MEAN = (80, 66, 57)
LEAF_MEAN = (60, 77, 54)
TWIG_R = 0.04
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def fir_bark(r, h=H, w=W, px=PX):
    """Old Douglas fir bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm:
    thick corky ridges 5 to 12 cm across, long and interlacing, rounded on top and cracked across into blocks, grey-
    brown and weathered there; between them deep V furrows 2 to 5 cm wide, their walls the cork's fresh orange-brown
    layers, their depths near black."""
    cm = px
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    warp = ((tr.fbm(r, h, w, (4 * cm, 14 * cm), 3) - 0.5) * 3.0 * cm,
            (tr.fbm(r, h, w, (4 * cm, 14 * cm), 3) - 0.5) * 6.0 * cm)
    edge, ridge, _, _ = tr.cells(r, h, w, 9 * cm, 4.5, warp)
    block_edge, block, _, _ = tr.cells(r, h, w, 6 * cm, 1.3, warp)
    del Y, X
    n = ridge.max() + 1
    shade = r.random(n)[ridge]
    wobble = tr.fbm(r, h, w, (2 * cm, 6 * cm), 3)
    width = (1.4 + 1.8 * wobble) * cm  # half the furrow
    # Depth across a furrow: a V from the ridge's rounded shoulder down to the bottom
    depth = 1.0 - tr.smoothstep(0.0, width, edge)
    wall = tr.smoothstep(0.2, 0.5, depth) * (1.0 - tr.smoothstep(0.7, 0.95, depth))
    top = tr.smoothstep(0.0, 1.6 * cm, edge - width * 0.6)
    crack = (1.0 - tr.smoothstep(0.0, (0.2 + 0.3 * wobble) * cm, block_edge)) * top
    crack *= tr.smoothstep(0.5, 0.65, tr.fbm(r, h, w, (6 * cm, 10 * cm), 3))
    cork = tr.fbm(r, h, w, (0.5 * cm, 1.2 * cm), 4)
    grit = tr.fbm(r, h, w, (0.2 * cm, 0.2 * cm), 3)
    mottle = tr.fbm(r, h, w, (3 * cm, 6 * cm), 4)
    # The ridges' corky faces scaled into small flakes and fibres
    flake_edge, _, _, _ = tr.cells(r, h, w, 1.5 * cm, 2.2, warp)
    flake = (1.0 - tr.smoothstep(0.0, 0.1 * cm, flake_edge)) * top * tr.smoothstep(0.35, 0.6, mottle)
    fibre = tr.fbm(r, h, w, (0.25 * cm, 2.0 * cm), 3)
    del block_edge, block, flake_edge

    face = tr.mix((0.27, 0.215, 0.18), (0.46, 0.38, 0.31),
                  0.3 * shade + 0.25 * mottle + 0.2 * cork + 0.15 * fibre + 0.1 * grit)
    inner = tr.mix((0.33, 0.19, 0.12), (0.47, 0.29, 0.18), cork)
    col = tr.mix(inner, face, top)
    col = tr.mix(col, inner, wall * 0.75)
    col = tr.mix(col, (0.09, 0.06, 0.045), tr.smoothstep(0.6, 1.0, depth))
    col = tr.mix(col, (0.15, 0.1, 0.075), np.maximum(crack * 0.8, flake * 0.45))
    lichen = (tr.smoothstep(0.8, 0.9, tr.fbm(r, h, w, (2 * cm, 2 * cm), 4))
              * tr.smoothstep(0.55, 0.8, tr.fbm(r, h, w, (20 * cm, 30 * cm), 3)) * top)
    col = tr.mix(col, (0.5, 0.53, 0.46), lichen * 0.4)

    height = (2.5 * (1.0 - depth) + 0.8 * top + 0.7 * cork + 0.35 * mottle + 0.3 * fibre + 0.3 * grit - 1.2 * crack
              - 0.5 * flake + 0.2 * lichen)
    rough = 0.9 + 0.05 * (grit - 0.5)
    occ = tr.cavity(height, 5.0 * RELIEF, 0.3)
    col = col * (0.7 + 0.3 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Limbs' and young stems' bark at 1 cm radius: smooth grey, a little brown, with raised resin blisters."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 2 * cm), 4)
    col = tr.mix((0.3, 0.28, 0.26), (0.46, 0.44, 0.41), tone)
    blisters = np.zeros((h, w))
    for _ in range(int(area * 0.25)):
        tr.stamp_lens(blisters, r.uniform(0, w), r.uniform(0, h), r.uniform(0.15, 0.35) * cm,
                      r.uniform(0.12, 0.25) * cm, 1.0, ends=0.5)
    col = tr.mix(col, (0.5, 0.47, 0.42), blisters * 0.4)
    grain = tr.fbm(r, h, w, (0.5 * cm, 0.3 * cm), 3)
    height = 0.4 * tone + 0.3 * grain + 1.2 * tr.blur(blisters, 1.5)
    rough = 0.65 + 0.1 * tone
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


def make_bark():
    r = np.random.default_rng(13)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = fir_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    # Furrows several centimetres deep: twice the relief in the normal map that birch-scale detail gets
    save("DouglasFirBark", col, height, rough, occ, RELIEF * 2.2)
    save("DouglasFirBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the needle atlas
#
# 2048 square, as birch's: four flat needle sprays (512 x 640) along the top, two of them with a hanging cone or two;
# two cluster cells (1024 x 1280) of a limb's end thick with sprays, for LOD2; one small sprig (128 square) for the
# seedling, past the decal strip.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.5, 0.62))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.6, 2.0))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.16, 0.16), pad=8)
    return atlas


def needle(m, base, way, normal, length, width, rv, age):
    """One soft flat needle from `base` along `way`: a narrow strip, blunt at its tip, curving a little; "leaf" =
    (across -1..1, along 0..1, a random) and "age" = how near its twig's tip it grew (1: this year's paler growth)."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d))
    nl = nl.normalized() if nl.length > 1e-6 else d.orthogonal().normalized()
    side = nl.cross(d)
    rows = []
    for s, wf in ((0.0, 0.55), (0.35, 1.0), (0.8, 0.9), (1.0, 0.4)):
        c = Vector(base) + d * (s * length) - nl * (0.06 * length * s * s)
        rows.append((m.v(c - side * (wf * width * 0.5), leaf=(-1.0, s, rv), age=age),
                     m.v(c + side * (wf * width * 0.5), leaf=(1.0, s, rv), age=age)))
    uv = ((0, 0),) * 4
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        m.quad(a0, a1, b1, b0, uv, "leaf")


def needled(m, rnd, pts, radius, per_m=950, length=(0.022, 0.032)):
    """A twig along `pts` with needles all round it, most spread out to its sides (a flat spray), pointing forward
    along it, shorter toward its tip, paler on this year's growth there."""
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
        # Round the twig, mostly near its sides (the spray's plane), some above and below
        phi = rnd.gauss(0.0, 0.55)
        radial = (lat * side * math.cos(phi) + up * math.sin(phi)).normalized()
        theta = math.radians(rnd.uniform(45.0, 70.0))
        way = tan * math.cos(theta) + radial * math.sin(theta)
        L = rnd.uniform(*length) * (1.0 - 0.35 * max(0.0, f - 0.8) / 0.2)
        needle(m, p + radial * radius * 0.8, way, up + radial * 0.3, L, 0.0024, rnd.random(), f)


def cone(m, rnd, top, way, length, key="cone", bract="bract"):
    """A Douglas fir cone hanging from `top` along `way`, `length` long: thin rounded scales spiralling round a core,
    each pointing toward the cone's tip, with a three-pointed bract poking out from under it."""
    d = Vector(way).normalized()
    _, u, v = tr.basis(d)
    core = [top + d * (length * i / 8) for i in range(9)]
    shape = [0.25, 0.7, 0.95, 1.0, 0.95, 0.85, 0.68, 0.45, 0.15]
    tr.twig(m, core, [0.26 * length * 0.42 * k for k in shape], key, 8)
    tr.twig(m, [top - d * 0.012, top], [0.0015, 0.0018], "twig", 5)
    count = 70
    for i in range(count):
        f = 0.06 + 0.9 * (i + rnd.uniform(-0.3, 0.3)) / count
        a = i * tr.GOLDEN + rnd.uniform(-0.2, 0.2)
        out = u * math.cos(a) + v * math.sin(a)
        k = float(np.interp(f, np.linspace(0.0, 1.0, len(shape)), shape))
        base = top + d * (f * length) + out * (0.26 * length * 0.4 * k)
        sl = length * 0.2 * (0.6 + 0.4 * k)
        tr.blade(m, base, (out * 0.75 + d * 0.66).normalized(), out, sl, sl * 1.05, lambda s: math.sin(math.pi * min(1.0, s * 0.95)) ** 0.6,
                 key, fold=0.2, arch=-0.2, rows=4, rnd_value=rnd.random())
        # The bract: three thin prongs, the middle one longest, out past the scale's lip
        for prong, size in ((-0.3, 0.7), (0.0, 1.0), (0.3, 0.7)):
            side = out.cross(d).normalized()
            bw = (out * 0.6 + d * 0.8 + side * prong).normalized()
            tr.blade(m, base + out * 0.001, bw, out, sl * 1.15 * size, sl * 0.12, lambda s: 1.0 - s, bract,
                     fold=0.0, arch=0.0, rows=2, rnd_value=0.5)


def leaf_materials(shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): needles ("leaf"), twig, cone, bract."""
    mat, g = tr.tk.new_material("FirNeedleSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    age = g.node("ShaderNodeAttribute", attribute_name="age").outputs["Fac"]
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Deep green, needle to needle a little bluer or yellower; this year's growth at the twigs' tips lime-pale
    base = g.mix(g.ramp(rv, 0.15, 0.95), (0.035, 0.085, 0.03), (0.06, 0.12, 0.05))
    base = g.mix(g.ramp(rv, 0.85, 1.0), base, (0.05, 0.11, 0.07))
    col = g.mix(g.math("MULTIPLY", g.ramp(age, 0.78, 0.95), 0.65), base, (0.17, 0.27, 0.06))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.85, 1.0), 0.25), col, (0.12, 0.16, 0.07))
    # Undersides: two pale stomatal bands either side of the midrib
    band = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", across), 0.45)), 0.2, 0.05), 0.7)
    col = g.mix(back, col, g.mix(band, col, (0.32, 0.38, 0.33)))
    if shade:
        col = g.mix(shade, col, (0.01, 0.025, 0.01))
    rough = g.mixf(back, 0.42, 0.6)
    tr.tk.finish(mat, g, col, 0.0, rough)
    leaf = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("FirTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.07, 0.045, 0.03), (0.15, 0.1, 0.065))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    twig = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("FirConeSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.2, 0.09, 0.04), (0.33, 0.16, 0.07))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.6, 1.0), 0.5), col, (0.42, 0.24, 0.12))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.3, 0.0), 0.6), col, (0.06, 0.03, 0.015))
    tr.tk.finish(mat, g, col, 0.0, 0.7, g.bump(g.noise(300.0, detail=3.0), 0.2, 0.0003))
    cone_mat = tr.signals(mat, col, 0.7)

    mat, g = tr.tk.new_material("FirBractSrc")
    col = g.mix(g.ramp(g.noise(200.0, detail=2.0), 0.3, 0.7), (0.4, 0.32, 0.18), (0.55, 0.45, 0.28))
    tr.tk.finish(mat, g, col, 0.0, 0.65)
    bract = tr.signals(mat, col, 0.65)
    return {"leaf": leaf, "twig": twig, "petiole": twig, "cone": cone_mat, "bract": bract}


def spray(m, rnd, start, direction, length, cones=0, order=2):
    """A flat fir spray hanging from `start`: a main twig with side twigs alternately left and right in its plane,
    shorter toward its tip, theirs again (`order` 2), every one needled; `cones` cones hanging under it."""
    pts = tr.bend_path(start, direction, length, rnd.uniform(0.15, 0.45), steps=12, down=(0.0, -1.0, 0.0))
    needled(m, rnd, pts, 0.0028 if order == 2 else 0.0018)
    tw = tr.Branch(pts, [0.003] * len(pts))
    f, side = rnd.uniform(0.06, 0.12), rnd.choice((-1, 1))
    while f < 0.86 and order > 0:
        p, tan, _ = tw.at(f)
        d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(38.0, 55.0))
        d.z += rnd.uniform(-0.12, 0.12)
        L = length * rnd.uniform(0.38, 0.5) * (1.0 - 0.6 * f)
        if L > 0.035:
            spray(m, rnd, p, d, L, 0, order - 1)
        f += rnd.uniform(0.05, 0.08)
        side = -side
    for _ in range(cones):
        p, tan, _ = tw.at(rnd.uniform(0.25, 0.55))
        cone(m, rnd, p + Vector((0.0, 0.0, -0.006)), Vector((rnd.uniform(-0.3, 0.3), -1.0, rnd.uniform(-0.3, 0.0))),
             rnd.uniform(0.07, 0.09))


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(31)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.1, 0.3), -1.0, 0.0)), rnd.uniform(0.48, 0.56),
              cones=(0, 1, 0, 2)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        # A limb's end: a stem with sprays fanned out along both sides of it, nearly flat, layered
        m = tr.Mesh()
        side = (1, -1)[ci]
        stem = tr.bend_path(Vector(), Vector((side * 0.35, -1.0, 0.05)), rnd.uniform(1.4, 1.6), 0.3, steps=12,
                            down=(0.0, -1.0, 0.0))
        tr.twig(m, stem, [0.012 * (1.0 - 0.7 * i / (len(stem) - 1)) for i in range(len(stem))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        br = tr.Branch(stem, [0.01] * len(stem))
        for j in range(16):
            f = 0.04 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / 16
            p, tan, _ = br.at(f)
            c = sprays[rnd.randrange(len(sprays))].copy()
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
    # A small sprig for the seedling
    m = tr.Mesh()
    spray(m, random.Random(5), Vector(), Vector((0.1, -1.0, 0.0)), 0.13, 0, 1)
    sprig = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [sprig])
    if render:
        atlas.render(atlas.cells[LEAF], [sprig])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "DouglasFirLeaves")
    atlas.preview(os.path.join(PREVIEWS, "douglas_fir_atlas.png"))
    for c in atlas.cells.values():
        print("[douglas_fir] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("DouglasFirLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def cone_shape(t):
    """The crown's envelope up the leader: the lowest live limbs longest, shortening steadily to the top, rounding
    a little near the bottom (a narrow cone)."""
    return (1.0 - 0.9 * t) * (0.85 + 0.15 * math.sin(math.pi * min(1.0, t * 2.0)))


def fir(trunks, crown=0.3, reach=1.0, whorl_gap=1.0, budget=11000, stubs=(8, 14), card_scale=(1.2, 1.5)):
    """A Douglas fir's TreeSpec: `trunks` (tr.Trunk), whorls of four limbs every `whorl_gap` m from `crown` of the
    height up, near horizontal low down and rising toward the top, drooping a little along their length; `reach`
    scales them; side branchlets in each limb's plane; dead stubs below the live crown; flat sprays along every limb
    and branchlet, laid out flat facing the sky, close enough to make tiers of dense foliage."""
    limbs = tr.Level(per_meter=4.0 / whorl_gap, whorl=4, span=(crown, 0.985), length=(4.0 * reach, 6.0 * reach),
                     shape=cone_shape, angle=86.0, angle_tip=55.0, angle_vary=7.0, radius=0.22, radius_length=0.7,
                     radius_max=0.075, tip_radius=0.004, step=0.3, gravitropism=0.12, droop=0.45, wander=0.15,
                     outward=0.15, sides=(4, 3, 3), seg=(1.2, 2.0, 3.0), min_len=(0.0, 0.5, 1.8))
    branchlets = tr.Level(per_meter=1.3, span=(0.12, 0.95), length=(0.7 * reach ** 0.5, 1.5 * reach ** 0.5),
                          shape="tapered", angle=55.0, angle_tip=45.0, angle_vary=10.0, planar=0.7, radius=0.5,
                          radius_length=0.5, radius_max=0.015, tip_radius=0.002, step=0.2, gravitropism=0.08,
                          droop=0.4, wander=0.3, sides=(3, 0, 0), seg=(0.8, 9.0, 9.0), min_len=(0.0, 99.0, 99.0))
    stubs_lv = tr.Level(count=stubs, span=(0.06, max(0.1, crown - 0.02)), length=(0.08, 0.5), angle=80.0,
                        angle_vary=10.0, radius=0.12, radius_length=0.4, radius_max=0.035, tip_radius=0.01,
                        broken=True, step=0.08, droop=0.4, wander=0.2, sides=(6, 4, 0), seg=(0.3, 1.0, 1.0),
                        min_length=0.05)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs, branchlets], stubs=stubs_lv, budget=budget, bark_budget=4500,
        foliage=tr.Foliage(levels={2: (0.0, 1.0), 1: (0.06, 1.0)}, trunk_top=(0.9, 1.0), spacing=0.055, cells=SPRAYS,
                           scale=card_scale, hang=0.12, spread=0.3, out=0.65, face=0.35, up=0.6, roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.15, 1.0)}, trunk_top=(0.85, 1.0), spacing=1.1, cells=CLUSTERS,
                           scale=(0.9, 1.15), hang=0.15, spread=0.25, out=0.7, face=0.5, up=0.5, roll=15.0,
                           bend=15.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.4, flare_height=0.6, lobes=(7, 0.12), taper=1.0, tip_radius=0.006, wander=0.05,
                sides=(16, 10, 6), seg=(1.0, 2.0, 3.6), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeDouglasFirSeed in game): a stem about 0.5 m tall with three
    whorls of short twigs, hung with small needle sprigs (the atlas's Leaf cell)."""
    shoots = tr.Level(per_meter=8.0, whorl=4, span=(0.3, 0.92), length=(0.08, 0.16), shape="tapered", angle=72.0,
                      angle_tip=55.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0008, step=0.03,
                      gravitropism=0.2, droop=0.3, wander=0.3, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.03, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.5, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0015,
                         lean=(0.02, 0.02), bow=0.2, wander=0.015, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.55, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.7, 1.0), hang=0.1, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.09, cells=(LEAF,), scale=(0.9, 1.1),
                           hang=0.1, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # Mature, about 30 m: a long straight trunk, the live crown from a third of the way up
    ("DouglasFir01", 5, lambda: fir([trunk(height=30.0, radius=0.4, lean=(0.3, -0.2), bow=0.1)], budget=12000)),
    # Leaning, about 25 m, its crown fuller on the open side it leans to
    ("DouglasFir02", 17, lambda: fir([trunk(height=25.0, radius=0.34, lean=(2.4, 0.7), bow=-0.3, wander=0.08)],
                                     crown=0.35, reach=0.9)),
    # Old and broken-topped, about 27 m: its top snapped off thick, the limbs below it gone long and heavy
    ("DouglasFir03", 29, lambda: fir([trunk(height=27.0, radius=0.5, tip_radius=0.14, broken=True, lean=(-0.4, 0.3),
                                            bow=0.15, sides=(18, 11, 7))],
                                     crown=0.42, reach=1.05, whorl_gap=1.2, stubs=(12, 18))),
    # Young, about 10 m, limbs right down to the ground
    ("DouglasFir04", 41, lambda: fir([trunk(height=10.0, radius=0.12, lean=(0.2, 0.3), bow=0.1, flare=0.25)],
                                     crown=0.06, reach=0.5, whorl_gap=0.6, budget=6500, stubs=(0, 0),
                                     card_scale=(1.0, 1.25))),
    # The seedling a planted seed shows before it grows into DouglasFir04
    ("DouglasFirSapling", 59, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """DouglasFirSeed_Icon.png (160 x 160, in Trees/DouglasFir; gen_nature.py copies it into the mod's item icons),
    drawn like vanilla's pine cone seed: a Douglas fir cone with its three-pointed bracts, lying on a needle sprig,
    under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(shade=0.15)
    rnd = random.Random(3)
    m = tr.Mesh()
    # Built in a card's frame (x right, y up, facing +z): a sprig behind, from the bottom right up to the left, and
    # the cone in front of it, hanging down to the left from the top
    spray(m, rnd, Vector((0.045, -0.05, 0.0)), Vector((-0.6, 1.0, 0.0)), 0.13, 0, 1)
    cone(m, rnd, Vector((0.02, 0.045, 0.02)), Vector((-0.35, -1.0, 0.1)), 0.085)
    obj = m.build("DouglasFirSeedIcon", mats)
    # Turned from the card's frame (facing +z) to face the icon camera (at -y)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (-0.03, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "DouglasFirSeed_Icon.png"), hide=())
    print("[douglas_fir] icon written")


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
    mats = {"bark": tr.textured("DouglasFirBark", paths("DouglasFirBark")),
            "twig": tr.textured("DouglasFirBarkTwig", paths("DouglasFirBarkTwig")),
            "leaves": tr.textured("DouglasFirLeaves", paths("DouglasFirLeaves"), cutout=True, translucent=0.25)}
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
        print("[douglas_fir] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("douglasfir01", lods[0], PREVIEWS, figure)
    tr.preview_lods("douglasfir01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("douglas_fir", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[douglas_fir] done")


main()
