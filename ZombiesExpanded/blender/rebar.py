"""Rebar (remnant): a length of ribbed reinforcing bar run clean through the chest and out the back, as if the zombie
fell onto it from a collapsed slab. In front it bends down and out to a broken chunk of concrete still cast round its
end (a cut stub of the crossing bar in it too); out the back it bends up and away to a sheared, flattened end. The bar
is rusted through, crusted grey with cement near the chunk, and soaked in dried blood where it goes in and comes out,
with scraps of torn flesh at both wounds.

The bar passes straight through the body, hidden inside it; out in the open it keeps clear of the arms. One part on
Spine2: "Spine2#Rebar".

    blender -b --factory-startup --python rebar.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "Rebar", "rebar", 8231

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
SK = zk.joe()
RND = random.Random(SEED)
UP = Vector((0.0, 0.0, 1.0))


def jit(a):
    return RND.uniform(-a, a)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def orth(v, axis):
    """v with its component along `axis` removed, normalized."""
    return (v - axis * v.dot(axis)).normalized()


# ---------------------------------------------------------------- the stand-in's hit boxes

def _capsules():
    out = []
    for c in SK.colliders:
        if c["type"] != "capsule":
            continue
        ax = Vector((0.0, 0.0, 0.0))
        ax[c["axis"]] = 1.0
        half = max(0.0, c["height"] / 2 - c["radius"])
        ctr = Vector(c["center"])
        out.append((c["bone"], SK.point(c["bone"], ctr - ax * half), SK.point(c["bone"], ctr + ax * half), c["radius"]))
    return out


CAPS = _capsules()


def seg_closest(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return a + ab * t, t


def sdf(p, bones=None):
    """Distance from p to the stand-in's surface, negative inside (the hit-box capsules)."""
    return min((p - seg_closest(p, a, b)[0]).length - r for bone, a, b, r in CAPS if bones is None or bone in bones)


def taper_sdf(a, b, ra, rb):
    """Distance to a round limb from a (radius ra) to b (radius rb), negative inside."""
    def f(p):
        q, t = seg_closest(p, a, b)
        return (p - q).length - (ra + (rb - ra) * t)
    return f


def entry(origin, d, f=sdf, maxd=0.6, step=0.0005):
    """Where a ray from `origin` along d first goes inside f (f < 0)."""
    d = d.normalized()
    t = 0.0
    while t < maxd:
        if f(origin + d * t) < 0.0:
            return origin + d * t
        t += step
    return None


# ---------------------------------------------------------------- mesh helpers

