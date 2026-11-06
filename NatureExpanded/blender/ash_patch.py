"""AshPatch (burnt forest): a 0.9 m drift of grey-white wood ash where something big burned, laid over scorched soil by
the wind: low dunes with fine wind ripples (and tails of ash blown out behind everything that stands in it), dry
cracks that open onto dark soil, crumbs and flakes of ash, charcoal lumps of all sizes, three half-burnt wood chunks,
curled flakes of burnt bark, a handful of black twigs and needles and a rock blackened and heat-cracked by the fire. The
rim is a ragged scatter of thin ash that gives out into the soot of the ground.

    blender -b --factory-startup --python ash_patch.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
import gckit as gc  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "AshPatch", "ash_patch"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(52)
SEED = 6.0

ash = gc.ash_surface("AshDrift", ripple=1.4, cracks=0.45, crack_scale=13.0, light=(0.3, 0.29, 0.28), dark=(0.11, 0.105, 0.1), specks=1.5)
char = gc.char_surface("Char", ash_amount=0.4)
bark_edge = gc.char_surface("BarkEdge", ash_amount=0.15, brown=0.9)
rock = gc.burnt_rock("BurntRock")
burnt = kf.litter_material("BurntNeedles", (0.02, 0.018, 0.016), (0.07, 0.05, 0.04), spots=0.0)
wood_end = nk.plant("SplitCoal", (0.12, 0.07, 0.04), (0.06, 0.04, 0.03), rough=0.9, vary=0.3)

b = ks.Builder("Ash")
R0 = gc.outline(SEED, 0.4, 0.28, 0.6)

# ---------------------------------------------------------------- what stands in the ash (so the wind can tail behind it)
obstacles = []   # (x, y, radius)


def free(x, y, r, gap=0.02):
    return all(math.hypot(x - ox, y - oy) > r + orr + gap for ox, oy, orr in obstacles)


def place(r, tries=80, inset=0.82):
    for _ in range(tries):
        a = rnd.uniform(0, gc.TAU)
        d = math.sqrt(rnd.random()) * R0(a) * inset
        x, y = d * math.cos(a), d * math.sin(a)
        if free(x, y, r):
            obstacles.append((x, y, r))
            return x, y
    return None


rock_at = place(0.08)
chunks = [place(0.05) for _ in range(3)]
barks = [place(0.06) for _ in range(4)]
lumps = []
for _ in range(16):
    r = rnd.uniform(0.012, 0.03)
    p = place(r, inset=0.9)
    if p:
        lumps.append((p, r))
twigs = [place(0.05) for _ in range(5)]


def hf(x, y):
    """Ash: low dunes, and a tail of ash blown out behind every obstacle (the wind blows toward +x), with a scour
    hollow at its upwind side."""
    crest = 1.0 - abs(gc.fbm(x * 3.0 + 0.5 * gc.fbm(y * 3.0, x * 2.0, SEED + 5.0), y * 6.5, SEED)) * 2.2
    h = 0.014 * (0.5 + gc.fbm(x * 4.5, y * 4.5, SEED)) + 0.022 * max(0.0, crest) ** 1.6 + 0.004 * gc.fbm(x * 15.0, y * 15.0, SEED + 2.0)
    for ox, oy, orad in obstacles:
        dx, dy = x - ox, y - oy
        u = dx / (orad * 3.2)
        v = dy / (orad * 1.1)
        if 0.0 < u < 1.6:
            h += orad * 0.45 * math.exp(-v * v) * math.sin(math.pi * min(1.0, u / 1.6 * 1.2)) ** 1.5 * (1.0 - u / 1.6)
        elif -1.2 < u <= 0.0:
            h -= orad * 0.1 * math.exp(-v * v * 0.6) * (1.0 + u / 1.2)
    return h


R = gc.patch(b, ash, rnd, radius=0.4, cell=0.036, height=hf, sink=0.012, seed=SEED, rough=0.28, floor=0.6)
gc.islands(b, ash, rnd, R, 7, hf=hf, seed=SEED)


def at(x, y, dz=0.0):
    return (x, y, G + hf(x, y) + dz)


# ---------------------------------------------------------------- the burnt rock, half sunk in the drift
if rock_at:
    x, y = rock_at
    base = G + hf(x, y) - 0.02
    gc.stone(b, rock, (x, y, base + 0.03), (0.085, 0.066, 0.05), rnd, subdiv=3, power=2.7, rough=0.14, cuts=3, base_z=base,
             t=lambda co: max(0.0, min(1.0, (co.z - base) / 0.06)), tilt=10.0, lod=2)

# ---------------------------------------------------------------- half-burnt wood chunks and charcoal lumps
for p in chunks:
    if not p:
        continue
    x, y = p
    gc.stone(b, char, (x, y, G + hf(x, y) + 0.012), (rnd.uniform(0.04, 0.062), rnd.uniform(0.018, 0.026), 0.017), rnd,
             subdiv=1, power=2.2, rough=0.22, cuts=3, base_z=G + hf(x, y) - 0.004, t=0.5, tilt=6.0, lod=2)
for (p, r) in lumps:
    x, y = p
    gc.blob(b, char, (x, y, G + hf(x, y) + 0.002), (r, r * rnd.uniform(0.6, 1.0), r * rnd.uniform(0.5, 0.8)), rnd,
            sides=5, rings=1, rough=0.3, lod=1)

# ---------------------------------------------------------------- curled flakes of burnt bark
for p in barks:
    if not p:
        continue
    x, y = p
    gc.slab(b, char, bark_edge, (x, y, 0.0), (rnd.uniform(0.07, 0.11), rnd.uniform(0.035, 0.05)), 0.004, rnd,
            yaw=rnd.uniform(0, 360), curl=rnd.uniform(0.5, 1.3), bow=rnd.uniform(0.0, 0.25), nu=4, nv=3, jag=0.18,
            tilt=(rnd.uniform(-5, 5), rnd.uniform(-5, 5)), convex=rnd.random() < 0.5, lod=2, hf=hf)

# ---------------------------------------------------------------- black twigs, burnt needles
for p in twigs:
    if not p:
        continue
    x, y = p
    a = rnd.uniform(0, gc.TAU)
    d = Vector((math.cos(a), math.sin(a), 0.0))
    L = rnd.uniform(0.06, 0.12)
    r = rnd.uniform(0.0035, 0.007)
    c = Vector(at(x, y, r * 0.8))
    pts = [c - d * L * 0.5, c + Vector((0, 0, r * 0.4)), c + d * L * 0.5]
    saved = b.lod
    b.lod = 1
    ks.tube(b, char, pts, [r * 0.8, r, r * 0.7], sides=4, cap=True, start_cap=True, jag=0.8, rnd=rnd)
    b.lod = saved
gc.needles(b, burnt, rnd, R, 90, hf=hf, length=(0.025, 0.05), width=0.0013, lift=0.0012)

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"AshDrift": 1.0, "Char": 1.2, "BarkEdge": 0.8, "BurntRock": 1.4, "BurntNeedles": 0.3})
gc.previews(SCRIPT, model, PREVIEWS, kind="burnt", lod_name=NAME + "_LOD1", macro=((0.1, -0.25), (0.0, 0.0)))
print("[%s] done" % SCRIPT)
