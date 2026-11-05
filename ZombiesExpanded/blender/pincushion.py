"""Pincushion (rare showpiece): someone's last stand. Eight arrows from at least three archers, shot as the zombie
came on and as it turned away: three in the upper back (a camo carbon hunting arrow high on the left shoulder blade, a
dark olive aluminum arrow with orange vanes low on the right shoulder blade, and a cedar shaft snapped off short in a
splintered break between them), two in the lower back (a cedar target arrow with barred turkey feathers and painted
cresting, a black carbon arrow with faded green vanes), one in the back of the left upper arm (white vanes on black
carbon), one in the front of the right thigh (a cedar shaft snapped off 15 cm out) and one in the chest from the
front (black carbon with red vanes). Worn, nicked and torn fletching, dried blood crusting every shaft where it
goes in.

Arrows and their parts are arrows.py's (copied, as that script builds its own model when it runs). Every head is
buried: each shaft runs 3.5 cm on into the stand-in. Four parts: Spine2#Arrows (the three upper back arrows and the
chest arrow), Spine1#Arrows (the two in the lower back), LeftArm#Arrows and RightUpLeg#Arrows.

    blender -b --factory-startup --python pincushion.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "Pincushion", "pincushion"
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



# ---------------------------------------------------------------- shared shapes for arrows and bolts

def fin(name, outline, thick, angle, mat, M, smooth=30, twist=0.0):
    """A thin flat plate standing out from the local z axis at `angle` (a vane, a feather, a splinter): outline
    [(r, z), ...] (r out from the axis), `thick` across. twist (radians per meter of z) leans it round the shaft,
    like a helical vane."""
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


def hash01(*k):
    return (math.sin(sum(v * c for v, c in zip(k, (12.9898, 78.233, 37.719)))) * 43758.5453) % 1.0


# ---------------------------------------------------------------- materials

def wood_base(light, dark, seed):
    """Cedar or birch shafting: the grain running along the shaft, a little darker in streaks."""
    def base(g, W, P):
        L = attr(g)
        Q = mapping(g, L, loc=(seed, seed * 0.7, 0.0))
        fib = g.noise(1.0, 5.0, 0.6, mapping(g, Q, scale=(900.0, 900.0, 12.0)))
        streak = g.noise(1.0, 3.0, 0.5, mapping(g, Q, scale=(160.0, 160.0, 4.0)))
        col = g.mix(fib, dark, light)
        col = g.mix(g.math("MULTIPLY", g.ramp(streak, 0.55, 0.75), 0.6), col, tk._darker(g, dark, 0.7))
        rgh = g.math("ADD", 0.5, g.math("MULTIPLY", fib, 0.15))
        height = g.math("MULTIPLY", fib, 0.3)
        return col, rgh, height
    return base


def camo_base(g, W, P):
    """Carbon printed in a dark woodland camo, a satin clear coat over it."""
    L = attr(g)
    Q = mapping(g, L, scale=(1.0, 1.0, 0.35), loc=(0.3, 0.8, 0.0))
    def blot(scale, seed, lo):
        n = g.noise(scale, 3.0, 0.55, mapping(g, Q, loc=seed), 0.8)
        return g.ramp(n, lo, lo + 0.02)
    col = g.mix(blot(120.0, (0.1, 0.4, 0.2), 0.5), (0.05, 0.045, 0.03), (0.022, 0.02, 0.014))
    col = g.mix(blot(150.0, (1.3, 0.2, 0.9), 0.55), col, (0.07, 0.055, 0.035))
    col = g.mix(blot(200.0, (2.1, 1.7, 0.3), 0.6), col, (0.008, 0.008, 0.007))
    rgh = g.math("ADD", 0.38, g.math("MULTIPLY", g.noise(60.0, 3.0, vector=P), 0.12))
    height = g.math("MULTIPLY", g.noise(400.0, 3.0, vector=P), 0.1)
    return col, rgh, height


def crested(z_bands):
    """Painted cresting: bands [(z0, z1, color), ...] along the shaft, the paint chipped."""
    def post(g, W, P, col, rgh, met, height):
        z = g.separate(attr(g))[2]
        chip = g.ramp(g.noise(90.0, 5.0, 0.7, P), 0.66, 0.6)
        for z0, z1, c in z_bands:
            b = g.math("MULTIPLY", band(g, z, z0, z1, 0.0003), chip)
            col = g.mix(b, col, c)
            rgh = g.mixf(b, rgh, 0.4)
        return wound(g, W, P, col, rgh, met, height)
    return post


def snapped(z_break):
    """The fresh broken wood at the snap: pale, fibrous, rough."""
    def post(g, W, P, col, rgh, met, height):
        z = g.separate(attr(g))[2]
        fresh = g.ramp(z, z_break - 0.006, z_break - 0.001)
        fib = g.noise(1.0, 4.0, 0.6, mapping(g, attr(g), scale=(1500.0, 1500.0, 40.0)))
        fc = g.mix(fib, (0.2, 0.14, 0.08), (0.3, 0.22, 0.13))
        col = g.mix(fresh, col, fc)
        rgh = g.mixf(fresh, rgh, 0.85)
        height = g.math("ADD", height, g.math("MULTIPLY", fresh, g.math("MULTIPLY", fib, 1.2)))
        return wound(g, W, P, col, rgh, met, height)
    return post


def wound(g, W, P, col, rgh, met, height):
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.07, soak=0.025)


def shaft_wear(name, base, post, seed, paint=(0.1, 0.07, 0.04)):
    return wear(name, paint, rough=0.5, base=base, post=post, seed=seed, scratches=0.5,
                scratch_col=(0.24, 0.2, 0.14), dark_scratches=0.5, scuffs=0.5, scuff_col=(0.16, 0.13, 0.09),
                edges=0.0, dirt=0.6, dirt_range=(0.16, 0.05), grime=0.9, dust=0.25, specks=0.7, blood=0.35, bump=0.35,
                dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))


def vane_post(g, W, P, col, rgh, met, height):
    L = attr(g)
    nick = g.ramp(g.noise(1.0, 3.0, 0.6, mapping(g, L, scale=(300.0, 300.0, 90.0))), 0.64, 0.7)
    col = g.mix(g.math("MULTIPLY", nick, 0.6), col, tk._darker(g, col, 0.35))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", nick, 0.8))
    return gore(g, W, P, col, rgh, met, height, amount=0.8, reach=0.3, soak=0.004)


def vane_mat(name, color, seed):
    return wear(name, color, rough=0.5, post=vane_post, seed=seed, tone=0.3, scratches=0.4,
                scratch_col=tuple(c * 1.6 + 0.03 for c in color), dark_scratches=0.4, scuffs=0.6,
                scuff_col=tuple(c * 1.4 + 0.02 for c in color), edges=0.6, edge_col=tuple(c * 1.9 + 0.04 for c in color),
                dirt=0.6, dirt_range=(0.16, 0.05), grime=0.8, dust=0.35, specks=0.6, blood=0.3, bump=0.3,
                dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))


def barred(g, W, P):
    """A barred turkey wing feather: brown and buff bars across, the barbs running out diagonally, darker shaft."""
    L = attr(g)
    x, y, z = g.separate(L)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    along = g.math("ADD", z, g.math("MULTIPLY", r, 1.4))  # barbs sweep back from the quill
    bars = g.ramp(g.math("SINE", g.math("MULTIPLY", g.math("ADD", along, g.math("MULTIPLY", g.noise(30.0, 3.0, vector=P), 0.004)),
                                         700.0)), -0.15, 0.25)
    col = g.mix(bars, (0.035, 0.024, 0.016), (0.16, 0.13, 0.095))
    barbs = g.noise(1.0, 2.0, 0.5, mapping(g, Q_barbs(g, L), scale=(2600.0, 1.0, 1.0)))
    col = g.mix(g.math("MULTIPLY", barbs, 0.5), col, tk._darker(g, col, 0.55))
    rgh = g.math("ADD", 0.6, g.math("MULTIPLY", barbs, 0.15))
    height = g.math("MULTIPLY", barbs, 0.6)
    return col, rgh, height


def Q_barbs(g, L):
    """Coordinates whose x runs across the barbs (they sweep back from the quill)."""
    x, y, z = g.separate(L)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", x, x), g.math("MULTIPLY", y, y)))
    c = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("SUBTRACT", z, g.math("MULTIPLY", r, 1.4)), c.inputs[0])
    return c.outputs[0]


def feather_post(g, W, P, col, rgh, met, height):
    """Matted and split: dark gaps where the barbs have parted, dirt and blood."""
    split = g.ramp(g.noise(1.0, 3.0, 0.6, mapping(g, Q_barbs(g, attr(g)), scale=(260.0, 1.0, 1.0), loc=(0.0, 0.3, 0.7))),
                   0.66, 0.72)
    col = g.mix(g.math("MULTIPLY", split, 0.8), col, (0.015, 0.012, 0.01))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", split, 1.0))
    return gore(g, W, P, col, rgh, met, height, amount=0.8, reach=0.3, soak=0.004)


feather_mat = wear("Feather", (0.1, 0.08, 0.06), rough=0.6, base=barred, post=feather_post, seed=45.0,
                   scratches=0.0, scuffs=0.3, scuff_col=(0.12, 0.1, 0.08), edges=0.4, edge_col=(0.16, 0.13, 0.1),
                   dirt=0.6, dirt_range=(0.16, 0.05), grime=0.8, dust=0.3, specks=0.5, blood=0.35, bump=0.4,
                   dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))
nock_mat = wear("ArrowNock", (0.02, 0.03, 0.018), rough=0.35, seed=46.0, scratches=0.5,
                scratch_col=(0.1, 0.12, 0.09), scuffs=0.5, scuff_col=(0.05, 0.06, 0.045), edges=0.7,
                edge_col=(0.12, 0.14, 0.1), dirt=0.6, dirt_range=(0.16, 0.05), grime=0.9, dust=0.2, specks=0.5,
                bump=0.3)


# ---------------------------------------------------------------- arrow parts

def shaft(name, length, r, mat, M, z0=0.0):
    zs = [z0 + (length - z0) * k / 6 for k in range(7)]
    prof = [(z0, r * 0.85), (z0 + 0.002, r)] + [(z, r) for z in zs[1:]]
    return lathe(name, prof, 8, mat, M, smooth=50, phase=math.pi / 8)


def nock(name, z, r, M):
    """A snap nock: a collar over the shaft end flaring a little to the throat (the slot is painted dark)."""
    prof = [(z - 0.004, r * 0.98), (z, r * 1.08), (z + 0.007, r * 1.18), (z + 0.012, r * 1.1), (z + 0.0125, r * 0.6),
            (z + 0.0127, 0.0)]
    return lathe(name, prof, 8, nock_mat, M, smooth=40, phase=math.pi / 8)


def vanes(prefix, z0, z1, r, h, mats, M, start=0.0, torn=None, shape="parabolic", thick=0.0007, twist=0.5):
    out = []
    for k, mat in enumerate(mats):
        if shape == "parabolic":
            pts = [(r - 0.0004, z0 - 0.002)]
            for i in range(1, 8):
                t = i / 7
                pts.append((r + h * (1 - (1 - t) ** 2.2), z0 + (z1 - z0 - 0.008) * t))
            pts += [(r + h * 0.6, z1), (r - 0.0004, z1)]
        else:  # a shield-cut feather with a ragged edge
            prof = [(0.0, 0.0), (0.1, 0.22), (0.25, 0.48), (0.42, 0.68), (0.58, 0.8), (0.66, 0.74), (0.72, 0.9),
                    (0.84, 0.98), (0.93, 1.0), (0.985, 0.45)]
            pts = [(r - 0.0004, z0 - 0.002)]
            for i, (t, f) in enumerate(prof[1:]):
                rag = 0.8 + 0.2 * hash01(k, i, 3.0) if 0 < i < len(prof) - 2 else 1.0
                pts.append((r + h * f * rag, z0 + (z1 - z0) * t))
            pts.append((r - 0.0004, z1))
        if torn is not None and k == torn[0]:
            for i, cut in torn[1]:
                rr, zz = pts[i]
                pts[i] = (r + (rr - r) * cut, zz)
        out.append(fin("%s%d" % (prefix, k), pts, thick, start + math.radians(120 * k), mat, M, twist=twist))
    return out


def splinters(name, z, r, mat, M, seed):
    """The jagged ends of a snapped shaft: a few long slivers and short teeth round the break."""
    out = []
    for k in range(7):
        a = 2 * math.pi * (k / 7 + 0.1 * hash01(seed, k))
        length = 0.003 + 0.016 * hash01(seed, k, 1.0) ** 2
        lean = 0.0015 * hash01(seed, k, 2.0)  # bent out a little where it tore
        w = r * (0.25 + 0.25 * hash01(seed, k, 3.0))
        pts = [(r * 0.55, z - 0.006), (r * 0.97, z - 0.006), (r * 0.97 + lean * 0.4, z + length * 0.4),
               (r * 0.8 + lean, z + length), (r * 0.62 + lean * 0.5, z + length * 0.55)]
        out.append(fin("%s%d" % (name, k), pts, w, a, mat, M, smooth=20))
    return out


# ---------------------------------------------------------------- the arrows

R_CARBON, R_WOOD = 0.0037, 0.0042
SINK = 0.035


def place(aim, d_in, bones=None, roll=0.0):
    """The arrow's frame: local z out of the body along its line, z 0 at its buried end SINK inside the stand-in."""
    d = Vector(d_in).normalized()
    entry = skin(aim, d, bones)
    m = frame(entry + d * SINK, -d, (0.0, 0.0, 1.0)) @ Matrix.Rotation(roll, 4, "Z")
    return entry, m


