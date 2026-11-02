"""Car door: the rear door off a small car (80 x 70 cm), worn on the zombie's left forearm as a shield. Faded dark
green paint gone chalky up top, rusting through along the bottom, round the wheel-arch cutout and at the hems,
dented, keyed, shot through four times, a survivor's kill tally sprayed on in white, blood run down from the sill.
The window glass is gone (a few crumbs of it left in the channels), the little fixed quarter light behind the divider
is still in, filthy. Black window frame and belt-line rubber, black pull handle, the hinges and check strap torn off
the car with the cut wiring loom still hanging out of its boot. The inner skin is bare: dark e-coat, body colour round
the shut edges, the trim's clip holes and the big access holes.

It is strapped on with a leather trouser belt run down the window slot, out through an access hole and buckled round
the forearm, a rolled-up flannel shirt wedged between the arm and the door. In the bind pose (the arm hanging 45
degrees down and out) the flat inner skin lies along the forearm 2.7 cm off it, so the door faces the zombie's front
turned out and tipped up the way the arm hangs, its top leaning in toward the neck: it covers the left side of the
torso from the shoulder to the hip, and comes upright when the arm hangs down. One part, LeftForeArm#Shield.

    blender -b --factory-startup --python car_door.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.geometry import delaunay_2d_cdt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT = "CarDoor", "car_door"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex (p, q, side): the door's own flat coordinates; side 1 on the outer skin, 0 inside

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
    with rims round every loop. Writes (p, q, side) to zx_local: 1 on the front, 0.6 on its rolled edge, 0 behind."""
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
    latb = material(_lattice(outer, sparse, 0.0), 0.6 * sparse)
    V2b, Fb, srcb = _cdt_loops(list(allL) + list(latb), sizes, sizes[0])
    Fb = keep(V2b, Fb)

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


# ---------------------------------------------------------------- printed masks (rasterized in the door's p, q)


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


# ---------------------------------------------------------------- where the door sits

# Searched (against the hand's bones, the hit boxes and how much of the torso it covers) for a pose that lays the
# forearm along the flat inner skin 2.7 cm off it and keeps the bind pose's forward-pointing thumb and fingers behind
# it, with the door clear of the chest: turned out and tipped up the way the arm hangs, its top leaning in toward the
# neck, the forearm near the hinge edge (so the door reaches across the torso).
QB = 0.07  # the belt line (window sill) in the door's own coordinates
FW = 0.028  # window frame width
ARC_C, ARC_R = np.array([-0.45, -0.45]), 0.28  # the rear wheel arch cut out of the lower rear corner
YAW = math.radians(30.0)
PITCH = math.atan(math.sin(YAW))  # the flat inner skin parallel to the forearm (hanging 45 degrees in x-z)
TILT = math.radians(30.0)
PM, QM = 0.275, -0.025  # where the middle of the forearm lies on the inner skin, from the door's center
GAP, FINGER_GAP = 0.022, 0.011


def frame(pitch):
    n = np.array([math.sin(YAW) * math.cos(pitch), -math.cos(YAW) * math.cos(pitch), math.sin(pitch)])
    wy = np.array([math.cos(YAW), math.sin(YAW), 0.0])
    up = np.cross(n, wy)
    return n, wy * math.cos(TILT) + up * math.sin(TILT), up * math.cos(TILT) - wy * math.sin(TILT)


NRM, WA, UA = frame(PITCH)  # out of the door's outer skin, across it (toward the hinge edge), up it
ELBOW, WRIST = np.array(sk.pos("LeftForeArm")), np.array(sk.pos("LeftHand"))
FA_A, FA_B, FA_R = capsule("LeftForeArm")
HAND = np.array([sk.pos(b) for b in sk.bones if b.startswith("LeftHand")])
_c0 = (ELBOW + WRIST) / 2 - WA * PM - UA * QM
_need = [(FA_A + (FA_B - FA_A) * t, GAP + FA_R) for t in np.linspace(0.0, 1.0, 21)] + [(h, FINGER_GAP) for h in HAND]
CENTER = _c0 + NRM * max(room + (x - _c0) @ NRM for x, room in _need)  # on the inner skin's plane
FA_AXIS = (WRIST - ELBOW) / np.linalg.norm(WRIST - ELBOW)


def to_pq(X):
    d = np.asarray(X) - CENTER
    return np.array([d @ WA, d @ UA])


def behind(X):
    """How far X is behind the inner skin."""
    return -(np.asarray(X) - CENTER) @ NRM


# The belt goes round the forearm just below the sill: there it runs down the window slot and out of an access hole
_ts = np.linspace(0.0, 1.0, 101)
_qs = np.array([to_pq(ELBOW + (WRIST - ELBOW) * t)[1] for t in _ts])
STATION = ELBOW + (WRIST - ELBOW) * _ts[np.argmin(np.abs(_qs - (QB - 0.035)))]
P_S = to_pq(STATION)[0]
HOLE_PQ = np.array([P_S + 0.01, QB - 0.075])


# ---------------------------------------------------------------- the door's shape (p across toward the hinges, q up)

def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


DENTS = [(0.13, -0.2, 0.065, 0.009), (-0.12, -0.08, 0.045, 0.006), (0.27, 0.0, 0.05, 0.005), (-0.02, -0.29, 0.07, 0.01),
         (0.33, -0.27, 0.04, 0.006)]


def thickness(PQ):
    """From the flat inner skin to the outer skin: the lower door bulges, thicker at the bottom; the frame is thin."""
    PQ = np.atleast_2d(PQ)
    p, q = PQ[:, 0], PQ[:, 1]
    ql = np.minimum(q, QB)
    base = 0.046 + 0.026 * np.clip((QB - ql) / 0.42, 0, 1)
    v = np.clip(1 - ((ql + 0.1) / 0.3) ** 2, 0, 1)
    h = np.clip(1 - (p / 0.46) ** 2, 0, 1)
    lower = base + 0.024 * v * h
    for pc, qc, r, depth in DENTS:
        lower = lower - depth * np.exp(-((p - pc) ** 2 + (q - qc) ** 2) / (r * r))
    # a long scrape pressed in across the lower door
    a, b = np.array([-0.3, -0.13]), np.array([0.08, -0.19])
    ab = b - a
    t = np.clip(((p - a[0]) * ab[0] + (q - a[1]) * ab[1]) / (ab @ ab), 0, 1)
    lower = lower - 0.0035 * np.exp(-((p - a[0] - t * ab[0]) ** 2 + (q - a[1] - t * ab[1]) ** 2) / 0.012 ** 2)
    s = smooth01((q - QB) / 0.012)
    return lower * (1 - s) + 0.03 * s


