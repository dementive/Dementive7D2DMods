using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Shared code for the defenses that look after friendly NPCs from an NPC mod (Rescue's survivors, Safehouse's
/// refugees): spawning them, picking them up (a listener walks up to one and it follows them, through SCore), making
/// them wait when the player they followed dies or leaves, bringing back ones that vanished, and sending the zombies
/// after them as well as the players.
/// </summary>
internal abstract class NpcDefense : Defense
{
    /// <summary>Buff on NPCs waiting for a player to come and get them: a marker on the map and compass.</summary>
    public const string WaitingBuff = "buffDementiveWaiting";

    /// <summary>
    /// SCore's NPCs take no damage while they have this buff (QuestsExpanded's buffs.xml defines it if nothing else
    /// does). Survivors have it until a player is close, so they're never dead before anyone arrives, and refugees
    /// while they wait at the trader.
    /// </summary>
    public const string ProtectedBuff = "buffInvulnerable";

    /// <summary>
    /// Cvar on the NPCs a quest spawned while it looks after them (<see cref="Tag"/> of its quest code), so ones it no
    /// longer tracks can be found and despawned (WaveDirectorDEM.CleanUpQuestNpcs).
    /// </summary>
    public const string TagCvar = "questNpcDEM";

    /// <summary>Cvar on refugees who settled into a safehouse (the safehouse's <see cref="Tag"/>): they stay for good.</summary>
    public const string SettledCvar = "safehouseNpcDEM";

    /// <summary>A quest code as a cvar value (cvars are floats, exact up to 2^24).</summary>
    public static float Tag(int questCode)
    {
        return (questCode & 0xFFFFFF) + 1;
    }

    /// <summary>How close a player has to get to an NPC for it to follow them.</summary>
    private const float PickUpDistance = 3f;

    /// <summary>Seconds an NPC has to be missing (with its spot loaded) before it's brought back.</summary>
    private const float MissingSeconds = 5f;

    protected class Member
    {
        public int Id = -1;
        public int ClassId;
        public Vector3 Position;
        /// <summary>The player it follows, or 0.</summary>
        public int Leader;
        /// <summary>It followed a player at some point.</summary>
        public bool Led;
        /// <summary>Delivered: saved (Rescue) or settled in (Safehouse).</summary>
        public bool Done;
        public bool Lost;
        public float Missing;
    }

    protected readonly List<Member> members = new List<Member>();
    private float npcRetargetTimer;

    /// <summary>Members lost since the defense last looked (<see cref="TakeNewlyLost"/>).</summary>
    private int newlyLost;

    protected NpcDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
    }

    /// <summary>Whether the entity is one of the members the defense looks after.</summary>
    public bool IsMember(int entityId)
    {
        foreach (Member member in members)
        {
            if (member.Id == entityId && !member.Lost)
                return true;
        }
        return false;
    }

    /// <summary>
    /// Server side: an NPC died (from DefenseKillPatches). Returns true if it was one of the members.
    /// </summary>
    public bool OnNpcDied(int entityId)
    {
        foreach (Member member in members)
        {
            if (member.Id == entityId && !member.Lost)
            {
                MarkLost(member);
                return true;
            }
        }
        return false;
    }

    protected void MarkLost(Member member)
    {
        if (member.Lost)
            return;
        member.Lost = true;
        member.Leader = 0;
        newlyLost++;
        OnLost(member);
    }

    /// <summary>A member died.</summary>
    protected virtual void OnLost(Member member)
    {
    }

    /// <summary>How many members died since the last call.</summary>
    protected int TakeNewlyLost()
    {
        int lost = newlyLost;
        newlyLost = 0;
        return lost;
    }

    /// <summary>Every member is delivered or lost (and there were some).</summary>
    protected bool AllResolved()
    {
        foreach (Member member in members)
        {
            if (!member.Done && !member.Lost)
                return false;
        }
        return members.Count > 0;
    }

    /// <summary>Members still to look after: alive, not delivered yet.</summary>
    protected IEnumerable<Member> Active()
    {
        foreach (Member member in members)
        {
            if (!member.Done && !member.Lost)
                yield return member;
        }
    }

    protected EntityAlive SpawnMember(World world, Member member, Vector3 position, GameRandom random, bool persist, bool protect)
    {
        if (member.ClassId == -1 || member.ClassId == 0)
            return null;
        var rotation = new Vector3(0f, random.RandomFloat * 360f, 0f);
        if (!(EntityFactory.CreateEntity(member.ClassId, position, rotation) is EntityAlive npc))
            return null;

        // Persisted NPCs are saved with the world (SCore keeps NPCs with a "Persist" cvar)
        npc.SetSpawnerSource(persist ? EnumSpawnerSource.StaticSpawner : EnumSpawnerSource.Dynamic);
        world.SpawnEntityInWorld(npc);
        if (persist)
            npc.Buffs.SetCustomVar("Persist", 1f);
        npc.Buffs.SetCustomVar(TagCvar, Tag(QuestCode));
        npc.Buffs.AddBuff(NpcFollowDEM.StayBuff);
        npc.Buffs.AddBuff(WaitingBuff);
        if (protect)
            npc.Buffs.AddBuff(ProtectedBuff);
        member.Id = npc.entityId;
        member.Position = npc.position;
        member.Missing = 0f;
        return npc;
    }

    /// <summary>
    /// Keeps track of the members (deaths found here and from the death hook are in <see cref="TakeNewlyLost"/>).
    /// </summary>
    /// <param name="canPickUp">Whether players can pick waiting members up now.</param>
    /// <param name="persist">Whether members brought back are saved with the world.</param>
    /// <param name="unprotectDistance">Waiting members lose their protection once a player is this close (0: only
    /// when picked up).</param>
    /// <param name="pickedUp">Members a player picked up just now.</param>
    protected void TrackMembers(World world, List<EntityPlayer> players, GameRandom random, float deltaTime, bool canPickUp,
        bool persist, float unprotectDistance, List<Member> pickedUp)
    {
        foreach (Member member in members)
        {
            if (member.Done || member.Lost)
                continue;

            var npc = world.GetEntity(member.Id) as EntityAlive;
            if (npc != null && npc.IsDead())
            {
                MarkLost(member);
                continue;
            }

            if (npc == null)
            {
                BringBack(world, member, players, random, deltaTime, persist);
                continue;
            }

            member.Position = npc.position;
            member.Missing = 0f;
            if (unprotectDistance > 0f && npc.Buffs.HasBuff(ProtectedBuff))
            {
                foreach (EntityPlayer player in players)
                {
                    if ((player.position - npc.position).sqrMagnitude <= unprotectDistance * unprotectDistance)
                    {
                        npc.Buffs.RemoveBuff(ProtectedBuff);
                        break;
                    }
                }
            }
            if (member.Leader != 0)
            {
                // The player it followed died or left: it waits where it is for someone to come and get it
                var leader = world.GetEntity(member.Leader) as EntityPlayer;
                if (leader == null || !players.Contains(leader))
                {
                    NpcFollowDEM.Stay(npc, member.Leader);
                    npc.Buffs.AddBuff(WaitingBuff);
                    member.Leader = 0;
                }
                continue;
            }

            if (!canPickUp)
                continue;
            foreach (EntityPlayer player in players)
            {
                if ((player.position - npc.position).sqrMagnitude > PickUpDistance * PickUpDistance)
                    continue;
                if (NpcFollowDEM.Follow(npc, player))
                {
                    npc.Buffs.RemoveBuff(WaitingBuff);
                    npc.Buffs.RemoveBuff(ProtectedBuff);
                    member.Leader = player.entityId;
                    member.Led = true;
                    pickedUp?.Add(member);
                }
                break;
            }
        }
    }

    /// <summary>
    /// A member that's gone without dying: unloaded with its chunk (it comes back with it if it's saved), or removed
    /// (NPC Core lists hired NPCs vanishing around vehicles as a known issue). Once the spot it was last seen at has been
    /// loaded for a few seconds without it, it comes back there, or next to the player it was following. While that
    /// spot is unloaded it may just be saved there, so it isn't replaced (a copy would follow someone forever once the
    /// original loaded again; WaveDirectorDEM.CleanUpQuestNpcs despawns any that still turn up).
    /// </summary>
    private void BringBack(World world, Member member, List<EntityPlayer> players, GameRandom random, float deltaTime, bool persist)
    {
        var leader = member.Leader != 0 ? world.GetEntity(member.Leader) as EntityPlayer : null;
        if (leader != null && !players.Contains(leader))
            leader = null;
        if (world.GetChunkFromWorldPos(new Vector3i(member.Position)) == null)
        {
            member.Missing = 0f;
            return;
        }
        Vector3 at = member.Position;
        if (leader != null && Around(world, random, leader.position, 1.5f, 3f, out Vector3 near))
            at = near;
        member.Missing += deltaTime;
        if (member.Missing < MissingSeconds)
            return;

        // Still protected if nobody has come for it yet
        EntityAlive npc = SpawnMember(world, member, at, random, persist, leader == null && !member.Led);
        if (npc == null)
            return;
        if (leader != null && NpcFollowDEM.Follow(npc, leader))
            npc.Buffs.RemoveBuff(WaitingBuff);
        else
            member.Leader = 0;
    }

    /// <summary>The member's entity, if it's in the world and alive.</summary>
    protected static EntityAlive Npc(World world, Member member)
    {
        return world.GetEntity(member.Id) is EntityAlive npc && !npc.IsDead() ? npc : null;
    }

    /// <summary>Takes a member out of the world (delivered, or the defense is over), letting go of its leader.</summary>
    protected static void RemoveMember(World world, Member member)
    {
        if (Npc(world, member) is EntityAlive npc)
        {
            NpcFollowDEM.Release(npc, member.Leader);
            world.RemoveEntity(npc.entityId, EnumRemoveEntityReason.Despawned);
        }
        member.Leader = 0;
    }

    /// <summary>
    /// Every 10 seconds, sends zombies without a target after the closest player or member (NPC Core already makes
    /// zombies go after NPCs they see; this keeps a siege from standing around).
    /// </summary>
    protected void RetargetAtMembers(World world, List<EntityPlayer> players, float deltaTime)
    {
        npcRetargetTimer -= deltaTime;
        if (npcRetargetTimer > 0f)
            return;
        npcRetargetTimer = 10f;

        var targets = new List<EntityAlive>(players);
        foreach (Member member in members)
        {
            if (!member.Lost && Npc(world, member) is EntityAlive npc)
                targets.Add(npc);
        }
        if (targets.Count == 0)
            return;
        foreach (int id in zombies)
        {
            // Bandits pick their own targets; steering them at the survivors would just be an execution
            if (bandits.Contains(id) || !(world.GetEntity(id) is EntityAlive zombie) || zombie.GetAttackTarget() != null)
                continue;
            EntityAlive closest = null;
            foreach (EntityAlive target in targets)
            {
                if (closest == null || (target.position - zombie.position).sqrMagnitude < (closest.position - zombie.position).sqrMagnitude)
                    closest = target;
            }
            zombie.SetAttackTarget(closest, 1200);
        }
    }
}

