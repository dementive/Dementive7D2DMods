"""Nature Expanded's tree kit, on top of zkit.py: one generator for every tree species (paper birch first; aspen,
maples, Douglas fir, larch, white pine, cottonwood, willow, mesquite, palo verde, Joshua tree, subalpine fir and
charred snags after it). TREES.md has the rules and the species table; birch.py is the worked example.

Trees are not block models like the plants: Blender meters, Z up, the ground at z = 0 and the trunk's base at the
origin. The game draws them with its own SpeedTree shader (Game/SpeedTree8, "palm" wind like vanilla's oaks, alpha
cutout at 0.5); the Unity side (NatureTreeBuilder) computes its per-vertex wind and occlusion from the geometry:
branch sway from the distance out from the trunk, leaf flutter per card (so every card stays its own connected
patch of faces), occlusion from the depth in the crown. Bark is drawn single-sided, so trunks and branches are
closed tubes with outward normals; leaf cards are single-sided quads the SpeedTree material draws from both sides.

A tree is built in four steps:

- `grow(spec, seed)`: a skeleton of Branch polylines from a TreeSpec: Trunk (one, or a clump), then one Level per
  order of branching (limbs off the trunk, branches off the limbs...) with length, angle, phyllotaxis, gravitropism
  and droop, taper, curvature noise and forks, and the crown's shape over each span. `Foliage` then places leaf cards
  on the outer twigs, facing out, up and down with a random roll; `Scars` puts decals where branches leave.
- Textures, once per species: tileable bark made with numpy (`fbm`, `blur`, `lens`, `stamp`, `normal_map`,
  `cavity`, `write_png`), and an `Atlas` of leaf sprays rendered from real 3D leaves (`Mesh`, `blade`, `twig`;
  `Atlas.render` draws albedo, normal, roughness and occlusion with alpha through `render_passes`).
- `build_lods(tree, materials)`: the meshes of LOD0, 1 and 2. LODs prune rather than decimate: coarser tubes, small
  branches dropped, cards thinned and grown (LOD1) or swapped for cluster cards (LOD2), within the triangle budget.
  Bark UVs run u once round each tube (the seam on shared vertices, so normals stay smooth across it) and v by
  length over radius, so a tiling bark texture keeps square texels on every branch.
- `impostor(...)`: LOD3, three crossed quads showing a side view of LOD0; `export_tree` writes the FBX,
  `write_sizes` the tree's line of trees.txt, and `stage` / `preview_*` the review renders.
"""
import bisect
import math
import os
import random
import struct
import zlib

import bpy
import numpy as np
from mathutils import Matrix, Vector

import zkit as tk

UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))
TAU = math.tau
GOLDEN = 2.39996323


def reset():
    """A fresh scene (Cycles on the GPU, as zkit sets it up) with room for many layers of cutout leaves."""
    scene = tk.reset_scene()
    scene.cycles.transparent_max_bounces = 128
    SIG.clear()
    return scene


def _set(obj, kw, label):
    for k, v in kw.items():
        if not hasattr(obj, k):
            raise TypeError("%s has no setting %r" % (label, k))
        setattr(obj, k, v)


def basis(axis):
    """(axis, u, v) with u x v = axis: a ring u cos(a) + v sin(a) runs counter-clockwise round the axis."""
    ax = Vector(axis).normalized()
    u = ax.cross(UP)
    if u.length < 1e-4:
        u = ax.cross(Vector((1.0, 0.0, 0.0)))
    u.normalize()
    return ax, u, ax.cross(u)


def rotate(vec, axis, degrees):
    return Matrix.Rotation(math.radians(degrees), 3, Vector(axis).normalized()) @ Vector(vec)


def frames(points):
    """Parallel-transport frames (tangent, normal, binormal; normal x binormal = tangent) along a polyline, so tubes
    don't twist."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    tans = []
    for i in range(n):
        d = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        tans.append(d.normalized() if d.length > 1e-9 else UP.copy())
    nrm = tans[0].cross(UP)
    if nrm.length < 1e-4:
        nrm = tans[0].cross(Vector((1.0, 0.0, 0.0)))
    nrm.normalize()
    out = []
    for i, t in enumerate(tans):
        if i:
            nrm = tans[i - 1].rotation_difference(t) @ nrm
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


# ---------------------------------------------------------------- tileable textures (numpy)
#
# Images are arrays (rows, columns[, channels]) with row 0 at the bottom, Blender's pixel order, so v and a normal
# map's +Y run up the rows. Everything wraps round the edges, so a texture made with these tiles both ways. Albedo
# work is done in sRGB values (what the PNG stores), data maps in linear.

def _freq(h, w):
    return np.fft.fftfreq(w)[None, :], np.fft.fftfreq(h)[:, None]


def blur(a, sx, sy=None):
    """A gaussian blur, sigma `sx` pixels across and `sy` up (default the same), wrapping round the edges."""
    sy = sx if sy is None else sy
    if a.ndim == 3:
        return np.stack([blur(a[..., c], sx, sy) for c in range(a.shape[2])], -1)
    fx, fy = _freq(*a.shape)
    k = np.exp(-2.0 * math.pi ** 2 * ((fx * sx) ** 2 + (fy * sy) ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * k))


def normalize(a, lo=0.5, hi=99.5):
    """Stretches an array to 0-1 between two percentiles."""
    p0, p1 = np.percentile(a, [lo, hi])
    return np.clip((a - p0) / max(p1 - p0, 1e-9), 0.0, 1.0)


def fbm(r, h, w, size, octaves=4, gain=0.5):
    """Tileable fractal noise in 0-1 (h x w), its coarsest features about `size` pixels across (a number, or
    (across, up) to stretch them: (80, 4) makes long horizontal streaks), each of `octaves` finer layers half the
    size and `gain` times as strong. `r` is a numpy Generator."""
    sx, sy = (size, size) if np.isscalar(size) else size
    out = np.zeros((h, w))
    amp = 1.0
    for _ in range(octaves):
        n = blur(r.standard_normal((h, w)), sx * 0.3, sy * 0.3)
        out += n / (n.std() + 1e-12) * amp
        amp *= gain
        sx, sy = sx * 0.5, sy * 0.5
    return normalize(out)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    """From a to b by t: colors (3 numbers) or images, t a number or a mask image."""
    a, b, t = np.asarray(a, float), np.asarray(b, float), np.asarray(t, float)
    if t.ndim == 2 and max(a.ndim, b.ndim) != 2:
        t = t[..., None]
    return a + (b - a) * t


def cells(r, h, w, size, stretch=1.0, warp=None):
    """Tileable Voronoi cells (Worley noise), about `size` pixels across and `stretch` times as tall (tall plates of
    bark): for every pixel its distance in pixels to its cell's edge (the true distance, so an edge drawn as
    distance < width is as wide whichever way it runs), which cell it's in (an index, for a random value per cell:
    `r.random(index.max() + 1)[index]`) and that cell's point's height and place across in pixels (unwrapped: below
    row 0 under the bottom rows, left of column 0 left of it; with the warp, in the warped frame).
    `warp` = (dx, dy) arrays bend the edges."""
    gx = max(1, int(round(w / size)))
    gy = max(1, int(round(h / (size * stretch))))
    cw, ch = w / gx, h / gy
    pts = r.random((gy, gx, 2))
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    if warp is not None:
        X += warp[0]
        Y += warp[1]
    ix, iy = np.floor(X / cw), np.floor(Y / ch)
    # Nearest and next nearest point measured with heights squeezed by `stretch` (where the cells are round)
    f1 = np.full((h, w), np.inf)
    f2 = np.full((h, w), np.inf)
    p1x, p1y, p2x, p2y = (np.zeros((h, w)) for _ in range(4))
    index = np.zeros((h, w), np.int64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            jx = ((ix + dx) % gx).astype(np.int64)
            jy = ((iy + dy) % gy).astype(np.int64)
            px = (ix + dx + pts[jy, jx, 0]) * cw
            py = (iy + dy + pts[jy, jx, 1]) * ch
            d = np.hypot(px - X, (py - Y) / stretch)
            nearer = d < f1
            second = ~nearer & (d < f2)
            f2 = np.where(nearer, f1, np.where(second, d, f2))
            p2x = np.where(nearer, p1x, np.where(second, px, p2x))
            p2y = np.where(nearer, p1y, np.where(second, py, p2y))
            f1 = np.where(nearer, d, f1)
            p1x = np.where(nearer, px, p1x)
            p1y = np.where(nearer, py, p1y)
            index = np.where(nearer, jy * gx + jx, index)
    # The edge is the bisector of the two points in the squeezed space, a straight line in the real one too
    nx, ny = p2x - p1x, (p2y - p1y) / stretch ** 2
    c = nx * (p1x + p2x) * 0.5 + ny * (p1y + p2y) * 0.5
    edge = np.abs(c - nx * X - ny * Y) / np.maximum(np.hypot(nx, ny), 1e-9)
    return edge, index, p1y, p1x


def contour(noise, width):
    """Thin lines along the 0.5 contour of a noise field, `width` (in noise units) wide: cracks and fissures (smooth
    curves: at high resolution a crack network reads better from `cells`)."""
    return 1.0 - smoothstep(0.0, width, np.abs(noise - 0.5))


def lens(length, thick, dx=0.0, dy=0.0, ends=0.5, size=None):
    """A horizontal lens shape (a lenticel, a crack) `length` by `thick` pixels, as a kernel for `stamp`: 1 inside,
    anti-aliased at the edge, its ends tapering (`ends` 0 square, 0.5 elliptic, 1 pointed). dx, dy shift it by a
    fraction of a pixel; `size` = (rows, columns) fixes the kernel's size (odd numbers)."""
    kh, kw = size if size is not None else ((int(thick) + 5) | 1, (int(length) + 5) | 1)
    x = np.arange(kw) - (kw - 1) * 0.5 - dx
    y = np.arange(kh) - (kh - 1) * 0.5 - dy
    X, Y = np.meshgrid(x, y)
    along = np.clip(1.0 - (2.0 * np.abs(X) / max(length, 1e-3)) ** 2, 0.0, 1.0)
    half = thick * 0.5 * along ** ends
    return np.clip(half + 0.5 - np.abs(Y), 0.0, 1.0) * (along > 0)


