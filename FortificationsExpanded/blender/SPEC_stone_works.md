# Stone Works: model spec for the integrator

Script: `FortificationsExpanded\blender\stone_works.py` (numpy atlas painter plus mesh builder; no Cycles bake; runs in
about 15 s). Invoked like palisade.py, with the icon optional:

    blender -b --factory-startup --python blender\stone_works.py -- <unity\Assets\FortificationsExpanded\StoneWorks> <previews> [<icon png>]

(`--threads 2` and low priority are fine. `STONE_EEVEE=1` renders the previews with Eevee, `STONE_PV=0.7` scales
them, `STONE_SHOTS=a,b` renders only matching preview files; a mode word `export`/`tex`/`reuse` can be added last.)

Textures: `src\fetch-textures-stone.ps1` (new; Poly Haven CC0 sets rock_boulder_dry, dry_riverbed_rock, quarry_wall_02,
rock_face_03, dark_rock_02, rough_plaster_03, mossy_rock, lichen_rock into `blender\textures`, gitignored). Fold its
list into `fetch-textures.ps1` if you want one script.

## Output (already written, from the last run)

Folder `unity\Assets\FortificationsExpanded\StoneWorks\` (family name for FortBuilder: `StoneWorks`):

- `StoneWorks_Albedo.png`, `StoneWorks_Normal.png`, `StoneWorks_RMOM.png` (2048, one shared material `StoneWorks`,
  RMOM = roughness / metallic 0 / occlusion / alpha 1, normal map OpenGL like the other families)
- `ArrowSlitWall.fbx`, `ArrowSlitCorner.fbx`, `Battlement.fbx`, `BattlementCorner.fbx`

Each FBX: three meshes `DMG0`, `DMG1`, `DMG2` at the same origin plus an empty `FX`. Origin = centre of the bottom
cell, bottom at z = -0.5 (Blender), wall line along X, front (outside) = -Y, like PalisadeSection / PalisadeCorner.
Also written: `UIAtlases\ItemIconAtlas\DementiveFortStoneWorks.png` (160x160, ArrowSlitWall) and previews
`unity\Build\previews\stone_*.png` (Eevee renders: stages front/back for every piece, close-ups, a corner+row with
battlements stacked on the wall, a low wall of battlements, the loophole from inside).

## Pieces

| Name | Display name (suggestion) | Cell / MultiBlockDim | Height | DMG0 / DMG1 / DMG2 tris | FX point (Blender) |
|---|---|---|---|---|---|
| ArrowSlitWall | Stone Wall with Arrow Slit | 1 x 3 x 1 | 3.0 m | 6342 / 6824 / 4450 | (0, -0.34, 1.0) |
| ArrowSlitCorner | Stone Wall Corner | 1 x 3 x 1 | 3.0 m | 7386 / 7798 / 3770 | (0.1, -0.34, 1.0) |
| Battlement | Battlement | 1 x 1 x 1 | 1.0 m | 2266 / 2374 / 1300 | (0, -0.33, 0.0) |
| BattlementCorner | Battlement Corner | 1 x 1 x 1 | 1.0 m | 2692 / 2922 / 1302 | (0.1, -0.33, 0.0) |

Footprints are the default 1 x 1 in FortBuilder (no entry needed). Wall thickness 0.6 m plus up to 3 cm of stone relief
each side (DMG0 bounds y -0.36..0.36, x +-0.51); the ends are flush at x = +-0.5, so pieces butt without a gap.
Courses are fixed heights (3 m wall: 12 courses plus a 0.24 m cap course; battlement: 4 courses plus a 0.12 m cap),
the same in every piece, so neighbours and the battlement-on-wall line up. The cap course of the 3 m wall is flush
enough that a Battlement placed on top (block above) sits on it.

- **ArrowSlitWall:** straight section. Loophole at standing eye height (z 1.29..1.94 m above the bottom, centre of
  the piece): 6 cm wide on the outside (-Y), splayed to 46 cm on the inside (+Y), dressed stone reveals, sill and
  lintel. The only open part is the slit.
- **ArrowSlitCorner:** L-shape, arms toward +X and +Y (outside corner at -X,-Y), quoins alternating long and short up
  the corner. No loophole. Arms reach the cell edges, so straight pieces continue from them like the palisade corner.
- **Battlement:** parapet, 1 m: three base courses (the top one a ledge slab) with a centred merlon 0.6 m wide and
  a capstone; 0.2 m of embrasure ledge at each end (two neighbours make a 0.4 m embrasure). Meant for the block on
  top of an ArrowSlit wall or as a low wall (1 m, zombies can climb it).
- **BattlementCorner:** L-shape like the corner above; a square merlon at the corner and ledge arms.

Damage stages (all four): DMG0 intact (hand-laid courses, mortar, a couple of missing stones and dark stones, moss
and soil low down, chinks); DMG1 cracked stones (split in two with a dark gap), chipped corners, ~8 more missing
stones (deep pockets), a few stones pushed out, a handful of fallen stones at the base; DMG2 heavily broken: top
collapsed to a stepped ragged profile (3 m wall left 0.8..1.9 m, battlement a 0.1..0.5 m stump), no caps, most
facing stones gone from the top, rubble heaped on both sides (up to the cell edge) and on the
broken top. Missing/pushed stones and rubble differ between stages by design; the layout of the remaining stones
is the same in all three.

## Notes for the generator

- **Collision / see-through:** FortBuilder puts one BoxCollider around DMG0 clipped to the cell, so the loophole is
  visual only (bullets and arrows hit the box). For a real firing slit use a mesh collider on DMG0 for ArrowSlitWall,
  or give the block a custom Collide; I did not touch FortBuilder. All pieces are solid (`Path solid`) and take
  support (`support=True`, build on top). DMG1/DMG2 rubble stays within about 0.07 m of the cell edge (bounds
  +-0.57 m); the collider is clipped to the cell anyway.
- **Zombies:** the 3 m wall is unclimbable; DMG2 is lower than 1.5 m in most of the section so it is climbable
  there, like the palisade stumps. The 1 m battlement is climbable.
- **Explosions:** the family hallmark is blast toughness, so give the material a high `explosionresistance`
  (more than concrete's 0.2; the pieces are modelled as thick massive masonry). Everything else (health, repair,
  upgrade) is yours.
- **Debris colour** for FortBuilder.Families: about (0.46, 0.43, 0.38) grey stone dust; the FX empty is on the front
  face (-Y) of the intact piece, mid-height.
- `MeshDamage` names: `DMG0,<hp>,DMG1,<hp*0.65>,DMG2,<hp*0.3>` as the generator already writes; all four models have
  all three stages and the FX.
- build-models.bat entry: `stone_works:StoneWorks:DementiveFortStoneWorks`. FortBuilder previews "finished" list
  would need the four names added if you want Unity previews.
- Destroy/harvest: the wall is stone; suggest stone/cobble-style harvest (`resourceRockSmall`, `resourceCobblestones`)
  and a stone burst on break. Lime mortar and moss are texture only.
- Placement proposal: forts, hunting-camp walls and ruins are natural homes for the stone look; biome-neutral, maybe
  slightly more common in forest and mountain (snow) than desert; rare.

## Weak spots (honest list)

- Triangle counts are high for a block model (6-7.8k for a 3 m piece, 2.3-2.9k for a battlement) because the stone
  relief is real geometry on both faces; there are no LODs (none of the other families have them either).
- The texture atlas is photo-based, graded dark and desaturated, but I could not compare it beside vanilla assets in
  the game's shader (Unity not run). Albedo means are ~0.25-0.33 for stones, mortar ~0.4. Check it next to vanilla
  cobblestone and darken `grade(...)` means in `stone_swatch` if it reads too bright.
- Previews were rendered with Eevee (the machine was busy), not Cycles, so there is no global illumination in them.
- About 530 vertices (mostly rounded stone edges and quoin tops) clamp at the swatch borders, so a few millimetres
  of edge pixels smear; not visible in the previews.
- The straight wall ends are plain rough stone faces (cut ends), not coursed masonry; they show only at the end of a
  run. Seams between pieces are random stone joints, so a vertical joint every metre is faintly visible.
- DMG2's stepped top has a few thin riser faces that show as odd dark slabs at some angles.
- Two iterations per piece only: no sandbag-style per-stone moss colour variation beyond the swatches, and no
  per-piece mirrored variants (the game rotates blocks).
