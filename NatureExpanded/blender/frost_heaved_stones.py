"""FrostHeavedStones (snow biome): seven small fieldstones, 6 to 17 cm, each stranded on a little pedestal of frozen soil
that the frost heaved up round it, the soil between them worn down, so they sit like mushrooms: wide stone on a narrow
neck striped with vertical needle-ice grooves, the neck flaring into the ground. Round every pedestal's foot a ring of
thin white needle-ice spikes, tufts of them standing among the stones; frozen, frost-cracked ground with a ragged rim
that snow creeps over; a dusting of snow on the stone tops and a few little drifts in their lee.

    blender -b --factory-startup --python frost_heaved_stones.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
sys.path.insert(0, os.path.join(HERE, "features"))
import gckit as gc  # noqa: E402
import featurekit as fk  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "FrostHeavedStones", "frost_heaved_stones"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(23)
SEED = 9.0


# ---------------------------------------------------------------- materials

def frost_stone(name):
    """A cold grey-brown fieldstone (granite crystals, rain streaks, pale lichen, hairline cracks), soil crusted on the
    lowest part where it touches the pedestal, rime in the cracks, and a dusting of snow on the faces that look up."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col, height, rough = fk.granite_surface(g, moss=0.0, lichen=0.45, stain=0.35, scale=3.2)
    col = tk.grade(g, col, sat=0.8, value=0.95)
    soil = g.math("MULTIPLY", g.ramp(g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(40.0, detail=4.0), 0.5), 0.4)), 0.3, 0.0), 0.95)
    col = g.mix(soil, col, g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.05, 0.04, 0.032), (0.11, 0.09, 0.07)))
    nz = ks._normal_z(g)
    snow = g.math("MULTIPLY", g.ramp(nz, 0.66, 0.92), g.ramp(g.noise(26.0, detail=5.0), 0.42, 0.62))
    snow = g.math("MULTIPLY", snow, g.ramp(t, 0.1, 0.4))
    gran, _ = kf._cells(g, 700.0)
    col = g.mix(g.math("MULTIPLY", snow, 0.92), col, g.mix(g.ramp(gran, 0.7, 0.2), (0.7, 0.75, 0.82), (0.86, 0.9, 0.95)))
    rough = g.mixf(snow, rough, 0.62)
    height = g.math("ADD", g.math("MULTIPLY", height, 0.8), g.math("MULTIPLY", snow, 0.35))
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.006))


def pedestal(name):
    """The soil neck under a stone: frost-heaved, striped with vertical needle-ice grooves and columns, pebbles frozen in
    (t runs 0 at its foot to 1 under the stone), rimed and glinting."""
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    st = ks._stretched(g, (110.0, 110.0, 7.0))
    grooves = g.noise(1.0, detail=4.0, roughness=0.6, vector=st)
    col = g.mix(g.ramp(g.noise(14.0, detail=5.0), 0.3, 0.7), (0.045, 0.035, 0.028), (0.1, 0.08, 0.062))
    col = g.mix(g.math("MULTIPLY", g.ramp(grooves, 0.55, 0.78), 0.55), col, (0.3, 0.28, 0.26))
    col = g.mix(g.math("MULTIPLY", g.ramp(grooves, 0.3, 0.1), 0.8), col, (0.02, 0.016, 0.013))
    gd, gr = kf._cells(g, 160.0)
    peb = g.math("MULTIPLY", g.ramp(gd, 0.34, 0.2), g.ramp(gr, 0.55, 0.62))
    col = g.mix(g.math("MULTIPLY", peb, 0.8), col, g.mix(g.ramp(gr, 0.5, 1.0), (0.12, 0.11, 0.1), (0.26, 0.24, 0.21)))
    cd, cr = kf._cells(g, 380.0)
    rime = g.math("MULTIPLY", g.ramp(cd, 0.36, 0.12), g.ramp(g.noise(8.0, detail=3.0), 0.36, 0.58))
    col = g.mix(g.math("MULTIPLY", rime, 0.85), col, (0.78, 0.85, 0.9))
    col = g.mix(g.math("MULTIPLY", g.ramp(t, 0.35, 0.0), g.ramp(g.noise(30.0, detail=4.0), 0.4, 0.62)), col,
                (0.62, 0.7, 0.78))
    height = g.math("ADD", g.math("MULTIPLY", grooves, 0.7), g.math("MULTIPLY", peb, 0.3))
    height = g.math("ADD", height, g.math("MULTIPLY", rime, 0.2))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.97), 0.0, g.mixf(rime, 0.9, 0.35), g.bump(height, 1.0, 0.0035))


