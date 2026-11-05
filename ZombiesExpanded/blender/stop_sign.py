"""StopSign (rare showpiece): a STOP sign rammed through the belly. The galvanized U-channel post, bent nearly square
where it hit, runs in at the front a little left of the navel and out the back; in front it bends up behind the
octagon (48 cm, 2.5 mm aluminum), which hangs crooked on its one remaining bolt (the top one tore out) about 35 cm
in front of the belly, tipped down and turned a little aside. The red sheeting is sun-faded and chalky, the white
border and letters dirty and peeling at the edges, the face dented, its bottom right corner folded back and two
bullet holes through it. Out the back the post runs on 30 cm to its torn bottom end, still set in a clump of
concrete footing caked with soil; that end went through him first, so it and the clump are soaked in blood.

The post passes straight through the body, hidden inside it. One part on Spine1: "Spine1#Sign".

    blender -b --factory-startup --python stop_sign.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT = "StopSign", "stop_sign"
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

import numpy as np  # noqa: E402

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
    """A small lumpy blob (a clot, a scrap of flesh): a squashed sphere along `axes`, pushed about by noise."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=1.0)
    for v in bm.verts:
        k = 1.0 + lump * noise.noise(v.co * 2.2 + Vector((seed, seed * 0.7, seed * 1.3)))
        v.co = Vector(center) + (axes[0] * (v.co.x * radii[0]) + axes[1] * (v.co.y * radii[1])
                                 + axes[2] * (v.co.z * radii[2])) * k
    return tk.smooth(tk.mesh_object(name, bm, mat), 70)


def splat(g, P, col, rgh, met, height, cover, seed=0.0):
    """Blood soaked over a fraction `cover` (0-1 signal) of a surface: clotted, drying dark at the edges."""
    fresh = g.ramp(g.noise(9.0, 4.0, vector=mapping(g, P, loc=(1.1 + seed, 0.3, 0.6))), 0.45, 0.72)
    bc = g.mix(fresh, (0.028, 0.005, 0.004), (0.07, 0.01, 0.007))
    clot = g.math("MULTIPLY", g.ramp(g.noise(24.0, 5.0, 0.6, P), 0.5, 0.7), cover)
    bc = g.mix(clot, bc, (0.016, 0.003, 0.002))
    col = g.mix(cover, col, bc)
    rgh = g.mixf(cover, rgh, g.mixf(fresh, 0.55, 0.32))
    met = g.mixf(cover, met, 0.0)
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", cover, 0.3), g.math("MULTIPLY", clot, 1.0)))
    return col, rgh, met, height


# ---------------------------------------------------------------- the post's line

D_T = Vector((0.0, 1.0, 0.08)).normalized()  # through the belly, front to back and a little up
AIM = Vector((0.0, 0.02, 1.03))  # inside the belly
BELLY = ("Hips", "Spine2")
E_F = skin(AIM, D_T, BELLY)  # in at the front
E_B = skin(AIM, -D_T, BELLY)  # out at the back
BACK_OUT = 0.30  # the torn bottom end, 30 cm out the back
FRONT_RUN = 0.215  # straight out of the belly before it bends up
R_BEND = 0.075
U_S = Vector((-0.04, -0.27, 1.0)).normalized()  # up the bent top of the post (leaning forward, a little right)
H0 = -D_T  # heading out of the belly, forward
A_B = H0.cross(U_S).normalized()  # the axis it was bent about (across the channel)
R_S = -A_B  # the sign's right (+X, reading the letters from the front)
N_S = R_S.cross(U_S).normalized()  # the sign's face: forward and tipped down
V_LEN = 0.415  # the post's straight top: from the bend up behind the sign
BOLT_V = -0.185  # the bottom bolt, up the post from the bend's end + 0.215
TOP_BOLT_V = 0.185  # the top bolt hole, torn out
CROOKED = math.radians(-11.0)  # the sign turned on its one bolt
APO = 0.24  # the octagon: 48 cm across the flats
T_SIGN = 0.0025


