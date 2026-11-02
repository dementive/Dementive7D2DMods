"""Snatcher sack: the Snatcher's burlap sack, slung on its back on a rope across the chest.

The rope is tied round the sack's gathered neck high on the left of the back, runs up over the left shoulder,
diagonally down across the chest and round the right flank, and is knotted round the sack's bottom right corner. Two
parts that sit in the same place, the game showing one or the other:

- Spine2#Sack: the sack empty, hanging flat down the back from its tied neck, slack drape folds and pleats gathered
  into the neck, its free bottom corner curling.
- Spine2#SackFull: the same sack stuffed and bulging, squashed flat against the back, lumpy with what's inside (a
  round lump like a head, a long one like a limb, a hard corner), the neck tied off with the burlap fanning out above
  the tie, the bottom ears pulled out, soaked dark with blood at the bottom.

Both carry the same rope (the chest strap, the turns round the neck and its knot are identical); only the last short
run from the right hip to the bottom corner differs, to reach each sack's corner. Coarse jute weave, a faded stencil
(SEED POTATOES 50 LB), side seams sewn with heavy twine, dirt and old blood; the rope is three-strand hemp, grimy.

The two variants overlap in space, so for the bake the full one is moved 2 m aside (the materials read each vertex's
true position from an attribute, so both ropes get the same texture), and its part is moved back and the FBX written
again after.

    blender -b --factory-startup --python snatcher_sack.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "SnatcherSack", "snatcher_sack"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex pattern coordinates (sacks: u across, v up, in meters; rope: along, cos, sin)
POS = "zx_pos"  # per-vertex true position: what the materials texture by (the full sack is baked 2 m aside)

# ---------------------------------------------------------------- the body's hit boxes


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


def sdf(P, bones=None, skip=()):
    """Distance from points to the nearest hit box (negative inside)."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    d = np.full(len(P), 9.0)
    for bone, a, b, r in CAPS:
        if (bones and bone not in bones) or bone in skip:
            continue
        ba, pa = b - a, P - a
        h = np.clip(pa @ ba / max(ba @ ba, 1e-12), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(pa - h[:, None] * ba, axis=1) - r)
    return d


def capsule(bone):
    for b, a, c, r in CAPS:
        if b == bone:
            return a, c, r
    raise KeyError(bone)


# ---------------------------------------------------------------- 2D outlines and flat slabs


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
    k = int(3 * sigma_pts)
    if k < 1:
        return P
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma_pts) ** 2)
    w /= w.sum()
    out = np.zeros_like(P)
    for o, wt in zip(range(-k, k + 1), w):
        out += wt * np.roll(P, o, axis=0)
    return out


def _adaptive(P, step, angle):
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


def outline(poly, step=0.03, round_r=0.004, angle=math.radians(30)):
    """A closed 2D outline resampled: a point every `step` or `angle` of turning, corners rounded by round_r; CCW."""
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


def _cdt(pts, n0):
    edges = [(i, (i + 1) % n0) for i in range(n0)]
    vs, es, fs, orig, _, _ = delaunay_2d_cdt([Vector((p[0], p[1])) for p in pts], edges, [list(range(n0))], 1, 1e-7)
    src = [o[0] if o else -1 for o in orig]
    return np.array([(v.x, v.y) for v in vs]), fs, src


def set_attr(obj, values, name=ATTR):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    for d, v in zip(a.data, values):
        d.vector = v


def _left_normals(L):
    T = np.roll(L, -1, axis=0) - np.roll(L, 1, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    return np.stack([-T[:, 1], T[:, 0]], axis=1)


def _cdt_loops(pts, loop_sizes, outer_n):
    """CDT of points whose first len(loop_sizes) runs are closed constraint loops; keeps what's inside the first."""
    edges, start = [], 0
    for n in loop_sizes:
        edges += [(start + i, start + (i + 1) % n) for i in range(n)]
        start += n
    vs, es, fs, orig, _, _ = delaunay_2d_cdt([Vector((p[0], p[1])) for p in pts], edges, [list(range(outer_n))], 1,
                                             1e-7)
    src = [o[0] if o else -1 for o in orig]
    return np.array([(v.x, v.y) for v in vs]), fs, src


def surface_normals(fn, PQ, toward, e=1e-4):
    """Unit normals of the surface fn(PQ) -> points, turned toward the direction `toward`."""
    PQ = np.atleast_2d(PQ)
    dp = fn(PQ + [e, 0.0]) - fn(PQ - [e, 0.0])
    dq = fn(PQ + [0.0, e]) - fn(PQ - [0.0, e])
    n = np.cross(dp, dq)
    n /= np.linalg.norm(n, axis=1)[:, None]
    return np.where((n @ toward)[:, None] < 0, -n, n)


def slab(name, loops, front_fn, back_fn, toward, mat, dense=0.045, sparse=0.1, inset=0.01, roll=0.006):
    """A solid sheet: loops[0] its outline (CCW), loops[1:] holes through it (CW). The front face lies at
    front_fn(PQ) with its cut edges rolled `roll` back over `inset` (a hemmed edge), the back face at back_fn(PQ),
    with rims round every loop (sparse=None: the back uses the front's triangles). Writes (p, q, side) to zx_local:
    1 on the front, 0.6 on its rolled edge, 0 behind."""
    loops = [np.asarray(L, float) for L in loops]
    sizes = [len(L) for L in loops]
    nL = sum(sizes)
    allL = np.vstack(loops)
    rings = np.vstack([L + _left_normals(L) * inset for L in loops])
    outer, holes = loops[0], loops[1:]

    def material(P, margin):
        P = np.asarray(P, float).reshape(-1, 2)
        P = P[_inside(P, outer)]
        for h in holes:
            P = P[~_inside(P, h)]
        if not len(P):
            return P
        d = np.min([_seg_dist(P, L) for L in loops], axis=0)
        return P[d > margin]

    def keep(V2, F):
        C = np.array([V2[list(f)].mean(axis=0) for f in F])
        ok = np.ones(len(F), bool)
        for h in holes:
            ok &= ~_inside(C, h)
        return [f for f, k in zip(F, ok) if k]

    lat = material(_lattice(outer, dense, 0.0), inset + 0.6 * dense)
    V2f, Ff, srcf = _cdt_loops(list(allL) + list(rings) + list(lat), sizes + sizes, sizes[0])
    Ff = keep(V2f, Ff)
    if sparse:
        latb = material(_lattice(outer, sparse, 0.0), 0.6 * sparse)
        V2b, Fb, srcb = _cdt_loops(list(allL) + list(latb), sizes, sizes[0])
        Fb = keep(V2b, Fb)
    else:  # a thin sheet: the back is the front's own triangles, so neither pokes through the other
        V2b, Fb, srcb = V2f, Ff, srcf

    edge_f = np.array([0 <= s < nL for s in srcf])
    Pf = front_fn(V2f)
    Nf = surface_normals(front_fn, V2f, toward)
    Pf = Pf - Nf * (edge_f * roll)[:, None]
    Pb = back_fn(V2b)
    bm = bmesh.new()
    vf = [bm.verts.new(p) for p in Pf]
    vb = [bm.verts.new(p) for p in Pb]
    for f in Ff:
        bm.faces.new([vf[i] for i in f])
    for f in Fb:
        bm.faces.new([vb[i] for i in reversed(f)])
    mf = {s: i for i, s in enumerate(srcf) if 0 <= s < nL}
    mb = {s: i for i, s in enumerate(srcb) if 0 <= s < nL}
    start = 0
    for n in sizes:
        for i in range(n):
            a, b = start + i, start + (i + 1) % n
            bm.faces.new((vf[mf[a]], vb[mb[a]], vb[mb[b]], vf[mf[b]]))
        start += n
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, [(p, q, 0.6 if e else 1.0) for (p, q), e in zip(V2f, edge_f)] + [(p, q, 0.0) for p, q in V2b])
    return tk.smooth(obj, 35)


