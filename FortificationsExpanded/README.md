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
| Picket Fence | by hand: 10 wood, 2 nails | Cheap low cover | Section, corner (1 wide, 1.1 m); gate (2 wide) | 250 (gate 300) |
| Post-and-Rail Fence | by hand: 8 wood, 2 yucca fibers | See-through boundary | Section, corner (1.2 m); gate (2 wide) | 200 (gate 250) |
| Razor-Wire Coil | workbench: 8 scrap iron, 2 yucca fibers | Hurts what touches it | Section, corner (1 m) | 300 |
| Pallet Wall | by hand: 6 wood | Tall wall for almost nothing | Section, corner (1 wide, 2 m) | 400 |
| Hedge Row | by hand: 4 yucca fibers for 2 cuttings | Grown wall, no upkeep | Cutting, young hedge, full hedge (3 shapes, 1.5 m) | 500 |
| Stone Works | workbench: 30 cobblestones | Blast resistance | Arrow-slit wall, corner (1 wide, 3 m); battlement, battlement corner (1 m) | 3000 / 1000 |

- **Log Palisade:** zombies can't climb 3 m. A broken section leaves 1 m stumps they can climb over; hammer the stumps
  back into a section with 15 wood, which restores the touching stumps along with it. Banding stays one section at a
  time.
- **Sandbag Wall:** place the empty bags, then fill them twice with a hammer or nail gun and crushed sand (10 a fill,
  5 for the low wall); each fill also fills the touching bags at the same stage. Any repair tool that takes clay takes
  crushed sand too. Earth with blast resistance 0.5: cops, boulders, pipe bombs and grenades do nothing, and a full
  wall survives about four point-blank demolisher blasts (concrete barely survives one). Rockets and dynamite still
  wreck it.
- **Chain-Link:** stops zombies, but bullets and arrows pass through and zombies can see you through it. It sags, then
  tears; hammer it back up a stage with 3 scrap iron, which pulls the touching fence at that stage up with it. The
  heavy upgrade stays one panel at a time.
- **Hesco Barrier:** fill it three times with clay (10 a fill, 20 for the double); each fill also fills the touching
  barriers at the same fill. Earth: ignores small explosives. Every single hit on it is capped at 100, so charged and
  infernal zombies struggle with it. A breach spills into a 1 m mound zombies can climb; refill it with clay, which
  refills the touching mounds too.
- **Tank Traps:** zombies can't climb them and would rather walk a long way around than break them; bullets, arrows
  and sight pass between the beams. A wrecked trap bends but stays a barrier; re-weld it with 6 forged iron, which
  re-welds the touching bent traps too.
- **Container Wall:** placed whole, with no upgrade hits, and blast resistance 0.5. One pool of health: when it
  breaks, the whole 3 by 3 goes at once, and a blast counts once for every cell it covers. Repairs run along touching
  container walls, corners and gates like every family's.
- **Picket Fence, Post-and-Rail Fence:** 1.1 and 1.2 m, so zombies climb them: boundaries and funnels, not walls. The
  picket fence blocks sight and bullets; the rails and the rail gate are open (bullets, arrows and sight pass).
- **Razor-Wire Coil:** zombies can't walk through it. Everything living that touches it, zombies and you included, takes
  8 damage every second and a half (vanilla barbed wire's mechanism, damage type barbed wire) and is slowed, and the coil
  wears down slightly with each cut. Bullets, arrows and sight pass.
- **Pallet Wall:** 2 m, so zombies can't climb it; solid and takes support blocks on top. Weak and cheap.
- **Hedge Row:** craft cuttings and plant them in soil (fertile ground, like the vanilla crops and trees). A cutting
  grows into a young hedge and then a full hedge, 63 minutes per stage (about one game day each at the default day
  length; the vanilla crop and tree rate), the full hedge one of three shapes at random. Cuttings and young hedges are
  walk-through and one hit breaks them (the cutting drops back); a full hedge is solid, blocks sight and bullets, and
  takes an axe. It grows only while the cell above is clear and the ground is fertile.
- **Stone Works:** blast resistance 0.45 (reinforced concrete 0.2, steel 0.5, sandbags 0.5 with the earth bonus on
  top). The arrow slit is visual only: bullets and arrows hit the wall. The 3 m wall and the battlement take support
  blocks on top.

## Whole runs

One fill, restore or repair hit on a piece also does the same to the rest of its run: every piece of the same family
joined to it through touching pieces of that family (gates included, any colour of container). A fill or restore
reaches the undamaged pieces at the same stage (repair a damaged one first); a repair reaches every damaged piece, as
long as the piece you hit still needs repairing. Up to 32 more pieces, nearest first. Each one takes its own
materials, exactly as a hit on it would, and the run stops at the first piece you can't pay for. It's still one swing
for the tool's wear. Vanilla blocks are never touched.

In co-op it runs where a vanilla repair does, on the client of the player holding the tool, taking that player's
materials, and the block changes sync through the server like any other repair.

## Building the models

`src\build-models.bat` runs `blender\<family>.py` (Blender, on PATH) and then Unity 2022.3.62f2
(`FortBuilder.BuildAndPreview`) to make `Resources\fortificationsexpanded.unity3d`; `src\build.bat` builds the DLL.
The Config is written by `Scripts\FortificationsExpanded\gen_fortifications.py`.
