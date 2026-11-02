# Vanilla zombie definitions in 7 Days to Die V3.4 (XML survey for "Zombies Expanded")

Read-only research. Nothing under the game folder was modified.

- Game folder: `C:\Program Files (x86)\Steam\steamapps\common\7 Days To Die` (`<game>` below). Steam build id 26237568, `Assembly-CSharp.dll` dated 2026-10-30.
- Sources read: `<game>\Data\Config\` `entityclasses.xml`, `entitygroups.xml`, `gamestages.xml`, `spawning.xml`, `items.xml` (zombie hand items and projectile ammo), `buffs.xml`, `sounds.xml`, `physicsbodies.xml`, `loot.xml`, `utilityai.xml`, `Localization.csv`, `Stealth.txt`, `XML.txt`; `7DaysToDie_Data\StreamingAssets\aa\catalog.json`; `Mods\0-SCore`, `Mods\0-XNPCCore` configs.
- Engine behaviour (marked **[IL]**) was read from an `ildasm` dump of `Assembly-CSharp.dll` made by earlier sessions (`...\12c0a9f8-...\scratchpad\game.il`, newer than the DLL). Anything I deduced from names rather than read is marked **(inferred)**.
- Companion file with one row for every zombie class (158 rows): `C:\Users\dm\AppData\Local\Temp\claude\C--Program-Files--x86--Steam-steamapps-common-7-Days-To-Die-Mods\819827e6-1dde-4cbd-bb54-81550a692653\scratchpad\zombie_all_classes.tsv`

---

## 0. Headline facts (read these first)

1. **Plague Spitter and Frostclaw do not exist as separate zombies in V3.4.** `zombiePlagueSpitter*` is a pure alias of `zombieRancher*` and `zombieFrostclaw*` a pure alias of `zombieChuck*` (empty `extends` shells, `UserSpawnType=None`, kept "for POI spawns and V2.4 save games"). Localization shows them as "Rancher" and "Chuck". Their old Mesh lines are commented out in `entityclasses.xml`, but the art still ships in the Addressables catalog (`Zombies/PlagueSpitter/ZPlagueSpitter{,Feral,Radiated}.prefab`, `Zombies/Frostclaw/ZFrostClaw{,Feral,Radiated}.prefab`).
2. **Unused zombie art in the catalog** (usable by a mod with pure XML `Mesh` lines): `Zombies/Sand/ZSand{,Feral,Radiated}.prefab`, `Zombies/Snow/ZSnow{,Feral,Radiated}.prefab`, the two sets above, and `Zombies/Crawler/ZCrawlerRadiated.prefab` (no `zombieSteveCrawlerRadiated` class exists although Localization has a "Radiated Crawler" key).
3. **There is no freeze/cold effect from Frostclaw/Chuck** in V3.4 XML. Chuck = boulder thrower; stun comes from `buffInjuryStunned03`.
4. **The Screamer has no special XML.** `zombieScreamer*` is an ordinary short zombie with `zombiefemalescout*` sounds. The scream/horde-call is a hard-coded director system (section 3.5) driven by entity spawners named `Scouts1/Scouts2/ScoutsFeral/ScoutsRadiated` and the gamestage spawner `ScoutGSList`.
5. **Special attacks are all expressed as the zombie's hand item, `Action1`**: `Class="Vomit"` (projectile, used by Cop/Mutated/Chuck), `Class="SpawnEntity"` (Rancher swarm). A zombie only uses Action1 if its `AITask` contains `RangedAttackTarget itemType=1`. Big Mama/Tourist/Bowler carry the Cop hand item (with vomit) but their AITask has no `RangedAttackTarget`, so they never spit.
6. **Variants are separate entity classes** (`...Feral`, `...Radiated`, `...Charged`, `...Infernal`) linked by `extends` and `PreviousTier`. The tier is derived from the **`Tags`** property **[IL]** (`feral`, `radiated`, `charged`/`infernal`, `special`, `strong`). Charged and Infernal reuse the Radiated prefab and differ only by the `MatColor` emissive tint, hand item, speed pattern and stats.
7. **Cop and Demolition explosions** are `Class=EntityZombieCop` + an `Explosion` property class. They explode only after being "primed" (health below a fraction, or a detonator body part is hit) and only if the zombie is still alive when the fuse ends **[IL]**.
8. **Inheritance rules.** `effect_group`s DO inherit through `extends` in `entityclasses.xml` (in-file header comment, and confirmed by the repo memory note on entity classes), so do not stack `base_add`/`perc_add` carelessly. All `<property>` values are copied from the parent first and the child's own properties then override; the only exclusions are `HideInSpawnMenu` and whatever is listed in the child's `ignore="A,B"` attribute **[IL]** (`EntityClassesFromXml.Load` → `EntityClass.CopyFrom`). The in-file comment that `Tags` "DOES NOT inherit" is contradicted by that loader code, but vanilla re-lists `Tags` on every class anyway, so do the same (the Plague Spitter/Frostclaw aliases, which have no `Tags` line, therefore inherit the Rancher/Chuck tags in V3.4 **[IL]**).
9. **XNPCCore rewrites `AITask`/`AITarget` on `zombieTemplateMale`, `zombieSpider`, `zombieFatCop`, `zombieMutated`, `zombieDemolition`** (section 8). Classes that define their own `AITask` (Rancher, Chuck and aliases) are untouched.

---

## 1. Entity classes

### 1.1 Template chain (all in `entityclasses.xml`)

```
zombieTemplateMale                          (Class=EntityZombie, UserSpawnType=None)
 ├─ zombieTemplateShort                     HandItem=meleeHandZombieShort, ExperienceGain=^xpSlim01
 │   └─ zombieTemplateSlimFemale            SizeScale 0.9, WalkType 3, MoveSpeedAggro "0.3, 1.35"
 └─ (most families extend zombieTemplateMale directly, a few extend zombieTemplateShort)
