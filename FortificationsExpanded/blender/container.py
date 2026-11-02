"""Container Wall (Fortifications Expanded): three block models that share one baked 2048 atlas, `Container`.

    ContainerWall.fbx    DMG0, DMG1, DMG2 + FX empty    3 wide, 3 tall, 1 deep
    ContainerCorner.fbx  DMG0, DMG1, DMG2 + FX empty    1 by 1, 3 tall (outer faces -X and -Y)
    ContainerGate.fbx    Frame, LeftLeaf, RightLeaf     3 wide, 3 tall; the leaves are children of Frame, each with its
                                                        origin on its hinge axis, built closed, opening out toward -Y

A wall cut and welded from shipping containers by survivors: vertical trapezoid corrugation on both faces, corner
posts with ISO castings, top and bottom rails, a corrugated roof, the cut ends capped with welded scrap plate, a
patch or two, stencilled ID codes and a faded made-up shipping-line logo ("KORVAN LINES"). DMG1 adds dents, claw
scrapes, bullet holes and a sprung seam; DMG2 a big torn hole, a sheet peeled back into the wall, a bent corner post
and rust-through. The gate is a classic container door pair in a header-and-posts frame.

Tint: the game colours these per block, so the painted steel is a light neutral grey in the albedo and the RMOM
alpha is the paint mask (1 where paint shows; 0 on rust, bare steel, stencils, castings, welds, plates, rubber).
The mask is baked from the paint material's own paint/rust/bare mix, like the other maps.

A kit (corrugated half-panels intact, dented, holed, torn, peeled and rusted through; posts, castings, rails, roof,
end caps, welds, patches, liner, door parts) is built in its design pose, baked once, and every piece is assembled
from copies of the baked parts (moved, mirrored, clipped and bent, keeping their UVs).

    blender -b --factory-startup --python container.py -- <unity asset folder> <preview folder> <icon file> [mode]

mode: all (default); fast (no bake: the pieces rendered with the procedural kit materials, for quick checks)
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
ASSETS, PREVIEWS, ICON = (os.path.abspath(a) for a in args[:3])
MODE = args[3] if len(args) > 3 else "all"
for _d in (ASSETS, PREVIEWS, os.path.dirname(ICON)):
    os.makedirs(_d, exist_ok=True)
FAST = MODE == "fast"

MAT_NAME = "Container"
Z0, ZT = -0.5, 2.5
# ISO corner casting: along the wall (x), across it (y), height
CX, CY, CZ = 0.178, 0.162, 0.118
PO = 0.006                   # posts sit this far behind the castings' outer faces
PW = 0.15                    # corner post width
XPO, XPI = 1.5 - PO, 1.5 - PO - PW          # post outer / inner x (front-right corner)
YPO, YPI = -0.5 + PO, -0.5 + PO + PW        # post front / back y
RB_TOP = -0.36               # bottom rail top
RT_BOT, RT_TOP = 2.41, 2.49  # top rail
YR = -0.49                   # rail front face
YS = -0.486                  # corrugation crests
DEPTH = 0.045
YIN = YS + DEPTH             # corrugation valleys
ZM = (RB_TOP + RT_BOT) / 2   # seam between the lower and upper kit half-panels
MOD_X = {"A": -0.9, "B": 0.0, "C": 0.9}
WALL_SEGS = [(0.08, YIN), (0.07, YS), (0.08, YS), (0.07, YIN)] * 3
HALF_Z = {"L": (RB_TOP, ZM), "U": (ZM, RT_BOT)}

# gate
GXH, GYH = 1.326, -0.44      # hinge axis |x| and y
LX_OUT, LX_IN = 1.32, 0.004  # leaf outer / meeting edge |x|
LZ0, LZ1 = -0.39, 2.19       # leaf bottom / top
LYF, LYB = -0.42, -0.37      # leaf frame front / back
LFW = 0.06                   # leaf frame width
PX0, PX1 = LX_OUT - LFW, LX_IN + LFW      # door panel |x| span (left leaf: -1.26 .. -0.064)
PZ0, PZ1 = LZ0 + LFW, LZ1 - LFW           # door panel z span
DZM = 0.9
DYS, DDEPTH = -0.416, 0.025
DYIN = DYS + DDEPTH
HDR_BOT = 2.2                # gate header underside
BAR_X = (-0.98, -0.36)       # locking bars (left leaf)
BAR_Y, BAR_R = -0.455, 0.017
HANDLE_Z = 0.7
HINGE_Z = (-0.22, 0.48, 1.38, 2.02)
OPEN_DEG = 95.0

PAINT = 0.5                  # neutral paint grey (linear); the game's tint multiplies it
STENCIL = (0.6, 0.59, 0.555)
BARE = (0.40, 0.395, 0.385)
DIRT = (0.045, 0.038, 0.03)
DUST = (0.27, 0.225, 0.165)
HOLE = (0.008, 0.007, 0.006)

FONTS = "C:/Windows/Fonts/"
F_BOLD, F_BLACK, F_NARROW = FONTS + "arialbd.ttf", FONTS + "ariblk.ttf", FONTS + "ARIALNB.TTF"


def log(*a):
    print("[container]", *a, flush=True)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def clamp01(x):
    return min(1.0, max(0.0, x))


def fbm(p, octaves=3, seed=0.0):
    v, amp, f = 0.0, 0.5, 1.0
    for _ in range(octaves):
        v += amp * noise.noise(Vector((p[0] * f + seed * 7.31, p[1] * f + seed * 3.17, p[2] * f + seed * 1.93)))
        amp *= 0.5
        f *= 2.03
    return v


def Tm(x, y, z):
    return Matrix.Translation((x, y, z))


def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Z")


def Ry(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Y")


def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, "X")


def Sc(x, y, z):
    return Matrix.Diagonal((x, y, z, 1.0))


def corner_M(cx, cy, sx, sy, top=False, design=(1.5, -0.5)):
    """Moves a part built at the front-right corner (outer sides +X and -Y, corner point `design`) to the corner at
    (cx, cy) whose outer sides face (sx, sy), by mirroring (castings and posts keep their proportions); `top` flips
    a bottom part (a casting) to the top of the 3 m piece."""
    M = Tm(-design[0], -design[1], 0.0)
    if top:
        M = Tm(0.0, 0.0, Z0 + ZT) @ Sc(1, 1, -1) @ M
    return Tm(cx, cy, 0.0) @ Sc(sx, -sy, 1) @ M


# ---------------------------------------------------------------- decals: stencils and damage, painted with numpy
# One frame for all of them: x -1.5..1.5, z -0.5..2.5 of the front face (the wall's and the gate doors' design pose)

DRES = 2048
PXM = DRES / 3.0


def blank():
    return np.zeros((DRES, DRES), np.float32)


def win(cx, cz, rx, rz):
    i0 = max(0, int((cx - rx + 1.5) * PXM))
    i1 = min(DRES, int((cx + rx + 1.5) * PXM) + 1)
    j0 = max(0, int((cz - rz + 0.5) * PXM))
    j1 = min(DRES, int((cz + rz + 0.5) * PXM) + 1)
    X = (np.arange(i0, i1) + 0.5) / PXM - 1.5
    Z = (np.arange(j0, j1) + 0.5) / PXM - 0.5
    XX, ZZ = np.meshgrid(X, Z)
    return (slice(j0, j1), slice(i0, i1)), XX, ZZ


def raster(tris, ss=3):
    """Coverage of a set of 2D triangles (meters, x/z) on the decal frame, supersampled."""
    out = blank()
    P = (np.asarray(tris, np.float64) + np.array([1.5, 0.5])) * PXM
    o = (np.arange(ss) + 0.5) / ss
    for t in P:
        (ax, ay), (bx, by), (cx_, cy_) = t
        if abs((bx - ax) * (cy_ - ay) - (by - ay) * (cx_ - ax)) < 1e-9:
            continue
        x0, x1 = max(0, int(np.floor(t[:, 0].min()))), min(DRES, int(np.ceil(t[:, 0].max())))
        y0, y1 = max(0, int(np.floor(t[:, 1].min()))), min(DRES, int(np.ceil(t[:, 1].max())))
        if x1 <= x0 or y1 <= y0:
            continue
        gx = (np.arange(x0, x1)[:, None] + o[None, :]).ravel()
        gy = (np.arange(y0, y1)[:, None] + o[None, :]).ravel()
        X, Y = np.meshgrid(gx, gy)
        w0 = (bx - ax) * (Y - ay) - (by - ay) * (X - ax)
        w1 = (cx_ - bx) * (Y - by) - (cy_ - by) * (X - bx)
        w2 = (ax - cx_) * (Y - cy_) - (ay - cy_) * (X - cx_)
        ins = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        out[y0:y1, x0:x1] += ins.reshape(y1 - y0, ss, x1 - x0, ss).mean(axis=(1, 3))
    return np.clip(out, 0.0, 1.0)


def text_tris(body, size, x, z, font, align="LEFT", spacing=1.0, shear=0.0):
    cu = bpy.data.curves.new("DecalText", "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.shear = shear
    cu.resolution_u = 10
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    ob = tk.link(bpy.data.objects.new("DecalText", cu))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    me.calc_loop_triangles()
    co = np.array([v.co[:2] for v in me.vertices], np.float64)
    tri = np.array([lt.vertices[:] for lt in me.loop_triangles], np.int64)
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)
    return co[tri] + np.array([x, z])


def rect_ring(x0, z0, x1, z1, w):
    out = blank()
    sl, X, Z = win((x0 + x1) / 2, (z0 + z1) / 2, (x1 - x0) / 2 + 0.01, (z1 - z0) / 2 + 0.01)
    inside_o = (X >= x0) & (X <= x1) & (Z >= z0) & (Z <= z1)
    inside_i = (X >= x0 + w) & (X <= x1 - w) & (Z >= z0 + w) & (Z <= z1 - w)
    out[sl] = (inside_o & ~inside_i).astype(np.float32)
    return out


def emblem(cx, cz, r):
    """The made-up line's emblem: a ring around three waves."""
    out = blank()
    sl, X, Z = win(cx, cz, r + 0.01, r + 0.01)
    d = np.hypot(X - cx, Z - cz)
    aa = 1.5 / PXM
    ring = np.clip((r - d) / aa, 0, 1) * np.clip((d - (r - 0.028)) / aa, 0, 1)
    inner = np.clip((r - 0.05 - d) / aa, 0, 1)
    w = (Z - cz - 0.022 * np.sin((X - cx) * 17.0)) / 0.072
    waves = np.clip((0.42 - np.abs(w - np.round(w))) / 0.03, 0, 1) * (np.abs(np.round(w)) <= 1)
    out[sl] = np.maximum(ring, inner * (1 - waves))
    return out


def check_digit(owner, serial):
    vals = {}
    v = 10
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if v % 11 == 0:
            v += 1
        vals[ch] = v
        v += 1
    s = sum((vals[c] if c.isalpha() else int(c)) * (2 ** i) for i, c in enumerate(owner + serial))
    return str(s % 11 % 10)


OWNER, SERIAL = "KVLU", "471093"
CHECK = check_digit(OWNER, SERIAL)


def id_code(x, z, size):
    t = text_tris("%s %s" % (OWNER, SERIAL), size, x, z, F_BOLD)
    xr = t[..., 0].max()
    img = raster(t)
    tc = text_tris(CHECK, size, xr + 0.055 * size / 0.085 + 0.012, z, F_BOLD, align="CENTER")
    img = np.maximum(img, raster(tc))
    lo, hi = tc[..., 0].min(), tc[..., 0].max()
    pad = 0.012 * size / 0.085
    img = np.maximum(img, rect_ring(lo - pad, z - size * 0.52, hi + pad, z + size * 0.5, 0.005 * size / 0.085))
    img = np.maximum(img, raster(text_tris("45G1", size * 0.8, x, z - size * 1.35, F_BOLD)))
    return img


def wall_decal():
    img = id_code(-1.24, 2.27, 0.085)
    img = np.maximum(img, emblem(-0.19, 1.72, 0.2))
    img = np.maximum(img, raster(text_tris("KORVAN", 0.25, 0.08, 1.76, F_BLACK, shear=0.18)))
    img = np.maximum(img, raster(text_tris("LINES", 0.085, 0.11, 1.5, F_BOLD, spacing=1.45)))
    return img


def door_decal():
    img = id_code(0.2, 2.0, 0.07)
    lines = ["MAX.GROSS   32.500 KG", "                    71.650 LB", "TARE             3.900 KG",
             "                      8.600 LB", "NET            28.600 KG", "CU.CAP.        76.4 CU.M"]
    for k, line in enumerate(lines):
        img = np.maximum(img, raster(text_tris(line, 0.042, -1.17, 2.0 - k * 0.056, F_NARROW)))
    img = np.maximum(img, emblem(-0.87, 1.42, 0.075))
    img = np.maximum(img, raster(text_tris("KORVAN", 0.1, -0.77, 1.43, F_BLACK, shear=0.18)))
    return img