/// <summary>
/// Bandit Hideout: bandits (from an NPC mod) posted through the POI, spread over its sleeper spots with the ones
/// farthest from the players first, and from tier 3 a leader with the boss buff at the far end. Over when every
/// bandit is dead. The POI's own zombies are there as usual but don't count.
/// </summary>
internal class HideoutDefense : Defense
{
    private bool spawned;
    private Vector3 lair;

    public HideoutDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
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
            if (!NpcCatalogDEM.HasHostile)
            {
                // The NPC mod that added the bandits is gone
                Failed = true;
                SendStatus("NpcQuestDEM_nonpcs");
                return true;
            }
            spawned = SpawnHideout(world, players, random);
            return false;
        }

        // A leader that unloads goes back to the far end
        TrackBosses(world, random, boss => lair, null);
        PruneZombies(world);
        if (zombies.Count == 0 && bosses.Count == 0)
        {
            wavesDone = settings.Waves;
            fighting = false;
            Won = true;
            SendStatus("BanditHideoutDEM_complete");
            return true;
        }

        MarkStragglers(world);
        ReportAlive();
        return false;
    }

    /// <summary>Returns false if no bandit could spawn, to try again.</summary>
    private bool SpawnHideout(World world, List<EntityPlayer> players, GameRandom random)
    {
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
        int count = BanditCount(WaveCount(gameStage, 1f, players.Count));
        bool leader = settings.BossCount > 0;

        List<Vector3> spots = SpreadOut(PoiSpawnPoints(), players, count + (leader ? 1 : 0), 6f);
        if (spots.Count == 0)
            spots.Add(settings.Center);
        lair = spots[0];

        if (leader)
        {
            int classId = NpcCatalogDEM.PickLeader(settings.Tier, random);
            if (EntityClass.list.Dict.TryGetValue(classId, out EntityClass leaderClass))
                SpawnBoss(world, leaderClass.entityClassName, lair, null, random);
            if (spots.Count > 1)
                spots.RemoveAt(0);
        }

        // Posted where they stand until they see someone
        SpawnBandits(world, null, random, count, i => spots[i % spots.Count]);
        if (zombies.Count == 0)
            return false;

        fighting = true;
        SendStatus("BanditHideoutDEM_start");
        return true;
    }
}

