"""Throat sacs: the Screecher's mutation. Its vocal sacs have swollen out of the throat like a bullfrog's gone wrong:
a big lumpy sac bulging from each side of the neck under the angle of the jaw (each with a smaller lobe below it
toward the throat) and a sagging pouch under the chin. Raw red-purple, stretched thin and shiny, inflamed, bruised
where they push out of the skin, knotted with dark swollen veins.

The neck sacs ride on the Neck bone ("Neck#Sacs"); the pouch under the chin rides on the jaw ("Jaw#Sacs"), so it
swings with the hanging jaw.

    blender -b --factory-startup --python throat_sacs.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], "ThroatSacs"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

rnd = random.Random(2203)


def jit(a):
    return rnd.uniform(-a, a)


tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

# Joe's neck as these sacs assume it: an upright column about 11 cm across around this axis
NECK_AXIS = Vector((0.0, 0.032, 0.0))
NECK_R = 0.055
CHIN = Vector((0.0, -0.078, 1.602))


# ---------------------------------------------------------------- helpers

def orth(v, axis):
    return (v - axis * v.dot(axis)).normalized()


def set_attr(obj, vals):
    """Per-vertex growth coordinates for the materials: (around 0-1, out 0-1, seed)."""
    me = obj.data
    at = me.attributes.new("gr", "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


class Sac:
    """A swollen sac: an ellipsoid around `center` with radii along (out, up, side), lumpy, sagging under its own
    weight, creased between lobes. `out` points away from the body; t runs from the inner pole (0, buried in the
    neck) to the outer dome (1)."""

    def __init__(self, center, out, up, radii, seed, sag=0.14, lumps=0.07, creases=()):
        self.c = Vector(center)
        self.e = Vector(out).normalized()
        self.u = orth(Vector(up), self.e)
        self.s = self.e.cross(self.u)
        self.r = radii
        self.seed = seed
        self.sag = sag
        self.lumps = lumps
        self.creases = [Vector(c).normalized() for c in creases]

    def point(self, d):
        """The surface point in the unit direction d, given in the sac's (out, up, side) frame."""
        d = Vector(d).normalized()
        k = 1.0 + self.lumps * noise.noise(d * 2.1 + Vector((self.seed * 3.7, self.seed * 1.9, 0.0)))
        k += 0.025 * noise.noise(d * 5.0 + Vector((0.0, self.seed * 2.3, self.seed)))
        for cr in self.creases:
            k -= 0.06 * math.exp(-(d.dot(cr) / 0.12) ** 2) * max(0.0, d.x)
        world = self.e * (d.x * self.r[0]) + self.u * (d.y * self.r[1]) + self.s * (d.z * self.r[2])
        world *= k
        # Sagging: the lower half hangs heavier and further out
        down = max(0.0, -world.normalized().z)
        world *= 1.0 + self.sag * down
        world.z -= self.sag * 0.25 * self.r[1] * max(0.0, d.x) * (1.0 - abs(d.y))
        return self.c + world

    def mesh(self, name, mat, u=28, v=18):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
        vals = []
        for vert in bm.verts:
            p = vert.co.copy()
            # The sphere's pole axis (z) becomes `out`
            d = Vector((p.z, p.x, p.y))
            vert.co = self.point(d)
            vals.append(((math.atan2(p.y, p.x) / (2 * math.pi)) % 1.0, (p.z + 1.0) / 2.0, self.seed))
        bm.normal_update()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        obj = tk.mesh_object(name, bm, mat)
        set_attr(obj, vals)
        return tk.smooth(obj, 80)

    def vein(self, name, mat, start, end, radius, seed, n=15, wiggle=0.1):
        """A swollen vein running over the sac between two directions (in its frame): it comes up out of the skin,
        runs along it half sunk in, and dives back under, thinning as it goes."""
        a, b = Vector(start).normalized(), Vector(end).normalized()
        side = a.cross(b).normalized()
        pts = []
        for i in range(n):
            f = i / (n - 1)
            d = a.slerp(b, f)
            d = (d + side * (wiggle * math.sin(f * math.pi * 2.3 + seed) * math.sin(f * math.pi))).normalized()
            p = self.point(d)
            # The surface normal, from the neighbouring surface points
            e1 = self.point((d + side * 0.02).normalized()) - self.point((d - side * 0.02).normalized())
            fwd = (b - a).normalized()
            e2 = self.point((d + fwd * 0.02).normalized()) - self.point((d - fwd * 0.02).normalized())
            normal = e2.cross(e1).normalized()
            if normal.dot(p - self.c) < 0:
                normal = -normal
            r = radius * (1.0 - 0.6 * f)
            rise = min(1.0, f / 0.12, (1.0 - f) / 0.12)
            pts.append((p + normal * (r * (0.25 * rise - 1.0 * (1.0 - rise))), r))
        return tube(name, pts, mat, seed)


