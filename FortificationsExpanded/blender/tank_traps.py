"""Tank Traps (Fortifications Expanded): welded scrap-steel anti-vehicle obstacles.

    TankTrapHedgehog.fbx       [DMG] Czech hedgehog, 2 x 2 footprint (X -1..1, Y -1..1), 1.8 m tall
    TankTrapHedgehogBent.fbx   the wrecked stage under it: bent, a leg folded, half sunk, about 1.6 m tall
    TankTrapLine.fbx           [DMG] hedgehog line, 3 wide x 1 deep (X -1.5..1.5, Y -0.5..0.5), 1.8 m tall
    TankTrapLineBent.fbx       its wrecked stage

Hedgehog: three rusty I-beams crossed at the middle and welded with gusset plates and fat beads; the feet cut level
to stand on the ground, the tops torch-cut at an angle. One beam keeps patches of olive paint, one of red-oxide
primer, one is bare rust. DMG1: scraped and gouged all over, one beam end dented, a cracked weld. DMG2: one arm bent
down, two welds torn open, a gusset sprung.

Line: three angle-iron crosses standing in a row, their feet welded onto an I-beam lying on the ground and their tops
welded under a channel top rail, each cross braced front and back with a raking strut down to a foot plate. DMG1:
scraped, the top rail dented, a cracked weld. DMG2: the +X cross buckled, its top welds torn, the rail bent down over
it, a strut torn off.

[DMG] files hold three meshes at the same origin, DMG0 (intact), DMG1 (worn) and DMG2 (breaking), plus an empty FX
(the front of the piece at mid-height); the Bent files hold one mesh, DMG0. One shared baked material, `TankTraps`
(2048 atlas), baked once from a kit; every piece is built from copies of the kit parts that keep their UVs.

    blender -b --factory-startup --python tank_traps.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default), export (no renders), kit (unbaked kit preview), beads (print weld positions)
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

Z0 = -0.5
MAT = "TankTraps"

# hedgehog geometry: three beams through C, feet at radius R on the ground, tops at radius R at z = ZT
HC = np.array([0.0, 0.0, 0.36])
HR = 0.9
HZT = 1.22
IB_H, IB_B, IB_TW, IB_TF = 0.16, 0.115, 0.01, 0.014
THETA = [0.0, 120.0, 240.0]  # feet; tops opposite
GUS_G = 0.4

# line geometry
LX = (-1.0, 0.0, 1.0)
LB_TOP = Z0 + 0.12  # top of the bottom beam
LR_BOT = 1.2  # underside of the top rail
LCROSS_Z = (LB_TOP + LR_BOT) / 2
LHALF = 0.42  # half-width of a cross at its ends


def log(*a):
    print("[tank_traps]", *a, flush=True)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def m_rot(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, axis))


def m_rot_axis(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, Vector(axis)))


def m_trans(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def m_scale(sx, sy, sz):
    return np.diag([sx, sy, sz, 1.0])


def m_frame(x, y, z, o):
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, o
    return m


def xf(V, M):
    return V @ M[:3, :3].T + M[:3, 3]


PERM_X = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # extrusion Z -> X, profile x -> Y, y -> Z


# ---------------------------------------------------------------- primitives

def extrude_z(profile, L, segs, caps=True):
    n = len(profile)
    V, F = [], []
    for k in range(segs + 1):
        z = L * k / segs
        V += [(x, y, z) for x, y in profile]
    for k in range(segs):
        for j in range(n):
            a, b = k * n + j, k * n + (j + 1) % n
            F.append((a, b, b + n, a + n))
    if caps:
        F.append(tuple(reversed(range(n))))
        F.append(tuple(segs * n + j for j in range(n)))
    return V, F


def lathe(prof, sides, phase=0.5, rnd=None, wobble=0.0):
    V, F, rings = [], [], []
    for r, z in prof:
        if r <= 1e-9:
            rings.append([len(V)] * sides)
            V.append((0.0, 0.0, z))
        else:
            ids = []
            for j in range(sides):
                a = 2 * math.pi * (j + phase) / sides
                rr = r * (1.0 + (rnd.uniform(-wobble, wobble) if rnd else 0.0))
                ids.append(len(V))
                V.append((rr * math.cos(a), rr * math.sin(a), z * (1.0 + (rnd.uniform(-wobble, wobble) if rnd else 0.0))))
            rings.append(ids)
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(sides):
            j1 = (j + 1) % sides
            q = []
            for v in (A[j], A[j1], B[j1], B[j]):
                if v not in q:
                    q.append(v)
            if len(q) >= 3:
                F.append(tuple(q))
    return V, F


def box_vf(sx, sy, sz, c=(0.0, 0.0, 0.0)):
    x, y, z = sx / 2, sy / 2, sz / 2
    V = [(c[0] + a * x, c[1] + b * y, c[2] + d * z) for a, b, d in
         ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return V, F


def frames(P):
    n = len(P)
    T = np.zeros_like(P)
    for i in range(n):
        d = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T[i] = d / max(np.linalg.norm(d), 1e-12)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    N = np.zeros_like(P)
    N[0] = unit(ref - T[0] * ref.dot(T[0]))
    for i in range(1, n):
        q = Vector(T[i - 1]).rotation_difference(Vector(T[i]))
        v = np.array(q @ Vector(N[i - 1]))
        v = v - T[i] * v.dot(T[i])
        N[i] = v / max(np.linalg.norm(v), 1e-12)
    return T, N, np.cross(T, N)


def sweep(points, r, sides, caps=False, rfn=None):
    P = np.array(points, float)
    T, N, B = frames(P)
    n = len(P)
    V, F = [], []
    for i in range(n):
        t = i / (n - 1)
        for j in range(sides):
            a = 2 * math.pi * j / sides
            rr = rfn(t, j) if rfn else r
            V.append(tuple(P[i] + rr * (math.cos(a) * N[i] + math.sin(a) * B[i])))
    for i in range(n - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            F.append((i * sides + j, i * sides + j1, (i + 1) * sides + j1, (i + 1) * sides + j))
    if caps:
        F.append(tuple(reversed(range(sides))))
        F.append(tuple((n - 1) * sides + j for j in range(sides)))
    return V, F


def chaikin(pts, it=2):
    P = [np.array(p, float) for p in pts]
    for _ in range(it):
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [a * 0.75 + b * 0.25, a * 0.25 + b * 0.75]
        Q.append(P[-1])
        P = Q
    return P


class Geo:
    def __init__(self):
        self.V, self.F, self.M = [], [], []

    def add(self, VF, mi=0, M=None, fmi=None):
        V, F = VF
        off = len(self.V)
        MM = None if M is None else (Matrix(M.tolist()) if isinstance(M, np.ndarray) else M)
        for v in V:
            p = Vector(v)
            self.V.append(tuple(MM @ p if MM is not None else p))
        for k, f in enumerate(F):
            self.F.append(tuple(i + off for i in f))
            self.M.append(fmi[k] if fmi is not None else mi)
        return self

    def obj(self, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        me.update()
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", np.array(self.M, np.int32))
        me.update()
        return tk.link(bpy.data.objects.new(name, me))


def set_attr(me, name, domain, kind, values):
    a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
    a.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", values)


# ---------------------------------------------------------------- profiles

def ibeam_profile(H, B, tw, tf, c=0.003):
    hb, hh = B / 2, H / 2
    return [(-hb + c, -hh), (hb - c, -hh), (hb, -hh + c), (hb, -hh + tf), (tw / 2, -hh + tf), (tw / 2, hh - tf),
            (hb, hh - tf), (hb, hh - c), (hb - c, hh), (-hb + c, hh), (-hb, hh - c), (-hb, hh - tf),
            (-tw / 2, hh - tf), (-tw / 2, -hh + tf), (-hb, -hh + tf), (-hb, -hh + c)]


def angle_profile(a, t, c=0.0025):
    """An equal angle with its heel at the origin, legs along +x and +y."""
    return [(0.0, 0.0), (a - c, 0.0), (a, c), (a, t), (t, t), (t, a), (c, a), (0.0, a - c)]


def channel_profile(w, h, t):
    """A channel in (u, v): web at u = -w/2 (the front), flanges reaching back to +w/2, v up."""
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, -h / 2 + t), (-w / 2 + t, -h / 2 + t), (-w / 2 + t, h / 2 - t),
            (w / 2, h / 2 - t), (w / 2, h / 2), (-w / 2, h / 2)]


def cut_member(profile, L, segs, n0, n1, rnd=None, jag=0.0):
    """A member extruded along +Z, its ends cut on planes through (0,0,0) with normal n0 and (0,0,L) with normal n1
    (local). Cut faces get material slot 1; jag roughens the far cut like a torch cut."""
    V, F = extrude_z(profile, L, segs)
    n = len(profile)
    V = [list(v) for v in V]
    for j in range(n):
        x, y = profile[j]
        V[j][2] = -(x * n0[0] + y * n0[1]) / n0[2]
        V[segs * n + j][2] = L - (x * n1[0] + y * n1[1]) / n1[2] + (rnd.uniform(-jag, jag) if rnd else 0.0)
    fmi = [0] * (len(F) - 2) + [1, 1]
    return (V, F), fmi


def bead_rfn(r0, L, pitch, seed, notch=None):
    rnd = random.Random(seed)
    jit = [rnd.uniform(-0.12, 0.12) for _ in range(64)]

    def f(t, j):
        s = t * L
        rip = 0.8 + 0.28 * abs(math.cos(math.pi * s / pitch)) ** 0.7
        taper = max(0.25, min(1.0, t / 0.07, (1.0 - t) / 0.07)) ** 0.5
        r = r0 * rip * taper * (1.0 + jit[(int(s / pitch * 2) + j) % 64] * 0.6)
        if notch is not None:
            r *= 1.0 - 0.7 * math.exp(-((t - notch) / 0.035) ** 2)
        return r
    return f


# ---------------------------------------------------------------- kit

KIT, META = [], {}


def kit_part(name, obj, split=40.0, pose=None):
    """Registers a part built in its own frame. pose: where it sits in the bake layout (its placement in a piece,
    so ground grime and rust streaks fall where they belong)."""
    if split:
        mod = obj.modifiers.new("Split", "EDGE_SPLIT")
        mod.split_angle = math.radians(split)
        mod.use_edge_sharp = False
        tk.apply_modifiers(obj)
    for p in obj.data.polygons:
        p.use_smooth = True
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    set_attr(me, "lco", "POINT", "FLOAT_VECTOR", co)
    set_attr(me, "kpart", "FACE", "INT", np.full(len(me.polygons), len(KIT), np.int32))
    obj.name = "Kit_" + name
    META[name] = dict(index=len(KIT), pose=np.eye(4) if pose is None else np.asarray(pose, float))
    KIT.append(obj)
    return obj


def hedgehog_frames():
    """Per beam: (frame matrix local -> world, length). Local x across the flanges (up the slope), y the depth
    (horizontal), z along the axis from the foot."""
    out = []
    for th in THETA:
        t = math.radians(th)
        foot = np.array([HR * math.cos(t), HR * math.sin(t), Z0])
        top = np.array([-HR * math.cos(t), -HR * math.sin(t), HZT])
        a = unit(top - foot)
        h = unit(np.cross([0.0, 0.0, 1.0], a))
        y = np.cross(a, h)
        # the web lies across (horizontal), the flanges face up and down the slope, so the gussets between the
        # beams meet the flange faces and their welds show
        out.append((m_frame(y, -h, a, foot), float(np.linalg.norm(top - foot))))
    return out


HFR = hedgehog_frames()
ALPHA = math.acos(float(HFR[0][0][2, 2]))  # beam angle from vertical


def build_kit():
    def paint(name, base, sat, value, tint, scr, patches, offset=(0.0, 0.0, 0.0), streaks=1.2):
        return tk.photo_material(name, base, scale=2.4, sat=sat, value=value, tint=tint, exposed="rust_coarse_01",
                                 chip=1.0, patches=patches, grime=0.9, streaks=streaks, offset=offset,
                                 metal_floor=0.35, rough_scale=0.85, grit=0.35, scratches=scr, edges=0.5 + 0.5 * scr,
                                 contrast=0.1)
    olive = [paint("K_Olive%s" % s, "green_metal_rust", 0.6, 0.85, (1.0, 0.93, 0.6), sc, 0.7) for s, sc in
             (("", 0.3), ("S", 1.0))]
    primer = [paint("K_Primer%s" % s, "rusty_painted_metal", 0.45, 0.6, None, sc, 0.7, (0.3, 0.6, 0.1)) for s, sc in
              (("", 0.3), ("S", 1.0))]
    bare = [tk.photo_material("K_Bare%s" % s, "rust_coarse_01", scale=2.6, value=0.85, exposed=None, grime=0.85,
                              streaks=1.0, metal_floor=0.3, rough_scale=0.9, grit=0.35, scratches=sc,
                              edges=0.4 + 0.6 * sc, contrast=0.12) for s, sc in (("", 0.3), ("S", 1.0))]
    plate = tk.photo_material("K_Plate", "metal_plate_02", scale=2.0, sat=0.4, value=0.7, exposed="rust_coarse_01",
                              chip=1.0, patches=0.7, grime=0.9, streaks=1.2, metal_floor=0.4, rough_scale=0.85,
                              grit=1.0, scratches=0.4, edges=0.8, contrast=0.1)
    cut = tk.photo_material("K_Cut", "rust_coarse_01", scale=5.0, sat=0.5, value=0.42, exposed=None, grime=0.5,
                            metal_floor=0.45, grit=0.6, bump=0.9)
    weld = tk.photo_material("K_Weld", "rust_coarse_01", scale=7.0, sat=0.9, value=0.38, exposed=None, grime=0.9,
                             metal_floor=0.25, grit=0.3, bump=1.2)
    crack = tk.grimy("K_Crack", (0.018, 0.014, 0.012), roughness=0.85, grime=0.3)
    fresh = tk.grimy("K_Fresh", (0.42, 0.41, 0.4), roughness=0.38, metallic=0.9, grime=0.35, stain=(0.25, 0.12, 0.05),
                     grit=0.3, dirt_range=(0.3, 0.1))
    soil = tk.grimy("K_Soil", (0.06, 0.038, 0.021), roughness=0.95, grime=0.45, grime_set="rust_coarse_01", scale=1.6,
                    bump_scale=30.0, bump=0.6, grit=0.0, stain=(0.034, 0.022, 0.012), dirt_range=(0.12, 0.03))

    # hedgehog beams: feet cut level with the ground, tops torch-cut at an angle (the upper flange longest)
    prof = ibeam_profile(IB_H, IB_B, IB_TW, IB_TF)
    n0 = (math.sin(ALPHA), 0.0, math.cos(ALPHA))
    n1 = (-math.sin(math.radians(32)), 0.0, math.cos(math.radians(32)))
    mats = [olive, primer, bare]
    for i in range(3):
        for v, suffix in ((0, ""), (1, "s")):
            rnd = random.Random(40 + i)
            VF, fmi = cut_member(prof, HFR[i][1], 14, n0, n1, rnd, jag=0.004)
            o = Geo().add(VF, fmi=fmi).obj("HB%d%s" % (i, suffix), [mats[i][v], cut])
            tk.dent(o, 0.0025, 0.25, seed=i * 3 + v)
            kit_part("HB%d%s" % (i, suffix), o, 30.0, pose=HFR[i][0])
    # gusset plates: a triangle with its apex clipped (buried in the beams) and a hollowed outer edge
    gam = math.acos(float(np.dot(HFR[0][0][:3, 2], HFR[1][0][:3, 2])))
    for name, mat in (("GusA", plate), ("GusB", bare[0])):
        d0, g = 0.07, GUS_G
        e2 = (math.cos(gam), math.sin(gam))
        pts = [(d0, 0.0), (g, 0.0), (0.5 * (g + g * e2[0]) * 0.86, 0.5 * (g * e2[1]) * 0.86), (g * e2[0], g * e2[1]),
               (d0 * e2[0], d0 * e2[1])]
        VF = extrude_z(pts, 0.012, 1)
        o = Geo().add(VF, 0, Matrix.Translation((0, 0, -0.006))).obj(name, [mat])
        kit_part(name, o, 30.0, pose=m_trans((0.0, 0.0, 0.4)))
    # fat weld beads along +X, a cracked one and a torn stub
    for name, L, segs, r, notch, mats_, fm in (("BeadF", 0.2, 8, 0.011, None, [weld], None),
                                              ("BeadFS", 0.09, 5, 0.0075, None, [weld], None),
                                              ("BeadCrack", 0.2, 11, 0.0095, 0.5, [weld, crack], "notch"),
                                              ("BeadRing", 0.62, 26, 0.0135, None, [weld], None),
                                              ("BeadTorn", 0.06, 4, 0.0085, None, [weld, fresh], "end")):
        pts = [(L * k / segs, 0.0, 0.0) for k in range(segs + 1)]
        VF = sweep(pts, r, 5, caps=True, rfn=bead_rfn(r, L, 0.024 if name == "BeadRing" else 0.018, segs, notch))
        fmi = None
        if fm == "notch":
            fmi = []
            for f in VF[1]:
                xs = [VF[0][i][0] for i in f]
                fmi.append(1 if abs(sum(xs) / len(xs) - L / 2) < L / segs * 0.75 else 0)
        elif fm == "end":
            fmi = [0] * (len(VF[1]) - 1) + [1]
            V = [list(v) for v in VF[0]]
            rr = random.Random(9)
            for k in range((segs) * 5, (segs + 1) * 5):
                V[k][0] += rr.uniform(-0.006, 0.004)
            VF = (V, VF[1])
        o = Geo().add(VF, fmi=fmi).obj(name, mats_)
        kit_part(name, o, 0, pose=m_trans((0.0, 0.0, 0.4)))
    # line: cross members (angle iron, cut to sit on the bottom beam and under the rail), struts, bottom beam, rail
    dx, dz = 2 * LHALF, LR_BOT - LB_TOP
    Lx = math.hypot(dx, dz)
    beta = math.atan2(dx, dz)  # member angle from vertical
    A80 = angle_profile(0.08, 0.008)
    nl = (0.0, -math.sin(beta), math.cos(beta))  # local y (across, in the cross's plane) tilted to level the ends
    for name, mat in (("LX0", olive[0]), ("LX1", bare[0]), ("LX0s", olive[1]), ("LX1s", bare[1])):
        # local: z along the member, x the leg lying in the cross's plane... see cross_frame()
        VF, fmi = cut_member([(x - 0.004, y - 0.04) for x, y in A80], Lx, 6, nl, nl)
        o = Geo().add(VF, fmi=fmi).obj(name, [mat, cut])
        tk.dent(o, 0.002, 0.25, seed=len(name))
        kit_part(name, o, 30.0, pose=cross_frame(0.0, 1))
    Ls = math.hypot(0.42, LCROSS_Z + 0.05 - (Z0 + 0.012))
    gam_s = math.atan2(0.42, LCROSS_Z + 0.05 - (Z0 + 0.012))
    A60 = angle_profile(0.06, 0.006)
    ns = (0.0, -math.sin(gam_s), math.cos(gam_s))
    for name, mat in (("LS", primer[0]), ("LSs", primer[1])):
        VF, fmi = cut_member([(x - 0.03, y - 0.003) for x, y in A60], Ls, 4, ns, (0.0, 0.0, 1.0))
        o = Geo().add(VF, fmi=fmi).obj(name, [mat, cut])
        kit_part(name, o, 30.0, pose=strut_frame(0.0, -1))
    VF, fmi = cut_member(ibeam_profile(0.12, 0.09, 0.008, 0.011), 2.96, 4, (0, 0, 1), (0, 0, 1))
    o = Geo().add(VF, fmi=fmi, M=PERM_X).obj("LB", [bare[0], cut])
    tk.dent(o, 0.002, 0.3, seed=5)
    kit_part("LB", o, 30.0, pose=m_trans((-1.48, 0.0, Z0 + 0.06)))
    for name, mat in (("LR", bare[0]), ("LRs", bare[1])):
        VF, fmi = cut_member(channel_profile(0.05, 0.1, 0.007), 2.96, 14, (0, 0, 1), (0, 0, 1))
        o = Geo().add(VF, fmi=fmi, M=PERM_X).obj(name, [mat, cut])
        tk.dent(o, 0.002, 0.3, seed=len(name) + 7)
        kit_part(name, o, 30.0, pose=m_trans((-1.48, 0.0, LR_BOT + 0.05)))
    g = Geo().add(box_vf(0.13, 0.13, 0.01, (0.0, 0.0, 0.005)))
    for sx, sy in ((-1, -1), (1, 1)):
        g.add(lathe([(0.0, 0.01), (0.011, 0.01), (0.011, 0.02), (0.0, 0.021)], 6), 0,
              Matrix.Translation((sx * 0.045, sy * 0.045, 0.0)))
    o = g.obj("LFoot", [plate])
    kit_part("LFoot", o, 30.0, pose=m_trans((0.0, -0.46, Z0)))
    g = Geo()
    g.add(lathe([(0.0, 0.0), (0.016, 0.0), (0.016, 0.012), (0.0, 0.0125)], 6))
    g.add(lathe([(0.0, -0.034), (0.009, -0.034), (0.009, 0.004), (0.0, 0.004)], 6))
    g.add(lathe([(0.0, -0.029), (0.016, -0.029), (0.016, -0.017), (0.0, -0.016)], 6))
    kit_part("Bolt", g.obj("Bolt", [weld]), 40.0, pose=m_trans((0.0, 0.0, 0.4)))
    # a mound of dirt for the sunk feet
    rnd = random.Random(3)
    prof_m = [(0.21, -0.02), (0.18, 0.025), (0.12, 0.068), (0.055, 0.092), (0.0, 0.1)]
    o = Geo().add(lathe(prof_m, 13, rnd=rnd, wobble=0.14)).obj("Mound", [soil])
    tk.dent(o, 0.025, 0.06, seed=4)
    kit_part("Mound", o, 0, pose=m_trans((0.0, 0.0, Z0 + 0.02)))
    return dict(cut=cut, weld=weld)


def cross_frame(xc, sgn, y_off=0.0):
    """Frame of a line cross member: sgn +1 rises toward +X, -1 toward -X. Local z along the member from its foot,
    local x toward the back (+Y, the outstanding leg is at x < 0... see the profile shift), local y in the cross's
    plane."""
    foot = np.array([xc - sgn * LHALF, y_off, LB_TOP])
    top = np.array([xc + sgn * LHALF, y_off, LR_BOT])
    a = unit(top - foot)
    yv = unit(np.cross(a, [0.0, 1.0, 0.0])) * (-1.0 if sgn > 0 else 1.0)
    xv = np.cross(yv, a)  # -Y for sgn +1 (outstanding leg to the front), +Y for sgn -1 (to the back)
    return m_frame(xv, yv, a, foot)


def strut_frame(xc, side):
    """A raking strut from the cross's crossing point down to a foot at y = side * 0.45 (front -1, back +1). Local z
    from the foot up."""
    foot = np.array([xc, side * 0.45, Z0 + 0.012])
    top = np.array([xc, side * 0.03, LCROSS_Z + 0.05])
    a = unit(top - foot)
    xv = np.array([-side, 0.0, 0.0])
    yv = np.cross(a, xv)
    return m_frame(xv, yv, a, foot)


def layout_kit():
    """Each part in its pose, spread apart past the AO bake distance."""
    x, y, row = 0.0, 0.0, 0.0
    for obj in KIT:
        name = obj.name[4:]
        pose = META[name]["pose"]
        co = np.array([v.co[:] for v in obj.data.vertices])
        P = xf(co, pose)
        lo, hi = P.min(axis=0), P.max(axis=0)
        w, d = hi[0] - lo[0], hi[1] - lo[1]
        if x + w > 9.0 and x > 0:
            x, y, row = 0.0, y + row + 0.6, 0.0
        M = m_trans((x - lo[0], y - lo[1], 0.0)) @ pose
        obj.matrix_world = Matrix(M.tolist())
        x += w + 0.6
        row = max(row, d)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- bake, templates

class Tpl:
    def __init__(self, name, V, F, UV):
        self.name, self.V, self.F, self.UV = name, V, F, UV
        self.lo, self.hi = V.min(axis=0), V.max(axis=0)


def bake_kit():
    kit = tk.join(list(KIT), "TankTrapKit")
    kit = tk.triangulate(kit)
    tk.smart_uvs(kit)
    scene = bpy.context.scene
    for attempt in range(3):
        try:
            paths = tk.bake_atlas(kit, ASSETS, MAT)
            img = bpy.data.images.load(paths["albedo"], check_existing=False)
            a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
            img.pixels.foreach_get(a)
            bpy.data.images.remove(img)
            if a.reshape(-1, 4)[:, :3].mean() < 0.01:
                raise RuntimeError("baked albedo came out black")
            return kit, paths
        except RuntimeError as e:
            log("bake failed (%s); retrying on the CPU" % e)
            scene.cycles.device = "CPU"
    raise RuntimeError("bake failed three times")


def extract_templates(kit):
    me = kit.data
    nv, nf = len(me.vertices), len(me.polygons)
    lco = np.empty(nv * 3, np.float32)
    me.attributes["lco"].data.foreach_get("vector", lco)
    lco = lco.reshape(-1, 3).astype(np.float64)
    loops = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loops)
    ls = np.empty(nf, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(nf, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    assert (lt == 3).all(), "kit is not triangulated"
    idx = ls[:, None] + np.arange(3)[None, :]
    F = loops[idx]
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    UV = uv.reshape(-1, 2)[idx]
    kp = np.empty(nf, np.int32)
    me.attributes["kpart"].data.foreach_get("value", kp)
    out = {}
    for name, m in META.items():
        sel = np.nonzero(kp == m["index"])[0]
        f = F[sel]
        used = np.unique(f)
        remap = np.full(nv, -1, np.int64)
        remap[used] = np.arange(len(used))
        out[name] = Tpl(name, lco[used], remap[f], UV[sel])
    return out


# ---------------------------------------------------------------- items

class Item:
    def __init__(self, V, F, UV, group=""):
        self.V, self.F, self.UV, self.group = V, F, UV, group


def local(name, deform=None):
    """A template's vertices in its own frame, optionally deformed there."""
    t = T[name]
    V = t.V.copy()
    if deform is not None:
        V = deform(V)
    return V


