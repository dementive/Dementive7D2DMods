"""Renders Nature Expanded's grasses as tiles for the game's grass texture sheet (the list is grasses.txt).

    blender -b --factory-startup --python grass_tiles.py -- <out folder> [Name,Name,...]

The game draws a grass block as a few upright quads turned about its middle, each showing one 512 x 512 tile of its
grass sheet, a block (1 m) wide and tall, with the grass's base on the tile's bottom edge, sunk 0.15 m into the
ground (BlockShapeGrass): about the bottom 75 pixels of a tile are buried, and the ground cuts straight across
whatever is there, so a tile's base should be narrow crowns or open stems, not a dense band (see inside()), and
NatureGrassBuilder can shade it dark toward the ground like vanilla's (grasses.txt). Each grass here is built from
real blades, stems and seed heads and rendered from the side, orthographic, one metre square, into three images in
<out folder>:
- <Name>_Color.png: the albedo (unlit), with alpha for the cutout. Darker toward each blade's base and for blades
  further back, varied blade to blade. Vanilla's tiles are dark (its tall grass averages about 50, 60, 28 in sRGB)
  because the game's grass shader brightens them with translucency, so these are kept as dark.
- <Name>_Normal.png: camera-space normals (raw, 0.5 + 0.5 n; x right, y up, z toward the camera).
- <Name>_T.png: each part's base-to-tip position (raw), which NatureGrassBuilder turns into occlusion.
Keep everything inside x in [-0.47, 0.47] and under 0.95 m, so a tile's sides and top stay clear (the builder
clears the top 20 pixels, and the mod's uv frame stops 16 short of the top). Parts are drawn
bolder than life (blades 1 to 2 cm wide), like vanilla's: a real 4 mm blade is 2 pixels here and vanishes past a few
metres.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
GROUND = -0.5
UP = Vector((0.0, 0.0, 1.0))
# The camera looks along +y, so this is the axis a ribbon turns across to face it
VIEW = Vector((0.0, 1.0, 0.0))


def srgb(c):
    """A color given as sRGB 0-255, in the linear values Blender's nodes take."""
    out = []
    for v in c:
        v /= 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out) + (1.0,)


class Parts:
    """Blades, stems and heads gathered into one mesh per material, each vertex carrying "t" (0 at a part's base, 1
    at its tip) and "s" (one random value per part, for its color)."""

    def __init__(self, seed):
        self.rnd = random.Random(seed)
        self.meshes = {}

    def add(self, key, rows, t, s=None):
        """A strip of quads through `rows` (pairs of points across the strip, base to tip) with "t" per row."""
        verts, faces, ts, ss = self.meshes.setdefault(key, ([], [], [], []))
        s = self.rnd.random() if s is None else s
        first = len(verts)
        for (a, b), tv in zip(rows, t):
            verts += [a, b]
            ts += [tv, tv]
            ss += [s, s]
        for i in range(len(rows) - 1):
            k = first + i * 2
            faces.append((k, k + 1, k + 3, k + 2))

    def build(self, materials):
        objs = []
        for key, (verts, faces, ts, ss) in self.meshes.items():
            mesh = bpy.data.meshes.new(key)
            mesh.from_pydata([tuple(v) for v in verts], [], faces)
            for name, values in (("t", ts), ("s", ss)):
                attr = mesh.attributes.new(name, "FLOAT", "POINT")
                attr.data.foreach_set("value", values)
            mesh.materials.append(materials[key])
            obj = bpy.data.objects.new(key, mesh)
            bpy.context.scene.collection.objects.link(obj)
            objs.append(obj)
        return objs


def width_at(profile, f):
    if profile == "lance":
        return max(0.0, (1.0 - f) ** 0.8 * min(1.0, f * 3.0 + 0.15))
    if profile == "fine":
        return max(0.0, (1.0 - f) ** 0.6)
    if profile == "strap":
        return 1.0 if f < 0.85 else (1.0 - f) / 0.15
    if profile == "oval":
        return math.sin(math.pi * f) ** 0.7
    return 1.0


def blade(parts, key, base, direction, length, width, bend=0.3, segments=7, profile="lance", roll=0.0, s=None):
    """A grass blade from `base`, leaving along `direction` and arching outward and over by `bend` (0 straight, 1
    tipped right over to horizontal at its tip), `roll` degrees about its own axis."""
    d = Vector(direction).normalized()
    out = Vector((d.x, d.y, 0.0))
    out = out.normalized() if out.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    axis = UP.cross(out).normalized()
    rows, t = [], []
    center = Vector(base)
    for i in range(segments + 1):
        f = i / segments
        heading = Matrix.Rotation(bend * f * f * math.pi * 0.5, 3, axis) @ d
        if i:
            center = center + heading * (length / segments)
        side = heading.cross(out if abs(heading.dot(out)) < 0.95 else UP)
        side = Matrix.Rotation(math.radians(roll), 3, heading) @ side.normalized()
        w = width * 0.5 * width_at(profile, f)
        rows.append((center - side * w, center + side * w))
        t.append(f)
    parts.add(key, rows, t, s)
    return center


def ribbon(parts, key, points, width, s=None, t0=0.0, t1=1.0, taper=0.0):
    """A thin stem or bristle along `points`, flat to the camera (it's only ever seen from the side)."""
    rows, t = [], []
    n = len(points)
    for i, p in enumerate(points):
        p = Vector(p)
        d = (Vector(points[min(i + 1, n - 1)]) - Vector(points[max(i - 1, 0)])).normalized()
        side = d.cross(VIEW)
        side = side.normalized() if side.length > 1e-4 else Vector((1.0, 0.0, 0.0))
        f = i / (n - 1)
        w = width * 0.5 * (1.0 - taper * f)
        rows.append((p - side * w, p + side * w))
        t.append(t0 + (t1 - t0) * f)
    parts.add(key, rows, t, s)


def arc(base, direction, length, bend, steps=8):
    """Points along a stem from `base` leaving along `direction`, arching outward by `bend` like `blade`."""
    d = Vector(direction).normalized()
    out = Vector((d.x, d.y, 0.0))
    out = out.normalized() if out.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    axis = UP.cross(out).normalized()
    pts = [Vector(base)]
    for i in range(1, steps + 1):
        f = i / steps
        pts.append(pts[-1] + (Matrix.Rotation(bend * f * f * math.pi * 0.5, 3, axis) @ d) * (length / steps))
    return pts