def back_3d(PQ):
    PQ = np.atleast_2d(PQ)
    return CENTER[None] + PQ[:, :1] * WA[None] + PQ[:, 1:2] * UA[None]


def front_3d(PQ):
    return back_3d(PQ) + thickness(PQ)[:, None] * NRM[None]


def offset_poly(poly, d, keep=()):
    """Each edge of a CCW polygon moved inward by d (edges listed in keep stay), corners mitred."""
    P = np.asarray(poly, float)
    n = len(P)
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        t = (b - a) / np.linalg.norm(b - a)
        lines.append((a + np.array([-t[1], t[0]]) * (0.0 if i in keep else d), t))
    out = []
    for i in range(n):
        (a1, t1), (a2, t2) = lines[i - 1], lines[i]
        s, _ = np.linalg.solve(np.array([t1, -t2]).T, a2 - a1)
        out.append(a1 + s * t1)
    return np.array(out)


def clip(poly, a, nrm):
    """The part of a convex polygon where (x - a) . nrm >= 0."""
    out = []
    n = len(poly)
    for i in range(n):
        P, Q = poly[i], poly[(i + 1) % n]
        dp, dq = (P - a) @ nrm, (Q - a) @ nrm
        if dp >= 0:
            out.append(P)
        if (dp >= 0) != (dq >= 0):
            out.append(P + (Q - P) * (dp / (dp - dq)))
    return np.array(out)


ARC = [tuple(ARC_C + ARC_R * np.array([math.cos(a), math.sin(a)])) for a in np.radians(np.linspace(79.7, 20.9, 16))]
DOOR = [(-0.1885, -0.35), (0.385, -0.35), (0.4, -0.335), (0.4, QB), (0.396, 0.30), (0.372, 0.336), (0.0, 0.352),
        (-0.19, 0.347), (-0.4, 0.13), (-0.4, -0.1745)] + ARC[1:-1]
FRAME = [(0.4, QB), (0.396, 0.30), (0.372, 0.336), (0.0, 0.352), (-0.19, 0.347), (-0.4, 0.13), (-0.4, QB)]
_win = offset_poly(FRAME, FW, keep=(6,))
D0, D1 = np.array([-0.2, QB]), np.array([-0.168, 0.36])  # the divider bar between the window and the quarter light
_dd = (D1 - D0) / np.linalg.norm(D1 - D0)
_nd = np.array([_dd[1], -_dd[0]])
DIV = 0.022
WINDOW = clip(_win, D0 + _nd * DIV / 2, _nd)
QUARTER = clip(_win, D0 - _nd * DIV / 2, -_nd)

O_DOOR = outline(DOOR, step=0.04, round_r=0.007, angle=math.radians(25))
O_WIN = outline(WINDOW, step=0.04, round_r=0.01, angle=math.radians(25))
O_QTR = outline(QUARTER, step=0.04, round_r=0.008, angle=math.radians(25))
# The window's bottom edge is the sill: keep it straight on the belt line
O_WIN[:, 1] = np.where(O_WIN[:, 1] < QB + 0.004, QB, O_WIN[:, 1])
O_QTR[:, 1] = np.where(O_QTR[:, 1] < QB + 0.004, QB, O_QTR[:, 1])


# ---------------------------------------------------------------- printed masks (p, q)

BOX = (-0.42, -0.37, 0.42, 0.37)
SHAPE = (740, 840)  # 1 px per mm
_X, _Y = grid_xy(SHAPE, BOX)


def poly_sd(poly, X=None, Y=None, chunk=60):
    """Signed distance to a closed polygon over the mask grid (negative inside)."""
    X = _X if X is None else X
    Y = _Y if Y is None else Y
    P = np.stack([X.ravel(), Y.ravel()], axis=1)
    d = np.empty(len(P))
    for k in range(0, len(P), chunk * 1000):
        d[k:k + chunk * 1000] = _seg_dist(P[k:k + chunk * 1000], np.asarray(poly))
    ins = _inside(P, np.asarray(poly))
    return np.where(ins, -d, d).reshape(X.shape)


def ellipse_sd(c, a, b, ang=0.0):
    ca, sa = math.cos(ang), math.sin(ang)
    dx, dy = _X - c[0], _Y - c[1]
    lx, ly = dx * ca + dy * sa, -dx * sa + dy * ca
    return (np.hypot(lx / a, ly / b) - 1.0) * min(a, b)


SHOTS = [(0.15, -0.07), (-0.06, -0.22), (0.3, -0.25), (-0.17, -0.13)]
HANDLE = (-0.27, 0.012)
_shot = np.min([np.hypot(_X - x, _Y - y) for x, y in SHOTS], axis=0)


def _tally():
    """A survivor's kill count sprayed on: four gates of five and three more."""
    rng = np.random.default_rng(3)
    strokes = []
    x = -0.1
    for grp in range(5):
        n = 4 if grp < 4 else 3
        xs = []
        for k in range(n):
            x0 = x + rng.normal(0, 0.002)
            y0, y1 = -0.305 + rng.normal(0, 0.004), -0.215 + rng.normal(0, 0.005)
            strokes.append([(x0, y0), (x0 + rng.normal(0, 0.003), (y0 + y1) / 2), (x0 + rng.normal(0, 0.004), y1)])
            xs.append(x0)
            x += 0.021
        if n == 4:
            strokes.append([(xs[0] - 0.012, -0.29 + rng.normal(0, 0.004)), (xs[-1] + 0.013, -0.228 + rng.normal(0, 0.004))])
        x += 0.022
    return strokes


