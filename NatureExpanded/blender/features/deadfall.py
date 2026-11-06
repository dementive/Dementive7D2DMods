"""DeadfallPile01 (pine forest), DeadfallPile02 (burnt forest): a heap of storm-broken limbs and branches piled against
a standing dead snag, bracket fungus and moss on the old wood. A good wood source. Solid: the snag, the thick limbs
and a hidden core under the heap.

    blender -b --factory-startup --python deadfall.py -- <features folder> <preview folder> [Name ...]
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

lk.AXIS = "z"
G = fk.G
FEATURES, PREVIEWS = fk.args()
lk.set_preview_dir(PREVIEWS)
ONLY = lk.only()

SPECS = {
    "DeadfallPile01": dict(style="forest", moss=0.6, peel=0.58, seed=3, limbs=62, fungus=4, snag=3.0),
    "DeadfallPile02": dict(style="burnt", moss=0.0, peel=0.7, seed=5, limbs=52, fungus=0, snag=2.7),
}


def build(name):
    sp = SPECS[name]
    nk.reset()
    rnd = random.Random(sp["seed"] * 53 + 1)
    kw = dict(style=sp["style"], moss=sp["moss"], bs=0.9, peel=sp["peel"])
    bark = lk.bark_mat("DfBark", **kw)
    wood = lk.end_grain("DfWood", "burnt" if sp["style"] == "burnt" else "bleached", 0.008)
    snag_bark = lk.bark_mat("DfSnag", **dict(kw, bs=0.45))
    dead = nk.plant("DfDeadNeedle", (0.13, 0.07, 0.03), (0.09, 0.05, 0.025), rough=0.8, vary=0.3)
    cap, pores = lk.fungus_materials()
    fern = nk.plant("DfFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    b = ks.Builder(name)
    extra = []
    H = sp["snag"]
    ctrl = [Vector((0.0, 0.0, G - 0.4)), Vector((0.06, 0.0, G + H * 0.5)), Vector((0.0, 0.06, G + H))]
    tr = lk.Trunk(ctrl, [0.44, 0.34, 0.2], seed=sp["seed"], sides=24, step=0.3, flare=0.3, flare_len=1.0)
    tr.build(b, snag_bark, None, ragged=(False, True), rnd=rnd)
    tr.cap(b, wood, 1, "break", rnd)
    extra += tr.capsules(spacing=1.4, shrink=0.8, rmin=0.1, s0=0.3)
    # Limbs leaning on the snag and heaped round it
    placed = []
    for i in range(sp["limbs"]):
        a = rnd.uniform(0, math.tau)
        ring = rnd.uniform(0.7, 2.0) * (1.0 if i % 3 else 0.6)
        p0 = Vector((math.cos(a) * ring, math.sin(a) * ring, G + 0.04))
        lean = rnd.random() < 0.45
        if lean:
            h = rnd.uniform(0.7, H * 0.7)
            tgt = Vector((0.0, 0.0, G + h))
            d = (tgt - p0)
            ln = d.length * rnd.uniform(1.0, 1.25)
            d.normalize()
            d = (d + Vector((rnd.gauss(0, 0.12), rnd.gauss(0, 0.12), 0.0))).normalized()
        else:
            ln = rnd.uniform(1.3, 3.0)
            d = Vector((-math.cos(a) + rnd.gauss(0, 0.5), -math.sin(a) + rnd.gauss(0, 0.5), rnd.uniform(0.05, 0.4))).normalized()
        r0 = rnd.uniform(0.035, 0.1) * (1.3 if lean and ln > 2.5 else 1.0)
        pts = lk.limb(b, bark, wood, p0, d, ln, r0, r0 * 0.45, rnd, sides=6, kink=0.035, bend=(0.0, 0.0, -0.03))
        placed.append((pts, r0))
        if rnd.random() < 0.6:
            for j in range(rnd.randint(2, 4)):
                k = rnd.randint(1, len(pts) - 2)
                dd = (pts[k + 1] - pts[k]).normalized()
                _, u, v = ks.basis(dd)
                aa = rnd.uniform(0, math.tau)
                dd = (dd * 0.6 + (u * math.cos(aa) + v * math.sin(aa)) * 0.8).normalized()
                sub = lk.limb(b, bark, wood, pts[k], dd, rnd.uniform(0.3, 0.9), r0 * 0.4, 0.012, rnd, sides=4, kink=0.05, bend=(0.0, 0.0, -0.1))
                if sp["style"] != "burnt" and rnd.random() < 0.5:
                    lk.needles(b, dead, sub, rnd, spacing=0.05, length=0.1, width=0.014, spread=1.0, skip=0.1)
        if r0 > 0.065 and ln > 2.0:
            extra.append("capsule %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (pts[1].x, pts[1].y, max(pts[1].z, G + 0.05), pts[-2].x, pts[-2].y,
                                                                         max(pts[-2].z, G + 0.05), r0 * 0.55))
    if sp["fungus"]:
        lk.shelf_tiers(b, cap, pores, tr, rnd, [(rnd.uniform(0.6, 2.4), rnd.uniform(0, 360), 2) for _ in range(sp["fungus"])], rad=(0.07, 0.12))
    ferns = []
    for k in range(3 if sp["style"] != "burnt" else 0):
        a = rnd.uniform(0, math.tau)
        ferns.append((math.cos(a) * 1.9, math.sin(a) * 1.9, G, math.degrees(a)))
    lk.ferns(b, fern, ferns, rnd)
    # A hidden core so the heap can't be walked through between the thin limbs
    core = fk.Rock(radii=(1.25, 1.2, 0.55), height=0.95, seed=11, power=2.4, rough=0.1, subdiv=3).build()
    body = ([v.co.copy() for v in core.verts], [tuple(v.index for v in f.verts) for f in core.faces])
    core.free()
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"DfSnag": 1.3, "DfBark": 1.0, "DfWood": 0.4, "DfDeadNeedle": 0.3, "DfFern": 0.3, "FungusTop": 1.0, "FungusPores": 0.5}
    model = lk.export(name, pieces, [body], FEATURES, size=lk.atlas_size(), density=density, extra=extra, rect=False, voxel=0.2)
    lk.preview(name.lower(), model, [
        ("a", (-5.5, -5.5, 3.2), (0.0, 0.0, 1.3)),
        ("b", (3.5, -2.5, 2.2), (0.0, 0.0, 1.0)),
    ], floor=1.0)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
