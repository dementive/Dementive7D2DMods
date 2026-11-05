"""Forest-floor parts for Nature Expanded's woodland plants (fern, fly agaric, bolete, trillium, wild strawberry,
foxglove, morels, snowdrop), on top of naturekit.py and zkit.py: shaped leaves and petals with a midrib, tapered
stems, surfaces of revolution (mushroom caps and stems, berries, bells), fern fronds and fiddleheads, warts and gills,
leaf litter, pine needles, moss and ash, and the materials they need. The materials of things seen up close (moss,
mushroom caps and stems, morels, ash) carry detail down to a few millimeters and real relief: `moss_layer` (moss
signals to mix into any material, as the mossy log does), `bolete_cap`, `agaric_cap`, `honeycomb`, `reticulate`,
built from `_cells`, `_ridged`, `_warped` and `_polar` (coordinates round a cap made with revolve(polar=True)).

Same conventions as naturekit: meters, Z up, the ground at nk.GROUND, and a float attribute "t" on every vertex (0 at
a part's base, 1 at its tip) for the materials to shade along. Every helper returns mesh objects for nk.export.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

import naturekit as nk
import zkit as tk

TAU = math.tau
Z = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------- frames and meshes

def basis(axis):
    """The unit axis and two unit vectors across it: `side` (horizontal when it can be) and `up` (toward +Z). In a
    revolve, angle a = -pi/2 faces the ground."""
    ax = Vector(axis).normalized()
    ref = Z if abs(ax.z) < 0.95 else Vector((1.0, 0.0, 0.0))
    side = ax.cross(ref).normalized()
    up = side.cross(ax).normalized()
    return ax, side, up


def _face(bm, verts, want):
    f = bm.faces.new(verts)
    f.normal_update()
    if f.normal.dot(want) < 0.0:
        f.normal_flip()
    return f


def finish(name, bm, material, ts, smooth=None):
    obj = tk.mesh_object(name, bm, material)
    nk._set_t(obj, ts)
    if smooth:
        tk.smooth(obj, smooth)
    return obj


def _rings_faces(bm, rings, segments):
    """Faces between consecutive rings (a ring of one vertex is a pole), wound consistently. Returns (face, ring
    index) pairs."""
    out = []
    k = segments
    for i, (A, B) in enumerate(zip(rings, rings[1:])):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            out += [(bm.faces.new((A[0], B[(j + 1) % k], B[j])), i) for j in range(k)]
        elif len(B) == 1:
            out += [(bm.faces.new((A[j], A[(j + 1) % k], B[0])), i) for j in range(k)]
        else:
            out += [(bm.faces.new((A[j], A[(j + 1) % k], B[(j + 1) % k], B[j])), i) for j in range(k)]
    return out


def _orient(bm, faces, ref_of):
    """Flips the whole surface if most of it (by area) faces toward ref_of(face, ring index)."""
    bm.normal_update()
    vote = 0.0
    for f, i in faces:
        c = f.calc_center_median()
        vote += f.normal.dot(c - ref_of(c, i)) * f.calc_area()
    if vote < 0.0:
        for f, _ in faces:
            f.normal_flip()


def revolve(name, profile, center, axis, material, segments=12, t=None, wobble=None, phase=0.0, away=None,
            smooth=75.0, polar=False):
    """A surface of revolution about `axis` through `center`: `profile` is a list of (r, h), a radius out from the
    axis and a height along it; a point with r = 0 closes the surface there. `t` gives each profile point's "t"
    (default 0 to 1 along it). `wobble(i, a)` returns (radius factor, height offset) for profile point i at angle a
    (lumps, wavy rims, lips; a = -pi/2 faces the ground). Faces turn away from the point `away` (default: outward
    from the axis). `polar` also gives each vertex its angle round the axis as two float attributes, "ca" and "sa"
    (its cosine and sine, 0 on the axis), for materials that run round a cap (radial fibrils, a striate rim)."""
    ax, s, u = basis(axis)
    c = Vector(center)
    bm = bmesh.new()
    rings, ts, cs, ss = [], [], [], []
    n = len(profile)
    for i, (r, h) in enumerate(profile):
        tt = t[i] if t is not None else i / max(1, n - 1)
        if r <= 1e-6:
            dh = wobble(i, 0.0)[1] if wobble else 0.0
            rings.append([bm.verts.new(c + ax * (h + dh))])
            ts.append(tt)
            cs.append(0.0)
            ss.append(0.0)
            continue
        ring = []
        for j in range(segments):
            a = phase + j / segments * TAU
            m, dh = wobble(i, a) if wobble else (1.0, 0.0)
            ring.append(bm.verts.new(c + ax * (h + dh) + (s * math.cos(a) + u * math.sin(a)) * (r * m)))
            ts.append(tt)
            cs.append(math.cos(a))
            ss.append(math.sin(a))
        rings.append(ring)
    faces = _rings_faces(bm, rings, segments)
    if away is not None:
        ref = Vector(away)
        _orient(bm, faces, lambda p, i: ref)
    else:
        _orient(bm, faces, lambda p, i: c + ax * (p - c).dot(ax))
    obj = finish(name, bm, material, ts, smooth)
    if polar:
        for key, values in (("ca", cs), ("sa", ss)):
            attr = obj.data.attributes.new(key, "FLOAT", "POINT")
            attr.data.foreach_set("value", values)
    return obj


def taper_tube(name, points, radii, material, sides=5, t=None, smooth=80.0):
    """A tube along a polyline, its radius going through `radii` (one per point, or a (start, end) pair); a radius of
    0 at an end closes it to a point. "t" runs 0 to 1 along it (or per point from `t`). Cheaper than nk.stem for thin
    stalks: `sides` 4 or 5 is plenty under smooth shading."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    if len(radii) != n:
        r0, r1 = radii
        radii = [r0 + (r1 - r0) * i / (n - 1) for i in range(n)]
    tans = [(pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]).normalized() for i in range(n)]
    _, nrm, _ = basis(tans[0])
    bm = bmesh.new()
    rings, ts = [], []
    for i in range(n):
        T = tans[i]
        nrm = (nrm - T * nrm.dot(T)).normalized()
        bi = T.cross(nrm)
        tt = t[i] if t is not None else i / (n - 1)
        if radii[i] <= 1e-6:
            rings.append([bm.verts.new(pts[i])])
            ts.append(tt)
            continue
        ring = []
        for j in range(sides):
            a = j / sides * TAU
            ring.append(bm.verts.new(pts[i] + (nrm * math.cos(a) + bi * math.sin(a)) * radii[i]))
            ts.append(tt)
        rings.append(ring)
    faces = _rings_faces(bm, rings, sides)
    _orient(bm, faces, lambda p, i: (pts[i] + pts[i + 1]) * 0.5)
    return finish(name, bm, material, ts, smooth)


