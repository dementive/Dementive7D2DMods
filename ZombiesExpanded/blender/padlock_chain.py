"""Padlock chain (remnant): the zombie was chained up by the wrist and tore loose. Two loops of heavy rusty chain round
the left wrist, locked together with a big laminated-steel padlock whose shackle runs through the bottom link of each
loop, and a short torn length of the chain (about 16 cm, its last link burst open) hanging from the loop beside the
lock. Chunky links (8.4 mm bar, 52 mm long) rusted dark and pitted, rubbed bright where they bear on each other, blood
dried on them where they chafed the wrist; the padlock body's steel plates showing as fine seams, rivets at its
corners, a tarnished brass keyway underneath, the shackle worn bright on top.

The loops rest on the back of the wrist (up and out in the bind pose) and hang loose underneath, pulled down to the
lock. They are sized for a wrist 12% thicker than Joe's (4.0 x 3.0 cm in radius rather than 3.2 x 2.4) so they don't
sink into the fat cop's or the nurse's wrist once the game sizes the part to them; on Joe they ride half a centimeter
proud. The lock and the torn end hang between straight down and along the forearm (22 degrees off straight down in
the bind pose), so they still hang about right when the arm swings in to the side. One part on the forearm bone:
"LeftForeArm#Chain".

    blender -b --factory-startup --python padlock_chain.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "PadlockChain", "padlock_chain", 4421

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

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


def arclen(P, closed=False):
    s = [0.0]
    for i in range(1, len(P)):
        s.append(s[-1] + (P[i] - P[i - 1]).length)
    if closed:
        s.append(s[-1] + (P[0] - P[-1]).length)
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
    """A tube along pts. Records zl = (meters along, x, y across)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T, N, B = frames(P, closed)
    S = arclen(P)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        ring = []
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides
            x, y = radius * math.cos(a), radius * math.sin(a)
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


def sub(g, a, b):
    return g.math("SUBTRACT", a, b)


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
    cav = mul(g, g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.015), 0.4, 1.0), clamp=True), 1.2)
    rm = g.math("MAXIMUM", blooms, mul(g, pits, rust))
    rm = g.math("MAXIMUM", rm, mul(g, cav, rust), clamp=True)
    col = g.mix(rm, iron, rust_col)
    rough = g.mixf(rm, add(g, 0.5, mul(g, tone, 0.15)), 0.9)
    metal = g.mixf(rm, 0.65, 0.05)
    height = add(g, mul(g, g.noise(80.0 * k, detail=5.0, vector=P), 0.15), mul(g, rm, p["height"]))
    if polish:
        st = g.noise(1.0, detail=3.0, vector=mapping(g, P, scale=(18.0 * k, 18.0 * k, 18.0 * k)))
        pm = mul(g, g.ramp(st, 0.55, 0.68), g.ramp(g.edges(0.003), 0.0, 0.4))
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
    return tk.finish(mat, g, col, metal, rough, g.bump(height, bump, 0.0015))


# ---------------------------------------------------------------- the wrist

EL, WR = SK.pos("LeftForeArm"), SK.pos("LeftHand")
AX, LEN = (WR - EL).normalized(), (WR - EL).length  # down the forearm, toward the hand
FRONT = orth(Vector((0.0, -1.0, 0.0)), AX)  # the thumb side
DORSAL = orth(UP, AX)  # the back of the wrist: up and out in the A-pose
PALM = -DORSAL
# Joe's forearm half-widths (thumb-pinky a, back-palm b) at fractions along it, as arm_cast.py measures them
FORE = ((0.0, 0.043, 0.041), (0.15, 0.043, 0.041), (0.4, 0.04, 0.036), (0.7, 0.035, 0.029), (0.9, 0.032, 0.024),
        (1.0, 0.031, 0.023))
FIT = 1.12  # the loops are sized round a wrist this much thicker than Joe's...
MARGIN = 0.0015  # ...plus this