def frames(P, closed=False):
    """Tangents and twist-free normals and binormals along a polyline (parallel transport)."""
    n = len(P)
    T = []
    for i in range(n):
        d = (P[(i + 1) % n] - P[(i - 1) % n]) if closed else (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        T.append(d.normalized())
    ref = UP if abs(T[0].z) < 0.9 else Vector((1.0, 0.0, 0.0))
    N = []
    for t in T:
        nv = (ref - t * ref.dot(t)).normalized()
        N.append(nv)
        ref = nv
    return T, N, [t.cross(nv) for t, nv in zip(T, N)]


def arclen(P):
    s = [0.0]
    for i in range(1, len(P)):
        s.append(s[-1] + (P[i] - P[i - 1]).length)
    return s


def set_attr(obj, name, vals):
    me = obj.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def depth_attr(obj, f, seed=0.0):
    """zd = (distance to the skin (f), seed, height) per vertex, for the materials' blood and wear."""
    return set_attr(obj, "zd", [(f(v.co), seed, v.co.z) for v in obj.data.vertices])


def tube(name, pts, radius, mat, sides=6, closed=False, caps=True, twist=0.0, phase=0.0, normals=None, smooth=None,
         s0=0.0):
    """A tube along pts. radius: a number, a list (one per point) or fn(i) -> r or (rx, ry). twist turns the
    cross-section (radians per meter); normals (one per point) fixes the cross-section's x direction. Records zl =
    (meters along, x, y across) for the materials."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T, N, B = frames(P, closed)
    if normals is not None:
        N = [orth(Vector(v), t) for v, t in zip(normals, T)]
        B = [t.cross(nv) for t, nv in zip(T, N)]
    S = arclen(P)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        r = radius(i) if callable(radius) else (radius[i] if isinstance(radius, (list, tuple)) else radius)
        rx, ry = r if isinstance(r, tuple) else (r, r)
        ring = []
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides + twist * S[i]
            x, y = rx * math.cos(a), ry * math.sin(a)
            ring.append(bm.verts.new(P[i] + N[i] * x + B[i] * y))
            vals.append((s0 + S[i], x, y))
        rings.append(ring)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, "zl", vals)
    # Round all the way round (a hexagon's faces meet at exactly 60 degrees), sharp at the caps where it can be
    return tk.smooth(obj, smooth if smooth is not None else max(60.0, 360.0 / sides + 15.0))


def prism(name, poly, thick, origin, u, v, face, edge, smooth=20):
    """A flat plate: the 2D outline `poly` [(a, b)] laid out on origin + u * a + v * b, `thick` through. The faces
    get material `face`, the cut edges `edge`. zl = (a, b, side)."""
    n = u.cross(v).normalized()
    bm = bmesh.new()
    vals = []
    top, bot = [], []
    for a, b in poly:
        p = origin + u * a + v * b
        top.append(bm.verts.new(p + n * (thick / 2)))
        vals.append((a, b, 1.0))
    for a, b in poly:
        p = origin + u * a + v * b
        bot.append(bm.verts.new(p - n * (thick / 2)))
        vals.append((a, b, -1.0))
    m = len(poly)
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    sides = []
    for i in range(m):
        k = (i + 1) % m
        sides.append(bm.faces.new((top[k], top[i], bot[i], bot[k])))
    for f in sides:
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, face)
    obj.data.materials.append(edge)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, smooth)


def hull(name, pts, mat):
    """The convex hull of points: an angular broken chunk."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    return tk.smooth(obj, 25)


def place(obj, m):
    """Bakes matrix m into the mesh (built at the origin) so it sits in world coordinates."""
    obj.data.transform(m)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def frame_matrix(origin, x, y, z):
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return m


def catmull(ctrl, per=6):
    """A smooth path through the control points."""
    P = [Vector(c) for c in ctrl]
    E = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(E) - 2):
        p0, p1, p2, p3 = E[i - 1], E[i], E[i + 1], E[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-1])
    return out


def resample(P, step):
    """Points every `step` meters along a polyline (ends kept)."""
    S = arclen(P)
    n = max(2, int(round(S[-1] / step)) + 1)
    out, k = [], 0
    for i in range(n):
        s = S[-1] * i / (n - 1)
        while k < len(S) - 2 and S[k + 1] < s:
            k += 1
        t = (s - S[k]) / max(S[k + 1] - S[k], 1e-9)
        out.append(P[k].lerp(P[k + 1], min(1.0, max(0.0, t))))
    return out


# ---------------------------------------------------------------- material helpers

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


def attr_vec(g, name):
    n = g.node("ShaderNodeAttribute", attribute_name=name)
    n.attribute_type = "GEOMETRY"
    return tk._sock(n.outputs, "Vector")


def attr(g, name):
    return g.separate(attr_vec(g, name))


def combine(g, x, y, z):
    n = g.node("ShaderNodeCombineXYZ")
    for k, s in enumerate((x, y, z)):
        g._in(n, n.inputs[k].identifier, s)
    return n.outputs[0]


def mul(g, a, b):
    return g.math("MULTIPLY", a, b)


def add(g, a, b):
    return g.math("ADD", a, b)


def seeded(g, seed):
    """World position shifted by a seed, for noise that differs per material."""
    return mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))


