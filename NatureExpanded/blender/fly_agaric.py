"""FlyAgaric (forest floor and edges): an arc of a fairy ring, seven fly agaric toadstools 4 to 20 cm tall, from a
warty white button just out of the ground through domed young caps to big flat old ones. Bright red caps flecked
with white warts (thick on the young, sparse on the old), white gills underneath, white stems with a hanging skirt and
a bulbous base ringed with scales; moss cushions, fallen leaves and pine needles at their feet. No grass.

    blender -b --factory-startup --python fly_agaric.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "FlyAgaric", "fly_agaric"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(11)
G = nk.GROUND

# A deep scarlet going orange-red at the rim, with the white veil remnants painted on as ragged flecks (raised warts
# are modelled on top)
cap_mat = kf.agaric_cap("AgaricCap", (0.26, 0.007, 0.004), (0.5, 0.02, 0.008), (0.62, 0.075, 0.016))
wart_mat = kf.fungus("AgaricWart", (0.5, 0.45, 0.32), (0.72, 0.68, 0.54), rough=0.9, vary=0.45, scale=300.0,
                     bump=0.4, ramp=(0.0, 1.0))
gill_mat = kf.fungus("AgaricGill", (0.8, 0.78, 0.68), (0.86, 0.84, 0.76), rough=0.7, vary=0.12, scale=50.0)
stem_mat = kf.fungus("AgaricStem", (0.34, 0.28, 0.19), (0.86, 0.84, 0.77), rough=0.65, vary=0.12, scale=40.0,
                     ramp=(0.0, 0.28), streaks=0.35)
moss_mat = kf.moss_material("Moss")
brown = kf.litter_material("LeafBrown", (0.1, 0.055, 0.026), (0.19, 0.1, 0.045))
gold = kf.litter_material("LeafGold", (0.3, 0.18, 0.05), (0.4, 0.25, 0.07))
needle = kf.litter_material("Needles", (0.2, 0.11, 0.045), (0.3, 0.17, 0.07), spots=0.0)

# Cap shapes (r, h) in cap radii, apex out to the rim: domed young, flat old; stage blends them
DOME = [(0.0, 0.9), (0.4, 0.84), (0.7, 0.66), (0.9, 0.38), (1.0, 0.1), (0.93, -0.03)]
FLAT = [(0.0, 0.2), (0.4, 0.22), (0.7, 0.18), (0.9, 0.11), (1.0, 0.06), (1.0, 0.02)]

pieces = []
keep = []


def toadstool(i, x, y, R, L, stage, lean):
    ax = Vector((lean[0], lean[1], 1.0)).normalized()
    base = Vector((x, y, G))
    sr = R * (0.24 - 0.07 * stage)
    B = sr * 1.75
    keep.append((x, y, B + 0.01))
    seg = 14 if R > 0.045 else 12
    # Stem: a bulb with a ring of scales round its top, tapering up into the cap
    prof = [(0.0, -0.008), (B * 0.8, -0.005), (B, B * 0.45), (B * 0.9, B * 0.95), (B * 0.74, B * 1.12),
            (sr * 1.15, B * 1.6), (sr * 1.05, L * 0.5), (sr * 0.92, L)]
    pieces.append(kf.revolve("Stem%d" % i, prof, base, ax, stem_mat, segments=8,
                             t=[max(0.0, h) / L for _, h in prof]))
    # Cap
    top = [(R * (a[0] + (b[0] - a[0]) * stage), R * (a[1] + (b[1] - a[1]) * stage)) for a, b in zip(DOME, FLAT)]
    rim_r, rim_h = top[-1]
    h_in = top[0][1] - R * (0.35 - 0.23 * stage)
    mid = rim_h + (h_in - rim_h) * 0.65
    under = [(rim_r * 0.99, rim_h - 0.001), (R * 0.6, mid), (sr * 0.95, h_in)]
    origin = base + ax * (L - h_in)
    pieces.append(kf.revolve("Cap%d" % i, top, origin, ax, cap_mat, segments=seg, t=[r / R for r, _ in top],
                             away=origin - ax * R, phase=rnd.uniform(0.0, 1.0), polar=True))
    pieces.append(kf.revolve("Under%d" % i, under, origin, ax, gill_mat, segments=seg, t=(0.6, 0.6, 0.6),
                             away=origin + ax * (R * 3.0)))
    if stage >= 0.35:
        pieces.append(kf.gills("Gills%d" % i, origin, ax, under, gill_mat, 26 if R > 0.05 else 20, R * 0.11, seed=i))
    pieces.append(kf.warts("Warts%d" % i, origin, ax, top, wart_mat, int(15 - 7 * stage), R * (0.21 - 0.06 * stage),
                           seed=i, reach=0.82, height=0.32))
    # The skirt hanging from the stem below the cap (still hidden under the young ones)
    if stage >= 0.3:
        hs = L * (0.86 - 0.08 * stage)
        ph = [rnd.uniform(0.0, math.tau) for _ in range(3)]

        def wob(k, a):
            if k < 2:
                return 1.0, 0.0
            return 1.0 + 0.12 * math.sin(3 * a + ph[0]) + 0.06 * math.sin(7 * a + ph[1]), sr * 0.3 * math.sin(5 * a + ph[2])

        pieces.append(kf.revolve("Skirt%d" % i, [(sr * 0.97, hs + 0.002), (sr * 1.4, hs - sr * 0.5),
                                                 (sr * 1.55, hs - sr * 1.75)], base, ax, stem_mat, segments=10,
                                 t=(0.9, 0.9, 0.85), wobble=wob))


# An arc of a fairy ring: (angle on the arc, cap radius, stem length, stage 0 domed .. 1 flat)
RING = ((35, 0.03, 0.065, 0.1), (52, 0.072, 0.165, 0.95), (72, 0.052, 0.125, 0.55), (92, 0.038, 0.085, 0.2),
        (112, 0.064, 0.18, 0.85), (130, 0.046, 0.1, 0.45), (146, 0.02, 0.035, 0.0))
for i, (deg, R, L, stage) in enumerate(RING):
    a = math.radians(deg + rnd.uniform(-3.0, 3.0))
    rr = 0.45 + rnd.uniform(-0.025, 0.025)
    x, y = rr * math.cos(a), -0.3 + rr * math.sin(a)
    out = (math.cos(a), math.sin(a))
    lean = (out[0] * 0.06 + rnd.uniform(-0.07, 0.07), out[1] * 0.06 + rnd.uniform(-0.07, 0.07))
    toadstool(i, x, y, R, L, stage, lean)

# Moss cushions and litter at their feet
for k, (deg, r, h) in enumerate(((44, 0.06, 0.03), (86, 0.075, 0.035), (128, 0.055, 0.028))):
    a = math.radians(deg)
    pieces.append(kf.moss("Moss%d" % k, (0.45 * math.cos(a) * 0.95, -0.3 + 0.45 * math.sin(a) * 0.95), r, h,
                          moss_mat, seed=k))
pieces += kf.litter("Leaf", 15, 0.42, [brown, gold, brown], seed=3, keep_out=keep)
pieces.append(kf.needles("Needles", 50, 0.42, needle, seed=4, keep_out=keep))

kf.report(SCRIPT, pieces)
# The atlas goes mostly to the caps, seen up close; the litter only needs its color
model = nk.export(NAME, pieces, MODELS, size=1024, density={"AgaricCap": 1.5, "AgaricStem": 1.1, "Leaf": 0.5,
                                                            "Needles": 0.5, "Moss": 0.9})
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.08, distance=1.3)
print("[%s] done" % SCRIPT)