def half_widths(t):
    t = max(0.0, min(1.0, t))
    for (t0, a0, b0), (t1, a1, b1) in zip(FORE, FORE[1:]):
        if t <= t1:
            f = smoothstep(t0, t1, t) if t1 > t0 else 1.0
            return a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
    return FORE[-1][1], FORE[-1][2]


def direction(phi):
    """Around the forearm: phi 0 on the back of the wrist, 90 degrees the thumb side, 180 the palm side."""
    return DORSAL * math.cos(phi) + FRONT * math.sin(phi)


def ellipse_r(a, b, phi):
    return 1.0 / math.sqrt((math.cos(phi) / b) ** 2 + (math.sin(phi) / a) ** 2)


def r_skin(x, phi):
    a, b = half_widths(x / LEN)
    return ellipse_r(a, b, phi)


def r_contact(x, phi):
    a, b = half_widths(x / LEN)
    return ellipse_r(a * FIT + MARGIN, b * FIT + MARGIN, phi)


def polar(p):
    """(x along the forearm, phi round it, distance from its axis) of a point."""
    rel = p - EL
    x = rel.dot(AX)
    q = rel - AX * x
    return x, math.atan2(q.dot(FRONT), q.dot(DORSAL)), q.length


def skin(p):
    """Signed distance to Joe's forearm (an ellipse round the bone, as arm_cast.py assumes), negative inside."""
    x, phi, r = polar(p)
    return r - r_skin(max(0.0, min(LEN, x)), phi)


def contact(p):
    """Signed distance to the wrist the loops are fitted round."""
    x, phi, r = polar(p)
    return r - r_contact(max(0.0, min(LEN, x)), phi)


# Straight down, turned 22 degrees toward the forearm's direction (out to the side): how the lock and the torn end hang
OUTW = orth(AX, UP)
HANG = (-UP * math.cos(math.radians(22.0)) + OUTW * math.sin(math.radians(22.0))).normalized()

# ---------------------------------------------------------------- materials

chain_iron = rusty_iron("ChainIron", seed=3.0, rust=0.7, scale=9.0, base=(0.014, 0.013, 0.012), rust_value=0.24,
                        rust_sat=1.05, grit=0.03, scale_dark=0.7, bump=0.7, gore=0.8, reach=0.013,
                        blood_scale=40.0, noise_scale=8.0, scratches=0.03, edges=0.0)


def laminations(g, P, col, rough, metal, height):
    """The padlock body's stacked steel plates as fine dark seams (zl.y is the height up the body), four rivet
    heads on each face (zl.z the depth across it), grime packed in the seams."""
    u, v, w = attr(g, "zl")
    seam = g.math("ABSOLUTE", sub(g, g.math("FRACT", mul(g, v, 1.0 / 0.0036)), 0.5))
    line = mul(g, g.ramp(seam, 0.4, 0.5), g.ramp(g.noise(300.0, detail=3.0, vector=P), 0.05, 0.3))
    col = g.mix(mul(g, line, 0.9), col, (0.008, 0.006, 0.005))
    rough = g.mixf(line, rough, 0.9)
    height = sub(g, height, mul(g, line, 0.6))
    du = sub(g, g.math("ABSOLUTE", u), 0.0195)
    dv = sub(g, g.math("ABSOLUTE", v), 0.0158)
    dist = g.math("SQRT", add(g, mul(g, du, du), mul(g, dv, dv)))
    face = g.ramp(g.math("ABSOLUTE", w), 0.0115, 0.0135)
    rivet = mul(g, g.ramp(dist, 0.0033, 0.0024), face)
    col = g.mix(rivet, col, (0.07, 0.064, 0.058))
    metal = g.mixf(rivet, metal, 0.7)
    rough = g.mixf(rivet, rough, 0.5)
    height = add(g, height, mul(g, g.ramp(dist, 0.0034, 0.0), mul(g, face, 0.6)))
    return col, rough, metal, height


lock_steel = rusty_iron("LockSteel", seed=5.0, rust=0.35, scale=7.0, base=(0.04, 0.04, 0.041), rust_value=0.22,
                        rust_sat=1.1, grit=0.04, scale_dark=0.45, bump=0.45, extra=laminations, noise_scale=5.0,
                        scratches=0.18, edges=0.25)
