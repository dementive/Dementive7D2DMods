"""WindfallFresh01, WindfallOld01, WindfallBurnt01, WindfallPair01 (pine forest and burnt forest): a big tree blown
over. The root plate stands up like a wall 4 m across, a tangle of roots packed with dirt and stones, moss, ferns and
a few mushrooms on it; the trunk leaves it at a slant and comes down to lie along the ground 11 to 13 m long, its
snapped limb stubs sticking up, bark peeling, moss on top, bracket fungus on the sides; a bay of dug-up soil in front
of the plate where the roots came out. Solid: the trunk (a chain of capsule colliders) is a ramp and a bridge a
player can walk along, the plate and the berms are voxel boxes.

    blender -b --factory-startup --python windfall.py -- <features folder> <preview folder> [Name ...]

The model lies along the x axis (plate at -x, crown at +x) and its footprint is a rectangle: the block is rotated in
quarter turns by the game. Environment: LK_SIZE overrides the atlas size (512 for a quick geometry check).
"""
import math
import os
import random
import sys
from types import SimpleNamespace

import bmesh
from mathutils import Matrix, Vector
from mathutils import noise as mn
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import featurekit as fk  # noqa: E402
import logkit as lk  # noqa: E402
import naturekit as nk  # noqa: E402
import kit_shrub as ks  # noqa: E402

G = fk.G
FEATURES, PREVIEWS = fk.args()
lk.set_preview_dir(PREVIEWS)
ONLY = lk.only()

# name: dict. L trunk length, rb/rt butt and tip radius, plate (half width, half height), theta slant of the trunk at the
# plate (degrees), sink = how far the trunk lies sunk into the ground (fraction of its radius), moss amount, crown
# foliage, stubs
SPECS = {
    "WindfallFresh01": dict(style="fresh", L=13.0, rb=0.7, rt=0.06, plate=(2.25, 1.8), theta=13.0, sink=0.15, moss=0.0, peel=0.78,
                            crown=4.4, stub_len=(0.25, 0.9), fungus=1, seed=3),
    "WindfallOld01": dict(style="forest", L=11.0, rb=0.76, rt=0.24, plate=(2.0, 1.55), theta=10.0, sink=0.38, moss=0.85, peel=0.58,
                          crown=0.0, stub_len=(0.1, 0.5), fungus=3, seed=5),
    "WindfallBurnt01": dict(style="burnt", L=12.0, rb=0.72, rt=0.22, plate=(2.1, 1.7), theta=12.0, sink=0.2, moss=0.0, peel=0.7,
                            crown=0.0, stub_len=(0.2, 1.3), fungus=0, seed=7),
    "WindfallPair01": dict(style="forest", L=11.0, rb=0.7, rt=0.22, plate=(2.0, 1.6), theta=12.0, sink=0.25, moss=0.6, peel=0.62,
                           crown=0.0, stub_len=(0.15, 0.7), fungus=2, seed=9, pair=True),
}


