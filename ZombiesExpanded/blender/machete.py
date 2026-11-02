"""Machete: an 18-inch Latin machete chopped into the top-left of the skull and stuck there, the blade sunk deep on a
slant so its far half is buried in the head, the handle standing out to the left and up. Black-coated carbon steel
worn through to bare metal and rust, the edge ground bright and nicked, scratched, and filthy with dried blood and
gore where it goes in; riveted walnut scales, dark with grease and grime, the black tang between them, a lanyard
hole at the butt.

The buried part of the blade is cut away 4 cm inside the stand-in's head (it can never show). One part on the Head
bone, Head#Machete.

    blender -b --factory-startup --python machete.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "Machete", "machete"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
SK = zk.joe()
LOCAL = "rl_local"  # each vertex's place in its part's own frame (z along the part), for the materials
EDGE = "rl_edge"  # blades: (u across from spine 0 to edge 1, side +-1, v along)


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


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def sdf(p, bones=None):
    """Distance from p to the stand-in's surface (its hit boxes), negative inside."""
    p = Vector(p)
    return min(seg_distance(p, a, b) - r for bone, a, b, r in CAPS if bones is None or bone in bones)


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


def frame(origin, z_axis, x_hint):
    """A placement: local z along z_axis, local x toward x_hint (squared up), local y = z cross x."""
    Z = Vector(z_axis).normalized()
    X = Vector(x_hint)
    X = (X - Z * X.dot(Z)).normalized()
    Y = Z.cross(X)
    m = Matrix((X, Y, Z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


# ---------------------------------------------------------------- mesh helpers

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def build(name, verts, faces, mat, M=None, smooth=40, extra=None):
    """A closed mesh from local vertices and faces, placed by M. LOCAL keeps each vertex's local position;
    extra = {attribute: [vector per vertex]} adds more."""
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        if len(set(f)) < 3:
            continue
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    me = obj.data
    layers = {LOCAL: [Vector(v) for v in verts]}
    layers.update(extra or {})
    for key, values in layers.items():
        a = me.attributes.new(key, "FLOAT_VECTOR", "POINT")
        for i in range(len(me.vertices)):
            a.data[i].vector = values[i]
    if M is not None:
        me.transform(M)
    me.update()
    return tk.smooth(obj, smooth)


def ring(z, rx, ry=None, n=8, phase=0.0, fn=None, cx=0.0, cy=0.0):
    """A closed ring of n points round the local z axis at height z (an ellipse; fn(angle) scales the radius)."""
    ry = rx if ry is None else ry
    pts = []
    for k in range(n):
        t = phase + 2 * math.pi * k / n
        s = fn(t) if fn else 1.0
        pts.append(Vector((cx + rx * s * math.cos(t), cy + ry * s * math.sin(t), z)))
    return pts


def loft(name, rings, mat, M=None, caps=(True, True), smooth=40, extra=None):
    """Rings (lists of local points, all the same count; a single point makes a pointed end) joined into a solid."""
    verts, faces, idx = [], [], []
    for r in rings:
        idx.append(list(range(len(verts), len(verts) + len(r))))
        verts.extend(Vector(p) for p in r)
    for a, b in zip(idx, idx[1:]):
        if len(a) == 1:
            n = len(b)
            faces += [(a[0], b[(k + 1) % n], b[k]) for k in range(n)]
        elif len(b) == 1:
            n = len(a)
            faces += [(a[k], a[(k + 1) % n], b[0]) for k in range(n)]
        else:
            n = len(a)
            faces += [(a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]) for k in range(n)]
    if caps[0] and len(idx[0]) > 2:
        faces.append(tuple(reversed(idx[0])))
    if caps[1] and len(idx[-1]) > 2:
        faces.append(tuple(idx[-1]))
    return build(name, verts, faces, mat, M, smooth, extra)


def lathe(name, profile, n, mat, M=None, fn=None, smooth=40, phase=0.0):
    """Turned along local z: profile [(z, r), ...] (r 0 at an end makes a point); fn(angle, z) scales the radius."""
    rings = []
    for z, r in profile:
        if r <= 0.0:
            rings.append([Vector((0.0, 0.0, z))])
        else:
            rings.append(ring(z, r, n=n, phase=phase, fn=(lambda t, z=z: fn(t, z)) if fn else None))
    return loft(name, rings, mat, M, smooth=smooth)


def slab(name, outline, thick, us, vs, mat, M=None, smooth=30, offset=None):
    """A blade: outline(u, v) -> local (x, z) with u across (0 spine to 1 edge) and v along; thick(u, v) its
    thickness (local y), offset(u, v) shifts its middle along y. EDGE keeps (u, side, v)."""
    verts, edge, top, bot = [], [], {}, {}
    for j, v in enumerate(vs):
        for i, u in enumerate(us):
            x, z = outline(u, v)
            t = max(thick(u, v), 0.0003) / 2
            c = offset(u, v) if offset else 0.0
            top[i, j] = len(verts)
            verts.append(Vector((x, c + t, z)))
            edge.append(Vector((u, 1.0, v)))
            bot[i, j] = len(verts)
            verts.append(Vector((x, c - t, z)))
            edge.append(Vector((u, -1.0, v)))
    I, J = len(us) - 1, len(vs) - 1
    faces = []
    for j in range(J):
        for i in range(I):
            faces.append((top[i, j], top[i + 1, j], top[i + 1, j + 1], top[i, j + 1]))
            faces.append((bot[i, j], bot[i, j + 1], bot[i + 1, j + 1], bot[i + 1, j]))
        for i in (0, I):
            faces.append((top[i, j], top[i, j + 1], bot[i, j + 1], bot[i, j]))
    for i in range(I):
        for j in (0, J):
            faces.append((top[i, j], bot[i, j], bot[i + 1, j], top[i + 1, j]))
    return build(name, verts, faces, mat, M, smooth, {EDGE: edge})


def capsule_mesh(a, b, r, segments=24, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=r)
    half = (b - a).length / 2
    for v in bm.verts:
        v.co.z += half if v.co.z > 0 else -half
    d = (b - a).normalized() if (b - a).length > 1e-6 else Vector((0, 0, 1))
    bm.transform(Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4())
    me = bpy.data.meshes.new("Cutter")
    bm.to_mesh(me)
    bm.free()
    return tk.link(bpy.data.objects.new("Cutter", me))


def bury(obj, depth=0.04, bones=None):
    """Cuts away what lies deeper than `depth` inside the stand-in (it can never show), and any loose bits left
    wholly inside."""
    for bone, a, b, r in CAPS:
        if bones is not None and bone not in bones:
            continue
        if all(seg_distance(obj.matrix_world @ v.co, a, b) > r - depth for v in obj.data.vertices):
            continue
        cutter = capsule_mesh(a, b, r - depth)
        cutter.data.materials.append(obj.data.materials[0])
        mod = obj.modifiers.new("Bury", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.material_mode = "INDEX"
        mod.object = cutter
        tk.apply_modifiers(obj)
        bpy.data.objects.remove(cutter, do_unlink=True)
    keep = [m for m in obj.data.materials if m is not None][0]
    if len(obj.data.materials) > 1:
        obj.data.materials.clear()
        obj.data.materials.append(keep)
        for poly in obj.data.polygons:
            poly.material_index = 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen = set()
    for v in bm.verts:
        if v in seen:
            continue
        island, stack = [], [v]
        seen.add(v)
        while stack:
            w = stack.pop()
            island.append(w)
            for e in w.link_edges:
                o = e.other_vert(w)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        if max(sdf(obj.matrix_world @ w.co) for w in island) < 0.0:
            bmesh.ops.delete(bm, geom=island, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    return tk.smooth(obj, 30)


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


def lines(g, vec, scale, rot, loc, width, seg=0.0):
    """Thin scratch lines: contours of stretched noise, broken into short runs when seg (a noise scale) is given."""
    n = g.noise(1.0, detail=1.0, roughness=0.3, vector=mapping(g, vec, scale, rot, loc))
    ln = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, width, False))
    if seg:
        ln = g.math("MULTIPLY", ln, g.ramp(g.noise(seg, detail=2.0, vector=mapping(g, vec, loc=loc)), 0.5, 0.58))
    return ln


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


def skin_distance(g, W):
    """The stand-in's distance field (as sdf()) worked out per pixel from the world position W."""
    out = None
    for bone, a, b, r in CAPS:
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
    """Blood and gore drying on the object where it went in: soaked and clotted from inside the body to `soak` out
    of the stand-in, then runs, smears and spatter thinning out to `reach`."""
    d = skin_distance(g, W)
    ragged = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(35.0, 6.0, 0.7, P), 0.5), 0.6 * soak)
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
    bc = g.mix(fresh, (0.05, 0.008, 0.005), (0.13, 0.015, 0.009))
    bc = g.mix(clot, bc, (0.022, 0.005, 0.004))
    tissue = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.5, 0.9, 0.2)), 70.0), 0.14, 0.06), clot)
    bc = g.mix(g.math("MULTIPLY", tissue, 0.8), bc, (0.15, 0.07, 0.055))
    col = g.mix(b, col, bc)
    rgh = g.mixf(b, rgh, g.mixf(clot, g.mixf(fresh, 0.62, 0.4), 0.25))
    met = g.mixf(b, met, 0.0)
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", b, 0.3), g.math("MULTIPLY", clot, 1.2)))
    return col, rgh, met, height