# ---------------------------------------------------------------- more shafts

def carbon_base(g, W, P):
    """Plain black carbon under a satin coat gone dull: a faint lengthwise weave, rubbed grey in streaks."""
    L = attr(g)
    weave = g.noise(1.0, 2.0, 0.5, mapping(g, L, scale=(1500.0, 1500.0, 60.0)))
    col = g.mix(g.math("MULTIPLY", weave, 0.5), (0.012, 0.012, 0.013), (0.022, 0.022, 0.024))
    rub = g.ramp(g.noise(1.0, 3.0, 0.5, mapping(g, L, scale=(300.0, 300.0, 8.0))), 0.6, 0.72)
    col = g.mix(g.math("MULTIPLY", rub, 0.6), col, (0.045, 0.044, 0.043))
    rgh = g.math("ADD", 0.36, g.math("MULTIPLY", rub, 0.2))
    height = g.math("MULTIPLY", weave, 0.12)
    return col, rgh, height


def alu_base(g, W, P):
    """Anodized aluminum in a dark olive camo print, the print rubbed through to bare grey metal in places."""
    L = attr(g)
    Q = mapping(g, L, scale=(1.0, 1.0, 0.4), loc=(1.3, 0.2, 0.0))

    def blot(scale, seed, lo):
        return g.ramp(g.noise(scale, 3.0, 0.55, mapping(g, Q, loc=seed), 0.8), lo, lo + 0.02)
    col = g.mix(blot(110.0, (0.4, 0.1, 0.8), 0.5), (0.03, 0.034, 0.018), (0.016, 0.017, 0.011))
    col = g.mix(blot(170.0, (2.2, 0.6, 0.1), 0.58), col, (0.05, 0.043, 0.026))
    bare = g.ramp(g.noise(1.0, 4.0, 0.6, mapping(g, L, scale=(260.0, 260.0, 10.0))), 0.64, 0.7)
    col = g.mix(bare, col, (0.11, 0.11, 0.105))
    rgh = g.mixf(bare, 0.42, 0.32)
    height = g.math("MULTIPLY", g.noise(300.0, 3.0, vector=P), 0.08)
    return col, rgh, height


