using UnityEngine;

/*
 * Fight zombies run by WaveDirectorDEM on the server: waves at the quest's POI, at its location or around the
 * flag the player planted, or a bounty boss inside the POI. Every party member with the shared quest joins the
 * same defense. The waves completed are the objective's value, so a quest picked up again later resumes from the
 * next wave. Put a POIStayWithin or StayWithin in the same phase so leaving the area fails the quest.
 * 	<objective type="DefendWavesDEM, QuestsExpanded">
 * 		<property name="phase" value="4"/>
 * 		<property name="waves" value="3"/>
 * 		<property name="center" value="poi"/>                   poi (default), location or flag
 * 		<property name="radius" value="10"/>                    size of the area for location/flag (POIs use their footprint)
 * 		<property name="spawn" value="inside"/>                 POIs: walls (default; zombies come from just outside the
 * 		                                                        footprint) or inside (about half come out of the building)
 * 		<property name="spawners" value="defenseGSList"/>       gamestage spawners, one picked per wave
 * 		<property name="bosses" value="zombieMutatedCharged"/>  a boss for the final wave (one picked at random)
 * 		<property name="strength" value="1.25"/>                gamestage multiplier
 * 		<property name="bounty" value="true"/>                  the boss waits inside the POI instead of waves
 * 		<property name="keyword" value="DefendWavesDEM_keyword"/>
 * 		<property name="text" value="horde"/>                   use DefendWavesDEM_*_horde text where there is one
 * 	</objective>
 */
public class ObjectiveDefendWavesDEM : ObjectiveDefenseBaseDEM
{
    public int Waves = 3;

    public string Center = "poi";

    public string Spawn = "walls";

    public float Radius = 10f;

    public string Spawners = WaveDirectorDEM.DefaultSpawner;

    public string Bosses = "";

    public float Strength = 1f;

    public bool Bounty;

    public ObjectiveDefendWavesDEM() : base("DefendWavesDEM_keyword")
    {
    }

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get(TextKey(Bounty ? "DefendWavesDEM_bounty_done" : "DefendWavesDEM_done"));
            if (Bounty)
                return Localization.Get(TextKey("DefendWavesDEM_bounty_hunting"));
            int wave = Mathf.Min(CurrentValue + 1, Waves);
            return status.Fighting
                ? Format("DefendWavesDEM_fighting", wave, Waves, status.ZombiesLeft)
                : Format("DefendWavesDEM_waiting", wave, Waves);
        }
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!GetArea(out Vector3 center, out float radius))
            return false;

        var spawnStyle = DefenseSettingsDEM.SpawnStyles.Around;
        Vector3 poiMin = Vector3.zero, poiSize = Vector3.zero;
        if (Center != "flag" && Center != "location" && DefenseSettingsDEM.FromPOI(OwnerQuest, out _, out _, out poiMin, out poiSize))
            spawnStyle = Spawn == "inside" ? DefenseSettingsDEM.SpawnStyles.Inside : DefenseSettingsDEM.SpawnStyles.Walls;

        settings = new DefenseSettingsDEM
        {
            Mode = Bounty ? DefenseSettingsDEM.Modes.Bounty : DefenseSettingsDEM.Modes.Waves,
            Center = center,
            Radius = radius,
            SpawnStyle = spawnStyle,
            PoiMin = poiMin,
            PoiSize = poiSize,
            Waves = Waves,
            WavesDone = CurrentValue,
            Spawners = Spawners,
            Bosses = Bosses,
            Strength = Strength,
        };
        return true;
    }

    private bool GetArea(out Vector3 center, out float radius)
    {
        radius = Radius;
        switch (Center)
        {
            case "flag":
                return OwnerQuest.GetPositionData(out center, Quest.PositionDataTypes.Activate);
            case "location":
                if (!OwnerQuest.GetPositionData(out center, Quest.PositionDataTypes.Location))
                    center = OwnerQuest.Position;
                return center != Vector3.zero;
            default:
                return DefenseSettingsDEM.FromPOI(OwnerQuest, out center, out radius);
        }
    }

    protected override bool IsDone()
    {
        return CurrentValue >= Waves;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseInt("waves", ref Waves);
        properties.ParseString("center", ref Center);
        properties.ParseString("spawn", ref Spawn);
        properties.ParseFloat("radius", ref Radius);
        properties.ParseString("spawners", ref Spawners);
        properties.ParseString("bosses", ref Bosses);
        properties.ParseFloat("strength", ref Strength);
        properties.ParseBool("bounty", ref Bounty);
        if (Bounty)
            Waves = 1;
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("waves", Waves);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveDefendWavesDEM();
        CopyDefenseValues(objective);
        objective.Waves = Waves;
        objective.Center = Center;
        objective.Spawn = Spawn;
        objective.Radius = Radius;
        objective.Spawners = Spawners;
        objective.Bosses = Bosses;
        objective.Strength = Strength;
        objective.Bounty = Bounty;
        return objective;
    }
}
