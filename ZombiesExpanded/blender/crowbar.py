"""Crowbar (remnant): a 26-inch gooseneck wrecking bar swung into the zombie's right flank, its split claw hooked in
under the lower ribs at the side and left there. The gooseneck arcs over just outside the skin and the straight bar
hangs from it, down and out past the right hip (out beside the thigh, never in front of it, as the thigh swings when it
walks), to a flattened pry end with its slight bend. Forged hex steel, the old black enamel flaked away to dark scale and
coarse rust, the corners rubbed smooth where hands held it; the claw and the bend caked with dried blood and torn flesh
where it went in, spatter and a few runs below.

The claw sinks 4 cm past the stand-in (its split tip is never seen). One part on Spine1: "Spine1#Crowbar".

    blender -b --factory-startup --python crowbar.py -- <unity models folder> <preview folder>
"""
NAME, SCRIPT, SEED = "Crowbar", "crowbar", 6211

import math
import os
import sys

import bmesh
from mathutils import Vector, noise

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
LOCAL = "cb_local"  # (x, y across the bar, s along it from the pry tip), for the materials


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def orth(v, axis):
    """v with its component along `axis` removed, normalized."""
    return (v - axis * v.dot(axis)).normalized()


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
NEAR = ("Hips", "Spine2", "RightUpLeg", "RightArm", "RightForeArm")  # the hit boxes the bar comes near


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


def sweep(name, P, W, section, mat, S=None, caps=(True, True), smooth=40):
    """A solid swept along the planar path P (the plane's normal W): section(i) gives ring i's outline [(x, y)], x
    in the plane (across the path), y along W. LOCAL records (x, y, s) per vertex, s from S (default arc length)."""
    n = len(P)
    S = S or arclen(P)
    T = []
    for i in range(n):
        T.append((P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized())
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        X = W.cross(T[i]).normalized()
        ring = []
        for x, y in section(i):
            ring.append(bm.verts.new(P[i] + X * x + W * y))
            vals.append((x, y, S[i]))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        m = len(a)
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if caps[0]:
        bm.faces.new(list(reversed(rings[0])))
    if caps[1]:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, LOCAL, vals)
    return tk.smooth(obj, smooth)


def point_at(P, S, s):
    """The point at arc length s along a polyline (S its arclen), and the heading there."""
    s = max(0.0, min(S[-1], s))
    i = max(1, next((j for j in range(len(S)) if S[j] >= s), len(S) - 1))
    t = (s - S[i - 1]) / max(S[i] - S[i - 1], 1e-9)
    return P[i - 1].lerp(P[i], t), (P[i] - P[i - 1]).normalized()


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


def skin_distance(g, W, bones=NEAR):
    """The stand-in's distance field (as sdf()) worked out per pixel from the world position W."""
    out = None
    for bone, a, b, r in CAPS:
        if bones is not None and bone not in bones:
            continue
        pa = vmath(g, "SUBTRACT", W, a)
        ab = b - a
        if ab.length < 1e-6:
            d = vmath(g, "LENGTH", pa, out="Value")
        else:
            t = vmath(g, "DOT_PRODUCT", pa, ab / ab.length_squared, out="Value")
            t = g.math("MINIMUM", g.math("MAXIMUM", t, 0.0), 1.0)
            q = vmath(g, "SUBTRACT", pa, vmath(g, "SCALE", ab, scale=t))
            d = vmath(g, "LENGTH", q, out="Value")
        d = g.math("SUBTRACT", d, r)
        out = d if out is None else g.math("MINIMUM", out, d)
    return out


def gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.06, soak=0.02):
    """Blood and gore drying on the bar where it went in: soaked and clotted from inside the body to `soak` out of
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


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood stuck to whatever went through it: wet dark red, black clots, pale shreds of fat
    and tissue."""
    mat, g = tk.new_material(name)
    P = mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))
    n1 = g.noise(30.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.014, 0.002, 0.002), (0.055, 0.007, 0.005))
    fat = g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=4.0, distortion=1.2, vector=P), 0.7, 0.74), 0.45)
    col = g.mix(fat, col, (0.085, 0.05, 0.035))
    clot = g.ramp(voronoi(g, P, 140.0), 0.25, 0.1)
    col = g.mix(g.math("MULTIPLY", clot, 0.6), col, (0.018, 0.002, 0.002))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.34, 0.6)
    height = g.math("ADD", g.math("MULTIPLY", n1, 0.6), g.math("MULTIPLY", fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


# ---------------------------------------------------------------- the crowbar's steel

def bar_steel(name, seed):
    """Forged hex steel gone mostly to rust: the old black enamel left in flaking patches along the middle of the
    bar, coarse rust in blooms, pits and the paint's broken edges, dark scale underneath, the corners rubbed smooth
    and dark-bright where hands held it, the ends hammered bare. Grime in the hollows, dust on top, dried blood and
    gore where it went in, spatter and drips below."""
    mat, g = tk.new_material(name)
    W = g.coords()
    P = mapping(g, W, loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))
    L = attr(g)
    s = g.separate(L)[2]
    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    # Dark forge scale, mottled
    tone = g.noise(6.0, 4.0, 0.55, P)
    col = g.mix(tone, (0.018, 0.0175, 0.017), (0.034, 0.032, 0.03))
    rgh = g.math("ADD", 0.55, g.math("MULTIPLY", tone, 0.15))
    met = 0.6
    height = g.math("MULTIPLY", g.noise(90.0, 5.0, 0.6, P), 0.15)
    # Old black enamel, flaked: kept in big patches along the middle of the bar, worn off toward both ends
    keep = g.math("MULTIPLY", g.ramp(s, 0.06, 0.16), g.ramp(s, 0.56, 0.44))
    fl = g.math("ADD", g.noise(14.0, 8.0, 0.7, P, 0.4), g.math("MULTIPLY", g.math("SUBTRACT", keep, 0.6), 0.26))
    chips = g.ramp(g.math("ADD", g.noise(48.0, 6.0, 0.7, P), g.math("MULTIPLY", g.noise(7.0, 3.0, vector=P), 0.3)),
                   0.83, 0.85)
    flake = g.math("MULTIPLY", g.ramp(fl, 0.5, 0.515), g.math("SUBTRACT", 1.0, chips))
    paint_col = g.mix(g.ramp(g.noise(20.0, 3.0, vector=P), 0.3, 0.7), (0.005, 0.005, 0.0055), (0.011, 0.011, 0.012))
    col = g.mix(flake, col, paint_col)
    rgh = g.mixf(flake, rgh, g.mixf(g.noise(30.0, 3.0, vector=P), 0.5, 0.68))
    met = g.mixf(flake, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", flake, 0.5))
    bare = g.math("SUBTRACT", 1.0, flake)
    # Rust on the bare steel: blooms and pits from the photo, and a rim creeping under the paint's broken edges
    p = tk.photo(g, "rust_coarse_01", 4.0, (seed * 0.31, 0.5 + seed * 0.17, seed * 0.23))
    rust_col = tk.grade(g, p["color"], 0.8, 0.46)
    rust_col = g.mix(g.ramp(tk._luma(g, p["color"]), 0.12, 0.03), rust_col, (0.03, 0.013, 0.006))
    blooms = g.ramp(g.noise(16.0, 8.0, 0.65, P, 0.5), 0.42, 0.52)
    pits = g.ramp(tk._luma(g, p["color"]), 0.16, 0.08)
    rim = g.math("MULTIPLY", g.ramp(fl, 0.47, 0.5), g.ramp(fl, 0.53, 0.5))
    rm = g.math("MULTIPLY", g.math("MAXIMUM", blooms, g.math("MULTIPLY", pits, 0.7)), bare)
    blisters = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.4, 0.8, 0.1)), 90.0), 0.16, 0.07),
                      g.ramp(g.noise(10.0, 4.0, vector=P), 0.5, 0.62))
    rm = g.math("MAXIMUM", rm, g.math("MULTIPLY", blisters, flake))
    rm = g.math("MAXIMUM", rm, g.math("MULTIPLY", rim, 0.9), clamp=True)
    col = g.mix(rm, col, rust_col)
    rgh = g.mixf(rm, rgh, 0.9)
    met = g.mixf(rm, met, 0.05)
    height = g.math("ADD", height, g.math("MULTIPLY", rm, p["height"]))
    # Corners and the hand-held stretch rubbed smooth: dark steel with a dull shine
    worn = g.math("MULTIPLY", g.ramp(g.edges(0.002), 0.1, 0.4), g.ramp(g.noise(25.0, 4.0, vector=P), 0.38, 0.58))
    grip = g.math("MULTIPLY", g.ramp(s, 0.1, 0.18), g.ramp(s, 0.36, 0.28))
    worn = g.math("MAXIMUM", worn, g.math("MULTIPLY", grip, g.ramp(g.noise(8.0, 4.0, vector=P), 0.5, 0.62)))
    worn = g.math("MULTIPLY", worn, 0.8)
    col = g.mix(worn, col, (0.045, 0.044, 0.042))
    rgh = g.mixf(worn, rgh, 0.36)
    met = g.mixf(worn, met, 0.85)
    # Scratches through it all
    sc = g.math("MULTIPLY", scratch_mask(g, P, 0.02), g.ramp(g.noise(3.0, 3.0, vector=P), 0.42, 0.66))
    col = g.mix(g.math("MULTIPLY", sc, 0.7), col, (0.1, 0.097, 0.093))
    rgh = g.mixf(sc, rgh, 0.4)
    met = g.mixf(sc, met, 0.9)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.4))
    # Grime in the hollows and dust settled on top
    dirt = g.math("MAXIMUM", tk._grime(g, 0.8), g.math("MULTIPLY", g.ramp(g.noise(5.0, 6.0, 0.6, P), 0.58, 0.7), 0.6))
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, g.mix(g.noise(9.0, vector=P), (0.015, 0.012, 0.009),
                                                            (0.038, 0.03, 0.021)))
    rgh = g.mixf(dirt, rgh, 0.88)
    met = g.mixf(dirt, met, 0.0)
    du = g.math("MULTIPLY", g.ramp(up, 0.3, 0.95), g.ramp(g.noise(8.0, 6.0, 0.6, P), 0.4, 0.7))
    col = g.mix(g.math("MULTIPLY", du, 0.25), col, (0.13, 0.115, 0.09))
    rgh = g.mixf(du, rgh, 0.95)
    met = g.mixf(du, met, 0.0)
    # Dried blood: soaked and clotted on the claw, spatter up the bend, a few drips and a smeared hand print below
    col, rgh, met, height = gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.12, soak=0.03)
    zw = g.separate(W)[2]
    drip = g.math("MULTIPLY", g.ramp(g.noise(1.0, 4.0, 0.6, mapping(g, P, scale=(150.0, 150.0, 5.0))), 0.6, 0.66),
                  g.ramp(zw, 0.9, 1.06))
    drip = g.math("MULTIPLY", drip, g.ramp(g.noise(4.0, 3.0, vector=P), 0.42, 0.55))
    smear = g.math("MULTIPLY", g.math("MULTIPLY", grip, g.ramp(g.noise(6.0, 6.0, 0.65, P, 1.0), 0.6, 0.67)), 0.85)
    bl = g.math("MAXIMUM", drip, smear)
    col = g.mix(bl, col, g.mix(g.noise(20.0, vector=P), (0.03, 0.005, 0.004), (0.07, 0.01, 0.006)))
    rgh = g.mixf(bl, rgh, 0.5)
    met = g.mixf(bl, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", bl, 0.2))
    col, rgh, met = tk._grit(g, col, rgh, met, 0.18)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, 0.4, 0.0015))


