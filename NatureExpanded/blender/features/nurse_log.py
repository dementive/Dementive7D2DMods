"""NurseLog01, NurseLog02, NurseLogSnow01 (pine forest, burnt forest edges): a rotting log 5 to 9 m long buried in
moss, a row of young firs, hemlock seedlings and ferns growing out of its back, bracket fungus up the sides, boletes
in the crevices. Solid: a chain of capsule colliders, sunk so its back is about 0.8 m up, a balance beam.

    blender -b --factory-startup --python nurse_log.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys
from types import SimpleNamespace

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

# firs / hemlocks: (position along the log 0..1, height m); ferns: positions
SPECS = {
    "NurseLog01": dict(L=6.6, r=(0.5, 0.36), seed=2, snow=0.0, firs=[(0.1, 0.9), (0.24, 0.5), (0.38, 1.35), (0.52, 0.7), (0.66, 0.4), (0.8, 1.05)],
                       hemlocks=[(0.17, 0.3), (0.31, 0.22), (0.45, 0.35), (0.59, 0.26), (0.73, 0.3), (0.9, 0.2)], ferns=[0.05, 0.33, 0.6, 0.85]),
    "NurseLog02": dict(L=8.6, r=(0.55, 0.38), seed=4, snow=0.0, firs=[(0.15, 0.55), (0.6, 1.1), (0.82, 0.45)],
                       hemlocks=[(0.08, 0.4), (0.22, 0.3), (0.3, 0.45), (0.4, 0.28), (0.5, 0.38), (0.68, 0.33), (0.74, 0.25), (0.9, 0.35)],
                       ferns=[0.12, 0.28, 0.45, 0.55, 0.72, 0.88, 0.95]),
    "NurseLogSnow01": dict(L=6.0, r=(0.46, 0.34), seed=6, snow=0.9, firs=[(0.18, 0.8), (0.4, 1.2), (0.62, 0.6), (0.82, 0.95)],
                           hemlocks=[(0.3, 0.25), (0.5, 0.3), (0.72, 0.22)], ferns=[]),
}


def build(name):
    sp = SPECS[name]
    nk.reset()
    rnd = random.Random(sp["seed"] * 97 + 3)
    snow = sp["snow"]
    kw = dict(style="forest", moss=1.25, bs=0.45, peel=0.56, snow=snow)
    bark = lk.bark_mat("NlBark", **kw)
    under = lk.bark_mat("NlBarkUnder", **dict(kw, moss=0.0, snow=0.0))
    moss = lk.moss_shell_mat("NlMoss", **kw)
    end = lk.end_grain("NlEnd", "rot", 0.012)
    wood = lk.end_grain("NlWood", "fresh", 0.012)
    cap, pores = lk.fungus_materials()
    mcap, mpores, mstem = lk.mushroom_materials()
    fern_mat = nk.plant("NlFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    gc = (0.04, 0.085, 0.07) if snow else (0.045, 0.095, 0.03)
    fir_mat = nk.plant("NlFir", gc, tuple(c * 1.5 for c in gc), rough=0.7, vary=0.3)
    hem_mat = nk.plant("NlHemlock", (0.07, 0.125, 0.04), (0.1, 0.17, 0.05), rough=0.7, vary=0.3)
    litter = lk.litter_materials()
    b = ks.Builder(name)
    L = sp["L"]
    r0, r1 = sp["r"]
    n = max(4, int(L / 1.3))
    ctrl, radii = [], []
    ph = rnd.uniform(0, 6.28)
    for i in range(n + 1):
        f = i / n
        x = -L / 2 + L * f
        r = r1 + (r0 - r1) * (1.0 - f) ** 0.9
        ctrl.append(Vector((x, 0.12 * math.sin(f * 4.0 + ph) + 0.05 * math.sin(f * 11), G + r * 0.6 + 0.06 * math.sin(f * 6 + ph))))
        radii.append(r)
    tr = lk.Trunk(ctrl, radii, seed=sp["seed"], sides=36, step=0.16, flare=0.25, flare_len=0.9,
                  knots=[(rnd.uniform(1.0, L - 1.0), rnd.uniform(0, 6.28), rnd.uniform(0.06, 0.14)) for _ in range(4)], lump=0.1)
    tr.build(b, bark, under, ragged=(True, True), rnd=rnd)
    tr.cap(b, end, 0, "break", rnd)
    tr.cap(b, end, 1, "break", rnd)
    lk.moss_cover(b, tr, moss, amount=1.3, thick=0.055, seed=sp["seed"], fade=0.6)
    # Rotten branch nubs
    for k in range(7):
        s = rnd.uniform(0.6, L - 0.6)
        a = math.radians(rnd.choice((rnd.uniform(20, 160), rnd.uniform(-30, 20), rnd.uniform(160, 210))))
        p, nrm = tr.surface(s, a)
        lk.limb(b, bark, wood, p - nrm * 0.04, nrm + Vector((0, 0, 0.1)), rnd.uniform(0.08, 0.3), 0.04, 0.025, rnd, sides=5)
    # The row on its back
    for f, h in sp["firs"]:
        s = f * L
        p, nrm = tr.surface(s, math.radians(90 + rnd.uniform(-22, 22)))
        lk.fir_sapling(b, fir_mat, bark, p + Vector((0, 0, 0.02)), h, rnd, lean=0.1, branches=4)
    for f, h in sp["hemlocks"]:
        s = f * L
        p, nrm = tr.surface(s, math.radians(90 + rnd.uniform(-45, 45)))
        lk.fir_sapling(b, hem_mat, bark, p + Vector((0, 0, 0.02)), h, rnd, lean=0.18, droop=0.5, branches=5, spread=1.2)
    fs = []
    for f in sp["ferns"]:
        s = f * L
        a = math.radians(rnd.choice((rnd.uniform(60, 120), rnd.uniform(30, 60), rnd.uniform(120, 150))))
        p, nrm = tr.surface(s, a)
        fs.append((p.x, p.y, p.z + 0.0, math.degrees(math.atan2(nrm.y, nrm.x))))
    lk.ferns(b, fern_mat, fs, rnd, big=0.9)
    # Ground ferns by the log
    gf = []
    for k in range(4):
        s = rnd.uniform(0.5, L - 0.5)
        c, T, S, U, r = tr.frame(s)
        side = rnd.choice((-1, 1))
        gf.append((c.x + S.x * side * (r + 0.3), c.y + S.y * side * (r + 0.3), G, math.degrees(math.atan2(S.y * side, S.x * side))))
    lk.ferns(b, fern_mat, gf, rnd, big=1.0)
    spots = [(rnd.uniform(0.8, L - 0.8), rnd.choice((rnd.uniform(160, 200), rnd.uniform(-20, 20))), rnd.randint(2, 3)) for _ in range(5)]
    lk.shelf_tiers(b, cap, pores, tr, rnd, spots, rad=(0.07, 0.12))
    for k in range(7):
        s = rnd.uniform(0.4, L - 0.4)
        a = math.radians(rnd.choice((rnd.uniform(110, 175), rnd.uniform(5, 70), rnd.uniform(180, 215))))
        p, nrm = tr.surface(s, a)
        out = Vector((nrm.x, nrm.y, 0.0)).normalized() if abs(nrm.z) < 0.9 else Vector((0, 1, 0))
        lk.mushroom(b, mcap, mpores, mstem, p + nrm * 0.01, rnd.uniform(0.04, 0.09), rnd.uniform(0.03, 0.05), rnd)
    lk.litter(b, litter, 40, rnd, (-L / 2 - 0.5, L / 2 + 0.5, -1.3, 1.3))
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    extra = tr.capsules(spacing=1.6, shrink=0.84, rmin=0.1)
    density = {"NlBarkUnder": 0.2, "NlBark": 1.4, "NlMoss": 1.6, "NlEnd": 0.5, "NlWood": 0.5, "NlFern": 0.3, "NlFir": 0.45, "NlHemlock": 0.45,
               "FungusTop": 1.0, "FungusPores": 0.5, "MushCap": 0.5, "MushPores": 0.3, "MushStem": 0.4, "Litter": 0.25}
    model = lk.export(name, pieces, [], FEATURES, size=lk.atlas_size(), density=density, extra=extra, rect=True)
    lk.preview(name.lower(), model, [
        ("a", (-L * 0.9, -4.5, 2.4), (0.0, 0.0, 0.5)),
        ("b", (L * 0.45, -2.6, 1.5), (0.0, 0.0, 0.7)),
        ("close", (-0.5, -1.6, 1.4), (0.2, 0.0, 0.7)),
        ("top", (0.0, -1.0, 11.0), (0.0, 0.0, 0.0)),
    ])
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
