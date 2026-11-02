"""Gnarled hands: the Grabber's mutation. Both hands have grown too big and knotted: huge swollen knuckles, bony
nodules and ridged tendons across the backs of the hands, bone breaking through the skin here and there, a lumpy
overgrown wrist, swollen finger joints and long, thick, cracked and broken nails.

The hand growths ride on the hand bone (LeftHand#Knuckles, RightHand#Knuckles); each finger's swollen joints and nail
ride on its second bone (LeftHandIndex2#Nail ... LeftHandThumb2#Nail).

    blender -b --factory-startup --python gnarled_hands.py -- <unity models folder> <preview folder>
"""
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
ASSETS, PREVIEWS = os.path.join(args[0], "GnarledHands"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

rnd = random.Random(7717)


def jit(a):
    return rnd.uniform(-a, a)


tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

SIDES = ("Left", "Right")
FINGERS = ("Index", "Middle", "Ring", "Pinky", "Thumb")
# Finger thickness on Joe (radius of the proximal, middle and distal segments)
RADII = {"Index": (0.0105, 0.0095, 0.0085), "Middle": (0.011, 0.0098, 0.0088), "Ring": (0.0102, 0.0092, 0.0082),
         "Pinky": (0.0088, 0.008, 0.0072), "Thumb": (0.0125, 0.0112, 0.0098)}
# The back of the hand: half-width and half-thickness of the hand at a distance x from the wrist (toward the
# knuckles), and how far its middle sits toward the palm
PALM = ((-0.01, 0.03, 0.024), (0.03, 0.044, 0.017), (0.08, 0.05, 0.0155), (0.125, 0.05, 0.0145), (0.137, 0.046, 0.012))
PALM_DROP = 0.003


# ---------------------------------------------------------------- frames and mesh helpers

def mirror(v, side):
    return Vector((v.x, v.y, v.z)) if side == "Left" else Vector((-v.x, v.y, v.z))


def orth(v, axis):
    return (v - axis * v.dot(axis)).normalized()


def bone(side, finger, k):
    return "%sHand%s%d" % (side, finger, k)


def local_y(b, side):
    """A left bone's local +Y (the back of the hand / the nail side), mirrored for the right."""
    return mirror((sk.point(b, (0.0, 1.0, 0.0)) - sk.pos(b)).normalized(), side)


def hand_frame(side):
    """The wrist point, the direction to the knuckles, the back of the hand and the across axis (thumb side to pinky
    side is not guaranteed; only used symmetrically)."""
    H = sk.pos(side + "Hand")
    ax = (sk.pos(bone(side, "Middle", 1)) - H).normalized()
    nh = orth(local_y("LeftHand", side), ax)
    return H, ax, nh, nh.cross(ax)


def finger_frame(side, finger, k):
    """At joint k of a finger: the joint, the segment's direction, the nail side and the across axis."""
    p, q = sk.pos(bone(side, finger, k)), sk.pos(bone(side, finger, k + 1))
    d = (q - p).normalized()
    n = orth(local_y(bone("Left", finger, 2), side), d)
    return p, d, n, n.cross(d)


def palm_at(x):
    """Half-width and half-thickness of the stand-in hand at x along it."""
    for (x0, w0, t0), (x1, w1, t1) in zip(PALM, PALM[1:]):
        if x <= x1:
            f = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
            return w0 + (w1 - w0) * f, t0 + (t1 - t0) * f
    return PALM[-1][1], PALM[-1][2]


def set_attr(obj, vals):
    """Per-vertex growth coordinates for the materials: (around 0-1, along/up 0-1, seed)."""
    me = obj.data
    at = me.attributes.new("gr", "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def loft(name, rings, attrs, mat, start=None, end=None, smooth=70, closed=True):
    """A tube through `rings` (point loops of equal length); start/end close it to a point (point, attr)."""
    bm = bmesh.new()
    vals = []
    vr = []
    for ring, at in zip(rings, attrs):
        vr.append([bm.verts.new(p) for p in ring])
        vals += at
    m = len(rings[0])
    for A, B in zip(vr, vr[1:]):
        for j in range(m if closed else m - 1):
            k = (j + 1) % m
            bm.faces.new((A[j], A[k], B[k], B[j]))
    for cap, ring in ((start, vr[0]), (end, vr[-1])):
        if cap is None:
            continue
        c = bm.verts.new(cap[0])
        vals.append(cap[1])
        for j in range(m):
            bm.faces.new((ring[j], ring[(j + 1) % m], c))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, smooth)


def lump(name, center, axes, radii, mat, seed, u=10, v=7, knots=0.16, freq=1.6, flat=0.6, lobes=0.0):
    """A knotted ellipsoid (radii along the three axes); its underside is flattened (it sinks into the body) and t
    runs from the underside (0) to the top (1) along the third axis. lobes splits the top into two bumps across."""
    X, Y, Z = axes
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    vals = []
    off = Vector((seed * 5.1, seed * 2.3, seed * 7.7))
    for vert in bm.verts:
        p = vert.co.copy()
        k = 1.0 + knots * noise.noise(p * freq + off)
        if lobes and p.z > 0:
            k *= 1.0 + lobes * (abs(p.y) * 2.0 - 0.6) * p.z
        z = p.z * (flat if p.z < 0 else 1.0)
        vert.co = center + X * (p.x * radii[0] * k) + Y * (p.y * radii[1] * k) + Z * (z * radii[2] * k)
        vals.append(((math.atan2(p.y, p.x) / (2 * math.pi)) % 1.0, (p.z + 1.0) / 2.0, seed))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, 80)


