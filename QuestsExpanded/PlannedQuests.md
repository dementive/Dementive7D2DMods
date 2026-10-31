# Planned Quest Types

Design notes for quest types and systems we want to add or bring back. Each section says how the quest plays, what has been decided, how it is (or would be) built, and what has to be checked in-game. **Nothing here has been playtested yet.**

New quests should be generated with QuestMaker like the existing ones, with their text in `Config/Localization.csv`.

## Build order

1. **Commission**: built (43 commissions, `QuestMaker/commissions.py`); waiting on an in-game playtest.
2. **The shared wave system**: built (`WaveDirectorDEM`), with bosses, boss loot bags, themed hordes and map markers.
3. **Clear and Defend**, **Bounty Hunt** (with its horde variant), **Build and Defend**, **Clear, Build and Defend**, **Last Stand**, **Blood Moon Bounty** and **Create Outpost**: built (50 quests from `QuestMaker/defense.py`); waiting on an in-game playtest.
4. **Contracts**: built, then removed after playtesting (see Decided against).
5. **Retire the POI-group quests:** done (see the last section).
6. **NPC quests** (Bandit Hideout, bandit raids, Rescue, Safehouse): designed and approved, not built yet. They only appear when the player has NPC mods installed.

## Rules for every new quest type

- **Tier progress:** every quest counts toward the trader's tier progress, whatever its type.
- **Co-op:** everything must work seamlessly in co-op, always: shared quests, parties, and dedicated servers with clients. Every quest is shareable with a party.
- **Rewards:** in line with vanilla quests of the same tier. The hardest compound types (Build and Defend; Clear, Build and Defend) pay slightly more, but never enough to unbalance the game. Loot picks are fine.
- **Scaling:** the number and type of enemies follow normal game progression (the player's gamestage), using the game's gamestage spawn lists rather than fixed zombie lists.
- **Blood moons:** no special handling. Planning around horde night is the player's job.
- **Distance:** same distance bands and biome rules as vanilla quests.

## Shared foundation: the wave director

**Status: built, not yet playtested.**

Every defense-style quest needs waves of zombies that reliably end. The old Clear and Defend quests (still in `Config/quests.xml`, but commented out of every trader's quest list) did each wave as `<action type="SpawnEnemy">` followed by `<objective type="ObjectiveEntityKill" value="N">`, that is, "spawn some zombies, then kill N of anything". That is why players reported on Nexus that the waves got stuck:

- Kills from bleeding, traps, turrets or other players may not count.
- A zombie that spawns inside a wall or falls through the floor can never be killed, so the wave never finishes.
- The zombie lists are fixed, so difficulty doesn't follow the player's gamestage.

The first plan was to run each wave as a vanilla game event sequence. That doesn't work in co-op: the game's `ObjectiveGameEvent` runs the event for whoever's copy of the quest reaches it, so every member of a party would start their own waves, and only that member's copy is told when the event finishes.

So the waves run in C# in `QuestsExpanded.dll`:

- **`ObjectiveDefendWavesDEM`** (`<objective type="DefendWavesDEM, QuestsExpanded">`): the objective. Put it in the same phase as `POIStayWithin` (or `StayWithin`) so leaving the area fails the quest. Its value is the number of waves done, so a quest picked up again later resumes from the next wave. Properties:
  - `waves`; `center`: `poi` (the POI's footprint, default), `location` (the quest's marker) or `flag` (the flag the player planted); `radius` for `location` and `flag`
  - `spawners`: gamestage spawners, one picked per wave; `bosses`: entity classes, one picked for the final wave; `strength`: gamestage multiplier
  - `bounty`: a boss inside the POI instead of waves (see Bounty Hunt); `keyword` and `text`: the quest's own versions of the objective text and messages (e.g. `DefendWavesDEM_incoming_horde`)
- **`WaveDirectorDEM`** (server): one defense per quest, keyed by quest code, which shared copies keep. Every party member whose quest reaches the defense joins it; the first one starts it, and it only stops when every member has left (finished, failed, abandoned or logged out). A won defense is remembered for an hour, so a party member whose quest only reaches it later completes instead of starting it over.
- **Waves** are sized by vanilla's `defenseGSList` spawner (a gamestage table vanilla ships for its unreleased defense quests) at the party's gamestage (`GameStageDefinition.CalcGameStageAround`), each wave at a slightly higher gamestage (+15%) and 20% bigger than the last (e.g. 4, 5, 6 zombies at the lowest gamestages), with more zombies for each extra player. The zombies come from the quest's spawners (`defenseGSList` unless the quest picks themed hordes; themed spawners only choose which zombies, since their own counts are for wandering hordes). Where they spawn depends on the quest (objective property `spawn`), never in water or a trader's area, and they are sent after the closest player:
  - `inside` (Clear and Defend): about half come out of the cleared building, at its sleeper spots at least 10m from every player, the rest from 2-6m outside the POI's footprint.
  - `walls` (the default for POIs: Clear, Build and Defend, Create Outpost): all from 2-6m outside the POI's footprint, so fortifications matter.
  - Flags and spots in the wild (Build and Defend, Last Stand, Horde Bounty): all around, 6-14m outside the defended area.
- **Every kill counts:** any enemy that dies during a wave, if it was one of the wave's or died in the defended area (+20m), counts toward the wave, however it died. That includes zombies drawn in by gunfire. The quest log shows what's left to kill; wave zombies still alive when it reaches 0 carry over into the next wave (a server-side hook on enemy deaths, `DefenseKillPatches`).
- **Breaks** of 15 seconds between waves, with on-screen messages before and during each wave, and the quest log showing the wave and zombies left.
- **No stalls:** a wave that lasts 4 minutes removes whatever is left (stuck or lost zombies) and counts as done. Zombies that die any way (bleeding, traps, turrets, other players) or unload count as gone.
- **`NetPackageDefendWavesDEM`** carries joining, leaving and the server's status to each player.
- **`QuestMaker/defense.py`** generates the defense quests and the wave text, like `commissions.py`.

- **Markers:** once 3 or fewer zombies of a wave are left, they show on the map and compass (`buffDementiveMarked`).
- **Bosses** (`buffDementiveBoss`): 2.5x health, half damage from explosions, 20% bigger, with vanilla's Twitch boss health bar overhead and a marker on the map and compass. A boss always drops a boss loot bag (`EntityLootContainerBoss`) where it dies. Bosses by tier, one picked at random:

| Tier | Bosses |
|---|---|
| 2 | Biker, Fat Cop |
| 3 | Feral Wight, Demolisher |
| 4 | Radiated Mutated, Radiated Screamer |
| 5 | Charged Wight, Mutated, Spider or Utility Worker (vanilla has the Charged Biker, Fat Cop and Soldier commented out) |
| 6 | Infernal Biker, Fat Cop, Wight, Mutated or Soldier |

Things to check in the playtest: the waves start after the clear, zombies reach the player and the waves end, the quest log and messages update, leaving the area fails the quest and removes the zombies, bosses are tougher and marked and drop their bag, and in a party only one set of waves spawns and everyone's quest completes.

## Commission

**Status: built, not yet playtested.** Things to check in-game: traders offer commissions (non-POI quests are new to this mod), crafting at a workstation counts, turn-in takes the items, shared commissions credit everyone's crafting and only the original taker delivers.

A crafting order: the trader commissions a batch of items you have to craft yourself, then you deliver it. Commissions are there to make the crafting side of the game pay off.

- **You have to craft it:** commissions use the game's `Craft` objective, which only counts items crafted after the quest is accepted (it listens to the crafting event itself). Loot, trader stock or a stockpile don't count. A delivery step then hands the items over.
- **One workstation or crafting area per order**, scaling with tier, for example:
  - Tier 1: a campfire cooking order
  - Tier 2: a forge order (forged iron, iron tools)
  - Tier 3: a chemistry station order (medicine, gunpowder)
  - Tier 4: a cement mixer order (concrete)
  - Tier 5-6: an armory order (steel weapons, ammo)
- **Themes:** most commissions are generic and can come from any trader; occasionally one matches the trader's specialty (Jen medicine, Hugh weapons and ammo, Rekt food, Bob tools and building materials, Joel armor and clothing).
- **Rewards feed crafting back:** dukes plus crafting magazines for the commission's crafting area, and at higher tiers workstation tools such as an anvil or crucible. Balanced against vanilla quests of the same tier.
- **Balance:** an order takes about as long as a POI quest of the same tier, counting gathering, processing and crafting time.
- **Never impossible:** traders only offer commissions whose items you can craft with the recipes you've unlocked (C#; vanilla can't check unlocks when offering quests).
- **Co-op:** crafting by anyone in the party who shares the commission counts toward it (C#; vanilla's `Craft` objective only counts the player's own crafting).
- **Offered:** at most one commission per trader at a time. No deadline.
- **Tiers:** 1-6.
- **Later, maybe:** quality requirements ("a quality 4+ machete") to tie commissions to crafting skill levels. The `Craft` objective only checks item and amount, so this needs more C#.

## Bounty Hunt

A bounty boss is holed up in a POI. Clear the POI, kill the boss and report back.

**Status: built (tiers 2-6, plus the horde variant at tiers 2-6), not yet playtested.** The boss spawns when the clear starts, at the POI's sleeper spawn point farthest from the players, with 2-6 escorts (by gamestage) at the spawn points nearest it. The clear and the boss are both objectives of the clear phase. The horde variant goes to a spot 350-600m from the trader (like vanilla's buried supplies); when you arrive, one themed horde (cops, soldiers, spiders, biker bar, burnt, lumberjacks, utility workers or zombie dogs) comes at you with a boss from the tier's list leading it, and `StayWithin` keeps you within 50m of the spot. The wave time limit and the markers handle horde members that wander off. Rewards: the mod's clear rewards for the tier, plus the boss bag.

- **The boss is in the POI from the start**, as a tougher version of its zombie type (moderately more health; tough, not ultra difficult). It always drops a boss loot bag.
- **Boss by tier** (2-6):

| Tier | Boss |
|---|---|
| 2 | Biker or Fat Cop |
| 3 | Feral Wight or Demolisher |
| 4 | Radiated Mutated or Radiated Screamer |
| 5 | A Charged variant |
| 6 | An Infernal variant |

- **Escorts** scale with gamestage.
- **Horde variant** (replaces a standalone "Eliminate Roaming Horde" quest): the trader sends you to a spot in the wilderness, and a themed wandering horde comes at you when you arrive (`spawn_type="WanderingHorde"`), such as a feral dog pack, cops led by a Demolisher, or a screamer-led horde. Its size and makeup scale with gamestage.
- **Flow:** go to the POI, rally point, clear sleepers, return to the trader. The boss spawns inside the POI, away from the player, when the clear starts; XML can't place it in a specific room.
- **No infested variant.**
- **Watch out for:** horde members wandering off or unloading with distant terrain, which would stall the quest. They need a marker or a time limit.

## Clear and Defend

Clear a POI, then hold it against waves of zombies coming from outside.

**Status: built (tiers 1-6, infested variant at tiers 3-6), not yet playtested.** Infested variants use vanilla's infested settings (double sleepers, POIs a tier lower) and pay 25% more. Rewards: the mod's fetch-and-clear rewards for the tier (tier 1: its clear rewards plus 15%).

- **Generic, like vanilla:** any POI of the quest's tier that supports clear quests, with the existing tag-based POI picking. This replaces the POI-specific `*_clear_and_defend` quests and the hand-written `tier1`-`tier6_dementiveDefenseQuests` in `Config/quests.xml`.
- **Waves:** 3 at tiers 1-2, 4 at tiers 3-4, 5 at tiers 5-6, each bigger than the last, and the last with a boss at every tier (tier 1: a Spider, Lumberjack or Fat Hawaiian with the boss buff). Gamestage-scaled, 15-second breaks with a warning, leaving fails the quest.
- **After the first playtest:** the tier 1 waves were 3 x 4 zombies spawning far out past the yard, so the player had to go outside to fight, and zombies drawn in by gunfire didn't count. Now about half of each wave comes back out of the building, the rest spawn just outside it, waves grow each time, and every kill in the area counts.
- **Infested variant:** one, at tiers 3 and up. Traders pick randomly from their quest list, so keeping the number of variants small is what keeps them from being spammy.
- **Large POIs:** zombies spawn just outside the POI's footprint, all around it, and head straight for the player. The wave time limit stops a huge building from stalling a wave. If that still plays badly on tier 5-6 POIs, the fallback is to spawn waves inside parts of the building that have already been cleared ("they're coming back in").

## Build and Defend

The trader hands you a supply kit, you go to a spot in the wilderness, build a defense against the clock, then survive the waves.

**Status: built (tiers 1-5), not yet playtested.** How it's built, where it differs from the plan below:
- The "marker" that starts the build phase is a **White River flag** in the kit (block `questFlagDEM`, `PlaceFlagDEM` objective). Plant it within 30m of the quest's marker, where you want your base; the waves come at the flag. A flag planted too far away says so, and can be picked up and planted again. In a party, the flag one member plants counts for everyone.
- The 5-minute countdown (`BuildPhaseDEM`) shows in the quest log, with a warning 30 seconds before the waves.
- The site is 350-600m from the trader, like vanilla's buried supplies. During the waves `StayWithin` keeps you within 60m of the quest's marker; the waves spawn 18-26m from the flag.
- Waves: 3/4/4/5/6 at tiers 1-5, boss in the last wave at tiers 4-5. Rewards: fetch-and-clear rewards plus 10%.
- **Kits** as built (counts in `QuestMaker/defense.py`). The planned blade and dart traps were left out because they need power (a generator or battery bank, fuel or batteries, and wiring) to do anything; adding a power setup would make the kits much bigger. **To decide:** leave them out, or add a small power setup at tiers 3-4.

| Tier | Kit |
|---|---|
| 1 | 30 wood frames, 20 cobblestone, 8 wood spikes |
| 2 | 30 wood frames, 30 cobblestone, 8 wood spikes, 6 iron bars, 8 barbed wire fences |
| 3 | 20 cobblestone, 30 concrete, 10 iron spikes, 8 iron bars, 10 barbed wire fences |
| 4 | 50 concrete, 12 iron spikes, 10 iron bars, 12 barbed wire fences |
| 5 | 30 concrete, 30 steel, 12 iron spikes, 12 barbed wire fences, a junk turret and 300 turret ammo |

1. **Accept:** the trader gives you the kit right away. A phase-1 `QuestActionGameEvent` runs an `AddItems` event.
2. **Travel:** `ObjectiveRandomGoto` to flat ground, with the same distances as vanilla quests.
3. **Build phase:** starts when you activate a marker at the site, so you can scout first. It lasts **5 minutes at every tier**. You can leave the site during the build phase, for example to chop wood.
4. **Defend:** 3-6 gamestage-scaled waves from every side, with a boss in the final wave at tiers 4-5. Leaving the area during the waves fails the quest.
5. **Return** to the trader for the reward.

- **Tiers:** 1-5. Any time of day.
- **Parties:** every member gets a kit (shared quests run separately for each member). The waves already grow with party size.
- **No infested variant** (there is no POI).
- **Kits:** small and balanced, chosen when building. A starting point:
  - Tier 1: wood frames, wood spikes, some cobblestone
  - Tier 2: adds iron bars and barbed wire
  - Tier 3: concrete blocks and blade traps
  - Tier 4: reinforced concrete and dart traps
  - Tier 5: steel blocks, a junk turret and ammo
- **Decided:** no anti-exploit measures for abandoning the quest after taking the kit; kits stay small and hordes hard enough that it isn't worth it.
- The base stays in the world afterwards as a little outpost.

## Clear, Build and Defend

The finale: clear a POI, fortify it against the clock with a kit from the trader, then defend it against a really difficult horde coming from outside.

**Status: built (tiers 3-6, infested variant at tiers 3-6), not yet playtested.** The kit (no flag) is the Build and Defend kit of the tier; tier 6 gets 40 concrete, 40 steel, 16 iron spikes, 16 barbed wire fences, a junk turret and 400 ammo. Waves: 4/4/5/5 at tiers 3-6 at 1.25x gamestage, with a boss in the last wave at every tier. Rewards: fetch-and-clear rewards plus 20% (infested: plus 25% on top).

- **Tiers:** 3-6.
- **POIs:** any POI of the quest's tier that supports clear quests. No hand-picked list.
- **Flow:** kit on accept, go to the POI, rally point, clear sleepers, **5-minute** build phase, waves, return.
- Players can place blocks in an active quest POI, so fortifying the POI itself works.
- **Watch out for:**
  - Fortifications disappear whenever the POI resets for a later quest.
  - It is a long chain. If the clear phase stalls on vanilla's "one last sleeper you can't find" problem, the player loses a lot of time.
- **Infested variant:** one, at tiers 3 and up, like Clear and Defend.
- **Large POIs:** handled the same way as Clear and Defend.

## Create Outpost

The trader gives you a building kit and a flag. Clear a POI, plant the flag inside, and hold the outpost for several in-game days against nightly attacks that grow each night.

**Status: built (tiers 2-6), not yet playtested.** How it's built:
- **Nights to hold:** 2, 3, 3, 4, 5 at tiers 2-6. Each night at 22:00 an attack of 3 waves hits the outpost, at a higher gamestage (+25% per night held) and with more zombies (+20% per night) each night. Waves come from outside the POI like Clear and Defend.
- **The flag** is the Duke's wall banner (block `questOutpostFlagDEM`, 3x2x1 so it fits indoors; vanilla's flag poles are 20 blocks tall). It has to go inside the POI's footprint. It has 2000 health (a cloth banner has about 50) so one swipe doesn't end a multi-day quest. Picking it up or losing it to the zombies makes the outpost fall.
- **Warnings** on screen 2 hours, 1 hour and 15 minutes before each attack; the quest log counts down to it.
- **Presence:** when an attack starts, at least one player sharing the quest has to be within the POI's area (plus 20m). Zombies go for the players at the outpost; with nobody there, they go for the banner.
- **Co-op (decision to check):** the outpost is shared. It only falls if *nobody* sharing it is there when an attack comes, and everyone sharing it gets the reward when it holds. A member who was offline when it fell or held finds out when they log in.
- **Persistence:** the server keeps each outpost's progress in the world's save folder (`QuestsExpanded/outposts.dat`), so it survives logouts and restarts. An attack nobody was online for counts as missed, and the outpost falls. Everyone logging out in the middle of an attack also loses the outpost.
- **Vanilla quirks handled:** vanilla fails a POI quest when the player dies and when a party member logs back in mid-quest. Once the banner is up the outpost is no longer treated as an active POI quest, so dying or logging out during the days doesn't fail it.
- **Kit:** the Build and Defend kit of the tier plus the banner. **Rewards:** fetch-and-clear rewards plus 50%.

