"""Picket Fence (Fortifications Expanded): a 1.1 m white-grey painted wooden picket fence, cheap early dressing that
slows a few zombies. All pieces share one baked material, `PicketFence` (PicketFence_Albedo.png, _Normal.png, _RMOM.png,
2048).

    PicketFenceSection.fbx   1 m cell: DMG0 intact, DMG1 slats kicked out and a post leaning, DMG2 collapsed wreck, FX
    PicketFenceCorner.fbx    the same three stages; a stout post at the origin with fence toward +X and +Y
    PicketFenceGate.fbx      2 wide swing gate: Frame (two posts), LeftLeaf and RightLeaf (origins on the hinge axes at
                             x = -+0.875, y = -0.035, z = -0.5); the leaves swing out toward -Y

Section: eight slats (every one a different board: pointed, flat, dog-eared, warped, a raw grey replacement, a wide one,
a short one) with 3.5 cm gaps, nailed to two rails (z 0.27 and 0.78 above the ground) on a post behind them. Paint
flakes to grey wood, algae and grime near the foot, bent and missing nails. The fence line is y = 0, slat fronts at
y = -0.035, the post at y 0.03 .. 0.12 (behind the rails, so a run of cells has one post a metre).

    blender -b --factory-startup --python picket_fence.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default), reuse (assemble from the last bake), export (no renders)
"""
import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fencekit as fk  # noqa: E402
import trapkit as tk  # noqa: E402
from fencekit import Z0, log, m_about, m_r, m_s, m_t  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

MAT_NAME = "PicketFence"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__", "picket_fence_kit.npz")
HX = 0.875  # gate hinge axis
HY = -0.035  # ... and its y (the leaf's front face)
RAIL_Z = (0.27, 0.78)
RAIL_Y = 0.0075
SLAT_Y = -0.025  # slat centre (front face -0.035, back -0.015)
POST_Y = 0.075
SLAT_X = [-0.4375 + 0.125 * i for i in range(8)]
ORDER = ["S0", "S4", "S1", "S6", "S2", "S5", "S3", "S7"]

# ================================================================ the kit

SLATS = {  # name: (width, length, top, seed, paint, wear, extra)
    "S0": (0.090, 1.080, "point", 11, 0.82, 0.4, dict(bow=0.004)),
    "S1": (0.090, 1.060, "flat", 12, 0.76, 0.5, dict(bow=0.003, twist=0.04)),
    "S2": (0.090, 1.100, "ear", 13, 0.72, 0.5, dict(bow=0.005)),
    "S3": (0.095, 1.050, "point", 14, 0.66, 0.6, dict(bow=0.009, twist=0.09)),
    "S4": (0.090, 1.070, "flat", 15, 0.0, 0.9, dict(bow=0.002)),   # raw replacement: weathered grey bare wood
    "S5": (0.090, 1.090, "point", 16, 0.52, 0.8, dict(bow=0.004, twist=-0.05)),
    "S6": (0.116, 1.040, "flat", 17, 0.30, 0.8, dict(bow=0.002)),  # a wide replacement, little paint
    "S7": (0.090, 0.960, "point", 18, 0.6, 0.7, dict(bow=0.003)),  # short
}
STUBS = {"BS0": (0.62, 21), "BS1": (0.50, 22), "BS2": (0.40, 23), "BS3": (0.30, 24), "BS4": (0.45, 25)}
TOPS = {"BT0": (0.50, 31), "BT1": (0.46, 32), "BT2": (0.55, 33), "BT3": (0.42, 34), "BT4": (0.50, 35)}
LAYOUT = {"x": 0.0, "y": 0.0, "row": 0}


def put(obj):
    """Lays kit parts out in rows, apart, so the baked occlusion of one doesn't darken the next."""
    if LAYOUT["x"] > 3.6:
        LAYOUT["x"] = 0.0
        LAYOUT["y"] += 1.5
    obj.location = (LAYOUT["x"], LAYOUT["y"], 0.0)
    LAYOUT["x"] += 0.3
    return obj


def top_cuts(w, L, top):
    s = math.sin(math.radians(55.0)), math.cos(math.radians(55.0))
    if top == "point":
        return [((0, 0, L), (s[0], 0, s[1]), fk.FT_END), ((0, 0, L), (-s[0], 0, s[1]), fk.FT_END)]
    if top == "ear":
        r = math.sqrt(0.5)
        return [((w / 2, 0, L - 0.05), (r, 0, r), fk.FT_END), ((-w / 2, 0, L - 0.05), (-r, 0, r), fk.FT_END)]
    return []


