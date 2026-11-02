"""Chain-Link (Fortifications Expanded): galvanised chain-link fence panels, corners and a rolling gate.

    ChainLinkPanel{Light,Heavy}{Taut,Sagging,Torn}.fbx   2 m panel (top rail at z = 1.45)
    ChainLinkTall{Light,Heavy}{Taut,Sagging,Torn}.fbx    3 m panel (top rail at z = 2.45)
    ChainLinkCorner{Light,Heavy}{Taut,Sagging,Torn}.fbx  corner post at the origin, half panels to +X and +Y
    ChainLinkGate.fbx                                     3 wide rolling gate: Frame (static) and SlideLeaf

Every panel and corner file holds one mesh, DMG0. The fence line runs along X at y = 0: posts at x = +-0.46 on
that line, the mesh hung on their front (-Y) face. Light: galvanised posts and top rail with bolted rail-end cups
and brace bands, a tension wire along the bottom, wire ties. Heavy: thicker posts on welded foot plates, welded
rails, a middle rail, welded angle-iron braces behind and a rusty kick plate between the posts at the bottom.
Sagging: the mesh bowed in and slumped off loose ties, a bent rail, slack tension wire. Torn: the mesh ripped open
low down and peeled out toward the front, unravelled wires, the tension wire snapped, one post bent back.

Two materials: `ChainLink`, a 2048 atlas baked once from a kit of parts (every piece is built from copies of the
kit parts that keep their UVs), and `ChainLinkMesh`, a 1 m tiling diamond wire-mesh texture made with numpy (RGBA,
alpha = wire coverage, cut out at 0.3 in game) on flat double-sided planes UV-mapped in metres (16 diamonds a metre
across, 14 up).

The gate's SlideLeaf has its origin at its own bottom centre (0, 0.12, -0.5) and opens by sliding along +X by
2.9 m (Blender coordinates).

    blender -b --factory-startup --python chainlink.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default), export (no renders), kit (unbaked kit preview only)
"""
import math
import os
import random
import sys

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
MAT = "ChainLink"
MESH_MAT = "ChainLinkMesh"
XP = 0.46  # post x in a panel

R_PL, R_PH, R_PX, R_PG = 0.024, 0.030, 0.036, 0.040  # post radii: light, heavy (and light corner), heavy corner, gate
R_RL, R_RH = 0.0175, 0.021  # rail radii: light, heavy (and the gate leaf)
GATE_Y = 0.12  # the gate leaf runs on this line
GATE_SLIDE = 2.9


def log(*a):
    print("[chainlink]", *a, flush=True)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- matrices (numpy)

def m_rot(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, axis))


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


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------- primitives: (verts, faces) lists

def tube_z(r, L, sides, segs, cap0=False, cap1=False, rfn=None, phase=0.0):
    V, F = [], []
    for k in range(segs + 1):
        z = L * k / segs
        rr = rfn(k / segs) if rfn else r
        for j in range(sides):
            a = 2 * math.pi * (j + phase) / sides
            V.append((rr * math.cos(a), rr * math.sin(a), z))
    for k in range(segs):
        for j in range(sides):
            a, b = k * sides + j, k * sides + (j + 1) % sides
            F.append((a, b, b + sides, a + sides))
    if cap0:
        F.append(tuple(reversed(range(sides))))
    if cap1:
        F.append(tuple(segs * sides + j for j in range(sides)))
    return V, F


def extrude_z(profile, L, segs, caps=True):
    """A CCW profile (x, y) extruded along +Z from 0 to L."""
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


def lathe(prof, sides, phase=0.5):
    """Revolves a (r, z) profile (listed bottom to top) around Z; r = 0 points become poles."""
    V, F, rings = [], [], []
    for r, z in prof:
        if r <= 1e-9:
            rings.append([len(V)] * sides)
            V.append((0.0, 0.0, z))
        else:
            ids = []
            for j in range(sides):
                a = 2 * math.pi * (j + phase) / sides
                ids.append(len(V))
                V.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ids)
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(sides):
            j1 = (j + 1) % sides
            q = [A[j], A[j1], B[j1], B[j]]
            q2 = []
            for v in q:
                if v not in q2:
                    q2.append(v)
            if len(q2) >= 3:
                F.append(tuple(q2))
    return V, F


