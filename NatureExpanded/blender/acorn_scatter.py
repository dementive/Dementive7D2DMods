"""AcornScatter (forest floor, ground cover): about twenty acorns scattered over a bed of fallen oak leaves and duff, 3 cm
long: glossy chestnut nuts striped lengthwise with a pale scar at the base, some wearing their rough scaly caps, some bare,
a few caps lying alone, one or two gnawed open by squirrels (a ragged rim round a pale hollow) and a couple split in
halves showing the cream kernel. The acorns lie on the leaves under them. All real geometry.

    blender -b --factory-startup --python acorn_scatter.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_ground as kg  # noqa: E402
import zkit as tk  # noqa: E402

NAME, SCRIPT = "AcornScatter", "acorn_scatter"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

kg.start()
G = nk.GROUND
rnd = random.Random(53)

patch = kg.Patch(0.42, seed=45, stretch=(1.0, 0.9))
patch.fade = (0.6, 1.25)
heap = kg.Heap(patch, reach=0.74)

floor = kg.duff("AcornDuff", (0.05, 0.033, 0.017), (0.1, 0.062, 0.028), (0.16, 0.1, 0.045), scale=105.0, chips=0.3)
oak = kg.leaf_material("AcornOakLeaf", [((0.2, 0.108, 0.04), 3.0), ((0.27, 0.19, 0.08), 2.4), ((0.3, 0.12, 0.035), 1.6),
                                        ((0.1, 0.06, 0.028), 2.4)],
                       kind="pinnate", veins=9.0, slope=0.35, edge_brown=0.5, damp=1.0, vein_lift=1.2, spots=0.55)


def nut_material():
    """The shell of an acorn (a lathe: lx along the axis, ly and lz round it, t 0 at the base): glossy chestnut, fine
    dark stripes along its length, a pale rough scar at the base, a darker tip, a few greener or tan ones by r."""
    mat, g = tk.new_material("AcornNut")
    lx, ly, lz = nk._attr(g, "lx"), nk._attr(g, "ly"), nk._attr(g, "lz")
    r, r2 = nk._attr(g, "r"), nk._attr(g, "r2")
    t = nk._attr(g, "t")
    along = g.math("SUBTRACT", lx, 0.5)
    st = g.noise(1.0, detail=3.0, roughness=0.5,
                 vector=kg._vec(g, g.math("MULTIPLY", along, 14.0), g.math("MULTIPLY", g.math("SUBTRACT", ly, 0.5), 260.0),
                                g.math("MULTIPLY", g.math("SUBTRACT", lz, 0.5), 260.0)))
    stripes = kf._ridged(g, st)
    ripe = g.mix(g.ramp(g.math("ADD", r, g.math("MULTIPLY", r2, 0.3)), 0.2, 0.9), (0.2, 0.082, 0.026), (0.3, 0.15, 0.05))
    col = g.mix(g.ramp(r2, 0.86, 0.96), ripe, (0.2, 0.17, 0.05))
    col = g.mix(g.ramp(r2, 0.0, 0.1), col, (0.34, 0.22, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(stripes, 0.75, 0.97), 0.7), col, (0.05, 0.02, 0.008))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(60.0, detail=4.0), 0.5, 0.75), 0.35), col, (0.09, 0.04, 0.015))
    col = g.mix(g.ramp(t, 0.16, 0.05), col, (0.46, 0.34, 0.2))
    grit_d, grit_r = kf._cells(g, 600.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.15, 0.03), g.math("MULTIPLY", g.ramp(grit_d, 0.4, 0.1), 0.6)), col,
                (0.2, 0.14, 0.08))
    col = g.mix(g.ramp(t, 0.9, 1.0), col, (0.045, 0.022, 0.01))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, stripes), 0.15))
    rough = g.mixf(g.ramp(t, 0.16, 0.05), 0.42, 0.85)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0004))


def cap_material():
    """The acorn cup: a rough grey-brown shell of tight overlapping scales (Voronoi plates, each its own shade), darker
    in the cracks, pale and worn on the scale tips, dark and felted toward the stalk."""
    mat, g = tk.new_material("AcornCap")
    t = nk._attr(g, "t")
    d, rr = kf._cells(g, 560.0, kf._warped(g, 150.0, 0.0012))
    d2, rr2 = kf._cells(g, 240.0, kf._warped(g, 90.0, 0.002))
    col = g.mix(g.ramp(rr, 0.0, 1.0), (0.1, 0.065, 0.04), (0.2, 0.15, 0.1))
    col = g.mix(g.math("MULTIPLY", g.ramp(rr2, 0.5, 0.9), 0.4), col, (0.27, 0.22, 0.16))
    col = g.mix(g.math("MULTIPLY", g.ramp(d, 0.2, 0.55), 0.7), col, (0.03, 0.02, 0.014))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(80.0, detail=3.0), 0.55, 0.78), 0.4), col, (0.25, 0.25, 0.2))
    col = g.mix(g.ramp(t, 0.0, 0.25), col, (0.07, 0.045, 0.028))
    col = tk.grade(g, col, sat=0.9, value=0.95)
    height = g.math("SUBTRACT", 1.0, g.ramp(d, 0.1, 0.55))
    return tk.finish(mat, g, col, 0.0, 0.85, g.bump(height, 1.0, 0.0007))


def flesh_material():
    """The kernel: cream, finely grained, mottled brown, a darker papery skin at the rim (t 1)."""
    mat, g = tk.new_material("AcornFlesh")
    t = nk._attr(g, "t")
    col = g.mix(g.ramp(g.noise(120.0, detail=4.0), 0.35, 0.7), (0.42, 0.33, 0.19), (0.58, 0.48, 0.3))
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(30.0, detail=3.0), 0.5, 0.75), 0.4), col, (0.4, 0.28, 0.14))
    col = g.mix(g.ramp(t, 0.9, 1.0), col, (0.3, 0.18, 0.08))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    return tk.finish(mat, g, col, 0.0, 0.7, g.bump(g.noise(260.0, detail=3.0), 0.3, 0.0004))


nut = nut_material()
cap = cap_material()
flesh = flesh_material()

b = kg.Ground(NAME)
kg.base_layer(b, floor, patch, rnd, reach=0.74)

# Oak leaves first (the bed the acorns lie on)
for k, (x, y) in enumerate(patch.sample(rnd, 46, min_gap=0.035)):
    big = k % 3 == 0
    curl = (rnd.uniform(-0.1, 0.4), rnd.uniform(-0.2, 0.4), rnd.uniform(0.0, 0.7), rnd.uniform(-0.5, 0.5))
    kg.add_leaf(b, oak, kg.oak_outline(rnd, 3 if big else (2 if k % 3 == 1 else 1)), rnd.uniform(0.09, 0.125), (x, y),
                rnd.uniform(0, math.tau), heap, rnd, curl=curl, tilt=(rnd.uniform(-3, 3), rnd.uniform(-3, 3)),
                r2=rnd.uniform(0.2, 1.0), lod=0 if big else 1, lod_scale=1.4)

PROFILE = [(0.0, 0.0), (0.88, 0.14), (1.0, 0.45), (0.58, 0.84), (0.0, 1.0)]
CAP = [(0.0, -0.1), (0.62, -0.04), (1.0, 0.05), (1.12, 0.2), (1.1, 0.33)]


def nut_profile(L, R):
    return [(R * r, L * h) for r, h in PROFILE]


def cap_profile(L, R):
    return [(R * r + (0.0012 if r == 1.0 else 0.0), L * h) for r, h in CAP]


def place(L, R, at, yaw, pitch):
    """A rigid acorn lying near horizontal, resting on the heap: returns (its base, its axis)."""
    ax = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
    p0 = Vector((at[0], at[1], 0.0)) - ax * (L * 0.5)
    z = max(heap.top(at[0] + ax.x * L * f, at[1] + ax.y * L * f) for f in (-0.4, 0.0, 0.4)) + R * 0.95 + 0.001
    base = Vector((p0.x, p0.y, z - ax.z * L * 0.5))
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        q = base + ax * (L * f)
        for dx, dy, k in ((0, 0, 1.0), (R, 0, 0.6), (-R, 0, 0.6), (0, R, 0.6), (0, -R, 0.6)):
            heap.stamp(q.x + dx, q.y + dy, q.z + R * k)
    return base, ax


def whole(at, L, R, with_cap, lod):
    base, ax = place(L, R, at, rnd.uniform(0, math.tau), rnd.uniform(-0.12, 0.2))
    kg.lathe(b, nut, nut_profile(L, R), base, ax, segments=6, t=(0.0, 0.25, 0.5, 0.78, 1.0), rnd=rnd, r=rnd.random(),
             r2=rnd.random(), lod=lod, lod_scale=1.4, phase=rnd.uniform(0, 1))
    if with_cap:
        kg.lathe(b, cap, cap_profile(L, R), base, ax, segments=7, t=(0.0, 0.3, 0.6, 0.85, 1.0), rnd=rnd, lod=lod,
                 lod_scale=1.4)
        # the inner lip of the cup, so it isn't an open shell
        kg.lathe(b, cap, [(1.1 * R, 0.33 * L), (0.96 * R, 0.31 * L)], base, ax, segments=7, t=(1.0, 1.0), rnd=rnd, lod=1)


def loose_cap(at, L, R, lod):
    yaw = rnd.uniform(0, math.tau)
    pitch = rnd.choice((math.pi / 2.0, rnd.uniform(0.2, 0.7), math.pi * 0.9))
    ax = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
    z = heap.top(*at) + R * 0.7 + 0.001
    base = Vector((at[0], at[1], z)) - ax * (L * 0.1)
    kg.lathe(b, cap, cap_profile(L, R), base, ax, segments=7, t=(0.0, 0.3, 0.6, 0.85, 1.0), rnd=rnd, lod=lod, lod_scale=1.4)
    kg.lathe(b, flesh, [(1.1 * R, 0.33 * L), (0.96 * R, 0.31 * L), (0.7 * R, 0.1 * L), (0.0, 0.0)], base, ax, segments=7,
             t=(0.0, 0.0, 0.0, 0.0), rnd=rnd, inward=True, lod=1)
    heap.stamp(at[0], at[1], z + R)


def gnawed(at, L, R, lod):
    yaw = rnd.uniform(0, math.tau)
    base, ax = place(L * 0.7, R, at, yaw, rnd.uniform(-0.1, 0.3))
    cut = 0.62

    def rag(i, a):
        return 1.0, (0.035 * L * math.sin(5 * a + yaw) + 0.02 * L * math.sin(9 * a) if i == 3 else 0.0)

    prof = [(0.0, 0.0), (0.88 * R, 0.14 * L), (1.0 * R, 0.45 * L), (0.9 * R, cut * L)]
    kg.lathe(b, nut, prof, base, ax, segments=7, t=(0.0, 0.25, 0.5, 0.7), rnd=rnd, wobble=rag, lod=lod, lod_scale=1.4)
    inner = [(0.9 * R, cut * L), (0.8 * R, cut * L - 0.01 * L), (0.62 * R, 0.52 * L), (0.28 * R, 0.46 * L), (0.0, 0.44 * L)]
    kg.lathe(b, flesh, inner, base, ax, segments=7, t=(1.0, 0.8, 0.4, 0.2, 0.0), rnd=rnd, wobble=rag, inward=True, lod=1)


def split(at, L, R, lod):
    """Two half-shells lying side by side, cut faces up, the cream kernel showing."""
    yaw = rnd.uniform(0, math.tau)
    for sgn in (-1, 1):
        off = Vector((-math.sin(yaw), math.cos(yaw), 0.0)) * (R * 1.3 * sgn)
        pos = (at[0] + off.x + rnd.uniform(-0.004, 0.004), at[1] + off.y + rnd.uniform(-0.004, 0.004))
        base, ax = place(L, R * 0.6, pos, yaw + rnd.uniform(-0.15, 0.15), 0.0)
        # Sit it lower (half of it is the shell below the cut) with its flat side up
        c = Vector(base)
        _, s, u = kf.basis(ax)
        # the half circle that goes below the cut plane: u is up-ish, so span from pi to 2pi (sin < 0)
        kg.lathe(b, nut, nut_profile(L, R), c, ax, segments=4, t=(0.0, 0.25, 0.5, 0.78, 1.0), rnd=rnd, phase=math.pi,
                 span=math.pi, lod=lod, lod_scale=1.4)
        m = b.mesh(flesh)
        prof = nut_profile(L, R)
        pts_a = [c + ax * h + s * r for r, h in prof]
        pts_b = [c + ax * h - s * r for r, h in prof]
        m.begin(c)
        ring = pts_a[:-1] + [pts_a[-1]] + list(reversed(pts_b[1:-1]))
        vs = [m.v(p, 0.5, lx=0.5, ly=0.5, lz=0.5, r=0.5, r2=0.5) for p in ring]
        for i in range(1, len(vs) - 1):
            f = m.f((vs[0], vs[i], vs[i + 1]), False)
            if f is not None:
                f.normal_update()
                if f.normal.z < 0:
                    f.normal_flip()


# Scatter the acorns: bare nuts, nuts in caps, loose caps, gnawed, split
spots = patch.sample(rnd, 20, min_gap=0.075, reach=0.8)
kinds = ["cap", "bare", "bare", "cap", "bare", "gnaw", "bare", "cap", "loose", "bare", "split", "cap", "bare", "loose",
         "gnaw", "bare", "cap", "split", "loose", "bare"]
for k, (at, kind) in enumerate(zip(spots, kinds)):
    L = rnd.uniform(0.04, 0.05)
    R = rnd.uniform(0.0125, 0.0155)
    lod = 0 if k % 3 != 1 else 1
    if kind == "bare":
        whole(at, L, R, False, lod)
    elif kind == "cap":
        whole(at, L, R, True, lod)
    elif kind == "loose":
        loose_cap(at, L, R, lod)
    elif kind == "gnaw":
        gnawed(at, L, R, 0)
    else:
        split(at, L, R, 0)

pieces = b.objects()
kg.build(SCRIPT, NAME, pieces, MODELS, PREVIEWS, size=1024,
         density={"AcornNut": 2.2, "AcornCap": 2.0, "AcornFlesh": 1.5, "AcornOakLeaf": 0.7, "AcornDuff": 0.4})
print("[%s] done" % SCRIPT)
