"""Propane tank: a dented 20 lb barbecue tank (scaled to about 40 cm tall to fit the chest) ratchet-strapped upright
to the zombie's chest, resting on the belly and leaning back onto the chest. Faded white paint with rust round the
collar and seam, chips and dents, a peeling DANGER / PROPANE warning label with the flammable-gas diamond. Its brass
valve and black handwheel sit inside the collar; the regulator's nut is still on the outlet, and a short torn-off hose
hangs out of a collar window, white with frost where the gas hisses out. Two faded orange ratchet straps run round
the tank and the torso, the ratchet on the tank's front-left with the loose tail of the strap hanging from it.

In game, shooting the chest blows the tank up and a headshot kill drops it, so the tank (with its valve and hose) is
one part, Spine2#Tank, and the straps another, Spine2#Straps.

    blender -b --factory-startup --python propane_tank.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], "PropaneTank"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

AXIS = np.array([0.0, 0.05])  # the chest hit box's vertical axis (x, y)
R0 = 0.175
CLEAR = 0.015
ATTR = "zx_local"  # per-vertex tank-local position, which the paint and label are laid out by

# ---------------------------------------------------------------- the body: hit-box capsules and their envelope

def _capsules():
    out = []
    for c in sk.colliders:
        if c["type"] != "capsule":
            continue
        ax = [0.0, 0.0, 0.0]
        ax[c["axis"]] = 1.0
        half = max(0.0, c["height"] / 2 - c["radius"])
        ctr = Vector(c["center"])
        a = sk.point(c["bone"], ctr - Vector(ax) * half)
        b = sk.point(c["bone"], ctr + Vector(ax) * half)
        out.append((c["bone"], np.array(a), np.array(b), c["radius"]))
    return out


CAPS = _capsules()


def sdf(P, bones=None):
    """Distance from points to the nearest hit box (negative inside)."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    d = np.full(len(P), 9.0)
    for bone, a, b, r in CAPS:
        if bones and bone not in bones:
            continue
        ba, pa = b - a, P - a
        h = np.clip(pa @ ba / max(ba @ ba, 1e-12), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(pa - h[:, None] * ba, axis=1) - r)
    return d


def _ray_exit(theta, z):
    """Where a level ray from the chest axis at angle theta (0 = front, -Y; +90 = the zombie's left, +X) leaves the
    torso's vertical capsules (chest and hips)."""
    theta, z = np.broadcast_arrays(np.asarray(theta, float), np.asarray(z, float))
    dx, dy = np.sin(theta), -np.cos(theta)
    best = np.zeros(theta.shape)
    for bone, a, b, r in CAPS:
        if bone not in ("Spine2", "Hips"):
            continue
        za, zb = min(a[2], b[2]), max(a[2], b[2])
        dz = np.where(z > zb, z - zb, np.where(z < za, za - z, 0.0))
        rz2 = r * r - dz * dz
        wx, wy = AXIS[0] - a[0], AXIS[1] - a[1]
        wd = wx * dx + wy * dy
        disc = wd * wd - (wx * wx + wy * wy - rz2)
        t = np.where((rz2 > 0) & (disc > 0), -wd + np.sqrt(np.maximum(disc, 0.0)), 0.0)
        best = np.maximum(best, t)
    return best


def _upper_hull(x, y):
    hull = []
    for p in zip(x, y):
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) >= 0:
            hull.pop()
        hull.append(p)
    hx, hy = zip(*hull)
    return np.interp(x, hx, hy)


TH = np.linspace(-math.pi, math.pi, 361)
ZS = np.arange(0.96, 1.74, 0.005)
_T, _Z = np.meshgrid(TH, ZS, indexing="ij")
ENV = np.array([_upper_hull(ZS, row) for row in _ray_exit(_T, _Z)])  # taut: a vest hangs straight over hollows


def env(theta, z):
    """The torso's taut radius round the chest axis (bilinear in the table)."""
    theta = (np.asarray(theta, float) + math.pi) % (2 * math.pi) - math.pi
    fi = np.clip((theta + math.pi) / (2 * math.pi) * (len(TH) - 1), 0, len(TH) - 1.001)
    fj = np.clip((np.asarray(z, float) - ZS[0]) / 0.005, 0, len(ZS) - 1.001)
    i, j = fi.astype(int), fj.astype(int)
    a, b = fi - i, fj - j
    return ((ENV[i, j] * (1 - b) + ENV[i, j + 1] * b) * (1 - a) + (ENV[i + 1, j] * (1 - b) + ENV[i + 1, j + 1] * b) * a)


def squarish(theta, p=2.3):
    """A little boxier than round (flatter front and back), never inside the circle."""
    c, s = np.abs(np.cos(theta)), np.abs(np.sin(theta))
    return (c ** p + s ** p) ** (-1.0 / p)


def wrap(theta, z, clear=CLEAR):
    r = env(theta, z) * squarish(theta) + clear
    return np.stack([AXIS[0] + r * np.sin(theta), AXIS[1] - r * np.cos(theta), np.asarray(z, float) * np.ones_like(r)],
                    axis=-1)


# ---------------------------------------------------------------- 2D pattern pieces

def _dense(poly, step=0.003):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = np.array(poly[i]), np.array(poly[(i + 1) % n])
        k = max(1, int(np.linalg.norm(b - a) / step))
        for t in range(k):
            out.append(a + (b - a) * t / k)
    return np.array(out)


def _smooth_closed(P, sigma_pts):
    n = len(P)
    k = int(3 * sigma_pts)
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma_pts) ** 2)
    w /= w.sum()
    out = np.zeros_like(P)
    for o, wt in zip(range(-k, k + 1), w):
        out += wt * np.roll(P, o, axis=0)
    return out


def _adaptive(P, step, angle):
    """Resamples a closed dense polyline: a point every `step` of length or `angle` of turning, whichever first."""
    n = len(P)
    keep, cost = [0], 0.0
    for i in range(1, n):
        d0 = P[i] - P[i - 1]
        d1 = P[(i + 1) % n] - P[i]
        turn = abs(math.atan2(d0[0] * d1[1] - d0[1] * d1[0], d0 @ d1))
        cost += np.linalg.norm(d0) / step + turn / angle
        if cost >= 1.0:
            keep.append(i)
            cost = 0.0
    if np.linalg.norm(P[keep[-1]] - P[0]) < 0.4 * step:
        keep.pop()
    return P[keep]