def stamp(canvas, x, y, kernel, op=np.maximum):
    """Draws `kernel` into `canvas` centered on (x, y) in pixels, wrapping round the edges; `op` combines the two
    (np.maximum, np.minimum, np.add...). Kernels are odd-sized; pass the fraction of x and y to their maker."""
    kh, kw = kernel.shape[:2]
    h, w = canvas.shape[:2]
    ys = (np.arange(kh) + int(math.floor(y)) - kh // 2) % h
    xs = (np.arange(kw) + int(math.floor(x)) - kw // 2) % w
    ix = np.ix_(ys, xs)
    canvas[ix] = op(canvas[ix], kernel)


def stamp_lens(canvas, x, y, length, thick, value=1.0, ends=0.5, op=np.maximum):
    """A lens (see `lens`) of `value` stamped at (x, y)."""
    stamp(canvas, x, y, lens(length, thick, x - math.floor(x), y - math.floor(y), ends) * value, op)


def normal_map(height, strength=1.0):
    """A tangent-space normal map (OpenGL: +Y up the rows, as zkit bakes and Unity reads) from a tileable height map
    in pixel units, `strength` scaling its slopes. Returns colors in 0-1."""
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5 * strength
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, -dy, np.ones_like(height)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def cavity(height, radius, depth=1.0):
    """Occlusion from a height map: 1 on the surface, darker in pits and cracks up to about `radius` pixels across,
    by `depth` per unit of height below their surroundings."""
    return np.clip(1.0 - np.maximum(0.0, blur(height, radius) - height) * depth, 0.0, 1.0)


def wrap_pad(image, pad):
    """Pads an image tileable across with `pad` columns of its own wrapped-round content on each side: a strip that
    sits in part of a texture's width but still tiles round a tube (see BarkUV)."""
    return np.concatenate([image[:, -pad:], image, image[:, :pad]], 1)


def match_mean(image, target, mask=None):
    """Scales an sRGB image channel by channel so its mean (over `mask`) is `target` (sRGB 0-255); returns the
    scaled image and the factors, to grade companion textures alike."""
    sel = image[mask] if mask is not None else image.reshape(-1, image.shape[-1])
    k = np.asarray(target, float) / 255.0 / np.maximum(sel.mean(0), 1e-6)
    return np.clip(image * k, 0.0, 1.0), k


def to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def to_linear(c):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def write_png(path, image):
    """Writes an image (rows bottom to top, values 0-1, 1 to 4 channels) as an 8-bit PNG exactly as given, with no
    color management: an sRGB albedo stays sRGB and a data map stays linear (Unity's importer decides)."""
    a = np.asarray(image, float)
    if a.ndim == 2:
        a = a[..., None]
    h, w, c = a.shape
    rows = (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)[::-1].reshape(h, w * c)
    # PNG filter "up" on every row (each byte less the one above it) keeps the files small
    up = rows.copy()
    up[1:] = rows[1:] - rows[:-1]
    raw = np.concatenate([np.full((h, 1), 2, np.uint8), up], 1).tobytes()

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    kind = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, kind, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_image(path):
    """An image file as a float array (rows bottom to top, 4 channels) with its values as stored: no color
    conversion, and EXR renders come premultiplied by their alpha."""
    img = bpy.data.images.load(path, check_existing=False)
    if not img.is_float:
        img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4).astype(np.float64)


def fill_holes(image, covered):
    """Spreads the colors of the `covered` pixels (a mask) into the rest, each hole taking the color of the nearest
    covered area (push-pull), so bilinear filtering and mipmaps at a cutout's edge don't pull in black. Each side
    must halve evenly a few times (texture sizes do)."""
    img = image if image.ndim == 3 else image[..., None]
    pyramid = []
    c, wt = img * covered[..., None], covered.astype(np.float64)
    while c.shape[0] % 2 == 0 and c.shape[1] % 2 == 0 and min(c.shape[:2]) > 1:
        pyramid.append((c, wt))
        h, w = c.shape[:2]
        c = c.reshape(h // 2, 2, w // 2, 2, -1).sum((1, 3))
        wt = wt.reshape(h // 2, 2, w // 2, 2).sum((1, 3))
    filled = c / np.maximum(wt, 1e-9)[..., None]
    if (wt <= 0).any():
        filled[wt <= 0] = img[covered].mean(0) if covered.any() else 0.0
    for c, wt in reversed(pyramid):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        filled = np.where((wt > 0)[..., None], c / np.maximum(wt, 1e-9)[..., None], up)
    out = np.where(covered[..., None], img, filled)
    return out if image.ndim == 3 else out[..., 0]


# ---------------------------------------------------------------- flat renders (atlas cells, impostors)

SIG = {}


def signals(mat, color, rough, normal=None, alpha=None):
    """Records which sockets of `mat` carry its albedo (a linear color), roughness, shading normal (world space; None
    for the mesh's own) and cutout alpha (None: opaque), so render_passes can render each flat. Every material on
    something rendered flat (a spray, a tree for its impostor) needs this. Colors and numbers may be constants."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    g = tk.Graph(mat)
    SIG[mat.name] = dict(out=out, surface=out.inputs["Surface"].links[0].from_socket,
                         color=color if hasattr(color, "is_output") else g.rgb(color),
                         rough=rough if hasattr(rough, "is_output") else g.value(rough), normal=normal, alpha=alpha)
    return mat


def _pass_shader(mat, kind, axes, ao_distance):
    """Swaps `mat`'s surface for a flat shader showing one signal (see render_passes); returns the nodes it added."""
    info = SIG[mat.name]
    nt = mat.node_tree
    made = []

    def node(idname, **props):
        n = nt.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        made.append(n)
        return n

    def math_node(op, a, b=0.0, c=None):
        n = node("ShaderNodeMath", operation=op)
        for i, x in enumerate((a, b) if c is None else (a, b, c)):
            if hasattr(x, "is_output"):
                nt.links.new(x, n.inputs[i])
            else:
                n.inputs[i].default_value = x
        return n.outputs[0]

    nrm = info["normal"] if info["normal"] is not None else node("ShaderNodeNewGeometry").outputs["Normal"]
    signal = None
    if kind == "normal":
        dots = []
        for axis in axes:
            d = node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
            nt.links.new(nrm, d.inputs[0])
            d.inputs[1].default_value = axis
            dots.append(d.outputs["Value"])
        # Always the side facing the camera: a leaf seen from behind shows its back's normal
        flip = math_node("MULTIPLY_ADD", math_node("GREATER_THAN", dots[2], 0.0), 2.0, -1.0)
        comb = node("ShaderNodeCombineXYZ")
        for i, d in enumerate(dots):
            nt.links.new(math_node("MULTIPLY_ADD", math_node("MULTIPLY", d, flip), 0.5, 0.5), comb.inputs[i])
        signal = comb.outputs[0]
    elif kind == "albedo":
        signal = info["color"]
    elif kind == "rough":
        signal = info["rough"]
    elif kind == "ao":
        ao = node("ShaderNodeAmbientOcclusion", samples=16, only_local=False)
        ao.inputs["Distance"].default_value = ao_distance
        nt.links.new(nrm, ao.inputs["Normal"])
        signal = ao.outputs["AO"]
    if kind == "sky":
        sh = node("ShaderNodeBsdfDiffuse")
        sh.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        nt.links.new(nrm, sh.inputs["Normal"])
        shader = sh.outputs[0]
    else:
        em = node("ShaderNodeEmission")
        nt.links.new(signal, em.inputs["Color"])
        em.inputs["Strength"].default_value = 1.0
        shader = em.outputs[0]
    if info["alpha"] is not None:
        tr = node("ShaderNodeBsdfTransparent")
        mixer = node("ShaderNodeMixShader")
        nt.links.new(math_node("GREATER_THAN", info["alpha"], 0.5), mixer.inputs[0])
        nt.links.new(tr.outputs[0], mixer.inputs[1])
        nt.links.new(shader, mixer.inputs[2])
        shader = mixer.outputs[0]
    nt.links.new(shader, info["out"].inputs["Surface"])
    return made


def render_passes(objs, cam, res, kinds, samples=32, ao_distance=0.1):
    """Renders `objs` alone through `cam` (res = (width, height)) once per pass in `kinds`, returning {kind: RGBA
    array, rows bottom to top, premultiplied by alpha (coverage)}: "albedo" (linear color), "normal" (the shading
    normal turned to face the camera, in its right/up/toward frame, encoded 0-1), "rough", "ao" (the AO node out to
    `ao_distance` m: contact shadow within a spray) and "sky" (how much of a white sky each point sees, letting light
    through cutout leaves: a whole tree's self-shadowing, for impostors). Materials need `signals`."""
    scene = bpy.context.scene
    keep = {o.name for o in objs}
    hidden = {}
    for o in scene.objects:
        hidden[o.name] = o.hide_render
        if o.type == "LIGHT" or (o.type == "MESH" and o.name not in keep):
            o.hide_render = True
        elif o.name in keep:
            o.hide_render = False
    world = scene.world
    flat = bpy.data.worlds.get("_Passes") or bpy.data.worlds.new("_Passes")
    flat.use_nodes = True
    bg = flat.node_tree.nodes["Background"]
    scene.world = flat
    cy = scene.cycles
    saved = (scene.render.film_transparent, cy.samples, cy.use_denoising, cy.filter_width, cy.max_bounces,
             cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces)
    scene.render.film_transparent = True
    cy.use_denoising = False
    cy.filter_width = 1.0
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces = 2, 0, 0, 0
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    st = scene.render.image_settings
    st.file_format = "OPEN_EXR"
    st.color_mode = "RGBA"
    st.color_depth = "32"
    # A camera made this moment still has an identity matrix until the view layer updates
    bpy.context.view_layer.update()
    m = cam.matrix_world.to_3x3()
    axes = (m.col[0].normalized(), m.col[1].normalized(), m.col[2].normalized())
    mats = {s.material for o in objs for s in o.material_slots if s.material is not None}
    for mt in mats:
        if mt.name not in SIG:
            print("[treekit] material %s has no signals; it renders as itself" % mt.name)
    out = {}
    for kind in kinds:
        made = [(mt, _pass_shader(mt, kind, axes, ao_distance)) for mt in mats if mt.name in SIG]
        sky = kind == "sky"
        bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0) if sky else (0.0, 0.0, 0.0, 1.0)
        bg.inputs["Strength"].default_value = 1.0 if sky else 0.0
        cy.samples = samples * 2 if sky else samples
        path = os.path.join(bpy.app.tempdir, "_pass_%s.exr" % kind)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out[kind] = read_image(path)
        os.remove(path)
        for mt, nodes in made:
            info = SIG[mt.name]
            mt.node_tree.links.new(info["surface"], info["out"].inputs["Surface"])
            for n in nodes:
                mt.node_tree.nodes.remove(n)
    (scene.render.film_transparent, cy.samples, cy.use_denoising, cy.filter_width, cy.max_bounces,
     cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces) = saved
    st.file_format = "PNG"
    st.color_depth = "8"
    scene.world = world
    for o in scene.objects:
        if o.name in hidden:
            o.hide_render = hidden[o.name]
    return out


def straight(img):
    """Color from a premultiplied render pass (divided by its alpha)."""
    return img[..., :3] / np.maximum(img[..., 3], 1e-5)[..., None]


def decode_normals(img):
    """Unit normals from a premultiplied "normal" pass, encoded again 0-1."""
    n = straight(img) * 2.0 - 1.0
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    n[img[..., 3] < 1e-4] = (0.0, 0.0, 1.0)
    return n * 0.5 + 0.5


class Cell:
    """One image in a leaf atlas: its pixel rectangle (x, y from the bottom left, w, h), the world size it shows in
    meters (a card cut from it is that big at scale 1), and its attach point as fractions of the cell ((0.5, 0.97)
    is just under the top middle, where a hanging spray's twig starts). `pad` pixels round its edge stay transparent,
    so nothing bleeds between cells; `coverage` is its mean alpha once drawn."""

    def __init__(self, name, x, y, w, h, world, attach=(0.5, 0.97), pad=12, size=2048):
        self.name = name
        self.x, self.y, self.w, self.h = x, y, w, h
        self.world = tuple(world)
        self.attach = tuple(attach)
        self.pad = pad
        self.uv = (x / size, y / size, (x + w) / size, (y + h) / size)
        self.coverage = 0.4

    def frame(self):
        """The cell's world rectangle (x0, y0, x1, y1) about its attach point, in the card's plane."""
        W, H = self.world
        ax, ay = self.attach
        return -ax * W, -ay * H, (1.0 - ax) * W, (1.0 - ay) * H


class Atlas:
    """A square leaf atlas being put together: cells rendered from 3D sprays (`render`) or painted with numpy
    (`paint`), then `save`d as <prefix>_Albedo.png (RGBA, the alpha is the cutout), _Normal.png and _RMOM.png (R
    roughness, G metallic 0, B occlusion, A 0: the game shader reads RMOM alpha as a tint mask)."""

    def __init__(self, size=2048):
        self.size = size
        self.albedo = np.zeros((size, size, 3))
        self.alpha = np.zeros((size, size))
        self.normal = np.tile([0.5, 0.5, 1.0], (size, size, 1))
        self.rough = np.full((size, size), 0.6)
        self.ao = np.ones((size, size))
        self.cells = {}

    def cell(self, name, x, y, w, h, world, attach=(0.5, 0.97), pad=12):
        c = self.cells[name] = Cell(name, x, y, w, h, world, attach, pad, self.size)
        return c

    def paint(self, cell, albedo, alpha, normal=None, rough=0.6, ao=1.0):
        """Puts cell-sized arrays into a cell: albedo (sRGB), alpha, normal (encoded 0-1) and roughness and
        occlusion (arrays or numbers). The padding is cleared."""
        h, w = cell.h, cell.w
        a = np.array(alpha, float)
        p = cell.pad
        a[:p], a[-p:], a[:, :p], a[:, -p:] = 0.0, 0.0, 0.0, 0.0
        sl = (slice(cell.y, cell.y + h), slice(cell.x, cell.x + w))
        self.albedo[sl] = albedo
        self.alpha[sl] = a
        self.normal[sl] = normal if normal is not None else (0.5, 0.5, 1.0)
        self.rough[sl] = rough
        self.ao[sl] = ao
        cell.coverage = float(a.mean())

    def frame(self, cell, objs, margin=3):
        """Fits a cell's world rectangle round `objs` (built in the card's plane, the attach point at the origin):
        the smallest that holds them clear of the padding at the cell's pixel aspect, centered on them, with the
        attach point moved to match. A card cut from the cell is then the size of what it shows, at true scale."""
        vs = _world_verts(objs)
        bx0, bx1 = min(v.x for v in vs), max(v.x for v in vs)
        by0, by1 = min(v.y for v in vs), max(v.y for v in vs)
        p = cell.pad + margin
        aspect = cell.w / cell.h
        H = max((by1 - by0) / (1.0 - 2.0 * p / cell.h), (bx1 - bx0) / (1.0 - 2.0 * p / cell.w) / aspect)
        W = aspect * H
        cx, cy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
        cell.world = (W, H)
        cell.attach = (0.5 - cx / W, 0.5 - cy / H)
        print("[treekit] cell %s shows %.2f x %.2f m (%d px/m), attach %.2f %.2f" % (
            cell.name, W, H, cell.w / W, cell.attach[0], cell.attach[1]))
        return cell

    def render(self, cell, objs, samples=32, ao_distance=0.04):
        """Renders `objs` (built in the card's plane: x right, y up, facing +z, the attach point at the origin) into
        `cell`, orthographic from +z, and warns if anything reaches into the padding."""
        x0, y0, x1, y1 = cell.frame()
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        cam = tk.camera("_Cell" + cell.name, (cx, cy, 5.0), (cx, cy, 0.0), ortho=max(cell.world))
        p = render_passes(objs, cam, (cell.w, cell.h), ("albedo", "normal", "rough", "ao"), samples=samples,
                          ao_distance=ao_distance)
        bpy.data.objects.remove(cam)
        a = p["albedo"][..., 3]
        pd = cell.pad
        border = np.ones_like(a, bool)
        border[pd:-pd, pd:-pd] = False
        if (a[border] > 0.02).any():
            print("[treekit] cell %s: the content reaches into the padding (clipped)" % cell.name)
        self.paint(cell, to_srgb(straight(p["albedo"])), a, decode_normals(p["normal"]),
                   straight(p["rough"])[..., 0], straight(p["ao"])[..., 0])
        return cell

    def grade(self, names, target):
        """Scales the albedo of the named cells, channel by channel, so their opaque pixels average `target` (sRGB
        0-255, e.g. measured off vanilla foliage in game): the leaf-to-leaf variation stays, the whole range moves."""
        sel = np.zeros_like(self.alpha, bool)
        for n in names:
            c = self.cells[n]
            sel[c.y:c.y + c.h, c.x:c.x + c.w] = True
        sel &= self.alpha > 0.5
        mean = self.albedo[sel].mean(0)
        k = np.asarray(target, float) / 255.0 / np.maximum(mean, 1e-6)
        self.albedo[sel] = np.clip(self.albedo[sel] * k, 0.0, 1.0)
        print("[treekit] graded %s from %s to %s" % (", ".join(names), tuple(np.round(mean * 255).astype(int)),
                                                     tuple(np.round(self.albedo[sel].mean(0) * 255).astype(int))))

    def save(self, folder, prefix):
        covered = self.alpha > 0.004
        albedo = fill_holes(self.albedo, covered)
        normal = fill_holes(self.normal, covered) * 2.0 - 1.0
        normal = normal / np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-6) * 0.5 + 0.5
        rough = fill_holes(self.rough, covered)
        ao = fill_holes(self.ao, covered)
        zero = np.zeros_like(rough)
        paths = dict(albedo=os.path.join(folder, prefix + "_Albedo.png"),
                     normal=os.path.join(folder, prefix + "_Normal.png"),
                     rmom=os.path.join(folder, prefix + "_RMOM.png"))
        write_png(paths["albedo"], np.dstack([albedo, self.alpha]))
        write_png(paths["normal"], normal)
        write_png(paths["rmom"], np.dstack([rough, zero, ao, zero]))
        return paths

    def preview(self, path, back=(0.35, 0.36, 0.38)):
        """The atlas over a grey ground with its cells outlined, for review."""
        img = mix(np.asarray(back), self.albedo, self.alpha)
        for c in self.cells.values():
            img[c.y:c.y + c.h, c.x] = img[c.y:c.y + c.h, c.x + c.w - 1] = (0.9, 0.2, 0.2)
            img[c.y, c.x:c.x + c.w] = img[c.y + c.h - 1, c.x:c.x + c.w] = (0.9, 0.2, 0.2)
        write_png(path, img)


# ---------------------------------------------------------------- mesh builder

class Mesh:
    """Triangles collected with a material key and UVs per corner, plus optional per-vertex attributes, built into
    one Blender mesh object by `build`. The corners of one vertex may carry different UVs (a tube's seam, a switch of
    bark material): the vertex stays shared, so its normal stays smooth across."""

    def __init__(self):
        self.co = []
        self.tris = []
        self.uvs = []
        self.keys = []
        self.attrs = {}

    def v(self, co, **attrs):
        i = len(self.co)
        for k, val in attrs.items():
            self.attrs.setdefault(k, {})[i] = val
        self.co.append(tuple(co))
        return i

    def tri(self, a, b, c, uv, key):
        self.tris.append((a, b, c))
        self.uvs.append(tuple(uv))
        self.keys.append(key)

    def quad(self, a, b, c, d, uv, key):
        """a b c d counter-clockwise seen from the front, `uv` their four UVs."""
        self.tri(a, b, c, (uv[0], uv[1], uv[2]), key)
        self.tri(a, c, d, (uv[0], uv[2], uv[3]), key)

    def count(self, keys=None):
        return sum(1 for k in self.keys if keys is None or k in keys)

    def build(self, name, materials, smooth=True):
        """The mesh object `name`; `materials` maps each key to a Blender material (keys may share one), in slot
        order."""
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.co, [], self.tris)
        slots = []
        for mat in materials.values():
            if mat not in slots and any(materials[k] is mat for k in set(self.keys)):
                slots.append(mat)
        for mat in slots:
            me.materials.append(mat)
        me.polygons.foreach_set("material_index", [slots.index(materials[k]) for k in self.keys])
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [c for tri in self.uvs for corner in tri for c in corner])
        for aname, values in self.attrs.items():
            sample = next(iter(values.values()))
            vec = isinstance(sample, (tuple, list, Vector))
            attr = me.attributes.new(aname, "FLOAT_VECTOR" if vec else "FLOAT", "POINT")
            if vec:
                flat = [0.0] * (3 * len(self.co))
                for i, val in values.items():
                    flat[3 * i:3 * i + 3] = val[0], val[1], val[2]
                attr.data.foreach_set("vector", flat)
            else:
                flat = [0.0] * len(self.co)
                for i, val in values.items():
                    flat[i] = val
                attr.data.foreach_set("value", flat)
        if smooth:
            me.shade_smooth()
        me.update()
        return tk.link(bpy.data.objects.new(name, me))


