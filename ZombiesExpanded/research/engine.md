# Zombie engine survey (7 Days to Die V3.4, Assembly-CSharp)

Purpose: a factual map of the engine code behind zombies, so the "Zombies Expanded" design only promises what can be built.

Source tags used below:
- **[IL]**: read from the ildasm dump (method bodies or signatures).
- **[XML]**: read from vanilla `Data/Config/*.xml`.
- **[inf]**: inferred, not proven by IL. Verify in game before relying on it.

All Assembly-CSharp members are public in V3.x, so "private" fields below are reachable directly.

---

## 0. The rules that shape every design decision

1. **AI exists only on the server.** `EntityAlive.Awake` builds `aiManager = new EAIManager(this)`, `navigator` and `hasAI = true` only when `ConnectionManager.Instance.IsServer` and the entity is not an `EntityPlayer`. Clients have `aiManager == null` for zombies. [IL]
2. **Movement speed, rage, target choice, attacks, explosions and loot are decided on the server.** Clients receive position, animator parameters, damage responses, buffs and cvars. [IL]
3. **Buffs tick on every machine.** `EntityAlive.OnUpdateEntity` calls `Buffs.Tick()` unconditionally, so buff `triggered_effect`s run on clients for remote zombies too. That is how vanilla shows fire particles on zombies. [IL]
4. **Buffs and cvars on zombies are not saved.** `EntityBuffs.Write` is only called from player-data save code and `NetPackageEntityStatsBuff.Setup`. A zombie written to a chunk save comes back without its buffs and cvars. `EntityEnemy.IsSavedToFile` returns false for living `EnumSpawnerSource.Dynamic` (3) spawns, so those are never saved anyway. Biome, static-spawner and sleeper zombies are saved. [IL]
5. **A client that starts tracking a zombie late does not get `onSelfBuffStart`.** The periodic sync sends each `BuffValue` with its `buffFlags`, which include `Started`. `EntityBuffs.Read` replaces the list, and `Tick` only fires `onSelfBuffStart` when `Started` is false. Only clients that were already tracking the zombie when the server added the buff (the `NetPackageAddRemoveBuff` path) run `AddBuff` locally and get the start event. See §5 for the workaround. [IL]

---

## 1. Class hierarchy and `Class` values

```
Entity : MonoBehaviour
 └ EntityAlive
    └ EntityEnemy                       (abstract)
       ├ EntityHuman                    <- all shared zombie logic lives here
       │  ├ EntityZombie                (Class="EntityZombie")
       │  │  └ EntityZombieCop          (Class="EntityZombieCop")
       │  └ EntityBandit
       ├ EntityEnemyAnimal              (Class="EntityEnemyAnimal")
       │  ├ EntityZombieDog             (Class="EntityZombieDog")
       │  └ EntityAnimalSnake
       └ EntityFlying
          └ EntityVulture               (Class="EntityVulture")
             └ EntitySwarm              (Class="EntitySwarm", insect/bee swarm)
```
[IL] (class `extends` lines). `EntityClass.Init` resolves the `Class` property with `Type.GetType(value)`, so assembly-qualified names from mods work. 0-XNPCCore on this machine ships `Class="EntityAliveSDX, SCore"`. [IL] [XML]

### What each class overrides [IL]
- **EntityZombie**: only `AimingGun` (property). There is no screamer, spider, frostclaw or spitter class in V3.4.
- **EntityHuman** (all zombies inherit this):
  - Speed: `GetMoveSpeed()` and `GetMoveSpeedAggro()`, plus `MoveSpeedPatternTick()` with the `MoveSpeedPattern` list that charged and infernal zombies use.
  - Rage: `StartRage(float speedPercent, float time)` and `StopRage()`, the `moveSpeedRagePer` field, and the statics `rageChance`, `superRageChance` and `SetupRageChance(float,int)`.
  - Movement and blocks: `UpdateJump`/`EndJump`, `ExecuteFallBehavior`, `ExecuteDestroyBlockBehavior`.
  - Crawler collider: `TurnIntoCrawler()` (resizes the BoxCollider and sets `bCanClimbLadders`).
  - Other overrides: `SetupHandItem()`, `IsStormEffected()`, `BuffAdded`, `DamageEntity`, `ProcessDamageResponseLocal` (rage roll, server only), and `OnAddedToWorld`, which sets `timeToDie` for some spawner sources.
- **EntityEnemy**:
  - Fields and spawn state: `IsHordeZombie`. `PostInit` sets `IsBloodMoon` from `AIDirector.BloodMoonComponent.BloodMoonActive`.
  - Overrides: `IsSavedToFile`, `canDespawn`, map icon, `isDetailedHeadBodyColliders`, `isGameMessageOnDeath`, `OnEntityTargeted`, `DamageEntity`.
- **EntityZombieCop** (Class for `zombieFatCop*`, `zombieMutated*` (spitter) and `zombieDemolition`) [XML]:
  - Detonator fields: `isPrimed`, `explodeDelay`, `explodeHealthThreshold`, `ticksToExplode`, plus warn and tick sounds.
  - Methods: `PrimeDetonator()`, `HandlePrimingDetonator(float)`, `OnUpdateEntity`, `GetMoveSpeed`/`GetMoveSpeedAggro`, `IsAttackValid`, `ProcessDamageResponseLocal` (a hit on `EnumBodyPartHit.Special` with `DamageSource.canHitSpecialBodyParts` primes it), `CopyPropertiesFromEntityClass` (`ExplodeDelay`, `ExplodeHealthThreshold`, `SoundExplodeWarn`, `SoundTick`).
  - On detonation: `GameManager.ExplosionServer(pos, blockPos, rot, EntityClass.explosionData, entityId, 0, false)`, then `SetDead()`. `explosionData` comes from the entity class `<property class="Explosion">`.
- **EntityZombieDog** (`EntityEnemyAnimal`): `timeToDie`, `Init`, `OnUpdateLive`, `GetMaxAttackTime`, `OnEntityTargeted`.
- **EntityEnemyAnimal**: owns its `Animator`, overrides `updateTasks` and `CanDamageEntity`.
- **EntityVulture**: its own flight state machine in `updateTasks()` (`State`, `FindTarget()`, `AttackAndAdjust`, battle fatigue). It uses no EAI tasks. `EntitySwarm` adds `dissipateDelay`.

