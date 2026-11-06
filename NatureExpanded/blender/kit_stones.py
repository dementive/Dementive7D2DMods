"""Ground-cover kit: small stones, slabs, plates, driftwood and sand, for the walk-through ground pieces of Nature
Expanded (Pebbles, FlatStones, RiverStones, ShaleChips, CrackedMud, Driftwood, BleachedBranch). See
groundcover/SPEC_stones.md.

Each piece is a block model like the plants (Blender meters, Z up, the ground at z = -0.5 = nk.GROUND, the piece lying
on it around the origin, 0.9 m across at most and mostly under 15 cm tall). Everything is real geometry (stones are
displaced super-ellipsoids sunk into the ground, slabs and plates are filled outlines with rounded shoulders, wood is a
lumpy tube with a splintered end) wearing a procedural material that is baked into one atlas by ks.export (near mesh
and a decimated far mesh, one shared atlas).

- `GM`: a mesh per material with named per-vertex float attributes (so materials can use "stone-local" coordinates,
  per-stone random numbers "t", wood grain coordinates "ws", "ca", "sa"). Every face carries "lod" (2 = decimated in
  the far mesh, 1 = left out of it).
- Geometry: `stone`, `pad` (a ragged soil/sand/mud pad), `plate` (a slab or mud plate from an outline), `voronoi_cells`,
  `rounded`, `shale`, `wood_tube`, `mound` (moss cushions), `strand`.
- Materials: `stone_frame` (each stone's own rotated coordinates), `soil_signals`, `sand_signals`, `granite`,
  `sandstone`, `quartz`, `river_stone`, `moss_mound`, `weathered_wood`, ... all built on kit_forest/featurekit pieces.
- Export/preview: `export`, `preview`.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "features"))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402
import featurekit as fk  # noqa: E402

G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    os.makedirs(a[1], exist_ok=True)
    return a[0], a[1]


# ---------------------------------------------------------------- meshes

class GM:
    """A mesh in one material with named per-vertex float attributes ("t" always) and a per-face "lod"."""

    def __init__(self, material, extra=()):
        self.material = material
        self.bm = bmesh.new()
        self.names = ("t",) + tuple(extra)
        self.L = {n: self.bm.verts.layers.float.new(n) for n in self.names}
        self.lodL = self.bm.faces.layers.int.new("lod")
        self.lod = 2

    def v(self, co, t=1.0, **attrs):
        v = self.bm.verts.new(co)
        v[self.L["t"]] = t
        for k, x in attrs.items():
            if k in self.L:
                v[self.L[k]] = x
        return v

    def f(self, verts, smooth=True, lod=None):
        try:
            face = self.bm.faces.new(verts)
        except ValueError:
            return None
        face.smooth = smooth
        face[self.lodL] = self.lod if lod is None else lod
        return face

    def object(self, name):
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if not v.link_faces], context="VERTS")
        if not self.bm.faces:
            self.bm.free()
            return None
        return tk.mesh_object(name, self.bm, self.material)


class Set:
    """The GMs of one piece, by material name."""

    def __init__(self, name):
        self.name = name
        self.gms = {}

    def gm(self, material, extra=()):
        g = self.gms.get(material.name)
        if g is None:
            g = self.gms[material.name] = GM(material, extra)
        return g

    def objects(self):
        out = []
        for k, g in self.gms.items():
            o = g.object(self.name + k)
            if o is not None:
                out.append(o)
        self.gms = {}
        return out


STONE_ATTRS = ("cx", "cy", "cz")


# ---------------------------------------------------------------- stones

def stone(gm, at, radii, height, rnd, tv, yaw=0.0, tilt=(0.0, 0.0), power=2.4, rough=0.06, planes=(), subdiv=3,
          sink=0.03, lod=2, lump=1.0):
    """A rounded stone: a super-ellipsoid with radii (a, b, c), its top `height` above the ground (the rest sunk, the
    part under the ground dropped), lumpy (`rough` as a fraction of its size), flat split faces (`planes`: (normal,
    distance from the center)). `tv` is its own random number for the materials ("t"); "cx cy cz" is its center, the
    origin of the stone-local coordinates."""
    a, b, c = radii
    size = (a * b * c) ** (1.0 / 3.0)
    cz = G + height - c
    rot = Matrix.Rotation(yaw, 3, "Z")
    tl = Matrix.Rotation(tilt[0], 3, "X") @ Matrix.Rotation(tilt[1], 3, "Y")
    off = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        u = v.co.copy().normalized()
        # lopsided: the direction is pushed about by a slow noise before it becomes a point on the ellipsoid
        wv = Vector((mn.noise(u * 1.4 + off * 0.1), mn.noise(u * 1.4 + off * 0.1 + Vector((9.0, 3.0, 5.0))),
                     mn.noise(u * 1.4 + off * 0.1 + Vector((2.0, 11.0, 7.0))))) * 0.34 * lump
        u = (u + wv).normalized()
        s = (abs(u.x) ** power + abs(u.y) ** power + abs(u.z) ** power) ** (-1.0 / power)
        p = Vector((u.x * s * a, u.y * s * b, u.z * s * c))
        q = p / size * 1.3 + off
        n = (mn.fractal(q, 0.5, 2.0, 4, noise_basis="PERLIN_ORIGINAL") * 0.75 + 0.35 * mn.noise(q * 5.0 + Vector((3.0, 1.0, 2.0)))
             + 0.08 * mn.noise(q * 14.0) - 0.22 * abs(mn.noise(q * 2.6 + Vector((7.0, 1.0, 4.0)))))
        p += u * (n * rough * size * lump)
        for nrm, d in planes:
            nv = Vector(nrm).normalized()
            over = p.dot(nv) - d
            if over > 0.0:
                p -= nv * over
        p = rot @ (tl @ p)
        p = Vector((p.x + at[0], p.y + at[1], p.z + cz))
        p.z = max(p.z, G - sink)
        v.co = p
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0015)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0015, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 4e-7 or max(v.co.z for v in f.verts) < G - 0.01],
                     context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cache = {}
    center = (at[0], at[1], cz)
    for f in bm.faces:
        vs = []
        for v in f.verts:
            if v.index not in cache:
                cache[v.index] = gm.v(v.co.copy(), tv, cx=center[0], cy=center[1], cz=center[2])
            vs.append(cache[v.index])
        gm.f(vs, True, lod)
    bm.free()


def pebble(S, mat, x, y, r, rnd, flat=None, elong=None, tv=None, chip=0.65, power=None, lod=2, rough=0.11,
           height=None, tilt=0.25, sub=None):
    """One stone of nominal radius `r` at (x, y): longer than wide by `elong`, `flat` as thick as wide, half sunk, with
    a flat chipped face now and then, turned and tipped at random. Every stone differs: shape, tilt, chips, its own
    "t" for the materials."""
    flat = flat if flat is not None else rnd.uniform(0.4, 0.75)
    el = elong if elong is not None else rnd.uniform(1.0, 1.4)
    a, b, c = r * el, r * rnd.uniform(0.72, 1.0), r * flat
    h = height if height is not None else c * rnd.uniform(0.85, 1.35)
    if sub is None:
        sub = 3 if r > 0.045 else (2 if r > 0.012 else 1)
    planes = []
    if rnd.random() < chip and r > 0.02:
        for _ in range(rnd.choice((1, 2, 2, 3))):
            nv = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.8))).normalized()
            sup = math.sqrt((nv.x * a) ** 2 + (nv.y * b) ** 2 + (nv.z * c) ** 2)
            planes.append((tuple(nv), sup * rnd.uniform(0.66, 0.88)))
    stone(S.gm(mat, STONE_ATTRS), (x, y), (a, b, c), h, rnd, tv if tv is not None else rnd.random(),
          yaw=rnd.uniform(0, math.tau), tilt=(rnd.uniform(-tilt, tilt), rnd.uniform(-tilt, tilt)),
          power=power if power is not None else rnd.uniform(2.1, 2.8), rough=rough, planes=planes, subdiv=sub,
          lod=lod)
    return h


def _poly_blob(radius, rnd, lobes=0.3, stretch=(1.0, 1.0), yaw=0.0):
    ph = [rnd.uniform(0, math.tau) for _ in range(4)]

    def r(a):
        return radius * (1.0 + lobes * (0.5 * math.sin(2 * a + ph[0]) + 0.3 * math.sin(3 * a + ph[1]) +
                                         0.25 * math.sin(5 * a + ph[2]) + 0.15 * math.sin(8 * a + ph[3])))
    return r


def pad(gm, center, radius, rnd, sides=26, dome=0.01, lobes=0.3, rings=3, sink=0.006, stretch=(1.0, 1.0), yaw=0.0,
        floor=None, lump=0.003, lod=2):
    """A low ragged mound of soil, sand or silt lying on the ground: its outline lobed and wobbly, its middle raised
    `dome`, its rim sunk below the ground so it melts in. "t" runs 1 in the middle to about 0.5 at the rim."""
    rr = _poly_blob(radius, rnd, lobes)
    cx, cy = center
    base = G if floor is None else floor
    off = Vector((rnd.uniform(0, 40), rnd.uniform(0, 40), 0.0))
    cyaw, syaw = math.cos(yaw), math.sin(yaw)

    def pt(a, f, jit):
        r = rr(a) * f * (1.0 + jit)
        x, y = math.cos(a) * r * stretch[0], math.sin(a) * r * stretch[1]
        return cx + x * cyaw - y * syaw, cy + x * syaw + y * cyaw

    old = gm.lod
    gm.lod = lod
    c = gm.v((cx, cy, base + dome), 1.0)
    rows = []
    for k in range(1, rings + 1):
        f = k / rings
        row = []
        for i in range(sides):
            a = i / sides * math.tau
            x, y = pt(a, f, rnd.uniform(-0.04, 0.04) * f)
            n = mn.noise(Vector((x * 9.0, y * 9.0, 0.0)) + off)
            z = base + dome * (1.0 - f * f) * (0.75 + 0.5 * n) + lump * n * (1.0 - f * 0.5)
            if k == rings:
                z = base - sink
            row.append(gm.v((x, y, z), 1.0 - 0.5 * f))
        rows.append(row)
    for i in range(sides):
        gm.f((c, rows[0][i], rows[0][(i + 1) % sides]), True)
    for A, B in zip(rows, rows[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            gm.f((A[i], B[i], B[j], A[j]), True)
    gm.lod = old


def mound(gm, center, radius, height, rnd, sides=14, rings=2, lumps=0.4, sink=0.01, t_rim=0.0):
    """A lumpy cushion (moss, a tuft's base): a dome of rings whose rim sinks below the ground; "t" runs 1 on top to
    `t_rim` at the rim, for materials to fade it into what is under it."""
    cx, cy = center
    rr = _poly_blob(radius, rnd, 0.25)
    off = Vector((rnd.uniform(0, 40), rnd.uniform(0, 40), 0.0))
    c = gm.v((cx, cy, G + height), 1.0)
    rows = []
    for k in range(1, rings + 1):
        f = k / rings
        row = []
        for i in range(sides):
            a = i / sides * math.tau
            r = rr(a) * f * (1.0 + rnd.uniform(-0.08, 0.08))
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            n = mn.noise(Vector((x * 14.0, y * 14.0, 0.0)) + off)
            z = G + height * (1.0 - f ** 2.2) * (1.0 + lumps * n) - (sink if k == rings else 0.0)
            row.append(gm.v((x, y, z), 1.0 + (t_rim - 1.0) * f ** 1.5))
        rows.append(row)
    for i in range(sides):
        gm.f((c, rows[0][i], rows[0][(i + 1) % sides]), True)
    for A, B in zip(rows, rows[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            gm.f((A[i], B[i], B[j], A[j]), True)


# ---------------------------------------------------------------- outlines: cells, rounding

def clip_halfplane(poly, n, c):
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        dp, dq = n.dot(p) - c, n.dot(q) - c
        if dp <= 0.0:
            out.append(p)
        if (dp < 0.0 < dq) or (dq < 0.0 < dp):
            out.append(p + (q - p) * (dp / (dp - dq)))
    return out


def circle_poly(radius, sides=24, stretch=(1.0, 1.0), yaw=0.0, rnd=None, wob=0.0):
    pts = []
    for i in range(sides):
        a = i / sides * math.tau
        r = radius * (1.0 + (rnd.uniform(-wob, wob) if rnd else 0.0))
        x, y = math.cos(a) * r * stretch[0], math.sin(a) * r * stretch[1]
        pts.append(Vector((x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw))))
    return pts


def voronoi_cells(seeds, bound, gap):
    """Polygons (counter-clockwise Vector2 lists) of the cells around `seeds` clipped to the convex polygon `bound`,
    each pulled back `gap`/2 from the bisector with every neighbor, so `gap` is the crack between plates."""
    cells = []
    for i, s in enumerate(seeds):
        poly = list(bound)
        for j, o in enumerate(seeds):
            if i == j:
                continue
            d = o - s
            n = d / d.length
            poly = clip_halfplane(poly, n, n.dot((s + o) * 0.5) - gap * 0.5)
            if len(poly) < 3:
                break
        cells.append(poly)
    return cells


def area(poly):
    return 0.5 * sum(p.x * poly[(i + 1) % len(poly)].y - poly[(i + 1) % len(poly)].x * p.y for i, p in enumerate(poly))


def centroid(poly):
    return sum(poly, Vector((0.0, 0.0))) / len(poly)


def rounded(poly, rnd, rounds=1, wobble=0.0, inset=0.0, cut=0.25):
    """The outline with corners cut (Chaikin), long edges wobbled sideways a little, optionally pulled in toward the
    centroid by `inset` (meters)."""
    pts = [p.copy() for p in poly]
    if wobble:
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out.append(p)
            e = q - p
            if e.length > 0.06:
                nrm = Vector((-e.y, e.x)).normalized()
                for f in (0.33, 0.66) if e.length > 0.14 else (0.5,):
                    out.append(p + e * f + nrm * rnd.uniform(-wobble, wobble) * e.length)
        pts = out
    for _ in range(rounds):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out.append(p + (q - p) * cut)
            out.append(p + (q - p) * (1.0 - cut))
        pts = out
    if inset:
        c = centroid(pts)
        pts = [c + (p - c) * max(0.2, 1.0 - inset / max(1e-4, (p - c).length)) for p in pts]
    return pts


def pack(radii, region, rnd, stretch=(1.0, 1.0), touch=0.9, pull=0.02, iters=120, start=None):
    """Positions (Vector2) for circles of `radii` crowded toward the middle of an ellipse of radius `region`: random
    starts, then relaxed until no two overlap by more than `touch` of their radii (so stones touch and nudge)."""
    pts = start or [Vector((rnd.uniform(-1, 1) * region * stretch[0], rnd.uniform(-1, 1) * region * stretch[1])) for _ in radii]
    for _ in range(iters):
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = pts[j] - pts[i]
                L = d.length or 1e-4
                need = (radii[i] + radii[j]) * touch
                if L < need:
                    push = d / L * (need - L) * 0.5
                    pts[i] -= push
                    pts[j] += push
        for i in range(len(pts)):
            pts[i] = pts[i] * (1.0 - pull)
    return pts


def poisson(count, radius, min_dist, rnd, stretch=(1.0, 1.0), tries=4000):
    pts = []
    while len(pts) < count and tries > 0:
        tries -= 1
        a = rnd.uniform(0, math.tau)
        r = radius * math.sqrt(rnd.random())
        p = Vector((math.cos(a) * r * stretch[0], math.sin(a) * r * stretch[1]))
        if all((p - q).length >= min_dist for q in pts):
            pts.append(p)
    return pts


# ---------------------------------------------------------------- plates and slabs

def plate(top, wall, poly, rnd, tv, z_top, floor, curl=0.0, curl_phase=0.0, dome=0.0, shoulder=0.01, lump=0.003,
          lump_scale=14.0, tilt=(0.0, 0.0), rings=(0.0, 0.55, 0.88), undercut=0.0, lod=2, wall_attrs=None,
          wall_rows=1, top_attrs=None, flat_wall=False, seed=0.0):
    """A slab or plate over the outline `poly` (counter-clockwise): its top `z_top` above the ground at the middle
    (dome raises the middle, `curl` raises the rim, more on the side facing `curl_phase`, as drying mud curls), a
    rounded shoulder `shoulder` deep at the rim, and a wall down to `floor` (the wall leans in by `undercut` meters
    as it goes down), the whole turned about its middle by `tilt` (radians about x and y). `rings` are the
    fractions of the outline at which the top is sampled. Returns nothing; adds to GMs `top` and `wall`."""
    n = len(poly)
    c = centroid(poly)
    rotm = Matrix.Rotation(tilt[0], 3, "X") @ Matrix.Rotation(tilt[1], 3, "Y")
    pivot = Vector((c.x, c.y, G))
    off = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), seed))
    rmax = max((p - c).length for p in poly)
    attrs_t = {"cx": c.x, "cy": c.y, "cz": G + z_top}
    tv_ = tv

    def place(x, y, z):
        p = rotm @ (Vector((x, y, z)) - pivot) + pivot
        p.z = max(p.z, G - 0.03)
        return p

    def top_z(s, a, x, y):
        nz = mn.noise(Vector((x * lump_scale, y * lump_scale, 0.0)) + off)
        nz2 = mn.noise(Vector((x * lump_scale * 3.1, y * lump_scale * 3.1, 3.0)) + off)
        lift = curl * (s ** 3.0) * (0.55 + 0.45 * math.cos(a - curl_phase))
        return G + z_top + dome * (1.0 - s * s) + lift + lump * (nz + 0.4 * nz2)

    old_t, old_w = top.lod, wall.lod
    top.lod = wall.lod = lod
    ang = [math.atan2(p.y - c.y, p.x - c.x) for p in poly]
    # Top: center, rings, then the shoulder ring at the full outline (a little lower) and the wall
    cen = place(c.x, c.y, top_z(0.0, 0.0, c.x, c.y))
    vc = top.v(cen, tv_, rim=0.0, wd=0.0, **attrs_t)
    ring_v = []
    for s in rings[1:]:
        row = []
        for i, p in enumerate(poly):
            q = c + (p - c) * s
            row.append(top.v(place(q.x, q.y, top_z(s, ang[i], q.x, q.y)), tv_, rim=s, wd=0.0, **attrs_t))
        ring_v.append(row)
    lip = []
    for i, p in enumerate(poly):
        lift_edge = curl * (0.55 + 0.45 * math.cos(ang[i] - curl_phase))
        s = 1.0
        lip.append(top.v(place(p.x, p.y, top_z(s, ang[i], p.x, p.y) - shoulder * 0.4), tv_, rim=1.0, wd=0.0, **attrs_t))
    for i in range(n):
        j = (i + 1) % n
        top.f((vc, ring_v[0][i], ring_v[0][j]), True)
    for A, B in zip(ring_v, ring_v[1:] + [lip]):
        for i in range(n):
            j = (i + 1) % n
            top.f((A[i], B[i], B[j], A[j]), True)
    # Wall: from the lip down to the floor, leaning in (the lip is duplicated for the wall's own mesh, once)
    prev = [wall.v(v.co.copy(), tv_, rim=1.0, wd=0.0, **attrs_t) for v in lip]
    for r in range(1, wall_rows + 1):
        f = r / wall_rows
        row = []
        for i, p in enumerate(poly):
            d = c - p
            inward = d.normalized() * undercut * f if d.length > 1e-5 else Vector((0.0, 0.0))
            z_lip_i = top_z(1.0, ang[i], p.x, p.y) - shoulder * 0.4
            z = z_lip_i + ((G + floor) - z_lip_i) * f
            row.append(wall.v(place(p.x + inward.x, p.y + inward.y, z), tv_, rim=1.0, wd=f, **attrs_t))
        for i in range(n):
            j = (i + 1) % n
            wall.f((prev[i], row[i], row[j], prev[j]), not flat_wall)
        prev = row
    top.lod, wall.lod = old_t, old_w


def shale(top, edge, poly, rnd, tv, center, thickness, rot, bury=0.0, lod=2, face_noise=0.0015):
    """A thin angular plate of shale: a polygon prism of `thickness`, its middle `center` (a point), turned by the
    3x3 matrix `rot`, the top face faceted by a raised middle vertex and torn edges. The edges carry "lz", the
    distance across the plate's thickness (plus a random offset), for the layered look of a broken edge."""
    c = centroid(poly)
    n = len(poly)
    zoff = rnd.uniform(0, 5.0)
    center = Vector(center)

    def pt(p, z):
        v = rot @ Vector((p.x - c.x, p.y - c.y, z)) + center
        return v

    old_t, old_e = top.lod, edge.lod
    top.lod = edge.lod = lod
    h = thickness * 0.5
    attrs = {"cx": center.x, "cy": center.y, "cz": center.z}
    jit = [rnd.uniform(-face_noise, face_noise) for _ in range(n)]
    up_c = top.v(pt(c, h + thickness * rnd.uniform(0.0, 0.5) * 0.6 + rnd.uniform(-face_noise, face_noise)), tv, **attrs)
    topv = [top.v(pt(p, h + jit[i]), tv, **attrs) for i, p in enumerate(poly)]
    for i in range(n):
        j = (i + 1) % n
        top.f((up_c, topv[i], topv[j]), False)
    # bottom
    dn_c = top.v(pt(c, -h), tv, **attrs)
    botv = [top.v(pt(p, -h), tv, **attrs) for p in poly]
    for i in range(n):
        j = (i + 1) % n
        top.f((dn_c, botv[j], botv[i]), False)
    # edges: separate vertices carrying lz
    for i in range(n):
        j = (i + 1) % n
        a0 = edge.v(topv[i].co.copy(), tv, lz=zoff + thickness, **attrs)
        a1 = edge.v(topv[j].co.copy(), tv, lz=zoff + thickness, **attrs)
        b1 = edge.v(botv[j].co.copy(), tv, lz=zoff, **attrs)
        b0 = edge.v(botv[i].co.copy(), tv, lz=zoff, **attrs)
        edge.f((a0, b0, b1, a1), False)
    top.lod, edge.lod = old_t, old_e


# ---------------------------------------------------------------- wood

def catmull(points, step):
    pts = [Vector(p) for p in points]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        n = max(1, int(math.ceil((p2 - p1).length / step)))
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def wood_tube(gm, points, radii, rnd, sides=10, step=0.04, twist=0.0, lump=0.1, groove=0.05, crack=0.05,
              ends=("splinter", "splinter"), ws0=0.0, seed=0.0, lod=2, flat=0.0, jag=1.0):
    """A length of weathered wood along `points` (a polyline smoothed with a spline), `radii` = [(s, radius)] along
    its length (s 0..1). Its radius is lumpy, with long grooves and a few deep checks running along the grain (that
    spirals by `twist` radians per meter); the ends are "splinter" (torn into spikes), "flat" (sawn), "buried" (open,
    sunk), or "stub" (a short broken knot). Vertices carry "ws" (distance along it), "ca" and "sa" (the cosine and sine
    of the angle round it, turned by the twist): the coordinates of the wood grain."""
    path = catmull(points, step)
    acc = [0.0]
    for i in range(1, len(path)):
        acc.append(acc[-1] + (path[i] - path[i - 1]).length)
    total = acc[-1]
    fr = ks.frames(path)
    rs = sorted(radii)

    def radius(s):
        for (s0, r0), (s1, r1) in zip(rs, rs[1:]):
            if s0 <= s <= s1:
                return r0 + (r1 - r0) * (s - s0) / max(1e-6, s1 - s0)
        return rs[0][1] if s < rs[0][0] else rs[-1][1]

    old = gm.lod
    gm.lod = lod
    off = Vector((rnd.uniform(0, 60), rnd.uniform(0, 60), rnd.uniform(0, 60) + seed))
    rings = []
    last = len(path) - 1
    for i, p in enumerate(path):
        s = acc[i] / total
        tan, nr, bn = fr[i]
        r0 = radius(s)
        row = []
        for k in range(sides):
            a = k / sides * math.tau
            ang = a + twist * acc[i]
            ca, sa = math.cos(ang), math.sin(ang)
            q = Vector((acc[i] * 5.0, ca * 1.3, sa * 1.3)) + off
            f = 1.0 + lump * mn.noise(q * 0.7) + 0.5 * lump * mn.noise(q * 1.9)
            g1 = mn.noise(Vector((acc[i] * 3.0, ca * 3.2, sa * 3.2)) + off)
            f += groove * g1
            ck = mn.noise(Vector((acc[i] * 1.6, ca * 4.5, sa * 4.5)) + off * 1.3)
            if abs(ck) < 0.06:
                f -= crack * (1.0 - abs(ck) / 0.06)
            sq = 1.0 - flat * 0.5 * (1.0 + math.cos(2 * (a + 1.0)))
            off_v = nr * math.cos(a) * r0 * f + bn * math.sin(a) * r0 * f * sq
            co = p + off_v
            ext = 0.0
            tag = 0.0
            if i == last and ends[1] == "splinter":
                ext = r0 * rnd.uniform(0.1, 1.8) * (1.0 if k % 2 else 0.35) * jag
                co = p + off_v * rnd.uniform(0.45, 0.8) + tan * ext
                tag = 0.5
            if i == 0 and ends[0] == "splinter":
                ext = r0 * rnd.uniform(0.1, 1.8) * (1.0 if k % 2 else 0.35) * jag
                co = p + off_v * rnd.uniform(0.45, 0.8) - tan * ext
                tag = 0.5
            row.append(gm.v(co, s, ws=acc[i] + ws0, ca=ca, sa=sa, cap=tag))
        rings.append(row)
    for A, B in zip(rings, rings[1:]):
        for k in range(sides):
            j = (k + 1) % sides
            quad = (A[k], A[j], B[j], B[k])
            if max(v.co.z for v in quad) < G - 0.012:
                continue
            gm.f(quad, True)
    # end caps
    for end, row, sign in ((ends[1], rings[-1], 1.0), (ends[0], rings[0], -1.0)):
        if end in ("buried",):
            continue
        idx = last if sign > 0 else 0
        tan = fr[idx][0]
        ctr = sum((v.co for v in row), Vector()) / len(row)
        depth = 0.0 if end == "flat" else -sign * 0.006 * 0.0
        c = gm.v(ctr - tan * sign * (0.012 if end == "splinter" else 0.0), 1.0 if sign > 0 else 0.0,
                 ws=acc[idx] + ws0, ca=0.0, sa=0.0, cap=1.0)
        for k in range(sides):
            j = (k + 1) % sides
            if sign > 0:
                gm.f((c, row[k], row[j]), True)
            else:
                gm.f((c, row[j], row[k]), True)
    gm.lod = old
    return path


# ---------------------------------------------------------------- materials (signals)

def _attr(g, name):
    return g.node("ShaderNodeAttribute", attribute_name=name).outputs["Fac"]


def stone_frame(g):
    """(t, local) for a stone: t its own random number 0..1, local its coordinates from its center, turned in a
    direction of its own: bands, veins and cells of each stone run their own way, and differ from every other."""
    t = _attr(g, "t")
    cen = g.node("ShaderNodeCombineXYZ")
    for i, n in enumerate(STONE_ATTRS):
        g.links.new(_attr(g, n), cen.inputs[i])
    d = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(g.coords(), d.inputs[0])
    g.links.new(cen.outputs[0], d.inputs[1])
    m = g.node("ShaderNodeMapping")
    g.links.new(d.outputs[0], m.inputs["Vector"])
    rot = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("MULTIPLY", t, 37.0), rot.inputs[0])
    g.links.new(g.math("ADD", g.math("MULTIPLY", t, 19.0), 1.0), rot.inputs[1])
    g.links.new(g.math("ADD", g.math("MULTIPLY", t, 53.0), 2.0), rot.inputs[2])
    g.links.new(rot.outputs[0], m.inputs["Rotation"])
    m.inputs["Location"].default_value = (0.0, 0.0, 0.0)
    return t, m.outputs[0]


