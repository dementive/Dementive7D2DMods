"""Elderberry (forest floor and edges): an arching, many-stemmed bush about 1.4 m tall and 0.9 m across. Six
grey-brown canes speckled with pale lenticels splay out of the crown in a fountain, the middle ones nearly upright
and the outer ones arching over, each with a side shoot reaching out at mid height. Big pinnate leaves (five or seven
lance leaflets with pointed tips, softly folded along the midrib, curving toward the leaf tip) sit in crossed opposite
pairs up the tops of the canes and at the shoot tips. Five tips hold up broad, lacy elderflower heads 15 to 17 cm
across: five rays from one point branching again into flat pedicels, each ending in a little puff of three to five
five-petaled cream florets with pale yellow eyes, with air between the puffs and no plate under them. Two shoots have
gone to fruit and are bowed down by heavy bunches of glossy purple-black berries (a few still green or reddening)
hanging in twos to fours from red-purple stalks.

The tiny parts (florets, berries, rays, stalks, rachises) share small squares of the atlas (ks.export_stacked), so
each one bakes clean. The far LOD keeps the wood and every ray down to the secondaries, about half the leaves (their
rachis, tip leaflet and every other pair, grown), and puts one bigger floret or berry on a coarser pedicel where each
secondary's cluster was, so the white and the purple still read from 15 m and nothing floats (ks.report_floating
checks both meshes).

    blender -b --factory-startup --python elderberry.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_lod as kl  # noqa: E402
import kit_meadow as km  # noqa: E402
import kit_shrub as ks  # noqa: E402

NAME, SCRIPT = "Elderberry", "elderberry"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(5)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))

bark = ks.bark("ElderBark", (0.24, 0.21, 0.16), (0.15, 0.13, 0.1), rough=0.85, grain=35.0, dots=1.0,
               dot_color=(0.55, 0.52, 0.44))
shoot = ks.bark("ElderShoot", (0.21, 0.21, 0.13), (0.15, 0.15, 0.09), rough=0.75, grain=30.0, dots=0.7,
                dot_color=(0.48, 0.47, 0.36))
leaf = nk.plant("ElderLeaf", (0.075, 0.15, 0.04), (0.12, 0.2, 0.055), rough=0.6, vary=0.3)
rachis = nk.plant("ElderRachis", (0.17, 0.22, 0.08), (0.12, 0.16, 0.06), rough=0.6)
floret = km.ramp_petal("ElderFloret", [(0.0, (0.78, 0.63, 0.18)), (0.3, (0.88, 0.8, 0.46)),
                                       (0.5, (0.92, 0.89, 0.72)), (1.0, (0.95, 0.93, 0.8))],
                       rough=0.6, vary=0.08, value=0.95)
ray = nk.plant("ElderRay", (0.4, 0.46, 0.2), (0.3, 0.36, 0.15), rough=0.6, vary=0.12)
ripe = nk.plant("ElderBerry", (0.035, 0.008, 0.042), (0.018, 0.004, 0.024), rough=0.35, wax=True, sat=1.0,
                value=1.0)
unripe = nk.plant("ElderBerryGreen", (0.2, 0.3, 0.05), (0.15, 0.23, 0.04), rough=0.4, wax=True, sat=1.0, value=0.95)
reddening = nk.plant("ElderBerryRed", (0.26, 0.016, 0.05), (0.15, 0.01, 0.04), rough=0.35, wax=True, sat=1.0,
                     value=0.95)
stalk = nk.plant("ElderStalk", (0.17, 0.022, 0.075), (0.11, 0.016, 0.05), rough=0.55, sat=1.0, value=0.95)
STACKED = [m.name for m in (floret, ray, ripe, unripe, reddening, stalk, rachis)]

b = ks.Builder("Elder")

# ---------------------------------------------------------------- the skeleton
# Six canes from a broad crown in a fountain: each splays out of the ground and bends outward, the middle ones tall
# and nearly upright, the outer ones arching over at the top; each puts out one side shoot reaching out at mid
# height, so the leaves fill a rounded crown rather than a broom
canes = []
leans = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
rnd.shuffle(leans)
n = len(leans)
for i, lean in enumerate(leans):
    a = (i + rnd.uniform(-0.3, 0.3)) / n * math.tau
    o = Vector((math.cos(a), math.sin(a), 0.0))
    r0 = 0.03 + 0.07 * lean
    tip_r = 0.14 + 0.34 * lean + rnd.uniform(-0.03, 0.03)
    tip_h = 1.36 - 0.42 * lean + rnd.uniform(-0.05, 0.05)
    # A cubic curve: out of the crown at a slant, up, then over in an arc; the outer canes rise past their tip and
    # arch down to it
    p0 = o * r0 + Vector((0.0, 0.0, G))
    c1 = p0 + o * (0.3 * (tip_r - r0)) + Vector((0.0, 0.0, tip_h * 0.42))
    c2 = o * (r0 + (tip_r - r0) * (0.55 + 0.15 * lean)) + Vector((0.0, 0.0, G + tip_h * (1.02 + 0.16 * lean)))
    p3 = o * tip_r + Vector((0.0, 0.0, G + tip_h))
    side = Vector((-o.y, o.x, 0.0)) * rnd.uniform(-0.07, 0.07)
    pts = []
    for k in range(7):
        s = k / 6
        p = (p0 * (1 - s) ** 3 + c1 * (3 * s * (1 - s) ** 2) + c2 * (3 * s * s * (1 - s)) + p3 * s ** 3
             + side * math.sin(math.pi * s))
        if 0 < k < 6:
            p += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * 0.012
        pts.append(p)
    r_base = 0.011 - 0.002 * lean
    canes.append(ks.Branch(pts, [r_base + (0.004 - r_base) * (k / 6) ** 0.85 for k in range(7)], 0, 0.0, 1.0))
shoots = []
for c in canes:
    s = rnd.uniform(0.45, 0.62)
    p, tan, r, t = c.at(s)
    out = Vector((p.x, p.y, 0.0))
    out = out.normalized() if out.length > 0.02 else Vector((1.0, 0.0, 0.0))
    turn = math.radians(rnd.uniform(-50.0, 50.0))
    out = Vector((out.x * math.cos(turn) - out.y * math.sin(turn), out.x * math.sin(turn) + out.y * math.cos(turn), 0))
    ang = math.radians(rnd.uniform(40.0, 58.0))
    d = (tan * math.cos(ang) + out * math.sin(ang) + UP * 0.15).normalized()
    shoots.append(ks.grow(rnd, p, d, rnd.uniform(0.3, 0.4), r * 0.6, 0.003, segments=3, gravity=0.8, wander=0.06,
                          level=1, t0=t, t1=min(1.0, t + 0.4), arch=True))

# Heads: flowers held up on the highest tips, spread over the crown; bunches of berries on outer shoots lower down
used = []


def free(p, gap):
    return all((Vector((p.x, p.y, p.z)) - q).length > gap for q in used)


flower_tips = []
for br in sorted(canes + shoots, key=lambda br: br.tip.z + 0.5 * math.hypot(br.tip.x, br.tip.y), reverse=True):
    if len(flower_tips) == 5:
        break
    if free(br.tip, 0.24):
        flower_tips.append(br)
        used.append(br.tip.copy())
berry_tips = []
for br in sorted([s for s in shoots if s not in flower_tips],
                 key=lambda br: -math.hypot(br.tip.x, br.tip.y) + 0.5 * abs(br.tip.z - (G + 1.0))):
    if len(berry_tips) == 2:
        break
    if free(br.tip, 0.2):
        berry_tips.append(br)
        used.append(br.tip.copy())
# The fruiting shoots bow down under the weight: regrown from the same spot, the tip pulled over
for k, br in enumerate(berry_tips):
    d0 = (br.points[1] - br.points[0]).normalized()
    heavy = ks.grow(rnd, br.points[0], d0, br.length * 1.15, br.radii[0], 0.003, segments=3, gravity=3.4,
                    wander=0.03, level=br.level, t0=br.t0, t1=br.t1, arch=True)
    shoots[shoots.index(br)] = heavy
    berry_tips[k] = heavy
# Keep the crown inside its footprint by easing only the far-reaching parts in (fitting the whole bush would
# squeeze the arch out of it)
for br in canes + shoots:
    for p in br.points:
        r = math.hypot(p.x, p.y)
        if r > 0.28:
            k = (0.28 + 0.16 * math.tanh((r - 0.28) / 0.16)) / r
            p.x, p.y = p.x * k, p.y * k
    br.__init__(br.points, br.radii, br.level, br.t0, br.t1)

ks.wood(b, bark, canes, sides=(5,))
ks.wood(b, shoot, shoots, sides=(3,))

# ---------------------------------------------------------------- leaves
leaves = 0


# Leaflets in the crown get the smoother outline; the ones down inside, seen less, a cheaper one
SMOOTH = ((0.1, 0.55), (0.3, 0.96), (0.55, 0.9), (0.8, 0.5))
PLAIN = ((0.12, 0.6), (0.36, 1.0), (0.66, 0.74))


def elder_leaf(p, d, size=1.0, rows=SMOOTH):
    global leaves
    seven = rnd.random() < 0.2
    L = rnd.uniform(0.27, 0.33) * size
    ks.pinnate_leaf(b, leaf, rachis, p, d, L, 7 if seven else 5, L * (0.38 if seven else 0.44), L * 0.16, rnd,
                    normal=UP, bend=rnd.uniform(0.2, 0.35), petiole=rnd.uniform(0.15, 0.2), droop=0.1, fold=0.32,
                    leaflet_bend=0.22, sweep=0.07, far=(0.55, 1.3), rows=rows)
    leaves += 1


def pair(br, s, phase, size=1.0, lift=0.15, forward=0.35, rows=SMOOTH):
    """An opposite pair of leaves at fraction s along a branch, turned `phase` about it."""
    p, tan, _, _ = br.at(s)
    side = tan.cross(UP)
    side = side.normalized() if side.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    other = tan.cross(side).normalized()
    side = (side * math.cos(phase) + other * math.sin(phase)).normalized()
    for sgn in (-1.0, 1.0):
        d = side * sgn + tan * forward + UP * lift
        d.z = max(d.z, -0.15)
        elder_leaf(p, d.normalized(), size, rows)


flowering = set(id(br) for br in flower_tips)
fruiting = set(id(br) for br in berry_tips)
for br in canes + shoots:
    phase = rnd.uniform(-0.5, 0.5)
    if br.level == 0:
        # One or two pairs up the top of the cane, crossed (each pair square to the last, as elder grows them)
        if rnd.random() < 0.5:
            pair(br, rnd.uniform(0.6, 0.66), phase, lift=0.2, rows=PLAIN)
        pair(br, rnd.uniform(0.8, 0.86), phase + math.pi * 0.5, lift=0.2, rows=PLAIN)
        if id(br) in flowering:
            continue
    elif id(br) in fruiting:
        # Back from the bunch, so it hangs clear of its leaves
        pair(br, 0.3, phase, rows=PLAIN)
        continue
    elif id(br) in flowering:
        continue
    # A young pair at the tip, which also hides the shoot's cut end
    pair(br, 0.97, phase + math.pi * 0.5, size=0.9, lift=0.3, forward=0.6, rows=PLAIN)

# ---------------------------------------------------------------- flower heads
florets = 0
head_tops = []
for br in flower_tips:
    t, td = br.tip, br.tip_dir
    side = td.cross(UP)
    side = side.normalized() if side.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    for sgn in (-1.0, 1.0):
        elder_leaf(t - td * 0.02, (side * sgn + td * 0.2 + UP * 0.12).normalized(), 0.95)
    top = t + (td + UP * 1.5).normalized() * rnd.uniform(0.035, 0.05)
    ks.tube(b, ray, [t, top], [0.0026, 0.0022], sides=3, cap=False, t0=0.0, t1=0.2)
    axis = (UP * 2.2 + Vector((td.x, td.y, 0.0)) * 0.6).normalized()
    radius = rnd.uniform(0.075, 0.084)
    prims = ks.cyme_layout(rnd, top, axis, radius, radius * 0.5, rnd.randint(18, 19), rays=5, dome=0.15,
                           rim=0.9, split=2.5)
    florets += ks.flower_cyme(b, floret, ray, prims, axis, rnd, floret_r=0.0052, per=(3, 5), ray_r=0.0019,
                              sec_w=0.0032, gap=0.12, reach=1.0, splay=(0.6, 0.95))
    head_tops.append(top + axis * radius * 0.55)

# ---------------------------------------------------------------- berry bunches
berries = 0
bunch_tops = []
for br in berry_tips:
    t, td = br.tip, br.tip_dir
    flat = Vector((td.x, td.y, 0.0))
    flat = flat.normalized() if flat.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    top = t + (td + DOWN * 0.6).normalized() * 0.025
    ks.tube(b, stalk, [t, top], [0.0028, 0.0024], sides=3, cap=False, t0=0.0, t1=0.2)
    axis = (DOWN + flat * 0.25).normalized()
    radius = rnd.uniform(0.044, 0.048)
    # Short rays that fan out at once and ends scattered through the bunch, so the berries make a heavy mass
    prims = ks.cyme_layout(rnd, top, axis, radius, radius * 0.85, 18, rays=5, dome=0.5, node=(0.1, 0.2),
                           node_h=(0.15, 0.25), depth=0.55, rim=0.88, split=2.5)
    berries += ks.berry_bunch(b, [(ripe, 0.8), (unripe, 0.11), (reddening, 0.09)], stalk, prims, axis, rnd,
                              berry_r=0.0038, ray_r=0.0018, sec_w=0.003, per=(2, 4), sides=5)
    bunch_tops.append(top + axis * radius * 0.6)

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] flower heads %d (%d florets), berry bunches %d (%d berries), leaves %d" %
      (SCRIPT, len(flower_tips), florets, len(berry_tips), berries, leaves))
model = ks.export_stacked(NAME, pieces, MODELS, size=1024, stacked=STACKED)
ks.report_floating(SCRIPT, NAME)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.75, distance=4.2)
kl.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.75, distance=4.2)

# Close looks: a flower head and a berry bunch at arm's length, the bush from a couple of steps, and the far LOD from
# the same spot and nearer, to check it for floating parts and hairlines
front = Vector((0.25, -1.0, 0.3)).normalized()
fh = min(head_tops, key=lambda p: p.y - 0.3 * p.z)
bh = min(bunch_tops, key=lambda p: p.y)


def outside(p, lift):
    """A direction from the bush's middle out through p (and up by `lift`), to look at p from outside the leaves."""
    o = Vector((p.x, p.y, 0.0))
    o = o.normalized() if o.length > 0.02 else Vector((0.0, -1.0, 0.0))
    return (o + Vector((0.0, 0.0, lift))).normalized()


shots = [("head", fh + outside(fh, 0.9) * 0.32, fh, 50),
         ("berries", bh + outside(bh, 0.1) * 0.3, bh, 50),
         ("near", Vector((0.0, 0.0, G + 0.85)) + front * 1.8, Vector((0.0, 0.0, G + 0.85)), 50)]
ks.closeups(SCRIPT, NAME, PREVIEWS, shots)
ks.closeups(SCRIPT, NAME, PREVIEWS, [("lodnear", shots[2][1], shots[2][2], 50),
                                     ("lodhead", fh + outside(fh, 0.9) * 0.6, fh, 50)],
            lod=True)
print("[%s] done" % SCRIPT)
