"""Scrap armor: survivor-made armor scavenged from junk and wired on, which the zombie still wears.

- Chest: an 18 inch stop sign, its top snipped off round the throat, bent round the chest and belly (a stiff sheet:
  straight top to bottom, leaning back over the dome of the chest), the red sheeting faded and peeling to aluminum,
  shot through, rust run down from the wire. It hangs from two loops of seatbelt webbing that run from its top over
  each shoulder, down the back and round under the arm onto its side, wired on through punched holes.
- Back: a sheet of corrugated iron, old grey paint peeling off red primer and rust, bent round the back with one
  corner snipped off, stitched with baling wire where the seatbelts run under it.
- Pads: a chrome hubcap over each shoulder, wired round the upper arm.

Each plate breaks off on its own, so each is its own part with the wire and webbing that hold it: Spine2#Chest,
Spine2#Back, LeftArm#Pad and RightArm#Pad (the hubcaps ride the upper arm bone and swing with it).

    blender -b --factory-startup --python scrap_armor.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "ScrapArmor"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

AXIS = np.array([0.0, 0.05])  # the chest hit box's vertical axis (x, y)
R0 = 0.175  # pattern u (meters along a piece) to angle round the axis
CLEAR = 0.015  # straps' inner face off the hit boxes
ATTR = "zx_local"  # per-vertex coordinates the materials print by (pattern u, z for the sign; local for the hubcaps)

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


def panel(name, poly, to3d, mat, thick, edge_thick=0.004, inset=0.008, dense=0.04, sparse=0.085, round_r=0.006):
    """A padded panel cut to the 2D pattern `poly` (u, z) and laid on the body by to3d(u, z) -> inner-face points:
    the outer face rises from edge_thick at the cut edge to `thick` an `inset` in (a rolled, bound edge)."""
    O = outline(poly, round_r=round_r)
    n0 = len(O)
    # Inset ring (the rolled edge), inward along the outline's left normal
    T = np.roll(O, -1, axis=0) - np.roll(O, 1, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    I = O + np.stack([-T[:, 1], T[:, 0]], axis=1) * inset
    inner_pts = _lattice(O, dense, max(0.7 * dense, inset + 0.012))
    ring = list(I) if inset else []
    v_out, f_out, s_out = _cdt(list(O) + ring + list(inner_pts), [n0, n0] if inset else [n0])
    if sparse:
        v_in, f_in, s_in = _cdt(list(O) + list(_lattice(O, sparse, 0.6 * sparse)), [n0])
    else:  # a thin sheet: the back face is the front face's own triangles, so neither pokes through the other
        v_in, f_in, s_in = v_out, f_out, s_out

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



# ---------------------------------------------------------------- sheet metal bent round the body

def ruled(th0, th1, z0, z1, clear, p=2.15):
    """A stiff sheet bent round the body: straight lines from z0 to z1 at each angle (it can lean, it can't follow
    the chest's dome), pushed out until it clears the torso by `clear`. Returns radius(theta, z)."""
    ths = np.linspace(th0, th1, 121)
    zs = np.linspace(z0, z1, 40)
    T, Z = np.meshgrid(ths, zs, indexing="ij")
    need = env(T, Z) * squarish(T, p) + clear
    rb, rt = need[:, 0].copy(), need[:, -1].copy()
    t = (zs - z0) / (z1 - z0)
    lift = (need - (rb[:, None] + (rt - rb)[:, None] * t[None])).max(axis=1).clip(0)
    rb, rt = smooth1d(rb + lift, 8) + 0.002, smooth1d(rt + lift, 8) + 0.002

    def radius(th, z):
        a, b = np.interp(th, ths, rb), np.interp(th, ths, rt)
        return a + (b - a) * (np.asarray(z) - z0) / (z1 - z0)
    return radius


def at(th, z, r):
    th, z, r = np.broadcast_arrays(np.asarray(th, float), np.asarray(z, float), np.asarray(r, float))
    return np.stack([AXIS[0] + r * np.sin(th), AXIS[1] - r * np.cos(th), z], axis=-1)


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


def fit_box(tris, box):
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    s = np.array([(box[2] - box[0]) / (hi[0] - lo[0]), (box[3] - box[1]) / (hi[1] - lo[1])])
    return (tris - lo) * s + np.array([box[0], box[1]])


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


def shell_first(origin, d, clear, bones=None, bridge=0.02, maxd=0.45):
    """Where a ray from inside the torso first gets `clear` of the hit boxes, bridging gaps under `bridge` (the
    crease between chest and shoulder) but not reaching past an arm it would only pass by."""
    t = np.arange(0.0, maxd, 0.0015)
    P = np.asarray(origin)[None] + t[:, None] * np.asarray(d)[None]
    inside = sdf(P, bones) < clear
    end, k = 0.0, 0
    while k < len(t) and inside[k]:
        k += 1
    end = t[min(k, len(t) - 1)]
    while k < len(t):
        j = k
        while j < len(t) and not inside[j]:
            j += 1
        if j >= len(t) or t[j] - t[k] > bridge:
            break
        while j < len(t) and inside[j]:
            j += 1
        end, k = t[min(j, len(t) - 1)], j
    return end


def core(p):
    """The nearest point on the chest hit box's axis, where straps are pushed out from."""
    return np.array([AXIS[0], AXIS[1], min(max(p[2], 1.2), 1.46)])


BODY = ("Spine2", "LeftArm", "RightArm", "Hips")


def drape(ctrl, n, trees, clear, half, gap=0.002, iters=8):
    """A strap through control points, laid on the body (and on any pieces in `trees`) and pulled taut: each point
    sits on the last thing its ray from the chest axis passes, `half` out."""
    P = resample(catmull(ctrl), n)

    def need(p):
        q = core(p)
        d = p - q
        d /= np.linalg.norm(d)
        t = shell_first(q, d, clear, BODY)
        for tree in trees:
            h = far_hit(tree, Vector(q), Vector(d))
            if h:
                t = max(t, h + gap)
        return q, d, t + half

    for it in range(iters + 1):
        if it:
            P[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
        for i in range(n):
            q, d, t = need(P[i])
            if it == 0 or np.linalg.norm(P[i] - q) < t:
                P[i] = q + d * t
    D = np.array([(p - core(p)) / np.linalg.norm(p - core(p)) for p in P])
    e = 1e-3
    gr = np.stack([sdf(P + dv, BODY) - sdf(P - dv, BODY) for dv in np.eye(3) * e], axis=1)
    gr /= np.linalg.norm(gr, axis=1)[:, None]
    N = D + gr
    N /= np.linalg.norm(N, axis=1)[:, None]
    return P, N


def settle(P, N, width, thick, clear, bones=BODY):
    """Lifts a strap wherever its edges dig into the hit boxes."""
    for _ in range(3):
        for i in range(len(P)):
            tng = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            tng /= np.linalg.norm(tng)
            W = np.cross(tng, N[i])
            W /= np.linalg.norm(W)
            probe = np.array([P[i] + W * k * width / 2 - N[i] * thick / 2 for k in (-1, 0, 1)])
            short = clear - sdf(probe, bones).min()
            if short > 0:
                P[i] = P[i] + N[i] * short
    return P


def transported(P, closed=False):
    """Cross-section frames carried along a path without twisting (so a round wire stays round)."""
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


def wire(name, pts, mat, radius=0.0016, sides=3, closed=False):
    P = np.array(pts, float)
    nrms = transported(P, closed)
    return band(name, P, nrms, radius * 2.0, radius * 2.0, mat,
                profile=[(0.5 * math.cos(2 * math.pi * k / sides), 0.5 * math.sin(2 * math.pi * k / sides))
                         for k in range(sides)], closed=closed)


def twist(name, base, direction, mat, length=0.022, radius=0.0016, turns=2.5):
    """The twisted-off end of a wire tie: a short tight helix sticking out."""
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    a = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
    a /= np.linalg.norm(a)
    b = np.cross(d, a)
    pts = []
    for k in range(6):
        t = k / 5
        ph = 2 * math.pi * turns * t
        pts.append(np.asarray(base) + d * length * t + (a * math.cos(ph) + b * math.sin(ph)) * radius * 0.9 * (1 - 0.5 * t))
    return wire(name, pts, mat, radius * 0.9)


# ---------------------------------------------------------------- the stop sign (chest plate)

ZC, HF = 1.335, 0.2285  # sign center and half its width across flats (an 18 inch stop sign)
SF = HF * math.tan(math.radians(22.5))
RS = 0.198  # pattern u to angle round the body for the sign
SIGN_BOX = (-HF, ZC - HF, HF, ZC + HF)


def octagon(inset=0.0):
    h, s = HF - inset, (HF - inset) * math.tan(math.radians(22.5))
    return [(s, ZC - h), (h, ZC - s), (h, ZC + s), (s, ZC + h), (-s, ZC + h), (-h, ZC + s), (-h, ZC - s), (-s, ZC - h)]


def cut_line(u):
    """Where the survivor cut the sign's top off, round the throat: snipped, a little ragged."""
    return 1.503 - 0.024 * math.exp(-(u / 0.06) ** 2) + 0.0022 * math.sin(u * 157.0) + 0.0012 * math.sin(u * 433.0 + 1.3)


def sign_outline():
    D = _dense(octagon(), 0.003)
    D = _smooth_closed(D, 0.012 / 0.003)  # stop signs have rounded corners
    out = [(u, min(z, cut_line(u))) for u, z in D]
    return out[::3]


# Wire ties through punched holes (pattern u, z on the sign); straps end under them
TIES = []
for s in (1, -1):
    TIES.append(((0.104 * s - 0.03, 1.452), (0.104 * s + 0.03, 1.452)))  # over the shoulder strap's front end
    TIES.append(((0.192 * s, 1.27), (0.192 * s, 1.33)))  # over the strap's end coming round the flank
SIGN_HOLES = [p for t in TIES for p in t] + [(0.0, ZC - 0.19)]  # and the sign's own lower mounting hole
SIGN_SHOTS = [(0.052, 1.372), (-0.135, 1.215), (0.16, 1.17)]
DENTS = [(0.12, 1.2, 0.055, 0.006), (-0.075, 1.43, 0.045, 0.004), (-0.17, 1.31, 0.06, 0.005), (0.05, 1.29, 0.08, 0.003)]
sign_r = ruled(-1.3, 1.3, 1.1, 1.505, 0.022)


def sign_3d(P, lift=0.0):
    u, z = P[:, 0], P[:, 1]
    th = u / RS
    r = sign_r(th, z) + lift
    for du, dz, rad, depth in DENTS:
        r = r - depth * np.exp(-((u - du) ** 2 + (z - dz) ** 2) / (rad * rad))
    r = r + 0.0015 * np.sin(u * 23.0 + z * 9.0)
    return at(th, z, r)


def sign_image():
    shape = (1024, 1024)
    border = np.clip(poly_fill(shape, SIGN_BOX, octagon(0.008)) - poly_fill(shape, SIGN_BOX, octagon(0.019)), 0, 1)
    tris = fit_box(glyph_tris("STOP", "C:/Windows/Fonts/ARIALNB.TTF", 1.08), (-0.168, ZC - 0.076, 0.168, ZC + 0.076))
    letters = raster(shape, SIGN_BOX, tris)
    return mask_image("StopSign", [np.clip(border + letters, 0, 1), np.zeros(shape), np.zeros(shape)])


SIGN_IMG = sign_image()


def spots(g, u, v, points):
    """Distance to the nearest of several pattern points."""
    best = None
    for pu, pv in points:
        cv = g.node("ShaderNodeCombineXYZ")
        g.links.new(u, cv.inputs[0])
        g.links.new(v, cv.inputs[1])
        dist = g.node("ShaderNodeVectorMath", operation="DISTANCE")
        g.links.new(cv.outputs[0], dist.inputs[0])
        dist.inputs[1].default_value = (pu, pv, 0.0)
        d = tk._sock(dist.outputs, "Value")
        best = d if best is None else g.math("MINIMUM", best, d)
    return best


def outward(g):
    """1 on faces turned away from the body (the sign's painted face), 0 on the inside."""
    x, y, z = g.separate(g.coords())
    radial = g.node("ShaderNodeCombineXYZ")
    g.links.new(x, radial.inputs[0])
    g.links.new(g.math("SUBTRACT", y, AXIS[1]), radial.inputs[1])
    unit = g.node("ShaderNodeVectorMath", operation="NORMALIZE")
    g.links.new(radial.outputs[0], unit.inputs[0])
    dot = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.links.new(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"), dot.inputs[0])
    g.links.new(unit.outputs[0], dot.inputs[1])
    return g.ramp(tk._sock(dot.outputs, "Value"), -0.2, 0.2)


def sign_paint(name):
    """Faded red reflective sheeting with the white border and STOP, peeling in flakes to dull aluminum, scratched,
    rust run down from the steel wire ties, shot through twice, grimy and bloodied. The back is bare aluminum."""
    mat, g = tk.new_material(name)
    x, y, z = g.separate(g.coords())
    u, v, _ = attr_uvw(g)
    white, _, _ = decal(g, SIGN_IMG, u, v, SIGN_BOX)
    face = outward(g)
    red = g.mix(g.ramp(g.noise(3.0, detail=5.0, distortion=0.4), 0.3, 0.75), (0.4, 0.016, 0.014), (0.5, 0.07, 0.055))
    wh = g.mix(g.ramp(g.noise(9.0, detail=4.0), 0.3, 0.7), (0.66, 0.64, 0.58), (0.52, 0.5, 0.45))
    paint = g.mix(white, red, wh)
    alu = g.mix(g.ramp(g.noise(14.0, detail=6.0), 0.3, 0.7), (0.44, 0.45, 0.46), (0.3, 0.31, 0.32))
    # Peeling sheeting: blotchy flakes, worse at the cut and bent edges and round the holes
    flakes = g.ramp(g.noise(4.5, detail=9.0, roughness=0.7, distortion=0.5), 0.6, 0.625)
    edge = g.math("MULTIPLY", g.ramp(g.edges(0.01), 0.05, 0.25), g.ramp(g.noise(18.0, detail=6.0), 0.3, 0.55))
    near = g.ramp(spots(g, u, v, SIGN_HOLES), 0.016, 0.008)
    peel = g.math("MAXIMUM", g.math("MAXIMUM", flakes, edge), near)
    lifted = g.math("MULTIPLY", g.ramp(g.noise(4.5, detail=9.0, roughness=0.7, distortion=0.5), 0.585, 0.6),
                    g.math("SUBTRACT", 1.0, peel))
    peel = g.math("MAXIMUM", peel, g.math("SUBTRACT", 1.0, face))
    col = g.mix(peel, paint, alu)
    col = g.mix(g.math("MULTIPLY", lifted, 0.5), col, (0.06, 0.04, 0.035))
    metal = g.math("MULTIPLY", peel, 0.85)
    rough = g.mixf(peel, g.mixf(white, 0.42, 0.5), 0.48)
    height = g.math("SUBTRACT", 0.5, g.math("MULTIPLY", peel, 0.5))
    # Punched holes (dark, ringed with bright torn metal) and rust run down from the wire through them
    dh = spots(g, u, v, SIGN_HOLES)
    ring = g.math("MULTIPLY", g.ramp(dh, 0.0075, 0.005), g.math("SUBTRACT", 1.0, g.ramp(dh, 0.0045, 0.0035)))
    hole = g.ramp(dh, 0.0042, 0.0032)
    run = None
    for pu, pv in SIGN_HOLES:
        w = g.math("ADD", 0.003, g.math("MULTIPLY", g.math("SUBTRACT", pv, v), 0.06))
        s = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", u, pu)), w, g.math("MULTIPLY", w, 0.3)),
                   g.math("MULTIPLY", g.ramp(v, pv + 0.002, pv - 0.004), g.ramp(v, pv - 0.13, pv - 0.03)))
        run = s if run is None else g.math("MAXIMUM", run, s)
    run = g.math("MULTIPLY", run, g.ramp(g.noise(30.0, detail=5.0), 0.3, 0.6))
    col = g.mix(g.math("MULTIPLY", run, 0.75), col, (0.2, 0.075, 0.025))
    rough = g.mixf(run, rough, 0.8)
    col = g.mix(ring, col, (0.55, 0.55, 0.56))
    metal = g.mixf(ring, metal, 0.9)
    col = g.mix(hole, col, (0.01, 0.009, 0.008))
    # Bullet holes: a black hole in a crater of bare, torn aluminum
    ds = spots(g, u, v, SIGN_SHOTS)
    shot = g.ramp(g.math("ADD", ds, g.math("MULTIPLY", g.noise(260.0, detail=4.0), 0.004)), 0.013, 0.008)
    col = g.mix(shot, col, (0.5, 0.5, 0.51))
    metal = g.mixf(shot, metal, 0.9)
    rough = g.mixf(shot, rough, 0.3)
    col = g.mix(g.ramp(ds, 0.0052, 0.0042), col, (0.008, 0.007, 0.006))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.ramp(ds, 0.014, 0.0), 1.5))
    # Grime in creases and from the photo's dark parts, then blood, dust and scratches
    p = tk.photo(g, "rust_coarse_01", 1.4, (0.13, 0.71, 0.29))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.2, 0.06), 0.6), tk._grime(g, 0.7))
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.07, 0.055, 0.04))
    rough = g.mixf(dirt, rough, 0.85)
    col, rough, height = blood(g, col, rough, height, g.math("ADD", g.math("MULTIPLY", g.ramp(z, 1.25, 1.5), 0.9), 0.25))
    col, rough, metal = tk._grit(g, col, rough, metal, 0.45, scratches=0.12, edges=0.2)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.002))


