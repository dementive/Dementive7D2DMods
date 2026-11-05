"""Charred snags for the burnt forest, on treekit.py (birch.py is the worked example; TREES.md has the rules).

Pines killed by the fire and left standing: no needles left, the trunk snapped off somewhere up it, a few splinters
standing up from the break, the limbs burnt back to stubs and the odd dead branch with its twigs. The bark is burnt
to charcoal and checked into small blocks (alligator-cracked) with a dull silvery sheen; here and there plates of it
have fallen away and show the grey weathered wood underneath; every snapped end shows bare wood. Forms: a tall snag,
a short thick stump of one, one leaning half over, one split into two leaders. No seedling or seed of their own (as
vanilla's burnt pines, they drop a mountain pine seed).

    blender -b --factory-startup --python trees/charred_snag.py -- <unity trees folder> <preview folder> [step]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`. Steps:
`all`, `textures` (or `bark`, `bark-textures`: the bark only, there's no leaf atlas), `trees`. It writes
Trees/CharredSnag/ (bark textures, CharredSnag01..04 with their impostors), the CharredSnag lines of Trees/trees.txt and
trunks.txt, and the previews. Built at its size in game.
"""
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import treekit as tr  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
TREES, PREVIEWS = args[0], args[1]
STEPS = args[2] if len(args) > 2 else "all"
FOLDER = os.path.join(TREES, "CharredSnag")
os.makedirs(FOLDER, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)
TAU = math.tau

# ---------------------------------------------------------------- bark textures
#
# CharredSnagBark: 2048 x 4096, wrapping twice round a tube and tiling up it every 2 pi radii, drawn at its size on
# CharredSnag01's 30 cm trunk (about 22 px per cm). CharredSnagBarkTwig: 512 x 1024, burnt limbs under 3.5 cm radius,
# once round them. CharredSnagBarkWood: 512 x 1024, the bare wood of a snapped end or a splinter, its grain running up.

W, H, WRAPS = 2048, 4096, 2
K = TAU * H / (WRAPS * W)
R_DESIGN = 30.0
PX = WRAPS * W / (TAU * R_DESIGN)
RELIEF = PX / 13.0
TWIST = 0.15
# Mean albedo (sRGB): charcoal, nearly black (vanilla's burnt pines are about as dark). The colours below are set
# near it already: grading a texture made too dark by 3x turned the block tops light grey and scorch marks orange
BARK_MEAN = (34, 32, 30)
TWIG_R = 0.035
UV = {
    "bark": tr.BarkUV(k=K, wraps=WRAPS, twist=TWIST),
    "twig": tr.BarkUV(k=4.0 * math.pi),
    "wood": tr.BarkUV(k=4.0 * math.pi),
}


def bark_key(br, s, r, z):
    """Splinters are bare wood, and so is the last stretch of any snapped-off trunk or limb (about half its radius,
    and its flat end); thin limbs get the twig bark."""
    if "splinter" in br.tags:
        return "wood"
    if getattr(br.spec, "broken", False) and s > 1.0 - min(0.4, 0.6 * r / max(br.length, 1e-3)):
        return "wood"
    if r < TWIG_R and br.level > 0:
        return "twig"
    return "bark"


