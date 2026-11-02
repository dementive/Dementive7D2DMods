"""IV line: what is left of a hospital drip on the left forearm. An IV cannula still in the inside of the forearm a few
centimeters above the wrist (on the thumb side of the palm face, where the vein is): its rose-colored hub and port on
off-white wings, held down by two strips of dirty cloth tape, the insertion spotted with blood.
The tube still clipped to the hub runs a little way along the arm under the tape, then lifts off and hangs, torn off
about 6 cm down: pale and grimy (opaque: the game can't draw clear plastic), dried blood backed up inside it near the
hub. Round the wrist, loose, a hospital ID band: off-white plastic, a printed label with a barcode and a red alert
stripe, snap-closed with its tail sticking out.

Joe's forearm as this assumes it (the same as the arm cast's, a touch fuller near the wrist): the tape lies about 1 mm
off that. The forearm hit box (5 cm) is fatter than the arm, so the previews use a slimmer stand-in arm. The tube
hangs straight down and a little forward, clear of the hand.

One part on the forearm bone: "LeftForeArm#IV".

    blender -b --factory-startup --python iv_line.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PART = "IVLine", "iv_line", "LeftForeArm", "IV"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()
ATTR = "iv"  # per vertex: (u, v, kind) for the materials that print on a strip


def orth(v, axis):
    return (v - axis * v.dot(axis)).normalized()


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the forearm

ELBOW, WRIST = sk.pos("LeftForeArm"), sk.pos("LeftHand")
AX = (WRIST - ELBOW).normalized()
LEN = (WRIST - ELBOW).length
FRONT = orth(Vector((0.0, -1.0, 0.0)), AX)  # the thumb side
PALM = AX.cross(FRONT)  # the palm face: down and in, toward the body in the A-pose
DORSAL = -PALM
DOWN = Vector((0.0, 0.0, -1.0))
SKIN = ((0.0, 0.043, 0.041), (0.15, 0.043, 0.041), (0.4, 0.04, 0.036), (0.7, 0.036, 0.031), (0.9, 0.033, 0.026),
        (1.0, 0.031, 0.024))


def skin_ab(t):
    t = max(0.0, min(1.0, t))
    for (t0, a0, b0), (t1, a1, b1) in zip(SKIN, SKIN[1:]):
        if t <= t1:
            f = smoothstep(t0, t1, t)
            return a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
    return SKIN[-1][1], SKIN[-1][2]


def direction(phi):
    """Round the forearm: 0 its back, +90 degrees the thumb side, 180 the palm face."""
    return DORSAL * math.cos(phi) + FRONT * math.sin(phi)


def r_skin(s, phi):
    a, b = skin_ab(s / LEN)
    return 1.0 / math.sqrt((math.cos(phi) / b) ** 2 + (math.sin(phi) / a) ** 2)


def skin(s, phi, lift=0.0):
    """The skin point at s along the forearm and phi round it, lifted along the surface normal; and that normal."""
    p = ELBOW + AX * s + direction(phi) * r_skin(s, phi)
    e = 1e-3
    tp = (ELBOW + AX * s + direction(phi + e) * r_skin(s, phi + e)) - (ELBOW + AX * s + direction(phi - e) *
                                                                      r_skin(s, phi - e))
    n = AX.cross(tp).normalized()
    if n.dot(direction(phi)) < 0:
        n = -n
    return p + n * lift, n


# Where the cannula is: 68% down the forearm, on the palm face toward the thumb
S_HUB, PHI_HUB = LEN * 0.68, math.radians(118.0)
HUB_BASE, HUB_N = skin(S_HUB, PHI_HUB)
ROUND = HUB_N.cross(AX).normalized()  # across the arm at the hub
# The tube hangs down and a little forward, clear of the hand
HANG = (DOWN + FRONT * 0.4).normalized()


# ---------------------------------------------------------------- mesh helpers

def set_attr(obj, values):
    me = obj.data
    a = me.attributes.get(ATTR) or me.attributes.new(ATTR, "FLOAT_VECTOR", "POINT")
    for d, v in zip(a.data, values):
        d.vector = v
    return obj


def frustum(name, a, b, ra, rb, mat, sides=10, kind=0.0):
    """A closed cylinder (or cone) from a to b."""
    bm = bmesh.new()
    d = (b - a)
    ax = d.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(ax.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    e1 = orth(ref, ax)
    e2 = ax.cross(e1)
    r0 = [bm.verts.new(a + (e1 * math.cos(2 * math.pi * k / sides) + e2 * math.sin(2 * math.pi * k / sides)) * ra)
          for k in range(sides)]
    r1 = [bm.verts.new(b + (e1 * math.cos(2 * math.pi * k / sides) + e2 * math.sin(2 * math.pi * k / sides)) * rb)
          for k in range(sides)]
    for k in range(sides):
        k1 = (k + 1) % sides
        bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    bm.faces.new(list(reversed(r0)))
    bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, [(0.0, 0.0, kind)] * len(obj.data.vertices))
    return tk.smooth(obj, 50)


def slab(name, rows, thick, normals, mat, attrs):
    """A thin closed slab from a grid of surface points (rows x cols), `thick` out along the given normals."""
    bm = bmesh.new()
    R, C = len(rows), len(rows[0])
    top = [[bm.verts.new(rows[i][j] + normals[i][j] * thick) for j in range(C)] for i in range(R)]
    bot = [[bm.verts.new(rows[i][j]) for j in range(C)] for i in range(R)]
    for i in range(R - 1):
        for j in range(C - 1):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]))
    for i in range(R - 1):
        for j in (0, C - 1):
            bm.faces.new((top[i][j], top[i + 1][j], bot[i + 1][j], bot[i][j]))
    for j in range(C - 1):
        for i in (0, R - 1):
            bm.faces.new((top[i][j], bot[i][j], bot[i][j + 1], top[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    vals = [attrs[i][j] for i in range(R) for j in range(C)] * 2
    set_attr(obj, vals)
    return tk.smooth(obj, 45)


def tube(name, pts, radius, mat, sides=6, kind=3.0):
    P = [Vector(p) for p in pts]
    n = len(P)
    bm = bmesh.new()
    rings = []
    ref = None
    along = 0.0
    attrs = []
    for i in range(n):
        T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        if ref is None:
            ref = orth(Vector((0.0, 0.0, 1.0)) if abs(T.z) < 0.9 else Vector((1.0, 0.0, 0.0)), T)
        N = orth(ref, T)
        ref = N
        B = T.cross(N)
        if i:
            along += (P[i] - P[i - 1]).length
        rings.append([bm.verts.new(P[i] + (N * math.cos(2 * math.pi * k / sides) + B * math.sin(2 * math.pi * k / sides))
                                   * radius) for k in range(sides)])
        attrs += [(along, k / sides, kind) for k in range(sides)]
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            k1 = (k + 1) % sides
            bm.faces.new((a[k], a[k1], b[k1], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, attrs)
    return tk.smooth(obj, 60)


# ---------------------------------------------------------------- the cannula

def cannula(hub_mat, white_mat):
    up = HUB_N
    c = HUB_BASE + up * 0.0042
    a = c - AX * 0.0095  # the catheter end, toward the elbow, dipping to the skin
    b = c + AX * 0.0085
    parts = [frustum("Hub", a - up * 0.0008, b, 0.0024, 0.0034, hub_mat, 10, 1.0)]
    # the catheter's sheath going into the skin
    parts.append(frustum("Sheath", a - up * 0.0008, a - AX * 0.0025 - up * 0.0042, 0.0011, 0.0009, white_mat, 6, 2.0))
    # the injection port on top, its cap
    pb = HUB_BASE + up * 0.0055 + AX * 0.0015
    parts.append(frustum("Port", pb, pb + up * 0.0045, 0.0026, 0.0026, white_mat, 10, 2.0))
    parts.append(frustum("PortCap", pb + up * 0.0045, pb + up * 0.0072, 0.0031, 0.0029, hub_mat, 10, 1.0))
    # the wings, flat on the gauze pad
    rows, nrms, attrs = [], [], []
    for i in range(3):
        s = S_HUB - 0.007 + 0.011 * i / 2
        row, nr, at = [], [], []
        for j in range(5):
            dphi = (-1.0 + 2.0 * j / 4) * 0.36
            p, n = skin(s, PHI_HUB + dphi, 0.0013)
            row.append(p)
            nr.append(n)
            at.append((0.0, 0.0, 2.0))
        rows.append(row)
        nrms.append(nr)
        attrs.append(at)
    parts.append(slab("Wings", rows, 0.0009, nrms, white_mat, attrs))
    # the tube's connector, clipped into the hub's back end
    lb = b + AX * 0.0105
    parts.append(frustum("Luer", b - AX * 0.001, lb, 0.003, 0.0026, white_mat, 10, 2.0))
    return parts, lb


def tape_strip(name, s0, half_phi, width, lift_fn, mat, skew=0.0, seed=0.0):
    """A strip of cloth tape laid round the forearm at s0 across +-half_phi of the cannula's side, draped over what
    is under it (lift_fn(phi, s)), its ends a little ragged."""
    n = 15
    rows, nrms, attrs = [], [], []
    for i in range(n):
        f = i / (n - 1)
        dphi = (-1.0 + 2.0 * f) * half_phi
        row, nr, at = [], [], []
        for j, w in enumerate((-0.5, 0.0, 0.5)):
            s = s0 + w * width + skew * (f - 0.5)
            lift = 0.0011 + lift_fn(dphi, s - S_HUB)
            if i in (0, n - 1):
                lift -= 0.0005  # the ends pressed down
            p, nn = skin(s, PHI_HUB + dphi, lift)
            row.append(p)
            nr.append(nn)
            at.append((f, w + 0.5, 4.0 + seed))
        rows.append(row)
        nrms.append(nr)
        attrs.append(at)
    return slab(name, rows, 0.0007, nrms, mat, attrs)


def bump(dphi, ds, height, half_phi, half_s):
    """A soft rise of `height` over a patch (half-widths in radians round and meters along)."""
    return height * smoothstep(half_phi, 0.0, abs(dphi)) * smoothstep(half_s, 0.0, abs(ds))


# ---------------------------------------------------------------- the torn tube

def torn_tube_path(start):
    """From the connector along the arm under the second tape strip, then off the arm and hanging, torn off."""
    pts = [start]
    s = S_HUB + 0.0085 + 0.0105
    for k in range(1, 5):
        ss = s + 0.0055 * k
        p, n = skin(ss, PHI_HUB + 0.03 * k, 0.0036 + 0.0004 * k)
        pts.append(p)
    last, n = skin(s + 0.026, PHI_HUB + 0.14, 0.0055)
    away = n
    pts.append(last + away * 0.003 + HANG * 0.003)
    p = pts[-1]
    d = (away * 0.7 + HANG).normalized()
    for k in range(9):
        d = (d * 0.72 + HANG * 0.28).normalized()
        p = p + d * 0.007
        p = p + ROUND * (0.0012 * math.sin(k * 0.8))
        pts.append(p)
    return pts


# ---------------------------------------------------------------- the wristband

S_BAND = LEN * 0.925


def wristband(band_mat, snap_mat):
    """A loose loop round the wrist, resting on the back of it and hanging away on the palm side; a printed label
    insert on the back toward the thumb, snaps where the ends overlap, the tail end sticking out."""
    a, b = skin_ab(S_BAND / LEN)
    sag = PALM * 0.003
    ra, rb = a + 0.0032, b + 0.0026 + 0.003
    tilt = Matrix.Rotation(math.radians(6.0), 3, FRONT)  # not quite square to the arm
    n = 30
    width = 0.019
    pts, nrms = [], []
    for k in range(n):
        phi = 2 * math.pi * k / n
        d = DORSAL * (math.cos(phi) * rb) + FRONT * (math.sin(phi) * ra)
        p = ELBOW + AX * S_BAND + sag + tilt @ d
        pts.append(p)
        nrms.append((tilt @ (DORSAL * (math.cos(phi) / rb) + FRONT * (math.sin(phi) / ra))).normalized())
    bm = bmesh.new()
    rings, attrs = [], []
    around = 0.0
    for k in range(n + 1):  # the last ring repeats the first, so the print coordinates don't wrap
        p, nn = pts[k % n], nrms[k % n]
        if k:
            around += (pts[k % n] - pts[k - 1]).length
        side = tilt @ AX
        ring = []
        for w, t in ((-0.5, 0.0), (0.5, 0.0), (0.5, 1.0), (-0.5, 1.0)):
            ring.append(bm.verts.new(p + side * (w * width) + nn * (t * 0.0013)))
            attrs.append((around, w + 0.5, 6.0))
        rings.append(ring)
    for k in range(n):
        r0, r1 = rings[k], rings[k + 1]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((r0[j], r0[j1], r1[j1], r1[j]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    f = bm.faces[2]  # an outer face
    if f.normal.dot(nrms[0]) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    band = tk.mesh_object("Band", bm, band_mat)
    set_attr(band, attrs)
    tk.smooth(band, 40)
    parts = [band]
    # The label insert: a raised panel on the back of the wrist toward the thumb
    k0, k1 = 2, 7
    rows, nr, at = [], [], []
    for k in range(k0, k1 + 1):
        p, nn = pts[k], nrms[k]
        side = tilt @ AX
        rows.append([p + nn * 0.0013 + side * (w * 0.015) for w in (-0.5, 0.0, 0.5)])
        nr.append([nn] * 3)
        at.append([((k - k0) / (k1 - k0), w + 0.5, 7.0) for w in (-0.5, 0.0, 0.5)])
    parts.append(slab("Label", rows, 0.0006, nr, band_mat, at))
    # Snaps where the ends overlap (on the pinky side), and the tail end sticking out past them
    for k, kk in enumerate((20, 22)):
        p, nn = pts[kk], nrms[kk]
        parts.append(frustum("Snap%d" % k, p + nn * 0.001, p + nn * 0.0034, 0.0032, 0.0026, snap_mat, 8, 8.0))
    p0, n0 = pts[23], nrms[23]
    tg = (pts[24] - pts[22]).normalized()
    out = (tg * 0.8 + n0 * 0.6).normalized()
    rows, nr, at = [], [], []
    for i in range(3):
        q = p0 + n0 * 0.0016 + out * (0.0055 * i) + n0 * (0.0008 * i * i)
        rows.append([q + (tilt @ AX) * (w * 0.013) for w in (-0.5, 0.0, 0.5)])
        nr.append([n0] * 3)
        at.append([(0.9 + 0.03 * i, w + 0.5, 6.0) for w in (-0.5, 0.0, 0.5)])
    parts.append(slab("Tail", rows, 0.0012, nr, band_mat, at))
    return parts


# ---------------------------------------------------------------- materials

def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def voronoi(g, vec, scale):
    n = g.node("ShaderNodeTexVoronoi")
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, "Distance")


def attr(g):
    a = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    a.attribute_type = "GEOMETRY"
    return g.separate(tk._sock(a.outputs, "Vector"))


def dist_to(g, point):
    d = g.node("ShaderNodeVectorMath", operation="DISTANCE")
    g.links.new(g.coords(), d.inputs[0])
    d.inputs[1].default_value = tuple(point)
    return tk._sock(d.outputs, "Value")


def grime(g, col, rough, P, amount=1.0, dark=(0.05, 0.042, 0.032)):
    """Dirt from a photo's dark parts, grime in creases, grubby smudges, specks."""
    p = tk.photo(g, "rust_coarse_01", 3.0, (0.31, 0.17, 0.52))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.26, 0.07), 0.8 * amount)
    dirt = g.math("MAXIMUM", dirt, tk._grime(g, 1.1 * amount), clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, dark)
    rough = g.mixf(dirt, rough, 0.9)
    smudge = g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=6.0, roughness=0.65, vector=P, distortion=0.8), 0.52,
                                       0.68), 0.5 * amount)
    col = g.mix(smudge, col, tk._darker(g, col, 0.5))
    spots = g.ramp(voronoi(g, P, 220.0), 0.12, 0.05)
    col = g.mix(g.math("MULTIPLY", spots, g.ramp(g.noise(6.0, vector=P), 0.45, 0.6)), col, (0.025, 0.02, 0.015))
    return col, rough