def outline(poly, step=0.03, round_r=0.006, angle=math.radians(30)):
    D = _dense(poly)
    D = _smooth_closed(D, round_r / 0.003)
    O = _adaptive(D, step, angle)
    area = 0.5 * np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1])
    return O if area > 0 else O[::-1]


def _seg_dist(P, O):
    A, B = O, np.roll(O, -1, axis=0)
    AB = B - A
    AP = P[:, None, :] - A[None]
    t = np.clip(np.einsum("ijk,jk->ij", AP, AB) / np.maximum(np.einsum("jk,jk->j", AB, AB), 1e-12), 0, 1)
    return np.linalg.norm(AP - t[..., None] * AB[None], axis=2).min(axis=1)


def _inside(P, O):
    x, y = P[:, 0][:, None], P[:, 1][:, None]
    x1, y1 = O[:, 0][None], O[:, 1][None]
    x2, y2 = np.roll(O[:, 0], -1)[None], np.roll(O[:, 1], -1)[None]
    cond = (y1 > y) != (y2 > y)
    xi = x1 + (y - y1) * (x2 - x1) / np.where(y2 - y1 == 0, 1e-12, y2 - y1)
    return (np.sum(cond & (x < xi), axis=1) % 2) == 1


def _lattice(O, spacing, margin):
    lo, hi = O.min(0), O.max(0)
    pts = []
    row = 0
    z = lo[1] + spacing * 0.5
    while z < hi[1]:
        off = (spacing * 0.5) if row % 2 else 0.0
        u = lo[0] + off + spacing * 0.25
        while u < hi[0]:
            pts.append((u, z))
            u += spacing
        z += spacing * 0.866
        row += 1
    P = np.array(pts)
    P = P[_inside(P, O)]
    return P[_seg_dist(P, O) > margin]


def _cdt(pts, loops):
    edges, faces, start = [], [], 0
    for n in loops:
        edges += [(start + i, start + (i + 1) % n) for i in range(n)]
        start += n
    faces = [list(range(loops[0]))]
    vs, es, fs, orig, _, _ = delaunay_2d_cdt([Vector((p[0], p[1])) for p in pts], edges, faces, 1, 1e-7)
    src = [o[0] if o else -1 for o in orig]
    return [(v.x, v.y) for v in vs], fs, src