def gore_mask(g, P, reach=0.035, amount=1.0, runs=0.6, dots=0.6, scale=16.0):
    """How bloody a point is from its distance to the skin (zd.x): soaked at and under the skin, ragged out to
    about `reach`, with runs and spatter beyond it."""
    d = attr(g, "zd")[0]
    edge = add(g, d, mul(g, g.math("SUBTRACT", g.noise(scale, detail=6.0, roughness=0.65, vector=P), 0.5), reach * 0.9))
    m = g.ramp(edge, reach, reach * 0.4)
    streak = g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(70.0, 70.0, 5.0))), 0.6, 0.67)
    m = g.math("MAXIMUM", m, mul(g, mul(g, streak, g.ramp(d, reach * 2.6, reach * 0.6)), runs))
    sp = mul(g, g.ramp(voronoi(g, mapping(g, P, loc=(0.3, 1.1, 0.7)), 110.0), 0.13, 0.05),
             g.ramp(g.noise(7.0, vector=P), 0.45, 0.6))
    m = g.math("MAXIMUM", m, mul(g, mul(g, sp, g.ramp(d, reach * 3.5, reach)), dots))
    return mul(g, m, amount)


def dried_blood(g, col, rough, height, mask, P, scale=11.0):
    """Dried blood: deep red going near-black where it pooled thick, tacky and glossy there, dull and flaking where
    thin."""
    thick = g.ramp(g.noise(scale, detail=5.0, vector=P), 0.35, 0.72)
    mask = g.math("MINIMUM", mask, 1.0)
    bc = g.mix(thick, (0.13, 0.012, 0.013), (0.04, 0.004, 0.004))
    col = g.mix(mask, col, bc)
    rough = g.mixf(mask, rough, g.mixf(thick, 0.42, 0.16))
    height = add(g, height, mul(g, mask, add(g, 0.1, mul(g, thick, 0.35))))
    return col, rough, height


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood stuck to whatever went through it: wet dark red, black clots, pale shreds of fat
    and tissue."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    n1 = g.noise(30.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.02, 0.002, 0.002), (0.085, 0.008, 0.007))
    fat = mul(g, g.ramp(g.noise(60.0, detail=4.0, distortion=1.2, vector=P), 0.68, 0.73), 0.6)
    col = g.mix(fat, col, (0.13, 0.075, 0.05))
    clot = g.ramp(voronoi(g, P, 140.0), 0.25, 0.1)
    col = g.mix(mul(g, clot, 0.6), col, (0.02, 0.002, 0.002))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.2, 0.42)
    height = add(g, mul(g, n1, 0.6), mul(g, fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


def blob(name, center, radii, axes, mat, seed=0.0, lump=0.25, seg=(8, 5)):
    """A small lumpy blob (a clot, a scrap of flesh): a squashed sphere along `axes` (three unit vectors), its
    surface pushed about by noise."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=1.0)
    for v in bm.verts:
        k = 1.0 + lump * noise.noise(v.co * 2.2 + Vector((seed, seed * 0.7, seed * 1.3)))
        v.co = Vector(center) + (axes[0] * (v.co.x * radii[0]) + axes[1] * (v.co.y * radii[1])
                                 + axes[2] * (v.co.z * radii[2])) * k
    return tk.smooth(tk.mesh_object(name, bm, mat), 70)


def point_at(P, S, s):
    """The point at arc length s along a polyline (S its arclen), and the heading there."""
    s = max(0.0, min(S[-1], s))
    i = max(1, next((j for j in range(len(S)) if S[j] >= s), len(S) - 1))
    t = (s - S[i - 1]) / max(S[i] - S[i - 1], 1e-9)
    return P[i - 1].lerp(P[i], t), (P[i] - P[i - 1]).normalized()


def gore_sleeve(name, P, s_mid, length, r, fat, mat, seed=0.0, droop=0.5):
    """Torn flesh and clot clinging round a rod (path P, radius r) about s_mid along it: lumpy, thickest in the middle,
    sagging down, its ends sunk into the rod."""
    S = arclen(P)
    pts, rad = [], []
    for m in range(6):
        t = m / 5
        c, d = point_at(P, S, s_mid + length * (t - 0.5))
        bulge = math.sin(math.pi * t) ** 0.8
        sag = orth(-UP, d) * (r * droop * bulge) if abs(d.z) < 0.95 else Vector()
        pts.append(c + sag)
        rad.append(r * (0.75 + (fat - 0.75) * bulge))
    obj = tube(name, pts, rad, mat, sides=8, caps=True, phase=seed)
    for v in obj.data.vertices:
        c, _ = seg_closest(v.co, pts[0], pts[-1])
        v.co = c + (v.co - c) * (1.0 + 0.45 * noise.noise(v.co * 110.0 + Vector((seed, 0.3 * seed, 0.7))))
    return obj


def thin_path(P, f, near=0.02, fine=0.007, coarse=0.022, keep=()):
    """Points of a dense path kept every `coarse` meters, every `fine` within `near` of the skin (|f| small); the
    ends and indices in `keep` always stay."""
    out = [P[0]]
    since = 0.0
    for i in range(1, len(P) - 1):
        since += (P[i] - P[i - 1]).length
        step = fine if abs(f(P[i])) < near else coarse
        if since >= step or i in keep:
            out.append(P[i])
            since = 0.0
    out.append(P[-1])
    return out


def rusty_iron(name, seed=0.0, rust=0.6, scale=2.5, base=(0.05, 0.046, 0.042), rust_value=0.5, polish=0.0,
               gore=0.0, reach=0.035, grit=0.5, scale_dark=0.4, grime=0.6, bump=0.35, extra=None, blood_scale=11.0, rust_sat=0.78):
    """Old iron and steel: dark mill scale, coarse rust in blooms and crevices (the photo, toned down), pitted,
    rubbed bright in places (polish), grimy and dusty, bloodied near the skin (gore, from zd)."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    p = tk.photo(g, "rust_coarse_01", scale, (seed * 0.31, 0.5 + seed * 0.17, seed * 0.23))
    tone = g.noise(6.0, detail=4.0, vector=P)
    iron = g.mix(tone, base, tk._darker(g, base, 0.6))
    scale_m = mul(g, g.ramp(g.noise(9.0, detail=6.0, roughness=0.6, vector=P), 0.45, 0.6), scale_dark)
    iron = g.mix(scale_m, iron, (0.022, 0.021, 0.02))
    rust_col = tk.grade(g, p["color"], rust_sat, rust_value)
    rust_col = g.mix(g.ramp(tk._luma(g, p["color"]), 0.12, 0.03), rust_col, (0.035, 0.016, 0.008))
    blooms = g.ramp(g.noise(4.5, detail=8.0, roughness=0.65, distortion=0.5, vector=P), 0.66 - 0.32 * rust,
                    0.72 - 0.32 * rust)
    pits = g.ramp(tk._luma(g, p["color"]), 0.16 + 0.1 * rust, 0.08)
    cav = mul(g, g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.03), 0.4, 1.0), clamp=True), 1.2)
    rm = g.math("MAXIMUM", blooms, mul(g, pits, rust))
    rm = g.math("MAXIMUM", rm, mul(g, cav, rust), clamp=True)
    col = g.mix(rm, iron, rust_col)
    rough = g.mixf(rm, add(g, 0.5, mul(g, tone, 0.15)), 0.9)
    metal = g.mixf(rm, 0.65, 0.05)
    height = add(g, mul(g, g.noise(80.0, detail=5.0, vector=P), 0.15), mul(g, rm, p["height"]))
    if polish:
        st = g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(18.0, 18.0, 18.0)))
        pm = mul(g, g.ramp(st, 0.55, 0.68), g.ramp(g.edges(0.004), 0.0, 0.4))
        pm = mul(g, g.math("MAXIMUM", pm, mul(g, g.ramp(st, 0.6, 0.7), 0.6)), polish)
        col = g.mix(pm, col, (0.2, 0.19, 0.18))
        rough = g.mixf(pm, rough, 0.38)
        metal = g.mixf(pm, metal, 0.9)
    dirt = tk._grime(g, grime)
    col = g.mix(mul(g, dirt, 0.8), col, (0.03, 0.024, 0.018))
    rough = g.mixf(dirt, rough, 0.88)
    metal = g.mixf(dirt, metal, 0.0)
    if extra:
        col, rough, metal, height = extra(g, P, col, rough, metal, height)
    col, rough, metal = tk._grit(g, col, rough, metal, grit, scratches=0.2, edges=0.15)
    if gore:  # after the dust, so blood isn't dusted over
        bm_ = gore_mask(g, P, reach, gore, scale=blood_scale * 1.5)
        col, rough, height = dried_blood(g, col, rough, height, bm_, P, scale=blood_scale)
        metal = g.mixf(bm_, metal, 0.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, bump, 0.002))


