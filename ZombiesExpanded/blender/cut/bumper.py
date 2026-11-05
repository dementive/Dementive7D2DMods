"""Bumper (rare showpiece): hit by a pickup and kept part of it. The torn-off half of an old chrome bumper (its
corner and part of its face, the C-section with a raised bead down the middle and a black rubber impact strip) is
wedged in under the right ribs from behind and outside, its ripped end buried in the body; out of the wound it is
bent back along the zombie's right side, behind the hanging arm, and its corner wraps in behind him, about 50 cm out
and back in all, twisted and drooping, dented and crumpled where it bent. The chrome is hazed, pitted with rust
blooms and flaking off in sheets to rusty steel (bronze under-plate at the edges), mud and tar thrown up along the
bottom; a mounting bracket is still bolted inside near the corner, bent and torn off. Blood and torn flesh at the
wound, run back along the bottom flange.

The torn end sinks 4.5 cm past the stand-in. One part on Spine1: "Spine1#Bumper".

    blender -b --factory-startup --python bumper.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "Bumper", "bumper"
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
    bc = g.mix(fresh, (0.034, 0.006, 0.004), (0.085, 0.011, 0.007))
    bc = g.mix(clot, bc, (0.017, 0.004, 0.003))
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
    parts = zk.export(NAME, pieces, ASSETS, size=1024)
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




# ---------------------------------------------------------------- sticks, tubes and broken wood

def jagged(n, long=0.03, base=0.002, seed=1.0, top=None):
    """Spike lengths round a snapped end: splinters torn along the grain (top: only on the side round angle `top`)."""
    rnd = [noise.noise(Vector((seed, k * 0.71, 0.3))) for k in range(n)]
    out = []
    for j in range(n):
        a = 2 * math.pi * j / n
        if top is None:
            s = base + long * max(0.0, math.sin(2.1 * j + seed)) ** 3 + 0.005 * abs(rnd[j])
        else:
            s = base + long * max(0.0, math.cos(a - top)) ** 2 * (0.6 + 0.8 * abs(rnd[j]))
        out.append(s)
    return out


def stick(name, z0, z1, r, mat, end_mat, M, sides=10, mid=(), jag0=None, jag1=None, phase=0.0, smooth=50):
    """A round wooden shaft along local z from z0 to z1 (radius r), placed by M. jag0 / jag1: spike lengths (one per
    side) for a snapped end, whose torn faces get end_mat; None leaves a sawn end. LOCAL = (x, y, z)."""
    bm = bmesh.new()
    loc = []

    def ring(z, rf, spikes=None, sign=1.0):
        out = []
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides
            rr = r * rf(j)
            p = Vector((rr * math.cos(a), rr * math.sin(a), z + (sign * spikes[j] if spikes else 0.0)))
            out.append(bm.verts.new(p))
            loc.append(p)
        return out

    def wobble(z):
        return lambda j: 1.0 + 0.015 * math.sin(3.0 * j + z * 37.0)

    rings, band = [], []
    if jag0:
        rings.append(ring(z0, lambda j: 0.84 - 0.25 * jag0[j] / 0.035, jag0, -1.0))
        band.append(1)
    for k, z in enumerate([z0] + list(mid) + [z1]):
        rings.append(ring(z, wobble(z)))
        band.append(0)
    if jag1:
        band[-1] = 1
        rings.append(ring(z1, lambda j: 0.84 - 0.25 * jag1[j] / 0.035, jag1, 1.0))
    for i in range(len(rings) - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            f = bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
            f.material_index = band[i]
    for end, ring_, jag, z, sign in ((0, rings[0], jag0, z0, -1.0), (1, rings[-1], jag1, z1, 1.0)):
        if jag:
            c = Vector((0.15 * r, -0.1 * r, z + sign * 0.003))
            cv = bm.verts.new(c)
            loc.append(c)
            for j in range(sides):
                f = bm.faces.new((ring_[j], ring_[(j + 1) % sides], cv))
                f.material_index = 1
        else:
            f = bm.faces.new(list(ring_))
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    obj.data.materials.append(end_mat)
    a = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for i, p in enumerate(loc):
        a.data[i].vector = p
    obj.data.transform(M)
    obj.data.update()
    return tk.smooth(obj, smooth)


def frames(P, x0):
    """Tangents and twist-free cross-section axes along a polyline, starting from x0."""
    n = len(P)
    T = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
    X, ref = [], Vector(x0)
    for t in T:
        x = (ref - t * ref.dot(t)).normalized()
        X.append(x)
        ref = x
    return T, X, [t.cross(x) for t, x in zip(T, X)]


def tube(name, pts, radius, mat, M=None, x0=(1.0, 0.0, 0.0), sides=4, smooth=30, phase=0.0):
    """A thin tube or ribbon along local points; radius: (rx, ry) per point (rx along x0's direction). LOCAL = (x, y,
    distance along)."""
    P = [Vector(p) for p in pts]
    T, X, Y = frames(P, x0)
    verts, local, faces = [], [], []
    s = 0.0
    for i, p in enumerate(P):
        if i:
            s += (P[i] - P[i - 1]).length
        rx, ry = radius[i]
        for j in range(sides):
            a = phase + 2 * math.pi * j / sides
            x, y = rx * math.cos(a), ry * math.sin(a)
            verts.append(p + X[i] * x + Y[i] * y)
            local.append(Vector((x, y, s)))
    n = len(P)
    for i in range(n - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            faces.append((i * sides + j, i * sides + j1, (i + 1) * sides + j1, (i + 1) * sides + j))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(range((n - 1) * sides, n * sides)))
    return build(name, verts, faces, mat, M, smooth, {LOCAL: local})


def splinter(name, base, d, out, length, w, mat, M, bend=0.2):
    """A thin splinter peeling off a break: from `base` (local) along d, curling out toward `out`."""
    pts = [base + d * (length * t) + out * (length * bend * t * t) for t in (0.0, 0.35, 0.7, 1.0)]
    rad = [(w, w * 0.45), (w * 0.8, w * 0.38), (w * 0.5, w * 0.25), (0.0004, 0.0003)]
    return tube(name, pts, rad, mat, M, x0=out, sides=3, smooth=60, phase=0.5)


# ---------------------------------------------------------------- more helpers

import random  # noqa: E402

UP = Vector((0.0, 0.0, 1.0))


def seeded(g, seed):
    return mapping(g, g.coords(), loc=(seed * 1.37 + 0.11, seed * 0.71 + 0.53, seed * 2.03 + 0.29))


def gore_flesh(name, seed=0.0):
    """Torn flesh and clotted blood: wet dark red, black clots, a few pale shreds of fat."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    n1 = g.noise(30.0, detail=6.0, roughness=0.6, distortion=0.6, vector=P)
    col = g.mix(g.ramp(n1, 0.3, 0.7), (0.014, 0.002, 0.002), (0.055, 0.007, 0.005))
    fat = g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=4.0, distortion=1.2, vector=P), 0.7, 0.74), 0.45)
    col = g.mix(fat, col, (0.085, 0.05, 0.035))
    clot = g.ramp(voronoi(g, P, 140.0), 0.25, 0.1)
    col = g.mix(g.math("MULTIPLY", clot, 0.6), col, (0.018, 0.002, 0.002))
    rough = g.mixf(g.ramp(n1, 0.4, 0.8), 0.3, 0.55)
    height = g.math("ADD", g.math("MULTIPLY", n1, 0.6), g.math("MULTIPLY", fat, 0.3))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.5, 0.002))


