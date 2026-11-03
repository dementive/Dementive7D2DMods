"""Ski pole (remnant): the top half of an aluminum ski pole, snapped in two and driven into the back of the left calf.
The snapped end went in buckled and bent (the crumpled kink shows right at the wound, the torn end is deep in the
calf); out behind it the dark anodized tube runs back, out and a little down to the moulded rubber grip, its nylon
wrist strap hanging in a loop from the top. The tube is scuffed to bare aluminum, its faded graphics half scraped off,
grimy, and caked with dried blood and torn flesh where it goes in; the grip is worn shiny where the palm rode it; the
strap is filthy.

The pole points back and a little out (clear of the other leg's swing) and slightly down. The snapped end sinks 4 cm
past the stand-in. One part on LeftLeg: "LeftLeg#Pole".

    blender -b --factory-startup --python ski_pole.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "SkiPole", "ski_pole", 4729

import math
import os
import sys

import bmesh
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
UP = Vector((0.0, 0.0, 1.0))
LOCAL = "sp_local"  # (x, y across, s along the pole from the skin outward), for the materials


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- the body as a distance field

def _hit_boxes():
    out = []
    for c in SK.colliders:
        if c["type"] == "capsule":
            ax = Vector((0.0, 0.0, 0.0))
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            out.append((c["bone"], SK.point(c["bone"], ctr - ax * half), SK.point(c["bone"], ctr + ax * half),
                        c["radius"]))
        elif c["type"] == "sphere":
            p = SK.point(c["bone"], c["center"])
            out.append((c["bone"], p, p.copy(), c["radius"]))
    return out


CAPS = _hit_boxes()
LEG = ("LeftLeg",)


def seg_closest(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return a + ab * t, t


def sdf(p, bones=None):
    """Distance from p to the stand-in's surface (its hit boxes), negative inside."""
    p = Vector(p)
    return min((p - seg_closest(p, a, b)[0]).length - r for bone, a, b, r in CAPS if bones is None or bone in bones)


def skin(target, direction, bones=None):
    """Where the line through `target` along `direction` (pointing into the body) meets the stand-in from outside."""
    d = Vector(direction).normalized()
    start = Vector(target) - d * 0.6
    t, step = 0.0, 0.002
    while sdf(start + d * t, bones) > 0.0:
        t += step
        if t > 1.2:
            raise ValueError("the line misses the body")
    lo, hi = t - step, t
    for _ in range(30):
        mid = (lo + hi) / 2
        if sdf(start + d * mid, bones) > 0.0:
            lo = mid
        else:
            hi = mid
    return start + d * hi


# ---------------------------------------------------------------- mesh helpers

def arclen(P):
    s = [0.0]
    for i in range(1, len(P)):
        s.append(s[-1] + (P[i] - P[i - 1]).length)
    return s


def set_attr(obj, name, vals):
    me = obj.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT_VECTOR", "POINT")
    assert len(vals) == len(me.vertices), (obj.name, name, len(vals), len(me.vertices))
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return obj


def frames(P, ref=None):
    """Tangents and twist-free normals and binormals along a polyline (parallel transport)."""
    n = len(P)
    T = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
    ref = ref or (UP if abs(T[0].z) < 0.9 else Vector((1.0, 0.0, 0.0)))
    N = []
    for t in T:
        nv = (ref - t * ref.dot(t)).normalized()
        N.append(nv)
        ref = nv
    return T, N, [t.cross(nv) for t, nv in zip(T, N)]


def sweep(name, P, section, mat, S=None, caps=(True, True), smooth=40, ref=None, mats=None):
    """A solid swept along the path P: section(i) gives ring i's outline [(x, y)] on the path's (N, B) frame.
    LOCAL records (x, y, s) per vertex, s from S (default arc length). mats(i) -> material index for the faces
    from ring i to i + 1 (the extra materials appended by the caller)."""
    n = len(P)
    S = S or arclen(P)
    T, N, B = frames(P, ref)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        ring = []
        for x, y in section(i):
            ring.append(bm.verts.new(P[i] + N[i] * x + B[i] * y))
            vals.append((x, y, S[i]))
        rings.append(ring)
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        m = len(a)
        for j in range(m):
            j1 = (j + 1) % m
            f = bm.faces.new((a[j], a[j1], b[j1], b[j]))
            if mats:
                f.material_index = mats(i)
    if caps[0]:
        f = bm.faces.new(list(reversed(rings[0])))
        if mats:
            f.material_index = mats(-1)
    if caps[1]:
        f = bm.faces.new(rings[-1])
        if mats:
            f.material_index = mats(n - 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, LOCAL, vals)
    return tk.smooth(obj, smooth)