def char_bark(r, h=H, w=W, px=PX):
    """Burnt pine bark as (albedo sRGB, height, roughness, occlusion), tileable both ways, `px` pixels per cm: the old
    bark's long plates (about 10 cm across) between furrows, every plate burnt to charcoal and checked into small
    blocks 1 to 3 cm (alligator-cracked), each domed and a shade of its own, their tops a dull silvery black with a
    sheen, the cracks between them soot-black and deep; here and there a plate fallen away to show the grey weathered
    wood under it, grain running up and scorched brown round the edge; pale ash caught in the furrows."""
    cm = px
    area = (w / cm) * (h / cm)
    warp = ((tr.fbm(r, h, w, (6 * cm, 25 * cm), 3) - 0.5) * 1.2 * cm,
            (tr.fbm(r, h, w, (6 * cm, 25 * cm), 3) - 0.5) * 4.0 * cm)
    pedge, plate, _, _ = tr.cells(r, h, w, 12 * cm, 2.8, warp)
    n = plate.max() + 1
    region = tr.fbm(r, h, w, (25 * cm, 40 * cm), 3)
    gone = (r.random(n)[plate] + 0.35 * (region - 0.5)) < 0.06
    pshade = r.random(n)[plate]
    wobble = tr.fbm(r, h, w, (2 * cm, 5 * cm), 3)
    fw = (1.2 + 1.5 * wobble) * cm
    furrow = 1.0 - tr.smoothstep(0.0, fw, pedge)
    shoulder = tr.smoothstep(0.0, 1.4 * cm, pedge - fw * 0.5)

    small = ((tr.fbm(r, h, w, (1.5 * cm, 1.5 * cm), 3) - 0.5) * 0.8 * cm,
             (tr.fbm(r, h, w, (1.5 * cm, 1.5 * cm), 3) - 0.5) * 0.8 * cm)
    cedge, block, _, _ = tr.cells(r, h, w, 3.0 * cm, 1.15, small)
    m = block.max() + 1
    bshade, sheen, cw = r.random(m)[block], r.random(m)[block], r.random(m)[block]
    cwidth = (0.06 + 0.1 * cw) * cm
    check = 1.0 - tr.smoothstep(cwidth * 0.5, cwidth + 0.06 * cm, cedge)
    dome = tr.smoothstep(0.0, 0.7 * cm, cedge)
    # Finer checking across the blocks' tops, thinner and shallower
    medge, _, _, _ = tr.cells(r, h, w, 0.8 * cm, 1.0)
    micro = (1.0 - tr.smoothstep(0.0, max(1.0, 0.04 * cm), medge)) * tr.smoothstep(0.4, 0.6, tr.fbm(r, h, w, (3 * cm, 3 * cm), 3))
    grit = tr.fbm(r, h, w, (0.06 * cm, 0.06 * cm), 2)
    fine = tr.fbm(r, h, w, (0.3 * cm, 0.3 * cm), 3)
    mottle = tr.fbm(r, h, w, (5 * cm, 8 * cm), 4)

    # Charcoal: matte brown-black, the domed tops greyer and silvery where they catch a sheen
    char = tr.mix((0.07, 0.065, 0.062), (0.17, 0.162, 0.155), 0.3 * bshade + 0.25 * pshade + 0.25 * grit + 0.2 * fine)
    shine = dome * tr.smoothstep(0.6, 0.95, sheen) * (0.5 + 0.5 * grit)
    char = tr.mix(char, (0.22, 0.22, 0.225), shine * (0.2 + 0.2 * mottle))
    char = tr.mix(char, (0.05, 0.047, 0.045), micro * 0.6)
    char = tr.mix(char, (0.03, 0.028, 0.026), check)
    char = tr.mix(char, (0.022, 0.02, 0.019), tr.smoothstep(0.2, 0.7, furrow))
    ash = (tr.smoothstep(0.66, 0.82, tr.fbm(r, h, w, (0.8 * cm, 2.0 * cm), 4)) * tr.smoothstep(0.55, 0.9, furrow)
           * (0.6 + 0.4 * grit))
    char = tr.mix(char, (0.3, 0.295, 0.285), ash * 0.35)
    # Some plates only scorched (a dark brown under the soot)
    brown = tr.smoothstep(0.85, 0.96, pshade) * tr.smoothstep(0.55, 0.75, mottle)
    char = tr.mix(char, (0.17, 0.12, 0.09), brown * (1.0 - check) * 0.5)

    # Fallen plates: weathered grey wood, grain up it, cracks along the grain, scorched round the edge
    grain = tr.fbm(r, h, w, (0.12 * cm, 4.0 * cm), 4)
    wgrain = tr.fbm(r, h, w, (0.5 * cm, 9.0 * cm), 3)
    wood = tr.mix((0.17, 0.15, 0.13), (0.33, 0.3, 0.27), 0.5 * grain + 0.3 * wgrain + 0.2 * grit)
    splits = np.zeros((h, w))
    for _ in range(int(area * 0.01)):
        tr.stamp(splits, r.uniform(0, w), r.uniform(0, h),
                 tr.lens(max(1.5, r.uniform(0.06, 0.15) * cm), r.uniform(2.0, 8.0) * cm, ends=1.0))
    wood = tr.mix(wood, (0.08, 0.07, 0.06), splits * 0.8)
    inside = gone & (pedge > fw * 0.8)
    inner = tr.blur(inside.astype(np.float64), 0.25 * cm)
    edge_burn = np.clip(1.0 - tr.smoothstep(0.0, 1.2 * cm, pedge - fw), 0.0, 1.0)
    wood = tr.mix(wood, (0.2, 0.12, 0.07), edge_burn * 0.6)
    col = tr.mix(char, wood, inner)

    height = (2.4 * (1.0 - furrow) + 0.6 * shoulder + (0.8 * dome - 1.0 * check - 0.3 * micro + 0.25 * bshade)
              * (1.0 - inner)
              + 0.25 * fine + 0.2 * grit + 0.15 * mottle + 0.15 * ash
              + inner * (-0.6 + 0.35 * grain + 0.2 * wgrain - 0.5 * splits))
    rough = 0.92 - 0.2 * shine * (1.0 - inner) + 0.04 * (grit - 0.5)
    occ = tr.cavity(height, 4.0 * RELIEF, 0.3)
    col = col * (0.75 + 0.25 * occ)[..., None]
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), occ, inner