steel = bar_steel("CrowbarSteel", 3.0)
flesh = gore_flesh("CrowbarGore", 5.0)

# ---------------------------------------------------------------- the bar's shape

A = 0.0118  # the hex's apothem: 15/16-inch stock, 23.6 mm across the flats
CHAMFER = math.radians(6.0)
TILT = math.radians(7.0)  # the bar hangs this far out from straight down
SD = Vector((-math.sin(TILT), 0.12, -math.cos(TILT))).normalized()  # down the bar: down, out to the right, a bit back
E_UP = -SD
E_IN = orth(Vector((1.0, 0.0, 0.0)), SD)  # in the hook's plane, toward the body
W_ACROSS = E_UP.cross(E_IN).normalized()  # the plane's normal (across the bar's flats)
SHAFT = 0.42  # the straight from the gooseneck down to the pry end's bend
PRY = 0.062  # the pry end past its bend
PRY_BEND = math.radians(22.0)
BEND = math.radians(132.0)  # the gooseneck
CURL = math.radians(8.0)  # the claw curls on a little more
CLAW = 0.078
SINK = 0.04  # how far the claw tip goes past the stand-in


def hexagon(sx=1.0, sy=1.0, a=A):
    """A hexagon of apothem a with chamfered corners (12 points), flats facing +-x, squashed by (sx, sy)."""
    pts = []
    k30 = math.radians(30.0) - CHAMFER
    r = a / math.cos(k30)
    for k in range(6):
        c = math.radians(60.0 * k)
        for s in (-1, 1):
            t = c + s * k30
            pts.append((r * math.cos(t) * sx, r * math.sin(t) * sy))
    return pts