def mats_for(spec):
    st = spec["style"]
    m = SimpleNamespace()
    burnt = st == "burnt"
    kw = dict(style=st, moss=spec["moss"], bs=0.42, peel=spec["peel"])
    m.bark = lk.bark_mat("WfBark", **kw)
    m.under = lk.bark_mat("WfBarkUnder", **dict(kw, moss=0.0))
    m.moss = None if (burnt or spec["moss"] <= 0.0) else lk.moss_shell_mat("WfMoss", **kw)
    m.end = lk.end_grain("WfEnd", "burnt" if burnt else "fresh", 0.012)
    m.rot = lk.end_grain("WfRot", "burnt" if burnt else "rot", 0.012)
    sm = 0.0 if burnt else 0.35 + 0.2 * spec["moss"]
    m.soil = lk.soil_mat("WfSoil", moss=sm, rooty=1.0, dark=0.5 if burnt else 1.0)
    m.skirt = lk.soil_mat("WfSkirt", moss=0.0, rooty=0.0, dark=0.5 if burnt else 1.0)
    m.soil_moss = None if burnt else lk.soil_moss_mat("WfSoilMoss", moss=sm, rooty=1.0)
    m.root = lk.root_mat("WfRoot", "fresh" if st == "fresh" else "forest")
    m.stone = fk.granite("WfStone", moss=0.0 if burnt else 0.4, lichen=0.0 if burnt else 1.0, stain=1.6 if burnt else 1.0,
                         tint=(0.62, 0.6, 0.58) if burnt else (1.0, 1.0, 1.0))
    m.stone_skirt = fk.granite("WfStoneSkirt", moss=0.0, lichen=0.0)
    m.fern = nk.plant("WfFern", (0.1, 0.2, 0.045), (0.15, 0.23, 0.06), rough=0.6, vary=0.3)
    m.needle = nk.plant("WfNeedle", (0.05, 0.105, 0.034), (0.085, 0.15, 0.045), rough=0.7, vary=0.3)
    m.dead = nk.plant("WfNeedleDead", (0.13, 0.07, 0.03), (0.09, 0.05, 0.025), rough=0.8, vary=0.3)
    m.litter = lk.litter_materials()
    if spec["fungus"]:
        m.cap, m.pores = lk.fungus_materials()
        m.mcap, m.mpores, m.mstem = lk.mushroom_materials()
    return m


class Plate:
    """The root plate: a soil lump (a flattened super-ellipsoid standing on edge, leaning with the trunk's slant),
    with a frame to lay roots over its face."""

    def __init__(self, b, m, rnd, cx, cy, yaw, half, theta, zc, seed, moss_amount):
        a, hb = half
        self.cx, self.cy, self.yaw, self.theta = cx, cy, yaw, theta
        self.a, self.hb = a, hb
        rot = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(theta), 3, "Y")
        self.ex = rot @ Vector((1.0, 0.0, 0.0))     # along the trunk (into the plate from the face)
        self.ey = rot @ Vector((0.0, 1.0, 0.0))     # across
        self.ez = rot @ Vector((0.0, 0.0, 1.0))     # up the plate
        self.n = -self.ex                            # out of the face
        self.c = Vector((cx, cy, zc))
        thick = 0.3 + 0.06 * a
        rk = dict(radii=(thick, a, hb), height=zc - G + hb, seed=seed, power=3.0, rough=0.14, yaw=yaw, at=(cx, cy),
                  tilt=(0.0, theta), subdiv=5, sink=3.0)
        planes = []
        for _ in range(5):
            ph_ = rnd.uniform(0, math.tau)
            rr_ = 1.0 / math.sqrt((math.cos(ph_) / a) ** 2 + (math.sin(ph_) / hb) ** 2)
            planes.append(((0.0, math.cos(ph_), math.sin(ph_)), rr_ * rnd.uniform(0.72, 0.9)))
        bm = fk.Rock(planes=planes, **rk).build()
        if m.soil_moss is not None:
            moss = (m.soil_moss, self._moss_depth(seed, moss_amount))
        else:
            moss = None
        self.body = fk.emit_rock(b, bm, m.soil, m.skirt, moss)
        bm.free()
        self.bvh = BVHTree.FromPolygons([tuple(v) for v in self.body[0]], self.body[1])

    def _moss_depth(self, seed, amount):
        def fn(p, nrm):
            up = nrm.z * 0.9
            q = Vector((p.x * 1.1 + seed * 3.0, p.y * 1.1, p.z * 1.1))
            patch = 0.5 + 0.9 * mn.noise(q) + 0.3 * mn.noise(q * 3.0)
            mask = (up + 0.18 + 0.4 * (amount - 0.3)) * patch
            d = max(0.0, min(1.0, (mask - 0.28) / 0.3))
            return d * (0.012 + 0.03 * max(0.0, 0.5 + 0.7 * mn.noise(q * 5.0)))
        return fn

    def point(self, u, v, lift=0.0):
        """The point on the plate's face at (u across, v up) from its center, lifted along the face's normal, and the
        surface normal there; None where the plate isn't."""
        o = self.c + self.ey * u + self.ez * v + self.n * 4.0
        loc, nor, idx, dist = self.bvh.ray_cast(o, -self.n)
        if loc is None:
            return None
        return loc + nor * lift, nor

    def world(self, u, v, w=0.0):
        return self.c + self.ey * u + self.ez * v + self.n * w


