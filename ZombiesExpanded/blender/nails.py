"""Nails (remnant): a burst of framing nails from a nail gun, fired in a rough line down the outside of the left arm,
four through the short sleeve of the upper arm and five in the bare forearm. Paper-taped clipped-head (D-head)
framing nails, the heads left standing 1.3 to 1.9 cm proud where the gun wasn't pressed home, two of them hit bone and
bent over, one still wearing a torn scrap of its paper collation strip under the head. Bright steel gone to dark rust,
the driver's strike worn dull on the heads in the sleeve, a ragged mound of torn flesh and clot round every entry,
blood soaked up the shanks.

The heads are bigger than real (13 mm across, shanks 4.2 mm) so the row reads a few meters away. The line runs down the
outside of the arm turned well toward the front (the outside faces up and out in the bind pose), so the heads face a
zombie's front; two sit nearer the outside and stand out of the arm's outline. Every shank runs 4 cm past Joe's skin
(or sleeve), so no tip shows on slimmer arms. Joe's forearm as arm_cast.py measures it (4.3 x 4.1 cm in radius below
the elbow to 3.1 x 2.3 at the wrist), with his real skin about 5 mm outside that as the renders on vanilla Joe show;
the upper arm is the outside of his sleeve, which comes down nearly to the elbow. On the fat cop the arm is fatter than
its hit boxes say, so the nails sit deeper and the sleeve ones mostly vanish into it. Parts "LeftArm#Nails" and
"LeftForeArm#Nails" (the game sizes them to the limb's thickness only).

    blender -b --factory-startup --python nails.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "Nails", "nails", 7719

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


def tube(name, pts, radius, mat, sides=6, closed=False, caps=True, phase=0.0, smooth=None):
    """A tube along pts (radius a number or one per point). Records zl = (meters along, x, y across)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T, N, B = frames(P, closed)
    S = arclen(P)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        r = radius[i] if isinstance(radius, (list, tuple)) else radius
        ring = []
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides
            x, y = r * math.cos(a), r * math.sin(a)
            ring.append(bm.verts.new(P[i] + N[i] * x + B[i] * y))
            vals.append((S[i], x, y))
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


