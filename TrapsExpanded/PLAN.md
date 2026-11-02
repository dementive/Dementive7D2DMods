# Traps Expanded: plan

The approved design (2026-11-01). Blood Moon is the wave and the week before it is the build phase; traps have roles,
set each other up with statuses, level up from kills, and a report after each Blood Moon shows how they did.

**Status (2026-11-01):** everything below is built (all nine milestones, at the user's request in one go, to be
playtested together at the end); the Tesla Coil alone has been played. What changed from the plan while building:

- The Tar Sprayer, Flame Vent and Bolt Thrower draw a little power (5, 10 and 15 W): powered blocks are what gives a
  trap an owner and an on/off switch.
- Ammo and fuel go in through the trap's radial menu (Load / Unload) into the mod's own saved store, not a container
  window.
- Re-arming the Bear Trap is instant, not a 2 s hold.
- The Burn Barrel and Flame Vent set zombies on fire with the mod's own burning (5 a second), not a molotov's: the
  vanilla fire buffs would let a cheap early trap kill most zombies on its own. Flaming arrows from the Trip Bow use the
  vanilla flaming-arrow fire.
- Knockback distances (Swinging Log, Ram, Pressure Washer, Bolt Thrower) are a guessed force per meter
  (TrapStatusDEM.KnockbackPerMeter) to tune in game.
- Frost Field is a 2.5 m ice patch around the vent whose chill lasts 5 s longer.
- The Overcharger boosts the mod's powered traps only, not vanilla ones.
- Vanilla traps that level: turrets and the blade trap. The dart trap and electric fence can't be told apart once
  their dart or shock is out, so they don't.
- Levels and loaded ammo are lost when a trap is picked up (the ammo drops).

## Rules every trap follows

- **Look:** scrap-built from recognizable junk like the vanilla traps, textured with photo-scanned materials, rendered
  with the game's own model shader (Game/Entity Tint Mask) and worn all over (scratches, worn edges, dust, grime).
  Each model is checked in renders beside the vanilla traps before it goes in game.
- **Upkeep:** every trap costs something to run: ammo, fuel, wear or your time.
- **No stun-lock:** control effects are short and followed by an immunity window.
- **Damage types chosen on purpose:** the game adds side effects to some (every Electrical hit plays the electrocute
  flinch). Combos are worked out in the mod's own code.
- **Role first:** at raw damage a vanilla turret beats these; they earn their place through area, control and combos.
- **Co-op:** everything that matters runs on the server; clients only draw effects.

## Statuses

| Status | From | Effect | Combo |
|---|---|---|---|
| Soaked | Sprinkler | 10 s: 15% slower, can't be set on fire | Tesla Coil: double damage, one more jump, and its jolt becomes a 2 s stun (then 6 s immune) |
| Tarred | Grease Slick, Tar Sprayer | 12 s: 35% slower, flammable | Fire turns it into an Inferno: triple burn for 6 s, spreading to tarred zombies within 3 m |
| Chilled, then Frozen | Cryo Vent | Each stack 20% slower; 3 stacks freeze for 2 s, then 6 s immune | Frozen zombies take double from blunt and crushing hits (Ram, Swinging Log, clubs, sledges) |

Demolishers and bosses can't be frozen, and their slows are halved.

## Traps

Unlock levels are the vanilla traps crafting skill. The primitive traps need no power and fill levels 1 to 20, which
vanilla leaves empty before its electric tier at 25.

