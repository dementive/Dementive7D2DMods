# Single finds, set B (Nature Expanded features)

Six small abandoned "single find" props, all built by `blender/features/singles_b.py` on the shared helpers in
`blender/features/singlekit.py` (on `featurekit.py` and `logkit.py`). Output: `unity/Assets/NatureExpanded/Features/<Name>/`
(`Name.fbx` with `Name` and `Name_LOD1`, `_Albedo/_Normal/_RMOM.png`, `_colliders.txt`); previews:
`unity/Build/previews/features/<name>_{far,mid,close,back}.png` (far = 8 m, mid = 2.5 m, close = arm's length, back = the other side).
Nothing was run in Unity.

    blender -b --factory-startup --python <abs>\blender\features\singles_b.py -- <abs features folder> <abs preview folder> [Name ...]

Optional environment: `SB_SIZE` overrides the atlas size (the table shows what was baked), `SB_BAKE` bake samples per map
(default 6; the materials are deterministic, 64 samples only cost time). Use a low-priority process with `--threads 2`: the
whole set bakes in under half an hour on a quiet machine.

All six are weathered "years abandoned, half swallowed by the ground and the weeds": soil mounds around and under them,
leaf litter, double-sided grass blades and broad weed leaves (feature materials are drawn one-sided, so every blade is
built with a back face), soil and mould baked into the textures. Variation inside each: the block is rotated by the game,
nothing is mirrored; every prop has its own damage (dents, tears, missing parts).

## Summary

| Name | Display name | Footprint | Height | Tris / LOD1 | Atlas | Collision | Harvest kind | Placement |
|---|---|---|---|---|---|---|---|---|
| `BrokenCooler` | Broken Cooler | 1x1 | 0.71 m (lid up) | 5016 / 2121 | 1024 | walk-through (1 hit box) | `scrap` | wasteland, roadsides, burnt forest; uncommon |
| `ShoppingCart` | Tipped Shopping Cart | 3x3 | 0.55 m | 9606 / 4530 | 2048 | solid low hull (wires see-through) | `scrap` | wasteland, roadsides (towns' edges); uncommon |
| `RustyBucketCans` | Rusty Bucket and Cans | 1x1 | 0.29 m | 10102 / 4780 | 1024 | walk-through (5 small hit boxes) | `scrap` | wasteland, roadsides, burnt forest, any lowland; common |
| `FirewoodStack` | Collapsed Firewood Stack | 3x3 | 0.78 m | 7550 / 4922 | 2048 | solid (stepped hull under the logs) | `wood` (axe) | pine forest, forest edges; uncommon |
| `AbandonedPack` | Abandoned Backpack | 1x1 | 0.31 m | 8952 / 3074 | 1024 | walk-through (1 hit box) | `cloth` | forest, meadow edges, wasteland; uncommon |
| `RustedBicycle` | Rusted Bicycle | 3x3 | 0.51 m | 11214 / 4127 | 2048 | solid low slab (spokes see-through) | `scrap` | wasteland, roadsides; uncommon |

Footprint is the odd square the geometry needs (the script prints `extent ... -> footprint NxN`); the three small ones stay
inside +-0.5 m (1x1), the large ones need 3x3. Suggested `BigDecorationRadius` is the usual half footprint plus 1. Relative
rarity suggestion (where 1.0 = a MossyBoulder): bucket 0.8, cooler 0.5, pack 0.5, firewood 0.5, cart 0.4, bicycle 0.4. They are
flat-ground decorations only (the decorator already requires a flat master cell).

## Per prop

**BrokenCooler.** A 58 x 36 x 34 cm ice chest of sun-faded, chalky blue plastic with a yellowed white lid hung open and askew
on one snapped hinge (lugs: one whole, one half gone). Hand recesses in the ends, a chipped rim corner, hairline cracks and
crazing, algae and soil low down, a rotted label band on the long sides (faded red stripes peeling off in patches, plain
stripes: no text, no brand), dirt and dead leaves and a weed growing out of it. Walk-through: one oriented hit box
(`Collide melee`, kind `scrap`). Could be solid if wanted: swap the hit box for a body (it is 0.34 m, a step-up).

**ShoppingCart.** Wire cart lying on its low side, racked and crushed (a front corner caved in, a second dent, cut rails,
missing and short uprights, a hanging child-seat flap), three casters and one torn off with its bracket bent, a faded red
plastic handle grip, weeds growing up through the basket, soil mounded round the low wires. Wires are thin closed 4-5 sided
bars (about 6 k triangles, the thin ones are dropped from the far LOD). Solid collision is only a low slab (20 voxel boxes,
0.2 m thick) along the lower side, so you can see and shoot through the rest. Kind `scrap`; the pick/wrench harvest count can be
small (about 8).

**RustyBucketCans.** A galvanized pail lying on its side (spangled zinc, white corrosion, a rust bloom, three dents, a bent-in
rim, stamped ribs, a rusted-through hole in the base showing toward -y, bail wire flopped over) with four cans: one closed with
half a faded label, one torn open with the lid peeled back and the rim ragged, one crushed flat, one squat tuna can standing.
Labels are plain stripes (no text). Walk-through with five oriented hit boxes. Kind `scrap`.

**FirewoodStack.** About 1 m wide, 0.5 m deep, 0.78 m high: split logs (halves, thirds, quarters and a few small rounds, 4.5 to
8 cm radius) in rows that settled by dropping each log onto the ones below, the right end slumped and a dozen logs tumbled
down it and onto the ground. Grey weathered bark with peeled patches and curling loose bark strips, silver split faces, dark
grey-brown end grain with rings and checks, moss and algae low down, bracket fungus on the end logs, small mushrooms at the
base. Solid: a stepped hull a few cm under the log tops (5 voxel boxes), the fallen logs are not solid. Harvest `wood` with an
axe (`resourceWood`, tags as the timber features); suggested count about 24 (the visible wood is roughly 0.5 m3).

**AbandonedPack.** A canvas rucksack lying on its back, olive canvas gone grey-green with mould, three torn holes (cloth pushed
in, dark lining and frayed rim), a flap open over the front pocket, two compression straps and a buckle, a sleeping bag roll
(faded maroon nylon, wound layers visible on the ends, two lashings of twisted rope with the ends hanging), one shoulder strap
whole, one torn through with the frayed pieces lying apart and loose threads, and a dent of flattened dead grass and dark soil
beneath it. Walk-through, one hit box (0.36 x 0.78 x 0.15). Kind `cloth`.

**RustedBicycle.** A 26" bicycle lying on its right side at about 75 degrees: diamond frame (faded blue paint almost all
flaked to rust), a dent in the down tube, handlebars turned hard over, the front wheel folded in a potato-chip taco with
spokes broken or missing, rear wheel true, flat cracked tires, rusted rims and 36 thin spokes per wheel, cracked leather
saddle, chainring with teeth, crank arms with one pedal gone, a slack chain, cables hanging. Weeds through the spokes. Solid
collision is only a low slab (14 voxel boxes) under the wheels and frame. No brand marks anywhere. Kind `scrap`.

## Weak spots and notes for the integrator

- Not checked in Unity: the collider sidecars (boxes, rotated boxes for the walk-through ones) were made by the kit and lie
  inside the mesh bounds by construction; the bundle build's own check is the real test.
- The cart's and the bike's far LOD keeps the rails and frame and drops the thin wires and spokes; at 50 m they read as a
  skeleton. The tires and wheels use LOD decimation only for the lathe parts.
- Weeds are low-poly dark blades; they are the weakest part up close (they read a little stiff and spiky). They are cheap to
  thin out in `tuft` calls if they cost too much.
- Rust is deliberately dark and varied; the galvanized bucket is the greyest, the cart wire and bike frame the most rusted.
- Rubber is paler than vanilla tires in the previews (the stage's sky reflection on a rough surface); the albedo itself is dark.
- Texel density: the 1024 props give 6 to 10 px/cm on the main surfaces, the 2048 ones 6 to 10 px/cm on wire, wood and metal,
  2 to 3 px/cm on weeds and soil (intended).
- Triangle counts include weeds, soil and leaves (about a third); the pack's rope (3.5 k) is the heaviest single piece and is
  decimated in LOD1. If the budget is tight, drop `helix_rope` to one strand or remove the second lashing.
- Every output folder holds a complete set from the final bakes (checked on disk). Only `singles_b.py`, `singlekit.py` and this
  file are mine in `blender/features`.
