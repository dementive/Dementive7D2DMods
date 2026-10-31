using UnityEngine;

/*
 * Blood Moon Bounty: when the next blood moon starts, bosses come for the player wherever they are, one wave of
 * bosses every in-game hour. Kill every one of them without dying; there is no deadline, so bosses that are still
 * alive at dawn keep hunting. In a party, everyone sharing the quest fights the same bosses (more of them for a
 * bigger party); a member who dies fails their own bounty while the rest carry on.
 * Traders only offer quests with this objective in the 2 days before a blood moon (BloodMoonBountyPatches).
 * 	<objective type="BloodMoonBountyDEM, QuestsExpanded">
 * 		<property name="phase" value="1"/>
 * 		<property name="bosses" value="zombieBiker,zombieFatCop;zombieWightFeral"/>  one list per boss wave, separated by ';'
 * 		<property name="count" value="2"/>                                          bosses in each wave
 * 	</objective>
 */
public class ObjectiveBloodMoonBountyDEM : ObjectiveDefenseBaseDEM
{
    public string Bosses = "";

    public int Count = 1;

    private float checkTimer;

    public ObjectiveBloodMoonBountyDEM() : base("BloodMoonBountyDEM_keyword")
    {
    }

    public override bool useUpdateLoop => true;

    public int Waves => Bosses.Split(';').Length;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Localization.Get(TextKey("BloodMoonBountyDEM_done"));
            if (status.Fighting || CurrentValue > 0)
                return Format("BloodMoonBountyDEM_fighting", status.ZombiesLeft, Waves - CurrentValue);
            return Format("BloodMoonBountyDEM_waiting", GameStats.GetInt(EnumGameStats.BloodMoonDay));
        }
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.BloodMoon,
            Center = Player.position,
            Waves = Waves,
            WavesDone = CurrentValue,
            Bosses = Bosses,
            BossCount = Count,
        };
        return true;
    }

    public override void Update(float deltaTime)
    {
        if (Complete || !joined)
            return;
        checkTimer -= deltaTime;
        if (checkTimer > 0f)
            return;
        checkTimer = 0.5f;

        if (Player != null && Player.IsDead())
            Fail("BloodMoonBountyDEM_died");
    }

    protected override bool IsDone()
    {
        return CurrentValue >= Waves;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseString("bosses", ref Bosses);
        properties.ParseInt("count", ref Count);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("count", Count);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveBloodMoonBountyDEM();
        CopyDefenseValues(objective);
        objective.Bosses = Bosses;
        objective.Count = Count;
        return objective;
    }
}
