# Weapons Expanded

Mod that adds 29 very rare weapons that can only be looted or bought from traders. All weapons are based on base game items so there will be no out of place icons, or unbalanced buffs.

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

## v3.0 Updates

- Bumped to version 2.0.0.0
- Updated `BurstRoundCount=1000` to `0` (proper "fully automatic" convention)
- Updated bow trader templates: `bowsTier2` / `bowsTier3` instead of `baseTier3`
- Added `UnlockedBy` property to all 29 items
- Added 7-tier `<stats>` blocks for quality roll variation
- Added DualSense/Xbox trigger effects to all ranged weapons with explicit Action blocks
- Fixed missing `TraderStageTemplate` on DementiveDesertRedeemer, DementivegunMGT3M60
- Cleaned trailing whitespace bug in `item_modifiers.xml` (`DementiveDesertRedeemer ` with space)
- Updated `Localization.txt` header to v3.0 format (removed deprecated `latam` column)
- Verified all perk names still exist in v3.0