def path2d():
    """The bar's centerline in the hook's plane, (u toward the body, v up the bar), from the pry tip to the claw tip,
    and the stretch each point is on (pry, pbend, shaft, bend, claw)."""
    pts, kind = [], []
    ds = 0.002
    # The pry end: from its tip up to the bend, then the straight shaft up to the gooseneck (built from the top down)
    down = []
    p = Vector((0.0, 0.0))
    h = Vector((0.0, -1.0))
    n = int(SHAFT / 0.02)
    for k in range(n + 1):
        down.append((Vector((0.0, -SHAFT * k / n)), "shaft"))
    p = down[-1][0].copy()
    ang = 0.0
    m = 12
    for k in range(1, m + 1):  # the pry end's bend toward the body (the same side the claw curls to), over 3 cm
        ang = PRY_BEND * k / m
        h = Vector((math.sin(ang), -math.cos(ang)))
        p = p + h * (0.03 / m)
        down.append((p.copy(), "pbend"))
    rest = PRY - 0.03
    m = 8
    for k in range(1, m + 1):
        p = p + h * (rest / m)
        down.append((p.copy(), "pry"))
    for q, kd in reversed(down):
        pts.append(q)
        kind.append(kd)
    # The gooseneck: up from the shaft, over toward the body, tightening as it goes
    p = Vector((0.0, 0.0))
    phi = 0.0
    while phi < BEND:
        r = 0.064 + (0.046 - 0.064) * (phi / BEND)
        phi = min(BEND, phi + ds / r)
        p = p + Vector((math.sin(phi), math.cos(phi))) * ds
        pts.append(p.copy())
        kind.append("bend")
    # The claw: curling on a little, flattening and widening toward the split tip
    s = 0.0
    while s < CLAW - 1e-6:
        s += ds
        phi = BEND + CURL * (s / CLAW) ** 1.5
        p = p + Vector((math.sin(phi), math.cos(phi))) * ds
        pts.append(p.copy())
        kind.append("claw")
    return pts, kind


P2, KIND = path2d()


def place(origin):
    return [origin + E_IN * q.x + E_UP * q.y for q in P2]