def webbing(name, base):
    """Seatbelt webbing: tight twill (fine stripes), grimy and bloodied."""
    mat, g = tk.new_material(name)
    x, y, z = g.separate(g.coords())
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (500.0, 500.0, 500.0)
    m.inputs["Rotation"].default_value = (0.6, 0.4, 0.9)
    wave = g.node("ShaderNodeTexWave", wave_type="BANDS")
    g._in(wave, "Scale", 1.0)
    g._in(wave, "Distortion", 2.0)
    g.links.new(m.outputs[0], wave.inputs["Vector"])
    twill = tk._sock(wave.outputs, "Fac")
    col = g.mix(g.math("MULTIPLY", twill, 0.3), base, tuple(c * 0.6 for c in base))
    col = g.mix(g.ramp(g.noise(5.0, detail=5.0), 0.3, 0.8), col, tuple(c * 1.8 for c in base))
    rough = g.math("ADD", 0.62, g.math("MULTIPLY", twill, 0.12))
    height = g.math("MULTIPLY", twill, 0.3)
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.1, 0.4), g.ramp(g.noise(30.0, detail=4.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", worn, 0.7), col, tuple(c * 3.0 + 0.04 for c in base))
    p = tk.photo(g, "rust_coarse_01", 2.0, (0.5, 0.2, 0.33))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.22, 0.07), 0.6), tk._grime(g, 0.6))
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.08, 0.068, 0.052))
    rough = g.mixf(dirt, rough, 0.9)
    col, rough, height = blood(g, col, rough, height, g.math("ADD", g.math("MULTIPLY", g.ramp(z, 1.3, 1.6), 0.7), 0.25))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.4)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.002))


