using UnityEngine;

/*
 * Plant a flag from the quest's kit (a block with Class "QuestFlagDEM, QuestsExpanded") near the quest's location,
 * or inside its POI. Its position is kept in the quest's Activate position data, for the objectives that defend it.
 * Planting it completes the objective for every party member with the shared quest. The flag only comes in the
 * quest's kit, so while the objective waits a lost one (dropped on death, stolen, sold) is replaced.
 * 	<objective type="PlaceFlagDEM, QuestsExpanded">
 * 		<property name="phase" value="2"/>
 * 		<property name="block" value="questFlagDEM"/>   which flag counts
 * 		<property name="max_distance" value="40"/>      how far from the quest's location the flag can go
 * 		<property name="inside_poi" value="true"/>      the flag has to go inside the quest's POI instead
 * 		<property name="keyword" value="SafehouseDEM_flag_keyword"/>   the objective's text, if not the default
 * 	</objective>
 */
public class ObjectivePlaceFlagDEM : BaseObjective
{
    public string Block = "questFlagDEM";

    public float MaxDistance = 40f;

    public bool InsidePOI;

    public string KeywordKey = "";

    /// <summary>Seconds between checks that the player still has a flag.</summary>
    public const float FlagCheckSeconds = 5f;

    private float flagCheckTimer;

    public override bool useUpdateLoop => true;

    public override ObjectiveValueTypes ObjectiveValueType => ObjectiveValueTypes.Boolean;

    public override void SetupObjective()
    {
        keyword = Localization.Get(KeywordKey != "" ? KeywordKey : InsidePOI ? "PlaceFlagDEM_keyword_poi" : "PlaceFlagDEM_keyword");
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    public override void AddHooks()
    {
        base.AddHooks();
        // The first check waits a moment: on login the quest is hooked before the player's inventory is ready
        flagCheckTimer = 2f;
    }

    public override void Update(float deltaTime)
    {
        if (Complete)
            return;
        flagCheckTimer -= deltaTime;
        if (flagCheckTimer > 0f)
            return;
        flagCheckTimer = FlagCheckSeconds;
        ReplaceLostFlag();
    }

    /// <summary>
    /// Gives the player a flag if they have none in their backpack or toolbelt. This runs on the game of the player
    /// whose journal the quest is in; party members with a shared copy get one the same way if they lost theirs, and
    /// a spare flag does no harm.
    /// </summary>
    private void ReplaceLostFlag()
    {
        EntityPlayerLocal player = OwnerQuest?.OwnerJournal?.OwnerPlayer;
        if (player == null || player.IsDead() || !player.IsSpawned()
            || OwnerQuest.CurrentState != Quest.QuestState.InProgress || OwnerQuest.CurrentPhase != Phase)
            return;

        ItemValue flag = ItemClass.GetItem(Block);
        if (flag == null || flag.type == ItemValue.None.type)
            return;
        if (player.bag.GetItemCount(flag) + player.inventory.GetItemCount(flag) > 0)
            return;
        if (LocalPlayerUI.GetUIForPlayer(player)?.xui?.PlayerInventory == null)
            return;

        RewardUtilsDEM.GiveItem(player, new ItemStack(flag, 1));
        GameManager.ShowTooltip(player, Localization.Get("PlaceFlagDEM_replaced"));
    }

    /// <summary>
    /// The flag was planted at the position. Returns false if it's the wrong flag or in the wrong place.
    /// </summary>
    public bool TryPlace(string blockName, Vector3 position, bool checkPosition)
    {
        if (Complete || blockName != Block)
            return false;

        if (checkPosition && !InPlace(position))
            return false;

        OwnerQuest.SetPositionData(Quest.PositionDataTypes.Activate, position);
        CurrentValue = 1;
        Refresh();
        return true;
    }

    private bool InPlace(Vector3 position)
    {
        if (InsidePOI)
        {
            if (!OwnerQuest.GetPositionData(out Vector3 poiPosition, Quest.PositionDataTypes.POIPosition))
                return true;
            OwnerQuest.GetPositionData(out Vector3 poiSize, Quest.PositionDataTypes.POISize);
            return position.x >= poiPosition.x && position.x <= poiPosition.x + poiSize.x
                && position.z >= poiPosition.z && position.z <= poiPosition.z + poiSize.z;
        }

        if (!OwnerQuest.GetPositionData(out Vector3 location, Quest.PositionDataTypes.Location))
            return true;
        return new Vector2(position.x - location.x, position.z - location.z).magnitude <= MaxDistance;
    }

    public override void Refresh()
    {
        if (Complete)
            return;

        Complete = CurrentValue >= 1 && OwnerQuest.CheckRequirements();
        if (Complete)
            OwnerQuest.RefreshQuestCompletion();
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseString("block", ref Block);
        properties.ParseFloat("max_distance", ref MaxDistance);
        properties.ParseBool("inside_poi", ref InsidePOI);
        properties.ParseString("keyword", ref KeywordKey);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("max_distance", MaxDistance);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectivePlaceFlagDEM();
        CopyValues(objective);
        objective.Block = Block;
        objective.MaxDistance = MaxDistance;
        objective.InsidePOI = InsidePOI;
        objective.KeywordKey = KeywordKey;
        return objective;
    }
}