def rust(g, P, col, rgh, met, height, amount=0.5, scale=1.0, seed=0.0):
    """Rust spots and patches from the rust photo, pitted, on bare steel."""
    p = tk.photo(g, "rust_coarse_01", 5.0 * scale, (seed, 0.3, 0.7))
    m = g.ramp(g.noise(9.0 * scale, 8.0, 0.7, mapping(g, P, loc=(seed, 0.0, 0.0)), 0.4), 0.68 - 0.18 * amount,
               0.72 - 0.18 * amount)
    pits = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(seed, 1.0, 0.0)), 260.0 * scale), 0.12, 0.05),
                  g.ramp(g.noise(5.0, 3.0, vector=P), 0.45, 0.6))
    m = g.math("MAXIMUM", m, g.math("MULTIPLY", pits, amount * 1.5), clamp=True)
    rc = tk.grade(g, p["color"], 0.8, 0.75)
    col = g.mix(m, col, rc)
    rgh = g.mixf(m, rgh, 0.85)
    met = g.mixf(m, met, 0.1)
    height = g.math("ADD", height, g.math("MULTIPLY", m, g.math("MULTIPLY", p["height"], 0.8)))
    return col, rgh, met, height


def wear(name, paint, rough=0.4, metal=0.0, base=None, post=None, seed=0.0, tone=0.2, scratches=0.5,
         scratch_col=(0.6, 0.58, 0.52), scratch_metal=0.0, dark_scratches=0.3, scuffs=0.4, scuff_col=None, edges=0.4,
         edge_col=None, edge_metal=None, dirt=0.5, dirt_set="rust_coarse_01", dirt_scale=3.0,
         dirt_range=(0.14, 0.04), grime=0.6, dust=0.3, specks=0.5, blood=0.0, grease=0.0, bump=0.3, grain=0.15,
         grain_scale=90.0, line_width=0.03, dirt_col=((0.04, 0.032, 0.024), (0.12, 0.095, 0.065))):
    """Worn surfaces (hard_hat.py's recipe): a base (flat `paint` with uneven tone, or base(g, W, P) -> col, rough,
    height), rubbed scuffs, scratches, worn edges, photo-patterned dirt and crease grime, grease, dust, specks,
    spattered blood, then post(g, W, P, col, rough, metal, height) for gore and rust. Amounts 0-1."""
    mat, g = tk.new_material(name)
    W = g.coords()
    S = (seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29)
    P = mapping(g, W, loc=S)

    def nz(scale, detail=4.0, r=0.55, dist=0.0):
        return g.noise(scale, detail=detail, roughness=r, vector=P, distortion=dist)

    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    if base:
        col, rgh, height = base(g, W, P)
    else:
        col = g.mix(g.math("MULTIPLY", nz(5.0, 3.0), tone * 2.0), paint, tk._darker(g, paint, 0.7))
        rgh = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", nz(14.0, 3.0), 0.5), 0.16))
        height = g.math("MULTIPLY", nz(grain_scale, 6.0, 0.6), grain)
    met = metal
    if scuffs:
        sm = g.math("MULTIPLY", g.ramp(nz(11.0, 6.0, 0.7, 1.2), 0.58, 0.72), scuffs)
        streak = lines(g, P, (30.0, 30.0, 8.0), (0.4, 1.1, 0.3), (0.5, 0.2, 0.9), 0.08)
        sm = g.math("MULTIPLY", sm, g.math("ADD", 0.45, g.math("MULTIPLY", streak, 0.55)))
        col = g.mix(g.math("MULTIPLY", sm, 0.75), col, scuff_col or tk.grade(g, col, 0.45, 1.45))
        rgh = g.mixf(sm, rgh, min(1.0, rough + 0.3))
    if scratches:
        sc = scratch_mask(g, P, line_width)
        dens = g.ramp(nz(3.0, 3.0), 0.42, 0.66)
        sc = g.math("MULTIPLY", g.math("MULTIPLY", sc, dens), scratches, clamp=True)
        dark = g.math("MULTIPLY", g.ramp(nz(7.0, 3.0), 0.48, 0.56), dark_scratches)
        scol = g.mix(dark, scratch_col, (0.05, 0.04, 0.03))
        col = g.mix(sc, col, scol)
        rgh = g.mixf(sc, rgh, 0.6 if scratch_metal < 0.5 else 0.3)
        met = g.mixf(sc, met, scratch_metal)
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", sc, 0.6))
    if edges:
        wm = g.math("MULTIPLY", g.ramp(g.edges(0.003), 0.06, 0.3), g.ramp(nz(30.0, 4.0), 0.36, 0.55))
        wm = g.math("MULTIPLY", wm, edges)
        col = g.mix(wm, col, edge_col or scratch_col)
        rgh = g.mixf(wm, rgh, 0.5)
        met = g.mixf(wm, met, scratch_metal if edge_metal is None else edge_metal)
    p = tk.photo(g, dirt_set, dirt_scale, (S[0] * 0.3, 0.5, S[2] * 0.2))
    dm = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), dirt_range[0], dirt_range[1]), dirt)
    dm = g.math("MAXIMUM", dm, tk._grime(g, grime), clamp=True)
    col = g.mix(g.math("MULTIPLY", dm, 0.88), col, g.mix(nz(9.0), dirt_col[0], dirt_col[1]))
    rgh = g.mixf(dm, rgh, 0.85)
    met = g.mixf(dm, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", dm, 0.2))
    if grease:
        gm = g.math("MULTIPLY", g.ramp(nz(5.0, 6.0, 0.6, 1.0), 0.56, 0.68), grease)
        col = g.mix(gm, col, tk._darker(g, col, 0.35))
        rgh = g.mixf(gm, rgh, 0.2)
    if dust:
        du = g.math("MULTIPLY", g.ramp(up, 0.25, 0.95), g.ramp(nz(8.0, 6.0, 0.6), 0.35, 0.65))
        du = g.math("MULTIPLY", du, dust)
        col = g.mix(du, col, (0.3, 0.26, 0.21))
        rgh = g.mixf(du, rgh, 0.95)
        met = g.mixf(du, met, 0.0)
    if specks:
        spots = g.ramp(voronoi(g, P, 150.0), 0.16, 0.07)
        sp = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.62)), specks)
        col = g.mix(sp, col, (0.025, 0.02, 0.015))
        rgh = g.mixf(sp, rgh, 0.9)
    if blood:
        reg = g.ramp(nz(1.6, 5.0, 0.6, 0.6), 0.5, 0.64)
        drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 60.0), 0.16, 0.05),
                       g.ramp(nz(25.0, 4.0), 0.42, 0.6))
        smear = g.ramp(nz(9.0, 8.0, 0.7, 1.5), 0.58, 0.65)
        bm_ = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", drops, smear), reg), blood, clamp=True)
        col = g.mix(bm_, col, g.mix(nz(20.0), (0.045, 0.006, 0.004), (0.11, 0.013, 0.008)))
        rgh = g.mixf(bm_, rgh, 0.45)
        met = g.mixf(bm_, met, 0.0)
    if post:
        col, rgh, met, height = post(g, W, P, col, rgh, met, height)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, bump, 0.0015))


