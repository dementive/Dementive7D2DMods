"""Joshua tree (Yucca brevifolia) for the desert, on treekit.py (birch.py is the worked example; TREES.md has the
rules).

A tree-sized yucca: a stout column of a trunk that forks at its top, and each arm forks again at its end, two or three
ways, every arm about as thick as the last and curving up; at the end of every arm a dense ball of stiff, sharp,
olive-green leaves 20 to 35 cm long, the young ones pointing up, the old ones out and down, the dead ones hanging
below. The arms and young trunks are shaggy with the dead leaves (a thatch hanging down, grey and straw); old trunks
have lost it and show corky grey-brown bark in small blocks. Forms: an old much-branched tree, a younger one of a few
arms, an unbranched column, a young one; the seedling a small rosette on a stub.

    blender -b --factory-startup --python trees/joshua_tree.py -- <unity trees folder> <preview folder> [step]

with absolute paths to `NatureExpanded/unity/Assets/NatureExpanded/Trees` and
`NatureExpanded/unity/Build/previews/trees`. Steps as birch.py's: `all`, `textures`, `bark`, `bark-textures`, `atlas`,
`trees`, `icon`. It writes Trees/JoshuaTree/ (bark, thatch and leaf textures, JoshuaTree01..04 and JoshuaTreeSapling
with their impostors, JoshuaTreeSeed_Icon.png), the JoshuaTree lines of Trees/trees.txt and trunks.txt, and the
previews. Built at its size in game.

The leaves are cards too, but one leaf each (cut from a narrow cell of a single leaf), set round the end of every arm
as the real leaves are: `rosettes` places them after the tree grows. LOD1 keeps fewer, bigger; LOD2 has the atlas's
rendered rosettes, a few crossed at each arm's end (the cluster Foliage, `on` the tips only).
"""
import math
import os
import random
import sys

import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import treekit as tr  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
TREES, PREVIEWS = args[0], args[1]
STEPS = args[2] if len(args) > 2 else "all"
FOLDER = os.path.join(TREES, "JoshuaTree")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))

# ---------------------------------------------------------------- bark textures
#
# JoshuaTreeBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii, drawn at its size on
# JoshuaTree01's 32 cm trunk (about 20 px per cm): the old trunk's corky blocks. JoshuaTreeBarkThatch: 1024 x 2048, the
# same wraps and tiling (so the two meet without a jump), drawn at its size on a 12 cm arm (about 27 px per cm): the
# dead leaves hanging in a thatch. Old trunks (over about 20 cm at the ground) are bark, everything else thatch.

W, H, WRAPS = 2048, 4096, 2
TW, TH = 1024, 2048
K = TAU * H / (WRAPS * W)
R_DESIGN = 32.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
T_DESIGN = 12.0
TPX = WRAPS * TW / (TAU * T_DESIGN)
R_BARK = 0.15
# Mean albedo (sRGB): the corky bark a grey-brown; the leaves an olive green, a little yellow
BARK_MEAN = (100, 90, 78)
LEAF_MEAN = (84, 96, 52)
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=0.1),
    "thatch": tr.BarkUV(k=K, wraps=WRAPS, twist=0.0),
}


def bark_key(br, s, r, z):
    """Corky bark on an old thick trunk, the thatch of dead leaves on every arm and on young trunks: the change falls
    at the first fork, where it reads as natural (partway up a trunk it was a hard ring)."""
    return "bark" if br.level == 0 and br.radii[0] > R_BARK * 1.4 else "thatch"