/// <summary>
/// Rescue: a group of survivors (friendly NPCs from an NPC mod) holed up at the far end of the POI, under attack
/// when the players arrive: zombies besieging them, bandits holding them (when an NPC mod adds bandits), or at tiers
/// 5-6 both. Once the attackers are dead, a player who walks up to a survivor is followed by them (SCore's follow
/// system); reinforcements come when the first survivor starts following and when the group leaves the POI's area.
/// A survivor who reaches a trader's compound goes inside and is saved. Over when every survivor is saved or dead;
/// lost if none were saved.
/// The objective's value is saved | lost &lt;&lt; 4, so a quest picked up again carries on with the ones left.
/// </summary>
internal class RescueDefense : NpcDefense
{
    public enum Stages
    {
        Arriving,
        Attack,
        Lead,
    }

    private Stages stage;
    private int saved;
    private int lost;
    private int siegeWavesLeft;
    /// <summary>The attack has bandits in it.</summary>
    private bool banditAttack;
    private int reinforcements;
    private float breakTimer;
    private float upkeepTimer;
    private readonly List<int> savedClasses = new List<int>();

    public RescueDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
        saved = settings.WavesDone & 15;
        lost = (settings.WavesDone >> 4) & 15;
    }

    protected override string StartMessage => null;

    public override bool Tick(World world, float deltaTime)
    {
        List<EntityPlayer> players = ListenerPlayers(world);
        if (players.Count == 0)
        {
            if (NobodyOnline(world))
            {
                Abandon();
                return true;
            }
            return false;
        }

        GameRandom random = world.GetGameRandom();
        if (stage == Stages.Arriving)
        {
            if (!NpcCatalogDEM.HasFollowers)
            {
                Failed = true;
                SendStatus("NpcQuestDEM_nonpcs");
                return true;
            }
            if (StartRescue(world, players, random))
                stage = Stages.Attack;
            return false;
        }

        upkeepTimer -= deltaTime;
        if (upkeepTimer <= 0f)
        {
            upkeepTimer = 0.5f;
            var pickedUp = new List<Member>();
            TrackMembers(world, players, random, 0.5f, stage == Stages.Lead, false, 15f, pickedUp);
            if (TakeNewlyLost() > 0)
                SendStatus("RescueDEM_lost", lost);
            if (pickedUp.Count > 0 && reinforcements == 0)
                SendReinforcements(world, players, random, null);
            if (stage == Stages.Lead)
                Deliver(world, players, random);
            if (AllResolved())
                return Finish(world);
        }

        PruneZombies(world);
        timer -= deltaTime;
        if (timer <= 0f && zombies.Exists(id => !bandits.Contains(id)))
        {
            // Zombies left of a wave are stuck or lost; don't let them stall the rescue. Bandits hold their posts
            RemoveWaveZombies();
            SendStatus("DefendWavesDEM_retreat");
        }

        if (stage == Stages.Attack && zombies.Count == 0)
        {
            if (siegeWavesLeft > 0)
            {
                breakTimer -= deltaTime;
                if (breakTimer <= 0f)
                    SpawnSiege(world, players, random);
            }
            else
            {
                stage = Stages.Lead;
                fighting = false;
                SendStatus("RescueDEM_broken");
            }
            return false;
        }

        if (stage == Stages.Attack)
            MarkStragglers(world);
        RetargetAtMembers(world, players, deltaTime);
        ReportAlive();
        return false;
    }

    /// <summary>Spawns the survivors left and the attack on them. Returns false to try again.</summary>
    private bool StartRescue(World world, List<EntityPlayer> players, GameRandom random)
    {
        List<Vector3> points = PoiSpawnPoints();
        Vector3 hideout = points.Count > 0 ? SpreadOut(points, players, 1, 0f)[0] : settings.Center;

        // The group sits together at the spots nearest the far end
        var near = new List<Vector3>(points);
        near.Sort((a, b) => (a - hideout).sqrMagnitude.CompareTo((b - hideout).sqrMagnitude));
        int left = Mathf.Max(0, settings.Count - saved - lost);
        int groupSpots = Mathf.Clamp(left, 1, Mathf.Max(1, near.Count));
        for (int i = 0; i < left; i++)
        {
            var member = new Member { ClassId = NpcCatalogDEM.PickFollower(random) };
            Vector3 spot = near.Count > 0 ? near[i % groupSpots] : hideout;
            if (SpawnMember(world, member, spot, random, false, true) != null)
                members.Add(member);
        }
        if (members.Count == 0)
            return false;

        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
        banditAttack = NpcCatalogDEM.HasHostile && (settings.Tier >= 5 || random.RandomFloat < 0.5f);
        siegeWavesLeft = !banditAttack || settings.Tier >= 5 ? (settings.Tier >= 4 ? 2 : 1) : 0;

        if (banditAttack)
        {
            // Bandits posted around the group, at the next spots out
            var posts = near.Count > groupSpots ? near.GetRange(groupSpots, Mathf.Min(near.Count - groupSpots, 8)) : new List<Vector3> { hideout };
            SpawnBandits(world, null, random, BanditCount(WaveCount(gameStage, 1f, players.Count)), i => posts[i % posts.Count]);
        }
        if (siegeWavesLeft > 0)
            SpawnSiege(world, players, random);

        fighting = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
        SendStatus(banditAttack && siegeWavesLeft > 0 ? "RescueDEM_start_both" : banditAttack ? "RescueDEM_start_bandits" : "RescueDEM_start_siege");
        return true;
    }

    /// <summary>A wave of zombies besieging the group: half out of the building, half from just outside it.</summary>
    private void SpawnSiege(World world, List<EntityPlayer> players, GameRandom random)
    {
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
        int first = zombies.Count;
        SpawnWaveZombies(world, players, random, gameStage, 1f);
        siegeWavesLeft--;
        breakTimer = 5f;
        timer = WaveDirectorDEM.WaveTimeLimit;
        // This wave's zombies go after the survivors as much as the players
        for (int i = first; i < zombies.Count; i++)
        {
            if (!(world.GetEntity(zombies[i]) is EntityAlive zombie))
                continue;
            EntityAlive closest = null;
            foreach (Member member in Active())
            {
                if (Npc(world, member) is EntityAlive npc && (closest == null
                    || (npc.position - zombie.position).sqrMagnitude < (closest.position - zombie.position).sqrMagnitude))
                    closest = npc;
            }
            if (closest != null && random.RandomFloat < 0.5f)
                zombie.SetAttackTarget(closest, 1200);
        }
    }

    /// <summary>
    /// Reinforcements: the first time from just outside the POI, the second around the player leading the group once
    /// it's out of the POI's area.
    /// </summary>
    private void SendReinforcements(World world, List<EntityPlayer> players, GameRandom random, EntityPlayer leader)
    {
        reinforcements++;
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength);
        System.Func<int, Vector3?> where = leader == null
            ? i => OutsidePosition(world, random, out Vector3 p) ? p : (Vector3?)null
            : i => Around(world, random, leader.position, 25f, 40f, out Vector3 p) ? p : (Vector3?)null;

        if (banditAttack && (siegeWavesLeft == 0 && settings.Tier < 5 || random.RandomFloat < 0.5f))
        {
            SpawnBandits(world, players, random, BanditCount(WaveCount(gameStage, 0.6f, players.Count)), where);
        }
        else
        {
            string[] spawners = settings.Spawners.Split(',');
            GameStageDefinition.Stage spawnStage = GameStageDefinition.GetGameStage(spawners[0].Trim())?.GetStage(gameStage);
            if (spawnStage != null && spawnStage.spawnGroups.Count > 0)
            {
                int lastClassId = -1;
                int count = WaveCount(gameStage, 0.6f, players.Count);
                for (int i = 0; i < count; i++)
                {
                    int classId = EntityGroups.GetRandomFromGroup(spawnStage.spawnGroups[i % spawnStage.spawnGroups.Count].groupName, ref lastClassId, random);
                    Vector3? spot = where(i);
                    if (spot.HasValue)
                        Spawn(world, classId, spot.Value, Closest(players, spot.Value), random);
                }
            }
        }
        timer = WaveDirectorDEM.WaveTimeLimit;
        SendStatus("RescueDEM_reinforcements");
    }

    /// <summary>Survivors who reached a trader's compound go inside; the group leaving the POI brings more attackers.</summary>
    private void Deliver(World world, List<EntityPlayer> players, GameRandom random)
    {
        foreach (Member member in members)
        {
            if (member.Done || member.Lost || !member.Led || !(Npc(world, member) is EntityAlive npc))
                continue;

            if (reinforcements == 1 && member.Leader != 0 && Flat(npc.position, settings.Center) > settings.Radius + 20f
                && world.GetEntity(member.Leader) is EntityPlayer leader)
                SendReinforcements(world, players, random, leader);

            if (!world.IsWithinTraderArea(new Vector3i(npc.position)))
                continue;
            member.Done = true;
            saved++;
            savedClasses.Add(member.ClassId);
            RemoveMember(world, member);
            SendStatus("RescueDEM_saved", saved);
        }
    }

    private bool Finish(World world)
    {
        fighting = false;
        RemoveZombies();
        if (saved > 0)
        {
            Won = true;
            // Survivors saved in an earlier session: someone like them
            var classes = new List<int>(savedClasses);
            GameRandom random = world.GetGameRandom();
            while (classes.Count < saved)
                classes.Add(NpcCatalogDEM.PickFollower(random));
            RescueJoinPoolDEM.Add(QuestCode, classes);
            SendStatus("RescueDEM_complete");
        }
        else
        {
            Failed = true;
            SendStatus("RescueDEM_alllost");
        }
        return true;
    }

    protected override void OnLost(Member member)
    {
        lost++;
    }

    public override void Abandon()
    {
        // Everybody left: the survivors still out there go back to waiting (they're back at the far end of the POI
        // when the quest is picked up again; ones in unloaded chunks are despawned when they load, by their tag)
        World world = GameManager.Instance.World;
        foreach (Member member in members)
        {
            if (!member.Done && !member.Lost && world != null)
                RemoveMember(world, member);
        }
        base.Abandon();
    }

    protected override DefenseStatusDEM Status(string messageKey, int messageValue)
    {
        DefenseStatusDEM status = base.Status(messageKey, messageValue);
        status.Waves = settings.Count;
        status.WavesDone = saved;
        status.Lost = lost;
        status.Stage = (int)stage;
        status.Fighting = stage == Stages.Attack;
        status.ZombiesLeft = stage == Stages.Attack ? zombies.Count : Mathf.Max(0, settings.Count - saved - lost);
        return status;
    }
}