def post_path():
    """The post's centerline on its web's face, from the torn bottom end (out the back) to the top (behind the
    sign), and each point's distance along it. Returns points and the indices of the two wounds and the bend's end."""
    P = []
    end = E_B + D_T * BACK_OUT
    for s in (0.0, 0.02, 0.07, 0.12, 0.2, 0.26, 0.285, 0.3):
        P.append(end - D_T * s)
    i_back = len(P) - 1
    thru = (E_F - E_B).length
    for t in (0.04, 0.5, thru - 0.04):
        P.append(E_B - D_T * t)
    P.append(E_F)
    i_front = len(P) - 1
    for s in (0.015, 0.035, 0.08, 0.15, FRONT_RUN):
        P.append(E_F + H0 * s)
    F1 = P[-1]
    n_c = (U_S - H0 * H0.dot(U_S)).normalized()
    ang = H0.angle(U_S)
    center = F1 + n_c * R_BEND
    for k in range(1, 9):
        phi = ang * k / 8
        P.append(center - n_c * (R_BEND * math.cos(phi)) + H0 * (R_BEND * math.sin(phi)))
    VB = P[-1]
    i_bend = len(P) - 1
    for s in (0.03, 0.12, 0.3, V_LEN):
        P.append(VB + U_S * s)
    return P, i_back, i_front, i_bend


PATH, I_BACK, I_FRONT, I_BEND = post_path()
S_PATH = [0.0]
for _i in range(1, len(PATH)):
    S_PATH.append(S_PATH[-1] + (PATH[_i] - PATH[_i - 1]).length)
S_BACK, S_FRONT, S_BEND = S_PATH[I_BACK], S_PATH[I_FRONT], S_PATH[I_BEND]
VB = PATH[I_BEND]
BOLT = VB + U_S * (0.215 + BOLT_V) + N_S * 0.0002  # where the bolt goes through the post's web
SIGN_C0 = VB + U_S * 0.215 + N_S * (0.0002 + T_SIGN / 2 + 0.0004)  # the sign's middle before it turned

# The sign's frame after turning about its bolt (in its own plane)
_rot = Matrix.Rotation(CROOKED, 3, N_S)
SR, SU = _rot @ R_S, _rot @ U_S
BOLT_C = SIGN_C0 + U_S * BOLT_V
SIGN_C = BOLT_C + _rot @ (SIGN_C0 - BOLT_C)


def sign_point(u, v, w=0.0):
    return SIGN_C + SR * u + SU * v + N_S * w


# ---------------------------------------------------------------- the letters, as a mask image for the sign's face

HALF = 0.262  # the mask covers the sign's u, v from -HALF to HALF
MASK_RES = 1024


def letter_mask():
    """STOP set in a condensed bold face, 16 cm high and 35 cm wide, rasterized into a Non-Color image."""
    cu = bpy.data.curves.new("StopText", "FONT")
    cu.body = "STOP"
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 10
    cu.fill_mode = "BOTH"
    for path in ("C:/Windows/Fonts/ARIALNB.TTF", "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(path):
            cu.font = bpy.data.fonts.load(path, check_existing=True)
            break
    cu.space_character = 1.05
    ob = tk.link(bpy.data.objects.new("StopText", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob)
    me.calc_loop_triangles()
    V = np.array([v.co[:2] for v in me.vertices], dtype=np.float64)
    T = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int64)
    lo, hi = V.min(axis=0), V.max(axis=0)
    V = (V - (lo + hi) / 2) * np.array([0.35 / (hi[0] - lo[0]), 0.16 / (hi[1] - lo[1])])
    N = MASK_RES * 2
    px = 2 * HALF / N
    mask = np.zeros((N, N), dtype=bool)
    for a, b, c in T:
        pa, pb, pc = V[a], V[b], V[c]
        x0 = max(0, int((min(pa[0], pb[0], pc[0]) + HALF) / px) - 1)
        x1 = min(N, int((max(pa[0], pb[0], pc[0]) + HALF) / px) + 2)
        y0 = max(0, int((min(pa[1], pb[1], pc[1]) + HALF) / px) - 1)
        y1 = min(N, int((max(pa[1], pb[1], pc[1]) + HALF) / px) + 2)
        if x1 <= x0 or y1 <= y0:
            continue
        xs = -HALF + (np.arange(x0, x1) + 0.5) * px
        ys = -HALF + (np.arange(y0, y1) + 0.5) * px
        X, Y = np.meshgrid(xs, ys)

        def edge(p, q):
            return (q[0] - p[0]) * (Y - p[1]) - (q[1] - p[1]) * (X - p[0])
        e0, e1, e2 = edge(pa, pb), edge(pb, pc), edge(pc, pa)
        inside = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
        mask[y0:y1, x0:x1] |= inside
    m = mask.reshape(MASK_RES, 2, MASK_RES, 2).mean(axis=(1, 3)).astype(np.float32)
    img = bpy.data.images.new("StopLetters", MASK_RES, MASK_RES, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((MASK_RES, MASK_RES, 4), dtype=np.float32)
    rgba[..., 0] = m
    rgba[..., 1] = m
    rgba[..., 2] = m
    img.pixels.foreach_set(rgba.ravel())
    print("[%s] letters: %d triangles rasterized, %.1f%% of the mask" % (SCRIPT, len(T), 100 * m.mean()))
    return img


LETTERS = letter_mask()


# ---------------------------------------------------------------- materials

HOLES = [(0.052, 0.012, 1.0), (0.158, 0.118, 2.0)]  # two bullet holes (u, v, seed)


def hole_marks(g, u, v):
    """The bullet holes (and the torn top bolt hole): black hole, bright torn petals, paint chipped round them.
    Returns (hole, petals, chipped)."""
    hole_m, pet_m, chip_m = None, None, None
    for hu, hv, seed in HOLES + [(0.0, TOP_BOLT_V + 0.004, 3.0)]:
        du, dv = g.math("SUBTRACT", u, hu), g.math("SUBTRACT", v, hv)
        if seed == 3.0:  # the bolt tore up through the edge: a stretched slot
            dv = g.math("MULTIPLY", dv, 0.45)
        r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", du, du), g.math("MULTIPLY", dv, dv)))
        ang = g.math("ARCTAN2", dv, du)
        wob = g.math("MULTIPLY", g.math("SINE", g.math("ADD", g.math("MULTIPLY", ang, 7.0), seed)), 0.0012)
        h = g.ramp(g.math("ADD", r, wob), 0.0046, 0.0036)
        p = g.math("MULTIPLY", g.ramp(g.math("ADD", r, g.math("MULTIPLY", wob, 1.6)), 0.0092, 0.0068),
                   g.math("SUBTRACT", 1.0, h))
        c = g.ramp(g.math("ADD", r, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(260.0, 3.0, vector=g.coords()), 0.5),
                                            0.008)), 0.0145, 0.011)
        hole_m = h if hole_m is None else g.math("MAXIMUM", hole_m, h)
        pet_m = p if pet_m is None else g.math("MAXIMUM", pet_m, p)
        chip_m = c if chip_m is None else g.math("MAXIMUM", chip_m, c)
    return hole_m, pet_m, chip_m


