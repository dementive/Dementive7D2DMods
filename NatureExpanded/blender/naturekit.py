"""Nature Expanded's plant kit, on top of zkit.py (mesh parts, materials, baking, FBX; a copy of the zombie and trap
mods' kit, so each mod builds on its own).

Plants are block models, like the traps: Blender meters, Z up, the block's center at the origin, so the ground is at
z = -0.5 (GROUND) and the plant stands on it (the game puts a model's origin at the center of its bottom block). One
block is 1 x 1 m: keep a plant's footprint inside x, y in [-0.45, 0.45] unless its spec says otherwise. The game draws
them with its own plant shader (Game/EntityTintMaskSSS) double-sided, so a leaf or petal is a single sheet of faces:
no thickness needed. It sways them in the wind, more the higher above the ground a vertex is.

Every helper takes a material made with `plant(...)`, `petal(...)` or zkit's own, and gives each vertex a float
attribute "t": 0 at a part's base, 1 at its tip, so `petal` can shade from base to tip after the parts are joined.
`export` bakes and writes <Name>.fbx with two meshes, <Name> and a lighter <Name>_LOD1 for far away.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import zkit as tk

GROUND = -0.5


def reset():
    tk.reset_scene()


# ---------------------------------------------------------------- materials

def _attr(g, name):
    n = g.node("ShaderNodeAttribute", attribute_name=name)
    return n.outputs["Fac"]


def plant(name, color, color2=None, rough=0.65, vary=0.25, scale=14.0, wax=False, sat=0.85, value=0.85):
    """A living plant surface (leaves, stems, needles, cactus): its color drifting between `color` and `color2` over
    the surface, a soft fine bump, a little glossier if waxy. Ends in a grade that pulls saturation and value down,
    like the game's own foliage (bright clean greens read as plastic in game)."""
    mat, g = tk.new_material(name)
    c2 = color2 or tuple(c * 0.65 for c in color)
    n = g.noise(scale, detail=3.0)
    col = g.mix(g.ramp(n, 0.5 - vary, 0.5 + vary), color, c2)
    # Darker toward the base of each part (older, shaded), lighter toward its tip
    col = g.mix(g.ramp(_attr(g, "t"), 0.0, 0.6), tuple(c * 0.7 for c in color), col)
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough - (0.25 if wax else 0.0), g.bump(g.noise(70.0), 0.04, 0.002))


def petal(name, base, tip, mid=None, rough=0.55, vary=0.12, streaks=0.0, sat=0.9, value=0.9):
    """A flower petal: `base` color at the base of each petal shading to `tip` at its tip (through `mid`), a
    little variation, optional fine streaks along the petal (`streaks` 0 to 1, e.g. on poppies and irises). Colors
    should be the real flower's, but a touch muted: the grade keeps them from reading as plastic."""
    mat, g = tk.new_material(name)
    t = _attr(g, "t")
    col = g.mix(g.ramp(t, 0.0, 0.85), base, tip) if mid is None else \
        g.mix(g.ramp(t, 0.45, 0.95), g.mix(g.ramp(t, 0.0, 0.45), base, mid), tip)
    col = g.mix(g.math("MULTIPLY", g.noise(30.0), vary), col, tuple(c * 0.8 for c in tip))
    if streaks > 0.0:
        wave = g.node("ShaderNodeTexWave", wave_type="RINGS", rings_direction="SPHERICAL")
        g._in(wave, "Scale", 160.0)
        g._in(wave, "Distortion", 6.0)
        g.links.new(g.coords(), wave.inputs["Vector"])
        col = g.mix(g.math("MULTIPLY", g.ramp(wave.outputs["Fac"], 0.6, 1.0), streaks), col, tuple(c * 0.55 for c in base))
    col = tk.grade(g, col, sat=sat, value=value)
    return tk.finish(mat, g, col, 0.0, rough, g.bump(g.noise(90.0), 0.02, 0.001))


# ---------------------------------------------------------------- geometry

