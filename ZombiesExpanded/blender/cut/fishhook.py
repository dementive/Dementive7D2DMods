"""Fishhook (remnant): a big (8 cm) treble hook caught in the upper outside of the right forearm, one prong dug in to
past its bend, the shank standing off the skin with its eye pulled down by the line; a clinch knot with a trimmed tag at
the eye, then 22 cm of faded braided line, a little curl still in it, down to a battered balsa minnow plug hanging nose up:
a sun-faded perch pattern, chipped to the primer and the wood, tooth-gouged, a cloudy chewed diving lip, a rusty
treble on its belly hanger and another on its tail. The hook's wire is black-bronzed steel gone rusty, blood dried on
it and down the shank where it comes out of the skin, a lump of clot where the prong goes in.

The hook rides the forearm bone: one part, "RightForeArm#Hook". The line and lure hang plumb with the body upright
in the bind pose (arms out and down), clear of the arm and hand. The crown sits on Joe's real forearm (measured from
the Unity renders, slimmer than its hit box) and the buried prong reaches 3 cm past the hit box.

    blender -b --factory-startup --python fishhook.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "Fishhook", "fishhook", 7741

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


def entry(origin, d, f=sdf, maxd=0.8, step=0.0005):
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
    """A tube along pts. radius: a number, a list (one per point) or fn(i) -> r or (rx, ry). Records zl =
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
    return tk.smooth(obj, smooth if smooth is not None else max(60.0, 360.0 / sides + 15.0))


def catmull(ctrl, per=6):
    """A smooth path through the control points."""
    P = [Vector(c) for c in ctrl]
    E_ = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(E_) - 2):
        p0, p1, p2, p3 = E_[i - 1], E_[i], E_[i + 1], E_[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-1])
    return out


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


def band(g, x, lo, hi, soft=0.0004):
    """1 between lo and hi, soft edges."""
    return mul(g, g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def seeded(g, seed):
    """World position shifted by a seed, for noise that differs per material."""
    return mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))


def gore_mask(g, P, reach=0.035, amount=1.0, runs=0.6, dots=0.6, scale=16.0):
    """How bloody a point is from its distance to the skin (zd.x): soaked at and under the skin, ragged out to
    about `reach`, with runs and spatter beyond it."""
    d = attr(g, "zd")[0]
    edge = add(g, d, mul(g, g.math("SUBTRACT", g.noise(scale, detail=6.0, roughness=0.65, vector=P), 0.5), reach * 1.4))
    m = g.ramp(edge, reach, reach * 0.75)
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
    # Where it dried thin it has flaked, and the surface shows through in specks
    flake = mul(g, g.ramp(g.noise(scale * 5.0, detail=4.0, vector=P), 0.6, 0.68), g.math("SUBTRACT", 1.0, thick))
    mask = mul(g, mask, g.math("SUBTRACT", 1.0, mul(g, flake, 0.75)))
    bc = g.mix(thick, (0.022, 0.0052, 0.0036), (0.0075, 0.0025, 0.0018))
    crust = g.ramp(g.noise(scale * 3.0, detail=4.0, vector=P), 0.55, 0.75)
    bc = g.mix(mul(g, crust, 0.55), bc, (0.02, 0.0095, 0.0055))
    col = g.mix(mask, col, bc)
    rough = g.mixf(mask, rough, g.mixf(thick, 0.62, 0.4))
    height = add(g, height, mul(g, mask, add(g, 0.1, mul(g, thick, 0.35))))
    return col, rough, height


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood stuck to whatever went through it: wet dark red, black clots, pale shreds of fat
    and tissue."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    n1 = g.noise(30.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.01, 0.0018, 0.0015), (0.038, 0.0065, 0.005))
    fat = mul(g, g.ramp(g.noise(60.0, detail=4.0, distortion=1.2, vector=P), 0.68, 0.73), 0.6)
    col = g.mix(fat, col, (0.06, 0.036, 0.024))
    clot = g.ramp(voronoi(g, P, 140.0), 0.25, 0.1)
    col = g.mix(mul(g, clot, 0.5), col, (0.03, 0.004, 0.003))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.35, 0.55)
    height = add(g, mul(g, n1, 0.6), mul(g, fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


# ---------------------------------------------------------------- export, checks and previews

def report(parts, f=sdf):
    """Triangles, bounds and how deep each part goes into the skin (f < 0 inside)."""
    groups = {}
    for p in parts:
        groups.setdefault(p["zbone"], []).append(p)
    total = 0
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
        print("[%s] %-22s %5d tris  bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)  deepest %.1f cm, %d/%d verts inside"
              % ((SCRIPT, label, tris) + tuple(lo) + tuple(hi) + (deep * 100, inside, nv)))
    print("[%s] total %d tris" % (SCRIPT, total))


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



def taper_sdf(a, b, ra, rb):
    """Distance to a round limb from a (radius ra) to b (radius rb), negative inside."""
    def f(p):
        q, t = seg_closest(p, a, b)
        return (p - q).length - (ra + (rb - ra) * t)
    return f


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
    for i in range(m):
        k = (i + 1) % m
        f = bm.faces.new((top[k], top[i], bot[i], bot[k]))
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, face)
    obj.data.materials.append(edge)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, smooth)