def blob(name, center, radii, axes, mat, seed=0.0, lump=0.25, seg=(7, 5)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=1.0)
    for v in bm.verts:
        k = 1.0 + lump * noise.noise(v.co * 2.2 + Vector((seed, seed * 0.7, seed * 1.3)))
        v.co = Vector(center) + (axes[0] * (v.co.x * radii[0]) + axes[1] * (v.co.y * radii[1])
                                 + axes[2] * (v.co.z * radii[2])) * k
    return tk.smooth(tk.mesh_object(name, bm, mat), 70)


def thicken(line, t):
    """A thin sheet's 2D centerline (a list of (h, d)) thickened both ways, mitred at the corners: the outline,
    and for each point whether it is on the outer face (the -d side)."""
    L = [Vector(q) for q in line]
    n = len(L)
    a, b = [], []
    for i in range(n):
        ns = []
        if i > 0:
            d = (L[i] - L[i - 1]).normalized()
            ns.append(Vector((-d.y, d.x)))
        if i < n - 1:
            d = (L[i + 1] - L[i]).normalized()
            ns.append(Vector((-d.y, d.x)))
        m = (ns[0] + ns[-1]).normalized()
        k = 1.0 / max(0.5, m.dot(ns[0]))
        a.append(L[i] + m * (t / 2 * k))
        b.append(L[i] - m * (t / 2 * k))
    # which side faces out (-d)?
    outer_is_a = sum(p.y for p in a) < sum(p.y for p in b)
    pts = a + list(reversed(b))
    flags = [1.0 if outer_is_a else 0.0] * n + [0.0 if outer_is_a else 1.0] * n
    return pts, flags