def box_vf(sx, sy, sz, c=(0.0, 0.0, 0.0)):
    x, y, z = sx / 2, sy / 2, sz / 2
    V = [(c[0] + a * x, c[1] + b * y, c[2] + d * z) for a, b, d in
         ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return V, F


def frames(P):
    """Tangents and parallel-transported normals/binormals along a polyline (numpy n x 3)."""
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
    B = np.cross(T, N)
    return T, N, B


def sweep(points, r, sides, caps=False, rfn=None, closed=False):
    """A tube along a polyline; rfn(t, j) varies the radius (t along the path 0-1, j around)."""
    P = np.array(points, float)
    if closed:
        P = np.concatenate([P[-1:], P, P[:1]])
    T, N, B = frames(P)
    if closed:
        P, T, N, B = P[1:-1], T[1:-1], N[1:-1], B[1:-1]
    n = len(P)
    V, F = [], []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        for j in range(sides):
            a = 2 * math.pi * j / sides
            rr = rfn(t, j) if rfn else r
            V.append(tuple(P[i] + rr * (math.cos(a) * N[i] + math.sin(a) * B[i])))
    rings = n if closed else n - 1
    for i in range(rings):
        i1 = (i + 1) % n
        for j in range(sides):
            j1 = (j + 1) % sides
            F.append((i * sides + j, i * sides + j1, i1 * sides + j1, i1 * sides + j))
    if caps and not closed:
        F.append(tuple(reversed(range(sides))))
        F.append(tuple((n - 1) * sides + j for j in range(sides)))
    return V, F


def chaikin(pts, it=2, closed=False):
    P = [np.array(p, float) for p in pts]
    for _ in range(it):
        Q = [] if closed else [P[0]]
        m = len(P) if closed else len(P) - 1
        for i in range(m):
            a, b = P[i], P[(i + 1) % len(P)]
            Q += [a * 0.75 + b * 0.25, a * 0.25 + b * 0.75]
        if not closed:
            Q.append(P[-1])
        P = Q
    return P


class Geo:
    """Vertices, faces and per-face material slots, gathered from primitives and turned into one object."""

    def __init__(self):
        self.V, self.F, self.M = [], [], []

    def add(self, VF, mi=0, M=None):
        V, F = VF
        off = len(self.V)
        for v in V:
            p = Vector(v)
            if M is not None:
                p = (Matrix(M.tolist()) if isinstance(M, np.ndarray) else M) @ p
            self.V.append(tuple(p))
        for f in F:
            self.F.append(tuple(i + off for i in f))
            self.M.append(mi)
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


# ---------------------------------------------------------------- kit

KIT, META = [], {}


def kit_part(name, obj, split=40.0, kz=0.0):
    """Registers a part built in its own frame: sharp edges split (so they survive smooth shading in the pieces),
    local coordinates stored for after the bake. kz is the height its local z = 0 sits at in the bake layout, so
    ground grime and rust streaks land where they would on a placed piece."""
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
    META[name] = dict(index=len(KIT), kz=kz)
    KIT.append(obj)
    return obj


def bead_rfn(r0, L, pitch, seed):
    """Weld ripples: stacked-coin lumps every `pitch`, tapered ends, a little noise."""
    rnd = random.Random(seed)
    jit = [rnd.uniform(-0.12, 0.12) for _ in range(64)]

    def f(t, j):
        s = t * L
        rip = 0.8 + 0.28 * abs(math.cos(math.pi * s / pitch)) ** 0.7
        taper = min(1.0, t / 0.07, (1.0 - t) / 0.07) if L > 0.05 else 1.0
        taper = max(0.25, taper) ** 0.5
        return r0 * rip * taper * (1.0 + jit[(int(s / pitch * 2) + j) % 64] * 0.6)
    return f


def build_kit():
    galv = tk.photo_material("K_Galv", "rust_coarse_01", scale=2.6, sat=0.06, value=0.95, tint=(0.95, 0.97, 1.0),
                             exposed="rust_coarse_01", chip=0.8, patches=0.3, grime=0.6, streaks=1.1,
                             metal_floor=0.45, rough_scale=0.85, grit=0.6, scratches=0.35, edges=0.55, contrast=0.12)
    galv_old = tk.photo_material("K_GalvOld", "rust_coarse_01", scale=2.3, sat=0.1, value=0.85,
                                 tint=(0.96, 0.96, 0.97), exposed="rust_coarse_01", chip=1.0, patches=0.55, grime=0.8,
                                 streaks=1.5, offset=(0.4, 0.2, 0.0), metal_floor=0.4, rough_scale=0.85, grit=0.8,
                                 scratches=0.4, edges=0.6, contrast=0.12)
    galv_b = tk.photo_material("K_GalvB", "rust_coarse_01", scale=2.6, sat=0.06, value=0.95, tint=(0.95, 0.97, 1.0),
                               exposed="rust_coarse_01", chip=0.8, patches=0.3, grime=0.6, streaks=1.1,
                               offset=(0.53, 0.29, 0.61), metal_floor=0.45, rough_scale=0.85, grit=0.6, scratches=0.35,
                               edges=0.55, contrast=0.12)
    galv_old_b = tk.photo_material("K_GalvOldB", "rust_coarse_01", scale=2.3, sat=0.1, value=0.85,
                                   tint=(0.96, 0.96, 0.97), exposed="rust_coarse_01", chip=1.0, patches=0.55,
                                   grime=0.8, streaks=1.5, offset=(0.11, 0.77, 0.37), metal_floor=0.4,
                                   rough_scale=0.85, grit=0.8, scratches=0.4, edges=0.6, contrast=0.12)
    fitting = tk.photo_material("K_Fitting", "metal_plate_02", scale=3.0, sat=0.2, value=1.15, exposed="rust_coarse_01",
                                chip=1.0, patches=0.45, grime=0.8, streaks=0.8, metal_floor=0.5, rough_scale=0.8,
                                grit=0.7, scratches=0.4, edges=0.7, contrast=0.1)
    angle = tk.photo_material("K_Angle", "rusty_painted_metal", scale=2.2, sat=0.55, value=0.62, chip=1.0,
                              patches=0.6, grime=0.8, streaks=0.8, metal_floor=0.4, rough_scale=0.85, grit=0.9,
                              scratches=0.45, edges=0.7, contrast=0.08)
    kick = tk.photo_material("K_Kick", "green_metal_rust", scale=1.6, sat=0.4, value=0.8, chip=1.0, patches=0.85,
                             grime=0.9, streaks=1.5, metal_floor=0.35, rough_scale=0.85, grit=1.0, scratches=0.5,
                             edges=0.8, contrast=0.1)
    rust = tk.photo_material("K_Rust", "rust_coarse_01", scale=3.2, value=0.9, exposed=None, grime=0.7, metal_floor=0.3,
                             grit=0.7)
    weld = tk.photo_material("K_Weld", "rust_coarse_01", scale=6.0, sat=0.7, value=0.55, exposed=None, grime=0.8,
                             metal_floor=0.35, grit=0.5, bump=0.8)
    wire = tk.grimy("K_Wire", (0.27, 0.27, 0.26), roughness=0.5, metallic=0.55, grime=0.55, stain=(0.2, 0.09, 0.04),
                    grit=0.4, scale=2.0, dirt_range=(0.3, 0.1))
    wheel = tk.photo_material("K_Wheel", "metal_plate_02", scale=3.0, sat=0.3, value=0.55, exposed="rust_coarse_01",
                              chip=1.0, patches=0.6, grime=0.9, metal_floor=0.5, rough_scale=0.8, grit=0.8,
                              scratches=0.4, edges=0.8)

    def part(name, VF, mats, mi=None, split=40.0, kz=0.0):
        g = Geo()
        if mi is None:
            g.add(VF, 0)
        else:
            V, F = VF
            g.V = [tuple(v) for v in V]
            g.F = [tuple(f) for f in F]
            g.M = list(mi)
        return kit_part(name, g.obj(name, mats), split, kz)

    # posts: open tubes (the cap covers the top, the ground the bottom), local z = 0 at the ground
    for name, r, sides, L, segs, mat in (("PL2", R_PL, 10, 1.99, 8, galv), ("PL3", R_PL, 10, 2.99, 10, galv),
                                         ("PH2", R_PH, 10, 1.99, 8, galv_old), ("PH3", R_PH, 10, 2.99, 10, galv_old),
                                         ("PX2", R_PX, 12, 1.99, 8, galv_old), ("PG2", R_PG, 14, 1.99, 4, galv_old),
                                         ("PL2b", R_PL, 10, 1.99, 8, galv_b), ("PL3b", R_PL, 10, 2.99, 10, galv_b),
                                         ("PH2b", R_PH, 10, 1.99, 8, galv_old_b),
                                         ("PH3b", R_PH, 10, 2.99, 10, galv_old_b)):
        part(name, tube_z(r, L, sides, segs), [mat], split=60.0, kz=Z0)
    # dome caps (local z = 0 at the post tube's top)
    part("CapS", lathe([(R_PL + 0.0005, -0.03), (R_PL + 0.0035, -0.03), (R_PL + 0.0035, 0.002),
                        (R_PL + 0.0012, 0.012), (R_PL * 0.6, 0.02), (0.0, 0.023)], 10), [fitting], split=50.0,
         kz=1.49)
    part("CapL", lathe([(R_PG + 0.0005, -0.035), (R_PG + 0.0038, -0.035), (R_PG + 0.0038, 0.003),
                        (R_PG + 0.0012, 0.015), (R_PG * 0.62, 0.026), (0.0, 0.03)], 14), [fitting], split=50.0,
         kz=1.49)
    # rails along +X from 0 (axis at local z = 0)
    to_x = Matrix.Rotation(math.radians(90), 4, "Y")
    for name, r, L, segs, mat in (("RailL", R_RL, 0.86, 7, galv), ("RailH", R_RH, 0.87, 7, galv_old),
                                  ("RailLS", R_RL, 0.40, 4, galv), ("RailHS", R_RH, 0.40, 4, galv_old)):
        g = Geo().add(tube_z(r, L, 10, segs), 0, to_x)
        kit_part(name, g.obj(name, [mat]), 50.0, kz=1.45)
    # light rail-end fittings: a brace band round the post (axis Z at the origin) and a cup for the rail along +X
    for name, rp in (("RailEnd24", R_PL), ("RailEnd30", R_PH)):
        g = Geo()
        g.add(lathe([(rp + 0.0004, -0.012), (rp + 0.0034, -0.012), (rp + 0.0034, 0.012), (rp + 0.0004, 0.012)], 12))
        g.add(box_vf(0.007, 0.024, 0.022, (0.0, rp + 0.013, 0.0)))
        g.add(tube_z(0.0062, 0.028, 6, 1, cap0=True, cap1=True), 0,
              Matrix.Translation((-0.014, rp + 0.016, 0.0)) @ to_x)
        cup = lathe([(0.0, 0.0), (R_RL + 0.0015, 0.0), (R_RL + 0.0036, 0.004), (R_RL + 0.0036, 0.03),
                     (R_RL + 0.0012, 0.033)], 10)
        g.add(cup, 0, Matrix.Translation((rp - 0.004, 0.0, 0.0)) @ to_x)
        kit_part(name, g.obj(name, [fitting]), 50.0, kz=1.45)
    # weld rings: round a rail end (axis X) and round a post foot (axis Z)
    for name, R, axis_m, kz in (("WeldRingR", R_RH + 0.0035, to_x, 1.45), ("WeldRingP", R_PH + 0.0035, None, Z0)):
        n = 7
        pts = [(R * math.cos(2 * math.pi * k / n), R * math.sin(2 * math.pi * k / n), 0.0) for k in range(n)]
        g = Geo().add(sweep(pts, 0.0055, 4, closed=True, rfn=bead_rfn(0.0055, 2 * math.pi * R, 0.02, len(name))), 0,
                      axis_m)
        kit_part(name, g.obj(name, [weld]), 0, kz=kz)
    # straight weld beads along +X (bent along paths in the pieces)
    for name, L, segs, r in (("BeadS", 0.08, 6, 0.005), ("BeadM", 0.17, 10, 0.0055)):
        pts = [(L * k / segs, 0.0, 0.0) for k in range(segs + 1)]
        part(name, sweep(pts, r, 4, caps=True, rfn=bead_rfn(r, L, 0.016, segs)), [weld], split=0, kz=0.4)
    # angle iron 40 x 40 x 4 along +X: one leg along +Y, the other along +Z
    prof = [(0.0, 0.0), (0.04, 0.0), (0.04, 0.004), (0.004, 0.004), (0.004, 0.04), (0.0, 0.04)]
    g = Geo().add(extrude_z(prof, 1.3, 4), 0, Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    kit_part("Brace", g.obj("Brace", [angle]), 30.0, kz=0.4)
    # kick plates (local: centred in x and y, z from 0)
    for name, w in (("Kick", 0.86), ("KickS", 0.39)):
        o = tk.box(name, (w, 0.006, 0.30), (0.0, 0.0, 0.15), kick, bevel_width=0.0015)
        tk.dent(o, 0.0025, 0.12, seed=len(name))
        kit_part(name, o, 30.0, kz=Z0 + 0.03)
    # foot plates with two nuts (local origin at the post's foot)
    for name, sx, sy in (("Foot", 0.075, 0.15), ("FootG", 0.1, 0.2)):
        g = Geo().add(box_vf(sx, sy, 0.01, (0.0, 0.0, 0.005)))
        for y in (-sy / 2 + 0.024, sy / 2 - 0.024):
            g.add(tube_z(0.0095, 0.008, 6, 1, cap1=True), 0, Matrix.Translation((0.0, y, 0.01)))
            g.add(tube_z(0.0045, 0.006, 6, 1, cap1=True), 0, Matrix.Translation((0.0, y, 0.018)))
        kit_part(name, g.obj(name, [rust]), 30.0, kz=Z0)
    # thin wire for ties, hog rings and the tension wire (bent along paths)
    for name, L, segs, r, sides in (("WireS", 0.25, 8, 0.0017, 3), ("WireM", 0.5, 6, 0.0021, 3),
                                    ("WireL", 1.0, 12, 0.0021, 4)):
        pts = [(L * k / segs, 0.0, 0.0) for k in range(segs + 1)]
        part(name, sweep(pts, r, sides), [wire], split=0, kz=0.4)
    # gate: V-groove wheel (axis Z), its bracket (axle along Y), tubes, guide, latch, handle
    part("Wheel", lathe([(0.0, -0.0175), (0.022, -0.0175), (0.024, -0.012), (0.062, -0.016), (0.066, -0.013),
                         (0.052, 0.0), (0.066, 0.013), (0.062, 0.016), (0.024, 0.012), (0.022, 0.0175),
                         (0.0, 0.0175)], 12), [wheel], split=45.0, kz=-0.435)
    g = Geo()
    for y in (-0.026, 0.026):
        g.add(box_vf(0.09, 0.006, 0.085, (0.0, y, 0.022)))
    g.add(tube_z(0.008, 0.07, 8, 1), 0, Matrix.Translation((0.0, -0.035, 0.0)) @
          Matrix.Rotation(math.radians(-90), 4, "X"))
    for y in (-0.035, 0.035):
        g.add(tube_z(0.012, 0.008, 6, 1, cap0=True, cap1=True), 0,
              Matrix.Translation((0.0, y + (0.0 if y < 0 else -0.008), 0.0)) @
              Matrix.Rotation(math.radians(-90), 4, "X"))
    kit_part("Bracket", g.obj("Bracket", [rust]), 40.0, kz=-0.435)
    for name, r, L, segs, sides, caps, mat in (("GRail", R_RH, 2.902, 6, 10, True, galv_old),
                                               ("GVert", R_RH, 1.76, 4, 10, False, galv_old),
                                               ("GBrace", 0.016, 3.37, 6, 8, False, galv)):
        g = Geo().add(tube_z(r, L, sides, segs, cap0=caps, cap1=caps), 0, to_x)
        kit_part(name, g.obj(name, [mat]), 50.0, kz=0.5)
    # guide at the top of the +X gate post (local: post axis Z at the origin, z = 0 at the leaf's top rail)
    g = Geo()
    g.add(lathe([(R_PG + 0.0004, -0.005), (R_PG + 0.0036, -0.005), (R_PG + 0.0036, 0.075), (R_PG + 0.0004, 0.075)],
                14))
    g.add(box_vf(0.05, 0.15, 0.01, (0.0, 0.11, 0.07)))
    for yy in (GATE_Y - 0.043, GATE_Y + 0.043):
        g.add(tube_z(0.006, 0.08, 6, 1), 0, Matrix.Translation((0.0, yy, -0.005)))
        g.add(lathe([(0.0, 0.002), (0.016, 0.002), (0.02, 0.008), (0.02, 0.05), (0.016, 0.056), (0.0, 0.056)], 12), 0,
              Matrix.Translation((0.0, yy, 0.0)))
        g.add(tube_z(0.01, 0.008, 6, 1, cap1=True), 0, Matrix.Translation((0.0, yy, 0.075)))
    kit_part("Guide", g.obj("Guide", [fitting]), 45.0, kz=1.42)
    g = Geo()
    g.add(lathe([(R_PG + 0.0004, -0.02), (R_PG + 0.0036, -0.02), (R_PG + 0.0036, 0.02), (R_PG + 0.0004, 0.02)], 14))
    g.add(box_vf(0.022, 0.07, 0.03, (0.0, 0.065, 0.0)))
    g.add(box_vf(0.008, 0.08, 0.04, (-0.004, GATE_Y, 0.0)))
    for yy in (GATE_Y - 0.034, GATE_Y + 0.034):
        g.add(box_vf(0.07, 0.008, 0.04, (0.031, yy, 0.0)))
    kit_part("Latch", g.obj("Latch", [rust]), 30.0, kz=0.55)
    hp = [(0.0, 0.0, 0.0), (0.0, -0.04, 0.0), (0.0, -0.06, 0.03), (0.0, -0.06, 0.15), (0.0, -0.04, 0.18),
          (0.0, 0.0, 0.18)]
    part("Handle", sweep(chaikin(hp, 2), 0.009, 8, caps=True), [fitting], split=60.0, kz=0.5)
    return dict(galv=galv, wire=wire)


def layout_kit():
    """Spreads the parts out (well past the AO bake distance) at their natural heights."""
    x, y, row = 0.0, 0.0, 0.0
    for obj in KIT:
        co = np.array([v.co[:] for v in obj.data.vertices])
        lo, hi = co.min(axis=0), co.max(axis=0)
        w, d = hi[0] - lo[0], hi[1] - lo[1]
        if x + w > 7.0 and x > 0:
            x, y, row = 0.0, y + row + 0.6, 0.0
        obj.location = (x - lo[0], y - lo[1], META[obj.name[4:]]["kz"])
        x += w + 0.6
        row = max(row, d)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- bake, then templates

class Tpl:
    def __init__(self, name, V, F, UV):
        self.name, self.V, self.F, self.UV = name, V, F, UV
        self.lo, self.hi = V.min(axis=0), V.max(axis=0)


def bake_kit():
    kit = tk.join(list(KIT), "ChainLinkKit")
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


# ---------------------------------------------------------------- the wire-mesh texture

def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def pnoise(nx, nz, N, rng):
    """Periodic value noise on an nz x nx lattice sampled N x N (rows = v, up)."""
    G = rng.random((nz, nx))
    u = (np.arange(N) + 0.5) / N
    gx, gz = u * nx, u * nz
    ix, iz = np.floor(gx).astype(int), np.floor(gz).astype(int)
    fx, fz = gx - ix, gz - iz
    sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    i0, i1 = ix % nx, (ix + 1) % nx
    j0, j1 = iz % nz, (iz + 1) % nz
    top = G[j0][:, i0] + (G[j0][:, i1] - G[j0][:, i0]) * sx[None, :]
    bot = G[j1][:, i0] + (G[j1][:, i1] - G[j1][:, i0]) * sx[None, :]
    return top + (bot - top) * sz[:, None]


def fbm(nx, nz, N, rng, octaves=4):
    out, amp, tot = np.zeros((N, N)), 1.0, 0.0
    for o in range(octaves):
        out += amp * pnoise(nx * 2 ** o, nz * 2 ** o, N, rng)
        tot += amp
        amp *= 0.5
    return out / tot


def mesh_texture(N=1024):
    """A 1 m x 1 m tile of galvanised chain-link: 32 zigzag wires a metre (16 diamonds across), 14 diamonds up,
    interlocking at hooked knuckles, rust streaks, white oxide and grime varying across the tile."""
    rng = np.random.default_rng(1907)
    NW, ND = 32, 14
    w, h = 1.0 / NW, 1.0 / ND
    rw = 0.0024  # wire radius (4.8 mm drawn wire, a little heavier than real so it reads at range)
    kn = 0.09 * h  # knuckle length
    a = 0.45 * rw  # the two wires of a knuckle sit side by side
    px = 1.0 / N
    c = (np.arange(N) + 0.5) / N
    X = np.broadcast_to(c[None, :], (N, N))
    Zg = np.broadcast_to(c[:, None], (N, N))
    segs = [(-a, 0.0, -a, kn / 2), (-a, kn / 2, w + a, h / 2 - kn / 2), (w + a, h / 2 - kn / 2, w + a, h / 2 + kn / 2),
            (w + a, h / 2 + kn / 2, -a, h - kn / 2), (-a, h - kn / 2, -a, h)]
    kbase = np.floor(X / w).astype(int)
    d1 = np.full((N, N), 9.0)
    vxb, vzb = np.zeros((N, N)), np.zeros((N, N))
    wid = np.zeros((N, N), int)
    knuck = np.zeros((N, N))
    per = []
    for dk in (-1, 0, 1):
        k = kbase + dk
        xl = X - k * w
        zl = np.mod(Zg - (k % 2) * (h / 2), h)
        dmin = np.full((N, N), 9.0)
        for sh in (-h, 0.0, h):
            zz = zl + sh
            for si, (ax, az, bx, bz) in enumerate(segs):
                dx, dz = bx - ax, bz - az
                t = np.clip(((xl - ax) * dx + (zz - az) * dz) / (dx * dx + dz * dz), 0.0, 1.0)
                vx, vz = xl - (ax + t * dx), zz - (az + t * dz)
                d = np.sqrt(vx * vx + vz * vz)
                m = d < d1
                d1 = np.where(m, d, d1)
                vxb = np.where(m, vx, vxb)
                vzb = np.where(m, vz, vzb)
                wid = np.where(m, k, wid)
                knuck = np.where(m, 1.0 if si in (0, 2, 4) else 0.0, knuck)
                dmin = np.minimum(dmin, d)
        per.append(dmin)
    ds = np.sort(np.stack(per), axis=0)
    d2 = ds[1]
    cover = np.clip((rw + 0.7 * px - d1) / (1.4 * px), 0.0, 1.0)

    # normal: a round wire, plus a little wobble along it
    nx = np.clip(vxb / rw, -1.0, 1.0)
    nz = np.clip(vzb / rw, -1.0, 1.0)
    s2 = np.minimum(nx * nx + nz * nz, 0.97)
    k2 = np.sqrt(np.maximum(1.0 - nx * nx - nz * nz, 0.0))
    inside = d1 < rw * 1.05
    nn = np.where(inside, np.sqrt(1.0 - s2), 1.0)
    nx = np.where(inside, nx, 0.0)
    nz = np.where(inside, nz, 0.0)
    wob = (fbm(64, 64, N, rng, 2) - 0.5) * 0.25
    nx = nx + wob * inside
    ln = np.sqrt(nx * nx + nz * nz + nn * nn)
    normal = np.ones((N, N, 4))
    normal[..., 0] = 0.5 + 0.5 * nx / ln
    normal[..., 1] = 0.5 + 0.5 * nz / ln
    normal[..., 2] = 0.5 + 0.5 * nn / ln

    # colour: galvanised zinc, white oxide, grime, rust spots at the knuckles running down as streaks
    wire_tone = rng.uniform(0.84, 1.14, NW)[np.mod(wid, NW)]
    fine = fbm(48, 48, N, rng, 3)
    zinc = np.array([0.235, 0.234, 0.224])[None, None, :] * (wire_tone * (0.8 + 0.4 * fine))[..., None]
    big = 0.45 + 0.9 * fbm(2, 2, N, rng, 2)
    oxide = smoothstep(0.56, 0.72, fbm(6, 6, N, rng, 4)) * 0.75
    grime = smoothstep(0.55, 0.74, fbm(5, 7, N, rng, 4)) * 0.55
    streak_n = 0.55 * pnoise(40, 3, N, rng) + 0.3 * pnoise(90, 6, N, rng) + 0.15 * pnoise(160, 12, N, rng)
    streak = smoothstep(0.58, 0.8, streak_n) * big
    knot = smoothstep(3.0 * rw, 1.0 * rw, d2) * smoothstep(0.66, 0.86, pnoise(NW, ND * 2, N, rng)) * big
    drip = knot.copy()
    step = max(1, int(round(0.004 / px)))
    for i in range(1, 12):
        drip = np.maximum(drip, np.roll(knot, -i * step, axis=0) * (1.0 - i / 12.0) * 0.7)
    blot = smoothstep(0.62, 0.8, fbm(9, 9, N, rng, 4)) * 0.7 * big
    rust = np.clip(streak * 0.9 + drip + blot, 0.0, 1.0)
    rtone = pnoise(24, 24, N, rng)[..., None]
    rust_col = np.array([0.24, 0.095, 0.036]) * (1 - rtone) + np.array([0.105, 0.048, 0.024]) * rtone
    col = zinc
    col = col + (np.array([0.33, 0.33, 0.315]) - col) * oxide[..., None]
    col = col + (np.array([0.07, 0.064, 0.058]) - col) * grime[..., None]
    col = col + (rust_col - col) * rust[..., None]
    occl = (0.72 + 0.28 * nn) * (1.0 - 0.38 * smoothstep(3.4 * rw, 1.4 * rw, d2))
    albedo = np.ones((N, N, 4))
    albedo[..., :3] = srgb(col)
    albedo[..., 3] = cover
    rough = 0.56 + 0.1 * fine
    rough = rough + (0.74 - rough) * oxide
    rough = rough + (0.82 - rough) * grime
    rough = rough + (0.9 - rough) * rust
    metal = 0.35 * (1.0 - rust) * (1.0 - 0.6 * oxide) * (1.0 - grime)
    paths = {k: os.path.join(ASSETS, "%s_%s.png" % (MESH_MAT, s)) for k, s in
             (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}
    tk.save_array(MESH_MAT + "_AlbedoMap", albedo, paths["albedo"], False)
    tk.save_array(MESH_MAT + "_NormalMap", normal, paths["normal"], True)
    tk.save_array(MESH_MAT + "_RMOMMap", tk.rmom(rough, metal, occl), paths["rmom"], True)
    wires = cover > 0.5
    log("mesh texture: coverage %.3f, wire albedo mean sRGB %s, rust share %.2f" % (
        cover.mean(), (albedo[..., :3][wires].mean(axis=0) * 255).round(1), (rust[wires] > 0.5).mean()))
    return paths


def mesh_material(paths):
    """Preview material for the wire mesh: the baked maps with the alpha cut out at 0.3, as the game does."""
    mat, g = tk.new_material(MESH_MAT)
    p = g.node("ShaderNodeBsdfPrincipled")
    out = g.node("ShaderNodeOutputMaterial")
    uv = tk._sock(g.node("ShaderNodeTexCoord").outputs, "UV")

    def tex(path, non_color):
        n = g.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        n.image.alpha_mode = "STRAIGHT"
        n.interpolation = "Linear"
        g.links.new(uv, n.inputs["Vector"])
        return n

    alb = tex(paths["albedo"], False)
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tex(paths["rmom"], True).outputs["Color"], sep.inputs[0])
    g._in(p, "Base Color", tk._multiply_color(g, alb.outputs["Color"], g.mix(1.0, (1.0, 1.0, 1.0), sep.outputs[2])))
    g._in(p, "Roughness", sep.outputs[0])
    g._in(p, "Metallic", sep.outputs[1])
    nm = g.node("ShaderNodeNormalMap")
    g.links.new(tex(paths["normal"], True).outputs["Color"], nm.inputs["Color"])
    g._in(p, "Normal", nm.outputs["Normal"])
    g._in(p, "Alpha", g.math("GREATER_THAN", alb.outputs["Alpha"], 0.3))
    g.links.new(p.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- pieces from templates

class Item:
    def __init__(self, V, F, UV, mi=0, group="", arm=""):
        self.V, self.F, self.UV, self.mi, self.group, self.arm = V, F, UV, mi, group, arm


def place(name, M, group="", arm=""):
    t = T[name]
    return Item(xf(t.V, M), t.F.copy(), t.UV.copy(), 0, group, arm)


def along(name, path, group="", arm="", rscale=1.0, smooth=2, closed=False):
    """Bends a straight template (built along +X) along a polyline."""
    t = T[name]
    pts = chaikin(path, smooth, closed) if smooth else [np.array(p, float) for p in path]
    if closed:
        pts = pts + [pts[0]]
    P = np.array(pts, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 1e-7])
    P = P[keep]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    Tg, Nn, Bn = frames(P)
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
    return Item(V, t.F.copy(), t.UV.copy(), 0, group, arm)


def stretch_x(name, x0, x1, M, group="", arm=""):
    """A template built along +X from 0, stretched to run x0..x1 in its own frame, then placed with M."""
    t = T[name]
    L = t.hi[0] - t.lo[0]
    V = t.V.copy()
    V[:, 0] = x0 + (V[:, 0] - t.lo[0]) / L * (x1 - x0)
    return Item(xf(V, M), t.F.copy(), t.UV.copy(), 0, group, arm)


def finish_mesh(name, items, mats):
    Vs, Fs, UVs, Ms, off = [], [], [], [], 0
    for it in items:
        if len(it.F) == 0:
            continue
        Vs.append(it.V)
        Fs.append(it.F + off)
        UVs.append(it.UV)
        Ms.append(np.full(len(it.F), it.mi, np.int32))
        off += len(it.V)
    V = np.concatenate(Vs)
    V[:, 2] = np.maximum(V[:, 2], Z0)
    F = np.concatenate(Fs)
    by = {}
    for it in items:
        by[it.group or "-"] = by.get(it.group or "-", 0) + len(it.F)
    log("  %s tris by group: %s" % (name, sorted(by.items(), key=lambda kv: -kv[1])))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.concatenate(UVs).reshape(-1).astype(np.float32))
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", np.concatenate(Ms))
    me.shade_smooth()
    me.update()
    return tk.link(bpy.data.objects.new(name, me))


# ---------------------------------------------------------------- wire paths

def tie_path(C, axis, mdir, r_obj, d_mesh, rnd, loose=False):
    """A twisted wire tie round a round member (centre C, unit axis, unit mdir toward the mesh), hooking the mesh
    at d_mesh from the axis. Loose: slipped off the mesh, hanging open."""
    C, A, E1 = np.array(C, float), unit(axis), unit(mdir)
    E2 = np.cross(A, E1)
    R = r_obj + 0.0019
    tw = rnd.uniform(-0.003, 0.003)
    if loose:
        pts = []
        for k in range(7):
            ang = math.radians(-40 + 260 * k / 6)
            pts.append(C + R * (E1 * math.cos(ang) + E2 * math.sin(ang)))
        down = np.array([0.0, 0.0, -1.0])
        perp = down - A * down.dot(A)
        down = unit(perp) if np.linalg.norm(perp) > 0.1 else down  # on a post it slides down the post
        p = pts[-1]
        pts += [p + down * 0.012 + E1 * 0.006, p + down * 0.03 + E1 * 0.012, p + down * 0.04 + E1 * 0.006]
        return pts
    pts = [C + E1 * (d_mesh + 0.0015) + E2 * 0.007 + A * tw]
    for k in range(7):
        ang = math.radians(60 + 240 * k / 6)
        pts.append(C + R * (E1 * math.cos(ang) + E2 * math.sin(ang)) + A * tw * math.cos(ang))
    pts.append(C + E1 * (d_mesh + 0.0015) - E2 * 0.007 - A * tw)
    pts.append(C + E1 * (d_mesh + 0.008) - E2 * 0.002 + A * 0.003)
    pts.append(C + E1 * (d_mesh + 0.015) + E2 * 0.002 - A * 0.001)
    return pts


def loose_wire_path(start, direction, length, rnd, droop=0.5):
    """An unravelled chain-link wire: a flattened zigzag spiralling out from a rip, drooping under its weight."""
    P, d = [], unit(direction)
    side = unit(np.cross(d, [0.0, 0.0, 1.0])) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n = int(length / 0.031) * 2 + 2
    for i in range(n + 1):
        t = i / n
        p = np.array(start, float) + d * length * t
        p = p + side * (0.016 if i % 2 else -0.016) * (1.0 - 0.3 * t)
        p[2] -= droop * length * t * t
        p = p + np.array([rnd.uniform(-0.004, 0.004) for _ in range(3)])
        P.append(p)
    return P


# ---------------------------------------------------------------- the mesh sheet

def sheet(bands, s2w, uv0, deform=None, rip=None, group="mesh", arm=""):
    """A double-sided chain-link sheet. bands: (xs, zs) grids (s along the fence, z up) sharing their boundary rows;
    s2w(s, n, z) -> world (arrays; n toward the back); deform(s, z, side) -> (ds, dn, dz); rip = (s_rip, z_top):
    vertices on that column below z_top are split between the two sides (side -1 left, +1 right)."""
    verts, S, Zs, SD = {}, [], [], []

    def vid(s, z, side):
        key = (round(s, 5), round(z, 5), side)
        if key not in verts:
            verts[key] = len(S)
            S.append(s)
            Zs.append(z)
            SD.append(side)
        return verts[key]

    tris = []
    for xs, zs in bands:
        for j in range(len(zs) - 1):
            for i in range(len(xs) - 1):
                ids = []
                for (ii, jj) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                    s, z = xs[ii], zs[jj]
                    side = 0
                    if rip is not None and abs(s - rip[0]) < 1e-6 and z < rip[1] - 1e-6:
                        side = -1 if ii == i + 1 else 1
                    ids.append(vid(s, z, side))
                a, b, c, d = ids
                tris += [(a, b, c), (a, c, d)]
    S, Zs, SD = np.array(S), np.array(Zs), np.array(SD)
    ds = dn = dz = np.zeros_like(S)
    if deform is not None:
        ds, dn, dz = deform(S, Zs, SD)
    W = s2w(S + ds, dn, Zs + dz)
    UV = np.stack([S + uv0[0], Zs + uv0[1]], axis=1)
    F = np.array(tris, np.int64)
    n = len(S)
    V2 = np.concatenate([W, W])
    F2 = np.concatenate([F, F[:, ::-1] + n])
    UV2 = np.concatenate([UV, UV])[F2]
    return Item(V2, F2, UV2, 1, group, arm)


def grid(a, b, step):
    n = max(1, int(round((b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


def tear_deform(hinge_l, hinge_r, rip_s, rip_top, z_bot, curl=7.5, peel=-1.0, droop=0.04, rnd=None, jag=0.012):
    """Two flaps either side of a vertical rip, curled out (toward peel * n) about hinges at hinge_l and hinge_r,
    fully at the bottom and fading to nothing at the rip's top."""
    jit = {}

    def f(s, z, side):
        ds, dn, dz = np.zeros_like(s), np.zeros_like(s), np.zeros_like(s)
        t = smoothstep(rip_top, z_bot + 0.06, z)
        for sgn, hinge in ((1.0, hinge_l), (-1.0, hinge_r)):
            if sgn > 0:
                on = (s > hinge) & ((s < rip_s - 1e-6) | ((np.abs(s - rip_s) < 1e-6) & (side < 0)))
                arc = s - hinge
            else:
                on = (s < hinge) & ((s > rip_s + 1e-6) | ((np.abs(s - rip_s) < 1e-6) & (side > 0)))
                arc = hinge - s
            k = curl * t
            safe = np.where(k > 1e-4, k, 1.0)
            along_ = np.where(k > 1e-4, np.sin(k * arc) / safe, arc)
            out = np.where(k > 1e-4, (1.0 - np.cos(k * arc)) / safe, 0.0)
            ds = np.where(on, sgn * (along_ - arc), ds)
            dn = np.where(on, peel * out, dn)
            dz = np.where(on, -droop * t * (arc / max(abs(rip_s - hinge), 1e-3)) ** 1.5, dz)
        if rnd is not None:
            edge = (np.abs(s - rip_s) < 1e-6) & (z < rip_top - 1e-6)
            for i in np.nonzero(edge)[0]:
                key = (round(z[i], 4), int(side[i]))
                if key not in jit:
                    jit[key] = (rnd.uniform(-jag, jag), rnd.uniform(-0.008, 0.008))
                ds[i] += jit[key][0] * t[i] * 2.0
                dz[i] += jit[key][1] * t[i]
        return ds, dn, dz
    return f


# ---------------------------------------------------------------- panels

STAGES = ("Taut", "Sagging", "Torn")


def u_of(x, x0, x1):
    return np.clip((x - x0) / (x1 - x0), 0.0, 1.0)


def bend_profile(z, zb, b, ang):
    tn = math.tan(math.radians(ang))
    d = np.clip(z - zb, 0.0, None)
    return np.where(d < b, tn * d * d / (2 * b), tn * (d - b / 2))


def build_panel(kind, weight, stage, mats, seed):
    """A 1-wide panel: kind 'Panel' (2 m) or 'Tall' (3 m), weight 'Light' or 'Heavy'."""
    rnd = random.Random(seed)
    tall = kind == "Tall"
    heavy = weight == "Heavy"
    TOP = 2.45 if tall else 1.45
    PTOP = TOP + 0.04
    rp = R_PH if heavy else R_PL
    rr = R_RH if heavy else R_RL
    post = ("PH" if heavy else "PL") + ("3" if tall else "2")
    ym = -(rp + 0.006)
    MTOP = TOP + 0.035
    MBOT = -0.45
    items = []
    # posts, caps
    for sx, grp in ((-1, "post_l"), (1, "post_r")):
        items.append(place(post + ("b" if sx > 0 else ""), m_trans((sx * XP, 0.0, Z0)) @ m_rot("Z", rnd.uniform(0, 360)),
                           grp))
        items.append(place("CapS", m_trans((sx * XP, 0.0, PTOP)) @ m_scale(rp / R_PL, rp / R_PL, 1.0) @
                           m_rot("Z", rnd.uniform(0, 360)), grp))
    # rails
    rails = [TOP] + ([0.95 if tall else 0.5] if heavy else [])
    for k, zr in enumerate(rails):
        grp = "rail_top" if k == 0 else "rail_mid"
        if heavy:
            x0, x1 = -XP + rp - 0.004, XP - rp + 0.004
            items.append(stretch_x("RailH", x0, x1, m_trans((0.0, 0.0, zr)) @ m_rot("X", rnd.uniform(0, 360)), grp))
            for sx in (-1, 1):
                items.append(place("WeldRingR", m_trans((sx * (XP - rp - 0.002), 0.0, zr)) @
                                   m_rot("X", rnd.uniform(0, 360)), grp))
        else:
            x0, x1 = -XP + rp + 0.012, XP - rp - 0.012
            items.append(stretch_x("RailL", x0, x1, m_trans((0.0, 0.0, zr)) @ m_rot("X", rnd.uniform(0, 360)), grp))
            items.append(place("RailEnd24", m_trans((-XP, 0.0, zr)), "post_l"))
            items.append(place("RailEnd24", m_trans((XP, 0.0, zr)) @ m_rot("Z", 180), "post_r"))
    # heavy: foot plates, kick plate, braces
    if heavy:
        for sx, grp in ((-1, "post_l"), (1, "post_r")):
            items.append(place("Foot", m_trans((sx * XP, 0.0, Z0)) @ m_rot("Z", 0 if sx < 0 else 180), grp))
            items.append(place("WeldRingP", m_trans((sx * XP, 0.0, Z0 + 0.011)) @ m_rot("Z", rnd.uniform(0, 360)),
                               grp))
        items.append(place("Kick", m_trans((0.0, 0.0, Z0 + 0.03)), "kick"))
        for sx in (-1, 1):
            xe = sx * (XP - rp + 0.001)
            items.append(along("BeadM", [(xe, -0.004, Z0 + 0.035), (xe, -0.0045, Z0 + 0.18), (xe, -0.004, Z0 + 0.325)],
                               "kick"))
        mid = rails[1]
        sections = [(-1, -0.13, 1, mid - 0.04), (1, mid + 0.04, -1, TOP - 0.05)]
        for sa, za, sb, zb in sections:
            A = np.array([sa * XP, 0.0, za])
            B = np.array([sb * XP, 0.0, zb])
            d = unit(B - A)
            q = np.cross(d, [0.0, 1.0, 0.0])
            y0 = rp + 0.0015
            M = m_frame(d, [0.0, 1.0, 0.0], q, A + np.array([0.0, y0, 0.0]) - q * 0.02)
            items.append(stretch_x("Brace", 0.0, np.linalg.norm(B - A), M, "brace"))
            for P_end in (A, B):
                # along the line where the brace leg rests on the post's back, on its inner side
                xe = P_end[0] - np.sign(P_end[0]) * 0.013
                c = np.array([xe, y0 - 0.0035, P_end[2] + d[2] / d[0] * (xe - P_end[0])])
                items.append(along("BeadS", [c - q * 0.024, c, c + q * 0.024], "brace"))
    # tension wire along the bottom, threaded through the bottom diamonds
    zt = -0.42
    yt = ym + 0.0035
    tw_pts = [(-XP + rp * 0.5, -rp - 0.001, zt), (-XP + rp + 0.02, yt, zt)] + \
             [(x, yt, zt) for x in np.linspace(-XP + 0.1, XP - 0.1, 5)] + \
             [(XP - rp - 0.02, yt, zt), (XP - rp * 0.5, -rp - 0.001, zt)]
    # ties: posts, rails, hog rings on the tension wire
    if heavy:
        post_z = [-0.25, 0.75, 1.75] if tall else [-0.25, 0.9]
    else:
        post_z = [-0.3, 0.45, 1.2, 1.95] if tall else [-0.3, 0.35, 1.0]
    rail_x = [-0.26, 0.04, 0.29] if not heavy else [-0.2, 0.22]
    ties = []
    for sx in (-1, 1):
        for zz in post_z:
            ties.append(("post_l" if sx < 0 else "post_r", (sx * XP, 0.0, zz), (0, 0, 1), rp, -ym))
    for k, zr in enumerate(rails):
        for x in (rail_x if k == 0 else [0.12]):
            ties.append(("rail_top" if k == 0 else "rail_mid", (x + rnd.uniform(-0.03, 0.03), 0.0, zr), (1, 0, 0),
                         rr, -ym))
    loose_set, gone_set = set(), set()
    if stage == "Sagging":
        loose_set = {i for i, t in enumerate(ties) if t[0] == "rail_top" and abs(t[2][0]) < 0.12}
        gone_set = {rnd.choice([i for i, t in enumerate(ties) if t[0] == "post_r"])}
    elif stage == "Torn":
        cands = [i for i, t in enumerate(ties) if t[0] in ("rail_top", "post_l")]
        loose_set = set(rnd.sample(cands, 2))
        gone_set = {i for i, t in enumerate(ties) if t[0] == "post_r" and t[2][2] < 0.6}
        gone_set |= {i for i, t in enumerate(ties) if t[0] == "rail_mid" and t[2][0] > 0.0}
    for i, (grp, C, ax, r_obj, dmesh) in enumerate(ties):
        if i in gone_set:
            continue
        items.append(along("WireS", tie_path(C, ax, (0, -1, 0), r_obj, dmesh, rnd, loose=i in loose_set), grp,
                           smooth=1))
    hog_x = [] if heavy else [-0.25, 0.27]
    if stage != "Torn":
        items.append(along("WireL", tw_pts, "tw", smooth=1))
        for x in hog_x:
            c = np.array([x, yt - 0.0015, zt])
            ring = [c + 0.0055 * np.array([0.0, math.cos(a), math.sin(a)]) for a in np.linspace(0.3, 2 * math.pi, 7)]
            items.append(along("WireS", ring, "tw", smooth=1))
    else:
        # snapped near the middle: each half sprung back and hanging
        for sx in (-1, 1):
            p0 = np.array([sx * (XP - rp * 0.5), -rp - 0.001, zt])
            p1 = np.array([sx * (XP - rp - 0.02), yt, zt])
            pts = [p0, p1]
            for k in range(1, 6):
                t = k / 5.0
                pts.append(np.array([sx * (XP - 0.05 - 0.3 * t), yt - 0.05 * t - 0.03 * t * t,
                                     max(Z0 + 0.004, zt - 0.08 * t)]) +
                           np.array([0.0, 0.0, 0.025 * math.sin(t * 7.0 + sx)]))
            items.append(along("WireL", pts, "tw", smooth=1))

    # the mesh
    span0, span1 = -XP, XP
    fx = lambda s, n, z: np.stack([s, ym + n, z], axis=1)  # noqa: E731
    uv0 = (rnd.uniform(0, 1), rnd.uniform(0, 1))
    H = MTOP - MBOT
    if stage == "Taut":
        bands = [(grid(span0, span1, 0.3), grid(MBOT, MTOP, 0.5))]
        deform = None
        rip = None
    else:
        bow = 0.06 if not tall else 0.085
        if stage == "Torn":
            bow *= 0.6

        def bow_f(s, z, side, bow=bow):
            u = u_of(s, span0 + rp, span1 - rp)
            wv = np.clip((z - MBOT) / H, 0.0, 1.0)
            dn = bow * np.sin(np.pi * u) * np.sin(np.pi * np.clip(wv * 1.1, 0, 1)) ** 0.8
            dz = -0.035 * np.sin(np.pi * u) * wv ** 2 - 0.02 * np.sin(np.pi * u) * (1 - wv) ** 6
            return np.zeros_like(s), dn, dz
        if stage == "Sagging":
            bands = [(grid(span0, span1, 0.15), grid(MBOT, MTOP, 0.22 if not tall else 0.26))]
            deform = bow_f
            rip = None
        else:
            hl, hr, rs, rt = -0.32, 0.26, -0.04, 0.24
            tear = tear_deform(hl, hr, rs, rt, MBOT, rnd=rnd)
            xs_lo = sorted(set(round(v, 6) for v in [span0, -0.39] + grid(hl, rs, 0.056) + grid(rs, hr, 0.06) +
                               [0.36, span1]))
            zs_lo = grid(MBOT, rt, 0.1) + [rt + 0.12]
            xs_hi = grid(span0, span1, 0.15)
            zs_hi = [rt + 0.12] + grid(rt + 0.12, MTOP, 0.25)[1:]
            bands = [(xs_lo, zs_lo), (xs_hi, zs_hi)]
            rip = (rs, rt)

            def deform(s, z, side):
                a = tear(s, z, side)
                b = bow_f(s, z, side)
                return a[0] + b[0], a[1] + b[1], a[2] + b[2]
            # unravelled wires hanging out of the rip
            for k in range(2):
                zs0 = MBOT + 0.08 + 0.12 * k
                start = (rs + rnd.uniform(-0.02, 0.02), ym - 0.02 - 0.03 * k, zs0)
                items.append(along("WireL", loose_wire_path(start, (0.25 * (1 if k else -1), -1.0, -0.2),
                                                            0.22 + 0.1 * k, rnd, droop=0.6), "mesh", smooth=0))
    items.append(sheet(bands, fx, uv0, deform, rip))

    # stage fields
    fields = []
    if stage in ("Sagging", "Torn"):
        sag = 0.045 if stage == "Sagging" else 0.065
        kx = rnd.uniform(-0.15, 0.2)

        def rail_sag(V, it):
            if it.group.startswith("post"):
                return V
            u = u_of(V[:, 0], -XP + rp, XP - rp)
            wz = smoothstep(TOP - 0.7, TOP - 0.02, V[:, 2])
            dz = -(sag * np.sin(np.pi * u) ** 1.2 + 0.016 * np.exp(-((V[:, 0] - kx) / 0.07) ** 2)) * wz
            dy = 0.018 * np.sin(np.pi * u) * wz
            out = V.copy()
            out[:, 2] += dz
            out[:, 1] += dy
            return out
        fields.append(rail_sag)

        def slack(V, it):
            if it.group != "tw" or stage == "Torn":
                return V
            u = u_of(V[:, 0], -XP + rp, XP - rp)
            out = V.copy()
            out[:, 2] -= 0.03 * np.sin(np.pi * u)
            out[:, 1] += 0.02 * np.sin(np.pi * u)
            return out
        fields.append(slack)
        if heavy:
            kc = np.array([rnd.uniform(-0.2, 0.2), 0.0, Z0 + 0.2])

            def kick_dent(V, it, kc=kc, amt=0.025 if stage == "Sagging" else 0.045):
                if it.group != "kick":
                    return V
                d = np.linalg.norm((V - kc) * np.array([1.0, 0.0, 1.4]), axis=1)
                out = V.copy()
                out[:, 1] += amt * np.exp(-(d / 0.13) ** 2)
                return out
            fields.append(kick_dent)
    if stage == "Torn":
        ang, zb, b = (6.0 if tall else 8.0), -0.22, 0.5
        dvec = unit([0.03, 1.0, 0.0])  # bent back, within the block

        def post_bend(V, it):
            wgt = smoothstep(-XP + rp + 0.05, XP - rp - 0.01, V[:, 0])
            if it.group == "post_r":
                wgt = np.ones(len(V))
            elif it.group == "post_l":
                return V
            g_ = bend_profile(V[:, 2], zb, b, ang) * wgt
            return V + g_[:, None] * dvec[None, :]
        fields.append(post_bend)
    for it in items:
        for f in fields:
            it.V = f(it.V, it)
    name = "ChainLink%s%s%s" % (kind, weight, stage)
    return finish_mesh(name, items, mats)


def build_corner(weight, stage, mats, seed):
    """Corner post at the origin, half panels to +X and +Y with end posts at x = 0.46 and y = 0.46."""
    rnd = random.Random(seed)
    heavy = weight == "Heavy"
    TOP = 1.45
    PTOP = TOP + 0.04
    rc = R_PX if heavy else R_PH
    re = R_PH if heavy else R_PL
    rr = R_RH if heavy else R_RL
    ym = -(rc + 0.006)
    MTOP, MBOT = TOP + 0.035, -0.45
    items = []
    cpost = "PX2" if heavy else "PH2"
    epost = "PH2" if heavy else "PL2"
    items.append(place(cpost, m_trans((0.0, 0.0, Z0)) @ m_rot("Z", rnd.uniform(0, 360)), "post_c"))
    items.append(place("CapS", m_trans((0.0, 0.0, PTOP)) @ m_scale(rc / R_PL, rc / R_PL, 1.0), "post_c"))
    # arms: frame (along, back, up) for each
    arms = {"X": (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])),
            "Y": (np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0]))}
    for arm, (a, bk) in arms.items():
        rotz = 0.0 if arm == "X" else 90.0
        E = a * XP
        items.append(place(epost + ("b" if arm == "X" else ""), m_trans((E[0], E[1], Z0)) @ m_rot("Z", rnd.uniform(0, 360)),
                           "post_e", arm))
        items.append(place("CapS", m_trans((E[0], E[1], PTOP)) @ m_scale(re / R_PL, re / R_PL, 1.0), "post_e", arm))
        rails = [TOP] + ([0.5] if heavy else [])
        for k, zr in enumerate(rails):
            grp = "rail_top" if k == 0 else "rail_mid"
            if heavy:
                M = m_rot("Z", rotz) @ m_trans((0.0, 0.0, zr)) @ m_rot("X", rnd.uniform(0, 360))
                items.append(stretch_x("RailHS", rc - 0.004, XP - re + 0.004, M, grp, arm))
                for xr in (rc + 0.002, XP - re - 0.002):
                    items.append(place("WeldRingR", m_rot("Z", rotz) @ m_trans((xr, 0.0, zr)) @
                                       m_rot("X", rnd.uniform(0, 360)), grp, arm))
            else:
                zr2 = zr - (0.028 if arm == "Y" else 0.0)  # the second band sits under the first on the corner post
                M = m_rot("Z", rotz) @ m_trans((0.0, 0.0, zr2)) @ m_rot("X", rnd.uniform(0, 360))
                items.append(stretch_x("RailLS", rc + 0.012, XP - re - 0.012, M, grp, arm))
                items.append(place("RailEnd30", m_rot("Z", rotz) @ m_trans((0.0, 0.0, zr2)), "post_c", arm))
                items.append(place("RailEnd24", m_rot("Z", rotz) @ m_trans((XP, 0.0, zr2)) @ m_rot("Z", 180), "post_e",
                                   arm))
        if heavy:
            items.append(place("Foot", m_trans((E[0], E[1], Z0)) @ m_rot("Z", rotz + 180), "post_e", arm))
            items.append(place("WeldRingP", m_trans((E[0], E[1], Z0 + 0.011)), "post_e", arm))
            kc = (rc + XP - re) / 2
            items.append(place("KickS", m_rot("Z", rotz) @ m_trans((kc, 0.0, Z0 + 0.03)), "kick", arm))
            for xe in (XP - re + 0.001,):
                pts = [(xe, -0.004, Z0 + 0.035), (xe, -0.0045, Z0 + 0.18), (xe, -0.004, Z0 + 0.325)]
                items.append(along("BeadM", [xf(np.array([p]), m_rot("Z", rotz))[0] for p in pts], "kick", arm))
            # brace behind the arm, from the corner post low to the end post under the middle rail
            A = np.array([0.0, 0.0, -0.13])
            B = np.array([XP, 0.0, 0.46])
            d = unit(B - A)
            q = np.cross(d, [0.0, 1.0, 0.0])
            y0 = max(rc, re) + 0.0015
            M = m_rot("Z", rotz) @ m_frame(d, [0.0, 1.0, 0.0], q, A + np.array([0.0, y0, 0.0]) - q * 0.02)
            if arm == "Y":
                M = m_rot("Z", 90) @ m_scale(1.0, -1.0, 1.0) @ m_frame(d, [0.0, 1.0, 0.0], q,
                                                                     A + np.array([0.0, y0, 0.0]) - q * 0.02)
            br = stretch_x("Brace", 0.0, np.linalg.norm(B - A), M, "brace", arm)
            if arm == "Y":
                br.F = br.F[:, ::-1]  # mirrored: keep the faces outward
            items.append(br)
            for P_end in (A, B):
                xe = P_end[0] + 0.013 * (1 if P_end[0] < 0.2 else -1)
                c = np.array([xe, y0 - 0.0035, P_end[2] + d[2] / max(d[0], 1e-6) * (xe - P_end[0])])
                pts = [c - q * 0.024, c, c + q * 0.024]
                if arm == "Y":
                    pts = [np.array([p[1], p[0], p[2]]) for p in pts]
                items.append(along("BeadS", pts, "brace", arm))
    if heavy:
        items.append(place("Foot", m_trans((0.0, 0.0, Z0)) @ m_rot("Z", 45), "post_c"))
        items.append(place("WeldRingP", m_trans((0.0, 0.0, Z0 + 0.011)) @ m_scale(rc / R_PH, rc / R_PH, 1.0), "post_c"))

    # ties, tension wires, mesh for each arm
    loose_n = 0
    for arm, (a, bk) in arms.items():
        rotz = 0.0 if arm == "X" else 90.0
        R = m_rot("Z", rotz)
        mdir = -bk
        zoff = -0.028 if (arm == "Y" and not heavy) else 0.0
        ties = []
        for zz in ([0.3] if heavy else [-0.25, 0.85]):
            ties.append(("post_c", (0.0, 0.0, zz + (0.05 if arm == "Y" else 0.0)), (0, 0, 1), rc, -ym))
            ties.append(("post_e", tuple(a * XP + np.array([0, 0, zz])), (0, 0, 1), re, -ym))
        for s in ([0.22] if heavy else [0.15, 0.32]):
            ties.append(("rail_top", tuple(a * s + np.array([0, 0, TOP + zoff])), tuple(a), rr, -ym))
        for i, (grp, C, ax, r_obj, dmesh) in enumerate(ties):
            if stage == "Torn" and arm == "X" and grp == "post_e" and C[2] < 0.6:
                continue
            loose = (stage != "Taut" and grp == "rail_top" and loose_n < (1 if stage == "Sagging" else 2))
            if loose:
                loose_n += 1
            items.append(along("WireS", tie_path(C, ax, mdir, r_obj, dmesh, rnd, loose=loose), grp, arm, smooth=1))
        zt = -0.42
        yt = ym + 0.0035
        if not (stage == "Torn" and arm == "X"):
            pts = [(rc * 0.5, -rc - 0.001, zt), (rc + 0.02, yt, zt), (0.2, yt, zt), (XP - re - 0.02, yt, zt),
                   (XP - re * 0.5, -re - 0.001, zt)]
            items.append(along("WireM", [xf(np.array([p]), R)[0] for p in pts], "tw", arm, smooth=1))
        else:
            pts = [(rc * 0.5, -rc - 0.001, zt), (rc + 0.02, yt, zt)]
            for k in range(1, 5):
                t = k / 4.0
                pts.append((rc + 0.04 + 0.18 * t, yt - 0.04 * t, max(Z0 + 0.004, zt - 0.07 * t)))
            items.append(along("WireM", [xf(np.array([p]), R)[0] for p in pts], "tw", arm, smooth=1))
        if arm == "X":
            fx = lambda s, n, z: np.stack([s, ym + n, z], axis=1)  # noqa: E731
        else:
            fx = lambda s, n, z: np.stack([ym + n, s, z], axis=1)  # noqa: E731
        span0, span1 = ym, XP
        uv0 = (rnd.uniform(0, 1), rnd.uniform(0, 1))
        H = MTOP - MBOT

        def bow_f(s, z, side, bow=0.04 if stage == "Sagging" else 0.025, span0=span0, span1=span1, H=H):
            u = u_of(s, rc, span1 - re)
            wv = np.clip((z - MBOT) / H, 0.0, 1.0)
            dn = bow * np.sin(np.pi * u) * np.sin(np.pi * np.clip(wv * 1.1, 0, 1)) ** 0.8
            dz = -0.03 * np.sin(np.pi * u) * wv ** 2
            return np.zeros_like(s), dn, dz
        if stage == "Taut":
            bands, deform, rip = [([span0, 0.2, span1], grid(MBOT, MTOP, 0.5))], None, None
        elif stage == "Sagging" or arm == "Y":
            bands, deform, rip = [(grid(span0, span1, 0.125), grid(MBOT, MTOP, 0.22))], bow_f, None
        else:
            hl, hr, rs, rt = 0.0, 0.40, 0.2, 0.2
            tear = tear_deform(hl, hr, rs, rt, MBOT, curl=9.0, rnd=rnd)
            xs_lo = sorted(set(round(v, 6) for v in [span0] + grid(hl, rs, 0.05) + grid(rs, hr, 0.05) + [span1]))
            zs_lo = grid(MBOT, rt, 0.1) + [rt + 0.12]
            bands = [(xs_lo, zs_lo), (grid(span0, span1, 0.125), [rt + 0.12] + grid(rt + 0.12, MTOP, 0.3)[1:])]
            rip = (rs, rt)

            def deform(s, z, side, tear=tear, bow_f=bow_f):
                a_ = tear(s, z, side)
                b_ = bow_f(s, z, side)
                return a_[0] + b_[0], a_[1] + b_[1], a_[2] + b_[2]
            start = xf(np.array([(rs, ym - 0.02, MBOT + 0.1)]), np.eye(4))[0]
            items.append(along("WireL", loose_wire_path(start, (0.2, -1.0, -0.2), 0.2, rnd, droop=0.6), "mesh", arm,
                               smooth=0))
        items.append(sheet(bands, fx, uv0, deform, rip, "mesh", arm))

    fields = []
    if stage != "Taut":
        sag = 0.03 if stage == "Sagging" else 0.045

        def rail_sag(V, it):
            if it.group.startswith("post") or not it.arm:
                return V
            s = V[:, 0] if it.arm == "X" else V[:, 1]
            u = u_of(s, rc, XP - re)
            wz = smoothstep(TOP - 0.6, TOP - 0.04, V[:, 2])
            out = V.copy()
            out[:, 2] -= sag * np.sin(np.pi * u) ** 1.2 * wz
            return out
        fields.append(rail_sag)
    if stage == "Torn":
        dvec = unit([0.02, 1.0, 0.0])

        def post_bend(V, it):
            if it.arm != "X" and it.group != "post_c":
                return V
            if it.group == "post_c":
                return V
            wgt = smoothstep(rc + 0.05, XP - re - 0.01, V[:, 0])
            if it.group == "post_e":
                wgt = np.ones(len(V))
            g_ = bend_profile(V[:, 2], -0.2, 0.45, 7.0) * wgt
            return V + g_[:, None] * dvec[None, :]
        fields.append(post_bend)
    for it in items:
        for f in fields:
            it.V = f(it.V, it)
    return finish_mesh("ChainLinkCorner%s%s" % (weight, stage), items, mats)


def build_gate(mats, seed):
    """Frame (end posts, guide, latch) and SlideLeaf, built closed; returns (frame, leaf)."""
    rnd = random.Random(seed)
    fr, lf = [], []
    for sx in (-1, 1):
        x = sx * 1.45
        fr.append(place("PG2", m_trans((x, 0.0, Z0)) @ m_rot("Z", rnd.uniform(0, 360))))
        fr.append(place("CapL", m_trans((x, 0.0, Z0 + 1.99))))
        fr.append(place("FootG", m_trans((x - sx * 0.008, 0.0, Z0)) @ m_rot("Z", rnd.uniform(-4, 4))))
        fr.append(place("WeldRingP", m_trans((x, 0.0, Z0 + 0.012)) @ m_scale(R_PG / R_PH * 0.98, R_PG / R_PH * 0.98,
                                                                               1.0)))
    fr.append(place("Guide", m_trans((1.45, 0.0, 1.42))))
    fr.append(place("Latch", m_trans((-1.45, 0.0, 0.55))))
    # leaf
    yl = GATE_Y
    zb, ztp = -0.36, 1.42
    for zr in (zb, ztp):
        lf.append(place("GRail", m_trans((-1.451, yl, zr)) @ m_rot("X", rnd.uniform(0, 360))))
    for x in (-1.43, 0.0, 1.43):
        lf.append(stretch_x("GVert", zb, ztp, m_trans((x, yl, 0.0)) @ m_rot("Y", -90) @ m_rot("X", rnd.uniform(0, 360))))
        for zr, flip in ((zb + R_RH + 0.001, 0), (ztp - R_RH - 0.001, 180)):
            lf.append(place("WeldRingR", m_trans((x, yl, zr)) @ m_rot("Y", 90 + flip)))
    A = np.array([-1.43, yl, zb])
    B = np.array([1.43, yl, ztp])
    d = unit(B - A)
    side = np.cross(d, [0.0, 1.0, 0.0])
    M = m_frame(d, [0.0, 1.0, 0.0], side, A)
    lf.append(stretch_x("GBrace", 0.02, np.linalg.norm(B - A) - 0.02, M))
    for t in (0.035, 0.5, 0.965):
        c = A + d * t * np.linalg.norm(B - A)
        lf.append(place("WeldRingR", m_frame(d, [0.0, 1.0, 0.0], side, c) @ m_scale(1.0, 0.82, 0.82)))
    for x in (-1.15, 1.15):
        lf.append(place("Wheel", m_trans((x, yl, -0.435)) @ m_rot("X", 90) @ m_rot("Z", rnd.uniform(0, 360))))
        lf.append(place("Bracket", m_trans((x, yl, -0.435))))
    lf.append(place("Handle", m_trans((-1.43 + R_RH + 0.004, yl + R_RH - 0.004, 0.42)) @ m_rot("Z", 180)))
    ym = yl - R_RH - 0.006
    ties = []
    for x in (-1.1, -0.55, 0.0, 0.55, 1.1):
        ties.append(((x + 0.06, yl, ztp), (1, 0, 0)))
        ties.append(((x - 0.06, yl, zb), (1, 0, 0)))
    for x in (-1.43, 1.43):
        for zz in (0.1, 0.75):
            ties.append(((x, yl, zz), (0, 0, 1)))
    for C, ax in ties:
        lf.append(along("WireS", tie_path(C, ax, (0, -1, 0), R_RH, yl - ym, rnd), smooth=1))
    fx = lambda s, n, z: np.stack([s, ym + n, z], axis=1)  # noqa: E731
    lf.append(sheet([([-1.43, -0.5, 0.5, 1.43], [zb, 0.5, 1.40])], fx, (0.37, 0.11)))
    frame = finish_mesh("GateFrame", fr, mats)
    leaf = finish_mesh("GateLeaf", lf, mats)
    return frame, leaf


# ---------------------------------------------------------------- reports, export

def stats(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(obj.matrix_world.translation)
    return co.min(axis=0), co.max(axis=0), len(me.polygons)


def export_single(fname, obj):
    saved = (obj.name, obj.data.name)
    obj.name = "DMG0"
    obj.data.name = "DMG0"
    tk.export_fbx([obj], os.path.join(ASSETS, fname))
    obj.name, obj.data.name = saved


def drop_unused_slots(obj):
    used = set(np.unique([p.material_index for p in obj.data.polygons]))
    for i in reversed(range(len(obj.data.materials))):
        if i not in used and i == len(obj.data.materials) - 1:
            obj.data.materials.pop(index=i)


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


def lineup(entries, cam, path, res=(2000, 900), samples=96):
    """entries: (object, (x, y), z rotation in degrees). Renders copies of them, everything else in ALL hidden."""
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


def image_array(path):
    img = bpy.data.images.load(path)
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return a


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("out", w, h, alpha=True)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def unity_light():
    """The light the vanilla references were rendered with in Unity (see sandbags.py): warm sun, trilight ambient,
    a dark floor."""
    world = bpy.context.scene.world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.03, 0.028, 0.025, 1.0)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.17, 0.21, 0.32, 1.0)
    mid = cr.elements.new(0.5)
    mid.color = (0.1, 0.1, 0.1, 1.0)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs[2], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    sun = tk.link(bpy.data.objects.new("CmpSun", bpy.data.lights.new("CmpSun", "SUN")))
    sun.data.color = (1.0, 0.93, 0.84)
    sun.data.energy = 9.0
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = Vector((-0.38, 0.66, -0.64)).to_track_quat("-Z", "Y").to_euler()
    mat, g = tk.new_material("CmpFloor")
    tk.finish(mat, g, (0.073, 0.069, 0.06), 0.0, 0.9)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20.0)
    bmesh.ops.translate(bm, vec=(0, 0, Z0), verts=bm.verts)
    fl = tk.mesh_object("CmpFloor", bm, mat)
    return sun, fl