- **Tiers:** 2-6. **Days to hold:** 2 at tier 2, rising to 5 at tier 6 (exact split to tune).
- **POIs:** any POI of the quest's tier that supports clear quests.
- **Kit:** given on accept, like the other build quests. It includes the flag.
- **The flag:** placed inside the POI. If zombies destroy it, the outpost falls and the quest fails.
- **Days:** you are free to leave the outpost during the day to scavenge, gather or visit the trader. Being forced to stay in the area for days would not be fun, so the quest never requires it.
- **Nights:** each night at a set hour an attack hits the outpost, bigger every night (gamestage-scaled). Warnings count down to it, in the quest log and as on-screen messages before it starts. You must be at the outpost when the attack starts; if you aren't, the outpost falls and the quest fails.
- **Blood moons:** no special handling. A horde night at your outpost is emergent gameplay and the player's to plan for.
- **Rewards:** a big payout at the end; this is one of the hardest quests, so it sits at the top of the reward range without unbalancing it.
- **Likely needs C#** in `QuestsExpanded.dll`: scheduling the nightly attacks, tracking the flag, and steering each attack at the flag rather than only at the player.
- **Watch out for:** the fortifications disappear whenever the POI resets for a later quest.

## Last Stand

Endless waves at a site, each harder than the last. After every wave you choose: leave with the reward built up so far, or stay for one more wave and a bigger payout. Dying loses everything.

