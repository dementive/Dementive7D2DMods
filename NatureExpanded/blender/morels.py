"""Morels (burnt forest, food): seven morels 4 to 11 cm tall coming up through the ash of a burn, the way they do the
spring after a fire. Tall honeycomb caps, deep pits between ridges drawn out lengthways: four dark "black morels"
(near-black ridges, paler grey-brown pits, pointed) and three tan ones (rounder, pale ridges round deep yellow-brown
pits), on short, thick, pale, mealy stems. Grey ash patches, charcoal crumbs, burnt needles and a charred twig with
crazed black bark.

    blender -b --factory-startup --python morels.py -- <unity models folder> <preview folder>
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naturekit as nk  # noqa: E402
import kit_forest as kf  # noqa: E402

NAME, SCRIPT = "Morels", "morels"
args = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS = args[0], args[1]
os.makedirs(PREVIEWS, exist_ok=True)

nk.reset()
rnd = random.Random(31)
G = nk.GROUND

tan = kf.honeycomb("MorelTan", ridge=(0.52, 0.4, 0.23), pit=(0.3, 0.2, 0.09), deep=(0.1, 0.06, 0.025), scale=150.0,
                   stretch=0.42)
dark = kf.honeycomb("MorelDark", ridge=(0.045, 0.032, 0.02), pit=(0.21, 0.135, 0.07), deep=(0.085, 0.052, 0.026),
                    scale=150.0, stretch=0.42)
# Mealy and finely furrowed lengthways, grubby with ash at the foot
stem_mat = kf.fungus("MorelStem", (0.3, 0.26, 0.19), (0.66, 0.58, 0.44), rough=0.9, vary=0.45, scale=200.0, bump=0.6,
                     ramp=(0.0, 0.45), streaks=0.3)
ash_mat = kf.ash("Ash", light=(0.33, 0.32, 0.3), dark=(0.11, 0.105, 0.1))
char_mat = kf.char("Char")
burnt = kf.litter_material("BurntNeedles", (0.02, 0.018, 0.016), (0.07, 0.05, 0.04), spots=0.0)

pieces = []
keep = []


def morel(i, x, y, Hc, Rc, L, mat, pointed):
    ax = Vector((x * 0.15 + rnd.uniform(-0.08, 0.08), y * 0.15 + rnd.uniform(-0.08, 0.08), 1.0)).normalized()
    base = Vector((x, y, G))
    sr = Rc * 0.72
    keep.append((x, y, sr * 1.3 + 0.01))
    stem = [(0.0, -0.004), (sr * 1.25, -0.002), (sr * 1.3, L * 0.15), (sr * 1.05, L * 0.5), (sr * 0.95, L * 0.85),
            (sr * 0.92, L + 0.004)]
    pieces.append(kf.revolve("Stem%d" % i, stem, base, ax, stem_mat, segments=10,
                             t=[max(0.0, h) / L for _, h in stem]))
    # The cap grows from the stem's top (its margin fused to it), swelling out and narrowing to the tip
    tipr = 0.28 if pointed else 0.45
    cap = [(sr * 0.9, 0.002), (Rc * 0.9, -0.002), (Rc, 0.12 * Hc), (Rc * 0.98, 0.35 * Hc), (Rc * 0.88, 0.58 * Hc),
           (Rc * (0.62 if pointed else 0.7), 0.8 * Hc), (Rc * tipr, 0.94 * Hc), (0.0, Hc)]
    ph = [rnd.uniform(0.0, math.tau) for _ in range(3)]

    def wob(k, a):
        if k < 2:
            return 1.0, 0.0
        # Lumpy, with a hint of the vertical ribs morels have
        return (1.0 + 0.06 * math.sin(3 * a + ph[0] + k * 0.6) + 0.04 * math.sin(5 * a + ph[1] - k * 0.4)
                + 0.035 * math.sin(7 * a + ph[2])), 0.0

    pieces.append(kf.revolve("Cap%d" % i, cap, base + ax * L, ax, mat, segments=14, t=[h / Hc for _, h in cap],
                             wobble=wob, away=base + ax * (L - Hc)))


# (x, y, cap height, cap radius, stem length, dark?)
for i, (x, y, Hc, Rc, L, is_dark) in enumerate((
        (-0.1, 0.06, 0.075, 0.024, 0.035, True),
        (0.04, 0.13, 0.06, 0.02, 0.03, True),
        (0.13, -0.02, 0.07, 0.025, 0.032, False),
        (-0.02, -0.09, 0.05, 0.018, 0.025, True),
        (-0.21, -0.08, 0.045, 0.017, 0.022, False),
        (0.23, 0.13, 0.042, 0.015, 0.02, True),
        (0.01, 0.025, 0.035, 0.013, 0.018, False))):
    morel(i, x, y, Hc, Rc, L, dark if is_dark else tan, is_dark)

# The burn: ash, charcoal crumbs, burnt needles and a charred twig
for k, (x, y, r, lift) in enumerate(((0.0, 0.02, 0.22, 0.003), (-0.22, -0.15, 0.13, 0.0045), (0.24, 0.07, 0.14, 0.006))):
    pieces.append(kf.patch("Ash%d" % k, (x, y), r, ash_mat, seed=k, lift=lift))
for k in range(9):
    a = rnd.uniform(0.0, math.tau)
    r = rnd.uniform(0.08, 0.36)
    x, y = r * math.cos(a), r * math.sin(a)
    if any((x - kx) ** 2 + (y - ky) ** 2 < kr * kr for kx, ky, kr in keep):
        continue
    s = rnd.uniform(0.6, 1.3)
    ph = rnd.uniform(0.0, math.tau)
    pieces.append(kf.revolve("Crumb%d" % k, [(0.0, 0.011 * s), (0.011 * s, 0.006 * s), (0.012 * s, 0.0),
                                             (0.0, -0.003)], (x, y, G + 0.002), (0, 0, 1), char_mat, segments=5,
                             wobble=lambda i, a, p=ph: (1.0 + 0.3 * math.sin(2 * a + p) + 0.15 * math.sin(3 * a), 0.0)))
pieces.append(kf.needles("Needles", 45, 0.42, burnt, seed=7, keep_out=keep))
twig = [Vector(p) for p in ((-0.36, 0.26, G + 0.011), (-0.21, 0.31, G + 0.014), (-0.05, 0.33, G + 0.013),
                            (0.1, 0.38, G + 0.01))]
end0 = twig[0] + (twig[0] - twig[1]).normalized() * 0.004
end1 = twig[-1] + (twig[-1] - twig[-2]).normalized() * 0.004
pieces.append(kf.taper_tube("Twig", [end0] + twig + [end1], [0.0, 0.012, 0.011, 0.009, 0.007, 0.0], char_mat,
                            sides=6))
pieces.append(kf.taper_tube("TwigFork", [twig[1], (-0.11, 0.22, G + 0.008), (-0.03, 0.17, G + 0.006),
                                         (-0.025, 0.166, G + 0.006)], [0.006, 0.0045, 0.0035, 0.0], char_mat, sides=5))

kf.report(SCRIPT, pieces)
# The atlas goes mostly to the caps, seen up close; the ash patches are big but plain
model = nk.export(NAME, pieces, MODELS, size=1024, density={"MorelTan": 1.6, "MorelDark": 1.6, "MorelStem": 1.2,
                                                            "Ash": 0.45, "BurntNeedles": 0.5})
nk.previews(SCRIPT, model, PREVIEWS, focus_height=G + 0.05, distance=0.85)
print("[%s] done" % SCRIPT)
