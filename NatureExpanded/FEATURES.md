# Solid natural features

Boulders, glacial erratics, rock formations (hoodoos, arches, spires, columns, outcrops), cairns, bone remains, and
the logs, stumps and windfalls of wave 2 that need to be solid: multi-block model blocks placed by world generation,
that players, zombies, animals and vehicles collide with, that can be climbed, and that break up with the right tool.
The mossy log (a plant, `PlantDEM`) is NOT one of these: its collider is a melee hit box you walk through.

## How the game does it (checked in IL, 2026-11-04)

- **Shape and placement.** A feature is `Shape ModelEntity` with `MultiBlockDim`, exactly like vanilla's
  `resourceRock01` (3x2x3 boulder). The master cell is the bottom, middle one: x and z run from `-(d/2)` to
  `round(d/2 + .1) - 1`, y from 0 up. Use ODD x and z (the master centered, so a quarter turn leaves the footprint
  where it was; even dims also shift the model half a block). `rotatemax="3"` with `OnlySimpleRotations` gives four
  quarter turns. The decorator (`WorldDecoratorBlocksFromBiome.decorateSingleBlock`) checks only the master cell is
  air and the biome's slope limit (`CanDecorateOnSlopes` false: flat ground only, as vanilla boulders); it then fills
  every cell of the footprint with child blocks (`Chunk.SetBlock`), which is also what keeps other blocks out of an
  arch's opening. `BigDecorationRadius` > 0 reserves the surroundings from other big decorations and shifts the
  placement so the footprint stays inside the chunk pair it knows about (keep it at half the footprint plus 1).
  `IsTerrainDecoration` keeps the terrain from being snapped under it, `StabilitySupport false` and the stone
  material's `stability_glue` keep it from falling or breaking with stability.
- **Colliders.** `Chunk.OnDisplayBlockEntities` sets every collider of the model to the movement layer when the block
  has `Collide` containing `movement` (`Utils.SetColliderLayerRecursively`); otherwise they stay on layer 16 and
  nothing walks into them (that is why the mossy log is walk-through). So: `Collide="movement,melee,bullet,arrow,rocket"`
  for solid things, `melee` alone for walk-through ones. Any mix of Box/Sphere/Capsule colliders in the prefab works
  (vanilla uses a non-convex MeshCollider on layer 16 child "Mesh"; we use convex primitives only).
  **Never put a collider on the prefab's ROOT**: `BlockShapeModelEntity.PoolCreateOnceToAllCallBack` turns a root
  Box/CapsuleCollider into the block's one custom AABB (`isCustomBounds`: step height = its height, used by the AI
  grid and movement checks), which would be a box round the whole arch.
- **Tag.** Raycasts count a collider as part of a block only when it is tagged `T_Block`; bundles can't carry the
  tag, so `BlockFeatureDEM` (class `FeatureDEM, NatureExpanded`) sets it on every collider, and moves the model's
  materials to the game's plant shader (`NatureShaderDEM`; a material named `Feature_<Name>` gets back faces culled, no
  wind, no translucency).
- **Harvest.** `<drop event="Harvest" name="resourceRockSmall" count="N" tag="oreWoodHarvest"/>` is vanilla's boulder
  recipe: a pickaxe (or any tool with the `oreWoodHarvest` tag) pays out stone per hit, scaled by damage, until the
  block (`Mboulder`, 400 HP, `PassThroughDamage` so a hit on any cell hits the master) breaks. `Destroy` drops nothing.
- **Multiplayer.** Everything is world generation plus ordinary blocks; the dedicated server instantiates the same
  model (colliders included) to simulate zombies. The mod (the bundle too) must be installed on the server.

## Adding a feature