def place(name, M, group="", deform=None):
    t = T[name]
    return Item(xf(local(name, deform), M), t.F.copy(), t.UV.copy(), group)


def along(name, path, group="", smooth=1, rscale=1.0):
    t = T[name]
    pts = chaikin(path, smooth) if smooth else [np.array(p, float) for p in path]
    P = np.array(pts, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    P = P[np.concatenate([[True], seg > 1e-7])]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    _, Nn, Bn = frames(P)
    u = (t.V[:, 0] - t.lo[0]) / max(t.hi[0] - t.lo[0], 1e-9)
    s = u * cum[-1]
    i = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(P) - 2)
    f = ((s - cum[i]) / np.maximum(seg[i], 1e-9))[:, None]
    pos = P[i] + f * (P[i + 1] - P[i])
    Nv = Nn[i] * (1 - f) + Nn[i + 1] * f
    Bv = Bn[i] * (1 - f) + Bn[i + 1] * f
    Nv /= np.linalg.norm(Nv, axis=1)[:, None]
    Bv /= np.linalg.norm(Bv, axis=1)[:, None]
    V = pos + (t.V[:, 1] * rscale)[:, None] * Nv + (t.V[:, 2] * rscale)[:, None] * Bv
    return Item(V, t.F.copy(), t.UV.copy(), group)