# ---------------------------------------------------------------- export, fit report and previews

def export(pieces):
    """Bakes and writes the model (the stand-in kept out of the bake), then reports each part's size and how deep
    it sits in the stand-in."""
    for o in BODY:
        o.hide_render = True
    parts = zk.export(NAME, pieces, ASSETS, size=512)
    for o in BODY:
        o.hide_render = False
    total = 0
    for part in parts:
        pts = [part.matrix_world @ v.co for v in part.data.vertices]
        lo = Vector([min(p[k] for p in pts) for k in range(3)])
        hi = Vector([max(p[k] for p in pts) for k in range(3)])
        tris = sum(len(f.vertices) - 2 for f in part.data.polygons)
        total += tris
        d = [sdf(p) for p in pts]
        print("[%s] %s: %d triangles, bounds (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f), deepest %.1f cm inside the "
              "stand-in, farthest %.1f cm out" % (NAME, part.name, tris, lo.x, lo.y, lo.z, hi.x, hi.y, hi.z,
                                                  -100 * min(d), 100 * max(d)))
    print("[%s] %d triangles in all" % (NAME, total))
    return parts


def close_up(view, direction, target, distance=0.5, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)



# ---------------------------------------------------------------- the machete

D_IN = Vector((-0.82, -0.1, -0.56)).normalized()  # chopped in from the upper left, down and across the skull
AIM = Vector((0.0, 0.03, 1.79))  # a point on the blade's middle line, inside the head
EXPOSED = 0.17  # blade showing along its middle between the handle and the stand-in's head
MID = -0.017  # the blade's middle line in local x (spine at +0.006, edge at -0.04)
ENTRY = skin(AIM, D_IN, ("Head",))
ORIGIN = ENTRY - D_IN * EXPOSED
M = frame(ORIGIN, -D_IN, (-0.62, -0.2, 0.8)) @ Matrix.Translation((-MID, 0.0, 0.0))  # local x up toward the spine
BLADE = 0.27  # modeled length: it ends well inside the head, so it never comes out the other side
HANDLE0, HANDLE1 = 0.0, 0.135


