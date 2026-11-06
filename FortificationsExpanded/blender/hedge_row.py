"""Hedge Row (Fortifications Expanded): a living hedge in growth stages. Two painted atlases (1024): `HedgeRow` (bark,
canes, dead twigs, broken wood, leaf litter on soil) and `HedgeRowMesh` (leaf sprites, alpha cut out at 0.3 in game).

    HedgeRowSaplingA/B.fbx   a few thin canes 0.55-1.0 m tall with a handful of small leaf cards (one mesh, DMG0)
    HedgeRowYoungA/B.fbx     a knee-high leafy bush, 0.6 m tall and 0.7 m wide (one mesh, DMG0)
    HedgeRowFull.fbx, HedgeRowFullB.fbx, HedgeRowFullC.fbx
        1.5 m tall, 0.9 m deep, 1 m wide neatly overgrown wild hedge (three different random shapes);
        DMG0 intact, DMG1 ripped and thinned (holes down to bare branches and broken stubs), DMG2 mostly stripped
        (stumps 0.4-0.9 m, bare twigs, broken branches on the ground, litter); plus an empty FX in the middle of the
        front face at mid-height

The foliage is layered leaf cards: each card is a 256 px sprite (a leafy sprig, a mass of leaves, a sparse dead twig)
painted with numpy leaf by leaf (veins, midrib, cupping, bitten edges, mixed ages, shadows between layers); cards sit
on the hedge's rounded shell and on three inner shells (lighter outside, darker inside) pointing outward and up, folded
along the midrib, double sided (duplicated reversed faces, as chain-link's mesh is). Vertex normals are set to point
outward from the hedge's core so the lighting stays soft. The branches are tapered tubes on the bark swatches; canes
and twigs are real geometry that shows once leaves are stripped.

    blender -b --factory-startup --python hedge_row.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default), export (no renders), lite (stage line-up, one damage close-up, the icon).
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

wk.TAG = "hedge"
log = wk.log

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)

N = 1024
CELL = 256
MAT = "HedgeRow"
MESH = "HedgeRowMesh"

# ---------------------------------------------------------------- leaf sprites (numpy)

PALETTES = [
    [(0.24, 0.33, 0.10), (0.21, 0.30, 0.09), (0.27, 0.35, 0.11), (0.19, 0.28, 0.08)],
    [(0.16, 0.25, 0.07), (0.14, 0.22, 0.07), (0.19, 0.27, 0.08), (0.17, 0.24, 0.09)],
    [(0.09, 0.15, 0.05), (0.11, 0.17, 0.06), (0.08, 0.13, 0.05)],
    [(0.33, 0.33, 0.11), (0.30, 0.22, 0.09), (0.22, 0.17, 0.08), (0.16, 0.24, 0.07), (0.28, 0.27, 0.10)],
]
TWIG = (0.2, 0.15, 0.1)


class Sprite:
    def __init__(self, rng, size=CELL):
        self.S = size
        self.img = np.zeros((size, size, 3), np.float32)
        self.img[...] = (0.14, 0.2, 0.07)
        self.a = np.zeros((size, size), np.float32)
        self.h = np.full((size, size), 0.5, np.float32)
        self.rng = rng

    def line(self, p0, p1, w0, w1, color=TWIG, height=0.7):
        S = self.S
        x0, x1 = int(max(0, min(p0[0], p1[0]) - w0 - 2)), int(min(S, max(p0[0], p1[0]) + w0 + 3))
        y0, y1 = int(max(0, min(p0[1], p1[1]) - w0 - 2)), int(min(S, max(p0[1], p1[1]) + w0 + 3))
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        ax, ay = p1[0] - p0[0], p1[1] - p0[1]
        L2 = max(ax * ax + ay * ay, 1e-6)
        t = np.clip(((xs + 0.5 - p0[0]) * ax + (ys + 0.5 - p0[1]) * ay) / L2, 0, 1)
        d = np.hypot(xs + 0.5 - (p0[0] + t * ax), ys + 0.5 - (p0[1] + t * ay))
        w = (w0 + (w1 - w0) * t) / 2
        a = np.clip(w - d + 0.5, 0, 1)
        tone = 0.8 + 0.4 * self.rng.random()
        c = np.array(color, np.float32) * tone
        self._over(y0, y1, x0, x1, a, c[None, None, :] * np.ones((1, 1, 3)), 0.5 + 0.5 * a * height)

    def _over(self, y0, y1, x0, x1, a, col, h):
        sl = (slice(y0, y1), slice(x0, x1))
        self.img[sl] = self.img[sl] * (1 - a[..., None]) + col * a[..., None]
        self.h[sl] = self.h[sl] * (1 - a) + h * a
        self.a[sl] = a + self.a[sl] * (1 - a)

    def leaf(self, cx, cy, ang, L, W, color, rng=None, shadow=True, bite=0.2, tip_brown=0.0, pale_edge=0.0):
        rng = rng or self.rng
        S = self.S
        r = int(L + 6)
        x0, x1 = max(0, int(cx - r)), min(S, int(cx + r) + 1)
        y0, y1 = max(0, int(cy - r)), min(S, int(cy + r) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)

        def cover(ox, oy):
            dx, dy = xs + 0.5 - cx - ox, ys + 0.5 - cy - oy
            ca, sa = math.cos(ang), math.sin(ang)
            s = (dx * ca + dy * sa) / L
            t = -dx * sa + dy * ca
            inside = (s > 0.0) & (s < 1.0)
            sc = np.clip(s, 0, 1)
            prof = np.clip(np.sin(np.pi * sc ** 0.72), 0, 1) ** 0.85
            hw = prof * W / 2
            return np.clip(hw - np.abs(t) + 0.5, 0, 1) * inside, s, t, hw
        a, s, t, hw = cover(0.0, 0.0)
        if a.max() <= 0:
            return
        if shadow:
            a_sh, _, _, _ = cover(2.5, -3.0)
            sl = (slice(y0, y1), slice(x0, x1))
            self.img[sl] *= (1 - 0.38 * a_sh * (self.a[sl] > 0.2) * (1 - a))[..., None]
        if bite > 0 and rng.random() < bite:
            for _ in range(rng.integers(1, 3)):
                bs = rng.uniform(0.25, 0.9)
                bt = rng.choice([-1, 1]) * W / 2 * 0.9
                dx, dy = xs + 0.5 - cx, ys + 0.5 - cy
                ca, sa = math.cos(ang), math.sin(ang)
                ss, tt = (dx * ca + dy * sa) / L, -dx * sa + dy * ca
                bite_m = np.clip((np.hypot((ss - bs) * L, tt - bt) - rng.uniform(2.5, 5.5)) * 1.0, 0, 1)
                a = a * bite_m
        tn = t / np.maximum(hw, 1e-3)
        rib = np.clip(1 - np.abs(t) / 1.4, 0, 1) * (s > 0.02)
        vein = smoothstep(0.78, 1.0, np.abs(np.sin(np.pi * (s * 9.0 - np.abs(tn) * 1.3))))
        vein = vein * (1 - np.clip(np.abs(tn), 0, 1) ** 3) * 0.9
        cup = -0.55 * tn
        shade = 0.84 + 0.2 * s + 0.12 * cup
        col = np.array(color, np.float32)[None, None, :] * shade[..., None]
        col = col + (np.array([0.5, 0.55, 0.25])[None, None, :] - col) * (0.22 * rib + 0.1 * vein)[..., None]
        edge = np.clip((hw - np.abs(t)) / 2.5, 0, 1)
        col = col * (0.82 + 0.18 * edge)[..., None]
        if tip_brown > 0:
            tb = smoothstep(1.0 - tip_brown, 1.0, s)
            col = col + (np.array([0.27, 0.19, 0.08])[None, None, :] - col) * tb[..., None] * 0.85
        if pale_edge > 0:
            col = col + (np.array([0.35, 0.3, 0.14])[None, None, :] - col) * ((1 - edge) * pale_edge)[..., None]
        h = 0.55 + 0.25 * (1 - np.abs(tn)) - 0.35 * rib + 0.25 * vein
        self._over(y0, y1, x0, x1, a, col, h)

    def finish(self):
        """Opaque colour under the transparent pixels is the average leaf colour (no pale fringes when filtered)."""
        m = self.a > 0.02
        avg = self.img[m].mean(axis=0) if m.any() else np.array([0.14, 0.2, 0.07])
        out = self.img.copy()
        out[~m] = avg
        return np.clip(out, 0, 1), self.a.copy(), self.h.copy()


def pick(rng, pal):
    c = np.array(PALETTES[pal][rng.integers(len(PALETTES[pal]))])
    return tuple(np.clip(c * rng.uniform(0.86, 1.14, 3), 0, 1))


def sprig_cell(rng, kind, row):
    """One 256 px sprite: kind 0 straight leafy sprig, 1 arching sprig with a side shoot, 2 dense leaf mass, 3 sparse
    twig with dead leaves; row = tone (0 lit outer .. 2 inner dark, 3 aged)."""
    sp = Sprite(rng)
    pal = row
    C = CELL

    def leaf_at(x, y, ang, L, dead=False):
        palette = 3 if dead else (3 if (row != 3 and rng.random() < 0.05) else pal)
        col = pick(rng, palette)
        sp.leaf(x, y, ang, L, L * rng.uniform(0.5, 0.62), col, bite=0.22, tip_brown=rng.uniform(0, 0.35) if rng.random() < 0.3 else 0.0,
                pale_edge=0.3 if dead else 0.0)

    if kind in (0, 1):
        base = np.array([128.0 + rng.uniform(-10, 10), 6.0])
        ang0 = math.radians(90 + rng.uniform(-8, 8))
        bend = 0.0 if kind == 0 else rng.choice([-1, 1]) * rng.uniform(0.35, 0.6)
        pts = [base.copy()]
        a = ang0
        step = 23.0
        nodes = 9
        for i in range(nodes):
            a += bend * 0.08 * (1 if kind else 0) + rng.uniform(-0.05, 0.05)
            pts.append(pts[-1] + step * np.array([math.cos(a), math.sin(a)]))
        # twig
        for i in range(len(pts) - 1):
            sp.line(pts[i], pts[i + 1], 4.2 - 2.4 * i / nodes, 4.2 - 2.4 * (i + 1) / nodes)
        order = list(range(1, len(pts)))
        for i in order:
            p = pts[i]
            t = i / nodes
            L = 54 * (1 - 0.36 * t) * rng.uniform(0.9, 1.08)
            if i > 0:
                ang_ax = math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0])
                for sgn in (-1, 1):
                    if rng.random() < 0.06:
                        continue
                    ang = ang_ax + sgn * math.radians(rng.uniform(42, 68))
                    sp.line(p, p + 7 * np.array([math.cos(ang), math.sin(ang)]), 2.2, 1.6)
                    leaf_at(*(p + 6 * np.array([math.cos(ang), math.sin(ang)])), ang, L)
                    # a smaller second leaf from the same node, lower and closer to the twig
                    ang2 = ang_ax + sgn * math.radians(rng.uniform(15, 30))
                    leaf_at(p[0], p[1], ang2, L * 0.78)
        # terminal leaf and tip pair
        tip = pts[-1]
        ang_ax = math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])
        leaf_at(tip[0], tip[1], ang_ax + rng.uniform(-0.1, 0.1), 34)
        if kind == 1:
            # a side shoot with its own smaller leaves
            k = rng.integers(3, 5)
            p = pts[k]
            ang = math.atan2(pts[k][1] - pts[k - 1][1], pts[k][0] - pts[k - 1][0]) + rng.choice([-1, 1]) * math.radians(48)
            q = p
            for j in range(3):
                q2 = q + 22 * np.array([math.cos(ang), math.sin(ang)])
                sp.line(q, q2, 2.6 - 0.5 * j, 2.2 - 0.5 * j)
                for sgn in (-1, 1):
                    la = ang + sgn * math.radians(rng.uniform(40, 62))
                    leaf_at(*(q2 + 4 * np.array([math.cos(la), math.sin(la)])), la, 34 - 4 * j)
                q = q2
                ang += rng.uniform(-0.12, 0.12)
            leaf_at(q[0], q[1], ang, 28)
    elif kind == 2:
        for _ in range(7):
            p0 = np.array([128 + rng.uniform(-30, 30), 20 + rng.uniform(0, 30)])
            ang = math.radians(rng.uniform(60, 120))
            sp.line(p0, p0 + 70 * np.array([math.cos(ang), math.sin(ang)]), 3.0, 2.0)
        leaves = []
        for _ in range(120):
            r = math.sqrt(rng.random()) * 104
            th = rng.uniform(0, 2 * math.pi)
            x, y = 128 + r * math.cos(th) * 1.05, 128 + r * math.sin(th) * 1.0
            ang = rng.uniform(0, 2 * math.pi)
            # leaves point roughly away from the sprite's base
            away = math.atan2(y - 10, x - 128)
            ang = away + rng.uniform(-1.1, 1.1)
            L = rng.uniform(34, 50) * (1.0 - 0.25 * (r / 100))
            leaves.append((r, x, y, ang, L))
        leaves.sort(key=lambda it: -it[0] + rng.uniform(-30, 30))
        for _, x, y, ang, L in leaves:
            leaf_at(x, y, ang, L)
    else:
        base = np.array([128.0 + rng.uniform(-12, 12), 6.0])
        pts = [base.copy()]
        a = math.radians(90 + rng.uniform(-14, 14))
        for i in range(6):
            a += rng.uniform(-0.2, 0.2)
            pts.append(pts[-1] + 34 * np.array([math.cos(a), math.sin(a)]))
            sp.line(pts[-2], pts[-1], 3.6 - 2 * i / 6, 3.6 - 2 * (i + 1) / 6, color=(0.3, 0.26, 0.2))
        # forked bare twigs
        for _ in range(5):
            i = rng.integers(1, 6)
            p = pts[i]
            ang = math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0]) + rng.choice([-1, 1]) * math.radians(rng.uniform(30, 60))
            q = p
            for j in range(2):
                q2 = q + rng.uniform(16, 26) * np.array([math.cos(ang), math.sin(ang)])
                sp.line(q, q2, 2.4 - 0.7 * j, 1.8 - 0.7 * j, color=(0.3, 0.26, 0.2))
                if rng.random() < 0.55:
                    leaf_at(q2[0], q2[1], ang + rng.uniform(-0.6, 0.6), rng.uniform(26, 40), dead=rng.random() < 0.8)
                q = q2
                ang += rng.uniform(-0.3, 0.3)
        for i in range(2, 7):
            if rng.random() < 0.7:
                p = pts[i]
                ang = math.radians(rng.uniform(20, 160))
                leaf_at(p[0], p[1], ang, rng.uniform(30, 44), dead=rng.random() < 0.7)
    return sp.finish()


def paint_leaf_atlas():
    rng = np.random.default_rng(2024)
    A = wk.Atlas(N)
    A.alb[..., :3] = (0.14, 0.2, 0.07)
    cover = {}
    for row in range(4):
        for kind in range(4):
            col, a, h = sprig_cell(rng, kind, row)
            # darkest at the base of the sprite (where it grows from inside the hedge)
            yy = np.linspace(0, 1, CELL)[:, None] * np.ones((1, CELL))
            ao = 0.62 + 0.38 * smoothstep(0.0, 0.5, yy)
            if row == 2:
                ao = ao * 0.9
            rough = 0.8 + 0.08 * fbm(CELL, CELL, 8, 8, rng, 3)
            x, y = kind * CELL, row * CELL
            A.paste(x, y, col, h * 2.2, rough, 0.0, ao=ao, alpha=a, nstrength=2.4, gutter=0)
            cover[(kind, row)] = float(a.mean())
    log("leaf sprite coverage by (kind,row):", {k: round(v, 2) for k, v in cover.items()})
    return A, cover


# ---------------------------------------------------------------- bark, litter

BARK_A = (0, 0, 128, 512)       # grey-brown old bark
BARK_B = (140, 0, 128, 512)     # young green-brown cane
BARK_C = (280, 0, 128, 512)     # dead grey twig
BROKEN = (420, 0, 96, 256)      # pale broken wood
LITTER = (0, 530, 256, 256)     # soil and fallen leaves


def paint_wood_atlas():
    rng = np.random.default_rng(555)
    A = wk.Atlas(N)
    for (x, y, w, h), base, fiss, sat in ((BARK_A, (0.26, 0.21, 0.16), 0.55, 1.0), (BARK_B, (0.25, 0.26, 0.13), 0.25, 1.0),
                                          (BARK_C, (0.45, 0.4, 0.33), 0.4, 0.7)):
        fib = fbm(h, w, 5, 28, rng, 4)
        crack = smoothstep(0.58, 0.72, fbm(h, w, 8, 36, rng, 5)) * fiss
        tone = fbm(h, w, 5, 2, rng, 4)
        col = np.array(base)[None, None, :] * (0.75 + 0.5 * fib)[..., None] * (0.85 + 0.3 * tone)[..., None]
        col = col * (1.0 - 0.55 * crack[..., None])
        # pale lenticels (small dashes across the grain) and lichen flecks
        lent = smoothstep(0.8, 0.9, fbm(h, w, 90, 10, rng, 2)) * 0.5
        col = col + (np.array([0.5, 0.46, 0.38])[None, None, :] - col) * lent[..., None] * 0.6
        lich = smoothstep(0.66, 0.75, fbm(h, w, 14, 5, rng, 4)) * 0.5
        col = col + (np.array([0.38, 0.4, 0.3])[None, None, :] - col) * lich[..., None]
        height = fib * 1.5 - crack * 2.0
        A.paste(x, y, np.clip(col, 0, 1), height, 0.88 - 0.1 * lich, 0.0, nstrength=2.0, gutter=2)
    # broken wood: pale splintered inside
    x, y, w, h = BROKEN
    fib = fbm(h, w, 3, 30, rng, 4)
    col = np.array([0.52, 0.42, 0.28])[None, None, :] * (0.7 + 0.5 * fib)[..., None]
    A.paste(x, y, np.clip(col, 0, 1), fib * 2.0, 0.85, 0.0, nstrength=2.0)
    # litter: dark soil with fallen dead leaves and twigs
    x, y, w, h = LITTER
    sp = Sprite(rng, 256)
    soil = fbm(256, 256, 10, 10, rng, 5)
    sp.img[...] = np.array([0.15, 0.115, 0.085])[None, None, :] * (0.7 + 0.6 * soil)[..., None]
    sp.a[...] = 1.0
    for _ in range(26):
        sp.line(np.array([rng.uniform(0, 256), rng.uniform(0, 256)]),
                np.array([rng.uniform(0, 256), rng.uniform(0, 256)]) * 0.3 + np.array([128, 128]) * 0.7, 3.0, 2.0,
                color=(0.28, 0.23, 0.17))
    for _ in range(95):
        c = [(0.3, 0.22, 0.1), (0.24, 0.17, 0.08), (0.2, 0.2, 0.08), (0.33, 0.28, 0.13), (0.15, 0.2, 0.07)][rng.integers(5)]
        sp.leaf(rng.uniform(0, 256), rng.uniform(0, 256), rng.uniform(0, 6.28), rng.uniform(22, 38), rng.uniform(13, 21),
                tuple(np.array(c) * rng.uniform(0.8, 1.15, 3)), shadow=True, bite=0.3)
    col, _, hm = sp.finish()
    A.paste(x, y, np.clip(col, 0, 1), hm * 2.0 + soil, 0.92, 0.0, nstrength=2.0)
    return A


# ---------------------------------------------------------------- geometry

def uvr(rect, margin=2):
    x, y, w, h = rect
    return ((x + margin) / N, (y + margin) / N, (x + w - margin) / N, (y + h - margin) / N)


def branch_pts(rnd, p0, direction, length, segs=5, bend=0.25, droop=0.0, wander=0.1):
    """A branch: a gently bending polyline from p0."""
    d = Vector(direction).normalized()
    pts = [Vector(p0)]
    ax = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)).normalized()
    for i in range(segs):
        d = (d + ax * bend / segs + Vector((rnd.uniform(-wander, wander), rnd.uniform(-wander, wander),
                                             rnd.uniform(-wander, wander) * 0.5 - droop / segs))).normalized()
        pts.append(pts[-1] + d * (length / segs))
    return [tuple(p) for p in pts]


def add_branch(g, pts, r0, r1, kind="A", sides=5, tag="stem", cut_top=False):
    rect = {"A": BARK_A, "B": BARK_B, "C": BARK_C}[kind]
    n = len(pts) - 1
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(n))
    g.tube(pts, r0, sides, uvr(rect), rfn=lambda t: r0 + (r1 - r0) * t, caps=(False, True), tag=tag, phase=0.5,
           vlen=1.5)


class Card:
    __slots__ = ("p", "d", "w", "size", "cell", "layer", "fold", "roll_n")


def hedge_surface(rnd, x, phi, a, b, base_z, lobe):
    """A point on the hedge's rounded shell: x along the hedge, phi 0..pi round the cross-section."""
    c, s = math.cos(phi), math.sin(phi)
    y = b * (abs(c) ** 0.78) * (1 if c >= 0 else -1)
    z = base_z + a * (abs(s) ** 0.7)
    return y * lobe, z