### "Special" zombies are XML, not code [XML]
| Zombie | C# class | What makes it special |
|---|---|---|
| Screamer (`zombieScreamer*`) | EntityZombie | Nothing in its class. Summoning is `AIScoutHordeSpawner` (§3). |
| Spider (`zombieSpider*`) | EntityZombie | `WalkType=22` (`cWalkTypeSpider`), `CanClimbVertical=true`, `JumpMaxDistance=7,9`, AITask `Leap`. |
| Chuck / Frostclaw (`zombieChuck*`, `zombieFrostclaw*` extends Chuck) | EntityZombie | `RangedAttackTarget startAnimType=2;itemType=1;...`, HandItem Action1 `Class=Vomit` with `ammoProjectileZombieBoulder`. |
| Rancher / Plague Spitter (`zombieRancher*`, `zombiePlagueSpitter*`) | EntityZombie | `RangedAttackTarget itemType=1`, HandItem Action1 `Class=SpawnEntity Entity=animalInsectSwarm`. |
| Fat cop | EntityZombieCop | HandItem Action1 `Class=Vomit` with `ammoProjectileZombieVomit`, plus the explode logic. |
| Mutated (spitter) | EntityZombieCop | Vomit with `ammoProjectileZombieMutated`, `DestroyArea`. |
| Demolisher | EntityZombieCop | Tags include `boss`. Chest charge = special body part, then explode. |
| Crawler (`zombieSteveCrawler`) | EntityZombie | Spawn walk type is a crawler. |

Named tag groups: `EntityClass.CalculateEntityTier` uses the statics `strongTag="strong"`, `specialTag="special"`, `feralTag="feral,animalFeral"`, `radiatedTag="radiated"`, `eliteTag="charged,infernal"` and `droneTag`. They feed `EntityTierTypes` / `EntityFactory.MaxEntityTier`, which caps spawns to a max tier with `GetEntityClassWithinMaxTier`. [IL]

---

## 2. Lifecycle hooks (where to Harmony)

### Creation order (same code on server and clients) [IL]
1. `EntityFactory.CreateEntity(EntityCreationData)`
   - It calls `CreateEntityOperation.Start(ecd, true)` and then `CreateEntityOperation.CompleteEntity()`.
   - Overloads you can call yourself:
     - `CreateEntity(int _et, Vector3 _transformPos)`
     - `CreateEntity(int _et, Vector3 _transformPos, Vector3 _rotation)`
     - `CreateEntity(int _et, int _id, Vector3, Vector3)`
     - `CreateEntity(int _et, Vector3, Vector3, int _spawnById, string _spawnByName)`
   - `CreateEntityAsync(ecd)` also exists.
2. `CreateEntityOperation.LoadAssets`:
   - Resolves `EntityClass` and applies `GetEntityClassWithinMaxTier`.
   - `EntityInstanceAssets.Load` loads the `Prefab` (the "Z" root prefab).
   - `EModelInstanceAssets.Load` loads the `Mesh` and picks the `AltMats` material.
3. `CompleteEntity`:
   1. Instantiates the prefab and runs `EntityFactory.addEntityComponent(go, ec.classname.FullName)`.
   2. **`Entity.Init(int _entityClass, EntityInstanceAssets _assets, EModelInstanceAssets _eModelAssets)`**
      - `Entity.InitCommon()`
        - Runs **`CopyPropertiesFromEntityClass()`** (virtual, see below) and `InitializeBagFromLootList()`.
        - `EntityHuman.InitCommon` also calls `TurnIntoCrawler()` for crawler walk types.
      - `Entity.InitEModel(assets)`
        - `AddComponent(ec.modelType)`, then **`EModelBase.Init(World, Entity, EModelInstanceAssets)`**.
        - That runs **`createModel(World, EntityClass)`**, which instantiates `Mesh`, applies the AltMat, and applies `MatColor` emissive.
        - Then `createAvatarController(EntityClass)`, which adds the `AvatarController` type by name.
      - `PhysicsInit()`
      - `EntityAlive.Init` then runs `InitStats()`, `switchModelView` and `InitPostCommon()`. InitPostCommon adds the class `Buffs` list and sets `hasAI` for AIPackages.
   3. Name and skin: `GUIHUDEntityName` (pref-gated), `SetEntityName(ecd.entityName)`, `EModelBase.SetSkinTexture`.
   4. Location: `InitLocation(pos, rot)`.
   5. Size: `SetScale(ec.SizeScale)` if ≠ 1, then `SetScale(ecd.overrideSize)` if ≠ 1, then `SetHeadSize(ecd.overrideHeadSize)`.
   6. **`Entity.PostInit()`**
      - Runs `EModelBase.PostInit()` and `HandleNavObject()`.
      - `EntityAlive.PostInit` calls `ApplySpawnState()` and **`GameEventManager.Current.HandleSpawnModifier(this)`**. That is vanilla's "add a buff to every new spawn" hook (bighead, dance and so on).
      - `EntityEnemy.PostInit` sets `IsBloodMoon`.
4. **`World.SpawnEntityInWorld(Entity)`**
   1. Invokes the public delegate **`World.EntityLoadedDelegates`** (type `World.OnEntityLoadedDelegate(Entity)`). You can subscribe to it without Harmony; `EntityUnloadedDelegates` also exists.
   2. Adds the entity to `World.Entities` and `EntityAlives`.
   3. Calls `Entity.OnAddedToWorld()`. `EntityAlive.OnAddedToWorld` sets `bSpawned` when not remote, then fires `MinEventTypes.onSelfFirstSpawn` for every non-player. It is fired on clients too, because the check is only `!(this is EntityPlayer)`.
   4. On the server only: `entityDistributer.Add(entity)` (network replication) and `aiDirector.AddEntity`.

**Server versus client:** the same `CreateEntity` path runs on clients when `NetPackageEntitySpawn` arrives. Clients build the zombie from the `EntityCreationData` the server builds when the player starts tracking it. That data carries class, position, `stats`, `bodyDamage`, `entityName`, `skinTexture`, `overrideSize`, `overrideHeadSize`, `headState`, `isSleeper`, `spawnerSource` and holding item. It does **not** carry buffs or cvars. Gate server-only logic with `!entity.isEntityRemote` or `ConnectionManager.Instance.IsServer`. [IL]

**Best hook points:**
- `EntityAlive.PostInit` postfix:
  - Runs on both sides. On the server it runs before `SpawnEntityInWorld`, so anything set there (`SetEntityName`, `OverrideSize`) is in the client's spawn data. [IL]
  - Covers spawns from biome, horde, sleeper, blood moon, game-event and console sources, and zombies reloaded from save.
- `World.EntityLoadedDelegates` runs after `PostInit`, on server and clients.
- `EntityAlive.OnEntityDeath` or `ModEvents.EntityKilled` for deaths (§7).
- For a virtual chain (`CopyPropertiesFromEntityClass`, `PostInit`), patch the `EntityAlive` implementation. Subclasses call `base` (seen for `EntityHuman.InitCommon`, `EntityEnemy.PostInit`, `EntityZombieCop.ProcessDamageResponseLocal`). [IL]

