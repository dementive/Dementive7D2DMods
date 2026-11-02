"""Claws: the Leaper's mutation. Long, hooked, yellowed claws have pushed out of all ten fingertips: each one grows
from the nail bed (the old nail torn away, the skin around it ripped and bloody), runs out past the fingertip and hooks
down toward the palm. They are cracked along their length, dark amber at the root and caked with dried blood toward the
tips; two have snapped off short.

Each claw rides on its finger's second bone (LeftHandIndex2 ... LeftHandThumb2) as its own part, "<Bone>#Claw".

    blender -b --factory-startup --python claws.py -- <unity models folder> <preview folder>
"""
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
ASSETS, PREVIEWS = os.path.join(args[0], "Claws"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

rnd = random.Random(5150)


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
# How far each claw reaches past the fingertip
LENGTH = {"Index": 0.078, "Middle": 0.085, "Ring": 0.076, "Pinky": 0.06, "Thumb": 0.064}


# ---------------------------------------------------------------- frames and mesh helpers

def mirror(v, side):
    return Vector((v.x, v.y, v.z)) if side == "Left" else Vector((-v.x, v.y, v.z))


def orth(v, axis):
    """v with its component along `axis` removed, normalized."""
    return (v - axis * v.dot(axis)).normalized()


def bone(side, finger, k):
    return "%sHand%s%d" % (side, finger, k)


def dorsal(side, finger):
    """The nail side of a finger (the back of the hand), from the left bone's local +Y, mirrored for the right."""
    b = bone("Left", finger, 2)
    return mirror((sk.point(b, (0.0, 1.0, 0.0)) - sk.pos(b)).normalized(), side)


def tip_frame(side, finger):
    """At the fingertip: the tip point, the direction the last segment points, the nail side and the side axis."""
    p3, p4 = sk.pos(bone(side, finger, 3)), sk.pos(bone(side, finger, 4))
    d = (p4 - p3).normalized()
    n = orth(dorsal(side, finger), d)
    return p4, d, n, d.cross(n)


def set_attr(obj, vals):
    """Per-vertex growth coordinates for the materials: (around 0-1, along 0-1, seed)."""
    me = obj.data
    at = me.attributes.new("gr", "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def loft(name, rings, attrs, mat, start=None, end=None, smooth=70):
    """A closed tube through `rings` (point loops of equal length); start/end close it to a point (point, attr)."""
    bm = bmesh.new()
    vals = []
    vr = []
    for ring, at in zip(rings, attrs):
        vr.append([bm.verts.new(p) for p in ring])
        vals += at
    m = len(rings[0])
    for A, B in zip(vr, vr[1:]):
        for j in range(m):
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


def strip(name, rows, attrs, mat, outward, smooth=80):
    """An open sheet through rows of points (each row the same length), its faces turned to face `outward(p)`."""
    bm = bmesh.new()
    vals = []
    vr = []
    for row, at in zip(rows, attrs):
        vr.append([bm.verts.new(p) for p in row])
        vals += at
    for A, B in zip(vr, vr[1:]):
        for j in range(len(A) - 1):
            bm.faces.new((A[j], A[j + 1], B[j + 1], B[j]))
    bm.normal_update()
    for f in bm.faces:
        if f.normal.dot(outward(f.calc_center_median())) < 0:
            f.normal_flip()
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, smooth)


def section(c, N, L, h, w, m, keel=0.42, flat=0.82):
    """A claw's cross-section: round on the back (N), pinched to a keel underneath."""
    pts = []
    for j in range(m):
        th = 2 * math.pi * j / m
        cy, sx = math.cos(th), math.sin(th)
        y = h * cy * (flat if cy < 0 else 1.0)
        x = w * sx * (1.0 - keel * max(0.0, -cy))
        pts.append(c + N * y + L * x)
    return pts


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
    """Thin wandering lines (the contour of a noise), 1 on a line."""
    n = g.noise(1.0, detail=detail, roughness=0.5, vector=vec)
    return g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), width, 0.0)


