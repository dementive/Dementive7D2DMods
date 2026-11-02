"""Bear trap (remnant): a rusty double long-spring leg-hold trap sprung shut on the left ankle, low on the shin. Its
two toothed jaws bite the shin from the front and back, standing up at about 50 degrees from the base where the leg
stopped them closing; the base bar runs through under the ankle between the hinge posts, and the two flat leaf springs
stick out either side (turned 25 degrees so the inner one angles back, clear of the other leg), their eyes riding up
the jaw arms. A short chain hangs from the outer end of the base, trailing back toward the ground, a broken link at its
end. All of it rusted dark and pitted, the jaws and teeth crusted with dried blood where they bite.

The teeth sink about 6 mm into Joe's shin (4 cm across there); the base bar and the middle of the jaws' bite are
inside the leg. One part on LeftLeg: "LeftLeg#Trap".

    blender -b --factory-startup --python bear_trap.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "BearTrap", "bear_trap", 3391

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

# ---------------------------------------------------------------- the leg

FOOT, KNEE = SK.pos("LeftFoot"), SK.pos("LeftLeg")


def leg_center(z):
    """The middle of Joe's shin at height z: between the bone line and the (calf-centered) hit box."""
    tb = (z - FOOT.z) / (KNEE.z - FOOT.z)
    bone = FOOT.lerp(KNEE, tb)
    a, b, r = next((a, b, r) for bone_, a, b, r in CAPS if bone_ == "LeftLeg")
    cap = a.lerp(b, (z - a.z) / (b.z - a.z))
    return Vector(((bone.x + cap.x) / 2, (bone.y + cap.y) / 2, z))


U = (leg_center(0.4) - leg_center(0.12)).normalized()
G = leg_center(0.2)  # where the jaws bite
R_LEG = 0.04
skin = taper_sdf(leg_center(0.0), leg_center(0.5), 0.036, 0.046)

# ---------------------------------------------------------------- the trap's frame and sizes

X = orth(Vector((math.cos(math.radians(-25)), math.sin(math.radians(-25)), 0.0)), U)  # hinge axis
Y = U.cross(X)  # toward the back jaw
R = 0.078  # jaw radius (15.6 cm spread)
JT, JH, TOOTH = 0.0048, 0.013, 0.0075  # jaw bar thickness, height, tooth height
LIFT = 0.006  # the hinge above the base bar
BITE = 0.006
_r2 = math.hypot(R, JH + TOOTH)
_d = math.atan2(JH + TOOTH, R)
THETA = math.acos((R_LEG - BITE) / _r2) - _d  # how far up the jaws stand
H_GRIP = R * math.sin(THETA) + (JH + TOOTH) * math.cos(THETA) + LIFT
C = G - U * H_GRIP  # the base bar's middle


def T(x, y, z):
    """Trap-local to world."""
    return C + X * x + Y * y + U * z


print("[%s] jaws stand at %.1f degrees, bite %.1f cm above the base; base at (%.3f, %.3f, %.3f)"
      % (SCRIPT, math.degrees(THETA), H_GRIP * 100, C.x, C.y, C.z))

# ---------------------------------------------------------------- materials

iron = rusty_iron("TrapIron", seed=1.0, rust=0.8, scale=3.0, rust_value=0.4, gore=1.0, reach=0.03, grit=0.5,
                  bump=0.45)
spring_steel = rusty_iron("SpringSteel", seed=2.0, rust=0.6, scale=3.5, rust_value=0.38, polish=0.35, grit=0.5,
                          gore=0.4, reach=0.03, bump=0.4)
chain_iron = rusty_iron("ChainIron", seed=3.0, rust=0.9, scale=4.0, rust_value=0.4, grit=0.6, bump=0.5)

# ---------------------------------------------------------------- parts


def jaw(name, side, phase):
    """One jaw: a half ring of flat bar from hinge to hinge, stood up THETA toward the leg, teeth along its top
    edge (offset half a tooth on the other jaw so they interlock)."""
    th = THETA
    teeth = 7
    a0, a1 = 0.42, math.pi - 0.42
    phis = [0.0, 0.2, a0]
    for k in range(1, 2 * teeth + 1):
        phis.append(a0 + (a1 - a0) * k / (2 * teeth))
    phis += [math.pi - 0.2, math.pi]
    H = Vector((0.0, -side * math.sin(th), math.cos(th)))  # the jaw's height direction, toward the leg

    def at(phi):
        p = Vector((R * math.cos(phi), side * R * math.sin(phi) * math.cos(th), R * math.sin(phi) * math.sin(th) + LIFT))
        r = Vector((math.cos(phi), side * math.sin(phi) * math.cos(th), math.sin(phi) * math.sin(th)))
        return p, r

    bm = bmesh.new()
    rings, vals = [], []
    for k, phi in enumerate(phis):
        p, r = at(phi)
        if a0 - 1e-6 <= phi <= a1 + 1e-6:
            kk = phis.index(phi) - 2
            top = JH + (TOOTH if (kk + phase) % 2 == 1 else 0.0)
        else:
            top = JH * 0.8
        ring = []
        for (dr, dh) in ((-1, 0.0), (1, 0.0), (0.6, top), (-0.6, top)):
            q = p + r * (dr * JT / 2) + H * dh
            if dh > 0 and top > JH:  # teeth taper to a point
                q = p + r * (dr * JT * 0.18) + H * dh
            w = T(q.x, q.y, q.z)
            ring.append(bm.verts.new(w))
            vals.append((phi * R, dr * JT / 2, dh))
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, iron)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 35)


