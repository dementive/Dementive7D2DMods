"""Pitchfork (remnant): a three-tine hay fork driven into the lower back from behind and below, its ash handle snapped
off about 40 cm out. The tines are forged steel gone dark and rusty, rubbed bright in streaks along their length, their
bow and the conical socket pitted with rust, a rivet through the socket; dried blood soaks the tines where they go in,
runs and spatters further out, and a couple of scraps of torn flesh cling to them. The handle stump is weathered ash,
grimy where hands held it, broken in a jagged, splintered end with slivers peeling off.

The tines sink 3.5 cm past the stand-in's skin (so the entry stays hidden on slimmer zombies) and the fork points
back, down and a little to the zombie's right. One part on Spine1: "Spine1#Pitchfork".

    blender -b --factory-startup --python pitchfork.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "Pitchfork", "pitchfork", 4417

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


def tube(name, pts, radius, mat, sides=6, closed=False, caps=True, twist=0.0, phase=0.0, normals=None, smooth=60,
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
    return tk.smooth(obj, smooth)


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


def gore_mask(g, P, reach=0.035, amount=1.0, runs=0.6, dots=0.6):
    """How bloody a point is from its distance to the skin (zd.x): soaked at and under the skin, ragged out to
    about `reach`, with runs and spatter beyond it."""
    d = attr(g, "zd")[0]
    edge = add(g, d, mul(g, g.math("SUBTRACT", g.noise(16.0, detail=6.0, roughness=0.65, vector=P), 0.5), reach * 0.9))
    m = g.ramp(edge, reach, reach * 0.4)
    streak = g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(70.0, 70.0, 5.0))), 0.6, 0.67)
    m = g.math("MAXIMUM", m, mul(g, mul(g, streak, g.ramp(d, reach * 2.6, reach * 0.6)), runs))
    sp = mul(g, g.ramp(voronoi(g, mapping(g, P, loc=(0.3, 1.1, 0.7)), 110.0), 0.13, 0.05),
             g.ramp(g.noise(7.0, vector=P), 0.45, 0.6))
    m = g.math("MAXIMUM", m, mul(g, mul(g, sp, g.ramp(d, reach * 3.5, reach)), dots))
    return mul(g, m, amount)


def dried_blood(g, col, rough, height, mask, P):
    """Dried blood: deep red going near-black where it pooled thick, tacky and glossy there, dull and flaking where
    thin."""
    thick = g.ramp(g.noise(11.0, detail=5.0, vector=P), 0.35, 0.72)
    mask = g.math("MINIMUM", mask, 1.0)
    bc = g.mix(thick, (0.15, 0.007, 0.011), (0.04, 0.002, 0.003))
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
               gore=0.0, reach=0.035, grit=0.5, scale_dark=0.4, grime=0.6, bump=0.35, extra=None):
    """Old iron and steel: dark mill scale, coarse rust in blooms and crevices (the photo, toned down), pitted,
    rubbed bright in places (polish), grimy and dusty, bloodied near the skin (gore, from zd)."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    p = tk.photo(g, "rust_coarse_01", scale, (seed * 0.31, 0.5 + seed * 0.17, seed * 0.23))
    tone = g.noise(6.0, detail=4.0, vector=P)
    iron = g.mix(tone, base, tk._darker(g, base, 0.6))
    scale_m = mul(g, g.ramp(g.noise(9.0, detail=6.0, roughness=0.6, vector=P), 0.45, 0.6), scale_dark)
    iron = g.mix(scale_m, iron, (0.022, 0.021, 0.02))
    rust_col = tk.grade(g, p["color"], 0.78, rust_value)
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
        bm_ = gore_mask(g, P, reach, gore)
        col, rough, height = dried_blood(g, col, rough, height, bm_, P)
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