def finish_mesh(name, items, material, clamp=True):
    Vs, Fs, UVs, off = [], [], [], 0
    for it in items:
        Vs.append(it.V)
        Fs.append(it.F + off)
        UVs.append(it.UV)
        off += len(it.V)
    V = np.concatenate(Vs)
    if clamp:
        V[:, 2] = np.maximum(V[:, 2], Z0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], np.concatenate(Fs).tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.concatenate(UVs).reshape(-1).astype(np.float32))
    me.materials.append(material)
    me.shade_smooth()
    me.update()
    return tk.link(bpy.data.objects.new(name, me))


def bend_local(V, z0, b, phi_deg, N, reverse_L=None):
    """Bends a member built along local +Z: past z0 it curves toward the local direction N (unit, in the xy plane)
    through phi over a length b, then runs straight. reverse_L bends the other end (from z = L - z0 down)."""
    V = V.copy()
    if reverse_L is not None:
        V[:, 2] = reverse_L - V[:, 2]
    phi = math.radians(phi_deg)
    Rb = b / phi
    N3 = np.array([N[0], N[1], 0.0])
    W3 = np.cross([0.0, 0.0, 1.0], N3)
    q = V @ N3
    w = V @ W3
    s = V[:, 2]
    th = phi * np.clip((s - z0) / b, 0.0, 1.0)
    extra = np.clip(s - z0 - b, 0.0, None)
    Cz = z0
    zhat = np.array([0.0, 0.0, 1.0])
    r = (Rb - q)[:, None]
    P = (Cz * zhat + Rb * N3)[None, :] + r * (-N3[None, :] * np.cos(th)[:, None] + zhat[None, :] * np.sin(th)[:, None])
    P = P + extra[:, None] * (zhat[None, :] * math.cos(phi) + N3[None, :] * math.sin(phi))
    P = P + w[:, None] * W3[None, :]
    out = np.where((s > z0)[:, None], P, V)
    if reverse_L is not None:
        out[:, 2] = reverse_L - out[:, 2]
    return out