1. **Blender script** `blender/features/<script>.py`, built on `featurekit.py` (read `mossy_boulder.py`, the worked
   example). Run one Blender process:

       blender -b --factory-startup --python <abs>\blender\features\<script>.py -- <abs>\unity\Assets\NatureExpanded\Features <abs>\unity\Build\previews\features [Name ...]

   Conventions: meters, Z up, the master cell's center at the origin, the ground at z = -0.5 (`fk.G`); stay inside
   an odd square footprint (the builder prints the footprint it needs); the model sinks `fk.SKIRT` (0.4 m) below the
   ground so terrain unevenness never shows a gap (faces wholly under the ground go to a cheap "Skirt" material that
   gets about a tenth of the atlas). Build closed, outward-facing meshes (the colliders are made from them), put the
   body's faces in `b.lod = 2` (the far mesh decimates those), and call `fk.export(name, pieces, bodies, out_dir,
   size=2048, ...)`, where `bodies` is a list of `(vertices, polygons)` of the closed meshes that must be solid
   (`fk.emit_rock` returns one; build your own for non-rock things, e.g. each stone of a cairn, each arch pier).
   `export` voxelizes the bodies into boxes lying inside the mesh (so players never hit empty air and an arch's
   opening stays open by construction), writes `<Name>_colliders.txt`, the atlas (`Name_Albedo/_Normal/_RMOM.png`)
   and `Name.fbx` with `Name` and `Name_LOD1`. Extra colliders go in `extra=["sphere cx cy cz r", "capsule x1 y1 z1 x2 y2 z2 r",
   "box cx cy cz sx sy sz ux uy uz vx vy vz wx wy wz"]`; `probes=[(x,y,z,dx,dy,dz)]` are rays that must hit nothing
   (put one through every arch opening; the Unity build fails if it is blocked). Walk-through things (bones): give
   them one or two small boxes and make the block's kind `bone` (Collide melee).
   Material helpers: `fk.granite(...)` (surface of mossy granite as node signals in `granite_surface`), copy and adapt it
   for sandstone, ice, etc. Keep `texture` (the `size` argument) at 2048 for anything over a metre, 1024 for the small
   stuff; budget about 3 to 5 px/cm up close (the export prints it).
2. **Build:** take the Unity lock (`mkdir unity\Build\.unity-lock`, `rmdir` after) and run `src\build-features.bat
   [Name,...]`. It builds `Resources\natureexpanded-features.unity3d` (all features, one bundle, separate from the plants
   and trees bundles), writes `unity\Build\feature-sizes.txt` (`Name cellsX cellsY cellsZ meshX meshY meshZ`), prints a
   collider check per feature in `unity\Build\unity-features.log` (every collider inside the mesh bounds, probes clear)
   and renders `unity\Build\features\<Name>.png` (the game shader, next to vanilla's boulder and a 1.8 m figure) and
   `<Name>_colliders.png` (model beside its colliders).
3. **Config:** in `Scripts\NatureExpanded\gen_nature.py`'s FEATURES section: add the name to `FEATURES` (display name,
   kind: `rock` or `bone`; add a kind to `FEATURE_KINDS` for other materials/drops/Collide), and placement to
   `FEATURE_PLACEMENT` (`main`: open ground; `mix`: into a vanilla sub-biome by its noise key; `fields`: own noise patches
   `(freq, (low, high), {name: prob})`). Run `python gen_nature.py <repo>\NatureExpanded <game>`; blocks.xml (block per
   feature, dims from the sizes file, `BigDecorationRadius`, harvest count from the mesh volume: 8 per m3 of half the
   bounds, 4 to 40), biomes.xml and Localization.csv are written. Blocks exist only for features the build measured.
4. **Check:** `refcheck`/`XmlPatch` as for the rest of the mod, and look at the two preview PNGs.

## Engine limits and cautions

- Footprint cells overwrite whatever terrain voxels are in them; only flat ground is allowed (`CanDecorateOnSlopes`
  false), so a feature never carves a hillside. Keep footprints modest (3 to 7 cells); a rotated 7x7 arch is 49 child
  blocks per cell layer.
- The AI path grid sees every footprint cell as blocked (Collide movement), so zombies path around an arch's opening
  even though it is open to the player. Only the footprint matters to them, not the voxel boxes.
- Colliders cost physics time: `export` merges voxels until there are at most ~140 boxes (`limit`).
- The bundle is large (each 2048 feature is about 14 MB of textures); it is git-ignored like the trees bundle (rebuild with
  `src\build-features.bat`).
- Unverified in game (nothing here has been played): collision feel and climbing (box steps of 10 to 16 cm),
  walking through an arch, the harvest yield, the flat-ground-only placement rate, the skirt depth on uneven ground.

## Status (2026-11-04, before the camps and finds below)

Built and checked offline (24 features, bundle `unity\Build\features-bundle\natureexpanded-features.unity3d`, 154 MB; copy it to
`Resources` with `src\build-features.bat`, and rebuild the DLL with `src\build.bat`: `BlockFeatureDEM.cs` and a small
`NatureShaderDEM.cs` edit are new):
MossyBoulder01-04, GlacialErratic01-02, GraniteOutcrop01, StoneCairnForest/Desert/Snow, Hoodoo01-03, DesertArch01, MesaLedge01,
SnowSpire01-02, SnowSlab01, WindColumn01-02, WasteSlab01, ElkSkull01, ElkRibcage01, AntlerShed01.
Checked: every collider lies inside its mesh bounds; the arch's four probe rays through the opening are clear; the generated
XML applies with XmlPatch (all xpaths match) and every ModelEntity block has a Model. Not checked in game: see the list above.
Known weak spots: the bones (skull, ribcage, shed) are crude, the snow slabs' icicles are tiny, the boulders read a little
smooth and pale next to vanilla's. In the Unity previews a face turned away from the sun can look black (the game shader's
ambient on shadowed sides is low in the preview stage); the Standard shader shows it fine, so it is a preview-lighting matter,
but look at it in game first.

## Timber features (wave 2, logs work)

Windfalls (`WindfallFresh01`, `WindfallOld01`, `WindfallBurnt01`, `WindfallPair01`), nurse logs (`NurseLog01-02`,
`NurseLogSnow01`), giant stumps (`GiantStump01`, `GiantStumpBurnt01`, `GiantStumpBleached01`), the hollow trunk cache
(`HollowTrunk01-02`, a loot container) and deadfall piles (`DeadfallPile01-02`). Scripts: `blender/features/windfall.py`,
`nurse_log.py`, `giant_stump.py`, `hollow_trunk.py`, `deadfall.py`, on the shared `logkit.py` (bark/moss/soil/end-grain
materials, the `Trunk` builder, saplings, fungus, previews, and an `export` that packs UV islands with a 1 px margin:
the default 0.004 margin wasted most of a 2048 atlas on features with thousands of needle cards).

- **Rectangular footprints.** The game rotates a multi-block's child offsets with the block (`Block.MultiBlockArray.Get`),
  so an odd-by-odd rectangle stays centered at any quarter turn. A feature whose colliders sidecar has a `rect` line
  (`fk.export(..., rect=True)`) gets `cellsX x cellsZ` from its own extents instead of the square of the larger; the sizes
  file and `MultiBlockDim` carry both. `BigDecorationRadius` is one number: the long side's half plus one.
- **Placement acceptance.** `decorateSingleBlockTryPlaceDeco` adds the radius to the roll's x and z and drops it when either
  is >= 16, so only `(16 - r)/16` of each axis is accepted (r 9: 19% of the chunk's cells), then needs a flat master cell.
- **Grain.** Bark and soil noise is stretched along the trunk's axis in object space: logs lie along x (`logkit.AXIS = "x"`),
  stumps and snags stand along z (set `lk.AXIS = "z"` before making materials).
- **Timber kind.** Material `MtreeWoodSmall` (300 HP), Harvest `resourceWood` with tags `oreWoodHarvest,lumberjackHarvest`
  (an axe), counts in gen_nature's `FEATURE_COUNTS` (about 6 per cubic metre of trunk; vanilla's 1.5 m stump pays 10 to 15).
- **Cache kind.** Class `FeatureCacheDEM, NatureExpanded` (`src/BlockFeatureCacheDEM.cs`, a `BlockCompositeTileEntity` with the
  colliders tagged like BlockFeatureDEM) plus vanilla's `CompositeFeatures/TEFeatureStorage LootList`, here
  `dementiveHollowCache` (Config/loot.xml, written by gen_nature.py).

## Camps and single finds (2026-11-06)

Four abandoned camps (`CampTent`, `CampLeanTo`, `CampChairs`: 5x5 multi-blocks with solid fire rings, stumps, coolers and
log seats under walk-through cloth, chairs and cans; `CampFishing`) and twelve single finds (`TrailMarker`, `Antlers`,
`LoneBoot`, `OldTire`, `Wheelbarrow` 3x1, `LawnChair`, `BrokenCooler`, `ShoppingCart` 3x3, `RustyBucketCans`, `FirewoodStack`
3x3, `AbandonedPack`, `RustedBicycle` 3x3). Models: `blender/features/camp_*.py`, `antlers.py` and the others (specs in
`blender/features/SPEC_camps.md`, `SPEC_singlesA.md`, `SPEC_singlesB.md`), built into the same bundle by
`src\build-features.bat` (the bundle is 384 MB now, git-ignored; the build always packs every feature, `-features`
only limits the previews). Pure set dressing: no loot and nothing hidden, only the break-for-materials harvest.

- **Kinds** (gen_nature.py `FEATURE_KINDS`): `scrap` (vanilla's scrapMetalPile recipe: material MmetalNoGlue, any tool and
  Junk Miner pay `resourceScrapIron`), `cloth` (`resourceCloth`), `plastic` (`resourceScrapPolymers`), `leather`
  (`resourceLeather`), plus the existing `timber` (axe, `resourceWood`) and `bone`. A feature's `MaxDamage` is set per prop
  (`FEATURE_HP`), counts in `FEATURE_COUNTS` (camps 6 to 10, props 2 to 8, the firewood stack 24) and a second drop in
  `FEATURE_EXTRA_DROPS` (the wheelbarrow's handles, a camp's firewood). Walk-through ones (`FEATURE_WALK_THROUGH`: antlers,
  boot, cooler, bucket and cans, backpack) are `Collide melee`: only a tool hit finds them.
- **Rarity** (`FEATURE_TARGETS`, per large 8k map; each probability is worked out from the target, the biome's rough
  cell count `MAP_CELLS`, the share of cells a feature can use `OPEN_FLAT` (open ground that is flat) and the chunk-edge loss
  for its footprint): camps 15 to 18 each, singles 20 to 45 (bicycle, cart and wheelbarrow 20), over the open ground of
  the pine forest, burnt forest, desert, snow and wasteland as the specs name. They are also in the drift, patch and field
  sub-biomes' ground (`extra_ground`), which otherwise take most of a biome's ground, so counts hold. The hollow trunk is
  untouched. The numbers are guesses good to a factor of two: retune a count in `FEATURE_TARGETS`.
- **CampFishing** is not in a biome table: `ShoreDEM` (the DLL) tries it on pine forest cells whose whole 5x5 is flat,
  dry and empty and whose nearest water in the chunk is 3 to 8 blocks away (`CampChance`, 1.2e-4, about 15 a large map by
  estimate).
- Zombies path round a camp's whole 5x5 (the footprint is solid to the AI grid).
