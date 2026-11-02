"""Sandbag Wall (Fortifications Expanded): twelve block models that all share one baked atlas, `Sandbags`.

    Sandbag{Wall,Low,Corner,End}{Empty,Half,Full}.fbx

Wall: a straight 2 m wall of burlap sandbags, battered both faces (0.88 m deep at the base, 0.6 m at the top), laid in
a running bond whose stagger carries across blocks: even courses join at x = 0 and on the block seams, odd courses
join at x = +-0.25 and the bag lying across each seam is split in two halves, one in each block, so a row of walls
reads as one wall. Low: the same at 1 m. Corner: the outside of an L (finished on -X and -Y), courses alternating
direction, open on +X and +Y. End: a racked-back finished end on -X, open on +X. Half: the lower half of each piece
with empty bags draped on top. Empty: a neat stack of folded empty bags and two stakes with twine on the wall line.

Half and Full files hold three meshes at the same origin, DMG0 (intact), DMG1 (worn: split and deflated bags, sand
trickling, a small pile) and DMG2 (breaking: a collapsed notch, burst bags, torn flaps, big piles), plus an empty FX
at the middle of the front face at mid-height. Empty files hold one mesh, DMG0.

A kit of bag variants, damaged bags, flaps, empties, sand, a stake and twine is built and baked once to a 2048
atlas; every piece is assembled from copies of the kit parts (moved, scaled and bent, keeping their UVs), with the
bag faces hidden inside the wall culled and a dark core so the gaps never show daylight. The damage is seeded, so a
rebuild gives the same models. The seam halves only match a neighbour in the same damage stage (DMG2 may take them).

    blender -b --factory-startup --python sandbags.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode (debug, optional): `export` skips the renders; `kit` renders unbaked kit bags beside a crop of the vanilla
reference, plus their albedo numbers; `holes:<Piece>:<Stage>:<level>` builds one mesh and renders it with back faces
red (append `:mat` to keep the baked material).
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

Z0 = -0.5  # bottom of every model
P = 1.0 / 6.0  # course pitch: 12 courses in 2 m
OVZ = 0.014  # courses squeeze into each other this much
OVL = 0.06  # bags in a row overlap at their rounded ends
BAG_L, BAG_W, BAG_H = 0.56, 0.28, 0.18
SHORT_L = 0.32
MAT_NAME = "Sandbags"


def log(*a):
    print("[sandbags]", *a, flush=True)


# ---------------------------------------------------------------- colors (linear)

TAN_A = (0.092, 0.058, 0.031)
TAN_B = (0.200, 0.122, 0.056)
PATCH = (0.036, 0.028, 0.021)
DARK = (0.022, 0.019, 0.016)
FIBRE_LIGHT = (0.20, 0.15, 0.095)
STAIN = (0.028, 0.023, 0.018)
MUD = (0.030, 0.022, 0.015)
DUST = (0.15, 0.115, 0.075)
SAND_GRAIN = (0.25, 0.21, 0.15)
SAND_L = (0.36, 0.30, 0.21)
SAND_D = (0.235, 0.195, 0.135)
SAND_IN = (0.22, 0.18, 0.125)
SAND_SHADOW = (0.05, 0.042, 0.03)
CORE_COL = (0.017, 0.014, 0.011)


# ---------------------------------------------------------------- small helpers

def smoothstep(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def pnoise(p, seed, freq=1.0):
    return noise.noise(Vector((p[0] * freq + seed * 7.31, p[1] * freq - seed * 3.17, p[2] * freq + seed * 1.93)))


def m_rot(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, axis))


def m_trans(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def m_scale(sx, sy, sz):
    return np.diag([sx, sy, sz, 1.0])


def bm_from(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


# ---------------------------------------------------------------- kit shapes

def box_grid(nx, ny, nz):
    """Points and outward quads on the surface of the [-1, 1] cube, on an nx * ny * nz grid."""
    index, pts, quads = {}, [], []

    def vid(i, j, k):
        key = (i, j, k)
        if key not in index:
            index[key] = len(pts)
            pts.append((2.0 * i / nx - 1.0, 2.0 * j / ny - 1.0, 2.0 * k / nz - 1.0))
        return index[key]

    for i in (0, nx):
        for j in range(ny):
            for k in range(nz):
                quads.append([vid(i, j, k), vid(i, j + 1, k), vid(i, j + 1, k + 1), vid(i, j, k + 1)])
    for j in (0, ny):
        for i in range(nx):
            for k in range(nz):
                quads.append([vid(i, j, k), vid(i, j, k + 1), vid(i + 1, j, k + 1), vid(i + 1, j, k)])
    for k in (0, nz):
        for i in range(nx):
            for j in range(ny):
                quads.append([vid(i, j, k), vid(i + 1, j, k), vid(i + 1, j + 1, k), vid(i, j + 1, k)])
    return pts, quads


def pillow(L, W, H, nx=6, ny=2, nz=2, seed=0, sewn=0.56, tuck=0.7, lump=0.012, quiet=None, bend=0.0, twist=0.0,
           cap_bulge=(0.04, 0.08), sag=0.0, ears=0.006):
    """A filled bag lying on its side: x along the bag, flat-ish top and bottom, bulging long sides, the sewn end
    (+x) flattened to a thin seam with little ears at the corners, the folded end (-x) thicker and rounder. `quiet`
    (x0, x1) fades the lumps out near x = 0 so a bag can be cut there into halves that join seamlessly."""
    a, b, c = L / 2.0, W / 2.0, H / 2.0
    pts, quads = box_grid(nx, ny, nz)
    out = []
    for (u, v, w) in pts:
        s = math.sin(u * math.pi / 2.0)
        t = abs(s)
        cap = abs(abs(u) - 1.0) < 1e-9
        rho = max(abs(v), abs(w))
        if rho < 1e-9:
            qy = qz = 0.0
        else:
            dy, dz = v / rho, w / rho
            n = 2.7 - 0.6 * t * t
            m = (abs(dy) ** n + abs(dz) ** n) ** (1.0 / n)
            qy, qz = rho * dy / m, rho * dz / m
        end_e = sewn if s > 0 else tuck
        hb = 1.0 - 0.04 * t ** 4 + 0.05 * (1.0 - s * s)
        hc = 1.0 - (1.0 - end_e) * t ** 8
        x = a * s
        if cap:
            x = math.copysign(a * (1.0 + (cap_bulge[0] if u > 0 else cap_bulge[1]) * (1.0 - rho * rho)), u)
        y = b * hb * qy
        z = c * hc * qz - c * (1.0 - hc) * 0.3
        if sag and qz > 0:
            z -= sag * c * qz * (1.0 - s * s) * (1.0 - 0.5 * abs(qy))
        if ears and u > 0 and t > 0.95 and abs(qy) > 0.7:
            x += ears * smoothstep(0.7, 1.0, abs(qy))
            y *= 1.03
        p = Vector((x, y, z))
        d = Vector((math.copysign(1.0, u) if cap else 0.35 * s, qy, qz))
        if d.length < 1e-6:
            d = Vector((math.copysign(1.0, u), 0.0, 0.0))
        d.normalize()
        amt = lump * (pnoise(p, seed, 6.0) + 0.5 * pnoise(p, seed + 11, 13.0))
        if quiet:
            amt *= smoothstep(quiet[0], quiet[1], abs(x))
        p += d * amt
        if bend:
            p.y += bend * (1.0 - s * s) * b
        if twist:
            ang = twist * s
            cy, cz = p.y, p.z
            p.y = cy * math.cos(ang) - cz * math.sin(ang)
            p.z = cy * math.sin(ang) + cz * math.cos(ang)
        out.append(p)
    return out, quads


def push_region(verts, center, radius, vec):
    c, v = Vector(center), Vector(vec)
    for p in verts:
        d = (p - c).length
        if d < radius:
            p += v * (0.5 + 0.5 * math.cos(math.pi * d / radius))


def half_bm(verts, quads, keep_negative):
    """Cuts a pillow at x = 0 and caps the cut: the left (x <= 0) or right half."""
    bm = bm_from(verts, quads)
    kill = [f for f in bm.faces if (f.calc_center_median().x > 0) == keep_negative]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    for v in bm.verts:
        if abs(v.co.x) < 1e-5:
            v.co.x = 0.0
    edges = [e for e in bm.edges if e.is_boundary]
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def flap_bm(seed, w=0.13, h=0.09):
    """A torn burlap flap: a jagged strip hanging from its top edge (z = 0 down to -h), curling outward (-y)."""
    rnd = random.Random(seed)
    nx, nz = 4, 2
    rows = []
    for k in range(nz + 1):
        row = []
        f = k / nz
        for i in range(nx + 1):
            x = -w / 2 + w * i / nx
            zz = -h * f
            if k == nz:
                zz += rnd.uniform(0.0, 0.045) * (1.0 + (i % 2))  # torn bottom edge
            if i in (0, nx):
                x *= 1.0 - 0.25 * f * rnd.uniform(0.3, 1.0)
            y = -0.05 * f * f - 0.012 * math.sin(i * 1.7 + seed) * f
            row.append((x, y, zz))
        rows.append(row)
    verts = [p for row in rows for p in row]
    faces = []
    for k in range(nz):
        for i in range(nx):
            a = k * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
    bm = bm_from(verts, faces)
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.0035)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def mound_bm(rx, rz, height, seed, rings=(1.0, 0.72, 0.42), segs=10, axis="Y", drop=0.0, power=0.7):
    """A lobed sand mound on a plane: in XY bulging +z (axis 'Z', a pile) or in XZ bulging -y (axis 'Y', sand
    spilling out of a tear, `drop` stretching it downward). Open underneath."""
    vs, faces = [], []
    ring_ids = []
    for rho in rings:
        ids = []
        for i in range(segs):
            t = 2 * math.pi * i / segs
            rr = 1.0 + 0.14 * math.sin(3 * t + seed) + 0.08 * math.sin(5 * t + 2.3 * seed)
            a = rx * rr * rho * math.cos(t)
            b = rz * rr * rho * math.sin(t)
            if axis == "Y" and b < 0:
                b *= 1.0 + drop
            hh = height * (1.0 - rho * rho) ** power + 0.0008
            hh *= 1.0 + 0.15 * math.sin(7 * t + 3 * rho + seed) * (1.0 - rho)
            ids.append(len(vs))
            vs.append((a, -hh, b) if axis == "Y" else (a, b, hh))
        ring_ids.append(ids)
    ci = len(vs)
    vs.append((0.0, -height - 0.0008, 0.0) if axis == "Y" else (0.0, 0.0, height + 0.0008))
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([ring_ids[k][i], ring_ids[k][j], ring_ids[k + 1][j], ring_ids[k + 1][i]])
    for i in range(segs):
        faces.append([ring_ids[-1][i], ring_ids[-1][(i + 1) % segs], ci])
    bm = bm_from(vs, faces)
    # make the visible side face outward
    for f in bm.faces:
        n = f.normal
        if (axis == "Z" and n.z < 0) or (axis == "Y" and n.y > 0):
            f.normal_flip()
    return bm


def pile_bm(seed):
    """A heap of spilled sand, radius 0.5 m, 0.22 m high, open underneath."""
    rnd = random.Random(seed)
    segs = 12
    rings = (1.0, 0.78, 0.5, 0.24)
    vs, faces, ring_ids = [], [], []
    for rho in rings:
        ids = []
        for i in range(segs):
            t = 2 * math.pi * i / segs
            rr = 1.0 + 0.1 * math.sin(3 * t + seed) + 0.06 * math.sin(5 * t + 1.7 * seed) + 0.03 * math.sin(9 * t)
            h = 0.22 * (1.0 - rho ** 1.7) ** 1.25 + 0.0015
            h *= 1.0 + 0.12 * math.sin(4 * t + 2 * rho + seed) * (1.0 - rho)
            ids.append(len(vs))
            vs.append((0.5 * rr * rho * math.cos(t), 0.5 * rr * rho * math.sin(t), h + rnd.uniform(-0.004, 0.004) * (1 - rho)))
        ring_ids.append(ids)
    ci = len(vs)
    vs.append((0.0, 0.0, 0.222))
    for k in range(len(rings) - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([ring_ids[k][i], ring_ids[k][j], ring_ids[k + 1][j], ring_ids[k + 1][i]])
    for i in range(segs):
        faces.append([ring_ids[-1][i], ring_ids[-1][(i + 1) % segs], ci])
    bm = bm_from(vs, faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return bm


def trickle_bm():
    """A ribbon of sand that has run down a face: 4.5 cm wide, 1 m long from z = 0 down, domed toward -y."""
    vs, faces = [], []
    rows = 9
    for k in range(rows):
        f = k / (rows - 1)
        w = 0.016 * (1.0 - 0.35 * f + 0.6 * f ** 4)
        for i, (xx, yy) in enumerate(((-w, 0.0), (0.0, -0.009), (w, 0.0))):
            vs.append((xx + 0.006 * math.sin(f * 9.0), yy, -f))
    for k in range(rows - 1):
        for i in range(2):
            a = k * 3 + i
            faces.append([a, a + 3, a + 4, a + 1])
    bm = bm_from(vs, faces)
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    return bm


def helix_points(radius, z0, z1, turns, n):
    return [(radius * math.cos(2 * math.pi * turns * i / (n - 1)), radius * math.sin(2 * math.pi * turns * i / (n - 1)),
             z0 + (z1 - z0) * i / (n - 1)) for i in range(n)]


# ---------------------------------------------------------------- materials

def attr_vec(g, name):
    n = g.node("ShaderNodeAttribute", attribute_name=name)
    return tk._sock(n.outputs, "Vector")


def mapped(g, vec, scale=(1.0, 1.0, 1.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def local_normal(g):
    geo = g.node("ShaderNodeNewGeometry")
    vt = g.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="WORLD", convert_to="OBJECT")
    g.links.new(tk._sock(geo.outputs, "Normal"), vt.inputs[0])
    return g.separate(vt.outputs[0])


def voronoi(g, vec, scale):
    v = g.node("ShaderNodeTexVoronoi")
    g._in(v, "Scale", scale)
    g.links.new(vec, v.inputs["Vector"])
    return tk._sock(v.outputs, "Distance")


def weave(g, a, b, t):
    """Plain weave height (0-1) on a surface parametrised by a and b (meters), thread spacing t: each thread a
    ridge, over and under its neighbours in a checker."""
    sa = g.math("SINE", g.math("MULTIPLY", a, math.pi / t))
    sb = g.math("SINE", g.math("MULTIPLY", b, math.pi / t))
    over = g.ramp(g.math("MULTIPLY", sa, sb), -0.15, 0.15)
    ra = g.math("POWER", g.math("ABSOLUTE", sa), 0.6)
    rb = g.math("POWER", g.math("ABSOLUTE", sb), 0.6)
    return g.mixf(over, ra, rb)


def burlap_material(name):
    """Hessian sandbag cloth. Reads per-vertex attributes the kit writes: lco (the part's own coordinates), kd
    (dirt 0-1, gash 0/1, style: 0 filled, 1 empty, 2 flap, 3 deflated, 4 burst), kdim (half sizes) and kg (gash
    center x, z and size), so folds, seams, mud and tears sit right on every bag wherever it lies in the kit."""
    mat, g = tk.new_material(name)
    lco = attr_vec(g, "lco")
    px, py, pz = g.separate(lco)
    kd = g.separate(attr_vec(g, "kd"))
    dirt, gashf, style = kd[0], kd[1], kd[2]
    dim = g.separate(attr_vec(g, "kdim"))
    kg = g.separate(attr_vec(g, "kg"))
    co = g.coords()
    nx, ny, nz = local_normal(g)

    u = g.math("DIVIDE", px, dim[0])
    au = g.math("ABSOLUTE", u)
    vy = g.math("DIVIDE", py, dim[1])
    vz = g.math("DIVIDE", pz, dim[2])
    filled = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", style, 0.0)), 0.5, 0.0)
    deflated = g.ramp(style, 2.5, 3.0)
    burst = g.ramp(style, 3.5, 4.0)
    empty = g.math("MULTIPLY", g.ramp(style, 0.5, 1.0), g.ramp(style, 1.5, 1.0))

    # ---- weave, triplanar in the part's own frame
    T = 0.009
    wob = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(22.0, detail=2.0, vector=co), 0.5), T * 1.3)
    ax, ay, az = (g.math("ADD", c, wob) for c in (px, py, pz))
    wf, wt, we = weave(g, ax, az, T), weave(g, ax, ay, T), weave(g, ay, az, T)

    def w4(c):
        return g.math("POWER", g.math("ABSOLUTE", c), 4.0)

    kx, ky, kz = w4(nx), w4(ny), w4(nz)
    tot = g.math("ADD", g.math("ADD", kx, ky), g.math("ADD", kz, 1e-4))
    hw = g.math("DIVIDE", g.math("ADD", g.math("ADD", g.math("MULTIPLY", wf, ky), g.math("MULTIPLY", wt, kz)),
                                 g.math("MULTIPLY", we, kx)), tot)
    slub = g.noise(1.0, detail=2.0, vector=mapped(g, co, (14.0, 90.0, 90.0)))
    hw = g.math("MULTIPLY", hw, g.math("ADD", 0.7, g.math("MULTIPLY", slub, 0.6)))

    # ---- loose fibres
    f1 = g.noise(1.0, detail=4.0, roughness=0.6, vector=mapped(g, co, (30.0, 260.0, 260.0)))
    f2 = g.noise(1.0, detail=4.0, roughness=0.6, vector=mapped(g, co, (260.0, 260.0, 30.0)))
    fib = g.ramp(g.math("MAXIMUM", f1, f2), 0.56, 0.8)

    # ---- folds: gathered ends, long wrinkles, crinkles on slack bags
    endz = g.ramp(au, 0.45, 1.0)
    ang = g.math("ARCTAN2", vz, vy)
    folds = g.math("SINE", g.math("ADD", g.math("MULTIPLY", ang, 4.0),
                                  g.math("MULTIPLY", g.noise(3.0, detail=3.0, vector=co), 12.0)))
    folds = g.math("MULTIPLY", folds, g.math("MULTIPLY", g.math("MULTIPLY", endz, endz), 0.65))
    wr = g.math("SUBTRACT", g.noise(1.0, detail=3.0, distortion=0.5, vector=mapped(g, co, (2.5, 15.0, 15.0))), 0.5)
    crinkle = g.math("SUBTRACT", g.noise(1.0, detail=4.0, distortion=0.8, vector=mapped(g, co, (8.0, 8.0, 8.0))), 0.5)
    slack = g.math("ADD", deflated, g.math("ADD", empty, burst))
    wr_amp = g.math("ADD", 0.55, g.math("MULTIPLY", slack, 0.9))
    foldh = g.math("ADD", g.math("MULTIPLY", folds, g.math("MULTIPLY", filled, 0.7)),
                   g.math("MULTIPLY", wr, g.math("MULTIPLY", wr_amp, g.math("ADD", 0.6, endz))))
    foldh = g.math("ADD", foldh, g.math("MULTIPLY", crinkle, g.math("MULTIPLY", slack, 1.2)))

    # ---- crumple: ridges and hollows of hessian pulled over lumpy sand, all over every bag
    c1 = g.noise(13.0, detail=5.0, roughness=0.62, distortion=1.1, vector=co)
    ridge = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", c1, 2.0), 1.0)))
    c2 = g.noise(30.0, detail=4.0, roughness=0.6, distortion=0.5, vector=co)
    crumple = g.math("ADD", g.math("MULTIPLY", ridge, 0.7), g.math("MULTIPLY", c2, 0.3))

    # ---- the sewn seam across the +x end
    seam = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", u, 0.9)), 0.03, 0.0), filled)
    stitch = g.math("MULTIPLY", g.ramp(g.math("SINE", g.math("MULTIPLY", g.math("ADD", py, pz), math.pi / 0.011)),
                                       0.2, 0.7), seam)

    # ---- tears: an elliptic jagged gash at (kg.x, kg.y) on the -y side (on top too for burst bags)
    gx_, gz_, gs = kg[0], kg[1], kg[2]
    dxg = g.math("DIVIDE", g.math("SUBTRACT", px, gx_), gs)
    dzg = g.math("DIVIDE", g.math("SUBTRACT", pz, gz_), g.math("MULTIPLY", gs, 0.42))
    jag = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(1.0, detail=3.0, vector=mapped(g, co, (45.0, 45.0, 18.0))), 0.5),
                 0.8)
    dg = g.math("ADD", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dxg, dxg), g.math("MULTIPLY", dzg, dzg))), jag)
    side = g.math("MAXIMUM", g.ramp(vy, -0.1, -0.55), g.math("MULTIPLY", g.ramp(vz, 0.1, 0.5), burst))
    hole = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(dg, 1.0, 0.82), side), gashf)
    lip = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", dg, 1.06)), 0.2, 0.0), side),
                 gashf)
    lip = g.math("MULTIPLY", lip, g.ramp(fib, 0.0, 0.4))

    # ---- color: warm tan hessian mottled dark, grime in the hollows, worn light on the ridges, dirt patches,
    # mud low down, a little dust on top
    tone = g.noise(2.2, detail=6.0, roughness=0.6, vector=co)
    spk = g.noise(85.0, detail=4.0, roughness=0.7, vector=co)
    base = g.mix(g.ramp(g.math("ADD", tone, g.math("MULTIPLY", g.math("SUBTRACT", spk, 0.5), 0.6)), 0.3, 0.72),
                 TAN_A, TAN_B)
    # grainy-edged dark mottling over about half of every bag, more low down and on the dirtier bags
    mott = g.noise(6.0, detail=6.0, roughness=0.65, distortion=0.4, vector=co)
    mott = g.math("ADD", mott, g.math("MULTIPLY", g.math("SUBTRACT", spk, 0.5), 0.35))
    # dark low on each bag and into the joints, tan on the upper front and top
    lowside = g.ramp(vz, 0.45, -0.7)
    mott = g.math("ADD", mott, g.math("MULTIPLY", lowside, 0.3))
    mott = g.math("SUBTRACT", mott, g.math("MULTIPLY", g.ramp(vz, 0.2, 0.8), 0.06))
    mott = g.math("ADD", mott, g.math("MULTIPLY", endz, 0.08))
    mott = g.math("ADD", mott, g.math("MULTIPLY", dirt, 0.05))
    dark = g.ramp(mott, 0.48, 0.6)
    base = g.mix(g.math("MULTIPLY", dark, 0.88), base, DARK)
    col = tk._multiply_color(g, base, g.mix(hw, (0.72, 0.72, 0.72), (1.12, 1.1, 1.07)))
    col = g.mix(g.math("MULTIPLY", fib, 0.3), col, FIBRE_LIGHT)
    hol = g.ramp(crumple, 0.5, 0.86)
    col = tk._multiply_color(g, col, g.mix(hol, (0.52, 0.5, 0.48), (1.14, 1.09, 1.02)))
    ph = tk.photo(g, "rust_coarse_01", 1.4, (0.31, 0.77, 0.19))
    blot = g.ramp(tk._luma(g, ph["color"]), 0.17, 0.06)
    patches = g.ramp(g.noise(3.2, detail=8.0, roughness=0.62, distortion=0.5, vector=co), 0.56, 0.68)
    dirty = g.math("MULTIPLY", g.math("MAXIMUM", blot, patches), g.math("ADD", 0.45, g.math("MULTIPLY", dirt, 0.4)))
    col = g.mix(dirty, col, PATCH)
    low = g.ramp(vz, 0.25, -1.0)
    mudn = g.ramp(g.noise(5.0, detail=6.0, roughness=0.65, vector=co), 0.32, 0.62)
    mud = g.math("MULTIPLY", g.math("MULTIPLY", low, mudn), g.math("ADD", 0.1, g.math("MULTIPLY", dirt, 0.8)))
    col = g.mix(mud, col, MUD)
    col = g.mix(g.math("MULTIPLY", dirt, 0.18), col, tk._darker(g, col, 0.7))
    endg = g.math("MULTIPLY", g.ramp(au, 0.8, 1.02), g.ramp(g.noise(9.0, detail=4.0, vector=co), 0.25, 0.6))
    col = g.mix(g.math("MULTIPLY", endg, g.math("MULTIPLY", filled, 0.5)), col, STAIN)
    col = tk._multiply_color(g, col, g.mix(g.ramp(foldh, -0.55, 0.55), (0.6, 0.58, 0.56), (1.08, 1.06, 1.04)))
    down = g.ramp(nz, -0.25, -0.85)
    col = g.mix(g.math("MULTIPLY", down, 0.45), col, STAIN)
    up = g.math("MULTIPLY", g.ramp(nz, 0.6, 0.95), g.ramp(g.noise(7.0, detail=6.0, vector=co), 0.4, 0.7))
    dusty = g.math("MULTIPLY", up, 0.35)
    col = g.mix(dusty, col, DUST)
    grains = g.math("MULTIPLY", g.ramp(voronoi(g, co, 220.0), 0.16, 0.06),
                    g.ramp(g.noise(6.0, vector=co), 0.42, 0.62))
    col = g.mix(g.math("MULTIPLY", grains, 0.5), col, SAND_GRAIN)
    col = g.mix(g.math("MULTIPLY", seam, 0.45), col, STAIN)
    col = g.mix(lip, col, FIBRE_LIGHT)
    col = g.mix(hole, col, g.mix(g.math("MULTIPLY", g.ramp(dzg, 0.5, -1.0), 0.7), SAND_SHADOW, SAND_IN))

    rough = g.math("ADD", 0.86, g.math("MULTIPLY", g.noise(15.0, vector=co), 0.1))
    rough = g.mixf(dusty, rough, 0.97)
    rough = g.mixf(hole, rough, 0.95)

    big = g.math("ADD", g.math("MULTIPLY", foldh, 0.7), g.math("MULTIPLY", crumple, 0.6))
    big = g.math("SUBTRACT", g.math("ADD", big, g.math("MULTIPLY", lip, 0.4)), g.math("MULTIPLY", hole, 1.4))
    fine = g.math("ADD", g.math("ADD", g.math("MULTIPLY", hw, 0.55), g.math("MULTIPLY", fib, 0.25)),
                  g.math("ADD", g.math("MULTIPLY", grains, 0.25), g.math("MULTIPLY", stitch, 0.7)))
    b1 = g.bump(big, 0.85, 0.02)
    b2 = g.bump(fine, 0.45, 0.003, normal=b1)
    return tk.finish(mat, g, col, 0.0, rough, b2)


def sand_material(name):
    """Pale crushed sand: grainy, a few darker pebbles, darker and damp where it meets the ground."""
    mat, g = tk.new_material(name)
    co = g.coords()
    lz = g.separate(attr_vec(g, "lco"))[2]
    style = g.separate(attr_vec(g, "kd"))[2]
    tone = g.noise(3.0, detail=5.0, roughness=0.6, vector=co)
    col = g.mix(g.ramp(tone, 0.3, 0.75), SAND_D, SAND_L)
    vor = voronoi(g, co, 140.0)
    peb = g.math("MULTIPLY", g.ramp(vor, 0.22, 0.1), g.ramp(g.noise(5.0, vector=co), 0.45, 0.6))
    col = g.mix(g.math("MULTIPLY", peb, 0.75), col,
                g.mix(g.noise(40.0, vector=co), (0.1, 0.085, 0.07), (0.33, 0.3, 0.24)))
    grain = g.noise(650.0, detail=2.0, vector=co)
    col = tk._multiply_color(g, col, g.mix(grain, (0.78, 0.78, 0.78), (1.14, 1.12, 1.1)))
    clump = g.noise(35.0, detail=4.0, vector=co)
    pile = g.ramp(style, 4.5, 5.0)
    damp = g.math("MULTIPLY", g.ramp(lz, 0.03, 0.0), g.math("MULTIPLY", pile, 0.45))
    col = g.mix(damp, col, tk._darker(g, col, 0.55))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=5.0, vector=co), 0.55, 0.75), 0.4), col,
                (0.09, 0.075, 0.055))
    trick = g.ramp(style, 5.5, 6.0)
    col = g.mix(g.math("MULTIPLY", trick, 0.7), col, (0.13, 0.105, 0.075))
    rough = g.math("ADD", 0.9, g.math("MULTIPLY", grain, 0.08))
    height = g.math("ADD", g.math("ADD", g.math("MULTIPLY", grain, 0.3), g.math("MULTIPLY", clump, 0.5)),
                    g.math("MULTIPLY", peb, 0.6))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.004))


# ---------------------------------------------------------------- the kit

KIT = []  # part objects, in kit_part order
META = {}  # name -> dict(index, dims, gash, ...)
CONTEXT = []  # occluders that give the bags contact shadow in the AO bake, deleted after it


def set_attr(me, name, domain, kind, values):
    a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
    a.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", values)


def kit_part(name, bm, mat, dirt=0.5, style=0.0, dims=(0.28, 0.14, 0.09), gash=None, context=True, **meta):
    obj = tk.mesh_object("Kit_" + name, bm, mat)
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    set_attr(me, "lco", "POINT", "FLOAT_VECTOR", co)
    set_attr(me, "kd", "POINT", "FLOAT_VECTOR", np.tile(np.array([dirt, 1.0 if gash else 0.0, style], np.float32), n))
    set_attr(me, "kdim", "POINT", "FLOAT_VECTOR", np.tile(np.array(dims, np.float32), n))
    set_attr(me, "kg", "POINT", "FLOAT_VECTOR", np.tile(np.array(gash if gash else (0.0, 0.0, 0.1), np.float32), n))
    set_attr(me, "kpart", "FACE", "INT", np.full(len(me.polygons), len(KIT), np.int32))
    for p in me.polygons:
        p.use_smooth = True
    META[name] = dict(index=len(KIT), dims=dims, gash=gash, context=context, **meta)
    KIT.append(obj)
    return obj


def hard_part(obj):
    """Splits a hard-surface part's sharp edges so it keeps them once rebuilt with smooth shading."""
    mod = obj.modifiers.new("Split", "EDGE_SPLIT")
    mod.split_angle = math.radians(40)
    tk.apply_modifiers(obj)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def build_kit():
    burlap = burlap_material("Burlap")
    sand = sand_material("SandSpill")
    wood = tk.photo_material("StakeWood", "weathered_planks", scale=2.2, sat=0.8, value=0.95, exposed=None, grime=0.9,
                             grit=0.6)
    twine = tk.grimy("Twine", (0.33, 0.25, 0.14), roughness=0.9, grime=0.4, grime_set="rust_coarse_01", scale=3.0,
                     bump_scale=420.0, bump=0.5, grit=0.3, dirt_range=(0.15, 0.04))
    core = tk.plain("CoreFill", CORE_COL, roughness=0.95, grime=0.3)

    dims_full = (BAG_L / 2, BAG_W / 2, BAG_H / 2)
    # Filled bags: two shapes for each dirt level (muddy bottom courses, middle, clean upper courses)
    for name, dirt, seed in (("FA0", 0.9, 1), ("FA1", 0.82, 2), ("FB0", 0.5, 3), ("FB1", 0.42, 4), ("FC0", 0.15, 5),
                             ("FC1", 0.22, 6)):
        rnd = random.Random(seed)
        v, q = pillow(BAG_L, BAG_W, BAG_H, nx=5, seed=seed, sewn=rnd.uniform(0.52, 0.6), tuck=rnd.uniform(0.66, 0.74),
                      lump=rnd.uniform(0.011, 0.016), bend=rnd.uniform(-0.06, 0.06), twist=rnd.uniform(-0.06, 0.06))
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, dims=dims_full, kind="full")
    # Bags split in halves across the block seams (one per dirt level): left half (x <= 0) and right half
    for name, dirt, seed in (("H0", 0.86, 21), ("H1", 0.46, 22), ("H2", 0.18, 23)):
        v, q = pillow(BAG_L, BAG_W, BAG_H, nx=4, seed=seed, quiet=(0.035, 0.1))
        lo = np.array([p[:] for p in v]).min(axis=0)
        hi = np.array([p[:] for p in v]).max(axis=0)
        for side, keep_neg in (("L", True), ("R", False)):
            kit_part(name + side, half_bm(v, q, keep_neg), burlap, dirt=dirt, dims=dims_full, kind="half",
                     parent_size=tuple(hi - lo), parent_center=tuple((hi + lo) / 2))
    # Short bags for the ends of runs
    for name, dirt, seed in (("SA", 0.8, 31), ("SC", 0.28, 32)):
        v, q = pillow(SHORT_L, BAG_W, BAG_H, nx=4, seed=seed, lump=0.01)
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, dims=(SHORT_L / 2, BAG_W / 2, BAG_H / 2), kind="short")
    # Split bags: a jagged tear on the -y side, the front slumped in round it
    for name, dirt, seed, gx in (("SP0", 0.7, 41, 0.05), ("SP1", 0.3, 42, -0.07)):
        v, q = pillow(BAG_L, BAG_W, BAG_H, nx=5, seed=seed, lump=0.011)
        push_region(v, (gx, -BAG_W / 2, 0.0), 0.15, (0.0, 0.03, -0.006))
        push_region(v, (gx, -BAG_W / 2 * 0.7, BAG_H / 2), 0.16, (0.0, 0.0, -0.022))
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, dims=dims_full, gash=(gx, -0.005, 0.085), kind="split",
                 tear=(gx, -BAG_W / 2 + 0.03, -0.005))
    # Deflated bags: half the sand gone, flat and slack
    for name, dirt, seed in (("DF0", 0.72, 51), ("DF1", 0.3, 52)):
        v, q = pillow(0.58, 0.31, 0.112, nx=5, seed=seed, sewn=0.45, tuck=0.6, lump=0.017, sag=0.4)
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, style=3.0, dims=(0.29, 0.16, 0.0575), kind="defl")
    # A burst bag: a flattened torn shell, the top front ripped open
    for name, dirt, seed, gx in (("BU0", 0.6, 61, 0.03), ("BU1", 0.25, 62, -0.06)):
        v, q = pillow(0.58, 0.30, 0.12, nx=5, seed=seed, sewn=0.5, tuck=0.65, lump=0.022, sag=0.4)
        push_region(v, (gx, -0.15, 0.0), 0.17, (0.0, 0.035, -0.012))
        push_region(v, (gx, -0.08, 0.05), 0.18, (0.0, 0.0, -0.02))
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, style=4.0, dims=(0.29, 0.15, 0.06), gash=(gx, 0.0, 0.15),
                 kind="burst", tear=(gx, -0.12, 0.0))
    # Torn flaps of burlap
    for name, seed in (("FL0", 71), ("FL1", 72)):
        kit_part(name, flap_bm(seed), burlap, dirt=0.45, style=2.0, dims=(0.11, 0.03, 4.0), context=False,
                 kind="flap")
    # Empty bags: folded flat for the stack, and one opened flat to drape
    for name, dirt, seed in (("EB0", 0.1, 81), ("EB1", 0.25, 82)):
        v, q = pillow(0.40, 0.36, 0.026, nx=5, ny=4, nz=1, seed=seed, sewn=0.75, tuck=0.75, lump=0.003,
                      cap_bulge=(0.0, 0.01), ears=0.006)
        kit_part(name, bm_from(v, q), burlap, dirt=dirt, style=1.0, dims=(0.2, 0.18, 0.013), kind="empty")
    v, q = pillow(0.74, 0.37, 0.014, nx=8, ny=3, nz=1, seed=83, sewn=0.7, tuck=0.7, lump=0.003, cap_bulge=(0.0, 0.0),
                  ears=0.01)
    kit_part("EU0", bm_from(v, q), burlap, dirt=0.15, style=1.0, dims=(0.37, 0.185, 0.007), kind="empty")
    # Sand: a pile, a tongue spilling from a tear, a trickle down a face
    kit_part("PL", pile_bm(5), sand, style=5.0, context=False, kind="sand")
    kit_part("TR", trickle_bm(), sand, style=6.0, context=False, kind="sand")
    # A wooden stake and twine
    stake = tk.box("StakeTmp", (0.045, 0.045, 0.40), (0.0, 0.0, 0.2), wood, bevel_width=0.004)
    tk.dent(stake, 0.002, 0.03, seed=3)
    hard_part(stake)
    bm = bmesh.new()
    bm.from_mesh(stake.data)
    bpy.data.objects.remove(stake)
    kit_part("SK", bm, wood, context=False, kind="stake")
    tw = tk.tube("TwineTmp", [(i / 12.0, 0.0, 0.0) for i in range(13)], 0.0025, twine, resolution=0)
    bm = bmesh.new()
    bm.from_mesh(tw.data)
    bpy.data.objects.remove(tw)
    kit_part("TW", bm, twine, context=False, kind="twine")
    tw = tk.tube("WrapTmp", helix_points(0.0345, 0.0, 0.012, 1.6, 14), 0.0026, twine, resolution=0)
    bm = bmesh.new()
    bm.from_mesh(tw.data)
    bpy.data.objects.remove(tw)
    kit_part("TWW", bm, twine, context=False, kind="twine")
    # The core filler swatch
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.09)
    kit_part("CORE", bm, core, context=False, kind="core")
    return dict(burlap=burlap, sand=sand, wood=wood, twine=twine, core=core)


