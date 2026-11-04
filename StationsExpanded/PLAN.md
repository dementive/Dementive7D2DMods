# Stations Expanded: plan

**Status (2026-11-01):** approved with the defaults for the open questions below (10% quality bump, names as listed),
except the look: the user chose no new models, so every named item keeps its vanilla model and is told apart by its
name and painted icon. All six build steps are built (2026-11-01, untested in game); the Config and icons are written
by `Scripts/StationsExpanded/gen_stations.py`. Changes from the tables below, forced by the engine:

- The Hellpot, Doc's Beaker: a 15% chance to come out twice instead of "15% less iron per steel" / "15% fewer
  ingredients". Ingredient bonuses are matched by ingredient name for everything made at the station, so they
  couldn't be limited to the tool's own recipes.
- Grandma's Stockpot, Pitmaster's Grill: a 10% / 15% chance of a second serving instead of "10% more from each batch" /
  "15% less meat". Output and ingredient percentages are rounded down per craft, so they did nothing on the many
  one-item and one-meat recipes.
- Old Ironsides: "anvil recipes" means everything made at its forge (no vanilla recipe needs the anvil; it speeds up
  everything at the forge). Its "10% cheaper in iron" was dropped after review: ingredient bonuses round down per
  craft, so it made one-iron recipes like nails free. The user approved the replacement: everything made at its
  forge also has a 10% chance to come out twice.
- Henhouse Deluxe: each hen lays 3 eggs instead of 2, instead of a third row. The collector window shows at most nine
  slots, and the coop's nesting box already adds the third row.

14 rare named versions of vanilla stations, collectors and station tools, in the same style as Tools Expanded: each
one does everything its vanilla version does, plus a signature bonus. Found, not crafted.

## Rules every item follows

- **Same as vanilla, plus one thing:** a named station uses the vanilla station's recipes, window, tool slots and
  fuel, so recipes from other mods show up in it too. It can be picked up and moved like the vanilla one.
- **Look:** every item keeps its vanilla model. Its icon is the vanilla icon painted with an IconTool recipe, like
  the named tools.
- **Where to find them:** the same as the named tools. Hardened chests, safes, buried treasure and zombie loot bags,
  trader stock (rare) and tier 4-6 quest rewards. Not craftable.
- **Co-op:** see "How it runs in co-op" below. Every bonus works for every player who uses the station.
- **Standalone:** needs no other mod. The bonuses need C#, so server and clients both install it; there is no
  server-only version.

## Engine facts the design rests on

Checked in the game code (2026-11-01):

- A station block has no speed of its own. Crafting time, output count and quality are set by the client of the player
  who queues the craft, from that player's perks, the recipe and the tools in the window, then fixed in the queue.
  A named station's bonuses are applied at that same moment by the mod's code.
- The queue keeps running while nobody has the window open. Then the server runs it; with the window open, the
  client who has it open does. Fuel and smelting work the same way.
- Fuel burns at a fixed rate and smelting speed comes only from the item and the bellows, so fuel and smelting
  bonuses need code on both sides.
- Station tools are checked by exact item: a differently named anvil won't go in the slot or count for recipes
  without code. Their bonuses only apply while the station's window is open, the same as vanilla tools (smelting
  bonuses always apply).
- Collectors are driven by block settings (fill time, output per fill, fuel cost, rows, which mod does what), so the
  three collectors are mostly settings. The vanilla apiary's third mod slot (smoker) does nothing at all, because its
  effect is never read.

## Stations

| Name | Base | Signature |
|---|---|---|
| Grandpa's Workbench | Workbench | Crafts 20% faster. 10% chance a crafted weapon, tool or armor piece comes out one quality higher (up to 6) |
| Old Smoky | Forge | Smelts 50% faster. Fuel lasts 25% longer |
| Doc's Lab | Chemistry station | Crafts 20% faster. Each finished item has a 15% chance of coming with a second one |
| Big Tumbler | Cement mixer | Mixes twice as fast. 10% chance of an extra bag |
| Grandma's Hearth | Campfire | Cooks 25% faster. Fuel lasts twice as long. 10% chance of an extra portion |

