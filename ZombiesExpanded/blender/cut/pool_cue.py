"""PoolCue (remnant): the thick half of a two-piece pool cue, snapped in its forearm and jabbed into the back of the
right shoulder, behind the joint, the splintered break buried in the body. The butt sticks out about 45 cm behind and
up: a worn black rubber bumper, a black lacquered butt sleeve with four inlaid pearl diamonds and thin rings, a
grimy black-and-grey Irish linen wrap gone shiny where hands held it and fraying at its lower end (one thread
unwinding and hanging), a ring collar, then the stained maple forearm with the bases of its four ebony points.
Dried blood soaks the forearm where it goes in, runs back along it and smears the wrap; shreds of torn flesh cling
to it at the skin.

The break sits 3.5 cm past the stand-in's skin, its jagged spikes deeper still, so the entry stays hidden on slimmer
zombies. One part on the right collarbone: "RightShoulder#Cue".

    blender -b --factory-startup --python pool_cue.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "PoolCue", "pool_cue", 5113

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


# ---------------------------------------------------------------- the cue's frame and profile

# The line it sits on: out of the back of the shoulder, behind the joint, pointing back, up and a little out
D = Vector((-0.4, 0.7, 0.6)).normalized()
AIM = Vector((-0.14, 0.09, 1.4))
E = entry(AIM + D * 0.5, -D)
X = orth(UP, D)  # across the cue, mostly up
Y = D.cross(X)  # across the cue, sideways
# The real shoulder bulges well past the hit boxes back here (deltoid, trapezius, the shirt): on Joe in Unity the cue
# meets the shirt about 12 cm out along it from the stand-in, some 6 cm off it. The cue sticks out 45 cm from there,
# the flesh and the worst of the blood sit there, and the break still goes 3 cm under the stand-in.
REAL_ALONG = 0.12
SKIN_OFF = sdf(E + D * REAL_ALONG)


def skin(p):
    """Distance to the real shoulder (the stand-in grown by SKIN_OFF), negative inside."""
    return sdf(p) - SKIN_OFF


OUT = 0.45  # real skin to the bumper's face
SINK = 0.03  # the break ring's shallowest point under the stand-in
B = E + D * (REAL_ALONG + OUT)  # the bumper's face; u runs from here into the body
U_STAND = OUT + REAL_ALONG  # where the cue's axis meets the stand-in
print("[%s] enters the stand-in at (%.3f, %.3f, %.3f), the real skin %.1f cm off it; butt at (%.3f, %.3f, %.3f), "
      "%.0f deg above level" % ((SCRIPT,) + tuple(E) + (SKIN_OFF * 100,) + tuple(B) + (math.degrees(math.asin(D.z)),)))

R0, R1 = 0.0162, 0.0128  # radius at the butt and at the joint (73 cm along)
Z_BUMP = 0.0122  # rubber bumper ends
Z_SLEEVE = 0.0141  # butt sleeve starts (after a thin ring)
Z_WRAP0, Z_WRAP1 = 0.118, 0.318  # the linen wrap
Z_FORE = 0.3305  # the forearm starts (after the ring collar)
SIDES = 16


def cue_r(u):
    return R0 + (R1 - R0) * u / 0.73


def at(u, x=0.0, y=0.0):
    return B - D * u + X * x + Y * y


def ring_depth(u):
    """How far outside the stand-in the shallowest point round the cue's surface at u is (negative: all inside)."""
    r = cue_r(u)
    return max(sdf(at(u, math.cos(a) * r, math.sin(a) * r)) for a in [2 * math.pi * k / 32 for k in range(32)])


# The cue goes in at a slant (the shoulder's back faces back and a little down, the cue points up), so its underside
# meets the skin later than its axis: the break goes where the whole ring is SINK under the skin.
U_BREAK = U_STAND
while ring_depth(U_BREAK) > -SINK:
    U_BREAK += 0.001
    assert U_BREAK < U_STAND + 0.15, "the cue never gets deep enough into the body"
print("[%s] %.1f cm of cue from bumper to break; the break is %.1f cm in past the stand-in along the cue, the whole "
      "ring %.1f cm under it" % (SCRIPT, U_BREAK * 100, (U_BREAK - U_STAND) * 100, -ring_depth(U_BREAK) * 100))

