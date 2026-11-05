# Tree models

One Blender script per species in `blender/trees/`, built on `treekit.py` (read it, and `birch.py`, the worked
example, first). Unlike the plants, trees are not block models: Blender meters, Z up, the ground at z = 0 and the
trunk's base centred on the origin. The game draws them with its own SpeedTree shader, **Game/SpeedTree8** in "palm"
wind mode like vanilla's oaks (alpha cutout at 0.5, both sides of leaf cards drawn); `src/build-trees.bat` runs
NatureTreeBuilder, which writes SpeedTree's per-vertex data from our geometry (branch sway from the distance out from
the trunk, leaf flutter per card, occlusion from the depth in the crown) and renders each tree in the game shader
beside vanilla's mountain pine and small oak into `unity/Build/trees/`. Run every Blender job under the shared 4-slot
rule (at most 4 Blender processes across all agents; see the session notes), as

    blender -b --factory-startup --python trees/<species>.py -- <unity trees folder> <preview folder> [textures|trees]

with `NatureExpanded/unity/Assets/NatureExpanded/Trees` and `NatureExpanded/unity/Build/previews/trees`, given as
absolute paths (Blender reads a relative one against its own `//`: images fail to load and renders land in
`C:\unity\...`). `textures`
stops after the species' shared textures; `trees` builds the variants on the textures already on disk (it rebuilds
the spray geometry, unrendered, to measure the atlas cells).

## What a species writes

Into `Trees/<Species>/`:

