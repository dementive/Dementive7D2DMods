using UnityEngine;

/// <summary>
/// The flags handed out by build quests (blocks with Class "QuestFlagDEM, QuestsExpanded": the White River flag of
/// Build and Defend and Last Stand, the Duke's banner of Create Outpost). Planting one completes the placing
/// player's PlaceFlagDEM objective for that flag, and the party's copies of that quest too.
/// </summary>
public class BlockQuestFlagDEM : Block
{
    public override void PlaceBlock(WorldBase _world, BlockPlacement.Result _result, EntityAlive _ea)
    {
        base.PlaceBlock(_world, _result, _ea);

        // Placing runs in the item action of the player holding the flag, so this is their client
        if (_ea is EntityPlayerLocal player)
            FlagPlaced(player, GetBlockName(), _result.blockPos.ToVector3());
    }

    public static void FlagPlaced(EntityPlayerLocal player, string blockName, Vector3 position)
    {
        bool waiting = false;
        bool placed = false;
        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (quest.CurrentState != Quest.QuestState.InProgress)
                continue;

            foreach (BaseObjective objective in quest.Objectives)
            {
                if (!(objective is ObjectivePlaceFlagDEM flag) || flag.Phase != quest.CurrentPhase || flag.Complete
                    || flag.Block != blockName)
                    continue;

                waiting = true;
                if (!flag.TryPlace(blockName, position, true))
                    continue;

                placed = true;
                if (player.Party == null)
                    continue;

                NetPackageQuestFlagDEM package = NetPackageManager.GetPackage<NetPackageQuestFlagDEM>()
                    .Setup(player.entityId, quest.QuestCode, blockName, position);
                if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
                    package.Relay(GameManager.Instance.World);
                else
                    SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(package);
            }
        }

        if (waiting && !placed)
            GameManager.ShowTooltip(player, Localization.Get("PlaceFlagDEM_too_far"));
    }
}
