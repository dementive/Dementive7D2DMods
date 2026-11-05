"""Foxglove (forest floor and edges): four tall spikes 0.9 to 1.35 m from one big rosette of soft, broad, wrinkled
grey-green leaves. Up each spike, mostly on its outer side, hang 13 to 20 tubular bells, longest at the bottom: closed
at the stalk, widening to a slanted mouth whose lower lip runs out spotted dark purple ringed with white. Green buds
crowd the tip. Three spikes are pink-purple, one white. No grass.

The bells are our own (a closed tube with a lipped mouth and a spotted throat sheet), not nk.spike's cups, which
read as little open flowers rather than foxglove bells.

    blender -b --factory-startup --python foxglove.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Foxglove", "foxglove"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(61)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

leaf_mat = nk.plant("FoxgloveLeaf", (0.08, 0.13, 0.05), (0.12, 0.17, 0.08), rough=0.8, vary=0.25)
stem_mat = nk.plant("FoxgloveStem", (0.12, 0.16, 0.06), (0.2, 0.13, 0.1), rough=0.7)
pink = nk.petal("FoxgloveBell", (0.66, 0.26, 0.52), (0.52, 0.06, 0.32), sat=1.0, value=0.95)
white = nk.petal("FoxgloveWhite", (0.8, 0.84, 0.74), (0.92, 0.9, 0.88), sat=1.0, value=0.97)
pink_throat = kf.spotted("FoxgloveThroat", (0.86, 0.68, 0.8), (0.2, 0.02, 0.12), (0.95, 0.92, 0.94),
                         tip=(0.6, 0.18, 0.44))
white_throat = kf.spotted("FoxgloveWhiteThroat", (0.9, 0.88, 0.86), (0.3, 0.06, 0.2), (0.96, 0.95, 0.95),
                          tip=(0.9, 0.88, 0.86))
pink_bud = nk.plant("FoxgloveBud", (0.14, 0.2, 0.07), (0.35, 0.12, 0.25), rough=0.6, vary=0.4)
white_bud = nk.plant("FoxgloveBudWhite", (0.18, 0.24, 0.1), (0.4, 0.42, 0.3), rough=0.6, vary=0.4)

pieces = []


def bell(name, attach, axis, L, m, mat, throat):
    """A tubular foxglove bell hanging from `attach` along `axis`: closed at the stalk, widening to a slanted mouth
    with a longer lower lip, a spotted throat sheet running along its floor and out over the lip."""
    ax, s, u = kf.basis(axis)

    def wob(i, a):
        if i == 3:
            low = -math.sin(a)
            return 1.0 + 0.12 * max(0.0, low), L * 0.14 * low
        return 1.0, 0.0

    parts = [kf.revolve(name, [(0.0, 0.0), (0.55 * m, 0.12 * L), (0.85 * m, 0.5 * L), (m, L)], attach, ax, mat,
                        segments=6, t=(0.0, 0.25, 0.6, 1.0), wobble=wob, phase=math.pi / 6)]
    d = (ax * math.cos(0.26) - u * math.sin(0.26)).normalized()
    parts.append(kf.leaf(name + "Throat", attach + ax * (0.4 * L) - u * (0.6 * m), d, 0.8 * L, 1.15 * m, throat,
                         "elliptic", segments=3, bend=0.25, fold=0.35, cols=3))
    return parts


def spike(i, base, height, opens, buds, mat, throat, bud_mat, seed):
    r = random.Random(seed)
    lean = Vector((base.x, base.y, 0.0)).normalized() if base.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    face = math.atan2(lean.y, lean.x)
    pts = [base, base + lean * height * 0.015 + Z * height * 0.35, base + lean * height * 0.045 + Z * height * 0.7,
           base + lean * height * 0.09 + Z * height]
    pieces.append(kf.taper_tube("Stalk%d" % i, pts, (0.0065, 0.0022), stem_mat, sides=5))

    def at(f):
        x = f * 3.0
        k = min(2, int(x))
        return pts[k].lerp(pts[k + 1], x - k)

    # A few leaves up the lower stalk, shrinking
    for j, f in enumerate((0.08, 0.18, 0.28)):
        a = face + r.uniform(-2.5, 2.5)
        d = Vector((math.cos(a), math.sin(a), 0.6))
        pieces.append(kf.leaf("StalkLeaf%d_%d" % (i, j), at(f), d, 0.13 - 0.03 * j, 0.035 - 0.007 * j, leaf_mat,
                              "lance", segments=3, bend=0.3, cols=2, seed=i * 10 + j))
    # Open bells, mostly on the outer side, the lower ones hanging further down
    f0, f1 = 0.42, 0.88
    for j in range(opens):
        k = j / (opens - 1)
        az = face + r.uniform(-1.35, 1.35)
        out = Vector((math.cos(az), math.sin(az), 0.0))
        droop = math.radians(50.0 - 20.0 * k + r.uniform(-8.0, 8.0))
        axis = out * math.cos(droop) - Z * math.sin(droop)
        L = (0.058 - 0.016 * k) * r.uniform(0.92, 1.06)
        m = (0.019 - 0.005 * k) * r.uniform(0.92, 1.06)
        pieces.extend(bell("Bell%d_%d" % (i, j), at(f0 + (f1 - f0) * k) + out * 0.005, axis, L, m, mat, throat))
    # Buds crowding the tip, pointing up and out
    for j in range(buds):
        k = j / max(1, buds - 1)
        az = face + r.uniform(-2.0, 2.0)
        out = Vector((math.cos(az), math.sin(az), 0.0))
        up = math.radians(-20.0 + 70.0 * k)
        axis = out * math.cos(up) + Z * math.sin(up)
        ln = 0.022 - 0.013 * k
        rr = ln * 0.36
        pieces.append(kf.revolve("Bud%d_%d" % (i, j), [(0.0, 0.0), (0.5 * rr, 0.2 * ln), (rr, 0.6 * ln), (0.0, ln)],
                                 at(f1 + (0.985 - f1) * (j + 0.5) / buds) + out * 0.003, axis, bud_mat, segments=5))


# (base x, y, height, open bells, buds, white?)
for i, (x, y, h, opens, buds, is_white) in enumerate(((0.025, 0.03, 1.35, 20, 5, False),
                                                       (-0.05, -0.015, 1.15, 17, 5, False),
                                                       (0.055, -0.05, 1.02, 15, 4, True),
                                                       (-0.03, 0.07, 0.92, 13, 4, False))):
    spike(i, Vector((x, y, G)), h, opens, buds, white if is_white else pink, white_throat if is_white else pink_throat,
          white_bud if is_white else pink_bud, seed=i)

# The rosette: big soft wrinkled leaves lying out round the base
for j in range(14):
    a = j / 14 * math.tau + rnd.uniform(-0.18, 0.18)
    e = math.radians(rnd.uniform(22.0, 40.0))
    d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    L = rnd.uniform(0.25, 0.34)
    pieces.append(kf.leaf("Rosette%d" % j, (math.cos(a) * 0.02, math.sin(a) * 0.02, G + 0.01), d, L, L * 0.34,
                          leaf_mat, "elliptic", segments=7, bend=0.55, fold=0.15, wave=0.08, waves=3.0, seed=j))

kf.report(SCRIPT, pieces)
model = nk.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.65, distance=2.6)
print("[%s] done" % SCRIPT)