def panel(name, poly, to3d, mat, thick, edge_thick=0.004, inset=0.008, dense=0.04, sparse=0.085):
    """A padded panel cut to the 2D pattern `poly` (u, z) and laid on the body by to3d(u, z) -> inner-face points:
    the outer face rises from edge_thick at the cut edge to `thick` an `inset` in (a rolled, bound edge)."""
    O = outline(poly)
    n0 = len(O)
    # Inset ring (the rolled edge), inward along the outline's left normal
    T = np.roll(O, -1, axis=0) - np.roll(O, 1, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    I = O + np.stack([-T[:, 1], T[:, 0]], axis=1) * inset
    inner_pts = _lattice(O, dense, max(0.7 * dense, inset + 0.012))
    v_out, f_out, s_out = _cdt(list(O) + list(I) + list(inner_pts), [n0, n0])
    v_in, f_in, s_in = _cdt(list(O) + list(_lattice(O, sparse, 0.6 * sparse)), [n0])

    # Inner face of the dense triangulation, for the normals
    P_out_in = to3d(np.array(v_out))
    bm = bmesh.new()
    vv = [bm.verts.new(p) for p in P_out_in]
    for f in f_out:
        try:
            bm.faces.new([vv[i] for i in f])
        except ValueError:
            pass
    bm.normal_update()
    N = np.array([v.normal[:] for v in vv])
    radial = P_out_in.copy()
    radial[:, 0] -= AXIS[0]
    radial[:, 1] -= AXIS[1]
    radial[:, 2] = 0
    if np.sum(np.einsum("ij,ij->i", N, radial)) < 0:
        N = -N
    bm.free()

    kind = np.array([0 if 0 <= s < n0 else 1 for s in s_out])  # 0 on the cut edge
    th = np.where(kind == 0, edge_thick, thick)
    P_outer = P_out_in + N * th[:, None]

    bm = bmesh.new()
    attr = []
    outer = [bm.verts.new(p) for p in P_outer]
    attr += [(v_out[i][0], v_out[i][1], float(kind[i])) for i in range(len(outer))]
    # The inner face shares the outline (in order) with the outer face's cut-edge vertices
    edge_out = {s: i for i, s in enumerate(s_out) if 0 <= s < n0}
    P_in = to3d(np.array(v_in))
    inner = [bm.verts.new(p) for p in P_in]
    attr += [(v_in[i][0], v_in[i][1], 0.0 if 0 <= s_in[i] < n0 else 1.0) for i in range(len(inner))]
    edge_in = {s: i for i, s in enumerate(s_in) if 0 <= s < n0}
    for f in f_out:
        bm.faces.new([outer[i] for i in f])
    for f in f_in:
        bm.faces.new([inner[i] for i in reversed(f)])
    for k in range(n0):
        k1 = (k + 1) % n0
        bm.faces.new((outer[edge_out[k]], outer[edge_out[k1]], inner[edge_in[k1]], inner[edge_in[k]]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, attr)
    return tk.smooth(obj, 50)


def set_attr(obj, values):
    me = obj.data
    a = me.attributes.get(ATTR) or me.attributes.new(ATTR, "FLOAT_VECTOR", "POINT")
    for d, v in zip(a.data, values):
        d.vector = v


# ---------------------------------------------------------------- straps and boxes

def bvh(objs):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def far_hit(tree, origin, d, maxd=0.6):
    """How far along the ray its last hit on the tree is (0 if none)."""
    o, best = Vector(origin), 0.0
    d = Vector(d).normalized()
    travelled = 0.0
    for _ in range(12):
        loc, nrm, idx, dist = tree.ray_cast(o, d, maxd - travelled)
        if loc is None:
            break
        travelled += dist + 1e-4
        best = travelled
        o = loc + d * 1e-4
    return best


def shell_exit(origin, d, clear, bones=None, maxd=0.45):
    """How far along the ray the last point within `clear` of the hit boxes is."""
    t = np.arange(0.0, maxd, 0.0015)
    P = np.asarray(origin)[None] + t[:, None] * np.asarray(d)[None]
    inside = np.nonzero(sdf(P, bones) < clear)[0]
    return t[inside[-1]] if len(inside) else 0.0


def taut(origin2, dirs2, ts):
    """Pulls a fan of distances (rays from one origin in a plane, 2D) tight: the convex hull's radius per ray."""
    P = [origin2 + d * t for d, t in zip(dirs2, ts)] + [origin2]
    pts = sorted(set((round(p[0], 7), round(p[1], 7)) for p in P))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    H = [np.array(p) for p in lower[:-1] + upper[:-1]]
    out = []
    for d, t0 in zip(dirs2, ts):
        best = t0
        for i in range(len(H)):
            a, b = H[i], H[(i + 1) % len(H)]
            e = b - a
            den = d[0] * (-e[1]) - d[1] * (-e[0])
            if abs(den) < 1e-12:
                continue
            w = a - origin2
            t = (w[0] * (-e[1]) - w[1] * (-e[0])) / den
            s = (d[0] * w[1] - d[1] * w[0]) / den
            if -1e-6 <= s <= 1 + 1e-6 and t > best:
                best = t
        out.append(best)
    return np.array(out)


PADDED = [(-0.5, 0.0), (-0.42, -0.5), (0.42, -0.5), (0.5, 0.0), (0.42, 0.5), (-0.42, 0.5)]
FLAT = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]


def band(name, pts, nrms, width, thick, mat, profile=FLAT, closed=False):
    """A strap swept along pts, lying on a surface whose outward normals are nrms: `width` across, `thick` out."""
    P = [Vector(p) for p in pts]
    Nn = [Vector(n).normalized() for n in nrms]
    n = len(P)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if closed:
            T = (P[(i + 1) % n] - P[i - 1]).normalized()
        else:
            T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        N = (Nn[i] - T * Nn[i].dot(T)).normalized()
        W = T.cross(N)
        rings.append([bm.verts.new(P[i] + W * (a * width) + N * (b * thick)) for a, b in profile])
    k = len(profile)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((a[j], a[(j + 1) % k], b[(j + 1) % k], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 50)


def smooth1d(a, passes=2):
    a = np.array(a, float)
    for _ in range(passes):
        a[1:-1] = 0.25 * a[:-2] + 0.5 * a[1:-1] + 0.25 * a[2:]
    return a


def frame_at(tree, u, z, back=False):
    """The outer surface point and frame (side, out, up) of a panel at pattern (u, z)."""
    th = (math.pi if back else 0.0) + u / R0
    d = Vector((math.sin(th), -math.cos(th), 0.0))
    o = Vector((AXIS[0], AXIS[1], z))
    t = far_hit(tree, o, d)
    p = o + d * t
    loc, nrm, idx, dist = tree.find_nearest(p)
    n = nrm if nrm.dot(d) > 0 else -nrm
    side = Vector((0, 0, 1)).cross(n).normalized()
    up = n.cross(side).normalized()
    return p, side, n, up


def block(name, size, mat, frame, offset=(0.0, 0.0, 0.0), bevel=0.004, tilt=0.0, taper=1.0, segments=1):
    """A bevelled box placed in a surface frame: size = (across, out, up), its back face `offset[1]` off the surface."""
    p, side, n, up = frame
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    for v in bm.verts:
        if v.co.y > 0:  # a softer, sewn-bag shape: the front face a little smaller
            v.co.x *= taper
            v.co.z *= taper
    bmesh.ops.translate(bm, vec=(offset[0], offset[1] + size[1] / 2, offset[2]), verts=bm.verts)
    obj = tk.mesh_object(name, bm, mat)
    if bevel:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = "ANGLE"
        tk.apply_modifiers(obj)
    rot = Matrix((side, n, up)).transposed().to_4x4()
    obj.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Rotation(math.radians(tilt), 4, "Y")
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return tk.smooth(fix_normals(obj), 40)


def fix_normals(obj):
    """Points every face of a closed piece outward (a mirrored frame turns a box inside out)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


# ---------------------------------------------------------------- printed lettering (rasterized to a mask image)

def glyph_tris(body, font, spacing=1.0):
    cu = bpy.data.curves.new("Glyphs", "FONT")
    cu.body = body
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.resolution_u = 8
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    ob = tk.link(bpy.data.objects.new("Glyphs", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tris = np.array([[(v.co.x, v.co.y) for v in f.verts] for f in bm.faces])
    bm.free()
    bpy.data.meshes.remove(me)
    return tris


def fit(tris, box):
    """Scales and moves glyph triangles to fill box (x0, y0, x1, y1), keeping their aspect."""
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    s = min((box[2] - box[0]) / (hi[0] - lo[0]), (box[3] - box[1]) / (hi[1] - lo[1]))
    c = (lo + hi) / 2
    return (tris - c) * s + np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])


def raster(shape, box, tris, ss=3):
    H, W = shape
    x0, y0, x1, y1 = box
    Hs, Ws = H * ss, W * ss
    img = np.zeros((Hs, Ws), np.float32)
    sx, sy = Ws / (x1 - x0), Hs / (y1 - y0)
    for t in tris:
        P = np.column_stack(((t[:, 0] - x0) * sx, (t[:, 1] - y0) * sy))
        lo = np.maximum(np.floor(P.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(P.max(0)).astype(int), [Ws, Hs])
        if (hi <= lo).any():
            continue
        X, Y = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)

        def ef(a, b):
            return (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
        e0, e1, e2 = ef(P[0], P[1]), ef(P[1], P[2]), ef(P[2], P[0])
        ins = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
        img[lo[1]:hi[1], lo[0]:hi[0]][ins] = 1.0
    return img.reshape(H, ss, W, ss).mean(axis=(1, 3))


def rounded_rect(shape, box, rect, r):
    H, W = shape
    x0, y0, x1, y1 = box
    X, Y = np.meshgrid(x0 + (np.arange(W) + 0.5) * (x1 - x0) / W, y0 + (np.arange(H) + 0.5) * (y1 - y0) / H)
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    hx, hy = (rect[2] - rect[0]) / 2 - r, (rect[3] - rect[1]) / 2 - r
    qx, qy = np.maximum(np.abs(X - cx) - hx, 0), np.maximum(np.abs(Y - cy) - hy, 0)
    d = np.sqrt(qx * qx + qy * qy) - r
    px = (x1 - x0) / W
    return np.clip(0.5 - d / px, 0, 1)


def mask_image(name, channels):
    H, W = channels[0].shape
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((H, W, 4), np.float32)
    for k, c in enumerate(channels):
        rgba[..., k] = c
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(tempfile.gettempdir(), "zx_%s.png" % name)
    img.file_format = "PNG"
    img.save()
    return img


def decal(g, img, u, v, box):
    """The image laid over pattern coordinates box (u0, v0, u1, v1); outside it reads black."""
    cx = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", u, box[0]), box[2] - box[0]), cx.inputs[0])
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", v, box[1]), box[3] - box[1]), cx.inputs[1])
    n = g.node("ShaderNodeTexImage", interpolation="Linear", extension="CLIP")
    n.image = img
    g.links.new(cx.outputs[0], n.inputs["Vector"])
    return g.separate(n.outputs["Color"])


def attr_uvw(g):
    a = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    a.attribute_type = "GEOMETRY"
    return g.separate(tk._sock(a.outputs, "Vector"))


def blood(g, col, rough, height, region):
    """Dried and tacky blood: splatter, smears and drips run down."""
    co = g.coords()
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 70.0)
    g.links.new(co, vor.inputs["Vector"])
    dots = g.ramp(tk._sock(vor.outputs, "Distance"), 0.2, 0.09)
    dots = g.math("MULTIPLY", dots, g.ramp(g.noise(5.0, detail=3.0), 0.45, 0.55))
    m = g.node("ShaderNodeMapping")
    g.links.new(co, m.inputs["Vector"])
    m.inputs["Scale"].default_value = (24.0, 24.0, 2.0)
    drips = g.ramp(g.noise(1.0, detail=5.0, vector=m.outputs[0]), 0.6, 0.66)
    smear = g.ramp(g.noise(2.6, detail=7.0, roughness=0.6, distortion=0.8), 0.56, 0.62)
    b = g.math("MAXIMUM", g.math("MAXIMUM", dots, drips), smear)
    b = g.math("MULTIPLY", b, region, clamp=True)
    fresh = g.ramp(g.noise(9.0, detail=4.0), 0.42, 0.7)
    bc = g.mix(fresh, (0.026, 0.006, 0.004), (0.07, 0.008, 0.005))
    col = g.mix(b, col, bc)
    rough = g.mixf(b, rough, g.mixf(fresh, 0.62, 0.4))
    height = g.math("ADD", height, g.math("MULTIPLY", b, 0.12))
    return col, rough, height


# ---------------------------------------------------------------- paths

def catmull(ctrl, per=6):
    P = [np.asarray(c, float) for c in ctrl]
    P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


def resample(P, n):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], axis=1)




# ---------------------------------------------------------------- more shapes

def poly_fill(shape, box, poly, ss=2):
    H, W = shape[0] * ss, shape[1] * ss
    x0, y0, x1, y1 = box
    X, Y = np.meshgrid(x0 + (np.arange(W) + 0.5) * (x1 - x0) / W, y0 + (np.arange(H) + 0.5) * (y1 - y0) / H)
    inside = np.zeros((H, W), bool)
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        if ya == yb:
            continue
        cond = (ya > Y) != (yb > Y)
        xi = xa + (Y - ya) * (xb - xa) / (yb - ya)
        inside ^= cond & (X < xi)
    return inside.astype(np.float32).reshape(shape[0], ss, shape[1], ss).mean(axis=(1, 3))


def text(shape, box, body, rect, font="C:/Windows/Fonts/arialbd.ttf", stretch=True):
    tris = glyph_tris(body, font)
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    sx = (rect[2] - rect[0]) / (hi[0] - lo[0])
    sy = (rect[3] - rect[1]) / (hi[1] - lo[1])
    if not stretch:
        sx = sy = min(sx, sy)
    return raster(shape, box, (tris - lo) * np.array([sx, sy]) + np.array([rect[0], rect[1]]))


def transported(P, closed=False):
    """Cross-section frames carried along a path without twisting (so a round tube stays round)."""
    n = len(P)
    T = [P[(i + 1) % n if closed else min(i + 1, n - 1)] - P[i - 1 if closed else max(i - 1, 0)] for i in range(n)]
    T = [t / np.linalg.norm(t) for t in T]
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    out = []
    for t in T:
        nv = ref - t * (ref @ t)
        nv /= np.linalg.norm(nv)
        out.append(nv)
        ref = nv
    return out


def round_tube(name, pts, radius, mat, sides=8, closed=False):
    P = np.array(pts, float)
    nrms = transported(P, closed)
    prof = [(0.5 * math.cos(2 * math.pi * k / sides), 0.5 * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    return band(name, P, nrms, radius * 2, radius * 2, mat, profile=prof, closed=closed)


def revolve(name, profile, mat, seg, closed=False, phase=0.0):
    """A surface of revolution about local Z from (r, h) points; r = 0 ends close in a fan. closed=True joins the
    last profile point back to the first (a ring's cross-section)."""
    bm = bmesh.new()
    rings = []
    for r, h in profile:
        if r == 0.0:
            rings.append([bm.verts.new((0.0, 0.0, h))])
        else:
            rings.append([bm.verts.new((r * math.cos(phase + 2 * math.pi * k / seg),
                                        r * math.sin(phase + 2 * math.pi * k / seg), h)) for k in range(seg)])
    pairs = list(zip(rings[:-1], rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for a, b in pairs:
        for k in range(seg):
            k1 = (k + 1) % seg
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[k1]))
            elif len(b) == 1:
                bm.faces.new((a[k], a[k1], b[0]))
            else:
                bm.faces.new((a[k], a[k1], b[k1], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, mat)


def local_attr(obj):
    """Records each vertex's tank-local position (before the tank is tilted onto the chest) for the materials."""
    set_attr(obj, [tuple(v.co) for v in obj.data.vertices])
    return obj


# ---------------------------------------------------------------- the tank's label

LABEL = (-0.07, 0.125, 0.07, 0.225)  # in the tank's (arc length round from the front, height) coordinates
LABEL_IMG = None


def label_image():
    """R: black ink, G: the label's paper, B: red ink (DANGER band and the flammable-gas diamond)."""
    shape = (384, 512)
    box = (-0.07, -0.05, 0.07, 0.05)
    paper = poly_fill(shape, box, [(-0.068, -0.048), (0.068, -0.048), (0.068, 0.048), (-0.068, 0.048)])
    band_ = poly_fill(shape, box, [(-0.068, 0.027), (0.068, 0.027), (0.068, 0.048), (-0.068, 0.048)])
    danger = text(shape, box, "DANGER", (-0.036, 0.031, 0.036, 0.044))
    ink = text(shape, box, "PROPANE", (-0.062, 0.006, 0.018, 0.021))
    lines = (("FLAMMABLE GAS UNDER PRESSURE", -0.003), ("KEEP AWAY FROM HEAT, FLAME", -0.0125),
             ("DO NOT PUNCTURE OR INCINERATE", -0.022), ("20 LB     WC 47.6   TW 17.8", -0.034))
    for body, v in lines:
        ink = np.maximum(ink, text(shape, box, body, (-0.062, v, 0.016, v + 0.0055), "C:/Windows/Fonts/arial.ttf"))
    cx, cy, rd = 0.043, -0.012, 0.024
    diamond = poly_fill(shape, box, [(cx, cy - rd), (cx + rd, cy), (cx, cy + rd), (cx - rd, cy)])
    inner = poly_fill(shape, box, [(cx, cy - rd + 0.003), (cx + rd - 0.003, cy), (cx, cy + rd - 0.003), (cx - rd + 0.003, cy)])
    inner2 = poly_fill(shape, box, [(cx, cy - rd + 0.0042), (cx + rd - 0.0042, cy), (cx, cy + rd - 0.0042),
                                    (cx - rd + 0.0042, cy)])
    outline_ = np.clip(inner - inner2, 0, 1)
    flame = poly_fill(shape, box, [(cx - 0.007, cy + 0.003), (cx + 0.007, cy + 0.003), (cx + 0.006, cy + 0.008),
                                   (cx + 0.003, cy + 0.012), (cx + 0.0035, cy + 0.009), (cx + 0.001, cy + 0.0115),
                                   (cx, cy + 0.017), (cx - 0.002, cy + 0.011), (cx - 0.004, cy + 0.0125),
                                   (cx - 0.0065, cy + 0.008)])
    words = text(shape, box, "FLAMMABLE GAS", (cx - 0.0125, cy - 0.0015, cx + 0.0125, cy + 0.0015))
    two = text(shape, box, "2", (cx - 0.0018, cy - 0.0175, cx + 0.0018, cy - 0.0115), stretch=False)
    white_in_red = np.clip(danger + outline_ + flame + words + two, 0, 1)
    red = np.clip(np.maximum(band_, diamond) - white_in_red, 0, 1)
    return mask_image("PropaneLabel", [ink * paper, paper, red])


LABEL_IMG = label_image()


# ---------------------------------------------------------------- materials

def tank_paint(name, rust_amt=1.0, label=False):
    """Faded white enamel over steel: grimy streaks, chips and scratches to bare steel, rust round the collar, along
    the weld seam and run down the sides, a peeling warning label, blood. zx_local is the tank-local position."""
    mat, g = tk.new_material(name)
    lx, ly, lh = attr_uvw(g)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", lx, lx), g.math("MULTIPLY", ly, ly)))
    arc = g.math("MULTIPLY", g.math("ARCTAN2", lx, g.math("MULTIPLY", ly, -1.0)), 0.133)  # 0 at the front
    tone = g.ramp(g.noise(4.0, detail=5.0, distortion=0.3), 0.3, 0.8)
    col = g.mix(tone, (0.6, 0.6, 0.56), (0.47, 0.46, 0.41))
    p = tk.photo(g, "rusty_painted_metal", 1.3, (0.4, 0.15, 0.6))
    streak = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.09, 0.03), 0.8)
    col = g.mix(streak, col, (0.2, 0.17, 0.13))
    rough = g.mixf(tone, 0.58, 0.74)  # chalky, sun-faded enamel
    metal = 0.0
    height = g.math("MULTIPLY", g.noise(60.0, detail=4.0), 0.15)
    if label:
        u0, v0, u1, v1 = LABEL
        ink, paper, red = decal(g, LABEL_IMG, arc, lh, (u0, v0, u1, v1))
        torn = g.ramp(g.noise(9.0, detail=7.0, roughness=0.7, distortion=0.4), 0.66, 0.7)
        corner = g.ramp(g.math("ADD", g.math("ABSOLUTE", g.math("SUBTRACT", arc, 0.07)),
                               g.math("ABSOLUTE", g.math("SUBTRACT", lh, 0.125))), 0.03, 0.022)
        paper = g.math("MULTIPLY", paper, g.math("SUBTRACT", 1.0, g.math("MAXIMUM", torn, corner)))
        ink = g.math("MULTIPLY", ink, paper)
        red = g.math("MULTIPLY", red, paper)
        faded = g.ramp(g.noise(6.0, detail=4.0), 0.3, 0.8)
        col = g.mix(paper, col, g.mix(faded, (0.72, 0.68, 0.52), (0.6, 0.55, 0.4)))
        col = g.mix(red, col, g.mix(faded, (0.42, 0.03, 0.02), (0.45, 0.12, 0.08)))
        col = g.mix(g.math("MULTIPLY", ink, 0.9), col, (0.03, 0.03, 0.03))
        rough = g.mixf(paper, rough, 0.62)
        height = g.math("ADD", height, g.math("MULTIPLY", paper, 0.25))
    # The weld seam round the middle
    seam = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", lh, 0.185)), 0.0035, 0.001)
    height = g.math("ADD", height, g.math("MULTIPLY", seam, 0.6))
    # Rust: round the collar's foot, the seam, low down, in blooms, and run down from the collar
    coll = g.math("MULTIPLY", g.ramp(lh, 0.3, 0.335), g.ramp(r, 0.11, 0.08))
    low = g.ramp(lh, 0.08, 0.04)
    blooms = g.ramp(g.noise(5.0, detail=9.0, roughness=0.65, distortion=0.5), 0.64, 0.7)
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (18.0, 18.0, 1.4)
    runs = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=5.0, vector=m.outputs[0]), 0.6, 0.7), g.ramp(lh, 0.05, 0.3))
    rust = g.math("MAXIMUM", g.math("MAXIMUM", coll, g.math("MULTIPLY", seam, 0.7)), g.math("MAXIMUM", low, blooms))
    rust = g.math("MAXIMUM", rust, g.math("MULTIPLY", runs, 0.65))
    rust = g.math("MULTIPLY", g.math("MULTIPLY", rust, g.ramp(g.noise(22.0, detail=6.0), 0.25, 0.55)), rust_amt, clamp=True)
    rp = tk.photo(g, "rust_coarse_01", 2.2, (0.2, 0.6, 0.1))
    col = g.mix(rust, col, tk.grade(g, rp["color"], 1.0, 0.9))
    rough = g.mixf(rust, rough, 0.88)
    height = g.math("ADD", height, g.math("MULTIPLY", rust, rp["height"]))
    # Chips through the paint at edges and knocks, to dark steel
    chips = g.math("MULTIPLY", g.ramp(g.edges(0.006), 0.08, 0.25), g.ramp(g.noise(30.0, detail=6.0), 0.4, 0.6))
    knocks = g.ramp(g.noise(11.0, detail=8.0, roughness=0.7), 0.7, 0.73)
    chip = g.math("MAXIMUM", chips, knocks)
    col = g.mix(chip, col, (0.09, 0.085, 0.08))
    metal = g.mixf(chip, metal, 0.45)
    rough = g.mixf(chip, rough, 0.5)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", chip, 0.3))
    dirt = tk._grime(g, 0.7)
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, (0.08, 0.065, 0.05))
    rough = g.mixf(dirt, rough, 0.85)
    x, y, z = g.separate(g.coords())
    col, rough, height = blood(g, col, rough, height, g.math("ADD", g.math("MULTIPLY", g.ramp(z, 1.28, 1.48), 1.0), 0.3))
    col, rough, metal = tk._grit(g, col, rough, metal, 0.5, scratches=0.35, edges=0.25)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.003))