def _frame(direction):
    """Two vectors across a direction (side, up-ish), for laying a blade along it."""
    d = Vector(direction).normalized()
    side = d.cross(Vector((0.0, 0.0, 1.0)))
    if side.length < 1e-4:
        side = d.cross(Vector((1.0, 0.0, 0.0)))
    side.normalize()
    return d, side, side.cross(d).normalized()


def _set_t(obj, values):
    attr = obj.data.attributes.new("t", "FLOAT", "POINT")
    for i, v in enumerate(values):
        attr.data[i].value = v


def blade(name, base, direction, length, width, material, bend=0.25, twist=0.0, segments=6, profile="lance",
          roll=0.0):
    """A leaf, grass blade or petal: a single sheet of faces from `base` along `direction`, `length` long and
    `width` wide at its widest, arching over by `bend` (0 straight, 1 bent right over toward the ground), twisting
    `twist` degrees along its length, rolled `roll` degrees about its own axis. Profiles: "lance" (widest a third of
    the way, pointed tip), "oval" (widest in the middle, round tip), "strap" (even width, blunt tip, like iris or
    cattail leaves), "spoon" (narrow base, wide round tip, like daisy or poppy petals), "heart" (wide base)."""
    d, side, up = _frame(direction)
    if roll:
        rot = Matrix.Rotation(math.radians(roll), 3, d)
        side, up = rot @ side, rot @ up
    bm = bmesh.new()
    ts = []
    rows = []
    for i in range(segments + 1):
        s = i / segments
        if profile == "lance":
            w = max(0.0, (1.0 - s) ** 0.8 * min(1.0, s * 3.0 + 0.15))
        elif profile == "oval":
            w = math.sin(math.pi * s) ** 0.7
        elif profile == "strap":
            w = 1.0 if s < 0.85 else (1.0 - s) / 0.15
        elif profile == "spoon":
            w = min(1.0, 0.25 + s * 1.2) * (math.sin(math.pi * min(s, 0.999)) ** 0.25 if s > 0.6 else 1.0)
        elif profile == "heart":
            w = (1.0 - s) ** 0.6
        else:
            w = 1.0
        # Arch: the blade's direction turns toward the ground as it goes
        angle = bend * s * s * math.pi * 0.5
        tw = Matrix.Rotation(math.radians(twist * s), 3, d)
        along = d * math.cos(angle) + Vector((0.0, 0.0, -1.0)) * math.sin(angle)
        center = Vector(base) + along * (length * s) if i == 0 else rows[-1][2] + along * (length / segments)
        sv = tw @ side
        a = bm.verts.new(center - sv * (width * 0.5 * w))
        b = bm.verts.new(center + sv * (width * 0.5 * w))
        rows.append((a, b, center))
        ts += [s, s]
    for i in range(segments):
        a0, b0, _ = rows[i]
        a1, b1, _ = rows[i + 1]
        bm.faces.new((a0, b0, b1, a1))
    obj = tk.mesh_object(name, bm, material)
    _set_t(obj, ts)
    return obj


def stem(name, points, radius, material, resolution=3):
    """A stem, stalk or twig along a polyline (a thin tube), with "t" 0 at its first point and 1 at its last."""
    obj = tk.tube(name, points, radius, material, resolution=resolution)
    zs = [v.co.z for v in obj.data.vertices]
    z0, z1 = points[0][2], points[-1][2]
    span = (z1 - z0) if abs(z1 - z0) > 1e-4 else 1.0
    _set_t(obj, [min(1.0, max(0.0, (z - z0) / span)) for z in zs])
    return obj


