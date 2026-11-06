"""Stone Works (Fortifications Expanded): hand-laid masonry walls, all sharing one baked material, `StoneWorks`
(StoneWorks_Albedo.png, StoneWorks_Normal.png, StoneWorks_RMOM.png, 2048).

    ArrowSlitWall.fbx, ArrowSlitCorner.fbx, Battlement.fbx, BattlementCorner.fbx
        three meshes at the same origin, DMG0 (intact), DMG1 (cracked, chipped, stones missing) and DMG2 (heavily
        broken: top collapsed, rubble piled at the base), plus an empty FX in the middle of the front face

Every piece is one block cell wide and deep and built with its bottom at z = -0.5 (like every family); the wall line
runs along X through the cell centre, the front (outside) is -Y. The wall is 0.6 m thick plus up to 3 cm of stone relief
each side. ArrowSlitWall and its corner are 3 m tall (cap course on top, a splayed loophole at eye height in the
straight wall); Battlement and its corner are 1 m tall (crenellated: merlons and embrasures). Corner pieces are an L
(arms toward +X and +Y, outside corner at -X,-Y) like the palisade corner.

Stones are real geometry: each is a rounded block with a bulged, noisy, tilted face laid in courses with recessed lime
mortar behind; the loophole reveals, caps, quoins, missing-stone pockets and rubble are built the same way. Every
face is textured from photo-scanned rock, plaster and moss swatches that are cropped, graded and weathered here
(numpy) into one atlas; there is no Cycles bake.

    blender -b --factory-startup --python stone_works.py -- <unity asset folder> <preview folder> [<icon file>] [mode]
mode: all (default), tex (atlas only), export (atlas + FBX files, no renders), reuse (reuse the last atlas)
"""
import json
import math
import os
import random
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

_argv = sys.argv[sys.argv.index("--") + 1:]
MODES = ("all", "tex", "export", "reuse", "dev")
MODE = "all"
_paths = []
for _a in _argv:
    if _a in MODES:
        MODE = _a
    else:
        _paths.append(_a)
ASSETS, PREVIEWS = (os.path.abspath(a) for a in _paths[:2])
ICON = os.path.abspath(_paths[2]) if len(_paths) > 2 else None
for _d in (ASSETS, PREVIEWS) + ((os.path.dirname(ICON),) if ICON else ()):
    os.makedirs(_d, exist_ok=True)

Z0 = -0.5  # bottom of every model
MAT_NAME = "StoneWorks"
T0 = time.time()
HT = 0.30  # nominal half thickness: the stone faces sit at y = -/+0.30
MD = 0.03  # mortar plane depth behind the nominal face
ATLAS = 2048
PPM = 640.0  # atlas pixels per meter, the same on every swatch
GUT = 6


def log(*a):
    print("[stone_works %5.0fs]" % (time.time() - T0), *a, flush=True)


# ================================================================ numpy noise and image helpers

def _hash(ix, iy, iz, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + iz * 74.7 + seed * 53.3) * 43758.5453
    return v - np.floor(v)


def vnoise(P, seed=0.0):
    """3D value noise at points P (..., 3), -1..1."""
    P = np.asarray(P, np.float64)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    ix, iy, iz = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    ux, uy, uz = (f * f * (3 - 2 * f) for f in (fx, fy, fz))
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (ux if dx else 1 - ux) * (uy if dy else 1 - uy) * (uz if dz else 1 - uz)
                out = out + w * _hash(ix + dx, iy + dy, iz + dz, seed)
    return out * 2 - 1


def fbm(P, seed=0.0, octaves=3):
    tot, amp, f, n = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        n = n + amp * vnoise(np.asarray(P) * f, seed + o * 7.7)
        tot += amp
        amp *= 0.5
        f *= 2.1
    return n / tot


