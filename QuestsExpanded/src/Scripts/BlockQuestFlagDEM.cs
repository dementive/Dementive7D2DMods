using UnityEngine;

/// <summary>
/// The White River flag handed out by build quests (block questFlagDEM, Class "QuestFlagDEM, QuestsExpanded").
/// Planting it completes the placing player's PlaceFlagDEM objective, and the party's copies of that quest too.
/// </summary>
public class BlockQuestFlagDEM : Block
{
    public override void PlaceBlock(WorldBase _world, BlockPlacement.Result _result, EntityAlive _ea)
    {
        base.PlaceBlock(_world, _result, _ea);

        // Placing runs in the item action of the player holding the flag, so this is their client
        if (_ea is EntityPlayerLocal player)
            FlagPlaced(player, _result.blockPos.ToVector3());
    }

    public static void FlagPlaced(EntityPlayerLocal player, Vector3 position)
    {
        bool waiting = false;
        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (quest.CurrentState != Quest.QuestState.InProgress)
                continue;

            foreach (BaseObjective objective in quest.Objectives)
            {
                if (!(objective is ObjectivePlaceFlagDEM flag) || flag.Phase != quest.CurrentPhase || flag.Complete)
                    continue;

                waiting = true;
                if (!flag.TryPlace(position, true))
                    continue;

                if (player.Party == null)
                    continue;

                NetPackageQuestFlagDEM package = NetPackageManager.GetPackage<NetPackageQuestFlagDEM>()
                    .Setup(player.entityId, quest.QuestCode, position);
                if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
                    package.Relay(GameManager.Instance.World);
                else
                    SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(package);
            }
        }

        if (waiting && !Placed(player))
            GameManager.ShowTooltip(player, Localization.Get("PlaceFlagDEM_too_far"));
    }

    private static bool Placed(EntityPlayerLocal player)
    {
        foreach (Quest quest in player.QuestJournal.quests)
        {
            foreach (BaseObjective objective in quest.Objectives)
            {
                if (objective is ObjectivePlaceFlagDEM flag && flag.Phase == quest.CurrentPhase && !flag.Complete
                    && quest.CurrentState == Quest.QuestState.InProgress)
                    return false;
            }
        }
        return true;
    }
}