/// <summary>
/// Safehouse: build a safehouse to a checklist around the flag (SafehouseChecklistDEM), then refugees (friendly NPCs
/// from an NPC mod) wait just outside the trader's compound for the players to lead them there. Once they've all
/// moved in, the safehouse is attacked at the attack hour: a few waves, going for the refugees as well as the
/// players. Won if at least one refugee is alive at the end; the refugees stay and guard the safehouse. Lost if every
/// refugee dies, nobody is there when the attack comes, or everybody leaves during it. Kept in SafehouseRegistryDEM,
/// saved with the world, like an outpost.
/// </summary>
internal class SafehouseDefense : NpcDefense
{
    public enum Stages
    {
        Build,
        Fetch,
        Night,
        Attack,
    }

    private readonly SafehouseRegistryDEM.Safehouse house;
    private int checklist = -1;
    private float checkTimer;
    private float upkeepTimer;
    private int attackWave;
    private bool waveActive;
    private int warned = int.MaxValue;

    public SafehouseDefense(int questCode, DefenseSettingsDEM settings) : base(questCode, settings)
    {
        house = SafehouseRegistryDEM.Get(questCode);
        if (house.Refugees == 0)
        {
            house.Refugees = settings.Count;
            SafehouseRegistryDEM.Save();
        }
        foreach (SafehouseRegistryDEM.Refugee refugee in house.Members)
        {
            members.Add(new Member
            {
                Id = refugee.Id,
                ClassId = refugee.ClassId,
                Position = refugee.Position,
                Done = refugee.Settled,
                Led = refugee.Settled,
            });
        }
    }