def smooth(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def snoise(h, w, sx, seed, sy=None, octaves=1):
    """Smooth gaussian-filtered noise (h, w), about unit std; sx, sy are the feature size in px."""
    sy = sx if sy is None else sy
    rng = np.random.default_rng(int(seed) & 0xFFFFFFF)
    out, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        white = rng.standard_normal((h, w))
        F = np.fft.rfft2(white)
        fy = np.fft.fftfreq(h)[:, None]
        fx = np.fft.rfftfreq(w)[None, :]
        g = np.exp(-0.5 * ((fx * sx / (2 ** o) * math.pi * 2) ** 2 + (fy * sy / (2 ** o) * math.pi * 2) ** 2))
        n = np.fft.irfft2(F * g, s=(h, w))
        n /= n.std() + 1e-9
        out += n * amp
        tot += amp
        amp *= 0.55
    out /= math.sqrt(sum(0.55 ** (2 * i) for i in range(octaves)))
    return out


def n01(n, gain=0.28):
    return np.clip(0.5 + gain * n, 0.0, 1.0)


# ================================================================ photo crops

PH_DIM = {"rock_boulder_dry": 1.8, "dry_riverbed_rock": 2.0, "quarry_wall_02": 1.8, "rock_face_03": 2.7,
          "dark_rock_02": 2.0, "rough_plaster_03": 1.5, "mossy_rock": 3.0, "lichen_rock": 2.0}
_PH = {}


def ph(set_name, kind):
    key = (set_name, kind)
    if key not in _PH:
        path = os.path.join(tk.TEXTURES, set_name, "%s_%s_2k.jpg" % (set_name, kind))
        if not os.path.exists(path):
            raise FileNotFoundError(path + " is missing; run src/fetch-textures-stone.ps1")
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        n = img.channels
        a = np.empty(img.size[0] * img.size[1] * n, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(img.size[1], img.size[0], n)[..., :3].astype(np.float64)
        H, W = a.shape[:2]
        if (W / PH_DIM[set_name]) / PPM >= 1.6:
            a = a[:H // 2 * 2, :W // 2 * 2].reshape(H // 2, 2, W // 2, 2, 3).mean((1, 3))
        _PH[key] = a
    return _PH[key]


def crop(set_name, kind, x0, y0, w_m, h_m):
    """w_m x h_m meters of the (tiling) photo starting at (x0, y0), at PPM, bottom row first."""
    a = ph(set_name, kind)
    H, W = a.shape[:2]
    dim = PH_DIM[set_name]
    ow, oh = int(round(w_m * PPM)), int(round(h_m * PPM))
    fx = ((x0 + (np.arange(ow) + 0.5) / PPM) / dim * W - 0.5) % W
    fy = ((y0 + (np.arange(oh) + 0.5) / PPM) / dim * H - 0.5) % H
    ix0 = np.floor(fx).astype(int)
    tx = (fx - ix0)[None, :, None]
    ix1 = (ix0 + 1) % W
    iy0 = np.floor(fy).astype(int)
    ty = (fy - iy0)[:, None, None]
    iy1 = (iy0 + 1) % H
    top = a[iy0][:, ix0] * (1 - tx) + a[iy0][:, ix1] * tx
    bot = a[iy1][:, ix0] * (1 - tx) + a[iy1][:, ix1] * tx
    return top * (1 - ty) + bot * ty


def luma(c):
    return c @ np.array([0.299, 0.587, 0.114])


def grade(c, mean, sat=1.0, contrast=1.0, tint=(1.0, 1.0, 1.0)):
    L = luma(c)[..., None]
    c = (L + (c - L) * sat) * np.array(tint)
    c = c * (mean / max(luma(c).mean(), 1e-6))
    c = (c - mean) * contrast + mean
    return np.clip(c, 0.0, 1.0)


def mixc(m, a, b):
    m = np.asarray(m)
    if m.ndim == a.ndim - 1:
        m = m[..., None]
    return a * (1 - m) + b * m


def photo_maps(set_name, x0, y0, w, h):
    """color (h, w, 3), normal slope (h, w, 2), roughness, ao of a crop."""
    col = crop(set_name, "diff", x0, y0, w, h)
    nor = crop(set_name, "nor_gl", x0, y0, w, h)
    arm = crop(set_name, "arm", x0, y0, w, h)
    return col, nor[..., :2] * 2 - 1, arm[..., 1], arm[..., 0]


def slope_from_height(hgt, strength):
    gy, gx = np.gradient(hgt)
    return np.stack([-gx, -gy], -1) * strength


# ================================================================ the swatches

def _soil(shape):
    return np.array((0.15, 0.115, 0.08))


def stone_swatch(key, seed, w, h):
    """Weathered stone face: a graded photo crop with mottling, rain streaks, dirt at the foot and pits."""
    recipe = {
        "ST0": ("rock_boulder_dry", 0.33, 0.45, 1.0, (1.0, 0.98, 0.93)),
        "ST1": ("dry_riverbed_rock", 0.27, 0.45, 1.2, (1.0, 0.94, 0.88)),
        "ST2": ("quarry_wall_02", 0.25, 0.4, 1.25, (1.0, 0.95, 0.86)),
        "ST3": ("rock_face_03", 0.30, 0.35, 1.1, (1.0, 0.95, 0.86)),
        "STD": ("dark_rock_02", 0.2, 0.5, 1.2, (0.95, 0.96, 1.0)),
        "STM": ("dry_riverbed_rock", 0.26, 0.55, 1.2, (0.97, 0.98, 0.9)),
        "STB": ("rock_boulder_dry", 0.28, 0.5, 1.15, (1.0, 0.93, 0.84)),
    }[key]
    rs = np.random.default_rng(seed)
    src, mean, sat, con, tint = recipe
    dim = PH_DIM[src]
    x0, y0 = rs.uniform(0, dim), rs.uniform(0, dim)
    col, nrm, rough, ao = photo_maps(src, x0, y0, w, h)
    ph_, pw_ = col.shape[:2]
    col = grade(col, mean, sat, con, tint)
    # slow mottling and a second scale of blotches
    col = col * (1 + 0.26 * snoise(ph_, pw_, 70, seed + 1)[..., None] + 0.10 * snoise(ph_, pw_, 14, seed + 2)[..., None])
    # rain streaks running down (anisotropic: long in v)
    st = snoise(ph_, pw_, 3.0, seed + 3, sy=95.0)
    st = np.clip(st - 0.4, 0, 2) * (0.5 + 0.5 * n01(snoise(ph_, pw_, 90, seed + 4)))
    col = col * (1 - 0.11 * st[..., None])
    # dark pits and specks
    pit = n01(snoise(ph_, pw_, 2.2, seed + 5, octaves=2), 0.5)
    col = col * (1 - 0.22 * smooth(0.88, 0.99, pit)[..., None])
    vv = (np.arange(ph_)[:, None] + 0.0) / PPM  # meters up the swatch
    soil_amt = {"STB": 0.95, "STM": 0.45}.get(key, 0.25)
    rim = smooth(0.09, 0.0, vv) * (0.55 + 0.45 * n01(snoise(ph_, pw_, 9, seed + 6)))
    col = mixc(np.clip(rim * soil_amt * 1.4, 0, 1), col, np.array((0.13, 0.10, 0.07)))
    if key == "STB":
        high = smooth(0.34, 0.06, vv) * n01(snoise(ph_, pw_, 22, seed + 7, octaves=2), 0.45)
        col = mixc(np.clip(high * 0.85, 0, 1), col, np.array((0.15, 0.115, 0.08)))
        rough = np.maximum(rough, 0.9 * high)
    if key in ("STM", "ST0", "ST1", "ST2", "ST3"):
        amt = 1.0 if key == "STM" else 0.0
        bias = np.clip(1 - vv / 0.32, 0, 1) ** 1.6
        m = n01(snoise(ph_, pw_, 38, seed + 8, octaves=3), 0.5) * 0.65 + bias * (0.55 if key == "STM" else 0.12)
        if key == "STM":
            m = m + 0.02 + 0.10 * n01(snoise(ph_, pw_, 150, seed + 9))
        mask = smooth(0.50 + 0.1 * (key != "STM"), 0.64 + 0.1 * (key != "STM"), m)
        mcol = grade(crop("mossy_rock", "diff", rs.uniform(0, 3), rs.uniform(0, 3), w, h), 0.17, 0.9, 1.25,
                     (0.9, 1.0, 0.68))
        mnrm = crop("mossy_rock", "nor_gl", 0, 0, w, h)[..., :2] * 2 - 1 if False else nrm
        col = mixc(mask * (1.0 if key == "STM" else 0.8), col, mcol)
        rough = rough * (1 - mask) + 0.96 * mask
        if key == "STM":
            # pale lichen crusts on top of the moss and the bare stone
            lc = grade(crop("lichen_rock", "diff", rs.uniform(0, 2), rs.uniform(0, 2), w, h), 0.2, 0.7, 1.3,
                       (0.95, 1.0, 0.9))
            lm = smooth(0.66, 0.74, n01(snoise(ph_, pw_, 12, seed + 10, octaves=3), 0.5) + 0.0 * mask)
            col = mixc(lm * 0.7, col, lc)
    return dict(alb=col, nrm=nrm * 1.0, rough=np.clip(rough * 0.97, 0.66, 1.0), ao=np.clip(ao, 0, 1))


def mortar_swatch(key, seed, w, h):
    rs = np.random.default_rng(seed)
    col, nrm, rough, ao = photo_maps("rough_plaster_03", rs.uniform(0, 1.5), rs.uniform(0, 1.5), w, h)
    ph_, pw_ = col.shape[:2]
    mean = {"MOR": 0.36, "MORM": 0.27, "MORD": 0.15}[key]
    col = grade(col, mean, 0.35, 1.25, (1.0, 0.97, 0.9))
    col = col * (1 + 0.22 * snoise(ph_, pw_, 55, seed + 1)[..., None] + 0.12 * snoise(ph_, pw_, 6, seed + 2)[..., None])
    grit = n01(snoise(ph_, pw_, 1.6, seed + 3), 0.5)
    col = col * (1 - 0.18 * smooth(0.88, 0.99, grit)[..., None])
    vv = (np.arange(ph_)[:, None]) / PPM
    if key == "MORM":
        bias = np.clip(1 - vv / 0.28, 0, 1) ** 1.2
        m = n01(snoise(ph_, pw_, 30, seed + 4, octaves=2), 0.45) * 0.6 + bias * 0.6 + 0.12
        mask = smooth(0.46, 0.62, m)
        mcol = grade(crop("mossy_rock", "diff", rs.uniform(0, 3), rs.uniform(0, 3), w, h), 0.15, 0.85, 1.2,
                     (0.9, 1.0, 0.68))
        col = mixc(mask, col, mcol)
        rough = rough * (1 - mask) + 0.96 * mask
    dirt = smooth(0.04, 0.0, vv) * 0.7
    col = mixc(np.clip(dirt, 0, 1), col, np.array((0.10, 0.08, 0.06)))
    if key == "MORD":
        col = col * (0.7 + 0.6 * n01(snoise(ph_, pw_, 20, seed + 5))[..., None])
    return dict(alb=col, nrm=nrm * 1.15, rough=np.clip(rough * 1.02, 0.6, 1.0), ao=np.clip(ao, 0, 1))


def fresh_swatch(seed, w, h):
    """Fresh fracture: paler rock with raw conchoidal faces."""
    rs = np.random.default_rng(seed)
    col, nrm, rough, ao = photo_maps("rock_face_03", rs.uniform(0, 2.7), rs.uniform(0, 2.7), w, h)
    ph_, pw_ = col.shape[:2]
    col = grade(col, 0.31, 0.3, 1.2, (1.0, 0.96, 0.88))
    col = col * (1 + 0.22 * snoise(ph_, pw_, 45, seed + 1)[..., None] + 0.12 * snoise(ph_, pw_, 8, seed + 2)[..., None])
    return dict(alb=col, nrm=nrm * 1.3, rough=np.clip(rough, 0.55, 1.0), ao=np.clip(ao, 0, 1))


def voronoi(h, w, nx, ny, seed, jitter=0.9):
    rs = np.random.default_rng(seed)
    gx, gy = np.meshgrid((np.arange(nx) + 0.5) / nx, (np.arange(ny) + 0.5) / ny)
    px = (gx + (rs.random(gx.shape) - 0.5) * jitter / nx).ravel() * w
    py = (gy + (rs.random(gy.shape) - 0.5) * jitter / ny).ravel() * h
    # anisotropy: cells a little wider than tall, like laid stones
    X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    d1 = np.full((h, w), 1e9)
    d2 = np.full((h, w), 1e9)
    idx = np.zeros((h, w), np.int32)
    for k in range(len(px)):
        d = np.hypot((X - px[k]) / 1.25, (Y - py[k]))
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idx = np.where(closer, k, idx)
        d1 = np.where(closer, d, d1)
    return d1, d2, idx


def core_swatch(seed, w, h):
    """Cross-section of rubble masonry: rough stones in dark mortar, for end faces, pockets and broken tops."""
    rs = np.random.default_rng(seed)
    pw_, ph_ = int(round(w * PPM)), int(round(h * PPM))
    d1, d2, idx = voronoi(ph_, pw_, 9, 6, seed)
    edge = (d2 - d1)
    nst = idx.max() + 1
    tone = 0.55 + 0.6 * rs.random(nst)
    which = rs.integers(0, 3, nst)
    srcs = ["rock_boulder_dry", "dry_riverbed_rock", "quarry_wall_02"]
    base = np.zeros((ph_, pw_, 3))
    nrm = np.zeros((ph_, pw_, 2))
    for k in range(3):
        c, n, _, _ = photo_maps(srcs[k], rs.uniform(0, 1.8), rs.uniform(0, 1.8), w, h)
        c = grade(c, 0.22, 0.5, 1.2, (1.0, 0.96, 0.9))
        sel = (which[idx] == k)[..., None]
        base = np.where(sel, c, base)
        nrm = np.where(sel, n, nrm)
    base = base * tone[idx][..., None]
    mor = grade(crop("rough_plaster_03", "diff", rs.uniform(0, 1.5), rs.uniform(0, 1.5), w, h), 0.20, 0.35, 1.2,
                (1.0, 0.96, 0.88))
    wd = 5.0 + 4.0 * n01(snoise(ph_, pw_, 25, seed + 1))
    mm = smooth(wd, wd * 0.35, edge)
    col = mixc(mm, base, mor)
    hgt = smooth(0.0, 18.0, d1 * 0 + edge) * 4.0 + (1 - mm) * -2.0
    nr = slope_from_height(hgt, 0.5) + nrm * 0.8
    col = col * (1 + 0.2 * snoise(ph_, pw_, 40, seed + 2)[..., None])
    return dict(alb=col, nrm=nr, rough=np.full((ph_, pw_), 0.9), ao=np.clip(0.55 + 0.45 * smooth(0.0, 10.0, edge), 0, 1))


SWATCH_DEFS = [  # key, width m, height m, builder
    ("ST0", 0.95, 0.80, lambda s, w, h: stone_swatch("ST0", s, w, h)),
    ("ST1", 0.95, 0.80, lambda s, w, h: stone_swatch("ST1", s, w, h)),
    ("ST2", 0.95, 0.80, lambda s, w, h: stone_swatch("ST2", s, w, h)),
    ("ST3", 0.95, 0.80, lambda s, w, h: stone_swatch("ST3", s, w, h)),
    ("STD", 0.95, 0.80, lambda s, w, h: stone_swatch("STD", s, w, h)),
    ("STM", 0.95, 0.80, lambda s, w, h: stone_swatch("STM", s, w, h)),
    ("STB", 0.95, 0.80, lambda s, w, h: stone_swatch("STB", s, w, h)),
    ("CORE", 1.05, 0.70, lambda s, w, h: core_swatch(s, w, h)),
    ("FRESH", 0.95, 0.50, lambda s, w, h: fresh_swatch(s, w, h)),
    ("MOR", 0.95, 0.45, lambda s, w, h: mortar_swatch("MOR", s, w, h)),
    ("MORM", 0.95, 0.45, lambda s, w, h: mortar_swatch("MORM", s, w, h)),
    ("MORD", 0.95, 0.45, lambda s, w, h: mortar_swatch("MORD", s, w, h)),
]
RECT = {}  # key -> (x0 px, y0 px, w px, h px, w m, h m)


def pack():
    x = y = GUT
    rowh = 0
    for key, wm, hm, _ in SWATCH_DEFS:
        wp, hp = int(round(wm * PPM)), int(round(hm * PPM))
        if x + wp + GUT > ATLAS:
            x, y, rowh = GUT, y + rowh + GUT, 0
        RECT[key] = (x, y, wp, hp, wm, hm)
        x += wp + GUT
        rowh = max(rowh, hp)
    assert y + rowh <= ATLAS, "the atlas is full (%d)" % (y + rowh)
    log("atlas rows end at %d of %d px" % (y + rowh, ATLAS))


def build_atlas(paths):
    pack()
    alb = np.zeros((ATLAS, ATLAS, 3))
    nrm = np.zeros((ATLAS, ATLAS, 2))
    rough = np.ones((ATLAS, ATLAS))
    ao = np.ones((ATLAS, ATLAS))
    alb[...] = (0.2, 0.2, 0.2)
    for i, (key, wm, hm, fn) in enumerate(SWATCH_DEFS):
        x0, y0, wp, hp, _, _ = RECT[key]
        s = fn(1000 + i * 37, wm, hm)
        a = s["alb"]
        assert a.shape[:2] == (hp, wp), (key, a.shape, hp, wp)
        # an edge-replicated gutter so mips and filtering never bring in a neighbour
        for arr, val in ((alb, a), (nrm, s["nrm"]), (rough, s["rough"]), (ao, s["ao"])):
            g = GUT // 2
            pad = [(g, g), (g, g)] + [(0, 0)] * (val.ndim - 2)
            v2 = np.pad(val, pad, mode="edge")
            arr[y0 - g:y0 + hp + g, x0 - g:x0 + wp + g] = v2
        log("swatch", key, a.shape, "mean", a.reshape(-1, 3).mean(0).round(3))
    nx, ny = nrm[..., 0], nrm[..., 1]
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.0, 1.0))
    ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
    # normalize slopes: if they exceed the unit disc, rescale
    over = np.sqrt(nx * nx + ny * ny) > 0.97
    sc = np.where(over, 0.97 / (np.sqrt(nx * nx + ny * ny) + 1e-9), 1.0)
    nx, ny = nx * sc, ny * sc
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0.0, 1.0))
    N = np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5, np.ones_like(nx)], -1)
    A = np.concatenate([np.clip(alb, 0, 1), np.ones((ATLAS, ATLAS, 1))], -1)
    R = np.stack([np.clip(rough, 0, 1), np.zeros_like(rough), np.clip(ao, 0, 1), np.ones_like(rough)], -1)
    for arr, path in ((A, paths["albedo"]), (N, paths["normal"]), (R, paths["rmom"])):
        save_png(arr, path)
    with open(os.path.join(ASSETS, "..", "..", "..", "Build", "stone_works_rects.json") if False else CACHE, "w") as f:
        json.dump(RECT, f)
    return A