def wood(name, seed, dark=(0.045, 0.034, 0.024), light=(0.12, 0.092, 0.064), grip=0.6, gore=0.0):
    """Weathered ash: long grain streaks and fine dark lines along zl's length, checks (cracks) along the grain,
    greyed by the weather in patches, darker and smoother where hands held it, grimy."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    L = combine(g, x, y, s)
    P = seeded(g, seed)
    streak = g.noise(1.0, detail=6.0, roughness=0.6, vector=mapping(g, L, scale=(240.0, 240.0, 7.0), loc=(seed, 0.3, 0.1)))
    col = g.mix(g.ramp(streak, 0.3, 0.75), dark, light)
    fine = g.noise(1.0, detail=2.0, vector=mapping(g, L, scale=(700.0, 700.0, 12.0), loc=(0.2, seed, 0.5)))
    lines = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", fine, 0.5)), 0.045, 0.0)
    col = g.mix(mul(g, lines, 0.75), col, (0.018, 0.013, 0.009))
    check = g.noise(1.0, detail=2.0, vector=mapping(g, L, scale=(380.0, 380.0, 4.0), loc=(seed * 0.3, 0.9, 0.2)))
    checks = mul(g, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", check, 0.5)), 0.016, 0.0),
                 g.ramp(g.noise(9.0, vector=P), 0.4, 0.55))
    col = g.mix(checks, col, (0.008, 0.006, 0.005))
    grey = g.ramp(g.noise(3.0, detail=5.0, distortion=0.4, vector=P), 0.4, 0.7)
    col = g.mix(mul(g, grey, 0.4), col, tk.grade(g, col, 0.5, 1.0))
    rough = add(g, 0.7, mul(g, streak, 0.14))
    height = add(g, mul(g, streak, 0.3), mul(g, add(g, lines, checks), -0.7))
    if grip:
        band = mul(g, g.ramp(s, 0.03, 0.08), g.ramp(g.noise(5.0, detail=4.0, vector=P), 0.3, 0.6))
        band = mul(g, band, grip)
        col = g.mix(band, col, tk._darker(g, col, 0.55))
        rough = g.mixf(band, rough, 0.45)
    dirt = tk._grime(g, 0.7)
    col = g.mix(mul(g, dirt, 0.8), col, (0.02, 0.016, 0.012))
    rough = g.mixf(dirt, rough, 0.9)
    if gore:
        sp = mul(g, g.ramp(voronoi(g, mapping(g, P, loc=(0.7, 0.2, 1.3)), 70.0), 0.13, 0.05),
                 g.ramp(g.noise(5.0, detail=4.0, vector=P), 0.45, 0.6))
        sm = mul(g, g.ramp(g.noise(4.0, detail=6.0, distortion=0.8, vector=P), 0.62, 0.7), g.ramp(s, 0.07, 0.0))
        col, rough, height = dried_blood(g, col, rough, height, mul(g, g.math("MAXIMUM", sp, sm), gore), P)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.2)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.4, 0.002))


def broken_wood(name, seed):
    """The snapped end: paler fibrous wood inside, torn along the grain, grey with grime in the fibers."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    L = combine(g, x, y, s)
    P = seeded(g, seed)
    fib = g.noise(1.0, detail=6.0, roughness=0.7, vector=mapping(g, L, scale=(700.0, 700.0, 30.0), loc=(seed, 0.1, 0.4)))
    col = g.mix(g.ramp(fib, 0.3, 0.75), (0.06, 0.046, 0.032), (0.17, 0.135, 0.095))
    torn = g.ramp(g.noise(30.0, detail=6.0, vector=P), 0.55, 0.7)
    col = g.mix(mul(g, torn, 0.7), col, (0.03, 0.024, 0.018))
    dirt = tk._grime(g, 0.8)
    col = g.mix(mul(g, dirt, 0.7), col, (0.03, 0.024, 0.018))
    rough = add(g, 0.82, mul(g, fib, 0.1))
    height = mul(g, add(g, fib, mul(g, torn, -0.8)), 0.6)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.3)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.5, 0.002))


steel = rusty_iron("ForkSteel", seed=1.0, rust=0.7, scale=3.0, polish=0.7, gore=1.0, reach=0.1, grit=0.5)
socket_steel = rusty_iron("ForkSocket", seed=2.0, rust=0.8, scale=2.5, gore=0.4, reach=0.13, grit=0.6)
ash = wood("Ash", 3.0, gore=0.5)
snapped = broken_wood("AshBroken", 4.0)
flesh = gore_flesh("Gore", 5.0)

