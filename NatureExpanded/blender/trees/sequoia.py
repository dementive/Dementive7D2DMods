"""Giant sequoia (Sequoiadendron giganteum), on treekit.py (birch.py is the worked example; TREES.md has the rules).

The biggest tree there is: a massively buttressed trunk with a few metres' girth to spare, deeply fluted, wrapped in
thick soft fibrous bark of cinnamon red-brown in long vertical ridges with grey-brown furrows; bare of branches for
the lower half, then a dense irregular crown of heavy limbs that sweep outward and curve up, carrying drooping plumes
of tiny scale-like leaves in a dark blue-green; round woody cones 5 to 7 cm.

    blender -b --factory-startup --python trees/sequoia.py -- <unity trees folder> <preview folder> [step] [variants]

with absolute paths for `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/
trees`. Steps as douglas_fir.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`; `variants` an
optional comma list (`Sequoia01,Sequoia04`) to build only those. It writes Trees/Sequoia/ (bark, burn-scar and leaf
textures, Sequoia01..04 and the seedling SequoiaSapling with their impostors, SequoiaSeed_Icon.png), the Sequoia lines of
Trees/trees.txt and trunks.txt, and the previews. Built at its size in game (the Unity builder's scale 1).

Treekit has no fluted trunks and no fire scars, so this module carries its own tube builder (`sequoia_tube`, swapped in
for treekit's `_tube`): the same tube, plus (on trunks that ask for it) a radial fluting that wanders up the trunk and,
for a fire-scarred tree, a cleft cut into the foot whose quads take the charcoal material. The trunk's collision
capsules (trunks.txt) stay the full trunk, so a scar never opens a hole in them.
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
ONLY = set(args[3].split(",")) if len(args) > 3 else None
FOLDER = os.path.join(TREES, "Sequoia")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
NL = chr(10)

# ---------------------------------------------------------------- bark textures
#
# SequoiaBark: 2048 x 4096 wrapping three times round a tube and tiling up it every 4.2 radii, drawn at its size on
# Sequoia01's 1.6 m trunk: about 6 px per cm (a pixel is 1.6 mm, finer than the screen's at an arm's length). Its
# ridges are 15 cm wide and metres long, its furrows 3 to 6 cm. SequoiaBarkTwig 512 x 1024: smooth red-brown bark of
# the limbs under 6 cm radius. SequoiaBarkBurn 1024 x 2048 wrapping twice: the charcoal of the fire scar.

W, H, WRAPS = 2048, 4096, 3
K = TAU * H / (WRAPS * W)
R_DESIGN = 160.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.17
WB, HB, WRAPS_B = 1024, 2048, 2
KB = TAU * HB / (WRAPS_B * WB)
# Mean albedo (sRGB): cinnamon red-brown, a touch redder than vanilla's grey-brown pine bark; the foliage a deep
# blue-green a little darker and bluer than the Douglas fir's (60, 77, 54)
BARK_MEAN = (96, 62, 50)
LEAF_MEAN = (44, 66, 55)
TWIG_R = 0.06
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
    "burn": tr.BarkUV(k=KB, wraps=WRAPS_B, twist=0.1),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def sequoia_bark(r, h=H, w=W, px=PX):
    """Old sequoia bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: soft
    spongy cinnamon-red ridges 10 to 20 cm wide running up for metres, stringy with long fibres, broken here and there
    by a crack across them, weathered grey-brown on their crests; between them furrows 3 to 6 cm wide, dark
    grey-brown, their walls the fresh red."""
    cm = px
    warp = ((tr.fbm(r, h, w, (6 * cm, 60 * cm), 3) - 0.5) * 8.0 * cm,
            (tr.fbm(r, h, w, (6 * cm, 40 * cm), 3) - 0.5) * 24.0 * cm)
    edge, ridge, _, _ = tr.cells(r, h, w, 12 * cm, 8.0, warp)
    block_edge, _, _, _ = tr.cells(r, h, w, 9 * cm, 3.0, warp)
    n = ridge.max() + 1
    shade = r.random(n)[ridge]
    wobble = tr.fbm(r, h, w, (2 * cm, 14 * cm), 3)
    width = (1.5 + 2.2 * wobble) * cm  # half the furrow
    depth = 1.0 - tr.smoothstep(0.0, width, edge)
    wall = tr.smoothstep(0.2, 0.55, depth) * (1.0 - tr.smoothstep(0.7, 0.95, depth))
    top = tr.smoothstep(0.0, 2.2 * cm, edge - width * 0.5)
    mottle = tr.fbm(r, h, w, (4 * cm, 18 * cm), 4)
    # The ridges are cracked across in places, and the cracks wander off along a ridge's grain
    crack = (1.0 - tr.smoothstep(0.0, (0.25 + 0.3 * wobble) * cm, block_edge)) * top
    crack *= tr.smoothstep(0.58, 0.72, tr.fbm(r, h, w, (8 * cm, 40 * cm), 3))
    # Fibres: the bark is stringy, strands a few millimetres wide and tens of centimetres long, a longer pale strip
    # peeling here and there
    fibre = tr.fbm(r, h, w, (0.4 * cm, 12 * cm), 3)
    fine = tr.fbm(r, h, w, (0.15 * cm, 3 * cm), 2)
    strip = tr.fbm(r, h, w, (1.4 * cm, 45 * cm), 3)
    weather = tr.smoothstep(0.55, 0.78, tr.fbm(r, h, w, (10 * cm, 40 * cm), 3)) * top

    fibre = np.clip((fibre - 0.5) * 2.0 + 0.5, 0.0, 1.0)
    fine = np.clip((fine - 0.5) * 2.2 + 0.5, 0.0, 1.0)
    strip = np.clip((strip - 0.5) * 1.6 + 0.5, 0.0, 1.0)
    face = tr.mix((0.33, 0.17, 0.115), (0.6, 0.36, 0.235),
                  0.2 * shade + 0.05 * mottle + 0.38 * fibre + 0.2 * strip + 0.17 * fine)
    inner = tr.mix((0.3, 0.15, 0.1), (0.46, 0.25, 0.16), 0.6 * fibre + 0.4 * fine)
    col = tr.mix(inner, face, top)
    col = tr.mix(col, inner, wall * 0.7)
    col = tr.mix(col, (0.09, 0.06, 0.055), tr.smoothstep(0.45, 1.0, depth))
    col = tr.mix(col, (0.46, 0.38, 0.33), weather * 0.2)
    col = tr.mix(col, (0.18, 0.115, 0.09), crack * 0.6)
    # Pale peeled fibre tips catching the light
    col = tr.mix(col, (0.7, 0.45, 0.32), tr.smoothstep(0.78, 0.95, fibre * 0.6 + strip * 0.4) * top * 0.35)

    crown = tr.smoothstep(0.0, 5.0 * cm, edge - width)  # each ridge domed from its furrow up to its crest
    height = (3.0 * (1.0 - depth) + 1.8 * crown + 0.6 * top + 0.5 * fibre + 0.3 * strip + 0.2 * mottle + 0.2 * fine
              - 1.3 * crack)
    rough = 0.93 + 0.04 * (fine - 0.5)
    occ = tr.cavity(height, 6.0 * RELIEF, 0.45)
    col = col * (0.6 + 0.4 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """The limbs' bark at 3 cm radius: smooth red-brown, finely grained along its length, a few longitudinal
    wrinkles."""
    cm = w / TAU / 3.0
    tone = tr.fbm(r, h, w, (3 * cm, 12 * cm), 4)
    grain = tr.fbm(r, h, w, (0.35 * cm, 6 * cm), 3)
    wrinkle = tr.contour(tr.fbm(r, h, w, (1.4 * cm, 14 * cm), 3), 0.07)
    col = tr.mix((0.36, 0.19, 0.125), (0.54, 0.31, 0.2), 0.5 * tone + 0.5 * grain)
    col = tr.mix(col, (0.18, 0.1, 0.075), wrinkle * 0.5)
    height = 0.4 * tone + 0.5 * grain - 0.8 * wrinkle
    return np.clip(col, 0.0, 1.0), height, 0.85 + 0.05 * grain, tr.cavity(height, 3.0, 0.2)


def burn_bark(r, h=HB, w=WB):
    """The fire scar's charcoal: blocks of burnt wood 3 to 5 cm across checked into domed plates by black cracks (the
    'alligator' of a burnt trunk), a dull sheen on a few, no glow; the first stretch of the scar's edge, where the
    bark is only scorched, is the same texture."""
    px = WRAPS_B * w / (TAU * 130.0)
    cm = px
    warp = ((tr.fbm(r, h, w, (6 * cm, 20 * cm), 3) - 0.5) * 4 * cm, (tr.fbm(r, h, w, (6 * cm, 20 * cm), 3) - 0.5) * 8 * cm)
    edge, block, _, _ = tr.cells(r, h, w, 5 * cm, 1.8, warp)
    sub, _, _, _ = tr.cells(r, h, w, 1.6 * cm, 1.2, warp)
    m = block.max() + 1
    bshade, sheen = r.random(m)[block], r.random(m)[block]
    check = 1.0 - tr.smoothstep(0.4, 1.8, edge)
    fine = 1.0 - tr.smoothstep(0.3, 1.1, sub)
    dome = tr.smoothstep(0.0, 0.5 * cm, edge)
    grit = tr.fbm(r, h, w, (0.2 * cm, 0.2 * cm), 2)
    grain = tr.fbm(r, h, w, (0.3 * cm, 8 * cm), 3)
    col = tr.mix((0.04, 0.038, 0.036), (0.13, 0.12, 0.115), 0.45 * bshade + 0.25 * grit + 0.15 * dome + 0.15 * grain)
    shine = dome * tr.smoothstep(0.65, 0.95, sheen)
    col = tr.mix(col, (0.22, 0.21, 0.205), shine * 0.3)
    col = tr.mix(col, (0.015, 0.014, 0.014), np.maximum(check, fine * 0.5))
    # Where the char has fallen away a little reddish wood shows, as dark as the rest
    red = tr.smoothstep(0.78, 0.84, tr.fbm(r, h, w, (3 * cm, 9 * cm), 3))
    col = tr.mix(col, (0.1, 0.045, 0.03), red * 0.7)
    height = 0.7 * dome - 1.0 * check - 0.4 * fine + 0.25 * grit + 0.2 * grain
    rough = 0.9 - 0.18 * shine
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), tr.cavity(height, 3.0, 0.25)


def make_bark():
    r = np.random.default_rng(41)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = sequoia_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    # The furrows are several centimetres deep: more relief in the normal map than shallow bark gets
    save("SequoiaBark", col, height, rough, occ, RELIEF * 6.0)
    save("SequoiaBarkTwig", *twig_bark(r), 1.0)
    save("SequoiaBarkBurn", *burn_bark(r), 1.5)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the foliage atlas
#
# 2048 square, as the others': four plume cells (512 x 768) along the top, two of them with a cone or two; two
# cluster cells (1024 x 1152) of a limb's end hung thick with plumes, for LOD2; one small sprig (128 square) for the
# seedling, past the decal strip.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1280, 512, 768, (0.78, 1.17))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1152, (2.4, 2.7))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.16, 0.16), pad=8)
    return atlas


def scale_leaf(m, base, way, out, length, width, rv, age):
    """One awl-shaped scale leaf: a thin triangle from `base` along `way`, lying close to its twig (`out` is the
    direction away from the twig's axis), its tip turned in a little; "leaf" = (across -1..1, along 0..1, a random)
    and "age" = how near its twig's tip it grew (1: this year's paler growth)."""
    d = Vector(way).normalized()
    o = Vector(out)
    side = d.cross(o)
    side = side.normalized() if side.length > 1e-6 else d.orthogonal().normalized()
    tip = Vector(base) + d * length - o * (0.06 * length)
    a = m.v(Vector(base) - side * (width * 0.5), leaf=(-1.0, 0.0, rv), age=age)
    b = m.v(Vector(base) + side * (width * 0.5), leaf=(1.0, 0.0, rv), age=age)
    c = m.v(tip, leaf=(0.0, 1.0, rv), age=age)
    m.tri(a, b, c, ((0, 0),) * 3, "leaf")


def cord(m, rnd, pts, radius, per_m=2600, length=(0.009, 0.014)):
    """A shoot along `pts` hung all round with scale leaves, spiralling up it, pressed close and pointing toward its
    tip, a little shorter at the tip, this year's growth there paler."""
    tr.twig(m, pts, [radius * (1.0 - 0.5 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 5)
    tw = tr.Branch(pts, [radius] * len(pts))
    n = max(4, int(tw.length * per_m))
    phi = rnd.uniform(0.0, TAU)
    for i in range(n):
        f = (i + rnd.random()) / n
        p, tan, _ = tw.at(f)
        phi += tr.GOLDEN
        _, u, v = tr.basis(tan)
        radial = u * math.cos(phi) + v * math.sin(phi)
        theta = math.radians(rnd.uniform(28.0, 55.0))
        way = tan * math.cos(theta) + radial * math.sin(theta)
        L = rnd.uniform(*length) * (1.0 - 0.4 * max(0.0, f - 0.8) / 0.2)
        scale_leaf(m, p + radial * radius * 0.85, way, radial, L, 0.0038, rnd.random(), f)


def plume(m, rnd, start, direction, length, order=2, thick=0.0034, per_m=2600):
    """A hanging plume from `start`: a cord that curves down, with side cords alternately left and right, hanging
    too and shorter toward its tip, theirs again (`order` 2), every one scaled."""
    pts = tr.bend_path(start, direction, length, rnd.uniform(0.35, 0.85), steps=10, down=(0.0, -1.0, 0.0))
    cord(m, rnd, pts, thick, per_m)
    tw = tr.Branch(pts, [thick] * len(pts))
    f, side = rnd.uniform(0.05, 0.09), rnd.choice((-1, 1))
    while f < 0.9 and order > 0:
        p, tan, _ = tw.at(f)
        d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(32.0, 62.0))
        d.z += rnd.uniform(-0.25, 0.25)
        L = length * rnd.uniform(0.3, 0.5) * (1.0 - 0.5 * f)
        if L > 0.05:
            plume(m, rnd, p, d, L, order - 1, thick * 0.8, per_m)
        f += rnd.uniform(0.04, 0.07)
        side = -side
    return tw


def cone(m, rnd, top, way, length, key="cone"):
    """A sequoia cone hanging from `top` along `way`, `length` long: an oval of woody shield-shaped scales in a
    tight spiral, each dimpled in the middle, on a short stalk."""
    d = Vector(way).normalized()
    _, u, v = tr.basis(d)
    rad = length * 0.36

    def prof(f):
        return math.sin(math.pi * (0.1 + 0.8 * f)) ** 0.5

    core = [top + d * (length * i / 8) for i in range(9)]
    tr.twig(m, core, [rad * 0.92 * prof(i / 8) for i in range(9)], key, 8)
    tr.twig(m, [top - d * 0.012, top], [0.0016, 0.0019], "twig", 5)
    count = 40
    sl = length * 0.2
    for i in range(count):
        f = 0.06 + 0.9 * (i + rnd.uniform(-0.3, 0.3)) / count
        a = i * tr.GOLDEN
        out = u * math.cos(a) + v * math.sin(a)
        slope = (prof(min(1.0, f + 0.03)) - prof(max(0.0, f - 0.03))) * rad / (0.06 * length)
        along = (d + out * slope).normalized()
        base = top + d * (f * length) + out * (rad * prof(f)) - along * (sl * 0.5)
        tr.blade(m, base, along, out, sl, sl * 1.15, lambda s: math.sin(math.pi * min(1.0, s * 0.98)) ** 0.7, key,
                 fold=0.18, arch=0.1, rows=4, rnd_value=rnd.random())


def leaf_materials(shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): scale leaves ("leaf"), twig, cone."""
    mat, g = tr.tk.new_material("SeqLeafSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    age = g.node("ShaderNodeAttribute", attribute_name="age").outputs["Fac"]
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Dull blue-green, leaf to leaf a little bluer or yellower; this year's growth at the shoots' tips paler
    base = g.mix(g.ramp(rv, 0.15, 0.95), (0.03, 0.075, 0.055), (0.055, 0.115, 0.08))
    base = g.mix(g.ramp(rv, 0.85, 1.0), base, (0.045, 0.1, 0.085))
    col = g.mix(g.math("MULTIPLY", g.ramp(age, 0.72, 0.95), 0.6), base, (0.1, 0.19, 0.12))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.8, 1.0), 0.3), col, (0.09, 0.15, 0.12))
    col = g.mix(g.math("MULTIPLY", back, 0.5), col, (0.13, 0.18, 0.17))
    if shade:
        col = g.mix(shade, col, (0.01, 0.025, 0.02))
    rough = g.mixf(back, 0.5, 0.6)
    tr.tk.finish(mat, g, col, 0.0, rough)
    leaf = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("SeqTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.1, 0.055, 0.035), (0.2, 0.11, 0.07))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    twig = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("SeqConeSrc")
    x, s, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.13, 0.11, 0.05), (0.27, 0.16, 0.08))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.55, 1.0), 0.5), col, (0.34, 0.2, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.3, 0.0), 0.6), col, (0.05, 0.03, 0.02))
    tr.tk.finish(mat, g, col, 0.0, 0.7, g.bump(g.noise(300.0, detail=3.0), 0.2, 0.0003))
    cone_mat = tr.signals(mat, col, 0.7)
    return {"leaf": leaf, "twig": twig, "petiole": twig, "cone": cone_mat}


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(53)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        tw = plume(m, rnd, Vector(), Vector((side * rnd.uniform(0.05, 0.25), -1.0, 0.0)), rnd.uniform(0.5, 0.58))
        for _ in range((0, 1, 0, 2)[i]):
            p, tan, _ = tw.at(rnd.uniform(0.25, 0.5))
            cone(m, rnd, p + Vector((0.0, 0.0, -0.006)), Vector((rnd.uniform(-0.3, 0.3), -1.0, rnd.uniform(-0.3, 0.0))),
                 rnd.uniform(0.055, 0.07))
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        # A limb's end: a stem curving up from the left or the right with plumes hung all along it, layered
        m = tr.Mesh()
        side = (1, -1)[ci]
        stem = tr.bend_path(Vector(), Vector((side * 0.9, 0.25, 0.05)), rnd.uniform(1.5, 1.7), 0.3, steps=12,
                            down=(0.0, -1.0, 0.0))
        tr.twig(m, stem, [0.014 * (1.0 - 0.7 * i / (len(stem) - 1)) for i in range(len(stem))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        br = tr.Branch(stem, [0.01] * len(stem))
        for j in range(15):
            f = 0.04 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / 15
            p, tan, _ = br.at(f)
            c = sprays[rnd.randrange(len(sprays))].copy()
            tr.tk.link(c)
            spin = (j % 2 * 2 - 1) * rnd.uniform(0.0, 50.0)
            rot = (Matrix.Rotation(math.radians(spin), 4, "Y")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-20, 20)), 4, "Z"))
            c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.85, 1.2) * (1.0 - 0.25 * f), 4)
            objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    # A small sprig for the seedling
    m = tr.Mesh()
    plume(m, random.Random(7), Vector(), Vector((0.1, -1.0, 0.0)), 0.13, 1, 0.0016, 1300)
    sprig = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [sprig])
    if render:
        atlas.render(atlas.cells[LEAF], [sprig])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "SequoiaLeaves")
    atlas.preview(os.path.join(PREVIEWS, "sequoia_atlas.png"))
    for c in atlas.cells.values():
        print("[sequoia] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("SequoiaLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- tubes: fluting and the fire scar

def wrap_angle(a):
    return (a + math.pi) % TAU - math.pi


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def make_flutes(rnd, depth, counts=(6, 9, 12), weights=(0.5, 0.35, 0.15), drift=1.5, height=55.0):
    """A fluting recipe: waves of `counts` crests round the trunk, their phases wandering up it so the flutes
    meander, merge and split (a different `L` per wave: metres per full wander), `depth` the share of the radius the
    valleys cut in (the crests stay at the nominal radius, so the collision capsules never sit in the air)."""
    return dict(depth=depth, height=height,
                waves=[(n, w, rnd.uniform(0, TAU), drift * rnd.uniform(0.7, 1.2), rnd.uniform(16.0, 34.0) + 5.0 * i,
                        rnd.uniform(0, TAU)) for i, (n, w) in enumerate(zip(counts, weights))],
                mod=(rnd.uniform(14.0, 24.0), rnd.uniform(0, TAU)))


def flute_factor(f, a, z, sides):
    """The radius multiplier (1 on a crest, down to 1 - depth in a valley) at angle `a`, height `z`; waves too fine
    for this many sides to draw (under 3 sides per crest) are left out."""
    tot = wsum = 0.0
    for n, w, ph, amp, L, psi in f["waves"]:
        if n * 3 > sides:
            continue
        tot += w * math.cos(n * a + ph + amp * math.sin(TAU * z / L + psi))
        wsum += w
    if wsum <= 0.0:
        return 1.0
    v = 0.5 - 0.5 * tot / wsum  # 0 on a crest, 1 in a valley
    L, psi = f["mod"]
    d = f["depth"] * (0.7 + 0.3 * math.sin(TAU * z / L + psi)) * max(0.3, 1.0 - z / (1.5 * f["height"]))
    return 1.0 - d * v ** 1.5


def scar_cut(sc, a, z):
    """How much of the radius the fire scar cuts away at angle `a`, height `z`: a cleft widest at the ground that
    narrows to a point up the trunk, steep-walled, its back wall `depth` of the radius in."""
    if z >= sc["h"]:
        return 0.0
    w = sc["w"] * max(0.0, 1.0 - z / sc["h"]) ** 0.5
    if w <= 1e-4:
        return 0.0
    x = abs(wrap_angle(a - sc["theta"])) / w
    across = 1.0 - smooth(0.7, 1.0, x)
    top = smooth(sc["h"], sc["h"] * 0.55, z)
    return sc["depth"] * across * top


def scar_zone(sc, a, z):
    """Whether a stretch of trunk at (a, z) takes the charcoal: the cleft, a hand's breadth of scorched bark round
    its edge, and a narrow black tongue licking up from its top."""
    da = abs(wrap_angle(a - sc["theta"]))
    if z < sc["h"] * 1.35:
        w = (sc["w"] + sc["margin"]) * max(0.0, 1.0 - z / (sc["h"] * 1.35)) ** 0.5
        if da <= w:
            return True
    return z < sc["h"] * 2.6 and da <= sc["w"] * 0.22 * (1.0 - z / (sc["h"] * 2.6))


def sequoia_tube(m, tree, br, lod):
    """treekit._tube with a trunk's fluting (`Trunk.flutes`, from make_flutes) and a fire scar (`Trunk.scar`) added:
    the same rings, bark mapping, tips and buried end."""
    spec = br.spec
    sides = spec.sides[lod]
    seg = spec.seg[lod]
    keyfn = tree.spec.bark_key
    maps = tree.spec.bark_uv
    fl = getattr(spec, "flutes", None) if br.level == 0 else None
    sc = getattr(spec, "scar", None) if br.level == 0 else None

    def key_at(s):
        p, _, r = br.at(s)
        return keyfn(br, s, r, p.z)

    n = max(1, int(round(br.length / seg)))
    forced = []
    if br.level == 0:
        forced = [br.s_at_height(z) for z in spec.rings[lod]]
    gap = 0.35 * seg / br.length
    ss = sorted(set([0.0, 1.0] + forced + [i / n for i in range(1, n) if all(abs(i / n - f) > gap for f in forced)]))
    rings_s = [ss[0]]
    for a, b in zip(ss, ss[1:]):
        ka = key_at(min(1.0, a + 1e-5))
        if ka != key_at(max(0.0, b - 1e-5)):
            lo, hi = a, b
            for _ in range(16):
                mid = (lo + hi) * 0.5
                lo, hi = (mid, hi) if key_at(mid) == ka else (lo, mid)
            rings_s.append((lo + hi) * 0.5)
        rings_s.append(b)
    pts, rads = [], []
    for s in rings_s:
        p, _, r = br.at(s)
        pts.append(p)
        rads.append(r)
    br.drawn[lod] = (list(rings_s), list(pts))
    fr = tr.frames(pts)
    acc = [0.0]
    for i in range(1, len(pts)):
        ds = (pts[i] - pts[i - 1]).length
        acc.append(acc[-1] + ds / max((rads[i] + rads[i - 1]) * 0.5, 0.004))
    if br.level == 0:
        j = next((i for i in range(1, len(pts)) if pts[i].z >= 0.0), None)
        if j is not None:
            f = max(0.0, min(1.0, -pts[j - 1].z / max(pts[j].z - pts[j - 1].z, 1e-9)))
            g = acc[j - 1] + (acc[j] - acc[j - 1]) * f
            acc = [a - g for a in acc]
    lobes = getattr(spec, "lobes", (0, 0.0))
    rings = []
    for i, (p, r) in enumerate(zip(pts, rads)):
        t, nr, bn = fr[i]
        ring = []
        if sc is not None and lod == 0 and p.z >= 1.0 and not hasattr(br, "scar_dir"):
            br.scar_dir = nr * math.cos(sc["theta"]) + bn * math.sin(sc["theta"])  # for the preview
        for k in range(sides):
            a = br.rot + k / sides * TAU
            rr = r
            if lobes[0] and br.level == 0:
                fade = math.exp(-max(0.0, p.z) / max(spec.flare_height, 1e-3))
                swell = 0.65 * math.cos(lobes[0] * a) + 0.35 * math.cos((lobes[0] + 2) * a + 1.3)
                rr *= 1.0 + lobes[1] * fade * swell
            if fl is not None and p.z > -0.2:
                rr *= flute_factor(fl, a, max(0.0, p.z), sides)
            if sc is not None and p.z > -0.2:
                rr *= 1.0 - scar_cut(sc, a, max(0.0, p.z))
            ring.append(m.v(p + (nr * math.cos(a) + bn * math.sin(a)) * rr))
        rings.append(ring)
    for i in range(len(rings) - 1):
        sm = (rings_s[i] + rings_s[i + 1]) * 0.5
        key0 = key_at(sm)
        za, zb = pts[i].z, pts[i + 1].z
        for k in range(sides):
            k1 = k + 1
            key = key0
            if sc is not None:
                am = br.rot + (k + 0.5) / sides * TAU
                if scar_zone(sc, am, max(0.0, (za + zb) * 0.5)):
                    key = "burn"
            bm = maps[key]
            m.quad(rings[i][k], rings[i][k1 % sides], rings[i + 1][k1 % sides], rings[i + 1][k],
                   (bm.uv(k / sides, acc[i], za, br), bm.uv(k1 / sides, acc[i], za, br),
                    bm.uv(k1 / sides, acc[i + 1], zb, br), bm.uv(k / sides, acc[i + 1], zb, br)), key)
    key = key_at(0.999)
    bm = maps[key]
    t_end = fr[-1][0]
    broken = getattr(spec, "broken", False)
    tip = m.v(pts[-1] + t_end * (rads[-1] * (0.15 if broken else 1.5)))
    for k in range(sides):
        k1 = k + 1
        m.tri(rings[-1][k], rings[-1][k1 % sides], tip,
              (bm.uv(k / sides, acc[-1], pts[-1].z, br), bm.uv(k1 / sides, acc[-1], pts[-1].z, br),
               bm.uv((k + 0.5) / sides, acc[-1] + 0.3, pts[-1].z, br)), key)
    if br.parent is None:
        key = key_at(0.0)
        bm = maps[key]
        bottom = m.v(pts[0] - fr[0][0] * rads[0])
        for k in range(sides):
            k1 = k + 1
            m.tri(rings[0][k1 % sides], rings[0][k], bottom,
                  (bm.uv(k1 / sides, acc[0], pts[0].z, br), bm.uv(k / sides, acc[0], pts[0].z, br),
                   bm.uv((k + 0.5) / sides, acc[0] - 0.3, pts[0].z, br)), key)


tr._tube = sequoia_tube


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """The crown's envelope up its span: the limbs fullest in the lower third of the crown, a rounded top."""
    return 0.3 + 0.7 * math.sin(math.pi * (0.1 + 0.85 * min(1.0, t)))


def young_shape(t):
    """A young tree's: a narrow cone, the lowest limbs longest, still reaching up near the top."""
    return (1.0 - 0.86 * t) * (0.8 + 0.2 * math.sin(math.pi * min(1.0, t * 2.0)))


def sequoia(trunks, crown=0.47, limbs=1.1, reach=1.0, budget=13000, shape=None, angle=(74.0, 38.0), grav=0.17,
            droop=0.04, per_branch=1.3, card_scale=(1.5, 2.1), spacing=0.08, span_top=0.985, bark_budget=7500,
            favor=None, young=False, stubs=None):
    """A giant sequoia's TreeSpec: `trunks` (tr.Trunk), massive limbs (`limbs` per metre of the span from `crown` of
    the height up) leaving near horizontal and sweeping up (`grav`), the longest `reach` times about 8 m, `per_branch`
    side branches per metre on each carrying plumes, the plumes hung close enough to fill the crown."""
    shape = shape or crown_shape
    lv_limbs = tr.Level(per_meter=limbs, span=(crown, span_top), length=(6.0 * reach, 10.0 * reach), shape=shape,
                        angle=angle[0], angle_tip=angle[1], angle_vary=7.0, radius=0.42, radius_length=0.5,
                        radius_max=0.65, tip_radius=0.012, taper=0.5, step=0.5, gravitropism=grav, droop=droop,
                        wander=0.12, outward=0.1, favor=favor, sides=(6, 4, 3), seg=(1.8, 3.2, 6.0),
                        min_len=(0.0, 0.0, 3.5))
    lv_br = tr.Level(per_meter=per_branch, span=(0.14, 0.97), length=(2.8, 5.2), shape="tapered", angle=52.0,
                     angle_tip=40.0, angle_vary=10.0, radius=0.3, radius_length=0.6, radius_max=0.07,
                     tip_radius=0.006, step=0.4, gravitropism=0.1, droop=0.35, wander=0.2, sides=(3, 3, 0),
                     seg=(2.4, 4.0, 9.0), min_len=(0.0, 1.6, 99.0))
    return tr.TreeSpec(
        trunks=trunks, levels=[lv_limbs, lv_br], stubs=stubs, budget=budget, bark_budget=bark_budget,
        foliage=tr.Foliage(levels={2: (0.03, 1.0), 1: (0.6, 1.0)}, trunk_top=(0.93, 1.0) if not young else (0.8, 1.0),
                           spacing=spacing, cells=SPRAYS, scale=card_scale, hang=0.7, spread=0.3, out=0.45, face=0.4,
                           up=0.12, roll=25.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.4, 1.0)}, trunk_top=(0.88, 1.0), spacing=1.2, cells=CLUSTERS,
                           scale=(0.9, 1.2), hang=0.6, spread=0.3, out=0.5, face=0.4, up=0.1, roll=20.0, bend=15.0),
        bark_key=bark_key, bark_uv=UV)