def make_cards(rnd, spec):
    """Foliage cards for a hedge of the given spec (width, depth half b, height a, layers...)."""
    cards = []
    a, b, base_z = spec["a"], spec["b"], Z0 + spec["base"]
    xw = spec["xw"]
    n_lobes = [(rnd.uniform(-xw, xw), rnd.uniform(0.0, math.pi), rnd.uniform(0.12, 0.22), rnd.uniform(0.1, 0.22)) for _ in range(9)]

    def lobe(x, phi):
        f = 1.0
        for lx, lp, lr, la in n_lobes:
            dist = math.hypot((x - lx) / 0.35, (phi - lp) / 0.7)
            f += la * math.exp(-dist * dist)
        return f

    for layer, (scale, count, size_rng) in enumerate(spec["layers"]):
        for _ in range(count):
            x = rnd.uniform(-xw, xw)
            phi = math.acos(rnd.uniform(-1, 1)) if layer == 0 else rnd.uniform(0.0, math.pi)
            yy, zz = hedge_surface(rnd, x, phi, a * scale, b * scale, base_z, lobe(x, phi))
            # sparser low down on the outer shell, so the stems show a little at the foot
            if layer == 0 and zz < base_z + 0.25 and rnd.random() < 0.65:
                continue
            core = np.array([0.0, 0.0, base_z + 0.1])
            pos = np.array([x, yy, zz])
            out = unit(pos - core + np.array([0.0, 0.0, 0.0001]))
            out_h = unit(np.array([out[0] * 0.25, out[1], out[2] * 0.8]))
            tip = unit(out_h * 0.85 + np.array([0.0, 0.0, 0.45]) + np.array([rnd.uniform(-0.4, 0.4) for _ in range(3)]))
            c = Card()
            c.size = rnd.uniform(*size_rng)
            c.d = tip
            c.p = pos - tip * (c.size * rnd.uniform(0.5, 0.62))
            c.layer = layer
            # sprite tone by depth, with some aged ones anywhere
            r = rnd.random()
            if r < 0.09:
                row = 3
            elif layer == 0:
                row = 0 if rnd.random() < 0.72 else 1
            elif layer == 1:
                row = 1 if rnd.random() < 0.7 else 2
            else:
                row = 2
            kind = rnd.choice([0, 1, 2, 2, 2, 2, 3]) if layer == 0 else rnd.choice([0, 1, 2, 2, 2, 3])
            c.cell = (kind, row)
            c.roll_n = out
            c.fold = rnd.uniform(0.01, 0.03)
            cards.append(c)
    # a few longer stray shoots poking out of the outer shell, so the outline isn't a clipped block
    for _ in range(spec.get("shoots", 0)):
        x = rnd.uniform(-xw, xw)
        phi = rnd.uniform(0.15, math.pi - 0.15)
        yy, zz = hedge_surface(rnd, x, phi, a, b, base_z, 1.0)
        out = unit(np.array([0.0, yy, zz - base_z - 0.1]))
        c = Card()
        c.size = rnd.uniform(0.42, 0.55)
        c.d = unit(out * 0.7 + np.array([rnd.uniform(-0.3, 0.3), 0.0, 0.55]))
        c.p = np.array([x, yy, zz]) - c.d * c.size * 0.45
        c.layer = 0
        c.cell = (rnd.choice([0, 1, 1]), 0 if rnd.random() < 0.7 else 1)
        c.roll_n = out
        c.fold = rnd.uniform(0.015, 0.035)
        cards.append(c)
    return cards


