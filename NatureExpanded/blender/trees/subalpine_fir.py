"""Subalpine fir (Abies lasiocarpa) in the snow, on treekit.py (birch.py is the worked example; TREES.md has the
rules; douglas_fir.py the other conifer).

Smooth grey bark with raised resin blisters, scaly here and there; a very narrow spire, dense right down to the ground,
of short drooping limbs in close whorls; dense dark blue-green needles crowding up round the twigs, the sprays laden
with snow like vanilla's winter pines; upright dark purple cones on the top limbs (the seed and its icon). Forms from
a tall spire to a wind-flattened krummholz bush.

    blender -b --factory-startup --python trees/subalpine_fir.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps as
birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`. It writes Trees/SubalpineFir/ (bark
and needle textures, SubalpineFir01..04 and SubalpineFirSapling with their impostors, SubalpineFirSeed_Icon.png), the
SubalpineFir lines of Trees/trees.txt and trunks.txt, and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "SubalpineFir")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# SubalpineFirBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii, drawn at its size on
# SubalpineFir01's 50 cm trunk (about 26 px per cm). SubalpineFirBarkTwig: 512 x 1024, its smooth grey-brown limbs
# under 3 cm radius, once round them.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 25.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.3
# Mean albedo (sRGB): bark a cool light grey; the needles aren't graded (the snow lying on them would be), their
# colours set directly to a dark blue-green
BARK_MEAN = (120, 119, 116)
TWIG_R = 0.03
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    return "bark"


def fir_bark(r, h=H, w=W, px=PX):
    """Subalpine fir bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm:
    thin and smooth, cool grey, mottled at every scale down to single pixels (paler weathered patches, browner ones,
    darker grime streaks run down by rain, sooty dark patches); raised resin blisters 0.4 to 1.6 cm, some burst and
    dribbled amber; faint lenticel lines across; and patches broken into small thin scales, each its own shade, their
    lower edges lifting off, the cracks between them fading out at the patch's edge; grey-green crusts of lichen."""
    cm = px
    area = (w / cm) * (h / cm)
    Y = np.mgrid[0:h, 0:w][0].astype(np.float64)
    patch = tr.fbm(r, h, w, (14 * cm, 22 * cm), 3)
    mottle = tr.fbm(r, h, w, (4 * cm, 7 * cm), 5)
    fine = tr.fbm(r, h, w, (0.5 * cm, 0.4 * cm), 3)
    grit = tr.fbm(r, h, w, (0.07 * cm, 0.07 * cm), 2)
    band = tr.fbm(r, h, w, (2.5 * cm, 0.12 * cm), 3)  # fine banding across, as the trunk grew
    streak = tr.fbm(r, h, w, (1.2 * cm, 10 * cm), 4)  # running down
    col = tr.mix((0.3, 0.3, 0.295), (0.64, 0.635, 0.62),
                 0.3 * mottle + 0.18 * patch + 0.2 * fine + 0.2 * grit + 0.12 * band)
    brown = tr.smoothstep(0.58, 0.82, tr.fbm(r, h, w, (9 * cm, 15 * cm), 3))
    col = tr.mix(col, col * np.array((1.1, 1.0, 0.86)), brown[..., None] * 0.75)
    grime = tr.smoothstep(0.5, 0.85, streak) * tr.smoothstep(0.35, 0.65, patch)
    col = tr.mix(col, (0.22, 0.22, 0.215), grime * 0.35)
    soot = tr.smoothstep(0.76, 0.9, tr.fbm(r, h, w, (6 * cm, 9 * cm), 4)) * tr.smoothstep(0.3, 0.6, fine)
    col = tr.mix(col, (0.16, 0.16, 0.155), soot * 0.35)

    # Scaly patches: small thin scales, each a shade of its own, lifting at its lower edge
    warp = ((tr.fbm(r, h, w, (2 * cm, 2 * cm), 3) - 0.5) * 0.8 * cm,
            (tr.fbm(r, h, w, (2 * cm, 2 * cm), 3) - 0.5) * 0.8 * cm)
    sedge, sidx, sy, _ = tr.cells(r, h, w, 1.5 * cm, 0.85, warp)
    n = sidx.max() + 1
    sshade, sopen = r.random(n)[sidx], r.random(n)[sidx]
    scaly = tr.smoothstep(0.6, 0.78, patch * 0.6 + tr.fbm(r, h, w, (5 * cm, 7 * cm), 3) * 0.4)
    gap = (0.04 + 0.1 * sopen) * cm * scaly
    crack = (1.0 - tr.smoothstep(gap * 0.4, gap + 0.05 * cm, sedge)) * tr.smoothstep(0.05, 0.3, scaly)
    lift = np.clip((sy - Y) / (0.9 * cm), -1.0, 1.0) * 0.5 + 0.5  # 0 at a scale's top, 1 at its lower edge (rows run up)
    lift = lift * tr.smoothstep(0.0, 0.25 * cm, sedge)
    col = tr.mix(col, col * (0.8 + 0.4 * sshade)[..., None], scaly * 0.8)
    col = tr.mix(col, col * 1.12, (lift * scaly * 0.5))
    col = tr.mix(col, (0.17, 0.165, 0.16), crack * 0.55)

    # Resin blisters: raised, a shade paler, a darker ring of stain round them; a few burst and dribbled resin down
    blister = np.zeros((h, w))
    resin = np.zeros((h, w))
    for _ in range(int(area * 0.01)):
        x, y = r.uniform(0, w), r.uniform(0, h)
        size = r.uniform(0.4, 1.6) * cm
        tr.stamp_lens(blister, x, y, size, size * r.uniform(0.55, 0.85), 1.0, ends=0.5)
        if r.random() < 0.22:
            length = r.uniform(1.0, 4.0) * cm
            k = tr.lens(max(1.5, 0.18 * size), length, ends=1.0)
            tr.stamp(resin, x, y + length * 0.5, k * r.uniform(0.6, 1.0))
    dome = tr.blur(blister, 0.2 * cm)
    ring = np.clip(tr.blur(blister, 0.35 * cm) - blister, 0.0, 1.0)
    # Lit from above: a highlight on the dome, its shadow just under it
    shadow = np.clip(np.roll(dome, -int(0.25 * cm), axis=0) - dome, 0.0, 1.0)
    col = tr.mix(col, col * 1.2, dome * 0.7)
    col = col * (1.0 - 0.35 * shadow)[..., None]
    col = tr.mix(col, (0.22, 0.2, 0.18), ring * 0.4)
    col = tr.mix(col, (0.5, 0.31, 0.09), resin * 0.85)

    # Faint lenticel lines across
    lines = np.zeros((h, w))
    for _ in range(int(area * 0.05)):
        tr.stamp_lens(lines, r.uniform(0, w), r.uniform(0, h), r.uniform(0.5, 2.2) * cm, max(1.2, 0.07 * cm),
                      r.uniform(0.35, 0.8), ends=0.8)
    col = tr.mix(col, (0.24, 0.235, 0.23), lines * 0.55)
    lichen = (tr.smoothstep(0.78, 0.9, tr.fbm(r, h, w, (1.2 * cm, 1.2 * cm), 4))
              * tr.smoothstep(0.5, 0.75, tr.fbm(r, h, w, (15 * cm, 20 * cm), 3)))
    lichen *= 0.6 + 0.4 * grit
    col = tr.mix(col, (0.52, 0.58, 0.47), lichen * 0.5)

    height = (0.35 * mottle + 0.35 * fine + 0.25 * grit + 0.15 * band + 1.6 * dome + 0.4 * resin - 0.5 * lines
              + scaly * (0.5 * lift + 0.3 * sshade) - 0.9 * crack + 0.25 * lichen)
    rough = 0.74 + 0.08 * (grit - 0.5) - 0.2 * dome - 0.45 * resin + 0.08 * scaly
    occ = tr.cavity(height, 4.0 * RELIEF, 0.3)
    col = col * (0.78 + 0.22 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    """Limbs' bark at 1 cm radius: smooth grey-brown with a few blisters."""
    cm = w / TAU
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (3 * cm, 2 * cm), 4)
    col = tr.mix((0.28, 0.25, 0.22), (0.42, 0.39, 0.35), tone)
    blisters = np.zeros((h, w))
    for _ in range(int(area * 0.2)):
        tr.stamp_lens(blisters, r.uniform(0, w), r.uniform(0, h), r.uniform(0.15, 0.3) * cm, r.uniform(0.12, 0.22) * cm,
                      1.0, ends=0.5)
    col = tr.mix(col, (0.48, 0.45, 0.4), blisters * 0.4)
    height = 0.4 * tone + 1.2 * tr.blur(blisters, 1.5)
    return np.clip(col, 0.0, 1.0), height, 0.6 + 0.1 * tone, tr.cavity(height, 3.0, 0.2)


