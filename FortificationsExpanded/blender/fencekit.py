"""Shared kit for the two light-fence families (picket_fence.py, post_rail.py): hand-hewn boards and posts, a wood
material that can be painted or bare grey timber, iron parts, the bake of a part kit to one atlas per family, and the
assembly of pieces from copies of the baked parts (moved, rotated, mirrored; the parts keep their atlas UVs).

Conventions are those of palisade.py / chainlink.py: meters, Blender Z-up, a model's bottom at z = -0.5 (the ground),
the fence line along X at y = 0 with the front toward -Y, FBX meshes named DMG0.. plus an FX empty, gate leaves named
LeftLeaf / RightLeaf with their origin on the hinge axis. Parts are built standing on z = 0 ("g-frame": z measured from
the ground); `place` adds the -0.5.

Not a script to run on its own.
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

Z0 = -0.5
SHARP = 40.0
FT_SIDE, FT_END, FT_FRESH, FT_BOTTOM = 0, 1, 2, 3
T0 = time.time()


def log(*a):
    print("[fence %5.0fs]" % (time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- numpy matrices

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


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the kit registry

KIT, META = [], {}


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


def kit_part(name, obj, paint=0.0, wear=0.5, ground=0.0, seed=None, **meta):
    """Registers a built object (standing at its own origin) as a kit part and writes the attributes its material
    reads: lco (local position), luv (grain coordinates in meters: across, along), ks (end grain, fresh break),
    kp (paint left, seed, wear), kq (ground contact: dirt and moss near the foot)."""
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
    voff = rnd.uniform(0, 5)
    loop_v = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loop_v)
    luv = np.zeros((len(me.loops), 3), np.float32)
    ks = np.zeros((len(me.loops), 3), np.float32)
    for p in me.polygons:
        li = np.arange(p.loop_start, p.loop_start + p.loop_total)
        P = co[loop_v[li]]
        n = p.normal
        t = ft[p.index]
        if abs(n.z) > 0.75:
            uv = np.c_[P[:, 0], P[:, 1]]
        else:
            tv = unit((-n.y, n.x, 0.0))
            uv = np.c_[P @ tv, P[:, 2] + voff]
        luv[li, :2] = uv
        if t in (FT_END, FT_BOTTOM):
            ks[li] = (1.0, 0.0, 0.0)
        elif t == FT_FRESH:
            ks[li] = (0.0, 1.0, 0.0)
    set_attr(me, "luv", "CORNER", "FLOAT_VECTOR", luv)
    set_attr(me, "ks", "CORNER", "FLOAT_VECTOR", ks)
    sd = seed if seed is not None else rnd.uniform(0.0, 9.0)
    set_attr(me, "kp", "POINT", "FLOAT_VECTOR", np.tile([paint, sd, wear], (nv, 1)))
    set_attr(me, "kq", "POINT", "FLOAT_VECTOR", np.tile([ground, 0.0, 0.0], (nv, 1)))
    set_attr(me, "kpart", "FACE", "INT", np.full(len(me.polygons), len(KIT)))
    tk.smooth(obj, SHARP)
    META[name] = dict(index=len(KIT), **meta)
    KIT.append(obj)
    return obj


# ---------------------------------------------------------------- boards, posts and rails

def cut_fill(bm, ftl, co, n, ft):
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co,
                                 plane_no=n, clear_outer=True)
    edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
    if edges:
        for f in bmesh.ops.holes_fill(bm, edges=edges, sides=0)["faces"]:
            f[ftl] = ft


def section_pts(w, t, c, nw, nt):
    """Closed outline of a board's cross-section, counter-clockwise from +Z: chamfered corners, nw points along each
    broad face, nt (at least 2) along each narrow one."""
    c = min(c, w / 2 - 1e-4, t / 2 - 1e-4)
    x0, x1, y0, y1 = -w / 2, w / 2, -t / 2, t / 2
    P = []
    for i in range(nw):
        P.append((x0 + c + (w - 2 * c) * i / (nw - 1), y0))
    for i in range(nt):
        P.append((x1, y0 + c + (t - 2 * c) * i / (nt - 1)))
    for i in range(nw):
        P.append((x1 - c - (w - 2 * c) * i / (nw - 1), y1))
    for i in range(nt):
        P.append((x0, y1 - c - (t - 2 * c) * i / (nt - 1)))
    return P


def board(name, mat, w, t, L, seed, nw=4, nt=2, chamfer=0.004, bow=0.004, wander=0.002, twist=0.0, rough=0.0015,
          taper=0.0, taper_len=0.12, cuts=(), jag_top=0.0, jag_bot=0.0, irregular=0.0, step=0.14, lumps=0.0):
    """A hand-hewn board, post or rail standing on z = 0 with its axis along Z: slightly bowed, wandering and twisted,
    rough-surfaced, with chamfered edges. cuts = [(plane point, normal, face type)] saw the end off (anything on the
    normal's side of a plane is removed). jag_top/jag_bot (amplitude, m) leave a splintered break at that end instead
    of a flat sawn one. irregular: split-timber irregularity of the outline."""
    rnd = random.Random(seed)
    sec = section_pts(w, t, chamfer, nw, nt)
    n = len(sec)
    # fixed per-point scale so the outline of a split post stays irregular along its length
    irr = [1.0 + irregular * rnd.uniform(-1, 1) for _ in sec]
    zs = [0.0]
    while zs[-1] + step < L - 0.06:
        zs.append(zs[-1] + step * rnd.uniform(0.85, 1.1))
    zs += [L - 0.03, L] if jag_top else [L]
    if jag_bot:
        zs = [0.0, 0.03] + [z for z in zs if z > 0.06]
    a1, a2, a3 = rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)
    sd = seed * 1.713
    bm = bmesh.new()
    ftl = bm.faces.layers.int.new("ftype")

    def jag(x, y, amp, k):
        j = abs(noise.noise(Vector((x * 38.0 + sd, y * 38.0 + k, 1.3)))) * 2.0
        s = 0.25 + 0.75 * j
        return amp * s

    spikes = {k: rnd.sample(range(n), 2) for k in (0, 1)}
    rings = []
    for zi, z in enumerate(zs):
        s_e = 1.0
        if taper:
            s_e = 1.0 - taper * (smoothstep(taper_len, 0.0, z) + smoothstep(L - taper_len, L, z))
        cx = wander * math.sin(3.1 * z + a2) + 0.4 * bow * math.sin(1.7 * z + a1) * 0.0
        cy = bow * math.sin(math.pi * min(max(z / L, 0), 1)) + wander * 0.6 * math.cos(2.3 * z + a3)
        tw = twist * z / L
        ring = []
        for i, (x, y) in enumerate(sec):
            f = irr[i] * (1.0 + 0.35 * irregular * noise.noise(Vector((i * 0.7 + sd, z * 1.6, 0.0))))
            xs, ys = x * s_e * f, y * s_e * f
            rx = xs * math.cos(tw) - ys * math.sin(tw)
            ry = xs * math.sin(tw) + ys * math.cos(tw)
            r = math.hypot(rx, ry) + 1e-9
            jit = rough * noise.noise(Vector((x * 33.0 + sd, y * 33.0 - sd, z * 7.0)))
            if lumps:
                jit += lumps * noise.noise(Vector((x * 6.0 + sd, y * 6.0, z * 2.2)))
            px, py, pz = cx + rx + rx / r * jit, cy + ry + ry / r * jit, z
            if jag_top and zi >= len(zs) - 2:
                k = 1.0 if zi == len(zs) - 1 else 0.3
                pz = z - jag_top * 0.4 * k + k * jag(x, y, jag_top, 0.0) + (k * jag_top * 1.8 if i in spikes[0] else 0.0)
                pz += k * 0.35 * jag_top * (y / max(t / 2, 1e-3)) * rnd.uniform(-1, 1)
            if jag_bot and zi <= 1:
                k = 1.0 if zi == 0 else 0.3
                pz = z + jag_bot * 0.4 * k - k * jag(x, y, jag_bot, 5.0) - (k * jag_bot * 1.8 if i in spikes[1] else 0.0)
            ring.append(bm.verts.new((px, py, pz)))
        rings.append(ring)
    for k in range(len(zs) - 1):
        for i in range(n):
            i1 = (i + 1) % n
            f = bm.faces.new((rings[k][i], rings[k][i1], rings[k + 1][i1], rings[k + 1][i]))
            f[ftl] = FT_SIDE

    def cap(ring, up, ft, fan):
        if fan:
            c = bm.verts.new(tuple(np.mean([v.co[:] for v in ring], axis=0) + np.array((0, 0, 0.004 * (1 if up else -1)))))
            for i in range(n):
                tri = (c, ring[i], ring[(i + 1) % n]) if up else (c, ring[(i + 1) % n], ring[i])
                bm.faces.new(tri)[ftl] = ft
        else:
            f = bm.faces.new(ring if up else list(reversed(ring)))
            f[ftl] = ft

    cap(rings[-1], True, FT_FRESH if jag_top else FT_END, bool(jag_top))
    cap(rings[0], False, FT_FRESH if jag_bot else FT_BOTTOM, bool(jag_bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for co, nrm, ft in cuts:
        cut_fill(bm, ftl, co, nrm, ft)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm_to_obj(name, bm, mat)


def boolean_cut(obj, cutters):
    """Cuts the cutter boxes (objects) out of obj with an exact boolean, then deletes them."""
    for c in cutters:
        mod = obj.modifiers.new("Cut", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = c
        tk.apply_modifiers(obj)
    for c in cutters:
        bpy.data.objects.remove(c)
    return obj


def plain_box(name, mat, size, center):
    return tk.box(name, size, center, mat)


# ---------------------------------------------------------------- iron parts

def iron_nail(name, mat, kind="NAIL"):
    """Round-head nail pointing toward +Z (placed with its axis along the surface normal): a low six-sided domed head
    on the surface (the shank is inside the wood). kind 'bent': a protruding shank hooked over, no head."""
    if kind == "NAIL":
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6, radius1=0.0046, radius2=0.0033,
                              depth=0.0028)
        bmesh.ops.translate(bm, vec=(0, 0, 0.0008), verts=bm.verts)
        return bm_to_obj(name, bm, mat)
    pts = [(0, 0, -0.01), (0, 0, 0.02), (0.003, 0, 0.032), (0.016, 0, 0.038)]
    return tk.tube(name, pts, 0.0018, mat, resolution=2)


def iron_staple(name, mat):
    """A U wire staple lying across a surface (axis along X), driven in at both ends."""
    pts = [(-0.017, 0, -0.012), (-0.017, 0, 0.0035), (-0.015, 0, 0.0055), (0.015, 0, 0.0055), (0.017, 0, 0.0035),
           (0.017, 0, -0.012)]
    return tk.tube(name, pts, 0.0018, mat, resolution=2)


def iron_wire(name, mat, pts, r=0.0021):
    return tk.tube(name, pts, r, mat, resolution=2)


# ---------------------------------------------------------------- materials

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
        if not os.path.exists(path):
            raise FileNotFoundError(path + " is missing; run src/fetch-textures.ps1")
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


PLANK_C0, PLANK_PITCH = 0.115, 0.1115  # where the planks photo's boards sit across its tile (0-1)


def fence_wood(name, look, tile, value, sat, tint, paint_rgb=(0.21, 0.21, 0.19)):
    """Fence timber. look 'paint': boards under white-grey paint flaking to weathered wood, algae and grime near the
    ground, bright worn edges. look 'grey': bare silvered split timber with long drying checks, raised grain, lichen
    and a damp dark foot. The weathered_planks photo supplies grain, knots, roughness and relief; each part picks one
    of its boards (by its seed) so no part shows the dark seams between them."""
    paint = look == "paint"
    mat, g = tk.new_material(name)
    M = lambda a, b: g.math("MULTIPLY", a, b)  # noqa: E731
    A = lambda a, b: g.math("ADD", a, b)  # noqa: E731
    S = lambda a, b: g.math("SUBTRACT", a, b)  # noqa: E731
    lco = attr_vec(g, "lco")
    lx, ly, lz = g.separate(lco)
    u, v, _ = g.separate(attr_vec(g, "luv"))
    endg, fresh, _ = g.separate(attr_vec(g, "ks"))
    paint_amt, seed, wear = g.separate(attr_vec(g, "kp"))
    ground, _, _ = g.separate(attr_vec(g, "kq"))
    side = g.math("SUBTRACT", 1.0, A(endg, fresh), clamp=True)

    pc = A(PLANK_C0, M(g.math("FLOOR", M(g.math("FRACT", M(seed, 0.6180339)), 8.0)), PLANK_PITCH))
    vec = combine(g, A(pc, M(u, 1.0 / tile)), A(M(seed, 0.3719), M(v, 1.0 / tile)))
    p = photo_at(g, "weathered_planks", vec)
    col = contrast(g, tk.grade(g, p["color"], sat, value, tint), 0.16)
    rough = p["rough"]
    height = p["height"]

    def lines(su, sv, ofs, width):
        n = g.noise(1.0, detail=2.0, roughness=0.5, distortion=0.2, vector=combine(g, M(u, su), M(v, sv), A(seed, ofs)))
        return g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", S(n, 0.5)), 0.0, width, False))

    # long drying checks along the grain: thin, meandering, dark inside (bare timber has many, paint hides some)
    if paint:
        checks = g.math("MAXIMUM", M(lines(3.2, 0.5, 0.2, 0.024), 0.55), M(lines(7.0, 0.9, 2.6, 0.016), 0.45))
    else:
        checks = g.math("MAXIMUM", lines(15.0, 0.42, 0.2, 0.010), g.math("MAXIMUM", lines(27.0, 0.7, 2.6, 0.008),
                                                                        M(lines(9.0, 0.3, 5.1, 0.013), 0.9)))
    col = g.mix(checks, col, (0.012, 0.01, 0.008))
    height = S(height, M(checks, 1.4))

    # raised, silvered grain: fine lines along the length, lighter where the surface fibres have lifted
    grain = g.noise(1.0, detail=6.0, roughness=0.7, vector=combine(g, M(u, 150.0), M(v, 7.0), A(seed, 1.7)))
    if not paint:
        col = g.mix(M(g.ramp(grain, 0.38, 0.72), 0.4), col, tk._darker(g, col, 0.55))
        silver = g.ramp(g.noise(1.0, detail=5.0, roughness=0.6, vector=combine(g, M(u, 5.0), M(v, 1.5), A(seed, 3.3))),
                        0.45, 0.65)
        col = g.mix(M(silver, 0.45), col, (0.4, 0.38, 0.34))
        height = A(height, M(grain, 0.7))
    else:
        height = A(height, M(grain, 0.4))

    # fresh wood: splinters, breaks
    fib = g.noise(1.0, detail=4.0, roughness=0.6, vector=combine(g, M(u, 70.0), M(v, 2.5), A(seed, 4.1)))
    fr = tk.grade(g, p["color"], 0.6, value * 1.45, (1.0, 0.88, 0.7))
    fr = g.mix(0.5, fr, (0.27, 0.22, 0.16))
    fr = g.mix(M(g.ramp(fib, 0.45, 0.72), 0.65), fr, (0.08, 0.057, 0.036))
    col = g.mix(fresh, col, fr)
    rough = g.mixf(fresh, rough, 0.8)
    height = g.mixf(fresh, height, M(fib, 1.5))

    # sawn / weathered end grain: rings, radial checks
    rn = A(g.math("SQRT", A(M(S(lx, M(S(seed, 4.0), 0.02)), S(lx, M(S(seed, 4.0), 0.02))), M(ly, ly))),
           M(g.noise(6.0, detail=3.0, vector=lco), 0.006))
    rings = g.ramp(g.math("FRACT", M(rn, 70.0)), 0.6, 0.95)
    eg = g.mix(M(rings, 0.6), (0.2, 0.17, 0.13) if not paint else (0.22, 0.19, 0.15),
               (0.095, 0.08, 0.06))
    rc = g.ramp(g.noise(1.0, detail=3.0, roughness=0.5,
                        vector=combine(g, M(g.math("ARCTAN2", ly, lx), 2.5), M(rn, 4.0), seed)), 0.6, 0.64)
    eg = g.mix(rc, eg, (0.025, 0.02, 0.016))
    eg = g.mix(0.3, eg, (0.19, 0.18, 0.16))

    # lichen and damp on bare timber; algae creeping up painted boards
    if not paint:
        lich = M(M(g.ramp(g.noise(10.0, detail=6.0, roughness=0.7, vector=A(lco, combine(g, seed, 0.0, 0.0))),
                          0.64, 0.7), 0.55), side)
        col = g.mix(lich, col, (0.33, 0.35, 0.27))
        rough = g.mixf(lich, rough, 0.95)
        lowdamp = M(g.ramp(lz, 0.38, 0.0), M(ground, g.ramp(g.noise(7.0, detail=5.0, vector=combine(g, lx, ly, M(lz, 0.5))),
                                                         0.3, 0.6)))
        col = g.mix(M(lowdamp, 0.8), col, (0.045, 0.04, 0.032))
        rough = g.mixf(lowdamp, rough, 0.95)

    # paint
    if paint:
        patch = g.noise(1.0, detail=7.0, roughness=0.62, distortion=0.35,
                        vector=combine(g, M(u, 7.0), M(v, 2.4), A(seed, 2.0)))
        flake = g.noise(1.0, detail=5.0, roughness=0.6, distortion=0.3,
                        vector=combine(g, M(u, 36.0), M(v, 10.0), A(seed, 2.5)))
        gr = g.noise(1.0, detail=4.0, roughness=0.6, vector=combine(g, M(u, 70.0), M(v, 5.0), A(seed, 9.0)))
        edge = g.ramp(g.edges(0.0045), 0.08, 0.3)
        low = M(g.ramp(lz, 0.35, 0.0), M(ground, 0.22))
        f = A(A(M(patch, 0.5), M(flake, 0.32)), M(S(gr, 0.5), 0.18))
        f = A(f, M(S(paint_amt, 0.5), 0.8))
        f = S(S(f, A(M(edge, 0.28), low)), M(wear, 0.14))
        thr = 0.43
        present = g.ramp(f, thr, thr + 0.02)
        present = M(present, A(M(S(1.0, endg), 0.8), 0.2))
        shadow = M(S(g.ramp(f, thr - 0.03, thr), 0.0), S(1.0, present))   # bare wood hugging a flake edge
        lip = M(g.ramp(f, thr + 0.02, thr + 0.035), S(1.0, g.ramp(f, thr + 0.035, thr + 0.06)))  # paint's lit edge
        # paint colour: chalky off-white, mottled, with dark mildew streaks running down and mildew patches low
        pcol = g.mix(g.ramp(patch, 0.3, 0.7), tuple(c * 0.72 for c in paint_rgb), tuple(c * 1.08 for c in paint_rgb))
        runs = g.ramp(g.noise(1.0, detail=4.0, roughness=0.6, vector=combine(g, M(u, 42.0), M(v, 0.9), A(seed, 6.0))),
                      0.52, 0.74)
        pcol = g.mix(M(runs, 0.55), pcol, (0.075, 0.07, 0.06))
        pcol = g.mix(M(lines(20.0, 1.0, 8.0, 0.007), 0.55), pcol, (0.07, 0.065, 0.058))   # hairline cracks in the paint
        pcol = g.mix(M(g.ramp(g.noise(1.0, detail=6.0, roughness=0.65, vector=combine(g, M(u, 16.0), M(v, 6.0), A(seed, 4.4))),
                              0.4, 0.78), 0.4), pcol, (0.09, 0.083, 0.07))   # general grime
        mild = M(g.ramp(g.noise(1.0, detail=6.0, roughness=0.65, vector=combine(g, M(u, 14.0), M(v, 5.0), A(seed, 7.0))),
                        0.52, 0.66), A(0.12, M(g.ramp(lz, 0.7, 0.0), M(ground, 0.8))))
        pcol = g.mix(M(mild, 0.8), pcol, (0.05, 0.062, 0.04))
        alg = M(g.ramp(lz, 0.4, 0.02), M(ground, g.ramp(g.noise(9.0, detail=6.0,
                                                             vector=combine(g, M(u, 8.0), M(v, 3.0), seed)), 0.35, 0.62)))
        pcol = g.mix(M(alg, 0.7), pcol, (0.12, 0.17, 0.08))
        # the wood under it is old grey-brown timber, darker where the paint just came off
        col = tk._darker(g, col, 0.8)
        col = g.mix(M(shadow, 0.8), col, tk._darker(g, col, 0.45))
        col = g.mix(present, col, pcol)
        col = g.mix(M(lip, 0.45), col, (0.33, 0.33, 0.31))
        rough = g.mixf(present, rough, 0.66)
        height = A(height, A(M(present, 1.3), M(lip, 0.3)))
    col = g.mix(endg, col, eg)
    rough = g.mixf(endg, rough, 0.88)
    height = g.mixf(endg, height, S(M(rings, 0.4), rc))

    # grime: crevices, the foot, dust, specks
    cav = g.ramp(g.cavity(0.07), 0.35, 1.0)
    dirt = g.math("ADD", M(S(1.0, cav), 0.7), M(g.ramp(lz, 0.3, 0.0), M(ground, 0.35)), clamp=True)
    dirt = M(dirt, g.ramp(g.noise(5.0, detail=5.0), 0.2, 0.7))
    col = g.mix(dirt, col, (0.04, 0.034, 0.027))
    rough = g.mixf(dirt, rough, 0.88)
    col = tk._multiply_color(g, col, g.mix(0.5, (1.0, 1.0, 1.0), p["ao"]))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.4)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.6, 0.01))


def iron_materials():
    iron = tk.photo_material("Iron", "metal_plate_02", scale=2.4, value=0.42, sat=0.7, exposed="rust_coarse_01",
                             chip=1.0, patches=1.0, grime=0.7, streaks=0.6, metal_floor=0.3, rough_scale=1.0,
                             grit=0.6, scratches=0.15, edges=0.15, contrast=0.12)
    wire = tk.photo_material("Wire", "metal_plate_02", scale=4.0, value=0.95, exposed="rust_coarse_01",
                             patches=0.7, chip=1.0, metal_floor=0.5, grime=0.5, grit=0.4)
    return iron, wire


# ---------------------------------------------------------------- bake, then cut the kit back into templates

class Tpl:
    def __init__(self, name, V, F, UV, meta):
        self.name, self.V, self.F, self.UV, self.meta = name, V, F, UV, meta


def _scale_bake_samples():
    """FENCE_BAKE_SCALE (e.g. 0.25) scales every bake pass's sample count, for quick looks while iterating."""
    scale = float(os.environ.get("FENCE_BAKE_SCALE", 1.0))
    if scale != 1.0:
        orig = tk._bake

        def scaled(obj, kind, img, samples, **kw):
            return orig(obj, kind, img, max(2, int(samples * scale)), **kw)
        tk._bake = scaled


def bake_kit(assets, mat_name):
    _scale_bake_samples()
    kit = tk.join(list(KIT), mat_name + "Kit")
    kit = tk.triangulate(kit)
    tk.smart_uvs(kit)
    log("kit: %d parts, %d triangles, baking" % (len(KIT), len(kit.data.polygons)))
    bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
    size = int(os.environ.get("FENCE_TEX", tk.TEX_SIZE))  # a smaller atlas (1024) for quick looks while iterating
    if os.environ.get("FENCE_DEVICE") == "CPU":
        bpy.context.scene.cycles.device = "CPU"
    try:
        paths = tk.bake_atlas(kit, assets, mat_name, size=size)
    except RuntimeError as e:
        log("GPU bake failed (%s); retrying on the CPU" % e)
        bpy.context.scene.cycles.device = "CPU"
        paths = tk.bake_atlas(kit, assets, mat_name, size=size)
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


# ---------------------------------------------------------------- assembling pieces

class Item:
    def __init__(self, V, F, UV, tag=""):
        self.V = np.asarray(V, np.float64).reshape(-1, 3)
        self.F = np.asarray(F, np.int64).reshape(-1, 3)
        self.UV = np.asarray(UV, np.float64).reshape(-1, 3, 2)
        self.tag = tag


def merge(items, tag=None):
    items = [it for it in items if it is not None and len(it.F)]
    V, F, UV, off = [], [], [], 0
    for it in items:
        V.append(it.V)
        F.append(it.F + off)
        UV.append(it.UV)
        off += len(it.V)
    return Item(np.concatenate(V), np.concatenate(F), np.concatenate(UV), tag or items[0].tag)


class Assembler:
    def __init__(self, templates):
        self.T = templates

    def place(self, name, M, tag=""):
        """A copy of kit part `name`, moved by M (g-frame: z measured up from the ground; mirrors are allowed)."""
        t = self.T[name]
        M = m_t(0, 0, Z0) @ M
        F = t.F.copy()
        UV = t.UV.copy()
        if np.linalg.det(M[:3, :3]) < 0:
            F = F[:, [0, 2, 1]]
            UV = UV[:, [0, 2, 1]]
        return Item(t.V @ M[:3, :3].T + M[:3, 3], F, UV, tag or name)


def finish_mesh(name, items, material, limits=None):
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
    me.materials.append(material)
    obj = tk.link(bpy.data.objects.new(name, me))
    return obj


def stats(objs):
    lo, hi, tris = np.full(3, 1e9), np.full(3, -1e9), 0
    for o in objs:
        co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
        lo, hi = np.minimum(lo, co.min(0)), np.maximum(hi, co.max(0))
        tris += len(o.data.polygons)
    return lo, hi, tris


def export_piece(assets, fname, meshes, fx):
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
    tk.export_fbx(objs, os.path.join(assets, fname))
    if empty is not None:
        bpy.data.objects.remove(empty)
    for m, n, dn in saved:
        m.name = n
        m.data.name = dn


# ---------------------------------------------------------------- checks and previews

def see_through(placed, axis, s0, s1, z0, z1, ds=0.01, dz=0.02):
    """Rays straight through the fence along `axis` (Y: from the front) on a grid between s0..s1 and z0..z1 (g-frame
    heights): returns the fraction that get through. placed: (object, location, z rotation)."""
    V, F, off = [], [], 0
    for obj, loc, rz in placed:
        M = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ obj.matrix_world
        V += [(M @ v.co)[:] for v in obj.data.vertices]
        F += [tuple(i + off for i in p.vertices) for p in obj.data.polygons]
        off += len(obj.data.vertices)
    bvh = BVHTree.FromPolygons(V, F)
    total = clear = 0
    for s in np.arange(s0 + ds / 2, s1, ds):
        for z in np.arange(z0 + dz / 2, z1, dz):
            o = Vector((s, -1.5, Z0 + z)) if axis == "Y" else Vector((-1.5, s, Z0 + z))
            d = Vector((0, 1, 0)) if axis == "Y" else Vector((1, 0, 0))
            total += 1
            if bvh.ray_cast(o, d, 3.0)[0] is None:
                clear += 1
    return clear / max(total, 1)


def swing_check(leaf, sx, post_box):
    """How far the leaf reaches into its post box (x0, x1, y0, y1) at 0, 5, 10, 20, 45 and 90 degrees open:
    positive = overlap in m (rough: depth of the deepest leaf vertex into the box), negative = clear."""
    bpy.context.view_layer.update()
    V = np.array([(leaf.matrix_world @ v.co)[:] for v in leaf.data.vertices])
    piv = np.array(leaf.matrix_world.translation)
    out = []
    x0, x1, y0, y1 = post_box
    for deg in (0, 5, 10, 20, 45, 90):
        a = math.radians(deg) * sx
        d = V[:, :2] - piv[:2]
        R = np.c_[d[:, 0] * math.cos(a) - d[:, 1] * math.sin(a), d[:, 0] * math.sin(a) + d[:, 1] * math.cos(a)] + piv[:2]
        inside = np.minimum.reduce([R[:, 0] - x0, x1 - R[:, 0], R[:, 1] - y0, y1 - R[:, 1]])
        out.append("%d deg %+.3f" % (deg, float(inside.max())))
    return ", ".join(out)


def stage():
    tk.preview_stage()
    floor = bpy.data.objects["Floor"]
    floor.data.transform(Matrix.Translation((0.5, 0.5, 0.0)) @ Matrix.Diagonal((4.0, 4.0, 1.0, 1.0)))
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (0.0, 0.0, 0.0)


def figure_at(x, y):
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)