class Dmg:
    """A damage map: R bare scraped steel, G holes / soot, B rust, H relief (stored +0.5 in alpha)."""

    def __init__(self, seed):
        self.R, self.G, self.B, self.H = blank(), blank(), blank(), blank()
        self.rng = np.random.default_rng(seed)

    def bullet(self, cx, cz, s=1.0):
        rng = self.rng
        rc, rr, rh = 0.0085 * s, 0.021 * s, 0.05 * s
        sl, X, Z = win(cx, cz, rh * 1.1, rh * 3.2)
        d = np.hypot(X - cx, Z - cz)
        a = np.arctan2(Z - cz, X - cx)
        ph = rng.uniform(0, 6.3, 3)
        jag = 1.0 + 0.22 * np.sin(a * 5 + ph[0]) + 0.12 * np.sin(a * 9 + ph[1])
        aa = 1.2 / PXM
        core = np.clip((rc * (0.85 + 0.15 * jag) - d) / aa + 0.5, 0, 1)
        ring = np.clip(1 - (d - rc) / (rr * jag - rc), 0, 1) ** 0.6 * (1 - core)
        halo = np.clip(1 - (d - rc) / (rh - rc), 0, 1) ** 1.6 * 0.6
        run = np.clip(1 - np.abs(X - cx - 0.002 * np.sin(Z * 90)) / (0.004 * s), 0, 1) \
            * np.clip((cz - Z) / 0.01, 0, 1) * np.clip(1 + (Z - cz) / (0.12 * s * rng.uniform(0.6, 1.3)), 0, 1)
        self.G[sl] = np.maximum(self.G[sl], core)
        self.R[sl] = np.maximum(self.R[sl], ring * 0.95)
        self.B[sl] = np.maximum(self.B[sl], np.maximum(halo, run * 0.7))
        rim = np.exp(-((d - rc * 1.35) / (rc * 0.5)) ** 2)
        self.H[sl] += (0.35 * rim - 0.5 * core - 0.12 * np.clip(1 - d / rr, 0, 1)).astype(np.float32)

    def scrape(self, x0, z0, x1, z1, width=0.02, lines=6, strength=1.0, rust=0.25):
        rng = self.rng
        p0, p1 = np.array([x0, z0]), np.array([x1, z1])
        L = np.linalg.norm(p1 - p0)
        t_hat = (p1 - p0) / L
        n_hat = np.array([-t_hat[1], t_hat[0]])
        c = (p0 + p1) / 2
        sl, X, Z = win(c[0], c[1], abs(p1[0] - p0[0]) / 2 + width + 0.02, abs(p1[1] - p0[1]) / 2 + width + 0.02)
        rx, rz = X - p0[0], Z - p0[1]
        t = (rx * t_hat[0] + rz * t_hat[1]) / L
        n = rx * n_hat[0] + rz * n_hat[1]
        ends = np.clip(t / 0.15, 0, 1) * np.clip((1 - t) / 0.3, 0, 1)
        acc = np.zeros_like(X)
        for _ in range(lines):
            off = rng.uniform(-width / 2, width / 2)
            hw = rng.uniform(0.0006, 0.0028)
            ph, fr = rng.uniform(0, 6.3), rng.uniform(8, 30)
            brk = np.clip(0.55 + 0.6 * np.sin(t * fr + ph) + 0.3 * np.sin(t * fr * 2.7 + ph * 2), 0, 1)
            line = np.clip(1 - np.abs(n - off - 0.003 * np.sin(t * 20 + ph)) / hw, 0, 1)
            acc = np.maximum(acc, line * brk * rng.uniform(0.6, 1.0))
        acc *= ends * strength
        self.R[sl] = np.maximum(self.R[sl], acc)
        self.B[sl] = np.maximum(self.B[sl], acc * rust)
        self.H[sl] -= (acc * 0.25).astype(np.float32)

    def claws(self, x, z, ang, length, spacing=0.028):
        a = math.radians(ang)
        t = np.array([math.cos(a), math.sin(a)])
        n = np.array([-t[1], t[0]])
        for k in range(4):
            o = (k - 1.5) * spacing
            p0 = np.array([x, z]) + n * o + t * self.rng.uniform(-0.03, 0.03)
            p1 = p0 + t * length * self.rng.uniform(0.75, 1.05)
            self.scrape(p0[0], p0[1], p1[0], p1[1], width=0.006, lines=3, strength=0.95, rust=0.15)

    def blotches(self, x0, x1, z0, z1, amount, seed, holes=0.0, bottom=RB_TOP):
        sl, X, Z = win((x0 + x1) / 2, (z0 + z1) / 2, (x1 - x0) / 2, (z1 - z0) / 2)
        n = value_fbm(X.shape, seed)
        low = np.clip(1 - (Z - bottom) / 0.9, 0, 1)
        edge = np.clip(np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Z - z0, z1 - Z)) / 0.14, 0, 1)
        th = 0.62 - 0.25 * amount * low
        m = np.clip((n - th) / 0.025, 0, 1) * edge
        self.B[sl] = np.maximum(self.B[sl], m)
        if holes:
            hm = np.clip((n - th - 0.2) / 0.025, 0, 1) * low * holes * edge
            self.G[sl] = np.maximum(self.G[sl], hm)
            self.R[sl] = np.maximum(self.R[sl], np.clip((n - th - 0.12) / 0.02, 0, 1) * (1 - hm) * 0.25 * edge)
        self.H[sl] += (m * 0.25 - self.G[sl] * 0.3).astype(np.float32)

    def tear_halo(self, poly):
        P = np.asarray(poly)
        c = P.mean(axis=0)
        r = np.abs(P - c).max(axis=0) + 0.12
        sl, X, Z = win(c[0], c[1], r[0], r[1])
        d = np.full(X.shape, 1e9)
        inside = np.zeros(X.shape, bool)
        for k in range(len(P)):
            a, b = P[k], P[(k + 1) % len(P)]
            ab = b - a
            t = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.hypot(X - a[0] - t * ab[0], Z - a[1] - t * ab[1]))
            cond = ((a[1] > Z) != (b[1] > Z))
            xint = a[0] + (Z - a[1]) * ab[0] / np.where(ab[1] == 0, 1e-9, ab[1])
            inside ^= cond & (X < xint)
        rough = value_fbm(X.shape, 91, cells=14.0)
        bare = np.where(inside, 1.0, np.clip(1 - d / (0.014 + 0.02 * rough), 0, 1))
        rust = np.where(inside, 1.0, np.clip(1 - d / (0.06 + 0.06 * rough), 0, 1) ** 1.3)
        soot = np.where(inside, 0.0, np.clip(1 - d / 0.035, 0, 1) * 0.18)
        self.R[sl] = np.maximum(self.R[sl], bare * 0.9)
        self.B[sl] = np.maximum(self.B[sl], rust * 0.8)
        self.G[sl] = np.maximum(self.G[sl], soot)
        self.H[sl] += (np.clip(1 - d / 0.03, 0, 1) * 0.3).astype(np.float32)

    def rgba(self):
        return np.dstack([self.R, self.G, self.B, np.clip(self.H + 0.5, 0, 1)])


def value_fbm(shape, seed, cells=6.0, octaves=4):
    """Smooth value noise (0..1) over an array, `cells` lattice cells across its larger side."""
    rng = np.random.default_rng(seed)
    h, w = shape
    out = np.zeros(shape, np.float64)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cells * (2 ** o)
        gh, gw = int(c * h / max(h, w)) + 3, int(c * w / max(h, w)) + 3
        lat = rng.random((gh, gw))
        v = np.linspace(0, gh - 2.001, h)
        u = np.linspace(0, gw - 2.001, w)
        i, j = np.floor(v).astype(int), np.floor(u).astype(int)
        fv, fu = v - i, u - j
        fv, fu = fv * fv * (3 - 2 * fv), fu * fu * (3 - 2 * fu)
        a = lat[i][:, j]
        b = lat[i][:, j + 1]
        cc = lat[i + 1][:, j]
        d = lat[i + 1][:, j + 1]
        top = a + (b - a) * fu[None, :]
        bot = cc + (d - cc) * fu[None, :]
        out += amp * (top + (bot - top) * fv[:, None])
        tot += amp
        amp *= 0.5
    return out / tot


# damage layout, shared by the geometry and the damage maps (design coordinates of the front face)
DENTS_A = [(-1.04, 0.36, 0.22, 0.075), (-0.70, -0.06, 0.15, 0.045), (-0.86, 0.76, 0.13, 0.04), (-1.2, -0.12, 0.1, 0.03)]
CREASE_A = ((-1.27, 0.62), (-0.62, 0.12), 0.05, 0.022)
TEAR_C = (0.03, 0.42)


def tear_poly():
    rnd = random.Random(5)
    pts = []
    n = 30
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.07, 0.07)
        r = 1.0 + 0.3 * fbm((math.cos(a) * 1.5, math.sin(a) * 1.5, 0.3), 2, 4.0)
        r *= rnd.choice((0.82, 0.92, 1.0, 1.0, 1.08, 1.2))
        # rips run on up and down the corrugation
        r *= 1.0 + 0.45 * max(0.0, math.cos(a - 1.62)) ** 12 + 0.3 * max(0.0, math.cos(a + 1.5)) ** 12
        pts.append((TEAR_C[0] + 0.25 * r * math.cos(a), TEAR_C[1] + 0.29 * r * math.sin(a)))
    return pts


TEAR = tear_poly()
PEEL_X = -1.05  # the peeled sheet bends back about this vertical line


def damage_maps():
    d1 = Dmg(11)
    # A lower (dented): claw rakes and scuffs round the dents
    d1.claws(-1.23, 0.82, -58, 0.42)
    d1.claws(-0.95, 0.15, -72, 0.36)
    d1.claws(-0.7, 0.9, -118, 0.3)
    for (x, z, r, dep) in DENTS_A:
        for _ in range(3):
            a = d1.rng.uniform(0, 6.28)
            p = np.array([x, z]) + np.array([math.cos(a), math.sin(a)]) * r * 0.4
            q = p + np.array([math.cos(a + 1.3), math.sin(a + 1.3)]) * r * 0.7
            d1.scrape(p[0], p[1], q[0], q[1], width=0.03, lines=5, strength=0.8)
    d1.blotches(-1.33, -0.47, -0.34, 1.0, 0.15, 21)
    # B upper (holed): a burst of bullet holes and a few strays, a couple of scrapes
    rng = d1.rng
    for k in range(8):
        a, rr = rng.uniform(0, 6.28), 0.16 * math.sqrt(rng.uniform(0.05, 1))
        d1.bullet(-0.04 + rr * math.cos(a), 1.74 + rr * math.sin(a), rng.uniform(0.85, 1.15))
    for (x, z) in ((0.31, 1.27), (-0.33, 2.17), (0.22, 2.27), (-0.27, 1.16), (0.36, 1.98)):
        d1.bullet(x, z, rng.uniform(0.8, 1.1))
    d1.scrape(-0.38, 1.4, 0.05, 1.1, width=0.03, lines=6, strength=0.85)
    d1.scrape(0.1, 2.35, 0.4, 2.1, width=0.02, lines=4, strength=0.7)

    d2 = Dmg(12)
    # B lower (torn): bare and rusty halo round the tear, claw marks, rust bleeding below
    d2.tear_halo(TEAR)
    d2.claws(-0.36, 0.92, -50, 0.3)
    d2.claws(0.22, 0.05, 55, 0.25)
    d2.blotches(-0.43, 0.43, -0.34, 1.0, 0.2, 33)
    # A lower (peeled): paint cracked along the bend, scrapes
    sl, X, Z = win(PEEL_X, 0.33, 0.06, 0.7)
    band = np.clip(1 - np.abs(X - PEEL_X - 0.01 * np.sin(Z * 13)) / 0.03, 0, 1)
    crack = band * np.clip((value_fbm(X.shape, 44, cells=30.0) - 0.45) / 0.1, 0, 1)
    d2.R[sl] = np.maximum(d2.R[sl], crack)
    d2.B[sl] = np.maximum(d2.B[sl], band * 0.5)
    d2.claws(-1.3, 0.55, -40, 0.24)
    d2.blotches(-1.33, -0.47, -0.34, 1.0, 0.2, 34)
    # C lower (rust-through): heavy rust with holes eaten through near the bottom
    d2.blotches(0.47, 1.33, -0.34, 1.0, 0.75, 35, holes=0.8)
    d2.scrape(0.6, 0.6, 1.0, 0.9, width=0.03, lines=5, strength=0.7)
    return d1.rgba(), d2.rgba()


def make_image(name, rgba):
    img = bpy.data.images.new(name, DRES, DRES, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    img.alpha_mode = "CHANNEL_PACKED"
    img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    return img


def build_decals():
    w = wall_decal()
    d = door_decal()
    m1, m2 = damage_maps()
    z = np.zeros_like(w)
    imgs = dict(wall=make_image("DecalWall", np.dstack([w, z, z, z + 1])),
                door=make_image("DecalDoor", np.dstack([d, z, z, z + 1])),
                dm1=make_image("DecalDmg1", m1), dm2=make_image("DecalDmg2", m2))
    if MODE == "decals":
        for k, im in imgs.items():
            a = np.empty(DRES * DRES * 4, np.float32)
            im.pixels.foreach_get(a)
            a = a.reshape(DRES, DRES, 4)
            a[..., 3] = 1.0
            tk.save_array("dbg" + k, a, os.path.join(PREVIEWS, "dbg_decal_%s.png" % k), True)
    return imgs


# ---------------------------------------------------------------- materials

def _set(g, sock, x):
    if hasattr(x, "is_output"):
        g.links.new(x, sock)
    elif isinstance(x, (tuple, list)):
        sock.default_value = tuple(x) + ((1.0,) if len(x) == 3 and len(sock.default_value) == 4 else ())
    else:
        sock.default_value = x


def attr(g, name, out="Vector"):
    n = g.node("ShaderNodeAttribute", attribute_name=name)
    return tk._sock(n.outputs, out)


def vop(g, op, a, b=None, scale=None):
    n = g.node("ShaderNodeVectorMath", operation=op)
    _set(g, n.inputs[0], a)
    if b is not None:
        _set(g, n.inputs[1], b)
    if scale is not None:
        _set(g, n.inputs[3], scale)
    return n.outputs[0]


def combine(g, x, y, z):
    n = g.node("ShaderNodeCombineXYZ")
    for s, v in zip(n.inputs, (x, y, z)):
        _set(g, s, v)
    return n.outputs[0]


def photo_at(g, set_name, vec, scale, kind="diff", offset=(0.0, 0.0, 0.0)):
    path = os.path.join(tk.TEXTURES, set_name, "%s_%s_2k.jpg" % (set_name, kind))
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB" if kind == "diff" else "Non-Color"
    n = g.node("ShaderNodeTexImage", projection="BOX", projection_blend=0.3, interpolation="Cubic")
    n.image = img
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Location"].default_value = offset
    m.inputs["Scale"].default_value = (scale, scale, scale)
    g.links.new(m.outputs[0], n.inputs["Vector"])
    return n.outputs["Color"]


def image_at(g, img, uv):
    n = g.node("ShaderNodeTexImage", interpolation="Linear", extension="CLIP")
    n.image = img
    g.links.new(uv, n.inputs["Vector"])
    return n


def mx(g, *xs):
    out = xs[0]
    for x in xs[1:]:
        out = g.math("MAXIMUM", out, x)
    return out


def inv(g, x):
    return g.math("SUBTRACT", 1.0, x, clamp=True)


def scratches(g, vec, amount):
    sc = None
    for k, (scale, rot) in enumerate((((70.0, 70.0, 14.0), (0.3, 0.9, 0.2)), ((120.0, 120.0, 22.0), (1.1, 0.2, 1.4)))):
        m = g.node("ShaderNodeMapping")
        g.links.new(vec, m.inputs["Vector"])
        m.inputs["Scale"].default_value = scale
        m.inputs["Rotation"].default_value = rot
        m.inputs["Location"].default_value = (0.3 * k, 0.7 * k, 0.1 * k)
        n = g.noise(1.0, detail=1.0, roughness=0.3, vector=m.outputs[0])
        line = inv(g, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, 0.012, False))
        sc = line if sc is None else g.math("MAXIMUM", sc, line)
    density = g.ramp(g.noise(4.0, detail=3.0, vector=vec), 0.42, 0.62)
    return g.math("MULTIPLY", g.math("MULTIPLY", sc, density), amount)


def drips(g, vec, amount):
    m = g.node("ShaderNodeMapping")
    g.links.new(vec, m.inputs["Vector"])
    m.inputs["Scale"].default_value = (16.0, 16.0, 0.9)
    return g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=m.outputs[0]), 0.55, 0.78), amount)


def common_inputs(g):
    lco = attr(g, "lco")
    seed, dmg, flag = g.separate(attr(g, "kd"))
    rust_amt, wear_amt, grime_amt = g.separate(attr(g, "kw"))
    inner = attr(g, "inner", "Fac")
    T = vop(g, "ADD", lco, vop(g, "SCALE", (3.7, 11.3, 5.9), scale=seed))
    x, y, z = g.separate(lco)
    low = g.ramp(g.math("SUBTRACT", z, Z0), 0.9, 0.0)
    return dict(lco=lco, seed=seed, dmg=dmg, flag=flag, rust=rust_amt, wear=wear_amt, grime=grime_amt, inner=inner,
                T=T, x=x, y=y, z=z, low=low)