def card_geo(g, c, strength=1.0, tag="leaf", centre=None):
    """The folded double-sided quad of a card; vertex normals are set later from the hedge core."""
    d = c.d
    ref = c.roll_n if c.layer == 0 else np.array([random.uniform(-1, 1) for _ in range(3)])
    w = np.cross(d, ref)
    if np.linalg.norm(w) < 1e-3:
        w = np.cross(d, [1, 0, 0])
    w = unit(w)
    n = unit(np.cross(w, d))
    if n.dot(ref) < 0:
        n = -n
    hw = c.size * 0.5
    h = c.size * 1.0
    kind, row = c.cell
    u0 = (kind * CELL + 3) / N
    u1 = ((kind + 1) * CELL - 3) / N
    v0 = (row * CELL + 3) / N
    v1 = ((row + 1) * CELL - 3) / N
    um = (u0 + u1) / 2
    fold = c.fold * c.size / 0.3
    P = c.p
    bl, br = P - w * hw * 0.5, P + w * hw * 0.5
    mc_b = P + n * fold * 0.1
    mc_t = P + d * h
    tl, tr = P + d * h - w * hw * 0.55 + n * fold * 0.3, P + d * h + w * hw * 0.55 + n * fold * 0.3
    # two panels folded along the midrib, plus a bend at mid-height on the outer edges
    ml, mr = P + d * h * 0.5 - w * hw + n * fold * 0.6, P + d * h * 0.5 + w * hw + n * fold * 0.6
    mc_m = P + d * h * 0.5 + n * fold
    vm = (v0 + v1) / 2
    qs = ((bl, mc_b, mc_m, ml), ((u0 + 0.25 * (u1 - u0), v0), (um, v0), (um, vm), (u0, vm)))
    pans = [qs,
            ((mc_b, br, mr, mc_m), ((um, v0), (u1 - 0.25 * (u1 - u0), v0), (u1, vm), (um, vm))),
            ((ml, mc_m, mc_t, tl), ((u0, vm), (um, vm), (um, v1), (u0 + 0.25 * (u1 - u0), v1))),
            ((mc_m, mr, tr, mc_t), ((um, vm), (u1, vm), (u1 - 0.25 * (u1 - u0), v1), (um, v1)))]
    if c.layer > 0:
        # inner cards are hidden: two flat triangles' worth per face is enough
        pans = [((bl, br, tr, tl), ((u0 + 0.25 * (u1 - u0), v0), (u1 - 0.25 * (u1 - u0), v0),
                                    (u1 - 0.25 * (u1 - u0), v1), (u0 + 0.25 * (u1 - u0), v1)))]
        pans = [((bl, br, mr, ml), ((u0 + 0.25 * (u1 - u0), v0), (u1 - 0.25 * (u1 - u0), v0), (u1, vm), (u0, vm))),
                ((ml, mr, tr, tl), ((u0, vm), (u1, vm), (u1 - 0.25 * (u1 - u0), v1), (u0 + 0.25 * (u1 - u0), v1)))]
    for quad, uvs in pans:
        g.quad(*quad, *uvs, tag=tag)
        g.quad(*reversed(quad), *reversed(uvs), tag=tag)