# ---------------------------------------------------------------- materials

def gr(g):
    n = g.node("ShaderNodeAttribute", attribute_name="gr")
    return g.separate(tk._sock(n.outputs, "Vector"))


def wrap(g, a, t, seed, ka, kt):
    """Noise coordinates that wrap around a growth (no seam) and run along it: ka around, kt along."""
    ang = g.math("MULTIPLY", a, 2 * math.pi)
    v = g.node("ShaderNodeCombineXYZ")
    g._in(v, "X", g.math("MULTIPLY", g.math("COSINE", ang), ka))
    g._in(v, "Y", g.math("MULTIPLY", g.math("SINE", ang), ka))
    g._in(v, "Z", g.math("ADD", g.math("MULTIPLY", t, kt), g.math("MULTIPLY", seed, 7.3)))
    return v.outputs[0]


def lines(g, vec, width, detail=2.0):
    n = g.noise(1.0, detail=detail, roughness=0.5, vector=vec)
    return g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), width, 0.0)


def veins(g, scale, width):
    """A branching network of raised veins (Voronoi cell edges, warped), 1 on a vein."""
    warp = g.node("ShaderNodeTexNoise")
    g._in(warp, "Scale", scale * 0.35)
    g._in(warp, "Detail", 3.0)
    g.links.new(g.coords(), warp.inputs["Vector"])
    mix = g.node("ShaderNodeMix", data_type="VECTOR")
    g._in(mix, "Factor_Float", 0.12)
    g.links.new(g.coords(), tk._sock(mix.inputs, "A_Vector"))
    g.links.new(tk._sock(warp.outputs, "Color"), tk._sock(mix.inputs, "B_Vector"))
    vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
    g._in(vor, "Scale", scale)
    g.links.new(tk._sock(mix.outputs, "Result_Vector"), vor.inputs["Vector"])
    edge = g.ramp(tk._sock(vor.outputs, "Distance"), width, 0.0)
    return g.math("MULTIPLY", edge, g.ramp(g.noise(scale * 0.25, detail=3.0), 0.38, 0.55))