def bend(P, H_old, H_new, R, n):
    """Points of an arc of radius R from P, turning from heading H_old to H_new."""
    n_c = (H_new - H_old * H_old.dot(H_new)).normalized()
    ang = H_old.angle(H_new)
    c = P + n_c * R
    return [c - n_c * (R * math.cos(ang * k / n)) + H_old * (R * math.sin(ang * k / n)) for k in range(1, n + 1)]


# ---------------------------------------------------------------- the bumper's line

D_IN = Vector((0.45, -0.88, -0.06)).normalized()  # the torn end driven in under the right ribs from behind and outside
AIM = Vector((-0.07, 0.07, 1.15))
TORSO = ("Hips", "Spine2")
E = skin(AIM, D_IN, TORSO)
H1 = -D_IN  # out of the wound
H2 = Vector((-0.02, 1.0, 0.1)).normalized()  # bent back along the zombie's right side, behind the arm, rising
H3 = Vector((0.8, 0.6, 0.06)).normalized()  # the corner wrapping in behind him
SINK = 0.045


def bumper_path():
    P = [E + D_IN * SINK, E + D_IN * 0.02, E, E + H1 * 0.02, E + H1 * 0.045]
    kinds = ["torn", "in", "skin", "out", "out"]
    b1 = bend(P[-1], H1, H2, 0.075, 6)
    P += b1
    kinds += ["bend"] * len(b1)
    s0 = P[-1]
    for t in (0.05, 0.11):
        P.append(s0 + H2 * t)
        kinds.append("face")
    # kinked out a little half way along, where it folded when it tore off
    H2b = (H2 + Vector((-0.2, 0.0, -0.04))).normalized()
    k0 = P[-1]
    for t in (0.006, 0.05, 0.1, 0.15):
        P.append(k0 + H2b * t)
        kinds.append("face")
    b2 = bend(P[-1], H2b, H3, 0.085, 8)
    P += b2
    kinds += ["corner"] * len(b2)
    w0 = P[-1]
    for t in (0.04, 0.085):
        P.append(w0 + H3 * t)
        kinds.append("wing")
    return P, kinds


PATH, KINDS = bumper_path()
S_PATH = [0.0]
for _i in range(1, len(PATH)):
    S_PATH.append(S_PATH[-1] + (PATH[_i] - PATH[_i - 1]).length)
S_TOTAL = S_PATH[-1]
S_SKIN = S_PATH[2]
S_CORNER0 = S_PATH[KINDS.index("corner") - 1]
S_CORNER1 = S_PATH[len(KINDS) - 3]
T_PATH = [(PATH[min(i + 1, len(PATH) - 1)] - PATH[max(i - 1, 0)]).normalized() for i in range(len(PATH))]


def twist(s):
    """Wrenched along its length when it tore off: up to 18 degrees by the corner."""
    return math.radians(18.0) * smoothstep(0.08, 0.5, s)


def frame_at(i):
    T = T_PATH[i]
    d = T.cross(UP).normalized()  # toward the inside of the bumper (its returns), the corner's turn
    h = d.cross(T).normalized()
    rot = Matrix.Rotation(twist(S_PATH[i]), 3, T)
    return rot @ h, rot @ d


# ---------------------------------------------------------------- materials