def circle(r, n=12, rx=1.0, ry=1.0, phase=0.0, fn=None):
    """n points round a circle of radius r squashed (rx, ry); fn(angle) scales the radius."""
    out = []
    for k in range(n):
        a = phase + 2 * math.pi * k / n
        s = fn(a) if fn else 1.0
        out.append((r * s * rx * math.cos(a), r * s * ry * math.sin(a)))
    return out


# ---------------------------------------------------------------- material helpers

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


def warp(g, P, scale, amount):
    """P pushed about by noise, so patterns laid on it lose their regularity."""
    n = g.node("ShaderNodeTexNoise")
    g._in(n, "Scale", scale)
    g._in(n, "Detail", 3.0)
    g.links.new(P, n.inputs["Vector"])
    s = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(tk._sock(n.outputs, "Color"), s.inputs[0])
    tk._sock(s.inputs, "Scale").default_value = amount
    a = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(P, a.inputs[0])
    g.links.new(s.outputs[0], a.inputs[1])
    return a.outputs[0]


def band(g, x, lo, hi, soft=0.001):
    """1 between lo and hi, soft edges."""
    return g.math("MULTIPLY", g.ramp(x, lo - soft, lo + soft), g.ramp(x, hi + soft, hi - soft))


def scratch_mask(g, P, width=0.015):
    """Straight scratches in five directions (bands of a wave texture, each broken into short runs)."""
    sc = None
    for i, (rot, scale) in enumerate((((0.3, 0.9, 0.2), 38.0), ((1.1, 0.2, 1.4), 55.0), ((0.5, 1.3, 2.7), 30.0),
                                      ((2.3, 0.4, 0.9), 70.0), ((1.7, 2.2, 0.3), 45.0))):
        m = mapping(g, P, rot=rot, loc=(0.13 * i, 0.31 * i, 0.07 * i))
        w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        g._in(w, "Scale", scale)
        g._in(w, "Distortion", 0.8)
        g._in(w, "Detail", 1.0)
        g._in(w, "Detail Scale", 0.5)
        g.links.new(warp(g, m, 2.5 + i, 0.03), w.inputs["Vector"])
        line = g.ramp(tk._sock(w.outputs, "Fac"), 1.0 - width, 1.0 - width * 0.15)
        seg = g.ramp(g.noise(16.0 + 7.0 * i, detail=2.0, vector=m), 0.57, 0.64)
        line = g.math("MULTIPLY", line, seg)
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    return sc


def attr(g, name=LOCAL):
    a = g.node("ShaderNodeAttribute", attribute_name=name)
    a.attribute_type = "GEOMETRY"
    return tk._sock(a.outputs, "Vector")


def vmath(g, op, a, b=None, scale=None, out="Vector"):
    n = g.node("ShaderNodeVectorMath", operation=op)
    for k, x in enumerate((a, b)):
        if x is None:
            continue
        if hasattr(x, "is_output"):
            g.links.new(x, n.inputs[k])
        else:
            n.inputs[k].default_value = tuple(x)
    if scale is not None:
        g._in(n, "Scale", scale)
    return tk._sock(n.outputs, out)


def skin_distance(g, W, bones=LEG):
    """The stand-in's distance field (as sdf()) worked out per pixel from the world position W."""
    out = None
    for bone, a, b, r in CAPS:
        if bones is not None and bone not in bones:
            continue
        pa = vmath(g, "SUBTRACT", W, a)
        ab = b - a
        t = vmath(g, "DOT_PRODUCT", pa, ab / ab.length_squared, out="Value")
        t = g.math("MINIMUM", g.math("MAXIMUM", t, 0.0), 1.0)
        q = vmath(g, "SUBTRACT", pa, vmath(g, "SCALE", ab, scale=t))
        d = g.math("SUBTRACT", vmath(g, "LENGTH", q, out="Value"), r)
        out = d if out is None else g.math("MINIMUM", out, d)
    return out


def gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.06, soak=0.02):
    """Blood and gore drying on the pole where it went in: soaked and clotted from inside the body to `soak` out of
    the stand-in, then runs, smears and spatter thinning out to `reach`."""
    d = skin_distance(g, W)
    ragged = g.math("ADD", g.math("SUBTRACT", g.noise(14.0, 4.0, 0.6, P), 0.5),
                    g.math("MULTIPLY", g.math("SUBTRACT", g.noise(60.0, 5.0, 0.7, P), 0.5), 0.6))
    ragged = g.math("MULTIPLY", ragged, 1.4 * soak + 0.006)
    wet = g.ramp(g.math("ADD", d, ragged), soak, soak * 0.2)
    near = g.ramp(g.math("ADD", d, g.math("MULTIPLY", g.noise(6.0, 4.0, 0.6, P), 0.4 * reach)), reach, soak * 0.5)
    runs = g.ramp(g.noise(1.0, 3.0, 0.55, mapping(g, P, scale=(110.0, 110.0, 7.0), loc=(0.2, 0.7, 0.1))), 0.6, 0.67)
    spots = g.ramp(voronoi(g, mapping(g, P, loc=(0.3, 0.1, 0.7)), 170.0), 0.17, 0.07)
    spots = g.math("MULTIPLY", spots, g.ramp(g.noise(9.0, 3.0, vector=P), 0.4, 0.55))
    smear = g.ramp(g.noise(14.0, 6.0, 0.65, P, 1.2), 0.53, 0.6)
    b = g.math("MAXIMUM", g.math("MAXIMUM", runs, spots), smear)
    b = g.math("MAXIMUM", wet, g.math("MULTIPLY", b, near))
    b = g.math("MULTIPLY", b, amount, clamp=True)
    clot = g.math("MULTIPLY", g.ramp(d, soak * 0.6, -0.01), g.ramp(g.noise(24.0, 5.0, 0.6, P), 0.38, 0.62))
    fresh = g.ramp(g.noise(7.0, 4.0, vector=mapping(g, P, loc=(1.1, 0.3, 0.6))), 0.45, 0.72)
    bc = g.mix(fresh, (0.03, 0.005, 0.004), (0.075, 0.01, 0.006))
    bc = g.mix(clot, bc, (0.015, 0.004, 0.003))
    tissue = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.5, 0.9, 0.2)), 70.0), 0.14, 0.06), clot)
    bc = g.mix(g.math("MULTIPLY", tissue, 0.8), bc, (0.12, 0.055, 0.045))
    col = g.mix(b, col, bc)
    rgh = g.mixf(b, rgh, g.mixf(clot, g.mixf(fresh, 0.62, 0.42), 0.3))
    met = g.mixf(b, met, 0.0)
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", b, 0.3), g.math("MULTIPLY", clot, 1.2)))
    return col, rgh, met, height


def grime_and_dust(g, P, col, rgh, met, grime=0.7, dust=0.4):
    """Dirt in the hollows and in blotches, dust settled on the upper faces."""
    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    dirt = g.math("MAXIMUM", tk._grime(g, grime),
                  g.math("MULTIPLY", g.ramp(g.noise(5.0, 6.0, 0.6, P), 0.58, 0.7), 0.6 * grime))
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, g.mix(g.noise(9.0, vector=P), (0.014, 0.011, 0.008),
                                                            (0.034, 0.027, 0.019)))
    rgh = g.mixf(dirt, rgh, 0.88)
    met = g.mixf(dirt, met, 0.0)
    du = g.math("MULTIPLY", g.ramp(up, 0.3, 0.95), g.ramp(g.noise(8.0, 6.0, 0.6, P), 0.4, 0.7))
    du = g.math("MULTIPLY", du, dust)
    col = g.mix(du, col, (0.11, 0.095, 0.075))
    rgh = g.mixf(du, rgh, 0.95)
    met = g.mixf(du, met, 0.0)
    return col, rgh, met


def seeded(g, seed):
    return mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))


# ---------------------------------------------------------------- materials