def twig_char(r, h=1024, w=512):
    """Burnt limbs' bark at 1 cm radius: charcoal checked into small blocks, grey wood where it's flaked away."""
    cm = w / TAU
    cedge, block, _, _ = tr.cells(r, h, w, 0.5 * cm, 1.3)
    m = block.max() + 1
    bshade, sheen = r.random(m)[block], r.random(m)[block]
    check = 1.0 - tr.smoothstep(0.5, 2.5, cedge)
    dome = tr.smoothstep(0.0, 0.25 * cm, cedge)
    grit = tr.fbm(r, h, w, (0.05 * cm, 0.05 * cm), 2)
    col = tr.mix((0.05, 0.047, 0.044), (0.12, 0.115, 0.11), 0.5 * bshade + 0.3 * grit + 0.2 * dome)
    shine = dome * tr.smoothstep(0.6, 0.95, sheen)
    col = tr.mix(col, (0.2, 0.2, 0.205), shine * 0.3)
    col = tr.mix(col, (0.02, 0.02, 0.02), check)
    patches = tr.fbm(r, h, w, (0.8 * cm, 2.5 * cm), 4)
    bare = tr.smoothstep(0.71, 0.74, patches)
    rim = tr.smoothstep(0.66, 0.71, patches) * (1.0 - bare)
    grain = tr.fbm(r, h, w, (0.08 * cm, 2 * cm), 3)
    col = tr.mix(col, tr.mix((0.18, 0.16, 0.14), (0.32, 0.29, 0.26), grain), bare)
    col = tr.mix(col, (0.16, 0.09, 0.05), rim * 0.5)
    height = (0.6 * dome - 0.8 * check) * (1.0 - bare) + 0.3 * grain * bare - 0.3 * bare + 0.2 * grit
    rough = 0.92 - 0.2 * shine * (1.0 - bare)
    return np.clip(col, 0.0, 1.0), height, np.clip(rough, 0.0, 1.0), tr.cavity(height, 3.0, 0.25)


