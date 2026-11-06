"""Props for the Nature Expanded camps (see campkit.py): cans, bottles, buckets, pots, a pressure lantern, a lawn chair,
a cooler, a rolled tarp, a fish skeleton, a fishing rod, the fire ring and its ashes. Each builds into a ks.Builder and
returns what the caller needs (a Place, collider bodies)."""
import math
import os
import random
import sys

from mathutils import Matrix, Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campkit import *  # noqa: E402,F401,F403
import campkit as ck  # noqa: E402
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G


def profile_t(profile, i):
    """The attribute t (0..1 along the profile by length) that lathe gives profile point i."""
    acc = [0.0]
    for k in range(1, len(profile)):
        acc.append(acc[-1] + math.hypot(profile[k][0] - profile[k - 1][0], profile[k][1] - profile[k - 1][1]))
    return acc[i] / (acc[-1] or 1.0)


def sm(x):
    return ck.smoothstep(0.0, 1.0, x)


# ---------------------------------------------------------------- cans and bottles

def can_profile(kind="open"):
    R = 0.0365 if kind != "tall" else 0.033
    H = 0.108 if kind != "tall" else 0.165
    prof = [(0.0, 0.0), (R * 0.9, 0.0), (R, 0.004), (R, H), (R * 0.97, H + 0.003), (R * 0.93, H + 0.003), (R * 0.93, H - 0.003),
            (R * 0.94, 0.008), (0.0, 0.008)]
    return prof, R, H


def can_band(kind="open"):
    prof, R, H = can_profile(kind)
    return profile_t(prof, 2) + 0.015, profile_t(prof, 3) - 0.015


def can(b, mat, at, yaw, rnd, kind="open", pitch=90.0, crushed=0.0, sink=0.004, roll=0.0):
    """A food can (open top, jagged lid) lying on its side (pitch 90) or standing (pitch 0), crushed by `crushed` 0..1."""
    prof, R, H = can_profile(kind)
    seed = rnd.uniform(0, 10)

    def dent(p):
        q = Vector((p.x * 9.0 + seed, p.y * 9.0, p.z * 9.0))
        f = 1.0 + 0.02 * mn.noise(q)
        if crushed > 0.0:
            f -= crushed * (0.3 + 0.2 * mn.noise(q * 0.6)) * sm(p.z / H) * (1.0 if p.x > 0 else 0.35)
        return Vector((p.x * f, p.y * (1.0 + crushed * 0.3 * sm(p.z / H)), p.z))

    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw, pitch=pitch, roll=roll)
    local = [Vector((0.0, 0.0, 0.0)), Vector((R, 0, 0)), Vector((0, R, 0)), Vector((0, 0, H)), Vector((-R, 0, 0)), Vector((0, -R, 0))]
    pl.rest(local, clearance=-sink)
    lathe(b, mat, prof, pl, sides=16, rnd=rnd, dent=dent, jag=0.004)
    return pl


def bottle(b, mat, at, yaw, rnd, pitch=90.0, broken=False, roll=0.0):
    prof = [(0.0, 0.0), (0.027, 0.0), (0.0315, 0.007), (0.0315, 0.105), (0.0305, 0.128), (0.022, 0.15), (0.0135, 0.172), (0.011, 0.195),
            (0.0105, 0.215), (0.0125, 0.219), (0.0125, 0.227), (0.0095, 0.229), (0.0, 0.2285)]
    top = 0.229
    if broken:
        prof = prof[:5] + [(0.0305, 0.118), (0.029, 0.118), (0.029, 0.012), (0.0, 0.012)]
        top = 0.12
    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw, pitch=pitch, roll=roll)
    local = [Vector((0, 0, 0)), Vector((0.0315, 0, 0)), Vector((-0.0315, 0, 0)), Vector((0, 0.0315, 0)), Vector((0, -0.0315, 0)), Vector((0, 0, top))]
    pl.rest(local, clearance=-0.004)
    lathe(b, mat, prof, pl, sides=14, rnd=rnd, jag=0.006 if broken else 0.0)
    return pl


# ---------------------------------------------------------------- bucket and pot

def bucket_profile():
    return [(0.0, 0.0), (0.108, 0.0), (0.115, 0.012), (0.15, 0.29), (0.157, 0.296), (0.153, 0.306), (0.145, 0.302), (0.142, 0.285),
            (0.108, 0.022), (0.0, 0.022)]