def sign_material(name, seed):
    """The sign: on the front, red sheeting sun-faded and chalky, the white border and letters gone grey with dirt
    and peeling at the edges, rain streaks, scratches through to the aluminum, two bullet holes and the torn bolt
    hole, blood spattered up from the bottom edge; on the back and edges dull mill-finish aluminum, grimy, splashed
    with the zombie's blood."""
    mat, g = tk.new_material(name)
    W = g.coords()
    P = seeded(g, seed)
    u, v, side = g.separate(attr(g))
    front = g.ramp(side, 0.3, 0.8)
    au, av = g.math("ABSOLUTE", u), g.math("ABSOLUTE", v)
    octd = g.math("MAXIMUM", g.math("MAXIMUM", au, av), g.math("MULTIPLY", g.math("ADD", au, av), 0.70711))
    # The letters from the mask image
    uv = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("DIVIDE", g.math("ADD", u, HALF), 2 * HALF), uv.inputs[0])
    g.links.new(g.math("DIVIDE", g.math("ADD", v, HALF), 2 * HALF), uv.inputs[1])
    tex = g.node("ShaderNodeTexImage", interpolation="Linear", extension="CLIP")
    tex.image = LETTERS
    g.links.new(uv.outputs[0], tex.inputs["Vector"])
    letters = g.ramp(g.separate(tex.outputs["Color"])[0], 0.35, 0.65)
    border = band(g, octd, 0.2155, 0.2295, 0.0006)
    white = g.math("MAXIMUM", letters, border)
    # Faded red sheeting, chalky in sun-bleached blotches, darker where it stayed wet
    tone = g.noise(5.0, 4.0, 0.6, P)
    red = g.mix(g.ramp(tone, 0.3, 0.75), (0.085, 0.016, 0.012), (0.125, 0.024, 0.017))
    chalk = g.ramp(g.noise(2.5, 5.0, 0.6, P, 0.4), 0.5, 0.75)
    red = g.mix(g.math("MULTIPLY", chalk, 0.7), red, (0.13, 0.05, 0.042))
    wht = g.mix(g.ramp(tone, 0.3, 0.75), (0.16, 0.152, 0.134), (0.23, 0.222, 0.198))
    col = g.mix(white, red, wht)
    rgh = g.mixf(white, g.math("ADD", 0.5, g.math("MULTIPLY", chalk, 0.2)), 0.42)
    height = g.math("MULTIPLY", g.noise(220.0, 3.0, vector=P), 0.05)
    # Rain streaks down the face, dirt settled toward the bottom and in a grimy rim along the edge
    streak = g.ramp(g.noise(1.0, 4.0, 0.6, mapping(g, attr(g), scale=(60.0, 5.0, 1.0), loc=(seed, 0.2, 0.0))), 0.55, 0.7)
    low = g.ramp(v, 0.05, -0.24)
    rim = g.ramp(octd, 0.2, 0.24)
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", streak, 0.6), g.math("MULTIPLY", low, 0.5))
    dirt = g.math("MAXIMUM", dirt, g.math("MULTIPLY", rim, 0.7))
    dirt = g.math("MULTIPLY", dirt, g.ramp(g.noise(8.0, 5.0, 0.6, P), 0.3, 0.7))
    col = g.mix(g.math("MULTIPLY", dirt, 0.75), col, g.mix(g.noise(15.0, vector=P), (0.035, 0.028, 0.02), (0.06, 0.05, 0.036)))
    rgh = g.mixf(dirt, rgh, 0.8)
    # The aluminum: the back, the edges, and wherever the sheeting is scratched, peeled or shot through
    alu_tone = g.noise(7.0, 4.0, 0.6, P)
    alu = g.mix(alu_tone, (0.12, 0.12, 0.118), (0.17, 0.168, 0.162))
    oxide = g.ramp(g.noise(4.0, 6.0, 0.6, P, 0.5), 0.45, 0.7)
    alu = g.mix(g.math("MULTIPLY", oxide, 0.6), alu, (0.2, 0.198, 0.19))
    sc = g.math("MULTIPLY", scratch_mask(g, P, 0.02), g.ramp(g.noise(3.0, 3.0, vector=P), 0.38, 0.62))
    peel = g.math("MULTIPLY", g.ramp(octd, 0.233, 0.2395), g.ramp(g.noise(30.0, 5.0, 0.65, P), 0.4, 0.55))
    peel = g.math("MAXIMUM", peel, g.ramp(g.noise(11.0, 8.0, 0.7, P, 0.4), 0.71, 0.73))
    hole, petals, chipped = hole_marks(g, u, v)
    bare = g.math("MAXIMUM", g.math("MAXIMUM", g.math("MULTIPLY", sc, 0.9), peel), g.math("MAXIMUM", petals, chipped))
    bare = g.math("MAXIMUM", bare, g.math("SUBTRACT", 1.0, front))
    col = g.mix(bare, col, alu)
    rgh = g.mixf(bare, rgh, g.mixf(oxide, 0.4, 0.6))
    met = g.mixf(bare, 0.0, g.mixf(oxide, 0.85, 0.55))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", g.math("MAXIMUM", peel, sc), 0.4))
    height = g.math("ADD", height, g.math("MULTIPLY", petals, 0.8))
    col = g.mix(hole, col, (0.004, 0.003, 0.003))
    rgh = g.mixf(hole, rgh, 0.9)
    met = g.mixf(hole, met, 0.0)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", hole, 1.5))
    # Grime over everything, darker on the back, dust on top edges
    grime = g.math("MAXIMUM", tk._grime(g, 0.7), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, front),
                                                        g.ramp(g.noise(6.0, 6.0, 0.6, P, 0.5), 0.35, 0.6)))
    col = g.mix(g.math("MULTIPLY", grime, 0.7), col, (0.03, 0.025, 0.02))
    rgh = g.mixf(grime, rgh, 0.85)
    met = g.mixf(grime, met, 0.0)
    # Blood: spattered up the front from the bottom edge, splashed over the back where it rammed into him
    sp = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(0.3, 0.1, 0.7)), 90.0), 0.15, 0.06),
                g.ramp(g.noise(9.0, 3.0, vector=P), 0.4, 0.55))
    smear = g.ramp(g.noise(5.0, 6.0, 0.65, P, 1.0), 0.56, 0.64)
    front_blood = g.math("MULTIPLY", g.math("MAXIMUM", sp, g.math("MULTIPLY", smear, 0.8)), g.ramp(v, -0.02, -0.2))
    back_blood = g.math("MULTIPLY", g.math("MAXIMUM", g.math("MULTIPLY", sp, 1.2), smear), g.ramp(v, 0.15, -0.1))
    blood = g.mixf(front, back_blood, g.math("MULTIPLY", front_blood, 0.85))
    blood = g.math("MINIMUM", blood, 1.0)
    col, rgh, met, height = splat(g, P, col, rgh, met, height, blood, seed=seed)
    col, rgh, met = tk._grit(g, col, rgh, met, 0.25)
    return tk.finish(mat, g, col, met, rgh, g.bump(height, 0.35, 0.0015))