def rubber_hose(name, frost_at):
    """Black rubber, cracked and grimy, white with frost where the gas hisses out."""
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(12.0, detail=4.0), 0.3, 0.7), (0.012, 0.012, 0.012), (0.024, 0.023, 0.022))
    crack = g.ramp(g.noise(140.0, detail=6.0, roughness=0.8, distortion=1.0), 0.66, 0.7)
    col = g.mix(crack, col, (0.05, 0.047, 0.044))
    lx, ly, lh = attr_uvw(g)  # tank-local position
    pos = g.node("ShaderNodeCombineXYZ")
    for k, s in enumerate((lx, ly, lh)):
        g.links.new(s, pos.inputs[k])
    dist = g.node("ShaderNodeVectorMath", operation="DISTANCE")
    g.links.new(pos.outputs[0], dist.inputs[0])
    dist.inputs[1].default_value = tuple(float(c) for c in frost_at)
    near = g.ramp(tk._sock(dist.outputs, "Value"), 0.032, 0.01)
    crystals = g.noise(200.0, detail=4.0, roughness=0.8)
    frost = g.math("MULTIPLY", near, g.ramp(g.math("ADD", crystals, g.noise(20.0)), 0.6, 0.9))
    frost = g.math("MAXIMUM", frost, g.math("MULTIPLY", near, near))
    col = g.mix(frost, col, (0.72, 0.75, 0.78))
    rough = g.mixf(frost, 0.78, 0.7)
    height = g.math("ADD", g.math("MULTIPLY", crack, -0.4), g.math("MULTIPLY", frost, crystals))
    dirt = tk._grime(g, 0.6)
    col = g.mix(g.math("MULTIPLY", dirt, 0.4), col, (0.05, 0.045, 0.035))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.15)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.4, 0.002))


