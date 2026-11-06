"""Flowering crabapple (Malus) of the forest edge, on treekit.py (birch.py is the worked example; TREES.md the rules).

A short crooked trunk of dark grey-brown scaly bark, a dense rounded crown of twisting, spreading branches carrying
short spur twigs; dark glossy oval toothed leaves 5-7 cm; in spring a blanket of pink buds opening to soft white-pink
five-petalled blossom, in fall small red and yellow fruit (2 cm) on thin stalks in clusters.
  Crabapple01  full blossom, about 5.5 m
  Crabapple02  leaves and clusters of small red crabapples (post-bloom), about 5 m
  Crabapple03  leaning, half in blossom, about 6.5 m
  Crabapple04  young, in blossom, about 3 m
  CrabappleSapling is the planted seed's seedling.

    blender -b --factory-startup --python trees/crabapple.py -- <unity trees folder> <preview folder> [step]

Steps as birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`, `skeleton`; extra arguments
after the step name variants to build. Built at its size in game.
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
FOLDER = os.path.join(TREES, "Crabapple")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
Z = Vector((0.0, 0.0, 1.0))

# ---------------------------------------------------------------- bark
# CrabappleBark 1024 x 2048, wrapping twice round, tiling every 2 pi radii, drawn for an 8 cm stem (about 40 px/cm):
# dark grey-brown, scaly: small curled plates with lighter lifting edges over dark furrows. CrabappleBarkTwig 512 x 1024.

W, H, WRAPS = 1024, 2048, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 8.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
GROUND_V = 0.1
BARK_MEAN = (84, 72, 64)
TWIG_MEAN = (88, 66, 52)
TWIG_R = 0.012
UV = {"bark": tr.BarkUV(k=K, wraps=WRAPS, twist=0.15), "twig": tr.BarkUV(k=4.0 * math.pi)}


def bark_key(br, s, r, z):
    return "twig" if r < TWIG_R and "stub" not in br.tags else "bark"


def scaly_bark(r, h=H, w=W, px=PX):
    cm = px
    warp = ((tr.fbm(r, h, w, (1.5 * cm, 3 * cm), 3) - 0.5) * 0.8 * cm,
            (tr.fbm(r, h, w, (1.5 * cm, 3 * cm), 3) - 0.5) * 1.2 * cm)
    edge, idx, py, _ = tr.cells(r, h, w, 2.2 * cm, 1.5, warp)
    shade = r.random(idx.max() + 1)[idx]
    tilt = (r.random(idx.max() + 1) * 2 - 1)[idx]
    Y = np.mgrid[0:h, 0:w][0].astype(float)
    wob = tr.fbm(r, h, w, (0.5 * cm, 0.8 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.1 + 0.18 * wob) * cm, edge)
    plate = tr.smoothstep(0.0, 0.6 * cm, edge)
    grit = tr.fbm(r, h, w, (0.15 * cm, 0.2 * cm), 3)
    mott = tr.fbm(r, h, w, (3 * cm, 4 * cm), 4)
    fibre = tr.fbm(r, h, w, (0.1 * cm, 1.2 * cm), 3)
    local = np.clip((Y - py) / (1.6 * cm), -1.0, 1.0) * tilt
    col = tr.mix((0.14, 0.12, 0.105), (0.42, 0.37, 0.32), 0.3 * shade + 0.2 * grit + 0.2 * mott + 0.15 * fibre + 0.15 * (local * 0.5 + 0.5))
    lift = tr.smoothstep(0.55, 0.9, plate) * (local > 0.2)
    col = tr.mix(col, (0.55, 0.47, 0.38), lift * 0.35)       # lighter lifting plate tips, a hint of the red-brown under
    col = tr.mix(col, (0.44, 0.42, 0.35), tr.smoothstep(0.86, 0.9, tr.fbm(r, h, w, (0.8 * cm, 0.8 * cm), 3)) * tr.smoothstep(0.5, 0.7, mott) * 0.5)
    col = tr.mix(col, (0.025, 0.02, 0.018), furrow * 0.92)
    height = 1.6 * plate + 0.5 * local * plate + 0.3 * grit + 0.3 * fibre - 1.8 * furrow
    rough = 0.9 + 0.05 * (grit - 0.5)
    occ = tr.cavity(height, 3.5 * RELIEF, 0.3)
    col = col * (0.75 + 0.25 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0, 1), occ


def twig_bark(r, h=1024, w=512):
    cm = w / TAU
    tone = tr.fbm(r, h, w, (3 * cm, 2 * cm), 4)
    col = tr.mix((0.2, 0.13, 0.095), (0.36, 0.26, 0.19), tone)
    streak = tr.fbm(r, h, w, (0.15 * cm, 3 * cm), 4)
    col = col * (0.85 + 0.3 * streak)[..., None]
    lent = np.zeros((h, w))
    for _ in range(int((w / cm) * (h / cm) * 1.4)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.3) * cm, max(1.5, 0.05 * cm), 0.9, ends=1.0)
    col = tr.mix(col, (0.62, 0.55, 0.45), tr.blur(lent, 0.3) * 0.6)
    height = 0.4 * streak + 0.4 * tone
    return np.clip(col, 0, 1), height, np.full((h, w), 0.5), tr.cavity(height, 3.0, 0.15)


def make_bark():
    r = np.random.default_rng(37)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = scaly_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("CrabappleBark", col, height, rough, occ, RELIEF * 1.5)
    tcol, th, tro, toc = twig_bark(r)
    tcol, _ = tr.match_mean(tcol, TWIG_MEAN)
    save("CrabappleBarkTwig", tcol, th, tro, toc, 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- atlas
BLOSSOMS = tuple("Blossom%d" % i for i in range(4))
FRUITS = ("Fruit0", "Fruit1")
LEAFYS = ("Leafy0", "Leafy1")
CLUSTERS = ("CloudBlossom", "CloudFruit", "CloudLeafy")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, n in enumerate(BLOSSOMS):
        atlas.cell(n, 512 * i, 1536, 512, 512, (0.5, 0.5))
    for i, n in enumerate(FRUITS + LEAFYS):
        atlas.cell(n, 512 * i, 1024, 512, 512, (0.5, 0.5))
    for i, n in enumerate(CLUSTERS):
        atlas.cell(n, 640 * i, 128, 640, 896, (0.95, 1.33))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.09, 0.09), pad=8)
    return atlas


def leaf_materials(shade=0.0):
    attr = lambda g: g.node("ShaderNodeAttribute", attribute_name="leaf")  # noqa: E731
    mat, g = tr.tk.new_material("CrabPetalSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    col = g.mix(g.ramp(rv, 0.0, 1.0), (0.80, 0.62, 0.66), (0.86, 0.72, 0.74))  # white with a pink flush
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.5, 0.0), 0.5), col, (0.78, 0.36, 0.5))  # deeper pink at the base
    col = g.mix(g.math("MULTIPLY", g.ramp(ax, 0.6, 1.0), 0.3), col, (0.76, 0.44, 0.56))  # pink along the edges
    col = g.mix(g.math("MULTIPLY", back, 0.5), col, (0.72, 0.30, 0.42))  # the back of a petal is the pinker side
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    petal = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("CrabHeartSrc")
    col = g.mix(g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.7), (0.5, 0.36, 0.03), (0.7, 0.5, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    heart = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("CrabBudSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    col = g.mix(g.ramp(s, 1.0, 0.1), (0.60, 0.24, 0.33), (0.78, 0.52, 0.58))
    col = g.mix(g.ramp(rv, 0.0, 1.0), col, (0.7, 0.32, 0.4))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    bud = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("CrabLeafSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    base = g.mix(g.ramp(rv, 0.0, 1.0), (0.04, 0.1, 0.03), (0.07, 0.15, 0.04))  # dark glossy green
    mid = g.ramp(ax, 0.06, 0.0)
    lat = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, g.math("MULTIPLY", ax, 0.5)), 7.0))
    lat = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lat, 0.5)), 0.43, 0.5),
                 g.ramp(ax, 0.02, 0.1))
    veins = g.math("MAXIMUM", mid, lat)
    col = g.mix(g.math("MULTIPLY", veins, 0.3), base, (0.16, 0.26, 0.08))
    col = g.mix(g.math("MULTIPLY", g.ramp(rv, 0.9, 1.0), 0.35), col, (0.2, 0.12, 0.05))  # a bronze young leaf
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    col = g.mix(back, col, g.mix(0.3, (0.12, 0.2, 0.08), (0.2, 0.28, 0.12)))
    tr.tk.finish(mat, g, col, 0.0, g.mixf(back, 0.35, 0.6))
    leaf = tr.signals(mat, col, 0.4)

    mat, g = tr.tk.new_material("CrabTwigSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=3.0), 0.3, 0.7), (0.065, 0.04, 0.028), (0.14, 0.09, 0.06))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("CrabFruitSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    red = g.mix(g.ramp(s, 0.2, 0.9), (0.42, 0.03, 0.03), (0.5, 0.06, 0.03))
    yel = g.mix(g.ramp(s, 0.3, 0.9), (0.48, 0.35, 0.05), (0.52, 0.2, 0.04))
    col = g.mix(g.ramp(rv, 0.45, 0.7), red, yel)
    col = g.mix(g.ramp(s, 0.06, 0.0), col, (0.05, 0.035, 0.015))  # calyx end
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(80.0, detail=2.0), 0.55, 0.7), 0.3), col, (0.4, 0.3, 0.1))
    tr.tk.finish(mat, g, col, 0.0, 0.3)
    fruit = tr.signals(mat, col, 0.3)

    mat, g = tr.tk.new_material("CrabFleshSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    col = g.mix(g.ramp(ax, 0.2, 0.7), (0.78, 0.7, 0.45), (0.8, 0.74, 0.5))
    col = g.mix(g.ramp(ax, 0.9, 1.0), col, (0.4, 0.04, 0.03))
    core = g.ramp(g.math("SUBTRACT", 0.3, ax), 0.0, 0.05)
    col = g.mix(core, col, (0.45, 0.4, 0.2))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    flesh = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("CrabSeedSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=2.0), 0.3, 0.7), (0.07, 0.03, 0.012), (0.16, 0.07, 0.025))
    tr.tk.finish(mat, g, col, 0.0, 0.3)
    seed = tr.signals(mat, col, 0.3)
    return {"petal": petal, "heart": heart, "bud": bud, "leaf": leaf, "twig": twig, "fruit": fruit, "flesh": flesh,
            "seed": seed}


def petal_profile(s):
    return float(np.interp(s, (0.0, 0.1, 0.4, 0.75, 0.93, 1.0), (0.12, 0.45, 0.95, 1.0, 0.7, 0.0)))


def leaf_profile(s):
    return float(np.interp(s, (0.0, 0.05, 0.3, 0.55, 0.8, 0.95, 1.0), (0.1, 0.6, 0.95, 1.0, 0.7, 0.28, 0.0)))


def ball(m, c, rx, ry, rz, key, rv, rings=5, segs=7, axis=None):
    """A small ellipsoid (a fruit, a bud) centred at `c`, radii rx ry (round `axis`) and rz along it."""
    ax = Vector(axis if axis is not None else (0, 0, 1)).normalized()
    _, u, v = tr.basis(ax)
    rows = []
    for j in range(rings + 1):
        t = j / rings
        phi = math.pi * t
        row = []
        for k in range(segs):
            a = k / segs * TAU
            p = c + ax * (-math.cos(phi) * rz) + (u * math.cos(a) + v * math.sin(a)) * (math.sin(phi) * rx)
            row.append(m.v(p, leaf=(0.0, t, rv)))
        rows.append(row)
    uv = ((0, 0),) * 3
    for a, b in zip(rows, rows[1:]):
        for k in range(segs):
            k1 = (k + 1) % segs
            m.quad(a[k], a[k1], b[k1], b[k], ((0, 0),) * 4, key)


def flower(m, rnd, c, n, size=1.0):
    n = Vector(n).normalized()
    _, u, v = tr.basis(n)
    a0 = rnd.uniform(0, TAU)
    for k in range(5):
        az = a0 + k * TAU / 5 + rnd.uniform(-0.1, 0.1)
        out = u * math.cos(az) + v * math.sin(az)
        way = (out * math.cos(math.radians(25)) + n * math.sin(math.radians(25))).normalized()
        L = 0.0165 * size * rnd.uniform(0.9, 1.1)
        tr.blade(m, c + out * 0.002 * size, way, n, L, L * rnd.uniform(0.9, 1.05), petal_profile, "petal", fold=0.1,
                 arch=rnd.uniform(0.0, 0.12), rows=4, rnd_value=rnd.random())
    for k in range(7):  # stamens
        az = rnd.uniform(0, TAU)
        out = u * math.cos(az) + v * math.sin(az)
        tr.twig(m, [c, c + out * 0.004 * size + n * 0.004 * size], [0.0005, 0.0004], "heart", 3)
    tr.blade(m, c + n * 0.002 * size, u, n, 0.006 * size, 0.006 * size,
             lambda q: float(np.interp(q, (0, 0.3, 0.8, 1.0), (0.5, 1.0, 0.8, 0.0))), "heart", rows=3)


def bud(m, rnd, c, way, size=1.0):
    ball(m, c + Vector(way).normalized() * 0.006 * size, 0.0042 * size, 0.0042 * size, 0.0085 * size, "bud", rnd.random(),
         axis=way)


def leaf_at(m, rnd, p, way, size=0.06, young=False):
    way = Vector(way).normalized()
    nrm = Vector((rnd.gauss(0, 0.3), 0.4 + rnd.gauss(0, 0.2), 1.0))
    q = p + way * 0.008
    tr.twig(m, [p, q], [0.0008, 0.0007], "twig", 3)
    L = size * rnd.uniform(0.85, 1.1)
    tr.blade(m, q, (way + Vector((0, -0.4, 0))).normalized(), nrm, L, L * rnd.uniform(0.55, 0.65), leaf_profile, "leaf",
             teeth=22, tooth=0.04, fold=0.12, arch=rnd.uniform(0.05, 0.2), twist=rnd.uniform(-20, 20), rows=10,
             rnd_value=0.95 if young else rnd.uniform(0.0, 0.8))


def corymb(m, rnd, p, way, n_flowers, buds, size, leaves=1):
    """A spur ending in a cluster: `n_flowers` open blossoms and `buds` buds on pedicels, a couple of young leaves."""
    way = Vector(way).normalized()
    tip = p + way * 0.02
    tr.twig(m, [p, tip], [0.0016, 0.0013], "twig", 4)
    for i in range(n_flowers + buds):
        d = (way + Vector((rnd.gauss(0, 0.6), rnd.gauss(0, 0.6), rnd.gauss(0, 0.5)))).normalized()
        c = tip + d * rnd.uniform(0.016, 0.03)
        tr.twig(m, [tip, c], [0.0005, 0.0004], "twig", 3)
        if i < n_flowers:
            ax = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), 0.0))
            nrm = tr.rotate(Z, ax, min(65.0, abs(rnd.gauss(0.0, 35.0)))) if ax.length > 1e-3 else Z.copy()
            flower(m, rnd, c + Vector((0, 0, 0.004)), nrm, size * rnd.uniform(0.85, 1.1))
        else:
            bud(m, rnd, c, d, size)
    for _ in range(leaves):
        leaf_at(m, rnd, tip, Vector((rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.6), 0.2)), 0.04, young=True)


def fruit_cluster(m, rnd, p, way, count):
    way = Vector(way).normalized()
    tip = p + way * 0.015
    tr.twig(m, [p, tip], [0.0016, 0.0013], "twig", 4)
    for i in range(count):
        d = (Vector((rnd.gauss(0, 0.6), -1.0, rnd.gauss(0, 0.4)))).normalized()
        L = rnd.uniform(0.022, 0.034)
        c = tip + d * L
        tr.twig(m, [tip, tip + d * L * 0.5 + Vector((0, 0.003, 0)), c], [0.0005, 0.0005, 0.0004], "twig", 3)
        r = rnd.uniform(0.0092, 0.0112)
        ball(m, c + d * r * 0.85, r, r, r * 0.93, "fruit", rnd.random(), rings=6, segs=8, axis=d)


def spray(m, rnd, kind, k):
    side = rnd.choice((-1, 1))
    way = Vector((side * rnd.uniform(0.2, 0.45), -1.0, rnd.uniform(-0.1, 0.1)))
    L = rnd.uniform(0.4, 0.46)
    pts = tr.bend_path(Vector(), way, L, rnd.uniform(0.4, 0.9), steps=12)
    for i in range(1, len(pts) - 1):  # a crooked twig
        pts[i] += Vector((rnd.gauss(0, 0.006), 0.0, rnd.gauss(0, 0.004)))
    tr.twig(m, pts, [0.0034 * (1 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], "twig", 5)
    br = tr.Branch(pts, [0.003] * len(pts))
    f, sd = 0.07, side
    while f < 0.97:
        p, tan, _ = br.at(f)
        out = (tr.rotate(tan, Z, sd * rnd.uniform(40, 70)) + Vector((0, 0.1, rnd.uniform(0.1, 0.5)))).normalized()
        if kind == "blossom":
            corymb(m, rnd, p, out, rnd.randint(3, 4), rnd.randint(1, 2) if k < 2 else rnd.randint(0, 1), 1.0,
                   leaves=rnd.randint(0, 1))
        elif kind == "fruit":
            if rnd.random() < 0.55:
                fruit_cluster(m, rnd, p, out, rnd.randint(2, 4))
            else:
                leaf_at(m, rnd, p, out, 0.062)
            leaf_at(m, rnd, p, tr.rotate(out, Z, -sd * 60.0), 0.06)
        else:
            leaf_at(m, rnd, p, out, 0.062)
            if rnd.random() < 0.5:
                corymb(m, rnd, p, tr.rotate(out, Z, -sd * 55.0), 1, 1, 1.0, leaves=2)
        f += rnd.uniform(0.07, 0.1)
        sd = -sd
    leaf_at(m, rnd, pts[-1], tan, 0.05)


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(53)
    sprays = {}
    for names, kind in ((BLOSSOMS, "blossom"), (FRUITS, "fruit"), (LEAFYS, "leafy")):
        for k, name in enumerate(names):
            m = tr.Mesh()
            spray(m, rnd, kind, k)
            obj = m.build(name + "Src", mats)
            atlas.frame(atlas.cells[name], [obj])
            sprays[name] = obj
    if render:
        for name, o in sprays.items():
            atlas.render(atlas.cells[name], [o])
    for ci, name in enumerate(CLUSTERS):
        pool = (BLOSSOMS, FRUITS, LEAFYS)[ci]
        m = tr.Mesh()
        side = (1, -1, 1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.35, -1.0, 0.1)), rnd.uniform(0.8, 0.9), 0.4, steps=10)]
        main = tr.Branch(stems[0], [0.006] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.65, -side)):
            p, tan, _ = main.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, Z, s2 * rnd.uniform(40.0, 60.0)), rnd.uniform(0.35, 0.5), 0.5, steps=8))
        for k, st in enumerate(stems):
            r0 = 0.006 if k == 0 else 0.004
            tr.twig(m, st, [r0 * (1.0 - 0.6 * i / (len(st) - 1)) for i in range(len(st))], "twig", 6)
        objs = [m.build(name + "Stem", mats)]
        for k, st in enumerate(stems):
            br = tr.Branch(st, [0.006] * len(st))
            count = 9 if k == 0 else 5
            for j in range(count):
                f = 0.08 + 0.92 * (j + rnd.uniform(0.2, 0.8)) / count
                p, tan, _ = br.at(f)
                c = sprays[pool[rnd.randrange(len(pool))]].copy()
                tr.tk.link(c)
                spin = (j % 2 * 2 - 1) * rnd.uniform(10.0, 70.0)
                rot = (Matrix.Rotation(math.radians(spin), 4, "Z") @ Matrix.Rotation(math.radians(rnd.uniform(-55, 55)), 4, "Y")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 4, "X"))
                c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.75, 1.0), 4)
                objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    m = tr.Mesh()
    tr.twig(m, [Vector(), Vector((0, -0.01, 0))], [0.0006, 0.0005], "twig", 3)
    tr.blade(m, Vector((0, -0.01, 0)), Vector((0.05, -1.0, 0.0)), Vector((0, 0.2, 1)), 0.06, 0.036, leaf_profile, "leaf",
             teeth=16, tooth=0.04, fold=0.1, arch=0.1, rows=8, rnd_value=0.3)
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    out = atlas.save(FOLDER, "CrabappleLeaves")
    atlas.preview(os.path.join(PREVIEWS, "crabapple_atlas.png"))
    for c in atlas.cells.values():
        sl = (slice(c.y, c.y + c.h), slice(c.x, c.x + c.w))
        op = atlas.alpha[sl] > 0.5
        mean = tuple(int(v) for v in np.round(atlas.albedo[sl][op].mean(0) * 255)) if op.any() else None
        print("[crabapple] cell %s coverage %.3f mean %s" % (c.name, c.coverage, mean))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("CrabappleLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- trees

def crown_shape(t):
    return (0.45 + 0.55 * math.sin(math.pi * min(1.0, t) ** 0.8)) * (1.0 - 0.2 * t)


def crab(trunks, cells, cluster_cells, limbs=2.4, reach=1.0, budget=8000, card_scale=(1.5, 2.1), spacing=0.04, twigs=5.0):
    l1 = tr.Level(per_meter=limbs, span=(0.2, 0.98), length=(1.4 * reach, 2.6 * reach), shape=crown_shape, angle=62.0,
                  angle_tip=34.0, angle_vary=14.0, radius=0.5, radius_length=0.6, radius_max=0.05, tip_radius=0.008,
                  step=0.22, gravitropism=0.25, droop=0.12, wander=0.5, outward=0.45, floor=0.8, sides=(7, 5, 3),
                  seg=(0.5, 0.9, 1.6))
    l2 = tr.Level(per_meter=twigs, span=(0.12, 0.97), length=(0.55 * reach ** 0.5, 1.2 * reach ** 0.5), shape="tapered",
                  angle=60.0, angle_tip=42.0, angle_vary=14.0, planar=0.1, radius=0.45, radius_length=0.5,
                  radius_max=0.014, tip_radius=0.004, step=0.18, gravitropism=0.1, droop=0.25, wander=0.6, outward=0.35,
                  floor=0.9, sides=(3, 3, 0), seg=(0.5, 0.9, 9.0), min_len=(0.0, 0.5, 99.0))
    return tr.TreeSpec(
        trunks=trunks, levels=[l1, l2], budget=budget, bark_budget=3000,
        foliage=tr.Foliage(levels={2: (0.12, 1.0), 1: (0.5, 1.0)}, trunk_top=None, spacing=spacing, cells=cells,
                           scale=card_scale, hang=0.03, spread=0.4, out=0.5, face=0.6, up=0.5, roll=60.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.3, 1.0), 2: (0.5, 1.0)}, spacing=0.9, cells=cluster_cells, scale=(0.85, 1.15),
                           hang=0.35, spread=0.3, out=0.5, face=0.8, up=0.3, roll=30.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V)


def trunk(height, radius, lean=(0.0, 0.0), bow=0.3, **kw):
    d = dict(height=height, radius=radius, flare=0.3, flare_height=0.35, lobes=(4, 0.08), taper=0.7, tip_radius=0.03,
             lean=lean, bow=bow, wander=0.25, sink=0.3, step=0.3, sides=(12, 8, 5), seg=(0.5, 1.0, 2.0),
             rings=((0.0, 0.25, 0.7), (0.0, 0.5), (0.0,)))
    d.update(kw)
    return tr.Trunk(**d)


def sapling():
    shoots = tr.Level(count=(3, 5), span=(0.3, 0.85), length=(0.1, 0.22), shape="tapered", angle=55.0, angle_tip=40.0,
                      radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03, gravitropism=0.5,
                      droop=0.2, wander=0.5, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0), min_length=0.04,
                      min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.6, radius=0.005, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0012,
                         lean=(0.03, 0.02), bow=0.3, wander=0.04, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.04, cells=(LEAF,), scale=(0.8, 1.15),
                           hang=0.2, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.06, cells=(LEAF,), scale=(0.9, 1.2), hang=0.25,
                           spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V, budget=500, lod_share=(0.55, 0.3))


def clump(seed, n, heights, radius, lean, spread=0.1, tilt=(0.0, 0.0)):
    rnd = random.Random(seed)
    a0 = rnd.uniform(0, TAU)
    out = []
    for i, h in enumerate(heights):
        az = a0 + i * TAU / n + rnd.uniform(-0.4, 0.4)
        L = lean * rnd.uniform(0.7, 1.3)
        out.append(trunk(h, radius * rnd.uniform(0.85, 1.1), lean=(L * math.cos(az) + tilt[0], L * math.sin(az) + tilt[1]),
                         bow=0.4, base=(spread * math.cos(az), spread * math.sin(az))))
    return out


BL = BLOSSOMS + (BLOSSOMS[0], BLOSSOMS[1], LEAFYS[0])
VARIANTS = [
    ("Crabapple01", 11, lambda: crab(clump(5, 3, [2.8, 2.5, 2.6], 0.08, 0.55), BL, ("CloudBlossom",) * 3 + ("CloudLeafy",),
                                     limbs=2.4, budget=8500)),
    ("Crabapple02", 23, lambda: crab(clump(8, 3, [2.6, 2.4, 2.3], 0.075, 0.5), FRUITS + FRUITS + LEAFYS,
                                     ("CloudFruit", "CloudFruit", "CloudLeafy"), limbs=2.3, reach=0.95, budget=8500)),
    ("Crabapple03", 37, lambda: crab(clump(12, 2, [3.6, 2.8], 0.09, 0.7, tilt=(1.1, 0.4)),
                                     BLOSSOMS + LEAFYS + LEAFYS, ("CloudBlossom", "CloudLeafy"), limbs=2.3, reach=1.1,
                                     budget=8000)),
    ("Crabapple04", 41, lambda: crab([trunk(2.4, 0.04, lean=(0.3, -0.2), flare=0.25, lobes=(0, 0.0), sides=(8, 6, 4))],
                                     BLOSSOMS + (LEAFYS[0],), ("CloudBlossom",), limbs=2.2, reach=0.6, budget=5000,
                                     twigs=3.0)),
    ("CrabappleSapling", 53, sapling),
]


def make_icon():
    """CrabappleSeed_Icon.png: a crabapple cut in half (cream flesh, a five-pointed core with brown seeds, red skin
    rim) with a loose seed, and a whole red fruit behind."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials()
    rnd = random.Random(7)
    m = tr.Mesh()
    ball(m, Vector((0.075, 0.045, -0.02)), 0.032, 0.032, 0.03, "fruit", 0.1, rings=10, segs=14, axis=(0, 0.2, 1))
    tr.twig(m, [Vector((0.075, 0.075, -0.02)), Vector((0.082, 0.1, -0.02))], [0.0016, 0.0013], "twig", 4)
    leaf_at(m, rnd, Vector((0.082, 0.1, -0.02)), Vector((-1.0, 0.4, 0.0)), 0.07)
    # The halved fruit: a disc of flesh (profile round) with the red rim as a ring behind, a core, seeds
    disc = lambda q: float(math.sqrt(max(0.0, 1.0 - (2 * q - 1) ** 2)))  # noqa: E731
    ball(m, Vector((-0.03, -0.02, 0.0)), 0.045, 0.045, 0.02, "fruit", 0.1, rings=10, segs=16, axis=(0, 0, 1))
    c = Vector((-0.03, -0.02, 0.02))
    for k in range(48):
        a = k / 48 * TAU
        pass
    tr.blade(m, c + Vector((-0.04, 0, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), 0.08, 0.08, disc, "flesh", rows=24)
    for k in range(5):  # core lobes, five-pointed
        a = k * TAU / 5 + 0.3
        way = Vector((math.cos(a), math.sin(a), 0.0))
        tr.blade(m, c + Vector((0, 0, 0.002)), way, Vector((0, 0, 1)), 0.016, 0.01,
                 lambda q: float(np.interp(q, (0, 0.4, 0.8, 1.0), (0.4, 1.0, 0.7, 0.0))), "heart", rows=4)
        if k % 2 == 0:
            ball(m, c + way * 0.008 + Vector((0, 0, 0.004)), 0.0032, 0.0022, 0.0055, "seed", 0.5, rings=4, segs=6, axis=way)
    for (x, y, ang) in ((0.03, -0.075, 25.0), (0.055, -0.065, -10.0)):
        way = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0))
        ball(m, Vector((x, y, 0.012)), 0.0045, 0.0032, 0.009, "seed", 0.5, rings=5, segs=8, axis=way)
    obj = m.build("CrabappleSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.5, 6.5, 6.5)
    obj.location = (0.0, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.8)
    tr.tk.icon(cam, os.path.join(FOLDER, "CrabappleSeed_Icon.png"), hide=())
    print("[crabapple] icon written")


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
        if STEPS in ("textures", "atlas"):
            return
        tr.reset()
    else:
        make_atlas(atlas, render=False)
        load_coverage(atlas)
        tr.reset()
    tr.use_atlas(atlas)
    mats = {"bark": tr.textured("CrabappleBark", paths("CrabappleBark")),
            "twig": tr.textured("CrabappleBarkTwig", paths("CrabappleBarkTwig")),
            "leaves": tr.textured("CrabappleLeaves", paths("CrabappleLeaves"), cutout=True, translucent=0.3)}
    figure = tr.stage()
    built = []
    only = list(args[3:])
    for name, seed, make in VARIANTS:
        if only and name not in only:
            continue
        spec = make()
        if STEPS == "skeleton":
            spec.foliage = None
            spec.cluster = None
        tree = tr.grow(spec, seed, name)
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[crabapple] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f; %d branches, %d cards" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1], len(tree.branches), len(tree.cards)))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("crabapple01", lods[0], PREVIEWS, figure)
    tr.preview_lods("crabapple01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("crabapple", [b[2][0] for b in built if b[0] != "CrabappleSapling"], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[crabapple] done")


main()