def galvanized(g, W, P):
    """Galvanized steel gone dull grey: zinc spangle mottling, white zinc bloom, the punched holes dark."""
    L = attr(g)
    a, b, s = g.separate(L)
    tone = g.noise(18.0, 4.0, 0.6, P)
    spangle = voronoi(g, mapping(g, P, loc=(0.3, 0.6, 0.1)), 60.0)
    col = g.mix(g.ramp(spangle, 0.2, 0.5), (0.085, 0.087, 0.088), (0.12, 0.122, 0.122))
    col = g.mix(g.math("MULTIPLY", g.ramp(tone, 0.3, 0.7), 0.5), col, (0.06, 0.061, 0.06))
    bloom = g.ramp(g.noise(5.0, 6.0, 0.65, P, 0.5), 0.58, 0.72)
    col = g.mix(g.math("MULTIPLY", bloom, 0.7), col, (0.2, 0.2, 0.19))
    rgh = g.math("ADD", 0.5, g.math("MULTIPLY", bloom, 0.25))
    height = g.math("MULTIPLY", g.ramp(spangle, 0.2, 0.5), 0.15)
    # Holes punched down the web on 1-inch centres
    ds = g.math("MULTIPLY", g.math("SUBTRACT", g.math("FRACT", g.math("DIVIDE", s, 0.0254)), 0.5), 0.0254)
    rr = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", a, a), g.math("MULTIPLY", ds, ds)))
    web = g.ramp(b, -0.0085, -0.006)
    holes = g.math("MULTIPLY", g.ramp(rr, 0.0049, 0.0041), web)
    col = g.mix(holes, col, (0.006, 0.005, 0.004))
    rgh = g.mixf(holes, rgh, 0.95)
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", holes, 1.2))
    return col, rgh, height