# ---------------------------------------------------------------- leaves, petals, fronds

def _beta(a, b):
    m = a / (a + b)
    peak = m ** a * (1.0 - m) ** b
    return lambda s: (max(s, 0.0) ** a * max(1.0 - s, 0.0) ** b) / peak


PROFILES = {
    "lance": lambda s: max(0.0, (1.0 - s) ** 0.8 * min(1.0, s * 3.0 + 0.15)),
    "ovate": _beta(0.5, 0.75),       # widest 40% up, pointed tip (trillium leaves, sepals)
    "obovate": _beta(0.9, 0.45),     # widest two thirds up, round tip (petals, strawberry leaflets)
    "elliptic": _beta(0.7, 0.7),
    "round": _beta(0.45, 0.4),       # nearly round (strawberry petals)
    "linear": _beta(0.12, 0.3),      # long and even, pointed
    "strap": lambda s: 1.0 if s < 0.8 else max(0.0, 1.0 - ((s - 0.8) / 0.2) ** 1.5),
}


def leaf(name, base, direction, length, width, material, profile="ovate", segments=5, bend=0.2, fold=0.0,
         wave=0.0, waves=2.0, twist=0.0, side=None, teeth=0.0, cols=3, t=(0.0, 1.0), seed=0, smooth=60.0):
    """A leaf, leaflet, petal, sepal or bract: a single sheet from `base` along `direction`, `length` long and
    `width` wide at its widest (a PROFILES name or a function of 0..1), arching toward the ground by `bend` (0
    straight, 1 bent right over; negative curls it up). `fold` lifts the edges along the leaf's normal (a V along the
    midrib; negative bows it the other way), `wave` ripples the margins, `teeth` (0 to 1) notches every other row of
    the margin (toothed leaves; give it enough segments). `cols` 3 keeps a midrib row of vertices (needed for fold);
    2 drops it (cheapest). `side` sets which way is across the leaf (default horizontal); its normal is
    side x direction."""
    prof = PROFILES[profile] if isinstance(profile, str) else profile
    rnd = random.Random(seed)
    ph = rnd.uniform(0.0, TAU)
    d0 = Vector(direction).normalized()
    if side is None:
        sd = d0.cross(Z)
        if sd.length < 1e-4:
            sd = d0.cross(Vector((1.0, 0.0, 0.0)))
    else:
        sd = Vector(side) - d0 * Vector(side).dot(d0)
    sd.normalize()
    bax = d0.cross(-Z)
    if bax.length < 1e-4:
        bax = sd.copy()
    bax.normalize()
    bm = bmesh.new()
    rows, ts = [], []
    p = Vector(base)
    step = length / segments
    for i in range(segments + 1):
        s = i / segments
        rot = Matrix.Rotation(bend * s * s * math.pi * 0.5, 3, bax)
        T = rot @ d0
        S = rot @ sd
        if twist:
            S = Matrix.Rotation(math.radians(twist * s), 3, T) @ S
        S = (S - T * S.dot(T)).normalized()
        N = S.cross(T)
        if i > 0:
            sm = (i - 0.5) / segments
            p = p + (Matrix.Rotation(bend * sm * sm * math.pi * 0.5, 3, bax) @ d0) * step
        w = prof(s) * width * 0.5
        if teeth and 0 < i < segments and i % 2 == 1:
            w *= 1.0 - teeth
        tt = t[0] + (t[1] - t[0]) * s
        if w < 1e-5:
            rows.append(([bm.verts.new(p)], N))
            ts.append(tt)
            continue
        lift = N * (fold * w)
        wl = N * (wave * w * math.sin(TAU * waves * s + ph))
        wr = N * (wave * w * math.sin(TAU * waves * s + ph + 1.9))
        row = [bm.verts.new(p - S * w + lift + wl)]
        if cols == 3:
            row.append(bm.verts.new(p))
        row.append(bm.verts.new(p + S * w + lift + wr))
        ts += [tt] * len(row)
        rows.append((row, N))
    for (A, na), (B, nb) in zip(rows, rows[1:]):
        want = na + nb
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for x, y in zip(B, B[1:]):
                _face(bm, (A[0], x, y), want)
        elif len(B) == 1:
            for x, y in zip(A, A[1:]):
                _face(bm, (x, y, B[0]), want)
        else:
            for k in range(len(A) - 1):
                _face(bm, (A[k], A[k + 1], B[k + 1], B[k]), want)
    return finish(name, bm, material, ts, smooth)


def corolla(name, center, axis, count, length, width, material, lift=0.3, bend=0.0, profile="obovate", segments=4,
            fold=0.0, wave=0.0, cols=2, seed=0, jitter=0.1, phase=None, spread=0.06):
    """A ring of petals (or sepals) round `center` facing along `axis`, like nk.petal_ring but with leaf()'s shapes:
    `lift` 0 spreads them flat, 1 stands them along the axis (negative sweeps them back). Each petal's normal faces
    the flower's front, so `fold` > 0 cups it."""
    rnd = random.Random(seed)
    ax, s, u = basis(axis)
    ph = rnd.uniform(0.0, TAU) if phase is None else phase
    parts = []
    for i in range(count):
        a = ph + (i + rnd.uniform(-jitter, jitter)) / count * TAU
        out = s * math.cos(a) + u * math.sin(a)
        lf = lift * math.pi * 0.5 + rnd.uniform(-spread, spread)
        d = out * math.cos(lf) + ax * math.sin(lf)
        parts.append(leaf("%s%d" % (name, i), center, d, length * rnd.uniform(0.92, 1.08),
                          width * rnd.uniform(0.92, 1.06), material, profile, segments, bend=bend, fold=fold,
                          wave=wave, side=out.cross(ax), cols=cols, seed=seed * 31 + i))
    return parts