PROFILE = [  # (u, radius) from the bumper's face to the break; None follows the taper, a small negative is a step in
    (0.0, 0.0101), (0.0022, 0.0139), (0.0062, 0.0153), (0.0112, 0.0156), (0.0121, 0.0150), (0.0134, 0.0150),
    (0.0143, None), (0.065, None), (Z_WRAP0 - 0.0005, None), (Z_WRAP0 + 0.0005, -0.0004), (0.185, -0.0004),
    (0.25, -0.00045), (0.296, -0.0007), (Z_WRAP1 - 0.0005, -0.0004), (Z_WRAP1 + 0.0005, None), (0.37, None),
    (0.405, None), (0.43, None), (0.455, None), (0.49, None), (0.53, None)] +     [(U_STAND + (U_BREAK - 0.012 - U_STAND) * k / 2, None) for k in (0, 1, 2)]


# ---------------------------------------------------------------- materials

def cue_material(name, seed):
    """The cue's turned surface, zone by zone along zl.x (u from the bumper): worn black rubber, black lacquer with
    pearl diamonds and rings, black-and-grey Irish linen gone shiny and dark where held and frayed at its lower end,
    a ring collar, stained maple with ebony points; lacquer chipped and scratched, grimy, blood soaked near the
    skin and smeared over the wrap."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    L = combine(g, x, y, s)
    P = seeded(g, seed)
    th = g.math("ARCTAN2", y, x)
    tone = g.noise(7.0, detail=4.0, vector=P)

    rubber = g.ramp(s, Z_BUMP + 0.0003, Z_BUMP - 0.0003)
    sleeve = band(g, s, Z_SLEEVE, Z_WRAP0, 0.0003)
    wrap = band(g, s, Z_WRAP0, Z_WRAP1, 0.0003)
    fore = g.ramp(s, Z_FORE - 0.0003, Z_FORE + 0.0003)
    collar = band(g, s, Z_WRAP1, Z_FORE, 0.0003)

    # Black lacquer (sleeve and collar), the base everywhere else gets painted over
    col = g.mix(tone, (0.013, 0.012, 0.012), (0.03, 0.028, 0.027))
    rough = add(g, 0.5, mul(g, tone, 0.12))
    metal = g.value(0.0)
    height = mul(g, g.noise(120.0, detail=4.0, vector=P), 0.05)

    # Rubber bumper: dull, grey with dust on its face and worn round the rim
    face = g.ramp(s, 0.003, 0.0)
    rc = g.mix(mul(g, g.ramp(g.noise(30.0, detail=5.0, vector=P), 0.4, 0.7), 0.7), (0.01, 0.0095, 0.009), (0.026, 0.024, 0.022))
    rc = g.mix(mul(g, face, g.ramp(g.noise(12.0, detail=5.0, vector=P), 0.35, 0.6)), rc, (0.05, 0.046, 0.04))
    col = g.mix(rubber, col, rc)
    rough = g.mixf(rubber, rough, 0.86)
    height = add(g, height, mul(g, rubber, mul(g, g.noise(200.0, detail=3.0, vector=P), 0.4)))

    # Rings: thin bands of grimy ivory and tarnished nickel
    ivory = (0.12, 0.105, 0.08)
    nickel = (0.2, 0.19, 0.175)
    a0, a1 = Z_WRAP0, Z_WRAP1
    for lo, hi, c, m in ((0.0124, 0.0139, ivory, 0.0), (a0 - 0.014, a0 - 0.012, ivory, 0.0), (a0 - 0.01, a0 - 0.0086, nickel, 1.0),
                         (a0 - 0.0066, a0 - 0.0046, ivory, 0.0), (a1 + 0.0014, a1 + 0.0034, ivory, 0.0),
                         (a1 + 0.0054, a1 + 0.0068, nickel, 1.0), (a1 + 0.0088, a1 + 0.0108, ivory, 0.0)):
        b = band(g, s, lo, hi, 0.00015)
        col = g.mix(b, col, c)
        metal = g.mixf(b, metal, m)
        rough = g.mixf(b, rough, 0.42)

    # Four pearl diamonds round the sleeve
    k = g.math("FRACT", add(g, g.math("DIVIDE", g.math("SUBTRACT", th, math.pi / 4), math.pi / 2), 0.5))
    dth = mul(g, g.math("ABSOLUTE", g.math("SUBTRACT", k, 0.5)), math.pi / 2)
    dia = add(g, g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", s, 0.062)), 0.016), g.math("DIVIDE", dth, 0.34))
    dmask = g.ramp(dia, 1.0, 0.9)
    pearl = g.mix(g.ramp(g.noise(160.0, detail=3.0, vector=P), 0.3, 0.7), (0.06, 0.06, 0.056), (0.11, 0.105, 0.095))
    col = g.mix(dmask, col, pearl)
    rough = g.mixf(dmask, rough, 0.32)
    col = g.mix(mul(g, band(g, dia, 0.9, 1.06, 0.02), 0.8), col, (0.06, 0.055, 0.05))  # the inlay's dark outline

    # Irish linen wrap: salt-and-pepper threads wound round, fine helical grooves
    fl = g.noise(1.0, detail=2.0, roughness=0.5, vector=mapping(g, L, scale=(330.0, 330.0, 900.0), loc=(seed, 0.2, 0.0)))
    lin = g.mix(g.ramp(fl, 0.42, 0.66), (0.011, 0.011, 0.011), (0.042, 0.041, 0.039))
    fl2 = g.noise(1.0, detail=2.0, vector=mapping(g, L, scale=(260.0, 260.0, 700.0), loc=(0.5, seed, 0.3)))
    lin = g.mix(mul(g, g.ramp(fl2, 0.62, 0.68), 0.7), lin, (0.075, 0.072, 0.066))
    h = g.math("FRACT", add(g, g.math("DIVIDE", s, 0.0019), g.math("DIVIDE", th, 2 * math.pi)))
    groove = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", h, 0.5)), 0.32, 0.5)
    lin = g.mix(mul(g, groove, 0.5), lin, (0.008, 0.008, 0.008))
    grip = mul(g, g.ramp(g.noise(5.0, detail=4.0, vector=P), 0.4, 0.66), band(g, s, Z_WRAP0 + 0.03, Z_WRAP1 - 0.02, 0.02))
    lin = g.mix(mul(g, grip, 0.7), lin, tk._darker(g, lin, 0.45))
    # Fraying at the lower end: broken threads lifting, the wood showing through in a ragged patch
    fray = mul(g, band(g, s, Z_WRAP1 - 0.026, Z_WRAP1 - 0.0013, 0.003), g.ramp(g.math("COSINE", g.math("SUBTRACT", th, 0.35)), 0.35, 0.75))
    fray = mul(g, fray, g.ramp(g.noise(60.0, detail=5.0, vector=P), 0.38, 0.5))
    lin = g.mix(fray, lin, g.mix(g.ramp(g.noise(300.0, detail=3.0, vector=P), 0.4, 0.6), (0.05, 0.035, 0.022), (0.1, 0.09, 0.075)))
    col = g.mix(wrap, col, lin)
    rough = g.mixf(wrap, rough, add(g, g.mixf(grip, 0.86, 0.6), mul(g, fl, 0.06)))
    height = add(g, height, mul(g, wrap, add(g, mul(g, groove, -0.5), add(g, mul(g, fl, 0.3), mul(g, fray, -0.4)))))

    # Stained maple forearm, birdseye flecks, under lacquer; four ebony points (widest at the wrap) with ivory veneers
    grain = g.noise(1.0, detail=5.0, roughness=0.6, vector=mapping(g, L, scale=(260.0, 260.0, 9.0), loc=(seed, 0.4, 0.1)))
    maple = g.mix(g.ramp(grain, 0.3, 0.72), (0.04, 0.024, 0.012), (0.085, 0.052, 0.026))
    eyes = g.ramp(voronoi(g, mapping(g, L, scale=(1.0, 1.0, 0.5)), 260.0), 0.1, 0.03)
    maple = g.mix(mul(g, eyes, 0.6), maple, (0.03, 0.017, 0.009))
    kp = g.math("FRACT", add(g, g.math("DIVIDE", th, math.pi / 2), 0.5))
    dp = mul(g, g.math("ABSOLUTE", g.math("SUBTRACT", kp, 0.5)), math.pi / 2)
    halfw = mul(g, g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("SUBTRACT", s, Z_FORE), 0.3), clamp=True), 0.46)
    point = g.ramp(g.math("SUBTRACT", dp, halfw), 0.006, -0.006)
    ven = band(g, g.math("SUBTRACT", dp, halfw), 0.012, 0.075, 0.006)
    ven_red = band(g, g.math("SUBTRACT", dp, halfw), 0.035, 0.052, 0.004)
    fc = g.mix(ven, maple, ivory)
    fc = g.mix(ven_red, fc, (0.06, 0.012, 0.01))
    fc = g.mix(point, fc, g.mix(g.ramp(grain, 0.4, 0.7), (0.01, 0.009, 0.008), (0.022, 0.018, 0.015)))
    col = g.mix(fore, col, fc)
    rough = g.mixf(fore, rough, add(g, 0.48, mul(g, grain, 0.1)))
    height = add(g, height, mul(g, fore, mul(g, grain, 0.15)))

    # Lacquer chipped and dinged where it was swung into things: pale-ish wood in the chips
    hard = g.math("MAXIMUM", g.math("MAXIMUM", sleeve, fore), collar)
    chips = mul(g, g.ramp(g.noise(38.0, detail=6.0, roughness=0.65, vector=P), 0.69, 0.73), hard)
    col = g.mix(chips, col, g.mix(g.ramp(tone, 0.3, 0.7), (0.06, 0.04, 0.024), (0.1, 0.07, 0.042)))
    rough = g.mixf(chips, rough, 0.78)
    height = add(g, height, mul(g, chips, -0.5))
    scuff = mul(g, g.ramp(g.noise(9.0, detail=6.0, roughness=0.7, distortion=1.0, vector=P), 0.56, 0.7), hard)
    col = g.mix(mul(g, scuff, 0.6), col, g.mix(sleeve, tk._darker(g, col, 1.6), (0.055, 0.05, 0.046)))
    rough = g.mixf(scuff, rough, 0.62)

    # Grime and dirt
    dirt = g.math("MAXIMUM", tk._grime(g, 0.6), mul(g, g.ramp(g.noise(4.0, detail=6.0, distortion=0.5, vector=P), 0.56, 0.74), 0.8))
    col = g.mix(mul(g, dirt, 0.75), col, (0.03, 0.025, 0.018))
    rough = g.mixf(dirt, rough, 0.88)
    metal = g.mixf(dirt, metal, 0.0)
    col, rough, metal = tk._grit(g, col, rough, metal, 0.1, scratches=0.05)

    # Blood: soaked at the wound, running back along the forearm, smeared over the wrap by bloody hands
    bm_ = gore_mask(g, P, reach=0.045, amount=1.0, runs=0.6, dots=0.6, scale=14.0)
    smear = mul(g, g.ramp(g.noise(3.2, detail=6.0, roughness=0.6, distortion=0.9, vector=P), 0.6, 0.67),
                band(g, s, 0.14, OUT - 0.03, 0.02))
    bm_ = g.math("MAXIMUM", bm_, mul(g, smear, 0.7))
    col, rough, height = dried_blood(g, col, rough, height, bm_, P)
    metal = g.mixf(bm_, metal, 0.0)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.002))


def broken_wood(name, seed, blood=0.85):
    """The snapped end: pale fibrous maple inside, torn along the grain, soaked dark with blood from the body."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    L = combine(g, x, y, s)
    P = seeded(g, seed)
    fib = g.noise(1.0, detail=6.0, roughness=0.7, vector=mapping(g, L, scale=(700.0, 700.0, 30.0), loc=(seed, 0.1, 0.4)))
    col = g.mix(g.ramp(fib, 0.3, 0.75), (0.06, 0.045, 0.03), (0.15, 0.12, 0.085))
    torn = g.ramp(g.noise(30.0, detail=6.0, vector=P), 0.55, 0.7)
    col = g.mix(mul(g, torn, 0.7), col, (0.03, 0.024, 0.018))
    rough = add(g, 0.82, mul(g, fib, 0.1))
    height = mul(g, add(g, fib, mul(g, torn, -0.8)), 0.6)
    soak = mul(g, g.ramp(g.noise(9.0, detail=5.0, vector=P), 0.2, 0.5), blood)
    col, rough, height = dried_blood(g, col, rough, height, soak, P)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