def chrome(name):
    """A worn chrome hubcap (zx_local holds its own frame: x, y across, h up its axis): silver-painted outer ring with
    eight vent slots, chrome center dome with a dark emblem, scratched, rust-pitted at the rim, grimy in the
    recesses, bloodied."""
    mat, g = tk.new_material(name)
    hx, hy, hh = attr_uvw(g)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", hx, hx), g.math("MULTIPLY", hy, hy)))
    ang = g.math("DIVIDE", g.math("ARCTAN2", hy, hx), 2 * math.pi)
    smudge = g.ramp(g.noise(6.0, detail=6.0, distortion=0.4), 0.35, 0.7)
    chrome_col = g.mix(smudge, (0.72, 0.72, 0.74), (0.5, 0.5, 0.52))
    painted = g.mix(smudge, (0.42, 0.42, 0.43), (0.3, 0.3, 0.31))
    inner = g.ramp(r, 0.05, 0.044)
    col = g.mix(inner, painted, chrome_col)
    metal = g.mixf(inner, 0.6, 1.0)
    rough = g.mixf(inner, g.mixf(smudge, 0.42, 0.55), g.mixf(smudge, 0.12, 0.3))
    height = g.math("MULTIPLY", g.noise(90.0), 0.1)
    # Vent slots
    f = g.math("FRACT", g.math("MULTIPLY", ang, 8.0))
    sa = g.math("DIVIDE", g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", f, 0.5), 2 * math.pi / 8), r), 0.0085)
    sb = g.math("DIVIDE", g.math("SUBTRACT", r, 0.068), 0.0105)
    slot = g.ramp(g.math("ADD", g.math("MULTIPLY", sa, sa), g.math("MULTIPLY", sb, sb)), 1.15, 0.85)
    col = g.mix(slot, col, (0.008, 0.007, 0.007))
    rough = g.mixf(slot, rough, 0.9)
    metal = g.mixf(slot, metal, 0.0)
    height = g.math("SUBTRACT", height, slot)
    # Emblem
    emb = g.ramp(r, 0.019, 0.016)
    col = g.mix(emb, col, (0.03, 0.03, 0.035))
    metal = g.mixf(emb, metal, 0.2)
    rough = g.mixf(emb, rough, 0.5)
    # Rust pitting and blooms, worst toward the rim and in the recesses
    p = tk.photo(g, "rust_coarse_01", 2.5, (0.7, 0.1, 0.4))
    pits = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.09, 0.04), g.mixf(g.ramp(r, 0.07, 0.105), 0.3, 0.9))
    bloom = g.math("MULTIPLY", g.ramp(g.noise(7.0, detail=8.0, distortion=0.5), 0.63, 0.7), 0.85)
    rust = g.math("MAXIMUM", pits, g.math("MULTIPLY", bloom, g.ramp(r, 0.088, 0.104)))
    col = g.mix(rust, col, g.mix(g.noise(40.0), (0.2, 0.08, 0.03), (0.12, 0.05, 0.02)))
    metal = g.mixf(rust, metal, 0.15)
    rough = g.mixf(rust, rough, 0.85)
    height = g.math("ADD", height, g.math("MULTIPLY", rust, 0.4))
    dirt = g.math("MAXIMUM", tk._grime(g, 0.8), g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.3, 0.12), 0.35))
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, (0.06, 0.05, 0.04))
    rough = g.mixf(dirt, rough, 0.85)
    metal = g.mixf(dirt, metal, 0.0)
    x, y, z = g.separate(g.coords())
    col, rough, height = blood(g, col, rough, height, 0.35)
    col, rough, metal = tk._grit(g, col, rough, metal, 0.5, scratches=0.8, edges=0.4)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.002))


