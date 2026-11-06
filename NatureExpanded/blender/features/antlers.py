"""Antlers (forest): a shed deer antler and the smaller other half of the pair lying in the leaf litter, bleached white on top,
brown and stained below, gnawed by mice and squirrels (the burr and the tine tips chewed down, fine parallel tooth marks),
half under the leaves. Walk-through (Collide melee, kind bone) with one box each so a pick finds them.

    blender -b --factory-startup --python antlers.py -- <features folder> <preview folder> [Name ...]
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import kit_forest as kf  # noqa: E402
import kit_shrub as ks  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import singleskit as sk  # noqa: E402
import zkit as tk  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
ONLY = sys.argv[sys.argv.index("--") + 3:]


# ---------------------------------------------------------------- materials

def _cyl(g, k, s, off=0.0):
    """A seamless coordinate round the antler's axis: (cos, sin) of the angle at radius k, the length t times s."""
    ang = ks._attr(g, "ang")
    t = ks._attr(g, "t")
    th = g.math("MULTIPLY", ang, math.tau)
    vec = g.node("ShaderNodeCombineXYZ")
    g.links.new(g.math("ADD", g.math("MULTIPLY", g.math("COSINE", th), k), off), vec.inputs[0])
    g.links.new(g.math("ADD", g.math("MULTIPLY", g.math("SINE", th), k), off * 0.7), vec.inputs[1])
    g.links.new(g.math("MULTIPLY", t, s), vec.inputs[2])
    return vec.outputs[0]