def ratchet_strap(name, base):
    """Polyester ratchet-strap webbing: faded, tight weave, grimy, bloodied."""
    mat, g = tk.new_material(name)
    x, y, z = g.separate(g.coords())
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (420.0, 420.0, 40.0)
    wave = g.node("ShaderNodeTexWave", wave_type="BANDS")
    g._in(wave, "Scale", 1.0)
    g._in(wave, "Distortion", 1.5)
    g.links.new(m.outputs[0], wave.inputs["Vector"])
    weave = tk._sock(wave.outputs, "Fac")
    faded = tuple(min(1.0, c * 1.25 + 0.06) for c in base)
    col = g.mix(g.ramp(g.noise(4.0, detail=5.0, distortion=0.4), 0.3, 0.8), base, faded)
    col = g.mix(g.math("MULTIPLY", weave, 0.25), col, tuple(c * 0.65 for c in base))
    rough = g.math("ADD", 0.58, g.math("MULTIPLY", weave, 0.1))
    height = g.math("MULTIPLY", weave, 0.3)
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.1, 0.4), g.ramp(g.noise(30.0, detail=4.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", worn, 0.6), col, (0.55, 0.5, 0.38))
    p = tk.photo(g, "rust_coarse_01", 2.0, (0.6, 0.3, 0.1))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.2, 0.06), 0.7), tk._grime(g, 0.8))
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, (0.11, 0.085, 0.05))
    rough = g.mixf(dirt, rough, 0.9)
    col, rough, height = blood(g, col, rough, height, g.math("ADD", g.math("MULTIPLY", g.ramp(z, 1.25, 1.45), 0.6), 0.3))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.5)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.002))


