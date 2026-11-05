"""Meadow wildflower parts on top of naturekit.py (Lupine, Cornflower, OxeyeDaisy, Paintbrush, BlackEyedSusan,
Coneflower, QueenAnnesLace).

A meadow clump carries 15 to 20 flower heads inside a 3,500 triangle budget, so everything here is cheap: a petal,
floret or bract is a handful of triangles cut from an explicit outline (`sheet`), stems are 3 or 4 sided tubes with no
caps (`stalk`), and flower centers are low fans rather than spheres (`dome`). Every part sets the "t" attribute
naturekit's materials read (0 at its base, 1 at its tip), and `ramp_petal` colors a part along it through any number
of stops.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import kit_lod as kl
import naturekit as nk
import zkit as tk

G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))
GOLDEN = 2.39996


# ---------------------------------------------------------------- materials

def ramp_petal(name, stops, rough=0.55, vary=0.12, sat=1.0, value=0.92, noise=30.0):
    """A petal, bract or flower center colored along each part by `stops`, a list of (t, color) from its base (t 0)
    to its tip (t 1), with a little patchy variation. Full saturation by default: flowers are the color of a drift."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = stops[0][1]
    for (t0, _), (t1, c1) in zip(stops, stops[1:]):
        col = g.mix(g.ramp(t, t0, t1), col, c1)
    darker = tk._multiply_color(g, col, (0.78, 0.78, 0.78))
    col = g.mix(g.math("MULTIPLY", g.noise(noise), vary), col, darker)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(90.0), 0.02, 0.001))


# ---------------------------------------------------------------- geometry

def _obj(name, bm, material, ts, smooth=False):
    if smooth:
        for f in bm.faces:
            f.smooth = True
    obj = tk.mesh_object(name, bm, material)
    nk._set_t(obj, ts)
    return obj


def _perp(v, d):
    """`v` with its part along `d` removed, normalized (None when nothing is left)."""
    p = Vector(v) - d * Vector(v).dot(d)
    return p.normalized() if p.length > 1e-5 else None


def _bridge(bm, a, b):
    """Faces between two rows of vertices (left to right), either of which may be a single point."""
    if len(a) == len(b):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    elif len(a) == 1:
        for j in range(len(b) - 1):
            bm.faces.new((a[0], b[j + 1], b[j]))
    elif len(b) == 1:
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[0]))


def sheet(name, base, direction, length, width, material, rows, bend=0.0, toward=None, twist=0.0, roll=0.0,
          fold=0.0, face=None, teeth=0, tooth=0.12, notch=0.2):
    """A petal, floret, bract or leaf cut from an explicit outline: `rows` is a list of (s, w), s from 0 at the base
    to 1 at the tip and w the width there as a fraction of `width` (0 makes a point). It runs from `base` along
    `direction` for `length`, arching by `bend` (1 turns it a right angle) toward `toward` (default the ground; a
    negative bend curls it the other way), twisting `twist` degrees along its length, rolled `roll` degrees.
    `face` is where its upper surface looks (a head's axis for its petals); `fold` lifts its edges toward that side
    by that fraction of its half width (a V: folded leaves, keels, funnel florets). `teeth` cuts the end of the last
    row into that many points `tooth` (fraction of length) long, the cuts `notch` of the way in (frilled florets,
    notched rays, lobed bracts)."""
    d = Vector(direction).normalized()
    side = None
    if face is not None:
        c = d.cross(Vector(face))
        if c.length > 1e-4:
            side = c.normalized()
    if side is None:
        _, side, _ = nk._frame(d)
    if roll:
        side = Matrix.Rotation(math.radians(roll), 3, d) @ side
    bend_to = _perp(toward if toward is not None else DOWN, d)
    if bend_to is None:
        bend_to, bend = Vector((0.0, 0.0, 0.0)), 0.0
    three = fold != 0.0
    bm = bmesh.new()
    ts = []

    def vert(co, t):
        ts.append(min(1.0, max(0.0, t)))
        return bm.verts.new(co)

    built = []
    center = Vector(base)
    prev = 0.0
    last = None
    for s, w in rows:
        angle = bend * s * s * math.pi * 0.5
        along = (d * math.cos(angle) + bend_to * math.sin(angle)).normalized()
        center = center + along * ((s - prev) * length)
        prev = s
        sv = Matrix.Rotation(math.radians(twist * s), 3, d) @ side
        nv = sv.cross(along)
        nv = nv.normalized() if nv.length > 1e-6 else Vector((0.0, 0.0, 0.0))
        hw = width * 0.5 * w
        if hw < 1e-5:
            row = [vert(center, s)]
        elif three:
            lift = nv * (fold * hw)
            row = [vert(center - sv * hw + lift, s), vert(center, s), vert(center + sv * hw + lift, s)]
        else:
            row = [vert(center - sv * hw, s), vert(center + sv * hw, s)]
        built.append(row)
        last = (s, along, hw)
    for a, b in zip(built, built[1:]):
        _bridge(bm, a, b)
    if teeth and last is not None and last[2] > 1e-5:
        s, along, _ = last
        row = built[-1]
        edge = [v.co.copy() for v in row]

        def across(u):
            if len(edge) == 2:
                return edge[0].lerp(edge[1], u)
            return edge[0].lerp(edge[1], u * 2.0) if u < 0.5 else edge[1].lerp(edge[2], u * 2.0 - 1.0)

        inner = []
        for k in range(1, teeth + 1):
            inner.append(vert(across((k - 0.5) / teeth) + along * (tooth * length), s + tooth))
            if k < teeth:
                inner.append(vert(across(k / teeth) + along * (tooth * length * notch), s + tooth * notch))
        bm.faces.new(row + list(reversed(inner)))
    return _obj(name, bm, material, ts)


