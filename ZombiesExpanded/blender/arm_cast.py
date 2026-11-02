"""Arm cast: a short plaster cast on the left forearm, from a few centimeters below the elbow (cut lower on the inside
so the elbow can still bend) to the wrist. Grey-beige plaster molded round the forearm, the spiral ridges of the
plaster bandage still showing, a rolled cuff of stockinette at each end. Old and filthy: grime in the ridges, dirt,
tide-marked water stains, dried blood smeared and spattered on it, cracked over the back of the wrist, and covered in
faded marker signatures and doodles ("Get well soon!", names, a heart, a star, a smiley, a skull).

Joe's forearm as this assumes it: a little flatter than round, 4.3 x 4.1 cm in radius below the elbow to 3.1 x 2.3 at
the wrist (the thumb-to-pinky width the larger), around the bone. The cast stands about 1.1 cm off that; the forearm
hit box (5 cm, fatter than the arm) shows through it near the wrist, so the previews use a slimmer stand-in arm.

One part on the forearm bone: "LeftForeArm#Cast".

    blender -b --factory-startup --python arm_cast.py -- <unity models folder> <preview folder>
"""
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zkit as tk  # noqa: E402
import zombiekit as zk  # noqa: E402

NAME, SCRIPT, BONE, PART = "ArmCast", "arm_cast", "LeftForeArm", "Cast"
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


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the forearm

ELBOW, WRIST = sk.pos("LeftForeArm"), sk.pos("LeftHand")
AX = (WRIST - ELBOW).normalized()
LEN = (WRIST - ELBOW).length
FRONT = orth(Vector((0.0, -1.0, 0.0)), AX)  # the thumb side (the hand hangs palm in, thumb forward)
PALM = AX.cross(FRONT)  # down and in, toward the body in the A-pose
DORSAL = -PALM  # the back of the forearm: up and out
# The forearm's half-widths (thumb-pinky a, back-palm b) at fractions along it from the elbow
SKIN = ((0.0, 0.043, 0.041), (0.15, 0.043, 0.041), (0.4, 0.04, 0.036), (0.7, 0.035, 0.029), (0.9, 0.032, 0.024),
        (1.0, 0.031, 0.023))


def skin_ab(t):
    t = max(0.0, min(1.0, t))
    for (t0, a0, b0), (t1, a1, b1) in zip(SKIN, SKIN[1:]):
        if t <= t1:
            f = smoothstep(t0, t1, t) if t1 > t0 else 1.0
            return a0 + (a1 - a0) * f, b0 + (b1 - b0) * f
    return SKIN[-1][1], SKIN[-1][2]


def direction(phi):
    """Around the forearm: phi 0 on the back (dorsal), +90 degrees the thumb side, 180 the palm side."""
    return DORSAL * math.cos(phi) + FRONT * math.sin(phi)


def r_skin(s, phi):
    a, b = skin_ab(s / LEN)
    return 1.0 / math.sqrt((math.cos(phi) / b) ** 2 + (math.sin(phi) / a) ** 2)


def r_cast(s, phi):
    """The plaster's outer surface: the arm plus padding and plaster, rounder than the arm (plaster is wrapped)."""
    a, b = skin_ab(s / LEN)
    mean = (a + b) / 2
    return 0.7 * r_skin(s, phi) + 0.3 * mean + 0.0112


def s_top(phi):
    """The elbow end, cut lower on the inside (palm side) so the elbow can bend."""
    palm = max(0.0, -math.cos(phi))
    return 0.034 + 0.017 * smoothstep(0.0, 1.0, palm)


def s_bottom(phi):
    """The wrist end, a touch longer on the back of the wrist."""
    return LEN - 0.017 + 0.003 * max(0.0, math.cos(phi))


# ---------------------------------------------------------------- the cast mesh