def grime_dust(g, c, col, rough, metal):
    T = c["T"]
    cav = g.ramp(g.cavity(0.1), 0.35, 1.0)
    gm = g.math("MULTIPLY", g.math("ADD", inv(g, cav), g.math("MULTIPLY", c["low"], 0.55)), c["grime"], clamp=True)
    gm = g.math("MULTIPLY", gm, g.ramp(g.noise(5.0, detail=5.0, vector=T), 0.2, 0.7))
    col = g.mix(gm, col, DIRT)
    col = g.mix(drips(g, T, g.math("MULTIPLY", c["grime"], 0.45)), col, tk._multiply_color(g, col, (0.55, 0.53, 0.5)))
    up = g.separate(tk._sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
    dust = g.math("MULTIPLY", g.ramp(up, 0.5, 0.9), g.ramp(g.noise(9.0, detail=6.0, roughness=0.6, vector=T), 0.3, 0.65))
    dust = g.math("MULTIPLY", dust, 0.75)
    col = g.mix(dust, col, DUST)
    fine = g.math("MULTIPLY", g.ramp(g.noise(45.0, detail=8.0, roughness=0.75, vector=T), 0.5, 0.7), 0.4)
    col = g.mix(fine, col, tk._multiply_color(g, col, (0.6, 0.58, 0.55)))
    rough = g.mixf(gm, rough, 0.86)
    rough = g.mixf(dust, rough, 0.95)
    metal = g.mixf(gm, metal, 0.03)
    metal = g.mixf(dust, metal, 0.0)
    return col, rough, metal, gm


def paint_material(imgs):
    """Container steel painted light grey (the game tints it), with the photo's marks, rust streaks running down,
    rust patches, chipped edges, scratches, stencils, damage maps, grime and dust. kd = (seed, damage level,
    decal set: 1 wall, 2 doors); kw = (rust, wear, grime); inner = interior side (grey primer, no stencils)."""
    mat, g = tk.new_material("CtPaint")
    c = common_inputs(g)
    T, inner = c["T"], c["inner"]
    cs = photo_at(g, "container_side", T, 0.42)
    var = g.math("SUBTRACT", g.math("DIVIDE", tk._luma(g, cs), 0.2), 1.0)
    big = g.math("SUBTRACT", g.noise(0.55, detail=3.0, vector=T), 0.5)
    grey = g.math("MULTIPLY", PAINT, g.math("ADD", 1.0, g.math("ADD", g.math("MULTIPLY", var, 2.0),
                                                              g.math("MULTIPLY", big, 0.18))))
    paint = combine(g, grey, grey, grey)
    paint = g.mix(g.math("MINIMUM", inner, 1.0), paint, tk._multiply_color(g, paint, (0.45, 0.43, 0.4)))
    deep = g.math("SUBTRACT", inner, 1.0, clamp=True)
    csr = g.separate(photo_at(g, "container_side", T, 0.42, "arm"))[1]
    rc = photo_at(g, "rust_coarse_01", T, 1.3, offset=(0.37, 0.11, 0.73))
    rch = photo_at(g, "rust_coarse_01", T, 1.3, "disp", offset=(0.37, 0.11, 0.73))
    # rust stains running down, straight from the photo
    rp = photo_at(g, "rusty_painted_metal", T, 0.5, offset=(0.3, 0.0, 0.1))
    stain = g.math("MULTIPLY", g.ramp(tk._luma(g, rp), 0.05, 0.014), g.math("MULTIPLY", c["rust"], 0.9), clamp=True)
    # rust patches, heavier low down and inside
    rb = g.math("MULTIPLY", c["rust"], g.math("ADD", 0.25, g.math("MULTIPLY", c["low"], 0.75)), clamp=True)
    rb = g.math("MAXIMUM", rb, g.math("MULTIPLY", g.math("MINIMUM", inner, 1.0), 0.6))
    blot = g.noise(2.3, detail=8.0, roughness=0.65, vector=T, distortion=0.5)
    th = g.math("SUBTRACT", 0.71, g.math("MULTIPLY", rb, 0.17))
    patch = g.ramp(blot, th, g.math("ADD", th, 0.03))
    e = g.edges(0.007)
    chips = g.noise(24.0, detail=6.0, roughness=0.7, vector=T)
    lo = g.math("SUBTRACT", 0.21, g.math("MULTIPLY", c["wear"], 0.09))
    edge_m = g.ramp(g.math("MULTIPLY", e, g.math("ADD", chips, 0.3)), lo, g.math("ADD", lo, 0.12))
    ef = g.ramp(g.noise(7.0, detail=3.0, vector=T), 0.38, 0.62)
    cav_r = g.math("MULTIPLY", inv(g, g.cavity(0.05)), g.math("MULTIPLY", c["rust"], 0.7), clamp=True)
    sc = scratches(g, T, g.math("MULTIPLY", c["wear"], 0.55))
    # stencils and damage maps (design frame of the front face)
    uv = combine(g, g.math("DIVIDE", g.math("ADD", c["x"], 1.5), 3.0), g.math("DIVIDE", g.math("ADD", c["z"], 0.5), 3.0),
                 0.0)
    W, D = image_at(g, imgs["wall"], uv), image_at(g, imgs["door"], uv)
    M1, M2 = image_at(g, imgs["dm1"], uv), image_at(g, imgs["dm2"], uv)
    flag = c["flag"]
    isw = inv(g, g.math("ABSOLUTE", g.math("SUBTRACT", flag, 1.0)))
    isd = g.math("SUBTRACT", flag, 1.0, clamp=True)
    sten = g.math("ADD", g.math("MULTIPLY", g.separate(W.outputs["Color"])[0], isw),
                  g.math("MULTIPLY", g.separate(D.outputs["Color"])[0], isd))
    fade = g.math("ADD", 0.25, g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=6.0, roughness=0.7, vector=T), 0.35, 0.65),
                                      0.6))
    sten = g.math("MULTIPLY", g.math("MULTIPLY", sten, fade), inv(g, g.math("MINIMUM", inner, 1.0)), clamp=True)
    f1 = inv(g, g.math("ABSOLUTE", g.math("SUBTRACT", c["dmg"], 1.0)))
    f2 = g.math("SUBTRACT", c["dmg"], 1.0, clamp=True)
    m1, m2 = g.separate(M1.outputs["Color"]), g.separate(M2.outputs["Color"])
    outside = inv(g, g.math("MINIMUM", inner, 1.0))
    dR, dG, dB = (g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", a, f1), g.math("MULTIPLY", b, f2)), outside)
                  for a, b in zip(m1, m2))
    dH = g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", M1.outputs["Alpha"], 0.5), f1),
                g.math("MULTIPLY", g.math("SUBTRACT", M2.outputs["Alpha"], 0.5), f2))
    rust_m = mx(g, patch, g.math("MULTIPLY", edge_m, ef), cav_r, dB)
    bare_m = mx(g, sc, g.math("MULTIPLY", edge_m, inv(g, ef)), dR)

    col = g.mix(g.math("MULTIPLY", stain, 0.85), paint, g.mix(0.45, tk._multiply_color(g, rp, (1.3, 1.2, 1.15)),
                                                              tk._multiply_color(g, rc, (0.75, 0.7, 0.65))))
    col = g.mix(sten, col, STENCIL)
    col = g.mix(rust_m, col, tk.grade(g, rc, 1.0, 1.1))
    col = g.mix(bare_m, col, BARE)
    rough = g.math("MULTIPLY", csr, 0.8)
    rough = g.mixf(stain, rough, 0.72)
    rough = g.mixf(sten, rough, 0.6)
    rough = g.mixf(rust_m, rough, 0.88)
    rough = g.mixf(bare_m, rough, 0.38)
    metal = g.mixf(rust_m, 0.32, 0.12)
    metal = g.mixf(sten, metal, 0.08)
    metal = g.mixf(bare_m, metal, 0.85)
    col, rough, metal, gm = grime_dust(g, c, col, rough, metal)
    col = g.mix(dG, col, HOLE)
    col = g.mix(deep, col, tk._multiply_color(g, col, (0.13, 0.12, 0.11)))
    rough = g.mixf(dG, rough, 0.95)
    metal = g.mixf(dG, metal, 0.0)
    tint = g.math("MULTIPLY", inv(g, rust_m), inv(g, bare_m))
    tint = g.math("MULTIPLY", tint, inv(g, sten))
    tint = g.math("MULTIPLY", tint, inv(g, dG))
    tint = g.math("MULTIPLY", tint, inv(g, g.math("MULTIPLY", stain, 0.85)))
    tint = g.math("MULTIPLY", tint, inv(g, g.math("MULTIPLY", gm, 0.4)))
    tint = g.math("MULTIPLY", tint, inv(g, g.math("MINIMUM", inner, 1.0)))
    h = g.math("MULTIPLY", g.math("MULTIPLY", rch, rust_m), 0.8)
    h = g.math("ADD", h, g.math("MULTIPLY", g.noise(70.0, detail=4.0, vector=T), 0.12))
    h = g.math("SUBTRACT", h, g.math("MULTIPLY", sc, 0.5))
    h = g.math("SUBTRACT", h, g.math("MULTIPLY", edge_m, 0.4))
    h = g.math("ADD", h, g.math("MULTIPLY", dH, 2.0))
    h = g.math("ADD", h, g.math("MULTIPLY", sten, 0.1))
    tk.finish(mat, g, col, metal, rough, g.bump(h, 0.35, 0.004))
    tk.BAKE[mat.name]["tint"] = tint
    return mat


def steel_material():
    """Unpainted scrap steel (end caps, patches, castings, the threshold): mill scale, rust, bright scrapes.
    kd.z = 1 adds a diamond tread."""
    mat, g = tk.new_material("CtSteel")
    c = common_inputs(g)
    T = c["T"]
    mp = photo_at(g, "metal_plate_02", T, 0.3)
    col = tk.grade(g, mp, 0.7, 0.8)
    mpr = g.separate(photo_at(g, "metal_plate_02", T, 0.3, "arm"))[1]
    rc = photo_at(g, "rust_coarse_01", T, 1.5, offset=(0.21, 0.5, 0.13))
    rch = photo_at(g, "rust_coarse_01", T, 1.5, "disp", offset=(0.21, 0.5, 0.13))
    rb = g.math("MULTIPLY", c["rust"], g.math("ADD", 0.35, g.math("MULTIPLY", c["low"], 0.65)), clamp=True)
    th = g.math("SUBTRACT", 0.62, g.math("MULTIPLY", rb, 0.2))
    patch = g.ramp(g.noise(2.6, detail=8.0, roughness=0.65, vector=T, distortion=0.5), th, g.math("ADD", th, 0.05))
    cav_r = g.math("MULTIPLY", inv(g, g.cavity(0.05)), c["rust"], clamp=True)
    rust_m = mx(g, patch, cav_r)
    e = g.edges(0.005)
    edge_m = g.ramp(g.math("MULTIPLY", e, g.math("ADD", g.noise(30.0, detail=5.0, vector=T), 0.3)), 0.14, 0.26)
    sc = scratches(g, T, g.math("MULTIPLY", c["wear"], 0.6))
    bare_m = mx(g, edge_m, sc)
    col = g.mix(rust_m, col, tk.grade(g, rc, 1.0, 1.05))
    col = g.mix(bare_m, col, (0.36, 0.355, 0.35))
    rough = g.mixf(rust_m, g.math("MULTIPLY", mpr, 0.85), 0.88)
    rough = g.mixf(bare_m, rough, 0.36)
    metal = g.mixf(rust_m, 0.45, 0.18)
    metal = g.mixf(bare_m, metal, 0.9)
    col, rough, metal, gm = grime_dust(g, c, col, rough, metal)
    # diamond tread: raised lozenges alternating direction in a checker
    s = 0.035
    u, v = g.math("DIVIDE", c["x"], s), g.math("DIVIDE", c["y"], s)
    fu, fv = g.math("SUBTRACT", g.math("FRACT", u), 0.5), g.math("SUBTRACT", g.math("FRACT", v), 0.5)
    chk = g.math("FRACT", g.math("MULTIPLY", g.math("ADD", g.math("FLOOR", u), g.math("FLOOR", v)), 0.5))
    a1 = g.math("ABSOLUTE", g.math("ADD", fu, fv))
    a2 = g.math("ABSOLUTE", g.math("SUBTRACT", fu, fv))
    along = g.mixf(g.math("GREATER_THAN", chk, 0.25), a2, a1)
    across = g.mixf(g.math("GREATER_THAN", chk, 0.25), a1, a2)
    lozenge = g.math("MULTIPLY", inv(g, g.ramp(across, 0.06, 0.13)), inv(g, g.ramp(along, 0.42, 0.62)))
    tread = g.math("MULTIPLY", lozenge, c["flag"])
    col = g.mix(g.math("MULTIPLY", tread, 0.5), col, tk._multiply_color(g, col, (1.35, 1.35, 1.35)))
    h = g.math("ADD", g.math("MULTIPLY", rch, rust_m), g.math("MULTIPLY", g.noise(60.0, detail=4.0, vector=T), 0.15))
    h = g.math("SUBTRACT", h, g.math("MULTIPLY", sc, 0.4))
    h = g.math("ADD", h, g.math("MULTIPLY", tread, 1.2))
    tk.finish(mat, g, col, metal, rough, g.bump(h, 0.4, 0.004))
    tk.BAKE[mat.name]["tint"] = None
    return mat


def weld_material():
    """Weld beads, laid along their own x: ripples, heat tint at the toes, rust."""
    mat, g = tk.new_material("CtWeld")
    c = common_inputs(g)
    T = c["T"]
    across = g.math("DIVIDE", g.math("ABSOLUTE", c["y"]), 0.008)
    t = g.math("DIVIDE", g.math("ADD", c["x"], g.math("MULTIPLY", g.math("MULTIPLY", across, across), 0.004)), 0.0042)
    rip = g.math("SINE", g.math("MULTIPLY", t, 2 * math.pi))
    heat = g.ramp(across, 0.55, 1.0)
    col = g.mix(heat, (0.075, 0.07, 0.065), (0.15, 0.1, 0.045))
    col = g.mix(g.math("MULTIPLY", g.ramp(across, 0.85, 1.2), 0.8), col, (0.05, 0.06, 0.1))
    rc = photo_at(g, "rust_coarse_01", T, 3.0, offset=(0.5, 0.2, 0.9))
    rust = g.ramp(g.noise(18.0, detail=5.0, vector=T), 0.5, 0.62)
    col = g.mix(rust, col, rc)
    col = g.mix(g.math("MULTIPLY", g.math("ADD", rip, 1.0), 0.12), col, (0.2, 0.19, 0.18))
    rough = g.mixf(rust, 0.45, 0.85)
    metal = g.mixf(rust, 0.65, 0.2)
    col, rough, metal, gm = grime_dust(g, c, col, rough, metal)
    h = g.math("ADD", g.math("MULTIPLY", rip, 0.4), g.math("MULTIPLY", g.noise(120.0, detail=4.0, vector=T), 0.3))
    tk.finish(mat, g, col, metal, rough, g.bump(h, 0.6, 0.002))
    tk.BAKE[mat.name]["tint"] = None
    return mat


