"""Shovel (remnant): a garden spade driven blade-first into the upper right back (across from where the axe sits in
the left shoulder blade), the ash shaft snapped off about 50 cm out, angled up and back and out over the right
shoulder (its broken end shows above the shoulder from the front). The forged blade is gone to
rust under the last flakes of its black enamel, scoured by years of digging, dried garden soil caked round the treads
and the tapered socket; its lower half is in the body, dried blood and gore soaked up the steel where it went in. The
shaft is ash gone dark and greasy with handling, broken off in a jagged, splintered end.

The blade runs on into the body and is cut away 4 cm inside the stand-in. One part on the Spine2 bone, Spine2#Shovel.

    blender -b --factory-startup --python shovel.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "Shovel", "shovel"
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


def snapped_wood(name, seed):
    """The torn wood of the break: pale fibers gone grey, torn along the grain, dark in the splits."""
    mat, g = tk.new_material(name)
    L = attr(g)
    P = mapping(g, g.coords(), loc=(seed, 0.3, 0.7))
    fib = g.noise(1.0, 6.0, 0.7, mapping(g, L, scale=(900.0, 900.0, 40.0), loc=(seed, 0.1, 0.4)))
    col = g.mix(g.ramp(fib, 0.3, 0.75), (0.018, 0.015, 0.011), (0.042, 0.034, 0.024))
    torn = g.ramp(g.noise(30.0, 6.0, vector=P), 0.52, 0.68)
    col = g.mix(g.math("MULTIPLY", torn, 0.8), col, (0.02, 0.016, 0.012))
    dirt = tk._grime(g, 0.9)
    col = g.mix(g.math("MULTIPLY", dirt, 0.7), col, (0.025, 0.02, 0.015))
    rough = g.math("ADD", 0.82, g.math("MULTIPLY", fib, 0.1))
    height = g.math("MULTIPLY", g.math("ADD", fib, g.math("MULTIPLY", torn, -0.8)), 0.6)
    col, rough, metal = tk._grit(g, col, rough, 0.0, 0.1)
    return tk.finish(mat, g, col, metal, rough, g.bump(height, 0.5, 0.002))


# ---------------------------------------------------------------- the spade's frame

D = Vector((-0.45, 0.62, 0.64)).normalized()  # up the shaft: up, back and out over the zombie's right shoulder
AIM = Vector((-0.04, 0.12, 1.32))  # inside the upper right back, on the blade's middle line
ENTRY = skin(AIM, -D, ("Spine2",))
Z_SKIN = -0.14  # where the skin crosses the blade's middle line, measured from the tread line
O = ENTRY - D * Z_SKIN  # the middle of the blade's top edge
TILT = math.radians(-20.0)  # the blade turned on the shaft a little, its face toward the back
M = frame(O, D, Matrix.Rotation(TILT, 3, D) @ Vector((1.0, 0.0, 0.0)))  # z up the shaft, x across the blade, y out
# of its back (the socket's side)
L_BLADE, HW0, HW1 = 0.27, 0.094, 0.087  # the blade's length and half widths at the top and the cutting edge
YS, RS = 0.013, 0.0175  # the shaft's axis behind the blade (local y) and its radius
Z_END = Z_SKIN + 0.5  # the snapped end, 50 cm out from the skin
SHAFT = M @ Matrix.Translation((0.0, YS, 0.0))


# ---------------------------------------------------------------- materials

def paint_kept(g, P, L):
    """Where the old black enamel is left: islands on the upper blade and the socket, worn off toward the edge."""
    z = g.separate(L)[2]
    n = g.math("ADD", g.noise(6.0, 8.0, 0.7, P, 0.5), g.math("MULTIPLY", z, 1.6))
    return g.ramp(n, 0.5, 0.53)


def scoured(g, P, L):
    """Thin bright lines scoured down the lower blade by years of digging, where the rust is rubbed off."""
    z = g.separate(L)[2]
    sc = lines(g, L, (700.0, 700.0, 12.0), (0.0, 0.0, 0.0), (0.2, 0.5, 0.1), 0.035, 25.0)
    return g.math("MULTIPLY", g.math("MULTIPLY", sc, g.ramp(z, -0.03, -0.09)), 0.8)


def steel_base(g, W, P):
    """Old forged steel gone mostly to rust: brown rust blooms and pits over dark scale, the last flakes of the black
    enamel up top, the lower blade scoured in thin lines."""
    L = attr(g)
    keep = paint_kept(g, P, L)
    p = tk.photo(g, "rust_coarse_01", 3.0, (0.37, 0.61, 0.13))
    rust_c = tk.grade(g, p["color"], 0.8, 0.85)
    rust_c = g.mix(g.ramp(tk._luma(g, p["color"]), 0.12, 0.03), rust_c, (0.025, 0.013, 0.008))
    scale_c = g.mix(g.ramp(g.noise(9.0, 4.0, vector=P), 0.3, 0.7), (0.02, 0.019, 0.018), (0.042, 0.039, 0.036))
    bloom = g.ramp(g.noise(4.0, 8.0, 0.65, P, 0.5), 0.38, 0.47)
    col = g.mix(bloom, scale_c, rust_c)
    sc = scoured(g, P, L)
    col = g.mix(sc, col, (0.1, 0.096, 0.09))
    paint = g.mix(g.ramp(g.noise(20.0, 3.0, vector=P), 0.3, 0.7), (0.012, 0.012, 0.013), (0.028, 0.027, 0.026))
    col = g.mix(keep, col, paint)
    rgh = g.mixf(bloom, 0.6, 0.88)
    rgh = g.mixf(sc, rgh, 0.4)
    rgh = g.mixf(keep, rgh, 0.5)
    height = g.math("ADD", g.math("MULTIPLY", bloom, g.math("MULTIPLY", p["height"], 0.9)),
                    g.math("MULTIPLY", g.noise(150.0, 4.0, 0.6, P), 0.1))
    height = g.math("ADD", height, g.math("MULTIPLY", keep, 0.35))
    return col, rgh, height


def steel_post(g, W, P, col, rgh, met, height):
    """Bare metal only in the scoured lines; dried garden soil caked round the treads and the socket; the gore where
    it went in."""
    L = attr(g)
    z = g.separate(L)[2]
    met = g.mixf(scoured(g, P, L), met, 0.85)
    col, rgh, met, height = rust(g, P, col, rgh, met, height, amount=0.4, scale=1.1, seed=4.4)
    soil = g.math("MAXIMUM", g.math("MULTIPLY", g.ramp(z, -0.075, -0.01), g.ramp(z, 0.07, 0.02)),
                  g.math("MULTIPLY", g.ramp(g.noise(5.0, 6.0, 0.6, P, 0.3), 0.6, 0.66), 0.8))
    soil = g.math("MULTIPLY", soil, g.ramp(g.noise(16.0, 6.0, 0.7, P, 0.4), 0.42, 0.55))
    soil_col = g.mix(g.ramp(g.noise(30.0, 4.0, vector=P), 0.3, 0.7), (0.03, 0.023, 0.015), (0.062, 0.05, 0.035))
    col = g.mix(soil, col, soil_col)
    rgh = g.mixf(soil, rgh, 0.95)
    met = g.mixf(soil, met, 0.0)
    height = g.math("ADD", height, g.math("MULTIPLY", soil, g.math("ADD", 0.4, g.noise(60.0, 4.0, 0.6, P))))
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.12, soak=0.019)


steel_mat = wear("SpadeSteel", (0.05, 0.045, 0.04), rough=0.7, metal=0.0, base=steel_base, post=steel_post, seed=41.0,
                 scratches=0.35, scratch_col=(0.11, 0.105, 0.1), scratch_metal=1.0, dark_scratches=0.5, scuffs=0.3,
                 scuff_col=(0.045, 0.03, 0.02), edges=0.35, edge_col=(0.09, 0.085, 0.08), edge_metal=1.0, dirt=0.6,
                 dirt_range=(0.05, 0.028), grime=1.0, dust=0.03, specks=0.8, blood=0.5, bump=0.5,
                 dirt_col=((0.018, 0.013, 0.009), (0.05, 0.038, 0.026)))


def ash_base(g, W, P):
    """Ash gone dark with years of handling: the grain still showing, late-wood lines and checks, a greasy sheen."""
    L = attr(g)
    Q = mapping(g, L, loc=(0.71, 0.23, 0.0))
    fib = g.noise(1.0, 6.0, 0.6, mapping(g, Q, scale=(380.0, 380.0, 10.0)))
    w = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SAW")
    g._in(w, "Scale", 70.0)
    g._in(w, "Distortion", 5.0)
    g._in(w, "Detail", 3.0)
    g._in(w, "Detail Scale", 1.0)
    g.links.new(mapping(g, Q, scale=(1.0, 0.6, 0.05)), w.inputs["Vector"])
    rings = g.ramp(tk._sock(w.outputs, "Fac"), 0.6, 0.95)
    col = g.mix(fib, (0.036, 0.025, 0.016), (0.078, 0.054, 0.033))
    col = g.mix(g.math("MULTIPLY", rings, 0.7), col, (0.022, 0.015, 0.009))
    checks = g.math("MULTIPLY", g.ramp(g.noise(1.0, 3.0, 0.5, mapping(g, Q, scale=(160.0, 160.0, 5.0))), 0.66, 0.7),
                    g.ramp(g.noise(8.0, 3.0, vector=P), 0.5, 0.6))
    col = g.mix(checks, col, (0.012, 0.009, 0.006))
    rgh = g.math("ADD", 0.5, g.math("MULTIPLY", fib, 0.15))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", fib, 0.3), g.math("MULTIPLY", rings, 0.25)),
                    g.math("MULTIPLY", checks, 1.0))
    return col, rgh, height


def ash_post(g, W, P, col, rgh, met, height):
    """Black greasy hand patina over most of it, soil rubbed in near the socket, blood spattered from the wound."""
    L = attr(g)
    z = g.separate(L)[2]
    hands = g.ramp(g.noise(5.0, 5.0, 0.6, P, 0.4), 0.25, 0.55)
    col = g.mix(g.math("MULTIPLY", hands, 0.75), col, (0.016, 0.012, 0.008))
    rgh = g.mixf(hands, rgh, 0.36)
    soil = g.math("MULTIPLY", g.ramp(z, 0.22, 0.15), g.ramp(g.noise(12.0, 6.0, 0.6, P, 0.3), 0.45, 0.6))
    col = g.mix(soil, col, (0.06, 0.048, 0.034))
    rgh = g.mixf(soil, rgh, 0.92)
    return gore(g, W, P, col, rgh, met, height, amount=0.8, reach=0.2, soak=0.003)


ash_mat = wear("SpadeShaft", (0.07, 0.05, 0.03), rough=0.5, base=ash_base, post=ash_post, seed=42.0,
               scratches=0.5, scratch_col=(0.13, 0.1, 0.07), dark_scratches=0.5, scuffs=0.5,
               scuff_col=(0.11, 0.085, 0.06), edges=0.3, edge_col=(0.12, 0.09, 0.06), dirt=0.6,
               dirt_range=(0.05, 0.028), grime=0.9, dust=0.04, specks=0.6, grease=0.6, blood=0.5, bump=0.45,
               dirt_col=((0.022, 0.016, 0.011), (0.06, 0.045, 0.03)))
broken_mat = snapped_wood("SpadeBroken", 43.0)


# ---------------------------------------------------------------- the spade

def blade_outline(u, v):
    a = 2 * u - 1
    hw = HW0 + (HW1 - HW0) * v
    corner = smoothstep(0.82, 1.0, v) * smoothstep(0.7, 1.0, abs(a))
    x = a * hw * (1.0 - 0.07 * corner)
    z = -L_BLADE * v - 0.006 * (1.0 - a * a) * v + 0.013 * corner
    return x, z


def rib(u, v):
    """The frog: a raised tongue down the back of the blade from the socket."""
    x, z = blade_outline(u, v)
    return 0.0045 * math.exp(-(x / 0.013) ** 2) * smoothstep(-0.12, -0.02, z)


def blade_thick(u, v):
    t = 0.0026 - 0.0008 * v
    t *= 1.0 - 0.7 * smoothstep(0.92, 1.0, v)
    return t + rib(u, v)


def blade_offset(u, v):
    a = 2 * u - 1
    return -0.008 * a * a - 0.005 * v * v + rib(u, v) / 2


def blade():
    us = [0.0, 0.03, 0.12, 0.25, 0.37, 0.44, 0.5, 0.56, 0.63, 0.75, 0.88, 0.97, 1.0]
    vs = [0.0, 0.03, 0.1, 0.2, 0.32, 0.45, 0.6, 0.75, 0.88, 0.95, 1.0]
    obj = slab("Blade", blade_outline, blade_thick, us, vs, steel_mat, M, smooth=35, offset=blade_offset)
    return bury(obj, 0.04, ("Spine2", "RightArm", "LeftArm", "Head"))


def treads():
    """The top edge rolled over into a step for the foot on each side of the socket."""
    out = []
    R = Matrix.Rotation(math.radians(90.0), 4, "X")  # the slab's (x, -z) becomes (x, y); its thickness runs along z
    for side in (1, -1):
        x0, x1 = 0.021, HW0 - 0.003

        def outline(u, v, side=side, x0=x0, x1=x1):
            x = x0 + (x1 - x0) * u
            x -= 0.006 * smoothstep(0.75, 1.0, u) * smoothstep(0.6, 1.0, v)  # rounded outer corner
            return side * x, -(-0.002 + 0.017 * v)

        def thick(u, v):
            return 0.0024

        def offset(u, v):
            return -0.0012 - 0.0035 * v * v  # the lip curls down a little

        out.append(slab("Tread%d" % side, outline, thick, [0.0, 0.5, 0.85, 1.0], [0.0, 0.5, 1.0], steel_mat, M @ R,
                        smooth=40, offset=offset))
    return out


def socket():
    """The tapered socket rising from the blade round the shaft, a lip at its mouth."""
    def ell(z, rx, ry, cy, n=12):
        return ring(z, rx, ry, n=n, cy=cy)
    rings = [ell(-0.06, 0.011, 0.0025, 0.0015), ell(-0.03, 0.017, 0.006, 0.004), ell(-0.008, 0.022, 0.011, 0.008),
             ell(0.012, 0.0215, 0.0195, YS), ell(0.07, 0.0205, 0.0205, YS), ell(0.128, 0.0199, 0.0199, YS),
             ell(0.134, 0.0207, 0.0207, YS), ell(0.141, 0.0204, 0.0204, YS)]
    return loft("Socket", rings, steel_mat, M, smooth=45)


def rivets():
    out = []
    prof = [(-0.003, 0.0), (-0.0028, 0.0042), (-0.0005, 0.0048), (0.0008, 0.0038), (0.0016, 0.0)]
    for k, z in enumerate((0.045, 0.1)):
        r = 0.0205 if z < 0.1 else 0.0202
        local = Matrix.Translation((0.0, YS + r, z)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        out.append(lathe("Rivet%d" % k, prof, 8, steel_mat, M @ local, smooth=60))
    return out


def shaft():
    out = [stick("Shaft", 0.12, Z_END, RS, ash_mat, broken_mat, SHAFT, sides=12, mid=(0.2, 0.3),
                 jag1=jagged(12, long=0.034, seed=1.3))]
    for k, (ang, ln, w, fl) in enumerate(((0.5, 0.05, 0.005, 0.25), (2.4, 0.035, 0.0042, 0.4),
                                          (4.1, 0.03, 0.0038, 0.15), (5.4, 0.022, 0.003, 0.5))):
        base = Vector((RS * 0.85 * math.cos(ang), RS * 0.85 * math.sin(ang), Z_END - 0.014))
        out.append(splinter("Splinter%d" % k, base, Vector((0.0, 0.0, 1.0)),
                            Vector((math.cos(ang), math.sin(ang), 0.0)), ln, w, broken_mat, SHAFT, bend=fl))
    return out


pieces = [blade()] + treads() + [socket()] + rivets() + shaft()
for p in pieces:
    zk.on(p, "Spine2", "Shovel")
edge = [M @ Vector((*blade_outline(u, 1.0)[:1], blade_offset(u, 1.0), blade_outline(u, 1.0)[1]))
        for u in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)]
print("[%s] cutting edge depth past the stand-in, corner to corner: %s cm" % (
    NAME, ", ".join("%.1f" % (-100 * sdf(p)) for p in edge)))
corners = [M @ Vector((s * HW0, 0.0, 0.0)) for s in (-1, 1)]
print("[%s] tread corners %.1f / %.1f cm out of the stand-in" % (NAME, 100 * sdf(corners[0]), 100 * sdf(corners[1])))
tip = SHAFT @ Vector((0.0, 0.0, Z_END))
print("[%s] blade enters the stand-in at (%.3f, %.3f, %.3f); top of the blade at (%.3f, %.3f, %.3f); snapped end "
      "at (%.3f, %.3f, %.3f)" % (NAME, *ENTRY, *O, *tip))
export(pieces)
zk.previews(SCRIPT, PREVIEWS, Vector((-0.05, 0.25, 1.4)), distance=1.5)
close_up("close", (-0.5, 1.0, 0.45), O, distance=0.6)
close_up("blade", (-0.1, 1.0, -0.1), O + D * -0.06, distance=0.4)
close_up("profile", (-1.0, 0.0, 0.1), O + D * 0.1, distance=0.7)
close_up("break", (-0.4, 0.4, 1.0), SHAFT @ Vector((0.0, 0.0, Z_END - 0.03)), distance=0.3)
print("[%s] done" % SCRIPT)