def make_bark():
    r = np.random.default_rng(17)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = fir_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("SubalpineFirBark", col, height, rough, occ, RELIEF)
    save("SubalpineFirBarkTwig", *twig_bark(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the needle atlas
#
# As douglas_fir.py's: four snow-laden sprays (512 x 640, one with upright cones), two cluster cells (1024 x 1280) of
# a limb's end for LOD2, one small sprig (128 square) for the seedling.

SPRAYS = ("Spray0", "Spray1", "Spray2", "Spray3")
CLUSTERS = ("Cluster0", "Cluster1")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(SPRAYS):
        atlas.cell(name, 512 * i, 1408, 512, 640, (0.4, 0.5))
    for i, name in enumerate(CLUSTERS):
        atlas.cell(name, 1024 * i, 128, 1024, 1280, (1.2, 1.5))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.14, 0.14), pad=8)
    return atlas


def needle(m, base, way, normal, length, width, rv, age):
    """One flat needle (as douglas_fir.py's): "leaf" = (across, along, random), "age" = how near its twig's tip."""
    d = Vector(way).normalized()
    nl = Vector(normal)
    nl = nl - d * nl.dot(d)
    nl = nl.normalized() if nl.length > 1e-6 else d.orthogonal().normalized()
    side = nl.cross(d)
    rows = []
    for s, wf in ((0.0, 0.55), (0.35, 1.0), (0.8, 0.9), (1.0, 0.45)):
        c = Vector(base) + d * (s * length) + nl * (0.08 * length * s * s)
        rows.append((m.v(c - side * (wf * width * 0.5), leaf=(-1.0, s, rv), age=age),
                     m.v(c + side * (wf * width * 0.5), leaf=(1.0, s, rv), age=age)))
    uv = ((0, 0),) * 4
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        m.quad(a0, a1, b1, b0, uv, "leaf")