# ---------------------------------------------------------------- export, checks and previews

def report(parts, f=sdf):
    """Triangles, bounds and how deep each part goes into the skin (f < 0 inside)."""
    groups = {}
    for p in parts:
        groups.setdefault(p["zbone"], []).append(p)
    total = 0
    lo_all, hi_all = Vector((9, 9, 9)), Vector((-9, -9, -9))
    for label, objs in groups.items():
        lo, hi = Vector((9, 9, 9)), Vector((-9, -9, -9))
        tris, deep, inside, nv = 0, 9.0, 0, 0
        for o in objs:
            me = o.data
            for v in me.vertices:
                w = o.matrix_world @ v.co
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
                d = f(w)
                deep = min(deep, d)
                inside += d < 0
                nv += 1
            tris += sum(len(pp.vertices) - 2 for pp in me.polygons)
        total += tris
        lo_all = Vector(map(min, lo_all, lo))
        hi_all = Vector(map(max, hi_all, hi))
        print("[%s] %-22s %5d tris  bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)  deepest %.1f cm, %d/%d verts inside"
              % ((SCRIPT, label, tris) + tuple(lo) + tuple(hi) + (deep * 100, inside, nv)))
    print("[%s] total %d tris, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)"
          % ((SCRIPT, total) + tuple(lo_all) + tuple(hi_all)))


