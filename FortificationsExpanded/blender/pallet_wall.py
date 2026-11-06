"""Pallet Wall (Fortifications Expanded): shipping pallets stood on edge, screwed and wired to posts, 2 m tall. One
painted atlas, `PalletWall` (PalletWall_Albedo.png, PalletWall_Normal.png, PalletWall_RMOM.png, 2048).

    PalletWallSection.fbx   1 m wide, 2 m tall panel on the wall line (y = 0, front -Y): a 1.2 m pallet with a 0.8 m
                            pallet on top of it, two 4x4 posts behind (+Y) at x = +-0.43, screws and wire lashings.
                            DMG0 intact, DMG1 boards stripped (gaps, hanging boards, the top pallet slumped, a post
                            leaning), DMG2 a collapsed pile of boards, stringers and snapped posts under 0.35 m;
                            plus an empty FX in the middle of the front face at mid-height
    PalletWallCorner.fbx    a 0.15 m post at the origin with half-width pallet panels (cut pallets) running to +X and
                            to +Y (the Y arm is the X arm mirrored across the diagonal, so both fronts face the
                            outside, as chain-link's corner does), end posts behind them; the same three stages

Every pallet is real geometry: a front deck and a back deck of boards (5 to 7 of different widths, gaps between, leading
edge boards flush), three stringers between them, nail heads at every crossing. Pallets are mismatched (different
heights, widths, board counts, tones), some boards are chipped, short or split, a few are raised on a loose nail.
Boards are lofted boxes with a slight bow and ragged or slanted ends.

Atlas: 42 strips of weathered pallet wood (a plank photo crop graded to grey and tan, normalised so the photo only
supplies the grain, knots and wear; a few carry faded stencilled marks made of random block glyphs, so nothing reads),
6 stringer strips, 6 post strips, end grain swatches, a rusty nail swatch and steel wire columns.

    blender -b --factory-startup --python pallet_wall.py -- <unity asset folder> <preview folder> <icon file> [mode]

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

wk.TAG = "pallet"
log = wk.log

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

N = 2048
MAT = "PalletWall"
SW, SH = 96, 640          # a board strip: 96 px wide, 640 px (1 m) long
SC = 640.0                # board strip pixels per metre
LOW_Y, LOW_H = 1290, 700  # the second block of swatches
STR_SC, POST_SC = 480.0, 304.0
POST_X = 600
EG_X, EG_Y = 1200, 1290   # end grain swatches (64 px, 8 of them)
NAIL = (1200, 1370, 64)
WIRE_X = 1300

TY = 0.019                # deck board thickness
STR = 0.089               # stringer section
YF, YB = -0.0525, 0.0525  # deck board centre lines
PX_POST = 0.43
POST = 0.09
Y_POST = 0.117


# ---------------------------------------------------------------- the atlas

PLANKS = [125, 344, 576, 806, 1034, 1261, 1495, 1722]
GLYPH_RNG = random.Random(99)


def glyph_bitmap(rnd):
    """A 7 x 5 block glyph, symmetric left-right like most capitals; random, so it spells nothing."""
    g = np.zeros((7, 5), bool)
    for r in range(7):
        a, b, c = rnd.random() < 0.6, rnd.random() < 0.55, rnd.random() < 0.5
        g[r] = [a, b, c, b, a]
    g[rnd.randrange(7)] = True
    g[0, 2] |= rnd.random() < 0.5
    return g


def stencil_mask(rng, rnd, h, w, v0, glyphs=7, cell=6):
    """Faded stencilled marks on a strip: a row of random block glyphs reading along v, and a bar, eroded by noise."""
    m = np.zeros((h, w), np.float32)
    u0 = (w - 7 * cell) // 2 + rnd.randint(-6, 6)
    v = v0
    for _ in range(glyphs):
        gm = glyph_bitmap(rnd)
        for r in range(7):
            for c in range(5):
                if gm[r, c]:
                    m[v + c * cell: v + (c + 1) * cell, u0 + r * cell: u0 + (r + 1) * cell] = 1.0
        v += 6 * cell
    # a rule under or beside the marks, and a small box mark
    m[v0 - 10: v0 - 6, 6:w - 6] = 1.0
    erode = smoothstep(0.38, 0.55, fbm(h, w, 14, 3, rng, 5)) * smoothstep(0.25, 0.45, fbm(h, w, 120, 12, rng, 2))
    return m * erode


def wood_strip(rng, rnd, w, h, tone, scale_down=2, stencil=None, grimy=0.3):
    plank = PLANKS[rnd.randrange(8)]
    xoff = plank + 8 + rnd.randrange(0, 20)
    yoff = rnd.randrange(0, 2048)
    ph = wk.crop(wk.photo("weathered_planks", "diff"), xoff, yoff, w * scale_down, h * scale_down)
    ph = wk.resize(ph, w, h)
    hh = wk.resize(wk.crop(wk.photo("weathered_planks", "disp"), xoff, yoff, w * scale_down, h * scale_down), w, h)
    L = wk.luma(ph)
    Ln = np.clip(L / max(L.mean(), 1e-3), 0.35, 2.2)
    chroma = np.clip(ph / (L[..., None] + 1e-3), 0.6, 1.7)
    chroma = chroma / chroma.mean(axis=(0, 1), keepdims=True)
    fiber = fbm(h, w, 4, 36, rng, 3)
    fine = fbm(h, w, 40, 200, rng, 2)
    t = np.asarray(tone, np.float32)[None, None, :]
    # a touch of the photo's own warmth only, so strips don't pick up its colour noise
    warm = np.clip(chroma[..., 0] / np.maximum(chroma[..., 2], 0.5), 0.8, 1.3)[..., None] - 1.0
    col = t * (Ln ** 1.45)[..., None] * (1.0 + 0.0 * warm) * (0.82 + 0.28 * fiber)[..., None] * \
        (0.93 + 0.14 * fine)[..., None]
    # grey weathering: streaks of dirt and green-grey mould, darker along the long grain
    streak = np.maximum(smoothstep(0.55, 0.78, fbm(h, w, 6, 3, rng, 4)) * grimy,
                        smoothstep(0.6, 0.8, fbm(h, w, 2, 1, rng, 5)) * 0.8)
    col = col + (np.array([0.13, 0.125, 0.11])[None, None, :] - col) * streak[..., None] * 0.65
    height = hh * 3.0 + fiber * 1.2 + fine * 0.6
    rough = 0.82 + 0.1 * fine - 0.15 * np.clip(Ln - 1.0, 0, 1)
    if stencil is not None:
        mask = stencil
        paint = np.array(stencil_color(rnd))[None, None, :] * (0.8 + 0.3 * fine)[..., None]
        col = col + (paint - col) * (mask * 0.85)[..., None]
        rough = rough - 0.1 * mask
        height = height + mask * 0.3
    return np.clip(col, 0, 1), height, np.clip(rough, 0, 1)


def stencil_color(rnd):
    return rnd.choice([(0.55, 0.53, 0.48), (0.07, 0.065, 0.06), (0.36, 0.14, 0.1), (0.5, 0.47, 0.38)])


TONES = [(0.34, 0.31, 0.28), (0.40, 0.34, 0.27), (0.45, 0.41, 0.36), (0.24, 0.21, 0.18), (0.29, 0.28, 0.25),
         (0.37, 0.33, 0.28), (0.31, 0.28, 0.25)]


def paint_atlas():
    rng = np.random.default_rng(88)
    rnd = random.Random(7)
    A = wk.Atlas(N)
    n = 0
    stencil_ids = {2, 9, 15, 23, 30, 36}
    for row in range(2):
        for k in range(21):
            tone = TONES[rnd.randrange(len(TONES))]
            f = rnd.uniform(0.82, 1.12)
            tone = tuple(c * f for c in tone)
            st = stencil_mask(rng, rnd, SH, SW, rnd.randrange(60, 300)) if n in stencil_ids else None
            col, height, rough = wood_strip(rng, rnd, SW, SH, tone, stencil=st)
            A.paste(k * SW, row * SH, col, height, rough, 0.0, nstrength=2.2, gutter=2)
            n += 1
    # stringer strips (cleaner, rougher sawn 2x4) and post strips (dark treated 4x4)
    for k in range(6):
        f = rnd.uniform(0.9, 1.05)
        tone = tuple(c * f for c in TONES[(k * 2 + 1) % len(TONES)])
        col, height, rough = wood_strip(rng, rnd, SW, LOW_H, tone, scale_down=2, grimy=0.4)
        A.paste(k * SW, LOW_Y, col, height, rough, 0.0, nstrength=2.2, gutter=2)
    for k in range(6):
        tone = (0.27, 0.25, 0.21) if k % 2 else (0.31, 0.29, 0.24)
        col, height, rough = wood_strip(rng, rnd, SW, LOW_H, tone, scale_down=3, grimy=0.6)
        A.paste(POST_X + k * SW, LOW_Y, col, height, rough, 0.0, nstrength=2.2, gutter=2)
    # end grain: pale or grey, with growth rings and checks
    for k in range(8):
        s = 64
        yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
        cx, cy = rnd.uniform(-40, 100), rnd.uniform(-60, 100)
        d = np.hypot(xx - cx, (yy - cy) * 1.4) * 0.35
        rings = 0.5 + 0.5 * np.sin(d * 2.4 + 3 * fbm(s, s, 4, 4, rng, 2))
        base = np.array(TONES[(k + 2) % len(TONES)])[None, None, :] * 1.05
        col = base * (0.7 + 0.35 * rings)[..., None] * (0.85 + 0.25 * fbm(s, s, 12, 12, rng, 3))[..., None]
        crack = smoothstep(0.02, 0.0, np.abs(fbm(s, s, 3, 20, rng, 2) - 0.5))
        col = col * (1.0 - 0.45 * crack[..., None])
        A.paste(EG_X + k * 66, EG_Y, np.clip(col, 0, 1), rings * 1.2 + crack * -2.0, 0.92, 0.0, nstrength=2.0, gutter=1)
    # nail and screw heads: rusty dark steel
    s = NAIL[2]
    tone = fbm(s, s, 8, 8, rng, 3)
    col = (np.array([0.22, 0.14, 0.09])[None, None, :] * (0.7 + 0.6 * tone)[..., None])
    col = col + (np.array([0.35, 0.34, 0.33])[None, None, :] - col) * (smoothstep(0.7, 0.8, tone) * 0.5)[..., None]
    A.paste(NAIL[0], NAIL[1], col, tone, 0.7, 0.45, nstrength=2.0)
    # wire columns
    for k in range(4):
        h, w = LOW_H, 16
        tone = fbm(h, w, 40, 1, rng, 4)
        rust = smoothstep(0.5, 0.7, fbm(h, w, 14, 1, rng, 5))
        steel = np.array([0.32, 0.32, 0.31])[None, None, :] * (0.85 + 0.3 * tone)[..., None]
        col = steel + (np.array([0.33, 0.15, 0.06])[None, None, :] - steel) * rust[..., None]
        A.paste(WIRE_X + k * 18, LOW_Y, col, rust * tone * 3.0, 0.4 + 0.5 * rust, 0.8 * (1 - rust), nstrength=2.0,
                gutter=1)
    return A


# ---------------------------------------------------------------- parts

def strip_uv(strip, low=False):
    """(x, y, scale) of a strip: ids 0-41 board strips, 100+ stringer strips, 200+ post strips."""
    if strip < 42:
        return (strip % 21) * SW, (strip // 21) * SH, SC
    if strip < 200:
        return (strip - 100) % 6 * SW, LOW_Y, STR_SC
    return POST_X + (strip - 200) % 6 * SW, LOW_Y, POST_SC


def lumber(L, wz, ty, strip, rnd, ns=4, bow=0.004, endL=(0, 0, 0, 0), endR=(0, 0, 0, 0), tag="board", flip=False,
           twist=0.0):
    """A board built along local x (centred on the origin), wz tall (local z), ty thick (local y), lofted in ns steps
    with a slight bow, ragged or slanted ends (per-corner x shifts endL/endR in metres), UV-mapped on a strip."""
    g = wk.Geo()
    sx, sy, sc = strip_uv(strip)
    corners = [(-ty / 2, -wz / 2), (-ty / 2, wz / 2), (ty / 2, wz / 2), (ty / 2, -wz / 2)]
    bx = rnd.uniform(-bow, bow)
    bz = rnd.uniform(-bow, bow) * 0.6
    rings = []
    for i in range(ns + 1):
        t = i / ns
        ring = []
        for c, (cy, cz) in enumerate(corners):
            x = -L / 2 + L * t
            if i == 0:
                x += endL[c]
            if i == ns:
                x -= endR[c]
            dy = bx * math.sin(math.pi * t) + twist * (t - 0.5) * (1 if cz > 0 else -1)
            dz = bz * math.sin(math.pi * t)
            ring.append((x, cy + dy, cz + dz))
        rings.append(ring)
    u_off = 2 + rnd.uniform(0, max(0.0, SW - 4 - wz * sc))
    vdir = -1.0 if flip else 1.0
    v_start = 2 if not flip else 2 + min(L * sc, LOW_H - 4 if strip >= 100 else SH - 4)

    def uvv(x, side):
        # u across the board width (face-dependent), v along the length
        v = v_start + vdir * (x + L / 2) * sc
        return v

    for i in range(ns):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            k1 = (k + 1) % 4
            quad = (b[k], b[k1], a[k1], a[k])
            pts = quad
            uvs = []
            for p in pts:
                if k in (0, 2):  # wide faces: u across the width (z), mirrored on the back
                    uu = u_off + (p[2] + wz / 2) * sc if k == 0 else u_off + (wz / 2 - p[2]) * sc
                else:  # thin faces: u across the thickness
                    uu = 2 + (p[1] + ty / 2) * sc if k == 1 else 2 + (ty / 2 - p[1]) * sc
                uvs.append(((sx + uu) / N, (sy + uvv(p[0], k)) / N))
            g.quad(*pts, *uvs, tag=tag)
    # end faces on the end grain swatches
    eg = rnd.randrange(8)
    ex, ey = EG_X + eg * 66 + 2, EG_Y + 2
    for ring, rev in ((rings[0], False), (rings[-1], True)):
        pts = list(ring) if not rev else list(reversed(ring))
        quv = [(ex + 4, ey + 4), (ex + 4, ey + 56), (ex + 56, ey + 56), (ex + 56, ey + 4)]
        if rev:
            quv = list(reversed(quv))
        g.quad(*pts, *[((a) / N, (b) / N) for a, b in quv], tag=tag)
    return g


def ragged(rnd, amount):
    """Per-corner end shifts for a sawn or broken end: mostly small, sometimes a slanted break."""
    if rnd.random() < 0.55:
        return tuple(rnd.uniform(0.0, 0.004) for _ in range(4))
    a = rnd.uniform(0.0, amount)
    b = rnd.uniform(0.0, amount)
    c = rnd.uniform(0.0, amount * 0.4)
    return (a, a + rnd.uniform(0, 0.02), b + rnd.uniform(0, 0.02), c)


def deck_layout(rnd, H, wmin=0.09, wmax=0.14, gap_min=0.018):
    """Board widths and centres up a deck of height H: a board flush with each end, even-ish gaps between."""
    while True:
        n = max(3, int(H / rnd.uniform(0.15, 0.185)))
        ws = [rnd.uniform(wmin, wmax) for _ in range(n)]
        total = sum(ws)
        if total + (n - 1) * gap_min <= H:
            break
        if wmax > wmin + 0.01:
            wmax -= 0.005
    gaps = [rnd.uniform(0.7, 1.4) for _ in range(n - 1)]
    scale = (H - total) / sum(gaps)
    gaps = [g * scale for g in gaps]
    out, z = [], 0.0
    for i, w in enumerate(ws):
        out.append((z + w / 2, w))
        z += w + (gaps[i] if i < n - 1 else 0)
    return out


def back_layout(rnd, front, H):
    """The back deck: flush boards at both ends and boards centred on the front deck's gaps, so little daylight
    shows straight through (the two decks of a real pallet don't line up either)."""
    out = []
    wl, wh = rnd.uniform(0.09, 0.12), rnd.uniform(0.09, 0.12)
    out.append((wl / 2, wl))
    top = wl
    for (z0c, w0), (z1c, w1) in zip(front, front[1:]):
        g0, g1 = z0c + w0 / 2, z1c - w1 / 2
        gc, gw = (g0 + g1) / 2, g1 - g0
        w = min(0.14, max(0.09, gw + rnd.uniform(0.06, 0.1)))
        lo, hi = gc - w / 2, gc + w / 2
        if lo < top + 0.012 or hi > H - wh - 0.012:
            continue
        out.append((gc, w))
        top = hi
    out.append((H - wh / 2, wh))
    return out


class Pallet:
    """A pallet stood on edge: its decks, boards and stringers as data, so the stages can strip it, bend it and
    scatter it."""

    def __init__(self, rnd, W, H, xc=0.0, z0=0.0, damaged=0.0, narrow_ok=False):
        self.rnd = rnd
        self.W, self.H, self.xc, self.z0 = W, H, xc, z0
        self.boards, self.stringers = [], []
        tone_pool = list(range(0, 42))
        front = deck_layout(rnd, H)
        for deck, y in (("f", YF), ("b", YB)):
            layout = front if deck == "f" else back_layout(rnd, front, H)
            for zc, wz in layout:
                kind = rnd.choices(["ok", "chip", "short", "split"], [0.62, 0.17, 0.11, 0.10])[0]
                xa, xb = xc - W / 2, xc + W / 2
                eL, eR = ragged(rnd, 0.0), ragged(rnd, 0.0)
                w_use = wz
                if kind == "chip":
                    if rnd.random() < 0.5:
                        eL = ragged(rnd, rnd.uniform(0.03, 0.09))
                    else:
                        eR = ragged(rnd, rnd.uniform(0.03, 0.09))
                elif kind == "short":
                    cut = rnd.uniform(0.12, 0.4) if W > 0.6 else rnd.uniform(0.05, 0.15)
                    if rnd.random() < 0.5:
                        xa += cut
                        eL = ragged(rnd, 0.06)
                    else:
                        xb -= cut
                        eR = ragged(rnd, 0.06)
                elif kind == "split":
                    w_use = wz * rnd.uniform(0.5, 0.7)
                    zc = zc + (wz - w_use) / 2 * rnd.choice([-1, 1])
                    eL, eR = ragged(rnd, 0.05), ragged(rnd, 0.05)
                self.boards.append(dict(deck=deck, y=y, xa=xa, xb=xb, zc=zc, wz=w_use, eL=eL, eR=eR, kind=kind,
                                        strip=rnd.choice(tone_pool), flip=rnd.random() < 0.5, state="ok",
                                        raised=rnd.random() < 0.08))
        n_str = 3 if W > 0.6 else 2
        xs = [xc - W / 2 + STR / 2 + 0.005, xc + W / 2 - STR / 2 - 0.005]
        if n_str == 3:
            xs.insert(1, xc + rnd.uniform(-0.03, 0.03))
        for x in xs:
            self.stringers.append(dict(x=x, strip=100 + rnd.randrange(6), flip=rnd.random() < 0.5,
                                       endL=ragged(rnd, 0.0), endR=ragged(rnd, 0.0)))

    def build(self, g, rnd, M=None, removed=(), hanging=(), nails=True, tag="pallet"):
        """Adds the pallet's geometry to g (transformed by M if given). removed/hanging: sets of board indices."""
        gg = wk.Geo()
        for s in self.stringers:
            L = self.H
            lg = lumber(L, STR, STR, s["strip"], rnd, ns=3, bow=0.003, endL=s["endL"], endR=s["endR"], tag="stringer",
                        flip=s["flip"])
            lg.transform(m_t(s["x"], 0.0, self.z0 + L / 2) @ m_r("Y", -90))
            gg.merge(lg)
        for i, b in enumerate(self.boards):
            if i in removed:
                continue
            L = b["xb"] - b["xa"]
            ns = 5 if L > 0.6 else 3
            lg = lumber(L, b["wz"], TY, b["strip"], rnd, ns=ns, bow=0.004, endL=b["eL"], endR=b["eR"], tag="board",
                        flip=b["flip"], twist=0.002 if b["raised"] else 0.0)
            xc = (b["xa"] + b["xb"]) / 2
            zc = self.z0 + b["zc"]
            if i in hanging:
                ang = hanging[i]
                pivot_x = b["xb"] if ang < 0 else b["xa"]
                # build about the pivot: the board's centre sits (xc - pivot_x) from it
                lg.transform(m_t(xc - pivot_x, 0.0, 0.0))
                lg.transform(m_t(pivot_x, b["y"], zc) @ m_r("Y", ang) @ m_r("Z", -ang * 0.1 * (1 if b["deck"] == "f" else -1)))
            else:
                lift = 0.012 if b["raised"] else 0.0
                lg.transform(m_t(xc, b["y"] - lift * (1 if b["deck"] == "f" else -1), zc))
            gg.merge(lg)
            if nails and i not in hanging:
                self.nails(gg, b, rnd, zc)
        g.merge(gg, M)

    def nails(self, g, b, rnd, zc):
        x0, y0, s = NAIL
        uc = ((x0 + s / 2) / N, (y0 + s / 2) / N)
        face = b["y"] - TY / 2 - 0.0008 if b["deck"] == "f" else b["y"] + TY / 2 + 0.0008
        sgn = -1.0 if b["deck"] == "f" else 1.0
        for st in self.stringers:
            if not (b["xa"] + 0.02 < st["x"] < b["xb"] - 0.02):
                continue
            for dz in (-0.5, 0.5) if b["wz"] > 0.1 else (0.0,):
                if rnd.random() < 0.18:
                    continue
                cx, cz = st["x"] + rnd.uniform(-0.01, 0.01), zc + dz * b["wz"] * 0.55 + rnd.uniform(-0.006, 0.006)
                r = 0.0065
                n = 5
                ring = [(cx + r * math.cos(2 * math.pi * k / n + 0.3), face, cz + r * math.sin(2 * math.pi * k / n + 0.3))
                        for k in range(n)]
                centre = (cx, face + sgn * 0.0012, cz)
                for k in range(n):
                    a, b2 = ring[k], ring[(k + 1) % n]
                    tri = (centre, a, b2) if sgn < 0 else (centre, b2, a)
                    g.tri(*tri, uc, uc, uc, "nail")


def post_geo(rnd, x, y, z0, top, size=POST, lean=(0.0, 0.0), strip=200, ns=5, cap_cut=True):
    """A 4x4 post: a lightly bowed square tube from z0 to top, base at (x, y)."""
    g = wk.Geo()
    pts = []
    bowx, bowy = rnd.uniform(-0.004, 0.004), rnd.uniform(-0.004, 0.004)
    for i in range(ns + 1):
        t = i / ns
        pts.append((bowx * math.sin(math.pi * t), bowy * math.sin(math.pi * t), z0 + (top - z0) * t))
    sx, sy, sc = strip_uv(strip)
    r = size / 2 * math.sqrt(2)
    height = top - z0
    uvr = ((sx + 2) / N, (sy + 2) / N, (sx + 2 + min(4 * size * sc, 92)) / N, (sy + 2 + height * sc) / N)
    g.tube(pts, r, 4, uvr, caps=(False, True), tag="post", phase=0.5, vlen=height)
    if lean != (0.0, 0.0):
        g.transform(m_t(x, y, z0) @ m_r("X", lean[0]) @ m_r("Y", lean[1]) @ m_t(0, 0, -z0))
    else:
        g.transform(m_t(x, y, 0.0))
    return g


def lashing(g, rnd, cx, z, y0=-0.07, y1=0.17, hw=0.058, col=0):
    """A wire loop round a post and the pallet behind it (a rounded rectangle in the XY plane) with a twisted tail."""
    r = 0.0025
    pts = []
    for (px, py) in ((-hw, y0 + 0.01), (-hw, y1 - 0.012), (-hw + 0.012, y1), (hw - 0.012, y1), (hw, y1 - 0.012),
                     (hw, y0 + 0.012), (hw - 0.012, y0), (-hw + 0.016, y0), (-hw, y0 + 0.012)):
        pts.append((cx + px, py, z + 0.0015 * len(pts) / 9))
    pts.append((cx - hw + 0.006, y0 - 0.002, z + 0.004))
    pts.append((cx - hw + 0.03, y0 - 0.012, z + 0.012))
    pts.append((cx - hw + 0.045, y0 - 0.02, z + 0.006))
    x0 = (WIRE_X + col * 18 + 2) / N
    g.tube(np.array(pts), r, 3, (x0, (LOW_Y + 2) / N, x0 + 12 / N, (LOW_Y + 2 + 0.7 * SC) / N), caps=(True, True),
           tag="wire", phase=0.5, vlen=0.7)


def screw(g, cx, cz, face_y=YF - TY / 2 - 0.0008):
    x0, y0, s = NAIL
    uc = ((x0 + s / 2) / N, (y0 + s / 2) / N)
    r, n = 0.013, 6
    ring = [(cx + r * math.cos(2 * math.pi * k / n), face_y, cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    centre = (cx, face_y - 0.0025, cz)
    for k in range(n):
        g.tri(centre, ring[k], ring[(k + 1) % n], uc, uc, uc, "screw")


# ---------------------------------------------------------------- pieces

def assemble(rnd, W1, W2, x1, x2, H1, post_xs, stage, tag_seed, corner_arm=False, with_ends=True):
    """The panel's pallets and fixings. Returns (geometry, pallets)."""
    g = wk.Geo()
    p1 = Pallet(rnd, W1, H1, x1, Z0)
    p2 = Pallet(rnd, W2, 2.0 - H1 - 0.004, x2, Z0 + H1 + 0.004)
    pallets = (p1, p2)
    if stage == 0:
        p1.build(g, rnd)
        p2.build(g, rnd, M=m_t(0, rnd.uniform(-0.004, 0.006), 0))
        for px in post_xs:
            g.merge(post_geo(rnd, px, Y_POST, Z0, Z0 + 2.05 + rnd.uniform(-0.01, 0.03)))
            for z in (Z0 + 0.55, Z0 + 1.0, Z0 + 1.45, Z0 + 1.8):
                screw(g, px + rnd.uniform(-0.008, 0.008), z + rnd.uniform(-0.01, 0.01))
            for z, c in ((Z0 + 0.3, 0), (Z0 + 1.2, 1)):
                lashing(g, rnd, px + rnd.uniform(-0.01, 0.01), z + rnd.uniform(-0.03, 0.03), col=c)
    else:
        removed1 = {i for i, b in enumerate(p1.boards) if rnd.random() < (0.42 if b["deck"] == "f" else 0.3)
                    and i not in (0,)}
        removed2 = {i for i, b in enumerate(p2.boards) if rnd.random() < (0.45 if b["deck"] == "f" else 0.3)}
        keep1 = [i for i in range(len(p1.boards)) if i not in removed1]
        hang1 = {rnd.choice(keep1): rnd.choice([-1, 1]) * rnd.uniform(35, 70)}
        keep2 = [i for i in range(len(p2.boards)) if i not in removed2]
        hang2 = {rnd.choice(keep2): rnd.choice([-1, 1]) * rnd.uniform(25, 60)}
        p1.build(g, rnd, removed=removed1, hanging=hang1)
        # the top pallet has slipped: tilted out and down on one side
        Mtop = (m_t(x2, 0.0, Z0 + H1) @ m_r("Y", rnd.choice([-1, 1]) * 3.0) @ m_r("X", -4.0) @
                m_t(-x2, 0.0, -(Z0 + H1)) @ m_t(0, -0.01, -0.02))
        p2.build(g, rnd, M=Mtop, removed=removed2, hanging=hang2)
        for j, px in enumerate(post_xs):
            lean = (0.0, 0.0) if j == 0 else (5.0, 2.0)
            g.merge(post_geo(rnd, px, Y_POST, Z0, Z0 + 2.05, lean=lean))
            for z in (Z0 + 0.55, Z0 + 1.45):
                if rnd.random() < 0.6:
                    screw(g, px, z)
            lashing(g, rnd, px, Z0 + 0.35, col=2)
    return g, pallets


def pile(rnd, pallets, post_xs, extra_posts=True, region=((-0.5, 0.5), (-0.42, 0.42))):
    """The collapsed wall: boards and stringers dropped into a heap (laid by a height map), snapped posts."""
    g = wk.Geo()
    (xl, xh), (yl, yh) = region
    res = 0.03
    nx, ny = int((xh - xl) / res) + 1, int((yh - yl) / res) + 1
    hm = np.zeros((ny, nx))
    items = []
    for p in pallets:
        for s in p.stringers:
            L = p.H * rnd.uniform(0.45, 1.0)
            items.append(("str", L, STR, STR, s["strip"], s["flip"]))
        for i, b in enumerate(p.boards):
            if rnd.random() < 0.18:
                continue
            L = b["xb"] - b["xa"]
            if L > 0.5 and rnd.random() < 0.3:
                L *= rnd.uniform(0.4, 0.6)
            items.append(("brd", L, b["wz"], TY, b["strip"], b["flip"], b["eL"], b["eR"]))
    items.sort(key=lambda it: (0 if it[0] == "str" else 1, rnd.random()))
    for it in items:
        kind, L, wz, ty, strip, flip = it[:6]
        eL, eR = (it[6], it[7]) if kind == "brd" else (ragged(rnd, 0.0), ragged(rnd, 0.0))
        lg = lumber(L, wz, ty, strip, rnd, ns=3, bow=0.004, endL=eL, endR=eR, tag="board" if kind == "brd" else "stringer",
                    flip=flip)
        # lie it flat: local y (thickness) up, local z (width) across; yaw at random
        for _ in range(30):
            yaw = rnd.uniform(0, math.pi)
            cx = rnd.uniform(xl + 0.1, xh - 0.1)
            cy = rnd.uniform(yl + 0.1, yh - 0.1)
            ex = abs(L / 2 * math.cos(yaw)) + abs(wz / 2 * math.sin(yaw))
            ey = abs(L / 2 * math.sin(yaw)) + abs(wz / 2 * math.cos(yaw))
            if xl + ex <= cx <= xh - ex and yl + ey <= cy <= yh - ey:
                break
        else:
            continue
        # footprint samples
        us = np.linspace(-L / 2, L / 2, 9)
        vs = np.linspace(-wz / 2, wz / 2, 3)
        cells = set()
        for u in us:
            for v in vs:
                px = cx + u * math.cos(yaw) - v * math.sin(yaw)
                py = cy + u * math.sin(yaw) + v * math.cos(yaw)
                cells.add((int((py - yl) / res), int((px - xl) / res)))
        cells = [(a, b) for a, b in cells if 0 <= a < ny and 0 <= b < nx]
        top = max(hm[a, b] for a, b in cells)
        zc = Z0 + top + ty / 2
        for a, b in cells:
            hm[a, b] = top + ty
        tilt = rnd.uniform(-3, 3)
        M = m_t(cx, cy, zc) @ m_r("Z", math.degrees(yaw)) @ m_r("X", 90 + tilt)
        # rotating X by 90 maps local z (width) to -y and local y (thickness) to +z
        g.merge(lg, M)
    # snapped posts: a stub still standing, a long piece lying across the heap, leaning against it
    if extra_posts:
        g.merge(post_geo(rnd, post_xs[0], Y_POST, Z0, Z0 + rnd.uniform(0.35, 0.5), lean=(0.0, 3.0)))
        lay = post_geo(rnd, 0.0, 0.0, 0.0, 0.75, strip=203)
        lay.transform(m_t(-0.38, 0.12, Z0 + 0.19) @ m_r("Z", rnd.uniform(-20, 20)) @ m_r("Y", 78))
        g.merge(lay)
    return g


def section_stage(stage, seed):
    rnd = random.Random(seed)
    H1 = rnd.choice([1.2, 1.14, 1.2])
    posts = (-PX_POST, PX_POST)
    if stage < 2:
        g, _ = assemble(rnd, rnd.uniform(0.95, 0.99), rnd.uniform(0.9, 0.99), rnd.uniform(-0.01, 0.01),
                        rnd.uniform(-0.03, 0.03), H1, posts, stage, seed)
        return g
    # the pile is built from the same pallets as the intact stage
    rnd0 = random.Random(seed - 2)
    H1 = rnd0.choice([1.2, 1.14, 1.2])
    p1 = Pallet(random.Random(seed + 1), 0.97, H1, 0.0, 0.0)
    p2 = Pallet(random.Random(seed + 2), 0.94, 2.0 - H1, 0.0, 0.0)
    return pile(rnd, (p1, p2), posts)


ARM_X0, ARM_X1 = 0.075, 0.5
CPOST = 0.15


def corner_stage(stage, seed):
    rnd = random.Random(seed)
    g = wk.Geo()
    W = ARM_X1 - ARM_X0
    xc = (ARM_X0 + ARM_X1) / 2
    H1 = 1.2
    arm = wk.Geo()
    if stage < 2:
        a, _ = assemble(rnd, W - 0.01, W - 0.02, xc, xc + rnd.uniform(-0.01, 0.01), H1, (0.43,), stage, seed,
                        with_ends=True)
        arm.merge(a)
    else:
        p1 = Pallet(random.Random(seed + 1), W - 0.01, H1, 0.0, 0.0)
        p2 = Pallet(random.Random(seed + 2), W - 0.02, 2.0 - H1, 0.0, 0.0)
        pg = pile(rnd, (p1, p2), (0.43,), extra_posts=False, region=((0.08, 0.5), (-0.35, 0.3)))
        arm.merge(pg)
    g.merge(arm)
    mir = wk.Geo().merge(arm)
    # mirror across the diagonal: swap x and y, reverse the faces
    V = np.asarray(mir.V, float)
    mir.V = [(v[1], v[0], v[2]) for v in V]
    mir.F = [tuple(reversed(f)) for f in mir.F]
    mir.UV = [list(reversed(u)) for u in mir.UV]
    g.merge(mir)
    if stage == 0:
        g.merge(post_geo(rnd, 0.0, 0.0, Z0, Z0 + 2.06, size=CPOST, strip=204))
        for z in (Z0 + 0.5, Z0 + 1.0, Z0 + 1.5, Z0 + 1.85):
            screw(g, 0.0, z - 0.0)
    elif stage == 1:
        g.merge(post_geo(rnd, 0.0, 0.0, Z0, Z0 + 2.05, size=CPOST, strip=204, lean=(-2.0, -3.0)))
    else:
        g.merge(post_geo(rnd, 0.0, 0.0, Z0, Z0 + 0.55, size=CPOST, strip=204, lean=(0.0, 4.0)))
    return g


# ================================================================ main

tk.reset_scene()
A = paint_atlas()
PATHS = A.save(ASSETS, MAT)
log("atlas painted")
MATERIAL = tk.baked_material(MAT, PATHS)
assert MATERIAL.name == MAT, MATERIAL.name

ALL, BUILT, REPORT = [], {}, []
for key, fn, seed0 in (("Section", section_stage, 301), ("Corner", corner_stage, 502)):
    meshes = []
    for s in range(3):
        g = fn(s, seed0 + s * 13)
        obj = g.to_object("%s_DMG%d" % (key, s), MATERIAL, sharp=50.0)
        meshes.append(obj)
        log("%s DMG%d: %d tris %s" % (key, s, g.tris(), g.by_tag()))
    BUILT[key] = meshes
    ALL.extend(meshes)
    wk.export_piece(ASSETS, "PalletWall%s.fbx" % key, meshes, (0.0, -0.2, Z0 + 1.0))
    for i, m in enumerate(meshes):
        lo, hi, tris = wk.stats([m])
        REPORT.append("PalletWall%s.fbx DMG%d: %d tris, bounds %s .. %s" % (key, i, tris, lo.round(3), hi.round(3)))
for line in REPORT:
    log(line)
S = BUILT["Section"]
for i in range(3):
    log("see-through (front to back, section DMG%d): %.1f %%" % (
        i, 100 * wk.see_through([(S[i], (0, 0, 0), 0)], "Y", -0.5, 0.5, Z0 + 0.03, Z0 + 2.0, ds=0.01, dz=0.02)))
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
P = wk.Preview(PREVIEWS, ALL)
P.stage(floor_scale=4.0, floor_shift=(0.5, 0.5))
C = BUILT["Corner"]
P.figure_at(2.9, 0.6)
ents = [(S[0], (-1.5, 0.0), 0), (S[1], (0.0, 0.0), 0), (S[2], (1.5, 0.0), 0)]
P.lineup(ents, tk.camera("St", (1.2, -7.0, 2.0), (0.0, 0.0, 0.5), lens=35), "pallet_section_stages.png")
P.lineup(ents, tk.camera("Bk", (-1.2, 7.0, 2.0), (0.0, 0.0, 0.5), lens=35), "pallet_section_stages_back.png")
ents = [(C[0], (-1.5, 0.0), 0), (C[1], (0.0, 0.0), 0), (C[2], (1.5, 0.0), 0)]
P.figure_at(2.7, 1.3)
P.lineup(ents, tk.camera("Cn", (1.6, -6.5, 2.6), (0.0, 0.3, 0.6), lens=35), "pallet_corner_stages.png")
P.lineup(ents, tk.camera("CnB", (-0.5, 6.5, 2.8), (0.0, 0.3, 0.6), lens=35), "pallet_corner_stages_back.png")
P.figure_at(1.4, -0.8)
P.lineup([(S[0], (0.0, 0.0), 0)], tk.camera("Close", (0.7, -1.8, 1.2), (0.0, 0.0, 0.5), lens=40), "pallet_close.png",
         res=(1400, 1100))
P.lineup([(S[2], (0.0, 0.0), 0)], tk.camera("Pile", (0.9, -1.6, 0.9), (0.0, 0.0, -0.3), lens=38), "pallet_pile.png",
         res=(1400, 1100))
row = [(S[0], (-1.0, 0.0), 0), (S[0], (0.0, 0.0), 180), (S[1], (1.0, 0.0), 0), (C[0], (2.0, 0.0), 0),
       (S[0], (2.0, 1.0), 90), (S[0], (2.0, 2.0), 90)]
P.figure_at(-2.3, -1.0)
P.lineup(row, tk.camera("Run", (-2.8, -5.5, 2.8), (1.0, 0.8, 0.8), lens=30), "pallet_run.png", res=(2000, 1100))
P.lineup(row, tk.camera("RunB", (4.6, 4.8, 2.8), (1.0, 0.6, 0.8), lens=30), "pallet_run_back.png", res=(2000, 1100))
for o in ALL:
    o.hide_render = o is not S[0]
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S[0]}
tk.icon(tk.camera("Icon", (2.2, -3.4, 1.8), (0.0, 0.0, 0.5), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.5))
log("icon", ICON)
wk.reimport_check(ASSETS, "PalletWall")
log("done")
