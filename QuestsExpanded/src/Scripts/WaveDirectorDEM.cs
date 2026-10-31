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

    /// <summary>Defenses that were won, by quest code: when they finished and how many waves they had.</summary>
    private static readonly Dictionary<int, KeyValuePair<float, int>> won = new Dictionary<int, KeyValuePair<float, int>>();

    public static void Init()
    {
        ModEvents.GameUpdate.RegisterHandler(Update);
    }

    /// <summary>
    /// A player whose quest reached the defense joins it, starting it if needed.
    /// </summary>
    public static void Join(int questCode, int playerId, DefenseSettingsDEM settings)
    {
        if (won.TryGetValue(questCode, out KeyValuePair<float, int> result))
        {
            // The party already won it; don't start it over for someone who arrives late
            SendStatus(questCode, playerId, new DefenseStatusDEM
            {
                WavesDone = result.Value,
                Waves = result.Value,
                Result = DefenseStatusDEM.Results.Won,
            });
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

    private static void Update(ref ModEvents.SGameUpdateData data)
    {
        if (defenses.Count == 0 || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
            return;

        World world = GameManager.Instance.World;
        if (world == null)
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
                won[defense.QuestCode] = new KeyValuePair<float, int>(Time.time, defense.Waves);
        }

        if (won.Count > 0)
        {
            var forgotten = new List<int>();
            foreach (KeyValuePair<int, KeyValuePair<float, int>> entry in won)
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

    public int Waves => settings.Waves;

    protected readonly DefenseSettingsDEM settings;
    protected int wavesDone;
    protected bool fighting;
    protected float timer;
    protected readonly List<int> zombies = new List<int>();
    protected readonly List<Boss> bosses = new List<Boss>();
    private float retargetTimer;
    private bool marked;
    private int lastReportedAlive = -1;

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
    protected void SpawnWaveZombies(World world, List<EntityPlayer> players, GameRandom random, int gameStage, float sizeMultiplier, Vector3 center, float radius)
    {
        string[] spawners = settings.Spawners.Split(',');
        GameStageDefinition.Stage stage = GameStageDefinition.GetGameStage(spawners[random.RandomRange(spawners.Length)].Trim())?.GetStage(gameStage);
        if (stage == null || stage.spawnGroups.Count == 0)
            return;

        // The wave's size always comes from the defense spawner; themed spawners (hordes of cops, soldiers,
        // spiders, ...) only pick which zombies, since their counts are for wandering hordes.
        // Spawner counts are for one player; more players in the defense means more zombies.
        int count = Mathf.RoundToInt(Mathf.Max(WaveDirectorDEM.WaveSize(gameStage), 4) * sizeMultiplier);
        count += count * (players.Count - 1) / 2;
        int lastClassId = -1;
        for (int i = 0; i < count; i++)
        {
            GameStageDefinition.SpawnGroup group = stage.spawnGroups[i % stage.spawnGroups.Count];
            int classId = EntityGroups.GetRandomFromGroup(group.groupName, ref lastClassId, random);
            if (RingPosition(world, random, center, radius, out Vector3 position))
                Spawn(world, classId, position, Closest(players, position), random);
        }
        marked = false;
        lastReportedAlive = -1;
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
        if (marked || zombies.Count > 3)
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
            ZombiesLeft = zombies.Count,
            MessageKey = messageKey ?? "",
            MessageValue = messageValue,
            BreakSeconds = Mathf.RoundToInt(settings.BreakSeconds),
            Result = Won ? DefenseStatusDEM.Results.Won : DefenseStatusDEM.Results.None,
        };
    }

    /// <summary>
    /// Tells every listener where the defense stands, with an optional on-screen message.
    /// </summary>
    public void SendStatus(string messageKey, int messageValue = 0)
    {
        lastReportedAlive = zombies.Count;
        // A copy: the status can complete or fail the local player's quest, which makes them leave (see Update)
        foreach (int id in new List<int>(Listeners))
            WaveDirectorDEM.SendStatus(QuestCode, id, Status(messageKey, messageValue));
    }

    /// <summary>Sends the status if the number of zombies left changed.</summary>
    protected void ReportAlive()
    {
        if (zombies.Count != lastReportedAlive)
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

        TrackBosses(world, random, boss => RingPosition(world, random, settings.Center, settings.Radius, out Vector3 p) ? p : (Vector3?)null,
            Closest(players, settings.Center));
        PruneZombies(world);

        if (zombies.Count > 0 && timer <= 0f)
        {
            // Whatever is left is stuck or lost; don't let it stall the quest
            RemoveZombies();
            SendStatus("DefendWavesDEM_retreat");
        }

        if (zombies.Count == 0)
        {
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
        // Each wave is a little harder than the last; a last stand's waves also keep getting bigger
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength * (1f + 0.15f * wavesDone));
        float size = Endless ? 1f + 0.1f * wavesDone : 1f;
        SpawnWaveZombies(world, players, random, gameStage, size, settings.Center, settings.Radius);

        bool boss = Endless
            ? settings.BossEvery > 0 && (wavesDone + 1) % settings.BossEvery == 0
            : wavesDone == settings.Waves - 1;
        if (boss && settings.Bosses != "" && RingPosition(world, random, settings.Center, settings.Radius, out Vector3 bossSpawn))
            SpawnBoss(world, settings.Bosses, bossSpawn, Closest(players, bossSpawn), random);

        if (zombies.Count == 0)
        {
            // Nowhere to spawn them (all water, or a trader's area): try again shortly rather than skip the wave
            timer = 5f;
            return;
        }

        fighting = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
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
        var spawnPoints = new List<Vector3>();
        PrefabInstance poi = GameManager.Instance.GetDynamicPrefabDecorator()?.GetPrefabFromWorldPosInside(
            Mathf.FloorToInt(settings.Center.x), Mathf.FloorToInt(settings.Center.z));
        if (poi != null)
        {
            foreach (SleeperVolume volume in poi.sleeperVolumes)
            {
                foreach (SleeperVolume.SpawnPoint point in volume.spawnPointList)
                    spawnPoints.Add(point.pos.ToVector3() + new Vector3(0.5f, 0f, 0.5f));
            }
        }

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
            SendStatus("OutpostDEM_attack", outpost.NightsHeld + 1);
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

        if (zombies.Count == 0)
        {
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
        SpawnWaveZombies(world, players, random, gameStage, 1f + 0.2f * night, settings.Center, settings.Radius);
        if (zombies.Count == 0)
        {
            timer = 5f;
            return;
        }
        waveActive = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
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
