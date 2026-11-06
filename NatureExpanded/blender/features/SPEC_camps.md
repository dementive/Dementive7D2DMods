# Abandoned camps (CampTent, CampLeanTo, CampChairs, CampFishing)

Scripts (`blender/features/`): `camp_tent.py`, `camp_leanto.py`, `camp_chairs.py`, `camp_fishing.py`, on two new kit
modules `campkit.py` (materials, cloth/log/lathe builders, Place transform) and `campprops.py` (cans, bottles, bucket,
pot, lantern, chair, cooler, rolled tarp, fish bones, fire ring). Run each as
`blender -b --factory-startup --python <abs>\camp_x.py -- <abs Features dir> <abs previews dir>`.
Env: `CK_BAKE_SAMPLES` caps bake samples (final used 12), `CK_NEUTRAL=1` grey geometry check, `LK_SIZE` atlas size.
Output: `unity/Assets/NatureExpanded/Features/<Name>/` (fbx with Name + Name_LOD1, _Albedo/_Normal/_RMOM at 2048,
`_colliders.txt`); previews `unity/Build/previews/features/camp*_*.png`.

All four: 5x5 footprint (extent about +-2.3 m, printed as `[extent]`), square (no `rect`), cloth built as two sheets
3 mm apart (the game culls back faces), no emissive anything. Not played, not run through Unity.

| Name | Display name | Tris / LOD1 | Height | Blocks | Solid (colliders) | Harvest kind | Biomes |
|---|---|---|---|---|---|---|---|
| CampTent | Abandoned Tent Camp | 15102 / 8917 | 0.64 m | 5x1x5 | 9 fire-ring stones, log seat, stump seat, a low core under the canvas (99 voxel boxes), firewood bundle (one box) | `cloth` (canvas) or `wood`; `scrap` ok | pine/mixed forest, meadow edge, taiga; common |
| CampLeanTo | Collapsed Lean-To Camp | 17663 / 8900 | 1.30 m | 5x2x5 | 2 posts (capsules), 7 stones, rack post (capsule), firewood stack (box); tarp, ridge, rack, pot, bucket walk-through | `cloth` (tarp) | pine/mixed forest, taiga, burnt forest; uncommon |
| CampChairs | Abandoned Car Camp | 16856 / 11457 | 0.88 m | 5x1x5 | 9 stones, stump, cooler (one box); chairs, grate, cans, bottles, lantern, tarp roll walk-through | `scrap` (chairs, grate, cans) | meadow, forest edge, roadsides, desert/wasteland edge (no snow); uncommon |
| CampFishing | Fisherman's Camp | 10216 / 7020 | 0.85 m | 5x1x5 | split-log bench, its stub leg and the fallen stub, 7 stones; rod, bucket, chair, cans, cord walk-through | `wood` (bench) or `scrap` (bucket, cans) | shores only: lake and river banks on flat ground within a few cells of water (the water side is -y in the model, but the block turns in quarter turns, so it needs no orientation); rare |

Ideas for the integrator: the block's drop is the one kind per block, so pick one: cloth for the tent and lean-to, scrap
for the chairs, wood for the fishing camp. Harvest counts are best low (these are small solid parts; a hit on any
cell hits the master). The decorator only wants flat ground and ignores the model's tarp/rope extents beyond the 5x5.

Doubts and weak spots (honest):
- Cloth reads as flat, clean-edged fabric from 2 m; torn edges and holes are geometry, tears are only dark texture
  lines. The tarp sags and wrinkles but it is still smooth for a tarp.
- Lean-to is 2 cells high (posts 1.2 m, ridge dropped); all else is under 1 m. Zombies path round the whole footprint.
- The enamel pot came out pale grey, not rusted enough; the lantern globe is an opaque grey blob; webbing is cleaner than
  it should be; the bones in the fishing bucket are hard to see (they sit low inside it).
- Fire-ring stones are sooted dark grey and a little uniform; leaf litter and grass are cheap cards (LOD1 drops them).
- Colliders were not checked in Unity (the featurekit export prints the box counts: 99, 27, 116, 62; the extra
  capsules/boxes are inside the mesh bounds by construction). The tent's collider "core" under the canvas is only 13 cm high.
- Bakes are at 12 samples (AO/albedo slightly noisier than the other features), one iteration at 2048 per camp.
