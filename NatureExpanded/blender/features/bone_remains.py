"""ElkSkull01 (desert and wasteland: a bleached bull elk skull with its antlers, half in the sand), ElkRibcage01
(desert and wasteland: a collapsed ribcage along a few vertebrae), AntlerShed01 (forest: a shed antler in the leaves).
Small; the block is walk-through (Collide melee) with a box or two so a pick can hit it (kind "bone" in gen_nature).

    blender -b --factory-startup --python bone_remains.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import naturekit as nk  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]


def bone(name, tone=(0.44, 0.39, 0.3), dark=(0.22, 0.17, 0.11), weather=1.0, sand=0.0):
    """Weathered bone: fibres along its length, a pitted porous surface, grey-brown weathering cracks, stains and, near the
    ground, dirt (and drifted sand)."""
    mat, g = tk.new_material(name)
    co = g.coords()
    fib = g.noise(1.0, detail=5.0, vector=ks._stretched(g, (60.0, 60.0, 60.0)))
    cells, r1 = kf._cells(g, 160.0)
    tonal = g.noise(5.0, detail=4.0)
    col = g.mix(g.ramp(tonal, 0.3, 0.7), tone, tuple(c * 0.78 for c in tone))
    col = g.mix(g.math("MULTIPLY", g.ramp(fib, 0.5, 0.85), 0.35), col, dark)
    pores = g.math("MULTIPLY", g.ramp(cells, 0.5, 0.15), g.ramp(g.noise(8.0, detail=3.0), 0.45, 0.7))
    col = g.mix(g.math("MULTIPLY", pores, 0.5), col, tuple(c * 0.45 for c in dark))
    ce = kf._voronoi(g, 14.0, kf._warped(g, 20.0, 0.01), feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.ramp(ce, 0.02, 0.0), g.ramp(g.noise(6.0), 0.4, 0.6))
    col = g.mix(g.math("MULTIPLY", crack, 0.8 * weather), col, tuple(c * 0.3 for c in dark))
    stain = g.math("MULTIPLY", g.ramp(g.noise(3.0, detail=4.0), 0.55, 0.75), 0.5 * weather)
    col = g.mix(stain, col, (0.1, 0.075, 0.045))
    z = g.separate(co)[2]
    soil = (0.2, 0.15, 0.1) if sand <= 0 else (0.42, 0.28, 0.16)
    col = g.mix(g.math("MULTIPLY", g.ramp(z, G + 0.12, G - 0.02), 0.85), col, soil)
    col = tk.grade(g, col, sat=0.95, value=0.95)
    height = g.math("ADD", g.math("MULTIPLY", fib, 0.4), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, pores), 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.5))
    return tk.finish(mat, g, col, 0.0, 0.8, g.bump(height, 1.0, 0.004))


def limb(b, mat, pts, radii, sides=6):
    ks.tube(b, mat, pts, radii, sides=sides, cap=True)


def antler(b, mat, base, direction, length, rnd, tines=4, radius=0.026, curl=0.5, up=Vector((0, 0, 1))):
    """A sweeping beam from `base` going `direction`, curving up and back, with tines forward off its top side."""
    d = Vector(direction).normalized()
    side = d.cross(up).normalized()
    pts = []
    for k in range(9):
        s = k / 8
        pts.append(Vector(base) + d * (length * s) + up * (curl * length * s * s * 0.9) - d * (0.0) + side * (0.03 * math.sin(s * 3)))
    radii = [radius * (1.0 - 0.7 * (k / 8) ** 1.4) for k in range(9)]
    limb(b, mat, pts, radii)
    for t in range(tines):
        s = 0.3 + 0.62 * t / max(1, tines - 1)
        k = int(s * 8)
        p = pts[k]
        td = (up * 0.8 + d * 0.5 + side * rnd.uniform(-0.2, 0.2)).normalized()
        tl = length * rnd.uniform(0.22, 0.38) * (1.0 - 0.25 * t / tines)
        tp = [p + td * (tl * q / 4) + d * (0.04 * q * q / 4) for q in range(5)]
        limb(b, mat, tp, [radius * 0.6 * (1.0 - 0.8 * (q / 4)) for q in range(5)], sides=5)


def skull(b, mat, dark, rnd):
    # Half buried, lying on its left side's antlers: cranium, snout, jaw, eye sockets, antlers
    cr = fk.Rock(radii=(0.2, 0.115, 0.1), height=0.22, seed=3, power=2.3, rough=0.035, at=(-0.1, 0.0), subdiv=3, sink=0.1)
    bm = cr.build()
    fk.emit_rock(b, bm, mat, mat)
    bm.free()
    limb(b, mat, [Vector((0.08, 0.0, G + 0.13)), Vector((0.3, 0.0, G + 0.12)), Vector((0.5, 0.0, G + 0.1)),
                  Vector((0.62, 0.0, G + 0.09))], [0.085, 0.07, 0.05, 0.04], sides=8)
    limb(b, mat, [Vector((0.12, 0.0, G + 0.055)), Vector((0.35, 0.0, G + 0.05)), Vector((0.58, 0.0, G + 0.045))],
         [0.05, 0.04, 0.03], sides=6)
    for sy in (-1, 1):
        bm = fk.Rock(radii=(0.038, 0.02, 0.034), height=0.2, seed=7 + sy, power=2.2, rough=0.0, at=(0.12, sy * 0.1), subdiv=2,
                     sink=0.05).build()
        fk.emit_rock(b, bm, dark, dark)
        bm.free()
    for sy in (-1, 1):
        antler(b, mat, Vector((-0.12, sy * 0.07, G + 0.2)), Vector((-0.4, sy * 0.9, 0.5)), 0.7, rnd, tines=4, radius=0.026,
               curl=0.45)


def ribcage(b, mat, rnd):
    for i in range(7):
        x = -0.55 + i * 0.18
        bm = fk.Rock(radii=(0.05, 0.04, 0.035), height=0.12, seed=i, power=2.4, rough=0.04, at=(x, 0.0), subdiv=2, sink=0.1).build()
        fk.emit_rock(b, bm, mat, mat)
        bm.free()
    for i in range(7):
        x = -0.55 + i * 0.18
        for sy in (-1, 1):
            if rnd.random() < 0.15:
                continue
            fall = rnd.uniform(0.0, 0.5) if sy > 0 else rnd.uniform(0.5, 1.0)
            r = 0.3 - 0.05 * abs(i - 3) * 0.6
            pts = []
            for k in range(10):
                a = k / 9 * math.radians(165 - 70 * fall)
                pts.append(Vector((x + 0.03 * math.sin(a), sy * r * (1 - math.cos(a)) * 1.05, G + 0.1 + r * math.sin(a) * (1.0 - 0.5 * fall))))
            limb(b, mat, pts, [0.02 * (1.0 - 0.5 * (k / 9)) for k in range(10)], sides=5)


def shed(b, mat, rnd):
    antler(b, mat, Vector((-0.55, 0.0, G + 0.05)), Vector((1.0, 0.25, 0.05)), 1.0, rnd, tines=5, radius=0.032, curl=0.12)
    bm = fk.Rock(radii=(0.055, 0.05, 0.04), height=0.1, seed=9, power=2.2, rough=0.1, at=(-0.55, 0.0), subdiv=2, sink=0.05).build()
    fk.emit_rock(b, bm, mat, mat)
    bm.free()


# name: (builder, tone kwargs, boxes [(cx, cy, cz, sx, sy, sz)])
SPECS = {
    "ElkSkull01": (skull, dict(sand=1.0), [(0.15, 0.0, G + 0.1, 0.9, 0.5, 0.2)], 1024),
    "ElkRibcage01": (ribcage, dict(sand=1.0, tone=(0.5, 0.45, 0.35)), [(0.0, 0.0, G + 0.15, 1.2, 0.7, 0.3)], 1024),
    "AntlerShed01": (shed, dict(tone=(0.34, 0.27, 0.18), dark=(0.14, 0.1, 0.06)), [(0.0, 0.1, G + 0.08, 1.0, 0.4, 0.16)], 1024),
}


def build(name):
    fn, kw, boxes, size = SPECS[name]
    nk.reset()
    rnd = random.Random(sum(map(ord, name)))
    mat = bone("Bone", **kw)
    dark = bone("BoneDark", tone=(0.06, 0.05, 0.04), dark=(0.02, 0.02, 0.02), weather=0.2)
    b = ks.Builder(name)
    b.lod = 0
    if fn is skull:
        fn(b, mat, dark, rnd)
    else:
        fn(b, mat, rnd)
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    extra = ["box %.3f %.3f %.3f %.3f %.3f %.3f" % bx for bx in boxes]
    model = fk.export(name, pieces, [], FEATURES, size=size, extra=extra, density={"Bone": 1.0, "BoneDark": 0.1}, coarse=0.6)
    nk.previews(name.lower(), model, PREVIEWS, focus_height=G + 0.2, distance=2.4)
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