def tube(name, pts, mat, seed, m=5):
    """A tube through (point, radius) pairs, closed at both ends, its frame carried along without twisting."""
    bm = bmesh.new()
    vals = []
    rings = []
    t0 = (pts[1][0] - pts[0][0]).normalized()
    nrm = orth(Vector((0.0, 0.0, 1.0)) if abs(t0.z) < 0.9 else Vector((1.0, 0.0, 0.0)), t0)
    for i, (p, r) in enumerate(pts):
        if i < len(pts) - 1:
            t = (pts[i + 1][0] - p).normalized()
        nrm = orth(nrm, t)
        bi = t.cross(nrm)
        ring = []
        for q in range(m):
            ang = 2 * math.pi * q / m
            ring.append(bm.verts.new(p + nrm * (math.cos(ang) * r) + bi * (math.sin(ang) * r)))
            vals.append((q / m, i / (len(pts) - 1), seed))
        rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new((A[j], A[k], B[k], B[j]))
    for ring, p, at in ((rings[0], pts[0][0] - (pts[1][0] - pts[0][0]).normalized() * pts[0][1], 0.0),
                        (rings[-1], pts[-1][0] + (pts[-1][0] - pts[-2][0]).normalized() * pts[-1][1], 1.0)):
        c = bm.verts.new(p)
        vals.append((0.5, at, seed))
        for j in range(m):
            bm.faces.new((ring[j], ring[(j + 1) % m], c))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, 70)


# ---------------------------------------------------------------- materials

def gr(g):
    n = g.node("ShaderNodeAttribute", attribute_name="gr")
    return g.separate(tk._sock(n.outputs, "Vector"))


def warped(g, scale, amount):
    """Object coordinates warped by noise (organic, not grid-like)."""
    warp = g.node("ShaderNodeTexNoise")
    g._in(warp, "Scale", scale)
    g._in(warp, "Detail", 3.0)
    g.links.new(g.coords(), warp.inputs["Vector"])
    mix = g.node("ShaderNodeMix", data_type="VECTOR")
    g._in(mix, "Factor_Float", amount)
    g.links.new(g.coords(), tk._sock(mix.inputs, "A_Vector"))
    g.links.new(tk._sock(warp.outputs, "Color"), tk._sock(mix.inputs, "B_Vector"))
    return tk._sock(mix.outputs, "Result_Vector")


def veins(g, scale, width, amount=0.12):
    """Winding, branching veins (the contour lines of a warped noise), broken up, 1 on a vein."""
    n = g.noise(1.0, detail=3.0, roughness=0.5, vector=_scaled(g, warped(g, scale * 0.3, amount), scale))
    line = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), width, 0.0)
    return g.math("MULTIPLY", line, g.ramp(g.noise(scale * 0.3, detail=3.0), 0.34, 0.54))


def _scaled(g, vec, k):
    n = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(vec, n.inputs[0])
    tk._sock(n.inputs, "Scale").default_value = k
    return n.outputs[0]


