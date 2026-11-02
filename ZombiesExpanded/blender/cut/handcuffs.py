"""Handcuffs: a pair of chain cuffs, one locked on the right wrist, the other hanging open from the chain. Nickel
steel gone dull: the double-strand frame with its lock box (keyhole, rivets) and the toothed swing arm, swivels at both
lock boxes and three links of chain. The locked cuff rests on the back of the wrist and hangs loose underneath, its
lock box underneath on the thumb side, where the chain's weight pulls it; the open cuff hangs below with its swing arm
swung out. Worn bright on the edges, scratched, grime in every gap, rust spotting the rivets and pitting the chain,
blood dried on the locked cuff where it chafed.

Joe's wrist as this assumes it: about 6.4 x 4.8 cm across (thumb to pinky, palm to back). The cuff sits 1.2 cm up
the forearm from the wrist joint. The chain and open cuff hang between straight down and along the forearm (22 degrees
out from straight down in the bind pose), so they still hang about right when the arm swings in to the side.

One part on the hand: "RightHand#Cuffs".

    blender -b --factory-startup --python handcuffs.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PART = "Handcuffs", "handcuffs", "RightHand", "Cuffs"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()


def orth(v, axis):
    return (v - axis * v.dot(axis)).normalized()


# ---------------------------------------------------------------- the wrist

ELBOW, WRIST = sk.pos("RightForeArm"), sk.pos("RightHand")
AX = (WRIST - ELBOW).normalized()  # down the forearm, toward the hand
DOWN = Vector((0.0, 0.0, -1.0))
FRONT = orth(Vector((0.0, -1.0, 0.0)), AX)  # the thumb side
PALM = orth(DOWN, AX)  # the palm face: down and in, toward the body in the A-pose
DORSAL = -PALM
WRIST_A, WRIST_B = 0.032, 0.024  # the wrist's half-widths: thumb to pinky, palm to back
HANG = (DOWN + AX).normalized()  # 22.5 degrees out from straight down

CUFF_C = WRIST - AX * 0.012 + PALM * 0.0045  # resting on the back of the wrist, hanging loose under it
RING_A, RING_B = 0.0375, 0.031  # the locked ring's inner half-widths
SEC_R, SEC_A = 0.006, 0.0068  # the frame's section: radial, axial (the swing arm is thinner)


def wrist_gap(p):
    """How far p is outside the assumed wrist (an ellipse round the forearm's axis)."""
    rel = p - ELBOW
    s = rel.dot(AX)
    x, y = rel.dot(FRONT), rel.dot(DORSAL)
    ang = math.atan2(x, y)
    r = 1.0 / math.sqrt((math.cos(ang) / WRIST_B) ** 2 + (math.sin(ang) / WRIST_A) ** 2)
    return math.hypot(x, y) - r


# ---------------------------------------------------------------- mesh helpers

def sweep(name, path, normals, profile, mat, closed=False, caps=True):
    """A profile [(across, out), ...] swept along a path; `out` along the given normals, `across` square to them."""
    P = [Vector(p) for p in path]
    n = len(P)
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if closed:
            T = (P[(i + 1) % n] - P[i - 1]).normalized()
        else:
            T = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        N = orth(Vector(normals[i]), T)
        B = T.cross(N)
        rings.append([bm.verts.new(P[i] + B * a + N * o) for a, o in profile])
    m = len(profile)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 50)


def rect_profile(w, h, chamfer=0.35):
    """A rectangle (w across, h out, centered) with its outer edges chamfered, 6 points."""
    cw, ch = w / 2, h / 2
    c = min(cw, ch) * chamfer
    return [(-cw, -ch), (cw, -ch), (cw, ch - c), (cw - c, ch), (-cw + c, ch), (-cw, ch - c)]


