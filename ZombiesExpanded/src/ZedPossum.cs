using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The Possum plays dead. Once, a hit that would kill it, or take it below a third of its health, drops it as if
/// dead instead, on a quarter of its health. It lies in one of the game's sleeper poses (silent, eyes dark) until a
/// player comes within 2.5 m, or turns their back on it within 8 m, after it has lain still for 5 s; then it gets up
/// and lunges at them. One in four Possums that spawn in the open start out lying "dead". A hit while it lies there
/// gets it up too (or kills it); a bleeding or burning tick doesn't.
///
/// The hit rule runs on every game from the same hit (ZedCombat), so everyone sees it drop; lying down happens a
/// moment later on every game; the server decides when it gets up and its profile tells everyone (the game's own
/// wake-ups are held back while it lies there, see ZedPossumWakePatch).
/// A sleeping zombie never despawns in the game, so one lying in the open with nobody near goes the way spawns that
/// wander off do.
/// </summary>
public static class ZedPossum
{
    private class Lying
    {
        public float Since;
        public bool Posed;
        public float AloneSince = -1f;
    }

    /// <summary>The sleeper senses and pose it had before it lay down (a POI sleeper goes back to its own).</summary>
    private struct Senses
    {
        public float NoiseToSense, NoiseToWake, SightRange;
        public int LastPose;
    }

    private static readonly Dictionary<int, Lying> lying = new Dictionary<int, Lying>();
    private static readonly Dictionary<int, Senses> senses = new Dictionary<int, Senses>();
    private static readonly Dictionary<int, float> spawnCheck = new Dictionary<int, float>();
    private static float tick;
    private static bool waking;

    /// <summary>Every game, from ZedCombat: whether this hit makes it fake its death, with the hit changed to suit
    /// (it keeps a quarter of its health and falls flat).</summary>
    public static bool FakeDeath(EntityAlive z, ZedProfile p, ref DamageResponse dr)
    {
        if (!p.Has(ZedMutation.Possum) || p.FakedDeath || p.PlayingDead || dr.Strength <= 0)
        {
            return false;
        }
        if (dr.Dismember && (dr.HitBodyPart & EnumBodyPartHit.Head) != 0)
        {
            return false;
        }
        int max = z.GetMaxHealth();
        if (!dr.Fatal && z.Health - dr.Strength >= max / 3)
        {
            return false;
        }
        int keep = Mathf.Max(1, Mathf.RoundToInt(max * 0.25f));
        dr.Strength = Mathf.Max(0, z.Health - keep);
        dr.Fatal = false;
        dr.Dismember = false;
        // No knockdown: its end would stand the zombie up out of the pose
        dr.Stun = EnumEntityStunType.None;
        dr.StunDuration = 0f;
        p.FakedDeath = true;
        p.PlayingDead = true;
        p.DeadPose = (byte)(1 + Mathf.Min(3, (int)(dr.Random * 4f)));
        LieDown(z, 0.15f);
        if (ZedStore.IsServer)
        {
            // Goes out after the hit (ZedStore.Changed), so players who missed it are told
            ZedStore.Changed(z);
        }
        return true;
    }

    /// <summary>Every game, from ZedCombat: a hit on it while it lies there (not the hit that dropped it, and not a
    /// bleeding or burning tick) gets it up. The server stands it up at whoever hit it; a player's game lets the game's
    /// own wake-up from that hit through, as the server does.</summary>
    public static void Hit(EntityAlive z, ZedProfile p, EntityAlive attacker)
    {
        if (p.PlayingDead && lying.TryGetValue(z.entityId, out Lying l) && l.Posed)
        {
            lying.Remove(z.entityId);
            if (ZedStore.IsServer)
            {
                GetUp(z, p, attacker as EntityPlayer ?? Nearest(z));
            }
        }
    }

    /// <summary>Whether the game may wake this zombie. The game wakes a sleeper on every hit, damage-over-time ticks
    /// included, and from a few other places (a fall, a target task starting): a Possum lying "dead" stays down until
    /// ZedPossum gets it up.</summary>
    public static bool MayWake(EntityAlive z)
    {
        return waking || !lying.TryGetValue(z.entityId, out Lying l) || !l.Posed;
    }

    private static void Wake(EntityAlive z)
    {
        waking = true;
        try
        {
            z.ConditionalTriggerSleeperWakeUp();
        }
        finally
        {
            waking = false;
        }
    }

    /// <summary>Every game: it lies down in a moment (after the fall).</summary>
    public static void LieDown(EntityAlive z, float delay)
    {
        lying[z.entityId] = new Lying { Since = Time.time + delay };
    }

