using UnityEngine;

/*
 * Create Outpost: hold the flag planted in the POI (PlaceFlagDEM with the outpost flag) for a number of nights.
 * Every night at the attack hour a few waves hit the outpost, bigger every night. You are free to leave during the
 * day; warnings count down to each attack. Someone sharing the quest has to be at the outpost when an attack
 * starts, and the flag has to survive it, or the outpost falls and the quest fails for everyone sharing it.
 * The outpost's progress is kept on the server (OutpostRegistryDEM), so it survives logouts and restarts.
 * 	<objective type="OutpostDEM, QuestsExpanded">
 * 		<property name="phase" value="5"/>
 * 		<property name="nights" value="3"/>
 * 		<property name="attack_hour" value="22"/>
 * 		<property name="attack_waves" value="3"/>   waves in each night's attack
 * 		<property name="strength" value="1"/>       gamestage multiplier
 * 	</objective>
 */
public class ObjectiveOutpostDEM : ObjectiveDefenseBaseDEM
{
    public int Nights = 3;

    public int AttackHour = 22;

    public int AttackWaves = 3;

    public float Strength = 1f;

    public ObjectiveOutpostDEM() : base("OutpostDEM_keyword")
    {
    }

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get(TextKey("OutpostDEM_done"));
            int night = Mathf.Min(CurrentValue + 1, Nights);
            if (status.Fighting)
                return Format("OutpostDEM_fighting", night, Nights, status.ZombiesLeft);

            World world = GameManager.Instance.World;
            if (world == null || status.NextTime == 0)
                return Format("OutpostDEM_holding", night, Nights);
            ulong left = status.NextTime > world.worldTime ? status.NextTime - world.worldTime : 0;
            ulong minutes = left * 60 / WaveDirectorDEM.Hour;
            return Format("OutpostDEM_waiting", night, Nights, minutes / 60, (minutes % 60).ToString("00"));
        }
    }

    public override void AddHooks()
    {
        // Vanilla fails a POI quest whose rally point was activated when the player dies, and when a party member
        // logs in again; an outpost lasts for days and must survive both.
        OwnerQuest.RallyMarkerActivated = false;
        base.AddHooks();
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!DefenseSettingsDEM.FromPOI(OwnerQuest, out Vector3 center, out float radius, out Vector3 poiMin, out Vector3 poiSize)
            || !OwnerQuest.GetPositionData(out Vector3 flag, Quest.PositionDataTypes.Activate))
            return false;

        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.Outpost,
            Center = center,
            Radius = radius,
            // The attacks come from just outside the POI, so the outpost's fortifications matter
            SpawnStyle = DefenseSettingsDEM.SpawnStyles.Walls,
            PoiMin = poiMin,
            PoiSize = poiSize,
            Waves = Nights,
            WavesDone = CurrentValue,
            Strength = Strength,
            Flag = flag,
            AttackHour = AttackHour,
            AttackWaves = AttackWaves,
        };
        return true;
    }

    protected override bool IsDone()
    {
        return CurrentValue >= Nights;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseInt("nights", ref Nights);
        properties.ParseInt("attack_hour", ref AttackHour);
        properties.ParseInt("attack_waves", ref AttackWaves);
        properties.ParseFloat("strength", ref Strength);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("nights", Nights);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveOutpostDEM();
        CopyDefenseValues(objective);
        objective.Nights = Nights;
        objective.AttackHour = AttackHour;
        objective.AttackWaves = AttackWaves;
        objective.Strength = Strength;
        return objective;
    }
}
