"""DeadBrush (wasteland): a tangle of dead scrub 40 to 70 cm. Nine zig-zagging stems bleached silver-grey, half of
them snapped off short, a mess of side branches and brittle twigs crossing each other, a few broken sticks fallen
on the ground under it; dry tan seed heads among it: brome grass stalks nodding with spikelets, and a few rusty
clusters of dried seed on the twig ends.

    blender -b --factory-startup --python dead_brush.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

NAME, SCRIPT = "DeadBrush", "dead_brush"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(61)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

dead = ks.bark("DeadWood", (0.38, 0.36, 0.33), (0.24, 0.22, 0.2), rough=0.85, grain=80.0, lichen=(0.42, 0.42, 0.34),
               lichen_amount=0.15, base_dark=0.45, sat=0.8)
seed = nk.plant("DrySeed", (0.56, 0.45, 0.27), (0.44, 0.33, 0.18), rough=0.8, vary=0.3, sat=0.9, value=0.95)
rust = nk.plant("DrySeedRust", (0.45, 0.24, 0.1), (0.32, 0.17, 0.08), rough=0.85, vary=0.3, sat=0.9, value=0.95)
stalk = nk.plant("DryStalk", (0.5, 0.42, 0.27), (0.36, 0.29, 0.17), rough=0.8, vary=0.3, sat=0.85)

b = ks.Builder("Brush")


def snap(br, chance):
    """Breaks a branch off short: drops its last stretch and leaves a blunt, ragged end."""
    if rnd.random() < chance and len(br.points) > 2:
        keep = rnd.randint(max(2, len(br.points) - 2), len(br.points) - 1)
        pts = br.points[:keep]
        radii = [max(r, br.radii[0] * 0.35) for r in br.radii[:keep]]
        br.__init__(pts, radii, br.level, br.t0, br.t1)
        br.broken = True
    elif rnd.random() < chance * 0.5:
        br.radii[-1] = max(br.radii[0] * 0.3, 0.0012)
        br.broken = True
    return br


stems = []
for i in range(12):
    a = (i + rnd.uniform(-0.3, 0.3)) / 12 * math.tau
    lean = rnd.random()
    r0 = 0.01 + 0.07 * lean
    tilt = math.radians(10 + 45 * lean)
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    st = ks.grow(rnd, (r0 * math.cos(a), r0 * math.sin(a), G), d, rnd.uniform(0.5, 0.78) - 0.15 * lean,
                 rnd.uniform(0.008, 0.012), 0.0, segments=5, gravity=0.15, wander=0.16, kink=0.25)
    stems.append(snap(st, 0.5))
for st in stems:
    ks.fit([st], 0.4)
branches = []
for st in stems:
    for br in ks.branch_out(rnd, st, 6, (0.12, 0.95), (0.12, 0.3), (30, 95), 0.6, segments=2, wander=0.25,
                            kink=0.3, lift=0.0, gravity=rnd.uniform(0.0, 1.2)):
        branches.append(snap(br, 0.4))
twigs = []
for br in branches:
    for tw in ks.branch_out(rnd, br, 4, (0.15, 1.0), (0.04, 0.12), (35, 95), 0.6, segments=1, wander=0.0):
        if rnd.random() < 0.3:
            tw.radii[-1] = 0.001
        twigs.append(tw)
ks.wood(b, dead, stems, sides=(4,), jag=1.2, rnd=rnd)
ks.wood(b, dead, branches, sides=(3,), jag=1.2, rnd=rnd)
b.lod = 1
ks.wood(b, dead, twigs, sides=(3,))

# Broken sticks fallen under it
for k in range(5):
    a = rnd.uniform(0, math.tau)
    r = rnd.uniform(0.05, 0.3)
    c = Vector((r * math.cos(a), r * math.sin(a), G + 0.006))
    d = Vector((math.cos(a + rnd.uniform(1.0, 2.2)), math.sin(a + rnd.uniform(1.0, 2.2)), 0.0))
    L = rnd.uniform(0.15, 0.35)
    rad = rnd.uniform(0.004, 0.008)
    pts = [c - d * L * 0.5, c + d * L * 0.05 + Vector((0, 0, 0.004)), c + d * L * 0.5]
    ks.tube(b, dead, pts, [rad, rad * 0.9, rad * 0.8], sides=3, cap=True, start_cap=True, jag=1.5, rnd=rnd)
b.lod = 0

# Dry brome grass among it: thin stalks nodding with drooping spikelets, a few dry blades at their feet
heads = 0
for k, (x, y) in enumerate(nk.scatter(7, 0.3, seed=9, min_gap=0.1)):
    out = Vector((x, y, 0.0))
    out = out.normalized() if out.length > 1e-4 else Vector((1.0, 0.0, 0.0))
    h = rnd.uniform(0.38, 0.6)
    d = (UP + out * rnd.uniform(0.1, 0.35)).normalized()
    pts = [ks.bent((x, y, G), d, h, 0.35, s) for s in (0.0, 0.4, 0.75, 1.0)]
    b.lod = 1
    ks.tube(b, stalk, pts, [0.0018, 0.0015, 0.0011, 0.0], sides=3, cap=False)
    b.lod = 0
    for j in range(12):
        s = 0.62 + 0.38 * j / 11
        p = ks.bent((x, y, G), d, h, 0.35, s)
        a = j * 2.39996
        _, u, v = ks.basis(ks.bent_tangent((x, y, G), d, h, 0.35, s))
        sd = ((u * math.cos(a) + v * math.sin(a)) * 0.8 + Vector((0, 0, -0.9))).normalized()
        ks.leaf(b, seed, p, sd, rnd.uniform(0.028, 0.04), 0.008, bend=0.15, fold=0.4, profile="lance")
    heads += 1
    for j in range(5):
        a = rnd.uniform(0, math.tau)
        bd = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, 1.0))
        b.lod = 1
        ks.leaf(b, stalk, (x + 0.01 * math.cos(a), y + 0.01 * math.sin(a), G), bd, rnd.uniform(0.12, 0.2), 0.006,
                bend=rnd.uniform(0.4, 0.9), fold=0.0, profile="lance", rows=2, roll=rnd.uniform(-40, 40))
        b.lod = 0

# Rusty clusters of dried seed on some twig ends
for tw in rnd.sample([t for t in twigs if t.radii[-1] < 1e-6], 7):
    t, td = tw.tip, tw.tip_dir
    for j in range(5):
        q = t + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 1))) * 0.009
        ks.berry(b, rust if j % 2 else seed, q, rnd.uniform(0.0045, 0.006), rnd, sides=4, stretch=1.4,
                 axis=(td + UP).normalized())
    heads += 1

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] seed heads %d" % (SCRIPT, heads))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.28, distance=1.7)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.28, distance=1.7)
print("[%s] done" % SCRIPT)