**Status: built (tiers 1-6), not yet playtested.** How it's built:
- Kit (the Build and Defend kit of the tier, tier 6 too) and White River flag on accept; site 350-600m from the trader; plant the flag; 5-minute build; then the stand.
- **Waves:** sized by the defense spawner, each at 15% higher gamestage and 10% bigger than the last, with no cap. A boss joins every 5th wave (tier 1 uses the tier 2 bosses). The first wave's gamestage is 0.8x at tier 1 rising to 1.3x at tier 6. 30-second breaks.
- **Leaving:** more than 50m from the flag counts as leaving. During a break it banks the waves held; during a wave it's fleeing and fails the quest; before the first wave it fails the quest. Dying fails it.
- **Pay:** a new reward type (`RewardLastStandDEM`): experience and dukes for every wave banked, each wave paying 25% more than the one before. The first wave pays the tier's clear rewards / 5.5, so 4 waves pay about one clear quest. The tier's usual loot picks are offered on top (every vanilla quest has loot picks, and the turn-in window expects them).
- **Co-op:** everyone fights the same waves; each player banks for themselves and only waves they were there for count.

- Push-your-luck inside a single fight.
- **Site:** a random spot almost anywhere (wilderness, town, next to a POI), with the same distance rules as vanilla quests.
- **Build phase:** 5 minutes with a kit, like the other build quests.
- **Breaks:** about 30 seconds between waves, longer than in the other defense types. Walking out of the area during a break ends the stand and banks the reward. Leaving during a wave counts as fleeing and loses everything.
- **Payout:** grows with each wave survived, faster the longer you stay. Paid when you return to the trader.
- **Co-op:** each player banks their own reward. A player who dies loses theirs; the rest can keep going. Anyone can leave during a break and keep what they've earned.
- **Tiers:** 1-6. The tier sets the payout rate and how hard the first wave hits; after that, waves keep escalating with no cap.