def needled(m, rnd, pts, radius, per_m=1100, length=(0.018, 0.028)):
    """A twig with dense needles crowding round it and curving up toward its upper side (+z, the sky when the spray
    lies flat), pointing forward along it."""
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
        # All round, but most toward the upper side: brush-like
        phi = rnd.uniform(-0.3, 1.4)
        radial = (lat * side * math.cos(phi) + up * math.sin(phi)).normalized()
        theta = math.radians(rnd.uniform(40.0, 65.0))
        way = tan * math.cos(theta) + radial * math.sin(theta) + up * 0.25
        L = rnd.uniform(*length) * (1.0 - 0.3 * max(0.0, f - 0.8) / 0.2)
        needle(m, p + radial * radius * 0.8, way, up + radial * 0.3, L, 0.0022, rnd.random(), f)


def snow(m, rnd, pts, coverage=0.2):
    """A dusting of snow caught on a twig: small flattened patches, more and bigger toward the twig's base where more
    catches, about `coverage` of its length (the sprays are seen from above and from the side, so it stays light)."""
    tw = tr.Branch(pts, [0.003] * len(pts))
    n = int(tw.length / 0.06 * coverage + rnd.random())
    for _ in range(n):
        f = rnd.uniform(0.0, 0.7) ** 1.3
        p, tan, _ = tw.at(f)
        size = rnd.uniform(0.006, 0.011) * (1.1 - 0.5 * f)
        lump(m, p + Vector((rnd.gauss(0, 0.0015), rnd.gauss(0, 0.0015), 0.006)), tan, size,
             size * rnd.uniform(0.35, 0.55), stretch=rnd.uniform(2.5, 4.0))