def bucket(b, mat, at, yaw, rnd, pitch=0.0, roll=0.0, bail_tilt=70.0, dents=1.0, sink=0.0, handle=True):
    """A galvanized bucket gone to rust (inside floor at z 0.022), a bail handle across it flopped by bail_tilt degrees."""
    prof = bucket_profile()
    seed = rnd.uniform(0, 10)

    def dent(p):
        q = Vector((p.x * 6.0 + seed, p.y * 6.0, p.z * 5.0))
        f = 1.0 + dents * (0.025 * mn.noise(q) + 0.05 * max(0.0, mn.noise(q * 0.5 + Vector((9, 3, 1))) - 0.15) * sm(p.z / 0.3))
        return Vector((p.x * f, p.y * f, p.z))

    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw, pitch=pitch, roll=roll)
    local = [Vector((0, 0, 0)), Vector((0.15, 0, 0.3)), Vector((-0.15, 0, 0.3)), Vector((0, 0.15, 0.3)), Vector((0, -0.15, 0.3)),
             Vector((0.11, 0, 0)), Vector((-0.11, 0, 0)), Vector((0, 0.11, 0)), Vector((0, -0.11, 0))]
    pl.rest(local, clearance=-sink)
    lathe(b, mat, prof, pl, sides=22, rnd=rnd, dent=dent)
    if handle:
        pts = []
        tl = math.radians(bail_tilt)
        for k in range(15):
            a = k / 14 * math.pi
            h = 0.17 * math.sin(a)
            pts.append(pl(Vector((0.153 * math.cos(a), -math.sin(tl) * h, 0.275 + math.cos(tl) * h))))
        wire(b, mat, pts, 0.0035, sides=4, cap=True)
    return pl


def pot_profile():
    return [(0.0, 0.0), (0.103, 0.0), (0.113, 0.012), (0.116, 0.14), (0.121, 0.147), (0.119, 0.154), (0.112, 0.15), (0.109, 0.14),
            (0.101, 0.016), (0.0, 0.016)]


def pot(b, mat, wire_mat, at, yaw, rnd, pitch=90.0, roll=0.0, sink=0.01, bail=True, dents=1.0):
    prof = pot_profile()
    seed = rnd.uniform(0, 10)

    def dent(p):
        q = Vector((p.x * 8.0 + seed, p.y * 8.0, p.z * 8.0))
        f = 1.0 + dents * 0.03 * mn.noise(q)
        return Vector((p.x * f, p.y * f, p.z))

    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw, pitch=pitch, roll=roll)
    local = [Vector((0, 0, 0)), Vector((0.12, 0, 0.15)), Vector((-0.12, 0, 0.15)), Vector((0, 0.12, 0.15)), Vector((0, -0.12, 0.15)),
             Vector((0.11, 0, 0)), Vector((-0.11, 0, 0))]
    pl.rest(local, clearance=-sink)
    lathe(b, mat, prof, pl, sides=22, rnd=rnd, dent=dent)
    for sx in (-1, 1):
        ear = [pl(Vector((sx * 0.118, 0.0, 0.128))), pl(Vector((sx * 0.14, 0.0, 0.132))), pl(Vector((sx * 0.14, 0.0, 0.112))),
               pl(Vector((sx * 0.118, 0.0, 0.108)))]
        wire(b, wire_mat, ear, 0.0045, sides=4, cap=True)
    if bail:
        pts = []
        for k in range(13):
            a = k / 12 * math.pi
            pts.append(pl(Vector((0.13 * math.cos(a), -0.1 * math.sin(a), 0.125 + 0.035 * math.sin(a)))))
        wire(b, wire_mat, pts, 0.0035, sides=4, cap=True)
    return pl


def ring(b, mat, center, normal, radius, tube_r, sides=4, n=10):
    """A small metal ring (a rod guide, a grommet) in the plane square to `normal`."""
    nx, u, v = ks.basis(normal)
    pts = [Vector(center) + (u * math.cos(k / n * math.tau) + v * math.sin(k / n * math.tau)) * radius for k in range(n + 1)]
    ks.tube(b, mat, pts, [tube_r] * len(pts), sides=sides, cap=False)