def build_materials(imgs):
    paint = paint_material(imgs)
    steel = steel_material()
    weld = weld_material()
    rubber = tk.grimy("CtRubber", (0.022, 0.022, 0.022), roughness=0.72, grime=0.5, grime_set="rust_coarse_01",
                      scale=2.0, bump_scale=200.0, bump=0.2, grit=0.4, dirt_range=(0.15, 0.04))
    tk.BAKE[rubber.name]["tint"] = None
    alu = tk.grimy("CtAlu", (0.5, 0.5, 0.52), roughness=0.38, metallic=0.85, grime=0.6, grime_set="metal_plate_02",
                   scale=2.5, bump_scale=300.0, bump=0.1, grit=0.6)
    tk.BAKE[alu.name]["tint"] = None
    return [paint, steel, weld, rubber, alu]


M_PAINT, M_STEEL, M_WELD, M_RUBBER, M_ALU = range(5)


# ---------------------------------------------------------------- geometry builders (bmesh, design pose)

def uv_layer(bm):
    return bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")


def inner_layer(bm):
    return bm.verts.layers.float.get("inner") or bm.verts.layers.float.new("inner")


def profile(x0, y0, segs, sub=1):
    """Breakpoints of a folded profile starting at (x0, y0); segs = [(width, y at its end)], each split `sub`
    times. Returns xs, ys and the indices of the folds (where the slope changes)."""
    xs, ys, x, y = [x0], [y0], x0, y0
    marks = []
    for w, ye in segs:
        for s in range(1, sub + 1):
            xs.append(x + w * s / sub)
            ys.append(y + (ye - y) * s / sub)
        x, y = x + w, ye
        marks.append(len(xs) - 1)
    folds = []
    for i in marks[:-1]:
        a = (ys[i] - ys[i - 1]) / (xs[i] - xs[i - 1])
        b = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
        if abs(a - b) > 1e-6:
            folds.append(i)
    return xs, ys, folds


def sheet(bm, xs, ys, zs, folds=(), flip=False, inner=0.0, yoff=0.0, closed=False):
    """A grid surface through profile points (xs, ys) swept along z (zs), facing -Y (flip: +Y), unfolded UVs
    (arclength, z). Returns the vertex grid G[i][j]."""
    uvl, inl = uv_layer(bm), inner_layer(bm)
    n = len(xs)
    s = [0.0]
    for i in range(1, n):
        s.append(s[-1] + math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
    G = [[bm.verts.new((xs[i], ys[i] + yoff, z)) for z in zs] for i in range(n)]
    for col in G:
        for v in col:
            v[inl] = inner
    for i in range(n - 1):
        for j in range(len(zs) - 1):
            vs = [G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]]
            uvs = [(s[i], zs[j]), (s[i + 1], zs[j]), (s[i + 1], zs[j + 1]), (s[i], zs[j + 1])]
            if flip:
                vs, uvs = vs[::-1], uvs[::-1]
            f = bm.faces.new(vs)
            f.smooth = True
            for lp, uv in zip(f.loops, uvs):
                lp[uvl].uv = uv
    for i in folds:
        for j in range(len(zs) - 1):
            e = bm.edges.get((G[i][j], G[i][j + 1]))
            if e:
                e.smooth = False
    return G


def sweep(bm, prof, axis, a0, a1, segs=1, closed=False, flip=False, inner=0.0):
    """Extrudes a 2D profile along an axis: 'X' profile (y, z), 'Y' (x, z), 'Z' (x, y). Folds sharp, unfolded UVs."""
    P = list(prof) + ([prof[0]] if closed else [])
    us = [p[0] for p in P]
    vs = [p[1] for p in P]
    stations = [a0 + (a1 - a0) * k / segs for k in range(segs + 1)]
    folds = []
    for i in range(1, len(P) - 1):
        folds.append(i)
    # build in a local frame where the profile is (x, y) and the sweep is z, then map
    tmp = bmesh.new()
    sheet(tmp, us, vs, stations, folds, flip=flip, inner=inner)
    if axis == "X":
        M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    elif axis == "Y":
        M = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    else:
        M = Matrix.Identity(4)
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
    if M.to_3x3().determinant() < 0:
        bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
    merge(bm, tmp)


def merge(bm, other):
    me = bpy.data.meshes.new("_merge")
    other.to_mesh(me)
    other.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def box(bm, size, center, mat=None):
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.scale(tmp, vec=size, verts=tmp.verts)
    bmesh.ops.translate(tmp, vec=center, verts=tmp.verts)
    for f in tmp.faces:
        f.smooth = True
        if mat is not None:
            f.material_index = mat
    for e in tmp.edges:
        e.smooth = False
    uv_layer(tmp)
    inner_layer(tmp)
    merge(bm, tmp)


def cyl(bm, r, z0, z1, center=(0.0, 0.0), segs=8, axis="Z", caps=True, mat=None, r_top=None):
    tmp = bmesh.new()
    bmesh.ops.create_cone(tmp, cap_ends=caps, cap_tris=False, segments=segs, radius1=r,
                          radius2=r if r_top is None else r_top, depth=z1 - z0)
    if axis == "X":
        bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
        bmesh.ops.translate(tmp, vec=((z0 + z1) / 2, center[0], center[1]), verts=tmp.verts)
    elif axis == "Y":
        bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
        bmesh.ops.translate(tmp, vec=(center[0], (z0 + z1) / 2, center[1]), verts=tmp.verts)
    else:
        bmesh.ops.translate(tmp, vec=(center[0], center[1], (z0 + z1) / 2), verts=tmp.verts)
    for f in tmp.faces:
        f.smooth = True
        if mat is not None:
            f.material_index = mat
    for e in tmp.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > math.radians(50):
            e.smooth = False
    uv_layer(tmp)
    inner_layer(tmp)
    merge(bm, tmp)


def orient(bm, ref):
    """Flips the whole part if most of its area faces toward `ref` (a point inside or behind it)."""
    bm.normal_update()
    s = 0.0
    for f in bm.faces:
        s += f.normal.dot(f.calc_center_median() - Vector(ref)) * f.calc_area()
    if s < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])


def bead(bm, p0, p1, up, width=0.016, height=0.006, segs=None, mat=M_WELD, blco_off=(0.0, 0.0, 0.0)):
    """A weld bead (two faces, a ridge) from p0 to p1 lying on a surface whose normal is `up`; its texture
    coordinates (attribute blco) run along the bead like the Weld kit part's."""
    p0, p1, up = Vector(p0), Vector(p1), Vector(up).normalized()
    t = (p1 - p0)
    L = t.length
    t.normalize()
    side = up.cross(t).normalized()
    n = segs or max(1, int(round(L / 0.12)))
    bl = bm.verts.layers.float_vector.get("blco") or bm.verts.layers.float_vector.new("blco")
    rows = []
    for k in range(n + 1):
        p = p0 + t * (L * k / n)
        wob = 0.0008 * math.sin(k * 2.1 + p0.x * 7)
        row = []
        for sgn, h in ((-1, 0.0), (0, 1.0), (1, 0.0)):
            v = bm.verts.new(p + side * (sgn * width / 2 + wob) + up * height * h)
            v[bl] = (L * k / n + blco_off[0], sgn * width / 2 + blco_off[1], blco_off[2])
            row.append(v)
        rows.append(row)
    uvl = uv_layer(bm)
    for k in range(n):
        for a in range(2):
            f = bm.faces.new((rows[k][a], rows[k][a + 1], rows[k + 1][a + 1], rows[k + 1][a]))
            f.smooth = True
            f.material_index = mat
            if f.normal.dot(up) < 0:
                f.normal_flip()
            for lp in f.loops:
                co = lp.vert[bl]
                lp[uvl].uv = (co[0], co[1])


# ---------------------------------------------------------------- the kit

KIT = []
META = {}
CONTEXT = []


def kit_part(name, bm, mat=M_PAINT, seed=0.0, dmg=0, decal=0, rust=1.0, wear=1.0, grime=1.0, uvw=1.0, smart=True,
             context=(), sharp=None):
    if mat is not None:
        for f in bm.faces:
            if f.material_index == 0 and mat != 0:
                f.material_index = mat
    me = bpy.data.meshes.new("Kit_" + name)
    bm.to_mesh(me)
    bm.free()
    for m in MATS:
        me.materials.append(m)
    if sharp is not None:
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(sharp))
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    if "blco" in me.attributes:
        b = np.empty(n * 3, np.float32)
        me.attributes["blco"].data.foreach_get("vector", b)
        b = b.reshape(-1, 3)
        has = np.abs(b).sum(axis=1) > 0
        co = co.reshape(-1, 3)
        co[has] = b[has]
        co = co.ravel()
        me.attributes.remove(me.attributes["blco"])
    inner = np.zeros(n, np.float32)
    if "inner" in me.attributes:
        me.attributes["inner"].data.foreach_get("value", inner)
    else:
        me.attributes.new("inner", "FLOAT", "POINT")
    kd = np.tile(np.array([seed, dmg, decal], np.float32), (n, 1))
    kd[inner > 0.5, 2] = 0.0
    for nm, vals in (("lco", co), ("kd", kd.ravel()), ("kw", np.tile(np.array([rust, wear, grime], np.float32), n))):
        a = me.attributes.get(nm) or me.attributes.new(nm, "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", vals)
    kp = me.attributes.new("kpart", "INT", "FACE")
    kp.data.foreach_set("value", np.full(len(me.polygons), len(KIT), np.int32))
    obj = tk.link(bpy.data.objects.new("Kit_" + name, me))
    META[name] = dict(index=len(KIT), uvw=uvw, smart=smart, context=list(context))
    KIT.append(obj)
    return obj


def module_profile(col, sub=1):
    return profile(MOD_X[col] - 0.45, YIN, WALL_SEGS, sub)


def border_falloff(x, z, w=0.1):
    """0 on the module borders (every 0.9 m from -1.35, the rails and the half seam), 1 inside."""
    xm = (x + 1.35) % 0.9
    dx = min(xm, 0.9 - xm)
    dz = min(abs(z - RB_TOP), abs(z - ZM), abs(RT_BOT - z))
    return smoothstep(0.0, w, dx) * smoothstep(0.0, w, dz)


def oil_can(v, amp=0.0045):
    x, y, z = v.co
    v.co.y += amp * border_falloff(x, z, 0.12) * fbm((x * 1.7, 0.4, z * 1.3), 2, 1.0) * 2.0


def profile_y(xs, ys, x):
    return float(np.interp(x, xs, ys))


def wall_half(bm, col, half, sub=1, rows=5, zs=None):
    xs, ys, folds = module_profile(col, sub)
    z0, z1 = HALF_Z[half]
    zs = zs or [z0 + (z1 - z0) * k / rows for k in range(rows + 1)]
    G = sheet(bm, xs, ys, zs, folds)
    for v in bm.verts:
        oil_can(v)
    return xs, ys, G


def rail_context(half, col):
    x = MOD_X[col]
    if half == "L":
        return [((0.92, 0.06, 0.14), (x, -0.465, RB_TOP - 0.07))]
    return [((0.92, 0.08, 0.08), (x, -0.45, RT_BOT + 0.04))]


def dent_y(x, z, dents, crease=None):
    d = 0.0
    for (cx, cz, r, dep) in dents:
        q = math.hypot(x - cx, z - cz) / r
        if q < 1.0:
            d += dep * (1 - q * q) ** 2
    if crease:
        (ax, az), (bx, bz), w, dep = crease
        abx, abz = bx - ax, bz - az
        t = clamp01(((x - ax) * abx + (z - az) * abz) / (abx * abx + abz * abz))
        dist = math.hypot(x - ax - t * abx, z - az - t * abz)
        if dist < w:
            d += dep * (1 - (dist / w) ** 2) * math.sin(math.pi * t) ** 0.5
    return d


def crush(v, d, xs, ys):
    """Pushes a corrugated sheet in by d: crests move the whole way, valleys only once the crest has reached them."""
    y0 = profile_y(xs, ys, v.co.x)
    depth = (y0 - YS) / DEPTH
    v.co.y += d - min(d, DEPTH * 0.7) * depth


def boundary_rim(bm, edges, thick=0.003):
    """Gives a cut edge of a sheet its thickness: a strip extruded inward (+Y)."""
    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    nv = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in nv:
        v.co.y += thick
    return [f for f in res["geom"] if isinstance(f, bmesh.types.BMFace)], nv


def build_wall_halves():
    for col in "ABC":
        for half in "LU":
            bm = bmesh.new()
            wall_half(bm, col, half)
            kit_part(col + half, bm, decal=1, smart=False, context=rail_context(half, col))
    # the corner's -X upper return: a C-upper panel with its own wear and no stencils
    bm = bmesh.new()
    wall_half(bm, "C", "U")
    kit_part("RU", bm, seed=5.0, decal=0, smart=False, context=rail_context("U", "C"))
    # A lower, dented (DMG1)
    bm = bmesh.new()
    xs, ys, G = wall_half(bm, "A", "L", sub=2, rows=11)
    for v in bm.verts:
        x, z = v.co.x, v.co.z
        f = border_falloff(x, z, 0.07)
        d = dent_y(x, z, DENTS_A, CREASE_A) * f
        crush(v, d, xs, ys)
        v.co.y += 0.006 * fbm((x * 9, 1.1, z * 9), 2, 3.0) * min(1.0, d / 0.01) * f
    kit_part("ALd", bm, dmg=1, decal=1, smart=False, context=rail_context("L", "A"))
    # B upper, shot (DMG1): the holes are in the damage map; two small dents
    bm = bmesh.new()
    xs, ys, G = wall_half(bm, "B", "U")
    for v in bm.verts:
        d = dent_y(v.co.x, v.co.z, [(-0.05, 1.75, 0.22, 0.012), (0.3, 2.0, 0.15, 0.01)]) * \
            border_falloff(v.co.x, v.co.z, 0.07)
        crush(v, d, xs, ys)
    kit_part("BUh", bm, dmg=1, decal=1, smart=False, context=rail_context("U", "B"))
    build_torn()
    build_peeled()
    build_rusted()


def point_in_poly(x, z, poly):
    ins = False
    n = len(poly)
    for k in range(n):
        (ax, az), (bx, bz) = poly[k], poly[(k + 1) % n]
        if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az):
            ins = not ins
    return ins


def poly_dist(x, z, poly):
    best = 1e9
    n = len(poly)
    for k in range(n):
        (ax, az), (bx, bz) = poly[k], poly[(k + 1) % n]
        abx, abz = bx - ax, bz - az
        t = clamp01(((x - ax) * abx + (z - az) * abz) / (abx * abx + abz * abz))
        best = min(best, math.hypot(x - ax - t * abx, z - az - t * abz))
    return best