def skin_material(name):
    """Swollen, stretched skin over knotted bone: dead grey-tan like a zombie's own where it rises out of the skin,
    bruised purple-brown in a broken ring around the base, tight, shiny and inflamed over the tops (t high), with
    faint veins, a few bloody splits at the tightest spots and grime in the creases."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    mott = g.noise(160.0, detail=5.0, distortion=0.5)
    blot = g.noise(40.0, detail=4.0, distortion=0.3)
    col = g.mix(g.ramp(mott, 0.3, 0.7), (0.34, 0.28, 0.25), (0.24, 0.19, 0.17))
    ring = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", t, 0.55)), 0.24, 0.04),
                  g.ramp(blot, 0.3, 0.62))
    col = g.mix(g.math("MULTIPLY", ring, 0.85), col,
                g.mix(g.ramp(blot, 0.4, 0.75), (0.19, 0.1, 0.11), (0.17, 0.12, 0.07)))
    top = g.math("MULTIPLY", g.ramp(t, 0.74, 1.0), g.ramp(blot, 0.22, 0.55))
    col = g.mix(g.math("MULTIPLY", top, 0.6), col, (0.33, 0.15, 0.12))
    vein = veins(g, 70.0, 0.03)
    col = g.mix(g.math("MULTIPLY", vein, 0.45), col, (0.15, 0.11, 0.16))
    split = g.math("MULTIPLY", lines(g, wrap(g, a, t, seed, 2.2, 3.0), 0.02), g.ramp(t, 0.86, 0.97))
    col = g.mix(split, col, (0.15, 0.015, 0.012))
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.012), clamp=True), 1.4, clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.65), col, (0.06, 0.04, 0.03))
    rough = g.mixf(top, g.math("ADD", 0.55, g.math("MULTIPLY", mott, 0.12)), 0.33)
    rough = g.mixf(split, rough, 0.2)
    pores = g.noise(700.0, detail=2.0)
    height = g.math("ADD", g.math("MULTIPLY", mott, 0.3), g.math("MULTIPLY", vein, 0.5))
    height = g.math("ADD", height, g.math("MULTIPLY", pores, 0.15))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", split, 0.8))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.0012))


def bone_material(name):
    """Yellowed bone breaking out through the skin: ivory to dirty yellow-brown, pitted, stained in the creases,
    bloody where it comes out of the skin (t low)."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    tone = g.noise(140.0, detail=5.0)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.6, 0.53, 0.37), (0.45, 0.37, 0.23))
    stain = g.ramp(g.noise(35.0, detail=6.0, distortion=0.4), 0.45, 0.72)
    col = g.mix(g.math("MULTIPLY", stain, 0.7), col, (0.3, 0.21, 0.11))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 600.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    pits = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.22, 0.08),
                  g.ramp(g.noise(60.0, detail=3.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", pits, 0.8), col, (0.16, 0.1, 0.05))
    blood = g.math("MULTIPLY", g.ramp(t, g.math("ADD", 0.45, g.math("MULTIPLY", tone, 0.2)), 0.3),
                   g.ramp(g.noise(90.0, detail=4.0), 0.25, 0.5))
    col = g.mix(blood, col, (0.16, 0.015, 0.012))
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.01), clamp=True), 1.5, clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.75), col, (0.08, 0.05, 0.03))
    rough = g.mixf(blood, g.math("ADD", 0.55, g.math("MULTIPLY", tone, 0.15)), 0.25)
    rough = g.mixf(pits, rough, 0.85)
    height = g.math("SUBTRACT", g.math("MULTIPLY", tone, 0.35), g.math("MULTIPLY", pits, 0.7))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.0008))