def antler_mat(name, bleach=1.0, brown=1.0, algae=0.5, gnaw=1.0, seed=0.0, relief=0.0016):
    mat, g = tk.new_material(name)
    co = g.coords()
    z = g.separate(co)[2]
    t = ks._attr(g, "t")
    nz = ks._normal_z(g)
    cs = _cyl(g, 2.3, 1.3, seed)
    groove_n = g.noise(1.0, detail=4.0, roughness=0.6, vector=cs)
    groove = g.ramp(kf._ridged(g, groove_n), 0.74, 0.97)
    fibre = g.noise(1.0, detail=3.0, vector=_cyl(g, 13.0, 26.0, seed))
    up = g.ramp(nz, -0.55, 0.55)                       # up-facing: sun-bleached; down: brown, stained by the litter
    tone = g.noise(2.6, detail=4.0, vector=cs)
    top_c = g.mix(g.ramp(tone, 0.3, 0.7), (0.28, 0.235, 0.17), (0.46, 0.4, 0.31))
    low_c = g.mix(g.ramp(tone, 0.3, 0.7), (0.085, 0.058, 0.035), (0.17, 0.115, 0.07))
    col = g.mix(g.math("MULTIPLY", up, bleach), low_c, top_c)
    # Grooves: dark lines along the length, branching
    col = g.mix(g.math("MULTIPLY", groove, 0.6), col, g.mix(up, (0.035, 0.024, 0.015), (0.1, 0.085, 0.065)))
    col = g.mix(g.math("MULTIPLY", g.ramp(fibre, 0.5, 0.8), 0.07), col, (0.08, 0.06, 0.04))
    tan = g.math("MULTIPLY", g.ramp(g.noise(3.2, detail=4.0, vector=cs), 0.45, 0.66), 0.7)
    col = g.mix(tan, col, (0.2, 0.125, 0.07))
    # Exfoliating chalky skin: flakes off to the darker bone beneath
    flake = g.ramp(g.math("ADD", g.noise(1.0, detail=5.0, vector=_cyl(g, 5.0, 6.0, seed + 3.0)),
                          g.math("MULTIPLY", g.math("SUBTRACT", g.noise(70.0, detail=3.0), 0.5), 0.3)), 0.6, 0.66)
    col = g.mix(g.math("MULTIPLY", flake, g.math("MULTIPLY", up, 0.8)), col, (0.1, 0.07, 0.045))
    # Hairline checks along the grain, with cross splits
    ce = kf._voronoi(g, 1.0, kf._warped(g, 18.0, 0.003, _cyl(g, 7.0, 9.0, seed + 5.0)), feature="DISTANCE_TO_EDGE")
    check = g.math("MULTIPLY", g.ramp(ce, 0.03, 0.0), g.ramp(g.noise(5.0, detail=3.0), 0.35, 0.58))
    col = g.mix(g.math("MULTIPLY", check, 0.85), col, (0.018, 0.013, 0.009))
    # Pores
    pc, pr = kf._cells(g, 230.0, kf._warped(g, 20.0, 0.004))
    pores = g.math("MULTIPLY", g.ramp(pc, 0.22, 0.07), g.ramp(g.noise(10.0, detail=3.0), 0.4, 0.62))
    col = g.mix(g.math("MULTIPLY", pores, 0.6), col, (0.03, 0.022, 0.014))
    # Algae film and a few lichen crusts on the sunny side
    al = g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(g.noise(6.0, detail=5.0, distortion=0.3), 0.52, 0.7), g.ramp(nz, 0.0, 0.7)), algae)
    mcol, mh, mrough, _ = kf.moss_layer(g, 0.9)
    col = g.mix(g.math("MULTIPLY", al, 0.75), col, tk.grade(g, mcol, sat=0.7, value=0.9))
    lc, lr = kf._cells(g, 80.0, kf._warped(g, 8.0, 0.01))
    lich = g.math("MULTIPLY", g.ramp(lc, 0.5, 0.3), g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=4.0), 0.58, 0.7), g.ramp(nz, 0.1, 0.8)))
    col = g.mix(g.math("MULTIPLY", lich, 0.8), col, g.mix(g.ramp(lr, 0.4, 0.9), (0.2, 0.22, 0.15), (0.34, 0.3, 0.1)))
    # Rodent work at both ends: fresh pale bone, rows of fine parallel tooth marks
    zone = g.math("MAXIMUM", g.ramp(t, 0.22, 0.04), g.ramp(t, 0.8, 0.97))
    patch = g.ramp(g.noise(8.0, detail=4.0, distortion=0.3, vector=cs), 0.38, 0.55)
    gz = g.math("MULTIPLY", g.math("MULTIPLY", zone, patch), gnaw)
    bands = g.math("ADD", g.math("MULTIPLY", t, 340.0), g.math("MULTIPLY", g.math("SUBTRACT", g.noise(20.0, detail=3.0, vector=cs), 0.5), 5.0))
    tooth = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", bands), 0.5)), 0.5, 0.3)
    tooth = g.math("MULTIPLY", tooth, g.ramp(g.noise(60.0, detail=2.0), 0.15, 0.4))
    fresh = g.mix(g.ramp(g.noise(30.0, detail=4.0), 0.3, 0.7), (0.4, 0.37, 0.3), (0.52, 0.49, 0.41))
    col = g.mix(g.math("MULTIPLY", gz, 0.9), col, fresh)
    col = g.mix(g.math("MULTIPLY", g.math("MULTIPLY", gz, tooth), 0.75), col, (0.09, 0.07, 0.05))
    # Dirt: soil dust on the lower parts, splashes
    soilm = g.math("MULTIPLY", g.ramp(z, G + 0.05, G - 0.01), g.ramp(g.noise(24.0, detail=5.0), 0.2, 0.55))
    col = g.mix(g.math("MULTIPLY", soilm, 0.9), col, g.mix(g.ramp(g.noise(110.0), 0.3, 0.7), (0.035, 0.026, 0.017), (0.07, 0.05, 0.033)))
    height = g.math("SUBTRACT", g.math("ADD", g.math("MULTIPLY", fibre, 0.12), g.math("MULTIPLY", g.math("SUBTRACT", 1.0, groove), 0.5)),
                    g.math("ADD", g.math("MULTIPLY", check, 0.8), g.math("ADD", g.math("MULTIPLY", pores, 0.5), g.math("MULTIPLY", g.math("MULTIPLY", gz, tooth), 0.9))))
    height = g.mixf(al, height, g.math("ADD", 0.4, g.math("MULTIPLY", mh, 0.5)))
    rough = g.mixf(al, g.mixf(flake, 0.82, 0.9), mrough)
    return tk.finish(mat, g, grade_(g, col), 0.0, rough, g.bump(height, 1.0, relief))


