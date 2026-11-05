"""Indian paintbrush (pine forest meadows): three little clumps of short upright stalks, 14 in all, 25 to 40 cm
tall, each tipped with a 6 to 8 cm brush of scarlet-orange bracts; narrow leaves up the stalks, meadow grass among
them.

A brush is two dozen leafy bracts spiraling round the top of the stalk, the lower ones longer and spreading, the
upper ones shorter and upright so the tip is rounded, most of them cut into three lobes at the end. The lower bracts
are green at their base going orange to scarlet at the tip, the upper ones orange-red all over, so the brush is red
at the top and greener toward its base, like a brush dipped in paint.

    blender -b --factory-startup --python paintbrush.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_meadow as km  # noqa: E402

NAME, SCRIPT = "Paintbrush", "paintbrush"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(41)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stalk_mat = nk.plant("PaintbrushStalk", (0.17, 0.2, 0.08), (0.22, 0.14, 0.1), rough=0.75)
leaf_mat = nk.plant("PaintbrushLeaf", (0.11, 0.18, 0.06), (0.18, 0.19, 0.1), rough=0.75, vary=0.35)
core_mat = nk.plant("PaintbrushCore", (0.35, 0.06, 0.02), (0.16, 0.12, 0.04), rough=0.7, sat=1.0, value=0.9)
low = km.ramp_petal("PaintbrushBractLow", [(0.0, (0.12, 0.2, 0.05)), (0.22, (0.45, 0.2, 0.03)),
                                          (0.45, (0.86, 0.15, 0.02)), (1.0, (0.86, 0.035, 0.02))], rough=0.65)
high = km.ramp_petal("PaintbrushBractHigh", [(0.0, (0.8, 0.14, 0.02)), (0.4, (0.87, 0.06, 0.02)),
                                             (1.0, (0.86, 0.03, 0.03))], rough=0.65)
grass = nk.grass()

groups = {"brushes": [], "stalks": [], "leaves": [], "grass": []}


def brush(name, top, axis, height, seed):
    r = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    base = top - ax * height
    parts = [km.stalk(name + "Core", [base, base + ax * (height * 0.55), top], 0.0, core_mat, sides=5,
                      radii=[0.004, 0.0065, 0.0])]
    n = r.randint(24, 28)
    turn = r.uniform(0, math.tau)
    for i in range(n):
        s = i / (n - 1)
        a = i * km.GOLDEN + turn + r.uniform(-0.3, 0.3)
        out = side * math.cos(a) + up * math.sin(a)
        at = base + ax * (height * 0.8 * s) + out * (0.004 * (1.0 - s))
        lift = (0.4 + 0.45 * s + r.uniform(-0.06, 0.06)) * math.pi * 0.5
        d = out * math.cos(lift) + ax * math.sin(lift)
        k = 0.036 * (1.0 - 0.45 * s) * r.uniform(0.9, 1.1)
        mat = low if s < 0.45 else high
        if i % 3 == 0 and s < 0.7:
            parts.append(km.sheet("%s%d" % (name, i), at, d, k, k * 0.5, mat, [(0.0, 0.35), (0.55, 1.0), (1.0, 0.0)],
                                  face=out, bend=-0.15, twist=r.uniform(-20, 20)))
        else:
            parts.append(km.sheet("%s%d" % (name, i), at, d, k, k * 0.6, mat, [(0.0, 0.35), (0.5, 1.0)], face=out,
                                  bend=-0.15, teeth=3, tooth=0.45, notch=0.35, twist=r.uniform(-20, 20)))
    return parts


clumps = nk.scatter(3, 0.2, seed=3, min_gap=0.2)
i = 0
for c, (cx, cy) in enumerate(clumps):
    for j in range(5 if c < 2 else 4):
        x, y = cx + rnd.uniform(-0.045, 0.045), cy + rnd.uniform(-0.045, 0.045)
        h = rnd.uniform(0.25, 0.4)
        bh = rnd.uniform(0.06, 0.08)
        out = Vector((x - cx, y - cy, 0.0)) + Vector((cx, cy, 0.0)) * 0.5
        out = out.normalized() if out.length > 1e-3 else Vector((1.0, 0.0, 0.0))
        lean = out * rnd.uniform(0.08, 0.25)
        foot = Vector((x, y, G))
        top = foot + lean * h + UP * h
        pts = km.curve(foot, top, bow=(lean.x * 0.06, lean.y * 0.06, -0.02), segments=3, wobble=0.006, rnd=rnd)
        groups["stalks"].append(km.stalk("Stalk%d" % i, pts, 0.0028, stalk_mat, sides=3, tip=0.0022))
        axis = ((pts[-1] - pts[-2]).normalized() + UP * 0.6).normalized()
        groups["brushes"] += brush("Brush%d_" % i, top, axis, bh, seed=i * 13 + 2)
        # Narrow leaves up the stalk below the brush, ascending
        for k in range(5):
            s = 0.15 + k * 0.13 + rnd.uniform(-0.03, 0.03)
            f = s * 3
            seg = min(2, int(f))
            p0 = pts[seg].lerp(pts[seg + 1], f - seg)
            tan = (pts[seg + 1] - pts[seg]).normalized()
            a = k * 2.4 + rnd.uniform(-0.4, 0.4)
            d = (Vector((math.cos(a), math.sin(a), 0.0)) * 0.55 + tan).normalized()
            groups["leaves"].append(km.sheet("Leaf%d_%d" % (i, k), p0, d, rnd.uniform(0.035, 0.055), 0.0075, leaf_mat,
                                             [(0.0, 0.5), (0.3, 1.0), (1.0, 0.0)], bend=0.2,
                                             twist=rnd.uniform(-30, 30)))
        i += 1

for k, (x, y) in enumerate(nk.scatter(4, 0.37, seed=14, min_gap=0.2)):
    groups["grass"] += nk.tuft("Grass%d_" % k, (x, y), 6, 0.26, grass, seed=k + 11)

km.report(SCRIPT, groups)
pieces = [p for parts in groups.values() for p in parts]
model = nk.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.22, distance=1.2)
print("[%s] done" % SCRIPT)