def dent_local(V, c, radius, vec):
    """Pushes the vertices within radius of local point c by vec (smooth falloff)."""
    d = np.linalg.norm(V - np.asarray(c), axis=1)
    k = np.where(d < radius, 0.5 + 0.5 * np.cos(np.pi * d / radius), 0.0)
    return V + k[:, None] * np.asarray(vec)[None, :]


# ---------------------------------------------------------------- hedgehog

def gusset_pairs():
    """(beam i, beam j, upper?) for the six gussets, with their frames."""
    out = []
    for up in (True, False):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            ui = HFR[i][0][:3, 2] * (1 if up else -1)
            uj = HFR[j][0][:3, 2] * (1 if up else -1)
            w = unit(uj - ui * ui.dot(uj))
            n = np.cross(ui, w)
            out.append((i, j, up, m_frame(ui, w, n, HC), ui, uj, w, n))
    return out


def inside_ibeam(Plocal):
    """Inside the beam's outline (the gusset runs along the web, so it leaves through a flange's outer face)."""
    x, y = np.abs(Plocal[:, 0]), np.abs(Plocal[:, 1])
    return (x <= IB_B / 2) & (y <= IB_H / 2)


def weld_line(k, along_dir, v, n, t0=0.1, t1=0.31, steps=6):
    """Where a gusset (in-plane direction v away from beam k's axis, normal n) meets beam k's flange: a bead path
    in the corner between the plate's face (the n side) and the flange."""
    Minv = np.linalg.inv(HFR[k][0])
    pts = []
    for t in np.linspace(t0, t1, steps):
        p0 = HC + along_dir * t
        s = np.linspace(0.0, 0.16, 161)
        P = p0[None, :] + s[:, None] * v[None, :] + n[None, :] * 0.007
        ins = inside_ibeam(xf(P, Minv))
        last = np.nonzero(ins)[0]
        se = s[last[-1]] if len(last) else 0.0
        pts.append(p0 + v * (se + 0.005) + n * 0.012)
    return pts


