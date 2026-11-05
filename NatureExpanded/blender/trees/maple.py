"""Sugar maple (Acer saccharum) in summer, on treekit.py (birch.py is the worked example; TREES.md has the rules).

Grey bark in long irregular plates curling away from the trunk along their edges (shaggy on old trees), a short stout
trunk splitting from 5 to 8 m into big ascending limbs under a dense rounded crown, and five-lobed leaves 9 to 14 cm
across on long stalks, held out flat in layers. Its seeds are paired winged samaras, the "helicopters".

    blender -b --factory-startup --python trees/maple.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps as
birch.py's: `all`, `textures` (bark and leaves, then stop), `bark` (the bark, then the trees), `bark-textures`, `atlas`
(the leaves, then the trees), `trees`, `icon`. It writes Trees/Maple/ (the bark and leaf textures, Maple01..04 and the
seedling MapleSapling with their impostors, MapleSeed_Icon.png), the Maple lines of Trees/trees.txt and trunks.txt and
the previews. Built at its size in game (the Unity builder scales only the birch).
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
FOLDER = os.path.join(TREES, "Maple")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# MapleBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (1.9 m on Maple01's 60 cm
# trunk), drawn at its size on that trunk (about 22 px per cm). MapleBarkTwig: 512 x 1024, the smooth grey-brown bark
# of branches under 1.2 cm radius, once round them.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)  # radii per repeat up a tube: 2 pi
R_DESIGN = 30.0  # cm: the trunk the bark is drawn for (Maple01's, 1 m up)
PX = WRAPS * W / (TAU * R_DESIGN)  # pixels per cm round and up that trunk
RELIEF = PX / 13.0  # birch's first bark's 13 px per cm: slopes and cavities keep their size in cm
TWIST = 0.3
# Mean albedo (sRGB) the textures are graded to: a mid grey a touch browner than birch's white, beside vanilla's
# grey-brown pines; leaves a clean mid green a little deeper than birch's
BARK_MEAN = (110, 108, 104)
LEAF_MEAN = (70, 92, 44)
TWIG_R = 0.012
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def maple_bark(r, h=H, w=W, px=PX):
    """Old sugar maple bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm:
    long irregular plates 4 to 9 cm across and 20 to 50 cm tall between shallow dark furrows, each curling away from
    the trunk along one edge (catching the light there, shading the furrow beside it), split here and there across,
    in greys from silvery to brown-grey, finely fibrous, with pale lichen crusts and a few plates flaked off to the
    brown underbark."""
    cm = px
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    warp = ((tr.fbm(r, h, w, (2.5 * cm, 9 * cm), 3) - 0.5) * 1.4 * cm,
            (tr.fbm(r, h, w, (2.5 * cm, 9 * cm), 3) - 0.5) * 4.0 * cm)
    edge, plate, _, cx = tr.cells(r, h, w, 6 * cm, 5.5, warp)
    split, piece, _, _ = tr.cells(r, h, w, 4 * cm, 2.5, warp)
    n = plate.max() + 1
    shade, tilt, flaked = r.random(n)[plate], (r.random(n) * 2.0 - 1.0)[plate], r.random(n)[plate] < 0.025
    # Across each plate, -1 at one edge and 1 at the other (about), for the curl
    across = np.clip((X + warp[0] - cx) / (3.0 * cm), -1.0, 1.0)
    del Y, X, cx

    wobble = tr.fbm(r, h, w, (1.0 * cm, 4 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.2 + 0.4 * wobble) * cm, edge)
    shoulder = 1.0 - tr.smoothstep(0.0, 1.8 * cm, edge)
    crack = ((1.0 - tr.smoothstep(0.0, (0.04 + 0.06 * wobble) * cm, split))
             * tr.smoothstep(0.55, 0.7, tr.fbm(r, h, w, (3 * cm, 8 * cm), 3)) * 0.5)
    body = tr.smoothstep(0.0, 1.2 * cm, edge)
    curl = np.clip(tilt * across, 0.0, 1.0) ** 2 * body
    streak = tr.fbm(r, h, w, (0.2 * cm, 2.5 * cm), 3)
    coarse = tr.fbm(r, h, w, (0.6 * cm, 6 * cm), 3)
    grit = tr.fbm(r, h, w, (0.2 * cm, 0.2 * cm), 3)
    mottle = tr.fbm(r, h, w, (1.5 * cm, 3 * cm), 4)
    # Checks: short splits across the plates' faces
    checks = np.zeros((h, w))
    for _ in range(int((w / cm) * (h / cm) * 0.02)):
        tr.stamp_lens(checks, r.uniform(0, w), r.uniform(0, h), r.uniform(0.8, 3.0) * cm,
                      max(1.2, r.uniform(0.05, 0.12) * cm), r.uniform(0.5, 1.0), ends=0.8)
    checks *= body
    # Flakes: the plates' faces scaled into small loose flakes, each a shade of its own, their edges a little raised
    flake_edge, flake, _, _ = tr.cells(r, h, w, 1.6 * cm, 1.8, warp)
    flake_shade = r.random(flake.max() + 1)[flake]
    flake_rim = (1.0 - tr.smoothstep(0.0, 0.12 * cm, flake_edge)) * tr.smoothstep(0.4, 0.6, mottle) * body
    del flake_edge, flake

    col = tr.mix((0.36, 0.345, 0.32), (0.6, 0.59, 0.565),
                 0.3 * shade + 0.2 * mottle + 0.15 * streak + 0.1 * coarse + 0.1 * grit + 0.15 * flake_shade)
    brown = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (12 * cm, 20 * cm), 3))
    col = tr.mix(col, col * np.array((1.06, 0.98, 0.9)), brown[..., None] * 0.8)
    # The curled edges weathered paler, the furrows and cracks dark, the flaked plates brown underbark
    col = tr.mix(col, (0.68, 0.67, 0.65), curl * 0.35)
    under = tr.mix((0.34, 0.28, 0.23), (0.44, 0.37, 0.31), mottle)
    col = tr.mix(col, under, (flaked * body)[..., None] * 0.9)
    lichen = (tr.smoothstep(0.76, 0.9, tr.fbm(r, h, w, (1.5 * cm, 1.5 * cm), 4))
              * tr.smoothstep(0.5, 0.75, tr.fbm(r, h, w, (14 * cm, 18 * cm), 3)) * body)
    col = tr.mix(col, tr.mix((0.5, 0.54, 0.47), (0.62, 0.65, 0.57), grit), lichen * 0.45)
    col = col * (1.0 - 0.3 * shoulder)[..., None]
    col = tr.mix(col, (0.2, 0.18, 0.16), checks * 0.6)
    col = tr.mix(col, (0.3, 0.285, 0.26), flake_rim * 0.5)
    col = tr.mix(col, (0.25, 0.235, 0.22), np.maximum(furrow, crack))

    height = (1.5 * body + 1.6 * curl + 0.5 * mottle + 0.45 * streak + 0.3 * coarse + 0.3 * grit + 0.3 * lichen
              + 0.35 * flake_shade * body - 0.4 * flake_rim
              - 2.0 * furrow - 0.8 * crack - 0.7 * checks - 0.6 * (flaked * body))
    rough = 0.86 + 0.06 * (grit - 0.5) + 0.05 * lichen
    occ = tr.cavity(height, 4.0 * RELIEF, 0.25)
    # The crevices' shade in the colour too: the game's light reads the occlusion only from the sky
    col = col * (0.72 + 0.28 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: smooth grey-brown, a little glossy, with short pale lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.26, 0.22, 0.18), (0.42, 0.38, 0.33), tone)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.9)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.08, 0.3) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=0.8)
    col = tr.mix(col, (0.62, 0.58, 0.5), lent * 0.8)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.7
    rough = 0.6 + 0.1 * tone
    return np.clip(col, 0.0, 1.0), height, rough, tr.cavity(height, 3.0, 0.2)


def make_bark():
    """Writes MapleBark_* and MapleBarkTwig_*, the bark graded to BARK_MEAN."""
    r = np.random.default_rng(11)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = maple_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("MapleBark", col, height, rough, occ, RELIEF)
    save("MapleBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square, as birch's: four sprays (512 x 640) along the top, two cluster cells (1024 x 1280) for LOD2, and one
# leaf (128 square) for the seedling, past the decal strip (u under .375, v under .0625).

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"
# The five lobes: (angle off the midrib in radians, length in leaf lengths, half-width in radians)
LOBES = ((0.0, 1.0, 0.75), (1.0, 0.86, 0.75), (-1.0, 0.86, 0.75), (1.9, 0.46, 0.6), (-1.9, 0.46, 0.6))


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.5, 0.62))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.4, 1.75))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.14, 0.14), pad=8)
    return atlas


def outline(theta, teeth):
    """The leaf's edge at angle theta (0 along the midrib) as a distance from the stalk in leaf lengths: a broad
    blade (its rounded U sinuses about halfway in) with five broad pointed lobes on the main veins, each with a
    couple of big teeth up its sides, and the base curving in to the stalk: about as wide as long. `teeth` jitters
    the teeth per leaf."""
    r = 0.47 * max(0.0, math.cos(theta * 0.6)) ** 0.5 + 0.04
    for i, (a, length, half) in enumerate(LOBES):
        x = (theta - a) / half
        if abs(x) < 1.0:
            lobe = length * (1.0 - abs(x)) ** 0.9
            # Big teeth: points on the lobe's sides, about a third and three fifths of the way out
            for t, size in ((0.32 + teeth[i] * 0.05, 0.07), (0.58 + teeth[i] * 0.05, 0.06)):
                lobe += size * length * max(0.0, 1.0 - abs(abs(x) - t) / 0.06)
            r = max(r, lobe)
    return r


def palm_leaf(m, base, direction, normal, length, rnd, key="leaf", rings=4, spokes=96):
    """A five-lobed maple leaf of real geometry from its stalk's end `base`, the midrib along `direction`, facing
    `normal`, `length` long (it is about as wide): a fan of spokes round the stalk, out to the edge, cupped a little
    and its lobe tips drooping. Each vertex gets "leaf" = (across, along, a per-leaf random) in leaf lengths, so the
    material draws the five main veins from the stalk."""
    d = Vector(direction).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    teeth = [rnd.uniform(-1.0, 1.0) for _ in LOBES]
    cup, droop, rv = rnd.uniform(0.04, 0.1), rnd.uniform(0.05, 0.14), rnd.random()
    span = 2.45
    centre = m.v(Vector(base), leaf=(0.0, 0.0, rv))
    ring_ids = []
    for k in range(spokes + 1):
        th = -span + 2.0 * span * k / spokes
        rr = outline(th, teeth)
        way = d * math.cos(th) + side * math.sin(th)
        row = []
        for j in range(1, rings + 1):
            f = rr * j / rings
            lift = cup * f * f - droop * max(0.0, f - 0.5) ** 2 * 2.0
            p = Vector(base) + way * (f * length) + nl * (lift * length)
            row.append(m.v(p, leaf=(math.sin(th) * f, math.cos(th) * f, rv)))
        ring_ids.append(row)
    uv = ((0, 0),) * 4
    for k in range(spokes):
        a, b = ring_ids[k], ring_ids[k + 1]
        m.tri(centre, b[0], a[0], uv[:3], key)
        for j in range(rings - 1):
            m.quad(a[j], b[j], b[j + 1], a[j + 1], uv, key)


def leaf_materials(vein=0.4, shade=0.0):
    """The sprays' own materials (rendered into the atlas, not exported): leaf, twig and petiole. `vein` is how much
    paler the veins are and `shade` darkens the leaf (the icon, drawn small, wants both stronger)."""
    mat, g = tr.tk.new_material("MapleLeafSrc")
    x, y, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    radius = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    angle = g.math("ARCTAN2", x, y)
    # Each leaf its own shade: mostly a clean mid green, some yellower, a few darker
    base = g.mix(g.ramp(rv, 0.2, 0.95), (0.075, 0.2, 0.03), (0.15, 0.29, 0.04))
    base = g.mix(g.ramp(rv, 0.14, 0.0), base, (0.05, 0.12, 0.022))
    hi = g.math("MULTIPLY", g.ramp(g.noise(24.0, detail=3.0), 0.5, 0.85), 0.45)
    col = g.mix(hi, base, (0.2, 0.32, 0.05))
    # The five main veins out from the stalk along the lobes, and finer ones off them, paler
    veins = None
    for a, length, _ in LOBES:
        off = g.math("SUBTRACT", angle, a)
        dist = g.math("ABSOLUTE", g.math("MULTIPLY", radius, g.math("SINE", off)))
        near = g.math("MULTIPLY", g.ramp(dist, 0.012, 0.0), g.ramp(g.math("ABSOLUTE", off), 0.9, 0.5))
        near = g.math("MULTIPLY", near, g.ramp(radius, length * 0.95, length * 0.5))
        veins = near if veins is None else g.math("MAXIMUM", veins, near)
    side = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", radius, g.math("MULTIPLY", g.math("ABSOLUTE", angle), 0.12)), 9.0))
    side = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", side, 0.5)), 0.44, 0.5), 0.45)
    veins = g.math("MAXIMUM", veins, side)
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.22, 0.34, 0.09))
    if shade:
        col = g.mix(shade, col, (0.015, 0.04, 0.01))
    under = g.mix(g.math("MULTIPLY", veins, 0.5), g.mix(g.ramp(rv, 0.1, 0.9), (0.2, 0.29, 0.12), (0.27, 0.34, 0.16)),
                  (0.34, 0.4, 0.22))
    col = g.mix(back, col, under)
    rough = g.mixf(back, 0.45, 0.68)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.3 + vein - 0.4, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("MapleTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.08, 0.06, 0.045), (0.16, 0.13, 0.1))
    tr.tk.finish(mat, g, col, 0.0, 0.55)
    twig = tr.signals(mat, col, 0.55)

    mat, g = tr.tk.new_material("MaplePetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    col = g.mix(g.ramp(t, 0.0, 0.85), (0.2, 0.06, 0.03), (0.15, 0.2, 0.05))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    pet = tr.signals(mat, col, 0.5)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, way, size, face=(0.0, 0.25, 1.0)):
    """A leaf on its long stalk from p, heading `way` (in the card's plane, x right, y up, facing +z), held out flat
    and facing the card's front, tilted at random; one in eight turned to show its paler back."""
    stalk = size * rnd.uniform(0.45, 0.7)
    w = Vector(way).normalized()
    q = p + w * stalk + Vector((0.0, 0.0, rnd.uniform(0.0, 0.02)))
    tr.twig(m, [p, p.lerp(q, 0.5) + Vector((0.0, -0.004, 0.003)), q], [0.0014, 0.0012, 0.0011], "petiole", 4)
    nl = Vector(face) + Vector((rnd.gauss(0.0, 0.3), rnd.gauss(0.0, 0.25), 0.0))
    if rnd.random() < 0.12:
        nl = Vector((nl.x, nl.y, -0.6))
    palm_leaf(m, q, (w + Vector((rnd.gauss(0.0, 0.2), rnd.gauss(0.0, 0.2), 0.0))).normalized(), nl, size, rnd)


def spray(m, rnd, start, direction, length, size=1.0, side_twigs=2):
    """A maple twig hanging from `start`: opposite pairs of leaves every 6 to 9 cm on stalks spreading sideways, a
    tuft of three to five leaves at its tip, and a couple of short leafy side twigs."""
    pts = tr.bend_path(start, direction, length, 0.6, steps=12, down=(0.0, -1.0, 0.0))
    tr.twig(m, pts, [0.004 * (1.0 - 0.5 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 6)
    tw = tr.Branch(pts, [0.004] * len(pts))
    f, i = rnd.uniform(0.12, 0.2), 0
    sides = set(rnd.sample(range(1, 5), min(side_twigs, 4)))
    while f < 0.86:
        p, tan, _ = tw.at(f)
        lat = Vector((-tan.y, tan.x, 0.0)).normalized()
        for s in (-1, 1):
            way = lat * s * 0.8 + tan * 0.35 + Vector((0.0, 0.0, 0.25))
            if i in sides and s == 1:
                spray(m, rnd, p, (lat * s + tan * 0.6).normalized(), length * rnd.uniform(0.35, 0.5), size * 0.9, 0)
            else:
                add_leaf(m, rnd, p, way, size * rnd.uniform(0.1, 0.13))
        f += rnd.uniform(0.17, 0.25)
        i += 1
    p, tan, _ = tw.at(1.0)
    for k in range(rnd.randint(3, 5)):
        way = tr.rotate(tan, (0.0, 0.0, 1.0), rnd.uniform(-70.0, 70.0)) + Vector((0.0, 0.0, 0.3))
        add_leaf(m, rnd, p, way, size * rnd.uniform(0.09, 0.12))


def make_atlas(atlas, render=True):
    """Builds the sprays, clusters and the single leaf, fits their cells; with `render`, renders them into the atlas,
    grades the leaves and saves it (without, the cells are only measured: the geometry is the same every run)."""
    mats = leaf_materials()
    rnd = random.Random(23)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.15, 0.35), -1.0, rnd.uniform(-0.1, 0.1))),
              rnd.uniform(0.42, 0.52), side_twigs=(2, 1, 2, 1)[i])
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
        stems = [tr.bend_path(Vector(), Vector((side * 0.5, -1.0, 0.1)), rnd.uniform(0.85, 1.0), 0.4, steps=10,
                              down=(0.0, -1.0, 0.0))]
        main_stem = tr.Branch(stems[0], [0.008] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.65, -side)):
            p, tan, _ = main_stem.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.4, 0.55), 0.5, steps=8, down=(0.0, -1.0, 0.0)))
        for k, st in enumerate(stems):
            r0 = 0.009 if k == 0 else 0.006
            tr.twig(m, st, [r0 * (1.0 - 0.6 * i / (len(st) - 1)) for i in range(len(st))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        for k, st in enumerate(stems):
            br = tr.Branch(st, [0.006] * len(st))
            for j in range(9 if k == 0 else 5):
                f = 0.08 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / (9 if k == 0 else 5)
                p, tan, _ = br.at(f)
                c = sprays[rnd.randrange(len(sprays))].copy()
                tr.tk.link(c)
                spin = (j % 2 * 2 - 1) * rnd.uniform(10.0, 70.0)
                rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-50, 50)), 4, "Y")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 4, "X"))
                c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.75, 1.0), 4)
                objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    # One leaf on its stalk, hanging from the cell's top
    m = tr.Mesh()
    end = Vector((0.003, -0.05, 0.0))
    tr.twig(m, [Vector(), Vector((0.002, -0.025, 0.002)), end], [0.0014, 0.0012, 0.0011], "petiole", 4)
    palm_leaf(m, end, Vector((0.05, -1.0, 0.0)), Vector((0.0, 0.2, 1.0)), 0.11, random.Random(5))
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), LEAF_MEAN)
    out = atlas.save(FOLDER, "MapleLeaves")
    atlas.preview(os.path.join(PREVIEWS, "maple_atlas.png"))
    for c in atlas.cells.values():
        print("[maple] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("MapleLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """The maple crown's envelope up the limbs' span on the trunk: limbs long all the way up (the top ones climb to
    make the dome's top), a little shorter at the very bottom and top."""
    return 0.8 + 0.2 * math.sin(math.pi * min(1.0, t) ** 0.9)


def maple(trunks, limbs=11, reach=1.0, crown=0.32, favor=None, inner=0.0, budget=12000, twig_density=1.8,
          stubs=(2, 4), card_scale=(1.05, 1.35), angle=(38.0, 22.0)):
    """A sugar maple's TreeSpec. Decurrent: each trunk (tr.Trunk, one or a fork) runs only about half the tree's
    height and gives out among `limbs` big limbs from `crown` of its height up, which climb at `angle` (degrees off
    the trunk at the bottom and top of the span) and fork now and then to make the crown's broad dome; `reach` scales
    their length, `favor` lengthens them toward the sunny side, `inner` shortens them into a fork's middle;
    `card_scale` is the spray cards' size range."""
    limbs_lv = tr.Level(count=limbs, span=(crown, 1.0), length=(8.0 * reach, 11.0 * reach), shape=crown_shape,
                        angle=angle[0], angle_tip=angle[1], angle_vary=10.0, radius=0.7, radius_length=0.7,
                        radius_max=0.2, tip_radius=0.006, step=0.45, gravitropism=0.08, droop=0.25, wander=0.25,
                        outward=0.3, split=0.08, split_angle=24.0, favor=favor, inner=inner, sides=(6, 5, 4),
                        seg=(1.2, 1.8, 2.8), min_len=(0.0, 0.0, 1.5))
    branches = tr.Level(per_meter=twig_density, span=(0.1, 0.97), length=(1.6 * reach ** 0.5, 3.6 * reach ** 0.5),
                        shape="tapered", angle=60.0, angle_tip=45.0, angle_vary=12.0, planar=0.2, radius=0.5,
                        radius_length=0.6, radius_max=0.035, tip_radius=0.003, step=0.25, gravitropism=0.12, droop=0.55,
                        wander=0.5, outward=0.35, sides=(3, 3, 0), seg=(1.4, 2.0, 9.0), min_len=(0.0, 1.0, 99.0))
    stubs_lv = tr.Level(count=stubs, span=(0.08, crown - 0.04), length=(0.04, 0.18), angle=70.0, angle_vary=12.0,
                        radius=0.18, radius_length=0.0, radius_max=0.04, tip_radius=0.01, broken=True, step=0.05,
                        droop=0.3, wander=0.2, sides=(9, 6, 0), seg=(0.3, 1.0, 1.0), min_length=0.03)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs_lv, branches], stubs=stubs_lv, budget=budget, bark_budget=4000,
        foliage=tr.Foliage(levels={2: (0.05, 1.0), 1: (0.4, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.04,
                           cells=SPRAYS, scale=card_scale, hang=0.15, spread=0.4, out=0.55, face=0.55, up=0.45,
                           roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.3, 1.0)}, trunk_top=(0.8, 1.0), spacing=1.0, cells=CLUSTERS,
                           scale=(0.9, 1.2), hang=0.3, spread=0.3, out=0.55, face=0.7, up=0.3, roll=25.0,
                           bend=20.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.35, flare_height=0.5, lobes=(6, 0.14), taper=0.8, tip_radius=0.03, wander=0.08,
                sides=(14, 9, 6), seg=(0.9, 1.8, 3.2), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeMapleSeed in game): a slim green-brown stem about 0.6 m tall
    with a couple of short side shoots, hung with single leaves (the atlas's Leaf cell), all twig bark."""
    shoots = tr.Level(count=(2, 4), span=(0.35, 0.85), length=(0.08, 0.18), shape="tapered", angle=50.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.5, droop=0.2, wander=0.4, floor=0.02, phyllo="opposite", sides=(4, 3, 0),
                      seg=(0.05, 0.1, 9.0), min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.6, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0014,
                         lean=(0.03, 0.02), bow=0.3, wander=0.02, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.045, cells=(LEAF,),
                           scale=(0.55, 0.85), hang=0.1, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.08, cells=(LEAF,), scale=(0.8, 1.0),
                           hang=0.15, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, budget=400, lod_share=(0.55, 0.3))


VARIANTS = [
    # Big and round, about 21 m: a stout trunk giving out at 11 m among big climbing limbs
    ("Maple01", 7, lambda: maple([trunk(height=11.5, radius=0.3, lean=(0.3, 0.2), bow=0.2)], limbs=13)),
    # Forked low: two trunks from one base, about 19 m, their crowns sharing one dome
    ("Maple02", 19, lambda: maple([trunk(height=10.0, radius=0.22, base=(0.12, 0.0), lean=(1.6, 0.5), bow=0.3,
                                         sides=(12, 8, 5)),
                                   trunk(height=9.0, radius=0.2, base=(-0.12, 0.02), lean=(-1.5, -0.4), bow=0.35,
                                         sides=(12, 8, 5))],
                                  limbs=8, reach=0.85, crown=0.3, inner=0.55, stubs=(1, 3))),
    # Narrower, about 16 m: its limbs climbing steeper
    ("Maple03", 29, lambda: maple([trunk(height=9.0, radius=0.21, lean=(-0.5, 0.3), bow=0.25)],
                                  limbs=11, reach=0.72, crown=0.34, budget=9500, angle=(30.0, 16.0))),
    # Young, about 8 m
    ("Maple04", 43, lambda: maple([trunk(height=4.5, radius=0.09, lean=(0.25, -0.25), bow=0.2, flare=0.2)],
                                  limbs=10, reach=0.38, crown=0.3, budget=6000, twig_density=2.4,
                                  card_scale=(0.9, 1.15))),
    # The seedling a planted seed shows before it grows into Maple04
    ("MapleSapling", 61, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def wing(s):
    """A samara wing's width from the seed (0) to its rounded tip (1): narrow at the seed, widest past the middle."""
    return float(np.interp(s, (0.0, 0.12, 0.35, 0.6, 0.8, 0.92, 1.0), (0.15, 0.35, 0.75, 0.98, 0.9, 0.6, 0.0)))


def samara(m, rnd, seed_at, way, normal, length):
    """One samara: a plump seed at `seed_at` and its veined wing `length` long heading `way`, a thick straight vein
    along its leading edge and the membrane flaring out on one side, facing `normal`."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    # The seed: a fat little spindle
    pts = [seed_at - d * 0.006 + d * (0.012 * i / 6) for i in range(7)]
    radii = [0.0015, 0.0042, 0.0055, 0.0055, 0.0046, 0.003, 0.0016]
    tr.twig(m, pts, radii, "seed", 8)
    # The wing: the leading edge straight, the trailing one curving out
    start = seed_at + d * 0.005
    rows = 18
    lead, trail = [], []
    for i in range(rows + 1):
        s = i / rows
        c = start + d * (s * length) + nl * (0.08 * length * math.sin(math.pi * s))
        lead.append(m.v(c, leaf=(0.0, s, 0.0)))
        trail.append(m.v(c + side * (wing(s) * length * 0.36) - nl * (0.03 * length * s), leaf=(1.0, s, 0.0)))
    uv = ((0, 0),) * 4
    for i in range(rows):
        m.quad(lead[i], lead[i + 1], trail[i + 1], trail[i], uv, "wing")
    tr.twig(m, [start + d * (length * i / 8) + nl * (0.08 * length * math.sin(math.pi * i / 8)) for i in range(9)],
            [0.0009 * (1.0 - 0.6 * i / 8) for i in range(9)], "seed", 4)


def make_icon():
    """MapleSeed_Icon.png (160 x 160, in Trees/Maple; gen_nature.py copies it into the mod's item icons), drawn like
    vanilla's tree seeds: a pair of maple keys (two winged samaras joined at their seeds) lying across a maple leaf,
    under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.6, shade=0.25)
    mat, g = tr.tk.new_material("MapleWingSrc")
    across, along, _ = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Papery wings, pale tan going green toward the seed, flushed red along the leading edge, fine veins fanning out
    col = g.mix(g.ramp(along, 0.0, 0.5), (0.2, 0.25, 0.06), (0.5, 0.36, 0.17))
    col = g.mix(g.math("MULTIPLY", g.ramp(across, 0.18, 0.0), 0.55), col, (0.35, 0.09, 0.05))
    v = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", across, g.math("MULTIPLY", along, 0.6)), 11.0))
    v = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5)), 0.42, 0.5), 0.3)
    col = g.mix(v, col, (0.22, 0.14, 0.07))
    tr.tk.finish(mat, g, col, 0.0, 0.6, g.bump(v, 0.2, 0.0003))
    mats["wing"] = mat
    mat, g = tr.tk.new_material("MapleSeedSrc")
    col = g.mix(g.ramp(g.noise(300.0, detail=3.0), 0.3, 0.7), (0.12, 0.12, 0.03), (0.22, 0.17, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.55, g.bump(g.noise(200.0, detail=4.0), 0.3, 0.0004))
    mats["seed"] = mat

    m = tr.Mesh()
    rnd = random.Random(9)
    # The leaf, its stalk at the bottom right
    end = Vector((0.03, 0.01, -0.035))
    tr.twig(m, [Vector((0.04, 0.01, -0.048)), end], [0.0012, 0.0011], "petiole", 5)
    palm_leaf(m, end, Vector((-0.55, 0.0, 0.83)), Vector((0.1, -1.0, 0.2)), 0.072, rnd)
    # The pair of keys in front, joined at their seeds, wings spread about 70 degrees
    joint = Vector((0.0, -0.02, -0.005))
    for a in (-35.0, 35.0):
        way = Vector((math.sin(math.radians(a + 20.0)), 0.0, math.cos(math.radians(a + 20.0))))
        samara(m, rnd, joint + way * 0.004, way, Vector((0.0, -1.0, 0.15)), 0.048)
    obj = m.build("MapleSeedIcon", mats)
    # Centred: the leaf and keys span about -0.03 to 0.06 across and -0.05 to 0.05 up
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (-0.07, 0.0, 0.32)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.78)
    tr.tk.icon(cam, os.path.join(FOLDER, "MapleSeed_Icon.png"), hide=())
    print("[maple] icon written")


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
    mats = {"bark": tr.textured("MapleBark", paths("MapleBark")),
            "twig": tr.textured("MapleBarkTwig", paths("MapleBarkTwig")),
            "leaves": tr.textured("MapleLeaves", paths("MapleLeaves"), cutout=True, translucent=0.3)}
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
        print("[maple] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("maple01", lods[0], PREVIEWS, figure)
    tr.preview_lods("maple01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("maple", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[maple] done")


main()
