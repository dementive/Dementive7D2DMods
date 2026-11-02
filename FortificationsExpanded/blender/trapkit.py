"""Shared helpers for the Traps Expanded model scripts: mesh parts, procedural materials, texture baking, preview
renders, the item icon and the FBX export. Each trap script builds its parts with these and calls bake_and_export().

Run a trap script with Blender in background mode (see build-models.bat):
    blender -b --factory-startup --python tesla_coil.py -- <unity asset folder> <preview folder> <icon file>

Units are meters, Blender is Z-up. Models are built with their bottom at z = -0.5: the game puts a block model's
origin at the center of its (bottom) block.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

TEX_SIZE = 2048


# ---------------------------------------------------------------- scene

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for device_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = device_type
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == device_type]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == device_type
                scene.cycles.device = "GPU"
                break
        except TypeError:
            continue
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    return scene


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_object(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = link(bpy.data.objects.new(name, me))
    obj.data.materials.append(material)
    return obj


def apply_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    obj.modifiers.clear()
    obj.data = me
    return obj


def bevel(obj, width, segments=2, angle=35.0):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = True
    return apply_modifiers(obj)


def triangulate(obj):
    """Fixed triangles, so the baked normal map and Unity's tangents agree."""
    mod = obj.modifiers.new("Triangulate", "TRIANGULATE")
    mod.keep_custom_normals = True
    mod.quad_method = "FIXED"
    mod.ngon_method = "BEAUTY"
    return apply_modifiers(obj)


def smooth(obj, angle=35.0):
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.data.set_sharp_from_angle(angle=math.radians(angle))
    return obj


# ---------------------------------------------------------------- parts

def box(name, size, center, material, bevel_width=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    obj = mesh_object(name, bm, material)
    if bevel_width:
        bevel(obj, bevel_width)
    return smooth(obj)


def cylinder(name, radius, z0, z1, material, segments=32, center=(0.0, 0.0), bevel_width=0.0, caps=True, axis="Z",
             rings=0, radius_top=None):
    """A cylinder (or cone, with radius_top) along an axis; rings adds height cuts so it can be dented."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segments, radius1=radius,
                          radius2=radius if radius_top is None else radius_top, depth=z1 - z0)
    if rings:
        side = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6]
        bmesh.ops.subdivide_edges(bm, edges=side, cuts=rings, use_grid_fill=True)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=_rot("Y", 90))
        bmesh.ops.translate(bm, vec=((z0 + z1) / 2, center[0], center[1]), verts=bm.verts)
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=_rot("X", 90))
        bmesh.ops.translate(bm, vec=(center[0], (z0 + z1) / 2, center[1]), verts=bm.verts)
    else:
        bmesh.ops.translate(bm, vec=(center[0], center[1], (z0 + z1) / 2), verts=bm.verts)
    obj = mesh_object(name, bm, material)
    if bevel_width:
        bevel(obj, bevel_width)
    return smooth(obj)


def torus(name, major, minor, center, material, major_segments=56, minor_segments=20, sweep=None, start=0.0,
          minor_fn=None):
    """A torus around Z, or an open arc of one (sweep radians from start). minor_fn(a) can vary the tube radius
    along the ring."""
    bm = bmesh.new()
    closed = sweep is None
    count = major_segments if closed else major_segments + 1
    rings = []
    for i in range(count):
        a = start + (2 * math.pi if closed else sweep) * i / major_segments
        m = minor_fn(a) if minor_fn else minor
        ring = []
        for j in range(minor_segments):
            b = 2 * math.pi * j / minor_segments
            r = major + m * math.cos(b)
            ring.append(bm.verts.new((center[0] + r * math.cos(a), center[1] + r * math.sin(a),
                                      center[2] + m * math.sin(b))))
        rings.append(ring)
    for i in range(major_segments if closed else major_segments):
        for j in range(minor_segments):
            a, b = rings[i], rings[(i + 1) % count]
            bm.faces.new((a[j], b[j], b[(j + 1) % minor_segments], a[(j + 1) % minor_segments]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    obj = mesh_object(name, bm, material)
    return smooth(obj, 60)


def tube(name, points, radius, material, resolution=6, closed=False):
    """A round tube along a polyline (curve with bevel), converted to a mesh."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = resolution
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (co[0], co[1], co[2], 1.0)
    spline.use_cyclic_u = closed
    cobj = link(bpy.data.objects.new(name + "Curve", curve))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(cobj)
    obj = link(bpy.data.objects.new(name, me))
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return smooth(obj, 50)


def hex_bolt(name, x, y, z, material, radius=0.02, height=0.018):
    return cylinder(name, radius, z, z + height, material, segments=6, center=(x, y), bevel_width=0.002)


def _rot(axis, degrees):
    from mathutils import Matrix
    return Matrix.Rotation(math.radians(degrees), 3, axis)


def join(objs, name):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs,
                                   selected_objects=objs):
        bpy.ops.object.join()
    obj = objs[0]
    # The joined object keeps the first part's transform; bake it in so the model's origin is the world origin
    # (points parented to it, like SprayOrigin, are given in world coordinates)
    with bpy.context.temp_override(active_object=obj, object=obj, selected_editable_objects=[obj],
                                   selected_objects=[obj]):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = name
    obj.data.name = name
    return obj


def dent(obj, strength=0.004, size=0.12, seed=0):
    """Dents and warps: displaces the surface along its normals with soft noise (seed shifts the pattern)."""
    tex = bpy.data.textures.new(obj.name + "Dent", "CLOUDS")
    tex.noise_scale = size
    tex.noise_depth = 2
    mod = obj.modifiers.new("Dent", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    mod.texture_coords = "GLOBAL"
    shift = seed * 3.7
    obj.data.transform(Matrix.Translation((shift, 0, 0)))
    apply_modifiers(obj)
    obj.data.transform(Matrix.Translation((-shift, 0, 0)))
    return obj


def orbit(obj, degrees, tilt=None):
    """Rotates an object (built in place) around the model's Z axis; tilt=(axis, degrees, pivot) tips it first."""
    if tilt is not None:
        axis, deg, pivot = tilt
        obj.matrix_world = (Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis)
                            @ Matrix.Translation([-c for c in pivot])) @ obj.matrix_world
    obj.matrix_world = Matrix.Rotation(math.radians(degrees), 4, "Z") @ obj.matrix_world
    return obj


