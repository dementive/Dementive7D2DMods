"""Red maple (Acer rubrum), on treekit.py (maple.py is its cousin, the sugar maple, whose techniques it reuses;
TREES.md has the rules).

Smooth pale grey bark on the young, breaking into long narrow dark-furrowed ridges with age; a rounded oval crown of
ascending limbs; smaller leaves than the sugar maple's, 6 to 9 cm, three shallow pointed lobes (and often a small pair
at the base) with sharp teeth all round, on long red stalks, glossy green above and silvery beneath; in autumn the
crimson and scarlet that name it. RedMaple03 is dressed in that autumn colour (its own leaf atlas, RedMapleAutumnLeaves),
the rare flame-red tree among the green ones.

    blender -b --factory-startup --python trees/red_maple.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps as
birch.py's: `all`, `textures` (bark and both leaf atlases, then stop), `bark` (the bark, then the trees),
`bark-textures`, `atlas`, `trees`, `icon`. It writes Trees/RedMaple/ (bark and leaf textures, RedMaple01..04 and the
seedling RedMapleSapling with their impostors, RedMapleSeed_Icon.png), the RedMaple lines of Trees/trees.txt and
trunks.txt and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "RedMaple")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# RedMapleBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii (1.3 m on RedMaple01's 21 cm
# trunk), drawn at its size on that trunk (about 31 px per cm). RedMapleBarkTwig: 512 x 1024, the smooth red-brown
# bark of branches under 1.2 cm radius, once round them.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 21.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.3
# Mean albedo (sRGB, the units Atlas.grade takes): a mid grey a little darker and cooler than the sugar maple's
# (110, 108, 104); summer leaves a clean mid green a little deeper and glossier, the autumn leaves crimson-scarlet at
# about the same luminance as the green ones
BARK_MEAN = (96, 91, 87)
LEAF_MEAN = (64, 90, 50)
AUTUMN_MEAN = (150, 45, 30)
TWIG_R = 0.012
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def red_maple_bark(r, h=H, w=W, px=PX):
    """Red maple bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: smooth
    pale grey ridges 3 to 6 cm across and 30 to 70 cm tall, flat on top and finely fibrous, split by narrow dark
    furrows that run on without the sugar maple's curling plates; here and there a ridge cracked across; a few ridges
    scuffed brown; pale lichen coins."""
    cm = px
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    warp = ((tr.fbm(r, h, w, (3 * cm, 12 * cm), 3) - 0.5) * 1.6 * cm,
            (tr.fbm(r, h, w, (3 * cm, 12 * cm), 3) - 0.5) * 6.0 * cm)
    edge, plate, _, cx = tr.cells(r, h, w, 4.2 * cm, 8.0, warp)
    split, _, _, _ = tr.cells(r, h, w, 3.5 * cm, 3.0, warp)
    n = plate.max() + 1
    shade, brown = r.random(n)[plate], r.random(n)[plate] < 0.12
    del Y, X, cx

    wobble = tr.fbm(r, h, w, (1.0 * cm, 5 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.22 + 0.4 * wobble) * cm, edge)
    shoulder = 1.0 - tr.smoothstep(0.0, 1.0 * cm, edge)
    body = tr.smoothstep(0.0, 0.9 * cm, edge)
    crack = ((1.0 - tr.smoothstep(0.0, (0.04 + 0.06 * wobble) * cm, split))
             * tr.smoothstep(0.58, 0.72, tr.fbm(r, h, w, (3 * cm, 9 * cm), 3)) * 0.6 * body)
    fibre = tr.fbm(r, h, w, (0.12 * cm, 3.5 * cm), 3)
    streak = tr.fbm(r, h, w, (0.3 * cm, 7 * cm), 3)
    grit = tr.fbm(r, h, w, (0.15 * cm, 0.15 * cm), 3)
    mottle = tr.fbm(r, h, w, (2 * cm, 4 * cm), 4)

    col = tr.mix((0.4, 0.385, 0.365), (0.66, 0.65, 0.625),
                 0.28 * shade + 0.2 * mottle + 0.22 * fibre + 0.12 * streak + 0.1 * grit + 0.08 * body)
    col = tr.mix(col, col * np.array((1.08, 0.96, 0.86)), (brown * body)[..., None] * 0.8)
    lichen = (tr.smoothstep(0.78, 0.9, tr.fbm(r, h, w, (1.2 * cm, 1.2 * cm), 4))
              * tr.smoothstep(0.5, 0.75, tr.fbm(r, h, w, (13 * cm, 17 * cm), 3)) * body)
    col = tr.mix(col, tr.mix((0.55, 0.6, 0.5), (0.68, 0.7, 0.6), grit), lichen * 0.45)
    col = col * (1.0 - 0.25 * shoulder)[..., None]
    col = tr.mix(col, (0.19, 0.175, 0.16), np.maximum(furrow, crack))

    height = (1.4 * body + 0.35 * mottle + 0.5 * fibre + 0.3 * streak + 0.25 * grit + 0.3 * lichen
              - 2.0 * furrow - 0.8 * crack + 0.15 * shade * body)
    rough = 0.82 + 0.06 * (grit - 0.5) + 0.05 * lichen
    occ = tr.cavity(height, 4.0 * RELIEF, 0.25)
    col = col * (0.74 + 0.26 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Thin branches' bark at 1 cm radius: smooth and glossy, red-brown (red maple's twigs are red), with short pale
    lenticels."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 1.2 * cm), 4)
    col = tr.mix((0.26, 0.11, 0.08), (0.44, 0.22, 0.16), tone)
    lent = np.zeros((h, w))
    for _ in range(int(area * 0.8)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.08, 0.28) * cm,
                      max(1.5, r.uniform(0.04, 0.08) * cm), r.uniform(0.6, 1.0), ends=0.8)
    col = tr.mix(col, (0.62, 0.52, 0.44), lent * 0.8)
    grain = tr.fbm(r, h, w, (0.6 * cm, 0.2 * cm), 3)
    height = 0.5 * tone + 0.4 * grain + lent * 0.7
    return np.clip(col, 0.0, 1.0), height, 0.5 + 0.1 * tone, tr.cavity(height, 3.0, 0.2)


def make_bark():
    r = np.random.default_rng(37)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = red_maple_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("RedMapleBark", col, height, rough, occ, RELIEF)
    save("RedMapleBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlases
#
# As maple.py's: four sprays (512 x 640) along the top, two cluster cells (1024 x 1280) for LOD2 and one leaf (128
# square) for the seedling, past the decal strip. The summer atlas (RedMapleLeaves) and the autumn one
# (RedMapleAutumnLeaves) are rendered from the same geometry, so they share every cell.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"
# The lobes: (angle off the midrib in radians, length in leaf lengths, half-width in radians). Three shallow pointed
# lobes, a small pair at the base
LOBES = ((0.0, 1.0, 0.62), (0.98, 0.8, 0.6), (-0.98, 0.8, 0.6), (1.95, 0.4, 0.5), (-1.95, 0.4, 0.5))


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.45, 0.56))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.3, 1.6))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.12, 0.12), pad=8)
    return atlas


def outline(theta, teeth):
    """The leaf's edge at angle theta (0 along the midrib) as a distance from the stalk in leaf lengths: a blade about
    as wide as long, broadest at the base, with three shallow lobes (the sinuses only a third of the way in) and a
    small pair at the base; the whole edge cut into sharp teeth pointing toward each lobe's tip. `teeth` shifts
    the teeth per leaf."""
    r = 0.56 * max(0.0, math.cos(theta * 0.55)) ** 0.5 + 0.04
    for i, (a, length, half) in enumerate(LOBES):
        x = (theta - a) / half
        if abs(x) < 1.0:
            r = max(r, length * (1.0 - abs(x)) ** 0.85)
    if r > 0.45:
        ph = (theta * 7.5 + teeth[0] * 3.0) % 1.0
        r *= 1.0 + 0.07 * (ph ** 1.6 - 0.35)
    return r


def palm_leaf(m, base, direction, normal, length, rnd, key="leaf", rings=4, spokes=150):
    """A three-lobed red maple leaf of real geometry from its stalk's end `base`, the midrib along `direction`, facing
    `normal`, `length` long: a fan of spokes round the stalk out to the toothed edge, cupped a little with the lobe
    tips drooping. Each vertex gets "leaf" = (across, along, a per-leaf random) in leaf lengths, so the material
    draws the veins from the stalk."""
    d = Vector(direction).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    teeth = [rnd.uniform(-1.0, 1.0) for _ in LOBES]
    cup, droop, rv = rnd.uniform(0.05, 0.12), rnd.uniform(0.04, 0.12), rnd.random()
    span = 2.4
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


def leaf_materials(vein=0.35, shade=0.0, autumn=False):
    """The sprays' own materials (rendered into the atlas, not exported): leaf, twig and petiole. `vein` is how much
    paler the veins are, `shade` darkens the leaf (the icon, drawn small, wants both stronger), `autumn` dresses it in
    crimson and scarlet."""
    mat, g = tr.tk.new_material("RedMapleLeafSrc")
    x, y, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    radius = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    angle = g.math("ARCTAN2", x, y)
    if autumn:
        # Crimson to scarlet leaf by leaf, a few burgundy, a few flame orange, mottled lighter and darker across
        base = g.mix(g.ramp(rv, 0.15, 0.9), (0.33, 0.012, 0.012), (0.58, 0.045, 0.014))
        base = g.mix(g.ramp(rv, 0.9, 1.0), base, (0.62, 0.15, 0.02))
        base = g.mix(g.ramp(rv, 0.1, 0.0), base, (0.2, 0.008, 0.015))
        hi = g.math("MULTIPLY", g.ramp(g.noise(22.0, detail=3.0), 0.45, 0.85), 0.5)
        col = g.mix(hi, base, (0.64, 0.09, 0.025))
    else:
        # Each leaf its own shade: mostly a glossy mid green, a few yellower, a few darker
        base = g.mix(g.ramp(rv, 0.2, 0.95), (0.055, 0.17, 0.035), (0.1, 0.27, 0.045))
        base = g.mix(g.ramp(rv, 0.12, 0.0), base, (0.035, 0.1, 0.025))
        hi = g.math("MULTIPLY", g.ramp(g.noise(24.0, detail=3.0), 0.5, 0.85), 0.4)
        col = g.mix(hi, base, (0.17, 0.3, 0.05))
    # The three main veins out from the stalk along the lobes, finer ones off them, paler
    veins = None
    for a, length, _ in LOBES[:3]:
        off = g.math("SUBTRACT", angle, a)
        dist = g.math("ABSOLUTE", g.math("MULTIPLY", radius, g.math("SINE", off)))
        near = g.math("MULTIPLY", g.ramp(dist, 0.012, 0.0), g.ramp(g.math("ABSOLUTE", off), 0.9, 0.5))
        near = g.math("MULTIPLY", near, g.ramp(radius, length * 0.95, length * 0.5))
        veins = near if veins is None else g.math("MAXIMUM", veins, near)
    side = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", radius, g.math("MULTIPLY", g.math("ABSOLUTE", angle), 0.12)), 10.0))
    side = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", side, 0.5)), 0.44, 0.5), 0.4)
    veins = g.math("MAXIMUM", veins, side)
    col = g.mix(g.math("MULTIPLY", veins, vein), col, (0.6, 0.12, 0.04) if autumn else (0.2, 0.34, 0.1))
    if shade:
        col = g.mix(shade, col, (0.014, 0.035, 0.01))
    # Silvery beneath
    under = g.mix(g.math("MULTIPLY", veins, 0.4), g.mix(g.ramp(rv, 0.1, 0.9), (0.2, 0.18, 0.15), (0.3, 0.24, 0.2))
                  if autumn else g.mix(g.ramp(rv, 0.1, 0.9), (0.24, 0.32, 0.2), (0.34, 0.42, 0.3)),
                  (0.45, 0.2, 0.15) if autumn else (0.5, 0.58, 0.45))
    col = g.mix(back, col, under)
    rough = g.mixf(back, 0.4, 0.66)
    bump = g.bump(g.math("SUBTRACT", 1.0, veins), 0.3 + vein - 0.35, 0.0004)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    leaf = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("RedMapleTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.1, 0.045, 0.03), (0.2, 0.1, 0.07))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("RedMaplePetioleSrc")
    t = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])[1]
    # Red all the way along, deeper at the twig
    col = g.mix(g.ramp(t, 0.0, 1.0), (0.3, 0.04, 0.03), (0.4, 0.07, 0.04))
    tr.tk.finish(mat, g, col, 0.0, 0.45)
    pet = tr.signals(mat, col, 0.45)
    return {"leaf": leaf, "twig": twig, "petiole": pet}


def add_leaf(m, rnd, p, way, size, face=(0.0, 0.25, 1.0)):
    """A leaf on its long red stalk from p, heading `way` (in the card's plane, x right, y up, facing +z), held out flat
    and facing the card's front, tilted at random; one in eight turned to show its silver back."""
    stalk = size * rnd.uniform(0.5, 0.85)
    w = Vector(way).normalized()
    q = p + w * stalk + Vector((0.0, 0.0, rnd.uniform(0.0, 0.02)))
    tr.twig(m, [p, p.lerp(q, 0.5) + Vector((0.0, -0.004, 0.003)), q], [0.0014, 0.0012, 0.0011], "petiole", 4)
    nl = Vector(face) + Vector((rnd.gauss(0.0, 0.3), rnd.gauss(0.0, 0.25), 0.0))
    if rnd.random() < 0.12:
        nl = Vector((nl.x, nl.y, -0.6))
    palm_leaf(m, q, (w + Vector((rnd.gauss(0.0, 0.2), rnd.gauss(0.0, 0.2), 0.0))).normalized(), nl, size, rnd)


def spray(m, rnd, start, direction, length, size=1.0, side_twigs=2):
    """A red maple twig hanging from `start`: opposite pairs of leaves every 4 to 6 cm on red stalks spreading
    sideways, a tuft of three to five leaves at its tip, and a couple of short leafy side twigs."""
    pts = tr.bend_path(start, direction, length, 0.6, steps=12, down=(0.0, -1.0, 0.0))
    tr.twig(m, pts, [0.0035 * (1.0 - 0.5 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 6)
    tw = tr.Branch(pts, [0.004] * len(pts))
    f, i = rnd.uniform(0.1, 0.16), 0
    sides = set(rnd.sample(range(1, 6), min(side_twigs, 5)))
    while f < 0.86:
        p, tan, _ = tw.at(f)
        lat = Vector((-tan.y, tan.x, 0.0)).normalized()
        for s in (-1, 1):
            way = lat * s * 0.8 + tan * 0.35 + Vector((0.0, 0.0, 0.25))
            if i in sides and s == 1:
                spray(m, rnd, p, (lat * s + tan * 0.6).normalized(), length * rnd.uniform(0.35, 0.5), size * 0.9, 0)
            else:
                add_leaf(m, rnd, p, way, size * rnd.uniform(0.065, 0.088))
        f += rnd.uniform(0.12, 0.17)
        i += 1
    p, tan, _ = tw.at(1.0)
    for k in range(rnd.randint(3, 5)):
        way = tr.rotate(tan, (0.0, 0.0, 1.0), rnd.uniform(-70.0, 70.0)) + Vector((0.0, 0.0, 0.3))
        add_leaf(m, rnd, p, way, size * rnd.uniform(0.06, 0.08))


def make_atlas(atlas, render=True, autumn=False):
    """Builds the sprays, clusters and the single leaf, fits their cells; with `render`, renders them into the atlas,
    grades the leaves and saves it (without, the cells are only measured: the geometry is the same every run, summer
    or autumn)."""
    mats = leaf_materials(autumn=autumn)
    rnd = random.Random(41)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.15, 0.35), -1.0, rnd.uniform(-0.1, 0.1))),
              rnd.uniform(0.4, 0.5), side_twigs=(2, 1, 2, 1)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
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
    m = tr.Mesh()
    end = Vector((0.003, -0.05, 0.0))
    tr.twig(m, [Vector(), Vector((0.002, -0.025, 0.002)), end], [0.0014, 0.0012, 0.0011], "petiole", 4)
    palm_leaf(m, end, Vector((0.05, -1.0, 0.0)), Vector((0.0, 0.2, 1.0)), 0.085, random.Random(5))
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    atlas.grade(SPRAYS + CLUSTERS + (LEAF,), AUTUMN_MEAN if autumn else LEAF_MEAN)
    prefix = "RedMapleAutumnLeaves" if autumn else "RedMapleLeaves"
    out = atlas.save(FOLDER, prefix)
    atlas.preview(os.path.join(PREVIEWS, "red_maple_atlas%s.png" % ("_autumn" if autumn else "")))
    for c in atlas.cells.values():
        print("[red_maple] %s cell %s coverage %.3f" % (prefix, c.name, c.coverage))
    return out