def post_post(g, W, P, col, rgh, met, height):
    """Rust where the zinc wore through (worst toward the buried end), the soil line, and blood: everything that
    went through him smeared and clotted, the wounds soaked."""
    a, b, s = g.separate(attr(g))
    low = g.ramp(s, 0.16, 0.04)
    col, rgh, met, height = rust(g, P, col, rgh, met, height, amount=0.35, scale=1.2, seed=0.4)
    rc = g.math("MULTIPLY", low, g.ramp(g.noise(8.0, 6.0, 0.6, P, 0.4), 0.3, 0.55))
    col = g.mix(rc, col, (0.06, 0.028, 0.013))
    rgh = g.mixf(rc, rgh, 0.85)
    met = g.mixf(rc, met, 0.05)
    through = g.ramp(s, S_FRONT + 0.02, S_FRONT - 0.005)
    cover = g.math("MULTIPLY", through, g.ramp(g.math("ADD", g.noise(7.0, 5.0, 0.6, P),
                                                      g.math("MULTIPLY", g.noise(40.0, 3.0, vector=P), 0.2)), 0.44, 0.57))
    col, rgh, met, height = splat(g, P, col, rgh, met, height, cover, seed=0.3)
    return gore(g, W, P, col, rgh, met, height, amount=1.0, reach=0.09, soak=0.03)


post_mat = wear("SignPost", (0.1, 0.1, 0.1), rough=0.5, metal=0.6, base=galvanized, post=post_post, seed=81.0,
                scratches=0.6, scratch_col=(0.2, 0.2, 0.2), scratch_metal=0.9, dark_scratches=0.4, scuffs=0.4,
                scuff_col=(0.07, 0.07, 0.07), edges=0.5, edge_col=(0.2, 0.2, 0.2), edge_metal=0.9, dirt=0.6,
                dirt_range=(0.16, 0.05), grime=0.9, dust=0.2, specks=0.6, blood=0.3, bump=0.35,
                dirt_col=((0.03, 0.025, 0.018), (0.07, 0.06, 0.045)))