def text_mesh(name, body, size, material, location, rotation=(90.0, 0.0, 0.0), extrude=0.0006,
              font="C:/Windows/Fonts/impact.ttf"):
    """Painted lettering as thin geometry (rotation in degrees; the default stands it up facing -Y)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    if font and os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cobj = link(bpy.data.objects.new(name + "Curve", cu))
    cobj.location = location
    cobj.rotation_euler = [math.radians(r) for r in rotation]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cobj.evaluated_get(dg), depsgraph=dg)
    obj = link(bpy.data.objects.new(name, me))
    obj.matrix_world = cobj.matrix_world.copy()
    bpy.data.objects.remove(cobj)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def flat_shape(name, points, thickness, material, location, rotation=(90.0, 0.0, 0.0)):
    """A thin extruded polygon (points in the XY plane), e.g. a painted symbol."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for x, y in points]
    bm.faces.new(verts)
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    bmesh.ops.translate(bm, vec=(0, 0, thickness),
                        verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = mesh_object(name, bm, material)
    obj.location = location
    obj.rotation_euler = [math.radians(r) for r in rotation]
    return obj


# ---------------------------------------------------------------- moving parts and points

PART_LABELS = ["_body"]


def mark_part(obj, label):
    """Marks every face of a piece as belonging to the moving part `label` (a swinging log, a jaw, a swivel). Mark the
    pieces before joining; the whole model is UV-packed and baked as one, and split_part moves the part back out after
    the bake so the game can move it."""
    if label not in PART_LABELS:
        PART_LABELS.append(label)
    me = obj.data
    attr = me.attributes.get("trap_part") or me.attributes.new("trap_part", "INT", "FACE")
    for i in range(len(me.polygons)):
        attr.data[i].value = PART_LABELS.index(label)
    return obj


def split_part(model, label, pivot):
    """After baking: moves the faces marked `label` into their own mesh object named `label`, with its origin at
    `pivot` (world coordinates; the point it turns or slides about) and parented to the model. It keeps the model's
    baked material. Returns the new object; export it with the model."""
    idx = PART_LABELS.index(label)
    for o in bpy.context.scene.objects:
        o.select_set(o == model)
    bpy.context.view_layer.objects.active = model
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(model.data)
    layer = bm.faces.layers.int.get("trap_part")
    for f in bm.faces:
        f.select_set(False)
    count = 0
    for f in bm.faces:
        if f[layer] == idx:
            f.select_set(True)
            count += 1
    bmesh.update_edit_mesh(model.data)
    if count == 0:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise ValueError("No faces are marked as part " + label)
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    part = [o for o in bpy.context.selected_objects if o != model][0]
    part.name = label
    part.data.name = label
    part.data.transform(Matrix.Translation(-Vector(pivot)))
    part.matrix_world = Matrix.Translation(Vector(pivot))
    part.parent = model
    part.matrix_world = Matrix.Translation(Vector(pivot))
    return part


def point(name, location, parent):
    """An empty the game's code looks up by name (a muzzle, a nozzle, an aim point), at `location` in world
    coordinates, parented to the model or to a moving part so it moves with it."""
    empty = link(bpy.data.objects.new(name, None))
    empty.parent = parent
    empty.matrix_world = Matrix.Translation(Vector(location))
    return empty


# ---------------------------------------------------------------- materials

def _sock(sockets, ident):
    for s in sockets:
        if s.identifier == ident or s.name == ident:
            return s
    raise KeyError(ident)


class Graph:
    """Small node-graph builder for procedural materials."""

    def __init__(self, mat):
        self.mat = mat
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links

    def node(self, kind, **props):
        n = self.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def connect(self, out, node, ident):
        self.links.new(out, _sock(node.inputs, ident))

    def value(self, v):
        n = self.node("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def rgb(self, c):
        n = self.node("ShaderNodeRGB")
        n.outputs[0].default_value = (c[0], c[1], c[2], 1.0)
        return n.outputs[0]

    def _in(self, node, ident, x):
        s = _sock(node.inputs, ident)
        if hasattr(x, "is_output"):
            self.links.new(x, s)
        elif isinstance(x, (tuple, list)):
            s.default_value = tuple(x) + ((1.0,) if len(x) == 3 and len(s.default_value) == 4 else ())
        else:
            s.default_value = x
        return s

    def math(self, op, a, b=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._in(n, n.inputs[0].identifier, a)
        self._in(n, n.inputs[1].identifier, b)
        return n.outputs[0]

    def ramp(self, x, lo, hi, smooth_step=True):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth_step else "LINEAR")
        n.clamp = True
        self._in(n, "From Min", lo)
        self._in(n, "From Max", hi)
        self._in(n, "Value", x)
        return _sock(n.outputs, "Result")

    def mix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA")
        self._in(n, "Factor_Float", fac)
        self._in(n, "A_Color", a)
        self._in(n, "B_Color", b)
        return _sock(n.outputs, "Result_Color")

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT")
        self._in(n, "Factor_Float", fac)
        self._in(n, "A_Float", a)
        self._in(n, "B_Float", b)
        return _sock(n.outputs, "Result_Float")

    def coords(self):
        return _sock(self.node("ShaderNodeTexCoord").outputs, "Object")

    def noise(self, scale, detail=4.0, roughness=0.55, vector=None, distortion=0.0):
        n = self.node("ShaderNodeTexNoise")
        self._in(n, "Scale", scale)
        self._in(n, "Detail", detail)
        self._in(n, "Roughness", roughness)
        self._in(n, "Distortion", distortion)
        self._in(n, "Vector", vector if vector is not None else self.coords())
        return _sock(n.outputs, "Fac")

    def separate(self, vec):
        n = self.node("ShaderNodeSeparateXYZ")
        self.links.new(vec, n.inputs[0])
        return n.outputs

    def edges(self, radius):
        """0 on flat faces, toward 1 within `radius` of a sharp edge (Cycles bevel trick)."""
        bev = self.node("ShaderNodeBevel", samples=8)
        self._in(bev, "Radius", radius)
        geo = self.node("ShaderNodeNewGeometry")
        dot = self.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        self.links.new(_sock(bev.outputs, "Normal"), dot.inputs[0])
        self.links.new(_sock(geo.outputs, "Normal"), dot.inputs[1])
        return self.math("SUBTRACT", 1.0, _sock(dot.outputs, "Value"), clamp=True)

    def cavity(self, distance):
        """1 in open areas, toward 0 in crevices."""
        ao = self.node("ShaderNodeAmbientOcclusion", samples=16, only_local=False)
        self._in(ao, "Distance", distance)
        return _sock(ao.outputs, "AO")

    def bump(self, height, strength, distance=0.02, normal=None):
        n = self.node("ShaderNodeBump")
        self._in(n, "Strength", strength)
        self._in(n, "Distance", distance)
        self._in(n, "Height", height)
        if normal is not None:
            self._in(n, "Normal", normal)
        return _sock(n.outputs, "Normal")


def new_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, Graph(mat)


def finish(mat, g, color, metallic, roughness, normal=None, emission=None):
    """Wires a Principled BSDF and records the signals the baker needs."""
    p = g.node("ShaderNodeBsdfPrincipled")
    out = g.node("ShaderNodeOutputMaterial")
    g._in(p, "Base Color", color)
    g._in(p, "Metallic", metallic)
    g._in(p, "Roughness", roughness)
    if normal is not None:
        g._in(p, "Normal", normal)
    g.links.new(p.outputs[0], out.inputs["Surface"])
    mat["_bake"] = True
    BAKE[mat.name] = dict(
        principled=p, output=out, color=color if hasattr(color, "is_output") else g.rgb(color),
        metallic=metallic if hasattr(metallic, "is_output") else g.value(metallic),
        emission=emission if emission is None or hasattr(emission, "is_output") else g.rgb(emission))
    return mat


BAKE = {}


def wear_layers(g, base, edge_width=0.006, chip=0.5, grime=0.6, rust=0.35, dirt_height=0.35, bare=(0.42, 0.42, 0.42)):
    """Edge wear to bare metal, grime in crevices and near the ground, rust patches. Returns color, metallic,
    roughness and a height signal for bump."""
    co = g.coords()
    z = g.separate(co)[2]
    edge = g.edges(edge_width)
    chips = g.noise(28.0, detail=6.0, roughness=0.7)
    lo = 0.22 - 0.1 * chip
    edge_mask = g.ramp(g.math("MULTIPLY", edge, g.math("ADD", chips, 0.35)), lo, lo + 0.12)
    cav = g.cavity(0.06)
    low = g.ramp(z, -0.5 + dirt_height, -0.5, smooth_step=True)
    grime_mask = g.math("MULTIPLY", g.math("ADD", g.math("SUBTRACT", 1.0, cav, clamp=True), g.math("MULTIPLY", low, 0.6)),
                        grime, clamp=True)
    grime_mask = g.math("MULTIPLY", grime_mask, g.ramp(g.noise(6.0, detail=5.0), 0.25, 0.7))
    rust_mask = g.math("MULTIPLY", g.ramp(g.noise(4.0, detail=8.0, roughness=0.65, distortion=0.4), 0.62, 0.72),
                       rust * 2.0, clamp=True)
    rust_mask = g.math("MAXIMUM", rust_mask, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), rust))
    tone = g.noise(14.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", tone, 0.35), base, _darker(g, base, 0.72))
    col = g.mix(rust_mask, col, (0.23, 0.10, 0.045))
    col = g.mix(grime_mask, col, (0.045, 0.038, 0.03))
    col = g.mix(edge_mask, col, bare)
    metal = g.math("MULTIPLY", edge_mask, g.math("SUBTRACT", 1.0, rust_mask, clamp=True))
    rough = g.mixf(rust_mask, g.math("ADD", 0.5, g.math("MULTIPLY", tone, 0.15)), 0.88)
    rough = g.mixf(grime_mask, rough, 0.82)
    rough = g.mixf(edge_mask, rough, 0.38)
    height = g.math("ADD", g.math("MULTIPLY", g.noise(60.0, detail=4.0), 0.25),
                    g.math("MULTIPLY", rust_mask, g.noise(30.0, detail=6.0)))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", edge_mask, 0.6))
    return col, metal, rough, height


def _darker(g, base, f):
    if hasattr(base, "is_output"):
        return _multiply_color(g, base, (f, f, f))
    return tuple(c * f for c in base)


def painted_metal(name, paint, **kw):
    mat, g = new_material(name)
    col, metal, rough, height = wear_layers(g, paint, **kw)
    return finish(mat, g, col, metal, rough, g.bump(height, 0.25, 0.004))


def hazard_stripes(name, stripes=10.0):
    """Yellow and black diagonal stripes around the Z axis, worn like the paint."""
    mat, g = new_material(name)
    x, y, z = g.separate(g.coords())
    ang = g.math("DIVIDE", g.math("ARCTAN2", y, x), 2 * math.pi)
    t = g.math("FRACT", g.math("ADD", g.math("MULTIPLY", ang, stripes), g.math("MULTIPLY", z, stripes * 1.6)))
    band = g.ramp(t, 0.48, 0.52)
    base = g.mix(band, (0.78, 0.55, 0.05), (0.02, 0.02, 0.02))
    col, metal, rough, height = wear_layers(g, base, rust=0.2)
    return finish(mat, g, col, metal, rough, g.bump(height, 0.2, 0.004))


def copper(name, patina=0.35):
    mat, g = new_material(name)
    cav = g.cavity(0.04)
    ox = g.ramp(g.noise(9.0, detail=6.0, distortion=0.3), 0.5, 0.75)
    ox = g.math("MAXIMUM", ox, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.5), clamp=True)
    ox = g.math("MULTIPLY", ox, patina, clamp=True)
    tone = g.noise(40.0, detail=3.0)
    col = g.mix(g.math("MULTIPLY", tone, 0.3), (0.93, 0.52, 0.33), (0.75, 0.36, 0.2))
    col = g.mix(ox, col, (0.18, 0.09, 0.05))
    col = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), patina * 1.2, clamp=True),
                col, (0.16, 0.32, 0.24))
    metal = g.math("SUBTRACT", 1.0, ox, clamp=True)
    rough = g.mixf(ox, g.math("ADD", 0.22, g.math("MULTIPLY", tone, 0.15)), 0.7)
    return finish(mat, g, col, metal, rough, g.bump(g.noise(80.0), 0.08, 0.002))