def lump(m, centre, tan, radius, depth, rings=4, segs=8, stretch=1.4):
    """A flattened dome of snow: `radius` across, `stretch` times as long along the twig, `depth` thick, its flat
    side down (-z)."""
    d = Vector(tan)
    d.z = 0.0
    d = d.normalized() if d.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    side = Vector((0.0, 0.0, 1.0)).cross(d)
    rows = []
    for j in range(rings + 1):
        a = (j / rings) * math.pi * 0.5
        rr, zz = radius * math.cos(a), depth * math.sin(a)
        row = []
        for k in range(segs):
            t = k / segs * TAU
            p = Vector(centre) + d * (math.cos(t) * rr * stretch) + side * (math.sin(t) * rr) + Vector((0.0, 0.0, zz))
            row.append(m.v(p, leaf=(math.cos(t), j / rings, 0.0)))
        rows.append(row)
    uv = ((0, 0),) * 4
    for a, b in zip(rows, rows[1:]):
        for k in range(segs):
            k1 = (k + 1) % segs
            m.quad(a[k], a[k1], b[k1], b[k], uv, "snow")


def cone(m, rnd, base, length, up=None, scales=0):
    """An upright subalpine fir cone standing on a twig at `base`: a dark purple barrel, blunt at its top; with
    `scales`, that many broad rounded scales spiralling round it, pressed close, tips curling in (the icon's; the
    atlas's are too small to show them). In the spray's frame the tree's up is +y (the spray hangs along -y), tipped
    a little out of the card toward +z."""
    up = (Vector(up) if up is not None else Vector((rnd.uniform(-0.15, 0.15), 1.0, 0.3))).normalized()
    core = [base + up * (length * i / 8) for i in range(9)]
    shape = [0.75, 0.95, 1.0, 1.0, 1.0, 0.98, 0.92, 0.75, 0.3]
    R = length * 0.21
    tr.twig(m, core, [R * (0.8 if scales else 1.0) * k for k in shape], "cone", 12 if scales else 10)
    _, u, v = tr.basis(up)
    for i in range(scales):
        f = 0.03 + 0.92 * (i + 0.5) / scales
        a = i * tr.GOLDEN + rnd.uniform(-0.1, 0.1)
        out = u * math.cos(a) + v * math.sin(a)
        k = float(np.interp(f, np.linspace(0.0, 1.0, len(shape)), shape))
        p = base + up * (f * length) + out * (R * 0.72 * k)
        sl = length * rnd.uniform(0.15, 0.18) * (0.6 + 0.4 * k)
        tr.blade(m, p, (out * 0.5 + up * 0.87).normalized(), out, sl, sl * 1.4,
                 lambda s: math.sin(math.pi * min(1.0, 0.15 + 0.85 * s)) ** 0.45, "cone", fold=-0.15, arch=0.35,
                 rows=5, rnd_value=rnd.random())


