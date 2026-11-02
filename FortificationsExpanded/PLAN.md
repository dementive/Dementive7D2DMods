# Fortifications Expanded: plan

**Status (2026-11-01):** approved with the defaults for the open questions below (single 3 by 3 container pool, Hesco
cap 100, unlocks by material only). At the user's request all six families were built at once instead of one per
playtest: 66 blocks from `Scripts/FortificationsExpanded/gen_fortifications.py`, 54 models by five parallel Blender
scripts (`blender/*.py`), bundled by `FortBuilder`. Installed; not tested in game. An independent review's fixes are
in. What changed from the plan while building:

- The "burst effect" is a puff of the family's debris that the game plays from the model's FX point each time a damage
  stage breaks; the final break uses the game's own destroy burst for the material.
- Hesco has no separate corner: its cells are square, so a barrier already turns a corner.
- Chain-link's three stages (taut, sagging, torn) are separate blocks a damaged fence breaks down through; a hammer
  and 3 scrap iron pull it back up a stage. The light-to-heavy upgrade is on the taut stage.
- Corners break down to their own stumps, which rebuild into a corner.
- Filled walls (full sandbags, palisade sections and corners, filled Hesco, containers) support blocks built on top;
  empty stages, stumps, mounds, chain-link and tank traps don't.
- Numbers the plan didn't give: palisade gate 2500, chain-link gate 1500, container gate 15000, container corner 8000,
  tank-trap line 5000 (bent 1500), bent hedgehog 2000, stumps 300, mounds a third of the first fill (500, double 1000).
- Gates are vanilla doors (open, close, lock) with their own animated models and vanilla gate sounds; the chain-link
  gate rolls aside, the others swing out to the front.
- Sandbag and Hesco textures were graded after the bake toward the vanilla sandbags' values (brighter albedo, lighter
  baked occlusion), since in the game's shader the first bakes went nearly black in shade.

New wall materials for horde bases, each with real 3D models built the way the traps were, and each with one job a
vanilla block doesn't do. They sit beside the vanilla upgrade chain (wood, cobblestone, concrete, steel) rather than
replacing it: you pick a material for what that stretch of wall has to survive.

## Rules every piece follows

- **Look:** scrap-built and field-made, textured with photo-scanned materials, rendered with the game's own model
  shader and worn all over, the same bar as the Tesla Coil. Checked in renders beside vanilla blocks before going in.
- **Visible damage:** every model has three damage stages that swap in as it loses health (the engine's `MeshDamage`):
  bags split and sag, mesh tears and dirt spills, logs splinter, panels buckle. Breaking a piece plays its own burst
  effect (sand, dirt, splinters, a metal crash). Hit sounds and puffs come from the material, so sandbags sound like
  sand.
- **One job each:** no material beats steel at raw health. Each earns its place through blast resistance, cost,
  shoot-through, height or footprint.
- **Built like vanilla:** one item per family; the radial picks the piece (wall, corner, low wall, gate), like the
  vanilla sandbag helper. Repaired and upgraded with the vanilla hammer and nail gun. Unlocked by materials, the same
  way vanilla gates steel behind the forge and crucible.
- **Co-op:** walls are world blocks the server owns, so health, damage stages, upgrades and repairs sync like any
  block. Anyone can place, repair or upgrade, and land claims work as normal.
- **Standalone:** needs no other mod. Custom models mean server and clients both install it; there is no
  server-only version.

## Engine facts the design rests on

Checked in the game code (2026-11-01):

- Zombies climb anything up to 1.5 m and can't climb 2 m or more, so 2 m pieces make an unclimbable wall and 1 m pieces
  are cover you can shoot over (and they can climb).
- Zombies decide between breaking a wall and walking around by cost: every 50 health is worth about 1 m of detour.
- Explosion resistance is per material, 0 to 1 (concrete 0.2, steel 0.75). Earth materials also take almost nothing
  from cop vomit, boulders, pipe bombs and grenades, and a tenth from demolishers; rockets and dynamite hit them fully.
- A block can stop zombies but let bullets and arrows through; it can also let them see you or not. This is set per
  block, not per part of the model.
- A material can cap the damage from any single hit (not explosions).
- A multi-block piece has one health pool, so when it breaks the whole piece goes. Every cell inside a blast adds to
  that pool's damage.
- Custom-model blocks can't be painted (colour variants use a tint instead) and don't appear in the shape menu.
- There's no block fire in V3.4: nothing sets walls alight, and molotovs barely scratch blocks.

## Families

Health is the whole piece's pool. For scale, vanilla per 1 m cell: wood 500, cobblestone 1500, concrete 5000 (blast
resistance 0.2), steel 10000 (0.75). Vanilla sandbags are 200 per cell.