def ray_poly(cx, cz, dx, dz, poly):
    """Distance along a ray from (cx, cz) to the polygon outline (first crossing)."""
    best = 1e9
    n = len(poly)
    for k in range(n):
        (ax, az), (bx, bz) = poly[k], poly[(k + 1) % n]
        ex, ez = bx - ax, bz - az
        den = dx * ez - dz * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - cx) * ez - (az - cz) * ex) / den
        u = ((ax - cx) * dz - (az - cz) * dx) / den
        if t > 0 and 0 <= u <= 1:
            best = min(best, t)
    return best


def build_torn():
    """B lower (DMG2): a big hole torn in, the jagged lips bent into the wall."""
    bm = bmesh.new()
    zs = [RB_TOP + (ZM - RB_TOP) * k / 12 for k in range(13)]
    xs, ys, G = wall_half(bm, "B", "L", sub=2, zs=zs)
    kill = [f for f in bm.faces if point_in_poly(f.calc_center_median().x, f.calc_center_median().z, TEAR)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    cx, cz = TEAR_C
    rim_edges = [e for e in bm.edges if len(e.link_faces) == 1 and all(
        border_falloff(v.co.x, v.co.z, 0.02) > 0.5 for v in e.verts)]
    rim_verts = {v for e in rim_edges for v in e.verts}
    for v in rim_verts:
        dx, dz = v.co.x - cx, v.co.z - cz
        L = math.hypot(dx, dz)
        t = ray_poly(cx, cz, dx / L, dz / L, TEAR)
        if t < 1e8 and abs(t - L) < 0.14:
            nx = cx + dx / L * t
            v.co.x, v.co.z = nx, cz + dz / L * t
            v.co.y = profile_y(xs, ys, nx)
    faces, nv = boundary_rim(bm, rim_edges)
    il = inner_layer(bm)
    for v in nv:
        v[il] = 1.0
    bm.normal_update()
    for f in faces:
        c = f.calc_center_median()
        if f.normal.x * (cx - c.x) + f.normal.z * (cz - c.z) < 0:
            f.normal_flip()
    rnd = random.Random(8)
    for v in bm.verts:
        x, z = v.co.x, v.co.z
        if point_in_poly(x, z, TEAR):
            dist = 0.0
        else:
            dist = poly_dist(x, z, TEAR)
        if dist < 0.24:
            a = math.atan2(z - cz, x - cx)
            petal = 0.75 + 0.5 * (0.5 + 0.5 * math.sin(a * 5 + 1.3))
            push = 0.13 * (1 - dist / 0.24) ** 2.2 * petal
            push *= border_falloff(x, z, 0.08)
            crush(v, push, xs, ys)
            v.co.y += 0.012 * fbm((x * 12, 2.2, z * 12), 2, 5.0) * (1 - dist / 0.24)
    kit_part("BLt", bm, dmg=2, decal=1, smart=False, context=rail_context("L", "B"))


def build_peeled():
    """A lower (DMG2): torn free along the top, bottom and right; both sides and the cut edges are modelled. Baked
    flat so its texture is right; peel_field rolls it back into the wall when the wall is built."""
    bm = bmesh.new()
    xs, ys, folds = module_profile("A", 2)
    zs = [RB_TOP + (ZM - RB_TOP) * k / 5 for k in range(6)]
    Gf = sheet(bm, xs, ys, zs, folds)
    Gb = sheet(bm, xs, ys, zs, folds, flip=True, inner=1.0, yoff=0.003)
    for v in bm.verts:
        oil_can(v)
    # cut edges: strips joining the two sides all round
    uvl = uv_layer(bm)
    n, m = len(xs), len(zs)
    ring = [(i, 0) for i in range(n)] + [(n - 1, j) for j in range(1, m)] + \
        [(i, m - 1) for i in range(n - 2, -1, -1)] + [(0, j) for j in range(m - 2, 0, -1)]
    s = 0.0
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        fa, fb, ba, bb = Gf[a[0]][a[1]], Gf[b[0]][b[1]], Gb[a[0]][a[1]], Gb[b[0]][b[1]]
        f = bm.faces.new((fb, fa, ba, bb))
        f.smooth = True
        L = (fb.co - fa.co).length
        for lp, uv in zip(f.loops, ((s + L, 0.0), (s, 0.0), (s, 0.003), (s + L, 0.003))):
            lp[uvl].uv = uv
        s += L
    bm.normal_update()
    cen = Vector((-0.9, -0.46, (RB_TOP + ZM) / 2))
    for f in bm.faces:
        if f.normal.y == 0 or abs(f.normal.y) < 0.5:
            c = f.calc_center_median()
            if f.normal.dot(c - cen) < 0:
                f.normal_flip()
    kit_part("ALp", bm, dmg=2, decal=1, smart=False, context=rail_context("L", "A"))


PEEL_R = 0.085


def peel_field(p):
    """Rolls the A-lower panel (baked flat) back into the wall about the vertical line x = PEEL_X, twisted (bent
    further at the top) and crumpled; both sides of the sheet follow (d is the depth behind the crests)."""
    x, y, z = p.x, p.y, p.z
    sdist = x - PEEL_X
    if sdist <= 0 or y > 0:
        return None
    tz = clamp01((z - RB_TOP) / (ZM - RB_TOP))
    th_max = math.radians(32 + 40 * tz + 8 * fbm((0.3, tz * 2, 0.5), 2, 7.0))
    R = PEEL_R * (1.0 + 0.25 * tz)
    r = R - (y - YS)
    th = sdist / R
    if th <= th_max:
        nx, ny = PEEL_X + r * math.sin(th), YS + R - r * math.cos(th)
    else:
        rest = sdist - R * th_max
        nx = PEEL_X + r * math.sin(th_max) + rest * math.cos(th_max)
        ny = YS + R - r * math.cos(th_max) + rest * math.sin(th_max)
    crumple = 0.02 * fbm((x * 6, 3.3, z * 4), 3, 9.0) * smoothstep(0.0, 0.2, sdist)
    return (nx + crumple * 0.5 - x, ny + crumple - y, -0.03 * smoothstep(0.1, 0.6, sdist) * (tz - 0.5))


def build_rusted():
    """C lower (DMG2): rotten through along the bottom, the edge ragged and lifted off the rail."""
    bm = bmesh.new()
    zs = [-0.36, -0.29, -0.2, -0.08, 0.12, 0.4, 0.7, ZM]
    xs, ys, G = wall_half(bm, "C", "L", sub=2, zs=zs)
    for i, colv in enumerate(G):
        x = xs[i]
        taper = smoothstep(0.45, 0.55, x)
        lift = max(0.0, 0.03 + 0.1 * fbm((x * 5.0, 0.7, 0.2), 3, 11.0)) * taper
        lift += 0.025 * abs(math.sin(x * 41.0)) * taper
        colv[0].co.z += lift
        colv[1].co.z = max(colv[1].co.z, colv[0].co.z + 0.03)
        colv[2].co.z = max(colv[2].co.z, colv[1].co.z + 0.03)
    bot = [e for e in bm.edges if len(e.link_faces) == 1 and all(v.co.z < -0.2 for v in e.verts)
           and all(0.46 < v.co.x for v in e.verts)]
    faces, nv = boundary_rim(bm, bot)
    il = inner_layer(bm)
    for v in nv:
        v[il] = 1.0
    bm.normal_update()
    for f in faces:
        if f.normal.z > 0:
            f.normal_flip()
    kit_part("CLr", bm, dmg=2, decal=1, rust=1.8, smart=False, context=rail_context("L", "C"))


def build_liner():
    """The inside of the wall, seen only through holes and gaps: both skins' inner faces (corrugated), the ends,
    floor and ceiling, all facing in."""
    bm = bmesh.new()
    segs = WALL_SEGS * 3
    xs, ys, folds = profile(-1.35, YIN, segs)
    keep = [i for i, x in enumerate(xs) if -1.31 <= x <= 1.31]
    xs2 = [-1.30] + [xs[i] for i in keep] + [1.30]
    ys2 = [profile_y(xs, ys, -1.30)] + [ys[i] for i in keep] + [profile_y(xs, ys, 1.30)]
    zs = [RB_TOP, RT_BOT - 0.01]
    sheet(bm, xs2, ys2, zs, flip=True, inner=2.0, yoff=0.006)
    tmp = bmesh.new()
    sheet(tmp, xs2, ys2, zs, flip=True, inner=2.0, yoff=0.006)
    bmesh.ops.rotate(tmp, verts=tmp.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi, 3, "Z"))
    merge(bm, tmp)
    yi = YIN + 0.006
    il = inner_layer(bm)
    uvl = uv_layer(bm)
    quads = [((-1.3, yi, RB_TOP), (-1.3, -yi, RB_TOP), (-1.3, -yi, RT_BOT - 0.01), (-1.3, yi, RT_BOT - 0.01)),
             ((1.3, -yi, RB_TOP), (1.3, yi, RB_TOP), (1.3, yi, RT_BOT - 0.01), (1.3, -yi, RT_BOT - 0.01)),
             ((-1.3, -yi, RB_TOP), (-1.3, yi, RB_TOP), (1.3, yi, RB_TOP), (1.3, -yi, RB_TOP)),
             ((-1.3, yi, RT_BOT - 0.01), (-1.3, -yi, RT_BOT - 0.01), (1.3, -yi, RT_BOT - 0.01),
              (1.3, yi, RT_BOT - 0.01))]
    for q in quads:
        vs = [bm.verts.new(p) for p in q]
        for v in vs:
            v[il] = 2.0
        f = bm.faces.new(vs)
        f.smooth = True
    bm.normal_update()
    zc = (RB_TOP + RT_BOT) / 2
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(c.y) > 0.3:
            bad = f.normal.y * -c.y < 0
        elif abs(c.x) > 1.29:
            bad = f.normal.x * -c.x < 0
        else:
            bad = f.normal.z * (zc - c.z) < 0
        if bad:
            f.normal_flip()
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > math.radians(30):
            e.smooth = False
    kit_part("Liner", bm, rust=1.4, grime=2.5, uvw=0.05)


POST_PROF = [(XPI, YPO), (XPI + 0.028, YPO), (XPI + 0.036, YPO + 0.012), (XPO - 0.044, YPO + 0.012),
             (XPO - 0.036, YPO), (XPO - 0.016, YPO), (XPO, YPO + 0.016), (XPO, YPI), (XPI + 0.035, YPI),
             (XPI, YPI - 0.035)]


def build_posts():
    for name, rows, seed in (("Post1", 1, 1.0), ("Post2", 7, 2.0)):
        bm = bmesh.new()
        z0, z1 = Z0 + CZ, ZT - CZ
        zs = [z0 + (z1 - z0) * k / rows for k in range(rows + 1)]
        P = POST_PROF + [POST_PROF[0]]
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        sheet(bm, xs, ys, zs, folds=range(1, len(P) - 1))
        orient(bm, (XPI + 0.075, YPO + 0.075, 1.0))
        for v in bm.verts:
            v.co.x += 0.002 * fbm((0.2, seed, v.co.z * 1.5), 2, seed)
        kit_part(name, bm, seed=seed, rust=1.1, uvw=0.8, smart=False,
                 context=[((0.2, 0.2, 0.12), (1.41, -0.42, Z0 + CZ / 2)), ((0.2, 0.2, 0.12), (1.41, -0.42, ZT - CZ / 2))])


def holed_face(bm, corners, center, axes, depth, mat=M_STEEL):
    """A rectangular face (4 corners, counter-clockwise seen from outside) with an oval hole (8 points, through the
    corners' directions) recessed `depth` into the part. axes = (u vector * half width, v vector * half height)."""
    c = Vector(center)
    au, av = Vector(axes[0]), Vector(axes[1])
    nrm = au.cross(av).normalized()
    pts_o, pts_i = [], []
    dirs = []
    for k in range(4):
        d = Vector(corners[k]) - c
        ang = math.atan2(d.dot(av.normalized()), d.dot(au.normalized()))
        dirs.append((ang, Vector(corners[k])))
    dirs.sort(key=lambda t: t[0])
    ring = []
    for k in range(4):
        a0, p0 = dirs[k]
        a1, p1 = dirs[(k + 1) % 4]
        if a1 < a0:
            a1 += 2 * math.pi
        ring.append((a0, p0))
        am = (a0 + a1) / 2
        # the point on the rectangle edge between the corners, in the direction am
        q = p0.lerp(p1, 0.5)
        ring.append((am, q))
    for a, p in ring:
        pts_o.append(bm.verts.new(p))
        pts_i.append(bm.verts.new(c + au * math.cos(a) + av * math.sin(a)))
    deep = [bm.verts.new(v.co - nrm * depth) for v in pts_i]
    faces = []
    n = len(ring)
    for k in range(n):
        k1 = (k + 1) % n
        faces.append(bm.faces.new((pts_o[k], pts_o[k1], pts_i[k1], pts_i[k])))
        faces.append(bm.faces.new((pts_i[k], pts_i[k1], deep[k1], deep[k])))
    faces.append(bm.faces.new(deep))
    for f in faces:
        f.material_index = mat
        f.smooth = True
    return faces


def build_casting():
    """ISO corner casting at the bottom front-right corner: side, end and bottom apertures."""
    bm = bmesh.new()
    x0, x1, y0, y1, z0, z1 = 1.5 - CX, 1.5, -0.5, -0.5 + CY, Z0, Z0 + CZ
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    # front (-Y)
    holed_face(bm, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], ((x0 + x1) / 2, y0, (z0 + z1) / 2 + 0.004),
               (X * 0.034, Z * 0.022), 0.035)
    # end (+X)
    holed_face(bm, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (x1, (y0 + y1) / 2, (z0 + z1) / 2 + 0.004),
               (Y * 0.027, Z * 0.021), 0.035)
    # bottom (-Z)
    holed_face(bm, [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], ((x0 + x1) / 2, (y0 + y1) / 2, z0),
               (Y * 0.026, X * 0.05), 0.03)
    for quad in (((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)),
                 ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
                 ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))):
        f = bm.faces.new([bm.verts.new(p) for p in quad])
        f.material_index = M_STEEL
        f.smooth = True
    bm.normal_update()
    cen = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    for f in bm.faces:
        if len(f.verts) == 4 and f.calc_area() > 0.01:
            if f.normal.dot(f.calc_center_median() - cen) < 0:
                f.normal_flip()
    for v in bm.verts:
        v.co += Vector((0.0015 * fbm(v.co * 30, 1, 3.0), 0.0015 * fbm(v.co * 30, 1, 4.0), 0.0))
    kit_part("Cast", bm, mat=M_STEEL, seed=3.0, rust=1.4, uvw=1.3, sharp=30)