def corky_bark(r, h=H, w=W, px=PX):
    """Old Joshua tree bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm:
    rugged grey-brown cork in narrow blocks 3 to 5 cm across and twice as tall, each raised to its own height and
    tilted, broken across here and there, between deep dark furrows; the cork in thin layers, fibrous up it, crumbling
    at the blocks' edges; old leaf fibres caught in some furrows."""
    cm = px
    warp = ((tr.fbm(r, h, w, (2.5 * cm, 6 * cm), 3) - 0.5) * 1.6 * cm,
            (tr.fbm(r, h, w, (2.5 * cm, 6 * cm), 3) - 0.5) * 2.5 * cm)
    edge, block, by, _ = tr.cells(r, h, w, 3.8 * cm, 2.0, warp)
    n = block.max() + 1
    bshade, braise, btilt = r.random(n)[block], r.random(n)[block], (r.random(n) * 2.0 - 1.0)[block]
    Y = np.mgrid[0:h, 0:w][0].astype(np.float64)
    wobble = tr.fbm(r, h, w, (1.0 * cm, 2.5 * cm), 3)
    fw = (0.35 + 0.6 * wobble) * cm
    furrow = 1.0 - tr.smoothstep(0.0, fw, edge)
    crumb = tr.fbm(r, h, w, (0.25 * cm, 0.25 * cm), 3)
    shoulder = tr.smoothstep(0.0, (0.6 + 0.8 * crumb) * cm, edge - fw * 0.6)
    # Breaks across the blocks
    cedge, _, _, _ = tr.cells(r, h, w, 2.5 * cm, 0.45, warp)
    across = ((1.0 - tr.smoothstep(0.0, 0.12 * cm, cedge)) * shoulder
              * tr.smoothstep(0.45, 0.6, tr.fbm(r, h, w, (3 * cm, 3 * cm), 3)))
    fibre = tr.fbm(r, h, w, (0.12 * cm, 1.4 * cm), 4)
    layer = tr.fbm(r, h, w, (1.6 * cm, 0.18 * cm), 3)
    grit = tr.fbm(r, h, w, (0.06 * cm, 0.06 * cm), 2)
    mottle = tr.fbm(r, h, w, (5 * cm, 8 * cm), 4)
    tilt = np.clip((Y - by) / (3.0 * cm), -1.0, 1.0) * btilt
    col = tr.mix((0.27, 0.245, 0.22), (0.52, 0.48, 0.43),
                 0.25 * bshade + 0.2 * fibre + 0.15 * layer + 0.15 * grit + 0.15 * mottle + 0.1 * (tilt * 0.5 + 0.5))
    col = tr.mix(col, col * np.array((1.12, 1.0, 0.85)), tr.smoothstep(0.62, 0.85, mottle)[..., None] * 0.6)
    col = tr.mix(col, col * 0.6, (1.0 - shoulder)[..., None] * 0.6)
    col = tr.mix(col, (0.08, 0.065, 0.05), across * 0.85)
    col = tr.mix(col, (0.04, 0.032, 0.025), tr.smoothstep(0.15, 0.7, furrow))
    fib = tr.smoothstep(0.7, 0.8, tr.fbm(r, h, w, (0.1 * cm, 3 * cm), 3)) * tr.smoothstep(0.3, 0.8, furrow)
    fib *= tr.smoothstep(0.55, 0.7, tr.fbm(r, h, w, (8 * cm, 12 * cm), 3))
    col = tr.mix(col, (0.5, 0.44, 0.33), fib * 0.7)
    height = (2.2 * (1.0 - furrow) + 0.8 * shoulder + 0.6 * braise * shoulder + 0.3 * tilt * shoulder
              + 0.35 * fibre + 0.25 * layer + 0.2 * grit + 0.2 * crumb - 0.8 * across + 0.3 * fib)
    rough = 0.9 + 0.05 * (grit - 0.5)
    occ = tr.cavity(height, 4.0 * RELIEF, 0.35)
    col = col * (0.7 + 0.3 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def thatch(r, h=TH, w=TW, px=TPX):
    """The thatch of dead leaves (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm
    (rows run up the arm): row on row of narrow leaves 12 to 22 cm long hanging down from where they grew, each one
    lying over the bases of those below it, their tips sticking out and frayed into fibres; weathered grey, straw and
    brown, darker toward their hidden bases, the gaps between them dark."""
    cm = px
    top = np.full((h, w), -9.0)
    who = np.full((h, w), -1, np.int64)
    t_at = np.zeros((h, w))
    x_at = np.zeros((h, w))
    fib = tr.fbm(r, h, w, (0.07 * cm, 2.5 * cm), 3)
    rows, cols = int(round(h / (5.0 * cm))), int(round(w / (0.95 * cm)))
    count = rows * cols
    shade, kind = r.random(count), r.random(count)
    i = 0
    for j in range(rows):
        for k in range(cols):
            x = (k + r.uniform(-0.45, 0.45) + 0.5 * (j % 2)) * w / cols
            y = (j + r.uniform(-0.35, 0.35)) * h / rows  # where it grew: it hangs down from here
            L = r.uniform(12.0, 22.0) * cm
            wd = r.uniform(0.8, 1.35) * cm
            skew = r.uniform(-0.1, 0.1)
            kh, kw = int(L) + 3, int(wd + abs(skew) * L) + 6
            t = (np.arange(kh, dtype=np.float64) / (kh - 1))[:, None]  # 0 at its tip (the bottom row), 1 at its base
            dx = np.arange(kw, dtype=np.float64)[None, :] - ((kw - 1) * 0.5 + skew * (t - 0.5) * L)
            half = 0.5 * wd * np.clip(t / 0.3, 0.0, 1.0) ** 0.6
            ys = (np.arange(kh) + int(math.floor(y - L))) % h
            xs = (np.arange(kw) + int(math.floor(x - kw * 0.5))) % w
            ix = np.ix_(ys, xs)
            inside = (np.abs(dx) < half) & ((t > 0.3) | (fib[ix] + 1.2 * t > 0.55))
            across = np.clip(dx / np.maximum(half, 0.5), -1.0, 1.0)
            lift = r.uniform(0.0, 0.3) + 1.5 * (1.0 - t) - 0.35 * across ** 2
            win = inside & (lift > top[ix])
            top[ix] = np.where(win, lift, top[ix])
            who[ix] = np.where(win, i, who[ix])
            t_at[ix] = np.where(win, t, t_at[ix])
            x_at[ix] = np.where(win, across, x_at[ix])
            i += 1
    leaf = who >= 0
    idx = np.maximum(who, 0)
    grey, straw, brown = np.array((0.47, 0.45, 0.42)), np.array((0.6, 0.52, 0.38)), np.array((0.38, 0.29, 0.2))
    kk = kind[idx][..., None]
    base = np.where(kk < 0.5, grey, np.where(kk < 0.85, straw, brown))
    col = base * (0.75 + 0.35 * shade[idx])[..., None]
    col = col * (1.0 - 0.45 * t_at - 0.3 * x_at ** 2)[..., None] * (0.85 + 0.3 * fib)[..., None]
    col = np.where(leaf[..., None], col, np.array((0.05, 0.04, 0.035)))
    height = np.where(leaf, top + 0.15 * fib, -0.8)
    rough = np.where(leaf, 0.82 + 0.08 * fib, 0.95)
    occ = tr.cavity(height, 3.0 * TPX / 13.0, 0.35)
    col = col * (0.65 + 0.35 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ


def make_bark():
    r = np.random.default_rng(29)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ = corky_bark(r)
    col, _ = tr.match_mean(col, BARK_MEAN)
    save("JoshuaTreeBark", col, height, rough, occ, RELIEF * 1.8)
    save("JoshuaTreeBarkThatch", *thatch(r), TPX / 13.0 * 1.5)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the leaf atlas
#
# 2048 square: six live leaves and three dead ones along the top, each alone in a narrow cell (96 x 768) with its base
# at the cell's attach point (the rosettes' cards); two rendered rosettes (1024 square) for LOD2.

BLADES = tuple("Blade%d" % i for i in range(6))
DEAD = tuple("Dead%d" % i for i in range(3))
ROSETTES = ("Rosette0", "Rosette1")


def layout():
    atlas = tr.Atlas(2048)
    for i, name in enumerate(BLADES + DEAD):
        atlas.cell(name, 96 * i, 1280, 96, 768, (0.04, 0.32))
    atlas.cell(ROSETTES[0], 1024, 1024, 1024, 1024, (0.9, 0.9))
    atlas.cell(ROSETTES[1], 1024, 0, 1024, 1024, (0.9, 0.9))
    return atlas


def leaf_profile(s):
    """A Joshua tree leaf's half-width along it: a sheath at its base, then tapering straight to a sharp point."""
    if s < 0.06:
        return 0.75 + 0.25 * s / 0.06
    return max(0.0, (1.0 - s) / 0.94) ** 0.9


def leaf(m, rnd, base, way, normal, length, dead=False):
    """One leaf from `base` along `way`: stiff, channeled, finely toothed; a dead one twisted and curling."""
    tr.blade(m, base, way, normal, length, length * rnd.uniform(0.04, 0.05), leaf_profile,
             "dead" if dead else "leaf", teeth=36, tooth=0.05, fold=0.3 if dead else 0.55,
             arch=rnd.uniform(0.1, 0.25) if dead else rnd.uniform(0.0, 0.06),
             twist=rnd.uniform(-60, 60) if dead else rnd.uniform(-12, 12), rows=24, rnd_value=rnd.random())


def leaf_materials(shade=0.0):
    """The leaves' own materials (rendered into the atlas, not exported): live leaves, dead ones, the stem."""
    mat, g = tr.tk.new_material("JoshuaLeafSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    back = tr.tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Backfacing")
    # Olive green, leaf to leaf yellower or bluer; a pale yellow sheath at the base, yellowish margins, a hard brown
    # spine at the tip; the underside paler
    # (Linear values, set so the leaves come out near LEAF_MEAN: the atlas isn't graded, as the rosette cells carry
    # the stem and dead leaves too)
    base = g.mix(g.ramp(rv, 0.1, 0.9), (0.05, 0.08, 0.016), (0.1, 0.125, 0.03))
    base = g.mix(g.ramp(rv, 0.85, 1.0), base, (0.055, 0.085, 0.05))
    # Fine parallel veins along it
    vein = g.ramp(g.math("SINE", g.math("MULTIPLY", across, 48.0)), 0.4, 1.0)
    base = g.mix(g.math("MULTIPLY", vein, 0.3), base, (0.03, 0.05, 0.01))
    col = g.mix(g.ramp(along, 0.09, 0.0), base, (0.22, 0.2, 0.07))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", across), 0.7, 0.95), 0.6), col, (0.17, 0.16, 0.05))
    col = g.mix(g.ramp(along, 0.92, 0.97), col, (0.06, 0.035, 0.015))
    col = g.mix(g.math("MULTIPLY", back, 0.4), col, (0.14, 0.16, 0.07))
    if shade:
        col = g.mix(shade, col, (0.02, 0.025, 0.01))
    rough = g.mixf(back, 0.5, 0.65)
    tr.tk.finish(mat, g, col, 0.0, rough)
    live = tr.signals(mat, col, rough)

    mat, g = tr.tk.new_material("JoshuaDeadSrc")
    across, along, rv = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    col = g.mix(g.ramp(rv, 0.1, 0.9), (0.15, 0.12, 0.075), (0.3, 0.24, 0.15))
    col = g.mix(g.ramp(rv, 0.8, 1.0), col, (0.2, 0.19, 0.17))
    col = g.mix(g.ramp(along, 0.85, 1.0), col, (0.07, 0.05, 0.03))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(300.0, detail=2.0), 0.4, 0.7), 0.3), col, (0.1, 0.08, 0.055))
    tr.tk.finish(mat, g, col, 0.0, 0.8)
    dead = tr.signals(mat, col, 0.8)

    mat, g = tr.tk.new_material("JoshuaStemSrc")
    col = g.mix(g.ramp(g.noise(80.0, detail=3.0), 0.3, 0.7), (0.1, 0.085, 0.06), (0.22, 0.19, 0.14))
    tr.tk.finish(mat, g, col, 0.0, 0.85)
    stem = tr.signals(mat, col, 0.85)
    return {"leaf": live, "dead": dead, "twig": stem}