def triangles(obj, material=None):
    """Triangles of a mesh object, or of those faces using `material` (a name)."""
    me = obj.data
    if material is None:
        return sum(len(p.vertices) - 2 for p in me.polygons)
    idx = [i for i, m in enumerate(me.materials) if m and m.name == material]
    return sum(len(p.vertices) - 2 for p in me.polygons if p.material_index in idx)


# ---------------------------------------------------------------- geometry for sprays (rendered into the atlas)

def blade(m, base, direction, normal, length, width, profile, key="leaf", teeth=0, tooth=0.0, fold=0.15,
          arch=0.15, twist=0.0, rows=14, rnd_value=0.0):
    """A leaf blade of real geometry for an atlas render: from `base` along `direction`, its face toward `normal`,
    `length` by `width` at its widest. `profile(s)` gives the half-width (0-1) at fraction s from base to tip;
    `teeth` serrations per side, `tooth` deep (fraction of the width; every other one half as deep, a doubly serrate
    edge); `fold` lifts the edges off the midrib (V section), `arch` droops the tip back, `twist` turns it (degrees)
    along the way. Each vertex gets "leaf" = (across -1..1, along 0..1, rnd_value) for vein and color shading."""
    d = Vector(direction).normalized()
    nl = Vector(normal)
    nl = (nl - d * nl.dot(d)).normalized()
    side = nl.cross(d)
    hw = width * 0.5
    n = rows
    # Margin points: dense enough for the teeth
    k = max(n, teeth * 4 + 4)
    mid, left, right = [], [], []
    for i in range(k + 1):
        s = i / k
        w = profile(s)
        if teeth and 0.12 < s < 0.97:
            ph = (s - 0.12) / 0.85 * teeth
            saw = (ph % 1.0) ** 1.6
            big = 1.0 if int(ph) % 2 == 0 else 0.55
            w += tooth * saw * big * min(1.0, w * 3.0)
        rot = Matrix.Rotation(math.radians(twist * s), 3, d)
        sd, up = rot @ side, rot @ nl
        drop = arch * s * s * length
        c = Vector(base) + d * (s * length) - nl * drop
        mid.append(m.v(c, leaf=(0.0, s, rnd_value)))
        left.append(m.v(c - sd * (w * hw) + up * (fold * w * hw), leaf=(-w, s, rnd_value)))
        right.append(m.v(c + sd * (w * hw) + up * (fold * w * hw), leaf=(w, s, rnd_value)))
    uv = ((0, 0),) * 4
    for i in range(k):
        m.quad(mid[i], mid[i + 1], right[i + 1], right[i], uv, key)
        m.quad(mid[i], left[i], left[i + 1], mid[i + 1], uv, key)


def twig(m, points, radii, key="twig", sides=5):
    """A thin round stem along a polyline (closed at the tip), for spray renders; "leaf" = (0, t, 0) along it."""
    pts = [Vector(p) for p in points]
    fr = frames(pts)
    uv = ((0, 0),) * 4
    rings = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        t, nr, bn = fr[i]
        f = i / max(1, len(pts) - 1)
        rings.append([m.v(p + (nr * math.cos(a) + bn * math.sin(a)) * r, leaf=(0.0, f, 0.0))
                      for a in (k / sides * TAU for k in range(sides))])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            m.quad(a[k], a[k1], b[k1], b[k], uv, key)
    tip = m.v(pts[-1] + fr[-1][0] * radii[-1], leaf=(0.0, 1.0, 0.0))
    for k in range(sides):
        m.tri(rings[-1][k], rings[-1][(k + 1) % sides], tip, uv[:3], key)


def bend_path(start, direction, length, bend, steps=10, down=(0.0, -1.0, 0.0), wobble=None):
    """A smooth polyline from `start` along `direction` that turns toward `down` by `bend` (radians, total, growing
    toward the tip): a hanging twig in a spray's frame. `wobble(f)` adds an offset at fraction f."""
    d = Vector(direction).normalized()
    g = Vector(down).normalized()
    p = Vector(start)
    pts = [p.copy()]
    ds = length / steps
    for i in range(steps):
        f = (i + 0.5) / steps
        turn = g * (bend * ds / length * 2.0 * f)
        d = (d + turn - d * d.dot(turn)).normalized()
        p = p + d * ds
        q = p + (Vector(wobble(f)) if wobble else Vector())
        pts.append(q)
    return pts