def frond(name, base, heading, length, material, pairs=22, rise=70.0, fall=-30.0, power=1.7, pinna=0.1,
          pinna_w=0.02, stipe=0.18, fwd=12.0, lift=10.0, droop=0.25, roll=0.0, sway=0.0, seed=0,
          stipe_material=None):
    """A sword fern frond: a bare stalk (stipe) rising from `base` toward `heading` (radians) at `rise` degrees, then
    a midrib arching over to `fall` degrees at its tip, with `pairs` pairs of lance leaflets (pinnae), each with an
    ear at its base, longest a fifth of the way up and shrinking toward the tip. `roll` tilts the frond's plane,
    `sway` curves it sideways (degrees). Returns [stipe, blade]."""
    rnd = random.Random(seed)
    steps = 64
    pts = [Vector(base)]
    for i in range(steps):
        s = (i + 0.5) / steps
        el = math.radians(rise + (fall - rise) * s ** power)
        hd = heading + math.radians(sway) * s
        pts.append(pts[-1] + Vector((math.cos(hd) * math.cos(el), math.sin(hd) * math.cos(el), math.sin(el)))
                   * (length / steps))

    def frame(s):
        x = min(steps - 1e-6, max(0.0, s) * steps)
        i = int(x)
        p = pts[i].lerp(pts[i + 1], x - i)
        T = (pts[i + 1] - pts[i]).normalized()
        S = T.cross(Z).normalized()
        if roll:
            S = Matrix.Rotation(math.radians(roll), 3, T) @ S
        return p, T, S, S.cross(T)

    parts = [taper_tube(name + "Stipe", [frame(stipe * k / 3)[0] for k in range(4)], (0.0045, 0.003),
                        stipe_material or material, sides=4, t=(0.0, 0.15, 0.3, 0.4))]
    bm = bmesh.new()
    ts = []
    # Midrib: a narrow ribbon in the frond's plane
    prev = None
    nodes = [stipe + (1.0 - stipe) * k / 10 for k in range(11)]
    for s in nodes:
        p, T, S, N = frame(min(s, 0.999))
        w = 0.004 * (1.0 - s) + 0.001
        row = (bm.verts.new(p - S * w), bm.verts.new(p + S * w))
        ts += [0.45 + 0.4 * s] * 2
        if prev:
            _face(bm, (prev[0], prev[1], row[1], row[0]), N)
        prev = row
    # Leaflets
    shape = ((0.0, 0.3, 0.95), (0.22, 1.0, 1.0), (0.6, 0.66, 0.66), (1.0, 0.0, 0.0))
    for k in range(pairs):
        u = (k + 0.5) / pairs
        f = (0.6 + 0.4 * min(1.0, u / 0.18)) * (1.0 - 0.72 * (max(0.0, u - 0.25) / 0.75) ** 1.4)
        for sgn in (-1.0, 1.0):
            s = stipe + (1.0 - stipe) * min(0.995, u + (0.35 / pairs if sgn > 0 else 0.0))
            p, T, S, N = frame(s)
            L = pinna * f * rnd.uniform(0.9, 1.1)
            W = pinna_w * (0.5 + 0.5 * f)
            fw = math.radians(fwd + 30.0 * u)
            dr = S * sgn * math.cos(fw) + T * math.sin(fw)
            lf = math.radians(lift)
            dr = (dr * math.cos(lf) + N * math.sin(lf)).normalized()
            tip = N.cross(dr).normalized() * sgn          # across the leaflet, toward the frond's tip
            prow = None
            for q, back, fore in shape:
                c = p + S * sgn * 0.0015 + dr * (L * q) - N * (droop * L * q * q) + tip * (L * 0.1 * q * q)
                tt = 0.4 + 0.6 * q
                if back == 0.0:
                    row = [bm.verts.new(c)]
                else:
                    row = [bm.verts.new(c - tip * (W * 0.5 * back)), bm.verts.new(c + tip * (W * 0.5 * fore))]
                ts += [tt] * len(row)
                if prow:
                    if len(row) == 1:
                        _face(bm, (prow[0], prow[1], row[0]), N)
                    else:
                        _face(bm, (prow[0], prow[1], row[1], row[0]), N)
                prow = row
    parts.append(finish(name, bm, material, ts, smooth=70.0))
    return parts


def fiddlehead(name, base, heading, height, material, coil=0.02, turns=1.6, radius=0.0035):
    """A fern fiddlehead: a stalk `height` tall leaning toward `heading`, its top rolled forward into a crozier
    coil."""
    hd = Vector((math.cos(heading), math.sin(heading), 0.0))
    b = Vector(base)
    pts = [b, b + hd * 0.006 + Z * height * 0.35, b + hd * 0.014 + Z * height * 0.7]
    top = b + hd * 0.02 + Z * height
    pts.append(top)
    radii = [radius, radius * 0.95, radius * 0.95, radius * 1.15]
    c = top + hd * coil
    n = 13
    for k in range(1, n + 1):
        th = k / n * turns * TAU
        r = coil * math.exp(-0.32 * th)
        pts.append(c + (hd * -math.cos(th) + Z * math.sin(th)) * r)
        radii.append(radius * (1.2 - 0.7 * k / n))
    return taper_tube(name, pts, radii, material, sides=5)


# ---------------------------------------------------------------- mushroom parts

def _profile_at(profile, rr):
    """Height and outward normal (in r, h) of a cap's top profile at radius rr."""
    for (r0, h0), (r1, h1) in zip(profile, profile[1:]):
        if r0 <= rr <= r1 + 1e-9:
            f = (rr - r0) / max(1e-9, r1 - r0)
            dr, dh = r1 - r0, h1 - h0
            ln = math.hypot(dr, dh) or 1.0
            return h0 + dh * f, (-dh / ln, dr / ln)
    r1, h1 = profile[-1]
    return h1, (1.0, 0.0)


def warts(name, center, axis, profile, material, count, size, seed=0, reach=0.88, height=0.45, sides=5):
    """Warts on a toadstool cap: `count` low pyramids, about `size` across, scattered over the top of the cap
    `profile` ((r, h) about `axis` through `center`, from the apex out to the rim), denser where there's more cap."""
    rnd = random.Random(seed)
    ax, s, u = basis(axis)
    c = Vector(center)
    top = []
    for r, h in profile:
        if top and r < top[-1][0]:
            break
        top.append((r, h))
    R = top[-1][0]
    # Pick spots by cap area: ring segments weighted by slant length times radius
    segs = []
    for (r0, h0), (r1, h1) in zip(top, top[1:]):
        if r0 >= R * reach:
            break
        r1c = min(r1, R * reach)
        segs.append((r0, r1c, math.hypot(r1 - r0, h1 - h0) * (r1c - r0) / max(1e-9, r1 - r0) * (r0 + r1c)))
    total = sum(w for _, _, w in segs)
    bm = bmesh.new()
    ts = []
    for k in range(count):
        x = rnd.uniform(0.0, total)
        for r0, r1, w in segs:
            if x <= w:
                break
            x -= w
        rr = math.sqrt(r0 * r0 + rnd.random() * (r1 * r1 - r0 * r0))
        hh, (nr, nh) = _profile_at(top, rr)
        a = rnd.uniform(0.0, TAU)
        out = s * math.cos(a) + u * math.sin(a)
        at = c + ax * hh + out * rr
        nv = (out * nr + ax * nh).normalized()
        sz = size * rnd.uniform(0.6, 1.3) * (1.0 - 0.35 * rr / R)
        _, ws, wu = basis(nv)
        ph = rnd.uniform(0.0, TAU)
        hgt = sz * height * rnd.uniform(0.7, 1.2)
        ring = []
        for j in range(sides):
            b = ph + j / sides * TAU
            ring.append(bm.verts.new(at + (ws * math.cos(b) + wu * math.sin(b)) * (sz * 0.5 * rnd.uniform(0.75, 1.15))
                                     - nv * hgt * 0.35))
        tip = bm.verts.new(at + nv * hgt + (ws * rnd.uniform(-1, 1) + wu * rnd.uniform(-1, 1)) * sz * 0.12)
        ts += [1.0] * (sides + 1)
        below = at - nv * hgt
        for j in range(sides):
            v0, v1 = ring[j], ring[(j + 1) % sides]
            _face(bm, (v0, v1, tip), (v0.co + v1.co + tip.co) / 3.0 - below)
    return finish(name, bm, material, ts, smooth=None)