def _vscale(g, vec, k):
    n = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(vec, n.inputs[0])
    g._in(n, "Scale", k)
    return n.outputs["Vector"]


def _vadd(g, vec, off):
    n = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(vec, n.inputs[0])
    n.inputs[1].default_value = off
    return n.outputs["Vector"]


def _stretch(g, vec, scale):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    return m.outputs[0]


def _comp(g, vec, i):
    return g.separate(vec)[i]


def soil_signals(g, V=None, dry=0.0, tone=1.0):
    """Crumbly dirt as node signals (color, height 0..1, roughness): clods a centimeter across each its own shade, dark
    crevices between them, grains of sand and grit, a few small pale stones, damp darker patches."""
    co = V if V is not None else g.coords()
    cd, cr = kf._cells(g, 52.0, kf._warped(g, 18.0, 0.004, co))
    gd, gr = kf._cells(g, 330.0, co)
    pd, pr = kf._cells(g, 120.0, co)
    mott = g.noise(6.0, detail=5.0, vector=co)
    base = g.mix(g.ramp(mott, 0.3, 0.7), (0.05, 0.039, 0.028), (0.1, 0.077, 0.053))
    base = g.mix(g.math("MULTIPLY", g.ramp(cr, 0.15, 0.95), 0.4), base, (0.115, 0.09, 0.063))
    base = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.5, 0.95), 0.6), base, (0.022, 0.016, 0.011))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.7, 0.95), 0.3), base, (0.17, 0.145, 0.11))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.32, 0.05), 0.5), base, (0.026, 0.021, 0.017))
    grit = g.math("MULTIPLY", g.ramp(pd, 0.16, 0.06), g.ramp(pr, 0.55, 0.8))
    base = g.mix(g.math("MULTIPLY", grit, 0.9), base, g.mix(g.ramp(pr, 0.6, 1.0), (0.2, 0.19, 0.17), (0.3, 0.26, 0.2)))
    if dry > 0.0:
        base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0, vector=co), 0.4, 0.7), dry), base,
                     (0.2, 0.16, 0.115))
    height = g.math("ADD", g.math("MULTIPLY", g.ramp(cd, 0.8, 0.0), 0.45), g.math("MULTIPLY", gr, 0.22))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", mott, 0.15), g.math("MULTIPLY", grit, 0.35)))
    return base, height, 0.93


