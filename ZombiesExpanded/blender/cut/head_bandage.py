"""Head bandage: a gauze roll wrapped round the head by someone in a hurry. A first turn round the forehead and low
over the back of the head, two passes over the crown crossing near the top (their ends held at the sides), a second
turn round over everything, the end split in two and tied in a knot behind the left ear with the two tails hanging.
Grey-beige from dirt and sweat, wrinkled and frayed at the edges, and a dried blood stain soaked through over the left
forehead (dark at its rim, as dried blood is), with an older brown one at the back.

It sits clear of Joe's hair: 1.3 cm off the head hit box at the forehead, 2 cm at the sides and 1.8 at the back, the
lower edge above the brows. One part on the head: "Head#Bandage".

    blender -b --factory-startup --python head_bandage.py -- <unity models folder> <preview folder>
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

NAME, SCRIPT, BONE, PART = "HeadBandage", "head_bandage", "Head", "Bandage"
args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS = os.path.join(args[0], NAME), args[1]
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

tk.reset_scene()
zk.stage()
BODY = zk.body()
sk = zk.joe()

UP = Vector((0.0, 0.0, 1.0))
HA, HB, HR = Vector((0.0, 0.035, 1.645)), Vector((0.0, 0.035, 1.745)), 0.1  # the head hit box
T = 0.0019  # one layer of gauze
ATTR = "bd"  # per vertex: (meters along the strip, across it -1..1, which strip)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def horiz(theta):
    """Round the head: theta 0 the front (-Y), +90 degrees the zombie's left (+X)."""
    return Vector((math.sin(theta), -math.cos(theta), 0.0))


def clear(theta, e=0.0):
    """How far the gauze sits off the hit box: close over the forehead, clear of the hair at the sides and back,
    pulled down onto the hair over the crown (e: the elevation over the dome)."""
    side = 0.013 + 0.007 * math.sin(theta) ** 2 + 0.005 * max(0.0, -math.cos(theta)) ** 2
    k = math.sin(max(0.0, e)) ** 2
    return side * (1 - k) + 0.011 * k


def head_point(theta, m, lift=0.0):
    """The point on the head's offset surface at azimuth theta and meridian arc m (0 at the top of the hit box's
    straight part, z 1.745; negative down the sides, positive up over the dome), `lift` further out."""
    if m <= 0.0:
        return HB + UP * m + horiz(theta) * (HR + clear(theta) + lift)
    e = min(m / (HR + clear(theta)), math.pi / 2)
    return HB + (horiz(theta) * math.cos(e) + UP * math.sin(e)) * (HR + clear(theta, e) + lift)


def project(q, lift=0.0):
    """q dropped onto the head's offset surface (from the hit box's axis), `lift` further out; also the normal."""
    t = max(0.0, min(1.0, (q.z - HA.z) / (HB.z - HA.z)))
    c = HA.lerp(HB, t)
    n = (q - c).normalized()
    theta = math.atan2(n.x, -n.y) if abs(n.x) + abs(n.y) > 1e-6 else 0.0
    e = math.asin(max(-1.0, min(1.0, n.z)))
    return c + n * (HR + clear(theta, e) + lift), n


# ---------------------------------------------------------------- strips of gauze

def set_attr(obj, values):
    me = obj.data
    a = me.attributes.new(ATTR, "FLOAT_VECTOR", "POINT")
    for d, v in zip(a.data, values):
        d.vector = v
    return obj