def foliage_normals(obj, core, squash=(0.35, 1.0, 0.8)):
    """Vertex normals pointing out from the hedge's core and up a little, so cards shade like one soft mass."""
    me = obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    v = (co - np.asarray(core)[None, :]) * np.asarray(squash)[None, :]
    v[:, 2] += 0.25
    v /= np.maximum(np.linalg.norm(v, axis=1), 1e-6)[:, None]
    pol_leaf = np.zeros(nv, bool)
    for p in me.polygons:
        if p.material_index == 1:
            for vi in p.vertices:
                pol_leaf[vi] = True
    normals = []
    for p in me.polygons:
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            if pol_leaf[vi]:
                normals.append(tuple(v[vi]))
            else:
                normals.append(tuple(me.vertex_normals[vi].vector))
    try:
        me.normals_split_custom_set(normals)
    except Exception as e:  # noqa: BLE001
        log("custom normals not set:", e)


def finish_hedge(name, g, core, leaf_mat, wood_mat, custom=True):
    mi = [1 if t == "leaf" else 0 for t in g.tag]
    obj = g.to_object(name, [wood_mat, leaf_mat], sharp=60.0, mat_index=mi)
    if custom:
        foliage_normals(obj, core)
    return obj


# ---------------------------------------------------------------- pieces