def sand_signals(g, V=None, color=((0.3, 0.235, 0.15), (0.4, 0.32, 0.21)), wet=0.0, ripple=0.0):
    """Sand: grains a third of a millimeter to a millimeter in assorted tans, dark and pale specks, soft drift
    ripples, damp patches (`wet`)."""
    co = V if V is not None else g.coords()
    gd, gr = kf._cells(g, 700.0, co)
    gd2, gr2 = kf._cells(g, 260.0, co)
    drift = g.noise(14.0, detail=4.0, vector=co)
    base = g.mix(g.ramp(drift, 0.3, 0.7), color[0], color[1])
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.3, 0.95), 0.5), base, tuple(min(1.0, c * 1.35) for c in color[1]))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr2, 0.8, 1.0), 0.5), base, (0.55, 0.5, 0.42))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.18, 0.0), 0.5), base, tuple(c * 0.35 for c in color[0]))
    height = g.math("ADD", g.math("MULTIPLY", gr, 0.4), g.math("MULTIPLY", g.ramp(gd2, 0.5, 0.1), 0.3))
    if ripple:
        rip = g.math("SINE", g.math("ADD", g.math("MULTIPLY", g.separate(co)[0], 160.0),
                                    g.math("MULTIPLY", g.noise(7.0, detail=3.0, vector=co), 12.0)))
        height = g.math("ADD", height, g.math("MULTIPLY", rip, ripple))
    if wet > 0.0:
        w = g.math("MULTIPLY", g.ramp(g.noise(9.0, detail=4.0, vector=co), 0.45, 0.65), wet)
        base = g.mix(g.math("MULTIPLY", w, 0.6), base, tuple(c * 0.45 for c in color[0]))
    return base, height, 0.95


