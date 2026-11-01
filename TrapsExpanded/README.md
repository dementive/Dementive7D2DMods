# Traps Expanded

New powered traps with their own models, built to work together like a tower defense game. Work in progress: this
build has one trap, the Tesla Coil, to test the whole pipeline from Blender model to working trap.

Has a DLL and new models, so it has to be installed on the server and on every client, with EAC off.

## Tesla Coil

Built from scrap like the vanilla traps: a pole transformer bolted to a pallet, a copper-pipe primary on wooden
blocks, a secondary wound on PVC pipe and a dryer-duct ring on top, with a junction box whose lamp lights while the
coil has power.

| | |
|---|---|
| Power | 30 W |
| Unlocks | Traps crafting skill 50, with the shotgun turret |
| Recipe | 15 forged steel, 12 electrical parts, 4 mechanical parts, 5 polymers, 5 oil (workbench) |
| Attack | Every 1.5 s, zaps the nearest zombie within 8 m for 22 damage |
| Chain | The arc jumps to 2 more zombies, each within 4 m of the last, at 60% damage per jump |
| Jolt | 10% chance per zombie hit: a one-second near stop and the vanilla electrocute flinch (not on charged zombies) |
| Wear | Each zap costs the coil 1 of its 1,000 health. At its last 5% it stops and its lamp blinks until repaired |

It needs a clear path to its first target; zombies in the way still conduct. Damage is credited to the coil's
owner, like the vanilla traps.

## Building

- `src\build.bat` builds `TrapsExpanded.dll` (needs Visual Studio's C# compiler).
- `src\fetch-textures.ps1` downloads the Poly Haven texture sets (CC0) the models are textured with into
  `blender\textures` (not committed, about 55 MB). Only the baked result ships.
- `src\build-models.bat` builds the models: each `blender\<trap>.py` script makes the mesh, bakes its textures into
  `unity\Assets\TrapsExpanded\<Trap>\`, renders previews and the item icon; then Unity 2022.3.62f2 in batch mode makes
  the prefabs, builds `Resources\trapsexpanded.unity3d` and renders `unity\Build\<Trap>-preview.png`. Needs Blender
  on PATH and Unity Hub signed in.