GUS = gusset_pairs()
BEADS = []  # (gusset index, beam index, path)
for gi, (i, j, up, M, ui, uj, w, n) in enumerate(GUS):
    wj = unit(ui - uj * uj.dot(ui))
    BEADS.append((gi, i, weld_line(i, ui, w, n)))
    BEADS.append((gi, j, weld_line(j, uj, wj, n)))


def seam_path(k, sgn):
    """Beam 0 runs through; beams 1 and 2 are each two halves butted against it. The seam round a half-beam's
    I-profile where it leaves beam 0's outline (sgn +1 the upper half, -1 the lower)."""
    M, L = HFR[k]
    inv0 = np.linalg.inv(HFR[0][0])
    prof = np.array(ibeam_profile(IB_H, IB_B, IB_TW, IB_TF))
    t_hit = 0.05
    for t in np.arange(0.03, 0.5, 0.004):
        P = np.column_stack([prof, np.full(len(prof), L / 2 + sgn * t)])
        loc = xf(xf(P, M), inv0)
        if not ((np.abs(loc[:, 0]) <= IB_B / 2) & (np.abs(loc[:, 1]) <= IB_H / 2)).any():
            t_hit = t
            break
    ring = prof * np.array([1.0 + 0.007 / (IB_B / 2), 1.0 + 0.007 / (IB_H / 2)])
    P = np.column_stack([ring, np.full(len(ring), L / 2 + sgn * (t_hit - 0.012))])
    pts = list(xf(P, M))
    return pts + [pts[0]], t_hit


SEAMS = [(k, sgn) + seam_path(k, sgn) for k in (1, 2) for sgn in (1, -1)]


def torn_bead(path, group=""):
    """A torn weld: two stubs left at the ends of the run, the rest ripped out."""
    P = [np.array(p) for p in path]
    a = [P[0], P[0] + (P[1] - P[0]) * 0.8]
    b = [P[-1], P[-1] + (P[-2] - P[-1]) * 0.8]
    return [along("BeadTorn", a, group, smooth=0), along("BeadTorn", b, group, smooth=0)]