def build_kit(mats):
    wood, iron, wire = mats
    for name, (w, L, top, seed, paint, wear, kw) in SLATS.items():
        obj = fk.board(name, wood, w, 0.02, L, seed, nw=2, nt=2, chamfer=0.0035, step=0.3, rough=0.0,
                       cuts=top_cuts(w, L, top), **kw)
        fk.kit_part(name, put(obj), paint=paint, wear=wear, ground=0.8, seed=seed * 1.37, kind="slat", width=w,
                    length=L)
    for name, (L, seed) in STUBS.items():
        obj = fk.board(name, wood, 0.09, 0.02, L, seed, nw=3, nt=2, chamfer=0.0035, step=0.3, jag_top=0.045,
                       bow=0.003)
        fk.kit_part(name, put(obj), paint=0.7, wear=0.7, ground=0.9, seed=seed * 1.37, kind="stub", length=L)
    for name, (L, seed) in TOPS.items():
        obj = fk.board(name, wood, 0.09, 0.02, L, seed, nw=3, nt=2, chamfer=0.0035, step=0.3, jag_bot=0.045,
                       bow=0.003, cuts=top_cuts(0.09, L, "point"))
        fk.kit_part(name, put(obj), paint=0.6, wear=0.7, ground=0.0, seed=seed * 1.37, kind="top", length=L)
    # posts: section, corner, gate; the snapped stump and its top
    cap = lambda h, L_, a=35.0: [((0, 0, L_), (math.sin(math.radians(a)) * sx, math.sin(math.radians(a)) * sy,  # noqa: E731
                                              math.cos(math.radians(a))), fk.FT_END)
                                 for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    posts = {"PP0": (0.090, 1.120, 41, dict(bow=0.004, twist=0.03)), "PC0": (0.120, 1.180, 42, dict(bow=0.003)),
             "PG0": (0.110, 1.200, 43, dict(bow=0.003, twist=-0.02))}
    for name, (w, L, seed, kw) in posts.items():
        obj = fk.board(name, wood, w, w, L, seed, nw=3, nt=3, chamfer=0.006, step=0.3, rough=0.0,
                       cuts=cap(w, L), **kw)
        fk.kit_part(name, put(obj), paint=0.65, wear=0.55, ground=1.0, seed=seed * 1.37, kind="post", length=L)
    obj = fk.board("PS0", wood, 0.09, 0.09, 0.44, 44, nw=3, nt=3, chamfer=0.006, step=0.3, jag_top=0.07, bow=0.003)
    fk.kit_part("PS0", put(obj), paint=0.5, wear=0.7, ground=1.0, seed=44 * 1.37, kind="stump")
    obj = fk.board("PT0", wood, 0.09, 0.09, 0.5, 45, nw=3, nt=3, chamfer=0.006, step=0.3, jag_bot=0.07, cuts=cap(0.09, 0.5))
    fk.kit_part("PT0", put(obj), paint=0.5, wear=0.7, ground=0.0, seed=45 * 1.37, kind="stump top")
    obj = fk.board("PC1", wood, 0.12, 0.12, 0.46, 46, nw=3, nt=3, chamfer=0.006, step=0.3, jag_top=0.08, bow=0.003)
    fk.kit_part("PC1", put(obj), paint=0.5, wear=0.7, ground=1.0, seed=46 * 1.37, kind="corner stump")
    # rails (built along Z, 0.09 wide, 0.045 thick; placed on edge along X)
    rails = {"RA0": (0.996, 51, dict(bow=0.003, twist=0.02)), "RA1": (0.996, 52, dict(bow=0.004, twist=-0.03)),
             "RB0": (0.446, 53, dict(bow=0.002)), "RB1": (0.446, 54, dict(bow=0.003)),
             "RG0": (0.855, 55, dict(bow=0.003)), "RG1": (0.855, 56, dict(bow=0.004, twist=0.03)),
             "RD0": (0.93, 57, dict(bow=0.003))}
    for name, (L, seed, kw) in rails.items():
        w, t = (0.07, 0.032) if name.startswith("RD") else (0.09, 0.045)
        obj = fk.board(name, wood, w, t, L, seed, nw=2, nt=2, chamfer=0.005, step=0.35, **kw)
        fk.kit_part(name, put(obj), paint=0.58, wear=0.7, ground=0.0, seed=seed * 1.37, kind="rail", length=L)
    obj = fk.board("RJ0", wood, 0.09, 0.045, 0.62, 58, nw=2, nt=2, chamfer=0.005, step=0.35, jag_top=0.05)
    fk.kit_part("RJ0", put(obj), paint=0.4, wear=0.8, ground=0.0, seed=58 * 1.37, kind="broken rail", length=0.62)
    obj = fk.board("RK0", wood, 0.09, 0.045, 0.42, 59, nw=2, nt=2, chamfer=0.005, step=0.35, jag_bot=0.05)
    fk.kit_part("RK0", put(obj), paint=0.4, wear=0.8, ground=0.0, seed=59 * 1.37, kind="broken rail", length=0.42)
    # iron: nails (axis +Z, head on the surface), a bent-over nail, strap hinge, pintle, slide bolt and keeper
    fk.kit_part("NAIL", put(fk.iron_nail("NAIL", iron)), kind="nail")
    fk.kit_part("NAILB", put(fk.iron_nail("NAILB", iron, "bent")), kind="bent nail")
    # strap hinge: strap along +X lying on the plane y = 0..-0.005, eye barrel on the axis (the origin)
    strap = tk.box("strap", (0.34, 0.005, 0.034), (0.17, -0.0025, 0.0), iron)
    taper = tk.box("tip", (0.05, 0.005, 0.022), (0.345, -0.0025, 0.0), iron)
    eye = tk.cylinder("eye", 0.0115, -0.026, 0.026, iron, segments=8)
    fk.kit_part("HINGE", put(tk.join([strap, taper, eye], "HINGE")), kind="strap hinge")
    # pintle: pin on the axis (origin), bridge plate on the post front (y 0..+0.005)
    pin = tk.cylinder("pin", 0.0068, -0.05, 0.05, iron, segments=8)
    plate = tk.box("plate", (0.06, 0.005, 0.07), (0.03, 0.0025, 0.0), iron)
    fk.kit_part("PINTLE", put(tk.join([pin, plate], "PINTLE")), kind="pintle")
    base = tk.box("base", (0.11, 0.004, 0.034), (0.0, -0.002, 0.0), iron)
    g1 = tk.cylinder("g1", 0.007, -0.04, -0.012, iron, segments=6, axis="X", center=(-0.012, 0.0))
    g2 = tk.cylinder("g2", 0.007, 0.012, 0.04, iron, segments=6, axis="X", center=(-0.012, 0.0))
    rod = tk.cylinder("rod", 0.0048, -0.18, 0.04, iron, segments=6, axis="X", center=(-0.012, 0.0))
    fk.kit_part("LATCH", put(tk.join([base, g1, g2, rod], "LATCH")), kind="slide bolt")
    kb = tk.box("kb", (0.05, 0.004, 0.03), (0.0, -0.002, 0.0), iron)
    kl = tk.torus("kl", 0.011, 0.0034, (0.0, -0.014, 0.0), iron, major_segments=10, minor_segments=4)
    kl.rotation_euler = (0.0, math.radians(90.0), 0.0)
    fk.kit_part("KEEPER", put(tk.join([kb, kl], "KEEPER")), kind="keeper loop")


# ================================================================ pieces

def lean_matrix(deg_x, deg_z, pivot):
    return m_about(m_r("Z", deg_z) @ m_r("X", deg_x), pivot)


def basis(zaxis, yaxis=(0, 1, 0)):
    z = fk.unit(zaxis)
    y = np.asarray(yaxis, float)
    y = fk.unit(y - z * y.dot(z))
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = x, y, z
    return M


class Builder:
    def __init__(self, asm, seed):
        self.A = asm
        self.rnd = random.Random(seed)
        self.items = []

    def add(self, name, M, tag=""):
        self.items.append(self.A.place(name, M, tag))

    def slat(self, name, x, L=np.eye(4), z0=0.05, nails=2, yaw=None, y=SLAT_Y, nail_set=(0, 1)):
        r = self.rnd
        yaw = r.uniform(-1.2, 1.2) if yaw is None else yaw
        z0 = z0 + r.uniform(-0.008, 0.008)
        self.add(name, L @ m_t(x + r.uniform(-0.003, 0.003), y + r.uniform(-0.002, 0.002), z0) @ m_r("Z", yaw)
                 @ m_r("X", r.uniform(-0.6, 0.6)) @ m_r("Y", r.uniform(-0.6, 0.6)), "slat")
        for k in nail_set:
            self.nail(L, x + r.uniform(-0.016, 0.016), -0.035, RAIL_Z[k] + r.uniform(-0.012, 0.012))

    def nail(self, L, x, y, z, bent=False, face="front"):
        r = self.rnd
        if face == "front":
            M = m_t(x, y, z) @ m_r("X", 90) @ m_r("Z", r.uniform(0, 360)) @ m_r("X", r.uniform(-9, 9)) @ m_r("Y", r.uniform(-9, 9))
        else:
            M = m_t(x, y, z) @ m_r("X", -90) @ m_r("Z", r.uniform(0, 360)) @ m_r("X", r.uniform(-9, 9)) @ m_r("Y", r.uniform(-9, 9))
        if bent:
            M = m_t(x, y, z) @ m_r("X", 90) @ m_r("Z", r.uniform(0, 360))
        self.add("NAILB" if bent else "NAIL", L @ M, "iron")

    def rail(self, name, zc, x0=-0.498, L=np.eye(4), y=RAIL_Y, yaw=0.0, dip=0.0):
        self.add(name, L @ m_t(x0, y, zc) @ m_r("Z", yaw) @ m_r("Y", 90 + dip), "rail")

    def clamp_center(self, cx, cy, ex, ey, lim=0.485):
        return (min(max(cx, -(lim - ex)), lim - ex), min(max(cy, -(lim - ey)), lim - ey))

    def rail_on_ground(self, name, cx, cy, yaw, length, lift=0.0, flip=False):
        """A rail lying flat on the ground, centred at (cx, cy), its length along +X turned by yaw."""
        a = math.radians(yaw)
        d = np.array((math.cos(a), math.sin(a)))
        cx, cy = self.clamp_center(cx, cy, abs(d[0]) * length / 2 + 0.01, abs(d[1]) * length / 2 + 0.05)
        x0, y0 = np.array((cx, cy)) - d * length / 2
        self.add(name, m_t(x0, y0, 0.0225 + lift) @ m_r("Z", yaw) @ m_r("Y", 90) @ m_r("Z", -90 if flip else 90), "rail")

    def lying(self, name, cx, cy, yaw, thick=0.01, tilt=0.0, face_up=True, lift=0.0):
        """A slat or top lying on the ground, centred at (cx, cy), its length pointing along -Y turned by yaw."""
        length = self.A.T[name].meta["length"]
        a = math.radians(yaw)
        d = np.array((math.sin(a), -math.cos(a)))
        cx, cy = self.clamp_center(cx, cy, abs(d[0]) * length / 2 + 0.05, abs(d[1]) * length / 2 + 0.05)
        x0, y0 = np.array((cx, cy)) - d * length / 2
        M = m_t(x0, y0, thick + lift) @ m_r("Z", yaw) @ m_r("X", 90) @ m_r("Z", 180 if face_up else 0) @ m_r("X", tilt)
        self.add(name, M, "slat")


def section(A, stage):
    b = Builder(A, 100 + stage)
    pivot = (0.01, POST_Y, 0.0)
    if stage == 0:
        L = np.eye(4)
    elif stage == 1:
        L = lean_matrix(-7.0, 2.2, pivot)
    else:
        L = lean_matrix(-12.0, 3.0, pivot)
    r = b.rnd
    if stage < 2:
        b.add("PP0", L @ m_t(0.01, POST_Y, 0.0) @ m_r("Z", 3.0), "post")
        b.rail("RA0", RAIL_Z[0], L=L, yaw=0.0 if stage == 0 else 0.8)
        b.rail("RA1", RAIL_Z[1], L=L, yaw=0.0, dip=0.0 if stage == 0 else 1.6)
        for k in (0, 1):
            for dx in (-0.018, 0.022):
                b.nail(L, 0.01 + dx, POST_Y + 0.045, RAIL_Z[k] + r.uniform(-0.01, 0.01), face="back")
    else:
        b.add("PS0", L @ m_t(0.01, POST_Y, 0.0) @ m_r("Z", 3.0), "post")
        b.rail("RA0", RAIL_Z[0], L=L, yaw=1.2)
        for dx in (-0.018, 0.022):
            b.nail(L, 0.01 + dx, POST_Y + 0.045, RAIL_Z[0] + r.uniform(-0.01, 0.01), face="back")
    if stage == 0:
        for i, name in enumerate(ORDER):
            b.slat(name, SLAT_X[i], nail_set=(0, 1) if i != 5 else (1,))
        # one slat nailed on a slant, one nail bent over
        b.nail(L, SLAT_X[2] + 0.012, -0.035, RAIL_Z[1] + 0.03)
    elif stage == 1:
        # slat 0, 3, 5 stay; slat 1 snapped (stub on the rail, top lying), 2 hanging by one nail, 4 kicked out, 6 gone
        for i in (0, 3, 5, 7):
            b.slat(ORDER[i], SLAT_X[i], L=L, nail_set=(0, 1) if i != 5 else (0,))
        b.slat("BS0", SLAT_X[1], L=L, z0=0.05, nail_set=(0, 1))
        # hanging by its top nail: swings out toward -Y about the nail
        piv = (SLAT_X[2], -0.035, RAIL_Z[1])
        H = m_about(m_r("X", -38.0) @ m_r("Z", 4.0), piv)
        b.slat(ORDER[2], SLAT_X[2], L=L @ H, nail_set=(1,), yaw=0.0)
        # slat 6 is gone: its nails stick out of the rails; slat 4 lies on the ground, kicked out
        for k in (0, 1):
            b.nail(L, SLAT_X[6] + r.uniform(-0.012, 0.012), -0.035, RAIL_Z[k] + r.uniform(-0.01, 0.01), bent=True)
        # the kicked-out slat leans against the fence, foot well out in front
        b.add("S3", m_t(SLAT_X[6] + 0.11, -0.46, 0.012) @ m_r("Z", 6.0) @ m_r("X", -24.0), "slat")
        b.lying("BT0", -0.2, -0.2, 100.0, lift=0.005)
        b.lying("BT3", 0.2, -0.12, 262.0, thick=0.011, tilt=-3.0, lift=0.012)
    else:
        stubs = {0: "BS2", 1: "BS3", 3: "BS4", 4: "BS1", 6: "BS3", 7: "BS2"}
        for i, name in stubs.items():
            b.slat(name, SLAT_X[i], L=L, z0=0.05, nail_set=(0,))
        b.lying("BT1", -0.22, -0.2, 78.0, lift=0.004)
        b.lying("BT3", 0.2, -0.3, 102.0, lift=0.004)
        b.lying("BT2", -0.06, -0.4, 266.0, lift=0.006)
        b.lying("BT4", 0.26, -0.13, 252.0, lift=0.004)
        # the top rail broken in two, lying; the top of the post beside it
        b.rail_on_ground("RJ0", -0.19, -0.1, -4.0, 0.62)
        b.rail_on_ground("RK0", 0.27, -0.46, 7.0, 0.42, flip=True)
        b.add("PT0", m_t(0.12, -0.24, 0.045) @ m_r("Z", 25.0) @ m_r("Y", 90) @ m_r("Z", 90), "post")
    return b.items


def corner(A, stage):
    b = Builder(A, 200 + stage)
    r = b.rnd
    if stage == 0:
        L = np.eye(4)
    elif stage == 1:
        L = np.array(Matrix.Rotation(math.radians(7.0), 4, Vector((1, -1, 0)).normalized()))
    else:
        L = np.array(Matrix.Rotation(math.radians(11.0), 4, Vector((1, -1, 0)).normalized()))
    SW = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])
    post = "PC0" if stage < 2 else "PC1"
    b.add(post, L @ m_t(0.0, 0.0, 0.0) @ m_r("Z", 6.0), "post")
    xs = [0.4375, 0.3, 0.1625]
    arm_names = [["S0", "S3", "S6"], ["S4", "S2", "S1"]]
    for arm in (0, 1):
        Lm = L if arm == 0 else L @ SW
        # arm geometry is built along +X; the Y arm is its mirror image across the diagonal
        rr = Builder(A, 300 + 10 * stage + arm)
        rr.items = b.items
        for k in range(2 if stage < 2 else 1):
            nm = ("RB0", "RB1")[arm]
            rr.add(nm, Lm @ m_t(0.05, RAIL_Y, RAIL_Z[k]) @ m_r("Y", 90), "rail")
        if stage == 0:
            for i in range(3):
                rr.slat(arm_names[arm][i], xs[i], L=Lm)
        elif stage == 1:
            for i in range(3):
                if arm == 1 and i == 1:
                    for k in (0, 1):
                        rr.nail(Lm, xs[i], -0.035, RAIL_Z[k], bent=True)
                    continue
                if arm == 0 and i == 0:
                    rr.slat("BS1", xs[i], L=Lm)
                    continue
                rr.slat(arm_names[arm][i], xs[i], L=Lm)
        else:
            for i, nm in zip((0, 2), (("BS2", "BS4"), ("BS3", "BS3"))[arm]):
                rr.slat(nm, xs[i], L=Lm, nail_set=(0,))
    if stage == 1:
        b.lying("BT0", 0.2, -0.2, 85.0, lift=0.005)
    if stage == 2:
        b.lying("BT1", 0.2, -0.2, 95.0, lift=0.004)
        b.lying("BT3", -0.2, 0.2, 6.0, lift=0.004)
        b.lying("BT2", 0.25, 0.3, 88.0, lift=0.004)
        b.lying("BT4", 0.0, -0.36, 262.0, lift=0.004)
    return b.items


