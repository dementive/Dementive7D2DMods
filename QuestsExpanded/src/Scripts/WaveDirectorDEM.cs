using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Runs the zombies of defense quests on the server. There is one defense per quest (keyed by quest code, which
/// shared copies keep), so a party fights it together: every member whose quest reaches the defense joins it, the
/// first one starts it, and it only stops when every member has left.
/// Waves are drawn from gamestage spawners (vanilla's defenseGSList by default) at the party's gamestage, spawn just
/// outside the defended area all around it and go after the players. The final wave can bring a boss. A bounty is
/// a boss with a few escorts deep inside a POI instead of waves.
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
            SendWon(questCode, playerId, result.Value);
            return;
        }

        bool starting = !defenses.TryGetValue(questCode, out Defense defense);
        if (starting)
        {
            defense = new Defense(questCode, settings);
            defenses.Add(questCode, defense);
        }
        defense.Listeners.Add(playerId);
        defense.SendStatus(starting && !settings.Bounty ? "DefendWavesDEM_starting" : null);
    }

    /// <summary>
    /// A player's quest left the defense (failed, abandoned or logged out). The defense stops when nobody is left.
    /// </summary>
    public static void Leave(int questCode, int playerId)
    {
        if (defenses.TryGetValue(questCode, out Defense defense))
        {
            defense.Listeners.Remove(playerId);
            if (defense.Listeners.Count == 0)
            {
                defense.RemoveZombies();
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

        float deltaTime = Time.deltaTime;
        var finished = new List<Defense>();
        foreach (Defense defense in defenses.Values)
        {
            if (defense.Tick(world, deltaTime))
                finished.Add(defense);
        }
        foreach (Defense defense in finished)
        {
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

    private static void SendWon(int questCode, int playerId, int waves)
    {
        World world = GameManager.Instance.World;
        var package = NetPackageManager.GetPackage<NetPackageDefendWavesDEM>()
            .SetupStatus(questCode, waves, waves, false, 0, "");
        if (world?.GetEntity(playerId) is EntityPlayerLocal)
            package.ApplyStatus(world);
        else
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(package, _onlyClientsAttachedToAnEntity: false, playerId);
    }

    private class Defense
    {
        public readonly int QuestCode;
        public readonly HashSet<int> Listeners = new HashSet<int>();

        /// <summary>Every wave was beaten (or the bounty killed), rather than everyone leaving.</summary>
        public bool Won;

        public int Waves => settings.Waves;

        private readonly DefenseSettingsDEM settings;
        private int wavesDone;
        private bool fighting;
        private bool marked;
        private float timer = BreakSeconds;
        private float retargetTimer;
        private int lastReportedAlive = -1;
        private readonly List<int> zombies = new List<int>();
        private int bossId = -1;
        private Vector3 bossPosition;

        public Defense(int questCode, DefenseSettingsDEM settings)
        {
            QuestCode = questCode;
            this.settings = settings;
            wavesDone = settings.WavesDone;
            // A bounty is waiting in the POI as soon as the clear starts
            if (settings.Bounty)
                timer = 0f;
        }

        /// <summary>
        /// Advances the defense. Returns true when it is over.
        /// </summary>
        public bool Tick(World world, float deltaTime)
        {
            List<EntityPlayer> players = ListenerPlayers(world);
            if (players.Count == 0)
            {
                RemoveZombies();
                return true;
            }

            timer -= deltaTime;

            if (!fighting)
            {
                if (timer <= 0f)
                {
                    if (settings.Bounty)
                        SpawnBounty(world, players);
                    else
                        SpawnWave(world, players);
                }
                return false;
            }

            if (bossId != -1)
            {
                if (world.GetEntity(bossId) is EntityAlive boss && !boss.IsDead())
                {
                    bossPosition = boss.position;
                }
                else
                {
                    DropBossBag(world);
                    bossId = -1;
                    if (settings.Bounty)
                    {
                        wavesDone = settings.Waves;
                        fighting = false;
                        Won = true;
                        SendStatus("DefendWavesDEM_bountydead");
                        return true;
                    }
                }
            }

            if (settings.Bounty)
                return false;

            zombies.RemoveAll(id => !(world.GetEntity(id) is EntityAlive zombie) || zombie.IsDead());

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
                timer = BreakSeconds;
                lastReportedAlive = -1;
                if (wavesDone >= settings.Waves)
                {
                    Won = true;
                    SendStatus("DefendWavesDEM_complete");
                    return true;
                }
                SendStatus("DefendWavesDEM_cleared");
                return false;
            }

            if (!marked && zombies.Count <= 3)
            {
                // Mark the last few so nobody has to hunt for them
                marked = true;
                foreach (int id in zombies)
                {
                    if (world.GetEntity(id) is EntityAlive zombie)
                        zombie.Buffs.AddBuff(MarkedBuff);
                }
            }

            retargetTimer -= deltaTime;
            if (retargetTimer <= 0f)
            {
                retargetTimer = 10f;
                foreach (int id in zombies)
                {
                    if (world.GetEntity(id) is EntityAlive zombie && zombie.GetAttackTarget() == null)
                        zombie.SetAttackTarget(Closest(players, zombie.position), 1200);
                }
            }

            if (zombies.Count != lastReportedAlive)
                SendStatus(null);

            return false;
        }

        private void SpawnWave(World world, List<EntityPlayer> players)
        {
            GameRandom random = world.GetGameRandom();
            // Each wave is a little harder than the last
            int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength * (1f + 0.15f * wavesDone));
            GameStageDefinition.Stage stage = PickSpawner(random)?.GetStage(gameStage);

            int lastClassId = -1;
            if (stage != null && stage.spawnGroups.Count > 0)
            {
                // The wave's size always comes from the defense spawner; themed spawners (hordes of cops, soldiers,
                // spiders, ...) only pick which zombies, since their counts are for wandering hordes.
                // Spawner counts are for one player; more players in the defense means more zombies.
                int count = Mathf.Max(WaveSize(gameStage), 4);
                count += count * (players.Count - 1) / 2;
                for (int i = 0; i < count; i++)
                {
                    GameStageDefinition.SpawnGroup group = stage.spawnGroups[i % stage.spawnGroups.Count];
                    int classId = EntityGroups.GetRandomFromGroup(group.groupName, ref lastClassId, random);
                    if (RingPosition(world, random, out Vector3 position))
                        Spawn(world, classId, position, players, random);
                }
            }

            if (wavesDone == settings.Waves - 1 && settings.Bosses != "" && RingPosition(world, random, out Vector3 bossSpawn))
                SpawnBoss(world, bossSpawn, players, random);

            fighting = true;
            marked = false;
            timer = WaveTimeLimit;
            retargetTimer = 10f;
            SendStatus("DefendWavesDEM_incoming");
        }

        /// <summary>
        /// The boss waits at the POI sleeper spawn point farthest from the players, with a few escorts nearby.
        /// </summary>
        private void SpawnBounty(World world, List<EntityPlayer> players)
        {
            GameRandom random = world.GetGameRandom();
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

            Vector3 lair;
            if (spawnPoints.Count > 0)
            {
                spawnPoints.Sort((a, b) => DistanceToPlayers(players, b).CompareTo(DistanceToPlayers(players, a)));
                lair = spawnPoints[0];
            }
            else if (!RingPosition(world, random, out lair))
            {
                lair = settings.Center;
            }

            SpawnBoss(world, lair, players, random);

            // Escorts at the spawn points nearest the boss
            int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
            GameStageDefinition.Stage stage = PickSpawner(random)?.GetStage(gameStage);
            if (stage != null && stage.spawnGroups.Count > 0 && spawnPoints.Count > 1)
            {
                spawnPoints.Sort((a, b) => (a - lair).sqrMagnitude.CompareTo((b - lair).sqrMagnitude));
                int escorts = Mathf.Clamp(WaveSize(gameStage) / 3, 2, 6);
                int lastClassId = -1;
                for (int i = 1; i <= escorts && i < spawnPoints.Count; i++)
                {
                    int classId = EntityGroups.GetRandomFromGroup(stage.spawnGroups[0].groupName, ref lastClassId, random);
                    Spawn(world, classId, spawnPoints[i], null, random);
                }
            }

            fighting = true;
            SendStatus("DefendWavesDEM_bounty");
        }

        private static int WaveSize(int gameStage)
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

        private GameStageDefinition PickSpawner(GameRandom random)
        {
            string[] spawners = settings.Spawners.Split(',');
            return GameStageDefinition.GetGameStage(spawners[random.RandomRange(spawners.Length)].Trim());
        }

        private void SpawnBoss(World world, Vector3 position, List<EntityPlayer> players, GameRandom random)
        {
            string[] bosses = settings.Bosses.Split(',');
            int classId = EntityClass.FromString(bosses[random.RandomRange(bosses.Length)].Trim());
            // A bounty waits in its lair until someone finds it
            EntityAlive boss = Spawn(world, classId, position, settings.Bounty ? null : players, random);
            if (boss == null)
                return;
            boss.Buffs.AddBuff(BossBuff);
            bossId = boss.entityId;
            bossPosition = boss.position;
        }

        private EntityAlive Spawn(World world, int classId, Vector3 position, List<EntityPlayer> attackPlayers, GameRandom random)
        {
            if (classId == -1 || classId == 0)
                return null;

            var rotation = new Vector3(0f, random.RandomFloat * 360f, 0f);
            if (!(EntityFactory.CreateEntity(classId, position, rotation) is EntityAlive zombie))
                return null;

            zombie.SetSpawnerSource(EnumSpawnerSource.Dynamic);
            world.SpawnEntityInWorld(zombie);
            if (attackPlayers != null)
                zombie.SetAttackTarget(Closest(attackPlayers, position), 1200);
            zombies.Add(zombie.entityId);
            return zombie;
        }

        private void DropBossBag(World world)
        {
            int bagClass = EntityClass.FromString(BossBag);
            if (bagClass != -1 && bagClass != 0 && EntityFactory.CreateEntity(bagClass, bossPosition + Vector3.up, Vector3.zero) is Entity bag)
                world.SpawnEntityInWorld(bag);
        }

        /// <summary>
        /// A spot on the ground 6-14m outside the defended area, in a random direction, not in water or a trader's area.
        /// </summary>
        private bool RingPosition(World world, GameRandom random, out Vector3 position)
        {
            for (int attempt = 0; attempt < 20; attempt++)
            {
                float angle = random.RandomFloat * Mathf.PI * 2f;
                float distance = settings.Radius + 6f + random.RandomFloat * 8f;
                int x = Mathf.FloorToInt(settings.Center.x + Mathf.Cos(angle) * distance);
                int z = Mathf.FloorToInt(settings.Center.z + Mathf.Sin(angle) * distance);
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

        public void RemoveZombies()
        {
            World world = GameManager.Instance.World;
            foreach (int id in zombies)
            {
                if (world?.GetEntity(id) is EntityAlive zombie && !zombie.IsDead())
                    world.RemoveEntity(id, EnumRemoveEntityReason.Despawned);
            }
            zombies.Clear();
            bossId = -1;
        }

        private List<EntityPlayer> ListenerPlayers(World world)
        {
            var players = new List<EntityPlayer>();
            foreach (int id in Listeners)
            {
                if (world.GetEntity(id) is EntityPlayer player)
                    players.Add(player);
            }
            return players;
        }

        private static EntityPlayer Closest(List<EntityPlayer> players, Vector3 position)
        {
            EntityPlayer closest = players[0];
            foreach (EntityPlayer player in players)
            {
                if ((player.position - position).sqrMagnitude < (closest.position - position).sqrMagnitude)
                    closest = player;
            }
            return closest;
        }

        private static float DistanceToPlayers(List<EntityPlayer> players, Vector3 position)
        {
            return (Closest(players, position).position - position).sqrMagnitude;
        }

        /// <summary>
        /// Tells every listener where the defense stands, with an optional on-screen message.
        /// </summary>
        public void SendStatus(string messageKey)
        {
            lastReportedAlive = zombies.Count;
            World world = GameManager.Instance.World;
            foreach (int id in Listeners)
            {
                var package = NetPackageManager.GetPackage<NetPackageDefendWavesDEM>()
                    .SetupStatus(QuestCode, wavesDone, settings.Waves, fighting, zombies.Count, messageKey ?? "");
                if (world?.GetEntity(id) is EntityPlayerLocal)
                    package.ApplyStatus(world);
                else
                    SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(package, _onlyClientsAttachedToAnEntity: false, id);
            }
        }
    }
}
