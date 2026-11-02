# Zombies Expanded

Every zombie in the game, vanilla or from another mod, becomes an individual. It gets its own body, voice,
temperament and weathering, senses that react to your noise and your light, and wounds that stay where you hit it.
It may carry a mutation or the gear it died in, and now and then it's a named champion. No new zombie types. Balanced
to play about as hard as vanilla: mutations and gear trade a strength for a weakness. The design is in PLAN.md.

Has a DLL and a model bundle, so it has to be installed on the server and on every client, with EAC off. Settings
are in `Settings.xml`.

## Every zombie

| | |
|---|---|
| Size | 93% to 107% |
| Body | Normal, gaunt, bulky, bloated or hunched, by reshaping its skeleton (heavy zombies are never gaunt or bloated). Needs the standard zombie skeleton, which most zombie packs share |
| Walk | Half of them get another walk style their body can use |
| Speed | ±8% |
| Voice | Groans, screams and footsteps pitched ±12%, so a crowd doesn't sound like one voice |
| Temperament (hidden) | Sluggish (30%): notices you later, gives up sooner, droops and sways. Normal (50%). Restless (10%): wanders more, notices more. Relentless (10%): keeps chasing four times as long, leans forward |

**Looks** (drawn over the zombie's own material, so they work whatever shader it uses; each player's choice):
weathering by biome (mud, dust and sun-bleach, frost rime, soot, ash) settling on what faces up; fresh or rotten; wet
in the rain; wounds where you hit, moving with the body; charring with glowing cracks while it burns; frost from cold;
blood dripping below a third of its health; eyes that catch your flashlight in the dark.

**Senses:** a player's gunshots, explosions and breaking blocks send zombies within range (from about 40 m for a pistol
to 80 for explosions; a suppressor is too quiet) to look. At night, a flashlight pointed at a zombie within 35 m gives
you away. When a zombie spots you, up to six others within 12 m that can see it turn too. A zombie that loses you
searches nearby for a while (longer if relentless).