def tube_metal(name, seed):
    """Dark anodized aluminum: charcoal-blue, faintly mottled, scuffed and scratched to bright metal, its printed
    graphics (white and red bands, a long logo panel) faded and half scraped off, grimy, bloodied at the wound."""
    mat, g = tk.new_material(name)
    W = g.coords()
    P = seeded(g, seed)
    x, y, s = g.separate(attr(g))
    tone = g.noise(8.0, 4.0, 0.55, P)
    col = g.mix(tone, (0.011, 0.013, 0.018), (0.019, 0.022, 0.029))
    rgh = g.math("ADD", 0.45, g.math("MULTIPLY", tone, 0.12))
    met = 0.75
    height = g.math("MULTIPLY", g.noise(120.0, 4.0, 0.6, P), 0.08)
    # Printed graphics down from the grip: a red band, white pinstripes and a long pale logo panel
    ang = g.math("ARCTAN2", y, x)
    red = band(g, s, 0.205, 0.228, 0.0008)
    white = g.math("MAXIMUM", band(g, s, 0.196, 0.2, 0.0005), band(g, s, 0.232, 0.236, 0.0005))
    panel = g.math("MULTIPLY", band(g, s, 0.1, 0.185, 0.001), band(g, ang, -0.7, 0.7, 0.03))
    letters = g.ramp(g.noise(1.0, 2.0, 0.4, mapping(g, attr(g), scale=(0.0, 0.0, 260.0), loc=(0.0, 0.0, 0.3))),
                     0.5, 0.53)
    panel_ink = g.math("MULTIPLY", panel, g.math("MULTIPLY", band(g, ang, -0.45, 0.45, 0.02), letters))
    scraped = g.ramp(g.noise(22.0, 6.0, 0.7, P, 0.6), 0.42, 0.5)
    ink_col = g.mix(red, (0.085, 0.082, 0.078), (0.05, 0.011, 0.008))
    ink = g.math("MULTIPLY", g.math("MAXIMUM", g.math("MAXIMUM", red, white), g.math("MULTIPLY", panel, 0.7)),
                 scraped)
    col = g.mix(ink, col, ink_col)
    col = g.mix(g.math("MULTIPLY", panel_ink, scraped), col, (0.013, 0.015, 0.018))
    rgh = g.mixf(ink, rgh, 0.5)
    met = g.mixf(ink, met, 0.1)
    # Scuffs and scratches to bare aluminum, the snapped end's metal torn bright and dull
    sc = g.math("MULTIPLY", scratch_mask(g, P, 0.025), g.ramp(g.noise(3.0, 3.0, vector=P), 0.4, 0.62))
    scuff = g.math("MULTIPLY", g.ramp(g.noise(12.0, 6.0, 0.7, P, 1.0), 0.6, 0.7), 0.7)
    bare = g.math("MAXIMUM", sc, scuff)
    col = g.mix(bare, col, g.mix(g.noise(40.0, 3.0, vector=P), (0.09, 0.09, 0.093), (0.16, 0.16, 0.165)))
    rgh = g.mixf(bare, rgh, 0.36)
    met = g.mixf(bare, met, 0.95)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.4))
    # Oxidized and dull where the tube is torn and buckled (by the wound)
    col, rgh, met = grime_and_dust(g, P, col, rgh, met, 0.75, 0.18)
    col, rgh, met, height = gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.16, soak=0.06)
    # Blood that ran out of the wound along the underside of the tube (it slopes down toward the grip)
    under = g.ramp(g.math("DIVIDE", y, R_TUBE), 0.2, 0.75)
    streak = g.ramp(g.noise(1.0, 3.0, 0.5, mapping(g, attr(g), scale=(260.0, 260.0, 9.0), loc=(0.3, 0.1, 0.0))),
                    0.48, 0.56)
    run = g.math("MULTIPLY", g.math("MULTIPLY", under, streak), g.ramp(g.math("ADD", s, g.math("MULTIPLY",
                 g.noise(9.0, 3.0, vector=P), 0.06)), 0.17, 0.03))
    col = g.mix(run, col, g.mix(g.noise(25.0, vector=P), (0.028, 0.005, 0.004), (0.065, 0.009, 0.006)))
    rgh = g.mixf(run, rgh, 0.45)
    met = g.mixf(run, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", run, 0.25))
    col, rgh, met = tk._grit(g, col, rgh, met, 0.15)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, 0.35, 0.0015))