# ---------------------------------------------------------------- gate

def leaf_items(A, sx, variants, seed):
    """One gate leaf built for the +X side (hinge at x = 0.875) and mirrored for the left one (sx = -1)."""
    b = Builder(A, seed)
    r = b.rnd
    Mx = m_s(sx, 1, 1)
    xs = [0.8225 - 0.126 * i for i in range(7)]
    for x, name in zip(xs, variants):
        b.add(name, Mx @ m_t(x + r.uniform(-0.002, 0.002), SLAT_Y, 0.05 + r.uniform(-0.006, 0.006))
              @ m_r("Z", r.uniform(-1, 1)) @ m_r("X", r.uniform(-0.5, 0.5)), "slat")
        for k in (0, 1):
            b.add("NAIL", Mx @ m_t(x + r.uniform(-0.016, 0.016), -0.035, RAIL_Z[k] + r.uniform(-0.012, 0.012))
                  @ m_r("X", 90) @ m_r("Z", r.uniform(0, 360)) @ m_r("X", r.uniform(-8, 8)), "iron")
    for k, nm in zip((0, 1), ("RG0", "RG1")):
        b.add(nm, Mx @ m_t(0.015, RAIL_Y, RAIL_Z[k]) @ m_r("Y", 90), "rail")
    # Z-brace on the back of the rails, hinge-bottom up to the latch-top
    a, c = np.array((0.82, 0.062, 0.27)), np.array((0.05, 0.062, 0.78))
    d = c - a
    Lb = np.linalg.norm(d)
    b.add("RD0", Mx @ m_t(*a) @ basis(d, (0, 1, 0)), "rail")
    # strap hinges on the front, eye on the axis, strap running toward the leaf's centre (-X in leaf frame)
    for zh in RAIL_Z:
        b.add("HINGE", Mx @ m_t(HX, HY, zh) @ m_s(-1, 1, 1), "iron")
        for dx in (-0.10, -0.2):
            b.add("NAIL", Mx @ m_t(HX + dx, HY - 0.0055, zh) @ m_r("X", 90) @ m_s(1.9, 1.9, 1.9)
                  @ m_r("Z", r.uniform(0, 360)), "iron")
    # brace nails (on its back face, +Y, where the rails are in front)
    return b.items