def glazed(name, color):
    mat, g = new_material(name)
    cav = g.cavity(0.03)
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.2, clamp=True)
    col = g.mix(dirt, color, (0.05, 0.035, 0.025))
    col = g.mix(g.math("MULTIPLY", g.noise(12.0), 0.3), col, tuple(c * 0.8 for c in color))
    rough = g.mixf(dirt, 0.12, 0.6)
    return finish(mat, g, col, 0.0, rough)


def aluminum(name, scorch=0.5):
    mat, g = new_material(name)
    tone = g.noise(6.0, detail=5.0)
    smudge = g.ramp(g.noise(3.0, detail=6.0, distortion=0.5), 0.45, 0.7)
    burn = g.math("MULTIPLY", g.ramp(g.noise(5.0, detail=8.0, distortion=0.8), 0.6, 0.72), scorch)
    col = g.mix(g.math("MULTIPLY", tone, 0.25), (0.86, 0.87, 0.89), (0.7, 0.71, 0.73))
    col = g.mix(burn, col, (0.12, 0.1, 0.11))
    rough = g.mixf(smudge, 0.18, 0.42)
    rough = g.mixf(burn, rough, 0.75)
    metal = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", burn, 0.8))
    return finish(mat, g, col, metal, rough, g.bump(g.noise(120.0), 0.03, 0.002))