def build_rails():
    bm = bmesh.new()
    prof = [(-0.432, RB_TOP), (YR + 0.006, RB_TOP), (YR, RB_TOP - 0.006), (YR, RB_TOP - 0.05), (YR + 0.012, RB_TOP - 0.062),
            (YR + 0.012, Z0 + 0.03), (YR, Z0 + 0.018), (YR, Z0)]
    sweep(bm, prof, "X", -1.5 + CX, 1.5 - CX, segs=4)
    orient(bm, (0.0, -0.3, -0.45))
    for v in bm.verts:
        v.co.y += 0.002 * fbm((v.co.x * 2, 0.5, 0.1), 2, 5.0)
    kit_part("RailB", bm, seed=4.0, rust=1.3, uvw=0.9, smart=False)
    bm = bmesh.new()
    prof = [(-0.41, RT_TOP), (YR + 0.006, RT_TOP), (YR, RT_TOP - 0.006), (YR, RT_BOT + 0.006), (YR + 0.006, RT_BOT),
            (-0.41, RT_BOT)]
    sweep(bm, prof, "X", -1.5 + CX, 1.5 - CX, segs=3, closed=True)
    orient(bm, (0.0, -0.45, (RT_BOT + RT_TOP) / 2))
    kit_part("RailT", bm, seed=5.0, uvw=0.9, smart=False)


def build_roof():
    bm = bmesh.new()
    zt, zl = RT_TOP - 0.012, RT_TOP - 0.028
    segs = [(0.1, zl), (0.041, zt), (0.1, zt), (0.041, zl)] * 10
    xs, zz, folds = profile(-1.41, zl, segs)
    tmp = bmesh.new()
    sheet(tmp, xs, zz, [-0.41, -0.14, 0.14, 0.41], folds)
    # sheet() sweeps along z; turn it so the profile is (x, z) and the sweep runs along y
    M = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
    bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
    merge(bm, tmp)
    orient(bm, (0.0, 0.0, 1.0))
    for v in bm.verts:
        v.co.z -= 0.012 * (1 - abs(v.co.y) / 0.41) * (0.5 + 0.5 * fbm((v.co.x * 1.5, v.co.y, 0.2), 2, 6.0)) \
            * smoothstep(0, 0.1, 1.41 - abs(v.co.x))
    kit_part("Roof", bm, seed=6.0, rust=1.5, grime=1.3, uvw=0.75, smart=False)


def build_cap():
    bm = bmesh.new()
    box(bm, (0.006, 2 * YPI * -1, 1.79), (XPO - 0.009, 0.0, RB_TOP + 0.895), M_STEEL)
    box(bm, (0.006, 2 * YPI * -1 - 0.02, 1.0), (XPO - 0.005, 0.004, RT_BOT - 0.5), M_STEEL)
    for v in bm.verts:
        v.co.x += 0.003 * fbm((0.3, v.co.y * 2, v.co.z * 2), 2, 7.0) * (1 if v.co.x > XPO - 0.009 else 0)
    kit_part("Cap", bm, mat=M_STEEL, seed=7.0, rust=1.2, uvw=0.8, sharp=40)


def build_weld():
    bm = bmesh.new()
    bead(bm, (0, 0, 0), (0.5, 0, 0), (0, 0, 1), segs=2)
    kit_part("Weld", bm, mat=M_WELD, seed=8.0, uvw=1.6)


def build_patches():
    for name, (cx, cz), (w, h), seed in (("Patch1", (-1.0, 1.32), (0.42, 0.34), 9.0),
                                        ("Patch2", (0.0, 0.0), (0.3, 0.26), 10.0)):
        bm = bmesh.new()
        y0 = YS - 0.0065
        box(bm, (w, 0.006, h), (cx, y0 + 0.003, cz), M_STEEL)
        c = [(cx - w / 2, cz - h / 2), (cx + w / 2, cz - h / 2), (cx + w / 2, cz + h / 2), (cx - w / 2, cz + h / 2)]
        for k in range(4):
            (ax, az), (bx, bz) = c[k], c[(k + 1) % 4]
            bead(bm, (ax, y0 - 0.001, az), (bx, y0 - 0.001, bz), (0, -1, 0), width=0.013, height=0.005,
                 blco_off=(k * 0.7 + seed, 0.0, 0.0))
        for v in bm.verts:
            v.co.y -= 0.002 * fbm((v.co.x * 4, 0.1, v.co.z * 4), 2, seed)
        kit_part(name, bm, mat=None, seed=seed, rust=1.3, uvw=1.1, sharp=40)


DOOR_SEGS = [(0.031, DYIN)] + [(0.043, DYS), (0.091, DYS), (0.043, DYIN), (0.062, DYIN)] * 4 + \
    [(0.043, DYS), (0.091, DYS), (0.043, DYIN), (0.031, DYIN)]


def door_profile(x0):
    xs, ys, folds = profile(x0, DYIN, DOOR_SEGS)
    w = PX0 - PX1
    k = w / (xs[-1] - xs[0])
    xs = [x0 + (x - x0) * k for x in xs]
    return xs, ys, folds


def build_doors():
    for name, x0, (z0, z1), decal, seed in (("DUl", -PX0, (DZM, PZ1), 2, 20.0), ("DL", -PX0, (PZ0, DZM), 0, 21.0),
                                           ("DUr", PX1, (DZM, PZ1), 2, 22.0)):
        bm = bmesh.new()
        xs, ys, folds = door_profile(x0)
        zs = [z0 + (z1 - z0) * k / 6 for k in range(7)]
        sheet(bm, xs, ys, zs, folds)
        for v in bm.verts:
            v.co.y += 0.003 * fbm((v.co.x * 2, 0.6, v.co.z * 2), 2, seed) * smoothstep(0, 0.08, min(
                abs(v.co.x - xs[0]), abs(v.co.x - xs[-1]), abs(v.co.z - z0), abs(v.co.z - z1)))
        ctx = [((0.07, 0.06, abs(z1 - z0)), (x0 - 0.03 if x0 < 0 else x0 - 0.03, -0.395, (z0 + z1) / 2))]
        kit_part(name, bm, seed=0.0, decal=decal, smart=False, context=ctx)
    bm = bmesh.new()
    xs, ys, folds = door_profile(-PX0)
    sheet(bm, xs, ys, [PZ0, PZ1], folds, flip=True, yoff=0.003)
    kit_part("DB", bm, seed=23.0, rust=1.2, grime=1.4, uvw=0.35, smart=False)
    # leaf frame: a stile and a rail (rectangular tubes)
    bm = bmesh.new()
    sweep(bm, [(-LX_OUT, LYF), (-PX0, LYF), (-PX0, LYB), (-LX_OUT, LYB)], "Z", LZ0, LZ1, segs=3, closed=True)
    orient(bm, (-LX_OUT + 0.03, (LYF + LYB) / 2, 1.0))
    kit_part("Stile", bm, seed=24.0, uvw=0.9, smart=False)
    bm = bmesh.new()
    sweep(bm, [(LYF, LZ0), (LYF, LZ0 + LFW), (LYB, LZ0 + LFW), (LYB, LZ0)], "X", -PX0, -PX1, segs=2, closed=True)
    orient(bm, (-0.6, (LYF + LYB) / 2, LZ0 + LFW / 2))
    kit_part("LRail", bm, seed=25.0, uvw=0.9, smart=False)


def build_door_hardware():
    x = BAR_X[0]
    # locking bar with its cams
    bm = bmesh.new()
    zs = [LZ0 + 0.015, 0.4, 1.3, LZ1 - 0.015]
    for a, b in zip(zs[:-1], zs[1:]):
        cyl(bm, BAR_R, a, b, (x, BAR_Y), segs=8, caps=False)
    cyl(bm, BAR_R * 1.15, LZ0 + 0.0, LZ0 + 0.015, (x, BAR_Y), segs=8)
    cyl(bm, BAR_R * 1.15, LZ1 - 0.015, LZ1, (x, BAR_Y), segs=8)
    for zc in (LZ0 + 0.045, LZ1 - 0.045):
        box(bm, (0.05, 0.03, 0.05), (x + 0.018, BAR_Y, zc))
    kit_part("Bar", bm, seed=30.0, rust=1.2, uvw=1.1, sharp=50)
    # bar guide: a strap round the bar, welded to the door
    bm = bmesh.new()
    box(bm, (0.075, 0.012, 0.035), (x, BAR_Y - BAR_R - 0.004, 0.0))
    for s in (-1, 1):
        box(bm, (0.01, LYF - (BAR_Y - BAR_R - 0.01), 0.035), (x + s * 0.033, (LYF + BAR_Y - BAR_R - 0.01) / 2, 0.0))
    kit_part("Guide", bm, seed=31.0, uvw=1.2, sharp=40)
    # handle: hub on the bar, the lever lying flat toward the meeting edge, a grip
    bm = bmesh.new()
    cyl(bm, 0.027, HANDLE_Z - 0.035, HANDLE_Z + 0.035, (x, BAR_Y), segs=8)
    box(bm, (0.34, 0.012, 0.034), (x + 0.19, BAR_Y - 0.022, HANDLE_Z))
    cyl(bm, 0.011, x + 0.33, x + 0.43, (BAR_Y - 0.03, HANDLE_Z), segs=6, axis="X")
    kit_part("Handle", bm, seed=32.0, uvw=1.2, sharp=50)
    # handle retainer (the catch the lever drops into) with a hasp
    bm = bmesh.new()
    rx = x + 0.37
    box(bm, (0.012, LYF - (BAR_Y - 0.04), 0.09), (rx - 0.03, (LYF + BAR_Y - 0.04) / 2, HANDLE_Z))
    box(bm, (0.012, LYF - (BAR_Y - 0.04), 0.09), (rx + 0.03, (LYF + BAR_Y - 0.04) / 2, HANDLE_Z))
    box(bm, (0.072, 0.008, 0.02), (rx, BAR_Y - 0.039, HANDLE_Z - 0.035))
    kit_part("Retainer", bm, seed=33.0, uvw=1.2, sharp=40)
    # hinge: knuckle on the pin axis and a blade on the door face
    bm = bmesh.new()
    cyl(bm, 0.016, -0.034, 0.034, (-GXH, GYH), segs=8)
    box(bm, (0.25, 0.008, 0.066), (-GXH + 0.135, LYF - 0.004, 0.0))
    box(bm, (0.02, LYF - GYH + 0.004, 0.066), (-GXH + 0.016, (LYF + GYH) / 2 - 0.002, 0.0))
    kit_part("Hinge", bm, seed=34.0, uvw=1.2, sharp=50)
    # post side of the hinge: lugs above and below the knuckle and the pin (frame)
    bm = bmesh.new()
    for s in (-1, 1):
        box(bm, (XPI - GXH + 0.016, 0.032, 0.026), ((-XPI - GXH + 0.016) / 2 - 0.0, GYH, s * 0.05))
    cyl(bm, 0.0075, -0.072, 0.072, (-GXH, GYH), segs=6, mat=M_STEEL)
    cyl(bm, 0.012, 0.064, 0.072, (-GXH, GYH), segs=6, mat=M_STEEL)
    kit_part("Lug", bm, mat=None, seed=35.0, uvw=1.2, sharp=50)
    # cam keeper (lower; flipped for the header)
    bm = bmesh.new()
    box(bm, (0.075, 0.055, 0.17), (x + 0.018, -0.4475, Z0 + 0.085))
    box(bm, (0.03, 0.02, 0.17), (x + 0.018, -0.4775, Z0 + 0.085))
    kit_part("Keeper", bm, seed=36.0, rust=1.4, uvw=1.1, sharp=40)
    # rubber seal strip, 1 m along z
    bm = bmesh.new()
    box(bm, (0.022, 0.008, 1.0), (-LX_OUT - 0.009, -0.401, 0.5), M_RUBBER)
    kit_part("Seal", bm, mat=M_RUBBER, seed=37.0, uvw=0.5, sharp=40)
    # CSC safety approval plate
    bm = bmesh.new()
    box(bm, (0.16, 0.003, 0.1), (-0.66, DYS - 0.0035, 1.25), M_ALU)
    kit_part("CSC", bm, mat=M_ALU, seed=38.0, uvw=2.0, sharp=40)


def build_frame_parts():
    bm = bmesh.new()
    prof = [(-0.40, HDR_BOT), (YPO, HDR_BOT), (YPO, RT_TOP - 0.006), (YPO + 0.006, RT_TOP), (-0.40, RT_TOP)]
    sweep(bm, prof, "X", -1.5 + CX, 1.5 - CX, segs=4)
    orient(bm, (0.0, -0.3, (HDR_BOT + RT_TOP) / 2))
    kit_part("Header", bm, seed=40.0, uvw=0.85, smart=False)
    bm = bmesh.new()
    box(bm, (2 * XPI, 0.92, 0.012), (0.0, (LYF + 0.5 - PO) / 2, -0.406), M_STEEL)
    kit_part("Tread", bm, mat=M_STEEL, seed=41.0, uvw=0.6, sharp=40)
    for p in KIT[-1].data.attributes["kd"].data:
        p.vector = (p.vector[0], p.vector[1], 1.0)
    bm = bmesh.new()
    box(bm, (2 * XPI, 0.05, 0.09), (0.0, LYF + 0.025, Z0 + 0.045))
    kit_part("Sill", bm, seed=42.0, rust=1.4, uvw=0.8, sharp=40)


def build_kit():
    build_wall_halves()
    build_liner()
    build_posts()
    build_casting()
    build_rails()
    build_roof()
    build_cap()
    build_weld()
    build_patches()
    build_doors()
    build_door_hardware()
    build_frame_parts()
    log("kit parts:", len(KIT), "tris", sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in KIT))


# ---------------------------------------------------------------- bake, then split the kit back into parts

PART = {}


def bake_kit():
    gap, x, y, row_h, width = 0.7, 0.0, 0.0, 0.0, 16.0
    occl = []
    occ_mat = MATS[M_STEEL]
    for name, m in META.items():
        obj = KIT[m["index"]]
        co = np.array([v.co[:] for v in obj.data.vertices])
        lo, hi = co.min(axis=0), co.max(axis=0)
        size = hi - lo
        if x + size[0] > width:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        off = Vector((x - lo[0], y - lo[1], 30.0 - lo[2]))
        obj.data.transform(Matrix.Translation(off))
        m["offset"] = off
        for (sz, ctr) in m["context"]:
            o = tk.box("Ctx_" + name, sz, Vector(ctr) + off, occ_mat)
            occl.append(o)
        x += size[0] + gap
        row_h = max(row_h, size[1])
    bm = bmesh.new()
    for obj in KIT:
        bm.from_mesh(obj.data)
    me = bpy.data.meshes.new("ContainerKit")
    bm.to_mesh(me)
    bm.free()
    for m in MATS:
        me.materials.append(m)
    kit = tk.link(bpy.data.objects.new("ContainerKit", me))
    for obj in KIT:
        bpy.data.objects.remove(obj)
    kit = tk.triangulate(kit)
    unwrap(kit)
    bpy.context.scene.world = bpy.data.worlds.new("BakeWorld")
    try:
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME)
        tint = bake_tint(kit)
    except RuntimeError as err:
        log("bake failed (%s); retrying on the CPU" % err)
        bpy.context.scene.cycles.device = "CPU"
        paths = tk.bake_atlas(kit, ASSETS, MAT_NAME)
        tint = bake_tint(kit)
    write_tint(paths, tint)
    for o in occl:
        bpy.data.objects.remove(o)
    return kit, paths