def nail_material(name):
    """Thick old fingernail: yellow-brown horn with deep ridges along it, grime packed under and around it, cracked,
    paler and chalky at the broken free edge."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    grain = g.noise(1.0, detail=4.0, roughness=0.6, vector=wrap(g, a, t, seed, 3.0, 1.0))
    col = g.mix(g.ramp(grain, 0.3, 0.72), (0.36, 0.25, 0.09), (0.58, 0.46, 0.22))
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.25, 0.0), 0.8), col, (0.2, 0.11, 0.06))
    edge = g.ramp(t, 0.75, 1.0)
    col = g.mix(g.math("MULTIPLY", edge, 0.55), col, (0.62, 0.58, 0.46))
    crack = g.math("MULTIPLY", lines(g, wrap(g, a, t, seed, 4.0, 0.7), 0.035),
                   g.ramp(g.noise(1.0, vector=wrap(g, a, t, seed, 1.0, 3.0)), 0.42, 0.56))
    col = g.mix(crack, col, (0.06, 0.04, 0.02))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.006), clamp=True), 1.6, clamp=True),
                  g.math("MULTIPLY", g.ramp(t, 0.85, 1.0), g.ramp(g.noise(200.0), 0.4, 0.6)))
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, (0.06, 0.045, 0.03))
    rough = g.mixf(g.math("MAXIMUM", crack, dirt), g.math("ADD", 0.36, g.math("MULTIPLY", grain, 0.15)), 0.8)
    rough = g.mixf(edge, rough, 0.6)
    ridges = g.math("SINE", g.math("ADD", g.math("MULTIPLY", a, 2 * math.pi * 9.0), g.math("MULTIPLY", grain, 3.0)))
    height = g.math("SUBTRACT", g.math("MULTIPLY", ridges, 0.3), g.math("MULTIPLY", crack, 0.9))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.0006))


skin = skin_material("GnarlSkin")
bonem = bone_material("GnarlBone")
nailm = nail_material("GnarlNail")


# ---------------------------------------------------------------- the hand: pad, knuckles, nodules, wrist

def hand_axis(side, x):
    """The middle of the stand-in hand at x along it (it shifts toward the knuckles' midline)."""
    H, ax, nh, lat = hand_frame(side)
    k1 = [sk.pos(bone(side, f, 1)) for f in ("Index", "Middle", "Ring", "Pinky")]
    mid_lat = ((k1[0] + k1[3]) / 2 - H).dot(lat)
    return H + ax * x + lat * (mid_lat * max(0.0, min(1.0, x / 0.08))) - nh * PALM_DROP


def dorsal_point(side, x, yf, lift=0.0):
    """A point on the back of the stand-in hand: x along it, yf across (-1 to 1 of its half-width), lifted off it."""
    H, ax, nh, lat = hand_frame(side)
    w, th = palm_at(x)
    z = th * max(0.0, 1.0 - abs(yf) ** 3) ** (1.0 / 3.0)
    return hand_axis(side, x) + lat * (yf * w) + nh * (z + lift)


SIZE = {"Index": 1.18, "Middle": 1.25, "Ring": 1.1, "Pinky": 0.95}


def ridge(side, finger, seed):
    """A metacarpal grown thick and knotted under the skin: it rises out of the middle of the back of the hand and
    swells into a big knuckle."""
    H, ax, nh, lat = hand_frame(side)
    K = sk.pos(bone(side, finger, 1))
    xk = (K - H).dot(ax)
    wk, _ = palm_at(xk)
    yk = (K - hand_axis(side, xk)).dot(lat) / wk
    s = SIZE[finger]
    m = 8
    xs = (xk - 0.046, xk - 0.034, xk - 0.023, xk - 0.012, xk - 0.003, xk + 0.006)
    rs = (0.0036, 0.0064, 0.0086, 0.0113, 0.0128, 0.0106)
    off = Vector((seed * 4.1, seed * 1.3, seed * 2.9))
    rings, attrs = [], []
    for i, (x, r) in enumerate(zip(xs, rs)):
        f = min(1.0, (x - xs[0]) / (xk - xs[0]))
        yf = yk * (0.82 + 0.18 * f)
        r *= s * (1.0 + 0.16 * noise.noise(Vector((x * 60.0, 0.0, 0.0)) + off))
        c = dorsal_point(side, x, yf, -(0.0042 + 0.0042 * (1.0 - f) ** 2) * s)
        ring, at = [], []
        for q in range(m):
            ang = 2 * math.pi * q / m
            ca, sa = math.cos(ang), math.sin(ang)
            k = 1.0 + 0.2 * noise.noise(Vector((ca * 2.2, sa * 2.2, x * 110.0)) + off)
            # Broad and low where it rises out of the hand, rounder at the knuckle
            spread = 1.35 - 0.3 * f
            ring.append(c + nh * (ca * r * k * (1.0 if ca > 0 else 0.6)) + lat * (sa * r * k * spread))
            at.append((q / m, 0.5 + 0.5 * ca * min(1.0, r / 0.011), seed))
        rings.append(ring)
        attrs.append(at)
    c0 = sum(rings[0], Vector()) / m
    c1 = sum(rings[-1], Vector()) / m
    return loft("Ridge%s%s" % (side, finger), rings, attrs, skin,
                start=(c0 - ax * 0.0035 - nh * 0.002, (0.5, 0.3, seed)),
                end=(c1 + ax * 0.0055 + nh * 0.001, (0.5, 0.8, seed)), smooth=80)


def spur(name, base, direction, length, r0, seed, m=6):
    """A short, blunt, knobbly spur of bone growing out of a swelling (its base buried in it)."""
    d = Vector(direction).normalized()
    u = orth(Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else Vector((1.0, 0.0, 0.0)), d)
    v = d.cross(u)
    bend = u * jit(0.25) + v * jit(0.25)
    rings, attrs = [], []
    for f, rf in ((0.0, 1.0), (0.4, 0.78), (0.72, 0.5)):
        c = base + (d + bend * f) * (length * f)
        ring = []
        for q in range(m):
            ang = 2 * math.pi * q / m
            k = 1.0 + 0.22 * noise.noise(Vector((math.cos(ang), math.sin(ang), f * 3.0 + seed * 5.0)))
            ring.append(c + u * (math.cos(ang) * r0 * rf * k) + v * (math.sin(ang) * r0 * rf * k))
        rings.append(ring)
        attrs.append([(q / m, f, seed) for q in range(m)])
    tip = base + (d + bend) * length
    return loft(name, rings, attrs, bonem, start=(base - d * r0, (0.5, 0.0, seed)), end=(tip, (0.5, 1.0, seed)),
                smooth=70)


def back_of_hand(side, seed0):
    H, ax, nh, lat = hand_frame(side)
    out = []
    ridges = {}
    for i, finger in enumerate(("Index", "Middle", "Ring", "Pinky")):
        ridges[finger] = ridge(side, finger, seed0 + i * 0.21)
        out.append(ridges[finger])
    # Bone spurs out of the index and middle knuckles and the ring finger's ridge
    for finger, lift, tilt, length, r0 in (("Index", 0.0105, (0.35, 0.3), 0.0155, 0.0034),
                                           ("Middle", 0.0115, (-0.25, -0.35), 0.0135, 0.0032)):
        K = sk.pos(bone(side, finger, 1))
        x = (K - H).dot(ax) - 0.004
        w, _ = palm_at(x)
        top = dorsal_point(side, x, (K - hand_axis(side, x)).dot(lat) / w, -0.0042 * SIZE[finger] + lift)
        out.append(spur("Spur%s%s" % (side, finger), top - nh * 0.004, nh + ax * tilt[0] + lat * tilt[1], length, r0,
                        seed0 + len(out) * 0.1))
    K = sk.pos(bone(side, "Ring", 1))
    w, _ = palm_at(0.09)
    yf = (K - hand_axis(side, 0.09)).dot(lat) / w * 0.85
    out.append(spur("Spur%sRing" % side, dorsal_point(side, 0.09, yf, 0.0), nh + lat * 0.4 * (1 if yf > 0 else -1),
                    0.0105, 0.003, seed0 + 0.77))
    # Bony nodules between the ridges
    for i, (x, yf, s) in enumerate(((0.062, -0.05, 1.05),)):
        c = dorsal_point(side, x, yf + jit(0.04), -0.0012)
        out.append(lump("Nodule%s%d" % (side, i), c, (ax, lat, nh), (0.0095 * s, 0.0082 * s, 0.0068 * s), skin,
                        seed0 + 1.3 + i * 0.17, u=9, v=6, knots=0.25))
    return out


def wrist(side, seed0):
    """Knots of bony overgrowth around the wrist: a big one over each of the wrist's knobs (pinky and thumb sides)
    and one over the back, with bone spurs out of two of them."""
    H, ax, nh, lat = hand_frame(side)
    thumb_side = 1.0 if (sk.pos(bone(side, "Index", 1)) - H).dot(lat) > 0 else -1.0
    out = []
    for i, (deg, x, size, spur_len) in enumerate(((-82.0 * thumb_side, -0.004, 1.15, 0.012),
                                                  (78.0 * thumb_side, 0.003, 0.95, 0.0),
                                                  (8.0, -0.002, 0.95, 0.0095))):
        ang = math.radians(deg)
        w, th = palm_at(x)
        radial = (nh * (math.cos(ang) / th) + lat * (math.sin(ang) / w)).normalized()
        surf = hand_axis(side, x) + nh * (math.cos(ang) * th) + lat * (math.sin(ang) * w)
        c = surf - radial * 0.0028 * size
        out.append(lump("WristKnot%s%d" % (side, i), c, (ax, radial.cross(ax), radial),
                        (0.0125 * size, 0.0095 * size, 0.0085 * size), skin, seed0 + i * 0.23, u=10, v=6, knots=0.25,
                        freq=1.8))
        if spur_len:
            out.append(spur("WristSpur%s%d" % (side, i), c + radial * 0.004 * size, radial + ax * jit(0.3),
                            spur_len, 0.0032 * size, seed0 + 0.5 + i))
    return out


# ---------------------------------------------------------------- fingers: swollen joints and nails

def nail(side, finger, seed, ext, broken=0, split=False):
    """A long, thick nail on the last segment, from the cuticle out past the fingertip, curling down a little."""
    T = sk.pos(bone(side, finger, 4))
    _, d, n, lat = finger_frame(side, finger, 3)
    rd = RADII[finger][2]
    half = math.radians(62.0)
    m = 4  # points across the top (and as many under)
    rings, attrs = [], []
    us = (-0.017, -0.011, -0.004, 0.003, 0.003 + ext * 0.4, 0.003 + ext * 0.75, 0.003 + ext)
    jag = [jit(1.0) for _ in range(2 * m)]
    for i, u in enumerate(us):
        f = max(0.0, u) / (0.003 + ext)
        phi = math.radians(24.0) * f ** 1.4
        # The nail's own axis: the finger's axis, then bending down past the tip
        if u <= 0:
            c = T + d * u
            N, D = n, d
        else:
            c = T + d * (u * math.cos(phi * 0.5)) - n * (u * math.sin(phi * 0.5))
            N = n * math.cos(phi) + d * math.sin(phi)
            D = d * math.cos(phi) - n * math.sin(phi)
        thick = 0.0018 + 0.0017 * min(1.0, (u + 0.017) / 0.024)
        R = rd - 0.0012 if i == 0 else (rd + 0.0002 - 0.0022 * f)
        hw = half * (0.75 if i == 0 else (1.0 - 0.15 * f))
        outer, inner = [], []
        for q in range(m):
            al = -hw + 2 * hw * q / (m - 1)
            radial = N * math.cos(al) + lat * math.sin(al)
            outer.append(c + radial * (R + thick))
            inner.append(c + radial * R)
        ring = outer + inner[::-1]
        if i == len(us) - 1 and broken:
            # Broken off ragged, or split down the middle
            ring = [p - D * (abs(jag[q]) * 0.004 * broken) for q, p in enumerate(ring)]
        if i == len(us) - 1 and split:
            ring = [p - D * (0.007 if q in (1, 2, 5, 6) else 0.0) for q, p in enumerate(ring)]
        rings.append(ring)
        tt = (u + 0.017) / (0.02 + ext)
        attrs.append([(q / (2 * m), tt, seed) for q in range(2 * m)])
    start = (sum(rings[0], Vector()) / len(rings[0]) - d * 0.001, (0.5, 0.0, seed))
    end = (sum(rings[-1], Vector()) / len(rings[-1]) + D * 0.0005, (0.5, 1.0, seed))
    return loft("Nail%s%s" % (side, finger), rings, attrs, nailm, start=start, end=end, smooth=55)


def finger_joints(side, finger, seed):
    """The middle joint swollen into a knot over its back and sides (a Bouchard's node), the last joint knobbed with
    two little nodes either side (Heberden's)."""
    rp = RADII[finger]
    big = {"Index": 1.15, "Middle": 1.15, "Thumb": 1.2}.get(finger, 1.0)
    p, d, n, lat = finger_frame(side, finger, 2)
    r = (rp[0] + rp[1]) / 2 * big
    out = [lump("Pip%s%s" % (side, finger), p + n * (r * 0.42) + d * 0.002, (d, lat, n),
                (0.0135 * big, r * 1.26, r * 0.98), skin, seed, u=10, v=7, knots=0.2, freq=1.8)]
    p3, d3, n3, lat3 = finger_frame(side, finger, 3)
    r3 = (rp[1] + rp[2]) / 2 * big
    out.append(lump("Dip%s%s" % (side, finger), p3 + n3 * (r3 * 0.5) + d3 * 0.001, (d3, lat3, n3),
                    (0.0085 * big, r3 * 1.08, r3 * 0.74), skin, seed + 0.3, u=8, v=5, knots=0.15, lobes=0.6))
    return out


# ---------------------------------------------------------------- build

pieces = []
EXT = {"Index": 0.03, "Middle": 0.035, "Ring": 0.029, "Pinky": 0.022, "Thumb": 0.027}
BROKEN = {("Left", "Middle"): 1.0, ("Left", "Pinky"): 0.8, ("Right", "Index"): 1.0, ("Right", "Ring"): 0.9,
          ("Right", "Thumb"): 0.7}
SPLIT = {("Left", "Index"), ("Right", "Middle")}
SHORT = {("Left", "Ring"): 0.45, ("Right", "Pinky"): 0.5}
seed = 0.0
for side in SIDES:
    for o in back_of_hand(side, 0.7 if side == "Left" else 2.9) + wrist(side, 1.9 if side == "Left" else 4.4):
        pieces.append(zk.on(o, side + "Hand", "Knuckles"))
    for finger in FINGERS:
        seed += 0.173
        ext = EXT[finger] * rnd.uniform(0.9, 1.1) * SHORT.get((side, finger), 1.0)
        objs = finger_joints(side, finger, seed)
        objs.append(nail(side, finger, seed, ext, BROKEN.get((side, finger), 0.25), (side, finger) in SPLIT))
        for o in objs:
            pieces.append(zk.on(o, bone(side, finger, 2), "Nail"))


# ---------------------------------------------------------------- a better stand-in hand (previews only)

def taper(name, a, b, ra, rb, mat, seg=16):
    bm = bmesh.new()
    length = (b - a).length
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=ra, radius2=rb, depth=length)
    for r, z in ((ra, -length / 2), (rb, length / 2)):
        s = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=8, radius=r)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=s["verts"])
    obj = tk.mesh_object(name, bm, mat)
    turn = (b - a).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation((a + b) / 2) @ turn
    return tk.smooth(obj, 60)


