"""Riot shield: a police riot shield (90 x 50 cm) strapped to the zombie's left forearm. Dark tinted polycarbonate
(opaque: the game's model shader can't do see-through), glossy, curved round its long axis, its rubber edge trim
scuffed. POLICE in worn white vinyl letters across the top, scratched and scuffed all over, a crazed impact crack, a
bloody handprint dragged down the front. On the back: a foam arm pad the forearm lies on, a webbing arm strap round the
forearm and a grip at the hand, bolted through (the bolt heads show on the front).

It rides the forearm: in the bind pose (the arm hanging 45 degrees down and out) the forearm lies along its back 2 cm
off it, on the pad, so the face looks to the zombie's front (-Y) turned out and tipped up the way the arm hangs, the top
leaning in toward the neck: it covers the left side of the torso from the shoulder to the hip, and comes upright when
the arm hangs down. One part, LeftForeArm#Shield.

    blender -b --factory-startup --python riot_shield.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "RiotShield", "riot_shield"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "zx_local"  # per-vertex (p, q, front): the shield's own flat coordinates, 1 on its front face

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


def slab(name, O, to3d, nrm3d, thick, mat, spacing=0.06):
    """A thin sheet cut to the closed 2D outline O: front face at to3d(p, q), back face `thick` behind it along the
    front normals nrm3d(p, q), a square-cut rim. Writes (p, q, front) into zx_local."""
    n0 = len(O)
    pts = list(O) + list(_lattice(O, spacing, 0.6 * spacing))
    V2, F, src = _cdt(pts, n0)
    Pf = to3d(V2)
    Pb = Pf - nrm3d(V2) * thick
    bm = bmesh.new()
    vf = [bm.verts.new(p) for p in Pf]
    vb = [bm.verts.new(p) for p in Pb]
    for f in F:
        bm.faces.new([vf[i] for i in f])
        bm.faces.new([vb[i] for i in reversed(f)])
    edge = {s: i for i, s in enumerate(src) if 0 <= s < n0}
    for k in range(n0):
        a, b = edge[k], edge[(k + 1) % n0]
        bm.faces.new((vf[a], vb[a], vb[b], vf[b]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, [(p, q, 1.0) for p, q in V2] + [(p, q, 0.0) for p, q in V2])
    return tk.smooth(obj, 40)


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


# ---------------------------------------------------------------- printed masks (rasterized in the shield's p, q)


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


# ---------------------------------------------------------------- where the shield sits

# Searched (against the hand's bones, the hit boxes and how much of the torso it covers) for a pose that lays the
# forearm along the back 2 cm off, keeps the bind pose's forward-pointing thumb and index finger behind it and the
# inner edge in front of the chest: the long axis leans in toward the neck, near the arm's own line (so when the arm
# hangs down in game the shield comes upright), the face turned outward and tipped up to follow the arm.
YAW = math.radians(30.0)  # the face turned this far outward (toward +X) from straight ahead
TILT = math.radians(35.0)  # the long axis leaning in (top toward the neck) from upright
HW, HH = 0.25, 0.45  # half width and height
R_BEND = 0.85  # curved round the long axis: the side edges bend back 3.7 cm
THICK = 0.006
GAP = 0.02  # at least this from the back face to the forearm's hit box
FINGER_GAP = 0.011  # and from the hand's bones (a fingertip's half thickness and a little air)
PM, QM = 0.14, 0.06  # where the middle of the forearm lies on the shield's back, from its center

ELBOW, WRIST = np.array(sk.pos("LeftForeArm")), np.array(sk.pos("LeftHand"))
FA_A, FA_B, FA_R = capsule("LeftForeArm")
HAND_BONES = [b for b in sk.bones if b.startswith("LeftHand")]
HAND = np.array([sk.pos(b) for b in HAND_BONES])


def frame(pitch):
    """The face's normal (turned out by YAW, up by pitch), the across and the long axis (leaning in by TILT)."""
    n = np.array([math.sin(YAW) * math.cos(pitch), -math.cos(YAW) * math.cos(pitch), math.sin(pitch)])
    wy = np.array([math.cos(YAW), math.sin(YAW), 0.0])
    up = np.cross(n, wy)
    return n, wy * math.cos(TILT) + up * math.sin(TILT), up * math.cos(TILT) - wy * math.sin(TILT)