def ring_sweep(name, rings_pts, mat, closed=True, caps=False):
    """Faces between consecutive rings of points (each ring a closed loop of the same length)."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in r] for r in rings_pts]
    n, k = len(rings), len(rings[0])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((a[j], a[(j + 1) % k], b[(j + 1) % k], b[j]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, mat)


FLAT = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]


def band(name, pts, nrms, width, thick, mat, profile=FLAT, closed=False):
    """A strap swept along pts, lying on a surface whose outward normals are nrms: `width` across, `thick` out."""
    P = [Vector(p) for p in pts]
    Nn = [Vector(n).normalized() for n in nrms]
    n = len(P)
    rings = []
    for i in range(n):
        if closed:
            T = (P[(i + 1) % n] - P[i - 1]).normalized()
        else:
            T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        Nv = (Nn[i] - T * Nn[i].dot(T)).normalized()
        Wv = T.cross(Nv)
        rings.append([P[i] + Wv * (a * width) + Nv * (b * thick) for a, b in profile])
    return tk.smooth(ring_sweep(name, rings, mat, closed=closed, caps=not closed), 50)


def block(name, size, mat, center, ex, ey, ez, bevel=0.003, segments=1):
    """A bevelled box: size along (ex, ey, ez) around center."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    obj = tk.mesh_object(name, bm, mat)
    if bevel:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = "ANGLE"
        tk.apply_modifiers(obj)
    rot = Matrix((Vector(ex), Vector(ey), Vector(ez))).transposed().to_4x4()
    obj.data.transform(Matrix.Translation(Vector(center)) @ rot)
    return tk.smooth(fix_normals(obj), 40)