def grade_(g, col):
    return tk.grade(g, col, sat=0.95, value=0.95)


def core_mat(name):
    """The spongy cut bone at a chewed base or tine tip: cream, honeycombed with dark pits."""
    mat, g = tk.new_material(name)
    d1, r1 = kf._cells(g, 190.0, kf._warped(g, 25.0, 0.003))
    d2, r2 = kf._cells(g, 60.0)
    col = g.mix(g.ramp(g.noise(12.0, detail=4.0), 0.3, 0.7), (0.34, 0.31, 0.25), (0.5, 0.46, 0.38))
    col = g.mix(g.math("MULTIPLY", g.ramp(d1, 0.5, 0.15), 0.8), col, (0.06, 0.045, 0.03))
    col = g.mix(g.math("MULTIPLY", g.ramp(d2, 0.4, 0.1), 0.35), col, (0.12, 0.09, 0.06))
    height = g.math("ADD", g.ramp(d1, 0.1, 0.5), g.math("MULTIPLY", g.ramp(d2, 0.1, 0.4), 0.4))
    return tk.finish(mat, g, grade_(g, col), 0.0, 0.88, g.bump(height, 1.0, 0.003))


def cone_mat(name):
    mat, g = tk.new_material(name)
    t = ks._attr(g, "t")
    d1, r1 = kf._cells(g, 90.0)
    col = g.mix(g.ramp(r1, 0.0, 1.0), (0.05, 0.034, 0.02), (0.13, 0.09, 0.055))
    col = g.mix(g.math("MULTIPLY", g.ramp(d1, 0.1, 0.5), 0.6), col, (0.015, 0.011, 0.008))
    col = g.mix(g.ramp(t, 0.0, 0.5), tuple(c * 0.6 for c in (0.1, 0.07, 0.04)), col)
    return tk.finish(mat, g, grade_(g, col), 0.0, 0.85, g.bump(g.ramp(d1, 0.5, 0.1), 1.0, 0.003))


# ---------------------------------------------------------------- geometry

def catmull(pts, n):
    out = []
    m = len(pts) - 1
    for i in range(n + 1):
        out.append(lk._catmull([Vector(p) for p in pts], i / n * m))
    return out


def stations(pts, spacing=0.03, fine=0.012, fine_len=0.07):
    """Resample a polyline: dense at the two ends (the chewed parts), `spacing` between."""
    pts = [Vector(p) for p in pts]
    dense = catmull(pts, 120)
    cum = [0.0]
    for i in range(1, len(dense)):
        cum.append(cum[-1] + (dense[i] - dense[i - 1]).length)
    total = cum[-1]
    s_list = [0.0]
    s = 0.0
    while s < total - 1e-4:
        step = fine if (s < fine_len or total - s < fine_len) else spacing
        s = min(total, s + step)
        s_list.append(s)
    out = []
    j = 0
    for s in s_list:
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        f = (s - cum[j]) / max(1e-9, cum[j + 1] - cum[j])
        out.append(dense[j].lerp(dense[j + 1], f))
    return out, total


