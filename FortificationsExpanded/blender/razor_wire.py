"""Razor-Wire Coil (Fortifications Expanded): a 1 m concertina coil on two steel pickets. One baked-by-numpy atlas,
`RazorWire` (RazorWire_Albedo.png, RazorWire_Normal.png, RazorWire_RMOM.png, 2048).

    RazorWireSection.fbx   1 m piece along X: DMG0 taut, DMG1 sagging and stretched, DMG2 a tangled heap on the ground,
                           plus an empty FX in the middle of the front face at mid-height
    RazorWireCorner.fbx    a picket at the origin and half-length coils running to +X and +Y (end pickets at 0.46),
                           the same three stages

Section: seven turns of a real helix (radius 0.46 m, pitch 1/7 m, axis along X at y = 0, 3 cm off the ground, so the
whole piece is under 1.0 m) of 5.6 mm steel wire with razor barbs clipped on every 6.5 cm (flat spikes in pairs, rolled
at random round the wire), two studded T-post pickets 0.99 m tall inside the coil at x = +-0.46 and wire ties round
them. The helix has the same phase at both ends, so neighbouring sections' wires meet. Sagging: the loops slump and
flatten in the middle, the pitch stretches, one wire snaps and curls back, one picket leans. Heap: the same wire in
tangled knots on the ground (under 0.4 m), one picket leaning at 35 degrees and one lying on the ground.

Atlas: the wire runs down narrow columns (v along its length: grey steel, sheen, rust bloom in patches), the barbs
share a steel swatch, the pickets lie on graded crops of the green-paint and rusty-paint photo sets.

    blender -b --factory-startup --python razor_wire.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default), export (no renders).
"""
import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402
import wallkit as wk  # noqa: E402
from wallkit import Z0, fbm, m_r, m_t, smoothstep, unit  # noqa: E402

wk.TAG = "razor"
log = wk.log

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

N = 2048
MAT = "RazorWire"
R_COIL = 0.46
PITCH = 1.0 / 7.0
WIRE_R = 0.0028
CLEAR = 0.03
ZC = Z0 + CLEAR + R_COIL  # coil axis height
PICKET_TOP = 0.99
PX = 0.46
BARB_SPACING = 0.065
BARB_LEN = 0.021
BARB_HALF = 0.0065

# ---------------------------------------------------------------- the atlas

WIRE_COLS = 8  # 20 px wide columns, the full height
COL_W = 20
BLADE = (176, 0, 256, 256)  # x, y, w, h
PICKET_X = (300, 580)
PICKET_W, PICKET_H = 250, 900
PX_PER_M = 700.0