sign_mat = sign_paint("StopSignPaint")
belt = webbing("Seatbelt", (0.045, 0.046, 0.05))
steel_wire = tk.photo_material("BalingWire", "metal_plate_02", scale=6.0, sat=0.5, value=1.1, exposed="rust_coarse_01",
                               chip=0.9, grime=0.3, patches=0.5, metal_floor=0.5, grit=0.3)
corr = tk.photo_material("CorrugatedSheet", "worn_corrugated_iron", scale=1.15, sat=0.85, value=0.95,
                         exposed="rust_coarse_01", chip=0.7, grime=0.7, streaks=0.5, patches=0.3, metal_floor=0.3,
                         grit=0.55, scratches=0.3, edges=0.5)
hub_mat = chrome("HubcapChrome")

chest = []
sign = panel("StopSign", sign_outline(), sign_3d, sign_mat, 0.002, edge_thick=0.002, inset=0.0, dense=0.042,
             sparse=None, round_r=0.0015)
chest.append(sign)
sign_tree = bvh([sign])


def sign_point(u, z, lift=0.001):
    """A point on the sign's painted face and its normal."""
    p = sign_3d(np.array([[u, z]]), 0.002 + lift)[0]
    q = sign_3d(np.array([[u, z]]))[0]
    n = p - q
    return p, n / np.linalg.norm(n)


