"""RiverStones (ground cover, water's edge): about 16 smooth, wet-looking dark river stones 8 to 25 cm across, packed
together over a bed of damp sand and silt, half sunk, no two alike: blue-black slate, grey-green and brown-black
stones with a fine pale speckle, a film of dried silt on their tops, sand grains stuck to their feet; four of them
crossed by a pale quartz band. Fine gravel bits in the sand between them.

    blender -b --factory-startup --python river_stones.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_stones as ks_  # noqa: E402
import kit_forest as kf  # noqa: E402
import zkit as tk  # noqa: E402
import naturekit as nk  # noqa: E402
from mathutils import Vector  # noqa: E402

NAME, SCRIPT = "RiverStones", "river_stones"
MODELS, PREVIEWS = ks_.args()
nk.reset()
rnd = random.Random(31)
G = nk.GROUND


def river_stone(name):
    """A wet river cobble as node signals: slate blue-black, grey-green or brown-black by its own number, fine pale
    speckle and darker mottling, a few pits and hairline cracks, damp gloss on the undersides and a dried film of
    pale silt on top in patches, sand stuck low down; stones numbered above 0.84 carry a pale quartz band."""
    mat, g = tk.new_material(name)
    t, L = ks_.stone_frame(g)
    fam = g.math("FRACT", g.math("MULTIPLY", t, 13.7))
    base = g.mix(g.ramp(fam, 0.0, 0.5), (0.03, 0.036, 0.045), (0.052, 0.057, 0.056))
    base = g.mix(g.ramp(fam, 0.55, 1.0), base, (0.06, 0.05, 0.04))
    mott = g.noise(7.0, detail=5.0, vector=L)
    base = g.mix(g.math("MULTIPLY", g.ramp(mott, 0.4, 0.8), 0.55), base, tuple(c * 1.7 for c in (0.05, 0.052, 0.054)))
    # fine pale speckle (quartz and feldspar grains) and dark crystals
    sd, sr = kf._cells(g, 520.0, L)
    spk = g.math("MULTIPLY", g.ramp(sd, 0.42, 0.2), g.ramp(sr, 0.7, 0.85))
    base = g.mix(g.math("MULTIPLY", spk, 0.6), base, (0.2, 0.2, 0.19))
    dk = g.math("MULTIPLY", g.ramp(sd, 0.4, 0.2), g.ramp(sr, 0.25, 0.05))
    base = g.mix(g.math("MULTIPLY", dk, 0.7), base, (0.012, 0.012, 0.014))
    # pits and hairline cracks
    pd, pr = kf._cells(g, 95.0, kf._warped(g, 25.0, 0.003, L))
    pit = g.math("MULTIPLY", g.ramp(pd, 0.17, 0.07), g.ramp(pr, 0.8, 0.95))
    base = g.mix(g.math("MULTIPLY", pit, 0.7), base, (0.012, 0.012, 0.012))
    ce = kf._voronoi(g, 3.0, kf._warped(g, 6.0, 0.03, L), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.006, 0.0), g.ramp(g.noise(8.0, detail=3.0, vector=L), 0.45, 0.6))
    base = g.mix(g.math("MULTIPLY", crack, 0.8), base, (0.01, 0.01, 0.011))
    # the pale band: a stripe across the stone, ragged-edged, fine parallel veins in it
    lx = g.separate(L)[0]
    wob = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(22.0, detail=4.0, vector=L), 0.5), 0.02)
    cx = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(2.0, vector=L), 0.5), 0.05)
    dist = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ADD", lx, wob), cx))
    half = g.math("ADD", 0.011, g.math("MULTIPLY", g.noise(2.7, vector=L), 0.012))
    flag = g.ramp(t, 0.83, 0.85)
    band = g.math("MULTIPLY", g.ramp(g.math("SUBTRACT", half, dist), 0.0, 0.0025), flag)
    vein = g.math("SINE", g.math("ADD", g.math("MULTIPLY", lx, 1100.0), g.math("MULTIPLY", g.noise(60.0, detail=3.0, vector=L), 6.0)))
    pale = g.mix(g.ramp(vein, -0.4, 0.8), (0.24, 0.225, 0.19), (0.38, 0.35, 0.3))
    pale = g.mix(g.math("MULTIPLY", g.ramp(g.noise(130.0, detail=3.0, vector=L), 0.55, 0.8), 0.4), pale, (0.2, 0.19, 0.17))
    base = g.mix(band, base, pale)
    # damp: darker lower down; dried silt film on the tops in patches; sand stuck to the feet
    z = g.separate(g.coords())[2]
    nz = ks_.ks._normal_z(g)
    wet = g.ramp(z, G + 0.05, G + 0.005)
    base = g.mix(g.math("MULTIPLY", wet, 0.4), base, tuple(c * 0.55 for c in (0.04, 0.045, 0.05)))
    silt_n = g.math("ADD", g.noise(6.0, detail=5.0, vector=L), g.math("MULTIPLY", g.noise(80.0, detail=3.0, vector=L), 0.15))
    silt = g.math("MULTIPLY", g.ramp(silt_n, 0.62, 0.72), g.ramp(nz, 0.35, 0.85))
    silt = g.math("MULTIPLY", silt, 0.8)
    base = g.mix(silt, base, g.mix(g.ramp(g.noise(300.0, detail=2.0), 0.3, 0.7), (0.2, 0.18, 0.14), (0.3, 0.27, 0.21)))
    scol, sh, sr_ = ks_.sand_signals(g, color=((0.17, 0.14, 0.1), (0.26, 0.21, 0.15)), wet=0.6)
    feet = g.math("MULTIPLY", g.ramp(z, G + 0.03, G + 0.0), g.ramp(g.noise(40.0, detail=3.0), 0.25, 0.5))
    base = g.mix(g.math("MULTIPLY", feet, 0.9), base, scol)
    col = ks_.tint_by(g, base, t, (0.85, 0.87, 0.9), (1.2, 1.12, 1.05))
    col = tk.grade(g, col, sat=0.95, value=1.0)
    # height and roughness: smooth with pits, cracks, silt crust and sand; wet gloss
    height = g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(40.0, detail=4.0, vector=L), 0.5), 0.35))
    height = g.math("SUBTRACT", height, g.math("ADD", g.math("MULTIPLY", pit, 0.5), g.math("MULTIPLY", crack, 0.6)))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", silt, 0.25), g.math("MULTIPLY", g.math("MULTIPLY", feet, sh), 0.4)))
    rough = g.mixf(g.ramp(g.noise(10.0, detail=3.0, vector=L), 0.3, 0.7), 0.3, 0.52)
    rough = g.mixf(wet, rough, 0.24)
    rough = g.mixf(silt, rough, 0.9)
    rough = g.mixf(feet, rough, 0.95)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0022))


stone_mat = river_stone("RiverStone")
sand_mat = ks_.sand_material("RiverSand", color=((0.14, 0.115, 0.085), (0.24, 0.195, 0.14)), wet=0.7, ripple=0.05,
                             relief=0.003)

S = ks_.Set(NAME)
# The bed of sand and silt, its ragged outline lapping out between and round the stones
ks_.pad(S.gm(sand_mat), (0.0, 0.0), 0.42, rnd, sides=34, dome=0.006, lobes=0.28, stretch=(1.05, 0.92), yaw=0.4, floor=G + 0.004)

radii = [0.12, 0.105, 0.098, 0.088, 0.082, 0.075, 0.07, 0.066, 0.06, 0.055, 0.05, 0.047, 0.044, 0.04, 0.04, 0.036]
pts = ks_.pack(radii, 0.36, rnd, stretch=(1.05, 0.9), touch=0.92, pull=0.012, iters=160)
# band stones: numbers above 0.84; the rest below it
band_idx = {1, 4, 8, 11}
for i, (r, p) in enumerate(zip(radii, pts)):
    tv = rnd.uniform(0.86, 0.99) if i in band_idx else rnd.uniform(0.0, 0.8)
    ks_.pebble(S, stone_mat, p.x, p.y, r * 0.9, rnd, flat=rnd.uniform(0.5, 0.72), elong=rnd.uniform(1.05, 1.35), tv=tv,
               chip=0.1, power=rnd.uniform(2.0, 2.5), rough=0.05, sub=3 if r > 0.07 else 2, lod=2, tilt=0.18)

pieces = S.objects()
model = ks_.export(NAME, pieces, MODELS, size=1024, density={"RiverStone": 1.0, "RiverSand": 0.6})
ks_.preview(SCRIPT, model, PREVIEWS, kind="shore", height=0.08)
print("[%s] done" % SCRIPT)
