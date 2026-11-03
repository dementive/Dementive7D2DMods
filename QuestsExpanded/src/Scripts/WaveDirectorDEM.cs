using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Runs the zombies of defense quests on the server. There is one defense per quest (keyed by quest code, which
/// shared copies keep), so a party fights it together: every member whose quest reaches the defense joins it, the
/// first one starts it, and it only stops when every member has left. See <see cref="DefenseSettingsDEM.Modes"/>
/// for the kinds of defense.
/// Waves are drawn from gamestage spawners (vanilla's defenseGSList by default) at the party's gamestage, spawn just
/// outside the defended area all around it and go after the players. Bosses get <see cref="BossBuff"/> and drop a
/// boss loot bag.
/// </summary>
public static class WaveDirectorDEM
{
    public const string DefaultSpawner = "defenseGSList";

    /// <summary>Buff on bosses: more health, bigger, and marked on screen, map and compass.</summary>
    public const string BossBuff = "buffDementiveBoss";

    /// <summary>Buff on a wave's last few zombies so they show on the map and compass.</summary>
    public const string MarkedBuff = "buffDementiveMarked";

    public const string BossBag = "EntityLootContainerBoss";

    /// <summary>Seconds between waves.</summary>
    public const float BreakSeconds = 15f;

    /// <summary>Seconds a wave can last before the zombies that are left (stuck or lost) are removed.</summary>
    public const float WaveTimeLimit = 240f;

    /// <summary>Seconds a finished defense is remembered, for party members whose quest only reaches it later.</summary>
    public const float RememberSeconds = 3600f;

    /// <summary>World time in one in-game hour.</summary>
    public const ulong Hour = 1000;

    private static readonly Dictionary<int, Defense> defenses = new Dictionary<int, Defense>();

    /// <summary>Defenses that were won, by quest code: when they finished and how they ended.</summary>
    private static readonly Dictionary<int, KeyValuePair<float, DefenseStatusDEM>> won = new Dictionary<int, KeyValuePair<float, DefenseStatusDEM>>();

    /// <summary>Seconds between sweeps for NPCs an NPC quest spawned and no longer looks after.</summary>
    private const float CleanUpSeconds = 10f;

    private static float cleanUpTimer = CleanUpSeconds;

    public static void Init()
    {
        ModEvents.GameUpdate.RegisterHandler(Update);
        ModEvents.WorldShuttingDown.RegisterHandler(WorldShuttingDown);
    }

    /// <summary>
    /// The world is closing (this fires before the world and the players are saved): every defense ends the way it
    /// does when its players leave (its zombies are removed, an outpost under attack falls), and none carries over
    /// into the next world loaded in this session.
    /// </summary>
    private static void WorldShuttingDown(ref ModEvents.SWorldShuttingDownData data)
    {
        foreach (Defense defense in new List<Defense>(defenses.Values))
        {
            try
            {
                defense.Abandon();
            }
            catch (System.Exception e)
            {
                Log.Exception(e);
            }
        }
        defenses.Clear();
        won.Clear();
        cleanUpTimer = CleanUpSeconds;
    }

    /// <summary>
    /// A player whose quest reached the defense joins it, starting it if needed.
    /// </summary>
    public static void Join(int questCode, int playerId, DefenseSettingsDEM settings)
    {
        if (won.TryGetValue(questCode, out KeyValuePair<float, DefenseStatusDEM> result))
        {
            // The party already won it; don't start it over for someone who arrives late, just tell them how it ended
            SendStatus(questCode, playerId, result.Value);
            return;
        }

        if (!defenses.TryGetValue(questCode, out Defense defense))
        {
            defense = Defense.Create(questCode, settings);
            defenses.Add(questCode, defense);
        }
        defense.AddListener(playerId);
    }

    /// <summary>
    /// A player's quest left the defense (finished, failed, abandoned or logged out). The defense stops when nobody
    /// is left.
    /// </summary>
    public static void Leave(int questCode, int playerId)
    {
        if (defenses.TryGetValue(questCode, out Defense defense))
        {
            defense.Listeners.Remove(playerId);
            if (defense.Listeners.Count == 0)
            {
                defense.Abandon();
                defenses.Remove(questCode);
            }
        }
    }

    /// <summary>
    /// Server side: an enemy died (see DefenseKillPatches). Every defense counts it toward its wave if it was one of
    /// the wave's zombies or died in the defended area.
    /// </summary>
    public static void EnemyDied(EntityAlive enemy)
    {
        foreach (Defense defense in new List<Defense>(defenses.Values))
            defense.OnEnemyDied(enemy);
    }

    /// <summary>
    /// Server side: a non-enemy entity died (see DefenseKillPatches). If it was a survivor or refugee of an NPC quest,
    /// that quest counts it as lost, even if nobody is around to find the body. A settled refugee whose safehouse isn't
    /// running right now (its party is offline) is struck from the safehouse's record.
    /// </summary>
    public static void NpcDied(EntityAlive npc)
    {
        if (npc == null || npc.Buffs == null)
            return;
        foreach (Defense defense in new List<Defense>(defenses.Values))
        {
            if (defense is NpcDefense npcDefense && npcDefense.OnNpcDied(npc.entityId))
                return;
        }
        if (npc.Buffs.HasCustomVar(NpcDefense.SettledCvar))
            SafehouseRegistryDEM.RefugeeDied(npc.Buffs.GetCustomVar(NpcDefense.SettledCvar), npc.entityId);
    }

    /// <summary>
    /// Server side: despawns NPCs an NPC quest spawned (they carry its tag) that no running quest looks after any
    /// more: ones that come back with their chunk after the quest ended, was abandoned or replaced them, so they don't
    /// follow someone forever or keep their marker.
    /// </summary>
    private static void CleanUpQuestNpcs(World world)
    {
        var byTag = new Dictionary<float, NpcDefense>();
        foreach (KeyValuePair<int, Defense> entry in defenses)
        {
            if (entry.Value is NpcDefense npcDefense)
                byTag[NpcDefense.Tag(entry.Key)] = npcDefense;
        }
        foreach (Entity entity in new List<Entity>(world.Entities.list))
        {
            if (!(entity is EntityAlive npc) || entity is EntityPlayer || npc.IsDead() || npc.Buffs == null
                || !npc.Buffs.HasCustomVar(NpcDefense.TagCvar))
                continue;
            if (byTag.TryGetValue(npc.Buffs.GetCustomVar(NpcDefense.TagCvar), out NpcDefense defense) && defense.IsMember(npc.entityId))
                continue;
            NpcFollowDEM.Release(npc, NpcFollowDEM.Leader(npc));
            world.RemoveEntity(npc.entityId, EnumRemoveEntityReason.Despawned);
        }
    }

    private static void Update(ref ModEvents.SGameUpdateData data)
    {
        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
            return;

        World world = GameManager.Instance.World;
        if (world == null)
            return;

        cleanUpTimer -= Time.deltaTime;
        if (cleanUpTimer <= 0f)
        {
            cleanUpTimer = CleanUpSeconds;
            CleanUpQuestNpcs(world);
        }

        if (defenses.Count == 0)
            return;

        // Ticking can change the defenses: a status that completes or fails the local player's quest (on a listen
        // server or in single player) makes it leave its defense right away, which can remove that defense
        float deltaTime = Time.deltaTime;
        var finished = new List<Defense>();
        foreach (Defense defense in new List<Defense>(defenses.Values))
        {
            bool stillRunning = defenses.TryGetValue(defense.QuestCode, out Defense current) && current == defense;
            if (stillRunning && defense.Tick(world, deltaTime))
                finished.Add(defense);
        }
        foreach (Defense defense in finished)
        {
            if (defenses.TryGetValue(defense.QuestCode, out Defense current) && current == defense)
                defenses.Remove(defense.QuestCode);
            if (defense.Won)
                won[defense.QuestCode] = new KeyValuePair<float, DefenseStatusDEM>(Time.time, defense.FinalStatus());
        }

        if (won.Count > 0)
        {
            var forgotten = new List<int>();
            foreach (KeyValuePair<int, KeyValuePair<float, DefenseStatusDEM>> entry in won)
            {
                if (Time.time - entry.Value.Key > RememberSeconds)
                    forgotten.Add(entry.Key);
            }
            foreach (int questCode in forgotten)
                won.Remove(questCode);
        }
    }

    /// <summary>
    /// Sends a defense's status to one player (applied directly for the local player of a listen server).
    /// </summary>
    public static void SendStatus(int questCode, int playerId, DefenseStatusDEM status)
    {
        World world = GameManager.Instance.World;
        var package = NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupStatus(questCode, status);
        if (world?.GetEntity(playerId) is EntityPlayerLocal)
            package.ApplyStatus(world);
        else
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(package, _onlyClientsAttachedToAnEntity: false, playerId);
    }

    /// <summary>
    /// Zombies in a wave at the gamestage: the defense spawner's count for one player.
    /// </summary>
    public static int WaveSize(int gameStage)
    {
        GameStageDefinition.Stage stage = GameStageDefinition.GetGameStage(DefaultSpawner)?.GetStage(gameStage);
        int size = 0;
        if (stage != null)
        {
            foreach (GameStageDefinition.SpawnGroup group in stage.spawnGroups)
                size += group.spawnCount;
        }
        return size;
    }

    public static bool IsBloodMoonNow(World world)
    {
        return GameUtils.IsBloodMoonTime(world.worldTime, (world.DuskHour, world.DawnHour), GameStats.GetInt(EnumGameStats.BloodMoonDay));
    }
}

/// <summary>
/// One defense on the server: its listeners (the players whose quest is in it), its zombies and bosses, and the
/// spawning and status code every kind of defense shares.
/// </summary>
internal abstract class Defense
{
    public readonly int QuestCode;
    public readonly HashSet<int> Listeners = new HashSet<int>();

    /// <summary>Every wave was beaten (or the bounty killed), rather than everyone leaving.</summary>
    public bool Won;

    /// <summary>The defense was lost (an NPC quest's survivors all died, its NPC mod is gone, ...).</summary>
    public bool Failed;

    public int Waves => settings.Waves;

    protected readonly DefenseSettingsDEM settings;
    protected int wavesDone;
    protected bool fighting;
    protected float timer;
    protected readonly List<int> zombies = new List<int>();
    protected readonly List<Boss> bosses = new List<Boss>();

    /// <summary>The hostile NPCs (bandits) among <see cref="zombies"/>, which pick their own targets.</summary>
    protected readonly HashSet<int> bandits = new HashSet<int>();
    private float retargetTimer;
    private bool marked;
    private int lastReportedAlive = -1;

    // Kill counting during a wave: every enemy that dies in the area counts, not just the wave's own zombies
    private bool counting;
    private int waveTarget;
    private readonly HashSet<int> waveKills = new HashSet<int>();

    /// <summary>The POI's sleeper spots, for waves that come out of the building (loaded on first use).</summary>
    private List<Vector3> insidePoints;

    protected class Boss
    {
        public int Id;
        public string ClassName;
        public Vector3 Position;
        public float Health = 1f;
        public int Wave;
    }

    protected Defense(int questCode, DefenseSettingsDEM settings)
    {
        QuestCode = questCode;
        this.settings = settings;
        wavesDone = settings.WavesDone;
        timer = settings.BreakSeconds;
    }

    public static Defense Create(int questCode, DefenseSettingsDEM settings)
    {
        switch (settings.Mode)
        {
            case DefenseSettingsDEM.Modes.Bounty:
                return new BountyDefense(questCode, settings);
            case DefenseSettingsDEM.Modes.BloodMoon:
                return new BloodMoonDefense(questCode, settings);
            case DefenseSettingsDEM.Modes.Outpost:
                return new OutpostDefense(questCode, settings);
            case DefenseSettingsDEM.Modes.Hideout:
                return new HideoutDefense(questCode, settings);
            case DefenseSettingsDEM.Modes.Rescue:
                return new RescueDefense(questCode, settings);
            case DefenseSettingsDEM.Modes.Safehouse:
                return new SafehouseDefense(questCode, settings);
            default:
                return new WaveDefense(questCode, settings);
        }
    }

    public virtual void AddListener(int playerId)
    {
        bool first = Listeners.Count == 0;
        Listeners.Add(playerId);
        SendStatus(first ? StartMessage : null);
    }

    /// <summary>Message the first player to join gets.</summary>
    protected virtual string StartMessage => null;

    /// <summary>
    /// Advances the defense. Returns true when it is over.
    /// </summary>
    public abstract bool Tick(World world, float deltaTime);

    /// <summary>
    /// Everybody left before it was over.
    /// </summary>
    public virtual void Abandon()
    {
        RemoveZombies();
    }

    // ---- Players ----

    protected List<EntityPlayer> ListenerPlayers(World world)
    {
        var players = new List<EntityPlayer>();
        foreach (int id in Listeners)
        {
            if (world.GetEntity(id) is EntityPlayer player && !player.IsDead())
                players.Add(player);
        }
        return players;
    }

    /// <summary>True if no listener is in the world at all (dead ones still count as there).</summary>
    protected bool NobodyOnline(World world)
    {
        foreach (int id in Listeners)
        {
            if (world.GetEntity(id) is EntityPlayer)
                return false;
        }
        return true;
    }

    protected static EntityPlayer Closest(List<EntityPlayer> players, Vector3 position)
    {
        EntityPlayer closest = null;
        foreach (EntityPlayer player in players)
        {
            if (closest == null || (player.position - position).sqrMagnitude < (closest.position - position).sqrMagnitude)
                closest = player;
        }
        return closest;
    }

    protected static float Flat(Vector3 a, Vector3 b)
    {
        return new Vector2(a.x - b.x, a.z - b.z).magnitude;
    }

    // ---- Kill counting ----

    /// <summary>
    /// Zombies left in the current wave: what's left to kill (every enemy killed in the area counts), but never more
    /// than the wave's zombies still around, and never fewer than its bosses still alive (a wave isn't over until its
    /// boss is dead).
    /// </summary>
    protected int Remaining => counting
        ? Mathf.Max(bosses.Count, Mathf.Max(0, Mathf.Min(zombies.Count, waveTarget - waveKills.Count)))
        : zombies.Count;

    /// <summary>Starts counting kills for a wave that just spawned (zombies left over from the last one count too).</summary>
    protected void StartCounting()
    {
        counting = true;
        waveTarget = zombies.Count;
        waveKills.Clear();
        marked = false;
        lastReportedAlive = -1;
    }

    /// <summary>The wave is over; zombies still alive carry over into the next one.</summary>
    protected void StopCounting()
    {
        counting = false;
    }

    public void OnEnemyDied(EntityAlive enemy)
    {
        if (!counting || enemy == null)
            return;
        if (zombies.Contains(enemy.entityId) || Flat(enemy.position, settings.Center) <= settings.Radius + 20f)
            waveKills.Add(enemy.entityId);
    }

    // ---- Spawning ----

    protected EntityAlive Spawn(World world, int classId, Vector3 position, EntityPlayer target, GameRandom random)
    {
        if (classId == -1 || classId == 0)
            return null;

        var rotation = new Vector3(0f, random.RandomFloat * 360f, 0f);
        if (!(EntityFactory.CreateEntity(classId, position, rotation) is EntityAlive zombie))
            return null;

        zombie.SetSpawnerSource(EnumSpawnerSource.Dynamic);
        world.SpawnEntityInWorld(zombie);
        if (target != null)
            zombie.SetAttackTarget(target, 1200);
        zombies.Add(zombie.entityId);
        return zombie;
    }

    protected EntityAlive SpawnBoss(World world, string list, Vector3 position, EntityPlayer target, GameRandom random, int wave = 0)
    {
        string[] names = list.Split(',');
        string name = names[random.RandomRange(names.Length)].Trim();
        return SpawnBossNamed(world, name, position, target, random, wave);
    }

    private EntityAlive SpawnBossNamed(World world, string name, Vector3 position, EntityPlayer target, GameRandom random, int wave)
    {
        EntityAlive boss = Spawn(world, EntityClass.FromString(name), position, target, random);
        if (boss == null)
            return null;
        boss.Buffs.AddBuff(WaveDirectorDEM.BossBuff);
        bosses.Add(new Boss { Id = boss.entityId, ClassName = name, Position = boss.position, Wave = wave });
        return boss;
    }

    /// <summary>
    /// Follows the bosses: a dead boss drops its loot bag and is gone; one that vanished without dying (unloaded
    /// with the terrain, or stuck and removed) comes back at <paramref name="respawnAt"/>, unless it was nearly dead.
    /// </summary>
    protected void TrackBosses(World world, GameRandom random, System.Func<Boss, Vector3?> respawnAt, EntityPlayer target)
    {
        for (int i = bosses.Count - 1; i >= 0; i--)
        {
            Boss boss = bosses[i];
            Entity entity = world.GetEntity(boss.Id);
            if (entity is EntityAlive alive && !alive.IsDead())
            {
                boss.Position = alive.position;
                boss.Health = alive.GetMaxHealth() > 0 ? (float)alive.Health / alive.GetMaxHealth() : 1f;
                continue;
            }

            bosses.RemoveAt(i);
            if (entity != null || boss.Health <= 0.3f)
            {
                DropBossBag(world, boss.Position);
                continue;
            }

            // If it can't come back, it counts as killed
            Vector3? position = respawnAt(boss);
            EntityAlive again = position.HasValue
                ? SpawnBossNamed(world, boss.ClassName, position.Value, target, random, boss.Wave)
                : null;
            if (again == null)
                DropBossBag(world, boss.Position);
        }
    }

    protected void DropBossBag(World world, Vector3 position)
    {
        int bagClass = EntityClass.FromString(WaveDirectorDEM.BossBag);
        if (bagClass != -1 && bagClass != 0 && EntityFactory.CreateEntity(bagClass, position + Vector3.up, Vector3.zero) is Entity bag)
            world.SpawnEntityInWorld(bag);
    }

    /// <summary>
    /// Spawns a wave of zombies around the defended area, sized by the defense spawner at the gamestage.
    /// </summary>
    protected void SpawnWaveZombies(World world, List<EntityPlayer> players, GameRandom random, int gameStage, float sizeMultiplier)
    {
        string[] spawners = settings.Spawners.Split(',');
        GameStageDefinition.Stage stage = GameStageDefinition.GetGameStage(spawners[random.RandomRange(spawners.Length)].Trim())?.GetStage(gameStage);
        if (stage == null || stage.spawnGroups.Count == 0)
            return;

        // The wave's size always comes from the defense spawner; themed spawners (hordes of cops, soldiers,
        // spiders, ...) only pick which zombies, since their counts are for wandering hordes.
        int count = WaveCount(gameStage, sizeMultiplier, players.Count);
        int lastClassId = -1;
        for (int i = 0; i < count; i++)
        {
            GameStageDefinition.SpawnGroup group = stage.spawnGroups[i % stage.spawnGroups.Count];
            int classId = EntityGroups.GetRandomFromGroup(group.groupName, ref lastClassId, random);
            if (WavePosition(world, random, players, out Vector3 position))
                Spawn(world, classId, position, Closest(players, position), random);
        }
    }

    /// <summary>
    /// Zombies in a wave: the defense spawner's count at the gamestage (for one player), more for each extra player.
    /// </summary>
    protected static int WaveCount(int gameStage, float sizeMultiplier, int players)
    {
        int count = Mathf.RoundToInt(Mathf.Max(WaveDirectorDEM.WaveSize(gameStage), 4) * sizeMultiplier);
        return count + count * (players - 1) / 2;
    }

    /// <summary>
    /// Bandits in place of a wave of zombies: about a third as many, since they shoot back, and at least 2.
    /// </summary>
    protected static int BanditCount(int zombies)
    {
        return Mathf.Max(2, Mathf.RoundToInt(zombies / 3f));
    }

    /// <summary>
    /// Spawns hostile NPCs (bandits from an NPC mod) for the tier at spots from <paramref name="position"/>, sent
    /// after the closest player (or posted where they are, with no players). Returns how many spawned.
    /// </summary>
    protected int SpawnBandits(World world, List<EntityPlayer> players, GameRandom random, int count, System.Func<int, Vector3?> position)
    {
        int spawned = 0;
        for (int i = 0; i < count; i++)
        {
            Vector3? spot = position(i);
            if (!spot.HasValue)
                continue;
            EntityPlayer target = players != null ? Closest(players, spot.Value) : null;
            EntityAlive bandit = Spawn(world, NpcCatalogDEM.PickHostile(settings.Tier, random), spot.Value, target, random);
            if (bandit != null)
            {
                bandits.Add(bandit.entityId);
                spawned++;
            }
        }
        return spawned;
    }

    /// <summary>
    /// Where a wave's zombie comes from, by the quest's spawn style: out of the building (for about half of them)
    /// or from outside it.
    /// </summary>
    protected bool WavePosition(World world, GameRandom random, List<EntityPlayer> players, out Vector3 position)
    {
        if (settings.SpawnStyle == DefenseSettingsDEM.SpawnStyles.Inside && random.RandomFloat < 0.5f
            && InsidePosition(world, random, players, out position))
            return true;
        return OutsidePosition(world, random, out position);
    }

    /// <summary>A spot outside the defended area: just outside the POI's footprint, or all around a flag or spot.</summary>
    protected bool OutsidePosition(World world, GameRandom random, out Vector3 position)
    {
        if (settings.SpawnStyle != DefenseSettingsDEM.SpawnStyles.Around && settings.PoiSize != Vector3.zero)
            return WallPosition(world, random, out position);
        return RingPosition(world, random, settings.Center, settings.Radius, out position);
    }

    /// <summary>
    /// A spot on the ground 2-6m outside the POI's footprint, anywhere along its edges.
    /// </summary>
    private bool WallPosition(World world, GameRandom random, out Vector3 position)
    {
        float width = settings.PoiSize.x;
        float depth = settings.PoiSize.z;
        for (int attempt = 0; attempt < 20; attempt++)
        {
            float margin = 2f + random.RandomFloat * 4f;
            // A point along the perimeter, then pushed out from that edge
            float along = random.RandomFloat * 2f * (width + depth);
            float x, z;
            if (along < width) { x = along; z = -margin; }
            else if (along < width + depth) { x = width + margin; z = along - width; }
            else if (along < 2f * width + depth) { x = along - width - depth; z = depth + margin; }
            else { x = -margin; z = along - 2f * width - depth; }

            int bx = Mathf.FloorToInt(settings.PoiMin.x + x);
            int bz = Mathf.FloorToInt(settings.PoiMin.z + z);
            int by = world.GetHeight(bx, bz) + 1;
            var block = new Vector3i(bx, by, bz);
            if (by <= 1 || world.IsWater(block) || world.IsWithinTraderArea(block))
                continue;
            position = new Vector3(bx + 0.5f, by, bz + 0.5f);
            return true;
        }
        position = Vector3.zero;
        return false;
    }

    /// <summary>
    /// One of the POI's sleeper spots at least 10m from every player (another room, in a house), so zombies come back
    /// into the building without popping up in front of anyone.
    /// </summary>
    private bool InsidePosition(World world, GameRandom random, List<EntityPlayer> players, out Vector3 position)
    {
        List<Vector3> insidePoints = PoiSpawnPoints();
        for (int attempt = 0; attempt < 15 && insidePoints.Count > 0; attempt++)
        {
            Vector3 candidate = insidePoints[random.RandomRange(insidePoints.Count)];
            bool clear = true;
            foreach (EntityPlayer player in players)
                clear &= (player.position - candidate).sqrMagnitude >= 10f * 10f;
            if (clear && !world.IsWithinTraderArea(new Vector3i(candidate)))
            {
                position = candidate;
                return true;
            }
        }
        position = Vector3.zero;
        return false;
    }

    /// <summary>
    /// The POI's sleeper spawn points (loaded on first use). Don't change the list.
    /// </summary>
    protected List<Vector3> PoiSpawnPoints()
    {
        if (insidePoints == null)
        {
            insidePoints = new List<Vector3>();
            PrefabInstance poi = GameManager.Instance.GetDynamicPrefabDecorator()?.GetPrefabFromWorldPosInside(
                Mathf.FloorToInt(settings.Center.x), Mathf.FloorToInt(settings.Center.z));
            if (poi != null)
            {
                foreach (SleeperVolume volume in poi.sleeperVolumes)
                {
                    foreach (SleeperVolume.SpawnPoint point in volume.spawnPointList)
                        insidePoints.Add(point.pos.ToVector3() + new Vector3(0.5f, 0f, 0.5f));
                }
            }
        }
        return insidePoints;
    }

    /// <summary>
    /// Up to <paramref name="count"/> of the points, the ones farthest from the players first and at least
    /// <paramref name="spacing"/> apart (closer together once that runs out), so NPCs end up spread through the POI.
    /// </summary>
    protected static List<Vector3> SpreadOut(List<Vector3> points, List<EntityPlayer> players, int count, float spacing)
    {
        var sorted = new List<Vector3>(points);
        sorted.Sort((a, b) => (Closest(players, b).position - b).sqrMagnitude.CompareTo((Closest(players, a).position - a).sqrMagnitude));
        var picked = new List<Vector3>();
        for (float gap = spacing; picked.Count < count && gap >= 0f; gap -= spacing / 2f)
        {
            foreach (Vector3 point in sorted)
            {
                if (picked.Count >= count)
                    break;
                bool apart = !picked.Contains(point);
                foreach (Vector3 other in picked)
                    apart &= (other - point).sqrMagnitude >= gap * gap;
                if (apart)
                    picked.Add(point);
            }
        }
        return picked;
    }

    /// <summary>
    /// A spot on the ground 6-14m outside the area, in a random direction, not in water or a trader's area.
    /// </summary>
    protected static bool RingPosition(World world, GameRandom random, Vector3 center, float radius, out Vector3 position)
    {
        return Around(world, random, center, radius + 6f, radius + 14f, out position);
    }

    /// <summary>
    /// A spot on the ground between the two distances from a point, not in water or a trader's area.
    /// </summary>
    protected static bool Around(World world, GameRandom random, Vector3 center, float minDistance, float maxDistance, out Vector3 position)
    {
        for (int attempt = 0; attempt < 20; attempt++)
        {
            float angle = random.RandomFloat * Mathf.PI * 2f;
            float distance = minDistance + random.RandomFloat * (maxDistance - minDistance);
            int x = Mathf.FloorToInt(center.x + Mathf.Cos(angle) * distance);
            int z = Mathf.FloorToInt(center.z + Mathf.Sin(angle) * distance);
            int y = world.GetHeight(x, z) + 1;
            var block = new Vector3i(x, y, z);
            if (y <= 1 || world.IsWater(block) || world.IsWithinTraderArea(block))
                continue;

            position = new Vector3(x + 0.5f, y, z + 0.5f);
            return true;
        }
        position = Vector3.zero;
        return false;
    }

    // ---- Wave upkeep ----

    /// <summary>Drops zombies that died (any way) or unloaded.</summary>
    protected void PruneZombies(World world)
    {
        zombies.RemoveAll(id => !(world.GetEntity(id) is EntityAlive zombie) || zombie.IsDead());
    }

    /// <summary>Marks the last few zombies of a wave so nobody has to hunt for them.</summary>
    protected void MarkStragglers(World world)
    {
        if (marked || Remaining > 3)
            return;
        marked = true;
        foreach (int id in zombies)
        {
            if (world.GetEntity(id) is EntityAlive zombie)
                zombie.Buffs.AddBuff(WaveDirectorDEM.MarkedBuff);
        }
    }

    /// <summary>Every 10 seconds, sends zombies that lost their target after the closest player.</summary>
    protected void Retarget(World world, List<EntityPlayer> players, float deltaTime, bool always = false)
    {
        retargetTimer -= deltaTime;
        if (retargetTimer > 0f || players.Count == 0)
            return;
        retargetTimer = 10f;
        foreach (int id in zombies)
        {
            if (world.GetEntity(id) is EntityAlive zombie && (always || zombie.GetAttackTarget() == null))
                zombie.SetAttackTarget(Closest(players, zombie.position), 1200);
        }
    }

    protected void ResetRetarget()
    {
        retargetTimer = 10f;
    }

    /// <summary>Removes the zombies left in a wave that ran too long, but not bandits: they hold their posts.</summary>
    protected void RemoveWaveZombies()
    {
        World world = GameManager.Instance.World;
        foreach (int id in zombies)
        {
            if (!bandits.Contains(id) && world?.GetEntity(id) is EntityAlive zombie && !zombie.IsDead())
                world.RemoveEntity(id, EnumRemoveEntityReason.Despawned);
        }
        zombies.RemoveAll(id => !bandits.Contains(id));
    }

    public void RemoveZombies()
    {
        World world = GameManager.Instance.World;
        foreach (int id in zombies)
        {
            if (world?.GetEntity(id) is EntityAlive zombie && !zombie.IsDead())
                world.RemoveEntity(id, EnumRemoveEntityReason.Despawned);
        }
        zombies.Clear();
        bosses.Clear();
    }

    // ---- Status ----

    protected virtual DefenseStatusDEM Status(string messageKey, int messageValue)
    {
        return new DefenseStatusDEM
        {
            WavesDone = wavesDone,
            Waves = settings.Waves,
            Fighting = fighting,
            ZombiesLeft = Remaining,
            MessageKey = messageKey ?? "",
            MessageValue = messageValue,
            BreakSeconds = Mathf.RoundToInt(settings.BreakSeconds),
            Result = Won ? DefenseStatusDEM.Results.Won : Failed ? DefenseStatusDEM.Results.Lost : DefenseStatusDEM.Results.None,
        };
    }

    /// <summary>How the defense ended, for party members who only get there later.</summary>
    public DefenseStatusDEM FinalStatus()
    {
        return Status(null, 0);
    }

    /// <summary>
    /// Tells every listener where the defense stands, with an optional on-screen message.
    /// </summary>
    public void SendStatus(string messageKey, int messageValue = 0)
    {
        lastReportedAlive = Remaining;
        // A copy: the status can complete or fail the local player's quest, which makes them leave (see Update)
        foreach (int id in new List<int>(Listeners))
            WaveDirectorDEM.SendStatus(QuestCode, id, Status(messageKey, messageValue));
    }

    /// <summary>Sends the status if the number of zombies left changed.</summary>
    protected void ReportAlive()
    {
        if (Remaining != lastReportedAlive)
            SendStatus(null);
    }
}

/// <summary>
/// A set number of waves, or a last stand's endless ones.
/// </summary>
internal class WaveDefense : Defense
{
    private bool Endless => settings.Mode == DefenseSettingsDEM.Modes.LastStand;

    public WaveDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
    }

    protected override string StartMessage => "DefendWavesDEM_starting";

    public override bool Tick(World world, float deltaTime)
    {
        List<EntityPlayer> players = ListenerPlayers(world);
        if (players.Count == 0)
        {
            if (NobodyOnline(world))
            {
                RemoveZombies();
                return true;
            }
            // Everybody is dead for the moment; their quests decide what that means
            return false;
        }

        timer -= deltaTime;
        GameRandom random = world.GetGameRandom();

        if (!fighting)
        {
            if (timer <= 0f)
                SpawnWave(world, players, random);
            return false;
        }

        TrackBosses(world, random, boss => OutsidePosition(world, random, out Vector3 p) ? p : (Vector3?)null,
            Closest(players, settings.Center));
        PruneZombies(world);

        if (zombies.Count > 0 && timer <= 0f)
        {
            // Whatever is left is stuck or lost; don't let it stall the quest
            RemoveZombies();
            SendStatus("DefendWavesDEM_retreat");
        }

        if (Remaining == 0)
        {
            StopCounting();
            wavesDone++;
            fighting = false;
            timer = settings.BreakSeconds;
            if (!Endless && wavesDone >= settings.Waves)
            {
                Won = true;
                SendStatus("DefendWavesDEM_complete");
                return true;
            }
            SendStatus("DefendWavesDEM_cleared");
            return false;
        }

        MarkStragglers(world);
        Retarget(world, players, deltaTime);
        ReportAlive();
        return false;
    }

    private void SpawnWave(World world, List<EntityPlayer> players, GameRandom random)
    {
        // Each wave is bigger and a little harder than the last (e.g. 4, 5, 6 zombies at the lowest gamestages);
        // a last stand's endless waves grow more slowly
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength * (1f + 0.15f * wavesDone));
        float size = 1f + (Endless ? 0.1f : 0.2f) * wavesDone;
        SpawnWaveZombies(world, players, random, gameStage, size);

        bool boss = Endless
            ? settings.BossEvery > 0 && (wavesDone + 1) % settings.BossEvery == 0
            : wavesDone == settings.Waves - 1;
        if (boss && settings.Bosses != "" && WavePosition(world, random, players, out Vector3 bossSpawn))
            SpawnBoss(world, settings.Bosses, bossSpawn, Closest(players, bossSpawn), random);

        if (zombies.Count == 0)
        {
            // Nowhere to spawn them (all water, or a trader's area): try again shortly rather than skip the wave
            timer = 5f;
            return;
        }

        fighting = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
        StartCounting();
        ResetRetarget();
        SendStatus(boss && settings.Bosses != "" ? "DefendWavesDEM_incoming_boss" : "DefendWavesDEM_incoming");
    }
}

