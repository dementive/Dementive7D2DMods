"""Bow tie (remnant): a dark red satin bow tie still at the throat, knocked crooked. A pre-tied butterfly bow, its two
wings flaring from the pinched knot to puffy lobes with a notch at each end and a fold down the middle, the knot
standing proud in front; the thin neck band running round the neck under the collar. Burgundy satin gone dull with
grime, rubbed shiny in places, frayed at the edges, a dark blood stain soaked into one wing, dust in the folds.

It sits on the front of Joe's neck (the 5.5 cm neck column the other neck pieces assume) just above the collar, the
band half a centimeter off the neck, turned 14 degrees so the left wing rides up and twisted a little on the neck.
Its top stays below the chin with the jaw opened for an attack. One part on the Neck bone: "Neck#BowTie".

    blender -b --factory-startup --python bow_tie.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT = "BowTie", "bow_tie"
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
RND = random.Random(2412)
EYES = (Vector((0.032, -0.075, 1.719)), Vector((-0.032, -0.075, 1.719)))
JAW_PIVOT = SK.pos("Jaw")
UP = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------- helpers

def set_attr(obj, name, vals):
    me = obj.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def sp(x, e):
    return math.copysign(abs(x) ** e, x)


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


def preview_head():
    """Joe's real head, jaw and neck for the previews (as sunglasses.py's face proxy, simplified). Not exported."""
    mat, g = tk.new_material("ProxySkin")
    tk.finish(mat, g, (0.46, 0.38, 0.34), 0.0, 0.65)
    parts = [
        blob("Cranium", (0.0, 0.02, 1.737), (0.076, 0.1, 0.107), mat, (2.8, 2.6)),
        blob("Brow", (0.0, -0.062, 1.745), (0.052, 0.024, 0.011), mat, (2.4, 2.0)),
        blob("Midface", (0.0, -0.03, 1.674), (0.062, 0.064, 0.06), mat, (2.4, 2.0)),
        blob("Lips", (0.0, -0.083, 1.646), (0.025, 0.017, 0.013), mat),
        blob("Nose", (0.0, -0.1, 1.69), (0.013, 0.02, 0.026), mat),
    ]
    for s in (1.0, -1.0):
        parts.append(blob("Cheek", (s * 0.047, -0.056, 1.699), (0.02, 0.022, 0.015), mat))
        parts.append(blob("Ear", (s * 0.076, 0.03, 1.70), (0.011, 0.02, 0.03), mat, rot_x=-10.0))
    head = tk.join(parts, "PreHead")
    jaw = tk.join([blob("Jaw", (0.0, -0.02, 1.628), (0.053, 0.066, 0.045), mat, (2.4, 2.0)),
                   blob("Chin", (0.0, -0.077, 1.611), (0.022, 0.017, 0.017), mat)], "PreJaw")
    neck = tk.cylinder("PreNeck", 0.055, 1.44, 1.69, mat, segments=40, center=(0.0, 0.032))
    for o in (head, jaw, neck):
        tk.smooth(o, 60)
        o["zbody"] = True
    return head, jaw, neck


# ---------------------------------------------------------------- where it sits

NECK_AXIS, NECK_R = Vector((0.0, 0.032, 0.0)), 0.055
BAND_OFF = 0.005  # the band's inside off the neck
CENTER = Vector((0.004, NECK_AXIS.y - NECK_R - BAND_OFF - 0.0125, 1.521))  # the knot's middle
ROLL = math.radians(14.0)  # crooked: the zombie's left wing up
YAW = math.radians(-7.0)  # and turned a little on the neck
FRAME = Matrix.Rotation(YAW, 3, "Z") @ Matrix.Rotation(-ROLL, 3, "Y")  # bow-local (x along, y out(-), z up) to world


def to_world(p):
    return CENTER + FRAME @ Vector(p)


# ---------------------------------------------------------------- the bow

def ring_pts(hh, hd, notch=0.0, crease=0.0, n=14):
    """A wing's cross-section (y depth, z height) round from the front: a rounded oblong, its front face pressed in
    along the middle fold (crease)."""
    pts = []
    for j in range(n):
        a = 2 * math.pi * j / n
        y = -sp(math.cos(a), 0.55) * hd
        z = sp(math.sin(a), 0.7) * hh
        if y < 0:  # the front: the fold along the middle
            y += crease * hd * math.exp(-(z / (0.35 * hh)) ** 2) * (-y / hd)
        pts.append((y, z))
    return pts


def wing(bm, vals, side, wid):
    """One wing from the knot out to its notched end: loft of cross-sections. vals: (u along 0-1, v round, wing)."""
    rows = []
    nsec = 9
    for i in range(nsec):
        u = i / (nsec - 1)
        x = side * (0.0095 + 0.046 * u)
        hh = 0.0105 + 0.0175 * math.sin(min(1.0, u * 1.15) * math.pi / 2) ** 1.3
        hd = 0.0042 + 0.0035 * math.sin(math.pi * min(u, 0.9) / 0.9) ** 0.7
        crease = 0.5 * u
        pts = ring_pts(hh, hd, crease=crease)
        row = []
        for j, (y, z) in enumerate(pts):
            # cloth: soft wrinkles, and the lobes swept slightly back at the outer end
            w = 0.0012 * noise.noise(Vector((x * 60.0, y * 60.0 + side, z * 60.0))) + 0.0007 * noise.noise(Vector((x * 300.0, z * 300.0, side)))
            yy = y + w + 0.004 * u * u + 0.002 * abs(z) / 0.028 * u
            zz = z * (1.0 - 0.06 * u) + 0.0015 * u * side
            row.append(bm.verts.new(to_world((x, yy, zz))))
            vals.append((u, j / len(pts), side))
        rows.append(row)
    n = len(rows[0])
    for a, b in zip(rows, rows[1:]):
        for j in range(n):
            j1 = (j + 1) % n
            bm.faces.new((a[j], a[j1], b[j1], b[j]) if side > 0 else (a[j1], a[j], b[j], b[j1]))
    # The outer end: a notch pulled in at the middle (the butterfly's waist)
    xe = side * (0.0095 + 0.046 + 0.0)
    tip = bm.verts.new(to_world((xe - side * 0.007, 0.0015, 0.0)))
    vals.append((1.0, 0.5, side))
    last = rows[-1]
    for j in range(n):
        j1 = (j + 1) % n
        bm.faces.new((last[j], last[j1], tip) if side > 0 else (last[j1], last[j], tip))
    first = rows[0]
    root = bm.verts.new(to_world((side * 0.006, 0.0, 0.0)))
    vals.append((0.0, 0.5, side))
    for j in range(n):
        j1 = (j + 1) % n
        bm.faces.new((first[j1], first[j], root) if side > 0 else (first[j], first[j1], root))


def knot(bm, vals):
    """The knot: a pinched, rounded band of the same satin wrapped round the middle, standing proud of the wings."""
    rows = []
    for i, x in enumerate((-0.0125, -0.008, 0.0, 0.008, 0.0125)):
        k = 1.0 - (abs(x) / 0.0125) ** 4 * 0.25
        pts = ring_pts(0.0125 * k, 0.0078 * k, crease=0.0)
        row = []
        for j, (y, z) in enumerate(pts):
            yy = y - 0.0012 * (1.0 - (x / 0.0125) ** 2)
            row.append(bm.verts.new(to_world((x, yy, z * (1.0 - 0.08 * math.cos(x * 250))))))
            vals.append((0.0, j / len(pts), 2.0))
        rows.append(row)
    n = len(rows[0])
    for a, b in zip(rows, rows[1:]):
        for j in range(n):
            j1 = (j + 1) % n
            bm.faces.new((a[j1], a[j], b[j], b[j1]))


def band(bm, vals):
    """The neck band: a 1.2 cm strap from behind the knot round the neck, rising a little at the nape."""
    pts = []
    n = 40
    h, t = 0.012, 0.0014
    rho = NECK_R + BAND_OFF + t / 2
    rows = []
    for i in range(n):
        psi = 2 * math.pi * i / n  # 0 at the front, + toward the zombie's left
        d = Vector((math.sin(psi), -math.cos(psi), 0.0))
        zc = CENTER.z + 0.012 * (1.0 - math.cos(psi)) / 2 + 0.003 * math.sin(psi)
        base = NECK_AXIS + d * (rho + 0.0045 * max(0.0, math.cos(psi)) ** 6)  # out to the knot at the front
        c = Vector((base.x, base.y, zc))
        row = []
        for (dr, dz) in ((-t / 2, -h / 2), (t / 2, -h / 2), (t / 2, h / 2), (-t / 2, h / 2)):
            row.append(bm.verts.new(c + d * dr + UP * dz))
            vals.append((psi / (2 * math.pi), 0.0, 3.0))
        rows.append(row)
    for i in range(n):
        a, b = rows[i], rows[(i + 1) % n]
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))


# ---------------------------------------------------------------- material

def attr(g, name):
    n = g.node("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name)
    return tk._sock(n.outputs, "Vector")


def mapping(g, vec, scale=(1.0, 1.0, 1.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def mul(g, a, b):
    return g.math("MULTIPLY", a, b)


def add(g, a, b):
    return g.math("ADD", a, b)


def satin():
    """Burgundy satin: a faint woven pattern of tiny diamonds, a sheen that's rubbed shiny on the high spots and
    dulled with grime in the folds, frayed lighter edges, dust, and a dark blood stain soaked into one wing."""
    mat, g = tk.new_material("Satin")
    u, v, which = g.separate(attr(g, "bw"))
    W = g.coords()
    P = mapping(g, W, loc=(0.4, 2.2, 1.3))
    base = g.mix(g.ramp(g.noise(80.0, detail=4.0, vector=P), 0.3, 0.7), (0.03, 0.0045, 0.005), (0.052, 0.0075, 0.008))
    # Woven diamonds (tiny), printed slightly darker
    d1 = g.math("SINE", mul(g, add(g, g.separate(W)[0], g.separate(W)[2]), 900.0))
    d2 = g.math("SINE", mul(g, g.math("SUBTRACT", g.separate(W)[0], g.separate(W)[2]), 900.0))
    dia = g.ramp(mul(g, d1, d2), 0.5, 0.8)
    col = g.mix(mul(g, dia, 0.35), base, (0.025, 0.004, 0.005))
    rough = add(g, 0.36, mul(g, dia, 0.08))
    # Cavity grime in the folds and where the wings meet the knot
    cav = g.math("SUBTRACT", 1.0, g.ramp(g.cavity(0.012), 0.35, 1.0), clamp=True)
    grime = g.math("MAXIMUM", mul(g, cav, 0.9), mul(g, g.ramp(g.noise(12.0, detail=6.0, vector=P), 0.55, 0.75), 0.6))
    col = g.mix(grime, col, (0.02, 0.012, 0.01))
    rough = g.mixf(grime, rough, 0.8)
    # The band is in shadow under the collar: darker, dirtier
    on_band = g.ramp(which, 2.5, 2.9)
    col = g.mix(mul(g, on_band, 0.6), col, (0.025, 0.008, 0.007))
    rough = g.mixf(on_band, rough, 0.7)
    # Frayed edges at the wing ends
    fray = mul(g, g.ramp(u, 0.85, 1.0), g.ramp(g.noise(250.0, detail=3.0, vector=P), 0.45, 0.65))
    col = g.mix(mul(g, fray, 0.6), col, (0.13, 0.05, 0.045))
    # Blood soaked into the zombie's right wing, tide-marked
    st = g.noise(30.0, detail=6.0, roughness=0.65, distortion=0.6, vector=P)
    right = g.ramp(which, -0.5, -0.9)
    stain = mul(g, mul(g, g.ramp(st, 0.5, 0.56), g.ramp(u, 0.15, 0.4)), right)
    col = g.mix(stain, col, (0.022, 0.003, 0.003))
    rough = g.mixf(stain, rough, 0.55)
    tide = mul(g, mul(g, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", st, 0.5)), 0.012, 0.0), g.ramp(u, 0.15, 0.4)), right)
    col = g.mix(mul(g, tide, 0.7), col, (0.012, 0.002, 0.002))
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.3)
    height = add(g, mul(g, dia, 0.25), mul(g, g.noise(200.0, detail=4.0, vector=P), 0.35))
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.001))


SATIN = satin()

bm = bmesh.new()
vals = []
wing(bm, vals, 1.0, 0)
wing(bm, vals, -1.0, 1)
knot(bm, vals)
band(bm, vals)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bow = tk.mesh_object("BowTie", bm, SATIN)
set_attr(bow, "bw", vals)
tk.smooth(bow, 60)
pieces = [bow]
zk.on(bow, "Neck", "BowTie")

# ---------------------------------------------------------------- checks

HEAD, JAW, NECK = preview_head()


def jaw_clearance():
    """The nearest the bow comes to Joe's chin and jaw with the jaw opened 18 degrees."""
    rot = Matrix.Translation(JAW_PIVOT) @ Matrix.Rotation(math.radians(18.0), 4, "X") @ Matrix.Translation(-JAW_PIVOT)
    jaw_pts = [rot @ v.co for v in JAW.data.vertices if v.co.y < 0.02]
    bow_pts = [v.co for v in bow.data.vertices if v.co.z > 1.49]
    best = min(((a - b).length, b) for a in jaw_pts for b in bow_pts)
    closed = min((a.co - b.co).length for a in JAW.data.vertices for b in bow.data.vertices if b.co.z > 1.49)
    print("[%s] chin and jaw: %.1f cm clear closed, %.1f cm opened 18 deg (nearest at %.3f, %.3f, %.3f)"
          % (SCRIPT, closed * 100, best[0] * 100, *best[1]))


