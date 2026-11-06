# Razor Wire, Pallet Wall, Hedge Row: model spec (for the integrator)

Scripts (all in `FortificationsExpanded\blender\`, built with the same command line as the other families; they also
need the shared helper `wallkit.py` next to them, and `trapkit.py`):

| Script | Output folder (`unity\Assets\FortificationsExpanded\`) | Icon |
|---|---|---|
| `razor_wire.py` | `RazorWire\` | `UIAtlases\ItemIconAtlas\DementiveFortRazorWire.png` |
| `pallet_wall.py` | `PalletWall\` | `DementiveFortPalletWall.png` |
| `hedge_row.py` | `HedgeRow\` | `DementiveFortHedgeRow.png` |

`blender -b --factory-startup --python <script> -- <asset folder> <preview folder> <icon file> [mode]`
(mode `export` = no renders; hedge also has `lite`). Previews are in `unity\Build\previews\` (`razor_*`, `pallet_*`,
`hedge_*`); the last full set were rendered with EEVEE (env `WK_ENGINE=EEVEE`, `WK_RES` scales them) because Cycles
was too slow on the shared machine. Nothing here has been through Unity.

All models follow the existing layout: bottom at z = -0.5, wall line y = 0, front -Y, one FBX per piece, one baked
material per family named like the folder; every staged piece has meshes `DMG0`, `DMG1`, `DMG2` (same origin) plus an
empty `FX` mid-front at mid-height. Textures `<Family>_Albedo/_Normal/_RMOM.png` sit in the family folder.

## Changes the builder needs (FortBuilder.cs, not touched by me)

- `Families`: add `("RazorWire", debris colour ~ (0.42,0.38,0.34))`, `("PalletWall", ~ (0.45,0.38,0.28))`,
  `("HedgeRow", ~ (0.28,0.34,0.14))`.
- Preview list (`finished`): add `RazorWireSection`, `RazorWireCorner`, `PalletWallSection`, `PalletWallCorner`
  (`HedgeRowFull*` already match `EndsWith("Full")` only for `HedgeRowFull`; `FullB`/`FullC` end differently, add them
  if wanted).
- `Footprints`: nothing needed (all 1 by 1).
- `HedgeRowMesh` is a cut-out material by name (alpha cut 0.3, 1024 atlas, repeat wrap): the builder already handles
  names ending in `Mesh`. The FBX has two material slots, `HedgeRow` (opaque) and `HedgeRowMesh` (leaves).
- The hedge's leaf vertices carry custom (outward-pointing) normals: keep `importNormals = Import` (already set).

## Razor Wire (family folder `RazorWire`, material `RazorWire`, atlas 2048)

| Model | Display name | Block dim | Stages | Tris DMG0 / 1 / 2 | Extent (m) |
|---|---|---|---|---|---|
| `RazorWireSection` | Razor Wire Coil | 1,1,1 | DMG0 taut, DMG1 sagging, DMG2 tangled heap | 3104 / 2360 / 4364 | x -0.52..0.55, y -0.49..0.50 (DMG2 lying picket to 0.64), height 0.99 (heap 0.41) |
| `RazorWireCorner` | Razor Wire Corner | 1,1,1 | same | 3384 / 2240 / 3372 | picket at the origin, coils to +X and +Y (end pickets at 0.46), height 0.99 |

- Piece: real helix of 5.6 mm steel wire, radius 0.46, pitch 1/7 m (7 turns per section, same phase at both ends so
  neighbours join), barb pairs every 6.5 cm, two studded T-post pickets 0.99 m tall at x = +-0.46, wire ties.
  Grey steel with rust bloom; pickets worn green paint over rust.
- Stages: DMG1 flattened, slumped loops with fewer turns, one wire snapped and curled back, one picket leaning; DMG2
  wire in knots on the ground (under 0.4 m high, easy to step over), one picket at 35 degrees, one lying.
- Handling: see-through (thin wire only, about 97 % open from the side; do not block sight or bullets: use
  `movement,melee,rocket` like chain-link). The auto box collider will be the full footprint (1 by 1 by 0.99); the
  hurt-on-contact logic is the generator's. Zombies can climb over (under 1.5 m). Good harvest: scrap iron.
- Placement: any biome, common near military/prison/industrial POIs and farms; early game, cheap.

## Pallet Wall (family folder `PalletWall`, material `PalletWall`, atlas 2048)

| Model | Display name | Block dim | Stages | Tris DMG0 / 1 / 2 | Extent (m) |
|---|---|---|---|---|---|
| `PalletWallSection` | Pallet Wall | 1,2,1 | intact, boards stripped, collapsed pile | 1842 / 1270 / 616 | x +-0.5, y -0.09..0.17 (posts behind, +Y), height 2.08 |
| `PalletWallCorner` | Pallet Wall Corner | 1,2,1 | same | 2440 / 1550 / 938 | 0.15 m post at the origin, arms to +X and +Y (Y arm = X arm mirrored across the diagonal), height 2.08 |

- Piece: a 1.2 m pallet with a 0.8 m pallet on top (mismatched widths, board counts, tones; chipped, short, split and
  raised boards, nails at every crossing), two 4x4 posts behind at x = +-0.43 with screws and wire lashings. Stencils
  made from random block glyphs (nothing readable). Greyed, dark wood.
- Stages: DMG1 about 40 % of the front-deck boards and 30 % of the back-deck boards gone, hanging boards, the top
  pallet slumped, a post leaning; DMG2 a heap of boards, stringers and snapped posts, 0.39 m high (zombies climb it).
- Handling: solid wall. Straight-through gaps: about 12 % of the area intact, 31 % in DMG1 (measured with rays front
  to back; the decks are staggered). I would treat it as opaque and bullet-blocking. Material wood.
- Harvest: wood, a few nails. Placement: industrial areas, warehouses, junkyards, rural lots; common, early game.

## Hedge Row (family folder `HedgeRow`, materials `HedgeRow` + `HedgeRowMesh`, atlases 1024)

| Model | Display name | Block dim | Stages | Tris | Extent (m) |
|---|---|---|---|---|---|
| `HedgeRowSaplingA`, `HedgeRowSaplingB` | Hedge Sapling | 1,1,1 | one mesh (DMG0), no FX | 472, 529 | 0.45 wide, 0.92 high |
| `HedgeRowYoungA`, `HedgeRowYoungB` | Young Hedge | 1,1,1 | one mesh (DMG0) | 1452, 1532 | 0.78 wide, 0.57 high |
| `HedgeRowFull`, `HedgeRowFullB`, `HedgeRowFullC` | Hedge | 1,2,1 | DMG0 intact, DMG1 ripped, DMG2 stripped | A 5538 / 2942 / 1626, B 5522 / 3398 / 1421, C 5640 / 2940 / 1818 | foliage to x about -0.6..0.7 (overlaps neighbours), y +-0.55, DMG0 height 1.5 (a few stray shoots to 1.6), DMG1 same, DMG2 0.8 |

- Growth: Sapling (5-7 thin canes, a few small leaves) -> Young (knee-high leafy bush) -> Full (dense, neatly
  overgrown wild shape). A, B, C are three random shapes of the same stage; use them as variants (separate blocks with
  the same behaviour) so a row doesn't repeat. Sapling and Young also come in A/B.
- Foliage: layered leaf cards (sprites painted leaf by leaf, folded, double sided) on four shells, lighter outside and
  darker inside, mixed leaf ages and a few dead twigs, over tapered branch tubes and a litter patch at the foot.
- Light through the middle of the intact Full hedge (straight rays along Y, leaf alpha cut at 0.3): 0.6-1.7 %. So it
  blocks sight; DMG1 lets 15-45 % through, DMG2 83-98 %.
- Handling: Full is a solid barrier with a wood/plant material, opaque to sight, not bullet-proof if you want
  (leaves). Sapling and Young are not barriers: make them walk-through (or a tiny collision) and have them grow into
  the next stage on a timer; their auto box colliders are small (canes about 0.45 wide, the bush 0.78 by 0.57).
  Harvest: plant fibre / wood; the DMG2 stumps leave sticks. Placement: temperate forest and plains, residential lots,
  roadside; Saplings and Young anywhere in grass.

## Weak spots

- Textures are numpy-painted (photo crops graded for the wood and paint, procedural wire and leaves) rather than baked
  from 3D, so occlusion is flat (leaf sprites carry a hand-made darker base); edge wear on the boards comes only from
  the photo. Not checked in the game's shader; leaf greens may need a 10 % brighter or darker tweak in play.
- Previews were EEVEE in a blue-sky stage, so greens read slightly cool.
- Hedge Full is 5.5 k triangles (half of it leaf cards), the heaviest of these; the inner shells use cheaper cards.
  If it is too much, lower the card counts in `FULL` in `hedge_row.py`.
- Razor-wire DMG2 section: the lying picket pokes to y = 0.64 (13 cm past the block). Hedge foliage overlaps the
  neighbouring blocks by up to 0.2 m at the ends on purpose (the round bushes join).
- Corner pieces of the pallet wall and razor wire were only looked at in the previews, not against real neighbours.
