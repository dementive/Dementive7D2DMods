"""RedClover (pine forest meadows): a low mat 15 to 25 cm of red clover filling the block. 30+ round pompom heads 3 cm
across, magenta-pink to rose-red, held just above a carpet of trefoil leaves (three ovals, each with a pale chevron),
a trefoil tucked right under some of the heads as on the real plant, a few small green buds and a couple of browned
spent heads, and meadow grass among them.

The far mesh (kit_lod) keeps every head, grown a little about its center with every other floret left off, and the
flowering stems; it drops the leaves, their stalks and the grass.

    blender -b --factory-startup --python red_clover.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_lod as kl  # noqa: E402
import kit_wayside as ww  # noqa: E402

NAME, SCRIPT = "RedClover", "red_clover"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(11)
G = nk.GROUND
UP = Vector((0.0, 0.0, 1.0))

stalk = nk.plant("CloverStalk", (0.16, 0.22, 0.1), (0.2, 0.2, 0.12), rough=0.7)
leafm = ww.leaf_mat("CloverLeaf", (0.1, 0.19, 0.06), (0.14, 0.21, 0.08), chevron=(0.42, 0.48, 0.32), rough=0.7)
magenta = nk.petal("CloverMagenta", (0.85, 0.5, 0.66), (0.72, 0.04, 0.3), sat=1.0, value=0.95)
rose = nk.petal("CloverRose", (0.85, 0.5, 0.58), (0.76, 0.06, 0.19), sat=1.0, value=0.95)
spent = nk.petal("CloverSpent", (0.4, 0.22, 0.14), (0.24, 0.1, 0.06), sat=0.9, value=0.85)
budm = nk.petal("CloverBud", (0.2, 0.3, 0.12), (0.55, 0.2, 0.32), sat=0.95, value=0.9)
grass = nk.grass()

sheets = {k: ww.Sheet("Clover" + k, m) for k, m in (("Stalk", stalk), ("Leaf", leafm), ("Magenta", magenta),
                                                  ("Rose", rose), ("Spent", spent), ("Bud", budm),
                                                  ("StalkMinor", stalk))}
# Each head's vertices in its sheet, (sheet, first, end, center), so the far mesh can grow it about its center
heads_at = []


def pompom(kind, center, *args, **kw):
    v0 = len(sheets[kind].t)
    ww.pompom(sheets[kind], center, *args, **kw)
    heads_at.append((kind, v0, len(sheets[kind].t), Vector(center)))


def trefoil(at, size, tilt, seed):
    """Three oval leaflets fanning out flat from `at`."""
    r = random.Random(seed)
    a0 = r.uniform(0, math.tau)
    for k in range(3):
        a = a0 + k / 3 * math.tau + r.uniform(-0.25, 0.25)
        d = Vector((math.cos(a), math.sin(a), tilt + r.uniform(-0.1, 0.15)))
        ww.leaf(sheets["Leaf"], at, d, size * r.uniform(0.85, 1.1), size * 0.64, profile="oval", segments=3,
                bend=r.uniform(0.05, 0.2), rib=False, roll=r.uniform(-15, 15), seed=seed * 7 + k)


# The leaf carpet: big trefoils on short petioles 3 to 9 cm, filling the ground between the stems
for i, (x, y) in enumerate(nk.scatter(26, 0.39, seed=4, min_gap=0.065)):
    h = rnd.uniform(0.03, 0.09)
    lean = Vector((x, y, 0.0)) * 0.2 + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0.0))
    top = Vector((x, y, G + h)) + lean
    ww.stalk(sheets["StalkMinor"], [(x, y, G), tuple(top)], 0.0016, 0.0011, t_range=(0.0, 0.7))
    trefoil(top, rnd.uniform(0.034, 0.046), rnd.uniform(0.0, 0.25), seed=i)

# The flowering stems: leafy, rising from the middle at a slant and curving up, 11 to 21 cm, a round pompom head of
# florets at each tip, most facing up; a trefoil on a short petiole halfway up and another right under the head
heads = nk.scatter(30, 0.26, seed=9, min_gap=0.035)
for i, (x, y) in enumerate(heads):
    h = rnd.uniform(0.11, 0.21)
    a = math.atan2(y, x) + rnd.uniform(-0.7, 0.7)
    spread = rnd.uniform(0.35, 0.85)
    pts = ww.path((x, y, G), (math.cos(a) * spread, math.sin(a) * spread, 1.0), h * (1.0 + spread * 0.25), 2,
                  bend=-0.3, wobble=0.04, seed=i)
    ww.stalk(sheets["Stalk"], pts, 0.002, 0.0014)
    top, d = ww.along(pts, 1.0)
    axis = (d + UP * 1.2).normalized()
    at, sd = ww.along(pts, 0.5)
    out = ww.perpendicular(sd, rnd.uniform(0, math.tau))
    petiole = at + (out + UP * 0.7).normalized() * rnd.uniform(0.02, 0.04)
    ww.stalk(sheets["StalkMinor"], [tuple(at), tuple(petiole)], 0.0012, 0.001, t_range=(0.5, 0.8))
    trefoil(petiole, rnd.uniform(0.028, 0.038), 0.15, seed=300 + i)
    if i >= 28:
        # A small closed bud
        pompom("Bud", top + axis * 0.008, axis, 0.0075, 10, 0.005, 0.004, core_sheet=sheets["Bud"],
                  cutoff=-0.2, lean_up=0.6, seed=100 + i, core_length=0.016)
        continue
    kind = "Spent" if i in (25, 26) else ("Rose" if rnd.random() < 0.4 else "Magenta")
    core = rnd.uniform(0.012, 0.014)
    pompom(kind, top + axis * core, axis, core, 24, core * 0.45, 0.0068, core_sheet=sheets[kind],
              cutoff=-0.45, lean_up=0.75, seed=i, core_length=core * 2.2, t_range=(0.4, 1.0))
    if i % 2 == 0:
        # The trefoil that sits right under the head on the real plant
        trefoil(top - axis * 0.004, rnd.uniform(0.02, 0.026), 0.25, seed=500 + i)

pieces = ww.build(sheets.values())
built = {o.name: o for o in pieces}
kl.tag([built["CloverLeaf"], built["CloverStalkMinor"]], kl.NEAR)
for kind, v0, v1, c in heads_at:
    kl.tag_verts(built["Clover" + kind], v0, v1, 1.15, c)
for kind in ("Magenta", "Rose", "Spent", "Bud"):
    if "Clover" + kind not in built:
        continue
    obj = built["Clover" + kind]
    u = obj.data.attributes["u"].data
    florets = [0]

    def every_other(poly, u=u, florets=florets):
        # A floret is one triangle with its base corners at u = -1 and 1; the head's core ball is all u = 0
        if any(abs(u[i].value) > 0.5 for i in poly.vertices):
            florets[0] += 1
            return kl.NEAR if florets[0] % 2 == 0 else kl.BOTH
        return kl.BOTH
    kl.tag_faces(obj, every_other)
for k, (x, y) in enumerate(nk.scatter(4, 0.36, seed=7, min_gap=0.2)):
    pieces += kl.tag(nk.tuft("Grass%d_" % k, (x, y), 6, 0.22, grass, seed=k), kl.NEAR)

model = kl.export(NAME, pieces, MODELS, size=512)
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.12, distance=1.1)
kl.lod_preview(SCRIPT, NAME, PREVIEWS, focus_height=G + 0.12, distance=1.1)
print("[%s] done" % SCRIPT)