def export(pieces, size=512):
    hidden = [o for o in bpy.context.scene.objects if o.get("zbody") or o.name.startswith("Pre")]
    for o in hidden:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=size)
    for o in hidden:
        o.hide_render = False
    return parts


def close_up(view, target, direction, distance=0.45, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


def ellipsoid(name, center, radii, mat, seg=(32, 20)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=1.0)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def limb(name, a, b, ra, rb, mat, seg=24):
    """A tapered round limb with rounded ends (preview stand-in)."""
    bm = bmesh.new()
    length = (b - a).length
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=ra, radius2=rb, depth=length)
    for r, z in ((ra, -length / 2), (rb, length / 2)):
        s = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=10, radius=r)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=s["verts"])
    obj = tk.mesh_object(name, bm, mat)
    obj.matrix_world = Matrix.Translation((a + b) / 2) @ (b - a).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    return tk.smooth(obj, 60)


def standin(head=False, forearms=False, chest=False):
    """Swaps hit-box capsules of the preview stand-in for closer shapes (previews only, never exported): a skull,
    face, jaw, eyes and neck for the head; slimmer forearms (4 cm at the elbow, 3.1 at the wrist); a chest whose dome
    stops at the neck."""
    mat = bpy.data.materials["BodySkin"]
    drop = set()
    if head:
        drop |= {"Head", "Spine2"}
    if forearms:
        drop |= {"LeftForeArm", "RightForeArm"}
    if chest:
        drop |= {"Spine2"}
    for i, c in enumerate(SK.colliders):
        if c["bone"] in drop and ("Body_%d" % i) in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
        if c["bone"] == "Spine2" and "Spine2" in drop:
            ax = Vector((0.0, 0.0, 0.0))
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            zk._capsule("PreChest", SK.point("Spine2", ctr - ax * half),
                        SK.point("Spine2", ctr + ax * half) - Vector((0.0, 0.0, 0.05)), c["radius"], mat)
    if head:
        ellipsoid("PreSkull", (0.0, 0.03, 1.738), (0.079, 0.1, 0.104), mat)
        ellipsoid("PreFace", (0.0, -0.022, 1.7), (0.064, 0.06, 0.07), mat)
        ellipsoid("PreJaw", (0.0, -0.022, 1.652), (0.062, 0.066, 0.055), mat)
        ellipsoid("PreChin", (0.0, -0.062, 1.614), (0.024, 0.02, 0.02), mat)
        ellipsoid("PreNose", (0.0, -0.088, 1.7), (0.012, 0.018, 0.026), mat)
        tk.cylinder("PreNeck", 0.055, 1.5, 1.69, mat, segments=32, center=(0.0, 0.032))
        eye, g = tk.new_material("PreEye")
        tk.finish(eye, g, (0.02, 0.02, 0.02), 0.0, 0.2)
        for s in (1, -1):
            ellipsoid("PreEye%d" % s, (0.032 * s, -0.075, 1.719), (0.013, 0.008, 0.009), eye, (16, 10))
    if forearms:
        for side in ("Left", "Right"):
            limb("Pre%sForeArm" % side, SK.pos(side + "ForeArm"), SK.pos(side + "Hand"), 0.04, 0.031, mat)