def blood(g, col, rough, P, region, amount=1.0):
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 70.0), 0.14, 0.05),
                   g.ramp(g.noise(20.0, vector=P), 0.42, 0.6))
    smear = g.ramp(g.noise(30.0, detail=6.0, roughness=0.7, vector=P, distortion=1.0), 0.58, 0.66)
    bl = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", drops, smear), region), amount, clamp=True)
    col = g.mix(bl, col, g.mix(g.noise(40.0, vector=P), (0.03, 0.008, 0.006), (0.055, 0.016, 0.011)))
    rough = g.mixf(bl, rough, 0.5)
    return col, rough


def tape_material(name):
    """Cloth surgical tape and the gauze pad under it: off-white gone grey-beige, a fine woven grain, grimy frayed
    edges, the adhesive's dark lint line at the ends, blood spots near the insertion."""
    mat, g = tk.new_material(name)
    u, v, kind = attr(g)
    P = mapping(g, g.coords(), loc=(0.6, 0.3, 0.9))
    col = g.mix(g.ramp(g.noise(80.0, detail=4.0, vector=P), 0.3, 0.75), (0.25, 0.238, 0.205), (0.18, 0.168, 0.138))
    weave = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", u, 2 * math.pi * 26.0)),
                   g.math("SINE", g.math("MULTIPLY", v, 2 * math.pi * 7.0)))
    height = g.math("MULTIPLY", weave, 0.2)
    edge = g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5)), 0.38, 0.5),
                  g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", u, 0.5)), 0.4, 0.5),
                         g.ramp(kind, 4.5, 3.9)))
    col = g.mix(g.math("MULTIPLY", edge, g.ramp(g.noise(60.0, vector=P), 0.3, 0.6)), col, (0.07, 0.06, 0.046))
    rough = 0.88
    col, rough = grime(g, col, rough, P, 1.0)
    near = g.ramp(dist_to(g, HUB_BASE - AX * 0.012), 0.03, 0.005)
    col, rough = blood(g, col, rough, P, g.math("ADD", g.math("MULTIPLY", near, 1.2), 0.12))
    col = tk.grade(g, col, sat=0.9, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.25, 0.0008))


