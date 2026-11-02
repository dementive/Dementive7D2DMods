"""Log Palisade (Fortifications Expanded): the palisade family's block models, all sharing one baked material,
`Palisade` (Palisade_Albedo.png, Palisade_Normal.png, Palisade_RMOM.png, 2048).

    PalisadeSection.fbx, PalisadeSectionBanded.fbx, PalisadeCorner.fbx, PalisadeCornerBanded.fbx
        three meshes at the same origin, DMG0 (intact), DMG1 (worn) and DMG2 (breaking), plus an empty FX in the
        middle of the front face at mid-height
    PalisadeStumps.fbx
        one mesh, DMG0: what is left when a section breaks
    PalisadeGate.fbx
        Frame (the two posts, their pintles and earth), LeftLeaf and RightLeaf; each leaf's origin is on its hinge axis
        and the leaves swing out toward -Y

Section: four sharpened logs (0.25-0.27 m thick, axe-faceted points 2.4-2.5 m up, bark in patches, mud splashed at
the foot) standing on the wall line (y = 0) in a low earth berm, two rails across their back (+Y) lashed with rope,
wired and spiked. Banded: rusty iron straps bolted across the front at the rail heights, through-bolted to straps
over the rails. Corner: a thick post at the origin with a log and rails running toward +X and toward +Y.

A kit of logs, posts, rails, iron parts and flat swatches (fresh splintered wood, end grain, rope, wire, strap iron,
mud) is built and baked once to the shared atlas. Every piece is assembled from copies of the kit parts (moved,
scaled, cut and capped, keeping their UVs); ropes, wire, straps, splinters and the berm are generated along paths
with their UVs laid on the swatches.

    blender -b --factory-startup --python palisade.py -- <unity asset folder> <preview folder> <icon file> [kit]
"""
import math
import os
import random
import sys
import time

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
MAT_NAME = "Palisade"
SHARP = 40.0  # the same sharp-edge angle on the kit and on the pieces, so the baked normals fit
ROPE_R = 0.0105
WIRE_R = 0.0022
STRAP_W, STRAP_T = 0.045, 0.008
T0 = time.time()
RND = random.Random(4242)


def log(*a):
    print("[palisade %5.0fs]" % (time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- small helpers

def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def m_t(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def m_r(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, axis))


def m_s(sx, sy, sz):
    return np.diag([sx, sy, sz, 1.0])


def m_about(M, pivot):
    p = np.asarray(pivot, float)
    return m_t(*p) @ M @ m_t(*(-p))


def m_align(direction):
    """Rotation taking +Z to `direction`."""
    d = Vector(tuple(float(c) for c in direction)).normalized()
    return np.array(Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4())


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def pnoise(x, y, z, seed=0.0):
    return noise.noise(Vector((x + seed * 7.31, y - seed * 3.17, z + seed * 1.93)))


# ---------------------------------------------------------------- 2D geometry

def hull2d(P):
    """Convex hull, counter-clockwise, starting at the leftmost point (the lower chain comes first)."""
    P = np.unique(np.round(np.asarray(P, float), 6), axis=0)
    if len(P) < 3:
        return P
    P = P[np.lexsort((P[:, 1], P[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(tuple(p))
    for p in P[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(tuple(p))
    return np.array(lower[:-1] + upper[:-1])


def resample(P, step=None, n=None, closed=False):
    P = np.asarray(P, float)
    Q = np.vstack([P, P[:1]]) if closed else P
    d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    L = d[-1]
    if n is None:
        n = max(2, int(round(L / step)) + (0 if closed else 1))
    t = np.linspace(0.0, L, n, endpoint=not closed)
    return np.stack([np.interp(t, d, Q[:, k]) for k in range(Q.shape[1])], axis=1)


def offset_hull(Q, off, n):
    ang = np.linspace(0, 2 * math.pi, 14, endpoint=False)
    ring = np.c_[np.cos(ang), np.sin(ang)] * off
    H = hull2d((Q[:, None, :] + ring[None]).reshape(-1, 2))
    return resample(H, n=n, closed=True)


def signed_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def circle_pts(cx, cy, r, n=24):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


# ================================================================ the kit

FT_SIDE, FT_FACET, FT_FRESH, FT_END, FT_GOUGE, FT_STUB, FT_BOTTOM = 0, 1, 2, 3, 4, 5, 9
KIT, META, CONTEXT = [], {}, []


def set_attr(me, name, domain, kind, values):
    a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
    dt = np.int32 if kind == "INT" else np.float32
    a.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", np.asarray(values, dt).ravel())


def bm_to_obj(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = tk.link(bpy.data.objects.new(name, me))
    obj.data.materials.append(mat)
    return obj


def kit_part(name, obj, kind, R=0.1, mud=0.0, bark=0.4, claws=(), context=False, **meta):
    """Registers a built object as a kit part and writes the attributes its material reads: lco (local position),
    luv (grain coordinates in meters: around/across, along), ks (axe facet, fresh wood, end grain), kp (mud, bark,
    seed), kc0-kc2 (claw mark sets: angle, height, on) and kpart (the part index)."""
    me = obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    set_attr(me, "lco", "POINT", "FLOAT_VECTOR", co)
    ft = np.zeros(len(me.polygons), np.int32)
    if me.attributes.get("ftype") is not None:
        me.attributes["ftype"].data.foreach_get("value", ft)
    rnd = random.Random(len(KIT) * 31 + 7)
    uoff, voff = rnd.uniform(0, 5), rnd.uniform(0, 5)
    loop_v = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loop_v)
    luv = np.zeros((len(me.loops), 3), np.float32)
    ks = np.zeros((len(me.loops), 3), np.float32)
    lo = co.min(axis=0)
    for p in me.polygons:
        li = np.arange(p.loop_start, p.loop_start + p.loop_total)
        P = co[loop_v[li]]
        t = ft[p.index]
        if kind == "flat":
            uv = P[:, :2] - lo[:2]
        elif kind == "cyl" and t in (FT_SIDE, FT_FRESH, FT_STUB):
            ang = np.arctan2(P[:, 1], P[:, 0])
            if ang.max() - ang.min() > math.pi:
                ang = np.where(ang < 0, ang + 2 * math.pi, ang)
            uv = np.c_[ang * R + uoff, P[:, 2] + voff]
        else:
            n = p.normal
            if abs(n.z) > 0.75:
                uv = np.c_[P[:, 0] + uoff, P[:, 1] + voff]
            else:
                tv = unit((-n.y, n.x, 0.0))
                uv = np.c_[P @ tv + uoff, P[:, 2] + voff]
        luv[li, :2] = uv
        if t == FT_FACET:
            ks[li] = (1.0, 0.0, 0.0)
        elif t in (FT_FRESH, FT_GOUGE):
            ks[li] = (0.0, 1.0, 0.0)
        elif t == FT_END:
            ks[li] = (0.0, 0.0, 1.0)
    set_attr(me, "luv", "CORNER", "FLOAT_VECTOR", luv)
    set_attr(me, "ks", "CORNER", "FLOAT_VECTOR", ks)
    set_attr(me, "kp", "POINT", "FLOAT_VECTOR", np.tile([mud, bark, rnd.uniform(0.0, 9.0)], (nv, 1)))
    for k in range(3):
        c = claws[k] if k < len(claws) else (0.0, -9.0, 0.0)
        set_attr(me, "kc%d" % k, "POINT", "FLOAT_VECTOR", np.tile(c, (nv, 1)))
    set_attr(me, "kpart", "FACE", "INT", np.full(len(me.polygons), len(KIT)))
    tk.smooth(obj, SHARP)
    META[name] = dict(index=len(KIT), kind=kind, R=R, context=context, **meta)
    KIT.append(obj)
    return obj


def cut_fill(bm, ftl, co, n, ft):
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co,
                                 plane_no=n, clear_outer=True)
    edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
    if edges:
        for f in bmesh.ops.holes_fill(bm, edges=edges, sides=0)["faces"]:
            f[ftl] = ft


def log_bm(R, length, seed, segs=14, bow=0.016, taper=0.022, facets=6, beta=(14.0, 19.0), crack=None, lump=0.026,
           chops=1):
    """A sharpened log standing on z = 0, axis along Z: lumpy, slightly bowed and tapered, with a butt flare, an
    optional split down its side (crack: th, z0, z1, depth, open), and a point cut by axe facets."""
    rnd = random.Random(seed)
    # bowed toward local +-Y (in or out of the wall when the log stands unturned), never into its neighbours
    psi = math.pi / 2 + rnd.uniform(-0.25, 0.25) + (math.pi if rnd.random() < 0.5 else 0.0)
    ph = rnd.uniform(0, 2 * math.pi)
    a2, a3 = rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)
    sd = seed * 1.37

    def center(z):
        s = math.sin(math.pi * min(max(z / length, 0.0), 1.0))
        return (bow * s * math.cos(psi) + 0.0015 * math.sin(3.1 * z + a2),
                bow * s * math.sin(psi) + 0.0015 * math.cos(2.3 * z + a3))

    def rad(th, z):
        base = R * (1.0 - taper * z / length) * (1.0 + 0.05 * max(0.0, 1.0 - z / 0.3) ** 2)
        n1 = noise.noise(Vector((math.cos(th) * 0.6 + sd, math.sin(th) * 0.6, z * 1.3)))
        n2 = noise.noise(Vector((math.cos(th) * 1.5, math.sin(th) * 1.5 - sd, z * 3.7)))
        return base * (1.0 + lump * n1 + 0.01 * n2 + 0.012 * math.sin(2 * th + a2))

    pl = R / math.tan(math.radians(0.5 * (beta[0] + beta[1])))
    z_pt = length - pl
    zs = [0.0, 0.08, 0.22]
    z = 0.22
    while z + 0.42 < z_pt - 0.1:
        z += 0.42
        zs.append(z)
    if crack:
        zz = crack["z0"]
        while zz <= crack["z1"]:
            zs.append(zz)
            zz += 0.2
        zs.append(crack["z1"])
    zs += [z_pt, z_pt + 0.5 * pl, length + 0.08]
    clean = []
    for v in sorted(zs):
        if not clean or v - clean[-1] > 0.06:
            clean.append(v)
    zs = clean

    base_angles = [ph + 2 * math.pi * j / segs for j in range(segs)]
    cols = [("b", a) for a in base_angles]
    if crack:
        j = min(range(segs), key=lambda k: abs(math.remainder(base_angles[k] - crack["th"], 2 * math.pi)))
        thc = base_angles[j]
        cols = cols[:j] + [("L", thc), ("C", thc), ("R", thc)] + cols[j + 1:]

    def cw(z):
        if not crack or z < crack["z0"] or z > crack["z1"]:
            return 0.0
        return math.sin(math.pi * (z - crack["z0"]) / (crack["z1"] - crack["z0"])) ** 0.6

    bm = bmesh.new()
    ftl = bm.faces.layers.int.new("ftype")
    rings = []
    for z in zs:
        cx, cy = center(z)
        w = cw(z)
        ring = []
        for kind, a in cols:
            if kind == "L":
                a -= (0.004 + crack["open"] * w) / R
            elif kind == "R":
                a += (0.004 + crack["open"] * w) / R
            r = rad(a, z)
            if kind == "C":
                r -= crack["depth"] * w
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
        rings.append(ring)
    nc = len(cols)
    for k in range(len(zs) - 1):
        band = cw(zs[k]) > 0.02 or cw(zs[k + 1]) > 0.02
        for c in range(nc):
            c1 = (c + 1) % nc
            f = bm.faces.new((rings[k][c], rings[k][c1], rings[k + 1][c1], rings[k + 1][c]))
            pair = cols[c][0] + cols[c1][0]
            f[ftl] = FT_FRESH if band and pair in ("LC", "CR") else FT_SIDE
    bm.faces.new(rings[-1])[ftl] = FT_SIDE
    bm.faces.new(list(reversed(rings[0])))[ftl] = FT_BOTTOM
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    cx, cy = center(length)
    off = rnd.uniform(0.015, 0.045) * R / 0.13
    oa = rnd.uniform(0, 2 * math.pi)
    tip = Vector((cx + off * math.cos(oa), cy + off * math.sin(oa), length))
    phi0 = rnd.uniform(0, 2 * math.pi)
    planes = []
    for i in range(facets):
        phi = phi0 + 2 * math.pi * i / facets + rnd.uniform(-0.35, 0.35)
        # facets on the side the tip leans toward are steeper and shorter, the far ones long and shallow
        lean = math.cos(phi - oa)
        b = math.radians(min(28.0, max(13.5, rnd.uniform(*beta) + 4.0 * lean)))
        n = Vector((math.cos(phi) * math.cos(b), math.sin(phi) * math.cos(b), math.sin(b)))
        planes.append((tip - n * rnd.uniform(0.0, 0.02), n))
    for k in range(chops):
        phi = rnd.uniform(0, 2 * math.pi)
        b = math.radians(rnd.uniform(24.0, 38.0))
        zc = length - pl * rnd.uniform(0.55, 0.8)
        ccx, ccy = center(zc)
        rq = R * (length - zc) / pl
        n = Vector((math.cos(phi) * math.cos(b), math.sin(phi) * math.cos(b), math.sin(b)))
        q = Vector((ccx + rq * math.cos(phi), ccy + rq * math.sin(phi), zc))
        planes.append((q - n * rnd.uniform(0.008, 0.014), n))
    for co, n in planes:
        cut_fill(bm, ftl, co, n, FT_FACET)
    return bm, dict(psi=psi, center=center, rad=rad, z_pt=z_pt, pl=pl, length=length, R=R)


def gouge_cutters(info, gouges):
    """Axe chops: wedges with a steep upper face and a shallow lower face meeting inside the wood."""
    out = []
    for th, z, w, d, rot in gouges:
        cx, cy = info["center"](z)
        r = info["rad"](th, z)
        er = Vector((math.cos(th), math.sin(th), 0.0))
        rm = Matrix.Rotation(math.radians(rot), 3, er)
        et = rm @ Vector((-math.sin(th), math.cos(th), 0.0))
        ez = rm @ Vector((0.0, 0.0, 1.0))
        apex = Vector((cx, cy, z)) + er * (r - d)
        up = (er * math.cos(math.radians(52)) + ez * math.sin(math.radians(52))).normalized()
        dn = (er * math.cos(math.radians(-14)) + ez * math.sin(math.radians(-14))).normalized()
        U, D = apex + up * 0.22, apex + dn * 0.22
        bm = bmesh.new()
        v = [bm.verts.new(p) for p in (apex - et * w / 2, U - et * w / 2, D - et * w / 2,
                                        apex + et * w / 2, U + et * w / 2, D + et * w / 2)]
        for f in ((0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (0, 2, 5, 3), (1, 4, 5, 2)):
            bm.faces.new([v[i] for i in f])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        n_up = et.cross(up).normalized()
        n_dn = dn.cross(et).normalized()
        out.append((bm, [(apex, n_up), (apex, n_dn)], et, w))
    return out


def add_stub(bm, ftl, info, rnd):
    """A limbed-off knot: a low swelling on the log's side, trimmed off at a slant (a separate closed shell)."""
    th = rnd.uniform(0, 2 * math.pi)
    zk = rnd.uniform(0.75, max(0.9, info["z_pt"] - 0.4))
    cx, cy = info["center"](zk)
    r0 = info["rad"](th, zk)
    er = Vector((math.cos(th), math.sin(th), 0.0))
    d = (er * math.cos(math.radians(30)) + Vector((0, 0, 1)) * math.sin(math.radians(30))).normalized()
    base = Vector((cx, cy, zk)) + er * (r0 - 0.03)
    rs = rnd.uniform(0.016, 0.024)
    e1 = d.cross(Vector((0, 0, 1))).normalized()
    e2 = d.cross(e1)
    n = 8
    rings = []
    for k, (f, out) in enumerate(((2.3, 0.0), (1.45, 0.034), (1.0, 0.048))):
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            jig = 1.0 + 0.15 * math.sin(3 * a + th * 5)
            ring.append(bm.verts.new(base + (e1 * math.cos(a) + e2 * math.sin(a)) * rs * f * jig
                                     + d * (out + (0.01 * math.cos(a) if k == 2 else 0.0))))
        rings.append(ring)
    for k in range(2):
        for j in range(n):
            j1 = (j + 1) % n
            bm.faces.new((rings[k][j], rings[k][j1], rings[k + 1][j1], rings[k + 1][j]))[ftl] = FT_STUB
    bm.faces.new(rings[2])[ftl] = FT_STUB
    bm.faces.new(list(reversed(rings[0])))[ftl] = FT_BOTTOM


def make_log(name, mat, R, length, seed, segs=12, facets=6, beta=(12.0, 21.0), crack=None, gouges=(), stubs=1,
             bow=0.008, chops=3):
    bm, info = log_bm(R, length, seed, segs=segs, bow=bow, facets=facets, beta=beta, crack=crack, chops=chops)
    obj = bm_to_obj(name, bm, mat)
    planes = []
    for k, (cbm, pl, et, w) in enumerate(gouge_cutters(info, gouges)):
        cutter = bm_to_obj(name + "Cut%d" % k, cbm, mat)
        mod = obj.modifiers.new("Gouge", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        try:
            mod.solver = "EXACT"
        except TypeError:
            mod.solver = "MANIFOLD"
        mod.object = cutter
        tk.apply_modifiers(obj)
        bpy.data.objects.remove(cutter)
        planes += [(p0, n, et, w) for p0, n in pl]
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ftl = bm.faces.layers.int.get("ftype") or bm.faces.layers.int.new("ftype")
    for f in bm.faces:
        f.material_index = 0
        if planes:
            c = f.calc_center_median()
            for p0, n, et, w in planes:
                if abs((c - p0).dot(n)) < 4e-4 and abs((c - p0).dot(et)) < w / 2 + 0.003:
                    f[ftl] = FT_GOUGE
    rnd = random.Random(seed + 99)
    for _ in range(stubs):
        add_stub(bm, ftl, info, rnd)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[ftl] == FT_BOTTOM], context="FACES")
    split = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0][ftl] != e.link_faces[1][ftl]]
    if split:
        bmesh.ops.split_edges(bm, edges=split)
    bm.to_mesh(obj.data)
    bm.free()
    return obj, info


def make_rail(name, mat, R, length, seed, segs=10, bow=0.01):
    """A pole along Z from 0 to length, its ends narrowed a little (rails of neighbouring blocks overlap there) and
    sawn square."""
    rnd = random.Random(seed)
    psi = rnd.uniform(0, 2 * math.pi)
    ph = rnd.uniform(0, 2 * math.pi)
    a2 = rnd.uniform(0, 6.3)
    sd = seed * 0.71
    n_mid = max(3, int(length / 0.24))
    zs = [0.0, 0.025] + list(np.linspace(0.025, length - 0.025, n_mid)[1:-1]) + [length - 0.025, length]
    bm = bmesh.new()
    ftl = bm.faces.layers.int.new("ftype")
    rings = []
    for z in zs:
        s = math.sin(math.pi * z / length)
        cx, cy = bow * s * math.cos(psi), bow * s * math.sin(psi)
        endf = 0.93 if (z < 0.02 or z > length - 0.02) else 1.0
        ring = []
        for j in range(segs):
            a = ph + 2 * math.pi * j / segs
            n1 = noise.noise(Vector((math.cos(a) * 0.6 + sd, math.sin(a) * 0.6, z * 1.6)))
            r = R * endf * (1.0 + 0.05 * n1 + 0.02 * math.sin(2 * a + a2))
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
        rings.append(ring)
    for k in range(len(zs) - 1):
        for c in range(segs):
            c1 = (c + 1) % segs
            bm.faces.new((rings[k][c], rings[k][c1], rings[k + 1][c1], rings[k + 1][c]))[ftl] = FT_SIDE
    bm.faces.new(rings[-1])[ftl] = FT_END
    bm.faces.new(list(reversed(rings[0])))[ftl] = FT_END
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    split = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0][ftl] != e.link_faces[1][ftl]]
    bmesh.ops.split_edges(bm, edges=split)
    return bm_to_obj(name, bm, mat)


def make_plane(name, mat, W, H, ft=FT_SIDE, nx=1, ny=1):
    bm = bmesh.new()
    ftl = bm.faces.layers.int.new("ftype")
    vs = [[bm.verts.new((-W / 2 + W * i / nx, -H / 2 + H * j / ny, 0.0)) for i in range(nx + 1)]
          for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))[ftl] = ft
    return bm_to_obj(name, bm, mat)