def gills(name, center, axis, under, material, count, depth, seed=0):
    """Gills under a cap: `count` thin radial sheets hanging up to `depth` below the cap's underside `under` ((r, h)
    pairs about `axis` through `center`), every other one a short one from the rim."""
    rnd = random.Random(seed)
    ax, s, u = basis(axis)
    c = Vector(center)
    pts = sorted(under)

    def h_at(r):
        for (r0, h0), (r1, h1) in zip(pts, pts[1:]):
            if r0 <= r <= r1:
                return h0 + (h1 - h0) * (r - r0) / max(1e-9, r1 - r0)
        return pts[0][1] if r < pts[0][0] else pts[-1][1]

    r_in, r_out = pts[0][0] * 1.08, pts[-1][0] * 0.97
    bm = bmesh.new()
    ts = []
    for k in range(count):
        a = (k + rnd.uniform(-0.2, 0.2)) / count * TAU
        out = s * math.cos(a) + u * math.sin(a)
        tan = ax.cross(out)
        r0 = r_in if k % 2 == 0 else r_in + (r_out - r_in) * 0.45
        rm = r0 + (r_out - r0) * 0.4
        dd = depth * (1.0 if k % 2 == 0 else 0.75)
        vs = [c + ax * (h_at(r0) - 0.0005) + out * r0,
              c + ax * (h_at(r0) - dd * 0.55) + out * r0,
              c + ax * (h_at(rm) - dd) + out * rm,
              c + ax * (h_at(rm) - 0.0005) + out * rm,
              c + ax * (h_at(r_out) - dd * 0.1) + out * r_out]
        v = [bm.verts.new(p) for p in vs]
        ts += [0.5] * 5
        _face(bm, (v[0], v[1], v[2], v[3]), tan)
        _face(bm, (v[3], v[2], v[4]), tan)
    return finish(name, bm, material, ts, smooth=None)


# ---------------------------------------------------------------- the ground: litter, needles, moss, ash

def litter(name, count, radius, materials, seed=0, center=(0.0, 0.0), size=(0.035, 0.06), keep_out=(), segments=3):
    """Fallen leaves lying on the ground: `count` of them within `radius` of `center`, taking `materials` in turn,
    each a little curled; `keep_out` lists (x, y, r) circles to leave clear (stems)."""
    rnd = random.Random(seed)
    parts = []
    tries = 0
    while len(parts) < count and tries < count * 40:
        tries += 1
        a = rnd.uniform(0.0, TAU)
        r = radius * math.sqrt(rnd.random())
        x, y = center[0] + r * math.cos(a), center[1] + r * math.sin(a)
        if any((x - kx) ** 2 + (y - ky) ** 2 < kr * kr for kx, ky, kr in keep_out):
            continue
        h = rnd.uniform(0.0, TAU)
        L = rnd.uniform(*size)
        d = Vector((math.cos(h), math.sin(h), rnd.uniform(0.0, 0.08)))
        z = nk.GROUND + 0.002 + rnd.uniform(0.0, 0.004)
        k = len(parts)
        parts.append(leaf("%s%d" % (name, k), (x - d.x * L * 0.5, y - d.y * L * 0.5, z), d, L,
                          L * rnd.uniform(0.5, 0.68), materials[k % len(materials)], "ovate", segments,
                          bend=rnd.uniform(-0.2, 0.02), fold=rnd.uniform(-0.3, 0.3), wave=0.15,
                          twist=rnd.uniform(-20.0, 20.0), seed=seed * 101 + k))
    return parts