def _gap(X, c, n, w):
    d = np.asarray(X) - c
    p = d @ w
    return -(p * p) / (2 * R_BEND) - THICK - d @ n


def _place(n, w, u):
    """Pushes the shield out along its normal until the forearm and every hand bone are behind it with room."""
    c0 = (ELBOW + WRIST) / 2 - w * PM - u * QM
    need = [(FA_A + (FA_B - FA_A) * t, GAP + FA_R) for t in np.linspace(0.0, 1.0, 21)] + [(h, FINGER_GAP) for h in HAND]
    k = max(room - _gap(f, c0, n, w) for f, room in need)
    return c0 + n * k


# Pitch it up until the forearm lies parallel to the back (the same gap at the elbow and the wrist)
lo, hi = math.radians(-10.0), math.radians(35.0)
for _ in range(40):
    mid = (lo + hi) / 2
    n_, w_, u_ = frame(mid)
    c_ = _place(n_, w_, u_)
    if _gap(ELBOW, c_, n_, w_) > _gap(WRIST, c_, n_, w_):
        lo = mid
    else:
        hi = mid
PITCH = (lo + hi) / 2
NRM, WA, UA = frame(PITCH)
CENTER = _place(NRM, WA, UA)
_bind = max(range(len(HAND)), key=lambda i: FINGER_GAP - _gap(HAND[i], CENTER, NRM, WA))
print("[%s] pitch %.1f deg; tightest hand bone %s" % (NAME, math.degrees(PITCH), HAND_BONES[_bind]))


def gap_at(X):
    """How far the back face is in front of point X (along the shield's normal)."""
    return _gap(X, CENTER, NRM, WA)


def shield_3d(PQ, lift=0.0):
    PQ = np.atleast_2d(PQ)
    p, q = PQ[:, 0], PQ[:, 1]
    bend = -(p * p) / (2 * R_BEND) + lift
    return CENTER[None] + p[:, None] * WA[None] + q[:, None] * UA[None] + bend[:, None] * NRM[None]


def shield_n(PQ):
    PQ = np.atleast_2d(PQ)
    n = NRM[None] + (PQ[:, 0] / R_BEND)[:, None] * WA[None]
    return n / np.linalg.norm(n, axis=1)[:, None]


def to_pq(X):
    d = np.asarray(X) - CENTER
    return np.array([d @ WA, d @ UA])


def back_point(p, q, lift=0.0):
    """A point on the back face (lift = further back, toward the zombie) and the back-facing normal there."""
    n = shield_n((p, q))[0]
    return shield_3d((p, q))[0] - n * (THICK + lift), -n


def front_point(p, q, lift=0.0):
    n = shield_n((p, q))[0]
    return shield_3d((p, q))[0] + n * lift, n


# ---------------------------------------------------------------- the printed and damaged face

BOX = (-HW, -HH, HW, HH)
SHAPE = (900, 500)  # 1 px per mm


def _cracks():
    """A crazed impact star (radial cracks and rings between them) and a smaller one low down."""
    rng = np.random.default_rng(7)
    out = []
    for (cx, cy), n_rays, reach in (((-0.07, 0.07), 9, 0.15), ((0.12, -0.27), 6, 0.07)):
        rays = []
        for k in range(n_rays):
            a = 2 * math.pi * k / n_rays + rng.uniform(-0.25, 0.25)
            length = reach * rng.uniform(0.45, 1.0)
            pts, p = [np.array([cx, cy])], np.array([cx, cy])
            s = 0.0
            while s < length:
                a += rng.normal(0, 0.18)
                step = 0.006
                p = p + step * np.array([math.cos(a), math.sin(a)])
                pts.append(p)
                s += step
                if rng.uniform() < 0.05 and s > 0.02:  # a branch
                    b = a + rng.choice([-1, 1]) * rng.uniform(0.4, 0.9)
                    q, bp = p.copy(), [p.copy()]
                    for _ in range(int(rng.uniform(3, 9))):
                        b += rng.normal(0, 0.2)
                        q = q + step * np.array([math.cos(b), math.sin(b)])
                        bp.append(q)
                    out.append(bp)
            rays.append(pts)
            out.append(pts)
        # Rings: broken arcs between neighbouring rays
        for rr in (0.018, 0.034, 0.055):
            if rr > reach * 0.6:
                continue
            for k in range(n_rays):
                if rng.uniform() < 0.35:
                    continue
                a0 = math.atan2(*(rays[k][min(len(rays[k]) - 1, 4)] - np.array([cx, cy]))[::-1])
                a1 = math.atan2(*(rays[(k + 1) % n_rays][min(len(rays[(k + 1) % n_rays]) - 1, 4)]
                                  - np.array([cx, cy]))[::-1])
                if a1 < a0:
                    a1 += 2 * math.pi
                if a1 - a0 > 1.6:
                    continue
                arc = [np.array([cx, cy]) + rr * rng.uniform(0.9, 1.1) * np.array([math.cos(t), math.sin(t)])
                       for t in np.linspace(a0, a1, 5)]
                out.append(arc)
    return out