**The crowd:** zombies attacking together spread around you (the game's own "group circle", unused by vanilla zombies).
Zombies that spawned together keep near their biggest member, and mill about for a few seconds if it dies. A zombie
whose target keeps backing away within 3 m for 2 s gets a short burst of speed (once every 6 s). Outdoors by day, 30%
of the non-restless zombies doze: half sight, no wandering.

**Where you hit them:** each zombie has poise (a third of its health, 60 to 400, double for big ones) that hits
drain (blunt and shotgun hits more) and that refills 2 s after the last hit; when it runs out the zombie stumbles. A
solid leg hit trips a runner; a heavy head hit dazes. Knocked-down zombies and crawlers take double melee damage.
Missing one arm, a zombie hits you and blocks 30% softer; with both gone, 60% (75% on blocks). Blades sever limbs
more often on the killing blow.

## Mutations

Share of zombies that carry one: 5% below gamestage 30, then 10%, 15% (60), 20% (100), 25% (150). Zombies that spawn
together share a strain: some groups carry one, and then half of the group has it (pairs from gamestage 100); other groups
have none. The total matches rolling each zombie alone.

| Mutation | From | Stronger | Weaker | Behavior |
|---|---|---|---|---|
| Bloater | 0 | Bursts into a 3 m bile cloud on death (nausea: blur, 2 damage/s) | 25% slower; a burning kill burns the gas off | |
| Sprinter | 0 | Runs fast even by day | 40% less health; doubles over for 3 s after 8 s of running | |
| Spiked | 30 | 25% of its hits make you bleed; melee hits on it scratch you (3, 20% bleed) except reach weapons | 50% more damage from blunt hits; attacks 20% slower | |
| Grabber | 30 | 20% per hit to hold you 2 s (no sprint or jump, 80% slower); any hit on it frees you; 8 s immunity after | 30% less damage, 20% slower | Goes for the player with the most zombies on them |
| Screecher | 40 | Shrieks the first time it has a target: every zombie within 25 m comes | Half health, half damage | Backs off for 6 s after its shriek while they come (cut short if it's hit or cornered), then attacks |
| Frostbitten (snow) | 40 | Its hits chill (20% slower, half stamina regen, 6 s, stacks twice); cold doesn't hurt it | 50% more fire damage, 15% slower | |
| Smoldering (burnt forest) | 40 | Fire doesn't hurt it; its hits set you on fire; flares on death (2 m) | 30% less health | |
| Possum | 40 | Plays dead: the first hit that would kill it, or take it below a third of its health, drops it as if dead instead, on a quarter of its health. Silent, eyes dark. One in four that spawn in the open start out lying "dead" | 25% less health; no XP pop-up when it "dies" (the tell) | After lying still 5 s, it gets up and lunges at a player within 2.5 m, or within 8 m with their back to it, or at whoever hits it |
| Leaper | 50 | Leaps at you (the spider's leap) | 30% less health | |
| Regenerator | 60 | Heals 2% of its health a second, 3 s after it was last hit | 30% slower; fire stops the healing and does 50% more | Runs off below 40% health to heal |
| Toxic | 75 | Its hits poison (2/s for 6 s); melee hits on it splash you with acid (3) | 25% less health | |
| Volatile | 75 | A propane tank on its chest: 60 damage to the chest or any fire, and it blows 1.5 s later (4 m; 60 to players, 300 to zombies, some to blocks) | 10% slower; a kill before that just drops the tank | |
| Lurker | 80 | Comes at you a third faster while nobody's looking at it; hunched, eyes that always catch the light | 30% less health | Until it's in a fight, runs when any player looks at it (from 25 m off it stands and stares) and comes again when they look away. Within 2.5 m of you, hitting or hit, or cornered, it fights like any zombie |
| Hulking | 90 | 15% bigger, double health and poise, 50% more block damage, knocks you back | Never runs; 50% more damage from headshots; crippling a leg drops it for 4 s | Charges across open ground (a short sprint) |
| Stalker | 100 | Silent until seen | 40% less health | Creeps up crouched behind you, freezing while you look at it; watched for 1.5 s or within 8 m, it stands and sprints |
| Brood | 120 | Two weak crawlers burst out on death (not from a fire or explosion kill) | 40% less health, 20% slower | |

**Snatcher** (from gamestage 30, rare: about one in 300 zombies at gamestage 60, never more than one within 80 m):
a thief with a sack on its back that never fights. It comes at you fast (faster by day) and grabs whatever is in your
hand (a weapon, a tool, food; never armor or the backpack), then runs. Kill it and it drops your item; if it gets 60 m
from everyone, or stays out of everyone's sight for 20 s, it's gone, and so is the item. If you're holding nothing it
hangs about 5 to 9 m off, waiting. Half health, no attack, never breaks blocks.

A mutated zombie gives the same XP as a normal one. Models never pile onto the same spot: a zombie with a growth on
its back gets no axe in it, a helmet and a cap never meet.

## Gear

From gamestage 20, 15% of zombies (25% from 100) wear gear that fits their job (vanilla zombies) or anything (other
zombies); zombies whose model already wears a hat or helmet get no helmet, and fat or bloated ones no scrap armor. Gear takes its share of each hit on what it
covers until its soak runs out, then it's knocked off as a tumbling prop. Blunt hits wear it 50% faster,
armor-piercing rounds go through, explosions strip it.

| Gear | Covers | Takes | Soak | Cost |
|---|---|---|---|---|
| Hard hat | head | all | 30 | |
| Welding mask | head | all | 40 | sees 30% less far |
| Football helmet | head | all | 60 | |
| Motorcycle helmet | head | all | 80 | hears 30% less far |
| Riot helmet | head | all | 100 | hears 30% less far |
| Military helmet | head | all | 100 | |
| Kevlar vest | chest | half | 150 | 10% slower |
| Scrap armor | chest plate (front), back plate (back), two shoulder pads; each breaks on its own | 60% | 250 a plate, 62 a pad | 20% slower |
| Car door (from 40) | a shield on the left arm: head, torso and left arm, from the front only | all | 120 | 15% slower, attacks 20% slower |
| Riot shield (from 40; cops, soldiers) | the same | all | 200 | 15% slower, attacks 20% slower |

## Remnants

About half of all zombies carry a prop that tells who they were and how they died, a fifth of those two: one that
fits the job for vanilla zombies (a nurse's surgical mask or IV line, an inmate's handcuffs or ankle monitor, a
worker's hi-vis vest or tool belt, a rancher's pitchfork in the back), otherwise one anyone might have; other mods'
zombies pick from everything. Hats and anything on top of the head only go on zombies with no hat of their own. They're
cosmetic, except the bear trap: a zombie with one clamped on its ankle limps (15% slower).

- **Stuck in them:** arrows, a crossbow bolt, a kitchen knife, a screwdriver, an axe, a machete, a snapped pitchfork,
  rebar through the chest, glass shards, a bear trap, barbed wire, a cut noose.
- **Hospital:** head bandage, arm cast, leg cast, neck brace, IV line.
- **Face and neck:** cracked glasses, sunglasses, headphones, surgical mask, dust mask, gas mask.
- **Headwear:** baseball cap, beanie, bandana, cowboy hat.
- **Personal, work and law:** chain necklace, wristwatch, lanyard, hi-vis vest, tool belt, messenger bag, fanny pack,
  handcuffs, ankle monitor.

## Champions and the Alpha

- **Champions:** from gamestage 50, 1% of zombies (2% from 150). Two mutations (three from 150), 15% bigger, triple
  health and XP, a name ("Earl the Bloater"). Once, below 30% health, it roars and pulls nearby zombies in. A bar with
  its name and health shows at the top of the screen while it's after you or for 20 s after you hit it. Drops a strong
  loot bag.
- **Champion rooms:** a POI's final room (where the game puts its "badass" sleepers) has a 25% chance that its first
  zombie is a champion.
- **Blood Moon Alpha:** the first zombie of each Blood Moon near each party (or lone player). Hulking plus two
  mutations, 20% bigger, five times the health and XP. It holds back at half speed for its first 45 s (unless hurt),
  then every 20 s roars and the zombies within 20 m surge for 3 s; zombies within 20 m are 10% faster while it lives,
  and all of them stumble when it dies. Drops two strong loot bags.

## Brutal

`Preset` Brutal in Settings.xml: mutation and champion rates ×1.5, plus double tap (a body-shot kill has a 10% chance to
go down without dying and get up 3 to 6 s later as a crawler) and crowd pressure (each zombie breaking blocks next to
another adds 15% block damage, up to 60%).

## Also

- **Horde audio:** with 8 or more zombies within 40 m, you hear distant moans from where they are.
- **Tips:** the first time you see a mutation, gear or a champion, a line tells you what it is and what works.

## Testing

The `ze` console command (F1):

- `ze spawn [class] [k=v ...]` spawns a zombie 5 m ahead (zombieJoe if no class) with parts of its profile set:
  `body=`, `temper=`, `walk=`, `size=`, `speed=`, `pitch=`, `age=`, `biome=`, `mutation=Toxic,Grabber`,
  `gear=KevlarVest,HardHat`, `remnant=Axe,Sunglasses`, `dead=1` (a Possum lying "dead"), `champion=1`, `alpha=1`,
  `plain=1`. Example: `ze spawn zombieJoe mutation=Volatile gear=RiotHelmet`.
- `ze info` shows the profile of the zombie you're looking at.
- `ze debug` shows every nearby zombie's profile and the AI tasks it's running above it.
- `ze set <name> <value>` changes a setting for the session; `ze` lists them.

## Settings

`Settings.xml` in the mod's folder. Gameplay settings count on the server, looks and sounds on each player's game.

## Building

- `src\build.bat` builds `ZombiesExpanded.dll` (needs Visual Studio's C# compiler).
- `src\fetch-textures.ps1` downloads the Poly Haven texture sets (CC0) the models are textured with into
  `blender\textures` (not committed).
- `src\build-models.bat` builds the gear and growth models (each `blender\<model>.py`; see `blender\MODELS.md`),
  then `src\build-bundle.bat`, which builds `Resources\zombiesexpanded.unity3d` with Unity 2022.3.62f2 and renders
  previews: `unity\Build\looks-*.png` (the looks), `unity\Build\models\*.png` (each model on vanilla Joe, Cop and
  Nurse) and `unity\Build\effects.png`.
- `research\` holds the notes on how the game's zombies work (engine code, XML, every zombie class).
