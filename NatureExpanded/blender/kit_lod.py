"""Far LODs that keep a plant's color, for plants built as many small parts (Nature Expanded).

nk.export makes <Name>_LOD1 by decimating the whole plant to 35 %, which collapses every small petal, floret and berry
to a sliver: a daisy drift's far mesh is bare stems. In the game the far mesh is what most of a drift shows, so
`export` here makes it the way kit_shrub.export does, by choosing parts instead:

- `tag(parts, lod=...)` marks whole parts: BOTH (the default: in the near and the far mesh), NEAR (only near: the far
  mesh drops it: grass, leaves, spokes, cups), COARSE (decimated on its own in the far mesh: big smooth surfaces) or
  FAR (only far: a cheap stand-in the near mesh drops, such as a flat star of white where a daisy's 20 rays were).
  `scale` grows a kept part about its own center (or `pivot`) in the far mesh, so fewer, bigger parts still cover.
- `tag_verts` / `tag_faces` do the same for ranges of one merged mesh (kit_wayside's sheets).

Far-only stand-ins are moved well away from the plant while the atlas bakes, so the parts they sit under don't
shade them in the occlusion map, and back again after. The FBX holds <Name> and <Name>_LOD1, one shared atlas.
Nothing is made two-sided (the Unity builder doubles the faces itself).
"""
import os

import bmesh
import bpy
from mathutils import Vector

import naturekit as nk
import zkit as tk

BOTH, NEAR, COARSE, FAR = 0, 1, 2, 3
_AWAY = Vector((25.0, 0.0, 0.0))


# ---------------------------------------------------------------- tagging

def _layer(me, name, kind, domain):
    a = me.attributes.get(name)
    return a if a is not None else me.attributes.new(name, kind, domain)