def ring_tube(name, center, u, v, radius, wire, mat, segs=8, sides=4, phase=0.0):
    """A closed wire ring (a hook's eye, a split ring) round `center` in the plane of u and v."""
    pts = [center + (u * math.cos(phase + 2 * math.pi * k / segs) + v * math.sin(phase + 2 * math.pi * k / segs)) * radius
           for k in range(segs)]
    return tube(name, pts, wire, mat, sides=sides, closed=True, smooth=70)


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


def slim_forearms():
    """Swaps the forearm hit boxes of the preview stand-in for the real forearms' size, previews only."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(SK.colliders):
        if c["bone"] in ("LeftForeArm", "RightForeArm") and ("Body_%d" % i) in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    for side in ("Left", "Right"):
        limb("Pre%sForeArm" % side, SK.pos(side + "ForeArm"), SK.pos(side + "Hand"), R_ELBOW, R_WRIST, mat)


def rot(v, axis, deg):
    return (Matrix.Rotation(math.radians(deg), 3, axis) @ v).normalized()


# ---------------------------------------------------------------- materials

def hook_steel(name, seed, rust=0.5, gore=0.0, reach=0.02, base=(0.03, 0.028, 0.026), polish=0.4):
    """Hook wire: black-bronzed steel gone dull, rust blooming at the bends and pitting the shank, rubbed to bare
    steel along the points, grimy; dried blood from the skin outward (gore, from zd)."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    p = tk.photo(g, "rust_coarse_01", 9.0, (seed * 0.31, 0.5, seed * 0.23))
    tone = g.noise(40.0, detail=4.0, vector=P)
    col = g.mix(tone, base, tk._darker(g, base, 0.55))
    rough = add(g, 0.45, mul(g, tone, 0.15))
    metal = g.value(0.7)
    rc = tk.grade(g, p["color"], 0.45, 0.3)
    rm = g.ramp(g.noise(55.0, detail=6.0, roughness=0.65, distortion=0.5, vector=P), 0.66 - 0.3 * rust, 0.72 - 0.3 * rust)
    rm = g.math("MAXIMUM", rm, mul(g, g.ramp(tk._luma(g, p["color"]), 0.2, 0.08), rust))
    col = g.mix(rm, col, rc)
    rough = g.mixf(rm, rough, 0.88)
    metal = g.mixf(rm, metal, 0.05)
    height = add(g, mul(g, g.noise(400.0, detail=4.0, vector=P), 0.2), mul(g, rm, p["height"]))
    if polish:
        st = g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(160.0, 160.0, 160.0))), 0.55, 0.7)
        pm = mul(g, mul(g, st, g.math("SUBTRACT", 1.0, rm, clamp=True)), polish)
        col = g.mix(pm, col, (0.15, 0.145, 0.14))
        rough = g.mixf(pm, rough, 0.35)
        metal = g.mixf(pm, metal, 0.95)
    dirt = mul(g, g.ramp(g.noise(30.0, detail=5.0, vector=P), 0.55, 0.72), 0.8)
    col = g.mix(dirt, col, (0.028, 0.022, 0.016))
    rough = g.mixf(dirt, rough, 0.9)
    metal = g.mixf(dirt, metal, 0.0)
    if gore:
        bm_ = gore_mask(g, P, reach, gore, runs=0.8, dots=0.6, scale=40.0)
        col, rough, height = dried_blood(g, col, rough, height, bm_, P, scale=30.0)
        metal = g.mixf(bm_, metal, 0.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.001))