M = 24  # around
BODY_RINGS = 13
SEED = Vector((3.1, 7.7, 1.3))
# The rolled stockinette cuff at an end, from a short sleeve inside it (open, the arm fills it) round the rolled lip
# to the plaster: (distance in from the end, measured off what, radial offset)
CUFF = ((0.016, "skin", -0.0025), (0.0045, "skin", -0.002), (-0.0005, "skin", 0.0045), (-0.002, "skin", 0.0095),
        (0.0012, "out", 0.0034), (0.0068, "out", 0.0028), (0.0105, "out", 0.0))
FABRIC_FACES = 5  # the faces between the first rings are stockinette


def lumps(p, amount):
    """Plaster is smoothed by hand: soft lumps and hollows, a few mm."""
    q = (p - ELBOW) * 30.0 + SEED
    return amount * (0.0022 * noise.noise(q) + 0.0008 * noise.noise(q * 2.7 + SEED))


def end_jitter(phi, end):
    """The ends are trimmed by hand: a few mm uneven."""
    return 0.0028 * noise.noise(Vector((math.cos(phi) * 1.6, math.sin(phi) * 1.6, 4.0 + 3.0 * end)))


PLASTER_PTS = []  # the plaster's outer surface, for the fit report


def cast_mesh(plaster, fabric):
    phis = [2 * math.pi * (j + 0.5) / M - math.pi for j in range(M)]
    rings = []

    def ring(fn):
        pts = []
        for phi in phis:
            s, r, lump = fn(phi)
            p = ELBOW + AX * s + direction(phi) * r
            if lump:
                p = p + direction(phi) * lumps(p, lump)
            pts.append(p)
        return pts

    def cuff_ring(end, ds, base, off):
        def fn(phi):
            s = (s_top(phi) + ds if end == 0 else s_bottom(phi) - ds) + end_jitter(phi, end)
            wob = 1.0 + 0.12 * noise.noise(Vector((math.cos(phi) * 3.0, math.sin(phi) * 3.0, 9.0 + end)))
            r = (r_skin(s, phi) if base == "skin" else r_cast(s, phi)) + off * (wob if off > 0 else 1.0)
            return s, r, (0.6 if base == "out" else 0.0)
        pts = ring(fn)
        if base == "out":
            PLASTER_PTS.extend(pts)
        return pts

    for ds, base, off in CUFF:
        rings.append(cuff_ring(0, ds, base, off))
    for i in range(BODY_RINGS):
        f = i / (BODY_RINGS - 1)

        def fn(phi, f=f):
            s = ((s_top(phi) + end_jitter(phi, 0) + 0.0155) * (1 - f)
                 + (s_bottom(phi) + end_jitter(phi, 1) - 0.0155) * f)
            return s, r_cast(s, phi), 0.6 + 0.4 * math.sin(math.pi * f)
        rings.append(ring(fn))
        PLASTER_PTS.extend(rings[-1])
    for ds, base, off in reversed(CUFF):
        rings.append(cuff_ring(1, ds, base, off))

    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    flags = []
    n = len(vr)
    for k in range(n - 1):
        a, b = vr[k], vr[k + 1]
        fab = k < FABRIC_FACES or k >= n - 1 - FABRIC_FACES  # the rolled cuffs; the plaster starts after them
        for j in range(M):
            j1 = (j + 1) % M
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
            flags.append(fab)
    # Outward: a face on the plaster faces away from the axis
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    f = bm.faces[(n // 2) * M]
    rel = f.calc_center_median() - ELBOW
    if f.normal.dot(rel - AX * rel.dot(AX)) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Cast", bm, plaster)
    obj.data.materials.append(fabric)
    for poly, fab in zip(obj.data.polygons, flags):
        poly.material_index = 1 if fab else 0
    return tk.smooth(obj, 55)


# ---------------------------------------------------------------- marker writing (rasterized to a mask image)

def glyph_tris(body, font):
    cu = bpy.data.curves.new("Glyphs", "FONT")
    cu.body = body
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 6
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    ob = tk.link(bpy.data.objects.new("Glyphs", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tris = np.array([[(v.co.x, v.co.y) for v in f.verts] for f in bm.faces])
    bm.free()
    bpy.data.meshes.remove(me)
    return tris


def place(tris, center, height, degrees, slant=0.0):
    """Glyph triangles scaled to `height`, slanted (a hand's lean), turned and moved to center."""
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    t = (tris - (lo + hi) / 2) * (height / (hi[1] - lo[1]))
    t[..., 0] += t[..., 1] * slant
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    x, y = t[..., 0].copy(), t[..., 1].copy()
    t[..., 0] = x * c - y * s + center[0]
    t[..., 1] = x * s + y * c + center[1]
    return t


def raster(shape, box, tris, ss=2):
    H, W = shape
    x0, y0, x1, y1 = box
    Hs, Ws = H * ss, W * ss
    img = np.zeros((Hs, Ws), np.float32)
    sx, sy = Ws / (x1 - x0), Hs / (y1 - y0)
    for t in tris:
        P = np.column_stack(((t[:, 0] - x0) * sx, (t[:, 1] - y0) * sy))
        lo = np.maximum(np.floor(P.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(P.max(0)).astype(int), [Ws, Hs])
        if (hi <= lo).any():
            continue
        X, Y = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)

        def ef(a, b):
            return (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
        e0, e1, e2 = ef(P[0], P[1]), ef(P[1], P[2]), ef(P[2], P[0])
        ins = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
        img[lo[1]:hi[1], lo[0]:hi[0]][ins] = 1.0
    return img.reshape(H, ss, W, ss).mean(axis=(1, 3))


def mask_image(name, channels):
    H, W = channels[0].shape
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((H, W, 4), np.float32)
    for k, c in enumerate(channels):
        rgba[..., k] = np.clip(c, 0.0, 1.0)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(tempfile.gettempdir(), "zx_%s.png" % name)
    img.file_format = "PNG"
    img.save()
    return img


FONTS = "C:/Windows/Fonts/"
INK, PRINT, SCRIPTF, COMIC, SYM = (FONTS + f for f in ("Inkfree.ttf", "segoepr.ttf", "segoesc.ttf", "comic.ttf",
                                                       "seguisym.ttf"))
# u: meters round the cast from the back of the forearm (+ toward the thumb side), v: meters down from the elbow.
# The palm side (|u| above about 0.11) faces the body and carries nothing.
DECAL_BOX = (-0.16, 0.0, 0.16, 0.28)
WRITING = [  # text, font, channel (0 black, 1 blue, 2 red), (u, v), height, turn, slant, felt tip (px)
    ("Get well soon!", INK, 1, (0.006, 0.148), 0.02, 88.0, 0.15, 2),
    ("Mike", PRINT, 0, (0.056, 0.092), 0.022, 76.0, 0.1, 2),
    ("Jess", INK, 2, (-0.046, 0.165), 0.02, 95.0, 0.2, 2),
    ("\u2661", SYM, 2, (-0.05, 0.218), 0.018, 10.0, 0.0, 1),
    ("Love, Mom", SCRIPTF, 0, (0.075, 0.19), 0.014, 98.0, 0.0, 2),
    ("Tony B.", COMIC, 1, (-0.04, 0.07), 0.014, -12.0, 0.1, 1),
    ("\u263a", SYM, 0, (0.034, 0.236), 0.022, 15.0, 0.0, 1),
    ("\u2606", SYM, 2, (-0.083, 0.108), 0.02, -20.0, 0.0, 1),
    ("\u2620", SYM, 0, (0.098, 0.122), 0.022, 80.0, 0.0, 0),
    ("XOXO", INK, 2, (-0.09, 0.2), 0.012, 92.0, 0.1, 1),
    ("lol", PRINT, 1, (-0.012, 0.055), 0.014, -6.0, 0.0, 1),
]


def dilate(img, px):
    """A felt tip: thickens the strokes by px pixels."""
    if px <= 0:
        return img
    out = img.copy()
    for dy in range(-px, px + 1):
        for dx in range(-px, px + 1):
            if dx * dx + dy * dy <= px * px + 0.5:
                out = np.maximum(out, np.roll(np.roll(img, dy, axis=0), dx, axis=1))
    return out


def writing_image():
    shape = (840, 960)
    chans = [np.zeros(shape, np.float32) for _ in range(3)]
    for text, font, ch, c, h, deg, slant, tip in WRITING:
        tris = place(glyph_tris(text, font), c, h, deg, slant)
        chans[ch] = np.maximum(chans[ch], dilate(raster(shape, DECAL_BOX, tris), tip))
    return mask_image("ArmCastWriting", chans)


# ---------------------------------------------------------------- materials

def mapping(g, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rot
    m.inputs["Location"].default_value = loc
    return m.outputs[0]


def voronoi(g, vec, scale, feature="F1", out="Distance"):
    n = g.node("ShaderNodeTexVoronoi", feature=feature)
    g._in(n, "Scale", scale)
    g.links.new(vec, n.inputs["Vector"])
    return tk._sock(n.outputs, out)


def vdot(g, vec, d):
    n = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = tuple(d)
    return tk._sock(n.outputs, "Value")


def vsub(g, vec, c):
    n = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = tuple(c)
    return n.outputs[0]


def arm_coords(g):
    """(u, v, angle): meters round the cast from its back, meters down from the elbow, the angle round (radians)."""
    rel = vsub(g, g.coords(), ELBOW)
    v = vdot(g, rel, AX)
    ang = g.math("ARCTAN2", vdot(g, rel, FRONT), vdot(g, rel, DORSAL))
    rr = g.math("ADD", 0.053, g.math("MULTIPLY", v, (0.0425 - 0.053) / LEN))
    return g.math("MULTIPLY", ang, rr), v, ang


def decal(g, img, u, v, box):
    cx = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", u, box[0]), box[2] - box[0]), cx.inputs[0])
    g.links.new(g.math("DIVIDE", g.math("SUBTRACT", v, box[1]), box[3] - box[1]), cx.inputs[1])
    n = g.node("ShaderNodeTexImage", interpolation="Linear", extension="CLIP")
    n.image = img
    g.links.new(cx.outputs[0], n.inputs["Vector"])
    return g.separate(n.outputs["Color"])


def plaster_material(name, writing):
    """Old plaster of Paris: grey-beige, the spiral edges of the bandage it was wrapped from, lumps smoothed by hand;
    marker writing faded and rubbed, grime packed in the ridges, dirt, water tide-marks, a crack, dried blood."""
    mat, g = tk.new_material(name)
    u, v, ang = arm_coords(g)
    P = mapping(g, g.coords(), loc=(0.37, 1.1, 0.53))

    def nz(scale, detail=4.0, r=0.55, dist=0.0, vec=P):
        return g.noise(scale, detail=detail, roughness=r, vector=vec, distortion=dist)

    def uvnoise(su, sv, detail=2.0, off=0.0):
        """Noise stretched along the wraps (round the arm, su) and tight across them (sv)."""
        c = g.node("ShaderNodeCombineXYZ")
        g.links.new(g.math("MULTIPLY", u, su), c.inputs[0])
        g.links.new(g.math("MULTIPLY", v, sv), c.inputs[1])
        c.inputs[2].default_value = off
        return g.noise(1.0, detail=detail, vector=c.outputs[0])

    # Plaster: grey-beige, blotchy, yellowed in patches
    tone = nz(5.0, 4.0)
    col = g.mix(g.ramp(tone, 0.25, 0.8), (0.255, 0.235, 0.197), (0.168, 0.152, 0.121))
    yel = g.ramp(nz(2.0, 5.0, 0.6, 0.5), 0.52, 0.72)
    col = g.mix(g.math("MULTIPLY", yel, 0.6), col, (0.22, 0.183, 0.118))
    rough = g.math("ADD", 0.84, g.math("MULTIPLY", g.math("SUBTRACT", nz(16.0), 0.5), 0.1))
    # The plaster bandage it was wrapped from, in two passes spiralling opposite ways: each overlapping edge a small
    # step with grime packed under it (some smoothed over), crinkles along the turns, the gauze's grain
    height = None
    for turns, pitch, lo, off in ((2.0, 0.062, 0.28, 0.0), (-1.0, 0.045, 0.5, 0.37)):
        wraw = g.math("ADD", g.math("ADD", g.math("DIVIDE", v, pitch), g.math("MULTIPLY", ang, turns / (2 * math.pi))),
                      g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", nz(4.0, 2.0), 0.5), 0.5), off))
        w = g.math("FRACT", wraw)
        shown = g.ramp(nz(9.0 + 4.0 * off, 3.0), lo, lo + 0.25)
        step = g.math("SUBTRACT", g.ramp(w, 0.0, 0.025), g.math("MULTIPLY", w, 0.5))
        h = g.math("MULTIPLY", step, g.math("MULTIPLY", shown, 0.8))
        height = h if height is None else g.math("ADD", height, h)
        crease = g.math("MULTIPLY", g.ramp(w, 0.88, 0.995), shown)
        col = g.mix(g.math("MULTIPLY", crease, 0.8), col, (0.05, 0.043, 0.033))
    crinkle = g.ramp(uvnoise(14.0, 150.0, 3.0), 0.45, 0.75)
    height = g.math("ADD", height, g.math("MULTIPLY", crinkle, 0.35))
    col = g.mix(g.math("MULTIPLY", g.ramp(uvnoise(14.0, 150.0, 3.0), 0.62, 0.8), 0.35), col, (0.09, 0.08, 0.063))
    height = g.math("ADD", height, g.math("MULTIPLY", nz(260.0, 2.0), 0.12))
    # Marker writing: faded and partly rubbed off
    if writing is not None:
        k, b, r = decal(g, writing, u, v, DECAL_BOX)
        rub = g.ramp(nz(28.0, 6.0, 0.7), 0.24, 0.46)
        fade = g.mixf(g.ramp(nz(3.0, 3.0), 0.3, 0.7), 0.72, 1.0)
        for ink, c in ((k, (0.014, 0.014, 0.016)), (b, (0.02, 0.034, 0.1)), (r, (0.11, 0.018, 0.016))):
            m = g.math("MULTIPLY", g.math("MULTIPLY", ink, rub), fade)
            col = g.mix(m, col, c)
            rough = g.mixf(m, rough, 0.62)
    # Water stains: tide-marked brown rings
    tide = nz(1.8, 4.0, 0.55, 0.3)
    ring = g.math("MULTIPLY", g.ramp(tide, 0.55, 0.58), g.ramp(tide, 0.61, 0.58))
    inside = g.ramp(tide, 0.565, 0.6)
    col = g.mix(g.math("MULTIPLY", inside, 0.5), col, (0.13, 0.098, 0.06))
    col = g.mix(g.math("MULTIPLY", ring, 0.85), col, (0.065, 0.046, 0.028))
    # Hairline cracks over the back of the wrist end, where it flexes: grime in them, the lips chipped paler
    # (one long crack running round the arm, wandering: noise stretched across the arm, so its contour runs round)
    region = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(v, 0.185, 0.215), g.ramp(v, 0.262, 0.245)),
                    g.ramp(g.math("ABSOLUTE", ang), 2.0, 1.2))
    n_ = g.noise(1.0, detail=3.0, roughness=0.6, vector=mapping(g, P, (9.0, 9.0, 9.0), loc=(0.2, 0.0, 0.0)),
                 distortion=0.25)
    d_ = g.math("ABSOLUTE", g.math("SUBTRACT", n_, 0.5))
    line = g.math("MULTIPLY", g.ramp(d_, 0.012, 0.002), g.ramp(nz(30.0), 0.28, 0.42))
    line = g.math("MULTIPLY", line, region)
    lip = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(d_, 0.03, 0.01), region), g.ramp(nz(50.0), 0.45, 0.6))
    col = g.mix(g.math("MULTIPLY", lip, 0.5), col, (0.235, 0.22, 0.19))
    col = g.mix(line, col, (0.022, 0.018, 0.014))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", line, 1.6), g.math("MULTIPLY", lip, 0.3)))
    # Dirt from a photo's dark parts, worse toward the hand and on the palm side; grime in hollows; grubby
    # smudges; dark specks
    p = tk.photo(g, "rust_coarse_01", 2.6, (0.61, 0.25, 0.17))
    grad = g.math("ADD", g.math("MULTIPLY", g.ramp(v, 0.08, 0.26), 0.35),
                  g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", ang), 1.9, 2.9), 0.4))
    ends = g.math("MAXIMUM", g.ramp(v, 0.075, 0.045), g.ramp(v, 0.22, 0.258))
    grad = g.math("ADD", grad, g.math("MULTIPLY", ends, g.ramp(nz(12.0, 4.0), 0.3, 0.6)))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.26, 0.07), g.math("ADD", 0.6, grad))
    dirt = g.math("MAXIMUM", dirt, tk._grime(g, 1.0), clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, g.mix(nz(10.0), (0.042, 0.035, 0.026), (0.085, 0.07, 0.05)))
    rough = g.mixf(dirt, rough, 0.9)
    smudge = g.math("MULTIPLY", g.ramp(nz(6.0, 6.0, 0.65, 0.8), 0.52, 0.68), 0.55)
    col = g.mix(smudge, col, tk._darker(g, col, 0.5))
    spots = g.ramp(voronoi(g, P, 140.0), 0.15, 0.06)
    sp = g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.6))
    col = g.mix(sp, col, (0.022, 0.018, 0.014))
    # Dried blood: smears, spatter and a run, dark brown-red
    reg = g.ramp(nz(1.8, 5.0, 0.6, 0.6), 0.5, 0.62)
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 30.0), 0.15, 0.05),
                   g.ramp(nz(25.0), 0.42, 0.6))
    smear_b = g.ramp(nz(8.0, 8.0, 0.7, 1.4), 0.57, 0.65)
    bl = g.math("MULTIPLY", g.math("MAXIMUM", drops, smear_b), reg, clamp=True)
    col = g.mix(bl, col, g.mix(nz(20.0), (0.032, 0.007, 0.005), (0.062, 0.015, 0.01)))
    rough = g.mixf(bl, rough, 0.5)
    height = g.math("ADD", height, g.math("MULTIPLY", bl, 0.15))
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.35, 0.0015))


