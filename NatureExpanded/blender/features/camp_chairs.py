"""CampChairs (meadow, forest edge, roadside; the most "car camping" of the four): a fire ring of black stones with a
burned-out grill grate sagging across it, two aluminum folding chairs (one still up and leaning, one on its side)
with frayed webbing, a cracked plastic cooler lying open, a handful of cans and bottles, a dead pressure lantern on a
stump, a tarp rolled and tied. 5 x 5 m footprint, nothing above 0.9 m. Solid: the stones, the stump, the cooler (a low
box). The chairs, grate, cans and tarp are walk-through.

    blender -b --factory-startup --python camp_chairs.py -- <features folder> <preview folder> [Name ...]
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

NAME = "CampChairs"
V = Vector
FIRE = (0.05, 0.1)
STUMP = (1.4, -1.25)


def grate(b, rod, center, yaw, rnd):
    """A burned-out grill grate: a frame and a lattice of rods, bent, one corner dropped in the ash, rods burned away."""
    W, D = 0.66, 0.44
    pl = ck.Place(at=(center[0], center[1], G), yaw=yaw)

    def z_at(x, y):
        z = 0.185 - 0.1 * ck.smoothstep(-0.05, 0.3, x) * (0.35 + 0.65 * ck.smoothstep(-0.1, 0.2, y)) - 0.02 * max(0.0, mn.noise(V((x * 4.0, y * 4.0, 1.0))))
        return max(0.03, z)

    def rodline(p0, p1, r, n=12, bow=0.0):
        pts = []
        for i in range(n + 1):
            f = i / n
            x = p0[0] + (p1[0] - p0[0]) * f
            y = p0[1] + (p1[1] - p0[1]) * f
            pts.append(pl(V((x, y, z_at(x, y) + bow * math.sin(f * math.pi)))))
        ck.wire(b, rod, pts, r, sides=4, cap=True)

    nlong, ncross = 8, 5
    for i in range(nlong):
        y = -D / 2 + D * i / (nlong - 1)
        r = 0.0055 if i in (0, nlong - 1) else 0.0042
        if i not in (0, nlong - 1) and rnd.random() < 0.22:
            continue
        x1 = W / 2 if rnd.random() > 0.2 else rnd.uniform(0.0, W / 2)
        rodline((-W / 2, y), (x1, y), r)
    for j in range(ncross):
        x = -W / 2 + W * j / (ncross - 1)
        r = 0.0055 if j in (0, ncross - 1) else 0.0042
        if j not in (0, ncross - 1) and rnd.random() < 0.18:
            continue
        rodline((x, -D / 2), (x, D / 2 if rnd.random() > 0.15 else rnd.uniform(-0.05, 0.15)), r)
    # legs, rusted off at the stones
    for sx, sy in ((-1, -1), (1, 1)):
        p = V((sx * W / 2, sy * D / 2, z_at(sx * W / 2, sy * D / 2)))
        ck.wire(b, rod, [pl(p), pl(p + V((0.0, 0.0, -0.06)))], 0.0055, sides=4, cap=True)


def build(name):
    nk.reset()
    rnd = random.Random(31)
    gm = ck.ground_mats()
    wood = ck.Wood("CampWood")
    frame = ck.alu_mat("CampAlu", corrode=1.0, rust=0.55)
    web = ck.webbing_mat("CampWeb", (0.035, 0.085, 0.055), (0.3, 0.29, 0.25))
    rod = ck.rust_mat("CampGrate", metal=(0.2, 0.2, 0.2), rust=1.0, soot=0.6)
    cool_b = ck.plastic_mat("CampCoolerBody", (0.19, 0.045, 0.035), (0.12, 0.03, 0.025), chalk=0.7, cracks=1.0, mildew=0.9)
    cool_l = ck.plastic_mat("CampCoolerLid", (0.3, 0.28, 0.22), (0.2, 0.19, 0.15), chalk=0.5, cracks=0.8, mildew=0.7)
    cool_h = ck.rope_mat("CampCoolerRope", (0.12, 0.11, 0.09))
    lant_p = ck.paint_mat("CampLanternPaint", paint=(0.055, 0.1, 0.06), wear=0.8)
    lant_m = ck.rust_mat("CampLanternMetal", metal=(0.24, 0.24, 0.23), rust=0.9)
    globe = ck.glass_mat("CampGlobe", color=(0.1, 0.1, 0.09), dirt=1.0)
    tarp = ck.fabric_mat("CampTarp", (0.11, 0.1, 0.055), (0.2, 0.18, 0.11), fade=0.8, mildew=0.7, stains=0.7, seams=0.25, slits=0.5,
                         sheen=0.15)
    rope = ck.rope_mat("CampRope", (0.2, 0.17, 0.12))
    can_a = ck.rust_mat("CampCanA", metal=(0.3, 0.3, 0.28), rust=0.95, label=((0.2, 0.05, 0.03), (0.3, 0.26, 0.17)), label_band=cp.can_band("open"))
    can_b = ck.rust_mat("CampCanB", metal=(0.3, 0.3, 0.28), rust=1.0, label=((0.06, 0.13, 0.06), (0.3, 0.27, 0.12)), label_band=cp.can_band("open"))
    can_t = ck.rust_mat("CampCanBeer", metal=(0.42, 0.42, 0.4), rust=0.3, label=((0.25, 0.05, 0.03), (0.35, 0.3, 0.2)), label_band=cp.can_band("tall"))
    bot_a = ck.glass_mat("CampBottleA", color=(0.075, 0.037, 0.01), dirt=0.8)
    bot_b = ck.glass_mat("CampBottleB", color=(0.025, 0.06, 0.025), dirt=0.9)
    stone = ck.stone_mat("CampStone", sooty=(FIRE[0], FIRE[1], 0.45), moss=0.0, lichen=0.5, stain=1.4, tint=(0.8, 0.8, 0.8))
    skirt = ck.stone_mat("CampStoneSkirt", moss=0.0, lichen=0.0)
    ash = ks.ash("CampAsh")
    char_end = lk.end_grain("CampCharEnd", "burnt", 0.01)
    end_cut = lk.end_grain("CampEndCut", "bleached", 0.011)
    under = lk.soil_mat("CampSkirtSoil", moss=0.0, rooty=0.0)
    dirt = ck.dirt_mat("CampDirt")
    dirt_ash = ck.dirt_mat("CampDirtAsh", ash=0.9)
    b = ks.Builder(name)
    bodies, extra = [], []

    # fire ring, ashes, grate
    cp.fire_ring(b, stone, skirt, rnd, bodies, FIRE, radius=0.44, n=9, size=(0.11, 0.17), seed=60)
    cp.fire_bed(b, ash, wood, char_end, rnd, FIRE, radius=0.4, sticks=6, lumps=18)
    grate(b, rod, FIRE, 14.0, rnd)

    # chair A: upright, leaning back, facing the fire; chair B: knocked over on its side
    for (x, y, yaw, roll, pitch, brk) in ((-1.35, -0.6, math.degrees(math.atan2(0.7, 1.4)) - 90.0 + 8.0, 5.0, -6.0, 0.28),
                                          (1.25, 0.95, 160.0, 98.0, 0.0, 0.4)):
        pl = ck.Place(at=(x, y, 0.0), yaw=yaw, pitch=pitch, roll=roll)
        pl.rest(cp.chair_points(), clearance=-0.012)
        cp.alu_chair(b, frame, web, pl, rnd, broken=brk, sag=0.07)

    # the cooler, open, lid thrown back
    pl, lp = cp.cooler(b, cool_b, cool_l, (-0.55, 1.5), 205.0, rnd, tip=7.0, lid_angle=244.0, handle=cool_h)
    extra.append(ck.box_line((pl.at.x, pl.at.y, G + 0.14), (0.58, 0.36, 0.26), 205.0))

    # the stump with the dead lantern
    b.lod = 2
    s0 = V((STUMP[0], STUMP[1], G - 0.05))
    s1 = V((STUMP[0] + 0.02, STUMP[1] + 0.01, G + 0.36))
    bodies.append(ck.solid_tube(b, wood.get("bark", V((0, 0, 1))), end_cut, s0, s1, 0.21, rnd, under=under, sides=16, lump=0.09, seed=3,
                                flare=0.3, r1=0.185, ragged=0.012))
    b.lod = 0
    cp.lantern(b, lant_p, lant_m, globe, (STUMP[0] + 0.01, STUMP[1] + 0.0, G + 0.355), 40.0, rnd, pitch=7.0)

    # the tarp, rolled and tied, against the cooler
    cp.rolled(b, tarp, rope, (-1.65, 1.05), 72.0, rnd, length=0.92, r0=0.03, turns=4.6)

    # cans and bottles
    cp.can(b, can_a, (0.7, -0.55), 20.0, rnd, kind="open", pitch=88.0)
    cp.can(b, can_b, (0.1, -0.9), 130.0, rnd, kind="open", pitch=0.0, sink=0.012)
    cp.can(b, can_t, (-0.9, 0.35), 80.0, rnd, kind="tall", pitch=90.0, crushed=0.5)
    cp.can(b, can_t, (-0.45, -1.25), 190.0, rnd, kind="tall", pitch=90.0, crushed=0.15, roll=20.0)
    cp.can(b, can_t, (0.95, 0.35), 20.0, rnd, kind="tall", pitch=90.0, crushed=0.8)
    cp.bottle(b, bot_a, (-0.15, 0.85), 100.0, rnd, pitch=90.0)
    cp.bottle(b, bot_b, (0.55, -1.15), 30.0, rnd, pitch=88.0, broken=True)
    cp.bottle(b, bot_a, (1.8, -0.3), 10.0, rnd, pitch=90.0)
    cp.bottle(b, bot_b, (-1.15, 0.1), 200.0, rnd, pitch=86.0)

    # ground: bare earth, litter, grass
    for (x, y, r) in ((0.05, 0.1, 1.0), (-1.3, -0.5, 0.55), (1.2, 0.9, 0.5), (-0.55, 1.5, 0.6), (1.4, -1.25, 0.4)):
        ks.ground_patch(b, dirt, (x, y), r, rnd, sides=18, dome=0.006, jitter=0.35, sink=0.004, rings=2)
    ks.ground_patch(b, dirt_ash, FIRE, 0.65, rnd, sides=18, dome=0.004, jitter=0.2, sink=0.004, rings=2)
    keep = lambda x, y: abs(x) < 2.35 and abs(y) < 2.35 and math.hypot(x - FIRE[0], y - FIRE[1]) > 0.5
    ck.litter_ring(b, gm["litter"], rnd, 260, (0.0, 0.0), (0.0, 2.35), keep=keep)
    ck.litter_ring(b, gm["litter"], rnd, 80, (-0.55, 1.5), (0.0, 0.8), keep=keep)
    spots = [(-1.9, -1.5), (-1.0, -1.9), (0.6, -2.1), (1.9, -2.0), (2.1, -0.2), (2.0, 1.4), (0.9, 2.1), (-0.2, 2.1), (-1.9, 0.3),
             (-2.1, 1.9), (-0.3, -1.6), (0.6, 1.3), (-1.0, 0.9), (1.7, 0.3), (-1.6, -0.1)]
    for i, (x, y) in enumerate(spots):
        mat = gm["straw"] if i % 3 == 0 else gm["grass"]
        ck.tuft(b, mat, x, y, rnd, count=rnd.randint(7, 13), height=rnd.uniform(0.22, 0.36), spread=rnd.uniform(0.07, 0.12))
    for (x, y) in ((FIRE[0] - 0.25, FIRE[1] + 0.2), (FIRE[0] + 0.3, FIRE[1] - 0.15)):
        ck.tuft(b, gm["grass"], x, y, rnd, count=6, height=0.2, spread=0.05)

    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"CampAlu": 0.5, "CampWeb": 0.5, "CampGrate": 0.4, "CampCoolerBody": 0.7, "CampCoolerLid": 0.5, "CampCoolerRope": 0.3,
               "CampLanternPaint": 0.5, "CampLanternMetal": 0.3, "CampGlobe": 0.35, "CampTarp": 0.6, "CampRope": 0.45, "CampCanA": 0.8,
               "CampCanB": 0.8, "CampCanBeer": 0.8, "CampBottleA": 0.45, "CampBottleB": 0.45, "CampStoneSkirt": 0.05, "CampStone": 0.8,
               "CampAsh": 0.5, "CampCharEnd": 0.4, "CampEndCut": 0.6, "CampSkirtSoil": 0.05, "CampDirtAsh": 0.35, "CampDirt": 0.35,
               "CampWood": 0.9, "CampLitter": 0.22, "CampGrass": 0.28, "CampStraw": 0.28}
    model = ck.export(name, pieces, bodies, FEATURES, size=ck.atlas_size(), density=density, extra=extra)
    ck.preview(name.lower(), model, [
        ("a", (-4.4, -4.6, 3.0), (0.0, 0.0, 0.2), 40),
        ("b", (4.4, -3.0, 2.4), (0.0, 0.0, 0.2), 40),
        ("top", (0.01, -0.4, 9.0), (0.0, 0.0, 0.0), 40),
        ("chair", (-2.4, -1.9, 0.9), (-1.35, -0.6, 0.35), 40),
        ("cooler", (-1.5, 3.0, 1.2), (-0.55, 1.5, 0.15), 40),
        ("lantern", (2.6, -2.4, 1.0), (1.4, -1.25, 0.35), 45),
    ])
    print("[%s] done" % name)


for n in (ONLY or [NAME]):
    build(n)