def compare_vanilla(entries, ref_path, out_path):
    scene = bpy.context.scene
    for o in ALL:
        o.hide_render = True
    hidden = [o for o in scene.objects if o.type == "LIGHT" or o.name in ("Floor", "ScaleFigure", "ScaleHead")]
    for o in hidden:
        o.hide_render = True
    old_world = scene.world
    scene.world = bpy.data.worlds.new("Cmp")
    sun, fl = unity_light()
    temps = []
    for obj, (x, y), rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = (x, y, 0.0)
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    cam = tk.camera("CmpCam", (1.8, -4.6, 2.2), (0.0, 0.4, 0.6), lens=50)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle_y = math.radians(34.0)
    ours = os.path.join(PREVIEWS, "_cmp_ours.png")
    tk.render(cam, ours, res=(1300, 1000), samples=96)
    a = image_array(ours)
    ref = image_array(ref_path)
    both = np.concatenate([ref[:, :1300, :3], a[:, :, :3]], axis=1)
    save_rgb(both, out_path)
    os.remove(ours)
    for t in temps:
        bpy.data.objects.remove(t)
    bpy.data.objects.remove(sun)
    bpy.data.objects.remove(fl)
    scene.world = old_world
    for o in hidden:
        o.hide_render = False


# ================================================================ main