def stockinette_material(name):
    """The cotton stockinette rolled over the plaster's ends: soft knit, grey with dirt, dark inside."""
    mat, g = tk.new_material(name)
    u, v, ang = arm_coords(g)
    P = mapping(g, g.coords(), loc=(2.1, 0.4, 1.9))
    ribs = g.math("SINE", g.math("ADD", g.math("MULTIPLY", ang, 60.0),
                                 g.math("MULTIPLY", g.noise(30.0, detail=2.0, vector=P), 6.0)))
    knit = g.noise(300.0, detail=2.0, vector=P)
    folds = g.noise(45.0, detail=3.0, vector=mapping(g, P, (1.0, 1.0, 1.0), loc=(0.3, 0.9, 0.1)))
    col = g.mix(g.ramp(g.noise(6.0, detail=4.0, vector=P), 0.3, 0.75), (0.135, 0.128, 0.112), (0.09, 0.084, 0.072))
    col = g.mix(g.math("MULTIPLY", g.ramp(folds, 0.55, 0.3), 0.6), col, (0.05, 0.045, 0.038))
    dirt = g.math("MAXIMUM", g.ramp(g.noise(9.0, detail=6.0, roughness=0.65, vector=P), 0.48, 0.68),
                  tk._grime(g, 1.4), clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, (0.036, 0.03, 0.024))
    bl = g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=6.0, distortion=0.8, vector=P), 0.6, 0.7), 0.8)
    col = g.mix(bl, col, (0.04, 0.009, 0.006))
    height = g.math("ADD", g.math("ADD", g.math("MULTIPLY", ribs, 0.08), g.math("MULTIPLY", knit, 0.3)),
                    g.math("MULTIPLY", folds, 0.6))
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(height, 0.4, 0.0012))