# Seatbelt loops: from the sign's top over each shoulder, down the back, round under the arm and back onto the sign
BELT_W, BELT_T = 0.046, 0.0025
belts = {}
for s in (1, -1):
    ctrl = [sign_point(0.104 * s, 1.425)[0], sign_point(0.106 * s, 1.49)[0],
            (0.114 * s, -0.035, 1.575), (0.121 * s, 0.065, 1.612), (0.128 * s, 0.16, 1.548), (0.14 * s, 0.215, 1.43),
            (0.163 * s, 0.195, 1.32), (0.19 * s, 0.1, 1.275), sign_point(0.226 * s, 1.3)[0],
            sign_point(0.168 * s, 1.3)[0]]
    P, N = drape(ctrl, 26, [sign_tree], 0.015, BELT_T / 2)
    P = settle(P, N, BELT_W, BELT_T, 0.015)
    belts[s] = (P, N)
    chest.append(band("Seatbelt%+d" % s, P, N, BELT_W, BELT_T, belt))
belt_tree = bvh([o for o in chest if o.name.startswith("Seatbelt")])

# Wire ties over the strap ends, through pairs of punched holes, twisted off
for k, (a, b) in enumerate(TIES):
    pa, na = sign_point(*a, lift=0.0)
    pb, nb = sign_point(*b, lift=0.0)
    mid = (pa + pb) / 2
    nm = (na + nb) / 2
    nm /= np.linalg.norm(nm)
    top = far_hit(belt_tree, Vector(mid - nm * 0.05), Vector(nm)) - 0.05
    lift = max(top, 0.002) + 0.0018
    pts = [pa - na * 0.003, pa + na * 0.0015]
    for t in (0.25, 0.5, 0.75):
        pts.append(pa + (pb - pa) * t + nm * lift * (1.0 if t == 0.5 else 0.85))
    pts += [pb + nb * 0.0015, pb - nb * 0.003]
    chest.append(wire("SignTie%d" % k, pts, steel_wire))
    chest.append(twist("SignTieEnd%d" % k, pts[2], nm + (pb - pa) / np.linalg.norm(pb - pa) * -0.6, steel_wire))