def paint_atlas():
    rng = np.random.default_rng(4410)
    A = wk.Atlas(N)
    # wire columns: grey steel with long rust blooms, sheen between them
    for k in range(WIRE_COLS):
        h, w = N, COL_W
        tone = fbm(h, w, 60, 1, rng, 4)
        steel = np.empty((h, w, 3), np.float32)
        base = 0.36 + 0.08 * (fbm(h, w, 9, 1, rng, 3) - 0.5)
        steel[...] = (base * (0.94 + 0.12 * tone))[..., None] * np.array([0.98, 1.0, 1.03])[None, None, :]
        bloom = smoothstep(0.52, 0.7, fbm(h, w, 22 + 3 * k, 1, rng, 5)) * smoothstep(0.35, 0.8, fbm(h, w, 7, 2, rng, 3))
        spots = smoothstep(0.68, 0.8, fbm(h, w, 160, 3, rng, 3)) * 0.8
        rust = np.clip(bloom * 1.1 + spots, 0, 1)
        rtone = fbm(h, w, 80, 2, rng, 3)
        rust_col = (np.array([0.40, 0.18, 0.075]) * (1 - rtone)[..., None] + np.array([0.24, 0.1, 0.045]) *
                    rtone[..., None])
        col = steel + (rust_col - steel) * rust[..., None]
        grime = smoothstep(0.55, 0.8, fbm(h, w, 14, 1, rng, 4)) * 0.4
        col = col + (col * 0.55 - col) * grime[..., None]
        rough = 0.36 + 0.12 * tone
        rough = rough + (0.9 - rough) * rust
        metal = 0.88 * (1.0 - rust * 0.9)
        height = rust * fbm(h, w, 240, 3, rng, 3) * 4.0 + tone
        A.paste(k * COL_W, 0, col, height, rough, metal, nstrength=3.0, gutter=1)
    # blade swatch: brighter steel, rust creeping in from the base and the edges
    bx, by, bw, bh = BLADE
    v = (np.arange(bh)[:, None] / bh) * np.ones((1, bw))
    u = np.abs(np.arange(bw)[None, :] / bw - 0.5) * 2
    tone = fbm(bh, bw, 6, 6, rng, 4)
    steel = np.array([0.5, 0.51, 0.52])[None, None, :] * (0.85 + 0.3 * tone)[..., None]
    rmask = np.clip(smoothstep(0.55, 0.0, v) * 1.2 + smoothstep(0.5, 0.95, u) * 0.4 +
                    smoothstep(0.55, 0.75, fbm(bh, bw, 8, 8, rng, 4)) * 0.8, 0, 1)
    rust_col = np.array([0.34, 0.15, 0.06])[None, None, :] * (0.7 + 0.5 * fbm(bh, bw, 20, 20, rng, 3))[..., None]
    col = steel + (rust_col - steel) * rmask[..., None]
    A.paste(bx, by, col, rmask * fbm(bh, bw, 40, 40, rng, 3), 0.45 + 0.4 * rmask, 0.85 * (1 - rmask), nstrength=2.0)
    # pickets: green enamel worn through to rust, graded down to the muted values of vanilla metal
    for i, px in enumerate(PICKET_X):
        off = (211 * (i + 1) % 1500, 311 * (i + 2) % 1500)
        green = wk.photo("green_metal_rust", "diff")
        rusty = wk.photo("rusty_painted_metal", "diff")
        a = wk.grade(wk.crop(green, off[0], off[1], PICKET_W, PICKET_H), sat=0.62, value=0.62, contrast=1.1)
        b = wk.grade(wk.crop(rusty, off[1], off[0], PICKET_W, PICKET_H), sat=0.7, value=0.7, contrast=1.1)
        wear = smoothstep(0.45, 0.7, fbm(PICKET_H, PICKET_W, 5, 2, rng, 5))
        wear = np.maximum(wear, smoothstep(0.62, 0.75, fbm(PICKET_H, PICKET_W, 60, 14, rng, 3)) * 0.7)
        col = a + (b - a) * wear[..., None]
        dirt = smoothstep(0.55, 0.8, fbm(PICKET_H, PICKET_W, 9, 3, rng, 4)) * 0.35
        # more grime and soil toward the foot
        foot = smoothstep(260, 0, np.arange(PICKET_H))[:, None] * np.ones((1, PICKET_W))
        dirt = np.clip(dirt + foot * 0.55, 0, 1)
        col = col + (np.array([0.075, 0.062, 0.05])[None, None, :] - col) * dirt[..., None]
        hmap = wk.crop(wk.photo("green_metal_rust", "disp"), off[0], off[1], PICKET_W, PICKET_H)
        rough = 0.5 + 0.35 * wear + 0.2 * dirt
        metal = 0.55 * (1 - dirt) * (0.3 + 0.7 * wear)
        A.paste(px, 0, col, hmap * 3.0, np.clip(rough, 0, 1), metal, ao=1.0, nstrength=2.5)
    return A


A = None


def wire_uv(k, margin=2):
    return ((k * COL_W + 2) / N, 2 / N, (k * COL_W + COL_W - 2) / N, (N - 2) / N)


# ---------------------------------------------------------------- parts

