"""Neck brace: a soft foam cervical collar, the kind handed out for whiplash. A band of foam in a beige knit cover,
about 2 cm thick, scooped low at the front for the chin and taller behind, its edges bound with a darker trim, closed
at the back where one end overlaps the other under a hook-and-loop strap. Stained: yellowed along the top where the
jaw rested, grimy, blotched, dried blood run down the front from the mouth.

It sits round Joe's neck (an upright column about 11 cm across round (0, 0.032)) with about 7 mm to spare, its front
scooped down to z 1.552, 4 cm under the chin, so the jaw can drop when the zombie bites. The head hit box covers the
neck and jaw, and the chest hit box bulges up round the neck, so the previews use a skull, jaw and neck stand-in
instead. One part on the neck: "Neck#Brace".

    blender -b --factory-startup --python neck_brace.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PART = "NeckBrace", "neck_brace", "Neck", "Brace"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()

NECK = Vector((0.0, 0.032, 0.0))  # the neck's axis (x, y)
NECK_R = 0.055
CHIN = Vector((0.0, -0.075, 1.6))
JAW_PIVOT = sk.pos("Jaw")
ATTR = "nb"  # per vertex: (round the collar from the back 0..1, up its outer face 0..1, 1 on the inner face)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def horiz(theta):
    """theta 0 at the back (+Y), 90 degrees the zombie's right (-X), 180 the front (-Y), 270 its left."""
    return Vector((-math.sin(theta), math.cos(theta), 0.0))


def front(theta):
    """1 at the front of the neck, 0 at the sides and back."""
    return max(0.0, -math.cos(theta))


def back(theta):
    return max(0.0, math.cos(theta))


def z_top(theta):
    """The top edge: scooped low at the front for the chin, high under the jaw's angles, a little lower behind."""
    f, b = front(theta), back(theta)
    return 1.598 - 0.046 * smoothstep(0.0, 1.0, f) ** 1.3 - 0.01 * b ** 2


def z_bottom(theta):
    """The bottom edge rests on the collarbones in front and the trapezius at the sides and back."""
    f = front(theta)
    return 1.53 - 0.036 * smoothstep(0.15, 1.0, f) - 0.002 * back(theta)


R_IN = 0.0625  # inside, round the neck
FOAM = 0.021  # thickness
OVERLAP = (math.radians(-14.0), math.radians(22.0))  # where one end lies over the other at the back


def r_inner(theta, h):
    """The inside: a touch wider across than front to back, flaring out a little at the bottom."""
    ell = 1.0 / math.sqrt((math.sin(theta) / 1.03) ** 2 + math.cos(theta) ** 2)
    return R_IN * ell + 0.004 * (1.0 - h) ** 2


def lap(theta):
    """How much of the overlapping end lies here (0-1)."""
    a0, a1 = OVERLAP
    t = math.atan2(math.sin(theta), math.cos(theta))
    return smoothstep(a0 - 0.08, a0 + 0.02, t) * smoothstep(a1 + 0.02, a1 - 0.06, t)


# ---------------------------------------------------------------- the collar

N_AROUND = 36
# The cross-section, a rounded slab: (out 0 inside .. 1 outside, up 0 bottom .. 1 top, extra out, extra up, inner?)
C = 0.0065  # corner radius
PROFILE = [(0.0, 0.0, 0.0, C, 1), (0.0, 1.0, 0.0, -C, 1), (0.0, 1.0, C * 0.3, -C * 0.3, 1), (0.5, 1.0, 0.0, 0.0015, 0),
           (1.0, 1.0, -C * 0.3, -C * 0.3, 0), (1.0, 1.0, 0.0, -C, 0), (1.0, 0.5, 0.0035, 0.0, 0),
           (1.0, 0.0, 0.0, C, 0), (1.0, 0.0, -C * 0.3, C * 0.3, 0), (0.5, 0.0, 0.0, -0.0015, 0),
           (0.0, 0.0, C * 0.3, C * 0.3, 1)]


def set_attr(obj, values):
    me = obj.data
    a = me.attributes.new(ATTR, "FLOAT_VECTOR", "POINT")
    for d, v in zip(a.data, values):
        d.vector = v
    return obj