## Blood Moon Bounty

A bounty for the next horde night, fought wherever you are (normally your own base). Bosses show up during the night; at higher tiers it becomes waves of bosses, each harder than the last.

**Status: built (tiers 1-6), not yet playtested.** How it's built:
- **Offered** only from 2 days before a blood moon until it starts (a check when traders build their quest list), at most one per trader. A trader's list lasts until it refreshes, so a bounty picked up after the blood moon simply waits for the next one.
- **Bosses:** when the blood moon starts, the first wave spawns 25-40m from the players; later waves come one in-game hour apart. Tier 1: one tier 2 boss. Tier 2: one tier 3 boss. Tier 3: two tier 3 bosses. Tier 4: three tier 4 bosses. Tier 5: five waves of two (boss tiers 3, 4, 4, 5, 5). Tier 6: six waves of two (4, 4, 5, 5, 6, 6). Bigger parties get more bosses. A boss that unloads or gets lost comes back near the players.
- **Rewards:** the mod's clear rewards for the tier, plus the boss bags.

- Gives the blood moon a goal and a payoff on top of surviving it.
- **Offered:** only in the 2 days before a blood moon, at most one per trader. No location; it happens wherever you are when the horde night starts.
- **Bosses by tier:** 1 boss at tiers 1-2; 2-3 bosses at tiers 3-4; at tiers 5-6 a wave of bosses roughly every hour through the night, each harder than the last. Bosses are tougher versions of their zombie types (like Bounty Hunt) and each drops a boss loot bag.
- **Winning:** kill every boss without dying. There is no deadline: horde nights often run into the next day, so bosses don't leave at dawn. Dying fails the bounty.
- **Co-op:** one shared set of bosses for the party, sized to the party. Everyone sharing the quest gets the reward; a member who dies fails their own bounty while the rest carry on.