# ---------------------------------------------------------------- materials

R_BAR = 0.0075  # a #5 bar, 16 mm across the ribs


def ribs(g, P, col, rough, metal, height):
    """Rebar deformations from zl: two lengthwise ribs and slanted crosswise ribs between them, with cement crust
    near the concrete end (zl.s small)."""
    s, x, y = attr(g, "zl")
    r = g.math("SQRT", add(g, mul(g, x, x), mul(g, y, y)))
    sn = g.math("DIVIDE", y, g.math("MAXIMUM", r, 1e-5))
    cs = g.math("DIVIDE", x, g.math("MAXIMUM", r, 1e-5))
    lr = g.ramp(g.math("ABSOLUTE", sn), 0.2, 0.08)
    side = g.math("SIGN", sn)
    ph = g.math("FRACT", add(g, g.math("DIVIDE", s, 0.0095), mul(g, mul(g, side, cs), 0.28)))
    tr = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", ph, 0.5)), 0.32, 0.18)
    rib = g.math("MAXIMUM", lr, tr)
    height = add(g, height, mul(g, rib, 1.1))
    col = g.mix(mul(g, rib, 0.25), col, tk._darker(g, col, 1.35))
    crust = mul(g, g.ramp(s, 0.05, 0.022), g.ramp(g.noise(40.0, detail=6.0, vector=P), 0.35, 0.55))
    col = g.mix(crust, col, g.mix(g.noise(90.0, vector=P), (0.11, 0.105, 0.095), (0.2, 0.19, 0.175)))
    rough = g.mixf(crust, rough, 0.95)
    metal = g.mixf(crust, metal, 0.0)
    height = add(g, height, mul(g, crust, 0.8))
    return col, rough, metal, height