def thread_material(name, seed):
    """A loose thread of the linen wrap: grey-black twisted fiber, lighter where it frays, grimy."""
    mat, g = tk.new_material(name)
    s, x, y = attr(g, "zl")
    P = seeded(g, seed)
    tw = g.math("FRACT", add(g, g.math("DIVIDE", s, 0.004), g.math("DIVIDE", g.math("ARCTAN2", y, x), math.pi)))
    col = g.mix(g.ramp(g.noise(200.0, detail=3.0, vector=P), 0.3, 0.7), (0.012, 0.012, 0.011), (0.045, 0.043, 0.04))
    col = g.mix(mul(g, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", tw, 0.5)), 0.3, 0.5), 0.6), col, (0.01, 0.01, 0.01))
    col = g.mix(g.ramp(s, 0.06, 0.085), col, (0.065, 0.06, 0.052))
    sp = mul(g, g.ramp(g.noise(30.0, detail=4.0, vector=P), 0.55, 0.65), 0.7)
    col, rough, height = dried_blood(g, col, g.value(0.85), mul(g, tw, 0.4), sp, P)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.002))


cue_mat = cue_material("Cue", 1.0)
snapped = broken_wood("CueBroken", 2.0)
thread_mat = thread_material("WrapThread", 3.0)
flesh = gore_flesh("Gore", 4.0)