def save_png(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.alpha_mode = "STRAIGHT"
    img.filepath_raw = path
    img.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    img.save()
    bpy.data.images.remove(img)


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__", "stone_works_rects.json")
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
PATHS = {k: os.path.join(ASSETS, "%s_%s.png" % (MAT_NAME, s)) for k, s in (("albedo", "Albedo"), ("normal", "Normal"),
                                                                           ("rmom", "RMOM"))}

tk.reset_scene()
if MODE in ("reuse", "dev") and os.path.exists(CACHE) and all(os.path.exists(p) for p in PATHS.values()):
    RECT.update({k: tuple(v) for k, v in json.load(open(CACHE)).items()})
    log("atlas reused")
else:
    build_atlas(PATHS)
    log("atlas written", PATHS["albedo"])
if MODE == "tex":
    sys.exit(0)


# ================================================================ geometry machinery

SHARP = 40.0
UVWARN = [0]
UVBY = {}


def atlas_uv(key, u_m, v_m):
    x0, y0, wp, hp, wm, hm = RECT[key]
    u_c = np.clip(u_m, 0.004, wm - 0.004)
    v_c = np.clip(v_m, 0.004, hm - 0.004)
    n_ = int((u_c != u_m).sum() + (v_c != v_m).sum())
    UVWARN[0] += n_
    if n_:
        UVBY[key] = UVBY.get(key, 0) + n_
    return np.stack([(x0 + u_c * PPM) / ATLAS, (y0 + v_c * PPM) / ATLAS], -1)


class Acc:
    """Triangle soup (per-corner positions and atlas UVs), welded into one mesh at the end."""

    def __init__(self):
        self.T, self.U, self.tags = [], [], {}

    def add(self, tris, uvs, tag):
        if len(tris):
            self.T.append(tris)
            self.U.append(uvs)
            self.tags[tag] = self.tags.get(tag, 0) + len(tris)

    def extend(self, other):
        self.T += other.T
        self.U += other.U
        for k, v in other.tags.items():
            self.tags[k] = self.tags.get(k, 0) + v


def orient(tri, uv, want):
    a, b = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    g = np.cross(a, b)
    area = np.linalg.norm(g, axis=1)
    flip = (g * want).sum(1) < 0
    tri = tri.copy()
    uv = uv.copy()
    tri[flip] = tri[flip][:, [0, 2, 1]]
    uv[flip] = uv[flip][:, [0, 2, 1]]
    keep = area > 1e-10
    return tri[keep], uv[keep]


def grid_to_tris(Q, UV, N):
    nb, nc = Q.shape[:2]
    i, j = np.meshgrid(np.arange(nb - 1), np.arange(nc - 1), indexing="ij")
    i, j = i.ravel(), j.ravel()
    A, B, C, D = (i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)
    t1 = np.stack([Q[A], Q[B], Q[C]], 1)
    t2 = np.stack([Q[A], Q[C], Q[D]], 1)
    u1 = np.stack([UV[A], UV[B], UV[C]], 1)
    u2 = np.stack([UV[A], UV[C], UV[D]], 1)
    n1 = (N[A] + N[B] + N[C]) / 3
    n2 = (N[A] + N[C] + N[D]) / 3
    tri = np.concatenate([t1, t2])
    uv = np.concatenate([u1, u2])
    nw = np.concatenate([n1, n2])
    return orient(tri, uv, nw)


def axis_nodes(h, r, k):
    r = max(min(r, h), 0.0)
    lo, hi = -h + r, h - r
    mid = list(np.linspace(lo, hi, k + 2)) if hi - lo > 1e-6 else [0.0]
    nodes = [-h] + mid + [h]
    out = [nodes[0]]
    for n in nodes[1:]:
        if n - out[-1] > 1e-6:
            out.append(n)
    return np.array(out)


def pick(nodes, rng):
    if rng == "all":
        return nodes
    if rng == "lo":
        return nodes[:2]
    if rng == "hi":
        return nodes[-2:]
    return nodes


STONE_FACES = {(1, -1): ("all", "all"), (0, -1): ("lo", "all"), (0, 1): ("lo", "all"), (2, -1): ("all", "lo"),
               (2, 1): ("all", "lo")}


def lump(sw, C, ex, ey, ez, h, R, faces, relief=None, k=(1, 1, 1), tilt=(0.0, 0.0), chips=(), uvoff=(0.08, 0.08),
         own=(), own_off=None, seed=0.0, jitter=0.0):
    """A rounded block (half sizes h, rounding radii R) in the frame (ex, ey, ez) at C, emitting only `faces`
    {(axis, sign): (range b, range c)}, with a noisy, bulged, tilted relief face. Local y points into the wall, the
    stone's front is its -y face. Returns world triangles and atlas UVs."""
    h = np.array(h, float)
    R = np.minimum(np.array(R, float), h)
    nodes = [axis_nodes(h[a], R[a], k[a]) for a in range(3)]
    relief = relief or {}
    ou, ov = uvoff
    tris, uvs = [], []
    Rc = R.clip(1e-6)
    for (a, s), (rb, rc) in faces.items():
        b, c = [x for x in range(3) if x != a]
        nb, nc = pick(nodes[b], rb), pick(nodes[c], rc)
        BB, CC = np.meshgrid(nb, nc, indexing="ij")
        p = np.zeros(BB.shape + (3,))
        p[..., a] = s * h[a]
        p[..., b] = BB
        p[..., c] = CC
        ps = p / Rc
        hs = h / Rc
        inner = np.clip(ps, -(hs - 1), hs - 1)
        d = ps - inner
        L = np.linalg.norm(d, axis=-1)
        m = L > 1e-9
        qs = inner + np.where(m[..., None], d / np.where(m, L, 1)[..., None], 0.0)
        q = np.where(m[..., None], qs * Rc, p)
        nrm = np.zeros_like(p)
        nrm[..., a] = s
        nn = d / Rc
        nn_l = np.linalg.norm(nn, axis=-1)
        nrm = np.where(m[..., None], nn / np.where(m, nn_l, 1)[..., None], nrm)
        disp = np.zeros_like(q)
        for (ra, rs), (amp, bulge) in relief.items():
            fa = np.clip((rs * p[..., ra] - (h[ra] - R[ra])) / max(R[ra], 1e-6), 0.0, 1.0)
            if not fa.any():
                continue
            rb2, rc2 = [x for x in range(3) if x != ra]
            wl = np.minimum(smooth(0.0, 1.0, (h[rb2] - np.abs(p[..., rb2])) / max(R[rb2], 1e-6)),
                            smooth(0.0, 1.0, (h[rc2] - np.abs(p[..., rc2])) / max(R[rc2], 1e-6)))
            lat = np.stack([q[..., rb2], q[..., rc2], np.full(q.shape[:-1], seed + ra * 3.1 + rs)], -1)
            nz = 0.65 * vnoise(lat * 9.0, seed) + 0.35 * vnoise(lat * 23.0, seed + 5.5)
            bl = (1 - (q[..., rb2] / h[rb2]) ** 2) * (1 - (q[..., rc2] / h[rc2]) ** 2)
            dd = (amp * nz + bulge * np.clip(bl, 0, 1)) * fa * wl
            disp[..., ra] += rs * dd
        q = q + disp
        for (sx, sz, rad, dep, ins) in chips:
            ff = np.clip((-p[..., 1] - (h[1] - R[1])) / max(R[1], 1e-6), 0.0, 1.0)
            dd = np.hypot(q[..., 0] - sx * h[0], q[..., 2] - sz * h[2])
            mm = smooth(0.0, 1.0, 1 - dd / rad)
            q[..., 0] -= sx * ins * mm
            q[..., 2] -= sz * ins * mm
            q[..., 1] += dep * mm * ff
        if jitter:
            q = q + jitter * np.stack([vnoise(q * 14 + o, seed + 2.2) for o in (0.0, 31.4, 62.8)], -1)
        q[..., 1] += tilt[0] * q[..., 0] + tilt[1] * q[..., 2]
        qy = q[..., 1] + h[1]
        qx, qz = q[..., 0] + h[0], q[..., 2] + h[2]
        key = (a, s)
        oo = own_off.get(key, uvoff) if own_off else uvoff
        if key in own:
            if a == 1:
                U = qx if s < 0 else 2 * h[0] - qx
                V = qz
            elif a == 0:
                U = qy if s < 0 else 2 * h[1] - qy
                V = qz
            else:
                U = qx
                V = qy if s > 0 else 2 * h[1] - qy
            U, V = U + oo[0], V + oo[1]
        else:
            if a == 1:
                U = (qx if s < 0 else 2 * h[0] - qx) + ou
                V = qz + ov
            elif a == 0:
                U = (2 * h[0] + qy if s > 0 else -qy) + ou
                V = qz + ov
            else:
                U = qx + ou
                V = (2 * h[2] + qy if s > 0 else -qy) + ov
        UVg = atlas_uv(sw, U, V)
        W = C + q[..., 0:1] * ex + q[..., 1:2] * ey + q[..., 2:3] * ez
        Nw = nrm[..., 0:1] * ex + nrm[..., 1:2] * ey + nrm[..., 2:3] * ez
        t, u = grid_to_tris(W, UVg, Nw)
        tris.append(t)
        uvs.append(u)
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 2))
    return np.concatenate(tris), np.concatenate(uvs)


def planar_uv(key, pts, nrm, rnd, shift=None):
    """Axis-aligned projection of grid points onto a swatch, centred with a random offset."""
    a = int(np.argmax(np.abs(nrm)))
    s = 1.0 if nrm[a] > 0 else -1.0
    P = pts.reshape(-1, 3)
    if a == 1:
        u, v = P[:, 0] * -s, P[:, 2]
    elif a == 0:
        u, v = P[:, 1] * s, P[:, 2]
    else:
        u, v = P[:, 0], P[:, 1] * s
    wm, hm = RECT[key][4], RECT[key][5]
    ru, rv = u.max() - u.min(), v.max() - v.min()
    f = min(1.0, (wm - 0.1) / max(ru, 1e-6), (hm - 0.1) / max(rv, 1e-6))
    u = (u - (u.max() + u.min()) / 2) * f
    v = (v - (v.max() + v.min()) / 2) * f
    cu = wm / 2 + (rnd.uniform(-0.15, 0.15) if shift is None else shift[0])
    cv = hm / 2 + (rnd.uniform(-0.1, 0.1) if shift is None else shift[1])
    return np.stack([u + cu, v + cv], -1).reshape(pts.shape[:-1] + (2,))


def quad_grid(sw, P00, P10, P11, P01, nu, nv, want, rnd, bump=None, shift=None):
    """A bilinear grid over four corners with border-zero bump noise along `want`; planar swatch UVs."""
    P00, P10, P11, P01 = (np.asarray(x, float) for x in (P00, P10, P11, P01))
    s = np.linspace(0, 1, nu + 1)[:, None, None]
    t = np.linspace(0, 1, nv + 1)[None, :, None]
    Q = (1 - s) * (1 - t) * P00 + s * (1 - t) * P10 + s * t * P11 + (1 - s) * t * P01
    want = np.asarray(want, float)
    want = want / (np.linalg.norm(want) + 1e-12)
    if bump is not None and nu > 1 and nv > 1:
        amp, freq, seed = bump
        bw = np.minimum(smooth(0.0, 0.25, np.minimum(s, 1 - s)), smooth(0.0, 0.25, np.minimum(t, 1 - t)))[..., 0]
        nz = 0.65 * vnoise(Q * freq, seed) + 0.35 * vnoise(Q * freq * 2.7, seed + 3.3)
        Q = Q + want * (amp * nz * bw)[..., None]
    UVm = planar_uv(sw, Q, want, rnd, shift)
    UV = atlas_uv(sw, UVm[..., 0], UVm[..., 1])
    N = np.broadcast_to(want, Q.shape)
    return grid_to_tris(Q, UV, N)


