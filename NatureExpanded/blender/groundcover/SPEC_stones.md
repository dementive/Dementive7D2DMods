# Ground cover: stones, shore and desert (nine models)

Built with `blender/kit_stones.py` (shared kit: stones, plates, wood tubes, materials) on top of naturekit, kit_forest,
kit_shrub, featurekit (granite) and zkit. One script per model in `blender/`. Run, one at a time:

    blender -b --factory-startup --python <script>.py -- <unity models folder> <preview folder>

Env switches: `STONES_FAST=1` (512 atlas, cheap previews), `STONES_SHOTS=crouch,macro` (which previews), `STONES_GEOM=1`
(geometry only, prints triangles). Previews written: `<script>_crouch|macro|far|lod|stand|top|patch.png` in
`unity/Build/previews`.

All are block models like the plants: ground at z = -0.5, piece lying on it around the origin, no collider, walk-through.
All meshes are closed to the ground (faces under the ground dropped, a 3 cm skirt below it). Materials: baked atlas
(Albedo/Normal/RMOM) 1024, near mesh + `_LOD1` (decimated, tiny parts dropped), same atlas, via ks.export.
No alpha, no emission, nothing mirrored.

| Name | Script | Tris / LOD1 | Footprint (m) | Height (m) | Notes |
|---|---|---|---|---|---|
| PebblesA | pebbles_a.py | 1877 / 481 | 0.63 x 0.6 (stray gravel to 0.3 off) | 0.045 | tight cluster of 15 stones + 9 gravel specks, grey/pink granite, sandstone, 1 quartz, soil pad |
| PebblesB | pebbles_b.py | 2532 / 601 | 0.78 x 0.78 | 0.077 | loose scatter around one 24 cm chipped pink granite stone, ~13 stones + gravel |
| PebblesC | pebbles_c.py | 2414 / 662 | 0.82 x 0.33 (a trail along x) | 0.042 | 20 stones strung in an S-curve, large end to gravel end, dirt smear |
| FlatStones | flat_stones.py | 2154 / 800 | 0.96 x 0.79 | 0.04 (grass tufts to 0.14) | 5 slabs 25-45 cm, 4 cm cracks, moss cushions + grass in cracks, soil in cracks |
| Driftwood | driftwood.py | 2033 / 515 | 1.05 x 0.76 (limb tips overhang) | 0.13 | 90 cm twisted limb with stub, 55 cm crooked branch, 30 cm chunk, dried weed wisps, pale shore sand |
| RiverStones | river_stones.py | 2237 / 781 | 0.87 x 0.9 | 0.086 | 16 wet dark stones (8-25 cm), 4 with a pale quartz band, damp sand bed |
| CrackedMud | cracked_mud.py | 2526 / 884 | 0.97 x 0.79 | 0.054 | 30 curled plates, 2 cm cracks, dust floor, ragged rim |
| ShaleChips | shale_chips.py | 1922 / 503 | 0.81 x 0.81 | 0.077 | ~85 thin angular plates and chips, stacked and leaning, scree skirt |
| BleachedBranch | bleached_branch.py | 1299 / 453 | 0.84 x 0.9 (diagonal) | 0.16 | 1.1 m dead branch, forked end, checking, half buried in a rippled sand drift |

Display names: Pebbles A / B / C, Flat Stones, Driftwood, River Stones, Cracked Mud, Shale Chips, Bleached Branch.
Triangle counts are all inside 800-3000. Texel density (px/cm at the 1024 atlas): stones 15-18 (pebbles), 9.9 (river
stones, flat tops, mud tops, shale tops), 8.8-11 (wood); ground pads (soil, sand, scree, mud floor) 4-11, they are
flat dust and only need color.

## Atlas size (important)
FLORA.md says non-solid models drop to 512 in the bundle. At 512 these lose half their crispness (pebbles 8-9 px/cm,
the rest 5 px/cm). Keep these nine at 1024 if the integrator can (they are small and have no other textures).

## Proposed harvest / placement (not defined in code)
- PebblesA/B/C, FlatStones, RiverStones, ShaleChips: pick up for 1-3 stone (destroy on pickup, like the wildflowers).
- Driftwood, BleachedBranch: 1-2 wood.
- CrackedMud: none (decoration only; can be walked over, destroyable for nothing or not at all).
- Placement (rarity relative to the wildflowers; spawn on the ground only, one per block, random yaw):
  - PebblesA/B/C: any biome ground, forest edges, meadows, burned forest, snow (they poke out of snow poorly: skip snow);
    A common, B uncommon, C uncommon. FlatStones: forest and meadow near roads or ruins, rare. 
  - RiverStones: shorelines and creek beds (next to water, wet sand), uncommon, in groups of 2-4.
  - Driftwood: shorelines and lake edges (pale sand/mud), uncommon, 1 in 3 blocks near water.
  - CrackedMud: desert and dried lake beds, common in dry basins. BleachedBranch: desert, uncommon, also wasteland.
  - ShaleChips: desert, mountains, burnt/wasteland rubble and cliff foot, uncommon.

## Weak spots (honest list)
- Stones are smooth water-worn shapes: good for pebbles and river stones, but they are not angular quarry rock; the
  lumpiness comes from displaced super-ellipsoids with chips, not sculpting. Textures at 1024 look right at 1 m, a bit soft
  at 25 cm.
- Pale quartz band on RiverStones reads clean/stripey up close (4 of 16 stones); gloss is the baked roughness.
- CrackedMud plates have visible polygon corners at macro range (rounded once or twice, tri budget); the cracks are
  wider than real mud cracks at ~4-5 cm to read from 3 m.
- Moss cushions on FlatStones are lumpy domes; grass is a few thin blades (2 tris each segment).
- Driftwood weed is a few flat dark strands; wood grain is a baked stretched noise (zebra-like at macro distance, softened
  but still regular), UV island seams are faintly visible on the thick limbs.
- Soil/sand pads under pieces are flat dark/pale discs with ragged sunk edges; against ground that is much lighter or
  darker than the previews the edge will show (they are the "dirt" blending trick, no alpha).
- Shale chips: a few leaning chips float a mm above the heap (hidden by shadow).
- Not seen in the game shader (no Unity run, as instructed); previews are Cycles on a flat stage floor.