def band(name, pts, side_dirs, widths, thick, mat):
    """A thin flat strip along pts, widths[i] along side_dirs[i] (offset so its top edge follows the path), `thick`
    through. zl = (meters along, across, side)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    Tn, _, _ = frames(P)
    S = arclen(P)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        W = orth(Vector(side_dirs[i]), Tn[i])
        Nn = Tn[i].cross(W)
        lo, hi = widths[i]
        ring = []
        for sw, st in ((lo, -1), (hi, -1), (hi, 1), (lo, 1)):
            ring.append(bm.verts.new(P[i] + W * sw + Nn * (st * thick / 2)))
            vals.append((S[i], sw, st))
        rings.append(ring)
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 40)


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
    bc = g.mix(thick, (0.05, 0.007, 0.006), (0.018, 0.003, 0.002))  # dark and dull: the game's shader shows red brighter
    col = g.mix(mask, col, bc)
    rough = g.mixf(mask, rough, g.mixf(thick, 0.6, 0.38))
    height = add(g, height, mul(g, mask, add(g, 0.1, mul(g, thick, 0.35))))
    return col, rough, height


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood stuck round the nail where it went in: wet dark red, black clots, pale shreds of
    fat and tissue."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    n1 = g.noise(60.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.007, 0.0018, 0.0014), (0.026, 0.0045, 0.0035))
    fat = mul(g, g.ramp(g.noise(110.0, detail=4.0, distortion=1.2, vector=P), 0.68, 0.73), 0.35)
    col = g.mix(fat, col, (0.05, 0.032, 0.024))
    clot = g.ramp(voronoi(g, P, 260.0), 0.25, 0.1)
    col = g.mix(mul(g, clot, 0.7), col, (0.006, 0.002, 0.0015))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.42, 0.68)
    height = add(g, mul(g, n1, 0.6), mul(g, fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.001))


def rusty_iron(name, seed=0.0, rust=0.6, scale=2.5, base=(0.05, 0.046, 0.042), rust_value=0.5, polish=0.0,
               gore=0.0, reach=0.035, grit=0.5, scale_dark=0.4, grime=0.6, bump=0.35, extra=None, blood_scale=11.0,
               rust_sat=0.78, noise_scale=1.0, scratches=0.2, edges=0.15):
    """Old iron and steel: dark mill scale, coarse rust in blooms and crevices (the photo, toned down), pitted,
    rubbed bright in places (polish), grimy and dusty, bloodied near the skin (gore, from zd). noise_scale shrinks
    the blooms and mill scale for small parts; scratches and edges are _grit's light scratches and worn edges
    (keep them low on thin bars, whose every corner counts as an edge)."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    k = noise_scale
    p = tk.photo(g, "rust_coarse_01", scale, (seed * 0.31, 0.5 + seed * 0.17, seed * 0.23))
    tone = g.noise(6.0 * k, detail=4.0, vector=P)
    iron = g.mix(tone, base, tk._darker(g, base, 0.6))
    scale_m = mul(g, g.ramp(g.noise(9.0 * k, detail=6.0, roughness=0.6, vector=P), 0.45, 0.6), scale_dark)
    iron = g.mix(scale_m, iron, (0.022, 0.021, 0.02))
    rust_col = tk.grade(g, p["color"], rust_sat, rust_value)
    rust_col = g.mix(g.ramp(tk._luma(g, p["color"]), 0.12, 0.03), rust_col, (0.035, 0.016, 0.008))
    blooms = g.ramp(g.noise(4.5 * k, detail=8.0, roughness=0.65, distortion=0.5, vector=P), 0.66 - 0.32 * rust,
                    0.72 - 0.32 * rust)
    pits = g.ramp(tk._luma(g, p["color"]), 0.16 + 0.1 * rust, 0.08)
    cav = mul(g, g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.01), 0.4, 1.0), clamp=True), 1.2)
    rm = g.math("MAXIMUM", blooms, mul(g, pits, rust))
    rm = g.math("MAXIMUM", rm, mul(g, cav, rust), clamp=True)
    col = g.mix(rm, iron, rust_col)
    rough = g.mixf(rm, add(g, 0.5, mul(g, tone, 0.15)), 0.9)
    metal = g.mixf(rm, 0.65, 0.05)
    height = add(g, mul(g, g.noise(80.0 * k, detail=5.0, vector=P), 0.15), mul(g, rm, p["height"]))
    if polish:
        st = g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(18.0 * k, 18.0 * k, 18.0 * k)))
        pm = mul(g, g.ramp(st, 0.55, 0.68), g.ramp(g.edges(0.002), 0.0, 0.4))
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
    col, rough, metal = tk._grit(g, col, rough, metal, grit, scratches=scratches, edges=edges)
    if gore:  # after the dust, so blood isn't dusted over
        bm_ = gore_mask(g, P, reach, gore, scale=blood_scale * 1.5)
        col, rough, height = dried_blood(g, col, rough, height, bm_, P, scale=blood_scale)
        metal = g.mixf(bm_, metal, 0.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, bump, 0.001))


def struck_heads(g, P, col, rough, metal, height):
    """The tops of the heads (zh.x = 1) worn to dull grey steel by the gun's driver blade, a dent ring round it."""
    top = attr(g, "zh")[0]
    worn = mul(g, g.ramp(top, 0.55, 0.95), g.ramp(g.noise(160.0, detail=4.0, vector=P), 0.3, 0.6))
    col = g.mix(mul(g, worn, 0.85), col, (0.085, 0.08, 0.075))
    rough = g.mixf(worn, rough, 0.5)
    metal = g.mixf(worn, metal, 0.75)
    height = add(g, height, mul(g, g.ramp(top, 0.7, 0.85), -0.25))
    return col, rough, metal, height


