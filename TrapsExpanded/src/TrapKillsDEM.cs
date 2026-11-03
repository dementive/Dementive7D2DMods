using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Server: works out which trap (or player) killed each zombie. A trap's own hits run inside Begin/End, so a kill
/// during one is the trap's. Statuses and fire a trap set mark the zombie (Touch), so a burn or fall that kills it
/// shortly after counts too, unless a player's weapon landed the killing blow. Vanilla turrets and blade traps are
/// tracked the same way through their own code (TrapPatchesDEM). Kills level the trap up, feed the Salvage Hoppers
/// near the body and go into the Blood Moon report.
/// </summary>
public static class TrapKillsDEM
{
    /// <summary>A kill this long after a trap's status counts for the trap; fire burns longer.</summary>
    private const float TouchWindow = 3f;
    private const float FireWindow = 16f;

    private struct Context
    {
        public Vector3i Pos;
        public string Name;
        public bool Fire;
        public bool Vanilla;
    }

    private class Mark
    {
        public Vector3i Pos;
        public string Name;
        public bool Fire;
        public float Time;
    }

    private static readonly Stack<Context> current = new Stack<Context>();
    private static readonly Dictionary<int, Mark> touched = new Dictionary<int, Mark>();
    private static readonly Dictionary<int, float> credited = new Dictionary<int, float>();
    private static float pruneAt;

    /// <summary>Server: a trap is about to hit something (pair with End).</summary>
    public static void Begin(Vector3i pos, string name, bool fire, bool vanilla = false)
    {
        current.Push(new Context { Pos = pos, Name = name, Fire = fire, Vanilla = vanilla });
    }

    public static void End()
    {
        if (current.Count > 0)
        {
            current.Pop();
        }
    }

    /// <summary>The vanilla trap whose code is running right now, if any (its level raises its damage).</summary>
    public static bool InVanillaTrap(out Vector3i pos)
    {
        if (current.Count > 0 && current.Peek().Vanilla)
        {
            pos = current.Peek().Pos;
            return true;
        }
        pos = Vector3i.zero;
        return false;
    }

    public static void Touch(EntityAlive e, Vector3i pos, string name, bool fire)
    {
        if (e == null || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        if (!touched.TryGetValue(e.entityId, out Mark m))
        {
            m = new Mark();
            touched[e.entityId] = m;
        }
        // Fire keeps its claim against a later non-fire touch while it's burning
        if (m.Fire && !fire && Time.time - m.Time < FireWindow && m.Name != null)
        {
            return;
        }
        m.Pos = pos;
        m.Name = name;
        m.Fire = fire;
        m.Time = Time.time;
    }

    /// <summary>Server, from EntityAlive.ClientKill: who gets the kill.</summary>
    public static void Killed(EntityAlive victim, DamageResponse response)
    {
        if (!(victim is EntityEnemy) || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        Prune();
        if (credited.ContainsKey(victim.entityId))
        {
            return;
        }
        credited[victim.entityId] = Time.time;

        if (current.Count > 0)
        {
            Context c = current.Peek();
            Credit(victim, c.Pos, c.Name);
            return;
        }
        DamageSource source = response.Source;
        bool weapon = source != null && source.AttackingItem != null && !source.AttackingItem.IsEmpty();
        if (!weapon && touched.TryGetValue(victim.entityId, out Mark m) && m.Name != null)
        {
            float age = Time.time - m.Time;
            if ((age <= TouchWindow || (m.Fire && age <= FireWindow)) && Credit(victim, m.Pos, m.Name))
            {
                return;
            }
        }
        int killer = source != null ? source.getEntityId() : -1;
        if (killer != -1 && GameManager.Instance.World.GetEntity(killer) is EntityPlayer player)
        {
            BloodMoonDEM.PlayerKill(player);
        }
    }

    /// <summary>The kill goes to the trap at pos, if it's still there: a trap picked up (or swapped for another)
    /// since it touched the zombie gets nothing, since crediting it would replace the record of whatever stands there
    /// now. Returns whether it was credited.</summary>
    private static bool Credit(EntityAlive victim, Vector3i pos, string name)
    {
        World world = GameManager.Instance.World;
        if (world == null || world.GetBlock(pos).Block?.GetBlockName() != name)
        {
            return false;
        }
        TrapStoreDEM.AddKill(pos, name);
        BloodMoonDEM.TrapKill(pos, name);
        if (world.GetBlock(pos).Block is BlockTrapDEM)
        {
            OverchargerControllerDEM.ShareKill(world, pos);
        }
        SalvageHopperControllerDEM.TrapKill(world, victim);
        return true;
    }

    private static void Prune()
    {
        if (Time.time < pruneAt)
        {
            return;
        }
        pruneAt = Time.time + 30f;
        List<int> old = new List<int>();
        foreach (KeyValuePair<int, Mark> kv in touched)
        {
            if (Time.time - kv.Value.Time > 60f)
            {
                old.Add(kv.Key);
            }
        }
        foreach (int id in old)
        {
            touched.Remove(id);
        }
        old.Clear();
        foreach (KeyValuePair<int, float> kv in credited)
        {
            if (Time.time - kv.Value > 60f)
            {
                old.Add(kv.Key);
            }
        }
        foreach (int id in old)
        {
            credited.Remove(id);
        }
    }

    public static void Clear()
    {
        current.Clear();
        touched.Clear();
        credited.Clear();
    }
}
