"""Cigar (remnant): a fat cigar, half smoked and gone out, still clamped in the right corner of the mouth. About 8 cm
of it sticks out of the lips, angled down 20 degrees and out to the side; the chewed, spit-darkened head end is in the
mouth. A dark maduro wrapper with its leaf veins and the helical seam of the rolled leaf, oily and grimy, a faded
paper band near the lips (dull red, tarnished gold rims and crest), blood smeared near the mouth. The burnt end is
dead: a charred ring where the wrapper burnt back, a grey-white flaky ash cap broken away on one side over the dull
black charcoal of the burnt end, at most a faint dark-orange scorch in the albedo. Nothing glows.

Fitted to Joe's real face (the face proxy from sunglasses.py, made to the REMNANTS.md face points): the head end
sinks 1.5 cm behind the corner of the lips, so it stays hidden in the mouth on the slimmer faces. On the Jaw bone, so
it moves with the mouth when it opens. One part: "Jaw#Cigar".

    blender -b --factory-startup --python cigar.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT = "Cigar", "cigar"
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
RND = random.Random(5150)
EYES = (Vector((0.032, -0.075, 1.719)), Vector((-0.032, -0.075, 1.719)))
JAW_PIVOT = SK.pos("Jaw")


# ---------------------------------------------------------------- mesh helpers

def set_attr(obj, name, vals):
    me = obj.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def cut(obj, cutter, slot=0):
    for p in cutter.data.polygons:
        p.material_index = slot
    mod = obj.modifiers.new("Cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.material_mode = "INDEX"
    mod.object = cutter
    tk.apply_modifiers(obj)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return obj


def blob(name, center, radii, mat, exps=(2.0, 2.0), rot_x=0.0, segs=28, rings=18):
    """A superellipsoid: exps = (around, up) exponents, 2 for an ellipsoid, higher for boxier."""
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
    """Joe's real face, neck and shoulders (as sunglasses.py makes them), to fit against and show the cigar on in
    the previews. Not exported."""
    mat, g = tk.new_material("ProxySkin")
    tk.finish(mat, g, (0.46, 0.38, 0.34), 0.0, 0.65)
    eye_mat, g = tk.new_material("ProxyEye")
    tk.finish(eye_mat, g, (0.06, 0.05, 0.045), 0.0, 0.15)
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
        parts.append(blob("Arch", (s * 0.06, -0.025, 1.694), (0.012, 0.035, 0.01), mat))
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
    mod.voxel_size = 0.0025
    tk.apply_modifiers(obj)
    mod = obj.modifiers.new("Smooth", "SMOOTH")
    mod.factor = 0.8
    mod.iterations = 6
    tk.apply_modifiers(obj)
    for s in (1.0, -1.0):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.0165)
        bmesh.ops.translate(bm, vec=(s * 0.032, -0.089, 1.723), verts=bm.verts)
        cut(obj, tk.mesh_object("Socket", bm, mat), 0)
    obj.data.materials.append(eye_mat)
    eyes = []
    for e in EYES:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.0125)
        bmesh.ops.translate(bm, vec=e + Vector((0.0, 0.0125, 0.0)), verts=bm.verts)
        eyes.append(tk.mesh_object("Eye", bm, eye_mat))
    obj = tk.join([obj] + eyes, "FaceProxy")
    tk.smooth(obj, 60)
    obj["zbody"] = True
    return obj


PROXY = face_proxy()


def proxy_bvh():
    bm = bmesh.new()
    bm.from_mesh(PROXY.data)
    bm.transform(PROXY.matrix_world)
    return BVHTree.FromBMesh(bm)


def inside(bvh, p):
    """Whether p is inside the face proxy (the nearest surface faces away from it)."""
    loc, nrm, _, _ = bvh.find_nearest(p)
    return (p - loc).dot(nrm) < 0, (p - loc).length


# ---------------------------------------------------------------- material helpers

def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def attr(g, name):
    n = g.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name)
    return tk._sock(n.outputs, "Vector")


def combine(g, x, y, z=0.0):
    n = g.node("ShaderNodeCombineXYZ")
    g._in(n, "X", x)
    g._in(n, "Y", y)
    g._in(n, "Z", z)
    return n.outputs[0]


def voronoi(g, vec, scale, feature="F1", output="Distance"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, output)


def mul(g, a, b):
    return g.math("MULTIPLY", a, b)


def add(g, a, b):
    return g.math("ADD", a, b)


def sub(g, a, b):
    return g.math("SUBTRACT", a, b)


def band(g, x, lo, hi, soft=0.0005):
    """1 between lo and hi, soft edges."""
    return mul(g, g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def lines(g, vec, scale, rot, width, loc=(0.0, 0.0, 0.0)):
    """Thin wavering lines: contours of stretched noise."""
    n = g.noise(1.0, detail=2.0, roughness=0.4, vector=mapping(g, vec, scale, rot, loc))
    return sub(g, 1.0, g.ramp(g.math("ABSOLUTE", sub(g, n, 0.5)), 0.0, width, False))


def unwrapped(g):
    """The cigar's surface laid flat in meters: (around, along, radius) from the stored cg = (s, turn, r)."""
    s, t, r = g.separate(attr(g, "cg"))
    return combine(g, mul(g, t, 2 * math.pi * R), s, r), s, t, r