def kraft_paper(name):
    """The scrap of the nails' paper collation tape: brown kraft paper, fibrous, grimy, blood wicked up into it from
    the bottom edge and dried dark."""
    mat, g = tk.new_material(name)
    P = seeded(g, 4.0)
    fib = g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(900.0, 900.0, 140.0), rot=(0.4, 0.2, 0.9)))
    tone = g.noise(90.0, detail=4.0, vector=P)
    col = g.mix(tone, (0.105, 0.064, 0.033), (0.07, 0.043, 0.023))
    col = g.mix(mul(g, g.ramp(fib, 0.45, 0.7), 0.5), col, (0.05, 0.032, 0.018))
    dirt = mul(g, g.ramp(g.noise(140.0, detail=5.0, vector=P), 0.45, 0.7), 0.7)
    col = g.mix(dirt, col, (0.035, 0.028, 0.02))
    rough = g.mixf(dirt, 0.82, 0.9)
    height = mul(g, fib, 0.3)
    m = gore_mask(g, P, reach=0.02, amount=1.0, runs=0.3, dots=0.5, scale=60.0)
    col, rough, height = dried_blood(g, col, rough, height, m, P, scale=70.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.25, 0.001))


# ---------------------------------------------------------------- export, checks and previews

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


# ---------------------------------------------------------------- the arm

SH, EL, WR = SK.pos("LeftArm"), SK.pos("LeftForeArm"), SK.pos("LeftHand")
AXU, LU = (EL - SH).normalized(), (EL - SH).length  # down the upper arm
AXF, LF = (WR - EL).normalized(), (WR - EL).length  # down the forearm (in the bind pose in line with the upper arm)
FRONT = orth(Vector((0.0, -1.0, 0.0)), AXF)  # the thumb side
DORSAL = orth(UP, AXF)  # the outside of the arm: up and out in the A-pose


def direction(phi):
    """Around the arm: phi 0 on the outside (up and out), +90 degrees toward the front."""
    return DORSAL * math.cos(phi) + FRONT * math.sin(phi)


# Half-widths (front-back a, out-in b) at fractions along each bone: the forearm as arm_cast.py measures Joe's (the
# renders on vanilla Joe put his real skin about 5 mm outside it on the outside of the forearm: REAL below); the upper
# arm is the outside of Joe's short sleeve, which comes down nearly to the elbow
FORE = ((0.0, 0.043, 0.041), (0.15, 0.043, 0.041), (0.4, 0.04, 0.036), (0.7, 0.035, 0.029), (0.9, 0.032, 0.024),
        (1.0, 0.031, 0.023))
UPPER = ((0.0, 0.057, 0.057), (0.3, 0.056, 0.056), (0.6, 0.055, 0.055), (0.85, 0.053, 0.053), (1.0, 0.05, 0.05))
REAL = {"LeftArm": 0.0, "LeftForeArm": 0.005}


def half_widths(table, t):
    t = max(0.0, min(1.0, t))
    for (t0, a0, b0), (t1, a1, b1) in zip(table, table[1:]):
        if t <= t1:
            f = smoothstep(t0, t1, t) if t1 > t0 else 1.0
            return a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
    return table[-1][1], table[-1][2]


LIMBS = {"LeftArm": (SH, AXU, LU, UPPER), "LeftForeArm": (EL, AXF, LF, FORE)}


def r_skin(bone, s, phi):
    a, b = half_widths(LIMBS[bone][3], s / LIMBS[bone][2])
    return 1.0 / math.sqrt((math.cos(phi) / b) ** 2 + (math.sin(phi) / a) ** 2) + REAL[bone]


def skin_of(bone):
    """Signed distance to Joe's arm on that bone as assumed above (negative inside)."""
    start, ax, ln, _ = LIMBS[bone]

    def f(p):
        s = (p - start).dot(ax)
        q = p - start - ax * s
        phi = math.atan2(q.dot(FRONT), q.dot(DORSAL))
        return q.length - r_skin(bone, max(0.0, min(ln, s)), phi)
    return f


# ---------------------------------------------------------------- materials

steel = rusty_iron("NailSteel", seed=1.0, rust=0.85, scale=7.0, base=(0.018, 0.017, 0.016), rust_value=0.18,
                   rust_sat=1.0, gore=1.0, reach=0.016, grit=0.02, scale_dark=0.55, bump=0.4, blood_scale=70.0,
                   extra=struck_heads, noise_scale=6.0, scratches=0.03, edges=0.0)
flesh = gore_flesh("NailGore", 3.0)
paper = kraft_paper("CollationPaper")