def sequoia_young(trunks, budget=8000):
    """A young tree's TreeSpec: a narrow cone of drooping limbs right down to the ground, branchlets hanging from
    them, plumes close."""
    lv_limbs = tr.Level(per_meter=2.9, span=(0.05, 0.985), length=(1.7, 3.3), shape=young_shape, angle=84.0,
                        angle_tip=56.0, angle_vary=8.0, radius=0.28, radius_length=0.7, radius_max=0.05,
                        tip_radius=0.008, taper=0.8, step=0.3, gravitropism=0.2, droop=0.55, wander=0.14,
                        outward=0.1, floor=0.45, sides=(5, 4, 3), seg=(0.9, 1.6, 3.0), min_len=(0.0, 0.0, 1.4))
    lv_br = tr.Level(per_meter=1.2, span=(0.12, 0.95), length=(0.5, 1.0), shape="tapered", angle=55.0,
                     angle_tip=42.0, angle_vary=10.0, radius=0.4, radius_length=0.5, radius_max=0.015,
                     tip_radius=0.004, step=0.25, gravitropism=0.08, droop=0.5, wander=0.25, floor=0.3,
                     sides=(3, 0, 0), seg=(0.6, 9.0, 9.0), min_len=(0.0, 99.0, 99.0))
    return tr.TreeSpec(
        trunks=trunks, levels=[lv_limbs, lv_br], budget=budget, bark_budget=3500,
        foliage=tr.Foliage(levels={2: (0.05, 1.0), 1: (0.5, 1.0)}, trunk_top=(0.82, 1.0), spacing=0.07, cells=SPRAYS,
                           scale=(1.4, 1.9), hang=0.65, spread=0.3, out=0.5, face=0.4, up=0.15, roll=25.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.35, 1.0)}, trunk_top=(0.88, 1.0), spacing=0.9, cells=CLUSTERS,
                           scale=(0.6, 0.85), hang=0.6, spread=0.3, out=0.5, face=0.4, up=0.1, roll=20.0, bend=15.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(flutes=None, scar=None, **kw):
    base = dict(flare=0.55, flare_height=1.8)
    base.update(lobes=(9, 0.10), taper=0.8, tip_radius=0.02, wander=0.12, sink=1.0, step=0.8, sides=(36, 20, 10),
                seg=(2.0, 3.5, 6.0), rings=((0.0, 0.2, 0.5, 1.0, 1.6, 2.4), (0.0, 0.8, 2.0), (0.0,)))
    base.update(kw)
    t = tr.Trunk(**base)
    t.flutes = flutes
    t.scar = scar
    return t