# ---------------------------------------------------------------- the corrugated back plate

PITCH, AMP = 0.068, 0.0072  # corrugation: wavelength and half its depth
RB = 0.215
back_r = ruled(math.pi - 1.25, math.pi + 1.25, 1.14, 1.53, 0.022 + AMP)


def back_mid(u, z):
    th = math.pi + u / RB
    r = back_r(th, z) + AMP * np.cos(2 * math.pi * u / PITCH) - 0.004 * np.exp(-((u + 0.08) ** 2 + (z - 1.3) ** 2) / 0.003)
    return at(th, z, r)


def back_normal(u, z):
    e = 1e-4
    du = back_mid(u + e, z) - back_mid(u - e, z)
    dz = back_mid(u, z + e) - back_mid(u, z - e)
    n = np.cross(du, dz)
    p = back_mid(u, z)
    radial = np.array([p[0] - AXIS[0], p[1] - AXIS[1], 0.0])
    n = n / np.linalg.norm(n)
    return n if n @ radial > 0 else -n


def back_edges(u):
    jag = 0.003 * math.sin(u * 131.0) + 0.0018 * math.sin(u * 377.0 + 0.7)
    top = 1.518 + jag - max(0.0, u - 0.105) * 0.95  # one upper corner snipped off at a slant
    bot = 1.148 + 0.003 * math.sin(u * 97.0 + 2.0) + 0.0015 * math.sin(u * 311.0)
    return bot, top