def spine_x(v):
    return 0.0062 - 0.002 * v


def edge_x(v):
    # Narrow at the handle, widening toward the belly
    return -0.034 - 0.013 * smoothstep(0.0, 1.0, v)


def blade_outline(u, v):
    return spine_x(v) + (edge_x(v) - spine_x(v)) * u, -0.004 - BLADE * v


def blade_thick(u, v):
    ts = 0.0026 - 0.0004 * v
    if u <= 0.45:
        return ts
    if u <= 0.9:
        return ts * (1.0 - 0.82 * (u - 0.45) / 0.45)
    return ts * 0.18 * (1.0 - (u - 0.9) / 0.1) + 0.00006


def coated(g, W, P):
    """Black powder coat, satin, faintly mottled; the edge bevel ground to bright steel."""
    u = g.separate(attr(g, EDGE))[0]
    col = g.mix(g.ramp(g.noise(18.0, 4.0, 0.6, P), 0.3, 0.7), (0.016, 0.016, 0.017), (0.032, 0.031, 0.03))
    rgh = g.math("ADD", 0.5, g.math("MULTIPLY", g.noise(30.0, 3.0, vector=P), 0.12))
    height = g.math("MULTIPLY", g.noise(220.0, 4.0, 0.6, P), 0.15)
    # The coat worn off the flats toward the edge, in ragged patches, and the bright ground bevel
    worn = g.math("MULTIPLY", g.ramp(u, 0.7, 0.88), g.ramp(g.noise(16.0, 6.0, 0.7, P, 0.6), 0.62, 0.46))
    bare = g.mix(g.ramp(g.noise(60.0, 3.0, vector=P), 0.3, 0.7), (0.19, 0.19, 0.19), (0.29, 0.29, 0.29))
    col = g.mix(worn, col, bare)
    rgh = g.mixf(worn, rgh, 0.36)
    bev = g.ramp(u, 0.91, 0.95)
    col = g.mix(bev, col, (0.42, 0.42, 0.42))
    rgh = g.mixf(bev, rgh, 0.25)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", worn, 0.3))
    # Nicks in the edge
    nick = g.math("MULTIPLY", g.ramp(u, 0.93, 0.99), g.ramp(g.noise(140.0, 2.0, vector=P), 0.62, 0.68))
    col = g.mix(nick, col, (0.08, 0.075, 0.07))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", nick, 1.0))
    return col, rgh, height