def unwrap(kit):
    me = kit.data
    kp = np.empty(len(me.polygons), np.int32)
    me.attributes["kpart"].data.foreach_get("value", kp)
    by_index = {m["index"]: m for m in META.values()}
    smart = np.array([by_index[i]["smart"] for i in kp])
    me.polygons.foreach_set("select", smart)
    for o in bpy.context.scene.objects:
        o.select_set(o == kit)
    bpy.context.view_layer.objects.active = kit
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.002, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_start", ls)
    w = np.array([math.sqrt(by_index[i]["uvw"]) for i in kp], np.float32)
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    assert (lt == 3).all()
    lw = np.empty(len(me.loops), np.float32)
    lw[ls[:, None] + np.arange(3)[None, :]] = w[:, None]
    uv *= lw[:, None]
    me.uv_layers["UVMap"].data.foreach_set("uv", uv.ravel())
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.0025)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_tint(kit):
    img = tk._new_image(MAT_NAME + "_Tint", tk.TEX_SIZE, True)
    tk._with_emission(kit, "tint", lambda: tk._bake(kit, "EMIT", img, 4))
    return tk._pixels(img)[..., 0].copy()


def write_tint(paths, tint):
    img = bpy.data.images.load(paths["rmom"], check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    img.alpha_mode = "CHANNEL_PACKED"
    a = tk._pixels(img).copy()
    bpy.data.images.remove(img)
    a[..., 3] = np.clip(tint, 0.0, 1.0)
    tk.save_array(MAT_NAME + "_RMOMTint", a, paths["rmom"], True)
    # read it back: alpha must be the mask and the colour channels must survive where the mask is 0
    chk = bpy.data.images.load(paths["rmom"], check_existing=False)
    chk.colorspace_settings.name = "Non-Color"
    chk.alpha_mode = "CHANNEL_PACKED"
    b = tk._pixels(chk)
    bpy.data.images.remove(chk)
    zero = a[..., 3] < 0.05
    log("RMOM written: alpha mean %.3f, painted %.1f%%, unpainted %.1f%%" % (
        b[..., 3].mean(), 100 * (b[..., 3] > 0.5).mean(), 100 * zero.mean()),
        "| R error where unpainted %.4f" % (np.abs(b[..., 0][zero] - a[..., 0][zero]).max() if zero.any() else 0.0))


def extract_parts(kit, offsets=True):
    bm = bmesh.new()
    bm.from_mesh(kit.data)
    layer = bm.faces.layers.int.get("kpart")
    for name, m in META.items():
        part = bm.copy()
        lay = part.faces.layers.int.get("kpart")
        bmesh.ops.delete(part, geom=[f for f in part.faces if f[lay] != m["index"]], context="FACES")
        if offsets:
            bmesh.ops.translate(part, vec=-m["offset"], verts=part.verts)
        me = bpy.data.meshes.new("P_" + name)
        part.to_mesh(me)
        part.free()
        for a in ("kpart",):
            if a in me.attributes:
                me.attributes.remove(me.attributes[a])
        PART[name] = me
    bm.free()


def parts_unbaked():
    for name, m in META.items():
        me = KIT[m["index"]].data.copy()
        me.attributes.remove(me.attributes["kpart"])
        PART[name] = me
    for obj in KIT:
        obj.hide_render = True
        obj.hide_viewport = True


# ---------------------------------------------------------------- assembling pieces

class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.bm.faces.layers.int.new("trap_part")

    def add(self, part, M=None, deform=None, clip=(), label=None):
        tmp = bmesh.new()
        tmp.from_mesh(PART[part])
        if M is not None:
            bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
            if M.to_3x3().determinant() < 0:
                bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
        for co, no in clip:
            bmesh.ops.bisect_plane(tmp, geom=tmp.verts[:] + tmp.edges[:] + tmp.faces[:], dist=1e-6, plane_co=co,
                                   plane_no=no, clear_outer=True)
        if deform is not None:
            for v in tmp.verts:
                d = deform(v.co)
                if d is not None:
                    v.co += Vector(d)
        n0 = len(self.bm.faces)
        merge(self.bm, tmp)
        if label is not None:
            if label not in tk.PART_LABELS:
                tk.PART_LABELS.append(label)
            idx = tk.PART_LABELS.index(label)
            lay = self.bm.faces.layers.int.get("trap_part")
            self.bm.faces.ensure_lookup_table()
            for f in self.bm.faces[n0:]:
                f[lay] = idx

    def finish(self, name, material=None):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.clear()
        if material is not None:
            me.materials.append(material)
            me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32))
        else:
            for m in MATS:
                me.materials.append(m)
        for a in ("lco", "kd", "kw", "inner") if material is not None else ():
            if a in me.attributes:
                me.attributes.remove(me.attributes[a])
        return tk.link(bpy.data.objects.new(name, me))


def weld_run(B, p0, p1, up, deform=None, label=None, M=None):
    p0, p1, up = Vector(p0), Vector(p1), Vector(up).normalized()
    t = p1 - p0
    L = t.length
    t.normalize()
    side = up.cross(t).normalized()
    n = max(1, int(round(L / 0.5)))
    seg = L / n
    for k in range(n):
        o = p0 + t * seg * k
        R = Matrix((t, side, up)).transposed().to_4x4()
        W = Tm(*o) @ R @ Sc(seg / 0.5, 1.0, 1.0)
        B.add("Weld", (M @ W) if M is not None else W, deform=deform, label=label)


def cap_welds(B, M=Matrix.Identity(4), deform=None):
    """Weld beads round an end cap built at +X (M moves it)."""
    x = XPO - 0.006
    up = (1, 0, 0)
    for p0, p1 in (((x, YPI + 0.004, RB_TOP + 0.02), (x, YPI + 0.004, RT_BOT - 0.02)),
                   ((x, -YPI - 0.004, RB_TOP + 0.02), (x, -YPI - 0.004, RT_BOT - 0.02)),
                   ((x, YPI + 0.02, RT_BOT - 1.0), (x, -YPI - 0.02, RT_BOT - 1.0)),
                   ((x, YPI + 0.02, RB_TOP + 0.01), (x, -YPI - 0.02, RB_TOP + 0.01))):
        weld_run(B, p0, p1, up, deform=deform, M=M)


def end_rails(B, sx, M=Matrix.Identity(4), deform=None):
    """Bottom and top rails across an end (sx = +1 for +X), made from clipped copies of the side rails."""
    R = Tm(sx * 1.0, 0, 0) @ Rz(90 * sx)
    clip = (((0, 0.5 - CY, 0), (0, 1, 0)), ((0, -0.5 + CY, 0), (0, -1, 0)))
    for part in ("RailB", "RailT"):
        B.add(part, M @ R, deform=deform, clip=clip)


def bend_post(cx, cy, amount=1.0, sx=-1, sy=-1):
    """A corner post bent in by a blow at about 1.3 m, the sheets next to it following."""
    def f(p):
        t = (p.z - (Z0 + CZ)) / (ZT - Z0 - 2 * CZ)
        if t <= 0 or t >= 1:
            return None
        prof = smoothstep(0.0, 0.45, t) * (1 - smoothstep(0.45, 1.0, t))
        prof = prof ** 0.8
        w = 1 - smoothstep(0.12, 0.6, math.hypot(p.x - cx, p.y - cy))
        if w <= 0:
            return None
        return (-sx * 0.035 * prof * w * amount, -sy * 0.085 * prof * w * amount, 0.0)
    return f


def sprung_seam(p):
    x, z = p.x, p.z
    if x < 1.0 or p.y > 0:
        return None
    w = smoothstep(1.02, 1.35, x)
    b = math.sin(math.pi * clamp01((z + 0.25) / 1.95)) ** 1.5
    return (-0.02 * w ** 3 * b, 0.07 * w * w * b, 0.0)


def rail_dent(p):
    if p.y > 0 or p.z > -0.3:
        return None
    return (0.0, 0.028 * math.exp(-((p.x - 0.05) / 0.22) ** 2), 0.0)


def chain(*fs):
    def f(p):
        tot = Vector((0, 0, 0))
        hit = False
        for g in fs:
            d = g(p)
            if d is not None:
                tot += Vector(d)
                hit = True
                p = p + Vector(d)
        return tot if hit else None
    return f


FRONT = {0: ["AU", "AL", "BU", "BL", "CU", "CL"],
         1: ["AU", "ALd", "BUh", "BL", "CU", "CL"],
         2: ["AU", "ALp", "BUh", "BLt", "CU", "CLr"]}
BACK = {0: ["AU", "AL", "BU", "BL", "CU", "CL"],
        1: ["AU", "AL", "BUh", "BL", "CU", "CL"],
        2: ["AU", "AL", "BUh", "BL", "CU", "CLr"]}


def build_wall(stage, mat):
    B = Builder()
    bent = bend_post(-1.42, -0.42) if stage == 2 else None
    for name in FRONT[stage]:
        d = None
        if stage == 1 and name in ("CU", "CL"):
            d = sprung_seam
        if stage == 2 and name[0] == "A":
            d = chain(peel_field, bent) if name == "ALp" else bent
        B.add(name, deform=d)
    for name in BACK[stage]:
        B.add(name, Rz(180))
    if stage >= 1:
        B.add("Liner")
    for (sx, sy) in ((1, -1), (-1, -1), (-1, 1), (1, 1)):
        post = "Post1" if sx * sy < 0 and sx > 0 or (sx < 0 and sy > 0) else "Post2"
        d = bent if (stage == 2 and sx < 0 and sy < 0) else None
        B.add(post, corner_M(sx * 1.5, sy * 0.5, sx, sy), deform=d)
        for top in (False, True):
            B.add("Cast", corner_M(sx * 1.5, sy * 0.5, sx, sy, top=top))
    B.add("RailB", deform=rail_dent if stage == 2 else None)
    B.add("RailT")
    B.add("RailB", Rz(180))
    B.add("RailT", Rz(180))
    for sx in (1, -1):
        M = Matrix.Identity(4) if sx > 0 else Rz(180)
        d = bent if (stage == 2 and sx < 0) else None
        end_rails(B, sx)
        B.add("Cap", M, deform=d)
        cap_welds(B, M, deform=d)
    B.add("Roof")
    B.add("Patch1", deform=bent)
    B.add("Patch2", Rz(180) @ Tm(0.62, 0.0, 1.05) @ Ry(6))
    return B.finish("Wall_DMG%d" % stage, mat)


def build_corner(stage, mat):
    """Outer faces -X and -Y; walls meet it on +X and +Y. Returns made from clipped wall half-panels."""
    B = Builder()
    bent = bend_post(-0.42, -0.42) if stage == 2 else None
    names_y = {0: ("AU", "AL"), 1: ("AU", "ALd"), 2: ("AU", "ALd")}[stage]
    names_x = {0: ("RU", "CL"), 1: ("RU", "CL"), 2: ("RU", "CLr")}[stage]
    clip_y = [((-0.36, 0, 0), (-1, 0, 0)), ((0.5, 0, 0), (1, 0, 0))]
    for n in names_y:
        B.add(n, Tm(0.95, 0, 0), clip=clip_y, deform=bent)
    clip_x = [((0, -0.36, 0), (0, -1, 0)), ((0, 0.5, 0), (0, 1, 0))]
    small_dents = None
    if stage >= 1:
        def small_dents(p):
            if p.x > -0.4:
                return None
            d = dent_y(p.y, p.z, [(0.1, 0.2, 0.16, 0.025), (-0.15, 0.75, 0.1, 0.015)])
            return (d, 0.0, 0.0) if d else None
    for n in names_x:
        B.add(n, Tm(0, 0.95, 0) @ Rz(-90), clip=clip_x, deform=chain(*(f for f in (small_dents, bent) if f)))
    if stage >= 1:
        B.add("Liner", Tm(0.863, 0, 0), clip=[((0.5, 0, 0), (1, 0, 0))])
    B.add("Post2", corner_M(-0.5, -0.5, -1, -1), deform=bent)
    for top in (False, True):
        B.add("Cast", corner_M(-0.5, -0.5, -1, -1, top=top))
    clip_r = [((-0.5 + CX, 0, 0), (-1, 0, 0)), ((0.5, 0, 0), (1, 0, 0))]
    B.add("RailB", Tm(1.0, 0, 0), clip=clip_r)
    B.add("RailT", Tm(1.0, 0, 0), clip=clip_r)
    clip_r2 = [((0, -0.5 + CX, 0), (0, -1, 0)), ((0, 0.5, 0), (0, 1, 0))]
    B.add("RailB", Tm(0, 1.0, 0) @ Rz(-90), clip=clip_r2)
    B.add("RailT", Tm(0, 1.0, 0) @ Rz(-90), clip=clip_r2)
    B.add("Roof", Tm(1.0, 0.045, 0) @ Sc(1, 1.11, 1), clip=[((0.5, 0, 0), (1, 0, 0)), ((-0.41, 0, 0), (-1, 0, 0)),
                                          ((0, 0.5, 0), (0, 1, 0))])
    # caps on the open sides (normally hidden by the walls that meet it)
    B.add("Cap", Tm(-0.994, 0.0, 0.0))
    B.add("Cap", Rz(90) @ Tm(-0.994, 0.0, 0.0))
    return B.finish("Corner_DMG%d" % stage, mat)