# ---------------------------------------------------------------- lantern

def lantern(b, paint, metal, glass, at, yaw, rnd, pitch=0.0):
    """A dead pressure lantern: green tank, cloudy globe with a pane missing and a ragged rim, vented cap, rod cage and bail.
    Stands on `at` (x, y, z absolute)."""
    pl = Place(at=(at[0], at[1], at[2] if len(at) > 2 else G), yaw=yaw, pitch=pitch)
    tank = [(0.0, 0.0), (0.072, 0.0), (0.085, 0.012), (0.087, 0.07), (0.075, 0.095), (0.05, 0.103), (0.03, 0.108), (0.0, 0.108)]
    lathe(b, paint, tank, pl, sides=22, rnd=rnd)
    lathe(b, metal, [(0.032, 0.105), (0.03, 0.125), (0.022, 0.13), (0.0, 0.13)], pl, sides=12, rnd=rnd)
    globe = [(0.05, 0.12), (0.062, 0.14), (0.07, 0.19), (0.062, 0.24), (0.05, 0.268), (0.044, 0.285)]
    lathe(b, glass, globe, pl, sides=18, rnd=rnd, jag=0.006, sweep=math.radians(290), start_angle=math.radians(rnd.uniform(0, 360)))
    cap = [(0.048, 0.285), (0.06, 0.288), (0.085, 0.3), (0.088, 0.31), (0.07, 0.325), (0.04, 0.335), (0.0, 0.34)]
    lathe(b, paint, cap, pl, sides=22, rnd=rnd)
    lathe(b, metal, [(0.02, 0.338), (0.02, 0.36), (0.0, 0.362)], pl, sides=8, rnd=rnd)
    for k in range(4):
        a = k / 4 * math.tau + 0.4
        wire(b, metal, [pl(Vector((0.072 * math.cos(a), 0.072 * math.sin(a), 0.1))), pl(Vector((0.068 * math.cos(a), 0.068 * math.sin(a), 0.2))),
                        pl(Vector((0.078 * math.cos(a), 0.078 * math.sin(a), 0.292)))], 0.0028, sides=4, cap=True)
    pts = []
    for k in range(13):
        a = k / 12 * math.pi
        pts.append(pl(Vector((0.082 * math.cos(a), 0.0, 0.31 + 0.075 * math.sin(a)))))
    wire(b, metal, pts, 0.0035, sides=4, cap=True)
    return pl


# ---------------------------------------------------------------- the lawn chair

def webbing_strip(b, mat, p0, p1, sag, rnd, up, width=0.04, n=9, broken=None):
    """A strap from p0 to p1 sagging `sag` along -up. `broken` (0..1 along it): it ends there and frays into strands."""
    p0, p1 = Vector(p0), Vector(p1)
    stop = 1.0 if broken is None else broken
    dn = Vector(up).normalized()
    m = max(2, int(n * stop))
    pts = []
    for k in range(m + 1):
        s = stop * k / m
        q = p0.lerp(p1, s) - dn * (sag * math.sin(math.pi * s) if broken is None else sag * math.sin(math.pi * s * 0.9) + 0.06 * (s ** 3) * 0.0)
        pts.append(q)
    if broken is not None:
        end = pts[-1]
        along = (p1 - p0).normalized()
        for k in range(3):
            d = Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0.0)) + along * 0.8 - dn * rnd.uniform(0.2, 0.8)
            d.normalize()
            ln = rnd.uniform(0.04, 0.14)
            sub = [end + d * (ln * f) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.004 for f in (0.0, 0.5, 1.0)]
            sub[0] = end.copy()
            ribbon(b, mat, sub, [width * 0.33, width * 0.25, width * 0.12], up=up)
        ws = [width] * (len(pts) - 1) + [width * 0.8]
        ribbon(b, mat, pts, ws, up=up)
    else:
        ribbon(b, mat, pts, width, up=up)


