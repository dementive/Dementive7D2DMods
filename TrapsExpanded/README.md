# Traps Expanded

Fourteen new traps with their own models, built to work together like a tower defense game. Blood Moon is the wave
and the week before it is the build phase. Traps put statuses on zombies that other traps cash in, level up from
their kills, and a report after each Blood Moon shows how they did. The design is in PLAN.md.

Has a DLL and new models, so it has to be installed on the server and on every client, with EAC off.

## Using traps

- Hold **E** on a trap for its radial menu: **Load** takes its ammo or fuel from your inventory, **Unload** gives it
  back, and traps add their own commands (light the Burn Barrel, re-arm the Bear Trap).
- Looking at a trap shows its level, kills, upgrade and what's loaded.
- Traps that wear (the Tesla Coil, Swinging Log, Cryo Vent, Ram) lose a little health each use and stop at their last
  5% until repaired. Powered ones blink their lamp when worn out.
- Damage and kills are credited to the player who placed the trap, like vanilla traps.

## Levels and upgrades

Every trap counts its own kills and levels up at 25, 75, 150 and 300 kills: +8% damage and 5% faster per level.
Status traps (Grease Slick, Sprinkler, Tar Sprayer, Cryo Vent) get +10% status duration instead of damage. At level 3
the radial menu offers two upgrades; the choice is permanent. The Salvage Hopper levels from its hauls, the
Overcharger from the kills of the traps it boosts. Vanilla turrets and blade traps level up too (+8% damage a level)
and show their level when you look at them. Picking a trap up loses its level.

## The traps

| Trap | Unlock | Power | What it does | Upkeep | Upgrades at level 3 |
|---|---|---|---|---|---|
| Grease Slick | start | none | Zombies walking through are Tarred for 12 s | 1 animal fat per 4 zombies (holds 10) | Deep Grease (55% slower) / Volatile Grease (Infernos +50%) |
| Burn Barrel | 5 | none | While lit: zombies within 1.5 m catch fire for 8 s; lights the area | 1 wood per 20 s while lit (holds 30) | Bellows (2 m) / Slow Burn (wood lasts 3x) |
| Swinging Log | 10 | none | Swings through zombies in front: 35 crushing damage, 3 m knockback, re-cocks over 5 s | 2 wear a swing | Spiked Log (+50% damage) / Battering Log (6 m, wider) |
| Bear Trap | 15 | none | First zombie on it: 50 damage, held 3 s (big zombies 1 s); then sprung | Re-arm by hand | Spring Loader (re-arms after 15 s) / Heavy Jaws (5 s, big zombies too) |
| Trip Bow | 20 | none | Every 3 s shoots a loaded arrow at the first zombie in a 12 m line ahead | Vanilla arrows (holds 30) | Repeater (1.5 s) / Long Draw (+50% damage, 20 m) |
| Sprinkler | 25 | 5 W | Soaks zombies in a 6 m, 60 degree cone ahead for 10 s | none | Deluge (90 degrees, 20 s) / Pressure Washer (narrow jet, 1 m shove, 15 damage) |
| Tar Sprayer | 25 | 5 W | Every 2 s lobs tar at the nearest zombie within 10 m: 5 damage, Tarred in a 2 m splash | Tar (holds 40, 4 globs each) | Sticky Tar (60% slower) / Volatile Tar (Infernos +50%, spread 5 m) |
| Salvage Hopper | 25 | none | Each zombie your traps kill within 10 m drops 1-3 scrap iron (and sometimes brass) into it | none | Ammo Press (the haul refills the emptiest ammo trap nearby) / Scavenger (sometimes food, meds, gun parts) |
| Tesla Coil | 50 | 30 W | Every 1.5 s zaps the nearest zombie within 8 m for 22, jumping to 2 more at 60% a jump; 10% jolt | 1 wear a zap | Storm (2 more jumps, -20% damage) / Overload (no jumps, 2.5x damage, every hit stuns) |
| Cryo Vent | 50 | 20 W | Floor grate: every 1.5 s zombies on it take 6 cold and a Chilled stack | 1 wear a pulse | Deep Freeze (freezes at 2 stacks, 3 s) / Frost Field (2.5 m ice patch, chill +5 s) |
| Ram | 50 | 15 W | Every 2 s punches zombies within 2 m ahead: 60 damage, 4 m knockback | 2 wear a punch | Piledriver (2x damage, no knockback) / Battering Ram (8 m, reaches 3 m) |
| Flame Vent | 75 | 10 W | 5 m fire cone: 15 damage a second and sets zombies on fire | 1 gas can a second firing (holds 500) | Napalm (fire stays on the ground 4 s) / Blowtorch (10 m jet, 1.5x damage) |
| Overcharger | 75 | 40 W | The mod's powered traps within 5 m act 25% faster and wear 25% faster | none | Capacitor Bank (8 m) / Surge (+50% speed, double wear) |
| Bolt Thrower | 100 | 15 W | Every 3 s shoots a rebar bolt at the zombie with the most health within 30 m: 800 damage and a knockdown | Rebar bolts (holds 20) | Skewer (through 3 zombies) / Explosive Bolts (3 m blast for 150, no block damage) |