def layout_kit():
    """Spreads the parts on a grid (far enough apart that the AO bake only sees each part itself and its context
    slab) and adds a slab under every bag for contact shadow where bags rest on each other."""
    col_w, row_h, per_row = 0.95, 0.8, 7
    k = 0
    for obj in KIT:
        name = obj.name[4:]
        if name == "PL":
            continue
        cx, cy = (k % per_row) * col_w, (k // per_row) * row_h
        obj.location = (cx, cy, 0.0)
        k += 1
        if META[name]["context"]:
            co = np.array([v.co[:] for v in obj.data.vertices])
            lo, hi = co.min(axis=0), co.max(axis=0)
            slab = tk.box("Ctx_" + name, (hi[0] - lo[0] + 0.12, hi[1] - lo[1] + 0.12, 0.04),
                          (cx + (lo[0] + hi[0]) / 2, cy + (lo[1] + hi[1]) / 2, lo[2] - 0.023), KIT[0].data.materials[0])
            CONTEXT.append(slab)
    rows = (k + per_row - 1) // per_row
    KIT[META["PL"]["index"]].location = (1.2, rows * row_h + 0.4, 0.0)
    bpy.context.view_layer.update()


def unity_light():
    """The light the vanilla references were rendered with in Unity: a warm sun (1.4) from 40/-30 degrees, trilight
    ambient (sky 0.45/0.5/0.6, equator 0.35, ground 0.18; gamma colors, so about 0.17/0.21/0.32, 0.1 and 0.03
    linear) and a floor of 0.3/0.29/0.27. Unity has no bounce light, so the world is a sky/equator/ground gradient
    and the floor is dark. Returns the sun and the floor."""
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
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20.0)
    bmesh.ops.translate(bm, vec=(0, 0, Z0), verts=bm.verts)
    fl = tk.mesh_object("CmpFloor", bm, mat)
    return sun, fl


