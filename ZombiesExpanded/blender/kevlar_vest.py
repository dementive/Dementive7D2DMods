"""Kevlar vest: a police body armor carrier the zombie died in. Padded front and back panels cut like a real vest
(scooped neck, deep armholes, shoulder tabs) and wrapped round Joe's chest hit box with 1.5 cm to spare, padded
shoulder straps over the trapezius, two elastic side straps a side with plastic buckles, a radio pouch with the radio
still in it, a double magazine pouch and a cuff pouch on the front, a drag handle on the back. Black-navy Cordura with
MOLLE webbing low down, "POLICE" printed on a chest patch and big across the back, worn bound edges, dust and dirt,
bullet holes showing the yellow Kevlar inside, and blood: splattered and run down the front from the mouth.

The whole vest is one part on Spine2 (it soaks chest hits and comes off in one piece when it breaks).

    blender -b --factory-startup --python kevlar_vest.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "KevlarVest"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

AXIS = np.array([0.0, 0.05])  # the chest hit box's vertical axis (x, y)
R0 = 0.175  # pattern u (meters along the vest) to angle round the axis
CLEAR = 0.015  # the panels' inner face off the hit boxes
ATTR = "zx_local"  # per-vertex (u, z, edge): pattern coordinates the fabric material prints and binds by


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


# ---------------------------------------------------------------- materials

# POLICE: R the letters, G the chest patch behind them (image covers 0.30 x 0.09 m)
PRINT_BOX = (-0.15, -0.045, 0.15, 0.045)
_shape = (192, 640)
_letters = raster(_shape, PRINT_BOX, fit(glyph_tris("POLICE", "C:/Windows/Fonts/arialbd.ttf", 1.05),
                                         (-0.128, -0.026, 0.128, 0.026)))
_patch = rounded_rect(_shape, PRINT_BOX, (-0.142, -0.04, 0.142, 0.04), 0.01)
PRINT = mask_image("VestPrint", [_letters, _patch, np.zeros(_shape)])
FRONT_PRINT = (0.0, 1.365, 0.62)  # center u, z and scale of the print on the front (patch 17.6 x 5 cm)
BACK_PRINT = (0.0, 1.43, 0.95)  # on the back, bigger and without the patch
HOLES = [(0.035, 1.255, 0), (-0.085, 1.43, 0), (-0.02, 1.47, 0), (0.07, 1.31, 1)]  # bullet holes (u, z, back?)


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


def fabric(name, base, panel=False, scale=1.0, blood_amt=1.0):
    """Cordura: blotchy fading, a fine weave, worn pale edges, dirt and dust, blood. Panels (with the zx_local
    attribute) also get MOLLE webbing, bound edges, the POLICE print and bullet holes."""
    mat, g = tk.new_material(name)
    x, y, z = g.separate(g.coords())
    faded = tuple(c * 1.7 + 0.012 for c in base)
    col = g.mix(g.ramp(g.noise(6.0, detail=5.0, distortion=0.3), 0.32, 0.82), base, faded)
    weave = g.noise(240.0 * scale, detail=2.0)
    col = g.mix(g.math("MULTIPLY", weave, 0.4), col, tk._darker(g, col, 0.65))
    height = g.math("MULTIPLY", weave, 0.25)
    rough = g.math("ADD", 0.8, g.math("MULTIPLY", weave, 0.1))
    front = g.ramp(y, 0.06, 0.03)
    metal = 0.0
    if panel:
        u, v, e = attr_uvw(g)
        absu = g.math("ABSOLUTE", u)
        # MOLLE: 2.5 cm webbing rows with bar-tacks every 3.8 cm, over the lower front and back
        row = g.math("FRACT", g.math("DIVIDE", g.math("SUBTRACT", v, 1.145), 0.05))
        web = g.math("MULTIPLY", g.ramp(row, 0.02, 0.07), g.ramp(row, 0.52, 0.47))
        region = g.math("MULTIPLY", g.ramp(v, 1.14, 1.16), g.ramp(v, 1.31, 1.29))
        region = g.math("MULTIPLY", region, g.ramp(absu, 0.185, 0.17))
        region = g.math("MULTIPLY", region, g.ramp(e, 0.9, 1.0))
        web = g.math("MULTIPLY", web, region)
        tack = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", u, 0.038)), 0.5)), 0.45, 0.49)
        gap = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("MAXIMUM", web, g.math("SUBTRACT", 1.0, region))), 0.7)
        col = g.mix(gap, col, tuple(c * 0.5 for c in base))
        col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", web, tack), 0.35), col, tuple(c * 0.6 for c in base))
        height = g.math("ADD", height, g.math("MULTIPLY", g.math("SUBTRACT", web, g.math("MULTIPLY", web, tack)), 0.9))
        # Bound edges: a darker, glossier tape round every cut edge with a stitch line inside it
        bind = g.ramp(e, 0.97, 0.75)
        col = g.mix(bind, col, tuple(c * 0.75 for c in base))
        rough = g.mixf(bind, rough, 0.62)
        stitch = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", e, 0.985)), 0.012, 0.0),
                        g.ramp(g.math("FRACT", g.math("DIVIDE", g.math("ADD", u, v), 0.006)), 0.3, 0.5))
        col = g.mix(g.math("MULTIPLY", stitch, 0.5), col, tuple(c * 2.0 for c in base))
        # The print: a patch with white letters on the front, big letters across the back
        fu, fz, fs = FRONT_PRINT
        bu, bz, bs = BACK_PRINT
        lf, pf, _ = decal(g, PRINT, u, v, (fu + PRINT_BOX[0] * fs, fz + PRINT_BOX[1] * fs, fu + PRINT_BOX[2] * fs,
                                           fz + PRINT_BOX[3] * fs))
        lb, _, _ = decal(g, PRINT, u, v, (bu + PRINT_BOX[0] * bs, bz + PRINT_BOX[1] * bs, bu + PRINT_BOX[2] * bs,
                                          bz + PRINT_BOX[3] * bs))
        back = g.math("SUBTRACT", 1.0, front)
        patch = g.math("MULTIPLY", pf, front)
        letters = g.math("ADD", g.math("MULTIPLY", lf, front), g.math("MULTIPLY", lb, back))
        cracked = g.ramp(g.noise(55.0, detail=8.0, roughness=0.7), 0.6, 0.66)
        scuffed = g.ramp(g.noise(7.0, detail=6.0, distortion=0.5), 0.62, 0.72)
        letters = g.math("MULTIPLY", letters, g.math("SUBTRACT", 1.0, g.math("MAXIMUM", cracked, scuffed)))
        col = g.mix(patch, col, (0.012, 0.012, 0.014))
        rough = g.mixf(patch, rough, 0.6)
        print_col = g.mix(g.ramp(g.noise(12.0), 0.3, 0.7), (0.62, 0.62, 0.6), (0.46, 0.45, 0.42))
        col = g.mix(letters, col, print_col)
        rough = g.mixf(letters, rough, 0.5)
        height = g.math("ADD", height, g.math("MULTIPLY", g.math("ADD", patch, letters), 0.2))
        # Bullet holes: black, ringed with frayed yellow Kevlar fibre
        for hu, hz, hb in HOLES:
            cv = g.node("ShaderNodeCombineXYZ")
            g.links.new(u, cv.inputs[0])
            g.links.new(v, cv.inputs[1])
            dist = g.node("ShaderNodeVectorMath", operation="DISTANCE")
            g.links.new(cv.outputs[0], dist.inputs[0])
            dist.inputs[1].default_value = (hu, hz, 0.0)
            dd = tk._sock(dist.outputs, "Value")
            side = back if hb else front
            ragged = g.math("ADD", dd, g.math("MULTIPLY", g.noise(420.0, detail=4.0, roughness=0.8), 0.009))
            fray = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(ragged, 0.0135, 0.0095),
                                             g.ramp(g.noise(160.0, detail=3.0), 0.35, 0.6)), side)
            hole = g.math("MULTIPLY", g.ramp(g.math("ADD", dd, g.math("MULTIPLY", g.noise(300.0), 0.003)), 0.0068,
                                             0.0052), side)
            scorch = g.math("MULTIPLY", g.ramp(dd, 0.02, 0.008), side)
            col = g.mix(g.math("MULTIPLY", scorch, 0.6), col, (0.01, 0.009, 0.008))
            col = g.mix(fray, col, (0.36, 0.26, 0.06))
            # the slug that stopped in the Kevlar: a flattened grey lead mushroom
            lead = g.mix(g.ramp(g.noise(200.0, detail=3.0), 0.3, 0.7), (0.2, 0.2, 0.21), (0.42, 0.42, 0.43))
            col = g.mix(hole, col, lead)
            rough = g.mixf(fray, rough, 0.9)
            rough = g.mixf(hole, rough, 0.42)
            metal = g.mixf(hole, metal, 0.75)
            height = g.math("ADD", height, g.math("SUBTRACT", g.math("MULTIPLY", hole, 0.8), g.math("MULTIPLY", fray, 0.5)))
    # Abrasion: pale scuffed fibre on edges and corners
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.1, 0.35), g.ramp(g.noise(25.0, detail=4.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", worn, 0.75), col, tuple(c * 3.2 + 0.05 for c in base))
    # Dirt from a photo's dark parts, heavier toward the hem, and grime in creases
    p = tk.photo(g, "rust_coarse_01", 1.6 * scale, (0.31, 0.6, 0.17))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.22, 0.07), g.mixf(g.ramp(z, 1.3, 1.12), 0.35, 0.8))
    dirt = g.math("MAXIMUM", dirt, tk._grime(g, 0.6))
    col = g.mix(g.math("MULTIPLY", dirt, 0.55), col, (0.075, 0.064, 0.05))
    rough = g.mixf(dirt, rough, 0.92)
    # Blood: mostly down the front from the mouth, some everywhere
    region = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", g.ramp(z, 1.15, 1.5), front), 0.3), blood_amt)
    col, rough, height = blood(g, col, rough, height, region)
    col, rough, metal = tk._grit(g, col, rough, metal, 0.32)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.003))


NAVY = (0.013, 0.016, 0.023)
cloth = fabric("VestCloth", NAVY, panel=True)
strap_cloth = fabric("VestStrap", NAVY, scale=1.4)
pouch_cloth = fabric("VestPouch", tuple(c * 1.35 for c in NAVY), scale=1.2, blood_amt=1.3)
elastic = fabric("VestElastic", (0.018, 0.018, 0.02), scale=2.0, blood_amt=0.6)
plastic = tk.grimy("VestBuckle", (0.02, 0.02, 0.021), roughness=0.42, grime=0.7, grit=0.6)
radio_mat = tk.grimy("VestRadio", (0.028, 0.029, 0.03), roughness=0.5, grime=0.8, grit=0.7,
                     stain=(0.09, 0.01, 0.008))


# ---------------------------------------------------------------- the panels

def vest_outline(US, Z_ARM, Z_TOP, UT1, UT0, Z_NECK, ZB):
    """Half a vest panel pattern mirrored: hem, side, armhole, shoulder tab, neck scoop (u across, z up)."""
    right = [(US * i / 10, ZB + 0.012 * (i / 10) ** 2) for i in range(11)]
    right.append((US, Z_ARM))
    a, b = US - UT1, Z_TOP - Z_ARM
    right += [(US + a * math.cos(t), Z_TOP + b * math.sin(t))
              for t in np.linspace(-math.pi / 2, -math.pi, 14)[1:]]
    right.append((UT0, Z_TOP))
    c = Z_TOP - Z_NECK
    right += [(UT0 * math.cos(t), Z_TOP + c * math.sin(t)) for t in np.linspace(0, -math.pi / 2, 14)[1:]]
    left = [(-u, z) for u, z in reversed(right[1:-1])]
    return right + left


def front_3d(P):
    return wrap(P[:, 0] / R0, P[:, 1])


def back_3d(P):
    return wrap(math.pi + P[:, 0] / R0, P[:, 1])


THICK = 0.013
front = panel("FrontPanel", vest_outline(0.235, 1.30, 1.545, 0.188, 0.112, 1.462, 1.115), front_3d, cloth, THICK)
back = panel("BackPanel", vest_outline(0.235, 1.27, 1.562, 0.162, 0.108, 1.528, 1.115), back_3d, cloth, THICK)
panels_tree = bvh([front, back])
pieces = [front, back]


# Shoulder straps: padded, from the front tab over the trapezius to the back tab, pulled taut
def shoulder_strap(side):
    x = 0.121 * side
    c = np.array([x, 0.06, 1.45])
    psis = np.radians(np.linspace(-66.0, 55.0, 17))
    dirs = [np.array([0.0, math.sin(p), math.cos(p)]) for p in psis]
    ts = []
    for d in dirs:
        tb = shell_exit(c, d, CLEAR, ("Spine2", "LeftArm", "RightArm"))  # the head's box is wider than the neck
        tp = far_hit(panels_tree, Vector(c), Vector(d))
        ts.append(max(tb, tp + 0.0015 if tp else 0.0))
    ts = taut(np.array([0.06, 1.45]), [np.array([d[1], d[2]]) for d in dirs], ts)
    ts = smooth1d(ts, 2) + 0.0055
    pts = np.array([c + d * t for d, t in zip(dirs, ts)])
    # Roll the strap to the slope of the shoulder (the hit boxes' gradient), then lift it wherever an edge digs in
    bones = ("Spine2", "LeftArm", "RightArm")
    e = 1e-3
    gr = np.stack([sdf(pts + dv, bones) - sdf(pts - dv, bones) for dv in np.eye(3) * e], axis=1)
    gr /= np.linalg.norm(gr, axis=1)[:, None]
    nrms = np.array(dirs) + gr
    nrms /= np.linalg.norm(nrms, axis=1)[:, None]
    w, th = 0.047, 0.011
    for _ in range(3):
        for i in range(len(pts)):
            tng = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            tng /= np.linalg.norm(tng)
            W = np.cross(tng, nrms[i])
            W /= np.linalg.norm(W)
            probe = np.array([pts[i] + W * k * w / 2 - nrms[i] * th / 2 for k in (-1, 0, 1)])
            short = CLEAR - sdf(probe, bones).min()
            if short > 0:
                pts[i] = pts[i] + nrms[i] * short
    return band("ShoulderStrap%+d" % side, pts, nrms, w, th, strap_cloth, profile=PADDED)


pieces += [shoulder_strap(1), shoulder_strap(-1)]


# Side straps: elastic, two a side, from the front panel round the flank to the back panel
def side_strap(side, z):
    ths = np.radians(np.linspace(58.0, 122.0, 12)) * side
    dirs = [np.array([math.sin(t), -math.cos(t), 0.0]) for t in ths]
    o = np.array([AXIS[0], AXIS[1], z])
    ts = []
    for th, d in zip(ths, dirs):
        tb = env(th, z) * squarish(th) + 0.011
        tp = far_hit(panels_tree, Vector(o), Vector(d))
        ts.append(max(tb, tp + 0.001 if tp else 0.0))
    ts = taut(AXIS, [d[:2] for d in dirs], ts) + 0.0035
    pts = [o + d * t for d, t in zip(dirs, ts)]
    strap = band("SideStrap%+d_%d" % (side, int(z * 100)), pts, dirs, 0.042, 0.006, elastic)
    # A side-release buckle where the strap rounds the flank
    k = len(pts) // 2 + 1
    tng = Vector(pts[k + 1] - pts[k - 1]).normalized()
    nrm = Vector(dirs[k])
    up = nrm.cross(tng).normalized()
    if up.z < 0:
        up = -up
    sidev = up.cross(nrm).normalized()
    fr = (Vector(pts[k]) + nrm * 0.003, sidev, nrm, up)
    buckle = [block("Buckle%+d_%d" % (side, int(z * 100)), (0.05, 0.01, 0.05), plastic, fr, (0.0, 0.0, 0.0), 0.004)]
    return [strap] + buckle


for s in (1, -1):
    pieces += side_strap(s, 1.172)
    pieces += side_strap(s, 1.258)

front_tree = bvh([front])
back_tree = bvh([back])


def pouch(name, u, z, w, h, d, flaps=1, tilt=0.0):
    fr = frame_at(front_tree, u, z)
    out = [block(name, (w, d, h), pouch_cloth, fr, (0.0, -0.004, 0.0), 0.01, tilt, taper=0.9, segments=2)]
    fw = w / flaps
    for k in range(flaps):
        out.append(block(name + "Flap%d" % k, (fw - 0.003, 0.006, 0.042), pouch_cloth, fr,
                         (-w / 2 + fw * (k + 0.5), d - 0.0045, h / 2 - 0.016), 0.0025, tilt))
    return out


# Lower front: a double pistol-magazine pouch and a handcuff pouch
pieces += pouch("MagPouch", -0.1, 1.215, 0.082, 0.1, 0.028, flaps=2)
pieces += pouch("CuffPouch", 0.098, 1.205, 0.072, 0.082, 0.032)
# Upper left chest: the radio pouch, the radio sticking out of it, its stubby antenna
fr = frame_at(front_tree, 0.122, 1.43)
pieces.append(block("RadioPouch", (0.064, 0.036, 0.1), pouch_cloth, fr, (0.0, -0.004, -0.02), 0.006, -6.0))
pieces.append(block("Radio", (0.054, 0.03, 0.06), radio_mat, fr, (0.003, -0.001, 0.045), 0.005, -6.0))
p, sv, nv, uv = fr
rot = Matrix.Rotation(math.radians(-6.0), 3, nv)
ant_base = p + nv * 0.018 + (rot @ uv) * 0.074 + (rot @ sv) * 0.016
ant = tk.cylinder("Antenna", 0.0055, 0.0, 0.085, radio_mat, segments=8, radius_top=0.0035)
ant.matrix_world = Matrix.Translation(ant_base) @ Vector((0, 0, 1)).rotation_difference(rot @ uv).to_matrix().to_4x4()
knob = tk.cylinder("RadioKnob", 0.0065, 0.0, 0.012, radio_mat, segments=8)
knob.matrix_world = (Matrix.Translation(ant_base - (rot @ sv) * 0.028)
                     @ Vector((0, 0, 1)).rotation_difference(rot @ uv).to_matrix().to_4x4())
pieces += [ant, knob]
for o in (ant, knob):
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)

# Drag handle: a webbing loop at the top of the back panel
hp = []
hn = []
for i in range(9):
    t = i / 8
    pp, sv, nv, uv = frame_at(back_tree, -0.045 + 0.09 * t, 1.497, back=True)
    lift = 0.004 + 0.022 * math.sin(math.pi * t)
    hp.append(pp + nv * lift)
    hn.append(nv)
pieces.append(band("DragHandle", hp, hn, 0.03, 0.005, strap_cloth))
for i, (u0, u1) in enumerate(((-0.052, -0.03), (0.03, 0.052))):
    pieces.append(block("HandleTab%d" % i, (0.026, 0.004, 0.034), strap_cloth, frame_at(back_tree, (u0 + u1) / 2, 1.497, back=True),
                        (0.0, -0.001, 0.0), 0.002))

# ---------------------------------------------------------------- checks, export, previews

for o in pieces:
    fix_normals(o)
for o in pieces:
    zk.on(o, "Spine2")
    print("[kevlar_vest] tris %-22s %d" % (o.name, sum(len(f.vertices) - 2 for f in o.data.polygons)))
allv = np.array([v.co[:] for o in pieces for v in o.data.vertices])
for o in pieces:
    V = np.array([v.co[:] for v in o.data.vertices])
    m = sdf(V).min()
    if m < 0.008:
        print("[kevlar_vest] %s comes within %.1f mm of the hit boxes" % (o.name, m * 1000))
print("[kevlar_vest] closest to the body: %.1f mm (arms %.1f mm, head %.1f mm)" % (
    sdf(allv).min() * 1000, sdf(allv, ("LeftArm", "RightArm")).min() * 1000, sdf(allv, ("Head",)).min() * 1000))
print("[kevlar_vest] bounds", np.round(allv.min(0), 3), np.round(allv.max(0), 3))

parts = zk.export("KevlarVest", pieces, ASSETS)
focus = Vector((0.0, 0.03, 1.33))
zk.previews("kevlar_vest", PREVIEWS, focus, distance=1.35)
for view, loc, tgt, lens in (("close", (0.22, -0.62, 1.5), (0.0, -0.05, 1.33), 50),
                             ("top", (0.42, -0.3, 2.05), (0.08, 0.05, 1.5), 45),
                             ("armpit", (0.75, 0.05, 1.12), (0.12, 0.05, 1.38), 50)):
    tk.render(tk.camera("kv_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "kevlar_vest_%s.png" % view), res=(900, 900), samples=64)
print("[kevlar_vest] done")