FULL = dict(a=1.2, b=0.29, base=0.1, xw=0.34, shoots=16, layers=[(1.0, 175, (0.30, 0.42)), (0.78, 90, (0.30, 0.42)),
                                                       (0.52, 46, (0.3, 0.42)), (0.28, 20, (0.3, 0.42))])
YOUNG = dict(a=0.4, b=0.24, base=0.04, xw=0.3, layers=[(1.0, 70, (0.2, 0.28)), (0.7, 26, (0.2, 0.28)),
                                                         (0.4, 8, (0.2, 0.28))])


def stems_for(rnd, spec, height, n, x_range, tall_var=0.25):
    out = []
    for i in range(n):
        x = x_range[0] + (x_range[1] - x_range[0]) * (i + rnd.uniform(0.1, 0.9)) / n
        base = (x, rnd.uniform(-0.1, 0.1), Z0)
        lean = Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.3, 0.3), 1.0))
        h = height * rnd.uniform(1 - tall_var, 1.0)
        out.append((base, lean, h))
    return out


def full_hedge(seed, stage):
    rnd = random.Random(seed)
    rng = np.random.default_rng(seed)
    random.seed(seed)
    spec = FULL
    cards = make_cards(rnd, spec)
    g = wk.Geo()
    base_z = Z0
    stems = stems_for(rnd, spec, 1.2, 8, (-0.42, 0.42))
    branches = []
    for base, lean, h in stems:
        pts = branch_pts(rnd, base, lean, h, segs=6, bend=0.4, wander=0.08)
        branches.append((pts, 0.016 * rnd.uniform(0.85, 1.2), 0.004, "A"))
        # forks
        for k in range(rnd.randint(2, 4)):
            j = rnd.randint(2, 4)
            d0 = Vector(pts[j + 1]) - Vector(pts[j])
            d1 = (d0.normalized() + Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(0.0, 0.3)))).normalized()
            fp = branch_pts(rnd, pts[j], d1, h * rnd.uniform(0.3, 0.5), segs=4, bend=0.5, wander=0.12)
            branches.append((fp, 0.009 * rnd.uniform(0.8, 1.2), 0.0025, "A" if rnd.random() < 0.7 else "B"))
    if stage == 0:
        for pts, r0, r1, kind in branches:
            add_branch(g, pts, r0, r1, kind, sides=4)
        for c in cards:
            card_geo(g, c)
        litter(g, rnd, 0.36, 0.27)
    elif stage == 1:
        holes = [(rnd.uniform(-0.4, 0.4), rnd.choice([-1, 1]) * rnd.uniform(0.15, 0.35), Z0 + rnd.uniform(0.35, 1.25),
                  rnd.uniform(0.24, 0.4)) for _ in range(6)]
        kept = []
        for c in cards:
            p = c.p + c.d * 0.12
            inhole = any(math.dist((p[0], p[1], p[2]), (hx, hy, hz)) < hr for hx, hy, hz, hr in holes)
            if inhole and c.layer < 3 or (rnd.random() < 0.38 and c.layer < 3):
                continue
            kept.append(c)
        for c in kept:
            if rnd.random() < 0.18:
                c.cell = (3, 3 if rnd.random() < 0.6 else 1)
            card_geo(g, c)
        for pts, r0, r1, kind in branches:
            add_branch(g, pts, r0, r1, kind, sides=4)
        # extra twigs and broken stubs in the holes
        for hx, hy, hz, hr in holes:
            for _ in range(5):
                p0 = (hx * 0.5 + rnd.uniform(-0.1, 0.1), hy * 0.4, hz - 0.2 + rnd.uniform(-0.1, 0.1))
                d = Vector((hx - p0[0], hy - p0[1], rnd.uniform(0.0, 0.5))).normalized()
                tp = branch_pts(rnd, p0, d, rnd.uniform(0.3, 0.5), segs=3, bend=0.6, wander=0.2, droop=rnd.uniform(0, 0.2))
                add_branch(g, tp, 0.0045, 0.0018, "C" if rnd.random() < 0.4 else "A", sides=3)
            # a snapped limb: short thick stub with a pale break
            sp = branch_pts(rnd, (hx * 0.4, hy * 0.3, hz - 0.35), (hx * 0.5, hy, 0.3), 0.3, segs=2, bend=0.2)
            add_branch(g, sp, 0.011, 0.009, "A", sides=4)
            broken_end(g, sp, 0.009, rnd)
        litter(g, rnd, 0.44, 0.32)
    else:
        for c in cards:
            if c.layer == 0 and rnd.random() < 0.06 or (c.layer == 1 and rnd.random() < 0.04):
                if c.p[2] < Z0 + 0.8:
                    if rnd.random() < 0.5:
                        c.cell = (3, 3)
                    card_geo(g, c)
        for pts, r0, r1, kind in branches:
            cut = rnd.uniform(0.3, 0.75)
            n = max(2, int(len(pts) * cut))
            kept = pts[:n]
            rr = r0 + (r1 - r0) * (n / len(pts))
            add_branch(g, kept, r0, max(rr, 0.006), kind, sides=4)
            broken_end(g, kept, max(rr, 0.006), rnd)
            # bare side twigs left on the stump
            for _ in range(rnd.randint(0, 2)):
                j = rnd.randint(1, len(kept) - 1)
                d0 = (Vector(kept[j]) - Vector(kept[j - 1])).normalized()
                d1 = (d0 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0))).normalized()
                tp = branch_pts(rnd, kept[j], d1, rnd.uniform(0.15, 0.3), segs=3, bend=0.5, wander=0.15, droop=0.1)
                add_branch(g, tp, 0.004, 0.0015, "C", sides=3)
        # fallen branches
        for _ in range(4):
            p0 = (rnd.uniform(-0.35, 0.25), rnd.uniform(-0.3, 0.3), Z0 + 0.012)
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)).normalized()
            fp = branch_pts(rnd, p0, d, rnd.uniform(0.35, 0.6), segs=4, bend=0.25, wander=0.06)
            fp = [(p[0], p[1], max(Z0 + 0.006, p[2] * 0.2 + Z0 * 0.8 + 0.012)) for p in fp]
            add_branch(g, fp, 0.009, 0.004, "A" if rnd.random() < 0.6 else "C", sides=4)
            if rnd.random() < 0.5:
                broken_end(g, fp, 0.009, rnd, start=True)
        # a scatter of stripped leaves lying about
        litter(g, rnd, 0.5, 0.36, leafy=True)
        for c in cards:
            if rnd.random() < 0.04:
                c.p = c.p * np.array([1, 1, 0.0]) + np.array([0, 0, Z0 + 0.04 + rnd.uniform(0, 0.05)])
                c.d = unit(np.array([c.d[0], c.d[1], 0.15]))
                c.cell = (3, 3)
                card_geo(g, c)
    return g


