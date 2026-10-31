using System.Collections.Generic;
using UnityEngine;

/*
 * A Rescue reward pick: one of the survivors you saved joins you as a hired NPC (SCore's hire, with all of the NPC
 * mod's orders). Each player sharing the quest can take one; when the party has taken every survivor saved, the pick
 * pays the dukes in its value instead.
 * 	<reward type="RescueJoinDEM, QuestsExpanded" ischosen="true" value="500"/>   dukes if nobody is left to join
 */
public class RewardRescueJoinDEM : BaseReward
{
    public int Dukes;

    public override void SetupReward()
    {
        Description = Localization.Get("RewardRescueJoinDEM_keyword");
        Icon = "ui_game_symbol_players";
        int.TryParse((Value ?? "").Trim(), out Dukes);
        ValueText = string.Format(Localization.Get("RewardRescueJoinDEM_value"), Dukes);
    }

    public override string GetRewardText()
    {
        return $"{Description} {ValueText}";
    }

    public override void GiveReward(EntityPlayer player)
    {
        if (OwnerQuest == null || player == null)
            return;
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            if (!RescueJoinPoolDEM.Join(OwnerQuest.QuestCode, player))
                RewardUtilsDEM.GiveDukes(player as EntityPlayerLocal, Dukes);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageRescueJoinDEM>().SetupRequest(OwnerQuest.QuestCode, Dukes));
        }
    }

    public override BaseReward Clone()
    {
        var reward = new RewardRescueJoinDEM();
        CopyValues(reward);
        reward.Dukes = Dukes;
        return reward;
    }
}

/// <summary>
/// Server side: the survivors each finished Rescue saved, by quest code, for the players who pick "a survivor joins
/// you". Remembered for 2 hours, first come first served.
/// </summary>
public static class RescueJoinPoolDEM
{
    private const float RememberSeconds = 7200f;

    private class Pool
    {
        public float Time;
        public readonly List<int> Classes = new List<int>();
    }

    private static readonly Dictionary<int, Pool> pools = new Dictionary<int, Pool>();

    public static void Add(int questCode, List<int> classes)
    {
        var pool = new Pool { Time = Time.time };
        pool.Classes.AddRange(classes);
        pools[questCode] = pool;
    }

    /// <summary>
    /// One of the quest's saved survivors joins the player, next to them. False if there's nobody left to join.
    /// </summary>
    public static bool Join(int questCode, EntityPlayer player)
    {
        World world = GameManager.Instance.World;
        if (world == null || !pools.TryGetValue(questCode, out Pool pool) || Time.time - pool.Time > RememberSeconds)
            return false;

        GameRandom random = world.GetGameRandom();
        while (pool.Classes.Count > 0)
        {
            int classId = pool.Classes[0];
            pool.Classes.RemoveAt(0);
            Vector3 position = player.position + Quaternion.Euler(0f, random.RandomFloat * 360f, 0f) * Vector3.forward * 2f;
            if (!(EntityFactory.CreateEntity(classId, position, new Vector3(0f, player.rotation.y + 180f, 0f)) is EntityAlive npc))
                continue;
            npc.SetSpawnerSource(EnumSpawnerSource.StaticSpawner);
            world.SpawnEntityInWorld(npc);
            if (NpcFollowDEM.Hire(npc, player))
                return true;
            world.RemoveEntity(npc.entityId, EnumRemoveEntityReason.Despawned);
        }
        return false;
    }
}