def stalk(name, points, radius, material, sides=4, tip=None, radii=None, t_range=(0.0, 1.0)):
    """A stem, twig or spoke: a `sides`-sided tube with no end caps along a polyline, tapering from `radius` to `tip`
    (default 60 %), or through `radii` (one per point; 0 closes it to a point). "t" runs along its length."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + (b - a).length)
    total = cum[-1] if cum[-1] > 1e-6 else 1.0
    if radii is None:
        end = radius * 0.6 if tip is None else tip
        radii = [radius + (end - radius) * (c / total) for c in cum]
    bm = bmesh.new()
    ts = []
    rings = []
    side = None
    for i, p in enumerate(pts):
        tan = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        carried = None if side is None else _perp(side, tan)
        side = nk._frame(tan)[1] if carried is None else carried
        up = tan.cross(side)
        t = t_range[0] + (t_range[1] - t_range[0]) * cum[i] / total
        if radii[i] <= 1e-6:
            rings.append([bm.verts.new(p)])
            ts.append(t)
            continue
        ring = []
        for j in range(sides):
            a = j / sides * math.tau
            ring.append(bm.verts.new(p + (side * math.cos(a) + up * math.sin(a)) * radii[i]))
            ts.append(t)
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        if len(a) == len(b):
            for j in range(sides):
                bm.faces.new((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]))
        elif len(b) == 1:
            for j in range(sides):
                bm.faces.new((a[j], a[(j + 1) % sides], b[0]))
        elif len(a) == 1:
            for j in range(sides):
                bm.faces.new((a[0], b[(j + 1) % sides], b[j]))
    return _obj(name, bm, material, ts, smooth=True)


def dome(name, center, axis, radius, height, material, sides=8, rings=2, jag=0.0, seed=0, t_rim=0.0, t_top=1.0,
         spin=0.0):
    """A flower center, cone or umbellet: a fan-capped dome facing `axis` (`height` 0 a flat disc, negative a dish).
    `jag` > 0 roughens it: every vertex pushed out or in by up to that fraction of the radius, alternately, the out
    ones getting "t" 1 (spine tips, a ragged rim) and the in ones 0.35, so a ramp material colors tips and hollows
    apart."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    bm = bmesh.new()
    ts = []
    rows = []
    for k in range(rings):
        f = k / rings
        ang = f * math.pi * 0.5
        ring = []
        for j in range(sides):
            a = (j + 0.5 * (k % 2)) / sides * math.tau + spin
            out = side * math.cos(a) + up * math.sin(a)
            p = Vector(center) + out * (radius * math.cos(ang)) + ax * (height * math.sin(ang))
            t = t_rim + (t_top - t_rim) * f
            if jag:
                nrm = (out * math.cos(ang) + ax * math.sin(ang)).normalized()
                if (j + k) % 2 == 0:
                    p = p + nrm * (jag * radius * rnd.uniform(0.6, 1.0))
                    t = 1.0
                else:
                    p = p - nrm * (jag * radius * 0.35 * rnd.uniform(0.6, 1.0))
                    t = 0.35
            ring.append(bm.verts.new(p))
            ts.append(t)
        rows.append(ring)
    apex = bm.verts.new(Vector(center) + ax * height)
    ts.append(1.0 if jag else t_top)
    for a, b in zip(rows, rows[1:]):
        for j in range(sides):
            bm.faces.new((a[j], b[j], b[(j + 1) % sides], a[(j + 1) % sides]))
    top = rows[-1]
    for j in range(sides):
        bm.faces.new((top[j], apex, top[(j + 1) % sides]))
    return _obj(name, bm, material, ts, smooth=not jag)