def kit_preview():
    """Debug (mode 'kit'): unbaked kit bags under the vanilla reference's light, beside a crop of that render."""
    for o in CONTEXT + KIT:
        o.hide_render = True
    bpy.context.scene.world = bpy.data.worlds.new("Cmp")
    unity_light()

    def dup(name, loc, rotz=0.0, scale=(1.0, 1.0, 1.0)):
        src = KIT[META[name]["index"]]
        o = tk.link(bpy.data.objects.new("Pv_" + name, src.data))
        o.location = loc
        o.rotation_euler = (math.radians(-4.0), 0.0, math.radians(rotz))
        o.scale = scale
        return o

    rows = [["FA0", "FA1", "FB0"], ["FB1", "SP0", "FB0"], ["FC0", "DF0", "FC1"], ["FC1", "FC0", "BU0"],
            ["FC0", "FB1", "FC1"], ["FC1", "FC0", "FB0"]]
    zc = Z0 + 0.09
    for k, row in enumerate(rows):
        off = 0.0 if k % 2 == 0 else 0.25
        for i, n in enumerate(row):
            slack = n in ("DF0", "BU0")
            dup(n, (-0.55 + i * 0.5 + off, -0.012 * k, zc - (0.03 if slack else 0.0)), rotz=180.0 * ((i + k) % 2))
        zc += P
    cam = tk.camera("KitCam", (1.25, -2.6, 1.0), (0.1, 0.0, 0.0), lens=50)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle_y = math.radians(30.0)
    ours = os.path.join(PREVIEWS, "dbg_kit_ours.png")
    tk.render(cam, ours, res=(700, 960), samples=64)
    a = image_array(ours)
    ref = image_array(os.path.join(os.path.dirname(PREVIEWS), "ref-sandbag_straight_01prefab.png"))
    h = ref.shape[0]
    crop = ref[h - 960:h - 480, 1590:1940]
    crop = np.repeat(np.repeat(crop, 2, axis=0), 2, axis=1)
    save_rgb(np.concatenate([crop[..., :3], a[..., :3]], axis=1), os.path.join(PREVIEWS, "dbg_kit_vs_vanilla.png"))
    os.remove(ours)
    # the albedo alone (straight from the material, no light), and its numbers on the bags
    alb = os.path.join(PREVIEWS, "dbg_kit_albedo.png")
    tk._with_emission(KIT[META["FA0"]["index"]], "color", lambda: tk.render(cam, alb, res=(700, 960), samples=16))
    a = image_array(alb)[..., :3]
    m = (a.max(axis=2) - a.min(axis=2)) > 0.02
    px = a[m]
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    log("albedo on bags (sRGB): mean", (px.mean(axis=0) * 255).round(1), "p10/50/90 luma",
        (np.percentile(lum, [10, 50, 90]) * 255).round(1), "| vanilla estimate: mean ~(85, 72, 60), lit ~(100, 85, 70)")


