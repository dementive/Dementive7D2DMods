"""Flower lei (remnant): a Hawaiian lei of cheap fabric flowers, long wilted and filthy, still round the neck. Forty
five-petal flowers threaded on a cord, each tilted out from the cord so the garland reads as flowers from the front,
lying round the base of the neck on the shoulders and hanging down the chest in a broad U. Dull magenta, faded
orange, and white gone grey, the petals limp and drooping at the tips, crumpled, frayed at the edges, the satin
dulled with grime and dust, a few stained with dried blood. Petals pressed against the body lie flat on it.

The petals are two-sided cards (the game culls back faces). Fitted to Joe's neck and chest as the other neck pieces
assume them (a 5.5 cm neck column and the chest hit box with its top lowered 5 cm to the shoulders), lifted a little
more off the chest lower down so it still lies on the nurse's chest when the game sizes the part by her head (the fat
cop's chest sits far in front of Joe's, and a Neck part isn't moved to it). Clear of the jaw when it opens. One part
on the Neck bone: "Neck#Lei".

    blender -b --factory-startup --python flower_lei.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT = "FlowerLei", "flower_lei"
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

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
RND = random.Random(808)
EYES = (Vector((0.032, -0.075, 1.719)), Vector((-0.032, -0.075, 1.719)))
JAW_PIVOT = SK.pos("Jaw")
UP = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------- helpers

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def set_attr(obj, name, vals):
    me = obj.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def catmull(ctrl, per=8, closed=False):
    P = [Vector(c) for c in ctrl]
    n = len(P)
    E = (P[-1:] + P + P[:2]) if closed else ([P[0]] + P + [P[-1]])
    out = []
    for i in range(1, (n + 1 if closed else n)):
        p0, p1, p2, p3 = E[i - 1], E[i], E[i + 1], E[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    if not closed:
        out.append(P[-1])
    return out


def arclen(P, closed=False):
    s = [0.0]
    for i in range(1, len(P)):
        s.append(s[-1] + (P[i] - P[i - 1]).length)
    if closed:
        s.append(s[-1] + (P[0] - P[-1]).length)
    return s


def resample_closed(P, step):
    """Points evenly spaced round a closed polyline, as near `step` apart as a whole number allows."""
    S = arclen(P, closed=True)
    n = max(3, int(round(S[-1] / step)))
    out, k = [], 0
    Q = P + [P[0]]
    for i in range(n):
        s = S[-1] * i / n
        while k < len(S) - 2 and S[k + 1] < s:
            k += 1
        t = (s - S[k]) / max(S[k + 1] - S[k], 1e-9)
        out.append(Q[k].lerp(Q[k + 1], t))
    return out, S[-1] / n


def blob(name, center, radii, mat, exps=(2.0, 2.0), rot_x=0.0, segs=28, rings=18):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    nh, nv = exps
    for v in bm.verts:
        d = v.co.normalized()
        f = ((abs(d.x) / radii[0]) ** nh + (abs(d.y) / radii[1]) ** nh) ** (nv / nh) + (abs(d.z) / radii[2]) ** nv
        v.co = d * f ** (-1.0 / nv)
    if rot_x:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot_x), 3, "X"))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return tk.mesh_object(name, bm, mat)


def face_proxy():
    """Joe's real head, neck and chest (as sunglasses.py makes them, the chest about 2 cm inside the hit box), for
    the previews and the jaw check. Not exported."""
    mat, g = tk.new_material("ProxySkin")
    tk.finish(mat, g, (0.46, 0.38, 0.34), 0.0, 0.65)
    parts = [
        blob("Cranium", (0.0, 0.02, 1.737), (0.076, 0.1, 0.107), mat, (2.8, 2.6)),
        blob("Brow", (0.0, -0.062, 1.745), (0.052, 0.024, 0.011), mat, (2.4, 2.0)),
        blob("Midface", (0.0, -0.03, 1.674), (0.062, 0.064, 0.06), mat, (2.4, 2.0)),
        blob("Jaw", (0.0, -0.02, 1.628), (0.053, 0.066, 0.045), mat, (2.4, 2.0)),
        blob("Chin", (0.0, -0.077, 1.611), (0.022, 0.017, 0.017), mat),
        blob("Lips", (0.0, -0.083, 1.646), (0.025, 0.017, 0.013), mat),
        blob("Neck", (0.0, 0.035, 1.56), (0.054, 0.058, 0.11), mat, (2.0, 3.0), rot_x=8.0),
        blob("Torso", (0.0, 0.04, 1.35), (0.165, 0.135, 0.19), mat, (2.3, 2.6)),
    ]
    for s in (1.0, -1.0):
        parts.append(blob("Cheek", (s * 0.047, -0.056, 1.699), (0.02, 0.022, 0.015), mat))
        parts.append(blob("Ear", (s * 0.076, 0.03, 1.70), (0.011, 0.02, 0.03), mat, rot_x=-10.0))
    nose = [(0.0, -0.087, 1.735), (0.0, -0.092, 1.722), (0.0, -0.112, 1.69), (0.0, -0.12, 1.683),
            (0.0, -0.116, 1.672), (0.0, -0.098, 1.664)]
    for s in (1.0, -1.0):
        nose += [(s * 0.016, -0.098, 1.671), (s * 0.018, -0.088, 1.676), (s * 0.009, -0.088, 1.716),
                 (s * 0.013, -0.08, 1.70), (s * 0.007, -0.112, 1.683), (s * 0.006, -0.08, 1.73)]
    bm = bmesh.new()
    for p in nose:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    parts.append(tk.mesh_object("Nose", bm, mat))
    obj = tk.join(parts, "FaceProxy")
    mod = obj.modifiers.new("Remesh", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = 0.003
    tk.apply_modifiers(obj)
    mod = obj.modifiers.new("Smooth", "SMOOTH")
    mod.factor = 0.8
    mod.iterations = 6
    tk.apply_modifiers(obj)
    tk.smooth(obj, 60)
    obj["zbody"] = True
    return obj


# ---------------------------------------------------------------- Joe's neck and chest, as the lei lies on it

NECK_AXIS, NECK_R = Vector((0.0, 0.032, 0.0)), 0.055
_c = SK.collider("Spine2")
_ax = Vector((0.0, 0.0, 0.0))
_ax[_c["axis"]] = 1.0
_half = max(0.0, _c["height"] / 2 - _c["radius"])
CHEST_A = SK.point("Spine2", Vector(_c["center"]) - _ax * _half)
CHEST_B = SK.point("Spine2", Vector(_c["center"]) + _ax * _half) - Vector((0.0, 0.0, 0.05))
CHEST_R = _c["radius"]

# How far the lei stands off the fitted chest, by height: snug at the collarbones, lifted lower down
# where the nurse's chest (sized by her head) comes out in front of Joe's (from the depth probes on the real zombies)
LIFT = ((1.47, 0.002), (1.44, 0.006), (1.41, 0.0105), (1.38, 0.015), (1.35, 0.02))


def lift(z):
    if z >= LIFT[0][0]:
        return LIFT[0][1]
    for (z0, l0), (z1, l1) in zip(LIFT, LIFT[1:]):
        if z >= z1:
            return l0 + (l1 - l0) * smoothstep(z0, z1, z)
    return LIFT[-1][1]


def chest_sd(q):
    ab = CHEST_B - CHEST_A
    t = max(0.0, min(1.0, (q - CHEST_A).dot(ab) / ab.length_squared))
    c = CHEST_A + ab * t
    return (q - c).length - CHEST_R, (q - c).normalized()


def neck_sd(q):
    d = Vector((q.x - NECK_AXIS.x, q.y - NECK_AXIS.y, 0.0))
    return d.length - NECK_R, d.normalized()


def drape(q, off):
    """Moves q onto the surface `off` outside the neck and chest (whichever it lies on)."""
    q = q.copy()
    for _ in range(14):
        sc, nc = chest_sd(q)
        sn, nn = neck_sd(q)
        if sn < sc and sn < off:
            q += nn * (off - sn)
            continue
        q += nc * (off - sc)
    return q


def body_normal(p):
    sc, nc = chest_sd(p)
    sn, nn = neck_sd(p)
    return nn if sn < sc else nc


def neck_ring(b, rho, off):
    """Round the back of the neck (b: 0 front, + the zombie's left) at `rho` from the neck's axis, resting on the
    shoulders `off` above the lowered chest."""
    d = Vector((math.sin(b), -math.cos(b), 0.0))
    p = NECK_AXIS + d * rho
    c = CHEST_B
    h = math.hypot(p.x - c.x, p.y - c.y)
    p.z = c.z + math.sqrt(max(0.0, (CHEST_R + off) ** 2 - h * h))
    return p


# ---------------------------------------------------------------- materials

def attr(g, name):
    n = g.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name)
    return tk._sock(n.outputs, "Vector")


def mapping(g, vec, scale=(1.0, 1.0, 1.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def white(g, vec):
    n = g.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Value")


def vsub(g, a, b):
    n = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(a, n.inputs[0])
    g.links.new(b, n.inputs[1])
    return n.outputs[0]


def vnorm(g, a):
    n = g.node("ShaderNodeVectorMath", operation="NORMALIZE")
    g.links.new(a, n.inputs[0])
    return n.outputs[0]


def mul(g, a, b):
    return g.math("MULTIPLY", a, b)


def add(g, a, b):
    return g.math("ADD", a, b)


def sub(g, a, b):
    return g.math("SUBTRACT", a, b)


def body_sd(q):
    """Distance outside Joe's fitted neck and chest (the nearer of the two)."""
    sc = chest_sd(q)[0]
    if 1.44 < q.z < 1.70:
        return min(sc, neck_sd(q)[0])
    return sc


def front_project(x, z, off):
    """The point at (x, z) `off` in front of the fitted neck and chest, seen from the front."""
    y = -0.4
    while body_sd(Vector((x, y, z))) > off and y < 0.2:
        y += 0.002
    lo, hi = y - 0.002, y
    for _ in range(20):
        mid = (lo + hi) / 2
        if body_sd(Vector((x, mid, z))) > off:
            lo = mid
        else:
            hi = mid
    return Vector((x, (lo + hi) / 2, z))


def bezier2(a, c, b, n):
    return [(a[0] * (1 - t) ** 2 + c[0] * 2 * (1 - t) * t + b[0] * t * t,
             a[1] * (1 - t) ** 2 + c[1] * 2 * (1 - t) * t + b[1] * t * t) for t in [k / n for k in range(1, n)]]


# ---------------------------------------------------------------- the garland's cord

FR = 0.025  # flower radius (5 cm flowers)
RHO = 0.077  # the cord round the back of the neck, from the neck's axis
LEAVE = 72.0  # where it leaves the neck for the chest (degrees either side of the front)
BOTTOM = (0.006, 1.386)  # the U's bottom
CORD_OFF = 0.013  # the cord off the fitted surface (the flowers' backs are pressed flat against it)


def cord_off(z):
    return CORD_OFF + lift(z)


def cord_path():
    b0 = math.radians(LEAVE)
    back = [neck_ring(b0 + (2 * math.pi - 2 * b0) * k / 16, RHO, CORD_OFF) for k in range(17)]
    bx, bz = BOTTOM
    left, right = back[0], back[-1]
    leg_r = bezier2((right.x, right.z), (right.x * 1.0, right.z - 0.05), (bx - 0.04, bz + 0.016), 9)
    leg_l = bezier2((left.x, left.z), (left.x * 1.0, left.z - 0.05), (bx + 0.04, bz + 0.016), 9)
    u = [(bx - 0.027, bz + 0.0065), (bx - 0.01, bz + 0.0008), (bx + 0.01, bz + 0.0008), (bx + 0.027, bz + 0.0065)]
    front2d = leg_r + u + list(reversed(leg_l))
    n = len(front2d)
    front2d = [(x - 0.006 * math.sin(math.pi * i / (n - 1)), z) for i, (x, z) in enumerate(front2d)]
    front = [front_project(x, z, cord_off(z)) for x, z in front2d]
    dense = catmull(back + front, 6, closed=True)
    return [front_project(q.x, q.z, cord_off(q.z)) if q.y < -0.004 else q for q in dense]


# ---------------------------------------------------------------- the flowers

PALETTE = [0, 0, 1, 2, 1, 0, 2, 0, 1, 1, 2, 0]  # magenta, orange, grey-white


def flower(bm, vals, c, T, Nb, k):
    """A five-petal fabric flower threaded on the cord at c (cord direction T, body normal Nb), its face tilted out
    from the cord; limp petals drooping at the tips, flattened where they'd go into the body. Two-sided."""
    tilt = (1.0 if k % 2 == 0 else -1.0) * RND.uniform(0.45, 0.7)
    F = (T * tilt + Nb * 1.0 + Vector((RND.uniform(-0.2, 0.2), RND.uniform(-0.2, 0.2), RND.uniform(-0.1, 0.25)))).normalized()
    a = (Nb - F * Nb.dot(F))
    if a.length < 1e-4:
        a = T - F * T.dot(F)
    a.normalize()
    b = F.cross(a)
    spin = RND.uniform(0.0, 2 * math.pi)
    r = FR * RND.uniform(0.88, 1.08)
    color = PALETTE[k % len(PALETTE)] if RND.random() > 0.2 else RND.choice((0, 1, 2))
    rid = RND.random()
    droop = RND.uniform(0.4, 1.0)
    center = c + F * 0.004
    for i in range(5):
        th = spin + 2 * math.pi * i / 5 + RND.uniform(-0.12, 0.12)
        e = a * math.cos(th) + b * math.sin(th)
        w = F.cross(e)
        rr = r * RND.uniform(0.85, 1.05)
        lay = 0.0006 * i  # stacked petals, so they don't fight where they overlap

        def pt(t, s):
            """t along the petal 0-1, s across (in petal lengths); cupped, pinwheeled, the tip drooping."""
            p = center + e * (t * rr) + w * (s * rr) + w * (0.1 * rr * t * t)
            p = p + F * (lay + 0.18 * rr * t * (1 - t) - 0.45 * rr * droop * t ** 2.2)
            p = p - UP * (0.25 * rr * droop * t ** 2.5)
            p = p + F * (0.02 * rr * math.sin(9 * s + 3 * i) * t)  # crumpled
            return p
        ring = [(0.0, 0.0), (0.48, -0.37), (0.95, -0.2), (0.95, 0.22), (0.48, 0.38)]
        P = [pt(t, s) for t, s in ring]
        # Pressed flat where the petal would go into the body (on the front of the chest, Joe's real chest is about a
        # centimeter inside the fitted one, so petals may reach back to it there)
        for j, p in enumerate(P):
            d = body_sd(p)
            clear = 0.003 - 0.011 * smoothstep(1.48, 1.42, p.z) * smoothstep(-0.05, -0.08, p.y)
            if d < clear:
                P[j] = p + body_normal(p) * (clear - d)
        front = [bm.verts.new(p) for p in P]
        back = [bm.verts.new(p - F * 0.0007) for p in P]
        for (t, s) in ring:
            vals["fl"].append((t, float(color), 1.0))
            vals["fp"].append((s, t, rid))
        for (t, s) in ring:
            vals["fl"].append((t, float(color), -1.0))
            vals["fp"].append((s, t, rid))
        for tri in ((0, 1, 2), (0, 2, 3), (0, 3, 4)):
            f = bm.faces.new([front[j] for j in tri])
            f.normal_update()
            if f.normal.dot(F) < 0:
                f.normal_flip()
            g = bm.faces.new([back[j] for j in reversed(tri)])
            g.normal_update()
            if g.normal.dot(F) > 0:
                g.normal_flip()


def lei_mesh(mat):
    path = cord_path()
    centers, pitch = resample_closed(path, 0.0185)
    bm = bmesh.new()
    vals = {"fl": [], "fp": []}
    for k, c in enumerate(centers):
        T = (centers[(k + 1) % len(centers)] - centers[k - 1]).normalized()
        Nb = body_normal(c)
        Nb = (Nb - T * Nb.dot(T)).normalized()
        flower(bm, vals, c, T, Nb, k)
    obj = tk.mesh_object("Lei", bm, mat)
    set_attr(obj, "fl", vals["fl"])
    set_attr(obj, "fp", vals["fp"])
    print("[%s] %d flowers, %.0f cm round, bottom at z %.3f" % (SCRIPT, len(centers), pitch * len(centers) * 100,
                                                                min(c.z for c in centers)))
    return tk.smooth(obj, 50), centers


def lei_material():
    """Cheap satin-polyester flowers: dull magenta, faded orange, white gone grey (from fl.y), a yellowed throat,
    printed veins, creases, frayed and darkened edges, grime and dust, blood on a few; the backs darker."""
    mat, g = tk.new_material("LeiFabric")
    t, cid, side = g.separate(attr(g, "fl"))
    s, _, rid = g.separate(attr(g, "fp"))
    W = g.coords()
    P = mapping(g, W, loc=(0.7, 1.9, 0.3))
    magenta, orange, grey = (0.08, 0.015, 0.038), (0.14, 0.042, 0.011), (0.115, 0.108, 0.095)
    col = g.mix(g.ramp(cid, 0.4, 0.6), magenta, orange)
    col = g.mix(g.ramp(cid, 1.4, 1.6), col, grey)
    col = g.mix(mul(g, sub(g, rid, 0.5), 0.5), col, tk._darker(g, col, 0.6))
    # Faded where the sun got at it, unevenly
    fade = mul(g, g.ramp(g.noise(14.0, detail=4.0, vector=P), 0.4, 0.7), 0.5)
    col = g.mix(fade, col, tk.grade(g, col, 0.6, 1.05))
    # The throat: yellowed toward the center, darker on the magenta ones
    throat = g.ramp(t, 0.32, 0.05)
    col = g.mix(mul(g, throat, 0.75), col, g.mix(g.ramp(cid, 0.4, 0.6), (0.035, 0.007, 0.017), (0.12, 0.08, 0.02)))
    # Printed veins and creases along the petal
    veins = g.ramp(g.math("ABSOLUTE", g.math("SINE", mul(g, s, 26.0))), 0.95, 1.0)
    col = g.mix(mul(g, mul(g, veins, g.ramp(t, 0.1, 0.4)), 0.25), col, tk._darker(g, col, 0.55))
    crease = g.ramp(g.noise(1.0, detail=2.0, vector=mapping(g, P, scale=(160.0, 160.0, 160.0))), 0.62, 0.7)
    col = g.mix(mul(g, crease, 0.4), col, tk._darker(g, col, 0.5))
    # Frayed, grimy edges and tips
    edge = g.math("MAXIMUM", g.ramp(t, 0.82, 0.97), g.ramp(g.math("ABSOLUTE", s), 0.25, 0.38))
    fray = mul(g, edge, g.ramp(g.noise(300.0, detail=3.0, vector=P), 0.35, 0.6))
    col = g.mix(mul(g, fray, 0.7), col, (0.045, 0.036, 0.028))
    rough = add(g, 0.6, mul(g, g.noise(40.0, vector=P), 0.15))
    # Dirt in blotches, dust, the backs darker
    dirt = mul(g, g.ramp(g.noise(9.0, detail=6.0, roughness=0.65, distortion=0.5, vector=P), 0.5, 0.72), 0.75)
    col = g.mix(dirt, col, (0.05, 0.04, 0.03))
    rough = g.mixf(dirt, rough, 0.85)
    backs = g.ramp(side, 0.0, -0.5)
    col = g.mix(mul(g, backs, 0.5), col, tk._darker(g, col, 0.5))
    blood = mul(g, g.ramp(g.noise(5.0, detail=6.0, distortion=1.0, vector=P), 0.6, 0.68),
                g.ramp(g.noise(60.0, detail=4.0, vector=P), 0.35, 0.55))
    col = g.mix(blood, col, (0.045, 0.006, 0.004))
    rough = g.mixf(blood, rough, 0.4)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.35)
    col = tk.grade(g, col, 0.8, 0.85)
    height = add(g, mul(g, veins, 0.3), add(g, mul(g, crease, -0.6), mul(g, g.noise(400.0, detail=3.0, vector=P), 0.3)))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.001))