def bare_wood(r, h=1024, w=512):
    """Bare weathered wood (a snapped end, a splinter) at 1 cm radius: silver-grey, its grain running up in fine
    lines and long cracks, charred black in streaks and toward the bottom (where the bark meets it)."""
    cm = w / TAU
    grain = tr.fbm(r, h, w, (0.05 * cm, 1.5 * cm), 4)
    rings = tr.fbm(r, h, w, (0.3 * cm, 6 * cm), 3)
    grit = tr.fbm(r, h, w, (0.05 * cm, 0.05 * cm), 2)
    col = tr.mix((0.19, 0.17, 0.15), (0.4, 0.37, 0.33), 0.5 * grain + 0.3 * rings + 0.2 * grit)
    splits = np.zeros((h, w))
    for _ in range(40):
        tr.stamp(splits, r.uniform(0, w), r.uniform(0, h),
                 tr.lens(max(1.5, r.uniform(0.05, 0.12) * cm), r.uniform(1.0, 5.0) * cm, ends=1.0))
    col = tr.mix(col, (0.07, 0.06, 0.05), splits * 0.85)
    burnt = tr.smoothstep(0.64, 0.69, tr.fbm(r, h, w, (0.35 * cm, 4 * cm), 4)) * (0.7 + 0.3 * grit)
    col = tr.mix(col, (0.05, 0.045, 0.04), burnt * 0.85)
    height = 0.5 * grain + 0.3 * rings + 0.2 * grit - 0.8 * splits
    return np.clip(col, 0.0, 1.0), height, 0.85 + 0.05 * grain, tr.cavity(height, 3.0, 0.25)


def make_bark():
    r = np.random.default_rng(23)

    def save(name, col, height, rough, occ, relief):
        p = paths(name)
        tr.write_png(p["albedo"], col)
        tr.write_png(p["normal"], tr.normal_map(tr.blur(height, 0.6), 0.9 * relief))
        zero = np.zeros_like(rough)
        tr.write_png(p["rmom"], np.dstack([rough, zero, occ, zero]))

    col, height, rough, occ, wood = char_bark(r)
    # The charcoal graded alone, so the bare wood keeps its own grey
    graded, k = tr.match_mean(col, BARK_MEAN, wood < 0.5)
    col = tr.mix(graded, col, wood)
    print("[charred_snag] charcoal graded by %s" % np.round(k, 2))
    # Furrows and deep checks: more relief in the normal map than smooth bark gets
    save("CharredSnagBark", col, height, rough, occ, RELIEF * 1.8)
    save("CharredSnagBarkTwig", *twig_char(r), 1.2)
    save("CharredSnagBarkWood", *bare_wood(r), 1.0)