def barbs(g, P, rnd, spacing=BARB_SPACING, skip=(), tag="barb"):
    """Razor barbs clipped on a wire path: pairs of flat spikes every `spacing` metres along the path, rolled at random
    round the wire."""
    P = np.asarray(P, float)
    T, Nn, Bn = wk.frames(P)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    s = rnd.uniform(0.0, spacing)
    bx, by, bw, bh = BLADE
    ua, ub, um = (bx + 14) / N, (bx + bw - 14) / N, (bx + bw / 2) / N
    va, vb = (by + 14) / N, (by + bh - 14) / N
    base_roll = rnd.uniform(0, 2 * math.pi)
    while s < cum[-1]:
        i = min(int(np.searchsorted(cum, s, side="right")) - 1, len(P) - 2)
        f = (s - cum[i]) / max(seg[i], 1e-9)
        p = P[i] + (P[i + 1] - P[i]) * f
        t = unit(T[i] * (1 - f) + T[i + 1] * f)
        n_ = unit(Nn[i] * (1 - f) + Nn[i + 1] * f)
        b_ = np.cross(t, n_)
        if not any(a <= s <= b for a, b in skip):
            roll = base_roll + s * 37.0 + rnd.uniform(-0.8, 0.8)
            for sign in (1.0, -1.0):
                d = (math.cos(roll) * n_ + math.sin(roll) * b_) * sign
                tilt = rnd.uniform(-0.004, 0.004)
                ln = BARB_LEN * rnd.uniform(0.85, 1.1)
                p1, p2 = p - t * BARB_HALF, p + t * BARB_HALF
                tip = p + d * ln + t * tilt
                g.tri(p1, p2, tip, (ua, va), (ub, va), (um, vb), tag)
                g.tri(p2, p1, tip, (ub, va), (ua, va), (um, vb), tag)
        s += spacing * rnd.uniform(0.85, 1.15)
    return g


def helix_path(x0, x1, turns, phase0, per_turn=28, R=R_COIL, zc=ZC, rscale=None, squash=None, wobble=None):
    n = int(round(turns * per_turn))
    pts = []
    for i in range(n + 1):
        t = i / n
        ph = phase0 + 2 * math.pi * turns * t
        r = R * (1.0 if rscale is None else rscale(t))
        sq = 1.0 if squash is None else squash(t)
        x = x0 + (x1 - x0) * t
        y, z = r * math.cos(ph), zc + r * math.sin(ph) * sq
        if wobble is not None:
            dx, dy, dz = wobble(t, ph)
            x, y, z = x + dx, y + dy, z + dz
        pts.append((x, y, z))
    return np.array(pts)


def wire(g, P, column, rnd, with_barbs=True, radius=WIRE_R, skip=()):
    g.tube(P, radius, 4, wire_uv(column), caps=(True, True), tag="wire", phase=0.5)
    if with_barbs:
        barbs(g, P, rnd, skip=skip)