# ---------------------------------------------------------------- skeleton

class Branch:
    """A branch's polyline (`points`, `radii`); level 0 is a trunk, 1 its limbs, 2 their branches and so on. `at(s)`
    gives position, direction and radius at fraction s of its length. It hangs off `parent` at `s_parent`, grew
    from `spec` (its Level, or Trunk) and `keep[lod]` says whether LOD0/1/2 draw it."""

    def __init__(self, points, radii, level=0, parent=None, s_parent=0.0, spec=None, rnd=None):
        self.points = [Vector(p) for p in points]
        self.radii = list(radii)
        self.level = level
        self.parent = parent
        self.s_parent = s_parent
        self.spec = spec
        self.children = []
        self.tags = set()
        self.root = parent.root if parent is not None else self
        self.keep = [True, True, True]
        self.drawn = {}  # lod -> (fractions, ring centers): the polyline that LOD's tube actually draws
        rnd = rnd or random
        self.rot = rnd.uniform(0.0, TAU)  # where the bark's u seam starts round the tube
        self.v0 = rnd.random()  # the bark's v offset, so neighbours don't start the texture alike
        if parent is not None:
            parent.children.append(self)
        self.measure()

    def measure(self):
        self.cum = [0.0]
        self.cum_r = [0.0]  # length over radius, as BarkUV tiles by
        for i, (a, b) in enumerate(zip(self.points, self.points[1:])):
            self.cum.append(self.cum[-1] + (b - a).length)
            self.cum_r.append(self.cum_r[-1] + (b - a).length / max((self.radii[i] + self.radii[i + 1]) * 0.5, 0.004))
        self.length = self.cum[-1]
        self.ground_r = self._interp_r(self.s_at_height(0.0)) if self.level == 0 else 0.0

    def _interp_r(self, s):
        target = max(0.0, min(1.0, s)) * self.length
        i = min(max(bisect.bisect_left(self.cum, target), 1), len(self.points) - 1)
        seg = self.cum[i] - self.cum[i - 1]
        f = max(0.0, min(1.0, (target - self.cum[i - 1]) / seg)) if seg > 1e-9 else 0.0
        return self.cum_r[i - 1] + (self.cum_r[i] - self.cum_r[i - 1]) * f

    def turns(self, s):
        """Length over radius up to fraction s, from the ground on a trunk: what BarkUV's v counts (a trunk's bark v
        at s is turns(s) / k + v0)."""
        return self._interp_r(s) - self.ground_r

    def at(self, s):
        target = max(0.0, min(1.0, s)) * self.length
        i = min(max(bisect.bisect_left(self.cum, target), 1), len(self.points) - 1)
        seg = self.cum[i] - self.cum[i - 1]
        f = max(0.0, min(1.0, (target - self.cum[i - 1]) / seg)) if seg > 1e-9 else 0.0
        p = self.points[i - 1].lerp(self.points[i], f)
        d = (self.points[i] - self.points[i - 1]).normalized()
        return p, d, self.radii[i - 1] + (self.radii[i] - self.radii[i - 1]) * f

    def s_at_height(self, z):
        """Fraction along a trunk (rising) where it reaches height z."""
        for i in range(1, len(self.points)):
            a, b = self.points[i - 1], self.points[i]
            if b.z >= z:
                f = (z - a.z) / (b.z - a.z) if b.z > a.z else 0.0
                return (self.cum[i - 1] + (self.cum[i] - self.cum[i - 1]) * max(0.0, min(1.0, f))) / self.length
        return 1.0

    def point_at_height(self, z):
        return self.at(self.s_at_height(z))[0]

    def drawn_at(self, s, lod):
        """Where fraction s lies on the tube LOD `lod` draws (straight between its rings), so what hangs on a branch
        sits on the bark that is drawn, not on the smooth curve beside it."""
        d = self.drawn.get(lod)
        if not d:
            return self.at(s)[0]
        ss, pts = d
        i = min(max(bisect.bisect_left(ss, s), 1), len(ss) - 1)
        f = (s - ss[i - 1]) / max(ss[i] - ss[i - 1], 1e-9)
        return pts[i - 1].lerp(pts[i], max(0.0, min(1.0, f)))

    @property
    def tip(self):
        return self.points[-1]


class Trunk:
    """One trunk (a clump has several). Heights and radii in meters."""

    def __init__(self, **kw):
        self.height = 15.0  # to the tip of the leader
        self.radius = 0.13  # 1 m up (half way up a trunk under 2 m: a seedling)
        self.flare = 0.3  # extra radius at the ground (a fraction), fading out over flare_height
        self.flare_height = 0.4
        self.lobes = (0, 0.0)  # (count, amount): root swellings round the flare
        self.taper = 1.0  # the radius falls as (1 - z / height) ** taper toward the tip
        self.tip_radius = 0.006
        self.lean = (0.0, 0.0)  # the top's offset from the base
        self.bow = 0.0  # 1: leans low down and the top grows back upright (a banana); -1: bends over high up
        self.wander = 0.03  # crooks, sideways, growing with height
        self.base = (0.0, 0.0)  # where it leaves the ground (clumps)
        self.sink = 0.4  # how far it reaches under the ground
        self.step = 0.4  # path step
        self.sides = (8, 6, 5)  # tube sides at LOD0, 1, 2
        self.seg = (0.6, 1.2, 2.4)  # ring spacing at each LOD
        self.rings = ((0.0, 0.15, 0.4, 0.8), (0.0, 0.4), (0.0,))  # extra rings at these heights (the flare)
        self.min_len = (0.0, 0.0, 0.0)
        self.broken = False  # a snapped top (snags): capped flat instead of tapering to a point
        self.tags = ()
        _set(self, kw, "Trunk")

    def radius_at(self, z):
        def raw(zz):
            zz = max(0.0, zz)
            core = max(0.0, 1.0 - zz / self.height) ** self.taper
            return core * (1.0 + self.flare * math.exp(-zz / max(self.flare_height, 1e-3)))
        return max(self.tip_radius, self.radius * raw(z) / raw(min(1.0, self.height * 0.5)))


class Level:
    """How one order of branches grows off its parents (limbs off a trunk, branches off a limb). Lengths in meters,
    angles in degrees, turns in radians per meter of growth."""

    def __init__(self, **kw):
        self.per_meter = 2.0  # children per meter of the parent's span...
        self.count = None  # ...or this many (a number, or (lo, hi))
        self.span = (0.2, 0.95)  # where along the parent (fractions of its length)
        self.whorl = 1  # children per node (conifers: 3 to 6 in a ring)
        self.phyllo = "spiral"  # "spiral" (137.5 degrees on), "alternate" (180), "opposite" (pairs), or whorls
        self.length = (0.5, 1.0)  # random range, times the shape...
        self.relative = False  # ...and times the parent's length beyond the child's base
        self.shape = "flat"  # the crown's envelope over the span (see `shape`)
        self.inner = 0.0  # shorten children heading toward the tree's center (clumps share a crown) by this much
        self.favor = None  # ((x, y), amount): children heading that way grow longer (the open, sunny side)
        self.angle = 45.0  # off the parent's direction at the base of the span...
        self.angle_tip = None  # ...and at its tip (default the same)
        self.angle_vary = 6.0
        self.planar = 0.0  # 0-1: pulls children toward the parent's sides (flat sprays: firs, elms)
        self.outward = 0.0  # pull toward horizontal out from the trunk
        self.lift = 0.0  # pull toward the sky (negative: the ground) at the start
        self.radius = 0.5  # child's base radius over the parent's there...
        self.radius_length = 0.5  # ...times (length / longest) to this power
        self.radius_max = None
        self.tip_radius = 0.003
        self.taper = 1.0  # radius falls as (1 - s) ** taper toward the tip radius
        self.step = 0.25  # path step
        self.gravitropism = 0.0  # turn toward the sky per meter (negative: toward the ground)
        self.droop = 0.0  # turn toward the ground per meter, growing as the square of the way along (the weight)
        self.wander = 0.15  # random turns (per square root of a meter): curvature noise
        self.floor = 0.3  # never grows below this height
        self.split = 0.0  # chance per meter of forking...
        self.split_angle = 28.0  # ...this far off
        self.min_length = 0.08  # shorter children aren't grown
        self.broken = False  # capped flat instead of pointed (dead stubs)
        self.tags = ()
        self.sides = (5, 4, 3)  # tube sides at LOD0, 1, 2 (under 3: not drawn)
        self.seg = (0.5, 0.9, 1.6)  # ring spacing at each LOD
        self.min_len = (0.0, 0.0, 0.0)  # shorter branches are dropped at that LOD (with all they carry)
        self.on = None  # optional test(parent) -> grow on this parent at all
        _set(self, kw, "Level")
        if self.angle_tip is None:
            self.angle_tip = self.angle


def shape(kind, t):
    """The crown's envelope: how long children are at fraction t of the parent's span (0 its base, 1 its tip).
    "conical" (longest low: firs), "spherical", "oval" (widest about 40 % up: birch, aspen), "flame" (widest at
    70 %), "cylinder" or "flat" (even), "tapered" (narrowing to the top), "umbrella" (longest high: mesquite), or a
    function of t."""
    if callable(kind):
        return kind(t)
    if kind == "conical":
        return 1.0 - 0.85 * t
    if kind == "spherical":
        return 0.2 + 0.8 * math.sin(math.pi * t)
    if kind == "oval":
        return 0.2 + 0.8 * math.sin(math.pi * min(1.0, t) ** 0.75)
    if kind == "flame":
        return 0.2 + 0.8 * (t / 0.7 if t < 0.7 else (1.0 - t) / 0.3)
    if kind == "tapered":
        return 1.0 - 0.6 * t
    if kind == "umbrella":
        return 0.3 + 0.7 * t ** 0.7
    return 1.0


class Foliage:
    """Where a tree's cards go and how they hang. One for the spray cards (LOD0, thinned for LOD1), another for
    LOD2's cluster cards."""

    def __init__(self, **kw):
        self.levels = {2: (0.3, 1.0)}  # branch level -> the stretch of each such branch that carries cards
        self.trunk_top = None  # and this stretch of each trunk (its leader), e.g. (0.9, 1.0)
        self.spacing = 0.12  # meters between cards along a branch
        self.tip = True  # a card at every tip
        self.cells = ()  # atlas cell names to pick from
        self.scale = (0.85, 1.15)  # card size over its cell's world size
        self.hang = 0.6  # 0: a card carries on along its twig, 1: it hangs straight down
        self.spread = 0.25  # random spread of the way it hangs
        self.out = 0.4  # how far a card leaves its branch outward from the trunk rather than along the branch
        self.face = 0.8  # share of cards facing out from the trunk (the rest face anywhere round)
        self.up = 0.2  # share of cards spread out flat facing the sky (they fill the crown seen from above)
        self.roll = 30.0  # random roll about the way it hangs (degrees)
        self.bend = 20.0  # LOD0 cards fold this far at their middle (4 triangles)
        self.on = None  # optional test(branch) -> it carries cards at all (e.g. only the tips: rosettes)
        _set(self, kw, "Foliage")


class Scars:
    """Bark scars: strips cut from atlas cells, hugging a parent just above where a child leaves it (a birch's black
    chevrons, a knot's ring), and `extra` more on the trunks with no branch (old self-pruned limbs). They are patches
    of the leaf material (it has the cutout), each its own patch like a card; the Unity side tells them from cards by
    their UVs, which lie only in the scar cells, and gives them no flutter."""

    def __init__(self, **kw):
        self.cells = ()  # atlas cell names
        self.levels = (1,)  # children of these levels scar their parent
        self.size = (5.0, 7.0)  # width, in the child's radii
        self.min_radius = (0.01, 0.03)  # the smallest child radius that scars at LOD0, LOD1 (LOD2 has none)
        self.above = 1.0  # the scar's bottom this many child radii above where the child leaves the bark
        self.extra = 0
        self.extra_height = (0.8, 5.0)
        self.extra_width = (0.08, 0.2)
        self.lift = 0.004  # off the bark
        _set(self, kw, "Scars")