def chrome_base(g, W, P):
    """Chrome plate over steel on the face, the bare (once black-painted) steel on the inside of the channel."""
    s, p, outer = g.separate(attr(g))
    o = g.ramp(outer, 0.3, 0.7)
    tone = g.noise(9.0, 4.0, 0.6, P)
    chrome = g.mix(g.ramp(tone, 0.3, 0.75), (0.26, 0.26, 0.265), (0.36, 0.36, 0.365))
    haze = g.ramp(g.noise(3.5, 5.0, 0.6, P, 0.4), 0.45, 0.75)
    chrome = g.mix(g.math("MULTIPLY", haze, 0.7), chrome, (0.13, 0.125, 0.12))
    inside = g.mix(g.ramp(tone, 0.3, 0.7), (0.02, 0.019, 0.018), (0.04, 0.036, 0.032))
    col = g.mix(o, inside, chrome)
    rgh = g.mixf(o, 0.6, g.mixf(haze, 0.08, 0.24))
    height = g.math("MULTIPLY", g.noise(160.0, 3.0, vector=P), 0.05)
    return col, rgh, height


def chrome_post(g, W, P, col, rgh, met, height):
    """Rust: pinhole blooms through the chrome, the plating flaking off in sheets (the copper-bronze under-plate at
    their edges), the inside rusted through; road tar and mud along the bottom; then blood at the wound and
    running back along the bottom flange."""
    s, p, outer = g.separate(attr(g))
    o = g.ramp(outer, 0.3, 0.7)
    met = g.mixf(o, 0.3, 1.0)
    # Chrome flaking off in patches, worst toward the torn end and the corner where it was bent
    stress = g.math("MAXIMUM", g.ramp(s, 0.2, 0.05), g.math("MULTIPLY", band(g, s, S_CORNER0, S_CORNER1, 0.03), 0.6))
    fl = g.math("ADD", g.noise(10.0, 8.0, 0.7, P, 0.5), g.math("MULTIPLY", stress, 0.12))
    flake = g.ramp(fl, 0.575, 0.59)
    under = g.math("MULTIPLY", g.ramp(fl, 0.56, 0.575), g.ramp(fl, 0.59, 0.575))
    col = g.mix(g.math("MULTIPLY", under, 0.7), col, (0.11, 0.06, 0.03))
    met = g.mixf(under, met, 0.8)
    col = g.mix(flake, col, (0.035, 0.03, 0.026))
    rgh = g.mixf(flake, rgh, 0.65)
    met = g.mixf(flake, met, 0.3)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", flake, 0.5))
    # Rust blooms through the plate (pinholes), coarse rust on the bare steel and the inside
    pin = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.7, 0.2, 0.4)), 140.0), 0.12, 0.05),
                 g.ramp(g.noise(5.0, 4.0, vector=P), 0.42, 0.6))
    p_r = tk.photo(g, "rust_coarse_01", 4.0, (0.3, 0.6, 0.9))
    rust_col = tk.grade(g, p_r["color"], 0.8, 0.3)
    rust_col = g.mix(g.ramp(tk._luma(g, p_r["color"]), 0.12, 0.03), rust_col, (0.03, 0.013, 0.006))
    rm = g.math("MAXIMUM", g.math("MULTIPLY", pin, 0.9), g.math("MULTIPLY", flake,
                                                                  g.ramp(g.noise(14.0, 6.0, 0.6, P), 0.35, 0.55)))
    rm = g.math("MAXIMUM", rm, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, o),
                                      g.ramp(g.noise(6.0, 6.0, 0.65, P, 0.4), 0.3, 0.5)))
    bloom = g.math("MULTIPLY", g.ramp(g.noise(4.0, 8.0, 0.65, P, 0.5), 0.6, 0.7), o)
    rm = g.math("MAXIMUM", rm, g.math("MULTIPLY", bloom, 0.75))
    col = g.mix(rm, col, rust_col)
    rgh = g.mixf(rm, rgh, 0.88)
    met = g.mixf(rm, met, 0.05)
    height = g.math("ADD", height, g.math("MULTIPLY", rm, p_r["height"]))
    # Road grime: tar specks and mud thrown up on the lower half, streaks of it running back
    low = g.ramp(p, 0.45, 0.85)
    mud = g.math("MULTIPLY", low, g.ramp(g.noise(6.0, 6.0, 0.65, P, 0.6), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", mud, 0.85), col, g.mix(g.noise(20.0, vector=P), (0.028, 0.022, 0.015),
                                                           (0.05, 0.04, 0.026)))
    rgh = g.mixf(mud, rgh, 0.9)
    met = g.mixf(mud, met, 0.0)
    tar = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 80.0), 0.12, 0.05),
                 g.math("ADD", 0.3, low))
    col = g.mix(tar, col, (0.008, 0.007, 0.006))
    rgh = g.mixf(tar, rgh, 0.5)
    met = g.mixf(tar, met, 0.0)
    # The torn end: bright raw steel at the rip, then the blood
    torn = g.ramp(s, 0.03, 0.0)
    col = g.mix(g.math("MULTIPLY", torn, 0.6), col, (0.09, 0.088, 0.085))
    met = g.mixf(torn, met, 0.9)
    run = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(p, 0.6, 0.95), g.ramp(s, 0.32, 0.08)),
                 g.ramp(g.noise(1.0, 4.0, 0.6, mapping(g, attr(g), scale=(6.0, 300.0, 1.0), loc=(0.3, 0.1, 0.0))),
                        0.5, 0.6))
    col = g.mix(run, col, (0.045, 0.008, 0.005))
    rgh = g.mixf(run, rgh, 0.45)
    met = g.mixf(run, met, 0.0)
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.11, soak=0.035)