def _chair_tubes():
    V = Vector
    W = 0.25
    tubes = []
    for sx in (-W, W):
        tubes.append(([V((sx, 0.27, 0.0)), V((sx, 0.245, 0.3)), V((sx, 0.2, 0.57)), V((sx, -0.02, 0.62)), V((sx, -0.27, 0.585))], 0.0125))
        tubes.append(([V((sx, -0.33, 0.0)), V((sx, -0.285, 0.29)), V((sx, -0.31, 0.5)), V((sx, -0.37, 0.84))], 0.0125))
        tubes.append(([V((sx, 0.245, 0.3)), V((sx, -0.1, 0.3)), V((sx, -0.285, 0.29))], 0.011))
    for yy, zz in ((0.245, 0.3), (-0.285, 0.29), (-0.37, 0.84), (-0.31, 0.5)):
        tubes.append(([V((-W, yy, zz)), V((W, yy, zz))], 0.011))
    return tubes


def chair_points():
    return [p for pts, _ in _chair_tubes() for p in pts]


def alu_chair(b, frame, web, pl, rnd, broken=0.3, sag=0.06):
    """A folding lawn chair of aluminum tube and webbing, seat 0.3 m up. Local frame: x across, +y front, z up; the Place
    `pl` stands it (rest it with chair_points()). Webbing straps may be snapped and frayed."""
    V = Vector
    W = 0.25
    for pts, r in _chair_tubes():
        wire(b, frame, [pl(p) for p in pts], r, sides=6, cap=True)
    nseat = 8
    for i in range(nseat):
        y = 0.215 - i * (0.5 / (nseat - 1))
        z = 0.3 - 0.01 * (0.245 - y) / 0.53 + 0.012
        br = rnd.uniform(0.35, 0.8) if rnd.random() < broken else None
        a, c = V((-W, y, z)), V((W, y, z))
        if br is not None and rnd.random() < 0.5:
            a, c = c, a
        webbing_strip(b, web, pl(a), pl(c), sag * (1.0 + 0.4 * rnd.random()), rnd, pl.dir(V((0, 0, 1))), width=0.04, n=9, broken=br)
    nb = 6
    for i in range(nb):
        h = 0.45 + i * (0.36 / (nb - 1))
        y = -0.31 - 0.07 * (h - 0.5) / 0.34
        if rnd.random() < broken * 0.6:
            continue
        br = rnd.uniform(0.3, 0.7) if rnd.random() < broken else None
        a, c = V((-W, y, h)), V((W, y, h))
        if br is not None and rnd.random() < 0.5:
            a, c = c, a
        webbing_strip(b, web, pl(a), pl(c), sag * 0.7, rnd, pl.dir(V((0, 1, 0.12))), width=0.04, n=9, broken=br)


# ---------------------------------------------------------------- cooler, rolled tarp