def roots(b, m, rnd, plate, burnt=False, count=15):
    """Tangled roots over the plate's face: big ones fanning out from the trunk's axis, curving over the surface,
    reaching past the rim as broken stumps and long trailing fibres, with laterals and fine rootlets."""
    ez, ey, n = plate.ez, plate.ey, plate.n

    def run(u, v, heading, length, r0, r1, wander, depth=0, floor_z=G + 0.04):
        pts, radii = [], []
        step = 0.17 if r0 > 0.05 else 0.12
        free = None
        steps = max(3, int(length / step))
        du, dv = math.cos(heading), math.sin(heading)
        for i in range(steps + 1):
            f = i / steps
            r = r0 + (r1 - r0) * f ** 0.85
            hit = plate.point(u, v, lift=r * 0.55) if free is None else None
            if hit is not None:
                pts.append(hit[0])
            else:
                if free is None:
                    free = pts[-1] if pts else plate.world(u, v, 0.1)
                    fd = (ey * du + ez * dv + n * 0.25).normalized()
                free = free + fd * step
                fd = (fd + Vector((0.0, 0.0, -0.22)) + Vector((rnd.gauss(0, 0.06), rnd.gauss(0, 0.06), rnd.gauss(0, 0.04)))).normalized()
                pts.append(free.copy())
            radii.append(r)
            heading += rnd.gauss(0.0, wander)
            du, dv = math.cos(heading), math.sin(heading)
            u += du * step
            v += dv * step
            if pts[-1].z < floor_z and i > 1:
                break
        radii = radii[:len(pts)]
        if len(pts) < 3:
            return None
        return pts, radii, heading

    made = []
    for i in range(count):
        h = i / count * math.tau + rnd.uniform(-0.2, 0.2)
        L = rnd.uniform(2.0, 3.6)
        r0 = rnd.uniform(0.07, 0.13)
        rr = run(math.cos(h) * 0.35, math.sin(h) * 0.35, h, L, r0, 0.02, 0.22)
        if rr is None:
            continue
        made.append((rr, r0, 0))
    for rr, r0, depth in list(made):
        pts, radii, heading = rr
        for j in range(rnd.randint(2, 5)):
            k = rnd.randint(2, max(2, len(pts) - 3))
            side = rnd.choice((-1.0, 1.0))
            # Pick the plate coordinates back from the point
            rel = pts[k] - plate.c
            u0, v0 = rel.dot(ey), rel.dot(ez)
            h2 = heading + side * rnd.uniform(0.5, 1.1)
            sub = run(u0, v0, h2, rnd.uniform(0.7, 1.9), radii[k] * 0.6, 0.012, 0.3)
            if sub is not None:
                made.append((sub, radii[k] * 0.6, 1))
    for rr, r0, depth in list(made):
        if depth == 1 and rnd.random() < 0.8:
            pts, radii, heading = rr
            for j in range(rnd.randint(1, 3)):
                k = rnd.randint(1, max(1, len(pts) - 2))
                rel = pts[k] - plate.c
                sub = run(rel.dot(ey), rel.dot(ez), heading + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.2), rnd.uniform(0.4, 1.1), 0.014, 0.004, 0.35)
                if sub is not None:
                    made.append((sub, 0.014, 2))
    for (pts, radii, heading), r0, depth in made:
        sides = 6 if r0 > 0.08 else 5 if r0 > 0.03 else 4
        end = radii[-1]
        b.lod = 1 if depth == 2 else 0
        if end > 0.015 and rnd.random() < 0.7:
            lk.tube_broken(b, m.root, m.end, pts, radii, sides, rnd, jag=1.3)
        else:
            ks.tube(b, m.root, pts, radii[:-1] + [0.0], sides=sides, cap=False)
    b.lod = 0