def _ensure(obj):
    me = obj.data
    if me.attributes.get("lod") is None:
        _layer(me, "lod", "INT", "FACE").data.foreach_set("value", [BOTH] * len(me.polygons))
    if me.attributes.get("lodscale") is None:
        _layer(me, "lodscale", "FLOAT", "POINT").data.foreach_set("value", [0.0] * len(me.vertices))
    if me.attributes.get("pivot") is None:
        _layer(me, "pivot", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", [0.0] * (3 * len(me.vertices)))


def _center(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return (lo + hi) * 0.5


def tag(parts, lod=BOTH, scale=1.0, pivot=None):
    """Marks every part in `parts` (objects) for the far mesh: `lod` BOTH, NEAR, COARSE or FAR, and grown by `scale`
    about `pivot` (default: each part's own center) there. Returns `parts`."""
    for o in parts:
        _ensure(o)
        me = o.data
        me.attributes["lod"].data.foreach_set("value", [lod] * len(me.polygons))
        if abs(scale - 1.0) > 1e-4:
            p = Vector(pivot) if pivot is not None else _center(o)
            n = len(me.vertices)
            me.attributes["lodscale"].data.foreach_set("value", [scale] * n)
            me.attributes["pivot"].data.foreach_set("vector", [c for _ in range(n) for c in p])
    return parts


def tag_verts(obj, start, end, scale, pivot):
    """Grows vertices `start` to `end` of one merged mesh by `scale` about `pivot` in the far mesh (one flower head
    in a sheet of many)."""
    _ensure(obj)
    me = obj.data
    sc = me.attributes["lodscale"].data
    pv = me.attributes["pivot"].data
    for i in range(start, end):
        sc[i].value = scale
        pv[i].vector = Vector(pivot)


def tag_faces(obj, fn):
    """Sets each face's lod to `fn(polygon)` (BOTH, NEAR, COARSE or FAR)."""
    _ensure(obj)
    me = obj.data
    me.attributes["lod"].data.foreach_set("value", [fn(p) for p in me.polygons])


# ---------------------------------------------------------------- export

def _keep(obj, keep):
    """Deletes the faces whose lod `keep` refuses (and the vertices left loose)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.faces.layers.int.get("lod")
    if layer is not None:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f[layer])], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _shift_far(obj, offset):
    """Moves the far-only faces' vertices by `offset` (out of the way while baking, and back)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.faces.layers.int.get("lod")
    if layer is not None:
        verts = {v for f in bm.faces if f[layer] == FAR for v in f.verts}
        for v in verts:
            v.co += offset
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _far(obj, coarse_ratio):
    """The far mesh from a copy of the baked plant: drops NEAR faces, grows each kept part about its pivot, and
    decimates COARSE faces on their own to `coarse_ratio`."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    sc = bm.verts.layers.float.get("lodscale")
    pv = bm.verts.layers.float_vector.get("pivot")
    if sc is not None and pv is not None:
        for v in bm.verts:
            k = v[sc]
            if k > 0.0 and abs(k - 1.0) > 1e-4:
                p = Vector(v[pv])
                v.co = p + (v.co - p) * k
    bm.to_mesh(obj.data)
    bm.free()
    _keep(obj, lambda lod: lod != NEAR)
    layer = obj.data.attributes.get("lod")
    if layer is None or not any(a.value == COARSE for a in layer.data):
        return obj
    dup = obj.copy()
    dup.data = obj.data.copy()
    tk.link(dup)
    _keep(obj, lambda lod: lod != COARSE)
    _keep(dup, lambda lod: lod == COARSE)
    mod = dup.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = coarse_ratio
    tk.apply_modifiers(dup)
    tk.triangulate(dup)
    name = obj.name
    return tk.join([obj, dup], name)


def _strip(obj):
    for name in ("lod", "lodscale", "pivot"):
        a = obj.data.attributes.get(name)
        if a is not None:
            obj.data.attributes.remove(a)


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def export(name, pieces, out_dir, size=512, coarse_ratio=0.4):
    """nk.export with a far mesh made from the tags (see `tag`) instead of decimating everything: bakes every piece
    into one atlas (<name>_Albedo/_Normal/_RMOM.png) and writes <name>.fbx with <name> (the near mesh: everything
    but the FAR stand-ins) and <name>_LOD1 (the far mesh), sharing the atlas. Returns the near mesh."""
    folder = os.path.join(out_dir, name)
    os.makedirs(folder, exist_ok=True)
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("Bake")
    for o in pieces:
        _ensure(o)
    atlas = tk.triangulate(tk.join(pieces, name))
    tk.smart_uvs(atlas)
    _shift_far(atlas, _AWAY)
    paths = tk.bake_atlas(atlas, folder, name, size=size)
    _shift_far(atlas, -_AWAY)
    baked = tk.baked_material(name, paths)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    lod = atlas.copy()
    lod.data = atlas.data.copy()
    lod.name = name + "_LOD1"
    tk.link(lod)
    lod = _far(lod, coarse_ratio)
    _keep(atlas, lambda v: v != FAR)
    _strip(atlas)
    _strip(lod)
    tk.export_fbx([atlas, lod], os.path.join(folder, name + ".fbx"))
    near, far = triangles(atlas), triangles(lod)
    print("[%s] %d triangles, LOD1 %d (%d %%)" % (name, near, far, round(100.0 * far / max(1, near))))
    lod.hide_render = True
    return atlas


def lod_preview(script, name, out_dir, focus_height=0.0, distance=1.6, patch=True):
    """Renders the far mesh (export hides it) the way nk.previews renders the plant: <script>_lod.png from the
    front, and <script>_lodpatch.png, a patch of nine copies from a few meters off, to check it keeps the color.
    Call it after nk.previews (which sets up the stage)."""
    model = bpy.data.objects.get(name)
    lod = bpy.data.objects.get(name + "_LOD1")
    if model is None or lod is None:
        return
    model.hide_render = True
    lod.hide_render = False
    f = Vector((0.0, 0.0, focus_height))
    loc = f + Vector((0.25, -1.0, 0.3)).normalized() * distance
    tk.render(tk.camera(script + "lod", loc, f, lens=50), os.path.join(out_dir, "%s_lod.png" % script), samples=32)
    if patch:
        import math
        import random
        rnd = random.Random(1)
        copies = []
        for i in range(8):
            c = lod.copy()
            tk.link(c)
            a = rnd.uniform(0, math.tau)
            r = rnd.uniform(0.7, 1.9)
            c.location = (r * math.cos(a), r * math.sin(a) + 0.6, 0.0)
            c.rotation_euler = (0.0, 0.0, rnd.uniform(0, math.tau))
            s = rnd.uniform(0.8, 1.15)
            c.scale = (s, s, s)
            copies.append(c)
        tk.render(tk.camera(script + "lodpatch", (0.4, -3.6, 1.4), (0.0, 0.6, -0.2), lens=35),
                  os.path.join(out_dir, "%s_lodpatch.png" % script), samples=32)
        for c in copies:
            bpy.data.objects.remove(c)
    model.hide_render = False
    lod.hide_render = True