def _handprint():
    """A bloody hand pressed on the lower front and dragged down."""
    X, Y = grid_xy(SHAPE, BOX)
    px = (BOX[2] - BOX[0]) / SHAPE[1]
    c = np.array([0.075, -0.1])
    ang = math.radians(-12.0)  # fingers up, turned a little
    ca, sa = math.cos(ang), math.sin(ang)

    def local(x, y):
        dx, dy = x - c[0], y - c[1]
        return dx * ca + dy * sa, -dx * sa + dy * ca

    lx, ly = local(X, Y)
    d = np.hypot(lx / 0.043, ly / 0.05) - 1.0
    d = d * 0.045
    for fx, length in ((-0.03, 0.068), (-0.01, 0.083), (0.011, 0.079), (0.03, 0.062)):
        a, b = np.array([fx, 0.035]), np.array([fx * 1.15, 0.035 + length])
        ab = b - a
        t = np.clip(((lx - a[0]) * ab[0] + (ly - a[1]) * ab[1]) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.hypot(lx - a[0] - t * ab[0], ly - a[1] - t * ab[1]) - 0.0095)
    a, b = np.array([0.04, -0.01]), np.array([0.085, 0.035])
    ab = b - a
    t = np.clip(((lx - a[0]) * ab[0] + (ly - a[1]) * ab[1]) / (ab @ ab), 0, 1)
    d = np.minimum(d, np.hypot(lx - a[0] - t * ab[0], ly - a[1] - t * ab[1]) - 0.011)
    hand = np.clip(0.5 - d / px, 0, 1)
    # Dragged down: each finger and the heel of the hand smeared 6-14 cm below
    smear = np.zeros_like(hand)
    for fx, reach in ((-0.03, 0.09), (-0.01, 0.13), (0.011, 0.11), (0.03, 0.07), (0.0, 0.06)):
        x0 = c[0] + fx
        w = np.exp(-((X - x0 + (Y - c[1]) * 0.08) / 0.008) ** 2)
        fall = np.clip((c[1] + 0.03 - Y) / reach, 0, 1)
        smear = np.maximum(smear, w * (1 - fall) * (Y < c[1] + 0.03) * (Y > c[1] - reach))
    # A few drips run down from it
    for x0, top, length in ((0.06, -0.15, 0.09), (0.098, -0.12, 0.14), (0.04, -0.2, 0.05)):
        w = np.exp(-((X - x0) / 0.0025) ** 2)
        smear = np.maximum(smear, w * (Y < top) * (Y > top - length) * np.clip((Y - (top - length)) / 0.02, 0, 1))
    return np.clip(np.maximum(hand, smear * 0.85), 0, 1)


_letters = raster(SHAPE, BOX, fit(glyph_tris("POLICE", "C:/Windows/Fonts/arialbd.ttf", 1.04),
                                  (-0.2, 0.235, 0.2, 0.325)))
_crack = lines_mask(SHAPE, BOX, _cracks(), 0.0007)
_crack = np.maximum(_crack, 0.8 * np.clip(0.5 - (np.hypot(*(np.array(grid_xy(SHAPE, BOX))
                                                          - np.array([-0.07, 0.07])[:, None, None])) - 0.005) / 0.002,
                                          0, 1))