_strokes = _tally()
_paint = lines_mask(SHAPE, BOX, _strokes, 0.0095)
_mist = lines_mask(SHAPE, BOX, _strokes, 0.032)
FRONT = mask_image("CarDoorFront", [np.clip(0.5 - ellipse_sd(HANDLE, 0.085, 0.03) / 0.004, 0, 1),
                                    np.clip(1 - _shot / 0.026, 0, 1), np.maximum(_paint, 0.3 * _mist)])

# Inside: the access holes (signed distance, 0.5 on the cut edge), body colour round the shut edges, clip holes
ACCESS = [((0.06, -0.13), 0.11, 0.07, 0.15), ((-0.21, -0.03), 0.07, 0.045, -0.2), ((-0.15, -0.23), 0.055, 0.055, 0.0),
          ((0.27, -0.11), 0.045, 0.03, 0.3), ((HOLE_PQ[0], HOLE_PQ[1]), 0.024, 0.017, 0.0)]
_acc = np.min([ellipse_sd(c, a, b, t) for c, a, b, t in ACCESS], axis=0)
_edge = poly_sd(O_DOOR)
_shut = np.clip((_edge + 0.05) / 0.006 + 0.5, 0, 1)  # within 5 cm of the door's edge
_clips = np.zeros(SHAPE)
for k in range(0, len(O_DOOR), 3):
    i = k
    n2 = _left_normals(O_DOOR)[i]
    c = O_DOOR[i] + n2 * 0.065
    if c[1] < QB - 0.03:
        _clips = np.maximum(_clips, np.clip(0.5 - (np.maximum(np.abs(_X - c[0]), np.abs(_Y - c[1])) - 0.0045) / 0.001,
                                            0, 1))
BACK = mask_image("CarDoorInside", [np.clip(0.5 - _acc / 0.03, 0, 1), _shut, _clips])


# ---------------------------------------------------------------- materials