def stones(b, m, rnd, plate, count, bodies=None):
    """Stones packed into the plate's face, half-sunk."""
    for i in range(count):
        for _ in range(8):
            u = rnd.uniform(-plate.a * 0.85, plate.a * 0.85)
            v = rnd.uniform(-plate.hb * 0.8, plate.hb * 0.95)
            hit = plate.point(u, v)
            if hit is not None:
                break
        else:
            continue
        r = rnd.choice((0.05, 0.07, 0.1, 0.14, 0.2)) * rnd.uniform(0.8, 1.2)
        rz = r * rnd.uniform(0.6, 0.95)
        rk = fk.Rock(radii=(r * rnd.uniform(0.8, 1.2), r, rz), height=2.0 * r, seed=rnd.randint(1, 999),
                     power=2.6, rough=0.12, yaw=rnd.uniform(0, 360), at=(0.0, 0.0), subdiv=3, sink=5.0,
                     tilt=(rnd.uniform(-30, 30), rnd.uniform(-30, 30)))
        bm = rk.build()
        c0 = G + 2.0 * r - rz
        p = hit[0] - hit[1] * (r * 0.15)
        lk.place(bm, p.x, p.y, p.z - c0)
        fk.emit_rock(b, bm, m.stone, m.stone_skirt)
        bm.free()
    b.lod = 0


def pit(b, m, rnd, plate, bodies, floor_len=3.2):
    """In front of the plate, where the roots came out: a bay of dug-up soil, heaped in two long berms and a low one
    across the far end, a dark floor between (the terrain below can't be dug, so the berms make the hollow)."""
    hx = plate.cx - 0.75 * math.cos(math.radians(plate.theta)) * 0.0
    face = plate.point(0.0, -plate.hb * 0.45)
    fx = face[0].x if face else plate.cx - 0.9
    yaw = plate.yaw
    R = Matrix.Rotation(math.radians(yaw), 3, "Z")

    def at(dx, dy):
        p = R @ Vector((dx, dy, 0.0))
        return (fx + p.x, plate.cy + p.y)

    lumps = [
        dict(radii=(floor_len * 0.55, 0.55, 0.5), height=0.62, seed=41, power=2.2, yaw=yaw + 6, at=at(-floor_len * 0.5 - 0.1, 1.55), rough=0.14),
        dict(radii=(floor_len * 0.5, 0.5, 0.42), height=0.52, seed=47, power=2.2, yaw=yaw - 9, at=at(-floor_len * 0.5, -1.6), rough=0.14),
        dict(radii=(0.5, 1.15, 0.3), height=0.36, seed=53, power=2.3, yaw=yaw, at=at(-floor_len - 0.55, 0.0), rough=0.14),
        dict(radii=(0.7, 0.8, 0.4), height=0.5, seed=59, power=2.4, yaw=yaw + 30, at=at(-floor_len - 0.1, 1.9), rough=0.16),
    ]
    for kw in lumps:
        bm = fk.Rock(subdiv=4, **kw).build()
        moss = (m.soil_moss, fk.moss_depth(kw["seed"], 0.45, 0.025)) if m.soil_moss is not None else None
        bodies.append(fk.emit_rock(b, bm, m.soil, m.skirt, moss))
        bm.free()
    # The floor: freshly turned dark soil, a hand's width above the ground
    bm = fk.Rock(radii=(floor_len * 0.5, 1.4, 0.2), height=0.05, seed=61, power=2.1, yaw=yaw, at=at(-floor_len * 0.5, 0.0), rough=0.05,
                 subdiv=4).build()
    fk.emit_rock(b, bm, m.soil, m.skirt)
    bm.free()
    b.lod = 0


