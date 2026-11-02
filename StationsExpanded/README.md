# Stations Expanded

14 rare named versions of vanilla workstations, collectors and station tools. Each does everything its vanilla
version does (same model, recipes, window, tool slots and fuel, so other mods' recipes show up too) and adds a
signature bonus. They can't be crafted: they're found in loot, sold rarely by traders and offered as quest rewards.
The design is in PLAN.md.

Has a DLL and new icons, so it has to be installed on the server and on every client, with EAC off.

## Stations

| Name | Base | Bonus |
|---|---|---|
| Grandpa's Workbench | Workbench | Crafts 20% faster. 10% chance a crafted weapon, tool or armor piece comes out one quality higher (up to 6) |
| Old Smoky | Forge | Smelts 50% faster. Fuel lasts 25% longer |
| Doc's Lab | Chemistry station | Crafts 20% faster. Each craft has a 15% chance to come out twice |
| Big Tumbler | Cement mixer | Mixes twice as fast. 10% chance a batch comes out twice |
| Grandma's Hearth | Campfire | Cooks 25% faster. Fuel lasts twice as long. 10% chance a dish comes out twice |

## Collectors

| Name | Base | Bonus |
|---|---|---|
| Rain Catcher | Dew collector | Fills in 4-7 hours (vanilla 6-10). With the tarp, each fill gives 3 jars instead of 2 |
| Queen's Court | Apiary | Honey every 32 hours (vanilla 48). Its smoker slot works: a smoker halves the flowers per honey (the vanilla apiary's third slot does nothing) |
| Henhouse Deluxe | Chicken coop | Eggs and feathers every 16 hours (vanilla 24). Each hen lays 3 eggs instead of 2 |

## Station tools

Each goes in its vanilla tool's slot and counts as that tool for recipes, and keeps the vanilla tool's own bonuses.
Like vanilla tools, their crafting bonuses count while they sit in the station.

| Name | Base | Bonus |
|---|---|---|
| Old Ironsides | Anvil | Everything made at its forge is another 25% faster, 10% chance to come out twice |
| Big Lung | Bellows | Twice the vanilla bellows' smelting boost at each quality |
| The Hellpot | Crucible | Crucible recipes (forged steel and the like) 25% faster, 15% chance to come out twice |
| Grandma's Stockpot | Cooking pot | Pot recipes another 25% faster, 10% chance of a second serving |
| Pitmaster's Grill | Grill | Grill recipes another 25% faster, 15% chance of a second serving |
| Doc's Beaker | Beaker | Beaker recipes (medicine, paper) 25% faster, 15% chance to come out twice |

A named tool in a named station stacks with it.

## Where to find them

The same places and odds as the named tools in Tools Expanded, as one pool of all 14:

| Container | Chance per container that it holds one |
|---|---|
| Large hardened chest (T5) | 5% |
| Hardened chest (T4) | 4% |
| Locked iron chest, buried treasure, boss zombie loot bags | 2% |
| Wall and picture safes, hidden stashes, strong zombie loot bags | 1% |
| Regular zombie loot bags | 0.5% |

Tier 4-6 trader quests can offer one as a reward (about 1 in 20 quests). Traders sometimes stock them from trader
stage 50, beside the vanilla workstations and tools. They're also in the creative menu.

## Co-op

Crafting time is worked out by the game of the player who queues a craft, so speed bonuses apply for everyone who
uses the station. The quality and extra-item rolls happen once per finished craft, on whichever machine is running
the queue: the player with the window open, or the server while it's closed. Fuel and smelting bonuses run on both.

## Building

`Scripts\StationsExpanded\gen_stations.py <game> StationsExpanded` writes the Config from its tables and paints the
icons (`ICONS`); `src\build.bat` builds the DLL.