def needles(name, count, radius, material, seed=0, center=(0.0, 0.0), length=(0.035, 0.06), keep_out=()):
    """Fallen pine needles strewn over the ground (two triangles each)."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    ts = []
    n = 0
    tries = 0
    while n < count and tries < count * 40:
        tries += 1
        a = rnd.uniform(0.0, TAU)
        r = radius * math.sqrt(rnd.random())
        x, y = center[0] + r * math.cos(a), center[1] + r * math.sin(a)
        if any((x - kx) ** 2 + (y - ky) ** 2 < kr * kr for kx, ky, kr in keep_out):
            continue
        h = rnd.uniform(0.0, TAU)
        L = rnd.uniform(*length)
        d = Vector((math.cos(h), math.sin(h), 0.0))
        sd = Vector((-d.y, d.x, 0.0)) * 0.0008
        z = nk.GROUND + 0.0015 + rnd.uniform(0.0, 0.006)
        p0 = Vector((x, y, z)) - d * L * 0.5
        p1 = p0 + d * L + Vector((0.0, 0.0, rnd.uniform(-0.002, 0.004)))
        v = [bm.verts.new(p0 - sd), bm.verts.new(p0 + sd), bm.verts.new(p1 + sd * 0.3), bm.verts.new(p1 - sd * 0.3)]
        ts += [0.6] * 4
        _face(bm, v, Z)
        n += 1
    return finish(name, bm, material, ts, smooth=None)


def moss(name, center, radius, height, material, seed=0, segments=9):
    """A low lumpy cushion of moss on the ground."""
    rnd = random.Random(seed)
    p = [rnd.uniform(0.0, TAU) for _ in range(3)]

    def wob(i, a):
        m = 1.0 + 0.18 * math.sin(3 * a + p[0]) + 0.1 * math.sin(5 * a + p[1])
        return m, (height * (0.3 if i == 1 else 0.2) * math.sin(2 * a + p[2] + i) if 0 < i < 3 else 0.0)

    prof = [(0.0, height), (radius * 0.45, height * 0.92), (radius * 0.8, height * 0.6), (radius, -0.004)]
    return revolve(name, prof, (center[0], center[1], nk.GROUND), Z, material, segments, t=(1.0, 0.8, 0.5, 0.0),
                   wobble=wob, phase=rnd.uniform(0.0, TAU), smooth=80.0)


def patch(name, center, radius, material, seed=0, segments=20, lift=0.003):
    """A flat, ragged patch lying on the ground (ash, soot): "t" 1 in its middle, 0 round its edge."""
    rnd = random.Random(seed)
    p = [rnd.uniform(0.0, TAU) for _ in range(6)]

    def wob(i, a):
        edge = (0.2 * math.sin(2 * a + p[0]) + 0.13 * math.sin(3 * a + p[1]) + 0.08 * math.sin(5 * a + p[2])
                + 0.06 * math.sin(9 * a + p[3]) + 0.04 * math.sin(13 * a + p[4]))
        bump = lift * 0.8 * math.sin(3 * a + p[5] + i) if 0 < i < 3 else 0.0
        return 1.0 + edge * (0.4 + 0.3 * i), bump

    prof = [(0.0, lift + 0.002), (radius * 0.35, lift + 0.0015), (radius * 0.7, lift), (radius, lift * 0.15)]
    return revolve(name, prof, (center[0], center[1], nk.GROUND), Z, material, segments, t=(1.0, 0.9, 0.6, 0.0),
                   wobble=wob, phase=rnd.uniform(0.0, TAU), away=(center[0], center[1], nk.GROUND - 1.0),
                   smooth=89.0)


# ---------------------------------------------------------------- materials

def _voronoi(g, scale, vector=None, feature="F1", randomness=1.0, output="Distance"):
    n = g.node("ShaderNodeTexVoronoi")
    n.voronoi_dimensions = "3D"
    n.feature = feature
    g._in(n, "Scale", scale)
    g._in(n, "Randomness", randomness)
    g.links.new(vector if vector is not None else g.coords(), tk._sock(n.inputs, "Vector"))
    return tk._sock(n.outputs, output)


def _mapped(g, scale, rotation=(0.0, 0.0, 0.0)):
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = scale
    m.inputs["Rotation"].default_value = rotation
    return m.outputs[0]


def _dark(c, f):
    return tuple(x * f for x in c)


# Close-up detail. A plant seen at arm's length shows a few texels per mm; textures built only from smooth noise read
# as blurry vector art there. These give the surfaces structure down to the texel: cells, crests, grit, and real
# relief for the normal map (bump distances in meters, so the relief doesn't depend on the atlas size).

def _warped(g, scale, amount, vector=None):
    """Object coordinates pushed about by a noise `scale` per meter, by up to `amount` meters: cells and lines drawn
    in it lose their straight edges."""
    nz = g.node("ShaderNodeTexNoise")
    g._in(nz, "Scale", scale)
    g._in(nz, "Detail", 3.0)
    g.links.new(vector if vector is not None else g.coords(), nz.inputs["Vector"])
    off = g.node("ShaderNodeVectorMath", operation="SUBTRACT")
    g.links.new(tk._sock(nz.outputs, "Color"), off.inputs[0])
    off.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = g.node("ShaderNodeVectorMath", operation="SCALE")
    g.links.new(off.outputs[0], sc.inputs[0])
    g._in(sc, "Scale", amount * 2.0)
    add = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(vector if vector is not None else g.coords(), add.inputs[0])
    g.links.new(tk._sock(sc.outputs, "Vector"), add.inputs[1])
    return tk._sock(add.outputs, "Vector")


def _cells(g, scale, vector=None, randomness=1.0, feature="F1"):
    """A Voronoi field: (distance to the nearest cell's point, a random 0..1 for that cell)."""
    n = g.node("ShaderNodeTexVoronoi")
    n.voronoi_dimensions = "3D"
    n.feature = feature
    g._in(n, "Scale", scale)
    g._in(n, "Randomness", randomness)
    g.links.new(vector if vector is not None else g.coords(), tk._sock(n.inputs, "Vector"))
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tk._sock(n.outputs, "Color"), sep.inputs[0])
    return tk._sock(n.outputs, "Distance"), sep.outputs[0]


def _ridged(g, n):
    """1 along the crest lines of a noise value (where it crosses 0.5), falling away either side: thin wiry lines."""
    return g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", n, 2.0), 1.0)))


def _polar(g, scale, along=0.0):
    """Coordinates that run round a cap made with revolve(polar=True): a circle of radius `scale` by angle, and "t"
    times `along`; noise in it streaks radially from the apex to the rim."""
    vec = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("MULTIPLY", nk._attr(g, "ca"), scale), vec.inputs[0])
    g.links.new(g.math("MULTIPLY", nk._attr(g, "sa"), scale), vec.inputs[1])
    g.links.new(g.math("MULTIPLY", nk._attr(g, "t"), along), vec.inputs[2])
    return vec.outputs[0]


def moss_layer(g, scale=1.0, relief=1.0):
    """Moss as it looks up close, as node signals for a material to mix: low cushions a few centimeters across, made
    of little rounded clumps (cells about a centimeter, each its own shade of green, a few yellower) with smaller
    tufts on them, wiry shoots, yellow-green tips catching the light on the tops, dark gaps between the clumps, and
    brown dead patches. Returns (color, height 0..1, roughness, bump normal)."""
    co = _warped(g, 25.0 * scale, 0.005 / scale)
    d1, r1 = _cells(g, 95.0 * scale, co)
    d2, _ = _cells(g, 240.0 * scale, co)
    cushion = g.ramp(g.noise(14.0 * scale, detail=3.0), 0.3, 0.7)
    dome = g.ramp(d1, 0.72, 0.05)
    tuft = g.ramp(d2, 0.65, 0.0)
    shoots = g.ramp(_ridged(g, g.noise(300.0 * scale, detail=3.0, distortion=1.4)), 0.72, 0.97)
    grain = g.noise(600.0 * scale, detail=2.0)
    height = g.math("ADD", g.math("MULTIPLY", cushion, 0.32), g.math("MULTIPLY", dome, 0.26))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", tuft, 0.22), g.math("MULTIPLY", shoots, 0.15)))
    height = g.math("ADD", height, g.math("MULTIPLY", grain, 0.05))
    col = g.mix(g.ramp(r1, 0.05, 0.95), (0.034, 0.062, 0.011), (0.07, 0.112, 0.018))
    col = g.mix(g.math("MULTIPLY", g.ramp(r1, 0.88, 0.96), 0.7), col, (0.12, 0.135, 0.03))
    col = g.mix(g.math("MULTIPLY", cushion, 0.35), col, (0.09, 0.14, 0.024))
    tips = g.math("MULTIPLY", g.ramp(g.math("ADD", g.math("MULTIPLY", dome, 0.6), g.math("MULTIPLY", tuft, 0.4)),
                                     0.5, 0.95), g.math("ADD", 0.4, g.math("MULTIPLY", shoots, 0.6)))
    col = g.mix(g.math("MULTIPLY", tips, 0.85), col, (0.16, 0.2, 0.042))
    col = g.mix(g.math("MULTIPLY", g.ramp(dome, 0.25, 0.0), 0.45), col, (0.012, 0.018, 0.005))
    col = g.mix(g.math("MULTIPLY", g.ramp(tuft, 0.2, 0.0), 0.3), col, (0.015, 0.024, 0.006))
    dead = g.math("MULTIPLY", g.ramp(g.noise(9.0 * scale, detail=5.0), 0.6, 0.7),
                  g.ramp(g.noise(60.0 * scale, detail=3.0), 0.35, 0.6))
    col = g.mix(g.math("MULTIPLY", dead, 0.85), col, (0.085, 0.06, 0.025))
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.55, 0.2), 0.35), col, (0.02, 0.032, 0.007))
    rough = g.mixf(tips, 0.95, 0.82)
    return col, height, rough, g.bump(height, 1.0, 0.005 * relief)