tk.reset_scene()
bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
build_kit()
layout_kit()
if MODE == "kit":
    tk.preview_stage()
    cam = tk.camera("KitCam", (3.5, -6.0, 3.0), (3.5, 1.0, 0.5), lens=30)
    tk.render(cam, os.path.join(PREVIEWS, "dbg_chainlink_kit.png"), res=(1600, 1000), samples=48)
    sys.exit(0)

kit, PATHS = bake_kit()
T = extract_templates(kit)
bpy.data.objects.remove(kit)
MATERIAL = tk.baked_material(MAT, PATHS)
assert MATERIAL.name == MAT, MATERIAL.name
MPATHS = mesh_texture()
MESHMAT = mesh_material(MPATHS)
assert MESHMAT.name == MESH_MAT, MESHMAT.name
MATS = [MATERIAL, MESHMAT]
log("baked", PATHS, MPATHS)

BUILT = {}
REPORT = []
seed = 11
for kind in ("Panel", "Tall"):
    for weight in ("Light", "Heavy"):
        for stg in STAGES:
            seed += 7
            obj = build_panel(kind, weight, stg, MATS, seed)
            BUILT[(kind, weight, stg)] = obj
            ALL.append(obj)
for weight in ("Light", "Heavy"):
    for stg in STAGES:
        seed += 7
        obj = build_corner(weight, stg, MATS, seed)
        BUILT[("Corner", weight, stg)] = obj
        ALL.append(obj)