def rosette_mesh(m, rnd, live=170, dead=34, size=1.0):
    """A whole rosette for the LOD2 cells, built in the card's frame (x right, y up the arm, facing +z) round the
    origin: the arm's end coming up from below, leaves all round its last 15 cm, the newest pointing up, the oldest
    out and down; dead ones hanging below."""
    ax = Vector((0.0, 1.0, 0.0))
    tr.twig(m, [Vector((0.0, -0.4 * size, 0.0)), Vector((0.0, -0.1 * size, 0.0)), Vector((0.0, -0.03, 0.0))],
            [0.06 * size, 0.055 * size, 0.04 * size], "twig", 10)
    for i in range(live):
        f = (i + rnd.random()) / live
        at = Vector((0.0, -0.15 * size * f, 0.0))
        az = i * tr.GOLDEN + rnd.uniform(-0.3, 0.3)
        out = Vector((math.cos(az), 0.0, math.sin(az)))
        th = math.radians(8.0 + 100.0 * f ** 0.8 + rnd.gauss(0.0, 8.0))
        way = ax * math.cos(th) + out * math.sin(th)
        nrm = tr.rotate(out.cross(way).normalized(), way, rnd.uniform(-50.0, 50.0))
        leaf(m, rnd, at + out * 0.035 * size, way, nrm, rnd.uniform(0.22, 0.34) * size)
    for i in range(dead):
        f = rnd.random()
        az = rnd.uniform(0.0, TAU)
        out = Vector((math.cos(az), 0.0, math.sin(az)))
        at = Vector((0.0, -(0.15 + 0.22 * f) * size, 0.0)) + out * 0.05 * size
        way = (-ax * rnd.uniform(0.75, 1.0) + out * rnd.uniform(0.15, 0.5)).normalized()
        nrm = tr.rotate(out.cross(way).normalized(), way, rnd.uniform(-60.0, 60.0))
        leaf(m, rnd, at, way, nrm, rnd.uniform(0.2, 0.3) * size, dead=True)