def blade_post(g, W, P, col, rgh, met, height):
    u = g.separate(attr(g, EDGE))[0]
    bare = g.ramp(u, 0.75, 0.92)
    met = g.mixf(bare, met, 1.0)
    col, rgh, met, height = rust(g, P, col, rgh, met, height, amount=0.5, scale=1.2, seed=2.7)
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.07, soak=0.024)


blade_mat = wear("MacheteBlade", (0.02, 0.02, 0.02), rough=0.5, metal=0.0, base=coated, post=blade_post, seed=11.0,
                 scratches=0.55, scratch_col=(0.26, 0.26, 0.26), scratch_metal=1.0, dark_scratches=0.15, scuffs=0.5,
                 scuff_col=(0.045, 0.044, 0.042), edges=0.0, dirt=0.45, dirt_range=(0.15, 0.05), grime=0.8, dust=0.05,
                 specks=0.6, blood=0.5, bump=0.3, line_width=0.03,
                 dirt_col=((0.018, 0.015, 0.011), (0.05, 0.04, 0.028)))


def walnut(g, W, P):
    """Walnut scales: dark brown with the grain running along the handle, oiled and gone darker with grease."""
    L = attr(g)
    Q = mapping(g, L, loc=(0.37, 0.11, 0.0))
    fib = g.noise(1.0, 6.0, 0.6, mapping(g, Q, scale=(420.0, 420.0, 14.0)))
    w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SAW")
    g._in(w, "Scale", 110.0)
    g._in(w, "Distortion", 7.0)
    g._in(w, "Detail", 3.0)
    g._in(w, "Detail Scale", 1.2)
    g.links.new(mapping(g, Q, scale=(1.0, 0.7, 0.06)), w.inputs["Vector"])
    rings = g.ramp(tk._sock(w.outputs, "Fac"), 0.55, 0.95)
    col = g.mix(fib, (0.04, 0.019, 0.009), (0.075, 0.04, 0.019))
    col = g.mix(g.math("MULTIPLY", rings, 0.7), col, (0.02, 0.01, 0.005))
    rgh = g.math("ADD", 0.48, g.math("MULTIPLY", fib, 0.15))
    height = g.math("ADD", g.math("MULTIPLY", fib, 0.3), g.math("MULTIPLY", rings, 0.2))
    return col, rgh, height


