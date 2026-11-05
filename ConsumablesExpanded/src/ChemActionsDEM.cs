using UnityEngine;

/// <summary>Effect actions used from items.xml and buffs.xml as action="Name, ConsumablesExpanded". Each runs only on the
/// player's own machine: that's where a player's buffs run and their health is changed.</summary>
public class MinEventActionDementiveNickOfTime : MinEventActionBase
{
    public override void Execute(MinEventParams _params)
    {
        var self = _params.Self;
        if (self != null && !self.isEntityRemote)
            self.Buffs.AddBuff(ChemTimeDEM.IsSolo() ? ChemTimeDEM.SoloBuff : ChemTimeDEM.CoopBuff);
    }
}

public class MinEventActionDementiveOverdose : MinEventActionBase
{
    public override void Execute(MinEventParams _params)
    {
        var self = _params.Self;
        if (self != null && !self.isEntityRemote)
            ChemDamageDEM.Hurt(Mathf.CeilToInt(self.GetMaxHealth() * .5f));
    }
}

public class MinEventActionDementiveTabBill : MinEventActionBase
{
    public override void Execute(MinEventParams _params)
    {
        var self = _params.Self;
        if (self != null && !self.isEntityRemote)
            ChemDamageDEM.PayTab(self);
    }
}