def shaft_metal(name, base, post, seed, metal):
    return wear(name, (0.03, 0.03, 0.02), rough=0.45, metal=metal, base=base, post=post, seed=seed, scratches=0.6,
                scratch_col=(0.12, 0.12, 0.11), scratch_metal=metal, dark_scratches=0.4, scuffs=0.5,
                scuff_col=(0.05, 0.05, 0.045), edges=0.0, dirt=0.6, dirt_range=(0.16, 0.05), grime=0.9, dust=0.25,
                specks=0.7, blood=0.35, bump=0.3, dirt_col=((0.03, 0.024, 0.017), (0.08, 0.065, 0.045)))


carbon_camo = shaft_wear("PinCamo", camo_base, wound, 51.0, paint=(0.03, 0.03, 0.02))
carbon_black = shaft_metal("PinCarbon", carbon_base, wound, 52.0, 0.0)
carbon_black2 = shaft_metal("PinCarbon2", carbon_base, wound, 53.0, 0.0)
alu = shaft_metal("PinAlu", alu_base, wound, 54.0, 0.75)
cedar_snap = shaft_wear("PinCedarSnapped", wood_base((0.17, 0.105, 0.055), (0.095, 0.056, 0.028), 0.6),
                        snapped(0.035 + 0.12), 55.0)