def make_atlas(atlas, render=True):
    mats = leaf_materials()
    rnd = random.Random(19)
    for name in BLADES + DEAD:
        m = tr.Mesh()
        dead = name in DEAD
        # Lying down the cell from its attach point, facing the camera
        leaf(m, rnd, Vector(), Vector((0.0, -1.0, 0.0)), Vector((0.0, 0.0, 1.0)),
             rnd.uniform(0.26, 0.34) if not dead else rnd.uniform(0.22, 0.3), dead)
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        if render:
            atlas.render(atlas.cells[name], [obj])
    for name in ROSETTES:
        m = tr.Mesh()
        rosette_mesh(m, rnd)
        obj = m.build(name + "Src", mats)
        atlas.frame(atlas.cells[name], [obj])
        if render:
            atlas.render(atlas.cells[name], [obj])
    if not render:
        return None
    sel = np.zeros_like(atlas.alpha, bool)
    for name in BLADES:
        c = atlas.cells[name]
        sel[c.y:c.y + c.h, c.x:c.x + c.w] = True
    sel &= atlas.alpha > 0.5
    print("[joshua_tree] leaves average %s (aiming at %s)" % (
        tuple(int(v) for v in np.round(atlas.albedo[sel].mean(0) * 255)), LEAF_MEAN))
    out = atlas.save(FOLDER, "JoshuaTreeLeaves")
    atlas.preview(os.path.join(PREVIEWS, "joshua_tree_atlas.png"))
    for c in atlas.cells.values():
        print("[joshua_tree] cell %s coverage %.3f" % (c.name, c.coverage))
    return out


