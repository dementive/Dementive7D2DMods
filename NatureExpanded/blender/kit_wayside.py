"""Helpers for the wayside batch (RedClover, Bergamot, Chicory, Thistle, WildMustard, CurlyDock, Fireweed), on top of
naturekit.py. Plants with hundreds of small parts (clover heads, mustard flowers, dock seeds) are built into a few
`Sheet`s, one per material, instead of an object per part: each sheet is one mesh with the kit's "t" attribute (0 at a
part's base, 1 at its tip) and a "u" attribute across leaves (-1 at one edge, 0 on the midrib, 1 at the other), so
`leaf_mat` can draw a midrib, a clover chevron or a red base.

    sh = Sheet("Petals", material)
    ww.leaf(sh, base, direction, 0.03, 0.01, profile="oval")
    pieces.append(sh.build())
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import naturekit as nk
import zkit as tk

DOWN = Vector((0.0, 0.0, -1.0))


# ---------------------------------------------------------------- materials

def leaf_mat(name, color, color2=None, base=None, base_to=0.45, rib=None, chevron=None, rough=0.65, vary=0.25,
             scale=14.0, sat=0.85, value=0.85):
    """`nk.plant` with marks: `base` a color creeping up from each leaf's base to `base_to` (dock's red), `rib` a
    midrib color, `chevron` a pale V across the leaf (clover). The rib and chevron need the "u" that `leaf` writes
    (with or without `rib`)."""
    mat, g = tk.new_material(name)
    c2 = color2 or tuple(c * 0.65 for c in color)
    t = nk._attr(g, "t")
    au = g.math("ABSOLUTE", nk._attr(g, "u"))
    col = g.mix(g.ramp(g.noise(scale, detail=3.0), 0.5 - vary, 0.5 + vary), color, c2)
    col = g.mix(g.ramp(t, 0.0, 0.6), tuple(c * 0.7 for c in color), col)
    if chevron is not None:
        # A V with its point on the midrib a third of the way up, its arms reaching the edges near the tip
        line = g.math("ABSOLUTE", g.math("SUBTRACT", t, g.math("ADD", g.math("MULTIPLY", au, 0.4), 0.32)))
        col = g.mix(g.math("SUBTRACT", 1.0, g.ramp(line, 0.05, 0.13), clamp=True), col, chevron)
    if rib is not None:
        col = g.mix(g.math("SUBTRACT", 1.0, g.ramp(au, 0.05, 0.16), clamp=True), col, rib)
    if base is not None:
        col = g.mix(g.math("SUBTRACT", 1.0, g.ramp(t, base_to * 0.3, base_to), clamp=True), col, base)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(70.0), 0.04, 0.002))


# ---------------------------------------------------------------- sheets

class Sheet:
    """Many small parts of one material gathered into one mesh."""

    def __init__(self, name, material):
        self.name, self.material = name, material
        self.bm = bmesh.new()
        self.t, self.u = [], []

    def v(self, co, t=0.0, u=0.0):
        self.t.append(t)
        self.u.append(u)
        return self.bm.verts.new(Vector(co))

    def f(self, *verts):
        if len(set(verts)) == len(verts):
            self.bm.faces.new(verts)

    def build(self):
        """The finished object (None if nothing was added)."""
        if not self.bm.faces:
            self.bm.free()
            return None
        # Closed parts (heads, buds, bulbs) must face out: the occlusion bake reads a ball facing in as black
        bmesh.ops.recalc_face_normals(self.bm, faces=list(self.bm.faces))
        obj = tk.mesh_object(self.name, self.bm, self.material)
        for key, values in (("t", self.t), ("u", self.u)):
            attr = obj.data.attributes.new(key, "FLOAT", "POINT")
            attr.data.foreach_set("value", values)
        return obj


def build(sheets):
    return [o for o in (s.build() for s in sheets) if o is not None]


# ---------------------------------------------------------------- parts

def _profile(kind, s):
    if kind == "lance":
        return max(0.0, (1.0 - s) ** 0.8 * min(1.0, s * 3.0 + 0.15))
    if kind == "oval":
        return math.sin(math.pi * s) ** 0.7
    if kind == "strap":
        return 1.0 if s < 0.85 else (1.0 - s) / 0.15
    if kind == "spoon":
        return min(1.0, 0.25 + s * 1.2) * (math.sin(math.pi * min(s, 0.999)) ** 0.25 if s > 0.6 else 1.0)
    if kind == "heart":
        return (1.0 - s) ** 0.6
    if kind == "square":
        # Narrow at the base, widening to a square tip (chicory's rays)
        return min(1.0, 0.3 + 0.7 * s / 0.6)
    if kind == "obovate":
        # Widest past the middle, round tip
        return math.sin(math.pi * s ** 1.5) ** 0.6
    if kind == "taper":
        return 1.0 - 0.7 * s
    if kind == "needle":
        return 1.0 - s
    if kind == "willow":
        # Long and narrow, widest a third of the way, tapering to a long point
        return max(0.0, math.sin(math.pi * s ** 0.75) ** 0.8)
    return 1.0


def leaf(sh, base, direction, length, width, profile="lance", segments=4, bend=0.25, twist=0.0, roll=0.0, fold=0.0,
         rib=True, wave=0.0, waves=3.0, lobes=0, lobe_depth=0.5, hook=0.0, notch=0.0, t_range=(0.0, 1.0), seed=0):
    """A leaf, petal, bract or floret as a single sheet, like `nk.blade` (same profiles and more: "square", "obovate",
    "taper", "needle", "willow", "linear"), into the sheet `sh`. `rib` gives each row a midrib vertex (so it can
    `fold` up into a V); `wave` ruffles the edges up and down by that many meters (`waves` times along
    the leaf, curly dock); `lobes` cuts that many lobes down each side, `lobe_depth` deep, their points pushed
    forward by `hook` (negative points them back, like a dandelion's); `notch` pulls the tip's middle back (a
    fraction of the length). Returns the lobe points [(position, outward)] for spines.

    `bend` arches the way `nk.blade` does, but each step is normalized, so the leaf keeps its full length. A blade
    that starts near upright still doesn't arch smoothly: it stays up, then folds straight back down once the turn
    passes 45 degrees (`bend` 0.5), so keep `bend` under 0.5 on those (this batch's upright parts use 0.45 at
    most)."""
    rnd = random.Random(seed)
    d, side0, _ = nk._frame(direction)
    if roll:
        side0 = Matrix.Rotation(math.radians(roll), 3, d) @ side0
    n = max(segments, 2 * lobes + 1) if lobes else segments
    step = length / n
    phases = (rnd.uniform(0.0, math.tau), rnd.uniform(0.0, math.tau))
    center = Vector(base)
    rows, tips = [], []
    for i in range(n + 1):
        s = i / n
        angle = bend * s * s * math.pi * 0.5
        along = (d * math.cos(angle) + DOWN * math.sin(angle)).normalized()
        if i:
            center = center + along * step
        sv = Matrix.Rotation(math.radians(twist * s), 3, d) @ side0
        uv = sv.cross(along).normalized()
        w = _profile(profile, s) * width * 0.5
        fwd = 0.0
        lobe = False
        if lobes and 0 < i < n:
            if i % 2:
                fwd, lobe = hook * step, True
            else:
                w *= 1.0 - lobe_depth
        t = t_range[0] + (t_range[1] - t_range[0]) * s
        if w < 1e-5:
            rows.append((sh.v(center, t, 0.0),))
            continue
        ends = []
        for k, sgn in enumerate((-1.0, 1.0)):
            lift = fold * w
            if wave:
                lift += wave * min(1.0, s * 4.0) * math.sin(math.tau * waves * s + phases[k])
            p = center + sv * (sgn * w) + uv * lift + along * fwd
            ends.append(sh.v(p, t, sgn))
            if lobe:
                tips.append((p, (sv * sgn + along * 0.5).normalized()))
        if rib:
            mid = center - along * (notch * length if i == n else 0.0)
            rows.append((ends[0], sh.v(mid, t, 0.0), ends[1]))
        else:
            rows.append((ends[0], ends[1]))
    for a, b in zip(rows, rows[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for k in range(len(b) - 1):
                sh.f(a[0], b[k], b[k + 1])
        elif len(b) == 1:
            for k in range(len(a) - 1):
                sh.f(a[k], a[k + 1], b[0])
        else:
            for k in range(len(a) - 1):
                sh.f(a[k], a[k + 1], b[k + 1], b[k])
    return tips


def needle(sh, base, direction, length, width, seed=0, t_range=(0.0, 1.0)):
    """A spine or bristle: one thin triangle."""
    rnd = random.Random(seed)
    d, side, up = nk._frame(direction)
    a = rnd.uniform(0.0, math.pi)
    sv = side * math.cos(a) + up * math.sin(a)
    b = Vector(base)
    sh.f(sh.v(b - sv * width * 0.5, t_range[0], -1.0), sh.v(b + sv * width * 0.5, t_range[0], 1.0),
         sh.v(b + d * length, t_range[1], 0.0))


def ring(sh, center, axis, count, length, width, cup=0.3, droop=0.0, seed=0, jitter=0.12, start=None,
         profile="spoon", segments=2, rib=False, spread=0.05, **kw):
    """A ring of petals round `center` facing along `axis` (like `nk.petal_ring`, into a sheet, cheaper)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    a0 = rnd.uniform(0.0, math.tau) if start is None else start
    for i in range(count):
        a = a0 + (i + rnd.uniform(-jitter, jitter)) / count * math.tau
        out = side * math.cos(a) + up * math.sin(a)
        lift = (cup + rnd.uniform(-spread, spread)) * math.pi * 0.5
        direction = (out * math.cos(lift) + ax * math.sin(lift)).normalized()
        leaf(sh, Vector(center), direction, length * rnd.uniform(0.9, 1.1), width, profile=profile, segments=segments,
             bend=droop, rib=rib, seed=seed * 31 + i, **kw)


def stalk(sh, points, r0, r1=None, sides=3, t_range=(0.0, 1.0)):
    """A stem as an open prism along a polyline (3 sides by default, 4 for a square stem), tapering from `r0` to
    `r1`: half the triangles of `nk.stem` for a stem too thin to see the difference."""
    pts = [Vector(p) for p in points]
    r1 = r0 * 0.6 if r1 is None else r1
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1] or 1.0
    rings = []
    ref = None
    for i, p in enumerate(pts):
        tan = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if ref is None:
            ref = tan.cross(Vector((1.0, 0.0, 0.0)) if abs(tan.x) < 0.9 else Vector((0.0, 1.0, 0.0))).normalized()
        else:
            # Carry the frame along the stem so it doesn't twist
            ref = (ref - tan * ref.dot(tan)).normalized()
        other = tan.cross(ref).normalized()
        f = acc[i] / total
        r = r0 + (r1 - r0) * f
        t = t_range[0] + (t_range[1] - t_range[0]) * f
        rings.append([sh.v(p + (ref * math.cos(k / sides * math.tau) + other * math.sin(k / sides * math.tau)) * r, t)
                      for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            sh.f(a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k])


def ball(sh, center, axis, radius, length=None, segs=6, rings=2, t_range=(0.0, 1.0), seed=0, rough=0.0):
    """A closed ellipsoid round `center`, `length` along `axis` (2 x radius if not given), `radius` across: a bud,
    a flower head's core, a thistle bulb. `rough` jitters the vertices by that fraction of the radius."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    length = 2.0 * radius if length is None else length
    c = Vector(center)
    a0 = rnd.uniform(0.0, math.tau)
    bottom = sh.v(c - ax * length * 0.5, t_range[0])
    top = sh.v(c + ax * length * 0.5, t_range[1])
    rows = []
    for j in range(1, rings + 1):
        phi = math.pi * j / (rings + 1)
        z = -math.cos(phi) * length * 0.5
        r = math.sin(phi) * radius
        t = t_range[0] + (t_range[1] - t_range[0]) * j / (rings + 1)
        row = []
        for k in range(segs):
            a = a0 + (k + 0.5 * (j % 2)) / segs * math.tau
            jit = 1.0 + rnd.uniform(-rough, rough)
            row.append(sh.v(c + ax * z + (side * math.cos(a) + up * math.sin(a)) * r * jit, t))
        rows.append(row)
    for k in range(segs):
        sh.f(bottom, rows[0][(k + 1) % segs], rows[0][k])
        sh.f(top, rows[-1][k], rows[-1][(k + 1) % segs])
    for a, b in zip(rows, rows[1:]):
        for k in range(segs):
            sh.f(a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k])


def bud(sh, base, axis, length, radius, seed=0, t_range=(0.0, 1.0)):
    """A closed bud standing on `base`: a pointed spindle of 8 triangles."""
    ax = Vector(axis).normalized()
    ball(sh, Vector(base) + ax * length * 0.5, ax, radius, length, segs=4, rings=1, t_range=t_range, seed=seed)


def dome(sh, center, axis, radius, height, segs=6, t_range=(0.0, 1.0), seed=0):
    """A low open cone (a flower's center): a fan of `segs` triangles."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    c = Vector(center)
    a0 = rnd.uniform(0.0, math.tau)
    tip = sh.v(c + ax * height, t_range[1])
    rim = [sh.v(c + (side * math.cos(a0 + k / segs * math.tau) + up * math.sin(a0 + k / segs * math.tau)) * radius,
                t_range[0]) for k in range(segs)]
    for k in range(segs):
        sh.f(tip, rim[k], rim[(k + 1) % segs])


def sphere_dirs(axis, count, cutoff=-1.0, seed=0, jitter=0.15):
    """`count` directions spread evenly over the part of a sphere at least `cutoff` up `axis` (-1 all of it, 0 the
    upper half), jittered a little."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = nk._frame(ax)
    total = max(count, int(round(count * 2.0 / max(0.05, 1.0 - cutoff))))
    out = []
    a0 = rnd.uniform(0.0, math.tau)
    for i in range(total):
        z = 1.0 - 2.0 * (i + 0.5) / total
        if z < cutoff:
            continue
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = a0 + i * 2.39996
        v = side * (r * math.cos(a)) + up * (r * math.sin(a)) + ax * z
        v += Vector((rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter)))
        out.append(v.normalized())
    return out[:count]


def pompom(sh, center, axis, core, count, length, width, core_sheet=None, cutoff=-0.4, profile="needle", segments=1,
           bend=0.0, seed=0, lean_up=0.0, t_range=(0.4, 1.0), core_length=None):
    """A round head of florets (clover, bergamot, a thistle's down): an ellipsoid core of radius `core` in
    `core_sheet` (none if not given) with `count` florets `length` long radiating from it over the part of it at least
    `cutoff` up `axis`, tipped up by `lean_up`."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    c = Vector(center)
    cl = core * 2.0 if core_length is None else core_length
    if core_sheet is not None:
        ball(core_sheet, c, ax, core, cl, segs=6, rings=2, t_range=(t_range[0] * 0.8, t_range[1]), seed=seed)
    for i, n in enumerate(sphere_dirs(ax, count, cutoff, seed=seed)):
        z = n.dot(ax)
        at = c + (n - ax * z) * core * 0.85 + ax * z * cl * 0.5 * 0.85
        direction = (n + ax * lean_up).normalized()
        leaf(sh, at, direction, length * rnd.uniform(0.8, 1.15), width * rnd.uniform(0.85, 1.15), profile=profile,
             segments=segments, bend=bend, rib=False, roll=rnd.uniform(-90.0, 90.0), t_range=t_range,
             seed=seed * 53 + i)


def path(start, direction, length, count, bend=0.0, wobble=0.0, seed=0):
    """Points along a gently curving stem: from `start` along `direction`, curving toward the ground by `bend` (or
    up by a negative one), with a little random wobble."""
    rnd = random.Random(seed)
    d = Vector(direction).normalized()
    p = Vector(start)
    pts = [p.copy()]
    step = length / count
    for i in range(1, count + 1):
        s = i / count
        angle = bend * s * math.pi * 0.5
        along = (d * math.cos(angle) + DOWN * math.sin(angle)).normalized() if bend >= 0 else \
            (d * math.cos(-angle) + Vector((0, 0, 1)) * math.sin(-angle)).normalized()
        along += Vector((rnd.uniform(-wobble, wobble), rnd.uniform(-wobble, wobble), 0.0))
        p = p + along.normalized() * step
        pts.append(p.copy())
    return pts


def along(points, s):
    """The point and direction a fraction `s` of the way along a polyline."""
    pts = [Vector(p) for p in points]
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    goal = s * acc[-1]
    for i in range(len(pts) - 1):
        if acc[i + 1] >= goal or i == len(pts) - 2:
            seg = acc[i + 1] - acc[i] or 1.0
            f = min(1.0, max(0.0, (goal - acc[i]) / seg))
            return pts[i].lerp(pts[i + 1], f), (pts[i + 1] - pts[i]).normalized()
    return pts[-1], (pts[-1] - pts[-2]).normalized()


def perpendicular(direction, angle):
    """A unit vector at right angles to `direction`, turned `angle` radians about it."""
    d, side, up = nk._frame(direction)
    return (side * math.cos(angle) + up * math.sin(angle)).normalized()