class BarkUV:
    """How a bark material's texture wraps a tube: u `wraps` times round (a full-width map only), inside the strip
    u = (u0, u1) of the texture (a strip must tile across on its own, see `wrap_pad`), v either tiling by length
    over radius (one repeat every `k` radii of length, so a texture whose height is k * wraps / (2 pi) times its
    width keeps square texels on every tube; a trunk's v counts from the ground, starting at TreeSpec.ground_v) or,
    given `height` = (z0, z1), running v = (v0, v1) from height z0 to z1 (a gradient texture: a dark base). `twist`
    slides u along v on full-width maps, so a trunk's repeats don't stack straight above each other. `floor` keeps
    v from falling under it (a buried trunk end that mustn't wrap round into the texture's top)."""

    def __init__(self, u=(0.0, 1.0), k=4.0 * math.pi, height=None, v=(0.0, 1.0), twist=0.0, min_radius=0.004,
                 wraps=1, floor=None):
        self.u0, self.u1 = u
        self.k = k
        self.height = height
        self.v0, self.v1 = v
        self.twist = twist
        self.min_radius = min_radius
        self.wraps = wraps
        self.floor = floor

    def uv(self, fu, acc, z, br):
        if self.height is not None:
            z0, z1 = self.height
            v = self.v0 + (self.v1 - self.v0) * max(0.0, min(1.0, (z - z0) / (z1 - z0)))
        else:
            v = acc / self.k + br.v0
        if self.floor is not None:
            v = max(v, self.floor)
        full = self.u0 == 0.0 and self.u1 == 1.0
        u = self.u0 + (self.u1 - self.u0) * fu * (self.wraps if full else 1)
        if self.twist and full:
            u += self.twist * v
        return u, v


class TreeSpec:
    """A species' recipe for one tree. `trunks` (Trunk, one or a clump), `levels` (a Level per order of branching:
    levels[0] grows off the trunks, levels[1] off those...), `stubs` (a Level of dead stubs on the trunks),
    `foliage` and `cluster` (Foliage for the spray cards and LOD2's cluster cards), `scars` (Scars), the bark:
    `bark_key(branch, s, radius, z)` names the material a stretch of tube gets and `bark_uv` maps each name to a
    BarkUV, with `ground_v` the v every trunk's bark has at the ground (None: each its own, at random); and the
    triangle `budget` of LOD0, with LOD1 and LOD2 as shares of it (`lod_share`)."""

    def __init__(self, **kw):
        self.trunks = [Trunk()]
        self.levels = []
        self.stubs = None
        self.foliage = None
        self.cluster = None
        self.scars = None
        self.bark_key = lambda br, s, r, z: "bark"
        self.bark_uv = {"bark": BarkUV()}
        self.ground_v = None
        self.budget = 7000
        self.bark_budget = 2500  # a warning only
        self.lod_share = (0.45, 0.18)
        self.lod1_fill = 0.95  # LOD1's leaf area over LOD0's (bigger cards overlap less)
        self.lod2_fill = 1.0  # LOD2's leaf area over LOD0's
        _set(self, kw, "TreeSpec")


class Card:
    """A leaf card: attached at `p` (on its twig), hanging along `a`, facing `n`, cut from `cell`, `scale` times
    its world size; `host` is the branch it sits on, at fraction `s`."""

    def __init__(self, p, a, n, cell, scale, host, s):
        self.p, self.a, self.n = Vector(p), Vector(a).normalized(), Vector(n).normalized()
        self.cell, self.scale, self.host, self.s = cell, scale, host, s

    @property
    def area(self):
        return self.cell.world[0] * self.cell.world[1] * self.scale ** 2 * self.cell.coverage

    def scaled(self, k):
        return Card(self.p, self.a, self.n, self.cell, self.scale * k, self.host, self.s)

    def on(self, lod):
        """The card hung from its branch as LOD `lod` draws it (see Branch.drawn_at)."""
        p = self.host.tip if self.s >= 1.0 else self.host.drawn_at(self.s, lod)
        return Card(p, self.a, self.n, self.cell, self.scale, self.host, self.s)


class Tree:
    """A grown tree: `trunks`, every Branch in `branches` (trunks first, then each level in turn), the spray
    `cards`, `scars` and the spec it grew from."""

    def __init__(self, name, spec, seed):
        self.name, self.spec, self.seed = name, spec, seed
        self.trunks, self.branches, self.cards, self.scars = [], [], [], []

    def radial(self, p, br):
        """The horizontal way out from the trunk `br` grows on, at p."""
        q = br.root.point_at_height(p.z)
        d = Vector((p.x - q.x, p.y - q.y, 0.0))
        if d.length < 1e-4:
            d = Vector((p.x, p.y, 0.0))
        return d.normalized() if d.length > 1e-6 else Vector((1.0, 0.0, 0.0))

    def center_way(self, p):
        """The horizontal way from p toward the middle of a clump (None for a single trunk)."""
        if len(self.trunks) < 2:
            return None
        c = sum((t.points[0] for t in self.trunks), Vector()) / len(self.trunks)
        d = Vector((c.x - p.x, c.y - p.y, 0.0))
        return d.normalized() if d.length > 1e-4 else None


def grow_path(rnd, start, direction, length, step=0.25, gravitropism=0.0, droop=0.0, wander=0.1, floor=0.3):
    """The polyline of a branch from `start` heading along `direction`, `length` meters in steps of about `step`:
    each step it turns toward the sky by `gravitropism` (per meter; negative turns down), toward the ground by
    `droop` (per meter, growing as the square of the way along: the weight of a long thin branch) and at random by
    `wander` (per square root of a meter), and it never sinks below `floor`."""
    n = max(2, int(math.ceil(length / step)))
    ds = length / n
    d = Vector(direction).normalized()
    p = Vector(start)
    pts = [p.copy()]
    for i in range(n):
        s = (i + 0.5) / n
        turn = UP * (gravitropism * ds) + DOWN * (droop * ds * 3.0 * s * s)
        turn += Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * (wander * math.sqrt(ds))
        d = (d + turn - d * d.dot(turn)).normalized()
        p = p + d * ds
        if p.z < floor:
            p.z = floor
        pts.append(p.copy())
    return pts


def _radii(r0, tip, count, taper):
    return [tip + (r0 - tip) * max(0.0, 1.0 - i / (count - 1)) ** taper for i in range(count)]


def grow_trunk(rnd, t):
    """A trunk's Branch from a Trunk: rising to `height` with its lean, bow and crooks, from `sink` under the ground."""
    H = t.height
    n = max(4, int(math.ceil(H / t.step)))
    lean = Vector((t.lean[0], t.lean[1], 0.0))
    waves = [(rnd.uniform(0.5, 1.6), rnd.uniform(0.0, TAU), rnd.uniform(0.4, 1.0)) for _ in range(4)]
    base = Vector((t.base[0], t.base[1], 0.0))
    pts = [base + Vector((0.0, 0.0, -t.sink))]
    for i in range(n + 1):
        f = i / n
        crook = Vector((sum(a * math.sin(TAU * c * f + ph) for c, ph, a in waves[:2]),
                        sum(a * math.sin(TAU * c * f + ph) for c, ph, a in waves[2:]), 0.0)) * (t.wander * f ** 0.6)
        pts.append(base + lean * (f + t.bow * f * (1.0 - f)) + crook + Vector((0.0, 0.0, f * H)))
    br = Branch(pts, [t.radius_at(p.z) for p in pts], 0, None, 0.0, t, rnd)
    br.tags.update(t.tags)
    return br


