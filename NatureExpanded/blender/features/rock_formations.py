"""Biome rock formations, all solid (voxel colliders from the meshes; see featurekit):

 desert (red banded sandstone):  Hoodoo01 (a balanced caprock), Hoodoo02 (tall, two caps), Hoodoo03 (a trio),
                                 DesertArch01 (a natural arch, 4 to 5 m high, you can walk through it), MesaLedge01
 snow (frost-shattered slate):   SnowSpire01, SnowSpire02 (leaning pair), SnowSlab01 (tilted slabs with icicles)
 wasteland (pale wind-carved):   WindColumn01, WindColumn02 (undercut columns), WasteSlab01 (a rust-streaked slab)

    blender -b --factory-startup --python rock_formations.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import formations as fm  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]


def rock_mats(kind, **kw):
    mk = {"sandstone": fm.sandstone, "slate": fm.slate, "waste": fm.wasteland}[kind]
    return mk("FormRock", **kw), mk("FormSkirt", **kw)


# Each builder returns (bodies, extra probes, top height above ground) after adding geometry to Builder b
def hoodoo(b, body, skirt, seed, height, base, neck, cap, caps=1, lean=(0.0, 0.0), at=(0.0, 0.0), faceted=0.0):
    prof = [(0.0, base), (height * 0.18, base * 0.8), (height * 0.4, (base + neck) * 0.5), (height * 0.62, neck)]
    top = height
    if caps == 2:
        prof += [(height * 0.7, neck * 1.15), (height * 0.76, cap * 0.78), (height * 0.8, cap * 0.78),
                 (height * 0.84, neck * 0.8), (height * 0.9, neck * 0.9)]
    else:
        prof += [(height * 0.8, neck * 1.1), (height * 0.88, neck * 1.0)]
    prof += [(top - 0.55, cap * 0.85), (top - 0.38, cap), (top - 0.1, cap * 0.95), (top, cap * 0.55)]
    prof = sorted(prof)
    bm = fm.column(prof, seed=seed, sides=30, rough=0.07, ellipse=1.08, yaw=seed * 37.0, at=at, lean=lean, steps=4,
                   faceted=faceted)
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    return out


def build_hoodoo01(b, body, skirt):
    return [hoodoo(b, body, skirt, 3, 4.8, 1.05, 0.5, 0.95)], (), 4.8


def build_hoodoo02(b, body, skirt):
    return [hoodoo(b, body, skirt, 8, 6.6, 1.15, 0.5, 0.9, caps=2, lean=(0.12, -0.06))], (), 6.6


def build_hoodoo03(b, body, skirt):
    return [hoodoo(b, body, skirt, 5, 4.4, 0.95, 0.45, 0.85, at=(0.0, 0.0)),
            hoodoo(b, body, skirt, 6, 3.0, 0.7, 0.36, 0.6, at=(1.55, 0.9)),
            hoodoo(b, body, skirt, 7, 2.0, 0.55, 0.3, 0.48, at=(-1.25, 1.2))], (), 4.4


def build_arch(b, body, skirt):
    bm = fm.arch(span=4.6, leg=1.35, pier=1.3, depth=2.5, seed=4, sides=22, steps=40)
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    # Rays that must pass through the opening (along y, at knee, chest and head height, and slightly off center)
    probes = [(0.0, -6.0, G + 0.6, 0.0, 1.0, 0.0), (0.0, -6.0, G + 1.6, 0.0, 1.0, 0.0), (0.4, -6.0, G + 1.0, 0.0, 1.0, 0.0),
              (-0.4, -6.0, G + 2.0, 0.0, 1.0, 0.0)]
    return [out], probes, 4.8


def build_mesa(b, body, skirt):
    prof = [(0.0, 2.35), (0.85, 2.3), (0.95, 1.95), (1.8, 1.9), (1.9, 1.45), (2.6, 1.4), (2.7, 1.2)]
    bm = fm.column(prof, seed=11, sides=36, rough=0.05, ellipse=1.15, yaw=15, steps=3, faceted=0.55)
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    return [out], (), 2.7


def spire(b, body, skirt, seed, height, base, at=(0.0, 0.0), lean=(0.0, 0.0)):
    prof = [(0.0, base), (height * 0.25, base * 0.82), (height * 0.5, base * 0.58), (height * 0.75, base * 0.34),
            (height * 0.93, base * 0.14), (height, 0.0)]
    bm = fm.column(prof, seed=seed, sides=26, rough=0.07, ellipse=1.0, yaw=seed * 29.0, at=at, lean=lean, steps=5, faceted=0.85)
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    return out


def build_spire01(b, body, skirt):
    return [spire(b, body, skirt, 2, 6.2, 1.15)], (), 6.2


def build_spire02(b, body, skirt):
    return [spire(b, body, skirt, 4, 5.4, 1.0, lean=(0.35, 0.1)), spire(b, body, skirt, 7, 3.4, 0.75, at=(1.5, 0.8), lean=(-0.2, 0.0))], (), 5.4


def build_slab(b, body, skirt):
    """Two tilted slabs leaning on each other, snow in the lee, icicles hanging from the upper slab's lower edge."""
    r1 = fk.Rock(radii=(1.9, 0.38, 1.7), height=3.1, seed=21, power=3.6, rough=0.04, yaw=20, tilt=(-14.0, 0.0), at=(-0.3, 0.2),
                 subdiv=4, planes=[((0, 0, 1), 1.6)])
    r2 = fk.Rock(radii=(1.3, 0.3, 1.1), height=1.9, seed=23, power=3.4, rough=0.05, yaw=25, tilt=(22.0, 0.0), at=(0.9, -1.1),
                 subdiv=4)
    out = []
    for r in (r1, r2):
        bm = r.build()
        out.append(fk.emit_rock(b, bm, body, skirt))
        bm.free()
    return out, (), 3.1