```

`zombieTemplateMale` key values (everything else inherits these):

| Property | Value |
|---|---|
| `Class` | `EntityZombie` (Cop/Demolition/Mutated override to `EntityZombieCop`) |
| `EntityFlags` / `EntityType` | `zombie` / `Zombie` (EntityFlags "decides for scoring") |
| `Tags` | `entity,zombie,walker` (comment says it does not inherit; the loader copies it, see 0.8; vanilla re-lists it per class) |
| `Prefab` / `Mesh` | `Z` / (empty, each family sets `Mesh`); Spider uses `Prefab=ZLong` |
| `AvatarController` / `ModelType` | `AvatarZombieController` / `Standard` |
| `PhysicsBody` | `zombieStandard` (Fat Cop/Tourist/Bowler: `zombieFat`; Big Mama: `zombieFemaleFat`) |
| `Mass` / `Weight` | 170 / 70 |
| `Faction` | `undead` |
| `WalkType` / `CrouchType` / `DanceType` | 7 / 1 / 1 |
| `HasRagdoll`, `RootMotion`, `HasDeathAnim` | true |
| `Buffs` | `zombieBuffStatusCheck01` |
| `HandItem` / `HandItemCrawler` | `meleeHandZombie01` / `meleeHandZombie02` |
| `Immunity` | `sickness;disease;wellness` |
| `MaxTurnSpeed` | 250 |
| `MoveSpeed` | 0.08 (idle wander) |
| `MoveSpeedAggro` | `0.2, 1.25` (min, max; see 1.6) |
| `MoveSpeedRand` | `-.2, .25` |
| `MoveSpeedPanic` | 0.55 |
| `SwimSpeed` / `SwimStrokeRate` | 1 / `1,1.5` |
| `CanClimbLadders` | true |
| `JumpMaxDistance` | `2.8, 3.9` |
| `MaxViewAngle` / `SightRange` / `SightLightThreshold` / `LookAtAngle` | 180 / 30 / `-2,150` / 60 |
| `AttackTimeoutDay` / `AttackTimeoutNight` | 1.5 / 1.1 (seconds) |
| `AIFeralSense` / `AINoiseSeekDist` / `AIPathCostScale` | 1.5 / 8 / `.15, .4` |
| `ExperienceGain` | `^xpNormal01` (=500) |
| `LootDropProb` / `LootDropEntityClass` | .04 / `EntityLootContainerRegular` |
| `TimeStayAfterDeath` / `DeadBodyHitPoints` | 30 / 1000 |
| `SleeperNoiseToSense` / `...SoundChance` / `SleeperNoiseToWake` | `3,8` / .5 / `9,12` |
| `SleeperSightToSenseMin/Max` | `-10,0` / `200,300` |
| `SleeperSightToWakeMin/Max` | `-40,5` / `340,480` |
| `PainResistPerHit` | .55 (comment: "caps at 3, decay .2/s, at 1 movement is not slowed") |
| `DismemberMultiplierHead/Arms/Legs` | 1 / 1 / 1; `LegCrippleScale` 2; `LegCrawlerThreshold` 0 |
| `KnockdownProneDamageThreshold` / `...StunDuration` / `...RefillRate` | 0.5 / `0.5,1.8` / `0.045,0.045` |
| `KnockdownKneelDamageThreshold` / `...StunDuration` / `...RefillRate` | 0.4 / `0.5,1.8` / `0.045,0.045` |
| `Legs/Arms/Head/ChestExplosionDamageMultiplier` | 1 |
| Property classes | `FallLandBehavior`, `DestroyBlockBehavior` (section 4.5) |
| effect_group | `DistractionResistance base_set 0,0`; `HealthMax base_set ^healthSlim` then `perc_add -.15,.15` (random +-15% HP per zombie); `onSelfFirstSpawn AddBuff buffEntitySpawnHeal` (fills health/stamina to full); `StaminaMax 100`; `BuffResistance base_set 5` on `buffFatiguedTrigger,buffArmSprainedCHTrigger,buffLegSprainedCHTrigger,buffLaceration,buffInfectionCatch,buffAbrasionCatch,buffInjuryStunned01CHTrigger,buffInjuryBleedingTwo,buffRadiationPool`; `onSelfAttackedOther ModifyCVar noTeethNoInfection` (0/1 depending on victim `buffBrawlerNoTeeth`) |

Value shorthand `^name` is replaced from the `<replace_properties>` / `<replace_passive_effect>` tables at the top of `entityclasses.xml` (HP buckets and XP buckets, section 1.4). Colors for `MatColor` are `<color name=.../>` entries in the same file.

### 1.2 Zombie families

Tiers present: N=Normal, F=Feral, R=Radiated, C=Charged, I=Infernal (`-` = no class). HP and XP are the resolved numbers (`healthXxx` / `xpXxx` buckets). MoveSpeedAggro is `min, max` for Normal and for Feral. All 158 zombie classes are in the companion TSV.

| Class (base) | Display | Extends | Mesh prefab (base) | WalkType | Size | Tiers present | HP N/F/R/C/I | MoveSpeed | MoveSpeedAggro N->F | HandItem (N) | XP N/F/R/C/I |
|---|---|---|---|---|---|---|---|---|---|---|---|
| zombieArlene | Arlene | zombieTemplateShort | Arlene/ZArlene.prefab | 3 | 0.9 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieMarlene | Marlene | zombieTemplateShort | Marlene/ZMarlene.prefab | 5 | 0.97 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombiePartyGirl | Party Girl | zombieTemplateSlimFemale | CocktailWaitress/ZCocktailWaitress.prefab | 3 | 0.99 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieNurse | Nurse | zombieTemplateShort | Nurse/ZNurse.prefab | 7 | 1 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieJoe | Joe | zombieTemplateMale | Joe/ZJoe.prefab | 5 | 1 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieSteve | Steve | zombieTemplateShort | Steve/ZSteve.prefab | 6 | 0.95 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieTomClark | Tom Clark | zombieTemplateShort | TomClark/ZTomClark.prefab | 6 | 0.95 | NFRC- | 125/500/800/1000/- | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/- |
| zombieBusinessMan | Businessman | zombieTemplateShort | Suit/ZSuit.prefab | 7 | 1 | NFRCI | 125/500/800/1000/1600 | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieShort | 400/800/1100/1400/1700 |
| zombieBurnt | Burnt | zombieTemplateShort | Burnt/ZBurnt.prefab | 7 | 1 | NFRCI | 125/500/800/1000/1600 | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieBurning | 450/875/1175/1450/1700 |
| zombieRancher | Rancher | zombieTemplateMale | Rancher/ZRancher.prefab | 7 | 1 | NFRCI | 450/950/1700/1900/2500 | .4 | .4, 1.35 -> 0.6, 1.45 | meleeHandZombieRancher | 700/1025/1300/1600/2200 |
| zombiePlagueSpitter (alias, UserSpawnType None) | Rancher | zombieRancher | Rancher/ZRancher.prefab | 7 | 1 | NFRCI | 450/950/1700/1900/2500 | .4 | .4, 1.35 -> 0.6, 1.45 | meleeHandZombieRancher | 700/1025/1300/1600/2200 |
| zombieChuck | Chuck | zombieTemplateMale | Chuck/ZChuck.prefab | 2 | 1.2 | NFRCI | 900/1200/2000/2400/3000 | .17 | .55, 1.35 -> .6, 1.4 | meleeHandZombieChuck | 1000/1075/1375/1650/2600 |
| zombieFrostclaw (alias, UserSpawnType None) | Chuck | zombieChuck | Chuck/ZChuck.prefab | 2 | 1.2 | NFRCI | 900/1200/2000/2400/3000 | .17 | .55, 1.35 -> .6, 1.4 | meleeHandZombieChuck | 1000/1075/1375/1650/2600 |
| zombieSpider | Spider | zombieTemplateMale | Spider/ZSpider.prefab | 22 | .94 | NFRCI | 125/500/800/1000/1600 | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombie01 | 425/850/1150/1450/1700 |
| zombieBoe | Boe | zombieTemplateMale | Boe/ZBoe.prefab | 2 | 1.08 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/1800 |
| zombieMaleHazmat | Hazmat | zombieBoe | Hazmat/ZHazmat.prefab | 7 | 1.08 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.2 -> .5, 1.3 | meleeHandZombieHazMat | 500/900/1200/1500/1800 |
| zombieJanitor | Janitor | zombieTemplateMale | Mechanic/ZMechanic.prefab | 5 | 1 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/1800 |
| zombieInmate | Inmate | zombieTemplateMale | Mechanic/ZInmate.prefab | 5 | 1.08 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/1800 |
| zombieMoe | Moe | zombieTemplateMale | Moe/ZMoe.prefab | 1 | 1.08 | NFR-I | 200/550/900/-/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/-/1800 |
| zombieLab | Lab Worker | zombieTemplateMale | Lab/ZLab.prefab | 7 | 1 | NFRC- | 200/550/900/1100/- | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/- |
| zombieDarlene | Darlene | zombieTemplateMale | Darlene/ZDarlene.prefab | 3 | 0.98 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/1800 |
| zombieYo | Yo | zombieTemplateMale | Yo/ZYo.prefab | 5 | 1.02 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombie01 | 500/900/1200/1500/1800 |
| zombieUtilityWorker | Utility Worker | zombieTemplateMale | Worker/ZWorker.prefab | 6 | 1 | NFRCI | 225/700/1100/1300/1900 | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombieWorker | 550/950/1250/1550/1900 |
| zombieBiker | Biker | zombieTemplateMale | Biker/ZBiker.prefab | 7 | 1.08 | NFR-I | 600/900/1600/-/2400 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieStrong | 775/1025/1300/-/2200 |
| zombieLumberjack | Lumberjack | zombieTemplateMale | Lumberjack/ZLumberjack.prefab | 2 | 1 | NFR-I | 450/950/1700/-/2500 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieStrong | 700/1000/1300/-/2200 |
| zombieFemaleFat | Big Mama | zombieTemplateMale | BigMama/ZBigMama.prefab | 1 | 1 | NFR-I | 450/950/1700/-/2500 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieCop | 700/1025/1300/-/2200 |
| zombieFatHawaiian | Tourist | zombieTemplateMale | Hawaiian/ZHawaiian.prefab | 1 | 1 | NFR-I | 450/950/1700/-/2500 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieCop | 700/1025/1300/-/2200 |
| zombieBowler | Bowler | zombieTemplateMale | Hawaiian/ZBowler.prefab | 1 | 1 | NFR-I | 450/950/1700/-/2500 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieCop | 700/1025/1300/-/2200 |
| zombieFatCop | Cop | zombieTemplateMale | Cop/ZCop.prefab | 1 | 1 | NFR-I | 450/950/1700/-/2500 | 0.08 | 0.2, 1.2 -> 0.45, 1.3 | meleeHandZombieCop | 750/1050/1350/-/2400 |
| zombieSkateboarder | Thug | zombieBoe | Thug/ZThug.prefab | 2 | 1.08 | NFRCI | 200/550/900/1100/1700 | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombie01 | 500/900/1200/1550/1800 |
| zombieSoldier | Soldier | zombieTemplateMale | Soldier/ZSoldier.prefab | 2 | 1 | NFR-I | 250/800/1400/-/2200 | 0.08 | 0.3, 1.35 -> 0.6, 1.45 | meleeHandZombieWorker | 575/975/1275/-/2000 |
| zombieWightFeral (no non-feral class; "zombieWight" is only a Localization/twitch key) | Wight | zombieTemplateMale | Wight/ZWightFeral.prefab | 2 | 1.1 | -FRCI | -/1200/2200/2400/3000 | 0.08 | 0.6, 1.45 -> 0.6, 1.45 | meleeHandZombieFeral | -/1075/1375/1650/2600 |
| zombieScreamer | Screamer | zombieTemplateShort | Screamer/ZScreamer.prefab | 3 | 1 | NFRC- | 200/500/800/1000/- | 0.08 | 0.2, 1.25 -> .5, 1.35 | meleeHandZombieShort | 475/850/1150/1450/- |
| zombieMutated | Mutated | zombieFatCop | Mutated/ZMutated.prefab | 2 | 1 | NFRCI | 950/1200/2100/2500/3100 | .25 | .4, 1.3 -> .5, 1.35 | meleeHandzombieMutated | 1000/1075/1375/1675/2700 |
| zombieDemolition | Demolition | zombieSoldier | Demolition/ZDemolition.prefab | 2 | 1 | N---- | 1200/-/-/-/- | 0.08 | 0.3, 1.35 -> - | meleeHandZombieDemolition | 1075/-/-/-/- |
| zombieSteveCrawler | Crawler | zombieTemplateMale | Crawler/ZCrawler.prefab | 21 | 1 | NF--- | 200/300/-/-/- | 0.25 | .7, 1 -> 1.2, 1.4 | meleeHandZombie02 | 550/600/-/-/- |

Notes on the table:

- **Normal-tier-less families**: `zombieWight` has no non-feral class at all (`zombieWightFeral` is the base, `extends zombieTemplateMale`, with `PreviousTier` listing the normal civilians). `zombieDemolition` has no variants. The Crawler has only N and F.
- **Commented-out (disabled) classes**: `zombieArleneInfernal`, `zombieMarleneInfernal`, `zombiePartyGirlInfernal`, `zombieNurseInfernal`, `zombieJoeInfernal`, `zombieSteveInfernal`, `zombieTomClarkInfernal`, `zombieLabInfernal`, `zombieScreamerInfernal`, and Charged for `zombieMoe`, `zombieBiker`, `zombieLumberjack`, `zombieFemaleFat`, `zombieFatHawaiian`, `zombieBowler`, `zombieFatCop`, `zombieSoldier`. (Template text is still in the file, usable as a pattern.)
- **Inheritance quirks**: `zombieJanitorRadiated`/`zombieInmateRadiated` extend the *Normal* class (not Feral) and repeat the feral stats; `zombieMaleHazmatRadiated` extends `zombieMaleHazmat`. `zombieMaleHazmat extends zombieBoe`, `zombieSkateboarder extends zombieBoe` (Thug), `zombieMutated extends zombieFatCop`, `zombieDemolition extends zombieSoldier`.
- **Display names** (Localization): Arlene, Marlene, Party Girl, Nurse, Joe, Steve, Tom Clark, Businessman (`zombieBusinessMan`), Burnt, Rancher, Chuck, Spider, Boe, Hazmat (`zombieMaleHazmat`), Janitor, Inmate, Moe, Lab Worker, Darlene, Yo, Utility Worker, Biker, Lumberjack, Big Mama (`zombieFemaleFat`), Tourist (`zombieFatHawaiian`), Bowler, Cop (`zombieFatCop`), Thug (`zombieSkateboarder`), Soldier, Wight, Screamer, Mutated, Demolition, Crawler (`zombieSteveCrawler`). `zombieBehemoth` has a Localization key but **no entity class**.
- **Mesh paths** are written `@:Entities/Zombies/<Folder>/<Prefab>.prefab` in XML; the catalog stores them as `Assets/AssetBundles/Zombies/<Folder>/<Prefab>.prefab` (folders: `Arlene, Bigmama, Biker, Boe, Burnt, Chuck, Cocktailwaitress, Cop, Crawler, Darlene, Demolition, Frostclaw, Hawaiian (Bowler+Hawaiian), Hazmat, Joe, Lab, Lumberjack, Marlene, Mechanic (Janitor+Inmate), Moe, Mutated, Nurse, PlagueSpitter, Rancher, Sand, Screamer, Snow, Soldier, Spider, Steve, Suit, Thug, Tomclark, Wight, Worker, Yo`). Each folder has `Z<Name>.prefab`, `Z<Name>Feral.prefab`, `Z<Name>Radiated.prefab` (Demolition has one; Wight has Feral+Radiated only). The single shared animator is `Zombies/Common/Controllers/ZController.controller` (plus `ZDogController`, `ZMutatedBubblesController`).

### 1.3 Standalone / special classes

| Class | Extends | Class= | Distinguishing XML |
|---|---|---|---|
| `zombieSpider` (+F/R/C/I) | TemplateMale | EntityZombie | `Prefab=ZLong`, `WalkType=22`, `AITask` begins `Leap`, `CanClimbVertical=true`, `JumpMaxDistance` `7, 9` (feral `11, 13`), `MoveSpeedPanic=1.2`, `SwimSpeed=1.3`, `LookAtAngle=0`, `AINoiseSeekDist=3`, `AIPathCostScale=.6, 1`, `DismemberMultiplierHead/Arms/Legs=0` on the Normal tier only (Feral/Radiated+ set .7/.4 again), `LegCrawlerThreshold=0`, `LegCrippleThreshold=0`, `KnockdownProneDamageThreshold=0`, `KnockdownKneelDamageThreshold=0` (these four are inherited by every tier: no leg crippling, crawler conversion or knockdown). Feral/Radiated use hand `meleeHandZombie02Feral` (20/24, range 1.3); Charged/Infernal use the generic `meleeHandZombieCharged`/`meleeHandZombieInfernal`. |
| `zombieSteveCrawler` (+Feral) | TemplateMale | EntityZombie | `WalkType=21`, `RotateToGround=true`, `CanClimbLadders=false`, `DanceType=0`, `MoveSpeed .25`, `MoveSpeedAggro ".7, 1"` (feral `1.2, 1.4`), hand `meleeHandZombie02` (range 1.3), `SoundRandomTime 20`, `SoundAlertTime 15`, HP bucket `healthCrawler` (200/300). Tag `crawler`; spawn group `ZombiesCrawlers`. |
| `zombieFatCop` family | TemplateMale | **EntityZombieCop** | acid vomit + detonator (3.2). `Mass 320`, `PhysicsBody zombieFat`, `RightHandJointName Jaw`, `PushFactor 20`, `LegsExplosionDamageMultiplier` (and Arms/Head/Chest) `2` ("volatile"), `DismemberMultiplierLegs 0` on the Normal tier only (Feral+ reset it to .7/.4); `LegCrawlerThreshold`, `LegCrippleThreshold`, `KnockdownProne/KneelDamageThreshold` are 0 for every tier (no cripple/crawler/knockdown). |
| `zombieMutated` family | FatCop | **EntityZombieCop** | `WalkType 2`, `MoveSpeed .25`, `ExplodeHealthThreshold 0`, radioactive spray (3.3). Tag `wasteland`. |
| `zombieDemolition` | Soldier | **EntityZombieCop** | boss, detonator backpack (3.4). |
| `zombieRancher` family (+`zombiePlagueSpitter*` aliases) | TemplateMale | EntityZombie | summons insect swarm (3.1). `MoveSpeed .4`, `SightRange 27`, `Mass 160`. Tags `desert,special,coverWorthy`. |
| `zombieChuck` family (+`zombieFrostclaw*` aliases) | TemplateMale | EntityZombie | boulder thrower (3.2b). `SizeScale 1.2`, `Mass 230`, `SightRange 40`, `MoveSpeed .17`, `RightHandJointName Boulder`, `PainResistPerHit "3, .8, .4"`. Tags `snow,special,coverWorthy`. |
| `zombieBurnt` family | TemplateShort | EntityZombie | fire hands from Feral up (3.6). Tag `burnt`. `Mass 160`, `HandItemCrawler=meleeHandZombieBurningCrawler`. |
| `zombieScreamer` family | TemplateShort | EntityZombie | scout (3.5). `Mass 110`, `AIPathCostScale .5, .6`. |
| `zombieMaleHazmat` family | Boe | EntityZombie | `JumpMaxDistance .5, .6` (cannot jump), `AINoiseSeekDist 6`, `AIPathCostScale .65, .9`, hand `meleeHandZombieHazMat*` adds `infectionCounter` +100 (normal) / +150 (feral+) instead of 10/15. |
| `zombieSoldier` family | TemplateMale | EntityZombie | tag `zombieSoldier`; `PhysicalDamageResist base_set 50`; `AIPathCostScale .35, .55`. |
| `zombieBiker`, `zombieUtilityWorker` | TemplateMale | EntityZombie | `PhysicalDamageResist base_set 20`. Utility Worker Radiated also `HealthChangeOT base_set 1.4`, no radiated-regen trigger (Businessman Radiated likewise). |
| `zombieLab`, `zombieNurse` | TemplateMale / Short | EntityZombie | `Mass 130`, `AIPathCostScale .5, .65`, own loot bag (`EntityLootContainerLab` / `EntityLootContainerNurse`). |
| `zombieWightFeral` family | TemplateMale | EntityZombie | `SizeScale 1.1`, `Mass 210`. `zombieWightRadiated` also sets `LegCrippleThreshold 0.01`, `KnockdownProneDamageThreshold 0.45`, `KnockdownKneelDamageThreshold 0.38`, `*ExplosionDamageMultiplier .85` (harder to knock down). No special ability in XML. |

Hostile "zombie" animals (also in `entityclasses.xml`, `Class` in brackets): `animalZombieDog` [EntityZombieDog, extends animalWolf, 200 HP, HP-based], `animalDireWolf` [EntityEnemyAnimal, 3000 HP, tag `animalFeral`], `animalZombieBear` [4000 HP, `animalFeral`], `animalZombieBoar` and `animalBossGrace` [bosses], `animalZombieVulture` and `animalZombieVultureRadiated` [EntityVulture; the radiated one has a `Vomit` Action1 using `ammoProjectileVultureVomit`], `animalInsectSwarm` / `animalBeeSwarm` [EntitySwarm]. They use legacy `AITask-N`/`AITarget-N` properties with a `data=` attribute (see section 2.1).

### 1.4 Variant (tier) scheme

Each tier is its own `entity_class` that `extends` the previous tier and sets `PreviousTier` to it. The generic recipe, taken from the Steve/Arlene/Boe families (values differ slightly per family, see the TSV):

| | Normal | Feral | Radiated | Charged | Infernal |
|---|---|---|---|---|---|
| `Tags` (re-listed every time) | base tags | `+feral` | `+feral,radiated` | `+feral,charged` (no `radiated`) | `+feral,infernal` (no `radiated`) |
| `Mesh` | `ZX.prefab` | `ZXFeral.prefab` | `ZXRadiated.prefab` | inherits Radiated prefab | inherits Radiated prefab |
| `AltMats` | `HD_X2.mat,HD_X3.mat` (random skin) | inherited | `HD_X_Radiated2/3.mat` | inherited | inherited |
| `MatColor` (emissive tint) | none | none | `radiated` = `.295,1,0,0` (green) | `charged` = `0,.8,3,.7` (blue, alpha 0.7 = emissive power) | `infernal` = `2.7,.8,0,.55` (red/orange) |
| `DismemberMultiplierHead/Arms/Legs` | 1 | .7 | .4 | inherits .4 | inherits .4 |
| `PainResistPerHit` | .55 | .7 | .9 | .9 | .9 (FatCop Infernal: `3, .5, .5`) |
| `MoveSpeedAggro` | family (slim `0.3, 1.35`; normal `0.2, 1.25`; strong `0.2, 1.2`) | slim `0.6, 1.45`; normal `.5, 1.35`; strong `0.45, 1.3` | inherits | inherits | inherits |
| `MoveSpeedPattern` | none | none | none | `^chargedMoveSpeedPattern` = `1.2, .8, .7, 1.5, 1, .8, .5, 1.5` (delay,scale pairs: speed oscillates) | `^infernalMoveSpeedPattern` = `3, .95, 1, .75` |
| `JumpMaxDistance` | `2.8, 3.9` (strong/fat `.8, 1.1`) | `4.6, 5` (strong `1.8, 2.5`) | inherits | inherits | inherits |
| `HandItem` (example slim/normal) | `meleeHandZombieShort` 8/7 or `meleeHandZombie01` 10/8 (entity/block dmg) | `...ShortFeral` 16/22, `meleeHandZombieFeral` 20/24 | same as Feral | `meleeHandZombieCharged` 60/150 | `meleeHandZombieInfernal` 45/250 |
| `LootDropProb` | .04 | .04 | .04 | **.1** | **.1** |
| `LootDropEntityClass` | family bag (usually `EntityLootContainerRegular`) | same | many families switch to `EntityLootContainerStrong` | `EntityLootContainerStrong` | `EntityLootContainerStrong` |
| `HealthMax` bucket | `healthSlim` 125 / `healthNormal` 200 / `healthStrong` 450 | `...Feral` 500 / 550 / 950 | `...Radiated` 800 / 900 / 1700 | `...Charged` 1000 / 1100 / 1900 | `...Infernal` 1600 / 1700 / 2500 |
| `ExperienceGain` bucket | `xpSlim01..04` (400-475), `xpNormal01..03` (500-575), `xpStrong00..03` (600-775) | `xp*Feral*` (800-1075) | `xp*Radiated*` (1100-1375) | `xp*Charged*` (1400-1675) | `xp*Infernal*` (1700-2700) |
| effect_group | - | - | `onOtherDamagedSelf` → `ModifyCVar RadiatedRegenAmount set N` + `AddBuff buffRadiatedRegen` | - | `BuffResistance base_set .75` tags `buffInjuryKnockdown01,buffInjuryKnockdown02` |

HP buckets (`replace_passive_effect`): Slim 125/500/800/1000/1600; Normal 200/550/900/1100/1700; UtilityWorker 225/700/1100/1300/1900; Sturdy (Biker) 600/900/1600/1800/2400; Tough (Chuck) 900/1200/2000/2400/3000; Brute (Mutated) 950/1200/2100/2500/3100; Strong 450/950/1700/1900/2500; Fit (Soldier) 250/800/1400/1600/2200; Wight (feral..infernal) 1200/2200/2400/3000; Screamer 200/500/800/1000/1600; Demo 1200; Crawler 200/300.

`RadiatedRegenAmount` per family: 2.5 (Screamer, Mutated), 4 (most slim and Rancher/Chuck/Lab/Darlene/Burnt), 4.5 (Boe, Hazmat, Janitor, Inmate), 5 (Spider, Yo), 6 (Thug, Soldier, Wight), 8 (Moe), 9 (Biker, Lumberjack, Big Mama, Tourist, Bowler, Cop).

**What each tier flag does in code [IL]:**

- `EntityClass.CalculateEntityTier()` classifies the class from `Tags`: any of `charged,infernal` → **Elite**; else `radiated` → **Radiated**; else `feral`/`animalFeral` → **Feral**; else `special` → **Special**; else `strong` → **Strong**; else **Normal**. The sandbox "Max Tier Limit" (`EntityFactory.MaxEntityTier`) then replaces over-tier spawns by walking `PreviousTier` (comma list allowed: `GetEntityClassWithinMaxTier`). So a new tier class needs correct tags and a `PreviousTier`.
- `EntityAlive.IsFeral` = class has the `feral` tag; it selects the `ZombieFeralMove` sandbox speed setting (section 1.6).
- `radiated` / `charged` / `infernal` tags also pick the `_IsRadiated`/`_Infernal` gib and cap materials in `DismembermentManager` (`Zombies/Common/Gibs/Materials/*_IsRadiated.mat`, `*_Infernal.mat`) and the `_IsRadiated` shader property on the body materials.
- `MatColor` → `EModelBase` instantiates the LOD material, sets `_Emissive=1` and `_EmissiveColor=<color>`. New colors can be added with `<color name="x" value="r,g,b,a"/>` under `<entity_classes>`; values above 1 over-brighten.
- `Game/Character` shader flags seen in code: `_IsRadiated`, `_EmissiveColor`, `_ElectricShockEnabled` (set by code, not XML).

### 1.5 `Tags` actually used (for `target_tags`, `EntityTagCompare`, quests)

- Base is `entity,zombie,walker`; **Spider** (`entity,zombie,spider,allbiome`) and **Crawler** (`entity,zombie,crawler,allbiome`) have **no `walker` tag**, which matters for `buffInjuryCrippled01` (only applies its limp walk type to `walker,bandit`).
- `allbiome` on every common family (Arlene, Biker, Boe, Bowler, Businessman, Darlene, Demolition, Cop, Tourist, Big Mama, Inmate, Janitor, Joe, Lab, Lumberjack, Hazmat, Marlene, Moe, Nurse, Party Girl, Screamer, Thug, Soldier, Spider, Steve, Crawler, Tom Clark, Utility Worker, Yo; all tiers). Biome-bound tags: `burnt` (Burnt), `desert` (Rancher), `snow` (Chuck), `wasteland` (Mutated).
- Role tags: `special` (Normal tier of Rancher, Chuck, Cop, Mutated, Demolition), `coverWorthy` (those plus their feral variants where re-listed; a `static FastTags EntityAlive.CoverWorthTags` exists in code, purpose not traced, inferred: AI/NPC cover logic), `strong` (Normal tier of Biker, Lumberjack, Big Mama, Tourist, Bowler; the Feral variants re-list tags without it), `boss` (Demolition), `zombieCop` (Cop, all tiers), `zombieSoldier`, `spider`, `crawler`.
- Tier tags: `feral` (120 classes), `radiated` (34), `charged` (26), `infernal` (25); see 1.4 for what they drive.
- Consumers seen in XML: `challenges.xml` `KillByTag entity_tags="allbiome,zombieAnimal,burnt,desert,snow,wasteland"`; `buffs.xml` `EntityTagCompare` on `walker`, `zombieCop`, `zombieSoldier`, `human`, etc. (Twitch bucket-head buff, crippling buff).

### 1.6 Speed model

- `MoveSpeed` = idle wander. `MoveSpeedPanic` = fleeing. `MoveSpeedRand` is added to the min aggro speed.
- `MoveSpeedAggro="min, max"`. **[IL]** `EntityHuman.GetMoveSpeedAggro`: the sandbox speed setting index i (0..4; option names Walk, Jog, Run, Sprint, Nightmare are inferred, the array has 5 entries) is read from `GamePrefs` by priority: `ZombieBMMove` if `IsBloodMoon`; else `ZombieFeralMove` if the class has the `feral` tag; else `ZombieMoveNight` if `World.IsDark()`; else `ZombieBMMove` if it is a biome-spawned zombie standing in a storm (not in biome type 3); else `ZombieMove` (daytime). `t = {0, .35, .7, 1.0, 1.35}[i]`; speed = `min*(1-t) + max*t` if t < 1 else `max*t`; then x `moveSpeedPatternScale` (from `MoveSpeedPattern`) and passed through the `RunSpeed` passive effect. Rage arrays: `moveRageSpeeds {.75,.8,.9,1.15,1.7}`, `moveSuperRageSpeeds {.88,.92,1,1.2,1.7}`.
- `MoveSpeedPattern="delay, scale, delay, scale, ..."`: cycles speed scale; used by Charged/Infernal, Big Mama `2, 1, 1, 1.1, 1, .6, 1, .4` and Tourist/Bowler `2, 1.15, 1, .8, 1, .5`.
- Walk animation set = `WalkType`: 1 = fat (Moe, Big Mama, Tourist, Bowler, Cop), 2 = Boe, Thug, Lumberjack, Chuck, Soldier, Wight, Mutated, Demolition; 3 = Arlene, Darlene, Party Girl, Screamer; 5 = Marlene, Joe, Janitor, Inmate, Yo; 6 = Steve, Tom Clark, Utility Worker; 7 = template default, Nurse, Businessman, Burnt, Rancher, Hazmat, Lab, Biker; 21 crawler; 22 spider. `buffInjuryCrippled01` switches non-player `walker`/`bandit` entities to `AnimatorSetWalkType value=5` (limp).
- Unused-by-zombies keys exist: `MoveSpeedNight`, `JumpDelay`, `SwimOffset`, `SoundGiveUp`, `AIGroupCircle`, `AISeeOffset`, `SearchRadius`, `StealthSoundDecayRate`.

---

## 2. AI task lists

### 2.1 Mechanism

- V3.4 zombies use **one multi-line property each**: `<property name="AITask" value="Task params|Task params|..."/>` and `<property name="AITarget" .../>`. Order = priority (first runnable wins). `EntityClass` still also parses the legacy `AITask-1`, `AITarget-1`, ... form with a `data="..."` attribute (used by animals, `animalTemplateHostile`). **[IL]** `EAIManager.CopyPropertiesFromEntityClass` reads `AITask` and `AITarget`; `GetType` maps names to classes `EAI<Name>`.
- Task names available **[IL]**: `ApproachAndAttackTarget`, `ApproachDistraction`, `ApproachSpot`, `BlockIf`, `BlockingTargetTask`, `BreakBlock`, `DestroyArea`, `Dodge`, `Leap`, `Look`, `PathTest`, `MeleeAttackTarget`, `RangedAttackTarget`, `RunawayFromEntity`, `RunawayWhenHurt`, `SetAsTargetIfHurt`, `SetNearestCorpseAsTarget`, `SetNearestEntityAsTarget`, `Territorial`, `Wander`, plus drone-only `DroneItemModStunWeapon`, `DroneItemModHealWeapon` (also a base `RunAway` with `fleeDistance`).
- Parameter keys **[IL]** (`SetData`): `RangedAttackTarget` / `MeleeAttackTarget`: `itemType` (slot/action index, 1 = Action1), `startAnimType` (default -1), `releaseDelay` (default .5), `cooldown`, `duration`, `minRange` (default 4), `maxRange` (default 25), `unreachableRange`, `sndStart`, `sndRelease` (`MeleeAttackTarget` also `slot`); `Wander`: `exePer`, `fade`, `lookMin`, `lookMax`; `Leap`: `legs`; `Dodge`: `tags,maxXZDistance,cooldown,duration,minRange,maxRange,unreachableRange`; `RunawayWhenHurt`: `runChance,healthPer,healthPerMax`; `RunawayFromEntity`: `flags,safeFlags,safeDistance,dangerDistance`; `BlockIf`: `condition` (e.g. `alert e 0`); `ApproachAndAttackTarget`, `SetAsTargetIfHurt`, `SetNearestEntityAsTarget`: `class=` list; `SetNearestCorpseAsTarget`: `flags=edible`.
- `class=` syntax in the template comments: `ApproachAndAttackTarget class=EntityPlayer,0,EntityBandit,0,...` = class, then chase/give-up time (0 = default). `SetNearestEntityAsTarget class=EntityPlayer,0,0,EntityBandit,0,-10,EntityAnimalRabbit,0,12` = class, hear distance, see distance; 0 = entity default, negative = do not apply the sense scale. Valid target classes: `EntityAnimalRabbit` (also chicken), `EntityAnimalStag`, `EntityBackpack`, `EntityBandit`, `EntityEnemyAnimal`, `EntityLootContainer`, `EntityMinibike`, `EntityNPC`, `EntityPlayer`, `EntitySupplyCrate`, `EntitySupplyPlane`, `EntitySurvivor`, `EntityVulture`, `EntityZombie`, `EntityZombieCop`, `EntityZombieDog`.
- Stealth `AIFeralSense`: **[IL]** `senseScale = 1 + CalcSenseScale() * AIFeralSense`, where CalcSenseScale is 1 when the sandbox "Zombie Feral Sense" option applies (day / night / always) and 0 otherwise; sight range = `SightRange * senseScale`. With the template's 1.5 and the option on, awake zombies see 2.5x farther.

### 2.2 The eight distinct lists in vanilla (exact text)

**AI1, default** (`zombieTemplateMale` and everything that does not override):
```
AITask:   BreakBlock| DestroyArea| Territorial| ApproachDistraction|
          ApproachAndAttackTarget class=EntityPlayer,0,EntityBandit,0,EntityEnemyAnimal,0,EntityAnimal| ApproachSpot| Look| Wander|
AITarget: SetAsTargetIfHurt class=EntityPlayer,EntityBandit,EntityEnemyAnimal| BlockingTargetTask|
          SetNearestCorpseAsTarget flags=edible|
          SetNearestEntityAsTarget class=EntityPlayer,0,0,EntityBandit,0,-10,EntityAnimalRabbit,0,12|
```
All AITask variants below keep this same `AITarget` (only `AITask` differs). Used by all civilians, Burnt, Hazmat, Soldier, Wight, Screamer, Crawler, Biker, Lumberjack, Big Mama, Tourist, Bowler, Lab, etc.

| Id | Used by | Difference vs AI1 |
|---|---|---|
| AI2 | Rancher (+Plague Spitter) all tiers | drops `DestroyArea`, `Territorial`; adds `RangedAttackTarget itemType=1;cooldown=6;duration=7;minRange=4;maxRange=27` after `ApproachDistraction`; `Wander exePer=.1;lookMin=8;lookMax=15`. |
| AI3 | Chuck (+Frostclaw) all tiers | drops `DestroyArea`, `Territorial`; adds `RangedAttackTarget startAnimType=2;itemType=1;cooldown=4;duration=5;minRange=5;maxRange=43;releaseDelay=.41;sndStart=chuckwarning;sndRelease=chuckrelease`. |
| AI4 | Spider all tiers | adds `Leap` as the first task. |
| AI5 | Cop all tiers | drops `DestroyArea`, `Territorial`; adds `RangedAttackTarget itemType=1;cooldown=4;duration=5` (default min 4 / max 25 m). |
| AI6 | Mutated, Mutated Feral | drops `Territorial`; `RangedAttackTarget itemType=1;cooldown=4;duration=3;minRange=1;maxRange=6;unreachableRange=18` placed before `DestroyArea`. |
| AI7 | Mutated Radiated/Charged/Infernal | as AI6 with `maxRange=14;unreachableRange=20`. |
| AI8 | Demolition | `BreakBlock| DestroyArea| ApproachDistraction| ApproachAndAttackTarget ...| ApproachSpot| Look| Wander|` (no `Territorial`). |

Task meanings (from names, strings and state enums **(inferred)** unless stated): `BreakBlock` attacks a block that blocks the path; `DestroyArea` has states FindExistingPos/FindPos/FindPath/WaitForPath/HasPath/EndPath/Attack, i.e. it picks a block position toward an unreachable target and hacks/tunnels toward it; `Territorial` returns the entity to its spawn point when an `entityspawner` with `Territorial=true` and `TerritorialRange` is used (XML.txt); `ApproachDistraction`/`ApproachSpot` follow distraction items (sound, grenades) and investigation positions; `Look`/`Wander` idle; `SetNearestCorpseAsTarget flags=edible` makes zombies eat corpses (`blood_eat`, `eat` animation). A zombie with any leg missing will not start `RangedAttackTarget`; with `startAnimType>=0` it also needs both arms **[IL]**.

---

## 3. Special abilities

### 3.1 Rancher / "Plague Spitter": summons an insect swarm (not a projectile)

`zombieRancher` (hand `meleeHandZombieRancher`, tiers `...Feral` / `...Charged` / `...Infernal`; Radiated reuses the Feral hand):
```xml
<item name="meleeHandZombieRancher">  <!-- Extends meleeHandMaster -->
  <property class="Action0"> Range 1.75, DamageEntity 20, DamageBlock 100 </property>   <!-- Feral 40/200, Charged 60/150, Infernal 45/250 -->
  <property class="Action1">
    <property name="Class" value="SpawnEntity"/>
    <property name="AnimType" value="4"/>          <!-- animation index; catalog has spitSwarm.fbx (inferred match) -->
    <property name="AnimWait" value="1.87"/>       <!-- seconds into the anim before the entity appears -->
    <property name="SoundWarn" value="plaguevomitwarning"/>
    <property name="SoundAttack" value="plaguevomitattack"/>
    <property name="Entity" value="animalInsectSwarm"/>
    <property name="EntityOffset" value="0, -.1, .45"/>
```
**[IL]** `ItemActionSpawnEntity` reads exactly `AnimType, AnimWait, SoundWarn, SoundAttack, Entity, EntityOffset`; `Spawn()` creates one `Entity` (looked up with `EntityClass.GetId`) at the holder's head position + the offset rotated by the holder, spawner source set, and sets the new entity's attack target to the spitter's target. Any entity class name works as `Entity`, so this is the XML-only "summon" mechanic.
- `animalInsectSwarm`: `Class=EntitySwarm`, `EntityFlags animal,zombie`, 10 HP, `PhysicalDamageResist` 75 (99 vs `ranged`), `TimeStayAfterDeath 0`, empty `AITask-1/AITarget-1` (behaviour is in C#), `MoveSpeed 1`, `MoveSpeedAggro 2.1, 2.1`, `SightRange 20`, `ExperienceGain 50`, hand `meleeHandAnimalInsectSwarm` (3 damage, Range 1, hit adds `buffInjurySlow` and `infectionCounter +150`). `animalBeeSwarm` is the same with 5 damage and no infection.
- Loot: `LootDropProb .05`; `LootDropEntityClass="EntityLootContainerRegular,1,EntityLootContainerPlague,1"` (class,weight list; Radiated+ uses `EntityLootContainerStrong,1,EntityLootContainerPlague,1`). `EntityLootContainerPlague` uses loot list `zPackPlague` (gold bag).

### 3.2 Cop (`zombieFatCop`): acid vomit + detonator

Hand `meleeHandZombieCop` (Feral `meleeHandZombieCopFeral`; Radiated and Infernal `meleeHandZombieCopRadiated`):
```xml
<property class="Action0"> Range 1.75, DamageEntity 20 (Feral/Rad 40), DamageBlock 100 (200) </property>
<property class="Action1">
  <property name="Class" value="Vomit"/>
  <property name="Hitmask_override" value="Arrow"/>
  <property name="Delay" value=".3"/>  <property name="Range" value="200"/>
  <property name="Infinite_ammo" value="true"/>
  <property name="Magazine_items" value="ammoProjectileZombieVomit"/>   <!-- ...Feral / ...Radiated -->
  <property name="Particles_muzzle_fire" value="vomitMouth"/>
  <property name="Sound_warning" value="hulkvomitwarning"/> <property name="Sound_start" value="hulkvomitattack"/>
```
Effect-group passives on the hand: `MaxRange 100`, `DamageFalloffRange 50`, `MagazineSize 1`, `BurstRoundCount` 1 / 3 / 6 (normal / feral / radiated), `SpreadDegreesVertical` 2 / 4 / 10, `SpreadDegreesHorizontal` 4 / 10 / 40. Hit effects: the usual `fireOneBuff` list, `infectionCounter` +10/15/20, `abrasionZombieHit` 1800/2400/3200.
Projectile ammo `ammoProjectileZombieVomit` (`...Feral`, `...Radiated`): `Class Projectile`, `DamageEntity` 10/20/25, `DamageBlock` 120/240/240 (passive `BlockDamage` 105 / 145 on Feral/Radiated), `Velocity 18`, `FlyTime 2`, `LifeTime 4`, `CollisionRadius .24`, `Explosion` `ParticleIndex 7` (Feral+: `RadiusBlocks 2`, `RadiusEntities 1`), `DamageBonus earth 0` (feral+ also water 0), **`Buff buffInfectionCatch`** with passive `BuffProcChance` .30 / .40 / .40. `DamageModifier` by material tag: `earth` 0, `stone` .5, `metal` +1.2.
Detonator: `Class=EntityZombieCop`, `<property class="Explosion">`:
| Tier | ParticleIndex | RadiusBlocks | RadiusEntities | BlockDamage | EntityDamage |
|---|---|---|---|---|---|
| Normal | 8 | 5 | 6 | 500 | 150 |
| Feral | 8 | 5 | 6 | 650 | 200 |
| Radiated | 80 | 5 | 6 | 750 | 250 |
| Infernal | 81 | 5 | 6 | 1000 | 250 |
plus `DamageBonus earth=0`. Other props: `SoundExplodeWarn=hulkexplodewarning`, optional `SoundTick="name,startDelay,scale"`, `ExplodeDelay` (default **5** s, **[IL]**), `ExplodeHealthThreshold` (default **0.4** = fraction of max health, **[IL]**).
**[IL] behaviour of `EntityZombieCop`:** `OnUpdateEntity` (server/local side only) primes when not already primed, not sleeping, no `buffShocked`, and `0 < Health < MaxHealth * ExplodeHealthThreshold`; `ProcessDamageResponseLocal` also primes immediately when a hit lands on body-part flag `0x400` (the detonator part) from a damage source with `canHitSpecialBodyParts`. Priming plays `SoundExplodeWarn`, sets `isPrimed` and, for the immediate path, starts the prefab's `Detonator` component (red light) and sends a `NetPackageEntityPrimeDetonator` to clients. While primed the zombie **cannot attack** (`IsAttackValid` false) and **runs at its max aggro speed** (`moveSpeedAggroMax`), ticking `SoundTick` faster each beep (delay x scale, floor 0.2 s). After `ExplodeDelay` s it sets `SpecialAttack2` (the `runningExplode` animation), stands still (speed 0) for `ExplodeDelay/5*1.5` s (1.5 s at the default 5 s), then calls `GameManager.ExplosionServer` with the class `Explosion` data, sets `timeStayAfterDeath=0` and dies. The countdown only runs while `!IsDead()`: **killing the zombie during the fuse cancels the blast**. Electric stun (`buffShocked`) blocks priming.
Also: the explosion damage multipliers on the class (`Legs/Arms/Head/ChestExplosionDamageMultiplier 2`) make Cops vulnerable to explosives. Feral/Radiated get `DismemberMultiplier` .7/.4; legs are not dismembered on the Normal tier (`DismemberMultiplierLegs 0`; Feral+ reset it) and are never crippled/knocked down (thresholds 0 in every tier).

`ExplosionData` keys readable from XML **[IL]**: `ParticleIndex, Duration, RadiusBlocks, BlockDamage, BlockTags, RadiusEntities, EntityDamage, BlastPower, Buff, IgnoreHeatMap, DamageType` (+ nested `DamageBonus`). `ParticleIndex` values already in use in vanilla: 0, 2, 5, 6, 7, 8, 10, 11, 13-18, 20-22, 25-32, 35, 36, 60-81; there is no XML way to add new indices.

### 3.2b Chuck (and "Frostclaw"): boulder thrower

```xml
<property name="RightHandJointName" value="Boulder"/>   <!-- bone that holds the visible boulder -->
AITask: RangedAttackTarget startAnimType=2;itemType=1;cooldown=4;duration=5;minRange=5;maxRange=43;releaseDelay=.41;sndStart=chuckwarning;sndRelease=chuckrelease
Action1: Class Vomit, Hitmask_override Rocket, AnimType 3, WarningMax 0, Delay .27, Range 100, Infinite_ammo, Magazine_items ammoProjectileZombieBoulder (Feral/Charged/Infernal variants)
```
Hand passives: `MaxRange 100`, `BurstRoundCount 1`, `SpreadDegrees` 2 vertical / 4 horizontal. Hand melee: 20/100 (Feral 40/200, Charged 60/150, Infernal 45/250).
Boulder ammo `ammoProjectileZombieBoulder[Feral|Charged|Infernal]`: `Class Projectile`, `DamageEntity` 50/60/75/100, `DamageBlock` 50/60/75/100, `Explosion` {`ParticleIndex 36`, `RadiusBlocks 2.5`, `RadiusEntities 4.7`, `EntityDamage` 80/90/100/120, `BlockDamage` 750/900/1000/1200}, **`FlyTime -5`** (negative = solve a ballistic arc landing on target over 5 s), `Velocity 50`, `Gravity -8`, `LifeTime 7`, `CollisionRadius .22`, **`Buff buffInjuryStunned03`** (8 s: -80% to -20% walk/run/crouch/jump speed, -50% attacks/min, blur screen effect). Sounds: `chuckwarning`, `chuckgrabboulder`, `chuckboulderimpact`, `chuckrelease`. Both Chuck and Frostclaw classes are identical, including `Tags` `snow`.

### 3.3 Mutated: radioactive blob spray

AI6/AI7 (section 2.2). Hand `meleeHandzombieMutated[Feral|Radiated|Charged|Infernal]`; Action0 melee 20/100, 25/140, 30/180, 60/200, 50/250 (entity/block). Action1: `Class Vomit`, `Hitmask_override Arrow`, `AnimType 1`, `Delay .1`, `Range 200`, `SpreadVerticalOffset -50` (-45 Radiated/Charged), `WarningDelay .6`, `WarningMax 1`, `Sound_warning zombie_mutated_attack_ranged`, `Magazine_items ammoProjectileZombieMutated` (Normal/Feral) or `ammoProjectileZombieMutatedFast` (Radiated and up). Hand passives (all `MaxRange 10`): Normal/Feral `MagazineSize 1`, `BurstRoundCount 5`, `SpreadDegreesHorizontal 90`, `SpreadDegreesVertical 30` (shotgun fan of lobbed blobs); Radiated `MagazineSize 7`, `BurstRoundCount 1`, `RoundsPerMinute 360`, spread 21 H / 38 V (rapid single blobs); Charged `MagazineSize 1`, `BurstRoundCount 5`, spread 13 H / 27 V (`SpreadVerticalOffset -32`); Infernal `MagazineSize 4`, `BurstRoundCount 3`, `RoundsPerMinute 90`, spread 30/30.
Ammo: `ammoProjectileZombieMutated` `DamageEntity 35`, `DamageBlock 180`, `Gravity -7.5`, `Velocity 4.5`, `FlyTime 0`, `LifeTime 4`, `CollisionRadius .2`, `Explosion` {`ParticleIndex 7`, **`Buff buffRadiationPool`** (comment: "index 7 has ExplosionDamageArea script", i.e. a lingering damage puddle)}, `Buff buffInfectionCatch` (`BuffProcChance .30`). `...Fast`: `DamageEntity 45`, `DamageBlock 250`, `Gravity -9`, `Velocity 10.5`. `buffRadiationPool`: 3 s, `damage_type radiation`, players only: `HealthChangeOT -4`/s, `Stamina` -20 per update, `Radiation` screen effect .6, removed on death. Model has `ZMutatedBubblesController.controller`.

### 3.4 Demolition (boss)

`Class=EntityZombieCop`, `extends zombieSoldier`, `HP healthDemo 1200`, `PhysicalDamageResist base_set 60`, `DamageModifier perc_set 1` tag `head`, `PainResistPerHit .5`, `LootDropProb .3` with `EntityLootContainerBoss` (zPackBoss), `Mass 300`, `CrouchType 0`, `JumpMaxDistance 1, 2`, `ExperienceGain ^xpStrongFeral03`.
`Explosion`: `ParticleIndex 2`, `RadiusBlocks 5`, `RadiusEntities 6`, **`BlockDamage 5000`**, **`EntityDamage 800`**. `ExplodeDelay 2`, `ExplodeHealthThreshold 0` (never primed by health; primed by a detonator-body-part hit, **[IL]** logic above), `SoundExplodeWarn demolitionzexplodewarning`, `SoundTick="demolitionz_beep,.5,.9"` (name, initial delay, delay scale: beeping accelerates), `StompsSpikes=true` (property exists; behaviour name suggests it ignores/destroys spike traps **(inferred)**). Hand `meleeHandZombieDemolition`: 20 entity, 500 block damage. Spawn: `ZombiesDowntown` p .02, `ZombiesWastelandDowntown` p .05, `zombieDemolition` spawner.

### 3.5 Screamer = scout system (hard-coded, XML only supplies groups and spawners)

- Entity: `zombieScreamer` (`extends zombieTemplateShort`, HP `healthScreamer` 200, `WalkType 3`, `Mass 110`, sounds `zombiefemalescout{roam,alert,attack,pain,death,sense}`). No ability properties.
- `spawning.xml` entity spawners flagged "referenced in code for the screamer system": `Scouts1` (1 alive), `Scouts2` (2 alive, `DelayBetweenSpawns 4`), `ScoutsFeral`, `ScoutsRadiated` (`TotalAlive 2`, `TotalPerWave 1,2`, `DelayBetweenSpawns 3`), using entity groups `ZombieScouts` (`zombieScreamer`), `ZombieScoutsFeral` (`zombieScreamerFeral`), `ZombieScoutsRadiated` (`zombieScreamerRadiated`).
- **[IL]** `AIDirectorChunkEventComponent.SpawnScouts(targetPos)`: finds a start position `kScoutSpawnDistance = 80` m out, finds the closest player within 120 m, computes `GameStageDefinition.CalcGameStageAround(player)` and picks the spawner: GS < 45 → `Scouts1`; < 85 → `Scouts2`; < 125 → `ScoutsFeral`; otherwise → `ScoutsRadiated`. `AIScoutHordeSpawner` flags the spawned entities `EntityAlive.IsScoutZombie = true` (plus `IsHordeZombie`, `IsBloodMoon` copied from the director); scouts skip the normal alert-sound branch in `EntityAlive`, and `EAIApproachSpot.updatePath` has a separate `IsScoutZombie` branch that uses the A* path manager (`AstarManager`). In `AIScoutHordeSpawner.UpdateHorde`, when a scout is in its attacking state with a living player target (or an investigate position) and is not stunned, it calls `spawnHordeNear` and waits 18 s before the next call (`ZombieCommand.AttackDelay = 18`; director constant `kScoutScreamAgainTime = 18`). Other director constants (usage inferred from their names): `kScoutScreamGraceTime = 2` s, `kScoutSummonedPerScream = 5`, `kScoutSummonedTotal = 25`, `kScoutSpawnAnotherScoutChance = 0.12`. The summoned horde is drawn from gamestage spawner **`ScoutGSList`** (groups `scoutHordeStageGS<N>`, section 5.1/5.3; log text "Scout spawned a zombie horde"). The class sound set is `zombiefemalescout*` (`SoundAlert` = `AudioSource_ScreamerAlert.prefab`, clips in `Sounds/Enemies/Scout_Zombie/`). What triggers `SpawnScouts` (heat/noise on a chunk) was not traced **(inferred: AIDirectorChunkEventComponent)**.
- Charged screamer class exists (`zombieScreamerCharged`) but no `ZombieScoutsCharged` group; Infernal is commented out.

### 3.6 Burnt: fire hands

- `zombieBurnt` itself has `meleeHandZombieBurning` with the `Buff` line commented out. From `zombieBurntFeral` up: hand `meleeHandZombieBurningFeral` (Action0 `Buff=buffBurningZombie`, passive `BuffProcChance base_set .25` tag `buffBurningZombie`; 24/24 damage), `...BurningCharged` (60/150) and `...BurningInfernal` (45/250), all with `Buff buffBurningZombie`.
- `buffBurningZombie` (hidden, .1 s, `damage_type heat`): sets cvar `$buffBurningElementDuration` 10 and adds `buffBurningElement` (10 s, `HealthChangeOT -1.5`, `WaterChangeOT -2`, adds `buffIsOnFire`).
- `zombieBurntFeral` effect group: `onSelfFirstSpawn AttachParticleEffectToEntity particle=p_twitch_zombie_fire_left parent_transform=LeftHand` and `..._right` / `RightHand`; `onSelfDied RemoveParticleEffectFromEntity` for both; `SoundSpawn="Ambient_Loops/a_fire_embersmoke_sm_lp"`. Crawler form uses `HandItemCrawler=meleeHandZombieBurningCrawler`.

### 3.7 Other per-hit effects shared by every zombie hand

Every `meleeHandZombie*` item has this trigger (one buff chosen per hit):
`onSelfAttackedOther AddBuff target=other fireOneBuff=true buff="buffFatiguedTrigger,buffArmSprainedCHTrigger,buffLegSprainedCHTrigger,buffLaceration,buffAbrasionCatch,buffInjuryStunned01CHTrigger,buffInjuryBleedingTwo" weights=".11,.07,.07,.05,.29,.36,.11"`, plus `ModifyCVar infectionCounter add` (Regular 10, Feral 15, Radiated 20 for Cop, Hazmat 100/150, swarm 150; only when the victim's `infectionCounter > 0`) and `ModifyCVar abrasionZombieHit set` (1800 regular, 2400 feral, 3200 radiated). The victim's `BuffResistance` gates these. `buffInfectionCatch`: sets `infectionCounter`, adds `buffInfectionMain`.

### 3.8 Not in V3.4 XML

No zombie-specific freeze, scream-stun, acid-pool-from-corpse, burrow, teleport or ground-pound ability exists in XML. `FallLandBehavior`/`DestroyBlockBehavior` give "rage" bursts (section 4.5). Anything beyond recombining existing hand-item actions (`Vomit`, `SpawnEntity`, melee), explosions, buffs and EAI tasks needs C# (the memory note says Harmony/SCore are only optional).

---

## 4. Tunable properties (per class)

### 4.1 Defense and damage taken
- `HealthMax` via `effect_group` `passive_effect name="HealthMax" operation="base_set" value="^bucket"`, then `perc_add -.15,.15` random spread. Ranged/armor: `PhysicalDamageResist base_set N` (Biker 20, Utility Worker 20, Soldier 50, Demolition 60; Swarm 75/99-vs-`ranged`). Other passives seen on zombies: `DistractionResistance`, `StaminaMax`, `BuffResistance`, `HealthChangeOT`, `DamageModifier` (tag `head`). `PassiveEffects` enum members **[IL]** that look relevant to zombies (queried by entity code or by damage/buff code; not every one is read for every entity): `PhysicalDamageResist`, `PhysicalDamageResistMax`, `ElementalDamageResist(Max)`, `GeneralDamageResist`, `DamageModifier`, `HeadshotDamageModifier`, `InternalDamageModifier`, `ExplosionIncomingDamage`, `TrapIncomingDamage`, `BuffResistance`, `BuffProcChance`, `DismemberChance`, `DismemberSelfChance`, `WalkSpeed`, `RunSpeed`, `CrouchSpeed`, `JumpStrength`, `HealthMax`, `HealthChangeOT`, `StaminaMax`, `EntityDamage`, `BlockDamage`, `LootDropProb`, `ExperienceGain`, `NegateDamageSelf/Other`, `DisableLoot`, `DistractionResistance/Radius/Lifetime/Strength`, `NoiseMultiplier`.
- Entity damage and block damage are not entity properties: they are the hand item's `Action0` `DamageEntity` / `DamageBlock` / `Range` (+ `Delay`/`Sphere`), tiered in 1.4. The `meleeHandZombie*` list (damage entity/block, range): `01` 10/8/1.6, `02` (crawler) 10/8/1.3, `Short` 8/7/1.4, `Feral` 20/24, `ShortFeral` 16/22, `02Feral` 20/24/1.3, `Charged` 60/150, `Infernal` 45/250, `Strong` 20/20/1.65, `StrongFeral` 40/60, `Worker` 10/40, `WorkerFeral` 20/120, `HazMat` 10/8, `HazMatFeral` 20/24, `Burning*` 12/8, 24/24, 60/150, 45/250, `Cop/Rancher/Chuck` 20/100 (feral 40/200), `Mutated` 20/100 to 50/250, `Demolition` 20/500.
- Dismemberment: `DismemberMultiplierHead|Arms|Legs` (1 / .7 / .4 / 0), `DismemberTag_L_*` (gore prefab per part, `type=blade|blunt`, `target=<bone>`, `detach`, `mask`, `atp`, `sfv`, `msb`, `scale`, `asp`), `LegCrippleScale` (2), `LegCrippleThreshold`, `LegCrawlerThreshold` (0; comment: ~.175 turns almost every knocked-down leg hit into a crawler), `Legs|Arms|Head|ChestExplosionDamageMultiplier`.
- Knockdown: `KnockdownProneDamageThreshold|StunDuration|RefillRate`, `KnockdownKneelDamageThreshold|StunDuration|RefillRate`; `PainResistPerHit` ("normal, at low health, health%" form for Chuck and FatCop Infernal); `buffInjuryKnockdown01/02` (Ragdoll 3.5 s) is resisted by Infernal (`BuffResistance .75`).
- Player-side hit effects are on the hand item (3.7).

### 4.2 Perception and noise
`SightRange` (30; Rancher 27; Chuck 40), `SightLightThreshold` (`-2,150`: light needed to be seen at min,max range), `MaxViewAngle` 180, `LookAtAngle` 60, `AINoiseSeekDist` 8 (Spider 3, Hazmat 6, Utility Worker 4), `AIFeralSense` 1.5, `AIPathCostScale`. Sleeper-only: `SleeperNoiseToSense`, `SleeperNoiseToSenseSoundChance`, `SleeperNoiseToWake`, `SleeperSightToSenseMin/Max`, `SleeperSightToWakeMin/Max`, `SoundSleeperSense=sleepersense`, `SoundSleeperBackToSleep=sleeperbacktosleep` (each rolled per zombie inside the min,max range; `Stealth.txt`). Hearing is `sounds.xml` `Noise` data (range/volume/time per sound), not an entity property. There is no per-class smell property in XML (`EntityAlive.smellPlayer` exists in code and feeds a sandbox pref into the aggro-speed index **[IL]**, details not traced).

### 4.3 Sleepers and spawn-source behaviour
There is no `SleeperType` on entity classes. Sleeper poses are blocks `Class="Sleeper"` (`sleeper*`, `infestedSleeper*`) using models `Zombies/Common/SleeperPoses/idle{Sit,Back,SideLeft,SideRight,Stomach,Sleep,Knee}Prefab.prefab` (+`...InfestedPrefab`); a sleeper block has `Pose`, `LookIdentity`, `ExcludeWalkType` (e.g. `Crawler`) (XML.txt). Which zombie fills a sleeper volume comes from the volume's gamestage group (section 5.3). Crawlers: `ExcludeWalkType` keeps them out of standing poses.

### 4.4 Loot, XP, corpse
`LootDropProb` (.04 normal/feral, **.1** charged/infernal, .05 Rancher family, .3 Demolition; blood moon bonus in `gamestages.xml` `<config lootBonusEvery lootBonusMaxCount lootBonusScale lootWanderingBonusEvery lootWanderingBonusScale>`), `LootDropEntityClass` (comma `class,weight` list allowed). Bags (`entityclasses.xml` → loot list in `loot.xml`): `EntityLootContainerRegular`→`zPackReg`, `Nurse`→`zPackNurse`, `Lab`→`zPackLab`, `Utility`→`zPackUtility`, `Soldier`→`zPackSoldier`, `Thug`→`zPackThug`, `Strong`→`zPackStrong`, `Boss`→`zPackBoss`, `Plague`→`zPackPlague` (each loot list → group `groupZpack*`; `Strong`/`Boss`/`Plague` use `qualPlus1Template`). `ExperienceGain` (value or `^xp...` bucket), `TimeStayAfterDeath` 30, `DeadBodyHitPoints` 1000, `RagdollOnDeathChance`, `HasDeathAnim`, `ParticleOnDeath blood_death`, `CorpseBlock` (commented out), `SizeScale`, `Mass`, `Weight`, `PushFactor`, `Immunity`.

### 4.5 Property classes (rage / stumble)
`<property class="FallLandBehavior">` entries `<property name="Id" data="anim=Land|LandLow|LandHard|Stumble|Ragdoll|None;height=min,max;weight=n;ragePer=min,max;rageTime=min,max;difficulty=min,max"/>` (template: 1None/1Land/1LandLow/1Stumble, LowLand/LowStumble, MidStumble, MidStumbleAndRage, MidLandHard, MidLandHardAndRage, HighStumbleAndRage, Ragdoll `height=3`). `<property class="DestroyBlockBehavior">` entries `None`/`Stumble` .2/`Ragdoll` .2 (`anim=None|Stumble|Ragdoll`, `weight`, `ragePer`, `rageTime`, `difficulty`). "Rage" = temporary speed multiplier (`ragePer` of the rage speed table, `rageTime` seconds) **[IL]** `EntityHuman.moveSpeedRagePer`.

### 4.6 Block / jump / swim
`JumpMaxDistance="min, max"`, `CanClimbLadders`, `CanClimbVertical` (Spider only), `SwimSpeed`, `SwimStrokeRate`, `StompsSpikes` (Demolition), `RotateToGround` (Crawler), `AttackTimeoutDay/Night` (template only, in seconds; no class overrides), `SoundRandomTime`/`SoundAlertTime` (Crawler 20/15, template 30/25).

### 4.7 Hit zones (`PhysicsBody`)
`physicsbodies.xml` bodies referenced by zombies: `zombieStandard` (template default, used by almost all), `zombieFat` (Cop, Tourist, Bowler), `zombieFemaleFat` (Big Mama). Also present but not referenced by any vanilla zombie class: `zombieStandardFemale`, `zombieUMA`, `zombieDog`. A body is a list of `<collider>` entries (`tag` = `E_BP_Body|Head|LArm|LLowerArm|RArm|RLowerArm|LLeg|LLowerLeg|RLeg|RLowerLeg`, bone `path` such as `Hips/LeftUpLeg`, `collisionScale`, `collisionOffset`, `ragdollScale`, `type`, `flags="collision;ragdoll"`). It holds geometry and body-part tags only; no per-part damage multiplier lives here (headshot and limb damage multipliers come from `DamageModifier`/`HeadshotDamageModifier` passives and `DismemberMultiplier*`). Using a new mesh with a different skeleton needs its own body (XNPCCore ships `mixamoConvertedStandardZombie`).

---

## 5. Spawning

### 5.1 `entitygroups.xml` (1875 groups, all `<entitygroup name="..."><e n="class" p="weight"/>...`)
- Only attributes: group `name`; entry `n` (entity class) and `p` (relative weight, default 1; **[IL]** lists are normalised: `NormalizeWorkingList`; the Max Tier option re-maps each entry via `PreviousTier` before picking). `p="0"` is used as "present but never".
- **Biome/ambient groups** (used by `spawning.xml`): `ZombiesAll` (day, 20 entries), `ZombiesNight`, `ZombiesDowntown`, `ZombiesForestDowntown`, `ZombiesForestDowntownNight`, `ZombiesBurntForest`, `ZombiesBurntForestNight`, `ZombiesDesert` (Rancher p1, Moe .25, Tourist .2, Crawler .05), `ZombiesDesertNight` (Rancher, RancherFeral .1, Biker .4, BikerFeral .1), `ZombiesSnow` (Chuck, Moe .25, Lumberjack .25), `ZombiesSnowNight` (Chuck, Feral/Radiated/Infernal/Charged Chuck .1 each, Lumberjack .45, Feral Lumberjack .05), `ZombiesWasteland` (Mutated, FatCop .4, Hazmat .4, Mutated Feral/Radiated/Infernal/Charged .05, WightFeral .05), `ZombiesAllWasteland`, `ZombiesWastelandNight`, `ZombiesWastelandDowntown`, `ZombiesCave`, `ZombiesCrawlers`, `ZombiesBoss` (FatCop), animal groups `WildGameForest`, `EnemyAnimals*`, `WolfPack`, `ZombieDogGroup`, `ZombieAnimalsGroup`, `ZombieBearsGroup`, `VultureGroup`...
- **Scout groups:** `ZombieScouts`, `ZombieScoutsFeral`, `ZombieScoutsRadiated`.
- **One group per class** (names equal the class: `zombieChuck`, `zombieRancherInfernal`, ...), used by the per-class spawners in `gamestages.xml` and by quests/console.
- **Themed groups:** `ZombieSoldierGroup`, `ZombieFatCopGroup`, `ZombieBusinessManGroup`, `ZombieBurntGroup`, `ZombieUtilityWorkerGroup`, `ZombieJanitorGroup`, `ZombieGhostTownGroup`, `HospitalGroup`, `PrisonGroup`, `ZombieBikerBarGroup`, `ZombieNightClubGroup`, `ZombieSpecialInfectedGroup` (Spider .35, Mutated .35, WightFeral .3), `ZombieFarmGroup`, plus all-tier groups `ZombiesFeral`, `ZombieFeralRadiatedGroup`, `ZombieChargedGroup`, `ZombieInfernalGroup`, `ZombieBadassGroup`.
- **Gamestage-tiered groups** (suffix = the game stage at which they begin; each is a plain entity group): `sleeperHordeStageGS<N>` (322 groups, GS 1-5778), `feralHordeStageGS<N>` (322; used by blood moon), `scoutHordeStageGS<N>` (322), `defenseHordeStageGS<N>` (322), `badassHordeStageGS<N>` and `badassOnlyHordeStageGS<N>` and `policeCarHordeStageGS<N>` (55 each, to GS 2026), `wanderingHordeStageGS<N>` (19, to 82), `FwanderingHordeStageGS<N>` (18, to 64), and per-POI-theme groups `zombie<Theme>GroupGS1/50/100/200/400/800` (LumberjackGroup, BusinessManGroup, FatCopGroup, BurntGroup, SoldierGroup, MaleHazmatGroup, UtilityWorkerGroup, JanitorGroup, `...FeralGroup` variants, GhostTown, Hospital, LabWorker, Prison, Spider, BikerBar, NightClub, SpecialInfected).
- Tier progression through the gamestage groups (share of entries by tier, first appearance): sleepers: Feral at GS 70, Radiated 125, Charged 140, Infernal 189; blood-moon (feral) groups: Feral 64, Radiated 133, Infernal 133, Charged 147; scouts: Feral 64, Radiated 103; badass: Feral 40, Radiated 65; badassOnly/policeCar start all-Feral. Wandering groups contain only normal-tier civilians (the `F` groups are still non-feral entries).

### 5.2 `spawning.xml` (biome ambient spawns)
```xml
<biome name="pine_forest">   <!-- also: burnt_forest, desert, snow, wasteland -->
  <spawn id="nz02" maxcount="3" respawndelay="0.15,0.263,0.203,0.15,0.098,0.053" time="Night"
         entitygroup="ZombiesNight" tags="commercial,industrial" notags="downtown" type="rare|animal"/>
```
- `maxcount`: max alive from that group per 5x5-chunk (80 m x 80 m) "biome chunk". `respawndelay`: game days, six values = Default, Very Slow, Slow, Normal, Fast, Very Fast; the doc says Default is the one to edit and modded values only apply when the Enemy Density sandbox option is Default. `time`: Any/Day/Night. `tags`/`notags`: POI/tile tags (`commercial,industrial,downtown`). `type="rare"` = covered by the Biome Density option; `type="animal"` = Biome Animal Respawn option.
- Per biome the id pattern is `dz01..dz04` (day), `nz01..nz04` (night), `aa/na/ae/ne/nv/av` (animals). Biome-special groups are the `dz01`/`nz04` slots (e.g. desert `ZombiesDesert(Night)`, snow `ZombiesSnow(Night)`, burnt `ZombiesBurntForest(Night)`, wasteland `ZombiesWasteland`). Wasteland has near-zero night respawn delays (0.003 days).
- `<entityspawner name=...><day value="*"><property name="EntityGroupName|Time|DelayBetweenSpawns|TotalAlive|TotalPerWave|DaysToRespawnIfPlayerLeft|AttackPlayerAtOnce|Territorial|TerritorialRange|ResetToday"/>` = static POI spawners referenced by name from prefab files (`Zombie_Soldier_Med_Territorial`, `Zombie_Ghost_Town_Large_Territorial`, `Dog_Med_Territorial`, `SpawnBurntTown`, `SpawnCave`, `SpawnSnowLarge`, ...) plus the four `Scouts*` ones.
- SCore adds cave/deep-cave `<spawn>` entries (`CaveSp01..`, `DeepCaveSp01..`) to its own biome list; no entity group is added.

### 5.3 `gamestages.xml`
```xml
<config daysAliveChangeWhenKilled="2" difficultyBonus="1.2" startingWeight="1" diminishingReturns="0.5"
        lootBonusEvery="12" lootBonusMaxCount="30" lootBonusScale="25" lootWanderingBonusEvery="3" lootWanderingBonusScale="15"/>
<group name="1GroupGenericZombie" spawner="SleeperGSList"/>   <!-- picker list for the prefab/level editor and quests; leading digit/minus only sorts -->
<spawner name="SleeperGSList">
  <gamestage stage="14"><spawn group="sleeperHordeStageGS14" num="7" maxAlive="2" duration="1" interval="0"/></gamestage>
```
- `gameStage = floor((playerLevel + daysAlive) * difficultyBonus)`; a party is combined by sorting individual GS descending and weighting 1, 0.5, 0.25... The highest `stage` <= computed GS is used. `spawn` attributes: `group` (an entitygroup name), `num` (total, default 1), `maxAlive` (per player since A17, default 1), `duration` (game hours), `interval` (seconds between waves). Max 65,535.
- 211 spawners: 173 are per-class (155 zombie + 18 animal; `zombieSteve`, `zombieRancherInfernal`, ... one stage `1`, `duration 10`; the spawner name equals the entity class and also a same-named entity group), thematic POI hordes (`ZombieBikerBarHorde`, `HospitalHorde`, `PrisonHorde`, `LabWorkerHorde`, `ZombieSoldierHorde`, `ZombieSpecialInfectedHorde`, `ZombieFatCopHorde`, `ZombieBurntHorde`, `ZombieGhostTownHorde`, `ZombieNightClubHorde`, `ZombieHazMatOnlyHorde`, ... each 6 stages at 1/50/100/200/400/800), `ZombieBadassGSHorde` / `ZombieBadassOnlyHorde` / `ZombiePoliceCarHorde` (38 stages to GS 1003), `AbandonedHouseHorde` (scoutHordeStageGS1), `SleeperGSList` (322 stages), `SleeperTestChamberGSList`, `ScoutGSList` (322), `defenseGSList` (322), `WanderingHorde` ("name is used in code"; stages 01-50 wrapping at 50; alternates `wanderingHordeStageGS<n>` and `FwanderingHordeStageGS<n>`; last stage is `ZombieBearsGroup`), **`BloodMoonHorde`** (322 stages to GS 4086; groups `feralHordeStageGS<N>`; waves like `num=5 maxAlive=5 interval=5`, final "station keeping" `num=999 maxAlive=2`). Code strings for named spawners: `BloodMoonHorde`, `ScoutGSList`, `SleeperGSList`, `WanderingHorde` **[IL]**; `gameevents.xml` also references `SleeperGSList`, `WanderingHorde`, `ZombiePoliceCarHorde`.

### 5.4 How a mod adds zombies (all pure XML)
- New class: `<append xpath="/entity_classes"><entity_class name="zombieX" extends="zombieYFeral"> ...` (mesh must be an existing prefab; new models need a Unity bundle). Localization key = class name in `Localization.csv`. Set `Tags`, `PreviousTier`, `UserSpawnType`.
- Ambient: `<append xpath="/entitygroups/entitygroup[@name='ZombiesNight']"><e n="zombieX" p="0.1"/></append>` (what XNPCCore does for its tutorial zombies on `ZombiesAll`, `ZombiesNight`, `ZombiesForestDowntown`, `ZombiesForestDowntownNight`), or a new biome slot `<append xpath="/spawning/biome[@name='snow']"><spawn id="nz05" .../></append>` (the `id` seems to key per-biome respawn state, so keep unique **(inferred)**).
- Gamestage-scaled (sleepers, blood moon, scouts, wandering, POIs): patch the stage groups by wildcard, e.g. `//entitygroup[starts-with(@name,'sleeperHordeStageGS')]`, optionally gated on the number (`[number(substring-after(@name,'GS')) >= 100]`; XPath 1.0 via System.Xml, same engine the game uses per memory note). Same for `feralHordeStageGS` (blood moon), `scoutHordeStageGS`, `badassHordeStageGS`, etc.
- To control a quest/console spawn create a named group (per-class groups exist for every vanilla class) and a `gamestages.xml` `<spawner>` + `<group>`.

---

## 6. Particles and sounds worth reusing

### 6.1 Particle prefabs (catalog `Assets/AssetBundles/Effects/ParticleEffects/`, 276 prefabs; names as used in `AttachParticleEffectToEntity particle=` without `.prefab`)
- Zombie-specific: `p_twitch_zombie_fire_left`, `p_twitch_zombie_fire_right`, `p_twitch_zombie_radiation_left`, `p_twitch_zombie_radiation_right`, `p_twitch_zombie_shock_left`, `p_twitch_zombie_shock_right` (hand effects; attach with `parent_transform="LeftHand"` / `"RightHand"`), `RadiatedParticlesOnMesh` (commented-out `ParticleOnSpawn ... param1="SetShapeToMesh0"`), `burntZombieSmoke`, `p_hotembersZombie`, `p_hotembers`, `p_onFire`, `p_onFire_attached_*` (per rig: `Spine_size_A/B/C/Demolition/FatCop`, `Spine3_...`, `Zombie_Dog_*`, `Zombie_Vulture_*`), `p_fat_cop_explosion`, `p_flies`, `p_vomitMouth`, `p_vomitVulture`, `Light_vomitAcidMouth`, `Light_vomitAcid_01`, `Light_Acid`, `p_weatherEffects_vomit`, `p_weatherEffects_freezingBreath`, `p_electric_shock`, `p_electric_shock_small`, `p_electric_fence_sparks`, `Light_ElectricArc_fpv`, `p_bleeding`, `p_blood_death`, `p_blood_decapitation`, `p_blood_eat`, `p_blood_impact`, `p_sleeperSpawn`, `p_critical`, `p_breath`, `p_smoke`, `p_big_smoke`, `p_smokePlume`, `p_flame_hazard`, `p_snowstorm1`, `p_sandstorm`, `p_confetti`, `p_drone_beam`/`p_drone_heal_beam`, `p_chemistryStation`.
- Gore/gib assets: `Zombies/Common/Gibs/Particles/{Blunt_SkullBurst,GoreDefaultBlood,GoreHeadBlood,GoreLowerArmBlood,GoreLowerLeg,GoreUpperArmBlood,GoreUpperLeg}.prefab`, `cop_explosionPrefab.prefab`, materials `*_IsRadiated.mat`, `*_Infernal.mat`.
- Entity-class particle properties: `ParticleOnSpawn`, `ParticleOnDeath` (`blood_death` → `p_blood_death`), `ParticleOnDestroy`. Explosions use integer `ParticleIndex` (vanilla values listed in 3.2); only existing indices are reachable from XML.
- Buff actions that attach visuals: `AttachParticleEffectToEntity` (`particle`, `parent_transform`, `local_offset`, `local_rotation`, `shape_mesh="true"`, `sound`, `oneshot`), `RemoveParticleEffectFromEntity`, `AttachPrefabToEntity` / `RemovePrefabFromEntity` (hats etc., see `twitch_buckethead`), `SetScale`, `AnimatorSetWalkType`, `Ragdoll`, `ModifyScreenEffect`.

### 6.2 `sounds.xml` groups (a `<SoundDataNode name=...>` with `AudioSource`, `AudioClip ClipName`, `Channel`, `Priority`, `LowestPitch/HighestPitch`, `NoiseScale`, `MaxVoices`, `MaxRepeatRate`; zombie entity properties `SoundRandom|Alert|Attack|Hurt|Death|Sense|StepType` name these)
| Zombie | Sound prefix (roam/alert/attack/pain/death/sense) |
|---|---|
| Template male, Joe, Steve, Tom Clark, Yo, Businessman, Janitor, Inmate, Thug, Biker | `zombiemale*` |
| Boe, Moe, Utility Worker, Soldier | `zombiemale2*` |
| Arlene, Nurse, Party Girl, Lab Worker, template slim | `zombiefemale*` |
| Marlene, Darlene, Big Mama | `zombiefemale2*` |
| Screamer | `zombiefemalescout*` (`AudioSource_ScreamerAlert/Screamer`) |
| Burnt | `zombieburnt*` (+`zombieburntfootstep`) |
| Rancher | `plague*` + `plaguevomitwarning`, `plaguevomitattack` |
| Chuck | `chuck*` + `chuckwarning`, `chuckgrabboulder`, `chuckboulderimpact`, `chuckrelease` |
| Cop, Tourist, Bowler | `hulk*` + `hulkvomitwarning`, `hulkvomitattack`, `vomitimpact`, `hulkexplode`, `hulkexplodewarning` |
| Demolition | `demolitionz*` + `demolitionzexplodewarning`, `demolitionz_beep` |
| Mutated | `zombie_mutated_{alert,attack,attack_ranged,death,pain,roam,sense}` |
| Hazmat | `zombie_hazmat_*` |
| Lumberjack | `zombielumberjack_*` |
| Wight | `zombieferal*` (+`zombieferalfootstep`) |
| Spider | `spider*` (roam) |
| Crawler | `crawler_roam` |
| Swarm | `swarm{alert,attack,death,pain,roam}` |
| Dogs/animals | `zombiedog*`, `zombieboar*`, `vulturevomit*` |
| Sleepers | `sleepersense`, `sleeperbacktosleep`, `sleeperspawn{concrete,dirt,metal,water,wood}` |
| Generic effects | `explosion1/2/3`, `explosion_grenade`, `explosion_charge`, `explosion_body`, `explosion_buzzer1`, `molotov_explosion`, `vomit_projectile`, `vomit_projectile_lp`, `zombie_bbq` |
`SoundStepType` values in use: `barestep`, `heelstep`, `step`, `heavystep`, `largestep`, `barehvystep`, `crawlerstep`.

---

## 7. Buffs that already behave like zombie "mutations" or statuses

| Buff / mechanism | What it does | Trigger |
|---|---|---|
| `zombieBuffStatusCheck01` | 1 s update: attaches `p_onFire` while `buffIsOnFire`, removes it otherwise | `Buffs` property on `zombieTemplateMale` |
| `buffEntitySpawnHeal` | 1 s, then `ModifyStats Health/Stamina +30000` so modified HP spawns full | `onSelfFirstSpawn` |
| `buffRadiatedRegen` | 2000000000 s, `update_rate 2.5`, `HealthChangeOT base_add @RadiatedRegenAmount`; removes itself at health >= 80%; disabled while any of `buffRadiatedRegenBlock15/30/45/60/75/90` (rad-remover mod, 15..90 s) is present | `onOtherDamagedSelf` on Radiated classes (cvar `RadiatedRegenAmount` set first) |
| Charged speed pattern | `MoveSpeedPattern ^chargedMoveSpeedPattern` | class property |
| Infernal knockdown resist | `BuffResistance .75` on `buffInjuryKnockdown01,02` | class effect_group |
| `buffBurningZombie` → `buffBurningElement` → `buffIsOnFire` | burning on hit (Burnt Feral+) | hand item `Action0 Buff` |
| `buffInfectionCatch`, `buffRadiationPool`, `buffInjuryStunned03`, `buffInjurySlow` | projectile / swarm on-hit effects | ammo `Buff` / hand effect |
| `buffInjuryCrippled01` | 300 s; walker/bandit non-players get `AnimatorSetWalkType 5` (limp) | Cripple 'Em mod, Ranger perk |
| `buffShocked` | blocks `EntityZombieCop` priming; 4 s electrical, slows movement | electric sources |
| `twitch_hordestone_zombie` (reference only) | shows entity buffs can scale a live zombie: `HealthMax perc_add -.25`, `EntityDamage`, `BlockDamage`, `LootDropProb`, `ExperienceGain`, `WalkSpeed`, `RunSpeed` | Twitch |
| `twitch_boss` | `SetScale 1.25`, `ExplosionIncomingDamage perc_add -0.75` | Twitch |
| Rage speed | `FallLandBehavior`/`DestroyBlockBehavior` entries with `ragePer`/`rageTime` | class property classes |
| Feral sense | `AIFeralSense` + sandbox `ZombieFeralSense` | class property + option |

There is no dedicated "mutation" or "enrage" buff system. Buffs on zombies run on the server (memory note); `Buffs="a,b"` on an `entity_class` attaches permanent ones at spawn.

---

## 8. Third-party mods in `<game>\Mods`

- **0-XNPCCore 3.4.01** (Dave Taylor): `Config/entityclasses.xml` `<set>` patches replace `AITask`/`AITarget` on `zombieTemplateMale` (adds `EntityNPC` to target classes; `SetNearestEntityAsTarget class=EntityPlayer,0,0,EntityBandit,0,-10,EntityNPC,0,0` drops the rabbit target), `zombieSpider`, `zombieFatCop`, `zombieMutated`, `zombieDemolition` (FatCop, Mutated and Demolition lose `ApproachDistraction` and `EntityAnimal` and gain `EntityNPC` in `ApproachAndAttackTarget`; Spider swaps `EntityAnimal` for `EntityNPC`; the template keeps `EntityAnimal` and adds `EntityNPC`), and several animal classes (bear/wolf/lion/Grace/zombie dog retarget `EntityNPC`/`EntityZombie`; `Faction zombieanimals` for zombie bear/vulture/dog). It also appends its tutorial zombies (`zombieFemaleTutorialT1/T2/T3/T5/T6/T7/T21/T22`, `p=.0125`) to `ZombiesAll`, `ZombiesNight`, `ZombiesForestDowntown(Night)` and defines a `zombieRegularTemplate`. It does **not** patch Rancher, Chuck, Burnt or any Feral/Radiated class directly; classes that inherit `AITask` from `zombieTemplateMale` follow its patch, classes with their own `AITask` do not.
- **0-SCore 3.4.3.826**: Config has no zombie entity classes; `spawning.xml` adds cave biome spawns (`ZombiesAll`, `ZombiesNight`, `ZombiesWasteland`, `ZombieBadassGroup`, `ZombiesWastelandNight`), `utilityai.xml` (NPC packages; vanilla `utilityai.xml` also has an unused `Zombie_Dumb` package, used by no entity), `buffs.xml`, `blocks.xml`, etc. Its C# (`SCore.dll`) is optional for us.
- `Mods\Dementive7D2DMods\ZombiesExpanded` contains only a Unity probe project so far (no XML).
- Vanilla files with no zombie behaviour content: `archetypes.xml` (modular SDCS human characters for the player/NPCs; zombies use fixed prefab meshes instead), `npc.xml`, `dialogs.xml`, `traders.xml`. `utilityai.xml` packages (`Zombie_Dumb`, `Human Basic`, `Human Melee`, `Human Ranged`) are for entities that set `AIPackages` (NPC/survivor templates); no vanilla zombie sets it.

---

## 9. What this means for design (promise-safe vs not)

Safe with XML only (vanilla art and engine):
1. New zombie classes by copying/extending any family, new tags, new XP/HP/speed/resist/loot, new tier classes (Feral..Infernal pattern), recoloured via `<color>` + `MatColor`, custom `AltMats` only with existing materials.
2. Meshes available today without new models: every vanilla prefab above plus the unused `ZSand*`, `ZSnow*`, `ZFrostClaw*`, `ZPlagueSpitter*`, `ZCrawlerRadiated`.
3. New ranged attacks by cloning a hand item: `Class=Vomit` + a new projectile ammo item (Projectile class with `Buff`, `Explosion` using existing `ParticleIndex`, `Velocity/Gravity/FlyTime`), or `Class=SpawnEntity` with any `Entity` class (summoner), wired through `RangedAttackTarget itemType=1` in `AITask` (params in 2.1).
4. Detonators: any zombie with `Class=EntityZombieCop` plus `Explosion`, `ExplodeDelay`, `ExplodeHealthThreshold`, `SoundExplodeWarn`, `SoundTick`. The fuse timer and blast are in `OnUpdateEntity` and do not need the prefab's `Detonator` component; that component only drives the fuse light, and its absence just logs "PrimeDetonator found no Detonator component" **[IL]** (`EnumBodyPartHit.Special = 0x400` is the detonator hit-zone; `physicsbodies.xml` has no `E_BP_Special` collider, so it must come from the prefab **(inferred)**; on other meshes expect HP-threshold priming only, via `ExplodeHealthThreshold`).
5. On-hit statuses: any buff on the hand item (`Action0 Buff`) or in a hit trigger; buff-driven zombie modification (speed, HP, size, particles) via buffs and `Buffs` property; burning/radiation/stun/slow/infection already exist as buff names.
6. Spawn control: ambient (`spawning.xml`), gamestage-scaled (patch `...HordeStageGS*` groups), POI/horde groups, blood moon (`feralHordeStageGS*`), scouts (`scoutHordeStageGS*`).

Needs C#/Harmony/new assets (do not promise): new AI behaviours, a real "freeze/slow aura" from Frostclaw (use buffs on hit instead), screamer behaviour changes beyond swapping groups, new explosion particle indices, new model/rig/animation, climbing/burrowing/teleport, new `EntityXxx` classes, per-zombie visual shader flags beyond `MatColor`.

Gotchas for multiplayer/server: zombies are server-simulated; AI tasks, hand-item actions, `Explode`, and zombie-side buffs run on the server (so a zombie-only XML pack is mainly a server concern; clients still need any new Localization keys, meshes and icons, **(inferred)**). `SpawnEntity` creates the entity server-side with the spitter's attack target.