IMG = mask_image("RiotShieldPrint", [_letters, _crack, _handprint()])


def shield_decals(g, W_, P, col, rgh, met, height):
    """POLICE in white vinyl (peeling, cracked and scuffed), the crack lines, the handprint and drips."""
    u, v, front = attr_uvw(g)
    letters, crack, hand = decal(g, IMG, u, v, BOX)
    face = g.ramp(front, 0.6, 0.95)
    peel = g.math("MAXIMUM", g.ramp(g.noise(9.0, detail=6.0, roughness=0.7, vector=P), 0.64, 0.68),
                  g.ramp(g.noise(60.0, detail=5.0, roughness=0.7, vector=P), 0.7, 0.74))
    lmask = g.math("MULTIPLY", g.math("MULTIPLY", letters, face), g.math("SUBTRACT", 1.0, peel))
    vinyl = g.mix(g.ramp(g.noise(14.0, vector=P), 0.3, 0.7), (0.5, 0.5, 0.48), (0.38, 0.37, 0.34))
    vinyl = g.mix(g.math("MULTIPLY", scratch_mask(g, mapping(g, P, loc=(0.4, 0.1, 0.7)), 0.05), 0.8), vinyl,
                  (0.05, 0.05, 0.05))
    col = g.mix(lmask, col, vinyl)
    rgh = g.mixf(lmask, rgh, 0.5)
    height = g.math("ADD", height, g.math("MULTIPLY", lmask, 0.35))
    # Glue left where letters peeled off: a dull ghost of them
    ghost = g.math("MULTIPLY", g.math("MULTIPLY", letters, face), peel)
    col = g.mix(g.math("MULTIPLY", ghost, 0.6), col, (0.06, 0.06, 0.058))
    rgh = g.mixf(ghost, rgh, 0.7)
    # Cracks: faint pale hairlines, broken up, a frosted halo round them and a crushed white spot at the impact
    cbreak = g.ramp(g.noise(30.0, detail=4.0, vector=P), 0.3, 0.6)
    cl = g.math("MULTIPLY", crack, g.mixf(cbreak, 0.35, 1.0))
    halo = g.math("MULTIPLY", g.ramp(crack, 0.0, 0.5), 0.3)
    col = g.mix(halo, col, (0.05, 0.055, 0.06))
    col = g.mix(cl, col, (0.2, 0.21, 0.22))
    rgh = g.mixf(cl, rgh, 0.3)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", cl, 0.5))
    # The handprint: old dried blood, dark and flaking, thin where it was smeared
    flake = g.ramp(g.noise(55.0, detail=6.0, roughness=0.7, vector=P), 0.26, 0.5)
    hb = g.math("MULTIPLY", g.math("MULTIPLY", hand, face), flake)
    hb = g.math("MULTIPLY", hb, g.ramp(g.noise(6.0, detail=3.0, vector=P), 0.15, 0.4))
    thick = g.ramp(g.noise(18.0, detail=4.0, vector=P), 0.35, 0.7)
    col = g.mix(hb, col, g.mix(thick, (0.085, 0.014, 0.009), (0.04, 0.007, 0.005)))
    rgh = g.mixf(hb, rgh, g.mixf(thick, 0.55, 0.32))
    height = g.math("ADD", height, g.math("MULTIPLY", hb, 0.25))
    return col, rgh, met, height


# ---------------------------------------------------------------- materials

poly_mat = wear("Polycarbonate", (0.011, 0.013, 0.017), rough=0.04, seed=41.0, tone=0.35, scratches=0.5,
                scratch_col=(0.17, 0.18, 0.19), dark_scratches=0.0, scuffs=0.3, scuff_col=(0.035, 0.038, 0.042),
                edges=0.0, dirt=0.3, dirt_set="metal_plate_02", dirt_scale=3.0, dirt_range=(0.13, 0.04), grime=0.35,
                dust=0.18, specks=0.35, blood=0.2, grease=0.45, bump=0.12, grain=0.02, line_width=0.022,
                decals=shield_decals, dirt_col=((0.018, 0.016, 0.013), (0.05, 0.043, 0.033)))