def door_skin(name):
    """The whole door shell: outer skin (paint), window frame (satin black), inner skin (e-coat), edges and sill."""
    mat, g = tk.new_material(name)
    W_ = g.coords()
    P = mapping(g, W_, loc=(3.1, 0.7, 1.9))
    p, q, side = attr_uvw(g)
    handle_rec, shot, tally = decal(g, FRONT, p, q, BOX)
    acc, shut, clips = decal(g, BACK, p, q, BOX)

    def nz(scale, detail=4.0, r=0.55, dist=0.0, vec=None):
        return g.noise(scale, detail=detail, roughness=r, vector=vec if vec is not None else P, distortion=dist)

    # Door-down drips: noise stretched along q
    cq = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("MULTIPLY", p, 60.0), cq.inputs[0])
    g.links.new(g.math("MULTIPLY", q, 3.0), cq.inputs[1])
    streak_vec = cq.outputs[0]

    # ---- body paint: faded dark green, chalky up top, rust coming through
    ph = tk.photo(g, "green_metal_rust", 1.2, (0.31, 0.12, 0.57))
    rust = tk.photo(g, "rust_coarse_01", 1.6, (0.71, 0.33, 0.12))
    paint = tk.grade(g, ph["color"], 0.72, 0.95)
    paint = g.mix(g.math("MULTIPLY", g.ramp(nz(4.0, 5.0), 0.3, 0.75), 0.5), paint, tk._darker(g, paint, 0.7))
    chalk = g.math("MULTIPLY", g.ramp(q, -0.15, 0.05), g.ramp(nz(3.0, 6.0, 0.6, 0.4), 0.35, 0.7))
    paint = g.mix(g.math("MULTIPLY", chalk, 0.4), paint, (0.07, 0.083, 0.07))
    blot = g.ramp(nz(2.2, 6.0, 0.65, 0.5), 0.5, 0.7)
    paint = g.mix(g.math("MULTIPLY", blot, 0.45), paint, tk._darker(g, paint, 0.55))
    prough = g.mixf(chalk, g.math("ADD", 0.38, g.math("MULTIPLY", ph["rough"], 0.25)), 0.75)
    pheight = g.math("MULTIPLY", ph["height"], 0.3)
    # rust: along the bottom, round the wheel arch, at the hems, in blisters, round the bullet holes
    ap = g.math("ADD", p, -ARC_C[0])
    aq = g.math("ADD", q, -ARC_C[1])
    arc_d = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", ap, ap),
                                                                          g.math("MULTIPLY", aq, aq))), ARC_R))
    brk = nz(9.0, 8.0, 0.7, 0.3)
    r_bot = g.math("ADD", g.ramp(q, -0.23, -0.34), g.ramp(arc_d, 0.045, 0.0))
    r_edge = g.math("MULTIPLY", g.ramp(g.edges(0.008), 0.05, 0.3), 0.8)
    r_blis = g.ramp(nz(6.0, 8.0, 0.7, 0.5), 0.66, 0.69)
    r_shot = g.math("MULTIPLY", g.ramp(shot, 0.25, 0.42), 0.9)
    rm = g.math("MAXIMUM", g.math("MAXIMUM", r_bot, r_edge), g.math("MAXIMUM", r_blis, r_shot))
    rm = g.ramp(g.math("ADD", rm, g.math("MULTIPLY", g.math("SUBTRACT", brk, 0.5), 0.9)), 0.45, 0.6)
    rcol = g.mix(g.ramp(tk._luma(g, rust["color"]), 0.05, 0.2), (0.06, 0.03, 0.015), tk.grade(g, rust["color"], 0.8, 0.8))
    # rust run down from the holes and the handle
    runs = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=streak_vec), 0.55, 0.75),
                  g.math("MAXIMUM", g.ramp(shot, 0.0, 0.05), g.ramp(q, -0.05, -0.3)))
    runs = g.math("MULTIPLY", runs, 0.6)
    col = g.mix(rm, paint, rcol)
    col = g.mix(runs, col, (0.09, 0.04, 0.018))
    rough = g.mixf(rm, prough, 0.88)
    metal = g.mixf(rm, 0.25, 0.05)
    height = g.math("ADD", pheight, g.math("MULTIPLY", g.math("MAXIMUM", rm, r_blis), 0.5))
    # keyed scratches through to grey primer, and worn hems to bare steel
    sc = g.math("MULTIPLY", scratch_mask(g, mapping(g, P, loc=(0.2, 0.5, 0.1)), 0.02), g.ramp(nz(2.5, 3.0), 0.45, 0.7))
    col = g.mix(sc, col, (0.22, 0.22, 0.2))
    rough = g.mixf(sc, rough, 0.6)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.4))
    # bullet holes: black hole, a ring of bright torn steel, paint flaked off round it
    rag = g.math("ADD", shot, g.math("MULTIPLY", g.math("SUBTRACT", nz(140.0, 4.0, 0.7), 0.5), 0.08))
    hole = g.ramp(rag, 0.77, 0.8)
    ring = g.math("MULTIPLY", g.ramp(rag, 0.66, 0.71), g.math("SUBTRACT", 1.0, hole))
    flake = g.math("MULTIPLY", g.ramp(g.math("ADD", shot, g.math("MULTIPLY", g.math("SUBTRACT", nz(80.0), 0.5), 0.3)),
                                      0.42, 0.47), g.math("SUBTRACT", 1.0, ring))
    col = g.mix(flake, col, g.mix(g.ramp(nz(50.0), 0.3, 0.7), (0.11, 0.1, 0.09), (0.1, 0.05, 0.025)))
    col = g.mix(ring, col, g.mix(g.ramp(nz(60.0), 0.35, 0.65), (0.2, 0.19, 0.18), (0.12, 0.07, 0.04)))
    metal = g.mixf(ring, metal, 0.9)
    rough = g.mixf(ring, rough, 0.35)
    col = g.mix(hole, col, (0.008, 0.007, 0.006))
    rough = g.mixf(hole, rough, 0.95)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("ADD", hole, g.math("MULTIPLY", ring, 0.5)), 1.2))
    # the pull handle's recess: a darker dished pocket
    col = g.mix(g.math("MULTIPLY", handle_rec, 0.8), col, (0.02, 0.022, 0.02))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", handle_rec, 0.8))
    # the kill tally: white spray paint, faded and flaking, a speckled mist round it
    solid = g.ramp(tally, 0.45, 0.6)
    mist = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(tally, 0.05, 0.3), g.math("SUBTRACT", 1.0, solid)),
                  g.ramp(voronoi(g, P, 260.0), 0.25, 0.08))
    spray = g.math("MAXIMUM", g.math("MULTIPLY", solid, g.ramp(nz(30.0, 6.0, 0.7), 0.3, 0.55)), g.math("MULTIPLY", mist, 0.5))
    spray = g.math("MULTIPLY", spray, g.mixf(g.ramp(nz(4.0, 4.0), 0.3, 0.7), 0.55, 0.9))
    col = g.mix(spray, col, (0.3, 0.3, 0.28))
    rough = g.mixf(spray, rough, 0.7)
    # the character line pressed along the door (shading only)
    height = g.math("ADD", height, g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", q, -0.03)), 0.008, 0.0),
                                          0.7))

    # ---- window frame: satin black, chipped to primer at the corners and edges
    fcol = g.mix(g.ramp(nz(6.0), 0.3, 0.7), (0.016, 0.016, 0.017), (0.03, 0.03, 0.031))
    fchip = g.math("MULTIPLY", g.ramp(g.edges(0.005), 0.05, 0.3), g.ramp(nz(35.0, 5.0, 0.7), 0.42, 0.55))
    fchip = g.math("MAXIMUM", fchip, g.ramp(nz(14.0, 8.0, 0.7), 0.68, 0.7))
    fcol = g.mix(fchip, fcol, g.mix(nz(20.0), (0.2, 0.19, 0.18), (0.12, 0.06, 0.03)))
    frough = g.mixf(fchip, 0.5, 0.75)
    fheight = g.math("SUBTRACT", g.math("MULTIPLY", nz(120.0), 0.1), g.math("MULTIPLY", fchip, 0.4))

    # ---- inner skin: dark e-coat, body colour round the shut edges, access and clip holes, rust run down
    icol = g.mix(g.ramp(nz(5.0, 4.0), 0.3, 0.7), (0.03, 0.031, 0.033), (0.055, 0.055, 0.056))
    icol = g.mix(shut, icol, tk._darker(g, paint, 0.85))
    inside = g.ramp(acc, 0.5, 0.56)
    cut = g.math("MULTIPLY", g.ramp(acc, 0.45, 0.49), g.math("SUBTRACT", 1.0, g.ramp(acc, 0.5, 0.52)))
    cavity = g.mix(g.ramp(nz(12.0, 6.0, 0.7), 0.4, 0.7), (0.012, 0.009, 0.007), (0.05, 0.025, 0.012))
    icol = g.mix(inside, icol, g.mix(g.ramp(acc, 0.56, 0.8), cavity, (0.006, 0.005, 0.004)))
    icol = g.mix(cut, icol, (0.26, 0.25, 0.24))
    icol = g.mix(clips, icol, (0.008, 0.008, 0.008))
    iruns = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=streak_vec), 0.58, 0.78),
                   g.math("MAXIMUM", g.ramp(q, -0.1, -0.33), g.ramp(acc, 0.35, 0.5)))
    irust = g.math("MAXIMUM", g.math("MULTIPLY", iruns, 0.8), g.math("MULTIPLY", g.ramp(q, -0.27, -0.35), brk))
    icol = g.mix(irust, icol, rcol)
    irough = g.mixf(irust, g.mixf(inside, 0.55, 0.9), 0.85)
    imetal = g.mixf(cut, 0.0, 0.9)
    iheight = g.math("ADD", g.math("SUBTRACT", g.math("MULTIPLY", nz(90.0), 0.1), g.math("MULTIPLY", inside, 1.5)),
                     g.math("MULTIPLY", irust, 0.3))

    # ---- the window sill's edge: black felt, the glass slot down its middle, crumbs of glass in it
    sill = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", q, QB)), 0.0025, 0.0005),
                  g.math("MULTIPLY", g.ramp(side, 0.03, 0.08), g.ramp(side, 0.57, 0.52)))
    slot = g.math("MULTIPLY", sill, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", side, 0.3)), 0.07, 0.04))
    crumbs = g.math("MULTIPLY", g.math("MULTIPLY", sill, g.ramp(voronoi(g, P, 120.0), 0.14, 0.06)),
                    g.ramp(nz(11.0), 0.5, 0.65))

    # ---- choose by zone: the frame above the belt line, the inner skin behind, the paint everywhere else
    frame_z = g.ramp(q, QB + 0.001, QB + 0.006)
    back_z = g.ramp(side, 0.06, 0.02)
    col = g.mix(frame_z, col, fcol)
    rough = g.mixf(frame_z, rough, frough)
    metal = g.mixf(frame_z, metal, 0.0)
    height = g.mixf(frame_z, height, fheight)
    col = g.mix(back_z, col, icol)
    rough = g.mixf(back_z, rough, irough)
    metal = g.mixf(back_z, metal, imetal)
    height = g.mixf(back_z, height, iheight)
    col = g.mix(sill, col, (0.018, 0.017, 0.016))
    rough = g.mixf(sill, rough, 0.9)
    col = g.mix(slot, col, (0.003, 0.003, 0.003))
    col = g.mix(crumbs, col, (0.3, 0.32, 0.31))
    rough = g.mixf(crumbs, rough, 0.1)

    # ---- over everything: road grime low down, dust, blood run down from the sill, specks
    p2 = tk.photo(g, "metal_plate_02", 2.4, (0.5, 0.2, 0.9))
    grime = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p2["color"]), 0.2, 0.06),
                                     g.mixf(g.ramp(q, -0.05, -0.33), 0.25, 0.85)), tk._grime(g, 0.7))
    col = g.mix(g.math("MULTIPLY", grime, 0.75), col, g.mix(nz(7.0), (0.045, 0.038, 0.028), (0.1, 0.085, 0.06)))
    rough = g.mixf(grime, rough, 0.9)
    metal = g.mixf(grime, metal, 0.0)
    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    dust = g.math("MULTIPLY", g.ramp(up, 0.3, 0.9), g.ramp(nz(8.0, 6.0, 0.6), 0.35, 0.65))
    dust = g.math("MULTIPLY", g.math("MULTIPLY", dust, g.mixf(frame_z, 0.5, 0.2)), g.math("SUBTRACT", 1.0, sill))
    col = g.mix(dust, col, (0.26, 0.235, 0.19))
    rough = g.mixf(dust, rough, 0.95)
    bl_drip = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=5.0, vector=streak_vec), 0.62, 0.7),
                     g.math("MULTIPLY", g.ramp(q, -0.2, 0.03), g.ramp(p, 0.35, 0.05)))
    bl_spat = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 30.0), 0.14, 0.05),
                     g.ramp(nz(2.0, 4.0, 0.6, 0.5), 0.5, 0.62))
    bl = g.math("MULTIPLY", g.math("MAXIMUM", bl_drip, bl_spat), g.ramp(side, 0.3, 0.6))
    bfresh = g.ramp(nz(9.0), 0.4, 0.7)
    col = g.mix(bl, col, g.mix(bfresh, (0.03, 0.006, 0.004), (0.075, 0.009, 0.006)))
    rough = g.mixf(bl, rough, g.mixf(bfresh, 0.6, 0.35))
    metal = g.mixf(bl, metal, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", bl, 0.15))
    col, rough, metal = tk._grit(g, col, rough, metal, 0.22)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.002))