### Reading custom `<property>`s
- `EntityClass.Properties` is a `DynamicProperties` that keeps **every** `<property>`, including unknown ones.
- Read them with `entity.EntityClass.Properties.GetString("ChampionPool")`, `.Values.TryGetValue`, `.ParseFloat(name, ref f)`, or `.Classes` for `<property class="X">` blocks. `Entity.EntityClass` is a getter; `EntityClass.list[entity.entityClass]` also works. [IL]
- `extends` copies the parent's properties (`EntityClass.CopyFrom(_other, exclude)`). The loader honours an `ignore` attribute.
- Effect groups **do** extend for entity classes. The `Tags` property does not inherit. [XML comments, IL loader strings]
- `entityclasses.xml` also accepts top-level `<color name=".." value="r,g,b,a"/>` (into `EntityClass.sColors`) and `replace_properties`. [IL]

---

## 3. AI

### EAIManager [IL]
- Fields: `tasks` and `targetTasks` (`EAITaskList`), `feralSense`, `groupCircle`, `noiseSeekDist`, `pathCostScale`, `seeOffset`, `interestDistance`, and the static `FeralSense` (game pref).
- `Update()` runs `targetTasks.OnUpdateTasks()` then `tasks.OnUpdateTasks()`.
- `EAITaskList` is a classic priority + `MutexBits` scheduler: `CanExecute`, `Continue`, `Start`, `Update`, `Reset`, `executeDelay`.
- `EAIBase` contract:
  - `virtual void Init(EntityAlive)`
  - `virtual void SetData(Dictionary<string,string>)`
  - `abstract bool CanExecute()`
  - `virtual bool Continue()`
  - `Start()`, `Reset()`, `Update()`, `IsContinuous()`
  - fields `manager`, `theEntity`, `MutexBits`, `executeDelay`
  - helpers `GetData(data, name, ref float/int)`
- Other methods: `GetTasks<T>()`, `GetTargetTask<T>()`, `ClearTaskDelay<T>()`, `StopAllTasks()`, `SleeperWokeUp()` (zeroes task delays), `DamagedByEntity()`, `SetTargetOnlyPlayers(float)`.
- `EAIManager.AddItemTasks(ItemClass)` parses an **item's** `AITask` property; `Weapon.Equip` calls it. Held items can therefore inject AI tasks. [IL]

### Parsing (`EAIManager.CopyPropertiesFromEntityClass`) [IL]
- It reads `AIFeralSense`, `AIGroupCircle`, `AINoiseSeekDist`, `AISeeOffset` and `AIPathCostScale` (a range).
- **Format A**, the single property `AITask` / `AITarget` with a `|`-separated list. In `ParseTasks`:
  - Each entry is split at the **first space**: the name comes before it, and the rest goes through `DynamicProperties.ParseData` as `key=value;key=value`.
  - The priority is the list order.
- **Format B** is used only when `AITask` is empty. It reads `AITask-1`, `AITask-2`, ... (and `AITarget-N`) until a key is missing **or empty**, with parameters in the `data="k=v;k=v"` attribute (`ParseKeyData`).
- Class lookup goes through `EAIManager.CreateInstance(name)`, which calls `EAIManager.GetType(name)`:
  - A hard-coded switch handles the vanilla names.
  - The fallback logs `Log.Warning("EAIManager GetType slow lookup for {0}")` and returns `Type.GetType("EAI" + name)`.
  - A null type throws `Exception("Class '...' not found!")`.

### Adding a custom task
- **XML route:** name the class `EAIChampionCharge` and write `AITask-N value="ChampionCharge, ZombiesExpanded" data="..."`. The lookup becomes `Type.GetType("EAIChampionCharge, ZombiesExpanded")`.
  - The same `Type.GetType` resolution is what makes `Class="EntityAliveSDX, SCore"` work on this install. [IL + XML]
  - That it resolves for EAI names too is [inf], but likely.
  - In the pipe format, write `ChampionCharge,ZombiesExpanded` with **no space**, because the first space starts the data.
  - Every new zombie logs the "slow lookup" warning once per custom task. A prefix on `EAIManager.GetType` that returns your types first avoids the spam.
- **Code route (cleaner):** postfix `EAIManager.CopyPropertiesFromEntityClass(EntityClass ec)`:
  - Build `var t = new EAIChampionCharge(); t.Init(entity); t.SetData(dict); manager.tasks.AddTask(priority, t);`
  - It only runs on the server, because only the server has an EAIManager.

### Vanilla tasks [IL for data keys, inf for behaviour summaries]
| Task (XML name) | Data keys | What it does |
|---|---|---|
| ApproachAndAttackTarget | `class=Type,chaseTime,...` | Paths to the attack target and melees through `EntityAlive.Attack` and `UseHoldingItem(0)`. Also eats corpses and returns home after the chase time. |
| ApproachDistraction | none | Goes to the `EntityAlive.distraction` item (decoys). |
| ApproachSpot | none | Goes to `InvestigatePosition`. |
| BlockIf | `condition=Alert e 0` (types `Alert`, `Investigate`; ops `e`, `ne`) | Blocks lower tasks while the condition holds. |
| BlockingTargetTask | none | Linked from ApproachAndAttack. |
| BreakBlock | none | Hits the block in the way (`moveHelper.BlockedTime`, `CanBreakBlocks`, `HitInfo.blockPos`). |
| DestroyArea | none | Unreachable target: picks a nearby spot and digs (`moveHelper.IsDestroyAreaTryUnreachable`, `UnreachablePercent`). |
| Dodge | `tags,maxXZDistance,cooldown,duration,minRange,maxRange,unreachableRange` | Dodge animation. Not used by vanilla zombies. |
| Leap | `legs` | Leap attack. Used by the spider and feral Chuck. |
| Look | none | Idle look. |
| MeleeAttackTarget | `slot,itemType,startAnimType,releaseDelay,cooldown,duration,minRange,maxRange,unreachableRange,sndStart,sndRelease` | Timed melee. Not used by vanilla zombies. |
| RangedAttackTarget | `itemType,startAnimType,releaseDelay,cooldown,duration,minRange,maxRange,unreachableRange,sndStart,sndRelease` | `StartAnimAction(3000+startAnimType)`, then after `releaseDelay` `UseHoldingItem(itemType)`. |
| RunawayFromEntity / RunawayWhenHurt | `flags,safeFlags,safeDistance,dangerDistance` / `runChance,healthPer,healthPerMax` (+`fleeDistance`) | Flee. |
| Territorial | none | Returns toward `getHomePosition()`. |
| Wander | `exePer,fade,lookMin,lookMax` | Wander. |
| PathTest | none | Debug. |
| *Target:* SetAsTargetIfHurt | `class` | Revenge. |
| SetNearestCorpseAsTarget | `flags,maxDistance2d` | Eat corpses. |
| SetNearestEntityAsTarget | `class=Type,hearDist,seeDist,...` | Main target acquisition. |

