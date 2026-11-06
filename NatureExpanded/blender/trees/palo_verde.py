"""Blue palo verde (Parkinsonia florida) of the desert washes, on treekit.py (birch.py is the worked example;
TREES.md has the rules).

A short trunk that divides low into several stems, every stem and branch SMOOTH and GREEN (yellow-green to blue-green
bark that photosynthesises, so the tree is nearly leafless), climbing in a broad vase-to-umbrella and zig-zagging
outward into a dense broom of thin green spiny twigs. In spring the whole crown is a soft cloud of yellow five-petalled
flowers over the green twigs; afterwards it is green twigs with a few flowers, tiny sparse leaflets and flat, bumpy
bean pods.
  PaloVerde01  full bloom, 5.5 m spreading tree (four stems)
  PaloVerde02  leaning multi-stem tree in half bloom, about 6.5 m
  PaloVerde03  low wide shrub-tree about 4 m, POST-BLOOM (green twigs, a few flowers, pods)
  PaloVerde04  young whip about 3 m, post-bloom
  PaloVerdeSapling is the planted seed's seedling.

    blender -b --factory-startup --python trees/palo_verde.py -- <unity trees folder> <preview folder> [step]

with absolute paths `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`.
Steps as birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`, `trees`, `icon`, plus `skeleton`. Writes
Trees/PaloVerde/, the PaloVerde lines of trees.txt and trunks.txt, and the previews. Built at its size in game.
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
FOLDER = os.path.join(TREES, "PaloVerde")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
Z = Vector((0.0, 0.0, 1.0))

# ---------------------------------------------------------------- bark textures
#
# PaloVerdeBark: 1024 x 2048, wrapping twice round a tube and tiling every 2 pi radii, drawn for a 6 cm stem (about
# 54 px per cm): smooth yellow-green to blue-green skin with fine lengthwise streaks, faint rings at the nodes, tiny
# dark lenticel dashes, pale freckles. PaloVerdeBarkFoot: the same with the old base drawn over its lower rows (grey-
# brown, shallowly fissured, flaking); PaloVerdeBarkTwig 512 x 1024: the thinnest twigs, smooth bluish green.

W, H, WRAPS = 1024, 2048, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 6.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TILE = K * R_DESIGN / 100.0
GROUND_V = 0.1
JOIN_V = 0.93
FOOT_END = 0.86
BARK_MEAN = (112, 130, 76)
TWIG_MEAN = (96, 124, 74)
TWIG_R = 0.007
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS),
    "foot": tr.BarkUV(k=K, wraps=WRAPS, floor=0.005),
    "twig": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    if r < TWIG_R and "stub" not in br.tags:
        return "twig"
    if br.level == 0 and br.turns(s) / K + br.v0 < JOIN_V:
        return "foot"
    return "bark"


def green_bark(r, h, w, px=PX):
    """Smooth green bark as (albedo sRGB, height, roughness, occlusion), tileable, `px` pixels per cm."""
    cm = px
    area = (w / cm) * (h / cm)
    tone = tr.fbm(r, h, w, (5 * cm, 12 * cm), 4)
    col = tr.mix((0.50, 0.58, 0.28), (0.36, 0.52, 0.34), tone)  # yellow-green to blue-green
    warm = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (7 * cm, 18 * cm), 3))
    col = tr.mix(col, (0.58, 0.60, 0.30), warm * 0.4)
    streak = tr.fbm(r, h, w, (0.18 * cm, 5 * cm), 4)  # fine lengthwise grain
    mottle = tr.fbm(r, h, w, (0.6 * cm, 0.9 * cm), 3)
    col = col * (0.88 + 0.22 * streak)[..., None] * (0.94 + 0.12 * mottle)[..., None]
    # Faint rings where the twigs' nodes were
    ring = tr.fbm(r, h, w, (40 * cm, 0.35 * cm), 3)
    col = col * (0.93 + 0.14 * ring)[..., None]
    # A soft powdery bloom wiped along it
    bloom = tr.smoothstep(0.55, 0.85, tr.fbm(r, h, w, (1.5 * cm, 9 * cm), 4))
    col = tr.mix(col, (0.62, 0.68, 0.52), bloom * 0.22)
    # Lenticels: small dark dashes, and pale freckles
    lent = np.zeros((h, w))
    for _ in range(int(area * 2.2)):
        length = r.uniform(0.15, 0.55) * cm
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), length, max(1.6, 0.07 * cm), r.uniform(0.5, 1.0), ends=1.0)
    lent = tr.smoothstep(0.25, 0.7, tr.blur(lent, 0.3))
    col = tr.mix(col, (0.19, 0.22, 0.12), lent * 0.65)
    free = np.zeros((h, w))
    for _ in range(int(area * 1.4)):
        tr.stamp_lens(free, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.25) * cm, max(1.6, 0.1 * cm), 0.9, ends=0.6)
    free = tr.smoothstep(0.3, 0.8, tr.blur(free, 0.3))
    col = tr.mix(col, (0.74, 0.76, 0.52), free * 0.45)
    # Node scars: tiny darker bumps ringed
    sc = np.zeros((h, w))
    for _ in range(int(area / 14.0)):
        tr.stamp_lens(sc, r.uniform(0, w), r.uniform(0, h), r.uniform(0.5, 1.0) * cm, r.uniform(0.2, 0.35) * cm, 1.0, ends=0.8)
    sc = tr.blur(sc, 0.5)
    col = tr.mix(col, (0.24, 0.26, 0.15), np.clip(sc, 0, 1) * 0.55)
    height = 0.5 * streak + 0.35 * mottle + 1.1 * sc - 0.6 * lent + 0.3 * free
    rough = 0.62 - 0.12 * bloom + 0.2 * lent
    occ = tr.cavity(height, 3.0 * RELIEF, 0.2)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def foot_bark(r, green, h=H, w=W, px=PX):
    """`green` with the old base drawn over its lower rows: grey-brown bark, shallowly fissured in long plates that
    flake away to the green beneath, all gone by FOOT_END (v)."""
    col0, h0, rough0, occ0 = green
    cm = px
    v = ((np.arange(h) + 0.5) / h)[:, None]
    warp = ((tr.fbm(r, h, w, (1.5 * cm, 4 * cm), 3) - 0.5) * 1.0 * cm,
            (tr.fbm(r, h, w, (1.5 * cm, 4 * cm), 3) - 0.5) * 2.0 * cm)
    edge, big, _, _ = tr.cells(r, h, w, 2.4 * cm, 3.6, warp)
    wob = tr.fbm(r, h, w, (0.5 * cm, 1.4 * cm), 3)
    furrow = 1.0 - tr.smoothstep(0.0, (0.12 + 0.2 * wob) * cm, edge)
    plate = tr.smoothstep(0.0, 0.7 * cm, edge)
    shade = r.random(big.max() + 1)[big]
    grit = tr.fbm(r, h, w, (0.2 * cm, 0.3 * cm), 3)
    flake = tr.fbm(r, h, w, (1.0 * cm, 2.2 * cm), 4)
    dark = tr.mix((0.18, 0.16, 0.13), (0.50, 0.45, 0.36), 0.35 * flake + 0.25 * grit + 0.3 * shade + 0.1 * wob)
    dark = tr.mix(dark, (0.52, 0.52, 0.40), tr.smoothstep(0.68, 0.9, flake) * 0.35)
    dark = tr.mix(dark, (0.04, 0.035, 0.03), furrow * 0.9)
    dark_h = 1.8 * plate + 0.5 * flake + 0.3 * grit - 1.8 * furrow
    t = np.clip((v - GROUND_V) / (FOOT_END - GROUND_V), 0.0, 1.0)
    m = 1.0 - tr.smoothstep(0.25, 1.0, t + (flake - 0.5) * 0.55 + (shade - 0.5) * 0.25)
    m = m * tr.smoothstep(FOOT_END, FOOT_END - 0.06, v)
    col = tr.mix(col0, dark, m)
    height = tr.mix(h0, dark_h, m)
    rough = tr.mix(rough0, 0.92, m)
    occ = np.minimum(tr.mix(occ0, tr.cavity(dark_h, 3.0 * RELIEF, 0.25), m), 1.0)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def twig_bark(r, h=1024, w=512):
    cm = w / TAU
    tone = tr.fbm(r, h, w, (3 * cm, 2 * cm), 4)
    col = tr.mix((0.34, 0.50, 0.30), (0.50, 0.58, 0.32), tone)
    streak = tr.fbm(r, h, w, (0.12 * cm, 3 * cm), 4)
    col = col * (0.88 + 0.22 * streak)[..., None]
    lent = np.zeros((h, w))
    for _ in range(int((w / cm) * (h / cm) * 1.6)):
        tr.stamp_lens(lent, r.uniform(0, w), r.uniform(0, h), r.uniform(0.1, 0.3) * cm, max(1.5, 0.05 * cm), 0.9, ends=1.0)
    col = tr.mix(col, (0.22, 0.26, 0.14), tr.blur(lent, 0.3) * 0.6)
    height = 0.4 * streak + 0.4 * tone
    return np.clip(col, 0.0, 1.0), height, np.full((h, w), 0.55), tr.cavity(height, 3.0, 0.15)


def make_bark():
    r = np.random.default_rng(31)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = green_bark(r, H, W)
    col, k = tr.match_mean(col, BARK_MEAN)
    save("PaloVerdeBark", col, height, rough, occ, RELIEF)
    save("PaloVerdeBarkFoot", *foot_bark(r, (col, height, rough, occ)), RELIEF)
    tcol, th, tro, toc = twig_bark(r)
    tcol, _ = tr.match_mean(tcol, TWIG_MEAN)
    save("PaloVerdeBarkTwig", tcol, th, tro, toc, 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square. Top row: four BLOOM sprays (512 square): zig-zag green twigs covered in yellow flowers. Second row: four
# green TWIG sprays (the post-bloom look: bare green spiny twigs, a few flowers, tiny leaflets, flat pods). Below: two
# cluster cells (640 x 896, for LOD2), and a single bipinnate leaf for the seedling (128, past the decal strip).

BLOOMS = tuple("Bloom%d" % i for i in range(4))
TWIGS = tuple("Twig%d" % i for i in range(4))
CLUSTERS = ("CloudBloom", "CloudGreen")
LEAF = "Leaf"


def layout():
    atlas = tr.Atlas(2048)
    for i, n in enumerate(BLOOMS):
        atlas.cell(n, 512 * i, 1536, 512, 512, (0.5, 0.5))
    for i, n in enumerate(TWIGS):
        atlas.cell(n, 512 * i, 1024, 512, 512, (0.5, 0.5))
    for i, n in enumerate(CLUSTERS):
        atlas.cell(n, 640 * i, 128, 640, 896, (0.95, 1.33))
    atlas.cell(LEAF, 768, 0, 128, 128, (0.09, 0.09), pad=8)
    return atlas


def leaf_materials(shade=0.0):
    """Linear colors, set so the cards come out soft: petals a desert yellow (about sRGB (214, 185, 76)), twigs a
    yellow-green, leaflets a blue-green, pods pale straw-green."""
    attr = lambda g: g.node("ShaderNodeAttribute", attribute_name="leaf")  # noqa: E731
    mat, g = tr.tk.new_material("PaloPetalSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    ax = g.math("ABSOLUTE", x)
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    col = g.mix(g.ramp(rv, 0.0, 0.8), (0.52, 0.38, 0.05), (0.62, 0.45, 0.075))
    col = g.mix(g.ramp(rv, 0.86, 0.93), col, (0.74, 0.50, 0.16))  # the banner petal: paler, orange-spotted
    col = g.mix(g.math("MULTIPLY", g.ramp(s, 0.4, 0.0), 0.45), col, (0.70, 0.30, 0.03))  # deeper at the throat
    col = g.mix(g.math("MULTIPLY", g.ramp(ax, 0.75, 1.0), 0.25), col, (0.80, 0.64, 0.2))  # paler edges
    col = g.mix(g.math("MULTIPLY", back, 0.3), col, (0.72, 0.56, 0.14))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    petal = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("PaloHeartSrc")
    col = g.mix(g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.7), (0.36, 0.17, 0.02), (0.5, 0.26, 0.03))
    tr.tk.finish(mat, g, col, 0.0, 0.6)
    heart = tr.signals(mat, col, 0.6)

    mat, g = tr.tk.new_material("PaloLeafletSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    col = g.mix(g.ramp(rv, 0.0, 1.0), (0.07, 0.15, 0.055), (0.12, 0.2, 0.07))
    col = g.mix(g.math("MULTIPLY", back, 0.5), col, (0.16, 0.22, 0.11))
    if shade:
        col = g.mix(shade, col, (0.02, 0.05, 0.01))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    leaflet = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("PaloTwigSrc")
    col = g.mix(g.ramp(g.noise(180.0, detail=3.0), 0.3, 0.7), (0.095, 0.2, 0.06), (0.17, 0.27, 0.075))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    twig = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("PaloSpineSrc")
    col = g.mix(g.ramp(g.noise(150.0, detail=2.0), 0.3, 0.7), (0.16, 0.2, 0.07), (0.3, 0.3, 0.14))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    spine = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("PaloPodSrc")
    x, s, rv = g.separate(attr(g).outputs["Vector"])
    bump = g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", s, 15.7)))
    col = g.mix(g.ramp(rv, 0.0, 1.0), (0.2, 0.26, 0.07), (0.34, 0.33, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(bump, 0.75, 1.0), 0.5), col, (0.22, 0.2, 0.06))
    col = g.mix(g.ramp(s, 0.9, 1.0), col, (0.2, 0.12, 0.05))
    tr.tk.finish(mat, g, col, 0.0, 0.5)
    pod = tr.signals(mat, col, 0.5)

    mat, g = tr.tk.new_material("PaloSeedSrc")
    col = g.mix(g.ramp(g.noise(120.0, detail=2.0), 0.3, 0.7), (0.07, 0.05, 0.02), (0.14, 0.1, 0.04))
    tr.tk.finish(mat, g, col, 0.0, 0.35)
    seed = tr.signals(mat, col, 0.35)
    return {"petal": petal, "heart": heart, "leaf": leaflet, "twig": twig, "spine": spine, "pod": pod, "seed": seed}


PETAL = (0.0, 0.1, 0.4, 0.7, 0.9, 1.0), (0.1, 0.35, 0.9, 1.0, 0.7, 0.0)


def petal_profile(s):
    return float(np.interp(s, *PETAL))


def leaflet_profile(s):
    return float(np.interp(s, (0.0, 0.2, 0.6, 1.0), (0.4, 1.0, 0.8, 0.0)))


def pod_profile(s):
    taper = min(1.0, s / 0.05, (1.0 - s) / 0.12) ** 0.6
    return (0.66 + 0.34 * abs(math.sin(5.0 * math.pi * s))) * max(taper, 0.0)


def flower(m, rnd, c, n, size=1.0):
    """A five-petalled flower, centre `c`, facing `n`, the petals cupped a little, the fifth (banner) paler."""
    n = Vector(n).normalized()
    _, u, v = tr.basis(n)
    a0 = rnd.uniform(0, TAU)
    for k in range(5):
        az = a0 + k * TAU / 5 + rnd.uniform(-0.12, 0.12)
        out = u * math.cos(az) + v * math.sin(az)
        way = (out * math.cos(math.radians(22)) + n * math.sin(math.radians(22))).normalized()
        L = 0.0085 * size * rnd.uniform(0.88, 1.1)
        tr.blade(m, c + out * 0.0012 * size, way, n, L, L * rnd.uniform(0.86, 1.0), petal_profile, "petal", fold=0.08,
                 arch=rnd.uniform(0.0, 0.1), rows=4, rnd_value=0.95 if k == 4 else rnd.uniform(0.0, 0.7))
    tr.blade(m, c + n * 0.0014 * size, u, n, 0.0036 * size, 0.0036 * size,
             lambda q: float(np.interp(q, (0, 0.3, 0.8, 1.0), (0.5, 1.0, 0.8, 0.0))), "heart", rows=3)


def leaflets(m, rnd, p, tan, side, size=1.0):
    """A tiny pinnate leaf at p: a short rachis with three or four pairs of oval leaflets, to the twig's `side`."""
    out = (tr.rotate(tan, Z, 70.0 * side) + Vector((0.0, 0.0, rnd.uniform(-0.2, 0.2)))).normalized()
    out.y = out.y * 0.5 - 0.15
    out.normalize()
    L = 0.016 * size * rnd.uniform(0.8, 1.2)
    pts = [p, p + out * L * 0.5, p + out * L]
    tr.twig(m, pts, [0.0004, 0.0004, 0.0003], "twig", 3)
    nrm = Vector((rnd.gauss(0, 0.3), rnd.gauss(0, 0.3), 1.0))
    sd = nrm.cross(out).normalized()
    for i in range(4):
        f = 0.25 + 0.7 * i / 3
        q = p + out * (L * f)
        for sgn in (-1, 1):
            tr.blade(m, q, (out * 0.5 + sd * sgn).normalized(), nrm, 0.0055 * size * (1.0 - 0.15 * i),
                     0.0028 * size, leaflet_profile, "leaf", fold=0.1, rows=3, rnd_value=rnd.random())
    tr.blade(m, p + out * L, out, nrm, 0.005 * size, 0.0026 * size, leaflet_profile, "leaf", rows=3, rnd_value=rnd.random())