def claw_material(name):
    """Old yellowed horn: streaky along its grain, dark amber and bloody at the root, cracked, grimy in the cracks,
    caked with dried blood toward the tip, a little glossy."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    grain = g.noise(1.0, detail=4.0, roughness=0.6, vector=wrap(g, a, t, seed, 2.6, 1.1))
    fine = g.noise(1.0, detail=3.0, roughness=0.5, vector=wrap(g, a, t, seed, 9.0, 2.0))
    col = g.mix(g.ramp(grain, 0.3, 0.72), (0.43, 0.31, 0.13), (0.7, 0.6, 0.38))
    col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.4, 0.75), 0.35), col, (0.3, 0.2, 0.08))
    root = g.ramp(t, 0.42, 0.0)
    col = g.mix(g.math("MULTIPLY", root, 0.85), col, (0.2, 0.1, 0.045))
    # The worn tip is paler and dirtier
    tip = g.ramp(t, 0.7, 1.0)
    col = g.mix(g.math("MULTIPLY", tip, 0.5), col, (0.5, 0.45, 0.36))
    # Cracks: long ones along the grain, a few across
    crack_l = g.math("MULTIPLY", lines(g, wrap(g, a, t, seed, 1.6, 2.2), 0.03),
                     g.ramp(g.noise(1.0, vector=wrap(g, a, t, seed, 1.0, 3.0)), 0.4, 0.55))
    crack_t = g.math("MULTIPLY", lines(g, wrap(g, a, t, seed, 0.5, 11.0), 0.025),
                     g.ramp(g.noise(1.0, vector=wrap(g, a, t, seed, 1.3, 2.0)), 0.5, 0.62))
    crack = g.math("MAXIMUM", crack_l, crack_t)
    col = g.mix(crack, col, (0.07, 0.045, 0.025))
    # Fresh blood where it tore out of the finger, dried blood smeared out toward the tip
    # (running out along the grain in streaks, not a dipped band)
    fresh = g.math("MULTIPLY", g.ramp(t, g.math("ADD", 0.12, g.math("MULTIPLY", grain, 0.3)), -0.02),
                   g.ramp(g.noise(1.0, detail=5.0, vector=wrap(g, a, t, seed, 4.0, 3.0)), 0.36, 0.52))
    dried = g.math("MULTIPLY", g.ramp(t, 0.35, 0.85),
                   g.ramp(g.noise(1.0, detail=6.0, roughness=0.65, distortion=0.6,
                                  vector=wrap(g, a, t, seed, 1.8, 3.5)), 0.55, 0.66))
    col = g.mix(dried, col, (0.13, 0.03, 0.018))
    col = g.mix(fresh, col, (0.15, 0.011, 0.008))
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.006), clamp=True), 1.6, clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.05, 0.035, 0.02))
    rough = g.math("ADD", 0.34, g.math("MULTIPLY", fine, 0.14))
    rough = g.mixf(dried, rough, 0.55)
    rough = g.mixf(fresh, rough, 0.22)
    rough = g.mixf(g.math("MAXIMUM", crack, dirt), rough, 0.8)
    ridges = g.math("SINE", g.math("ADD", g.math("MULTIPLY", a, 2 * math.pi * 7.0), g.math("MULTIPLY", grain, 4.0)))
    height = g.math("ADD", g.math("MULTIPLY", ridges, 0.12), g.math("MULTIPLY", fine, 0.25))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.9))
    height = g.math("ADD", height, g.math("MULTIPLY", dried, 0.25))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.0006))


def nailbed_material(name):
    """Torn skin around the claw's root: raw red flesh and clotted blood at the torn edge (t = 0), bruised grey-purple
    skin where it goes back into the finger (t = 1)."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    n1 = g.noise(260.0, detail=5.0, distortion=0.4)
    raw = g.mix(g.ramp(n1, 0.35, 0.7), (0.15, 0.012, 0.01), (0.34, 0.045, 0.035))
    clot = g.ramp(g.noise(140.0, detail=6.0, roughness=0.7), 0.52, 0.66)
    raw = g.mix(clot, raw, (0.07, 0.008, 0.006))
    # Bruised, blood-smeared skin: dark, so it sits on any zombie's skin
    skin = g.mix(g.ramp(g.noise(90.0, detail=4.0), 0.3, 0.7), (0.2, 0.09, 0.085), (0.15, 0.09, 0.12))
    out = g.ramp(t, 0.4, 0.95)
    # Blood runs back over the skin in places
    smear = g.math("MULTIPLY", g.ramp(g.noise(1.0, vector=wrap(g, a, t, seed, 3.0, 2.0)), 0.45, 0.6), 0.85)
    col = g.mix(out, raw, g.mix(smear, skin, (0.16, 0.02, 0.015)))
    rough = g.mixf(out, g.math("ADD", 0.22, g.math("MULTIPLY", clot, 0.15)), 0.55)
    rough = g.mixf(g.math("MULTIPLY", smear, out), rough, 0.3)
    height = g.math("ADD", g.math("MULTIPLY", n1, 0.4), g.math("MULTIPLY", clot, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.35, 0.0006))


horn = claw_material("ClawHorn")
bed = nailbed_material("NailBed")


# ---------------------------------------------------------------- the claws

M = 10  # vertices around a claw