- **Shared bark:** `<Species>Bark_Albedo/_Normal/_RMOM.png`, tiling across (u `wraps` times round every tube) and
  up (v by length over radius), sharp up close: birch's is 2048 x 4096 wrapping twice round, about 36 px per cm on
  its trunk (one wrap of 1024 round a trunk read blurry in game). RMOM is R roughness, G metallic 0, B occlusion,
  **A 0** (the game's shaders read RMOM alpha as a tint mask). Optionally `<Species>BarkFoot_*`, a dark foot: the
  main bark itself, mapped the same way (a trunk's v counts from the ground: `TreeSpec.ground_v`), with the foot
  drawn over its lower rows; the trunk changes to the main bark (`bark_key`, at a v from `Branch.turns`) in rows the
  two share untouched, so the change can't be seen. A foot strip mapped by height met the main bark in a visible
  seam at eye height. And optionally `<Species>BarkTwig_*` for thin branches.
- **Shared leaves:** `<Species>Leaves_Albedo.png` (RGBA, alpha the cutout at 0.5), `_Normal`, `_RMOM`: a 2048 (or
  1024) atlas of 4 to 6 card images rendered from real 3D leaves, padded so nothing bleeds between cells, the holes
  filled with the nearest color so mipmaps don't pull in black. Extra cells may hold bark decals (in the atlas's
  bottom row: u 0 to 0.375, v 0 to 0.0625). Decal patches use the leaf material for its cutout, so the Unity builder
  tells them from cards by those UVs and gives them no flutter. Birch dropped its scar decals: on a round trunk seen
  up close they stood off the bark as flat black patches; its chevrons and eyes are in the bark texture instead.
- **Variants** `<Species>01.fbx` ...: exactly four meshes `<Species>NN_LOD0..3`. LOD0 to 2 use the materials
  `<Species>Bark`, `<Species>Leaves` (and `<Species>BarkFoot`, `<Species>BarkTwig`); LOD3 is the impostor, material
  `<Species>NNImpostor` with `<Species>NNImpostor_Albedo/_Normal/_RMOM.png` (1024 tall, as wide as the tree needs).
- **Seeds**, as vanilla's oak and pine seeds (players plant them and they grow): a seedling variant
  (`<Species>Sapling`, under 1 m, single-leaf cards from a one-leaf atlas cell, all twig bark) for the planted
  seed's model, and the seed's icon `<Species>Seed_Icon.png` (160 px, `make_icon`: the species' real seed, e.g.
  birch's catkin on a leaf, under zkit's icon lights, like vanilla's acorns and pine cone). gen_nature.py's `SEEDS`
  makes the seed block, the stages it grows through (variants, the last the grown wild tree) and the seed drops on
  every tree of the species (1 under 15 m, 2 above).
- A line per variant in `Trees/trees.txt` (`tr.write_sizes` replaces its own and keeps the rest):
  `<Variant> height <m> trunk_radius <m, 1 m up> crown_radius <m> lean <x> <y>`. Height is LOD0's top; crown radius
  the farthest leaf from the vertical through the origin (so it already includes the lean); lean the main trunk's
  top offset from its base in **Blender x and y** (a clump gives its first trunk).
- Previews in `unity/Build/previews/trees/`: each variant from two sides with a 1.8 m figure (`<variant>_a/_b`), a
  grove of all of them from about 36 m and from inside (`<script>_grove`, `_grove_near`), LOD0 to LOD3 side by side
  (`<variant>_lods`), the trunk's foot from 5 m and 1.5 m (`_bark5m`, `_bark1m`) and the atlas (`<script>_atlas`).

## Rules for every tree

- **Budgets** (triangles, single-sided): LOD0 7,000, up to 8,000 where the crown needs it for density, bark at most
  about 2,500 of it (a small or young tree 5,000 or less); LOD1 about 45 %, LOD2 about 18 %, LOD3 6 (three crossed
  quads). Vanilla's 23 m pine is 7.5k / 3.9k / 2.0k / 32, a 45 m oak 12.7k / 7.4k / 4.5k, a 9 m oak 4.4k / 2.2k /
  1.3k. `build_lods` stays inside `TreeSpec.budget` and `lod_share` and prints what it made, the bark by level; LOD2
  is often under its share, because it keeps LOD0's leaf area rather than filling the budget (more cluster cards
  would make it denser than LOD0). Spend LOD0's leaves on flat cards (2 triangles, `Foliage.bend` 0): twice as many
  as folded ones, and density is what a crown needs most.
- **Bark is single-sided:** trunks and branches are closed tubes with outward normals (`_tube` closes tips and a
  trunk's buried end; a child starts on its parent's axis, so its open base is inside the parent). Normals are smooth
  across the u seam (the seam vertices are shared, only their UVs differ).
- **Leaves are single-sided cards** with alpha (the SpeedTree material draws both sides): never model both sides,
  and keep **every card its own connected patch** of faces, never sharing vertices with another (the builder gives
  each patch its own flutter). Cards **sit on twigs**: each one's attach point (where the twig in its image starts)
  is on the branch as that LOD draws it (`Branch.drawn_at`), and LOD1/2 cards hang from branches those LODs still
  draw. No floating limbs: every branch starts on its parent's axis.
- **Real sizes:** leaves at their real size (cells are framed to their content, so a card is as big as what it
  shows), needles and cones too. A tree's height, trunk and crown match the species' spec below.
- **Colors next to vanilla, measured in the game shader** (mean albedo of opaque pixels, sRGB): vanilla oak foliage
  about (70-75, 78-83, 56-61), vanilla pine needles (76-80, 85-87, 63-73). Our foliage stays in that range, lighter
  or yellower only as far as the species is (birch leaves (84, 98, 58)); `Atlas.grade` scales a rendered atlas's
  leaf cells to a target mean keeping the leaf-to-leaf variation (yellower, darker, paler undersides). Bark the same
  way (`match_mean`): birch's white is (180, 176, 168), which still reads white beside vanilla's grey-brown pines
  without glowing. The impostors are rendered from the graded textures, so they follow.
- **Density and silhouette:** a mature broadleaf crown should carry about the leaf mass of vanilla's small oak, sky
  showing through it here and there, starting low enough (birch: from 35-40 % of the height, with some lower side
  limbs) and as wide as the species is, never a tuft on a bare pole. Judge the crown at game distances (10 to 80 m,
  the grove preview) and up close; conifers read as dark layered masses with gaps between whorls. LOD1 and LOD2
  keep the same silhouette and color mass as LOD0 (`<variant>_lods`). The final word is the game-shader render
  beside vanilla in `unity/Build/trees/`: Blender's previews light differently (darker foliage, no translucency).
- **Bark reads from 5 m** (`_bark5m`): the species' color, pattern and scale, the trunk's foot darker and rougher
  where the species is, its scars in the bark texture. Round up close: a trunk 12 sides at LOD0, limbs 6, stubs 9
  (birch's 4-sided stubs and limbs showed sharp corners in game).
- **Variants:** 3 or 4 per species, each its own seed and shape so neighbours never match: one typical, one leaning
  or crooked, one clump or odd form where the species does that, one young.
- **No wind data, no vertex colors:** the Unity builder computes SpeedTree's wind and occlusion from the geometry.
- **Review the previews** critically and iterate until the tree reads as its species at 10 to 80 m and up close.

## The kit (treekit.py)

```python
spec = tr.TreeSpec(
    trunks=[tr.Trunk(height=14.7, radius=0.18, lean=(0.35, 0.2), bow=0.3, flare=0.28, lobes=(5, 0.1))],
    levels=[tr.Level(count=26, span=(0.38, 0.97), length=(2.8, 4.1), shape=crown_shape, angle=66, angle_tip=32,
                     gravitropism=0.3, droop=0.5, ...),                   # limbs off the trunk
            tr.Level(per_meter=1.9, span=(0.1, 0.97), length=(0.7, 1.6), gravitropism=0.35, droop=0.8, ...)],
    stubs=tr.Level(..., broken=True),                                    # dead stubs low on the trunk
    foliage=tr.Foliage(levels={2: (0.08, 1.0), 1: (0.3, 1.0)}, trunk_top=(0.8, 1.0), spacing=0.04,
                       cells=SPRAYS, hang=0.35, face=0.7, up=0.35, roll=45, bend=0),
    cluster=tr.Foliage(levels={1: (0.3, 1.0)}, cells=CLUSTERS, ...),     # LOD2's cluster cards
    bark_key=bark_key, bark_uv={"bark": tr.BarkUV(...), "foot": ..., "twig": ...}, ground_v=0.1)
tree = tr.grow(spec, seed, "Birch01")              # skeleton, spray cards
lods = tr.build_lods(tree, materials)              # LOD0..2 within the budget
lods.append(tr.impostor("Birch01", lods[0], folder))
tr.export_tree("Birch01", lods, folder)
tr.write_sizes(trees_txt, "Birch01", tr.measure(tree, lods[0]))
```

- **Skeleton.** `Trunk`: height, radius 1 m up, flare and root `lobes`, taper, lean and `bow` (1 leans low and turns
  back upright, -1 bends over high), crooks (`wander`), its `base` for clumps, `broken` for a snapped top.
  `Level` (one per order of branching): count or `per_meter`, `span`, `whorl` (rings of N: conifers) and `phyllo`
  ("spiral", "alternate", "opposite"), `length` times `shape` ("conical", "spherical", "oval", "flame", "tapered",
  "umbrella", "cylinder" or a function) and optionally the parent's remaining length (`relative`), `angle` to
  `angle_tip` along the span, `planar` (flat sprays), `outward`, `lift`, `gravitropism` and `droop` (radians per
  meter; droop grows toward the tip like a branch's weight), `wander`, `split` and `split_angle` (forks: maples,
  Joshua tree), `radius`, `radius_length`, `radius_max`, `tip_radius`, `taper`, `broken` tips, `inner` (shorter
  toward a clump's middle), `favor` (longer toward the open side), `on(parent)` to choose parents, and per LOD
  `sides`, `seg` (ring spacing) and `min_len` (shorter branches dropped, with everything on them).
- **Bark.** `bark_key(branch, s, radius, z)` names the material of each stretch of tube (the tube gets a ring where
  it changes); `BarkUV` maps each name: a strip `u` of the texture, v tiling every `k` radii of length (k = 2 pi x
  height / width keeps texels square: 4 pi for a 1:2 texture) with `twist` so repeats don't stack, or v by
  `height` for a gradient. Draw textures with the numpy helpers: `fbm` (tileable fractal noise, stretchable), `blur`,
  `contour` (cracks along noise contours), `lens` / `stamp` / `stamp_lens` (lenticels, scars, cracks; wrapping),
  `normal_map`, `cavity` (occlusion), `wrap_pad`, `mix`, `smoothstep`, `match_mean` (grade to a measured mean),
  `write_png` (exact 8-bit PNGs, rows bottom to top).
- **Leaf atlas.** `Atlas(2048)`, `atlas.cell(name, x, y, w, h, world)`; build each card's content in the card's plane
  (x right, y up, facing +z, the twig's start at the origin) with `Mesh`, `blade` (a real leaf: profile function,
  doubly serrate teeth, fold, arch, twist; the "leaf" attribute carries across/along/random for the material) and
  `twig` along `bend_path`; `atlas.frame(cell, objs)` sizes the cell to it, `atlas.render(cell, objs)` renders
  albedo, normal, roughness and occlusion with alpha (materials need `tr.signals(mat, color, rough, normal)`),
  `atlas.grade(cells, mean)` scales the leaf cells to a measured mean, `atlas.paint` draws numpy cells (decals),
  `atlas.save(folder, prefix)` writes the maps, `atlas.preview`. Then `tr.use_atlas(atlas)` before `grow`. A clump of
  sprays (linked copies) makes a cluster cell for LOD2.
- **Cards.** `Foliage`: which levels (and the trunk's top) carry cards and where along them, `spacing` (set it
  closer than the budget allows: the cards are thinned evenly to it), `cells`, `scale`, `hang` (0 along the twig, 1
  straight down), `spread`, `out` (leave the branch outward), `face` (share facing out from the trunk), `up` (share
  spread flat facing the sky), `roll`, `bend` (cards fold at the middle, 4 triangles; 0 keeps them flat, 2), `on`
  (a test(branch): only branches it passes carry cards, e.g. the Joshua tree's rosettes on its tips). A species can
  also place its own cards after `grow` (`tree.cards = ...`, as joshua_tree.py's `rosettes`): give each an `s` under
  1 (thinning keeps every card at 1.0) and subclass `Card` if it needs an offset from the branch's axis.
- **LODs.** `build_lods`: LOD0 everything (cards thinned evenly if over budget); LOD1 coarser tubes, branches its
  levels drop, fewer cards, flat and grown to keep the leaf area (`lod1_fill`); LOD2 the main limbs and `cluster`
  cards hung on them, as many as keep LOD0's leaf area (`lod2_fill`), from cells' measured coverage. Each LOD hangs
  its cards and scars on its own drawn polyline (`Branch.drawn_at`), so nothing floats off a coarse tube.
  `impostor` renders LOD0 orthographically (albedo, normal, roughness, sky occlusion through the cutouts) onto three
  crossed quads; a leaning crown is seen along its lean and the quads sheared by it, so it leans the same way from
  every side.
- **Flat renders.** `render_passes(objs, cam, res, kinds)`: "albedo", "normal" (camera frame, flipped to face it),
  "rough", "ao" (AO node, contact shadow) and "sky" (white-sky visibility through cutouts). EXR, premultiplied.
- **Previews.** `stage()` (sky, sun, grass floor with a 1 m grid near the middle, a 1.8 m figure), `preview_tree`,
  `preview_bark`, `preview_grove`, `preview_lods`; `textured(name, paths, cutout, translucent)` shows exported maps.

## Writing a species

1. Copy birch.py's shape: textures (`make_bark`, `make_atlas`) behind the `textures` step, `VARIANTS` as
   (name, seed, spec), `main()`.
2. Bark first: draw it at the size it has on a typical trunk (pixels per cm round and up it), grade it to its
   target mean, write it, look at the PNG and at `_bark5m`. Then the sprays: build one, `frame`, render, look at
   `<script>_atlas.png`. Leaves at real size; 50 to 80 leaves (or needle tufts) per spray, filling the cell (birch's
   cover about 20 % of their cell, clusters about 30 %); grade the leaf cells to their target mean.
3. The skeleton: get the limbs' count, angles, length envelope and droop right with foliage off (spec.foliage=None),
   then the cards: spacing until the crown's density matches the spec (a card's coverage is printed per cell).
4. Check the budget lines, the LOD lineup (same silhouette and mass) and the grove at game distance; then the
   coordinator's game-shader renders beside vanilla (`unity/Build/trees/`), which decide color and density.

## Species

| Name | Script | Variants | Bark | Form | Foliage |
|---|---|---|---|---|---|
| Birch | birch.py | 01 single ~15 m, 02 leaning and curved ~13 m, 03 clump of three ~16 m, 04 young ~10 m | Chalky white, cream-pink cast (mean (180, 176, 168)), dark lenticel dashes, peeling paper with salmon underlayer, black chevron and eye scars (in the texture); black fissured foot to ~0.5 m, tongues and islands to ~1 m (on Birch01, lower on thinner trunks); dark reddish twig bark under 1.2 cm radius. | Trunk 36 cm (19 cm young) before the bundle's 1.35 scale, as stout as vanilla's pines (the first, 26 cm, looked too slim in game), a full narrow-oval crown from 35-40 % of the height (radius about 4 m, 2.5 m young) of upswept limbs, branches drooping at the ends, sky showing through here and there. | Done (the example): drooping twig sprays of 5-8 cm toothed triangular leaves (mean (84, 98, 58)), flat cards at LOD0; two cluster cells for LOD2. |
| Aspen | aspen.py | 4: three straight grove trees 14-20 m of different heights, one young 8 m (aspens stand in clonal groves, so straight and alike is right) | Smooth greenish-white to cream, powdery; black diamond "eye" scars and knots (decals, many), no lenticel dashes; rough black foot to 1-2 m; twig bark grey-brown. | Tall straight trunk 20-35 cm, short limbs only in the top third, narrow rounded crown (`shape` "oval", limbs 1-2.5 m, angle 50-35), sparse. | Round 4-7 cm finely toothed leaves with a pointed tip on long flat petioles, on short twigs that don't droop (`hang` 0.3, `up` 0.35); bright green, paler backs. Golden autumn atlas a later option. |
| Maple | maple.py | Sugar maple: 01 big round ~21 m, 02 forked low (two trunks) ~19 m, 03 narrower ~16 m, 04 young ~8 m; seedling MapleSapling. (Red maple, 3-lobed with red stalks, a later variant set.) | Grey (mean (110, 108, 104)), long irregular plates curling away along one edge (`tr.cells` with a per-plate tilt across it), soft grey-brown furrows, cross checks, small loose flakes, pale lichen, a few plates flaked to brown underbark; grey-brown twig bark under 1.2 cm. | Trunk 60 cm (built at its size in game, no bundle scale), tapering fast above the fork (taper 1.25); 6-12 big ascending limbs from 25-33 % of the height, forking now and then (`split`), a broad dome (`crown_shape`). | Five-lobed leaves 9-14 cm on long stalks (`palm_leaf`: a fan of spokes to an outline of broad toothed lobes and U sinuses; the material draws the five main veins from the stalk), opposite pairs on hanging twigs with a tip tuft (mean (70, 92, 44)); seeds paired samaras. |
| DouglasFir | douglas_fir.py | 01 mature ~30 m, 02 leaning ~25 m, 03 old broken-topped ~27 m (snapped thick: `tip_radius` 0.14 with `broken`), 04 young ~10 m limbed to the ground; seedling DouglasFirSapling. | Dark brown-grey (mean (80, 66, 57), normal relief x2.2 for deep furrows): corky ridges (`tr.cells` 9 cm, stretched 4.5) rounded and flaky on top, cracked into blocks, deep V furrows with red-brown walls; smooth grey twig bark with resin blisters under 4 cm radius. | Excurrent leader to the top, whorls of 4 limbs every 0.6-1.2 m (`whorl`), near horizontal low down rising toward the top, a narrow cone (`cone_shape`), dead stubs below the live crown (from 30-42 % up). Built at its size in game. | Dense flat sprays of real needles (`needled`: ~950 per metre of twig, 2-3 cm, most spread to the spray's sides, this year's growth paler), laid flat facing the sky (`up` 0.6); two sprays carry cones with three-pointed bracts (`cone`), which are also the seed's icon. Needles mean (60, 77, 54). |
| Larch | larch.py | 3: tall 25-30 m, leaning, young 9 m | Reddish-brown flaky plates, deep furrows at the foot, scaly on the limbs. | Very long clear trunk, sparse open conical crown of short horizontal limbs, drooping branchlets (sky shows through everywhere). | Soft tufts of 20-30 bright light green needles on spur shoots along drooping twigs (tufted spray images), small upright cones. Autumn gold atlas later. |
| WhitePine | white_pine.py | 4: mature 25-30 m with flat layered tiers, wind-flagged (limbs on one side, `favor`), forked old (two leaders), young 8 m | Dark grey, deep furrows with long narrow ridges; young smooth grey-green. | Distinct tiers: whorls of 4-5 long near-horizontal limbs every 0.7-1 m (`whorl`, gravitropism small), gaps between tiers, an irregular crown on old trees. | Long soft blue-green needles (8-12 cm, bundles of 5) in tufts at the branch ends, facing out and up; long hanging cones (10-20 cm) at the top. |
| Cottonwood | cottonwood.py | 4: big 25 m broad, forked low 22 m, leaning by water 18 m, young 9 m | Thick deeply furrowed grey bark with dark furrows, lighter and smoother on the limbs. | Massive trunk 0.6-1 m (budget: more to bark, maybe 3,000), thick upswept limbs forking (`split`), a broad open vase or irregular crown. | Triangular-deltoid 7-12 cm coarsely toothed glossy leaves on flat petioles, on stout twigs (`hang` 0.4); a lighter green. |
| WeepingWillow | willow.py | 3: big 15 m wide dome, leaning over water, young 7 m | Grey-brown, deep interlacing ridges; yellowish twig bark. | Short thick trunk forking low into arching limbs (`gravitropism` up then `droop`); level 2 long pendulous branchlets hanging straight down 2-4 m, curtains reaching near the ground. | Long hanging strands: tall narrow cells (e.g. 256 x 1024) of long thin twigs with narrow 8-12 cm lance leaves, cards hanging straight (`hang` 1.0, `spread` small, `face` 1.0), many layered; a light yellow-green. |
| Mesquite | mesquite.py | 4: wide 6 m umbrella, multi-trunk clump, crooked leaning, young shrubby 3 m | Dark grey-brown, rough, shaggy strips; thorny zig-zag reddish twigs. | Short crooked trunks (2-5 from one base, high `wander`, `bow`), spreading limbs (`gravitropism` small), a wide flat-topped crown (`shape` "umbrella"). | Feathery bipinnate leaves (many tiny leaflets), airy, spread flat facing up; some sprays with hanging yellow-tan bean pods. |
| PaloVerde | palo_verde.py | 3: typical 6 m, multi-stem, flowering (yellow) | Smooth yellow-green photosynthetic bark on trunk and every branch (green bark is the point), greyer and rougher only at the foot. | Several stems from the base, many upswept green branches dividing into a dense broom of green twigs; nearly leafless. | Cards of green twig brooms with tiny leaflets (mostly twig); the flowering variant swaps in cells covered in small yellow five-petal flowers. |
| JoshuaTree | joshua_tree.py | 01 old much-branched ~10 m (four forks deep), 02 a few arms ~6 m, 03 unbranched column ~4 m, 04 young ~2 m; seedling JoshuaTreeSapling (a rosette on a stub). | Two textures on the same tiling (`K`), so they meet without a jump: the thatch of dead leaves hanging down (JoshuaTreeBarkThatch, 1024 x 2048: rows of 12-22 cm leaves composited by height so each lies over the bases below it, tips frayed), on every tube thinner than about 15 cm (`R_BARK`, the edge wandering); rugged corky blocks (JoshuaTreeBark, mean (100, 90, 78)) on the old thick wood. | Trunk ending blunt (`broken`, `tip_radius` 0.7 r, `taper` 0.15) in a fork: each `arms` Level is 1-3 children at the parent's very end (`span` 0.97-1), 0.8 of its radius, curving up (`gravitropism`), ending blunt; `tag_tips` marks the arms nothing grows on. | Not sprays: every leaf is its own card (`rosettes`): 55-70 round the last 15 cm of each tip, newest pointing up, older further out, plus 10-16 dead ones hanging in a skirt below, cut from narrow single-leaf cells and set out from the arm's surface (`LeafCard`). LOD2: rendered rosette cells at the tips only (the cluster Foliage's `on`). Leaves aren't graded (the rosette cells carry stem and dead leaves): their linear colors are set to come out near (84, 96, 52). Seed: the fruit with flat black seeds. |
| SubalpineFir | subalpine_fir.py | 01 spire ~20 m, 02 snow-bent ~15 m (leaning, top curving back), 03 krummholz ~3.4 m (wind-flattened: `favor`, `krummholz` shape), 04 young ~6 m; seedling SubalpineFirSapling. | Smooth cool grey (mean (120, 119, 116)) mottled to pixel level, rain-grime streaks, raised resin blisters (lit from above: highlight and shadow below, some burst and dribbled amber), patches of thin scales lifting at their lower edges, lichen. | Very narrow spire (`spire` envelope), close whorls of 4 short drooping limbs every 0.55 m from the ground up (`floor` 0.15), branchlets in each limb's plane; limbs at 1.2 m rings so the bark leaves the needles most of the budget (a first version with 0.8 m rings and 2 branchlets/m spent 6,800 of 10,000 triangles on wood and looked see-through). | Brush-like sprays of dense dark blue-green needles (`needled`, 1,100/m, crowding up round the twig), snow lying in drifts along the twigs' tops (`snow`: elongated lumps, few: round blobs read as polka dots); upright cones standing up the card (+y is the tree's up there); cards 1.2-1.6 scale. Seed icon: two scaly cones on a sprig. |
| CharredSnag | charred_snag.py | 01 tall snag ~14.6 m, 02 thick stump ~5.8 m, 03 leaning half over ~11 m (6 m lean, straight), 04 split into two leaders ~13 m; no seedling (felled ones drop vanilla's mountain pine seed, as its burnt pines do). | Charcoal (mean (40, 38, 36), graded on the charcoal only, so the bare wood keeps its grey): long plates 12 cm between straight black furrows, each checked into domed 2 cm blocks (alligator) with finer checks, a dull silvery sheen on some; a few plates fallen to grey wood; ash in the furrows. Twig bark the same, finer; `wood` (bare weathered wood) on splinters and the last stretch of every snapped end (`bark_key`). | No foliage: trunks `broken`, 2-2.6 burnt limbs per metre (`broken`), some with burnt twigs; `stubs` used for 3-7 splinters standing up out of the break (tag "splinter"). 700-2,300 triangles. | None. |

## Notes on the engine side (for the Unity prefabs)

- Game/SpeedTree8, palm wind; NatureTreeBuilder computes the per-vertex data: branch sway from the distance out from
  the trunk, leaf flutter per connected card patch (scar decals, told apart by their UVs in the scar cells, get
  none), occlusion from the depth in the crown. The trunk base sits near the origin.
- Card normals are flat (the face's own); the SpeedTree material draws both sides. The leaf atlas's normals face the
  camera they were rendered from (a leaf seen from behind shows its back).
- Leaf albedo alpha is anti-aliased coverage: cut at 0.5. Unity's "mip maps preserve coverage" (alpha cutoff 0.5)
  keeps distant crowns from thinning out.