# Hang it with the claw tip SINK past the skin and the claw crossing the skin under the lower ribs at the side
TORSO = ("Hips", "Spine2")
target = Vector((-0.15, 0.025, 1.13))
tip_dir = None
for _ in range(3):
    E = skin(target, Vector((1.0, 0.0, 0.0)), TORSO)
    origin = E - (E_IN * P2[-1].x + E_UP * P2[-1].y)
    pts = place(origin)
    tip_dir = (pts[-1] - pts[-2]).normalized()
    lo, hi = 0.0, 0.12
    for _ in range(40):
        mid = (lo + hi) / 2
        if sdf(pts[-1] + tip_dir * mid, TORSO) > -SINK:
            lo = mid
        else:
            hi = mid
    origin = origin + tip_dir * hi
    PATH = place(origin)
    cross = next(i for i in range(len(PATH)) if KIND[i] in ("bend", "claw") and sdf(PATH[i], TORSO) < 0.0)
    dz = PATH[cross].z - 1.13
    target = target - Vector((0.0, 0.0, dz))
CROSS = cross
print("[%s] claw crosses the skin at (%.3f, %.3f, %.3f), tip at (%.3f, %.3f, %.3f) (%.1f cm in), pry tip at "
      "(%.3f, %.3f, %.3f)" % ((SCRIPT,) + tuple(PATH[CROSS]) + tuple(PATH[-1]) + (-100 * sdf(PATH[-1], NEAR),)
                              + tuple(PATH[0])))


STEP = {"pry": 0.008, "pbend": 0.0075, "shaft": 0.09, "bend": 0.0062, "claw": 0.0068}


def thin(P, kind):
    """Rings every few mm on the bends, the claw and the pry end, every 9 cm on the straight shaft; the ends and
    where one stretch meets the next always kept."""
    keep = [0]
    since = 0.0
    for i in range(1, len(P)):
        since += (P[i] - P[i - 1]).length
        last = i == len(P) - 1
        joint = kind[i] != kind[i - 1]
        if last or joint or since >= STEP[kind[i]] - 1e-6:
            keep.append(i)
            since = 0.0
    return keep


S_PATH = arclen(PATH)
S_TOTAL = S_PATH[-1]
S_CLAW = S_PATH[next(i for i in range(len(KIND)) if KIND[i] == "claw")]
S_PRY = S_PATH[next(i for i in range(len(KIND)) if KIND[i] == "shaft")]


def squash(s):
    """How the hex is flattened (sx in the hook's plane, sy across it) at arc length s from the pry tip."""
    sx, sy = 1.0, 1.0
    if s < S_PRY:  # the pry end: flattened to a chisel, wider, sharpened at the very tip
        t = 1.0 - s / S_PRY
        sx = 1.0 - 0.7 * smoothstep(0.0, 0.85, t) - 0.18 * smoothstep(0.85, 1.0, t)
        sy = 1.0 + 0.32 * smoothstep(0.1, 0.9, t)
    elif s > S_CLAW - 0.03:  # the claw: flattening and widening from the end of the gooseneck
        t = (s - (S_CLAW - 0.03)) / (S_TOTAL - (S_CLAW - 0.03))
        sx = 1.0 - 0.55 * smoothstep(0.0, 0.8, t) - 0.15 * smoothstep(0.85, 1.0, t)
        sy = 1.0 + 0.45 * smoothstep(0.1, 0.8, t) - 0.25 * smoothstep(0.9, 1.0, t)
    return sx, sy


def bar():
    idx = thin(PATH, KIND)
    P = [PATH[i] for i in idx]
    S = [S_PATH[i] for i in idx]
    obj = sweep("Bar", P, W_ACROSS, lambda i: hexagon(*squash(S[i])), steel, S=S, smooth=24)
    print("[%s] bar: %d rings, %.3f m along (claw from %.3f, skin at %.3f)"
          % (SCRIPT, len(P), S_TOTAL, S_CLAW, S_PATH[CROSS]))
    return obj