class Frame:
    """A wall face: P(u, v, d) is u along the face, v up from the model's bottom, d deep into the wall."""

    def __init__(self, O, ex, n):
        self.O = np.array(O, float)
        self.ex = np.array(ex, float)
        self.n = np.array(n, float)
        self.ez = np.array((0.0, 0.0, 1.0))
        self.ey = -self.n

    def P(self, u, v, d=0.0):
        return self.O + self.ex * u + self.ez * v + self.ey * d


FRONT = Frame((0, -HT, Z0), (1, 0, 0), (0, -1, 0))
BACK = Frame((0, HT, Z0), (-1, 0, 0), (0, 1, 0))

# ================================================================ masonry: laying courses, damage, building

class O(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


STAGE_CFG = {
    0: dict(miss=0.6, dark=0.9, crack=0.0, chip=0.10, push=0.0, depth=(0.05, 0.09), prof=False, spill=0),
    1: dict(miss=2.6, dark=1.0, crack=1.0, chip=0.33, push=1.3, depth=(0.10, 0.20), prof=False, spill=6),
    2: dict(miss=1.6, dark=1.0, crack=0.8, chip=0.5, push=0.0, depth=(0.10, 0.22), prof=True, spill=0),
}


def end_gap(rnd, style):
    if style == "seam":
        return rnd.uniform(0.012, 0.03)
    return 0.010


def pick_stone_sw(rnd, v):
    r = rnd.random()
    if v < 0.34 and r < 0.4:
        return "STB"
    if r < (0.30 if v < 0.8 else 0.05):
        return "STM"
    if rnd.random() < 0.03:
        return "STD"
    return rnd.choices(["ST0", "ST1", "ST2", "ST3"], [0.34, 0.28, 0.26, 0.12])[0]


def make_stone(rnd, u0, u1, v0, v1, course, vmid, plinth):
    w, h = u1 - u0, v1 - v0
    sw = pick_stone_sw(rnd, vmid)
    p = rnd.uniform(0.0, 0.02) + (plinth if course == 0 else plinth * 0.35 if course == 1 else 0.0)
    ou = rnd.uniform(0.07, max(0.075, 0.95 - w - 0.17))
    ov = 0.08 + rnd.uniform(0, 0.03) if sw in ("STM", "STB") else rnd.uniform(0.08, max(0.085, 0.8 - h - 0.17))
    chips = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            if rnd.random() < 0.10:
                chips.append((sx, sz, rnd.uniform(0.04, 0.075), rnd.uniform(0.004, 0.01), rnd.uniform(0.008, 0.02)))
    return O(u0=u0, u1=u1, v0=v0, v1=v1, p=p, r=rnd.uniform(0.012, 0.026), bulge=rnd.uniform(0.004, 0.011),
             amp=rnd.uniform(0.006, 0.014), tilt=(rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04)),
             roll=math.radians(rnd.uniform(-1.2, 1.2)), chips=chips, sw=sw, ou=ou, ov=ov, seed=rnd.uniform(0, 500),
             course=course, gone=False, quoin=None)


def lay(rnd, B, spans_for, wr=(0.24, 0.5), plinth=0.035, lead=None):
    """Courses of stones between the boundaries B: returns (stones, tiles) in face coordinates (u along the face,
    v up). spans_for(i) -> [(ua, ub, style_a, style_b, [tile_a, tile_b])]; lead(i) -> None | ('long', length) |
    ('short', skip) for the corner end of the first span (ua)."""
    n = len(B) - 1
    gvs = [0.0] + [rnd.uniform(0.012, 0.026) for _ in range(n - 1)] + [0.012]
    stones, tiles = [], []
    prev = []
    for i in range(n):
        wscale = 1.18 if i == 0 else 1.08 if i == 1 else 1.0
        cur = []
        for si, span in enumerate(spans_for(i)):
            ua, ub, ea, eb = span[:4]
            ta = span[4] if len(span) > 4 else ua
            tb = span[5] if len(span) > 5 else ub
            ld = lead(i) if (lead and si == 0) else None
            start = ua
            first_long = None
            if ld and ld[0] == "short":
                start = ua + ld[1]
            cuts = [start]
            if ld and ld[0] == "long":
                cuts.append(ua + ld[1])
                first_long = ld[1]
            while True:
                w = rnd.uniform(*wr) * wscale
                nxt = cuts[-1] + w
                if ub - nxt < 0.17:
                    cuts.append(ub)
                    break
                cuts.append(nxt)
            for j in range(1, len(cuts) - 1):
                if first_long and j == 1:
                    continue
                for pc in prev:
                    if abs(cuts[j] - pc) < 0.07:
                        for dlt in (0.09, -0.09):
                            c2 = cuts[j] + dlt
                            if cuts[j - 1] + 0.14 < c2 < cuts[j + 1] - 0.14:
                                cuts[j] = c2
                                break
            cur += cuts[1:-1]
            ng = len(cuts) - 1
            for j in range(ng):
                a, b = cuts[j], cuts[j + 1]
                if j == 0 and ld and ld[0] == "long":
                    ga = 0.0
                elif j == 0:
                    ga = end_gap(rnd, ea) if not (ld and ld[0] == "short") else 0.012
                else:
                    ga = rnd.uniform(0.012, 0.028)
                gb = end_gap(rnd, eb) if j == ng - 1 else rnd.uniform(0.012, 0.028)
                u0, u1 = a + ga / 2, b - gb / 2
                v0 = B[i] + gvs[i] / 2 + (rnd.uniform(0.0, 0.022) if rnd.random() < 0.35 else rnd.uniform(0, 0.006)) + (0.012 if i == 0 else 0.0)
                v1 = B[i + 1] - gvs[i + 1] / 2 - (rnd.uniform(0.0, 0.034) if rnd.random() < 0.35 else rnd.uniform(0, 0.012))
                ti = len(tiles)
                tiles.append(O(u0=(ta if j == 0 else a), u1=(tb if j == ng - 1 else b), v0=B[i], v1l=B[i + 1],
                               v1r=B[i + 1], sw=None, pocket=None, gone=False, dark=False, course=i))
                vm = (v0 + v1) / 2
                tiles[-1].sw = "MORM" if (vm < 0.5 and rnd.random() < 0.6) or rnd.random() < 0.08 else "MOR"
                if (v1 - v0) > 0.19 and (u1 - u0) < 0.36 and rnd.random() < 0.15 and not (j == 0 and first_long):
                    vs = v0 + (v1 - v0) * rnd.uniform(0.42, 0.58)
                    g = rnd.uniform(0.012, 0.022)
                    for (va, vb) in ((v0, vs - g / 2), (vs + g / 2, v1)):
                        s = make_stone(rnd, u0, u1, va, vb, i, (va + vb) / 2, plinth)
                        s.tile = ti
                        stones.append(s)
                else:
                    s = make_stone(rnd, u0, u1, v0, v1, i, vm, plinth)
                    s.tile = ti
                    if j == 0 and first_long:
                        s.quoin = ld[2] if len(ld) > 2 else True
                    stones.append(s)
        prev = cur
    return stones, tiles


def clip_profile(stones, tiles, pf):
    """Cut the wall down to the stepped height profile pf(u); tiles split at the steps."""
    old = list(tiles)
    tiles.clear()
    remap = {}
    for k, t in enumerate(old):
        n = max(2, int((t.u1 - t.u0) / 0.01))
        us = np.linspace(t.u0, t.u1, n + 1)
        hs = [pf(u) for u in (us[:-1] + us[1:]) / 2]
        cuts = [0]
        for i in range(1, n):
            if abs(hs[i] - hs[i - 1]) > 0.02:
                cuts.append(i)
        cuts.append(n)
        remap[k] = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            ua, ub = us[a], us[b]
            top = min(hs[a:b])
            nt = O(t)
            nt.u0, nt.u1 = ua, ub
            nt.v1l = nt.v1r = min(t.v1l, top)
            nt.gone = nt.v1l <= t.v0 + 0.03
            nt.v1l = nt.v1r = max(nt.v1l, t.v0 + 0.012)
            remap[k].append(len(tiles))
            tiles.append(nt)
    for s in stones:
        c = (s.u0 + s.u1) / 2
        best = min(remap[s.tile], key=lambda j: 0 if tiles[j].u0 <= c <= tiles[j].u1 else min(abs(tiles[j].u0 - c), abs(tiles[j].u1 - c)))
        s.tile = best
    for s in stones:
        top = min(pf(s.u0), pf(s.u1), pf((s.u0 + s.u1) / 2)) - 0.012
        if top < s.v0 + 0.07 or tiles[s.tile].gone:
            s.gone = True
        elif top < s.v1:
            s.v1 = top
            s.chips.append((1, 1, 0.09, 0.012, 0.03))
            s.chips.append((-1, 1, 0.09, 0.012, 0.03))
            s.broken = True


def damage_face(rnd, stones, tiles, cfg, area, protect):
    """Pockets where stones fell out, dark and cracked stones, chipped corners, stones pushed out."""
    live = [s for s in stones if not s.gone and not s.quoin and not protect(s)]

    def count(d):
        return int(d * area + rnd.random())

    for s in rnd.sample(live, min(len(live), count(cfg["dark"]))):
        s.sw = "STD"
    for s in live:
        if rnd.random() < cfg["chip"]:
            for _ in range(rnd.choice((1, 1, 2))):
                s.chips.append((rnd.choice((-1, 1)), rnd.choice((-1, 1)), rnd.uniform(0.07, 0.13),
                                rnd.uniform(0.01, 0.025), rnd.uniform(0.025, 0.06)))
    for s in rnd.sample(live, min(len(live), count(cfg["push"]))):
        s.p += rnd.uniform(0.03, 0.05)
        s.roll += math.radians(rnd.uniform(-4, 4))
        s.tilt = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12))
        tiles[s.tile].dark = True
    # one tile per pocket, only where every stone on it is free
    by_tile = {}
    for s in stones:
        by_tile.setdefault(s.tile, []).append(s)
    free = [s for s in live if all((x in live) for x in by_tile[s.tile]) and not tiles[s.tile].gone
            and tiles[s.tile].pocket is None and (tiles[s.tile].u1 - tiles[s.tile].u0) > 0.18
            and (tiles[s.tile].v1l - tiles[s.tile].v0) > 0.15]
    for s in rnd.sample(free, min(len(free), count(cfg["miss"]))):
        t = tiles[s.tile]
        t.pocket = rnd.uniform(*cfg["depth"])
        for x in by_tile[s.tile]:
            x.gone = True
    cr = [s for s in live if not s.gone and (s.u1 - s.u0) > 0.3 and (s.v1 - s.v0) > 0.15]
    for s in rnd.sample(cr, min(len(cr), count(cfg["crack"]))):
        s.crack = O(at=rnd.uniform(0.35, 0.65), horiz=rnd.random() < 0.3, gap=rnd.uniform(0.005, 0.011),
                    turn=math.radians(rnd.uniform(2.5, 6)))
        tiles[s.tile].dark = True


# ---------------------------------------------------------------- building

def add_tile(acc, F, t, rnd):
    """A mortar tile at the mortar plane; its UVs follow the face (u, v), so tiles split by a broken top stay
    continuous."""
    sw = "MORD" if t.dark else t.sw
    wm, hm = RECT[sw][4], RECT[sw][5]
    cu, cv, j = t.cu, t.cv, t.j
    cs = [(t.u0, t.v0), (t.u1, t.v0), (t.u1, t.v1r), (t.u0, t.v1l)]
    Q = np.array([F.P(u, v, MD) for u, v in cs]).reshape(2, 2, 3)[:, :, :]
    Q = np.array([[F.P(*cs[0], MD), F.P(*cs[3], MD)], [F.P(*cs[1], MD), F.P(*cs[2], MD)]])
    UVm = np.array([[(cs[0][0] - cu + wm / 2 + j[0], cs[0][1] - cv + hm / 2 + j[1]),
                     (cs[3][0] - cu + wm / 2 + j[0], cs[3][1] - cv + hm / 2 + j[1])],
                    [(cs[1][0] - cu + wm / 2 + j[0], cs[1][1] - cv + hm / 2 + j[1]),
                     (cs[2][0] - cu + wm / 2 + j[0], cs[2][1] - cv + hm / 2 + j[1])]])
    UV = atlas_uv(sw, UVm[..., 0], UVm[..., 1])
    tri, uv = grid_to_tris(Q, UV, np.broadcast_to(F.n, Q.shape))
    acc.add(tri, uv, "tile")