    private Stages Stage
    {
        get => (Stages)house.Stage;
        set
        {
            house.Stage = (int)value;
            SaveHouse();
        }
    }

    public override void AddListener(int playerId)
    {
        Listeners.Add(playerId);
        World world = GameManager.Instance.World;
        if (house.Fallen || house.Won)
        {
            Won = house.Won;
            Failed = house.Fallen;
            SendStatus(null);
            return;
        }
        // Every refugee died while the party was away
        if (Stage != Stages.Build && house.Members.Count == 0 && house.Lost > 0)
        {
            Fall("SafehouseDEM_alllost");
            return;
        }
        // Nobody was there when the attack came
        if (Stage == Stages.Night && world.worldTime > house.NextAttack + WaveDirectorDEM.Hour / 4)
        {
            Fall("SafehouseDEM_missed");
            return;
        }
        SendStatus(Listeners.Count == 1 && Stage == Stages.Build ? "SafehouseDEM_start" : null, HoursUntilAttack(world));
    }

    private int HoursUntilAttack(World world)
    {
        return world.worldTime >= house.NextAttack ? 0 : (int)((house.NextAttack - world.worldTime + WaveDirectorDEM.Hour - 1) / WaveDirectorDEM.Hour);
    }

    public override void Abandon()
    {
        // Everyone left in the middle of the attack: the safehouse is lost
        if (Stage == Stages.Attack && !house.Fallen && !house.Won)
        {
            house.Fallen = true;
            SaveHouse();
        }
        // Refugees following someone wait where they are
        World world = GameManager.Instance.World;
        foreach (Member member in Active())
        {
            if (member.Leader != 0 && world != null && Npc(world, member) is EntityAlive npc)
            {
                NpcFollowDEM.Stay(npc, member.Leader);
                member.Leader = 0;
            }
        }
        SaveHouse();
        base.Abandon();
    }

