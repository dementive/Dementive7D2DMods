using UnityEngine;

/*
 * Defend the quest's POI against waves of zombies run by WaveDirectorDEM on the server. Put it in the same phase
 * as POIStayWithin so leaving the area fails the quest. Every party member with the shared quest joins the same
 * defense, and the waves completed are the objective's value, so a quest picked up again later resumes from the
 * next wave.
 * 	<objective type="DefendWavesDEM, QuestsExpanded">
 * 		<property name="phase" value="4"/>
 * 		<property name="waves" value="3"/>
 * 	</objective>
 */
public class ObjectiveDefendWavesDEM : BaseObjective
{
    public const string PropWaves = "waves";

    public int Waves = 3;

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
                return Localization.Get("DefendWavesDEM_done");
            int wave = Mathf.Min(CurrentValue + 1, Waves);
            return fighting
                ? string.Format(Localization.Get("DefendWavesDEM_fighting"), wave, Waves, zombiesLeft)
                : string.Format(Localization.Get("DefendWavesDEM_waiting"), wave, Waves);
        }
    }

    public override void SetupObjective()
    {
        keyword = Localization.Get("DefendWavesDEM_keyword");
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    public override void AddHooks()
    {
        if (joined || Complete || !OwnerQuest.GetPositionData(out Vector3 poiPosition, Quest.PositionDataTypes.POIPosition))
            return;

        OwnerQuest.GetPositionData(out Vector3 poiSize, Quest.PositionDataTypes.POISize);
        joined = true;

        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            WaveDirectorDEM.Join(OwnerQuest.QuestCode, OwnerQuest.OwnerJournal.OwnerPlayer.entityId, poiPosition, poiSize, Waves, CurrentValue);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupJoin(OwnerQuest.QuestCode, poiPosition, poiSize, Waves, CurrentValue));
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
        if (properties.Values.ContainsKey(PropWaves))
            Waves = StringParsers.ParseSInt32(properties.Values[PropWaves]);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add(PropWaves, Waves);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveDefendWavesDEM();
        CopyValues(objective);
        objective.Waves = Waves;
        return objective;
    }
}
