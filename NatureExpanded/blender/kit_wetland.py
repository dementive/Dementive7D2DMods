"""Helpers for the water's edge, snow and wasteland plants (cattail, reeds, blue flag iris, marsh marigold, alpine
aster, heather, silver sage), on top of naturekit.py. Kept in their own file so naturekit stays as it is for the
other plants.

Every part returns one object with the float attribute "t" (0 at its base, 1 at its tip), like naturekit's, and
packs a whole head, spike or plume into that one object, so a dense clump stays a few hundred objects for the join.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import naturekit as nk
import zkit as tk

UP = Vector((0.0, 0.0, 1.0))


def _obj(name, bm, material, ts, smooth=False):
    obj = tk.mesh_object(name, bm, material)
    nk._set_t(obj, ts)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def _perp(d):
    """A unit vector across `d`, horizontal where it can be."""
    side = d.cross(UP)
    if side.length < 1e-4:
        side = d.cross(Vector((1.0, 0.0, 0.0)))
    return side.normalized()


def _width(profile, s):
    if profile == "lance":
        return max(0.0, (1.0 - s) ** 0.8 * min(1.0, s * 3.0 + 0.15))
    if profile == "oval":
        return math.sin(math.pi * s) ** 0.7
    if profile == "strap":
        return 1.0 if s < 0.85 else (1.0 - s) / 0.15
    if profile == "spoon":
        return min(1.0, 0.25 + s * 1.2) * (math.sin(math.pi * min(s, 0.999)) ** 0.25 if s > 0.6 else 1.0)
    if profile == "heart":
        return (1.0 - s) ** 0.6
    if profile == "sword":
        # Iris leaves: even width up most of the blade, a long sharp point
        return min(1.0, 0.55 + s * 4.0) * (1.0 if s < 0.7 else ((1.0 - s) / 0.3) ** 0.85)
    if profile == "linear":
        # Reed and grass leaves: widest near the base, a long fine taper
        return min(1.0, 0.45 + s * 5.0) * (1.0 - s) ** 0.75
    if profile == "raceme":
        # A spike of tiny flowers seen as one shape: full width most of its length, a short rounded point
        return min(1.0, 0.45 + s * 2.5) * max(0.0, 1.0 - s ** 4) ** 0.5
    if profile == "fall":
        # An iris fall: a narrow haft, then a broad round blade
        return 0.25 + 0.75 * math.sin(math.pi * min(1.0, s * 0.75)) ** 1.6 if s < 0.97 else 0.4
    return 1.0


# ---------------------------------------------------------------- stems and leaves

def rod(name, points, r0, r1, material, sides=3):
    """A thin tapered stem along a polyline, `r0` thick at its first point and `r1` at its last, open-ended and
    smooth-shaded (cheaper than naturekit's capped tube: a reed or twig is 6 triangles a segment)."""
    pts = [Vector(p) for p in points]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1] or 1.0
    bm = bmesh.new()
    rings, ts = [], []
    side = None
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = _perp(d) if side is None else (side - d * side.dot(d)).normalized()
        up = d.cross(side)
        s = lengths[i] / total
        r = r0 + (r1 - r0) * s
        rings.append([bm.verts.new(p + (side * math.cos(a) + up * math.sin(a)) * r)
                      for a in (k / sides * math.tau for k in range(sides))])
        ts += [s] * sides
    for r_a, r_b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((r_a[k], r_a[(k + 1) % sides], r_b[(k + 1) % sides], r_b[k]))
    return _obj(name, bm, material, ts, smooth=True)