    /// <summary>Server: a Possum entered the world. One already playing dead (asked for, or saved that way) lies down;
    /// a new one may be set to lie "dead" in the open once the game has said whether it's a POI sleeper.</summary>
    public static void Spawned(EntityAlive z, ZedProfile p, bool fresh)
    {
        if (!p.Has(ZedMutation.Possum))
        {
            return;
        }
        if (p.PlayingDead)
        {
            LieDown(z, 0.5f);
        }
        else if (fresh && !p.FakedDeath)
        {
            spawnCheck[z.entityId] = Time.time + 1.5f;
        }
    }

    /// <summary>A player's game, a profile arrived: lie down if it's playing dead and isn't yet; get up if the
    /// server says it's up and this game still has it lying (waking locally sends nothing).</summary>
    public static void Received(EntityAlive z, ZedProfile p)
    {
        if (p.PlayingDead && !lying.ContainsKey(z.entityId))
        {
            if (z.IsSleeping)
            {
                // Already lying there (this game started tracking it late): only the server gets it up
                lying[z.entityId] = new Lying { Since = Time.time, Posed = true };
            }
            else
            {
                LieDown(z, 0.2f);
            }
        }
        else if (!p.PlayingDead)
        {
            lying.Remove(z.entityId);
            if (p.Has(ZedMutation.Possum) && z.IsSleeping && !ZedStore.IsServer)
            {
                z.ConditionalTriggerSleeperWakeUp();
            }
        }
    }

    public static void Forget(int entityId)
    {
        lying.Remove(entityId);
        spawnCheck.Remove(entityId);
        senses.Remove(entityId);
    }

    public static void Clear()
    {
        lying.Clear();
        spawnCheck.Clear();
        senses.Clear();
    }

    /// <summary>Every game update: lying down when it's time; on the server, whether it gets up.</summary>
    public static void Update()
    {
        World world = GameManager.Instance.World;
        if (world == null || (lying.Count == 0 && spawnCheck.Count == 0))
        {
            return;
        }
        float now = Time.time;
        tick -= Time.deltaTime;
        bool check = tick <= 0f;
        if (check)
        {
            tick = 0.25f;
        }
        List<int> gone = null;
        foreach (KeyValuePair<int, Lying> kv in lying)
        {
            EntityAlive z = world.GetEntity(kv.Key) as EntityAlive;
            ZedProfile p = ZedStore.Get(kv.Key);
            if (z == null || z.IsDead() || p == null || !p.PlayingDead)
            {
                (gone ??= new List<int>()).Add(kv.Key);
                continue;
            }
            Lying l = kv.Value;
            if (!l.Posed)
            {
                if (now >= l.Since)
                {
                    Pose(z, p);
                    l.Posed = true;
                    l.Since = now;
                }
                continue;
            }
            if (check && ZedStore.IsServer)
            {
                if (!z.IsSleeping)
                {
                    // Something woke it (the game wakes a sleeper that's hit): it's up
                    GetUp(z, p, Nearest(z));
                    (gone ??= new List<int>()).Add(kv.Key);
                }
                else if (now - l.Since >= 5f && Triggered(z, out EntityPlayer by))
                {
                    GetUp(z, p, by);
                    (gone ??= new List<int>()).Add(kv.Key);
                }
                else if (Alone(z, now, l))
                {
                    (gone ??= new List<int>()).Add(kv.Key);
                    z.Despawn();
                }
            }
        }
        if (gone != null)
        {
            foreach (int id in gone)
            {
                lying.Remove(id);
            }
        }
        if (check && ZedStore.IsServer && spawnCheck.Count > 0)
        {
            SpawnChecks(world, now);
        }
    }

    private static void SpawnChecks(World world, float now)
    {
        List<int> done = null;
        foreach (KeyValuePair<int, float> kv in spawnCheck)
        {
            if (now < kv.Value)
            {
                continue;
            }
            (done ??= new List<int>()).Add(kv.Key);
            EntityAlive z = world.GetEntity(kv.Key) as EntityAlive;
            ZedProfile p = ZedStore.Get(kv.Key);
            if (z == null || z.IsDead() || p == null || z.IsSleeper || z.GetAttackTarget() != null || !Outdoors(z)
                || Random.value >= 0.25f)
            {
                continue;
            }
            p.PlayingDead = true;
            p.FakedDeath = true;
            p.DeadPose = (byte)Random.Range(1, 5);
            LieDown(z, 0f);
            ZedStore.Changed(z);
        }
        if (done != null)
        {
            foreach (int id in done)
            {
                spawnCheck.Remove(id);
            }
        }
    }