def clump_material(name, seed):
    """The footing's concrete: grey, gravel showing on the broken faces, caked with dried soil, then dragged
    through a body: blood soaked into it and clotted in the hollows."""
    mat, g = tk.new_material(name)
    P = seeded(g, seed)
    tone = g.noise(7.0, detail=6.0, roughness=0.6, vector=P)
    col = g.mix(tone, (0.03, 0.029, 0.027), (0.052, 0.05, 0.046))
    cells = g.node("ShaderNodeTexVoronoi", feature="F1")
    g._in(cells, "Scale", 90.0)
    g.links.new(mapping(g, P, loc=(0.2, 0.4, 0.1)), cells.inputs["Vector"])
    stone = g.math("MULTIPLY", g.ramp(tk._sock(cells.outputs, "Distance"), 0.42, 0.3), g.ramp(g.noise(9.0, vector=P), 0.38, 0.55))
    stone_col = g.mix(g.separate(tk._sock(cells.outputs, "Color"))[0], (0.04, 0.034, 0.027), (0.12, 0.1, 0.08))
    col = g.mix(stone, col, stone_col)
    pores = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.1, 0.3, 0.6)), 420.0), 0.1, 0.04),
                   g.ramp(g.noise(5.0, vector=P), 0.45, 0.65))
    col = g.mix(pores, col, (0.012, 0.011, 0.01))
    soil = g.ramp(g.noise(4.0, 6.0, 0.65, P, 0.6), 0.45, 0.6)
    col = g.mix(g.math("MULTIPLY", soil, 0.9), col, g.mix(g.noise(25.0, vector=P), (0.03, 0.022, 0.014), (0.055, 0.04, 0.024)))
    rough = g.math("ADD", 0.86, g.math("MULTIPLY", tone, 0.08))
    height = g.math("ADD", g.math("MULTIPLY", tone, 0.35), g.math("ADD", g.math("MULTIPLY", stone, 0.15),
                                                                   g.math("MULTIPLY", pores, -0.9)))
    height = g.math("ADD", height, g.math("MULTIPLY", soil, 0.3))
    dirt = tk._grime(g, 0.8)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, (0.025, 0.02, 0.015))
    cover = g.ramp(g.math("ADD", g.noise(5.0, 6.0, 0.6, P), g.math("MULTIPLY", g.noise(30.0, 4.0, vector=P), 0.3)),
                   0.54, 0.66)
    met = 0.0
    col, rough, met, height = splat(g, P, col, rough, met, height, cover, seed=seed)
    col, rough, met = tk._grit(g, col, rough, met, 0.08)
    rough = g.math("MAXIMUM", rough, 0.74)  # dry and dusty, blood and all: no wet highlights on its flat faces
    return tk.finish(mat, g, col, met, rough, g.bump(height, 0.45, 0.002))


bolt_mat = wear("SignBolt", (0.08, 0.08, 0.078), rough=0.45, metal=0.8, seed=82.0, tone=0.3, scratches=0.5,
                scratch_col=(0.18, 0.18, 0.18), scratch_metal=1.0, scuffs=0.3, scuff_col=(0.06, 0.06, 0.06),
                edges=0.6, edge_col=(0.2, 0.2, 0.2), edge_metal=1.0, dirt=0.7, dirt_range=(0.16, 0.05), grime=1.0,
                dust=0.2, specks=0.6, bump=0.3, post=lambda g, W, P, c, r, m, h: rust(g, P, c, r, m, h, amount=0.7,
                                                                                     scale=3.0, seed=2.2))
sign_mat = sign_material("StopSignPlate", 83.0)
clump_mat = clump_material("SignFooting", 84.0)
flesh = gore_flesh("SignGore", 85.0)


# ---------------------------------------------------------------- the post

def channel_section():
    """The U-channel's outline (a across, b toward the sign: the web's face at b = 0, the flanges behind it), as a
    thin sheet's centerline thickened both ways (mitred at the corners)."""
    t = 0.0035
    line = [Vector(q) for q in ((-0.031, -0.0225), (-0.0195, -0.0225), (-0.015, -t / 2), (0.015, -t / 2),
                                (0.0195, -0.0225), (0.031, -0.0225))]
    n = len(line)
    outer, inner = [], []
    for i in range(n):
        ns = []
        if i > 0:
            d = (line[i] - line[i - 1]).normalized()
            ns.append(Vector((-d.y, d.x)))
        if i < n - 1:
            d = (line[i + 1] - line[i]).normalized()
            ns.append(Vector((-d.y, d.x)))
        m = (ns[0] + ns[-1]).normalized()
        k = 1.0 / max(0.5, m.dot(ns[0]))
        outer.append(line[i] + m * (t / 2 * k))
        inner.append(line[i] - m * (t / 2 * k))
    return [tuple(q) for q in outer + list(reversed(inner))]