def ray_ring(name, center, axis, count, length, width, material, rows, cup=0.0, droop=0.0, reflex=0.0, offset=0.0,
             seed=0, jitter=0.12, vary=0.1, droop_vary=0.3, teeth=0, tooth=0.1, notch=0.2, fold=0.0, twist=0.0):
    """A ring of `count` ray petals (daisy, susan, coneflower) round `center`, their faces looking along `axis`,
    starting `offset` out from it. `cup` lifts them toward the axis (negative angles them back), `droop` arches the
    tips over: toward the ground, or with `reflex` 1 back behind the head (coneflower petals)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    toward = DOWN * (1.0 - reflex) - ax * reflex
    if toward.length < 1e-4:
        toward = DOWN
    parts = []
    turn = rnd.uniform(0.0, math.tau)
    for i in range(count):
        a = (i + rnd.uniform(-jitter, jitter)) / count * math.tau + turn
        out = side * math.cos(a) + up * math.sin(a)
        lift = (cup + rnd.uniform(-0.06, 0.06)) * math.pi * 0.5
        dv = out * math.cos(lift) + ax * math.sin(lift)
        parts.append(sheet("%s%d" % (name, i), Vector(center) + out * offset, dv,
                           length * rnd.uniform(1.0 - vary, 1.0 + vary), width * rnd.uniform(0.9, 1.1), material,
                           rows, bend=droop * rnd.uniform(1.0 - droop_vary, 1.0 + droop_vary), toward=toward,
                           twist=rnd.uniform(-twist, twist), fold=fold, face=ax, teeth=teeth, tooth=tooth,
                           notch=notch))
    return parts


def pea_spike(name, base, axis, height, wing_mat, banner_mat, bud_mat, count=52, radius=0.03, size=0.016,
              open_to=0.72, seed=0):
    """A lupine spike: `count` pea flowers spiraling up `height` from `base`, a cone `radius` wide at the bottom,
    `size` long at the bottom and smaller up it. Each open flower is an upright banner (looking outward, pale at its
    base) over a keel folded like a boat pointing out; above `open_to` they're closed buds pressed upward."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    parts = []
    for i in range(count):
        s = i / max(1, count - 1)
        a = i * GOLDEN + rnd.uniform(-0.25, 0.25)
        out = side * math.cos(a) + up * math.sin(a)
        taper = (1.0 - s) ** 0.7
        r = radius * (0.2 + 0.8 * taper)
        at = Vector(base) + ax * (height * s) + out * (r * 0.55)
        k = size * (0.5 + 0.5 * taper) * rnd.uniform(0.9, 1.1)
        if s > open_to:
            d = (ax * 0.9 + out * 0.4).normalized()
            parts.append(sheet("%sB%d" % (name, i), at - out * (r * 0.3), d, k * 1.0, k * 0.6, bud_mat,
                               [(0.0, 0.35), (0.5, 1.0), (1.0, 0.0)], face=out))
            continue
        # The keel: a flat diamond pointing out, tipped up, turned a little about itself
        keel = (out + ax * rnd.uniform(0.2, 0.5)).normalized()
        parts.append(sheet("%sK%d" % (name, i), at, keel, k * 1.0, k * 0.75, wing_mat,
                           [(0.0, 0.0), (0.4, 1.0), (1.0, 0.0)], face=ax, roll=rnd.uniform(-25, 25)))
        # The banner: standing up behind it, looking out, its top curled back
        flag = (ax * 0.8 + out * 0.6).normalized()
        parts.append(sheet("%sS%d" % (name, i), at + ax * (k * 0.1) - out * (k * 0.1), flag, k * 1.0, k * 1.15,
                           banner_mat, [(0.0, 0.3), (0.45, 1.0), (1.0, 0.75)], bend=0.3, toward=-out, face=out))
    return parts