def collar(mat):
    bm = bmesh.new()
    cols, attrs = [], []
    seed = Vector((1.7, 3.3, 0.4))
    for i in range(N_AROUND + 1):  # the last column repeats the first, so the material's coordinates do not wrap
        th = 2 * math.pi * i / N_AROUND
        zt, zb = z_top(th), z_bottom(th)
        d = horiz(th)
        col = []
        for out, up, dr, dz, inner in PROFILE:
            h = up
            ri = r_inner(th, h)
            thick = FOAM + 0.003 * lap(th)
            r = ri + thick * out + dr
            z = zb + (zt - zb) * up + dz
            p = Vector((NECK.x, NECK.y, 0.0)) + d * r + Vector((0.0, 0.0, z))
            # soft foam: lumpy, a little crushed
            if out > 0.0:
                p += d * (0.0012 * noise.noise(p * 40.0 + seed))
            col.append(bm.verts.new(p))
            hz = (z - zb) / (zt - zb)
            attrs.append((i / N_AROUND, max(0.0, min(1.0, hz)), float(inner)))
        cols.append(col)
    m = len(PROFILE)
    for i in range(N_AROUND):
        a, b = cols[i], cols[i + 1]
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    # Merge the seam's twin vertices by position for the shading only: keep them split (the coordinates differ), but
    # point every face outward from the slab's middle
    bm.normal_update()
    for f in bm.faces:
        c = f.calc_center_median()
        rel = Vector((c.x - NECK.x, c.y - NECK.y, 0.0))
        th = math.atan2(-rel.x, rel.y)
        mid = Vector((NECK.x, NECK.y, 0.0)) + horiz(th) * (r_inner(th, 0.5) + FOAM / 2) + \
            Vector((0.0, 0.0, (z_top(th) + z_bottom(th)) / 2))
        if f.normal.dot(c - mid) < 0:
            f.normal_flip()
    obj = tk.mesh_object("Collar", bm, mat)
    set_attr(obj, attrs)
    return tk.smooth(obj, 50)


def strap(mat):
    """The hook-and-loop strap over the overlap at the back: a flat tab stuck across the seam, its free end lifted."""
    a0, a1 = math.radians(-26.0), math.radians(24.0)
    n = 10
    bm = bmesh.new()
    rings, attrs = [], []
    for k in range(n):
        f = k / (n - 1)
        th = a0 + (a1 - a0) * f
        d = horiz(th)
        zc = (z_top(th) + z_bottom(th)) / 2 - 0.004
        r = r_inner(th, 0.5) + FOAM + 0.003 * lap(th) + 0.0042 + 0.0025 * smoothstep(0.75, 1.0, f) ** 2
        ring = []
        for s, t in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            p = Vector((NECK.x, NECK.y, zc)) + d * (r + (t - 0.5) * 0.0028) + Vector((0.0, 0.0, s * 0.017))
            ring.append(bm.verts.new(p))
            attrs.append((0.5 + 0.5 * f, 0.5 + 0.5 * s, 2.0))
        rings.append(ring)
    for k in range(n - 1):
        a, b = rings[k], rings[k + 1]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Strap", bm, mat)
    set_attr(obj, attrs)
    return tk.smooth(obj, 40)


# ---------------------------------------------------------------- material

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


def vsub(g, vec, c):
    n = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = tuple(c)
    return n.outputs[0]