def spread(rnd, lean):
    """A direction leaning out from upright by up to `lean` (0 to 1), at a random heading."""
    a = rnd.uniform(0.0, math.tau)
    r = lean * math.sqrt(rnd.random())
    return Vector((math.cos(a) * r, math.sin(a) * r, 1.0))


def clump_bases(rnd, centers, radius):
    """Points near one of `centers` (x positions across the tile), for the bases of a clump's blades."""
    cx = rnd.choice(centers)
    a = rnd.uniform(0.0, math.tau)
    r = radius * math.sqrt(rnd.random())
    return Vector((cx + r * math.cos(a), rnd.uniform(-0.12, 0.12) + r * math.sin(a), GROUND))


def tuft_blades(parts, key, centers, count, length, width, lean, bend, radius=0.06, profile="lance"):
    """`count` blades from clumps at `centers`, each a random length, width and bend from the (low, high) ranges."""
    rnd = parts.rnd
    for i in range(count):
        blade(parts, key, clump_bases(rnd, centers, radius), spread(rnd, lean), rnd.uniform(*length), rnd.uniform(*width),
              bend=rnd.uniform(*bend), profile=profile, roll=rnd.uniform(-50, 50))


def stem(parts, key, base, height, lean, bend, width, steps=8, s=None, t0=0.0):
    """A stem from `base`, returned as its points."""
    pts = arc(base, spread(parts.rnd, lean), height, bend, steps=steps)
    ribbon(parts, key, pts, width, s=s, taper=0.3, t0=t0)
    return pts


def along(pts, f):
    """The point a fraction `f` along a polyline, and the direction it runs there."""
    i0 = max(0, min(int(f * (len(pts) - 1)), len(pts) - 2))
    p = pts[i0].lerp(pts[i0 + 1], f * (len(pts) - 1) - i0)
    return p, (pts[i0 + 1] - pts[i0]).normalized()


def seed(parts, key, at, direction, length, width, s=None):
    """A small seed or spikelet: a diamond of two quads."""
    blade(parts, key, at, direction, length, width, bend=0.0, segments=2, profile="oval", roll=parts.rnd.uniform(-50, 50), s=s)


def panicle(parts, twig, seed_key, pts, branches, reach, seeds, seed_len, seed_width, droop=0.4, start=0.75, s=None):
    """An open panicle: fine branches off the top of a stem (from `start` of the way up), shorter toward the tip,
    each beaded with small spikelets."""
    rnd = parts.rnd
    for k in range(branches):
        f = rnd.uniform(start, 0.98)
        p, d = along(pts, f)
        a = rnd.uniform(0.0, math.tau)
        out = (d * 0.6 + Vector((math.cos(a), math.sin(a), 0.0)) * 0.8).normalized()
        branch = arc(p, out, reach * rnd.uniform(0.6, 1.0) * (1.2 - (f - start)), droop, steps=4)
        ribbon(parts, twig, branch, 0.0022, s=s)
        for j in range(seeds):
            q, qd = along(branch, rnd.uniform(0.3, 1.0))
            sd = (qd + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3)))).normalized()
            seed(parts, seed_key, q, sd, seed_len * rnd.uniform(0.8, 1.2), seed_width, s=s)


def stubble(parts, key, count, height):
    """Short, burnt-off stalks scattered over the ground."""
    rnd = parts.rnd
    for i in range(count):
        base = Vector((rnd.uniform(-0.44, 0.44), rnd.uniform(-0.18, 0.18), GROUND))
        ribbon(parts, key, arc(base, spread(rnd, 0.5), rnd.uniform(*height), rnd.uniform(0.0, 0.3), steps=3),
               rnd.uniform(0.004, 0.008), taper=0.4)


# ---------------------------------------------------------------- the grasses

def inside(base, direction, length, bend, reach=0.45):
    """`length` cut back until a blade from `base` along `direction` (arching by `bend`) stays within `reach` of the
    tile's middle, so the tile's side border never slices it off square."""
    while length > 0.08 and max(abs(p.x) for p in arc(base, direction, length, bend, steps=7)) > reach:
        length *= 0.9
    return length


def upright(rnd, base, height, lean, bend, reach, steps=10):
    """A stem's points from `base`, re-drawn (up to 20 times) until it stays within `reach` of the tile's middle."""
    pts = arc(base, spread(rnd, lean), rnd.uniform(*height), rnd.uniform(*bend), steps=steps)
    for tries in range(20):
        if max(abs(p.x) for p in pts) < reach:
            break
        pts = arc(base, spread(rnd, lean), rnd.uniform(*height), rnd.uniform(*bend), steps=steps)
    return pts


def hair_grass(parts):
    """Tufted hairgrass: dense, dark green tussocks of fine, stiff blades arching from narrow crowns, under a haze of
    tall, airy panicles of tiny green-silver spikelets on hair-fine branches. A shade grass of damp woods."""
    rnd = parts.rnd
    centers = [-0.27, 0.0, 0.26]
    for c in centers:
        for i in range(56):
            base = clump_bases(rnd, [c], 0.035)
            d, bend = spread(rnd, 0.95), rnd.uniform(0.15, 0.6)
            length = inside(base, d, rnd.uniform(0.22, 0.44), bend)
            blade(parts, "blade", base, d, length, rnd.uniform(0.009, 0.012), bend=bend, profile="fine", roll=rnd.uniform(-60, 60))
        for i in range(rnd.randint(4, 5)):
            pts = upright(rnd, clump_bases(rnd, [c], 0.03), (0.55, 0.8), 0.35, (0.0, 0.15), 0.31)
            ribbon(parts, "stem", pts, 0.0035, taper=0.3)
            panicle(parts, "twig", "seed", pts, 10, 0.1, 4, 0.011, 0.006, droop=0.25, start=0.6, s=rnd.random())


