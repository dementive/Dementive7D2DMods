"""Fern (forest floor and edges): a lush clump of sword fern, eleven arching fronds 50 to 80 cm long springing from
one crown, each a midrib with twenty-odd pairs of lance leaflets (an ear at each leaflet's base) shrinking toward the
tip, the outer fronds arching right over, the inner ones younger and more upright, and two fiddleheads uncurling in
the middle. No grass: it's a forest-floor plant. Footprint up to 0.6 m out from the center.

    blender -b --factory-startup --python fern.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Fern", "fern"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(5)
G = nk.GROUND

# A deep, lush green: a touch more saturated than the meadow foliage, since the green is the point of a fern
leaf = nk.plant("FernLeaf", (0.07, 0.19, 0.03), (0.045, 0.13, 0.022), rough=0.5, vary=0.3, scale=9.0, sat=0.97,
                value=0.92)
young_leaf = nk.plant("FernYoung", (0.11, 0.26, 0.04), (0.08, 0.2, 0.03), rough=0.5, vary=0.25, scale=9.0,
                      sat=0.97, value=0.92)
stipe = nk.plant("FernStipe", (0.08, 0.07, 0.03), (0.1, 0.11, 0.035), rough=0.6, vary=0.3)
fiddle = nk.plant("FernFiddlehead", (0.15, 0.27, 0.05), (0.17, 0.11, 0.04), rough=0.75, vary=0.45, scale=60.0)
crown = kf.fungus("FernCrown", (0.04, 0.025, 0.012), (0.09, 0.055, 0.025), rough=0.95, vary=0.4, scale=80.0,
                  bump=0.2)

pieces = []
n = 12
for i in range(n):
    heading = i / n * math.tau + rnd.uniform(-0.2, 0.2)
    young = i % 4 == 1
    if young:
        # Younger fronds, fresher green, standing up in the middle
        length, rise, fall, power = rnd.uniform(0.5, 0.6), rnd.uniform(74.0, 80.0), rnd.uniform(-15.0, 5.0), 1.6
    else:
        # Older fronds arching out and down like a fountain, so they hide the stalks
        length, rise, fall, power = rnd.uniform(0.62, 0.74), rnd.uniform(56.0, 66.0), rnd.uniform(-58.0, -38.0), 1.25
    base = (math.cos(heading) * 0.03, math.sin(heading) * 0.03, G + 0.012)
    pieces += kf.frond("Frond%d" % i, base, heading, length, young_leaf if young else leaf, pairs=rnd.randint(19, 21),
                       rise=rise, fall=fall, power=power, pinna=0.09 + 0.06 * (length - 0.5), pinna_w=0.024,
                       stipe=0.12, roll=rnd.uniform(-18.0, 18.0), sway=rnd.uniform(-18.0, 18.0),
                       droop=rnd.uniform(0.15, 0.28), seed=i, stipe_material=stipe)

# Two fiddleheads uncurling in the middle, and the crown they come from
for k, (h, hd) in enumerate(((0.27, 0.9), (0.33, 3.6))):
    pieces.append(kf.fiddlehead("Fiddle%d" % k, (0.02 * math.cos(hd), 0.02 * math.sin(hd), G + 0.01), hd, h,
                                fiddle, coil=0.022 + 0.004 * k, radius=0.004))
pieces.append(kf.revolve("Crown", [(0.0, 0.04), (0.04, 0.028), (0.06, 0.0)], (0.0, 0.0, G - 0.005), (0, 0, 1),
                         crown, segments=8, t=(1.0, 0.6, 0.0)))

kf.report(SCRIPT, pieces)
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.25, distance=2.1)
print("[%s] done" % SCRIPT)