## Collectors

Vanilla for comparison: the dew collector fills a jar in 6-10 hours (the tarp doubles it); the apiary makes honey
every 48 hours for 10 flowers; the coop lays eggs every 24 hours and has two rows.

| Name | Base | Signature |
|---|---|---|
| Rain Catcher | Dew collector | Fills in 4-7 hours. With the tarp, each fill gives 3 jars instead of 2 |
| Queen's Court | Apiary | Honey every 32 hours. Its smoker slot works: it halves the flowers per honey |
| Henhouse Deluxe | Chicken coop | Three rows instead of two. Eggs and feathers every 16 hours |

## Station tools

Each one also does its vanilla tool's job (unlocks the same recipes, keeps the vanilla tool's own bonuses).

| Name | Base | Signature |
|---|---|---|
| Old Ironsides | Anvil | Anvil recipes 25% faster and 10% cheaper in iron |
| Big Lung | Bellows | Twice the vanilla bellows' smelting boost |
| The Hellpot | Crucible | Forged steel 25% faster, 15% less iron per steel |
| Grandma's Stockpot | Cooking pot | Pot recipes 25% faster, 10% more from each batch |
| Pitmaster's Grill | Grill | Grill recipes 25% faster, 15% less meat |
| Doc's Beaker | Beaker | Beaker recipes 25% faster, 15% fewer ingredients |

A named tool in a named station stacks with it. Numbers are first passes, to tune in play.

## How it runs in co-op

- **Speed and quality** are set when someone queues a craft, by their own game, so every player gets them.
- **Extra items** (Doc's Lab, Big Tumbler, Grandma's Hearth) are rolled when each item finishes, on whichever machine
  is running the queue at that moment (the server, or the player with the window open). Either way the item lands in
  the station's output for everyone.
- **Fuel and smelting** bonuses run on both sides, so they hold whether or not anyone has the window open.
- **Collectors** run on the server like vanilla.
- **Named tools** work for whoever uses the station, the same as vanilla tools.

## Build order

1. Pipeline test: Grandpa's Workbench (crafting speed, the quality roll). Played before going further.
2. Old Smoky with Old Ironsides, Big Lung and The Hellpot (fuel and smelting code, named tools in the slots)
3. Grandma's Hearth with the Stockpot, Grill and Beaker
4. Doc's Lab and Big Tumbler
5. The three collectors
6. Loot, trader and quest placement

## Decided

1. Looks: vanilla models, painted icons (the user's call, 2026-11-01).
2. Grandpa's Workbench quality bump: 10%.
3. Names: as listed.

## Added 2026-11-03: crafting from storage and station status

Both approved by the user and built (untested in game). They apply to every workstation, not just the named ones.

- **Crafting from storage** (`StorageCraftingDEM`): with a workstation window open, recipes also count player
  storage within 10 m of the station (storage whose grid is `PlayerOwned`, set when a player places it, the flag the
  game's own server-side container actions use). Locked containers the player can't open and containers someone has
  open (`LockManager.IsLockedServer`) are skipped. Only items without quality or mods. The backpack and toolbelt are
  used first. The server takes the items (directly on a host or in single player, through
  `NetPackageStorageRequestDEM`/`ReplyDEM` from a client) and hands them to the player as a credit that vanilla's
  `RemoveItems` uses after the backpack and toolbelt; leftovers go to the backpack. The forge with smelting crafts
  from its material grid only (`ItemActionEntryCraft.OnActivated`), so storage doesn't apply there.
- **Station status** (`StationStatusDEM`): a line under the use prompt with the item being made, the count left in
  its queue slot and the time left on the current one, other queued slots, fuel burn time, or Idle. Engine facts:
  while nobody has a station open, the server works it once a second and sends the whole station (queue, times, fuel)
  to nearby clients; while someone has it open, their game crafts and sends the queue only when crafting starts or
  stops (`syncTEfromUI`), and the server never sets `bUserAccessing` for a remote player. So the time is shown only
  when the fire is lit, the time is above 0 and nobody has the station open; a client asks the server about the last
  part (`NetPackageStationOpenDEM`) about once a second while it looks at the station.