def orchard_grass(parts):
    """Orchard grass (cocksfoot): coarse, loose clumps of broad, flat green blades arching out and over, and stiff
    stems carrying one-sided heads: a few short, stiff branches near the top, all to one side, each ending in a dense
    fist of spikelets, green with a grey-purple bloom."""
    rnd = parts.rnd
    centers = [-0.25, 0.02, 0.27]
    for c in centers:
        for i in range(34):
            base = clump_bases(rnd, [c], 0.045)
            d, bend = spread(rnd, 1.0), rnd.uniform(0.4, 0.95)
            length = inside(base, d, rnd.uniform(0.28, 0.55), bend)
            blade(parts, "blade", base, d, length, rnd.uniform(0.016, 0.022), bend=bend, roll=rnd.uniform(-35, 35))
        for i in range(rnd.randint(3, 5)):
            pts = upright(rnd, clump_bases(rnd, [c], 0.03), (0.58, 0.82), 0.25, (0.0, 0.1), 0.36)
            s = rnd.random()
            ribbon(parts, "stem", pts, 0.005, s=s, taper=0.3)
            # A leaf part way up the stem
            blade(parts, "blade", pts[rnd.randint(2, 4)], spread(rnd, 1.2), rnd.uniform(0.12, 0.2), 0.014, bend=0.6,
                  roll=rnd.uniform(-35, 35))
            # The head: a cluster at the tip and two or three on stiff branches below it, all off one side
            side = rnd.choice((-1, 1))
            clusters = [pts[-1]]
            for k in range(rnd.randint(2, 3)):
                p, d = along(pts, 0.93 - k * 0.045)
                out = (d * 0.8 + Vector((side, rnd.uniform(-0.5, 0.5), 0.0))).normalized()
                end = p + out * (0.045 + 0.025 * k)
                ribbon(parts, "stem", [p, p.lerp(end, 0.5), end], 0.003, s=s)
                clusters.append(end)
            for q in clusters:
                for j in range(18):
                    sd = (Vector((side * 0.6, 0.0, 1.0)) + Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(-0.4, 0.4)))).normalized()
                    seed(parts, "head", q + Vector((rnd.uniform(-0.006, 0.006), rnd.uniform(-0.006, 0.006), rnd.uniform(-0.008, 0.008))),
                         sd, rnd.uniform(0.016, 0.022), 0.011, s=s)


def wild_oats(parts):
    """Wild oats: tall, loose golden-straw stems, some still green, with narrow leaves low down and open panicles of
    papery spikelets dangling from fine branches near the top."""
    rnd = parts.rnd
    for i in range(30):
        base = Vector((rnd.uniform(-0.42, 0.42), rnd.uniform(-0.15, 0.15), GROUND))
        green = rnd.random() < 0.3
        s = rnd.uniform(0.0, 0.3) if green else rnd.uniform(0.4, 1.0)
        height = rnd.uniform(0.6, 0.86)
        pts = arc(base, spread(rnd, 0.22), height, rnd.uniform(0.0, 0.12), steps=10)
        ribbon(parts, "stem", pts, 0.0065, s=s, taper=0.4)
        for k in range(rnd.randint(2, 3)):
            p = pts[rnd.randint(1, 4)]
            blade(parts, "leaf", p, spread(rnd, 1.3), rnd.uniform(0.2, 0.32), rnd.uniform(0.012, 0.016),
                  bend=rnd.uniform(0.35, 0.8), roll=rnd.uniform(-40, 40), s=s)
        # Panicle: whorls of thin branches near the top, each ending in a hanging spikelet
        for k in range(rnd.randint(7, 12)):
            p = pts[rnd.randint(7, 10)]
            a = rnd.uniform(0.0, math.tau)
            out = Vector((math.cos(a), math.sin(a), rnd.uniform(0.2, 0.9))).normalized()
            twig = [p, p + out * 0.05, p + out * 0.09 + Vector((0.0, 0.0, -0.02))]
            ribbon(parts, "twig", twig, 0.0035, s=s)
            tip = twig[-1]
            for side in (-1, 1):
                hang = Vector((side * rnd.uniform(0.08, 0.3), rnd.uniform(-0.2, 0.2), -1.0))
                blade(parts, "spikelet", tip, hang, rnd.uniform(0.03, 0.042), 0.012, bend=0.0, segments=3,
                      roll=rnd.uniform(-40, 40), s=s)
    for i in range(55):
        base = Vector((rnd.uniform(-0.42, 0.42), rnd.uniform(-0.15, 0.15), GROUND))
        blade(parts, "leaf", base, spread(rnd, 1.1), rnd.uniform(0.16, 0.32), rnd.uniform(0.011, 0.015),
              bend=rnd.uniform(0.3, 0.8), roll=rnd.uniform(-40, 40), s=rnd.uniform(0.0, 0.6))


def foxtail(parts):
    """Green foxtail: arching green stems with leafy bases, each ending in a nodding, bristly cylindrical seed head."""
    rnd = parts.rnd
    centers = [-0.28, 0.0, 0.26]
    for i in range(80):
        base = clump_bases(rnd, centers, 0.08)
        blade(parts, "blade", base, spread(rnd, 1.2), rnd.uniform(0.2, 0.4), rnd.uniform(0.012, 0.017),
              bend=rnd.uniform(0.3, 0.8), roll=rnd.uniform(-50, 50))
    for i in range(24):
        base = clump_bases(rnd, centers, 0.06)
        pts = arc(base, spread(rnd, 0.45), rnd.uniform(0.45, 0.7), rnd.uniform(0.1, 0.3), steps=10)
        ribbon(parts, "stem", pts, 0.0055, taper=0.3)
        # The head carries on along the stem and nods over
        d = (pts[-1] - pts[-2]).normalized()
        head = arc(pts[-1], d, rnd.uniform(0.08, 0.11), rnd.uniform(0.3, 0.7), steps=6)
        s = rnd.random()
        ribbon(parts, "head", head, 0.02, s=s, taper=0.35)
        for k in range(70):
            f = rnd.random()
            i0 = min(int(f * (len(head) - 1)), len(head) - 2)
            p = head[i0].lerp(head[i0 + 1], f * (len(head) - 1) - i0)
            hd = (head[i0 + 1] - head[i0]).normalized()
            a = rnd.uniform(0.0, math.tau)
            radial = hd.cross(UP if abs(hd.dot(UP)) < 0.95 else VIEW).normalized()
            radial = Matrix.Rotation(a, 3, hd) @ radial
            tip = p + (radial * 0.85 + hd * 0.5).normalized() * rnd.uniform(0.014, 0.022)
            ribbon(parts, "bristle", [p, tip], 0.0022, s=s, t0=f * 0.6, t1=f * 0.6 + 0.4)