def cooler(b, body, lid, at, yaw, rnd, tip=6.0, lid_angle=245.0, handle=None):
    """A molded cooler lying on the ground, open, its lid swung back. Returns (Place, lid Place)."""
    hx, hy, H = 0.31, 0.2, 0.36
    prof = [(0.0, 0.0), (0.93, 0.0), (0.985, 0.02), (1.0, 0.06), (1.0, H - 0.04), (0.99, H - 0.012), (0.955, H), (0.925, H),
            (0.915, H - 0.015), (0.9, H - 0.02), (0.9, 0.05), (0.88, 0.035), (0.0, 0.035)]
    seed = rnd.uniform(0, 10)

    def dent(p):
        q = Vector((p.x * 5.0 + seed, p.y * 5.0, p.z * 5.0))
        f = 1.0 + 0.012 * mn.noise(q) + 0.02 * max(0.0, mn.noise(q * 0.4 + Vector((4, 1, 2))))
        return Vector((p.x * f, p.y * f, p.z))

    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw, roll=tip)
    local = [Vector((sx * hx, sy * hy, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, H)]
    pl.rest(local, clearance=-0.012)
    lathe(b, body, prof, pl, sides=56, rnd=rnd, dent=dent, shape=(hx, hy, 6.0))
    hinge = pl.child(at=(0.0, -hy, H), roll=lid_angle)
    lprof = [(0.0, 0.06), (0.93, 0.06), (0.99, 0.045), (1.0, 0.0), (0.935, 0.0), (0.93, 0.012), (0.0, 0.03)]
    lp = hinge.child(at=(0.0, hy, 0.0))
    lathe(b, lid, lprof, lp, sides=56, rnd=rnd, shape=(hx, hy, 6.0))
    if handle is not None:
        for sx in (-1, 1):
            pts = [pl(Vector((sx * hx * 0.99, -0.05, 0.28))), pl(Vector((sx * (hx + 0.045), -0.05, 0.285))),
                   pl(Vector((sx * (hx + 0.05), 0.05, 0.285))), pl(Vector((sx * hx * 0.99, 0.05, 0.28)))]
            wire(b, handle, pts, 0.01, sides=5, cap=True)
    return pl, lp


def rolled(b, mat, rope, at, yaw, rnd, length=0.9, r0=0.03, turns=4.5, pitch_r=0.0042, sink=0.01, ties=2, rope_r=0.006):
    """A tarp rolled up and tied: a spiral of double-sided sheet seen end-on, lying on the ground along `yaw`."""
    spins = int(turns * 30)
    outer = r0 + pitch_r * turns
    pl = Place(at=(at[0], at[1], 0.0), yaw=yaw)
    pl.rest([Vector((0, 0, -outer)), Vector((0, 0, outer))], clearance=-sink)
    shift = [rnd.uniform(-0.012, 0.012) for _ in range(spins + 1)]
    ph = rnd.uniform(0, math.tau)

    def fn(i, j):
        th = i / 30.0 * math.tau
        r = r0 + pitch_r * th / math.tau
        x = (j / 2.0 - 0.5) * length + shift[i] * (1.0 if j else -1.0)
        return pl(Vector((x, r * math.cos(th + ph), r * math.sin(th + ph))))

    ck.cloth(b, mat, fn, spins, 2, sgn=1.0, thick=0.0025)
    for tx in (-0.22 * length, 0.2 * length)[:ties]:
        pts = [pl(Vector((tx + 0.003 * k / 12, (outer + 0.004) * math.cos(k / 12 * math.tau), (outer + 0.004) * math.sin(k / 12 * math.tau))))
               for k in range(13)]
        wire(b, rope, pts, rope_r, sides=4, cap=True)
        tail = [pts[-1], pts[-1] + pl.dir(Vector((0.02, 0.0, 0.0))) + Vector((0, 0, 0.02)), pts[-1] + pl.dir(Vector((0.05, 0.03, 0.0)))]
        tail[-1].z = max(tail[-1].z, G + 0.01)
        wire(b, rope, tail, rope_r * 0.9, sides=4, cap=True)
    return pl


# ---------------------------------------------------------------- bones

def fish_bones(b, mat, at, yaw, rnd, size=1.0, z=G + 0.02, pitch=0.0, roll=0.0, skull=True):
    """A fish skeleton (skull, spine, rib pairs, tail fan), about 0.3 m x size long, lying flat or at `pitch`/`roll`."""
    pl = Place(at=(at[0], at[1], z), yaw=yaw, pitch=pitch, roll=roll)
    L = 0.3 * size
    spine = [pl(Vector((-L * 0.5 + L * k / 8, 0.012 * math.sin(k * 0.8) * size, 0.0))) for k in range(9)]
    tapered(b, mat, spine, 0.0035 * size, 0.0016 * size, sides=5, cap=True)
    for k in range(1, 8):
        x = -L * 0.5 + L * k / 8
        rl = 0.07 * size * (1.0 - abs(k - 3) / 6.0)
        for sy in (-1, 1):
            if rnd.random() < 0.18:
                continue
            pts = [pl(Vector((x + 0.01 * j, sy * rl * math.sin(j * 0.52), -0.004 * j + rl * 0.25 * math.sin(j * 0.52)))) for j in range(4)]
            tapered(b, mat, pts, 0.0017 * size, 0.0007 * size, sides=3, cap=True)
    tail = pl(Vector((L * 0.5, 0.0, 0.0)))
    for q in range(5):
        a = (q - 2) * 0.28
        pts = [tail, tail + pl.dir(Vector((math.cos(a) * 0.035 * size, math.sin(a) * 0.035 * size, 0.0))),
               tail + pl.dir(Vector((math.cos(a) * 0.065 * size, math.sin(a) * 0.065 * size, 0.0)))]
        tapered(b, mat, pts, 0.0011 * size, 0.0004 * size, sides=3, cap=True)
    if skull:
        c = pl(Vector((-L * 0.5 - 0.03 * size, 0.0, 0.004)))
        hd = pl.dir(Vector((1, 0, 0)))
        bm = fk.Rock(radii=(0.034 * size, 0.017 * size, 0.017 * size), height=0.03 * size, seed=int(rnd.uniform(1, 99)), power=2.2,
                     rough=0.12, yaw=math.degrees(math.atan2(hd.y, hd.x)), at=(c.x, c.y), subdiv=2, sink=0.1).build()
        for v in bm.verts:
            v.co.z += (c.z - G) - 0.004
        fk.emit_rock(b, bm, mat, mat)
        b.lod = 0
        bm.free()
    return pl


# ---------------------------------------------------------------- the fire ring

def fire_ring(b, stone, skirt, rnd, bodies, center, radius=0.43, n=9, size=(0.11, 0.17), seed=20):
    """A ring of low field stones, flat-faced toward the fire; returns nothing, bodies get each stone's mesh."""
    cx, cy = center
    for i in range(n):
        a = i / n * math.tau + rnd.uniform(-0.12, 0.12)
        rr = radius + rnd.uniform(-0.04, 0.04)
        r = rnd.uniform(*size)
        planes = [((math.cos(a), math.sin(a), rnd.uniform(-0.2, 0.3)), r * rnd.uniform(0.68, 0.85)),
                  ((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.5, 1.0)), r * rnd.uniform(0.5, 0.65)),
                  ((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.0, 0.6)), r * rnd.uniform(0.8, 1.0))]
        bm = fk.Rock(radii=(r * rnd.uniform(1.0, 1.4), r, r * rnd.uniform(0.7, 1.0)), height=rnd.uniform(0.1, 0.19), seed=seed + i,
                     power=3.1, rough=0.13, yaw=math.degrees(a) + rnd.uniform(-30, 30), at=(cx + rr * math.cos(a), cy + rr * math.sin(a)),
                     subdiv=3 if r > 0.13 else 2, sink=0.12, planes=planes).build()
        bodies.append(fk.emit_rock(b, bm, stone, skirt))
        bm.free()
    b.lod = 0


