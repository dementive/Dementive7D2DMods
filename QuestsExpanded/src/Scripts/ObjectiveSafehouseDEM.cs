using UnityEngine;

/*
 * Safehouse: build a safehouse around the flag you planted (PlaceFlagDEM in an earlier phase) to the tier's checklist
 * (SafehouseChecklistDEM), then refugees wait just outside the trader's compound: walk up to them and lead them home.
 * Once they've all moved in, the safehouse is attacked at the attack hour; someone sharing the quest has to be there.
 * Won if at least one refugee is alive when the last wave ends; they stay and guard the safehouse.
 * The refugees are friendly NPCs from an NPC mod that can follow a player (SCore's, see NpcCatalogDEM); traders only
 * offer the quest when there are some. WaveDirectorDEM runs it on the server and keeps it with the world
 * (SafehouseRegistryDEM), like an outpost, so it survives logouts, restarts and dying.
 * 	<objective type="SafehouseDEM, QuestsExpanded">
 * 		<property name="phase" value="2"/>
 * 		<property name="refugees" value="3"/>
 * 		<property name="attack_hour" value="22"/>
 * 		<property name="attack_waves" value="3"/>
 * 		<property name="strength" value="1"/>      gamestage multiplier for the attack
 * 	</objective>
 */
public class ObjectiveSafehouseDEM : ObjectiveDefenseBaseDEM
{
    public int Refugees = 3;

    public int AttackHour = 22;

    public int AttackWaves = 3;

    public float Strength = 1f;

    public ObjectiveSafehouseDEM() : base("SafehouseDEM_keyword")
    {
    }

    private int Tier => OwnerQuest.QuestClass.DifficultyTier;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get("SafehouseDEM_done");
            switch ((SafehouseDefense.Stages)status.Stage)
            {
                case SafehouseDefense.Stages.Build:
                    string missing = SafehouseChecklistDEM.Missing(status.Checklist, Tier, Refugees);
                    return missing == "" ? Localization.Get("SafehouseDEM_checking") : string.Format(Localization.Get("SafehouseDEM_building"), missing);
                case SafehouseDefense.Stages.Fetch:
                    return string.Format(Localization.Get("SafehouseDEM_fetching"), status.WavesDone, status.Waves);
                case SafehouseDefense.Stages.Night:
                    World world = GameManager.Instance.World;
                    if (world == null || status.NextTime == 0)
                        return Localization.Get("SafehouseDEM_waiting_night");
                    ulong left = status.NextTime > world.worldTime ? status.NextTime - world.worldTime : 0;
                    ulong minutes = left * 60 / WaveDirectorDEM.Hour;
                    return string.Format(Localization.Get("SafehouseDEM_night"), minutes / 60, (minutes % 60).ToString("00"));
                default:
                    return string.Format(Localization.Get("SafehouseDEM_fighting"), status.ZombiesLeft, status.Waves - status.Lost);
            }
        }
    }

    public override void AddHooks()
    {
        // A safehouse takes days; vanilla failing a quest on death or a party member's login doesn't apply
        OwnerQuest.RallyMarkerActivated = false;
        base.AddHooks();
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!OwnerQuest.GetPositionData(out Vector3 flag, Quest.PositionDataTypes.Activate))
            return false;
        if (!OwnerQuest.GetPositionData(out Vector3 trader, Quest.PositionDataTypes.QuestGiver)
            && !OwnerQuest.GetPositionData(out trader, Quest.PositionDataTypes.TraderPosition))
            trader = Player.position;

        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.Safehouse,
            Center = flag,
            Flag = flag,
            Radius = SafehouseChecklistDEM.Radius,
            SpawnStyle = DefenseSettingsDEM.SpawnStyles.Around,
            Waves = 1,
            WavesDone = CurrentValue,
            Count = Refugees,
            Strength = Strength,
            AttackHour = AttackHour,
            AttackWaves = AttackWaves,
            Trader = trader,
            Tier = Tier,
        };
        return true;
    }

    public override void UpdateStatus(DefenseStatusDEM newStatus)
    {
        // The status counts refugees settled in, which isn't the objective's progress: it's done when the night is held
        status = newStatus;
        if (status.Result == DefenseStatusDEM.Results.Lost)
        {
            Fail(null);
            return;
        }
        if (status.Result == DefenseStatusDEM.Results.Won)
        {
            CurrentValue = 1;
            Refresh();
        }
    }

    protected override bool IsDone()
    {
        return CurrentValue >= 1;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseInt("refugees", ref Refugees);
        properties.ParseInt("attack_hour", ref AttackHour);
        properties.ParseInt("attack_waves", ref AttackWaves);
        properties.ParseFloat("strength", ref Strength);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("refugees", Refugees);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveSafehouseDEM();
        CopyDefenseValues(objective);
        objective.Refugees = Refugees;
        objective.AttackHour = AttackHour;
        objective.AttackWaves = AttackWaves;
        objective.Strength = Strength;
        return objective;
    }
}
