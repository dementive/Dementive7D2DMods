"""Nature Expanded's kit for solid natural features (boulders, rock formations, cairns, bones; see ../FEATURES.md), on
top of naturekit.py, kit_shrub.py, kit_forest.py and zkit.py.

A feature is a block model like the plants (Blender meters, Z up, the master cell's center at the origin, the ground at
z = -0.5 = nk.GROUND) but SOLID: it stands on a footprint of an odd number of cells, is built from closed meshes, and
comes with colliders. This kit supplies:

- `Rock`: a closed, displaced super-ellipsoid with flat split faces and cracks, sunk into the ground (a flat skirt
  SKIRT deep, out of sight under the terrain). `emit_rock` puts it into a ks.Builder in two materials (the body, and
  the skirt that only needs a sliver of the atlas) and `moss_shell` lays lumpy cushions over its top.
- `granite(...)`: the surface of a mossy granite boulder, as node signals (`granite_surface`) and a material.
- `voxel_boxes`: the colliders. Every closed body mesh is voxelized and the solid voxels merged into a few boxes that
  lie INSIDE the mesh (a corner test with a margin), so a player can never be stopped by empty air, can step up the
  voxel steps, and an arch's opening stays open automatically. Convex primitives only, as the game wants.
- `export`: ks.export (atlas, FBX with the near and far meshes) plus the sidecar <Name>_colliders.txt that
  NatureFeatureBuilder reads (see its header for the format).

Typical script: `featurekit.start()`, build with a ks.Builder, `export(...)`.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mn
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

G = nk.GROUND
SKIRT = 0.4  # how far below the ground a feature's flat underside sits (terrain is smooth, a cell's bottom is not flat)
UP = Vector((0.0, 0.0, 1.0))


def args():
    """(Features folder, preview folder) from the command line after `--`."""
    a = sys.argv[sys.argv.index("--") + 1:]
    os.makedirs(a[1], exist_ok=True)
    return a[0], a[1]


# ---------------------------------------------------------------- rocks

class Rock:
    """A rounded boulder: `radii` (a, b, c) of a super-ellipsoid (`power` 2 is an ellipsoid, 3 and up gets blocky),
    `height` visible above the ground (the rest is sunk), noise on the surface (`rough` as a fraction of the size),
    flat split faces (`planes`: (normal, distance from the center) in the rock's own frame, the part beyond is cut
    flat) and cracks (`cracks`: (normal, distance, half width, depth)). Turned `yaw` degrees and moved to `at`."""

    def __init__(self, radii, height=None, seed=0, power=2.5, rough=0.07, planes=(), cracks=(), yaw=0.0, at=(0.0, 0.0),
                 tilt=(0.0, 0.0), subdiv=4, sink=SKIRT):
        self.radii = Vector(radii)
        self.height = height if height is not None else self.radii.z * 1.7
        self.seed = seed
        self.power = power
        self.rough = rough
        self.planes = planes
        self.cracks = cracks
        self.yaw = yaw
        self.at = at
        self.tilt = tilt
        self.subdiv = subdiv
        self.sink = sink

    def _noise(self, p, size):
        q = p / size * 1.3 + Vector((self.seed * 7.31, self.seed * 3.17, self.seed * 1.91))
        return (mn.fractal(q, 0.5, 2.0, 4, noise_basis="PERLIN_ORIGINAL") * 0.75
                + 0.35 * mn.noise(q * 5.0 + Vector((3.0, 1.0, 2.0))) + 0.08 * mn.noise(q * 14.0))

    def build(self):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=self.subdiv, radius=1.0)
        a, b, c = self.radii
        size = (a * b * c) ** (1.0 / 3.0)
        n = self.power
        cz = G + self.height - c
        rot = Matrix.Rotation(math.radians(self.yaw), 3, "Z")
        tilt = Matrix.Rotation(math.radians(self.tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(self.tilt[1]), 3, "Y")
        for v in bm.verts:
            u = v.co.copy().normalized()
            s = (abs(u.x) ** n + abs(u.y) ** n + abs(u.z) ** n) ** (-1.0 / n)
            p = Vector((u.x * s * a, u.y * s * b, u.z * s * c))
            p += u * (self._noise(p, size) * self.rough * size)
            for nrm, d in self.planes:
                nv = Vector(nrm).normalized()
                over = p.dot(nv) - d
                if over > 0.0:
                    p -= nv * over
            for nrm, d, w, depth in self.cracks:
                nv = Vector(nrm).normalized()
                s2 = abs(p.dot(nv) - d)
                if s2 < w and p.length > 1e-6:
                    p -= p.normalized() * depth * (1.0 - (s2 / w) ** 2)
            p = tilt @ p
            p = rot @ p
            p = Vector((p.x + self.at[0], p.y + self.at[1], p.z + cz))
            p.z = max(p.z, G - self.sink)
            v.co = p
        # Flattening leaves slivers and coincident vertices: their zero-area triangles give the game's tangent
        # calculation nothing to work with (the flat face drew black), so weld and drop them
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.004)
        bmesh.ops.dissolve_degenerate(bm, dist=0.002, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 2e-6], context="FACES_ONLY")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        return bm


def emit_rock(b, bm, body_mat, skirt_mat, moss=None):
    """Adds a Rock's bmesh to Builder `b` (far LOD: decimated). Faces wholly near the ground go to `skirt_mat`.
    `moss` = (material, depth(p, n)) lays cushions over the top. Returns the body as (vertices, polygons) for the
    colliders."""
    b.lod = 2
    cache = {}
    for f in bm.faces:
        mat = skirt_mat if max(v.co.z for v in f.verts) < G + 0.03 else body_mat
        m = b.mesh(mat)
        m.begin(f.calc_center_median())
        vs = []
        for v in f.verts:
            key = (mat.name, v.index)
            if key not in cache:
                cache[key] = m.v(v.co.copy(), 0.5)
            vs.append(cache[key])
        m.f(vs, True)
    if moss is not None and not os.environ.get("FK_NOSHELL"):
        mat, depth = moss
        m = b.mesh(mat)
        shell = {}
        info = {}

        def d_of(v):
            if v.index not in info:
                info[v.index] = depth(v.co, v.normal)
            return info[v.index]

        for f in bm.faces:
            if max(v.co.z for v in f.verts) < G + 0.12:
                continue
            if max(d_of(v) for v in f.verts) < 0.004:
                continue
            m.begin(f.calc_center_median())
            vs = []
            for v in f.verts:
                if v.index not in shell:
                    d = d_of(v)
                    shell[v.index] = m.v(v.co + v.normal * (d + 0.0015 if d > 0.0 else -0.006), min(1.0, d / 0.02))
                vs.append(shell[v.index])
            m.f(vs, True)
    return [v.co.copy() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces]


def moss_depth(seed=0, reach=1.0, thickness=0.03, north=0.3):
    """A moss-cushion depth function for emit_rock: thick on up-facing surfaces and the north (+y) side, in clumps,
    none low on the rock where it meets the ground (that's the skirt's)."""

    def fn(p, n):
        top = n.z * 0.85 + max(0.0, n.y) * north
        q = Vector((p.x * 1.9 + seed * 5.0, p.y * 1.9, p.z * 1.9))
        mask = max(0.0, min(1.0, (top - 0.1) / 0.55)) * (0.5 + 0.8 * mn.noise(q) + 0.3 * mn.noise(q * 3.0)) * reach
        d = max(0.0, min(1.0, (mask - 0.42) / 0.3))
        return d * (0.01 + thickness * max(0.0, 0.5 + 0.7 * mn.noise(q * 5.0)))

    return fn


# ---------------------------------------------------------------- granite

def granite_surface(g, tint=(1.0, 1.0, 1.0), moss=1.0, lichen=1.0, stain=1.0, scale=1.0):
    """Mossy granite as node signals (color, height 0..1, roughness): coarse crystals (feldspar, quartz, dark mica)
    a few mm across, tone drifting over the rock, long rain streaks and a little rust, hairline cracks, crusty lichen
    in pale green and orange, and moss on the tops and the north side with the clumps of kf.moss_layer. Everything
    has structure down to the texel."""
    co = g.coords()
    # Crystals
    d1, r1 = kf._cells(g, 170.0 * scale, kf._warped(g, 40.0, 0.002))
    d2, r2 = kf._cells(g, 38.0 * scale, kf._warped(g, 18.0, 0.006))
    fine = g.noise(450.0 * scale, detail=2.0)
    tone = g.noise(2.2 * scale, detail=4.0)
    patch = g.noise(9.0 * scale, detail=4.0, distortion=0.4)
    base = g.mix(g.ramp(tone, 0.3, 0.7), (0.115, 0.11, 0.104), (0.185, 0.177, 0.165))
    base = g.mix(g.math("MULTIPLY", g.ramp(patch, 0.55, 0.8), 0.55), base, (0.07, 0.068, 0.066))
    felds = g.math("MULTIPLY", g.ramp(r2, 0.55, 0.7), g.ramp(g.noise(5.0 * scale), 0.35, 0.6))
    base = g.mix(g.math("MULTIPLY", felds, 0.6), base, (0.27, 0.2, 0.17))
    quartz = g.ramp(r1, 0.12, 0.2)
    quartz = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.ramp(r1, 0.2, 0.3)), quartz)
    base = g.mix(g.math("MULTIPLY", quartz, 0.6), base, (0.25, 0.25, 0.26))
    mica = g.math("MULTIPLY", g.ramp(r1, 0.11, 0.0), g.ramp(d1, 0.55, 0.15))
    base = g.mix(g.math("MULTIPLY", mica, 0.9), base, (0.028, 0.028, 0.03))
    base = g.mix(g.math("MULTIPLY", g.ramp(fine, 0.55, 0.9), 0.25), base, (0.1, 0.1, 0.1))
    base = g.mix(g.math("MULTIPLY", g.ramp(d1, 0.5, 0.9), 0.3), base, (0.12, 0.115, 0.11))
    # Rain streaks running down, rust blooms
    st = ks._stretched(g, (3.2 * scale, 3.2 * scale, 0.35 * scale))
    streak = g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=st), 0.48, 0.7),
                    g.ramp(ks._normal_z(g), 0.8, 0.2))
    streak = g.math("MULTIPLY", streak, 0.7 * stain)
    base = g.mix(streak, base, (0.035, 0.033, 0.03))
    rust = g.math("MULTIPLY", g.ramp(g.noise(4.0 * scale, detail=5.0, distortion=0.5), 0.6, 0.72), 0.55 * stain)
    base = g.mix(rust, base, (0.17, 0.085, 0.04))
    # Cracks: the edges of big warped cells, hairline, black in the depths
    ce = kf._voronoi(g, 0.55 * scale, kf._warped(g, 2.0, 0.15, kf._warped(g, 9.0, 0.04)), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(ce, 0.03, 0.0)
    crack = g.math("MULTIPLY", crack, g.ramp(g.noise(2.0 * scale, detail=3.0), 0.5, 0.64))
    col = g.mix(g.math("MULTIPLY", g.ramp(crack, 0.1, 0.9), 0.9), base, (0.012, 0.011, 0.01))
    height = g.math("ADD", g.math("MULTIPLY", g.math("ADD", r1, fine), 0.12), g.math("MULTIPLY", g.ramp(d2, 0.5, 0.1), 0.12))
    height = g.math("SUBTRACT", g.math("ADD", height, 0.45), g.math("MULTIPLY", crack, 0.55))
    rough = g.mixf(quartz, 0.78, 0.55)
    rough = g.mixf(crack, rough, 0.95)
    # Lichen: pale grey-green rosettes and orange crusts, granular, mostly on the sunny sides
    if lichen > 0.0:
        lc, lr = kf._cells(g, 5.0 * scale, kf._warped(g, 5.0, 0.07))
        gate = g.ramp(g.noise(1.6 * scale, detail=3.0), 0.55, 0.66)
        disc = g.math("MULTIPLY", g.ramp(lc, 0.5, 0.36), g.math("MULTIPLY", g.ramp(lr, 0.45, 0.6), gate))
        gran, _ = kf._cells(g, 380.0 * scale)
        disc = g.math("MULTIPLY", g.math("MULTIPLY", disc, g.ramp(gran, 0.8, 0.3)), lichen)
        col = g.mix(g.math("MULTIPLY", disc, 0.85), col, g.mix(g.ramp(lr, 0.5, 0.9), (0.2, 0.225, 0.15), (0.42, 0.34, 0.1)))
        height = g.math("ADD", height, g.math("MULTIPLY", disc, 0.18))
        rough = g.mixf(disc, rough, 0.9)
    # Moss on the tops and the north side, in clumps, giving way to the rock through a ragged edge
    if moss > 0.0:
        mcol, mh, mrough, _ = kf.moss_layer(g)
        nz = ks._normal_z(g)
        geo = g.node("ShaderNodeNewGeometry")
        ny = g.separate(tk._sock(geo.outputs, "Normal"))[1]
        up = g.math("ADD", g.math("MULTIPLY", nz, 0.9), g.math("MULTIPLY", g.math("MAXIMUM", ny, 0.0), 0.3))
        reach = g.math("ADD", g.math("MULTIPLY", up, 0.9), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(3.0 * scale, detail=5.0), 0.5), 0.9))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.35))
        reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(38.0, detail=3.0), 0.5), 0.12))
        z = g.separate(co)[2]
        low = g.ramp(z, G + 0.5, G + 0.05)
        cover = g.math("MULTIPLY", g.ramp(reach, 0.62 - 0.12 * moss, 0.7 - 0.12 * moss), 1.0)
        cover = g.math("MAXIMUM", cover, g.math("MULTIPLY", low, g.ramp(g.noise(6.0, detail=4.0), 0.4, 0.6)))
        mc = tk.grade(g, mcol, sat=0.95, value=0.95)
        col = g.mix(cover, col, mc)
        height = g.mixf(cover, height, g.math("ADD", 0.3, g.math("MULTIPLY", mh, 0.6)))
        rough = g.mixf(cover, rough, mrough)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.separate(co)[2], G + 0.1, G - 0.05), 0.65), col, (0.02, 0.017, 0.013))
    col = tk.grade(g, col, sat=0.95, value=0.95, tint=tint if tint != (1.0, 1.0, 1.0) else None)
    return col, height, rough


def granite(name, relief=0.012, **kw):
    mat, g = tk.new_material(name)
    col, height, rough = granite_surface(g, **kw)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


def granite_moss(name, relief=0.012, **kw):
    """The moss cushions of emit_rock's shell: the rock's own surface at the rim of each patch (attribute t runs 0 at
    the rim to 1 inside), kf.moss_layer's clumps within, so the edge is drawn by the texture."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    bcol, bh, brough = granite_surface(g, **kw)
    mcol, mh, mrough, _ = kf.moss_layer(g)
    reach = g.math("ADD", g.math("MULTIPLY", t, 1.3), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(14.0, detail=5.0), 0.5), 0.6))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", mh, 0.5), 0.5))
    cover = g.ramp(reach, 0.36, 0.5)
    col = g.mix(cover, bcol, tk.grade(g, mcol, sat=0.95, value=0.95))
    height = g.mixf(cover, bh, g.math("ADD", 0.25, g.math("MULTIPLY", mh, 0.75)))
    rough = g.mixf(cover, brough, mrough)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, relief))