LEI = lei_material()
lei, CENTERS = lei_mesh(LEI)
pieces = [lei]
zk.on(lei, "Neck", "Lei")

# ---------------------------------------------------------------- checks

PROXY = face_proxy()


def jaw_clearance():
    rot = Matrix.Translation(JAW_PIVOT) @ Matrix.Rotation(math.radians(18.0), 4, "X") @ Matrix.Translation(-JAW_PIVOT)
    pts = []
    for (c, r) in [((0.0, -0.077, 1.611), (0.022, 0.017, 0.017)), ((0.0, -0.02, 1.628), (0.053, 0.066, 0.045))]:
        for i in range(24):
            for j in range(1, 12):
                th, ph = 2 * math.pi * i / 24, math.pi * j / 12
                p = Vector((c[0] + r[0] * math.sin(ph) * math.cos(th), c[1] + r[1] * math.sin(ph) * math.sin(th),
                            c[2] + r[2] * math.cos(ph)))
                if p.y < 0.01:
                    pts.append(rot @ p)
    verts = [v.co for v in lei.data.vertices]
    best = min(((v - p).length, v) for v in verts for p in pts[::2])
    print("[%s] jaw open 18 deg: nearest petal %.1f cm away at (%.3f, %.3f, %.3f)" % (SCRIPT, best[0] * 100, *best[1]))