## NPC quests (with NPC mods)

Quests with human NPCs: bandits to fight and survivors to rescue. The base game has no NPCs that can do this, so these quests use whatever NPC mods the player has installed. QuestsExpanded doesn't require any of them: without NPC mods these quests never show up at the trader, and the rest of the mod works exactly as before.

**Status: designed and approved on 2026-10-31 (see "Decided" below), nothing built yet.** Building starts once SCore, NPC Core and NPC packs are installed for testing (see "Before building").

### Finding the NPCs

The base game already has types for human NPCs that it doesn't use yet, and the NPC mods build on them:
- **Hostile humans:** vanilla `EntityHuman` and `EntityBandit`. SCore's bandits (`EntityNPCBandit`, `EntityEnemySDX`) derive from these.
- **Friendly NPCs:** vanilla `EntityNPC` (and its `EntitySurvivor`). SCore's NPCs (`EntityAliveSDX`, `EntityAliveSDXV4`) derive from it through `EntityTrader`.
- **Factions:** vanilla's `bandits`, `whiteriver`, `duke` and `trader` (`npc.xml`).

So:
- **The NPC list:** when the game starts, the server goes through every loaded entity class and sorts out the hostile humans and the friendly survivors by their C# class, with the faction as a cross-check. It skips traders, and vanilla's own unused survivor entries and templates (`npcSurvivorTemplate`, `npcSurvivorRanged`, ...).
- **Followers:** only NPCs made with SCore (the `IEntityAliveSDX` interface) can follow a player, so only they can be rescued or move into a safehouse. Nearly every NPC pack is built on SCore and NPC Core.
- **No link to SCore:** QuestsExpanded never references SCore's DLL. To make a survivor follow, it calls SCore's own `EntityUtilities.SetLeader` by name (reflection), the same call SCore's hiring makes: it sets the NPC's `Leader` cvar, the player's `hired_<id>` cvar and the `buffOrderFollow` buff. Without SCore, Rescue and Safehouse aren't offered.
- **Only offered when possible:** traders only offer a bandit quest when hostile humans were found, and a Rescue or Safehouse when followers were found (the same check that hides commissions you can't craft).
- **An NPC mod removed mid-quest:** the quest fails with a message instead of breaking.
- Everything about the NPCs themselves (looks, weapons, AI, loot) comes from the NPC mods, so every NPC pack the player adds makes these quests more varied.

### Bandit Hideout

Bandits have taken over a POI. Go in and kill every one of them.

- **Flow:** go to the POI, rally point, kill the bandits, return to the trader. When the quest starts, bandits are posted at the POI's sleeper spots. The POI's own zombie sleepers are there as usual, but you don't have to clear them.
- **Three-way fights:** vanilla zombies already go after bandits, so the shooting draws zombies into the fight against both sides.
- **Goal:** kill every bandit. Once 3 or fewer are left, they show on the map and compass (`buffDementiveMarked`). From tier 3 a bandit leader with the boss buff holds the far end of the POI and drops the boss loot bag.
- **Numbers:** scale with gamestage and party size, but fewer than a zombie wave since bandits shoot back (about a third of a wave, at least 2).
- **Tiers:** 2-6, at POIs of the quest's tier that support clear quests.
- **Co-op:** one set of bandits for the party; kills by anyone count; everyone sharing the quest completes it.
- **Rewards:** the mod's clear rewards for the tier, plus whatever the bandits drop.
- **Built on** the wave director: bandits are spawned and tracked like the Bounty Hunt boss and its escorts. Kill counting already includes them: `EntityBandit` is an `EntityEnemy`, so `DefenseKillPatches` already sees their deaths.

### Bandit raids in the defense quests

When bandit NPCs are installed, some defense waves are bandit raids instead of zombies.

- **Where:** Create Outpost only, to start. From tier 3, one night's attack in each outpost is a bandit raid, never the first night. Build and Defend and Clear, Build and Defend could get raids too after a playtest.
- **How they play:** bandits fight from range, so cover and sightlines matter, not just walls. Zombies drawn by the shooting go after them too.
- **Size:** about a third of the zombie wave they replace, at least 2.
- Without bandit NPCs every wave stays zombies, as now.

### Rescue

A group of survivors is holed up in a POI and under attack. Break the attack and bring as many of them as you can back to the trader alive. Always a group: this merges the first single-survivor Rescue with the Relief Mission and Hostage Rescue ideas.

- **The group:** 3 survivors at tier 2, 4 at tiers 3-4, 5 at tier 5, 6 at tier 6, picked from the friendly NPCs that can follow (mixed, for variety).
- **Under attack when you arrive:** zombies besieging them (waves from the wave director, going for the survivors as well as the players), or, when bandit NPCs are installed, bandits holding them (posted around them like in Bandit Hideout). Tiers 2-4 pick one at random; at tiers 5-6 it can be both. The attack starts when you reach the rally point, so the survivors aren't overrun before you get there, and they can't be hurt before that.
- **Where they are:** together, in the part of the POI farthest from the entrance, marked once you're inside. You don't have to clear the whole POI.
- **Breaking it:** kill the attackers (the siege's waves, or every bandit guard). The survivors fight back with whatever their NPC mod gives them.
- **Getting out:** walk up to a survivor and they follow you. SCore's follow system keeps them with you: they keep up, ride along in vehicles, and catch up on their own if they fall more than 60m behind. Reinforcements come twice, when the group starts following and when you leave the POI's area. Each survivor who reaches the trader's compound goes inside and counts as saved.
- **Pay:** half of the tier's fetch-and-clear experience and dukes for finishing, the other half split between the survivors and paid for each one saved, plus the usual loot picks. The quest only fails if every survivor dies.
- **Vanishing:** a survivor who vanishes (NPC Core lists hired NPCs vanishing around vehicles as a known issue) comes back next to the player they were following.
- **Dying:** once the group is following, the quest is no longer treated as a POI quest (like Create Outpost after the banner), so dying doesn't fail it. Your survivors wait where they are until someone from the party walks up to them.
- **Co-op:** one group for the party. Each survivor follows whoever walks up to them first, so the group can be spread across the party. Everyone sharing the quest gets the same reward, based on how many made it.
- **Tiers:** 2-6.

### Arm the Group (part of Rescue)

- Survivors start with little gear. They use the weapons, armor and medicine you give them (SCore's give-to-NPC), so crafting and bringing gear for them means more of them make it, and a bigger payout.
- Anyone in the party can hand out gear. What you give a survivor goes inside with them; that's the cost of keeping them alive.
- **To check once installed:** NPC packs often give their NPCs special NPC-only weapons, so a crafted pistol may have to be swapped for the NPC's own version of it. Survivors from a pack that can't take gear just fight with what they have.

### Survivors who join you

- At tier 4 and up, each player sharing the quest can take one saved survivor on as a hired NPC (a reward pick): they come back out of the trader's compound to join you. You get them with all of the NPC mod's own orders (follow, stay, guard, patrol), so you can, for example, post them at your outpost or safehouse.
- **Co-op:** each player takes a different survivor, first come first served. When there are more players than saved survivors, the pick pays dukes instead.

### Safehouse

Refugees at the trader need a place to live. Build them a safehouse, lead them there, and hold it with them through its first night.

- **Accept:** the refugees wait just outside the trader's compound (2 at tier 2, 3 at tiers 3-4, 4 at tier 5, 5 at tier 6), and you get a Safehouse flag.
- **Build:** plant the flag where you want the safehouse: anywhere outside a trader's area, in the wild, in a POI or at your own base. Everything on the checklist has to be within 10m of the flag, and the quest log ticks items off as they're done. There's no kit: crafting it is the point.

| Tier | Checklist |
|---|---|
| 2 | a bedroll for each refugee, each under a roof; a campfire; a light; a storage box; a door |
| 3 | adds a workbench |
| 4 | adds a dew collector |
| 5 | adds a chemistry station |
| 6 | adds an electric light with power (a generator, battery bank or solar bank) |

- **Move in:** once the checklist passes, walk up to the refugees and lead them to the safehouse (the same follow system as Rescue). When they arrive, they settle in.
- **First night:** at 22:00 the safehouse is attacked: 3 waves like a Create Outpost night, from just outside the safehouse, going for the refugees and the players. At least one player sharing the quest has to be there when it starts. The refugees fight alongside you. If they move in after 22:00, the attack comes the next night.
- **Winning:** at least one refugee alive when the last wave ends. Losing all of them fails the quest. Return to the trader for the reward.
- **Afterwards:** the refugees stay and guard the safehouse (SCore's guard order, kept in the save), so it becomes a staffed outpost you built. They aren't anyone's hires, and nothing happens if they die later.
- **Co-op:** one safehouse per party. Blocks anyone places count toward the checklist, whoever walks up to a refugee leads them, and everyone sharing the quest completes it.
- **Rewards:** the mod's fetch-and-clear rewards plus 20%, like Clear, Build and Defend.
- **Tiers:** 2-6.
- **Built on:** the flag of Build and Defend (`PlaceFlagDEM`), Rescue's follow system, a Create Outpost night with its presence check, and a new checklist objective that scans the blocks around the flag.
- **Note:** planting the flag in a base that already has everything passes the checklist at once. Like the other build quests, there are no anti-exploit rules for that.

### Later, maybe

- **Specialists:** some survivors have a trade (medic, gunsmith, mechanic, cook). Once living in a safehouse, they craft their kind of item from materials you give them, like a workstation run by an NPC. Only once Safehouse has been playtested and turned out to be fun.

### Decided

- **Tiers:** Bandit Hideout, Rescue and Safehouse at 2-6.
- **Rescue** is always a group; it merges the first single-survivor Rescue with the Relief Mission and Hostage Rescue ideas. Arm the Group is part of it.
- **Bandit Hideout:** only the bandits have to die; the POI's zombies are optional.
- **Bandit raids:** one night per Create Outpost from tier 3, never the first; other defense quests maybe after a playtest.
- **Survivors who join you:** yes, from tier 4, one per player.
- **Squad Op and Ambush:** not chosen (see Decided against). **Specialists:** later, maybe, after a Safehouse playtest.
- **Bandit difficulty:** NPC packs don't share a difficulty scale, so the quests rank the hostile NPCs they found by health and use the weaker ones at low tiers, all of them at tier 6. A list for server admins of which NPCs the quests may use comes only if that isn't enough.

### Before building

- Install SCore, NPC Core, a bandit pack and a friendly NPC pack (soldiers or civilians, unless NPC Core comes with followers) for testing, and check how NPC Core sets up its NPCs (classes, factions, tags). NPC Core is only on Nexus, so its files haven't been looked at yet.
- NPC mods have to be installed on the server and every client. That requirement is theirs: QuestsExpanded's own requirements don't change.

## Decided against

- **Contracts** (a roguelike layer over any quest: rewards went into a pot that grew with every quest done in a row, with boons to pick and a boss on the fifth): built, then removed after playtesting; it wasn't fun.
- **Restore Power by area:** too close to vanilla's restore power quests.
- **Hunting contracts** (kill N animals or zombies anywhere): boring.
- **Supply Requests** (hand over items from your inventory): trivial with a stockpile and a chore without one, and they didn't push players toward crafting. Replaced by Commissions.
- **Courier runs between traders:** awkward when the player hasn't found the other traders yet.
- **Eliminate Roaming Horde as its own quest type:** folded into Bounty Hunt as the horde variant.
- **Hand-picked POIs** for any of the new types.
- **Questlines tied to other mods** (e.g. quests rewarding Weapons Expanded weapons): every mod stays standalone.
- **Cosmetic or gimmick quests** (random chaos events, big heads, supply drops, heists, timed clears, treasure trails): they didn't add anything new to how the game plays.
- **Supply Depot** (defend three caches at once): too close to the other defend quests.
- **Other systems pitched and not chosen:** Nemesis (zombies that kill you come back stronger), Outbreak (infestation spreading across POIs over days), Job Board (player-posted paid requests), Stranded (dropped far away, survive the trip back), Nest Purge (destroy zombie-spawning nests in a POI), Raid (multi-stage tier 6 set piece), Repo Job (fix up a broken-down vehicle and drive it back), Demolition Order (bring down a condemned building), Live Specimen (wear down a fleeing zombie and capture it alive).
- **Variants of vanilla types, pitched and not chosen:** filling in the late tiers (Fetch, Buried Supplies, Restore Power and the urban/rural quests at tiers 4-6), infested Fetch & Clear and Restore Power, Search (Fetch & Clear with unmarked supplies), Backyard Stash (Buried Supplies in a POI's yard).
- **NPC quests, pitched and not chosen:** Squad Op (the trader lends you mercenaries for one hard job), Ambush (set up and spring an ambush on a bandit patrol on a road).

## Retiring POI-group quests

**Status: done.** The 108 POI-group quests, the 6 old hand-written Clear and Defend quests, the `GotoPOIDEM` objective and ZZZTongPrefabs-QuestsExpanded are gone; the 28 urban/rural tag quests stay. A removed quest a player had in progress is dropped when their save loads.

Once the new types are working, retire the 108 quests tied to specific POI groups (cabin, cave, gas station, farm, ... fetch, clear and clear-and-defend quests). They caused most of the Nexus complaints (long trips, missing markers, fetch quests at POIs that can't host them) and never worked well with POI packs like ZZTong's.

- **Keep** the 28 urban/rural tag quests. They pick from any POI with the right tags, so they also cover POI packs whose POIs are tagged.
- **Then retire** the ZZZTongPrefabs-QuestsExpanded variant, which only exists for ZZTong POI names, and the `GotoPOIDEM` objective (only used by the POI-group quests).