| Trap | Unlock | Role | What it does | Upkeep | Built from | Upgrade A / B (level 3) |
|---|---|---|---|---|---|---|
| Grease Slick | start | control | Floor patch: zombies that walk through are Tarred | 1 animal fat per 4 zombies (holds 10) | Half an oil drum flattened into a pan, a black greasy puddle, a dented oil can | Deep Grease (55% slower) / Volatile Grease (Infernos +50%) |
| Burn Barrel | 5 | area | Zombies within 1.5 m catch fire (vanilla burning); lights Tarred into Inferno; a light at night; toggled with E | 1 wood per 20 s while lit | A rusty holed 55-gallon drum burning on cinder blocks | Bellows (2 m reach) / Slow Burn (wood lasts 3 times longer) |
| Swinging Log | 10 | damage, control | When a zombie walks into its path it swings through: 35 damage and 3 m knockback to every zombie hit, then re-cocks over 5 s | Wear (2 per swing) | A spiked log hung by rope from a 2x4 A-frame, with a tripwire | Spiked Log (+50% damage) / Battering Log (6 m knockback, wider swing) |
| Bear Trap | 15 | control | Snaps on the first zombie to step on it: 50 damage, holds it 3 s (big zombies 1 s); then sprung until re-armed (E, 2 s) | Re-arming by hand | A rusty steel jaw trap chained to a stake | Spring Loader (re-arms itself after 15 s) / Heavy Jaws (holds 5 s, even big zombies) |
| Trip Bow | 20 | damage | Fires a real arrow every 3 s at the first zombie in a 12 m line ahead, using whatever vanilla arrows are loaded | Arrows | A hunting bow lashed to a sawhorse, with a tripwire and pulley | Repeater (every 1.5 s) / Long Draw (+50% damage, 20 m) |
| Sprinkler Head | 25 | control | Soaks zombies in a 6 m cone ahead | 5 W | Sprinkler heads on a copper pipe rig, fed by a blue plastic drum on cinder blocks | Deluge (90 degree cone, Soaked 20 s) / Pressure Washer (narrow jet, shoves 1 m, 15 damage) |
| Tar Sprayer | 25 | control | Lobs a tar glob every 2 s up to 10 m: 5 damage, Tarred in a 2 m splash | Tar (crafted from oil and coal) | A paint-sprayer gun on a swivel, a tar bucket on a hand truck, a car battery | Sticky Tar (60% slower) / Volatile Tar (Infernos +50%, spread 5 m) |
| Salvage Hopper | 25 | economy | Zombies your traps kill within 10 m drop extra scrap and brass into it, earning back about half the ammo cost | none | A rusty bin with a funnel and a car-alternator magnet | Ammo Press (turns the haul into ammo for nearby traps) / Scavenger (food, meds, gun parts) |
| Tesla Coil (built) | 50 | area | Every 1.5 s zaps the nearest zombie within 8 m for 22, jumping to 2 more at 60% per jump; 10% jolt per hit | 30 W + wear (1 per zap) | A pole transformer on a pallet, copper-pipe primary, PVC secondary, dryer-duct ring | Storm / Overload, rescaled to the current numbers |
| Cryo Vent | 50 | control | Floor vent: every 1.5 s zombies over it get a Chilled stack and 6 cold damage | 20 W + wear | A car A/C compressor and fridge coils under a frosty steel grate | Deep Freeze (freezes at 2 stacks, 3 s) / Frost Field (ice patch that chills for 5 s) |
| Ram | 50 | damage, control | Punches zombies within 2 m every 2 s: 60 damage and 4 m knockback, no stun | 15 W + wear | A log-splitter ram on a skid, with a road sign as the striking plate | Piledriver (double damage, no knockback) / Battering Ram (8 m knockback, 3 m line) |
| Flame Vent | 75 | area | 5 m fire cone: sets zombies on fire plus 15 damage per second; Inferno on Tarred; won't light Soaked | Gas cans | The game's own unfinished flamethrower trap model, plus a new flame jet | Napalm (fire stays on the ground 4 s) / Blowtorch (10 m jet, 1.5 times damage) |
| Overcharger | 75 | support | Powered traps within 5 m attack 25% faster but wear 25% faster | 40 W | Car batteries and a capacitor bank in a shopping cart, wired with jumper cables | Capacitor Bank (8 m) / Surge (+50%, double wear) |
| Bolt Thrower | 100 | damage (big zombies) | Every 3 s up to 30 m: 800 damage and a knockdown, aimed at the zombie with the most health | Rebar bolts | A ballista from a car leaf spring and a winch, on a tripod | Skewer (through 3 zombies) / Explosive Bolts (3 m blast, 150) |

Spares if a primitive trap doesn't work out: Deadfall (a weighted log drops for 120 crushing damage on one zombie,
then is winched back up) and Caltrops (a nail patch that slows and chips damage). Cut for good: the Lure Siren, and the Spotlight Marker with its Marked status (not realistic or fun).

## Systems

- **Trap levels:** each trap counts its own kills and levels up at 25, 75, 150 and 300 kills (+8% damage and +5%
  attack speed per level; status traps get +10% duration instead). At level 3 you pick upgrade A or B from the trap's
  radial menu. Vanilla traps level too (this hooks the game's own trap code, so it comes last).
- **Blood Moon report:** the morning after, everyone in the party sees kills by trap and by player, the MVP trap,
  combos triggered, traps lost, and the world's records.
- **Morning forecast:** on Blood Moon day a radio message gives the rough horde size and which special zombies are
  coming, read from the game's own spawn tables for the party.

## Effects

The game has fire, smoke and sparks to reuse. Water spray, frost, the flame jet and tar globs are new particle effects
built in the Unity project.

## Build order

Planned as one playtest per milestone; built all together instead (see the status above).

1. Sprinkler and the Soaked combo with the Tesla Coil
2. Blood Moon report
3. Grease Slick, Burn Barrel, Trip Bow
4. Swinging Log, Bear Trap
5. Tar Sprayer, Flame Vent
6. Cryo Vent, Ram
7. Bolt Thrower
8. Overcharger, Salvage Hopper
9. Trap levels, upgrades and the forecast