def angdiff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def antler(b, mat, core, rnd, T, spec):
    """One shed antler built in its own frame (u along the head, v up the beam, w outward) and placed by T(p). Returns the
    world points it touches (for the collider)."""
    touched = []
    L = spec.get("scale", 1.0)
    ctrl = [Vector(p) * L for p in spec["beam"]]
    pts, total = stations(ctrl, spacing=0.034 * L)
    n = len(pts)
    bite_a = spec.get("bite", 1.2)
    chew = spec.get("chew", 1.0)
    cut = spec.get("cut", 1.0)             # fraction of the beam kept (a snapped end)

    def r_at(f):
        r = spec["r0"] * L * (1.0 - 0.7 * f ** 1.25) + 0.0045 * L
        r += 0.011 * L * math.exp(-(f / 0.028) ** 2)             # the burr (coronet)
        return r

    fs = []
    acc = 0.0
    for i in range(n):
        if i:
            acc += (pts[i] - pts[i - 1]).length
        fs.append(acc / total)
    keep = [i for i, f in enumerate(fs) if f <= cut]
    pts = [pts[i] for i in keep]
    fs = [fs[i] for i in keep]
    radii = [r_at(f / max(cut, 1e-6) * cut) for f in fs]
    ph = rnd.uniform(0, 6.28)

    def mod(i, a, s):
        f = fs[i]
        m = 1.0
        if f < 0.16:
            pearl = max(0.0, math.sin(a * 11.0 + 2.5 * sk.fbm((a, f * 20, 0.3), 1.0) + ph)) ** 1.5
            m += (0.16 * pearl + 0.05 * math.sin(a * 5.0)) * (1.0 - f / 0.16)
        m += 0.05 * sk.fbm((math.cos(a) * 2, math.sin(a) * 2, f * 9), 2.0)
        # gnawed bite on one side of the base
        if f < 0.24:
            m -= 0.5 * chew * math.exp(-(angdiff(a, bite_a) / 0.75) ** 2) * (1.0 - f / 0.24) ** 1.3 * (0.75 + 0.25 * math.sin(f * 90 + a * 3))
        return m

    def shift0(a):
        step = 0.012 * L * chew
        q = math.floor((math.sin(a * 2.0 + 0.4) * 0.5 + 0.5) * 3.99)
        return (q * step + 0.014 * L * chew * max(0.0, math.cos(angdiff(a, bite_a)))) if chew > 0 else 0.0

    sk.sweep(b, mat, pts, radii, sides=14, mod=mod, cap_start=True, cap_end=True, end_mat=core, shift0=shift0, aspect=[0.92] * len(pts))
    for p in pts:
        touched.append(T(p))
    # Tines: base fraction, direction (u, v, w), length, radius, chewed?
    for tn in spec["tines"]:
        f0, d, ln, r0 = tn["f"], Vector(tn["dir"]).normalized(), tn["len"] * L, tn["r"] * L
        if f0 > cut:
            continue
        k = int(f0 * (len(pts) - 1) / max(cut, 1e-6))
        k = max(0, min(len(pts) - 2, k))
        base = pts[k] - d * 0.006
        bow = Vector(tn.get("bow", (0.25, 0.0, 0.0)))
        tp = [base + d * (ln * q / 6) + bow * (ln * (q / 6) ** 2) for q in range(7)]
        rr = [max(0.0013 * L, r0 * (1.0 - (q / 6)) ** 0.8 * (1.0 if q else 1.15)) for q in range(7)]
        if tn.get("chewed"):
            rr[-1] = max(rr[-1], r0 * 0.28)

        def shift1(a, tn=tn, ln=ln):
            return -0.006 * L * (0.5 + 0.5 * math.sin(a * 3.0 + 1.0)) * (1.0 if tn.get("chewed") else 0.0)

        def tmod(i, a, s, tn=tn):
            m = 1.0 + 0.06 * sk.fbm((math.cos(a) * 3, math.sin(a) * 3, i * 0.7), 5.0)
            if tn.get("chewed") and s > 0.62:
                m -= 0.22 * (0.5 + 0.5 * math.sin(a * 2.0 + 2.0)) * (s - 0.62) / 0.38
            return m
        sk.sweep(b, mat, tp, rr, sides=8, mod=tmod, cap_start=False, cap_end=True, end_mat=core if tn.get("chewed") else None,
                 shift1=shift1 if tn.get("chewed") else None)
        for p in tp:
            touched.append(T(p))
    return touched


BEAM = [(0.0, 0.0, 0.0), (0.02, 0.07, 0.012), (0.055, 0.16, 0.03), (0.12, 0.25, 0.048), (0.22, 0.32, 0.055), (0.34, 0.36, 0.05),
        (0.46, 0.37, 0.04), (0.56, 0.355, 0.03)]
TINES = [dict(f=0.13, dir=(0.85, 0.5, 0.15), len=0.115, r=0.0105, chewed=True, bow=(0.0, 0.3, 0.0)),
         dict(f=0.34, dir=(0.1, 1.0, 0.08), len=0.2, r=0.0115),
         dict(f=0.58, dir=(0.05, 1.0, 0.04), len=0.165, r=0.011),
         dict(f=0.79, dir=(0.0, 1.0, 0.0), len=0.1, r=0.009, chewed=True)]