def use_device():
    """FENCE_DEVICE=CPU renders and bakes on the CPU (the GPU runs out of memory when many Blender jobs share it)."""
    if os.environ.get("FENCE_DEVICE") == "CPU":
        bpy.context.scene.cycles.device = "CPU"


def lineup(all_objs, entries, cam, path, res=(1800, 1100), samples=None, show=()):
    """entries: (object, (x, y), z rotation in degrees). Renders copies of them; everything in all_objs is hidden
    except `show`."""
    for o in all_objs:
        o.hide_render = o not in show
    temps = []
    for obj, (x, y), rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = (x, y, 0.0)
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    samples = samples or int(os.environ.get("FENCE_SAMPLES", 96))
    rs = float(os.environ.get("FENCE_RESCALE", 1.0))
    tk.render(cam, path, res=(int(res[0] * rs), int(res[1] * rs)), samples=samples)
    for t in temps:
        bpy.data.objects.remove(t)


def image_array(path):
    img = bpy.data.images.load(path)
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return a


def albedo_stats(paths, label):
    a = image_array(paths["albedo"])[..., :3]
    m = a.max(axis=2) > 0.01
    px = a[m]
    log("albedo (sRGB) mean %s p10 %s p90 %s | %s" % (px.mean(0).round(3), np.percentile(px, 10, axis=0).round(3),
                                                       np.percentile(px, 90, axis=0).round(3), label))
    r = image_array(paths["rmom"])
    log("roughness mean %.3f (vanilla 0.81), metallic mean %.3f, AO mean %.3f" % (r[..., 0][m].mean(),
                                                                                r[..., 1][m].mean(),
                                                                                r[..., 2][m].mean()))