# ---------------------------------------------------------------- colliders

def _parity(tree, p):
    """True when `p` is inside the closed mesh: the majority of three rays cross its surface an odd number of times
    (the nearest face's normal is not reliable far from the surface or near edges)."""
    votes = 0
    for d in (Vector((1.0, 0.0131, 0.0071)), Vector((0.0093, 1.0, 0.0117)), Vector((0.0071, 0.0113, 1.0))):
        d = d.normalized()
        o = p.copy()
        hits = 0
        for _ in range(40):
            loc, nor, idx, dist = tree.ray_cast(o, d)
            if loc is None:
                break
            hits += 1
            o = loc + d * 1e-4
        votes += hits % 2
    return votes >= 2


def voxel_boxes(bodies, voxel=0.12, margin=0.03, floor=G, limit=140):
    """Boxes (center, size) inside the closed meshes `bodies` ([(vertices, polygons)] in Blender coordinates): the
    space above `floor` is cut into voxels, a voxel counts when its eight corners are inside a body by at least
    `margin`, and the solid voxels are merged (greedy rectangles per layer, equal rectangles on consecutive layers
    joined). Returns [(cx, cy, cz, sx, sy, sz)]. The voxel grows until there are at most `limit` boxes."""
    verts, polys, base = [], [], 0
    for vs, ps in bodies:
        verts += [Vector(v) for v in vs]
        polys += [tuple(base + i for i in p) for p in ps]
        base += len(vs)
    tree = BVHTree.FromPolygons([tuple(v) for v in verts], polys)
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), floor))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    inside_cache = {}
    while True:
        i0 = int(math.floor(lo.x / voxel)) - 1
        j0 = int(math.floor(lo.y / voxel)) - 1
        nx = int(math.ceil(hi.x / voxel)) + 2 - i0
        ny = int(math.ceil(hi.y / voxel)) + 2 - j0
        nz = int(math.ceil((hi.z - floor) / voxel)) + 1

        def inside(i, j, k):
            key = (voxel, i, j, k)
            if key not in inside_cache:
                p = Vector(((i0 + i) * voxel, (j0 + j) * voxel, floor + k * voxel))
                loc, nor, idx, dist = tree.find_nearest(p)
                inside_cache[key] = loc is not None and dist >= margin and _parity(tree, p)
            return inside_cache[key]

        layers = []
        for k in range(nz):
            grid = [[False] * ny for _ in range(nx)]
            for i in range(nx):
                for j in range(ny):
                    grid[i][j] = all(inside(i + di, j + dj, k + dk) for di in (0, 1) for dj in (0, 1) for dk in (0, 1))
            layers.append(grid)
        rects = {}
        open_rects = {}
        for k in range(nz):
            grid = layers[k]
            seen = [[False] * ny for _ in range(nx)]
            now = set()
            for i in range(nx):
                for j in range(ny):
                    if not grid[i][j] or seen[i][j]:
                        continue
                    j1 = j
                    while j1 + 1 < ny and grid[i][j1 + 1] and not seen[i][j1 + 1]:
                        j1 += 1
                    i1 = i
                    while i1 + 1 < nx and all(grid[i1 + 1][jj] and not seen[i1 + 1][jj] for jj in range(j, j1 + 1)):
                        i1 += 1
                    for ii in range(i, i1 + 1):
                        for jj in range(j, j1 + 1):
                            seen[ii][jj] = True
                    now.add((i, i1, j, j1))
            for r in now:
                if r in open_rects:
                    open_rects[r][1] = k
                else:
                    open_rects[r] = [k, k]
            for r in list(open_rects):
                if r not in now:
                    rects[(r, open_rects[r][0])] = open_rects[r][1]
                    del open_rects[r]
        for r, (k0, k1) in open_rects.items():
            rects[(r, k0)] = k1
        if len(rects) <= limit or voxel > 0.5:
            break
        voxel *= 1.2
    boxes = []
    for ((a, a1, b, b1), k0), k1 in rects.items():
        x0, x1 = (i0 + a) * voxel, (i0 + a1 + 1) * voxel
        y0, y1 = (j0 + b) * voxel, (j0 + b1 + 1) * voxel
        z0, z1 = floor + k0 * voxel, floor + (k1 + 1) * voxel
        if k0 == 0:
            z0 -= 0.25  # down into the ground, so no gap shows on uneven terrain
        boxes.append(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, x1 - x0, y1 - y0, z1 - z0))
    print("[colliders] %d boxes (voxel %.2f m)" % (len(boxes), voxel))
    return boxes