# ---------------------------------------------------------------- the cue

def cue():
    """The turned cue from the bumper's face to the break: a domed bumper, a groove, the sleeve, the wrap a hair
    below the sleeve and collar, the forearm, and a jagged snapped end (spikes along the grain) deep in the body."""
    bm = bmesh.new()
    rings, vals = [], []
    prof = [(u, cue_r(u) if r is None else (cue_r(u) + r if r < 0 else r)) for u, r in PROFILE]
    prof.append((U_BREAK, cue_r(U_BREAK)))
    spikes = [0.003 + 0.03 * max(0.0, math.sin(2.3 * j + 0.4)) ** 3 + abs(jit(0.007)) for j in range(SIDES)]
    n = len(prof) - 1
    for i, (u, r) in enumerate(prof):
        ring = []
        for j in range(SIDES):
            ang = 2 * math.pi * j / SIDES
            rr, uu = r, u
            if i == n:  # the break: splintered spikes reaching on into the body, thinning toward their tips
                uu = U_BREAK + spikes[j]
                rr = r * (0.86 - 0.3 * spikes[j] / 0.036)
            ring.append(bm.verts.new(at(uu, math.cos(ang) * rr, math.sin(ang) * rr)))
            vals.append((uu, math.cos(ang) * rr, math.sin(ang) * rr))
        rings.append(ring)
    for i in range(n):
        for j in range(SIDES):
            j1 = (j + 1) % SIDES
            f = bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
            if i == n - 1:
                f.material_index = 1
    # The bumper's face, domed a touch
    c0 = bm.verts.new(at(-0.0012))
    vals.append((-0.0012, 0.0, 0.0))
    for j in range(SIDES):
        bm.faces.new((rings[0][(j + 1) % SIDES], rings[0][j], c0))
    # The torn wood inside the spikes
    c1 = bm.verts.new(at(U_BREAK - 0.004, 0.002, -0.001))
    vals.append((U_BREAK - 0.004, 0.0, 0.0))
    for j in range(SIDES):
        f = bm.faces.new((rings[n][j], rings[n][(j + 1) % SIDES], c1))
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Cue", bm, cue_mat)
    obj.data.materials.append(snapped)
    set_attr(obj, "zl", vals)
    tk.smooth(obj, 50)
    out = [obj]
    # A few long slivers peeling off the break, deep in the body
    r = cue_r(U_BREAK)
    for k, (ang, ln, w, flare) in enumerate(((0.6, 0.045, 0.0036, 0.25), (2.7, 0.035, 0.003, 0.15),
                                              (4.4, 0.03, 0.0028, 0.3))):
        base = U_BREAK - 0.012
        pts, rad = [], []
        for m in range(4):
            t = m / 3
            rr = r * (0.92 + flare * t * t * 2.2)
            pts.append(at(base + ln * t, math.cos(ang + 0.1 * t) * rr, math.sin(ang + 0.1 * t) * rr))
        rad = [(w, w * 0.45), (w * 0.8, w * 0.4), (w * 0.5, w * 0.25), (0.0004, 0.0003)]
        nrm = [X * math.cos(ang) + Y * math.sin(ang)] * 4
        out.append(tube("Sliver%d" % k, pts, rad, snapped, sides=3, normals=nrm, phase=0.5, s0=base))
    return out