def load_coverage(atlas):
    a = tr.read_image(paths("JoshuaTreeLeaves")["albedo"])[..., 3]
    for c in atlas.cells.values():
        c.coverage = float(a[c.y:c.y + c.h, c.x:c.x + c.w].mean())


# ---------------------------------------------------------------- the trees

def tag_tips(tree):
    """Tags "tip" every arm (or unbranched trunk) nothing grows on from its end: the ones that end in a rosette."""
    for br in tree.branches:
        if "stub" in br.tags:
            continue
        if not any(c.s_parent > 0.85 and "stub" not in c.tags for c in br.children):
            br.tags.add("tip")


class LeafCard(tr.Card):
    """A card set out from its branch's axis by `off` (a leaf growing from the arm's surface, not its middle)."""

    def __init__(self, p, a, n, cell, scale, host, s, off):
        super().__init__(p, a, n, cell, scale, host, s)
        self.off = Vector(off)

    def scaled(self, k):
        return LeafCard(self.p, self.a, self.n, self.cell, self.scale * k, self.host, self.s, self.off)

    def on(self, lod):
        return LeafCard(self.host.drawn_at(self.s, lod) + self.off, self.a, self.n, self.cell, self.scale, self.host,
                        self.s, self.off)


def rosettes(tree, rnd, live=(75, 95), dead=(12, 18), size=1.4):
    """The leaf cards round the end of every tip: `live` leaves set round its last 15 cm (`size` scales it all),
    the newest at the top pointing up along it, each older one lower and further out, the oldest out and a little
    down; `dead` ones hanging below them."""
    cells = tr.ATLAS_CELLS
    cards = []
    for br in tree.branches:
        if "tip" not in br.tags:
            continue
        L = br.length
        core = min(0.15 * size, L * 0.3)
        n = rnd.randint(*live)
        for i in range(n):
            f = (i + rnd.random()) / n
            s = 1.0 - (core / L) * (0.01 + 0.98 * f)
            p, tan, r = br.at(s)
            _, u, v = tr.basis(tan)
            az = i * tr.GOLDEN + rnd.uniform(-0.3, 0.3)
            out = u * math.cos(az) + v * math.sin(az)
            th = math.radians(8.0 + 100.0 * f ** 0.8 + rnd.gauss(0.0, 8.0))
            a = tan * math.cos(th) + out * math.sin(th)
            nrm = tr.rotate(out.cross(a).normalized(), a, rnd.uniform(-50.0, 50.0))
            cards.append(LeafCard(p, a, nrm, cells[rnd.choice(BLADES)], rnd.uniform(0.75, 1.1) * size, br, s,
                                  out * r * 0.6))
        skirt = min(0.3 * size, L * 0.5 - core)
        for _ in range(rnd.randint(*dead) if skirt > 0.02 else 0):
            f = rnd.random()
            s = max(0.02, 1.0 - (core + skirt * f) / L)
            p, tan, r = br.at(s)
            _, u, v = tr.basis(tan)
            az = rnd.uniform(0.0, TAU)
            out = u * math.cos(az) + v * math.sin(az)
            a = (-tan).lerp(DOWN, 0.5) * rnd.uniform(0.8, 1.0) + out * rnd.uniform(0.15, 0.45)
            a.normalize()
            nrm = tr.rotate(out.cross(a).normalized() if out.cross(a).length > 1e-3 else u, a, rnd.uniform(-60, 60))
            cards.append(LeafCard(p, a, nrm, cells[rnd.choice(DEAD)], rnd.uniform(0.75, 1.0) * size, br, s,
                                  out * r * 0.85))
    return cards