def gate_frame(A):
    items = []
    for sx in (-1, 1):
        Mx = m_s(sx, 1, 1)
        items.append(A.place("PG0", m_t(sx * 0.94, 0.025, 0.0) @ m_r("Z", 90.0 * (1 if sx > 0 else 3) + 5.0), "post"))
        for zh in RAIL_Z:
            items.append(A.place("PINTLE", Mx @ m_t(HX, HY, zh), "iron"))
    return items


# ================================================================ main

def save_templates(path, T):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    arrs = {}
    for n, t in T.items():
        arrs[n + "|V"], arrs[n + "|F"], arrs[n + "|UV"] = t.V, t.F, t.UV
    meta = {n: {k: v for k, v in t.meta.items() if isinstance(v, (int, float, str, bool))} for n, t in T.items()}
    np.savez(path, __meta__=np.array(json.dumps(meta)), **arrs)


def load_templates(path):
    import json
    z = np.load(path)
    meta = json.loads(str(z["__meta__"]))
    return {n: fk.Tpl(n, z[n + "|V"], z[n + "|F"], z[n + "|UV"], m) for n, m in meta.items()}


tk.reset_scene()
fk.use_device()
if MODE == "reuse" and os.path.exists(CACHE):
    T = load_templates(CACHE)
    PATHS = {k: os.path.join(ASSETS, "%s_%s.png" % (MAT_NAME, s)) for k, s in (("albedo", "Albedo"), ("normal", "Normal"),
                                                                              ("rmom", "RMOM"))}
