"""Icicles: the Frostbitten mutation (snow biome). Ice has crusted onto the zombie wherever it drips: a lumpy collar of
rime along the underside of the jaw and chin, crusts along the bottoms of both forearms, and a frozen band along the
lower edge of the clothes at the waist, with short icicles hanging straight down from all of them (in the bind pose).
Pale blue-white, glossy where it's solid ice, white and rough where it's frost; bright along the ridges and at the
tips. The game shader is opaque, so the ice is suggested by color, gloss and those bright rims, not transparency.

Parts: "Jaw#Ice", "LeftForeArm#Ice", "RightForeArm#Ice", "Hips#Ice".

    blender -b --factory-startup --python icicles.py -- <unity models folder> <preview folder>
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
ASSETS, PREVIEWS = os.path.join(args[0], "Icicles"), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

rnd = random.Random(9091)


def jit(a):
    return rnd.uniform(-a, a)


tk.reset_scene()
zk.stage()
zk.body()
sk = zk.joe()

DOWN = Vector((0.0, 0.0, -1.0))
# Joe's forearm as this assumes it: round, 4 cm in radius at the elbow, 3.1 cm at the wrist
FOREARM_R = (0.04, 0.031)
# The lower edge of the clothes around the waist: an ellipse (half-widths across and front to back) at this height
HEM_Z = 0.985
HEM_C = Vector((0.0, 0.013, HEM_Z))
HEM_R = (0.168, 0.16)
# The lower border of the jaw, from the left angle of the jaw round the chin (mirrored for the right)
JAW_LINE = [Vector(p) for p in ((0.057, 0.01, 1.628), (0.052, -0.012, 1.617), (0.043, -0.036, 1.607),
                                (0.028, -0.058, 1.6), (0.0, -0.07, 1.597))]
JAW_CENTER = Vector((0.0, -0.015, 1.65))


# ---------------------------------------------------------------- helpers

def orth(v, axis):
    return (v - axis * v.dot(axis)).normalized()


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


def sheet(name, rows, attrs, mat, outward, closed=False, smooth=80):
    """A sheet through rows of points (each row the same length; closed joins each row's ends), its faces turned
    to face `outward(p)`."""
    bm = bmesh.new()
    vals = []
    vr = []
    for row, at in zip(rows, attrs):
        vr.append([bm.verts.new(p) for p in row])
        vals += at
    for A, B in zip(vr, vr[1:]):
        n = len(A)
        for j in range(n if closed else n - 1):
            k = (j + 1) % n
            bm.faces.new((A[j], A[k], B[k], B[j]))
    bm.normal_update()
    for f in bm.faces:
        if f.normal.dot(outward(f.calc_center_median())) < 0:
            f.normal_flip()
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, vals)
    return tk.smooth(obj, smooth)


def smooth_path(ctrl, per=5):
    """Catmull-Rom through the control points."""
    pts = [Vector(p) for p in ctrl]
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def icicle(name, root, length, r0, seed, mat, m=6):
    """An icicle hanging straight down from `root` (its top buried in the crust): tapering, rippled, slightly
    wavering, with a fine point."""
    fs = (0.0, 0.2, 0.42, 0.64, 0.84)
    lean = Vector((jit(1.0), jit(1.0), 0.0)) * (0.06 * length)
    rings, attrs = [], []
    for f in fs:
        r = r0 * (1.0 - f) ** 0.9 * (1.0 + 0.15 * math.sin(f * 11.0 + seed * 3.0) + jit(0.06))
        c = root + DOWN * (length * f) + lean * (f * f) + Vector((jit(0.0005), jit(0.0005), 0.0))
        ring = []
        for q in range(m):
            ang = 2 * math.pi * q / m + seed
            k = 1.0 + 0.12 * noise.noise(Vector((math.cos(ang), math.sin(ang), f * 3.0 + seed)))
            ring.append(c + Vector((math.cos(ang) * r * k, math.sin(ang) * r * k, 0.0)))
        rings.append(ring)
        attrs.append([(q / m, f, seed) for q in range(m)])
    tip = root + DOWN * length + lean
    return loft(name, rings, attrs, mat, start=(root - DOWN * r0 * 0.6, (0.5, 0.0, seed)), end=(tip, (0.5, 1.0, seed)),
                smooth=75)


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


def pointy(g, lo, hi):
    """1 along convex ridges and tips (Cycles' pointiness, which bakes)."""
    geo = g.node("ShaderNodeNewGeometry")
    return g.ramp(tk._sock(geo.outputs, "Pointiness"), lo, hi)


def icicle_material(name):
    """Solid icicle ice: pale blue-white, glassy-smooth and glossy, streaked along its length with white air
    bubbles, a deeper blue through its middle, frosted white at the root, bright on its ridges and at the tip."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    streak = g.noise(1.0, detail=3.0, vector=wrap(g, a, t, seed, 3.2, 0.9))
    col = g.mix(g.ramp(streak, 0.3, 0.72), (0.46, 0.62, 0.78), (0.66, 0.78, 0.89))
    core = g.math("MULTIPLY", g.ramp(t, 0.12, 0.45), g.ramp(t, 0.95, 0.75))
    col = g.mix(g.math("MULTIPLY", core, 0.55), col, (0.32, 0.49, 0.69))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 1.0)
    g.links.new(wrap(g, a, t, seed, 9.0, 4.0), vor.inputs["Vector"])
    bubbles = g.math("MULTIPLY", g.ramp(tk._sock(vor.outputs, "Distance"), 0.14, 0.05), g.ramp(streak, 0.45, 0.6))
    col = g.mix(g.math("MULTIPLY", bubbles, 0.8), col, (0.9, 0.93, 0.96))
    frost = g.math("MAXIMUM", g.ramp(t, 0.16, 0.02),
                   g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=5.0, vector=wrap(g, a, t, seed, 2.0, 3.0)),
                                             0.66, 0.76), g.ramp(t, 0.5, 0.2)))
    col = g.mix(frost, col, (0.86, 0.9, 0.94))
    rim = g.math("MAXIMUM", pointy(g, 0.52, 0.62), g.math("MULTIPLY", g.ramp(t, 0.82, 1.0), 0.7))
    col = g.mix(g.math("MULTIPLY", rim, 0.5), col, (0.9, 0.95, 1.0))
    rough = g.math("ADD", 0.04, g.math("MULTIPLY", streak, 0.05))
    rough = g.mixf(frost, rough, 0.55)
    ripple = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, 60.0), g.math("MULTIPLY", streak, 4.0)))
    height = g.math("ADD", g.math("MULTIPLY", ripple, 0.07), g.math("MULTIPLY", streak, 0.2))
    height = g.math("ADD", height, g.math("MULTIPLY", frost, g.noise(400.0, detail=3.0)))
    # Toned down to sit beside the game's dark, dirty zombies: pure white ice reads as a flat white shape in game
    col = tk.grade(g, col, sat=1.2, value=0.66)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.2, 0.0008))


def rime_material(name, blood=0.0):
    """A crust of ice frozen onto the body: clear grey-blue ice under a white, crystalline frost that is thicker on
    top and along the ridges; thin and greyed (the dirty skin or cloth under it) where it thins out at its edges
    (t low); a few specks of grime frozen in, and pinkish frozen drool and blood with `blood`."""
    mat, g = tk.new_material(name)
    a, t, seed = gr(g)
    body = g.noise(35.0, detail=5.0, distortion=0.3)
    col = g.mix(g.ramp(body, 0.3, 0.7), (0.42, 0.55, 0.68), (0.6, 0.71, 0.82))
    geo = g.node("ShaderNodeNewGeometry")
    up = g.separate(tk._sock(geo.outputs, "Normal"))[2]
    blot = g.noise(55.0, detail=6.0, roughness=0.62, distortion=0.4)
    field = g.math("ADD", blot, g.math("MULTIPLY", g.ramp(up, -0.4, 0.9), 0.2))
    frost = g.math("MAXIMUM", g.ramp(field, 0.55, 0.64), g.math("MULTIPLY", pointy(g, 0.52, 0.6), 0.7))
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 700.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    crystal = tk._luma(g, tk._sock(vor.outputs, "Color"))
    glint = g.ramp(crystal, 0.62, 0.8)
    fc = g.mix(crystal, (0.74, 0.79, 0.85), (0.9, 0.93, 0.96))
    col = g.mix(frost, col, fc)
    thin = g.ramp(t, 0.35, 0.05)
    col = g.mix(g.math("MULTIPLY", thin, 0.6), col, (0.42, 0.43, 0.45))
    if blood:
        stain = g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=5.0, distortion=0.5), 0.55, 0.68), blood)
        col = g.mix(stain, col, (0.55, 0.28, 0.3))
    v2 = g.node("ShaderNodeTexVoronoi")
    g._in(v2, "Scale", 220.0)
    g.links.new(g.coords(), v2.inputs["Vector"])
    specks = g.math("MULTIPLY", g.ramp(tk._sock(v2.outputs, "Distance"), 0.12, 0.05), g.ramp(body, 0.55, 0.65))
    col = g.mix(g.math("MULTIPLY", specks, 0.7), col, (0.12, 0.1, 0.09))
    rough = g.mixf(frost, g.math("ADD", 0.08, g.math("MULTIPLY", body, 0.08)), g.mixf(glint, 0.62, 0.35))
    rough = g.mixf(thin, rough, 0.5)
    height = g.math("ADD", g.math("MULTIPLY", body, 0.4), g.math("MULTIPLY", frost, g.math("ADD", 0.4, crystal)))
    col = tk.grade(g, col, sat=1.15, value=0.6)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.45, 0.002))


ice = icicle_material("Icicle")
rime = rime_material("Rime")
rime_jaw = rime_material("RimeJaw", blood=0.55)


# ---------------------------------------------------------------- the jaw

def lobes(x, drops, width):
    """Drip lobes: how much the crust swells where each icicle hangs from it (x and the drops' positions in the same
    units)."""
    return sum(math.exp(-((x - d) / width) ** 2) * min(1.0, 0.4 + length / 0.04) for d, length in drops)


JAW_DROPS = ((0.5, 0.036), (0.44, 0.024), (0.565, 0.03), (0.36, 0.018), (0.63, 0.02), (0.29, 0.012), (0.7, 0.013))


def jaw_ice():
    """A lumpy collar of rime along the underside of the jaw, thickest under the chin and swollen into drips where
    the icicles hang from the chin and the front of the jaw."""
    ctrl = [Vector((p.x, p.y, p.z)) for p in JAW_LINE] + [Vector((-p.x, p.y, p.z)) for p in reversed(JAW_LINE[:-1])]
    path = smooth_path(ctrl, per=3)
    m = 7
    rings, attrs = [], []
    n = len(path)
    for i, p in enumerate(path):
        f = i / (n - 1)
        tang = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        nrm = orth(p - JAW_CENTER, tang)
        side = tang.cross(nrm)
        chin = math.exp(-((f - 0.5) / 0.22) ** 2)
        end = min(1.0, f / 0.1, (1.0 - f) / 0.1)
        drip = lobes(f, JAW_DROPS, 0.03)
        rn = (0.0035 + 0.004 * chin + 0.0016 * drip) * (0.35 + 0.65 * end)
        rn *= 1.0 + 0.35 * noise.noise(Vector((f * 14.0, 0.3, 0.0)))
        rb = rn * 1.45
        c = p - nrm * (0.0022 + 0.002 * (1.0 - end))
        ring = []
        for q in range(m):
            ang = 2 * math.pi * q / m
            k = 1.0 + 0.3 * noise.noise(Vector((math.cos(ang) * 1.7, math.sin(ang) * 1.7, f * 18.0)))
            # drips hang down off the crust
            sag = max(0.0, -(nrm * math.cos(ang) + side * math.sin(ang)).z) * drip * 0.0018
            ring.append(c + nrm * (math.cos(ang) * rn * k) + side * (math.sin(ang) * rb * k) + DOWN * sag)
        rings.append(ring)
        attrs.append([(q / m, min(1.0, 0.2 + 0.8 * end * (0.5 + 0.5 * math.cos(2 * math.pi * q / m))), 0.4)
                      for q in range(m)])
    ends = [path[k] - (path[k] - JAW_CENTER).normalized() * 0.003 for k in (0, -1)]
    out = [loft("JawCrust", rings, attrs, rime_jaw, start=(ends[0], (0.5, 0.0, 0.4)), end=(ends[1], (0.5, 0.0, 0.4)),
                smooth=70)]
    # Icicles hanging from the drips, their tops buried in the crust
    for k, (f, length) in enumerate(JAW_DROPS):
        ring = rings[int(round(f * (n - 1)))]
        low = min(ring, key=lambda q: q.z)
        root = low + Vector((jit(0.001), jit(0.001), 0.003))
        out.append(icicle("JawIcicle%d" % k, root, length * rnd.uniform(0.85, 1.15), 0.004 + 0.0014 * (length / 0.036),
                          0.2 + k * 0.37, ice))
    return out


# ---------------------------------------------------------------- the forearms

ARM_DROPS = ((0.28, 0.02), (0.36, 0.012), (0.43, 0.042), (0.5, 0.026), (0.58, 0.055), (0.64, 0.016),
             (0.71, 0.036), (0.8, 0.022))


def forearm_ice(side, seed0):
    """A crust of ice along the bottom of the forearm (the side that faces down, toward the body, in the A-pose),
    thick along the bottom and thinning to nothing up its sides in a ragged edge, swollen into drips where icicles
    hang straight down from it."""
    a0, a1 = sk.pos(side + "ForeArm"), sk.pos(side + "Hand")
    axis = (a1 - a0).normalized()
    bottom = orth(DOWN, axis)
    across = axis.cross(bottom)
    t0, t1 = 0.16, 0.9
    nt, na = 15, 9
    drops = [(tt + jit(0.015), length * rnd.uniform(0.85, 1.15)) for tt, length in ARM_DROPS]
    rows, attrs = [], []
    for i in range(nt):
        f = i / (nt - 1)
        tt = t0 + (t1 - t0) * f
        rf = FOREARM_R[0] + (FOREARM_R[1] - FOREARM_R[0]) * tt
        c = a0.lerp(a1, tt)
        drip = lobes(tt, drops, 0.025)
        row, at = [], []
        for j in range(na):
            gg = -1.0 + 2.0 * j / (na - 1)
            ang = math.radians(80.0) * gg
            radial = bottom * math.cos(ang) + across * math.sin(ang)
            rag = 0.3 * noise.noise(Vector((tt * 14.0, gg, seed0 * 2.0)))
            edge = max(0.0, min(1.0, (1.0 - abs(gg) + rag) / 0.45, f / 0.18, (1.0 - f) / 0.14))
            lump = 0.0022 * noise.noise(Vector((tt * 34.0, gg * 2.4, seed0)))
            h = -0.0022 + edge ** 0.8 * (0.0052 + 0.0026 * math.sin(math.pi * f) + lump
                                         + 0.0035 * drip * max(0.0, 1.0 - abs(gg) * 2.2))
            row.append(c + radial * (rf + h))
            at.append((j / (na - 1), edge, seed0))
        rows.append(row)
        attrs.append(at)

    def outward(p):
        rel = p - a0
        return rel - axis * rel.dot(axis)

    out = [sheet("ArmCrust%s" % side, rows, attrs, rime, outward)]
    for k, (tt, length) in enumerate(drops):
        rf = FOREARM_R[0] + (FOREARM_R[1] - FOREARM_R[0]) * tt
        root = a0.lerp(a1, tt) + bottom * (rf + 0.0045) + across * jit(0.003)
        out.append(icicle("ArmIcicle%s%d" % (side, k), root, length, 0.0036 + 0.0018 * (length / 0.05),
                          seed0 + k * 0.29, ice))
    return out


# ---------------------------------------------------------------- the waist

def hem_point(phi, lift, dz):
    """A point on the hem ellipse at angle phi (0 = +X, -90 degrees = the front), pushed out by `lift`."""
    c, s = math.cos(phi), math.sin(phi)
    # the outward normal of the ellipse there
    nrm = Vector((c / HEM_R[0], s / HEM_R[1], 0.0)).normalized()
    return HEM_C + Vector((c * HEM_R[0], s * HEM_R[1], dz)) + nrm * lift, nrm


# Icicles round the hem in clusters: (angle in degrees, length); -90 is the front, 90 the back, 0 and 180 the
# sides, where the hips are right below and they stay short
HEM_DROPS = ((-93, 0.072), (-99, 0.03), (-86, 0.045), (-107, 0.052), (-79, 0.022), (-118, 0.03), (-64, 0.04),
             (-58, 0.018), (-131, 0.02), (-142, 0.012), (-45, 0.022), (-30, 0.01), (88, 0.06), (95, 0.026),
             (80, 0.034), (106, 0.045), (118, 0.02), (66, 0.03), (58, 0.014), (132, 0.016), (15, 0.011), (168, 0.012),
             (200, 0.01))


def hem_ice():
    """A frozen band along the lower edge of the clothes all round the waist: lumpy, uneven in thickness and height,
    swollen into drips where the icicles hang from it."""
    n = 72
    profile = ((0.013, -0.0022, 0.0), (0.007, 0.006, 0.55), (0.0, 0.0098, 1.0), (-0.006, 0.0072, 0.8),
               (-0.0095, -0.0012, 0.2))
    drops = [(math.radians(d + jit(2.5)), length * rnd.uniform(0.85, 1.15)) for d, length in HEM_DROPS]
    rows, attrs = [], []
    for r, (dz, h, t) in enumerate(profile):
        row, at = [], []
        for i in range(n):
            phi = 2 * math.pi * i / n
            drip = 0.0
            for d, length in drops:
                dd = math.atan2(math.sin(phi - d), math.cos(phi - d))
                drip += math.exp(-(dd / 0.07) ** 2) * min(1.0, 0.4 + length / 0.05)
            lump = noise.noise(Vector((math.cos(phi) * 3.0, math.sin(phi) * 3.0, 0.7)))
            thick = 0.7 + 0.45 * lump + 0.25 * noise.noise(Vector((math.cos(phi) * 9.0, math.sin(phi) * 9.0, 2.1)))
            hh = h * max(0.2, thick) if h > 0 else h
            if r in (2, 3):
                hh += (0.0042 if r == 3 else 0.0025) * min(1.3, drip)
            dzz = dz + 0.006 * noise.noise(Vector((math.cos(phi) * 5.0, math.sin(phi) * 5.0, 4.4)))
            if r >= 3:
                dzz -= 0.006 * drip
            p, _ = hem_point(phi, hh, dzz)
            row.append(p)
            at.append((i / n, t * min(1.0, max(0.3, thick)), 0.9))
        rows.append(row)
        attrs.append(at)

    def outward(p):
        rel = p - HEM_C
        rel.z = 0.0
        return rel

    out = [sheet("HemCrust", rows, attrs, rime, outward, closed=True)]
    for k, (phi, length) in enumerate(drops):
        drip = sum(math.exp(-(math.atan2(math.sin(phi - d), math.cos(phi - d)) / 0.07) ** 2) * min(1.0, 0.4 + ln / 0.05)
                   for d, ln in drops)
        # its top buried in the drip it hangs from
        p, nrm = hem_point(phi, 0.0052 + 0.001 * drip, -0.0025 - 0.0045 * drip)
        out.append(icicle("HemIcicle%d" % k, p, length + 0.004, 0.0036 + 0.0024 * (length / 0.07),
                          0.5 + k * 0.23, ice))
    return out


pieces = []
for o in jaw_ice():
    pieces.append(zk.on(o, "Jaw", "Ice"))
for side, seed0 in (("Left", 1.1), ("Right", 2.7)):
    for o in forearm_ice(side, seed0):
        pieces.append(zk.on(o, side + "ForeArm", "Ice"))
for o in hem_ice():
    pieces.append(zk.on(o, "Hips", "Ice"))


# ---------------------------------------------------------------- better stand-in parts (previews only)

def ellipsoid(name, center, radii, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1.0)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    return tk.smooth(tk.mesh_object(name, bm, mat), 60)


def taper(name, a, b, ra, rb, mat, seg=20):
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


def standin():
    """The stand-in's head capsule covers the whole neck and jaw and its forearm capsules are fat (5 cm), so for
    these previews they're swapped for a skull, jaw, chin and neck and for slimmer forearms."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] in ("Head", "LeftForeArm", "RightForeArm", "Spine2"):
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
        if c["bone"] == "Spine2":
            ax = [0.0, 0.0, 0.0]
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            zk._capsule("PreChest", sk.point("Spine2", ctr - Vector(ax) * half),
                        sk.point("Spine2", ctr + Vector(ax) * half) - Vector((0.0, 0.0, 0.05)), c["radius"], mat)
    ellipsoid("PreSkull", (0.0, 0.03, 1.738), (0.079, 0.1, 0.104), mat)
    ellipsoid("PreJaw", (0.0, -0.022, 1.652), (0.062, 0.066, 0.055), mat)
    ellipsoid("PreChin", (0.0, -0.062, 1.614), (0.024, 0.02, 0.02), mat)
    tk.cylinder("PreNeck", 0.055, 1.5, 1.69, mat, segments=32, center=(0.0, 0.032))
    for side in ("Left", "Right"):
        taper("Pre%sForeArm" % side, sk.pos(side + "ForeArm"), sk.pos(side + "Hand"), FOREARM_R[0], FOREARM_R[1], mat)


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


report("icicles", pieces)
standin()
parts = zk.export("Icicles", pieces, ASSETS)
zk.previews("icicles", PREVIEWS, Vector((0.0, -0.02, 1.25)), distance=2.3)


def closeup(name, focus, direction, dist=0.42, lens=50):
    cam = tk.camera(name, focus + Vector(direction).normalized() * dist, focus, lens=lens)
    tk.render(cam, os.path.join(PREVIEWS, "%s.png" % name), res=(900, 900), samples=64)


closeup("icicles_jaw_front", Vector((0.0, -0.04, 1.6)), (0.25, -1.0, -0.15), dist=0.3)
closeup("icicles_jaw_side", Vector((0.0, -0.03, 1.6)), (1.0, -0.35, -0.1), dist=0.3)
closeup("icicles_forearm", sk.pos("LeftForeArm").lerp(sk.pos("LeftHand"), 0.55) + Vector((0, 0, -0.02)),
        (0.3, -1.0, -0.2), dist=0.45)
closeup("icicles_forearm_under", sk.pos("LeftForeArm").lerp(sk.pos("LeftHand"), 0.55), (-0.5, -0.6, -0.6), dist=0.4)
closeup("icicles_waist_front", Vector((0.0, -0.1, 0.95)), (0.3, -1.0, 0.05), dist=0.75)
closeup("icicles_waist_back", Vector((0.0, 0.1, 0.95)), (-0.4, 1.0, 0.1), dist=0.75)
closeup("icicles_waist_close", Vector((0.05, -0.15, 0.96)), (0.35, -1.0, 0.15), dist=0.3)
print("[icicles] done")