def sac_material(name):
    """Raw, stretched sac skin: dark red-purple and wet over the dome, mottled with angrier red, a web of dark veins
    (thicker toward the base), a few pale pus blisters; bruised, wrinkled, duller skin where it pushes out of the
    neck (t low)."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    blot = g.noise(26.0, detail=5.0, distortion=0.4)
    fine = g.noise(140.0, detail=4.0)
    col = g.mix(g.ramp(blot, 0.3, 0.72), (0.36, 0.05, 0.09), (0.19, 0.035, 0.1))
    angry = g.ramp(g.noise(12.0, detail=4.0, distortion=0.6), 0.5, 0.72)
    col = g.mix(g.math("MULTIPLY", angry, 0.7), col, (0.48, 0.07, 0.05))
    col = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.4, 0.75), 0.3), col, (0.13, 0.02, 0.05))
    # Where it pushes out of the neck: bruised skin, stretched into pale marks
    base = g.ramp(t, g.math("ADD", 0.5, g.math("MULTIPLY", blot, 0.12)), 0.36)
    skin = g.mix(g.ramp(blot, 0.35, 0.7), (0.27, 0.16, 0.17), (0.17, 0.09, 0.13))
    marks = g.noise(1.0, detail=2.0, vector=_stretch_vec(g, a, t, seed))
    stretch = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", marks, 0.5)), 0.035, 0.0)
    skin = g.mix(g.math("MULTIPLY", stretch, 0.6), skin, (0.42, 0.27, 0.27))
    col = g.mix(base, col, skin)
    big = veins(g, 22.0, 0.022, 0.18)
    small = veins(g, 70.0, 0.018, 0.12)
    vein = g.math("MAXIMUM", big, g.math("MULTIPLY", small, 0.7))
    col = g.mix(g.math("MULTIPLY", vein, 0.85), col, (0.07, 0.02, 0.09))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 70.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    blister = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.16, 0.07),
                     g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=3.0), 0.6, 0.7), g.ramp(t, 0.55, 0.75)))
    col = g.mix(blister, col, (0.55, 0.42, 0.18))
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.02), clamp=True), 1.5, clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.05, 0.015, 0.02))
    rough = g.math("ADD", 0.2, g.math("MULTIPLY", fine, 0.1))
    rough = g.mixf(base, rough, 0.5)
    rough = g.mixf(dirt, rough, 0.6)
    rough = g.mixf(blister, rough, 0.35)
    height = g.math("ADD", g.math("MULTIPLY", vein, 0.7), g.math("MULTIPLY", fine, 0.25))
    height = g.math("ADD", height, g.math("MULTIPLY", blister, 0.6))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MULTIPLY", stretch, base), 0.5))
    # Muted to a bruised, dirty flesh: at full strength the reds read as bright pink balloons in game
    col = tk.grade(g, col, sat=0.65, value=0.62)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.35, 0.0025))


def _stretch_vec(g, a, t, seed):
    """Coordinates for stretch marks: they run around the sac's base, so vary fast along t, slowly around."""
    ang = g.math("MULTIPLY", a, 2 * math.pi)
    v = g.node("ShaderNodeCombineXYZ")
    g._in(v, "X", g.math("MULTIPLY", g.math("COSINE", ang), 0.9))
    g._in(v, "Y", g.math("MULTIPLY", g.math("SINE", ang), 0.9))
    g._in(v, "Z", g.math("ADD", g.math("MULTIPLY", t, 26.0), g.math("MULTIPLY", seed, 7.3)))
    return v.outputs[0]


def vein_material(name):
    """A swollen vein: dark blue-purple, wet."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    n = g.noise(220.0, detail=4.0)
    col = g.mix(g.ramp(n, 0.3, 0.7), (0.09, 0.03, 0.11), (0.16, 0.04, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.6, 1.0), 0.5), col, (0.25, 0.06, 0.1))
    rough = g.math("ADD", 0.26, g.math("MULTIPLY", n, 0.12))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(n, 0.2, 0.001))


sacm = sac_material("SacSkin")
veinm = vein_material("SacVein")


# ---------------------------------------------------------------- the sacs

def neck_point(z, direction):
    """Where a horizontal direction from the neck's axis meets its surface at height z."""
    d = Vector((direction[0], direction[1], 0.0)).normalized()
    return Vector((NECK_AXIS.x, NECK_AXIS.y, z)) + d * NECK_R