`TokenManager` and `AITokenType` (`MeleeAttack`, `RangedAttack`, `ThrowProjectile`) exist with an XML `<array name="TokenManager">`, but no callers of `TryClaimToken` were found. Do not count on attack-slot limiting. [IL]

### Senses, investigate, sleepers, heat [IL]
- **Investigate:** `EntityAlive.SetInvestigatePosition(Vector3 pos, int ticks, bool isAlert = true)`, `ClearInvestigatePosition()`, `HasInvestigatePosition`, `InvestigatePosition`.
  - This is the game's own "go check this spot" call; wandering and scout hordes use it.
  - Also useful: `SetAttackTarget(EntityAlive, int ticks)`, `GetAttackTarget()`, `SetRevengeTarget(EntityAlive)`, `SetAlertTicks(int)`, `IsAlert`.
- **Feral sense:** `EAIManager.CalcSenseScale()` uses the static `EAIManager.FeralSense` (game pref) and `World.IsDaytime`/`IsDark`. The per-class `AIFeralSense` goes into `EAIManager.feralSense`.
- **Noise:** `AIDirector.NotifyNoise(Entity instigator, Vector3 pos, string clipName, float volumeScale)`.
  - It looks the clip up in `AIDirectorData` noise entries (sounds.xml).
  - For tracked players it feeds `PlayerStealth.NotifyNoise`.
  - It also calls `World.CheckSleeperVolumeNoise(pos)` and adds heat through `NotifyActivity`.
  - Zombies hear players through the stealth system (`noisePlayer`). A non-player noise only makes heat and wakes sleepers. To pull zombies to a point, call `SetInvestigatePosition` on each zombie in range.
- **Heat:**
  - Entry point: `AIDirector.NotifyActivity(EnumAIDirectorChunkEvent type, Vector3i pos, float value, float _duration = 720)`. The types are `Campfire, Forge, KillAnimal, Sound, Smell, Carcass, Torch`.
  - Scaling and suppression: the value is scaled by the static `AIDirector.HeatMapSensitivityModifier`. Heat is skipped during a blood moon or a Twitch boss horde.
  - Storage: `AIDirectorChunkEventComponent.NotifyEvent` stores the event per chunk area (`AIDirectorChunkData.AddEvent`).
  - Spawn check: `CheckToSpawn(chunkData)` spawns when `ActivityLevel >= 25` and `RandomFloat < 0.2`. It then applies neighbour cooldowns and calls `SpawnScouts(Vector3 targetPos)`.
- **Screamers / scouts:**
  - `SpawnScouts` picks an entity group by gamestage: `Scouts1`, `Scouts2`, `ScoutsFeral`, `ScoutsRadiated`.
  - It builds an `AIScoutHordeSpawner`, which is added to `scoutSpawnList`.
  - `AIScoutHordeSpawner.UpdateHorde`:
    - When a scout has an attack target and is not stunned, after an 18 s `AttackDelay` it calls `spawnHordeNear`.
    - That runs `AIDirectorChunkEventComponent.CreateHorde(pos)`, which spawns from the `ScoutGSList` group. There is a 12% random factor for extra waves.
    - Without a target it uses `SetInvestigatePosition` toward the heat spot.
  - **Only heat-spawned screamers summon.** A screamer spawned by biome or POI does nothing special.
  - A mod can call `AIDirectorChunkEventComponent.SpawnScouts(pos)` (via `world.aiDirector.GetComponent<AIDirectorChunkEventComponent>()`) or patch `AIScoutHordeSpawner.spawnHordeNear`.
- **Wandering hordes:** `AIDirectorWanderingHordeComponent` with `AIWanderingHordeSpawner`.
  - `SpawnType` is bandit or horde, using the `WanderingHorde` group.
  - Zombies get `IsHordeZombie` and `SetInvestigatePosition`.
  - The spawner sets `lootDropProb` on horde zombies.
- **Blood moon:** `AIDirectorBloodMoonComponent.StartBloodMoon/EndBloodMoon` (hookable). `AIDirectorBloodMoonParty.SpawnZombie` sets `IsBloodMoon` and `lootDropProb`.
- **Sleepers:**
  - State fields: `EntityAlive.IsSleeper`, `IsSleeping`, `IsSleeperPassive`.
  - Wake and pose methods: `ConditionalTriggerSleeperWakeUp()`, `SetSleeperActive()`, `TriggerSleeperPose(int, bool)`, `ResumeSleeperPose()`.
  - Waking sets the flags, plays the pose, calls `aiManager.SleeperWokeUp()` and broadcasts `NetPackageSleeperWakeup`.
  - Thresholds come from the class properties `SleeperSightToSense*`, `SleeperSightToWake*`, `SleeperNoiseToSense`, `SleeperNoiseToWake`.

---

## 4. Movement and combat

### Speed [IL]
- **Day versus night:** `EntityHuman.GetMoveSpeed()` checks, in order:
  - blood moon → `WalkSpeed` applied to `moveSpeedNight`
  - smelling a player → aggro × 0.85
  - storm → aggro × 0.8
  - alert → aggro × 0.65
  - dark → `WalkSpeed`(`moveSpeedNight`)
  - otherwise → `CrouchSpeed` passive applied to `moveSpeed`
  - (`PassiveEffects` 0x85 = WalkSpeed, 0x86 = RunSpeed, 0x87 = CrouchSpeed.)
- **Chasing:** `GetMoveSpeedAggro()`:
  - Picks a game-pref speed table (`ZombieMove`, `ZombieMoveNight`, `ZombieFeralMove`, `ZombieBMMove`; static arrays `moveSpeeds`, `moveRageSpeeds`, `moveSuperRageSpeeds`) using `IsBloodMoon`, `IsFeral`, `IsDark`, spawner source and storm.
  - Interpolates `moveSpeedAggro..moveSpeedAggroMax` by `moveSpeedRagePer`.
  - Applies the **`RunSpeed`** passive and multiplies by `moveSpeedPatternScale`.
  - **Buff `RunSpeed` and `WalkSpeed` passives therefore work** (evaluated on the server).
- **Class properties:** `MoveSpeed`, `MoveSpeedNight`, `MoveSpeedAggro` (`min,max`), `MoveSpeedRand`, `MoveSpeedPanic`, `MoveSpeedPattern` (`delay,scale,...`).
- **Rage:**
  - Rolled in `EntityHuman.ProcessDamageResponseLocal`, server only, scaled by damage relative to 40.
  - Calls `StartRage(speedPercent, time)`: normal rage is `StartRage(0.5+0.5r, 4+6r)` (50–100% for 4–10 s); super rage is `StartRage(2, 30)`.
  - You can call `StartRage` yourself.