def broken_end(g, pts, r, rnd, start=False):
    """A splintered, pale break at the top (or start) of a branch: a short cone of broken wood fibres."""
    end = Vector(pts[0]) if start else Vector(pts[-1])
    nxt = Vector(pts[1]) if start else Vector(pts[-2])
    d = (end - nxt).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = d.cross(Vector((1, 0, 0)))
    side.normalize()
    up = d.cross(side)
    x, y, w, h = BROKEN
    u0, v0 = (x + 4) / N, (y + 4) / N
    u1, v1 = (x + w - 4) / N, (y + h - 4) / N
    n = 5
    ring = [end + (side * math.cos(2 * math.pi * k / n) + up * math.sin(2 * math.pi * k / n)) * r * 1.02 for k in range(n)]
    for k in range(n):
        tip = end + d * rnd.uniform(0.012, 0.05) + (side * rnd.uniform(-1, 1) + up * rnd.uniform(-1, 1)) * r * 0.5
        a, b = ring[k], ring[(k + 1) % n]
        g.tri(a, b, tip, (u0, v0), (u1, v0), ((u0 + u1) / 2, v1), "stem")


def litter(g, rnd, rx, ry, leafy=False):
    """A flat patch of soil and dead leaves round the foot (an irregular disc just above the ground)."""
    x, y, w, h = LITTER
    n = 18
    cx, cy = rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03)
    ring = []
    for k in range(n):
        a = 2 * math.pi * k / n
        r = rnd.uniform(0.82, 1.0)
        ring.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    z = Z0 + 0.012

    def uv(px, py):
        return ((x + 128 + (px / 1.0) * 150) / N, (y + 128 + (py / 1.0) * 150) / N)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        g.tri((cx, cy, z), (a[0], a[1], z), (b[0], b[1], z), uv(cx, cy), uv(*a), uv(*b), "litter")