def handle_post(g, W, P, col, rgh, met, height):
    """The black tang between the scales along the top and bottom, the lanyard hole, gore spatter."""
    L = attr(g)
    x, y, z = g.separate(L)
    t = g.ramp(g.math("ABSOLUTE", y), 0.0017, 0.0012)
    col = g.mix(t, col, (0.03, 0.03, 0.03))
    rgh = g.mixf(t, rgh, 0.45)
    met = g.mixf(t, met, 0.6)
    seam = band(g, g.math("ABSOLUTE", y), 0.0012, 0.002, 0.0002)
    col = g.mix(g.math("MULTIPLY", seam, 0.8), col, (0.012, 0.009, 0.006))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", seam, 0.6))
    dx = g.math("SUBTRACT", x, -0.003)
    dz = g.math("SUBTRACT", z, HANDLE1 - 0.014)
    hole = g.ramp(g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dz, dz))), 0.0032, 0.0026)
    col = g.mix(hole, col, (0.008, 0.006, 0.005))
    rgh = g.mixf(hole, rgh, 0.9)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", hole, 2.0))
    return gore(g, W, P, col, rgh, met, height, amount=0.8, reach=0.2, soak=0.004)


wood_mat = wear("MacheteHandle", (0.05, 0.025, 0.012), rough=0.5, base=walnut, post=handle_post, seed=12.0,
                scratches=0.5, scratch_col=(0.13, 0.08, 0.045), dark_scratches=0.5, scuffs=0.4,
                scuff_col=(0.1, 0.06, 0.035), edges=0.6, edge_col=(0.15, 0.095, 0.055), dirt=0.6,
                dirt_range=(0.15, 0.05), grime=1.0, dust=0.1, specks=0.6, grease=0.7, blood=0.5, bump=0.4,
                dirt_col=((0.025, 0.017, 0.011), (0.06, 0.042, 0.027)))