# ---------------------------------------------------------------- the fork's frame

# Where the middle tine meets the skin, and the way the fork points out of the body (back, down, to the right)
D = Vector((-0.28, 0.9, -0.33)).normalized()
AIM = Vector((-0.03, 0.17, 1.13)) + D * 0.3
E = entry(AIM, -D)
L = orth(Vector((1.0, 0.0, 0.0)), D)
L = (Matrix.Rotation(math.radians(14.0), 3, D) @ L).normalized()
NF = D.cross(L).normalized()  # the side the tines curve toward
print("[%s] entry (%.3f, %.3f, %.3f), aim (%.2f, %.2f, %.2f)" % ((SCRIPT,) + tuple(E) + tuple(D)))

A_S = 0.17  # the crown: where the tines meet under the socket, measured out from the skin
SPREAD = 0.08
BOW = 0.058
SINK = 0.035


def fork(a, b, c=0.0):
    return E + D * a + L * b + NF * c


def scoop(a):
    """The tines' gentle curve toward NF, more toward their tips."""
    return 0.35 * max(0.0, A_S - a) ** 2


def tine(k, side):
    """One tine from the crown down into the body: round, thick at the bow, tapering to a point SINK past the skin,
    with rings close together round the skin line for the blood."""
    ab = []
    if side:
        for m in range(8):
            ph = (math.pi / 2) * m / 7
            ab.append((A_S - BOW * (1.0 - math.cos(ph)), side * SPREAD * math.sin(ph)))
    else:
        ab.append((A_S + 0.004, 0.0))
    bow = len(ab)
    a = ab[-1][0] - 0.004
    while a > -0.1:
        ab.append((a, side * SPREAD))
        a -= 0.004
    dense = [fork(a, b, scoop(a)) for a, b in ab]
    S = arclen(dense)
    hit = None
    for i in range(1, len(dense)):
        if sdf(dense[i]) < 0.0:
            hit = S[i]
            break
    end = hit + SINK
    cut = [p for p, s in zip(dense, S) if s <= end]
    P = thin_path(cut, sdf, near=0.03, fine=0.008, coarse=0.024, keep=set(range(bow)))
    P = [p + (L * jit(0.0006) if 0 < i < len(P) - 1 else Vector()) for i, p in enumerate(P)]
    S = arclen(P)
    R = []
    for s in S:
        t = s / S[-1]
        r = 0.0066 - 0.0011 * smoothstep(0.0, 0.3, t) - 0.0016 * smoothstep(0.4, 0.85, t)
        r *= 1.0 - 0.65 * smoothstep(0.88, 1.0, t)
        R.append(r)
    obj = tube("Tine%d" % k, P, R, steel, sides=6, caps=True, phase=0.3 * k)
    print("[%s] tine %d: %.1f cm out of the skin, %.1f cm in, %d rings" % (SCRIPT, k, hit * 100, SINK * 100, len(P)))
    return obj, P, hit


def gore_bits(tines):
    """Shreds of torn flesh and clot clinging round the tines a little way out of the wound."""
    return [gore_sleeve("GoreBit%d" % k, P, hit - at, length, 0.0052, fat, flesh, seed=k * 1.7)
            for k, ((P, hit), at, length, fat) in enumerate(((tines[1], 0.02, 0.03, 1.9), (tines[2], 0.034, 0.022, 1.6),
                                                             (tines[0], 0.01, 0.018, 1.5)))]


def socket():
    """The conical socket the handle sits in, a ridge round its mouth and a rivet through it."""
    a0, a1 = A_S - 0.004, A_S + 0.11
    rings = [(a0, 0.0105), (a0 + 0.012, 0.0115), (A_S + 0.075, 0.0158), (a1 - 0.011, 0.0184), (a1 - 0.005, 0.0194),
             (a1, 0.0195)]
    pts = [fork(a, 0.0) for a, r in rings]
    cone = tube("Socket", pts, [r for a, r in rings], socket_steel, sides=12, caps=True)
    rivet = tube("Rivet", [fork(A_S + 0.087, 0.0, -0.0195), fork(A_S + 0.087, 0.0, 0.0195)], 0.0032, socket_steel,
                 sides=8)
    collar = tube("Crown", [fork(A_S - 0.014, 0.0), fork(A_S + 0.006, 0.0)], lambda i: (0.012, 0.0095), steel,
                  sides=8, normals=[L, L])
    return [cone, rivet, collar]