def column_waste(b, body, skirt, seed, height, base, waist, belly, cap, at=(0.0, 0.0)):
    prof = [(0.0, base), (height * 0.1, base * 0.7), (height * 0.22, waist), (height * 0.3, waist * 1.05),
            (height * 0.5, belly), (height * 0.72, belly * 0.92), (height * 0.86, cap), (height * 0.97, cap * 0.9),
            (height, cap * 0.5)]
    bm = fm.column(prof, seed=seed, sides=28, rough=0.08, ellipse=1.12, yaw=seed * 41.0, at=at, steps=4, faceted=0.25)
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    return out


def build_wind01(b, body, skirt):
    return [column_waste(b, body, skirt, 3, 4.2, 1.0, 0.46, 0.8, 0.7)], (), 4.2


def build_wind02(b, body, skirt):
    return [column_waste(b, body, skirt, 5, 3.4, 0.9, 0.4, 0.7, 0.62),
            column_waste(b, body, skirt, 6, 2.2, 0.6, 0.3, 0.5, 0.45, at=(1.3, 0.8))], (), 3.4


def build_wasteslab(b, body, skirt):
    r = fk.Rock(radii=(0.42, 1.5, 1.8), height=3.3, seed=31, power=3.8, rough=0.05, yaw=35, tilt=(0.0, 7.0), subdiv=4,
                planes=[((0, 0, 1), 1.7), ((0.2, 1.0, 0.6), 1.2)])
    bm = r.build()
    out = fk.emit_rock(b, bm, body, skirt)
    bm.free()
    return [out], (), 3.3


# name: (rock kind, material kwargs, builder, texture size, voxel)
SPECS = {
    "Hoodoo01": ("sandstone", {}, build_hoodoo01, 2048, 0.16),
    "Hoodoo02": ("sandstone", {}, build_hoodoo02, 2048, 0.18),
    "Hoodoo03": ("sandstone", {}, build_hoodoo03, 2048, 0.16),
    "DesertArch01": ("sandstone", {"lichen": 0.15}, build_arch, 2048, 0.2),
    "MesaLedge01": ("sandstone", {}, build_mesa, 2048, 0.2),
    "SnowSpire01": ("slate", {}, build_spire01, 2048, 0.16),
    "SnowSpire02": ("slate", {}, build_spire02, 2048, 0.16),
    "SnowSlab01": ("slate", {}, build_slab, 2048, 0.16),
    "WindColumn01": ("waste", {}, build_wind01, 2048, 0.16),
    "WindColumn02": ("waste", {}, build_wind02, 2048, 0.16),
    "WasteSlab01": ("waste", {}, build_wasteslab, 2048, 0.16),
}


def build(name):
    kind, kw, builder, size, voxel = SPECS[name]
    nk.reset()
    body, skirt = rock_mats(kind, **kw)
    b = ks.Builder(name)
    bodies, probes, top = builder(b, body, skirt)
    b.lod = 0
    if name == "SnowSlab01":
        # Icicles under the upper slab's lower edge: little cones hanging from it
        ice = fm.slate("FormIce", snow=0.0, ice=1.0, lo=(0.35, 0.42, 0.5), hi=(0.5, 0.58, 0.66), band_lo=(0.4, 0.48, 0.56),
                       band_hi=(0.5, 0.58, 0.66), crack=0.0)
        rnd = random.Random(2)
        b.lod = 0
        for i in range(7):
            x = -1.4 + i * 0.45 + rnd.uniform(-0.1, 0.1)
            y = 0.2 - 0.38
            z0 = G + 1.7 + rnd.uniform(-0.05, 0.1)
            ln = rnd.uniform(0.25, 0.6)
            bm = fm.column([(z0 - ln + 0.001, 0.004), (z0 - ln * 0.5, 0.03), (z0 - 0.01, 0.045)], seed=i, sides=8, rough=0.05,
                           at=(x, y), sink=-(z0 - ln), steps=1)
            fk.emit_rock(b, bm, ice, ice)
            bm.free()
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    model = fk.export(name, pieces, bodies, FEATURES, size=size, voxel=voxel, margin=0.04, probes=probes, limit=120,
                      density={"FormRock": 1.0, "FormSkirt": 0.1, "FormIce": 0.2})
    reach = max(max(abs(v.x), abs(v.y)) for vs, _ in bodies for v in vs)
    nk.previews(name.lower(), model, PREVIEWS, focus_height=G + top * 0.45, distance=3.0 + 2.1 * max(reach, top * 0.7))
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
