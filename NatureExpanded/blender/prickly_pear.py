"""Prickly pear (desert): a sprawling clump of Engelmann prickly pear 50 to 80 cm tall and about 1.3 m across. 18
flat obovate blue-green pads joined edge to edge, three or four deep (a few old ones sprawling low, the young ones
standing up on the rims of the old), each dotted with brown felt areoles in diagonal rows, pale spines bristling from
about half of them. Yellow cup flowers (two of them pink-orange) stand on the rims of the top pads on their green
pericarpels, with magenta fruits on the rims lower down.

    blender -b --factory-startup --python prickly_pear.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_desert as kd  # noqa: E402

NAME, SCRIPT = "PricklyPear", "prickly_pear"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(8)
G = nk.GROUND
Z = Vector((0.0, 0.0, 1.0))
LATTICE = 0.034

pad_mat = kd.skin("PearPad", (0.12, 0.23, 0.16), (0.17, 0.25, 0.11), rough=0.5, vary=0.3, scale=6.0,
                  dots=(0.1, (0.26, 0.18, 0.09), (0.1, 0.07, 0.035)))
spine_mat = nk.petal("PearSpine", (0.3, 0.2, 0.09), (0.85, 0.8, 0.6), mid=(0.75, 0.68, 0.45), sat=0.9, value=0.95)
yellow = nk.petal("PearFlower", (1.0, 0.78, 0.04), (1.0, 0.86, 0.06), mid=(1.0, 0.8, 0.05), sat=1.0, value=1.0)
salmon = nk.petal("PearFlowerPink", (1.0, 0.42, 0.2), (1.0, 0.5, 0.3), mid=(1.0, 0.56, 0.38), sat=1.0,
                  value=1.0)
stamen = nk.petal("PearStamen", (0.85, 0.7, 0.2), (0.95, 0.88, 0.45), sat=1.0)
stigma = nk.petal("PearStigma", (0.1, 0.35, 0.06), (0.2, 0.55, 0.12), sat=1.0)
peri_mat = kd.skin("PearPericarpel", (0.16, 0.27, 0.1), (0.2, 0.3, 0.1), rough=0.5)
fruit_mat = kd.skin("PearFruit", (0.55, 0.03, 0.17), (0.42, 0.02, 0.2), rough=0.4, vary=0.2, sat=1.0, value=0.95,
                    base_dark=0.85)

pads_b, spines_b, peri_b, fruit_b = (kd.Builder() for _ in range(4))
petals_b = {yellow: kd.Builder(), salmon: kd.Builder()}
stamen_b, stigma_b = kd.Builder(), kd.Builder()

# ---------------------------------------------------------------- the pads, grown outward from four old ones

pads = []        # dicts: frame, level, children, center point


def add_pad(base, direction, normal, level, b=pads_b, scale=1.0):
    length = rnd.uniform(0.2, 0.26) * scale * (1.0 - 0.05 * level)
    width = length * rnd.uniform(0.66, 0.76)
    fr, areoles = kd.pad(b, base, direction, normal, length, width, rnd.uniform(0.022, 0.03), k=10, rings=6,
                         widest=rnd.uniform(0.55, 0.65), warp=rnd.uniform(-0.04, 0.04), lattice=LATTICE,
                         offset=(rnd.random(), rnd.random()), seed=len(pads))
    p = dict(frame=fr, level=level, children=0, areoles=areoles, mid=fr[7](0.5), tip=fr[7](1.0))
    pads.append(p)
    return p


def fits(base, direction, length):
    d = Vector(direction).normalized()
    mid = Vector(base) + d * length * 0.5
    tip = Vector(base) + d * length
    if tip.z > G + 0.78 or min(tip.z, mid.z) < G + 0.04:
        return False
    if max(abs(tip.x), abs(tip.y)) > 0.66:
        return False
    return all((mid - q["mid"]).length > 0.13 for q in pads)


for i, (tilt, az) in enumerate(((18, 30), (34, 150), (62, 260), (70, 345))):
    a = math.radians(az + rnd.uniform(-15, 15))
    t = math.radians(tilt + rnd.uniform(-5, 5))
    d = Vector((math.cos(a) * math.sin(t), math.sin(a) * math.sin(t), math.cos(t)))
    base = Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, G - 0.02))
    side = Vector((-math.sin(a), math.cos(a), 0.0))
    nrm = kd.rotate(d.cross(side), d, rnd.uniform(-30, 30) + (90 if i % 2 else 0))
    add_pad(base, d, nrm, 0)

queue = list(pads)
while queue and len(pads) < 18:
    parent = queue.pop(0)
    want = {0: 3, 1: 2, 2: 2, 3: 0}[min(parent["level"], 3)]
    P, L, W, N, length, hw, ht, center = parent["frame"]
    for _ in range(want):
        for attempt in range(14):
            where = rnd.choice(("tip", "side", "side"))
            if where == "tip":
                s, sg = 0.97, 0.0
                rim = center(s)
                out = L
            else:
                s = rnd.uniform(0.55, 0.9)
                sg = rnd.choice((-1.0, 1.0))
                rim = center(s) + W * (sg * hw(s) * 0.92)
                out = (W * sg + L * (0.4 + (s - 0.55) * 2.0)).normalized()
            d = (out + Z * rnd.uniform(0.25, 0.9)).normalized()
            if parent["level"] == 0 and d.z < 0.35:
                d = (d + Z * 0.6).normalized()
            nrm = kd.rotate(N, d, rnd.uniform(-80, 80))
            nrm = nrm - d * nrm.dot(d)
            base = rim - d * 0.018
            ln = 0.24 * (1.0 - 0.05 * (parent["level"] + 1))
            if nrm.length > 1e-3 and fits(base, d, ln):
                child = add_pad(base, d, nrm, parent["level"] + 1)
                parent["children"] += 1
                child["anchor"] = (parent, s, sg)
                queue.append(child)
                break
        if len(pads) >= 18:
            break


# ---------------------------------------------------------------- spines from about half the areoles

for p in pads:
    L = p["frame"][1]
    for (pt, nrm, s, rim) in p["areoles"]:
        if rnd.random() > (0.55 if s > 0.4 else 0.35):
            continue
        for k in range(rnd.choice((1, 1, 2, 2, 3))):
            d = (nrm + (-L) * rnd.uniform(0.2, 0.9) + Vector([rnd.uniform(-0.45, 0.45) for _ in range(3)])).normalized()
            kd.sliver(spines_b, pt - nrm * 0.002, d, rnd.uniform(0.012, 0.03) * (1.3 if rim else 1.0), 0.0016)

# ---------------------------------------------------------------- flowers on the top pads' rims, fruit lower down


def rim_spot(p, s, sg):
    P, L, W, N, length, hw, ht, center = p["frame"]
    if sg == 0.0:
        return center(s), L
    return center(s) + W * (sg * hw(s) * 0.95), (W * sg + L * (0.3 + (s - 0.55) * 2.0)).normalized()


def taken(pt, spots, gap):
    return any((pt - q).length < gap for q in spots)


tops = sorted(pads, key=lambda q: -q["tip"].z)
spots = []
flowers = 0
for p in tops:
    if flowers >= 10:
        break
    for _ in range(rnd.choice((1, 2, 2))):
        s, sg = rnd.choice(((0.97, 0.0), (rnd.uniform(0.7, 0.9), 1.0), (rnd.uniform(0.7, 0.9), -1.0)))
        pt, out = rim_spot(p, s, sg)
        if taken(pt, spots, 0.07):
            continue
        spots.append(pt)
        ax = (out + Z * rnd.uniform(1.2, 1.8)).normalized()
        kd.blob(peri_b, pt + ax * 0.012, ax, 0.011, 0.03, k=6, rings=2)
        head = pt + ax * 0.026
        mat = salmon if flowers in (2, 6) else yellow
        kd.cup_flower(petals_b[mat], head, ax, 9, rnd.uniform(0.045, 0.052), 0.036, widths=(0.35, 0.85, 1.0, 0.8),
                      cup=rnd.uniform(0.14, 0.24), droop=-0.2, layers=2, seed=flowers, jitter=0.2)
        kd.dome(stamen_b, head + ax * 0.004, ax, 0.016, 0.011, k=8, ring2=True)
        kd.dome(stigma_b, head + ax * 0.015, ax, 0.005, 0.007, k=5)
        flowers += 1

fruits = 0
for p in sorted(pads, key=lambda q: q["tip"].z):
    if fruits >= 5:
        break
    if p["level"] == 0 and rnd.random() < 0.5:
        continue
    s, sg = rnd.choice(((0.97, 0.0), (rnd.uniform(0.65, 0.9), 1.0), (rnd.uniform(0.65, 0.9), -1.0)))
    pt, out = rim_spot(p, s, sg)
    if taken(pt, spots, 0.06):
        continue
    spots.append(pt)
    for k in range(rnd.choice((1, 2))):
        ax = (out + Z * rnd.uniform(0.5, 1.1) + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0))).normalized()
        q = pt + ax * 0.024 + (p["frame"][1] * (0.03 * k))
        kd.blob(fruit_b, q, ax, rnd.uniform(0.016, 0.019), rnd.uniform(0.045, 0.055), k=7, rings=3, wobble=0.06,
                rnd=rnd, top_dent=0.06)
        fruits += 1

pieces = [pads_b.obj("Pads", pad_mat, closed=True),
          spines_b.obj("Spines", spine_mat, smooth=False), peri_b.obj("Pericarpels", peri_mat, closed=True),
          fruit_b.obj("Fruit", fruit_mat, closed=True), stamen_b.obj("Stamens", stamen),
          stigma_b.obj("Stigmas", stigma)]
pieces += [b.obj("Petals%d" % i, m) for i, (m, b) in enumerate(petals_b.items())]
print("[%s] %d pads, %d flowers, %d fruit, %d spine triangles" % (SCRIPT, len(pads), flowers, fruits, spines_b.tris()))

model = nk.export(NAME, pieces, MODELS, size=1024)
kd.previews(SCRIPT, model, PREVIEWS, height=0.8, focus=G + 0.3, distance=2.0)
print("[%s] done" % SCRIPT)