def grip_rubber(name, seed):
    """Moulded black rubber: a fine pebbled texture, worn smooth and shiny where the palm and fingers rode it, grime
    packed in the grooves, a faded dull red cap on top, blood spatter."""
    mat, g = tk.new_material(name)
    W = g.coords()
    P = seeded(g, seed)
    x, y, s = g.separate(attr(g))
    tone = g.noise(10.0, 4.0, 0.55, P)
    col = g.mix(tone, (0.007, 0.007, 0.007), (0.013, 0.0125, 0.012))
    rgh = g.math("ADD", 0.78, g.math("MULTIPLY", tone, 0.1))
    pebble = g.ramp(voronoi(g, mapping(g, P, loc=(0.2, 0.3, 0.4)), 900.0), 0.0, 0.35)
    height = g.math("MULTIPLY", pebble, 0.5)
    # The cap: dull red plastic over the top 1.5 cm
    cap = g.ramp(s, 0.399, 0.401)
    cap_col = g.mix(g.noise(30.0, 3.0, vector=P), (0.028, 0.008, 0.006), (0.042, 0.012, 0.009))
    col = g.mix(cap, col, cap_col)
    rgh = g.mixf(cap, rgh, 0.5)
    height = g.mixf(cap, height, 0.0)
    # Worn smooth and shiny on the palm side and the finger ridges
    worn = g.math("MULTIPLY", g.ramp(g.noise(6.0, 4.0, 0.6, P), 0.45, 0.62), g.math("SUBTRACT", 1.0, cap))
    worn = g.math("MAXIMUM", worn, g.math("MULTIPLY", g.ramp(g.edges(0.003), 0.05, 0.3), 0.6))
    col = g.mix(g.math("MULTIPLY", worn, 0.7), col, (0.022, 0.021, 0.02))
    rgh = g.mixf(worn, rgh, 0.5)
    height = g.math("MULTIPLY", height, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", worn, 0.8)))
    col, rgh, met = grime_and_dust(g, P, col, rgh, 0.0, 1.0, 0.15)
    # Spattered blood
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 70.0), 0.15, 0.05),
                   g.ramp(g.noise(12.0, 4.0, vector=P), 0.45, 0.6))
    smear = g.ramp(g.noise(9.0, 8.0, 0.7, P, 1.5), 0.62, 0.68)
    bl = g.math("MAXIMUM", drops, smear)
    col = g.mix(bl, col, g.mix(g.noise(20.0, vector=P), (0.03, 0.005, 0.004), (0.06, 0.009, 0.006)))
    rgh = g.mixf(bl, rgh, 0.45)
    col, rgh, met = tk._grit(g, col, rgh, met, 0.1)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, 0.4, 0.0012))