def loose_thread():
    """A thread of the wrap come loose at its frayed lower end: it peels off the top of the wrap, round one side and
    hangs in a short curl below the cue."""
    u0 = Z_WRAP1 - 0.012
    r = cue_r(u0) - 0.0002
    ctrl = []
    for k in range(5):
        a = 0.35 - 1.5 * k / 4
        ctrl.append(at(u0 - 0.004 * k, math.cos(a) * (r + 0.0006 + 0.0005 * k), math.sin(a) * (r + 0.0006 + 0.0005 * k)))
    last = ctrl[-1]
    side = orth(Y, UP)
    ctrl += [last + Vector((0.0, 0.0, -0.012)) + side * 0.003 - D * 0.004,
             last + Vector((0.0, 0.0, -0.028)) + side * 0.001 - D * 0.003,
             last + Vector((0.0, 0.0, -0.042)) - side * 0.004 + D * 0.002,
             last + Vector((0.0, 0.0, -0.05)) - side * 0.002 + D * 0.006]
    pts = catmull(ctrl, 2)
    n = len(pts)
    rad = [0.0009 if i < n - 3 else 0.0009 - 0.00022 * (i - n + 4) for i in range(n)]
    return tube("Thread", pts, rad, thread_mat, sides=4, caps=True)


def gore_bits():
    """Shreds of torn flesh and clot stuck round the forearm where it meets the real shoulder (a few cm out past the
    stand-in here) and a little way out from it, mostly underneath where they sagged, flattened onto the wood."""
    out = []
    for k, (du, ang, size, seed) in enumerate(((-0.006, math.pi * 1.0, (0.014, 0.0068, 0.0036), 2.1),
                                               (-0.03, math.pi * 1.22, (0.009, 0.005, 0.003), 3.7),
                                               (0.004, math.pi * 1.55, (0.011, 0.006, 0.0034), 5.3),
                                               (-0.016, math.pi * 0.62, (0.007, 0.0045, 0.0026), 6.9),
                                               (-0.05, math.pi * 0.95, (0.006, 0.0035, 0.0024), 8.4))):
        u = OUT + du
        rr = cue_r(u)
        radial = X * math.cos(ang) + Y * math.sin(ang)
        c = at(u, math.cos(ang) * rr * 0.9, math.sin(ang) * rr * 0.9)
        out.append(blob("Shred%d" % k, c, size, (-D, radial.cross(-D), radial), flesh, seed=seed, lump=0.5,
                        seg=(7, 5)))
    return out