cedar_thigh = shaft_wear("PinCedarThigh", wood_base((0.16, 0.1, 0.052), (0.09, 0.052, 0.026), 1.7),
                         snapped(0.035 + 0.15), 56.0)

# Vanes: faded, dirty colors (never neon)
v_white = vane_mat("PinVaneWhite", (0.26, 0.25, 0.225), 61.0)
v_yellow = vane_mat("PinVaneYellow", (0.2, 0.15, 0.025), 62.0)
v_orange = vane_mat("PinVaneOrange", (0.22, 0.068, 0.015), 63.0)
v_black = vane_mat("PinVaneBlack", (0.018, 0.018, 0.017), 64.0)
v_green = vane_mat("PinVaneGreen", (0.045, 0.09, 0.028), 65.0)
v_red = vane_mat("PinVaneRed", (0.16, 0.02, 0.014), 66.0)


# ---------------------------------------------------------------- the eight arrows

TORSO_HI = ("Spine2",)
TORSO_LO = ("Hips", "Spine2")
pieces = {"Spine2": [], "Spine1": [], "LeftArm": [], "RightUpLeg": []}
entries = []


def arrow(tag, bone, aim, d_in, bones, out, shaft_mat, r, roll=0.0, fletch=None, snap=False, seed=1.0):
    """One arrow `out` meters out of the stand-in (its head buried SINK past the skin). fletch = (vane materials,
    shape, height, length, torn) or None; snap leaves a splintered stub."""
    entry, M = place(aim, d_in, bones, roll)
    length = SINK + out
    objs = [shaft("Shaft" + tag, length, r, shaft_mat, M)]
    if snap:
        objs += splinters("Splinter" + tag, length, r, shaft_mat, M, seed)
    else:
        objs.append(nock("Nock" + tag, length, r, M))
        mats, shape, h, flen, torn = fletch
        z1 = length - 0.022
        if shape == "shield":
            objs += vanes("Vane" + tag, z1 - flen, z1, r, h, mats, M, start=roll + 0.6, shape="shield",
                          thick=0.0006, twist=0.4, torn=torn)
        else:
            objs += vanes("Vane" + tag, z1 - flen, z1, r, h, mats, M, start=roll + 0.3, torn=torn)
    pieces[bone] += objs
    entries.append((tag, entry, M))
    return entry, M