shackle_steel = rusty_iron("ShackleSteel", seed=6.0, rust=0.5, scale=6.0, base=(0.026, 0.025, 0.024), rust_value=0.19,
                           rust_sat=1.0, polish=0.08, grit=0.03, scale_dark=0.45, bump=0.35, noise_scale=3.0,
                           scratches=0.05, edges=0.0)


def brass_material(name):
    """The keyway: tarnished brass gone dark brown-olive, grime in the slot and round the rim, the key slot black."""
    mat, g = tk.new_material(name)
    P = seeded(g, 8.0)
    tone = g.noise(220.0, detail=4.0, vector=P)
    col = g.mix(tone, (0.085, 0.06, 0.028), (0.05, 0.036, 0.018))
    tarnish = g.ramp(g.noise(160.0, detail=6.0, roughness=0.65, vector=P), 0.45, 0.7)
    col = g.mix(mul(g, tarnish, 0.8), col, (0.035, 0.032, 0.02))
    u, v, w = attr(g, "zl")
    slot = mul(g, mul(g, g.ramp(g.math("ABSOLUTE", u), 0.0011, 0.0007), g.ramp(g.math("ABSOLUTE", v), 0.0043, 0.0037)),
               g.ramp(w, 0.5, 0.9))
    col = g.mix(slot, col, (0.006, 0.005, 0.004))
    rough = g.mixf(tarnish, 0.42, 0.75)
    metal = g.mixf(add(g, tarnish, slot), 0.85, 0.2)
    col, rough, metal = tk._grit(g, col, rough, metal, 0.05)
    return tk.finish(mat, g, col, metal, rough, g.bump(add(g, mul(g, tone, 0.3), mul(g, slot, -1.0)), 0.4, 0.001))


brass = brass_material("LockBrass")

# ---------------------------------------------------------------- the chain

WIRE = 0.0042  # the links' bar radius (8.4 mm)
LINK_L, LINK_W = 0.052, 0.031  # outside length and width
PITCH = LINK_L - 4 * WIRE  # center to center along the chain


def chain_link(name, center, along, across, open_gap=False):
    """An oval link round `center`, long along `along`, flat in the plane of along and across (8 x 4 bar)."""
    a = along.normalized()
    b = orth(across, a)
    hl, hw = LINK_L / 2 - WIRE, LINK_W / 2 - WIRE
    pts = []
    for k in range(4):  # the two round ends
        t = -math.pi / 2 + math.pi * k / 3
        pts.append(center + a * (hl - hw + hw * math.cos(t)) + b * (hw * math.sin(t)))
    for k in range(4):
        t = math.pi / 2 + math.pi * k / 3
        pts.append(center + a * (-(hl - hw) + hw * math.cos(t)) + b * (hw * math.sin(t)))
    if open_gap:  # burst open where it tore: the far end sprung apart
        pts = pts[2:] + pts[:2]
        pts[0] = pts[0] + b * 0.0045 + a * 0.004
        pts[-1] = pts[-1] - b * 0.003 + a * 0.002
        return tube(name, pts, WIRE, chain_iron, sides=4, caps=True, phase=math.pi / 4)
    return tube(name, pts, WIRE, chain_iron, sides=4, closed=True, phase=math.pi / 4)


# ---------------------------------------------------------------- the padlock (placed first: the loops hang on it)

X1, X2 = LEN - 0.05, LEN - 0.018  # the two loops, from the elbow
XM = (X1 + X2) / 2
BOTTOM = EL + AX * XM + PALM * (r_contact(XM, math.pi) + 0.004)  # under the wrist, between the loops
RS = 0.0175  # the shackle's bend radius (centerline): 2.5 cm inside, 1 cm bar
ROD = 0.005
SA = orth(AX, HANG)  # across the lock, along the arm
FN = SA.cross(HANG)
if FN.y > 0:  # its face toward the front
    FN = -FN
