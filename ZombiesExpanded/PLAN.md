# Zombies Expanded: plan

**Status: approved 2026-11-01; built 2026-11-01, not playtested.** README.md describes what's built, with exact numbers.
Champion rooms are the POI rooms whose sleeper volume spawns the game's "badass" groups. Not built yet: pile-ups and
playing dead (the experiments), the
Sprinter's sidestep (the dodge animation), the Bloater's and Brood's positioning, and throwing bodies further (the
game never reads a hit's impulse; only blades severing more on the kill was kept). The Volatile going for walls is
the game's own dig-when-unreachable behavior. Gear soak is per hit on what a piece covers, as written; scrap armor's
pads soak a quarter of a plate. Fat and bloated zombies never wear scrap armor (its rigid plate sank into their bellies). The Regenerator's
fungus grows on the upper back, not across the chest (zombies' chests differ too much: a patch there floated off slim
zombies and sank into the others). After the first playtest: Screechers fled for good and never attacked, so they now back off only for 6 s after the shriek; the brood sac is a fifth smaller; and a 15th mutation, the Lurker (the user's idea), only comes at you while nobody's looking until it's in a fight.

No new zombies. Everything works on whatever zombies are in the game, vanilla or from another mod. The goal is the
whole zombie experience: zombies that are individuals, notice you in believable ways, move and fight like a crowd,
react to where you hit them, sometimes carry a mutation or the gear they died in, and show the fight on their bodies.
It should play about as hard as vanilla: more varied, not more punishing.

## Rules everything follows

- **Any zombie:** features attach to every zombie the game spawns (any entity tagged `zombie`), including other mods'.
  Nothing edits a specific zombie class, so it stacks with zombie packs and NPC Core.
- **Close to vanilla balance:** every mutation and gear piece is a trade, a strength paid for with a weakness, so a
  mutated zombie is different, not harder, and gives the same XP. Features that only add difficulty (double tap,
  crowd pressure) are off unless the server picks the Brutal preset. The numbers get tuned in playtests.
- **Readable:** you can tell what a zombie will do by looking at or listening to it, before it does it.
- **Counterplay:** every threat has an answer.
- **Grounded:** rot, growths, scavenged gear, crowd behavior. No magic, and no markers or floating tags over zombies.
- **No stun-lock:** grabs, slows and stuns are short and followed by an immunity window.
- **Co-op:** the server decides everything that matters; each client only draws the looks and plays the sounds.
- **Everything can be switched off:** gameplay per server, looks and sounds per player.

## Presets

| Preset | What it is |
|---|---|
| Standard (default) | Everything below at the listed numbers, balanced to play about as hard as vanilla |
| Brutal | Adds double tap and crowd pressure, mutation and champion rates ×1.5, Alpha at +25% health |

## What works on which zombies

| Feature | Any zombie | Needs a standard skeleton (vanilla bone names, which most zombie packs share) |
|---|---|---|
| Everything gameplay: senses, movement, combat, mutation effects, strains, gear protection, champions | yes | |
| Looks and sounds: weathering, wounds, char and frost, eyeshine, voices, horde audio | yes | |
| Body reshaping; gear and growth models | | yes. Without the bones a zombie still gets the effect, shown by the overlay instead of a model |

Bosses (the `boss` tag, like the Demolisher) never get mutations, gear or strains, so scripted fights stay as
designed. Zombie animals (dogs, vultures) get the looks and sounds only.

## 1. Individuals

Every zombie rolls these when it spawns.

| What | How it varies |
|---|---|
| Size | 93% to 107% |
| Body | normal, gaunt, bulky, bloated or hunched, by reshaping the skeleton (heavy zombies skip gaunt and bloated) |
| Old injury | a third: a limp arm, a dragged foot, a lolled head or a twisted back, on one side, as a pose on top of the animation (no stat change) |
| Gait and speed | a walk style its body can use, speed ±8% (averaging vanilla) |
| Voice | groans, screams and footsteps pitched ±12%, so a horde sounds like a crowd, not one voice repeated |
| Weathering | by biome: mud and moss (forest), dust and sun-bleach (desert), frost rime (snow), soot (burnt forest), ash (wasteland); wet in the rain |
| Age | fresh and bloody to rotten and grimy |
| Temperament (hidden) | **Sluggish** (30%): notices you later, gives up sooner. **Normal** (50%). **Restless** (10%): wanders more, notices more. **Relentless** (10%): never gives up a chase and follows you into buildings |

Temperament uses the game's own sight, hearing, wander and chase-time values per zombie. The mix leans sluggish on
purpose, to pay for the sharper senses in section 2. It shows: sluggish zombies sway and droop, relentless ones lean
forward.

## 2. Senses

All on the server, built on the game's own stealth system (noise, light, sight), which zombies already use.

- **Sound carries:** gunshots, explosions and breaking blocks send zombies within range to the spot to look. The range
  follows loudness: pistols about 40 m, rifles 60, shotguns 50, explosions 80, a suppressor cuts it to 10. Vanilla
  mostly turns these sounds into "heat" for later spawns; here the zombies already nearby come.
- **Lights give you away at night:** a flashlight, headlamp or torch pointed at a zombie within 35 m makes it notice
  you. The game already counts how lit you are; this adds the beam. With eyeshine (section 7) it cuts both ways: your
  light shows you their eyes and shows them you.
- **Herd alert:** when a zombie spots you, others within 12 m that can see it turn toward you too.

## 3. Moving as a crowd

- **Surround:** zombies spread out to come at you from different sides instead of lining up. The game's zombie attack
  code already has this ("group circle"); no vanilla zombie turns it on.
- **Herds:** wandering zombies drift in loose packs that follow one zombie, instead of alone.
- **Lunge:** a zombie that has been within 3 m of a player backing away for 2 s gets a short burst of speed (once every
  6 s). Backpedal-and-swing still works, but not forever.
- **Dormant by day:** outdoors in daylight, some zombies stand swaying in place and notice you late. Days are for
  scavenging, nights are for hiding.
- **Pile-ups (experiment):** zombies crushed against a wall climb onto the ones in front. Cut if it looks or plays
  badly.

## 4. Where you hit them matters

- **Poise and stagger:** every zombie has poise (more for big and tough zombies). Damage drains it, heavy hits drain
  more, and when it runs out the zombie staggers (the game's own stumble). Sustained fire or a sledge can stop a
  charge; a pea shooter can't.
- **Legs:** a solid leg hit on a running zombie trips it. Crippled legs make it limp, as in vanilla.
- **Arms:** one arm crippled or gone means 30% less damage to you and to blocks; both gone and it can only bite (60%
  less).
- **Head:** helmets (section 6) aside, a heavy head hit that doesn't kill dazes it for a moment.
- **Downed zombies** (knocked down, or crawlers) take double melee damage.
- **Impact:** shotgun and big-caliber kills throw bodies further, explosions scatter them, blades sever limbs more
  often on the killing blow.
- **Playing dead (needs a test):** at night, a few outdoor zombies lie still among wrecks in the game's own sleeper
  poses and get up when you pass within 4 m. Cut if the poses don't work outside POIs.
- **Brutal only:**
  - **Double tap:** a zombie killed by a body shot has a 10% chance to go down without dying and get back up 3 to 6
    s later as a crawler. Not if the killing hit was to the head, or it burned or was blown up.
  - **Crowd pressure:** zombies piled against the same block hit it harder, +15% for each one beyond the first, up
    to +60%.

These mostly help a player who aims: poise, legs, arms, head and downed zombies all reward placing your hits.

## 5. Mutations

A mutation is a change a zombie spawns with, visible on its body. Each one makes it stronger one way and weaker
another, so a mutated zombie gives the same XP as a normal one; what changes is how you should fight it. Share of
zombies that carry one, by gamestage: 5% (below 30), 10% (30), 15% (60), 20% (100), 25% (150+). A zombie carries at
most one (champions more). Strains (section 8) decide which zombies get them.

| Mutation | From GS | Look | Stronger | Weaker | Answer |
|---|---|---|---|---|---|
| ~~Bloater~~ (removed 2026-11-03: its death cloud caught you unawares) | 0 | Swollen belly, pustule sacs on the back and shoulders, sloshing | On death bursts into a 3 m bile cloud for 5 s: nausea (blurred vision) and 2 damage/s | 25% slower. Killed by fire, the gas burns off harmlessly | Kill it at range, or with fire |
| Sprinter | 0 | Pulsing red veins, panting | Runs at feral speed even by day | 40% less health; after 8 s of running it doubles over for 3 s | Sidestep and punish the stagger |
| Spiked | 30 | Bone spurs from the spine, shoulders and forearms | 25% of its hits make you bleed; every melee hit on it scratches you for 3, except spears | Brittle: 50% more damage from blunt hits; attacks 20% slower | A club ends it fast but costs scratches; or guns, bows, spears |
| Grabber | 30 | Long gnarled hands | 20% per hit to grab you for 2 s: no sprint or jump, 80% slower. Any hit on it, yours or a teammate's, breaks the grab; then 8 s immune | Its hits do 30% less damage; 20% slower | Keep distance, keep a melee weapon ready |
| Screecher | 40 | Torn hanging jaw, swollen throat sacs | Shrieks the first time it sees you: every zombie within 25 m comes to where you are. Calls no new zombies | Half health; its hits do half damage | Kill it before it sees you |
| Frostbitten (snow only) | 40 | Frost rime, icicles | Hits chill you (20% slower, half stamina regen, 6 s, stacks twice); immune to cold | 50% more fire damage; 15% slower | Fire |
| Smoldering (burnt forest only) | 40 | Charred, glowing cracks, smoke and embers | Immune to fire; its hits set you on fire; on death it bursts into flame (2 m) | 30% less health | Range. Kill it in a crowd and its burst sets the others on fire |
| Leaper | 50 | Wiry and hunched, long claws | Leaps 4 to 8 m at you (the spider's leap) | 30% less health; if the leap misses, it stumbles for 2 s | Sidestep the leap |
| Regenerator | 60 | Pale fungal growths, spore puffs | Heals 2% of its health per second once it hasn't been hit for 3 s | 30% slower; fire stops the healing for 10 s and does 50% more | Fire, steady damage |
| Toxic | 75 | Green glowing veins, dripping ooze | Its hits poison you (2/s for 6 s); melee hits on it splash you with acid (3) | 25% less health | Range |
| Volatile | 75 | A dented propane tank ratchet-strapped to its chest, hissing | If its chest takes 60 damage or it catches fire, the tank blows 1.5 s later: 4 m, 60 to players, 300 to zombies, some to blocks | 10% slower; a headshot kill just drops the tank | Headshot it, or shoot the chest when it's in a crowd and away from you |
| Hulking | 90 | 15% bigger, broad shoulders and arms | Double health and poise; knocks you back 1.5 m; 50% more block damage | Never runs; 50% more damage from headshots | Headshots; crippling a leg drops it for 4 s |
| Stalker | 100 | Dark and matte, no eyeshine | Silent; crouch-walks while you're not looking at it. Within 8 m, or once you look at it, it stands and sprints | 40% less health | Check behind you; light on it |
| Brood | 120 | A writhing sac on its belly | On death two weak crawlers (half a crawler's health) burst out | 40% less health; 20% slower. A fire or explosion kill burns the brood | Fire, explosives |

## 6. Gear they died in

From gamestage 20, a zombie has a 15% chance (25% from 100) to wear protective gear. Vanilla zombies pick gear that
fits their job (cops get riot helmets, bikers motorcycle helmets); any other zombie picks from the whole pool. Gear
soaks damage on the part it covers until it breaks, then it's knocked off with a clank and falls as a physics prop
(gone after 30 s). Body armor is heavy, so wearers are slower. Blunt hits wear gear 50% faster, armor-piercing
rounds go through it, explosions strip it.

| Gear | Covers | Soaks | Trade |
|---|---|---|---|
| Hard hat | head | 30 | none |
| Welding mask | head | 40 | can't see well: notices you 30% later |
| Football helmet | head | 60 | none |
| Motorcycle helmet | head | 80 | hears you 30% later |
| Riot helmet with visor | head | 100 | hears you 30% later |
| Military helmet (not on zombies whose model already wears one) | head | 100 | none |
| Kevlar vest | chest, half of each hit | 150 | 10% slower |
| Scrap armor (rare, from gamestage 100): road-sign chest plate, hubcap shoulders, car-door back plate, wired on | chest, 60% of each hit; plates break off one by one | 250 | 20% slower |

## 7. The fight shows on them

- **Wounds stay where you hit:** holes from bullets and arrows, gashes from blades, up to 12 per zombie, moving with
  the body.
- **Badly hurt zombies drip blood** (below a third of their health), so you can follow one that got away.
- **Fire chars them** (glowing embers while they burn), **cold frosts them**, **shocks scorch them.** It fades slowly.
- **Eyeshine:** in the dark, zombies' eyes catch your flashlight, headlamp or torch. You see pairs of eyes before you
  see bodies.

All of this is drawn as an extra layer over the zombie's own material (tested on vanilla zombies:
`unity/Build/look-test.png`), so it works whatever shader another mod's zombie uses.

## 8. Strains

Instead of mutations landing on random zombies one by one, zombies that spawn together share one: a strain. A fight
gets a theme you can read and answer.

- **A group** is zombies spawned together: a wandering horde, a screamer's horde, the zombies of one sleeper room in
  a POI, one Blood Moon wave around a player, or a biome spawn batch.
- **Each group rolls whether it carries a strain**, at twice the mutation share for its gamestage (30% of groups at
  gamestage 60, where the share is 15%). A strain group picks one mutation the gamestage has unlocked (Frostbitten and
  Smoldering only in their biomes), and **half its zombies carry it**. The other groups have no mutated zombies at
  all. The total comes out the same as rolling each zombie alone; the mutated ones are just bunched up.
- **From gamestage 100 a strain can pair two mutations** that work together: Screechers with Sprinters (one calls, the
  others come running), Grabbers with Toxics (held while poisoned), Bloaters with Brood, Stalkers with Leapers.
- **Zombies that spawn alone** roll on their own at the mutation share.
- A **champion** in a strain group carries the strain's mutation plus its own.

Example, gamestage 60: you clear a house. Upstairs, the room is a Toxic strain: two of its four zombies drip green
and splash acid when you melee them, so you switch to the bow for that room. The next room is plain.

## 9. Atmosphere

- **Horde audio:** when a lot of zombies are close, you hear a distant crowd moan from their direction, built from the
  game's own zombie voices. It follows the real count and direction, so you learn to read it.

## 10. Champions and the Blood Moon Alpha

These are the only zombies meant to be harder than vanilla's, and they pay for it.

- **Champions:** from gamestage 50, 1% of zombies (2% from 150), whatever kind they are. Two mutations (three from
  150), 15% bigger, triple health, poise and XP, and a name built from its mutations ("Earl the Bloater"). While it's
  after you or you've hit it, a bar with its name and health shows at the top of the screen (the game's own boss bar).
  It always drops a strong loot bag.
- **Champion rooms:** the last sleeper room of a POI (where the loot is) has a 25% chance to hold a champion.
- **Blood Moon Alpha:** one per Blood Moon for each group of players, picked from the horde's own zombies. Hulking
  plus two mutations, five times the health. While it lives, zombies within 20 m are 10% faster; when it dies, they
  all stumble. It drops two strong loot bags.

## 11. Learning them

The first time each player meets a mutation, a piece of gear or a champion, a short tip pops up (the game's own tip
window): what it is, how to spot it and what works against it. Each tip shows once per player.

## 12. How they think

Each mutation gets its own behavior, written as new AI tasks in the same task system vanilla zombies run. The mod
adds them to each zombie on the server when it spawns, alongside its normal tasks, so other mods' AI edits (NPC Core)
stay. Behaviors only use animations every zombie already has (walk, run, crouch-walk, stumble, scream, jump, eat,
dodge), so they work on any zombie with the standard animation controller. A zombie from a mod that runs a different
AI system gets the mutation's effects but not its behavior. The AI makes them smarter, not stronger: the trades in
section 5 stand.

| Mutation | Behavior |
|---|---|
| Sprinter | Hunts in bursts: sprints at you from an angle, and after catching its breath circles to a new side instead of walking straight in. Sidesteps when you aim at it (the game's unused dodge, if the animation plays on zombies) |
| Screecher | Hangs back 10 to 15 m behind other zombies, shrieks, and backs away when you come for it, keeping the pack between you |
| Stalker | Shadows you out of your line of sight: freezes when you turn, moves when you turn away, waits beside doorways in POIs, and strikes while you're fighting something else or looting |
| Leaper | Holds 6 to 8 m off and circles for a clear line, then leaps. If you back off, it repositions for another leap rather than running in |
| Grabber | Opportunist: hangs at the edge of a fight and goes for whoever is busy with another zombie, or the player furthest from teammates |
| Hulking | Breacher: smashes through blocks in its way instead of going around, and leads its group into your wall. Across open ground it shoulder-charges (a short sprint that knocks you back) |
| Regenerator | Below 40% health it retreats out of sight to heal, then comes back. Burning it stops the healing, so it doesn't bother hiding |
| Bloater | Shambles to the front of its group, into close quarters |
| Volatile | When it can't reach you, it goes for your walls and doors, so the tank becomes a decision at your base |
| Brood | Keeps to the back and the dark |
| Spiked, Toxic, Frostbitten, Smoldering | Plain brawlers: their threat is up close, so they just come at you |

**Groups:**
- **Strain packs work together:** they share a target. Some come straight at you while others circle around; callers
  hang back, and opportunists wait for you to commit.
- **Herds follow a leader** (usually the biggest). Kill it and the herd loses its cohesion and mills around for a few
  seconds.
- **Searching:** a zombie that loses you searches where it last saw you, spreading out to check nearby rooms and
  corners, before giving up. Its temperament sets how long.
- **Champions** use their mutations' behaviors and, once, when badly hurt, roar to pull nearby zombies to them.
- **The Alpha** holds back behind its horde at first and sends it in with roars (short speed pulses). It steps in when
  half the wave is dead or a wall is close to breaking.

**Tools for tuning:** a console command spawns a zombie with a chosen mutation, temperament, gear or strain, and an
optional debug readout (off by default) shows what each zombie is doing.

## Settings

- **Server** (XML in `Config`, plus a console command): the preset (Standard or Brutal) and each feature on or off
  with its rates.
- **Each player**, through Gears if installed: weathering, wounds, eyeshine, voices, horde audio, blood drips and tips.

## How it's built

- **C# DLL and a model bundle**, like Traps Expanded: install on the server and every client, EAC off.
- **Server:**
  - Rolls each zombie when it spawns, through vanilla's own spawn-modifier hook, which every spawn goes through,
    modded zombies included.
  - Groups zombies for strains through the spawners: wandering horde, scouts, sleeper volume, Blood Moon and biome.
  - Runs senses, movement, combat, mutations and gear.
  - Remembers each zombie's roll across saves (the game doesn't save buffs on zombies).
- **Clients:**
  - A buff tells each client what the zombie is.
  - A small component draws the models, overlay and eyes and sets the voice pitch.
  - Zombies that come into view late still get their look, because buffs are resent every few seconds.
- **Models:** Blender scripts with the same baked, photo-textured pipeline as the traps. Rigid pieces are bolted to
  bones: helmets, vests, plates, the tank, spurs, growths and claws. About 18 models.
- **Overlay:** one shader drawn as an extra layer on the zombie's own mesh, driven per zombie (no texture copies).
- **Cost:** one extra draw per zombie, a few small models, light server checks a few times a second per zombie.

## Build order

1. **Core and individuals:** spawn roll, sync and save, size, body, gait, voice, temperament; the spawn command and
   AI debug readout.
2. **Looks:** overlay (weathering, wounds, fire and frost, blood drips), eyeshine.
3. **Senses and the crowd:** sound, light, herd alert, surround, herds with leaders, lunge, dormant by day, searching.
4. **Where you hit them:** poise, legs, arms, head, downed, impact; double tap and crowd pressure for Brutal.
5. **Mutations without new models, with their behaviors, and strain packs:** Sprinter, Screecher, Hulking, Stalker,
   Toxic, Frostbitten, Smoldering.
6. **Mutations with models, with their behaviors:** Bloater, Spiked, Grabber, Leaper, Regenerator, Volatile, Brood.
7. **Gear** with knock-off.
8. **Champions, champion rooms and the Alpha** with their behaviors, the boss bar, loot.
9. **Horde audio and tips.** Then the experiments: pile-ups, playing dead.

## Proven so far

- Every vanilla zombie shares one humanoid rig and one animation controller, with the same bone names: models can be
  bolted to the same bones on every zombie.
- The overlay draws over vanilla zombies with no flicker (charring with embers, frost, glowing veins, grime and wet,
  wounds). The masks are still rough.
- Reshaping the skeleton gives bulky, gaunt, bloated and hunched bodies (`unity/Build/body-test.png`). Still to check
  in game: that the animator leaves the bone scale alone.
- Every hit reports the body part, the direction and the bone that was hit: enough for gear, the Volatile tank,
  wounds and the hit-location rules.
- The game already shifts sound pitch per source (it does it for players), which is what the voices need.
- Zombie AI already reads the player's light level, has a "group circle" spread in its attack code, and has
  investigate-a-spot and rage calls a mod can use.

Needs a check in game before relying on it: surround, the flashlight beam check, Stalker's crouch-walk, the Leaper's
leap on other bodies, the dodge animation on zombies, retreat and search paths in POIs, pile-ups, playing dead, and
(Brutal) double tap's fake death.

Decided against:
- New zombie types, including the unused vanilla models (Frostclaw, Plague Spitter, Sand and Snow zombies, Radiated
  Crawler) and zombies built on vanilla bodies (Riot Cop, Firefighter, Miner).
- Blood scent (zombies tracking bleeding players).
- Lingering corpses.
- After the first playtest: the Howler (a pack leader that makes zombies flank you), the Risen (dead players rise as
  named zombies), an adaptive horde (more of whatever counters how you kill), Blood Moon pile-ups and roaming
  mega-herds.

---

# Round 2: more mutations (approved and built 2026-11-01, not playtested)

The first playtest liked the mutations that each do one readable thing (the Lurker). This round adds more of those.
Same rules as before: any zombie, a strength paid for by a weakness, unchanged XP, works in co-op. Mostly played solo
on hardcore, so each one is pitched for a solo game first.

## Liked, with numbers to approve

**Approved to build:** Possum, Snatcher and the Shield-bearer, with the numbers below. **Dropped:** Climber and
Burrower ("might make things not fun").

| Mutation | From | Stronger | Weaker | How it's built |
|---|---|---|---|---|
| **Possum** | 40 | Plays dead. The first time a hit would kill it, or takes it below a third of its health, it drops as if dead (one of the game's lying sleeper poses): eyes dark, silent, a quarter of its health left. It gets up and lunges when a player comes within 2.5 m or turns their back on it within 8 m. One in four Possums spawn lying "dead" outdoors. | 25% less health. Its fake death gives no XP pop-up, which is the tell. | Sleeper pose and wake calls from the game's sleeper code; the Lurker's gaze check |
| **Climber** | 50 | Climbs sheer walls like the spider zombie, so a wall doesn't stop it: it comes over the top and onto roofs. | 40% less health, 30% less block damage (it climbs instead of breaking). Takes fall damage as normal. Always gaunt, with bloodied hands. | The game's own vertical-climb pathing (`bCanClimbVertical`, read each time a path is made) |
| **Burrower** (experimental) | 70 | With a target 10 to 40 m off on open ground, it digs in and travels unseen underground toward you; a dirt trail and a rumble on the surface show where. It bursts up beside you. It can't come up through blocks players placed, so floored bases stay safe and open yards don't. | 30% less health; dazed for 2 s after it surfaces. | Its model hidden while it travels on the server, its own dirt trail and burst effects. Prototype first. If it can't travel underground cleanly, it becomes a trapdoor ambusher: it digs in where it stands and bursts up when you walk over it. |

**Shield-bearer** (gear, from gamestage 40): a shield on its left forearm takes all of a hit from the front on the
head, torso or left arm until it breaks, then falls off as a prop. Legs, back and right side stay open.
- **Car door** (any zombie): soak 120.
- **Riot shield** (cops, soldiers): soak 200. Dark and tinted, since the game's model shader can't do see-through.
- **Cost:** 15% slower and attacks 20% slower, with one arm busy.
- **Other rules:** the same as all gear (blunt wears it faster, armor-piercing goes through, explosions strip it).
- **Models:** two new ones.

**Snatcher** (from gamestage 30, rare: a quarter as common as other mutations, and never more than one near a
player at a time): a thief that never fights.
- **The grab:** it never attacks. It comes at you fast and quiet, grabs whatever is in your hand (a weapon, a tool,
  food: the held toolbelt slot) with a screech, and runs off at a sprint, by day or night, ducking out of your sight
  the way the Lurker does.
- **Never stolen:** armor and the backpack.
- **Empty hands:** if you're holding nothing, it hangs around at a distance and waits for you to take something out.
- **Getting it back:** kill it before it gets away and it drops your item. If it gets away (60 m off, or out of sight
  for 20 s), it's gone for good, and so is your item.
- **Weakness:** half health, no attack at all.
- **Look:** a burlap sack slung over its shoulder that bulges when it's carrying something (one new model).
- **Co-op:** it steals from the player it reaches, and anyone can kill it to get the item back.
- **Engine:** each player's inventory lives on their own game. The grab is a message to that game, which takes the
  held item out and hands it to the server to carry. That works the same in solo and co-op.

## Grounded ideas, batch 3

Things real zombies in fiction do, with no gimmicks. Most apply to every zombie, a few to some.

- **Feeding:** a zombie that kills an animal, or comes across a fresh kill, kneels over it and feeds for 20 to 40 s.
  While feeding it's distracted (half sight and hearing): a chance to sneak past or line up a sneak attack. Engine:
  the kneel the Sprinter's exhaustion uses.
- **Hunting wildlife:** zombies go after the animals they come across (deer, rabbits, chickens, pigs; not wolves or
  bears, which fight back), then feed on them. The wilds look like something lives in them. Engine: a target task for
  animals, below players in priority.
- **Waiting outside:** a zombie that loses you at a building doesn't just search and wander off. It hangs around
  outside the door or window where it last saw you, groaning, for up to an in-game hour, and zombies passing by join
  it. Getting back out means dealing with them.
- **Falls break legs:** a zombie that falls more than 4 m breaks a leg and crawls: off roofs, knocked off your walls,
  out of upper windows, a Climber that loses its grip. Height and drops in your base design pay off.
- **Weather and dark:** rain halves how far they hear you, fog and storms cut how far they see, and deep snow and mud
  slow them. At night they see less far but hear farther. Weather starts to matter in a fight.
- **Trip and fall:** running zombies sometimes trip over low obstacles (a step, rubble, a low wall, a downed zombie)
  and go sprawling. Running hordes look less robotic, and a line of rubble in front of your door slows a rush.
- **Ankle grabs:** crawlers and knocked-down zombies grab at your legs when you pass within reach: half speed for a
  second. Crawlers become something you step around, not just ignore.
- **Sleepers stir:** sleeping zombies in POIs stir before they wake (a twitch, a groan, the head turning), which gives
  a stealth player a beat of warning.
- **Fresh and rotten:** the age every zombie already has (it shows in its look) starts to matter. Fresh ones are
  faster; rotten ones are slower but their limbs come off more easily. You can read it from how they look.

## Decided against in round 2

Remnant (opens doors, climbs ladders), Berserker, Spitter, Carrier, Dustborn and Shrapnel (biome mutations),
Backpacker and firefighter gear, burning panic, headless flailing. Batch 2: Pitcher, Mimic, Copycat, Shade, Knocker,
Hitchhiker, Flicker, Ventriloquist, Vandal. The Snatcher's hidden stash (it just leaves with your item). Batch 3, all
of it: feeding, hunting wildlife, waiting outside, falls break legs, weather and dark, trip and fall, ankle grabs,
sleepers stir, fresh and rotten.

---

# Round 3: variety (approved and built 2026-11-01, not playtested)

**After the review** (the user marked each model on a gallery page): cut the bandana, baseball cap, beanie, dust mask,
fanny pack, handcuffs, head bandage, hi-vis vest, IV line, lanyard, leg cast, messenger bag, neck brace, surgical mask,
tool belt and wristwatch, plus the hard hat, scrap armor and the Frostbitten's icicles (the frost look on its skin stays). The
Kevlar vest only goes on regular builds (it rode up on fat zombies and sank into female ones). Being reworked:
the pustules (edges that blend, a more varied pattern, variant clusters), the fungus, a bigger bear trap, barbed wire
that can also turn up on a leg or the waist, and a narrower cowboy hat.
After a second look at the renders: cut the cowboy hat, the football and military helmets and the Kevlar vest too. Gear
left: welding mask, motorcycle and riot helmets, car door and riot shield.

More of what already works: small models bolted onto any zombie, like the gear and growths, so no two zombies look
alike. A bigger visual round (deep wounds, blood decals in the world, gore chunks, new fire, clothing recolors,
footprints) was too large and complicated; it's dropped.

## Remnants

Small props that tell who a zombie was and how it died. About half of all zombies carry one, and a few carry two.
They're picked to fit the zombie's job (vanilla zombies), or from everything for other mods' zombies. They're
cosmetic, except the bear trap. Everyone sees the same ones, since they're part of the zombie's profile.

**Stuck in them:**
- **Arrows and bolts:** one to three arrows in the back, chest or thigh, or a crossbow bolt through the shoulder.
- **Blades and tools:** a kitchen knife in the shoulder, a screwdriver in the neck, an axe in the back, a machete in
  the skull, a snapped-off pitchfork in the back.
- **Rebar:** a length of it through the chest, poking out the back.
- **Glass:** shards in the face and arms.
- **Bear trap:** clamped on an ankle. It limps, 15% slower.
- **Barbed wire:** wrapped round an arm.
- **Noose:** a cut rope round the neck.

**Worn and carried:**
- **Hospital:** head bandage, arm sling, leg cast, neck brace, hospital wristband, an IV line taped to the arm.
- **Face:** cracked glasses, sunglasses, headphones round the neck, a surgical or dust mask, a gas mask hanging at the
  neck.
- **Headwear** (only zombies without their own): baseball cap, beanie, bandana, cowboy hat.
- **Work:** lanyard and ID badge, hi-vis vest, tool belt.
- **Law:** handcuffs dangling from a wrist, an ankle monitor.
- **Personal:** purse strap or messenger bag, fanny pack, wristwatch, chain necklace.

Seasonal pieces (masks at Halloween, Santa hats) were dropped.

**The approved list** (36 models; the arm sling became a cast, since a sling can't hold an animated arm):
- **Stuck in:** Arrows, CrossbowBolt, KitchenKnife, Screwdriver, Axe, Machete, Pitchfork, Rebar, GlassShards,
  BearTrap, BarbedWire, Noose.
- **Hospital:** HeadBandage, ArmCast, LegCast, NeckBrace, IVLine (with a hospital wristband).
- **Face and neck:** CrackedGlasses, Sunglasses, Headphones, SurgicalMask, DustMask, GasMask.
- **Headwear:** BaseballCap, Beanie, Bandana, CowboyHat.
- **Personal, work and law:** ChainNecklace, Wristwatch, Lanyard, HiVisVest, ToolBelt, MessengerBag, FannyPack,
  Handcuffs, AnkleMonitor.

## Models for the round-2 mutations

- **Snatcher:** its burlap sack.
- **Shield-bearer:** the car door and the riot shield.

## How it's built

The same pipeline as the gear and growths: one Blender script per model, bolted to bones, checked on Joe, the fat cop
and the nurse before it goes in. That's about 35 remnants plus 6 mutation models. They're built in batches by
parallel agents, starting with the ones that show most (things stuck in them, hospital, headwear).

---

# Round 5: personality (approved 2026-11-03, building)

After playtesting, the user said the variety "makes a huge difference": the Sunglasses and the lumberjack's Axe were
favorites, and they asked for more that gives each zombie its own flavor. From the pitch they picked gore, things that
move and rare showpieces, plus "a whole bunch of interesting and fun sunglasses or other types of glasses or
accessories like that". Not chosen: lights in the dark (a taped flashlight, a road flare, glow sticks, a ringing phone)
and painted survivors' marks.

- **Eyewear and accessories** (everyday remnants): Aviators, RoundShades, TapedGlasses, Glasses3D, StarShades,
  HeartShades, ShutterShades, SkiGoggles, EyePatch, WeldingGoggles; Cigar (a new Mouth slot, so it goes with glasses),
  MardiGrasBeads, FlowerLei, BowTie, DogTags. Added to the vanilla jobs they fit.
- **How they died** (everyday remnants): CompoundFracture, GutLoop, ExposedRibs, ExposedSpine, TurningBite,
  ChewedCalf.
- **Showpieces** (their own roll, 2.5% of zombies): StopSign, CinderBlock (dragged on the ground by ZedDrag, 20%
  slower), Harpoon, Pincushion, Bumper.
- **Things that move** (ZedLife, ZedSwing; looks only): flies and the game's `flies_lp` loop round zombies whose age
  is past 0.85, within 18 m; breath puffs every few seconds in the snow or below 40 F; a spatter from the jaw as an
  attack starts; parts named `...Swing` swing about their pivot (dog tags, gut loop, the noose's rope end, the padlock
  chain's torn length, the harpoon's rope).

Model specs are in `blender/REMNANTS.md` (Round 5).

**Glows removed (2026-11-03).** The user found the Sprinter's red glowing veins "horrible" at night and asked to get
rid of anything like it (after the Bloater's yellow vein lines earlier). The overlay's whole vein layer (the Sprinter's
red and the Toxic's green, lines and glow) and its embers (the glowing cracks on Smoldering and burning zombies) are
gone, and with them the overlay's additive glow pass. Smoldering and burning zombies still char black. The Sprinter
and the Toxic no longer have a look of their own. Don't bring back glowing skin, veins or cracks.