- **Walk type:** `EntityAlive.SetWalkType(int)` and `walkType`.
  - Constants: `cWalkTypeFat=1`, `Cripple=5`, `Crouch=8`, `Bandit=15`, `CrawlFirst=20`, `Crawler=21`, `Spider=22`, `Swim=-1`.
  - Animator params `WalkType` and `WalkTypeBlend`.
  - Buff action `AnimatorSetWalkType` exists.

### Jump, climb, block breaking [IL]
- **Jump and climb fields:** `jumpDelay`, `jumpMaxDistance` (props `JumpDelay`, `JumpMaxDistance`), `bCanClimbVertical` (`CanClimbVertical`), `bCanClimbLadders` (`CanClimbLadders`), `CanEntityJump()`, `StartJump()`. The `JumpStrength` passive exists.
- **`EntityMoveHelper` (`entity.moveHelper`):** `CanBreakBlocks`, `BlockedTime`, `BlockedFlags`, `BlockedEntity`, `HitInfo`, `IsUnreachableAbove/Side/SideJump`, `UnreachablePercent`, `IsDestroyAreaTryUnreachable`, `isDigging`, `StartJump(bool calcYaw, float dist, float heightDiff)`, `DigStart(int ticks)`. The static `AllowZombieDigging` also lives here.
- **Block damage** is the HandItem melee `DamageBlock`, scaled by `EntityAlive.GetBlockDamageScale(bool isTerrain)` / `CalculateBlockDamage(...)` and the `BlockDamage` passive.
- **Reactions to breaking or falling:** the class `<property class="DestroyBlockBehavior">` (None/Stumble/Ragdoll weights) and `FallLandBehavior` choose them (`ExecuteDestroyBlockBehavior`, `ExecuteFallBehavior`). Both can trigger rage (`ragePer`, `rageTime`).

### Melee [IL] [XML]
- Zombies hold an invisible `HandItem` (`meleeHandZombie01`, `...Feral`, `...Charged`, `...Infernal`, ...).
  - All of them extend `meleeHandMaster`: Action0 `Class=Melee` (`ItemActionMelee`) with `Delay .8`, `Range 1.65`, `Block_range 2.5`, `DamageEntity`, `DamageBlock`.
- The task calls `EntityAlive.Attack(bool released)`, which calls `UseHoldingItem(0, released)`:
  - Checks `IsAttackValid()`.
  - Plays `SoundAttack` and sets `attackingTime`.
  - Runs `ItemAction.ExecuteAction`.
- Hit timing comes from the attack clip: an animation event calls `AnimationEventBridge.Hit`, then `AvatarController.SetAttackImpact()`. `ItemActionMelee.OnHoldingUpdate` waits for `IsAttackImpact()` and then hits through `ItemActionAttack.Hit`.
- Infection and injury buffs are `onSelfAttackedOther` triggered effects on the hand item.
- Attack interval: `AttackTimeoutDay` / `AttackTimeoutNight` (`GetAttackTimeoutTicks()`), plus `AttacksPerMinute`.

### Ranged zombies [IL] [XML]
- `RangedAttackTarget` → `EntityAlive.StartAnimAction(3000 + startAnimType)` → `AvatarZombieController.StartAction(int)`. That sets animator int `Attack` = value and fires `AttackTrigger`; values < 3000 fall back to the normal melee attack.
- Then, after `releaseDelay`, it calls `UseHoldingItem(itemType=1)` on HandItem **Action1**:
  - `Class=Vomit` (`ItemActionVomit`): projectile `Magazine_items` ammo (`ammoProjectileZombieVomit`, `...Boulder`, `...Mutated`), `Hitmask_override`, `Sound_warning`, `WarningDelay`.
  - `Class=SpawnEntity` (`ItemActionSpawnEntity`): spawns `Entity=animalInsectSwarm` (plague spitter).
- A new ranged zombie is therefore XML-only: a new hand item Action1 plus a `RangedAttackTarget` entry, provided the model's animator has a suitable `Attack` 300x state.

### Animator (zombie) [IL]
- Main types: `AvatarZombieController : AvatarHumanController : AvatarController`.
- **Parameter names** (hashed in `AvatarController` statics):
  - Attacks: `Attack`, `AttackBlend`, `AttackTrigger`, `SpecialAttack2`, `Rage`
  - Hits: `HitTrigger`, `HitBodyPart`, `HitDirection`, `HitDamage`, `CriticalHit`
  - Stun: `BeginStunTrigger`, `EndStunTrigger`, `StunType`, `StunBodyPart`
  - Crawler: `ToCrawlerTrigger`
  - Electrocution: `ElectrocuteTrigger`, `IsElectrocuted`
  - Dodge: `DodgeTrigger`, `DodgeBlend`
  - Movement: `WalkType`, `WalkTypeBlend`, `Forward`, `Strafe`, `MovementState`, `JumpTrigger`, `JumpStart`, `JumpLand`, `IsClimbing`
  - Sleeper: `SleeperPose`, `SleeperTrigger`
  - Corpse eating: `BeginCorpseEat`, `EndCorpseEat`
  - Death: `DeathTrigger`, `IsDead`, `IsAlive`
  - Other: `PreventAttack`, `Random`
- **Melee attack index:** `StartAnimationAttack()` computes `Attack` from walk type, arm loss and random (tens and hundreds offsets).
- **Special animation methods:** `StartAnimationSpecialAttack2()` and `StartAnimationRaging()` (triggers).
- **Network sync:** setting a parameter on the server through `AvatarController._setTrigger/_setInt/_setFloat/_setBool(hash, value, netsync=true)` queues it into `changedAnimationParameters`, which is synced to clients.
- **Dedicated servers:** the server uses `AvatarControllerDummy` with Animators disabled only when the class has neither `RootMotion` nor `HasRagdoll`. Zombies have both, so they keep a real animator on dedicated servers.

### Stun, knockdown, ragdoll [IL]
- **Thresholds:** `EntityAlive.damageEntityLocal` picks `DamageResponse.Stun` and `StunDuration` from:
  - `KnockdownProneDamageThreshold` / `KnockdownProneStunDuration`
  - `KnockdownKneelDamageThreshold` / `KnockdownKneelStunDuration`
  - refill rates and `bodyDamage.StunKnee`/`StunProne`
  - `DamageSource.CanStun`
- **Applying it:** `ProcessDamageResponseLocal` (runs on every machine, from `NetPackageDamageEntity`) does `avatarController.BeginStun(stun, bodyPart, hitDir, crit, random)`, `SetStun(stun)` and `DoRagdoll`.
- `EnumEntityStunType`: `None, Kneel, Prone, Getup, Stumble, StumbleBreakThrough, StumbleBreakThroughRagdoll`. `BodyDamage.CurrentStun` and `StunDuration` hold the current state.
- **Ragdoll:**
  - `EntityAlive.DoRagdoll(in DamageResponse)` / `DoRagdoll(in DamageResponse, EModelBase.RagdollMode)` → `EModelBase.DoRagdoll(in dr, mode, stunTime)`, which broadcasts `NetPackageEntityRagdoll`.
  - `BeginDynamicRagdoll(DynamicRagdollFlags, FloatRange)` also exists.
  - The buff action `Ragdoll` (`duration`, `force`, `massScale`, `scaleY`) calls `DoRagdoll`.