def curl_end(P, end, rnd, turns=1.3, r0=0.045, outward=0.0):
    """A snapped wire end: sprung into a small coil that continues the path's direction."""
    P = np.asarray(P, float)
    p = P[-1] if end else P[0]
    d = unit(P[-1] - P[-2]) if end else unit(P[0] - P[1])
    side = unit(np.cross(d, [0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.cross(d, [1.0, 0.0, 0.0]))
    up = np.cross(d, side)
    ph0 = rnd.uniform(0, 6.28)
    pts = []
    n = 12
    for i in range(1, n + 1):
        t = i / n
        a = ph0 + 2 * math.pi * turns * t
        r = r0 * (1.0 - 0.45 * t)
        pts.append(p + d * (0.12 * t) + r * (math.cos(a) * side + math.sin(a) * up) - r * (math.cos(ph0) * side
                                                                                       + math.sin(ph0) * up))
    pts = np.array(pts)
    return np.concatenate([P, pts]) if end else np.concatenate([pts[::-1], P])


def picket(rnd, column, top=PICKET_TOP, tag="picket"):
    """A studded T-post with its base at the origin (z = Z0), 1 m (top) above the ground."""
    g = wk.Geo()
    prof = [(-0.02, -0.02), (0.02, -0.02), (0.02, -0.014), (0.003, -0.014), (0.003, 0.02), (-0.003, 0.02),
            (-0.003, -0.014), (-0.02, -0.014)]
    # (u offset in px, width in px) per edge of the profile along the swatch row
    lens = [math.hypot(prof[(k + 1) % 8][0] - prof[k][0], prof[(k + 1) % 8][1] - prof[k][1]) for k in range(8)]
    offs = np.concatenate([[0], np.cumsum(lens)]) * PX_PER_M
    x0 = PICKET_X[column] + 4

    def uvfn(k, s, z, w):
        return ((x0 + offs[k] + s * w * PX_PER_M) / N, (4 + (z - Z0) * PX_PER_M) / N)
    g.prism(prof, Z0 - 0.0, Z0 + top, uvfn, tag)
    # studs along the stem, both sides, and the anchor plate near the ground
    z = Z0 + 0.28
    while z < Z0 + top - 0.08:
        for sx in (-1, 1):
            xs, ys = 0.003 * sx, 0.012
            c = [(xs, ys - 0.005, z - 0.005), (xs, ys + 0.005, z - 0.005), (xs, ys + 0.005, z + 0.005),
                 (xs, ys - 0.005, z + 0.005)]
            tip = (xs + 0.005 * sx, ys, z)
            order = c if sx > 0 else list(reversed(c))
            uc = (x0 + 20) / N, (4 + (z - Z0) * PX_PER_M) / N
            for a, b in zip(order, order[1:] + order[:1]):
                g.tri(a, b, tip, uc, uc, uc, tag)
        z += 0.072
    plate = [(-0.04, 0.0, Z0 + 0.06), (0.04, 0.0, Z0 + 0.06), (0.025, 0.0, Z0 + 0.13), (-0.025, 0.0, Z0 + 0.13)]
    uc = (x0 + 60) / N, (4 + 0.08 * PX_PER_M) / N
    for a, b, c_ in ((plate[0], plate[1], plate[2]), (plate[0], plate[2], plate[3])):
        g.tri(a, b, c_, uc, uc, uc, tag)
        g.tri(b, a, c_, uc, uc, uc, tag)
    return g


def place_picket(g, pk, x, y, lean=(0.0, 0.0), yaw=0.0):
    """pk (built at the origin, bottom z = Z0) placed at (x, y) on the ground, leaning (about X, about Y in degrees),
    turned by yaw about Z."""
    M = (m_t(x, y, Z0) @ m_r("Z", yaw) @ m_r("X", lean[0]) @ m_r("Y", lean[1]) @ m_t(0, 0, -Z0))
    g.merge(pk, M)


def tie(g, x, y, z, rnd, column=7, r=0.029):
    """A twisted wire tie round a picket."""
    pts = []
    n = 14
    for i in range(n + 1):
        a = 2 * math.pi * 1.15 * i / n + rnd.uniform(0, 0.2)
        pts.append((x + r * math.cos(a), y + r * 0.8 * math.sin(a), z + 0.004 * i / n))
    p = np.array(pts)
    tail = [p[-1] + np.array([0.012, 0.01, 0.0]) * k * 2 + np.array([0, 0, rnd.uniform(-0.004, 0.004)]) for k in (1, 2, 3)]
    g.tube(np.concatenate([p, np.array(tail)]), 0.0017, 3, wire_uv(column), caps=(True, True), tag="tie", phase=0.5)


# ---------------------------------------------------------------- the pieces

def section(stage, seed):
    rnd = random.Random(seed)
    g = wk.Geo()
    if stage == 0:
        phase = 0.0
        P = helix_path(-0.5, 0.5, 7, phase, per_turn=22,
                       rscale=lambda t: 1.0 + 0.025 * math.sin(2 * math.pi * 2.3 * t + seed),
                       wobble=lambda t, ph: (0.012 * math.sin(2 * math.pi * 3 * t + 1.0) * math.sin(math.pi * t), 0.0,
                                            0.006 * math.sin(math.pi * t * 7)))
        wire(g, P, 0, rnd)
        pk = [place_picket(g, picket(rnd, 0), -PX, 0.0, (0, 0), rnd.uniform(0, 360)),
              place_picket(g, picket(rnd, 1), PX, 0.0, (0.0, 0.0), rnd.uniform(0, 360))]
        for x in (-PX, PX):
            for z in (Z0 + 0.35, Z0 + 0.8):
                tie(g, x, 0.0, z, rnd)
    elif stage == 1:
        # stretched and slumped: fewer, flatter, lower loops; one wire snapped; one picket leaning
        def squash(t):
            return 1.0 - 0.45 * math.exp(-((t - 0.5) / 0.22) ** 2)

        def rscale(t):
            return 1.0 - 0.18 * math.exp(-((t - 0.5) / 0.25) ** 2)

        def wob(t, ph):
            mid = math.exp(-((t - 0.5) / 0.22) ** 2)
            return (0.03 * math.sin(2 * math.pi * 2 * t), 0.06 * mid * math.sin(ph * 0.5 + 1.0) + 0.05 * mid,
                    -0.11 * mid - 0.025 * math.sin(3 * math.pi * t))
        P = helix_path(-0.5, 0.5, 4.8, 0.0, per_turn=26, rscale=rscale, squash=squash, wobble=wob)
        # clamp the lowest points above the ground
        P[:, 2] = np.maximum(P[:, 2], Z0 + WIRE_R + 0.004)
        cut0, cut1 = int(len(P) * 0.58), int(len(P) * 0.66)
        a = curl_end(P[:cut0 + 1], True, rnd, turns=1.4, r0=0.05)
        b = curl_end(P[cut1:], False, rnd, turns=1.1, r0=0.04)
        wire(g, a, 0, rnd)
        wire(g, b, 1, rnd)
        place_picket(g, picket(rnd, 0), -PX, 0.0, (0, 3.0), rnd.uniform(0, 360))
        place_picket(g, picket(rnd, 1), PX, 0.03, (-15.0, 5.0), rnd.uniform(0, 360))
        for x, z in ((-PX, Z0 + 0.35), (-PX, Z0 + 0.8), (PX, Z0 + 0.4)):
            tie(g, x, 0.0, z, rnd)
    else:
        heap(g, rnd, 1.0, (-0.5, 0.5))
    return g


def knot(rnd, center, radii, n=220, harmonics=7, spin=1.0):
    """A tangled loop of wire: a closed curve of low random harmonics in an ellipsoid."""
    cof = [[(rnd.uniform(-1, 1), rnd.uniform(0, 6.28)) for _ in range(harmonics)] for _ in range(3)]
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        p = []
        for a in range(3):
            v = sum(cof[a][k][0] / (k + 1) ** 0.7 * math.cos((k + 2) * t + cof[a][k][1]) for k in range(harmonics))
            p.append(v)
        pts.append(p)
    P = np.array(pts)
    P /= np.abs(P).max(axis=0)[None, :]
    P = P * np.asarray(radii)[None, :] + np.asarray(center)[None, :]
    P[:, 2] = np.maximum(P[:, 2], Z0 + WIRE_R + 0.003)
    return P


def heap(g, rnd, scale, xr, corner=False):
    """The collapsed coil: knots of wire on the ground, a stretched tail of loops, pickets down."""
    knots = [knot(rnd, (0.0, 0.0, Z0 + 0.2), (0.38, 0.33, 0.19), 120, 8),
             knot(rnd, (0.12, -0.08, Z0 + 0.17), (0.3, 0.26, 0.15), 100, 7),
             knot(rnd, (-0.2, 0.1, Z0 + 0.15), (0.24, 0.22, 0.13), 90, 6)]
    for k, P in enumerate(knots):
        wire(g, np.concatenate([P, P[:1]]), 2 + k, rnd)
    # a few loops still hanging off the leaning picket, sagging to the ground
    def squash(t):
        return 1.0 - 0.6 * t

    def wob(t, ph):
        return (0.0, 0.08 * t, -0.3 * t * t)
    tail = helix_path(-0.5, -0.05, 2.0, 0.0, per_turn=26, rscale=lambda t: 1.0 - 0.45 * t, squash=squash, wobble=wob)
    tail[:, 2] = np.maximum(tail[:, 2], Z0 + WIRE_R + 0.004)
    wire(g, curl_end(tail, True, rnd, turns=1.2, r0=0.05), 5, rnd)
    # pickets: one leaning at 35 degrees, one snapped off and lying on the ground
    place_picket(g, picket(rnd, 0, top=1.0), -PX, 0.05, (-35.0, 0.0), 0.0)
    lying = wk.Geo()
    place_picket(lying, picket(rnd, 1, top=0.75), 0.0, 0.0, (0, 0), 0)
    M = m_t(-0.3, -0.33, Z0 + 0.025) @ m_r("Z", 30) @ m_r("Y", 90) @ m_t(0, 0, -Z0)
    g.merge(lying, M)
    tie(g, -PX, 0.05, Z0 + 0.3, rnd, 6)


def corner(stage, seed):
    rnd = random.Random(seed)
    g = wk.Geo()
    L = 0.5
    if stage == 0:
        for arm, rotz in (("X", 0.0), ("Y", 90.0)):
            ph = -2 * math.pi * 3.5 + (0.0 if arm == "X" else 0.5)
            # shorter arm radius so the two coils cross inside the corner
            P = helix_path(0.0, L, 3.5, ph, per_turn=22,
                           rscale=lambda t: 0.93 + 0.07 * t + 0.02 * math.sin(7 * t + seed),
                           wobble=lambda t, p_: (0.008 * math.sin(5 * t), 0.0, 0.004 * math.sin(9 * t)))
            P = wk.xf(P, m_r("Z", rotz))
            wire(g, P, 0 if arm == "X" else 1, rnd)
        for (x, y) in ((0.0, 0.0), (PX, 0.0), (0.0, PX)):
            place_picket(g, picket(rnd, 0 if x == 0 else 1, top=PICKET_TOP),
                         x, y, (0, 0), rnd.uniform(0, 360))
        for (x, y) in ((0.0, 0.0), (PX, 0.0), (0.0, PX)):
            for z in (Z0 + 0.35, Z0 + 0.8):
                tie(g, x, y, z, rnd)
    elif stage == 1:
        for arm, rotz in (("X", 0.0), ("Y", 90.0)):
            ph = -2 * math.pi * 2.4
            P = helix_path(0.0, L, 2.4, ph, per_turn=26,
                           rscale=lambda t: 0.9 - 0.18 * math.exp(-((t - 0.55) / 0.25) ** 2),
                           squash=lambda t: 1.0 - 0.4 * math.exp(-((t - 0.55) / 0.25) ** 2),
                           wobble=lambda t, p_: (0.02 * math.sin(4 * t), 0.04 * t, -0.09 * math.exp(-((t - 0.55) / 0.25) ** 2)))
            P[:, 2] = np.maximum(P[:, 2], Z0 + WIRE_R + 0.004)
            if arm == "X":
                P = curl_end(P[:int(len(P) * 0.7)], True, rnd, turns=1.3, r0=0.05)
            P = wk.xf(P, m_r("Z", rotz))
            wire(g, P, 0 if arm == "X" else 1, rnd)
        place_picket(g, picket(rnd, 0), 0.0, 0.0, (3.0, -4.0), rnd.uniform(0, 360))
        place_picket(g, picket(rnd, 1), PX, 0.0, (0.0, 8.0), rnd.uniform(0, 360))
        place_picket(g, picket(rnd, 1), 0.0, PX, (-14.0, 0.0), rnd.uniform(0, 360))
        for (x, y, z) in ((0, 0, 0.35), (0, 0, 0.8), (PX, 0, 0.4), (0, PX, 0.5)):
            tie(g, x, y, Z0 + z, rnd)
    else:
        knots = [knot(rnd, (0.12, 0.12, Z0 + 0.18), (0.34, 0.34, 0.17), 120, 8),
                 knot(rnd, (0.2, 0.0, Z0 + 0.14), (0.25, 0.2, 0.12), 90, 6),
                 knot(rnd, (0.0, 0.22, Z0 + 0.14), (0.2, 0.25, 0.12), 90, 6)]
        for k, P in enumerate(knots):
            wire(g, np.concatenate([P, P[:1]]), 2 + k, rnd)
        place_picket(g, picket(rnd, 0, top=1.0), 0.0, 0.0, (-24.0, -20.0), 0.0)
        lying = wk.Geo()
        place_picket(lying, picket(rnd, 1, top=0.7), 0.0, 0.0, (0, 0), 0)
        g.merge(lying, m_t(0.42, 0.4, Z0 + 0.025) @ m_r("Z", 200) @ m_r("Y", 90) @ m_t(0, 0, -Z0))
        tie(g, 0.0, 0.0, Z0 + 0.3, rnd, 6)
    return g


# ================================================================ main

tk.reset_scene()
A = paint_atlas()
PATHS = A.save(ASSETS, MAT)
log("atlas painted", PATHS)
MATERIAL = tk.baked_material(MAT, PATHS)
assert MATERIAL.name == MAT, MATERIAL.name

ALL = []
BUILT = {}
REPORT = []
for key, fn, seed0 in (("Section", section, 5), ("Corner", corner, 77)):
    meshes = []
    for s in range(3):
        g = fn(s, seed0 + s * 11)
        obj = g.to_object("%s_DMG%d" % (key, s), MATERIAL, sharp=50.0)
        meshes.append(obj)
        log("%s DMG%d: %d tris %s" % (key, s, g.tris(), g.by_tag()))
    BUILT[key] = meshes
    ALL.extend(meshes)
    wk.export_piece(ASSETS, "RazorWire%s.fbx" % key, meshes, (0.0, -0.3, Z0 + 0.5))
    for i, m in enumerate(meshes):
        lo, hi, tris = wk.stats([m])
        REPORT.append("RazorWire%s.fbx DMG%d: %d tris, bounds %s .. %s" % (key, i, tris, lo.round(3), hi.round(3)))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
P = wk.Preview(PREVIEWS, ALL)
P.stage(floor_scale=4.0, floor_shift=(0.5, 0.5))
S, C = BUILT["Section"], BUILT["Corner"]
P.figure_at(2.8, 0.6)
ents = [(S[0], (-1.5, 0.0), 0), (S[1], (0.0, 0.0), 0), (S[2], (1.5, 0.0), 0)]
P.lineup(ents, tk.camera("St", (1.2, -6.2, 1.5), (0.0, 0.0, 0.35), lens=35), "razor_section_stages.png")
P.lineup(ents, tk.camera("Bk", (-1.2, 6.2, 1.5), (0.0, 0.0, 0.35), lens=35), "razor_section_stages_back.png")
ents = [(C[0], (-1.5, 0.0), 0), (C[1], (0.0, 0.0), 0), (C[2], (1.5, 0.0), 0)]
P.figure_at(2.6, 1.0)
P.lineup(ents, tk.camera("Cn", (1.5, -6.0, 2.4), (0.0, 0.3, 0.3), lens=35), "razor_corner_stages.png")
P.lineup(ents, tk.camera("CnB", (-0.5, 6.0, 2.6), (0.0, 0.3, 0.3), lens=35), "razor_corner_stages_back.png")
P.figure_at(1.6, -0.6)
P.lineup([(S[0], (0.0, 0.0), 0)], tk.camera("Close", (0.9, -1.4, 0.8), (0.0, 0.0, 0.4), lens=40), "razor_close.png",
         res=(1400, 1100))
P.lineup([(S[0], (0.0, 0.0), 0)], tk.camera("Close2", (0.35, -0.9, 0.25), (0.15, -0.2, 0.0), lens=40),
         "razor_close_barbs.png", res=(1400, 1100))
P.lineup([(S[2], (0.0, 0.0), 0)], tk.camera("Heap", (0.9, -1.5, 0.6), (0.0, 0.0, -0.3), lens=38),
         "razor_heap_close.png", res=(1400, 1100))
P.lineup([(S[1], (0.0, 0.0), 0)], tk.camera("Sag", (0.9, -1.5, 1.0), (0.0, 0.0, 0.1), lens=38),
         "razor_sag_close.png", res=(1400, 1100))
row = [(S[0], (-1.0, 0.0), 0), (S[0], (0.0, 0.0), 180), (S[0], (1.0, 0.0), 0), (C[0], (2.0, 0.0), 0),
       (S[0], (2.0, 1.0), 90), (S[1], (2.0, 2.0), 90)]
P.figure_at(-2.3, -1.0)
P.lineup(row, tk.camera("Run", (-2.4, -4.8, 2.4), (1.0, 0.8, 0.2), lens=30), "razor_run.png", res=(2000, 1100))
for o in ALL:
    o.hide_render = o is not S[0]
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S[0]}
tk.icon(tk.camera("Icon", (1.8, -2.6, 1.3), (0.0, 0.0, 0.2), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.2))
log("icon", ICON)
wk.reimport_check(ASSETS, "RazorWire")
log("done")