neck_pieces, jaw_pieces = [], []
for s, seed in ((1.0, 0.31), (-1.0, 0.77)):
    out = Vector((s * 1.0, -0.38, -0.1)).normalized()
    # The big sac, a third of it buried in the neck, its top tucked under the angle of the jaw
    base = neck_point(1.579, out)
    big = Sac(base + out * 0.021 + Vector((jit(0.002), jit(0.002), 0.0)), out, (0, 0, 1),
              (0.044, 0.043, 0.045), seed, sag=0.14, lumps=0.1,
              creases=((0.25, 0.15, 1.0), (0.35, -0.9, 0.2)))
    neck_pieces.append(big.mesh("Sac%d" % int(s), sacm))
    # A smaller lobe below it, toward the front of the throat
    out2 = Vector((s * 0.75, -0.7, -0.35)).normalized()
    lobe = Sac(neck_point(1.538, out2) + out2 * 0.008, out2, (0, 0, 1), (0.026, 0.028, 0.027), seed + 0.5,
               sag=0.1, lumps=0.06)
    neck_pieces.append(lobe.mesh("Lobe%d" % int(s), sacm, u=18, v=12))
    # Veins from where it comes out of the neck, up and over the dome
    for k, (st, en, r) in enumerate((((-0.1, -0.75, 0.55), (0.92, 0.2, -0.25), 0.0026),
                                     ((-0.05, 0.85, 0.3), (0.88, 0.1, 0.4), 0.0022))):
        neck_pieces.append(big.vein("Vein%d_%d" % (int(s), k), veinm, st, en, r, seed * 10 + k))

# The pouch under the chin, sagging, its front kept behind the chin
pouch = Sac(Vector((0.0, -0.032, 1.584)), (0, 0, -1), (0, 1, 0), (0.034, 0.033, 0.042), 1.13, sag=0.1, lumps=0.08,
            creases=((0.2, 0.0, 1.0),))
jaw_pieces.append(pouch.mesh("Pouch", sacm, u=24, v=14))
for k, (st, en, r) in enumerate((((0.1, 0.9, 0.35), (0.92, -0.2, -0.15), 0.0021),)):
    jaw_pieces.append(pouch.vein("PouchVein%d" % k, veinm, st, en, r, 7.0 + k))

pieces = []
for o in neck_pieces:
    pieces.append(zk.on(o, "Neck", "Sacs"))
for o in jaw_pieces:
    pieces.append(zk.on(o, "Jaw", "Sacs"))


# ---------------------------------------------------------------- a better stand-in head and neck (previews only)

def ellipsoid(name, center, radii, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1.0)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def standin_head():
    """The stand-in's head capsule reaches down over the whole neck and its chest capsule up past the base of the
    neck, so for these previews they're swapped for a skull, a jaw, a neck column and a slightly lower chest."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] in ("Head", "Spine2"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
        if c["bone"] == "Spine2":
            ax = [0.0, 0.0, 0.0]
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            a = sk.point("Spine2", ctr - Vector(ax) * half)
            b = sk.point("Spine2", ctr + Vector(ax) * half) - Vector((0.0, 0.0, 0.05))
            zk._capsule("PreChest", a, b, c["radius"], mat)
    ellipsoid("PreSkull", (0.0, 0.03, 1.738), (0.079, 0.1, 0.104), mat)
    ellipsoid("PreJaw", (0.0, -0.022, 1.652), (0.062, 0.066, 0.055), mat)
    ellipsoid("PreChin", CHIN + Vector((0.0, 0.016, 0.012)), (0.024, 0.02, 0.02), mat)
    tk.cylinder("PreNeck", NECK_R, 1.44, 1.69, mat, segments=32, center=(NECK_AXIS.x, NECK_AXIS.y))


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


report("throat_sacs", pieces)
standin_head()
parts = zk.export("ThroatSacs", pieces, ASSETS)
zk.previews("throat_sacs", PREVIEWS, Vector((0.0, 0.0, 1.6)), distance=0.95)


def closeup(name, focus, direction, dist=0.42, lens=50):
    cam = tk.camera(name, focus + Vector(direction).normalized() * dist, focus, lens=lens)
    tk.render(cam, os.path.join(PREVIEWS, "%s.png" % name), res=(900, 900), samples=64)


neck = Vector((0.0, 0.0, 1.585))
closeup("throat_sacs_neck_front", neck, (0.0, -1.0, 0.05))
closeup("throat_sacs_neck_below", neck, (0.25, -0.8, -0.55))
closeup("throat_sacs_neck_side", neck, (1.0, 0.05, 0.05))
closeup("throat_sacs_neck_close", Vector((0.07, -0.01, 1.58)), (0.8, -0.6, 0.1), dist=0.22)
print("[throat_sacs] done")