chrome_mat = wear("BumperChrome", (0.2, 0.2, 0.2), rough=0.25, metal=1.0, base=chrome_base, post=chrome_post,
                  seed=91.0, scratches=0.7, scratch_col=(0.34, 0.34, 0.34), scratch_metal=1.0, dark_scratches=0.5,
                  scuffs=0.25, scuff_col=(0.1, 0.1, 0.1), edges=0.3, edge_col=(0.12, 0.1, 0.09), edge_metal=0.6,
                  dirt=0.4, dirt_range=(0.16, 0.05), grime=0.7, dust=0.05, specks=0.5, blood=0.3, bump=0.35,
                  dirt_col=((0.025, 0.02, 0.015), (0.06, 0.05, 0.035)))


def rubber_post(g, W, P, col, rgh, met, height):
    """Cracks across the rubber strip, grey bloom, then the blood near the wound."""
    s, p, flag = g.separate(attr(g))
    cr = g.ramp(g.noise(1.0, 3.0, 0.5, mapping(g, attr(g), scale=(140.0, 6.0, 1.0), loc=(0.2, 0.4, 0.0))), 0.62, 0.66)
    col = g.mix(cr, col, (0.006, 0.006, 0.006))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", cr, 1.0))
    bloom = g.ramp(g.noise(6.0, 5.0, 0.6, P), 0.5, 0.7)
    col = g.mix(g.math("MULTIPLY", bloom, 0.45), col, (0.04, 0.039, 0.037))
    rgh = g.mixf(bloom, rgh, 0.85)
    return gore(g, W, P, col, rgh, met, height, amount=0.9, reach=0.1, soak=0.02)


rubber_mat = wear("BumperRubber", (0.016, 0.016, 0.016), rough=0.7, post=rubber_post, seed=92.0, tone=0.2,
                  scratches=0.3, scratch_col=(0.045, 0.045, 0.045), scuffs=0.5, scuff_col=(0.035, 0.035, 0.034),
                  edges=0.3, edge_col=(0.04, 0.04, 0.038), dirt=0.3, dirt_range=(0.16, 0.05), grime=0.6, dust=0.08,
                  specks=0.4, bump=0.3, dirt_col=((0.012, 0.011, 0.01), (0.03, 0.026, 0.02)))


def bracket_post(g, W, P, col, rgh, met, height):
    return rust(g, P, col, rgh, met, height, amount=0.85, scale=2.0, seed=0.9)


bracket_mat = wear("BumperBracket", (0.02, 0.02, 0.02), rough=0.55, metal=0.6, post=bracket_post, seed=93.0,
                   scratches=0.4, scratch_col=(0.12, 0.12, 0.12), scratch_metal=1.0, scuffs=0.3,
                   scuff_col=(0.05, 0.05, 0.05), edges=0.5, edge_col=(0.12, 0.11, 0.1), edge_metal=0.8, dirt=0.8,
                   dirt_range=(0.16, 0.05), grime=1.0, dust=0.3, specks=0.7, bump=0.4)
