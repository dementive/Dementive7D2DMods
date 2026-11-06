"""IceCrust (snow biome): a 0.9 m patch of thin broken ice over frozen mud, the crust of a puddle that froze, sank when
the water drained from under it and cracked. A ragged bed of black frozen mud (frost-cracked, flecked with rime, a few
pine needles, snow creeping in at its rim) with a dozen irregular plates of milky blue ice 6 to 10 mm thick lying on it,
tilted a few degrees, riding up over one another, the biggest ones 30 cm across. Each plate is opaque and glossy, its
"depth" painted in: milky and clear blue zones, hairline fractures drawn twice (white, and a shadow offset beneath it) so
they seem to lie inside the ice, trapped bubbles with dark rims, patches of frost, dirty edges where mud has soaked up
into the thin rim. A little hoarfrost needles along some edges.

    blender -b --factory-startup --python ice_crust.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "groundcover"))
import gckit as gc  # noqa: E402
nk, kf, ks, tk = gc.nk, gc.kf, gc.ks, gc.tk
G = gc.G

NAME, SCRIPT = "IceCrust", "ice_crust"
MODELS, PREVIEWS = gc.args()
gc.reset()
rnd = random.Random(14)


# ---------------------------------------------------------------- materials

def star_crack(g, cx, cy, spokes=4.0, reach=0.16, seed=0.0, width=0.07):
    """An impact star: thin cracks fanning out from (cx, cy), with a few broken rings round it, as a 0..1 mask."""
    x, y, z = g.separate(g.coords())
    dx = g.math("SUBTRACT", x, cx)
    dy = g.math("SUBTRACT", y, cy)
    ang = g.math("ARCTAN2", dy, dx)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy)))
    wob = g.math("MULTIPLY", g.math("SUBTRACT", g.noise(9.0 + seed, detail=3.0), 0.5), 1.4)
    s = g.math("ABSOLUTE", g.math("SINE", g.math("ADD", g.math("MULTIPLY", ang, spokes), g.math("MULTIPLY", wob, g.ramp(r, 0.0, reach)))))
    spoke = g.ramp(s, width, 0.0)
    spoke = g.math("MULTIPLY", spoke, g.ramp(r, reach, reach * 0.35))
    spoke = g.math("MULTIPLY", spoke, g.ramp(g.noise(30.0 + seed, detail=3.0), 0.3, 0.45))
    ring_s = g.math("ABSOLUTE", g.math("SINE", g.math("ADD", g.math("MULTIPLY", r, 260.0), g.math("MULTIPLY", wob, 9.0))))
    ring = g.math("MULTIPLY", g.ramp(ring_s, 0.1, 0.0), g.ramp(r, reach * 0.8, reach * 0.2))
    ring = g.math("MULTIPLY", ring, g.ramp(g.noise(24.0 + seed, detail=3.0), 0.5, 0.62))
    return g.math("MAXIMUM", spoke, ring)


def straight_cracks(g, scale, offset, width, coverage, warp=0.01):
    """Fractures along the edges of big warped cells, only some of them, as a 0..1 mask."""
    add = g.node("ShaderNodeVectorMath", operation="ADD")
    g.links.new(g.coords(), add.inputs[0])
    add.inputs[1].default_value = offset
    v = kf._warped(g, scale * 0.8, warp, add.outputs[0])
    e = kf._voronoi(g, scale, v, feature="DISTANCE_TO_EDGE")
    line = g.ramp(e, width, 0.0)
    gate = g.ramp(g.noise(scale * 0.45, detail=3.0, vector=add.outputs[0]), coverage[0], coverage[1])
    return g.math("MULTIPLY", line, gate)


def hairlines(g, scale, width=0.03, coverage=(0.45, 0.58)):
    v = kf._warped(g, scale * 0.4, 0.004)
    ridge = kf._ridged(g, g.noise(scale, detail=2.0, roughness=0.5, vector=v))
    line = g.ramp(ridge, 1.0 - width, 1.0)
    return g.math("MULTIPLY", line, g.ramp(g.noise(5.0, detail=3.0), coverage[0], coverage[1]))


def ice_top(name, stars):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    # What shows through: milky ice, clearer blue ice, and the dark mud under thin or clear ice
    cloud = g.noise(8.0, detail=5.0, roughness=0.6, distortion=0.4)
    clear = g.ramp(g.noise(4.2, detail=5.0, distortion=0.5), 0.42, 0.7)
    milky = g.mix(g.ramp(cloud, 0.3, 0.72), (0.36, 0.52, 0.62), (0.58, 0.72, 0.8))
    deep = g.mix(g.ramp(g.noise(14.0, detail=4.0), 0.3, 0.7), (0.1, 0.2, 0.27), (0.17, 0.3, 0.38))
    col = g.mix(g.math("MULTIPLY", clear, 0.85), milky, deep)
    # Slightly different clarity in fine streaks, like layers of freezing
    grain = g.noise(1.0, detail=4.0, roughness=0.6, vector=ks._stretched(g, (38.0, 14.0, 38.0)))
    col = g.mix(g.math("MULTIPLY", g.ramp(grain, 0.35, 0.7), 0.3), col, (0.5, 0.64, 0.73))
    # Cracks inside the ice: a darker blue shadow below and offset, then the white fracture on top
    cracks_w = None
    cracks_s = None
    for (sc, w, cov, off) in ((4.2, 0.011, (0.36, 0.48), (0.0, 0.0, 0.0)), (9.5, 0.008, (0.46, 0.58), (3.0, 1.0, 0.0))):
        shadow = straight_cracks(g, sc, (off[0] + 0.004, off[1] + 0.0035, off[2]), w * 1.3, cov)
        line = straight_cracks(g, sc, off, w, cov)
        cracks_w = line if cracks_w is None else g.math("MAXIMUM", cracks_w, line)
        cracks_s = shadow if cracks_s is None else g.math("MAXIMUM", cracks_s, shadow)
    for k, (cx, cy) in enumerate(stars):
        cracks_w = g.math("MAXIMUM", cracks_w, star_crack(g, cx, cy, spokes=[4.0, 5.0, 3.0][k % 3], seed=k * 3.0))
    hair = hairlines(g, 70.0)
    cracks_w = g.math("MAXIMUM", cracks_w, g.math("MULTIPLY", hair, 0.7))
    col = g.mix(g.math("MULTIPLY", cracks_s, 0.7), col, (0.12, 0.2, 0.27))
    col = g.mix(g.math("MULTIPLY", cracks_w, 0.9), col, (0.74, 0.84, 0.9))
    # Trapped bubbles in clusters: a pale dome with a dark rim
    for scale, gate_lo, size in ((130.0, 0.66, 0.3), (48.0, 0.84, 0.3)):
        d, r = kf._cells(g, scale, kf._warped(g, 30.0, 0.002))
        cluster = g.ramp(g.noise(7.0, detail=3.0), 0.46, 0.64)
        gate = g.math("MULTIPLY", g.ramp(r, gate_lo, gate_lo + 0.03), cluster)
        disc = g.math("MULTIPLY", g.ramp(d, size, size * 0.65), gate)
        ring = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(d, size * 0.55, size * 0.95), g.ramp(d, size * 1.45, size * 1.0)), gate)
        col = g.mix(g.math("MULTIPLY", ring, 0.75), col, (0.1, 0.18, 0.25))
        col = g.mix(g.math("MULTIPLY", disc, 0.6), col, (0.74, 0.84, 0.9))
    # Frost bloom in patches, rough and white, sprinkled with rime crystals
    frost = g.ramp(g.noise(10.0, detail=5.0, distortion=0.3), 0.64, 0.74)
    cd, cr = kf._cells(g, 330.0)
    rime = g.math("MULTIPLY", g.ramp(cd, 0.5, 0.2), g.ramp(g.noise(6.0, detail=3.0), 0.45, 0.68))
    col = g.mix(g.math("MULTIPLY", frost, 0.8), col, (0.6, 0.7, 0.78))
    col = g.mix(g.math("MULTIPLY", rime, 0.55), col, (0.72, 0.8, 0.86))
    # The rim: mud soaked up into the thin ice, ragged, with grit
    edge = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(26.0, detail=5.0), 0.5), 0.3))
    dirt = g.ramp(edge, 0.26, 0.0)
    col = g.mix(g.math("MULTIPLY", dirt, 0.8), col, g.mix(g.ramp(g.noise(80.0, detail=4.0), 0.3, 0.7), (0.09, 0.08, 0.07), (0.19, 0.17, 0.14)))
    grit, gr = kf._cells(g, 260.0)
    col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(grit, 0.3, 0.1), dirt), g.ramp(gr, 0.4, 0.5)), col, (0.04, 0.035, 0.03))
    # Brown smudges of mud under the ice
    smudge = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=5.0, distortion=0.6), 0.62, 0.8), 0.45)
    col = g.mix(smudge, col, (0.17, 0.15, 0.12))
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("SUBTRACT", 0.55, g.math("ADD", g.math("MULTIPLY", g.math("MAXIMUM", cracks_w, cracks_s), 0.18),
                                              g.math("MULTIPLY", dirt, -0.08)))
    height = g.math("ADD", height, g.math("MULTIPLY", frost, 0.2))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(240.0, detail=3.0), 0.07))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(22.0, detail=4.0), 0.12))
    rough = g.mixf(frost, g.math("ADD", 0.08, g.math("MULTIPLY", g.noise(30.0), 0.1)), 0.7)
    rough = g.mixf(g.math("MAXIMUM", rime, cracks_w), rough, 0.5)
    rough = g.mixf(dirt, rough, 0.8)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(height, 1.0, 0.0022))


def ice_edge(name):
    """The broken edge of a plate: whiter, fractured, in thin horizontal layers, muddy where it touched the ground."""
    mat, g = tk.new_material(name)
    z = g.separate(g.coords())[2]
    layers = g.noise(1.0, detail=3.0, roughness=0.5, vector=ks._stretched(g, (6.0, 6.0, 900.0)))
    col = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), (0.42, 0.57, 0.67), (0.66, 0.78, 0.85))
    col = g.mix(g.math("MULTIPLY", g.ramp(layers, 0.45, 0.7), 0.5), col, (0.42, 0.57, 0.68))
    cd, cr = kf._cells(g, 160.0)
    col = g.mix(g.math("MULTIPLY", g.ramp(cd, 0.4, 0.15), 0.35), col, (0.94, 0.97, 0.99))
    dirt = g.math("MULTIPLY", g.ramp(g.noise(24.0, detail=5.0), 0.38, 0.62), 0.8)
    col = g.mix(dirt, col, (0.1, 0.085, 0.07))
    col = tk.grade(g, col, sat=0.92, value=0.97)
    return tk.finish(mat, g, col, 0.0, 0.32, g.bump(g.math("ADD", layers, g.noise(200.0, detail=3.0)), 0.8, 0.0015))


def frozen_mud(name):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    big = g.noise(12.0, detail=6.0, roughness=0.62)
    col = g.mix(g.ramp(big, 0.3, 0.72), (0.04, 0.032, 0.026), (0.1, 0.078, 0.06))
    # Grit and little stones frozen into it
    gd, gr = kf._cells(g, 190.0, kf._warped(g, 90.0, 0.002))
    stones = g.math("MULTIPLY", g.ramp(gd, 0.34, 0.2), g.ramp(gr, 0.55, 0.62))
    col = g.mix(g.math("MULTIPLY", stones, 0.8), col, g.mix(g.ramp(gr, 0.5, 1.0), (0.1, 0.09, 0.08), (0.26, 0.23, 0.2)))
    # Frost cracks: polygons of heaved mud with rime along their edges
    e = kf._voronoi(g, 8.0, kf._warped(g, 22.0, 0.012, kf._warped(g, 4.0, 0.03)), feature="DISTANCE_TO_EDGE")
    crack = g.ramp(e, 0.014, 0.003)
    rime_line = g.math("MULTIPLY", g.ramp(e, 0.03, 0.012), g.ramp(g.noise(12.0, detail=4.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", rime_line, 0.7), col, (0.62, 0.7, 0.76))
    col = g.mix(crack, col, (0.012, 0.01, 0.008))
    # Needle-ice rime crystals frosting the lumps
    cd, cr = kf._cells(g, 420.0)
    sparkle = g.math("MULTIPLY", g.ramp(cd, 0.34, 0.14), g.ramp(g.noise(9.0, detail=3.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", sparkle, 0.8), col, (0.78, 0.85, 0.9))
    # Thin black ice skin in the low places
    skin = g.ramp(g.noise(6.5, detail=5.0, distortion=0.5), 0.6, 0.66)
    col = g.mix(g.math("MULTIPLY", skin, 0.75), col, (0.05, 0.07, 0.085))
    # Snow creeping in from the rim in ragged tongues
    reach = g.math("ADD", t, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(9.0, detail=5.0, distortion=0.4), 0.5), 0.55))
    reach = g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", g.noise(55.0, detail=3.0), 0.5), 0.12))
    snow = g.ramp(reach, 0.2, 0.06)
    scol = g.mix(g.ramp(g.noise(30.0, detail=3.0), 0.3, 0.7), (0.74, 0.8, 0.88), (0.88, 0.92, 0.96))
    col = g.mix(snow, col, scol)
    rough = g.mixf(skin, 0.88, 0.18)
    rough = g.mixf(sparkle, rough, 0.4)
    rough = g.mixf(snow, rough, 0.6)
    height = g.math("ADD", g.math("MULTIPLY", big, 0.4), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, crack), 0.3))
    height = g.math("ADD", height, g.math("ADD", g.math("MULTIPLY", stones, 0.25), g.math("MULTIPLY", snow, 0.3)))
    height = g.math("ADD", height, g.math("MULTIPLY", g.noise(300.0, detail=3.0), 0.1))
    return tk.finish(mat, g, tk.grade(g, col, sat=0.95, value=0.97), 0.0, rough, g.bump(height, 1.0, 0.004))


def hoarfrost(name):
    mat, g = tk.new_material(name)
    col = g.mix(g.ramp(g.noise(120.0, detail=3.0), 0.3, 0.7), (0.72, 0.8, 0.88), (0.92, 0.96, 0.99))
    return tk.finish(mat, g, col, 0.0, 0.3, g.bump(g.noise(300.0), 0.2, 0.0006))


# ---------------------------------------------------------------- the plates, laid out first so the materials know where
# the impact stars are

b = ks.Builder("Ice")
SEED = 4.0


def hf(x, y):
    """Frozen mud: heaved lumps and ridges a few millimeters high."""
    return 0.006 * (0.55 + gc.fbm(x * 10.0, y * 10.0, SEED)) + 0.003 * gc.fbm(x * 34.0, y * 34.0, SEED + 3.0)


def inside(poly, x, y):
    c = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


plates = []   # (center, rot, thick, poly)


def support(x, y):
    """Height of the highest plate top under (x, y), or None."""
    best = None
    for c, rot, thick, poly in plates:
        dx, dy = x - c.x, y - c.y
        if dx * dx + dy * dy > 0.16:
            continue
        local = rot.inverted() @ Vector((dx, dy, 0.0))
        if inside(poly, local.x, local.y):
            n = rot @ Vector((0, 0, 1))
            z = c.z + thick * 0.5 - (n.x * dx + n.y * dy) / n.z
            if best is None or z > best:
                best = z
    return best


mud = frozen_mud("FrozenMud")
edge = ice_edge("IceEdge")
frost_mat = hoarfrost("Hoarfrost")
needle = kf.litter_material("PineNeedle", (0.17, 0.1, 0.05), (0.1, 0.065, 0.04), spots=0.2)

R = gc.patch(b, mud, rnd, radius=0.4, cell=0.042, height=hf, sink=0.014, seed=SEED, rough=0.28, floor=0.62)
gc.needles(b, needle, rnd, R, 70, hf=hf, length=(0.025, 0.05), width=0.0014, lift=0.001)

radii = sorted([rnd.uniform(0.07, 0.17) for _ in range(15)], reverse=True)
specs = []
for i, rad in enumerate(radii):
    poly = gc.shard_poly(rnd, rad, cuts=(4, 7), elong=(1.0, 1.7), jag=0.008, step=0.05)
    reach = max(math.hypot(*p) for p in poly)
    thick = rnd.uniform(0.006, 0.0105) * (0.75 + 0.45 * min(1.0, rad / 0.17))
    big = rad > 0.11
    mag = rnd.uniform(1.0, 5.0 if big else 12.0)
    ph = rnd.uniform(0, 360)
    tilt = (mag * math.cos(math.radians(ph)), mag * math.sin(math.radians(ph)))
    yaw = rnd.uniform(0, 360)
    rot = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(tilt[0]), 3, "X")
           @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y"))
    best = None
    for cand in gc.scatter_in(R, 14, rnd, 0.0, inset=0.9):
        x, y = cand
        if math.hypot(x, y) + reach > 0.46:
            continue
        need = -1e9
        for px, py in poly[::2] + [(0.0, 0.0)]:
            w = rot @ Vector((px * 0.92, py * 0.92, -thick * 0.5))
            wx, wy = x + w.x, y + w.y
            floor = G + hf(wx, wy) + 0.002
            sup = support(wx, wy)
            if sup is not None:
                floor = max(floor, sup + 0.0012)
            need = max(need, floor - w.z)
        # prefer low spots, and some overlap with the neighbours
        score = need - G + (0.01 if not any(math.hypot(x - c.x, y - c.y) < 0.2 for c, _, _, _ in plates) else 0.0)
        if best is None or score < best[0]:
            best = (score, x, y, need)
    if best is None:
        continue
    _, x, y, need = best
    center = Vector((x, y, need))
    plates.append((center, rot, thick, poly))
    specs.append((center, poly, thick, tilt, yaw, big))

# Impact stars on three of the biggest plates
stars = [(plates[k][0].x, plates[k][0].y) for k in (0, 2, min(5, len(plates) - 1))]
top = ice_top("IceTop", stars)

rim_lists = []
for center, poly, thick, tilt, yaw, big in specs:
    ws = rnd.uniform(0, 30)
    dish = rnd.uniform(-0.004, 0.004)
    rad = max(math.hypot(*p) for p in poly)

    def warp(px, py, rad=rad, dish=dish, ws=ws):
        r = math.hypot(px, py) / max(rad, 1e-3)
        return dish * (r * r - 0.4) + 0.0016 * gc.fbm(px * 22.0, py * 22.0, ws) + 0.0012 * gc.fbm(px * 60.0, py * 60.0, ws + 5)

    rim_lists.append(gc.plate(b, top, edge, center, poly, thick, rnd, tilt=tilt, yaw=yaw, rings=2 if big else 1,
                              warp=warp, lod=2))

# Hoarfrost needles along some plate edges
for rim in rim_lists:
    for k in range(len(rim)):
        if rnd.random() < 0.2:
            p = rim[k]
            nxt = rim[(k + 1) % len(rim)]
            q = p.lerp(nxt, rnd.uniform(0.2, 0.8))
            d = Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 1.0))
            gc.spike(b, frost_mat, q + Vector((0, 0, 0.001)), d, rnd.uniform(0.008, 0.018), 0.0016, sides=3, lod=1)

pieces = b.objects()
for o in pieces:
    print("  %s %d" % (o.name, ks.triangles([o])))
gc.stats(SCRIPT, pieces)
model = ks.export(NAME, pieces, MODELS, size=gc.atlas_size(1024), coarse_ratio=0.4,
                  density={"FrozenMud": 0.7, "IceTop": 1.25, "IceEdge": 0.6, "Hoarfrost": 0.3, "PineNeedle": 0.3})
gc.previews(SCRIPT, model, PREVIEWS, kind="snow", lod_name=NAME + "_LOD1", macro=((0.1, -0.22), (0.02, 0.0)))
print("[%s] done" % SCRIPT)
