using UnityEngine;

/// <summary>
/// Tesla Coil block (XML class "TeslaCoilDEM, TrapsExpanded"). The zapping lives in TeslaCoilControllerDEM on the
/// block's model.
///
/// XML properties: EntityDamage, Range, FireDelay (seconds between zaps), Chains (extra targets per zap),
/// ChainRange, ChainFalloff (damage multiplier per jump), JoltChance and JoltBuff (per zombie hit), ZapSound, and
/// the Soaked combo: SoakedDamage (damage multiplier on soaked zombies), SoakedChains (extra jumps once the arc has
/// hit a soaked zombie), SoakedStunBuff and SoakedStunImmuneBuff (a soaked zombie's jolt becomes a stun, then it
/// can't be stunned again for a while). Upgrades (level 3): A Storm (StormChains more jumps at StormDamage), B
/// Overload (no jumps, OverloadDamage times the damage, and every hit jolts: a stun on zombies that aren't big, then
/// the stun immunity). Wear, levels and the rest come from BlockTrapDEM.
/// </summary>
public class BlockTeslaCoilDEM : BlockTrapDEM
{
    public float EntityDamage = 22f;
    public float Range = 8f;
    public float FireDelay = 1.5f;
    public int Chains = 2;
    public float ChainRange = 4f;
    public float ChainFalloff = 0.6f;
    public float JoltChance = 0.1f;
    public string JoltBuff = "buffDementiveTrapsJolt";
    public string ZapSound = "electric_fence_impact";
    public float SoakedDamage = 2f;
    public int SoakedChains = 1;
    public string SoakedStunBuff = "buffDementiveTrapsStun";
    public string SoakedStunImmuneBuff = "buffDementiveTrapsStunImmune";
    public int StormChains = 2;
    public float StormDamage = 0.8f;
    public float OverloadDamage = 2.5f;

    /// <summary>Arc origin: the toroid's center, relative to the bottom center of the block.</summary>
    public static readonly Vector3 ArcOffset = new Vector3(0.5f, 1.62f, 0.5f);

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("EntityDamage", ref EntityDamage);
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseInt("Chains", ref Chains);
        Properties.ParseFloat("ChainRange", ref ChainRange);
        Properties.ParseFloat("ChainFalloff", ref ChainFalloff);
        Properties.ParseFloat("JoltChance", ref JoltChance);
        Properties.ParseString("JoltBuff", ref JoltBuff);
        Properties.ParseString("ZapSound", ref ZapSound);
        Properties.ParseFloat("SoakedDamage", ref SoakedDamage);
        Properties.ParseInt("SoakedChains", ref SoakedChains);
        Properties.ParseString("SoakedStunBuff", ref SoakedStunBuff);
        Properties.ParseString("SoakedStunImmuneBuff", ref SoakedStunImmuneBuff);
        Properties.ParseInt("StormChains", ref StormChains);
        Properties.ParseFloat("StormDamage", ref StormDamage);
        Properties.ParseFloat("OverloadDamage", ref OverloadDamage);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<TeslaCoilControllerDEM>();
    }
}