def ring_verts(bm, n, r, z, a0=0.0, square=False):
    out = []
    for j in range(n):
        a = a0 + 2 * math.pi * j / n
        out.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
    return out


def bridge(bm, A, B):
    n = len(A)
    for j in range(n):
        bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j]))


def fan(bm, ring, c, up=True):
    n = len(ring)
    for j in range(n):
        bm.faces.new((ring[j], ring[(j + 1) % n], c) if up else (ring[(j + 1) % n], ring[j], c))


def iron_part(name, mat, kind):
    bm = bmesh.new()
    if kind == "NAIL":  # a big hand-forged spike head
        a = ring_verts(bm, 8, 0.0115, -0.002)
        b = ring_verts(bm, 8, 0.0105, 0.0035)
        bridge(bm, a, b)
        fan(bm, b, bm.verts.new((0.0, 0.0, 0.0065)))
    elif kind == "BOLT":  # a carriage-bolt dome
        rs = [ring_verts(bm, 8, r, z) for r, z in ((0.0165, -0.002), (0.0145, 0.0055), (0.008, 0.0102))]
        for k in range(2):
            bridge(bm, rs[k], rs[k + 1])
        fan(bm, rs[-1], bm.verts.new((0.0, 0.0, 0.0118)))
    elif kind == "NUT":  # washer, square nut and the bolt's threaded end
        w0 = ring_verts(bm, 8, 0.024, -0.002)
        w1 = ring_verts(bm, 8, 0.024, 0.003)
        bridge(bm, w0, w1)
        fan(bm, w1, bm.verts.new((0.0, 0.0, 0.003)))
        n0 = ring_verts(bm, 4, 0.022, 0.003, a0=math.pi / 4 + 0.2)
        n1 = ring_verts(bm, 4, 0.022, 0.017, a0=math.pi / 4 + 0.2)
        bridge(bm, n0, n1)
        bm.faces.new(n1)
        s0 = ring_verts(bm, 5, 0.0075, 0.016)
        s1 = ring_verts(bm, 5, 0.0072, 0.03)
        bridge(bm, s0, s1)
        bm.faces.new(s1)
    elif kind == "PINTLE":  # the hinge pin and the spike driven into the post (toward +X)
        p0 = ring_verts(bm, 8, 0.012, -0.065)
        p1 = ring_verts(bm, 8, 0.012, 0.055)
        bridge(bm, p0, p1)
        bm.faces.new(p1)
        bm.faces.new(list(reversed(p0)))
        sp = bmesh.ops.create_cube(bm, size=1.0)["verts"]
        bmesh.ops.scale(bm, vec=(0.17, 0.024, 0.026), verts=sp)
        bmesh.ops.translate(bm, vec=(0.085, 0.0, -0.052), verts=sp)
    elif kind == "BARREL":  # the hinge strap's rolled eye round the pin
        b0 = ring_verts(bm, 8, 0.025, -0.035)
        b1 = ring_verts(bm, 8, 0.025, 0.04)
        bridge(bm, b0, b1)
        i0 = ring_verts(bm, 8, 0.0135, -0.035)
        i1 = ring_verts(bm, 8, 0.0135, 0.04)
        bridge(bm, i1, i0)
        for j in range(8):
            j1 = (j + 1) % 8
            bm.faces.new((b1[j], b1[j1], i1[j1], i1[j]))
            bm.faces.new((b0[j1], b0[j], i0[j], i0[j1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm_to_obj(name, bm, mat)


# ---------------------------------------------------------------- kit materials

def attr_vec(g, name):
    return tk._sock(g.node("ShaderNodeAttribute", attribute_name=name).outputs, "Vector")


def combine(g, x, y, z=0.0):
    c = g.node("ShaderNodeCombineXYZ")
    g._in(c, "X", x)
    g._in(c, "Y", y)
    g._in(c, "Z", z)
    return c.outputs[0]


def contrast(g, col, c):
    bc = g.node("ShaderNodeBrightContrast")
    g._in(bc, "Color", col)
    g._in(bc, "Contrast", c)
    return bc.outputs[0]


def photo_at(g, set_name, vec):
    out = {}
    for kind, nc in (("diff", False), ("arm", True), ("disp", True)):
        path = os.path.join(tk.TEXTURES, set_name, "%s_%s_2k.jpg" % (set_name, kind))
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "Non-Color" if nc else "sRGB"
        n = g.node("ShaderNodeTexImage", interpolation="Cubic")
        n.image = img
        g.links.new(vec, n.inputs["Vector"])
        out[kind] = n.outputs["Color"]
    arm = g.node("ShaderNodeSeparateColor")
    g.links.new(out["arm"], arm.inputs[0])
    return dict(color=out["diff"], ao=arm.outputs[0], rough=arm.outputs[1], height=out["disp"])


def voronoi_dist(g, vec, scale):
    v = g.node("ShaderNodeTexVoronoi")
    g._in(v, "Scale", scale)
    g.links.new(vec, v.inputs["Vector"])
    return tk._sock(v.outputs, "Distance")


WOOD_VALUE = 2.2  # the photo's brightness gain: calibrated against the vanilla wood gate's albedo


def wood_material():
    """Weathered palisade timber: grey-brown checked wood along the grain (the planks photo stretched round the log),
    patches of dark fissured bark, lichen; axe facets lighter with chop steps; fresh splits, gouges and breaks raw and
    fibrous; sawn ends with growth rings; claw marks raked through the surface; mud splashed up from the ground."""
    mat, g = tk.new_material("Wood")
    M = lambda a, b: g.math("MULTIPLY", a, b)  # noqa: E731
    A = lambda a, b: g.math("ADD", a, b)  # noqa: E731
    S = lambda a, b: g.math("SUBTRACT", a, b)  # noqa: E731
    lco = attr_vec(g, "lco")
    u, v, _ = g.separate(attr_vec(g, "luv"))
    lx, ly, lz = g.separate(lco)
    facet, fresh, endg = g.separate(attr_vec(g, "ks"))
    mud_amt, bark_amt, seed = g.separate(attr_vec(g, "kp"))
    rr = g.math("SQRT", A(M(lx, lx), M(ly, ly)))
    th = g.math("ARCTAN2", ly, lx)
    side = g.math("SUBTRACT", 1.0, A(A(facet, fresh), endg), clamp=True)

    p = photo_at(g, "weathered_planks", combine(g, A(M(u, 0.35), M(seed, 0.37)), A(v, M(seed, 0.61))))
    col = contrast(g, tk.grade(g, p["color"], 0.5, WOOD_VALUE, (1.0, 0.9, 0.78)), 0.18)
    rough = p["rough"]
    height = p["height"]

    def lines(su, sv, ofs, width):
        n = g.noise(1.0, detail=2.0, roughness=0.5, distortion=0.2,
                    vector=combine(g, M(u, su), M(v, sv), A(seed, ofs)))
        return g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", S(n, 0.5)), 0.0, width, False))

    checks = g.math("MAXIMUM", lines(2.4, 0.45, 0.2, 0.02), M(lines(5.0, 0.9, 2.6, 0.014), 0.8))
    col = g.mix(checks, col, (0.012, 0.01, 0.008))
    height = S(height, M(checks, 1.2))

    # bark left on in patches, more of it low down
    blot = g.noise(1.0, detail=6.0, roughness=0.62, distortion=0.3, vector=combine(g, M(u, 4.0), M(v, 1.5),
                                                                                   A(seed, 0.37)))
    lo = S(S(0.62, M(bark_amt, 0.26)), M(g.ramp(lz, 1.4, 0.1), M(mud_amt, 0.08)))
    patch = M(g.ramp(blot, lo, A(lo, 0.012)), side)
    rim = M(g.math("SUBTRACT", g.ramp(blot, S(lo, 0.035), S(lo, 0.005)), patch, clamp=True), side)
    ridge = g.noise(1.0, detail=5.0, roughness=0.65, distortion=0.4, vector=combine(g, M(u, 45.0), M(v, 4.0),
                                                                                    A(seed, 1.3)))
    fiss = g.ramp(ridge, 0.36, 0.64)
    bark_col = g.mix(fiss, (0.008, 0.006, 0.004), (0.052, 0.035, 0.023))
    bark_col = g.mix(M(g.ramp(g.noise(5.0, detail=4.0), 0.45, 0.8), M(fiss, 0.35)), bark_col, (0.07, 0.06, 0.05))
    col = g.mix(M(rim, 0.85), col, (0.045, 0.032, 0.022))
    col = g.mix(patch, col, bark_col)
    rough = g.mixf(patch, rough, 0.93)
    height = g.mixf(patch, height, A(M(fiss, 2.4), 0.8))
    lichen = M(M(g.ramp(g.noise(11.0, detail=6.0, roughness=0.7), 0.66, 0.72), 0.5), side)
    col = g.mix(lichen, col, (0.27, 0.28, 0.21))

    # axe facets on the points: lighter weathered wood with chop steps across the grain
    fc = tk.grade(g, p["color"], 0.55, WOOD_VALUE * 1.12, (1.0, 0.87, 0.7))
    vv = A(M(v, 17.0), M(g.noise(1.0, detail=2.0, vector=combine(g, M(u, 4.0), M(v, 2.0), A(seed, 7.7))), 1.4))
    st = g.math("FRACT", vv)
    tone = g.noise(1.0, detail=1.0, vector=combine(g, g.math("FLOOR", vv), M(u, 2.0), A(seed, 2.2)))
    fc = g.mix(M(g.ramp(tone, 0.35, 0.65), 0.45), fc, tk._darker(g, fc, 0.62))
    stepline = g.ramp(st, 0.12, 0.0, False)
    fc = g.mix(M(stepline, 0.7), fc, (0.035, 0.028, 0.02))
    col = g.mix(facet, col, fc)
    rough = g.mixf(facet, rough, 0.82)
    height = g.mixf(facet, height, M(st, 0.7))

    # fresh wood: splits, gouges, breaks and splinters
    fib = g.noise(1.0, detail=4.0, roughness=0.6, vector=combine(g, M(u, 70.0), M(v, 2.5), A(seed, 4.1)))
    fr = tk.grade(g, p["color"], 0.9, WOOD_VALUE * 1.5, (1.0, 0.8, 0.56))
    fr = g.mix(0.45, fr, (0.28, 0.2, 0.12))
    fr = g.mix(M(g.ramp(fib, 0.45, 0.72), 0.65), fr, (0.075, 0.054, 0.034))
    col = g.mix(fresh, col, fr)
    rough = g.mixf(fresh, rough, 0.8)
    height = g.mixf(fresh, height, M(fib, 1.4))

    # sawn end grain
    rn = A(rr, M(g.noise(6.0, detail=3.0, vector=lco), 0.012))
    rings = g.ramp(g.math("FRACT", M(rn, 60.0)), 0.62, 0.95)
    eg = g.mix(M(rings, 0.65), (0.24, 0.19, 0.14), (0.1, 0.08, 0.058))
    rc = g.ramp(g.noise(1.0, detail=3.0, roughness=0.5, vector=combine(g, M(th, 2.0), M(rr, 4.0), seed)), 0.6, 0.64)
    eg = g.mix(rc, eg, (0.025, 0.02, 0.016))
    eg = g.mix(0.35, eg, (0.19, 0.18, 0.16))
    col = g.mix(endg, col, eg)
    rough = g.mixf(endg, rough, 0.85)
    height = g.mixf(endg, height, S(M(rings, 0.4), rc))

    # claw marks: sets of four raked grooves, raw wood with dark torn rims
    claw, crim = g.value(0.0), g.value(0.0)
    for k in range(3):
        tc, zc, on = g.separate(attr_vec(g, "kc%d" % k))
        d = S(th, tc)
        d = S(d, M(g.math("ROUND", g.math("DIVIDE", d, 2 * math.pi)), 2 * math.pi))
        s_ = M(d, rr)
        t_ = S(lz, zc)
        phi = 0.22 + 0.13 * k
        a = A(M(s_, math.cos(phi)), M(t_, math.sin(phi)))
        b = S(M(t_, math.cos(phi)), M(s_, math.sin(phi)))
        a = A(a, M(S(g.noise(1.0, detail=2.0, vector=combine(g, M(b, 9.0), A(seed, 3.0 + k), 0.0)), 0.5), 0.008))
        tap = g.math("SUBTRACT", 1.0, M(M(b, 2.0 / 0.34), M(b, 2.0 / 0.34)), clamp=True)
        dist = M(g.math("ABSOLUTE", S(g.math("FRACT", g.math("DIVIDE", a, 0.024)), 0.5)), 0.024)
        w = A(M(g.math("SQRT", tap), 0.0034), 0.0001)
        gate = M(M(g.ramp(g.math("ABSOLUTE", a), 0.05, 0.043), on), g.ramp(tap, 0.0, 0.06))
        claw = g.math("MAXIMUM", claw, M(S(1.0, g.ramp(dist, M(w, 0.45), w)), gate))
        crim = g.math("MAXIMUM", crim, M(S(1.0, g.ramp(dist, w, M(w, 2.0))), gate))
    col = g.mix(M(crim, 0.75), col, (0.03, 0.024, 0.018))
    col = g.mix(claw, col, (0.3, 0.22, 0.135))
    rough = g.mixf(claw, rough, 0.75)
    height = S(height, M(A(claw, M(crim, 0.4)), 1.5))

    # mud splashed up the foot of standing parts, splatter dots above it
    # a dark wet soil line where the log goes into the ground, then splashes of mud thrown up in patches
    soil = M(g.ramp(lz, A(0.05, M(g.noise(1.0, detail=4.0, vector=combine(g, M(u, 9.0), seed, 0.0)), 0.12)), 0.0),
             mud_amt)
    medge = A(A(0.16, M(g.noise(1.0, detail=3.0, vector=combine(g, M(u, 2.2), M(seed, 3.1), 0.0)), 0.36)),
              M(S(g.noise(1.0, detail=5.0, roughness=0.7, vector=combine(g, M(u, 14.0), M(v, 9.0), seed)), 0.5),
                0.3))
    patchy = g.ramp(g.noise(1.0, detail=6.0, roughness=0.68, distortion=0.5,
                            vector=combine(g, M(u, 7.0), M(v, 4.0), A(seed, 5.5))), 0.38, 0.52)
    mud = M(M(g.ramp(lz, medge, S(medge, 0.05)), patchy), mud_amt)
    vd = voronoi_dist(g, combine(g, M(u, 1.4), v, seed), 30.0)
    dots = M(M(g.ramp(vd, 0.2, 0.08), g.ramp(lz, 0.75, 0.15)), mud_amt)
    dots = M(dots, g.ramp(g.noise(1.0, vector=combine(g, M(u, 4.0), M(v, 4.0), seed)), 0.45, 0.6))
    mm = g.math("MAXIMUM", g.math("MAXIMUM", mud, M(dots, 0.85)), soil)
    mc = g.mix(g.noise(9.0, detail=5.0), (0.055, 0.04, 0.027), (0.1, 0.075, 0.05))
    mc = g.mix(soil, mc, (0.026, 0.02, 0.014))
    col = g.mix(mm, col, mc)
    rough = g.mixf(mm, rough, 0.8)
    height = g.mixf(mm, height, A(0.6, M(g.noise(30.0, detail=4.0), 0.7)))

    # grime in the crevices and low down, the photo's own occlusion, dust and specks
    cav = g.ramp(g.cavity(0.08), 0.35, 1.0)
    dirt = g.math("ADD", M(S(1.0, cav), 0.85), M(g.ramp(lz, 1.0, 0.0), M(mud_amt, 0.3)), clamp=True)
    dirt = M(dirt, g.ramp(g.noise(5.0, detail=5.0), 0.2, 0.7))
    col = g.mix(dirt, col, (0.03, 0.024, 0.018))
    rough = g.mixf(dirt, rough, 0.88)
    col = tk._multiply_color(g, col, g.mix(0.55, (1.0, 1.0, 1.0), p["ao"]))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.4)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.55, 0.01))