/// <summary>
/// A bounty: the boss waits at the POI's sleeper spawn point farthest from the players, with a few escorts nearby.
/// Over when the boss is dead.
/// </summary>
internal class BountyDefense : Defense
{
    private bool spawned;
    private Vector3 lair;

    public BountyDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
    }

    public override bool Tick(World world, float deltaTime)
    {
        List<EntityPlayer> players = ListenerPlayers(world);
        if (players.Count == 0)
        {
            if (NobodyOnline(world))
            {
                RemoveZombies();
                return true;
            }
            return false;
        }

        GameRandom random = world.GetGameRandom();
        if (!spawned)
        {
            spawned = SpawnBounty(world, players, random);
            return false;
        }

        // A bounty that unloads goes back to its lair
        TrackBosses(world, random, boss => lair, null);
        PruneZombies(world);
        if (bosses.Count == 0)
        {
            wavesDone = settings.Waves;
            fighting = false;
            Won = true;
            SendStatus("DefendWavesDEM_bountydead");
            return true;
        }
        return false;
    }

    /// <summary>Returns false if the boss couldn't spawn, to try again.</summary>
    private bool SpawnBounty(World world, List<EntityPlayer> players, GameRandom random)
    {
        var spawnPoints = new List<Vector3>(PoiSpawnPoints());

        if (spawnPoints.Count > 0)
        {
            spawnPoints.Sort((a, b) => (Closest(players, b).position - b).sqrMagnitude.CompareTo((Closest(players, a).position - a).sqrMagnitude));
            lair = spawnPoints[0];
        }
        else if (!RingPosition(world, random, settings.Center, settings.Radius, out lair))
        {
            lair = settings.Center;
        }

        // A bounty waits in its lair until someone finds it
        if (SpawnBoss(world, settings.Bosses, lair, null, random) == null)
            return false;

        // Escorts at the spawn points nearest the boss
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
        string[] spawners = settings.Spawners.Split(',');
        GameStageDefinition.Stage stage = GameStageDefinition.GetGameStage(spawners[random.RandomRange(spawners.Length)].Trim())?.GetStage(gameStage);
        if (stage != null && stage.spawnGroups.Count > 0 && spawnPoints.Count > 1)
        {
            spawnPoints.Sort((a, b) => (a - lair).sqrMagnitude.CompareTo((b - lair).sqrMagnitude));
            int escorts = Mathf.Clamp(WaveDirectorDEM.WaveSize(gameStage) / 3, 2, 6);
            int lastClassId = -1;
            for (int i = 1; i <= escorts && i < spawnPoints.Count; i++)
            {
                int classId = EntityGroups.GetRandomFromGroup(stage.spawnGroups[0].groupName, ref lastClassId, random);
                Spawn(world, classId, spawnPoints[i], null, random);
            }
        }

        fighting = true;
        SendStatus("DefendWavesDEM_bounty");
        return true;
    }
}