class Tree:
    pass


def tree(b, m, rnd, spec, cx, cy, yaw, L, rb, rt, plate_half, theta, zc, sink, seed, end_z=None, target=None, bodies=None,
         extra=None, first=True, stubs=True):
    """One fallen tree: plate, roots, stones, trunk, stubs, crown, fungus. Returns a SimpleNamespace(trunk, plate)."""
    burnt = spec["style"] == "burnt"
    plate = Plate(b, m, rnd, cx, cy, yaw, plate_half, theta, zc, seed, spec["moss"])
    bodies.append(plate.body)
    roots(b, m, rnd, plate, burnt, count=14 if first else 11)
    stones(b, m, rnd, plate, 24 if first else 14)
    # Centerline
    R = Matrix.Rotation(math.radians(yaw), 3, "Z")
    n = max(8, int(L / 1.4))
    ctrl, radii = [], []
    ph = rnd.uniform(0, 6.28)
    tan_th = math.tan(math.radians(theta))
    for i in range(n + 1):
        f = i / n
        d = L * f
        r = rt + (rb - rt) * (1.0 - f) ** 0.5
        lat = 0.18 * math.sin(d * 0.45 + ph) * min(1.0, d / 3.0)
        p = Vector((cx, cy, 0.0)) + R @ Vector((d + 0.2, lat, 0.0))
        zg = G + r * (1.0 - sink) + 0.1 * math.sin(d * 0.8 + ph) * min(1.0, d / 4.0)
        if end_z is None:
            delta = max(0.0, zc - zg)
            lam = min(7.0, max(2.5, delta / max(0.12, tan_th)))
            z = zg + delta * math.exp(-d / lam)
        else:
            # Held up: from the plate to a resting place on another trunk
            z = zc + (end_z - zc) * (f ** 1.4)
            if target is not None:
                p = Vector((cx, cy, 0.0)).lerp(Vector((target[0], target[1], 0.0)), f)
                p.x += 0.0
        ctrl.append(Vector((p.x, p.y, z)))
        radii.append(r)
    tr = lk.Trunk(ctrl, radii, seed=seed, sides=30, step=0.26, flare=0.38, flare_len=1.5,
                  knots=[(rnd.uniform(2.0, L - 1.5), rnd.uniform(0, 6.28), rnd.uniform(0.08, 0.18)) for _ in range(5)])
    tr.build(b, m.bark, m.under, ragged=(False, spec["crown"] <= 0.0), rnd=rnd)
    tr.cap(b, m.rot if burnt else m.end, 1, "flat" if spec["crown"] > 0 else "break", rnd)
    if m.moss is not None:
        lk.moss_cover(b, tr, m.moss, amount=spec["moss"], thick=0.032, seed=seed, fade=1.5)
    # Stubs of snapped limbs, live branches on the crown
    if stubs:
        s = 2.2
        while s < L - 0.6:
            s += rnd.uniform(0.35, 0.8)
            if s > L - 0.5:
                break
            f = s / L
            a = math.radians(rnd.choice((rnd.uniform(15, 165), rnd.uniform(15, 165), rnd.uniform(165, 215), rnd.uniform(-35, 15))))
            p, nrm = tr.surface(s, a)
            c, T, S, U, r = tr.frame(s)
            if spec["crown"] > 0 and s > L - spec["crown"]:
                continue
            ln = rnd.uniform(*spec["stub_len"]) * (0.7 + 0.8 * f)
            d = (nrm + T * 0.3 + UPV * 0.18).normalized()
            lk.limb(b, m.bark, m.end, p - nrm * 0.05, d, ln, rnd.uniform(0.028, 0.05) * (1.1 - 0.6 * f), 0.02, rnd, sides=6, kink=0.03)
    if spec["crown"] > 0:
        crown(b, m, rnd, tr, spec["crown"])
    # Fungus, ferns, mushrooms
    if spec["fungus"]:
        spots = []
        for k in range(spec["fungus"] * 3):
            spots.append((rnd.uniform(1.5, L - 2.0), rnd.choice((rnd.uniform(160, 200), rnd.uniform(-20, 20), rnd.uniform(130, 220))), rnd.randint(2, 3)))
        lk.shelf_tiers(b, m.cap, m.pores, tr, rnd, spots, rad=(0.08, 0.13))
        for k in range(spec["fungus"] * 5):
            ang = rnd.uniform(0.0, 6.28)
            q = plate.world(rnd.uniform(-1.6, 1.6), rnd.uniform(-1.2, 0.2), 0.0)
            hit = plate.point(rnd.uniform(-1.5, 1.5), rnd.uniform(-1.2, 0.3), lift=0.0)
            if hit is not None and rnd.random() < 0.8:
                lk.mushroom(b, m.mcap, m.mpores, m.mstem, hit[0] - hit[1] * 0.01, rnd.uniform(0.04, 0.09), rnd.uniform(0.03, 0.055), rnd)
    # Ferns on the plate's top and along the trunk
    ferns = []
    for k in range(5 if not burnt else 0):
        hit = plate.point(rnd.uniform(-1.4, 1.4), rnd.uniform(plate.hb * 0.55, plate.hb * 0.95))
        if hit is not None:
            ferns.append((hit[0].x, hit[0].y, hit[0].z, math.degrees(math.atan2(hit[1].y, hit[1].x))))
    for k in range(6 if not burnt else 0):
        s = rnd.uniform(1.0, L - 2.0)
        c, T, S, U, r = tr.frame(s)
        side = rnd.choice((-1.0, 1.0))
        ferns.append((c.x + S.x * side * (r + 0.25), c.y + S.y * side * (r + 0.25), G, math.degrees(math.atan2(S.y * side, S.x * side))))
    lk.ferns(b, m.fern, ferns, rnd, big=1.0)
    tree_ns = SimpleNamespace(trunk=tr, plate=plate)
    extra.extend(tr.capsules(spacing=1.7, shrink=0.84, rmin=0.1))
    return tree_ns