ROPE_W = 0.12  # the rope swatch is twice the rope's girth wide, for more pixels across the strands


def rope_material():
    """Three-strand laid rope on the flat swatch (u around 0-1 across its width, v along): strands, fibres, grime."""
    mat, g = tk.new_material("Rope")
    lu, lv, _ = g.separate(attr_vec(g, "luv"))
    u = g.math("DIVIDE", lu, ROPE_W)
    a = g.math("ADD", g.math("MULTIPLY", u, 3.0), g.math("DIVIDE", lv, 0.034))
    t = g.math("FRACT", a)
    prof = g.math("SUBTRACT", 1.0, g.math("POWER", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", t, 2.0),
                                                                                 1.0)), 2.5))
    fib = g.noise(1.0, detail=5.0, roughness=0.7, vector=combine(g, g.math("MULTIPLY", a, 9.0),
                                                                 g.math("MULTIPLY", lv, 6.0)))
    color = (0.165, 0.125, 0.08)
    col = g.mix(g.ramp(prof, 0.05, 0.7), (0.025, 0.019, 0.013), color)
    col = g.mix(g.math("MULTIPLY", fib, 0.7), col, tuple(c * 0.55 for c in color))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=4.0), 0.45, 0.75), 0.6), col, (0.12, 0.11, 0.09))
    dirt = g.ramp(g.noise(3.0, detail=5.0), 0.4, 0.68)
    col = g.mix(g.math("MULTIPLY", dirt, 0.75), col, (0.038, 0.03, 0.021))
    rough = 0.92
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.8)
    height = g.math("ADD", g.math("MULTIPLY", prof, 0.8), g.math("MULTIPLY", fib, 0.3))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.7, 0.004))


def mud_material():
    """Packed earth for the berm: dark soil, dry lighter crust, small stones."""
    mat, g = tk.new_material("Mud")
    n1 = g.noise(7.0, detail=6.0, roughness=0.6)
    n2 = g.noise(25.0, detail=4.0)
    col = g.mix(n1, (0.026, 0.02, 0.014), (0.068, 0.052, 0.036))
    crust = g.ramp(g.noise(3.0, detail=5.0), 0.55, 0.66)
    col = g.mix(g.math("MULTIPLY", crust, 0.55), col, (0.105, 0.086, 0.064))
    straw = g.math("MULTIPLY", g.ramp(g.noise(14.0, detail=6.0, roughness=0.7, distortion=1.2), 0.66, 0.72), 0.7)
    col = g.mix(straw, col, (0.12, 0.1, 0.055))
    vd = voronoi_dist(g, g.coords(), 45.0)
    peb = g.math("MULTIPLY", g.ramp(vd, 0.26, 0.15), g.ramp(g.noise(9.0), 0.54, 0.64))
    col = g.mix(peb, col, g.mix(n2, (0.07, 0.066, 0.06), (0.15, 0.14, 0.125)))
    rough = g.mixf(crust, 0.8, 0.95)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.12)
    height = g.math("ADD", g.math("ADD", g.math("MULTIPLY", n1, 0.6), g.math("MULTIPLY", n2, 0.3)),
                    g.math("MULTIPLY", peb, 0.8))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.6, 0.01))


# ---------------------------------------------------------------- the kit parts

FRONT = -math.pi / 2  # local angle of the face that faces -Y when a log is placed unturned
P_FRONT = -3 * math.pi / 4  # the corner post's outside corner (-X, -Y)

LOGS = {
    "L0": dict(R=0.130, length=2.93, seed=11, facets=4, stubs=1, beta=(13.0, 21.0)),
    "L1": dict(R=0.124, length=2.99, seed=12, facets=5, stubs=1, beta=(13.0, 19.0)),
    "L2": dict(R=0.135, length=2.90, seed=13, facets=6, stubs=2, beta=(13.0, 23.0)),
    "L3": dict(R=0.127, length=2.96, seed=14, facets=4, stubs=1, beta=(11.0, 21.0), chops=4),
    # split down the front, claw marks
    "LA": dict(R=0.126, length=2.95, seed=15, facets=5, stubs=0,
               crack=dict(th=FRONT + 0.32, z0=0.7, z1=2.1, depth=0.05, open=0.013),
               claws=((FRONT - 0.3, 1.1, 1.0), (FRONT + 0.95, 1.55, 1.0))),
    # axe gouges, claw marks
    "LB": dict(R=0.132, length=2.92, seed=16, facets=6, stubs=1,
               gouges=((FRONT - 0.22, 1.25, 0.10, 0.045, 12.0), (FRONT + 0.25, 1.37, 0.09, 0.035, -8.0),
                       (FRONT + 0.05, 0.6, 0.11, 0.04, 4.0)),
               claws=((FRONT + 0.75, 0.95, 1.0),)),
    # the corner post, intact and battered
    "P0": dict(R=0.19, length=3.0, seed=21, facets=6, stubs=2, segs=14, beta=(16.0, 26.0), bark=0.5, chops=4),
    "P1": dict(R=0.19, length=3.0, seed=22, facets=5, stubs=1, segs=14, beta=(16.0, 26.0), bark=0.5, chops=4,
               gouges=((P_FRONT + 0.2, 1.3, 0.12, 0.05, 10.0), (P_FRONT - 0.28, 1.43, 0.1, 0.04, -6.0),
                       (P_FRONT + 0.5, 0.72, 0.12, 0.045, 0.0)),
               crack=dict(th=P_FRONT - 0.65, z0=0.85, z1=2.05, depth=0.055, open=0.015),
               claws=((P_FRONT - 0.05, 1.0, 1.0), (P_FRONT + 0.95, 1.5, 1.0))),
}
RAILS = {
    "RA": dict(R=0.056, length=1.04, seed=31),
    "RB": dict(R=0.054, length=1.04, seed=32),
    "RG": dict(R=0.052, length=1.24, seed=33),
    "RD": dict(R=0.048, length=1.85, seed=34),
}
SWATCHES = {  # name: (width, height, material key, face type)
    "FRESH": (0.36, 0.62, "wood", FT_FRESH),
    "END": (0.32, 0.32, "wood", FT_END),
    "ROPE": (ROPE_W, 1.6, "rope", FT_SIDE),
    "WIRE": (0.022, 1.2, "wire", FT_SIDE),
    "STRAP": (0.07, 1.3, "iron", FT_SIDE),
    "MUD": (0.62, 0.38, "mud", FT_SIDE),
}


def build_kit():
    mats = dict(
        wood=wood_material(),
        rope=rope_material(),
        mud=mud_material(),
        iron=tk.photo_material("Iron", "metal_plate_02", scale=2.4, value=0.42, sat=0.7, exposed="rust_coarse_01",
                               chip=1.0, patches=1.0, grime=0.7, streaks=0.6, metal_floor=0.3, rough_scale=1.0,
                               grit=0.6, scratches=0.15, edges=0.15, contrast=0.12),
        wire=tk.photo_material("Wire", "metal_plate_02", scale=4.0, value=0.95, exposed="rust_coarse_01",
                               patches=0.7, chip=1.0, metal_floor=0.5, grime=0.5, grit=0.4),
    )
    x = 0.0
    for name, spec in LOGS.items():
        spec = dict(spec)
        claws = spec.pop("claws", ())
        bark = spec.pop("bark", 0.38)
        obj, info = make_log("Kit_" + name, mats["wood"], **spec)
        obj.location = (x, 0.0, Z0)
        kit_part(name, obj, "cyl", R=spec["R"], mud=1.0, bark=bark, claws=claws, context=True,
                 length=spec["length"], psi=info["psi"])
        slab = tk.box("Ctx_" + name, (0.9, 0.9, 0.06), (x, 0.0, Z0 - 0.03), mats["wood"])
        CONTEXT.append(slab)
        x += 1.0
    x = 0.0
    for name, spec in RAILS.items():
        obj = make_rail("Kit_" + name, mats["wood"], **spec)
        obj.location = (x, 1.5, Z0)
        kit_part(name, obj, "cyl", R=spec["R"], mud=0.0, bark=0.6, length=spec["length"])
        x += 0.6
    # Swatches (all but the earth) and iron parts are baked standing up, facing -Y: their pieces are mostly
    # vertical, and lying flat would give them the material's dust settled on upward faces all over
    x = 3.0
    for name, (W, H, mk, ft) in SWATCHES.items():
        obj = make_plane("Kit_" + name, mats[mk], W, H, ft)
        obj.location = (x, 1.5, Z0 + 0.5 + (H / 2 if name != "MUD" else 0.0))
        if name != "MUD":
            obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        kit_part(name, obj, "flat", W=W, H=H)
        x += max(W, 0.2) + 0.4
    x = 0.0
    for name in ("NAIL", "BOLT", "NUT", "PINTLE", "BARREL"):
        obj = iron_part("Kit_" + name, mats["iron"], name)
        obj.location = (x, 3.2, Z0 + 0.5)
        if name in ("NAIL", "BOLT", "NUT"):
            obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        kit_part(name, obj, "iron")
        x += 0.5
    bpy.context.view_layer.update()
    return mats


def kit_preview(mats):
    """Debug (mode 'kit'): the unbaked kit under the preview lights, standing as a wall."""
    tk.preview_stage()
    for o in CONTEXT:
        o.hide_render = True
    for k, name in enumerate(("L0", "LA", "L2", "LB", "L3", "L1", "P1", "P0")):
        KIT[META[name]["index"]].location = (-2.0 + 0.27 * k + (0.3 if k > 5 else 0.0) + (0.25 if k > 6 else 0.0),
                                             0.0, Z0)
    for name, cam, path in (("front", ((0.2, -3.6, 1.4), (-1.0, 0.0, 1.0)), "dbg_kit_front.png"),
                            ("top", ((-0.4, -1.6, 2.5), (-1.2, 0.0, 1.9)), "dbg_kit_top.png")):
        tk.render(tk.camera("KitCam" + name, cam[0], cam[1], lens=35), os.path.join(PREVIEWS, path),
                  res=(1400, 1000), samples=48)


# ---------------------------------------------------------------- bake, then cut the kit back into templates

class Tpl:
    def __init__(self, name, V, F, UV, meta):
        self.name, self.V, self.F, self.UV, self.meta = name, V, F, UV, meta


def bake_kit():
    kit = tk.join(list(KIT), "PalisadeKit")
    kit = tk.triangulate(kit)
    tk.smart_uvs(kit)
    log("kit: %d triangles, baking" % len(kit.data.polygons))
    try:
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME)
    except RuntimeError as e:
        log("GPU bake failed (%s); retrying on the CPU" % e)
        bpy.context.scene.cycles.device = "CPU"
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME)
    for o in CONTEXT:
        bpy.data.objects.remove(o)
    return kit, paths


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
    UV = uv.reshape(-1, 2)[idx].astype(np.float64)
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


SW = {}


def swatch_maps():
    for name, (W, H, _, _) in SWATCHES.items():
        t = T[name]
        P = t.V[t.F].reshape(-1, 3)[:, :2]
        U = t.UV.reshape(-1, 2)
        A = np.c_[P, np.ones(len(P))]
        Mx, res, *_ = np.linalg.lstsq(A, U, rcond=None)
        err = np.abs(A @ Mx - U).max()
        SW[name] = (Mx, W, H)
        log("swatch %s: %.3f x %.3f m, fit error %.2g, %d px across" % (name, W, H, err,
                                                                         np.linalg.norm(Mx[0]) * W * 2048))


def sw_uv(name, a, b, margin=0.004):
    """Swatch coordinates (meters from its corner) to atlas UVs."""
    Mx, W, H = SW[name]
    a = np.clip(np.asarray(a, float), margin, W - margin)
    b = np.clip(np.asarray(b, float), margin, H - margin)
    return np.stack([a - W / 2, b - H / 2, np.ones_like(a)], axis=-1) @ Mx