def grow_children(rnd, tree, parent, lv, level):
    """Grows Level `lv`'s children (and their forks) on `parent`; returns them."""
    s0, s1 = lv.span
    span = parent.length * (s1 - s0)
    if span <= 0.01:
        return []
    if lv.count is not None:
        n = lv.count if isinstance(lv.count, int) else rnd.randint(*lv.count)
    else:
        n = int(round(span * lv.per_meter * rnd.uniform(0.85, 1.15)))
    per = max(1, lv.whorl)
    groups = max(1, n // per) if n else 0
    kids = []
    phase = rnd.uniform(0.0, TAU)
    favor = None
    if lv.favor is not None:
        favor = (Vector((lv.favor[0][0], lv.favor[0][1], 0.0)).normalized(), lv.favor[1])
    for gi in range(groups):
        t = (gi + rnd.uniform(0.3, 0.7) if per == 1 else gi + 0.5) / groups
        s = s0 + (s1 - s0) * t
        p, tan, r = parent.at(s)
        _, u, v = basis(tan)
        for j in range(per):
            i = gi * per + j
            if per > 1:
                az = phase + gi * 0.6 + j * TAU / per + rnd.uniform(-0.25, 0.25)
            elif lv.phyllo == "alternate":
                az = phase + i * math.pi + rnd.uniform(-0.5, 0.5)
            elif lv.phyllo == "opposite":
                az = phase + (i // 2) * math.pi * 0.5 + (i % 2) * math.pi + rnd.uniform(-0.3, 0.3)
            else:
                az = phase + i * GOLDEN + rnd.uniform(-0.35, 0.35)
            out = u * math.cos(az) + v * math.sin(az)
            if lv.planar:
                side = tan.cross(UP)
                if side.length > 1e-3:
                    side.normalize()
                    out = out.lerp(side * (1.0 if out.dot(side) >= 0.0 else -1.0), lv.planar).normalized()
            ang = math.radians(lv.angle + (lv.angle_tip - lv.angle) * t + rnd.gauss(0.0, lv.angle_vary))
            d = tan * math.cos(ang) + out * math.sin(ang)
            d = (d + tree.radial(p, parent) * lv.outward + UP * lv.lift).normalized()
            L = rnd.uniform(*lv.length) * shape(lv.shape, t)
            if lv.relative:
                L *= parent.length * (1.0 - s)
            h = Vector((d.x, d.y, 0.0))
            if h.length > 1e-3:
                h.normalize()
                cw = tree.center_way(p)
                if lv.inner and cw is not None:
                    L *= 1.0 - lv.inner * max(0.0, h.dot(cw))
                if favor is not None:
                    L *= 1.0 + favor[1] * h.dot(favor[0])
            if L < lv.min_length:
                continue
            r0 = r * lv.radius * min(1.0, (L / max(lv.length[1], 1e-3)) ** lv.radius_length)
            if lv.radius_max:
                r0 = min(r0, lv.radius_max)
            r0 = max(r0, lv.tip_radius * 1.3)
            pts = grow_path(rnd, p, d, L, lv.step, lv.gravitropism, lv.droop, lv.wander, lv.floor)
            tip = r0 * 0.85 if lv.broken else lv.tip_radius
            kid = Branch(pts, _radii(r0, tip, len(pts), lv.taper), level, parent, s, lv, rnd)
            kid.tags.update(lv.tags)
            kids.append(kid)
            if lv.split and rnd.random() < lv.split * L:
                sf = rnd.uniform(0.3, 0.65)
                q, qt, qr = kid.at(sf)
                _, fu, fv = basis(qt)
                a = rnd.uniform(0.0, TAU)
                fd = rotate(qt, fu * math.cos(a) + fv * math.sin(a), lv.split_angle)
                fpts = grow_path(rnd, q, fd, L * (1.0 - sf) * rnd.uniform(0.75, 1.0), lv.step, lv.gravitropism,
                                 lv.droop, lv.wander, lv.floor)
                fork = Branch(fpts, _radii(qr * 0.85, tip, len(fpts), lv.taper), level, kid, sf, lv, rnd)
                fork.tags.update(lv.tags)
                fork.tags.add("fork")
                kids.append(fork)
    return kids


def grow(spec, seed=0, name="Tree"):
    """Grows a Tree from a TreeSpec: trunks, each Level in turn, stubs, scars and the spray cards (their cells must
    be in the atlas by then, for their sizes)."""
    rnd = random.Random(seed)
    tree = Tree(name, spec, seed)
    for t in spec.trunks:
        tree.trunks.append(grow_trunk(rnd, t))
        if spec.ground_v is not None:
            tree.trunks[-1].v0 = spec.ground_v
    tree.branches = list(tree.trunks)
    current = list(tree.trunks)
    for li, lv in enumerate(spec.levels):
        nxt = []
        for br in current:
            if lv.on is None or lv.on(br):
                nxt += grow_children(rnd, tree, br, lv, li + 1)
        tree.branches += nxt
        current = nxt
    if spec.stubs is not None:
        for t in tree.trunks:
            stubs = grow_children(rnd, tree, t, spec.stubs, 1)
            for s in stubs:
                s.tags.add("stub")
            tree.branches += stubs
    # Which LODs draw each branch: its level's sides and minimum length, and its parent drawn too
    for br in tree.branches:
        for lod in range(3):
            ok = br.spec.sides[lod] >= 3 and br.length >= br.spec.min_len[lod]
            br.keep[lod] = ok and (br.parent is None or br.parent.keep[lod])
    if spec.scars is not None:
        _plan_scars(rnd, tree)
    if spec.foliage is not None:
        tree.cards = place_cards(rnd, tree, spec.foliage)
    return tree


# ---------------------------------------------------------------- foliage

def _host_spans(tree, fol, lod):
    for br in tree.branches:
        if "stub" in br.tags or not br.keep[lod] or (fol.on is not None and not fol.on(br)):
            continue
        span = fol.trunk_top if br.level == 0 else fol.levels.get(br.level)
        if span is not None:
            yield br, span


def host_length(tree, fol, lod=0):
    """Meters of branch that carry `fol`'s cards."""
    return sum(br.length * (s1 - s0) for br, (s0, s1) in _host_spans(tree, fol, lod))


def place_cards(rnd, tree, fol, lod=0, spacing=None, atlas_cells=None):
    """Cards along every branch `fol` names (kept at `lod`), `spacing` (default fol.spacing) apart, alternating sides,
    each leaving its branch outward and hanging (see Foliage), facing out from the trunk with a random roll, or
    spread flat facing the sky. The cards' attach points sit on the branches, so none hovers."""
    cells = atlas_cells or ATLAS_CELLS
    spacing = spacing or fol.spacing
    cards = []
    for br, (s0, s1) in _host_spans(tree, fol, lod):
        n = int((s1 - s0) * br.length / spacing)
        ss = [s0 + (s1 - s0) * (i + rnd.uniform(0.2, 0.8)) / max(n, 1) for i in range(n)]
        if fol.tip and (s1 >= 0.999 or not ss):
            ss.append(1.0)
        phase = rnd.uniform(0.0, TAU)
        for i, s in enumerate(ss):
            p, tan, r = br.at(min(s, 0.999))
            if s >= 1.0:
                p = br.tip.copy()
            _, u, v = basis(tan)
            az = phase + i * math.pi + rnd.uniform(-0.7, 0.7)
            off = u * math.cos(az) + v * math.sin(az)
            radial = tree.radial(p, br)
            lead = tan * (1.0 - fol.out) + radial * fol.out + off * 0.45
            if s >= 1.0:
                lead = tan + radial * 0.25
            lead.normalize()
            if rnd.random() < fol.up:
                # Spread out flat, a little down, facing the sky
                a = Vector((lead.x, lead.y, 0.0))
                a = (a.normalized() if a.length > 1e-3 else radial) + DOWN * rnd.uniform(0.1, 0.35)
                n0 = UP.copy()
            else:
                jit = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1) * 0.5)) * fol.spread
                a = lead.lerp(DOWN, fol.hang) + jit
                if rnd.random() < fol.face:
                    n0 = radial.copy()
                else:
                    b = rnd.uniform(0.0, TAU)
                    n0 = Vector((math.cos(b), math.sin(b), 0.0))
            a.normalize()
            nrm = n0 - a * n0.dot(a)
            if nrm.length < 1e-3:
                nrm = basis(a)[1]
            nrm = rotate(nrm.normalized(), a, rnd.uniform(-fol.roll, fol.roll))
            cell = cells[rnd.choice(fol.cells)]
            cards.append(Card(p, a, nrm, cell, rnd.uniform(*fol.scale), br, s))
    return cards


ATLAS_CELLS = {}


def use_atlas(atlas):
    """Makes `atlas`'s cells the ones cards and scars are cut from."""
    ATLAS_CELLS.clear()
    ATLAS_CELLS.update(atlas.cells)


def thin(cards, ratio, rnd=None):
    """Keeps `ratio` of the cards (rounded down), evenly along each branch, its tip card kept while ratio is over
    0.3."""
    if ratio >= 1.0:
        return list(cards)
    rnd = rnd or random.Random(5)
    target = int(len(cards) * ratio)
    by = {}
    for c in cards:
        by.setdefault(id(c.host), []).append(c)
    out = []
    for group in by.values():
        group.sort(key=lambda c: c.s)
        acc = rnd.random()
        for c in group:
            acc += ratio
            if acc >= 1.0 or (c.s >= 1.0 and ratio > 0.3):
                out.append(c)
                acc = acc - 1.0 if acc >= 1.0 else acc
    # The tips and rounding keep a few too many: drop some of the others at random
    extra = len(out) - target
    if extra > 0:
        inner = [i for i, c in enumerate(out) if c.s < 1.0]
        drop = set(rnd.sample(inner, min(extra, len(inner))))
        out = [c for i, c in enumerate(out) if i not in drop]
    return out


def card_quads(m, card, rows=1, bend=0.0, key="leaves"):
    """A card's quads: `rows` 1 is a flat quad (2 triangles), 2 folds at the middle by `bend` degrees (4)."""
    cell = card.cell
    w, h = cell.world[0] * card.scale, cell.world[1] * card.scale
    ax, ay = cell.attach
    a, n = card.a, card.n
    right = n.cross(a).normalized()
    a2 = rotate(a, right, bend) if rows > 1 else a
    u0, v0, u1, v1 = cell.uv
    ys = [1.0, 0.5, 0.0] if rows > 1 else [1.0, 0.0]

    def along(y):
        d = (ay - y) * h  # distance down the card from the attach point
        mid = (ay - 0.5) * h
        if rows > 1 and d > mid:
            return a * mid + a2 * (d - mid)
        return a * d

    grid = []
    for y in ys:
        base = card.p + along(y)
        grid.append([m.v(base + right * ((x - ax) * w)) for x in (0.0, 1.0)])
    for j in range(len(ys) - 1):
        top, low = grid[j], grid[j + 1]
        yt, yl = ys[j], ys[j + 1]
        m.quad(low[0], low[1], top[1], top[0],
               ((u0, v0 + (v1 - v0) * yl), (u1, v0 + (v1 - v0) * yl), (u1, v0 + (v1 - v0) * yt),
                (u0, v0 + (v1 - v0) * yt)), key)


# ---------------------------------------------------------------- scars

def _plan_scars(rnd, tree):
    sc = tree.spec.scars
    for br in tree.branches:
        if br.level not in sc.levels or br.parent is None:
            continue
        par = br.parent
        p, tan, rp = par.at(br.s_parent)
        d0 = (br.points[1] - br.points[0]).normalized()
        out = d0 - tan * d0.dot(tan)
        if out.length < 1e-3:
            continue
        out.normalize()
        rc = br.radii[0]
        # Where the child comes out of the bark, then a little above it
        cot = d0.dot(tan) / max(1e-3, out.dot(d0))
        width = rc * rnd.uniform(*sc.size)
        tree.scars.append(dict(parent=par, child=br, s=br.s_parent + (rp * cot + rc * sc.above) / par.length,
                               out=out, width=width, radius=rc, cell=rnd.choice(sc.cells)))
    for t in tree.trunks:
        for _ in range(sc.extra):
            z = rnd.uniform(*sc.extra_height)
            if z > t.points[-1].z * 0.9:
                continue
            s = t.s_at_height(z)
            _, tan, _ = t.at(s)
            _, u, v = basis(tan)
            a = rnd.uniform(0.0, TAU)
            w = rnd.uniform(*sc.extra_width)
            tree.scars.append(dict(parent=t, child=None, s=s, out=u * math.cos(a) + v * math.sin(a), width=w,
                                   radius=w / 6.0, cell=rnd.choice(sc.cells)))


def _scar_quads(m, tree, lod, key="leaves"):
    sc = tree.spec.scars
    if sc is None or lod >= 2:
        return
    for d in tree.scars:
        par = d["parent"]
        if not par.keep[lod] or (d["child"] is not None and not d["child"].keep[lod]):
            continue
        if d["radius"] < sc.min_radius[lod] and d["child"] is not None:
            continue
        if d["child"] is None and lod > 0 and d["width"] < 0.14:
            continue
        cell = ATLAS_CELLS[d["cell"]]
        width = d["width"]
        height = width * cell.world[1] / cell.world[0]
        s_mid = d["s"] + height * 0.5 / par.length
        if s_mid > 0.98:
            continue
        _, tan, r = par.at(s_mid)
        p = par.drawn_at(s_mid, lod)
        out = (d["out"] - tan * d["out"].dot(tan)).normalized()
        side = tan.cross(out)
        rr = r + sc.lift
        half = min(width * 0.5 / rr, math.pi * 0.45)
        cols = 3 if lod == 0 else 2
        u0, v0, u1, v1 = cell.uv
        grid = []
        for k in range(cols + 1):
            phi = -half + 2.0 * half * k / cols
            radial = out * math.cos(phi) + side * math.sin(phi)
            grid.append([m.v(p + tan * dz + radial * rr) for dz in (-height * 0.5, height * 0.5)])
        for k in range(cols):
            fu0, fu1 = u0 + (u1 - u0) * k / cols, u0 + (u1 - u0) * (k + 1) / cols
            m.quad(grid[k][0], grid[k + 1][0], grid[k + 1][1], grid[k][1],
                   ((fu0, v0), (fu1, v0), (fu1, v1), (fu0, v1)), key)


# ---------------------------------------------------------------- bark tubes