# ---------------------------------------------------------------- bake, then cut the kit back into templates

class Tpl:
    """A baked kit part: vertices in its own frame, triangles and their UVs in the shared atlas."""

    def __init__(self, name, V, F, UV, meta):
        self.name, self.V, self.F, self.UV, self.meta = name, V, F, UV, meta
        self.lo, self.hi = V.min(axis=0), V.max(axis=0)
        self.size = self.hi - self.lo
        self.center = (self.lo + self.hi) / 2.0


def bake_kit():
    for o in KIT:
        o.location = (o.location[0] + 40.0, o.location[1] + 40.0, 8.0)
    for o in CONTEXT:
        o.location = (o.location[0] + 40.0, o.location[1] + 40.0, 8.0)
    kit = tk.join(list(KIT), "SandbagKit")
    kit = tk.triangulate(kit)
    tk.smart_uvs(kit)
    paths = tk.bake_atlas(kit, ASSETS, MAT_NAME)
    match_vanilla(paths)
    for o in CONTEXT:
        bpy.data.objects.remove(o)
    return kit, paths


# The vanilla sandbags' textures, read from the game's bundle (FortificationsExpanded's RefDump): albedo about 40%
# brighter than our first bake, and baked occlusion mostly light (mean 0.91 against our 0.68). With the darker
# values the wall's shaded side went nearly black next to vanilla sandbags in the game's shader.
ALBEDO_GAIN = 1.3
ALBEDO_DESATURATE = 0.3  # toward grey: vanilla burlap is greyer and less orange in sunlight
OCCLUSION_KEEP = 0.3  # how much of the baked occlusion's darkening to keep


def _grade_albedo(px):
    rgb = px[..., :3] * ALBEDO_GAIN
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    return np.clip(rgb + (luma[..., None] - rgb) * ALBEDO_DESATURATE, 0.0, 1.0)