    /// <summary>A wandering or biome spawn with no player within 80 m for 90 s: time it went.</summary>
    private static bool Alone(EntityAlive z, float now, Lying l)
    {
        EnumSpawnerSource source = z.GetSpawnerSource();
        if (source != EnumSpawnerSource.Dynamic && source != EnumSpawnerSource.Biome)
        {
            return false;
        }
        foreach (EntityPlayer player in z.world.Players.list)
        {
            if ((player.position - z.position).sqrMagnitude < 80f * 80f)
            {
                l.AloneSince = -1f;
                return false;
            }
        }
        if (l.AloneSince < 0f)
        {
            l.AloneSince = now;
        }
        return now - l.AloneSince > 90f;
    }

    private static bool Outdoors(EntityAlive z)
    {
        Vector3 top = z.getHeadPosition() + Vector3.up * 0.6f;
        return !Voxel.Raycast(z.world, new Ray(top, Vector3.up), 40f, false, false);
    }

    /// <summary>Every game: into the sleeper pose. On the server it also stops what it was doing and stops sensing
    /// (only ZedPossum gets it up, not the game's sleeper hearing or sight).</summary>
    private static void Pose(EntityAlive z, ZedProfile p)
    {
        if (!z.IsSleeping)
        {
            z.TriggerSleeperPose(p.DeadPose, false);
        }
        if (ZedStore.IsServer)
        {
            if (!senses.ContainsKey(z.entityId))
            {
                senses[z.entityId] = new Senses
                {
                    NoiseToSense = z.sleeperNoiseToSense, NoiseToWake = z.sleeperNoiseToWake, SightRange = z.sleeperSightRange,
                    LastPose = z.lastSleeperPose,
                };
            }
            z.SetAttackTarget(null, 0);
            z.SetRevengeTarget(null);
            z.navigator?.clearPath();
            z.moveHelper?.Stop();
            z.sleeperNoiseToSense = 1e6f;
            z.sleeperNoiseToWake = 1e6f;
            z.sleeperSightRange = 0f;
        }
    }

    /// <summary>A living player within 2.5 m, or within 8 m with their back to it.</summary>
    private static bool Triggered(EntityAlive z, out EntityPlayer by)
    {
        by = null;
        foreach (EntityPlayer player in z.world.Players.list)
        {
            if (player.IsDead())
            {
                continue;
            }
            Vector3 to = z.position - player.position;
            if (Mathf.Abs(to.y) > 2f)
            {
                // Another floor
                continue;
            }
            to.y = 0f;
            float d = to.magnitude;
            if (d < 2.5f)
            {
                by = player;
                return true;
            }
            if (d < 8f)
            {
                Vector3 look = player.GetLookVector();
                look.y = 0f;
                if (Vector3.Dot(look.normalized, to / Mathf.Max(d, 0.01f)) < -0.2f)
                {
                    by = player;
                    return true;
                }
            }
        }
        return false;
    }

    private static EntityPlayer Nearest(EntityAlive z)
    {
        EntityPlayer best = null;
        float bestD = 40f * 40f;
        foreach (EntityPlayer player in z.world.Players.list)
        {
            float d = (player.position - z.position).sqrMagnitude;
            if (!player.IsDead() && d < bestD)
            {
                best = player;
                bestD = d;
            }
        }
        return best;
    }

    /// <summary>Server: it gets up (the game's sleeper wake-up, which every player sees) and lunges at `at`.</summary>
    private static void GetUp(EntityAlive z, ZedProfile p, EntityPlayer at)
    {
        p.PlayingDead = false;
        Wake(z);
        if (senses.TryGetValue(z.entityId, out Senses s))
        {
            senses.Remove(z.entityId);
            z.sleeperNoiseToSense = s.NoiseToSense;
            z.sleeperNoiseToWake = s.NoiseToWake;
            z.sleeperSightRange = s.SightRange;
            z.lastSleeperPose = s.LastPose;
        }
        if (at != null)
        {
            z.SetAttackTarget(at, 1200);
            (z as EntityHuman)?.StartRage(1.5f, 4f);
        }
        ZedBrain.Of(z)?.Lunge();
        ZedStore.Changed(z);
    }
}

/// <summary>The game's sleeper wake-up, on every game: not for a Possum lying "dead" unless ZedPossum is getting it
/// up (or this game was told it's up).</summary>
[HarmonyLib.HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ConditionalTriggerSleeperWakeUp))]
public class ZedPossumWakePatch
{
    public static bool Prefix(EntityAlive __instance)
    {
        return ZedPossum.MayWake(__instance);
    }
}
