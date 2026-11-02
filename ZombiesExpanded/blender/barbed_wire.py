"""Barbed wire (remnant): lengths of old two-strand barbed wire the zombie got tangled in, in up to three places, each
its own variant part (the game shows a random mix, at least one):

- WireVar1, round the right forearm: a couple of loose, uneven coils biting into the skin here and there and standing
  off it elsewhere, a cut end poking out where it starts and a long loose end sprung out from the wrist end, kinked.
- WireVar2, round the left thigh: a coil and a half sprung loose over the shorts or trousers, from a cut end high on
  the outside down to above the knee, the loose end springing out behind.
- WireVar3, round the waist: a loop and a bit slanting from the right hip up across the belly, loose, the loose end
  springing out and down at the back right.

Four-point barbs every 10 to 12 cm. The galvanizing is gone: dark brown rust with dull grey patches, grimy, and
crusted with dried blood where the wire and barbs dig in. The wire is a little heavier than real (3.4 mm strands) so
it shows at a distance.

The forearm coils sit round Joe's bare forearm (4 cm across at the elbow, 3.1 at the wrist, well inside the fat 5 cm
hit box). The thigh and waist coils follow Joe's real body (radii measured on the vanilla mesh, in tables below),
looser at the waist's front and sides where the nurse's waist is fuller than Joe's scaled down (the game scales
Spine1 pieces by the chest hit box: 0.8 on her). Parts "RightForeArm#WireVar1", "LeftUpLeg#WireVar2",
"Spine1#WireVar3".

    blender -b --factory-startup --python barbed_wire.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "BarbedWire", "barbed_wire", 6143

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
    bc = g.mix(thick, (0.07, 0.009, 0.008), (0.024, 0.004, 0.003))  # dark and dull: the game's shader shows red brighter
    col = g.mix(mask, col, bc)
    rough = g.mixf(mask, rough, g.mixf(thick, 0.55, 0.35))
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

# ---------------------------------------------------------------- the wire, wherever it goes

STRAND = 0.0017  # each of the two line wires (3.4 mm: a little heavy, so it shows at a distance)
PITCH = 0.075  # one full twist of the pair
BARB_R = 0.0014
STEP = 0.016  # path samples (the big loops round the thigh and waist get by with fewer)

# Dark: the galvanizing long gone to rust (the game's shader shows pale, metallic wire as a faint silver line)
wire_mat = rusty_iron("BarbedWire", seed=1.0, rust=0.85, scale=6.0, base=(0.032, 0.03, 0.028), rust_value=0.22,
                      rust_sat=0.95, scale_dark=0.3, gore=0.85, reach=0.012, grit=0.1, bump=0.3, blood_scale=60.0)


def strands(tag, P):
    """The two line wires twisted round each other along the path P."""
    S = arclen(P)
    _, N_, B_ = frames(P)
    out = []
    for k in range(2):
        pts = []
        for i, p in enumerate(P):
            a = 2 * math.pi * S[i] / PITCH + k * math.pi
            pts.append(p + (N_[i] * math.cos(a) + B_[i] * math.sin(a)) * STRAND * 1.02)
        out.append(tube("%sStrand%d" % (tag, k), pts, STRAND, wire_mat, sides=3, caps=True, phase=k))
    return out


def barbs(tag, P, first=0.035, every=0.1):
    """Four-point barbs: two short wires each wrapped round the pair, their cut ends sticking out."""
    S = arclen(P)
    _, N_, _ = frames(P)
    out = []
    s = first
    k = 0
    while s < S[-1] - 0.03:
        c, t = point_at(P, S, s)
        i = min(range(len(P)), key=lambda j: abs(S[j] - s))
        n0, b0 = orth(N_[i], t), t.cross(orth(N_[i], t))
        beta = RND.uniform(0, 2 * math.pi)
        for w in range(2):
            bb = beta + w * math.pi / 2
            off = t * (w * 0.004 - 0.002)

            def rad(ang, r):
                return n0 * math.cos(ang) * r + b0 * math.sin(ang) * r
            ln = 0.0135 + jit(0.002)
            pts = [c + off + rad(bb, ln) + t * 0.003,
                   c + off + rad(bb + 1.4, 0.0032) + t * 0.002,
                   c + off + rad(bb + math.pi, ln) + t * 0.0045]
            out.append(tube("%sBarb%d_%d" % (tag, k, w), pts, [0.0002, BARB_R, 0.0002], wire_mat, sides=3,
                            caps=True))
        k += 1
        s += every + jit(0.012)
    print("[%s] %s: wire %.2f m, %d samples, %d barbs" % (SCRIPT, tag, S[-1], len(P), k))
    return out


def wire(tag, P, bone, piece, skin, every=0.1):
    out = strands(tag, P) + barbs(tag, P, every=every)
    for p in out:
        depth_attr(p, skin)
        zk.on(p, bone, piece)
    gaps = [skin(p) for p in P]
    print("[%s] %s: wire center off the skin min %.1f mm, max %.1f mm" % (SCRIPT, tag, min(gaps) * 1000,
                                                                         max(gaps) * 1000))
    return out


def table_radius(table, step, z0, dz, phi, z):
    """A body's radius at angle phi (radians, from +X toward -Y) and height z, from rows of radii measured every
    `step` degrees on the vanilla mesh (rows from z0 up every dz), smoothed a little and interpolated."""
    n = len(table[0])
    zi = max(0.0, min(len(table) - 1.0, (z - z0) / dz))
    j0 = min(int(zi), len(table) - 2)
    tz = zi - j0
    f = (math.degrees(phi) % 360.0) / step - 0.5
    i0 = int(math.floor(f))
    ti = f - i0

    def row(j, i):
        r = table[j]
        return (r[(i - 1) % n] + 2 * r[i % n] + r[(i + 1) % n]) / 4.0

    def at(j):
        return row(j, i0) * (1 - ti) + row(j, i0 + 1) * ti
    return (at(j0) * (1 - tz) + at(j0 + 1) * tz) / 100.0


def body_sdf(center, table, step, z0, dz):
    """Distance from a point to a body measured as radii round a vertical axis through `center` (x, y)."""
    def f(p):
        d = Vector((p.x - center[0], p.y - center[1]))
        phi = math.atan2(-d.y, d.x)
        return d.length - table_radius(table, step, z0, dz, phi, p.z)
    return f


# ---------------------------------------------------------------- Var1: round the right forearm

ELBOW, WRIST = SK.pos("RightForeArm"), SK.pos("RightHand")
F = (WRIST - ELBOW).normalized()
FRONT = Vector((0.0, -1.0, 0.0))
TOP = orth(UP, F)
R0, R1 = 0.04, 0.031  # Joe's bare forearm at the elbow and wrist
arm_skin = taper_sdf(ELBOW, WRIST, R0, R1)


def arm_path():
    """The wire's center line: a short cut end, two and a bit loose coils from near the elbow to near the wrist, and
    the loose end springing off forward and out."""
    def axis_pt(t):
        return ELBOW.lerp(WRIST, t)

    def r_skin(t):
        return R0 + (R1 - R0) * t

    def radial(phi):
        return TOP * math.cos(phi) + FRONT * math.sin(phi)
    turns = 2.3
    n = int(turns * 9) + 1
    ctrl = []
    for k in range(n):
        u = k / (n - 1)
        phi = 0.5 + 2 * math.pi * turns * u
        t = 0.26 + 0.52 * u + 0.035 * math.sin(5.0 * u + 0.4)
        gap = 0.0095 + 0.011 * math.sin(2.3 * phi + 0.9) + 0.004 * math.sin(7.1 * phi) + jit(0.003)
        gap = max(-0.0016, gap)  # where it touches it bites in a little
        ctrl.append(axis_pt(t) + radial(phi) * (r_skin(t) + 0.0026 + gap))
    phi0 = 0.5
    t0 = ctrl[1] - ctrl[0]
    start = [ctrl[0] + radial(phi0) * 0.022 - t0.normalized() * 0.012, ctrl[0] + radial(phi0) * 0.008 - t0 * 0.3]
    last, tang = ctrl[-1], (ctrl[-1] - ctrl[-2]).normalized()
    phi1 = 0.5 + 2 * math.pi * turns
    out1 = (tang + radial(phi1) * 0.9).normalized()
    out2 = (FRONT * 0.7 + radial(phi1) * 0.5 + F * 0.35).normalized()
    q1 = last + out1 * 0.035
    q2 = q1 + (out1 * 0.5 + out2 * 0.5).normalized() * 0.045
    q3 = q2 + out2 * 0.06 + F * 0.01
    pts = catmull(start + ctrl + [q1, q2, q3], 4)
    return resample(pts, STEP)


# ---------------------------------------------------------------- Var2: round the left thigh

# Joe's left thigh in his baggy shorts, measured on the vanilla mesh: radii (cm) every 22.5 degrees from his left
# (+X) toward his front (-Y), round (0.13, 0.002), from z 0.66 up every 2 cm
THIGH_C = (0.13, 0.002)
THIGH = [
    [11.3, 11.3, 11.2, 11.9, 12.3, 12.3, 11.2, 11.2, 11.3, 11.8, 11.9, 12.1, 11.5, 11.2, 10.6, 10.9],
    [11.0, 11.2, 11.3, 11.9, 12.5, 12.7, 12.2, 11.4, 11.3, 12.0, 12.1, 12.1, 11.6, 11.3, 10.7, 10.9],
    [11.1, 10.6, 11.0, 11.9, 12.3, 13.1, 12.5, 11.7, 11.4, 12.0, 12.3, 12.1, 11.5, 11.1, 10.6, 11.3],
    [12.7, 12.9, 12.3, 11.6, 12.3, 13.4, 12.7, 12.0, 11.5, 11.9, 12.4, 12.2, 11.4, 10.3, 11.9, 12.6],
    [13.2, 13.2, 11.8, 11.4, 12.3, 13.3, 12.9, 12.2, 11.6, 12.1, 12.6, 12.3, 11.4, 9.7, 11.6, 12.4],
    [12.8, 13.0, 12.3, 11.1, 12.5, 12.9, 13.3, 12.3, 11.8, 12.4, 12.8, 12.4, 11.5, 9.5, 11.4, 12.1],
    [12.1, 12.7, 12.0, 10.9, 11.7, 12.8, 13.4, 12.5, 12.1, 12.8, 13.2, 12.5, 11.6, 9.6, 11.4, 11.8],
    [11.6, 12.1, 11.7, 10.7, 12.0, 12.9, 13.0, 12.5, 12.1, 13.1, 13.6, 12.6, 10.7, 10.3, 11.2, 11.3],
    [11.2, 11.4, 11.4, 10.9, 12.0, 13.2, 13.0, 12.9, 12.2, 13.5, 14.1, 13.0, 11.5, 10.5, 10.9, 10.6],
]
thigh_skin = body_sdf(THIGH_C, THIGH, 22.5, 0.66, 0.02)
INNER_X = 0.006  # the coil stays this side of the gap between the thighs


def thigh_path():
    """A coil and a half sprung loose round the thigh over the shorts, from a cut end high on the outside front down
    to above the hem, touching in places and standing off elsewhere, the loose end springing out behind."""
    def radial(phi):
        return Vector((math.cos(phi), -math.sin(phi), 0.0))

    def at(phi, z, gap):
        r = table_radius(THIGH, 22.5, 0.66, 0.02, phi, z) + 0.0026 + gap
        d = radial(phi)
        if d.x < -1e-3:  # between the legs: no further in than INNER_X
            r = min(r, (THIGH_C[0] - INNER_X) / -d.x)
        return Vector((THIGH_C[0], THIGH_C[1], z)) + d * r
    turns = 1.2
    n = int(turns * 12) + 1
    phi0 = math.radians(-45)  # starts on the outside, toward the back
    ctrl = []
    for k in range(n):
        u = k / (n - 1)
        phi = phi0 + 2 * math.pi * turns * u
        z = 0.8 - 0.11 * u + 0.008 * math.sin(4.0 * u + 0.6)
        gap = 0.011 + 0.008 * math.sin(2.2 * phi + 0.4) + 0.003 * math.sin(6.3 * phi) + jit(0.002)
        ctrl.append(at(phi, z, max(-0.002, gap)))
    t0 = (ctrl[1] - ctrl[0]).normalized()
    start = [ctrl[0] - t0 * 0.03 + radial(phi0) * 0.02, ctrl[0] - t0 * 0.012 + radial(phi0) * 0.006]
    phi1 = phi0 + 2 * math.pi * turns
    last, tang = ctrl[-1], (ctrl[-1] - ctrl[-2]).normalized()
    out1 = (tang + radial(phi1) * 0.8).normalized()
    q1 = last + out1 * 0.035 - UP * 0.004
    q2 = q1 + (out1 + radial(phi1) * 0.5 - UP * 0.3).normalized() * 0.045
    q3 = q2 + (radial(phi1) * 0.7 - UP * 0.45 - tang * 0.3).normalized() * 0.045
    pts = catmull(start + ctrl + [q1, q2, q3], 4)
    return resample(pts, STEP * 1.3)


# ---------------------------------------------------------------- Var3: round the waist

# Joe's waist, measured on the vanilla mesh: radii (cm) every 15 degrees from his left (+X) toward his front (-Y),
# round (0, 0.015), from z 1.04 up every 2 cm
WAIST_C = (0.0, 0.015)
WAIST = [
    [19.6, 20.4, 19.1, 17.9, 15.6, 14.7, 16.1, 16.2, 16.7, 18.4, 18.4, 18.8, 19.3, 19.1, 18.2, 15.0, 14.8, 14.7, 14.9,
     15.0, 16.1, 17.2, 18.0, 18.8],
    [19.9, 20.2, 18.9, 17.7, 15.6, 14.7, 15.3, 16.5, 16.4, 17.3, 18.2, 18.1, 18.5, 18.4, 18.3, 16.5, 14.3, 14.5, 15.4,
     15.5, 15.7, 16.8, 17.5, 18.9],
    [19.6, 19.8, 18.7, 17.4, 15.1, 14.3, 15.4, 15.9, 16.3, 17.3, 17.9, 17.6, 17.7, 17.8, 17.4, 16.8, 15.5, 14.9, 14.7,
     15.7, 15.8, 16.2, 17.2, 18.8],
    [19.3, 19.2, 18.2, 17.0, 14.9, 14.0, 15.2, 15.6, 15.6, 16.5, 17.8, 17.7, 17.3, 17.0, 16.5, 16.4, 16.4, 15.6, 14.9,
     15.4, 15.9, 16.3, 17.1, 18.8],
    [18.4, 18.5, 17.8, 15.8, 14.5, 13.8, 14.6, 15.6, 15.5, 15.7, 17.1, 17.3, 17.3, 17.0, 15.8, 15.9, 15.9, 15.8, 15.7,
     15.7, 16.0, 16.2, 17.3, 18.2],
]
waist_skin = body_sdf(WAIST_C, WAIST, 15.0, 1.04, 0.02)


def waist_path():
    """A loop round the waist, slanting from low on the right hip up across the belly to the left side and round the
    back, loose: off the shirt a couple of centimeters most of the way (the vanilla zombies' waists don't scale like
    Joe's), touching it here and there. Both ends at the right hip: a short cut end, and the loose end springing out
    and down over it."""
    def radial(phi):
        return Vector((math.cos(phi), -math.sin(phi), 0.0))

    def at(phi, z, gap):
        r = table_radius(WAIST, 15.0, 1.04, 0.02, phi, z) + 0.0026 + gap
        return Vector((WAIST_C[0], WAIST_C[1], z)) + radial(phi) * r
    turns = 1.05
    n = int(turns * 26) + 1
    phi0 = math.radians(205)  # the right hip, a little behind
    ctrl = []
    for k in range(n):
        u = k / (n - 1)
        phi = phi0 + 2 * math.pi * turns * u
        z = 1.083 + 0.033 * math.cos(phi - math.radians(20)) - 0.01 * u + 0.004 * math.sin(9.0 * u)
        # Looser at the front and sides, where the nurse's waist is fuller than Joe's scaled down
        side = abs(math.cos(phi))
        front = max(0.0, math.sin(phi))
        gap = 0.0105 + 0.0075 * side + 0.004 * front + 0.006 * math.sin(3.1 * phi + 1.2) + 0.002 * math.sin(7.7 * phi)
        gap += jit(0.002)
        ctrl.append(at(phi, z, max(0.0, gap)))
    t0 = (ctrl[1] - ctrl[0]).normalized()
    start = [ctrl[0] - t0 * 0.028 + radial(phi0) * 0.018, ctrl[0] - t0 * 0.011 + radial(phi0) * 0.005]
    phi1 = phi0 + 2 * math.pi * turns
    last, tang = ctrl[-1], (ctrl[-1] - ctrl[-2]).normalized()
    out1 = (tang + radial(phi1) * 0.7).normalized()
    q1 = last + out1 * 0.04 - UP * 0.008
    q2 = q1 + (out1 * 0.7 + radial(phi1) * 0.6 - UP * 0.35).normalized() * 0.05
    q3 = q2 + (radial(phi1) * 0.7 - UP * 0.5 - tang * 0.35).normalized() * 0.05
    pts = catmull(start + ctrl + [q1, q2, q3], 4)
    return resample(pts, STEP * 1.4)


# ---------------------------------------------------------------- build

pieces = wire("Arm", arm_path(), "RightForeArm", "WireVar1", arm_skin)
pieces += wire("Thigh", thigh_path(), "LeftUpLeg", "WireVar2", thigh_skin, every=0.12)
pieces += wire("Waist", waist_path(), "Spine1", "WireVar3", waist_skin, every=0.125)

SKINS = {"RightForeArm#WireVar1": arm_skin, "LeftUpLeg#WireVar2": thigh_skin, "Spine1#WireVar3": waist_skin}
for label, f in SKINS.items():
    report([p for p in pieces if p["zbone"] == label], f)
parts = export(pieces, size=1024)
standin(forearms=True)
mid = ELBOW.lerp(WRIST, 0.55)
zk.previews(SCRIPT, PREVIEWS, Vector((0.0, 0.0, 1.0)), distance=2.6)
close_up("close", mid, (-0.25, -1.0, 0.3), distance=0.36)
close_up("top", mid, (-0.6, -0.2, 0.8), distance=0.36)
close_up("thigh", Vector((0.13, 0.0, 0.74)), (0.6, -1.0, 0.2), distance=0.6)
close_up("waist", Vector((0.0, 0.0, 1.08)), (0.3, -1.0, 0.25), distance=0.9)
close_up("waist_back", Vector((0.0, 0.02, 1.08)), (-0.4, 1.0, 0.25), distance=0.9)
print("[%s] done" % SCRIPT)