def webbing(name, seed):
    """Black nylon webbing: a tight diagonal weave, a faded grey-red stripe near each edge, frayed fuzz on the
    edges, filthy and stiff with old blood in places."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    x, y, s = g.separate(attr(g))
    weave = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", g.math("ADD", s, y), 520.0)), 0.5))
    weave2 = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", g.math("SUBTRACT", s, y), 520.0)),
                                       0.5))
    tw = g.math("MULTIPLY", g.ramp(weave, 0.1, 0.4), g.ramp(weave2, 0.05, 0.35))
    col = g.mix(tw, (0.006, 0.006, 0.0065), (0.013, 0.0125, 0.013))
    ay = g.math("ABSOLUTE", y)
    stripe = band(g, ay, 0.0068, 0.0084, 0.0004)
    col = g.mix(g.math("MULTIPLY", stripe, 0.8), col, (0.035, 0.014, 0.012))
    edge = g.ramp(ay, 0.0095, 0.011)
    col = g.mix(g.math("MULTIPLY", edge, g.ramp(g.noise(80.0, 3.0, vector=P), 0.4, 0.6)), col, (0.03, 0.028, 0.025))
    rgh = g.math("ADD", 0.82, g.math("MULTIPLY", tw, 0.1))
    height = g.math("ADD", g.math("MULTIPLY", tw, 0.5), g.math("MULTIPLY", edge, 0.2))
    col, rgh, met = grime_and_dust(g, P, col, rgh, 0.0, 0.9, 0.12)
    stain = g.math("MULTIPLY", g.ramp(g.noise(7.0, 6.0, 0.65, P, 0.8), 0.6, 0.68), 0.8)
    col = g.mix(stain, col, (0.035, 0.007, 0.005))
    rgh = g.mixf(stain, rgh, 0.55)
    col, rgh, met = tk._grit(g, col, rgh, met, 0.08)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, 0.35, 0.001))


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood stuck to whatever went in: wet dark red, black clots, pale shreds of fat."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    n1 = g.noise(30.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.014, 0.002, 0.002), (0.055, 0.007, 0.005))
    fat = g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=4.0, distortion=1.2, vector=P), 0.7, 0.74), 0.45)
    col = g.mix(fat, col, (0.085, 0.05, 0.035))
    clot = g.ramp(voronoi(g, P, 140.0), 0.25, 0.1)
    col = g.mix(g.math("MULTIPLY", clot, 0.6), col, (0.014, 0.002, 0.002))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.34, 0.6)
    height = g.math("ADD", g.math("MULTIPLY", n1, 0.6), g.math("MULTIPLY", fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


R_TUBE = 0.0095  # a 19 mm tube
metal = tube_metal("PoleTube", 2.0)
rubber = grip_rubber("PoleGrip", 3.0)
strap_mat = webbing("PoleStrap", 4.0)
flesh = gore_flesh("PoleGore", 5.0)

# ---------------------------------------------------------------- the pole's frame

OUT_ANGLE = math.radians(20.0)  # back and this far out to the zombie's left, clear of the other leg
DOWN_ANGLE = math.radians(8.0)
D = Vector((math.sin(OUT_ANGLE) * math.cos(DOWN_ANGLE), math.cos(OUT_ANGLE) * math.cos(DOWN_ANGLE),
            -math.sin(DOWN_ANGLE)))  # out of the calf toward the grip
CALF_Z = 0.375
TUBE_OUT = 0.25  # tube from the skin to the grip
GRIP = 0.165
SINK = 0.04
KINK = math.radians(18.0)  # the snapped end bent down inside the wound
K_AT = -0.024  # where it bends, inside the stand-in (so the pole shows straight going in)

_a, _b = [(a, b) for bone, a, b, r in CAPS if bone == "LeftLeg"][0]
LEG_C = _a.lerp(_b, (CALF_Z - _a.z) / (_b.z - _a.z))  # the leg's middle at calf height
BACK = Vector((math.sin(math.radians(4.0)), math.cos(math.radians(4.0)), 0.0))
AIM = LEG_C + BACK * 0.05 - D * 0.02  # in at the middle of the back of the calf (where it shows from behind)
E = skin(AIM, -D, LEG)  # where the tube goes in
SIDE = D.cross(UP).normalized()  # horizontal, across the pole
I_DIR = (Matrix.Rotation(KINK, 3, SIDE) @ (-D)).normalized()  # the snapped end's heading into the leg
print("[%s] enters the calf at (%.3f, %.3f, %.3f), heading out (%.2f, %.2f, %.2f), snapped end heading in "
      "(%.2f, %.2f, %.2f)" % ((SCRIPT,) + tuple(E) + tuple(D) + tuple(I_DIR)))
print("[%s] the leg's middle at calf height (%.3f, %.3f, %.3f)" % ((SCRIPT,) + tuple(LEG_C)))


def pole_path():
    """The tube's centerline from the torn end deep in the calf, through the buckled kink at the wound, out to the
    top of the tube inside the grip; with each point's distance along the pole from the skin (negative inside)."""
    K = E + D * K_AT  # the kink, inside the wound
    # Inside: from the kink along I_DIR until SINK past the stand-in
    # March in until SINK past the stand-in, or until it would start coming out the other side
    inner, best = 0.0, 9.0
    t = 0.0
    while t < 0.12:
        d = sdf(K + I_DIR * t, LEG)
        if d > best + 1e-5:
            break
        best, inner = d, t
        if d <= -SINK:
            break
        t += 0.001
    P, S = [], []
    for k in range(5):  # the snapped end in the leg, every 1 cm or so
        t = inner - (inner - 0.012) * k / 4
        P.append(K + I_DIR * t)
        S.append(K_AT - t)
    # The kink: an arc from I_DIR (reversed) round to D over 2 cm, centered on K
    n = 5
    for k in range(n + 1):
        u = k / n
        h = (-I_DIR).lerp(D, smoothstep(0.0, 1.0, u)).normalized()
        P.append(K + h * (u - 0.5) * 0.02)
        S.append(K_AT + (u - 0.5) * 0.02)
    # Out to the grip
    for t in (-0.004, 0.012, 0.035, 0.12, 0.2, TUBE_OUT, TUBE_OUT + 0.02):
        P.append(E + D * t)
        S.append(t)
    return P, S