else:
    wood = fk.fence_wood("Wood", "paint", tile=0.9, value=2.2, sat=0.42, tint=(1.0, 0.94, 0.86))
    iron, wire = fk.iron_materials()
    build_kit((wood, iron, wire))
    log("kit built: %d parts" % len(fk.KIT))
    kit, PATHS = fk.bake_kit(ASSETS, MAT_NAME)
    T = fk.extract_templates(kit)
    bpy.data.objects.remove(kit)
    save_templates(CACHE, T)
MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
log("baked", PATHS)
fk.albedo_stats(PATHS, "vanilla wood gate mean (0.29, 0.24, 0.20)")
A = fk.Assembler(T)

REPORT = []
BUILT = {}
ALL = []
LIM_SECTION = ((-0.5, 0.5), (-0.5, 0.5))
FX = {"Section": (0.0, -0.08, Z0 + 0.55), "Corner": (-0.03, -0.1, Z0 + 0.55)}
for key, fn in (("Section", section), ("Corner", corner)):
    meshes = []
    for s in range(3):
        obj = fk.finish_mesh("%s_DMG%d" % (key, s), fn(A, s), MATERIAL, LIM_SECTION)
        meshes.append(obj)
        log("%s DMG%d: %d tris" % (key, s, len(obj.data.polygons)))
    BUILT[key] = meshes
    ALL.extend(meshes)