- **Electrocution:**
  - `Electrocuted = true` plays a 0.6 s animation.
  - `AvatarZombieController.Electrocute(bool)` sets the material property `_ElectricShockEnabled` (`ElectrocuteEnabledProperty`).

### Crawlers [IL]
- **Leg loss to crawler:**
  - `ApplyLocalBodyDamage` sets `bodyDamage.ShouldBeCrawler` from leg-loss flags or from `DamageResponse.TurnIntoCrawler`.
  - `ExecuteDismember` → `SetupCrawler()` → `SetWalkType(21)` → `AvatarController.TurnIntoCrawler()` (`ToCrawlerTrigger`).
  - Thresholds: `LegCrawlerThreshold` and `LegCrippleScale` (Cripple walk type 5 from the `cCrippledLegL/R` flags).
- **Clean, synced way to force a crawler** (vanilla `GameEvent.SequenceActions.ActionEnemyToCrawler`):
  ```csharp
  var dr = DamageResponse.New(false);
  dr.Source = new DamageSource(EnumDamageSource.External, EnumDamageTypes.Bashing); // as vanilla (0, 3)
  dr.Source.DismemberChance = 1; dr.Strength = 1;
  dr.CrippleLegs = true; dr.Dismember = true; dr.TurnIntoCrawler = true;
  dr.HitBodyPart = EnumBodyPartHit.UpperLegs;   // 0x30
  zombie.ProcessDamageResponse(dr);             // broadcasts NetPackageDamageEntity
  ```

### Dismemberment [IL] [XML]
- Handled by `DismembermentManager` (static helpers plus `instance.parts`) and `AvatarZombieController`: `MakeDismemberedPart`, `RemoveLimb`, `SpawnLimbGore`, `ActivateDetachableLimbs`, `scaleOutChildBones`, `setLimbShaderProps`, `hideDismemberedPart`.
- **Both techniques are used:**
  1. Shader cut-off floats on the body material: `_LeftLowerLeg`, `_LeftUpperLeg`, `_RightLowerLeg`, `_RightUpperLeg`, `_LeftLowerArm`, `_LeftUpperArm`, `_RightLowerArm`, `_RightUpperArm`. Child bones are also scaled out.
  2. **Separate gore prefabs** per class. Each property is `DismemberTag_L_<Part>Gore` with value `Zombie/Dismemberment/Blade/Head;...`, parented under a `DynamicGore` node at the bone. The data keys are `type=blade|blunt+target=<bone>+atp+detach+mask+msb+sfv+asp+scale`, and `linked` reuses another part.
- Radiated gib caps use `_IsRadiated` / `_Irradiated`. Fade uses `_Fade`.

---

## 5. What reaches clients, and how to tag a zombie

### Automatic sync [IL]
- **Spawn data:** `EntityCreationData` is sent when a player starts tracking (see §2). It includes `entityName`, `overrideSize`, `overrideHeadSize` and `bodyDamage`. Buffs and cvars are not included.
- **Buffs:**
  - `EntityBuffs.AddBuff(string _name, int _instigatorId = -1, bool _netSync = true, bool _fromElectrical = false, float _buffDuration = -1)`.
  - On the server it sends `NetPackageAddRemoveBuff` to all clients immediately; each client runs `AddBuff` locally, so `onSelfBuffStart` fires there. `RemoveBuff` works the same way.
  - Clients not yet tracking the zombie drop the package. Package arrives before the zombie spawns on the client → dropped [inf].
- **Periodic full sync:**
  - `EntityStats.Tick`/`TickWait` on the owner sends `NetPackageEntityStatsBuff` about every 5.5 s (`netSyncWaitTicks` = 10 × 0.5 s) [IL constants, timing inf].
  - It carries **all active buffs**, including their `Started` flag, plus **only changed cvars** (delta against `CVarsLastNetSync`; `.`-prefixed cvars are never sent).
- **Cvars:**
  - `SetCustomVar(name, value, _netSync = true, op, _forceSendToClients = false)`.
  - On a server-owned zombie a cvar is pushed immediately (`NetPackageModifyCVar`) only if its name starts with `%` or `_forceSendToClients` is true. Names starting with `.` or `_` are never pushed.
  - Otherwise the cvar waits for the 5 s delta sync, and **a late-tracking client never receives an unchanged cvar.**
- **Damage responses** go through `NetPackageDamageEntity` to tracked players, so stun, dismember, crawler and death replay on clients.
- **Ragdoll:** `NetPackageEntityRagdoll`.
- **Animator parameters:** synced through `changedAnimationParameters`.
- **Alive flags:** `NetPackageEntityAliveFlags` carries ApproachingEnemy/Player, AimingGun, Spawned, Jumping, IsBreakingBlocks, IsAlert, IsGodMode and Crouching.
- **Explosions:** `GameManager.ExplosionServer` replicates as `ExplosionClient`.
- **Not synced after spawn:** `Entity.SetScale` alone (local; `MinEventActionSetScale` also sets `OverrideSize`, which only reaches clients that start tracking later), and `SetEntityName` after the spawn packet (`NetPackagePlayerStats` is only sent for `EntityPlayer`) [inf from `updatePlayerList`].

### Recommended tagging pattern
1. Roll the champion on the server in an `EntityAlive.PostInit` postfix, guarded by `!isEntityRemote`. At that point:
   - Set `OverrideSize`/`SetScale` and, if you want, `SetEntityName`. Both travel in the spawn data.
   - Add a buff `buffZEChampion<Type>` with a long or infinite duration. A buff is resent in full every sync; a cvar is not.
   - Store the champion type somewhere persistent, because buffs are lost when a saved zombie reloads. Options: re-roll deterministically from `entityId`, keep a mod-side save keyed by `entityId`, or encode it in `entityName`, which is saved in `EntityCreationData`.
2. **Client visuals must not rely on `onSelfBuffStart` alone** (rule 5 in §0). Use one of:
   - (a) XML only: put the attach actions on `onSelfBuffUpdate`, guarded by a local `.cvar` flag (`.` cvars are client-local and never overwritten by sync) [inf].
   - (b) C# (more robust): a small client component, or an `EntityAlive.OnUpdateLive` postfix, that applies the material, particles and nameplate once when `Buffs.HasBuff("buffZEChampion...")` turns true, and removes them when it turns false.