# ---------------------------------------------------------------- fit report, export, previews

def capsules():
    out = []
    for c in sk.colliders:
        if c["type"] != "capsule":
            continue
        ax = Vector((0.0, 0.0, 0.0))
        ax[c["axis"]] = 1.0
        half = max(0.0, c["height"] / 2 - c["radius"])
        ctr = Vector(c["center"])
        out.append((c["bone"], sk.point(c["bone"], ctr - ax * half), sk.point(c["bone"], ctr + ax * half),
                    c["radius"]))
    return out


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def skin_gap(p):
    """How far p is outside the assumed forearm skin (negative inside)."""
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
    for bone, a, b, r in capsules():
        if bone != BONE:
            continue
        gaps = [(seg_distance(p, a, b) - r, (p - ELBOW).dot(AX) / LEN) for p in PLASTER_PTS]
        for lo_t, hi_t in ((0.0, 0.5), (0.5, 1.0)):
            g_ = [d for d, t in gaps if lo_t <= t < hi_t]
            if g_:
                print("[%s] plaster off the %s hit box, %d-%d%% down the bone: %.1f to %.1f cm, %d of %d vertices "
                      "inside it" % (NAME, bone, 100 * lo_t, 100 * hi_t, 100 * min(g_), 100 * max(g_),
                                     sum(1 for d in g_ if d < 0), len(g_)))
    gaps = sorted(skin_gap(p) for p in pts)
    og = [d for d in gaps if d > 0.003]
    print("[%s] off the assumed skin: the cuffs' inner sleeves %.1f cm, the outer surface %.1f to %.1f cm"
          % (NAME, 100 * gaps[0], 100 * og[0], 100 * og[-1]))
    return parts