# ================================================================ pieces

class Item:
    def __init__(self, V, F, UV, tag=""):
        self.V = np.asarray(V, np.float64).reshape(-1, 3)
        self.F = np.asarray(F, np.int64).reshape(-1, 3)
        self.UV = np.asarray(UV, np.float64).reshape(-1, 3, 2)
        self.tag = tag
        self._bvh = None

    def moved(self, M):
        return Item(self.V @ M[:3, :3].T + M[:3, 3], self.F, self.UV, self.tag)

    def bvh(self):
        if self._bvh is None:
            self._bvh = BVHTree.FromPolygons(self.V.tolist(), self.F.tolist(), all_triangles=True)
        return self._bvh


def merge(items, tag=None):
    items = [it for it in items if it is not None and len(it.F)]
    V, F, UV, off = [], [], [], 0
    for it in items:
        V.append(it.V)
        F.append(it.F + off)
        UV.append(it.UV)
        off += len(it.V)
    return Item(np.concatenate(V), np.concatenate(F), np.concatenate(UV), tag or items[0].tag)


def place(name, M, tag=""):
    t = T[name]
    return Item(t.V @ M[:3, :3].T + M[:3, 3], t.F.copy(), t.UV.copy(), tag or name)


def hit(it, origin, direction, dist=3.0):
    loc, nrm, _, _ = it.bvh().ray_cast(Vector(tuple(map(float, origin))), Vector(tuple(map(float, unit(direction)))),
                                       dist)
    if loc is None:
        return None, None
    n = np.array(nrm)
    if np.dot(n, direction) > 0:
        n = -n
    return np.array(loc), n