def snow_dust(name):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    col = g.mix(g.ramp(g.noise(24.0, detail=4.0), 0.3, 0.7), (0.5, 0.57, 0.66), (0.7, 0.75, 0.82))
    cd, cr = kf._cells(g, 900.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.4, 0.12), 0.5), col, (0.88, 0.92, 0.96))
    # Wind-packed ripples along x
    rip = kf._ridged(g, g.noise(1.0, detail=2.0, vector=ks._stretched(g, (34.0, 3.0, 8.0))))
    col = g.mix(g.math("MULTIPLY", g.ramp(rip, 0.8, 1.0), 0.25), col, (0.78, 0.83, 0.9))
    height = g.math("ADD", g.math("MULTIPLY", rip, 0.25), g.math("MULTIPLY", g.noise(380.0, detail=3.0), 0.2))
    return tk.finish(mat, g, col, 0.0, 0.5, g.bump(height, 1.0, 0.0012))


def hoarfrost(name):
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.7, 0.78, 0.86), (0.92, 0.96, 0.99))
    return tk.finish(mat, g, col, 0.0, 0.3, g.bump(g.noise(300.0), 0.2, 0.0006))


stone_mat = frost_stone("FrostStone")
ped_mat = pedestal("FrostPedestal")
soil_mat = gc.frozen_ground("FrozenSoil", dark=(0.05, 0.04, 0.032), light=(0.12, 0.095, 0.072), pebbles=1.4, glaze=0.5,
                            snow_reach=1.1)
snow_mat = snow_dust("SnowDrift")
frost_mat = hoarfrost("NeedleIce")
needle = kf.litter_material("PineNeedle", (0.17, 0.1, 0.05), (0.1, 0.065, 0.04), spots=0.2)

b = ks.Builder("Heave")

# ---------------------------------------------------------------- layout

RADII = [(0.092, 0.074, 0.052), (0.078, 0.064, 0.05), (0.062, 0.05, 0.04), (0.056, 0.045, 0.036), (0.046, 0.038, 0.03),
         (0.038, 0.032, 0.026), (0.03, 0.026, 0.02)]
R0 = gc.outline(SEED, 0.4, 0.26, 0.64)
placed = []   # (x, y, radius, pedestal height)
for rr in RADII:
    rad = max(rr[0], rr[1])
    for _ in range(200):
        a = rnd.uniform(0, gc.TAU)
        r = math.sqrt(rnd.random()) * R0(a) * 0.82
        x, y = r * math.cos(a), r * math.sin(a)
        if all(math.hypot(x - px, y - py) > rad + pr + 0.045 for px, py, pr, _ in placed):
            placed.append((x, y, rad, 0.0))
            break
heights = [0.058, 0.07, 0.046, 0.04, 0.032, 0.026, 0.02]
placed = [(x, y, r, heights[i] * rnd.uniform(0.9, 1.15)) for i, (x, y, r, _) in enumerate(placed)]


def hf(x, y):
    """Frozen ground: lumps a few mm, and the soil rising round each pedestal's foot."""
    h = 0.005 * (0.55 + gc.fbm(x * 9.0, y * 9.0, SEED)) + 0.0025 * gc.fbm(x * 34.0, y * 34.0, SEED + 3.0)
    for px, py, pr, ph in placed:
        d = math.hypot(x - px, y - py) / (pr * 0.75)
        h += ph * 0.3 * math.exp(-d * d * 0.55)
    return h


R = gc.patch(b, soil_mat, rnd, radius=0.4, cell=0.043, height=hf, sink=0.014, seed=SEED, rough=0.26, floor=0.64)
gc.needles(b, needle, rnd, R, 55, hf=hf, length=(0.025, 0.05), width=0.0014, lift=0.001)

