using UnityEngine;

/*
 * Bandit Hideout: kill every bandit holding the quest's POI. The bandits come from an NPC mod (see NpcCatalogDEM);
 * traders only offer the quest when one adds them. WaveDirectorDEM posts them through the POI when the phase starts,
 * spread over its sleeper spots (the far ones first), with a leader with the boss buff at the far end. The POI's own
 * zombies don't have to be cleared. Every party member with the shared quest fights the same bandits.
 * 	<objective type="BanditHideoutDEM, QuestsExpanded">
 * 		<property name="phase" value="3"/>
 * 		<property name="leader" value="true"/>     a bandit leader at the far end
 * 		<property name="strength" value="1"/>      gamestage multiplier for how many bandits
 * 	</objective>
 */
public class ObjectiveBanditHideoutDEM : ObjectiveDefenseBaseDEM
{
    public bool Leader;

    public float Strength = 1f;

    public ObjectiveBanditHideoutDEM() : base("BanditHideoutDEM_keyword")
    {
    }

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get("BanditHideoutDEM_done");
            return status.Fighting
                ? string.Format(Localization.Get("BanditHideoutDEM_fighting"), status.ZombiesLeft)
                : Localization.Get("BanditHideoutDEM_waiting");
        }
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!DefenseSettingsDEM.FromPOI(OwnerQuest, out Vector3 center, out float radius, out Vector3 poiMin, out Vector3 poiSize))
            return false;

        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.Hideout,
            Center = center,
            Radius = radius,
            SpawnStyle = DefenseSettingsDEM.SpawnStyles.Walls,
            PoiMin = poiMin,
            PoiSize = poiSize,
            Waves = 1,
            WavesDone = CurrentValue,
            Strength = Strength,
            BossCount = Leader ? 1 : 0,
            Tier = OwnerQuest.QuestClass.DifficultyTier,
        };
        return true;
    }

    protected override bool IsDone()
    {
        return CurrentValue >= 1;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseBool("leader", ref Leader);
        properties.ParseFloat("strength", ref Strength);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("leader", Leader);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveBanditHideoutDEM();
        CopyDefenseValues(objective);
        objective.Leader = Leader;
        objective.Strength = Strength;
        return objective;
    }
}
