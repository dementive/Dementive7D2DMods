"""What Zombies Expanded's gear and growth models need on top of zkit: the reference zombie skeletons exported from
the game (skeletons/<name>.json, numbers only), a stand-in body built from their hit boxes to fit pieces on and to
render previews with, and the export that puts each piece on its bone.

Run a model script with Blender in background mode (src/build-models.bat runs them all):
    blender -b --factory-startup --python hard_hat.py -- <unity models folder> <preview folder>
Each script writes its model to <unity models folder>/<Name>/ (Name in PascalCase, e.g. HardHat).

Coordinates: Blender meters, Z up, the zombie standing at the origin with its feet at z = 0, facing -Y, so its left
is +X (Unity (x, y, z) = (-bx, bz, -by)). Every piece is modeled in place on Joe's bind pose (an A-pose, arms down
45 degrees). Mark each piece with on(obj, bone) for the bone it rides on ("Head", "Spine2", "LeftForeArm"...); export()
bakes all pieces into one texture atlas, splits them by bone with each origin at its bone, and writes <Name>.fbx and
the textures. The Unity builder makes each bone's piece a child the game parents to that bone on any zombie, scaled
to that zombie's size (from its hit boxes).
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

import zkit as tk

HERE = os.path.dirname(os.path.abspath(__file__))


def to_blender(u):
    return Vector((-u[0], -u[2], u[1]))


class Skeleton:
    """A reference zombie's bind pose: bone positions and hit boxes, in Blender coordinates."""

    def __init__(self, name="joe"):
        with open(os.path.join(HERE, "skeletons", name + ".json"), encoding="utf-8") as f:
            data = json.load(f)
        self.name = name
        self.bones = {b["name"]: b for b in data["bones"]}
        self.colliders = data["colliders"]

    def has(self, bone):
        return bone in self.bones

    def pos(self, bone):
        """Where a bone is (its pivot)."""
        return to_blender(self.bones[bone]["pos"])

    def point(self, bone, local):
        """A point given in the bone's own Unity frame (as the hit boxes are), in Blender coordinates."""
        b = self.bones[bone]
        x, y, z, w = b["rot"]
        return to_blender(Vector(b["pos"]) + Quaternion((w, x, y, z)) @ Vector(local))

    def axis(self, bone, child):
        """The unit direction from a bone to its child (along an arm, down a leg)."""
        return (self.pos(child) - self.pos(bone)).normalized()

    def collider(self, bone):
        for c in self.colliders:
            if c["bone"] == bone:
                return c
        return None

    def radius(self, bone):
        """The bone's hit box radius (how thick that part of the body is), or 0."""
        c = self.collider(bone)
        return c.get("radius", 0.0) if c else 0.0

    def center(self, bone):
        """The middle of the bone's hit box."""
        c = self.collider(bone)
        return self.point(bone, c["center"]) if c else self.pos(bone)


JOE = None


def joe():
    global JOE
    if JOE is None:
        JOE = Skeleton("joe")
    return JOE


# ---------------------------------------------------------------- stand-in body

def _capsule(name, a, b, r, material):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r)
    half = (b - a).length / 2
    for v in bm.verts:
        v.co.z += half if v.co.z > 0 else -half
    obj = tk.mesh_object(name, bm, material)
    d = (b - a).normalized() if (b - a).length > 1e-6 else Vector((0, 0, 1))
    obj.matrix_world = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    tk.smooth(obj, 60)
    return obj