# ---------------------------------------------------------------- the nails

SHANK_R = 0.0021  # 4.2 mm (real 3.3)
HEAD_R = 0.0065  # 13 mm across (real 7 to 8): the row has to read a few meters off
HEAD_T = 0.0017
DEPTH = 0.04  # past Joe's skin


def d_head(name, under, n, roll, strike=1.0):
    """A clipped (D) head: a disc 13 mm across with one side cut flat near the shank, its underside centered on the
    shank at `under`, facing n, a low dome on top. zh = strike on the top face (how worn by the driver it is)."""
    n = n.normalized()
    u = orth(Vector((0.3, 0.5, 0.8)), n)
    u = Matrix.Rotation(roll, 3, n) @ u
    v = n.cross(u)
    off = 0.0012  # the shank sits off-center, toward the flat
    clip = math.acos(-(off + 0.0036) / HEAD_R)
    outline = []
    m = 10
    for k in range(m):
        a = -clip + 2 * clip * k / (m - 1)
        outline.append((off + HEAD_R * math.cos(a), HEAD_R * math.sin(a)))
    bm = bmesh.new()
    bot = [bm.verts.new(under + u * x + v * y) for x, y in outline]
    rim = [bm.verts.new(under + u * x * 0.97 + v * y * 0.97 + n * HEAD_T) for x, y in outline]
    top = bm.verts.new(under + u * off + n * (HEAD_T + 0.0007))
    for k in range(m):
        k1 = (k + 1) % m
        bm.faces.new((bot[k], bot[k1], rim[k1], rim[k]))
        bm.faces.new((rim[k], rim[k1], top))
    bm.faces.new(list(reversed(bot)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, steel)
    vals = [(0.0, 0.0, 0.0)] * m + [(0.75 * strike, 0.0, 0.0)] * m + [(strike, 0.0, 0.0)]
    set_attr(obj, "zh", vals)
    return tk.smooth(obj, 50)


def nail(tag, bone, s, phi, tilt_along, tilt_side, proud, roll, bend=None, scrap=False, clot=1.0, strike=1.0):
    """One nail in `bone` s meters from its start, phi degrees round from the outside toward the front, tilted
    (degrees) along the arm and round it, its head's underside `proud` out from Joe's skin (or sleeve). bend (degrees:
    0 down the arm toward the hand, 90 round it, 180 up toward the shoulder) bends it over just above the skin."""
    start, ax, ln, _ = LIMBS[bone]
    f = skin_of(bone)
    ph = math.radians(phi)
    rad = direction(ph)
    O = start + ax * s
    E = O + rad * r_skin(bone, s, ph)  # where it goes into Joe
    head_r = r_skin(bone, s, ph) + proud
    N = (rad * math.cos(math.radians(tilt_along)) - ax * math.sin(math.radians(tilt_along))).normalized()
    N = Matrix.Rotation(math.radians(tilt_side), 3, ax) @ N
    out = []
    deep = E - N * DEPTH
    if bend is None:
        # Along N until the head's underside is head_r from the axis
        t = (head_r - r_skin(bone, s, ph)) / max(0.5, N.dot(rad))
        under = E + N * t
        out.append(tube(tag + "Shank", [deep, under + N * 0.0003], SHANK_R, steel, sides=6, caps=False))
        head_n = N
    else:
        bd = orth(ax * math.cos(math.radians(bend)) + rad.cross(ax) * math.sin(math.radians(bend)), N)
        b0 = E + N * ((head_r - 0.004 - r_skin(bone, s, ph)) / max(0.5, N.dot(rad)))
        rb = 0.0042
        pts = [deep, E, b0]
        for k in range(1, 5):
            th = math.radians(84.0) * k / 4
            pts.append(b0 + N * (rb * math.sin(th)) + bd * (rb * (1 - math.cos(th))))
        th = math.radians(84.0)
        head_n = (N * math.cos(th) + bd * math.sin(th)).normalized()
        under = pts[-1] + head_n * 0.011
        pts.append(under + head_n * 0.0003)
        out.append(tube(tag + "Shank", pts, SHANK_R, steel, sides=6, caps=False))
    out.append(d_head(tag + "Head", under, head_n, roll, strike))
    if clot:
        out.append(crater(tag + "Clot", E, N, rad, ax, clot, seed=s * 31.0 + phi))
    if scrap:
        out.append(paper_scrap(tag + "Paper", under - N * 0.0035, N, rad, ax))
    for o in out:
        depth_attr(o, f)
        zk.on(o, bone, "Nails")
    hr = (under - O).length
    print("[%s] %s: head %.1f cm off the axis (%.1f cm over Joe's assumed skin, %.1f over the hit box)"
          % (SCRIPT, tag, hr * 100, (hr - r_skin(bone, s, ph)) * 100, (hr - SK.radius(bone)) * 100))
    return out


def crater(name, E, N, rad, ax, size, seed=0.0):
    """The wound round a nail: a ragged mound of torn flesh and clot pushed up round the shank, sloping down into
    the skin (its outer edge 4 mm under Joe's, to cover how far his real skin strays) with an uneven, lobed rim."""
    w1 = orth(ax, rad)
    w2 = rad.cross(w1)
    m = 9
    # (radius, height over Joe's skin) from the shank out
    rings = ((SHANK_R * 0.97, 0.0032), (0.0038 * size, 0.0024), (0.006 * size, 0.0004), (0.008 * size, -0.0042))
    bm = bmesh.new()
    rows = []
    lobes = [1.0 + 0.5 * noise.noise(Vector((math.cos(2 * math.pi * j / m) * 1.7 + seed, math.sin(2 * math.pi * j / m) * 1.7,
                                                    seed * 0.37))) + jit(0.18) for j in range(m)]
    for i, (r, h) in enumerate(rings):
        c = E + N * (h / max(0.5, N.dot(rad)))
        row = []
        for j in range(m):
            a = 2 * math.pi * (j + 0.37 * i + jit(0.18) * (i > 0)) / m
            d = w1 * math.cos(a) + w2 * math.sin(a)
            q = Vector((math.cos(a) * 3.0 + seed, math.sin(a) * 3.0, i * 0.7 + seed * 0.3))
            k = 1.0 if i == 0 else max(0.55, lobes[j] * (1.0 + 0.25 * noise.noise(q)) + jit(0.1))
            dh = 0.0 if i == 0 else (0.0016 * noise.noise(q + Vector((5.1, 1.3, 2.2))) + jit(0.0006)) * (1.4 if i == 1 else 1.0)
            row.append(bm.verts.new(c + d * (r * k) + rad * dh))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:  # outward (away from the arm)
        if f.normal.dot(rad) < 0:
            f.normal_flip()
    return tk.smooth(tk.mesh_object(name, bm, flesh), 70)


def paper_scrap(name, top, n, rad, ax):
    """A torn scrap of the collation tape still round the shank under the head: wrapped half round it, the torn
    end flapping out to one side and drooping."""
    w = orth(ax, n)
    side = n.cross(w)
    pts = []
    for k in range(5):  # half round the shank
        a = math.pi * (0.15 + 0.85 * k / 4)
        pts.append(top + (w * math.cos(a) + side * math.sin(a)) * (SHANK_R + 0.0004))
    tail = pts[-1]
    d = (-w * 0.9 - n * 0.25 + side * 0.15).normalized()
    for k in range(1, 6):
        pts.append(tail + d * (0.0044 * k) - n * (0.0011 * k * k / 5) + side * (0.0008 * math.sin(k * 1.7)))
    widths = []
    for k in range(len(pts)):  # torn ragged at the far end
        lo = -0.0105 + (0.0005 if k % 2 else 0.0) + (0.0025 if k == len(pts) - 1 else 0.0)
        hi = 0.0 - (0.0022 if k == len(pts) - 1 else (0.0006 if k == len(pts) - 2 else 0.0))
        widths.append((lo, hi))
    return band(name, pts, [n] * len(pts), widths, 0.0006, paper)


# Upper arm (s from the shoulder joint, 26.5 cm long): two through the sleeve, two in the bare arm above the elbow.
# Mostly turned well toward the front (the heads face a zombie coming at you), a couple nearer the outside to stand
# out of the arm's outline. The heads in the sleeve are struck bright (they show against the cloth), the ones in the
# skin darker (they show against it).
# (tag, s, phi, tilt along (+ head toward the shoulder), tilt round, proud, D-head roll, bend, scrap, clot, strike)
UP_NAILS = [
    ("U1", 0.112, 46, 10, -8, 0.016, 0.4, None, False, 0.65, 1.0),
    ("U2", 0.150, 26, -14, 9, 0.017, 2.1, None, False, 0.65, 1.0),
    ("U3", 0.186, 50, 5, 12, 0.013, 4.0, 150, False, 0.7, 1.0),
    ("U4", 0.222, 38, -19, -5, 0.016, 1.2, None, False, 0.65, 1.0),
]
# Forearm (s from the elbow, 28 cm long)
FORE_NAILS = [
    ("F1", 0.040, 50, 16, 5, 0.018, 3.3, None, False, 1.0, 0.55),
    ("F2", 0.081, 42, -9, -10, 0.019, 5.2, None, True, 1.0, 0.55),
    ("F3", 0.122, 54, 20, 7, 0.016, 0.7, -35, False, 1.1, 0.55),
    ("F4", 0.163, 26, -12, -8, 0.018, 2.6, None, False, 0.95, 0.55),
    ("F5", 0.201, 48, 6, 10, 0.017, 4.6, None, False, 0.9, 0.55),
]

pieces = []
for spec in UP_NAILS:
    pieces += nail(spec[0], "LeftArm", *spec[1:])
for spec in FORE_NAILS:
    pieces += nail(spec[0], "LeftForeArm", *spec[1:])


def report(parts):
    groups = {}
    for p in parts:
        groups.setdefault(p["zbone"], []).append(p)
    total = 0
    for label, objs in groups.items():
        bone = label.split("#")[0]
        f = skin_of(bone)
        start, ax, ln, _ = LIMBS[bone]
        tris = sum(len(pp.vertices) - 2 for o in objs for pp in o.data.polygons)
        total += tris
        deep = min(f(o.matrix_world @ v.co) for o in objs for v in o.data.vertices)
        hit = min(((o.matrix_world @ v.co) - start - ax * ((o.matrix_world @ v.co) - start).dot(ax)).length
                  for o in objs for v in o.data.vertices)
        print("[%s] %-20s %5d tris, deepest %.1f cm inside Joe's assumed skin (%.1f cm from the axis)"
              % (SCRIPT, label, tris, -deep * 100, hit * 100))
    print("[%s] total %d tris" % (SCRIPT, total))


report(pieces)
parts = export(pieces)


def slim_arm():
    """The previews' arm: the assumed upper arm and forearm (elliptical, tapering) in place of the fat hit boxes."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(SK.colliders):
        if c["bone"] in LIMBS:
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    for bone, (start, ax, ln, table) in LIMBS.items():
        bm = bmesh.new()
        n, m = 20, 24
        rows = []
        for i in range(n + 1):
            s = -0.02 + (ln + 0.04) * i / n
            rows.append([bm.verts.new(start + ax * s + direction(2 * math.pi * j / m) * r_skin(bone, max(0.0, min(ln, s)),
                                                                                             2 * math.pi * j / m))
                         for j in range(m)])
        for a, b in zip(rows, rows[1:]):
            for j in range(m):
                bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
        bm.faces.new(rows[0])
        bm.faces.new(list(reversed(rows[-1])))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        tk.smooth(tk.mesh_object("Pre" + bone, bm, mat), 60)


slim_arm()
zk.previews(SCRIPT, PREVIEWS, EL, distance=1.0)
close_up("close", EL + DORSAL * 0.03, FRONT * 0.6 + DORSAL * 0.8 - AXF * 0.1, distance=0.42)
close_up("fore", EL + AXF * 0.12 + DORSAL * 0.04, FRONT * 1.0 + DORSAL * 0.35, distance=0.26)
close_up("upper", SH + AXU * 0.16 + DORSAL * 0.05, FRONT * 1.0 + DORSAL * 0.5, distance=0.26)
close_up("back", EL + DORSAL * 0.03, -FRONT * 1.0 + DORSAL * 0.4, distance=0.5)
print("[%s] done" % SCRIPT)