def concrete(name, seed, gore=0.0):
    """Broken concrete: grey cement paste, aggregate stones showing on the fresh breaks, air pores, grime in the
    hollows, dust on top, a smear of blood."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    tone = g.noise(7.0, detail=6.0, roughness=0.6, vector=P)
    col = g.mix(tone, (0.05, 0.048, 0.045), (0.1, 0.095, 0.088))
    cells = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(cells, "Scale", 130.0)
    g.links.new(mapping(g, P, scale=(1.0, 1.0, 1.0), loc=(0.2, 0.4, 0.1)), cells.inputs["Vector"])
    cell_col = tk._sock(cells.outputs, "Color")
    stone = mul(g, g.ramp(tk._sock(cells.outputs, "Distance"), 0.42, 0.3), g.ramp(g.noise(9.0, vector=P), 0.38, 0.55))
    stone_col = g.mix(g.separate(cell_col)[0], (0.04, 0.034, 0.027), (0.14, 0.12, 0.095))
    stone_col = g.mix(g.separate(cell_col)[1], stone_col, (0.08, 0.08, 0.085))
    col = g.mix(stone, col, stone_col)
    pores = mul(g, g.ramp(voronoi(g, mapping(g, P, loc=(1.1, 0.3, 0.6)), 420.0), 0.1, 0.04),
                g.ramp(g.noise(5.0, vector=P), 0.45, 0.65))
    col = g.mix(pores, col, (0.015, 0.014, 0.013))
    rough = add(g, 0.86, mul(g, tone, 0.08))
    height = add(g, mul(g, tone, 0.35), add(g, mul(g, stone, 0.12), mul(g, pores, -0.9)))
    dirt = tk._grime(g, 0.8)
    col = g.mix(mul(g, dirt, 0.85), col, (0.035, 0.03, 0.024))
    if gore:
        sm = mul(g, g.ramp(g.noise(3.0, detail=6.0, distortion=0.8, vector=P), 0.6, 0.7), gore)
        col, rough, height = dried_blood(g, col, rough, height, sm, P)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.6)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.4, 0.002))


bar_mat = rusty_iron("RebarSteel", seed=1.0, rust=0.95, scale=3.0, rust_value=0.33, gore=1.0, reach=0.09, grit=0.4,
                     scale_dark=0.25, bump=0.5, extra=ribs, rust_sat=0.6)
stub_mat = rusty_iron("RebarStub", seed=2.0, rust=0.9, scale=3.0, rust_value=0.33, grit=0.5, bump=0.5, extra=ribs,
                     rust_sat=0.6)
cement = concrete("Concrete", 3.0, gore=0.5)
flesh = gore_flesh("Gore", 4.0)

# ---------------------------------------------------------------- the bar's path

THRU = Vector((-0.17, 1.0, 0.2)).normalized()  # front to back through the chest: back, a little right and up
C = Vector((0.035, 0.05, 1.37))  # a point on that line inside the chest
F = entry(C - THRU * 0.5, THRU)  # where it goes in at the front
B = entry(C + THRU * 0.5, -THRU)  # and out at the back
print("[%s] in at (%.3f, %.3f, %.3f), out at (%.3f, %.3f, %.3f)" % ((SCRIPT,) + tuple(F) + tuple(B)))


def bend(p0, d0, d1, radius, n):
    """An arc of `radius` from p0 heading d0 round to heading d1: its points after p0, and the end heading."""
    d0, d1 = d0.normalized(), d1.normalized()
    ang = d0.angle(d1)
    axis = d0.cross(d1).normalized()
    pts = []
    for k in range(1, n + 1):
        a = ang * k / n
        rot = Matrix.Rotation(a, 3, axis)
        # integrate the arc: chord of the circle swept so far
        pts.append(p0 + (axis.cross(d0) * (1 - math.cos(a)) + d0 * math.sin(a)) * radius)
        _ = rot
    return pts


def run(start, heading, legs):
    """A bent bar from `start`: legs are (length, new heading, bend radius) — a straight run, then a bend toward
    the new heading. Returns dense points (every 4 mm)."""
    P = [start]
    d = heading.normalized()
    for length, nd, rad in legs:
        n = max(1, int(length / 0.004))
        for k in range(1, n + 1):
            P.append(P[-1] + d * (length / n))
        if nd is not None:
            nd = nd.normalized()
            P += bend(P[-1], d, nd, rad, max(3, int(d.angle(nd) * rad / 0.004)))
            d = nd
    return P


# Front: out of the chest 8 cm, a bend down and out (to the zombie's left), then to the concrete
front = run(F, -THRU, [(0.06, Vector((0.3, -0.75, -0.6)), 0.06), (0.1, None, 0)])
# Back: out 7 cm, a bend up and to the right, then out to the sheared end
back = run(B, THRU, [(0.065, Vector((-0.45, 0.55, 0.7)), 0.06), (0.14, None, 0)])
CHUNK = front[-1]
HEAD = (front[-1] - front[-6]).normalized()
dense = list(reversed(front)) + [F.lerp(B, t / 20) for t in range(1, 20)] + back


def thin(P):
    """Rings every 8 mm round the wounds and bends, 2.5 cm on the straights, none deep inside the body."""
    out = [P[0]]
    since = 0.0
    for i in range(1, len(P) - 1):
        since += (P[i] - P[i - 1]).length
        d = sdf(P[i])
        turn = (P[i + 1] - P[i]).normalized().angle((P[i] - P[i - 1]).normalized(), 0.0)
        step = 0.008 if abs(d) < 0.03 else (0.2 if d < -0.04 else (0.006 if turn > 0.02 else 0.025))
        if since >= step:
            out.append(P[i])
            since = 0.0
    out.append(P[-1])
    return out


def bar():
    P = thin(dense)
    # The sheared back end: squashed flat and a little wider, the last ring tilted
    S = arclen(P)

    def rad(i):
        t = (S[-1] - S[i])
        if t < 0.012:
            k = 1.0 - t / 0.012
            return (R_BAR * (1.0 + 0.35 * k), R_BAR * (1.0 - 0.45 * k))
        return R_BAR
    obj = tube("Bar", P, rad, bar_mat, sides=8, caps=True, phase=math.pi / 8)
    print("[%s] bar: %d rings, %.2f m" % (SCRIPT, len(P), S[-1]))
    return obj, P


def chunk():
    """The broken concrete lump round the bar's front end, and a cut stub of the crossing bar through it."""
    up = orth(UP, HEAD)
    side = HEAD.cross(up)
    c = CHUNK + HEAD * 0.026
    pts = []
    for k in range(26):
        a = RND.uniform(0, 2 * math.pi)
        b = RND.uniform(-1.0, 1.0)
        rr = math.sqrt(1 - b * b)
        q = Vector((math.cos(a) * rr, math.sin(a) * rr, b))
        q = Vector((q.x * 0.07, q.y * 0.042, q.z * 0.055)) * RND.uniform(0.7, 1.0)
        q.x += 0.012 * (1 if q.z > 0 else -0.5)  # lopsided
        pts.append(c + side * q.x + up * q.y + HEAD * q.z)
    # Two flat break faces: squash points beyond a plane onto it
    for nrm, off in ((side * 0.6 + up * 0.8 - HEAD * 0.1, 0.03), (-side * 0.7 + HEAD * 0.7, 0.045)):
        nrm = nrm.normalized()
        pts = [p - nrm * max(0.0, (p - c).dot(nrm) - off) for p in pts]
    lump = hull("Chunk", pts, cement)
    for v in lump.data.vertices:
        v.co += (v.co - c).normalized() * 0.005 * noise.noise(v.co * 45.0)
    stub_dir = (side * 0.9 + up * 0.3).normalized()
    sc = c - HEAD * 0.004 + up * 0.012
    stub = tube("Stub", [sc - stub_dir * 0.085, sc + stub_dir * 0.075], 0.0062, stub_mat, sides=8, caps=True)
    return [lump, stub]