def _tube(m, tree, br, lod):
    spec = br.spec
    sides = spec.sides[lod]
    seg = spec.seg[lod]
    keyfn = tree.spec.bark_key
    maps = tree.spec.bark_uv

    def key_at(s):
        p, _, r = br.at(s)
        return keyfn(br, s, r, p.z)

    n = max(1, int(round(br.length / seg)))
    forced = []
    if br.level == 0:
        forced = [br.s_at_height(z) for z in spec.rings[lod]]
    gap = 0.35 * seg / br.length
    ss = sorted(set([0.0, 1.0] + forced + [i / n for i in range(1, n) if all(abs(i / n - f) > gap for f in forced)]))
    # A ring wherever the bark material changes (found by bisection)
    rings_s = [ss[0]]
    for a, b in zip(ss, ss[1:]):
        ka = key_at(min(1.0, a + 1e-5))
        if ka != key_at(max(0.0, b - 1e-5)):
            lo, hi = a, b
            for _ in range(16):
                mid = (lo + hi) * 0.5
                lo, hi = (mid, hi) if key_at(mid) == ka else (lo, mid)
            rings_s.append((lo + hi) * 0.5)
        rings_s.append(b)
    pts, rads = [], []
    for s in rings_s:
        p, _, r = br.at(s)
        pts.append(p)
        rads.append(r)
    br.drawn[lod] = (list(rings_s), list(pts))
    fr = frames(pts)
    acc = [0.0]
    for i in range(1, len(pts)):
        ds = (pts[i] - pts[i - 1]).length
        acc.append(acc[-1] + ds / max((rads[i] + rads[i - 1]) * 0.5, 0.004))
    if br.level == 0:
        # A trunk's v counts from the ground (BarkUV), so every trunk's bark starts the same there
        j = next((i for i in range(1, len(pts)) if pts[i].z >= 0.0), None)
        if j is not None:
            f = max(0.0, min(1.0, -pts[j - 1].z / max(pts[j].z - pts[j - 1].z, 1e-9)))
            g = acc[j - 1] + (acc[j] - acc[j - 1]) * f
            acc = [a - g for a in acc]
    lobes = getattr(spec, "lobes", (0, 0.0))
    rings = []
    for i, (p, r) in enumerate(zip(pts, rads)):
        t, nr, bn = fr[i]
        ring = []
        for k in range(sides):
            a = br.rot + k / sides * TAU
            rr = r
            if lobes[0] and br.level == 0:
                fade = math.exp(-max(0.0, p.z) / max(spec.flare_height, 1e-3))
                swell = 0.65 * math.cos(lobes[0] * a) + 0.35 * math.cos((lobes[0] + 2) * a + 1.3)
                rr *= 1.0 + lobes[1] * fade * swell
            ring.append(m.v(p + (nr * math.cos(a) + bn * math.sin(a)) * rr))
        rings.append(ring)
    for i in range(len(rings) - 1):
        sm = (rings_s[i] + rings_s[i + 1]) * 0.5
        key = key_at(sm)
        bm = maps[key]
        za, zb = pts[i].z, pts[i + 1].z
        for k in range(sides):
            k1 = k + 1
            m.quad(rings[i][k], rings[i][k1 % sides], rings[i + 1][k1 % sides], rings[i + 1][k],
                   (bm.uv(k / sides, acc[i], za, br), bm.uv(k1 / sides, acc[i], za, br),
                    bm.uv(k1 / sides, acc[i + 1], zb, br), bm.uv(k / sides, acc[i + 1], zb, br)), key)
    # The tip: a point, or flat where it snapped off
    key = key_at(0.999)
    bm = maps[key]
    t_end = fr[-1][0]
    broken = getattr(spec, "broken", False)
    tip = m.v(pts[-1] + t_end * (rads[-1] * (0.15 if broken else 1.5)))
    for k in range(sides):
        k1 = k + 1
        m.tri(rings[-1][k], rings[-1][k1 % sides], tip,
              (bm.uv(k / sides, acc[-1], pts[-1].z, br), bm.uv(k1 / sides, acc[-1], pts[-1].z, br),
               bm.uv((k + 0.5) / sides, acc[-1] + 0.3, pts[-1].z, br)), key)
    if br.parent is None:
        # A trunk's buried end, closed
        key = key_at(0.0)
        bm = maps[key]
        bottom = m.v(pts[0] - fr[0][0] * rads[0])
        for k in range(sides):
            k1 = k + 1
            m.tri(rings[0][k1 % sides], rings[0][k], bottom,
                  (bm.uv(k1 / sides, acc[0], pts[0].z, br), bm.uv(k / sides, acc[0], pts[0].z, br),
                   bm.uv((k + 0.5) / sides, acc[0] - 0.3, pts[0].z, br)), key)


# ---------------------------------------------------------------- LODs

def _bark(m, tree, lod):
    """Every kept branch's tube; returns the triangles per level ("stub" for stubs)."""
    per = {}
    for br in tree.branches:
        if br.keep[lod]:
            n = len(m.tris)
            _tube(m, tree, br, lod)
            k = "stub" if "stub" in br.tags else br.level
            per[k] = per.get(k, 0) + len(m.tris) - n
    return per