def plain(name, color, metallic=0.0, roughness=0.6, grime=0.5, emission=None):
    mat, g = new_material(name)
    cav = g.cavity(0.04)
    dirt = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), grime * 2.0, clamp=True)
    col = g.mix(g.math("MULTIPLY", g.noise(20.0), 0.25), color, tuple(c * 0.75 for c in color))
    col = g.mix(dirt, col, (0.03, 0.025, 0.02))
    rough = g.mixf(dirt, roughness, 0.85)
    return finish(mat, g, col, metallic, rough, g.bump(g.noise(50.0), 0.05, 0.003), emission=emission)


# ---------------------------------------------------------------- photo materials

TEXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
# Poly Haven sets (CC0) downloaded by src/fetch-textures.ps1; keep the two lists in step
PHOTO = ["rusty_painted_metal", "green_metal_rust", "container_side", "metal_plate_02", "rust_coarse_01",
         "worn_corrugated_iron", "weathered_planks"]


def _photo_node(g, set_name, kind, scale, non_color, offset):
    path = os.path.join(TEXTURES, set_name, "{0}_{1}_2k.jpg".format(set_name, kind))
    if not os.path.exists(path):
        raise FileNotFoundError(path + " is missing; run src/fetch-textures.ps1")
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    n = g.node("ShaderNodeTexImage", projection="BOX", projection_blend=0.3, interpolation="Cubic")
    n.image = img
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Location"].default_value = offset
    m.inputs["Scale"].default_value = (scale, scale, scale)
    g.links.new(m.outputs[0], n.inputs["Vector"])
    return n


def photo(g, set_name, scale=0.5, offset=(0.0, 0.0, 0.0)):
    """A photo set box-projected in object space: color, AO, roughness, metal and height signals."""
    col = _photo_node(g, set_name, "diff", scale, False, offset).outputs["Color"]
    arm = g.node("ShaderNodeSeparateColor")
    g.links.new(_photo_node(g, set_name, "arm", scale, True, offset).outputs["Color"], arm.inputs[0])
    height = _photo_node(g, set_name, "disp", scale, True, offset).outputs["Color"]
    return dict(color=col, ao=arm.outputs[0], rough=arm.outputs[1], metal=arm.outputs[2], height=height)


def grade(g, color, sat=1.0, value=1.0, tint=None):
    n = g.node("ShaderNodeHueSaturation")
    g._in(n, "Saturation", sat)
    g._in(n, "Value", value)
    g._in(n, "Color", color)
    out = n.outputs[0]
    return _multiply_color(g, out, tint) if tint else out


def _luma(g, color):
    n = g.node("ShaderNodeRGBToBW")
    g.links.new(color, n.inputs[0])
    return n.outputs[0]


def _grime(g, grime, ground=0.3):
    """Dirt in crevices and toward the ground, broken up with noise."""
    cav = g.ramp(g.cavity(0.1), 0.35, 1.0)
    z = g.separate(g.coords())[2]
    low = g.ramp(z, -0.5 + ground, -0.5)
    dirt = g.math("MULTIPLY", g.math("ADD", g.math("SUBTRACT", 1.0, cav, clamp=True), g.math("MULTIPLY", low, 0.5)),
                  grime, clamp=True)
    return g.math("MULTIPLY", dirt, g.ramp(g.noise(5.0, detail=5.0), 0.2, 0.7))