paint = tank_paint("TankPaint", 1.15, label=True)
paint_rusty = tank_paint("TankCollarPaint", 0.75)
brass = tk.tarnished_copper("ValveBrass", bright=(0.7, 0.5, 0.2), dark=(0.42, 0.28, 0.09))
black = tk.grimy("TankPlastic", (0.018, 0.018, 0.019), roughness=0.42, grime=0.7, grit=0.6)
webbing_mat = ratchet_strap("RatchetStrap", (0.5, 0.28, 0.02))
steel = tk.photo_material("RatchetSteel", "metal_plate_02", scale=3.0, sat=0.25, value=2.8, exposed="rust_coarse_01",
                          chip=0.6, grime=0.6, patches=0.35, metal_floor=0.6, grit=0.4, scratches=0.4, edges=0.5)

# ---------------------------------------------------------------- the tank, built upright at the origin

BODY_PROFILE = [(0.0, 0.032), (0.055, 0.035), (0.092, 0.044), (0.116, 0.056), (0.129, 0.071), (0.133, 0.09),
                (0.133, 0.15), (0.133, 0.22), (0.133, 0.28), (0.13, 0.298), (0.12, 0.315), (0.1, 0.33), (0.072, 0.341),
                (0.04, 0.347), (0.0, 0.349)]