def hedgehog(level):
    """level 0, 1, 2 or 'bent'."""
    rnd = random.Random(7 + (level if isinstance(level, int) else 9))
    bent = level == "bent"
    scraped = bent or level >= 1
    items = []
    deform = {0: None, 1: None, 2: None}
    L = [HFR[i][1] for i in range(3)]
    torn = set()
    crack = None
    sprung = None
    if level == 1:
        # beam 2's top dented in from above and its tip knocked aside; a cracked weld
        L2 = L[2]
        deform[2] = lambda V, L2=L2: bend_local(dent_local(V, (IB_B / 2, 0.0, L2 - 0.12), 0.15, (-0.03, 0.0, 0.0)),
                                                L2 - 0.3, 0.2, 7.0, (0.0, 1.0))
        crack = 3
    elif level == 2:
        L1 = L[1]
        deform[1] = lambda V, L1=L1: bend_local(V, L1 / 2 + GUS_G * 0.95, 0.32, 36.0, (-1.0, 0.0))
        L2 = L[2]
        deform[2] = lambda V, L2=L2: bend_local(dent_local(V, (IB_B / 2, 0.0, L2 - 0.12), 0.15, (-0.03, 0.0, 0.0)),
                                                L2 - 0.3, 0.2, 7.0, (0.0, 1.0))
        torn = {7}  # gusset 3's weld to beam 1
        crack = 3
        sprung = 4
    elif bent:
        L0, L1, L2 = L
        deform[0] = lambda V, L0=L0: bend_local(V, L0 / 2 + 0.2, 0.3, 62.0, (-1.0, 0.0))
        deform[1] = lambda V, L1=L1: bend_local(V, L1 / 2 + 0.26, 0.4, 70.0, (0.0, 1.0), reverse_L=L1)
        deform[2] = lambda V, L2=L2: bend_local(bend_local(V, L2 / 2 + 0.38, 0.3, 28.0, (0.0, 1.0)),
                                                L2 - 0.3, 0.2, 9.0, (-1.0, 0.0))
    for i in range(3):
        items.append(place("HB%d%s" % (i, "s" if scraped else ""), HFR[i][0], "beam%d" % i, deform[i]))
    # gussets and their welds (in the bent stage the upper gussets on beam 0 and the lower ones on beam 1 are torn
    # off with the arm and the leg, leaving stubs of weld on the other beam)
    def removed(i, j, up):
        return bent and ((up and 0 in (i, j)) or ((not up) and 1 in (i, j)))
    for gi, (i, j, up, M, ui, uj, w, n) in enumerate(GUS):
        if removed(i, j, up):
            continue
        Mg = M
        if sprung == gi:
            Mg = m_trans(HC) @ m_rot_axis(uj, 5.0) @ m_trans(-HC) @ M
        items.append(place("GusA" if gi % 2 == 0 else "GusB", Mg, "gusset"))
    for bi, (gi, k, path) in enumerate(BEADS):
        i, j, up = GUS[gi][:3]
        if removed(i, j, up):
            if k != (0 if up else 1):
                items += torn_bead(path)
            continue
        if bi in torn or (sprung == gi and k == GUS[gi][0]):
            items += torn_bead(path)
        elif bi == crack:
            items.append(along("BeadCrack", path, smooth=1))
        else:
            items.append(along("BeadF", path, smooth=1))
    # the seams where the half-beams butt onto beam 0 (in DMG2 one has torn half open)
    for si, (k, sgn, path, t_hit) in enumerate(SEAMS):
        if level == 2 and k == 1 and sgn > 0:
            items.append(along("BeadRing", path[:10], smooth=0))
            items += torn_bead(path[11:15])
        elif level == 1 and si == 3:
            items.append(along("BeadRing", path[:9], smooth=0))
            items.append(along("BeadCrack", path[8:12], smooth=0))
            items.append(along("BeadF", path[11:], smooth=0))
        else:
            items.append(along("BeadRing", path, smooth=0))
    if bent:
        # tilt down toward the folded leg (beam 1's foot, at 120 degrees) and sink it into the ground
        d = np.array([math.cos(math.radians(120)), math.sin(math.radians(120)), 0.0])
        axis = np.cross([0.0, 0.0, 1.0], d)
        tilt = m_trans((0.0, 0.0, Z0)) @ m_rot_axis(axis, 13.0) @ m_trans((0.0, 0.0, -Z0))
        for it in items:
            it.V = xf(it.V, tilt)
        top = max(it.V[:, 2].max() for it in items)
        for it in items:
            it.V[:, 2] -= top - 1.1
        # keep the wreck inside its 2 x 2 footprint: turn it for the best fit, then pull it in a little if needed
        allv = np.concatenate([it.V for it in items])
        best = min(range(0, 120, 5), key=lambda d: np.abs(xf(allv, m_rot("Z", d))[:, :2]).max())
        ext = np.abs(xf(allv, m_rot("Z", best))[:, :2]).max()
        k = min(1.0, 1.01 / ext)
        fit = m_scale(k, k, 1.0) @ m_rot("Z", best)
        for it in items:
            it.V = xf(it.V, fit)
        log("bent hedgehog: turned %d degrees, scaled %.3f to fit (extent was %.3f)" % (best, k, ext))
        # dirt heaped where the sunk legs go into the ground
        for it in list(items):
            if not it.group.startswith("beam"):
                continue
            low = it.V[it.V[:, 2] < Z0 + 0.01]
            if len(low) > 12:
                c = low.mean(axis=0)
                for k in range(2):
                    off = np.array([rnd.uniform(-0.07, 0.07), rnd.uniform(-0.07, 0.07), 0.0])
                    sc = rnd.uniform(0.95, 1.25) * (1.0 if k == 0 else 0.7)
                    items.append(place("Mound", m_trans((c[0] + off[0], c[1] + off[1], Z0 - 0.012)) @
                                       m_rot("Z", rnd.uniform(0, 360)) @ m_scale(sc, sc * rnd.uniform(0.8, 1.1), sc * 0.65),
                                       "dirt"))
        # the torn-off gusset lying in the dirt by a foot
        items.append(place("GusA", m_trans((0.3, -0.6, Z0 + 0.007)) @ m_rot("Z", 35.0) @ m_rot("X", 3.0), "loose"))
    name = "Hedgehog_%s" % (("DMG%d" % level) if not bent else "Bent")
    return finish_mesh(name, items, MATERIAL)


# ---------------------------------------------------------------- line