def scar_recipe(theta, w=0.52, h=6.0, depth=0.5, margin=0.2):
    return dict(theta=theta, w=w, h=h, depth=depth, margin=margin)


def monarch():
    """Sequoia01: about 55 m, 1.6 m radius a metre up, the crown from 47 % up, a slight lean, the biggest tree
    here."""
    rnd = random.Random(11)
    return sequoia([trunk(flutes=make_flutes(rnd, 0.15, height=55.0), height=55.0, radius=1.6, lean=(0.9, -0.6),
                          bow=0.05)], crown=0.45, limbs=1.0, reach=1.25, budget=13500)


def mature():
    """Sequoia02: about 45 m, 1.25 m radius, the crown from 52 % up, fuller on one side."""
    rnd = random.Random(23)
    return sequoia([trunk(flutes=make_flutes(rnd, 0.13, counts=(5, 8, 11), height=45.0), height=45.0, radius=1.25,
                          lean=(-0.5, 0.7), bow=-0.1, wander=0.18)], crown=0.52, limbs=1.2, reach=0.88,
                   budget=12500, favor=((0.6, 0.8), 0.25))


def young():
    """Sequoia03: about 25 m, 0.4 m radius, a narrow dense cone with limbs down to the ground."""
    rnd = random.Random(37)
    return sequoia_young([trunk(flutes=make_flutes(rnd, 0.03, counts=(4, 7, 10), height=25.0), height=25.0, radius=0.4,
                                lean=(0.3, 0.2), bow=0.1, flare=0.3, flare_height=0.8, lobes=(7, 0.06), sink=0.5,
                                sides=(24, 14, 8), seg=(1.2, 2.5, 5.0), tip_radius=0.015,
                                rings=((0.0, 0.2, 0.5, 1.0), (0.0, 0.8), (0.0,)))])