ST = BOTTOM + HANG * 0.012  # the top of the shackle's bend
SC = ST + HANG * RS  # the bend's center
CLEAR = 0.018  # the shackle's legs between the bend and the body
BW, BH, BT = 0.062, 0.051, 0.03  # the body: wide (along the arm), high, thick
BC = SC + HANG * (CLEAR + BH / 2)  # the body's center


def lock_pt(u, v, w):
    """Lock-local (u across along SA, v down along HANG from the body's center, w out of its face) to world."""
    return BC + SA * u + HANG * v + FN * w


def rounded_rect(w, h, r, per=3):
    """The outline of a rounded rectangle (w by h, corners r), counter-clockwise from the right."""
    out = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90.0), (w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 90.0),
                       (-w / 2 + r, -h / 2 + r, 180.0)):
        for k in range(per):
            a = math.radians(a0 + 90.0 * k / (per - 1))
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def lock_body():
    """The laminated body: a rounded block with chamfered faces. zl = lock-local (u, v, w)."""
    outer = rounded_rect(BW, BH, 0.0065)
    inner = rounded_rect(BW - 0.003, BH - 0.003, 0.005)
    bm = bmesh.new()
    vals = []

    def ring(outline, w):
        vs = []
        for u, v in outline:
            vs.append(bm.verts.new(lock_pt(u, v, w)))
            vals.append((u, v, w))
        return vs
    f_in = ring(inner, BT / 2)
    f_out = ring(outer, BT / 2 - 0.0015)
    b_out = ring(outer, -BT / 2 + 0.0015)
    b_in = ring(inner, -BT / 2)
    m = len(outer)
    for r0, r1 in ((f_in, f_out), (f_out, b_out), (b_out, b_in)):
        for k in range(m):
            k1 = (k + 1) % m
            bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    bm.faces.new(f_in)
    bm.faces.new(list(reversed(b_in)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("LockBody", bm, lock_steel)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 35)


def shackle():
    """The U of hardened bar: its bend through the loops' bottom links, the legs down into the body."""
    pts = [SC + SA * RS + HANG * (CLEAR + 0.006)]
    pts.append(SC + SA * RS + HANG * (CLEAR * 0.4))
    for k in range(7):
        th = math.pi * k / 6
        pts.append(SC + (SA * math.cos(th) - HANG * math.sin(th)) * RS)
    pts.append(SC - SA * RS + HANG * (CLEAR * 0.4))
    pts.append(SC - SA * RS + HANG * (CLEAR + 0.006))
    return tube("Shackle", pts, ROD, shackle_steel, sides=5, caps=False)


def keyway():
    """The brass keyway plug in the bottom of the body, its slot across the body."""
    c = lock_pt(0.0, BH / 2, 0.0)
    bm = bmesh.new()
    vals = []
    rows = []
    for depth in (-0.002, 0.0013):
        row = []
        for k in range(8):
            a = 2 * math.pi * k / 8
            u, w = 0.0075 * math.cos(a), 0.0075 * math.sin(a)
            row.append(bm.verts.new(c + SA * u + FN * w + HANG * depth))
            vals.append((w, u, 1.0 if depth > 0 else 0.0))  # slot along u (across the body's thickness)
        rows.append(row)
    for k in range(8):
        k1 = (k + 1) % 8
        bm.faces.new((rows[0][k], rows[0][k1], rows[1][k1], rows[1][k]))
    bm.faces.new(rows[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Keyway", bm, brass)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 50)


def on_shackle(du):
    """The point on the shackle's bend `du` along SA from its middle."""
    du = max(-RS * 0.98, min(RS * 0.98, du))
    return SC + SA * du - HANG * math.sqrt(RS * RS - du * du)


# ---------------------------------------------------------------- the loops


def loop_path(x, sag, bottom_link, samples=180):
    """A closed path for a loop's link centers round the wrist at x: resting on the back of the wrist, hanging slack
    underneath and pulled down to its bottom link on the shackle. phi from the bottom round."""
    pts = []
    base = EL + AX * x + PALM * (r_contact(x, math.pi) + 0.006 + sag)  # where the slack loop's bottom would be
    pull = bottom_link - base
    for i in range(samples):
        phi = math.pi + 2 * math.pi * i / samples
        p = EL + AX * x + direction(phi) * (r_contact(x, phi) + 0.006)
        p = p + PALM * (sag * (1 - math.cos(phi)) / 2)
        d = math.atan2(math.sin(phi - math.pi), math.cos(phi - math.pi))  # angle from the bottom
        w = math.exp(-(d / math.radians(48.0)) ** 2)
        pts.append(p + pull * w)
    return pts


def resample_closed(P, n):
    """n points evenly spaced (by arc length) round a closed polyline, starting at P[0]."""
    S = arclen(P, closed=True)
    out = []
    k = 0
    for i in range(n):
        s = S[-1] * i / n
        while k < len(P) - 1 and S[k + 1] < s:
            k += 1
        a, b = P[k], P[(k + 1) % len(P)]
        t = (s - S[k]) / max(S[k + 1] - S[k], 1e-9)
        out.append(a.lerp(b, t))
    return out


def loop(tag, x, du, links=None):
    """One loop of links round the wrist at x; its bottom link hangs on the shackle du along it. The slack is chosen
    so a whole (even) number of links goes round."""
    bottom = on_shackle(du) - HANG * 0.0026  # the bend's bar rests against the inside of the link
    L0 = arclen(loop_path(x, 0.0, bottom), closed=True)[-1]
    n = links or max(6, 2 * int(round(L0 / PITCH / 2)))
    print("[%s] %s: %.2f links' length round with no slack" % (SCRIPT, tag, L0 / PITCH))
    lo, hi = 0.0, 0.05
    for _ in range(40):  # slack so that the loop is n links round
        mid = (lo + hi) / 2
        if arclen(loop_path(x, mid, bottom), closed=True)[-1] < n * PITCH:
            lo = mid
        else:
            hi = mid
    P = loop_path(x, lo, bottom)
    C = resample_closed(P, n)
    out = []
    centers = []
    for k in range(n):
        c, prev, nxt = C[k], C[k - 1], C[(k + 1) % n]
        along = (nxt - prev).normalized()
        xk, phik, rk = polar(c)
        rad = direction(phik)
        standing = k % 2 == 0  # the bottom link stands across the arm so the shackle's bend goes through it
        if n % 2 and k == n - 1:  # an odd loop: the link before the bottom one twisted half way
            across = (rad + AX).normalized()
            lift = (LINK_W / 2 + WIRE) / 2 + 0.0004
        elif standing:
            across = rad
            lift = LINK_W / 2 + 0.0004
        else:
            across = AX
            lift = WIRE + 0.0004
        gap = contact(c)
        if gap < lift:  # rest on the wrist, not in it
            c = c + rad * (lift - gap)
        link = chain_link("%sLink%d" % (tag, k), c, along, across)
        low = min(contact(v.co) for v in link.data.vertices)
        if low < 0.0004:  # nothing of it inside the fitted wrist
            link.data.transform(Matrix.Translation(rad * (0.0004 - low)))
            c = c + rad * (0.0004 - low)
        centers.append(c)
        out.append(link)
    print("[%s] %s: %d links, slack %.1f cm, %.0f cm round" % (SCRIPT, tag, n, lo * 100, n * PITCH * 100))
    return out, centers


def torn_end(start, n=4):
    """The torn length hanging from a loop link beside the lock: links alternating, hanging along HANG and a little
    back, the last one burst open."""
    back = orth(Vector((0.0, 1.0, 0.0)), HANG)
    out = []
    prev_dir = HANG
    for k in range(n):
        d = (HANG * 1.0 + back * (0.2 - 0.06 * k) - SA * (0.12 + 0.08 * k)).normalized()
        c = start + (prev_dir * 0.5 + d * 0.5).normalized() * (PITCH * 0.5) if k == 0 else start + d * (PITCH * 0.5)
        across = SA if k % 2 == 0 else d.cross(SA)
        out.append(chain_link("TailLink%d" % k, c, d, across, open_gap=(k == n - 1)))
        start = c + d * (PITCH * 0.5)
        prev_dir = d
    return out


pieces = []
loop1, c1 = loop("Loop1", X1, -0.012, links=8)
loop2, c2 = loop("Loop2", X2, 0.012, links=7)
pieces += loop1 + loop2
# The torn end hangs from loop 1's link next to the bottom one on the pinky side, behind the lock
k_tail = 1
tail_from = c1[k_tail] + HANG * 0.006
pieces += torn_end(tail_from)
pieces += [lock_body(), shackle(), keyway()]
for p in pieces:
    depth_attr(p, skin)
    zk.on(p, "LeftForeArm", "Chain")


# ---------------------------------------------------------------- export, checks and previews

def report(objs):
    tris = sum(len(pp.vertices) - 2 for o in objs for pp in o.data.polygons)
    gaps = [(contact(o.matrix_world @ v.co), skin(o.matrix_world @ v.co)) for o in objs if "Link" in o.name
            and "Tail" not in o.name for v in o.data.vertices]
    low = min(g[0] for g in gaps)
    print("[%s] %d tris; loops' nearest %.1f mm off the fitted wrist, %.1f mm off Joe's" % (SCRIPT, tris, low * 1000,
                                                                                         min(g[1] for g in gaps) * 1000))
    zs = [(o.matrix_world @ v.co).z for o in objs for v in o.data.vertices]
    print("[%s] lowest point z %.3f (wrist %.3f)" % (SCRIPT, min(zs), WR.z))


def export(pieces, size=512):
    hidden = [o for o in bpy.context.scene.objects if o.get("zbody") or o.name.startswith("Pre")]
    for o in hidden:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=size)
    for o in hidden:
        o.hide_render = False
    return parts


def close_up(view, target, direction_, distance=0.45, lens=50):
    loc = Vector(target) + Vector(direction_).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


def slim_forearm():
    """The previews' forearm and hand: Joe's arm as assumed (elliptical, tapering) in place of the fat hit box, and a
    flat hand."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(SK.colliders):
        if c["bone"] == "LeftForeArm":
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    bm = bmesh.new()
    n, m = 22, 24
    rows = []
    for i in range(n + 1):
        s = -0.03 + (LEN + 0.03) * i / n
        rows.append([bm.verts.new(EL + AX * s + direction(2 * math.pi * j / m) * r_skin(max(0.0, s), 2 * math.pi * j / m))
                     for j in range(m)])
    for a, b in zip(rows, rows[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bm.faces.new(rows[0])
    bm.faces.new(list(reversed(rows[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tk.smooth(tk.mesh_object("PreForeArm", bm, mat), 60)
    # the hand: a flattened capsule, palm toward PALM, thumb side FRONT
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
    for v in bm.verts:
        v.co = WR + AX * (0.07 + v.co.z * 0.085) + FRONT * (v.co.x * 0.042) + DORSAL * (v.co.y * 0.017)
    tk.smooth(tk.mesh_object("PreHand", bm, mat), 60)
    for i, o in enumerate([o for o in bpy.data.objects if o.name.startswith("BodyLeftHand")]):
        bpy.data.objects.remove(o)


report(pieces)
parts = export(pieces)
slim_forearm()
focus = EL + AX * XM + PALM * 0.03
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.75)
close_up("close", focus, FRONT * 1.0 + DORSAL * 0.3 - AX * 0.25, distance=0.34)
close_up("top", focus, DORSAL * 1.0 + FRONT * 0.4, distance=0.34)
close_up("under", focus + HANG * 0.03, PALM * 0.8 + FRONT * 0.6 + AX * 0.2, distance=0.36)
close_up("back_close", focus, -FRONT * 1.0 + DORSAL * 0.3, distance=0.36)
print("[%s] done" % SCRIPT)
