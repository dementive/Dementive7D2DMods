using UnityEngine;

/*
 * Plant the White River flag from the quest's kit (block questFlagDEM) near the quest's location. Its position is
 * kept in the quest's Activate position data, for a DefendWavesDEM with center "flag". Planting it completes the
 * objective for every party member with the shared quest.
 * 	<objective type="PlaceFlagDEM, QuestsExpanded">
 * 		<property name="phase" value="2"/>
 * 		<property name="max_distance" value="40"/>   how far from the quest's location the flag can go
 * 	</objective>
 */
public class ObjectivePlaceFlagDEM : BaseObjective
{
    public float MaxDistance = 40f;

    public override ObjectiveValueTypes ObjectiveValueType => ObjectiveValueTypes.Boolean;

    public override void SetupObjective()
    {
        keyword = Localization.Get("PlaceFlagDEM_keyword");
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    /// <summary>
    /// The flag was planted at the position. Returns false if it is too far from the quest's location.
    /// </summary>
    public bool TryPlace(Vector3 position, bool checkDistance)
    {
        if (Complete)
            return false;

        if (checkDistance && OwnerQuest.GetPositionData(out Vector3 location, Quest.PositionDataTypes.Location))
        {
            var offset = new Vector2(position.x - location.x, position.z - location.z);
            if (offset.magnitude > MaxDistance)
                return false;
        }

        OwnerQuest.SetPositionData(Quest.PositionDataTypes.Activate, position);
        CurrentValue = 1;
        Refresh();
        return true;
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
        properties.ParseFloat("max_distance", ref MaxDistance);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("max_distance", MaxDistance);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectivePlaceFlagDEM();
        CopyValues(objective);
        objective.MaxDistance = MaxDistance;
        return objective;
    }
}