def sedge(parts):
    """A sedge: dense fountains of broad, dark, glossy blades, with a few dark brown seed spikes on stiff stems."""
    rnd = parts.rnd
    centers = [-0.22, 0.2]
    for c in centers:
        for i in range(65):
            base = clump_bases(rnd, [c], 0.07)
            blade(parts, "blade", base, spread(rnd, 0.9), rnd.uniform(0.4, 0.72), rnd.uniform(0.012, 0.018),
                  bend=rnd.uniform(0.15, 0.6), profile="strap" if rnd.random() < 0.4 else "lance", roll=rnd.uniform(-35, 35))
        for i in range(rnd.randint(4, 6)):
            base = clump_bases(rnd, [c], 0.04)
            pts = arc(base, spread(rnd, 0.25), rnd.uniform(0.6, 0.8), 0.05, steps=6)
            ribbon(parts, "stalk", pts, 0.005, t0=0.3)
            d = (pts[-1] - pts[-2]).normalized()
            for k in range(rnd.randint(2, 3)):
                p = pts[-1] - d * (k * 0.035)
                sd = (d + Vector((rnd.uniform(-0.5, 0.5), 0.0, 0.0))).normalized()
                end = p + sd * rnd.uniform(0.035, 0.05)
                ribbon(parts, "spike", [p, p.lerp(end, 0.5), end], 0.011, taper=0.5)


def timothy(parts):
    """Timothy: tall, upright stems from a leafy base, each topped by a dense cylindrical spike, grey-green flushed
    purple."""
    rnd = parts.rnd
    centers = [-0.3, -0.05, 0.22]
    tuft_blades(parts, "blade", centers, 70, (0.2, 0.42), (0.012, 0.016), 1.0, (0.3, 0.75), radius=0.09)
    for i in range(16):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.07), rnd.uniform(0.55, 0.8), 0.18, rnd.uniform(0.0, 0.08), 0.0055, steps=10)
        d = (pts[-1] - pts[-2]).normalized()
        ribbon(parts, "head", [pts[-1] + d * (k * rnd.uniform(0.02, 0.026)) for k in range(5)], 0.014, taper=0.25)
        for k in range(rnd.randint(1, 2)):
            blade(parts, "blade", pts[rnd.randint(2, 5)], spread(rnd, 1.3), rnd.uniform(0.12, 0.2), 0.012, bend=0.6,
                  roll=rnd.uniform(-40, 40))


def bracken(parts):
    """Bracken: coarse fern fronds on short bare stalks, each a broad blade of paired leaflets leaning out and over,
    shrinking to its tip; yellow-green, a few browning. The fronds are turned to face the camera: a flat frond seen
    from the side is only its stalk."""
    rnd = parts.rnd
    for i in range(9):
        base = Vector((rnd.uniform(-0.26, 0.26), rnd.uniform(-0.12, 0.12), GROUND))
        s = rnd.random()
        stalk = arc(base, spread(rnd, 0.15), rnd.uniform(0.18, 0.38), 0.0, steps=4)
        ribbon(parts, "stalk", stalk, 0.007, s=s)
        # Leaning back across the tile, so it stays inside it
        lean = -1.0 if base.x > 0.0 else 1.0
        out = Vector((lean * rnd.uniform(0.5, 1.0), rnd.uniform(-0.15, 0.15), rnd.uniform(0.5, 0.9)))
        rachis = arc(stalk[-1], out, rnd.uniform(0.26, 0.38), rnd.uniform(0.3, 0.55), steps=8)
        ribbon(parts, "stalk", rachis, 0.005, s=s, taper=0.6)
        for k in range(1, 11):
            p, d = along(rachis, k / 11.0)
            size = 1.0 - k / 12.0
            perp = d.cross(VIEW).normalized()
            for sgn in (-1, 1):
                blade(parts, "leaf", p, (perp * sgn + d * 0.45 + Vector((0.0, 0.0, -0.15))).normalized(), 0.12 * size + 0.03,
                      0.03 * size + 0.012, bend=0.2, segments=4, roll=90.0 + rnd.uniform(-25, 25), s=s)


def redtop(parts):
    """Redtop: a low mat of fine leaves under a haze of airy, reddish-purple panicles on slender stems."""
    rnd = parts.rnd
    centers = [-0.3, 0.0, 0.28]
    tuft_blades(parts, "blade", centers, 90, (0.15, 0.3), (0.008, 0.012), 1.3, (0.4, 0.9), radius=0.1)
    for i in range(22):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.08), rnd.uniform(0.5, 0.78), 0.3, rnd.uniform(0.0, 0.15), 0.0045, steps=10)
        panicle(parts, "twig", "seed", pts, 9, 0.09, 5, 0.013, 0.008, droop=0.3, start=0.72, s=rnd.random())


def clover_patch(parts):
    """Clover and plantain: a low mat of white clover trefoils and round flower heads, with broad plantain rosettes
    and a few thin plantain spikes, all under 30 cm."""
    rnd = parts.rnd
    for i in range(90):
        base = Vector((rnd.uniform(-0.44, 0.44), rnd.uniform(-0.2, 0.2), GROUND))
        s = rnd.random()
        st = arc(base, spread(rnd, 0.5), rnd.uniform(0.06, 0.2), 0.1, steps=3)
        ribbon(parts, "stalk", st, 0.003, s=s)
        a = rnd.uniform(0.0, math.tau)
        for k in range(3):
            ang = a + k * math.tau / 3
            # Leaflets spread out flat-ish, tipped toward the camera so they read from the side
            blade(parts, "clover", st[-1], Vector((math.cos(ang), math.sin(ang) * 0.4 - 0.5, rnd.uniform(0.15, 0.5))), 0.045, 0.04,
                  bend=0.1, segments=3, profile="oval", s=s)
    for i in range(16):
        st = arc(Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.2, 0.2), GROUND)), spread(rnd, 0.35), rnd.uniform(0.15, 0.28), 0.1, steps=4)
        ribbon(parts, "stalk", st, 0.0035)
        s = rnd.random()
        for k in range(18):
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 1.0))).normalized()
            seed(parts, "flower", st[-1] - d * 0.008, d, 0.02, 0.008, s=s)
    for c in (-0.25, 0.22):
        for k in range(8):
            a = k / 8 * math.tau + rnd.uniform(-0.2, 0.2)
            blade(parts, "plantain", Vector((c, rnd.uniform(-0.05, 0.05), GROUND)), Vector((math.cos(a), math.sin(a), 0.45)),
                  rnd.uniform(0.14, 0.2), 0.06, bend=0.35, segments=5, profile="oval")
        for k in range(rnd.randint(2, 3)):
            st = arc(Vector((c, 0.0, GROUND)), spread(rnd, 0.3), rnd.uniform(0.2, 0.3), 0.05, steps=5)
            ribbon(parts, "stalk", st, 0.003)
            d = (st[-1] - st[-2]).normalized()
            ribbon(parts, "spike", [st[-1] + d * (j * 0.012) for j in range(4)], 0.008, taper=0.3)