def stud(kit, target, origin, direction, sink=0.002, spin=None, rnd=None, tilt=0.0):
    p, n = hit(target, origin, direction)
    if p is None:
        return None
    rnd = rnd or RND
    if tilt:
        n = unit(n + np.array((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * tilt)
    M = m_t(*(p - n * sink)) @ m_align(n) @ m_r("Z", spin if spin is not None else rnd.uniform(0, 360))
    return place(kit, M, "iron")


def section_points(items, p0, n):
    p0, n = np.asarray(p0, float), unit(n)
    out = []
    for it in items:
        if it is None:
            continue
        d = (it.V - p0) @ n
        D = d[it.F]
        m = (D.min(1) < 0) & (D.max(1) > 0)
        if not m.any():
            continue
        F, D = it.F[m], D[m]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            di, dj = D[:, i], D[:, j]
            k = di * dj < 0
            t = di[k] / (di[k] - dj[k])
            a, b = it.V[F[k, i]], it.V[F[k, j]]
            out.append(a + t[:, None] * (b - a))
    return np.concatenate(out) if out else np.zeros((0, 3))


# ---------------------------------------------------------------- bmesh round trip: cutting and capping

def item_bm(it):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(tuple(p)) for p in it.V]
    for f, uv in zip(it.F, it.UV):
        if len(set(f.tolist())) < 3:
            continue
        try:
            face = bm.faces.new([vs[i] for i in f])
        except ValueError:
            continue
        for lp, u in zip(face.loops, uv):
            lp[uvl].uv = (float(u[0]), float(u[1]))
    return bm, uvl


def bm_item(bm, uvl, tag=""):
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    big = [f for f in bm.faces if len(f.verts) > 3]
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.verts.index_update()
    V = np.array([v.co[:] for v in bm.verts])
    F = np.array([[l.vert.index for l in f.loops] for f in bm.faces])
    UV = np.array([[l[uvl].uv[:] for l in f.loops] for f in bm.faces])
    bm.free()
    return Item(V, F, UV, tag)


def boundary_loops(edges):
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def plane_basis(no):
    a = Vector((1, 0, 0)) if abs(no.x) < 0.9 else Vector((0, 1, 0))
    e1 = (a - no * a.dot(no)).normalized()
    return e1, no.cross(e1)


def fresh_uv_faces(faces, uvl, c, no, rnd, sw="FRESH"):
    """Planar UVs on the fresh-wood swatch per face, with the grain along the break normal on steep faces."""
    _, W, H = SW[sw]
    e1, e2 = plane_basis(no)
    for f in faces:
        f.normal_update()
        t = f.normal.cross(no)
        if t.length > 0.25:
            ax, bx = t.normalized(), no
        else:
            ax, bx = e1, e2
        oa, ob = rnd.uniform(0.1, W - 0.1), rnd.uniform(0.12, H - 0.3)
        for lp in f.loops:
            d = lp.vert.co - c
            lp[uvl].uv = tuple(sw_uv(sw, oa + d.dot(ax), ob + d.dot(bx)))


def cap_flat(bm, uvl, loop, no, sw):
    c = sum((v.co for v in loop), Vector()) / len(loop)
    e1, e2 = plane_basis(no)
    pts = [((v.co - c).dot(e1), (v.co - c).dot(e2)) for v in loop]
    if signed_area(pts) < 0:
        loop = loop[::-1]
    try:
        f = bm.faces.new(loop)
    except ValueError:
        return
    _, W, H = SW[sw]
    rmax = max(math.hypot(*p) for p in pts)
    s = min(1.0, (min(W, H) / 2 - 0.006) / max(rmax, 1e-6))
    for lp in f.loops:
        d = lp.vert.co - c
        lp[uvl].uv = tuple(sw_uv(sw, W / 2 + d.dot(e1) * s, H / 2 + d.dot(e2) * s))


def shard(base, d, L, w, t, rnd, outward=None):
    """A splinter: a thin tapering sliver of fresh wood, slightly bent."""
    base, d = np.asarray(base, float), unit(d)
    ref = unit(outward) if outward is not None else unit(np.cross(d, (0.3, 0.2, 0.9)))
    et = unit(ref - d * ref.dot(d))
    ew = np.cross(d, et)
    bend = et * rnd.uniform(-0.15, 0.15) * L
    r0 = [base + ew * sw_ * w / 2 + et * st * t / 2 for sw_, st in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    mid = base + d * L * 0.5 + bend * 0.4
    r1 = [mid + (p - base) * 0.55 for p in r0]
    tip = base + d * L + bend
    V = r0 + r1 + [tip]
    F, UV = [], []
    _, W, H = SW["FRESH"]
    oa, ob = rnd.uniform(0.05, W - 0.05), rnd.uniform(0.05, H - L - 0.05)

    def uvp(i, side):
        p = V[i] - base
        ax = ew if side % 2 == 0 else et
        return sw_uv("FRESH", oa + p @ ax + side * 0.02, ob + p @ d)

    for j in range(4):
        j1 = (j + 1) % 4
        for tri in ((j, j1, 4 + j1), (j, 4 + j1, 4 + j), (4 + j, 4 + j1, 8)):
            F.append(tri)
            UV.append([uvp(i, j) for i in tri])
    F += [(0, 3, 2), (0, 2, 1)]
    UV += [[uvp(i, 0) for i in (0, 3, 2)], [uvp(i, 0) for i in (0, 2, 1)]]
    return Item(V, F, UV, "splinter")


def cap_jagged(bm, uvl, loop, no, rnd, spikes, shards):
    """A snapped end: the rim torn unevenly, long splinters on the side that gave last, a fibrous broken face."""
    c = sum((v.co for v in loop), Vector()) / len(loop)
    e1, e2 = plane_basis(no)
    pts = [((v.co - c).dot(e1), (v.co - c).dot(e2)) for v in loop]
    if signed_area(pts) < 0:
        loop = loop[::-1]
    n = len(loop)
    a0 = rnd.uniform(0, 2 * math.pi)
    planar = []
    for v in loop:
        d = v.co - c
        d = d - no * d.dot(no)
        planar.append(d)
        ang = math.atan2(d.dot(e2), d.dot(e1))
        sd = max(0.0, math.cos(ang - a0))
        lift = rnd.uniform(-0.01, 0.014) + spikes * sd ** 2 * rnd.uniform(0.0, 0.06) * (1.0 if rnd.random() < 0.6
                                                                                      else 0.3)
        v.co += no * lift
    r1, r2 = [], []
    m = max(4, (n + 1) // 2)
    for d in planar:
        ang = math.atan2(d.dot(e2), d.dot(e1))
        sd = max(0.0, math.cos(ang - a0))
        h1 = rnd.uniform(-0.01, 0.022) + spikes * sd ** 1.5 * (rnd.uniform(0.04, 0.15) if rnd.random() < 0.35
                                                                else rnd.uniform(0.0, 0.035))
        r1.append(bm.verts.new(c + d * rnd.uniform(0.55, 0.7) + no * h1))
    for k in range(m):
        d = planar[int(k * n / m)]
        ang = math.atan2(d.dot(e2), d.dot(e1))
        sd = max(0.0, math.cos(ang - a0))
        h2 = rnd.uniform(-0.015, 0.02) + spikes * sd * (rnd.uniform(0.03, 0.09) if rnd.random() < 0.25 else 0.0)
        r2.append(bm.verts.new(c + d * rnd.uniform(0.2, 0.32) + no * h2))
    cv = bm.verts.new(c + no * rnd.uniform(-0.02, 0.03))
    faces = []

    def jm(i):
        return (i * m // n) % m

    for i in range(n):
        j = (i + 1) % n
        a, b = jm(i), jm(i + 1)
        polys = [(loop[i], loop[j], r1[j], r1[i]),
                 (r1[i], r1[j], r2[a]) if a == b else (r1[i], r1[j], r2[b], r2[a])]
        for vs in polys:
            try:
                faces.append(bm.faces.new(vs))
            except ValueError:
                pass
    for k in range(m):
        try:
            faces.append(bm.faces.new((r2[k], r2[(k + 1) % m], cv)))
        except ValueError:
            pass
    fresh_uv_faces(faces, uvl, c, no, rnd)
    out = []
    count = shards if shards is not None else int(round(0.5 + 1.5 * spikes))
    for _ in range(count):
        cands = [i for i in range(n) if math.cos(math.atan2(planar[i].dot(e2), planar[i].dot(e1)) - a0) > 0.2]
        i = rnd.choice(cands or list(range(n)))
        d = planar[i]
        base = c + d * rnd.uniform(0.72, 0.92) + no * rnd.uniform(0.0, 0.02)
        dirn = unit(np.array(no) + np.array(d.normalized()) * rnd.uniform(0.05, 0.3)
                    + np.array(e1) * rnd.uniform(-0.12, 0.12))
        out.append(shard(np.array(base), dirn, rnd.uniform(0.05, 0.15) * spikes + 0.03, rnd.uniform(0.01, 0.022),
                         rnd.uniform(0.005, 0.009), rnd, outward=np.array(d)))
    return out


def cut(it, co, no, cap="jagged", seed=0, spikes=1.0, shards=None):
    """Cuts away everything on the +no side of the plane through co and caps the hole: 'jagged' (a snapped end),
    'end' (a sawn end with growth rings) or 'fresh' (a flat raw cut)."""
    bm, uvl = item_bm(it)
    co = Vector(tuple(map(float, co)))
    no = Vector(tuple(map(float, no))).normalized()
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co,
                                 plane_no=no, clear_outer=True)
    edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
    rnd = random.Random(seed)
    extra = []
    for loop in boundary_loops(edges):
        if cap == "end":
            cap_flat(bm, uvl, loop, no, "END")
        elif cap == "fresh":
            cap_flat(bm, uvl, loop, no, "FRESH")
        elif cap == "jagged":
            extra += cap_jagged(bm, uvl, loop, no, rnd, spikes, shards)
    out = bm_item(bm, uvl, it.tag)
    return merge([out] + extra, it.tag) if extra else out


# ---------------------------------------------------------------- generated parts: rope, wire, straps, debris, earth

def frames(P, closed, up=None):
    n = len(P)
    T_ = []
    for i in range(n):
        if closed:
            d = P[(i + 1) % n] - P[(i - 1) % n]
        else:
            d = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T_.append(unit(d))
    N = []
    for i in range(n):
        if i == 0:
            ref = np.asarray(up, float) if up is not None else (np.array((0.0, 0.0, 1.0)) if abs(T_[0][2]) < 0.9
                                                                 else np.array((1.0, 0.0, 0.0)))
        else:
            ref = N[-1]
        N.append(unit(ref - T_[i] * ref.dot(T_[i])))
    B = [np.cross(T_[i], N[i]) for i in range(n)]
    return np.array(T_), np.array(N), np.array(B)


def tube(pts, r, sides, sw, closed=False, caps=True, rfun=None, tag="rope", up=None):
    """A tube along a polyline with its surface laid on a swatch (u around its width, v along its length)."""
    P = np.asarray(pts, float)
    n = len(P)
    T_, N, B = frames(P, closed, up)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]
    close = np.linalg.norm(P[0] - P[-1]) if closed else 0.0
    total = s[-1] + close
    _, Wsw, Hsw = SW[sw]
    vs = min(1.0, (Hsw - 0.03) / max(total, 1e-6))
    v0 = RND.uniform(0.012, max(0.013, Hsw - 0.015 - total * vs))
    V = []
    for i in range(n):
        ri = r * (rfun(i / max(n - 1, 1)) if rfun else 1.0)
        for j in range(sides):
            a = 2 * math.pi * j / sides
            V.append(P[i] + (N[i] * math.cos(a) + B[i] * math.sin(a)) * ri)
    F, UVa = [], []
    for i in range(n if closed else n - 1):
        i1 = (i + 1) % n
        va, vb = v0 + s[i] * vs, v0 + (s[i] + (seg[i] if i < n - 1 else close)) * vs
        for j in range(sides):
            q = (i * sides + j, i * sides + (j + 1) % sides, i1 * sides + (j + 1) % sides, i1 * sides + j)
            quv = ((j / sides, va), ((j + 1) / sides, va), ((j + 1) / sides, vb), (j / sides, vb))
            F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            UVa += [(quv[0], quv[1], quv[2]), (quv[0], quv[2], quv[3])]
    if caps and not closed:
        for end, i, v in ((0, 0, v0), (1, n - 1, v0 + s[-1] * vs)):
            c = len(V)
            V.append(P[i])
            for j in range(sides):
                a, b = i * sides + j, i * sides + (j + 1) % sides
                F.append((c, b, a) if end == 0 else (c, a, b))
                UVa.append(((0.5, v), (0.5 + 0.1 / sides, v), (0.5 - 0.1 / sides, v)))
    UVa = np.array(UVa)
    UV = sw_uv(sw, UVa[..., 0] * Wsw, UVa[..., 1])
    return Item(V, F, UV, tag)


def fray(p, d, rnd, r=ROPE_R, count=3, length=0.05):
    """Frayed rope fibres splaying from an end."""
    out = []
    d = unit(d)
    for k in range(count):
        side = unit(np.cross(d, (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))))
        L = length * rnd.uniform(0.6, 1.3)
        a = np.asarray(p) + side * r * 0.4
        pts = [a, a + d * L * 0.45 + side * L * 0.15, a + d * L * 0.85 + side * L * 0.45
               + np.array((0, 0, -L * 0.15))]
        out.append(tube(pts, r * 0.32, 3, "ROPE", rfun=lambda t: 1.0 - 0.6 * t))
    return out


def rope_end(pts, rnd, r=ROPE_R, frayed=True):
    """A loose rope end hanging along pts, frayed at its tip."""
    items = [tube(pts, r, 5, "ROPE")]
    if frayed:
        items += fray(pts[-1], np.asarray(pts[-1]) - np.asarray(pts[-2]), rnd, r)
    return items


def dangling(target, origin, direction, rnd, length, drift):
    """A torn rope end hanging from where a ray from origin meets target, drifting (dx, dy) as it falls."""
    p, n = hit(target, origin, direction)
    if p is None:
        return []
    p = p + n * (ROPE_R + 0.001)
    pts = [p]
    for k, t in enumerate((0.3, 0.6, 1.0)):
        pts.append(p + np.array((drift[0] * t + rnd.uniform(-0.006, 0.006), drift[1] * t, -length * t)))
    return rope_end(pts, rnd)


def loop_path(items, c, eu, ev, off, n):
    c, eu, ev = np.asarray(c, float), unit(eu), unit(ev)
    pts = section_points(items, c, np.cross(eu, ev))
    if len(pts) < 3:
        return None
    Q = np.c_[(pts - c) @ eu, (pts - c) @ ev]
    H = offset_hull(Q, off, n)
    return np.array([c + eu * x + ev * y for x, y in H])


def lashing(items, c, eu_of, ev, rnd, alphas=(40.0, -40.0), loose=0.0, drop=0.0, n=20, tails=True, gap=0.013):
    """Rope wrapped round two crossing timbers: a loop in each of two tilted planes, a knot's two tails."""
    out = []
    paths = []
    ev = unit(ev)
    for k, a in enumerate(alphas):
        eu = unit(eu_of(a))
        cc = np.asarray(c, float) + np.cross(eu, ev) * (k - (len(alphas) - 1) / 2) * gap
        path = loop_path(items, cc, eu, ev, ROPE_R + 0.0015 + loose, n)
        if path is None:
            continue
        if drop:
            path = path + np.array((0.0, 0.0, -drop))
        paths.append(path)
        out.append(tube(path, ROPE_R, 5, "ROPE", closed=True))
    if tails and paths:
        P = paths[0]
        i = int(np.argmax(P @ ev * 1.0 + P[:, 2] * 0.6))
        p = P[i]
        dx, dz = rnd.choice(((0.02, -0.075), (-0.018, -0.065)))
        q = [p, p + ev * 0.015 + np.array((dx * 0.4, 0.0, dz * 0.4)), p + ev * 0.022 + np.array((dx, 0, dz))]
        out += rope_end(q, rnd, ROPE_R * 0.9)
    return out, paths


def wire_wrap(items, c, eu_of, ev, rnd, alphas=(32.0, -32.0)):
    """Fence wire twisted round a crossing: two loops and a twisted pigtail."""
    out = []
    ev = unit(ev)
    first = None
    for k, a in enumerate(alphas):
        eu = unit(eu_of(a))
        cc = np.asarray(c, float) + np.cross(eu, ev) * (k - 0.5) * 0.02
        path = loop_path(items, cc, eu, ev, WIRE_R + 0.001, 18)
        if path is None:
            continue
        first = path if first is None else first
        out.append(tube(path, WIRE_R, 3, "WIRE", closed=True, tag="wire"))
    if first is not None:
        i = int(np.argmax(first @ ev + first[:, 2] * 0.3))
        p = first[i]
        d = unit(ev + np.array((0.25, 0.0, 0.3)))
        e1 = unit(np.cross(d, (0, 0, 1)))
        e2 = np.cross(d, e1)
        for ph in (0.0, math.pi):
            pts = [p + d * (0.06 * t) + (e1 * math.cos(ph + t * 14) + e2 * math.sin(ph + t * 14)) * WIRE_R * 1.1
                   for t in np.linspace(0, 1, 7)]
            out.append(tube(pts, WIRE_R, 3, "WIRE", tag="wire"))
    return out


def strap(pts, up, width, thick, outward, sw="STRAP", tag="strap"):
    """A flat iron bar along pts: width along `up`, thickness toward `outward` (a vector or a function of the
    point)."""
    P = np.asarray(pts, float)
    n = len(P)
    T_, _, _ = frames(P, False)
    U = np.tile(unit(up), (n, 1)) if np.ndim(up) == 1 else np.array([unit(u) for u in up])
    U = np.array([unit(U[i] - T_[i] * U[i].dot(T_[i])) for i in range(n)])
    Nn = np.cross(T_, U)
    ref = np.array([outward(p) for p in P]) if callable(outward) else np.tile(outward, (n, 1))
    if np.mean(np.sum(Nn * ref, axis=1)) < 0:
        U = -U
        Nn = -Nn
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    _, Wsw, Hsw = SW[sw]
    vs = min(1.0, (Hsw - 0.03) / max(s[-1], 1e-6))
    v0 = RND.uniform(0.012, max(0.013, Hsw - 0.015 - s[-1] * vs))
    aw = min(1.0, (Wsw - 0.012) / width)
    V = []
    for i in range(n):
        w2, t2 = U[i] * width / 2, Nn[i] * thick / 2
        V += [P[i] + w2 + t2, P[i] - w2 + t2, P[i] - w2 - t2, P[i] + w2 - t2]
    F, UVa = [], []

    def quad(a, b, c_, d, uv):
        F.extend([(a, b, c_), (a, c_, d)])
        UVa.extend([(uv[0], uv[1], uv[2]), (uv[0], uv[2], uv[3])])

    # the inner face reads another stretch of the swatch (after the outer one if it fits, else before it)
    vend = v0 + s[-1] * vs
    vin = 0.3 if vend + 0.3 < Hsw - 0.01 else -min(0.3, v0 - 0.008)
    for i in range(n - 1):
        k, k1 = 4 * i, 4 * (i + 1)
        va, vb = v0 + s[i] * vs, v0 + s[i + 1] * vs
        quad(k + 1, k1 + 1, k1 + 0, k + 0, ((0.006, va), (0.006, vb), (0.006 + width * aw, vb), (0.006 + width * aw, va)))
        quad(k + 3, k1 + 3, k1 + 2, k + 2, ((0.006 + width * aw, va + vin), (0.006 + width * aw, vb + vin),
                                            (0.006, vb + vin), (0.006, va + vin)))
        quad(k + 0, k1 + 0, k1 + 3, k + 3, ((0.002, va), (0.002, vb), (0.002 + thick, vb), (0.002 + thick, va)))
        quad(k + 2, k1 + 2, k1 + 1, k + 1, ((0.002, va), (0.002, vb), (0.002 + thick, vb), (0.002 + thick, va)))
    e = 4 * (n - 1)
    quad(0, 3, 2, 1, ((0.006, v0), (0.006, v0), (0.012, v0), (0.012, v0)))
    quad(e + 0, e + 1, e + 2, e + 3, ((0.006, v0), (0.006, v0), (0.012, v0), (0.012, v0)))
    UVa = np.array(UVa)
    UVa[..., 1] = np.clip(UVa[..., 1], 0.005, Hsw - 0.005)
    return Item(V, F, sw_uv(sw, UVa[..., 0], UVa[..., 1]), tag), (P, U, Nn)


def chip(center, size, yaw, rnd, tilt=8.0):
    """A wood chip lying on the ground: a small irregular slab of fresh wood."""
    sx, sy, sz = size
    bm = bmesh.new()
    vs = []
    for z in (-sz / 2, sz / 2):
        for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(bm.verts.new((x * sx / 2 * rnd.uniform(0.6, 1.0), y * sy / 2 * rnd.uniform(0.6, 1.0),
                                    z * rnd.uniform(0.6, 1.2))))
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new("UVMap")
    fresh_uv_faces(bm.faces[:], uvl, Vector((0, 0, 0)), Vector((1, 0, 0)), rnd)
    M = m_t(*center) @ m_r("Z", yaw) @ m_r("X", rnd.uniform(-tilt, tilt)) @ m_r("Y", rnd.uniform(-tilt, tilt))
    return bm_item(bm, uvl, "chip").moved(M)


def heightfield(xs, ys, hfun, sw="MUD", sa=1.0, sb=1.0, tag="earth"):
    """Earth on the ground: a grid of heights (cells entirely at ground level are left out)."""
    nx, ny = len(xs), len(ys)
    H = np.array([[hfun(x, y) for x in xs] for y in ys])
    V, F, UVa = [], [], []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            h = H[j, i]
            V.append((x, y, Z0 + (h if h > 0.0008 else -0.006)))
    _, W, Hh = SW[sw]
    for j in range(ny - 1):
        for i in range(nx - 1):
            if max(H[j, i], H[j, i + 1], H[j + 1, i], H[j + 1, i + 1]) <= 0.0008:
                continue
            q = (j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
            uv = [((V[k][0] - xs[0]) * sa + 0.01, (V[k][1] - ys[0]) * sb + 0.01) for k in q]
            F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            UVa += [(uv[0], uv[1], uv[2]), (uv[0], uv[2], uv[3])]
    UVa = np.array(UVa)
    return Item(V, F, sw_uv(sw, UVa[..., 0], UVa[..., 1]), tag)


def lumps(a, b, seed):
    """Noise periodic over 1 m along a, faded to nothing at a = +-0.5 so any two blocks meet cleanly."""
    n = pnoise(math.cos(2 * math.pi * a) * 0.8, math.sin(2 * math.pi * a) * 0.8, b * 5.0, seed)
    return n * math.sin(math.pi * (a + 0.5)) ** 2


def berm_profile(d, along=None, seed=1.0):
    """Earth height across the wall line (d = distance from it; along = position along the wall, which makes the
    edge wander): flat 6.5 cm over the logs' feet, gone by 18-25 cm out."""
    w = 0.215 if along is None else 0.215 + 0.035 * lumps(along, 3.0 if d > 0 else -3.0, seed + 5.0) / 0.6
    w = min(0.25, max(0.17, w))
    return 0.065 * smoothstep(w, w - 0.13, abs(d))


def section_h(x, y, seed=1.0):
    base = berm_profile(y, x, seed)
    return max(0.0, base * (1.0 + 0.45 * lumps(x, y, seed)))


def section_berm(seed=1.0):
    xs = np.linspace(-0.5, 0.5, 11)
    ys = np.array([-0.25, -0.2, -0.15, -0.1, -0.03, 0.03, 0.1, 0.15, 0.2, 0.25])
    return heightfield(xs, ys, lambda x, y: section_h(x, y, seed), sa=0.58, sb=0.34 / 0.5)


def scatter_chips(items, count, rnd, area=((-0.38, 0.38), (-0.2, 0.2)), big=0.0, hfun=None, along_x=True):
    """Wood chips and splinters knocked off, lying on the earth (kept inside `area` whole)."""
    for _ in range(count):
        x = rnd.uniform(*area[0])
        y = rnd.uniform(*area[1])
        if hfun is None and abs(y) < 0.14:
            y = math.copysign(rnd.uniform(0.15, 0.2), y if y != 0 else -1)
        h = hfun(x, y) if hfun else section_h(x, y)
        s = (rnd.uniform(0.03, 0.07 + big), rnd.uniform(0.012, 0.03 + big * 0.3), rnd.uniform(0.006, 0.012))
        yaw = rnd.uniform(-35, 35) + (0.0 if along_x else 90.0)
        items.append(chip((x, y, Z0 + h + s[2] * 0.3), s, yaw, rnd, tilt=14.0))
        if rnd.random() < 0.35:
            a = math.radians(rnd.uniform(-25, 25) + (0.0 if along_x else 90.0) + rnd.choice((0.0, 180.0)))
            d = unit((math.cos(a), math.sin(a), 0.05))
            L = rnd.uniform(0.08, 0.16)
            items.append(shard((x - d[0] * L / 2, y - d[1] * L / 2, Z0 + h + 0.004), d, L, rnd.uniform(0.01, 0.02),
                               0.005, rnd, outward=(0, 0, 1)))


# ---------------------------------------------------------------- shared layout

# Neighbouring logs overlap 1.5-2 cm (inside a section and across block seams), so their lumps never open a slit
LOG_X = (-0.375, -0.126, 0.121, 0.377)
LOG_R = (0.137, 0.131, 0.14, 0.134)
LOG_TIP = (Z0 + 2.92, Z0 + 2.99, Z0 + 2.90, Z0 + 2.96)
INTACT = (("L0", 15.0), ("L1", 190.0), ("L2", 350.0), ("L3", 168.0))  # turned near 0/180 so bows stay in Y
RAIL_Y = 0.174
RAIL_Z = (Z0 + 0.62, Z0 + 1.98)
FX_SECTION = (0.0, -0.16, Z0 + 1.5)


WIDEN = 1.035  # logs are squashed this much wider along their wall line, so lumps never open a chink


def place_log(kit, x, y, r, tip, spin, tag="log", along="X"):
    """A kit log standing at (x, y), scaled to radius r, a little wider along the wall line (`along`), and stretched
    so its actual tip reaches z = tip."""
    t = T[kit]
    s = r / t.meta["R"]
    w = m_s(WIDEN, 1.0, 1.0) if along == "X" else m_s(1.0, WIDEN, 1.0) if along == "Y" else np.eye(4)
    return place(kit, m_t(x, y, Z0) @ w @ m_r("Z", spin) @ m_s(s, s, (tip - Z0) / t.V[:, 2].max()), tag)


def rail_x(kit, x0, y, z, spin):
    return place(kit, m_t(x0, y, z) @ m_r("Y", 90) @ m_r("Z", spin), "rail")


def rail_y(kit, y0, x, z, spin):
    return place(kit, m_t(x, y0, z) @ m_r("X", -90) @ m_r("Z", spin), "rail")


def eu_x(a):
    return (math.cos(math.radians(a)), 0.0, math.sin(math.radians(a)))


def eu_y(a):
    return (0.0, math.cos(math.radians(a)), math.sin(math.radians(a)))


def front_chain(items, z, x0, x1, off, extra=None, back=False, step=0.035):
    """The path a strap pulled tight across the front (or back) of the logs takes at height z."""
    pts = section_points(items, (0, 0, z), (0, 0, 1))
    Q = pts[:, :2]
    if extra is not None:
        Q = np.vstack([Q, extra])
    ang = np.linspace(0, 2 * math.pi, 16, endpoint=False)
    H = hull2d((Q[:, None, :] + (np.c_[np.cos(ang), np.sin(ang)] * off)[None]).reshape(-1, 2))
    ir = int(np.argmax(H[:, 0]))
    C = H[:ir + 1] if not back else np.vstack([H[ir:], H[:1]])[::-1]
    C = C[np.argsort(C[:, 0])]
    ys = np.interp([x0, x1], C[:, 0], C[:, 1])
    inner = C[(C[:, 0] > x0) & (C[:, 0] < x1)]
    C = np.vstack([[x0, ys[0]], inner, [x1, ys[1]]])
    C = resample(C, step=step)
    return np.c_[C, np.full(len(C), z)]


def neighbour_logs():
    """Where a neighbouring section's outer logs stand, as points, so straps bridge the seam as one strap would."""
    return np.vstack([circle_pts(LOG_X[0] + 1.0, 0.0, LOG_R[0]), circle_pts(LOG_X[3] - 1.0, 0.0, LOG_R[3])])


def bolts_on(strap_item, origins, direction, kit="BOLT", rnd=None):
    out = []
    for o in origins:
        b = stud(kit, strap_item, o, direction, sink=0.001, rnd=rnd)
        if b is not None:
            out.append(b)
    return out


def back_strap(rail_item, z, x0, x1, y_dir=1.0, along="X", c=RAIL_Y):
    """A strap laid along the back of a rail (the rail along X at height z, its back toward +Y)."""
    pts = []
    for s in np.linspace(x0, x1, max(3, int(abs(x1 - x0) / 0.08) + 1)):
        o = (s, c + y_dir * 0.6, z) if along == "X" else (c + y_dir * 0.6, s, z)
        d = (0, -y_dir, 0) if along == "X" else (-y_dir, 0, 0)
        p, _ = hit(rail_item, o, d)
        if p is not None:
            pts.append(p)
    P = np.array(pts)
    k = 1 if along == "X" else 0
    vals = P[:, k] * y_dir
    sm = np.array([vals[max(0, i - 2):i + 3].max() for i in range(len(vals))])
    P[:, k] = sm * y_dir + y_dir * (STRAP_T / 2 + 0.0015)
    P[:, 2] = z
    out = (0.0, y_dir, 0.0) if along == "X" else (y_dir, 0.0, 0.0)
    return strap(P, (0, 0, 1), STRAP_W, STRAP_T, out)


# ---------------------------------------------------------------- section

def section(stage, banded):
    rnd = random.Random(1000 + 37 * stage + (500 if banded else 0))
    items = []
    kits = [k for k, _ in INTACT]
    spins = [s for _, s in INTACT]
    if stage >= 1:
        kits[1], spins[1] = "LA", 6.0
        kits[3], spins[3] = "LB", -8.0
    logs = [place_log(kits[i], LOG_X[i], 0.0, LOG_R[i], LOG_TIP[i], spins[i]) for i in range(4)]
    hang = None
    if stage == 1:
        logs[2] = cut(logs[2], (LOG_X[2], 0.0, LOG_TIP[2] - 0.3), (0.3, -0.25, 1.0), "jagged", seed=21, spikes=0.7)
    if stage == 2:
        lean = m_about(m_r("X", -2.4) @ m_r("Y", 0.8), (LOG_X[0], 0.0, Z0))
        logs[0] = cut(logs[0], (LOG_X[0], 0.0, LOG_TIP[0] - 0.42), (-0.35, -0.2, 1.0), "jagged", seed=22,
                      spikes=0.8).moved(lean)
        hang = cut(logs[1], (LOG_X[1], 0.0, Z0 + 0.86), (0.25, 0.1, -1.0), "jagged", seed=23, spikes=1.0)
        hang = hang.moved(m_about(m_r("Y", 1.4), (LOG_X[1], RAIL_Y, RAIL_Z[1])))
        logs[1] = cut(logs[1], (LOG_X[1], 0.0, Z0 + 0.38), (-0.3, 0.2, 1.0), "jagged", seed=24, spikes=1.3)
        logs[2] = cut(logs[2], (LOG_X[2], 0.0, Z0 + 1.45), (0.4, 0.15, 1.0), "jagged", seed=25, spikes=1.6)
    upright = logs + ([hang] if hang is not None else [])
    items += upright

    # rails, each with what is fixed to it, built in place and then moved as one when it is torn loose
    groups = []
    for j, (kit, spin) in enumerate((("RB", 40.0), ("RA", 200.0))):
        z = RAIL_Z[j]
        rail = rail_x(kit, -0.52, RAIL_Y, z, spin)
        g = [rail]
        if banded:
            st, _ = back_strap(rail, z, -0.505, 0.505)
            g.append(st)
            for x in LOG_X:
                if stage == 2 and j == 0 and x < 0.3:
                    continue
                n = stud("NUT", st, (x + 0.002, 0.8, z), (0, -1, 0), sink=0.001, rnd=rnd)
                g.append(n)
        groups.append(g)
    # the crossings: which are lashed with rope, wired or only spiked
    nailed = {(i, j) for i in range(4) for j in range(2)}
    if stage == 2:
        nailed -= {(0, 0), (1, 0), (2, 0), (2, 1), (0, 1)}
    for (i, j) in sorted(nailed):
        x = LOG_X[i] + rnd.uniform(-0.03, 0.03)
        if banded and abs(x - LOG_X[i]) < 0.03:
            x = LOG_X[i] + 0.045 * (1 if i % 2 else -1)
        for dz in ((0.012,) if not banded else (0.016,)):
            nl = stud("NAIL", groups[j][0], (x, 0.8, RAIL_Z[j] + dz * (1 if i % 2 else -1)), (0, -1, 0),
                      sink=0.003, rnd=rnd, tilt=0.12)
            groups[j].append(nl)
    if stage == 2:
        # the lower rail torn off at its left end and hanging, the upper one pushed back at the left
        M0 = m_t(0.0, 0.03, 0.0) @ m_about(m_r("Y", -33.0), (0.4, RAIL_Y, RAIL_Z[0]))
        groups[0] = [it.moved(M0) for it in groups[0] if it is not None]
        M1 = m_about(m_r("Z", -5.5), (0.42, RAIL_Y, RAIL_Z[1]))
        groups[1] = [it.moved(M1) for it in groups[1] if it is not None]
        # nails pulled half out of the logs where the lower rail was
        for i in (0, 2):
            p, n = hit(logs[i], (LOG_X[i] + 0.02, 0.6, RAIL_Z[0] + 0.01), (0, -1, 0))
            if p is not None:
                d = unit(n + np.array((0.2, 0.0, -0.25)))
                items.append(tube([p - d * 0.01, p + d * 0.05], 0.0035, 4, "STRAP", tag="iron"))
                items.append(place("NAIL", m_t(*(p + d * 0.05)) @ m_align(d), "iron"))
    for g in groups:
        items += [it for it in g if it is not None]
    rails = [g[0] for g in groups]

    # lashings and wire
    def cross_c(i, j):
        return np.array((LOG_X[i], RAIL_Y * 0.5, RAIL_Z[j]))

    # Rope on the inner logs only (a loop round an outer log would pass through the next block's log); the
    # banded section trades the wire and one lashing for its iron
    if stage == 0:
        for i, j in ((1, 1), (1, 0)) + (() if banded else ((2, 1),)):
            items += lashing([logs[i], rails[j]], cross_c(i, j), eu_x, (0, 1, 0), rnd)[0]
        if not banded:
            items += wire_wrap([logs[2], rails[0]], cross_c(2, 0), eu_x, (0, 1, 0), rnd)
    elif stage == 1:
        for i, j in ((2, 1),) if banded else ((2, 1), (1, 0)):
            items += lashing([logs[i], rails[j]], cross_c(i, j), eu_x, (0, 1, 0), rnd)[0]
        if not banded:
            items += wire_wrap([logs[2], rails[0]], cross_c(2, 0), eu_x, (0, 1, 0), rnd)
        # the frayed, loose lashing round the split log: one loop slack and slipped down, the other snapped with
        # its ends hanging
        lo, paths = lashing([logs[1], rails[1]], cross_c(1, 1), eu_x, (0, 1, 0), rnd, alphas=(38.0,), loose=0.012,
                            drop=0.03, tails=False)
        items += lo
        x1, z1 = LOG_X[1], RAIL_Z[1]
        items += dangling(rails[1], (x1 + 0.035, 0.8, z1 + 0.03), (0, -1, 0), rnd, 0.3, (0.02, 0.012))
        items += dangling(logs[1], (x1 - 0.05, -0.8, z1 + 0.05), (0, 1, 0), rnd, 0.28, (-0.01, -0.012))
    else:
        if hang is not None:
            items += lashing([hang, rails[1]], cross_c(1, 1), eu_x, (0, 1, 0), rnd, alphas=(36.0,), tails=False)[0]
        # log 2 snapped below the upper rail: its lashing torn, ends hanging from the rail; the lower lashing
        # round log 1 went with the log, a torn end left round the hanging rail
        x2, z1 = LOG_X[2], RAIL_Z[1]
        items += dangling(rails[1], (x2 + 0.04, 0.8, z1 + 0.03), (0, -1, 0), rnd, 0.38, (0.015, 0.015))
        items += dangling(rails[1], (x2 - 0.05, 0.8, z1 - 0.02), (0, -1, 0), rnd, 0.22, (-0.01, 0.015))
        items += dangling(rails[0], (LOG_X[1], 0.8, RAIL_Z[0] - 0.29), (0, -1, 0), rnd, 0.2, (0.02, 0.01))

    # iron bands across the front
    if banded:
        extra = neighbour_logs()
        for j, z in enumerate(RAIL_Z):
            src = [it for it in upright]
            path = front_chain(src, z, -0.505, 0.505, STRAP_T / 2 + 0.0015, extra=extra)
            cuts = None
            if stage == 1 and j == 1:
                # bowed out between the middle logs where a bolt has sheared
                bump = np.exp(-((path[:, 0] - 0.0) / 0.13) ** 2)
                path[:, 1] -= 0.035 * bump
            if stage == 2 and j == 0:
                # pushed in where log 1 is gone
                bump = np.exp(-((path[:, 0] - LOG_X[1]) / 0.12) ** 2)
                path[:, 1] += 0.06 * bump
            if stage == 2 and j == 1:
                cuts = 0.0
            pieces = [path] if cuts is None else [path[path[:, 0] < cuts - 0.02], path[path[:, 0] > cuts + 0.04]]
            for k, pp in enumerate(pieces):
                pp = pp.copy()
                if cuts is not None and k == 1:
                    # the torn right half: nothing behind it any more where log 2 snapped, curling out
                    keep = pp[:, 0] > 0.26
                    free = pp[~keep]
                    t = (0.26 - free[:, 0]) / 0.22
                    free[:, 1] = pp[keep][0, 1] - 0.1 * t ** 1.6
                    free[:, 2] = z - 0.06 * t ** 2
                    pp = np.vstack([free, pp[keep]])
                if cuts is not None and k == 0:
                    t = np.clip((pp[:, 0] - (cuts - 0.14)) / 0.12, 0, 1)
                    pp[:, 1] -= 0.05 * t ** 2
                    pp[:, 2] += 0.03 * t ** 2
                st, _ = strap(pp, (0, 0, 1), STRAP_W, STRAP_T, (0, -1, 0))
                items.append(st)
                for i, x in enumerate(LOG_X):
                    if stage == 1 and j == 1 and i == 2:
                        continue
                    if stage == 2 and ((j == 0 and i == 1) or (j == 1 and i == 2)):
                        continue
                    if pp[:, 0].min() <= x <= pp[:, 0].max():
                        items += bolts_on(st, [(x + 0.002, -0.8, z)], (0, 1, 0), rnd=rnd)

    # debris and the earth
    if stage >= 1:
        scatter_chips(items, 4 if stage == 1 else 9, rnd, big=0.0 if stage == 1 else 0.03)
    items.append(section_berm())
    return items


# ---------------------------------------------------------------- corner

POST_R = 0.19
RUN_R = 0.162
RUN_C = 0.34
RUN_OFF = -0.026
FX_CORNER = (0.0, -0.215, Z0 + 1.5)


def corner_h(x, y, seed=2.0):
    fx = smoothstep(-0.27, -0.08, x)
    fy = smoothstep(-0.27, -0.08, y)
    a = berm_profile(y, x, seed) * fx * (1.0 + 0.45 * lumps(x, y, seed))
    b = berm_profile(x, -y, seed) * fy * (1.0 + 0.45 * lumps(-y, x, seed))
    return max(0.0, a, b)


def corner_berm():
    xs = np.linspace(-0.25, 0.5, 11)
    ys = np.linspace(-0.25, 0.5, 11)
    return heightfield(xs, ys, corner_h, sa=0.58 / 0.75, sb=0.34 / 0.75)


def corner(stage, banded):
    rnd = random.Random(2000 + 37 * stage + (500 if banded else 0))
    items = []
    post = place_log("P0" if stage == 0 else "P1", 0.0, 0.0, POST_R, Z0 + 3.0, 70.0 if stage == 0 else 0.0,
                     along=None)
    xr = place_log("L3", RUN_C, RUN_OFF, RUN_R, Z0 + 2.94, 190.0)
    yr = place_log("L1" if stage < 2 else "LA", RUN_OFF, RUN_C, RUN_R, Z0 + 2.97, 100.0 if stage < 2 else -90.0,
                   along="Y")
    hang = None
    if stage == 1:
        xr = cut(xr, (RUN_C, RUN_OFF, Z0 + 2.62), (-0.3, -0.3, 1.0), "jagged", seed=31, spikes=0.7)
    if stage == 2:
        post = cut(post, (0.0, 0.0, Z0 + 2.3), (-0.3, -0.35, 1.0), "jagged", seed=32, spikes=1.2)
        xr = cut(xr, (RUN_C, RUN_OFF, Z0 + 1.15), (0.3, -0.2, 1.0), "jagged", seed=33, spikes=1.5)
        hang = cut(yr, (RUN_OFF, RUN_C, Z0 + 0.95), (0.1, 0.3, -1.0), "jagged", seed=34, spikes=1.0)
        hang = hang.moved(m_about(m_r("X", -1.3), (RAIL_Y, RUN_C, RAIL_Z[1])))
        yr = cut(yr, (RUN_OFF, RUN_C, Z0 + 0.42), (-0.2, 0.3, 1.0), "jagged", seed=35, spikes=1.3)
    upright = [post, xr, yr] + ([hang] if hang is not None else [])
    items += upright

    # rails: the Y rails run past the post's +X side; the X rails butt into them
    groups = []
    for j, z in enumerate(RAIL_Z):
        ry = cut(rail_y("RB" if j == 0 else "RA", -0.52, RAIL_Y, z, 60.0 + 90 * j), (RAIL_Y, 0.05, z), (0, -1, 0),
                 "end", seed=40 + j)
        rx = cut(rail_x("RA" if j == 0 else "RB", -0.52, RAIL_Y, z, 150.0 + 70 * j), (RAIL_Y + 0.05, RAIL_Y, z),
                 (-1, 0, 0), "end", seed=42 + j)
        gx, gy = [rx], [ry]
        if banded:
            sx, _ = back_strap(rx, z, RAIL_Y + 0.07, 0.505)
            sy, _ = back_strap(ry, z, 0.25, 0.505, along="Y")
            gx.append(sx)
            gy.append(sy)
            gx.append(stud("NUT", sx, (RUN_C, 0.8, z), (0, -1, 0), sink=0.001, rnd=rnd))
            gy.append(stud("NUT", sy, (0.8, RUN_C, z), (-1, 0, 0), sink=0.001, rnd=rnd))
        gx.append(stud("NAIL", rx, (RUN_C + 0.05, 0.8, z + 0.012), (0, -1, 0), sink=0.003, rnd=rnd, tilt=0.12))
        gy.append(stud("NAIL", ry, (0.8, RUN_C - 0.05, z - 0.012), (-1, 0, 0), sink=0.003, rnd=rnd, tilt=0.12))
        gy.append(stud("NAIL", ry, (0.8, 0.07, z + 0.01), (-1, 0, 0), sink=0.003, rnd=rnd, tilt=0.12))
        groups.append((gx, gy))
    if stage == 2:
        # the upper X rail went with its log; the lower Y rail hangs from the seam end
        groups[1] = ([], groups[1][1])
        gx, gy = groups[0]
        My = m_t(0.03, -0.045, 0.0) @ m_about(m_r("X", 34.0), (RAIL_Y, 0.52, RAIL_Z[0]))
        groups[0] = (gx, [it.moved(My) for it in gy if it is not None])
    for gx, gy in groups:
        items += [it for it in gx + gy if it is not None]

    # rope binding the run logs to the post (one turn fewer where iron bands take the load)
    def bind(run, z, axis, alphas=(7.0, -5.0), **kw):
        c = (np.array((RUN_C / 2, RUN_OFF / 2, z)) if axis == "X" else np.array((RUN_OFF / 2, RUN_C / 2, z)))
        if banded and len(alphas) > 1:
            alphas = alphas[:1]
        return lashing([post, run], c, eu_x if axis == "X" else eu_y, (0, 1, 0) if axis == "X" else (1, 0, 0), rnd,
                       alphas=alphas, n=22, gap=0.026, **kw)[0]

    if stage == 0:
        items += bind(xr, Z0 + 0.95, "X") + bind(xr, Z0 + 2.15, "X")
        items += bind(yr, Z0 + 1.02, "Y") + bind(yr, Z0 + 2.2, "Y")
    elif stage == 1:
        items += bind(xr, Z0 + 0.95, "X") + bind(xr, Z0 + 2.15, "X") + bind(yr, Z0 + 1.02, "Y")
        items += bind(yr, Z0 + 2.2, "Y", alphas=(6.0,), loose=0.007, drop=0.035, tails=False)
        items += rope_end([(-0.13, 0.16, Z0 + 2.24), (-0.15, 0.2, Z0 + 2.12), (-0.155, 0.22, Z0 + 1.98),
                           (-0.15, 0.22, Z0 + 1.88)], rnd)
    else:
        items += bind(xr, Z0 + 0.95, "X")
        if hang is not None:
            items += bind(hang, Z0 + 2.2, "Y", alphas=(6.0,))
        items += rope_end([(0.08, -0.205, Z0 + 2.16), (0.12, -0.215, Z0 + 2.05), (0.13, -0.22, Z0 + 1.9),
                           (0.125, -0.215, Z0 + 1.78)], rnd)
        items += rope_end([(0.17, -0.12, Z0 + 2.13), (0.2, -0.13, Z0 + 2.0), (0.21, -0.135, Z0 + 1.87)], rnd)

    # bands round the outside of the corner
    if banded:
        virt = np.vstack([circle_pts(LOG_X[0] + 1.0, 0.0, LOG_R[0]), circle_pts(0.0, 1.0 - LOG_X[3], LOG_R[3])])
        for j, z in enumerate(RAIL_Z):
            pts = section_points(upright, (0, 0, z), (0, 0, 1))[:, :2]
            Q = np.vstack([pts, virt])
            ang = np.linspace(0, 2 * math.pi, 16, endpoint=False)
            H = hull2d((Q[:, None, :] + (np.c_[np.cos(ang), np.sin(ang)] * (STRAP_T / 2 + 0.0015))[None])
                       .reshape(-1, 2))
            # walk the hull clockwise from the +X end of the front round to the +Y end of the -X side
            i0 = int(np.argmin(np.abs(H[:, 0] - 0.62) + (H[:, 1] > 0) * 9))
            i1 = int(np.argmin(np.abs(H[:, 1] - 0.62) + (H[:, 0] > 0) * 9))
            seq, k = [], i0
            while True:
                seq.append(H[k])
                if k == i1:
                    break
                k = (k - 1) % len(H)
            C = np.array(seq)
            # clip at the block's +X and +Y edges
            C = C[(C[:, 0] <= 0.506) & (C[:, 1] <= 0.506)]
            C = resample(C, step=0.035)
            path = np.c_[C, np.full(len(C), z)]
            if stage == 1 and j == 0:
                d = np.linalg.norm(C - np.array((-0.14, -0.14)), axis=1)
                path[:, 0] -= 0.03 * np.exp(-(d / 0.12) ** 2)
                path[:, 1] -= 0.03 * np.exp(-(d / 0.12) ** 2)
            if stage == 2 and j == 1:
                # torn at the post: the X side has nothing behind it any more and droops out
                front = path[:, 1] < -0.05
                xp = path[front & (path[:, 0] > 0.03) & (path[:, 0] < 0.36)].copy()
                rest = path[~(front & (path[:, 0] > -0.005))]
                t = np.clip((xp[:, 0] - 0.03) / 0.33, 0, 1)
                xp[:, 1] -= 0.06 * t ** 1.5
                xp[:, 2] -= 0.2 * t ** 1.8
                parts = [rest, xp]
            else:
                parts = [path]
            for pp in parts:
                if len(pp) < 2:
                    continue
                st, _ = strap(pp, (0, 0, 1), STRAP_W, STRAP_T, lambda p: np.array((p[0] - 0.2, p[1] - 0.2, 0.0)))
                items.append(st)
                items += bolts_on(st, [(-0.8, -0.8, z)], (1, 1, 0), rnd=rnd)
                items += bolts_on(st, [(RUN_C, -0.8, z)], (0, 1, 0), rnd=rnd)
                items += bolts_on(st, [(-0.8, RUN_C, z)], (1, 0, 0), rnd=rnd)

    if stage >= 1:
        scatter_chips(items, 3 if stage == 1 else 7, rnd, area=((0.24, 0.4), (-0.2, -0.17)), hfun=corner_h)
        scatter_chips(items, 2 if stage == 1 else 4, rnd, area=((-0.2, -0.17), (0.24, 0.4)), hfun=corner_h,
                      along_x=False)
    items.append(corner_berm())
    return items


# ---------------------------------------------------------------- stumps

def stumps():
    rnd = random.Random(3000)
    items = []
    hs = (0.74, 0.97, 0.63, 0.86)
    logs = []
    for i, (kit, spin) in enumerate(INTACT):
        it = place_log(kit, LOG_X[i], 0.0, LOG_R[i], LOG_TIP[i], spin)
        n = unit((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.35, 0.2), 1.0))
        it = cut(it, (LOG_X[i], 0.0, Z0 + hs[i]), n, "jagged", seed=50 + i, spikes=1.5)
        tilt = m_about(m_r("X", rnd.uniform(-2.5, 1.0)) @ m_r("Y", rnd.uniform(-1.5, 1.5)), (LOG_X[i], 0.0, Z0))
        logs.append(it.moved(tilt))
    items += logs
    # the lower rail, snapped: its left piece still spiked to stumps 0 and 1, the right piece sagging off stump 3
    z = RAIL_Z[0]
    rail = rail_x("RB", -0.52, RAIL_Y, z, 40.0)
    left = cut(rail, (-0.03, RAIL_Y, z), (1, 0, 0), "jagged", seed=60, spikes=0.6)
    right = cut(rail, (0.05, RAIL_Y, z), (-1, 0.2, 0.1), "jagged", seed=61, spikes=0.8)
    for i in (0, 1):
        items.append(stud("NAIL", left, (LOG_X[i] + 0.02, 0.8, z + 0.012), (0, -1, 0), sink=0.003, rnd=rnd,
                          tilt=0.12))
    gr = [right, stud("NAIL", right, (LOG_X[3] - 0.02, 0.8, z - 0.01), (0, -1, 0), sink=0.003, rnd=rnd, tilt=0.12)]
    Mr = m_about(m_r("Y", -17.0), (LOG_X[3], RAIL_Y, z))
    items += [left] + [it.moved(Mr) for it in gr if it is not None]
    # the lower lashing at stump 1, slack, one end torn
    items += lashing([logs[1], left], np.array((LOG_X[1], RAIL_Y * 0.5, z)), eu_x, (0, 1, 0), rnd, alphas=(38.0,),
                     loose=0.008, drop=0.015, tails=False)[0]
    x1 = LOG_X[1]
    items += rope_end([(x1 - 0.04, RAIL_Y + 0.06, z - 0.03), (x1 - 0.05, RAIL_Y + 0.08, z - 0.15),
                       (x1 - 0.045, RAIL_Y + 0.09, z - 0.3), (x1 - 0.03, RAIL_Y + 0.1, z - 0.42)], rnd)
    # a length of torn rope lying on the earth behind
    pts = []
    for t in np.linspace(0, 1, 9):
        x = -0.35 + 0.6 * t
        y = 0.3 + 0.08 * math.sin(t * 5.0)
        pts.append((x, y, Z0 + 0.012 + berm_profile(y) * 0.9))
    items += rope_end(pts, rnd)
    items += fray(pts[0], np.asarray(pts[0]) - np.asarray(pts[1]), rnd)
    # the fallen point of log 2, lying in front
    top = place_log("L2", 0.0, 0.0, LOG_R[2], LOG_TIP[2], 250.0)
    top = cut(top, (0.0, 0.0, LOG_TIP[2] - 0.92), (0.25, 0.3, -1.0), "jagged", seed=62, spikes=0.6, shards=1)
    M = m_t(-0.05, -0.3, 0.0) @ m_r("Z", 172.0) @ m_r("Y", 92.0) @ m_t(0.0, 0.0, -(LOG_TIP[2] - 0.47))
    top = top.moved(M)
    top = top.moved(m_t(0.0, 0.0, Z0 - 0.012 - top.V[:, 2].min()))
    items.append(top)
    # a broken piece of the upper rail on the earth behind
    up = rail_x("RA", -0.52, 0.0, 0.0, 200.0)
    up = cut(up, (0.2, 0.0, 0.0), (1, 0.15, 0.1), "jagged", seed=63, spikes=0.9)
    up = up.moved(m_t(0.05, 0.4, Z0 + 0.05) @ m_r("Z", 10.0) @ m_r("Y", -3.0))
    items.append(up)
    scatter_chips(items, 16, rnd, big=0.04)
    items.append(section_berm())
    return items


# ---------------------------------------------------------------- gate

GATE_POST_X, GATE_POST_R = 1.36, 0.165
HINGE_X = GATE_POST_X - GATE_POST_R
HINGE_Y = -0.156
HINGE_Z = (Z0 + 0.45, Z0 + 2.0)
LEAF_R = (0.125, 0.123, 0.126, 0.123, 0.1245)
LEAF_TIP = (Z0 + 2.82, Z0 + 2.88, Z0 + 2.8, Z0 + 2.9, Z0 + 2.85)
LEAF_RAIL_Y = 0.165
LEAF_RAIL_Z = (Z0 + 0.38, Z0 + 2.03)


def leaf_xs():
    """Log centres from the hinge side in. The hinge-side log bears on its post when closed (no daylight down the
    hinge side); every point of the leaf moves away from the post as it opens."""
    xs = [HINGE_X + 0.004 - LEAF_R[0]]
    for i in range(1, 5):
        xs.append(xs[-1] - (LEAF_R[i - 1] + LEAF_R[i] - 0.012))
    return xs


def gate_frame():
    rnd = random.Random(4000)
    items = []
    for sx, spin, tip in ((-1, 140.0, Z0 + 2.97), (1, 300.0, Z0 + 3.0)):
        post = place_log("P0", sx * GATE_POST_X, 0.0, GATE_POST_R, tip, spin)
        items.append(post)
        for zh in HINGE_Z:
            yaw = 45.0 if sx > 0 else 135.0
            items.append(place("PINTLE", m_t(sx * HINGE_X, HINGE_Y, zh) @ m_r("Z", yaw), "iron"))

        def h(x, y, sx=sx):
            d = math.hypot(x - sx * GATE_POST_X, y)
            base = 0.075 * smoothstep(0.32, 0.12, d) * (1.0 + 0.4 * pnoise(x * 4, y * 4, 0.0, 7.0))
            return max(0.0, base) if abs(x) >= 1.25 else 0.0
        x0, x1 = (1.24, 1.53) if sx > 0 else (-1.53, -1.24)
        items.append(heightfield(np.linspace(x0, x1, 7), np.linspace(-0.3, 0.3, 9), h, sa=1.0, sb=0.6))
    return items


def gate_leaf(sx, kits):
    rnd = random.Random(5000 + (sx > 0))
    items = []
    logs = []
    for i, x in enumerate(leaf_xs()):
        kit, spin = kits[i]
        it = place_log(kit, sx * x, 0.0, LEAF_R[i], LEAF_TIP[i], spin)
        it = cut(it, (sx * x, 0.0, Z0 + 0.03), (0, 0, -1), "end", seed=70 + i)
        logs.append(it)
    items += logs
    rails = []
    for j, z in enumerate(LEAF_RAIL_Z):
        r = rail_x("RG", 0.0 if sx > 0 else -1.24, LEAF_RAIL_Y, z, 30.0 + 140 * j)
        r = cut(r, (sx * 0.035, LEAF_RAIL_Y, z), (-sx, 0, 0), "end", seed=80 + j)
        r = cut(r, (sx * (HINGE_X - 0.055), LEAF_RAIL_Y, z), (sx, 0, 0), "end", seed=82 + j)
        rails.append(r)
    a = np.array((sx * (HINGE_X - 0.12), LEAF_RAIL_Y, LEAF_RAIL_Z[0] + 0.035))
    b = np.array((sx * 0.13, LEAF_RAIL_Y, LEAF_RAIL_Z[1] - 0.035))
    d = b - a
    L = np.linalg.norm(d)
    brace = place("RD", m_t(*a) @ m_align(d) @ m_r("Z", 77.0) @ m_s(1, 1, L / T["RD"].meta["length"]), "rail")
    items += rails + [brace]
    xs = leaf_xs()
    for i, x in enumerate(xs):
        for j, z in enumerate(LEAF_RAIL_Z):
            if (i + j) % 2 == 0:
                items.append(stud("NAIL", rails[j], (sx * x + rnd.uniform(-0.03, 0.03), 0.8,
                                                     z + rnd.uniform(-0.012, 0.012)), (0, -1, 0), sink=0.003, rnd=rnd,
                                  tilt=0.12))
        zb = a[2] + (sx * x - a[0]) / d[0] * d[2] if abs(d[0]) > 1e-6 else None
        if i % 2 == 1 and zb is not None and LEAF_RAIL_Z[0] + 0.12 < zb < LEAF_RAIL_Z[1] - 0.12:
            items.append(stud("NAIL", brace, (sx * x, 0.8, zb), (0, -1, 0), sink=0.003, rnd=rnd, tilt=0.12))
    # strap hinges on the front, rolled round the pintles
    for zh in HINGE_Z:
        C = front_chain(logs, zh, 0.4, HINGE_X - 0.11, 0.0055) if sx > 0 else \
            front_chain(logs, zh, -(HINGE_X - 0.11), -0.4, 0.0055)
        end = np.array((sx * (HINGE_X - 0.022), HINGE_Y + 0.009, zh))
        C = np.vstack([C, end]) if sx > 0 else np.vstack([end, C])
        st, _ = strap(C, (0, 0, 1), 0.06, 0.008, (0, -1, 0))
        items.append(st)
        items.append(place("BARREL", m_t(sx * HINGE_X, HINGE_Y, zh), "iron"))
        for x in xs[:2]:
            items += bolts_on(st, [(sx * x, -0.8, zh)], (0, 1, 0), rnd=rnd)
        # the strap's tapered tail end, nailed
        items += bolts_on(st, [(sx * 0.47, -0.8, zh)], (0, 1, 0), kit="NAIL", rnd=rnd)
    # the drop-bar bracket on the back near the meeting edge
    zb = Z0 + 1.25
    xb = sx * 0.21
    p, _ = hit(merge(logs), (xb, 0.8, zb), (0, -1, 0))
    yb = (p[1] if p is not None else 0.12) + 0.0055
    U = [(xb, yb, zb + 0.06), (xb, yb, zb - 0.03), (xb, yb + 0.012, zb - 0.052), (xb, yb + 0.04, zb - 0.06),
         (xb, yb + 0.08, zb - 0.06), (xb, yb + 0.106, zb - 0.045), (xb, yb + 0.112, zb - 0.02),
         (xb, yb + 0.112, zb + 0.07)]
    br, _ = strap(resample(U, step=0.02), (1, 0, 0), 0.05, 0.008, lambda q: np.array((0.0, q[1] - (yb + 0.05),
                                                                                      q[2] - (zb + 0.01))) * -1)
    items.append(br)
    items += bolts_on(br, [(xb, yb + 0.05, zb + 0.035)], (0, -1, 0), kit="NUT", rnd=rnd)
    # one rope lashing near the top of the meeting edge (the rail's free end to the last log)
    items += lashing([logs[4], rails[1]], np.array((sx * xs[4], LEAF_RAIL_Y * 0.5, LEAF_RAIL_Z[1])), eu_x,
                     (0, 1, 0), rnd, alphas=(40.0,), tails=False)[0]
    return items


# ---------------------------------------------------------------- building meshes, reports, export

MATERIAL = None


def finish_mesh(name, items, limits=None):
    items = [it for it in items if it is not None and len(it.F)]
    if limits is not None:
        (x0, x1), (y0, y1) = limits
        for it in items:
            lo, hi = it.V.min(0), it.V.max(0)
            if lo[0] < x0 or hi[0] > x1 or lo[1] < y0 or hi[1] > y1:
                log("  %s: a %s part reaches x %.3f..%.3f y %.3f..%.3f" % (name, it.tag, lo[0], hi[0], lo[1], hi[1]))
    it = merge(items)
    V = it.V.copy()
    V[:, 2] = np.maximum(V[:, 2], Z0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], it.F.tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", it.UV.reshape(-1).astype(np.float32))
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(SHARP))
    me.materials.append(MATERIAL)
    obj = tk.link(bpy.data.objects.new(name, me))
    by = {}
    for x in items:
        by[x.tag] = by.get(x.tag, 0) + len(x.F)
    return obj, by