def post():
    """The channel swept along the post's line, with a flattened, torn top end."""
    sec = channel_section()
    n = len(PATH)
    T = [(PATH[min(i + 1, n - 1)] - PATH[max(i - 1, 0)]).normalized() for i in range(n)]
    bm = bmesh.new()
    rings, vals = [], []
    for i in range(n):
        nn = T[i].cross(A_B).normalized()
        squash = 1.0
        if I_BEND - 8 <= i <= I_BEND:  # the flanges folded in a little where it bent
            squash = 1.0 - 0.18 * math.sin(math.pi * (i - (I_BEND - 8)) / 8)
        ring = []
        for (a, b) in sec:
            bb = b * squash
            ring.append(bm.verts.new(PATH[i] + A_B * a + nn * bb))
            vals.append(Vector((a, bb, S_PATH[i])))
        rings.append(ring)
    m = len(sec)
    for i in range(n - 1):
        for j in range(m):
            j1 = (j + 1) % m
            bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Post", bm, post_mat)
    a = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for i, v in enumerate(vals):
        a.data[i].vector = v
    return tk.smooth(obj, 40)


def footing():
    """The clump of concrete the post was set in, torn up with it: lumpy, with two broken faces."""
    rnd = random.Random(7)
    end = PATH[0]
    side = A_B
    up = D_T.cross(A_B).normalized()
    c = end - D_T * 0.045
    pts = []
    for k in range(34):
        a = rnd.uniform(0, 2 * math.pi)
        z = rnd.uniform(-1.0, 1.0)
        rr = math.sqrt(1 - z * z)
        q = Vector((math.cos(a) * rr * 0.068, math.sin(a) * rr * 0.06, z * 0.08)) * rnd.uniform(0.75, 1.0)
        q.x += 0.012 * (1 if q.y > 0 else -0.4)
        pts.append(c + side * q.x + up * q.y + D_T * q.z)
    for nrm, off in ((side * 0.5 + up * 0.8 + D_T * 0.3, 0.035), (-side * 0.8 + D_T * 0.5, 0.04)):
        nrm = nrm.normalized()
        pts = [p - nrm * max(0.0, (p - c).dot(nrm) - off) for p in pts]
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Footing", bm, clump_mat)
    for v in obj.data.vertices:
        v.co += (v.co - c).normalized() * 0.006 * noise.noise(v.co * 40.0)
    return tk.smooth(obj, 25)


def gore_at(tag, centre, along, n, seed):
    """Lumps of torn flesh and clot stuck round the post where it comes out of the body."""
    rnd = random.Random(seed)
    up = along.cross(A_B).normalized()
    out = []
    for k in range(n):
        a = 2 * math.pi * (k + rnd.uniform(-0.3, 0.3)) / n
        off = A_B * (0.03 * math.cos(a)) + up * (-0.012 + 0.018 * math.sin(a))
        c = centre + off + along * rnd.uniform(-0.006, 0.012)
        r = rnd.uniform(0.007, 0.012)
        out.append(blob("%s%d" % (tag, k), c, (r, r * 0.7, r * 1.3), (A_B, up, along), flesh,
                        seed=seed + k * 1.7, lump=0.35))
    return out


# ---------------------------------------------------------------- the sign