def build_gate(mat):
    B = Builder()
    # jambs: front and back posts with castings, end caps outside and in
    for sx in (1, -1):
        for sy in (-1, 1):
            B.add("Post1", corner_M(sx * 1.5, sy * 0.5, sx, sy))
            for top in (False, True):
                B.add("Cast", corner_M(sx * 1.5, sy * 0.5, sx, sy, top=top))
        M = Matrix.Identity(4) if sx > 0 else Rz(180)
        B.add("Cap", M)
        cap_welds(B, M)
        end_rails(B, sx)
        Mi = Tm(sx * (XPI - 0.003 + XPO - 0.006), 0, 0) @ (Rz(180) if sx > 0 else Matrix.Identity(4))
        B.add("Cap", Mi, clip=[((0, 0, HDR_BOT + 0.01), (0, 0, 1))])
    # header front and back, roof, soffit
    B.add("Header")
    B.add("Header", Rz(180))
    B.add("Roof")
    B.add("Roof", Tm(0, 0, HDR_BOT + RT_TOP - 0.02) @ Sc(1, 1, -1) @ Tm(0, 0, 0),
          clip=[((XPI, 0, 0), (1, 0, 0)), ((-XPI, 0, 0), (-1, 0, 0))])
    # threshold
    B.add("Sill")
    B.add("Tread")
    B.add("RailB", Rz(180) @ Tm(0, 0, -0.04), clip=[((0, 0, Z0), (0, 0, -1))])
    # hinge lugs and cam keepers
    for sx in (-1, 1):
        S = Sc(-1, 1, 1) if sx > 0 else Matrix.Identity(4)
        for hz in HINGE_Z:
            B.add("Lug", Tm(0, 0, hz) @ S)
        for bx in BAR_X:
            dx = bx - BAR_X[0]
            B.add("Keeper", S @ Tm(dx, 0, 0))
            B.add("Keeper", S @ Tm(dx, 0, 0) @ Tm(0, 0, HDR_BOT + Z0) @ Sc(1, 1, -1) @ Tm(0, 0, 0))
    # leaves
    for sx, label in ((-1, "LeftLeaf"), (1, "RightLeaf")):
        S = Sc(-1, 1, 1) if sx > 0 else Matrix.Identity(4)
        B.add("DUl" if sx < 0 else "DUr", label=label)
        B.add("DL", S, label=label)
        B.add("DB", S, label=label)
        B.add("Stile", S, label=label)
        B.add("Stile", S @ Tm(LX_OUT - PX1, 0, 0), label=label)
        B.add("LRail", S, label=label)
        B.add("LRail", S @ Tm(0, 0, LZ1 - LZ0 - LFW), label=label)
        for k, bx in enumerate(BAR_X):
            dx = bx - BAR_X[0]
            B.add("Bar", S @ Tm(dx, 0, 0), label=label)
            for gz in (-0.12, 0.33, 1.15, 1.75):
                B.add("Guide", S @ Tm(dx, 0, gz), label=label)
            # the outer bar's handle points to the meeting edge, the inner one's back toward the hinge, higher up
            H = Tm(dx, 0, 0) if k == 0 else Tm(bx, 0, 0.25) @ Sc(-1, 1, 1) @ Tm(-BAR_X[0], 0, 0)
            B.add("Handle", S @ H, label=label)
            B.add("Retainer", S @ H, label=label)
        for hz in HINGE_Z:
            B.add("Hinge", S @ Tm(0, 0, hz), label=label)
        B.add("Seal", S @ Tm(0, 0, LZ0) @ Sc(1, 1, LZ1 - LZ0), label=label)
        B.add("Seal", S @ Tm(LX_OUT - LX_IN + 0.007, 0.009 if sx > 0 else 0.0, LZ0) @ Sc(1, 1, LZ1 - LZ0), label=label)
        if sx < 0:
            B.add("CSC", label=label)
    return B.finish("Frame", mat)


# ---------------------------------------------------------------- reports, export

def stats(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(obj.matrix_world)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    return co.min(axis=0), co.max(axis=0), sum(len(p.vertices) - 2 for p in me.polygons)


def export_dmg(fname, meshes, fx):
    saved = []
    objs = []
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


# ---------------------------------------------------------------- previews

ALL = []


def preview_material(name, paths, tint):
    """The baked maps as the game shows them: albedo x (1 - mask + mask x tint), with RMOM's alpha as the mask."""
    mat, g = tk.new_material(name)
    p = g.node("ShaderNodeBsdfPrincipled")
    out = g.node("ShaderNodeOutputMaterial")
    uv = tk._sock(g.node("ShaderNodeTexCoord").outputs, "UV")

    def tex(path, non_color):
        n = g.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        if non_color:
            n.image.alpha_mode = "CHANNEL_PACKED"
        g.links.new(uv, n.inputs["Vector"])
        return n

    alb = tex(paths["albedo"], False)
    rm = tex(paths["rmom"], True)
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(rm.outputs["Color"], sep.inputs[0])
    col = tk._multiply_color(g, alb.outputs["Color"], g.mix(1.0, (1.0, 1.0, 1.0), sep.outputs[2]))
    if tint is not None:
        col = tk._multiply_color(g, col, g.mix(rm.outputs["Alpha"], (1.0, 1.0, 1.0), tint))
    g._in(p, "Base Color", col)
    g._in(p, "Roughness", sep.outputs[0])
    g._in(p, "Metallic", sep.outputs[1])
    nm = g.node("ShaderNodeNormalMap")
    g.links.new(tex(paths["normal"], True).outputs["Color"], nm.inputs["Color"])
    g._in(p, "Normal", nm.outputs["Normal"])
    g.links.new(p.outputs[0], out.inputs["Surface"])
    return cull_backfaces(mat)


def cull_backfaces(mat):
    """The game's shader culls back faces, also when it draws shadows, and Cycles doesn't. For the previews: the camera
    sees only front faces, and light (shadow and bounce rays) is stopped only by faces turned toward it."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    src = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    lp = nt.nodes.new("ShaderNodeLightPath")
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(geo.outputs["Backfacing"], add.inputs[0])
    nt.links.new(lp.outputs["Is Camera Ray"], add.inputs[1])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    nt.links.new(add.outputs[0], sub.inputs[0])
    sub.inputs[1].default_value = 1.0
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "ABSOLUTE"
    nt.links.new(sub.outputs[0], fac.inputs[0])
    # |backfacing + camera - 1|: camera rays skip back faces, other rays skip front faces
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac.outputs[0], mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


# sRGB tints as they might be set on the blocks, in linear
def srgb(c):
    return tuple(((v / 255.0 + 0.055) / 1.055) ** 2.4 for v in c)


TINTS = {"red": srgb((176, 58, 46)), "blue": srgb((46, 92, 140)), "dullred": srgb((150, 62, 50))}


def stage():
    tk.preview_stage()
    floor = bpy.data.objects["Floor"]
    floor.data.transform(Matrix.Scale(4.0, 4))
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (0.0, 0.0, 0.0)


def figure_at(x, y):
    for n in ("ScaleFigure", "ScaleHead"):
        bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)


def lineup(entries, cam, path, res=(2000, 900), samples=96, material=None):
    """entries: (object, (x, y), z rotation, [extra objects parented]). Renders linked copies, ALL hidden."""
    for o in ALL:
        o.hide_render = True
    temps = []
    for ent in entries:
        obj, (x, y), rz = ent[:3]
        t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
        t.matrix_world = Tm(x, y, 0.0) @ Rz(rz) @ obj.matrix_world
        temps.append(t)
        if material is not None:
            for s in t.material_slots:
                s.link = "OBJECT"
                s.material = material
    tk.render(cam, path, res=res, samples=samples)
    for t in temps:
        bpy.data.objects.remove(t)


# ================================================================ main

tk.reset_scene()
if os.environ.get("CT_CPU"):
    bpy.context.scene.cycles.device = "CPU"
IMGS = build_decals()
if MODE == "decals":
    log("decals written")
    sys.exit(0)
MATS = build_materials(IMGS)
build_kit()

if FAST:
    parts_unbaked()
    MATERIAL = None
    PATHS = None
else:
    kit, PATHS = bake_kit()
    extract_parts(kit)
    bpy.data.objects.remove(kit)
    MATERIAL = tk.baked_material(MAT_NAME, PATHS)
    assert MATERIAL.name == MAT_NAME, MATERIAL.name
    log("baked", PATHS)

WALL = [build_wall(s, MATERIAL) for s in range(3)]
CORNER = [build_corner(s, MATERIAL) for s in range(3)]
FRAME = build_gate(MATERIAL)
LEAVES = {}
pivots = {"LeftLeaf": Vector((-GXH, GYH, Z0)), "RightLeaf": Vector((GXH, GYH, Z0))}
for label in ("LeftLeaf", "RightLeaf"):
    LEAVES[label] = tk.split_part(FRAME, label, pivots[label])
if "trap_part" in FRAME.data.attributes:
    for o in [FRAME] + list(LEAVES.values()):
        if "trap_part" in o.data.attributes:
            o.data.attributes.remove(o.data.attributes["trap_part"])
ALL.extend(WALL + CORNER + [FRAME] + list(LEAVES.values()))

REPORT = []
if not FAST:
    export_dmg("ContainerWall.fbx", WALL, (0.0, -0.5, 1.0))
    export_dmg("ContainerCorner.fbx", CORNER, (0.0, -0.5, 1.0))
    tk.export_fbx([FRAME, LEAVES["LeftLeaf"], LEAVES["RightLeaf"]], os.path.join(ASSETS, "ContainerGate.fbx"))
for fname, objs in (("ContainerWall", WALL), ("ContainerCorner", CORNER),
                    ("ContainerGate", [FRAME, LEAVES["LeftLeaf"], LEAVES["RightLeaf"]])):
    for i, o in enumerate(objs):
        lo, hi, tris = stats(o)
        REPORT.append("%s %s: tris %d bounds %s .. %s" % (fname, o.name, tris, lo.round(3), hi.round(3)))
for label, o in LEAVES.items():
    REPORT.append("%s origin %s" % (label, tuple(round(c, 4) for c in o.matrix_world.translation)))
for line in REPORT:
    log(line)
if MODE == "export":
    sys.exit(0)

# ---------------------------------------------------------------- renders
stage()
GREY = None
if not FAST:
    TMAT = {k: preview_material("Prev_" + k, PATHS, v) for k, v in TINTS.items()}
    TMAT["grey"] = preview_material("Prev_grey", PATHS, None)
else:
    TMAT = {"grey": None}
    for m in MATS:
        cull_backfaces(m)
pre = "fast_" if FAST else ""

cam_w = tk.camera("WallCam", (3.2, -13.5, 4.2), (0.0, 0.0, 0.9), lens=40)
cam_wb = tk.camera("WallCamB", (-3.2, 13.5, 4.2), (0.0, 0.0, 0.9), lens=40)
ents = [(WALL[0], (-3.4, 0.0), 0), (WALL[1], (0.0, 0.0), 0), (WALL[2], (3.4, 0.0), 0)]
figure_at(5.6, 0.4)
for k in (["grey", "red", "blue"] if not FAST else ["grey"]):
    lineup(ents, cam_w, os.path.join(PREVIEWS, "%scontainer_wall_stages_%s.png" % (pre, k)), material=TMAT[k])
lineup(ents, cam_wb, os.path.join(PREVIEWS, "%scontainer_wall_stages_back.png" % pre), material=TMAT["grey"])
cam_c = tk.camera("CornerCam", (-5.0, -8.0, 3.6), (0.0, 0.0, 0.9), lens=40)
ents = [(CORNER[0], (-1.8, 0.8), 0), (CORNER[1], (0.0, 0.0), 0), (CORNER[2], (1.8, -0.8), 0)]
figure_at(3.0, -1.6)
for k in (["grey", "red", "blue"] if not FAST else ["grey"]):
    lineup(ents, cam_c, os.path.join(PREVIEWS, "%scontainer_corner_stages_%s.png" % (pre, k)), res=(1600, 1000),
           material=TMAT[k])
# gate closed and open
figure_at(2.4, -1.2)
gate = [(FRAME, (0, 0), 0), (LEAVES["LeftLeaf"], (0, 0), 0), (LEAVES["RightLeaf"], (0, 0), 0)]
cam_g = tk.camera("GateCam", (2.6, -7.2, 2.6), (0.0, 0.0, 0.9), lens=40)
lineup(gate, cam_g, os.path.join(PREVIEWS, "%scontainer_gate_closed.png" % pre), res=(1400, 1100),
       material=TMAT.get("red"))
LEAVES["LeftLeaf"].rotation_euler.z = math.radians(-OPEN_DEG)
LEAVES["RightLeaf"].rotation_euler.z = math.radians(OPEN_DEG)
bpy.context.view_layer.update()
cam_go = tk.camera("GateCamO", (4.2, -7.0, 3.0), (0.0, -0.5, 0.9), lens=36)
lineup(gate, cam_go, os.path.join(PREVIEWS, "%scontainer_gate_open.png" % pre), res=(1400, 1100),
       material=TMAT.get("red"))
cam_gb = tk.camera("GateCamB", (-3.0, 6.5, 2.8), (0.0, 0.0, 0.9), lens=36)
lineup(gate, cam_gb, os.path.join(PREVIEWS, "%scontainer_gate_open_back.png" % pre), res=(1400, 1100),
       material=TMAT.get("grey"))
LEAVES["LeftLeaf"].rotation_euler.z = 0.0
LEAVES["RightLeaf"].rotation_euler.z = 0.0
bpy.context.view_layer.update()
# two walls and a corner: corner at the origin cell, one wall along +X, one along +Y facing -X
row = [(CORNER[0], (0, 0), 0), (WALL[0], (2.0, 0.0), 0), (WALL[0], (0.0, 2.0), -90)]
figure_at(-1.6, -1.4)
lineup(row, tk.camera("RowCam", (-4.8, -5.6, 3.8), (0.6, 0.6, 1.0), lens=30),
       os.path.join(PREVIEWS, "%scontainer_row.png" % pre), res=(1600, 1100), material=TMAT.get("blue"))
lineup(row, tk.camera("RowTop", (-2.6, -3.0, 6.5), (0.7, 0.7, 2.0), lens=30),
       os.path.join(PREVIEWS, "%scontainer_row_top.png" % pre), res=(1600, 1100), material=TMAT.get("grey"))
figure_at(3.0, 3.0)
lineup([(WALL[0], (0, 0), 0)], tk.camera("Close0", (0.9, -3.2, 1.5), (-0.1, 0.0, 1.2), lens=40),
       os.path.join(PREVIEWS, "%scontainer_wall_close.png" % pre), res=(1400, 1000), material=TMAT.get("grey"))
lineup([(WALL[2], (0, 0), 0)], tk.camera("Close2", (0.6, -3.3, 1.2), (-0.45, 0.0, 0.5), lens=38),
       os.path.join(PREVIEWS, "%scontainer_wall_dmg2_close.png" % pre), res=(1400, 1000), material=TMAT.get("red"))

if not FAST:
    # ---------------------------------------------------------------- icon
    for o in ALL:
        o.hide_render = True
    ic = tk.link(bpy.data.objects.new("IconWall", WALL[0].data))
    for s in ic.material_slots:
        s.link = "OBJECT"
        s.material = TMAT["dullred"]
    hide = {o.name for o in bpy.context.scene.objects if o.type == "MESH" and o is not ic}
    tk.icon(tk.camera("Icon", (4.6, -7.4, 4.4), (0.0, 0.0, 0.95), lens=80), ICON, hide=hide, target=(0.0, 0.0, 1.0))
    log("icon", ICON)

    # ---------------------------------------------------------------- the files as the importer sees them
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for fname in ("ContainerWall.fbx", "ContainerCorner.fbx", "ContainerGate.fbx"):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.import_scene.fbx(filepath=os.path.join(ASSETS, fname))
        parts = []
        for o in sorted(bpy.data.objects, key=lambda o: o.name):
            if o.type == "MESH":
                co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
                tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
                parts.append("%s mesh tris %d mat %s x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f origin %s parent %s" % (
                    o.name, tris, [m.name for m in o.data.materials], co[:, 0].min(), co[:, 0].max(), co[:, 1].min(),
                    co[:, 1].max(), co[:, 2].min(), co[:, 2].max(),
                    tuple(round(c, 3) for c in o.matrix_world.translation), o.parent.name if o.parent else None))
            else:
                parts.append("%s %s at %s parent %s" % (o.name, o.type, tuple(round(c, 3) for c in
                                                                              o.matrix_world.translation),
                                                        o.parent.name if o.parent else None))
        log("reimport", fname, "|", " || ".join(parts))
log("done")