    public override bool Tick(World world, float deltaTime)
    {
        if (house.Fallen || house.Won)
            return true;
        if (NobodyOnline(world))
        {
            Abandon();
            return true;
        }

        List<EntityPlayer> players = ListenerPlayers(world);
        GameRandom random = world.GetGameRandom();

        if (Stage != Stages.Build)
        {
            upkeepTimer -= deltaTime;
            if (upkeepTimer <= 0f)
            {
                upkeepTimer = 0.5f;
                if (UpkeepRefugees(world, players, random))
                    return true;
            }
        }

        switch (Stage)
        {
            case Stages.Build:
                return Build(world, deltaTime);
            case Stages.Fetch:
                Fetch(world, players, random);
                return false;
            case Stages.Night:
                return WaitForNight(world, players, deltaTime);
            default:
                return Attack(world, players, random, deltaTime);
        }
    }

    /// <summary>Checks the safehouse against its checklist every couple of seconds.</summary>
    private bool Build(World world, float deltaTime)
    {
        checkTimer -= deltaTime;
        if (checkTimer > 0f)
            return false;
        checkTimer = 2f;
        if (world.GetChunkFromWorldPos(new Vector3i(settings.Flag)) == null)
            return false;

        int found = SafehouseChecklistDEM.Scan(world, settings.Flag);
        if (SafehouseChecklistDEM.Passes(found, settings.Tier, house.Refugees))
        {
            checklist = found;
            Stage = Stages.Fetch;
            SendStatus("SafehouseDEM_ready");
            return false;
        }
        if (found != checklist)
        {
            checklist = found;
            SendStatus(null);
        }
        return false;
    }

