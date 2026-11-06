"""Re-renders the previews of an already exported ground-cover model without baking it again.

    blender -b --factory-startup --threads 2 --python preview_only.py -- <models folder> <preview folder> <Name> <script> <kind>
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gckit as gc  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
MODELS, PREVIEWS, NAME, SCRIPT, KIND = a[:5]
os.makedirs(PREVIEWS, exist_ok=True)
gc.reset()
folder = os.path.join(MODELS, NAME)
bpy.ops.import_scene.fbx(filepath=os.path.join(folder, NAME + ".fbx"), axis_forward="-Z", axis_up="Y")
paths = {"albedo": os.path.join(folder, NAME + "_Albedo.png"), "normal": os.path.join(folder, NAME + "_Normal.png"),
         "rmom": os.path.join(folder, NAME + "_RMOM.png")}
mat = gc.tk.baked_material(NAME, paths)
objs = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}
for o in objs.values():
    o.data.materials.clear()
    o.data.materials.append(mat)
import math
from mathutils import Matrix, Vector
model = objs[NAME]


def zrange():
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)).z for o in (model,) for c in o.bound_box]
    return min(zs), max(zs)


best = None
for deg in (0.0, 90.0, -90.0, 180.0):
    for o in objs.values():
        o.rotation_mode = "XYZ"
        o.rotation_euler = (math.radians(deg), 0.0, 0.0)
        o.location = (0.0, 0.0, 0.0)
    lo, hi = zrange()
    score = abs(lo + 0.52) + (hi - lo)
    if best is None or score < best[0]:
        best = (score, deg)
for o in objs.values():
    o.rotation_euler = (math.radians(best[1]), 0.0, 0.0)
bpy.context.view_layer.update()
print("[preview_only] orientation", best)
for o in objs.values():
    mw = o.matrix_world.copy()
    o.parent = None
    o.data.transform(mw)
    o.matrix_world = Matrix.Identity(4)
    o.scale = (1.0, 1.0, 1.0)
    o.rotation_euler = (0.0, 0.0, 0.0)
    o.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.update()
lod = objs.get(NAME + "_LOD1")
if lod is not None:
    lod.hide_render = True
gc.previews(SCRIPT, model, PREVIEWS, kind=KIND, lod_name=NAME + "_LOD1" if lod is not None else None,
            neighbors=True)
print("[preview_only] done", NAME)
