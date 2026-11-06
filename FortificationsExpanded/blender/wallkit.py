"""Shared helpers for the razor-wire, pallet-wall and hedge-row model scripts (Fortifications Expanded).

These three families don't bake a kit of 3D parts the way chainlink.py does. Their atlas is painted directly with numpy
(photo crops from blender/textures graded to the family's look, plus procedural wear), every part's UVs are laid onto
the painted swatches, and the pieces are meshes built from numpy arrays. Contents:

- numpy noise, photo loading and grading, `Atlas` (albedo, normal, roughness, metal, occlusion layers, swatches pasted
  with a gutter, normals made from a height field) saved the way FortBuilder expects (<Name>_Albedo/_Normal/_RMOM.png);
- `Geo`: a mesh built from vertices, faces and per-corner UVs, with tubes along polylines, boxes, prisms, quads;
- FBX export of a piece as DMG0..DMG2 meshes plus an FX empty (same layout as palisade.py), the preview stage, the
  lineup renderer, a see-through ray test and the re-import check.

Units are meters, Blender is Z-up, models are built with their bottom at z = -0.5 (the block's bottom), the wall line
is y = 0 and the front is -Y.
"""
import math
import os
import random
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trapkit as tk  # noqa: E402

Z0 = -0.5
T0 = time.time()
TAG = "wallkit"


