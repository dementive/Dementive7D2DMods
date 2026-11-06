"""HollowTrunk01, HollowTrunk02 (pine forest, SUPER rare): a hollow fallen trunk 3.4 m long and 1.1 m thick lying in the
forest, moss on top, ferns at the dark mouth, shelf fungus up the side. A forest stash is hidden inside: the block is a
loot container (see gen_nature.py, FEATURE_KINDS "cache"). Solid like the logs (capsule colliders).

    blender -b --factory-startup --python hollow_trunk.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
lk.set_preview_dir(PREVIEWS)
ONLY = lk.only()

SPECS = {
    "HollowTrunk01": dict(L=3.5, r=(0.62, 0.52), seed=2, moss=0.7, peel=0.56),
    "HollowTrunk02": dict(L=3.2, r=(0.58, 0.5), seed=8, moss=1.15, peel=0.6),
}


def build(name):
    sp = SPECS[name]
    nk.reset()
    rnd = random.Random(sp["seed"] * 71 + 9)
    kw = dict(style="forest", moss=sp["moss"], bs=0.45, peel=sp["peel"])
    bark = lk.bark_mat("HtBark", **kw)
    under = lk.bark_mat("HtBarkUnder", **dict(kw, moss=0.0))
    moss = lk.moss_shell_mat("HtMoss", **kw)
    rim = lk.end_grain("HtRim", "rot", 0.012)
    dark = lk.end_grain("HtDark", "hollow", 0.02)
    cap, pores = lk.fungus_materials()
    fern_mat = nk.plant("HtFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    mcap, mpores, mstem = lk.mushroom_materials()
    litter = lk.litter_materials()
    b = ks.Builder(name)
    L = sp["L"]
    r0, r1 = sp["r"]
    ctrl, radii = [], []
    for i in range(5):
        f = i / 4
        r = r0 + (r1 - r0) * f
        ctrl.append(Vector((-L / 2 + L * f, 0.05 * math.sin(f * 5 + sp["seed"]), G + r * 0.78)))
        radii.append(r)
    tr = lk.Trunk(ctrl, radii, seed=sp["seed"], sides=36, step=0.16, flare=0.12, flare_len=0.6, lump=0.08,
                  knots=[(rnd.uniform(0.8, L - 0.8), rnd.uniform(0, 6.28), 0.12) for _ in range(3)])
    tr.build(b, bark, under, ragged=(False, True), rnd=rnd)
    tr.cap(b, rim, 1, "break", rnd)
    lk.moss_cover(b, tr, moss, amount=sp["moss"] + 0.3, thick=0.04, seed=sp["seed"], fade=0.3)
    # The mouth: a lip of rotten wood round a dark tunnel running back into the trunk
    c, T, S, U, r = tr.frame(0.0)
    n = tr.sides
    mr = b.mesh(rim)
    md = b.mesh(dark)
    mr.begin(c)
    md.begin(c)
    outer = [tr.rings[0][k][0] for k in range(n)]
    inner_r = 0.64
    lip = []
    for k in range(n):
        a = k / n * math.tau
        jitter = 1.0 + 0.07 * math.sin(3 * a + 1.3) + rnd.uniform(-0.03, 0.03)
        p = c + (S * math.cos(a) + U * math.sin(a)) * r * inner_r * jitter - T * 0.02
        lip.append(p)
    ov = [mr.v(p, (p - c).length) for p in outer]
    iv = [mr.v(p, (p - c).length) for p in lip]
    for k in range(n):
        k1 = (k + 1) % n
        mr.f((ov[k1], ov[k], iv[k], iv[k1]), False)
    depth = 2.0
    steps = 8
    rowsd = []
    for j in range(steps + 1):
        s = depth * j / steps
        cj, Tj, Sj, Uj, rj = tr.frame(s)
        shrink = 1.0 - 0.45 * (j / steps) ** 1.5
        row = []
        for k in range(n):
            a = k / n * math.tau
            jitter = 1.0 + 0.08 * math.sin(3 * a + 1.3 + j) + 0.04 * math.sin(7 * a + 2 * j)
            p = cj + (Sj * math.cos(a) + Uj * math.sin(a)) * rj * inner_r * shrink * jitter
            row.append(md.v(p, 0.3 + 0.2 * j))
        rowsd.append(row)
    for A, B_ in zip(rowsd, rowsd[1:]):
        for k in range(n):
            k1 = (k + 1) % n
            md.f((A[k1], A[k], B_[k], B_[k1]), True)
    cj = tr.frame(depth)[0]
    cv = md.v(cj, 0.0)
    for k in range(n):
        md.f((rowsd[-1][(k + 1) % n], rowsd[-1][k], cv), True)
    # Hollow lip through to the rotted, scooped outer rim: leave outer lip ring as is (it joins the bark ring)
    # Ferns flanking the mouth, mushrooms, fungus, litter
    mouth = c - T * 0.35
    ferns = []
    for sgn, away in ((1.0, 70.0), (-1.0, -70.0), (1.0, 150.0), (-1.0, -150.0), (0.3, 180.0)):
        ferns.append((mouth.x + rnd.uniform(-0.2, 0.15), mouth.y + sgn * (r * 0.75 + rnd.uniform(0.0, 0.25)) * (1 if abs(sgn) > 0.5 else 0.2), G, away))
    lk.ferns(b, fern_mat, ferns, rnd, big=1.1)
    lk.shelf_tiers(b, cap, pores, tr, rnd, [(rnd.uniform(0.6, L - 0.6), rnd.choice((rnd.uniform(160, 200), rnd.uniform(-20, 20))), rnd.randint(2, 3)) for _ in range(4)],
                   rad=(0.08, 0.13))
    for k in range(6):
        a = math.radians(rnd.choice((rnd.uniform(110, 175), rnd.uniform(5, 70), rnd.uniform(180, 215))))
        p, nrm = tr.surface(rnd.uniform(0.3, L - 0.3), a)
        lk.mushroom(b, mcap, mpores, mstem, p + nrm * 0.01, rnd.uniform(0.04, 0.09), rnd.uniform(0.03, 0.05), rnd)
    lk.litter(b, litter, 40, rnd, (-L / 2 - 0.8, L / 2 + 0.6, -1.4, 1.4))
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    extra = tr.capsules(spacing=1.2, shrink=0.85, rmin=0.1)
    density = {"HtBarkUnder": 0.2, "HtBark": 1.5, "HtMoss": 1.5, "HtRim": 0.7, "HtDark": 0.3, "HtFern": 0.3, "FungusTop": 1.0,
               "FungusPores": 0.5, "MushCap": 0.5, "MushPores": 0.3, "MushStem": 0.4, "Litter": 0.25}
    model = lk.export(name, pieces, [], FEATURES, size=lk.atlas_size(), density=density, extra=extra, rect=True)
    lk.preview(name.lower(), model, [
        ("a", (-L * 1.2, -3.8, 2.2), (0.0, 0.0, 0.6)),
        ("mouth", (-3.4, -1.2, 1.1), (-1.8, 0.0, 0.7)),
        ("b", (L * 0.6, -3.0, 2.0), (0.0, 0.0, 0.6)),
    ], floor=1.0)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