# Upper back: high on the left shoulder blade, shot from behind and above
arrow("U1", "Spine2", (0.085, 0.12, 1.43), (-0.12, -1.0, -0.5), TORSO_HI, 0.47, carbon_camo, 0.0037, roll=0.4,
      fletch=((v_white, v_yellow, v_yellow), "parabolic", 0.015, 0.1, (1, [(4, 0.45), (5, 0.3), (6, 0.55)])))
# Low on the right shoulder blade, from behind and the right, a little below
arrow("U2", "Spine2", (-0.075, 0.12, 1.33), (0.22, -1.0, 0.16), TORSO_HI, 0.5, alu, 0.0044, roll=1.1,
      fletch=((v_black, v_orange, v_orange), "parabolic", 0.016, 0.11, None))
# Between them, a cedar shaft snapped off 12 cm out
arrow("U3", "Spine2", (0.01, 0.12, 1.47), (0.05, -1.0, 0.22), TORSO_HI, 0.12, cedar_snap, 0.0042, roll=2.0,
      snap=True, seed=7.0)
# The chest, from the front: over the heart, a little from above and the left
arrow("C1", "Spine2", (0.07, -0.05, 1.37), (-0.12, 1.0, -0.14), TORSO_HI, 0.43, carbon_black, 0.0037, roll=0.9,
      fletch=((v_black, v_red, v_red), "parabolic", 0.015, 0.1, (2, [(5, 0.5), (6, 0.35)])))