def add_pocket(acc, F, t, rnd):
    d = t.pocket
    ul, ur, vb, vtl, vtr = t.u0, t.u1, t.v0, t.v1l, t.v1r
    m = [F.P(ul, vb, MD), F.P(ur, vb, MD), F.P(ur, vtr, MD), F.P(ul, vtl, MD)]
    f = [F.P(ul, vb, d), F.P(ur, vb, d), F.P(ur, vtr, d), F.P(ul, vtl, d)]
    seed = rnd.uniform(0, 300)
    tri, uv = quad_grid("CORE", f[0], f[1], f[2], f[3], 4, 3, F.n, rnd, bump=(0.022, 14.0, seed))
    acc.add(tri, uv, "pocket")
    ez, ex = F.ez, F.ex
    for a, b, want in ((0, 1, ez), (1, 2, -ex), (2, 3, -ez), (3, 0, ex)):
        tri, uv = quad_grid("CORE", m[a], m[b], f[b], f[a], 3, 2, want, rnd, bump=(0.01, 20.0, seed + a))
        acc.add(tri, uv, "pocket")


def add_stone(acc, F, s):
    hx, hz = (s.u1 - s.u0) / 2, (s.v1 - s.v0) / 2
    uc, vc = (s.u0 + s.u1) / 2, (s.v0 + s.v1) / 2
    ry = MD + s.p + 0.006
    rl = min(s.r, hx * 0.8, hz * 0.8)
    C = F.P(uc, vc, -s.p + ry)
    ca, sa = math.cos(s.roll), math.sin(s.roll)
    ex = F.ex * ca + F.ez * sa
    ez = -F.ex * sa + F.ez * ca
    k = (max(1, round(2 * hx / 0.2)), 1, max(1, round(2 * hz / 0.14)))
    tri, uv = lump(s.sw, C, ex, F.ey, ez, (hx, ry, hz), (rl, ry, rl), STONE_FACES, relief={(1, -1): (s.amp, s.bulge)},
                   k=k, tilt=s.tilt, chips=s.chips, uvoff=(s.ou, s.ov), seed=s.seed)
    acc.add(tri, uv, "stone")


def add_quoin(acc, F, s, ret, side, pb):
    """A corner stone: its long face on F, its return (depth `ret`) showing on the other wall at u side `side`."""
    hx, hz = (s.u1 - s.u0) / 2, (s.v1 - s.v0) / 2
    uc, vc = (s.u0 + s.u1) / 2, (s.v0 + s.v1) / 2
    hy = ret / 2
    ry = MD + s.p + 0.006
    rx = MD + pb + 0.006
    C = F.P(uc, vc, -s.p + hy)
    far = "lo" if side < 0 else "hi"
    faces = {(1, -1): ("all", "all"), (0, side): ("all", "all"), (0, -side): ("lo", "all"), (1, 1): (far, "all"),
             (2, 1): ("all", "all"), (2, -1): ("all", "all")}
    ou2 = min(0.95 - ret - 0.1, s.ou + 0.5)
    k = (max(1, round(2 * hx / 0.2)), 2, max(1, round(2 * hz / 0.14)))
    tri, uv = lump(s.sw, C, F.ex, F.ey, F.ez, (hx, hy, hz), (rx, ry, 0.025), faces,
                   relief={(1, -1): (s.amp, s.bulge), (0, side): (s.amp, s.bulge)}, k=k, tilt=(0.0, 0.0),
                   chips=s.chips, uvoff=(s.ou, s.ov), own={(0, side)}, own_off={(0, side): (max(0.08, ou2), s.ov)},
                   seed=s.seed)
    acc.add(tri, uv, "quoin")


def add_shards(acc, F, s, rnd):
    """A cracked stone: two shards with a wedge-shaped gap, one slumped and turned."""
    c = s.crack
    u0, u1, v0, v1 = s.u0, s.u1, s.v0, s.v1
    parts = []
    if c.horiz:
        vm = v0 + (v1 - v0) * c.at
        parts = [(u0, u1, v0, vm - c.gap / 2, c.turn * 0.4, 0.0), (u0, u1, vm + c.gap / 2, v1, -c.turn, 0.012)]
    else:
        um = u0 + (u1 - u0) * c.at
        parts = [(u0, um - c.gap / 2, v0, v1, c.turn * 0.5, 0.0), (um + c.gap / 2, u1, v0, v1, -c.turn, 0.012)]
    for (a, b, c0, c1, roll, sink) in parts:
        t = O(s)
        t.u0, t.u1, t.v0, t.v1 = a, b, c0, c1
        t.roll = s.roll + roll
        t.p = max(0.0, s.p - sink)
        t.chips = []
        t.ou = s.ou + (a - s.u0)
        t.ov = s.ov + (c0 - s.v0)
        add_stone(acc, F, t)


def emit_face(acc, F, stones, tiles, rnd, pb_of=None):
    for t in tiles:
        if t.gone:
            continue
        if t.pocket:
            add_pocket(acc, F, t, rnd)
        else:
            add_tile(acc, F, t, rnd)
    for s in stones:
        if s.gone:
            continue
        if s.quoin:
            add_quoin(acc, F, s, s.quoin["ret"], s.quoin["side"], s.quoin["pb"])
        elif s.crack:
            add_shards(acc, F, s, rnd)
        else:
            add_stone(acc, F, s)


# ---------------------------------------------------------------- rubble, caps, ledges, cut faces

IDENT = (np.array((1.0, 0, 0)), np.array((0, 1.0, 0)), np.array((0, 0, 1.0)))
ROCK_FACES = {(a, s): ("all", "all") for a in range(3) for s in (-1, 1) if not (a == 2 and s == -1)}


def rock(acc, rnd, C, size, sw=None, yaw=None, tag="rubble"):
    """An angular chunk of broken masonry centred at C."""
    h = np.array(size, float) / 2
    ext = max(size[0], size[1]) * 0.6
    C = (min(max(C[0], -0.53 + ext), 0.53 - ext), min(max(C[1], -0.53 + ext), 0.53 - ext), C[2])
    yaw = rnd.uniform(0, 2 * math.pi) if yaw is None else yaw
    cy, sy = math.cos(yaw), math.sin(yaw)
    ex, ey, ez = np.array((cy, sy, 0.0)), np.array((-sy, cy, 0.0)), np.array((0.0, 0.0, 1.0))
    t = rnd.uniform(-0.25, 0.25)
    ez2 = ez * math.cos(t) + ex * math.sin(t)
    ex2 = ex * math.cos(t) - ez * math.sin(t)
    sw = sw or rnd.choice(["ST0", "ST1", "ST2", "ST3", "FRESH", "ST1", "ST0"])
    mw, mh = RECT[sw][4], RECT[sw][5]
    ou = rnd.uniform(0.08, max(0.085, mw - 0.5))
    ov = rnd.uniform(0.08, max(0.085, mh - 0.35))
    tri, uv = lump(sw, np.array(C, float), ex2, ey, ez2, h, (0.0, 0.0, 0.0), ROCK_FACES, k=(1, 1, 1),
                   uvoff=(ou, ov), own=set(ROCK_FACES), jitter=0.2 * float(h.min()), seed=rnd.uniform(0, 400))
    acc.add(tri, uv, tag)


def pile(acc, rnd, x0, x1, y0, y1, n, axis=1, wpos=-HT, size=(0.08, 0.26), hmax=0.3, zbase=0.0, thin=0.7):
    """Rubble heaped in the box, highest toward the wall (distance along `axis` to the wall plane `wpos`)."""
    for _ in range(n):
        x = rnd.uniform(x0, x1)
        y = rnd.uniform(y0, y1)
        dist_wall = abs((y if axis == 1 else x) - wpos)
        along = x if axis == 1 else y
        mid = (x0 + x1) / 2 if axis == 1 else (y0 + y1) / 2
        hh = hmax * smooth(0.28, 0.0, dist_wall) * (0.65 + 0.35 * math.cos((along - mid) * 2.6))
        sz = rnd.uniform(*size)
        dims = (sz * rnd.uniform(0.8, 1.5), sz * rnd.uniform(0.7, 1.3), sz * rnd.uniform(0.5, thin + 0.3))
        z = Z0 + zbase + hh * rnd.uniform(0.2, 1.0) + dims[2] * 0.4
        rock(acc, rnd, (x, y, z), dims)


def cap_lump(acc, rnd, x0, x1, y0, y1, z0, z1, gaps=(0.01, 0.01), faces=None, sw=None, chips=0.0):
    """A capstone: top, front, back and end faces, rounded, bulged."""
    hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
    C = np.array(((x0 + x1) / 2, (y0 + y1) / 2, Z0 + (z0 + z1) / 2))
    sw = sw or rnd.choice(["ST0", "ST1", "ST2", "ST0", "ST1"])
    faces = faces or {(2, 1): ("all", "all"), (1, -1): ("all", "all"), (1, 1): ("all", "all"), (0, -1): ("all", "all"),
                      (0, 1): ("all", "all")}
    ch = []
    if chips:
        for sx in (-1, 1):
            if rnd.random() < chips:
                ch.append((sx, 1, rnd.uniform(0.05, 0.09), rnd.uniform(0.005, 0.012), rnd.uniform(0.01, 0.03)))
    rel = {k: v for k, v in {(2, 1): (0.006, 0.010), (1, -1): (0.005, 0.004), (1, 1): (0.005, 0.004),
                              (0, -1): (0.005, 0.004), (0, 1): (0.005, 0.004)}.items() if k in faces}
    ou = rnd.uniform(0.08, 0.2)
    own_off = {k: (rnd.uniform(0.08, 0.3), rnd.uniform(0.08, 0.2)) for k in faces}
    tri, uv = lump(sw, C, *IDENT, (hx, hy, hz), (0.028, 0.028, min(0.028, hz)), faces, relief=rel,
                   k=(max(1, round(2 * hx / 0.22)), 2, 0), uvoff=(ou, 0.1), own=set(faces), own_off=own_off,
                   seed=rnd.uniform(0, 500), chips=ch if False else ())
    acc.add(tri, uv, "cap")


def heightfield(acc, rnd, sw, xs, ys, zfun, bump, tag="core"):
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z = np.vectorize(zfun)(X, Y)
    Q = np.stack([X, Y, Z], -1)
    amp, freq, seed = bump
    bw = np.minimum(smooth(0, 0.12, np.minimum(X - xs[0], xs[-1] - X)), smooth(0, 0.12, np.minimum(Y - ys[0], ys[-1] - Y)))
    Q[..., 2] += amp * (0.65 * vnoise(Q * freq, seed) + 0.35 * vnoise(Q * freq * 2.7, seed + 3)) * bw
    UVm = planar_uv(sw, Q, np.array((0, 0, 1.0)), rnd)
    UV = atlas_uv(sw, UVm[..., 0], UVm[..., 1])
    tri, uv = grid_to_tris(Q, UV, np.broadcast_to(np.array((0, 0, 1.0)), Q.shape))
    acc.add(tri, uv, tag)