DENTS = [(-0.6, 0.115, 0.045, 0.012), (2.4, 0.25, 0.05, 0.01), (-2.2, 0.2, 0.035, 0.008), (0.9, 0.29, 0.04, 0.009),
         (0.35, 0.1, 0.03, 0.007), (-1.1, 0.27, 0.03, 0.007)]  # (angle from the front, height, size, depth)
OUTLET = np.array([1.0, 0.0, 0.0])  # the valve's outlet faces the zombie's left, out through a collar window

tank = []
body = revolve("TankBody", BODY_PROFILE, paint, 32, phase=math.pi / 32)
for v in body.data.vertices:
    rr = math.hypot(v.co.x, v.co.y)
    if rr < 1e-6:
        continue
    phi = math.atan2(v.co.x, -v.co.y)
    push = 0.0
    for a, h, size, depth in DENTS:
        da = (phi - a + math.pi) % (2 * math.pi) - math.pi
        push += depth * math.exp(-((da * 0.133) ** 2 + (v.co.z - h) ** 2) / (size * size))
    v.co.x *= (rr - push) / rr
    v.co.y *= (rr - push) / rr
tank.append(tk.smooth(body, 60))

foot = revolve("FootRing", [(0.0958, 0.003), (0.1008, 0.0), (0.1, 0.049), (0.0962, 0.05)], paint_rusty, 24, closed=True)
tank.append(tk.smooth(foot, 50))

# Collar: a ring with two hand openings (one the outlet looks out of), its top edge rolled, one side bent in
bm = bmesh.new()
SEG, HS = 22, (0.33, 0.35, 0.379, 0.4)
RS = (0.083, 0.083, 0.083, 0.0855)
grid = [[bm.verts.new((RS[j] * math.cos(2 * math.pi * k / SEG), RS[j] * math.sin(2 * math.pi * k / SEG), HS[j]))
         for k in range(SEG)] for j in range(len(HS))]
for j in range(len(HS) - 1):
    for k in range(SEG):
        a = 2 * math.pi * (k + 0.5) / SEG
        window = j == 1 and (abs(math.cos(a)) > 0.82)
        if not window:
            bm.faces.new((grid[j][k], grid[j][(k + 1) % SEG], grid[j + 1][(k + 1) % SEG], grid[j + 1][k]))
for k in range(SEG):
    a = 2 * math.pi * k / SEG
    bend = 0.009 * math.exp(-(((a - 2.2 + math.pi) % (2 * math.pi) - math.pi) / 0.4) ** 2)
    for j in range(2, len(HS)):
        v = grid[j][k]
        f = 1.0 - bend * (j - 1) / 3 / RS[j]
        v.co.x *= f
        v.co.y *= f
collar = tk.mesh_object("Collar", bm, paint_rusty)
mod = collar.modifiers.new("Solidify", "SOLIDIFY")
mod.thickness = 0.0028
mod.offset = -1.0
mod.use_even_offset = True
tk.apply_modifiers(collar)
tank.append(tk.smooth(collar, 50))

# Valve: brass body on the boss, black handwheel, the outlet with the regulator's big nut, a relief valve
tank.append(tk.cylinder("ValveBody", 0.0155, 0.343, 0.377, brass, segments=6, bevel_width=0.0015))
tank.append(tk.cylinder("ValveStem", 0.0045, 0.377, 0.386, brass, segments=6))
wheel = tk.cylinder("Handwheel", 0.025, 0.384, 0.393, black, segments=10)
for v in wheel.data.vertices:  # scalloped grip
    a = math.atan2(v.co.y, v.co.x)
    rr = math.hypot(v.co.x, v.co.y)
    if rr > 0.01:
        f = 1.0 - 0.12 * (0.5 + 0.5 * math.cos(5 * a))
        v.co.x *= f
        v.co.y *= f
tank.append(wheel)
tank.append(tk.cylinder("Outlet", 0.0105, 0.0, 0.03, brass, segments=8, center=(0.0, 0.36), axis="X"))
tank.append(tk.cylinder("AcmeNut", 0.019, 0.026, 0.05, black, segments=8, center=(0.0, 0.36), axis="X"))
tank.append(tk.cylinder("Regulator", 0.0085, 0.05, 0.068, brass, segments=8, center=(0.0, 0.36), axis="X"))
relief = tk.cylinder("ReliefValve", 0.0065, 0.0, 0.024, brass, segments=6)
relief.matrix_world = Matrix.Translation((-0.012, 0.0, 0.358)) @ Matrix.Rotation(math.radians(-70), 4, "Y")
relief.data.transform(relief.matrix_world)
relief.matrix_world = Matrix.Identity(4)
tank.append(relief)
# The hose: torn off the regulator's far side, out of the collar window and down the tank's shoulder
HOSE = [(0.066, 0.0, 0.36), (0.094, -0.003, 0.358), (0.122, -0.01, 0.348), (0.141, -0.02, 0.327), (0.146, -0.03, 0.298),
        (0.145, -0.04, 0.27), (0.143, -0.049, 0.248)]
hose_pts = resample(catmull(HOSE, 4), 11)
for i, p in enumerate(hose_pts):  # keep it on the outside of the tank where it hangs against it
    rr = math.hypot(p[0], p[1])
    need = 0.133 + 0.0075 if p[2] < 0.33 else 0.0
    if rr < need:
        hose_pts[i][:2] *= need / rr
local_end = hose_pts[-1].copy()

# ---------------------------------------------------------------- onto the chest

TILT = math.radians(6.0)
ZB = 1.09


def tank_matrix(yb):
    return Matrix.Translation((0.0, yb, ZB)) @ Matrix.Rotation(-TILT, 4, "X")


rigid = [o for o in tank]
local_V = np.array([v.co[:] for o in rigid for v in o.data.vertices])
local_V = np.vstack([local_V, hose_pts])
lo, hi = -0.5, -0.1
for _ in range(30):
    mid = (lo + hi) / 2
    M = np.array(tank_matrix(mid))
    W = local_V @ M[:3, :3].T + M[:3, 3]
    if sdf(W).min() < 0.014:
        hi = mid
    else:
        lo = mid
YB = lo
M = tank_matrix(YB)
hose_mat = rubber_hose("HoseRubber", local_end)
hose = round_tube("Hose", hose_pts, 0.0068, hose_mat, sides=7)
tank.append(hose)
for o in tank:
    local_attr(o)
    o.data.transform(M)
    o.matrix_world = Matrix.Identity(4)
axis_dir = np.array(M.to_3x3() @ Vector((0, 0, 1)))
axis_base = np.array(M @ Vector((0, 0, 0)))