# ---------------------------------------------------------------- the cigar's shape

R = 0.0099  # 50 ring gauge (19.8 mm)
L = 0.095  # what's left of it: 1.5 cm in the mouth, 8 cm out
S_IN = 0.015  # how far the head end sits behind the lips' corner
S_CHAR = 0.0795  # the wrapper burnt back to here (varies round)
S_ASH = 0.0835  # the ash starts
S_BAND = (0.0205, 0.0335)  # the paper band, from the head end
SIDES = 16
CORNER = Vector((-0.0255, -0.0745, 1.6445))  # the right corner of the lips (the zombie's right is -X)
YAW, PITCH = math.radians(32.0), math.radians(20.0)  # out to the side from straight ahead, down
AXIS = Vector((-math.sin(YAW) * math.cos(PITCH), -math.cos(YAW) * math.cos(PITCH), -math.sin(PITCH)))
UPV = (Vector((0.0, 0.0, 1.0)) - AXIS * AXIS.z).normalized()  # turn 0 on top
SIDEV = AXIS.cross(UPV)
HEAD = CORNER - AXIS * S_IN
BROKE = math.radians(200.0)  # where the ash broke away (turn angle from the top, toward the bottom-outside)


def char_s(th):
    """Where the wrapper's burnt edge is, round the cigar: uneven, burnt further back on one side."""
    return S_CHAR + 0.0016 * math.sin(th * 2 + 0.7) + 0.0012 * math.sin(th * 3 + 2.1) - 0.0018 * max(0.0, math.cos(th - 1.1))


def ash_end(th):
    """The ash cap's end, broken back on one side."""
    broke = max(0.0, math.cos(th - BROKE)) ** 1.5
    return L - 0.0065 * broke + 0.0007 * math.sin(th * 5 + 0.3)


def radius(s, th):
    """The cigar's radius at s from the head end and turn angle th."""
    wob = 1.0 + 0.012 * noise.noise(Vector((math.cos(th) * 1.3, math.sin(th) * 1.3, s * 60.0)))
    r = R * wob
    if s < 0.012:  # the chewed head end: pinched flat between the teeth, frayed
        k = 1.0 - (0.012 - s) / 0.012
        flat = 1.0 - 0.28 * (1.0 - k) * abs(math.sin(th))  # squashed top to bottom... across the bite
        r *= flat * (0.93 + 0.07 * k)
        r *= 1.0 + (1.0 - k) * 0.05 * noise.noise(Vector((math.cos(th) * 4, math.sin(th) * 4, 3.3)))
    if s > S_CHAR - 0.003:  # the wrapper shrinks a little where it charred, the ash swells a touch
        c = char_s(th)
        if s > c:
            r *= 0.965
        if s > S_ASH:
            r *= 1.0 + 0.04 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3, s * 400.0)))
    return r


def place(s, th, r):
    return HEAD + AXIS * s + (UPV * math.cos(th) + SIDEV * math.sin(th)) * r