def _grit(g, color, rough, metal, grit, scratches=0.0, edges=0.0):
    """The fine wear vanilla models have all over: scratches through the paint (thin contour lines of stretched
    noise), bright worn edges, dust settled on upward faces, and dark dirt specks. Each amount is 0-1."""
    if scratches:
        sc = None
        for k, (scale, rot) in enumerate((((70.0, 70.0, 14.0), (0.3, 0.9, 0.2)), ((120.0, 120.0, 22.0), (1.1, 0.2, 1.4)))):
            m = g.node("ShaderNodeMapping")
            g.links.new(g.coords(), m.inputs["Vector"])
            m.inputs["Scale"].default_value = scale
            m.inputs["Rotation"].default_value = rot
            m.inputs["Location"].default_value = (0.3 * k, 0.7 * k, 0.1 * k)
            n = g.noise(1.0, detail=1.0, roughness=0.3, vector=m.outputs[0])
            line = g.math("SUBTRACT", 1.0, g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", n, 0.5)), 0.0, 0.012, False))
            sc = line if sc is None else g.math("MAXIMUM", sc, line)
        density = g.ramp(g.noise(4.0, detail=3.0), 0.42, 0.62)
        sc = g.math("MULTIPLY", g.math("MULTIPLY", sc, density), scratches)
        color = g.mix(sc, color, (0.42, 0.41, 0.39))
        metal = g.mixf(sc, metal, 0.85)
        rough = g.mixf(sc, rough, 0.45)
    if edges:
        worn = g.math("MULTIPLY", g.ramp(g.edges(0.003), 0.12, 0.3), g.ramp(g.noise(30.0, detail=4.0), 0.35, 0.55))
        worn = g.math("MULTIPLY", worn, edges)
        color = g.mix(worn, color, (0.5, 0.49, 0.47))
        metal = g.mixf(worn, metal, 0.9)
        rough = g.mixf(worn, rough, 0.35)
    if grit:
        up = g.separate(_sock(g.node("ShaderNodeNewGeometry").outputs, "Normal"))[2]
        dust = g.math("MULTIPLY", g.ramp(up, 0.45, 0.9), g.ramp(g.noise(9.0, detail=6.0, roughness=0.6), 0.3, 0.65))
        dust = g.math("MULTIPLY", dust, grit)
        color = g.mix(dust, color, (0.36, 0.31, 0.24))
        rough = g.mixf(dust, rough, 0.95)
        metal = g.mixf(dust, metal, 0.0)
        vor = g.node("ShaderNodeTexVoronoi")
        g._in(vor, "Scale", 160.0)
        g.links.new(g.coords(), vor.inputs["Vector"])
        spots = g.ramp(_sock(vor.outputs, "Distance"), 0.18, 0.08)
        specks = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.ramp(g.noise(7.0, detail=4.0), 0.4, 0.6)), 0.85 * grit)
        color = g.mix(specks, color, (0.03, 0.025, 0.02))
        rough = g.mixf(specks, rough, 0.9)
        grime_fine = g.math("MULTIPLY", g.ramp(g.noise(45.0, detail=8.0, roughness=0.75), 0.5, 0.7), 0.5 * grit)
        color = g.mix(grime_fine, color, _darker(g, color, 0.55))
    return color, rough, metal


def _streaks(g, amount):
    m = g.node("ShaderNodeMapping")
    g.links.new(g.coords(), m.inputs["Vector"])
    m.inputs["Scale"].default_value = (16.0, 16.0, 0.9)
    return g.math("MULTIPLY", g.ramp(g.noise(1.0, detail=4.0, vector=m.outputs[0]), 0.55, 0.78), amount)


def photo_material(name, base, scale=0.5, sat=1.0, value=1.0, tint=None, exposed="rust_coarse_01", chip=0.5,
                   grime=0.6, streaks=0.0, offset=(0.0, 0.0, 0.0), metal_scale=1.0, bump=0.35, ao=0.6, patches=0.0,
                   metal_floor=0.0, rough_scale=1.0, grit=0.0, scratches=0.0, edges=0.0, contrast=0.0):
    """A photo-scanned surface, graded, with paint chipped through to `exposed` at the edges (and in blotchy
    patches, 0-1), crevice and ground grime, and optional rust streaks running down."""
    mat, g = new_material(name)
    p = photo(g, base, scale, offset)
    color = grade(g, p["color"], sat, value, tint)
    if contrast:
        bc = g.node("ShaderNodeBrightContrast")
        g._in(bc, "Color", color)
        g._in(bc, "Contrast", contrast)
        color = bc.outputs[0]
    rough = p["rough"]
    metal = g.math("MULTIPLY", p["metal"], metal_scale)
    height = p["height"]
    if exposed:
        e = photo(g, exposed, scale * 1.3, (0.37, 0.11, 0.73))
        edge = g.edges(0.006)
        chips = g.noise(22.0, detail=6.0, roughness=0.7)
        lo = 0.22 - 0.1 * chip
        mask = g.ramp(g.math("MULTIPLY", edge, g.math("ADD", chips, 0.35)), lo, lo + 0.12)
        if patches:
            blotch = g.noise(2.5, detail=8.0, roughness=0.65, distortion=0.4)
            pm = g.ramp(blotch, 0.66 - 0.16 * patches, 0.7 - 0.16 * patches)
            pm = g.math("MAXIMUM", pm, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.cavity(0.05), clamp=True),
                                              patches * 1.5, clamp=True))
            mask = g.math("MAXIMUM", mask, pm)
        color = g.mix(mask, color, e["color"])
        rough = g.mixf(mask, rough, e["rough"])
        metal = g.mixf(mask, metal, e["metal"])
        height = g.mixf(mask, height, g.math("MULTIPLY", e["height"], 0.5))
    dirt = _grime(g, grime)
    color = g.mix(dirt, color, (0.035, 0.028, 0.02))
    rough = g.mixf(dirt, rough, 0.85)
    if streaks:
        color = g.mix(_streaks(g, streaks), color, (0.2, 0.1, 0.05))
    color = _multiply_color(g, color, g.mix(ao, (1.0, 1.0, 1.0), p["ao"]))
    if metal_floor:
        # Vanilla models treat painted and rusty metal as part-metallic; dirt stays dielectric
        metal = g.math("MAXIMUM", metal, g.math("MULTIPLY", metal_floor, g.math("SUBTRACT", 1.0, dirt, clamp=True)))
    if rough_scale != 1.0:
        rough = g.math("MULTIPLY", rough, rough_scale, clamp=True)
    color, rough, metal = _grit(g, color, rough, metal, grit, scratches, edges)
    return finish(mat, g, color, metal, rough, g.bump(height, bump, 0.01))


