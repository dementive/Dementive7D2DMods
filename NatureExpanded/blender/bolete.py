"""Bolete (forest floor and edges, food): a cluster of five fat porcini (king boletes), from a button just pushing up
through the needles to a big one with a 14 cm cap. Chestnut-brown bun caps, paler toward a thin whitish margin; a
spongy pale yellow pore layer underneath; thick club-shaped pale stems with a fine raised white net over their upper
part. Fallen leaves, pine needles and a little moss round them. No grass.

    blender -b --factory-startup --python bolete.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Bolete", "bolete"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(21)
G = nk.GROUND

cap_mat = kf.bolete_cap("PorciniCap", (0.085, 0.032, 0.011), (0.2, 0.098, 0.038), (0.46, 0.37, 0.25))
pore_mat = kf.pores("PorciniPores", (0.66, 0.6, 0.26), (0.45, 0.4, 0.14))
stem_mat = kf.reticulate("PorciniStem", (0.5, 0.4, 0.26), (0.76, 0.68, 0.52), (0.86, 0.83, 0.74), scale=230.0,
                         stretch=0.5, soil=(0.05, 0.035, 0.022))
moss_mat = kf.moss_material("Moss")
brown = kf.litter_material("LeafBrown", (0.1, 0.055, 0.026), (0.19, 0.1, 0.045))
gold = kf.litter_material("LeafGold", (0.3, 0.18, 0.05), (0.4, 0.25, 0.07))
needle = kf.litter_material("Needles", (0.2, 0.11, 0.045), (0.3, 0.17, 0.07), spots=0.0)

# A bun-shaped cap (r, h) in cap radii from the apex out to the rounded rim
BUN = [(0.0, 0.6), (0.4, 0.56), (0.7, 0.45), (0.9, 0.28), (0.99, 0.1), (0.96, 0.0)]

pieces = []
keep = []


def porcini(i, x, y, R, L, sr, lean):
    ax = Vector((lean[0], lean[1], 1.0)).normalized()
    base = Vector((x, y, G))
    B = sr * 1.35
    keep.append((x, y, B + 0.012))
    seg = 16 if R > 0.05 else 14
    # A club of a stem, widest low down
    prof = [(0.0, -0.008), (B * 0.85, -0.006), (B, L * 0.18), (B * 0.97, L * 0.4), (sr * 1.08, L * 0.68),
            (sr * 0.95, L * 0.9), (sr * 0.92, L)]
    pieces.append(kf.revolve("Stem%d" % i, prof, base, ax, stem_mat, segments=10,
                             t=[max(0.0, h) / L for _, h in prof]))
    # The cap, and the pore layer bulging a little below its rim
    top = [(R * r, R * h) for r, h in BUN]
    h_in = -0.04 * R
    under = [(R * 0.95, -0.005 * R), (R * 0.75, -0.08 * R), (R * 0.45, -0.1 * R), (sr * 0.95, h_in)]
    origin = base + ax * (L - h_in)
    pieces.append(kf.revolve("Cap%d" % i, top, origin, ax, cap_mat, segments=seg, t=(0.0, 0.35, 0.62, 0.8, 0.9, 1.0),
                             away=origin - ax * R, phase=rnd.uniform(0.0, 1.0),
                             wobble=lambda k, a, p=rnd.uniform(0, 6.3): (1.0 + 0.035 * math.sin(3 * a + p), 0.0)))
    pieces.append(kf.revolve("Pores%d" % i, under, origin, ax, pore_mat, segments=seg, t=(0.5, 0.5, 0.5, 0.5),
                             away=origin + ax * (R * 3.0),
                             wobble=lambda k, a, p=rnd.uniform(0, 6.3): (1.0 + (0.03 * math.sin(3 * a + p) if k == 0 else 0.0), 0.0)))


# (x, y, cap radius, stem length, stem radius, lean)
for i, (x, y, R, L, sr, lean) in enumerate((
        (-0.08, 0.04, 0.07, 0.1, 0.024, (-0.05, 0.03)),
        (0.1, -0.06, 0.05, 0.085, 0.019, (0.06, -0.04)),
        (0.05, 0.13, 0.032, 0.06, 0.02, (0.03, 0.08)),
        (-0.17, -0.1, 0.042, 0.07, 0.017, (-0.08, -0.05)),
        (0.17, 0.1, 0.022, 0.035, 0.016, (0.05, 0.03)))):
    porcini(i, x, y, R, L, sr, lean)

pieces.append(kf.moss("Moss0", (-0.2, 0.12), 0.07, 0.02, moss_mat, seed=1))
pieces.append(kf.moss("Moss1", (0.2, -0.16), 0.055, 0.016, moss_mat, seed=2))
pieces += kf.litter("Leaf", 20, 0.4, [brown, gold, brown], seed=5, keep_out=keep, segments=4)
pieces.append(kf.needles("Needles", 60, 0.4, needle, seed=6, keep_out=keep))

kf.report(SCRIPT, pieces)
# The atlas goes mostly to the caps and stems, seen up close; the litter only needs its color
model = nk.export(NAME, pieces, MODELS, size=1024, density={"PorciniCap": 1.5, "PorciniStem": 1.2, "Leaf": 0.5,
                                                            "Needles": 0.5, "Moss": 0.9})
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.07, distance=0.95)
print("[%s] done" % SCRIPT)