def young_hedge(seed):
    rnd = random.Random(seed)
    random.seed(seed)
    g = wk.Geo()
    cards = make_cards(rnd, YOUNG)
    for c in cards:
        card_geo(g, c)
    for base, lean, h in stems_for(rnd, YOUNG, 0.5, 5, (-0.26, 0.26), 0.35):
        pts = branch_pts(rnd, base, lean, h, segs=4, bend=0.35, wander=0.08)
        add_branch(g, pts, 0.008, 0.003, "B", sides=4)
    litter(g, rnd, 0.22, 0.18)
    return g


def sapling(seed):
    rnd = random.Random(seed)
    random.seed(seed)
    g = wk.Geo()
    n = rnd.randint(5, 7)
    for i in range(n):
        x, y = rnd.uniform(-0.12, 0.12), rnd.uniform(-0.1, 0.1)
        h = rnd.uniform(0.55, 1.0)
        lean = Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1.0))
        pts = branch_pts(rnd, (x, y, Z0), lean, h, segs=4, bend=0.3, wander=0.05)
        add_branch(g, pts, 0.0036, 0.0018, "B", sides=3)
        # a few small leaf cards near the top of the cane
        for k in range(rnd.randint(2, 4)):
            c = Card()
            t = rnd.uniform(0.45, 1.0)
            j = min(int(t * 4), 3)
            p = Vector(pts[j]).lerp(Vector(pts[j + 1]), t * 4 - j)
            c.p = np.array(p)
            ang = rnd.uniform(0, 2 * math.pi)
            c.d = unit(np.array([math.cos(ang) * 0.8, math.sin(ang) * 0.8, 0.5]))
            c.size = rnd.uniform(0.11, 0.17)
            c.layer = 0
            c.cell = (rnd.choice([0, 1]), 0 if rnd.random() < 0.8 else 3)
            c.roll_n = c.d * 1.0
            c.fold = 0.01
            card_geo(g, c)
    # the little pile of litter and the pruned stub of the cutting it grew from
    litter(g, rnd, 0.14, 0.12)
    return g


# ================================================================ main

tk.reset_scene()
WA = paint_wood_atlas()
WP = WA.save(ASSETS, MAT)
LA, COVER = paint_leaf_atlas()
LP = LA.save(ASSETS, MESH)
log("atlases painted")
WOOD = tk.baked_material(MAT, WP)
LEAF = wk.mesh_material(MESH, LP)
assert WOOD.name == MAT and LEAF.name == MESH, (WOOD.name, LEAF.name)

ALL, BUILT, REPORT = [], {}, []
CORE_FULL = (0.0, 0.0, Z0 + 0.3)


def build(name, g, core):
    obj = finish_hedge(name, g, core, LEAF, WOOD)
    ALL.append(obj)
    lo, hi, tris = wk.stats([obj])
    REPORT.append("%s: %d tris, bounds %s .. %s" % (name, tris, lo.round(3), hi.round(3)))
    return obj


for suf, seed in (("A", 11), ("B", 29)):
    BUILT["Sapling" + suf] = build("Sapling" + suf, sapling(seed), (0, 0, Z0 + 0.3))
    BUILT["Young" + suf] = build("Young" + suf, young_hedge(seed), (0, 0, Z0 + 0.15))
for suf, seed in (("", 101), ("B", 202), ("C", 303)):
    stages = [build("Full%s_DMG%d" % (suf, s), full_hedge(seed, s), CORE_FULL) for s in range(3)]
    BUILT["Full" + suf] = stages

for key in ("SaplingA", "SaplingB", "YoungA", "YoungB"):
    wk.export_piece(ASSETS, "HedgeRow%s.fbx" % key, [BUILT[key]], None)
for suf in ("", "B", "C"):
    wk.export_piece(ASSETS, "HedgeRowFull%s.fbx" % suf, BUILT["Full" + suf], (0.0, -0.3, Z0 + 0.75))
for line in REPORT:
    log(line)