def fungus(name, base, tip, rough=0.5, vary=0.2, scale=30.0, bump=0.03, ramp=(0.1, 0.95), margin=None,
           streaks=0.0, sat=1.0, value=1.0, spots=None):
    """A mushroom's flesh (cap, stem, gills, warts): `base` at t = 0 shading to `tip` at t = 1 over `ramp`, blotched
    by `vary`, an optional `margin` color right at t = 1 (a cap's rim), fine fibers along Z (`streaks`, stems).
    `spots` = (color, scale, size) paints ragged raised flecks (a fly agaric's veil remnants) where t < 0.9."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, ramp[0], ramp[1]), base, tip)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(scale, detail=4.0), 0.35, 0.75), vary), col, _dark(tip, 0.7))
    if margin is not None:
        col = g.mix(g.ramp(t, 0.9, 1.0), col, margin)
    height = g.noise(scale * 3.0, detail=6.0)
    if spots is not None:
        scol, sscale, ssize = spots
        warp = g.node("ShaderNodeVectorMath", operation="ADD")
        g.links.new(g.coords(), warp.inputs[0])
        nz = g.node("ShaderNodeTexNoise")
        g._in(nz, "Scale", sscale * 0.7)
        g._in(nz, "Detail", 3.0)
        g.links.new(g.coords(), nz.inputs["Vector"])
        sub = g.node("ShaderNodeVectorMath", operation="SCALE")
        g.links.new(tk._sock(nz.outputs, "Color"), sub.inputs[0])
        g._in(sub, "Scale", 0.35 / sscale)
        g.links.new(sub.outputs[0], warp.inputs[1])
        fleck = g.math("MULTIPLY", g.ramp(_voronoi(g, sscale, warp.outputs[0]), ssize, ssize * 0.75), g.ramp(t, 0.92, 0.86))
        col = g.mix(fleck, col, scol)
        height = g.math("ADD", height, g.math("MULTIPLY", fleck, 2.0))
    if streaks:
        fib = g.noise(1.0, detail=3.0, vector=_mapped(g, (180.0, 180.0, 6.0)))
        col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.45, 0.72), streaks), col, _dark(tip, 0.78))
        height = g.math("ADD", height, fib)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, bump, 0.002))


def bolete_cap(name, center, rim, margin, flesh=(0.6, 0.52, 0.36), rough=(0.58, 0.74)):
    """A porcini's cap up close (t 0 at the apex, 1 at the rim): `center` brown darkening and reddening toward the
    middle, paler `rim` toward a thin whitish `margin`, unevenly colored at several scales (darker water-soaked
    blotches, paler bloom); a softly hammered surface of shallow dimples, finely wrinkled skin and a suede grain;
    a few slug-grazed bites down to the white `flesh` with a bruised brown edge, and grit. A little greasy in the
    middle (`rough` runs from the middle to the rim), matte toward the edge."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    co = _warped(g, 30.0, 0.004)
    col = g.mix(g.ramp(t, 0.05, 0.92), center, rim)
    # Uneven color: broad darker blotches, paler bloom, a fine mottle
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(11.0, detail=6.0, roughness=0.62), 0.6, 0.28), 0.75), col,
                _dark(center, 0.62))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(32.0, detail=5.0, distortion=0.4), 0.52, 0.8), 0.6), col,
                tuple(min(1.0, c * 1.45) for c in rim))
    blot, br = _cells(g, 45.0, _warped(g, 90.0, 0.004))
    soak = g.math("MULTIPLY", g.ramp(blot, 0.42, 0.22), g.ramp(br, 0.5, 0.62))
    col = g.mix(g.math("MULTIPLY", soak, 0.45), col, _dark(center, 0.6))
    mottle = g.noise(150.0, detail=4.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(mottle, 0.62, 0.3), 0.35), col, _dark(center, 0.75))
    # Hammered: shallow dimples a centimeter across, their floors a touch darker; wrinkled skin; suede grain
    dim, _ = _cells(g, 95.0, co)
    dimple = g.ramp(dim, 0.0, 0.55)
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, dimple), 0.22), col, _dark(center, 0.8))
    wrinkle = g.ramp(_ridged(g, g.noise(170.0, detail=3.0, distortion=0.8)), 0.8, 0.97)
    col = g.mix(g.math("MULTIPLY", wrinkle, 0.15), col, _dark(center, 0.72))
    suede = g.noise(420.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(suede, 0.62, 0.25), 0.35), col, _dark(center, 0.72))
    # Slug grazing: ragged bites down to the white flesh, with a brown bruised edge
    bd, bsel = _cells(g, 24.0, _warped(g, 110.0, 0.0025))
    bite = g.math("MULTIPLY", g.math("SUBTRACT", 0.3, bd), g.ramp(bsel, 0.86, 0.87))
    scar = g.ramp(bite, 0.06, 0.075)
    bruise = g.math("MULTIPLY", g.ramp(bite, 0.0, 0.06), g.math("SUBTRACT", 1.0, scar))
    col = g.mix(g.math("MULTIPLY", bruise, 0.75), col, (0.1, 0.055, 0.028))
    col = g.mix(scar, col, g.mix(g.ramp(g.noise(160.0), 0.3, 0.7), flesh, _dark(flesh, 0.82)))
    # Grit: dark specks of soil
    grit, gr = _cells(g, 260.0)
    speck = g.math("MULTIPLY", g.ramp(grit, 0.16, 0.08), g.ramp(gr, 0.8, 0.86))
    col = g.mix(speck, col, (0.03, 0.022, 0.015))
    col = g.mix(g.ramp(t, 0.93, 0.995), col, margin)
    height = g.math("ADD", g.math("MULTIPLY", dimple, 0.6), g.math("MULTIPLY", suede, 0.12))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", wrinkle, 0.07))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", scar, 0.9), g.math("MULTIPLY", bruise, 0.25)))
    height = g.math("ADD", height, g.math("MULTIPLY", speck, 0.3))
    r = g.mixf(g.ramp(t, 0.2, 0.9), rough[0], rough[1])
    r = g.math("ADD", r, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(25.0, detail=3.0), 0.5), 0.14))
    r = g.mixf(g.math("MAXIMUM", scar, speck), r, 0.92)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.0012))