def rod(name, a, b, radius, mat, sides=8, radius_b=None):
    """A capped cylinder from a to b."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    e1 = d.cross(ref).normalized()
    e2 = d.cross(e1)
    rb = radius if radius_b is None else radius_b
    rings = [[c + (e1 * math.cos(2 * math.pi * k / sides) + e2 * math.sin(2 * math.pi * k / sides)) * r
              for k in range(sides)] for c, r in ((a, radius), (b, rb))]
    return tk.smooth(ring_sweep(name, rings, mat, closed=False, caps=True), 50)


def fix_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


# ---------------------------------------------------------------- printed masks


def glyph_tris(body, font, spacing=1.0):
    cu = bpy.data.curves.new("Glyphs", "FONT")
    cu.body = body
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.resolution_u = 8
    if not os.path.exists(font):
        font = "C:/Windows/Fonts/arialbd.ttf"
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
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    s = min((box[2] - box[0]) / (hi[0] - lo[0]), (box[3] - box[1]) / (hi[1] - lo[1]))
    c = (lo + hi) / 2
    return (tris - c) * s + np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])


def raster(shape, box, tris, ss=3):
    H, W_ = shape
    x0, y0, x1, y1 = box
    Hs, Ws = H * ss, W_ * ss
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
    return img.reshape(H, ss, W_, ss).mean(axis=(1, 3))


def grid_xy(shape, box):
    H, W_ = shape
    x0, y0, x1, y1 = box
    return np.meshgrid(x0 + (np.arange(W_) + 0.5) * (x1 - x0) / W_, y0 + (np.arange(H) + 0.5) * (y1 - y0) / H)


def lines_mask(shape, box, polylines, width):
    """Antialiased polylines (lists of 2D points) `width` wide, as a 0-1 mask."""
    X, Y = grid_xy(shape, box)
    px = (box[2] - box[0]) / shape[1]
    d = np.full(X.shape, 9.0, np.float32)
    for pl in polylines:
        pl = np.asarray(pl, float)
        for a, b in zip(pl[:-1], pl[1:]):
            lo = np.minimum(a, b) - width * 2 - px * 2
            hi = np.maximum(a, b) + width * 2 + px * 2
            sel = (X >= lo[0]) & (X <= hi[0]) & (Y >= lo[1]) & (Y <= hi[1])
            if not sel.any():
                continue
            ab = b - a
            t = np.clip(((X[sel] - a[0]) * ab[0] + (Y[sel] - a[1]) * ab[1]) / max(ab @ ab, 1e-12), 0, 1)
            dd = np.hypot(X[sel] - a[0] - t * ab[0], Y[sel] - a[1] - t * ab[1])
            d[sel] = np.minimum(d[sel], dd)
    return np.clip(0.5 - (d - width / 2) / px, 0, 1)


def mask_image(name, channels):
    H, W_ = channels[0].shape
    img = bpy.data.images.new(name, W_, H, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((H, W_, 4), np.float32)
    for k, c in enumerate(channels):
        rgba[..., k] = c
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(tempfile.gettempdir(), "zx_%s_%s.png" % (SCRIPT, name))
    img.file_format = "PNG"
    img.save()
    img.pack()
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


def attr_uvw(g, name=ATTR):
    a = g.node("ShaderNodeAttribute", attribute_name=name)
    a.attribute_type = "GEOMETRY"
    return g.separate(tk._sock(a.outputs, "Vector"))


# ---------------------------------------------------------------- worn surfaces (after riot_helmet.py's wear)


def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def voronoi(g, vec, scale, feature="F1"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Distance")


def warp(g, P, scale, amount):
    n = g.node("ShaderNodeTexNoise")
    g._in(n, "Scale", scale)
    g._in(n, "Detail", 3.0)
    g.links.new(P, n.inputs["Vector"])
    s = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(tk._sock(n.outputs, "Color"), s.inputs[0])
    tk._sock(s.inputs, "Scale").default_value = amount
    a = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(P, a.inputs[0])
    g.links.new(s.outputs[0], a.inputs[1])
    return a.outputs[0]


def lines(g, vec, scale, rot, loc, width, seg=0.0):
    n = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, vec, scale, rot, loc))
    ln = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, width, False))
    if seg:
        ln = g.math("MULTIPLY", ln, g.ramp(g.noise(seg, detail=2.0, vector=mapping(g, vec, loc=loc)), 0.5, 0.58))
    return ln


def scratch_mask(g, P, width=0.015):
    """Straight scratches in five directions (bands of a wave texture, each broken into short runs)."""
    sc = None
    for i, (rot, scale) in enumerate((((0.3, 0.9, 0.2), 38.0), ((1.1, 0.2, 1.4), 55.0), ((0.5, 1.3, 2.7), 30.0),
                                      ((2.3, 0.4, 0.9), 70.0), ((1.7, 2.2, 0.3), 45.0))):
        m = mapping(g, P, rot=rot, loc=(0.13 * i, 0.31 * i, 0.07 * i))
        w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        g._in(w, "Scale", scale)
        g._in(w, "Distortion", 0.8)
        g._in(w, "Detail", 1.0)
        g._in(w, "Detail Scale", 0.5)
        g.links.new(warp(g, m, 2.5 + i, 0.03), w.inputs["Vector"])
        line = g.ramp(tk._sock(w.outputs, "Fac"), 1.0 - width, 1.0 - width * 0.15)
        seg = g.ramp(g.noise(16.0 + 7.0 * i, detail=2.0, vector=m), 0.57, 0.64)
        line = g.math("MULTIPLY", line, seg)
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    return sc


def wear(name, paint, rough=0.4, metal=0.0, decals=None, seed=0.0, tone=0.2, scratches=0.5,
         scratch_col=(0.6, 0.58, 0.52), scratch_metal=0.0, dark_scratches=0.3, scuffs=0.4, scuff_col=None, edges=0.4,
         edge_col=None, chips=0.0, chip_col=(0.5, 0.5, 0.5), chip_rough=0.6, chip_metal=0.0, dirt=0.5,
         dirt_set="rust_coarse_01", dirt_scale=3.0, dirt_range=(0.14, 0.04), grime=0.6, dust=0.4, specks=0.5,
         blood=0.0, grease=0.0, bump=0.3, grain=0.15, grain_scale=90.0, line_width=0.03,
         dirt_col=((0.04, 0.032, 0.024), (0.12, 0.095, 0.065))):
    """Worn gear: base color with uneven tone, decals, chips, rubbed scuffs, scratches, worn edges, photo-patterned
    dirt and crease grime, dust on top, dark specks, grease and blood. All amounts 0-1."""
    mat, g = tk.new_material(name)
    W_ = g.coords()
    S = (seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29)
    P = mapping(g, W_, loc=S)

    def nz(scale, detail=4.0, r=0.55, dist=0.0):
        return g.noise(scale, detail=detail, roughness=r, vector=P, distortion=dist)

    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    col = g.mix(g.math("MULTIPLY", nz(5.0, 3.0), tone * 2.0), paint, tk._darker(g, paint, 0.7))
    rgh = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", nz(14.0, 3.0), 0.5), 0.16))
    met = metal
    height = g.math("MULTIPLY", nz(grain_scale, 6.0, 0.6), grain)
    if chips:
        cm = g.ramp(nz(16.0, 8.0, 0.7), 0.7 - 0.13 * chips, 0.715 - 0.13 * chips)
        ce = g.math("MULTIPLY", g.ramp(g.edges(0.006), 0.05, 0.25), g.ramp(nz(40.0), 0.42, 0.55))
        cm = g.math("MAXIMUM", cm, g.math("MULTIPLY", ce, chips), clamp=True)
        col = g.mix(cm, col, chip_col)
        rgh = g.mixf(cm, rgh, chip_rough)
        met = g.mixf(cm, met, chip_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", cm, 0.5))
    if scuffs:
        sm = g.math("MULTIPLY", g.ramp(nz(11.0, 6.0, 0.7, 1.2), 0.58, 0.72), scuffs)
        streak = lines(g, P, (30.0, 30.0, 8.0), (0.4, 1.1, 0.3), (0.5, 0.2, 0.9), 0.08)
        sm = g.math("MULTIPLY", sm, g.math("ADD", 0.45, g.math("MULTIPLY", streak, 0.55)))
        col = g.mix(g.math("MULTIPLY", sm, 0.75), col, scuff_col or tk.grade(g, col, 0.45, 1.45))
        rgh = g.mixf(sm, rgh, min(1.0, rough + 0.3))
    if scratches:
        sc = scratch_mask(g, P, line_width)
        dens = g.ramp(nz(3.0, 3.0), 0.42, 0.66)
        sc = g.math("MULTIPLY", g.math("MULTIPLY", sc, dens), scratches, clamp=True)
        dark = g.math("MULTIPLY", g.ramp(nz(7.0, 3.0), 0.48, 0.56), dark_scratches)
        scol = g.mix(dark, scratch_col, (0.05, 0.04, 0.03))
        col = g.mix(sc, col, scol)
        rgh = g.mixf(sc, rgh, 0.6)
        met = g.mixf(sc, met, scratch_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.6))
    if edges:
        wm = g.math("MULTIPLY", g.ramp(g.edges(0.004), 0.06, 0.3), g.ramp(nz(30.0, 4.0), 0.36, 0.55))
        wm = g.math("MULTIPLY", wm, edges)
        col = g.mix(wm, col, edge_col or scratch_col)
        rgh = g.mixf(wm, rgh, 0.55)
        met = g.mixf(wm, met, scratch_metal)
    if decals:
        col, rgh, met, height = decals(g, W_, P, col, rgh, met, height)
    p = tk.photo(g, dirt_set, dirt_scale, (S[0] * 0.3, 0.5, S[2] * 0.2))
    dm = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1]), dirt)
    dm = g.math("MAXIMUM", dm, tk._grime(g, grime), clamp=True)
    col = g.mix(g.math("MULTIPLY", dm, 0.88), col, g.mix(nz(9.0), dirt_col[0], dirt_col[1]))
    rgh = g.mixf(dm, rgh, 0.85)
    met = g.mixf(dm, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", dm, 0.2))
    if grease:
        gm = g.math("MULTIPLY", g.ramp(nz(5.0, 6.0, 0.6, 1.0), 0.56, 0.68), grease)
        col = g.mix(gm, col, tk._darker(g, col, 0.3))
        rgh = g.mixf(gm, rgh, 0.18)
    if dust:
        du = g.math("MULTIPLY", g.ramp(up, 0.25, 0.95), g.ramp(nz(8.0, 6.0, 0.6), 0.35, 0.65))
        du = g.math("MULTIPLY", du, dust)
        col = g.mix(du, col, (0.33, 0.29, 0.23))
        rgh = g.mixf(du, rgh, 0.95)
        met = g.mixf(du, met, 0.0)
    if specks:
        spots = g.ramp(voronoi(g, P, 150.0), 0.16, 0.07)
        sp = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.62)), specks)
        col = g.mix(sp, col, (0.025, 0.02, 0.015))
        rgh = g.mixf(sp, rgh, 0.9)
    if blood:
        reg = g.ramp(nz(1.6, 5.0, 0.6, 0.6), 0.52, 0.66)
        drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 26.0), 0.16, 0.05),
                       g.ramp(nz(25.0, 4.0), 0.42, 0.6))
        smear = g.ramp(nz(9.0, 8.0, 0.7, 1.5), 0.56, 0.64)
        bm_ = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", drops, smear), reg), blood, clamp=True)
        col = g.mix(bm_, col, g.mix(nz(20.0), (0.06, 0.004, 0.003), (0.15, 0.014, 0.009)))
        rgh = g.mixf(bm_, rgh, 0.3)
        met = g.mixf(bm_, met, 0.0)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, bump, 0.0015))


def bandf(g, x, lo, hi, soft=0.001):
    """1 between lo and hi, soft edges."""
    return g.math("MULTIPLY", g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- the torso's envelope (after scrap_armor.py)

AXIS = np.array([0.0, 0.05])  # the chest hit box's vertical axis (x, y)
R_BACK = 0.175  # arc length across the back to angle round the axis


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
ZS = np.arange(0.86, 1.74, 0.005)
_T, _Z = np.meshgrid(TH, ZS, indexing="ij")
ENV = np.array([_upper_hull(ZS, row) for row in _ray_exit(_T, _Z)])  # taut: cloth hangs straight over hollows


def env(theta, z):
    theta = (np.asarray(theta, float) + math.pi) % (2 * math.pi) - math.pi
    fi = np.clip((theta + math.pi) / (2 * math.pi) * (len(TH) - 1), 0, len(TH) - 1.001)
    fj = np.clip((np.asarray(z, float) - ZS[0]) / 0.005, 0, len(ZS) - 1.001)
    i, j = fi.astype(int), fj.astype(int)
    a, b = fi - i, fj - j
    return ((ENV[i, j] * (1 - b) + ENV[i, j + 1] * b) * (1 - a) + (ENV[i + 1, j] * (1 - b) + ENV[i + 1, j + 1] * b) * a)


def wrap(theta, z, clear):
    r = env(theta, z) + clear
    return np.stack([AXIS[0] + r * np.sin(theta), AXIS[1] - r * np.cos(theta), np.asarray(z, float) * np.ones_like(r)],
                    axis=-1)


TORSO = ("Spine2", "Hips")
STRAP_BODY = ("Spine2", "LeftArm", "RightArm", "Hips")


def sdf_grad(P, bones, e=1e-3):
    P = np.atleast_2d(P)
    g = np.stack([sdf(P + dv, bones) - sdf(P - dv, bones) for dv in np.eye(3) * e], axis=1)
    return g / np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]


def push_out(P, bones, clear, iters=4):
    """Moves points that are closer than `clear` to the hit boxes out along the distance gradient."""
    P = np.array(P, float)
    for _ in range(iters):
        d = sdf(P, bones)
        bad = d < clear
        if not bad.any():
            break
        P[bad] += sdf_grad(P[bad], bones) * (clear - d[bad])[:, None]
    return P


# ---------------------------------------------------------------- straps laid on the body (after scrap_armor.py)


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


def resample(P, n=None, step=None):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = n or max(2, int(round(s[-1] / step)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], axis=1)


def core(p):
    """The nearest point on the torso's axis, where straps are pushed out from."""
    return np.array([AXIS[0], AXIS[1] if p[2] > 1.2 else 0.03, min(max(p[2], 1.0), 1.46)])