# Lower back: a cedar target arrow with feathers and cresting on the right, from behind and above
L1_LEN = SINK + 0.42
F0 = L1_LEN - 0.022 - 0.105  # where its feathers start
cedar_crest = shaft_wear("PinCedarCrested", wood_base((0.19, 0.12, 0.062), (0.11, 0.066, 0.032), 2.3),
                         crested([(F0 - 0.034, F0 - 0.02, (0.012, 0.011, 0.01)), (F0 - 0.019, F0 - 0.017, (0.3, 0.28, 0.24)),
                                  (F0 - 0.016, F0 - 0.009, (0.03, 0.05, 0.11)), (F0 - 0.008, F0 - 0.006, (0.3, 0.28, 0.24)),
                                  (F0 - 0.005, F0 - 0.001, (0.012, 0.011, 0.01))]), 57.0)
arrow("L1", "Spine1", (-0.065, 0.1, 1.1), (0.14, -1.0, -0.32), TORSO_LO, 0.42, cedar_crest, 0.0042, roll=2.1,
      fletch=((feather_mat,) * 3, "shield", 0.013, 0.105, None))
# Left of the spine, lower: shot from behind and a little below, sticking out back and slightly down
arrow("L2", "Spine1", (0.06, 0.1, 1.03), (-0.08, -1.0, 0.2), TORSO_LO, 0.45, carbon_black2, 0.0037, roll=0.2,
      fletch=((v_green, v_green, v_white), "parabolic", 0.015, 0.1, (0, [(3, 0.6), (4, 0.4), (5, 0.5)])))
# The back of the left upper arm, from behind and outside
arrow("A1", "LeftArm", (0.27, 0.085, 1.375), (-0.38, -0.92, 0.12), ("LeftArm",), 0.4, carbon_black, 0.0037, roll=1.6,
      fletch=((v_white, v_white, v_red), "parabolic", 0.015, 0.1, None))
# The front of the right thigh, from the front and the right, snapped off 15 cm out
arrow("T1", "RightUpLeg", (-0.13, -0.03, 0.76), (0.4, 1.0, 0.22), ("RightUpLeg",), 0.15, cedar_thigh, 0.0042,
      roll=0.7, snap=True, seed=11.0)

all_pieces = []
for bone, objs in pieces.items():
    for p in objs:
        zk.on(p, bone, "Arrows")
    all_pieces += objs
for tag, e, M in entries:
    out = (M.col[2].to_3d()).normalized()
    print("[%s] arrow %s enters the stand-in at (%.3f, %.3f, %.3f), out along (%.2f, %.2f, %.2f)" % (NAME, tag, *e, *out))
export(all_pieces)
zk.previews(SCRIPT, PREVIEWS, Vector((0.0, 0.1, 1.1)), distance=2.4)
close_up("back", (-0.45, 1.0, 0.35), Vector((0.0, 0.3, 1.25)), distance=1.1)
close_up("front", (0.4, -1.0, 0.25), Vector((0.0, -0.15, 1.1)), distance=1.2)
print("[%s] done" % SCRIPT)
