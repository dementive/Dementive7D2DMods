using UnityEngine;

/*
 * Last Stand's payout: experience and dukes for the waves the player banked (ObjectiveLastStandDEM's value). Each
 * wave pays 25% more than the one before, so staying pays faster the longer you stay.
 * 	<reward type="LastStandDEM, QuestsExpanded" value="550,145"/>   experience and dukes for the first wave
 */
public class RewardLastStandDEM : BaseReward, IPotRewardDEM
{
    /// <summary>How much more each wave pays than the one before.</summary>
    public const float Growth = 0.25f;

    public int BaseExp;

    public int BaseDukes;

    public override void SetupReward()
    {
        Description = Localization.Get("RewardLastStandDEM_keyword");
        Icon = "ui_game_symbol_trophy";
        ParseValue();
        RefreshValue(Waves);
    }

    private void ParseValue()
    {
        string[] parts = (Value ?? "").Split(',');
        if (parts.Length >= 1)
            int.TryParse(parts[0].Trim(), out BaseExp);
        if (parts.Length >= 2)
            int.TryParse(parts[1].Trim(), out BaseDukes);
    }

    /// <summary>The waves banked by the quest's last stand.</summary>
    private int Waves
    {
        get
        {
            if (OwnerQuest == null)
                return 0;
            foreach (BaseObjective objective in OwnerQuest.Objectives)
            {
                if (objective is ObjectiveLastStandDEM stand)
                    return stand.CurrentValue;
            }
            return 0;
        }
    }

    /// <summary>The total for a number of waves: base * (1 + (1 + g) + (1 + 2g) + ...).</summary>
    public static int Total(int baseAmount, int waves)
    {
        return Mathf.RoundToInt(baseAmount * (waves + Growth * waves * (waves - 1) / 2f));
    }

    public int PotExp => Total(BaseExp, Waves);

    public int PotDukes => Total(BaseDukes, Waves);

    public void RefreshValue(int waves)
    {
        ValueText = waves > 0
            ? string.Format(Localization.Get("RewardLastStandDEM_value"), Total(BaseExp, waves), Total(BaseDukes, waves), waves)
            : Localization.Get("RewardLastStandDEM_none");
    }

    public override string GetRewardText()
    {
        RefreshValue(Waves);
        return $"{Description} {ValueText}";
    }

    public override void GiveReward(EntityPlayer player)
    {
        var local = player as EntityPlayerLocal;
        RewardUtilsDEM.GiveExp(local, PotExp);
        RewardUtilsDEM.GiveDukes(local, PotDukes);
    }

    public override BaseReward Clone()
    {
        var reward = new RewardLastStandDEM();
        CopyValues(reward);
        reward.BaseExp = BaseExp;
        reward.BaseDukes = BaseDukes;
        return reward;
    }
}