def leaf(name, base, direction, length, width, material, arch=0.3, power=2.0, twist=0.0, segments=6,
         profile="lance", roll=0.0, toward=None):
    """A leaf, petal or blade that arches properly: its direction turns from `direction` toward the outside and down
    by `arch` quarter turns at the tip (1 = turned 90 degrees, 2 = turned right round; negative curls it up and in),
    `power` how late along the blade the turn comes. Unlike naturekit's blade it keeps its length on near-upright
    leaves (cattail, iris, reed). `roll` turns the blade about its own axis (90 puts the flat of it in the plane it
    bends in, the way an iris leaf curves like a scimitar); `toward` names the outside for an upright one. A blade
    that narrows to nothing ends in a single point."""
    d0 = Vector(direction).normalized()
    h = Vector(toward) if toward is not None else Vector((d0.x, d0.y, 0.0))
    h.z = 0.0
    if h.length < 1e-4:
        h = Vector((1.0, 0.0, 0.0))
    h.normalize()
    axis = UP.cross(h).normalized()
    if abs(axis.dot(d0)) > 0.99:
        axis = _perp(d0)
    # Keep the bend axis square to the leaf
    axis = (axis - d0 * axis.dot(d0)).normalized()
    bm = bmesh.new()
    ts, rows = [], []
    center = Vector(base)
    step = length / segments
    for i in range(segments + 1):
        s = i / segments
        ang = arch * (math.pi * 0.5) * s ** power
        d = Matrix.Rotation(ang, 3, axis) @ d0
        if i > 0:
            mid = Matrix.Rotation(arch * (math.pi * 0.5) * ((i - 0.5) / segments) ** power, 3, axis) @ d0
            center = center + mid * step
        sv = Matrix.Rotation(math.radians(roll + twist * s), 3, d) @ axis
        w = _width(profile, s) * width * 0.5
        if w < 1e-5 and i == segments:
            rows.append((bm.verts.new(center),))
        else:
            rows.append((bm.verts.new(center - sv * w), bm.verts.new(center + sv * w)))
        ts += [s] * len(rows[-1])
    for r_a, r_b in zip(rows, rows[1:]):
        if len(r_b) == 1:
            bm.faces.new((r_a[0], r_a[1], r_b[0]))
        else:
            bm.faces.new((r_a[0], r_a[1], r_b[1], r_b[0]))
    return _obj(name, bm, material, ts)


def needles(name, points, count, length, width, material, seed=0, spread=55.0, droop=0.0):
    """Fine needle or scale leaves all along a twig's polyline (heather, sage sprigs): `count` single-triangle
    needles spiraling round it, pointing out and up from the twig by about `spread` degrees."""
    rnd = random.Random(seed)
    pts = [Vector(p) for p in points]
    seglens = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(seglens) or 1.0
    bm = bmesh.new()
    ts = []
    for i in range(count):
        u = (i + rnd.uniform(0.1, 0.9)) / count * total
        k = 0
        while k < len(seglens) - 1 and u > seglens[k]:
            u -= seglens[k]
            k += 1
        d = (pts[k + 1] - pts[k]).normalized()
        at = pts[k] + d * min(u, seglens[k])
        side = _perp(d)
        up = d.cross(side)
        a = i * 2.39996 + rnd.uniform(-0.3, 0.3)
        out = side * math.cos(a) + up * math.sin(a)
        sp = math.radians(spread * rnd.uniform(0.7, 1.2))
        nd = (d * math.cos(sp) + out * math.sin(sp) - UP * droop).normalized()
        across = nd.cross(out).normalized()
        n = length * rnd.uniform(0.75, 1.2)
        w = width * 0.5
        v0 = bm.verts.new(at - across * w)
        v1 = bm.verts.new(at + across * w)
        v2 = bm.verts.new(at + nd * n)
        bm.faces.new((v0, v1, v2))
        ts += [0.2, 0.2, 1.0]
    return _obj(name, bm, material, ts)


def brush(name, base, direction, length, width, material, blades=3, arch=0.15, seed=0, profile="lance", segments=3,
          twist=0.0):
    """A spike or spray that reads solid from any side without alpha: `blades` narrow blades crossed round one axis
    (heather racemes, foliage sprays, sage flower spikes), arching a little toward a random side."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    a = rnd.uniform(0, math.tau)
    toward = Vector((math.cos(a), math.sin(a), 0.0))
    parts = []
    r0 = rnd.uniform(0, 180.0 / blades)
    for k in range(blades):
        parts.append(leaf("%s%d" % (name, k), base, d, length * rnd.uniform(0.9, 1.05), width * rnd.uniform(0.85, 1.1),
                          material, arch=arch, power=1.6, twist=twist, segments=segments, profile=profile,
                          roll=r0 + k * 180.0 / blades, toward=toward))
    return parts


# ---------------------------------------------------------------- heads

def sausage(name, base, axis, length, radius, material, sides=8, seed=0):
    """A cattail's velvet head: a long cylinder with rounded ends from `base` along `axis`, a little uneven."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    side = _perp(ax)
    up = ax.cross(side)
    prof = ((0.0, 0.0), (0.025, 0.72), (0.09, 0.97), (0.5, 1.0 + rnd.uniform(-0.04, 0.05)), (0.91, 0.96),
            (0.975, 0.7), (1.0, 0.0))
    bm = bmesh.new()
    rows, ts = [], []
    for s, r in prof:
        c = Vector(base) + ax * (length * s)
        if r == 0.0:
            rows.append([bm.verts.new(c)])
        else:
            rows.append([bm.verts.new(c + (side * math.cos(a) + up * math.sin(a)) * radius * r *
                                      (1.0 + rnd.uniform(-0.03, 0.03)))
                         for a in (k / sides * math.tau for k in range(sides))])
        ts += [s] * len(rows[-1])
    for r_a, r_b in zip(rows, rows[1:]):
        for k in range(sides):
            if len(r_a) == 1:
                bm.faces.new((r_a[0], r_b[k], r_b[(k + 1) % sides]))
            elif len(r_b) == 1:
                bm.faces.new((r_a[k], r_a[(k + 1) % sides], r_b[0]))
            else:
                bm.faces.new((r_a[k], r_a[(k + 1) % sides], r_b[(k + 1) % sides], r_b[k]))
    return _obj(name, bm, material, ts, smooth=True)