PATH, S_POLE = pole_path()


def buckle(s):
    """How crumpled the tube is at s (1 at the kink)."""
    return math.exp(-((s - K_AT) / 0.016) ** 2)


def tube():
    def section(i):
        s = S_POLE[i]
        b = buckle(s)
        if b < 0.02:
            return circle(R_TUBE, 12)
        seed = 7.0 + i * 1.3

        def fn(a):
            return 1.0 + 0.16 * b * noise.noise(Vector((math.cos(a) * 3.0, math.sin(a) * 3.0, seed)))
        return circle(R_TUBE, 12, rx=1.0 + 0.28 * b, ry=1.0 - 0.3 * b, fn=fn)

    return sweep("Tube", PATH, section, metal, S=S_POLE, smooth=50, ref=SIDE)


# ---------------------------------------------------------------- the grip and strap

G0 = E + D * TUBE_OUT  # the grip's bottom
TOP = G0 + D * GRIP


def grip_profile():
    """(z along the grip from its bottom, radius, finger-side bulge) — a flared lip at the bottom, a slim neck, four
    finger ridges on one side, the palm swell, a rounded top."""
    prof = [(0.0, 0.0105, 0.0), (0.001, 0.0158, 0.0), (0.005, 0.0178, 0.0), (0.011, 0.0168, 0.0), (0.018, 0.0148, 0.0)]
    for k in range(4):
        z0 = 0.03 + 0.022 * k
        prof += [(z0, 0.0152, 0.0), (z0 + 0.011, 0.0156, 0.0016)]
    prof += [(0.12, 0.0166, 0.0), (0.135, 0.0178, 0.0), (0.147, 0.0184, 0.0), (0.156, 0.0178, 0.0),
             (0.1615, 0.0155, 0.0), (0.165, 0.0105, 0.0)]
    return prof


def grip():
    prof = grip_profile()
    P = [G0 + D * z for z, r, f in prof]
    S = [TUBE_OUT + z for z, r, f in prof]

    def section(i):
        z, r, f = prof[i]

        def fn(a):
            # the finger ridges on the underside (+B is about straight down)
            return 1.0 + (f / r) * max(0.0, math.sin(a)) ** 2
        return circle(r, 12, rx=1.0, ry=0.92, fn=fn)

    return sweep("Grip", P, section, rubber, S=S, smooth=55, ref=SIDE)


def strap():
    """The wrist strap: a loop of webbing out of the slot in the top of the grip, hanging down. Its plane is turned
    across the pole, so the loop shows from behind."""
    yaw = math.radians(72.0)
    dh = Vector((D.x, D.y, 0.0)).normalized()
    u = (Matrix.Rotation(yaw, 3, UP) @ dh).normalized()  # across the loop
    n_w = u.cross(UP).normalized()  # the webbing's width (normal to the loop's plane)
    L, Wd = 0.1, 0.062
    top = TOP - D * 0.004
    pts = []
    m = 24
    for k in range(m + 1):
        th = 2 * math.pi * k / m
        b = -L * (1.0 - math.cos(th)) / 2
        a = (Wd / 2) * math.sin(th) * math.sqrt(max(0.0, (1.0 - math.cos(th)) / 2)) ** 0.7
        a += 0.0018 * (1 if math.sin(th) > 0 else -1) if 0 < k < m else 0.0
        out = D * 0.016 * math.sin(th / 2) ** 0.5  # leaves the slot heading out along the pole first
        pts.append(top + u * a + UP * b + out)
    S = [0.0]
    for k in range(1, len(pts)):
        S.append(S[-1] + (pts[k] - pts[k - 1]).length)
    T = [(pts[min(k + 1, m)] - pts[max(k - 1, 0)]).normalized() for k in range(m + 1)]
    bm = bmesh.new()
    rings, vals = [], []
    hw, ht = 0.011, 0.0009
    for k in range(m + 1):
        X = n_w.cross(T[k]).normalized()  # through the webbing's thickness
        ring = []
        for x, y in ((-ht, -hw), (ht, -hw), (ht, hw), (-ht, hw)):
            ring.append(bm.verts.new(pts[k] + X * x + n_w * y))
            vals.append((x, y, S[k]))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Strap", bm, strap_mat)
    set_attr(obj, LOCAL, vals)
    return tk.smooth(obj, 50)


