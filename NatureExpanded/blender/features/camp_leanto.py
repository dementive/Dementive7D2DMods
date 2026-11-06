"""CampLeanTo (pine and mixed forest, taiga): a tarp shelter years old. A ridge pole on two forked posts (one has leaned
over and dragged the ridge down), a faded blue-grey poly tarp sagging off it with a hole through it, ropes gone slack
and lying in the leaves, a drift of dead leaves in the back corner, a stick rack with a few rotted strips hanging, a
rusted enamel pot knocked over by a cold fire ring, a dented bucket, a stack of split firewood. 5 x 5 m footprint,
ridge at most 1.2 m. Solid: the two posts, the stones, the firewood stack. The rest is walk-through.

    blender -b --factory-startup --python camp_leanto.py -- <features folder> <preview folder> [Name ...]
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

NAME = "CampLeanTo"
V = Vector
RIDGE_A = V((0.78, -1.42, G + 1.2))      # south end of the ridge pole (still on its post)
RIDGE_B = V((0.42, 1.34, G + 0.7))       # north end (dropped with its leaning post)
POST_S = (0.78, -1.12)
POST_N0 = V((0.86, 1.12, G))
POST_N1 = V((0.5, 1.03, G + 0.72))
FIRE = (1.45, -1.3)
DEPTH = 1.95                              # how far the tarp reaches back from the ridge
DRIFT = (-0.78, 0.8, 0.62, 0.17)          # the leaf drift in the back corner: (x, y, radius, height)


def ridge_pt(s):
    p = RIDGE_A.lerp(RIDGE_B, s)
    p.z -= 0.1 * math.sin(math.pi * s)    # the pole sags between its supports
    return p


def tarp_pt(s, t):
    r = ridge_pt(s)
    back = DEPTH * (0.92 + 0.12 * math.sin(s * 5.0 + 1.0))
    x = r.x - back * t
    y = r.y - 0.2 * t * t * (1.0 if s > 0.5 else -0.5) + 0.05 * math.sin(t * 6.0 + s * 3.0)
    h = r.z - G
    z = h * (1.0 - t) ** 1.15
    z -= 0.13 * math.sin(math.pi * t) * (0.4 + math.sin(math.pi * s) ** 0.5)       # the sag
    z *= 1.0 - 0.15 * ck.smoothstep(0.55, 1.0, s) * ck.smoothstep(0.2, 0.9, t)    # the north corner came down
    dx, dy = x - DRIFT[0], y - DRIFT[1]
    z += DRIFT[3] * math.exp(-(dx * dx + dy * dy) / (DRIFT[2] ** 2)) * (1.0 - 0.5 * t)
    q = V((x * 4.0 + 5.0, y * 4.0, 0.6))
    rn = mn.noise(V((x * 3.0 + 1.0, y * 3.0, 2.0)))
    w = 0.02 * mn.noise(q) + 0.01 * mn.noise(q * 2.9) + 0.022 * (1.0 - 2.0 * abs(rn)) + 0.008 * (1.0 - 2.0 * abs(mn.noise(V((x * 8.0, y * 8.0, 5.0)))))
    w *= 0.5 + t
    z = max(z + w, 0.008 + 0.008 * abs(mn.noise(q * 1.9)))
    return V((x, y, G + z))


TARP_HOLES = [(0.4, 0.55, 0.13, 0.1), (0.78, 0.38, 0.07, 0.05), (0.1, 0.8, 0.12, 0.07), (0.95, 0.9, 0.18, 0.1)]


def build_tarp(b, tarp, nu=40, nv=30):
    def fn(i, j):
        s, t = i / nu, j / nv
        p = tarp_pt(s, t)
        if j == nv or i in (0, nu):
            q = V((p.x * 8.0, p.y * 8.0, 2.2))
            p.x += 0.04 * mn.noise(q)
            p.y += 0.04 * mn.noise(q + V((7, 3, 0)))
        return p

    def skip(i, j, k):
        s, t = (i + 0.5) / nu, (j + 0.5) / nv
        for hs, ht, rs, rt in TARP_HOLES:
            q = V((s * 13.0, t * 13.0, 0.9))
            if ((s - hs) / rs) ** 2 + ((t - ht) / rt) ** 2 + 0.45 * mn.noise(q) < 1.0:
                return True
        if t > 0.9 or s > 0.93:
            q = V((s * 7.0 + 3.0, t * 7.0, 3.1))
            n = mn.noise(q) + 0.35 * mn.noise(q * 3.3)
            if n > 0.3 - 0.5 * (max(t - 0.9, s - 0.93) * 8.0):
                return True
        return False

    ck.cloth(b, tarp, fn, nu, nv, skip=skip, thick=0.003, hint=V((0.2, 0, 1)))


def posts_and_ridge(b, wood, end_cut, end_split, under, rnd, bodies, extra):
    # south post: straight, forked
    p0 = V((POST_S[0], POST_S[1], G - 0.05))
    p1 = V((POST_S[0], POST_S[1], ridge_pt(0.1).z - 0.0))
    pts = [p0.lerp(p1, f) + V((0.012 * math.sin(f * 5), 0.01 * math.cos(f * 4), 0.0)) for f in (0, 0.25, 0.5, 0.75, 1.0)]
    d = V((0, 0, 1))
    lk.tube_broken(b, wood.get("bark", d), end_split, pts, [0.05, 0.045, 0.042, 0.04, 0.038], 9, rnd, jag=0.6)
    top = pts[-1]
    for sx in (-1, 1):
        pr = [top + V((0, 0, -0.04)), top + V((0.0, sx * 0.06, 0.09)), top + V((0.0, sx * 0.1, 0.17))]
        lk.tube_broken(b, wood.get("bark", V((0, sx * 0.4, 1))), end_split, pr, [0.025, 0.022, 0.02], 6, rnd, jag=0.8)
    extra.append("capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (p0.x, p0.y, G + 0.05, p1.x, p1.y, p1.z - 0.1, 0.04))
    # north post: leaning over, its fork out of the ridge
    pn = [POST_N0.lerp(POST_N1, f) + V((0.0, 0.012 * math.sin(f * 6), 0.0)) for f in (0, 0.25, 0.5, 0.75, 1.0)]
    dn = (POST_N1 - POST_N0).normalized()
    lk.tube_broken(b, wood.get("bark", dn), end_split, pn, [0.052, 0.047, 0.043, 0.04, 0.037], 9, rnd, jag=0.6)
    top = pn[-1]
    for sx in (-1, 1):
        pr = [top + dn * -0.04, top + V((-0.03, sx * 0.07, 0.08)), top + V((-0.06, sx * 0.1, 0.15))]
        lk.tube_broken(b, wood.get("bark", V((0, sx * 0.4, 1))), end_split, pr, [0.025, 0.022, 0.02], 6, rnd, jag=0.8)
    extra.append("capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (POST_N0.x, POST_N0.y, G + 0.05, POST_N1.x, POST_N1.y, POST_N1.z - 0.08, 0.04))
    # the ridge pole: stripped, silver, a bow in it, knots, resting in the south fork and fallen onto the north one
    rp = [ridge_pt(i / 12.0) + V((0.0, 0.0, 0.0)) for i in range(13)]
    rp[0] = rp[0] + V((0.0, 0.0, 0.06))
    d = (rp[-1] - rp[0]).normalized()
    lk.tube_broken(b, wood.get("silver", d), end_cut, rp, [0.036, 0.034, 0.033, 0.032, 0.031, 0.03, 0.03, 0.029, 0.028, 0.027, 0.026, 0.025, 0.024],
                   8, rnd, jag=0.5)
    # a snapped branch stub or two
    for f in (0.35, 0.62, 0.8):
        p = ridge_pt(f)
        dd = V((rnd.uniform(-0.4, 0.4), rnd.uniform(-1, 1), rnd.uniform(0.3, 0.8))).normalized()
        lk.tube_broken(b, wood.get("silver", dd), end_cut, [p, p + dd * 0.06, p + dd * 0.12], [0.012, 0.01, 0.009], 5, rnd, jag=0.8)


def ropes_and_pegs(b, tarp_p, rope, peg, grommet, rnd):
    """Corner ropes: two still tied (slack, lying in the grass), one snapped lying coiled, pegs rusted."""
    corners = [
        (tarp_pt(0.0, 0.0), V((1.12, -1.95, G + 0.01)), 0.04),
        (tarp_pt(0.0, 1.0), V((-1.8, -1.95, G + 0.01)), 0.05),
        (tarp_pt(1.0, 1.0), V((-1.85, 1.8, G + 0.01)), 0.07),
    ]
    for a, e, sag in corners:
        pts = ck.catenary(a, e, sag, n=12)
        for q in pts:
            q.z = max(G + 0.008, q.z)
        ck.wire(b, rope, pts, 0.0058, sides=5, cap=True)
        cp.ring(b, grommet, a, V((0, 0, 1)), 0.016, 0.0035, sides=4, n=10)
        pp = [e + V((0, 0, 0.05)), e - V((0, 0, 0.0)), e - V((0, 0, 0.1))]
        ck.wire(b, peg, pp, 0.0055, sides=4, cap=True)
    # the north front rope, snapped: a coil on the ground
    top = ridge_pt(1.0)
    pts = [top, top + V((0.12, 0.1, -0.2)), V((0.55, 1.45, G + 0.05)), V((0.95, 1.7, G + 0.01))]
    c = V((0.95, 1.7, G))
    for k in range(18):
        a = k / 17 * math.tau * 1.6
        r = 0.14 - 0.06 * k / 17
        pts.append(V((c.x + r * math.cos(a), c.y + r * math.sin(a), G + 0.008 + 0.006 * (k % 3))))
    ck.wire(b, rope, pts, 0.0058, sides=5, cap=True)


def drying_rack(b, wood, end_cut, end_split, strip, rope, rnd, extra, at=(1.55, 0.05)):
    ax, ay = at
    ups = []
    for k, sy in enumerate((-0.6, 0.52)):
        base = V((ax + rnd.uniform(-0.02, 0.02), ay + sy, G - 0.04))
        lean = V((0.0, 0.0, 0.0)) if k == 0 else V((0.11, 0.2, 0.0))
        top = base + V((0, 0, 1.0)) + lean
        pts = [base.lerp(top, f) for f in (0, 0.35, 0.7, 1.0)]
        d = (top - base).normalized()
        lk.tube_broken(b, wood.get("silver", d), end_cut, pts, [0.026, 0.024, 0.022, 0.02], 7, rnd, jag=0.8)
        for sx in (-1, 1):
            pr = [top + d * -0.03, top + V((sx * 0.05, 0.0, 0.07)), top + V((sx * 0.09, 0.0, 0.13))]
            lk.tube_broken(b, wood.get("silver", V((sx * 0.5, 0, 1))), end_cut, pr, [0.014, 0.012, 0.011], 5, rnd, jag=0.7)
        ups.append(top)
    # crossbar: the north end slipped out of its fork and rests low on its slat
    barp = [ups[0] + V((0, 0, 0.0)), ups[0].lerp(ups[1], 0.5) + V((0.02, 0, -0.18)), ups[1] + V((0.0, 0.05, -0.48))]
    pts = [ck.catenary(barp[0], barp[2], 0.0, n=10)[i] for i in range(11)]
    pts = [barp[0].lerp(barp[2], i / 10) + V((0.04 * math.sin(i / 10 * math.pi), 0.0, -0.1 * math.sin(i / 10 * math.pi))) for i in range(11)]
    d = (barp[2] - barp[0]).normalized()
    lk.tube_broken(b, wood.get("silver", d), end_cut, pts, [0.017] * 11, 6, rnd, jag=0.6)
    # slats leaning from the bar to the ground
    for sy, ln in ((-0.3, 1.1), (0.15, 0.95)):
        top = pts[int(5 + sy * 6)] if 0 <= int(5 + sy * 6) < 11 else pts[5]
        foot = V((top.x + 0.5, top.y + 0.05, G + 0.01))
        dd = (foot - top).normalized()
        lk.tube_broken(b, wood.get("silver", dd), end_cut, [top, top.lerp(foot, 0.5), foot], [0.012, 0.011, 0.01], 5, rnd, jag=0.6)
    # strips of something dried and rotted hung over the bar
    for k in range(6):
        s = 0.12 + 0.13 * k + rnd.uniform(-0.02, 0.02)
        i = min(9, int(s * 10))
        p = pts[i].lerp(pts[i + 1], s * 10 - i)
        w = rnd.uniform(0.028, 0.05)
        ln = rnd.uniform(0.18, 0.38)
        spts = [p + V((0.0, 0.0, 0.02)), p + V((0.015, 0.0, -0.01)), p + V((0.02, rnd.uniform(-0.03, 0.03), -0.05 - ln * 0.4)),
                p + V((0.01, rnd.uniform(-0.04, 0.04), -0.05 - ln * 0.8)), p + V((0.0, rnd.uniform(-0.05, 0.05), -ln))]
        spts = [V((q.x, q.y, max(q.z, G + 0.01))) for q in spts]
        ck.ribbon(b, strip, spts, [w, w, w * 0.9, w * 0.8, w * 0.5], up=V((1, 0, 0)))
    extra.append("capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (ax, ay - 0.6, G + 0.05, ax, ay - 0.6, G + 0.85, 0.028))


def firewood(b, wood, end_cut, end_split, rnd, extra, at=(0.38, -1.78), yaw=-8.0):
    pl = ck.Place(at=(at[0], at[1], 0.0), yaw=yaw)
    rows = [(0.0, 5), (0.085, 4), (0.165, 3), (0.24, 2)]
    for z, n in rows:
        for i in range(n):
            r = rnd.uniform(0.04, 0.052)
            dy = (i - (n - 1) / 2) * 0.092 + rnd.uniform(-0.008, 0.008)
            ln = rnd.uniform(0.5, 0.6)
            sh = rnd.uniform(-0.04, 0.04)
            q0 = pl(V((-ln * 0.5 + sh, dy, r - 0.012 + z))) + V((0, 0, G))
            q1 = pl(V((ln * 0.5 + sh, dy + rnd.uniform(-0.01, 0.01), r - 0.012 + z + rnd.uniform(-0.005, 0.01)))) + V((0, 0, G))
            dd = (q1 - q0).normalized()
            split = rnd.random() < 0.55
            b.lod = 2
            ck.solid_tube(b, wood.get("bark", dd), end_split, q0, q1, r, rnd, sides=8, lump=0.08, seed=rnd.randint(0, 99),
                          flat=((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.7), r * 0.4) if split else None, ragged=0.01,
                          cut=wood.get("silver", dd))
            b.lod = 0
    extra.append(ck.box_line((at[0], at[1], G + 0.15), (0.6, 0.46, 0.3), yaw))


def build(name):
    nk.reset()
    rnd = random.Random(23)
    gm = ck.ground_mats()
    wood = ck.Wood("CampWood")
    tarp = ck.fabric_mat("CampTarp", (0.04, 0.058, 0.078), (0.09, 0.11, 0.135), fade=0.45, mildew=0.7, stains=0.95, seams=0.25, slits=0.5,
                         sheen=0.1, bleach=(0.14, 0.16, 0.18))
    rope = ck.rope_mat("CampRope", (0.27, 0.19, 0.06))
    peg = ck.rust_mat("CampPeg", rust=1.0)
    grommet = ck.rust_mat("CampGrommet", metal=(0.34, 0.3, 0.2), rust=0.5)
    strip = ck.fabric_mat("CampStrip", (0.075, 0.055, 0.04), (0.04, 0.032, 0.024), fade=0.1, mildew=0.9, stains=0.3, slits=0.0, seams=0.0,
                          creases=1.2)
    stone = ck.stone_mat("CampStone", sooty=(FIRE[0], FIRE[1], 0.3), moss=0.0, lichen=0.5, stain=1.4, tint=(0.8, 0.8, 0.8))
    skirt = ck.stone_mat("CampStoneSkirt", moss=0.0, lichen=0.0)
    ash = ks.ash("CampAsh")
    char_end = lk.end_grain("CampCharEnd", "burnt", 0.01)
    end_cut = lk.end_grain("CampEndCut", "bleached", 0.011)
    end_split = lk.end_grain("CampEndSplit", "bleached", 0.014)
    under = lk.soil_mat("CampSkirtSoil", moss=0.0, rooty=0.0)
    dirt = ck.dirt_mat("CampDirt")
    enamel = ck.enamel_mat("CampEnamel", enamel=(0.2, 0.215, 0.225), speck=(0.03, 0.04, 0.06), wear=1.0, rim=(0.03, 0.05, 0.1), rim_t=cp.profile_t(cp.pot_profile(), 5),
                           foot_t=cp.profile_t(cp.pot_profile(), 2) + 0.05)
    bucket_m = ck.rust_mat("CampBucket", metal=(0.3, 0.31, 0.32), rust=0.9)
    wire_m = ck.rust_mat("CampWire", metal=(0.2, 0.2, 0.2), rust=1.0)
    b = ks.Builder(name)
    bodies, extra = [], []

    build_tarp(b, tarp)
    posts_and_ridge(b, wood, end_cut, end_split, under, rnd, bodies, extra)
    ropes_and_pegs(b, None, rope, peg, grommet, rnd)
    drying_rack(b, wood, end_cut, end_split, strip, rope, rnd, extra)
    firewood(b, wood, end_cut, end_split, rnd, extra)

    # the cold fire, the pot and the bucket
    cp.fire_ring(b, stone, skirt, rnd, bodies, FIRE, radius=0.3, n=7, size=(0.08, 0.13), seed=40)
    cp.fire_bed(b, ash, wood, char_end, rnd, FIRE, radius=0.26, sticks=5, lumps=10)
    cp.pot(b, enamel, wire_m, (1.9, -0.85), 140.0, rnd, pitch=90.0, roll=0.0)
    cp.bucket(b, bucket_m, (-0.1, 1.85), 30.0, rnd, pitch=90.0, roll=14.0, bail_tilt=60.0, sink=0.02)

    # bare earth under the shelter, the leaf drift, litter and grass
    for (x, y, r) in ((-0.2, 0.1, 1.2), (1.45, -1.25, 0.7), (1.55, 0.0, 0.6)):
        ks.ground_patch(b, dirt, (x, y), r, rnd, sides=18, dome=0.006, jitter=0.35, sink=0.004, rings=2)
    keep = lambda x, y: abs(x) < 2.35 and abs(y) < 2.35 and math.hypot(x - FIRE[0], y - FIRE[1]) > 0.32
    drift = lambda x, y: DRIFT[3] * 0.9 * math.exp(-((x - DRIFT[0]) ** 2 + (y - DRIFT[1]) ** 2) / (DRIFT[2] ** 2 * 0.8))
    ck.litter_ring(b, gm["litter"], rnd, 520, (DRIFT[0], DRIFT[1]), (0.0, 0.7), keep=keep, zfn=drift, size=(0.06, 0.095))
    ck.litter_ring(b, gm["litter"], rnd, 230, (-0.2, 0.0), (0.0, 2.2), keep=keep)
    ck.litter_ring(b, gm["litter"], rnd, 110, (1.3, 0.0), (0.0, 1.0), keep=keep)
    spots = [(-1.9, 0.2), (-1.5, -1.9), (-0.4, -2.0), (1.0, -2.1), (2.1, -1.8), (2.1, 0.7), (1.7, 1.9), (0.0, 2.1), (-1.1, 2.0),
             (-2.1, 1.2), (1.9, -0.3), (-2.0, -0.9), (0.9, 0.9), (-0.2, -1.2), (1.2, 1.3)]
    for i, (x, y) in enumerate(spots):
        mat = gm["straw"] if i % 3 == 0 else gm["grass"]
        ck.tuft(b, mat, x, y, rnd, count=rnd.randint(7, 13), height=rnd.uniform(0.22, 0.36), spread=rnd.uniform(0.07, 0.12))
    for (x, y) in ((FIRE[0] - 0.12, FIRE[1] + 0.1), (FIRE[0] + 0.1, FIRE[1] - 0.1)):
        ck.tuft(b, gm["grass"], x, y, rnd, count=6, height=0.2, spread=0.05)

    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"CampTarp": 0.9, "CampRope": 0.5, "CampPeg": 0.35, "CampGrommet": 0.25, "CampStrip": 0.6, "CampStoneSkirt": 0.05,
               "CampStone": 0.7, "CampAsh": 0.5, "CampCharEnd": 0.4, "CampEndCut": 0.5, "CampEndSplit": 0.35, "CampSkirtSoil": 0.05,
               "CampDirt": 0.35, "CampEnamel": 0.8, "CampBucket": 0.7, "CampWire": 0.3, "CampWood": 0.9, "CampLitter": 0.22,
               "CampGrass": 0.28, "CampStraw": 0.28}
    model = ck.export(name, pieces, bodies, FEATURES, size=ck.atlas_size(), density=density, extra=extra)
    ck.preview(name.lower(), model, [
        ("a", (-4.6, -4.4, 3.0), (0.0, 0.0, 0.3), 40),
        ("b", (4.4, -3.4, 2.4), (0.0, 0.0, 0.3), 40),
        ("top", (0.01, -0.4, 9.0), (0.0, 0.0, 0.0), 40),
        ("shelter", (-0.5, -2.4, 1.0), (0.1, 0.6, 0.3), 40),
        ("rack", (3.2, -1.6, 1.2), (1.5, 0.0, 0.4), 40),
        ("pot", (2.7, -2.4, 0.9), (1.6, -1.0, 0.1), 45),
    ])
    print("[%s] done" % name)


for n in (ONLY or [NAME]):
    build(n)