def over_soil(g, col, height, rough, amount=1.0, z_lo=0.012, z_hi=0.045, splotch=0.55):
    """Dirt clinging to a stone: packed against the ground (below z_lo above it, fading out by z_hi), plus ragged
    splotches and smears higher up (`amount` scales them); crumbly, rougher, and its own relief."""
    z = g.separate(g.coords())[2]
    low = g.ramp(z, G + z_hi, G + z_lo * 0.2)
    sm = g.math("ADD", g.noise(7.0, detail=5.0), g.math("MULTIPLY", g.noise(60.0, detail=3.0), 0.25))
    smear = g.ramp(sm, 0.70 - 0.15 * amount, 0.78 - 0.15 * amount)
    lowr = g.math("MULTIPLY", low, g.ramp(g.noise(30.0, detail=4.0), 0.2, 0.5))
    mask = g.math("MAXIMUM", g.math("MULTIPLY", g.math("MAXIMUM", lowr, g.math("MULTIPLY", low, 0.75)), 1.0),
                  g.math("MULTIPLY", smear, splotch * amount))
    mask = g.math("MULTIPLY", mask, g.ramp(g.noise(120.0, detail=2.0), 0.18, 0.5), clamp=True)
    sc, sh, sr = soil_signals(g)
    return (g.mix(mask, col, sc), g.mixf(mask, height, g.math("ADD", 0.4, g.math("MULTIPLY", sh, 0.6))),
            g.mixf(mask, rough, sr))