def grimy(name, color, roughness=0.55, metallic=0.0, grime=0.5, grime_set="metal_plate_02", scale=0.7,
          emission=None, bump_scale=60.0, bump=0.08, soot_from=None, stain=None, grit=0.0, dirt_range=(0.4, 0.12)):
    """A plain surface (plastic, rubber, tape, porcelain) dirtied with the dark parts of a photo set, optionally
    sooted above height soot_from (model space) and blotched with a stain color. dirt_range is the photo
    brightness (linear) from clean to fully dirty; the default dirties most of a dark photo, which suits greys,
    while strong colors want a narrower range such as (0.1, 0.03) so they survive."""
    mat, g = new_material(name)
    p = photo(g, grime_set, scale, (0.21, 0.5, 0.13))
    pattern = g.ramp(_luma(g, p["color"]), dirt_range[0], dirt_range[1])
    dirt = g.math("MAXIMUM", g.math("MULTIPLY", pattern, grime), _grime(g, grime * 1.4), clamp=True)
    col = g.mix(g.math("MULTIPLY", g.noise(18.0), 0.25), color, _darker(g, color, 0.8))
    if stain is not None:
        col = g.mix(g.ramp(g.noise(3.0, detail=6.0, distortion=0.5), 0.45, 0.75), col, stain)
    col = g.mix(dirt, col, (0.06, 0.05, 0.04))
    if soot_from is not None:
        zz = g.separate(g.coords())[2]
        soot = g.math("MULTIPLY", g.ramp(zz, soot_from, soot_from + 0.35), g.ramp(g.noise(8.0, detail=6.0), 0.3, 0.6))
        col = g.mix(g.math("MULTIPLY", soot, 0.85), col, (0.03, 0.028, 0.027))
        dirt = g.math("MAXIMUM", dirt, soot)
    rough = g.mixf(dirt, roughness, 0.85)
    col, rough, metal = _grit(g, col, rough, metallic, grit)
    return finish(mat, g, col, metal, rough, g.bump(g.noise(bump_scale, detail=6.0), bump, 0.003),
                  emission=emission)


def tarnished_copper(name, bright=(0.85, 0.45, 0.24), dark=(0.6, 0.28, 0.14)):
    """Old plumbing copper (or brass, with yellower colors): dull, with dark tarnish patches and green verdigris
    in the crevices."""
    mat, g = new_material(name)
    p = photo(g, "rust_coarse_01", 1.2, (0.4, 0.2, 0.9))
    tarnish = g.ramp(_luma(g, p["color"]), 0.2, 0.1)
    cav = g.cavity(0.04)
    col = g.mix(g.math("MULTIPLY", g.noise(30.0), 0.4), bright, dark)
    col = g.mix(g.math("MULTIPLY", tarnish, 0.9), col, (0.13, 0.07, 0.04))
    green = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, cav, clamp=True), 1.3, clamp=True)
    col = g.mix(g.math("MULTIPLY", green, 0.75), col, (0.12, 0.24, 0.17))
    metal = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("MAXIMUM", tarnish, green), 0.75))
    rough = g.mixf(tarnish, g.math("ADD", 0.26, g.math("MULTIPLY", g.noise(12.0), 0.2)), 0.7)
    return finish(mat, g, col, metal, rough, g.bump(p["height"], 0.15, 0.004))


def foil(name, ridges=0, scorch=1.0, smooth_tape=False):
    """Aluminum dryer duct (or foil tape): crinkled, dulled, scorched where arcs have hit it."""
    mat, g = new_material(name)
    x, y, z = g.separate(g.coords())
    crinkle = g.noise(70.0 if smooth_tape else 110.0, detail=8.0, roughness=0.7, distortion=0.6)
    height = g.math("MULTIPLY", crinkle, 0.25 if smooth_tape else 0.6)
    if ridges:
        ang = g.math("ARCTAN2", y, x)
        rid = g.math("SINE", g.math("MULTIPLY", ang, float(ridges)))
        height = g.math("ADD", height, g.math("MULTIPLY", rid, 0.8))
    p = photo(g, "metal_plate_02", 0.9, (0.6, 0.3, 0.2))
    dirt = g.math("MAXIMUM", g.ramp(_luma(g, p["color"]), 0.38, 0.12), _grime(g, 0.5))
    burn_noise = g.noise(4.0, detail=8.0, distortion=0.9)
    burn = g.math("MULTIPLY", g.ramp(burn_noise, 0.5, 0.62), scorch)
    halo = g.math("MULTIPLY", g.ramp(burn_noise, 0.4, 0.52), scorch)
    tone = g.math("MULTIPLY", crinkle, 0.5)
    col = g.mix(tone, (0.66, 0.67, 0.68), (0.46, 0.47, 0.49))
    col = g.mix(dirt, col, (0.1, 0.09, 0.08))
    col = g.mix(g.math("MULTIPLY", halo, 0.5), col, (0.26, 0.22, 0.17))
    col = g.mix(burn, col, (0.07, 0.06, 0.06))
    metal = g.math("SUBTRACT", 1.0, g.math("MAXIMUM", g.math("MULTIPLY", burn, 0.8), g.math("MULTIPLY", dirt, 0.5)))
    rough = g.mixf(dirt, g.math("ADD", 0.28, g.math("MULTIPLY", crinkle, 0.25)), 0.75)
    rough = g.mixf(burn, rough, 0.8)
    col, rough, metal = _grit(g, col, rough, metal, 0.8)
    return finish(mat, g, col, metal, rough, g.bump(height, 0.5, 0.003))