frame = fk.finish_mesh("GateFrame", gate_frame(A), MATERIAL)
left = fk.finish_mesh("GateLeft", leaf_items(A, -1, ["S5", "S0", "S3", "S1", "S2", "S4", "S0"], 500), MATERIAL)
right = fk.finish_mesh("GateRight", leaf_items(A, 1, ["S2", "S6", "S1", "S0", "S3", "S7", "S5"], 501), MATERIAL)
log("gate: frame %d tris, left %d, right %d" % (len(frame.data.polygons), len(left.data.polygons), len(right.data.polygons)))
tk.mark_part(left, "LeftLeaf")
tk.mark_part(right, "RightLeaf")
gate = tk.join([frame, left, right], "Frame")
leaf_l = tk.split_part(gate, "LeftLeaf", (-HX, HY, Z0))
leaf_r = tk.split_part(gate, "RightLeaf", (HX, HY, Z0))
for o in (gate, leaf_l, leaf_r):
    if o.data.attributes.get("trap_part") is not None:
        o.data.attributes.remove(o.data.attributes["trap_part"])
GATE = [gate, leaf_l, leaf_r]
ALL.extend(GATE)
log("swing check, leaf into its post: left %s | right %s" % (fk.swing_check(leaf_l, -1, (-0.995, -0.885, -0.03, 0.08)),
                                                          fk.swing_check(leaf_r, 1, (0.885, 0.995, -0.03, 0.08))))