def fire_bed(b, ash, wood, char_end, rnd, center, radius=0.4, sticks=7, lumps=16):
    """Ash, charred sticks and a half-burnt log end, charcoal lumps: a cold fire."""
    cx, cy = center
    ks.ground_patch(b, ash, (cx, cy), radius, rnd, sides=16, dome=0.016, jitter=0.22, sink=0.003, rings=3)
    ks.ground_patch(b, ash, (cx + 0.05 * radius / 0.4, cy - 0.03), radius * 0.55, rnd, sides=12, dome=0.026, jitter=0.3, sink=0.0, rings=2)
    for i in range(sticks):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0.0, radius * 0.65)
        p = Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), G + 0.03))
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.0, 0.25))).normalized()
        ln = rnd.uniform(0.18, 0.5) * (radius / 0.4)
        rad = rnd.uniform(0.014, 0.036)
        pts = [p + d * (ln * f) for f in (0.0, 0.34, 0.67, 1.0)]
        for q in pts:
            q.z = max(G + 0.012, q.z)
        lk.tube_broken(b, wood.get("char", d), char_end, pts, [rad, rad * 0.95, rad * 0.88, rad * 0.8], 6, rnd, jag=1.0)
    p = Vector((cx - 0.06, cy + 0.1, G + 0.05))
    d = Vector((0.8, -0.5, 0.1)).normalized()
    lk.tube_broken(b, wood.get("char", d), char_end, [p, p + d * 0.16, p + d * 0.34], [0.05, 0.048, 0.044], 8, rnd, jag=0.9)
    cm = wood.get("char", Vector((1, 0, 0)))
    for i in range(lumps):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0.0, radius * 0.82)
        sz = rnd.uniform(0.012, 0.03)
        bm = fk.Rock(radii=(sz * 1.4, sz, sz * 0.6), height=sz * 1.2, seed=100 + i, power=2.3, rough=0.2, yaw=rnd.uniform(0, 360),
                     at=(cx + rr * math.cos(a), cy + rr * math.sin(a)), subdiv=1, sink=0.01).build()
        fk.emit_rock(b, bm, cm, cm)
        bm.free()
    b.lod = 0