def shell_first(origin, d, clear, bones, bridge=0.02, maxd=0.45):
    t = np.arange(0.0, maxd, 0.0015)
    P = np.asarray(origin)[None] + t[:, None] * np.asarray(d)[None]
    inside = sdf(P, bones) < clear
    k = 0
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


def drape(ctrl, step, clear, half, iters=10):
    """A rope through control points, laid on the body and pulled taut: each point sits on the last hit box its ray
    from the torso's axis passes, `half` out; the end points stay where they are."""
    P = resample(catmull(ctrl), step=step)
    n = len(P)

    def need(p):
        q = core(p)
        d = p - q
        d /= np.linalg.norm(d)
        return q, d, shell_first(q, d, clear, STRAP_BODY) + half

    for it in range(iters + 1):
        if it:
            P[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
        for i in range(1, n - 1):
            q, d, t = need(P[i])
            if it == 0 or np.linalg.norm(P[i] - q) < t:
                P[i] = q + d * t
    return P


def transported(P, closed=False):
    """Cross-section frames carried along a path without twisting."""
    n = len(P)
    T = [P[(i + 1) % n if closed else min(i + 1, n - 1)] - P[i - 1 if closed else max(i - 1, 0)] for i in range(n)]
    T = [t / np.linalg.norm(t) for t in T]
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    out = []
    for t in T:
        nv = ref - t * (ref @ t)
        nv /= np.linalg.norm(nv)
        out.append((t, nv, np.cross(t, nv)))
        ref = nv
    return out


RR = 0.0062  # rope radius
SIDES = 5


def rope(name, P, mat, s0=0.0, radius=RR, taper_end=0.0, caps=True):
    """A rope swept along P (round, SIDES sided), writing (along, cos, sin) for the strands to zx_local; the last
    `taper_end` meters thin out to a frayed end."""
    P = np.asarray(P, float)
    fr = transported(P)
    seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    rings, attr = [], []
    for i, (t, nv, bv) in enumerate(fr):
        r = radius
        if taper_end and seg[-1] - seg[i] < taper_end:
            r *= 0.55 + 0.45 * (seg[-1] - seg[i]) / taper_end
        ring = []
        for k in range(SIDES):
            a = 2 * math.pi * k / SIDES
            ring.append(Vector(P[i] + (nv * math.cos(a) + bv * math.sin(a)) * r))
            attr.append((s0 + seg[i], math.cos(a), math.sin(a)))
        rings.append(ring)
    obj = tk.smooth(ring_sweep(name, rings, mat, closed=False, caps=caps), 70)
    set_attr(obj, attr)
    return obj, s0 + seg[-1]


def knot(name, c, mat, size=0.016, seed=0):
    """A rope knot: a lumpy blob."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=size)
    rng = np.random.default_rng(seed)
    for v in bm.verts:
        v.co *= 1.0 + 0.25 * rng.uniform(-1, 1)
        v.co.z *= 0.8
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    obj = tk.mesh_object(name, bm, mat)
    attr = []
    for v in obj.data.vertices:
        d = v.co - Vector(c)
        a = math.atan2(d.y, d.x)
        attr.append((d.z * 3.0 + seed, math.cos(a), math.sin(a)))
    set_attr(obj, attr)
    return tk.smooth(obj, 80)


# ---------------------------------------------------------------- burlap and rope materials


def by_position(g):
    """Makes the material texture by each vertex's true position (zx_pos) instead of where it is for the bake."""
    a = g.node("ShaderNodeAttribute", attribute_name=POS)
    a.attribute_type = "GEOMETRY"
    v = tk._sock(a.outputs, "Vector")
    g.coords = lambda: v
    return v


STENCIL = "C:/Windows/Fonts/STENCIL.TTF"
PRINT_BOX = (-0.15, -0.09, 0.15, 0.09)
_ps = (180, 300)
_l1 = raster(_ps, PRINT_BOX, fit(glyph_tris("SEED POTATOES", STENCIL, 1.0), (-0.135, 0.005, 0.135, 0.06)))
_l2 = raster(_ps, PRINT_BOX, fit(glyph_tris("50 LB", STENCIL, 1.0), (-0.07, -0.075, 0.07, -0.02)))
_X2, _Y2 = grid_xy(_ps, PRINT_BOX)
_frame = np.clip(0.5 - (np.abs(np.maximum(np.abs(_X2) - 0.14, np.abs(_Y2) - 0.082)) - 0.002) / 0.0012, 0, 1)
PRINT = mask_image("SackPrint", [np.clip(_l1 + _l2 + _frame * 0.9, 0, 1), np.zeros(_ps), np.zeros(_ps)])


def burlap(name, print_at, full):
    """Coarse jute: a two-way weave with slubby threads, blotchy tan to brown, stitched side seams, a faded stencil,
    dirt, and old blood (the full sack soaked dark from the bottom)."""
    mat, g = tk.new_material(name)
    W_ = by_position(g)
    u, v, seam = attr_uvw(g)
    P = mapping(g, W_, loc=(0.7, 2.1, 1.3))
    # The weave: threads across and along, each with its own slub (thickness wobble), over and under
    pitch = 0.0068
    wu = g.math("SINE", g.math("MULTIPLY", u, 2 * math.pi / pitch))
    wv = g.math("SINE", g.math("MULTIPLY", v, 2 * math.pi / pitch))
    slub_u = g.noise(1.0, detail=2.0, vector=mapping(g, P, scale=(4.0, 4.0, 60.0)))
    over = g.math("MULTIPLY", wu, wv)
    weave = g.math("ADD", 0.5, g.math("MULTIPLY", over, 0.5))
    gaps = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", wu), 0.25, 0.0), g.ramp(g.math("ABSOLUTE", wv), 0.25, 0.0))
    tan = g.mix(g.ramp(g.noise(5.0, detail=5.0, distortion=0.4, vector=P), 0.3, 0.75), (0.17, 0.11, 0.055),
                (0.24, 0.165, 0.085))
    tan = g.mix(g.math("MULTIPLY", g.ramp(g.noise(1.6, detail=4.0, vector=P), 0.45, 0.7), 0.6), tan, (0.11, 0.08, 0.05))
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, weave), 0.3), tan, tk._darker(g, tan, 0.65))
    col = g.mix(g.math("MULTIPLY", slub_u, 0.35), col, tk._darker(g, col, 1.25))
    col = g.mix(gaps, col, (0.02, 0.014, 0.008))
    height = g.math("SUBTRACT", g.math("MULTIPLY", weave, 0.6), g.math("MULTIPLY", gaps, 0.5))
    rough = g.math("ADD", 0.86, g.math("MULTIPLY", weave, 0.08))
    # Stitched seams (heavy twine in long stitches) where the zx_local third channel says
    sm = g.ramp(seam, 0.75, 0.95)
    st = g.math("MULTIPLY", sm, g.ramp(g.math("FRACT", g.math("DIVIDE", v, 0.016)), 0.25, 0.4))
    col = g.mix(sm, col, tk._darker(g, col, 0.55))
    col = g.mix(st, col, (0.16, 0.12, 0.07))
    height = g.math("ADD", height, g.math("MULTIPLY", st, 1.0))
    # The stencil, faded and rubbed off the raised threads
    pu, pv, ps = print_at
    ink, _, _ = decal(g, PRINT, g.math("DIVIDE", g.math("SUBTRACT", pu, u), ps), g.math("DIVIDE", g.math("SUBTRACT", v, pv), ps),
                      PRINT_BOX)  # u runs toward the zombie's left: from behind, read it the other way
    ink = g.math("MULTIPLY", ink, g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=6.0, vector=P), 0.15, 0.45),
                                         g.mixf(weave, 0.6, 0.95)))
    col = g.mix(g.math("MULTIPLY", ink, 0.85), col, (0.028, 0.024, 0.03))
    # Dirt, grime in the folds, sweat-dark where it lies on the back
    p = tk.photo(g, "rust_coarse_01", 1.8, (0.2, 0.6, 0.4))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.24, 0.07), 0.65), tk._grime(g, 0.9))
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, g.mix(g.noise(7.0, vector=P), (0.04, 0.03, 0.02), (0.08, 0.06, 0.04)))
    rough = g.mixf(dirt, rough, 0.9)
    # Blood: old brown blotches all over, and on the full sack soaking up from the bottom, darker and wet
    x, y, z = g.separate(W_)
    blot = g.ramp(g.noise(3.5, detail=6.0, roughness=0.6, distortion=0.7, vector=P), 0.58, 0.66)
    if full:
        soak = g.math("MULTIPLY", g.ramp(v, 0.45, 0.06), g.ramp(g.noise(4.0, detail=5.0, distortion=0.5, vector=P), 0.25, 0.5))
        soak = g.math("MAXIMUM", soak, blot)
        wet = g.math("MULTIPLY", g.ramp(v, 0.2, 0.0), g.ramp(g.noise(6.0, vector=P), 0.4, 0.6))
    else:
        soak = g.math("MULTIPLY", blot, 0.85)
        wet = g.value(0.0)
    bcol = g.mix(g.ramp(g.noise(12.0, vector=P), 0.3, 0.7), (0.05, 0.012, 0.007), (0.035, 0.009, 0.006))
    col = g.mix(soak, col, g.mix(wet, bcol, (0.045, 0.004, 0.003)))
    rough = g.mixf(soak, rough, g.mixf(wet, 0.8, 0.35))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.25)
    col = tk.grade(g, col, 0.95, 0.8)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.45, 0.0025))


