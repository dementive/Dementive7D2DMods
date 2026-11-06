"""GiantStump01 (weathered forest), GiantStumpBurnt01 (charred), GiantStumpBleached01 (grey bleached, wasteland): the
stump of a giant tree, 2.2 to 2.5 m across, 1.7 to 2.4 m high, flat sawn top with growth rings and weathering checks,
two springboard notches, buttress roots flaring into the ground, bracket fungus, a fir seedling on top of the forest
one. Solid: two crossed boxes (an octagon) with a flat top, a perch.

    blender -b --factory-startup --python giant_stump.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Vector
from mathutils import noise as mn

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
    "GiantStump01": dict(style="forest", R=1.08, H=2.1, moss=1.0, peel=0.6, seed=3, seedling=True, fungus=3, top="fresh", ring=0.011),
    "GiantStumpBurnt01": dict(style="burnt", R=1.12, H=2.35, moss=0.0, peel=0.7, seed=5, seedling=False, fungus=0, top="burnt", ring=0.011),
    "GiantStumpBleached01": dict(style="bleached", R=0.98, H=1.8, moss=0.0, peel=0.7, seed=7, seedling=False, fungus=0, top="bleached", ring=0.009),
}


def build(name):
    sp = SPECS[name]
    nk.reset()
    rnd = random.Random(sp["seed"] * 31 + 5)
    R0, H = sp["R"], sp["H"]
    style = sp["style"]
    kw = dict(style=style, moss=sp["moss"], bs=0.45, peel=sp["peel"])
    bark = lk.bark_mat("StBark", **kw)
    moss = lk.moss_shell_mat("StMoss", **kw) if sp["moss"] > 0 else None
    top = lk.end_grain("StTop", sp["top"], sp["ring"])
    wood = lk.end_grain("StWood", "burnt" if style == "burnt" else "bleached" if style == "bleached" else "fresh", 0.012)
    cap, pores = lk.fungus_materials()
    mcap, mpores, mstem = lk.mushroom_materials()
    fern_mat = nk.plant("StFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    fir_mat = nk.plant("StFir", (0.045, 0.095, 0.03), (0.07, 0.14, 0.04), rough=0.7, vary=0.3)
    litter = lk.litter_materials()
    b = ks.Builder(name)
    SIDES = 56
    ph = rnd.uniform(0, 6.28)
    notches = [(math.radians(a0), 1.25 + 0.15 * i) for i, a0 in enumerate((rnd.uniform(20, 50), rnd.uniform(200, 235)))]
    pith = (0.1, -0.06)

    def notch_depth(z, a):
        d = 0.0
        for na, nz in notches:
            da = abs(math.atan2(math.sin(a - na), math.cos(a - na)))
            if da < 0.17 and nz - 0.02 <= z <= nz + 0.2:
                d = max(d, 0.2)
        return d

    def radius(z, a):
        e = math.exp(-max(z + 0.4, 0.0) / 0.45)
        lobes = 0.5 + 0.5 * math.cos(6 * a + ph + 1.5 * mn.noise(Vector((z * 0.6, a, 0.0))))
        r = R0 * (1.0 - 0.07 * (z / H)) * (1.0 + 0.4 * e * lobes)
        q = Vector((z * 2.0, math.cos(a) * R0 * 3.0 + 4.0, math.sin(a) * R0 * 3.0))
        r *= 1.0 + 0.045 * mn.noise(q) + 0.02 * mn.noise(q * 4.0)
        return r - notch_depth(z, a)

    zs = [-0.4] + [i * 0.075 for i in range(0, int(H / 0.075) + 1)]
    zs[-1] = H
    m = b.mesh(bark)
    mw = b.mesh(wood)
    m.begin((0, 0, G))
    mw.begin((0, 0, G))
    b.lod = 2
    grid = []
    for z in zs:
        row = []
        for k in range(SIDES):
            a = k / SIDES * math.tau
            r = radius(z, a)
            p = Vector((math.cos(a) * r, math.sin(a) * r, G + z))
            row.append([p, None, None])
        grid.append(row)
    for i in range(len(zs) - 1):
        if G + zs[i + 1] < G + 0.0:
            continue
        for k in range(SIDES):
            k1 = (k + 1) % SIDES
            quad = (grid[i][k], grid[i][k1], grid[i + 1][k1], grid[i + 1][k])
            ang = [k / SIDES * math.tau, k1 / SIDES * math.tau]
            innotch = any(notch_depth(zs[i + j], ang[c]) > 0 for j in (0, 1) for c in (0, 1))
            mesh, idx = (mw, 2) if innotch else (m, 1)
            vs = []
            for q in quad:
                if q[idx] is None:
                    c = Vector((0.0, 0.0, q[0].z))
                    q[idx] = mesh.v(q[0], (q[0] - c).length if innotch else 0.5)
                vs.append(q[idx])
            mesh.f(vs, True)
    b.lod = 0
    # The sawn top: concentric rings of vertices, uneven by a few millimeters, `t` = distance from the pith
    mt = b.mesh(top)
    mt.begin((0, 0, G + H))
    rings = 9
    toprows = [[mt.v(Vector((pith[0] * 0.0, pith[1] * 0.0, G + H + 0.004)), 0.0)]]
    last = grid[-1]
    for j in range(1, rings + 1):
        f = j / rings
        row = []
        for k in range(SIDES):
            p0 = last[k][0]
            p = Vector((p0.x * f, p0.y * f, G + H + 0.004 + 0.012 * (1.0 - f) * mn.noise(Vector((p0.x * f * 2.0, p0.y * f * 2.0, 3.0))) * 0.0))
            row.append(mt.v(p, (Vector((p.x - pith[0], p.y - pith[1], 0.0))).length))
        toprows.append(row)
    for k in range(SIDES):
        mt.f((toprows[0][0], toprows[1][k], toprows[1][(k + 1) % SIDES]), False)
    for A, B in zip(toprows[1:], toprows[2:]):
        for k in range(SIDES):
            k1 = (k + 1) % SIDES
            mt.f((A[k], B[k], B[k1], A[k1]), False)
    # Moss cushions: low on the flare, up the north side, along the top edge
    if moss is not None:
        mm = b.mesh(moss)
        mm.begin((0, 0, G))
        shell = {}

        def depth(i, k):
            z = zs[i]
            a = k / SIDES * math.tau
            q = Vector((z * 1.6 + 5.0, math.cos(a) * 2.2, math.sin(a) * 2.2))
            mask = 0.45 + 0.9 * mn.noise(q) + 0.3 * mn.noise(q * 3.0) + 0.5 * max(0.0, math.sin(a)) * 0.4
            mask += 0.55 * math.exp(-max(z, 0.0) / 0.5) + 0.5 * math.exp(-max(H - z, 0.0) / 0.25)
            d = max(0.0, min(1.0, (mask - 0.55) / 0.3))
            return d * (0.012 + 0.035 * max(0.0, 0.5 + 0.7 * mn.noise(q * 6.0)))

        def vert(i, k):
            if (i, k) not in shell:
                p = grid[i][k][0]
                d = depth(i, k)
                out = Vector((p.x, p.y, 0.0)).normalized()
                shell[(i, k)] = mm.v(p + out * (d + 0.0015 if d > 0.0 else -0.006), min(1.0, d / 0.03))
            return shell[(i, k)]

        for i in range(1, len(zs) - 1):
            for k in range(SIDES):
                k1 = (k + 1) % SIDES
                cs = ((i, k), (i, k1), (i + 1, k1), (i + 1, k))
                if max(depth(a, c) for a, c in cs) < 0.004:
                    continue
                if any(notch_depth(zs[a], c / SIDES * math.tau) > 0 for a, c in cs):
                    continue
                mm.f([vert(a, c) for a, c in cs], True)
    # Fungus on the sides, ferns and mushrooms at the foot
    def surf(z, a):
        r = radius(z, a)
        return Vector((math.cos(a) * r, math.sin(a) * r, G + z)), Vector((math.cos(a), math.sin(a), 0.0))

    for g in range(sp["fungus"]):
        a0 = rnd.uniform(0, math.tau)
        z0 = rnd.uniform(0.4, H - 0.5)
        for j in range(rnd.randint(2, 3)):
            a = a0 + rnd.uniform(-0.1, 0.1)
            z = z0 + 0.22 * j
            p, out = surf(z, a)
            if notch_depth(z, a) > 0:
                continue
            rr = rnd.uniform(0.09, 0.15) * (1 - 0.12 * j)
            ks.shelf_fungus(b, cap, pores, p - out * 0.03, out, rr, rnd, thickness=rr * 0.3, depth=0.85, segs=8)
    fs = []
    for k in range(4 if style == "forest" else 0):
        a = rnd.uniform(0, math.tau)
        p, out = surf(0.0, a)
        fs.append((p.x + out.x * 0.3, p.y + out.y * 0.3, G, math.degrees(a)))
    lk.ferns(b, fern_mat, fs, rnd, big=1.0)
    if style == "forest":
        for k in range(6):
            a = rnd.uniform(0, math.tau)
            z = rnd.uniform(0.0, 0.6)
            p, out = surf(z, a)
            lk.mushroom(b, mcap, mpores, mstem, p + out * 0.01, rnd.uniform(0.04, 0.09), rnd.uniform(0.03, 0.05), rnd)
    if sp["seedling"]:
        lk.fir_sapling(b, fir_mat, bark, Vector((0.35, 0.28, G + H + 0.01)), 0.75, rnd, lean=0.1, branches=4)
        lk.fir_sapling(b, fir_mat, bark, Vector((-0.5, 0.2, G + H + 0.01)), 0.3, rnd, lean=0.15, branches=4)
    lk.litter(b, litter, 40, rnd, (-1.4, 1.4, -1.4, 1.4), keep=lambda x, y: x * x + y * y > (R0 * 1.15) ** 2)
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    # Colliders: two crossed squares make an octagon inside the stump; the notches are shallow
    rc = R0 * 0.8
    side = rc * math.sqrt(2.0)
    hz = (H + 0.25) / 2.0
    cz = G + H - hz + 0.0
    extra = ["box 0 0 %.3f %.3f %.3f %.3f 1 0 0 0 1 0 0 0 1" % (cz, side, side, H + 0.25 - 0.0)]
    c45, s45 = math.cos(math.pi / 4), math.sin(math.pi / 4)
    extra.append("box 0 0 %.3f %.3f %.3f %.3f %.4f %.4f 0 %.4f %.4f 0 0 0 1" % (cz, side, side, H + 0.25, c45, s45, -s45, c45))
    density = {"StBark": 1.5, "StMoss": 1.4, "StTop": 1.3, "StWood": 0.4, "StFern": 0.3, "StFir": 0.4,
               "FungusTop": 1.0, "FungusPores": 0.5, "MushCap": 0.5, "MushPores": 0.3, "MushStem": 0.4, "Litter": 0.25}
    model = lk.export(name, pieces, [], FEATURES, size=lk.atlas_size(), density=density, extra=extra, rect=False)
    lk.preview(name.lower(), model, [
        ("a", (-5.0, -5.5, 3.0), (0.0, 0.0, 0.8)),
        ("b", (4.0, -2.0, 4.2), (0.0, 0.0, 1.2)),
        ("close", (-1.6, -2.2, 1.6), (0.0, 0.0, 1.2)),
    ], floor=1.0)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