def band(name, pts, side_dirs, width, thick, mat, closed=False):
    """A flat strip along pts, `width` along side_dirs (one per point), `thick` across."""
    P = [Vector(p) for p in pts]
    n = len(P)
    Tn, _, _ = frames(P, closed)
    S = arclen(P)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        W = orth(Vector(side_dirs[i]), Tn[i])
        N = Tn[i].cross(W)
        ring = []
        for sw, st in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            ring.append(bm.verts.new(P[i] + W * (sw * width / 2) + N * (st * thick / 2)))
            vals.append((S[i], sw * width / 2, st * thick / 2))
        rings.append(ring)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 40)


def base_and_posts():
    out = []
    span = R + 0.03
    pts = [T(-span, 0.0, -0.003), T(-R, 0.0, -0.003), T(0.0, 0.0, -0.003), T(R, 0.0, -0.003), T(span, 0.0, -0.003)]
    out.append(band("Base", pts, [Y] * 5, 0.024, 0.0062, iron))
    for s in (1, -1):
        out.append(band("Post%d" % s, [T(s * R, 0.0, -0.002), T(s * R, 0.0, LIFT + 0.006)], [Y] * 2, 0.026, 0.012,
                        iron))
    return out


def spring(s):
    """A leaf spring off the post at x = s * R: lower leaf out along the base, round the bend, the upper leaf back up
    to the eye that rides up both jaw arms."""
    x0, x1 = s * (R + 0.012), s * (R + 0.14)
    zb, rb = -0.0075, 0.011
    eye_x, eye_z = s * (R - 0.006), 0.03
    pts = []
    for k in range(5):
        pts.append(T(x0 + (x1 - x0) * k / 4, 0.0, zb))
    for k in range(1, 7):
        a = math.pi * k / 6
        pts.append(T(x1 + s * rb * math.sin(a), 0.0, zb + rb * (1 - math.cos(a))))
    top_z = zb + 2 * rb
    ex = eye_x + s * 0.017
    for k in range(1, 6):
        t = k / 5
        pts.append(T(x1 + (ex - x1) * t, 0.0, top_z + (eye_z - top_z) * t ** 1.2))
    leaf = band("Spring%d" % s, pts, [Y] * len(pts), 0.021, 0.0036, spring_steel)
    # The eye: a flat loop round both jaw arms
    ring = []
    hx, hy = 0.014, 0.034
    for k in range(12):
        a = 2 * math.pi * k / 12
        ring.append(T(eye_x + hx * math.cos(a), hy * math.sin(a), eye_z))
    eye = band("Eye%d" % s, ring, [U] * 12, 0.012, 0.0034, spring_steel, closed=True)
    return [leaf, eye]


def chain_link(name, center, along, across, length=0.034, width=0.021, wire=0.0034, open_gap=0.0):
    """An oval chain link round `center`, long along `along`, flat in the plane of along and across."""
    a = along.normalized()
    b = orth(across, a)
    hl, hw = length / 2 - wire, width / 2 - wire
    pts = []
    for k in range(5):  # the two round ends
        t = -math.pi / 2 + math.pi * k / 4
        pts.append(center + a * (hl - hw + hw * math.cos(t)) + b * (hw * math.sin(t)))
    for k in range(5):
        t = math.pi / 2 + math.pi * k / 4
        pts.append(center + a * (-(hl - hw) + hw * math.cos(t)) + b * (hw * math.sin(t)))
    if open_gap:
        pts = pts[1:] + pts[:1]
        return tube(name, pts[:-1], wire, chain_iron, sides=4, caps=True, phase=math.pi / 4)
    return tube(name, pts, wire, chain_iron, sides=4, closed=True, phase=math.pi / 4)


def chain():
    """The chain off the outer end of the base, hanging down and trailing back, links turned alternately."""
    start = T(R + 0.024, 0.0, -0.01)
    ctrl = [start, start - U * 0.03 + Y * 0.004, start - U * 0.062 + Y * 0.015 + X * 0.006,
            start - U * 0.082 + Y * 0.045 + X * 0.012, start - U * 0.09 + Y * 0.085 + X * 0.012]
    path = catmull(ctrl, 10)
    S = arclen(path)
    pitch = 0.0215
    out = []
    n = int(S[-1] / pitch)
    for k in range(n + 1):
        c, d = point_at(path, S, k * pitch)
        across = d.cross(X) if k % 2 == 0 else X
        last = k == n
        out.append(chain_link("Link%d" % k, c, d, across, open_gap=0.01 if last else 0.0))
    print("[%s] chain: %d links, lowest at z %.3f" % (SCRIPT, len(out), min(p.z for p in path) - 0.012))
    return out


pieces = [jaw("JawFront", -1, 0), jaw("JawBack", 1, 1)] + base_and_posts() + spring(1) + spring(-1) + chain()
for p in pieces:
    depth_attr(p, skin)
    zk.on(p, "LeftLeg", "Trap")

report(pieces, skin)
parts = export(pieces)
focus = G - U * 0.03
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.9)
close_up("close", focus, (0.5, -1.0, 0.45), distance=0.42)
close_up("inner", focus, (-0.7, -0.4, 0.5), distance=0.45)
close_up("back_close", focus, (0.5, 1.0, 0.3), distance=0.42)
print("[%s] done" % SCRIPT)