Unlocks are the vanilla traps crafting skill. The primitive traps (no power) are crafted by hand; the rest at a
workbench. Tar (oil and coal) and rebar bolts (forged iron and polymers) are made at a workbench. The Flame Vent is the
game's own unfinished flamethrower trap model (two blocks deep); it fires out of the end with the three nozzles.

## Statuses and combos

| Status | From | Effect | Combo |
|---|---|---|---|
| Soaked | Sprinkler | 15% slower, can't catch fire | Tesla Coil: double damage, one more jump, and its jolt becomes a 2 s stun (then 6 s immune) |
| Tarred | Grease Slick, Tar Sprayer | 35% slower | Any fire (the traps', a molotov, a flaming arrow) turns it into an **Inferno**: 15 damage a second for 6 s, spreading to tarred zombies within 3 m |
| Chilled | Cryo Vent | 20% slower per stack | 3 stacks freeze it for 2 s (then 6 s before it can freeze again) |
| Frozen | Cryo Vent | Can't move | Blunt and crushing hits do double damage (**Shatter**): the Ram, the Swinging Log, clubs, sledgehammers |
| Held | Bear Trap | Can't move | |

Big zombies (demolishers and bosses) get half the slows, never freeze and are held for less. Knockbacks can't hit the
same zombie again for 2.5 s, and stuns are followed by an immunity, so nothing can be stun-locked. The traps' own fire
does 5 damage a second, weaker than a molotov's on purpose.

## Blood Moon report and forecast

When a Blood Moon ends, everyone gets a report window (and a chat summary): zombies killed by traps and by players, kills
by kind of trap, the MVP trap, level-ups, combos (soaked shocks, Infernos, freezes, shatters), traps destroyed, and the
world's records. On the morning of Blood Moon day a radio message in chat forecasts the horde for the players' game
stage from the game's own spawn tables, with the special zombies to expect. Records live in the save folder
(`TrapsExpanded/bloodmoon.dat`, with the traps' levels and ammo in `traps.dat`).

## Building

- `src\build.bat` builds `TrapsExpanded.dll` (needs Visual Studio's C# compiler and the game's Harmony).
- `src\fetch-textures.ps1` downloads the Poly Haven texture sets (CC0) the models are textured with into
  `blender\textures` (not committed, about 55 MB). Only the baked result ships.
- `src\build-models.bat` builds the models: each `blender\<trap>.py` script makes the mesh, bakes its textures into
  `unity\Assets\TrapsExpanded\<Trap>\`, renders previews and the item icon; then Unity 2022.3.62f2 in batch mode makes
  the prefabs and the effects (`unity\Assets\Editor\TrapsEffects.cs`), builds `Resources\trapsexpanded.unity3d` and
  renders `unity\Build\<Trap>-preview.png` (each trap in the game's shader between vanilla traps) and
  `Effects-preview.png`. Needs Blender on PATH and Unity Hub signed in. Pass `script:folder:icon` entries to rebuild
  only some models.
- Moving parts (the log, the jaws, the swivels, the ram head) are separate meshes whose origin is their pivot. Don't
  rely on points (empties) parented to a moving part: Blender's FBX export puts them in the wrong place, so the C#
  works those positions out from the geometry instead.