def flannel(name):
    """A torn-up flannel shirt rolled tight: faded red and black plaid, grimy, soaked through with old blood."""
    mat, g = tk.new_material(name)
    s, ca, sa = attr_uvw(g)
    P = mapping(g, g.coords(), loc=(0.4, 1.1, 0.3))
    u = g.math("MULTIPLY", s, 1.0)
    v = g.math("MULTIPLY", g.math("ARCTAN2", sa, ca), 0.1 / (2 * math.pi))  # round the roll: two repeats

    def stripes(x, period, width):
        f = g.math("FRACT", g.math("DIVIDE", x, period))
        return g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", f, 0.5)), 0.5 - width, 0.5 - width + 0.04)

    su = g.math("MAXIMUM", stripes(g.math("ADD", u, g.math("MULTIPLY", v, 0.7)), 0.05, 0.22),
                g.math("MULTIPLY", stripes(g.math("ADD", u, 0.012), 0.05, 0.05), 0.6))
    sv = g.math("MAXIMUM", stripes(g.math("SUBTRACT", v, g.math("MULTIPLY", u, 0.7)), 0.05, 0.22),
                g.math("MULTIPLY", stripes(g.math("ADD", v, 0.02), 0.05, 0.05), 0.6))
    dark = g.math("MULTIPLY", su, sv)
    col = g.mix(g.math("MAXIMUM", su, sv), (0.15, 0.035, 0.03), (0.07, 0.02, 0.018))
    col = g.mix(dark, col, (0.02, 0.016, 0.014))
    col = g.mix(g.ramp(g.noise(5.0, detail=5.0, vector=P), 0.3, 0.75), col, tk.grade(g, col, 0.6, 1.4))
    weave = g.noise(400.0, detail=2.0, vector=P)
    height = g.math("MULTIPLY", weave, 0.3)
    p = tk.photo(g, "rust_coarse_01", 2.0, (0.5, 0.2, 0.33))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.25, 0.08), 0.7), tk._grime(g, 0.8))
    col = g.mix(g.math("MULTIPLY", dirt, 0.75), col, (0.05, 0.04, 0.03))
    blood = g.ramp(g.noise(3.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P), 0.52, 0.62)
    col = g.mix(blood, col, (0.045, 0.008, 0.006))
    rough = g.mixf(blood, g.math("ADD", 0.85, g.math("MULTIPLY", weave, 0.1)), 0.6)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


