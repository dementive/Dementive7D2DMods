# Fortifications Expanded

New wall materials for horde bases, each with its own models and one job a vanilla block doesn't do. Pieces show
three damage stages as they lose health and burst when a stage breaks; several break down into something weaker
(stumps, a spilled mound, a sagging fence) that you can hammer back up. The design is in PLAN.md.

Has a DLL and new models, so it has to be installed on the server and on every client, with EAC off.

Each family is one item: pick the piece from the radial menu. Gates are crafted separately and work like vanilla
doors (open, close, lock).

## Families

| Family | Craft | Job | Pieces | Health |
|---|---|---|---|---|
| Log Palisade | by hand: 25 wood, 4 yucca fibers | Tall wall on day one | Section, corner (1 wide, 3 m); gate (3 wide) | 1500; iron-banded 3000 (+4 forged iron) |
| Sandbag Wall | by hand: 10 cloth | Blast wall | Wall, corner, end (2 m), low wall (1 m) | 2000 full (low wall 1000) |
| Chain-Link | workbench: 6 scrap iron, 1 duct tape | See-through screen | Panel (2 m), tall panel (3 m), corner; rolling gate (3 wide) | 400 / 300 / 200 as it sags and tears (tall 1.5x); heavy 800 / 600 / 400 (+2 forged iron) |
| Hesco Barrier | workbench: 4 forged iron, 6 cloth | Cheap bulk wall | Barrier (1 wide, 2 m), double (2 wide) | 300 empty, 1500 / 3000 / 5000 as it's filled (double 2x) |
| Tank Traps | workbench: 12 forged iron | Funnels | Hedgehog (2 by 2), line (3 wide), 1.8 m | 6000 / 5000, then a bent stage |
| Container Wall | workbench: 30 forged steel, 10 forged iron | Late wall in one placement | Wall (3 by 3), corner (1 by 3), red/blue/green/rust; gate (3 by 3) | 25000 (corner 8000) |

- **Log Palisade:** zombies can't climb 3 m. A broken section leaves 1 m stumps they can climb over; hammer the stumps
  back into a section with 15 wood.
- **Sandbag Wall:** place the empty bags, then fill them twice with a hammer or nail gun and crushed sand (10 a fill,
  5 for the low wall). Earth with blast resistance 0.5: cops, boulders, pipe bombs and grenades do nothing, and a full
  wall survives about four point-blank demolisher blasts (concrete barely survives one). Rockets and dynamite still
  wreck it.
- **Chain-Link:** stops zombies, but bullets and arrows pass through and zombies can see you through it. It sags, then
  tears; hammer it back up a stage with 3 scrap iron.
- **Hesco Barrier:** fill it three times with clay (10 a fill, 20 for the double). Earth: ignores small explosives.
  Every single hit on it is capped at 100, so charged and infernal zombies struggle with it. A breach spills into a
  1 m mound zombies can climb; refill it with clay.
- **Tank Traps:** zombies can't climb them and would rather walk a long way around than break them; bullets, arrows
  and sight pass between the beams. A wrecked trap bends but stays a barrier; re-weld it with 6 forged iron.
- **Container Wall:** placed whole, with no upgrade hits, and blast resistance 0.5. One pool of health: when it
  breaks, the whole 3 by 3 goes at once, and a blast counts once for every cell it covers.

## Building the models

`src\build-models.bat` runs `blender\<family>.py` (Blender, on PATH) and then Unity 2022.3.62f2
(`FortBuilder.BuildAndPreview`) to make `Resources\fortificationsexpanded.unity3d`; `src\build.bat` builds the DLL.
The Config is written by `Scripts\FortificationsExpanded\gen_fortifications.py`.