flesh = gore_flesh("BumperGore", 94.0)


def lens_material(name, seed):
    """The parking light's amber lens: dark, sun-crazed plastic, cracked across, dirt packed round its rim, a
    corner broken out to the black reflector."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    x, y, flag = g.separate(attr(g))
    tone = g.noise(18.0, 4.0, 0.6, P)
    col = g.mix(g.ramp(tone, 0.3, 0.7), (0.065, 0.022, 0.003), (0.11, 0.04, 0.005))
    prism = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", x, 0.004)), 0.5)), 0.3, 0.5)
    col = g.mix(g.math("MULTIPLY", prism, 0.3), col, (0.05, 0.018, 0.003))
    crack = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.noise(1.0, 2.0, 0.5, mapping(g, attr(g), scale=(40.0, 40.0, 1.0),
                                                                                       loc=(0.3, 0.7, 0.0))), 0.5)), 0.012, 0.0)
    col = g.mix(g.math("MULTIPLY", crack, 0.7), col, (0.1, 0.07, 0.045))
    broken = g.math("MULTIPLY", g.ramp(x, 0.022, 0.03), g.ramp(y, 0.008, 0.016))
    col = g.mix(broken, col, (0.012, 0.011, 0.01))
    rim = g.math("MAXIMUM", g.ramp(g.math("ABSOLUTE", x), 0.03, 0.036), g.ramp(g.math("ABSOLUTE", y), 0.017, 0.022))
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", rim, 0.8), g.math("MULTIPLY", g.ramp(g.noise(6.0, 5.0, 0.6, P), 0.5, 0.7), 0.6))
    col = g.mix(dirt, col, (0.025, 0.02, 0.014))
    rough = g.mixf(dirt, g.mixf(crack, 0.14, 0.5), 0.85)
    height = g.math("SUBTRACT", g.math("MULTIPLY", prism, 0.2), g.math("MULTIPLY", crack, 1.0))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.4, 0.001))


lens_mat = lens_material("BumperLens", 95.0)


# ---------------------------------------------------------------- the shell

PROFILE_LINE = [(h * 1.2, d) for h, d in (
    (0.055, 0.028), (0.06, 0.014), (0.061, 0.004), (0.057, -0.005), (0.048, -0.009), (0.03, -0.011), (0.012, -0.013),
    (0.0, -0.018), (-0.012, -0.013), (-0.03, -0.011), (-0.048, -0.009), (-0.057, -0.005), (-0.061, 0.004),
    (-0.06, 0.014), (-0.055, 0.028))]  # a 15 cm face
T_SHEET = 0.0028


def shell():
    """The bumper: its C-section (a crowned face with a raised bead, top and bottom returns) swept along the line,
    twisted, dented and crumpled at the corner; the torn end ragged with teeth of ripped steel."""
    sec, flags = thicken(PROFILE_LINE, T_SHEET)
    m = len(sec)
    n = len(PATH)
    rnd = random.Random(4)
    teeth = [0.004 + 0.028 * max(0.0, math.sin(2.3 * j + 0.7)) ** 3 + 0.006 * rnd.random() for j in range(m)]
    bm = bmesh.new()
    rings, vals, outs = [], [], []
    for i in range(n):
        h, d = frame_at(i)
        ring = []
        for j, (hh, dd) in enumerate(sec):
            q = PATH[i] + h * hh + d * dd
            if i == 0:
                q = q + D_IN * teeth[j]
            # dents: low bumps everywhere, a crumple at the corner and where it was bent
            k = 0.003 * noise.noise(q * 18.0) + 0.0015 * noise.noise(q * 45.0 + Vector((3.0, 1.0, 2.0)))
            if KINDS[i] in ("corner", "bend"):
                k += 0.007 * noise.noise(q * 30.0 + Vector((1.0, 5.0, 2.0)))
            q = q + d * k
            ring.append(bm.verts.new(q))
            p = (0.074 - hh) / 0.148
            vals.append(Vector((S_PATH[i], p, flags[j])))
        rings.append(ring)
    for i in range(n - 1):
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Shell", bm, chrome_mat)
    at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return tk.smooth(obj, 28)


def strip():
    """The black rubber impact strip along the bead, torn off short of the torn end."""
    prof = [(0.013, 0.0), (0.012, -0.005), (0.0, -0.0068), (-0.012, -0.005), (-0.013, 0.0), (0.0, 0.0015)]
    i0 = next(i for i in range(len(PATH)) if S_PATH[i] > 0.17)
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(i0, len(PATH) - 3):  # stops at the end of the corner, short of the parking light
        h, d = frame_at(i)
        base = PATH[i] + d * (-0.0175 - T_SHEET / 2)
        ring = []
        for hh, dd in prof:
            ring.append(bm.verts.new(base + h * hh + d * dd))
            vals.append(Vector((S_PATH[i], hh, 2.0)))
        rings.append(ring)
    m = len(prof)
    for a, b in zip(rings, rings[1:]):
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Strip", bm, rubber_mat)
    at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for i, v in enumerate(vals):
        at.data[i].vector = v
    return tk.smooth(obj, 50)


def bracket():
    """A mounting bracket still bolted inside the channel near the corner, bent and torn off: a flat steel strap
    from the inside of the face back toward where the frame was, two bolt heads on the face."""
    i = KINDS.index("corner") - 2
    h, d = frame_at(i)
    T = T_PATH[i]
    base = PATH[i] + d * 0.004
    pts = [base, base + d * 0.04, base + d * 0.075 - h * 0.012, base + d * 0.105 - h * 0.035]
    W2, TH = 0.026, 0.003
    bm = bmesh.new()
    rings, vals = [], []
    for k, c in enumerate(pts):
        ring = []
        for (a, b) in ((-W2, -TH), (W2, -TH), (W2, TH), (-W2, TH)):
            jag = 0.006 * noise.noise(Vector((a * 80.0, 3.1, 0.0))) if k == len(pts) - 1 else 0.0
            ring.append(bm.verts.new(c + T * a + h * b + d * jag))
            vals.append(Vector((a, b, k * 0.03)))
        rings.append(ring)
    for a_, b_ in zip(rings, rings[1:]):
        for j in range(4):
            j1 = (j + 1) % 4
            bm.faces.new((a_[j], a_[j1], b_[j1], b_[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Bracket", bm, bracket_mat)
    at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for k, v in enumerate(vals):
        at.data[k].vector = v
    out = [tk.smooth(obj, 30)]
    for k, a in enumerate((-0.014, 0.014)):
        c = PATH[i] + T * a + d * (-0.0175 - T_SHEET)
        out.append(lathe("BoltHead%d" % k, [(0.0, 0.0072), (0.002, 0.0068), (0.0035, 0.0045), (0.004, 0.0)], 6,
                         bracket_mat, frame(c, -d, h), smooth=40))
    return out


def rounded_rect(w, h0, h1, r, per=3):
    """A rounded rectangle across (x from -w to w) and up (y from h0 to h1), corners r."""
    out = []
    for cx, cy, a0 in ((w - r, h0 + r, -90.0), (w - r, h1 - r, 0.0), (-w + r, h1 - r, 90.0), (-w + r, h0 + r, 180.0)):
        for k in range(per):
            a = math.radians(a0 + 90.0 * k / (per - 1))
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def lamp():
    """The parking light set in the face of the wrap-around end: a chrome bezel and the amber lens, visible from
    behind."""
    i = len(PATH) - 2
    h, d = frame_at(i)
    T = T_PATH[i]
    base = PATH[i] + d * (-0.012)
    out = -d
    parts = []
    for name, mat, rings, flag in (
            ("Bezel", chrome_mat, [(0.0, 0.041, -0.026, 0.026, 0.008), (0.009, 0.04, -0.025, 0.025, 0.008)], 1.0),
            ("Lens", lens_mat, [(0.005, 0.036, -0.021, 0.021, 0.006), (0.0115, 0.035, -0.02, 0.02, 0.0055)], 3.0)):
        bm = bmesh.new()
        vs, vals = [], []
        for (o, w, h0, h1, r) in rings:
            ring = []
            for x, y in rounded_rect(w, h0, h1, r):
                ring.append(bm.verts.new(base + out * o + T * x + h * y))
                vals.append(Vector((S_PATH[i] + x, (0.074 - y) / 0.148, 1.0)) if flag == 1.0 else Vector((x, y, 3.0)))
            vs.append(ring)
        m = len(vs[0])
        for a, b in zip(vs, vs[1:]):
            for j in range(m):
                j1 = (j + 1) % m
                bm.faces.new((a[j], a[j1], b[j1], b[j]))
        bm.faces.new(list(reversed(vs[0])))
        bm.faces.new(vs[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        obj = tk.mesh_object(name, bm, mat)
        at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
        for k, v in enumerate(vals):
            at.data[k].vector = v
        parts.append(tk.smooth(obj, 45))
    return parts


def guard():
    """A bumper guard (overrider) on the face just before the corner: a tapered chrome block standing up past the
    top edge, with a black rubber pad on its face."""
    i = KINDS.index("corner") - 2
    h, d = frame_at(i)
    T = T_PATH[i]
    base = PATH[i] + d * (-0.0125)
    out = -d
    parts = []
    for name, mat, rings, flag in (
            ("Guard", chrome_mat, [(0.0, 0.03, -0.082, 0.096, 0.01), (0.03, 0.028, -0.078, 0.094, 0.012),
                                   (0.047, 0.024, -0.072, 0.088, 0.011)], 1.0),
            ("GuardPad", rubber_mat, [(0.044, 0.019, -0.064, 0.08, 0.008), (0.056, 0.018, -0.061, 0.077, 0.0075)], 2.0)):
        bm = bmesh.new()
        vs, vals = [], []
        for (o, w, h0, h1, r) in rings:
            ring = []
            for x, y in rounded_rect(w, h0, h1, r):
                ring.append(bm.verts.new(base + out * o + T * x + h * y))
                vals.append(Vector((S_PATH[i] + x, (0.074 - y) / 0.148, flag)) if flag == 1.0 else Vector((S_PATH[i] + x, y, 2.0)))
            vs.append(ring)
        m = len(vs[0])
        for a, b in zip(vs, vs[1:]):
            for j in range(m):
                j1 = (j + 1) % m
                bm.faces.new((a[j], a[j1], b[j1], b[j]))
        bm.faces.new(list(reversed(vs[0])))
        bm.faces.new(vs[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        obj = tk.mesh_object(name, bm, mat)
        at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
        for k, v in enumerate(vals):
            at.data[k].vector = v
        parts.append(tk.smooth(obj, 45))
    return parts


def gore_bits():
    rnd = random.Random(31)
    h, d = frame_at(2)
    T = T_PATH[2]
    out = []
    for k in range(6):
        hh = rnd.uniform(-0.06, 0.06)
        side = d * rnd.choice((-0.012, 0.03))
        c = E + h * hh + side + T * rnd.uniform(-0.004, 0.012)
        r = rnd.uniform(0.008, 0.013)
        out.append(blob("Gore%d" % k, c, (r, r * 0.7, r * 1.25), (T, d, h), flesh, seed=k * 2.3, lump=0.35))
    return out


pieces = [shell(), strip()] + guard() + lamp() + bracket() + gore_bits()
for p in pieces:
    zk.on(p, "Spine1", "Bumper")

# Clearance: the bumper outside the wound against the torso, the legs and the right arm's hit boxes
far = [v.co for p in pieces[:3] for v in p.data.vertices if (v.co - E).length > 0.1]
for bones in (TORSO, ("RightUpLeg", "LeftUpLeg"), ("RightArm", "RightForeArm")):
    dmin = min(sdf(q, bones) for q in far)
    print("[%s] clearance from %s: %.1f cm" % (SCRIPT, "+".join(bones), 100 * dmin))
xs = [q.x for q in far]
ys = [q.y for q in far]
print("[%s] wound at (%.3f, %.3f, %.3f); outside the wound x %.3f..%.3f, y %.3f..%.3f, %.0f cm along" % (
    SCRIPT, *E, min(xs), max(xs), min(ys), max(ys), 100 * S_TOTAL))
export(pieces)
zk.previews(SCRIPT, PREVIEWS, Vector((-0.08, 0.22, 1.12)), distance=1.7)
close_up("close", (-1.0, 0.5, 0.35), Vector((-0.12, 0.3, 1.15)), distance=0.7)
close_up("wound", (-0.8, 0.3, 0.3), E, distance=0.32)
print("[%s] done" % SCRIPT)
