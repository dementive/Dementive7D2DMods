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
 * 		<property name="spawners" value="defenseGSList"/>       gamestage spawners, one picked per wave
 * 		<property name="bosses" value="zombieMutatedCharged"/>  a boss for the final wave (one picked at random)
 * 		<property name="strength" value="1.25"/>                gamestage multiplier
 * 		<property name="bounty" value="true"/>                  the boss waits inside the POI instead of waves
 * 		<property name="keyword" value="DefendWavesDEM_keyword"/>
 * 		<property name="text" value="horde"/>                   use DefendWavesDEM_*_horde text where there is one
 * 	</objective>
 */
public class ObjectiveDefendWavesDEM : BaseObjective
{
    public int Waves = 3;

    public string Center = "poi";

    public float Radius = 10f;

    public string Spawners = WaveDirectorDEM.DefaultSpawner;

    public string Bosses = "";

    public float Strength = 1f;

    public bool Bounty;

    public string KeywordKey = "DefendWavesDEM_keyword";

    public string Text = "";

    private bool fighting;

    private int zombiesLeft;

    private bool joined;

    public override ObjectiveValueTypes ObjectiveValueType => ObjectiveValueTypes.Number;

    public override bool UpdateUI => true;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get(TextKey(Bounty ? "DefendWavesDEM_bounty_done" : "DefendWavesDEM_done"));
            if (Bounty)
                return Localization.Get(TextKey("DefendWavesDEM_bounty_hunting"));
            int wave = Mathf.Min(CurrentValue + 1, Waves);
            return fighting
                ? string.Format(Localization.Get(TextKey("DefendWavesDEM_fighting")), wave, Waves, zombiesLeft)
                : string.Format(Localization.Get(TextKey("DefendWavesDEM_waiting")), wave, Waves);
        }
    }

    /// <summary>
    /// The quest's own version of a text, e.g. DefendWavesDEM_incoming_horde for text "horde", if there is one.
    /// </summary>
    public string TextKey(string key)
    {
        return Text != "" && Localization.Exists(key + "_" + Text) ? key + "_" + Text : key;
    }

    public override void SetupObjective()
    {
        keyword = Localization.Get(KeywordKey);
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    public override void AddHooks()
    {
        if (joined || Complete || !GetArea(out Vector3 center, out float radius))
            return;

        joined = true;
        var settings = new DefenseSettingsDEM
        {
            Center = center,
            Radius = radius,
            Waves = Waves,
            WavesDone = CurrentValue,
            Spawners = Spawners,
            Bosses = Bosses,
            Strength = Strength,
            Bounty = Bounty,
        };

        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            WaveDirectorDEM.Join(OwnerQuest.QuestCode, OwnerQuest.OwnerJournal.OwnerPlayer.entityId, settings);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupJoin(OwnerQuest.QuestCode, settings));
        }
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

    public override void RemoveHooks()
    {
        if (!joined)
            return;

        joined = false;
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            WaveDirectorDEM.Leave(OwnerQuest.QuestCode, OwnerQuest.OwnerJournal.OwnerPlayer.entityId);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupLeave(OwnerQuest.QuestCode));
        }
    }

    /// <summary>
    /// Called with the server's status of the defense.
    /// </summary>
    public void UpdateStatus(int wavesDone, bool waveActive, int zombies)
    {
        fighting = waveActive;
        zombiesLeft = zombies;
        if (wavesDone > CurrentValue)
        {
            CurrentValue = (byte)Mathf.Min(wavesDone, Waves);
            Refresh();
        }
    }

    public override void Refresh()
    {
        if (Complete)
            return;

        Complete = CurrentValue >= Waves && OwnerQuest.CheckRequirements();
        if (Complete)
            OwnerQuest.RefreshQuestCompletion();
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseInt("waves", ref Waves);
        properties.ParseString("center", ref Center);
        properties.ParseFloat("radius", ref Radius);
        properties.ParseString("spawners", ref Spawners);
        properties.ParseString("bosses", ref Bosses);
        properties.ParseFloat("strength", ref Strength);
        properties.ParseBool("bounty", ref Bounty);
        properties.ParseString("keyword", ref KeywordKey);
        properties.ParseString("text", ref Text);
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
        CopyValues(objective);
        objective.Waves = Waves;
        objective.Center = Center;
        objective.Radius = Radius;
        objective.Spawners = Spawners;
        objective.Bosses = Bosses;
        objective.Strength = Strength;
        objective.Bounty = Bounty;
        objective.KeywordKey = KeywordKey;
        objective.Text = Text;
        return objective;
    }
}