UPV = Vector((0.0, 0.0, 1.0))


def crown(b, m, rnd, tr, span):
    """Live branches in whorls on the last `span` meters of the trunk, with needle sprays and a few brown ones."""
    L = tr.length
    s = L - span
    while s < L - 0.3:
        f = (L - s) / span
        for k in range(4):
            a = math.radians(k * 90 + rnd.uniform(-25, 25) + s * 40)
            if math.sin(a) < -0.4:
                a = -a
            p, nrm = tr.surface(s, a)
            c, T, S, U, r = tr.frame(s)
            ln = (0.45 + 1.7 * f ** 0.8) * rnd.uniform(0.75, 1.15)
            d = (nrm * 1.0 + T * 0.35 + UPV * 0.25).normalized()
            pts = lk.limb(b, m.bark, None, p - nrm * 0.04, d, ln, max(0.014, 0.05 * f + 0.014), 0.008, rnd, sides=4,
                          bend=(0.0, 0.0, -0.18), broken=False, kink=0.05)
            tmat = m.dead if rnd.random() < 0.14 else m.needle
            lk.needles(b, tmat, pts, rnd, spacing=0.038, length=0.12, width=0.018, spread=1.05, skip=0.12)
            for j in range(int(2 + 4 * f)):
                q = rnd.uniform(0.25, 0.9)
                i0 = min(len(pts) - 2, int(q * (len(pts) - 1)))
                base = pts[i0].lerp(pts[i0 + 1], q * (len(pts) - 1) - i0)
                tdir = (pts[i0 + 1] - pts[i0]).normalized()
                _, u, v = ks.basis(tdir)
                aa = rnd.uniform(0, math.tau)
                dd = (tdir * 0.55 + (u * math.cos(aa) + v * math.sin(aa)) * 0.8).normalized()
                sub = lk.limb(b, m.bark, None, base, dd, ln * rnd.uniform(0.25, 0.45), 0.007, 0.003, rnd, sides=3, bend=(0.0, 0.0, -0.1),
                              broken=False, kink=0.05)
                lk.needles(b, tmat, sub, rnd, spacing=0.045, length=0.11, width=0.017, spread=1.0, skip=0.1)
        s += rnd.uniform(0.35, 0.55)