def tint_by(g, col, t, lo=(0.82, 0.84, 0.88), hi=(1.18, 1.1, 1.0)):
    """Each stone a touch different from the next: the colour times a grey that drifts with its own number."""
    return tk._multiply_color(g, col, g.mix(t, lo, hi))


def granite(name, tint_lo=(0.82, 0.84, 0.88), tint_hi=(1.2, 1.1, 1.02), soil=1.0, relief=0.0035):
    """A granite pebble: the boulder granite's crystals (feldspar, quartz, mica) at the pebble's scale, each stone its
    own tone, dirt on its low side."""
    mat, g = tk.new_material(name)
    t, L = stone_frame(g)
    col, height, rough = fk.granite_surface(g, moss=0.0, lichen=0.0, stain=0.5, scale=1.0)
    col = tint_by(g, col, t, tint_lo, tint_hi)
    if soil > 0.0:
        col, height, rough = over_soil(g, col, height, rough, soil)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def sandstone(name, soil=1.0, relief=0.0035):
    """A sandstone pebble: tan, ochre and rust, sand grains and pits, a faint bedding that runs its own way in each
    stone, iron rings, darker where it has weathered, crumbled edges."""
    mat, g = tk.new_material(name)
    t, L = stone_frame(g)
    warp = kf._warped(g, 9.0, 0.006, L)
    z = g.separate(warp)[2]
    gd, gr = kf._cells(g, 420.0, L)
    pd, pr = kf._cells(g, 75.0, kf._warped(g, 30.0, 0.003, L))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.2, 0.07), g.ramp(pr, 0.45, 0.8))
    bands = g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 230.0), g.math("MULTIPLY", g.noise(11.0, detail=3.0, vector=L), 5.0)))
    fine = g.math("SINE", g.math("ADD", g.math("MULTIPLY", z, 900.0), g.math("MULTIPLY", g.noise(30.0, detail=3.0, vector=L), 9.0)))
    tone = g.noise(4.0, detail=4.0, vector=L)
    base = g.mix(g.ramp(tone, 0.25, 0.75), (0.21, 0.15, 0.09), (0.38, 0.285, 0.175))
    base = g.mix(g.math("MULTIPLY", g.ramp(bands, -0.3, 0.9), 0.45), base, (0.31, 0.235, 0.15))
    base = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.2, 0.9), 0.25), base, (0.11, 0.075, 0.045))
    # iron bloom rings: rusty ripples that follow the stone's curve
    rust = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.8, vector=L), 0.6, 0.72), 0.7)
    base = g.mix(rust, base, (0.28, 0.115, 0.045))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.62, 0.95), 0.55), base, (0.36, 0.29, 0.2))
    base = g.mix(g.math("MULTIPLY", g.ramp(gr, 0.3, 0.05), 0.5), base, (0.07, 0.05, 0.035))
    base = g.mix(g.math("MULTIPLY", pit, 0.8), base, (0.045, 0.03, 0.02))
    # a pale bloom of dust on weathered faces
    base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0, vector=L), 0.6, 0.8), 0.35), base, (0.4, 0.34, 0.26))
    col = tint_by(g, base, t, (0.8, 0.8, 0.82), (1.22, 1.12, 1.0))
    height = g.math("ADD", g.math("MULTIPLY", gr, 0.3), g.math("ADD", g.math("MULTIPLY", bands, 0.12),
                                                                g.math("SUBTRACT", 0.4, g.math("MULTIPLY", pit, 0.5))))
    rough = 0.9
    if soil > 0.0:
        col, height, rough = over_soil(g, col, height, rough, soil)
    col = tk.grade(g, col, sat=0.92, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def quartz(name, soil=0.8, relief=0.003):
    """A pale quartz pebble: milky cream-white with grey translucent patches, smooth conchoidal ripples, glassy
    frosted specks, rusty iron stain in the cracks, hairline fractures."""
    mat, g = tk.new_material(name)
    t, L = stone_frame(g)
    cd, cr = kf._cells(g, 190.0, kf._warped(g, 40.0, 0.002, L))
    wave = g.noise(26.0, detail=2.0, distortion=1.2, vector=L)
    conch = kf._ridged(g, g.noise(14.0, detail=2.0, distortion=1.5, vector=L))
    cloud = g.noise(8.0, detail=5.0, vector=L)
    base = g.mix(g.ramp(cloud, 0.3, 0.7), (0.38, 0.365, 0.33), (0.58, 0.55, 0.5))
    base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(13.0, detail=4.0, vector=L), 0.55, 0.75), 0.55), base, (0.27, 0.27, 0.27))
    base = g.mix(g.math("MULTIPLY", g.ramp(conch, 0.8, 0.98), 0.28), base, (0.7, 0.67, 0.6))
    base = g.mix(g.math("MULTIPLY", g.ramp(cr, 0.55, 0.9), 0.18), base, (0.64, 0.62, 0.57))
    cr_d = kf._voronoi(g, 3.5, kf._warped(g, 6.0, 0.03, L), feature="DISTANCE_TO_EDGE")
    fract = g.ramp(cr_d, 0.012, 0.0)
    stain = g.math("MULTIPLY", g.ramp(cr_d, 0.06, 0.0), g.ramp(g.noise(10.0, detail=3.0, vector=L), 0.35, 0.7))
    base = g.mix(g.math("MULTIPLY", stain, 0.9), base, (0.3, 0.17, 0.07))
    base = g.mix(g.math("MULTIPLY", fract, 0.9), base, (0.07, 0.06, 0.05))
    col = tint_by(g, base, t, (0.9, 0.9, 0.9), (1.08, 1.06, 1.0))
    height = g.math("ADD", g.math("MULTIPLY", conch, 0.3), g.math("ADD", g.math("MULTIPLY", wave, 0.2),
                                                                   g.math("SUBTRACT", g.math("MULTIPLY", cd, 0.18), g.math("MULTIPLY", fract, 0.4))))
    height = g.math("ADD", height, 0.3)
    rough = g.mixf(g.ramp(cr, 0.4, 0.8), 0.42, 0.6)
    if soil > 0.0:
        col, height, rough = over_soil(g, col, height, rough, soil)
    col = tk.grade(g, col, sat=0.9, value=0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def moss_mound(name, soil_rim=True):
    """Moss cushions (kf.moss_layer's clumps) on mound()s: "t" 1 on top to 0 at the rim; the rim fades through a
    ragged line of clumps to bare soil."""
    mat, g = tk.new_material(name)
    t = _attr(g, "t")
    mcol, mh, mrough, _ = kf.moss_layer(g)
    scol, sh, sr = soil_signals(g)
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.35), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(16.0, detail=5.0), 0.5), 0.6))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.5))
    cover = g.ramp(reach, 0.34, 0.5)
    col = g.mix(cover, scol, tk.grade(g, mcol, sat=0.95, value=0.95))
    height = g.mixf(cover, sh, g.math("ADD", 0.25, g.math("MULTIPLY", mh, 0.75)))
    rough = g.mixf(cover, sr, mrough)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.006))