def leaf_materials(shade=0.0):
    """The sprays' own materials: needles ("leaf"), twig, snow, cone."""
    mat, g = tr.tk.new_material("SubalpineNeedleSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    age = g.node("ShaderNodeAttribute", attribute_name="age").outputs["Fac"]
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Dark blue-green with a waxy bloom, some needles bluer; new growth at the tips a little lighter
    base = g.mix(g.ramp(rv, 0.15, 0.95), (0.02, 0.05, 0.04), (0.04, 0.085, 0.07))
    base = g.mix(g.ramp(rv, 0.8, 1.0), base, (0.05, 0.09, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(age, 0.8, 0.95), 0.4), base, (0.08, 0.15, 0.1))
    band = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", across), 0.45)), 0.2, 0.05), 0.5)
    col = g.mix(band, col, (0.14, 0.2, 0.2))
    col = g.mix(back, col, g.mix(band, col, (0.25, 0.3, 0.3)))
    if shade:
        col = g.mix(shade, col, (0.01, 0.02, 0.015))
    rough = g.mixf(back, 0.5, 0.62)
    tr.tk.finish(mat, g, col, 0.0, rough)
    leaf = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("SubalpineTwigSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.06, 0.05, 0.04), (0.13, 0.11, 0.09))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    twig = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("SubalpineSnowSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=4.0), 0.3, 0.8), (0.6, 0.64, 0.7), (0.82, 0.84, 0.88))
    rough = 0.85
    bump = g.bump(g.noise(220.0, detail=5.0), 0.25, 0.001)
    tr.tk.finish(mat, g, col, 0.0, rough, bump)
    snow_mat = tr.signals(mat, col, rough, bump)

    mat, g = tr.tk.new_material("SubalpineConeSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(g.noise(400.0, detail=3.0), 0.3, 0.7), (0.045, 0.03, 0.035), (0.1, 0.066, 0.072))
    # Scale to scale a little lighter or darker, their lips paler, beads of resin on a few
    col = g.mix(g.math("MULTIPLY", g.ramp(rv, 0.2, 1.0), 0.5), col, (0.075, 0.05, 0.06))
    col = g.mix(g.math("MULTIPLY", g.ramp(along, 0.75, 1.0), 0.45), col, (0.16, 0.12, 0.13))
    col = g.mix(g.ramp(g.noise(900.0, detail=1.0), 0.72, 0.76), col, (0.5, 0.45, 0.38))
    tr.tk.finish(mat, g, col, 0.0, 0.45, g.bump(g.noise(500.0, detail=3.0), 0.3, 0.0003))
    cone_mat = tr.signals(mat, col, 0.45)
    return {"leaf": leaf, "twig": twig, "petiole": twig, "snow": snow_mat, "cone": cone_mat}


def spray(m, rnd, start, direction, length, cones=0, order=2, snowy=True):
    """A drooping fir spray hanging from `start`: a main twig and short side twigs alternately left and right, every
    one densely needled, snow along their tops (`snowy`), `cones` upright cones standing on it."""
    pts = tr.bend_path(start, direction, length, rnd.uniform(0.3, 0.6), steps=12, down=(0.0, -1.0, 0.0))
    needled(m, rnd, pts, 0.0026 if order == 2 else 0.0017)
    if snowy:
        snow(m, rnd, pts, 0.6 if order == 2 else 0.2)
    tw = tr.Branch(pts, [0.003] * len(pts))
    f, side = rnd.uniform(0.06, 0.12), rnd.choice((-1, 1))
    while f < 0.86 and order > 0:
        p, tan, _ = tw.at(f)
        d = tr.rotate(tan, (0.0, 0.0, 1.0), side * rnd.uniform(40.0, 60.0))
        L = length * rnd.uniform(0.32, 0.45) * (1.0 - 0.55 * f)
        if L > 0.03:
            spray(m, rnd, p, d, L, 0, order - 1, snowy)
        f += rnd.uniform(0.06, 0.09)
        side = -side
    for _ in range(cones):
        p, _, _ = tw.at(rnd.uniform(0.2, 0.6))
        cone(m, rnd, p + Vector((rnd.uniform(-0.01, 0.01), 0.0, 0.004)), rnd.uniform(0.07, 0.1))


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(47)
    sprays = []
    for i, name in enumerate(SPRAYS):
        m = tr.Mesh()
        side = (-1, 1, -1, 1)[i]
        spray(m, rnd, Vector(), Vector((side * rnd.uniform(0.1, 0.25), -1.0, 0.0)), rnd.uniform(0.38, 0.45),
              cones=(0, 0, 3, 0)[i])
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        sprays.append(obj)
    if render:
        for name, o in zip(SPRAYS, sprays):
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        m = tr.Mesh()
        side = (1, -1)[ci]
        stem = tr.bend_path(Vector(), Vector((side * 0.3, -1.0, 0.05)), rnd.uniform(1.1, 1.3), 0.45, steps=12,
                            down=(0.0, -1.0, 0.0))
        tr.twig(m, stem, [0.01 * (1.0 - 0.7 * i / (len(stem) - 1)) for i in range(len(stem))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        br = tr.Branch(stem, [0.01] * len(stem))
        for j in range(16):
            f = 0.04 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / 16
            p, tan, _ = br.at(f)
            c = sprays[rnd.randrange(len(sprays))].copy()
            tr.tk.link(c)
            spin = (j % 2 * 2 - 1) * rnd.uniform(30.0, 65.0)
            rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-30, 30)), 4, "Y")
                   @ Matrix.Rotation(math.radians(rnd.uniform(-12, 12)), 4, "X"))
            c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.8, 1.05) * (1.0 - 0.25 * f), 4)
            objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    m = tr.Mesh()
    spray(m, random.Random(5), Vector(), Vector((0.1, -1.0, 0.0)), 0.12, 0, 1, snowy=False)
    sprig = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [sprig])
    if render:
        atlas.render(atlas.cells[LEAF], [sprig])
    if not render:
        return None
    out = atlas.save(FOLDER, "SubalpineFirLeaves")
    atlas.preview(os.path.join(PREVIEWS, "subalpine_fir_atlas.png"))
    for c in atlas.cells.values():
        print("[subalpine_fir] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("SubalpineFirLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def spire(t):
    """The crown's envelope up the trunk: a very narrow spire, the lowest limbs a little shorter than those just
    above them (they're the oldest, broken back by snow), tapering steadily to the top."""
    return (1.0 - 0.9 * t) * (0.8 + 0.2 * min(1.0, t * 6.0))


def fir(trunks, crown=0.02, reach=1.0, whorl_gap=0.55, budget=12000, favor=None, card_scale=(1.2, 1.6),
        shape=spire, stubs=(2, 5)):
    """A subalpine fir's TreeSpec: `trunks`, close whorls of four short limbs every `whorl_gap` m from `crown` of the
    height (near the ground) to the top, drooping under snow; `reach` scales them, `favor` lengthens them toward one
    side (the lee of the wind); side branchlets in each limb's plane; snow-laden sprays all along them."""
    limbs = tr.Level(per_meter=4.0 / whorl_gap, whorl=4, span=(crown, 0.985), length=(1.6 * reach, 2.6 * reach),
                     shape=shape, angle=84.0, angle_tip=60.0, angle_vary=8.0, radius=0.2, radius_length=0.7,
                     radius_max=0.04, tip_radius=0.003, step=0.2, gravitropism=0.05, droop=0.8, wander=0.15,
                     floor=0.15, favor=favor, sides=(4, 3, 3), seg=(1.2, 2.0, 3.0), min_len=(0.0, 0.35, 0.9))
    branchlets = tr.Level(per_meter=1.2, span=(0.15, 0.92), length=(0.35 * reach ** 0.5, 0.7 * reach ** 0.5),
                          shape="tapered", angle=55.0, angle_tip=45.0, angle_vary=10.0, planar=0.7, radius=0.5,
                          radius_length=0.5, radius_max=0.01, tip_radius=0.0015, step=0.12, droop=0.5,
                          wander=0.3, sides=(3, 0, 0), seg=(0.5, 9.0, 9.0), min_len=(0.0, 99.0, 99.0))
    stubs_lv = tr.Level(count=stubs, span=(0.02, 0.2), length=(0.06, 0.3), angle=80.0, angle_vary=10.0,
                        radius=0.15, radius_length=0.4, radius_max=0.02, tip_radius=0.006, broken=True, step=0.06,
                        droop=0.4, wander=0.2, sides=(6, 4, 0), seg=(0.3, 1.0, 1.0), min_length=0.04)
    return tr.TreeSpec(
        trunks=trunks, levels=[limbs, branchlets], stubs=stubs_lv, budget=budget, bark_budget=4000,
        foliage=tr.Foliage(levels={2: (0.0, 1.0), 1: (0.0, 1.0)}, trunk_top=(0.85, 1.0), spacing=0.045,
                           cells=SPRAYS, scale=card_scale, hang=0.25, spread=0.3, out=0.6, face=0.4, up=0.55,
                           roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.1, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.7, cells=CLUSTERS,
                           scale=(0.9, 1.15), hang=0.25, spread=0.25, out=0.65, face=0.5, up=0.5, roll=15.0,
                           bend=15.0),
        bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.3, flare_height=0.4, lobes=(6, 0.1), taper=1.0, tip_radius=0.005, wander=0.04,
                sides=(12, 8, 6), seg=(0.8, 1.6, 3.0), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


def krummholz(t):
    """A wind-flattened mat: long limbs low down spreading over the snow, only stubby ones above."""
    return 1.0 - 0.95 * min(1.0, t * 1.6)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeSubalpineFirSeed in game): a stem about 0.4 m tall with three
    close whorls of short twigs, hung with small needle sprigs (the atlas's Leaf cell, no snow)."""
    shoots = tr.Level(per_meter=12.0, whorl=4, span=(0.25, 0.92), length=(0.05, 0.11), shape="tapered", angle=75.0,
                      angle_tip=60.0, radius=0.6, radius_length=0.5, radius_max=0.003, tip_radius=0.0008, step=0.03,
                      droop=0.4, wander=0.3, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.025, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.4, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0015,
                         lean=(0.02, 0.01), bow=0.2, wander=0.01, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.5, 1.0), spacing=0.045, cells=(LEAF,),
                           scale=(0.7, 1.0), hang=0.15, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.08, cells=(LEAF,), scale=(0.9, 1.1),
                           hang=0.15, spread=0.3, out=0.7, face=0.4, up=0.6, roll=20.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, budget=500, lod_share=(0.55, 0.3))


VARIANTS = [
    # A tall spire, about 20 m, dense right down to the snow
    ("SubalpineFir01", 3, lambda: fir([trunk(height=20.0, radius=0.25, lean=(0.2, 0.15), bow=0.1)], budget=13000)),
    # Bent by snow: leaning, its top curving back up, about 15 m
    ("SubalpineFir02", 13, lambda: fir([trunk(height=15.0, radius=0.2, lean=(2.2, 0.6), bow=0.6, wander=0.06)],
                                       reach=0.9, budget=11000)),
    # Krummholz, about 3 m: stunted and wind-flattened, its limbs spreading low on the lee side
    ("SubalpineFir03", 23, lambda: fir([trunk(height=3.2, radius=0.12, lean=(0.5, 0.1), bow=0.4, wander=0.1,
                                              flare=0.4, sides=(10, 7, 5), seg=(0.4, 0.8, 1.6))],
                                       reach=1.15, whorl_gap=0.25, favor=((1.0, 0.2), 0.8), shape=krummholz,
                                       budget=6000, card_scale=(1.0, 1.3), stubs=(0, 0))),
    # Young, about 6 m
    ("SubalpineFir04", 37, lambda: fir([trunk(height=6.0, radius=0.08, lean=(0.15, 0.2), bow=0.1, flare=0.2)],
                                       reach=0.55, whorl_gap=0.4, budget=7000, card_scale=(1.0, 1.3),
                                       stubs=(0, 0))),
    # The seedling a planted seed shows before it grows into SubalpineFir04
    ("SubalpineFirSapling", 53, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """SubalpineFirSeed_Icon.png (160 x 160, in Trees/SubalpineFir; gen_nature.py copies it into the mod's item icons),
    drawn like vanilla's pine cone seed: two upright dark purple cones on a needle sprig, under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(shade=0.0)
    rnd = random.Random(7)
    m = tr.Mesh()
    # In a card's frame (x right, y up, facing +z): a sprig lying across, two cones standing up out of it toward the
    # viewer's upper side (the frame's +y after the turn below)
    spray(m, rnd, Vector((0.05, -0.02, 0.0)), Vector((-1.0, 0.25, 0.0)), 0.13, 0, 1, snowy=False)
    for x, h, lean in ((-0.014, 0.075, -0.1), (0.022, 0.06, 0.12)):
        cone(m, rnd, Vector((x, -0.012, 0.01)), h, up=(lean, 1.0, 0.15), scales=70)
    obj = m.build("SubalpineFirSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (0.0, 0.0, 0.18)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "SubalpineFirSeed_Icon.png"), hide=())
    print("[subalpine_fir] icon written")


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
    mats = {"bark": tr.textured("SubalpineFirBark", paths("SubalpineFirBark")),
            "twig": tr.textured("SubalpineFirBarkTwig", paths("SubalpineFirBarkTwig")),
            "leaves": tr.textured("SubalpineFirLeaves", paths("SubalpineFirLeaves"), cutout=True, translucent=0.2)}
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
        print("[subalpine_fir] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("subalpinefir01", lods[0], PREVIEWS, figure)
    tr.preview_lods("subalpinefir01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("subalpine_fir", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[subalpine_fir] done")


main()