def dry_bunchgrass(parts):
    """Dry bunchgrass: tawny, sun-cured clumps of fine blades curling out and over, a few seed stalks above."""
    rnd = parts.rnd
    centers = [-0.27, 0.05, 0.3]
    tuft_blades(parts, "blade", centers, 85, (0.22, 0.45), (0.009, 0.013), 1.2, (0.5, 1.1), radius=0.05, profile="fine")
    for i in range(12):
        pts = stem(parts, "stalk", clump_bases(rnd, centers, 0.04), rnd.uniform(0.5, 0.7), 0.35, rnd.uniform(0.1, 0.3), 0.004)
        panicle(parts, "stalk", "seed", pts, 5, 0.05, 3, 0.016, 0.006, droop=0.2, start=0.8)


def horsetail(parts):
    """Horsetail: a stand of upright, jointed green stems with whorls of fine needle-like branches at each joint,
    longest low down."""
    rnd = parts.rnd
    for i in range(26):
        base = Vector((rnd.uniform(-0.42, 0.42), rnd.uniform(-0.15, 0.15), GROUND))
        pts = stem(parts, "stem", base, rnd.uniform(0.25, 0.55), 0.12, 0.0, 0.006)
        nodes = rnd.randint(5, 8)
        for k in range(1, nodes + 1):
            p, d = along(pts, k / (nodes + 1.0))
            length = 0.07 * (1.1 - k / (nodes + 1.0))
            for j in range(8):
                a = j / 8 * math.tau + rnd.uniform(-0.2, 0.2)
                end = p + Vector((math.cos(a), math.sin(a), 0.6)).normalized() * length
                ribbon(parts, "needle", [p, p.lerp(end, 0.5) + Vector((0.0, 0.0, -0.005)), end], 0.0018)


def sheep_sorrel(parts):
    """Sheep sorrel among grass: thin branching stems hazed with tiny rust-red seeds over low, narrow leaves; the red
    tinge over a poor meadow in summer."""
    rnd = parts.rnd
    centers = [-0.25, 0.1, 0.32]
    tuft_blades(parts, "blade", centers, 50, (0.15, 0.3), (0.01, 0.014), 1.2, (0.4, 0.9), radius=0.1)
    tuft_blades(parts, "leaf", centers, 18, (0.06, 0.1), (0.022, 0.028), 1.2, (0.3, 0.5), radius=0.08)
    for i in range(20):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.08), rnd.uniform(0.35, 0.55), 0.3, 0.05, 0.004)
        s = rnd.random()
        branches = [pts]
        for k in range(rnd.randint(3, 5)):
            p, d = along(pts, rnd.uniform(0.45, 0.85))
            a = rnd.uniform(0.0, math.tau)
            branch = arc(p, (d + Vector((math.cos(a), math.sin(a), 0.0)) * 0.6).normalized(), rnd.uniform(0.06, 0.12), 0.1, steps=4)
            ribbon(parts, "stem", branch, 0.003)
            branches.append(branch)
        for b in branches:
            for j in range(10):
                q, _ = along(b, rnd.uniform(0.4 if b is pts else 0.2, 1.0))
                seed(parts, "seed", q, Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 1.0))).normalized(), 0.009, 0.008, s=s)


def blue_grama(parts):
    """Blue grama: a low, curly mat of fine grey-green blades, with wiry stems each holding one or two curved
    "eyebrow" seed heads off to the side, tinged purple."""
    rnd = parts.rnd
    centers = [-0.3, -0.05, 0.2, 0.38]
    tuft_blades(parts, "blade", centers, 100, (0.1, 0.22), (0.008, 0.011), 1.4, (0.6, 1.2), profile="fine")
    for i in range(18):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.05), rnd.uniform(0.28, 0.45), 0.25, 0.05, 0.0035)
        s = rnd.random()
        for k in range(rnd.randint(1, 2)):
            p, d = along(pts, 0.88 + k * 0.1)
            flag = arc(p, Vector((rnd.choice((-1, 1)), rnd.uniform(-0.3, 0.3), 0.2)), 0.04, 0.6, steps=5)
            ribbon(parts, "head", flag, 0.005, s=s)
            for j in range(12):
                q, qd = along(flag, (j + 0.5) / 12)
                seed(parts, "comb", q, (Vector((0.0, 0.0, -1.0)) + qd * 0.2).normalized(), 0.011, 0.004, s=s)


def needlegrass(parts):
    """Indian ricegrass: fine, pale straw tussocks under a cloud of wiry, zig-zag branches tipped with plump
    white seeds."""
    rnd = parts.rnd
    centers = [-0.25, 0.05, 0.3]
    tuft_blades(parts, "blade", centers, 100, (0.22, 0.4), (0.01, 0.013), 1.0, (0.3, 0.8), radius=0.05, profile="fine")
    for i in range(22):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.04), rnd.uniform(0.38, 0.58), 0.4, 0.1, 0.004)
        for k in range(rnd.randint(5, 8)):
            zig = [along(pts, rnd.uniform(0.6, 1.0))[0]]
            for j in range(3):
                a = rnd.uniform(0.0, math.tau)
                zig.append(zig[-1] + Vector((math.cos(a) * 0.035, math.sin(a) * 0.02, rnd.uniform(0.0, 0.03))))
            ribbon(parts, "twig", zig, 0.003)
            seed(parts, "seed", zig[-1], Vector((rnd.uniform(-0.5, 0.5), 0.0, 1.0)), 0.016, 0.011)