/// <summary>
/// Blood Moon Bounty: when the next blood moon starts, waves of bosses come for the players wherever they are, one
/// wave every in-game hour. Over when every boss of every wave is dead, however long that takes.
/// </summary>
internal class BloodMoonDefense : Defense
{
    private bool started;
    private int spawnedWaves;
    private ulong nextWave;
    private readonly string[] waveBosses;

    public BloodMoonDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
        waveBosses = settings.Bosses.Split(';');
        // Picking a hunt up again (e.g. after logging out) carries on with the next wave right away
        spawnedWaves = wavesDone;
        started = wavesDone > 0;
    }

    public override bool Tick(World world, float deltaTime)
    {
        List<EntityPlayer> players = ListenerPlayers(world);
        if (players.Count == 0)
        {
            if (NobodyOnline(world))
            {
                RemoveZombies();
                return true;
            }
            return false;
        }

        GameRandom random = world.GetGameRandom();
        if (!started)
        {
            if (!WaveDirectorDEM.IsBloodMoonNow(world))
                return false;
            started = true;
            nextWave = world.worldTime;
        }

        // A wave that can't spawn yet (nowhere to put it, e.g. everyone is in a trader's area) tries again
        if (spawnedWaves < settings.Waves && world.worldTime >= nextWave && SpawnBossWave(world, players, random))
            nextWave = world.worldTime + WaveDirectorDEM.Hour;

        TrackBosses(world, random, boss => Around(world, random, Closest(players, boss.Position).position, 25f, 40f, out Vector3 p) ? p : (Vector3?)null,
            Closest(players, settings.Center));
        PruneZombies(world);

        // A wave is done when all of its bosses are dead
        int done = spawnedWaves;
        foreach (Boss boss in bosses)
            done = Mathf.Min(done, boss.Wave);
        if (done > wavesDone)
        {
            wavesDone = done;
            if (spawnedWaves >= settings.Waves && bosses.Count == 0)
            {
                fighting = false;
                Won = true;
                SendStatus("BloodMoonBountyDEM_complete");
                return true;
            }
            SendStatus("BloodMoonBountyDEM_wavedead");
        }

        // Bosses hunt the players down
        Retarget(world, players, deltaTime, true);
        ReportAlive();
        return false;
    }

    /// <summary>Spawns the next wave of bosses near the players. Returns false if none of them could spawn.</summary>
    private bool SpawnBossWave(World world, List<EntityPlayer> players, GameRandom random)
    {
        string list = waveBosses[Mathf.Min(spawnedWaves, waveBosses.Length - 1)];
        // More players means more bosses
        int count = settings.BossCount + (players.Count - 1) / 2;
        int spawned = 0;
        for (int i = 0; i < count; i++)
        {
            EntityPlayer target = players[random.RandomRange(players.Count)];
            if (Around(world, random, target.position, 25f, 40f, out Vector3 position)
                && SpawnBoss(world, list, position, target, random, spawnedWaves) != null)
                spawned++;
        }
        if (spawned == 0)
            return false;
        spawnedWaves++;
        fighting = true;
        SendStatus("BloodMoonBountyDEM_incoming", spawned);
        return true;
    }

    protected override DefenseStatusDEM Status(string messageKey, int messageValue)
    {
        DefenseStatusDEM status = base.Status(messageKey, messageValue);
        status.ZombiesLeft = bosses.Count;
        return status;
    }
}

