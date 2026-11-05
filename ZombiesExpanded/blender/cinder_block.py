"""CinderBlock (rare showpiece): somebody's makeshift ball and chain. A rusty leg iron locked round the right ankle (a
flat bar band hammered a little out of round, its hinge on the outside, a keyed lock box on the front, a forged eye on
the back with a ring through it), a metre of heavy rusty chain, and at its end a cracked, chipped grey cinder block
with the chain wrapped round its near end through one of its holes and padlocked back on itself.

Three parts on the shin bone. "RightLeg#Cuff" rides the leg. The game detaches the other two and lays them on the
ground behind the zombie: "RightLeg#ChainDrag" is exactly 1.0 m of chain, straight and horizontal, from its pivot
(where its first link bears on the ring) straight back along +Y, which the game stretches and aims at the block;
"RightLeg#BlockDrag" is the block lying on a face shell (its cores running across it), the wrapped chain and the
padlock, its pivot where the chain's last link bears on the padlock's shackle, 10 cm above the block's bottom face
(exactly 1.0 m behind the chain's pivot). In the previews the chain just sticks straight out behind the leg with the
block at its end.

    blender -b --factory-startup --python cinder_block.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "CinderBlock", "cinder_block", 5303

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




# ---------------------------------------------------------------- more helpers

def catmull(ctrl, per=8):
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


def resample(P, n):
    """n points evenly spaced by arc length along an open polyline, both ends kept."""
    S = arclen(P)
    out, k = [], 0
    for i in range(n):
        s = S[-1] * i / (n - 1)
        while k < len(S) - 2 and S[k + 1] < s:
            k += 1
        t = (s - S[k]) / max(S[k + 1] - S[k], 1e-9)
        out.append(P[k].lerp(P[k + 1], min(1.0, max(0.0, t))))
    return out


def hull(name, pts, mat):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.mesh_object(name, bm, mat)


def boolean(obj, cutter, op="DIFFERENCE"):
    mod = obj.modifiers.new("Bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.material_mode = "TRANSFER"
    mod.object = cutter
    tk.apply_modifiers(obj)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return obj


def ring_mesh(name, center, a, b, R, r, mat, nmaj=12, nmin=5, phase=0.0, fn=None):
    """A closed ring (torus) round `center` in the plane of unit vectors a and b. zl = (meters round, x, y)."""
    pts = []
    for i in range(nmaj):
        t = 2 * math.pi * i / nmaj
        rr = R * (fn(t) if fn else 1.0)
        pts.append(center + (a * math.cos(t) + b * math.sin(t)) * rr)
    return tube(name, pts, r, mat, sides=nmin, closed=True, phase=phase)


# ---------------------------------------------------------------- the ankle

def leg_capsule():
    for c in SK.colliders:
        if c["bone"] == "RightLeg":
            ax = Vector((0.0, 0.0, 0.0))
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            return SK.point("RightLeg", ctr - ax * half), SK.point("RightLeg", ctr + ax * half), c["radius"]


LEG_A, LEG_B, LEG_R = leg_capsule()
LA = (LEG_B - LEG_A).normalized()  # up the shin


def leg_sdf(p):
    ab = LEG_B - LEG_A
    t = max(0.0, min(1.0, (p - LEG_A).dot(ab) / ab.length_squared))
    return (p - (LEG_A + ab * t)).length - LEG_R


CUFF_Z = 0.205  # low on the shin, clear of the top of the foot (the stand-in's ankle ball reaches z 0.165)
_t = (CUFF_Z - LEG_A.z) / (LEG_B.z - LEG_A.z)
C = LEG_A.lerp(LEG_B, _t) + Vector((0.0, -0.006, 0.0))  # a little forward of the hit box, toward the shin bone
NC = (LA + Vector((0.0, -math.tan(math.radians(5.0)), 0.0))).normalized()  # the cuff's axis: it sags 5 deg at the front
E_BACK = orth(Vector((0.0, 1.0, 0.0)), NC)
E_OUT = NC.cross(E_BACK).normalized()  # the outside of the right ankle (-X)
R_IN, T_BAND, H_BAND = 0.06, 0.0055, 0.024


def cuff_dir(a):
    """Round the cuff from the back (a = 0) toward the outside."""
    return E_BACK * math.cos(a) + E_OUT * math.sin(a)


cuff_iron = rusty_iron("CuffIron", seed=11.0, rust=0.75, scale=7.0, base=(0.02, 0.019, 0.018), rust_value=0.26,
                       rust_sat=1.0, polish=0.12, gore=0.7, reach=0.014, grit=0.06, scale_dark=0.6, bump=0.6,
                       blood_scale=30.0, noise_scale=5.0, scratches=0.08, edges=0.1)


def band():
    """The leg iron's band: a flat bar ring, a little out of round where it was hammered shut."""
    prof = [(0.0, -H_BAND / 2 + 0.001), (T_BAND * 0.5, -H_BAND / 2), (T_BAND, -H_BAND / 2 + 0.0012),
            (T_BAND, H_BAND / 2 - 0.0012), (T_BAND * 0.5, H_BAND / 2), (0.0, H_BAND / 2 - 0.001)]
    n = 22
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = R_IN * (1.0 + 0.035 * math.sin(2 * a + 0.6) + 0.012 * math.sin(5 * a))
        d = cuff_dir(a)
        ring = []
        for r, h in prof:
            ring.append(bm.verts.new(C + d * (rr + r) + NC * h))
            vals.append((R_IN * a, r, h))
        rings.append(ring)
    m = len(prof)
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Band", bm, cuff_iron)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 40)