def cotton_grass(parts):
    """Cotton grass: sedge-like blades, green going rusty, under slender stems each topped with a bright white tuft
    of silky bristles."""
    rnd = parts.rnd
    centers = [-0.3, 0.0, 0.28]
    tuft_blades(parts, "blade", centers, 60, (0.18, 0.35), (0.009, 0.012), 0.9, (0.3, 0.8))
    for i in range(18):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.06), rnd.uniform(0.35, 0.55), 0.25, 0.08, 0.0035)
        top = pts[-1]
        for j in range(45):
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 1.0))).normalized()
            ribbon(parts, "cotton", [top, top + d * rnd.uniform(0.016, 0.032)], 0.003)


def frost_tussock(parts):
    """A frosted tussock: dense mounds of fine grey-green blades whitened toward their tips by hoarfrost, with a few
    frosty seed stalks."""
    rnd = parts.rnd
    centers = [-0.28, 0.02, 0.3]
    for c in centers:
        tuft_blades(parts, "blade", [c], 80, (0.25, 0.42), (0.008, 0.011), 1.4, (0.3, 0.8), radius=0.05, profile="fine")
        for i in range(rnd.randint(3, 5)):
            pts = stem(parts, "stalk", clump_bases(rnd, [c], 0.03), rnd.uniform(0.45, 0.6), 0.3, 0.1, 0.0045)
            panicle(parts, "stalk", "seed", pts, 4, 0.04, 3, 0.014, 0.006, droop=0.1, start=0.85)


def burnt_stubble(parts):
    """Burnt stubble: short, charred black stalks of grass after a fire, with fresh green shoots pushing up through
    them."""
    stubble(parts, "char", 90, (0.08, 0.3))
    tuft_blades(parts, "shoot", [-0.3, -0.05, 0.2, 0.36], 80, (0.16, 0.38), (0.012, 0.016), 0.8, (0.2, 0.6), radius=0.05)


def green_shoots(parts):
    """Regrowth after a fire: dense young grass, bright and fresh, a few dead tan blades left from before and black
    stubble at its feet."""
    centers = [-0.32, -0.1, 0.12, 0.33]
    stubble(parts, "char", 25, (0.05, 0.16))
    tuft_blades(parts, "dead", centers, 30, (0.2, 0.38), (0.01, 0.013), 1.4, (0.6, 1.1), radius=0.07)
    tuft_blades(parts, "blade", centers, 150, (0.26, 0.5), (0.012, 0.016), 1.0, (0.2, 0.7), radius=0.08)


def cheatgrass(parts):
    """Cheatgrass: weedy brome gone purple-red as it dries, its spikelets hanging on hair-thin stalks from the top of
    its nodding stems."""
    rnd = parts.rnd
    centers = [-0.3, -0.02, 0.27]
    tuft_blades(parts, "blade", centers, 50, (0.12, 0.25), (0.009, 0.012), 1.2, (0.4, 0.9), radius=0.08)
    for i in range(26):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.07), rnd.uniform(0.3, 0.5), 0.35, rnd.uniform(0.2, 0.5), 0.0035)
        s = rnd.random()
        for k in range(rnd.randint(5, 8)):
            p, d = along(pts, rnd.uniform(0.7, 1.0))
            out = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5), -0.2)).normalized()
            hang = arc(p, out, rnd.uniform(0.03, 0.05), 0.6, steps=3)
            ribbon(parts, "twig", hang, 0.0018, s=s)
            blade(parts, "spikelet", hang[-1], Vector((out.x * 0.3, 0.0, -1.0)), rnd.uniform(0.024, 0.032), 0.008, bend=0.0,
                  segments=3, s=s)


def foxtail_barley(parts):
    """Foxtail barley: nodding, silky heads of long fine awns, pink-purple fading to silver, over grey-green blades."""
    rnd = parts.rnd
    centers = [-0.28, 0.02, 0.28]
    tuft_blades(parts, "blade", centers, 55, (0.14, 0.28), (0.009, 0.012), 1.1, (0.3, 0.8), radius=0.07)
    for i in range(18):
        pts = stem(parts, "stem", clump_bases(rnd, centers, 0.06), rnd.uniform(0.35, 0.55), 0.3, rnd.uniform(0.15, 0.4), 0.0035)
        head = arc(pts[-1], (pts[-1] - pts[-2]).normalized(), rnd.uniform(0.05, 0.08), rnd.uniform(0.3, 0.6), steps=5)
        s = rnd.random()
        ribbon(parts, "head", head, 0.008, s=s)
        for j in range(40):
            p, hd = along(head, rnd.random())
            radial = hd.cross(UP if abs(hd.dot(UP)) < 0.95 else VIEW).normalized()
            radial = Matrix.Rotation(rnd.uniform(0.0, math.tau), 3, hd) @ radial
            tip = p + (radial * 0.45 + hd * 0.9).normalized() * rnd.uniform(0.04, 0.07)
            ribbon(parts, "awn", [p, p.lerp(tip, 0.5), tip], 0.0016, s=s)