def agaric_cap(name, center, mid, rim, fleck=(0.76, 0.71, 0.55), rough=(0.5, 0.62), flecks=0.3):
    """A fly agaric's cap up close (made with revolve(polar=True); t 0 at the apex, 1 at the rim): a deep `center`
    red through scarlet `mid` to an orange-red `rim`, fine dark fibrils streaking out from the middle, a faintly
    striate margin, soft mottling, and ragged cream veil flecks (`flecks` 0 to 1 of the cap) between the modelled
    warts, a little raised. Satin rather than glossy."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, 0.45, 1.0), g.mix(g.ramp(t, 0.0, 0.5), center, mid), rim)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(16.0, detail=5.0), 0.35, 0.75), 0.35), col, _dark(mid, 0.7))
    # Radial fibrils, fainter toward the middle
    fib = g.noise(1.0, detail=4.0, vector=_polar(g, 90.0, 6.0))
    streak = g.math("MULTIPLY", g.ramp(fib, 0.5, 0.7), g.ramp(t, 0.3, 0.85))
    col = g.mix(g.math("MULTIPLY", streak, 0.22), col, _dark(center, 0.75))
    # A striate margin: short grooves in from the rim
    groove = g.math("MULTIPLY", g.ramp(_ridged(g, g.noise(1.0, detail=2.0, vector=_polar(g, 40.0, 2.0))), 0.75, 0.95),
                    g.ramp(t, 0.86, 0.97))
    col = g.mix(g.math("MULTIPLY", groove, 0.4), col, _dark(rim, 0.6))
    # Veil flecks: ragged patches of every size, cream with a yellowish-brown edge, thinning toward the rim
    co = _warped(g, 70.0, 0.0035)
    d, size = _cells(g, 55.0, co)
    edge = g.math("SUBTRACT", g.math("ADD", d, g.math("MULTIPLY", g.noise(260.0, detail=3.0), 0.14)),
                  g.math("MULTIPLY", g.math("POWER", size, 1.5), 0.3 + flecks * 0.6))
    fl = g.math("MULTIPLY", g.ramp(edge, 0.1, 0.06), g.ramp(t, 0.9, 0.72))
    rimfl = g.math("MULTIPLY", g.ramp(edge, 0.12, 0.085), g.ramp(t, 0.9, 0.72))
    col = g.mix(g.math("MULTIPLY", rimfl, 0.8), col, _dark(fleck, 0.5))
    col = g.mix(fl, col, g.mix(g.ramp(g.noise(200.0), 0.3, 0.7), fleck, _dark(fleck, 0.82)))
    sheen = g.noise(500.0, detail=2.0)
    height = g.math("ADD", g.math("MULTIPLY", fl, 0.8), g.math("MULTIPLY", sheen, 0.08))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", groove, 0.4), g.math("MULTIPLY", streak, 0.1)))
    r = g.mixf(g.ramp(t, 0.2, 0.95), rough[0], rough[1])
    r = g.math("ADD", r, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(20.0, detail=3.0), 0.5), 0.1))
    r = g.mixf(fl, r, 0.85)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.0008))


def pores(name, color, dark, rough=0.8, scale=650.0):
    """A bolete's spongy underside: a fine field of pores."""
    mat, g = tk.new_material(name)
    hole = g.ramp(_voronoi(g, scale), 0.32, 0.12)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(18.0), 0.3, 0.75), 0.45), color, dark)
    col = g.mix(g.math("MULTIPLY", hole, 0.6), col, _dark(dark, 0.7))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.math("SUBTRACT", 1.0, hole), 0.3, 0.001))


def reticulate(name, base, tip, net, rough=0.6, scale=110.0, stretch=0.45, reach=(0.3, 0.75), soil=None):
    """A bolete stem: `base` shading to `tip` up it, fine fibrous streaks along it, a raised pale net over its upper
    part, and (if `soil` is given) dirt clinging round its foot."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, 0.0, 1.0), base, tip)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(25.0, detail=5.0), 0.4, 0.7), 0.3), col, _dark(base, 0.8))
    fib = g.noise(1.0, detail=4.0, vector=_mapped(g, (260.0, 260.0, 18.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.75), 0.25), col, _dark(base, 0.85))
    e = _voronoi(g, scale, _warped(g, scale * 0.5, 0.25 / scale, _mapped(g, (1.0, 1.0, stretch))),
                 feature="DISTANCE_TO_EDGE")
    cell = g.math("MULTIPLY", g.ramp(e, 0.05, 0.25), g.ramp(t, reach[0], reach[1]))
    line = g.math("MULTIPLY", g.ramp(e, 0.06, 0.015), g.ramp(t, reach[0], reach[1]))
    col = g.mix(g.math("MULTIPLY", cell, 0.2), col, _dark(base, 0.75))
    col = g.mix(line, col, net)
    height = g.math("ADD", line, g.math("MULTIPLY", fib, 0.25))
    r = rough
    if soil is not None:
        dirt = g.ramp(g.math("ADD", t, g.math("MULTIPLY", g.noise(40.0, detail=4.0), 0.25)), 0.32, 0.2)
        col = g.mix(dirt, col, g.mix(g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.7), soil, _dark(soil, 1.6)))
        height = g.math("ADD", height, g.math("MULTIPLY", dirt, g.noise(300.0, detail=2.0)))
        r = g.mixf(dirt, rough, 0.95)
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.0006))


def honeycomb(name, ridge, pit, deep, rough=0.75, scale=95.0, stretch=0.5):
    """A morel's cap: pale or dark ridges round deep pits, the pits drawn out lengthways (along Z). The ridges wander
    (warped cells), thicken and thin, carry a mealy grain, and the pits' walls are wrinkled and darken toward their
    floors, with real depth in the normal map."""
    mat, g = tk.new_material(name)
    co = _warped(g, scale * 0.45, 0.35 / scale, _mapped(g, (1.0, 1.0, stretch)))
    e = _voronoi(g, scale, co, feature="DISTANCE_TO_EDGE")
    wob = g.math("MULTIPLY", g.noise(scale * 0.8, detail=3.0), 0.05)
    thick = g.math("MULTIPLY", g.noise(scale * 0.25, detail=2.0), 0.05)
    e = g.math("SUBTRACT", g.math("ADD", e, wob), thick)
    on_ridge = g.ramp(e, 0.07, 0.02)
    depth = g.ramp(e, 0.03, 0.3)
    wrinkle = g.noise(scale * 4.0, detail=3.0, distortion=0.8)
    meal = g.noise(scale * 9.0, detail=2.0)
    col = g.mix(depth, pit, deep)
    col = g.mix(g.math("MULTIPLY", g.ramp(wrinkle, 0.55, 0.8), g.math("MULTIPLY", depth, 0.6)), col, _dark(deep, 0.5))
    col = g.mix(on_ridge, col, ridge)
    col = g.mix(g.math("MULTIPLY", g.ramp(meal, 0.55, 0.8), g.math("MULTIPLY", on_ridge, 0.45)), col,
                tuple(min(1.0, c * 1.5 + 0.02) for c in ridge))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(10.0), 0.35, 0.7), 0.3), col, _dark(ridge, 0.7))
    height = g.math("SUBTRACT", 1.0, depth)
    height = g.math("ADD", height, g.math("MULTIPLY", wrinkle, g.math("MULTIPLY", depth, 0.12)))
    height = g.math("ADD", height, g.math("MULTIPLY", meal, 0.04))
    r = g.mixf(on_ridge, rough, min(1.0, rough + 0.12))
    return tk.finish(mat, g, col, 0.0, r, g.bump(height, 1.0, 0.004))


def berry(name, color, top, seed_color=(0.6, 0.42, 0.07), rough=0.3, scale=520.0):
    """A strawberry's skin: `top` color by the calyx shading to `color`, studded with seeds in little dimples."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, 0.0, 0.45), top, color)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(40.0), 0.35, 0.7), 0.25), col, _dark(color, 0.75))
    d = _voronoi(g, scale, randomness=0.7)
    seedm = g.ramp(d, 0.17, 0.11)
    col = g.mix(seedm, col, seed_color)
    dimple = g.ramp(d, 0.32, 0.12)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.math("SUBTRACT", seedm, g.math("MULTIPLY", dimple, 0.6)),
                                                       0.35, 0.001))