def collar_material(name):
    """A beige knit cover over foam: fine ribs running up it, a darker bound trim along both edges with a stitch
    line, the strap a greyer hook-and-loop. Yellowed along the top, grimy inside, dirt and blotches, dried blood run
    down the front from the mouth."""
    mat, g = tk.new_material(name)
    a = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    a.attribute_type = "GEOMETRY"
    u, h, kind = g.separate(tk._sock(a.outputs, "Vector"))
    inner = g.ramp(kind, 0.5, 0.9)
    is_strap = g.ramp(kind, 1.5, 1.9)
    P = mapping(g, g.coords(), loc=(0.17, 0.81, 0.33))
    x, y, z = g.separate(g.coords())

    def nz(scale, detail=4.0, r=0.55, dist=0.0, vec=P):
        return g.noise(scale, detail=detail, roughness=r, vector=vec, distortion=dist)

    col = g.mix(g.ramp(nz(5.0, 4.0), 0.25, 0.8), (0.235, 0.19, 0.135), (0.165, 0.13, 0.09))
    # Knit: fine ribs running up the collar
    ribs = g.math("SINE", g.math("MULTIPLY", u, 2 * math.pi * 170.0))
    height = g.math("MULTIPLY", g.math("ADD", ribs, g.math("MULTIPLY", nz(400.0, 2.0), 0.8)), 0.12)
    # Trim: the bound edges, darker and smoother, a stitch line inside each
    edge = g.math("MAXIMUM", g.ramp(h, 0.12, 0.06), g.ramp(h, 0.88, 0.94))
    edge = g.math("MAXIMUM", edge, g.math("MULTIPLY", inner, 0.0))
    col = g.mix(g.math("MULTIPLY", edge, 0.85), col, (0.13, 0.105, 0.075))
    stitch = g.math("MULTIPLY", g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", h, 0.13)), 0.012, 0.0),
                                       g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", h, 0.87)), 0.012, 0.0)),
                    g.ramp(g.math("FRACT", g.math("MULTIPLY", u, 260.0)), 0.25, 0.55))
    col = g.mix(g.math("MULTIPLY", stitch, 0.6), col, (0.09, 0.072, 0.05))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", stitch, 0.4))
    # The overlap seam at the back, under the strap
    seam = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", u, 0.94)), 0.006, 0.0),
                  g.math("SUBTRACT", 1.0, inner))
    col = g.mix(seam, col, (0.05, 0.04, 0.03))
    # Hook-and-loop strap
    hook = nz(600.0, 2.0)
    col = g.mix(is_strap, col, g.mix(g.ramp(hook, 0.3, 0.7), (0.07, 0.062, 0.05), (0.12, 0.105, 0.082)))
    height = g.mixf(is_strap, height, g.math("MULTIPLY", hook, 0.5))
    # Yellowed along the top (sweat, drool), the inside darker with grime and grease
    yel = g.math("MULTIPLY", g.ramp(h, 0.45, 0.92), g.ramp(nz(4.0, 5.0, 0.6, 0.4), 0.25, 0.55))
    col = g.mix(g.math("MULTIPLY", yel, 0.8), col, (0.17, 0.12, 0.045))
    tide = nz(2.6, 4.0, 0.55, 0.3)
    ring = g.math("MULTIPLY", g.ramp(tide, 0.53, 0.565), g.ramp(tide, 0.6, 0.565))
    col = g.mix(g.math("MULTIPLY", g.ramp(tide, 0.55, 0.59), 0.45), col, (0.12, 0.09, 0.055))
    col = g.mix(g.math("MULTIPLY", ring, 0.8), col, (0.07, 0.05, 0.03))
    col = g.mix(g.math("MULTIPLY", inner, 0.6), col, (0.075, 0.06, 0.042))
    # Dirt and grime, blotches, specks
    p = tk.photo(g, "rust_coarse_01", 2.4, (0.43, 0.12, 0.88))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.26, 0.07), 0.8)
    dirt = g.math("MAXIMUM", dirt, tk._grime(g, 1.1), clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, g.mix(nz(10.0), (0.045, 0.036, 0.026), (0.09, 0.072, 0.05)))
    blot = g.ramp(nz(3.0, 5.0, 0.6, 0.5), 0.5, 0.64)
    col = g.mix(g.math("MULTIPLY", blot, 0.65), col, (0.09, 0.07, 0.045))
    smudge = g.math("MULTIPLY", g.ramp(nz(6.0, 6.0, 0.65, 0.8), 0.5, 0.68), 0.6)
    col = g.mix(smudge, col, tk._darker(g, col, 0.45))
    grease = g.math("MULTIPLY", g.ramp(nz(11.0, 6.0, 0.7, 1.0), 0.55, 0.7), 0.5)
    col = g.mix(grease, col, (0.05, 0.042, 0.032))
    spots = g.ramp(voronoi(g, P, 150.0), 0.1, 0.04)
    col = g.mix(g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.5, 0.65)), col, (0.03, 0.024, 0.018))
    # Blood from the mouth: a ragged blot soaked into the front top a little off center, runs down from it, spatter
    fr = g.ramp(y, -0.015, -0.05)
    rel = vsub(g, g.coords(), (0.012, -0.05, 1.552))
    rx, ry, rz = g.separate(rel)
    d = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", rx, rx), g.math("MULTIPLY", g.math("MULTIPLY", rz, rz), 2.2)))
    f = g.math("SUBTRACT", 1.0, g.math("DIVIDE", d, 0.04))
    for k, (sc, amt) in enumerate(((24.0, 0.9), (70.0, 0.35))):
        f = g.math("ADD", f, g.math("MULTIPLY", g.math("SUBTRACT", nz(sc, 3.0, 0.6, 0.0,
                                                                     mapping(g, P, loc=(k, 0.4, 0.2))), 0.5), amt))
    soak = g.math("MULTIPLY", g.ramp(f, 0.3, 0.46), fr)
    rim = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(f, 0.26, 0.32), g.ramp(f, 0.42, 0.34)), fr)
    runs = g.ramp(g.noise(1.0, detail=3.0, vector=mapping(g, P, (110.0, 110.0, 6.0), loc=(0.3, 0.0, 0.0))), 0.6, 0.7)
    runs = g.math("MULTIPLY", g.math("MULTIPLY", runs, fr),
                  g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", x, 0.012)), 0.045, 0.015),
                         g.ramp(z, 1.56, 1.54)))
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 45.0), 0.12, 0.04),
                   g.math("MULTIPLY", fr, g.ramp(nz(3.0), 0.45, 0.6)))
    bl = g.math("MAXIMUM", g.math("MAXIMUM", soak, runs), drops)
    bl = g.math("MULTIPLY", bl, g.math("SUBTRACT", 1.0, is_strap))
    col = g.mix(bl, col, g.mix(nz(20.0), (0.03, 0.009, 0.006), (0.055, 0.017, 0.011)))
    col = g.mix(g.math("MULTIPLY", rim, 0.8), col, (0.022, 0.007, 0.005))
    rough = g.mixf(bl, g.mixf(dirt, 0.9, 0.95), 0.55)
    col = tk.grade(g, col, sat=0.85, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.3, 0.0012))


