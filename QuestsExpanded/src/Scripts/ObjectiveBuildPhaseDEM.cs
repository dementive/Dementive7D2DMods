using UnityEngine;

/*
 * A countdown to build defenses before the waves come. Players can leave the area during it, e.g. to gather wood.
 * 	<objective type="BuildPhaseDEM, QuestsExpanded">
 * 		<property name="phase" value="3"/>
 * 		<property name="time" value="300"/>   seconds
 * 	</objective>
 */
public class ObjectiveBuildPhaseDEM : BaseObjective
{
    public float Time = 300f;

    private float remaining = -1f;

    private bool warned;

    public override bool useUpdateLoop => true;

    public override ObjectiveValueTypes ObjectiveValueType => ObjectiveValueTypes.Number;

    public override bool UpdateUI => true;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get("DefendWavesDEM_done");
            int seconds = Mathf.CeilToInt(Mathf.Max(remaining, 0f));
            return $"{seconds / 60}:{seconds % 60:00}";
        }
    }

    public override void SetupObjective()
    {
        keyword = Localization.Get("BuildPhaseDEM_keyword");
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    public override void AddHooks()
    {
        if (Complete || remaining >= 0f)
            return;

        remaining = Time;
        warned = false;
        ShowMessage("BuildPhaseDEM_start", Mathf.RoundToInt(Time / 60f));
    }

    public override void Update(float deltaTime)
    {
        if (Complete || remaining < 0f)
            return;

        remaining -= deltaTime;
        if (!warned && remaining <= 30f)
        {
            warned = true;
            ShowMessage("BuildPhaseDEM_warning", 30);
        }
        if (remaining <= 0f)
        {
            CurrentValue = 1;
            Refresh();
        }
    }

    private void ShowMessage(string key, int value)
    {
        EntityPlayerLocal player = OwnerQuest.OwnerJournal.OwnerPlayer;
        if (player != null)
            GameManager.ShowTooltip(player, string.Format(Localization.Get(key), value));
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
        properties.ParseFloat("time", ref Time);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("time", Time);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveBuildPhaseDEM();
        CopyValues(objective);
        objective.Time = Time;
        return objective;
    }
}