def cut_face(acc, rnd, P0, P1, ztop0, ztop1, want, tag="end"):
    """A vertical cut through the masonry (a wall end): rough stone, in 0.4 m tall pieces so the texture tiles."""
    P0, P1 = np.array(P0, float), np.array(P1, float)
    n = max(2, int(round(np.linalg.norm(P1 - P0) / 0.14)))
    zt = max(ztop0, ztop1)
    nseg = max(1, int(math.ceil(zt / 0.4)))
    for k in range(nseg):
        za, zb = zt * k / nseg, zt * (k + 1) / nseg
        tri, uv = quad_grid(rnd.choice(["ST0", "ST1", "ST2"]), P0 + (0, 0, Z0 + za), P1 + (0, 0, Z0 + za),
                            P1 + (0, 0, Z0 + zb), P0 + (0, 0, Z0 + zb), n, 3, want, rnd,
                            bump=(0.02, 9.0, rnd.uniform(0, 300)))
        acc.add(tri, uv, tag)


# ---------------------------------------------------------------- the wall builder

class Wall:
    def __init__(self, name, stage, seed):
        self.name, self.stage, self.seed = name, stage, seed
        self.acc = Acc()
        self.rl = random.Random(seed)
        self.rd = random.Random(seed * 977 + stage * 131 + 5)
        self.rg = random.Random(seed * 31 + 7)
        self.cfg = STAGE_CFG[stage]
        self.pf_xy = None

    def pf_face(self, F):
        if not (self.cfg["prof"] and self.pf_xy):
            return None
        return lambda u: self.pf_xy(*F.P(u, 0.0, 0.0)[:2])

    def face(self, F, B, spans_for, area, protect=lambda s: False, lead=None, wr=(0.24, 0.5), flip=None, plinth=0.035,
             shift=None):
        stones, tiles = lay(self.rl, B, spans_for, wr, plinth, lead)
        if shift is not None:
            for s in stones:
                s.u0 += shift
                s.u1 += shift
            for t in tiles:
                t.u0 += shift
                t.u1 += shift
        if flip is not None:  # layout was in w (distance from the corner); u = flip - w
            for s in stones:
                s.u0, s.u1 = flip - s.u1, flip - s.u0
            for t in tiles:
                t.u0, t.u1 = flip - t.u1, flip - t.u0
        for t in tiles:
            t.cu, t.cv = (t.u0 + t.u1) / 2, (t.v0 + t.v1l) / 2
            jr = random.Random(int(abs(t.u0) * 1000) * 31 + t.course * 7 + int(F.O[0] * 10) + int(F.O[1] * 100))
            t.j = (jr.uniform(-0.12, 0.12), jr.uniform(-0.05, 0.05))
        pf = self.pf_face(F)
        if pf:
            clip_profile(stones, tiles, pf)
        damage_face(self.rd, stones, tiles, self.cfg, area, protect)
        emit_face(self.acc, F, stones, tiles, random.Random(self.seed * 13 + int(F.O[0] * 10) + int(F.O[1] * 100)))
        return stones

    def core_top(self, xs, ys, ztop, arm="x"):
        pf = self.pf_xy if self.cfg["prof"] else None
        if pf:
            if arm == "x":
                self.core_steps(xs[0], xs[-1], ys[0], ys[-1], 0, ztop)
            else:
                self.core_steps(ys[0], ys[-1], xs[0], xs[-1], 1, ztop)
            return
        heightfield(self.acc, self.rg, "CORE", xs, ys, lambda x, y: Z0 + ztop, (0.008, 7.0, self.seed + 1.0))

    def core_steps(self, t0, t1, w0, w1, axis, ztop):
        """The broken top of a wall arm: flat stepped beds of rubble core with risers between them."""
        pf = self.pf_xy
        ev = (lambda t: pf(t, 0.0)) if axis == 0 else (lambda t: pf(0.0, t))
        ts = np.arange(t0, t1 + 1e-6, 0.02)
        groups = []
        for a, b in zip(ts[:-1], ts[1:]):
            z = min(ztop, ev((a + b) / 2)) - 0.05
            if groups and abs(groups[-1][2] - z) < 0.012:
                groups[-1][1] = b
            else:
                groups.append([a, b, z])

        def P(t, w, z):
            return (t, w, Z0 + z) if axis == 0 else (w, t, Z0 + z)
        for ta, tb, z in groups:
            tri, uv = quad_grid("CORE", P(ta, w0, z), P(tb, w0, z), P(tb, w1, z), P(ta, w1, z), 2, 2, (0, 0, 1.0),
                                self.rg, bump=(0.01, 7.0, self.seed + ta))
            self.acc.add(tri, uv, "core")
        for g1, g2 in zip(groups[:-1], groups[1:]):
            t = g1[1]
            za, zb = g1[2], g2[2]
            lo, hi = min(za, zb), max(za, zb)
            sgn = 1.0 if za > zb else -1.0
            want = (sgn, 0, 0) if axis == 0 else (0, sgn, 0)
            tri, uv = quad_grid("ST1", P(t, w0, lo), P(t, w1, lo), P(t, w1, hi), P(t, w0, hi), 2, 1, want, self.rg)
            self.acc.add(tri, uv, "core")

    def top_at(self, x, y, ztop):
        return min(ztop, self.pf_xy(x, y) - 0.04) if (self.cfg["prof"] and self.pf_xy) else ztop

    def finish(self, tag):
        return finish_mesh("%s_DMG%d" % (self.name, self.stage), self.acc)


MATERIAL = None
PV_SCALE = float(os.environ.get("STONE_PV", "1.0"))
SHOTS = [x for x in os.environ.get("STONE_SHOTS", "").split(",") if x]


def finish_mesh(name, acc):
    tris = np.concatenate(acc.T)
    uvs = np.concatenate(acc.U)
    tris = tris.copy()
    tris[..., 2] = np.maximum(tris[..., 2], Z0)
    area = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    keep = area > 1e-9
    tris, uvs = tris[keep], uvs[keep]
    key = np.round(tris.reshape(-1, 3) * 2e4).astype(np.int64)
    uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    V = tris.reshape(-1, 3)[first]
    F = inv.reshape(-1, 3)
    ok = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    F, uvs = F[ok], uvs[ok]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", uvs.reshape(-1).astype(np.float32))
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(SHARP))
    me.materials.append(MATERIAL)
    obj = tk.link(bpy.data.objects.new(name, me))
    return obj, dict(acc.tags)


# ================================================================ the pieces

YS = HT - MD  # the mortar planes sit at y = -/+0.27
SLIT_B = [0.0, 0.30, 0.57, 0.82, 1.06, 1.29, 1.51, 1.73, 1.94, 2.15, 2.35, 2.55, 2.76]
SLIT_TOP = 3.0
SLIT_WIN = (5, 8)  # courses 5, 6, 7 hold the loophole
XO, XI = 0.03, 0.23  # half width of the loophole at the outer and inner mortar planes


def make_pf(points, seed):
    """Ragged remaining height along s = x (or max(x, y) on corners): piecewise linear plus a little noise."""
    xs = np.array([p[0] for p in points])
    hs = np.array([p[1] for p in points])

    step = 0.17

    def f(s):
        sw = s + 0.06 * float(vnoise(np.array((s * 7.0, 1.7, seed)), seed))
        cell = math.floor(sw / step)
        base = float(np.interp((cell + 0.5) * step, xs, hs))
        return base + 0.09 * float(vnoise(np.array((cell * 3.1, 0.5, seed)), seed + 2))
    return f


def slit_reveals(W, rnd):
    B = SLIT_B
    ys0, ys1 = -YS, YS
    pf = W.pf_xy if W.cfg["prof"] else None

    def avail(x, z):
        return pf is None or pf(x, 0.0) > z
    for sx in (-1, 1):
        Po = np.array((sx * XO, ys0))
        Pi = np.array((sx * XI, ys1))
        d = Pi - Po
        L = float(np.linalg.norm(d))
        d = d / L
        n_out = np.array((d[1], -d[0])) * (-sx)
        ey = np.array((-n_out[0], -n_out[1], 0.0))
        ez = np.array((0.0, 0.0, 1.0))
        ex = np.cross(ey, ez)
        mid = (Po + Pi) / 2
        for k in range(SLIT_WIN[0], SLIT_WIN[1]):
            v0, v1 = B[k] + 0.006, B[k + 1] - 0.006
            if pf is not None:
                top = pf(sx * (XO + XI) / 2, 0.0) - 0.01
                if top < v0 + 0.07:
                    continue
                v1 = min(v1, top)
            hz = (v1 - v0) / 2
            hy = 0.06
            Pm = np.array((mid[0], mid[1], Z0 + (v0 + v1) / 2))
            C = Pm + ey * hy
            sw = "ST3" if k != 6 else rnd.choice(["ST3", "ST0"])
            tri, uv = lump(sw, C, ex, ey, ez, (L / 2 + 0.02, hy, hz), (0.02, 0.04, 0.02), STONE_FACES,
                           relief={(1, -1): (0.004, 0.005)}, k=(2, 1, 1), uvoff=(0.1 + 0.2 * rnd.random(), 0.1),
                           seed=rnd.uniform(0, 500))
            W.acc.add(tri, uv, "reveal")
    for (zz, want, sw) in ((B[SLIT_WIN[0]], (0, 0, 1.0), "ST3"), (B[SLIT_WIN[1]], (0, 0, -1.0), "ST3")):
        if pf is not None and not (pf(0.0, 0.0) > zz + 0.0 or pf(-XI, 0.0) > zz):
            continue
        z = Z0 + zz
        tri, uv = quad_grid(sw, (-XO, ys0, z), (XO, ys0, z), (XI, ys1, z), (-XI, ys1, z), 3, 4, want, rnd,
                            bump=(0.004, 16.0, 17.0))
        W.acc.add(tri, uv, "reveal")
        # the reveal's flanks of the same plane (outside the trapezoid) are masonry; nothing more to add


def build_slit(stage):
    W = Wall("ArrowSlitWall", stage, 101)
    cfg = W.cfg
    B = SLIT_B
    if cfg["prof"]:
        g = make_pf([(-0.5, 1.95), (-0.32, 1.62), (-0.1, 1.05), (0.1, 0.80), (0.28, 1.18), (0.5, 1.40)], 3.0)
        W.pf_xy = lambda x, y: g(x)

    def sp_front(i):
        if SLIT_WIN[0] <= i < SLIT_WIN[1]:
            return [(-0.5, -XO, "seam", "edge"), (XO, 0.5, "edge", "seam")]
        return [(-0.5, 0.5, "seam", "seam")]

    def sp_back(i):
        if SLIT_WIN[0] <= i < SLIT_WIN[1]:
            return [(-0.5, -XI, "seam", "edge"), (XI, 0.5, "edge", "seam")]
        return [(-0.5, 0.5, "seam", "seam")]

    def prot(s):
        return SLIT_WIN[0] <= s.course < SLIT_WIN[1] and abs((s.u0 + s.u1) / 2) < 0.4 or s.course >= len(B) - 2 and False
    area = 1.0 * B[-1]
    W.face(FRONT, B, sp_front, area, prot)
    W.face(BACK, B, sp_back, area, prot)
    slit_reveals(W, random.Random(55))
    xs = np.linspace(-0.5, 0.5, 11)
    W.core_top(xs, np.linspace(-YS, YS, 4), B[-1])
    for xe, want in ((-0.5, (-1, 0, 0)), (0.5, (1, 0, 0))):
        t = W.top_at(xe, 0.0, B[-1])
        cut_face(W.acc, W.rg, (xe, -YS, 0), (xe, YS, 0), t, t, want)
    if not cfg["prof"]:
        rc = random.Random(77)
        cut = rc.uniform(-0.12, 0.12)
        for (a, b) in ((-0.5, cut), (cut, 0.5)):
            ga = rc.uniform(0.012, 0.03) / 2 if a == -0.5 else 0.007
            gb = rc.uniform(0.012, 0.03) / 2 if b == 0.5 else 0.007
            cap_lump(W.acc, random.Random(int(a * 1000) + 5), a + ga, b - gb, -0.335, 0.335, B[-1], SLIT_TOP)
    slit_rubble(W)
    return W


