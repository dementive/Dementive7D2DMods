"""Sagebrush (desert): big sagebrush, a twisted, silver-grey woody shrub 60 to 80 cm tall and about 1.1 m across.
Five gnarled trunks leaning out from one base, their bark grey-brown and shaggy, hanging in loose strips low down,
branching twice into fine twigs; every twig end and the upper branches carry dense, puffy tufts of small silver
wedge leaves, each with three little teeth at its tip, so the crown is a soft, uneven silver mass over a bare
woody inside.

    blender -b --factory-startup --python sagebrush.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "Sagebrush", "sagebrush"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(61)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))

bark_mat = kd.skin("SageBark", (0.23, 0.21, 0.18), (0.14, 0.13, 0.11), rough=0.9, vary=0.35, scale=6.0, streaks=0.85,
                   base_dark=0.75, bump=0.08)
shred_mat = nk.plant("SageShred", (0.2, 0.18, 0.14), (0.12, 0.1, 0.08), rough=0.9, vary=0.4, sat=0.7, value=0.95)
leaf_mat = nk.plant("SageLeaf", (0.36, 0.4, 0.33), (0.29, 0.33, 0.27), rough=0.85, vary=0.35, sat=0.5, value=1.05)

wood_b, shred_b, leaf_b = kd.Builder(), kd.Builder(), kd.Builder()
tufts = 0


def wedge(p, d, length, width, r):
    """A sagebrush leaf: a narrow wedge with three teeth at its tip (two triangles)."""
    _, sd, up = kd.frame(d, roll=r.uniform(0, 180))
    tip = p + d * length
    shoulder = p + d * (length * 0.82)
    a = leaf_b.v(p, 0.3)
    b = leaf_b.v(shoulder + sd * (width * 0.5), 0.9)
    c = leaf_b.v(tip, 1.0)
    e = leaf_b.v(shoulder - sd * (width * 0.5), 0.9)
    leaf_b.f(a, b, c, e)


def tuft(p, d, r, size=1.0):
    """A dense, puffy tuft of silver leaves round a twig end, reaching up and out."""
    global tufts
    tufts += 1
    for k in range(r.randint(12, 14)):
        o = Vector([r.gauss(0.0, 1.0) for _ in range(3)]).normalized()
        ld = (o + d * 0.5 + Z * 0.6).normalized()
        base = p + Vector([r.gauss(0.0, 0.02) for _ in range(3)]) * size
        wedge(base, ld, r.uniform(0.028, 0.045) * size, r.uniform(0.009, 0.014) * size, r)


def grow(start, d, length, radius, depth, r):
    """A gnarled branch and, recursively, its side branches; the ends and upper branches get tufts of leaves."""
    segs = (4, 3, 2)[depth]
    pts, radii = [start], [radius]
    cur, dd = Vector(start), Vector(d)
    gn = (0.4, 0.45, 0.4)[depth]
    for k in range(1, segs + 1):
        dd = (dd + Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.4, 0.6))) * gn + Z * 0.12).normalized()
        cur = cur + dd * (length / segs)
        pts.append(cur.copy())
        radii.append(radius * (1.0 - 0.55 * k / segs))
    kd.tube(wood_b, pts, radii, sides=(5, 4, 3)[depth], cap=depth >= 1, wobble=0.12 if depth == 0 else 0.0, rnd=r)

    def at(s):
        f = s * segs
        k = min(segs - 1, int(f))
        return pts[k].lerp(pts[k + 1], f - k), radii[k] + (radii[k + 1] - radii[k]) * (f - k),             (pts[k + 1] - pts[k]).normalized()

    if depth == 2:
        tuft(cur, dd, r, size=1.1)
        p, _, td = at(0.5)
        tuft(p, td, r, size=0.9)
        return
    if depth == 1:
        for s in (0.6, 0.85):
            p, _, td = at(s)
            tuft(p, td, r)
    n = (3, 2)[depth] + (1 if r.random() < 0.45 else 0)
    for c in range(n):
        s = r.uniform(0.45, 0.9) if c else 1.0
        p, rr, td = at(min(s, 0.999))
        side = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0.0))
        nd = (td * 1.0 + side * r.uniform(0.5, 1.0) + Z * r.uniform(0.05, 0.3)).normalized()
        grow(p, nd, length * r.uniform(0.6, 0.72), rr * 0.8, depth + 1, r)


for i in range(5):
    a = (i + rnd.uniform(-0.25, 0.25)) / 5 * math.tau
    out = Vector((math.cos(a), math.sin(a), 0.0))
    tilt = math.radians(rnd.uniform(24, 46))
    d = (out * math.sin(tilt) + Z * math.cos(tilt)).normalized()
    start = out * 0.02 + Vector((0, 0, G - 0.02))
    r = random.Random(100 + i)
    grow(start, d, rnd.uniform(0.3, 0.38), rnd.uniform(0.017, 0.022), 0, r)
    # Shaggy bark hanging off the lower trunk in loose strips
    for k in range(3):
        h = rnd.uniform(0.04, 0.16)
        p = start + d * h
        _, sd, up = kd.frame(d)
        b = rnd.uniform(0, math.tau)
        o = sd * math.cos(b) + up * math.sin(b)
        kd.sheet(shred_b, p + o * 0.016, (-d * 0.6 + o * 0.5).normalized(), rnd.uniform(0.05, 0.1),
                 rnd.uniform(0.008, 0.014), (1.0, 0.9, 0.7, 0.3), bend=-0.3, toward=o, twist=rnd.uniform(-60, 60))

# A gnarled root crown where the trunks meet the ground
kd.tube(wood_b, [(0, 0, G - 0.02), (0.0, 0.0, G + 0.04)], [0.05, 0.035], sides=7, wobble=0.25, rnd=rnd)

pieces = [wood_b.obj("Wood", bark_mat), shred_b.obj("Shreds", shred_mat), leaf_b.obj("Leaves", leaf_mat)]
print("[%s] %d tufts; wood %d, leaves %d triangles" % (SCRIPT, tufts, wood_b.tris(), leaf_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=1024)
kd.previews(SCRIPT, model, PREVIEWS, height=0.85, focus=G + 0.4, distance=2.0)
print("[%s] done" % SCRIPT)