def torus(name, center, axis_u, axis_v, normal, ru, rv, minor, mat, seg=10, minor_seg=4, scale_minor=(1.0, 1.0)):
    """A ring (an oval link): centerline center + u*ru*cos + v*rv*sin; the wire `minor` thick."""
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        c = center + axis_u * (ru * math.cos(t)) + axis_v * (rv * math.sin(t))
        out = (axis_u * (math.cos(t) / ru) + axis_v * (math.sin(t) / rv)).normalized()
        ring = []
        for j in range(minor_seg):
            q = 2 * math.pi * j / minor_seg
            ring.append(bm.verts.new(c + out * (minor * scale_minor[0] * math.cos(q))
                                     + normal * (minor * scale_minor[1] * math.sin(q))))
        rings.append(ring)
    for i in range(seg):
        a, b = rings[i], rings[(i + 1) % seg]
        for j in range(minor_seg):
            j1 = (j + 1) % minor_seg
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def cyl(name, a, b, r, mat, sides=8):
    bm = bmesh.new()
    ax = (b - a).normalized()
    e1 = orth(Vector((0.0, 0.0, 1.0)) if abs(ax.z) < 0.9 else Vector((1.0, 0.0, 0.0)), ax)
    e2 = ax.cross(e1)
    r0 = [bm.verts.new(a + (e1 * math.cos(2 * math.pi * k / sides) + e2 * math.sin(2 * math.pi * k / sides)) * r)
          for k in range(sides)]
    r1 = [bm.verts.new(b + (e1 * math.cos(2 * math.pi * k / sides) + e2 * math.sin(2 * math.pi * k / sides)) * r)
          for k in range(sides)]
    for k in range(sides):
        k1 = (k + 1) % sides
        bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    bm.faces.new(list(reversed(r0)))
    bm.faces.new(r1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return tk.smooth(tk.mesh_object(name, bm, mat), 40)


def curved_box(name, center, e_out, e_tan, e_ax, radius, ang0, ang1, h_in, h_out, depth, mat, seg=6):
    """A block bent round an arc of `radius` about `center` (in the plane e_out/e_tan), from ang0 to ang1, from
    h_in inside the arc to h_out outside it, `depth` thick along e_ax: a lock box."""
    bm = bmesh.new()
    rings = []
    for i in range(seg + 1):
        t = ang0 + (ang1 - ang0) * i / seg
        d = e_out * math.cos(t) + e_tan * math.sin(t)
        c = center + d * radius
        ring = [bm.verts.new(c + d * o + e_ax * a) for a, o in
                ((-depth / 2, -h_in), (depth / 2, -h_in), (depth / 2, h_out), (-depth / 2, h_out))]
        rings.append(ring)
    for i in range(seg):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = 0.0012
    mod.segments = 1
    mod.limit_method = "ANGLE"
    tk.apply_modifiers(obj)
    return tk.smooth(obj, 35)


# ---------------------------------------------------------------- one cuff

def cuff(prefix, center, e_out, e_tan, e_ax, rx, ry, open_deg, mat, lock_ang):
    """A cuff in the plane (e_out, e_tan) round `center`, its ring an ellipse of inner half-widths rx (along e_out) and
    ry (along e_tan); the lock box centered at angle lock_ang. The frame runs 190 degrees from the lock box round to the
    pivot; the swing arm from the pivot back into the lock box, turned `open_deg` out about the pivot.
    Returns the pieces and the swivel's anchor (the lock box's outer end) and the box's outward direction there."""
    pieces = []

    def ring_pt(t, out=0.0):
        d = e_out * (math.cos(t) * (rx + SEC_R / 2 + out)) + e_tan * (math.sin(t) * (ry + SEC_R / 2 + out))
        return center + d

    def ring_n(t):
        return (e_out * (math.cos(t) / rx) + e_tan * (math.sin(t) / ry)).normalized()

    half_box = math.radians(30.0)
    a_frame0 = lock_ang + half_box * 0.6
    a_pivot = lock_ang + math.radians(205.0)
    # The frame: two cheek plates with a slot between (one thick section here; the slot is in the material)
    n = 13
    path = [ring_pt(a_frame0 + (a_pivot - a_frame0) * i / (n - 1)) for i in range(n)]
    nrm = [ring_n(a_frame0 + (a_pivot - a_frame0) * i / (n - 1)) for i in range(n)]
    pieces.append(sweep(prefix + "Frame", path, nrm, [(a, o) for a, o in rect_profile(SEC_A, SEC_R)], mat))
    # The swing arm: from the pivot round into the lock box, thinner, its teeth on the outside; turned open
    a_arm1 = lock_ang + 2 * math.pi - half_box * 0.2
    n = 11
    piv = ring_pt(a_pivot)
    rot = Matrix.Rotation(math.radians(open_deg), 3, e_ax)
    path, nrm = [], []
    for i in range(n):
        t = a_pivot + (a_arm1 - a_pivot) * i / (n - 1)
        path.append(piv + rot @ (ring_pt(t, -0.0004) - piv))
        nrm.append(rot @ ring_n(t))
    pieces.append(sweep(prefix + "Arm", path, nrm, [(a, o) for a, o in rect_profile(SEC_A * 0.6, SEC_R * 0.85)],
                        mat))
    # The pivot rivet through the frame and arm
    pieces.append(cyl(prefix + "Pivot", piv - e_ax * 0.0035, piv + e_ax * 0.0035, 0.0026, mat))
    # The lock box over the ring at lock_ang (bent round the ellipse's mean radius there)
    rr = (rx + ry) / 2 + SEC_R / 2
    pieces.append(curved_box(prefix + "Lock", center, e_out, e_tan, e_ax, rr, lock_ang - half_box, lock_ang + half_box,
                             0.0036, 0.0105, 0.0105, mat))
    # the swivel's anchor: the lock box's outer face at its middle
    d = e_out * math.cos(lock_ang) + e_tan * math.sin(lock_ang)
    anchor = center + d * (rr + 0.0105)
    return pieces, anchor, d


def swivel(prefix, anchor, d, plane_a, mat):
    """The swivel: a rivet out of the lock box and a small ring on it."""
    pieces = [cyl(prefix + "Rivet", anchor - d * 0.001, anchor + d * 0.004, 0.0021, mat)]
    c = anchor + d * 0.0085
    pieces.append(torus(prefix + "Swivel", c, d, plane_a, d.cross(plane_a).normalized(), 0.0048, 0.0042, 0.0016, mat,
                        seg=10, minor_seg=4))
    return pieces, c + d * 0.0048


# ---------------------------------------------------------------- material

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


def steel_material(name):
    """Nickel-plated steel gone dull: grey and part-metallic, worn bright on the edges, scratched, grime in every gap,
    rust spots and pitting, dried blood on the locked cuff."""
    mat, g = tk.new_material(name)
    P = mapping(g, g.coords(), loc=(0.5, 0.2, 0.9))

    def nz(scale, detail=4.0, r=0.55, dist=0.0):
        return g.noise(scale, detail=detail, roughness=r, vector=P, distortion=dist)

    # (the cuffs are small: the noise scales here are per centimeter or so)
    col = g.mix(g.ramp(nz(80.0, 4.0), 0.3, 0.7), (0.25, 0.248, 0.252), (0.16, 0.158, 0.16))
    metal = 0.65
    rough = g.math("ADD", 0.5, g.math("MULTIPLY", nz(120.0, 3.0), 0.15))
    # Plating worn through: duller, darker patches
    dull = g.ramp(nz(35.0, 6.0, 0.6, 0.5), 0.45, 0.62)
    col = g.mix(g.math("MULTIPLY", dull, 0.8), col, (0.085, 0.08, 0.075))
    rough = g.mixf(dull, rough, 0.7)
    # Rust: spots and pitting, orange-brown, not metallic; in the crevices too
    p = tk.photo(g, "rust_coarse_01", 14.0, (0.37, 0.71, 0.13))
    rust = g.math("MULTIPLY", g.ramp(nz(70.0, 8.0, 0.7, 0.6), 0.56, 0.66), g.ramp(nz(22.0), 0.38, 0.58))
    rust = g.math("MAXIMUM", rust, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.008), 0.5, 1.0),
                                                             clamp=True), 0.9))
    rc = tk.grade(g, p["color"], sat=0.85, value=0.6)
    col = g.mix(rust, col, rc)
    metal = g.mixf(rust, metal, 0.0)
    rough = g.mixf(rust, rough, 0.88)
    # Grime: in the gaps, and caked on in patches
    grime = g.math("MAXIMUM", tk._grime(g, 1.5), g.math("MULTIPLY", g.ramp(nz(30.0, 6.0, 0.65, 0.8), 0.5, 0.64),
                                                          0.75), clamp=True)
    col = g.mix(g.math("MULTIPLY", grime, 0.9), col, g.mix(nz(60.0), (0.03, 0.026, 0.022), (0.06, 0.05, 0.04)))
    metal = g.mixf(grime, metal, 0.0)
    rough = g.mixf(grime, rough, 0.9)
    # Worn edges and scratches, not too bright
    col, rough, metal = tk._grit(g, col, rough, metal, 0.4, scratches=0.3, edges=0.45)
    # Dried blood on the locked cuff, a few drops on the rest
    near = g.ramp(g.separate(g.coords())[2], 1.04, 1.07)
    bl = g.math("MULTIPLY", g.ramp(nz(40.0, 6.0, 0.6, 1.2), 0.6, 0.7), near)
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, P, 150.0), 0.12, 0.04), g.ramp(nz(15.0), 0.55, 0.65))
    bl = g.math("MAXIMUM", bl, drops)
    col = g.mix(bl, col, g.mix(nz(90.0), (0.03, 0.008, 0.006), (0.055, 0.015, 0.01)))
    metal = g.mixf(bl, metal, 0.0)
    rough = g.mixf(bl, rough, 0.5)
    height = g.math("ADD", g.math("MULTIPLY", rust, nz(200.0, 3.0)), g.math("MULTIPLY", nz(400.0, 2.0), 0.1))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.0006))