def soil_material(name, relief=0.005, dry=0.0):
    mat, g = tk.new_material(name)
    col, height, rough = soil_signals(g, dry=dry)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def sand_material(name, color=((0.3, 0.235, 0.15), (0.4, 0.32, 0.21)), wet=0.0, ripple=0.0, relief=0.003):
    mat, g = tk.new_material(name)
    col, height, rough = sand_signals(g, color=color, wet=wet, ripple=ripple)
    return tk.finish(mat, g, tk.grade(g, col, sat=0.9, value=0.95), 0.0, rough, g.bump(height, 1.0, relief))


# ---------------------------------------------------------------- wood material

def wood_vec(g, along, around):
    c = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("MULTIPLY", _attr(g, "ws"), along), c.inputs[0])
    g.links.new(g.math("MULTIPLY", _attr(g, "ca"), around), c.inputs[1])
    g.links.new(g.math("MULTIPLY", _attr(g, "sa"), around), c.inputs[2])
    return c.outputs[0]


def weathered_wood(name, light=(0.36, 0.335, 0.295), dark=(0.235, 0.215, 0.188), groove=(0.12, 0.098, 0.076),
                   warm=0.5, stain=0.45, grey=0.0, relief=0.0035, inner=(0.2, 0.15, 0.1)):
    """Sun-bleached wood as it lies: silvery fibres running along the grain (long streaks of two greys), hard ridges
    standing proud and soft trenches between them filled with warm dust, deep checks (cracks) along the grain with
    near-black bottoms, bleach-white and grey-black patches, tiny bore holes, torn splinters at the ends showing
    paler fresh-looking wood. Coordinates come from the tube's "ws", "ca", "sa"."""
    mat, g = tk.new_material(name)
    cap = _attr(g, "cap")
    V = wood_vec(g, 28.0, 26.0)
    Vb = wood_vec(g, 9.0, 11.0)
    Vc = wood_vec(g, 3.2, 6.0)
    Vs = wood_vec(g, 70.0, 70.0)
    fib = g.noise(1.0, detail=6.0, roughness=0.6, vector=V)
    fib2 = g.noise(1.0, detail=4.0, roughness=0.5, vector=Vb)
    rid = kf._ridged(g, g.noise(1.0, detail=2.0, vector=Vb))
    strings = g.ramp(kf._ridged(g, g.noise(1.0, detail=3.0, vector=_stretch(g, V, (1.0, 3.2, 3.2)))), 0.8, 0.97)
    patch = g.noise(5.0, detail=4.0, vector=wood_vec(g, 1.0, 1.4))
    base = g.mix(g.ramp(fib, 0.25, 0.8), dark, light)
    base = g.mix(g.math("MULTIPLY", g.ramp(rid, 0.55, 0.9), 0.35), base, tuple(min(1.0, c * 1.22) for c in light))
    base = g.mix(g.math("MULTIPLY", strings, 0.25), base, tuple(min(1.0, c * 1.3) for c in light))
    # trenches: warm brown dust between the ridges
    trench = g.math("MULTIPLY", g.ramp(rid, 0.4, 0.05), g.ramp(fib2, 0.35, 0.7))
    base = g.mix(g.math("MULTIPLY", trench, warm * 0.55), base, groove)
    # bleached and stained patches
    base = g.mix(g.math("MULTIPLY", g.ramp(patch, 0.62, 0.8), 0.5), base, tuple(min(1.0, c * 1.5) for c in light))
    base = g.mix(g.math("MULTIPLY", g.ramp(g.noise(3.5, detail=5.0, vector=wood_vec(g, 1.0, 1.1)), 0.58, 0.78), stain), base,
                 tuple(c * 0.4 for c in dark))
    # checks: long cracks that run with the grain, black at the bottom
    ce = kf._voronoi(g, 1.0, kf._warped(g, 12.0, 0.04, _stretch(g, Vc, (1.0, 1.0, 1.0))), feature="DISTANCE_TO_EDGE")
    check = g.ramp(ce, 0.045, 0.0)
    base = g.mix(g.math("MULTIPLY", g.ramp(ce, 0.15, 0.0), 0.35), base, tuple(c * 0.6 for c in groove))
    base = g.mix(g.math("MULTIPLY", check, 0.9), base, (0.04, 0.032, 0.025))
    # bore holes
    bd, br = kf._cells(g, 1.0, Vs)
    bore = g.math("MULTIPLY", g.ramp(bd, 0.12, 0.05), g.ramp(br, 0.9, 0.97))
    base = g.mix(g.math("MULTIPLY", bore, 0.9), base, (0.02, 0.016, 0.012))
    # torn ends and cap
    base = g.mix(g.ramp(cap, 0.45, 0.8), base, g.mix(g.ramp(fib, 0.3, 0.7), inner, tuple(min(1.0, c * 1.5) for c in inner)))
    height = g.math("ADD", g.math("MULTIPLY", rid, 0.5), g.math("MULTIPLY", g.math("SUBTRACT", fib, 0.5), 0.5))
    height = g.math("ADD", g.math("MULTIPLY", height, 1.0), 0.5)
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", check, 1.4), g.math("MULTIPLY", bore, 0.8)))
    rough = g.mixf(check, 0.92, 0.98)
    col = tk.grade(g, base, sat=0.9, value=0.97)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