def cigar_body(wrapper, char, ash, coal):
    """One closed mesh: the chewed head cap, the wrapper, the charred ring, the ash and the broken end over the
    charcoal. cg = (s along, turn 0-1, radius) per vertex for the materials."""
    bm = bmesh.new()
    vals = []

    def vert(p, s, th, r):
        vals.append((s, (th / (2 * math.pi)) % 1.0, r))
        return bm.verts.new(p)

    # Rings along the cigar (s per turn angle can bend round the burnt edge)
    ring_s = [0.0, 0.002, 0.006, 0.012, 0.019, S_BAND[0], S_BAND[1], 0.042, 0.052, 0.062, 0.071]
    rings = []
    for s in ring_s:
        rings.append([(s, 2 * math.pi * j / SIDES) for j in range(SIDES)])
    # The burnt edge: the last wrapper ring follows it, then the char, then the ash rings
    rings.append([(char_s(2 * math.pi * j / SIDES) - 0.0012, 2 * math.pi * j / SIDES) for j in range(SIDES)])
    rings.append([(char_s(2 * math.pi * j / SIDES), 2 * math.pi * j / SIDES) for j in range(SIDES)])
    rings.append([(S_ASH, 2 * math.pi * j / SIDES) for j in range(SIDES)])
    for f in (0.35, 0.7, 1.0):
        rings.append([(S_ASH + (ash_end(2 * math.pi * j / SIDES) - S_ASH) * f, 2 * math.pi * j / SIDES)
                      for j in range(SIDES)])
    mats = ([0] * (len(ring_s) - 1) + [0, 1, 1] + [2, 2, 2])  # material of the faces from each ring to the next
    vrings = []
    for ring in rings:
        vrings.append([vert(place(s, th, radius(s, th)), s, th, radius(s, th)) for s, th in ring])
    faces = []
    for k in range(len(vrings) - 1):
        a, b = vrings[k], vrings[k + 1]
        for j in range(SIDES):
            j1 = (j + 1) % SIDES
            f = bm.faces.new((a[j], a[j1], b[j1], b[j]))
            f.material_index = mats[k]
    # The head end: a frayed, pinched cap
    c0 = vert(HEAD - AXIS * 0.0015, 0.0, 0.0, 0.0)
    for j in range(SIDES):
        f = bm.faces.new((vrings[0][(j + 1) % SIDES], vrings[0][j], c0))
        f.material_index = 0
    # The burnt end: the ash rim rolls in over a ring of ash, then the charcoal cone, sunk in where the ash broke
    last = vrings[-1]
    lips = []
    for j in range(SIDES):
        th = 2 * math.pi * j / SIDES
        s = ash_end(th) - 0.0009
        r = radius(s, th) * 0.5
        lips.append(vert(place(s, th, r), s, th, r))
    for j in range(SIDES):
        j1 = (j + 1) % SIDES
        f = bm.faces.new((last[j], last[j1], lips[j1], lips[j]))
        f.material_index = 2
    core = []
    for j in range(SIDES):
        th = 2 * math.pi * j / SIDES
        s = ash_end(th) - 0.0022
        r = R * 0.22
        core.append(vert(place(s, th, r), s, th, r))
    for j in range(SIDES):
        j1 = (j + 1) % SIDES
        f = bm.faces.new((lips[j], lips[j1], core[j1], core[j]))
        f.material_index = 3
    tip = vert(HEAD + AXIS * (L - 0.0038) + (UPV * math.cos(BROKE) + SIDEV * math.sin(BROKE)) * 0.0015, L - 0.0038, 0.0, 0.0)
    for j in range(SIDES):
        f = bm.faces.new((core[j], core[(j + 1) % SIDES], tip))
        f.material_index = 3
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Cigar", bm, wrapper)
    for m in (char, ash, coal):
        obj.data.materials.append(m)
    set_attr(obj, "cg", vals)
    return tk.smooth(obj, 50)


def paper_band(mat):
    """The paper band round the cigar near the lips: a thin ring standing 0.4 mm proud, torn at one edge."""
    bm = bmesh.new()
    vals = []
    rows = []
    s0, s1 = S_BAND
    for s in (s0, s0 + 0.0005, s1 - 0.0005, s1):
        row = []
        for j in range(SIDES):
            th = 2 * math.pi * j / SIDES
            out = 0.0004 if s0 < s < s1 else 0.0001
            r = radius(s, th) + out
            row.append(bm.verts.new(place(s, th, r)))
            vals.append((s - s0, (th / (2 * math.pi)) % 1.0, r))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for j in range(SIDES):
            j1 = (j + 1) % SIDES
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Band", bm, mat)
    set_attr(obj, "cg", vals)
    return tk.smooth(obj, 50)


# ---------------------------------------------------------------- materials