for key in ("Section", "Corner"):
    meshes = BUILT[key]
    fk.export_piece(ASSETS, "PicketFence%s.fbx" % key, meshes, FX[key])
    for i, m in enumerate(meshes):
        lo, hi, tris = fk.stats([m])
        REPORT.append("PicketFence%s.fbx DMG%d: %d tris, bounds %s .. %s" % (key, i, tris, lo.round(3), hi.round(3)))
    REPORT.append("PicketFence%s.fbx FX at %s" % (key, FX[key]))
tk.export_fbx(GATE, os.path.join(ASSETS, "PicketFenceGate.fbx"))
for o in GATE:
    lo, hi, tris = fk.stats([o])
    REPORT.append("PicketFenceGate.fbx %s: %d tris, bounds %s .. %s, origin %s, parent %s" % (
        o.name, tris, lo.round(3), hi.round(3), tuple(round(c, 3) for c in o.matrix_world.translation),
        o.parent.name if o.parent else None))
S0_ = BUILT["Section"][0]
for label, placed in (("section", [(S0_, (0, 0, 0), 0)]), ("two sections", [(S0_, (0, 0, 0), 0), (S0_, (1, 0, 0), 0)])):
    REPORT.append("see-through, %s, from the front, z 0.05 to 1.05: %.0f%% of rays get through" % (
        label, 100 * fk.see_through(placed, "Y", -0.45 if len(placed) == 1 else 0.0, 0.45 if len(placed) == 1 else 1.0, 0.05, 1.05)))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