def arms(count, length, angle=48.0, grav=0.35, sides=(9, 7, 5)):
    """One more fork: `count` arms off the end of each arm before (or the trunk), `length` long, `angle` off it,
    pushed out from the trunk so they spread rather than cross, curving up (`grav`), barely thinner than it and
    ending blunt (in a rosette). Old trees fork often in short segments (a year or a few of growth between
    flowerings): many short levels, not a few long ones."""
    return tr.Level(count=count, span=(0.97, 1.0), length=length, angle=angle, angle_vary=10.0, radius=0.82,
                    radius_length=0.3, tip_radius=0.02, broken=True, taper=0.5, step=0.1, gravitropism=grav,
                    outward=0.3, wander=0.25, floor=0.6, sides=sides, seg=(0.3, 0.6, 1.2), min_length=0.2)


def joshua(trunks, levels, budget=9000):
    return tr.TreeSpec(
        trunks=trunks, levels=levels, budget=budget, bark_budget=budget,
        foliage=tr.Foliage(levels={}, trunk_top=None, cells=BLADES, bend=0.0),
        cluster=tr.Foliage(levels={i: (0.985, 1.0) for i in range(1, 6)}, trunk_top=(0.985, 1.0), spacing=0.1,
                           cells=ROSETTES, scale=(1.25, 1.5), hang=1.0, spread=0.05, out=0.0, face=0.0, up=0.0,
                           roll=0.0, bend=0.0, on=lambda br: "tip" in br.tags),
        bark_key=bark_key, bark_uv=UV, lod_share=(0.5, 0.2))