# name: (builder, seed, {part: (sRGB base at s=0, at s=1, tip at s=0, at s=1)})
GRASSES = {
    "HairGrass": (hair_grass, 11, {
        "blade": ((16, 26, 10), (20, 30, 12), (46, 66, 24), (54, 72, 28)),
        # The haze kept a darker green than the blades' tips: paler, it read as pale lime puffs in the sun
        "stem": ((30, 42, 16), (36, 46, 20), (54, 68, 30), (62, 72, 34)),
        "twig": ((44, 58, 24), (52, 60, 30), (60, 76, 34), (68, 78, 40)),
        "seed": ((54, 70, 30), (62, 72, 36), (72, 90, 42), (82, 94, 50)),
    }),
    "OrchardGrass": (orchard_grass, 73, {
        "blade": ((22, 36, 14), (28, 40, 18), (58, 82, 34), (68, 88, 40)),
        "stem": ((34, 48, 20), (40, 52, 24), (64, 82, 36), (72, 86, 42)),
        "head": ((52, 70, 32), (62, 68, 46), (78, 98, 50), (90, 94, 70)),
    }),
    "WildOats": (wild_oats, 23, {
        "stem": ((40, 50, 22), (78, 66, 36), (62, 72, 34), (138, 116, 64)),
        "leaf": ((34, 44, 18), (70, 58, 30), (60, 70, 30), (120, 100, 54)),
        "twig": ((70, 78, 40), (110, 94, 52), (82, 88, 46), (126, 106, 60)),
        "spikelet": ((84, 94, 52), (132, 112, 64), (110, 116, 70), (164, 142, 86)),
    }),
    "Foxtail": (foxtail, 37, {
        "blade": ((26, 38, 12), (34, 44, 16), (58, 76, 28), (70, 84, 34)),
        "stem": ((34, 46, 16), (40, 50, 20), (60, 74, 30), (68, 80, 34)),
        "head": ((54, 66, 30), (70, 66, 38), (78, 90, 44), (96, 88, 54)),
        "bristle": ((70, 84, 40), (96, 86, 56), (96, 106, 58), (126, 110, 74)),
    }),
    "Sedge": (sedge, 41, {
        "blade": ((12, 22, 9), (16, 26, 12), (36, 54, 20), (44, 60, 24)),
        "stalk": ((26, 34, 14), (30, 36, 16), (40, 46, 22), (46, 50, 24)),
        "spike": ((40, 30, 18), (48, 34, 20), (58, 44, 26), (66, 48, 28)),
    }),
    "Timothy": (timothy, 43, {
        "blade": ((26, 40, 14), (32, 44, 16), (56, 74, 28), (66, 82, 34)),
        "stem": ((34, 46, 18), (40, 50, 22), (60, 72, 30), (70, 78, 36)),
        "head": ((52, 54, 40), (66, 52, 62), (80, 84, 64), (98, 80, 94)),
    }),
    "Bracken": (bracken, 47, {
        "stalk": ((44, 40, 22), (60, 48, 26), (70, 72, 34), (90, 80, 40)),
        "leaf": ((34, 50, 14), (70, 62, 24), (66, 88, 26), (112, 96, 40)),
    }),
    "Redtop": (redtop, 53, {
        "blade": ((24, 38, 12), (30, 42, 16), (52, 70, 26), (62, 78, 32)),
        "stem": ((40, 44, 22), (56, 44, 30), (62, 64, 34), (84, 58, 44)),
        "twig": ((70, 44, 40), (84, 50, 50), (96, 58, 54), (116, 66, 66)),
        "seed": ((96, 46, 48), (116, 58, 62), (128, 66, 64), (150, 82, 80)),
    }),
    "Clover": (clover_patch, 59, {
        "stalk": ((32, 48, 18), (38, 52, 22), (46, 62, 26), (52, 66, 30)),
        "clover": ((22, 40, 16), (30, 48, 22), (40, 66, 28), (52, 76, 34)),
        "flower": ((150, 146, 132), (160, 130, 140), (196, 192, 178), (204, 170, 180)),
        "plantain": ((24, 40, 14), (30, 46, 18), (44, 66, 24), (52, 72, 28)),
        "spike": ((60, 58, 38), (70, 64, 44), (84, 80, 54), (96, 90, 60)),
    }),
    "DryBunchgrass": (dry_bunchgrass, 61, {
        "blade": ((60, 52, 32), (70, 60, 38), (110, 94, 62), (128, 108, 72)),
        "stalk": ((70, 62, 40), (80, 70, 46), (110, 98, 66), (124, 108, 74)),
        "seed": ((110, 96, 64), (124, 108, 72), (140, 124, 84), (154, 134, 92)),
    }),
    "Horsetail": (horsetail, 67, {
        "stem": ((26, 40, 16), (30, 44, 20), (54, 78, 30), (62, 86, 36)),
        "needle": ((30, 48, 18), (36, 54, 22), (58, 84, 32), (66, 92, 38)),
    }),
    "SheepSorrel": (sheep_sorrel, 71, {
        "blade": ((26, 40, 14), (32, 44, 16), (54, 72, 28), (64, 78, 32)),
        "leaf": ((30, 46, 18), (36, 50, 20), (50, 70, 28), (58, 74, 30)),
        "stem": ((50, 36, 22), (62, 42, 28), (88, 52, 34), (104, 58, 38)),
        "seed": ((92, 34, 24), (110, 48, 30), (130, 52, 32), (150, 72, 40)),
    }),
    "BlueGrama": (blue_grama, 79, {
        "blade": ((44, 48, 32), (54, 52, 36), (90, 94, 68), (108, 104, 74)),
        "stem": ((60, 58, 40), (70, 64, 46), (96, 92, 66), (110, 100, 72)),
        "head": ((70, 52, 56), (90, 70, 60), (110, 86, 90), (130, 108, 92)),
        "comb": ((84, 62, 66), (104, 82, 70), (124, 96, 100), (146, 120, 104)),
    }),
    "Needlegrass": (needlegrass, 83, {
        "blade": ((66, 62, 42), (76, 70, 48), (130, 120, 86), (146, 134, 96)),
        "stem": ((80, 74, 52), (90, 82, 58), (130, 122, 90), (142, 132, 98)),
        "twig": ((90, 84, 60), (100, 92, 66), (136, 128, 96), (148, 138, 104)),
        "seed": ((150, 146, 132), (160, 154, 138), (190, 186, 170), (200, 194, 176)),
    }),
    "CottonGrass": (cotton_grass, 89, {
        "blade": ((26, 38, 18), (54, 44, 24), (52, 66, 30), (96, 70, 38)),
        "stem": ((40, 50, 24), (48, 52, 28), (70, 76, 40), (80, 80, 44)),
        "cotton": ((170, 170, 164), (180, 178, 170), (214, 214, 208), (222, 220, 214)),
    }),
    "FrostTussock": (frost_tussock, 97, {
        "blade": ((34, 42, 40), (40, 46, 44), (140, 150, 154), (160, 166, 170)),
        "stalk": ((60, 64, 60), (70, 72, 66), (150, 156, 158), (168, 172, 172)),
        "seed": ((140, 144, 144), (150, 152, 150), (190, 194, 196), (200, 204, 204)),
    }),
    "BurntStubble": (burnt_stubble, 101, {
        "char": ((10, 9, 8), (18, 15, 12), (30, 27, 24), (44, 38, 32)),
        "shoot": ((28, 50, 12), (34, 56, 16), (64, 96, 26), (76, 104, 32)),
    }),
    "GreenShoots": (green_shoots, 103, {
        "char": ((10, 9, 8), (18, 15, 12), (30, 27, 24), (44, 38, 32)),
        "dead": ((64, 56, 38), (72, 62, 42), (104, 92, 64), (118, 104, 72)),
        "blade": ((26, 46, 12), (32, 52, 14), (62, 92, 26), (72, 100, 30)),
    }),
    "Cheatgrass": (cheatgrass, 107, {
        "blade": ((40, 40, 24), (54, 40, 34), (76, 72, 44), (96, 70, 62)),
        "stem": ((54, 44, 34), (70, 46, 44), (96, 74, 62), (120, 80, 80)),
        "twig": ((80, 60, 56), (96, 64, 66), (110, 84, 78), (130, 88, 92)),
        "spikelet": ((96, 70, 64), (120, 76, 84), (136, 104, 90), (160, 110, 118)),
    }),
    "FoxtailBarley": (foxtail_barley, 109, {
        "blade": ((36, 46, 36), (42, 50, 40), (70, 84, 66), (80, 90, 72)),
        "stem": ((50, 56, 40), (60, 58, 46), (84, 88, 64), (96, 90, 72)),
        "head": ((90, 64, 76), (104, 74, 84), (130, 104, 116), (146, 120, 128)),
        "awn": ((116, 80, 98), (130, 96, 108), (186, 176, 180), (200, 192, 194)),
    }),
}