| Family | When | Job | Pieces | Health | Special | Cost |
|---|---|---|---|---|---|---|
| Log Palisade | start | Tall wall on day one | Section (1 wide, 3 m tall), corner post, double gate (3 wide) | 1500; iron-banded upgrade 3000 | 3 m sharpened logs zombies can't climb. Breaks down to 1 m splintered stumps they can climb over | 25 wood, 4 yucca fibers; banding +4 forged iron |
| Sandbag Wall | start | Blast wall | Wall (2 m), low wall (1 m), corner, end | Wall 2000, low wall 1000 | Earth material with blast resistance 0.5: shrugs off cops, boulders and grenades, and survives about 4 point-blank demolisher blasts (concrete barely survives one). Rockets and dynamite still wreck it | Place empty bags (10 cloth), fill twice with the hammer (+10 crushed sand each) |
| Chain-Link | workbench | See-through screen, gates | Panel (2 m), tall panel (3 m), rolling gate (3 wide), corner | Panel 900 across three stages (taut, sagging, torn) | Bullets and arrows pass, zombies see you. The cheapest shoot-through wall before the forge, and the only craftable gate of its kind | 6 scrap iron, 1 duct tape; heavy upgrade +2 forged iron (1800) |
| Hesco Barrier | forge | Cheap bulk wall | Barrier (1 wide, 2 m), double-wide, corner | Empty 300, then 1500, 3000, full 5000 | Filled with clay you dig anyway; no cement mixer needed. Earth: ignores small explosives. Each single hit is capped at 100: ferals (24 a hit) are unaffected, charged zombies (150) lose a third and infernal ones (250) more than half. A breach spills into a 1 m mound zombies can climb | Cage: 4 forged iron, 6 cloth. Fill three times with the hammer, +10 clay each |
| Tank Traps | forge | Funnels | Hedgehog (2 by 2 footprint, 1.8 m), hedgehog line (3 wide) | 6000; bent stage below it | Welded steel beams: zombies can't climb them and walk a long way around rather than break them, while bullets, arrows and sight pass. Lay out a maze across open ground fast | 12 forged iron |
| Container Wall | crucible | Late-game wall in one placement | Wall (3 wide, 3 tall), container gate with swing doors, corner | Wall 25000, gate 15000 | Blast resistance 0.5, placed whole with no upgrade hits. Red, blue, green and rust tints. The catch: one pool, so a breach opens a 3 by 3 hole at once, and a blast counts once per cell it covers | 30 forged steel, 10 forged iron |

Numbers are first passes, to tune in play like the traps were.

## Effects

New: sand burst, dirt spill, wood splinters and a metal crash when a piece breaks; sand trickling from split bags
and dirt falling from torn Hesco mesh in the last damage stage. The game's own dust and spark effects are reused where
they fit.

## Cut from the pitch

- **Palisade burns:** cut. Nothing in V3.4 sets blocks on fire (no zombie does, and molotovs barely touch blocks), so
  burning walls would only ever punish the player who threw the molotov. It would also need a whole fire system.

## Build order

1. Pipeline test: Sandbag Wall (one model with three damage stages, the fill upgrades, the burst effect). Played
   before going further, like the Tesla Coil.
2. Log Palisade and its gate
3. Hesco Barrier (fill stages, hit cap, breach mound)
4. Chain-Link and the rolling gate
5. Tank Traps
6. Container Wall and the container gate

## Open questions

1. Container walls: keep the single 3 by 3 health pool as the trade-off, or split each wall into three 1-wide columns
   (smaller breaches, more placing)?
2. Hesco hit cap of 100: right strength? It's the one wall that makes charged and infernal zombies struggle.
3. Should any family need a schematic or perk to unlock, or is gating by material (forge, crucible) enough?
