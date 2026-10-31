using UnityEngine;

/*
 * Rescue: a group of survivors is holed up at the far end of the quest's POI, under attack when you arrive (zombies,
 * bandits, or both). Break the attack, then walk up to the survivors and lead them to the trader: each one who
 * reaches a trader's compound is saved. Done when every survivor is saved or lost; fails if none are saved. Pay
 * grows with the survivors saved (RewardRescueDEM).
 * The survivors are friendly NPCs from an NPC mod that can follow a player (SCore's, see NpcCatalogDEM); traders only
 * offer the quest when there are some. WaveDirectorDEM runs it on the server, so a party shares one group, and each
 * survivor follows whoever walks up to them.
 * The value is saved | lost << 4. Once the group is following, dying no longer fails the quest (like an outpost).
 * 	<objective type="RescueDEM, QuestsExpanded">
 * 		<property name="phase" value="3"/>
 * 		<property name="survivors" value="4"/>
 * 		<property name="strength" value="1"/>      gamestage multiplier for the attack
 * 	</objective>
 */
public class ObjectiveRescueDEM : ObjectiveDefenseBaseDEM
{
    public int Survivors = 3;

    public float Strength = 1f;

    public ObjectiveRescueDEM() : base("RescueDEM_keyword")
    {
    }

    public int Saved => CurrentValue & 15;

    public int Lost => (CurrentValue >> 4) & 15;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return string.Format(Localization.Get("RescueDEM_done"), Saved, Survivors);
            switch ((RescueDefense.Stages)status.Stage)
            {
                case RescueDefense.Stages.Attack:
                    return string.Format(Localization.Get("RescueDEM_fighting"), status.ZombiesLeft);
                case RescueDefense.Stages.Lead:
                    return string.Format(Localization.Get("RescueDEM_leading"), Saved, Survivors, Lost);
                default:
                    return Localization.Get("RescueDEM_waiting");
            }
        }
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!DefenseSettingsDEM.FromPOI(OwnerQuest, out Vector3 center, out float radius, out Vector3 poiMin, out Vector3 poiSize))
            return false;

        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.Rescue,
            Center = center,
            Radius = radius,
            // The siege comes half out of the building, half from just outside it
            SpawnStyle = DefenseSettingsDEM.SpawnStyles.Inside,
            PoiMin = poiMin,
            PoiSize = poiSize,
            Waves = 1,
            WavesDone = CurrentValue,
            Count = Survivors,
            Strength = Strength,
            Tier = OwnerQuest.QuestClass.DifficultyTier,
        };
        return true;
    }

    public override void UpdateStatus(DefenseStatusDEM newStatus)
    {
        status = newStatus;
        // The group is out of the POI's fight: vanilla failing a POI quest on death or a party member's login no
        // longer applies
        if (status.Stage >= (int)RescueDefense.Stages.Lead)
            OwnerQuest.RallyMarkerActivated = false;

        CurrentValue = (byte)(Mathf.Clamp(status.WavesDone, 0, 15) | (Mathf.Clamp(status.Lost, 0, 15) << 4));
        if (status.Result == DefenseStatusDEM.Results.Lost)
        {
            Fail(null);
            return;
        }
        Refresh();
    }

    protected override bool IsDone()
    {
        return status.Result == DefenseStatusDEM.Results.Won;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseInt("survivors", ref Survivors);
        properties.ParseFloat("strength", ref Strength);
        Survivors = Mathf.Clamp(Survivors, 1, 15);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("survivors", Survivors);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveRescueDEM();
        CopyDefenseValues(objective);
        objective.Survivors = Survivors;
        objective.Strength = Strength;
        return objective;
    }
}
