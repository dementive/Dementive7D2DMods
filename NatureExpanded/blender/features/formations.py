"""Rock-formation helpers on top of featurekit: layered rock materials (sandstone, wasteland rock, frost-shattered
slate) and closed solid shapes for standing rock (columns, spires, hoodoos, cairn stones) and natural arches.
Import as `import formations as fm` (it imports featurekit as fk)."""
import math
import os
import sys

import bmesh
from mathutils import Matrix, Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
SKIRT = fk.SKIRT


# ---------------------------------------------------------------- layered rock

def strata_surface(g, lo, hi, band_lo, band_hi, freq=2.2, thin=1.0, rust=0.0, rust_col=(0.2, 0.08, 0.035), snow=0.0,
                   ice=0.0, lichen=0.0, grooves=1.0, crack=1.0, pits=0.0, scale=1.0):
    """Sedimentary or frost-shattered rock as node signals (color, height, roughness): horizontal bands (`freq` per
    meter, varying in thickness along the rock; `band_lo`/`band_hi` the two tones, `lo`/`hi` the grain), thin dark
    seams between layers, vertical weathering grooves, sand-grain speckle, hairline cracks, optional rust streaks,
    `pits` (wind-carved pockets), lichen, and snow lying on the up-facing ledges (`snow`) with a glaze of ice (`ice`)."""
    co = g.coords()
    x, y, z = g.separate(co)
    warp = g.math("ADD", g.math("MULTIPLY", g.noise(1.3 * scale, detail=3.0), 0.9),
                  g.math("MULTIPLY", g.noise(7.0 * scale, detail=3.0), 0.12))
    zz = g.math("ADD", g.math("MULTIPLY", z, freq), warp)
    band = g.ramp(g.math("SINE", g.math("MULTIPLY", zz, 3.1416 * thin)), -0.6, 0.6)
    seam = g.ramp(g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", zz, 3.1416 * thin))), 0.07, 0.0)
    seam = g.math("MULTIPLY", seam, g.ramp(g.noise(5.0 * scale, detail=3.0), 0.35, 0.6))
    d1, r1 = kf._cells(g, 190.0 * scale, kf._warped(g, 40.0, 0.002))
    grain = g.noise(420.0 * scale, detail=2.0)
    tone = g.noise(2.6 * scale, detail=4.0)
    col = g.mix(band, band_lo, band_hi)
    col = g.mix(g.math("MULTIPLY", g.ramp(tone, 0.35, 0.75), 0.5), col, lo)
    col = g.mix(g.math("MULTIPLY", g.ramp(r1, 0.65, 0.95), 0.35), col, hi)
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.55, 0.9), 0.3), col, tuple(c * 0.4 for c in lo))
    col = g.mix(g.math("MULTIPLY", seam, 0.7), col, tuple(c * 0.25 for c in lo))
    gv = ks._stretched(g, (9.0 * scale, 9.0 * scale, 0.9 * scale))
    gr = g.ramp(kf._ridged(g, g.noise(1.0, detail=4.0, vector=gv)), 0.78, 0.97)
    col = g.mix(g.math("MULTIPLY", gr, 0.4 * grooves), col, tuple(c * 0.35 for c in lo))
    height = g.math("ADD", g.math("MULTIPLY", r1, 0.14), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, gr), 0.3 * grooves))
    height = g.math("ADD", height, g.math("MULTIPLY", band, 0.22))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", seam, 0.35))
    if pits > 0.0:
        pc, _ = kf._cells(g, 5.5 * scale, kf._warped(g, 4.0, 0.08))
        pit = g.math("MULTIPLY", g.ramp(pc, 0.4, 0.15), g.ramp(g.noise(2.0 * scale), 0.45, 0.65))
        pit = g.math("MULTIPLY", pit, pits)
        col = g.mix(g.math("MULTIPLY", pit, 0.6), col, tuple(c * 0.3 for c in lo))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", pit, 0.7))
    if rust > 0.0:
        st = ks._stretched(g, (3.0 * scale, 3.0 * scale, 0.3 * scale))
        rs = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=st), 0.5, 0.72), rust)
        col = g.mix(rs, col, rust_col)
    if crack > 0.0:
        ce = kf._voronoi(g, 0.9 * scale, kf._warped(g, 3.0, 0.12, kf._warped(g, 11.0, 0.03)), feature="DISTANCE_TO_EDGE")
        cr = g.math("MULTIPLY", g.ramp(ce, 0.024, 0.0), g.ramp(g.noise(3.0 * scale), 0.38, 0.55))
        cr = g.math("MULTIPLY", cr, crack)
        col = g.mix(g.math("MULTIPLY", g.ramp(cr, 0.1, 0.9), 0.9), col, (0.01, 0.009, 0.008))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", cr, 0.5))
    rough = g.mixf(g.ramp(grain, 0.4, 0.9), 0.93, 0.82)
    if lichen > 0.0:
        lc, lr = kf._cells(g, 10.0 * scale, kf._warped(g, 6.0, 0.05))
        disc = g.math("MULTIPLY", g.ramp(lc, 0.5, 0.36),
                      g.math("MULTIPLY", g.ramp(lr, 0.45, 0.6), g.ramp(g.noise(2.4 * scale, detail=3.0), 0.5, 0.62)))
        disc = g.math("MULTIPLY", disc, lichen)
        col = g.mix(g.math("MULTIPLY", disc, 0.8), col, g.mix(g.ramp(lr, 0.5, 0.9), (0.2, 0.22, 0.14), (0.4, 0.3, 0.08)))
    if snow > 0.0:
        nz = ks._normal_z(g)
        reach = g.math("ADD", g.math("MULTIPLY", nz, 0.9),
                       g.math("MULTIPLY", g.math("SUBTRACT", g.noise(4.0 * scale, detail=4.0), 0.5), 0.8))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(60.0, detail=3.0), 0.5), 0.1))
        cover = g.ramp(reach, 0.78 - 0.25 * snow, 0.86 - 0.25 * snow)
        sn = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), (0.62, 0.66, 0.72), (0.8, 0.84, 0.9))
        col = g.mix(cover, col, sn)
        height = g.mixf(cover, height, g.math("ADD", 0.55, g.math("MULTIPLY", g.noise(40.0, detail=3.0), 0.2)))
        rough = g.mixf(cover, rough, 0.7)
    if ice > 0.0:
        gl = g.math("MULTIPLY", g.ramp(g.noise(3.0 * scale, detail=4.0), 0.55, 0.7), ice)
        col = g.mix(g.math("MULTIPLY", gl, 0.5), col, (0.35, 0.42, 0.5))
        rough = g.mixf(gl, rough, 0.25)
    col = g.mix(g.math("MULTIPLY", g.ramp(z, G + 0.1, G - 0.05), 0.65), col, (0.02, 0.017, 0.013))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return col, height, rough