def petal_ring(name, center, axis, count, length, width, material, cup=0.3, droop=0.0, profile="spoon", seed=0,
               jitter=0.12, layers=1):
    """A ring of petals around `center`, facing along `axis`: a daisy, poppy, aster or rose head. `cup` 0 lays the
    petals flat, 1 stands them up into a cup; `droop` bends their tips back down. `layers` > 1 adds inner rings,
    smaller and more upright (roses, peonies)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = _frame(ax)
    parts = []
    for layer in range(layers):
        n = max(3, count - layer * 2)
        scale = 1.0 - layer * 0.25
        lift = cup + layer * 0.25
        for i in range(n):
            a = (i + rnd.uniform(-jitter, jitter)) / n * math.tau + layer * 0.4
            out = (side * math.cos(a) + up * math.sin(a))
            direction = (out * math.cos(lift * math.pi * 0.5) + ax * math.sin(lift * math.pi * 0.5)).normalized()
            parts.append(blade("%s%d_%d" % (name, layer, i), Vector(center) + ax * (0.002 * layer), direction,
                               length * scale * rnd.uniform(0.9, 1.1), width * scale, material, bend=droop,
                               segments=4, profile=profile))
    return parts


def disc(name, center, axis, radius, material, height=0.006, segments=10):
    """A flower's center (a daisy's or sunflower's disc, a poppy's seed head): a low dome facing `axis`."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=4, radius=1.0)
    bmesh.ops.scale(bm, vec=(radius, radius, max(height, 0.001)), verts=bm.verts)
    ax = Vector(axis).normalized()
    rot = ax.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ rot, verts=bm.verts)
    obj = tk.mesh_object(name, bm, material)
    _set_t(obj, [1.0] * len(obj.data.vertices))
    return obj


def spike(name, base, axis, height, material, count=24, size=0.018, seed=0, shape="cup", open_to=0.85,
          bud_material=None):
    """A spike of small flowers up a stalk (lupine, foxglove, fireweed, cattail head): `count` florets spiraling up
    from `base` along `axis` over `height`, largest at the bottom. Shapes: "cup" (little bells), "pea" (lupine's
    pea flowers: two petals each), "dot" (tight buds). Up to `open_to` (0 to 1 up the spike) they're open, above it
    they're buds (in `bud_material` if given)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = _frame(ax)
    parts = []
    for i in range(count):
        s = i / max(1, count - 1)
        a = i * 2.39996 + rnd.uniform(-0.2, 0.2)
        out = (side * math.cos(a) + up * math.sin(a))
        at = Vector(base) + ax * (height * s) + out * (size * 0.6)
        k = size * (1.0 - 0.6 * s)
        if shape == "dot" or s > open_to:
            parts.append(disc("%s%d" % (name, i), at, out, k * 0.45, bud_material or material, height=k * 0.35, segments=6))
        elif shape == "pea":
            for j, sgn in enumerate((-1, 1)):
                d = (out + ax * 0.25).normalized()
                parts.append(blade("%s%d_%d" % (name, i, j), at, d, k, k * 0.7, material, bend=-0.2, segments=2,
                                   profile="oval", roll=sgn * 35.0))
        else:
            parts += petal_ring("%s%d" % (name, i), at, (out - ax * 0.6).normalized(), 5, k, k * 0.6, material,
                                cup=0.75, profile="oval", seed=seed + i, jitter=0.05)
    return parts


def umbel(name, top, axis, radius, material, spokes=10, florets=7, size=0.006, seed=0, dome=0.3):
    """A flat or domed head of tiny flowers on spokes (Queen Anne's lace, yarrow, elderberry): `spokes` short stalks
    from `top`, each ending in a cluster of `florets` tiny dots. Returns the florets (give the spokes their own stems
    if they should show)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    _, side, up = _frame(ax)
    parts = []
    for i in range(spokes):
        a = i / spokes * math.tau + rnd.uniform(-0.15, 0.15)
        r = radius * rnd.uniform(0.55, 1.0)
        out = side * math.cos(a) + up * math.sin(a)
        center = Vector(top) + out * r + ax * (dome * radius * (1.0 - (r / radius) ** 2))
        for j in range(florets):
            b = rnd.uniform(0, math.tau)
            q = rnd.uniform(0.0, radius * 0.18)
            at = center + (side * math.cos(b) + up * math.sin(b)) * q
            parts.append(disc("%s%d_%d" % (name, i, j), at, ax, size, material, height=size * 0.5, segments=5))
    return parts


def grass(name="Grass"):
    """The meadow grass mixed into every flower clump, close to the game's own grass so a drift doesn't leave a bare
    patch where the grass would be."""
    return plant(name, (0.2, 0.26, 0.09), (0.3, 0.3, 0.13), rough=0.75, vary=0.35)


def tuft(name, center, count, height, material, radius=0.05, width=0.012, seed=0):
    """A tuft of grass blades fanning up and out from `center` (x, y on the ground), `height` tall."""
    rnd = random.Random(seed)
    parts = []
    for i in range(count):
        a = i / count * math.tau + rnd.uniform(-0.3, 0.3)
        r = radius * math.sqrt(rnd.random())
        base = (center[0] + r * math.cos(a), center[1] + r * math.sin(a), GROUND)
        d = Vector((math.cos(a) * rnd.uniform(0.15, 0.45), math.sin(a) * rnd.uniform(0.15, 0.45), 1.0))
        parts.append(blade("%s%d" % (name, i), base, d, height * rnd.uniform(0.6, 1.1), width * rnd.uniform(0.8, 1.2),
                           material, bend=rnd.uniform(0.15, 0.5), twist=rnd.uniform(-40, 40), segments=4))
    return parts


def scatter(count, radius, seed=0, min_gap=0.0):
    """`count` points (x, y) inside a circle of `radius` on the ground, for the stems of a clump."""
    rnd = random.Random(seed)
    pts = []
    tries = 0
    while len(pts) < count and tries < count * 50:
        tries += 1
        a = rnd.uniform(0, math.tau)
        r = radius * math.sqrt(rnd.random())
        p = (r * math.cos(a), r * math.sin(a))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= min_gap * min_gap for q in pts):
            pts.append(p)
    return pts


