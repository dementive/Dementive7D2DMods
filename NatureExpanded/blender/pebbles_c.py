"""PebblesC (ground cover, stones): a trail of stones, as a rain wash or a footpath leaves them: about 20 stones
strung out in a curve nearly a meter long, the biggest at one end and sizes dwindling along it to gravel, a smear
of dirt dragged under the line, one pale quartz and a few rusty sandstones among the grey granite.

    blender -b --factory-startup --python pebbles_c.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "PebblesC", "pebbles_c"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(37)
G = nk.GROUND

grey = ks_.granite("PebGranite", tint_lo=(0.78, 0.8, 0.84), tint_hi=(1.12, 1.06, 1.0))
pink = ks_.granite("PebGranitePink", tint_lo=(0.95, 0.74, 0.66), tint_hi=(1.3, 1.0, 0.88))
sand = ks_.sandstone("PebSandstone")
quartz = ks_.quartz("PebQuartz")
soil = ks_.soil_material("PebSoil")

S = ks_.Set(NAME)


def trail(s):
    """The centerline: an S-curve from (-0.42, -0.12) to (0.42, 0.17)."""
    x = -0.34 + 0.68 * s
    y = -0.1 + 0.25 * s + 0.1 * math.sin(s * math.pi * 1.6)
    return x, y


# A smear of dirt dragged along the trail, in overlapping pads
for k in range(6):
    s = (k + 0.5) / 6
    x, y = trail(s)
    ks_.pad(S.gm(soil), (x, y), 0.095 - 0.045 * s, rnd, sides=16, rings=2, dome=0.007 - 0.003 * s, lobes=0.35)

n = 20
mats = [grey, sand, grey, pink, grey, sand, grey, quartz, grey, sand, pink, grey, grey, sand, grey, pink, sand, grey, grey, sand]
for i in range(n):
    s = (i + rnd.uniform(-0.25, 0.25)) / (n - 1)
    s = min(1.0, max(0.0, s))
    x, y = trail(s)
    # spread across the trail, wider at the big end
    side = rnd.gauss(0, 0.028) * (1.2 - 0.6 * s)
    ex, ey = trail(min(1.0, s + 0.02))
    d = Vector((ex - x, ey - y)).normalized() if (ex != x or ey != y) else Vector((1, 0))
    x, y = x - d.y * side, y + d.x * side
    r = (0.052 - 0.036 * s ** 0.8) * rnd.uniform(0.8, 1.2)
    ks_.pebble(S, mats[i % len(mats)], x, y, r, rnd, lod=2 if r > 0.02 else 1, elong=rnd.uniform(1.0, 1.5))
for i in range(10):
    s = rnd.uniform(0.0, 1.0)
    x, y = trail(s)
    x += rnd.gauss(0, 0.06)
    y += rnd.gauss(0, 0.06)
    ks_.pebble(S, rnd.choice((grey, sand, pink)), x, y, rnd.uniform(0.007, 0.013), rnd, lod=1, sub=1, chip=0.0)

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024,
                   density={"PebGranite": 1.0, "PebSandstone": 1.0, "PebQuartz": 1.0, "PebSoil": 0.6})
ks_.preview(SCRIPT, model, PREVIEWS, kind="grass", height=0.07)
print("[%s] done" % SCRIPT)