def reimport_report(assets, prefix):
    """Imports the exported FBX files again and logs what the importer sees (names, triangles, bounds, parents)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lines = []
    for fname in sorted(os.listdir(assets)):
        if not (fname.startswith(prefix) and fname.endswith(".fbx")):
            continue
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.import_scene.fbx(filepath=os.path.join(assets, fname))
        parts = []
        for o in sorted(bpy.data.objects, key=lambda o: o.name):
            if o.type == "MESH":
                co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
                tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
                parts.append("%s tris %d mat %s z %.3f..%.3f x %.3f..%.3f y %.3f..%.3f origin %s parent %s" % (
                    o.name, tris, [m.name for m in o.data.materials], co[:, 2].min(), co[:, 2].max(), co[:, 0].min(),
                    co[:, 0].max(), co[:, 1].min(), co[:, 1].max(),
                    tuple(round(c, 3) for c in o.matrix_world.translation), o.parent.name if o.parent else None))
            else:
                parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation),
                                                        o.parent.name if o.parent else None))
        lines.append("reimport %s | %s" % (fname, " || ".join(parts)))
        log(lines[-1])
    return lines


# ---------------------------------------------------------------- shared helpers for the piece scripts

def basis(zaxis, yaxis=(0, 1, 0)):
    """A rotation taking +Z to `zaxis`, with +Y as near `yaxis` as it can be (a board lying along a diagonal)."""
    z = unit(zaxis)
    y = np.asarray(yaxis, float)
    y = unit(y - z * y.dot(z))
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = x, y, z
    return M


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
    return {n: Tpl(n, z[n + "|V"], z[n + "|F"], z[n + "|UV"], m) for n, m in meta.items()}