def band_point(a, out=0.0):
    rr = R_IN * (1.0 + 0.035 * math.sin(2 * a + 0.6) + 0.012 * math.sin(5 * a))
    return C + cuff_dir(a) * (rr + T_BAND + out)


def hinge():
    """The hinge knuckle on the outside of the ankle, its pin's peened ends."""
    a = math.pi / 2
    c = band_point(a, 0.0035)
    pts = [c - NC * (H_BAND / 2 + 0.003), c - NC * 0.004, c + NC * 0.004, c + NC * (H_BAND / 2 + 0.003)]
    out = [tube("Hinge", pts, 0.0056, cuff_iron, sides=8, phase=0.2)]
    for s in (-1, 1):
        out.append(tube("HingePin%d" % s, [c + NC * s * (H_BAND / 2 + 0.002), c + NC * s * (H_BAND / 2 + 0.0055)],
                        0.0032, cuff_iron, sides=6))
    return out


def rounded_rect(w, h, r, per=3):
    out = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90.0), (w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 90.0),
                       (-w / 2 + r, -h / 2 + r, 180.0)):
        for k in range(per):
            a = math.radians(a0 + 90.0 * k / (per - 1))
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def slab_box(name, center, eu, ev, ew, w, h, t, mat, r=0.003, chamfer=0.0012):
    """A rounded box: w along eu, h along ev, t along ew (its faces chamfered). zl = (u, v, w)."""
    outer = rounded_rect(w, h, r)
    inner = rounded_rect(w - 2 * chamfer, h - 2 * chamfer, max(r - chamfer, 0.0005))
    bm = bmesh.new()
    vals = []

    def ring(outline, z):
        vs = []
        for u, v in outline:
            vs.append(bm.verts.new(center + eu * u + ev * v + ew * z))
            vals.append((u, v, z))
        return vs
    f_in = ring(inner, t / 2)
    f_out = ring(outer, t / 2 - chamfer)
    b_out = ring(outer, -t / 2 + chamfer)
    b_in = ring(inner, -t / 2)
    m = len(outer)
    for r0, r1 in ((f_in, f_out), (f_out, b_out), (b_out, b_in)):
        for k in range(m):
            k1 = (k + 1) % m
            bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    bm.faces.new(f_in)
    bm.faces.new(list(reversed(b_in)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, "zl", vals)
    return tk.smooth(obj, 35)


def keyhole_marks(g, P, col, rough, metal, height):
    """The lock box's keyhole: a dark slot with a round top in the middle of its outer face (zl.z > 0)."""
    u, v, w = attr(g, "zl")
    face = g.ramp(w, 0.004, 0.006)
    top = g.math("SQRT", add(g, mul(g, u, u), mul(g, sub(g, v, 0.002), sub(g, v, 0.002))))
    hole = g.math("MAXIMUM", g.ramp(top, 0.0024, 0.0017),
                  mul(g, g.ramp(g.math("ABSOLUTE", u), 0.0011, 0.0007), mul(g, g.ramp(v, 0.003, 0.0), g.ramp(v, -0.006, -0.005))))
    hole = mul(g, hole, face)
    col = g.mix(hole, col, (0.004, 0.003, 0.003))
    rough = g.mixf(hole, rough, 0.9)
    height = sub(g, height, mul(g, hole, 1.5))
    return col, rough, metal, height


lockbox_iron = rusty_iron("CuffLockIron", seed=12.0, rust=0.6, scale=7.0, base=(0.024, 0.023, 0.022), rust_value=0.25,
                          rust_sat=1.0, polish=0.08, grit=0.05, scale_dark=0.5, bump=0.5, extra=keyhole_marks,
                          noise_scale=5.0, scratches=0.1, edges=0.2)


def lock_box():
    """The leg iron's lock on the front of the ankle, toward the inside."""
    a = math.radians(-150.0)  # from the back round past the inside to the front
    d = cuff_dir(a)
    c = band_point(a, 0.0062)
    tang = NC.cross(d).normalized()
    return slab_box("LockBox", c, tang, NC, d, 0.034, 0.027, 0.0125, lockbox_iron, r=0.004, chamfer=0.0015)


R_EYE, W_EYE = 0.0095, 0.0042  # the forged eye on the back (centerline radius, wire)
R_RING, W_RING = 0.0165, 0.0048  # the ring through it
W_LINK = 0.0055  # the chain: 11 mm bar, 50 mm inside
N_LINKS = 20
L_IN = 1.0 / N_LINKS  # inside length = pitch: 20 links make exactly 1.0 m
HL = L_IN / 2 + W_LINK  # a link's centerline half length
HW = 0.0095 + W_LINK  # and half width (19 mm inside)


def eye_and_ring():
    """The eye forged on the back of the band (flat, in the cuff's plane) and the ring through it (standing)."""
    back = band_point(0.0)
    ec = back + E_BACK * (R_EYE - 0.0045)
    eye = ring_mesh("Eye", ec, E_BACK, E_OUT, R_EYE, W_EYE, cuff_iron, nmaj=10, nmin=5, phase=0.3)
    y_eye_far = (ec + E_BACK * R_EYE).y
    rc = Vector((ec.x, y_eye_far - (W_EYE + W_RING) + R_RING, ec.z))
    ring = ring_mesh("Ring", rc, Vector((0.0, 1.0, 0.0)), UP, R_RING, W_RING, cuff_iron, nmaj=12, nmin=5, phase=0.4)
    pivot = Vector((rc.x, rc.y + R_RING - W_RING, rc.z))  # where the chain's first link bears on the ring
    return [eye, ring], pivot


chain_iron = rusty_iron("ChainIron", seed=3.0, rust=0.75, scale=8.0, base=(0.016, 0.015, 0.014), rust_value=0.25,
                        rust_sat=1.0, polish=0.14, grit=0.12, scale_dark=0.7, bump=0.7, noise_scale=6.0,
                        scratches=0.03, edges=0.0)


def chain_link(name, center, along, across, mat=None):
    """An oval link round `center`, long along `along`, flat in the plane of along and across (8 x 4 bar)."""
    a = along.normalized()
    b = orth(across, a)
    pts = []
    for k in range(4):
        t = -math.pi / 2 + math.pi * k / 3
        pts.append(center + a * (HL - HW + HW * math.cos(t)) + b * (HW * math.sin(t)))
    for k in range(4):
        t = math.pi / 2 + math.pi * k / 3
        pts.append(center + a * (-(HL - HW) + HW * math.cos(t)) + b * (HW * math.sin(t)))
    return tube(name, pts, W_LINK, mat or chain_iron, sides=4, closed=True, phase=math.pi / 4)


# ---------------------------------------------------------------- the chain (dragged: straight back along +Y)

def drag_chain(pivot):
    """N_LINKS links from the ring straight back along +Y, flat and standing in turn (the first flat, through the
    standing ring; the last standing, so the padlock's shackle goes through it)."""
    out = []
    Y = Vector((0.0, 1.0, 0.0))
    for k in range(N_LINKS):
        c = pivot + Y * (L_IN / 2 + k * L_IN)
        roll = math.radians(jit(7.0))
        flat = Vector((math.cos(roll), 0.0, math.sin(roll)))
        standing = Vector((-math.sin(roll), 0.0, math.cos(roll)))
        out.append(chain_link("Link%d" % k, c, Y, standing if k % 2 else flat))
    return out


# ---------------------------------------------------------------- the block and its padlock

BL, BW, BH = 0.397, 0.194, 0.194  # length (along the drag), width (the cores run across it), height
SHELL, WEB, MID = 0.032, 0.032, 0.026
CORE = (BL - 2 * WEB - MID) / 2
GAP = 0.045  # from the padlock's shackle to the block's near end


def concrete_block(name, seed, fresh=False):
    """A cinder block's face: coarse grey concrete full of dark cinder grit and pores, grime in the hollows, mud
    and green-brown dirt toward the ground, rust stains where the chain rubs. fresh: the pale, rough faces of a
    new break."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    tone = g.noise(6.0, detail=6.0, roughness=0.6, vector=P)
    col = g.mix(tone, (0.04, 0.039, 0.036), (0.068, 0.066, 0.061))
    if fresh:
        col = g.mix(tone, (0.075, 0.072, 0.066), (0.11, 0.105, 0.097))
    cells = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(cells, "Scale", 160.0)
    g.links.new(mapping(g, P, loc=(0.2, 0.4, 0.1)), cells.inputs["Vector"])
    grit = mul(g, g.ramp(tk._sock(cells.outputs, "Distance"), 0.35, 0.22), g.ramp(g.noise(9.0, vector=P), 0.3, 0.55))
    grit_col = g.mix(g.separate(tk._sock(cells.outputs, "Color"))[0], (0.018, 0.017, 0.016), (0.05, 0.045, 0.04))
    col = g.mix(grit, col, grit_col)
    pores = mul(g, g.ramp(voronoi(g, mapping(g, P, loc=(1.1, 0.3, 0.6)), 300.0), 0.14, 0.05),
                g.ramp(g.noise(5.0, vector=P), 0.3, 0.6))
    col = g.mix(pores, col, (0.012, 0.011, 0.01))
    rough = add(g, 0.88, mul(g, tone, 0.08))
    height = add(g, mul(g, tone, 0.3), add(g, mul(g, grit, 0.25), mul(g, pores, -1.0)))
    zrel = g.separate(g.coords())[2]
    if not fresh:
        mud = mul(g, g.ramp(zrel, Z_BLOCK + 0.05, Z_BLOCK + 0.004),
                  g.ramp(g.noise(7.0, detail=6.0, roughness=0.65, vector=P, distortion=0.6), 0.3, 0.55))
        col = g.mix(mul(g, mud, 0.85), col, g.mix(g.noise(20.0, vector=P), (0.03, 0.024, 0.016), (0.05, 0.045, 0.028)))
        rough = g.mixf(mud, rough, 0.95)
        stain = mul(g, g.ramp(g.noise(3.0, detail=6.0, vector=mapping(g, P, scale=(1.0, 1.0, 3.0)), distortion=0.4),
                              0.55, 0.7), 0.7)
        col = g.mix(stain, col, (0.04, 0.042, 0.028))
        # rust rubbed off the chain round the near end
        yrel = g.separate(g.coords())[1]
        rub = mul(g, g.ramp(yrel, Y_NEAR + 0.075, Y_NEAR + 0.02),
                  g.ramp(g.noise(14.0, detail=6.0, roughness=0.65, vector=P, distortion=0.5), 0.45, 0.6))
        col = g.mix(mul(g, rub, 0.8), col, (0.075, 0.032, 0.014))
    dirt = tk._grime(g, 0.9)
    col = g.mix(mul(g, dirt, 0.8), col, (0.022, 0.02, 0.016))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.1)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.55, 0.002))


def block(origin):
    """The block lying on a face shell, its two cores running across it (open at the sides), near end toward the
    zombie. Built as a grid section in y-z extruded across x, edges eased, chipped and cracked with booleans."""
    ys = [0.0, WEB, WEB + CORE, WEB + CORE + MID, BL - WEB, BL]
    zs = [0.0, SHELL, BH - SHELL, BH]
    holes = {(1, 1), (3, 1)}
    bm = bmesh.new()
    vs = {}
    for side, x in ((0, -BW / 2), (1, BW / 2)):
        for i, y in enumerate(ys):
            for j, z in enumerate(zs):
                vs[side, i, j] = bm.verts.new(origin + Vector((x, y, z)))
    for i in range(len(ys) - 1):
        for j in range(len(zs) - 1):
            if (i, j) in holes:
                continue
            for side in (0, 1):
                q = [vs[side, i, j], vs[side, i + 1, j], vs[side, i + 1, j + 1], vs[side, i, j + 1]]
                bm.faces.new(q if side else list(reversed(q)))
    # walls: round the outside and inside each core
    edges = []
    for i in range(len(ys) - 1):
        edges.append(((i, 0), (i + 1, 0)))
        edges.append(((i + 1, len(zs) - 1), (i, len(zs) - 1)))
    for j in range(len(zs) - 1):
        edges.append(((0, j + 1), (0, j)))
        edges.append(((len(ys) - 1, j), (len(ys) - 1, j + 1)))
    for (hi, hj) in holes:
        edges += [((hi, hj + 1), (hi + 1, hj + 1)), ((hi + 1, hj + 1), (hi + 1, hj)), ((hi + 1, hj), (hi, hj)),
                  ((hi, hj), (hi, hj + 1))]
    for (a, b) in edges:
        bm.faces.new((vs[0, a[0], a[1]], vs[0, b[0], b[1]], vs[1, b[0], b[1]], vs[1, a[0], a[1]]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Block", bm, block_mat)
    obj.data.materials.append(break_mat)
    tk.bevel(obj, 0.0035, segments=1, angle=40.0)
    # Chips knocked out of corners and edges, and a crack across the top running down the side
    chips = [((BW / 2, BL, BH), (0.045, 0.05, 0.05), 1), ((-BW / 2, 0.0, 0.0), (0.035, 0.04, 0.03), 2),
             ((BW / 2, WEB + CORE * 0.6, BH), (0.03, 0.06, 0.022), 3), ((-BW / 2, BL, 0.06), (0.025, 0.03, 0.05), 4),
             ((-BW / 2, WEB + CORE + MID + CORE * 0.3, SHELL), (0.02, 0.04, 0.018), 5)]
    for (cx, cy, cz), (sx, sy, sz), seed in chips:
        rnd = random.Random(seed * 17)
        c = origin + Vector((cx, cy, cz))
        pts = [c + Vector((rnd.uniform(-1, 1) * sx, rnd.uniform(-1, 1) * sy, rnd.uniform(-1, 1) * sz)) for _ in range(9)]
        pts.append(c)
        cut = hull("Chip%d" % seed, pts, break_mat)
        boolean(obj, cut)
    crack = []
    rnd = random.Random(99)
    path = [Vector((-BW / 2 - 0.01, BL * 0.78, BH + 0.01)), Vector((-BW * 0.15, BL * 0.74 + 0.01, BH + 0.01)),
            Vector((BW * 0.2, BL * 0.77, BH + 0.01)), Vector((BW / 2 + 0.01, BL * 0.73, BH + 0.01)),
            Vector((BW / 2 + 0.01, BL * 0.75, BH * 0.55))]
    for k in range(len(path) - 1):
        a, b = origin + path[k], origin + path[k + 1]
        d = (b - a).normalized()
        n = Vector((0.0, 0.0, 1.0)) if k < 3 else Vector((1.0, 0.0, 0.0))
        side = d.cross(n).normalized()
        w = 0.0016
        pts = [a - side * w, a + side * w, b - side * w, b + side * w, a - n * 0.016, b - n * 0.016,
               a - d * 0.004 + n * 0.004, b + d * 0.004 + n * 0.004]
        crack.append(hull("Crack%d" % k, pts, break_mat))
    for c in crack:
        boolean(obj, c)
    for v in obj.data.vertices:  # a little lumpy and worn (the bottom face kept flat, 10 cm under the pivot)
        d = Vector((noise.noise(v.co * 23.0), noise.noise(v.co * 23.0 + Vector((5.0, 1.0, 2.0))),
                    noise.noise(v.co * 23.0 + Vector((2.0, 7.0, 3.0))))) * 0.0018
        if v.co.z < origin.z + 0.0005:
            d.z = 0.0
        v.co += d
    return tk.smooth(obj, 30)


lock_steel = rusty_iron("LockSteel", seed=5.0, rust=0.5, scale=7.0, base=(0.035, 0.035, 0.036), rust_value=0.22,
                        rust_sat=1.1, grit=0.08, scale_dark=0.45, bump=0.45, noise_scale=5.0, scratches=0.18,
                        edges=0.25)
shackle_steel = rusty_iron("ShackleSteel", seed=6.0, rust=0.45, scale=6.0, base=(0.026, 0.025, 0.024), rust_value=0.2,
                           rust_sat=1.0, polish=0.1, grit=0.05, scale_dark=0.45, bump=0.35, noise_scale=3.0,
                           scratches=0.05, edges=0.0)


def padlock(J):
    """The padlock joining the chain's last link and both ends of the loop round the block: its shackle's bend
    across the chain (through the standing last link), the laminated body hanging under it, face to the zombie."""
    RS, ROD, CLEAR = 0.0135, 0.0045, 0.012
    SA, HANG, FN = Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, -1.0)), Vector((0.0, -1.0, 0.0))
    SC = Vector((J.x, J.y - W_LINK, J.z - RS))
    pts = [SC + SA * RS + HANG * (CLEAR + 0.006), SC + SA * RS + HANG * (CLEAR * 0.4)]
    for k in range(7):
        th = math.pi * k / 6
        pts.append(SC + (SA * math.cos(th) - HANG * math.sin(th)) * RS)
    pts += [SC - SA * RS + HANG * (CLEAR * 0.4), SC - SA * RS + HANG * (CLEAR + 0.006)]
    shackle = tube("Shackle", pts, ROD, shackle_steel, sides=6, caps=False)
    bw, bh, bt = 0.05, 0.042, 0.025
    body = slab_box("LockBody", SC + HANG * (CLEAR + bh / 2), SA, HANG, FN, bw, bh, bt, lock_steel, r=0.0055,
                    chamfer=0.0014)
    return [shackle, body], SC, RS, ROD


def loop_round_block(J, SC, RS, ROD, origin):
    """The chain wrapped round the block's near end: from the padlock out to both front corners, round the sides
    and through the near core, its two end links hanging on the shackle beside the drag chain's last link."""
    ends = []
    for s in (1, -1):
        dx = 0.012 * s
        zc = SC.z + math.sqrt(RS * RS - dx * dx)  # the bend's height there
        ends.append(Vector((J.x + dx, SC.y - (ROD + W_LINK) + HL, zc)))
    o = origin
    y_core = WEB + 0.022  # pressed against the near end web inside the core, clear of it
    ctrl = [ends[0], o + Vector((0.055, -0.02, 0.094)), o + Vector((0.112, -0.012, 0.09)),
            o + Vector((0.116, 0.02, 0.074)), o + Vector((0.106, y_core + 0.004, 0.058)),
            o + Vector((0.04, y_core, 0.054)), o + Vector((-0.04, y_core, 0.054)),
            o + Vector((-0.106, y_core + 0.004, 0.058)), o + Vector((-0.116, 0.02, 0.074)),
            o + Vector((-0.112, -0.012, 0.09)), o + Vector((-0.055, -0.02, 0.094)), ends[1]]
    dense = catmull(ctrl, per=12)
    length = arclen(dense)[-1]
    n = int(round(length / L_IN)) + 1
    if n % 2 == 0:
        n += 1  # odd, so both end links stand (across the shackle's bar)
    C = resample(dense, n)
    out = []
    for k in range(n):
        prev, nxt = C[max(k - 1, 0)], C[min(k + 1, n - 1)]
        along = (nxt - prev).normalized()
        if k == 0:
            along = (C[1] - C[0]).normalized()
        across = UP if k % 2 == 0 else along.cross(UP).normalized()
        out.append(chain_link("LoopLink%d" % k, C[k], along, across))
    print("[%s] loop round the block: %d links over %.2f m (%.1f mm apart)" % (SCRIPT, n, length,
                                                                               1000 * length / (n - 1)))
    return out


# ---------------------------------------------------------------- build

cuff = [band(), lock_box()] + hinge()
er, PIVOT_CHAIN = eye_and_ring()
cuff += er
chain = drag_chain(PIVOT_CHAIN)
PIVOT_BLOCK = PIVOT_CHAIN + Vector((0.0, 1.0, 0.0))  # where the chain's last link bears on the padlock's shackle
Y_NEAR = PIVOT_BLOCK.y + GAP
Z_BLOCK = PIVOT_BLOCK.z - 0.10  # the block's bottom face, 10 cm under the pivot
ORIGIN = Vector((PIVOT_BLOCK.x, Y_NEAR, Z_BLOCK))
block_mat = concrete_block("Cinder", 21.0)
break_mat = concrete_block("CinderBreak", 22.0, fresh=True)
lock, SC, RS, ROD = padlock(PIVOT_BLOCK)
blk = [block(ORIGIN)] + lock + loop_round_block(PIVOT_BLOCK, SC, RS, ROD, ORIGIN)
for p in cuff + chain + blk:
    depth_attr(p, leg_sdf)
for p in cuff:
    zk.on(p, "RightLeg", "Cuff")
for p in chain:
    zk.on(p, "RightLeg", "ChainDrag", pivot=PIVOT_CHAIN)
for p in blk:
    zk.on(p, "RightLeg", "BlockDrag", pivot=PIVOT_BLOCK)

first = chain[0]
last = chain[-1]
ys = [(last.matrix_world @ v.co).y for v in last.data.vertices]
print("[%s] ChainDrag pivot (%.4f, %.4f, %.4f); links from y %.4f to %.4f; BlockDrag pivot (%.4f, %.4f, %.4f); "
      "block bottom z %.4f (pivot %.4f above it), near face y %.4f" % (
          SCRIPT, *PIVOT_CHAIN, min((first.matrix_world @ v.co).y for v in first.data.vertices), max(ys), *PIVOT_BLOCK,
          Z_BLOCK, PIVOT_BLOCK.z - Z_BLOCK, Y_NEAR))
low = min(leg_sdf(v.co) for p in cuff for v in p.data.vertices)
print("[%s] cuff: nearest %.1f mm off the shin's hit box; band bottom z %.3f" % (
    SCRIPT, 1000 * low, min(v.co.z for v in cuff[0].data.vertices)))


def report(objs):
    groups = {}
    for o in objs:
        groups.setdefault(o["zbone"], []).append(o)
    total = 0
    for label, os_ in groups.items():
        tris = sum(len(pp.vertices) - 2 for o in os_ for pp in o.data.polygons)
        total += tris
        print("[%s] %-18s %5d tris (before triangulating)" % (SCRIPT, label, tris))
    print("[%s] %d tris in all" % (SCRIPT, total))


def export(pieces, size=1024):
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


report(cuff + chain + blk)
export(cuff + chain + blk)
zk.previews(SCRIPT, PREVIEWS, Vector((-0.15, 0.45, 0.35)), distance=2.6)
close_up("cuff", C + Vector((0.0, 0.03, 0.0)), (-0.7, 0.8, 0.45), distance=0.4)
close_up("block", ORIGIN + Vector((0.0, 0.12, 0.09)), (-1.0, -0.7, 0.6), distance=0.95)
print("[%s] done" % SCRIPT)