def leaf_transmission(obj, atlas, samples=1500, seed=5, x_range=(-0.4, 0.4), z_range=(Z0 + 0.35, Z0 + 1.35)):
    """Rays along Y through the hedge (x and z within the ranges): the fraction that meet no card at all, and the mean
    light that gets through when each hit card passes (1 - alpha at the hit's UV) of the ray."""
    from mathutils.bvhtree import BVHTree
    me = obj.data
    uv = me.uv_layers["UVMap"].data
    V = [tuple(v.co) for v in me.vertices]
    F, idx = [], []
    for p in me.polygons:
        if p.material_index == 1:
            F.append(tuple(p.vertices))
            idx.append(p.index)
    bvh = BVHTree.FromPolygons(V, F)
    a_img = atlas.alb[..., 3]
    r = random.Random(seed)
    free, light = 0, 0.0
    d = Vector((0, 1, 0))
    for _ in range(samples):
        x, z = r.uniform(*x_range), r.uniform(*z_range)
        o = Vector((x, -1.5, z))
        hits, t = 0, 1.0
        while hits < 80:
            h = bvh.ray_cast(o, d, 6.0)
            if h[0] is None:
                break
            hits += 1
            poly = me.polygons[idx[h[2]]]
            verts = [Vector(V[i]) for i in poly.vertices]
            uvs = [uv[li].uv for li in poly.loop_indices]
            P = h[0]
            best = None
            for tri in ((0, 1, 2), (0, 2, 3)):
                if tri[2] >= len(verts):
                    continue
                A, B, C = verts[tri[0]], verts[tri[1]], verts[tri[2]]
                v0, v1, v2 = B - A, C - A, P - A
                d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
                den = d00 * d11 - d01 * d01
                if abs(den) < 1e-12:
                    continue
                bv = (d11 * d20 - d01 * d21) / den
                bw = (d00 * d21 - d01 * d20) / den
                bu = 1 - bv - bw
                score = min(bu, bv, bw)
                if best is None or score > best[0]:
                    best = (score, bu, bv, bw, tri)
            if best is not None:
                _, bu, bv, bw, tri = best
                u = bu * uvs[tri[0]][0] + bv * uvs[tri[1]][0] + bw * uvs[tri[2]][0]
                vv = bu * uvs[tri[0]][1] + bv * uvs[tri[1]][1] + bw * uvs[tri[2]][1]
                a = float(a_img[min(N - 1, max(0, int(vv * N))), min(N - 1, max(0, int(u * N)))])
                t *= 1.0 - (1.0 if a > 0.3 else 0.0)  # the game cuts at 0.3: a hit is solid or empty
            o = h[0] + d * 0.003
        if t > 0.5:
            free += 1
        light += t
    return free / samples, light / samples


for key in ("Full", "FullB", "FullC"):
    for s, o in enumerate(BUILT[key]):
        f, l = leaf_transmission(o, LA)
        log("%s DMG%d: straight rays through the middle that see daylight (alpha cut at 0.3): %.1f %%" % (key, s, 100 * f))
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
P = wk.Preview(PREVIEWS, ALL)
P.stage(floor_scale=4.0, floor_shift=(0.5, 0.5))
P.figure_at(3.0, 0.6)
growth = [(BUILT["SaplingA"], (-2.25, 0.0), 0), (BUILT["YoungA"], (-0.9, 0.0), 0), (BUILT["Full"][0], (0.7, 0.0), 0),
          (BUILT["Full"][1], (2.0, 0.0), 0), (BUILT["Full"][2], (3.3, 0.0), 0)]
P.lineup(growth, tk.camera("Grow", (0.5, -7.2, 2.0), (0.5, 0.0, 0.3), lens=35), "hedge_growth_stages.png", res=(2200, 1000))
P.figure_at(2.5, 0.8)
if MODE != "lite":
    P.lineup([(BUILT["Full"][0], (0.0, 0.0), 0)], tk.camera("Close", (0.8, -1.9, 1.0), (0.0, 0.0, 0.5), lens=40),
             "hedge_full_close.png", res=(1400, 1100))
P.lineup([(BUILT["Full"][1], (0.0, 0.0), 0)], tk.camera("Close1", (0.8, -1.9, 1.0), (0.0, 0.0, 0.5), lens=40),
         "hedge_full_dmg1_close.png", res=(1400, 1100))
if MODE == "lite":
    for o in ALL:
        o.hide_render = o is not BUILT["Full"][0]
    hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not BUILT["Full"][0]}
    tk.icon(tk.camera("Icon", (1.9, -2.6, 1.4), (0.0, 0.0, 0.4), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.4))
    log("icon", ICON)
    sys.exit(0)
P.lineup([(BUILT["Full"][2], (0.0, 0.0), 0)], tk.camera("Close2", (0.8, -1.9, 0.9), (0.0, 0.0, 0.2), lens=40),
         "hedge_full_dmg2_close.png", res=(1400, 1100))
row = [(BUILT["Full"][0], (-2.0, 0.0), 0), (BUILT["FullB"][0], (-1.0, 0.0), 180), (BUILT["FullC"][0], (0.0, 0.0), 0),
       (BUILT["Full"][0], (1.0, 0.0), 180), (BUILT["FullB"][0], (2.0, 0.0), 0), (BUILT["FullC"][1], (3.0, 0.0), 0),
       (BUILT["FullB"][0], (4.0, 0.0), 180)]
P.figure_at(-3.2, -1.2)
P.lineup(row, tk.camera("Row", (0.5, -6.0, 2.0), (1.0, 0.0, 0.5), lens=30), "hedge_row.png", res=(2200, 1000))
P.lineup(row, tk.camera("RowFar", (-3.0, -11.0, 2.6), (1.0, 0.0, 0.5), lens=35), "hedge_row_far.png", res=(1600, 800))
for o in ALL:
    o.hide_render = o is not BUILT["Full"][0]
hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not BUILT["Full"][0]}
tk.icon(tk.camera("Icon", (1.9, -2.6, 1.4), (0.0, 0.0, 0.4), lens=50), ICON, hide=hide, target=(0.0, 0.0, 0.4))
log("icon", ICON)
wk.reimport_check(ASSETS, "HedgeRow")
log("done")