# ---------------------------------------------------------------- the cuffs

steel = steel_material("Steel")
pieces = []
# The locked cuff: round the wrist, square to the forearm; the lock box underneath toward the thumb side
lock_ang = math.radians(118.0)  # from the back of the wrist (DORSAL) toward the thumb side (FRONT)
locked, anchor0, d0 = cuff("Locked", CUFF_C, DORSAL, FRONT, AX, RING_B, RING_A, 0.0, steel, lock_ang)
pieces += locked
sw0, hook0 = swivel("A", anchor0, d0, AX, steel)
pieces += sw0
# The chain: three links hanging from the swivel
plane = AX.cross(HANG).normalized()  # square to the hanging direction
p = hook0
links = 3
for k in range(links):
    c = p + HANG * 0.0105
    u = HANG
    v = (plane if k % 2 == 0 else u.cross(plane)).normalized()
    pieces.append(torus("Link%d" % k, c, u, v, u.cross(v).normalized(), 0.0105, 0.0056, 0.0019, steel, seg=10,
                        minor_seg=5))
    p = c + HANG * 0.0105 - HANG * 0.0038
# The open cuff: its swivel on the last link, the lock box up, the ring hanging below, swung open
hook1 = p + HANG * 0.0038
d1 = -HANG
sw_c = hook1 + HANG * 0.0048
# the swivel ring and rivet, mirrored: the rivet goes down into the open cuff's lock box
pieces.append(torus("BSwivel", sw_c, -d1, plane, (-d1).cross(plane).normalized(), 0.0048, 0.0042, 0.0016, steel,
                    seg=10, minor_seg=4))