def paths(prefix):
    return {k: os.path.join(FOLDER, "%s_%s.png" % (prefix, s)) for k, s in
            (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}


# ---------------------------------------------------------------- the snags

def snag(trunks, limbs=2.6, reach=1.0, splinters=(3, 6), twigs=1.2, budget=3200, span=(0.25, 0.98)):
    """A snag's TreeSpec: `trunks` (snapped off, so tr.Trunk(broken=True, tip_radius=...)), dead limbs burnt back to
    stubs, `limbs` of them per metre over `span` of the trunk, near horizontal low down and rising toward the break,
    the longest `reach` times 2 m, some carrying a few burnt twigs (`twigs` per metre); `splinters` thin spikes of
    wood standing up out of the break."""
    lv = tr.Level(per_meter=limbs, span=span, length=(0.12 * reach, 1.8 * reach), shape="conical", angle=78.0,
                  angle_tip=55.0, angle_vary=12.0, radius=0.28, radius_length=0.8, radius_max=0.07, tip_radius=0.008,
                  broken=True, step=0.15, gravitropism=0.05, droop=0.15, wander=0.25, floor=0.5, sides=(6, 5, 0),
                  seg=(0.5, 1.0, 9.0), min_length=0.1, min_len=(0.0, 0.3, 99.0))
    tw = tr.Level(per_meter=twigs, span=(0.15, 0.85), length=(0.15, 0.6), shape="tapered", angle=50.0,
                  angle_vary=15.0, radius=0.45, radius_length=0.6, radius_max=0.012, tip_radius=0.002, step=0.08,
                  gravitropism=0.2, wander=0.5, sides=(4, 3, 0), seg=(0.25, 0.6, 9.0), min_length=0.1,
                  min_len=(0.0, 99.0, 99.0))
    spl = tr.Level(count=splinters, span=(0.965, 0.995), length=(0.25, 1.1), angle=10.0, angle_vary=6.0,
                   radius=0.3, radius_length=0.6, radius_max=0.06, tip_radius=0.004, step=0.1, wander=0.15,
                   tags=("splinter",), sides=(4, 3, 0), seg=(0.3, 0.6, 9.0), min_length=0.15,
                   min_len=(0.0, 0.5, 99.0))
    return tr.TreeSpec(trunks=trunks, levels=[lv, tw], stubs=spl, budget=budget, bark_budget=budget,
                       bark_key=bark_key, bark_uv=UV)


def trunk(**kw):
    base = dict(flare=0.4, flare_height=0.5, lobes=(6, 0.14), taper=0.9, broken=True, wander=0.05,
                sides=(14, 9, 6), seg=(0.7, 1.4, 3.0), rings=((0.0, 0.15, 0.4, 0.8), (0.0, 0.5), (0.0,)))
    base.update(kw)
    return tr.Trunk(**base)


VARIANTS = [
    # A tall snag, about 14 m, snapped off near the top, burnt limb stubs all up it
    ("CharredSnag01", 7, lambda: snag([trunk(height=14.0, radius=0.3, tip_radius=0.11, lean=(0.3, -0.2), bow=0.1)])),
    # A short thick stump of one, about 5 m, broken off low, a few stubs
    ("CharredSnag02", 19, lambda: snag([trunk(height=5.0, radius=0.4, tip_radius=0.26, taper=0.7, lean=(0.15, 0.1),
                                              lobes=(7, 0.18), sides=(16, 10, 7), seg=(0.5, 1.0, 2.5))],
                                       limbs=1.6, reach=0.5, splinters=(4, 7), budget=2400, span=(0.3, 0.95))),
    # Leaning half over, about 11 m tall and its top 6 m out, propped where it fell against its neighbours
    ("CharredSnag03", 31, lambda: snag([trunk(height=10.0, radius=0.26, tip_radius=0.09, lean=(6.0, 1.2), bow=0.05,
                                              wander=0.05)], limbs=2.0, reach=0.8)),
    # Split low into two leaders, about 12 and 9 m, both snapped off
    ("CharredSnag04", 43, lambda: snag([trunk(height=12.0, radius=0.2, tip_radius=0.07, base=(0.11, 0.03),
                                              lean=(1.4, 0.3), bow=0.4, sides=(12, 8, 6)),
                                        trunk(height=9.0, radius=0.18, tip_radius=0.08, base=(-0.1, -0.04),
                                              lean=(-1.1, -0.5), bow=0.5, sides=(12, 8, 6))],
                                       limbs=2.0, reach=0.8, budget=3600)),
]


def main():
    tr.reset()
    if STEPS in ("all", "textures", "bark", "bark-textures"):
        make_bark()
        if STEPS != "all":
            return
    mats = {"bark": tr.textured("CharredSnagBark", paths("CharredSnagBark")),
            "twig": tr.textured("CharredSnagBarkTwig", paths("CharredSnagBarkTwig")),
            "wood": tr.textured("CharredSnagBarkWood", paths("CharredSnagBarkWood"))}
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
        print("[charred_snag] %s height %.2f trunk radius %.3f crown radius %.2f lean %.2f %.2f" % (
            name, size[0], size[1], size[2], size[3][0], size[3][1]))
        for o in lods:
            o.hide_render = True
        built.append((name, tree, lods, size))
    for name, tree, lods, size in built:
        tr.preview_tree(name.lower(), lods[0], PREVIEWS, size[0], figure)
    name, tree, lods, size = built[0]
    tr.preview_bark("charredsnag01", lods[0], PREVIEWS, figure)
    tr.preview_lods("charredsnag01", lods, PREVIEWS, figure, size[0], size[2] * 2.0)
    tr.preview_grove("charred_snag", [b[2][0] for b in built], PREVIEWS, figure)
    print("[charred_snag] done")


main()