def chest_report():
    bm = bmesh.new()
    bm.from_mesh(PROXY.data)
    bvh = BVHTree.FromBMesh(bm)
    lo, hi = 9.0, -9.0
    inside = 0
    for v in lei.data.vertices:
        if v.co.z > 1.5 or v.co.y > 0.0:
            continue
        loc, nrm, _, d = bvh.find_nearest(v.co)
        gap = d if (v.co - loc).dot(nrm) > 0 else -d
        lo, hi = min(lo, gap), max(hi, gap)
        inside += gap < 0
    print("[%s] front petals off Joe's real chest (proxy): %.1f to %.1f cm, %d inside" % (SCRIPT, lo * 100, hi * 100, inside))


jaw_clearance()
chest_report()
print("[%s] %d triangles before export" % (SCRIPT, len(lei.data.polygons)))
if os.environ.get("ZED_DRY"):
    sys.exit(0)

hidden = [o for o in bpy.context.scene.objects if o.get("zbody")]
for o in hidden:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS, size=512)
for o in hidden:
    o.hide_render = False
for i, c in enumerate(SK.colliders):
    if c["bone"] in ("Head", "Spine2"):
        BODY[i].hide_render = True
focus = Vector((0.0, -0.03, 1.46))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.8)


def close_up(view, direction, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


close_up("close", (-0.35, -1.0, 0.15), Vector((0.0, -0.11, 1.42)), 0.28)
close_up("profile", (1.0, -0.15, 0.05), Vector((0.0, -0.05, 1.47)), 0.45)
print("[%s] done" % SCRIPT)