# ---------------------------------------------------------------- fit report, export, previews

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
    gaps = [math.hypot(p.x - NECK.x, p.y - NECK.y) - NECK_R for p in pts]
    print("[%s] inside the collar: %.1f cm off the assumed neck (radius %.1f cm)" % (NAME, 100 * min(gaps),
                                                                                       100 * NECK_R))
    # The chin, and where it goes when the jaw drops 20 and 30 degrees
    for deg in (0, 20, 30):
        v = CHIN - JAW_PIVOT
        rot = Matrix.Rotation(math.radians(deg), 3, "X")
        c = JAW_PIVOT + rot @ v
        d = min((p - c).length for p in pts)
        print("[%s] chin with the jaw dropped %d degrees (%.3f, %.3f, %.3f): %.1f cm from the collar"
              % (NAME, deg, c.x, c.y, c.z, 100 * d))
    return parts


def ellipsoid(name, center, radii, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1.0)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def standin():
    """The stand-in's head capsule covers the whole neck and jaw, and its chest capsule bulges up round the neck, so
    for the previews they are swapped for a skull, jaw, chin and neck and a lower chest (as the icicles do)."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] in ("Head", "Spine2"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
        if c["bone"] == "Spine2":
            ax = Vector((0.0, 0.0, 0.0))
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            zk._capsule("PreChest", sk.point("Spine2", ctr - ax * half),
                        sk.point("Spine2", ctr + ax * half) - Vector((0.0, 0.0, 0.07)), c["radius"], mat)
    ellipsoid("PreSkull", (0.0, 0.03, 1.738), (0.079, 0.1, 0.104), mat)
    ellipsoid("PreJaw", (0.0, -0.022, 1.652), (0.062, 0.066, 0.055), mat)
    ellipsoid("PreChin", (0.0, -0.062, 1.614), (0.024, 0.02, 0.02), mat)
    tk.cylinder("PreNeck", NECK_R, 1.45, 1.69, mat, segments=32, center=(NECK.x, NECK.y))


def close_up(view, direction, target, distance=0.5, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


foam = collar_material("CollarCover")
pieces = [collar(foam), strap(foam)]
export(pieces)
standin()
focus = Vector((0.0, 0.03, 1.57))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.75)
close_up("close", (0.45, -1.0, 0.2), focus, distance=0.42)
close_up("strap", (-0.5, 1.0, 0.25), focus, distance=0.42)
close_up("profile", (1.0, 0.0, 0.05), Vector((0.0, 0.0, 1.6)), distance=0.5)
print("[%s] done" % SCRIPT)