def strip(name, n, point_at, width, mat, strip_id, closed=False, wobble=1.0, seed=0.0):
    """A strip of gauze along a path of n points: point_at(i, w, lift) gives the point i of the path, w across it
    (meters), lifted `lift` off whatever it lies on. Its outer face bows with the surface (three points across), the
    inner face is flat; the edges ripple and the face wrinkles a little."""
    bm = bmesh.new()
    rings, attrs = [], []
    along = 0.0
    prev = None
    for i in range(n):
        mid = point_at(i, 0.0, T)
        if prev is not None:
            along += (mid - prev).length
        prev = mid
        ring, at = [], []
        for w, lift, side in ((-1, T, -1), (0, T, 0), (1, T, 1), (1, 0.0, 1), (-1, 0.0, -1)):
            q = Vector((math.sin(along * 37.0 + seed), w * 3.1, seed * 1.7))
            rip = 0.0019 * wobble * noise.noise(Vector((along * 30.0, w * 2.0 + seed, seed))) if w else 0.0
            wr = 0.0009 * wobble * noise.noise(q) if (w == 0 and lift) else 0.0
            p = point_at(i, w * (width / 2 + rip), lift + wr)
            ring.append(bm.verts.new(p))
            at.append((along, float(side), float(strip_id)))
        rings.append(ring)
        attrs += at
    m = len(rings)
    for i in range(m if closed else m - 1):
        a, b = rings[i], rings[(i + 1) % m]
        for j in range(5):
            j1 = (j + 1) % 5
            bm.faces.new((a[j], a[j1], b[j1], b[j]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    # Outward: the outer face's middle points away from the head
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    f = bm.faces[1]  # between the middle and +edge of the outer face
    c = f.calc_center_median()
    if f.normal.dot(project(c)[1]) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    obj = tk.mesh_object(name, bm, mat)
    set_attr(obj, attrs)
    return tk.smooth(obj, 50)


# Turns round the head: the centerline's meridian height m(theta) = mid + front-back tilt * cos + side tilt * sin
TURN_A = dict(mid=0.0065, fb=0.0315, lr=0.0, width=0.062, lift=0.0)
TURN_B = dict(mid=0.011, fb=0.029, lr=0.006, width=0.054, lift=T)
N_TURN = 28


def turn_m(turn, theta):
    wob = 0.003 * noise.noise(Vector((math.cos(theta) * 1.5, math.sin(theta) * 1.5, turn["mid"] * 100.0)))
    return turn["mid"] + turn["fb"] * math.cos(theta) + turn["lr"] * math.sin(theta) + wob


def turn(name, turn_, mat, strip_id, seed):
    """A closed turn round the head, its width laid along the head's meridians."""
    thetas = [2 * math.pi * k / N_TURN for k in range(N_TURN)]

    def point_at(i, w, lift):
        th = thetas[i]
        extra = turn_["lift"]
        if turn_ is TURN_B:
            # over the crossing passes' ends at the sides
            extra += 3 * T * smoothstep(0.55, 0.85, abs(math.sin(th)))
        return head_point(th, turn_m(turn_, th) + w, extra + lift)
    return strip(name, N_TURN, point_at, turn_["width"], mat, strip_id, closed=True, seed=seed)


def crown_pass(name, tilt_deg, width, mat, strip_id, seed, layer, n=18):
    """A pass from the left side over the crown to the right, in a plane tipped `tilt_deg` forward, its ends lying
    on the first turn (and under the second)."""
    tilt = math.radians(tilt_deg)
    # the plane's in-plane directions: across the head (x) and up, tipped about x
    upv = Vector((0.0, -math.sin(tilt), math.cos(tilt)))
    side_axis = Vector((1.0, 0.0, 0.0))
    b0 = math.radians(84.0)
    pts, nrm, sides = [], [], []
    for k in range(n):
        beta = -b0 + 2 * b0 * k / (n - 1)
        d = side_axis * math.sin(beta) + upv * math.cos(beta)
        p, nn = project(HB + d * 0.3)
        pts.append(p)
        nrm.append(nn)
    for k in range(n):
        tg = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
        sides.append(tg.cross(nrm[k]).normalized())

    def point_at(i, w, lift):
        beta = -b0 + 2 * b0 * i / (n - 1)
        on_turn = T * (layer + smoothstep(math.radians(58.0), math.radians(76.0), abs(beta)))
        q, _ = project(pts[i] + sides[i] * w, on_turn + lift)
        return q
    return strip(name, n, point_at, width, mat, strip_id, seed=seed)


def knot_and_tails(mat, theta=math.radians(112.0)):
    """The bandage's end split in two and tied: a lumpy knot on the second turn behind the left ear, and its two
    tails hanging down past the ear, twisted, their ends torn."""
    m = turn_m(TURN_B, theta)
    base = head_point(theta, m, 3 * T)
    out = horiz(theta)
    pieces = []
    rot = Vector((0.0, 1.0, 0.0)).rotation_difference(out).to_matrix().to_4x4()
    for k, (size, off, turn_deg, seed) in enumerate((((0.016, 0.0095, 0.012), (0.0, 0.0, 0.0), 25.0, 2.0),
                                                     ((0.012, 0.008, 0.009), (0.008, 0.002, -0.006), -40.0, 5.0))):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        for v in bm.verts:
            c = v.co.copy()
            lump = 1.0 + 0.25 * noise.noise(c * 1.9 + Vector((seed, 5.0, 1.0)))
            v.co = Vector((c.x * size[0], c.y * size[1], c.z * size[2])) * lump + Vector(off)
        knot = tk.mesh_object("Knot%d" % k, bm, mat)
        knot.matrix_world = (Matrix.Translation(base + out * 0.004) @ rot
                             @ Matrix.Rotation(math.radians(turn_deg), 4, "Y"))
        knot.data.transform(knot.matrix_world)
        knot.matrix_world = Matrix.Identity(4)
        set_attr(knot, [(0.0, 0.0, 9.0 + k)] * len(knot.data.vertices))
        pieces.append(tk.smooth(knot, 180))
    across = UP.cross(out).normalized()  # horizontal, along the head's side
    for k, (length, lean, twist, wdt) in enumerate(((0.078, 0.18, 70.0, 0.03), (0.06, -0.12, -50.0, 0.027))):
        n = 9
        start = base + out * 0.004 + across * (0.006 if k == 0 else -0.007) - UP * 0.006
        path = []
        for i in range(n):
            f = i / (n - 1)
            p = start - UP * (length * f) + across * (lean * length * f * f) + out * (0.006 * math.sin(f * 2.5))
            # keep clear of the hair: never closer than the head's offset surface plus a bit
            q, nn = project(p, 0.004)
            if (p - q).dot(nn) < 0:
                p = q
            path.append(p)

        def point_at(i, w, lift, path=path, twist=twist):
            tg = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
            ang = math.radians(twist) * i / (n - 1)
            side = (across * math.cos(ang) + out * math.sin(ang))
            side = (side - tg * side.dot(tg)).normalized()
            nrm = tg.cross(side)
            if nrm.dot(out) < 0:
                nrm = -nrm
            taper = 1.0 - 0.25 * (i / (n - 1)) ** 2
            return path[i] + side * (w * taper) + nrm * (lift - T / 2)
        pieces.append(strip("Tail%d" % k, n, point_at, wdt, mat, 3 + k, wobble=1.6, seed=7.0 + k))
    return pieces


# ---------------------------------------------------------------- material

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


def stain(g, center, radius, warp_scale=40.0, seed=0.0, squash=(1.0, 1.0, 1.0)):
    """A soaked-through stain round `center`: its body (0-1), the darker tide line at its rim (0-1) and the faint
    halo it wicked out into (0-1). `squash` stretches it (it spreads along the threads, round the head)."""
    P = g.coords()
    rel = mapping(g, P, scale=squash, loc=tuple(-c * k for c, k in zip(center, squash)))
    dist = g.node("ShaderNodeVectorMath", operation="LENGTH")
    g.links.new(rel, dist.inputs[0])
    # 1 at the center falling to 0 at `radius`, pushed about by three octaves of noise: a ragged, lobed blot
    f = g.math("SUBTRACT", 1.0, g.math("DIVIDE", tk._sock(dist.outputs, "Value"), radius))
    for k, (sc, amt) in enumerate(((warp_scale, 0.7), (warp_scale * 2.7, 0.45), (warp_scale * 7.0, 0.2))):
        n = g.noise(sc, detail=3.0, roughness=0.6, vector=mapping(g, P, loc=(seed + k, seed * 0.7, 0.3 * k)))
        f = g.math("ADD", f, g.math("MULTIPLY", g.math("SUBTRACT", n, 0.5), amt))
    body = g.ramp(f, 0.36, 0.5)
    rim = g.math("MULTIPLY", g.ramp(f, 0.3, 0.36), g.ramp(f, 0.46, 0.38))
    halo = g.math("MULTIPLY", g.ramp(f, 0.08, 0.3), g.ramp(f, 0.4, 0.3))
    return body, rim, halo


def gauze_material(name):
    """Gauze gone grey-beige: a fine crinkled weave, wrinkles, frayed paler edges, grime where the layers overlap,
    sweat-yellowed patches, dust; a dried blood stain soaked through over the left forehead, its rim darker, and an
    older brown one at the back."""
    mat, g = tk.new_material(name)
    a = g.node("ShaderNodeAttribute", attribute_name=ATTR)
    a.attribute_type = "GEOMETRY"
    along, across, sid = g.separate(tk._sock(a.outputs, "Vector"))
    P = mapping(g, g.coords(), loc=(0.71, 0.33, 1.27))

    def nz(scale, detail=4.0, r=0.55, dist=0.0, vec=P):
        return g.noise(scale, detail=detail, roughness=r, vector=vec, distortion=dist)

    # Strip coordinates for the weave and wrinkles: (along, across in meters, a per-strip offset)
    c = g.node("ShaderNodeCombineXYZ")
    g.links.new(along, c.inputs[0])
    g.links.new(g.math("MULTIPLY", across, 0.03), c.inputs[1])
    g.links.new(g.math("MULTIPLY", sid, 1.37), c.inputs[2])
    S = c.outputs[0]
    col = g.mix(g.ramp(nz(6.0, 4.0), 0.25, 0.8), (0.255, 0.228, 0.183), (0.172, 0.152, 0.117))
    sweat = g.ramp(nz(2.5, 5.0, 0.6, 0.4), 0.48, 0.68)
    col = g.mix(g.math("MULTIPLY", sweat, 0.7), col, (0.21, 0.168, 0.1))
    # Crinkles across the strip (crepe gauze), soft folds along it
    crinkle = g.noise(1.0, detail=2.0, vector=mapping(g, S, (230.0, 25.0, 1.0)))
    crinkle = g.ramp(crinkle, 0.3, 0.7)
    fold = g.noise(1.0, detail=2.0, vector=mapping(g, S, (6.0, 55.0, 1.0)))
    height = g.math("ADD", g.math("MULTIPLY", crinkle, 0.45), g.math("MULTIPLY", g.ramp(fold, 0.3, 0.7), 1.2))
    col = g.mix(g.math("MULTIPLY", g.ramp(fold, 0.5, 0.25), 0.5), col, (0.085, 0.074, 0.058))
    col = g.mix(g.math("MULTIPLY", g.ramp(crinkle, 0.4, 0.1), 0.3), col, (0.12, 0.105, 0.082))
    # Weave: a loose grid of threads with darker gaps
    weave = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", along, 2 * math.pi / 0.0026)),
                   g.math("SINE", g.math("MULTIPLY", across, 2 * math.pi * 7.0)))
    height = g.math("ADD", height, g.math("MULTIPLY", weave, 0.15))
    col = g.mix(g.math("MULTIPLY", g.ramp(weave, 0.2, 0.9), 0.18), col, (0.1, 0.088, 0.07))
    # Frayed edges: paler loose threads, grime packed along them
    edge = g.ramp(g.math("ABSOLUTE", across), 0.78, 1.0)
    fray = g.math("MULTIPLY", edge, g.ramp(nz(90.0, 3.0), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", fray, 0.5), col, (0.27, 0.255, 0.22))
    grime_edge = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", across), 0.6, 0.95), g.ramp(nz(20.0), 0.35, 0.65))
    col = g.mix(g.math("MULTIPLY", grime_edge, 0.45), col, (0.07, 0.06, 0.045))
    # Dirt and grime: a photo's dark parts, crevices between the layers, dust, specks
    p = tk.photo(g, "rust_coarse_01", 3.0, (0.21, 0.66, 0.4))
    dirt = g.math("MULTIPLY", g.ramp(tk._luma(g, p["color"]), 0.3, 0.07), 1.0)
    dirt = g.math("MAXIMUM", dirt, tk._grime(g, 1.3), clamp=True)
    col = g.mix(g.math("MULTIPLY", dirt, 0.85), col, g.mix(nz(10.0), (0.045, 0.038, 0.028), (0.09, 0.076, 0.055)))
    smudge = g.math("MULTIPLY", g.ramp(nz(5.0, 6.0, 0.65, 0.8), 0.48, 0.64), 0.7)
    col = g.mix(smudge, col, tk._darker(g, col, 0.45))
    # Hair grease and grime soaked into the inner layers' lower edges and round the back
    z = g.separate(g.coords())[2]
    greasy = g.math("MULTIPLY", g.ramp(z, 1.76, 1.72), g.ramp(nz(9.0, 5.0, 0.6, 0.6), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", greasy, 0.6), col, (0.075, 0.062, 0.045))
    spots = g.ramp(voronoi(g, P, 160.0), 0.15, 0.06)
    col = g.mix(g.math("MULTIPLY", spots, g.ramp(nz(6.0), 0.4, 0.6)), col, (0.025, 0.02, 0.015))
    rough = g.mixf(dirt, 0.9, 0.95)
    # Blood: soaked through over the left forehead, a dark tide line at the rim; an older brown stain at the back;
    # a few spots
    body, rim, halo = stain(g, (0.05, -0.07, 1.775), 0.04, 30.0, 0.3, (0.8, 0.8, 1.35))
    col = g.mix(g.math("MULTIPLY", halo, 0.55), col, (0.12, 0.075, 0.045))
    fresh = g.ramp(nz(14.0, 4.0), 0.3, 0.7)
    col = g.mix(g.math("MULTIPLY", body, 0.9), col, g.mix(fresh, (0.034, 0.009, 0.005), (0.052, 0.015, 0.008)))
    col = g.mix(g.math("MULTIPLY", rim, 0.9), col, (0.02, 0.006, 0.004))
    core, _, _ = stain(g, (0.052, -0.075, 1.773), 0.014, 60.0, 1.1)
    col = g.mix(g.math("MULTIPLY", core, 0.8), col, (0.018, 0.005, 0.003))
    rough = g.mixf(g.math("MAXIMUM", body, rim), rough, 0.62)
    old, old_rim, old_halo = stain(g, (-0.06, 0.13, 1.735), 0.032, 40.0, 2.3, (0.8, 0.8, 1.3))
    col = g.mix(g.math("MULTIPLY", g.math("MAXIMUM", old, old_halo), 0.55), col, (0.1, 0.062, 0.036))
    col = g.mix(g.math("MULTIPLY", old_rim, 0.75), col, (0.06, 0.03, 0.018))
    drops = g.math("MULTIPLY", g.ramp(voronoi(g, mapping(g, P, loc=(1.3, 0.2, 0.8)), 60.0), 0.09, 0.03),
                   g.ramp(nz(2.0, 4.0), 0.62, 0.72))
    col = g.mix(g.math("MULTIPLY", drops, 0.8), col, (0.045, 0.014, 0.01))
    col = tk.grade(g, col, sat=0.9, value=1.0)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 0.35, 0.0012))


# ---------------------------------------------------------------- fit report, export, previews

def capsule_gap(p):
    t = max(0.0, min(1.0, (p - HA).dot(HB - HA) / (HB - HA).length_squared))
    return (p - HA.lerp(HB, t)).length - HR


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
    gaps = [capsule_gap(p) for p in pts]
    k = min(range(len(gaps)), key=gaps.__getitem__)
    front = [p for p in pts if p.y < -0.04 and abs(p.x) < 0.05]
    print("[%s] head hit box: closest %.1f cm at (%.3f, %.3f, %.3f); lowest point over the face z %.3f (brows 1.745)"
          % (NAME, 100 * gaps[k], pts[k].x, pts[k].y, pts[k].z, min(p.z for p in front)))
    return parts


def close_up(view, direction, target, distance=0.5, lens=50):
    loc = Vector(target) + Vector(direction).normalized() * distance
    tk.render(tk.camera(SCRIPT + view, loc, target, lens=lens), os.path.join(PREVIEWS, "%s_%s.png" % (SCRIPT, view)),
              res=(900, 900), samples=64)


gauze = gauze_material("Gauze")
pieces = [turn("TurnA", TURN_A, gauze, 0, 0.0), crown_pass("PassA", 25.0, 0.058, gauze, 1, 1.0, 0),
          crown_pass("PassB", 1.0, 0.056, gauze, 2, 2.0, 1),
          crown_pass("PassC", -23.0, 0.056, gauze, 6, 4.0, 2),
          turn("TurnB", TURN_B, gauze, 5, 3.0)]
pieces += knot_and_tails(gauze)
export(pieces)
focus = Vector((0.0, 0.035, 1.76))
zk.previews(SCRIPT, PREVIEWS, focus, distance=0.85)
close_up("close", (0.7, -0.9, 0.3), focus, distance=0.5)
close_up("knot", (1.0, 0.35, 0.05), Vector((0.08, 0.06, 1.72)), distance=0.42)
close_up("top", (0.2, 0.3, 1.0), focus, distance=0.55)
print("[%s] done" % SCRIPT)