for (kind, weight, stg), obj in BUILT.items():
    fname = "ChainLink%s%s%s.fbx" % (kind, weight, stg)
    export_single(fname, obj)
    lo, hi, tris = stats(obj)
    REPORT.append("%s: DMG0 tris %d bounds %s..%s" % (fname, tris, lo.round(3), hi.round(3)))

frame, leaf = build_gate(MATS, 99)
tk.mark_part(leaf, "SlideLeaf")
model = tk.join([frame, leaf], "Frame")
model.data.name = "Frame"
PIVOT = (0.0, GATE_Y, Z0)
leaf = tk.split_part(model, "SlideLeaf", PIVOT)
for o in (model, leaf):
    if "trap_part" in o.data.attributes:
        o.data.attributes.remove(o.data.attributes["trap_part"])
drop_unused_slots(model)
ALL += [model, leaf]
tk.export_fbx([model, leaf], os.path.join(ASSETS, "ChainLinkGate.fbx"))
bpy.context.view_layer.update()
for o in (model, leaf):
    lo, hi, tris = stats(o)
    REPORT.append("ChainLinkGate.fbx: %s tris %d bounds %s..%s mats %s" % (o.name, tris, lo.round(3), hi.round(3),
                                                                         [m.name for m in o.data.materials]))