    /// <summary>Refugees wait outside the trader's compound (spawned once a player is nearby) to be led home.</summary>
    private void Fetch(World world, List<EntityPlayer> players, GameRandom random)
    {
        if (members.Count == 0)
        {
            bool near = false;
            foreach (EntityPlayer player in players)
                near |= Flat(player.position, settings.Trader) <= 100f;
            if (!near || world.GetChunkFromWorldPos(new Vector3i(settings.Trader)) == null)
                return;
            if (!NpcCatalogDEM.HasFollowers)
            {
                Fall("NpcQuestDEM_nonpcs");
                return;
            }
            for (int i = 0; i < house.Refugees; i++)
            {
                var member = new Member { ClassId = NpcCatalogDEM.PickFollower(random) };
                if (Around(world, random, settings.Trader, 22f, 35f, out Vector3 spot) && SpawnMember(world, member, spot, random, true, true) != null)
                    members.Add(member);
            }
            if (members.Count > 0)
            {
                house.Refugees = members.Count;
                SaveHouse();
                SendStatus("SafehouseDEM_waiting");
            }
            return;
        }

        // Moving in: a refugee led to the safehouse stops following and settles in
        foreach (Member member in Active())
        {
            if (member.Leader == 0 || !(Npc(world, member) is EntityAlive npc) || Flat(npc.position, settings.Flag) > settings.Radius)
                continue;
            NpcFollowDEM.Stay(npc, member.Leader);
            Settle(npc);
            member.Leader = 0;
            member.Done = true;
            SaveHouse();
            SendStatus("SafehouseDEM_settled", Settled());
        }

        foreach (Member member in members)
        {
            if (!member.Done && !member.Lost)
                return;
        }
        // Everyone alive has moved in: the attack comes at the attack hour
        house.NextAttack = NextAttackAfter(world.worldTime);
        warned = int.MaxValue;
        Stage = Stages.Night;
        SendStatus("SafehouseDEM_movedin", HoursUntilAttack(world));
    }

    /// <summary>A refugee moves in for good: saved with the world, no longer one of the quest's passing NPCs.</summary>
    private void Settle(EntityAlive npc)
    {
        npc.Buffs.SetCustomVar("Persist", 1f);
        npc.Buffs.RemoveCustomVar(TagCvar);
        npc.Buffs.SetCustomVar(SettledCvar, Tag(QuestCode));
    }

    /// <summary>The first attack hour at or after the time.</summary>
    private ulong NextAttackAfter(ulong time)
    {
        int day = GameUtils.WorldTimeToDays(time);
        ulong attack = GameUtils.DayTimeToWorldTime(day, settings.AttackHour, 0);
        return attack >= time ? attack : GameUtils.DayTimeToWorldTime(day + 1, settings.AttackHour, 0);
    }

    private bool WaitForNight(World world, List<EntityPlayer> players, float deltaTime)
    {
        checkTimer -= deltaTime;
        if (checkTimer > 0f)
            return false;
        checkTimer = 1f;

        // Warnings 2 hours, 1 hour and 15 minutes before the attack
        ulong left = world.worldTime >= house.NextAttack ? 0 : house.NextAttack - world.worldTime;
        int warning = left <= WaveDirectorDEM.Hour / 4 ? 0 : left <= WaveDirectorDEM.Hour ? 1 : left <= 2 * WaveDirectorDEM.Hour ? 2 : int.MaxValue;
        if (warning < warned)
        {
            warned = warning;
            if (warning != int.MaxValue && left > 0)
                SendStatus(warning == 0 ? "SafehouseDEM_warning_soon" : "SafehouseDEM_warning", warning);
        }
        if (left > 0)
            return false;

        bool present = false;
        foreach (EntityPlayer player in players)
            present |= Flat(player.position, settings.Flag) <= settings.Radius + 20f;
        if (!present)
            return Fall("SafehouseDEM_absent");

        attackWave = 0;
        waveActive = false;
        timer = 0f;
        fighting = true;
        Stage = Stages.Attack;
        SendStatus("SafehouseDEM_attack");
        return false;
    }