def plastic_material(name, base, rough0=0.4):
    mat, g = tk.new_material(name)
    P = mapping(g, g.coords(), loc=(0.2, 0.7, 0.1))
    col = g.mix(g.ramp(g.noise(60.0, detail=3.0, vector=P), 0.3, 0.7), base, tuple(c * 0.75 for c in base))
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.0015), 0.1, 0.4), g.ramp(g.noise(90.0, vector=P), 0.35, 0.55))
    col = g.mix(g.math("MULTIPLY", worn, 0.5), col, tuple(min(1.0, c * 1.4 + 0.03) for c in base))
    rough = g.math("ADD", rough0, g.math("MULTIPLY", g.noise(40.0, vector=P), 0.15))
    col, rough = grime(g, col, rough, P, 1.1)
    col, rough = blood(g, col, rough, P, 0.35)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(300.0, detail=2.0, vector=P), 0.1, 0.0005))


def tube_material(name, length):
    """IV tubing, drawn opaque: a pale, faintly yellowed grey with a glossy skin, a brighter streak where the light
    catches it, grime in streaks, and dried blood backed up inside it near the hub, darkest at the hub."""
    mat, g = tk.new_material(name)
    along, around, kind = attr(g)
    P = mapping(g, g.coords(), loc=(0.9, 0.1, 0.4))
    col = g.mix(g.ramp(g.noise(40.0, detail=3.0, vector=P), 0.3, 0.7), (0.24, 0.236, 0.21), (0.18, 0.176, 0.155))
    # the inside showing through as a darker core along the middle of each side
    core = g.ramp(g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", around, 2 * math.pi))), 0.9, 0.4)
    col = g.mix(g.math("MULTIPLY", core, 0.25), col, (0.1, 0.098, 0.088))
    inside = g.math("MULTIPLY", g.ramp(along, 0.045, 0.01), g.ramp(g.noise(25.0, detail=3.0, vector=P), 0.25, 0.5))
    col = g.mix(inside, col, g.mix(core, (0.07, 0.016, 0.011), (0.035, 0.008, 0.006)))
    streak = g.ramp(g.noise(1.0, detail=2.0, vector=mapping(g, P, (40.0, 40.0, 200.0))), 0.62, 0.7)
    col = g.mix(g.math("MULTIPLY", streak, 0.6), col, (0.06, 0.05, 0.04))
    rough = 0.32
    col, rough = grime(g, col, rough, P, 0.8)
    # the torn end: ragged and darker
    torn = g.ramp(along, length - 0.012, length - 0.002)
    col = g.mix(g.math("MULTIPLY", torn, 0.6), col, (0.06, 0.05, 0.042))
    col = tk.grade(g, col, sat=0.9, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(200.0, detail=2.0, vector=P), 0.08, 0.0005))