REPORT.append("ChainLinkGate.fbx: SlideLeaf origin %s (parent %s), opens +X by %.1f m" % (
    tuple(round(c, 3) for c in leaf.matrix_world.translation), leaf.parent.name, GATE_SLIDE))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
stage()
B = BUILT
for kind in ("Panel", "Tall"):
    ents = []
    for i, (weight, stg) in enumerate([(w, s) for w in ("Light", "Heavy") for s in STAGES]):
        ents.append((B[(kind, weight, stg)], (-3.5 + i * 1.4, 0.0), 0))
    figure_at(5.0, 0.6)
    zc = 0.6 if kind == "Panel" else 1.0
    lineup(ents, tk.camera("St" + kind, (1.0, -10.5, 2.4 + (0.6 if kind == "Tall" else 0)), (0.0, 0.0, zc), lens=35),
           os.path.join(PREVIEWS, "chainlink_%s_stages.png" % kind.lower()), res=(2200, 1000))
    lineup(ents, tk.camera("Bk" + kind, (-1.0, 10.5, 2.4 + (0.6 if kind == "Tall" else 0)), (0.0, 0.0, zc), lens=35),
           os.path.join(PREVIEWS, "chainlink_%s_stages_back.png" % kind.lower()), res=(2200, 1000))
ents = [(B[("Corner", w, s)], (-3.0 + i * 1.3, 0.0), 0) for i, (w, s) in
        enumerate([(w, s) for w in ("Light", "Heavy") for s in STAGES])]