def frame(phi, psi):
    return Matrix.Rotation(math.radians(psi), 3, "Z") @ Matrix.Rotation(math.radians(phi), 3, "X")


def build(name):
    nk.reset()
    rnd = random.Random(sum(map(ord, name)) * 11 + 5)
    ant_a = antler_mat("AntlerA", bleach=1.0, algae=0.55, gnaw=1.0, seed=1.0)
    ant_b = antler_mat("AntlerB", bleach=0.55, algae=1.0, gnaw=0.7, seed=4.0)
    core = core_mat("AntlerCore")
    soil = sk.soil_small("AntSoil", moss=0.2, stony=0.7)
    bed = sk.litter_bed("AntBed")
    lits = sk.litter_mats("AnLf")
    gm = nk.plant("AnGrass", (0.09, 0.16, 0.04), (0.14, 0.2, 0.05), rough=0.7, vary=0.3)
    gd = nk.plant("AnGrassDry", (0.26, 0.2, 0.09), (0.18, 0.13, 0.06), rough=0.8, vary=0.25)
    cone = cone_mat("AnCone")
    fern_mat = nk.plant("AnFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    twig = ks.bark("AnTwig", (0.1, 0.075, 0.05), (0.05, 0.04, 0.03), rough=0.9)
    b = ks.Builder(name)

    # Main antler: its flat side down, tilted up on the tines
    spec_a = dict(beam=BEAM, tines=TINES, r0=0.021, scale=1.0, bite=1.3, chew=1.0)
    Ra = frame(27.0, 8.0)
    pts_local = [Vector(p) for p in BEAM]
    for t_ in TINES:
        pts_local.append(Vector(BEAM[3]) + Vector(t_["dir"]).normalized() * t_["len"])
    wa = [Ra @ p for p in pts_local]
    za = min(p.z for p in wa)
    cx = (min(p.x for p in wa) + max(p.x for p in wa)) / 2
    oa = Vector((-0.04 - cx, -0.12 - (min(p.y for p in wa) + max(p.y for p in wa)) / 2, G - 0.012 - za + 0.0))
    Ta = lambda p: oa + Ra @ Vector(p)
    mound = sk.mound(b, bed, (0.0, 0.0), 0.5, rnd, dome=0.03, sides=26, rings=4, sink=0.05, jitter=0.2, lump=0.008)

    # Build with transformed points: sweep takes world points, so transform the control polylines first
    # (antler() works in whatever frame the control points are in: give it world points)
    def world_antler(mat, spec, R, o):
        sc = spec.get("scale", 1.0)
        beam = [o + R @ (Vector(p) * sc) for p in spec["beam"]]
        tines = []
        for tn in spec["tines"]:
            t2 = dict(tn)
            t2["dir"] = tuple((R @ Vector(tn["dir"]).normalized()))
            if "bow" in tn:
                t2["bow"] = tuple(R @ Vector(tn["bow"]))
            else:
                t2["bow"] = tuple(R @ Vector((0.25, 0.0, 0.0)))
            tines.append(t2)
        s2 = dict(spec, beam=beam, tines=tines, scale=1.0)
        # radii and lengths scale with the antler: bake the scale into them
        s2["r0"] = spec["r0"] * sc
        for t2 in s2["tines"]:
            t2["len"] *= sc
            t2["r"] *= sc
        return antler(b, mat, core, rnd, lambda p: p, s2)

    ta = world_antler(ant_a, spec_a, Ra, oa)

    # The other shed: smaller, older, half under the leaves, one tine and the beam's tip broken off
    spec_b = dict(beam=BEAM, tines=[dict(t_) for t_ in TINES[:3]], r0=0.02, scale=0.78, bite=-1.7, chew=0.8, cut=0.82)
    Rb = frame(10.0, -63.0)
    pl = [Rb @ (Vector(p) * 0.78) for p in BEAM]
    ob = Vector((0.1 - (min(p.x for p in pl) + max(p.x for p in pl)) / 2, 0.2 - (min(p.y for p in pl) + max(p.y for p in pl)) / 2,
                 G - 0.0 - min(p.z for p in pl) - 0.02))
    tb = world_antler(ant_b, spec_b, Rb, ob)

    # Litter over everything: a settled layer, then loose leaves lying across the antlers' ends
    lim = 0.39
    sk.litter(b, lits, 120, rnd, (-lim, lim, -lim, lim), size=(0.045, 0.085), rows=4, ground=mound)
    sk.litter(b, lits, 26, rnd, (-lim, lim, -lim, lim), size=(0.05, 0.085), rows=4, lift=0.05, ground=mound)
    for (px, py) in ((ob.x - 0.05, ob.y - 0.03), (oa.x + 0.02, oa.y + 0.0)):
        sk.litter(b, lits, 8, rnd, (px - 0.12, px + 0.12, py - 0.1, py + 0.1), size=(0.05, 0.08), rows=4, lift=0.03, ground=mound)
    sk.twigs(b, twig, 5, rnd, (-lim, lim, -lim, lim), length=(0.1, 0.28), z=G + 0.01)
    # Pine cones
    for (cx_, cy_, ca) in ((0.36, -0.18, 20.0), (-0.38, 0.33, 120.0)):
        base = Vector((cx_, cy_, G + 0.016))
        d = Vector((math.cos(math.radians(ca)), math.sin(math.radians(ca)), 0.12)).normalized()
        pts = [base + d * (0.07 * q / 7) for q in range(8)]
        rr = [0.004 + 0.019 * math.sin(math.pi * (0.12 + 0.88 * q / 7)) ** 0.8 for q in range(8)]
        sk.sweep(b, cone, pts, rr, sides=10, mod=lambda i, a, s: 1.0 + 0.2 * max(0.0, math.sin(a * 5.0 + i * 1.9)) ** 1.3,
                 cap_start=True, cap_end=True)
    # Grass, a fern
    for (gx, gy, n) in ((-0.38, -0.34, 10), (0.36, 0.36, 12), (0.4, -0.38, 6), (-0.42, 0.05, 6)):
        sk.grass(b, gm, gx, gy, rnd, blades=n, height=(0.15, 0.4), spread=0.05, lean=0.75, z=mound(gx, gy), dry=gd, dry_share=0.5,
                 bound=(-0.5, 0.5, -0.5, 0.5))
    ks.fern(b, fern_mat, (0.3, 0.1, G), rnd, fronds=5, length=(0.2, 0.3), pinnae=11, pinna_len=0.055, pinna_w=0.016, away=100, arc=150,
            tilt=(25.0, 55.0), bend=(0.4, 0.8))

    # Colliders: a box over each antler
    extra = []
    for tp, h in ((ta, 0.1), (tb, 0.07)):
        xs, ys = [p.x for p in tp], [p.y for p in tp]
        cx_, cy_ = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        extra.append("box %.3f %.3f %.3f %.3f %.3f %.3f" % (cx_, cy_, G + h / 2 - 0.02, max(xs) - min(xs), max(ys) - min(ys), h + 0.04))
    density = {"AntlerA": 1.6, "AntlerB": 1.2, "AntlerCore": 0.35, "AntSoil": 0.5, "AntBed": 0.6, "AnLf": 0.4, "AnGrass": 0.3, "AnGrassDry": 0.3,
               "AnCone": 0.5, "AnFern": 0.3, "AnTwig": 0.2}
    model = sk.finish_export(name, b, [], FEATURES, 1024, density, extra=extra, coarse=0.5)
    ex, ey, top = sk.bounds_report(name, model)
    shots = sk.standard_shots(top + 0.05, reach=0.3)
    shots.append(("antlerA", Vector((oa.x + 0.1, oa.y - 0.45, G + 0.4)), Vector((oa.x, oa.y, G + 0.05)), 40))
    shots.append(("base", Vector((oa.x - 0.35, oa.y - 0.1, G + 0.22)), Vector((oa.x - 0.2, oa.y + 0.1, G + 0.05)), 40))
    sk.preview(name, model, shots, PREVIEWS)
    print("[%s] done" % name)


for n in (ONLY or ["Antlers"]):
    build(n)