def corrugated(name, mat, nu=25, nz=5, half=0.0006):
    us = np.linspace(-0.204, 0.204, nu)
    bm = bmesh.new()
    outer, inner = [], []
    for u in us:
        bot, top = back_edges(u)
        ro, ri = [], []
        for j in range(nz):
            z = bot + (top - bot) * j / (nz - 1)
            m = back_mid(u, z)
            n = back_normal(u, z)
            ro.append(bm.verts.new(m + n * half))
            ri.append(bm.verts.new(m - n * half))
        outer.append(ro)
        inner.append(ri)
    for i in range(nu - 1):
        for j in range(nz - 1):
            bm.faces.new((outer[i][j], outer[i + 1][j], outer[i + 1][j + 1], outer[i][j + 1]))
            bm.faces.new((inner[i][j + 1], inner[i + 1][j + 1], inner[i + 1][j], inner[i][j]))
    ring = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nz)] + \
           [(i, nz - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nz - 2, 0, -1)]
    for k in range(len(ring)):
        (i0, j0), (i1, j1) = ring[k], ring[(k + 1) % len(ring)]
        bm.faces.new((outer[i0][j0], inner[i0][j0], inner[i1][j1], outer[i1][j1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


backs = [corrugated("Corrugated", corr)]
# Its wire: loops through a hole and round the sheet's edge (where the seatbelts run under it), twisted off
for k, (u0, z0, side) in enumerate(((0.128, None, 0), (-0.128, None, 0), (0.204, 1.31, 1), (-0.204, 1.31, -1))):
    for j, off in enumerate((-0.007, 0.007)):
        if side == 0:  # over the top edge
            uu = u0 + off
            edge_z = back_edges(uu)[1]
            spots_ = [(uu, edge_z - 0.016), (uu, edge_z - 0.004), (uu, edge_z + 0.0035)]
        else:  # round the side edge
            zz = z0 + off
            spots_ = [(u0 * (1 - 0.016 / 0.204), zz), (u0 * (1 - 0.004 / 0.204), zz), (u0 + 0.0035 * side, zz)]
        (ua, za), (ub, zb), (uc, zc) = spots_
        na, nb = back_normal(ua, za), back_normal(ub, zb)
        lift = AMP + 0.0018
        hole = back_mid(ua, za)
        loop = [hole + na * 0.0016, back_mid(ub, zb) + nb * lift, back_mid(uc, zc),
                back_mid(ub, zb) - nb * lift, hole - na * 0.0016]
        backs.append(wire("BackTie%d_%d" % (k, j), loop, steel_wire, closed=True))
    backs.append(twist("BackTieEnd%d" % k, back_mid(ua, za) + na * 0.002, na + np.array([0.0, 0.0, -0.5]), steel_wire))

# ---------------------------------------------------------------- hubcap shoulder guards

HUB = [(0.106, 0.0), (0.103, 0.006), (0.094, 0.0115), (0.082, 0.0185), (0.06, 0.025), (0.044, 0.032), (0.029, 0.041),
       (0.016, 0.045)]
HUB_IN = [(0.105, -0.0015), (0.058, 0.0215)]
HUB_TOP, HUB_TOP_IN = 0.047, 0.041


def hubcap(name, mat, frame, seg=16):
    c, ex, ey, ez = frame
    bm = bmesh.new()
    attr = []

    def ring(r, h):
        out = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            lx, ly = r * math.cos(a), r * math.sin(a)
            out.append(bm.verts.new(c + ex * lx + ey * ly + ez * h))
            attr.append((lx, ly, h))
        return out

    def point(h):
        attr.append((0.0, 0.0, h))
        return bm.verts.new(c + ez * h)
    outer = [ring(r, h) for r, h in HUB]
    inner = [ring(r, h) for r, h in HUB_IN]
    top, bottom = point(HUB_TOP), point(HUB_TOP_IN)
    for rings, flip in ((outer, False), (inner, True)):
        for a, b in zip(rings[:-1], rings[1:]):
            for k in range(seg):
                f = (a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k])
                bm.faces.new(f[::-1] if flip else f)
    for k in range(seg):
        bm.faces.new((outer[-1][k], outer[-1][(k + 1) % seg], top))
        bm.faces.new((inner[-1][(k + 1) % seg], inner[-1][k], bottom))
        bm.faces.new((outer[0][(k + 1) % seg], outer[0][k], inner[0][k], inner[0][(k + 1) % seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, attr)
    return tk.smooth(obj, 40)


pads = {}
for s, arm, fore in ((1, "LeftArm", "LeftForeArm"), (-1, "RightArm", "RightForeArm")):
    pivot = np.array(sk.pos(arm))
    d = np.array(sk.axis(arm, fore))
    up = np.array([0.0, 0.0, 1.0])
    perp = up - d * (up @ d)
    perp /= np.linalg.norm(perp)
    ez = perp + 0.25 * up  # over the shoulder, a little more up than the arm's own top
    ez /= np.linalg.norm(ez)
    ey = np.array([0.0, 1.0, 0.0])
    ex = np.cross(ey, ez)
    ex /= np.linalg.norm(ex)
    base = pivot + d * 0.045
    # Push it out along its axis until its rim clears the arm, chest and head by 1.2 cm
    lo, hi = 0.0, 0.2
    probe = np.array([[r * math.cos(a), r * math.sin(a), h] for r, h in HUB + HUB_IN
                      for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)])
    for _ in range(30):
        mid = (lo + hi) / 2
        pts = base + ez * mid + probe[:, :1] * ex + probe[:, 1:2] * ey + probe[:, 2:3] * ez
        if sdf(pts, (arm, "Spine2", "Head")).min() < 0.012:
            lo = mid
        else:
            hi = mid
    center = base + ez * hi
    cap = hubcap("Hubcap%+d" % s, hub_mat, (center, ex, ey, ez))
    cap_tree = bvh([cap])
    # Baling wire round the upper arm, over the hubcap, twisted off underneath
    station = pivot + d * 0.135
    e1 = perp
    e2 = np.cross(d, e1)
    loop = []
    for k in range(14):
        a = 2 * math.pi * k / 14
        dirv = e1 * math.cos(a) + e2 * math.sin(a)
        t = sk.radius(arm) + 0.006
        h = far_hit(cap_tree, Vector(station), Vector(dirv))
        if h:
            t = max(t, h + 0.0021)
        loop.append(station + dirv * t)
    wires = [wire("ArmWire%+d" % s, loop, steel_wire, closed=True),
             twist("ArmWireEnd%+d" % s, loop[7], -e1 + d * 0.4, steel_wire)]
    pads[s] = [cap] + wires

# ---------------------------------------------------------------- checks, export, previews

for o in chest + backs + pads[1] + pads[-1]:
    fix_normals(o)
for o in chest:
    zk.on(o, "Spine2", "Chest")
for o in backs:
    zk.on(o, "Spine2", "Back")
for o in pads[1]:
    zk.on(o, "LeftArm", "Pad")
for o in pads[-1]:
    zk.on(o, "RightArm", "Pad")
pieces = chest + backs + pads[1] + pads[-1]
for group, objs in (("Chest", chest), ("Back", backs), ("LeftPad", pads[1]), ("RightPad", pads[-1])):
    V = np.array([v.co[:] for o in objs for v in o.data.vertices])
    tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
    print("[scrap_armor] %-8s %4d tris, bounds %s %s, closest to the hit boxes %.1f mm" % (
        group, tris, np.round(V.min(0), 3), np.round(V.max(0), 3), sdf(V).min() * 1000))
for o in pieces:
    m = sdf(np.array([v.co[:] for v in o.data.vertices])).min()
    if m < 0.006:
        print("[scrap_armor] %s comes within %.1f mm of the hit boxes" % (o.name, m * 1000))

parts = zk.export("ScrapArmor", pieces, ASSETS)
focus = Vector((0.0, 0.04, 1.36))
zk.previews("scrap_armor", PREVIEWS, focus, distance=1.45)
for view, loc, tgt, lens in (("close", (0.2, -0.66, 1.46), (0.0, -0.06, 1.33), 50),
                             ("shoulder", (0.62, -0.42, 1.78), (0.2, 0.05, 1.5), 50),
                             ("backclose", (-0.25, 0.75, 1.5), (0.0, 0.18, 1.34), 50)):
    tk.render(tk.camera("sa_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "scrap_armor_%s.png" % view), res=(900, 900), samples=64)
print("[scrap_armor] done")