def leather(name):
    """A worn brown trouser belt: crazed and cracked, scuffed pale on the edges, a stitch line along each edge, the
    holes punched along its tail end, greasy dark where hands held it."""
    mat, g = tk.new_material(name)
    s, a, _ = attr_uvw(g)
    P = mapping(g, g.coords(), loc=(2.2, 0.4, 1.6))
    col = g.mix(g.ramp(g.noise(6.0, detail=5.0, vector=P), 0.3, 0.75), (0.07, 0.038, 0.018), (0.12, 0.068, 0.034))
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", 260.0)
    g.links.new(warp(g, P, 30.0, 0.002), vor.inputs["Vector"])
    craze = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.05, 0.0), g.ramp(g.noise(12.0, vector=P), 0.4, 0.6))
    col = g.mix(craze, col, (0.035, 0.02, 0.01))
    edge = g.ramp(g.math("ABSOLUTE", a), 0.36, 0.5)
    worn = g.math("MAXIMUM", g.math("MULTIPLY", edge, g.ramp(g.noise(30.0, vector=P), 0.3, 0.6)),
                  g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.1, 0.4), 0.7))
    col = g.mix(worn, col, (0.2, 0.13, 0.075))
    stitch = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", a), 0.36)), 0.035, 0.015),
                    g.ramp(g.math("FRACT", g.math("DIVIDE", s, 0.005)), 0.35, 0.55))
    col = g.mix(stitch, col, (0.16, 0.13, 0.09))
    holes = g.math("MULTIPLY", g.ramp(g.math("ADD", g.math("MULTIPLY", g.math("ABSOLUTE", a), 6.0),
                                             g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT",
                                                                                          g.math("DIVIDE", s, 0.025)), 0.5))),
                                      0.22, 0.17), g.ramp(s, BELT_HOLES0, BELT_HOLES0 + 0.005))
    col = g.mix(holes, col, (0.008, 0.006, 0.005))
    rough = g.mixf(worn, g.mixf(craze, 0.5, 0.75), 0.65)
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", g.noise(150.0, vector=P), 0.2), g.math("MULTIPLY", stitch, 0.3)),
                    g.math("ADD", g.math("MULTIPLY", craze, 0.4), holes))
    p = tk.photo(g, "rust_coarse_01", 2.0, (0.1, 0.7, 0.4))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.25, 0.08), 0.6), tk._grime(g, 0.7))
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.04, 0.03, 0.02))
    rough = g.mixf(dirt, rough, 0.85)
    blood = g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=6.0, distortion=0.6, vector=P), 0.58, 0.66), 0.85)
    col = g.mix(blood, col, (0.04, 0.007, 0.005))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.002))


BELT_HOLES0 = 0.0  # set once the belt's length is known (the holes run along its tail)
skin = door_skin("DoorSkin")
glass_mat = wear("QuarterGlass", (0.012, 0.014, 0.015), rough=0.05, seed=51.0, tone=0.3, scratches=0.3,
                 scratch_col=(0.16, 0.17, 0.17), dark_scratches=0.0, scuffs=0.5, scuff_col=(0.05, 0.052, 0.05),
                 edges=0.0, dirt=0.8, dirt_set="metal_plate_02", dirt_range=(0.22, 0.06), grime=0.9, dust=0.5,
                 specks=0.6, blood=0.3, grease=0.3, bump=0.1, grain=0.02,
                 dirt_col=((0.035, 0.03, 0.022), (0.09, 0.077, 0.055)))
rubber = wear("Rubber", (0.016, 0.016, 0.017), rough=0.75, seed=52.0, tone=0.25, scratches=0.3,
              scratch_col=(0.07, 0.07, 0.07), scuffs=0.5, scuff_col=(0.045, 0.044, 0.043), edges=0.5,
              edge_col=(0.075, 0.073, 0.07), dirt=0.7, dirt_range=(0.2, 0.06), grime=0.8, dust=0.35, specks=0.5,
              bump=0.4, dirt_col=((0.02, 0.017, 0.014), (0.05, 0.044, 0.036)))
plastic = wear("HandlePlastic", (0.02, 0.02, 0.021), rough=0.45, seed=53.0, tone=0.25, scratches=0.5,
               scratch_col=(0.09, 0.09, 0.09), scuffs=0.5, scuff_col=(0.05, 0.05, 0.05), edges=0.6,
               edge_col=(0.1, 0.1, 0.1), dirt=0.7, dirt_range=(0.2, 0.06), grime=0.9, dust=0.3, specks=0.4,
               blood=0.3, bump=0.3, dirt_col=((0.025, 0.02, 0.016), (0.06, 0.05, 0.04)))
hinge_mat = tk.photo_material("HingeSteel", "rusty_painted_metal", scale=3.0, sat=0.35, value=0.55,
                              exposed="rust_coarse_01", chip=0.9, grime=0.7, patches=0.6, metal_floor=0.4, grit=0.4,
                              scratches=0.3, edges=0.5)
steel = wear("Buckle", (0.2, 0.2, 0.2), rough=0.4, metal=0.9, seed=54.0, tone=0.3, scratches=0.5,
             scratch_col=(0.45, 0.45, 0.45), scratch_metal=1.0, scuffs=0.3, edges=0.5, edge_col=(0.5, 0.5, 0.5),
             dirt=0.7, dirt_range=(0.22, 0.07), grime=0.9, dust=0.2, specks=0.4, bump=0.3,
             dirt_col=((0.06, 0.035, 0.02), (0.13, 0.07, 0.035)))
WIRE_COLS = [(0.12, 0.02, 0.015), (0.13, 0.1, 0.02), (0.02, 0.04, 0.09), (0.03, 0.06, 0.025), (0.09, 0.09, 0.085)]
wire_mats = [tk.grimy("Wire%d" % i, c, roughness=0.45, grime=0.6, grit=0.3) for i, c in enumerate(WIRE_COLS)]
copper = tk.tarnished_copper("WireCopper")
rag_mat = flannel("Flannel")

# ---------------------------------------------------------------- the door

pieces = []
door = slab("Door", [O_DOOR, O_WIN[::-1], O_QTR[::-1]], front_3d, back_3d, NRM, skin, dense=0.045, sparse=0.1,
            inset=0.011, roll=0.007)
pieces.append(door)

# The quarter light: its glass still in, set back in the frame
O_GL = outline(offset_poly(QUARTER, -0.006), step=0.05, round_r=0.006)
gl_depth = 0.014


def glass_front(PQ):
    return back_3d(PQ) + NRM[None] * (gl_depth + 0.002)


def glass_back(PQ):
    return back_3d(PQ) + NRM[None] * (gl_depth - 0.002)