def stats(objs):
    lo, hi, tris = np.full(3, 1e9), np.full(3, -1e9), 0
    for o in objs:
        co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
        lo, hi = np.minimum(lo, co.min(0)), np.maximum(hi, co.max(0))
        tris += len(o.data.polygons)
    return lo, hi, tris


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


def lineup(entries, cam, path, res=(1800, 1100), samples=96, show=()):
    """entries: (object, (x, y), z rotation in degrees). Renders copies of them, everything else in ALL hidden."""
    for o in ALL:
        o.hide_render = o not in show
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


def albedo_stats(paths):
    a = image_array(paths["albedo"])[..., :3]
    m = a.max(axis=2) > 0.01
    px = a[m]
    log("albedo (sRGB) mean %s p10 %s p90 %s | vanilla wood gate mean (0.29, 0.24, 0.20) p10 (0.16, 0.13, 0.10) "
        "p90 (0.46, 0.38, 0.32)" % (px.mean(0).round(3), np.percentile(px, 10, axis=0).round(3),
                                    np.percentile(px, 90, axis=0).round(3)))
    r = image_array(paths["rmom"])
    log("roughness mean %.3f (vanilla 0.81), metallic mean %.3f, AO mean %.3f" % (r[..., 0][m].mean(),
                                                                                r[..., 1][m].mean(),
                                                                                r[..., 2][m].mean()))


