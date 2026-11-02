"""Crossbow bolt: an 18-inch carbon hunting bolt shot clean through the left shoulder from the front: the three-blade
broadhead and a few centimetres of shaft stick out of the back, the vanes and nock out of the front. Matte black
carbon with a scuffed white wrap under the vanes, two olive vanes and a dull orange cock vane (one torn), a black
half-moon nock; the broadhead and the shaft by both wounds dark with dried blood, a scrap of tissue caught on the
blades.

One part on the LeftShoulder bone, LeftShoulder#Bolt (in game it is scaled with the chest's hit box).

    blender -b --factory-startup --python crossbow_bolt.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "CrossbowBolt", "crossbow_bolt"
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



# ---------------------------------------------------------------- shared shapes for arrows and bolts

def fin(name, outline, thick, angle, mat, M, smooth=30, twist=0.0):
    """A thin flat plate standing out from the local z axis at `angle` (a vane, a feather, a broadhead blade):
    outline [(r, z), ...] (r out from the axis), `thick` across. twist (radians per meter of z) leans it round the
    shaft, like a helical vane."""
    n = len(outline)
    verts, faces = [], []
    for side in (-1.0, 1.0):
        for r, z in outline:
            a = angle + twist * z
            radial = Vector((math.cos(a), math.sin(a), 0.0))
            tangent = Vector((-math.sin(a), math.cos(a), 0.0))
            verts.append(radial * r + tangent * (side * thick / 2) + Vector((0.0, 0.0, z)))
    faces.append(tuple(range(n)))
    faces.append(tuple(range(n, 2 * n)))
    for k in range(n):
        k1 = (k + 1) % n
        faces.append((k, k1, n + k1, n + k))
    return build(name, verts, faces, mat, M, smooth)


def blob(name, center, radius, mat, seed=0, lumps=0.35, M=None):
    """A lumpy clot or scrap of tissue (a displaced ico sphere), flattened a little."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    rnd = [math.sin(seed * 12.9898 + k * 78.233) * 43758.5453 % 1.0 for k in range(64)]
    verts = []
    for v in bm.verts:
        p = v.co.copy()
        n = sum(rnd[k] * math.sin(p.dot(Vector((rnd[k + 1] - 0.5, rnd[k + 2] - 0.5, rnd[k + 3] - 0.5))) * 9.0 + k)
                for k in range(0, 24, 4)) / 6.0
        verts.append(Vector((p.x * radius[0], p.y * radius[1], p.z * radius[2])) * (1.0 + lumps * n) + Vector(center))
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return build(name, verts, faces, mat, M, 60)


# ---------------------------------------------------------------- the bolt

D_FLY = Vector((0.12, 1.0, -0.12)).normalized()  # its flight: in at the front, out at the back, a little down
AIM = Vector((0.128, 0.05, 1.452))  # a point on its line, inside the shoulder
FRONT_IN = skin(AIM, D_FLY)


def exit_point(start, d):
    t, step = 0.0, 0.002
    while sdf(start + d * t) < 0.0:
        t += step
    lo, hi = t - step, t
    for _ in range(30):
        mid = (lo + hi) / 2
        if sdf(start + d * mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return start + d * hi


BACK_OUT = exit_point(AIM, D_FLY)
BACK_SHAFT = 0.035  # shaft showing at the back before the broadhead
HEAD = 0.046  # broadhead length
TIP = BACK_OUT + D_FLY * (BACK_SHAFT + HEAD)
LENGTH = 0.46  # point to nock
M = frame(TIP, -D_FLY, (0.0, 0.0, 1.0))  # local z from the point toward the nock, local x up
R = 0.0044  # 8.8 mm shaft
Z_SHAFT0 = HEAD - 0.004  # the shaft (with its insert) starts inside the ferrule
Z_NOCK = LENGTH - 0.014
VANES = (LENGTH - 0.085, LENGTH - 0.022)


def carbon(g, W, P):
    """Matte black carbon, a faint woven sheen, the maker's faded print and a scuffed white wrap under the vanes."""
    L = attr(g)
    x, y, z = g.separate(L)
    weave = g.noise(1.0, 2.0, 0.5, mapping(g, L, scale=(900.0, 900.0, 140.0), rot=(0.0, 0.0, 0.6)))
    col = g.mix(g.math("MULTIPLY", weave, 0.5), (0.012, 0.012, 0.013), (0.03, 0.03, 0.032))
    rgh = g.math("ADD", 0.42, g.math("MULTIPLY", weave, 0.15))
    height = g.math("MULTIPLY", weave, 0.15)
    wrap = band(g, z, VANES[0] - 0.006, Z_NOCK - 0.002, 0.0005)
    wc = g.mix(g.ramp(g.noise(40.0, 4.0, vector=P), 0.3, 0.7), (0.19, 0.185, 0.17), (0.29, 0.28, 0.26))
    col = g.mix(wrap, col, wc)
    rgh = g.mixf(wrap, rgh, 0.5)
    height = g.math("ADD", height, g.math("MULTIPLY", wrap, 0.3))
    # The print: a thin pale band of lettering running along one side of the shaft, ahead of the wrap
    side = g.ramp(y, 0.0, 0.003)
    text = g.math("MULTIPLY", band(g, z, VANES[0] - 0.09, VANES[0] - 0.03, 0.0005),
                  g.math("MULTIPLY", band(g, x, -0.0012, 0.0012, 0.0002), side))
    text = g.math("MULTIPLY", text, g.ramp(g.math("SINE", g.math("MULTIPLY", z, 1900.0)), -0.3, 0.3))
    text = g.math("MULTIPLY", text, g.ramp(g.noise(70.0, 4.0, vector=P), 0.35, 0.5))
    col = g.mix(g.math("MULTIPLY", text, 0.7), col, (0.3, 0.3, 0.29))
    return col, rgh, height


def shaft_post(g, W, P, col, rgh, met, height):
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.07, soak=0.024)