def palmate(name, base, direction, petiole, material, stalk_mat, fingers=8, finger_len=0.08, finger_w=0.014,
            droop=0.3, seed=0):
    """A lupine-style palmate leaf: a petiole `petiole` long from `base` toward `direction`, rising a little, ending in
    `fingers` narrow leaflets spread like the spokes of an umbrella, their tips drooping."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    p0 = Vector(base)
    p2 = p0 + d * petiole
    mid = p0.lerp(p2, 0.5) + UP * (petiole * 0.12)
    parts = [stalk(name + "P", [p0, mid, p2], 0.0022, stalk_mat, sides=3, tip=0.0012)]
    face = (UP + Vector((d.x, d.y, 0.0)) * 0.25).normalized()
    _, side, up = nk._frame(face)
    turn = rnd.uniform(0.0, math.tau)
    for j in range(fingers):
        a = (j + rnd.uniform(-0.15, 0.15)) / fingers * math.tau + turn
        out = side * math.cos(a) + up * math.sin(a)
        fd = (out + face * 0.3).normalized()
        parts.append(sheet("%sF%d" % (name, j), p2, fd, finger_len * rnd.uniform(0.8, 1.1), finger_w, material,
                           [(0.0, 0.2), (0.45, 1.0), (1.0, 0.0)], bend=droop * rnd.uniform(0.7, 1.3), face=face,
                           twist=rnd.uniform(-20, 20)))
    return parts


def pinnate(name, base, direction, length, material, stalk_mat, pairs=7, leaflet=0.035, width=0.016, droop=0.35,
            teeth=3, seed=0):
    """A feathery (carrot-like) leaf: a rachis `length` long from `base` toward `direction`, arching down, with
    `pairs` pairs of leaflets, each cut into `teeth` deep lobes, shrinking toward the tip."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    flat = Vector((d.x, d.y, 0.0)).normalized() if Vector((d.x, d.y, 0.0)).length > 1e-4 else Vector((1.0, 0.0, 0.0))
    pts = []
    for i in range(4):
        s = i / 3
        ang = droop * s * s * math.pi * 0.5
        pts.append(Vector(base) + (d * (length * s)) + DOWN * (math.sin(ang) * length * s * 0.6))
    parts = [stalk(name + "R", pts, 0.0016, stalk_mat, sides=3, tip=0.0008)]
    right = flat.cross(UP).normalized()
    for k in range(pairs):
        s = 0.18 + 0.8 * k / max(1, pairs - 1)
        seg = min(2, int(s * 3))
        at = pts[seg].lerp(pts[seg + 1], s * 3 - seg)
        fwd = (pts[seg + 1] - pts[seg]).normalized()
        size = leaflet * (1.1 - 0.6 * s) * rnd.uniform(0.85, 1.1)
        for sgn in (-1.0, 1.0):
            ld = (right * sgn + fwd * 0.75 + UP * 0.15).normalized()
            parts.append(sheet("%sL%d_%d" % (name, k, int(sgn > 0)), at, ld, size, width * (1.1 - 0.5 * s), material,
                               [(0.0, 0.35)], face=UP, teeth=teeth, tooth=1.0, notch=0.35, bend=0.2,
                               twist=rnd.uniform(-25, 25)))
    return parts


