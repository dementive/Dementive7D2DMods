"""CampFishing (lake shores and river banks, flat ground near water; the water side is -y): a fishing spot someone used for
a summer long ago. A split-log bench with one stub leg gone, a fishing rod still leaning on its forked stick with the
line rotted through, a rusty bucket with fish bones in it and more bones scattered, a small cold fire, a faded folded
camp chair propped on the bench, tin cans, a stringer cord on a stake with a skeleton on it. 5 x 5 m footprint, nothing
above 0.95 m. Solid: the bench and its leg, the stones. The rod, bucket, chair, cans and cord are walk-through.

    blender -b --factory-startup --python camp_fishing.py -- <features folder> <preview folder> [Name ...]
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
import kit_forest as kf  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ck.set_preview_dir(PREVIEWS)
ONLY = ck.only()

NAME = "CampFishing"
V = Vector
FIRE = (0.2, 0.0)
BENCH_A = V((-0.88, 1.36, G + 0.3))
BENCH_B = V((0.82, 1.28, G + 0.2))       # the leg under this end is gone; the log has settled
ROD_BUTT = V((0.1, -0.5, G + 0.045))
FORK = V((-0.75, -1.3, G + 0.7))
STAKE = V((1.75, -1.0, G))


def cork_mat(name):
    mat, g = ck.new_mat(name)
    d, r = kf._cells(g, 330.0)
    base = g.mix(g.ramp(g.noise(7.0, detail=4.0), 0.3, 0.7), (0.17, 0.1, 0.055), (0.09, 0.05, 0.027))
    pit = g.math("MULTIPLY", g.ramp(d, 0.55, 0.2), g.ramp(r, 0.3, 0.8))
    col = g.mix(g.math("MULTIPLY", pit, 0.75), base, (0.03, 0.017, 0.009))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.5, 0.75), 0.6), col, (0.05, 0.04, 0.03))
    col, rough, low = ck._ground_dirt(g, col, 0.9, amount=0.7, height=0.08)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), 0.0, rough, g.bump(g.math("SUBTRACT", 1.0, pit), 1.0, 0.002))


def forked(b, wood, end_cut, base, top, rnd, r0=0.028, prongs=2, spread=0.06):
    """A forked branch from `base` to `top`: the stem and two prongs."""
    pts = [base.lerp(top, f) + V((0.008 * math.sin(f * 7), 0.008 * math.cos(f * 6), 0.0)) for f in (0, 0.3, 0.62, 1.0)]
    d = (top - base).normalized()
    lk.tube_broken(b, wood.get("bark", d), end_cut, pts, [r0, r0 * 0.93, r0 * 0.85, r0 * 0.78], 7, rnd, jag=0.8)
    for k in range(prongs):
        s = -1.0 if k == 0 else 1.0
        side = d.cross(V((0, 0, 1)))
        if side.length < 1e-3:
            side = V((1, 0, 0))
        side.normalize()
        pr = [top - d * 0.04, top + d * 0.05 + side * s * spread * 0.6, top + d * 0.14 + side * s * spread * 1.4]
        lk.tube_broken(b, wood.get("bark", (pr[2] - pr[0])), end_cut, pr, [r0 * 0.6, r0 * 0.55, r0 * 0.5], 6, rnd, jag=0.9)


def rod(b, blank, cork, metal, line, rnd):
    d = (FORK - ROD_BUTT).normalized()
    L = 1.82
    tip = ROD_BUTT + d * L
    pts = [ROD_BUTT + d * (L * k / 14) + V((0, 0, 0.0)) for k in range(15)]
    # the butt end on the ground with a cork grip and a reel
    grip = [pts[0] - d * 0.03, pts[0], pts[1]]
    ck.tapered(b, cork, [ROD_BUTT - d * 0.04, ROD_BUTT + d * 0.1, ROD_BUTT + d * 0.24], 0.0155, 0.0165, sides=8, cap=True)
    radii = [0.0098 * (1.0 - k / 16) ** 1.1 + 0.0018 for k in range(15)]
    # a little droop at the tip
    tp = [p + V((0, 0, -0.1 * (max(0.0, (k - 9) / 5.0)) ** 2)) for k, p in enumerate(pts)]
    ck.tapered(b, blank, tp[2:], 0.0098, 0.0018, sides=6, cap=True)
    ck.wire(b, blank, [ROD_BUTT + d * 0.24, tp[2]], 0.0098, sides=6, cap=False)
    # reel: a short wide drum on the grip, spool of rotten line
    side = d.cross(V((0, 0, 1))).normalized()
    rc = ROD_BUTT + d * 0.2 + side * 0.035
    ck.lathe(b, metal, [(0.0, -0.014), (0.032, -0.014), (0.036, -0.01), (0.036, 0.01), (0.032, 0.014), (0.0, 0.014)],
             ck.Place(matrix=Matrix.Translation(rc) @ side.to_track_quat("Z", "Y").to_matrix().to_4x4()), sides=16, rnd=rnd)
    ck.wire(b, metal, [ROD_BUTT + d * 0.2 + side * 0.01, rc + side * 0.0, rc + side * 0.05], 0.004, sides=4)
    for k in (4, 6, 8, 10, 12):
        c = tp[k] + V((0, 0, 0.012))
        cp.ring(b, metal, c, d, 0.0072 - 0.0003 * k * 0.5, 0.0013, sides=3, n=8)
    return tip, tp[-1], d


def build(name):
    nk.reset()
    rnd = random.Random(47)
    gm = ck.ground_mats()
    wood = ck.Wood("CampWood")
    frame = ck.alu_mat("CampAlu", corrode=1.0, rust=0.5)
    canvas = ck.fabric_mat("CampCanvas", (0.045, 0.055, 0.1), (0.11, 0.12, 0.17), fade=0.85, mildew=0.8, stains=0.8, seams=0.5, slits=0.6)
    rope = ck.rope_mat("CampRope", (0.2, 0.17, 0.12))
    linem = ck.rope_mat("CampLine", (0.07, 0.07, 0.065))
    cork = cork_mat("CampCork")
    blank = ck.rust_mat("CampRod", metal=(0.1, 0.1, 0.09), rust=0.35, paint=(0.04, 0.05, 0.035), paint_cover=0.8)
    reel = ck.rust_mat("CampReel", metal=(0.28, 0.27, 0.25), rust=0.9)
    bone = ck.bone_mat("CampBone")
    bucket_m = ck.rust_mat("CampBucket", metal=(0.3, 0.31, 0.32), rust=1.0)
    can_a = ck.rust_mat("CampCanA", metal=(0.3, 0.3, 0.28), rust=0.95, label=((0.2, 0.05, 0.03), (0.3, 0.26, 0.17)), label_band=cp.can_band("open"))
    can_b = ck.rust_mat("CampCanB", metal=(0.3, 0.3, 0.28), rust=1.0, label=((0.06, 0.13, 0.06), (0.3, 0.27, 0.12)), label_band=cp.can_band("open"))
    bobber = ck.plastic_mat("CampBobber", (0.19, 0.04, 0.03), (0.3, 0.28, 0.24), chalk=0.8, cracks=0.8, mildew=0.8)
    stone = ck.stone_mat("CampStone", sooty=(FIRE[0], FIRE[1], 0.26), moss=0.0, lichen=0.5, stain=1.4, tint=(0.8, 0.8, 0.8))
    skirt = ck.stone_mat("CampStoneSkirt", moss=0.0, lichen=0.0)
    ash = ks.ash("CampAsh")
    char_end = lk.end_grain("CampCharEnd", "burnt", 0.01)
    end_cut = lk.end_grain("CampEndCut", "bleached", 0.011)
    end_split = lk.end_grain("CampEndSplit", "bleached", 0.016)
    under = lk.soil_mat("CampSkirtSoil", moss=0.0, rooty=0.0)
    dirt = ck.dirt_mat("CampDirt")
    b = ks.Builder(name)
    bodies, extra = [], []

    # the bench: half a log, flat side up, on one stub leg; the other end has settled onto the ground
    b.lod = 2
    d = (BENCH_B - BENCH_A).normalized()
    bodies.append(ck.solid_tube(b, wood.get("bark", d), end_split, BENCH_A, BENCH_B, 0.2, rnd, under=under, sides=14, lump=0.07, seed=5,
                                flat=((0, 0, 1), 0.0), ragged=0.014, cut=wood.get("silver", d)))
    leg = V((-0.72, 1.36, G - 0.05))
    bodies.append(ck.solid_tube(b, wood.get("bark", V((0, 0, 1))), end_cut, leg, leg + V((0.0, 0.0, 0.2)), 0.1, rnd, under=under, sides=10,
                                lump=0.09, seed=8, flare=0.2, ragged=0.01))
    # the other stub, fallen on its side beside the bench
    l0 = V((0.55, 1.78, G + 0.095))
    l1 = V((0.8, 1.74, G + 0.095))
    bodies.append(ck.solid_tube(b, wood.get("bark", l1 - l0), end_cut, l0, l1, 0.1, rnd, under=under, sides=10, lump=0.09, seed=11, ragged=0.012))
    b.lod = 0

    # forked stick and the rod leaning on it
    forked(b, wood, end_cut, V((FORK.x + 0.05, FORK.y + 0.04, G - 0.06)), FORK, rnd, r0=0.026, spread=0.07)
    tip, tip_end, rd = rod(b, blank, cork, reel, linem, rnd)
    # the line from the tip, rotted in places, down to the ground and a rusty hook and a faded bobber
    pts = [tip_end]
    pts += [tip_end + V((-0.03, -0.1, -0.35)), tip_end + V((-0.02, -0.14, -0.55))]
    base = V((tip_end.x - 0.05, tip_end.y - 0.25, G + 0.02))
    pts += [base + V((0.0, 0.0, 0.18)), base]
    cur = base.copy()
    for k in range(10):
        a = k * 0.75
        cur = cur + V((math.cos(a) * 0.06, math.sin(a) * 0.05 - 0.01, 0.0))
        pts.append(V((cur.x, cur.y, G + 0.008 + 0.004 * (k % 2))))
    for seg in (pts[:3], pts[3:]):
        ck.wire(b, linem, seg, 0.0024, sides=3, cap=True)
    hook = pts[-1]
    cp.ring(b, reel, hook + V((0, 0, 0.012)), V((0, 1, 0)), 0.012, 0.0016, sides=3, n=9)
    # bobber: a faded float lying in the grass
    ck.lathe(b, bobber, [(0.0, -0.025), (0.014, -0.022), (0.022, -0.005), (0.021, 0.012), (0.012, 0.026), (0.0, 0.03)],
             ck.Place(at=(hook.x + 0.1, hook.y - 0.03, G + 0.022), yaw=10.0, pitch=84.0), sides=12, rnd=rnd)

    # bucket with bones, bones scattered
    cp.bucket(b, bucket_m, (1.15, 0.05), 20.0, rnd, pitch=0.0, bail_tilt=82.0, dents=1.2)
    cp.fish_bones(b, bone, (1.15, 0.05), 35.0, rnd, size=0.55, z=G + 0.034, pitch=0.0, roll=0.0)
    cp.fish_bones(b, bone, (1.12, 0.1), 150.0, rnd, size=0.38, z=G + 0.058, pitch=0.0, roll=14.0, skull=False)
    cp.fish_bones(b, bone, (1.7, -0.45), 100.0, rnd, size=0.6, z=G + 0.008, pitch=0.0, roll=0.0)
    cp.fish_bones(b, bone, (-0.4, -0.15), 20.0, rnd, size=0.4, z=G + 0.008, pitch=0.0, roll=0.0, skull=False)

    # the cold fire
    cp.fire_ring(b, stone, skirt, rnd, bodies, FIRE, radius=0.27, n=7, size=(0.075, 0.12), seed=80)
    cp.fire_bed(b, ash, wood, char_end, rnd, FIRE, radius=0.22, sticks=4, lumps=8)

    # cans
    cp.can(b, can_a, (0.55, -0.15), 70.0, rnd, kind="open", pitch=88.0)
    cp.can(b, can_b, (-0.35, 0.45), 160.0, rnd, kind="open", pitch=0.0, crushed=0.3, sink=0.012)
    cp.can(b, can_b, (0.05, 0.95), 15.0, rnd, kind="open", pitch=86.0, crushed=0.5)

    # the stringer: a stake with a cord running to a fish skeleton
    sd = V((-0.12, 0.05, 1.0)).normalized()
    s0 = STAKE + V((0, 0, -0.1))
    s1 = STAKE + sd * 0.6
    ck.tapered(b, wood.get("silver", sd), [s0, s0.lerp(s1, 0.5), s1], 0.017, 0.0145, sides=7, cap=True)
    cord = [s1 - sd * 0.06, s1 + V((0.02, -0.02, -0.12)), s1 + V((0.04, -0.12, -0.38)), V((STAKE.x + 0.08, STAKE.y - 0.3, G + 0.03))]
    cur = cord[-1].copy()
    for k in range(9):
        a = k * 0.9 + 1.0
        cur = cur + V((math.cos(a) * 0.06, math.sin(a) * 0.08 - 0.045, 0.0))
        cord.append(V((cur.x, cur.y, G + 0.01 + 0.003 * (k % 2))))
    ck.wire(b, rope, cord, 0.0032, sides=3, cap=True)
    cp.ring(b, reel, cord[len(cord) // 2], V((0, 0, 1)), 0.016, 0.0022, sides=3, n=9)
    cp.fish_bones(b, bone, (cur.x + 0.05, cur.y - 0.1), 255.0, rnd, size=0.65, z=G + 0.01)

    # the folded camp chair propped against the bench
    chair_pl = ck.Place(at=(0.0, 1.62, 0.0), yaw=185.0, pitch=-66.0)
    lp = [V((sx, 0.0, z)) for sx in (-0.19, 0.19) for z in (0.0, 0.88)]
    chair_pl.rest(lp, clearance=-0.01)
    for sx in (-0.19, 0.19):
        ck.wire(b, frame, [chair_pl(V((sx, 0.0, 0.0))), chair_pl(V((sx, 0.0, 0.45))), chair_pl(V((sx, 0.01, 0.88)))], 0.0115, sides=6, cap=True)
        ck.wire(b, frame, [chair_pl(V((sx * 0.9, 0.045, 0.0))), chair_pl(V((sx * 0.8, 0.045, 0.45))), chair_pl(V((sx * 0.6, 0.04, 0.88)))],
                0.0105, sides=6, cap=True)

    def cfn(i, j):
        x = -0.19 + 0.38 * i / 16.0
        z = 0.12 + 0.62 * j / 18.0
        y = 0.022 + 0.032 * math.sin(j * 1.35 + i * 0.1) * (0.6 + 0.4 * math.sin(i * 0.5))
        return chair_pl(V((x, y, z)))

    ck.cloth(b, canvas, cfn, 16, 18, thick=0.003, hint=chair_pl.dir(V((0, 1, 0))))

    # ground: bare earth, litter, grass, a few dead reed blades
    for (x, y, r) in ((0.2, 0.2, 1.1), (-0.1, 1.4, 0.8), (1.2, 0.0, 0.5), (-0.6, -0.8, 0.5)):
        ks.ground_patch(b, dirt, (x, y), r, rnd, sides=18, dome=0.006, jitter=0.35, sink=0.004, rings=2)
    keep = lambda x, y: abs(x) < 2.35 and abs(y) < 2.35 and math.hypot(x - FIRE[0], y - FIRE[1]) > 0.3
    ck.litter_ring(b, gm["litter"], rnd, 190, (0.0, 0.3), (0.0, 2.4), keep=lambda x, y: keep(x, y) and y > -1.0)
    spots = [(-1.9, -1.7), (-1.0, -2.0), (0.2, -2.1), (1.2, -2.0), (2.1, -1.9), (2.0, -0.3), (2.1, 1.2), (1.2, 2.1), (-0.3, 2.1),
             (-1.5, 2.0), (-2.1, 0.8), (-2.0, -0.4), (-1.2, -0.7), (0.8, -1.2), (1.6, 0.9), (-0.9, 0.3)]
    for i, (x, y) in enumerate(spots):
        mat = gm["straw"] if i % 2 == 0 else gm["grass"]
        ck.tuft(b, mat, x, y, rnd, count=rnd.randint(7, 13), height=rnd.uniform(0.25, 0.42) if y < -1.2 else rnd.uniform(0.2, 0.34),
                spread=rnd.uniform(0.07, 0.12))
    for (x, y) in ((FIRE[0] - 0.1, FIRE[1] + 0.12), (FIRE[0] + 0.1, FIRE[1] - 0.1)):
        ck.tuft(b, gm["grass"], x, y, rnd, count=6, height=0.2, spread=0.05)

    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"CampAlu": 0.5, "CampCanvas": 0.7, "CampRope": 0.4, "CampLine": 0.2, "CampCork": 0.4, "CampRod": 0.4, "CampReel": 0.3,
               "CampBone": 0.6, "CampBucket": 0.7, "CampCanA": 0.8, "CampCanB": 0.8, "CampBobber": 0.3, "CampStoneSkirt": 0.05,
               "CampStone": 0.8, "CampAsh": 0.5, "CampCharEnd": 0.4, "CampEndCut": 0.5, "CampEndSplit": 0.5, "CampSkirtSoil": 0.05,
               "CampDirt": 0.35, "CampWood": 1.0, "CampLitter": 0.22, "CampGrass": 0.28, "CampStraw": 0.28}
    model = ck.export(name, pieces, bodies, FEATURES, size=ck.atlas_size(), density=density, extra=extra)
    ck.preview(name.lower(), model, [
        ("a", (-4.5, -4.5, 3.0), (0.0, 0.0, 0.2), 40),
        ("b", (4.6, -2.6, 2.4), (0.0, 0.0, 0.2), 40),
        ("top", (0.01, -0.4, 9.0), (0.0, 0.0, 0.0), 40),
        ("bench", (-1.6, -0.3, 1.0), (0.0, 1.4, 0.25), 40),
        ("rod", (1.2, -2.6, 1.1), (-0.5, -1.0, 0.5), 40),
        ("bucket", (2.4, -0.9, 0.9), (1.1, 0.05, 0.15), 45),
    ])
    print("[%s] done" % name)


for n in (ONLY or [NAME]):
    build(n)