# ---------------------------------------------------------------- export and previews

def _triangles(obj):
    return sum(len(f.vertices) - 2 for f in obj.data.polygons)


def weighted_uvs(obj, density, margin=0.004):
    """tk.smart_uvs, then each UV island grown or shrunk by its material's `density` (a linear factor on pixels per
    cm, keyed by the start of the material's name; 1 for the rest) before the islands are packed again: the parts
    seen up close (a mushroom's cap, a log's bark and moss) take the atlas from the parts that only need their color
    (litter, ferns), which would otherwise get the same texels per cm."""
    tk.smart_uvs(obj, margin)
    me = obj.data
    names = [m.name if m else "" for m in me.materials]

    def factor(index):
        n = names[index] if index < len(names) else ""
        return next((v for k, v in density.items() if n.startswith(k)), 1.0)

    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # An island: faces joined by edges whose two ends sit at the same UVs on both sides
    for e in bm.edges:
        loops = list(e.link_loops)
        if len(loops) != 2:
            continue
        a, b = loops
        ua = {a.vert.index: a[uv].uv.copy(), a.link_loop_next.vert.index: a.link_loop_next[uv].uv.copy()}
        ub = {b.vert.index: b[uv].uv.copy(), b.link_loop_next.vert.index: b.link_loop_next[uv].uv.copy()}
        if all((ua[k] - ub[k]).length < 1e-6 for k in ua if k in ub):
            parent[find(a.face.index)] = find(b.face.index)
    islands = {}
    for f in bm.faces:
        islands.setdefault(find(f.index), []).append(f)
    for faces in islands.values():
        k = factor(faces[0].material_index)
        if abs(k - 1.0) < 1e-4:
            continue
        loops = [l for f in faces for l in f.loops]
        c = sum((l[uv].uv for l in loops), Vector((0.0, 0.0))) / len(loops)
        for l in loops:
            l[uv].uv = c + (l[uv].uv - c) * k
    bm.to_mesh(me)
    bm.free()
    me.update()
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=margin, rotate=True, scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def texel_report(obj, size):
    """Pixels per cm each material gets in the atlas (`size` square), printed for checking the texel density."""
    me = obj.data
    uv = me.uv_layers.active.data
    area3, area2 = {}, {}
    for p in me.polygons:
        n = me.materials[p.material_index].name if me.materials else "?"
        pts = [uv[i].uv for i in p.loop_indices]
        a2 = 0.0
        for i in range(1, len(pts) - 1):
            a2 += abs((pts[i] - pts[0]).cross(pts[i + 1] - pts[0])) * 0.5
        area3[n] = area3.get(n, 0.0) + p.area
        area2[n] = area2.get(n, 0.0) + a2
    for n in sorted(area3):
        if area3[n] > 0:
            print("  texels %-16s %6.1f px/cm over %6.0f cm2" % (n, size * math.sqrt(area2[n] / area3[n]) / 100.0,
                                                                  area3[n] * 1e4))