def build(name):
    spec = SPECS[name]
    nk.reset()
    rnd = random.Random(spec["seed"] * 101 + 7)
    m = mats_for(spec)
    b = ks.Builder(name)
    bodies = []
    extra = []
    L = spec["L"]
    pair = spec.get("pair", False)
    cx = (3.6 - L) / 2.0 - (0.3 if not pair else 1.5)
    theta = spec["theta"]
    hb = spec["plate"][1]
    zc = G + hb * math.cos(math.radians(theta)) + 0.1
    A = tree(b, m, rnd, spec, cx, 0.0, 0.0, L, spec["rb"], spec["rt"], spec["plate"], theta, zc, spec["sink"], spec["seed"], bodies=bodies,
             extra=extra)
    pit(b, m, rnd, A.plate, bodies)
    if pair:
        # A smaller tree brought down by the big one: its plate to one side, its trunk held up above the ground on
        # the big trunk's back and lying along it
        bx, by = cx + 3.2, 4.3
        Lb = 8.6
        tx = bx + Lb * 0.97
        ty = 0.45
        # where the big trunk's top is at that x
        s_t = tx - A.trunk.ctrl[0].x
        c, T, S, U, r = A.trunk.frame(max(0.0, min(A.trunk.length, s_t)))
        end_z = c.z + r * 1.0 + 0.2
        B = tree(b, m, rnd, spec, bx, by, math.degrees(math.atan2(ty - by, tx - bx)), Lb, 0.42, 0.14, (1.45, 1.2), 5.0,
                 G + 1.25 + 0.1, 0.0, spec["seed"] + 11, end_z=end_z, target=(tx, ty), bodies=bodies, extra=extra, first=False)
        # The trunk's capsule chain must follow the real centerline, which tree() built from `target`
    b.lod = 0
    lk.litter(b, m.litter, 90, rnd, (cx - 3.5, cx + L, -3.2, 3.2), keep=lambda x, y: True)
    pieces = b.objects()
    for o in pieces:
        print("  %s %d" % (o.name, ks.triangles([o])))
    density = {"WfBarkUnder": 0.2, "WfBark": 1.7, "WfMoss": 1.5, "WfEnd": 0.5, "WfRot": 0.4, "WfSoilMoss": 0.5, "WfSoil": 0.45,
               "WfSkirt": 0.05, "WfRoot": 0.4, "WfStoneSkirt": 0.05, "WfStone": 0.3, "WfFern": 0.3, "WfNeedleDead": 0.2, "WfNeedle": 0.3,
               "FungusTop": 1.0, "FungusPores": 0.5, "MushCap": 0.5, "MushPores": 0.3, "MushStem": 0.4, "Litter": 0.25}
    model = lk.export(name, pieces, bodies, FEATURES, size=lk.atlas_size(), density=density, voxel=0.16, rect=True, extra=extra, limit=120)
    top = 3.6
    lk.preview(name.lower(), model, [
        ("a", (cx - 9.0, -9.0, 4.0), (cx + 2.0, 0.0, 1.0)),
        ("b", (L * 0.55 + 4.0, -7.0, 3.0), (cx + 3.0, 0.0, 0.8)),
        ("plate", (cx - 5.5, -3.2, 2.2), (cx, 0.0, 1.5)),
        ("trunk", (cx + 6.0, -3.0, 1.8), (cx + 5.0, 0.0, 0.9)),
        ("top", (cx + 3.0, -4.0, 20.0), (cx + 3.0, 0.0, 0.0)),
    ])
    print("[%s] done" % name)


for n in (ONLY or list(SPECS)):
    build(n)