trim_mat = wear("EdgeRubber", (0.016, 0.016, 0.017), rough=0.72, seed=42.0, tone=0.25, scratches=0.35,
                scratch_col=(0.075, 0.075, 0.075), scuffs=0.5, scuff_col=(0.045, 0.044, 0.043), edges=0.5,
                edge_col=(0.08, 0.078, 0.075), dirt=0.6, dirt_range=(0.2, 0.06), grime=0.7, dust=0.25, specks=0.5,
                blood=0.2, bump=0.4, dirt_col=((0.018, 0.016, 0.014), (0.045, 0.04, 0.034)))
pad_mat = wear("ArmPad", (0.028, 0.028, 0.03), rough=0.88, seed=43.0, tone=0.35, scratches=0.0, scuffs=0.5,
               scuff_col=(0.06, 0.06, 0.062), edges=0.6, edge_col=(0.075, 0.073, 0.07), dirt=0.8,
               dirt_set="metal_plate_02", dirt_range=(0.35, 0.1), grime=1.0, dust=0.2, specks=0.6, blood=0.45,
               bump=0.6, grain=0.5, grain_scale=320.0, dirt_col=((0.018, 0.015, 0.012), (0.06, 0.05, 0.036)))
strap_mat = wear("Webbing", (0.022, 0.023, 0.026), rough=0.78, seed=44.0, tone=0.3, scratches=0.0, scuffs=0.4,
                 scuff_col=(0.06, 0.06, 0.065), edges=0.7, edge_col=(0.08, 0.078, 0.075), dirt=0.7,
                 dirt_range=(0.3, 0.08), grime=0.9, dust=0.2, specks=0.5, blood=0.35, bump=0.5, grain=0.6,
                 grain_scale=520.0, dirt_col=((0.02, 0.016, 0.012), (0.065, 0.054, 0.04)))
grip_mat = wear("Grip", (0.018, 0.018, 0.019), rough=0.55, seed=45.0, tone=0.2, scratches=0.4,
                scratch_col=(0.09, 0.09, 0.09), scuffs=0.5, scuff_col=(0.05, 0.05, 0.05), edges=0.5,
                edge_col=(0.1, 0.1, 0.1), dirt=0.6, dirt_range=(0.2, 0.06), grime=0.9, dust=0.2, specks=0.4,
                blood=0.4, grease=0.5, bump=0.4)
steel = wear("Hardware", (0.09, 0.09, 0.094), rough=0.5, metal=0.8, seed=46.0, tone=0.3, scratches=0.5,
             scratch_col=(0.42, 0.42, 0.42), scratch_metal=1.0, scuffs=0.3, edges=0.6, edge_col=(0.45, 0.45, 0.45),
             dirt=0.7, dirt_range=(0.22, 0.07), grime=0.9, dust=0.3, specks=0.4, bump=0.3,
             dirt_col=((0.05, 0.035, 0.022), (0.12, 0.07, 0.035)))

# ---------------------------------------------------------------- the shield

CORNER_TOP, CORNER_BOT = 0.075, 0.045