pieces = cue() + [loose_thread()] + gore_bits()
for p in pieces:
    depth_attr(p, skin)
    zk.on(p, "RightShoulder", "Cue")

report(pieces)
for p in pieces:
    if p.name.startswith("Sliver") or p.name == "Cue":
        out_ = max(sdf(v.co) for v in p.data.vertices if (v.co - B).dot(-D) > U_BREAK - 0.012)
        print("[%s] %s: its buried end comes no closer than %.1f cm under the skin" % (SCRIPT, p.name, -out_ * 100))
d_head = min(sdf(at(u), ("Head",)) for u in [k * 0.01 for k in range(int(U_STAND * 100))])
d_arm = min(sdf(at(u), ("RightArm",)) - cue_r(u) for u in [k * 0.01 for k in range(int(U_STAND * 100) - 3)])
print("[%s] the cue clears the head by %.1f cm, the upper arm's hit box by %.1f cm" % (SCRIPT, d_head * 100, d_arm * 100))
parts = export(pieces)
focus = at(OUT - 0.2)
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.35)
close_up("close", at(OUT - 0.2), (-1.0, 0.25, 0.25), distance=0.8)
close_up("entry", at(OUT - 0.03), (-0.9, 0.5, 0.1), distance=0.3)
close_up("butt", B - D * 0.1, (-0.5, 0.2, 0.9), distance=0.3)
close_up("frontview", at(OUT - 0.15) + Vector((0.0, 0.0, 0.05)), (-0.35, -1.0, 0.25), distance=1.0)
print("[%s] done" % SCRIPT)