def handle():
    """The ash handle from inside the socket's mouth to its snapped end, the break jagged, with splinters."""
    a0, a1 = A_S + 0.097, A_S + 0.245
    r = 0.0172
    sides = 10
    n = 6
    bm = bmesh.new()
    rings, vals = [], []
    spikes = [0.002 + 0.032 * max(0.0, math.sin(2.1 * j + 0.7)) ** 3 + jit(0.006) for j in range(sides)]
    for i in range(n + 1):
        a = a0 + (a1 - a0) * min(i, n - 1) / (n - 1)
        ring = []
        for j in range(sides):
            ang = 2 * math.pi * j / sides
            rr = r * (1.0 + 0.012 * math.sin(ang * 3 + i))
            aa = a
            if i == n:  # the jagged break: spikes along the grain, thinner toward their tips
                aa = a1 + spikes[j]
                rr = r * (0.84 - 0.25 * spikes[j] / 0.035)
            ring.append(bm.verts.new(fork(aa, math.cos(ang) * rr, math.sin(ang) * rr)))
            vals.append((aa - a0, math.cos(ang) * rr, math.sin(ang) * rr))
        rings.append(ring)
    for i in range(n):
        for j in range(sides):
            j1 = (j + 1) % sides
            f = bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
            if i == n - 1:
                f.material_index = 1
    bm.faces.new(list(reversed(rings[0])))
    c = bm.verts.new(fork(a1 - 0.004, 0.002, -0.001))
    vals.append((a1 - 0.004 - a0, 0.0, 0.0))
    for j in range(sides):
        f = bm.faces.new((rings[n][j], rings[n][(j + 1) % sides], c))
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Handle", bm, ash)
    obj.data.materials.append(snapped)
    set_attr(obj, "zl", vals)
    tk.smooth(obj, 50)
    out = [obj]
    # Splinters peeling off the break
    for k, (ang, ln, w, flare) in enumerate(((0.75, 0.07, 0.004, 0.12), (2.9, 0.05, 0.0034, 0.25),
                                              (4.6, 0.038, 0.0028, 0.06), (5.6, 0.03, 0.0024, 0.35))):
        base = a1 - 0.02
        pts = []
        for m in range(4):
            t = m / 3
            rr = r * (0.9 + flare * t * t * 2.5)
            pts.append(fork(base + ln * t, math.cos(ang + 0.08 * t) * rr, math.sin(ang + 0.08 * t) * rr))
        rad = [(w, w * 0.45), (w * 0.8, w * 0.4), (w * 0.5, w * 0.25), (0.0004, 0.0003)]
        rot = Vector((math.cos(ang), math.sin(ang), 0.0))
        nrm = [L * rot.x + NF * rot.y] * 4
        out.append(tube("Splinter%d" % k, pts, rad, snapped, sides=3, normals=nrm, phase=0.5))
    return out


tines = [tine(0, 0.0), tine(1, 1.0), tine(2, -1.0)]
pieces = [t[0] for t in tines] + gore_bits([(t[1], t[2]) for t in tines]) + socket() + handle()
for p in pieces:
    depth_attr(p, sdf, seed=0.0)
    zk.on(p, "Spine1", "Pitchfork")

report(pieces)
parts = export(pieces)
tip = fork(0.42, 0.0)
print("[%s] handle end %.1f cm out from the skin, at (%.3f, %.3f, %.3f)" % ((SCRIPT, (tip - E).dot(D) * 100) + tuple(tip)))
focus = E + D * 0.16
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.25)
close_up("close", E + D * 0.12, (0.9, 0.7, 0.15), distance=0.42)
close_up("tines", E + D * 0.05 + Vector((0.0, 0.0, 0.01)), (0.25, 0.4, -0.6), distance=0.26)
close_up("break", E + D * 0.37, (0.2, 0.6, 0.9), distance=0.25)
print("[%s] done" % SCRIPT)