# ---------------------------------------------------------------- strands (dried weed, grass)

def strand(b, material, points, width, t0=0.0, t1=1.0, lod=1):
    """A thin ribbon (a dried weed, a stalk of straw) along `points`, `width` wide, lying across z."""
    pts = [Vector(p) for p in points]
    m = b.mesh(material)
    m.begin(pts[0])
    n = len(pts)
    old = b.lod
    b.lod = lod
    rows = []
    for i, p in enumerate(pts):
        d = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        side = d.cross(UP)
        if side.length < 1e-5:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        w = width * 0.5 * (1.0 - 0.8 * (i / (n - 1)) ** 2)
        s = i / (n - 1)
        rows.append((m.v(p - side * w, t0 + (t1 - t0) * s), m.v(p + side * w, t0 + (t1 - t0) * s)))
    for (a0, b0), (a1, b1) in zip(rows, rows[1:]):
        m.f((a0, b0, b1, a1), False)
    b.lod = old


# ---------------------------------------------------------------- export and previews

FAST = bool(os.environ.get("STONES_FAST"))
_orig_bake = tk._bake
_CAPS = {"EMIT": 12, "NORMAL": 3, "ROUGHNESS": 3, "AO": 40}


def _capped_bake(obj, kind, img, samples, **kw):
    """The procedural materials are deterministic, so a handful of samples (anti-aliasing only) bakes them as well as
    the kit's 64 and 128 do, in a fraction of the time; the occlusion map keeps 40."""
    cap = _CAPS.get(kind, samples)
    return _orig_bake(obj, kind, img, min(samples, 4 if FAST else cap), **kw)