def export(name, pieces, out_dir, size=512, lod_ratio=0.35, density=None):
    """Bakes every piece into one atlas (<name>_Albedo/_Normal/_RMOM.png), and writes <name>.fbx with the plant
    (<name>) and a lighter copy for far away (<name>_LOD1, decimated to `lod_ratio`, same atlas). `density` weights
    the atlas between materials (see weighted_uvs). Returns the plant."""
    folder = os.path.join(out_dir, name)
    os.makedirs(folder, exist_ok=True)
    if bpy.context.scene.world is None:
        # The ambient occlusion bake needs a world
        bpy.context.scene.world = bpy.data.worlds.new("Bake")
    atlas = tk.triangulate(tk.join(pieces, name))
    if density:
        weighted_uvs(atlas, density)
    else:
        tk.smart_uvs(atlas)
    texel_report(atlas, size)
    paths = tk.bake_atlas(atlas, folder, name, size=size)
    baked = tk.baked_material(name, paths)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    lod = atlas.copy()
    lod.data = atlas.data.copy()
    lod.name = name + "_LOD1"
    tk.link(lod)
    mod = lod.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = lod_ratio
    with bpy.context.temp_override(active_object=lod, object=lod, selected_editable_objects=[lod], selected_objects=[lod]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    tk.triangulate(lod)
    tk.export_fbx([atlas, lod], os.path.join(folder, name + ".fbx"))
    print("[%s] %d triangles, LOD1 %d" % (name, _triangles(atlas), _triangles(lod)))
    lod.hide_render = True
    return atlas


def previews(name, model, out_dir, focus_height=0.0, distance=1.6):
    """Front, side and top renders of the plant on the stage (floor at the ground, a 1.8 m figure for scale), and a
    patch: eight more copies, turned and sized at random, the way the game scatters it over a field."""
    tk.preview_stage()
    f = Vector((0.0, 0.0, focus_height))
    views = {
        "front": f + Vector((0.25, -1.0, 0.3)).normalized() * distance,
        "side": f + Vector((1.0, 0.1, 0.15)).normalized() * distance,
        "top": f + Vector((0.2, -0.3, 1.0)).normalized() * distance,
    }
    for view, loc in views.items():
        tk.render(tk.camera(name + view, loc, f, lens=50), os.path.join(out_dir, "%s_%s.png" % (name, view)), samples=64)
    rnd = random.Random(1)
    copies = []
    for i in range(8):
        c = model.copy()
        tk.link(c)
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.7, 1.9)
        c.location = (r * math.cos(a), r * math.sin(a) + 0.6, 0.0)
        c.rotation_euler = (0.0, 0.0, rnd.uniform(0, math.tau))
        s = rnd.uniform(0.8, 1.15)
        c.scale = (s, s, s)
        copies.append(c)
    tk.render(tk.camera(name + "patch", (0.4, -3.6, 1.4), (0.0, 0.6, -0.2), lens=35), os.path.join(out_dir, "%s_patch.png" % name),
              samples=48)
    for c in copies:
        bpy.data.objects.remove(c)