def claw(side, finger, seed, broken=False, notch=None):
    T, d, n, lat = tip_frame(side, finger)
    rd = RADII[finger][2]
    big = 1.12 if finger == "Thumb" else (0.85 if finger == "Pinky" else 1.0)
    L = LENGTH[finger] * rnd.uniform(0.93, 1.07)
    bend = math.radians(rnd.uniform(96.0, 118.0))
    splay = jit(0.005)
    h0, w0 = 0.0078 * big, 0.0072 * big

    def at(u, v, w):
        return T + d * u + n * v + lat * w

    rings, attrs = [], []

    def add(c, N, h, w, t):
        rings.append(section(c, N, lat, h, w, M))
        attrs.append([(j / M, t, seed) for j in range(M)])

    # The root, flat in the torn nail bed, then thickening over the fingertip
    for u, v, h, w, t in ((-0.017, rd - 0.0033, 0.0026 * big, 0.0062 * big, -0.25),
                          (-0.011, rd - 0.0028, 0.004 * big, 0.0074 * big, -0.15),
                          (-0.005, rd - 0.0032, 0.0055 * big, 0.0078 * big, -0.07)):
        add(at(u, v, 0.0), n, h, w, t)
    # Out past the tip, curling toward the palm: phi is the bend from straight ahead toward -n
    steps = 11
    end = L * (rnd.uniform(0.55, 0.68) if broken else 1.0)
    phi0 = math.radians(-7.0)
    pos = Vector((0.0, rd * 0.15, 0.0))  # (u, v, w)
    ds = end / steps
    s = 0.0
    for i in range(steps + 1):
        f = s / L
        phi = phi0 + (bend - phi0) * f ** 1.55
        tau = d * math.cos(phi) - n * math.sin(phi)
        N = d * math.sin(phi) + n * math.cos(phi)
        taper = (1.0 - f) ** 0.8
        h = h0 * taper * (1.0 + 0.12 * math.exp(-((f - 0.12) / 0.1) ** 2))
        w = w0 * (1.0 - f) ** 0.95
        c = at(pos.x, pos.y, pos.z + splay * f * f)
        if i == steps and not broken:
            break
        ring = section(c, N, lat, max(h, 0.0004), max(w, 0.0003), M)
        if notch is not None and i == notch:
            # A crack across the back: the top of this ring sinks in
            ring = [p - N * (0.32 * h * max(0.0, (p - c).dot(N) / h) ** 2) for p in ring]
        if broken and i == steps:
            # Snapped off: a jagged break
            ring = [p + tau * jit(0.0016) for p in ring]
        rings.append(ring)
        attrs.append([(j / M, f, seed) for j in range(M)])
        last_c, last_tau = c, tau
        pos += Vector((math.cos(phi), -math.sin(phi), 0.0)) * ds
        s += ds
    if broken:
        tip = (last_c - last_tau * 0.0006, (0.5, end / L, seed))
    else:
        f = 1.0
        tip_pt = at(pos.x, pos.y, pos.z + splay)
        tip = (tip_pt, (0.5, 1.0, seed))
    root = (at(-0.0195, rd - 0.0034, 0.0), (0.5, -0.3, seed))
    obj = loft("Claw%s%s" % (side, finger), rings, attrs, horn, start=root, end=tip, smooth=75)
    return obj, (T, d, n, lat, rd, big)


def nail_bed(side, finger, frame, seed):
    """Ragged torn skin around the claw's root, on the back of the fingertip: a lip of raw flesh hugging the claw
    that slopes back down under the finger's skin."""
    T, d, n, lat, rd, big = frame
    cols = 13
    rows, attrs = [], []
    # Ragged: mostly low, with a few torn flaps standing up
    lip_jag = [jit(1.0) ** 3 * 1.6 + jit(0.35) for _ in range(cols)]
    for r, (gh, gw, du, sink, t) in enumerate(((-0.0008, -0.0008, 0.0035, 0.0, 0.0),
                                               (0.0011, 0.0016, -0.0005, 0.0, 0.2),
                                               (0.0021, 0.0033, -0.0045, 0.5, 0.6),
                                               (0.003, 0.0048, -0.009, 1.0, 1.0))):
        row, at = [], []
        for i in range(cols):
            th = math.radians(-105.0 + 210.0 * i / (cols - 1))
            u = -0.008 + du
            vc = rd - 0.003
            h, w = 0.0048 * big, 0.0076 * big
            hh, ww = h + gh, w + gw
            if r == 1:
                hh += 0.0012 * lip_jag[i]
                ww += 0.0008 * lip_jag[i]
                u += 0.0012 * lip_jag[(i + 5) % cols]
            p = T + d * u + n * (vc + math.cos(th) * hh) + lat * (math.sin(th) * ww)
            if sink:
                # Down onto (just under) the finger's skin
                rel = p - T
                along = rel.dot(d)
                radial = rel - d * along
                target = rd - 0.0006
                if radial.length > target:
                    p = T + d * along + radial.normalized() * (radial.length + (target - radial.length) * sink)
            row.append(p)
            at.append((i / (cols - 1), t, seed))
        rows.append(row)
        attrs.append(at)
    center = T + d * -0.008 + n * (rd - 0.003)

    def outward(p):
        return (p - center) - d * (p - center).dot(d) * 0.3

    return strip("Bed%s%s" % (side, finger), rows, attrs, bed, outward)