def band_material(name):
    """The ID band: off-white vinyl, dirty, a paper label (name lines, a barcode, a red alert stripe) on the insert."""
    mat, g = tk.new_material(name)
    u, v, kind = attr(g)
    P = mapping(g, g.coords(), loc=(0.4, 0.9, 0.2))
    is_label = g.ramp(kind, 6.5, 6.9)
    col = g.mix(g.ramp(g.noise(50.0, detail=3.0, vector=P), 0.3, 0.7), (0.235, 0.228, 0.205), (0.17, 0.164, 0.145))
    # the band's embossed edge lines
    rim = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5)), 0.4, 0.47)
    col = g.mix(g.math("MULTIPLY", rim, 0.4), col, (0.11, 0.105, 0.092))
    # the label: paper, name lines, a barcode, a red stripe
    paper = g.mix(g.ramp(g.noise(120.0, vector=P), 0.3, 0.7), (0.245, 0.235, 0.205), (0.2, 0.19, 0.16))
    lc = paper
    for k, (v0, v1) in enumerate(((0.72, 0.84), (0.52, 0.62))):
        line = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(v, v0, v0 + 0.02), g.ramp(v, v1, v1 - 0.02)),
                      g.math("MULTIPLY", g.ramp(u, 0.06, 0.08), g.ramp(u, 0.55 - 0.12 * k, 0.53 - 0.12 * k)))
        chars = g.ramp(g.math("SINE", g.math("MULTIPLY", u, 2 * math.pi * (38.0 + 6 * k))), -0.3, 0.4)
        lc = g.mix(g.math("MULTIPLY", line, g.math("MULTIPLY", chars, 0.85)), lc, (0.03, 0.03, 0.035))
    bars = g.ramp(g.math("SINE", g.math("ADD", g.math("MULTIPLY", u, 300.0),
                                        g.math("MULTIPLY", g.noise(1.0, detail=1.0,
                                                                   vector=mapping(g, P, (900.0, 900.0, 900.0))),
                                                       9.0))), 0.0, 0.3)
    code = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(u, 0.6, 0.62), g.ramp(u, 0.94, 0.92)),
                  g.math("MULTIPLY", g.ramp(v, 0.18, 0.2), g.ramp(v, 0.82, 0.8)))
    lc = g.mix(g.math("MULTIPLY", code, bars), lc, (0.03, 0.03, 0.035))
    alert = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(u, 0.06, 0.08), g.ramp(u, 0.5, 0.48)),
                   g.math("MULTIPLY", g.ramp(v, 0.15, 0.17), g.ramp(v, 0.36, 0.34)))
    lc = g.mix(alert, lc, (0.13, 0.02, 0.018))
    col = g.mix(is_label, col, lc)
    rough = g.mixf(is_label, 0.42, 0.75)
    col, rough = grime(g, col, rough, P, 1.1)
    col, rough = blood(g, col, rough, P, 0.3)
    col = tk.grade(g, col, sat=0.9, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(250.0, detail=2.0, vector=P), 0.08, 0.0005))