def braid(name, seed):
    """Braided line, once moss green, faded to a dirty grey-olive: the diagonal weave along zl, fuzz, grime, dark
    dried blood near the hook (zd)."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    P = seeded(g, seed)
    th = g.math("DIVIDE", g.math("ARCTAN2", y, x), 2 * math.pi)
    w1 = g.math("FRACT", add(g, g.math("DIVIDE", s, 0.003), th))
    w2 = g.math("FRACT", g.math("SUBTRACT", g.math("DIVIDE", s, 0.003), th))
    weave = g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", w1, 0.5)), 0.3, 0.5),
                   g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", w2, 0.5)), 0.3, 0.5))
    tone = g.noise(25.0, detail=4.0, vector=P)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.02, 0.022, 0.014), (0.045, 0.046, 0.032))
    col = g.mix(mul(g, weave, 0.6), col, (0.01, 0.011, 0.008))
    dirt = g.ramp(g.noise(12.0, detail=5.0, vector=P), 0.5, 0.7)
    col = g.mix(mul(g, dirt, 0.7), col, (0.045, 0.036, 0.024))
    rough = add(g, 0.78, mul(g, weave, 0.12))
    height = mul(g, weave, -0.6)
    bm_ = gore_mask(g, P, 0.03, 1.0, runs=0.9, dots=0.8, scale=60.0)
    col, rough, height = dried_blood(g, col, rough, height, bm_, P, scale=40.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.001))


def lure_paint(name, seed):
    """A balsa minnow plug in a perch pattern, sun-faded and battered: dark olive back, dull khaki flanks with dark
    bars and a faint scale net, a once-orange belly gone to dirty tan, a painted eye gone yellow; the clear coat
    worn dull, paint chipped to grey primer and water-darkened wood at the nose, belly and edges, tooth gouges,
    mud in the gouges, a smear of dried blood. zl = (along from the nose, across, up toward the back)."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    L = combine(g, s, x, y)
    P = seeded(g, seed)
    hy = g.math("DIVIDE", y, add(g, attr(g, "zh")[0], 0.0001))  # -1 at the belly, +1 along the back
    side_ = g.ramp(g.math("ABSOLUTE", x), 0.002, 0.0035)
    back = g.ramp(hy, 0.15, 0.6)
    belly = g.ramp(hy, -0.25, -0.7)
    col = g.mix(back, (0.02, 0.019, 0.01), (0.0075, 0.0082, 0.0042))
    col = g.mix(belly, col, (0.03, 0.023, 0.014))
    bars = g.ramp(g.math("SINE", add(g, mul(g, s, 2 * math.pi / 0.021), mul(g, g.noise(30.0, detail=3.0, vector=P), 2.0))), 0.35, 0.7)
    bars = mul(g, bars, mul(g, g.ramp(hy, -0.5, 0.0), g.ramp(s, 0.02, 0.03)))
    col = g.mix(mul(g, bars, 0.8), col, (0.009, 0.01, 0.006))
    scales = g.ramp(voronoi(g, mapping(g, L, scale=(1.0, 1.4, 1.0)), 420.0, "DISTANCE_TO_EDGE"), 0.06, 0.0)
    col = g.mix(mul(g, mul(g, scales, 0.45), g.math("SUBTRACT", 1.0, belly)), col, tk._darker(g, col, 0.5))
    # A painted gill arc behind the eye
    gx = g.math("SUBTRACT", s, add(g, 0.027, mul(g, mul(g, y, y), 60.0)))
    gill = mul(g, mul(g, band(g, gx, -0.0007, 0.0007, 0.0003), g.ramp(hy, 0.75, 0.5)), side_)
    col = g.mix(mul(g, gill, 0.8), col, (0.012, 0.01, 0.008))
    # The painted eye
    er = g.math("SQRT", add(g, mul(g, g.math("SUBTRACT", s, 0.0145), g.math("SUBTRACT", s, 0.0145)),
                            mul(g, g.math("SUBTRACT", y, 0.0016), g.math("SUBTRACT", y, 0.0016))))
    side = g.ramp(g.math("ABSOLUTE", x), 0.0025, 0.004)
    eye = mul(g, g.ramp(er, 0.0047, 0.0041), side)
    pupil = mul(g, g.ramp(er, 0.0023, 0.0018), side)
    col = g.mix(eye, col, (0.06, 0.047, 0.018))
    col = g.mix(pupil, col, (0.008, 0.008, 0.008))
    rough = g.mixf(eye, add(g, 0.5, mul(g, g.noise(20.0, detail=3.0, vector=P), 0.15)), 0.3)
    height = mul(g, g.noise(300.0, detail=4.0, vector=P), 0.05)
    # Sun-faded and chalky toward the back and the nose
    fade = mul(g, g.ramp(g.noise(5.0, detail=4.0, vector=P), 0.4, 0.7), 0.5)
    col = g.mix(fade, col, tk.grade(g, col, 0.45, 1.12))
    rough = g.mixf(fade, rough, 0.72)
    # Chipped paint: grey primer, and dark water-soaked balsa where it's gone through
    chip_n = g.noise(70.0, detail=6.0, roughness=0.7, vector=P)
    edge = g.ramp(g.edges(0.0015), 0.05, 0.25)
    nose = g.ramp(s, 0.012, 0.0)
    wearz = g.math("MAXIMUM", g.math("MAXIMUM", edge, nose), mul(g, belly, 0.5))
    chips = g.ramp(add(g, chip_n, mul(g, wearz, 0.3)), 0.6, 0.63)
    deep = g.ramp(add(g, chip_n, mul(g, wearz, 0.3)), 0.7, 0.73)
    col = g.mix(chips, col, (0.034, 0.031, 0.026))
    col = g.mix(deep, col, (0.02, 0.015, 0.009))
    rough = g.mixf(chips, rough, 0.8)
    height = add(g, height, mul(g, add(g, chips, deep), -0.5))
    # Tooth gouges: short dark slashes across the body
    gouge = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, L, scale=(900.0, 120.0, 120.0), rot=(0.4, 0.0, 0.3)))
    gouge = mul(g, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", gouge, 0.5)), 0.03, 0.0),
                g.ramp(g.noise(60.0, detail=2.0, vector=P), 0.58, 0.64))
    col = g.mix(gouge, col, (0.025, 0.02, 0.014))
    height = add(g, height, mul(g, gouge, -1.0))
    dirt = g.math("MAXIMUM", tk._grime(g, 0.7), mul(g, g.ramp(g.noise(9.0, detail=6.0, distortion=0.6, vector=P), 0.6, 0.72), 0.7))
    col = g.mix(mul(g, dirt, 0.8), col, (0.022, 0.018, 0.012))
    rough = g.mixf(dirt, rough, 0.9)
    sm = mul(g, mul(g, g.ramp(g.noise(6.0, detail=6.0, distortion=0.8, vector=P), 0.66, 0.71), 0.9), g.ramp(s, 0.03, 0.045))
    col, rough, height = dried_blood(g, col, rough, height, sm, P, scale=40.0)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.12)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.001))