# ---------------------------------------------------------------- ratchet straps round tank and torso


def strap_loop(z, n=40):
    """The taut loop round the tank and the zombie at height z: the convex hull of the tank's cross-section and the
    torso's (pulled 8 mm into the skin), as points with outward normals."""
    pts = []
    t = (z - axis_base[2]) / axis_dir[2]
    c = axis_base + axis_dir * t
    for k in range(48):
        a = 2 * math.pi * k / 48
        pts.append((c[0] + 0.1335 * math.cos(a), c[1] + 0.1335 * math.sin(a) / math.cos(TILT)))
    for th in np.linspace(-math.pi, math.pi, 72, endpoint=False):
        r = float(env(th, z) * squarish(th)) + 0.008
        pts.append((AXIS[0] + r * math.sin(th), AXIS[1] - r * math.cos(th)))
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    H = np.array(lower[:-1] + upper[:-1])
    # resample the hull evenly
    closed = np.vstack([H, H[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    ts = np.linspace(0, s[-1], n, endpoint=False)
    P2 = np.stack([np.interp(ts, s, closed[:, 0]), np.interp(ts, s, closed[:, 1])], axis=1)
    T = np.roll(P2, -1, axis=0) - np.roll(P2, 1, axis=0)
    N2 = np.stack([T[:, 1], -T[:, 0]], axis=1)
    N2 /= np.linalg.norm(N2, axis=1)[:, None]
    cen = P2.mean(axis=0)
    if np.sum(np.einsum("ij,ij->i", N2, P2 - cen)) < 0:
        N2 = -N2
    P = np.column_stack([P2 + N2 * 0.0026, np.full(n, z)])  # half its thickness, and the chords' sag
    N = np.column_stack([N2, np.zeros(n)])
    return P, N


straps = []
SW, ST = 0.032, 0.0022
loops = {}
for zz in (1.205, 1.355):
    P, N = strap_loop(zz)
    loops[zz] = (P, N)
    straps.append(band("Strap%d" % int(zz * 1000), P, N, SW, ST, webbing_mat, closed=True))

# The ratchet on the upper strap, on the tank's front-left, and the strap's loose tail hanging from it
P, N = loops[1.355]
target = np.array([math.sin(math.radians(40)), -math.cos(math.radians(40))])
k = int(np.argmax([(p[:2] - axis_base[:2]) @ target / np.linalg.norm(p[:2] - axis_base[:2]) for p in P]))
p0 = P[k]
tng = P[(k + 1) % len(P)] - P[k - 1]
tng /= np.linalg.norm(tng)
nrm = N[k]
up = np.array([0.0, 0.0, 1.0])
fr = (Vector(p0 + nrm * 0.0012), Vector(tng), Vector(nrm), Vector(up))
straps.append(block("RatchetBase", (0.07, 0.003, 0.04), steel, fr, (0.0, 0.0, 0.0), 0.0))
for s in (1, -1):
    straps.append(block("RatchetSide%+d" % s, (0.066, 0.02, 0.0028), steel, fr, (0.0, 0.0, 0.0205 * s), 0.0))
for s in (1, -1):  # the handle: two arms and a grip bar, open in the middle
    straps.append(block("RatchetArm%+d" % s, (0.052, 0.004, 0.004), steel, fr, (0.012, 0.017, 0.0165 * s), 0.0))
straps.append(block("RatchetGrip", (0.012, 0.007, 0.04), steel, fr, (0.036, 0.0155, 0.0), 0.0))
spool = tk.cylinder("RatchetSpool", 0.0095, -0.0165, 0.0165, webbing_mat, segments=8)  # strap wound on it
gears = [tk.cylinder("RatchetGear%+d" % s, 0.0125, 0.0185 * s - 0.0015, 0.0185 * s + 0.0015, steel, segments=10)
         for s in (1, -1)]
for o in [spool] + gears:
    rot = Matrix((Vector(tng), Vector(nrm), Vector(up))).transposed().to_4x4()
    o.matrix_world = Matrix.Translation(Vector(p0 + nrm * 0.011 - tng * 0.018)) @ rot
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    straps.append(o)
# loose tail: out of the ratchet, hanging down over the tank, curling a little
tail = []
tail_n = []
start = p0 + nrm * 0.006 + tng * 0.03
for i in range(8):
    t = i / 7
    q = start + tng * 0.012 * math.sin(t * 1.6) + np.array([0, 0, -0.13 * t])
    # keep it out on the tank's surface as it hangs
    rel = q - (axis_base + axis_dir * ((q[2] - axis_base[2]) / axis_dir[2]))
    rel[2] = 0
    rr = np.linalg.norm(rel)
    if rr < 0.1335 + 0.003:
        q[:2] += rel[:2] / rr * (0.1335 + 0.003 - rr)
    tail.append(q)
    tail_n.append(rel / max(rr, 1e-6))
straps.append(band("StrapTail", tail, tail_n, SW, ST, webbing_mat))

# ---------------------------------------------------------------- checks, export, previews

for o in tank + straps:
    fix_normals(o)
for o in tank:
    zk.on(o, "Spine2", "Tank")
for o in straps:
    zk.on(o, "Spine2", "Straps")
for group, objs in (("Tank", tank), ("Straps", straps)):
    V = np.array([v.co[:] for o in objs for v in o.data.vertices])
    tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
    print("[propane_tank] %-7s %4d tris, bounds %s %s, closest to the hit boxes %.1f mm" % (
        group, tris, np.round(V.min(0), 3), np.round(V.max(0), 3), sdf(V).min() * 1000))
print("[propane_tank] tank base at y %.3f, tilted %.1f degrees" % (YB, math.degrees(TILT)))

parts = zk.export("PropaneTank", tank + straps, ASSETS)
focus = Vector((0.0, -0.08, 1.32))
zk.previews("propane_tank", PREVIEWS, focus, distance=1.5)
for view, loc, tgt, lens in (("valve", (0.3, -0.75, 1.75), (0.02, -0.2, 1.43), 50),
                             ("label", (0.12, -0.85, 1.32), (0.0, -0.25, 1.3), 50),
                             ("top", (0.05, -0.15, 2.15), (0.0, -0.1, 1.35), 40)):
    tk.render(tk.camera("pt_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "propane_tank_%s.png" % view), res=(900, 900), samples=64)
print("[propane_tank] done")
