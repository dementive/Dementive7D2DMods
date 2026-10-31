using UnityEngine;

/*
 * Last Stand: endless waves at the flag, each harder than the last, with a boss every few waves. The objective's
 * value is the waves this player has held. Walking away from the flag during a break banks them (the objective
 * completes and RewardLastStandDEM pays for them at the trader); walking away during a wave is fleeing, and dying
 * is dying: both fail the quest and lose everything. In a party everyone banks for themselves.
 * 	<objective type="LastStandDEM, QuestsExpanded">
 * 		<property name="phase" value="4"/>
 * 		<property name="radius" value="12"/>          size of the defended area around the flag
 * 		<property name="leave_distance" value="50"/>  how far from the flag counts as leaving
 * 		<property name="break" value="30"/>           seconds between waves
 * 		<property name="boss_every" value="5"/>       a boss joins every this many waves
 * 		<property name="bosses" value="zombieBiker,zombieFatCop"/>
 * 		<property name="strength" value="1"/>         gamestage multiplier for the first wave
 * 	</objective>
 */
public class ObjectiveLastStandDEM : ObjectiveDefenseBaseDEM
{
    public float Radius = 12f;

    public float LeaveDistance = 50f;

    public float BreakSeconds = 30f;

    public int BossEvery = 5;

    public string Bosses = "";

    public float Strength = 1f;

    public string Spawners = WaveDirectorDEM.DefaultSpawner;

    private Vector3 center;

    /// <summary>The waves the server had counted the last time it reported, or -1 before its first report.</summary>
    private int serverWaves = -1;

    private float checkTimer;

    public ObjectiveLastStandDEM() : base("LastStandDEM_keyword")
    {
    }

    public override bool useUpdateLoop => true;

    public override string StatusText
    {
        get
        {
            if (Complete)
                return Format("LastStandDEM_banked_status", CurrentValue);
            if (status.Fighting)
                return Format("LastStandDEM_fighting", status.WavesDone + 1, status.ZombiesLeft);
            return CurrentValue == 0
                ? Localization.Get(TextKey("LastStandDEM_waiting"))
                : Format("LastStandDEM_break", CurrentValue);
        }
    }

    protected override bool BuildSettings(out DefenseSettingsDEM settings)
    {
        settings = null;
        if (!OwnerQuest.GetPositionData(out center, Quest.PositionDataTypes.Activate))
            return false;

        settings = new DefenseSettingsDEM
        {
            Mode = DefenseSettingsDEM.Modes.LastStand,
            Center = center,
            Radius = Radius,
            // Picked up again after a logout: carry on at the same difficulty
            WavesDone = CurrentValue,
            Spawners = Spawners,
            Bosses = Bosses,
            Strength = Strength,
            BreakSeconds = BreakSeconds,
            BossEvery = BossEvery,
        };
        return true;
    }

    public override void UpdateStatus(DefenseStatusDEM newStatus)
    {
        status = newStatus;
        // Only waves held while this player was in the stand count for them
        if (serverWaves >= 0 && status.WavesDone > serverWaves)
            CurrentValue = (byte)Mathf.Min(CurrentValue + status.WavesDone - serverWaves, 255);
        serverWaves = status.WavesDone;
    }

    public override void Update(float deltaTime)
    {
        if (Complete || !joined)
            return;
        checkTimer -= deltaTime;
        if (checkTimer > 0f)
            return;
        checkTimer = 0.5f;

        EntityPlayerLocal player = Player;
        if (player == null)
            return;
        if (player.IsDead())
        {
            Fail("LastStandDEM_died");
            return;
        }
        if (Flat(player.position, center) <= LeaveDistance)
            return;

        if (status.Fighting)
            Fail("LastStandDEM_fled");
        else if (CurrentValue == 0)
            Fail("LastStandDEM_left_early");
        else
            Bank();
    }

    private void Bank()
    {
        foreach (BaseReward reward in OwnerQuest.Rewards)
            (reward as RewardLastStandDEM)?.RefreshValue(CurrentValue);
        GameManager.ShowTooltip(Player, Format("LastStandDEM_banked", CurrentValue));
        Complete = true;
        OwnerQuest.RefreshQuestCompletion();
    }

    protected override bool IsDone()
    {
        // Only banking completes it
        return false;
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseFloat("radius", ref Radius);
        properties.ParseFloat("leave_distance", ref LeaveDistance);
        properties.ParseFloat("break", ref BreakSeconds);
        properties.ParseInt("boss_every", ref BossEvery);
        properties.ParseString("bosses", ref Bosses);
        properties.ParseFloat("strength", ref Strength);
        properties.ParseString("spawners", ref Spawners);
    }

    public override void InternalToParametersDictionary(ref System.Collections.Generic.Dictionary<string, object> parameters)
    {
        parameters.Add("boss_every", BossEvery);
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveLastStandDEM();
        CopyDefenseValues(objective);
        objective.Radius = Radius;
        objective.LeaveDistance = LeaveDistance;
        objective.BreakSeconds = BreakSeconds;
        objective.BossEvery = BossEvery;
        objective.Bosses = Bosses;
        objective.Strength = Strength;
        objective.Spawners = Spawners;
        return objective;
    }
}