def lip_plastic(name, seed):
    """The diving lip: clear plastic gone cloudy and smoky with scratches and grit (opaque, dark), its edge chewed."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    tone = g.noise(40.0, detail=4.0, vector=P)
    col = g.mix(tone, (0.04, 0.036, 0.026), (0.075, 0.066, 0.045))
    sc = None
    for k, rot_ in enumerate(((0.3, 0.9, 0.2), (1.1, 0.2, 1.4), (2.0, 1.3, 0.6))):
        n = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, P, scale=(400.0, 400.0, 40.0), rot=rot_, loc=(0.3 * k, 0.1, 0.5)))
        line = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.012, 0.0)
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    col = g.mix(mul(g, sc, 0.7), col, (0.12, 0.11, 0.095))
    rough = g.mixf(sc, add(g, 0.3, mul(g, tone, 0.1)), 0.6)
    dirt = g.math("MAXIMUM", tk._grime(g, 0.8), mul(g, g.ramp(g.noise(14.0, detail=5.0, vector=P), 0.55, 0.7), 0.7))
    col = g.mix(dirt, col, (0.03, 0.025, 0.018))
    rough = g.mixf(dirt, rough, 0.85)
    height = mul(g, sc, -0.6)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.001))


steel = hook_steel("HookSteel", 1.0, rust=0.55, gore=1.0, reach=0.016)
small_steel = hook_steel("TrebleSteel", 2.0, rust=0.75, polish=0.2, base=(0.035, 0.03, 0.026))
line_mat = braid("Braid", 3.0)
paint = lure_paint("LurePaint", 4.0)
lip_mat = lip_plastic("LureLip", 5.0)
flesh = gore_flesh("Gore", 6.0)


# ---------------------------------------------------------------- the forearm

ELBOW, WRIST = SK.pos("RightForeArm"), SK.pos("RightHand")
A = (WRIST - ELBOW).normalized()  # along the forearm, toward the hand
N1 = orth(UP, A)  # the outside of the forearm (up and out in the bind pose)
N2 = A.cross(N1)  # the back of the forearm
R_ELBOW, R_WRIST = 0.046, 0.033  # Joe's real forearm (from the renders in Unity), slimmer than its 5 cm hit box
ARM = taper_sdf(ELBOW, WRIST, R_ELBOW, R_WRIST)
S_HOOK = 0.05  # along the forearm from the elbow (well up from the hand, so the lure doesn't hang by it)
THETA = 55.0  # round from the outside toward the back
NRM = (N1 * math.cos(math.radians(THETA)) + N2 * math.sin(math.radians(THETA))).normalized()
R_CROWN = R_ELBOW + (R_WRIST - R_ELBOW) * S_HOOK / (WRIST - ELBOW).length + 0.003  # the crown 3 mm off the skin
CROWN = ELBOW + A * S_HOOK + NRM * R_CROWN
DOWN = Vector((0.0, 0.0, -1.0))

# ---------------------------------------------------------------- the treble in the arm

GAP, SHANK, POINT, WIRE, EYE_R = 0.0258, 0.0515, 0.0336, 0.00155, 0.0058  # a big 8 cm treble
H = (orth(DOWN, NRM) + NRM * 0.45).normalized()  # crown to eye: hanging down, standing 24 degrees off the skin
P0 = orth(-NRM, H)  # the prong dug into the arm
EYE = CROWN + H * (SHANK + EYE_R)


def treble(prefix, crown, h, p0, gap, shank, point, wire, eye_r, mat, sides=5, bend=7, barb=True, eye_segs=8,
           eye_sides=5, pt_segs=3, shank_rings=3):
    """A treble hook: the shank from the crown along h to the eye; three prongs at 120 degrees round it, the first
    toward p0, each bending away from the eye and round, its point coming back toward the eye `gap` out from the
    shank, sharpened and barbed on the inside."""
    out = []
    w = h.cross(p0).normalized()
    for k in range(3):
        a = 2 * math.pi * k / 3
        p = (p0 * math.cos(a) + w * math.sin(a)).normalized()
        pts = []
        for i in range(bend):
            phi = math.pi + math.pi * i / (bend - 1)
            pts.append(crown + p * (gap / 2 + gap / 2 * math.cos(phi)) + h * (gap / 2 * math.sin(phi) * 1.08))
        for i in range(1, pt_segs + 1):
            t = i / pt_segs
            pts.append(crown + p * (gap - 0.14 * gap * t * t) + h * (point * t))
        n = len(pts)
        taper = (1.0, 0.82, 0.5, 0.12) if pt_segs == 3 else (1.0, 0.7, 0.12)
        rad = [wire * (1.0 if i < n - pt_segs else taper[i - n + pt_segs + 1]) for i in range(n)]
        out.append(tube("%sProng%d" % (prefix, k), pts, rad, mat, sides=sides, caps=True, phase=0.3))
        if barb:  # a small wedge on the inside of the point, swept back from the tip
            sc = gap / 0.019
            yb = point * 0.7
            base = crown + p * (gap - 0.14 * gap * 0.7 ** 2) + h * yb
            poly = [(0.0, 0.0012 * sc), (0.0, -0.0022 * sc), (-wire - 0.0024 * sc, -0.0036 * sc)]
            out.append(prism("%sBarb%d" % (prefix, k), poly, wire * 1.1, base, p, h, mat, mat))
    sp = [crown - h * wire * 0.5, crown + h * (shank * 0.5), crown + h * shank]
    out.append(tube(prefix + "Shank", sp if shank_rings == 3 else [sp[0], sp[2]], wire * 1.08, mat, sides=sides,
                    caps=True))
    out.append(ring_tube(prefix + "Eye", crown + h * (shank + eye_r), h, w, eye_r, wire, mat, segs=eye_segs,
                         sides=eye_sides, phase=math.pi))
    return out


def wound_gore():
    """A lump of clot and torn skin round the buried prong where it goes in (just past the crown), riding up onto
    the bend."""
    w = H.cross(P0).normalized()
    t = 0.0
    while t < math.pi and ARM(CROWN + P0 * (GAP / 2 - GAP / 2 * math.cos(t)) - H * (GAP / 2 * math.sin(t) * 1.08)) > 0.0:
        t += 0.02
    mouth = CROWN + P0 * (GAP / 2 - GAP / 2 * math.cos(t)) - H * (GAP / 2 * math.sin(t) * 1.08)
    print("[%s] the buried prong goes in %.1f mm from the crown" % (SCRIPT, (mouth - CROWN).length * 1000))
    return [blob("Clot", mouth + NRM * 0.0012 - P0 * 0.001, (0.0058, 0.005, 0.0036), (P0.cross(NRM).normalized(), P0, NRM),
                 flesh, seed=1.7, lump=0.45, seg=(7, 5))]


# ---------------------------------------------------------------- line and lure

L_LINE = 0.22
LINE_R = 0.0011


def line():
    """The knot at the eye with its trimmed tag, then the line hanging from it, a little curl left in it, to the
    lure's nose eye."""
    top = EYE + H * EYE_R * 0.9
    w = H.cross(P0).normalized()
    side = orth(w, DOWN)
    fwd = DOWN.cross(side)
    knot_pts = [top - H * 0.001, top + DOWN * 0.003, top + DOWN * 0.007, top + DOWN * 0.011]
    knot = tube("Knot", knot_pts, [LINE_R * 1.1, LINE_R * 2.1, LINE_R * 1.9, LINE_R * 1.1], line_mat, sides=5,
                caps=True, twist=60.0)
    tag = tube("Tag", [top + DOWN * 0.004, top + DOWN * 0.006 + side * 0.006 - H * 0.002,
                       top + DOWN * 0.005 + side * 0.012 - H * 0.003], [LINE_R, LINE_R * 0.9, LINE_R * 0.5],
               line_mat, sides=3, caps=True)
    start = top + DOWN * 0.011
    ctrl = [start]
    for k, (dz, ds, df) in enumerate(((0.03, 0.004, 0.002), (0.07, 0.009, -0.003), (0.105, 0.004, -0.006),
                                      (0.13, -0.004, -0.002), (0.17, -0.002, 0.004), (0.205, 0.003, 0.002),
                                      (L_LINE, 0.0, 0.0))):
        ctrl.append(start + DOWN * dz + side * ds + fwd * df)
    pts = catmull(ctrl, 2)
    hang = tube("Line", pts, LINE_R, line_mat, sides=4, caps=True, s0=0.011)
    return [knot, tag, hang], pts[-1]