def old():
    """Sequoia04: about 38 m, an old fire-scarred tree: a cleft burnt into the foot (charcoal-black, with a black
    tongue up its top), the top snapped off thick with splinters standing out of the break, the crown thinner and
    gnarled with a few big dead stubs below it."""
    rnd = random.Random(59)
    scar = scar_recipe(theta=1.1, w=0.5, h=6.5, depth=0.5)
    scar_rings = tuple(0.5 * i for i in range(0, 17)) + (9.0, 10.5)
    stubs = tr.Level(count=9, span=(0.12, 0.5), length=(0.4, 1.6), angle=75.0, angle_vary=12.0, radius=0.2,
                     radius_length=0.5, radius_max=0.09, tip_radius=0.03, broken=True, step=0.15, droop=0.4,
                     wander=0.25, sides=(7, 5, 0), seg=(0.4, 1.0, 1.0), min_length=0.2, min_len=(0.0, 0.5, 99.0))
    tk = trunk(flutes=make_flutes(rnd, 0.13, height=38.0), scar=scar, height=38.0, radius=1.3, tip_radius=0.34,
               broken=True, lean=(0.5, -1.0), bow=0.15, wander=0.3, sides=(48, 24, 12), seg=(2.0, 3.5, 6.0),
               rings=(scar_rings, (0.0, 1.0, 2.5, 4.0, 6.0), (0.0, 3.0)))
    spec = sequoia([tk], crown=0.56, limbs=0.85, reach=0.8, budget=11000, angle=(78.0, 44.0), grav=0.15, droop=0.06,
                   shape=lambda t: 0.35 + 0.65 * math.sin(math.pi * (0.15 + 0.8 * min(1.0, t))),
                   span_top=0.93, stubs=stubs, spacing=0.12)
    spec.foliage.trunk_top = None
    spec.cluster.trunk_top = None
    return spec