# ---------------------------------------------------------------- stones on pedestals

for i, ((x, y, pr, ph), rr) in enumerate(zip(placed, RADII)):
    base = G + ph
    neck = pr * 0.5
    foot = neck * rnd.uniform(1.35, 1.7)
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0.0)) * ph * 0.12
    c0 = Vector((x, y, 0.0))
    pts = [c0 + Vector((0, 0, G - 0.012)), c0 + lean * 0.3 + Vector((0, 0, G + ph * 0.28)),
           c0 + lean * 0.7 + Vector((0, 0, G + ph * 0.66)), c0 + lean + Vector((0, 0, base + 0.006))]
    saved = b.lod
    b.lod = 2
    ks.tube(b, ped_mat, pts, [foot, neck * 1.12, neck * 0.88, neck * 1.0], sides=9, cap=True, t0=0.0, t1=1.0, smooth=True)
    b.lod = saved
    top = c0 + lean + Vector((0, 0, base))
    gc.stone(b, stone_mat, (x + lean.x, y + lean.y, base + rr[2] * 0.62), rr, rnd, subdiv=3 if i == 0 else (2 if rr[0] > 0.05 else 1),
             power=rnd.uniform(2.2, 3.0), rough=0.15, cuts=2 if rr[0] > 0.045 else 1, base_z=base - 0.004,
             t=lambda co, b0=base: max(0.0, min(1.0, (co.z - b0) / 0.05)), tilt=9.0, lod=2)
    # Needle ice round the foot: thin white spikes leaning out
    count = 12 + int(pr * 150)
    for k in range(count):
        a = k / count * gc.TAU + rnd.uniform(-0.25, 0.25)
        rr_ = foot * rnd.uniform(0.95, 1.9)
        px, py = x + rr_ * math.cos(a), y + rr_ * math.sin(a)
        out = Vector((math.cos(a), math.sin(a), 0.0))
        d = (Vector((0, 0, 1.0)) + out * rnd.uniform(0.0, 0.7)).normalized()
        L = rnd.uniform(0.014, 0.034) * (0.7 + 0.6 * pr / 0.09)
        gc.spike(b, frost_mat, (px, py, G + hf(px, py) - 0.002), d, L, rnd.uniform(0.001, 0.0016), sides=3,
                 bend=out * 0.08, lod=1)

# Tufts of needle ice standing among the stones
for k in range(5):
    for _ in range(40):
        a = rnd.uniform(0, gc.TAU)
        r = math.sqrt(rnd.random()) * R(a) * 0.9
        x, y = r * math.cos(a), r * math.sin(a)
        if all(math.hypot(x - px, y - py) > pr + 0.07 for px, py, pr, _ in placed):
            break
    else:
        continue
    for j in range(rnd.randint(6, 10)):
        px, py = x + rnd.uniform(-0.03, 0.03), y + rnd.uniform(-0.03, 0.03)
        d = Vector((rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 1.0))
        gc.spike(b, frost_mat, (px, py, G + hf(px, py) - 0.002), d, rnd.uniform(0.012, 0.03), rnd.uniform(0.0012, 0.0019),
                 sides=3, lod=1)

# A few small drifts of snow in the lee of the bigger stones, and on the ground between
for (x, y, pr, ph), k in zip(placed[:5], range(5)):
    side = rnd.uniform(0, gc.TAU)
    cx, cy = x + math.cos(side) * pr * 1.5, y + math.sin(side) * pr * 1.5
    ks.ground_patch(b, snow_mat, (cx, cy), pr * rnd.uniform(0.9, 1.3), rnd, sides=12, dome=0.012, jitter=0.35, sink=0.006, rings=2)

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"FrozenSoil": 0.6, "FrostStone": 1.5, "FrostPedestal": 1.1, "SnowDrift": 0.5, "NeedleIce": 0.3,
                           "PineNeedle": 0.3})
gc.previews(SCRIPT, model, PREVIEWS, kind="snow", lod_name=NAME + "_LOD1", macro=((0.12, -0.24), (0.0, 0.0)))
print("[%s] done" % SCRIPT)