LURE_LEN, LURE_H, LURE_W = 0.12, 0.026, 0.0165
PROF = [(0.0, 0.0, 0.0, 0.0), (0.004, 0.42, 0.42, -0.08), (0.013, 0.7, 0.68, -0.06), (0.026, 0.88, 0.86, -0.02),
        (0.043, 0.98, 0.97, 0.0), (0.062, 1.0, 1.0, 0.01), (0.081, 0.9, 0.88, 0.02), (0.096, 0.72, 0.66, 0.02),
        (0.108, 0.52, 0.44, 0.02), (0.1155, 0.36, 0.28, 0.02), (LURE_LEN, 0.3, 0.22, 0.02)]  # (along, height, width, rise)


def lure(nose_eye):
    """A minnow plug hanging nose up from the line, a little canted, its broad side to the front and back: the body,
    the diving lip, the nose eye the line is tied to, and two trebles hanging off the belly and tail hangers."""
    lat = rot(Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)), -25.0)  # its broad side to the front and back
    belly = DOWN.cross(lat).normalized()
    if belly.x > 0:  # the belly toward the outside
        belly = -belly
    # Canted, the tail swung toward its back: the belly weight and trebles hang under the nose eye
    cant = math.radians(11.0)
    a = (DOWN * math.cos(cant) - belly * math.sin(cant)).normalized()
    belly = orth(belly, a)
    lat = a.cross(belly).normalized()
    dors = -belly
    nose = nose_eye + a * 0.0019  # the screw eye's shank in the nose

    def at_(t, x, y):
        return nose + a * t + lat * x + dors * y

    # The body: an elliptic loft, fans at the nose and the tail
    sides = 10
    bm = bmesh.new()
    vals, hts, rings = [], [], []
    for t, hh, ww, rise in PROF[1:]:
        ring = []
        for j in range(sides):
            ang = 2 * math.pi * j / sides
            x, y = ww * LURE_W / 2 * math.cos(ang), hh * LURE_H / 2 * math.sin(ang) + rise * LURE_H
            ring.append(bm.verts.new(at_(t, x, y)))
            vals.append((t, x, y - rise * LURE_H))
            hts.append((hh * LURE_H / 2, 0.0, 0.0))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
    c0 = bm.verts.new(at_(0.0, 0.0, -0.08 * LURE_H))
    vals.append((0.0, 0.0, 0.0))
    hts.append((0.42 * LURE_H / 2, 0.0, 0.0))
    for j in range(sides):
        bm.faces.new((rings[0][(j + 1) % sides], rings[0][j], c0))
    c1 = bm.verts.new(at_(LURE_LEN + 0.0015, 0.0, 0.02 * LURE_H))
    vals.append((LURE_LEN, 0.0, 0.0))
    hts.append((0.3 * LURE_H / 2, 0.0, 0.0))
    for j in range(sides):
        bm.faces.new((rings[-1][j], rings[-1][(j + 1) % sides], c1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    body = tk.mesh_object("LureBody", bm, paint)
    set_attr(body, "zl", vals)
    set_attr(body, "zh", hts)
    tk.smooth(body, 60)
    out = [body]
    # The diving lip, out of the chin, angled forward and down
    q = (-a * 0.72 + belly * 0.7).normalized()
    root = at_(0.009, 0.0, -0.36 * LURE_H)
    outline = [(-0.0085, -0.002), (0.0085, -0.002), (0.0102, 0.012), (0.0082, 0.02), (0.003, 0.0235),
               (-0.003, 0.0235), (-0.0082, 0.02), (-0.0102, 0.012)]
    out.append(prism("Lip", outline, 0.0017, root, lat, q, lip_mat, lip_mat, smooth=25))
    # The nose eye, through the line's end
    out.append(ring_tube("NoseEye", nose_eye, a, dors, 0.0028, 0.0006, small_steel, segs=6, sides=3))
    # Belly and tail hangers with a treble on each, hanging plumb
    up = -DOWN
    tw = []
    belly_hanger = at_(0.042, 0.0, -0.49 * LURE_H - 0.0011)
    tail_hanger = at_(LURE_LEN + 0.0028, 0.0, 0.02 * LURE_H)
    for k, (hanger, spin) in enumerate(((belly_hanger, 0.0), (tail_hanger, 40.0))):
        out.append(ring_tube("Hanger%d" % k, hanger, a, belly if k == 0 else dors, 0.0026, 0.00055, small_steel,
                             segs=6, sides=3))
        eye_c = hanger + DOWN * 0.0042
        p0 = rot(orth(belly, up), up, spin)
        g_, sh, pt, wi, er = 0.0095, 0.017, 0.012, 0.00068, 0.0022
        crown = eye_c - up * (sh + er)
        tw += treble("T%d" % k, crown, up, p0, g_, sh, pt, wi, er, small_steel, sides=4, bend=5, barb=False,
                     eye_segs=6, eye_sides=3, pt_segs=2, shank_rings=2)
    center = nose + a * (LURE_LEN / 2)
    return out + tw, center


hook = treble("Hook", CROWN, H, P0, GAP, SHANK, POINT, WIRE, EYE_R, steel)
gore_bits = wound_gore()
line_parts, line_end = line()
lure_parts, LURE_C = lure(line_end + DOWN * 0.0026)
pieces = hook + gore_bits + line_parts + lure_parts
for p in pieces:
    depth_attr(p, ARM)
    zk.on(p, "RightForeArm", "Hook")

report(pieces, ARM)
deep = min(ARM(v.co) for p in hook for v in p.data.vertices)
deep_box = min(sdf(v.co) for p in hook for v in p.data.vertices)
clear = min(sdf(v.co) for p in line_parts[2:] + lure_parts for v in p.data.vertices)
print("[%s] crown (%.3f, %.3f, %.3f), eye (%.3f, %.3f, %.3f); the buried prong goes %.1f cm under the real forearm's "
      "skin, %.1f cm past its hit box" % ((SCRIPT,) + tuple(CROWN) + tuple(EYE) + (-deep * 100, -deep_box * 100)))
print("[%s] the line and lure clear the stand-in by %.1f cm; the lure's tail at z %.3f" % (
    SCRIPT, clear * 100, min(v.co.z for p in lure_parts for v in p.data.vertices)))
parts = export(pieces)
slim_forearms()
focus = CROWN + DOWN * 0.13
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.95)
close_up("hook", CROWN + H * 0.015, (NRM * 1.0 + DOWN * 0.3 + N1 * 0.4), distance=0.2)
close_up("lure", LURE_C, (-0.3, -1.0, 0.15), distance=0.3)
close_up("back", CROWN + DOWN * 0.12, (-0.2, 1.0, 0.15), distance=0.6)
close_up("front", CROWN + DOWN * 0.12, (-0.2, -1.0, 0.15), distance=0.6)
close_up("outside", CROWN + DOWN * 0.1, (-1.0, 0.25, 0.3), distance=0.65)
print("[%s] done" % SCRIPT)