# ================================================================ main

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__", "palisade_kit.npz")


def save_templates(path):
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
    return {n: Tpl(n, z[n + "|V"], z[n + "|F"], z[n + "|UV"], m) for n, m in meta.items()}


tk.reset_scene()
if MODE == "reuse" and os.path.exists(CACHE):
    # assemble from the last bake (debugging the pieces without baking again)
    T = load_templates(CACHE)
    PATHS = {k: os.path.join(ASSETS, "%s_%s.png" % (MAT_NAME, s)) for k, s in (("albedo", "Albedo"),
                                                                               ("normal", "Normal"),
                                                                               ("rmom", "RMOM"))}
else:
    MATS = build_kit()
    log("kit built: %d parts" % len(KIT))
    if MODE == "kit":
        kit_preview(MATS)
        log("kit preview done")
        sys.exit(0)
    bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
    kit, PATHS = bake_kit()
    T = extract_templates(kit)
    bpy.data.objects.remove(kit)
    save_templates(CACHE)
MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
log("baked", PATHS)
albedo_stats(PATHS)
swatch_maps()

REPORT = []
BUILT = {}
LIM_SECTION = ((-0.53, 0.53), (-0.25, 0.35))
LIM_CORNER = ((-0.27, 0.53), (-0.27, 0.53))
for key, fn, lim in (("Section", lambda s: section(s, False), LIM_SECTION),
                     ("SectionBanded", lambda s: section(s, True), LIM_SECTION),
                     ("Corner", lambda s: corner(s, False), LIM_CORNER),
                     ("CornerBanded", lambda s: corner(s, True), LIM_CORNER)):
    meshes = []
    for s in range(3):
        obj, by = finish_mesh("%s_DMG%d" % (key, s), fn(s), lim)
        meshes.append(obj)
        log("%s DMG%d: %d tris %s" % (key, s, len(obj.data.polygons), by))
    BUILT[key] = meshes
    ALL.extend(meshes)