def spotted(name, base, spot, halo, tip=None, scale=300.0, reach=0.75):
    """A foxglove's throat: dark spots ringed with white on a pale ground, fading out toward t = 1."""
    mat, g = tk.new_material(name)
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(t, 0.5, 1.0), base, tip or base)
    d = _voronoi(g, scale, randomness=0.85)
    fade = g.ramp(t, reach, reach - 0.25)
    sp = g.math("MULTIPLY", g.ramp(d, 0.25, 0.17), fade)
    hl = g.math("MULTIPLY", g.ramp(d, 0.38, 0.27), fade)
    col = g.mix(hl, col, halo)
    col = g.mix(sp, col, spot)
    return tk.finish(mat, g, col, 0.0, 0.5, g.bump(g.noise(80.0), 0.02, 0.001))


def moss_material(name, soil=(0.035, 0.025, 0.016)):
    """A moss cushion on the ground (moss()): moss_layer's clumps, breaking up toward the cushion's foot (t = 0) into
    separate tufts over dark soil, so its edge is ragged rather than a clean outline."""
    mat, g = tk.new_material(name)
    col, height, rough, normal = moss_layer(g)
    edge = g.math("ADD", g.math("MULTIPLY", nk._attr(g, "t"), 1.5), g.math("MULTIPLY", g.noise(30.0, detail=4.0), 0.5))
    cover = g.ramp(g.math("ADD", edge, g.math("MULTIPLY", height, 0.6)), 0.75, 0.95)
    col = g.mix(cover, g.mix(g.ramp(g.noise(80.0, detail=4.0), 0.3, 0.7), soil, _dark(soil, 1.8)), col)
    return tk.finish(mat, g, col, 0.0, g.mixf(cover, 0.95, rough), normal)


def litter_material(name, color, color2, spots=0.35):
    """Dead leaves: blotchy browns with darker rot spots."""
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), color, color2)
    sp = g.ramp(g.noise(90.0, detail=3.0), 0.64, 0.7)
    col = g.mix(g.math("MULTIPLY", sp, spots), col, _dark(color, 0.4))
    return tk.finish(mat, g, col, 0.0, 0.8, g.bump(g.noise(150.0), 0.08, 0.001))


def ash(name, light=(0.4, 0.39, 0.37), dark=(0.15, 0.145, 0.14), soot=(0.035, 0.032, 0.03)):
    """Wood ash: soft greys in drifts, a powdery grain, crumbs of charcoal of every size (a few with brown unburnt
    wood), pale flakes of white ash, sooty round the patch's edge (t = 0), which breaks up into specks rather than
    ending in a line."""
    mat, g = tk.new_material(name)
    drift = g.noise(16.0, detail=6.0, roughness=0.65)
    col = g.mix(g.ramp(drift, 0.2, 0.8), g.mix(0.45, dark, light), light)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(70.0, detail=4.0), 0.4, 0.75), 0.5), col, dark)
    powder = g.noise(700.0, detail=2.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(powder, 0.62, 0.22), 0.5), col, _dark(dark, 0.75))
    d, r = _cells(g, 90.0, _warped(g, 160.0, 0.003))
    crumb = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", d, g.math("MULTIPLY", r, 0.22)), 0.05, 0.0),
                   g.ramp(g.noise(7.0, detail=3.0), 0.52, 0.62))
    col = g.mix(crumb, col, g.mix(g.ramp(r, 0.9, 0.95), (0.014, 0.013, 0.012), (0.1, 0.05, 0.022)))
    specks = g.ramp(_voronoi(g, 240.0), 0.12, 0.05)
    col = g.mix(g.math("MULTIPLY", specks, 0.9), col, (0.015, 0.014, 0.013))
    fd, fr = _cells(g, 160.0)
    flake = g.math("MULTIPLY", g.ramp(fd, 0.16, 0.08), g.ramp(fr, 0.9, 0.93))
    col = g.mix(flake, col, (0.6, 0.59, 0.56))
    edge = g.math("ADD", nk._attr(g, "t"), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(60.0, detail=3.0), 0.5), 0.4))
    col = g.mix(g.ramp(edge, 0.05, 0.5), soot, col)
    height = g.math("ADD", g.math("MULTIPLY", drift, 0.5), g.math("MULTIPLY", powder, 0.15))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", crumb, 0.5), g.math("MULTIPLY", flake, 0.2)))
    return tk.finish(mat, g, col, 0.0, g.mixf(crumb, 0.95, 0.7), g.bump(height, 1.0, 0.0015))


def char(name, scale=70.0):
    """Charcoal: black, crazed into little blocks, a dull sheen on the blocks, brown wood showing here and there."""
    mat, g = tk.new_material(name)
    e = _voronoi(g, scale, _mapped(g, (1.0, 1.0, 1.0)), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.07, 0.02)
    col = g.mix(g.ramp(g.noise(40.0), 0.3, 0.7), (0.02, 0.019, 0.018), (0.055, 0.05, 0.047))
    col = g.mix(crack, col, (0.004, 0.004, 0.004))
    col = g.mix(g.ramp(g.noise(6.0, detail=5.0), 0.68, 0.74), col, (0.12, 0.06, 0.025))
    return tk.finish(mat, g, col, 0.0, g.mixf(crack, 0.55, 0.95), g.bump(g.math("SUBTRACT", 1.0, crack), 0.6, 0.003))


# ---------------------------------------------------------------- checks

def bounds(objs):
    """The (min, max) corners of everything in `objs`, for checking a plant's footprint."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def report(script, pieces):
    lo, hi = bounds(pieces)
    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in pieces)
    print("[%s] footprint x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f, %d pieces, ~%d triangles" %
          (script, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z, len(pieces), tris))