/// <summary>
/// An outpost: every night at the attack hour, a few waves hit the flag in the POI, bigger every night. Someone has
/// to be at the outpost when an attack starts, and the flag has to survive it. The outpost's progress is kept in
/// <see cref="OutpostRegistryDEM"/>, saved with the world, so it carries on across days, logouts and restarts.
/// </summary>
internal class OutpostDefense : Defense
{
    private readonly OutpostRegistryDEM.Outpost outpost;
    private int attackWave;
    private bool waveActive;
    private int warned = int.MaxValue;
    private float flagTimer;
    private float scheduleTimer;

    /// <summary>
    /// Tonight's attack is a bandit raid: one night per outpost (never the first), when the quest asks for it and an
    /// NPC mod adds bandits.
    /// </summary>
    private bool RaidTonight => settings.BanditRaid && outpost.Nights > 1 && NpcCatalogDEM.HasHostile
        && outpost.NightsHeld == 1 + (QuestCode & int.MaxValue) % (outpost.Nights - 1);

    public OutpostDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
        outpost = OutpostRegistryDEM.Get(questCode);
        if (outpost.NextAttack == 0)
        {
            outpost.Nights = settings.Waves;
            outpost.NightsHeld = settings.WavesDone;
            outpost.NextAttack = NextAttackAfter(GameManager.Instance.World.worldTime + WaveDirectorDEM.Hour);
            OutpostRegistryDEM.Save();
        }
        wavesDone = outpost.NightsHeld;
    }

    /// <summary>The first attack hour at or after the time.</summary>
    private ulong NextAttackAfter(ulong time)
    {
        int day = GameUtils.WorldTimeToDays(time);
        ulong attack = GameUtils.DayTimeToWorldTime(day, settings.AttackHour, 0);
        return attack >= time ? attack : GameUtils.DayTimeToWorldTime(day + 1, settings.AttackHour, 0);
    }

    public override void AddListener(int playerId)
    {
        Listeners.Add(playerId);
        World world = GameManager.Instance.World;
        if (outpost.Fallen || outpost.Won)
        {
            Won = outpost.Won;
            SendStatus(null);
            return;
        }
        // Nobody was here when an attack came
        if (!fighting && world.worldTime > outpost.NextAttack + WaveDirectorDEM.Hour / 4)
        {
            Fall("OutpostDEM_missed");
            return;
        }
        SendStatus(Listeners.Count == 1 ? "OutpostDEM_planted" : null, HoursUntilAttack(world));
    }

    private int HoursUntilAttack(World world)
    {
        return world.worldTime >= outpost.NextAttack ? 0 : (int)((outpost.NextAttack - world.worldTime + WaveDirectorDEM.Hour - 1) / WaveDirectorDEM.Hour);
    }

    public override void Abandon()
    {
        // Everyone logged out in the middle of an attack: the outpost is lost
        if (fighting && !outpost.Fallen && !outpost.Won)
        {
            outpost.Fallen = true;
            OutpostRegistryDEM.Save();
        }
        base.Abandon();
    }

    public override bool Tick(World world, float deltaTime)
    {
        if (outpost.Fallen || outpost.Won)
            return true;

        List<EntityPlayer> players = ListenerPlayers(world);
        if (NobodyOnline(world))
        {
            Abandon();
            return true;
        }

        GameRandom random = world.GetGameRandom();
        if (!fighting)
        {
            scheduleTimer -= deltaTime;
            if (scheduleTimer > 0f)
                return false;
            scheduleTimer = 1f;

            // Warnings 2 hours, 1 hour and 15 minutes before the attack
            ulong left = world.worldTime >= outpost.NextAttack ? 0 : outpost.NextAttack - world.worldTime;
            int warning = left <= WaveDirectorDEM.Hour / 4 ? 0 : left <= WaveDirectorDEM.Hour ? 1 : left <= 2 * WaveDirectorDEM.Hour ? 2 : int.MaxValue;
            if (warning < warned)
            {
                warned = warning;
                if (warning != int.MaxValue && left > 0)
                    SendStatus(warning == 0 ? "OutpostDEM_warning_soon" : "OutpostDEM_warning", warning);
            }

            if (left > 0)
                return false;

            // Someone has to be there when the attack comes, and the flag has to still be standing
            bool present = false;
            foreach (EntityPlayer player in players)
                present |= Flat(player.position, settings.Center) <= settings.Radius + 20f;
            if (!present)
                return Fall("OutpostDEM_absent");
            if (FlagGone(world))
                return Fall("OutpostDEM_flaglost");

            fighting = true;
            attackWave = 0;
            timer = 0f;
            SendStatus(RaidTonight ? "OutpostDEM_attack_bandits" : "OutpostDEM_attack", outpost.NightsHeld + 1);
            return false;
        }

        // The flag falls, the outpost falls
        flagTimer -= deltaTime;
        if (flagTimer <= 0f)
        {
            flagTimer = 1f;
            if (FlagGone(world))
                return Fall("OutpostDEM_flaglost");
        }

        timer -= deltaTime;
        if (!waveActive)
        {
            if (timer <= 0f && players.Count > 0)
                StartWave(world, players, random);
            return false;
        }

        PruneZombies(world);
        if (zombies.Count > 0 && timer <= 0f)
        {
            RemoveZombies();
            SendStatus("DefendWavesDEM_retreat");
        }

        if (Remaining == 0)
        {
            StopCounting();
            waveActive = false;
            attackWave++;
            timer = settings.BreakSeconds;
            if (attackWave < settings.AttackWaves)
            {
                SendStatus("OutpostDEM_wavecleared", settings.AttackWaves - attackWave);
                return false;
            }

            // The night is held
            fighting = false;
            outpost.NightsHeld++;
            wavesDone = outpost.NightsHeld;
            warned = int.MaxValue;
            if (outpost.NightsHeld >= outpost.Nights)
            {
                outpost.Won = true;
                Won = true;
                OutpostRegistryDEM.Save();
                SendStatus("OutpostDEM_complete");
                return true;
            }
            outpost.NextAttack = NextAttackAfter(world.worldTime + WaveDirectorDEM.Hour);
            OutpostRegistryDEM.Save();
            SendStatus("OutpostDEM_held", outpost.Nights - outpost.NightsHeld);
            return false;
        }

        MarkStragglers(world);
        SteerAtFlag(world, players, deltaTime);
        ReportAlive();
        return false;
    }

    private void StartWave(World world, List<EntityPlayer> players, GameRandom random)
    {
        // Bigger every night, and each wave of the night a little harder than the last
        int night = outpost.NightsHeld;
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength * (1f + 0.25f * night) * (1f + 0.15f * attackWave));
        if (RaidTonight)
        {
            // Bandits instead of zombies, from just outside the POI like the zombies would
            int bandits = BanditCount(WaveCount(gameStage, 1f + 0.2f * night, players.Count));
            SpawnBandits(world, players, random, bandits, i => OutsidePosition(world, random, out Vector3 p) ? p : (Vector3?)null);
        }
        else
        {
            SpawnWaveZombies(world, players, random, gameStage, 1f + 0.2f * night);
        }
        if (zombies.Count == 0)
        {
            timer = 5f;
            return;
        }
        waveActive = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
        StartCounting();
        ResetRetarget();
        SendStatus("OutpostDEM_wave", attackWave + 1);
    }

    private float steerTimer;

    /// <summary>
    /// Zombies go for the players at the outpost; with nobody there, they go for the flag.
    /// </summary>
    private void SteerAtFlag(World world, List<EntityPlayer> players, float deltaTime)
    {
        steerTimer -= deltaTime;
        if (steerTimer > 0f)
            return;
        steerTimer = 10f;

        var defenders = players.FindAll(p => Flat(p.position, settings.Center) <= settings.Radius + 40f);
        foreach (int id in zombies)
        {
            if (!(world.GetEntity(id) is EntityAlive zombie))
                continue;
            if (defenders.Count > 0)
            {
                if (zombie.GetAttackTarget() == null)
                    zombie.SetAttackTarget(Closest(defenders, zombie.position), 1200);
            }
            else
            {
                zombie.SetInvestigatePosition(settings.Flag, 1200);
            }
        }
    }

    private bool FlagGone(World world)
    {
        var position = new Vector3i(settings.Flag);
        // Can't tell while the outpost's chunk isn't loaded; nothing can break the flag then either
        if (world.GetChunkFromWorldPos(position) == null)
            return false;
        return !(world.GetBlock(position).Block is BlockQuestFlagDEM);
    }

    private bool Fall(string messageKey)
    {
        outpost.Fallen = true;
        OutpostRegistryDEM.Save();
        RemoveZombies();
        fighting = false;
        SendStatus(messageKey);
        return true;
    }

    protected override DefenseStatusDEM Status(string messageKey, int messageValue)
    {
        DefenseStatusDEM status = base.Status(messageKey, messageValue);
        status.WavesDone = outpost.NightsHeld;
        status.Waves = outpost.Nights;
        status.NextTime = outpost.NextAttack;
        status.Result = outpost.Fallen ? DefenseStatusDEM.Results.Lost
            : outpost.Won ? DefenseStatusDEM.Results.Won : DefenseStatusDEM.Results.None;
        return status;
    }
}
