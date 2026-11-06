"""PineconeCluster (forest floor, ground cover): six dry pine cones, 7 to 11 cm, lying among fallen needles on a dark bed
of needle duff, a few of them open wide and one half sunk into the ground. Each cone is real geometry: a woody core
wrapped in about sixty overlapping woody scales laid out in the spiral of a real cone (golden angle), flaring wide at
the stem end and closing toward the pointed tip, each scale a plate with a raised pad at its end.

    blender -b --factory-startup --python pinecone_cluster.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector
from mathutils import noise as mn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_ground as kg  # noqa: E402

NAME, SCRIPT = "PineconeCluster", "pinecone_cluster"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(41)

patch = kg.Patch(0.42, seed=33, stretch=(1.0, 0.88))
patch.fade = (0.6, 1.25)
heap = kg.Heap(patch, reach=0.74)

floor = kg.duff("ConeDuff", (0.035, 0.021, 0.011), (0.085, 0.048, 0.02), (0.2, 0.11, 0.045), scale=95.0,
                strands=0.7, strand_cols=((0.22, 0.12, 0.045), (0.12, 0.062, 0.025)), chips=0.3)
needle = kg.needle_material("ConeNeedle")
scale_mat = kg.cone_scale_material("ConeScale")
core_mat = kg.cone_scale_material("ConeCore", dark=(0.05, 0.028, 0.014), light=(0.16, 0.09, 0.04), tip=(0.12, 0.07, 0.03))

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd, reach=0.74)

# Needles under everything
for k, (x, y) in enumerate(patch.sample(rnd, 120, min_gap=0.01)):
    heading = mn.noise(Vector((x * 2.6 + 3.0, y * 2.6, 0.7))) * math.tau * 1.3 + rnd.gauss(0.0, 0.9)
    kg.needle_bundle(b, needle, heap, (x, y), heading, rnd.uniform(0.11, 0.17), 3 if rnd.random() < 0.7 else 2, rnd,
                     lod=0 if k % 5 < 2 else 1, lod_scale=1.3, spread=rnd.uniform(0.05, 0.12), arch=rnd.uniform(0.001, 0.003))

X = Vector((1.0, 0.0, 0.0))


def cone_profile(u, rmax):
    return rmax * max(0.25, math.sin(math.pi * (0.08 + 0.92 * u) ** 0.85)) ** 0.8


def pinecone(at, length, nscale, openness, sink, yaw, tilt, lod_keep):
    rmax = length * 0.29
    local = []          # per scale: (points, attrs, normal)
    for k in range(nscale):
        u = (k + 0.5) / nscale
        phi = k * 2.39996 + rnd.uniform(-0.05, 0.05)
        rho = Vector((0.0, math.cos(phi), math.sin(phi)))
        tau = Vector((0.0, -math.sin(phi), math.cos(phi)))
        Rc = cone_profile(u, rmax)
        rc = 0.34 * Rc
        beta = math.radians((74.0 - 42.0 * u) * openness + rnd.uniform(-4, 4))
        ell = min(rmax * 0.95, 0.74 * Rc / max(0.3, math.sin(beta))) * rnd.uniform(0.92, 1.1)
        w = ell * 0.62 * rnd.uniform(0.9, 1.1)
        B = X * (u * length) + rho * rc
        d1 = X * math.cos(beta) + rho * math.sin(beta)
        d2 = X * math.cos(beta + 0.42) + rho * math.sin(beta + 0.42)
        n = (-X * math.sin(beta) + rho * math.cos(beta)).normalized()
        M = B + d1 * (ell * 0.55)
        T = M + d2 * (ell * 0.45) + n * (0.04 * ell)
        pts = [B - tau * (0.3 * w), B + tau * (0.3 * w), M - tau * (0.5 * w), M + tau * (0.5 * w), T]
        q = w / ell
        attrs = [(0.5, 0.5 - 0.3 * q, 0.2), (0.5, 0.5 + 0.3 * q, 0.2), (1.05, 0.5 - 0.5 * q, 1.0),
                 (1.05, 0.5 + 0.5 * q, 1.0), (1.5, 0.5, 1.0)]
        local.append((pts, attrs, n, rnd.random(), u))
    rot = (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "Y")
           @ Matrix.Rotation(math.radians(tilt[1]), 3, "X") @ Matrix.Rotation(rnd.uniform(0, math.tau), 3, "X"))
    # Rest it on the heap (lowest scale tip touching), sunk by `sink` of its width
    allp = [rot @ p for pts, _, _, _, _ in local for p in pts]
    z0 = max(heap.top(at[0] + p.x, at[1] + p.y) - p.z for p in allp) + 0.001 - sink * 2.0 * rmax
    origin = Vector((at[0], at[1], z0)) - rot @ (X * (length * 0.5))
    m = b.mesh(scale_mat)
    for k, (pts, attrs, n, rr, u) in enumerate(local):
        keep = (k % 3 != 0) or lod_keep
        b.lod, b.lod_scale = (0 if keep else 1), 1.0
        wp = [origin + rot @ p for p in pts]
        m.begin(wp[0].lerp(wp[4], 0.5))
        vs = [m.v(p, a[0] - 0.5, lx=a[0], ly=a[1], lz=a[2], r=rr, r2=0.5) for p, a in zip(wp, attrs)]
        wn = rot @ n
        for face_verts in ((vs[0], vs[1], vs[3], vs[2]), (vs[2], vs[3], vs[4])):
            f = m.f(face_verts, False)
            if f is not None:
                f.normal_update()
                if f.normal.dot(wn) < 0:
                    f.normal_flip()
        for p in wp:
            heap.stamp(p.x, p.y, p.z + 0.001)
    b.lod, b.lod_scale = 0, 1.0
    # The woody core under the scales
    ax = rot @ X
    prof = [(0.0, -0.002), (0.3 * cone_profile(0.05, rmax) * 0.9, 0.0), (0.3 * cone_profile(0.35, rmax) * 1.0, length * 0.35),
            (0.3 * cone_profile(0.75, rmax) * 1.0, length * 0.75), (0.0, length * 0.99)]
    kg.lathe(b, core_mat, prof, origin, ax, segments=6, t=(0.0, 0.2, 0.5, 0.8, 1.0), rnd=rnd, lod=1)


spots = patch.sample(rnd, 6, min_gap=0.2, reach=0.55)
configs = [(0.125, 62, 1.0, 0.0), (0.105, 56, 0.85, 0.0), (0.118, 58, 1.0, 0.0), (0.095, 50, 0.7, 0.45), (0.14, 66, 1.0, 0.0),
           (0.1, 52, 0.9, 0.0)]
for k, ((x, y), (L, n, op, sink)) in enumerate(zip(spots, configs)):
    pinecone((x, y), L, n, op, sink, rnd.uniform(0, math.tau), (rnd.uniform(-6, 6), rnd.uniform(-8, 8)), k % 2 == 0)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=1024,
         density={"ConeScale": 1.5, "ConeCore": 0.5, "ConeNeedle": 0.8, "ConeDuff": 0.45})
print("[%s] done" % SCRIPT)