brass = wear("MacheteRivet", (0.3, 0.2, 0.075), rough=0.4, metal=1.0, seed=13.0, tone=0.3, scratches=0.4,
             scratch_col=(0.45, 0.33, 0.14), scratch_metal=1.0, scuffs=0.0, edges=0.0, dirt=0.7,
             dirt_range=(0.18, 0.05), grime=1.0, dust=0.0, specks=0.5, bump=0.2,
             dirt_col=((0.03, 0.03, 0.015), (0.07, 0.07, 0.04)))


def blade():
    us = [0.0, 0.04, 0.45, 0.68, 0.9, 1.0]
    vs = [j / 18 for j in range(19)]
    obj = slab("Blade", blade_outline, blade_thick, us, vs, blade_mat, M, smooth=35)
    return bury(obj, 0.04, ("Head",))


def handle_ring(z, n=14):
    """The handle's section: an oval, a lip under the front for the fingers, swelling to a hooked butt."""
    t = (z - HANDLE0) / (HANDLE1 - HANDLE0)
    lip = 0.0045 * math.exp(-((t - 0.05) / 0.06) ** 2)
    hook = 0.0075 * smoothstep(0.72, 1.0, t)
    top = 0.0128 + 0.0012 * math.sin(math.pi * t) - 0.0015 * smoothstep(0.85, 1.0, t)
    bottom = -0.0128 - 0.0008 * math.sin(math.pi * t) - lip - hook
    hw = 0.0105 + 0.0012 * math.sin(math.pi * t)
    cx, rx = (top + bottom) / 2, (top - bottom) / 2
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        # a squarish oval: flatter on the scale faces
        f = (abs(c) ** 2.6 + abs(s) ** 2.6) ** (-1 / 2.6)
        pts.append(Vector((cx + rx * c * f, hw * s * f, z)))
    return pts


def handle():
    zs = [0.004, 0.016, 0.03, 0.05, 0.072, 0.094, 0.112, 0.124, 0.131]
    first = handle_ring(-0.006)
    c0 = sum(first, Vector()) / len(first)
    rings = [[c0 + (p - c0) * 0.82 for p in first]] + [handle_ring(z) for z in zs]
    last = handle_ring(HANDLE1)
    c = sum(last, Vector()) / len(last)
    rings.append([c + (p - c) * 0.75 for p in last])
    rings.append([c + (p - c) * 0.3 + Vector((0.0, 0.0, 0.002)) for p in last])
    return loft("Handle", rings, wood_mat, M, smooth=42)


def rivets():
    out = []
    for k, z in enumerate((0.024, 0.064, 0.104)):
        hw = 0.0105 + 0.0012 * math.sin(math.pi * z / HANDLE1)
        prof = [(-hw - 0.0004, 0.0), (-hw - 0.0003, 0.0022), (-hw + 0.001, 0.0032), (hw - 0.001, 0.0032),
                (hw + 0.0003, 0.0022), (hw + 0.0004, 0.0)]
        local = Matrix.Translation((-0.0005, 0.0, z)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        out.append(lathe("Rivet%d" % k, prof, 10, brass, M @ local, smooth=60))
    return out


pieces = [blade(), handle()] + rivets()
for p in pieces:
    zk.on(p, "Head", "Machete")
print("[%s] enters the stand-in at (%.3f, %.3f, %.3f); handle starts at (%.3f, %.3f, %.3f)" % (
    NAME, ENTRY.x, ENTRY.y, ENTRY.z, ORIGIN.x, ORIGIN.y, ORIGIN.z))
export(pieces)
focus = Vector((0.08, 0.03, 1.8))
zk.previews(SCRIPT, PREVIEWS, focus, distance=1.0)
close_up("close", (0.5, -1.0, 0.35), focus, distance=0.55)
close_up("top", (0.6, 0.3, 1.0), focus, distance=0.55)
close_up("left", (1.0, 0.1, 0.1), focus, distance=0.55)
print("[%s] done" % SCRIPT)