def plate():
    """The octagon, 2.5 mm aluminum: rings of points from the middle out (so it can dent and fold), both faces and
    the edge. Dented all over, a big dent where it hit him, the bottom right corner folded back, dimples round the
    bullet holes. LOCAL = (u, v, side) in the sign's own (unturned) frame."""
    R_O = APO / math.cos(math.radians(22.5))
    per_side = 4
    fr = [0.0, 0.18, 0.36, 0.54, 0.7, 0.83, 0.93, 1.0]

    def outline(k):
        i, j = divmod(k, per_side)
        a0 = math.radians(22.5 + 45 * i)
        a1 = math.radians(22.5 + 45 * (i + 1))
        p0 = Vector((math.cos(a0), math.sin(a0))) * R_O
        p1 = Vector((math.cos(a1), math.sin(a1))) * R_O
        return p0.lerp(p1, j / per_side)
    m = 8 * per_side
    bolt_uv = Vector((0.0, BOLT_V))
    post_dir = Vector((-math.sin(-CROOKED), math.cos(-CROOKED)))  # the post's line in the sign's own frame

    def dent(u, v):
        p = Vector((u, v))
        d = 0.004 * noise.noise(Vector((u * 7.0, v * 7.0, 0.3))) + 0.002 * noise.noise(Vector((u * 19.0, v * 19.0, 1.7)))
        r = (p - Vector((-0.09, 0.06))).length
        d -= 0.009 * max(0.0, 1.0 - (r / 0.075)) ** 2  # pushed back where it struck him
        fold = (u - v) * 0.70711 - 0.255
        if fold > 0.0:
            d -= fold * math.sin(math.radians(24.0)) + fold * fold * 0.4
        for hu, hv, _ in HOLES:
            rh = (p - Vector((hu, hv))).length
            d -= 0.0035 * max(0.0, 1.0 - rh / 0.022) ** 2
        # held flat against the post's web along its line, so it never dents into it
        q = p - bolt_uv
        dist = abs(q.x * post_dir.y - q.y * post_dir.x)
        if dist < 0.05:
            k = smoothstep(0.02, 0.05, dist)
            d = d * k if d < 0.0 else d
        return d
    bm = bmesh.new()
    vals = []
    layers = {}
    for side in (1.0, -1.0):
        rows = []
        for fi, f in enumerate(fr):
            if f == 0.0:
                u, v = 0.0, 0.0
                w = side * T_SIGN / 2 + dent(u, v)
                rows.append([bm.verts.new(sign_point(u, v, w))])
                vals.append((u, v, side))
                continue
            row = []
            for k in range(m):
                q = outline(k) * f
                w = side * T_SIGN / 2 + dent(q.x, q.y)
                row.append(bm.verts.new(sign_point(q.x, q.y, w)))
                vals.append((q.x, q.y, side))
            rows.append(row)
        layers[side] = rows
        for k in range(m):
            f = bm.faces.new((rows[0][0], rows[1][k], rows[1][(k + 1) % m]))
        for r0, r1 in zip(rows[1:], rows[2:]):
            for k in range(m):
                k1 = (k + 1) % m
                bm.faces.new((r0[k], r1[k], r1[k1], r0[k1]))
    a, b = layers[1.0][-1], layers[-1.0][-1]
    for k in range(m):
        k1 = (k + 1) % m
        bm.faces.new((a[k], a[k1], b[k1], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = tk.mesh_object("Plate", bm, sign_mat)
    at = obj.data.attributes.new(LOCAL, "FLOAT_VECTOR", "POINT")
    for i, val in enumerate(vals):
        at.data[i].vector = val
    return tk.smooth(obj, 50)


def bolt():
    """The bottom bolt the sign hangs from: a domed carriage-bolt head on the face, the stub and nut behind the web."""
    c = BOLT_C + N_S * (T_SIGN / 2 + 0.0003)
    Mb = frame(c, N_S, SU)
    head = lathe("BoltHead", [(-0.0008, 0.0112), (0.0012, 0.011), (0.0032, 0.008), (0.0045, 0.0035), (0.0049, 0.0)], 10,
                 bolt_mat, Mb, smooth=50)
    nut_c = BOLT - N_S * 0.0045
    Mn = frame(nut_c, -N_S, SU)
    nut = lathe("Nut", [(0.0, 0.0075), (0.007, 0.0075), (0.0075, 0.006), (0.0105, 0.0042), (0.0112, 0.0)], 6, bolt_mat,
                Mn, smooth=20)
    return [head, nut]


# ---------------------------------------------------------------- build

post_obj = post()
pieces = [post_obj, footing(), plate()] + bolt()
pieces += gore_at("GoreFront", E_F + H0 * 0.004, H0, 6, 11.0)
pieces += gore_at("GoreBack", E_B + D_T * 0.004, D_T, 5, 23.0)
for p in pieces:
    zk.on(p, "Spine1", "Sign")
print("[%s] post in at (%.3f, %.3f, %.3f), out at (%.3f, %.3f, %.3f), bottom end at (%.3f, %.3f, %.3f) (%.0f cm out); "
      "bend ends at (%.3f, %.3f, %.3f)" % (SCRIPT, *E_F, *E_B, *PATH[0], 100 * (PATH[0] - E_B).length, *VB))
print("[%s] sign centre (%.3f, %.3f, %.3f), %.0f cm in front of the belly, face (%.2f, %.2f, %.2f), top z %.3f, bottom z "
      "%.3f" % (SCRIPT, *SIGN_C, 100 * (E_F.y - SIGN_C.y), *N_S,
                max(sign_point(*(Vector((math.cos(math.radians(22.5 + 45 * i)), math.sin(math.radians(22.5 + 45 * i))))
                                 * APO / math.cos(math.radians(22.5)))).z for i in range(8)),
                min(sign_point(*(Vector((math.cos(math.radians(22.5 + 45 * i)), math.sin(math.radians(22.5 + 45 * i))))
                                 * APO / math.cos(math.radians(22.5)))).z for i in range(8))))
export(pieces)
zk.previews(SCRIPT, PREVIEWS, Vector((0.0, -0.05, 1.15)), distance=2.3)
close_up("face", (0.15, -1.0, 0.15), SIGN_C, distance=0.95)
close_up("back", (-0.6, 1.0, 0.3), E_B + D_T * 0.15, distance=0.75)
print("[%s] done" % SCRIPT)
