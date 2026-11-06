"""Post-and-Rail Fence (Fortifications Expanded): a 1.2 m split-rail ranch fence of silvered, checked timber with rusty
wire staples, cheap early dressing that slows a few zombies. Rails and gaps are open, so sight and bullets pass
between them. All pieces share one baked material, `PostRail` (PostRail_Albedo.png, _Normal.png, _RMOM.png, 2048).

    PostRailSection.fbx   1 m cell: DMG0 intact, DMG1 top rail snapped and a post leaning, DMG2 posts leaning and
                          rails on the ground, FX
    PostRailCorner.fbx    the same three stages; a stout post at the origin with rails toward +X and +Y
    PostRailGate.fbx      2 wide swing gate: Frame (two posts), LeftLeaf and RightLeaf (origins on the hinge axes at
                          x = -+0.875, y = -0.0305, z = -0.5); the leaves swing out toward -Y

Section: one weathered split post at the centre of the cell (13 x 12 cm, 1.2 m, three rectangular mortises through it)
and three rails (z 0.38, 0.74, 1.08 above the ground; 10 x 5.5 cm, split and tapered at the ends) running through the
mortises from cell edge to cell edge (a 4 mm gap at each cell boundary, where the rails of two cells meet). The fence
line is y = 0, front -Y. Rusty wire stapled to the post and the top rail, a loose end hanging.

    blender -b --factory-startup --python post_rail.py -- <unity asset folder> <preview folder> <icon file> [mode]

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
from fencekit import Z0, basis, log, m_about, m_r, m_s, m_t  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

MAT_NAME = "PostRail"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__", "post_rail_kit.npz")
HX = 0.875  # gate hinge axis x ...
RAIL_Y = -0.003  # rail centre y (55 mm thick: front -0.0305, back 0.0245)
HY = RAIL_Y - 0.0275  # ... and its y: the leaf's front face
RAIL_Z = (0.38, 0.74, 1.08)
MORTISE = (0.066, 0.114)  # y, z
SW = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])  # the mirror across the diagonal
LAYOUT = {"x": 0.0, "y": 0.0}


def put(obj):
    if LAYOUT["x"] > 3.6:
        LAYOUT["x"] = 0.0
        LAYOUT["y"] += 1.5
    obj.location = (LAYOUT["x"], LAYOUT["y"], 0.0)
    LAYOUT["x"] += 0.3
    return obj


# ================================================================ the kit

def slope_cut(L, deg, dx, dy):
    a = math.radians(deg)
    n = np.array((dx, dy, 0.0))
    n = n / (np.linalg.norm(n) + 1e-9)
    return [((0, 0, L), (n[0] * math.sin(a), n[1] * math.sin(a), math.cos(a)), fk.FT_END)]


def post_mortised(name, wood, w, t, L, seed, rails_x=True, rails_y=False, through=True, cut=(14.0, 1.0, 0.3), **kw):
    """A split post with rectangular mortises (through along X for a line post, blind from +X and +Y for a corner)."""
    obj = fk.board(name, wood, w, t, L, seed, nw=4, nt=3, chamfer=0.008, step=0.4, rough=0.002, irregular=0.07,
                   bow=0.006, cuts=slope_cut(L, *cut), **kw)
    cutters = []
    for z in RAIL_Z:
        if rails_x:
            sx = w + 0.1 if through else w / 2 + 0.05
            cutters.append(tk.box("cx", (sx, MORTISE[0], MORTISE[1]), (0.0 if through else sx / 2, RAIL_Y, z), wood))
        if rails_y:
            sy = t / 2 + 0.05
            cutters.append(tk.box("cy", (MORTISE[0], sy, MORTISE[1]), (RAIL_Y, sy / 2, z), wood))
    fk.boolean_cut(obj, cutters)
    return obj


def build_kit(mats):
    wood, iron, wire = mats
    posts = {
        "PR0": post_mortised("PR0", wood, 0.13, 0.12, 1.205, 61, cut=(15.0, 1.0, 0.3), twist=0.03),
        "PR1": post_mortised("PR1", wood, 0.125, 0.125, 1.19, 62, cut=(12.0, -0.8, 0.5), twist=-0.04),
        "PRC": post_mortised("PRC", wood, 0.17, 0.17, 1.22, 63, rails_x=True, rails_y=True, through=False,
                             cut=(10.0, 1.0, 1.0), twist=0.02),
    }
    for (name, obj), sd in zip(posts.items(), (3.1, 5.7, 7.3)):
        fk.kit_part(name, put(obj), wear=0.7, ground=1.0, seed=sd, kind="post")
    for name, seed, kw, cut in (("PRG0", 64, dict(twist=0.02), (12.0, 1.0, 0.2)), ("PRG1", 65, dict(twist=-0.03), (14.0, -1.0, 0.6))):
        obj = fk.board(name, wood, 0.12, 0.12, 1.22, seed, nw=4, nt=3, chamfer=0.008, step=0.4, rough=0.002,
                       irregular=0.07, bow=0.005, cuts=slope_cut(1.22, *cut), **kw)
        fk.kit_part(name, put(obj), wear=0.7, ground=1.0, seed=seed * 1.31, kind="gate post")
    # rails and boards: built along Z (10 cm wide in X, 5.5 cm thick in Y), placed on edge along X
    boards = {}
    for i in range(4):
        boards["RR%d" % i] = (0.992, 0.10, 0.055, 70 + i, dict(taper=0.08, taper_len=0.12))
    for i in range(5):
        boards["RB%d" % i] = (0.476, 0.10, 0.055, 80 + i, dict(taper=0.06, taper_len=0.1))
    for i in range(5):
        boards["RG%d" % i] = (0.855, 0.10, 0.055, 90 + i, dict())
    for i in range(4):
        boards["ST%d" % i] = (1.0, 0.065, 0.045, 100 + i, dict())
    boards["RD0"] = (1.09, 0.075, 0.035, 110, dict())
    boards["RD1"] = (1.09, 0.075, 0.035, 111, dict())
    for name, (L, w, t, seed, kw) in boards.items():
        obj = fk.board(name, wood, w, t, L, seed, nw=3, nt=2, chamfer=0.007 if t > 0.05 else 0.005, step=0.36,
                       rough=0.002, irregular=0.11 if t > 0.05 else 0.03, bow=0.006, wander=0.003,
                       twist=random.Random(seed).uniform(-0.05, 0.05), **kw)
        fk.kit_part(name, put(obj), wear=0.7, ground=0.0, seed=seed * 1.29, kind="rail", length=L)
    for name, L, seed, kind in (("RJ0", 0.62, 120, "top"), ("RK0", 0.38, 121, "bot"), ("RJ1", 0.50, 122, "top"),
                                ("RK1", 0.45, 123, "bot")):
        obj = fk.board(name, wood, 0.10, 0.055, L, seed, nw=3, nt=2, chamfer=0.007, step=0.36, rough=0.0012,
                       irregular=0.06, bow=0.005, jag_top=0.06 if kind == "top" else 0.0,
                       jag_bot=0.06 if kind == "bot" else 0.0)
        fk.kit_part(name, put(obj), wear=0.8, ground=0.0, seed=seed * 1.29, kind="broken rail")
    # iron
    fk.kit_part("NAIL", put(fk.iron_nail("NAIL", iron)), kind="nail")
    fk.kit_part("STAPLE", put(fk.iron_staple("STAPLE", wire)), kind="staple")
    p1 = [(0.07, -0.0605, 1.10), (0.078, -0.048, 1.10), (0.1, -0.0345, 1.105), (0.2, -0.0335, 1.108),
          (0.3, -0.034, 1.10), (0.36, -0.035, 1.04), (0.4, -0.037, 0.95), (0.398, -0.046, 0.88), (0.375, -0.07, 0.83)]
    fk.kit_part("WIRE1", put(fk.iron_wire("WIRE1", wire, p1)), kind="wire")
    p2 = [(0.075, -0.0605, 1.10), (0.09, -0.07, 1.04), (0.13, -0.083, 0.9), (0.15, -0.09, 0.72), (0.12, -0.1, 0.5),
          (0.16, -0.105, 0.34), (0.15, -0.12, 0.2), (0.1, -0.15, 0.1), (0.2, -0.17, 0.035), (0.3, -0.15, 0.04)]
    fk.kit_part("WIRE2", put(fk.iron_wire("WIRE2", wire, p2)), kind="wire")
    p3 = [(0.0, 0.0, 0.004), (0.06, 0.03, 0.006), (0.12, 0.02, 0.012), (0.17, -0.02, 0.008), (0.2, -0.06, 0.012),
          (0.26, -0.07, 0.006), (0.32, -0.03, 0.01), (0.36, 0.02, 0.006), (0.41, 0.03, 0.01)]
    fk.kit_part("WIRE3", put(fk.iron_wire("WIRE3", wire, p3)), kind="wire")
    strap = tk.box("strap", (0.34, 0.005, 0.04), (0.17, -0.0025, 0.0), iron)
    tip = tk.box("tip", (0.05, 0.005, 0.026), (0.345, -0.0025, 0.0), iron)
    eye = tk.cylinder("eye", 0.0115, -0.03, 0.03, iron, segments=8)
    fk.kit_part("HINGE", put(tk.join([strap, tip, eye], "HINGE")), kind="strap hinge")
    pin = tk.cylinder("pin", 0.0068, -0.055, 0.055, iron, segments=8)
    plate = tk.box("plate", (0.005, 0.06, 0.08), (0.0025, 0.0, 0.0), iron)
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

class Builder:
    def __init__(self, asm, seed):
        self.A = asm
        self.rnd = random.Random(seed)
        self.items = []

    def add(self, name, M, tag=""):
        self.items.append(self.A.place(name, M, tag))

    def rail(self, name, zc, x0=-0.496, L=np.eye(4), y=RAIL_Y, yaw=0.0, dip=0.0, dip_pivot=None):
        r = self.rnd
        M = m_t(x0, y + r.uniform(-0.003, 0.003), zc + r.uniform(-0.004, 0.004)) @ m_r("Z", yaw) @ m_r("Y", 90)
        if dip:
            M = m_about(m_r("Y", dip), dip_pivot or (0.0, y, zc)) @ M
        self.add(name, L @ M, "rail")

    def rail_on_ground(self, name, cx, cy, yaw, length, lift=0.0, flip=False):
        """A rail lying flat on the ground, centred at (cx, cy), its length along +X turned by yaw."""
        a = math.radians(yaw)
        d = np.array((math.cos(a), math.sin(a)))
        ex, ey = abs(d[0]) * length / 2 + 0.01, abs(d[1]) * length / 2 + 0.06
        cx, cy = min(max(cx, -(0.495 - ex)), 0.495 - ex), min(max(cy, -(0.495 - ey)), 0.495 - ey)
        x0, y0 = np.array((cx, cy)) - d * length / 2
        self.add(name, m_t(x0, y0, 0.0275 + lift) @ m_r("Z", yaw) @ m_r("Y", 90) @ m_r("Z", -90 if flip else 90), "rail")

    def staple(self, L, x, y, z, spin, face="front"):
        ax = m_r("X", 90) if face == "front" else m_r("X", -90)
        self.add("STAPLE", L @ m_t(x, y, z) @ ax @ m_r("Z", spin) @ m_r("X", self.rnd.uniform(-8, 8)), "iron")

    def nail(self, L, x, y, z):
        r = self.rnd
        self.add("NAIL", L @ m_t(x, y, z) @ m_r("X", 90) @ m_r("Z", r.uniform(0, 360)) @ m_r("X", r.uniform(-9, 9))
                 @ m_r("Y", r.uniform(-9, 9)), "iron")


def lean_matrix(deg_x, deg_z, pivot):
    return m_about(m_r("Z", deg_z) @ m_r("X", deg_x), pivot)


def section(A, stage):
    b = Builder(A, 100 + stage)
    r = b.rnd
    L = [np.eye(4), lean_matrix(-4.0, 1.5, (0, 0, 0)), lean_matrix(-18.0, 3.0, (0, 0, 0))][stage]
    b.add("PR0", L @ m_t(0.0, 0.0, 0.0) @ m_r("Z", 0.0), "post")
    if stage == 0:
        for i, nm in enumerate(("RR0", "RR1", "RR2")):
            b.rail(nm, RAIL_Z[i], yaw=r.uniform(-0.4, 0.4))
        b.add("WIRE1", L, "iron")
        b.staple(L, 0.07, -0.0615, 1.10, 90.0)
        b.staple(L, 0.085, -0.0535, 1.10, 40.0)
        b.staple(L, 0.22, -0.0325, 1.115, 90.0)
        b.staple(L, -0.04, -0.0615, 0.62, 80.0)
    elif stage == 1:
        b.rail("RR0", RAIL_Z[0], L=L, dip=2.5, dip_pivot=(0, RAIL_Y, RAIL_Z[0]))
        b.rail("RR1", RAIL_Z[1], L=L)
        # the top rail snapped: the left part stays through the post, the right part fell in front
        b.rail("RJ0", RAIL_Z[2], L=L)
        b.rail_on_ground("RK0", 0.3, -0.25, -10.0, 0.38, flip=True)
        b.add("WIRE1", L, "iron")
        b.staple(L, 0.07, -0.0615, 1.10, 90.0)
        b.staple(L, 0.085, -0.0535, 1.10, 40.0)
    else:
        b.rail("RR0", RAIL_Z[0], L=L, dip=7.0, dip_pivot=(0, RAIL_Y, RAIL_Z[0]))
        b.rail_on_ground("RR1", 0.0, -0.3, 12.0, 0.992, flip=True)
        b.rail_on_ground("RJ1", -0.24, -0.1, -3.0, 0.50, lift=0.002)
        b.rail_on_ground("RK1", 0.26, -0.43, 6.0, 0.45, lift=0.002)
        b.add("WIRE2", L, "iron")
        b.add("WIRE3", m_t(-0.36, 0.2, 0.0) @ m_r("Z", 8.0), "iron")
        b.staple(L, 0.075, -0.0615, 1.10, 90.0)
        b.staple(L, 0.09, -0.0535, 1.10, 40.0)
    return b.items


def corner(A, stage):
    b = Builder(A, 200 + stage)
    r = b.rnd
    axis = Vector((1, -1, 0)).normalized()
    L = [np.eye(4), np.array(Matrix.Rotation(math.radians(6.0), 4, axis)),
         np.array(Matrix.Rotation(math.radians(17.0), 4, axis))][stage]
    b.add("PRC", L @ m_r("Z", 3.0), "post")
    arms = (("RB0", "RB1", "RB2"), ("RB3", "RB4", "RB1"))
    for arm in (0, 1):
        Lm = L if arm == 0 else L @ SW
        for k, nm in enumerate(arms[arm]):
            if stage == 1 and arm == 0 and k == 2:
                # the top rail of the X arm fell
                b.add(nm, m_t(0.0, -0.19, 0.0275) @ m_r("Z", 8.0) @ m_r("Y", 90) @ m_r("Z", 90), "rail")
                continue
            if stage == 2 and not (arm == 0 and k == 0):
                if arm == 0:
                    b.add(nm, m_t(0.0, -0.12 - 0.12 * k, 0.0275) @ m_r("Z", 6.0 - 5 * k) @ m_r("Y", 90) @ m_r("Z", 90), "rail")
                else:
                    b.add(nm, m_t(-0.14 - 0.11 * k, 0.0, 0.0275) @ m_r("Z", 84.0 + 5 * k) @ m_r("Y", 90) @ m_r("Z", 90), "rail")
                continue
            dip = 4.0 if (stage == 1 and arm == 1 and k == 1) else (6.0 if stage == 2 else 0.0)
            M = m_t(0.02, RAIL_Y, RAIL_Z[k]) @ m_r("Y", 90)
            if dip:
                M = m_about(m_r("Y", dip), (0.02, RAIL_Y, RAIL_Z[k])) @ M
            b.add(nm, Lm @ M, "rail")
    b.staple(L, 0.0, -0.0865, 1.10, 90.0)
    b.staple(L, 0.04, -0.0865, 0.80, 70.0)
    if stage == 2:
        b.add("WIRE3", m_t(-0.34, -0.3, 0.0) @ m_r("Z", 20.0), "iron")
    return b.items


# ---------------------------------------------------------------- gate

def leaf_items(A, sx, rails, stiles, brace, seed):
    """One gate leaf built for the +X side (hinge at x = 0.875) and mirrored for the left one (sx = -1)."""
    b = Builder(A, seed)
    r = b.rnd
    Mx = m_s(sx, 1, 1)
    for k, nm in enumerate(rails):
        b.add(nm, Mx @ m_t(0.015, RAIL_Y + r.uniform(-0.002, 0.002), RAIL_Z[k] + r.uniform(-0.004, 0.004)) @ m_r("Y", 90),
              "rail")
    xs = (0.835, 0.05)
    for x, nm in zip(xs, stiles):
        b.add(nm, Mx @ m_t(x, 0.05, 0.14 + r.uniform(-0.01, 0.01)) @ m_r("Z", 90.0 * 0 + r.uniform(-1, 1)), "rail")
        for zc in RAIL_Z:
            b.add("NAIL", Mx @ m_t(x + r.uniform(-0.012, 0.012), HY, zc + r.uniform(-0.012, 0.012)) @ m_r("X", 90)
                  @ m_r("Z", r.uniform(0, 360)) @ m_r("X", r.uniform(-8, 8)), "iron")
    a, c = np.array((0.80, 0.0525, 0.20)), np.array((0.11, 0.0525, 1.02))
    b.add(brace, Mx @ m_t(*a) @ basis(c - a, (0, 1, 0)), "rail")
    for zh in (RAIL_Z[0], RAIL_Z[2]):
        b.add("HINGE", Mx @ m_t(HX, HY, zh) @ m_s(-1, 1, 1), "iron")
        for dx in (-0.10, -0.2):
            b.add("NAIL", Mx @ m_t(HX + dx, HY - 0.0055, zh) @ m_r("X", 90) @ m_s(1.9, 1.9, 1.9)
                  @ m_r("Z", r.uniform(0, 360)), "iron")
    return b.items


def gate_frame(A):
    items = []
    for sx, nm in ((-1, "PRG0"), (1, "PRG1")):
        Mx = m_s(sx, 1, 1)
        items.append(A.place(nm, m_t(sx * 0.935, 0.0, 0.0), "post"))
        for zh in (RAIL_Z[0], RAIL_Z[2]):
            items.append(A.place("PINTLE", Mx @ m_t(HX, HY, zh), "iron"))
    return items


# ================================================================ main

tk.reset_scene()
fk.use_device()
if MODE == "reuse" and os.path.exists(CACHE):
    T = fk.load_templates(CACHE)
    PATHS = {k: os.path.join(ASSETS, "%s_%s.png" % (MAT_NAME, s)) for k, s in (("albedo", "Albedo"), ("normal", "Normal"),
                                                                              ("rmom", "RMOM"))}
else:
    wood = fk.fence_wood("Timber", "grey", tile=1.5, value=2.3, sat=0.3, tint=(1.0, 0.95, 0.88))
    iron, wire = fk.iron_materials()
    build_kit((wood, iron, wire))
    log("kit built: %d parts" % len(fk.KIT))
    kit, PATHS = fk.bake_kit(ASSETS, MAT_NAME)
    T = fk.extract_templates(kit)
    bpy.data.objects.remove(kit)
    fk.save_templates(CACHE, T)
MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
log("baked", PATHS)
fk.albedo_stats(PATHS, "vanilla wood gate mean (0.29, 0.24, 0.20)")
A = fk.Assembler(T)

REPORT = []
BUILT = {}
ALL = []
LIM = ((-0.5, 0.5), (-0.5, 0.5))
FX = {"Section": (0.0, -0.1, Z0 + 0.7), "Corner": (-0.05, -0.12, Z0 + 0.7)}
for key, fn in (("Section", section), ("Corner", corner)):
    meshes = []
    for s in range(3):
        obj = fk.finish_mesh("%s_DMG%d" % (key, s), fn(A, s), MATERIAL, LIM)
        meshes.append(obj)
        log("%s DMG%d: %d tris" % (key, s, len(obj.data.polygons)))
    BUILT[key] = meshes
    ALL.extend(meshes)

frame = fk.finish_mesh("GateFrame", gate_frame(A), MATERIAL)
left = fk.finish_mesh("GateLeft", leaf_items(A, -1, ["RG3", "RG4", "RG0"], ["ST2", "ST3"], "RD1", 500), MATERIAL)
right = fk.finish_mesh("GateRight", leaf_items(A, 1, ["RG0", "RG1", "RG2"], ["ST0", "ST1"], "RD0", 501), MATERIAL)
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
log("swing check, leaf into its post: left %s | right %s" % (fk.swing_check(leaf_l, -1, (-1.0, -0.88, -0.06, 0.06)),
                                                          fk.swing_check(leaf_r, 1, (0.88, 1.0, -0.06, 0.06))))

for key in ("Section", "Corner"):
    meshes = BUILT[key]
    fk.export_piece(ASSETS, "PostRail%s.fbx" % key, meshes, FX[key])
    for i, m in enumerate(meshes):
        lo, hi, tris = fk.stats([m])
        REPORT.append("PostRail%s.fbx DMG%d: %d tris, bounds %s .. %s" % (key, i, tris, lo.round(3), hi.round(3)))
    REPORT.append("PostRail%s.fbx FX at %s" % (key, FX[key]))
tk.export_fbx(GATE, os.path.join(ASSETS, "PostRailGate.fbx"))
for o in GATE:
    lo, hi, tris = fk.stats([o])
    REPORT.append("PostRailGate.fbx %s: %d tris, bounds %s .. %s, origin %s, parent %s" % (
        o.name, tris, lo.round(3), hi.round(3), tuple(round(c, 3) for c in o.matrix_world.translation),
        o.parent.name if o.parent else None))
S0_ = BUILT["Section"][0]
REPORT.append("see-through, section from the front, z 0.05 to 1.15: %.0f%% of rays get through" % (
    100 * fk.see_through([(S0_, (0, 0, 0), 0)], "Y", -0.45, 0.45, 0.05, 1.15)))
REPORT.append("see-through, gate closed between two sections: %.0f%%" % (
    100 * fk.see_through([(gate, (0, 0, 0), 0), (leaf_l, (0, 0, 0), 0), (leaf_r, (0, 0, 0), 0)], "Y", -0.85, 0.85, 0.05,
                         1.15)))
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
    LU(ents, CAM("St_" + key, (0.9, -5.2, 1.7), (0.0, 0.0, 0.5), lens=35), "postrail_%s_stages.png" % nm)
    LU(ents, CAM("Bk_" + key, (-0.9, 5.2, 1.7), (0.0, 0.0, 0.5), lens=35), "postrail_%s_stages_back.png" % nm)
fk.figure_at(1.0, 0.8)
for s in range(3):
    LU([(BUILT["Section"][s], (0.0, 0.0), 0)], CAM("Cl%d" % s, (0.6, -1.7, 1.1), (0.0, 0.0, 0.5), lens=38),
       "postrail_close_dmg%d.png" % s, res=(1200, 1000))
LU([(BUILT["Section"][0], (0.0, 0.0), 0)], CAM("ClPost", (0.35, -0.8, 1.15), (0.0, 0.0, 0.8), lens=40),
   "postrail_close_post.png", res=(1200, 1000))
LU([(BUILT["Section"][0], (0.0, 0.0), 0)], CAM("ClFar", (1.0, -4.0, 1.5), (0.0, 0.0, 0.5), lens=45),
   "postrail_far.png", res=(1400, 900))
C0, S0 = BUILT["Corner"][0], BUILT["Section"][0]
row = [(C0, (0.0, 0.0), 0), (S0, (1.0, 0.0), 0), (S0, (2.0, 0.0), 0), (S0, (0.0, 1.0), -90), (S0, (0.0, 2.0), -90)]
fk.figure_at(1.6, -1.0)
LU(row, CAM("RowF", (-2.2, -4.2, 2.3), (0.9, 0.7, 0.5), lens=32), "postrail_row.png")
LU(row, CAM("RowB", (3.6, 3.5, 2.4), (0.6, 0.6, 0.5), lens=32), "postrail_row_back.png")
fk.figure_at(3.0, -1.0)
side = [(S0, (-2.0, 0.0), 0), (S0, (2.0, 0.0), 0)]
LU(side, CAM("GateF", (1.2, -5.2, 1.7), (0.0, 0.0, 0.5), lens=32), "postrail_gate_closed.png", show=GATE)
LU(side, CAM("GateB", (-1.2, 5.2, 1.7), (0.0, 0.0, 0.5), lens=32), "postrail_gate_closed_back.png", show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, math.radians(-90.0))
leaf_r.rotation_euler = (0.0, 0.0, math.radians(90.0))
LU(side, CAM("GateO", (2.6, -4.6, 2.0), (0.0, -0.3, 0.5), lens=32), "postrail_gate_open.png", show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, 0.0)
leaf_r.rotation_euler = (0.0, 0.0, 0.0)
LU([], CAM("GateH", (1.15, -1.2, 1.05), (0.85, -0.05, 0.6), lens=40), "postrail_gate_hinge.png", res=(1200, 1000),
   show=GATE)

for o in ALL:
    o.hide_render = o is not S0
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S0}
tk.icon(CAM("Icon", (1.8, -2.7, 1.4), (0.0, 0.0, 0.55), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.55 + Z0))
log("icon", ICON)

fk.reimport_report(ASSETS, "PostRail")
log("done")
