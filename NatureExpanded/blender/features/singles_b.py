"""Single finds, set B: BrokenCooler, ShoppingCart, RustyBucketCans, FirewoodStack, AbandonedPack, RustedBicycle.
Small weathered things abandoned for years and half swallowed by the ground and the weeds (see SPEC_singlesB.md).

    blender -b --factory-startup --python singles_b.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import singlekit as sk  # noqa: E402
from singlekit import G, clamp, smoothstep, emit, sweep, box, xform, warp, euler_matrix, body_of, tube_loop  # noqa: E402
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

FEATURES, PREVIEWS = fk.args()
ONLY = lk.only()


def obb(center, size, m3):
    """A collider line for a box of `size` with axes the columns of rotation matrix `m3`."""
    u, v, w = m3.col[0], m3.col[1], m3.col[2]
    return "box %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f %.3f" % (
        center[0], center[1], center[2], size[0], size[1], size[2], u[0], u[1], u[2], v[0], v[1], v[2], w[0], w[1], w[2])


def put(bms, matrix, sink=0.01, ref=0):
    """Transforms the bmeshes by `matrix`, then lowers them together so bmesh `ref` rests `sink` below the ground."""
    for bm in bms:
        xform(bm, matrix)
    dz = (G - sink) - min(v.co.z for v in bms[ref].verts)
    for bm in bms:
        bmesh.ops.translate(bm, vec=(0.0, 0.0, dz), verts=bm.verts)
    return dz


def soil_patches(b, soil, rnd, spots):
    for x, y, r, dome in spots:
        ks.ground_patch(b, soil, (x, y), r, rnd, sides=16, dome=dome, jitter=0.3, sink=0.03, rings=3)


def leaves(b, mats, rnd, area, count, keep=None):
    b.lod = 1
    n = tries = 0
    while n < count and tries < count * 30:
        tries += 1
        x, y = rnd.uniform(area[0], area[1]), rnd.uniform(area[2], area[3])
        if keep and not keep(x, y):
            continue
        n += 1
        a = rnd.uniform(0, math.tau)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.05, 0.1)))
        ks.leaf(b, rnd.choice(mats), (x, y, G + 0.004), d, rnd.uniform(0.05, 0.085), rnd.uniform(0.03, 0.05), bend=-0.1, fold=0.3,
                profile="oval", rows=2, roll=rnd.uniform(-20, 20))
    b.lod = 0


# ================================================================ RustyBucketCans

def bucket_parts(rnd, mat_body):
    H, Rt, Rb, rh = 0.27, 0.139, 0.112, 0.048
    ph = rnd.uniform(0, 6.0)

    def outer_r(z):
        r = Rb + (Rt - Rb) * (z / H)
        r += 0.0035 * math.exp(-((z - 0.095) / 0.008) ** 2) + 0.0035 * math.exp(-((z - 0.165) / 0.008) ** 2)
        return r

    prof = [(rh, 0.0), (Rb - 0.03, 0.0), (Rb - 0.012, 0.0), (Rb - 0.004, 0.005), (Rb, 0.016)]
    z = 0.028
    while z < H - 0.016:
        prof.append((outer_r(z), z))
        z += 0.0115
    prof += [(Rt + 0.0045, H - 0.011), (Rt + 0.0058, H - 0.005), (Rt + 0.0045, H + 0.0005), (Rt + 0.0005, H + 0.002),
             (Rt - 0.0035, H - 0.001), (Rt - 0.0045, H - 0.006)]
    z = H - 0.016
    while z > 0.02:
        prof.append((outer_r(z) - 0.004, z))
        z -= 0.034
    prof += [(Rb - 0.012, 0.0085), (Rb - 0.03, 0.0045), (rh, 0.0045)]

    def ring(u, z, k, a):
        if u is None:
            return Vector((0.0, 0.0, z))
        if abs(u - rh) < 1e-6:
            jag = 1.0 + 0.5 * mn.noise(Vector((math.cos(a) * 1.4 + ph, math.sin(a) * 1.4, 0.4))) + 0.16 * math.sin(5.0 * a + ph)
            u = u * max(0.45, jag)
            z = z + 0.006 * mn.noise(Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, ph)))
        return Vector((u * math.cos(a), u * math.sin(a), z))

    bm = sweep(prof, ring, 36)
    dents = [(rnd.uniform(0, math.tau), rnd.uniform(0.08, 0.2), rnd.uniform(0.012, 0.022), rnd.uniform(0.03, 0.05)) for _ in range(3)]
    dents.append((1.3, 0.28, 0.034, 0.05))  # the rim, bent in

    def deform(p):
        r = math.hypot(p.x, p.y)
        if r < 0.085:
            return p
        a = math.atan2(p.y, p.x)
        dd = 0.0
        for da, dz, amp, sig in dents:
            ang = math.atan2(math.sin(a - da), math.cos(a - da)) * r
            dd += amp * math.exp(-((ang / sig) ** 2 + ((p.z - dz) / (sig * 1.3)) ** 2))
        k = (r - dd) / r
        p = Vector((p.x * k, p.y * k * 0.97, p.z))
        # the whole thing a little out of round and sagging
        p += Vector((0.0, 0.0, -0.004 * math.sin(a * 2.0 + ph)))
        return p

    warp(bm, deform)
    # ears and the bail
    ears = []
    for sgn in (-1, 1):
        e = box((0.014, 0.006, 0.026), (sgn * (Rt - 0.001), 0.0, H - 0.028), bevel=0.0015)
        ears.append(e)
    pts = []
    for i in range(19):
        a = math.pi * i / 18.0
        pts.append(Vector((math.cos(a) * (Rt + 0.004), 0.0, H - 0.028 + math.sin(a) * (Rt + 0.004) * 1.0)))
    bail = tube_loop(pts, [0.0024] * len(pts), 5, closed=False)
    # flopped over to one side and kinked
    xform(bail, Matrix.Translation((0, 0, -(H - 0.028))))
    xform(bail, euler_matrix(rx=-112.0))
    xform(bail, Matrix.Translation((0, 0, H - 0.028)))
    for v in bail.verts:
        v.co += Vector((0.0, 0.0, 0.0))
    return bm, ears, bail, (H, Rt, Rb)


def can_profile(r, h, kind):
    prof = []
    if kind != "open":
        prof += [(None, 0.0016)]
    else:
        prof += [(None, 0.0016)]
    prof += [(r - 0.006, 0.0016), (r - 0.0045, 0.0), (r + 0.0012, 0.0), (r + 0.002, 0.005), (r + 0.0004, 0.0085)]
    prof += [(r, 0.02), (r - 0.0014, h * 0.33), (r - 0.0014, h * 0.36), (r, h * 0.39), (r, h * 0.6), (r - 0.0014, h * 0.63),
             (r - 0.0014, h * 0.66), (r, h * 0.69), (r, h - 0.012), (r + 0.0004, h - 0.0085), (r + 0.002, h - 0.005), (r + 0.0012, h)]
    if kind == "open":
        prof += [(r - 0.0012, h), (r - 0.0014, h - 0.012), (r - 0.0014, 0.012), (r - 0.007, 0.0045), (None, 0.0045)]
    else:
        prof += [(r - 0.0045, h), (r - 0.0062, h - 0.0045), (r - 0.009, h - 0.0045), (r - 0.0095, h - 0.003), (None, h - 0.003)]
    return prof


def make_can(rnd, r, h, kind, seed):
    prof = can_profile(r, h, kind)
    bm = sweep(prof, sk.lathe_ring(), 28)
    if kind == "open":
        # a ragged torn rim, the top edge cut and bent
        ph = rnd.uniform(0, 6.0)

        def jag(p):
            if p.z > h - 0.006:
                a = math.atan2(p.y, p.x)
                p.z += 0.0045 * mn.noise(Vector((math.cos(a) * 3.0 + ph, math.sin(a) * 3.0, 0.2))) - 0.0015 * max(0.0, math.sin(a * 4.0 + ph))
                rr = math.hypot(p.x, p.y)
                if rr > 1e-6:
                    k = 1.0 + 0.02 * mn.noise(Vector((math.cos(a) * 4.0, math.sin(a) * 4.0, ph)))
                    p.x *= k
                    p.y *= k
            return p
        warp(bm, jag)
    if kind == "crushed":
        ph = rnd.uniform(0, 6.0)

        def crush(p):
            q = Vector(p)
            squash = 0.34 + 0.12 * math.sin(p.z / h * 7.0 + ph)
            q.y *= squash
            q.x *= 1.0 + 0.45 * (1.0 - squash) * (0.4 + math.sin(p.z / h * 5.0 + ph * 0.5) * 0.5)
            q.z = p.z * (0.82 + 0.1 * math.sin(p.x / r * 2.0 + ph))
            q += Vector((0.0, 0.0, 0.0))
            q += Vector((sk.fbm3(p, 60.0, seed) * 0.008, sk.fbm3(p, 60.0, seed + 5) * 0.008, sk.fbm3(p, 45.0, seed + 9) * 0.01))
            # bend the can along its length
            q.x += 0.012 * math.sin(q.z * 40.0 + ph) + 0.35 * (q.z / h) ** 2 * 0.05
            return q
        warp(bm, crush)
    return bm


def can_label(r, h, rnd, gap_start, gap_span, seed):
    """A paper label wrapped round the can with a torn-away stretch of its circumference (angles gap_start..+span)."""
    bm = bmesh.new()
    n = 30
    z0, z1 = 0.0155, h - 0.0155
    rows = []
    a_start = gap_start + gap_span
    a_len = math.tau - gap_span
    for k in range(n + 1):
        a = a_start + a_len * k / n
        f = k / n
        # ragged torn ends and a few nibbled bites along the edges
        torn = 0.0
        e = min(f, 1.0 - f)
        if e < 0.12:
            torn = (0.12 - e) / 0.12 * (0.25 + 0.55 * (0.5 + 0.5 * mn.noise(Vector((a * 3.0, seed, 1.0)))))
        lo = z0 + (z1 - z0) * (torn * 0.5 + max(0.0, 0.22 * (mn.noise(Vector((a * 2.2, seed, 7.0)))) ))
        hi = z1 - (z1 - z0) * (torn * 0.4 + max(0.0, 0.2 * (mn.noise(Vector((a * 2.5, seed, 3.0))))))
        rr = r + 0.0009
        A = bm.verts.new((rr * math.cos(a), rr * math.sin(a), lo))
        B = bm.verts.new((rr * math.cos(a), rr * math.sin(a), hi))
        rows.append((A, B))
    for (A0, B0), (A1, B1) in zip(rows, rows[1:]):
        try:
            bm.faces.new((A0, A1, B1, B0))
        except ValueError:
            pass
    return bm


def build_bucket(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)))
    galv = sk.metal_mat("BcGalv", kind="galv", rust=0.38, white=0.5, scale=1.0, relief=0.0016)
    tin = sk.metal_mat("BcTin", kind="tin", rust=0.4, white=0.25, scale=1.2, relief=0.0012)
    rustdark = sk.metal_mat("BcWire", kind="wire", rust=0.8, white=0.1, scale=1.3, relief=0.0012)
    lab1 = sk.label_mat("BcLabelA", (0.17, 0.05, 0.03), (0.28, 0.12, 0.05))
    lab2 = sk.label_mat("BcLabelB", (0.07, 0.11, 0.05), (0.2, 0.2, 0.1))
    lab3 = sk.label_mat("BcLabelC", (0.05, 0.08, 0.14), (0.14, 0.17, 0.22))
    soil = lk.soil_mat("BcSoil", moss=0.15)
    mats_g = sk.grass_mats()
    dock_mat = nk.plant("BcDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)
    extra = []

    # --- the bucket, on its side with the base turned toward -y and up a little (so the hole shows)
    body, ears, bail, (H, Rt, Rb) = bucket_parts(rnd, galv)
    M = euler_matrix(rz=18.0, loc=(0.02, 0.02, 0.0)) @ euler_matrix(rx=-82.0, rz=0.0)
    # axis +z (base to rim) goes to +y tipped; mirror so the base faces toward -y/-x
    put([body] + ears + [bail], M, sink=0.025)
    emit(b, body, galv, lod=2, angle=48.0)
    for e in ears:
        emit(b, e, galv, lod=0)
    emit(b, bail, rustdark, lod=1, angle=70.0)
    c = Vector((0.0, 0.0, 0.0))
    for v in body.verts:
        c += v.co
    c /= len(body.verts)
    m3 = M.to_3x3()
    axis_z = (M.to_3x3() @ Vector((0, 0, 1)))
    extra.append(obb(c, (0.27, 0.27, 0.27), m3))

    # --- the cans
    specs = [
        ("closed", 0.0375, 0.108, lab1, (0.25, -0.17), 75.0, 90.0),     # intact, label half gone
        ("open", 0.0375, 0.108, lab2, (-0.2, -0.27), 20.0, 0.0),       # torn open, lid peeled back
        ("crushed", 0.0375, 0.108, None, (0.2, 0.3), 140.0, 0.0),
        ("closed", 0.0525, 0.037, lab3, (-0.04, -0.34), 200.0, 8.0),    # a squat tuna can
    ]
    for i, (kind, r, h, lab, (x, y), yaw, tilt) in enumerate(specs):
        bm = make_can(rnd, r, h, kind, i * 7)
        # centre the can on its own middle
        xform(bm, Matrix.Translation((0.0, 0.0, -h * 0.5)))
        parts = [bm]
        label = None
        if lab is not None:
            label = can_label(r, h, rnd, rnd.uniform(0, math.tau), rnd.uniform(1.0, 2.3), i + 3)
            xform(label, Matrix.Translation((0.0, 0.0, -h * 0.5)))
            parts.append(label)
        flap = None
        if kind == "open":
            # the lid: a thin disc, its half peeled back about a jagged chord
            lp = [(None, 0.0), (r - 0.0045, 0.0), (r - 0.0045, 0.0007), (None, 0.0007)]
            flap = sweep(lp, sk.lathe_ring(), 24)
            ph = rnd.uniform(0, 6.0)
            xh = 0.004

            def peel(p, ph=ph):
                xj = xh + 0.006 * mn.noise(Vector((p.y * 80.0 + ph, 0.0, 1.0)))
                if p.x > xj:
                    d = p.x - xj
                    ang = math.radians(128.0)
                    return Vector((xj + d * math.cos(ang), p.y, p.z + d * math.sin(ang)))
                return p
            warp(flap, peel)
            xform(flap, Matrix.Translation((0.0, 0.0, h - 0.0045 - h * 0.5)))
            parts.append(flap)
        if kind == "crushed":
            M2 = euler_matrix(rz=yaw, rx=rnd.uniform(-8, 8), ry=rnd.uniform(-8, 8), loc=(x, y, 0.0))
        elif kind == "open":
            M2 = euler_matrix(rz=yaw, ry=-14.0, loc=(x, y, 0.0)) @ euler_matrix(ry=0.0)
        else:
            M2 = euler_matrix(rz=yaw, loc=(x, y, 0.0)) @ euler_matrix(ry=tilt - rnd.uniform(-6, 6))
        dz = put(parts, M2, sink=0.012 if kind != "crushed" else 0.004)
        emit(b, bm, tin, lod=1 if i > 1 else 0, angle=50.0)
        if label is not None:
            emit(b, label, lab, lod=1, angle=70.0)
        if flap is not None:
            emit(b, flap, tin, lod=1, angle=70.0)
        cc = Vector((0.0, 0.0, 0.0))
        for v in bm.verts:
            cc += v.co
        cc /= len(bm.verts)
        sz = (2 * r, 2 * r, h) if kind != "crushed" else (0.09, 0.05, 0.08)
        extra.append(obb(cc, (sz[0] * 0.9, sz[1] * 0.9, sz[2] * 0.9), M2.to_3x3()))

    # --- soil, leaves, weeds
    b.lod = 0
    soil_patches(b, soil, rnd, [(0.06, 0.02, 0.22, 0.05), (0.27, -0.17, 0.1, 0.012), (-0.2, -0.27, 0.1, 0.015), (0.2, 0.3, 0.09, 0.012),
                                (-0.04, -0.34, 0.07, 0.012), (-0.32, 0.28, 0.12, 0.02)])
    leaves(b, leafm, rnd, (-0.4, 0.4, -0.4, 0.4), 16)
    for cx, cy, n, hgt in [(-0.3, 0.28, 14, 0.3), (0.32, 0.05, 9, 0.24), (-0.36, -0.05, 10, 0.26), (0.05, 0.38, 9, 0.22), (0.3, -0.36, 7, 0.2)]:
        sk.tuft(b, mats_g, rnd, (cx, cy), n, hgt, spread=0.06, limit=0.43)
    sk.dock(b, dock_mat, rnd, (-0.3, 0.28), leaves=6, length=0.16, width=0.06)
    sk.dock(b, dock_mat, rnd, (0.1, 0.34), leaves=5, length=0.13, width=0.05)

    density = {"BcGalv": 1.0, "BcTin": 0.9, "BcWire": 0.6, "BcLabel": 0.55, "BcSoil": 0.35, "GrassGreen": 0.3, "GrassDry": 0.3,
               "BcDock": 0.3, "LeafBrown": 0.2, "LeafGold": 0.2}
    sk.finish(name, b, [], FEATURES, PREVIEWS, 1024, density, extra=extra, views=sk.standard_views(0.3, reach=0.5))
    print("[%s] done" % name)


# ================================================================ BrokenCooler

def build_cooler(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)))
    hx, hy = 0.29, 0.18
    body_mat = sk.plastic_mat("CoolBody", (0.05, 0.1, 0.17), (0.2, 0.25, 0.28), crack=1.0, fade=0.85, dirt=1.6,
                              band=(G + 0.19, G + 0.245, (0.2, 0.045, 0.035), (0.3, 0.11, 0.08)))
    lid_mat = sk.plastic_mat("CoolLid", (0.27, 0.26, 0.21), (0.42, 0.41, 0.36), crack=1.0, fade=0.7, dirt=1.6)
    soil = lk.soil_mat("CoolSoil", moss=0.25)
    grass = sk.grass_mats()
    dock_mat = nk.plant("CoolDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)

    # --- the tub: a rounded-rectangle shell with thick walls, a lip and hand recesses in the ends
    prof = [(None, 0.0), (0.05, 0.0), (0.018, 0.004), (0.003, 0.022)]
    z = 0.07
    while z < 0.30:
        prof.append((0.0, z))
        z += 0.04
    prof += [(0.0, 0.318), (0.0035, 0.336), (0.022, 0.340), (0.028, 0.336), (0.029, 0.31)]
    z = 0.27
    while z > 0.07:
        prof.append((0.03, z))
        z -= 0.05
    prof += [(0.034, 0.05), (0.06, 0.036), (None, 0.034)]
    body = sweep(prof, sk.rrect_ring(hx, hy, 7.0), 44)

    def deform(p):
        x, y, z = p.x, p.y, p.z
        if abs(x) > 0.272 and 0.15 < z < 0.31 and abs(y) < 0.11:
            d = 0.022 * smoothstep(0.11, 0.078, abs(y)) * smoothstep(0.15, 0.195, z) * smoothstep(0.31, 0.272, z)
            x -= math.copysign(d, x)
        dd = math.hypot(x - 0.2, y + 0.17)
        if z > 0.27:
            z -= 0.055 * math.exp(-(dd / 0.055) ** 2) * smoothstep(0.27, 0.33, z)
        # sun-warped: the long walls bow a little
        x += 0.006 * math.sin(z * 9.0 + y * 3.0)
        y += 0.005 * math.sin(x * 6.0 + z * 4.0)
        return Vector((x, y, z))

    warp(body, deform)
    # --- the lid: a slab with a lip, its underside hollowed
    lprof = [(None, 0.081), (0.06, 0.079), (0.018, 0.073), (0.004, 0.063), (0.0, 0.05), (0.0, 0.012), (0.004, 0.0), (0.026, 0.0),
             (0.03, 0.005), (0.03, 0.046), (0.05, 0.056), (0.08, 0.06), (None, 0.062)]
    lid = sweep(lprof, sk.rrect_ring(hx + 0.002, hy + 0.002, 7.0), 44)
    T0 = Matrix.Translation((0.0, -(hy + 0.002), 0.0))
    Ml = Matrix.Translation((0.0, hy + 0.002, 0.341)) @ euler_matrix(rx=-112.0, ry=15.0) @ T0
    xform(lid, Ml)
    lugs = []
    for sx, hh in ((-1, 0.05), (1, 0.022)):
        lugs.append(box((0.07, 0.03, hh), (sx * 0.2, hy - 0.004, 0.335 - 0.005 + hh * 0.3), bevel=0.004))
    # --- dirt in the tub
    dirt = sk.blob((0.2, 0.105, 0.03), seed=4, power=2.2, rough=0.3, subdiv=3)
    xform(dirt, Matrix.Translation((0.01, 0.0, 0.05)))
    Mb = euler_matrix(rx=2.5, ry=-3.0, rz=24.0)
    dz = put([body, lid, dirt] + lugs, Mb, sink=0.03)
    emit(b, body, body_mat, lod=2, angle=44.0)
    emit(b, lid, lid_mat, lod=2, angle=44.0)
    for lg in lugs:
        emit(b, lg, body_mat, lod=0)
    emit(b, dirt, soil, lod=1, angle=70.0)

    def W(x, y, z):
        return Mb @ Vector((x, y, z)) + Vector((0.0, 0.0, dz))

    # --- litter in the tub, a weed growing out of the dirt, leaves and soil round the base
    b.lod = 1
    for i in range(14):
        p = W(rnd.uniform(-0.2, 0.2), rnd.uniform(-0.1, 0.1), 0.07 + rnd.uniform(0.0, 0.02))
        a = rnd.uniform(0, math.tau)
        ks.leaf(b, rnd.choice(leafm), p, Vector((math.cos(a), math.sin(a), rnd.uniform(0.0, 0.25))), rnd.uniform(0.05, 0.09),
                rnd.uniform(0.03, 0.05), bend=-0.1, fold=0.3, profile="oval", roll=rnd.uniform(-30, 30))
    b.lod = 0
    wc = W(0.1, 0.0, 0.07)
    sk.dock(b, dock_mat, rnd, (wc.x, wc.y, wc.z), leaves=6, length=0.2, width=0.06, lift=1.1)
    wc2 = W(-0.14, 0.03, 0.07)
    sk.tuft(b, grass, rnd, (wc2.x, wc2.y), 7, 0.3, spread=0.03, limit=0.44)
    soil_patches(b, soil, rnd, [(-0.2, -0.28, 0.14, 0.03), (0.28, 0.2, 0.12, 0.025), (-0.3, 0.2, 0.1, 0.02), (0.22, -0.3, 0.1, 0.02)])
    leaves(b, leafm, rnd, (-0.4, 0.4, -0.4, 0.4), 22)
    for cx, cy, n, hgt in [(-0.32, -0.2, 12, 0.3), (0.3, 0.1, 10, 0.26), (-0.3, 0.28, 10, 0.3), (0.05, -0.38, 8, 0.2), (0.34, -0.28, 8, 0.24)]:
        sk.tuft(b, grass, rnd, (cx, cy), n, hgt, spread=0.06, limit=0.44)
    c = W(0.0, 0.0, 0.17)
    extra = [obb(c, (0.58, 0.36, 0.34), Mb.to_3x3())]
    density = {"CoolBody": 1.0, "CoolLid": 0.9, "CoolSoil": 0.4, "GrassGreen": 0.3, "GrassDry": 0.3, "CoolDock": 0.3, "LeafBrown": 0.2,
               "LeafGold": 0.2}
    sk.finish(name, b, [], FEATURES, PREVIEWS, 1024, density, extra=extra, views=sk.standard_views(0.55, reach=0.6))
    print("[%s] done" % name)


# ================================================================ ShoppingCart

def resample(loop, m, closed=True):
    """`m` points spread evenly by arc length along a polyline (closed loops wrap)."""
    pts = [Vector(p) for p in loop] + ([Vector(loop[0])] if closed else [])
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    tot = sum(seg)
    out = []
    for k in range(m):
        s = tot * k / (m if closed else max(1, m - 1))
        i = 0
        while i < len(seg) - 1 and s > seg[i]:
            s -= seg[i]
            i += 1
        f = s / max(seg[i], 1e-9)
        out.append(pts[i].lerp(pts[i + 1], min(1.0, f)))
    return out


def subd(pts, maxlen, closed=False):
    out = []
    n = len(pts)
    for i in range(n if closed else n - 1):
        a, b_ = Vector(pts[i]), Vector(pts[(i + 1) % n])
        k = max(1, int(math.ceil((b_ - a).length / maxlen)))
        for j in range(k):
            out.append(a.lerp(b_, j / k))
    if not closed:
        out.append(Vector(pts[-1]))
    return out


def rounded_rect(x0, x1, y0, y1, z, rc=0.035):
    """A closed loop (counter-clockwise from above) round a rectangle with its corners cut, 12 points."""
    r = rc
    pts = [(x0 + r, y0), (x1 - r, y0), (x1 - 0.3 * r, y0 + 0.3 * r), (x1, y0 + r), (x1, y1 - r), (x1 - 0.3 * r, y1 - 0.3 * r),
           (x1 - r, y1), (x0 + r, y1), (x0 + 0.3 * r, y1 - 0.3 * r), (x0, y1 - r), (x0, y0 + r), (x0 + 0.3 * r, y0 + 0.3 * r)]
    return [Vector((px, py, z)) for px, py in pts]


def build_cart(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)))
    wire = sk.metal_mat("CartWire", kind="wire", rust=1.0, white=0.1, scale=1.3, relief=0.0009)
    hubm = sk.metal_mat("CartHub", kind="tin", rust=0.7, white=0.1, scale=1.2, relief=0.0009)
    plastic = sk.plastic_mat("CartPlastic", (0.16, 0.035, 0.028), (0.3, 0.14, 0.11), crack=0.9, fade=0.8)
    tire = sk.rubber_mat("CartTire", tone=(0.06, 0.06, 0.065))
    soil = lk.soil_mat("CartSoil", moss=0.2)
    grass = sk.grass_mats()
    dock_mat = nk.plant("CartDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)

    zb, zt = 0.40, 0.88
    bx, by0, by1 = 0.20, -0.30, 0.44
    tx, ty0, ty1 = 0.30, -0.38, 0.54

    def loop(t):
        return rounded_rect(-(bx + (tx - bx) * t), bx + (tx - bx) * t, by0 + (ty0 - by0) * t, by1 + (ty1 - by1) * t, zb + (zt - zb) * t)

    def damage(p):
        q = Vector(p)
        q.x += 0.035 * (q.z - 0.4)
        c = Vector((0.30, 0.52, 0.80))
        f = math.exp(-((q - c).length / 0.24) ** 2)
        q += Vector((-0.11, -0.13, -0.15)) * f
        c2 = Vector((-0.30, -0.12, 0.66))
        f2 = math.exp(-((q - c2).length / 0.17) ** 2)
        q += Vector((0.075, 0.0, -0.03)) * f2
        q += Vector((sk.fbm3(p, 7.0, 3) * 0.012, sk.fbm3(p, 7.0, 4) * 0.012, sk.fbm3(p, 7.0, 5) * 0.012))
        return q

    def frame_wob(p):
        q = Vector(p)
        q.x += 0.035 * (q.z - 0.4)
        q += Vector((sk.fbm3(p, 5.0, 8) * 0.006, sk.fbm3(p, 5.0, 9) * 0.006, 0.0))
        return q

    wires = []  # (points, radius, sides, closed, lod)

    def add(pts, r, sides, closed=False, lod=0, fn=damage, maxlen=0.1):
        pts = subd(pts, maxlen, closed)
        wires.append(([fn(p) for p in pts], r, sides, closed, lod))

    # rails round the basket
    for t, r, lod in ((0.0, 0.0028, 0), (0.22, 0.0026, 1), (0.44, 0.0026, 1), (0.66, 0.0026, 1), (0.84, 0.0026, 1), (1.0, 0.0042, 0)):
        lp = loop(t)
        if t in (0.44, 0.84):
            # a cut rail: the loop opened where it broke, the ends sprung outward
            i0 = rnd.randint(0, 11)
            pts = lp[i0 + 3:] + lp[:i0]
            add(pts, r, 4, False, lod)
        else:
            add(lp, r, 5 if t == 1.0 else 4, True, lod)
    # uprights
    m = 46
    pb, pt = resample(loop(0.0), m), resample(loop(1.0), m)
    for i in range(m):
        e = rnd.random()
        if e < 0.07:
            continue
        a, c = pb[i], pt[i]
        if e < 0.14:
            c = a.lerp(c, rnd.uniform(0.45, 0.8)) + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0.0))
        add([a, c], 0.0024, 4, False, 1, maxlen=0.14)
    # basket floor
    for k in range(9):
        x = -0.18 + 0.045 * k
        add([Vector((x, by0, zb)), Vector((x, by1, zb))], 0.0024, 4, False, 1, maxlen=0.2)
    for k in range(14):
        y = by0 + 0.0565 * k
        add([Vector((-bx, y, zb)), Vector((bx, y, zb))], 0.0024, 4, False, 1, maxlen=0.2)
    # lower tray
    for sx in (-1, 1):
        add([Vector((sx * 0.2, -0.32, 0.17)), Vector((sx * 0.2, 0.48, 0.17))], 0.0035, 4, False, 0, fn=frame_wob, maxlen=0.2)
    for k in range(13):
        y = -0.3 + 0.062 * k
        add([Vector((-0.2, y, 0.17)), Vector((0.2, y, 0.17))], 0.0024, 4, False, 1, fn=frame_wob, maxlen=0.2)
    # the frame: base loop, rear uprights to the handle, front legs to the basket, braces
    add(rounded_rect(-0.22, 0.22, -0.40, 0.50, 0.15, 0.03), 0.0052, 5, True, 0, fn=frame_wob, maxlen=0.12)
    for sx in (-1, 1):
        add([Vector((sx * 0.22, -0.40, 0.15)), Vector((sx * 0.255, -0.43, 0.55)), Vector((sx * 0.27, -0.46, 0.93))], 0.0055, 5,
            False, 0, fn=damage, maxlen=0.1)
        add([Vector((sx * 0.22, 0.50, 0.15)), Vector((sx * 0.205, 0.45, 0.41))], 0.005, 4, False, 0, fn=damage, maxlen=0.1)
        add([Vector((sx * 0.22, -0.18, 0.15)), Vector((sx * 0.195, -0.18, 0.40))], 0.0042, 4, False, 1, fn=damage, maxlen=0.1)
    # handle bar
    add([Vector((-0.27, -0.46, 0.93)), Vector((0.0, -0.475, 0.935)), Vector((0.27, -0.46, 0.93))], 0.0058, 5, False, 0, fn=damage, maxlen=0.07)
    # the child seat flap, hinged on the rear wall and hanging down crooked into the basket
    hz, hyy = 0.80, -0.325
    fl = [Vector((-0.2, hyy, hz)), Vector((0.2, hyy, hz)), Vector((0.19, hyy + 0.17, hz - 0.2)), Vector((-0.19, hyy + 0.2, hz - 0.17))]
    add(fl, 0.0028, 4, True, 1, fn=damage, maxlen=0.07)
    for k in (-0.1, 0.0, 0.1):
        add([Vector((k, hyy, hz)), Vector((k * 0.95, hyy + 0.185, hz - 0.185))], 0.0022, 4, False, 1, fn=damage, maxlen=0.1)

    bms = []
    for pts, r, sides, closed, lod in wires:
        bms.append((tube_loop(pts, [r] * len(pts), sides, closed=closed), lod))

    # wheels: three, the front one on the high side torn off (its bent bracket stays)
    wheels = []
    brk = []
    for sx in (-1, 1):
        for yy in (-0.40, 0.50):
            cx, cy = sx * 0.22, yy
            lost = (sx == -1 and yy > 0)
            top = Vector((cx, cy, 0.15))
            axle = Vector((cx + sx * 0.012, cy + (0.025 if lost else 0.0), 0.062 if not lost else 0.1))
            path = [frame_wob(p) for p in subd([top, Vector((cx, cy, 0.105)), axle], 0.04)]
            brk.append(tube_loop(path, [0.0042] * len(path), 4, closed=False))
            if not lost:
                wp = [(None, -0.014), (0.045, -0.014), (0.058, -0.009), (0.061, 0.0), (0.058, 0.009), (0.045, 0.014), (None, 0.014)]
                wb = sweep(wp, sk.lathe_ring(), 16)
                xform(wb, euler_matrix(ry=90.0, loc=(axle.x + sx * 0.008, axle.y, axle.z)))
                hubb = sweep([(None, -0.019), (0.017, -0.019), (0.017, 0.019), (None, 0.019)], sk.lathe_ring(), 10)
                xform(hubb, euler_matrix(ry=90.0, loc=(axle.x + sx * 0.008, axle.y, axle.z)))
                wheels.append((wb, hubb))
    # the grip: a plastic sleeve on the handle bar
    grip = tube_loop([Vector((-0.14, -0.476, 0.935)), Vector((0.14, -0.476, 0.935))], [0.0125, 0.0125], 8, closed=False)
    # --- the lying hull: a slab along the low side's wires
    hull = box((0.20, 0.82, 0.86), (0.2, 0.05, 0.50), bevel=0.01)

    # lie it on its +x side, a little crooked
    M = euler_matrix(rz=33.0) @ euler_matrix(ry=84.0)
    allb = [x[0] for x in bms] + [w for w, h in wheels] + [h for w, h in wheels] + brk + [grip, hull]
    for bm in allb:
        xform(bm, M)
    zlow = min(v.co.z for bm, _ in bms for v in bm.verts)
    cxs = [v.co.x for bm, _ in bms for v in bm.verts]
    cys = [v.co.y for bm, _ in bms for v in bm.verts]
    shift = Vector((-(max(cxs) + min(cxs)) * 0.5, -(max(cys) + min(cys)) * 0.5, (G - 0.06) - zlow))
    for bm in allb:
        bmesh.ops.translate(bm, vec=shift, verts=bm.verts)
    for bm, lod in bms:
        emit(b, bm, wire, lod=lod, angle=60.0)
    for bm in brk:
        emit(b, bm, wire, lod=0, angle=60.0)
    for wb, hubb in wheels:
        emit(b, wb, tire, lod=0, angle=50.0)
        emit(b, hubb, hubm, lod=1, angle=50.0)
    emit(b, grip, plastic, lod=0, angle=50.0)

    # --- soil mounded round the low side, weeds through the wires
    def Wp(x, y, z):
        return M @ Vector((x, y, z)) + shift

    spots = []
    for k in range(7):
        q = Wp(0.28, by0 + 0.1 + k * 0.12, 0.3 + rnd.uniform(0.0, 0.5))
        spots.append((q.x, q.y, rnd.uniform(0.18, 0.3), 0.03))
    soil_patches(b, soil, rnd, spots)
    leaves(b, leafm, rnd, (-1.0, 1.0, -0.9, 0.9), 40)
    for k in range(10):
        q = Wp(rnd.uniform(0.0, 0.25), rnd.uniform(-0.3, 0.45), rnd.uniform(0.35, 0.85))
        sk.tuft(b, grass, rnd, (q.x, q.y), rnd.randint(8, 13), rnd.uniform(0.3, 0.55), spread=0.1, limit=1.2)
    for k in range(5):
        q = Wp(0.26, rnd.uniform(-0.3, 0.4), rnd.uniform(0.3, 0.8))
        sk.dock(b, dock_mat, rnd, (q.x, q.y), leaves=6, length=0.24, width=0.08, limit=1.2)

    bodies = [body_of(hull)]
    density = {"CartWire": 1.0, "CartHub": 0.5, "CartPlastic": 0.5, "CartTire": 0.5, "CartSoil": 0.4, "GrassGreen": 0.3, "GrassDry": 0.3,
               "CartDock": 0.3, "LeafBrown": 0.2, "LeafGold": 0.2}
    sk.finish(name, b, bodies, FEATURES, PREVIEWS, 2048, density, voxel=0.06, limit=60, views=sk.standard_views(0.7, reach=0.9))
    print("[%s] done" % name)


# ================================================================ FirewoodStack

def log_section(rnd, R, kind):
    """The cross-section of a split log in the x-z plane: (points, tags) with tag 0 = bark edge, 1 = split face edge.
    The round (unsplit) log is all bark; half, third and quarter pieces have flat split faces."""
    def rr(a):
        return R * (1.0 + 0.06 * mn.noise(Vector((math.cos(a) * 2.0 + R * 40.0, math.sin(a) * 2.0, 1.7))))
    if kind == "round":
        n = 12
        pts = [(rr(a) * math.cos(a), rr(a) * math.sin(a)) for a in (k / n * math.tau for k in range(n))]
        return pts, [0] * n
    span = {"half": math.pi, "third": math.tau / 3.0, "quarter": math.pi / 2.0}[kind]
    n = {"half": 8, "third": 6, "quarter": 5}[kind]
    a0 = 0.0
    arc = []
    for k in range(n + 1):
        a = a0 + span * k / n
        arc.append((rr(a) * math.cos(a), rr(a) * math.sin(a)))
    px, pz = rnd.uniform(-0.1, 0.1) * R, rnd.uniform(-0.1, 0.1) * R
    if kind == "half":
        return arc, [0] * n + [1]
    pts = [(px, pz)] + arc
    tags = [1] + [0] * n + [1]
    return pts, tags


def split_log(rnd, R, L, kind, lay_name="tt"):
    pts, tags = log_section(rnd, R, kind)
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    stations = [0.0, 0.5, 1.0]
    rings = []
    ph = rnd.uniform(0, 6.0)
    for j, f in enumerate(stations):
        ring = []
        for (x, z) in pts:
            end_cut = 0.0
            if j in (0, 2):
                end_cut = 0.014 * mn.noise(Vector((x * 30.0 + ph, z * 30.0, j * 4.0))) + 0.012 * (x * 3.0 + z * 1.5) * (1 if j == 2 else -1)
            sx = 1.0 + 0.04 * math.sin(f * 3.1 + ph)
            ring.append(Vector((x * sx + 0.006 * math.sin(f * 4.0 + ph), (f - 0.5) * L + end_cut, z * sx)))
        rings.append(ring)
    bm = loft_rings_tagged(rings, tags)
    lay = bm.verts.layers.float.new(lay_name)
    for v in bm.verts:
        v[lay] = math.hypot(v.co.x - cx, v.co.z - cz) * 0.0 + math.hypot(v.co.x, v.co.z)
    return bm, lay, pts


def loft_rings_tagged(rings, tags):
    return sk.loft_rings(rings, tags, cap_tag=2)


def curl_strip(rnd, R, y0, y1, a0, span):
    """A strip of loosened bark curling away from the log between angles a0..a0+span (log frame, axis y)."""
    m = 6
    ys = [y0 + (y1 - y0) * k / 4 for k in range(5)]
    rings = []
    for yk, j in zip(ys, range(5)):
        env = math.sin(math.pi * j / 4.0) ** 0.6 + 0.12
        ring_o, ring_i = [], []
        for k in range(m + 1):
            s = k / m
            a = a0 + span * s
            lift = 0.004 + 0.034 * (s ** 1.8) * env
            ro = R + lift + 0.004
            ri = R + lift - 0.0005
            ring_o.append(Vector((ro * math.cos(a), yk, ro * math.sin(a))))
            ring_i.append(Vector((ri * math.cos(a), yk, ri * math.sin(a))))
        rings.append(ring_o + list(reversed(ring_i)))
    tags = [0] * m + [0] + [1] * m + [0]
    return sk.loft_rings(rings, tags, cap_tag=0)


def build_firewood(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) + 5)
    bark = sk.wood_mat("FwBark", style="forest", moss_low=1.0, peel=0.5, bs=1.0, sat=0.55, value=1.2)
    split = sk.wood_mat("FwSplit", style="bleached", moss_low=1.0, bs=1.0, sat=0.8)
    endm = sk.end_grain_old("FwEnd", 0.0065)
    cap, pores = lk.fungus_materials()
    mcap, mpores, mstem = lk.mushroom_materials()
    soil = lk.soil_mat("FwSoil", moss=0.3)
    grass = sk.grass_mats()
    dock_mat = nk.plant("FwDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)
    mats = [bark, split, endm]

    placed = []   # (x, z, r) of the stack's logs, for settling
    items = []    # (kind, R, L, x, y, z, yaw, pitch, roll, row)

    def drop(x, r):
        z = G + r - 0.035
        for px, pz, pr in placed:
            dx = x - px
            if abs(dx) < r + pr:
                z = max(z, pz + math.sqrt((r + pr) ** 2 - dx * dx))
        return z

    def kind_pick():
        r = rnd.random()
        return "half" if r < 0.45 else "quarter" if r < 0.75 else "third" if r < 0.88 else "round"

    rows = 7
    for j in range(rows):
        x = -0.5 + rnd.uniform(0.0, 0.03) + (j % 2) * 0.045
        xmax = 0.5 if j < 2 else 0.5 - (0.085 * (j - 1) ** 1.3) + rnd.uniform(-0.03, 0.03)
        if j >= rows - 2:
            xmax = min(xmax, -0.12 + rnd.uniform(0, 0.1))
        while True:
            kind = kind_pick()
            R = rnd.uniform(0.05, 0.082) if kind != "round" else rnd.uniform(0.032, 0.05)
            xc = x + R
            if xc + R > xmax:
                break
            z = drop(xc, R * 0.92)
            L = rnd.uniform(0.46, 0.54)
            edge = clamp((xc - (xmax - 0.16)) / 0.16)
            slump = edge * (j >= 2)
            items.append(dict(kind=kind, R=R, L=L, x=xc, y=rnd.uniform(-0.03, 0.03) + slump * rnd.uniform(0.0, 0.08), z=z - slump * 0.015,
                              yaw=rnd.gauss(0, 2.5) + slump * rnd.uniform(-22, 22), pitch=rnd.gauss(0, 1.5) + slump * rnd.uniform(-9, 9),
                              roll=rnd.uniform(0, 360), row=j))
            placed.append((xc, z, R * 0.92))
            x = xc + R + rnd.uniform(0.001, 0.01)
    main_count = len(items)
    # logs that came down in the collapse: onto the slumped end, then the ground
    for i in range(14):
        kind = kind_pick()
        R = rnd.uniform(0.045, 0.08) if kind != "round" else rnd.uniform(0.03, 0.045)
        xc = rnd.uniform(0.1, 0.95)
        yy = rnd.uniform(-0.05, 0.38) * (1 if i % 3 else -0.5)
        if abs(yy) < 0.07:
            z = drop(xc, R * 0.92)
            placed.append((xc, z, R * 0.92))
        else:
            z = G + R * 0.9 - 0.03
        items.append(dict(kind=kind, R=R, L=rnd.uniform(0.44, 0.54), x=xc, y=yy, z=z,
                          yaw=rnd.uniform(-70, 70) if abs(yy) >= 0.07 else rnd.uniform(-20, 20), pitch=rnd.uniform(-14, 14), roll=rnd.uniform(0, 360), row=9))
    for i in range(7):
        kind = kind_pick()
        R = rnd.uniform(0.045, 0.075) if kind != "round" else rnd.uniform(0.03, 0.045)
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(0.38, 0.8)
        items.append(dict(kind=kind, R=R, L=rnd.uniform(0.42, 0.52), x=max(-0.95, min(0.95, 0.3 + d * math.cos(a) * 1.4)),
                          y=max(-0.95, min(0.95, d * math.sin(a) * 1.6)), z=G + R * 0.9 - 0.035, yaw=rnd.uniform(0, 180), pitch=rnd.uniform(-5, 5),
                          roll=rnd.uniform(0, 360), row=10))

    for k, it in enumerate(items):
        bm, lay, pts = split_log(rnd, it["R"], it["L"], it["kind"])
        M = (Matrix.Translation((it["x"], it["y"], it["z"])) @ euler_matrix(rz=it["yaw"], rx=it["pitch"])
             @ Matrix.Rotation(math.radians(it["roll"]), 4, "Y"))
        curl = None
        if it["kind"] in ("half", "third", "round") and rnd.random() < 0.34:
            curl = curl_strip(rnd, it["R"], rnd.uniform(-0.2, -0.05), rnd.uniform(0.08, 0.22), rnd.uniform(0.2, 1.5) if it["kind"] != "round" else rnd.uniform(0, 5.0),
                              rnd.uniform(0.9, 1.4))
        xform(bm, M)
        emit(b, bm, None, lod=2 if it["row"] < 9 else 0, angle=38.0, mat_of=lambda f, mats=mats: mats[f.material_index], t=lambda v, lay=lay: v[lay])
        if curl is not None:
            xform(curl, M)
            emit(b, curl, None, lod=0, angle=38.0, mat_of=lambda f, mats=mats: mats[f.material_index], t=0.0)
            curl.free()

    # --- fungus, mushrooms, moss-green on the lowest row's ends
    low = sorted([it for it in items if it["row"] == 0], key=lambda it: it["x"])
    for it in low[:1] + low[-1:] + low[3:4]:
        side = -1 if it is low[0] else 1
        att = Vector((it["x"] + side * it["R"] * 0.9, it["y"], it["z"] + 0.01))
        ks.shelf_fungus(b, cap, pores, att, (side, 0.0, 0.0), rnd.uniform(0.05, 0.07), rnd, thickness=0.02, depth=0.8, segs=7)
    fl = [it for it in items if it["row"] == 10]
    for it in fl[:3]:
        att = Vector((it["x"] + 0.0, it["y"] + it["R"] * 0.5, it["z"] + it["R"] * 0.6))
        ks.shelf_fungus(b, cap, pores, att, (0.0, 1.0, 0.0), rnd.uniform(0.04, 0.06), rnd, thickness=0.016, depth=0.8, segs=7)
    for i in range(6):
        x, y = rnd.uniform(-0.6, 0.7), rnd.uniform(-0.38, -0.27)
        lk.mushroom(b, mcap, mpores, mstem, (x, y, G - 0.01), rnd.uniform(0.04, 0.07), rnd.uniform(0.025, 0.04), rnd)

    # --- soil, leaves, weeds
    b.lod = 0
    soil_patches(b, soil, rnd, [(x, -0.3, rnd.uniform(0.12, 0.2), 0.03) for x in (-0.6, -0.15, 0.3, 0.75)] + [(-0.5, 0.3, 0.15, 0.025), (0.5, 0.3, 0.2, 0.03)])
    leaves(b, leafm, rnd, (-1.2, 1.2, -1.2, 1.2), 50)
    for cx, cy, n, h in [(-0.7, -0.28, 14, 0.4), (-0.2, -0.3, 10, 0.3), (0.35, -0.3, 12, 0.35), (0.9, -0.1, 12, 0.45), (-0.78, 0.2, 12, 0.4),
                         (0.2, 0.33, 14, 0.5), (0.8, 0.5, 10, 0.4), (-0.4, 0.34, 9, 0.35), (0.0, -0.7, 8, 0.3)]:
        sk.tuft(b, grass, rnd, (cx, cy), n, h, spread=0.1, limit=1.3)
    sk.dock(b, dock_mat, rnd, (0.55, -0.36), leaves=7, length=0.26, width=0.09, limit=1.3)
    sk.dock(b, dock_mat, rnd, (-0.9, 0.3), leaves=6, length=0.22, width=0.08, limit=1.3)

    # --- the solid: an envelope under the main stack's tops
    xs = [-0.5 + 0.1 * i for i in range(11)]
    tops = []
    for xv in xs:
        h = G + 0.04
        for it in items[:main_count]:
            if abs(it["x"] - xv) < it["R"] * 0.8:
                h = max(h, it["z"] + it["R"] * 0.75)
        tops.append(h)
    # smooth, and keep under the logs
    tops = [min(tops[max(0, i - 1):i + 2]) - 0.025 for i in range(len(tops))]
    prof = [(xs[0], G - 0.08), (xs[-1], G - 0.08)] + [(xv, t_) for xv, t_ in reversed(list(zip(xs, tops)))]
    hull = sk.hull_prism(prof, -0.17, 0.17)
    bodies = [body_of(hull)]
    density = {"FwBark": 1.0, "FwSplit": 0.9, "FwEnd": 0.8, "FungusTop": 0.6, "FungusPores": 0.3, "MushCap": 0.4, "MushPores": 0.2, "MushStem": 0.4,
               "FwSoil": 0.4, "GrassGreen": 0.3, "GrassDry": 0.3, "FwDock": 0.3, "LeafBrown": 0.2, "LeafGold": 0.2}
    sk.finish(name, b, bodies, FEATURES, PREVIEWS, 2048, density, voxel=0.07, limit=80, views=sk.standard_views(0.9, reach=1.0))
    print("[%s] done" % name)


# ================================================================ AbandonedPack

def strap(path, width, thick, frays=None, rnd=None, pad=0.0):
    """A flat webbing strap along `path` (points near the ground): a closed solid, rectangular section. `frays` (0, 1 or 2
    ends) tears the ends raggedly."""
    pts = [Vector(p) for p in path]
    n = len(pts)
    rings = []
    for i, p in enumerate(pts):
        tan = (pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]).normalized()
        side = tan.cross(UPV).normalized()
        up = side.cross(tan).normalized()
        f = i / (n - 1)
        th = thick * (1.0 + pad * smoothstep(0.7, 0.2, f))
        w = width * (1.0 + 0.3 * pad * smoothstep(0.7, 0.2, f)) * 0.5
        ring = [p - side * w - up * th * 0.5, p + side * w - up * th * 0.5, p + side * w * 0.96 + up * th * 0.5, p - side * w * 0.96 + up * th * 0.5]
        if frays and rnd is not None:
            if (frays in (1, 3) and i == n - 1) or (frays in (2, 3) and i == 0):
                sgn = 1.0 if i == n - 1 else -1.0
                ring = [q + tan * sgn * rnd.uniform(-0.02, 0.012) for q in ring]
        rings.append(ring)
    return sk.loft_rings(rings, [0, 0, 0, 0], cap_tag=0)


UPV = Vector((0.0, 0.0, 1.0))


def build_pack(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) + 11)
    yaw = 25.0
    # --- the pack, lying on its back: body, the front pocket, the lid flap hanging open
    def sag(p):
        q = Vector(p)
        q.z = max(q.z, -0.062)
        q.z += 0.012 * math.sin(q.y * 24.0 + q.x * 7.0) + 0.01 * sk.fbm3(q, 9.0, 3)
        q.x += 0.05 * q.y * q.y * 3.0 - 0.02 * q.y
        return q

    body = sk.blob((0.155, 0.255, 0.088), seed=2, power=3.5, rough=0.1, subdiv=4, fn=sag)
    xform(body, Matrix.Translation((0.0, 0.0, G + 0.065)))
    pocket = sk.blob((0.115, 0.105, 0.04), seed=7, power=2.6, rough=0.12, subdiv=3)
    xform(pocket, euler_matrix(rx=-6.0, loc=(0.005, -0.1, G + 0.142)))
    lid = sk.blob((0.15, 0.115, 0.024), seed=12, power=3.0, rough=0.15, subdiv=3)
    xform(lid, euler_matrix(rx=-17.0, ry=3.0, loc=(0.01, 0.235, G + 0.176)))
    # --- the sleeping bag: a roll across the bottom end, wound layers at its ends
    rprof = [(None, -0.215), (0.05, -0.213), (0.068, -0.205), (0.075, -0.185), (0.079, -0.1), (0.081, 0.0), (0.079, 0.1), (0.075, 0.185),
             (0.068, 0.205), (0.05, 0.213), (None, 0.215)]
    roll = sweep(rprof, sk.lathe_ring(), 28)
    for f in roll.faces:
        f.material_index = 1 if (abs(f.calc_center_median().z) > 0.198 and len(f.verts) <= 4 and all(abs(v.co.z) > 0.19 for v in f.verts)) else 0
    lay = roll.verts.layers.float.new("tt")
    for v in roll.verts:
        v[lay] = math.hypot(v.co.x, v.co.y)

    def crumple(p):
        q = Vector(p)
        r = math.hypot(q.x, q.y)
        a = math.atan2(q.y, q.x)
        k = 1.0 + 0.045 * math.sin(q.z * 52.0 + a * 2.0) + 0.05 * sk.fbm3(q, 8.0, 5)
        q.x *= k
        q.y *= k * 0.9
        return q

    warp(roll, crumple)
    Mr = euler_matrix(ry=90.0, rz=0.0)
    xform(roll, euler_matrix(rz=7.0, loc=(0.0, -0.325, G + 0.062)) @ euler_matrix(ry=90.0))
    # --- the rope: two lashings round the roll, tied on top with the ends left hanging
    ropes = []
    for xk, ph in ((-0.125, 0.3), (0.12, 1.0)):
        path = []
        n = 36
        for i in range(n + 1):
            a = ph + (i / n) * (math.tau + 0.35)
            rr = 0.083 + 0.0045 + 0.002 * (i / n)
            path.append(Vector((xk + 0.012 * (i / n), rr * math.cos(a), rr * math.sin(a))))
        # the loose ends: down over the roll and onto the ground
        last = path[-1]
        for e in range(2):
            end = [last + Vector((0.0, 0.0, 0.0))]
            d = Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(0.7, 1.0), -0.6))
            for q in range(1, 8):
                end.append(end[-1] + d.normalized() * 0.025 + Vector((0.0, 0.0, -0.004 * q)))
            ropes.append(end)
        ropes.append(path)
    Mroll = euler_matrix(rz=7.0, loc=(0.0, -0.325, G + 0.062))
    # --- straps on the ground: one whole, one torn through
    s1 = strap([(0.13, 0.19, G + 0.045), (0.2, 0.2, G + 0.02), (0.27, 0.17, G + 0.011), (0.33, 0.1, G + 0.01), (0.36, 0.0, G + 0.01),
                (0.36, -0.08, G + 0.01)], 0.058, 0.014, frays=0, rnd=rnd, pad=0.7)
    s2 = strap([(-0.13, 0.19, G + 0.045), (-0.19, 0.22, G + 0.02), (-0.26, 0.25, G + 0.011), (-0.31, 0.24, G + 0.01)], 0.05, 0.012,
               frays=1, rnd=rnd, pad=0.7)
    s3 = strap([(-0.4, -0.02, G + 0.01), (-0.38, 0.06, G + 0.01), (-0.33, 0.14, G + 0.01), (-0.28, 0.19, G + 0.01)], 0.05, 0.011, frays=2, rnd=rnd)
    s4 = strap([(0.12, -0.2, G + 0.03), (0.18, -0.27, G + 0.012), (0.26, -0.31, G + 0.01), (0.33, -0.33, G + 0.01)], 0.04, 0.01, frays=0, rnd=rnd)
    buckle = box((0.045, 0.035, 0.012), (0.36, -0.12, G + 0.014), bevel=0.003)
    comp = []
    for yy in (-0.03, 0.115):
        pts_ = [(x_, yy, G + 0.163 - 0.075 * (x_ / 0.16) ** 2 + 0.01) for x_ in (-0.19, -0.1, 0.0, 0.1, 0.19)]
        comp.append(strap(pts_, 0.034, 0.008))
    threads = []
    for _ in range(9):
        p0 = Vector((-0.31, 0.24 + rnd.uniform(-0.02, 0.02), G + 0.012))
        d = Vector((rnd.uniform(0.4, 1.0), rnd.uniform(-0.5, 0.5), 0.1)).normalized()
        threads.append([p0, p0 + d * rnd.uniform(0.02, 0.05), p0 + d * rnd.uniform(0.04, 0.08) + Vector((0, 0, 0.003))])
    for _ in range(7):
        p0 = Vector((-0.28 + rnd.uniform(-0.01, 0.01), 0.19 + rnd.uniform(-0.02, 0.02), G + 0.012))
        d = Vector((rnd.uniform(-0.2, -1.0), rnd.uniform(-0.5, 0.5), 0.1)).normalized()
        threads.append([p0, p0 + d * rnd.uniform(0.02, 0.05), p0 + d * rnd.uniform(0.04, 0.08)])

    # tears in the canvas: on the up-facing surfaces of the pack
    cands = [v.co.copy() for v in body.verts if v.co.z > G + 0.12 and abs(v.co.x) < 0.12] + [v.co.copy() for v in pocket.verts if v.co.z > G + 0.16]
    tears = []
    for _ in range(40):
        c = rnd.choice(cands)
        if all((c - Vector(t[:3])).length > 0.14 for t in tears):
            tears.append((c.x, c.y, c.z, rnd.uniform(0.022, 0.04)))
        if len(tears) == 3:
            break
    # push the cloth in at the tears
    for bm in (body, pocket, lid):
        bm.normal_update()
        for v in bm.verts:
            for tx, ty, tz, tr in tears:
                d = (v.co - Vector((tx, ty, tz))).length
                if d < tr * 1.6:
                    v.co -= v.normal * 0.016 * math.exp(-(d / (tr * 0.9)) ** 2)

    Yt = euler_matrix(rz=yaw)
    tears = [tuple(Yt @ Vector(t[:3])) + (t[3],) for t in tears]
    canvas = sk.fabric_mat("PkCanvas", (0.07, 0.07, 0.04), (0.17, 0.16, 0.095), mould=0.9, dirt=0.9, tears=tears, weave=330.0)
    web = sk.webbing_mat("PkWeb", (0.05, 0.06, 0.04))
    bag = sk.fabric_mat("PkBag", (0.07, 0.025, 0.03), (0.17, 0.07, 0.07), mould=0.9, dirt=0.8, weave=420.0)
    bag_end = sk.layers_mat("PkBagEnd", (0.12, 0.05, 0.05), (0.06, 0.025, 0.03))
    rope = sk.rope_mat("PkRope", (0.2, 0.16, 0.1))
    plastic = sk.plastic_mat("PkBuckle", (0.04, 0.05, 0.035), (0.2, 0.2, 0.16), crack=0.9)
    soil = lk.soil_mat("PkSoil", moss=0.15)
    straw = nk.plant("PkStraw", (0.24, 0.2, 0.09), (0.15, 0.12, 0.05), rough=0.85, vary=0.3)
    grass = sk.grass_mats()
    dock_mat = nk.plant("PkDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)

    # the whole pack turned a little
    Y = euler_matrix(rz=yaw)
    allb = [body, pocket, lid, roll, s1, s2, s3, s4, buckle] + comp
    for bm in allb:
        xform(bm, Y)
    emit(b, body, canvas, lod=2, angle=60.0)
    emit(b, pocket, canvas, lod=2, angle=60.0)
    emit(b, lid, canvas, lod=2, angle=60.0)
    emit(b, roll, None, lod=2, angle=60.0, mat_of=lambda f: bag_end if f.material_index == 1 else bag, t=lambda v, lay=lay: v[lay])
    for s_ in (s1, s2, s3, s4) + tuple(comp):
        emit(b, s_, web, lod=1, angle=50.0)
    emit(b, buckle, plastic, lod=1)
    for th in threads:
        bm = tube_loop([Y @ p for p in th], [0.0014, 0.001, 0.0006], 3, closed=False)
        emit(b, bm, web, lod=1)
    for pts in ropes:
        wpts = [Y @ (Mroll @ p) if len(pts) > 9 else Y @ (Mroll @ p) for p in pts]
        sk.helix_rope(b, rope, wpts, 0.0042, rnd, strands=2, pitch=0.03, sides=3, lod=2, per_pitch=4)

    # --- the dent in the grass: flattened dead stalks lying radially, dark soil under the pack
    b.lod = 0
    soil_patches(b, soil, rnd, [(0.0, 0.0, 0.3, 0.004), (0.15, -0.1, 0.1, 0.012), (-0.2, 0.12, 0.08, 0.01)])
    for i in range(70):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.1, 0.27)
        x, y = r * math.cos(a), r * math.sin(a) * 0.9
        d = Vector((math.cos(a), math.sin(a), 0.03))
        sk.blade(b, straw if rnd.random() < 0.7 else grass[1], Vector((x, y, G + 0.003 + rnd.uniform(0, 0.012))), d, rnd.uniform(0.1, 0.17), 0.012, 0.12, rnd,
                 rows=2, fold=0.05, lod=1)
    leaves(b, leafm, rnd, (-0.44, 0.44, -0.44, 0.44), 14)
    for cx, cy, n, hgt in [(-0.36, -0.3, 12, 0.3), (0.34, 0.3, 10, 0.34), (-0.36, 0.33, 12, 0.32), (0.0, 0.4, 8, 0.25), (0.38, -0.36, 8, 0.25), (-0.1, -0.42, 8, 0.2)]:
        sk.tuft(b, grass, rnd, (cx, cy), n, hgt, spread=0.05, limit=0.46)
    sk.dock(b, dock_mat, rnd, (-0.36, 0.02), leaves=6, length=0.16, width=0.06)

    extra = [obb((0.0, -0.02, G + 0.075), (0.36, 0.78, 0.15), euler_matrix(rz=yaw).to_3x3())]
    density = {"PkCanvas": 1.0, "PkWeb": 0.7, "PkBag": 0.8, "PkBagEnd": 0.5, "PkRope": 0.5, "PkBuckle": 0.2, "PkSoil": 0.3, "PkStraw": 0.3,
               "GrassGreen": 0.3, "GrassDry": 0.3, "PkDock": 0.3, "LeafBrown": 0.2, "LeafGold": 0.2}
    sk.finish(name, b, [], FEATURES, PREVIEWS, 1024, density, extra=extra, views=sk.standard_views(0.2, reach=0.5))
    print("[%s] done" % name)


# ================================================================ RustedBicycle

def rot_about(point, axis, deg):
    """A matrix turning by `deg` about the line through `point` along `axis`."""
    return Matrix.Translation(point) @ Matrix.Rotation(math.radians(deg), 4, Vector(axis).normalized()) @ Matrix.Translation(-Vector(point))


def build_bike(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) + 3)
    frame_m = sk.metal_mat("BkFrame", kind="paint", paint=(0.05, 0.095, 0.135), paint2=(0.16, 0.2, 0.22), rust=0.7, flake=0.8, scale=1.1, relief=0.0012)
    steel_m = sk.metal_mat("BkSteel", kind="chrome", rust=0.95, scale=1.2, relief=0.0009)
    iron_m = sk.metal_mat("BkIron", kind="tin", rust=0.95, white=0.0, scale=1.0, relief=0.0009)
    tire_m = sk.rubber_mat("BkTire", tone=(0.045, 0.045, 0.048))
    grip_m = sk.rubber_mat("BkGrip", tone=(0.06, 0.055, 0.05))
    saddle_m = sk.leather_mat("BkSaddle")
    refl_m = sk.plastic_mat("BkPlastic", (0.17, 0.035, 0.03), (0.32, 0.15, 0.12), crack=1.0)
    soil = lk.soil_mat("BkSoil", moss=0.25)
    grass = sk.grass_mats()
    dock_mat = nk.plant("BkDock", (0.09, 0.15, 0.04), (0.14, 0.17, 0.05), rough=0.65, vary=0.3)
    leafm = sk.dead_leaf_mats()
    b = ks.Builder(name)

    parts = []   # (bmesh, material, lod, angle)
    front = []   # the same, the steering assembly

    def add(lst, bm, mat, lod=0, angle=55.0):
        lst.append([bm, mat, lod, angle])

    def tube(lst, pts, r, mat, sides=6, lod=0, closed=False):
        rr = r if isinstance(r, (list, tuple)) else [r] * len(pts)
        add(lst, tube_loop(pts, rr, sides, closed=closed), mat, lod)

    V = Vector
    RA, FA = V((0.0, 0.0, 0.33)), V((1.04, 0.0, 0.33))
    BB = V((0.43, 0.0, 0.27))
    ST = V((0.31, 0.0, 0.78))
    HTt, HTb = V((0.95, 0.0, 0.80)), V((0.925, 0.0, 0.66))
    # the diamond frame, a dent in the down tube
    tube(parts, [V((0.31, 0, 0.745)), V((0.63, 0, 0.765)), V((0.945, 0, 0.775))], 0.0155, frame_m)
    dt = [BB.lerp(HTb, k / 6.0) for k in range(7)]
    dt = [p + V((0, 0, -0.012 * math.exp(-((k - 3.0) / 0.9) ** 2))) + V((0, 0.0, 0)) for k, p in enumerate(dt)]
    tube(parts, dt, 0.0195, frame_m)
    tube(parts, [BB, ST], 0.0165, frame_m)
    tube(parts, [HTb, HTt], 0.0225, frame_m)
    for sy in (-1, 1):
        tube(parts, [BB + V((0, sy * 0.03, 0)), V((0.2, sy * 0.05, 0.3)), RA + V((0, sy * 0.06, 0))], 0.0115, frame_m)
        tube(parts, [ST + V((0, sy * 0.012, -0.08)), V((0.15, sy * 0.04, 0.56)), RA + V((0, sy * 0.06, 0.0))], 0.0095, frame_m)
    tube(parts, [BB + V((0, -0.06, 0)), BB + V((0, 0.06, 0))], 0.021, iron_m, sides=8)
    # seat post, saddle with its rails
    tube(parts, [ST + V((0, 0, -0.02)), ST + V((-0.02, 0, 0.12))], 0.0145, steel_m)
    sad = sk.blob((0.145, 0.08, 0.034), seed=3, power=2.3, rough=0.08, subdiv=3,
                  fn=lambda p: V((p.x, p.y * (1.0 - 0.55 * smoothstep(0.0, 0.145, p.x)), p.z - 0.02 * max(0.0, p.x) / 0.145 + 0.01 * (p.x < 0))))
    xform(sad, euler_matrix(ry=-8.0, loc=(0.33, 0.0, 0.945)))
    add(parts, sad, saddle_m, 2, 60.0)
    for sy in (-1, 1):
        tube(parts, [ST + V((-0.02, sy * 0.01, 0.115)), V((0.25, sy * 0.045, 0.915)), V((0.43, sy * 0.012, 0.925))], 0.0032, steel_m, sides=4)
    # cranks, chainring, pedal
    ca = math.radians(-35.0)
    for sy, pedal in ((1, True), (-1, False)):
        tip = BB + V((0.17 * math.sin(ca) * sy, sy * 0.075, -0.17 * math.cos(ca) * sy))
        tube(parts, [BB + V((0, sy * 0.06, 0)), BB + V((0, sy * 0.075, 0)), tip + V((0, 0, 0))], [0.0115, 0.0105, 0.0085], iron_m, sides=6)
        if pedal:
            pm_ = box((0.1, 0.05, 0.02), (0, 0, 0), bevel=0.003)
            xform(pm_, Matrix.Translation(tip + V((0.0, 0.03, 0.0))) @ euler_matrix(rz=8.0, ry=14.0))
            add(parts, pm_, iron_m, 1)
            tube(parts, [tip, tip + V((0, 0.018, 0))], 0.006, iron_m, sides=5)
        else:
            tube(parts, [tip, tip + V((0, -0.03, 0))], 0.0045, iron_m, sides=5)
    ring_n = 72
    rprof = [(0.066, -0.0025), (0.094, -0.0025), (0.094, 0.0025), (0.066, 0.0025)]
    ring = sweep(rprof, lambda u, z, k, a: V((u * (1.0 + (0.075 * ((k % 2) * 2 - 1) if u > 0.09 else 0.0)) * math.cos(a),
                                              u * (1.0 + (0.075 * ((k % 2) * 2 - 1) if u > 0.09 else 0.0)) * math.sin(a), z)), ring_n)
    xform(ring, euler_matrix(rx=90.0, loc=BB + V((0, 0.052, 0))))
    add(parts, ring, iron_m, 1)
    for k in range(5):
        a = k / 5 * math.tau + 0.4
        tube(parts, [BB + V((0.012 * math.cos(a), 0.052, 0.012 * math.sin(a))), BB + V((0.07 * math.cos(a), 0.052, 0.07 * math.sin(a)))], 0.0045, iron_m, sides=4, lod=1)
    # the chain: slack, drooping off the chainring
    cp = []
    cr, sr = 0.094, 0.04
    sc = V((0.0, 0.0, 0.33))
    c0 = V((BB.x, 0.0, BB.z))
    for k in range(10):
        a = math.radians(90.0 - 180.0 * k / 9.0)
        cp.append(c0 + V((cr * math.cos(a), 0, cr * math.sin(a))))
    p_a, p_b = c0 + V((0, 0, -cr)), sc + V((0, 0, -sr))
    for k in range(1, 6):
        f = k / 6.0
        cp.append(p_a.lerp(p_b, f) + V((0, 0, -0.055 * math.sin(math.pi * f))))
    for k in range(9):
        a = math.radians(-90.0 - 180.0 * k / 8.0)
        cp.append(sc + V((sr * math.cos(a), 0, sr * math.sin(a))))
    p_c, p_d = sc + V((0, 0, sr)), c0 + V((0, 0, cr))
    for k in range(1, 6):
        f = k / 6.0
        cp.append(p_c.lerp(p_d, f) + V((0, 0, -0.03 * math.sin(math.pi * f))))
    cpts = [p + V((0, 0.05, 0)) for p in cp]
    add(parts, tube_loop(cpts, [0.0045] * len(cpts), 4, closed=True, squash=0.5), iron_m, 1, 40.0)
    # rear wheel and front wheel (built at the origin in the x-z plane, axis y)

    def wheel(center, lst, taco=0.0, lost_spokes=(), phase=0.0):
        rimp = [(0.287, -0.0125), (0.298, -0.0145), (0.302, -0.011), (0.302, 0.011), (0.298, 0.0145), (0.287, 0.0125), (0.284, 0.0)]
        rim = sweep(rimp, sk.lathe_ring(), 56)
        tp = [(0.296, -0.0165), (0.314, -0.0235), (0.332, -0.019), (0.338, -0.008), (0.338, 0.008), (0.332, 0.019), (0.314, 0.0235), (0.296, 0.0165)]

        def tring(u, z, k, a):
            w = 1.0 + 0.012 * sk.noise3(V((math.cos(a) * 3.0, math.sin(a) * 3.0, 0.5)), 1.0, phase)
            return V((u * w * math.cos(a), u * w * math.sin(a), z))
        tire = sweep(tp, tring, 56)
        hub = sweep([(None, -0.05), (0.014, -0.05), (0.014, -0.036), (0.03, -0.034), (0.03, -0.03), (0.016, -0.03), (0.016, 0.03), (0.03, 0.03),
                     (0.03, 0.034), (0.014, 0.036), (0.014, 0.05), (None, 0.05)], sk.lathe_ring(), 14)
        for bm in (rim, tire, hub):
            xform(bm, euler_matrix(rx=90.0))
        spokes = []
        for side in (-1, 1):
            for i in range(18):
                if (side, i) in lost_spokes:
                    continue
                ha = i * math.tau / 18 + (side > 0) * math.pi / 18
                ra = ha + side * 1.05 + (0.5 * (side > 0))
                p0 = V((0.03 * math.cos(ha), side * 0.034, 0.03 * math.sin(ha)))
                p1 = V((0.284 * math.cos(ra), side * 0.006, 0.284 * math.sin(ra)))
                spokes.append(tube_loop([p0, p0.lerp(p1, 0.5), p1], [0.0011] * 3, 3, closed=False))
        allw = [rim, tire, hub] + spokes
        if taco:
            def fold(p):
                r = math.hypot(p.x, p.z)
                a = math.atan2(p.z, p.x)
                k = smoothstep(0.1, 0.3, r)
                dy = taco * math.cos(2.0 * (a - 0.9)) * k + 0.4 * taco * math.cos(3.0 * a + 1.0) * k * k
                d_in = -0.02 * taco / 0.05 * math.exp(-((a + 1.9) / 0.35) ** 2) * k
                return V((p.x * (1.0 + d_in), p.y + dy, p.z * (1.0 + d_in)))
            for bm in allw:
                warp(bm, fold)
        for bm in allw:
            xform(bm, Matrix.Translation(center))
        add(lst, rim, steel_m, 1)
        add(lst, tire, tire_m, 2, 50.0)
        add(lst, hub, iron_m, 1)
        for sp in spokes:
            add(lst, sp, steel_m, 1)

    wheel(RA, parts, 0.0, phase=1.0)
    # --- the steering assembly: fork, bars, grips, front wheel, turned hard over
    fk_pts = []
    for sy in (-1, 1):
        pts = [HTb + V((0.0, sy * 0.05, -0.02)), V((0.935, sy * 0.054, 0.5)), V((1.02, sy * 0.054, 0.4)), FA + V((0, sy * 0.05, 0))]
        tube(front, subd(pts, 0.1), 0.0125, frame_m)
    tube(front, [HTb + V((0, -0.052, -0.02)), HTb + V((0, 0.052, -0.02))], 0.012, frame_m, sides=5)
    tube(front, [HTt + V((0, 0, 0.0)), HTt + V((-0.015, 0, 0.12))], 0.011, steel_m)
    tube(front, [HTt + V((-0.015, 0, 0.115)), V((0.99, 0, 0.945))], [0.012, 0.012], steel_m)
    bar = []
    for k in range(15):
        s_ = -0.32 + 0.64 * k / 14.0
        bar.append(V((0.99 - 0.1 * (s_ / 0.32) ** 2 + 0.0, s_, 0.945 + 0.06 * (abs(s_) / 0.32) ** 2)))
    tube(front, bar, 0.0115, steel_m)
    for sy in (-1, 1):
        a_, b_ = bar[0 if sy < 0 else -1], bar[1 if sy < 0 else -2]
        d = (a_ - b_).normalized()
        tube(front, [a_ - d * 0.11, a_ + d * 0.01], 0.0165, grip_m, sides=8)
    for sy, off in ((-1, 0.0), (1, 0.1)):
        base = bar[3 if sy < 0 else -4]
        cab = [base, base + V((0.03, sy * 0.01, -0.06)), base + V((0.1, sy * 0.05, -0.22 - off)), base + V((0.25, sy * 0.08, -0.55 - off))]
        cab = [V((p.x, p.y, max(p.z, 0.03))) for p in subd(cab, 0.06)]
        tube(front, cab, 0.0022, grip_m, sides=4, lod=1)
    wheel(FA, front, taco=0.055, lost_spokes={(1, 2), (1, 3), (-1, 11), (-1, 12), (1, 9)}, phase=4.0)
    steer = rot_about(HTb, HTt - HTb, 44.0)
    for item in front:
        xform(item[0], steer)
    parts += front

    # --- the lying bicycle
    tilt = 75.0
    Mw = euler_matrix(rz=-28.0) @ euler_matrix(rx=tilt)
    for it in parts:
        xform(it[0], Mw)
    zlow = min(v.co.z for it in parts for v in it[0].verts)
    xs = [v.co.x for it in parts for v in it[0].verts]
    ys = [v.co.y for it in parts for v in it[0].verts]
    shift = V((-(max(xs) + min(xs)) * 0.5, -(max(ys) + min(ys)) * 0.5, (G - 0.05) - zlow))
    for it in parts:
        bmesh.ops.translate(it[0], vec=shift, verts=it[0].verts)
        emit(b, it[0], it[1], lod=it[2], angle=it[3])

    def Wp(p):
        return Mw @ V(p) + shift

    # the solid: a low stadium slab under the wheels and the frame between them
    c_mid = Wp(V((0.52, 0.0, 0.3)))
    hull = sweep([(None, G - 0.04), (0.0, G - 0.04), (0.0, G + 0.1), (None, G + 0.1)], sk.rrect_ring(0.78, 0.28, 3.0), 40)
    xform(hull, euler_matrix(rz=-28.0 + 0.0, loc=(c_mid.x, c_mid.y, 0.0)))
    # soil, weeds through the spokes
    spots = []
    for p in ((0.0, 0.0, 0.0), (1.04, 0.0, 0.0), (0.5, 0.0, 0.3), (0.95, 0.0, 0.9)):
        q = Wp(V(p))
        spots.append((q.x, q.y, rnd.uniform(0.2, 0.3), 0.03))
    soil_patches(b, soil, rnd, spots)
    leaves(b, leafm, rnd, (-1.1, 1.1, -0.8, 0.8), 40)
    for k in range(11):
        q = Wp(V((rnd.uniform(-0.2, 1.2), rnd.uniform(-0.04, 0.04), rnd.uniform(0.0, 0.6))))
        sk.tuft(b, grass, rnd, (q.x, q.y), rnd.randint(9, 14), rnd.uniform(0.3, 0.55), spread=0.1, limit=1.3)
    for k in range(5):
        q = Wp(V((rnd.uniform(0.0, 1.1), 0.0, rnd.uniform(0.0, 0.4))))
        sk.dock(b, dock_mat, rnd, (q.x, q.y), leaves=6, length=0.24, width=0.08, limit=1.3)
    bodies = [body_of(hull)]
    density = {"BkFrame": 1.0, "BkSteel": 0.8, "BkIron": 0.7, "BkTire": 0.8, "BkGrip": 0.3, "BkSaddle": 0.7, "BkPlastic": 0.2, "BkSoil": 0.4,
               "GrassGreen": 0.3, "GrassDry": 0.3, "BkDock": 0.3, "LeafBrown": 0.2, "LeafGold": 0.2}
    sk.finish(name, b, bodies, FEATURES, PREVIEWS, 2048, density, voxel=0.06, limit=60, views=sk.standard_views(0.5, reach=1.0))
    print("[%s] done" % name)


# ================================================================

BUILDERS = {
    "RustedBicycle": build_bike,
    "AbandonedPack": build_pack,
    "RustyBucketCans": build_bucket,
    "BrokenCooler": build_cooler,
    "ShoppingCart": build_cart,
    "FirewoodStack": build_firewood,
}


for n in (ONLY or list(BUILDERS)):
    BUILDERS[n](n)