# ---------------------------------------------------------------- fit report, export, previews

def capsule(bone):
    c = sk.collider(bone)
    ax = Vector((0.0, 0.0, 0.0))
    ax[c["axis"]] = 1.0
    half = max(0.0, c["height"] / 2 - c["radius"])
    ctr = Vector(c["center"])
    return sk.point(bone, ctr - ax * half), sk.point(bone, ctr + ax * half), c["radius"]


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def skin_gap(p):
    rel = p - ELBOW
    s = rel.dot(AX)
    phi = math.atan2(rel.dot(FRONT), rel.dot(DORSAL))
    return (rel - AX * s).length - r_skin(s, phi)


def export(pieces):
    for p in pieces:
        zk.on(p, BONE, PART)
    for o in BODY:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=512)
    for o in BODY:
        o.hide_render = False
    pts = [part.matrix_world @ v.co for part in parts for v in part.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    tris = sum(len(f.vertices) - 2 for part in parts for f in part.data.polygons)
    print("[%s] parts %s, %d triangles, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)"
          % ((NAME, [p.name for p in parts], tris) + tuple(lo) + tuple(hi)))
    on_arm = [p for p in pts if 0.0 < (p - ELBOW).dot(AX) < LEN + 0.005]
    gaps = [skin_gap(p) for p in on_arm]
    print("[%s] off the assumed forearm skin: %.1f to %.1f cm (the sheath goes in)" % (NAME, 100 * min(gaps),
                                                                                        100 * max(gaps)))
    a, b, r = capsule(BONE)
    hb = [seg_distance(p, a, b) - r for p in pts]
    print("[%s] %d of %d vertices inside the forearm hit box (5 cm, fatter than the arm)"
          % (NAME, sum(1 for d in hb if d < 0), len(hb)))
    hand = [seg_distance(p, sk.pos("LeftHand"), sk.pos("LeftHandMiddle2")) - 0.035 for p in tube_pts]
    print("[%s] the hanging tube's closest to the stand-in hand: %.1f cm" % (NAME, 100 * min(hand)))
    return parts


def slim_forearm():
    """The previews' forearm: the assumed arm (elliptical, tapering) in place of the fat hit box capsule."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] == BONE:
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    bm = bmesh.new()
    n, m = 24, 28
    rows = []
    for i in range(n + 1):
        s = -0.03 + (LEN + 0.03) * i / n
        rows.append([bm.verts.new(skin(s, 2 * math.pi * j / m)[0]) for j in range(m)])
    for a, b in zip(rows, rows[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bm.faces.new(rows[0])
    bm.faces.new(list(reversed(rows[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tk.smooth(tk.mesh_object("PreForeArm", bm, mat), 60)
    for name, p, r in (("PreElbow", ELBOW, 0.045), ("PreWrist", WRIST, 0.028)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r)
        bmesh.ops.translate(bm, vec=p, verts=bm.verts)
        tk.smooth(tk.mesh_object(name, bm, mat), 60)


def close_up(view, direction_, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction_).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


tape = tape_material("Tape")
hub_mat = plastic_material("HubPlastic", (0.2, 0.075, 0.085), 0.38)
white = plastic_material("WhitePlastic", (0.2, 0.198, 0.185), 0.35)
snap = plastic_material("SnapPlastic", (0.17, 0.165, 0.15), 0.4)
pieces, luer_end = cannula(hub_mat, white)
tube_pts = torn_tube_path(luer_end - AX * 0.002)
tube_len = sum((b - a).length for a, b in zip(tube_pts, tube_pts[1:]))
pieces += [tube("Tube", tube_pts, 0.0019, tube_material("Tube", tube_len), sides=6, kind=3.0)]


def plateau(dphi, ds, h, half_phi, half_s, edge=0.12, edge_s=0.004):
    """A flat rise of `h` over a patch with soft edges (what the tape drapes over: the wings)."""
    return h * smoothstep(half_phi + edge, half_phi, abs(dphi)) * smoothstep(half_s + edge_s, half_s, abs(ds))


def hub_bump(dphi, ds):
    return max(bump(dphi, ds, 0.0062, 0.34, 0.016), plateau(dphi, ds + 0.0015, 0.0013, 0.38, 0.006))


def tube_bump(dphi, ds):
    return max(bump(dphi - 0.08, ds - 0.024, 0.0052, 0.3, 0.014), bump(dphi, ds, 0.0028, 0.5, 0.02))


pieces.append(tape_strip("TapeA", S_HUB - 0.003, 0.95, 0.013, hub_bump, tape, skew=0.004, seed=0.0))
pieces.append(tape_strip("TapeB", S_HUB + 0.024, 0.85, 0.012, tube_bump, tape, skew=-0.003, seed=0.3))
band_mat = band_material("Wristband")
pieces += wristband(band_mat, snap)
export(pieces)
slim_forearm()
zk.previews(SCRIPT, PREVIEWS, HUB_BASE, distance=0.55)
close_up("cannula", HUB_N * 1.0 + FRONT * 0.2 - AX * 0.25, HUB_BASE + AX * 0.012, distance=0.2)
close_up("band", DORSAL * 0.7 + FRONT * 0.7 - AX * 0.3, ELBOW + AX * S_BAND, distance=0.22)
close_up("hanging", FRONT * 1.0 - AX * 0.2 + Vector((0.0, 0.0, 0.1)), HUB_BASE + DOWN * 0.035, distance=0.3)
print("[%s] done" % SCRIPT)