def gore(P):
    """Torn flesh round the bar where it comes out of the chest and the back."""
    S = arclen(P)
    sf = S[min(range(len(P)), key=lambda i: (P[i] - F).length)]
    sb = S[min(range(len(P)), key=lambda i: (P[i] - B).length)]
    return [gore_sleeve("Gore0", P, sf - 0.016, 0.04, R_BAR, 1.6, flesh, seed=1.0),
            gore_sleeve("Gore1", P, sb + 0.02, 0.048, R_BAR, 1.8, flesh, seed=2.0)]


bar_obj, PATH = bar()
pieces = [bar_obj] + chunk() + gore(PATH)
for p in pieces:
    depth_attr(p, sdf)
    zk.on(p, "Spine2", "Rebar")
# The bar's zl.s counts from the concrete end; the stub's from its own end (crust along all of it is fine)

report(pieces)
parts = export(pieces)
print("[%s] concrete at (%.3f, %.3f, %.3f), back end at (%.3f, %.3f, %.3f)" % ((SCRIPT,) + tuple(CHUNK) + tuple(PATH[-1])))
zk.previews(SCRIPT, PREVIEWS, Vector((0.02, 0.0, 1.3)), distance=1.5)
close_up("chunk", CHUNK + Vector((0.0, 0.03, 0.03)), (0.6, -1.0, 0.35), distance=0.42)
close_up("back_close", B + THRU * 0.08, (-0.3, 1.0, 0.25), distance=0.45)
close_up("wound", F - THRU * 0.03, (0.9, -0.6, 0.1), distance=0.25)
print("[%s] done" % SCRIPT)