def make_atlases():
    make_atlas(layout())
    tr.reset()
    make_atlas(layout(), autumn=True)


def load_coverage(atlas):
    a = tr.read_image(paths("RedMapleLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """The red maple crown's envelope up the limbs' span on the trunk: a rounded oval, limbs shortest at the bottom
    and the very top, longest about two thirds of the way up the span."""
    return 0.5 + 0.5 * math.sin(math.pi * min(1.0, t * 0.9 + 0.1) ** 0.95)


def red_maple(trunks, limbs=10, reach=1.0, crown=0.3, favor=None, inner=0.0, budget=12000, twig_density=2.2,
              stubs=(1, 3), card_scale=(1.0, 1.3), angle=(34.0, 18.0)):
    """A red maple's TreeSpec. As maple.py's decurrent form, but oval: the trunk (tr.Trunk) runs about 60% of the
    height and gives out among `limbs` ascending limbs from `crown` of its height up at `angle` (degrees off the trunk
    at the bottom and top of the span), forking now and then; `reach` scales their length, `favor` lengthens them
    toward one side, `inner` shortens them into a fork's middle; `card_scale` is the spray cards' size range."""
    limbs_lv = tr.Level(count=limbs, span=(crown, 1.0), length=(8.0 * reach, 11.0 * reach), shape=crown_shape,
                        angle=angle[0], angle_tip=angle[1], angle_vary=9.0, radius=0.7, radius_length=0.7,
                        radius_max=0.15, tip_radius=0.006, step=0.45, gravitropism=0.1, droop=0.18, wander=0.22,
                        outward=0.25, split=0.08, split_angle=22.0, favor=favor, inner=inner, sides=(6, 5, 4),
                        seg=(1.2, 1.8, 2.8), min_len=(0.0, 0.0, 1.5))
    branches = tr.Level(per_meter=twig_density, span=(0.1, 0.97), length=(1.4 * reach ** 0.5, 3.2 * reach ** 0.5),
                        shape="tapered", angle=58.0, angle_tip=42.0, angle_vary=12.0, planar=0.2, radius=0.5,
                        radius_length=0.6, radius_max=0.03, tip_radius=0.003, step=0.25, gravitropism=0.14, droop=0.5,
                        wander=0.5, outward=0.35, sides=(3, 3, 0), seg=(1.4, 2.0, 9.0), min_len=(0.0, 1.0, 99.0))
    stubs_lv = tr.Level(count=stubs, span=(0.08, max(0.1, crown - 0.04)), length=(0.04, 0.16), angle=70.0,
                        angle_vary=12.0, radius=0.18, radius_length=0.0, radius_max=0.035, tip_radius=0.01,
                        broken=True, step=0.05, droop=0.3, wander=0.2, sides=(9, 6, 0), seg=(0.3, 1.0, 1.0),
                        min_length=0.03)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs_lv, branches], stubs=stubs_lv, budget=budget, bark_budget=4000,
        foliage=tr.Foliage(levels={2: (0.05, 1.0), 1: (0.35, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.037,
                           cells=SPRAYS, scale=card_scale, hang=0.15, spread=0.4, out=0.55, face=0.55, up=0.45,
                           roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.3, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.9, cells=CLUSTERS,
                           scale=(0.9, 1.2), hang=0.3, spread=0.3, out=0.55, face=0.7, up=0.3, roll=25.0,
                           bend=20.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.3, flare_height=0.45, lobes=(5, 0.1), taper=0.9, tip_radius=0.03, wander=0.08,
                sides=(14, 9, 6), seg=(0.9, 1.8, 3.2), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeRedMapleSeed in game): a slim red-brown stem about 0.55 m tall
    with a couple of short side shoots, hung with single leaves (the atlas's Leaf cell), all twig bark."""
    shoots = tr.Level(count=(2, 4), span=(0.35, 0.85), length=(0.08, 0.16), shape="tapered", angle=50.0,
                      angle_tip=40.0, radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.5, droop=0.2, wander=0.4, floor=0.02, phyllo="opposite", sides=(4, 3, 0),
                      seg=(0.05, 0.1, 9.0), min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.55, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0014,
                         lean=(0.03, 0.02), bow=0.3, wander=0.02, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.045, cells=(LEAF,),
                           scale=(0.6, 0.9), hang=0.1, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.08, cells=(LEAF,), scale=(0.8, 1.0),
                           hang=0.15, spread=0.4, out=0.7, face=0.4, up=0.6, roll=30.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, budget=400, lod_share=(0.55, 0.3))


# The name of each variant's leaf atlas: RedMaple03 is the flame-red tree
AUTUMN = {"RedMaple03"}

VARIANTS = [
    # Typical, about 15 m: a rounded oval crown
    ("RedMaple01", 7, lambda: red_maple([trunk(height=11.3, radius=0.2, lean=(0.3, 0.2), bow=0.2)], limbs=10,
                                        reach=0.6)),
    # Upright, about 18 m: a tall narrow oval, the limbs steep
    ("RedMaple02", 19, lambda: red_maple([trunk(height=14.6, radius=0.21, lean=(-0.4, 0.3), bow=0.15)], limbs=11,
                                         reach=0.5, crown=0.34, angle=(26.0, 12.0))),
    # In full autumn colour, about 14 m: broader, its crown fuller
    ("RedMaple03", 31, lambda: red_maple([trunk(height=10.2, radius=0.2, lean=(0.5, -0.3), bow=0.25)], limbs=11,
                                         reach=0.64, crown=0.3, budget=12000)),
    # Young, about 8 m
    ("RedMaple04", 43, lambda: red_maple([trunk(height=5.5, radius=0.09, lean=(0.25, -0.25), bow=0.2, flare=0.2)],
                                         limbs=9, reach=0.36, crown=0.3, budget=6000, twig_density=2.6,
                                         card_scale=(0.85, 1.1), stubs=(0, 1))),
    # The seedling a planted seed shows before it grows into RedMaple04
    ("RedMapleSapling", 61, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def wing(s):
    """A samara wing's width from the seed (0) to its rounded tip (1): narrow at the seed, widest past the middle."""
    return float(np.interp(s, (0.0, 0.12, 0.35, 0.6, 0.8, 0.92, 1.0), (0.15, 0.35, 0.72, 0.95, 0.88, 0.6, 0.0)))


def samara(m, rnd, seed_at, way, normal, length):
    """One red maple samara: a plump seed at `seed_at` and its veined red wing `length` long heading `way`, the leading
    edge a thick straight vein and the membrane flaring out on one side, facing `normal`."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    pts = [seed_at - d * 0.006 + d * (0.012 * i / 6) for i in range(7)]
    radii = [0.0015, 0.0042, 0.0055, 0.0055, 0.0046, 0.003, 0.0016]
    tr.twig(m, pts, radii, "seed", 8)
    start = seed_at + d * 0.005
    rows = 18
    lead, trail = [], []
    for i in range(rows + 1):
        s = i / rows
        c = start + d * (s * length) + nl * (0.08 * length * math.sin(math.pi * s))
        lead.append(m.v(c, leaf=(0.0, s, 0.0)))
        trail.append(m.v(c + side * (wing(s) * length * 0.34) - nl * (0.03 * length * s), leaf=(1.0, s, 0.0)))
    uv = ((0, 0),) * 4
    for i in range(rows):
        m.quad(lead[i], lead[i + 1], trail[i + 1], trail[i], uv, "wing")
    tr.twig(m, [start + d * (length * i / 8) + nl * (0.08 * length * math.sin(math.pi * i / 8)) for i in range(9)],
            [0.0009 * (1.0 - 0.6 * i / 8) for i in range(9)], "seed", 4)


def make_icon():
    """RedMapleSeed_Icon.png (160 x 160, in Trees/RedMaple; gen_nature.py copies it into the mod's item icons), drawn
    like vanilla's tree seeds and the sugar maple's: a pair of red-winged keys (a V, about 50 degrees) lying across a
    three-lobed crimson leaf, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(vein=0.4, shade=0.0, autumn=True)
    mat, g = tr.tk.new_material("RedMapleWingSrc")
    across, along, _ = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Red-pink wings flushed deeper along the leading edge, fine veins fanning out, the seed end greener
    col = g.mix(g.ramp(along, 0.0, 0.45), (0.2, 0.2, 0.05), (0.55, 0.1, 0.07))
    col = g.mix(g.math("MULTIPLY", g.ramp(across, 0.18, 0.0), 0.6), col, (0.4, 0.04, 0.03))
    v = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", across, g.math("MULTIPLY", along, 0.6)), 11.0))
    v = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5)), 0.42, 0.5), 0.3)
    col = g.mix(v, col, (0.3, 0.08, 0.05))
    tr.tk.finish(mat, g, col, 0.0, 0.55, g.bump(v, 0.2, 0.0003))
    mats["wing"] = mat
    mat, g = tr.tk.new_material("RedMapleSeedSrc")
    col = g.mix(g.ramp(g.noise(300.0, detail=3.0), 0.3, 0.7), (0.15, 0.1, 0.03), (0.28, 0.16, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.55, g.bump(g.noise(200.0, detail=4.0), 0.3, 0.0004))
    mats["seed"] = mat

    m = tr.Mesh()
    rnd = random.Random(9)
    end = Vector((0.03, 0.01, -0.035))
    tr.twig(m, [Vector((0.042, 0.01, -0.05)), end], [0.0012, 0.0011], "petiole", 5)
    palm_leaf(m, end, Vector((-0.55, 0.0, 0.83)), Vector((0.1, 1.0, -0.2)), 0.07, rnd)
    joint = Vector((0.0, -0.02, -0.005))
    for a in (-25.0, 25.0):
        way = Vector((math.sin(math.radians(a + 22.0)), 0.0, math.cos(math.radians(a + 22.0))))
        samara(m, rnd, joint + way * 0.004, way, Vector((0.0, -1.0, 0.15)), 0.046)
    obj = m.build("RedMapleSeedIcon", mats)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (-0.07, 0.0, 0.32)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.78)
    tr.tk.icon(cam, os.path.join(FOLDER, "RedMapleSeed_Icon.png"), hide=())
    print("[red_maple] icon written")


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
        make_atlases()
        if STEPS == "textures":
            return
        tr.reset()
        atlas = layout()
    else:
        make_atlas(atlas, render=False)
        load_coverage(atlas)
        tr.reset()
    tr.use_atlas(atlas)
    mats = {"bark": tr.textured("RedMapleBark", paths("RedMapleBark")),
            "twig": tr.textured("RedMapleBarkTwig", paths("RedMapleBarkTwig")),
            "leaves": tr.textured("RedMapleLeaves", paths("RedMapleLeaves"), cutout=True, translucent=0.3)}
    mats_autumn = dict(mats, leaves=tr.textured("RedMapleAutumnLeaves", paths("RedMapleAutumnLeaves"), cutout=True,
                                                translucent=0.3))
    figure = tr.stage()
    built = []
    for name, seed, make in VARIANTS:
        tree = tr.grow(make(), seed, name)
        lods = tr.build_lods(tree, mats_autumn if name in AUTUMN else mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[red_maple] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("redmaple01", lods[0], PREVIEWS, figure)
    tr.preview_lods("redmaple01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("red_maple", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[red_maple] done")


main()