pieces.append(slab("QuarterGlass", [O_GL], glass_front, glass_back, NRM, glass_mat, dense=0.08, sparse=0.08,
                   inset=0.004, roll=0.001))

# The belt-line rubber along the top of the outer skin
bl_rings = []
for pp in np.linspace(-0.392, 0.392, 22):
    pq = np.array([[pp, QB - 0.002]])
    top = front_3d(pq)[0]
    nn = surface_normals(front_3d, pq, NRM)[0]
    prof = [(-0.009, -0.007), (0.004, -0.007), (0.006, 0.0), (0.004, 0.007), (-0.009, 0.007)]
    bl_rings.append([Vector(top + nn * a + UA * b) for a, b in prof])
pieces.append(tk.smooth(ring_sweep("BeltRubber", bl_rings, rubber, closed=False, caps=True), 50))

# Exterior pull handle near the opening edge
hp_ = np.array([HANDLE])
hc = front_3d(hp_)[0]
hn = surface_normals(front_3d, hp_, NRM)[0]
pieces.append(block("Handle", (0.125, 0.024, 0.02), plastic, hc + hn * 0.008, WA, UA, hn, bevel=0.007, segments=2))
for sgn in (1, -1):
    pq = np.array([[HANDLE[0] + sgn * 0.055, HANDLE[1]]])
    pieces.append(block("HandleFoot", (0.02, 0.02, 0.012), plastic, front_3d(pq)[0] + hn * 0.002, WA, UA, hn,
                        bevel=0.004))

# Hinges and check strap torn off the car, the wiring loom cut and hanging out of its boot
for i, qh in enumerate((-0.22, 0.0)):
    mid = back_3d(np.array([[0.4, qh]]))[0] + NRM * (thickness(np.array([[0.39, qh]]))[0] * 0.5)
    pieces.append(block("HingeLeaf%d" % i, (0.05, 0.055, 0.012), hinge_mat, mid + WA * 0.02, WA, UA, NRM, bevel=0.002))
    knuckle = mid + WA * 0.047
    pieces.append(rod("HingePin%d" % i, knuckle - UA * 0.03, knuckle + UA * 0.03, 0.009, hinge_mat, sides=8))
    # the body-side leaf, bent back and torn
    bend = math.radians(55.0 if i == 0 else -35.0)
    ex = WA * math.cos(bend) + NRM * math.sin(bend)
    pieces.append(block("HingeTorn%d" % i, (0.04, 0.05, 0.004), hinge_mat, knuckle + ex * 0.026, ex, UA,
                        np.cross(ex, UA), bevel=0.001))
    for k, dq in enumerate((-0.016, 0.016)):
        b0 = mid + WA * 0.012 + UA * dq + NRM * 0.006
        pieces.append(rod("HingeBolt%d_%d" % (i, k), b0, b0 + NRM * 0.006, 0.0075, hinge_mat, sides=6))
cs = back_3d(np.array([[0.4, -0.11]]))[0] + NRM * 0.03
pieces.append(block("CheckStrap", (0.075, 0.014, 0.005), hinge_mat, cs + WA * 0.035, WA, UA, NRM, bevel=0.001))
pieces.append(block("CheckStop", (0.014, 0.024, 0.016), hinge_mat, cs + WA * 0.07, WA, UA, NRM, bevel=0.002))
boot0 = back_3d(np.array([[0.4, 0.04]]))[0] + NRM * 0.024
pieces.append(rod("WireBoot", boot0 - WA * 0.004, boot0 + WA * 0.042, 0.012, rubber, sides=8, radius_b=0.009))
rng = np.random.default_rng(11)
for k, m in enumerate(wire_mats):
    a0 = boot0 + WA * 0.04 + UA * rng.uniform(-0.004, 0.004) + NRM * rng.uniform(-0.004, 0.004)
    d = WA + UA * rng.uniform(-0.6, 0.3) + NRM * rng.uniform(-0.5, 0.5) - np.array([0, 0, 0.4])
    d /= np.linalg.norm(d)
    length = rng.uniform(0.025, 0.055)
    a1 = a0 + d * length
    pieces.append(rod("Wire%d" % k, a0, a1, 0.0019, m, sides=5))
    pieces.append(rod("WireEnd%d" % k, a1, a1 + d * 0.006, 0.001, copper, sides=4))

# ---------------------------------------------------------------- the rag and the belt

gap = behind(ELBOW) - FA_R
rag_r = (gap + 0.012) / 2
print("[%s] forearm %.1f mm behind the inner skin (elbow), %.1f mm (wrist); rag radius %.1f mm" % (
    NAME, (behind(ELBOW) - FA_R) * 1000, (behind(WRIST) - FA_R) * 1000, rag_r * 1000))
rag_rings, rag_attr = [], []
ref = np.cross(FA_AXIS, NRM)
ref /= np.linalg.norm(ref)
for k, t in enumerate(np.linspace(0.2, 0.8, 20)):
    c = ELBOW + (WRIST - ELBOW) * t + NRM * (FA_R - 0.012 + rag_r)
    taper = smooth01(min(t - 0.2, 0.8 - t) / 0.07) * 0.75 + 0.25
    ring = []
    for j in range(8):
        a = 2 * math.pi * j / 8
        lump = 1.0 + 0.16 * math.sin(3 * a + t * 31.0) + 0.1 * math.sin(5 * a - t * 17.0 + 1.3)
        r = rag_r * taper * lump
        ring.append(Vector(c + (NRM * math.cos(a) + ref * math.sin(a)) * r))
        rag_attr.append((t * np.linalg.norm(WRIST - ELBOW), math.cos(a), math.sin(a)))
    rag_rings.append(ring)
rag = tk.smooth(ring_sweep("Rag", rag_rings, rag_mat, closed=False, caps=True), 60)
set_attr(rag, rag_attr)
pieces.append(rag)

# The belt: down the window slot, out through an access hole, round the forearm and the rag, buckled on the far side
S = STATION
lip = back_3d(np.array([[P_S, QB]]))[0]
slot = (front_3d(np.array([[P_S, QB - 0.001]]))[0] + lip) / 2
hole3 = back_3d(HOLE_PQ[None])[0]
nb = NRM - FA_AXIS * (NRM @ FA_AXIS)
nb /= np.linalg.norm(nb)  # from the arm toward the door
sb = np.cross(FA_AXIS, nb)
rs = FA_R + 0.006
up_side = UA - FA_AXIS * (UA @ FA_AXIS)
if sb @ up_side < 0:
    sb = -sb  # sb points from the arm toward the sill


