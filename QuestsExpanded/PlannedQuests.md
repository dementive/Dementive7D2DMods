# Planned Quest Types

Design notes for quest types and systems we want to add or bring back. **None of this is implemented yet.** Each section says how the quest plays, what has been decided, how it would be built, and what has to be checked in-game.

New quests should be generated with QuestMaker like the existing ones, with their text in `Config/Localization.csv`.

## Build order

1. **Commission**: built (43 commissions, `QuestMaker/commissions.py`); waiting on an in-game playtest.
2. **The shared wave system**, with a single Clear and Defend quest built on it as a prototype: built (`WaveDirectorDEM`, tier 2 Clear and Defend from `QuestMaker/defense.py`); waiting on an in-game playtest before going further.
3. Once waves work in-game: **Clear and Defend**, then **Bounty Hunt** (with its horde variant), **Build and Defend**, **Clear, Build and Defend**, **Last Stand**, **Blood Moon Bounty**, and **Create Outpost**.
4. **Contracts** can be built at any point; they work on top of any quest and don't depend on the new types.
5. If the new types work out, retire the POI-group quests (see the last section).

## Rules for every new quest type

- **Tier progress:** every quest counts toward the trader's tier progress, whatever its type.
- **Co-op:** everything must work seamlessly in co-op, always: shared quests, parties, and dedicated servers with clients. Every quest is shareable with a party.
- **Rewards:** in line with vanilla quests of the same tier. The hardest compound types (Build and Defend; Clear, Build and Defend) pay slightly more, but never enough to unbalance the game. Loot picks are fine.
- **Scaling:** the number and type of enemies follow normal game progression (the player's gamestage), using the game's gamestage spawn lists rather than fixed zombie lists.
- **Blood moons:** no special handling. Planning around horde night is the player's job.
- **Distance:** same distance bands and biome rules as vanilla quests.

## Shared foundation: the wave director

**Status: built, with a tier 2 Clear and Defend prototype; not yet playtested.**

Every defense-style quest needs waves of zombies that reliably end. The old Clear and Defend quests (still in `Config/quests.xml`, but commented out of every trader's quest list) did each wave as `<action type="SpawnEnemy">` followed by `<objective type="ObjectiveEntityKill" value="N">`, that is, "spawn some zombies, then kill N of anything". That is why players reported on Nexus that the waves got stuck:

- Kills from bleeding, traps, turrets or other players may not count.
- A zombie that spawns inside a wall or falls through the floor can never be killed, so the wave never finishes.
- The zombie lists are fixed, so difficulty doesn't follow the player's gamestage.

The first plan was to run each wave as a vanilla game event sequence. That doesn't work in co-op: the game's `ObjectiveGameEvent` runs the event for whoever's copy of the quest reaches it, so every member of a party would start their own waves, and only that member's copy is told when the event finishes.

So the waves run in C# in `QuestsExpanded.dll`:

- **`ObjectiveDefendWavesDEM`** (`<objective type="DefendWavesDEM, QuestsExpanded">`, property `waves`): the objective. Put it in the same phase as `POIStayWithin` so leaving the area fails the quest. Its value is the number of waves done, so a quest picked up again later resumes from the next wave.
- **`WaveDirectorDEM`** (server): one defense per quest, keyed by quest code, which shared copies keep. Every party member whose quest reaches the defense joins it; the first one starts it, and it only stops when every member has left (finished, failed, abandoned or logged out).
- **Waves** come from vanilla's `defenseGSList` spawner (a gamestage table vanilla ships for its unreleased defense quests) at the party's gamestage (`GameStageDefinition.CalcGameStageAround`), each wave at a slightly higher gamestage than the last, with more zombies for each extra player. They spawn 6-14m outside the POI's footprint all around it, not in water or a trader's area, and are sent after the closest player.
- **Breaks** of 15 seconds between waves, with on-screen messages before and during each wave, and the quest log showing the wave and zombies left.
- **No stalls:** a wave that lasts 4 minutes removes whatever is left (stuck or lost zombies) and counts as done. Zombies that die any way (bleeding, traps, turrets, other players) or unload count as gone.
- **`NetPackageDefendWavesDEM`** carries joining, leaving and the server's status to each player.
- **`QuestMaker/defense.py`** generates the defense quests and the wave text, like `commissions.py`.

Things to check in the playtest: the waves start after the clear, zombies reach the player and the waves end, the quest log and messages update, leaving the area fails the quest and removes the zombies, and in a party only one set of waves spawns and everyone's quest completes.

Still to settle for later types: map markers on spawned enemies, and how bosses are made tougher.

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

**Status:** the tier 2 version is built as the wave system prototype (`QuestMaker/defense.py`); the other tiers and the infested variant follow once it has been playtested.

- **Generic, like vanilla:** any POI of the quest's tier that supports clear quests, with the existing tag-based POI picking. This replaces the POI-specific `*_clear_and_defend` quests and the hand-written `tier1`-`tier6_dementiveDefenseQuests` in `Config/quests.xml`.
- **Waves:** 3 at tiers 1-2, 4 at tiers 3-4, 5 at tiers 5-6 (the last with a boss). Gamestage-scaled, 15-second breaks with a warning, leaving fails the quest.
- **Infested variant:** one, at tiers 3 and up. Traders pick randomly from their quest list, so keeping the number of variants small is what keeps them from being spammy.
- **Large POIs:** zombies spawn just outside the POI's footprint, all around it, and head straight for the player. The wave time limit stops a huge building from stalling a wave. If that still plays badly on tier 5-6 POIs, the fallback is to spawn waves inside parts of the building that have already been cleared ("they're coming back in").

## Build and Defend

The trader hands you a supply kit, you go to a spot in the wilderness, build a defense against the clock, then survive the waves.

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

- Push-your-luck inside a single fight, where Contracts does it across several quests.
- **Site:** a random spot almost anywhere (wilderness, town, next to a POI), with the same distance rules as vanilla quests.
- **Build phase:** 5 minutes with a kit, like the other build quests.
- **Breaks:** about 30 seconds between waves, longer than in the other defense types. Walking out of the area during a break ends the stand and banks the reward. Leaving during a wave counts as fleeing and loses everything.
- **Payout:** grows with each wave survived, faster the longer you stay. Paid when you return to the trader.
- **Co-op:** each player banks their own reward. A player who dies loses theirs; the rest can keep going. Anyone can leave during a break and keep what they've earned.
- **Tiers:** 1-6. The tier sets the payout rate and how hard the first wave hits; after that, waves keep escalating with no cap.

## Blood Moon Bounty

A bounty for the next horde night, fought wherever you are (normally your own base). Bosses show up during the night; at higher tiers it becomes waves of bosses, each harder than the last.

- Gives the blood moon a goal and a payoff on top of surviving it.
- **Offered:** only in the 2 days before a blood moon, at most one per trader. No location; it happens wherever you are when the horde night starts.
- **Bosses by tier:** 1 boss at tiers 1-2; 2-3 bosses at tiers 3-4; at tiers 5-6 a wave of bosses roughly every hour through the night, each harder than the last. Bosses are tougher versions of their zombie types (like Bounty Hunt) and each drops a boss loot bag.
- **Winning:** kill every boss without dying. There is no deadline: horde nights often run into the next day, so bosses don't leave at dawn. Dying fails the bounty.
- **Co-op:** one shared set of bosses for the party, sized to the party. Everyone sharing the quest gets the reward; a member who dies fails their own bounty while the rest carry on.

## Contracts

An optional layer on top of every quest, vanilla ones included. Start a contract at a trader, and the quests you do next become a run of up to 5 stages where you gamble your rewards forward for a bigger payout. Inspired by the "gamble forward" and pick-one-of-three loop of roguelike games such as Orcs Must Die! Deathtrap.

- **Starting:** a trader dialog option. Players who never start a contract see no change.
- **Picking quests:** you pick each quest from the trader's normal quest list, exactly as usual. Any quest type counts.
- **Stages:** each quest completed during a contract is a stage. Its normal reward goes into the contract's pot instead of to you.
- **Quests don't know about contracts:** the contract layer only watches quests being completed, failed or abandoned. Quests are never changed by it and are balanced on their own.
- **Escalation:** at each stage the contract raises the player's own gamestage with a buff (the game's `GameStage` passive effect, which the player's gamestage already reads). Everything that spawns around that player gets tougher: quest sleepers, defense waves, wandering hordes, and blood moon hordes too. The buff ends with the contract.
- **Pick 1 of 3:** after each stage, the trader offers three random boons and you take one. Boons last until the contract ends and work for any quest type, for example +15% damage with every weapon, kills restore a little health, faster stamina regeneration, more loot in containers, or surviving one lethal hit per stage. Some are deals with a downside, like "+30% damage but -20% max health".
- **Gamble forward or cash out:** after each stage, take another quest to continue, or cash out at the trader and collect the pot. The pot grows by more than the sum of the quests' rewards, so pushing on pays.
- **Stage 5:** the last stage. A tough contract boss hunts the player down: it spawns near them at some point while their stage 5 quest is active, wherever they are, the same for every quest type (never inside a trader's area, where nothing can spawn). Finishing stage 5 ends the contract with the biggest payout.
- **Losing:** dying, failing a quest or abandoning a quest during a contract ends it, and the pot is lost.
- **Tier progress:** quests done on a contract count toward the trader's tier progress exactly like normal quests.
- **Every quest is treated the same:** same pot rules for every quest type.
- **Co-op:** every player has their own contract, pot and boons. A shared quest counts as a stage for each party member who is on a contract. If one member dies, only their own contract ends. A contract player's raised gamestage feeds into the party's gamestage the normal way the game combines party members.
- **Built in C#** in `QuestsExpanded.dll` (Harmony is already set up): hooks for quest completion and failure, player death and quest difficulty; trader dialog options for starting, picking boons and cashing out; and per-player contract state saved with the character and synced in multiplayer.

## Decided against

- **Restore Power by area:** too close to vanilla's restore power quests.
- **Hunting contracts** (kill N animals or zombies anywhere): boring.
- **Supply Requests** (hand over items from your inventory): trivial with a stockpile and a chore without one, and they didn't push players toward crafting. Replaced by Commissions.
- **Courier runs between traders:** awkward when the player hasn't found the other traders yet.
- **Eliminate Roaming Horde as its own quest type:** folded into Bounty Hunt as the horde variant.
- **Hand-picked POIs** for any of the new types.
- **Questlines tied to other mods** (e.g. quests rewarding Weapons Expanded weapons): every mod stays standalone.
- **Trader-assigned contract quests:** during a contract the player still picks quests from the normal list.
- **Cosmetic or gimmick quests** (random chaos events, big heads, supply drops, heists, timed clears, treasure trails): they didn't add anything new to how the game plays.
- **Supply Depot** (defend three caches at once): too close to the other defend quests.
- **Other systems pitched and not chosen:** Nemesis (zombies that kill you come back stronger), Outbreak (infestation spreading across POIs over days), Job Board (player-posted paid requests), Stranded (dropped far away, survive the trip back), Nest Purge (destroy zombie-spawning nests in a POI), Raid (multi-stage tier 6 set piece).

## Retiring POI-group quests

Once the new types are working, retire the 108 quests tied to specific POI groups (cabin, cave, gas station, farm, ... fetch, clear and clear-and-defend quests). They caused most of the Nexus complaints (long trips, missing markers, fetch quests at POIs that can't host them) and never worked well with POI packs like ZZTong's.

- **Keep** the 28 urban/rural tag quests. They pick from any POI with the right tags, so they also cover POI packs whose POIs are tagged.
- **Then retire** the ZZZTongPrefabs-QuestsExpanded variant, which only exists for ZZTong POI names, and the `GotoPOIDEM` objective (only used by the POI-group quests).