def build_lods(tree, materials, report=True):
    """LOD0, LOD1 and LOD2 of a grown tree as mesh objects <name>_LOD0..2; `materials` maps every bark key and
    "leaves" to its Blender material. LOD0 is the full skeleton and the spray cards (thinned evenly if over the
    budget), folded at the middle if foliage.bend. LOD1 drops what its levels' sides and min_len drop, coarsens the
    tubes and keeps fewer cards, flat and grown so the leaf area stays about the same. LOD2 is the trunk and main
    limbs with cluster cards (spec.cluster) hung on them, as many as keep LOD0's leaf area. Every card hangs from its
    branch as that LOD draws it."""
    spec = tree.spec
    fol = spec.foliage
    rnd = random.Random(tree.seed + 101)
    out = []
    # LOD0
    m0 = Mesh()
    per = _bark(m0, tree, 0)
    bark0 = m0.count()
    if report:
        print("[treekit] %s LOD0 bark by level: %s (%d branches)" % (
            tree.name, ", ".join("%s %d" % kv for kv in sorted(per.items(), key=str)), len(tree.branches)))
    _scar_quads(m0, tree, 0)
    cards0 = list(tree.cards)
    if fol is not None and cards0:
        allow = max(0, spec.budget - m0.count())
        rows = 2 if fol.bend else 1
        n0 = min(len(cards0), allow // (2 * rows))
        if n0 < len(cards0):
            cards0 = thin(cards0, n0 / len(cards0), rnd)
        for c in cards0:
            card_quads(m0, c.on(0), rows, fol.bend)
    total0 = m0.count()
    if bark0 > spec.bark_budget:
        print("[treekit] %s: bark %d triangles, over the %d budget" % (tree.name, bark0, spec.bark_budget))
    out.append(m0)
    area0 = sum(c.area for c in cards0)
    # LOD1
    m1 = Mesh()
    _bark(m1, tree, 1)
    _scar_quads(m1, tree, 1)
    kept = [c for c in cards0 if c.host.keep[1]]
    if kept:
        allow = spec.lod_share[0] * total0 - m1.count()
        n1 = int(max(1, min(allow // 2, len(cards0) * 0.7)))
        cards1 = thin(kept, n1 / len(kept), rnd)
        k = math.sqrt(area0 * spec.lod1_fill / max(1e-6, sum(c.area for c in cards1)))
        for c in cards1:
            card_quads(m1, c.on(1).scaled(k), 1)
    out.append(m1)
    # LOD2
    m2 = Mesh()
    _bark(m2, tree, 2)
    cl = spec.cluster
    if cl is not None and area0 > 0:
        cells = [ATLAS_CELLS[n] for n in cl.cells]
        mean = sum(c.world[0] * c.world[1] * c.coverage for c in cells) / len(cells)
        mean *= ((cl.scale[0] + cl.scale[1]) * 0.5) ** 2
        want = area0 * spec.lod2_fill / max(mean, 1e-6)
        allow = max(1, int((spec.lod_share[1] * total0 - m2.count()) // 2))
        want = min(want, allow)
        hl = host_length(tree, cl, 2)
        if hl > 0 and want >= 1:
            clusters = place_cards(random.Random(tree.seed + 202), tree, cl, 2, spacing=hl / want)
            if len(clusters) > allow:
                clusters = thin(clusters, allow / len(clusters), rnd)
            k = math.sqrt(area0 * spec.lod2_fill / max(1e-6, sum(c.area for c in clusters)))
            k = max(0.8, min(1.3, k))
            rows = 2 if cl.bend and m2.count() + 4 * len(clusters) <= spec.lod_share[1] * total0 else 1
            for c in clusters:
                card_quads(m2, c.on(2).scaled(k), rows, cl.bend)
    out.append(m2)
    objs = [mm.build("%s_LOD%d" % (tree.name, i), materials) for i, mm in enumerate(out)]
    if report:
        for i, (o, mm) in enumerate(zip(objs, out)):
            leaves = mm.count(("leaves",))
            print("[treekit] %s LOD%d: %d triangles (bark %d, leaves %d)" % (tree.name, i, mm.count(),
                                                                             mm.count() - leaves, leaves))
    return objs


# ---------------------------------------------------------------- materials

def textured(name, paths, cutout=False, translucent=0.0):
    """A material showing exported maps (albedo times the RMOM occlusion, roughness, normal map), cut out where the
    albedo's alpha is under 0.5 if `cutout`, letting a little light through (`translucent` 0-1) like the game's leaf
    shader: the previews' stand-in for Game/SpeedTree8. Registered for render_passes (impostors)."""
    mat, g = tk.new_material(name)
    uv = tk._sock(g.node("ShaderNodeTexCoord").outputs, "UV")

    def tex(path, non_color, packed=False):
        n = g.node("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        if packed:
            n.image.alpha_mode = "CHANNEL_PACKED"
        g.links.new(uv, n.inputs["Vector"])
        return n

    alb = tex(paths["albedo"], False)
    sep = g.node("ShaderNodeSeparateColor")
    g.links.new(tex(paths["rmom"], True, True).outputs["Color"], sep.inputs[0])
    nm = g.node("ShaderNodeNormalMap")
    g.links.new(tex(paths["normal"], True).outputs["Color"], nm.inputs["Color"])
    base = tk._multiply_color(g, alb.outputs["Color"], g.mix(1.0, (1.0, 1.0, 1.0), sep.outputs[2]))
    p = g.node("ShaderNodeBsdfPrincipled")
    g._in(p, "Base Color", base)
    g._in(p, "Roughness", sep.outputs[0])
    g._in(p, "Metallic", 0.0)
    g._in(p, "Normal", nm.outputs["Normal"])
    shader = p.outputs[0]
    if translucent:
        tl = g.node("ShaderNodeBsdfTranslucent")
        g._in(tl, "Color", base)
        g._in(tl, "Normal", nm.outputs["Normal"])
        mx = g.node("ShaderNodeMixShader")
        g._in(mx, mx.inputs[0].identifier, translucent)
        g.links.new(shader, mx.inputs[1])
        g.links.new(tl.outputs[0], mx.inputs[2])
        shader = mx.outputs[0]
    if cutout:
        cut = g.math("GREATER_THAN", alb.outputs["Alpha"], 0.5)
        tr = g.node("ShaderNodeBsdfTransparent")
        mx = g.node("ShaderNodeMixShader")
        g.links.new(cut, mx.inputs[0])
        g.links.new(tr.outputs[0], mx.inputs[1])
        g.links.new(shader, mx.inputs[2])
        shader = mx.outputs[0]
    out = g.node("ShaderNodeOutputMaterial")
    g.links.new(shader, out.inputs["Surface"])
    return signals(mat, alb.outputs["Color"], sep.outputs[0], nm.outputs["Normal"],
                   alb.outputs["Alpha"] if cutout else None)


# ---------------------------------------------------------------- impostor (LOD3)

def _world_verts(objs):
    out = []
    for o in objs:
        mw = o.matrix_world
        out += [mw @ v.co for v in o.data.vertices]
    return out


def impostor(name, lod0, folder, height=1024, samples=24, occlusion=0.6):
    """LOD3: three vertical quads crossed at 0, 60 and 120 degrees, as tall and wide as the tree, showing a side view
    of LOD0 rendered orthographically with alpha (<name>Impostor_Albedo (RGBA), _Normal, _RMOM, `height` pixels tall
    and as wide as the tree needs). Its occlusion is the crown's own shade (how much white sky each point sees),
    `occlusion` strong. A tree whose crown leans is seen along its lean and the quads are sheared by it, so the lean
    shows from every side rather than fanning three ways. Returns the mesh object <name>_LOD3."""
    verts = _world_verts([lod0])
    c = sum(verts, Vector()) / len(verts)
    shear = Vector((c.x, c.y, 0.0)) / max(c.z, 1.0)
    if shear.length * c.z < 0.3:
        shear = Vector()
    view = Vector((shear.x, shear.y, 0.0)).normalized() if shear.length else Vector((0.0, 1.0, 0.0))
    right = view.cross(UP).normalized()
    xs = [abs((v - shear * v.z).dot(right)) for v in verts]
    z_lo = max(-0.3, min(v.z for v in verts))
    z_hi = max(v.z for v in verts) + 0.1
    H = z_hi - z_lo
    W = 2.0 * max(xs) * 1.03 + 0.2
    # Square pixels: the width rounded up to 32 pixels, and the frame widened to match
    res_x = int(max(128, min(2 * height, math.ceil(height * W / H / 32.0) * 32)))
    W = H * res_x / height
    zc = (z_lo + z_hi) * 0.5
    cam = tk.camera("_Impostor", Vector((0.0, 0.0, zc)) - view * 80.0, (0.0, 0.0, zc), ortho=max(W, H))
    p = render_passes([lod0], cam, (res_x, height), ("albedo", "normal", "rough", "sky"), samples=samples)
    bpy.data.objects.remove(cam)
    a = p["albedo"][..., 3]
    covered = a > 0.004
    albedo = fill_holes(to_srgb(straight(p["albedo"])), covered)
    nrm = fill_holes(decode_normals(p["normal"]), covered)
    rough = fill_holes(straight(p["rough"])[..., 0], covered)
    # The crown's self-shadowing, softened: the quads are lit as flat sheets, and LOD0 has no baked crown shade
    occ = fill_holes(1.0 - occlusion * (1.0 - np.clip(straight(p["sky"])[..., 0], 0.0, 1.0)), covered)
    zero = np.zeros_like(rough)
    paths = dict(albedo=os.path.join(folder, name + "Impostor_Albedo.png"),
                 normal=os.path.join(folder, name + "Impostor_Normal.png"),
                 rmom=os.path.join(folder, name + "Impostor_RMOM.png"))
    write_png(paths["albedo"], np.dstack([albedo, a]))
    write_png(paths["normal"], nrm)
    write_png(paths["rmom"], np.dstack([rough, zero, occ, zero]))
    mat = textured(name + "Impostor", paths, cutout=True, translucent=0.15)
    m = Mesh()
    for k in range(3):
        wk = rotate(right, UP, 60.0 * k)
        q = []
        for x, z in ((-0.5, z_lo), (0.5, z_lo), (0.5, z_hi), (-0.5, z_hi)):
            q.append(m.v(wk * (x * W) + Vector((0.0, 0.0, z)) + shear * max(0.0, z)))
        m.quad(q[0], q[1], q[2], q[3], ((0, 0), (1, 0), (1, 1), (0, 1)), "impostor")
    obj = m.build(name + "_LOD3", {"impostor": mat}, smooth=False)
    print("[treekit] %s LOD3: %d triangles, impostor %dx%d" % (name, triangles(obj), res_x, height))
    return obj


# ---------------------------------------------------------------- export

def export_tree(name, lods, folder):
    """Writes <folder>/<name>.fbx with exactly the four meshes <name>_LOD0..3."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".fbx")
    tk.export_fbx(list(lods), path)
    return path


def measure(tree, lod0):
    """(height, trunk radius 1 m up, crown radius, lean) of a grown tree: the height of LOD0's top, the main trunk's
    mean radius at 1 m, the farthest leaf vertex's horizontal distance from the trunk's base (the origin), and the
    main trunk's top offset from its base."""
    me = lod0.data
    leaf_idx = {i for i, mt in enumerate(me.materials) if mt and "Bark" not in mt.name}
    leaf_verts = set()
    for poly in me.polygons:
        if poly.material_index in leaf_idx:
            leaf_verts.update(poly.vertices)
    height = max(v.co.z for v in me.vertices)
    crown = max((math.hypot(me.vertices[i].co.x, me.vertices[i].co.y) for i in leaf_verts), default=0.0)
    t = tree.trunks[0]
    lean = t.points[-1] - t.points[1]
    return height, t.spec.radius_at(min(1.0, t.spec.height * 0.5)), crown, (lean.x, lean.y)


def write_trunks(path, name, tree, top=0.6, step=0.5):
    """Replaces <name>'s lines in trunks.txt with one line per trunk: `<Variant> x y z r x y z r ...`, points every
    `step` m along it from just under the ground to `top` of its length, in Blender's coordinates (the FBX meshes'
    own), with its radius there. The Unity builder hangs a chain of collision capsules on them, so no trunk can be
    walked into (a clump's every trunk, a bowed trunk's whole curve)."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() and ln.split()[0] != name]
    for t in tree.trunks:
        s0 = t.s_at_height(-0.3)
        n = max(2, int(math.ceil((top - s0) * t.length / step)) + 1)
        pts = []
        for i in range(n):
            p, _, r = t.at(s0 + (top - s0) * i / (n - 1))
            pts.append("%.3f %.3f %.3f %.4f" % (p.x, p.y, p.z, r))
        lines.append(name + " " + " ".join(pts))
    lines.sort(key=lambda ln: ln.split()[0])
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def write_sizes(path, name, size):
    """Replaces <name>'s line in trees.txt (`<Variant> height <m> trunk_radius <m> crown_radius <m> lean <x> <y>`,
    lean in Blender's x and y), keeping every other tree's line."""
    height, radius, crown, lean = size
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() and ln.split()[0] != name]
    lines.append("%s height %.2f trunk_radius %.3f crown_radius %.2f lean %.2f %.2f" % (
        name, height, radius, crown, lean[0], lean[1]))
    lines.sort()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- previews

def stage(sky=(0.42, 0.58, 0.85), ground=(0.11, 0.13, 0.065), sun_elevation=50.0, sun_azimuth=-30.0):
    """A daylight stage for tree previews: a blue sky (it shows through the crown), a sun, a big grassy floor at
    z = 0 with a faint 1 m grid near the middle, and a 1.8 m figure for scale (returned, to be moved about)."""
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (sky[0], sky[1], sky[2], 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    sun = tk.link(bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")))
    sun.data.energy = 4.5
    sun.data.angle = math.radians(1.5)
    sun.data.color = (1.0, 0.96, 0.9)
    sun.rotation_euler = (math.radians(90.0 - sun_elevation), 0.0, math.radians(sun_azimuth))
    cy = scene.cycles
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces = 4, 2, 1, 2
    cy.use_denoising = True
    cy.filter_width = 1.5
    mat, g = tk.new_material("Ground")
    x, y, _ = g.separate(g.coords())
    gx = g.ramp(g.math("PINGPONG", x, 0.5), 0.0, 0.02)
    gy = g.ramp(g.math("PINGPONG", y, 0.5), 0.0, 0.02)
    near = g.ramp(g.math("ADD", g.math("ABSOLUTE", x), g.math("ABSOLUTE", y)), 14.0, 10.0)
    line = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gx, gy)), near)
    col = g.mix(g.ramp(g.noise(0.4, detail=4.0), 0.3, 0.7), ground, tuple(c * 1.35 for c in ground))
    col = g.mix(g.math("MULTIPLY", line, 0.5), col, tuple(c * 0.5 for c in ground))
    tk.finish(mat, g, col, 0.0, 0.92)
    m = Mesh()
    q = [m.v((x0 * 300.0, y0 * 300.0, 0.0)) for x0, y0 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    m.quad(q[0], q[1], q[2], q[3], ((0, 0), (1, 0), (1, 1), (0, 1)), "g")
    m.build("Ground", {"g": mat}, smooth=False)
    dummy, g = tk.new_material("Figure")
    tk.finish(dummy, g, (0.25, 0.3, 0.38), 0.0, 0.7)
    body = tk.cylinder("ScaleFigure", 0.19, 0.0, 1.56, dummy, segments=20)
    head = tk.cylinder("ScaleHead", 0.11, 1.58, 1.8, dummy, segments=20)
    return [body, head]


def place(objs, x, y):
    for o in objs:
        o.location = (x, y, 0.0)


def _copy(obj, loc, rot=0.0):
    c = obj.copy()
    tk.link(c)
    c.location = loc
    c.rotation_euler = (0.0, 0.0, rot)
    c.hide_render = False
    return c


def _shot(name, loc, target, path, lens=35, res=(900, 1200), samples=48, ortho=None):
    cam = tk.camera(name, loc, target, lens=lens, ortho=ortho)
    tk.render(cam, path, res=res, samples=samples)
    bpy.data.objects.remove(cam)


def _only(objs):
    """Hides every mesh but `objs` and the stage (ground, figure); returns how to undo it."""
    keep = {o.name for o in objs} | {"Ground", "ScaleFigure", "ScaleHead"}
    saved = {}
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            saved[o.name] = o.hide_render
            o.hide_render = o.name not in keep
    return saved


def _restore(saved):
    for o in bpy.context.scene.objects:
        if o.name in saved:
            o.hide_render = saved[o.name]


def preview_tree(script, obj, out_dir, height, figure, samples=48):
    """Two side views of one tree (from the front, -y, and the right, +x) with the figure beside the trunk."""
    saved = _only([obj])
    place(figure, -1.6, -1.2)
    half = math.atan(18.0 / 35.0)
    for view, d in (("a", Vector((0.12, -1.0, 0.0))), ("b", Vector((1.0, 0.25, 0.0)))):
        d.normalize()
        dist = height * 0.62 / math.tan(half)
        loc = Vector((0.0, 0.0, height * 0.32)) + d * dist
        _shot(script + view, loc, (0.0, 0.0, height * 0.5), os.path.join(out_dir, "%s_%s.png" % (script, view)),
              samples=samples)
    _restore(saved)


def preview_bark(script, obj, out_dir, figure, samples=64):
    """The trunk's foot from 5 m and 1.5 m off: the bark has to read as the species from 5 m."""
    saved = _only([obj])
    place(figure, 1.2, 0.8)
    _shot(script + "bark5", (0.6, -5.0, 1.7), (0.0, 0.0, 1.5), os.path.join(out_dir, script + "_bark5m.png"),
          lens=40, res=(1000, 750), samples=samples)
    _shot(script + "bark1", (0.3, -1.5, 1.3), (0.0, 0.0, 1.0), os.path.join(out_dir, script + "_bark1m.png"),
          lens=40, res=(1000, 750), samples=samples)
    _restore(saved)


def preview_grove(script, objs, out_dir, figure, samples=48, spots=None, distance=36.0):
    """All the variants together as a little grove, from about `distance` m off (game distance)."""
    rnd = random.Random(4)
    spots = spots or [(-7.0, 4.0), (0.5, 9.0), (6.5, 2.0), (-1.5, -2.5), (9.0, 11.0), (-9.0, 12.0)]
    copies = [_copy(o, (x, y, 0.0), rnd.uniform(0.0, TAU)) for o, (x, y) in zip(objs, spots)]
    saved = _only(copies)
    place(figure, 2.5, -3.5)
    _shot(script + "grove", (3.0, -distance, 4.5), (0.0, 4.0, 6.5), os.path.join(out_dir, script + "_grove.png"),
          lens=40, res=(1400, 900), samples=samples)
    _shot(script + "grovenear", (-2.0, -12.0, 1.7), (0.5, 4.0, 6.0), os.path.join(out_dir, script + "_grove_near.png"),
          lens=24, res=(1400, 900), samples=samples)
    _restore(saved)
    for c in copies:
        bpy.data.objects.remove(c)


def preview_lods(script, lods, out_dir, figure, height, width, samples=48):
    """LOD0 to LOD3 side by side at the same scale, orthographic from the front."""
    gap = width + 1.5
    copies = [_copy(o, ((i - 1.5) * gap, 0.0, 0.0)) for i, o in enumerate(lods)]
    saved = _only(copies)
    place(figure, -1.5 * gap - width * 0.5 - 0.8, 0.0)
    span = max(4 * gap, height * 1.15 * 2.0)
    _shot(script + "lods", (0.0, -120.0, height * 0.5), (0.0, 0.0, height * 0.5),
          os.path.join(out_dir, script + "_lods.png"), res=(1600, 800), samples=samples, ortho=span)
    _restore(saved)
    for c in copies:
        bpy.data.objects.remove(c)