def strata(name, relief=0.012, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = strata_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


# Looks used by the formation scripts
def sandstone(name, **kw):
    """Desert red sandstone: warm banded layers, dark seams, sand grain, rust streaks, a little lichen."""
    p = dict(lo=(0.2, 0.085, 0.045), hi=(0.32, 0.15, 0.08), band_lo=(0.17, 0.065, 0.035), band_hi=(0.34, 0.15, 0.075),
             freq=2.0, rust=0.35, rust_col=(0.1, 0.03, 0.015), lichen=0.25, crack=0.8)
    p.update(kw)
    return strata(name, **p)


def slate(name, **kw):
    """Frost-shattered snow-country rock: dark grey-blue, snow on the ledges, a glaze of ice."""
    p = dict(lo=(0.07, 0.075, 0.085), hi=(0.13, 0.14, 0.15), band_lo=(0.06, 0.065, 0.075), band_hi=(0.12, 0.125, 0.135),
             freq=1.2, snow=0.8, ice=0.6, crack=1.0, grooves=0.6)
    p.update(kw)
    return strata(name, **p)


def wasteland(name, **kw):
    """Wind-carved wasteland rock: pale dusty bone-grey with pitted pockets and rust-red streaks."""
    p = dict(lo=(0.28, 0.255, 0.215), hi=(0.38, 0.35, 0.3), band_lo=(0.25, 0.225, 0.19), band_hi=(0.36, 0.33, 0.28),
             freq=1.5, rust=0.55, rust_col=(0.2, 0.075, 0.03), pits=0.9, crack=0.7)
    p.update(kw)
    return strata(name, **p)


# ---------------------------------------------------------------- closed shapes

def _noise(p, seed, size):
    q = p / size + Vector((seed * 5.7, seed * 2.3, seed * 1.1))
    return mn.fractal(q, 0.5, 2.0, 3, noise_basis="PERLIN_ORIGINAL") + 0.4 * mn.noise(q * 4.0)


def _finish(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    return bm


def column(profile, seed=0, sides=28, rough=0.05, ellipse=1.0, yaw=0.0, at=(0.0, 0.0), lean=(0.0, 0.0), sink=SKIRT,
           steps=3, faceted=0.0, base=None):
    """A closed standing rock (hoodoo, spire, wind column, cairn stone): `profile` is [(height above the ground,
    radius)] from the base up (the base is sunk SKIRT deep and flat; the top capped flat, or pointed if its radius is
    0), `steps` rings between profile points, noise on the radius, `ellipse` stretches x, `lean` (dx, dy) shifts the
    top over, `faceted` (0 to 1) pulls the sides toward flat planes (frost-shattered rock). Returns a bmesh."""
    bm = bmesh.new()
    pts = [(G - sink, profile[0][1] * 0.97)] + [(G + h, r) for h, r in profile]
    rings = []
    for (z0, r0), (z1, r1) in zip(pts, pts[1:]):
        n = steps if abs(z1 - z0) > 0.05 else 1
        for k in range(n):
            t = k / n
            rings.append((z0 + (z1 - z0) * t, r0 + (r1 - r0) * t))
    rings.append(pts[-1])
    bottom, top = G - sink, pts[-1][0]
    rot = Matrix.Rotation(math.radians(yaw), 3, "Z")
    m = 6 + int(seed) % 3
    grid = []
    for z, r in rings:
        s = (z - bottom) / max(1e-6, top - bottom)
        ring = []
        for k in range(sides):
            a = k / sides * math.tau
            c, sn = math.cos(a), math.sin(a)
            rr = r
            if faceted > 0.0:
                poly = math.cos(math.pi / m) / math.cos((a % (math.tau / m)) - math.pi / m)
                rr = r * (1.0 - faceted + faceted * poly)
            n_ = _noise(Vector((c * 1.5, sn * 1.5, z * 1.3)), seed, max(0.4, r))
            rr = rr * (1.0 + n_ * rough * 3.0)
            p = rot @ Vector((c * ellipse * rr + lean[0] * s, sn * rr + lean[1] * s, z))
            ring.append(Vector((p.x + at[0], p.y + at[1], p.z)))
        grid.append(ring)
    vr = [[bm.verts.new(p) for p in ring] for ring in grid]
    for i in range(len(vr) - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            bm.faces.new((vr[i][k], vr[i][k1], vr[i + 1][k1], vr[i + 1][k]))
    bot = bm.verts.new(Vector((at[0], at[1], bottom)))
    for k in range(sides):
        bm.faces.new((bot, vr[0][(k + 1) % sides], vr[0][k]))
    tc = sum((v.co for v in vr[-1]), Vector()) / sides
    tv = bm.verts.new(tc)
    for k in range(sides):
        bm.faces.new((tv, vr[-1][k], vr[-1][(k + 1) % sides]))
    return _finish(bm)


def arch(span=4.4, leg=1.6, pier=1.25, depth=2.6, seed=0, sides=20, steps=36, yaw=0.0, rough=0.06, sink=SKIRT):
    """A natural rock arch as a closed tube swept along a path: up the left leg, over a semicircle of radius
    `span / 2` and down the right leg; the cross-section is a rounded rectangle `pier` thick and `depth` deep that
    thins toward the crown. The opening is about `span - pier` wide and `leg + span / 2 - pier / 2` high."""
    bm = bmesh.new()
    R = span / 2.0
    foot = G - sink
    path = []
    legs = max(2, int(steps * 0.2))
    for i in range(legs):
        path.append((-R, foot + (G + leg - foot) * i / legs, -1.0))
    for i in range(steps + 1):
        a = math.pi - math.pi * i / steps
        path.append((R * math.cos(a), G + leg + R * math.sin(a), math.sin(a)))
    for i in range(1, legs + 1):
        path.append((R, G + leg - (G + leg - foot) * i / legs, -1.0))
    n = len(path)
    rings = []
    for idx, (x, z, crown) in enumerate(path):
        a0, a1 = path[max(0, idx - 1)], path[min(n - 1, idx + 1)]
        tan = Vector((a1[0] - a0[0], 0.0, a1[1] - a0[1]))
        tan = tan.normalized() if tan.length > 1e-6 else Vector((0.0, 0.0, 1.0))
        nrm = Vector((-tan.z, 0.0, tan.x))
        s = idx / (n - 1)
        cw = max(0.0, crown)
        t = pier * (1.0 - 0.3 * cw) * (1.0 + 0.16 * math.sin(s * 9.0 + seed))
        d = depth * (1.0 - 0.25 * cw) * (1.0 + 0.1 * math.sin(s * 7.0 + seed * 2.0))
        ring = []
        for k in range(sides):
            ang = k / sides * math.tau
            c, sn = math.cos(ang), math.sin(ang)
            e = 0.5
            cx = math.copysign(abs(c) ** e, c) * t * 0.5
            cy = math.copysign(abs(sn) ** e, sn) * d * 0.5
            q = Vector((x, 0.0, z)) + nrm * cx + Vector((0.0, cy, 0.0))
            k_ = 1.0 + rough * 3.0 * _noise(q, seed, 1.2)
            ring.append(Vector((x, 0.0, z)) + nrm * cx * k_ + Vector((0.0, cy * k_, 0.0)))
        rings.append(ring)
    rot = Matrix.Rotation(math.radians(yaw), 3, "Z")
    vr = [[bm.verts.new(rot @ p) for p in ring] for ring in rings]
    for i in range(len(vr) - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            bm.faces.new((vr[i][k], vr[i + 1][k], vr[i + 1][k1], vr[i][k1]))
    for j, ring in enumerate((vr[0], vr[-1])):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / sides)
        for k in range(sides):
            bm.faces.new((c, ring[k], ring[(k + 1) % sides]) if j == 0 else (c, ring[(k + 1) % sides], ring[k]))
    for v in bm.verts:
        v.co.z = max(v.co.z, foot)
    return _finish(bm)
