# Harsh-biome ground cover (snow, burnt forest, wasteland): model spec

Seven small walk-through decorations, placed by world generation like the wildflowers. Each is a patch about 0.8 to 0.9 m
across lying on the ground (ground at z = -0.5 = nk.GROUND), built the way FLORA.md describes (Blender meters, Z up, the
block's center at the origin). None of them is a textured card: the ground under each is a ragged height-field with
real relief whose rim is sunk 1 to 1.4 cm below the terrain and dissolves into the ground through the texture (t = 1 in
the middle, 0 at the rim), a few small ragged outliers of the same material lie round it, and everything on it is real
geometry (plates, stones, sticks, scraps, stems) with a normal map baked from procedural relief. No alpha textures, nothing
emissive or glowing. Nothing is solid: all seven are walk-through plant-shader blocks (the builder doubles the faces).

Scripts are in `NatureExpanded/blender/` (one per piece, snake_case). They share a small helper kit,
`NatureExpanded/blender/groundcover/gckit.py` (ragged patch, stones, plates, slabs, shared materials, the preview
shots); it is only imported by these seven scripts and changes nothing else. Run:

    blender -b --factory-startup --python <script>.py -- <unity Models folder> <preview folder>

Render and bake run on the CPU by default (set `GC_CPU=0` for the GPU). `GC_SIZE=2048` rebakes at a different atlas size.
Output goes to `NatureExpanded/unity/Assets/NatureExpanded/Models/<Name>/` (<Name>.fbx with <Name> and <Name>_LOD1,
<Name>_Albedo.png, _Normal.png, _RMOM.png). Previews: `NatureExpanded/unity/Build/previews/<script>_{stand,crouch,macro,top,far,lod,lodfar}.png`
(stand = eyes 1.65 m up, 1.1 m off; crouch = eyes 0.5 m up; macro = 30 cm over it; far = 3 m off with six neighbors; lod =
the far mesh at crouch distance; lodfar = the far mesh at 3 m).

## Common numbers and notes for the integrator

- Atlas: all seven baked at 1024. Texel density (px/cm) is printed by each script; the main surfaces get 6 to 14 px/cm
  (see table). **FLORA.md says non-solid plants drop to 512 in the bundle; please keep these at 1024** (at 512 the ice
  cracks, the char blocks, the gravel chips and the rust crazing fall to 3 to 7 px/cm and go soft at crouch distance). If
  the 512 rule can't be bypassed, they still read, but the close-up detail is lost.
- Far LOD: `<Name>_LOD1` is made by dropping the small parts (needles, spikes, chips, flakes, twigs) and decimating the
  ground and big stones, 22 to 40 % of the near triangles. The tumbleweed's far mesh also has a 80-triangle opaque stand-in
  shell (far-only), see below.
- Footprints spill a little over the 0.9 m block where noted (wind tails of ash, a long stick, the weed's seed stalks); the
  game doesn't mind.
- The pieces are rotated at random by the game; nothing in them is mirrored or gridded.
- Meshes carry no custom vertex data the game needs (t / lod / pivot are stripped on export). The CharredSticks material
  used a `grain` vertex attribute at bake time only; it is not exported.

| Name | Script | Near / far triangles | Footprint (x, y) | Height | px/cm main surfaces |
|---|---|---|---|---|---|
| IceCrust | ice_crust.py | 2,163 / 748 | 0.78 x 0.87 | 7.7 cm | ice 7.3, mud 4.1, edges 3.5 |
| FrostHeavedStones | frost_heaved_stones.py | 3,187 / 785 | 0.89 x 0.85 | 15.8 cm | stone 13.9, pedestal 10, soil 6.0 |
| AshPatch | ash_patch.py | 2,158 / 561 | 0.88 x 0.83 | 8.9 cm | ash 10.5, char 11.8, rock 14.1 |
| CharredSticks | charred_sticks.py | 2,534 / 622 | 0.86 x 0.97 | 11.1 cm | sticks 12.8, ash 6.9 |
| GravelPatch | gravel_patch.py | 2,433 / 496 | 0.84 x 0.79 | 24.8 cm (weed seed stalks; the stone patch itself is under 8 cm) | chips 12.4, concrete 12.0, bed 6.7 |
| RustFlakes | rust_flakes.py | 1,633 / 374 | 0.96 x 0.89 | 12.3 cm | rust 14.4, ground 7.8 |
| DeadTumbleweed | dead_tumbleweed.py | 3,271 / 1,256 | 0.55 x 0.47 | 39 cm | stems at 1024 (thin) |

## 1. IceCrust (display name "Broken Ice")
A frozen puddle: fifteen thin plates (6 to 10 mm, 14 to 36 cm across, irregular straight-broken outlines) of opaque,
glossy, milky-blue ice resting on a ragged bed of black frozen mud, tilted 1 to 12 degrees, riding up on one another where
they overlap, each with its own thickness. Painted "depth": milky and clear blue zones, clear ice showing dark mud under it,
straight fractures drawn twice (a white line and an offset blue shadow so they seem to lie inside the ice), three
impact-star cracks, trapped bubbles with dark rims in clusters, frost bloom, dirty gritty edges where mud soaked up into
the thin rim. A little hoarfrost needles on some edges, fallen pine needles and frost-cracked mud with snow creeping in at
its rim. Glossy (roughness 0.08 to 0.15 on the ice).
- Walk-through, decoration only, no loot. Harvest: none.
- Placement: snow biome only; in hollows and next to water/frozen lakes if the generator can tell; uncommon (about one block
  in 60, not on deep drifts). Looks best sparse.
- Weak spot: the ice is opaque (no refraction), so "translucency" is the painted depth and the dark mud showing through the
  plates' gaps. At 3 m it reads as a patch of blue-grey ice plates; against very bright snow in game it may need a
  slightly lower albedo.

## 2. FrostHeavedStones (display name "Frost-Heaved Stones")
Seven fieldstones 6 to 18 cm across, each perched on a short neck of frozen soil (2 to 7 cm tall, flared at the foot,
striped with vertical needle-ice grooves, pebbles frozen into it) so they look like mushrooms; a ring of thin white
needle-ice spikes round every foot, five tufts of needle ice among them, frost-cracked ground with rimed cracks, a few
little snow drifts in their lee, a dusting of snow on the stone tops and pine needles. Stones are granite-grained with
lichen, rain streaks and soil crusted on the lowest part.
- Walk-through (stones are 6 to 18 cm, below knee height; if the integrator makes it solid, only the three big ones need a
  box). Harvest (proposed): pick up for 1 to 3 `resourceRockSmall` (stone), one pick-up consumes the block. Needle ice and snow
  are decoration only.
- Placement: snow biome, bare ground and gravel patches rather than deep snow; common-uncommon (about one in 45).
- Weak spot: the needle-ice spikes are 3-triangle cones with a lit white color; at 3 m they are specks and in the far LOD
  they are dropped.

## 3. AshPatch (display name "Ash Drift")
A drift of grey-white wood ash over scorched soil: low wind-ridged dunes (crests across the wind, a tail of ash blown out
behind every obstacle, a scour hollow in front), fine wind ripples in the texture, dry cracks that open onto dark soil,
crumbs and flakes of charcoal and pale ash, 16 charcoal lumps, three half-burnt wood chunks, four curled flakes of burnt
bark (thick slabs with a rim), five black twigs, burnt needles and a rock blackened and heat-cracked by the fire (rusty
oxide haloes, spalled flakes, ash on top). Ragged rim of thin ash over soot with seven small outlier patches.
- Walk-through. Harvest: none (optionally the chunks could drop `resourceCoal`, but the brief says none).
- Placement: burnt forest, common, in clusters (about one in 30), best near CharredShrub and burnt trees.
- Weak spot: the char is an alligator-skin cell pattern, fine at 1 m but a little regular on the bark flakes at macro range.

## 4. CharredSticks (display name "Charred Sticks")
Nine burnt sticks and branch stubs, 15 to 50 cm long and 1.3 to 4.2 cm thick, lying criss-cross on a bed of grey ash, each
resting on the ones below (computed, not placed by eye). Alligator-skin char with silver-white weathered wood showing
where the char has flaked off (grain running along each stick whatever way it lies), ash on the up sides; broken ends
are fresh brown splits with 2 to 4 splinters, a few 4 to 9 cm branch stubs (also with split ends); no embers or glow.
Charcoal crumbs, burnt needles and ripple-and-crack ash bed with six outlier patches.
- Walk-through (sticks are a few cm thick). Harvest (proposed): break for 1 to 2 `resourceWood` (the vanilla `resourceCoal` also exists in
  the game if charcoal is preferred; I'd use wood 1 to 2 with a 30 % chance of 1 `resourceCoal`).
- Placement: burnt forest, common (about one in 25), same zones as AshPatch and more frequent.
- Weak spot: the silver-white patches are subtle at 3 m (they read as paler grey on the sticks); the sticks' strong dark
  value is what carries the read. One stick can reach 0.53 m from the middle.

## 5. GravelPatch (display name "Rubble Gravel")
A bed of coarse gravel (three sizes of chip heaped over one another, each its own grey, brown or tan, dust in the gaps),
54 loose angular chips (1.6 to 4 cm, a color picked per chip), 12 pieces of crushed concrete 3 to 8 cm (pale cement with
fine aggregate and air pits, weathered, dust on top), a concrete slab chunk 17 cm with a stub of rusted rebar, a brick end,
a half-sunk 15 cm boulder, a tongue of wind-blown rippled dust drifting over one side and burying the small stones, a tuft
of dry weed (14 blades, 3 seed stalks to 25 cm) at the edge. Ragged rim of loose chips.
- Walk-through. Harvest (proposed): pick up the stones for 1 to 2 `resourceRockSmall`; the weed tuft decoration only.
- Placement: wasteland, common (about one in 25), near roads, rubble and ruins.
- Weak spot: the chips are smooth faceted lumps (15 triangles); fine in the bed's context, a little plain on their own at macro.
  The brick end is the only red in the piece.

## 6. RustFlakes (display name "Rusted Scrap")
Three scraps of corrugated iron (one 27 x 22 cm with its end curled up, one folded along a crease and galvanized-grey under its
rust, one torn little piece), paint faded and flaking to dark rust with steel glints, torn jagged edges; a hex bolt, a washer, a crown
bottle cap (plain faded dark-red enamel, a pressed ring, no lettering or brand), three nails, a few turns of rusty wire, 46 loose
curled rust flakes (orange, brown, near-black, pale powder) and rust stains in the dust round each piece. The ground is dry
dusty crust cracked into curling plates, ragged rim, outliers.
- Walk-through (the sheets are 1 cm high at the ridges, the curl 12 cm). Harvest (proposed): pick up for 1 to 2 `resourceScrapIron`.
- Placement: wasteland, uncommon (about one in 40), near ruins, roads, junk.
- Weak spot: sheets are single-sided sheets (no thickness; the builder doubles the faces); the big curl reads as a fabric-like
  curve from some angles. The bolt, washer and cap are tiny (1 to 3 cm) and mostly seen only up close.

## 7. DeadTumbleweed (display name "Dead Tumbleweed")
A dead Russian thistle 41 cm across, a hollow sphere of its own stems: 14 main stems from a small knot at the middle sweeping
out round the shell, 20 more arcing round it on their own, 5 cutting across the inside, side sprigs with spiny awl leaves, 55 thin
twig strips, about 25 dry papery seed pods, all smooth Catmull-Rom curves, grey-tan with bleached tips and the red-brown pigment
left at the stem bases. You can see through it. A few husks and snapped twigs lie round it. Static: it does not roll.
Far LOD: 14 main stems, 10 arcs and an 80-triangle opaque stand-in shell (far-only, so the near mesh never shows a solid ball).
- Walk-through, decoration only. Harvest (proposed): 1 to 2 plant fibers (`resourceYuccaFibers` in vanilla, please confirm the item name).
- Placement: wasteland (and desert if wanted), common but sparse and single (about one in 20), in open ground away from trees.
- Weak spot: the far stand-in shell is a paler, solid-looking ball (lodfar preview) and could be darkened a notch if the far
  mesh looks like a white ball in game; thin (2 to 3 mm) stems at 1024 go sub-pixel past about 5 m, which is the point of the stand-in shell; the near
  mesh is at the top of the triangle range (3,271).

## Not done / doubtful
- Everything checked only in Blender previews, not in the game's shader (no Unity run, as briefed).
- The previews' lighting is brighter than the game's; albedos were kept vanilla-dark.
- IceCrust's gloss and FrostHeavedStones' white needles depend on the game's specular and probe lighting.
