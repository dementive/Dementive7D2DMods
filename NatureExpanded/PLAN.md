# Nature Expanded: plan

Approved 2026-11-03. The user found the fields "overpoweringly yellow and white and green" (vanilla's flower patches
are goldenrod, cotton and a rare chrysanthemum over grass) and the world empty: a full day turned up one rabbit, one
deer, the trader and some zombies. Vanilla allows at most one small animal per spawn area and deer only at night. They
asked for "a large variety of flora and fauna of all kinds", then "EVEN more animals and EVEN MORE plants". Herd
behavior and predator hunts were offered and not picked.

A standalone mod: it needs no other mod. Everything works in co-op. Plants and animals are the game's own world
generation and spawning, so the server decides them and every player sees the same. The ambient creatures are looks
only, each player's game drawing its own near them.

## Flora

Real plants placed by world generation, as 3D models that sway in the wind with the game's own plant shader
(`Game/EntityTintMaskSSS`: alpha cutout, `_WindStartY`/`_WindStrength`; Torch drives its wind). They grow in
**colonies**: a noise field per species decides where its drifts are, so a meadow has a swathe of lupine, a patch of
poppies and a run of daisies, rather than the same mix everywhere. Whole patches of color read from far off, and
single flowers don't. Goldenrod and cotton are thinned to two colors among many. Everything harvests for plant fibers
like grass (mushrooms and berries for a bite of food). New ground only: chunks the game already generated keep what
they have.

| Where | Plants |
|---|---|
| Pine forest meadows | Lupine (purple spikes), Poppy (red), Cornflower (blue), OxeyeDaisy (white), Paintbrush (orange-red Indian paintbrush), BlackEyedSusan (gold with a dark eye), Coneflower (pink-purple), QueenAnnesLace (white lace umbels), RedClover (low pink-red), Bergamot (lavender pompoms), Chicory (sky blue, along roads) |
| Forest floor and edges | Fern (clumps), FlyAgaric (red, white-spotted toadstools in rings), Bolete (brown mushrooms, food), Trillium (white), WildStrawberry (tiny red berries, food), Foxglove (pink spikes), WildRose (pink-flowered bush), Elderberry (white-flowered bush), Sumac (red-leaved shrub), MossyLog (fallen log with moss and shelf fungus) |
| Water's edge | Cattail, Reeds, BlueFlagIris (violet), MarshMarigold (yellow) |
| Burnt forest | Fireweed (pink spikes, the first thing back after a fire), CharredShrub (burnt bush putting out green shoots), Morels (food), and lupine coming back |
| Desert | PricklyPear (pads with yellow and pink blooms), BarrelCactus (crown of red flowers), Ocotillo (tall whips with red tips), AgaveBloom (a tall stalk of yellow flowers), DesertMarigold (yellow), Globemallow (orange), Sagebrush (silver-green), EveningPrimrose (white) |
| Snow | AlpineAster (blue-violet), Heather (purple), Winterberry (red berries on bare twigs), Snowdrop (white), FrostedJuniper (blue-green bush) |
| Wasteland | Thistle (purple), SilverSage, WildMustard (yellow), CurlyDock (rust-red seed heads), DeadBrush |

## Fauna

### Ambient creatures (looks and sounds only, each player's game, near the player)

Cheap: our own small models, wings and tails animated in their shader (an opaque deferred surface shader, so they're
lit like everything else), flocks moved by simple steering. Not entities: they can't be shot or hunted.

- **Birds:** Crow and Raven (fields, carrion, wasteland), BlueJay, Cardinal and Robin (forest edges), Sparrow flocks,
  Starling murmurations swirling over fields at dusk, Hawk and Eagle circling high, Ducks and Geese on lakes and geese
  flying over in a V, Heron standing in the shallows, Owl perched at night. Birds on the ground or in trees burst up
  when you or a zombie come close: a flock taking off ahead of you is a warning.
- **Critters:** Squirrels and Chipmunks darting up trees, Frogs at ponds, Fish jumping in lakes, Turtles on the
  shore, Lizards on desert rocks, Butterflies over the flower drifts by day (several colors), Dragonflies over water,
  Bats at dusk, Rats scurrying in towns and ruins.
- **Sound:** birdsong by day that goes quiet when zombies are near; crickets, frogs and owls at night; woodpeckers;
  geese honking overhead; wolves howling at dusk.

### New huntable animals (real game animals)

Built on the game's own animal bodies and animations, resized and recolored at runtime (the game's fur shader has no
tint, so a multiply pass over the animal's own lit color does it), with their own names, sounds, health, meat and
hides, spawned by biome:

| Animal | Body | Where |
|---|---|---|
| RedFox | coyote, small, orange-red | forest, burnt |
| ArcticFox | coyote, small, white | snow |
| SnowshoeHare | rabbit, larger; white in snow, brown elsewhere | forest, snow |
| Jackrabbit | rabbit, tan | desert |
| Elk | stag, 1.3x, dark | forest |
| Caribou | stag, pale grey-brown | snow |
| MuleDeer | doe and stag, grey-tan | desert, wasteland |
| WildTurkey | chicken, 1.6x, dark bronze, in flocks | forest |
| Pheasant | chicken, copper body and dark green head | forest meadows |
| BlackBear | bear, smaller, black | forest |
| PolarBear | bear, white, dangerous | snow |
| GreyWolf | wolf, grey | forest, snow |
| ArcticWolf | wolf, white | snow |
| Bobcat | mountain lion, 0.6x, tawny | forest, desert |
| FeralHog | boar, dark | forest, burnt |
| Javelina | boar, 0.7x, grey, in small groups | desert |

### More of them

About 2 to 3 times vanilla's wildlife (`WildlifeRate` setting), deer by day as well as at night, and the species that
live in groups (turkeys, javelinas, hares, wolves) spawning together.

## How it's built

- `blender/`: one script per model with `zkit.py` (photo-real materials, bake, FBX) and `naturekit.py` (stems,
  leaves, petals, flower heads, bark, the block-model frame: bottom at -0.5, origin at the bottom block's center).
- `unity/`: its own project (it can batch-build next to the other mods). `NatureBuilder` makes the prefabs (a root
  BoxCollider for the block's bounds), the bird and critter shaders and the bundle `Resources/natureexpanded.unity3d`.
  `NatureProbe` dumps the game's plants and animals for reference.
- `src/`: C#. At load it swaps the plant materials to the game's plant shader and tags them `T_Block` once (all
  instances share the prefab), then runs the ambient creatures, the animal recolor and the soundscape.
- `Config/`: blocks (decorations), biomes (drifts), entityclasses, entitygroups, spawning, loot, sounds, Localization.

## Build order

1. Flora: kit, models, blocks, biome drifts. (Fixes the fields first.)
2. Ambient creatures and the soundscape.
3. Huntable animals and the wildlife rate.