def dome(name, center, axis, radius, height, material, segments=8):
    """A flower's center as a cheap low dome (24 triangles at 8 segments) facing `axis`."""
    ax = Vector(axis).normalized()
    side = _perp(ax)
    up = ax.cross(side)
    c = Vector(center)
    bm = bmesh.new()
    outer = [bm.verts.new(c + (side * math.cos(a) + up * math.sin(a)) * radius)
             for a in (k / segments * math.tau for k in range(segments))]
    inner = [bm.verts.new(c + (side * math.cos(a) + up * math.sin(a)) * radius * 0.6 + ax * height * 0.75)
             for a in (k / segments * math.tau + 0.2 for k in range(segments))]
    apex = bm.verts.new(c + ax * height)
    for k in range(segments):
        n = (k + 1) % segments
        bm.faces.new((outer[k], outer[n], inner[n], inner[k]))
        bm.faces.new((inner[k], inner[n], apex))
    return _obj(name, bm, material, [0.6] * segments + [0.85] * segments + [1.0], smooth=True)


def rays(name, center, axis, count, length, width, material, cup=0.1, droop=0.0, seed=0, jitter=0.15, inner=0.004):
    """A daisy or aster's ring of ray petals, three triangles each (narrow base, widest past the middle, pointed
    tip), all in one object. `cup` lifts them toward `axis`, `droop` bends the outer half back down."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    side = _perp(ax)
    up = ax.cross(side)
    bm = bmesh.new()
    ts = []
    for i in range(count):
        a = (i + rnd.uniform(-jitter, jitter)) / count * math.tau
        out = side * math.cos(a) + up * math.sin(a)
        across = ax.cross(out)
        lift = (cup + rnd.uniform(-0.06, 0.06)) * math.pi * 0.5
        d1 = out * math.cos(lift) + ax * math.sin(lift)
        lift2 = lift - droop * math.pi * 0.5
        d2 = out * math.cos(lift2) + ax * math.sin(lift2)
        n = length * rnd.uniform(0.85, 1.12)
        w = width * rnd.uniform(0.85, 1.15) * 0.5
        b = Vector(center) + out * inner
        m = b + d1 * (n * 0.55)
        tip = m + d2 * (n * 0.45)
        tw = across * (w * 0.35)
        vs = [bm.verts.new(b - tw), bm.verts.new(b + tw), bm.verts.new(m + across * w), bm.verts.new(m - across * w),
              bm.verts.new(tip)]
        bm.faces.new((vs[0], vs[1], vs[2], vs[3]))
        bm.faces.new((vs[3], vs[2], vs[4]))
        ts += [0.0, 0.0, 0.55, 0.55, 1.0]
    return _obj(name, bm, material, ts)


def florets(name, points, count, size, material, seed=0, out=0.6, nod=0.3, one_side=None):
    """Tiny flowers along a stem's polyline (heather bells, sage and mustard florets): `count` little diamonds, two
    triangles each, spiraling round it and pointing out (`out`) and down (`nod`), smaller toward the tip. With
    `one_side` (a direction) most of them turn that way, like heather's one-sided spikes."""
    rnd = random.Random(seed)
    pts = [Vector(p) for p in points]
    seglens = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(seglens) or 1.0
    bm = bmesh.new()
    ts = []
    for i in range(count):
        s = (i + rnd.uniform(0.0, 0.8)) / count
        u = s * total
        k = 0
        while k < len(seglens) - 1 and u > seglens[k]:
            u -= seglens[k]
            k += 1
        d = (pts[k + 1] - pts[k]).normalized()
        at = pts[k] + d * min(u, seglens[k])
        side = _perp(d)
        up = d.cross(side)
        a = i * 2.39996 + rnd.uniform(-0.4, 0.4)
        o = side * math.cos(a) + up * math.sin(a)
        if one_side is not None:
            o = (o + Vector(one_side).normalized() * 0.9).normalized()
        fd = (o * out + d * (1.0 - out) - UP * nod).normalized()
        across = fd.cross(o if abs(fd.dot(o)) < 0.95 else d).normalized()
        across = Matrix.Rotation(rnd.uniform(-0.8, 0.8), 3, fd) @ across
        k_size = size * (1.0 - 0.45 * s) * rnd.uniform(0.85, 1.15)
        c = at + o * (k_size * 0.2)
        v0 = bm.verts.new(c)
        v1 = bm.verts.new(c + fd * (k_size * 0.5) - across * (k_size * 0.42))
        v2 = bm.verts.new(c + fd * k_size)
        v3 = bm.verts.new(c + fd * (k_size * 0.5) + across * (k_size * 0.42))
        bm.faces.new((v0, v1, v2, v3))
        ts += [0.0, 0.6, 1.0, 0.6]
    return _obj(name, bm, material, ts)