def crust(name, s0, s1, thick, seed, step=0.005, cover=0.6):
    """Clots and torn flesh caked on the tube from s0 to s1 (distance from the skin): the tube's own section grown by
    up to thick(t) (t 0 to 1 along it) where noise says so and sunk under the metal elsewhere."""
    Sx = S_POLE
    n = max(2, int(round((s1 - s0) / step)) + 1)
    P, S = [], []
    for k in range(n):
        s = s0 + (s1 - s0) * k / (n - 1)
        i = max(1, next((j for j in range(len(Sx)) if Sx[j] >= s), len(Sx) - 1))
        t = (s - Sx[i - 1]) / max(Sx[i] - Sx[i - 1], 1e-9)
        P.append(PATH[i - 1].lerp(PATH[i], t))
        S.append(s)
    off = Vector((seed, 0.37 * seed, 0.71 * seed))
    T, N, B = frames(P, SIDE)

    def section(i):
        b = buckle(S[i])
        amp = thick(i / (n - 1))
        out = []
        for a in [2 * math.pi * k / 10 for k in range(10)]:
            x0 = R_TUBE * (1.0 + 0.28 * b) * math.cos(a)
            y0 = R_TUBE * (1.0 - 0.3 * b) * math.sin(a)
            q = P[i] + N[i] * x0 + B[i] * y0
            k = 0.5 + 0.5 * noise.noise(q * 120.0 + off) + 0.25 * noise.noise(q * 380.0 + off * 2.0)
            k = (k - (1.0 - cover)) / cover
            r0 = math.hypot(x0, y0) * (1.0 + 0.16 * b)
            t = amp * k if k > 0.0 else -0.0012
            g = max(0.5, (r0 + t) / max(math.hypot(x0, y0), 1e-6))
            out.append((x0 * g, y0 * g))
        return out

    return sweep(name, P, section, flesh, S=S, smooth=60, ref=SIDE)


def gore_bits():
    return [crust("Gore0", -0.02, 0.026, lambda t: 0.0055 * (1.0 - smoothstep(0.3, 1.0, t)) ** 0.8, 1.0, cover=0.6)]


# ---------------------------------------------------------------- export, fit report and previews

def report(parts):
    total = 0
    for o in parts:
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        lo = Vector([min(p[k] for p in pts) for k in range(3)])
        hi = Vector([max(p[k] for p in pts) for k in range(3)])
        tris = sum(len(f.vertices) - 2 for f in o.data.polygons)
        total += tris
        print("[%s] %-6s %4d tris, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f), deepest %.1f cm in"
              % (SCRIPT, o.name, tris, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z, -100 * min(sdf(p, LEG) for p in pts)))
    print("[%s] %d triangles before triangulating" % (SCRIPT, total))
    other = min(sdf(o.matrix_world @ v.co, ("RightLeg", "RightUpLeg")) for o in parts for v in o.data.vertices)
    low = min((o.matrix_world @ v.co).z for o in parts for v in o.data.vertices)
    print("[%s] %.1f cm from the right leg's hit boxes; lowest point z %.3f" % (SCRIPT, other * 100, low))


def export(pieces):
    for o in BODY:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=512)
    for o in BODY:
        o.hide_render = False
    return parts


def close_up(view, target, direction, distance=0.5, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, Vector(target), lens=lens),
              os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)), res=(900, 900), samples=64)


pieces = [tube(), grip(), strap()] + gore_bits()
for p in pieces:
    zk.on(p, "LeftLeg", "Pole")
report(pieces)
export(pieces)
mid = E + D * 0.2
zk.previews(SCRIPT, PREVIEWS, mid + Vector((-0.05, 0.0, 0.08)), distance=1.3)
close_up("wound", E + D * 0.03, (1.0, 0.5, 0.4), distance=0.25)
close_up("grip", TOP - D * 0.06 - UP * 0.04, (1.0, -0.2, 0.5), distance=0.4)
close_up("behind", mid, (0.1, 1.0, 0.35), distance=0.75)
print("[%s] done" % SCRIPT)