pieces = []
seed = 0.0
# Two claws snapped off short, three with a crack across the back
BROKEN = {("Left", "Ring"), ("Right", "Index")}
NOTCH = {("Left", "Middle"): 5, ("Right", "Middle"): 7, ("Right", "Thumb"): 4}
for side in SIDES:
    for finger in FINGERS:
        seed += 0.137
        c, frame = claw(side, finger, seed, broken=(side, finger) in BROKEN, notch=NOTCH.get((side, finger)))
        b = nail_bed(side, finger, frame, seed)
        for o in (c, b):
            zk.on(o, bone(side, finger, 2), "Claw")
        pieces += [c, b]


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
    for these previews they're swapped for a slimmer forearm, a palm and jointed fingers."""
    skin = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] in ("LeftForeArm", "RightForeArm"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    for nm in ("BodyLeftHand", "BodyRightHand"):
        bpy.data.objects.remove(bpy.data.objects[nm])
    for side in SIDES:
        fa, hand = sk.pos(side + "ForeArm"), sk.pos(side + "Hand")
        taper("Pre%sForeArm" % side, fa, hand, 0.04, 0.029, skin)
        ax = (sk.pos(bone(side, "Middle", 1)) - hand).normalized()
        nh = orth(mirror((sk.point("LeftHand", (0, 1, 0)) - sk.pos("LeftHand")).normalized(), side), ax)
        lat = nh.cross(ax)
        k1 = [sk.pos(bone(side, f, 1)) for f in ("Index", "Middle", "Ring", "Pinky")]
        knuckles = sum(k1, Vector()) / 4
        length = (knuckles - hand).dot(ax) + 0.012
        width = abs((k1[0] - k1[3]).dot(lat)) + 0.024
        palm = tk.box("Pre%sPalm" % side, (length, width, 0.028), (0, 0, 0), skin, bevel_width=0.009)
        mid = hand + ax * (length / 2 - 0.004) + lat * ((k1[0] + k1[3]) / 2 - hand).dot(lat) - nh * 0.003
        palm.matrix_world = Matrix.Translation(mid) @ Matrix((ax, lat, nh)).transposed().to_4x4()
        taper("Pre%sThenar" % side, hand + ax * 0.02 - nh * 0.006, sk.pos(bone(side, "Thumb", 2)), 0.02, 0.013, skin)
        for f in FINGERS:
            r = RADII[f]
            for k in range(1, 4):
                taper("Pre%s%s%d" % (side, f, k), sk.pos(bone(side, f, k)), sk.pos(bone(side, f, k + 1)),
                      r[k - 1], r[min(k, 2)], skin, seg=12)


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


report("claws", pieces)
standin_hands()
parts = zk.export("Claws", pieces, ASSETS)
zk.previews("claws", PREVIEWS, Vector((0.0, -0.02, 1.12)), distance=2.5)


def closeup(name, focus, direction, dist=0.36, lens=50):
    cam = tk.camera(name, focus + Vector(direction).normalized() * dist, focus, lens=lens)
    tk.render(cam, os.path.join(PREVIEWS, "%s.png" % name), res=(900, 900), samples=64)


for side, s in (("Left", 1.0), ("Right", -1.0)):
    focus = sk.pos(side + "Hand").lerp(sk.pos(bone(side, "Middle", 4)), 0.85)
    closeup("claws_%s_front" % side.lower(), focus, (0.45 * s, -1.0, 0.15), dist=0.42)
    closeup("claws_%s_top" % side.lower(), focus, (0.8 * s, -0.35, 0.75), dist=0.42)
closeup("claws_left_under", sk.pos("LeftHand").lerp(sk.pos("LeftHandMiddle4"), 0.8), (-0.35, -0.7, -0.6), dist=0.42)
closeup("claws_left_thumb", sk.pos("LeftHandThumb4"), (0.2, -1.0, -0.25), dist=0.22)
closeup("claws_left_tips", sk.pos("LeftHandMiddle4") + Vector((0.01, -0.02, -0.02)), (0.9, -0.6, 0.1), dist=0.2)
print("[claws] done")