def slit_rubble(W):
    rd, acc = W.rd, W.acc
    if W.stage == 1:
        pile(acc, rd, -0.5, 0.5, -0.52, -0.31, 5, size=(0.05, 0.12), hmax=0.12)
        pile(acc, rd, -0.5, 0.5, 0.31, 0.52, 2, size=(0.05, 0.11), hmax=0.1)
    elif W.stage == 2:
        pile(acc, rd, -0.52, 0.52, -0.54, -0.30, 24, size=(0.08, 0.30), hmax=0.45)
        pile(acc, rd, -0.52, 0.52, 0.30, 0.54, 14, size=(0.08, 0.26), hmax=0.36, wpos=HT)
        for _ in range(6):
            x = rd.uniform(-0.45, 0.45)
            top = W.top_at(x, 0.0, SLIT_B[-1])
            sz = rd.uniform(0.09, 0.2)
            rock(acc, rd, (x, rd.uniform(-0.2, 0.2), Z0 + top + sz * 0.3), (sz * 1.3, sz, sz * 0.7))


def corner_plan(seed, n):
    q = random.Random(seed)
    return dict(Lq=[q.uniform(0.40, 0.50) for _ in range(n)], ret=[q.uniform(0.20, 0.25) for _ in range(n)],
                pa=[q.uniform(0.0, 0.015) for _ in range(n)], pb=[q.uniform(0.0, 0.015) for _ in range(n)])


FB = Frame((-HT, 0, Z0), (0, -1, 0), (-1, 0, 0))
FD = Frame((HT, 0, Z0), (0, 1, 0), (1, 0, 0))
SIDE_R = Frame((HT + MD, 0, Z0), (0, 1, 0), (1, 0, 0))
SIDE_L = Frame((-HT - MD, 0, Z0), (0, -1, 0), (-1, 0, 0))
SIDE_F = Frame((0, HT + MD, Z0), (-1, 0, 0), (0, 1, 0))


def corner_faces(W, B, plan, spans_AB, area, prot=lambda s: False):
    """The two outer faces with their alternating quoins; spans_AB(i) -> (w0, w1, style_b)."""
    def sp(i):
        w1, eb = spans_AB(i)
        return [(0.0, w1, "corner", eb, MD, w1)]

    def lead_a(i):
        if i % 2 == 0:
            return ("long", plan["Lq"][i], dict(ret=plan["ret"][i], side=-1, pb=plan["pb"][i]))
        return ("short", plan["ret"][i] + 0.014)

    def lead_b(i):
        if i % 2 == 1:
            return ("long", plan["Lq"][i], dict(ret=plan["ret"][i], side=1, pb=plan["pa"][i]))
        return ("short", plan["ret"][i] + 0.014)
    W.face(FRONT, B, sp, area, prot, lead=lead_a, shift=-HT)
    W.face(FB, B, sp, area, prot, lead=lead_b, flip=HT)


def build_slit_corner(stage):
    W = Wall("ArrowSlitCorner", stage, 202)
    B = SLIT_B
    if W.cfg["prof"]:
        g = make_pf([(-0.3, 1.9), (-0.1, 1.55), (0.1, 1.05), (0.3, 0.8), (0.5, 1.2)], 5.0)
        W.pf_xy = lambda x, y: g(max(x, y))
    plan = corner_plan(31, len(B) - 1)
    corner_faces(W, B, plan, lambda i: (0.8, "seam"), 0.8 * B[-1])
    spc = lambda i: [(-0.5, -0.3, "seam", "edge", -0.5, -YS)]  # noqa: E731
    spd = lambda i: [(0.3, 0.5, "edge", "seam", YS, 0.5)]  # noqa: E731
    W.face(BACK, B, spc, 0.2 * B[-1], wr=(0.3, 0.5))
    W.face(FD, B, spd, 0.2 * B[-1], wr=(0.3, 0.5))
    W.core_top(np.linspace(-YS, 0.5, 9), np.linspace(-YS, YS, 4), B[-1])
    W.core_top(np.linspace(-YS, YS, 4), np.linspace(YS, 0.5, 3), B[-1], arm="y")
    t = W.top_at(0.5, 0.0, B[-1])
    cut_face(W.acc, W.rg, (0.5, -YS, 0), (0.5, YS, 0), t, t, (1, 0, 0))
    t = W.top_at(0.0, 0.5, B[-1])
    cut_face(W.acc, W.rg, (-YS, 0.5, 0), (YS, 0.5, 0), t, t, (0, 1, 0))
    if not W.cfg["prof"]:
        rc = random.Random(88)
        cap_lump(W.acc, rc, -0.335, 0.335, -0.335, 0.335, B[-1], SLIT_TOP)
        cap_lump(W.acc, rc, 0.345, 0.5 - 0.01, -0.335, 0.335, B[-1], SLIT_TOP)
        cap_lump(W.acc, rc, -0.335, 0.335, 0.345, 0.5 - 0.01, B[-1], SLIT_TOP)
    rd, acc = W.rd, W.acc
    if W.stage == 1:
        pile(acc, rd, -0.4, 0.5, -0.52, -0.31, 4, size=(0.05, 0.12), hmax=0.12)
        pile(acc, rd, -0.52, -0.31, -0.3, 0.5, 3, axis=0, wpos=-HT, size=(0.05, 0.12), hmax=0.12)
    elif W.stage == 2:
        pile(acc, rd, -0.4, 0.52, -0.54, -0.30, 12, size=(0.08, 0.30), hmax=0.42)
        pile(acc, rd, -0.54, -0.30, -0.3, 0.52, 12, axis=0, wpos=-HT, size=(0.08, 0.30), hmax=0.42)
        pile(acc, rd, 0.30, 0.54, 0.3, 0.52, 5, axis=0, wpos=HT, size=(0.08, 0.2), hmax=0.3)
        for _ in range(5):
            x, y = rd.uniform(-0.2, 0.4), rd.uniform(-0.2, 0.2)
            sz = rd.uniform(0.09, 0.2)
            rock(acc, rd, (x, y, Z0 + W.top_at(x, y, B[-1]) + sz * 0.3), (sz * 1.3, sz, sz * 0.7))
    return W


BAT_B = [0.0, 0.26, 0.47, 0.62, 0.88]
BAT_TOP = 1.0
BAT_M = [0.62, 0.88]  # merlon courses
MERLON = 0.3
BAT_LED = (0.47, 0.62)


def ledge(W, rnd, x0, x1, y0, y1, faces):
    faces = {k: ("all", "all") for k in faces}
    cap_lump(W.acc, rnd, x0, x1, y0, y1, BAT_LED[0], BAT_LED[1], faces=faces, sw=None)


def bat_pf(seed, corner):
    pts = [(-0.5, 0.52), (-0.25, 0.30), (0.0, 0.46), (0.22, 0.20), (0.5, 0.36)]
    if corner:
        pts = [(-0.3, 0.58), (-0.1, 0.42), (0.1, 0.25), (0.3, 0.34), (0.5, 0.20)]
    g = make_pf(pts, seed)
    return g


def build_bat(stage):
    W = Wall("Battlement", stage, 303)
    cfg = W.cfg
    B = BAT_B
    if cfg["prof"]:
        g = bat_pf(2.0, False)
        W.pf_xy = lambda x, y: g(x)

    def sp(i):
        if i < 2:
            return [(-0.5, 0.5, "seam", "seam")]
        return [(-MERLON, MERLON, "edge", "edge")]
    W.face(FRONT, B, sp, 0.9)
    W.face(BACK, B, sp, 0.9)
    if not cfg["prof"]:
        for F in (SIDE_R, SIDE_L):
            W.face(F, BAT_M, lambda i: [(-0.29, 0.29, "edge", "edge", -YS, YS)], 0.2, wr=(0.3, 0.5))
        rc = random.Random(19)
        for sx in (-1, 1):
            a, b = sorted((sx * 0.5 + (-0.012 * sx), sx * MERLON))
            ledge(W, rc, a, b, -HT, HT, [(2, 1), (1, -1), (1, 1), (0, sx)])
        cap_lump(W.acc, rc, -0.33, 0.33, -0.31, 0.31, B[-1], BAT_TOP)
    W.core_top(np.linspace(-0.5, 0.5, 9), np.linspace(-YS, YS, 4), BAT_LED[0] if not cfg["prof"] else 0.9)
    for xe, want in ((-0.5, (-1, 0, 0)), (0.5, (1, 0, 0))):
        t = W.top_at(xe, 0.0, BAT_LED[0])
        cut_face(W.acc, W.rg, (xe, -YS, 0), (xe, YS, 0), t, t, want)
    rd, acc = W.rd, W.acc
    if W.stage == 1:
        pile(acc, rd, -0.5, 0.5, -0.52, -0.31, 3, size=(0.05, 0.11), hmax=0.1)
        pile(acc, rd, -0.5, 0.5, 0.31, 0.52, 1, size=(0.05, 0.1), hmax=0.1)
    elif W.stage == 2:
        pile(acc, rd, -0.52, 0.52, -0.54, -0.30, 9, size=(0.07, 0.24), hmax=0.3)
        pile(acc, rd, -0.52, 0.52, 0.30, 0.54, 6, size=(0.07, 0.22), hmax=0.26, wpos=HT)
        for _ in range(4):
            x = rd.uniform(-0.45, 0.45)
            sz = rd.uniform(0.08, 0.17)
            rock(acc, rd, (x, rd.uniform(-0.15, 0.15), Z0 + W.top_at(x, 0.0, B[-1]) + sz * 0.3),
                 (sz * 1.3, sz, sz * 0.7))
    return W


def build_bat_corner(stage):
    W = Wall("BattlementCorner", stage, 404)
    cfg = W.cfg
    B = BAT_B
    if cfg["prof"]:
        g = bat_pf(4.0, True)
        W.pf_xy = lambda x, y: g(max(x, y))
    plan = corner_plan(41, len(B) - 1)

    def span_ab(i):
        return (0.8, "seam") if i < 2 else (0.6, "edge")
    corner_faces(W, B, plan, span_ab, 0.7)
    Bl = [0.0, 0.26, 0.47]
    W.face(BACK, Bl, lambda i: [(-0.5, -0.3, "seam", "edge", -0.5, -YS)], 0.2, wr=(0.3, 0.5))
    W.face(FD, Bl, lambda i: [(0.3, 0.5, "edge", "seam", YS, 0.5)], 0.2, wr=(0.3, 0.5))
    if not cfg["prof"]:
        for F in (SIDE_R, SIDE_F):
            W.face(F, BAT_M, lambda i: [(-0.29, 0.29, "edge", "edge", -YS, YS)], 0.2, wr=(0.3, 0.5))
        rc = random.Random(29)
        ledge(W, rc, MERLON, 0.5 - 0.012, -HT, HT, [(2, 1), (1, -1), (1, 1), (0, 1)])
        ledge(W, rc, -HT, HT, MERLON, 0.5 - 0.012, [(2, 1), (0, -1), (0, 1), (1, 1)])
        cap_lump(W.acc, rc, -0.31, 0.33, -0.31, 0.33, B[-1], BAT_TOP)
    ztop = BAT_LED[0] if not cfg["prof"] else 0.9
    W.core_top(np.linspace(-YS, 0.5, 9), np.linspace(-YS, YS, 4), ztop)
    W.core_top(np.linspace(-YS, YS, 4), np.linspace(YS, 0.5, 3), ztop, arm="y")
    t = W.top_at(0.5, 0.0, BAT_LED[0])
    cut_face(W.acc, W.rg, (0.5, -YS, 0), (0.5, YS, 0), t, t, (1, 0, 0))
    t = W.top_at(0.0, 0.5, BAT_LED[0])
    cut_face(W.acc, W.rg, (-YS, 0.5, 0), (YS, 0.5, 0), t, t, (0, 1, 0))
    rd, acc = W.rd, W.acc
    if W.stage == 1:
        pile(acc, rd, -0.4, 0.5, -0.52, -0.31, 3, size=(0.05, 0.11), hmax=0.1)
        pile(acc, rd, -0.52, -0.31, -0.3, 0.5, 2, axis=0, wpos=-HT, size=(0.05, 0.11), hmax=0.1)
    elif W.stage == 2:
        pile(acc, rd, -0.4, 0.52, -0.54, -0.30, 7, size=(0.07, 0.24), hmax=0.3)
        pile(acc, rd, -0.54, -0.30, -0.3, 0.52, 7, axis=0, wpos=-HT, size=(0.07, 0.24), hmax=0.3)
        pile(acc, rd, 0.30, 0.54, 0.3, 0.52, 3, axis=0, wpos=HT, size=(0.07, 0.18), hmax=0.2)
    return W