def wrapper_material():
    """A dark maduro wrapper leaf: brown with darker mottling, fine leaf veins running across the roll, the helical
    seam where the leaf overlaps, an oily sheen; the head end wet and darkened with spit and blood, grime and specks
    over it all."""
    mat, g = tk.new_material("Wrapper")
    U, s, t, r = unwrapped(g)
    P = mapping(g, g.coords(), loc=(3.1, 0.7, 1.9))
    tone = g.noise(70.0, detail=6.0, roughness=0.6, vector=P)
    col = g.mix(g.ramp(tone, 0.3, 0.75), (0.017, 0.009, 0.0045), (0.045, 0.024, 0.011))
    blotch = g.ramp(g.noise(25.0, detail=4.0, vector=P), 0.55, 0.75)
    col = g.mix(mul(g, blotch, 0.6), col, (0.02, 0.011, 0.006))
    # Leaf veins: thin pale lines slanting across the roll, and a few heavier ribs
    veins = lines(g, U, (180.0, 600.0, 1.0), (0.0, 0.0, 0.6), 0.03)
    veins = mul(g, veins, g.ramp(g.noise(90.0, detail=2.0, vector=U), 0.4, 0.55))
    ribs = lines(g, U, (60.0, 220.0, 1.0), (0.0, 0.0, 0.62), 0.025, loc=(0.3, 0.1, 0.0))
    col = g.mix(mul(g, veins, 0.45), col, (0.065, 0.04, 0.022))
    col = g.mix(mul(g, ribs, 0.35), col, (0.058, 0.036, 0.02))
    # The seam: where the rolled leaf's edge overlaps, spiralling down the cigar
    f = g.math("FRACT", add(g, t, g.math("DIVIDE", s, 0.034)))
    seam = g.ramp(g.math("ABSOLUTE", sub(g, f, 0.5)), 0.46, 0.49)
    col = g.mix(mul(g, seam, 0.8), col, (0.018, 0.01, 0.005))
    height = add(g, mul(g, veins, 0.5), add(g, mul(g, ribs, 0.8), mul(g, seam, -1.2)))
    height = add(g, height, mul(g, g.noise(300.0, detail=3.0, vector=P), 0.25))
    rough = add(g, 0.5, mul(g, tone, 0.18))
    # Spit and blood at the chewed end, drying to a ragged line along it
    wet_edge = add(g, s, mul(g, sub(g, g.noise(160.0, detail=4.0, vector=P), 0.5), 0.008))
    wet = g.ramp(wet_edge, 0.019, 0.012)
    col = g.mix(mul(g, wet, 0.7), col, tk._darker(g, col, 0.45))
    rough = g.mixf(wet, rough, 0.22)
    blood = mul(g, g.ramp(wet_edge, 0.024, 0.008), g.ramp(g.noise(55.0, detail=5.0, distortion=0.8, vector=P), 0.45, 0.62))
    col = g.mix(mul(g, blood, 0.9), col, (0.055, 0.006, 0.004))
    rough = g.mixf(blood, rough, 0.3)
    # Soot creeping up from the burnt end
    soot = mul(g, g.ramp(add(g, s, mul(g, sub(g, g.noise(90.0, vector=P), 0.5), 0.01)), 0.062, 0.079), 0.85)
    col = g.mix(soot, col, (0.016, 0.012, 0.009))
    rough = g.mixf(soot, rough, 0.85)
    dirt = mul(g, g.ramp(g.noise(18.0, detail=6.0, roughness=0.65, vector=P), 0.56, 0.72), 0.7)
    col = g.mix(dirt, col, (0.03, 0.024, 0.018))
    rough = g.mixf(dirt, rough, 0.85)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.25)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.35, 0.0015))