lineup(ents, tk.camera("Corners", (-2.0, -9.0, 3.4), (0.4, 0.4, 0.5), lens=35),
       os.path.join(PREVIEWS, "chainlink_corners.png"), res=(2200, 1000))
lineup(ents, tk.camera("CornersB", (3.5, 8.5, 3.4), (0.4, 0.4, 0.5), lens=35),
       os.path.join(PREVIEWS, "chainlink_corners_back.png"), res=(2200, 1000))
figure_at(-2.6, -0.8)
lineup([(B[("Panel", "Light", "Taut")], (0.0, 0.0), 0)], tk.camera("Close", (0.7, -1.6, 1.0), (0.0, 0.0, 0.6), lens=35),
       os.path.join(PREVIEWS, "chainlink_light_close.png"), res=(1200, 1200))
lineup([(B[("Panel", "Heavy", "Torn")], (0.0, 0.0), 0)], tk.camera("CloseT", (0.9, -2.0, 0.9), (0.0, 0.0, 0.3), lens=35),
       os.path.join(PREVIEWS, "chainlink_heavy_torn_close.png"), res=(1200, 1200))
lineup([(B[("Panel", "Light", "Torn")], (0.0, 0.0), 0)], tk.camera("CloseL", (-0.8, -2.0, 0.6), (0.0, 0.0, 0.2), lens=35),
       os.path.join(PREVIEWS, "chainlink_light_torn_close.png"), res=(1200, 1200))