def neck_gap():
    gaps = [math.hypot(v.co.x - NECK_AXIS.x, v.co.y - NECK_AXIS.y) - NECK_R for v in bow.data.vertices]
    print("[%s] nearest to the neck column: %.1f mm; top z %.3f, bottom z %.3f; width %.1f cm" % (
        SCRIPT, min(gaps) * 1000, max(v.co.z for v in bow.data.vertices), min(v.co.z for v in bow.data.vertices),
        (max(v.co.x for v in bow.data.vertices if v.co.y < -0.02) - min(v.co.x for v in bow.data.vertices if v.co.y < -0.02)) * 100))


jaw_clearance()
neck_gap()
print("[%s] %d triangles before export" % (SCRIPT, sum(len(p.vertices) - 2 for p in bow.data.polygons)))
if os.environ.get("ZED_DRY"):
    sys.exit(0)

hidden = [o for o in bpy.context.scene.objects if o.get("zbody")]
for o in hidden:
    o.hide_render = True
parts = zk.export(NAME, pieces, ASSETS, size=512)
for o in hidden:
    o.hide_render = False
# The previews show Joe's real head and neck, and a chest set back where his collarbones really are (the chest hit
# box bulges up round the base of the neck)
for i, c in enumerate(SK.colliders):
    if c["bone"] in ("Head", "Spine2"):
        BODY[i].hide_render = True
blob("PreChest", (0.0, 0.055, 1.33), (0.16, 0.105, 0.17), bpy.data.materials["ProxySkin"], (2.3, 2.6))
focus = Vector((0.0, -0.04, 1.53))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.5)


def close_up(view, direction, target, distance=0.3, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


close_up("close", (0.3, -1.0, 0.15), CENTER, 0.2)
# The jaw opened for an attack
rot = Matrix.Translation(JAW_PIVOT) @ Matrix.Rotation(math.radians(18.0), 4, "X") @ Matrix.Translation(-JAW_PIVOT)
JAW.matrix_world = rot @ JAW.matrix_world
close_up("jaw_open", (1.0, -0.4, 0.1), Vector((0.0, -0.04, 1.56)), 0.3)
print("[%s] done" % SCRIPT)
