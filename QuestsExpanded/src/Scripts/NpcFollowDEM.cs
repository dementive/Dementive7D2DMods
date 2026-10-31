using System;
using System.Reflection;

/// <summary>
/// SCore's follow and hire system, reached by name so QuestsExpanded loads without SCore. Following is SCore's own
/// EntityUtilities.SetLeader (the call its hiring makes): the NPC's "Leader" cvar, the player's "hired_&lt;id&gt;" cvar and
/// the buffOrderFollow buff. Stopping is what SCore's own Dismiss order does to those cvars. Server side.
/// </summary>
public static class NpcFollowDEM
{
    public const string StayBuff = "buffOrderStay";

    private static bool looked;
    private static MethodInfo setLeader;
    private static MethodInfo setLeaderAndOwner;

    public static bool Available
    {
        get
        {
            Find();
            return setLeader != null;
        }
    }

    private static void Find()
    {
        if (looked)
            return;
        looked = true;
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.GetName().Name != "SCore")
                continue;
            Type utilities = assembly.GetType("EntityUtilities");
            setLeader = utilities?.GetMethod("SetLeader", BindingFlags.Public | BindingFlags.Static, null,
                new[] { typeof(int), typeof(int), typeof(bool) }, null);
            setLeaderAndOwner = utilities?.GetMethod("SetLeaderAndOwner", BindingFlags.Public | BindingFlags.Static, null,
                new[] { typeof(int), typeof(int), typeof(bool) }, null);
            return;
        }
    }

    /// <summary>The NPC follows the player (not hired: it leaves when the quest is done with it).</summary>
    public static bool Follow(EntityAlive npc, EntityPlayer player)
    {
        if (!Available || npc == null || player == null)
            return false;
        try
        {
            setLeader.Invoke(null, new object[] { npc.entityId, player.entityId, true });
            return true;
        }
        catch (Exception e)
        {
            Log.Warning($"QuestsExpanded: couldn't make {npc.EntityName} follow {player.EntityName}: {e.InnerException?.Message ?? e.Message}");
            return false;
        }
    }

    /// <summary>The NPC joins the player for good, as if hired.</summary>
    public static bool Hire(EntityAlive npc, EntityPlayer player)
    {
        Find();
        if (setLeaderAndOwner == null || npc == null || player == null)
            return false;
        try
        {
            setLeaderAndOwner.Invoke(null, new object[] { npc.entityId, player.entityId, true });
            return true;
        }
        catch (Exception e)
        {
            Log.Warning($"QuestsExpanded: couldn't hire {npc.EntityName} for {player.EntityName}: {e.InnerException?.Message ?? e.Message}");
            return false;
        }
    }

    /// <summary>
    /// The NPC stops following and waits where it is (its leader died or left, or it reached where it was going).
    /// </summary>
    public static void Stay(EntityAlive npc, int leaderId)
    {
        if (npc == null)
            return;
        Release(npc, leaderId);
        npc.Buffs.AddBuff(StayBuff);
    }

    /// <summary>Unlinks the NPC from the player it was following, like SCore's Dismiss order.</summary>
    public static void Release(EntityAlive npc, int leaderId)
    {
        if (npc == null)
            return;
        npc.Buffs.RemoveCustomVar("Leader");
        if (GameManager.Instance.World?.GetEntity(leaderId) is EntityPlayer player)
        {
            player.Buffs.SetCustomVar($"hired_{npc.entityId}", 0f);
            player.Companions?.Remove(npc);
        }
    }

    /// <summary>The player the NPC follows, or 0.</summary>
    public static int Leader(EntityAlive npc)
    {
        return npc != null && npc.Buffs.HasCustomVar("Leader") ? (int)npc.Buffs.GetCustomVar("Leader") : 0;
    }
}