### Radiated / charged / infernal looks [IL] [XML]
- **Radiated** is a different `Mesh` prefab and `AltMats` (`HD_*_Radiated*.mat`) chosen by the entity class. `_IsRadiated` / `_Irradiated` are only set on gib-cap and eye materials (`_InitDismembermentMaterials`, `setUpEyeMats`) when the entity has the `radiated` tag.
- **Charged / infernal / radiated glow:**
  - Property `MatColor` names a top-level `<color name="charged" value="0,.8,3,.7"/>` in entityclasses.xml (also `radiated`, `infernal`).
  - `EModelBase.createModel` instantiates the material and sets `_Emissive = 1` and `_EmissiveColor = color` (alpha + 1 = emissive power).
  - It runs when the model is created on each machine, so a new `<color>` plus `MatColor` on a custom class is fully supported.
  - Recolouring an existing zombie at runtime needs C#: set `_EmissiveColor` on the instanced material of `emodel.meshTransform`'s renderers on each client [inf].
- **Electric shock:** `_ElectricShockEnabled` through `AvatarZombieController.Electrocute(bool)`.
- **Fire:**
  - The buff `buffIsOnFire` (added by `buffBurningElement` and others) does `AttachParticleEffectToEntity particle="p_onFire" parent_transform="LOD0" shape_mesh="true"` on `onSelfBuffStart` **and** `onSelfEnteredGame`.
  - `RemoveParticleEffectFromEntity` runs on remove and death.
  - Burning zombies use `buffBurningZombie` and the `zombieBurnt` HandItems.

---

## 6. Model structure accessors [IL]
- **`EModelBase` fields:**
  - Roots: `modelTransformParent`, `modelTransform`, `meshTransform` (tag `E_Mesh` or child `LOD0`), `bipedRootTransform` (tag `E_BP_BipedRoot`, or `Bip001`/`Bip01`).
  - Body: `bipedPelvisTransform` (partial name `pelvis`/`Hips`/`hip`), `headTransform` (tag `E_BP_Head`), `neckTransform`, `neckParentTransform`, `NavObjectTransform` (tag `E_BP_Eye` / `IconTag`).
  - Other: `pelvisRB`, `avatarController`, `matPropBlock`.
  - **There is no `bipedTransforms` list in V3.4.**
- **Methods:**
  - Transforms: `GetHeadTransform()`, `GetPelvisTransform()`, `GetRightHandTransform()`, `GetModelTransform()`, `GetHitTransform(DamageSource)`, `NeckTransform`.
  - Ragdoll: `DoRagdoll`, `StartRagdoll(float)`, `SetRagdollState`, `IsRagdollActive`.
  - Display: `SetVisible`, `SetFade(float)`, `SetSkinTexture(string)`, `ForceHeadState`, `SetHeadScale`.
- Other bones: `GameUtils.FindDeepChild(transform, "Spine1")` / `FindDeepChildActive`.
- **`AttachParticleEffectToEntity`** (attributes `particle`, `parent_transform`, `local_offset`, `local_rotation`, `oneshot`, `shape_mesh`, `sound`):
  - `parent_transform` values:
    - `LOD0` = `meshTransform`
    - `.item` = right-hand item child
    - `.body` = `Graphics/Model` → `body`/`torso`/`Spine1`, or the pelvis
    - `.head` = `GetHeadTransform()`
    - anything else = `GameUtils.FindDeepChild(entity.transform, name)`, i.e. bone names such as `Head`, `Spine1`, `RightHand`, `LeftHand`
  - The instance is named `Ptl_<prefab>` and registered with `EntityAlive.AddParticle`, so `RemoveParticleEffectFromEntity` can remove it.
  - The `particle` value maps to `ParticleEffects/<name>.prefab`; mod bundles use the `#@modfolder:` path [inf].
- **`AttachPrefabToEntity`** (`prefab`, `parent_transform`, `local_offset`, `local_rotation`, `local_scale`): parents to `FindDeepChild(name)` and names the instance `tempPrefab_<name>`.
- **Scale:**
  - `Entity.SetScale(float)` scales `ModelTransform`, fixes joints, and rescales `physicsHeight` and the colliders.
  - `EntityAlive.OverrideSize` is sent in spawn data.
  - The class property `SizeScale` is applied on creation.
  - Buff `SetScale scale=".."` (vanilla `twitch_boss` uses 1.25). `SetHeadSize`/`OverrideHeadSize` also exist.

---

## 7. Death, loot, extra spawns [IL]
- **Death flow:**
  - `EntityAlive.Kill(DamageResponse)` and the fatal damage path both lead to `ClientKill(DamageResponse)`.
  - `ClientKill` sets `entityThatKilledMe`, calls `SetDead()` and `Buffs.OnDeath(killer, item, blockKilled, tags)`, which fires `onOtherKilledSelf` and `onSelfDied`.
  - It then calls `HandleClientDeath`, and **`OnEntityDeath()`**:
    - Score, `AwardKill` if not remote, `ParticleOnDeath`, the game message.
    - **`ModEvents.EntityKilled.Invoke(SEntityKilledData)`**, the official mod event.
    - `dropItemOnDeath()`.
  - On the server it also calls `AwardKillXPServer` and `PartyShareKillServer`.
  - `OnEntityDeath` runs on clients too, so check `IsServer` in handlers.
- **Loot bag:**
  - `dropItemOnDeath` rolls `lootDropProb` × the killer's `LootDropProb` passive (0x50) and calls `Entity.DropBagServer()`, which is server only.
  - `DropBagServer` picks `EntityClass.LootDropPick(rand)` from `LootDropEntityClass` (`EntityLootContainerRegular,1,...`), then `EntityFactory.CreateEntity` and `World.SpawnEntityInWorld`.
  - The class property is `LootDropProb`. Hordes and blood moon set `lootDropProb` at spawn.
  - A champion can set `entity.lootDropProb = 1` on the server and use a custom `LootDropEntityClass` on a champion entity class, or call `DropBagServer()` directly.
- **Corpse:**
  - It stays `TimeStayAfterDeath` seconds; `OnDeathUpdate` counts it down and plays `ParticleOnDestroy`.
  - It can be hit using `DeadBodyHitPoints`/`DeathHealth` and harvested with `<drop event="Harvest|Destroy">` in the entity class.
  - Ragdoll on death uses `RagdollOnDeathChance`/`HasRagdoll`. `corpseBlockValue`/`corpseBlockChance` exist.
- **Spawn an extra entity (server):**
  ```csharp
  int id = EntityClass.FromString("zombieSteveCrawler");
  var e = (EntityAlive)EntityFactory.CreateEntity(id, pos, new Vector3(0, yaw, 0));
  e.SetSpawnerSource(EnumSpawnerSource.Dynamic);   // not saved, despawns like hordes
  GameManager.Instance.World.SpawnEntityInWorld(e);
  ```
  Replication is automatic: `SpawnEntityInWorld` calls `entityDistributer.Add` on the server. To "split into crawlers", spawn normal zombies and run the crawler `DamageResponse` from §4 on them, or spawn crawler classes.
