"""Mardi Gras beads (remnant): three strands of cheap throw beads still round the neck from the last parade. Each is a
loop of big round metallized plastic beads (16 and 19 mm) lying round the base of the neck on the trapezius and hanging down the chest
in a U, to different lengths: purple close under the throat, gold lower, a strand of bigger green beads lowest. The
longer ones lie over the shorter where they cross. Tarnished and grimy: the purple and green gone dark,
the gold dull brass, the metal coating rubbed off some beads to the grey plastic, dirt packed where the beads touch,
a few spots of dried blood.

The beads are low-poly (ten triangles each) with a rounded normal baked in, so they read as round. Fitted to Joe's
neck and chest as the other neck pieces assume them (a 5.5 cm neck column and the chest hit box with its top lowered
5 cm to the shoulders), and lifted a little more off the chest lower down so they still lie on the nurse's chest when
the game sizes the part by her head (the fat cop's chest sits far in front of Joe's, and a Neck part isn't moved to
it). Clear of the jaw when it opens. One part on the Neck bone: "Neck#Beads".

    blender -b --factory-startup --python mardi_gras_beads.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT = "MardiGrasBeads", "mardi_gras_beads"
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
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
RND = random.Random(1857)
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


# ---------------------------------------------------------------- Joe's neck and chest, as the beads lie on them

NECK_AXIS, NECK_R = Vector((0.0, 0.032, 0.0)), 0.055
_c = SK.collider("Spine2")
_ax = Vector((0.0, 0.0, 0.0))
_ax[_c["axis"]] = 1.0
_half = max(0.0, _c["height"] / 2 - _c["radius"])
CHEST_A = SK.point("Spine2", Vector(_c["center"]) - _ax * _half)
CHEST_B = SK.point("Spine2", Vector(_c["center"]) + _ax * _half) - Vector((0.0, 0.0, 0.05))
CHEST_R = _c["radius"]

# How far the beads' surface stands off the fitted chest, by height: snug at the collarbones, lifted lower down
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


def bead_material(name, metal_col, seed):
    """Metallized plastic beads: a colored metal film (tarnished, darker on some beads), rubbed through to grey
    plastic on a few, grime packed where neighbors touch (bd.x near the poles), dust, specks and a little blood.
    The normal is the bead's sphere (from its center, bc), so the low-poly beads shade round."""
    mat, g = tk.new_material(name)
    W = g.coords()
    bc = attr(g, "bc")
    bx, rid, _ = g.separate(attr(g, "bd"))
    P = mapping(g, W, loc=(seed * 1.3, seed * 0.7, seed * 2.1))
    per = white(g, mapping(g, bc, scale=(97.0, 97.0, 97.0), loc=(seed, 0.0, 0.0)))  # one random value per bead
    per2 = white(g, mapping(g, bc, scale=(53.0, 53.0, 53.0), loc=(0.0, seed, 0.3)))
    base = g.mix(per, tk._darker(g, metal_col, 0.55), metal_col)
    tone = g.noise(220.0, detail=4.0, vector=P)
    col = g.mix(mul(g, tone, 0.3), base, tk._darker(g, base, 0.7))
    rough = add(g, 0.26, mul(g, per2, 0.16))
    metal = 0.85
    # Tarnish: a brown film in blotches over most beads
    tarn = mul(g, g.ramp(g.noise(60.0, detail=5.0, roughness=0.6, vector=P), 0.4, 0.7), 0.55)
    col = g.mix(tarn, col, (0.07, 0.05, 0.03))
    rough = g.mixf(tarn, rough, 0.55)
    # Coating rubbed off to the grey plastic on some beads (more on a few)
    rub_amt = g.ramp(per2, 0.86, 0.98)
    rub = mul(g, g.ramp(g.noise(140.0, detail=5.0, roughness=0.7, vector=P), 0.62, 0.55), rub_amt)
    col = g.mix(rub, col, (0.11, 0.105, 0.095))
    rough = g.mixf(rub, rough, 0.5)
    metal = g.mixf(rub, metal, 0.0)
    # Grime packed into the joints between beads (the poles), and in the creases generally
    joint = g.ramp(g.math("ABSOLUTE", bx), 0.55, 0.9)
    grime = g.math("MAXIMUM", joint, mul(g, g.ramp(g.noise(30.0, detail=6.0, vector=P), 0.55, 0.75), 0.7))
    col = g.mix(mul(g, grime, 0.85), col, (0.028, 0.022, 0.016))
    rough = g.mixf(grime, rough, 0.85)
    metal = g.mixf(grime, metal, 0.0)
    # Dust and dark specks
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 900.0)
    g.links.new(P, vor.inputs["Vector"])
    specks = mul(g, g.ramp(tk._sock(vor.outputs, "Distance"), 0.18, 0.08), g.ramp(g.noise(40.0, vector=P), 0.45, 0.6))
    col = g.mix(specks, col, (0.03, 0.025, 0.02))
    metal = g.mixf(specks, metal, 0.0)
    rough = g.mixf(specks, rough, 0.9)
    # Dried blood flecked on some beads
    blood = mul(g, g.ramp(g.noise(24.0, detail=6.0, distortion=0.9, vector=P), 0.66, 0.74), g.ramp(per, 0.3, 0.6))
    col = g.mix(blood, col, (0.05, 0.005, 0.004))
    rough = g.mixf(blood, rough, 0.35)
    metal = g.mixf(blood, metal, 0.0)
    # The bead's round normal, with fine scuffs bumped on it
    sphere = vnorm(g, vsub(g, W, bc))
    height = add(g, mul(g, g.noise(600.0, detail=3.0, vector=P), 0.3), mul(g, rub, -0.4))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.0005, normal=sphere))