def rounded_rect(hw, hh, rt, rb, n=10):
    pts = []
    for (cx, cy, r, a0) in ((hw - rb, -hh + rb, rb, -90), (hw - rt, hh - rt, rt, 0), (-hw + rt, hh - rt, rt, 90),
                            (-hw + rb, -hh + rb, rb, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


O = outline(rounded_rect(HW, HH, CORNER_TOP, CORNER_BOT), step=0.05, round_r=0.002, angle=math.radians(25))
pieces = [slab("Shield", O, shield_3d, shield_n, THICK, poly_mat, spacing=0.062)]

# Rubber edge trim: a U-channel round the whole edge
mids = shield_3d(O) - shield_n(O) * (THICK / 2)
nrm = shield_n(O)
ht = THICK / 2 + 0.0026
PROFILE = [(-0.009, ht), (0.0012, ht), (0.0045, ht * 0.45), (0.0045, -ht * 0.45), (0.0012, -ht), (-0.009, -ht)]
rings = []
for i in range(len(O)):
    t3 = mids[(i + 1) % len(O)] - mids[i - 1]
    t3 /= np.linalg.norm(t3)
    e = np.cross(t3, nrm[i])
    e /= np.linalg.norm(e)
    if e @ (mids[i] - CENTER) < 0:
        e = -e
    rings.append([Vector(mids[i] + e * a + nrm[i] * b) for a, b in PROFILE])
trim = tk.smooth(ring_sweep("EdgeTrim", rings, trim_mat, closed=True), 50)
pieces.append(trim)

# ---------------------------------------------------------------- the arm pad, strap and grip on the back

fa_axis = (WRIST - ELBOW) / np.linalg.norm(WRIST - ELBOW)
pe, pw = to_pq(ELBOW), to_pq(WRIST)
along2 = (pw - pe) / np.linalg.norm(pw - pe)  # the forearm's direction on the shield
across2 = np.array([-along2[1], along2[0]])


def on_back(pq, lift=0.0):
    return back_point(pq[0], pq[1], lift)


# Foam arm pad: a long rounded pad under the forearm, filling the gap to it
pad_c2 = pe + (pw - pe) * 0.42
pad_p, pad_n = on_back(pad_c2)
pad_gap = np.mean([gap_at(ELBOW + (WRIST - ELBOW) * t) for t in (0.0, 0.42, 0.84)]) - FA_R
pad_len, pad_w, pad_t = 0.26, 0.078, pad_gap + 0.008  # sinks 8 mm into the hit box: the real arm is slimmer
print("[%s] forearm gap: %.1f mm at the elbow, %.1f mm at the wrist; pad %.1f mm" % (
    NAME, (gap_at(ELBOW) - FA_R) * 1000, (gap_at(WRIST) - FA_R) * 1000, pad_t * 1000))
ax3 = shield_3d(pad_c2 + along2 * 0.01)[0] - shield_3d(pad_c2 - along2 * 0.01)[0]
ax3 /= np.linalg.norm(ax3)
side3 = np.cross(pad_n, ax3)
pieces.append(block("ArmPad", (pad_len, pad_w, pad_t), pad_mat, pad_p + pad_n * (pad_t / 2 - 0.002), ax3, side3,
                    pad_n, bevel=0.012, segments=2))

# Arm strap round the forearm, a little below the elbow, riveted to the shield either side of the pad
S = ELBOW + (WRIST - ELBOW) * 0.3
s_pq = to_pq(S)
anc = []
for sgn in (1, -1):
    pq = s_pq + across2 * sgn * (pad_w / 2 + 0.018)
    anc.append(on_back(pq, 0.001))
nb = -NRM - fa_axis * (-NRM @ fa_axis)
nb /= np.linalg.norm(nb)  # from the shield toward the zombie, square to the forearm
sb = np.cross(fa_axis, nb)
if sb @ (anc[0][0] - S) < 0:
    sb = -sb
rs = FA_R + 0.009
center = S + fa_axis * ((anc[0][0] - S) @ fa_axis)
loop = [anc[0][0] + anc[0][1] * 0.002]
for a in np.radians(np.linspace(-105.0, 105.0, 11)):
    loop.append(center + rs * (nb * math.cos(a) + sb * math.sin(a)))
loop.append(anc[1][0] + anc[1][1] * 0.002)
# Order from anchor 0 round the far side of the arm to anchor 1
if np.linalg.norm(loop[1] - loop[0]) > np.linalg.norm(loop[-2] - loop[0]):
    loop = [loop[0]] + loop[1:-1][::-1] + [loop[-1]]
nrms = []
for k, p in enumerate(loop):
    r = p - (center + fa_axis * ((p - center) @ fa_axis))
    if k in (0, len(loop) - 1):
        r = np.cross(fa_axis, (loop[1] - loop[0]) if k == 0 else (loop[-1] - loop[-2]))
        if r @ (p - center) < 0:
            r = -r
    nrms.append(r)
pieces.append(band("ArmStrap", loop, nrms, 0.038, 0.004, strap_mat))
# Its buckle on the outer side of the arm, and the riveted end tabs
k = 3
bt = loop[k + 1] - loop[k - 1]
bt /= np.linalg.norm(bt)
bn = nrms[k] / np.linalg.norm(nrms[k])
pieces.append(block("Buckle", (0.03, 0.046, 0.007), steel, loop[k] + bn * 0.004, bt, np.cross(bn, bt), bn,
                    bevel=0.0015))
for i, (p, n) in enumerate(anc):
    t = np.cross(n, ax3)
    t /= np.linalg.norm(t)
    pieces.append(block("StrapTab%d" % i, (0.04, 0.03, 0.005), strap_mat, p + n * 0.0025, ax3, t, n, bevel=0.001))

# Grip at the hand: a rubber-sleeved bar on two standoffs, square to the forearm
palm = (WRIST + np.array(sk.pos("LeftHandMiddle1"))) / 2
g_pq = to_pq(palm)
standoff = gap_at(palm) - 0.024  # the bar's far side just at the palm: the fingers close round it
ends = []
for sgn in (1, -1):
    p, n = on_back(g_pq + across2 * sgn * 0.058)
    ends.append((p, n))
    t = np.cross(n, ax3)
    pieces.append(block("Standoff%d" % (sgn > 0), (0.022, 0.024, standoff), steel, p + n * (standoff / 2 - 0.001), ax3,
                        t / np.linalg.norm(t), n, bevel=0.003))
ga = ends[0][0] + ends[0][1] * (standoff - 0.012)
gb = ends[1][0] + ends[1][1] * (standoff - 0.012)
pieces.append(rod("Grip", ga, gb, 0.015, grip_mat, sides=8))
# Pad and strap mounts: bolt heads on the front
bolts2 = [pad_c2 + along2 * 0.1, pad_c2 - along2 * 0.1] + [s_pq + across2 * s * (pad_w / 2 + 0.018) for s in (1, -1)] \
    + [g_pq + across2 * s * 0.058 for s in (1, -1)]
for i, pq in enumerate(bolts2):
    p, n = front_point(pq[0], pq[1], -0.0005)
    pieces.append(rod("Bolt%d" % i, p, p + n * 0.0032, 0.0062, steel, sides=6, radius_b=0.0052))

# ---------------------------------------------------------------- checks, export, previews


def report(objs):
    V = np.array([v.co[:] for o in objs for v in o.data.vertices])
    tris = sum(len(f.vertices) - 2 for o in objs for f in o.data.polygons)
    print("[%s] %d triangles, bounds %s to %s" % (NAME, tris, np.round(V.min(0), 3), np.round(V.max(0), 3)))
    for bones in (("Spine2",), ("Hips",), ("LeftArm",), ("LeftForeArm",), ("Head",), ("LeftUpLeg",)):
        d = sdf(V, bones)
        k = int(np.argmin(d))
        print("[%s] closest to %-12s %6.1f mm at %s" % (NAME, bones[0], d[k] * 1000, np.round(V[k], 3)))
    sh = np.array([v.co[:] for v in pieces[0].data.vertices])
    print("[%s] shield panel: closest to the torso %.1f mm, to the forearm %.1f mm" % (
        NAME, sdf(sh, ("Spine2", "Hips")).min() * 1000, sdf(sh, ("LeftForeArm",)).min() * 1000))
    print("[%s] center %s, normal %s, long axis %s" % (NAME, np.round(CENTER, 3), np.round(NRM, 3), np.round(UA, 3)))


for o in pieces:
    zk.on(o, "LeftForeArm", "Shield")
report(pieces)
for o in BODY:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS)
for o in BODY:
    o.hide_render = False

FAST = os.environ.get("ZX_FAST", "")  # while iterating: only these comma-separated close-ups, at fewer samples
focus = Vector((0.22, -0.05, 1.2))
if not FAST:
    zk.previews(SCRIPT, PREVIEWS, focus, distance=2.1)
for view, loc, tgt, lens in (("straight", (0.18, -2.6, 1.25), (0.18, 0.0, 1.2), 50),
                             ("top", (0.2, -0.1, 2.75), (0.2, -0.1, 1.25), 50),
                             ("close", (0.05, -0.85, 1.42), (0.22, -0.08, 1.25), 50),
                             ("back_close", (0.95, 0.75, 0.95), (0.42, 0.0, 1.18), 50)):
    if FAST and view not in FAST.split(","):
        continue
    tk.render(tk.camera("rs_" + view, Vector(loc), Vector(tgt), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=32 if FAST else 64)
print("[%s] done" % SCRIPT)