def lace_umbel(name, top, axis, radius, flower_mat, spoke_mat, spokes=15, lift=0.4, size=0.3, dome_h=0.06, nest=0.0,
               seed=0, eye_mat=None, jag=0.25, far_scale=None):
    """A compound umbel (Queen Anne's lace): `spokes` rays from `top` fanning up and out to a flat plate `radius`
    across of ragged little umbellets (each a jagged fan `size` of the radius), spread evenly over the plate, the rays
    showing beneath. `nest` 0..1 curls the rays up and in, into a bird's nest seed head. `eye_mat` adds the single dark
    floret at the center. `far_scale` tags it for kit_lod: the far mesh keeps only the umbellets, each grown by that
    much about its own center."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    parts = []
    turn = rnd.uniform(0.0, math.tau)
    u = radius * size
    reach = radius - u * 0.6
    for i in range(spokes):
        f = math.sqrt((i + 0.6) / spokes)
        a = i * GOLDEN + turn + rnd.uniform(-0.15, 0.15)
        out = side * math.cos(a) + up * math.sin(a)
        r = reach * f * rnd.uniform(0.92, 1.05)
        h = radius * (lift + dome_h * (1.0 - f * f)) * rnd.uniform(0.95, 1.05)
        tilt = ax
        if nest:
            r *= 1.0 - 0.45 * nest
            h += nest * radius * 0.7 * f
            tilt = (ax - out * nest * 0.9 * f).normalized()
        end = Vector(top) + out * r + ax * h
        if nest:
            bow = Vector(top) + out * (r * 1.25) + ax * (h * 0.45)
            ray = [Vector(top), bow, end]
        else:
            ray = [Vector(top), end]
        spoke = stalk("%sS%d" % (name, i), ray, 0.0009, spoke_mat, sides=3, tip=0.0006)
        cluster = dome("%sU%d" % (name, i), end, tilt, u * rnd.uniform(0.85, 1.1), u * 0.3, flower_mat, sides=8,
                       rings=1, jag=jag, seed=seed * 31 + i, spin=rnd.uniform(0, math.tau))
        if far_scale is not None:
            kl.tag([spoke], kl.NEAR)
            kl.tag([cluster], kl.BOTH, scale=far_scale, pivot=end)
        parts += [spoke, cluster]
    if eye_mat is not None and not nest:
        eye = dome(name + "Eye", Vector(top) + ax * (radius * (lift + dome_h) + u * 0.3), ax, 0.0035, 0.002, eye_mat,
                   sides=5, rings=1)
        if far_scale is not None:
            kl.tag([eye], kl.NEAR)
        parts.append(eye)
    return parts


def curve(p0, p1, bow=(0.0, 0.0, 0.0), segments=3, wobble=0.0, rnd=None):
    """Points along a gentle arc from `p0` to `p1`, bowed by `bow` at its middle (a quadratic curve), the inner points
    nudged sideways by up to `wobble`."""
    p0, p1 = Vector(p0), Vector(p1)
    c = (p0 + p1) * 0.5 + Vector(bow)
    pts = []
    for i in range(segments + 1):
        s = i / segments
        p = p0 * ((1 - s) ** 2) + c * (2 * s * (1 - s)) + p1 * (s * s)
        if 0 < i < segments and wobble and rnd is not None:
            p = p + Vector((rnd.uniform(-wobble, wobble), rnd.uniform(-wobble, wobble), 0.0))
        pts.append(p)
    return pts


def inside(p, limit):
    """`p` pulled in toward the block's vertical axis so it's no more than `limit` from it (keeps branch tips, and
    the heads on them, inside the footprint)."""
    p = Vector(p)
    flat = Vector((p.x, p.y, 0.0))
    if flat.length > limit:
        flat = flat.normalized() * limit
        p.x, p.y = flat.x, flat.y
    return p


def facing(lean, up_bias=1.0):
    """A head's axis: up, tipped toward `lean` (x, y)."""
    return (Vector((lean[0], lean[1], 0.0)) + UP * up_bias).normalized()


def report(script, groups):
    """Prints each group's triangle count (before the export triangulates), to keep a clump in budget."""
    total = 0
    lo, hi = [1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]
    for key, objs in groups.items():
        n = sum(nk._triangles(o) for o in objs)
        total += n
        print("[%s] %-8s %4d parts %5d triangles" % (script, key, len(objs), n))
        for o in objs:
            for v in o.data.vertices:
                co = o.matrix_world @ v.co
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], co[i]), max(hi[i], co[i])
    print("[%s] parts total %d triangles" % (script, total))
    print("[%s] bounds x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (triangles check)" %
          (script, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