PIECES = [  # export name, builder, FX point (front face, mid height)
    ("ArrowSlitWall", build_slit, (0.0, -0.34, Z0 + 1.5)),
    ("ArrowSlitCorner", build_slit_corner, (0.1, -0.34, Z0 + 1.5)),
    ("Battlement", build_bat, (0.0, -0.33, Z0 + 0.5)),
    ("BattlementCorner", build_bat_corner, (0.1, -0.33, Z0 + 0.5)),
]

# PIECES2_BELOW

# ================================================================ previews

ALL = []


def stage_scene():
    tk.preview_stage()
    floor = bpy.data.objects["Floor"]
    floor.data.transform(Matrix.Translation((0.5, 0.5, 0.0)) @ Matrix.Scale(4.0, 4))
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (0.0, 0.0, 0.0)


def figure_at(x, y):
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)


def lineup(entries, cam, path, res=(1800, 1100), samples=64, show=()):
    """entries: (object, (x, y), z rotation in degrees)."""
    for o in ALL:
        o.hide_render = o not in show
    temps = []
    for obj, (x, y), rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = (x, y, 0.0)
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    tk.render(cam, path, res=res, samples=samples)
    for t in temps:
        bpy.data.objects.remove(t)


MATERIAL = tk.baked_material(MAT_NAME, PATHS)
assert MATERIAL.name == MAT_NAME, MATERIAL.name
BUILT = {}


def stats(o):
    co = np.array([v.co[:] for v in o.data.vertices])
    return co.min(0), co.max(0), len(o.data.polygons)


def make(key, builder):
    meshes = []
    for s in range(3):
        u0_ = UVWARN[0]
        W = builder(s)
        log(key, 'DMG%d uv clamps' % s, UVWARN[0] - u0_)
        obj, by = W.finish(key)
        lo, hi, tris = stats(obj)
        log("%s DMG%d: %d tris %s bounds %s..%s" % (key, s, tris, by, lo.round(3), hi.round(3)))
        meshes.append(obj)
    BUILT[key] = meshes
    ALL.extend(meshes)




def lineup(entries, cam, path, res=(1500, 950), samples=48, show=()):
    """entries: (object, (x, y[, z]), z rotation in degrees)."""
    if SHOTS and not any(k in os.path.basename(path) for k in SHOTS):
        return
    for o in ALL:
        o.hide_render = o not in show
    temps = []
    for obj, loc, rz in entries:
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.location = tuple(loc) + ((0.0,) if len(loc) == 2 else ())
        t.rotation_euler = (0.0, 0.0, math.radians(rz))
        temps.append(t)
    k = PV_SCALE
    tk.render(cam, path, res=(int(res[0] * k), int(res[1] * k)), samples=max(8, int(samples * min(1.0, k * 1.5))))
    for t in temps:
        bpy.data.objects.remove(t)


def export_piece(fname, meshes, fx):
    saved, objs = [], []
    for i, m in enumerate(meshes):
        saved.append((m, m.name, m.data.name))
        m.name = "DMG%d" % i
        m.data.name = "DMG%d" % i
        objs.append(m)
    empty = tk.link(bpy.data.objects.new("FX", None))
    empty.empty_display_size = 0.1
    empty.location = fx
    objs.append(empty)
    tk.export_fbx(objs, os.path.join(ASSETS, fname))
    bpy.data.objects.remove(empty)
    for m, n, dn in saved:
        m.name = n
        m.data.name = dn


DEV = ("ArrowSlitWall",) if MODE == "dev" else tuple(p[0] for p in PIECES)
for name, builder, fx in PIECES:
    if name in DEV:
        make(name, builder)
log("uv clamps (should be 0):", UVWARN[0], UVBY)

REPORT = []
if MODE != "dev":
    for name, builder, fx in PIECES:
        export_piece(name + ".fbx", BUILT[name], fx)
        for i, m in enumerate(BUILT[name]):
            lo, hi, tris = stats(m)
            REPORT.append("%s.fbx DMG%d: %d tris, bounds %s .. %s" % (name, i, tris, lo.round(3), hi.round(3)))
        REPORT.append("%s.fbx FX at %s" % (name, fx))
    for line in REPORT:
        log(line)
    if MODE == "export":
        sys.exit(0)

if os.environ.get("STONE_EEVEE"):
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 16
stage_scene()
CAMS = {"front": ((1.3, -7.4, 2.0), (0.0, 0.0, 0.95), 35), "back": ((-1.3, 7.4, 2.0), (0.0, 0.0, 0.95), 35)}
SHORT = {"front": ((1.1, -5.2, 1.2), (0.0, 0.0, 0.35), 35), "back": ((-1.1, 5.2, 1.2), (0.0, 0.0, 0.35), 35)}
for name in DEV:
    m = BUILT[name]
    ents = [(m[0], (-1.5, 0.0), 0), (m[1], (0.0, 0.0), 0), (m[2], (1.5, 0.0), 0)]
    figure_at(2.8, 0.6)
    tall = name.startswith("ArrowSlit")
    for side, (loc, tgt, lens) in (CAMS if tall else SHORT).items():
        lineup(ents, tk.camera("St_%s_%s" % (name, side), loc, tgt, lens=lens),
               os.path.join(PREVIEWS, "stone_%s_stages%s.png" % (name, "" if side == "front" else "_back")))

S0 = BUILT["ArrowSlitWall"][0]
S1, S2 = BUILT["ArrowSlitWall"][1], BUILT["ArrowSlitWall"][2]
figure_at(1.4, -0.8)
lineup([(S0, (0.0, 0.0), 0)], tk.camera("Close1", (0.35, -1.5, 1.45), (0.0, 0.0, 1.3), lens=40),
       os.path.join(PREVIEWS, "stone_close_slit.png"), res=(1300, 1000))
lineup([(S0, (0.0, 0.0), 0)], tk.camera("Close3", (0.4, -3.3, 1.5), (0.0, 0.0, 1.0), lens=35),
       os.path.join(PREVIEWS, "stone_view_3m.png"), res=(1300, 1000))
lineup([(S0, (0.0, 0.0), 0)], tk.camera("Inside", (-0.2, 1.4, 1.35), (0.0, 0.0, 1.2), lens=35),
       os.path.join(PREVIEWS, "stone_inside_slit.png"), res=(1300, 1000))
lineup([(S1, (0.0, 0.0), 0)], tk.camera("Close1b", (0.6, -1.6, 0.8), (0.0, 0.0, 0.6), lens=40),
       os.path.join(PREVIEWS, "stone_close_dmg1.png"), res=(1300, 1000))
lineup([(S2, (0.0, 0.0), 0)], tk.camera("Close2", (0.9, -1.9, 0.9), (0.0, 0.0, 0.4), lens=40),
       os.path.join(PREVIEWS, "stone_close_dmg2.png"), res=(1300, 1000))

if MODE != "dev":
    SC, BT, BC = BUILT["ArrowSlitCorner"][0], BUILT["Battlement"][0], BUILT["BattlementCorner"][0]
    row = [(SC, (0.0, 0.0), 0), (S0, (1.0, 0.0), 0), (S0, (2.0, 0.0), 180), (S0, (3.0, 0.0), 0), (S0, (0.0, 1.0), -90),
           (S0, (0.0, 2.0), -90),
           (BC, (0.0, 0.0, 3.0), 0), (BT, (1.0, 0.0, 3.0), 0), (BT, (2.0, 0.0, 3.0), 180), (BT, (3.0, 0.0, 3.0), 0),
           (BT, (0.0, 1.0, 3.0), -90), (BT, (0.0, 2.0, 3.0), -90)]
    figure_at(2.2, -1.2)
    lineup(row, tk.camera("RowF", (-2.6, -5.6, 3.4), (1.3, 0.5, 1.7), lens=30), os.path.join(PREVIEWS, "stone_row.png"))
    lineup(row, tk.camera("RowB", (3.6, 4.4, 3.4), (0.8, 0.6, 1.7), lens=30),
           os.path.join(PREVIEWS, "stone_row_back.png"))
    lineup(row, tk.camera("RowC", (-1.0, -2.2, 3.9), (0.4, 0.4, 3.2), lens=30),
           os.path.join(PREVIEWS, "stone_row_top.png"), res=(1500, 950))
    # a low wall of battlements on their own, and the corners close
    figure_at(2.3, -1.0)
    low = [(BC, (0.0, 0.0), 0), (BT, (1.0, 0.0), 0), (BT, (2.0, 0.0), 180), (BT, (3.0, 0.0), 0), (BT, (0.0, 1.0), -90)]
    lineup(low, tk.camera("LowF", (1.8, -4.2, 1.7), (1.4, 0.4, 0.4), lens=32), os.path.join(PREVIEWS, "stone_low_wall.png"))
    lineup([(SC, (0.0, 0.0), 0)], tk.camera("CornerC", (-1.4, -1.5, 1.6), (0.0, 0.0, 1.2), lens=35),
           os.path.join(PREVIEWS, "stone_corner_close.png"), res=(1300, 1000))
    lineup([(BT, (0.0, 0.0), 0)], tk.camera("BatC", (0.9, -1.5, 0.9), (0.0, 0.0, 0.3), lens=38),
           os.path.join(PREVIEWS, "stone_battlement_close.png"), res=(1300, 1000))
    if ICON:
        for o in ALL:
            o.hide_render = o is not S0
        hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not S0}
        tk.icon(tk.camera("Icon", (2.4, -4.6, 2.5), (0.0, 0.0, 1.0), lens=50), ICON, hide=hide, target=(0.0, 0.0, 1.0))
        log("icon", ICON)

    # check the files as the importer sees them
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for fname in sorted(os.listdir(ASSETS)):
        if not fname.endswith(".fbx"):
            continue
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.import_scene.fbx(filepath=os.path.join(ASSETS, fname))
        parts = []
        for o in sorted(bpy.data.objects, key=lambda o: o.name):
            if o.type == "MESH":
                co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
                parts.append("%s tris %d mat %s z %.3f..%.3f" % (o.name, sum(len(p.vertices) - 2 for p in o.data.polygons),
                                                                 [m.name for m in o.data.materials], co[:, 2].min(),
                                                                 co[:, 2].max()))
            else:
                parts.append("%s %s at %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation)))
        log("reimport", fname, "|", " || ".join(parts))
log("done")