def standin_hands():
    """The stand-in's forearm capsules are fat and reach over half the hand, and its hand is a single capsule, so
    for these previews they're swapped for a slimmer forearm, a tapered hand and jointed fingers."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] in ("LeftForeArm", "RightForeArm"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    for nm in ("BodyLeftHand", "BodyRightHand"):
        bpy.data.objects.remove(bpy.data.objects[nm])
    for side in SIDES:
        H, ax, nh, lat = hand_frame(side)
        fa = sk.pos(side + "ForeArm")
        rings = []
        for k in range(6):
            f = k / 5
            w, th = 0.04 + (0.03 - 0.04) * f, 0.04 + (0.024 - 0.04) * f
            c = fa.lerp(hand_axis(side, -0.004), f)
            rings.append([c + nh * (math.cos(2 * math.pi * q / 16) * th) + lat * (math.sin(2 * math.pi * q / 16) * w)
                          for q in range(16)])
        loft("Pre%sForeArm" % side, rings, [[(0, 0, 0)] * 16] * 6, mat,
             start=(fa - (H - fa).normalized() * 0.03, (0, 0, 0)), smooth=60)
        k1 = [sk.pos(bone(side, f, 1)) for f in ("Index", "Middle", "Ring", "Pinky")]
        mid_lat = ((k1[0] + k1[3]) / 2 - H).dot(lat)
        rings, attrs = [], []
        for x, w, th in PALM:
            f = max(0.0, min(1.0, x / 0.08))
            c = H + ax * x + lat * (mid_lat * f) - nh * PALM_DROP
            ring = []
            for q in range(20):
                a = 2 * math.pi * q / 20
                ca, sa = math.cos(a), math.sin(a)
                # a rounded rectangle
                e = 3.0
                rr = (abs(ca) ** e + abs(sa) ** e) ** (-1.0 / e)
                ring.append(c + nh * (ca * rr * th) + lat * (sa * rr * w))
            rings.append(ring)
            attrs.append([(0, 0, 0)] * 20)
        loft("Pre%sPalm" % side, rings, attrs, mat, start=(sum(rings[0], Vector()) / 20 - ax * 0.008, (0, 0, 0)),
             end=(sum(rings[-1], Vector()) / 20 + ax * 0.004, (0, 0, 0)), smooth=60)
        taper("Pre%sThenar" % side, H + ax * 0.02 - nh * 0.006, sk.pos(bone(side, "Thumb", 2)), 0.02, 0.013, mat)
        for f in FINGERS:
            r = RADII[f]
            for k in range(1, 4):
                taper("Pre%s%s%d" % (side, f, k), sk.pos(bone(side, f, k)), sk.pos(bone(side, f, k + 1)),
                      r[k - 1], r[min(k, 2)], mat, seg=12)


def report(name, pieces):
    groups = {}
    for p in pieces:
        groups.setdefault(p["zbone"], []).append(p)
    lo_all = Vector((9, 9, 9))
    hi_all = Vector((-9, -9, -9))
    for label, objs in groups.items():
        lo = Vector((9, 9, 9))
        hi = Vector((-9, -9, -9))
        tris = 0
        for o in objs:
            for v in o.data.vertices:
                p = o.matrix_world @ v.co
                lo = Vector(map(min, lo, p))
                hi = Vector(map(max, hi, p))
            tris += sum(len(f.vertices) - 2 for f in o.data.polygons)
        lo_all = Vector(map(min, lo_all, lo))
        hi_all = Vector(map(max, hi_all, hi))
        print("[%s] %-24s %5d tris  min (%.3f, %.3f, %.3f)  max (%.3f, %.3f, %.3f)"
              % ((name, label, tris) + tuple(lo) + tuple(hi)))
    print("[%s] all bounds min (%.3f, %.3f, %.3f) max (%.3f, %.3f, %.3f)" % ((name,) + tuple(lo_all) + tuple(hi_all)))


report("gnarled_hands", pieces)
standin_hands()
parts = zk.export("GnarledHands", pieces, ASSETS)
zk.previews("gnarled_hands", PREVIEWS, Vector((0.0, -0.02, 1.12)), distance=2.5)


def closeup(name, focus, direction, dist=0.36, lens=50):
    cam = tk.camera(name, focus + Vector(direction).normalized() * dist, focus, lens=lens)
    tk.render(cam, os.path.join(PREVIEWS, "%s.png" % name), res=(900, 900), samples=64)


for side, s in (("Left", 1.0), ("Right", -1.0)):
    focus = sk.pos(side + "Hand").lerp(sk.pos(bone(side, "Middle", 4)), 0.45)
    closeup("gnarled_hands_%s_top" % side.lower(), focus, (0.8 * s, -0.25, 0.75), dist=0.4)
    closeup("gnarled_hands_%s_front" % side.lower(), focus, (0.4 * s, -1.0, 0.1), dist=0.4)
closeup("gnarled_hands_left_knuckles", sk.pos("LeftHand").lerp(sk.pos("LeftHandMiddle1"), 0.7),
        (0.9, 0.35, 0.55), dist=0.2)
closeup("gnarled_hands_left_wrist", sk.pos("LeftHand"), (0.3, -0.9, 0.5), dist=0.2)
closeup("gnarled_hands_left_nails", sk.pos("LeftHandMiddle3"), (0.75, -0.55, 0.1), dist=0.2)
print("[gnarled_hands] done")