def zigzag(rnd, start, way, length, seg=0.036, zig=32.0, bend=0.5, down=(0.0, -1.0, 0.0)):
    """A zig-zag polyline from `start` heading `way`, `length` long: each segment alternately left and right."""
    n = max(2, int(round(length / seg)))
    base = Vector(way).normalized()
    pts = [Vector(start)]
    sgn = rnd.choice((-1, 1))
    for i in range(n):
        d = tr.rotate(base, Z, sgn * zig * rnd.uniform(0.6, 1.25))
        d.z += rnd.gauss(0.0, 0.2)
        pts.append(pts[-1] + d.normalized() * seg)
        sgn = -sgn
        base = base.lerp(Vector(down), bend / n).normalized()
    return pts


def sprig(m, rnd, start, way, length, r0, flower_p, leaf_p, pods=0, size=1.0, depth=0):
    """A zig-zag twig with flowers (probability `flower_p` at each node, on short stalks), tiny leaflets, side twigs
    and a thorn at its tip."""
    pts = zigzag(rnd, start, way, length, seg=0.03 if depth == 0 else 0.022, zig=28.0 if depth == 0 else 34.0)
    rad = [r0 * (1.0 - 0.7 * i / (len(pts) - 1)) for i in range(len(pts))]
    tr.twig(m, pts, rad, "twig", 4)
    end = pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.014
    tr.twig(m, [pts[-1], end], [rad[-1] * 0.8, 0.0002], "spine", 3)
    side = rnd.choice((-1, 1))
    for i in range(2, len(pts)):
        tan = (pts[i] - pts[i - 1]).normalized()
        if depth == 0 and i % 2 == 0 and i < len(pts) - 2 and length > 0.2:
            d = tr.rotate(tan, Z, side * rnd.uniform(40.0, 62.0))
            d.y -= 0.25
            d.z = rnd.uniform(-0.15, 0.15)
            sprig(m, rnd, pts[i], d, length * rnd.uniform(0.3, 0.5), r0 * 0.7, flower_p, leaf_p, size=size, depth=1)
            side = -side
        if rnd.random() < flower_p:
            perp = (tr.rotate(tan, Z, 90.0 * side) * rnd.uniform(0.6, 1.0)).normalized()
            stalk = (0.005 + 0.008 * rnd.random()) * size
            c = pts[i] + perp * stalk + Vector((0.0, 0.0, rnd.uniform(-0.004, 0.012)))
            tr.twig(m, [pts[i], pts[i] + (c - pts[i]) * 0.5, c], [0.0005, 0.00045, 0.0004], "twig", 3)
            ax = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), 0.0))
            nrm = tr.rotate(Z, ax, min(70.0, abs(rnd.gauss(0.0, 38.0)))) if ax.length > 1e-3 else Z.copy()
            flower(m, rnd, c, nrm, size * rnd.uniform(0.85, 1.12))
            side = -side
        elif rnd.random() < leaf_p:
            leaflets(m, rnd, pts[i], tan, side, size)
            side = -side
    return pts


