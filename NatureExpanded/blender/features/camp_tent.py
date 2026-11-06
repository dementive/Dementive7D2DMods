"""CampTent (forest, meadow, taiga edge): an abandoned camp years old. A dome tent that came down on one side, its canvas
faded to khaki, torn, mildewed, grass poking through; a snapped alloy pole; a cold fire ring of blackened stones with ash,
charcoal and weeds; a log and a stump to sit on; three rusted cans; a bundle of firewood tied with rotten cord; guy lines
and tent pegs lying in the grass; litter and tufts. 5 x 5 m footprint, nothing above 0.75 m. Solid: the stones, the two
seats, the lump of gear under the canvas and the firewood. The rest is walk-through.

    blender -b --factory-startup --python camp_tent.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campkit as ck  # noqa: E402
import campprops as cp  # noqa: E402
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ck.set_preview_dir(PREVIEWS)
ONLY = ck.only()

NAME = "CampTent"
TENT_AT = (-0.55, 0.5)
TENT_YAW = 25.0
RA, RB = 1.12, 0.92
FIRE = (1.05, -0.75)


# ---------------------------------------------------------------- the tent

def h1(a):
    return 0.62 * max(0.0, 1.0 - ((a + 0.25) / 1.25) ** 2) * (1.0 - ck.smoothstep(0.1, 0.8, a))


def h2(b):
    return 0.5 * max(0.0, 1.0 - (b / 0.98) ** 2) * (1.0 - 0.55 * ck.smoothstep(0.0, 0.85, b))


def pole2_a(b):
    return -0.4 + 0.25 * b


GEAR = [(0.55, -0.2, 0.42, 0.15), (0.15, 0.45, 0.3, 0.08)]   # lumps under the canvas: (a, b, radius, height)


def tent_z(a, b):
    rho = math.hypot(a / RA, b / RB)
    z1 = h1(a) - 0.95 * abs(b - 0.1 * a)
    z2 = h2(b) - 0.85 * abs(a - pole2_a(b))
    k = 14.0
    zs = math.log(math.exp(k * z1) + math.exp(k * z2) + 1.0) / k
    zs *= 1.0 - ck.smoothstep(0.74, 1.0, rho)
    for ga, gb, gr, gh in GEAR:
        zs += gh * math.exp(-((a - ga) ** 2 + (b - gb) ** 2) / (gr * gr)) * (1.0 - ck.smoothstep(0.7, 1.0, rho))
    # the sleeves of the poles show as ridges in the canvas
    zs += 0.02 * math.exp(-((b - 0.1 * a) / 0.035) ** 2) * ck.smoothstep(0.03, 0.16, h1(a)) * (1.0 - ck.smoothstep(0.8, 1.0, rho))
    zs += 0.02 * math.exp(-((a - pole2_a(b)) / 0.035) ** 2) * ck.smoothstep(0.03, 0.16, h2(b)) * (1.0 - ck.smoothstep(0.8, 1.0, rho))
    sup = ck.clamp(zs / 0.3)
    q = Vector((a * 5.0 + 3.1, b * 5.0 + 1.7, 0.4))
    w = 0.016 * mn.noise(q) + 0.008 * mn.noise(q * 2.7) + 0.003 * mn.noise(q * 7.3)
    w *= 0.4 + 0.9 * (1.0 - sup)
    ground = 0.007 + 0.006 * abs(mn.noise(q * 1.7))
    return max(zs + w, ground)


HOLES = [(-0.22, 0.04, 0.17, 0.15), (0.5, -0.1, 0.22, 0.15), (-0.55, -0.58, 0.1, 0.09), (0.85, 0.5, 0.28, 0.2),
         (0.1, 0.62, 0.09, 0.07), (-0.95, 0.2, 0.12, 0.08)]


def grid_ab(i, j, nu, nv):
    X, Y = 2.0 * i / nu - 1.0, 2.0 * j / nv - 1.0
    x = X * math.sqrt(max(0.0, 1.0 - Y * Y / 2.0))
    y = Y * math.sqrt(max(0.0, 1.0 - X * X / 2.0))
    return x * RA, y * RB


def build_tent(b, M, tent, nu=34, nv=34):
    P = ck.Place(at=(TENT_AT[0], TENT_AT[1], G), yaw=TENT_YAW)

    def fn(i, j):
        a, bb = grid_ab(i, j, nu, nv)
        edge = max(abs(2.0 * i / nu - 1.0), abs(2.0 * j / nv - 1.0))
        z = tent_z(a, bb)
        if edge > 0.93:
            q = Vector((a * 9.0, bb * 9.0, 1.3))
            a += 0.05 * mn.noise(q)
            bb += 0.05 * mn.noise(q + Vector((5.0, 2.0, 0.0)))
        return P(Vector((a, bb, z)))

    def skip(i, j, k):
        a, bb = grid_ab(i + 0.5, j + 0.5, nu, nv)
        for ha, hb, ra, rb in HOLES:
            q = Vector((a * 11.0, bb * 11.0, 0.7))
            d = ((a - ha) / ra) ** 2 + ((bb - hb) / rb) ** 2 + 0.5 * mn.noise(q)
            if d < 1.0:
                return True
        edge = max(abs(2.0 * (i + 0.5) / nu - 1.0), abs(2.0 * (j + 0.5) / nv - 1.0))
        if edge > 0.86:
            q = Vector((a * 3.6 + 4.0, bb * 3.6, 2.2))
            n = mn.noise(q) + 0.35 * mn.noise(q * 3.3)
            if n > 0.28 - 0.5 * (edge - 0.86):
                return True
        return False

    ck.cloth(b, tent, fn, nu, nv, skip=skip, thick=0.003)
    # poles under the cloth: the long one is snapped near a = 0.45, the cross one bent
    pts = []
    for s in range(0, 26):
        a = -1.0 + s * 0.058
        if a > 0.46:
            break
        pts.append(P(Vector((a, 0.1 * a, h1(a) - 0.012))))
    return P, pts


def poles(b, P, pole, rnd):
    pts = []
    for s in range(0, 40):
        a = -1.0 + s * 0.04
        if a > 0.46:
            break
        pts.append(P(Vector((a, 0.1 * a, max(0.012, h1(a) - 0.012)))))
    ck.tapered(b, pole, pts, 0.0085, 0.0085, sides=6, cap=False, jag=1.3, rnd=rnd)
    pts = []
    for s in range(0, 40):
        bb = -0.95 + s * 0.05
        if bb > 0.9:
            break
        pts.append(P(Vector((pole2_a(bb), bb, max(0.012, h2(bb) - 0.012)))))
    ck.wire(b, pole, pts, 0.0085, sides=6, cap=True)
    # the snapped half-piece lying on the ground near the right edge
    a0 = P(Vector((0.55, -0.45, 0.012)))
    a1 = P(Vector((1.0, -0.2, 0.011)))
    ck.wire(b, pole, [a0, a0.lerp(a1, 0.5) + Vector((0, 0, 0.004)), a1], 0.0085, sides=6, cap=True)


def guy_lines(b, P, rope, peg, rnd):
    for ang, reach in ((20, 1.5), (110, 1.35), (200, 1.45), (290, 1.55), (60, 1.2)):
        a = math.radians(ang)
        e0 = P(Vector((math.cos(a) * RA * 0.92, math.sin(a) * RB * 0.92, 0.012)))
        e1 = P(Vector((math.cos(a) * RA * reach + rnd.uniform(-0.1, 0.1), math.sin(a) * RB * reach * 1.1, 0.0))) if False else \
            P(Vector((math.cos(a) * RA * reach, math.sin(a) * RB * reach * 1.1, 0.0)))
        e1.z = G + 0.008
        if abs(e1.x) > 2.3 or abs(e1.y) > 2.3:
            continue
        pts = ck.catenary(e0, e1, 0.0, n=7)
        for q in pts:
            q.z = max(G + 0.007, q.z)
            q.z += 0.012 * rnd.random()
        ck.wire(b, rope, pts, 0.0055, sides=4, cap=True)
        # a rusted peg, bent over
        d = (e1 - e0).normalized()
        p0 = e1 + d * 0.0
        pp = [p0 + Vector((0, 0, 0.06)), p0 + Vector((0, 0, 0.0)), p0 - Vector((0, 0, 0.08))]
        ck.wire(b, peg, [Vector(pp[0]), Vector(pp[1]), Vector(pp[2])], 0.0045, sides=4, cap=True)


# ---------------------------------------------------------------- the camp

def build(name):
    nk.reset()
    rnd = random.Random(11)
    gm = ck.ground_mats()
    wood = ck.Wood("CampWood")
    tent = ck.fabric_mat("CampCanvas", (0.2, 0.185, 0.11), (0.085, 0.08, 0.048), fade=0.5, mildew=0.8, stains=0.95, seams=0.7,
                         slits=0.7, bleach=(0.21, 0.2, 0.15))
    pole = ck.alu_mat("CampPole", corrode=0.5, rust=0.12)
    rope = ck.rope_mat("CampRope", (0.17, 0.145, 0.1))
    peg = ck.rust_mat("CampPeg", rust=1.0)
    stone = ck.stone_mat("CampStone", sooty=(FIRE[0], FIRE[1], 0.43), moss=0.0, lichen=0.5, stain=1.4, tint=(0.8, 0.8, 0.8))
    skirt = ck.stone_mat("CampStoneSkirt", moss=0.0, lichen=0.0)
    ash = ks.ash("CampAsh")
    char_end = lk.end_grain("CampCharEnd", "burnt", 0.01)
    end_cut = lk.end_grain("CampEndCut", "bleached", 0.011)
    end_bark = lk.end_grain("CampEndSplit", "bleached", 0.014)
    under = lk.soil_mat("CampSkirtSoil", moss=0.0, rooty=0.0)
    dirt = ck.dirt_mat("CampDirt")
    dirt_ash = ck.dirt_mat("CampDirtAsh", ash=0.9)
    can_a = ck.rust_mat("CampCanA", metal=(0.3, 0.3, 0.28), rust=0.95, label=((0.2, 0.05, 0.03), (0.3, 0.26, 0.17)), label_band=cp.can_band("open"))
    can_b = ck.rust_mat("CampCanB", metal=(0.3, 0.3, 0.28), rust=1.0, label=((0.06, 0.13, 0.06), (0.3, 0.27, 0.12)), label_band=cp.can_band("open"))
    can_c = ck.rust_mat("CampCanC", metal=(0.34, 0.34, 0.32), rust=0.85)
    b = ks.Builder(name)
    bodies, extra = [], []

    # tent and its gear
    P, _ = build_tent(b, None, tent)
    poles(b, P, pole, rnd)
    guy_lines(b, P, rope, peg, rnd)
    for ga, gb, gr, gh in GEAR[:1]:
        c = P(Vector((ga, gb, 0.0)))
        core = fk.Rock(radii=(gr * 0.75, gr * 0.6, 0.13), height=0.09, seed=3, power=2.4, rough=0.05, yaw=TENT_YAW + 20.0,
                       at=(c.x, c.y), subdiv=2).build()
        bodies.append(ck.body_from_bm(core))
        core.free()

    # the fire
    cp.fire_ring(b, stone, skirt, rnd, bodies, FIRE)
    cp.fire_bed(b, ash, wood, char_end, rnd, FIRE)

    # seats: a fallen log with a flat cut for sitting, and a stump
    b.lod = 2
    p0 = Vector((0.55, 0.35, G + 0.1))
    p1 = Vector((1.62, 0.12, G + 0.13))
    d = (p1 - p0).normalized()
    bodies.append(ck.solid_tube(b, wood.get("bark", d), end_bark, p0, p1, 0.155, rnd, under=under, sides=14, lump=0.07, seed=4,
                                flat=((0, 0, 1), 0.105), ragged=0.012, cut=wood.get("silver", d)))
    s0 = Vector((1.88, -1.5, G - 0.04))
    s1 = Vector((1.9, -1.49, G + 0.4))
    bodies.append(ck.solid_tube(b, wood.get("bark", Vector((0, 0, 1))), end_cut, s0, s1, 0.2, rnd, under=under, sides=16, lump=0.08, seed=9,
                                flare=0.28, r1=0.175, ragged=0.01))
    b.lod = 0

    # three rusted cans
    cp.can(b, can_a, (0.55, -1.38), 40.0, rnd, kind="open")
    cp.can(b, can_b, (1.5, -0.12), 110.0, rnd, kind="open", pitch=84.0)
    cp.can(b, can_c, (-0.15, -1.0), 15.0, rnd, kind="tall", crushed=0.55)

    # firewood bundle tied with cord, beside the tent
    fw_at = Vector((-1.5, -1.2, 0.0))
    fw_yaw = 18.0
    pl = ck.Place(at=fw_at, yaw=fw_yaw)
    layers = [(0.0, [-0.12, -0.04, 0.04, 0.12]), (0.075, [-0.08, 0.0, 0.08]), (0.14, [0.0])]
    for z, offs in layers:
        for dy in offs:
            r = rnd.uniform(0.04, 0.058)
            ln = rnd.uniform(0.55, 0.72)
            ya = rnd.uniform(-5, 5)
            q0 = pl(Vector((-ln * 0.5, dy + rnd.uniform(-0.01, 0.01), r - 0.012 + z)))
            q1 = pl(Vector((ln * 0.5, dy + rnd.uniform(-0.015, 0.015), r - 0.012 + z)))
            q0.z += G
            q1.z += G
            dd = (q1 - q0).normalized()
            split = rnd.random() < 0.5
            b.lod = 2
            ck.solid_tube(b, wood.get("bark", dd), end_bark, q0, q1, r, rnd, sides=8, lump=0.1, seed=rnd.randint(0, 99),
                          flat=((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.6), r * 0.45) if split else None, ragged=0.01,
                          cut=wood.get("silver", dd))
            b.lod = 0
    extra.append(ck.box_line((fw_at.x, fw_at.y, G + 0.09), (0.62, 0.34, 0.16), fw_yaw))
    # cord round the bundle's middle and the loose end
    ring = []
    for k in range(19):
        a = k / 18 * math.tau
        ring.append(pl(Vector((0.05 + 0.002 * k, math.cos(a) * 0.115, 0.075 + math.sin(a) * 0.105 + 0.0)) ) + Vector((0, 0, G)))
    for q in ring:
        q.z = max(q.z, G + 0.004)
    ck.wire(b, rope, ring, 0.0055, sides=4, cap=True)
    tail = [ring[-1], ring[-1] + pl.dir(Vector((0.05, 0.1, 0.0))) + Vector((0, 0, -0.04)), ring[-1] + pl.dir(Vector((0.12, 0.2, 0.0)))]
    for q in tail:
        q.z = max(q.z, G + 0.006)
    ck.wire(b, rope, tail, 0.0055, sides=4, cap=True)

    # bare earth under the camp, litter and grass
    for (x, y, r) in ((-0.5, 0.5, 1.15), (1.05, -0.7, 0.85), (1.2, 0.3, 0.55), (1.9, -1.45, 0.4)):
        ks.ground_patch(b, dirt, (x, y), r, rnd, sides=18, dome=0.006, jitter=0.35, sink=0.004, rings=2)
    ks.ground_patch(b, dirt_ash, (FIRE[0], FIRE[1]), 0.62, rnd, sides=18, dome=0.004, jitter=0.2, sink=0.004, rings=2)
    keep = lambda x, y: abs(x) < 2.35 and abs(y) < 2.35 and math.hypot(x - FIRE[0], y - FIRE[1]) > 0.5
    ck.litter_ring(b, gm["litter"], rnd, 260, (-0.1, 0.0), (0.0, 2.35), keep=keep)
    ck.litter_ring(b, gm["litter"], rnd, 90, (-0.9, 0.7), (0.0, 1.0), keep=keep)
    spots = [(-0.9, 0.9), (0.4, 0.95), (0.35, 0.1), (-1.9, 0.3), (-1.2, -0.5), (-0.1, -0.5), (0.2, 1.9), (-1.8, 1.4), (2.0, 0.9),
             (1.8, 0.25), (-0.7, 2.0), (-2.1, -0.5), (0.3, -1.9), (1.5, -1.95), (-0.5, -1.8), (2.1, -0.4), (-2.0, -1.8)]
    for i, (x, y) in enumerate(spots):
        mat = gm["straw"] if i % 3 == 0 else gm["grass"]
        ck.tuft(b, mat, x, y, rnd, count=rnd.randint(7, 13), height=rnd.uniform(0.22, 0.36), spread=rnd.uniform(0.07, 0.12))
    # weeds in the fire ring and through the tent
    for (x, y) in ((FIRE[0] - 0.28, FIRE[1] + 0.12), (FIRE[0] + 0.25, FIRE[1] - 0.2), (FIRE[0] + 0.05, FIRE[1] + 0.3)):
        ck.tuft(b, gm["grass"], x, y, rnd, count=6, height=0.2, spread=0.05)
    for (a, bb) in ((0.5, -0.1), (0.85, 0.45), (-0.2, 0.0), (0.9, -0.5), (0.2, -0.45)):
        c = P(Vector((a, bb, 0.0)))
        ck.tuft(b, gm["grass"] if a > 0 else gm["straw"], c.x, c.y, rnd, count=9, height=0.34, spread=0.07, z=G)

    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"CampCanvas": 0.9, "CampPole": 0.45, "CampRope": 0.5, "CampPeg": 0.35, "CampStoneSkirt": 0.05, "CampStone": 0.8,
               "CampAsh": 0.5, "CampCharEnd": 0.4, "CampEndCut": 0.6, "CampEndSplit": 0.35, "CampSkirtSoil": 0.05, "CampDirtAsh": 0.35,
               "CampDirt": 0.35, "CampCan": 0.8, "CampWood": 0.9, "CampLitter": 0.22, "CampGrass": 0.28, "CampStraw": 0.28}
    model = ck.export(name, pieces, bodies, FEATURES, size=ck.atlas_size(), density=density, extra=extra)
    ck.preview(name.lower(), model, [
        ("a", (-4.2, -5.0, 3.2), (0.0, 0.0, 0.2), 40),
        ("b", (4.4, -3.2, 2.4), (0.0, 0.0, 0.15), 40),
        ("top", (0.01, -0.4, 9.0), (0.0, 0.0, 0.0), 40),
        ("tent", (-2.3, -1.2, 1.5), (-0.5, 0.5, 0.15), 40),
        ("fire", (2.4, -1.9, 1.0), (1.1, -0.75, 0.05), 40),
        ("near", (-0.4, -2.1, 0.75), (0.6, -0.3, 0.1), 45),
    ])
    print("[%s] done" % name)


for n in (ONLY or [NAME]):
    build(n)