    private bool Attack(World world, List<EntityPlayer> players, GameRandom random, float deltaTime)
    {
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

            // The night is held, if anyone made it
            fighting = false;
            house.Won = true;
            Won = true;
            SaveHouse();
            SendStatus("SafehouseDEM_complete");
            return true;
        }

        MarkStragglers(world);
        RetargetAtMembers(world, players, deltaTime);
        ReportAlive();
        return false;
    }

    private void StartWave(World world, List<EntityPlayer> players, GameRandom random)
    {
        int gameStage = Mathf.RoundToInt(GameStageDefinition.CalcGameStageAround(players[0]) * settings.Strength * (1f + 0.15f * attackWave));
        SpawnWaveZombies(world, players, random, gameStage, 1f + 0.2f * attackWave);
        if (zombies.Count == 0)
        {
            timer = 5f;
            return;
        }
        waveActive = true;
        timer = WaveDirectorDEM.WaveTimeLimit;
        StartCounting();
        SendStatus("OutpostDEM_wave", attackWave + 1);
    }

    /// <summary>Follows the refugees. Returns true if the safehouse fell (every refugee died).</summary>
    private bool UpkeepRefugees(World world, List<EntityPlayer> players, GameRandom random)
    {
        if (members.Count == 0)
            return false;
        TrackMembers(world, players, random, 0.5f, Stage == Stages.Fetch, true, 0f, null);
        TrackSettled(world, random);
        if (TakeNewlyLost() > 0)
        {
            SaveHouse();
            bool anyLeft = false;
            foreach (Member member in members)
                anyLeft |= !member.Lost;
            if (!anyLeft)
                return Fall("SafehouseDEM_alllost");
            SendStatus("SafehouseDEM_lost");
        }
        return false;
    }

    /// <summary>
    /// Refugees who moved in stay in the safehouse: one that died is lost; one that's gone while its spot is loaded
    /// comes back there.
    /// </summary>
    private void TrackSettled(World world, GameRandom random)
    {
        foreach (Member member in members)
        {
            if (!member.Done || member.Lost)
                continue;
            var npc = world.GetEntity(member.Id) as EntityAlive;
            if (npc != null)
            {
                if (npc.IsDead())
                    MarkLost(member);
                else
                {
                    member.Position = npc.position;
                    member.Missing = 0f;
                }
                continue;
            }
            if (world.GetChunkFromWorldPos(new Vector3i(member.Position)) == null)
                continue;
            member.Missing += 0.5f;
            if (member.Missing >= 5f && SpawnMember(world, member, member.Position, random, true, false) is EntityAlive back)
            {
                back.Buffs.RemoveBuff(WaitingBuff);
                Settle(back);
            }
        }
    }

    protected override void OnLost(Member member)
    {
        house.Lost++;
    }

    private bool Fall(string messageKey)
    {
        house.Fallen = true;
        Failed = true;
        // When it ended, so the record is kept for 30 days from now (one that fell before the attack was set has none)
        if (house.NextAttack == 0)
            house.NextAttack = GameManager.Instance.World?.worldTime ?? 0;
        SaveHouse();
        RemoveZombies();
        fighting = false;
        SendStatus(messageKey);
        return true;
    }

    private void SaveHouse()
    {
        house.Members.Clear();
        foreach (Member member in members)
        {
            if (member.Lost)
                continue;
            house.Members.Add(new SafehouseRegistryDEM.Refugee
            {
                Id = member.Id,
                ClassId = member.ClassId,
                Position = member.Position,
                Settled = member.Done,
            });
        }
        SafehouseRegistryDEM.Save();
    }

    private int Settled()
    {
        int settled = 0;
        foreach (Member member in members)
        {
            if (member.Done && !member.Lost)
                settled++;
        }
        return settled;
    }

    protected override DefenseStatusDEM Status(string messageKey, int messageValue)
    {
        DefenseStatusDEM status = base.Status(messageKey, messageValue);
        status.Waves = house.Refugees;
        status.WavesDone = Settled();
        status.Lost = house.Lost;
        status.Stage = house.Stage;
        status.Checklist = Mathf.Max(0, checklist);
        status.NextTime = house.NextAttack;
        status.Fighting = Stage == Stages.Attack;
        status.Result = house.Fallen ? DefenseStatusDEM.Results.Lost : house.Won ? DefenseStatusDEM.Results.Won : DefenseStatusDEM.Results.None;
        return status;
    }
}