def body(sk=None, name="Body"):
    """A grey stand-in zombie made of its hit boxes (spheres and capsules on the bones), to fit pieces against and
    to show them on in previews. Not exported."""
    sk = sk or joe()
    mat, g = tk.new_material(name + "Skin")
    tk.finish(mat, g, (0.42, 0.4, 0.38), 0.0, 0.75)
    parts = []
    for i, c in enumerate(sk.colliders):
        bone = c["bone"]
        if c["type"] == "sphere":
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=c["radius"])
            o = tk.mesh_object("%s_%d" % (name, i), bm, mat)
            o.matrix_world = Matrix.Translation(sk.point(bone, c["center"]))
            tk.smooth(o, 60)
        elif c["type"] == "capsule":
            ax = [0.0, 0.0, 0.0]
            ax[c["axis"]] = 1.0
            half = max(0.0, c["height"] / 2 - c["radius"])
            ctr = Vector(c["center"])
            a = sk.point(bone, ctr - Vector(ax) * half)
            b = sk.point(bone, ctr + Vector(ax) * half)
            o = _capsule("%s_%d" % (name, i), a, b, c["radius"], mat)
        else:
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            o = tk.mesh_object("%s_%d" % (name, i), bm, mat)
            corners = [sk.point(bone, Vector(c["center"]) + Vector((sx * c["size"][0], sy * c["size"][1], sz * c["size"][2])) / 2)
                       for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
            for v, p in zip(o.data.vertices, sorted(corners, key=lambda p: (p.x, p.y, p.z))):
                v.co = p
        o["zbody"] = True
        parts.append(o)
    # Feet and hands, which have no hit boxes
    for bone, toe in (("LeftFoot", "LeftToeBase"), ("RightFoot", "RightToeBase")):
        if sk.has(bone) and sk.has(toe):
            parts.append(_capsule(name + bone, sk.pos(bone), sk.pos(toe), 0.05, mat))
    for bone, tip in (("LeftHand", "LeftHandMiddle2"), ("RightHand", "RightHandMiddle2")):
        if sk.has(bone) and sk.has(tip):
            parts.append(_capsule(name + bone, sk.pos(bone), sk.pos(tip), 0.035, mat))
    for p in parts:
        p["zbody"] = True
    return parts


def stage():
    """Lights and a floor at z = 0 for the previews."""
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Stage")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.6, 0.68, 1)
    bg.inputs["Strength"].default_value = 0.7
    scene.world = world
    sun = tk.link(bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    fill = tk.link(bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA")))
    fill.data.energy = 150
    fill.data.size = 3
    fill.location = (-2.5, 2.5, 2.4)
    fill.rotation_euler = (math.radians(60), 0, math.radians(-135))
    mat, g = tk.new_material("Floor")
    tk.finish(mat, g, (0.3, 0.29, 0.28), 0.0, 0.8)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4.0)
    tk.mesh_object("Floor", bm, mat)


# ---------------------------------------------------------------- pieces and export

def on(obj, bone, piece=None):
    """Marks a piece as riding on `bone` (it moves and turns with it in game). Pieces on the same bone are baked
    and exported as one, unless they're given a `piece` name: then each is its own part ("Spine2#Chest",
    "Spine2#Back"), which the game can knock off or drop on its own."""
    if not joe().has(bone):
        raise ValueError("Joe has no bone " + bone)
    label = bone if piece is None else bone + "#" + piece
    tk.mark_part(obj, label)
    obj["zbone"] = label
    return obj


def export(name, pieces, out_dir, size=1024):
    """Bakes every piece into one atlas (<name>_Albedo/_Normal/_RMOM[/_Emission].png), splits them by bone (and
    piece name) with the origin at the bone's pivot, and writes <name>.fbx: an empty root named <name> with one child
    per part, named "<Bone>" or "<Bone>#<Piece>". Returns the split parts (with the baked material, for previews)."""
    bones = []
    for p in pieces:
        if p["zbone"] not in bones:
            bones.append(p["zbone"])
    atlas = tk.triangulate(tk.join(pieces, name))
    tk.smart_uvs(atlas)
    paths = tk.bake_atlas(atlas, out_dir, name, size=size)
    baked = tk.baked_material(name, paths, emission_strength=4.0)
    atlas.data.materials.clear()
    atlas.data.materials.append(baked)
    parts = [tk.split_part(atlas, b, joe().pos(b.split("#")[0])) for b in bones]
    for p in parts:
        if "trap_part" in p.data.attributes:
            p.data.attributes.remove(p.data.attributes["trap_part"])
    tk.export_fbx([atlas] + parts, os.path.join(out_dir, name + ".fbx"))
    tris = sum(len(f.vertices) - 2 for p in parts for f in p.data.polygons)
    print("[%s] %d triangles on %s" % (name, tris, ", ".join(bones)))
    return parts


def previews(name, out_dir, focus, distance=1.6, lens=50):
    """Front, three-quarter back and side renders around `focus` (a point, e.g. the head), on the stand-in body."""
    f = Vector(focus)
    views = {
        "front": f + Vector((0.35, -1.0, 0.25)).normalized() * distance,
        "back": f + Vector((-0.6, 0.9, 0.35)).normalized() * distance,
        "side": f + Vector((1.0, -0.15, 0.1)).normalized() * distance,
    }
    for view, loc in views.items():
        tk.render(tk.camera(name + view, loc, f, lens=lens), os.path.join(out_dir, "%s_%s.png" % (name, view)),
                  res=(900, 900), samples=64)