def slim_forearm():
    """The previews' forearm: the assumed arm (elliptical, tapering) in place of the fat hit box capsule."""
    mat = bpy.data.materials["BodySkin"]
    for i, c in enumerate(sk.colliders):
        if c["bone"] == BONE:
            bpy.data.objects.remove(bpy.data.objects["Body_%d" % i])
    bm = bmesh.new()
    n, m = 20, 24
    rows = []
    for i in range(n + 1):
        s = -0.03 + (LEN + 0.03) * i / n
        rows.append([bm.verts.new(ELBOW + AX * s + direction(2 * math.pi * j / m) * r_skin(s, 2 * math.pi * j / m))
                     for j in range(m)])
    for a, b in zip(rows, rows[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
    bm.faces.new(rows[0])
    bm.faces.new(list(reversed(rows[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tk.smooth(tk.mesh_object("PreForeArm", bm, mat), 60)
    for name, p, r in (("PreElbow", ELBOW, 0.045), ("PreWrist", WRIST, 0.03)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r)
        bmesh.ops.translate(bm, vec=p, verts=bm.verts)
        tk.smooth(tk.mesh_object(name, bm, mat), 60)


def close_up(view, direction_, target, distance=0.4, lens=50):
    loc = Vector(target) + Vector(direction_).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


plaster = plaster_material("Plaster", writing_image())
fabric = stockinette_material("Stockinette")
pieces = [cast_mesh(plaster, fabric)]
export(pieces)
slim_forearm()
mid = ELBOW + AX * (LEN * 0.55)
zk.previews(SCRIPT, PREVIEWS, mid, distance=0.75)
close_up("top", DORSAL * 1.0 + FRONT * 0.35, mid, distance=0.42)
close_up("front", FRONT * 1.0 + DORSAL * 0.3 - AX * 0.2, mid, distance=0.42)
close_up("wrist", AX * 0.8 + DORSAL * 0.5 + FRONT * 0.5, WRIST - AX * 0.02, distance=0.3)
print("[%s] done" % SCRIPT)