def match_vanilla(paths):
    for key, fn in (("albedo", _grade_albedo), ("rmom", None)):
        img = bpy.data.images.load(paths[key], check_existing=False)
        px = np.empty(len(img.pixels), np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        if key == "albedo":
            px[:, :3] = fn(px)
        else:
            px[:, 2] = 1.0 - (1.0 - px[:, 2]) * OCCLUSION_KEEP
        img.pixels.foreach_set(px.ravel())
        img.filepath_raw = paths[key]
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
    print("[sandbags] graded albedo x%.2f, occlusion kept %.0f%%" % (ALBEDO_GAIN, OCCLUSION_KEEP * 100))


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
        out[name] = Tpl(name, lco[used], remap[f], UV[sel], m)
    return out


# ---------------------------------------------------------------- pieces: bags in courses

def depth_at(piece, z):
    """Outer depth of the wall at height z (battered both faces)."""
    if piece == "Low":
        return 0.74 - 0.14 * (z - Z0) / 1.0
    return 0.88 - 0.28 * (z - Z0) / 2.0


def course_depth(piece, k):
    return depth_at(piece, Z0 + (k + 0.5) * P)


def rows_for(D):
    n = 3 if D > 0.72 else 2
    w = D / n
    return [(-D / 2 + w * (r + 0.5), w, r, n) for r in range(n)]


def end_pos(k):
    """Where the End piece's courses stop on -X: racked back as they rise."""
    return -0.47 + 0.2 * k / 11.0


class Bag:
    def __init__(self, kind, axis, lat, w, s0, s1, k, role, side=0, top=False):
        self.kind, self.axis, self.lat, self.w, self.s0, self.s1 = kind, axis, lat, w, s0, s1
        self.k, self.role, self.side, self.top = k, role, side, top
        self.removed = False
        self.dmg = None
        self.dz = self.tilt = self.shift = self.yaw = self.roll = 0.0
        self.flip = None
        self.M = None
        self.tpl = None

    @property
    def smid(self):
        return (self.s0 + self.s1) / 2.0

    def xy(self):
        return (self.smid, self.lat) if self.axis == "X" else (self.lat, self.smid)

    def outward(self):
        """Unit vector (x, y) out of the face this bag lies on, or None for a hidden middle bag."""
        if self.side == 0:
            return None
        return (0.0, float(self.side)) if self.axis == "X" else (float(self.side), 0.0)


HALF_LEN = BAG_L / 2.0


def fill_run(s0, pat):
    """Bags (kind, start, end) along a run from s0 (a free rounded end) to the +seam of a block: pattern A ends
    with a whole bag reaching 0.53 (it laps into the neighbour), pattern B with the half bag cut at 0.5 and a whole
    bag across 0 before it."""
    if pat == "A":
        fixed = [["full", -0.03, 0.53]]
    else:
        fixed = [["halfL", 0.5 - HALF_LEN, 0.5], ["full", -0.28, 0.28]]
    last = fixed[-1]
    if last[0] == "full" and last[1] < s0 - 0.03:
        last[1] = s0 - 0.03
        if last[2] - last[1] < 0.12:
            fixed.pop()
        elif last[2] - last[1] < 0.42:
            last[0] = "short"
    cur = fixed[-1][1]
    items = []
    span = cur + OVL - s0
    if span > 0.02 and fixed[-1][0] == "full" and fixed[-1][2] - s0 <= 0.74 and span <= 0.24:
        fixed[-1][1] = s0
    elif span > 0.14:
        n = max(1, int(round((span - OVL) / (BAG_L - OVL))))
        ln = (span + (n - 1) * OVL) / n
        for i in range(n):
            a = s0 + i * (ln - OVL)
            items.append(["full" if ln >= 0.42 else "short", a, a + ln])
    elif span > 0.02 and fixed[-1][0] in ("full", "short"):
        fixed[-1][1] = s0
        if fixed[-1][2] - fixed[-1][1] >= 0.42:
            fixed[-1][0] = "full"
    return items + fixed[::-1]


def layout_wall(piece, n_courses):
    bags = []
    for k in range(n_courses):
        D = course_depth(piece, k)
        top = k == n_courses - 1
        for lat, w, r, n in rows_for(D):
            side = -1 if r == 0 else (1 if r == n - 1 else 0)
            if side == 0 and not top:
                continue  # hidden inside the wall: the core stands in for it
            role = "face" if (side != 0 or top) else "mid"
            if k % 2 == 0:
                for s0, s1 in ((-0.53, 0.03), (-0.03, 0.53)):
                    bags.append(Bag("full", "X", lat, w, s0, s1, k, role, side, top))
            else:
                bags.append(Bag("halfR", "X", lat, w, -0.5, -0.5 + HALF_LEN, k, "seam", side, top))
                bags.append(Bag("full", "X", lat, w, -0.28, 0.28, k, role, side, top))
                bags.append(Bag("halfL", "X", lat, w, 0.5 - HALF_LEN, 0.5, k, "seam", side, top))
    return bags


def layout_end(n_courses):
    bags = []
    for k in range(n_courses):
        D = course_depth("Wall", k)
        top = k == n_courses - 1
        pat = "A" if k % 2 == 0 else "B"
        e = end_pos(k)
        start = e
        if k % 2 == 1:
            hx = e + 0.14
            spans = [(-D / 2, 0.03), (-0.03, D / 2)] if D > 0.68 else [(-D / 2, D / 2)]
            for a, b in spans:
                bags.append(Bag("full", "Y", hx, 0.28, a, b, k, "header", -1, top))
            start = e + 0.25
        for lat, w, r, n in rows_for(D):
            side = -1 if r == 0 else (1 if r == n - 1 else 0)
            for i, (kind, s0, s1) in enumerate(fill_run(start, pat)):
                if side == 0 and not top and i > 0:
                    continue
                role = "seam" if kind.startswith("half") else "face"
                bags.append(Bag(kind, "X", lat, w, s0, s1, k, role, side, top))
    return bags


def layout_corner(n_courses):
    bags = []
    for k in range(n_courses):
        D = course_depth("Wall", k)
        h = D / 2.0
        top = k == n_courses - 1
        main, stub = ("X", "Y") if k % 2 == 0 else ("Y", "X")
        pat = "A" if k % 2 == 0 else "B"
        for lat, w, r, n in rows_for(D):
            side = -1 if r == 0 else (1 if r == n - 1 else 0)
            for i, (kind, s0, s1) in enumerate(fill_run(-h - 0.01, pat)):
                if side == 0 and not top and i > 0:
                    continue
                role = "seam" if kind.startswith("half") else ("face" if (side == -1 or top or i == 0) else "stub")
                bags.append(Bag(kind, main, lat, w, s0, s1, k, role, side, top))
            if side == 0 and not top:
                continue
            if pat == "A":
                if h < 0.4 or top:
                    bags.append(Bag("stubR", stub, lat, w, 0.53 - HALF_LEN, 0.53, k, "stub", side, top))
            else:
                bags.append(Bag("halfL", stub, lat, w, 0.5 - HALF_LEN, 0.5, k, "seam", side, top))
    return bags


PIECES = {
    "Wall": dict(full=12, half=6, layout=lambda n: layout_wall("Wall", n)),
    "Low": dict(full=6, half=3, layout=lambda n: layout_wall("Low", n)),
    "Corner": dict(full=12, half=6, layout=layout_corner),
    "End": dict(full=12, half=6, layout=layout_end),
}
LEAN = math.degrees(math.atan(0.14 / 2.0))


def dirt_level(k):
    return 0 if k <= 1 else (1 if k <= 4 else 2)


FILLED = {0: ("FA0", "FA1"), 1: ("FB0", "FB1"), 2: ("FC0", "FC1")}
SHORTS = {0: "SA", 1: "SA", 2: "SC"}
SPLITS = {0: "SP0", 1: "SP0", 2: "SP1"}
DEFLS = {0: "DF0", 1: "DF0", 2: "DF1"}


def realize(bag, T, rnd):
    """The bag's template and placement matrix (bag.M)."""
    lvl = dirt_level(bag.k)
    R_axis = m_rot("Z", 90.0) if bag.axis == "Y" else np.eye(4)
    lean = LEAN * (1.0 if bag.side else 0.0)
    if bag.kind in ("halfL", "halfR", "stubR"):
        tpl = T[("H%d" % lvl) + ("L" if bag.kind == "halfL" else "R")]
        psize, pc = np.array(tpl.meta["parent_size"]), np.array(tpl.meta["parent_center"])
        S = m_scale(1.0, bag.w / psize[1], (P + OVZ) / psize[2]) @ m_trans((0.0, -pc[1], -pc[2]))
        seam = bag.s1 if bag.kind == "halfL" else bag.s0
        zc = Z0 + bag.k * P + P / 2.0 - (OVZ / 2.0 if bag.top else 0.0) + bag.dz
        tilt = bag.side * lean
        R = m_rot("X", tilt) if bag.axis == "X" else m_rot("Y", -tilt)
        c = (seam, bag.lat, zc) if bag.axis == "X" else (bag.lat, seam, zc)
        bag.tpl, bag.M = tpl, m_trans(c) @ R @ R_axis @ S
        return
    natural = False
    if bag.dmg == "split":
        name = SPLITS[lvl]
    elif bag.dmg == "defl":
        name, natural = DEFLS[lvl], True
    elif bag.dmg == "burst":
        name, natural = ("BU0" if lvl < 2 else "BU1"), True
    elif bag.kind == "short":
        name = SHORTS[lvl]
    else:
        name = rnd.choice(FILLED[lvl])
    tpl = T[name]
    length = bag.s1 - bag.s0
    sx = length / tpl.size[0]
    if natural:
        sy = bag.w / tpl.size[1] * rnd.uniform(0.98, 1.06)
        sz = rnd.uniform(0.92, 1.05)
        hgt = tpl.size[2] * sz
        zc = Z0 + bag.k * P + hgt / 2.0 - 0.006
    else:
        sy = bag.w / tpl.size[1] * rnd.uniform(0.96, 1.04)
        hgt = P + OVZ + (0.012 if bag.top else 0.0)
        sz = hgt / tpl.size[2]
        zc = Z0 + bag.k * P + P / 2.0 + (0.006 - OVZ if bag.top else 0.0) + rnd.uniform(-0.005, 0.004)
    zc += bag.dz
    flip = bag.flip
    if flip is None:
        if tpl.meta.get("tear") and bag.side:
            # turn the tear to face out of the wall: local -y -> world outward
            o = bag.outward()
            loc_out = (0.0, -1.0) if bag.axis == "X" else (1.0, 0.0)
            flip = (o[0] * loc_out[0] + o[1] * loc_out[1]) < 0
        else:
            flip = rnd.random() < 0.5
    S = m_scale(sx, sy, sz) @ m_trans(-tpl.center)
    Rf = m_rot("Z", 180.0) if flip else np.eye(4)
    Ry = m_rot("Z", rnd.uniform(-3.0, 3.0) + bag.yaw)
    tilt = bag.side * (lean + rnd.uniform(-1.0, 1.0) - bag.tilt)
    R = m_rot("X", tilt) if bag.axis == "X" else m_rot("Y", -tilt)
    roll = bag.roll + rnd.uniform(-2.0, 2.0)
    R = (m_rot("Y", roll) if bag.axis == "X" else m_rot("X", -roll)) @ R
    js = rnd.uniform(-0.006, 0.006)
    jl = rnd.uniform(-0.006, 0.006) + bag.side * bag.shift
    c = (bag.smid + js, bag.lat + jl, zc) if bag.axis == "X" else (bag.lat + jl, bag.smid + js, zc)
    bag.tpl, bag.M = tpl, m_trans(c) @ R @ R_axis @ Ry @ Rf @ S


def place(tpl, M):
    return tpl.V @ M[:3, :3].T + M[:3, 3]


class Item:
    def __init__(self, V, F, UV, occ=True, cull=True, kind="bag", seam=False):
        self.V, self.F, self.UV, self.occ, self.cull, self.kind, self.seam = V, F, UV, occ, cull, kind, seam

    def bounds(self):
        return self.V.min(axis=0), self.V.max(axis=0)


def item_of(tpl, M, **kw):
    return Item(place(tpl, M), tpl.F.copy(), tpl.UV.copy(), **kw)


# ---------------------------------------------------------------- damage plans

NOTCH = {  # main-run notch center, half width at the top, courses deep (full / half)
    "Wall": dict(c=-0.06, w=0.34, depth=(4, 3)),
    "Low": dict(c=0.12, w=0.32, depth=(2, 2)),
    "End": dict(c=-0.22, w=0.3, depth=(4, 3)),
    "Corner": dict(c=None, w=0.48, depth=(4, 3)),
}


def notch_region(piece, k, n_courses, stage):
    """The notch as an (x0, x1, y0, y1) box at course k, or None below it: a V that widens upward."""
    spec = NOTCH[piece]
    depth = spec["depth"][0 if stage == "Full" else 1]
    top = n_courses - 1
    if k <= top - depth:
        return None
    hw = spec["w"] * (k - (top - depth)) / depth
    if piece == "Corner":
        h = course_depth("Wall", k) / 2.0
        return (-h - 0.1, -h + 0.08 + 1.3 * hw, -h - 0.1, -h + 0.08 + 1.3 * hw)
    return (spec["c"] - hw, spec["c"] + hw, -1.0, 1.0)


def bag_box(b):
    if b.axis == "X":
        return (b.s0, b.s1, b.lat - b.w / 2, b.lat + b.w / 2)
    return (b.lat - b.w / 2, b.lat + b.w / 2, b.s0, b.s1)


def overlap_frac(b, box):
    x0, x1, y0, y1 = bag_box(b)
    ox = max(0.0, min(x1, box[1]) - max(x0, box[0]))
    oy = max(0.0, min(y1, box[3]) - max(y0, box[2]))
    return (ox * oy) / ((x1 - x0) * (y1 - y0))


def plan_damage(bags, piece, stage, level, rnd):
    plan = dict(sags=[], spills=[], trickles=[], piles=[], flaps=[], fallen=[], notch=[])
    if level == 0:
        return plan
    n_courses = max(b.k for b in bags) + 1
    visible = [b for b in bags if b.role in ("face", "seam", "header")]

    def candidates(min_k=0):
        return [b for b in bags if b.role in ("face", "header") and b.kind in ("full", "short") and not b.removed
                and b.dmg is None and b.k >= min_k]

    def add_sag(b, amount):
        x, y = b.xy()
        plan["sags"].append(dict(axis=b.axis, s=b.smid, half=(b.s1 - b.s0) / 2, lat=b.lat, side=b.side,
                                 z=Z0 + (b.k + 1) * P - 0.03, amount=amount))

    if level == 1:
        n = max(3, int(round(0.2 * len(visible))))
        pool = candidates(1)
        rnd.shuffle(pool)
        chosen = pool[:n]
        for i, b in enumerate(chosen):
            if i % 2 == 0 and b.side != 0:
                b.dmg = "split"
                if b.k >= 2 and rnd.random() < 0.6:
                    plan["trickles"].append(b)
            else:
                b.dmg = "defl"
                add_sag(b, P - 0.115 - 0.004)
        others = candidates()
        for b in rnd.sample(others, int(round(0.15 * len(others)))):
            b.shift = rnd.uniform(0.008, 0.02)
            b.yaw = rnd.uniform(-4.0, 4.0)
            b.tilt = rnd.uniform(-2.0, 6.0)
        under = [b for b in plan["trickles"] if b.side == -1 and b.axis == "X"]
        plan["piles"].append(dict(x=under[0].smid if under else rnd.uniform(-0.2, 0.2), side=-1, rx=0.24, h=0.12))
        return plan

    # level 2: a collapsed notch, the top course partly gone, a third of what's visible burst or missing
    for b in bags:
        box = notch_region(piece, b.k, n_courses, stage)
        if box is None:
            continue
        if overlap_frac(b, box) > 0.45:
            b.removed = True
            plan["notch"].append(b)
        elif overlap_frac(b, box) > 0.05:
            # slumped toward the gap
            cx = (box[0] + box[1]) / 2 if b.axis == "X" else (box[2] + box[3]) / 2
            b.roll = (1.0 if cx > b.smid else -1.0) * rnd.uniform(8.0, 16.0)
            b.dz = -rnd.uniform(0.02, 0.045)
            b.tilt = rnd.uniform(3.0, 10.0)
    if piece != "Corner":
        # nothing floats: a bag needs a quarter of its length resting on what is left of the course below
        for k in range(1, n_courses):
            below = [x for x in bags if x.k == k - 1 and not x.removed and x.axis == "X"]
            for b in [x for x in bags if x.k == k and not x.removed and x.axis == "X"]:
                sup = sum(max(0.0, min(b.s1, x.s1) - max(b.s0, x.s0)) for x in below
                          if b.side == 0 or x.side == b.side)
                if sup < 0.25 * (b.s1 - b.s0):
                    b.removed = True
                    plan["notch"].append(b)
    top = n_courses - 1
    for b in [b for b in candidates(top) if not b.removed]:
        r = rnd.random()
        if r < 0.25:
            b.removed = True
        elif r < 0.65:
            b.tilt = rnd.uniform(8.0, 22.0)
            b.dz = -rnd.uniform(0.015, 0.05)
            b.shift = rnd.uniform(0.01, 0.035)
            b.yaw = rnd.uniform(-8.0, 8.0)
    removed_vis = len([b for b in visible if b.removed])
    want = int(round(len(visible) / 3.0)) - removed_vis
    pool = [b for b in candidates(1) if b.k < top]
    rnd.shuffle(pool)
    for b in pool[:min(7, max(3, want))]:
        b.dmg = "burst"
        add_sag(b, P - 0.12 - 0.006)
        if b.side and len(plan["flaps"]) < (2 if piece == "End" else 3) and rnd.random() < 0.6:
            plan["flaps"].append(b)
        if b.side and b.k >= 2 and len(plan["trickles"]) < 3 and rnd.random() < 0.4:
            plan["trickles"].append(b)
    for b in candidates():
        if rnd.random() < 0.2:
            b.shift = rnd.uniform(0.01, 0.025)
            b.yaw = rnd.uniform(-5.0, 5.0)
            b.tilt = rnd.uniform(0.0, 8.0)
    # bags from the gap lying slumped in it, some hanging over the face
    gone = [b for b in plan["notch"] if b.side != 0]
    rnd.shuffle(gone)
    for b in gone[:1 if piece == "End" else 2]:
        plan["fallen"].append(b)
    for k in range(1, n_courses):
        below = [x for x in bags if x.k == k - 1 and not x.removed and (x.dz < -0.005 or x.roll)]
        for b in [x for x in bags if x.k == k and not x.removed]:
            drop = 0.0
            for x in below:
                if overlap_frac(b, bag_box(x)) > 0.15:
                    drop = min(drop, x.dz - 0.12 * abs(math.sin(math.radians(x.roll))))
            if drop < 0.0:
                b.dz = min(b.dz, drop)
    plan["piles"] += [dict(x=-0.12 if piece != "Low" else 0.1, side=-1, rx=0.44, h=0.3),
                      dict(x=0.34, side=-1, rx=0.22, h=0.18) if piece != "End" else None,
                      dict(x=0.05, side=1, rx=0.36, h=0.24)]
    return plan


# ---------------------------------------------------------------- deforming, conforming, culling

def apply_sags(items, sags):
    for it in items:
        if it.kind != "bag" or it.seam:
            continue
        V = it.V
        for s in sags:
            sc = V[:, 0] if s["axis"] == "X" else V[:, 1]
            lc = V[:, 1] if s["axis"] == "X" else V[:, 0]
            d = np.abs(sc - s["s"])
            fs = np.clip((s["half"] + 0.12 - d) / (0.5 * s["half"] + 0.12), 0.0, 1.0)
            fs = fs * fs * (3 - 2 * fs)
            if s["side"]:
                q = (lc - s["lat"]) * s["side"]
                fl = np.clip((q + 0.2) / 0.2, 0.0, 1.0)
            else:
                fl = np.clip(1.0 - np.abs(lc - s["lat"]) / 0.3, 0.0, 1.0)
            fz = np.clip((V[:, 2] - (s["z"] - 0.03)) / 0.05, 0.0, 1.0)
            fz = fz * np.clip(1.0 - (V[:, 2] - s["z"]) / 0.5, 0.0, 1.0)  # the settling fades a few courses up
            V[:, 2] -= s["amount"] * fs * fl * fz


def bvh_of(items):
    Vs, Fs, off = [], [], 0
    for it in items:
        Vs.append(it.V)
        Fs.append(it.F + off)
        off += len(it.V)
    V = np.concatenate(Vs)
    F = np.concatenate(Fs)
    return BVHTree.FromPolygons(V.tolist(), F.tolist(), all_triangles=True)


def conform(V, offs, outward, bvh, gap=0.003, only_out=False):
    """Pushes points onto the surface along `outward` (unit xy): each point is moved to where a ray coming in from
    outside first hits the bags, plus gap + its own offset (so a thin shell keeps its thickness)."""
    o = Vector((outward[0], outward[1], 0.0))
    for i in range(len(V)):
        p = Vector(V[i])
        start = p + o * 0.6
        hit = bvh.ray_cast(start, -o, 1.2)
        if hit[0] is not None:
            q = hit[0] + o * (gap + offs[i])
            if only_out and (q - p).dot(o) <= 0:
                continue
            V[i] = q[:]


RAY_DIRS = [Vector(d).normalized() for d in ((0.31, 0.12, 0.94), (-0.27, 0.91, -0.31))]


def _parity(bvh, p, d):
    """Crossings of a ray from p along d through a closed mesh: odd means p is inside."""
    n, o = 0, p
    for _ in range(12):
        hit = bvh.ray_cast(o, d, 3.0)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + d * 1e-5
    return n % 2 == 1


def inside_mask(V, bvh, margin=0.003, pending=None):
    """Points at least `margin` inside a closed mesh: the nearest surface faces away from them, and two rays agree
    (the nearest-normal test alone is fooled near creases, like a bag's pinched ends)."""
    out = np.zeros(len(V), bool)
    for i in range(len(V)):
        if pending is not None and not pending[i]:
            continue
        p = Vector(V[i])
        loc, nor, _, dist = bvh.find_nearest(p, 0.4)
        if loc is None or (p - loc).dot(nor) >= -margin or dist < margin:
            continue
        if all(_parity(bvh, p, d) for d in RAY_DIRS):
            out[i] = True
    return out


def cull(items):
    """Drops every triangle whose corners, edge midpoints and middle all lie inside another closed part (a bag,
    the core): the bag faces pressed into the wall and the courses above and below."""
    occ = [(it, it.bounds(), BVHTree.FromPolygons(it.V.tolist(), it.F.tolist(), all_triangles=True))
           for it in items if it.occ]
    before = sum(len(it.F) for it in items)
    for it in items:
        if not it.cull or len(it.F) == 0:
            continue
        lo, hi = it.bounds()
        near = [bvh for other, (olo, ohi), bvh in occ
                if other is not it and not ((olo > hi + 0.01).any() or (ohi < lo - 0.01).any())]
        if not near:
            continue
        inside = np.zeros(len(it.V), bool)
        for bvh in near:
            inside |= inside_mask(it.V, bvh, pending=~inside)
            if inside.all():
                break
        cand = np.nonzero(inside[it.F].all(axis=1))[0]
        if len(cand) == 0:
            continue
        T3 = it.V[it.F[cand]]
        c = T3.mean(axis=1)
        pts = np.concatenate([c, (T3[:, 0] + T3[:, 1]) / 2, (T3[:, 1] + T3[:, 2]) / 2, (T3[:, 2] + T3[:, 0]) / 2,
                              (T3[:, 0] + c) / 2, (T3[:, 1] + c) / 2, (T3[:, 2] + c) / 2])
        ins = np.zeros(len(pts), bool)
        for bvh in near:
            ins |= inside_mask(pts, bvh, margin=0.003, pending=~ins)
        hidden = ins.reshape(7, -1).all(axis=0)
        keep = np.ones(len(it.F), bool)
        keep[cand[hidden]] = False
        F, UV = it.F[keep], it.UV[keep]
        used = np.unique(F)
        remap = np.full(len(it.V), -1, np.int64)
        remap[used] = np.arange(len(used))
        it.V, it.F, it.UV = it.V[used], remap[F], UV
    after = sum(len(it.F) for it in items)
    return before, after


# ---------------------------------------------------------------- the core

CORE_UV = None


def core_item(prisms):
    """A dark filler inside the wall so the gaps between bags never show daylight. Each prism: axis, the s
    positions of its sections (the first may slope: s at the bottom, sa_top at the top), half depth at the bottom
    and top, and a top height function of s (stepped down where bags are missing). Flat shaded."""
    V, F = [], []
    for pr in prisms:
        base = len(V)
        ss = pr["ss"]
        zb = Z0 + 0.004
        for i, s0 in enumerate(ss):
            for corner in range(4):
                bottom = corner in (0, 3)
                s = pr.get("sa_top", s0) if (i == 0 and not bottom) else s0
                z = zb if bottom else pr["top"](s0)
                frac = (z - Z0) / max(1e-6, pr["H"])
                hd = pr["hd0"] + (pr["hd1"] - pr["hd0"]) * frac
                lat = -hd if corner in (0, 1) else hd
                V.append((s, lat, z) if pr["axis"] == "X" else (lat, s, z))
        for i in range(len(ss) - 1):
            a, b = base + i * 4, base + (i + 1) * 4
            for c in range(4):
                c2 = (c + 1) % 4
                F.append((a + c, b + c, b + c2))
                F.append((a + c, b + c2, a + c2))
        last = base + (len(ss) - 1) * 4
        F += [(base, base + 1, base + 2), (base, base + 2, base + 3), (last, last + 2, last + 1),
              (last, last + 3, last + 2)]
    V = np.array(V, np.float64)
    bm = bm_from([Vector(v) for v in V], [list(f) for f in F])
    bm.verts.index_update()
    F = np.array([[v.index for v in f.verts] for f in bm.faces], np.int64)
    bm.free()
    P2 = V[F]
    V = P2.reshape(-1, 3)
    F = np.arange(len(V), dtype=np.int64).reshape(-1, 3)
    u0, v0, u1, v1 = CORE_UV
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    ru, rv = (u1 - u0) * 0.3, (v1 - v0) * 0.3
    UV = np.stack([cu + ru * np.sin(P2[..., 0] * 3.1 + P2[..., 2] * 1.3),
                   cv + rv * np.sin(P2[..., 1] * 2.7 + P2[..., 2] * 1.9)], axis=-1)
    return Item(V, F, UV, occ=True, cull=True, kind="core")


def core_for(piece, stage, n_courses, bags, sags=()):
    H = n_courses * P
    top_z = Z0 + H - P * 0.6
    removed = [b for b in bags if b.removed or b.dz < -0.01 or b.roll or (b.dmg and b.k == n_courses - 1)]

    def ranges(axis):
        out = []
        for b in removed:
            if b.axis == axis:
                lo, hi = b.s0, b.s1
            elif piece == "Corner":
                lo, hi = b.lat - b.w / 2, b.lat + b.w / 2
            else:
                continue
            # under a missing bag the core drops into the course below; under a slumped one, just under it
            z = Z0 + b.k * P - P * 0.4 if b.removed else Z0 + b.k * P + 0.03 + min(0.0, b.dz)
            out.append((lo, hi, z))
        # where a slack bag lets the courses above sink, the core's top sinks with them
        for sg in sags:
            if sg["axis"] == axis:
                lo, hi = sg["s"] - sg["half"] - 0.1, sg["s"] + sg["half"] + 0.1
            elif piece == "Corner":
                lo, hi = sg["lat"] - 0.18, sg["lat"] + 0.18
            else:
                continue
            reach = sg["amount"] * max(0.0, 1.0 - (Z0 + H - P / 2 - sg["z"]) / 0.5)
            if reach > 0.008:
                out.append((lo, hi, top_z - reach - 0.03))
        return out

    def top_fn(rs):
        def f(s):
            z = top_z
            for lo, hi, zz in rs:
                if lo <= s <= hi:
                    z = min(z, zz)
            return max(Z0 + 0.03, z)
        return f

    def secs(sa, sb, rs, start_lim):
        pts = {round(sa, 4), round(sb, 4)}
        for lo, hi, _ in rs:
            for v in (lo - 0.003, lo, hi, hi + 0.003):
                if start_lim + 0.004 < v < sb - 0.004:
                    pts.add(round(v, 4))
        return sorted(pts)

    kind = "Low" if piece == "Low" else "Wall"
    D0, D1 = depth_at(kind, Z0), depth_at(kind, Z0 + H)
    hd0, hd1 = D0 / 2 - 0.13, D1 / 2 - 0.13
    if piece in ("Wall", "Low"):
        rs = ranges("X")
        prisms = [dict(axis="X", ss=secs(-0.48, 0.48, rs, -0.48), hd0=hd0, hd1=hd1, H=H, top=top_fn(rs))]
    elif piece == "End":
        rs = ranges("X")
        sa0, sa1 = end_pos(0) + 0.15, end_pos(n_courses - 1) + 0.15
        prisms = [dict(axis="X", ss=secs(sa0, 0.48, rs, max(sa0, sa1)), sa_top=sa1, hd0=hd0, hd1=hd1, H=H,
                       top=top_fn(rs))]
    else:
        prisms = []
        for ax in ("X", "Y"):
            rs = ranges(ax)
            prisms.append(dict(axis=ax, ss=secs(-hd0, 0.48, rs, -hd1), sa_top=-hd1, hd0=hd0, hd1=hd1, H=H,
                               top=top_fn(rs)))
    return [core_item([pr]) for pr in prisms]  # one closed shell each, for the culler's ray test


# ---------------------------------------------------------------- extras: sand, flaps, drapes

def rot2(o):
    """Z rotation (degrees) turning local -y to the outward direction o."""
    return math.degrees(math.atan2(o[1], o[0])) + 90.0


def spill_item(T, b, bvh, rnd, big=False):
    o = b.outward()
    tear = np.array(b.tpl.meta["tear"] + (1.0,)) if b.tpl.meta.get("tear") else None
    if tear is None:
        p = b.M @ np.array([0.0, -0.1, 0.0, 1.0])
    else:
        p = b.M @ tear
    tpl = T["ST"]
    s = rnd.uniform(0.9, 1.3) * (1.6 if big else 1.0)
    M = m_trans(p[:3] + np.array([0.0, 0.0, -0.01])) @ m_rot("Z", rot2(o)) @ m_scale(s, s, s * 1.1)
    it = item_of(tpl, M, occ=False, kind="sand")
    offs = -tpl.V[:, 1] * s
    conform(it.V, offs, o, bvh, gap=0.002)
    return it, p[:3]


def trickle_item(T, b, bvh, rnd, start):
    o = b.outward()
    tpl = T["TR"]
    drop = start[2] - Z0 - 0.04
    if drop < 0.15:
        return None
    w = rnd.uniform(0.7, 1.1)
    M = m_trans((start[0], start[1], start[2] - 0.03)) @ m_rot("Z", rot2(o)) @ m_scale(w, 1.0, drop)
    Vl = tpl.V.copy()
    for r in range(len(Vl) // 3):
        Vl[3 * r:3 * r + 3, 0] *= rnd.choice((0.0, 0.0, 0.45, 0.8, 1.0))
    it = Item(Vl @ M[:3, :3].T + M[:3, 3], tpl.F.copy(), tpl.UV.copy(), occ=False, kind="sand")
    offs = -tpl.V[:, 1]
    conform(it.V, offs, o, bvh, gap=0.0025)
    return it


def pile_item(T, x, y, rx, ry, h, rnd, yaw=0.0):
    tpl = T["PL"]
    M = m_trans((x, y, Z0)) @ m_rot("Z", yaw) @ m_scale(rx / 0.5, ry / 0.5, h / 0.22) @ m_trans((0.0, 0.0, 0.0))
    return item_of(tpl, M, occ=False, kind="sand")


def flap_item(T, b, bvh, rnd):
    """A torn flap of burlap hanging from the lip of a tear, its bottom curling away from the bag."""
    o = b.outward()
    tpl = T[rnd.choice(("FL0", "FL1"))]
    tear = b.tpl.meta.get("tear") or (0.0, -0.12, 0.0)
    p = (b.M @ np.array(tuple(tear) + (1.0,)))[:3] + np.array([o[0], o[1], 0.0]) * 0.012 + np.array([0, 0, 0.025])
    M = (m_trans(p) @ m_rot("Z", rot2(o) + rnd.uniform(-20, 20)) @ m_rot("X", -rnd.uniform(4.0, 14.0))
         @ m_rot("Y", rnd.uniform(-15, 15)) @ m_scale(*(rnd.uniform(0.85, 1.15),) * 3))
    it = item_of(tpl, M, occ=False, kind="flap")
    offs = -tpl.V[:, 1]
    conform(it.V, offs - offs.min(), o, bvh, gap=0.004, only_out=True)
    return it


def drape_item(T, name, x0, y0, yaw, bvh, edge, z_guess, rnd, radius=0.05):
    """An empty bag laid over the top, the part past `edge` (signed y of the face line; its sign is the side)
    folded down over the face and following it."""
    tpl = T[name]
    L = tpl.V - tpl.center
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    X = x0 + L[:, 0] * c - L[:, 1] * s
    Y = y0 + L[:, 0] * s + L[:, 1] * c
    t = L[:, 2]
    side = 1.0 if edge > 0 else -1.0
    hit = bvh.ray_cast(Vector((x0, edge - side * 0.06, z_guess + 1.0)), Vector((0, 0, -1)), 3.0)
    z_edge = (hit[0].z if hit[0] is not None else z_guess) + 0.004
    out = np.zeros((len(L), 3))
    for i in range(len(L)):
        d = (Y[i] - edge) * side
        if d <= 0:
            h = bvh.ray_cast(Vector((X[i], Y[i], z_guess + 1.0)), Vector((0, 0, -1)), 3.0)
            zm = (h[0].z if h[0] is not None else z_edge - 0.004) + 0.006
            out[i] = (X[i], Y[i], zm + t[i])
        else:
            phi = min(d / radius, math.pi / 2)
            beyond = max(0.0, d - radius * math.pi / 2)
            ym = edge + side * radius * math.sin(phi)
            zm = z_edge - radius * (1 - math.cos(phi)) - beyond
            h = bvh.ray_cast(Vector((X[i], edge + side * 0.6, zm)), Vector((0, -side, 0)), 1.2)
            if h[0] is not None:
                ym = max(ym * side, (h[0].y + side * 0.007) * side) * side
            n = (0.0, side * math.sin(phi), math.cos(phi))
            out[i] = (X[i] + n[0] * t[i], ym + n[1] * t[i], zm + n[2] * t[i])
    return Item(out, tpl.F.copy(), tpl.UV.copy(), occ=False, kind="drape")


# ---------------------------------------------------------------- building one mesh

def finish_mesh(name, items, material, z_max):
    Vs, Fs, UVs, off = [], [], [], 0
    for it in items:
        if len(it.F) == 0:
            continue
        Vs.append(it.V)
        Fs.append(it.F + off)
        UVs.append(it.UV)
        off += len(it.V)
    V = np.concatenate(Vs)
    F = np.concatenate(Fs)
    UV = np.concatenate(UVs)
    V[:, 2] = np.clip(V[:, 2], Z0, z_max)
    V[:, 0] = np.clip(V[:, 0], -0.56, 0.56)
    V[:, 1] = np.clip(V[:, 1], -0.5, 0.5)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", UV.reshape(-1).astype(np.float32))
    me.shade_smooth()
    me.materials.append(material)
    obj = tk.link(bpy.data.objects.new(name, me))
    return obj


def build_variant(T, piece, stage, level, material):
    spec = PIECES[piece]
    n_courses = spec["full"] if stage == "Full" else spec["half"]
    bags = spec["layout"](n_courses)
    seed = sum(ord(c) for c in piece + stage) * 31 + level * 7
    rnd = random.Random(seed)
    plan = plan_damage(bags, piece, stage, level, rnd)
    items = []
    for b in bags:
        if b.removed:
            continue
        realize(b, T, rnd)
        items.append(item_of(b.tpl, b.M, kind="bag", seam=b.kind.startswith("half")))
        items[-1].role = b.role
    # bags from the gap lying slumped in it
    notch_floor = min((x.k for x in plan["notch"]), default=None)
    for j, b in enumerate(plan["fallen"]):
        b2 = Bag("full", b.axis, b.lat, b.w, b.s0, b.s1, b.k, b.role, b.side)
        b2.k = notch_floor + (1 if j == 2 else 0)
        box = notch_region(piece, b2.k, n_courses, stage)
        if box is not None:
            c = (box[0] + box[1]) / 2 if b.axis == "X" else (box[2] + box[3]) / 2
            half = (b.s1 - b.s0) / 2
            b2.s0, b2.s1 = c - half + rnd.uniform(-0.06, 0.06), c + half
        b2.dz = -0.02
        b2.tilt = rnd.uniform(16.0, 30.0)
        b2.shift = rnd.uniform(0.0, 0.03)
        b2.yaw = rnd.uniform(-14.0, 14.0)
        b2.roll = rnd.uniform(-10.0, 10.0)
        realize(b2, T, rnd)
        items.append(item_of(b2.tpl, b2.M, kind="bag"))
    apply_sags(items, plan["sags"])
    bvh = bvh_of(items)
    extras = []
    for b in plan["trickles"]:
        if b.removed or not b.tpl.meta.get("tear"):
            continue
        p = (b.M @ np.array(tuple(b.tpl.meta["tear"]) + (1.0,)))[:3]
        tr = trickle_item(T, b, bvh, rnd, p)
        if tr is not None:
            extras.append(tr)
    for b in plan["flaps"]:
        if not b.removed:
            extras.append(flap_item(T, b, bvh, rnd))
    D0 = course_depth("Low" if piece == "Low" else "Wall", 0)
    for pl in [p for p in plan["piles"] if p]:
        side = pl["side"]
        ry = 0.5 - (D0 / 2 - 0.08)
        if piece == "Corner":
            # along the two outside faces (-Y, and -X for the 'back' ones)
            s = min(0.5 - pl["rx"] * 0.8, max(-0.1, pl["x"] + 0.15))
            if side < 0:
                extras.append(pile_item(T, s, -(0.5 - ry), pl["rx"], ry, pl["h"], rnd, yaw=rnd.uniform(-6, 6)))
            else:
                extras.append(pile_item(T, -(0.5 - ry), s, ry, pl["rx"], pl["h"], rnd, yaw=rnd.uniform(-6, 6)))
            continue
        y = side * (0.5 - ry)
        x = pl["x"]
        if piece == "End":
            x = max(x, end_pos(0) + pl["rx"] * 0.6)
        x = max(-0.54 + pl["rx"], min(0.54 - pl["rx"], x))
        extras.append(pile_item(T, x, y, pl["rx"], ry, pl["h"], rnd, yaw=rnd.uniform(-6, 6)))
    cores = core_for(piece, stage, n_courses, bags, plan["sags"])
    if stage == "Half":
        bvh = bvh_of(items + cores)
        z_top = Z0 + n_courses * P
        Dt = course_depth("Low" if piece == "Low" else "Wall", n_courses - 1)
        edge = -(Dt / 2 - 0.05)
        if piece == "Corner":
            drapes = [("EU0", -0.05, -0.1, 84.0, edge), ("EU0", 0.22, 0.02, 8.0, Dt / 2 - 0.05)]
        elif piece == "End":
            drapes = [("EU0", 0.14, -0.1, 80.0, edge), ("EU0", 0.08, 0.05, 4.0, Dt / 2 - 0.05)]
        else:
            drapes = [("EU0", -0.18, -0.12, 82.0, edge), ("EU0", 0.2, 0.0, 6.0, Dt / 2 - 0.05)]
        for name, x0, y0, yaw, e in drapes:
            extras.append(drape_item(T, name, x0, y0, yaw + rnd.uniform(-5, 5), bvh, e, z_top, rnd))
        # one still folded, lying on top
        extras.append(drape_item(T, "EB0", 0.05 if piece != "End" else 0.15, 0.12, rnd.uniform(-20, 20), bvh, 0.9,
                                 z_top, rnd))
    allitems = items + cores + extras
    for it in extras:
        it.cull = True
    before, after = cull(allitems)
    z_max = Z0 + n_courses * P + (0.04 if stage == "Half" else 0.0)
    name = "%s%s_DMG%d" % (piece, stage, level)
    obj = finish_mesh(name, allitems, material, z_max)
    vis = len([b for b in bags if b.role in ("face", "seam", "header")])
    by = {}
    for it in allitems:
        key = getattr(it, "role", it.kind)
        by[key] = by.get(key, 0) + len(it.F)
    log("  by role:", by)
    log("%s: %d bags (%d visible), %d removed, tris %d -> %d" % (name, len(bags), vis,
                                                                 len([b for b in bags if b.removed]), before, after))
    return obj


def build_empty(T, material):
    """Folded empty bags stacked neatly, an opened one over the top of the stack, two stakes on the wall line with
    twine between them."""
    rnd = random.Random(909)
    items = []
    for i in range(8):
        tpl = T["EB0" if i % 2 == 0 else "EB1"]
        M = (m_trans((0.06 + rnd.uniform(-0.012, 0.012), 0.13 + rnd.uniform(-0.012, 0.012),
                      Z0 + tpl.size[2] / 2 + i * 0.0215)) @ m_rot("Z", rnd.uniform(-7, 7) + (180 if i % 3 == 0 else 0))
             @ m_rot("X", rnd.uniform(-1.0, 1.0)) @ m_trans(-tpl.center))
        items.append(item_of(tpl, M, kind="bag"))
    bvh = bvh_of(items)
    top = Z0 + 8 * 0.0215 + 0.012
    items.append(drape_item(T, "EU0", 0.04, -0.06, 88.0, bvh, -0.05, top, rnd, radius=0.03))
    for it in items[-1:]:
        it.occ = False
    stake = T["SK"]
    pts = []
    for sx in (-0.42, 0.42):
        M = m_trans((sx, -0.36, Z0)) @ m_rot("Z", rnd.uniform(0, 90)) @ m_rot("X", rnd.uniform(-3, 3)) \
            @ m_trans((-stake.center[0], -stake.center[1], -stake.lo[2]))
        items.append(item_of(stake, M, occ=False, kind="stake"))
        pts.append((sx, -0.36))
        wrap = T["TWW"]
        Mw = m_trans((sx, -0.36, Z0 + 0.24)) @ m_rot("Z", rnd.uniform(0, 360)) @ m_trans(-wrap.center)
        items.append(item_of(wrap, Mw, occ=False, kind="twine"))
    tw = T["TW"]
    a, b = np.array(pts[0] + (Z0 + 0.245,)), np.array(pts[1] + (Z0 + 0.245,))
    V = tw.V.copy()
    t = (V[:, 0] - tw.lo[0]) / tw.size[0]
    span = b - a
    base = a[None, :] + t[:, None] * span[None, :]
    sag = 0.018 * 4 * t * (1 - t)
    V = base + np.stack([np.zeros_like(t), V[:, 1], V[:, 2] - sag], axis=1)
    items.append(Item(V, tw.F.copy(), tw.UV.copy(), occ=False, kind="twine"))
    # the loose end hanging from the right stake
    tail = tw.V.copy()
    t = (tail[:, 0] - tw.lo[0]) / tw.size[0]
    V = np.stack([0.42 + 0.03 * t + tail[:, 1], -0.34 - 0.02 * t, Z0 + 0.245 - 0.2 * t + tail[:, 2]], axis=1)
    V[:, 2] = np.maximum(V[:, 2], Z0 + 0.003)
    items.append(Item(V, tw.F.copy(), tw.UV.copy(), occ=False, kind="twine"))
    before, after = cull(items)
    obj = finish_mesh("Empty_DMG0", items, material, 0.5)
    log("Empty: tris %d -> %d" % (before, after))
    return obj


# ---------------------------------------------------------------- reports, export

def stats(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0), len(me.polygons)


def fx_point(piece, stage):
    n = PIECES[piece]["full" if stage == "Full" else "half"]
    zm = Z0 + n * P / 2.0
    D = depth_at("Low" if piece == "Low" else "Wall", zm)
    return (0.0, -D / 2.0 - 0.02, zm)


def export_piece(fname, meshes, fx):
    """Exports meshes renamed DMG0.. (and an FX empty) to one FBX, then restores the names."""
    saved = []
    objs = []
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
    floor.data.transform(Matrix.Translation((0.5, 0.5, 0.0)) @ Matrix.Scale(4.0, 4))
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


def compare_vanilla(wall, ref_path, out_path):
    """Our wall under the light and camera the vanilla reference was rendered with (Unity: sun 1.4 at 40/-30,
    trilight ambient, floor 0.3/0.29/0.27), next to the reference's first view, plus the mean bag colors."""
    scene = bpy.context.scene
    for o in ALL:
        o.hide_render = o is not wall
    hidden = [o for o in scene.objects if o.type == "LIGHT" or o.name in ("Floor", "ScaleFigure", "ScaleHead")]
    for o in hidden:
        o.hide_render = True
    old_world = scene.world
    scene.world = bpy.data.worlds.new("Cmp")
    sun, fl = unity_light()
    cam = tk.camera("CmpCam", (1.8, -4.6, 2.2), (0.0, 0.4, 0.6), lens=50)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle_y = math.radians(34.0)
    ours = os.path.join(PREVIEWS, "_cmp_ours.png")
    tk.render(cam, ours, res=(1300, 1000), samples=96)
    fl.hide_render = True
    mask_path = os.path.join(PREVIEWS, "_cmp_mask.png")
    tk.render(cam, mask_path, res=(1300, 1000), samples=8, transparent=True)
    a = image_array(ours)
    m = image_array(mask_path)[..., 3] > 0.5
    ref = image_array(ref_path)
    left = ref[:, :1300]
    both = np.concatenate([left[..., :3], a[..., :3]], axis=1)
    save_rgb(both, out_path)
    px = a[..., :3][m]
    floor_px = a[..., :3][~m]
    log("compare: ours bag mean sRGB", (px.mean(axis=0) * 255).round(1), "p25/p75 luma",
        np.percentile(px @ np.array([0.2126, 0.7152, 0.0722]), [25, 75]).round(3) * 255,
        "| floor", (np.median(floor_px[len(floor_px) // 2:], axis=0) * 255).round(1),
        "| vanilla ref bags mean ~ (114, 97, 82), floor (110, 104, 98)")
    os.remove(ours)
    os.remove(mask_path)
    bpy.data.objects.remove(sun)
    bpy.data.objects.remove(fl)
    scene.world = old_world
    for o in hidden:
        o.hide_render = False


# ================================================================ main

tk.reset_scene()
MATS = build_kit()
layout_kit()
if MODE == "kit":
    kit_preview()
    log("kit preview done")
    sys.exit(0)

bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
kit, PATHS = bake_kit()
T = extract_templates(kit)
cu = T["CORE"].UV.reshape(-1, 2)
CORE_UV = (cu[:, 0].min(), cu[:, 1].min(), cu[:, 0].max(), cu[:, 1].max())
bpy.data.objects.remove(kit)
MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
log("baked", PATHS)

if MODE.startswith("holes"):
    # debug: one variant, back faces red, the core green (holes:<piece>:<stage>:<level>)
    pc, sg, lv = MODE.split(":")[1:4]
    obj = build_variant(T, pc, sg, int(lv), MATERIAL)
    dbg, g = tk.new_material("Dbg")
    geo = g.node("ShaderNodeNewGeometry")
    col = g.mix(tk._sock(geo.outputs, "Backfacing"), (0.5, 0.45, 0.4), (1.0, 0.0, 0.0))
    tk.finish(dbg, g, col, 0.0, 0.8)
    if len(MODE.split(":")) < 5:
        obj.data.materials[0] = dbg
    stage()
    figure_at(3.0, 3.0)
    for name, loc in (("front", (0.6, -2.6, 0.6)), ("back", (-0.6, 2.6, 0.6)), ("side", (-2.6, -0.8, 0.6)),
                      ("top", (-0.9, -1.4, 3.4))):
        tk.render(tk.camera("Dbg" + name, loc, (0.0, 0.0, 0.0), lens=40),
                  os.path.join(PREVIEWS, "dbg_holes_%s.png" % name), res=(900, 800), samples=32)
    sys.exit(0)

BUILT = {}
for piece in PIECES:
    for stg in ("Half", "Full"):
        BUILT[(piece, stg)] = [build_variant(T, piece, stg, lvl, MATERIAL) for lvl in range(3)]
        ALL.extend(BUILT[(piece, stg)])
EMPTY = build_empty(T, MATERIAL)
ALL.append(EMPTY)

REPORT = []
for piece in PIECES:
    export_piece("Sandbag%sEmpty.fbx" % piece, [EMPTY], None)
    lo, hi, tris = stats(EMPTY)
    REPORT.append("Sandbag%sEmpty.fbx: DMG0 tris %d bounds %s..%s" % (piece, tris, lo.round(3), hi.round(3)))
    for stg in ("Half", "Full"):
        meshes = BUILT[(piece, stg)]
        fx = fx_point(piece, stg)
        export_piece("Sandbag%s%s.fbx" % (piece, stg), meshes, fx)
        for i, m in enumerate(meshes):
            lo, hi, tris = stats(m)
            REPORT.append("Sandbag%s%s.fbx: DMG%d tris %d bounds %s..%s" % (piece, stg, i, tris, lo.round(3),
                                                                           hi.round(3)))
        REPORT.append("Sandbag%s%s.fbx: FX at %s" % (piece, stg, tuple(round(c, 3) for c in fx)))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
stage()
for piece in PIECES:
    full, half = BUILT[(piece, "Full")], BUILT[(piece, "Half")]
    ents = [(full[0], (-3.0, 0.0), 0), (full[1], (-1.5, 0.0), 0), (full[2], (0.0, 0.0), 0), (half[0], (1.5, 0.0), 0),
            (EMPTY, (3.0, 0.0), 0)]
    figure_at(4.3, 0.4)
    tk_cam = tk.camera("St_" + piece, (1.6, -9.0, 2.7), (0.0, 0.0, 0.35), lens=38)
    lineup(ents, tk_cam, os.path.join(PREVIEWS, "sandbag_%s_stages.png" % piece.lower()))
    tk_cam = tk.camera("Bk_" + piece, (-1.6, 9.0, 2.7), (0.0, 0.0, 0.35), lens=38)
    lineup(ents, tk_cam, os.path.join(PREVIEWS, "sandbag_%s_stages_back.png" % piece.lower()))
    ents = [(half[0], (-1.4, 0.0), 0), (half[1], (0.0, 0.0), 0), (half[2], (1.4, 0.0), 0)]
    tk_cam = tk.camera("Hf_" + piece, (1.0, -5.2, 1.6), (0.0, 0.0, -0.05), lens=40)
    lineup(ents, tk_cam, os.path.join(PREVIEWS, "sandbag_%s_half.png" % piece.lower()), res=(1600, 800))

W = BUILT[("Wall", "Full")]
C = BUILT[("Corner", "Full")]
E = BUILT[("End", "Full")]
row = [(E[0], (-1.0, 0.0), 0), (W[0], (0.0, 0.0), 0), (W[0], (1.0, 0.0), 180), (W[0], (2.0, 0.0), 0),
       (C[0], (3.0, 0.0), 90), (W[0], (3.0, 1.0), 90)]
figure_at(-2.0, -1.0)
lineup(row, tk.camera("RowF", (-1.2, -6.8, 3.2), (1.3, 0.2, 0.25), lens=35), os.path.join(PREVIEWS, "sandbag_row.png"))
lineup(row, tk.camera("RowB", (4.6, 6.2, 3.4), (1.0, 0.3, 0.25), lens=35), os.path.join(PREVIEWS, "sandbag_row_back.png"))
lineup(row, tk.camera("RowT", (1.0, -3.2, 4.2), (1.0, 0.2, 1.0), lens=30), os.path.join(PREVIEWS, "sandbag_row_top.png"))
rowd = [(E[2], (-1.0, 0.0), 0), (W[1], (0.0, 0.0), 0), (W[2], (1.0, 0.0), 0), (W[0], (2.0, 0.0), 0),
        (C[1], (3.0, 0.0), 90)]
lineup(rowd, tk.camera("RowD", (-1.2, -6.8, 3.2), (1.3, 0.2, 0.25), lens=35),
       os.path.join(PREVIEWS, "sandbag_row_damaged.png"))
figure_at(6.0, 6.0)
lineup([(W[0], (0.0, 0.0), 0)], tk.camera("Close", (0.9, -1.9, 1.0), (0.0, -0.3, 0.55), lens=40),
       os.path.join(PREVIEWS, "sandbag_wall_close.png"), res=(1200, 1000))
lineup([(W[2], (0.0, 0.0), 0)], tk.camera("Close2", (0.9, -2.2, 1.6), (0.0, -0.2, 0.6), lens=40),
       os.path.join(PREVIEWS, "sandbag_wall_dmg2_close.png"), res=(1200, 1000))
lineup([(C[0], (-1.3, 0.0), 0), (C[1], (0.0, 0.0), 0), (C[2], (1.3, 0.0), 0)],
       tk.camera("CornerClose", (-2.4, -3.9, 2.0), (0.0, 0.0, 0.45), lens=36),
       os.path.join(PREVIEWS, "sandbag_corner_close.png"), res=(1600, 1000))
lineup([(E[0], (-1.3, 0.0), 0), (E[1], (0.0, 0.0), 0), (E[2], (1.3, 0.0), 0)],
       tk.camera("EndClose", (-3.6, -3.6, 2.0), (0.0, 0.0, 0.45), lens=36),
       os.path.join(PREVIEWS, "sandbag_end_close.png"), res=(1600, 1000))

figure_at(1.0, 0.7)
lineup([(EMPTY, (0.0, 0.0), 0)], tk.camera("EmptyClose", (0.9, -1.5, 0.45), (0.0, -0.05, -0.38), lens=40),
       os.path.join(PREVIEWS, "sandbag_empty_close.png"), res=(1200, 900))

REF = os.path.join(os.path.dirname(PREVIEWS), "ref-sandbag_straight_01prefab.png")
if os.path.exists(REF):
    compare_vanilla(W[0], REF, os.path.join(PREVIEWS, "sandbag_vs_vanilla.png"))

# ---------------------------------------------------------------- icon
for o in ALL:
    o.hide_render = o is not W[0]
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not W[0]}
tk.icon(tk.camera("Icon", (2.3, -3.6, 2.5), (0.0, 0.0, 0.42), lens=58), ICON, hide=hide, target=(0.0, 0.0, 0.5))
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
            parts.append("%s mesh tris %d mat %s z %.3f..%.3f x %.3f..%.3f y %.3f..%.3f parent %s" % (
                o.name, tris, [m.name for m in o.data.materials], co[:, 2].min(), co[:, 2].max(), co[:, 0].min(),
                co[:, 0].max(), co[:, 1].min(), co[:, 1].max(), o.parent.name if o.parent else None))
        else:
            parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation),
                                                    o.parent.name if o.parent else None))
    log("reimport", fname, "|", " || ".join(parts))
log("done")