anchor1 = sw_c + HANG * 0.0085
pieces.append(cyl("BRivet", anchor1 - HANG * 0.004, anchor1 + HANG * 0.001, 0.0021, steel))
# the open cuff's plane: facing forward-ish (its ring seen face-on from the front), containing the hanging direction
face = orth(FRONT + AX * 0.3, HANG)
e_up = -HANG
e_side = face.cross(e_up).normalized()
rr = (0.034 + 0.03) / 2 + SEC_R / 2
center1 = anchor1 + HANG * (rr + 0.0105)
# its lock box at the top (toward the swivel): angle 0 along e_up
open_cuff, _, _ = cuff("Open", center1, e_up, e_side, face, 0.034, 0.03, -105.0, steel, 0.0)
pieces += open_cuff


# ---------------------------------------------------------------- fit report, export, previews

def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


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
    ring = [p for p in pts if abs((p - CUFF_C).dot(AX)) < 0.01 and (p - CUFF_C).length < 0.06]
    print("[%s] the locked cuff: %.1f to %.1f cm off the assumed wrist" % (NAME, 100 * min(wrist_gap(p) for p in ring),
                                                                         100 * max(wrist_gap(p) for p in ring)))
    hang = [p for p in pts if (p - CUFF_C).dot(HANG) > 0.05]
    hand = min(seg_distance(p, WRIST, sk.pos("RightHandMiddle2")) for p in hang) - 0.035
    thumb = min(seg_distance(p, sk.pos("RightHandThumb1"), sk.pos("RightHandThumb4")) for p in hang) - 0.012
    print("[%s] the hanging cuff: %.1f cm clear of the stand-in hand, %.1f cm of the thumb; lowest z %.3f"
          % (NAME, 100 * hand, 100 * thumb, lo.z))
    return parts


def slim_forearm():
    """The previews' forearm and hand: the assumed wrist instead of the fat hit box capsule, a slimmer hand."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] == "RightForeArm":
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    bpy.data.objects.remove(bpy.data.objects["BodyRightHand"])
    bm = bmesh.new()
    n, m = 16, 24
    L = (WRIST - ELBOW).length
    rows = []
    for i in range(n + 1):
        f = i / n
        s = -0.02 + (L + 0.02) * f
        a = 0.043 + (WRIST_A - 0.043) * f ** 0.8
        b = 0.041 + (WRIST_B - 0.041) * f ** 0.8
        rows.append([bm.verts.new(ELBOW + AX * s + DORSAL * (b * math.cos(2 * math.pi * j / m))
                                  + FRONT * (a * math.sin(2 * math.pi * j / m))) for j in range(m)])
    for a, b in zip(rows, rows[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bm.faces.new(rows[0])
    bm.faces.new(list(reversed(rows[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tk.smooth(tk.mesh_object("PreForeArm", bm, mat), 60)
    zk._capsule("PreHand", WRIST + AX * 0.012, sk.pos("RightHandMiddle2"), 0.028, mat)


def close_up(view, direction_, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction_).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


export(pieces)
slim_forearm()
focus = CUFF_C + HANG * 0.05
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.6)
close_up("close", FRONT * 1.0 - AX * 0.3 + Vector((0.0, 0.0, 0.15)), focus, distance=0.3)
close_up("wrist", DORSAL * 0.6 + FRONT * 0.8 - AX * 0.4, CUFF_C, distance=0.22)
close_up("open", FRONT * 1.0 + DORSAL * 0.2, center1, distance=0.2)
# (the stock side view looks from the zombie's left, through its body: this one looks from its right)
close_up("outside", Vector((-1.0, -0.25, 0.15)), focus, distance=0.6)
print("[%s] done" % SCRIPT)
