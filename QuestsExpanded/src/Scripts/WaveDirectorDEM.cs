using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Runs the zombie waves of defense quests on the server. There is one defense per quest (keyed by quest code,
/// which shared copies keep), so a party fights one set of waves together: the first member whose quest reaches
/// the defense joins it and starts it, the others join it, and it only stops when every member has left.
/// Waves come from the vanilla defenseGSList spawner at the party's gamestage, spawn just outside the POI all
/// around it and go after the players.
/// </summary>
public static class WaveDirectorDEM
{
    public const string SpawnList = "defenseGSList";

    /// <summary>Seconds between waves.</summary>
    public const float BreakSeconds = 15f;

    /// <summary>Seconds a wave can last before the zombies that are left (stuck or lost) are removed.</summary>
    public const float WaveTimeLimit = 240f;

    private static readonly Dictionary<int, Defense> defenses = new Dictionary<int, Defense>();

    public static void Init()
    {
        ModEvents.GameUpdate.RegisterHandler(Update);
    }

    /// <summary>
    /// A player whose quest reached the defense joins it, starting it if needed.
    /// </summary>
    public static void Join(int questCode, int playerId, Vector3 poiPosition, Vector3 poiSize, int waves, int wavesDone)
    {
        bool starting = !defenses.TryGetValue(questCode, out Defense defense);
        if (starting)
        {
            defense = new Defense(questCode, poiPosition, poiSize, waves, wavesDone);
            defenses.Add(questCode, defense);
        }
        defense.Listeners.Add(playerId);
        defense.SendStatus(starting ? "DefendWavesDEM_starting" : null);
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
        var finished = new List<int>();
        foreach (Defense defense in defenses.Values)
        {
            if (defense.Tick(world, deltaTime))
                finished.Add(defense.QuestCode);
        }
        foreach (int questCode in finished)
            defenses.Remove(questCode);
    }

    private class Defense
    {
        public readonly int QuestCode;
        public readonly HashSet<int> Listeners = new HashSet<int>();

        private readonly Vector3 center;
        private readonly float radius;
        private readonly int waves;
        private int wavesDone;
        private bool fighting;
        private float timer = BreakSeconds;
        private float retargetTimer;
        private int lastReportedAlive = -1;
        private readonly List<int> zombies = new List<int>();

        public Defense(int questCode, Vector3 poiPosition, Vector3 poiSize, int waves, int wavesDone)
        {
            QuestCode = questCode;
            center = new Vector3(poiPosition.x + poiSize.x / 2f, poiPosition.y, poiPosition.z + poiSize.z / 2f);
            // Half the POI's diagonal: anything farther than this from the center is outside the POI
            radius = new Vector2(poiSize.x / 2f, poiSize.z / 2f).magnitude;
            this.waves = waves;
            this.wavesDone = wavesDone;
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
                    SpawnWave(world, players);
                return false;
            }

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
                if (wavesDone >= waves)
                {
                    SendStatus("DefendWavesDEM_complete");
                    return true;
                }
                SendStatus("DefendWavesDEM_cleared");
                return false;
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
            GameStageDefinition spawner = GameStageDefinition.GetGameStage(SpawnList);
            int gameStage = GameStageDefinition.CalcGameStageAround(players[0]);
            // Each wave is a little harder than the last
            int waveGameStage = Mathf.RoundToInt(gameStage * (1f + 0.15f * wavesDone));
            GameStageDefinition.Stage stage = spawner?.GetStage(waveGameStage);

            int lastClassId = -1;
            GameRandom random = world.GetGameRandom();
            if (stage != null)
            {
                foreach (GameStageDefinition.SpawnGroup group in stage.spawnGroups)
                {
                    // defenseGSList counts are for one player; more players in the defense means more zombies
                    int count = Mathf.Max(group.spawnCount, 4);
                    count += count * (players.Count - 1) / 2;
                    for (int i = 0; i < count; i++)
                    {
                        int classId = EntityGroups.GetRandomFromGroup(group.groupName, ref lastClassId, random);
                        Spawn(world, classId, players, random);
                    }
                }
            }

            fighting = true;
            timer = WaveTimeLimit;
            retargetTimer = 10f;
            SendStatus("DefendWavesDEM_incoming");
        }

        private void Spawn(World world, int classId, List<EntityPlayer> players, GameRandom random)
        {
            if (classId == -1 || !SpawnPosition(world, random, out Vector3 position))
                return;

            var rotation = new Vector3(0f, random.RandomFloat * 360f, 0f);
            if (!(EntityFactory.CreateEntity(classId, position, rotation) is EntityAlive zombie))
                return;

            zombie.SetSpawnerSource(EnumSpawnerSource.Dynamic);
            world.SpawnEntityInWorld(zombie);
            zombie.SetAttackTarget(Closest(players, position), 1200);
            zombies.Add(zombie.entityId);
        }

        /// <summary>
        /// A spot on the ground 6-14m outside the POI, in a random direction, not in water or a trader's area.
        /// </summary>
        private bool SpawnPosition(World world, GameRandom random, out Vector3 position)
        {
            for (int attempt = 0; attempt < 20; attempt++)
            {
                float angle = random.RandomFloat * Mathf.PI * 2f;
                float distance = radius + 6f + random.RandomFloat * 8f;
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

        public void RemoveZombies()
        {
            World world = GameManager.Instance.World;
            foreach (int id in zombies)
            {
                if (world?.GetEntity(id) is EntityAlive zombie && !zombie.IsDead())
                    world.RemoveEntity(id, EnumRemoveEntityReason.Despawned);
            }
            zombies.Clear();
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
                    .SetupStatus(QuestCode, wavesDone, waves, fighting, zombies.Count, messageKey ?? "");
                if (world?.GetEntity(id) is EntityPlayerLocal)
                    package.ApplyStatus(world);
                else
                    SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(package, _onlyClientsAttachedToAnEntity: false, id);
            }
        }
    }
}