# gate, closed and open
for o in ALL:
    o.hide_render = True
model.hide_render = leaf.hide_render = False
figure_at(-2.8, -1.2)
cam = tk.camera("Gate", (2.2, -6.5, 2.4), (0.6, 0.0, 0.5), lens=35)
tk.render(cam, os.path.join(PREVIEWS, "chainlink_gate_closed.png"), res=(1800, 1000))
leaf.location.x += GATE_SLIDE
bpy.context.view_layer.update()
cam2 = tk.camera("GateOpen", (3.4, -7.5, 2.6), (1.4, 0.0, 0.5), lens=32)
tk.render(cam2, os.path.join(PREVIEWS, "chainlink_gate_open.png"), res=(1800, 1000))
tk.render(tk.camera("GateBack", (1.0, 6.5, 2.4), (1.4, 0.0, 0.5), lens=32),
          os.path.join(PREVIEWS, "chainlink_gate_open_back.png"), res=(1800, 1000))
leaf.location.x -= GATE_SLIDE
bpy.context.view_layer.update()
tk.render(tk.camera("GateGuide", (2.3, -0.9, 1.75), (1.45, 0.1, 1.38), lens=45),
          os.path.join(PREVIEWS, "chainlink_gate_guide.png"), res=(1000, 1000))
model.hide_render = leaf.hide_render = True
# a run of three panels and a corner turning to +Y, with one more panel up the Y side
run = [(B[("Panel", "Light", "Taut")], (-1.0, 0.0), 0), (B[("Panel", "Light", "Taut")], (0.0, 0.0), 0),
       (B[("Panel", "Light", "Sagging")], (1.0, 0.0), 0), (B[("Corner", "Light", "Taut")], (2.0, 0.0), 90),
       (B[("Panel", "Light", "Taut")], (2.0, 1.0), 90)]
figure_at(-2.2, -1.0)
lineup(run, tk.camera("Run", (-1.6, -5.8, 2.6), (1.0, 0.4, 0.5), lens=30), os.path.join(PREVIEWS, "chainlink_run.png"),
       res=(2000, 1100))
lineup(run, tk.camera("RunB", (4.6, 4.8, 2.6), (1.0, 0.2, 0.5), lens=30), os.path.join(PREVIEWS, "chainlink_run_back.png"),
       res=(2000, 1100))
runh = [(B[("Panel", "Heavy", "Taut")], (-1.0, 0.0), 0), (B[("Panel", "Heavy", "Sagging")], (0.0, 0.0), 0),
        (B[("Panel", "Heavy", "Taut")], (1.0, 0.0), 0), (B[("Corner", "Heavy", "Taut")], (2.0, 0.0), 90),
        (B[("Panel", "Heavy", "Taut")], (2.0, 1.0), 90)]
lineup(runh, tk.camera("RunH", (-1.6, -5.8, 2.6), (1.0, 0.4, 0.5), lens=30),
       os.path.join(PREVIEWS, "chainlink_run_heavy.png"), res=(2000, 1100))
REF = os.path.join(os.path.dirname(PREVIEWS), "ref-chainlinkfencemiddleprefab.png")
if os.path.exists(REF):
    compare_vanilla([(B[("Panel", "Light", "Taut")], (0.0, 0.0), 0)], REF,
                    os.path.join(PREVIEWS, "chainlink_vs_vanilla.png"))

# ---------------------------------------------------------------- icon
icon_obj = B[("Panel", "Light", "Taut")]
for o in ALL:
    o.hide_render = o is not icon_obj
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not icon_obj}
tk.icon(tk.camera("Icon", (2.3, -2.5, 1.25), (0.02, 0.0, 0.5), lens=52), ICON, hide=hide, target=(0.0, 0.0, 0.5))
log("icon", ICON)

# ---------------------------------------------------------------- check the files as the importer sees them
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
            parts.append("%s tris %d mats %s x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f parent %s origin %s" % (
                o.name, tris, [m.name for m in o.data.materials], co[:, 0].min(), co[:, 0].max(), co[:, 1].min(),
                co[:, 1].max(), co[:, 2].min(), co[:, 2].max(), o.parent.name if o.parent else None,
                tuple(round(c, 3) for c in o.matrix_world.translation)))
        else:
            parts.append("%s %s" % (o.name, o.type))
    log("reimport", fname, "|", " || ".join(parts))
log("done")