def line(level):
    rnd = random.Random(31 + (level if isinstance(level, int) else 9))
    bent = level == "bent"
    scraped = bent or level >= 1
    items = []
    items.append(place("LB", m_trans((-1.48, 0.0, Z0 + 0.06)), "bottom"))
    items.append(place("LRs" if scraped else "LR", m_trans((-1.48, 0.0, LR_BOT + 0.05)), "rail"))
    welds = []  # (cross, at the top?, path)
    for ci, xc in enumerate(LX):
        grp = "cross%d" % ci
        for k, sgn in enumerate((1, -1)):
            # the two members' flat legs lie back to back in the cross's plane, the outstanding legs to the front
            # (rising to +X) and to the back (rising to -X); welded along the side of the flat leg at each end
            yo = -0.0045 if sgn > 0 else 0.0045
            nm = ("LX%d" % ((ci + k) % 2)) + ("s" if scraped else "")
            items.append(place(nm, cross_frame(xc, sgn, yo), grp))
            yb = yo + (-0.0105 if sgn > 0 else 0.0105)
            for x, z, is_top in ((xc - sgn * LHALF, LB_TOP + 0.005, False), (xc + sgn * LHALF, LR_BOT - 0.005, True)):
                welds.append((ci, is_top, [(x - 0.044, yb, z), (x, yb, z), (x + 0.044, yb, z)]))
        items.append(place("Bolt", m_trans((xc, -0.0085, LCROSS_Z)) @ m_rot("X", 90), grp))
        # raking struts front and back from just above the crossing down to bolted foot plates
        for side in (-1, 1):
            tag = "%d%s" % (ci, "f" if side < 0 else "b")
            items.append(place("LSs" if scraped else "LS", strut_frame(xc, side), "strut" + tag))
            foot = np.array([xc, side * 0.45, Z0])
            items.append(place("LFoot", m_trans(foot) @ m_rot("Z", rnd.uniform(-8, 8)), "foot" + tag))
            fc = foot + np.array([0.0, 0.0, 0.012])
            items.append(along("BeadFS", [fc + np.array([-0.034, -side * 0.01, 0.003]), fc + np.array([0.0, -side * 0.012, 0.005]),
                                          fc + np.array([0.034, -side * 0.01, 0.003])], "foot" + tag, smooth=0))
            tc = np.array([xc + side * 0.0, side * 0.012, LCROSS_Z + 0.02])
            welds.append((ci, "strut" + tag, [tc + np.array([-0.034, 0.0, 0.0]), tc, tc + np.array([0.034, 0.0, 0.0])]))
    crack_i = 4 if level in (1, 2) else None
    torn_cross = 2 if level == 2 else (1 if bent else None)
    for wi, (ci, where, path) in enumerate(welds):
        grp = "cross%d" % ci if not isinstance(where, str) else where
        if where is True and torn_cross == ci:
            items += torn_bead(path, grp)
        elif where == "strut2f" and level == 2:
            items += torn_bead(path, grp)
        elif bent and isinstance(where, str) and where.startswith("strut1"):
            items += torn_bead(path, grp)
        elif bent and ci == 0 and where is True and wi % 2 == 0:
            items += torn_bead(path, grp)
        elif wi == crack_i:
            items.append(along("BeadCrack", path, grp, smooth=0))
        else:
            items.append(along("BeadFS", path, grp, smooth=0))
    fields = []
    if level == 1:
        def rail_dent(V, it):
            if it.group != "rail":
                return V
            out = V.copy()
            g = np.exp(-((V[:, 0] + 0.55) / 0.12) ** 2) * smoothstep(LR_BOT - 0.02, LR_BOT + 0.1, V[:, 2])
            out[:, 2] -= 0.035 * g
            out[:, 1] += 0.012 * g
            return out
        fields.append(rail_dent)
    if level == 2 or bent:
        xb = 1.0 if level == 2 else 0.0
        cb = "cross%d" % LX.index(xb)
        drop = 0.11 if level == 2 else 0.4
        bow = 0.13 if level == 2 else 0.26
        width = 0.55 if level == 2 else 0.75

        def buckle(V, it):
            out = V.copy()
            near = np.exp(-((V[:, 0] - xb) / width) ** 2)
            if it.group == "rail" or (it.group.startswith("cross") and it.group != cb):
                hz = smoothstep(LB_TOP + 0.3, LR_BOT + 0.1, V[:, 2])
                out[:, 2] -= drop * near * hz
                out[:, 1] -= bow * 0.3 * near * hz
            elif it.group == cb or it.group in ("strut%sf" % cb[-1], "strut%sb" % cb[-1]):
                u = np.clip((V[:, 2] - LB_TOP) / (LR_BOT - LB_TOP), 0.0, 1.0)
                out[:, 1] -= bow * np.sin(np.pi * u) ** 1.3
                out[:, 2] -= drop * u ** 1.5 * 1.15
                out[:, 0] += 0.05 * np.sin(np.pi * u) * (1 if level == 2 else -1)
            return out
        fields.append(buckle)

        def strut_bend(V, it):
            # torn off at the top and buckled: bowed sideways, slumped
            tags = ("strut2f",) if level == 2 else ("strut1f", "strut1b")
            if it.group not in tags:
                return V
            out = V.copy()
            u = np.clip((V[:, 2] - Z0) / (LCROSS_Z + 0.05 - Z0), 0.0, 1.0)
            out[:, 0] += (0.1 if level == 2 else -0.16) * np.sin(np.pi * u)
            out[:, 2] -= (0.08 if level == 2 else 0.22) * u ** 2
            if level == 2:
                out[:, 1] -= 0.04 * u
            return out
        fields.append(strut_bend)
    if bent:
        def lean(V, it):
            if not it.group.startswith(("cross", "strut", "rail")):
                return V
            ang = 9.0 * smoothstep(-0.2, -1.3, V[:, 0]) - 6.0 * smoothstep(0.2, 1.3, V[:, 0])
            a = np.radians(ang)
            y, z = V[:, 1], V[:, 2] - LB_TOP
            out = V.copy()
            out[:, 1] = y * np.cos(a) - z * np.sin(a)
            out[:, 2] = LB_TOP + y * np.sin(a) + z * np.cos(a)
            return out
        fields.append(lean)
    for it in items:
        for f in fields:
            it.V = f(it.V, it)
    if bent:
        for x in (-0.2, 0.3):
            items.append(place("Mound", m_trans((x, rnd.uniform(-0.12, 0.12), Z0 - 0.03)) @ m_scale(1.1, 0.8, 0.55),
                               "dirt"))
    name = "Line_%s" % (("DMG%d" % level) if not bent else "Bent")
    return finish_mesh(name, items, MATERIAL)


# ---------------------------------------------------------------- reports, export

def stats(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0), len(me.polygons)