- **Explosion:**
  - Signature: `GameManager.ExplosionServer(Vector3 _worldPos, Vector3i _blockPos, Quaternion _rotation, ExplosionData _explosionData, int _entityId, float _delay, bool _bRemoveBlockAtExplPosition, ItemValue _itemValueExplosionSource = null)`.
  - `new ExplosionData(DynamicProperties props, MinEffectController effects = null)` reads the `Explosion` property class: `ParticleIndex`, `Duration`, `RadiusBlocks`, `BlockDamage`, `BlockTags`, `RadiusEntities`, `EntityDamage`, `BlastPower`, `Buff`, `IgnoreHeatMap`, `DamageType`.
  - `EntityClass.explosionData` is pre-parsed from the class's `<property class="Explosion">`.
  - The `Explode` buff action is server only (see memory notes).

---

## 8. Built-in "elite/boss" support worth reusing
- **Tags:** `boss` is only used in XML (demolisher, zombie boar, Grace); no code reads `"boss"`/`"elite"`. `EntityClass.eliteTag` = `charged,infernal` only feeds tier capping. [IL] [XML]
- **Boss health bar (`XUiC_TargetBar`, window `windowTargetBar`):**
  - Bindings: `name`, `current`, `currentwithmax`, `fill`, `isboss`, `isnotboss`, `minioncount`, `boss_sprite`. The window `visibility` is `never|godmode|always` (vanilla `godmode`, plus a sandbox option).
  - Boss mode is shown when `GameEventManager.Current.CurrentBossGroup` is set. `name` = `Localization.Get(EntityClass.entityClassName)` or `BossGroup.BossName`, which is also the localized class name. **`EntityAlive.EntityName` is never shown**, so a per-zombie champion name needs a postfix on `XUiC_TargetBar.GetBindingValueInternal(ref string value, string bindingName)` or your own controller. [IL] [XML]
- **`BossGroup` / `GameEventManager.SetupBossGroup(EntityPlayer target, EntityAlive boss, List<EntityAlive> minions, BossGroup.BossGroupTypes type, string bossIcon)`** (`Standard`, `ImmortalBoss`, `ImmortalMinions`, `Specialized`; synced with `NetPackageBossEvent`): this is Twitch logic.
  - `HandleLiveHandling` despawns the whole group (`DespawnAll`) when the target player leaves server range.
  - `HandleAutoPull`/`HandleTeleportList` teleport minions.
  - It is not suitable as a generic champion bar without patches. [IL]
  - It can be triggered data-only through gameevents.xml actions `SpawnEntity` (`add_buffs`, `add_to_group`) and `SetupBossGroup` (`boss_group_name`, `minion_group_name`, `boss_icon1`, `group_type`), via `GameEventManager.HandleAction(name, requester, entity, twitchActivated, ...)`. [IL] [XML]
- **Nameplate above the head:**
  - Nav objects. `Entity.AddNavObject(string navObjectName, string overrideSprite, string overrideText)` / `RemoveNavObject`. The buff action `SetNavObject` has `nav_object`, `sprite`, `text`, `cvar_to_text`, `add`.
  - In `nav_objects.xml`, an `onscreen_settings` block with `text_type` (`None|Distance|Name|SpawnName`), `use_head_offset`, `offset`, `max_distance`, `color` gives a floating label. `NavObject.DisplayName` uses `localizedName` or `Localization.Get(name)`.
  - Example: vanilla `twitch_spawn` shows `SpawnName` above Twitch spawns.
  - Nav objects are local per client, so add them from client-side buff or C# logic (see §5 for the late-tracking caveat).
  - The class property `NavObject` attaches one at `PostInit` on every machine; `NavObjectHeadOffset` is also a class property. [IL] [XML]
- **`GUIHUDEntityName`** (NGUI floating name, read from `entityName`) is only added for players or when a game pref is set. Not for zombies by default. [IL]
- **Spawn-time buff hook:** vanilla `GameEventManager.HandleSpawnModifier(EntityAlive)` runs inside `EntityAlive.PostInit` and adds `twitch_bighead`, `twitch_dance` and similar buffs to new spawns. The same place is right for a champion roll. [IL]
- **Example boss buff:** `twitch_boss` buff = `SetScale 1.25` + `ExplosionIncomingDamage -75%`. [XML]

---

## Quick API reference (signatures from IL)
```
EntityFactory.CreateEntity(int _et, Vector3 _transformPos, Vector3 _rotation) : Entity
World.SpawnEntityInWorld(Entity _entity)
World.EntityLoadedDelegates / EntityUnloadedDelegates  (event-style delegate fields)
EntityClass.FromString(string) : int ; EntityClass.list[id] ; Entity.EntityClass
EntityAlive.SetInvestigatePosition(Vector3 pos, int ticks, bool isAlert = true)
EntityAlive.SetAttackTarget(EntityAlive _attackTarget, int _attackTargetTime)
EntityHuman.StartRage(float speedPercent, float time) : bool
EntityAlive.SetWalkType(int) ; SetupCrawler() ; SetStun(EnumEntityStunType) ; ClearStun()
EntityAlive.DoRagdoll(in DamageResponse, EModelBase.RagdollMode)
Entity.ProcessDamageResponse(DamageResponse)   // replicated
EntityAlive.StartAnimAction(int animType) ; AvatarController._setTrigger(int hash, bool netsync)
EntityBuffs.AddBuff(string, int instigatorId=-1, bool netSync=true, bool fromElectrical=false, float duration=-1)
EntityBuffs.SetCustomVar(string, float, bool netSync=true, CVarOperation op=set, bool forceSendToClients=false)
Entity.SetScale(float) ; EntityAlive.OverrideSize ; EntityAlive.SetEntityName(string)
Entity.AddNavObject(string navObjectName, string overrideSprite, string overrideText)
Entity.DropBagServer() ; Entity.lootDropProb
GameManager.ExplosionServer(Vector3, Vector3i, Quaternion, ExplosionData, int entityId, float delay, bool removeBlock, ItemValue src = null)
AIDirector.NotifyActivity(EnumAIDirectorChunkEvent, Vector3i, float value, float duration = 720)
AIDirector.NotifyNoise(Entity instigator, Vector3 pos, string clipName, float volumeScale)
AIDirectorChunkEventComponent.SpawnScouts(Vector3 targetPos)
GameEventManager.SetupBossGroup(EntityPlayer, EntityAlive boss, List<EntityAlive> minions, BossGroup.BossGroupTypes, string icon) : int
ModEvents.EntityKilled (ModEvent<SEntityKilledData>)
```