def sapling():
    """The planted seed's seedling (DementiveNatureTreeSequoiaSeed in game): a stem about 0.5 m tall with three whorls
    of short drooping shoots hung with small scale-leaf sprigs (the atlas's Leaf cell)."""
    shoots = tr.Level(per_meter=8.0, whorl=4, span=(0.28, 0.92), length=(0.08, 0.16), shape="tapered", angle=70.0,
                      angle_tip=52.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0008, step=0.03,
                      gravitropism=0.15, droop=0.4, wander=0.3, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.03, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.5, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0015,
                         lean=(0.02, 0.02), bow=0.2, wander=0.015, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.55, 1.0), spacing=0.05, cells=(LEAF,),
                           scale=(0.7, 1.0), hang=0.2, spread=0.3, out=0.7, face=0.4, up=0.4, roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.09, cells=(LEAF,), scale=(0.9, 1.1),
                           hang=0.2, spread=0.3, out=0.7, face=0.4, up=0.4, roll=20.0, bend=0.0),
        bark_key=lambda br, s, r, z: "twig", bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


# (name, seed, spec maker, impostor height in px)
VARIANTS = [
    ("Sequoia01", 5, monarch, 2048),
    ("Sequoia02", 17, mature, 2048),
    ("Sequoia03", 29, young, 1024),
    ("Sequoia04", 41, old, 1536),
    ("SequoiaSapling", 59, sapling, 1024),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """SequoiaSeed_Icon.png (160 x 160, in Trees/Sequoia; gen_nature.py copies it into the mod's item icons): a round
    sequoia cone on a sprig of scale-leaf plumes, under zkit's icon lights, drawn like vanilla's pine cone seed."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(shade=0.12)
    rnd = random.Random(3)
    m = tr.Mesh()
    plume(m, rnd, Vector((0.05, -0.06, 0.0)), Vector((-0.55, 1.0, 0.0)), 0.15, 1, 0.0026, 1500)
    cone(m, rnd, Vector((0.01, 0.045, 0.02)), Vector((-0.3, -1.0, 0.1)), 0.075)
    obj = m.build("SequoiaSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (-0.03, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "SequoiaSeed_Icon.png"), hide=())
    print("[sequoia] icon written")


# ---------------------------------------------------------------- previews of a tree this tall

def proxy_pine(x, y, height=23.0):
    """A stand-in for a vanilla pine (23 m, 0.5 m trunk, dark cone crown) beside the big trees, for scale."""
    import bpy
    mat, g = tr.tk.new_material("ProxyPine")
    tr.tk.finish(mat, g, (0.03, 0.06, 0.03), 0.0, 0.9)
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=4.0, radius2=0.0, depth=height * 0.75,
                                    location=(x, y, height * 0.25 + height * 0.375))
    crown = bpy.context.active_object
    crown.name = "ProxyCrown"
    crown.data.materials.append(mat)
    trunk_mat, g = tr.tk.new_material("ProxyTrunk")
    tr.tk.finish(trunk_mat, g, (0.1, 0.07, 0.05), 0.0, 0.9)
    trunk_o = tr.tk.cylinder("ProxyTrunk", 0.4, 0.0, height * 0.5, trunk_mat, segments=12, center=(x, y))
    return [crown, trunk_o]


def preview_big(built, figure):
    """The four tall trees together at game distances (a pine proxy for scale), from 110 m and from 45 m, plus the
    monarch's trunk from 10 m."""
    import bpy
    rnd = random.Random(4)
    spots = {"Sequoia01": (0.0, 14.0), "Sequoia02": (-26.0, 8.0), "Sequoia03": (24.0, 6.0), "Sequoia04": (-48.0, 12.0)}
    copies = []
    for name, tree, lods, size in built:
        if name in spots:
            x, y = spots[name]
            copies.append(tr._copy(lods[0], (x, y, 0.0), rnd.uniform(0.0, TAU)))
    pines = proxy_pine(10.0, -2.0) + proxy_pine(40.0, 8.0, 26.0) + proxy_pine(-14.0, -3.0, 19.0)
    saved = tr._only(copies + pines)
    tr.place(figure, 4.0, -6.0)
    tr._shot("seqgrove", (-8.0, -125.0, 18.0), (-8.0, 8.0, 24.0), os.path.join(PREVIEWS, "sequoia_grove.png"),
             lens=35, res=(1600, 900), samples=48)
    tr._shot("seqgrovenear", (-3.0, -42.0, 1.7), (-3.0, 12.0, 26.0), os.path.join(PREVIEWS, "sequoia_grove_near.png"),
             lens=22, res=(1000, 1100), samples=48)
    tr._shot("seqtrunk10", (4.0, -12.0, 2.5), (0.0, 14.0, 4.5), os.path.join(PREVIEWS, "sequoia_trunk10m.png"),
             lens=30, res=(1000, 1100), samples=64)
    tr._restore(saved)
    for c in copies + pines:
        bpy.data.objects.remove(c)


def preview_scar(name, lods, tree, figure):
    """The fire scar from 6 m and from 2.5 m, on the side it faces."""
    saved = tr._only([lods[0]])
    t = tree.trunks[0]
    out = Vector((t.scar_dir.x, t.scar_dir.y, 0.0)).normalized()
    base = t.point_at_height(1.0)
    tr.place(figure, base.x + out.x * 4.0 - out.y * 1.5, base.y + out.y * 4.0 + out.x * 1.5)
    tr._shot("scar6", base + out * 7.0 + Vector((0, 0, 0.7)), base + Vector((0, 0, 2.2)),
             os.path.join(PREVIEWS, "sequoia04_scar6m.png"), lens=35, res=(1000, 1000), samples=64)
    tr._shot("scar25", base + out * 3.6 + Vector((0, 0, 0.5)), base + Vector((0, 0, 2.0)),
             os.path.join(PREVIEWS, "sequoia04_scar25m.png"), lens=35, res=(1000, 1000), samples=64)
    tr._restore(saved)


def scale_trunk_radii(path, name, k):
    """The collision capsules are drawn 0.95 of the radius in trunks.txt (NatureTreeBuilder): scaled up a little the
    capsule reaches within about 2 % of a flute's crest (the valleys, up to 11 % under the crest, leave a wall of air
    of a few centimetres, never a trunk to clip into)."""
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        p = ln.split()
        if p and p[0] == name:
            for i in range(4, len(p), 4):
                p[i] = "%.4f" % (float(p[i]) * k)
            ln = " ".join(p)
        out.append(ln)
    with open(path, "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(out) + NL)


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
    mats = {"bark": tr.textured("SequoiaBark", paths("SequoiaBark")),
            "twig": tr.textured("SequoiaBarkTwig", paths("SequoiaBarkTwig")),
            "burn": tr.textured("SequoiaBarkBurn", paths("SequoiaBarkBurn")),
            "leaves": tr.textured("SequoiaLeaves", paths("SequoiaLeaves"), cutout=True, translucent=0.25)}
    figure = tr.stage()
    built = []
    for name, seed, make, imp_height in VARIANTS:
        if ONLY and name not in ONLY:
            continue
        tree = tr.grow(make(), seed, name)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER, height=imp_height))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        scale_trunk_radii(os.path.join(TREES, "trunks.txt"), name, 1.03)
        print("[sequoia] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    for name, tree, lods, size in built:
        if name == "Sequoia01":
            tr.preview_bark("sequoia01", lods[0], PREVIEWS, figure)
            tr.preview_lods("sequoia01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
        if name == "Sequoia04":
            preview_scar(name, lods, tree, figure)
    preview_big(built, figure)
    if STEPS == "all":
        make_icon()
    print("[sequoia] done")


main()