def hemp(name):
    """Three-strand hemp rope: the strands' lay, fibres along them, greyed and grimy, dark with blood in places."""
    mat, g = tk.new_material(name)
    W_ = by_position(g)
    s, ca, sa = attr_uvw(g)
    P = mapping(g, W_, loc=(1.7, 0.3, 2.2))
    ang = g.math("DIVIDE", g.math("ARCTAN2", sa, ca), 2 * math.pi)
    lay = 0.024  # one strand's turn
    phase = g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", ang, g.math("DIVIDE", s, lay)), 3.0))
    strand = g.math("SINE", g.math("MULTIPLY", phase, math.pi))
    groove = g.ramp(strand, 0.25, 0.0)
    fib = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", ang, 3.0), g.math("DIVIDE", s, 0.004)), 4.0))
    fib = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", fib, math.pi)), g.noise(40.0, vector=P))
    base = g.mix(g.ramp(g.noise(4.0, detail=5.0, vector=P), 0.3, 0.7), (0.12, 0.095, 0.06), (0.085, 0.066, 0.042))
    col = g.mix(g.math("MULTIPLY", fib, 0.4), base, tk._darker(g, base, 1.35))
    col = g.mix(groove, col, (0.025, 0.02, 0.014))
    height = g.math("SUBTRACT", g.math("ADD", strand, g.math("MULTIPLY", fib, 0.15)), groove)
    p = tk.photo(g, "rust_coarse_01", 2.2, (0.6, 0.1, 0.8))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.24, 0.07), 0.7), g.math("MULTIPLY", groove, 0.4))
    col = g.mix(g.math("MULTIPLY", dirt, 0.75), col, (0.05, 0.04, 0.028))
    blood = g.math("MULTIPLY", g.ramp(g.noise(2.5, detail=6.0, distortion=0.6, vector=P), 0.57, 0.65), 0.85)
    col = g.mix(blood, col, (0.04, 0.008, 0.005))
    rough = g.mixf(blood, g.math("ADD", 0.82, g.math("MULTIPLY", fib, 0.1)), 0.55)
    col = tk.grade(g, col, 0.85, 0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.6, 0.002))


# ---------------------------------------------------------------- the neck, shared by both