tk._bake = _capped_bake


def export(name, pieces, out_dir, size=1024, density=None, coarse=0.35):
    if FAST:
        size = 512
    if os.environ.get("STONES_GEOM"):
        atlas = tk.triangulate(tk.join(pieces, name))
        me = atlas.data
        zs = [v.co.z for v in me.vertices]
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        print("[%s] GEOM triangles %d  x %.2f..%.2f y %.2f..%.2f  z %.3f..%.3f above ground" % (
            name, len(me.polygons), min(xs), max(xs), min(ys), max(ys), min(zs) - G, max(zs) - G))
        bad = {}
        tot = {}
        for p in me.polygons:
            mname = me.materials[p.material_index].name
            tot[mname] = tot.get(mname, 0) + 1
            if p.normal.z < -0.5 and p.center.z > G + 0.01:
                bad[mname] = bad.get(mname, 0) + 1
        print("[%s] faces by material %s; facing down above the ground: %s" % (name, tot, bad))
        raise SystemExit(0)
    return ks.export(name, pieces, out_dir, size=size, coarse_ratio=coarse, density=density)


def floor_material(kind):
    mat, g = tk.new_material("PreviewGround_" + kind)
    if kind == "sand":
        col = g.mix(g.ramp(g.noise(3.0, detail=6.0), 0.35, 0.7), (0.5, 0.36, 0.2), (0.42, 0.29, 0.16))
        col = g.mix(g.ramp(g.noise(40.0, detail=4.0), 0.55, 0.75), col, (0.3, 0.22, 0.14))
        return tk.finish(mat, g, col, 0.0, 0.9, g.bump(g.noise(300.0, detail=2.0), 0.4, 0.002))
    if kind == "dirt":
        col = g.mix(g.ramp(g.noise(5.0, detail=6.0), 0.35, 0.7), (0.17, 0.125, 0.085), (0.12, 0.09, 0.06))
        col = g.mix(g.ramp(g.noise(60.0, detail=4.0), 0.5, 0.75), col, (0.08, 0.06, 0.04))
        return tk.finish(mat, g, col, 0.0, 0.95, g.bump(g.noise(260.0, detail=2.0), 0.4, 0.002))
    if kind == "shore":
        col = g.mix(g.ramp(g.noise(6.0, detail=6.0), 0.35, 0.7), (0.3, 0.26, 0.2), (0.22, 0.19, 0.145))
        col = g.mix(g.ramp(g.noise(55.0, detail=4.0), 0.5, 0.75), col, (0.14, 0.12, 0.09))
        return tk.finish(mat, g, col, 0.0, 0.9, g.bump(g.noise(300.0, detail=2.0), 0.4, 0.002))
    # grass-ish meadow floor
    col = g.mix(g.ramp(g.noise(4.0, detail=6.0), 0.35, 0.7), (0.1, 0.14, 0.05), (0.15, 0.17, 0.07))
    col = g.mix(g.ramp(g.noise(80.0, detail=4.0), 0.45, 0.7), col, (0.06, 0.085, 0.03))
    col = g.mix(g.ramp(g.noise(9.0, detail=5.0), 0.62, 0.75), col, (0.13, 0.1, 0.06))
    return tk.finish(mat, g, col, 0.0, 0.9, g.bump(g.noise(220.0, detail=3.0), 0.5, 0.004))


def preview(script, model, out_dir, kind="grass", height=0.1, focus=None):
    """Renders on a ground of `kind` (grass, dirt, sand, shore): stand (eye height 1.7 m, 1.3 m off), crouch (0.7 m
    high, 0.8 m off), macro (25 cm off), far (3 m, eye height), top, a patch (several copies), and the far LOD."""
    tk.preview_stage()
    floor = bpy.data.objects.get("Floor")
    if floor is not None:
        floor.data.materials[0] = floor_material(kind)
    f = Vector((0.0, 0.0, G + (height * 0.5 if focus is None else focus)))
    base = Vector((0.0, 0.0, G))

    only = os.environ.get("STONES_SHOTS")

    def shot(tag, loc, target=f, lens=50, res=(1000, 750), samples=32):
        if only and tag not in only.split(","):
            return
        if FAST:
            samples = 8
            res = (640, 480)
        import time
        t0 = time.time()
        tk.render(tk.camera(script + tag, loc, target, lens=lens), os.path.join(out_dir, "%s_%s.png" % (script, tag)),
                  res=res, samples=samples)
        print("[%s] shot %s %.0fs" % (script, tag, time.time() - t0), flush=True)

    shot("stand", Vector((0.55, -1.2, 1.2)))
    shot("crouch", Vector((0.5, -0.75, G + 0.55)), lens=45)
    shot("macro", Vector((0.12, -0.28, G + 0.2)), Vector((0.0, 0.02, G + 0.01)), lens=50)
    shot("far", Vector((1.0, -2.8, G + 1.7)), Vector((0.0, 0.0, G + 0.05)), lens=50)
    shot("top", Vector((0.0, -0.15, G + 1.5)), Vector((0.0, 0.0, G)), lens=45)
    # patch: eight copies scattered the way world generation would
    rnd = random.Random(1)
    copies = []
    for i in range(8):
        c = model.copy()
        tk.link(c)
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.9, 1.9)
        c.location = (r * math.cos(a), r * math.sin(a) + 0.6, 0.0)
        c.rotation_euler = (0.0, 0.0, rnd.uniform(0, math.tau))
        copies.append(c)
    shot("patch", Vector((0.4, -3.4, G + 1.5)), Vector((0.0, 0.6, G + 0.05)), lens=35)
    for c in copies:
        bpy.data.objects.remove(c)
    lod = bpy.data.objects.get(model.name + "_LOD1")
    if lod is not None:
        model.hide_render = True
        lod.hide_render = False
        shot("lod", Vector((0.55, -1.2, 1.2)), samples=32)
        model.hide_render = False
        lod.hide_render = True
    # the model's own stats
    me = model.data
    lo = Vector((min(v.co.x for v in me.vertices), min(v.co.y for v in me.vertices), min(v.co.z for v in me.vertices)))
    hi = Vector((max(v.co.x for v in me.vertices), max(v.co.y for v in me.vertices), max(v.co.z for v in me.vertices)))
    print("[%s] extent x %.2f..%.2f y %.2f..%.2f height above ground %.3f (min z above ground %.3f)" % (
        script, lo.x, hi.x, lo.y, hi.y, hi.z - G, lo.z - G))