def crust(name, s0, s1, thick, seed, step=0.004, cover=0.5):
    """Clots and shreds of flesh caked on the bar from s0 to s1 (arc length): the bar's own section grown by up to
    thick(t) (t 0 to 1 along it) where noise says so and sunk under the steel elsewhere (about `cover` of it shows),
    so it reads as lumps stuck to a bloodied bar, not a sleeve."""
    n = max(2, int(round((s1 - s0) / step)) + 1)
    P, S = [], []
    for k in range(n):
        s = s0 + (s1 - s0) * k / (n - 1)
        c, _ = point_at(PATH, S_PATH, s)
        P.append(c)
        S.append(s)
    T = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
    off = Vector((seed, 0.37 * seed, 0.71 * seed))

    def section(i):
        sx, sy = squash(S[i])
        amp = thick(i / (n - 1))
        X = W_ACROSS.cross(T[i]).normalized()
        out = []
        for x, y in hexagon(sx, sy, A):
            r = math.hypot(x, y)
            q = P[i] + X * x + W_ACROSS * y
            k = 0.5 + 0.5 * noise.noise(q * 120.0 + off) + 0.25 * noise.noise(q * 380.0 + off * 2.0)
            k = (k - (1.0 - cover)) / cover
            t = amp * k if k > 0.0 else -0.0015
            g = max(0.5, (r + t) / max(r, 1e-6))
            out.append((x * g, y * g))
        return out

    return sweep(name, P, W_ACROSS, section, flesh, S=S, smooth=60)


def gore_bits():
    """Clots and torn flesh caked on the claw where it goes in (thickest at the skin, thinning out up the claw and
    sunk into the wound), and a few more in the crook of the bend."""
    sc = S_PATH[CROSS]
    return [crust("Gore0", sc - 0.03, sc + 0.014, lambda t: 0.006 * smoothstep(0.0, 0.7, t) ** 0.7, 1.0, cover=0.74),
            crust("Gore1", sc - 0.062, sc - 0.03, lambda t: 0.0032 * math.sin(math.pi * t) ** 0.6, 4.0, cover=0.45)]


# ---------------------------------------------------------------- export, fit report and previews

def report(parts):
    total = 0
    for o in parts:
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        lo = Vector([min(p[k] for p in pts) for k in range(3)])
        hi = Vector([max(p[k] for p in pts) for k in range(3)])
        tris = sum(len(f.vertices) - 2 for f in o.data.polygons)
        total += tris
        print("[%s] %-8s %4d tris, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f), deepest %.1f cm in"
              % (SCRIPT, o.name, tris, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z, -100 * min(sdf(p) for p in pts)))
    print("[%s] %d triangles before triangulating" % (SCRIPT, total))


def clearance():
    """How far the bar stays off the body outside the wound: the gooseneck and shaft against the torso and the
    right thigh, and the shaft against the right arm."""
    out = [i for i in range(len(PATH)) if KIND[i] != "claw"]
    for bones in (("Hips", "Spine2"), ("RightUpLeg",), ("RightArm", "RightForeArm")):
        d = min(sdf(PATH[i], bones) for i in out) - A * 1.15
        i = min(out, key=lambda k: sdf(PATH[k], bones))
        print("[%s] clearance from %s: %.1f cm at (%.3f, %.3f, %.3f)" % ((SCRIPT, "+".join(bones), d * 100)
                                                                        + tuple(PATH[i])))


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


pieces = [bar()] + gore_bits()
for p in pieces:
    zk.on(p, "Spine1", "Crowbar")
report(pieces)
clearance()
export(pieces)
hook = PATH[CROSS] + Vector((-0.04, 0.0, 0.03))
zk.previews(SCRIPT, PREVIEWS, Vector((-0.16, 0.02, 0.95)), distance=1.5)
close_up("hook", hook, (-0.5, -1.0, 0.25), distance=0.38)
close_up("hook_back", hook, (-0.6, 1.0, 0.3), distance=0.38)
close_up("pry", PATH[0] + Vector((0.0, 0.0, 0.04)), (-0.6, -1.0, 0.2), distance=0.3)
print("[%s] done" % SCRIPT)