def trunk(**kw):
    base = dict(flare=0.45, flare_height=0.4, lobes=(5, 0.12), taper=0.15, broken=True, wander=0.1,
                sides=(14, 10, 6), seg=(0.4, 0.8, 1.6), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    base.setdefault("tip_radius", base["radius"] * 0.7)
    return tr.Trunk(**base)


def sapling():
    """The planted seed's seedling (DementiveNatureTreeJoshuaTreeSeed in game): a stub of a stem about 0.2 m tall
    topped with a small rosette."""
    return joshua([trunk(height=0.22, radius=0.03, flare=0.2, flare_height=0.05, lobes=(0, 0.0), wander=0.01,
                         sink=0.06, step=0.04, sides=(8, 6, 4), seg=(0.08, 0.16, 0.4),
                         rings=((0.0,), (0.0,), (0.0,)))], [], budget=700)


VARIANTS = [
    # Old and much-branched, about 8 m and as wide: five forks deep, a crown of 20-40 heads
    ("JoshuaTree01", 11, lambda: joshua([trunk(height=3.2, radius=0.3, lean=(0.2, 0.1), bow=0.2)],
                                        [arms((2, 3), (0.9, 1.5), 55.0, sides=(10, 7, 5)),
                                         arms((1, 3), (0.7, 1.2), 50.0),
                                         arms((2, 3), (0.55, 0.95), 46.0, sides=(8, 6, 4)),
                                         arms((1, 3), (0.45, 0.8), 42.0, sides=(8, 6, 4)),
                                         arms((1, 2), (0.35, 0.6), 40.0, sides=(7, 5, 4))], budget=12000)),
    # Younger, about 5-6 m: a few arms forked once or twice more
    ("JoshuaTree02", 23, lambda: joshua([trunk(height=2.6, radius=0.22, lean=(-0.3, 0.2), bow=0.3)],
                                        [arms((2, 4), (0.9, 1.5), 52.0), arms((1, 3), (0.6, 1.1), 46.0),
                                         arms((0, 2), (0.5, 0.8), 42.0, sides=(8, 6, 4))], budget=8000)),
    # An unbranched column about 4 m, shaggy to the ground
    ("JoshuaTree03", 37, lambda: joshua([trunk(height=3.8, radius=0.14, lean=(0.4, 0.2), bow=0.3, wander=0.15,
                                               sides=(12, 8, 6))], [], budget=2500)),
    # Young, about 2 m
    ("JoshuaTree04", 41, lambda: joshua([trunk(height=1.7, radius=0.1, lean=(0.1, -0.15), bow=0.2, wander=0.08,
                                               sides=(10, 8, 6), seg=(0.3, 0.6, 1.2))], [], budget=1800)),
    # The seedling a planted seed shows before it grows into JoshuaTree04
    ("JoshuaTreeSapling", 53, sapling),
]
ROSETTE_SIZE = {"JoshuaTreeSapling": 0.55, "JoshuaTree04": 1.15}


# ---------------------------------------------------------------- the seed's icon

def pod(m, centre, axis, length, radius, rings=14, segs=18):
    """A Joshua tree's fruit: a fat egg-shaped capsule with three shallow lobes, `length` along `axis`."""
    d = Vector(axis).normalized()
    _, u, v = tr.basis(d)
    rows = []
    for j in range(rings + 1):
        t = j / rings
        prof = math.sin(math.pi * t) ** 0.7 * (1.0 + 0.1 * math.sin(math.pi * t * 2.0 - 0.5))
        row = []
        for k in range(segs):
            a = k / segs * TAU
            rr = radius * prof * (1.0 + 0.16 * math.cos(3.0 * a))
            p = centre + d * ((t - 0.5) * length) + (u * math.cos(a) + v * math.sin(a)) * rr
            row.append(m.v(p, leaf=(math.cos(3.0 * a), t, 0.5)))
        rows.append(row)
    uv = ((0, 0),) * 4
    for a, b in zip(rows, rows[1:]):
        for k in range(segs):
            k1 = (k + 1) % segs
            m.quad(a[k], a[k1], b[k1], b[k], uv, "pod")


def seed(m, centre, normal, radius, thick=0.0015, segs=14):
    """A flat black seed: a thin disc, a little lopsided."""
    nrm = Vector(normal).normalized()
    _, u, v = tr.basis(nrm)
    ring = [m.v(centre + (u * math.cos(a) * (1.0 + 0.12 * math.cos(a + 1.0)) + v * math.sin(a)) * radius,
                leaf=(0.0, 0.0, 0.0)) for a in (k / segs * TAU for k in range(segs))]
    top, bottom = m.v(centre + nrm * thick), m.v(centre - nrm * thick)
    uv = ((0, 0),) * 3
    for k in range(segs):
        k1 = (k + 1) % segs
        m.tri(ring[k], ring[k1], top, uv, "seed")
        m.tri(ring[k1], ring[k], bottom, uv, "seed")


def make_icon():
    """JoshuaTreeSeed_Icon.png (160 x 160, in Trees/JoshuaTree; gen_nature.py copies it into the mod's item icons),
    drawn like vanilla's seeds: a Joshua tree's fruit with a few of its flat black seeds before it, on a leaf, under
    zkit's icon lights."""
    import bpy
    tr.reset()
    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    mats = leaf_materials(shade=0.0)
    mat, g = tr.tk.new_material("JoshuaPodSrc")
    lobe, along, _ = g.separate(g.node("ShaderNodeAttribute", attribute_name="leaf").outputs["Vector"])
    # Olive going brown as it dries, darker down the grooves between its lobes, a rough skin
    col = g.mix(g.ramp(g.noise(60.0, detail=3.0), 0.3, 0.7), (0.12, 0.13, 0.04), (0.22, 0.2, 0.07))
    col = g.mix(g.ramp(g.noise(9.0, detail=2.0), 0.45, 0.7), col, (0.2, 0.13, 0.06))
    col = g.mix(g.math("MULTIPLY", g.ramp(lobe, 0.2, -0.9), 0.6), col, (0.06, 0.05, 0.02))
    col = g.mix(g.ramp(along, 0.06, 0.0), col, (0.1, 0.07, 0.03))
    tr.tk.finish(mat, g, col, 0.0, 0.6, g.bump(g.noise(300.0, detail=3.0), 0.3, 0.0004))
    mats["pod"] = tr.signals(mat, col, 0.6)
    mat, g = tr.tk.new_material("JoshuaSeedSrc")
    tr.tk.finish(mat, g, (0.018, 0.017, 0.016), 0.0, 0.35)
    mats["seed"] = tr.signals(mat, (0.018, 0.017, 0.016), 0.35)
    rnd = random.Random(9)
    m = tr.Mesh()
    # In a card's frame (x right, y up, facing +z): two leaves crossing behind, the fruit lying across them, three
    # flat seeds lying in front, seen at a slant (their faces up, +y here)
    leaf(m, rnd, Vector((0.075, -0.06, -0.01)), Vector((-1.0, 0.7, 0.0)), Vector((0.0, 0.3, 1.0)), 0.2)
    leaf(m, rnd, Vector((-0.08, -0.05, -0.015)), Vector((1.0, 0.9, 0.0)), Vector((0.0, 0.3, 1.0)), 0.18)
    pod(m, Vector((0.0, 0.012, 0.01)), Vector((1.0, 0.3, 0.0)), 0.08, 0.026)
    for x, y, tilt in ((-0.032, -0.042, 0.25), (0.002, -0.05, -0.2), (0.034, -0.038, 0.1)):
        seed(m, Vector((x, y, 0.045)), Vector((tilt, 1.0, 0.55)), 0.0095, thick=0.001)
    obj = m.build("JoshuaTreeSeedIcon", mats)
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.scale = (6.0, 6.0, 6.0)
    obj.location = (0.0, 0.0, 0.3)
    cam = tr.tk.camera("IconCam", (0.0, -4.0, 0.3), (0.0, 0.0, 0.3), ortho=0.72)
    tr.tk.icon(cam, os.path.join(FOLDER, "JoshuaTreeSeed_Icon.png"), hide=())
    print("[joshua_tree] icon written")


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
    mats = {"bark": tr.textured("JoshuaTreeBark", paths("JoshuaTreeBark")),
            "thatch": tr.textured("JoshuaTreeBarkThatch", paths("JoshuaTreeBarkThatch")),
            "leaves": tr.textured("JoshuaTreeLeaves", paths("JoshuaTreeLeaves"), cutout=True, translucent=0.15)}
    figure = tr.stage()
    built = []
    for name, seed_, make in VARIANTS:
        tree = tr.grow(make(), seed_, name)
        tag_tips(tree)
        tree.cards = rosettes(tree, random.Random(seed_ + 7), size=ROSETTE_SIZE.get(name, 1.0))
        lods = tr.build_lods(tree, mats)
        lods.append(tr.impostor(name, lods[0], FOLDER))
        tr.export_tree(name, lods, FOLDER)
        size = tr.measure(tree, lods[0])
        tr.write_sizes(os.path.join(TREES, "trees.txt"), name, size)
        tr.write_trunks(os.path.join(TREES, "trunks.txt"), name, tree)
        print("[joshua_tree] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f, %d tips" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1], sum("tip" in b.tags for b in tree.branches)))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("joshuatree01", lods[0], PREVIEWS, figure)
    tr.preview_lods("joshuatree01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("joshua_tree", [b[2][0] for b in built], PREVIEWS, figure)
    if STEPS == "all":
        make_icon()
    print("[joshua_tree] done")


main()