fk.stage()
CAM = lambda name, loc, tgt, lens=35: tk.camera(name, (loc[0], loc[1], loc[2] + Z0), (tgt[0], tgt[1], tgt[2] + Z0), lens=lens)  # noqa: E731
LU = lambda ents, cam, name, **kw: fk.lineup(ALL, ents, cam, os.path.join(PREVIEWS, name), **kw)  # noqa: E731
for key, nm in (("Section", "section"), ("Corner", "corner")):
    m = BUILT[key]
    ents = [(m[0], (-1.4, 0.0), 0), (m[1], (0.0, 0.0), 0), (m[2], (1.4, 0.0), 0)]
    fk.figure_at(2.5, 0.6)
    LU(ents, CAM("St_" + key, (0.9, -5.2, 1.7), (0.0, 0.0, 0.5), lens=35), "picket_%s_stages.png" % nm)
    LU(ents, CAM("Bk_" + key, (-0.9, 5.2, 1.7), (0.0, 0.0, 0.5), lens=35), "picket_%s_stages_back.png" % nm)
fk.figure_at(1.0, 0.8)
for s in range(3):
    LU([(BUILT["Section"][s], (0.0, 0.0), 0)], CAM("Cl%d" % s, (0.55, -1.5, 1.05), (0.0, 0.0, 0.5), lens=38),
       "picket_close_dmg%d.png" % s, res=(1200, 1000))
LU([(BUILT["Section"][0], (0.0, 0.0), 0)], CAM("ClBack", (-0.45, 1.2, 0.95), (0.0, 0.05, 0.5), lens=38),
   "picket_close_back.png", res=(1200, 1000))
LU([(BUILT["Section"][0], (0.0, 0.0), 0)], CAM("ClTop", (0.3, -0.7, 1.45), (0.0, 0.0, 1.0), lens=40),
   "picket_close_tops.png", res=(1200, 1000))
LU([(BUILT["Section"][0], (0.0, 0.0), 0)], CAM("ClFar", (1.0, -4.0, 1.5), (0.0, 0.0, 0.5), lens=45),
   "picket_far.png", res=(1400, 900))
C0, S0 = BUILT["Corner"][0], BUILT["Section"][0]
row = [(C0, (0.0, 0.0), 0), (S0, (1.0, 0.0), 0), (S0, (2.0, 0.0), 0), (S0, (0.0, 1.0), -90), (S0, (0.0, 2.0), -90)]
fk.figure_at(1.6, -1.0)
LU(row, CAM("RowF", (-2.2, -4.2, 2.3), (0.9, 0.7, 0.5), lens=32), "picket_row.png")
LU(row, CAM("RowB", (3.6, 3.5, 2.4), (0.6, 0.6, 0.5), lens=32), "picket_row_back.png")
fk.figure_at(3.0, -1.0)
side = [(S0, (-2.0, 0.0), 0), (S0, (2.0, 0.0), 0)]
LU(side, CAM("GateF", (1.2, -5.2, 1.7), (0.0, 0.0, 0.5), lens=32), "picket_gate_closed.png", show=GATE)
LU(side, CAM("GateB", (-1.2, 5.2, 1.7), (0.0, 0.0, 0.5), lens=32), "picket_gate_closed_back.png", show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, math.radians(-90.0))
leaf_r.rotation_euler = (0.0, 0.0, math.radians(90.0))
LU(side, CAM("GateO", (2.6, -4.6, 2.0), (0.0, -0.3, 0.5), lens=32), "picket_gate_open.png", show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, 0.0)
leaf_r.rotation_euler = (0.0, 0.0, 0.0)
LU([], CAM("GateH", (1.15, -1.2, 1.05), (0.85, -0.05, 0.6), lens=40), "picket_gate_hinge.png", res=(1200, 1000),
   show=GATE)
LU([], CAM("GateL", (0.55, -1.0, 1.0), (0.0, 0.0, 0.5), lens=40), "picket_gate_latch.png", res=(1200, 1000),
   show=GATE)

for o in ALL:
    o.hide_render = o is not S0
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S0}
tk.icon(CAM("Icon", (1.7, -2.6, 1.3), (0.0, 0.0, 0.5), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.5 + Z0))
log("icon", ICON)

lines = fk.reimport_report(ASSETS, "PicketFence")
log("done")