def plume(name, top, axis, length, material, lean, seed=0, branches=9, width=0.02):
    """A reed's feathery plume: a panicle of soft branches off the top `length` of a stalk ending at `top`, all
    sweeping over and drooping toward `lean` (a horizontal direction), longest in the middle."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    lv = Vector(lean)
    lv.z = 0.0
    lv.normalize()
    parts = []
    for i in range(branches):
        s = (i + 0.5) / branches
        at = Vector(top) - ax * (length * (1.0 - s) * 0.85)
        reach = length * (0.35 + 0.45 * math.sin(math.pi * (0.25 + s * 0.6))) * rnd.uniform(0.85, 1.1)
        a = rnd.uniform(-0.8, 0.8)
        sideways = Matrix.Rotation(a, 3, UP) @ lv
        d = (ax * 1.0 + sideways * rnd.uniform(0.2, 0.45)).normalized()
        parts.append(leaf("%s%d" % (name, i), at, d, reach, width * rnd.uniform(0.8, 1.2), material,
                          arch=rnd.uniform(0.5, 1.0), power=1.4, segments=3, profile="lance",
                          roll=rnd.uniform(-60, 60), toward=sideways))
    return parts


def round_leaf(name, attach, forward, radius, material, tilt=15.0, cup=0.15, notch=0.7, seed=0, teeth=0.04,
               points=14):
    """A round, heart- or kidney-shaped leaf (marsh marigold, violet) held flat-ish at the top of its stalk:
    `attach` is where the stalk meets it, at the notch; the blade spreads `radius` around a center ahead of it along
    `forward`, tipped up `tilt` degrees at the front, its rim lifted by `cup`. `notch` is how deep the sinus cuts in
    (0 round, 1 down to the stalk)."""
    rnd = random.Random(seed)
    f = Vector(forward)
    f.z = 0.0
    f.normalize()
    s = UP.cross(f).normalized()
    tl = math.radians(tilt)
    fwd = f * math.cos(tl) + UP * math.sin(tl)
    n = s.cross(fwd).normalized()
    if n.z < 0:
        n = -n
    a0 = Vector(attach)
    c = a0 + fwd * (radius * (1.0 - notch * 0.6))
    bm = bmesh.new()
    ts = []
    rim = []
    gap = math.radians(14.0 + notch * 18.0)
    for k in range(points):
        phi = gap + (math.tau - 2 * gap) * k / (points - 1)  # 0 at the notch, behind the center
        r = radius * (1.0 + teeth * math.sin(phi * 9.0 + rnd.uniform(0, 1))) * (1.0 - 0.08 * math.cos(phi))
        p = c + (-fwd * math.cos(phi) + s * math.sin(phi)) * r
        p = p + n * (cup * radius * (0.6 + 0.4 * rnd.random()))
        rim.append(bm.verts.new(p))
        ts.append(1.0)
    mid = [bm.verts.new(c + (v.co - c) * 0.5 - n * (cup * radius * 0.25)) for v in rim]
    ts += [0.6] * len(mid)
    center = bm.verts.new(c - n * (cup * radius * 0.3))
    att = bm.verts.new(a0)
    ts += [0.4, 0.3]
    for k in range(points - 1):
        bm.faces.new((mid[k], mid[k + 1], rim[k + 1], rim[k]))
        bm.faces.new((center, mid[k + 1], mid[k]))
    # Close the notch through the stalk's point
    bm.faces.new((center, mid[0], att))
    bm.faces.new((center, att, mid[-1]))
    return _obj(name, bm, material, ts, smooth=True)


def iris_flower(name, center, axis, size, fall, standard, style, seed=0):
    """A blue flag iris: three falls spreading and turning down (their throats in `fall`'s yellow and white), three
    narrower standards held up between them, three pale style arms lying over the falls' hafts. `size` is the
    fall's length (the flower is about twice that across)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    side = _perp(ax)
    up = ax.cross(side)
    c = Vector(center)
    parts = []
    a0 = rnd.uniform(0, math.tau)
    for i in range(3):
        a = a0 + i * math.tau / 3 + rnd.uniform(-0.12, 0.12)
        out = side * math.cos(a) + up * math.sin(a)
        d = (out * math.cos(math.radians(28)) + ax * math.sin(math.radians(28))).normalized()
        parts.append(leaf("%sFall%d" % (name, i), c, d, size * rnd.uniform(0.92, 1.08), size * 0.7, fall,
                          arch=rnd.uniform(1.15, 1.45), power=1.3, segments=6, profile="fall", toward=out))
        sty = (out * math.cos(math.radians(32)) + ax * math.sin(math.radians(32))).normalized()
        parts.append(leaf("%sStyle%d" % (name, i), c + ax * (size * 0.04), sty, size * 0.5, size * 0.2, style,
                          arch=0.2, power=1.5, segments=3, profile="spoon", toward=out))
        b = a + math.pi / 3
        out2 = side * math.cos(b) + up * math.sin(b)
        d2 = (out2 * math.cos(math.radians(62)) + ax * math.sin(math.radians(62))).normalized()
        parts.append(leaf("%sStd%d" % (name, i), c + ax * (size * 0.03), d2, size * rnd.uniform(0.66, 0.76),
                          size * 0.36, standard, arch=rnd.uniform(0.1, 0.35), power=1.5, segments=4, profile="spoon",
                          toward=out2))
    return parts


# ---------------------------------------------------------------- materials

def throat_petal(name, throat, white, color, tip=None, throat_end=0.2, white_end=0.45, streaks=0.4, sat=1.0,
                 value=0.92, rough=0.5):
    """An iris fall: a `throat` color (yellow) at the base, a veined `white` patch, then `color` out to the tip
    (darkening to `tip`)."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, throat_end * 0.55, throat_end), throat, white)
    col = g.mix(g.ramp(t, white_end * 0.7, white_end), col, color)
    if tip is not None:
        col = g.mix(g.ramp(t, 0.7, 1.0), col, tip)
    col = g.mix(g.math("MULTIPLY", g.noise(30.0), 0.12), col, tuple(c * 0.75 for c in color))
    if streaks > 0.0:
        wave = g.node("ShaderNodeTexWave", wave_type="RINGS", rings_direction="SPHERICAL")
        g._in(wave, "Scale", 160.0)
        g._in(wave, "Distortion", 6.0)
        g.links.new(g.coords(), wave.inputs["Vector"])
        veins = g.math("MULTIPLY", g.ramp(wave.outputs["Fac"], 0.6, 1.0), streaks)
        col = g.mix(veins, col, tuple(c * 0.55 for c in color))
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(90.0), 0.02, 0.001))


# ---------------------------------------------------------------- checks and extra views

def bounds(pieces, label):
    """Prints the clump's extent, to check it against the block's footprint."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in pieces:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    print("[%s] bounds x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f (height %.2f)"
          % (label, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z, hi.z - nk.GROUND))


def view(script, label, model, out_dir, location, target, lens=50, samples=64):
    """One more render of the plant on the preview stage (after naturekit's previews have set it up)."""
    tk.render(tk.camera(script + label, location, target, lens=lens), "%s/%s_%s.png" % (out_dir, script, label),
              samples=samples)


def wide_patch(script, model, out_dir, height=1.6, samples=48):
    """naturekit's patch again from farther back and higher, so a tall plant's tops are in it too."""
    rnd = random.Random(1)
    copies = []
    for i in range(8):
        c = model.copy()
        tk.link(c)
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.7, 1.9)
        c.location = (r * math.cos(a), r * math.sin(a) + 0.6, 0.0)
        c.rotation_euler = (0.0, 0.0, rnd.uniform(0, math.tau))
        s = rnd.uniform(0.8, 1.15)
        c.scale = (s, s, s)
        copies.append(c)
    k = max(1.0, height / 0.8)
    tk.render(tk.camera(script + "patchwide", (0.4 * k, -3.6 * k, 1.4 * k * 0.85), (0.0, 0.6, -0.5 + height * 0.45),
                        lens=35), "%s/%s_patchwide.png" % (out_dir, script), samples=samples)
    for c in copies:
        bpy.data.objects.remove(c)