shaft_mat = wear("BoltShaft", (0.02, 0.02, 0.02), rough=0.45, base=carbon, post=shaft_post, seed=31.0, scratches=0.6,
                 scratch_col=(0.16, 0.16, 0.16), dark_scratches=0.1, scuffs=0.5, scuff_col=(0.07, 0.07, 0.07),
                 edges=0.0, dirt=0.5, dirt_range=(0.16, 0.05), grime=0.8, dust=0.2, specks=0.6, blood=0.5, bump=0.3,
                 dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))


def vane_post(g, W, P, col, rgh, met, height):
    """Ragged nicks and a split along the trailing edge, and spatter."""
    L = attr(g)
    nick = g.ramp(g.noise(1.0, 3.0, 0.6, mapping(g, L, scale=(300.0, 300.0, 90.0))), 0.64, 0.7)
    col = g.mix(g.math("MULTIPLY", nick, 0.6), col, tk._darker(g, col, 0.35))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", nick, 0.8))
    return gore(g, W, P, col, rgh, met, height, amount=0.8, reach=0.25, soak=0.004)


def vane_mat(name, color, seed):
    return wear(name, color, rough=0.5, post=vane_post, seed=seed, tone=0.3, scratches=0.4,
                scratch_col=tuple(c * 1.8 + 0.03 for c in color), dark_scratches=0.4, scuffs=0.6,
                scuff_col=tuple(c * 1.5 + 0.02 for c in color), edges=0.6, edge_col=tuple(c * 2.2 + 0.04 for c in color),
                dirt=0.6, dirt_range=(0.16, 0.05), grime=0.8, dust=0.3, specks=0.6, blood=0.3, bump=0.3,
                dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))


olive = vane_mat("VaneOlive", (0.045, 0.05, 0.022), 32.0)
orange = vane_mat("VaneOrange", (0.2, 0.06, 0.015), 33.0)
nock_mat = wear("BoltNock", (0.016, 0.017, 0.016), rough=0.35, seed=34.0, scratches=0.5,
                scratch_col=(0.12, 0.12, 0.11), scuffs=0.5, scuff_col=(0.05, 0.05, 0.05), edges=0.7,
                edge_col=(0.14, 0.14, 0.13), dirt=0.6, dirt_range=(0.16, 0.05), grime=0.9, dust=0.2, specks=0.5,
                bump=0.3)


def head_post(g, W, P, col, rgh, met, height):
    col, rgh, met, height = rust(g, P, col, rgh, met, height, amount=0.3, scale=2.0, seed=4.4)
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.13, soak=0.085)


steel = wear("Broadhead", (0.38, 0.38, 0.39), rough=0.3, metal=1.0, post=head_post, seed=35.0, scratches=0.6,
             scratch_col=(0.6, 0.6, 0.6), scratch_metal=1.0, scuffs=0.3, scuff_col=(0.25, 0.25, 0.25), edges=0.0,
             dirt=0.4, dirt_range=(0.16, 0.05), grime=0.8, dust=0.0, specks=0.5, bump=0.25)


def tissue(g, W, P):
    col = g.mix(g.ramp(g.noise(30.0, 5.0, 0.6, P), 0.3, 0.7), (0.03, 0.005, 0.004), (0.09, 0.022, 0.016))
    fat = g.ramp(g.noise(60.0, 4.0, vector=P), 0.68, 0.74)
    col = g.mix(fat, col, (0.13, 0.08, 0.05))
    rgh = g.mixf(fat, 0.3, 0.45)
    height = g.math("MULTIPLY", g.noise(120.0, 6.0, 0.6, P), 0.8)
    return col, rgh, height