obj, by = finish_mesh("Stumps_DMG0", stumps(), ((-0.53, 0.53), (-0.5, 0.5)))
BUILT["Stumps"] = [obj]
ALL.append(obj)
log("Stumps: %d tris %s" % (len(obj.data.polygons), by))

frame, _ = finish_mesh("GateFrame", gate_frame())
lk = (("L2", 15.0), ("L0", 190.0), ("L3", 170.0), ("L1", 355.0), ("L0", 185.0))  # turned near 0/180: bows in Y
rk = (("L1", 200.0), ("L3", 20.0), ("L0", 175.0), ("L2", 345.0), ("L3", 10.0))
left, lby = finish_mesh("GateLeft", gate_leaf(-1, lk))
right, rby = finish_mesh("GateRight", gate_leaf(1, rk))
log("gate leaves: left %d tris %s, right %d tris %s, frame %d" % (len(left.data.polygons), lby,
                                                                  len(right.data.polygons), rby,
                                                                  len(frame.data.polygons)))
tk.mark_part(left, "LeftLeaf")
tk.mark_part(right, "RightLeaf")
gate = tk.join([frame, left, right], "Frame")
HINGES = {"LeftLeaf": (-HINGE_X, HINGE_Y, Z0), "RightLeaf": (HINGE_X, HINGE_Y, Z0)}
leaf_l = tk.split_part(gate, "LeftLeaf", HINGES["LeftLeaf"])
leaf_r = tk.split_part(gate, "RightLeaf", HINGES["RightLeaf"])
for o in (gate, leaf_l, leaf_r):
    if o.data.attributes.get("trap_part") is not None:
        o.data.attributes.remove(o.data.attributes["trap_part"])
GATE = [gate, leaf_l, leaf_r]
ALL.extend(GATE)


def swing_check(leaf, sx):
    """How far the leaf reaches into its post's (nominal, widened) cylinder at 0, 5, 10, 20, 45 and 90 degrees
    open: positive = overlap, negative = clearance."""
    bpy.context.view_layer.update()
    V = np.array([(leaf.matrix_world @ v.co)[:] for v in leaf.data.vertices])
    piv = np.array(leaf.matrix_world.translation)
    out = []
    for deg in (0, 5, 10, 20, 45, 90):
        a = math.radians(deg) * sx
        d = V[:, :2] - piv[:2]
        Rr = np.c_[d[:, 0] * math.cos(a) - d[:, 1] * math.sin(a), d[:, 0] * math.sin(a) + d[:, 1] * math.cos(a)]
        Rr += piv[:2]
        out.append("%d deg %+.3f" % (deg, float((GATE_POST_R * WIDEN - np.hypot(Rr[:, 0] - sx * GATE_POST_X,
                                                                              Rr[:, 1])).max())))
    return ", ".join(out)


log("swing check, leaf into its post (+ overlap / - clear): left %s | right %s" % (swing_check(leaf_l, -1),
                                                                                  swing_check(leaf_r, 1)))

def gap_check(placed, axis, s0, s1, z1=Z0 + 2.2, skip=()):
    """Rays straight through the wall (along `axis`) on a 6 mm x 5 cm grid between s0 and s1, from just above the
    earth to z1 (below the points): returns how many see daylight. placed: (object, location, z rotation)."""
    V, F, off = [], [], 0
    for obj, loc, rz in placed:
        M = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ obj.matrix_world
        V += [(M @ v.co)[:] for v in obj.data.vertices]
        F += [tuple(i + off for i in p.vertices) for p in obj.data.polygons]
        off += len(obj.data.vertices)
    bvh = BVHTree.FromPolygons(V, F)
    misses, where = 0, []
    for s in np.arange(s0 + 0.003, s1, 0.006):
        if any(a <= s <= b for a, b in skip):
            continue
        for z in np.arange(Z0 + 0.12, z1, 0.05):
            o = Vector((s, -1.5, z)) if axis == "Y" else Vector((-1.5, s, z))
            d = Vector((0, 1, 0)) if axis == "Y" else Vector((1, 0, 0))
            if bvh.ray_cast(o, d, 3.0)[0] is None:
                misses += 1
                where.append((round(float(s), 3), round(float(z), 2)))
    return misses, where[:6]


S0_, B0_, C0_ = BUILT["Section"][0], BUILT["SectionBanded"][0], BUILT["Corner"][0]
for label, placed, axis, s0, s1, skip in (
        ("section", [(S0_, (0, 0, 0), 0)], "Y", -0.5, 0.5, ()),
        ("banded section", [(B0_, (0, 0, 0), 0)], "Y", -0.5, 0.5, ()),
        ("section|section seam", [(S0_, (0, 0, 0), 0), (S0_, (1, 0, 0), 0)], "Y", 0.35, 0.65, ()),
        ("section|banded seam", [(S0_, (0, 0, 0), 0), (B0_, (1, 0, 0), 0)], "Y", 0.35, 0.65, ()),
        ("section|turned section seam", [(S0_, (0, 0, 0), 0), (S0_, (1, 0, 0), 180)], "Y", 0.35, 0.65, ()),
        ("corner X arm + section", [(C0_, (0, 0, 0), 0), (S0_, (1, 0, 0), 0)], "Y", -0.15, 0.7, ()),
        ("corner Y arm + section", [(C0_, (0, 0, 0), 0), (S0_, (0, 1, 0), -90)], "X", -0.15, 0.7, ()),
        ("gate (closed) between sections", [(gate, (0, 0, 0), 0), (leaf_l, (0, 0, 0), 0), (leaf_r, (0, 0, 0), 0),
                                            (S0_, (-2, 0, 0), 0), (S0_, (2, 0, 0), 0)], "Y", -1.7, 1.7,
         ((-0.03, 0.03),))):
    m, where = gap_check(placed, axis, s0, s1, skip=skip)
    log("see-through check, %s: %d rays get through %s" % (label, m, where if m else ""))

FX = {"Section": FX_SECTION, "SectionBanded": FX_SECTION, "Corner": FX_CORNER, "CornerBanded": FX_CORNER}
for key in ("Section", "SectionBanded", "Corner", "CornerBanded", "Stumps"):
    meshes = BUILT[key]
    export_piece("Palisade%s.fbx" % key, meshes, FX.get(key))
    for i, m in enumerate(meshes):
        lo, hi, tris = stats([m])
        REPORT.append("Palisade%s.fbx DMG%d: %d tris, bounds %s .. %s" % (key, i, tris, lo.round(3), hi.round(3)))
    if key in FX:
        REPORT.append("Palisade%s.fbx FX at %s" % (key, FX[key]))
tk.export_fbx(GATE, os.path.join(ASSETS, "PalisadeGate.fbx"))
for o in GATE:
    lo, hi, tris = stats([o])
    REPORT.append("PalisadeGate.fbx %s: %d tris, bounds %s .. %s, origin %s, parent %s" % (
        o.name, tris, lo.round(3), hi.round(3), tuple(round(c, 3) for c in o.matrix_world.translation),
        o.parent.name if o.parent else None))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
stage()
for key, name in (("Section", "section"), ("SectionBanded", "section_banded"), ("Corner", "corner"),
                  ("CornerBanded", "corner_banded")):
    m = BUILT[key]
    ents = [(m[0], (-1.5, 0.0), 0), (m[1], (0.0, 0.0), 0), (m[2], (1.5, 0.0), 0)]
    figure_at(2.8, 0.6)
    lineup(ents, tk.camera("St_" + key, (1.3, -7.4, 2.0), (0.0, 0.0, 0.95), lens=35),
           os.path.join(PREVIEWS, "palisade_%s_stages.png" % name))
    lineup(ents, tk.camera("Bk_" + key, (-1.3, 7.4, 2.0), (0.0, 0.0, 0.95), lens=35),
           os.path.join(PREVIEWS, "palisade_%s_stages_back.png" % name))
figure_at(1.5, 0.6)
lineup([(BUILT["Stumps"][0], (0.0, 0.0), 0)], tk.camera("Stumps", (1.4, -2.6, 1.3), (0.0, 0.0, -0.05), lens=35),
       os.path.join(PREVIEWS, "palisade_stumps.png"), res=(1400, 1000))
lineup([(BUILT["Stumps"][0], (0.0, 0.0), 0)], tk.camera("StumpsB", (-1.3, 2.6, 1.4), (0.0, 0.0, -0.05), lens=35),
       os.path.join(PREVIEWS, "palisade_stumps_back.png"), res=(1400, 1000))

S0 = BUILT["Section"][0]
figure_at(1.4, -0.8)
lineup([(S0, (0.0, 0.0), 0)], tk.camera("Close", (0.75, -1.5, 2.15), (0.0, 0.0, 1.55), lens=40),
       os.path.join(PREVIEWS, "palisade_close_points.png"), res=(1200, 1000))
lineup([(S0, (0.0, 0.0), 0)], tk.camera("CloseB", (-0.6, 1.3, 1.5), (-0.1, 0.1, 1.35), lens=40),
       os.path.join(PREVIEWS, "palisade_close_lashing.png"), res=(1200, 1000))
lineup([(BUILT["Section"][2], (0.0, 0.0), 0)], tk.camera("CloseD", (0.9, -1.9, 1.1), (0.0, 0.0, 0.6), lens=38),
       os.path.join(PREVIEWS, "palisade_close_dmg2.png"), res=(1200, 1000))
lineup([(BUILT["Section"][1], (0.0, 0.0), 0)], tk.camera("CloseW", (0.6, -1.6, 1.3), (0.0, 0.0, 1.0), lens=38),
       os.path.join(PREVIEWS, "palisade_close_dmg1.png"), res=(1200, 1000))

# a run of sections meeting a corner
C0 = BUILT["Corner"][0]
B0 = BUILT["SectionBanded"][0]
row = [(C0, (0.0, 0.0), 0), (S0, (1.0, 0.0), 0), (B0, (2.0, 0.0), 0), (S0, (3.0, 0.0), 0), (S0, (0.0, 1.0), -90),
       (S0, (0.0, 2.0), -90)]
figure_at(1.5, -1.2)
lineup(row, tk.camera("RowF", (-2.6, -5.6, 3.0), (1.3, 0.5, 0.7), lens=30), os.path.join(PREVIEWS, "palisade_row.png"))
lineup(row, tk.camera("RowB", (3.4, 4.6, 3.2), (0.8, 0.6, 0.8), lens=30),
       os.path.join(PREVIEWS, "palisade_row_back.png"))
lineup(row, tk.camera("RowS", (1.0, -2.4, 2.2), (1.0, 0.0, 1.0), lens=32),
       os.path.join(PREVIEWS, "palisade_row_seams.png"), res=(1600, 1000))

# the gate between two sections, closed and open
figure_at(2.7, -1.0)
side = [(S0, (-2.0, 0.0), 0), (S0, (2.0, 0.0), 0)]
lineup(side, tk.camera("GateF", (1.6, -7.6, 2.2), (0.0, 0.0, 0.95), lens=32),
       os.path.join(PREVIEWS, "palisade_gate_closed.png"), show=GATE)
lineup(side, tk.camera("GateB", (-1.6, 7.6, 2.2), (0.0, 0.0, 0.95), lens=32),
       os.path.join(PREVIEWS, "palisade_gate_closed_back.png"), show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, math.radians(-90.0))
leaf_r.rotation_euler = (0.0, 0.0, math.radians(90.0))
lineup(side, tk.camera("GateO", (3.6, -6.8, 2.6), (0.0, -0.4, 0.8), lens=32),
       os.path.join(PREVIEWS, "palisade_gate_open.png"), show=GATE)
leaf_l.rotation_euler = (0.0, 0.0, 0.0)
leaf_r.rotation_euler = (0.0, 0.0, 0.0)
lineup([], tk.camera("GateH", (1.75, -1.15, 1.85), (1.15, -0.12, 1.45), lens=40),
       os.path.join(PREVIEWS, "palisade_gate_hinge.png"), res=(1200, 1000), show=GATE)
lineup([], tk.camera("GateBr", (-0.5, 1.4, 1.3), (0.0, 0.15, 0.8), lens=40),
       os.path.join(PREVIEWS, "palisade_gate_bracket.png"), res=(1200, 1000), show=GATE)

# ---------------------------------------------------------------- icon
for o in ALL:
    o.hide_render = o is not S0
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S0}
tk.icon(tk.camera("Icon", (2.0, -3.9, 2.2), (0.0, 0.0, 1.0), lens=50), ICON, hide=hide, target=(0.0, 0.0, 1.0))
log("icon", ICON)

# ---------------------------------------------------------------- check the files as the importer sees them
bpy.ops.wm.read_factory_settings(use_empty=True)
for fname in sorted(os.listdir(ASSETS)):
    if not (fname.startswith("Palisade") and fname.endswith(".fbx")):
        continue
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=os.path.join(ASSETS, fname))
    parts = []
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type == "MESH":
            co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            parts.append("%s tris %d mat %s z %.3f..%.3f x %.3f..%.3f y %.3f..%.3f origin %s parent %s" % (
                o.name, tris, [m.name for m in o.data.materials], co[:, 2].min(), co[:, 2].max(), co[:, 0].min(),
                co[:, 0].max(), co[:, 1].min(), co[:, 1].max(), tuple(round(c, 3) for c in o.matrix_world.translation),
                o.parent.name if o.parent else None))
        else:
            parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation),
                                                    o.parent.name if o.parent else None))
    log("reimport", fname, "|", " || ".join(parts))
log("done")