def glow(name, color, strength, alpha=1.0):
    """Unlit emissive, optionally see-through (for the icon's arcs)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def bolt(name, start, end, seed, core, halo, radius=0.004, roughness=0.12, branches=1):
    """A jagged lightning bolt (core plus a soft halo tube), for the icon."""
    import random
    rnd = random.Random(seed)
    a, b = Vector(start), Vector(end)
    n = 14
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        if 0 < i < n:
            amp = (b - a).length * roughness * math.sin(t * math.pi)
            p += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * amp
        pts.append(tuple(p))
    objs = [tube(name, pts, radius, core, resolution=2), tube(name + "Halo", pts, radius * 3, halo, resolution=3)]
    for k in range(branches):
        i = rnd.randint(4, n - 4)
        p = Vector(pts[i])
        tip = p + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.6))) * (b - a).length * 0.35
        objs += bolt(name + "Branch%d" % k, p, tip, seed + 17 + k, core, halo, radius * 0.6, roughness, 0)
    return objs


# ---------------------------------------------------------------- UVs, bake, export

def cylinder_uvs(obj, z0, z1, v_repeat):
    """u around the Z axis, v along it (v_repeat tiles over the height), for tiling textures."""
    me = obj.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            us.append((math.atan2(co.y, co.x) / (2 * math.pi)) % 1.0)
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u in zip(poly.loop_indices, us):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (u, (co.z - z0) / (z1 - z0) * v_repeat)


def smart_uvs(obj, margin=0.004):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    for o in bpy.context.scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _new_image(name, size, non_color, alpha=False):
    img = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def _target(obj, img):
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        n = nt.nodes.get("_bake_target") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "_bake_target"
        n.image = img
        nt.nodes.active = n


def _bake(obj, kind, img, samples, **kw):
    _target(obj, img)
    scene = bpy.context.scene
    scene.cycles.samples = samples
    for o in scene.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type=kind, margin=16, margin_type="EXTEND", use_clear=True, **kw)


def _with_emission(obj, which, fn):
    """Temporarily routes a recorded signal (metallic or emission) into an Emission shader for an EMIT bake."""
    saved = []
    for slot in obj.material_slots:
        mat = slot.material
        info = BAKE[mat.name]
        nt = mat.node_tree
        em = nt.nodes.new("ShaderNodeEmission")
        src = info[which]
        if src is None:
            em.inputs["Color"].default_value = (0, 0, 0, 1)
        else:
            nt.links.new(src, em.inputs["Color"])
        em.inputs["Strength"].default_value = 1.0
        out = info["output"]
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        saved.append((nt, em, info))
    fn()
    for nt, em, info in saved:
        nt.links.new(info["principled"].outputs[0], info["output"].inputs["Surface"])
        nt.nodes.remove(em)


def _pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def _save(img, path, rgba=False):
    img.filepath_raw = path
    img.file_format = "PNG"
    bpy.context.scene.render.image_settings.color_mode = "RGBA" if rgba else "RGB"
    img.save()


def save_array(name, arr, path, non_color):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.alpha_mode = "STRAIGHT"
    _save(img, path, rgba=True)
    return img


def rmom(rough, metal, occlusion=None):
    """The game's packed map for model shaders (Game/Entity Tint Mask): R roughness, G metallic, B occlusion,
    A tint mask (unused, 1)."""
    out = np.ones(rough.shape[:2] + (4,), dtype=np.float32)
    out[..., 0] = rough
    out[..., 1] = metal
    if occlusion is not None:
        out[..., 2] = occlusion
    return out


def bake_atlas(obj, out_dir, prefix, size=TEX_SIZE):
    """Bakes albedo, normal, RMOM (roughness, metallic, occlusion) and emission maps for the atlas object."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.bake.normal_space = "TANGENT"
    paths = {}

    # Through emission: Cycles' diffuse color pass is black on metals
    img = _new_image(prefix + "_Albedo", size, False)
    _with_emission(obj, "color", lambda: _bake(obj, "EMIT", img, 64))
    paths["albedo"] = os.path.join(out_dir, prefix + "_Albedo.png")
    _save(img, paths["albedo"])

    nrm = _new_image(prefix + "_Normal", size, True)
    _bake(obj, "NORMAL", nrm, 16)
    paths["normal"] = os.path.join(out_dir, prefix + "_Normal.png")
    _save(nrm, paths["normal"])

    rough = _new_image(prefix + "_Rough", size, True)
    _bake(obj, "ROUGHNESS", rough, 16)
    metal = _new_image(prefix + "_Metal", size, True)
    _with_emission(obj, "metallic", lambda: _bake(obj, "EMIT", metal, 4))
    ao = _new_image(prefix + "_AO", size, True)
    scene.world.light_settings.distance = 0.25
    _bake(obj, "AO", ao, 128)
    paths["rmom"] = os.path.join(out_dir, prefix + "_RMOM.png")
    save_array(prefix + "_RMOMMap", rmom(_pixels(rough)[..., 0], _pixels(metal)[..., 0], _pixels(ao)[..., 0]),
               paths["rmom"], True)

    if any(BAKE[s.material.name]["emission"] is not None for s in obj.material_slots):
        em = _new_image(prefix + "_Emission", size, False)
        _with_emission(obj, "emission", lambda: _bake(obj, "EMIT", em, 4))
        paths["emission"] = os.path.join(out_dir, prefix + "_Emission.png")
        _save(em, paths["emission"])
    return paths


