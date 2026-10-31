using UnityEngine;

/*
 * Rescue's pay: experience and dukes that grow with the survivors saved. Half is for finishing, the other half is
 * split between the survivors and paid for each one saved (ObjectiveRescueDEM's value).
 * 	<reward type="RescueDEM, QuestsExpanded" value="8400,2300"/>   experience and dukes when everyone is saved
 */
public class RewardRescueDEM : BaseReward
{
    public int FullExp;

    public int FullDukes;

    public override void SetupReward()
    {
        Description = Localization.Get("RewardRescueDEM_keyword");
        Icon = "ui_game_symbol_trophy";
        string[] parts = (Value ?? "").Split(',');
        if (parts.Length >= 1)
            int.TryParse(parts[0].Trim(), out FullExp);
        if (parts.Length >= 2)
            int.TryParse(parts[1].Trim(), out FullDukes);
        RefreshValue();
    }

    private ObjectiveRescueDEM Rescue
    {
        get
        {
            if (OwnerQuest == null)
                return null;
            foreach (BaseObjective objective in OwnerQuest.Objectives)
            {
                if (objective is ObjectiveRescueDEM rescue)
                    return rescue;
            }
            return null;
        }
    }

    /// <summary>The share of the full pay earned: half, plus half split between the survivors saved.</summary>
    private float Share
    {
        get
        {
            ObjectiveRescueDEM rescue = Rescue;
            if (rescue == null || rescue.Survivors <= 0)
                return 1f;
            return 0.5f + 0.5f * Mathf.Clamp01((float)rescue.Saved / rescue.Survivors);
        }
    }

    public int Exp => Mathf.RoundToInt(FullExp * Share);

    public int Dukes => Mathf.RoundToInt(FullDukes * Share);

    private void RefreshValue()
    {
        ObjectiveRescueDEM rescue = Rescue;
        ValueText = rescue != null
            ? string.Format(Localization.Get("RewardRescueDEM_value"), Exp, Dukes, rescue.Saved, rescue.Survivors)
            : Localization.Get("RewardRescueDEM_none");
    }

    public override string GetRewardText()
    {
        RefreshValue();
        return $"{Description} {ValueText}";
    }

    public override void GiveReward(EntityPlayer player)
    {
        var local = player as EntityPlayerLocal;
        RewardUtilsDEM.GiveExp(local, Exp);
        RewardUtilsDEM.GiveDukes(local, Dukes);
    }

    public override BaseReward Clone()
    {
        var reward = new RewardRescueDEM();
        CopyValues(reward);
        reward.FullExp = FullExp;
        reward.FullDukes = FullDukes;
        return reward;
    }
}
