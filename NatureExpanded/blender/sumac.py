"""Sumac (forest floor and edges): staghorn sumac in fall, about 1.3 m tall. Three stout, velvety brown stems rise
from the ground and fork into thick blunt branches curving up like antlers; at every branch tip a rosette of long
pinnate leaves (13 to 15 lance leaflets on a red stalk) arches out and droops like a palm, turned scarlet, orange and
crimson, and upright cones of dark red fuzzy fruit stand in the middle of the rosettes. Bare stems below, a blaze of
red above: the color is the point of it.

    blender -b --factory-startup --python sumac.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402
import zkit as tk  # noqa: E402

NAME, SCRIPT = "Sumac", "sumac"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(12)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

bark = ks.bark("SumacBark", (0.27, 0.17, 0.1), (0.17, 0.11, 0.07), rough=0.9, grain=30.0, dots=0.5,
               dot_color=(0.42, 0.33, 0.24), fuzz=0.8)
rachis = nk.plant("SumacRachis", (0.5, 0.05, 0.03), (0.32, 0.03, 0.03), rough=0.5, sat=1.0, value=0.95)
# Fall color: scarlet, red-orange, orange, crimson, and a few leaves still turning
LEAVES = [
    nk.plant("SumacScarlet", (0.66, 0.035, 0.02), (0.48, 0.02, 0.02), rough=0.55, vary=0.3, sat=1.0, value=0.95),
    nk.plant("SumacRedOrange", (0.78, 0.13, 0.015), (0.6, 0.05, 0.015), rough=0.55, vary=0.3, sat=1.0, value=0.95),
    nk.plant("SumacOrange", (0.82, 0.28, 0.02), (0.7, 0.14, 0.015), rough=0.55, vary=0.3, sat=1.0, value=0.95),
    nk.plant("SumacCrimson", (0.4, 0.02, 0.035), (0.28, 0.015, 0.03), rough=0.55, vary=0.3, sat=1.0, value=0.95),
    nk.plant("SumacTurning", (0.7, 0.3, 0.03), (0.3, 0.25, 0.04), rough=0.55, vary=0.45, sat=1.0, value=0.95),
]
WEIGHTS = [0.32, 0.24, 0.16, 0.18, 0.1]


def fruit_material(name):
    """The fruit cone: a dense pack of fuzzy drupes, deep crimson with dark crevices between them."""
    mat, g = tk.new_material(name)
    vor = g.node("ShaderNodeTexVoronoi")
    g._in(vor, "Scale", 140.0)
    g.links.new(g.coords(), vor.inputs["Vector"])
    dist = tk._sock(vor.outputs, "Distance")
    drupe = g.ramp(dist, 0.45, 0.05)
    col = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.42, 0.03, 0.04), (0.64, 0.07, 0.06))
    col = g.mix(drupe, (0.1, 0.01, 0.015), col)
    col = g.mix(g.math("MULTIPLY", g.ramp(g.noise(400.0, detail=2.0), 0.55, 0.75), 0.4), col, (0.62, 0.22, 0.2))
    col = tk.grade(g, col, sat=1.0, value=0.95)
    return tk.finish(mat, g, col, 0.0, 0.95, g.bump(drupe, 0.6, 0.002))


fruit = fruit_material("SumacFruit")
b = ks.Builder("Sumac")

# Three stout stems, forking at the top into antler branches that curve up
stems, forks = [], []
for i in range(3):
    a = (i + rnd.uniform(-0.2, 0.2)) / 3 * math.tau
    r0 = rnd.uniform(0.04, 0.08)
    tilt = math.radians(rnd.uniform(6, 16))
    d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt))
    st = ks.grow(rnd, (r0 * math.cos(a), r0 * math.sin(a), G), d, rnd.uniform(0.62, 0.8), rnd.uniform(0.017, 0.021),
                 0.011, segments=4, wander=0.07)
    stems.append(st)
    forks += ks.branch_out(rnd, st, 3, (0.78, 0.98), (0.24, 0.38), (25, 50), 0.75, segments=3,
                           gravity=-0.9, wander=0.06, tip_radius=0.0075, lift=0.1)
ks.fit(stems + forks, 0.2)
ks.wood(b, bark, stems + forks, sides=(5, 5))
for st in stems:
    # The stem's own blunt top above the fork
    ks.tube(b, bark, [st.tip, st.tip + st.tip_dir * 0.01], [0.011, 0.0], sides=5)

tips = [(f.tip, f.tip_dir) for f in forks] + [(s.tip, s.tip_dir) for s in stems]
leaves = 0
cones = 0
for k, (t, td) in enumerate(tips):
    # A rosette of leaves from just below the tip, ascending then drooping
    n = 7 if k < len(forks) else 5
    phase = rnd.uniform(0, math.tau)
    for j in range(n):
        a = phase + j * 2.39996
        elev = math.radians(rnd.uniform(15, 50))
        out = Vector((math.cos(a) * math.cos(elev), math.sin(a) * math.cos(elev), math.sin(elev)))
        base = t - td * rnd.uniform(0.04, 0.1)
        mat = rnd.choices(LEAVES, WEIGHTS)[0]
        ks.compound_leaf(b, mat, base, out, rnd.uniform(0.36, 0.46), rnd.choice((15, 17)), 0.085, 0.02, rnd,
                         rachis_mat=rachis, rachis_r=0.0022, rachis_segs=2, bend=rnd.uniform(0.45, 0.7), spread=65,
                         droop=0.12, fold=0.35, profile="lance", taper=0.3, start=0.15, leaflet_bend=0.2,
                         far=(0.42, 1.45))
        leaves += 1
    if k < 7:
        # The fruit cone, standing up from the tip clear of the leaves
        axis = (td + UP * 3.0).normalized()
        h = rnd.uniform(0.17, 0.22)
        R = rnd.uniform(0.03, 0.036)
        prof = [0.55, 1.0, 0.97, 0.88, 0.72, 0.5, 0.0]
        along = [0.0, 0.14, 0.34, 0.54, 0.74, 0.9, 1.0]
        pts = [t + axis * (h * f) for f in along]
        rings = ks.tube(b, fruit, pts, [R * p for p in prof], sides=7, start_cap=True)
        # Lumpy, not a smooth cone
        for ring in rings[1:-1]:
            for v in ring:
                c = pts[rings.index(ring)]
                v.co = c + (v.co - c) * rnd.uniform(0.85, 1.12)
        cones += 1

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
print("[%s] leaves %d, cones %d" % (SCRIPT, leaves, cones))
model = ks.export(NAME, pieces, MODELS, size=1024)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.65, distance=3.2)
ks.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.65, distance=3.2)
print("[%s] done" % SCRIPT)