def front_fx(obj, z=0.4):
    """The middle of the piece's front at mid-height: in front of the nearest geometry around x = 0."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    sel = co[(np.abs(co[:, 0]) < 0.3) & (np.abs(co[:, 2] - z) < 0.3)]
    y = sel[:, 1].min() if len(sel) else -0.3
    return (0.0, round(float(y) - 0.03, 3), z)


def export_piece(fname, meshes, fx):
    saved, objs = [], []
    for i, m in enumerate(meshes):
        saved.append((m, m.name, m.data.name))
        m.name = "DMG%d" % i
        m.data.name = "DMG%d" % i
        objs.append(m)
    empty = None
    if fx is not None:
        empty = tk.link(bpy.data.objects.new("FX", None))
        empty.empty_display_size = 0.1
        empty.location = fx
        objs.append(empty)
    tk.export_fbx(objs, os.path.join(ASSETS, fname))
    if empty is not None:
        bpy.data.objects.remove(empty)
    for m, n, dn in saved:
        m.name = n
        m.data.name = dn


# ---------------------------------------------------------------- previews

ALL = []


def stage():
    tk.preview_stage()
    floor = bpy.data.objects["Floor"]
    floor.data.transform(Matrix.Scale(3.0, 4))
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (0.0, 0.0, 0.0)


def figure_at(x, y):
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)


def lineup(entries, cam, path, res=(2200, 900), samples=96):
    for o in ALL:
        o.hide_render = True
    temps = []
    for obj, (x, y), rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = (x, y, 0.0)
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    tk.render(cam, path, res=res, samples=samples)
    for t in temps:
        bpy.data.objects.remove(t)


# ================================================================ main

if MODE == "beads":
    for bi, (gi, k, path) in enumerate(BEADS):
        P = np.array(path)
        loc = xf(P, np.linalg.inv(HFR[k][0]))
        log("bead %d gusset %d beam %d local x %s y %s" % (bi, gi, k, loc[:, 0].round(3), loc[:, 1].round(3)))
    for k, sgn, path, t_hit in SEAMS:
        log("seam beam %d half %+d at %.3f m from the centre, %d points" % (k, sgn, t_hit, len(path)))
    sys.exit(0)
tk.reset_scene()
bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
build_kit()
layout_kit()
if MODE == "kit":
    tk.preview_stage()
    cam = tk.camera("KitCam", (4.5, -9.0, 4.0), (4.5, 2.0, 0.3), lens=28)
    tk.render(cam, os.path.join(PREVIEWS, "dbg_tanktraps_kit.png"), res=(1600, 1000), samples=48)
    sys.exit(0)

kit, PATHS = bake_kit()
T = extract_templates(kit)
bpy.data.objects.remove(kit)
MATERIAL = tk.baked_material(MAT, PATHS)
assert MATERIAL.name == MAT, MATERIAL.name
log("baked", PATHS)

HH = [hedgehog(i) for i in range(3)]
HB = hedgehog("bent")
LL = [line(i) for i in range(3)]
LBt = line("bent")
ALL += HH + [HB] + LL + [LBt]
REPORT = []
for fname, meshes, fx in (("TankTrapHedgehog.fbx", HH, front_fx(HH[0])), ("TankTrapHedgehogBent.fbx", [HB], None),
                          ("TankTrapLine.fbx", LL, front_fx(LL[0])), ("TankTrapLineBent.fbx", [LBt], None)):
    export_piece(fname, meshes, fx)
    for i, m in enumerate(meshes):
        lo, hi, tris = stats(m)
        REPORT.append("%s: DMG%d tris %d bounds %s..%s" % (fname, i, tris, lo.round(3), hi.round(3)))
    if fx:
        REPORT.append("%s: FX at %s" % (fname, fx))
for line_ in REPORT:
    log(line_)
if MODE == "export":
    sys.exit(0)

stage()
figure_at(4.4, 1.2)
ents = [(HH[0], (-3.3, 0.0), 0), (HH[1], (-1.1, 0.0), 0), (HH[2], (1.1, 0.0), 0), (HB, (3.3, 0.0), 0)]
lineup(ents, tk.camera("HF", (0.8, -11.0, 3.0), (0.0, 0.0, 0.35), lens=35), os.path.join(PREVIEWS, "tanktrap_hedgehog_stages.png"))
lineup(ents, tk.camera("HB", (-0.8, 11.0, 3.0), (0.0, 0.0, 0.35), lens=35),
       os.path.join(PREVIEWS, "tanktrap_hedgehog_stages_back.png"))
figure_at(1.6, 1.0)
lineup([(HH[0], (0.0, 0.0), 0)], tk.camera("HClose", (1.6, -3.4, 1.4), (0.0, 0.0, 0.35), lens=35),
       os.path.join(PREVIEWS, "tanktrap_hedgehog_close.png"), res=(1300, 1100))
lineup([(HH[2], (0.0, 0.0), 0)], tk.camera("HClose2", (-2.2, -2.8, 1.6), (0.0, 0.0, 0.35), lens=35),
       os.path.join(PREVIEWS, "tanktrap_hedgehog_dmg2_close.png"), res=(1300, 1100))
lineup([(HB, (0.0, 0.0), 0)], tk.camera("HClose3", (2.4, -2.6, 1.5), (0.0, 0.0, 0.2), lens=35),
       os.path.join(PREVIEWS, "tanktrap_hedgehog_bent_close.png"), res=(1300, 1100))
figure_at(5.6, 1.0)
ents = [(LL[0], (-5.1, 0.0), 0), (LL[1], (-1.7, 0.0), 0), (LL[2], (1.7, 0.0), 0), (LBt, (5.1, 0.0), 0)]
lineup(ents, tk.camera("LF", (1.5, -14.0, 3.6), (0.0, 0.0, 0.35), lens=35), os.path.join(PREVIEWS, "tanktrap_line_stages.png"),
       res=(2400, 900))
lineup(ents, tk.camera("LB", (-1.5, 14.0, 3.6), (0.0, 0.0, 0.35), lens=35),
       os.path.join(PREVIEWS, "tanktrap_line_stages_back.png"), res=(2400, 900))
figure_at(2.4, 1.2)
lineup([(LL[0], (0.0, 0.0), 0)], tk.camera("LClose", (2.6, -4.2, 1.6), (0.0, 0.0, 0.35), lens=35),
       os.path.join(PREVIEWS, "tanktrap_line_close.png"), res=(1400, 1000))
lineup([(LL[2], (0.0, 0.0), 0)], tk.camera("LClose2", (3.0, -3.6, 1.5), (0.4, 0.0, 0.3), lens=35),
       os.path.join(PREVIEWS, "tanktrap_line_dmg2_close.png"), res=(1400, 1000))
lineup([(LBt, (0.0, 0.0), 0)], tk.camera("LClose3", (-2.6, -4.0, 1.7), (0.0, 0.0, 0.2), lens=35),
       os.path.join(PREVIEWS, "tanktrap_line_bent_close.png"), res=(1400, 1000))
# a small field of them, to see them together
field = [(HH[0], (-2.2, 1.2), 0), (HH[1], (0.4, 2.6), 25), (LL[0], (1.6, -0.6), 0), (HB, (-3.4, -1.4), 60)]
figure_at(0.6, -1.4)
lineup(field, tk.camera("Field", (3.5, -8.5, 3.8), (-0.4, 0.6, 0.2), lens=30), os.path.join(PREVIEWS, "tanktrap_field.png"),
       res=(2000, 1100))

for o in ALL:
    o.hide_render = o is not HH[0]
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not HH[0]}
tk.icon(tk.camera("Icon", (2.0, -3.3, 1.75), (0.03, 0.0, 0.38), lens=46), ICON, hide=hide, target=(0.0, 0.0, 0.38))
log("icon", ICON)

bpy.ops.wm.read_factory_settings(use_empty=True)
for fname in sorted(os.listdir(ASSETS)):
    if not fname.endswith(".fbx"):
        continue
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=os.path.join(ASSETS, fname))
    parts = []
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type == "MESH":
            co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            parts.append("%s tris %d mats %s x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f parent %s" % (
                o.name, tris, [m.name for m in o.data.materials], co[:, 0].min(), co[:, 0].max(), co[:, 1].min(),
                co[:, 1].max(), co[:, 2].min(), co[:, 2].max(), o.parent.name if o.parent else None))
        else:
            parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation),
                                                    o.parent.name if o.parent else None))
    log("reimport", fname, "|", " || ".join(parts))
log("done")
