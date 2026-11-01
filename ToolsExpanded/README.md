# Tools Expanded

Adds 15 rare named tools in the same style as the base game, one for each vanilla tool. Each tool is built on its vanilla tool and is better than it at the same quality: +20% block damage, +50% durability, the vanilla tool's own perks and bonuses, and a signature ability.

They can only be looted or bought, not crafted. When held they look like the vanilla tool; the icon is repainted.

Adds new icons so has to be installed on server and client. `ToolsExpanded-SERVERSIDE` is the server-only version: it uses tinted vanilla icons, so players don't need to install anything.

## Tools

| Name | Base | Ability |
|---|---|---|
| Grandpa's Hatchet | Stone axe | Wears out 75% slower. +25% damage to wood, earth and stone |
| The Contractor | Claw hammer | Repairs and upgrades 30% faster. +50% XP from repairing and upgrading |
| Night Shift | Nail gun | Repairs twice as much per hit. On Blood Moon nights you take 25% less damage while holding it |
| Widowmaker | Fireaxe | +50% damage to trees. Trees can drop honey like with the Waste Treasures book, and twice as much |
| Chopper | Steel axe | Killing a zombie with a power attack makes your axe swing 50% faster and cost no stamina for 5 seconds |
| Meat Grinder | Chainsaw | Twice the fuel tank. +25% damage to zombies |
| Prospector's Pick | Iron pickaxe | Ore can drop gold, silver and raw diamonds, at 3 times the Lucky Strike book's chance |
| John Henry | Steel pickaxe | Every block you break gives back 5 stamina. Swings 25% faster |
| Big Bertha | Auger | Twice the fuel tank. Drills 20% faster. +25% damage to stone and metal |
| Lucky Spade | Stone shovel | Digging dirt, forest ground and sand sometimes turns up a buried stash |
| Trench Raider | Iron shovel | +50% damage to zombies. Power attacks have a 25% chance to knock them down |
| X Marks the Spot | Steel shovel | Digs earth 50% faster. Inside a buried treasure circle it digs twice as fast and uses no stamina |
| Grease Monkey | Wrench | Salvaging cars gives 50% more parts, and small engines and car batteries come out in pairs |
| Tinkerer | Ratchet | +100% electrical parts and springs from salvaging |
| Pit Crew | Impact driver | Salvages 40% faster. Each car you strip has a 5% chance to drop a crate with a vanilla vehicle mod |

The Buried Stash holds a hidden stash's worth of loot. The Salvaged Vehicle Mod crate holds one vanilla vehicle mod.

## Where to find them

Chance per container opened that it holds one of the tools:

| Container | Chance |
|---|---|
| Large hardened chest (T5) | 5% |
| Hardened chest (T4) | 4% |
| Locked iron chest, buried treasure, boss zombie loot bags | 2% |
| Wall and picture safes, hidden stashes, strong zombie loot bags | 1% |
| Regular zombie loot bags | 0.5% |

Tier 4-6 trader quests can offer one as a reward (about 1 in 20 quests). Traders sometimes stock them: the stone and iron tools with the vanilla tools, the steel and motor tools with the rare tools from trader stage 50.

## Changes to vanilla

- Trees get a `DementiveTree` tag, so Widowmaker's bonus only hits trees.
- The ore blocks get the Lucky Strike drops a second time under the Prospector's Pick's own harvest tag. Dirt, forest ground and desert ground (and sand and topsoil through them) get the Buried Stash drop. Cars get the vehicle mod crate drop. These only drop for the matching tool: every player starts at 0 for those harvest tags.
- Salvage drops on cars, and electrical parts and springs on everything, get extra harvest tags. Other tools ignore them, so salvaging works as before.
- Players get a hidden buff while inside a buried treasure circle, which X Marks the Spot checks.