def baked_material(name, paths, emission_strength=0.0):
    """A material that shows the baked maps (albedo, normal, RMOM) for the preview renders."""
    mat, g = new_material(name)
    p = g.node("ShaderNodeBsdfPrincipled")
    out = g.node("ShaderNodeOutputMaterial")
    uv = _sock(g.node("ShaderNodeTexCoord").outputs, "UV")

    def tex(path, non_color):
        n = g.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        g.links.new(uv, n.inputs["Vector"])
        return n

    alb = tex(paths["albedo"], False)
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tex(paths["rmom"], True).outputs["Color"], sep.inputs[0])
    g._in(p, "Base Color", _multiply_color(g, alb.outputs["Color"], g.mix(1.0, (1.0, 1.0, 1.0), sep.outputs[2])))
    g._in(p, "Roughness", sep.outputs[0])
    g._in(p, "Metallic", sep.outputs[1])
    nm = g.node("ShaderNodeNormalMap")
    g.links.new(tex(paths["normal"], True).outputs["Color"], nm.inputs["Color"])
    g._in(p, "Normal", nm.outputs["Normal"])
    if "emission" in paths and emission_strength > 0:
        g._in(p, "Emission Color", tex(paths["emission"], False).outputs["Color"])
        g._in(p, "Emission Strength", emission_strength)
    g.links.new(p.outputs[0], out.inputs["Surface"])
    return mat


def _multiply_color(g, a, b):
    n = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    g._in(n, "Factor_Float", 1.0)
    g._in(n, "A_Color", a)
    g._in(n, "B_Color", b)
    return _sock(n.outputs, "Result_Color")


def export_fbx(objs, path):
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z",
                             axis_up="Y", bake_space_transform=True, mesh_smooth_type="OFF", use_tspace=False,
                             add_leaf_bones=False, bake_anim=False, use_custom_props=False, path_mode="STRIP")


# ---------------------------------------------------------------- previews

def preview_stage(height=2.0):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Stage")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.6, 0.68, 1)
    bg.inputs["Strength"].default_value = 0.7
    scene.world = world
    sun = link(bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    fill = link(bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA")))
    fill.data.energy = 120
    fill.data.size = 3
    fill.location = (-2.5, 2.5, 2.0)
    fill.rotation_euler = (math.radians(60), 0, math.radians(-135))

    mat, g = new_material("Floor")
    x, y, _ = g.separate(g.coords())
    gx = g.ramp(g.math("PINGPONG", x, 0.5), 0.0, 0.012)
    gy = g.ramp(g.math("PINGPONG", y, 0.5), 0.0, 0.012)
    line = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gx, gy))
    finish(mat, g, g.mix(line, (0.32, 0.31, 0.3), (0.12, 0.12, 0.12)), 0.0, 0.8)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6.0)
    bmesh.ops.translate(bm, vec=(0, 0, -0.5), verts=bm.verts)
    mesh_object("Floor", bm, mat)

    # A 1.8 m figure for scale
    dummy, g = new_material("Dummy")
    finish(dummy, g, (0.25, 0.3, 0.38), 0.0, 0.7)
    cylinder("ScaleFigure", 0.18, -0.5, 1.3, dummy, segments=24, center=(1.1, 0.6))
    cylinder("ScaleHead", 0.11, 1.3, 1.52, dummy, segments=24, center=(1.1, 0.6))


def camera(name, location, target, lens=50, ortho=None):
    from mathutils import Vector
    cam = link(bpy.data.objects.new(name, bpy.data.cameras.new(name)))
    cam.location = location
    d = Vector(target) - Vector(location)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    return cam


def render(cam, path, res=(1000, 750), samples=96, transparent=False):
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def icon(cam, path, hide, extra=(), target=(0.0, 0.0, 0.3)):
    """Renders the item icon the way the vanilla ones look: transparent background, a warm key light from the upper
    left, a cool rim from behind and little fill, at 480 px scaled to the game's 160x160. `hide` names objects left
    out; `extra` objects (icon-only effects such as arcs, kept hidden elsewhere) are shown only here."""
    scene = bpy.context.scene
    hidden = [o for o in scene.objects if o.name in hide or o.type == "LIGHT"]
    for o in hidden:
        o.hide_render = True
    for o in extra:
        o.hide_render = False
    rig = []
    for name, color, energy, size, loc in (("IconKey", (1.0, 0.9, 0.78), 260.0, 1.6, (-2.2, -2.6, 2.8)),
                                           ("IconRim", (0.7, 0.8, 1.0), 220.0, 1.2, (2.0, 2.4, 2.2)),
                                           ("IconFill", (0.9, 0.9, 1.0), 40.0, 3.0, (2.6, -2.0, 0.2))):
        light = link(bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA")))
        light.data.color = color
        light.data.energy = energy
        light.data.size = size
        light.location = loc
        _aim(light, target)
        rig.append(light)
    strength = scene.world.node_tree.nodes["Background"].inputs["Strength"]
    saved = strength.default_value
    strength.default_value = 0.15

    tmp = path + ".full.png"
    render(cam, tmp, res=(480, 480), samples=160, transparent=True)
    img = bpy.data.images.load(tmp)
    img.scale(160, 160)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    os.remove(tmp)

    strength.default_value = saved
    for light in rig:
        bpy.data.objects.remove(light)
    for o in hidden:
        o.hide_render = False
    for o in extra:
        o.hide_render = True
