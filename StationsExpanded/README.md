# Stations Expanded

14 rare named versions of vanilla workstations, collectors and station tools. Each does everything its vanilla
version does (same model, recipes, window, tool slots and fuel, so other mods' recipes show up too) and adds a
signature bonus. They can't be crafted: they're found in loot, sold rarely by traders and offered as quest rewards.
The design is in PLAN.md.

For every workstation, named or vanilla, it also adds crafting from nearby storage and a status line when you look at
a station (both below).

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

## Crafting from storage

While you have any workstation open (workbench, chemistry station, cement mixer, campfire, a named station, or a
station from another mod that uses the workstation window), its recipes can use what's in your storage within 10 m of
the station:

- **What counts:** containers players have placed, like wooden boxes, writable crates, gun safes and hardened chests.
  POI loot containers, vehicles, drones, backpacks and other stations' slots don't. A locked container counts only if
  you can open it.
- **What it can take:** items without quality or mods: resources, parts, food, ammo and the like. A recipe that needs
  a weapon or tool as an ingredient still needs that item in your backpack.
- **The recipe list** shows a recipe as craftable when your backpack, toolbelt and that storage together cover it,
  and the ingredient counts and the craft count include the storage. The storage is recounted every second.
- **Crafting** takes from the backpack and toolbelt first, and only the rest from storage, nearest container first.
  If something is cancelled, the ingredients come back to your backpack, as usual.
- **The forge** crafts from the materials smelted inside it, never from the backpack, so storage doesn't feed it.
  (With smelting turned off, it crafts from the backpack and storage like the others.) Crafting from the backpack
  without a station isn't affected.

## Station status

Looking at a workstation shows what it's doing under the use prompt:

- *Making Forged Iron x10, next one in 0:42*: the item being made, how many are still to come in that queue slot, and
  the time left on the current one. *(+2 more in the queue)* means other queue slots are waiting after it.
- *Idle* when nothing is queued.
- At stations that burn fuel (forge, campfire, chemistry station): *Fuel: 5:30 left*, with *(fire is out)* when it's
  turned off, and *Out of fuel* when something is queued but there's nothing to burn.

The time left is shown only while it's really counting down. When the fire is out or the output is full, the line
shows just the item and the count. When someone has the station open, it shows *Making Forged Iron (someone is using
it)*: their game does the crafting then and only tells the others when crafting starts or stops, so only the item is
sure.

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

Crafting from storage works for everyone, on a dedicated server and with a host:

- Only the server takes items out of storage. When you craft, your game asks it for what your backpack is missing;
  it checks the containers again, takes the items and hands them to you, and the craft starts a moment later. Requests
  are handled one at a time, so two players crafting from the same box can never both use the same items.
- A container someone else has open is skipped. Your game can't see that, so the recipe can still show as craftable;
  the craft then doesn't start and you get a message instead. If the server can't supply everything, it takes nothing
  and the craft doesn't start.
- If the craft can't start once the items arrive (the queue filled up, or you closed the window or picked another
  recipe), they go to your backpack, or on the ground if it's full.

The station status works on every player's game from the server's updates, which come once a second while a station
is working. Whether someone has the station open is asked from the server about once a second while you look at it.

## Building

`Scripts\StationsExpanded\gen_stations.py <game> StationsExpanded` writes the Config from its tables and paints the
icons (`ICONS`); `src\build.bat` builds the DLL.