def band_material():
    """The paper band: faded dark red, tarnished gold rims and a crest on the front, scuffed through to the paper,
    a greasy thumb-dark patch, torn at one edge."""
    mat, g = tk.new_material("BandPaper")
    U, s, t, r = unwrapped(g)
    P = mapping(g, g.coords(), loc=(1.7, 2.2, 0.4))
    h = S_BAND[1] - S_BAND[0]
    red = g.mix(g.ramp(g.noise(60.0, detail=4.0, vector=P), 0.3, 0.7), (0.07, 0.01, 0.009), (0.115, 0.02, 0.016))
    gold = g.mix(g.ramp(g.noise(80.0, detail=4.0, vector=P), 0.3, 0.7), (0.14, 0.1, 0.038), (0.21, 0.15, 0.058))
    rims = g.math("MAXIMUM", band(g, s, 0.0008, 0.0022), band(g, s, h - 0.0022, h - 0.0008))
    # The crest: a gold oval with a dark center and a ring of dots, on the side facing up and out
    ct = sub(g, g.math("FRACT", add(g, t, 0.5 - 0.9 / (2 * math.pi) / 1.0)), 0.5)  # turn from the crest's center
    cu = mul(g, ct, 2 * math.pi * R)
    cv = sub(g, s, h / 2)
    d = g.math("SQRT", add(g, mul(g, mul(g, cu, 0.8), mul(g, cu, 0.8)), mul(g, cv, cv)))
    oval = band(g, d, 0.0, 0.0047, 0.0003)
    ring = band(g, d, 0.0032, 0.0041, 0.0002)
    col = g.mix(rims, red, gold)
    col = g.mix(oval, col, gold)
    col = g.mix(mul(g, sub(g, oval, ring), g.ramp(d, 0.0033, 0.0029)), col, (0.05, 0.012, 0.01))
    col = g.mix(ring, col, (0.12, 0.08, 0.03))
    metal = mul(g, g.math("MAXIMUM", rims, oval), 0.55)
    rough = g.mixf(g.math("MAXIMUM", rims, oval), 0.7, 0.42)
    height = add(g, mul(g, rims, 0.4), mul(g, ring, 0.6))
    # Worn: scuffed to pale paper, grease, grime, a torn notch at the lips' end
    scuff = mul(g, g.ramp(g.noise(45.0, detail=6.0, roughness=0.7, vector=P), 0.62, 0.7), 0.85)
    col = g.mix(scuff, col, (0.16, 0.14, 0.11))
    metal = g.mixf(scuff, metal, 0.0)
    rough = g.mixf(scuff, rough, 0.85)
    grease = g.ramp(g.noise(9.0, detail=4.0, vector=P), 0.5, 0.65)
    col = g.mix(mul(g, grease, 0.6), col, tk._darker(g, col, 0.4))
    blood = mul(g, g.ramp(g.noise(30.0, detail=5.0, distortion=0.9, vector=P), 0.6, 0.7), g.ramp(s, 0.007, 0.0))
    col = g.mix(blood, col, (0.05, 0.006, 0.004))
    col, rough, metal = tk._grit(g, col, rough, metal, 0.3)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.3, 0.001))


def char_material():
    """The ring where the wrapper burnt back: black-brown, crusted, a faint dark orange scorch toward the ash."""
    mat, g = tk.new_material("Char")
    U, s, t, r = unwrapped(g)
    P = mapping(g, g.coords(), loc=(0.2, 1.4, 2.6))
    n = g.noise(400.0, detail=5.0, roughness=0.7, vector=P)
    col = g.mix(g.ramp(n, 0.3, 0.75), (0.014, 0.011, 0.009), (0.04, 0.026, 0.016))
    scorch = mul(g, g.ramp(g.noise(120.0, detail=3.0, vector=P), 0.45, 0.7), 0.6)
    col = g.mix(scorch, col, (0.075, 0.03, 0.01))
    cracks = g.ramp(voronoi(g, P, 500.0, "DISTANCE_TO_EDGE"), 0.06, 0.0)
    col = g.mix(mul(g, cracks, 0.8), col, (0.006, 0.005, 0.004))
    return tk.finish(mat, g, col, 0.0, add(g, 0.82, mul(g, n, 0.1)), g.bump(add(g, n, mul(g, cracks, -1.0)), 0.5, 0.001))


def ash_material():
    """Cigar ash: layered grey-white flakes in rings round the cigar, darker grey between the layers, cracked, dusty
    and dull; darker toward the charcoal where it broke."""
    mat, g = tk.new_material("Ash")
    U, s, t, r = unwrapped(g)
    P = mapping(g, g.coords(), loc=(2.6, 0.3, 1.1))
    layers = g.math("SINE", mul(g, add(g, s, mul(g, g.noise(200.0, detail=3.0, vector=P), 0.0015)), 2 * math.pi / 0.0016))
    layer = g.ramp(layers, -0.4, 0.8)
    flecks = g.noise(700.0, detail=4.0, roughness=0.7, vector=P)
    col = g.mix(layer, (0.085, 0.082, 0.076), (0.2, 0.193, 0.18))
    col = g.mix(mul(g, g.ramp(flecks, 0.62, 0.72), 0.7), col, (0.26, 0.252, 0.235))
    col = g.mix(mul(g, g.ramp(flecks, 0.35, 0.25), 0.6), col, (0.07, 0.066, 0.06))
    cracks = g.ramp(voronoi(g, mapping(g, P, scale=(1.0, 1.0, 1.0)), 260.0, "DISTANCE_TO_EDGE"), 0.025, 0.0)
    cracks = mul(g, cracks, g.ramp(g.noise(150.0, detail=3.0, vector=P), 0.4, 0.6))
    col = g.mix(mul(g, cracks, 0.55), col, (0.07, 0.066, 0.06))
    # Toward the charcoal (the inner edge and the broken side): darker and sooty
    inner = g.ramp(r, R * 0.85, R * 0.62)
    col = g.mix(mul(g, inner, 0.75), col, (0.05, 0.045, 0.04))
    height = add(g, mul(g, layer, 0.6), add(g, mul(g, flecks, 0.4), mul(g, cracks, -0.8)))
    return tk.finish(mat, g, col, 0.0, 0.96, g.bump(height, 0.6, 0.001))