NECK = np.array([0.05, 0.252, 1.47])  # the middle of the tie round the sack's neck
NAX = np.array([0.0, 0.26, 1.0]) / np.linalg.norm([0.0, 0.26, 1.0])  # up the neck, leaning out off the back
RT = 0.025  # the gathered neck's radius at the tie
XN = np.array([1.0, 0.0, 0.0]) - NAX * NAX[0]
XN /= np.linalg.norm(XN)
ON = np.cross(NAX, XN)  # out of the back
if ON[1] < 0:
    ON = -ON


def loft(name, mat, rings_v, profile, center, frame_x, frame_o, nj=22, seam_phi=90.0, bumps=None, flatten=None,
         cap_bottom=True, cap_top=True, uv_scale=1.0):
    """A closed sack-like surface: rings at v, each an ellipse (a across, b out from the back) round center(v), with
    radial folds, lumps and, optionally, the side toward the body flattened against it. The ring's first and last
    vertices are split at seam_phi (a sewn side seam). Writes (u, v, seam) to zx_local, u and v in meters."""
    rings, attr = [], []
    vlen = 0.0
    prev_c = None
    phis = np.radians(seam_phi + np.linspace(0.0, 360.0, nj + 1))
    for v in rings_v:
        c = center(v)
        if prev_c is not None:
            vlen += np.linalg.norm(c - prev_c)
        prev_c = c
        a, b, folds = profile(v)
        X, Ob = frame_x(v), frame_o(v)
        ring = []
        circ = 2 * math.pi * math.sqrt((a * a + b * b) / 2)
        for j, ph in enumerate(phis):
            r_scale = 1.0 + folds(v, ph)
            p = c + X * (a * math.sin(ph) * r_scale) + Ob * (b * math.cos(ph) * r_scale)
            if bumps:
                nrm = X * (math.sin(ph) / max(a, 1e-4)) + Ob * (math.cos(ph) / max(b, 1e-4))
                nrm /= np.linalg.norm(nrm)
                p = p + nrm * bumps(v, ph)
            ring.append(p)
            seam = 1.0 if (j == 0 or j == nj or abs(math.cos(ph - math.radians(seam_phi + 180.0)) - 1) < 1e-3) else 0.0
            attr.append((circ * j / nj * uv_scale, vlen, seam))
        rings.append(ring)
    R = np.array(rings)
    if flatten:
        R = flatten(R)
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in ring] for ring in R]
    n, k = len(vs), nj + 1
    for i in range(n - 1):
        for j in range(nj):
            bm.faces.new((vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]))
    extra = []
    for cap, idx in ((cap_bottom, 0), (cap_top, n - 1)):
        if cap:
            cc = R[idx].mean(axis=0)
            cv = bm.verts.new(cc)
            extra.append(cv)
            for j in range(nj):
                bm.faces.new((vs[idx][j], vs[idx][j + 1], cv))
            attr.append((0.0, 0.0 if idx == 0 else vlen, 0.0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, attr)
    return tk.smooth(obj, 80)


def neck_center(v):
    """The sack's spine above the shoulders: up the neck through the tie into the tuft (v from 0.8 to 1)."""
    if v <= 0.86:
        return NECK - NAX * (0.86 - v) * 0.6
    return NECK + NAX * (v - 0.86) * 0.62


def tuft(v, ph):
    """The burlap fanned out above the tie: deep gathered folds."""
    k = smooth01((v - 0.88) / 0.04)
    return k * (0.24 * math.sin(9 * ph + 0.6) + 0.1 * math.sin(14 * ph + 2.0))


def tuft_profile(v):
    """Radius of the tie and the tuft above it (v from 0.86)."""
    return float(np.interp(v, [0.86, 0.9, 0.92, 0.95, 0.975, 0.99, 1.0], [RT, RT, 0.033, 0.046, 0.048, 0.036, 0.012]))


# ---------------------------------------------------------------- the rope, shared by both

coil_ang0 = math.radians(-60.0)
TURNS = 2.2
coil = []
nc = int(TURNS * 11)
for k in range(nc + 1):
    a = coil_ang0 + 2 * math.pi * TURNS * k / nc
    h = -0.004 + 0.026 * k / nc
    r = RT + RR * 0.85
    coil.append(NECK + NAX * h + (XN * math.cos(a) + ON * math.sin(a)) * r)
coil = np.array(coil)
# leaves the last turn toward the left shoulder
exit_dir = coil[-1] - coil[-2]
exit_dir /= np.linalg.norm(exit_dir)
SHARED_CTRL = [coil[-1], coil[-1] + exit_dir * 0.02 + np.array([0.02, 0.0, 0.02]), (0.12, 0.2, 1.55), (0.14, 0.11, 1.6),
               (0.142, 0.02, 1.61), (0.13, -0.07, 1.545), (0.07, -0.125, 1.42), (-0.02, -0.14, 1.3), (-0.1, -0.125, 1.2),
               (-0.155, -0.075, 1.115), (-0.18, 0.02, 1.065)]
strap = drape(SHARED_CTRL, 0.03, 0.013, RR)
F = strap[-1]
# The loose end hanging from the knot under the first turn
k0 = coil[0]
tail_pts = [k0 + np.array([0.0, 0.004, -0.004]), k0 + np.array([0.004, 0.012, -0.03]), k0 + np.array([0.006, 0.016, -0.06]),
            k0 + np.array([0.004, 0.018, -0.085])]


def shared_rope(tag, mat):
    """The chest strap with its turns round the neck, its knot and loose end: built once per part, identical."""
    out = []
    path = np.vstack([coil[:-1], strap])
    obj, s_end = rope("Rope" + tag, path, mat)
    out.append(obj)
    t_obj, _ = rope("RopeEnd" + tag, np.array(tail_pts[::-1]), mat, s0=1.7, taper_end=0.03)
    out.append(t_obj)
    out.append(knot("NeckKnot" + tag, k0 + ON * 0.006 + np.array([0.0, 0.0, -0.002]), mat, 0.015, 1))
    return out, s_end


def corner_rope(tag, mat, corner, s0, sack_tree=None, out_dir=None):
    """From the right hip round to the sack's bottom corner, with a turn round the corner and a knot."""
    ctrl = [F, F + np.array([0.0, 0.03, -0.012]), (F + corner) / 2 + np.array([-0.01, 0.0, -0.01]), corner]
    P = resample(catmull(ctrl), step=0.025)
    P[1:] = push_out(P[1:], TORSO + ("RightUpLeg",), 0.013 + RR)
    if sack_tree is not None:
        for i in range(1, len(P) - 1):
            loc, nrm, idx, dist = sack_tree.find_nearest(Vector(P[i]))
            if loc is not None:
                d = (Vector(P[i]) - loc).dot(nrm)
                if d < RR + 0.002:
                    P[i] = np.array(loc + nrm * (RR + 0.002))
    out = []
    obj, s1 = rope("RopeTail" + tag, P, mat, s0=s0)
    out.append(obj)
    # the turn round the corner ear
    d = P[-1] - P[-2]
    d /= np.linalg.norm(d)
    e1 = np.cross(d, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    loop = [corner + d * 0.012 + (e1 * math.cos(a) + e2 * math.sin(a)) * 0.018 for a in np.linspace(0, 2 * math.pi, 9)]
    lobj, _ = rope("CornerTurn" + tag, np.array(loop), mat, s0=s1, caps=False)
    out.append(lobj)
    out.append(knot("CornerKnot" + tag, corner + d * 0.014 + e2 * 0.016, mat, 0.013, 2))
    return out


# ---------------------------------------------------------------- the full sack

B0 = np.array([0.03, 0.318, 0.985])  # the bottom seam's middle
B1 = np.array([0.045, 0.29, 1.37])  # the shoulders, where it narrows to the neck
A_V = [0.0, 0.03, 0.08, 0.16, 0.3, 0.45, 0.6, 0.7, 0.76, 0.8, 0.84, 0.86]
A_A = [0.175, 0.2, 0.207, 0.212, 0.214, 0.208, 0.185, 0.15, 0.11, 0.07, 0.036, RT]
A_B = [0.012, 0.05, 0.095, 0.13, 0.148, 0.148, 0.13, 0.105, 0.075, 0.05, 0.032, RT]


def full_center(v):
    if v <= 0.7:
        return B0 + (B1 - B0) * (v / 0.7)
    if v <= 0.86:
        t = (v - 0.7) / 0.16
        return B1 + (NECK - B1) * t
    return neck_center(v)


def full_profile(v):
    if v >= 0.86:
        r = tuft_profile(v)
        return r, r, lambda vv, ph: tuft(vv, ph)
    a, b = float(np.interp(v, A_V, A_A)), float(np.interp(v, A_V, A_B))

    def folds(vv, ph):
        gather = smooth01((vv - 0.62) / 0.2) * 0.22 * math.sin(9 * ph + 2.0 * vv)
        wrinkle = 0.03 * math.sin(17 * ph + 31 * vv) * math.sin(5 * ph - 13 * vv + 1.0)
        return gather + wrinkle
    return a, b, folds


LUMPS = [  # (v, phi deg, v radius, phi radius deg, height, sharpness): what's inside pressing out
    (0.33, -40.0, 0.13, 34.0, 0.06, 2.0),  # round, like a head
    (0.67, -66.0, 0.07, 18.0, 0.045, 1.2),  # a hard corner (a box, a can)
    (0.14, 25.0, 0.08, 22.0, 0.03, 2.0),
    (0.5, -2.0, 0.08, 20.0, -0.022, 2.0),  # a sag between them
    (0.57, 15.0, 0.06, 15.0, 0.024, 2.0),
    (0.24, 110.0, 0.08, 25.0, 0.025, 2.0),  # pushing out the sides too
    (0.45, -115.0, 0.09, 25.0, 0.022, 2.0),
]
LIMB = ((0.66, 40.0), (0.16, 74.0), 0.06, 0.042)  # a long one, like an arm: from, to, radius, height


def full_bumps(v, ph):
    if v > 0.84:
        return 0.0
    phd = (math.degrees(ph) + 180.0) % 360.0 - 180.0  # -180..180, 0 = straight out
    out = 0.0
    for lv, lp, rv, rp, h, sh in LUMPS:
        d = math.sqrt(((v - lv) / rv) ** 2 + ((phd - lp) / rp) ** 2)
        out += h * math.exp(-d ** sh)
    (v0, p0), (v1, p1), rad, h = LIMB
    a = np.array([v0, p0 / 120.0])
    b = np.array([v1, p1 / 120.0])
    x = np.array([v, phd / 120.0])
    t = np.clip((x - a) @ (b - a) / ((b - a) @ (b - a)), 0, 1)
    d = np.linalg.norm(x - a - t * (b - a))
    out += h * math.exp(-(d / rad) ** 2) * (1.0 - 0.3 * t)
    # the bottom ears, pulled out at the ends of the bottom seam
    if v < 0.07:
        out += 0.022 * (1 - v / 0.07) * max(0.0, abs(math.sin(ph)) ** 6)
    # only the outside bulges: the side against the back is pressed flat
    return out * smooth01((math.cos(ph) + 0.6) / 0.6)


def frame_x_full(v):
    t = np.array(full_center(min(v + 0.01, 1.0))) - np.array(full_center(max(v - 0.01, 0.0)))
    t /= np.linalg.norm(t)
    x = np.array([1.0, 0.0, 0.0]) - t * t[0]
    return x / np.linalg.norm(x)


def frame_o_full(v):
    t = np.array(full_center(min(v + 0.01, 1.0))) - np.array(full_center(max(v - 0.01, 0.0)))
    t /= np.linalg.norm(t)
    o = np.cross(t, frame_x_full(v))
    return o if o[1] > 0 else -o


def flatten_full(R):
    """The sack pressed flat on the back (1.6 cm off the hit boxes)."""
    sh = R.shape
    P = push_out(R.reshape(-1, 3), TORSO + ("LeftArm", "RightArm"), 0.016)
    return P.reshape(sh)


FULL_V = [0.0, 0.02, 0.045, 0.075, 0.11, 0.15, 0.19, 0.235, 0.28, 0.33, 0.38, 0.43, 0.48, 0.53, 0.58, 0.625, 0.665,
          0.70, 0.735, 0.77, 0.80, 0.83, 0.855, 0.875, 0.9, 0.925, 0.95, 0.975, 0.99, 1.0]

# ---------------------------------------------------------------- the empty sack

EW, EH = 0.18, 0.465  # half its width, its length from the bottom to where it disappears into the tie
E_TOP = NECK[2] - 0.012


def empty_outline():
    return [(-EW, 0.0), (-0.1, -0.006), (-0.03, 0.004), (0.06, -0.003), (0.13, 0.005), (EW, 0.0), (EW + 0.004, 0.18),
            (EW - 0.002, 0.33),
            (0.12, 0.40), (0.03, EH), (-0.03, EH), (-0.12, 0.40), (-EW + 0.003, 0.33), (-EW - 0.004, 0.18)]


def empty_uv_to(PQ, lift):
    """The flat sack's pattern (u across, v up from its bottom) laid down the back, hanging from the neck."""
    PQ = np.atleast_2d(PQ)
    u, v = PQ[:, 0], PQ[:, 1]
    z = E_TOP - (EH - v)
    x = NECK[0] - 0.02 + u * (1.0 - 0.35 * smooth01((v - 0.3) / 0.17))
    theta = math.pi - np.arcsin(np.clip(x / 0.24, -0.97, 0.97))  # hangs flatter than it would wrap
    return wrap(theta, z, lift)


def empty_lift(PQ, front):
    """Off the back: the two layers of burlap lie together (5 mm), folded and crumpled as one."""
    PQ = np.atleast_2d(PQ)
    u, v = PQ[:, 0], PQ[:, 1]
    drape_f = 0.02 * np.maximum(0.0, np.sin(2 * math.pi * u / 0.13 + 1.6 * np.sin(5 * v) + 0.6)) ** 1.6 \
        * (0.3 + 0.7 * smooth01((0.36 - v) / 0.3))
    sag = 0.012 * smooth01((0.2 - np.abs(v - 0.12)) / 0.2) * smooth01((EW - np.abs(u)) / 0.1)  # a little left in it
    pleats = 0.016 * np.abs(np.sin(2 * math.pi * u / 0.05)) * smooth01((v - 0.28) / 0.16)
    crumple = 0.006 * np.sin(31 * u + 7 * v) * np.sin(13 * v - 9 * u) + 0.004 * np.sin(57 * u - 23 * v)
    curl = 0.035 * smooth01((0.07 - v) / 0.07) * smooth01((u - 0.06) / 0.1)  # the free corner curls off the back
    return 0.011 + drape_f + sag + pleats + crumple + curl + (0.005 if front else 0.0)


def empty_front(PQ):
    return empty_uv_to(PQ, empty_lift(PQ, True))


def empty_back(PQ):
    return empty_uv_to(PQ, empty_lift(PQ, False))


def neck_profile_empty(v):
    """Below the tie the empty sack is bunched flat on the back; above it the same tuft as the full one."""
    if v >= 0.86:
        r = tuft_profile(v)
        return r, r, lambda vv, ph: tuft(vv, ph)
    a = float(np.interp(v, [0.8, 0.83, 0.86], [0.05, 0.034, RT]))
    b = float(np.interp(v, [0.8, 0.83, 0.86], [0.016, 0.022, RT]))
    return a, b, lambda vv, ph: 0.2 * smooth01((vv - 0.8) / 0.03) * math.sin(9 * ph)


def frame_x_neck(v):
    return XN


def frame_o_neck(v):
    return ON


# ---------------------------------------------------------------- build both parts

rope_mat = hemp("Hemp")
sack_e_mat = burlap("BurlapEmpty", (0.0, 0.2, 1.0), False)
sack_f_mat = None  # made after the full sack's u at its front is known

full_sack = loft("SackFull", None, FULL_V, full_profile, full_center, frame_x_full, frame_o_full, nj=28,
                 seam_phi=90.0, bumps=full_bumps, flatten=flatten_full)
# its print sits on the outside (phi = 0), a third of the way up
_circ_mid = 2 * math.pi * math.sqrt((0.214 ** 2 + 0.148 ** 2) / 2)
sack_f_mat = burlap("BurlapFull", (_circ_mid * 270.0 / 360.0, 0.2, 1.08), True)
full_sack.data.materials.clear()
full_sack.data.materials.append(sack_f_mat)
full_tree = BVHTree.FromPolygons([v.co.copy() for v in full_sack.data.vertices],
                                 [list(p.vertices) for p in full_sack.data.polygons])

empty_sheet = slab("Sack", [outline(empty_outline(), step=0.04, round_r=0.01)], empty_front, empty_back,
                   np.array([0.0, 1.0, 0.0]), sack_e_mat, dense=0.042, sparse=None, inset=0.006, roll=0.002)
tk.smooth(empty_sheet, 70)
# the sheet's rim is its sewn edge: mark the side seams
_a = empty_sheet.data.attributes[ATTR]
for d in _a.data:
    pu, pv, side = d.vector
    d.vector = (pu, pv, 1.0 if (abs(abs(pu) - EW) < 0.02 and pv < 0.36) else 0.0)
empty_neck = loft("SackNeck", sack_e_mat, [0.8, 0.82, 0.84, 0.86, 0.9, 0.925, 0.95, 0.975, 0.99, 1.0],
                  neck_profile_empty, neck_center, frame_x_neck, frame_o_neck, nj=16, seam_phi=90.0)

# Bottom right corners where the rope's end is tied
corner_full = None
best = None
for vtx in full_sack.data.vertices:
    p = np.array(vtx.co)
    if p[2] < B0[2] + 0.04:
        score = -p[0] + 0.3 * p[2]
        if best is None or score > best:
            best, corner_full = score, p
corner_full = corner_full + np.array([-0.004, -0.01, 0.006])
corner_empty = empty_front(np.array([[-EW + 0.012, 0.016]]))[0]

e_rope, s_end = shared_rope("E", rope_mat)
f_rope, _ = shared_rope("F", rope_mat)
e_tail = corner_rope("E", rope_mat, corner_empty, s_end)
f_tail = corner_rope("F", rope_mat, corner_full, s_end, sack_tree=full_tree)

empty_part = [empty_sheet, empty_neck] + e_rope + e_tail
full_part = [full_sack] + f_rope + f_tail

# ---------------------------------------------------------------- checks, export, previews


def report(tag, objs):
    V = np.array([v.co[:] for o in objs for v in o.data.vertices])
    tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
    print("[%s] %-9s %4d triangles, bounds %s to %s" % (NAME, tag, tris, np.round(V.min(0), 3), np.round(V.max(0), 3)))
    for bones in (("Spine2",), ("Hips",), ("LeftArm",), ("RightArm",), ("Head",), ("LeftUpLeg", "RightUpLeg")):
        d = sdf(V, bones)
        k = int(np.argmin(d))
        print("[%s]   closest to %-10s %6.1f mm at %s" % (NAME, bones[0], d[k] * 1000, np.round(V[k], 3)))
    for o in objs:
        print("[%s]     %-14s %4d tris" % (NAME, o.name, sum(len(f.vertices) - 2 for f in o.data.polygons)))


report("Sack", empty_part)
report("SackFull", full_part)

for o in empty_part:
    zk.on(o, "Spine2", "Sack")
for o in full_part:
    zk.on(o, "Spine2", "SackFull")
pieces = empty_part + full_part
for o in pieces:
    set_attr(o, [v.co[:] for v in o.data.vertices], POS)
# Bake with the full sack 2 m aside, so neither variant shades the other
OFFSET = Vector((2.0, 0.0, 0.0))
for o in full_part:
    o.data.transform(Matrix.Translation(OFFSET))
for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS)
for o in BODY:
    o.hide_render = False
full_obj = [p for p in parts if p.name.endswith("#SackFull")][0]
empty_obj = [p for p in parts if p.name.endswith("#Sack")][0]
full_obj.data.transform(Matrix.Translation(-OFFSET))
tk.export_fbx([parts[0].parent] + parts, os.path.join(ASSETS, NAME + ".fbx"))
print("[%s] parts %s written with the full sack back in place" % (NAME, [p.name for p in parts]))

FAST = os.environ.get("ZX_FAST", "")  # while iterating: only these comma-separated views, at fewer samples
focus = Vector((0.0, 0.12, 1.28))
for tag, show, hide in (("", full_obj, empty_obj), ("_empty", empty_obj, full_obj)):
    show.hide_render = False
    hide.hide_render = True
    if not FAST:
        zk.previews(SCRIPT + tag, PREVIEWS, focus, distance=1.75)
    for view, loc, tgt, lens in (("close", (-0.55, 0.85, 1.55), (0.02, 0.24, 1.25), 50),
                                 ("chest", (0.25, -0.9, 1.5), (0.0, -0.05, 1.33), 50),
                                 ("profile", (1.2, 0.2, 1.35), (0.0, 0.15, 1.25), 50)):
        if FAST and (view + tag) not in FAST.split(","):
            continue
        tk.render(tk.camera("ss_" + view + tag, Vector(loc), Vector(tgt), lens=lens),
                  os.path.join(PREVIEWS, "%s%s_%s.png" % (SCRIPT, tag, view)), res=(900, 900), samples=32 if FAST else 64)
for p in parts:
    p.hide_render = False
print("[%s] done" % SCRIPT)