def hang_pod(m, rnd, p, length=0.09):
    """A flat bumpy bean pod on a short stalk, hanging."""
    way = Vector((rnd.gauss(0.0, 0.18), -1.0, rnd.gauss(0.0, 0.1))).normalized()
    nrm = Vector((rnd.gauss(0, 0.3), 0.2, 1.0))
    q = p + Vector((0.0, -0.008, 0.002))
    tr.twig(m, [p, q], [0.0006, 0.0005], "twig", 3)
    L = length * rnd.uniform(0.85, 1.1)
    tr.blade(m, q, way, nrm, L, 0.013 * rnd.uniform(0.9, 1.1), pod_profile, "pod", fold=0.12, arch=rnd.uniform(0.0, 0.12),
             twist=rnd.uniform(-20, 20), rows=26, rnd_value=rnd.random())


def spray(m, rnd, kind, k):
    """One spray card: the attach point at the origin, hanging down -y. `kind` "bloom" (flowers on every node),
    "twig" (bare green twigs, k picks how many flowers and pods)."""
    side = rnd.choice((-1, 1))
    way = Vector((side * rnd.uniform(0.15, 0.4), -1.0, rnd.uniform(-0.1, 0.1)))
    if kind == "bloom":
        sprig(m, rnd, Vector(), way, rnd.uniform(0.4, 0.46), 0.0032, flower_p=1.0, leaf_p=0.1, size=1.25)
    else:
        fp, lp, pods = ((0.1, 0.3, 0), (0.0, 0.34, 0), (0.0, 0.2, 3), (0.06, 0.2, 2))[k]
        pts = sprig(m, rnd, Vector(), way, rnd.uniform(0.46, 0.52), 0.0032, flower_p=fp, leaf_p=lp, size=1.3)
        for j in range(pods):
            i = rnd.randint(4, len(pts) - 4)
            hang_pod(m, rnd, pts[i] + Vector((rnd.uniform(-0.01, 0.01), 0.0, 0.003)))


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(41)
    sprays = {}
    for names, kind in ((BLOOMS, "bloom"), (TWIGS, "twig")):
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
        pool = BLOOMS if ci == 0 else TWIGS
        m = tr.Mesh()
        side = (1, -1)[ci]
        stems = [tr.bend_path(Vector(), Vector((side * 0.35, -1.0, 0.1)), rnd.uniform(0.8, 0.9), 0.4, steps=10)]
        main = tr.Branch(stems[0], [0.006] * len(stems[0]))
        for f, s2 in ((0.2, -side), (0.45, side), (0.65, -side)):
            p, tan, _ = main.at(f)
            stems.append(tr.bend_path(p, tr.rotate(tan, (0.0, 0.0, 1.0), s2 * rnd.uniform(40.0, 60.0)),
                                      rnd.uniform(0.35, 0.5), 0.5, steps=8))
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
                rot = (Matrix.Rotation(math.radians(spin), 4, "Z")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-55, 55)), 4, "Y")
                       @ Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 4, "X"))
                c.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Scale(rnd.uniform(0.75, 1.0), 4)
                objs.append(c)
        atlas.frame(atlas.cells[name], objs)
        if render:
            atlas.render(atlas.cells[name], objs)
    # The seedling's leaf: one bipinnate leaf on a short stalk
    m = tr.Mesh()
    p0 = Vector((0.0, -0.012, 0.0))
    tr.twig(m, [Vector(), p0], [0.0006, 0.0005], "twig", 3)
    for sgn in (-1, 1):
        base = p0
        way = Vector((0.7 * sgn, -0.7, 0.0))
        pts = [base, base + way.normalized() * 0.02, base + way.normalized() * 0.04]
        tr.twig(m, pts, [0.0004, 0.0004, 0.0003], "twig", 3)
        for i in range(5):
            q = base + way.normalized() * (0.008 + 0.0072 * i)
            for sg2 in (-1, 1):
                tr.blade(m, q, (way.normalized() * 0.4 + Vector((sg2 * 0.6, 0.0, 0.0))).normalized(), Vector((0, 0.2, 1)),
                         0.009, 0.0045, leaflet_profile, "leaf", rows=3, rnd_value=rnd.random())
    leaf = m.build(LEAF + "Src", mats)
    atlas.frame(atlas.cells[LEAF], [leaf])
    if render:
        atlas.render(atlas.cells[LEAF], [leaf])
    if not render:
        return None
    out = atlas.save(FOLDER, "PaloVerdeLeaves")
    atlas.preview(os.path.join(PREVIEWS, "palo_verde_atlas.png"))
    for c in atlas.cells.values():
        sl = (slice(c.y, c.y + c.h), slice(c.x, c.x + c.w))
        op = atlas.alpha[sl] > 0.5
        mean = tuple(int(v) for v in np.round(atlas.albedo[sl][op].mean(0) * 255)) if op.any() else None
        print("[palo_verde] cell %s coverage %.3f mean %s" % (c.name, c.coverage, mean))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("PaloVerdeLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def crown_shape(t):
    """Limb length up the span: longer higher up, so the crown is a vase opening into an umbrella."""
    return 0.5 + 0.5 * min(1.0, t) ** 0.7


def palo(trunks, cells, cluster_cells, limbs=1.7, reach=1.0, budget=8000, card_scale=(1.3, 1.8), spacing=0.06,
         twigs=3.6, fine=3.2):
    l1 = tr.Level(per_meter=limbs, span=(0.3, 0.98), length=(1.2 * reach, 2.4 * reach), shape=crown_shape,
                  angle=38.0, angle_tip=26.0, angle_vary=12.0, radius=0.55, radius_length=0.6, radius_max=0.035,
                  tip_radius=0.006, step=0.2, gravitropism=0.55, droop=0.12, wander=0.55, outward=0.5, floor=0.7,
                  sides=(7, 5, 3), seg=(0.5, 0.9, 1.6), min_len=(0.0, 0.0, 0.0))
    l2 = tr.Level(per_meter=twigs, span=(0.1, 0.97), length=(0.6 * reach ** 0.5, 1.3 * reach ** 0.5), shape="tapered",
                  angle=52.0, angle_tip=40.0, angle_vary=12.0, planar=0.15, radius=0.5, radius_length=0.6,
                  radius_max=0.012, tip_radius=0.004, step=0.2, gravitropism=0.3, droop=0.2, wander=0.75, outward=0.35,
                  floor=0.8, sides=(3, 3, 0), seg=(0.5, 0.9, 9.0), min_len=(0.0, 0.5, 99.0))
    l3 = tr.Level(per_meter=fine, span=(0.1, 0.98), length=(0.3, 0.65), shape="tapered", angle=55.0, angle_tip=42.0,
                  angle_vary=12.0, radius=0.45, radius_length=0.5, radius_max=0.006, tip_radius=0.0025, step=0.1,
                  gravitropism=0.2, droop=0.2, wander=0.85, outward=0.3, floor=0.8, sides=(3, 3, 0),
                  seg=(0.3, 0.6, 9.0), min_len=(0.0, 0.4, 99.0))
    return tr.TreeSpec(
        trunks=trunks, levels=[l1, l2], budget=budget, bark_budget=3000,
        foliage=tr.Foliage(levels={2: (0.12, 1.0), 1: (0.5, 1.0)}, trunk_top=None, spacing=spacing, cells=cells,
                           scale=card_scale, hang=0.02, spread=0.4, out=0.5, face=0.6, up=0.5, roll=60.0, bend=0.0),
        cluster=tr.Foliage(levels={1: (0.3, 1.0), 2: (0.5, 1.0)}, spacing=0.9, cells=cluster_cells,
                           scale=(0.85, 1.15), hang=0.35, spread=0.3, out=0.5, face=0.8, up=0.3, roll=30.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V)


def stems(seed, heights, lean, radius=0.085, bow=0.55, spread=0.12, tilt=(0.0, 0.0), az0=None):
    """A low-dividing clump: stems from within `spread` m of the origin, each heading out at its own bearing."""
    rnd = random.Random(seed)
    a0 = rnd.uniform(0, TAU) if az0 is None else az0
    n = len(heights)
    out = []
    for i, h in enumerate(heights):
        az = a0 + i * TAU / n + rnd.uniform(-0.35, 0.35)
        L = lean * rnd.uniform(0.75, 1.25)
        out.append(tr.Trunk(height=h, radius=radius * rnd.uniform(0.85, 1.12), flare=0.35, flare_height=0.3,
                            taper=0.55, tip_radius=0.012, lean=(L * math.cos(az) + tilt[0], L * math.sin(az) + tilt[1]),
                            bow=bow, wander=0.14, base=(spread * math.cos(az), spread * math.sin(az)), sink=0.3,
                            step=0.3, sides=(10, 7, 5), seg=(0.5, 1.0, 2.0),
                            rings=((0.0, 0.25, 0.6), (0.0,), (0.0,))))
    return out


def sapling():
    """The seedling a planted seed shows (about 0.5 m): a slender green stem with a few side shoots, hung with small
    bipinnate leaves."""
    shoots = tr.Level(count=(3, 5), span=(0.3, 0.85), length=(0.1, 0.22), shape="tapered", angle=55.0, angle_tip=40.0,
                      radius=0.6, radius_length=0.5, radius_max=0.0025, tip_radius=0.0008, step=0.03,
                      gravitropism=0.5, droop=0.2, wander=0.5, floor=0.02, sides=(4, 3, 0), seg=(0.05, 0.1, 9.0),
                      min_length=0.04, min_len=(0.0, 0.0, 99.0))
    return tr.TreeSpec(
        trunks=[tr.Trunk(height=0.55, radius=0.0042, flare=0.2, flare_height=0.04, taper=0.9, tip_radius=0.0012,
                         lean=(0.03, 0.02), bow=0.3, wander=0.04, sink=0.06, step=0.04, sides=(6, 4, 3),
                         seg=(0.08, 0.16, 0.4), rings=((0.0,), (0.0,), (0.0,)))],
        levels=[shoots],
        foliage=tr.Foliage(levels={1: (0.0, 1.0)}, trunk_top=(0.3, 1.0), spacing=0.035, cells=(LEAF,),
                           scale=(0.7, 1.05), hang=0.2, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        cluster=tr.Foliage(levels={}, trunk_top=(0.3, 1.0), spacing=0.06, cells=(LEAF,), scale=(0.9, 1.2),
                           hang=0.25, spread=0.5, out=0.6, face=0.5, up=0.5, roll=35.0, bend=0.0),
        bark_key=bark_key, bark_uv=UV, ground_v=GROUND_V, budget=500, lod_share=(0.55, 0.3))


FULL = (BLOOMS[0], BLOOMS[1], BLOOMS[2], BLOOMS[3], BLOOMS[0], BLOOMS[1], BLOOMS[2], BLOOMS[3], TWIGS[1])
HALF = (BLOOMS[0], BLOOMS[1], BLOOMS[2], BLOOMS[3], TWIGS[0], TWIGS[1], TWIGS[1], TWIGS[3])
POST = (TWIGS[0], TWIGS[1], TWIGS[2], TWIGS[3], TWIGS[1], TWIGS[1], BLOOMS[0])
VARIANTS = [
    # Full bloom: four stems from a short trunk, a broad vase about 5.5 m
    ("PaloVerde01", 11, lambda: palo(stems(5, [2.8, 3.0, 2.7, 2.9], 2.0, radius=0.06, bow=0.35), FULL, ("CloudBloom",) * 3 + ("CloudGreen",),
                                     limbs=1.7, budget=8500, spacing=0.06)),
    # A leaning multi-stem tree about 6.5 m in half bloom
    ("PaloVerde02", 23, lambda: palo(stems(8, [3.4, 3.1, 2.7], 1.2, radius=0.065, tilt=(1.0, 0.45), az0=0.4), HALF,
                                     ("CloudBloom", "CloudGreen"), limbs=1.7, reach=1.1, budget=8000, spacing=0.06)),
    # Low and wide, post-bloom: five short stems fanning out, 4 m
    ("PaloVerde03", 37, lambda: palo(stems(12, [1.8, 2.0, 1.7, 1.9, 1.8], 2.0, radius=0.05, bow=0.4, spread=0.1), POST,
                                     ("CloudGreen",) * 3 + ("CloudBloom",), limbs=1.6, reach=0.95, budget=7500,
                                     spacing=0.075)),
    # Young whip, 3 m
    ("PaloVerde04", 41, lambda: palo([tr.Trunk(height=2.5, radius=0.028, flare=0.3, flare_height=0.2, taper=0.7,
                                               tip_radius=0.008, lean=(0.35, -0.2), bow=0.4, wander=0.12, sink=0.2,
                                               step=0.25, sides=(7, 5, 4), seg=(0.4, 0.8, 1.6),
                                               rings=((0.0, 0.2), (0.0,), (0.0,)))], POST, ("CloudGreen",),
                                     limbs=2.2, reach=0.6, budget=4500, spacing=0.08, twigs=2.4)),
    ("PaloVerdeSapling", 53, sapling),
]


# ---------------------------------------------------------------- the seed's icon

def make_icon():
    """PaloVerdeSeed_Icon.png (160 x 160): a flat bumpy bean pod with its seeds, and a sprig of yellow flowers behind,
    under zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials()
    rnd = random.Random(7)
    m = tr.Mesh()
    # A flowering sprig behind (in the card frame x right, y up, facing +z)
    tw = tr.bend_path(Vector((-0.07, 0.085, -0.02)), Vector((1.0, -0.35, 0.0)), 0.17, 0.35, steps=8)
    tr.twig(m, tw, [0.0016 - 0.0008 * i / 8 for i in range(9)], "twig", 5)
    for i, c in enumerate((0.3, 0.5, 0.7, 0.92)):
        br = tr.Branch(tw, [0.0012] * len(tw))
        p, tan, _ = br.at(c)
        q = p + Vector((0.0, 0.012 if i % 2 else -0.012, 0.0))
        flower(m, rnd, q + Vector((0, 0, 0.006)), Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(0.0, 0.4), 1.0)), 2.6)
    # Two pods
    for (x, y, ang, L) in ((-0.02, -0.01, -14.0, 0.2), (0.0, -0.06, 8.0, 0.19)):
        way = tr.rotate(Vector((1.0, 0.0, 0.0)), Z, ang)
        tr.blade(m, Vector((x - 0.1, y, 0.02)), way, Vector((0.0, 0.1, 1.0)), L, 0.024, pod_profile, "pod", fold=0.2,
                 arch=0.05, rows=40, rnd_value=rnd.random())
    # Loose seeds: oblong, dark olive-brown
    for (x, y, ang) in ((-0.07, -0.11, 20.0), (-0.035, -0.125, -10.0), (0.01, -0.118, 30.0)):
        way = tr.rotate(Vector((1.0, 0.0, 0.0)), Z, ang)
        tr.blade(m, Vector((x, y, 0.03)), way, Vector((0.0, 0.3, 1.0)), 0.026, 0.017,
                 lambda q: float(np.interp(q, (0, 0.25, 0.75, 1.0), (0.45, 1.0, 1.0, 0.45))), "seed", fold=0.0, rows=6)
    obj = m.build("PaloVerdeSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (5.0, 5.0, 5.0)
    obj.location = (0.0, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.8)
    tr.tk.icon(cam, os.path.join(FOLDER, "PaloVerdeSeed_Icon.png"), hide=())
    print("[palo_verde] icon written")


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
    mats = {"bark": tr.textured("PaloVerdeBark", paths("PaloVerdeBark")),
            "foot": tr.textured("PaloVerdeBarkFoot", paths("PaloVerdeBarkFoot")),
            "twig": tr.textured("PaloVerdeBarkTwig", paths("PaloVerdeBarkTwig")),
            "leaves": tr.textured("PaloVerdeLeaves", paths("PaloVerdeLeaves"), cutout=True, translucent=0.3)}
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
        print("[palo_verde] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f; %d branches, %d cards"
              % (name, size[0], size[1], size[2], size[3][0], size[3][1], len(tree.branches), len(tree.cards)))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("paloverde01", lods[0], PREVIEWS, figure)
    tr.preview_lods("paloverde01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("palo_verde", [b[2][0] for b in built if b[0] != "PaloVerdeSapling"], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[palo_verde] done")


main()