PURPLE = bead_material("BeadPurple", (0.13, 0.04, 0.17), 1.0)
GOLD = bead_material("BeadGold", (0.34, 0.24, 0.085), 2.0)
GREEN = bead_material("BeadGreen", (0.045, 0.15, 0.05), 3.0)


# ---------------------------------------------------------------- the strands

def bead_mesh(beads, mat, name):
    """Low-poly beads: poles along the strand (flattened, where the hole is), a ring of five round it.
    beads = [(center, along, radius, spin, random)]. The ring sits at alternating turns so neighbors don't line up.
    Stores bc (the bead's center) and bd = (position along the bead -1..1, a random value, 0)."""
    bm = bmesh.new()
    bcs, bds = [], []
    for c, a, r, spin, rid in beads:
        a = a.normalized()
        u = (UP - a * a.dot(UP)) if abs(a.z) < 0.95 else Vector((1.0, 0.0, 0.0))
        u.normalize()
        v = a.cross(u)
        hl = r * HOLE
        top = bm.verts.new(c + a * hl)
        bot = bm.verts.new(c - a * hl)
        ring = []
        for k in range(RING):
            t = spin + 2 * math.pi / RING * k
            ring.append(bm.verts.new(c + (u * math.cos(t) + v * math.sin(t)) * r))
        for vv, x in [(top, 1.0), (bot, -1.0)] + [(rv, 0.0) for rv in ring]:
            bcs.append(tuple(c))
            bds.append((x, rid, 0.0))
        for k in range(RING):
            k1 = (k + 1) % RING
            bm.faces.new((top, ring[k], ring[k1]))
            bm.faces.new((bot, ring[k1], ring[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    # vertex order: per bead top, bot, ring... matches bcs/bds order
    set_attr(obj, "bc", bcs)
    set_attr(obj, "bd", bds)
    return tk.smooth(obj, 89)


RING, HOLE = 5, 0.85  # beads: five round, the poles 0.85 of the radius out (flattened at the holes)

# Strands: (name, material, bead radius, ring distance from the neck axis, where it leaves the neck (deg),
# its bottom (x, z), sway)
STRANDS = [
    ("Purple", PURPLE, 0.008, 0.0675, 62.0, (0.004, 1.456), 0.0),
    ("Gold", GOLD, 0.008, 0.084, 71.0, (-0.006, 1.433), 0.006),
    ("Green", GREEN, 0.0095, 0.1, 80.0, (0.006, 1.407), -0.005),
]


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


def strand_path(rho, leave, bottom, rb, sway):
    """The closed loop of a strand's bead centers: round the back of the neck at rho, leaving it `leave` degrees
    either side of the front, then down the chest in a U to `bottom` (laid on the chest as seen from the front)."""
    b0 = math.radians(leave)
    back = [neck_ring(b0 + (2 * math.pi - 2 * b0) * k / 16, rho, rb + 0.0015) for k in range(17)]
    bx, bz = bottom
    left, right = back[0], back[-1]
    # The legs in (x, z): over the collarbone, in and down to the U at the bottom
    leg_r = bezier2((right.x, right.z), (right.x * 0.97, right.z - 0.045), (bx - 0.026, bz + 0.011), 9)
    leg_l = bezier2((left.x, left.z), (left.x * 0.97, left.z - 0.045), (bx + 0.026, bz + 0.011), 9)
    u = [(bx - 0.018, bz + 0.0045), (bx - 0.0065, bz + 0.0006), (bx + 0.0065, bz + 0.0006), (bx + 0.018, bz + 0.0045)]
    front2d = leg_r + u + list(reversed(leg_l))
    n = len(front2d)
    front2d = [(x + sway * math.sin(math.pi * i / (n - 1)), z) for i, (x, z) in enumerate(front2d)]

    def off(z):
        return rb + lift(z) + 0.0015
    front = [front_project(x, z, off(z)) for x, z in front2d]
    dense = catmull(back + front, 6, closed=True)
    out = [front_project(q.x, q.z, off(q.z)) if q.y < -0.004 else q for q in dense]
    if os.environ.get("ZED_DEBUG"):
        print("  dense %d pts, %.1f cm" % (len(out), arclen(out, True)[-1] * 100))
    return out


def build():
    objs, all_beads = [], []
    for name, mat, rb, rho, leave, bottom, sway in STRANDS:
        path = strand_path(rho, leave, bottom, rb, sway)
        centers, pitch = resample_closed(path, 2 * rb * HOLE)
        beads = []
        for i, c in enumerate(centers):
            a = centers[(i + 1) % len(centers)] - centers[i - 1]
            beads.append([c, a, rb * RND.uniform(0.96, 1.03), (i % 2) * math.pi / RING + RND.uniform(-0.2, 0.2), RND.random()])
        # Lie over the beads of the shorter strands where they cross (pushed out along the body's normal)
        for b in beads:
            for (c2, r2) in all_beads:
                gap = (b[0] - c2).length - (b[2] + r2) * 0.96
                if gap < 0:
                    b[0] = b[0] + body_normal(b[0]) * (-gap + 0.0005)
        all_beads += [(b[0], b[2]) for b in beads]
        objs.append(bead_mesh([tuple(b) for b in beads], mat, "Strand" + name))
        print("[%s] %s: %d beads of %.1f mm, %.0f cm round, bottom at z %.3f" % (
            SCRIPT, name, len(beads), rb * 2000, pitch * len(beads) * 100, min(c.z for c in centers)))
    return objs, all_beads


pieces, BEADS = build()
for p in pieces:
    zk.on(p, "Neck", "Beads")

# ---------------------------------------------------------------- checks

PROXY = face_proxy()


def jaw_clearance():
    """The nearest bead to Joe's lower face with the jaw opened 18 degrees (the attack)."""
    rot = Matrix.Translation(JAW_PIVOT) @ Matrix.Rotation(math.radians(18.0), 4, "X") @ Matrix.Translation(-JAW_PIVOT)
    pts = []
    for (c, r) in [((0.0, -0.077, 1.611), (0.022, 0.017, 0.017)), ((0.0, -0.02, 1.628), (0.053, 0.066, 0.045))]:
        for i in range(24):
            for j in range(1, 12):
                th, ph = 2 * math.pi * i / 24, math.pi * j / 12
                p = Vector((c[0] + r[0] * math.sin(ph) * math.cos(th), c[1] + r[1] * math.sin(ph) * math.sin(th),
                            c[2] + r[2] * math.cos(ph)))
                if p.y < 0.0:
                    pts.append(rot @ p)
    best = min(((c - p).length - r, c) for c, r in BEADS for p in pts)
    print("[%s] jaw open 18 deg: nearest bead %.1f cm away at (%.3f, %.3f, %.3f)" % (SCRIPT, best[0] * 100, *best[1]))


def chest_report():
    bm = bmesh.new()
    bm.from_mesh(PROXY.data)
    bvh = BVHTree.FromBMesh(bm)
    worst, far = 9.0, 0.0
    for c, r in BEADS:
        loc, nrm, _, d = bvh.find_nearest(c)
        s = (c - loc).dot(nrm)
        gap = (d if s > 0 else -d) - r
        if c.z < 1.5 and c.y < 0.0:
            worst = min(worst, gap)
            far = max(far, gap)
    print("[%s] front beads off Joe's real chest (proxy): %.1f to %.1f cm" % (SCRIPT, worst * 100, far * 100))


jaw_clearance()
chest_report()
tris = sum(len(p.data.polygons) for p in pieces)
print("[%s] %d triangles before export" % (SCRIPT, tris))
if os.environ.get("ZED_DRY"):  # fitting checks only, no bake
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
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.75)


def close_up(view, direction, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


close_up("close", (-0.35, -1.0, 0.15), Vector((0.0, -0.1, 1.42)), 0.25)
close_up("profile", (1.0, -0.15, 0.05), Vector((0.0, -0.04, 1.47)), 0.42)
close_up("nape", (-0.5, 1.0, 0.5), Vector((0.0, 0.05, 1.55)), 0.35)
print("[%s] done" % SCRIPT)