def ang(v):
    return math.atan2(v @ sb, v @ nb)


def tangent_angle(P_):
    v = P_ - S - FA_AXIS * ((P_ - S) @ FA_AXIS)
    L = np.linalg.norm(v)
    return ang(v), math.acos(min(1.0, rs / L))


a_lip, da_lip = tangent_angle(lip)
a_hole, da_hole = tangent_angle(hole3)
a0 = a_lip + da_lip  # leave the sill side round the far side of the arm (through 180 degrees)
a1 = a_hole - da_hole + 2 * math.pi
if a1 < a0:
    a1 += 2 * math.pi
arc = []
for a in np.linspace(a0, a1, 14):
    tt = (a - a0) / (a1 - a0)
    c = S + FA_AXIS * (((lip - S) @ FA_AXIS) * (1 - tt) + ((hole3 - S) @ FA_AXIS) * tt)
    arc.append(c + rs * (nb * math.cos(a) + sb * math.sin(a)))
path = [slot - UA * 0.03, slot + UA * 0.004, lip + UA * 0.006 - NRM * 0.003] + arc + \
    [hole3 - NRM * 0.004 + UA * 0.004, hole3 + NRM * 0.02]
core = (S + lip + hole3) / 3 + NRM * 0.01
nrms = []
for k, pnt in enumerate(path):
    if k < 2:
        nrms.append(UA)
    else:
        v = pnt - core
        nrms.append(v / np.linalg.norm(v))
BELT_W, BELT_T = 0.034, 0.0042
belt = band("Belt", path, nrms, BELT_W, BELT_T, None)
seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array(path), axis=0), axis=1))])
set_attr(belt, [(seg[i], a, 0.0) for i in range(len(path)) for a, _ in FLAT])

# The buckle on the far side of the arm, and the belt's tail run through it and hanging off
kb = 3 + int(len(arc) * 0.55)
bt = path[kb + 1] - path[kb - 1]
bt /= np.linalg.norm(bt)
bn = nrms[kb]
bw = np.cross(bn, bt)
bc = path[kb] + bn * 0.004
corners = [bc + bt * x + bw * y for x, y in ((-0.022, -0.026), (0.022, -0.026), (0.022, 0.026), (-0.022, 0.026))]
for k in range(4):
    pieces.append(rod("BuckleFrame%d" % k, corners[k], corners[(k + 1) % 4], 0.0026, steel, sides=6))
pieces.append(rod("BucklePin", bc - bt * 0.022 + bn * 0.002, bc + bt * 0.012 + bn * 0.004, 0.0018, steel, sides=5))
tail = [path[kb] + bn * 0.0055 + bt * x for x in (-0.03, 0.0, 0.03, 0.055)]
end = tail[-1]
for k in range(4):
    end = end + bt * 0.022 + np.array([0.0, 0.0, -0.025]) * (k + 1) * 0.5
    tail.append(end + bn * 0.002 * k)
tail_n = [bn] * len(tail)
tail_obj = band("BeltTail", tail, tail_n, BELT_W, BELT_T, None)
tseg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array(tail), axis=0), axis=1))]) + seg[-1] + 0.1
set_attr(tail_obj, [(tseg[i], a, 0.0) for i in range(len(tail)) for a, _ in FLAT])
BELT_HOLES0 = tseg[2]
leather_mat = leather("Leather")
for o in (belt, tail_obj):
    o.data.materials.clear()
    o.data.materials.append(leather_mat)
pieces += [belt, tail_obj]

# ---------------------------------------------------------------- checks, export, previews


def report(objs):
    V = np.array([v.co[:] for o in objs for v in o.data.vertices])
    tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
    print("[%s] %d triangles, bounds %s to %s" % (NAME, tris, np.round(V.min(0), 3), np.round(V.max(0), 3)))
    for bones in (("Spine2",), ("Hips",), ("LeftArm",), ("LeftForeArm",), ("Head",), ("LeftUpLeg",)):
        d = sdf(V, bones)
        k = int(np.argmin(d))
        print("[%s] closest to %-12s %6.1f mm at %s" % (NAME, bones[0], d[k] * 1000, np.round(V[k], 3)))
    dv = np.array([v.co[:] for v in door.data.vertices])
    print("[%s] door shell: closest to the torso %.1f mm, upper arm %.1f mm, forearm %.1f mm" % (
        NAME, sdf(dv, ("Spine2", "Hips")).min() * 1000, sdf(dv, ("LeftArm",)).min() * 1000,
        sdf(dv, ("LeftForeArm",)).min() * 1000))
    for o in objs:
        print("[%s]   %-14s %4d tris" % (NAME, o.name, sum(len(f.vertices) - 2 for f in o.data.polygons)))


for o in pieces:
    zk.on(o, "LeftForeArm", "Shield")
report(pieces)
for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS)
for o in BODY:
    o.hide_render = False

FAST = os.environ.get("ZX_FAST", "")  # while iterating: only these comma-separated close-ups, at fewer samples
focus = Vector((0.24, -0.08, 1.2))
if not FAST:
    zk.previews(SCRIPT, PREVIEWS, focus, distance=2.2)
for view, loc, tgt, lens in (("straight", (0.2, -2.7, 1.2), (0.2, 0.0, 1.15), 50),
                             ("top", (0.22, -0.12, 2.8), (0.22, -0.12, 1.25), 50),
                             ("close", (0.0, -0.95, 1.35), (0.24, -0.12, 1.15), 50),
                             ("hinge", (0.95, -0.55, 1.45), (0.5, -0.08, 1.25), 50),
                             ("back_close", (0.95, 0.75, 0.95), (0.42, 0.0, 1.18), 50)):
    if FAST and view not in FAST.split(","):
        continue
    tk.render(tk.camera("cd_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=32 if FAST else 64)
print("[%s] done" % SCRIPT)