def coal_material():
    """The dead charcoal of the burnt end: matte black with fine cracks and a few dull rust-brown flecks."""
    mat, g = tk.new_material("Coal")
    P = mapping(g, g.coords(), loc=(0.9, 0.2, 3.3))
    n = g.noise(500.0, detail=5.0, roughness=0.7, vector=P)
    col = g.mix(g.ramp(n, 0.3, 0.7), (0.012, 0.011, 0.01), (0.03, 0.026, 0.022))
    flecks = mul(g, g.ramp(g.noise(300.0, detail=3.0, vector=P), 0.66, 0.74), 0.7)
    col = g.mix(flecks, col, (0.07, 0.03, 0.012))
    cracks = g.ramp(voronoi(g, P, 700.0, "DISTANCE_TO_EDGE"), 0.07, 0.0)
    col = g.mix(cracks, col, (0.004, 0.004, 0.004))
    return tk.finish(mat, g, col, 0.0, add(g, 0.7, mul(g, n, 0.2)), g.bump(sub(g, n, cracks), 0.6, 0.001))


WRAPPER, BAND, CHAR, ASH, COAL = (wrapper_material(), band_material(), char_material(), ash_material(),
                                  coal_material())

# ---------------------------------------------------------------- build, check, export, previews

pieces = [cigar_body(WRAPPER, CHAR, ASH, COAL), paper_band(BAND)]
for p in pieces:
    zk.on(p, "Jaw", "Cigar")

bvh = proxy_bvh()
for label, s in (("head end", 0.0), ("1 cm in", 0.005), ("at the lips", S_IN), ("1 cm out", S_IN + 0.01),
                 ("2 cm out", S_IN + 0.02), ("band", S_BAND[1])):
    p = HEAD + AXIS * s
    ins, dist = inside(bvh, p)
    print("[%s] axis %s (%.3f, %.3f, %.3f): %s the face by %.1f mm" % (SCRIPT, label, p.x, p.y, p.z,
                                                                       "inside" if ins else "outside", dist * 1000))
# Wrapper surface points out past the lips that end up inside the face (should be none past 1 cm out)
buried = 0
for v in pieces[0].data.vertices:
    s = pieces[0].data.attributes["cg"].data[v.index].vector[0]
    if s > S_IN + 0.012 and inside(bvh, v.co)[0]:
        buried += 1
print("[%s] %d surface points more than 1.2 cm out of the lips are inside the face" % (SCRIPT, buried))
tip = HEAD + AXIS * L
print("[%s] axis %.0f deg down, %.0f deg out; tip at (%.3f, %.3f, %.3f)" % (SCRIPT, math.degrees(PITCH),
                                                                         math.degrees(YAW), tip.x, tip.y, tip.z))

hidden = [o for o in bpy.context.scene.objects if o.get("zbody")]
for o in hidden:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS, size=512)
for o in hidden:
    o.hide_render = False
# The previews show the face proxy in place of the head and chest capsules
for i, c in enumerate(SK.colliders):
    if c["bone"] in ("Head", "Spine2"):
        BODY[i].hide_render = True
focus = Vector((-0.03, -0.09, 1.66))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.55)


def close_up(view, direction, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


mid = HEAD + AXIS * 0.06
close_up("close", (-0.5, -1.0, 0.15), mid, 0.2)
close_up("tip", AXIS * 1.0 + Vector((0.2, -0.1, 0.5)), HEAD + AXIS * 0.085, 0.12)
print("[%s] done" % SCRIPT)