# ---------------------------------------------------------------- materials and rendering

def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat, nodes, links, emit


def color_material(name, colors):
    """Unlit albedo: base color shading to tip color along "t", picked between two per part by "s", a little
    brighter or darker part to part, and darker the further back a part stands."""
    base0, base1, tip0, tip1 = (srgb(c) for c in colors)
    mat, nodes, links, emit = node_material(name)
    t = nodes.new("ShaderNodeAttribute")
    t.attribute_name = "t"
    s = nodes.new("ShaderNodeAttribute")
    s.attribute_name = "s"

    def mix(fac, a, b):
        m = nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        links.new(fac, m.inputs["Factor"])
        for sock, v in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(v, tuple):
                sock.default_value = v
            else:
                links.new(v, sock)
        return m.outputs[2]

    def math_node(op, a, b=None):
        m = nodes.new("ShaderNodeMath")
        m.operation = op
        for sock, v in zip(m.inputs, (a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                links.new(v, sock)
        return m.outputs[0]

    base = mix(s.outputs["Fac"], base0, base1)
    tip = mix(s.outputs["Fac"], tip0, tip1)
    col = mix(math_node("POWER", t.outputs["Fac"], 0.8), base, tip)
    # Brightness part to part, from a second hash of "s"
    jitter = math_node("ADD", 0.86, math_node("MULTIPLY", math_node("FRACT", math_node("MULTIPLY", s.outputs["Fac"], 7.13)), 0.28))
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs[0])
    back = math_node("MINIMUM", math_node("MAXIMUM", math_node("MULTIPLY", math_node("ADD", sep.outputs["Y"], 0.3), 1.6), 0.0), 1.0)
    shade = math_node("MULTIPLY", jitter, math_node("SUBTRACT", 1.0, math_node("MULTIPLY", back, 0.25)))
    final = nodes.new("ShaderNodeVectorMath")
    final.operation = "SCALE"
    links.new(col, final.inputs[0])
    links.new(shade, final.inputs["Scale"])
    links.new(final.outputs[0], emit.inputs["Color"])
    return mat


def normal_material():
    """Camera-space normals, turned to face the camera on a sheet's far side."""
    mat, nodes, links, emit = node_material("Normals")
    geo = nodes.new("ShaderNodeNewGeometry")
    flip = nodes.new("ShaderNodeMath")
    flip.operation = "MULTIPLY_ADD"
    links.new(geo.outputs["Backfacing"], flip.inputs[0])
    flip.inputs[1].default_value = -2.0
    flip.inputs[2].default_value = 1.0
    n = nodes.new("ShaderNodeVectorMath")
    n.operation = "SCALE"
    links.new(geo.outputs["Normal"], n.inputs[0])
    links.new(flip.outputs[0], n.inputs["Scale"])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(n.outputs[0], sep.inputs[0])
    comb = nodes.new("ShaderNodeCombineColor")
    for i, (src, sign) in enumerate((("X", 0.5), ("Z", 0.5), ("Y", -0.5))):
        m = nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY_ADD"
        links.new(sep.outputs[src], m.inputs[0])
        m.inputs[1].default_value = sign
        m.inputs[2].default_value = 0.5
        links.new(m.outputs[0], comb.inputs[i])
    links.new(comb.outputs[0], emit.inputs["Color"])
    return mat


def t_material():
    mat, nodes, links, emit = node_material("T")
    t = nodes.new("ShaderNodeAttribute")
    t.attribute_name = "t"
    links.new(t.outputs["Fac"], emit.inputs["Color"])
    return mat


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.dither_intensity = 0.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    cam_data = bpy.data.cameras.new("Tile")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 1.0
    cam = bpy.data.objects.new("Tile", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, -5.0, GROUND + 0.5)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.camera = cam
    return scene


def render(scene, path, view):
    scene.view_settings.view_transform = view
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(HERE, "..", "..", "unity", "Build", "grass")
    only = set(argv[1].split(",")) if len(argv) > 1 else None
    os.makedirs(out, exist_ok=True)
    listed = [line.split()[1] for line in open(os.path.join(HERE, "grasses.txt"), encoding="utf-8")
              if line.strip() and not line.startswith("#")]
    for name in listed:
        if only and name not in only:
            continue
        if name not in GRASSES:
            print("[grass] %s is listed but has no builder here" % name)
            continue
        build, seed, colors = GRASSES[name]
        scene = setup()
        parts = Parts(seed)
        build(parts)
        materials = {k: color_material(name + k, c) for k, c in colors.items()}
        objs = parts.build(materials)
        render(scene, os.path.join(out, name + "_Color.png"), "Standard")
        for mat, suffix in ((normal_material(), "_Normal.png"), (t_material(), "_T.png")):
            for o in objs:
                o.data.materials[0] = mat
            render(scene, os.path.join(out, name + suffix), "Raw")
        tris = sum(len(o.data.polygons) * 2 for o in objs)
        print("[grass] %s: %d triangles rendered" % (name, tris))


main()