def write_colliders(folder, name, boxes, texture=1024, probes=(), extra=(), rect=False):
    """<folder>/<name>/<name>_colliders.txt: boxes [(cx, cy, cz, sx, sy, sz)], extra raw lines (spheres, capsules,
    rotated boxes), probes [(x, y, z, dx, dy, dz)] (rays that must stay clear: an arch's opening)."""
    path = os.path.join(folder, name, name + "_colliders.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# colliders for %s, Blender coordinates (see unity/Assets/Editor/NatureFeatureBuilder.cs)\n" % name)
        f.write("texture %d\n" % texture)
        if rect:
            f.write("rect\n")  # the block footprint may be a rectangle (see NatureFeatureBuilder)
        for b in boxes:
            f.write("box %.3f %.3f %.3f %.3f %.3f %.3f\n" % b)
        for line in extra:
            f.write(line + "\n")
        for p in probes:
            f.write("probe %.3f %.3f %.3f %.3f %.3f %.3f\n" % p)


def export(name, pieces, bodies, out_dir, size=1024, density=None, voxel=0.12, probes=(), extra=(), coarse=0.3,
           margin=0.03, limit=140, rect=False, boxes=None):
    """ks.export (near and far meshes, atlas of `size`) plus the collider sidecar built from `bodies`."""
    boxes = list(boxes or []) + (voxel_boxes(bodies, voxel, margin, limit=limit) if bodies else [])
    model = ks.export(name, pieces, out_dir, size=size, coarse_ratio=coarse, density=density)
    write_colliders(out_dir, name, boxes, size, probes, extra, rect)
    return model
