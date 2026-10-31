# Weapons Expanded

Mod that adds 40 very rare weapons that can only be looted or bought from traders. All weapons are based on base game items so there will be no out of place icons, or unbalanced buffs.

**v3.0 Compatible** - Updated for 7 Days to Die v3.0 with modern stats blocks, DualSense/Xbox trigger effects, UnlockedBy progression, and v3.0 perk conventions.

## Weapons Include

### Handguns
1. Hugh's Special Glock (gunHandgunT1Pistol)
2. Desert Redeemer (gunHandgunT3DesertVulture)
3. Joe's Golden Magnum (gunHandgunT2Magnum44)
4. Marc's MP5 (gunHandgunT3SMG5)

### Machine Guns
5. Red Army AK-47 (gunMGT1AK47)
6. Lieutenant Dan's Zombie Slayer (gunMGT2TacticalAR)
7. Manny's Meat Grinder (gunMGT3M60)

### Rifles
8. Winchester Model 70 (gunRifleT1HuntingRifle)
9. Ron's Rifle (gunRifleT2LeverActionRifle)
10. Jen's Special Sniper (gunRifleT3SniperRifle)

### Shotguns
11. Double Barrel Peacekeeper (gunShotgunT1DoubleBarrel)
12. Bob's Super Shotgun (gunShotgunT3AutoShotgun)
13. Super Pump (gunShotgunT2PumpShotgun)

### Bows / Crossbows
14. The Trifecta (gunBowT3CompoundCrossbow)
15. The Pacifier (gunBowT3CompoundBow)

### Explosives
16. The Finale (gunExplosivesT3RocketLauncher)

### Axes / Tools
17. Infested Fireaxe (meleeToolAxeT1IronFireaxe)
18. Barbarian's Battle Axe (meleeToolAxeT2SteelAxe)
19. Rekt's Chainsaw (meleeToolAxeT3Chainsaw)
20. Gravedigger (meleeToolPickT3Auger)
21. The Architect (meleeToolSalvageT3ImpactDriver)

### Melee Weapons
22. Lightning Rod (meleeWpnBatonT2StunBaton)
23. Hell Hound (meleeWpnBladeT3Machete)
24. Joel's Retribution (meleeWpnClubT3SteelClub)
25. Golden Knuckles (meleeWpnKnucklesT3SteelKnuckles)
26. Legendary War Hammer (meleeWpnSledgeT3SteelSledgehammer)
27. Sam's Stabbing Stick (meleeWpnSpearT3SteelSpear)

### Junk Turrets / Drones
28. Killer Drone (gunBotT3JunkDrone)
29. Papa Sledge (gunBotT1JunkSledge)
30. The Warden (gunBotT2JunkTurret)

### Signature Weapons
Each of these has a special ability on top of better stats.

31. Stalker's Harvester (meleeWpnBladeT1HuntingKnife) - 25% chance to cause bleeding, +50% harvest from corpses, 6x sneak attack damage
32. Grand Slam (meleeWpnClubT1BaseballBat) - power attacks send zombies flying and have a 30% chance to knock them down
33. Bloodletter (meleeWpnSledgeT1IronSledgehammer) - each hit heals you 8 health, kills heal 15 more
34. Hellfire (gunBowT1WoodenBow) - 35% chance to set targets on fire
35. Whisper (gunBowT1IronCrossbow) - 5x sneak attack damage, reloads 40% faster
36. Chain Reaction (gunRifleT0PipeRifle) - anything it kills explodes, hurting everything within 4 meters (including you)
37. Frostbite (gunShotgunT0PipeShotgun) - hits slow enemies by 50% for 4 seconds
38. The Prospector (meleeToolPickT2SteelPickaxe) - +50% ore and stone from mining
39. Rampage (gunMGT0PipeMachineGun) - each kill gives 6 seconds of +25% fire rate, faster reloads and faster movement
40. Lucky Seven (gunHandgunT0PipePistol) - every shot has a 7% chance to hit for up to 7x damage

## Where to Find Them

Chance per container opened that it holds one of the weapons:

| Container | Chance |
|---|---|
| Large hardened chest (T5) | 5% |
| Hardened chest (T4) | 4% |
| Gun safe | 4% weapon + 4% drone/turret |
| Hero loot chest | 2% |
| Wall and picture safes, hidden stashes, buried weapon chests | 1% |
| Buried treasure | about 10% |
| Zombie loot bags (regular / strong / boss) | 0.5% / 1% / 2% |

Traders can also stock them: a typical trader has about a 5% chance per restock (Hugh about 8%), once your trader stage is high enough for that weapon's tier. Tier 4-6 trader quests have about a 1 in 20 chance to offer one as a reward choice.

The chances are set by the five `DementiveRares` templates at the top of `Config/loot.xml` if you want to tune them.

## v3.0 Updates

- Bumped to version 2.0.0.0
- Updated `BurstRoundCount=1000` to `0` (proper "fully automatic" convention)
- Updated bow trader templates: `bowsTier2` / `bowsTier3` instead of `baseTier3`
- Added `UnlockedBy` property to all 29 items
- Added 7-tier `<stats>` blocks for quality roll variation
- Added DualSense/Xbox trigger effects to all ranged weapons with explicit Action blocks
- Fixed missing `TraderStageTemplate` on DementiveDesertRedeemer, DementivegunMGT3M60
- Cleaned trailing whitespace bug in `item_modifiers.xml` (`DementiveDesertRedeemer ` with space)
- Renamed `Localization.txt` to `Localization.csv` (the game no longer loads `.txt` localization from mods) and aligned rows to the v3.0 header (removed deprecated `latam` column, added `KeepLoaded` column) so weapon names and descriptions display correctly
- Verified all perk names still exist in v3.0
- Lightning Rod uses the V3.4 stun baton logic, so Intellect Mastery (2-hit charge at rank 4, extra shock damage at rank 5), the Tech Junkie bonus charge and the 0-point Electrocutioner shock all work. It keeps its own bonuses: +1s shock duration, double knockback, and leftover charges after a discharge
- HP/AP ammo, shotgun slugs and better arrows/bolts add their extra damage again. The guns, bows and crossbows used to set a fixed damage that replaced the ammo's, so every ammo type hit the same. Damage with standard ammo is unchanged.
- Fixed the error spam, stuck mod and broken save after putting a Burning Shaft mod on the Infested Fireaxe, Barbarian's Battle Axe, Hell Hound, Sam's Stabbing Stick, Papa Sledge or Joel's Retribution (the flame effect still used the pre-1.0 asset path). The Legendary War Hammer now gets its flame effect too.
- Attachment overrides (Burning Shaft flames, scope and sight positions, silencer sounds, club meshes) are copied from each weapon's vanilla parent, which also fixes the scopes' DualSense trigger setting and uses the proper silenced sounds for the Desert Redeemer and Joe's Golden Magnum
- Loot chances are 5x higher; before this most players never found a single weapon in a whole playthrough
- Traders can now actually stock the weapons (they were never in any trader's inventory), and tier 4-6 quests can offer one as a reward
- Server-side version: weapons use their vanilla icons with a color tint again (the last update had switched them to the custom icons, which players without the client mod don't have)
- Axes and the Gravedigger auger get the V3.4 Strength Mastery healing effect, the Legendary War Hammer gets the V3.4 second-power-attack tracking, and Golden Knuckles use the V3.4 left-hand knuckle attachment
- Chain Reaction's kill explosions now work in multiplayer and on dedicated servers for every player. Before, only the host's kills exploded: the game only runs explosions on the server, and other players' kills are detected on their own machines