def log(*a):
    print("[%s %5.0fs]" % (TAG, time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- numpy helpers

def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def m_t(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def m_r(axis, deg):
    return np.array(Matrix.Rotation(math.radians(deg), 4, axis))


def xf(V, M):
    return np.asarray(V, float) @ M[:3, :3].T + M[:3, 3]


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def lin(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _lattice(G, h, w):
    nz, nx = G.shape
    gy, gx = (np.arange(h) + 0.5) / h * nz, (np.arange(w) + 0.5) / w * nx
    iy, ix = np.floor(gy).astype(int), np.floor(gx).astype(int)
    fy, fx = gy - iy, gx - ix
    sy, sx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    i0, i1, j0, j1 = ix % nx, (ix + 1) % nx, iy % nz, (iy + 1) % nz
    top = G[j0][:, i0] + (G[j0][:, i1] - G[j0][:, i0]) * sx[None, :]
    bot = G[j1][:, i0] + (G[j1][:, i1] - G[j1][:, i0]) * sx[None, :]
    return top + (bot - top) * sy[:, None]


def fbm(h, w, ny, nx, rng, octaves=4, persistence=0.5):
    """Periodic fractal value noise, h x w, 0-1 (rows = v, up). ny, nx = lattice cells of the lowest octave."""
    out, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        out += amp * _lattice(rng.random((ny * 2 ** o, nx * 2 ** o)), h, w)
        tot += amp
        amp *= persistence
    return out / tot


def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


# ---------------------------------------------------------------- photos and swatches

TEXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
_PHOTOS = {}


def photo(set_name, kind="diff"):
    """A Poly Haven map as a float array (h, w, 3) (or (h, w) for single-channel kinds), rows bottom to top, values
    as stored in the file (sRGB-encoded for diff)."""
    key = (set_name, kind)
    if key not in _PHOTOS:
        path = os.path.join(TEXTURES, set_name, "{0}_{1}_2k.jpg".format(set_name, kind))
        if not os.path.exists(path):
            raise FileNotFoundError(path + " is missing; run src/fetch-textures.ps1")
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "sRGB" if kind == "diff" else "Non-Color"
        a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(img.size[1], img.size[0], 4)[..., :3].copy()
        if kind in ("disp",):
            a = a[..., 0]
        _PHOTOS[key] = a
    return _PHOTOS[key]


def crop(a, x, y, w, h):
    """A w x h crop of a photo at (x, y) (pixels from the bottom left), wrapping round the edges."""
    ys = (np.arange(h) + y) % a.shape[0]
    xs = (np.arange(w) + x) % a.shape[1]
    return a[ys][:, xs]


def resize(a, w, h):
    """Nearest/bilinear-ish resize by sampling (a: h0 x w0 [x c])."""
    h0, w0 = a.shape[:2]
    fy, fx = (np.arange(h) + 0.5) / h * h0 - 0.5, (np.arange(w) + 0.5) / w * w0 - 0.5
    y0, x0 = np.clip(np.floor(fy).astype(int), 0, h0 - 1), np.clip(np.floor(fx).astype(int), 0, w0 - 1)
    y1, x1 = np.clip(y0 + 1, 0, h0 - 1), np.clip(x0 + 1, 0, w0 - 1)
    wy, wx = fy - np.floor(fy), fx - np.floor(fx)
    if a.ndim == 3:
        wy, wx = wy[:, None, None], wx[None, :, None]
    else:
        wy, wx = wy[:, None], wx[None, :]
    top = a[y0][:, x0] * (1 - wx) + a[y0][:, x1] * wx
    bot = a[y1][:, x0] * (1 - wx) + a[y1][:, x1] * wx
    return top * (1 - wy) + bot * wy


def blur(a, r):
    """A box-ish blur (three passes of a running mean along each axis), cheap and good enough for masks."""
    if r < 1:
        return a
    out = a.astype(np.float64)
    k = 2 * r + 1
    for axis in (0, 1):
        for _ in range(3):
            pad = [(0, 0)] * out.ndim
            pad[axis] = (r, r)
            c = np.cumsum(np.pad(out, pad, mode="edge"), axis=axis)
            zero = np.zeros_like(np.take(c, [0], axis=axis))
            c = np.concatenate([zero, c], axis=axis)
            hi = np.take(c, np.arange(k, c.shape[axis]), axis=axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - k), axis=axis)
            out = (hi - lo) / k
    return out.astype(np.float32)


def normal_from_height(h, strength=1.0):
    """Tangent-space (OpenGL, y up) normals (h, w, 3 as 0-1) from a height field in the same units as the pixels'
    spacing (strength scales the slope)."""
    gy, gx = np.gradient(h.astype(np.float64))
    n = np.stack([-gx * strength, -gy * strength, np.ones_like(h, dtype=np.float64)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return 0.5 + 0.5 * n


def grade(c, sat=1.0, value=1.0, tint=None, contrast=1.0):
    """Saturation, value (a multiplier) and contrast about mid-grey on an encoded RGB array."""
    g = luma(c)[..., None]
    out = g + (c - g) * sat
    out = (out - 0.18) * contrast + 0.18
    out = out * value
    if tint is not None:
        out = out * np.asarray(tint)[None, None, :]
    return np.clip(out, 0.0, 1.0)


class Atlas:
    """The painted maps of one family. Pixel coordinates (x, y) count from the bottom left (y up, like v)."""

    def __init__(self, N=2048):
        self.N = N
        self.alb = np.ones((N, N, 4), np.float32)
        self.alb[..., :3] = 0.18
        self.alb[..., 3] = 1.0
        self.nrm = np.ones((N, N, 4), np.float32)
        self.nrm[..., 0], self.nrm[..., 1], self.nrm[..., 2] = 0.5, 0.5, 1.0
        self.rough = np.full((N, N), 0.8, np.float32)
        self.metal = np.zeros((N, N), np.float32)
        self.ao = np.ones((N, N), np.float32)
        self.used = []

    def uv(self, x, y):
        return (x / self.N, y / self.N)

    def paste(self, x, y, color, height=None, rough=0.8, metal=0.0, ao=1.0, nstrength=1.0, alpha=None, gutter=4):
        """Puts a swatch at (x, y): color (h, w, 3) encoded; height, rough, metal, ao, alpha arrays (h, w) or scalars.
        The border is repeated `gutter` pixels outward so mip-mapping and filtering don't pull in neighbours."""
        h, w = color.shape[:2]
        N = self.N
        assert 0 <= x and 0 <= y and x + w <= N and y + h <= N, (x, y, w, h)

        def full(v):
            return np.broadcast_to(np.asarray(v, np.float32), (h, w)).astype(np.float32)
        layers = {
            "alb": np.concatenate([color, full(1.0 if alpha is None else alpha)[..., None]], axis=2).astype(np.float32),
            "rough": full(rough), "metal": full(metal), "ao": full(ao)}
        if height is None:
            nrm = np.ones((h, w, 3), np.float32) * np.array([0.5, 0.5, 1.0], np.float32)
        else:
            nrm = normal_from_height(np.broadcast_to(height, (h, w)), nstrength).astype(np.float32)
        layers["nrm"] = np.concatenate([nrm, np.ones((h, w, 1), np.float32)], axis=2)
        for name, arr in layers.items():
            if gutter:
                pad = [(gutter, gutter), (gutter, gutter)] + ([(0, 0)] if arr.ndim == 3 else [])
                arr = np.pad(arr, pad, mode="edge")
            x0, y0 = x - gutter, y - gutter
            ya, xa = max(0, y0), max(0, x0)
            yb, xb = min(N, y0 + arr.shape[0]), min(N, x0 + arr.shape[1])
            getattr(self, name)[ya:yb, xa:xb] = arr[ya - y0:yb - y0, xa - x0:xb - x0]
        self.used.append((x, y, w, h))

    def save(self, out_dir, name):
        os.makedirs(out_dir, exist_ok=True)
        paths = {k: os.path.join(out_dir, "%s_%s.png" % (name, s)) for k, s in
                 (("albedo", "Albedo"), ("normal", "Normal"), ("rmom", "RMOM"))}
        tk.save_array(name + "_AlbedoMap", self.alb, paths["albedo"], False)
        tk.save_array(name + "_NormalMap", self.nrm, paths["normal"], True)
        tk.save_array(name + "_RMOMMap", tk.rmom(self.rough, self.metal, self.ao), paths["rmom"], True)
        return paths


# ---------------------------------------------------------------- materials for previews

def mesh_material(name, paths):
    """Preview material for a cut-out surface (leaf cards): the baked maps with the alpha cut at 0.3, as the game does
    for materials whose name ends in Mesh."""
    mat, g = tk.new_material(name)
    p = g.node("ShaderNodeBsdfPrincipled")
    out = g.node("ShaderNodeOutputMaterial")
    uv = tk._sock(g.node("ShaderNodeTexCoord").outputs, "UV")

    def tex(path, non_color):
        n = g.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        n.image.alpha_mode = "STRAIGHT"
        n.interpolation = "Linear"
        g.links.new(uv, n.inputs["Vector"])
        return n

    alb = tex(paths["albedo"], False)
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tex(paths["rmom"], True).outputs["Color"], sep.inputs[0])
    g._in(p, "Base Color", tk._multiply_color(g, alb.outputs["Color"], g.mix(1.0, (1.0, 1.0, 1.0), sep.outputs[2])))
    g._in(p, "Roughness", sep.outputs[0])
    g._in(p, "Metallic", sep.outputs[1])
    nm = g.node("ShaderNodeNormalMap")
    g.links.new(tex(paths["normal"], True).outputs["Color"], nm.inputs["Color"])
    g._in(p, "Normal", nm.outputs["Normal"])
    g._in(p, "Alpha", g.math("GREATER_THAN", alb.outputs["Alpha"], 0.3))
    g.links.new(p.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- geometry

def frames(P):
    """Tangents and parallel-transported normals/binormals along a polyline (n x 3)."""
    P = np.asarray(P, float)
    n = len(P)
    T = np.zeros_like(P)
    for i in range(n):
        d = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T[i] = d / max(np.linalg.norm(d), 1e-12)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    N = np.zeros_like(P)
    N[0] = unit(ref - T[0] * ref.dot(T[0]))
    for i in range(1, n):
        q = Vector(T[i - 1]).rotation_difference(Vector(T[i]))
        v = np.array(q @ Vector(N[i - 1]))
        v = v - T[i] * v.dot(T[i])
        N[i] = v / max(np.linalg.norm(v), 1e-12)
    return T, N, np.cross(T, N)


def catmull(pts, per=6, closed=False):
    """A smooth curve through control points (Catmull-Rom), `per` samples per span."""
    P = np.asarray(pts, float)
    n = len(P)
    out = []
    spans = n if closed else n - 1
    for i in range(spans):
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[0] * 2 - P[1]
        p1, p2 = P[i], P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[-1] * 2 - P[-2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    if not closed:
        out.append(P[-1])
    return np.array(out)


class Geo:
    """Vertices, faces (triangles or quads) and a UV for every face corner, gathered from primitives."""

    def __init__(self):
        self.V, self.F, self.UV, self.tag = [], [], [], []

    def __len__(self):
        return len(self.F)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)

    def vert(self, p):
        self.V.append(tuple(float(c) for c in p))
        return len(self.V) - 1

    def face(self, idx, uvs, tag=""):
        self.F.append(tuple(idx))
        self.UV.append([tuple(u) for u in uvs])
        self.tag.append(tag)

    def quad(self, a, b, c, d, uva, uvb, uvc, uvd, tag=""):
        i = [self.vert(p) for p in (a, b, c, d)]
        self.face(i, (uva, uvb, uvc, uvd), tag)

    def tri(self, a, b, c, uva, uvb, uvc, tag=""):
        i = [self.vert(p) for p in (a, b, c)]
        self.face(i, (uva, uvb, uvc), tag)

    def tube(self, pts, radius, sides, uv, rfn=None, caps=(True, True), tag="", vrep=1.0, v_offset=0.0, phase=0.0,
             vlen=None, squash=None):
        """A tube along a polyline. uv = (u0, v0, u1, v1) swatch rectangle in 0-1: u across the ring (the full ring
        spans u0..u1), v along the length (v0..v1 over `vlen` metres if given, else over the whole path * vrep).
        rfn(t) varies the radius along the path (t 0-1); squash=(a, b) scales the ring on its normal/binormal."""
        P = np.asarray(pts, float)
        n = len(P)
        T, Nn, Bn = frames(P)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        total = cum[-1] if cum[-1] > 0 else 1.0
        u0, v0, u1, v1 = uv
        rings = []
        for i in range(n):
            t = i / (n - 1) if n > 1 else 0.0
            r = radius if rfn is None else rfn(t)
            ring = []
            for j in range(sides):
                a = 2 * math.pi * (j + phase) / sides
                ca, sa = math.cos(a), math.sin(a)
                if squash:
                    ca, sa = ca * squash[0], sa * squash[1]
                ring.append(self.vert(P[i] + r * (ca * Nn[i] + sa * Bn[i])))
            rings.append(ring)
        for i in range(n - 1):
            va = v0 + (v1 - v0) * ((cum[i] / vlen) if vlen else (cum[i] / total * vrep)) + v_offset
            vb = v0 + (v1 - v0) * ((cum[i + 1] / vlen) if vlen else (cum[i + 1] / total * vrep)) + v_offset
            for j in range(sides):
                j1 = (j + 1) % sides
                ua = u0 + (u1 - u0) * j / sides
                ub = u0 + (u1 - u0) * (j + 1) / sides
                self.face((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]),
                          ((ua, va), (ub, va), (ub, vb), (ua, vb)), tag)
        if caps[0] and sides >= 3:
            self.face(tuple(reversed(rings[0])), [((u0 + u1) / 2, v0)] * sides, tag)
        if caps[1] and sides >= 3:
            self.face(tuple(rings[-1]), [((u0 + u1) / 2, v1)] * sides, tag)
        return self

    def prism(self, profile, z0, z1, uvfn, tag="", caps=True):
        """A vertical extrusion of a CCW polygon (x, y) from z0 to z1. uvfn(edge_index, s, z, width) -> (u, v) for the
        side faces; s runs 0..1 along the edge's length."""
        n = len(profile)
        for k in range(n):
            a, b = profile[k], profile[(k + 1) % n]
            w = math.hypot(b[0] - a[0], b[1] - a[1])
            self.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1),
                      uvfn(k, 0.0, z0, w), uvfn(k, 1.0, z0, w), uvfn(k, 1.0, z1, w), uvfn(k, 0.0, z1, w), tag)
        if caps:
            for z, flip in ((z1, False), (z0, True)):
                idx = [self.vert((p[0], p[1], z)) for p in (reversed(profile) if flip else profile)]
                self.face(idx, [uvfn(0, 0.5, z, 0.0)] * n, tag)
        return self

    def box(self, center, size, uvs, tag="", rot=None, faces="all"):
        """A box (size = x, y, z extents) at center, rotated by a 3x3 numpy matrix about its centre. uvs: a dict of
        face name (px, nx, py, ny, pz, nz) -> (u0, v0, u1, v1) rectangles (or one rectangle for all faces); faces:
        'all' or a string of names to skip."""
        sx, sy, sz = (s / 2.0 for s in size)
        c = np.asarray(center, float)
        R = np.eye(3) if rot is None else np.asarray(rot, float)
        corners = {}
        for a in (-1, 1):
            for b in (-1, 1):
                for d in (-1, 1):
                    corners[(a, b, d)] = c + R @ np.array([a * sx, b * sy, d * sz])
        spec = {  # name: (corner order CCW seen from outside)
            "px": [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
            "nx": [(-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1)],
            "py": [(1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1)],
            "ny": [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)],
            "pz": [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
            "nz": [(-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1)]}
        for name, order in spec.items():
            if name in faces and faces != "all":
                continue
            rect = uvs[name] if isinstance(uvs, dict) else uvs
            if rect is None:
                continue
            u0, v0, u1, v1 = rect
            self.quad(*[corners[k] for k in order], (u0, v0), (u1, v0), (u1, v1), (u0, v1), tag)
        return self

    def merge(self, other, M=None):
        off = len(self.V)
        V = np.asarray(other.V, float)
        if M is not None and len(V):
            V = xf(V, M)
        self.V += [tuple(v) for v in V]
        self.F += [tuple(i + off for i in f) for f in other.F]
        self.UV += [list(u) for u in other.UV]
        self.tag += list(other.tag)
        return self

    def transform(self, M):
        if self.V:
            self.V = [tuple(v) for v in xf(np.asarray(self.V, float), M)]
        return self

    def apply(self, fn):
        """fn(V array) -> V array (a deformation)."""
        if self.V:
            self.V = [tuple(v) for v in fn(np.asarray(self.V, float))]
        return self

    def bounds(self):
        V = np.asarray(self.V, float)
        return V.min(axis=0), V.max(axis=0)

    def by_tag(self):
        out = {}
        for f, t in zip(self.F, self.tag):
            out[t] = out.get(t, 0) + len(f) - 2
        return out

    def to_object(self, name, material, sharp=40.0, floor=Z0, mat_index=None):
        """A Blender mesh object. Vertices below `floor` are lifted onto it. mat_index: optional list per face (material
        slots beyond the first must already be on the mesh via the `material` list)."""
        V = np.asarray(self.V, float).reshape(-1, 3).copy()
        if floor is not None and len(V):
            V[:, 2] = np.maximum(V[:, 2], floor)
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], [list(f) for f in self.F])
        uv = me.uv_layers.new(name="UVMap")
        flat = [c for face in self.UV for c in face]
        uv.data.foreach_set("uv", np.asarray(flat, np.float32).reshape(-1))
        mats = material if isinstance(material, (list, tuple)) else [material]
        for m in mats:
            me.materials.append(m)
        if mat_index is not None:
            me.polygons.foreach_set("material_index", np.asarray(mat_index, np.int32))
        me.update()
        me.shade_smooth()
        if sharp:
            me.set_sharp_from_angle(angle=math.radians(sharp))
        return tk.link(bpy.data.objects.new(name, me))


# ---------------------------------------------------------------- export, checks

def export_piece(assets, fname, meshes, fx=None, names=None):
    """Exports meshes renamed DMG0.. (and an FX empty at `fx`) to one FBX, then restores the names."""
    saved, objs = [], []
    for i, m in enumerate(meshes):
        saved.append((m, m.name, m.data.name))
        nm = "DMG%d" % i if names is None else names[i]
        m.name = nm
        m.data.name = nm
        objs.append(m)
    empty = None
    if fx is not None:
        empty = tk.link(bpy.data.objects.new("FX", None))
        empty.empty_display_size = 0.1
        empty.location = fx
        objs.append(empty)
    tk.export_fbx(objs, os.path.join(assets, fname))
    if empty is not None:
        bpy.data.objects.remove(empty)
    for m, n, dn in saved:
        m.name = n
        m.data.name = dn


def stats(objs):
    lo, hi, tris = np.full(3, 1e9), np.full(3, -1e9), 0
    for o in objs:
        co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
        lo, hi = np.minimum(lo, co.min(0)), np.maximum(hi, co.max(0))
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return lo, hi, tris


def see_through(placed, axis, s0, s1, z0, z1, ds=0.01, dz=0.02, cut=None):
    """Fraction of rays shot straight through the wall (along Y when axis = 'Y', along X for 'X') on a grid that get
    through. placed: (object, location, z rotation degrees) entries, merged. cut: optional alpha-cut callback."""
    V, F, off = [], [], 0
    for obj, loc, rz in placed:
        M = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ obj.matrix_world
        V += [(M @ v.co)[:] for v in obj.data.vertices]
        F += [tuple(i + off for i in p.vertices) for p in obj.data.polygons]
        off += len(obj.data.vertices)
    bvh = BVHTree.FromPolygons(V, F)
    hit = tot = 0
    for s in np.arange(s0 + ds / 2, s1, ds):
        for z in np.arange(z0, z1, dz):
            o = Vector((s, -2.0, z)) if axis == "Y" else Vector((-2.0, s, z))
            d = Vector((0, 1, 0)) if axis == "Y" else Vector((1, 0, 0))
            tot += 1
            if bvh.ray_cast(o, d, 4.0)[0] is not None:
                hit += 1
    return 1.0 - hit / max(tot, 1)


# ---------------------------------------------------------------- previews

class Preview:
    def __init__(self, previews_dir, all_objs):
        self.dir = previews_dir
        self.ALL = all_objs

    def stage(self, floor_scale=4.0, floor_shift=(0.0, 0.0)):
        tk.preview_stage()
        floor = bpy.data.objects["Floor"]
        floor.data.transform(Matrix.Translation((floor_shift[0], floor_shift[1], 0.0)) @ Matrix.Scale(floor_scale, 4))
        self.figure_at(5.0, 5.0)

    def figure_at(self, x, y):
        for n in ("ScaleFigure", "ScaleHead"):
            bpy.data.objects[n].location = (x - 1.1, y - 0.6, 0.0)

    def lineup(self, entries, cam, name, res=(1800, 1000), samples=None, show=()):
        """entries: (object, (x, y), z rotation degrees); renders copies, everything else in ALL hidden."""
        for o in self.ALL:
            o.hide_render = o not in show
        temps = []
        for obj, (x, y), rz in entries:
            t = tk.link(bpy.data.objects.new("tmp_" + obj.name, obj.data))
            t.location = (x, y, 0.0)
            t.rotation_euler = (0.0, 0.0, math.radians(rz))
            temps.append(t)
        if os.environ.get("WK_ENGINE") == "EEVEE":
            sc = bpy.context.scene
            sc.render.engine = "BLENDER_EEVEE"
            try:
                sc.eevee.taa_render_samples = 24
            except AttributeError:
                pass
        k = float(os.environ.get("WK_RES", "1.0"))
        tk.render(cam, os.path.join(self.dir, name), res=(int(res[0] * k), int(res[1] * k)),
                  samples=samples or int(os.environ.get("WK_SAMPLES", "64")))
        for t in temps:
            bpy.data.objects.remove(t)
        log("rendered", name)


def reimport_check(assets, prefix):
    """Re-imports every FBX of the family the way the importer sees it and logs parts, tris, bounds."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for fname in sorted(os.listdir(assets)):
        if not (fname.startswith(prefix) and fname.endswith(".fbx")):
            continue
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.import_scene.fbx(filepath=os.path.join(assets, fname))
        parts = []
        for o in sorted(bpy.data.objects, key=lambda o: o.name):
            if o.type == "MESH":
                co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
                tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
                parts.append("%s tris %d mat %s x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (
                    o.name, tris, [m.name for m in o.data.materials], co[:, 0].min(), co[:, 0].max(), co[:, 1].min(),
                    co[:, 1].max(), co[:, 2].min(), co[:, 2].max()))
            else:
                parts.append("%s %s at %s" % (o.name, o.type, tuple(round(c, 3) for c in o.matrix_world.translation)))
        log("reimport", fname, "|", " || ".join(parts))