gore_mat = wear("BoltGore", (0.08, 0.01, 0.008), rough=0.35, base=tissue, seed=36.0, scratches=0.0, scuffs=0.0,
                edges=0.0, dirt=0.3, dirt_range=(0.12, 0.04), grime=0.6, dust=0.0, specks=0.4, bump=0.6,
                dirt_col=((0.02, 0.006, 0.004), (0.05, 0.015, 0.01)))


def shaft():
    zs = [Z_SHAFT0, Z_SHAFT0 + 0.003]
    zs += [Z_SHAFT0 + (Z_NOCK - Z_SHAFT0) * k / 5 for k in range(1, 6)]
    prof = [(Z_SHAFT0 - 0.0005, R * 0.8)] + [(z, R) for z in zs]
    return lathe("Shaft", prof, 10, shaft_mat, M, smooth=50)


def nock():
    """A half-moon nock: a collar over the shaft end, the back cut in a shallow crescent."""
    rings = [ring(Z_NOCK - 0.004, R * 0.97, n=10), ring(Z_NOCK, R * 1.06, n=10), ring(LENGTH - 0.003, R * 1.06, n=10)]
    # The crescent: the end face dips in across local y
    end = []
    for p in ring(LENGTH, R * 0.95, n=10):
        end.append(Vector((p.x, p.y, LENGTH - 0.0035 * (1.0 - (p.x / R) ** 2))))
    rings.append(end)
    rings.append([Vector((0.0, 0.0, LENGTH - 0.0035))])
    return loft("Nock", rings, nock_mat, M, smooth=40)


def vanes():
    out = []
    z0, z1 = VANES
    for k, (ang, mat) in enumerate(((90.0, orange), (210.0, olive), (330.0, olive))):
        h = 0.0115
        # A low parabolic vane: rises from the front, full height toward the back, a steep trailing edge
        pts = [(R, z0 - 0.002)]
        for i in range(1, 7):
            t = i / 6
            pts.append((R + h * (1 - (1 - t) ** 2) * (0.9 if k == 0 else 1.0), z0 + (z1 - z0 - 0.006) * t))
        pts.append((R + h * 0.55, z1))
        pts.append((R - 0.0006, z1))
        if k == 0:
            # The cock vane is torn: a bite out of its top
            pts[4] = (pts[4][0] - 0.0055, pts[4][1])
            pts[5] = (pts[5][0] - 0.003, pts[5][1])
        out.append(fin("Vane%d" % k, pts, 0.0008, math.radians(ang), mat, M, twist=0.6))
    return out


def broadhead():
    """A fixed three-blade broadhead: a steel ferrule to a cut-on-contact point, three blades swept back."""
    ferrule = lathe("Ferrule", [(0.0, 0.0), (0.006, 0.0022), (0.018, 0.0036), (0.034, 0.0045), (HEAD - 0.002, 0.0046),
                                (HEAD + 0.003, 0.0044)], 8, steel, M, smooth=40, phase=math.pi / 8)
    out = [ferrule]
    for k in range(3):
        pts = [(0.001, 0.002), (0.0145, 0.03), (0.0142, 0.0335), (0.004, 0.038), (0.002, 0.036)]
        out.append(fin("Blade%d" % k, pts, 0.0007, math.radians(30 + 120 * k), steel, M))
    return out


def scrap():
    """A scrap of flesh caught on the blades behind the point."""
    return blob("Scrap", (0.006, -0.002, 0.027), (0.0085, 0.004, 0.012), gore_mat, seed=3, lumps=0.7, M=M)


pieces = [shaft(), nock()] + vanes() + broadhead() + [scrap()]
for p in pieces:
    zk.on(p, "LeftShoulder", "Bolt")
print("[%s] in at the front (%.3f, %.3f, %.3f), out at the back (%.3f, %.3f, %.3f), point (%.3f, %.3f, %.3f); "
      "%.1f cm showing in front" % (NAME, *FRONT_IN, *BACK_OUT, *TIP, 100 * (LENGTH - (FRONT_IN - TIP).length)))
export(pieces)
zk.previews(SCRIPT, PREVIEWS, Vector((0.12, 0.05, 1.42)), distance=1.0)
close_up("close", (0.8, -1.0, 0.3), FRONT_IN - D_FLY * 0.1, distance=0.45)
close_up("tip", (0.5, 1.0, 0.4), BACK_OUT + D_FLY * 0.04, distance=0.3)
print("[%s] done" % SCRIPT)
