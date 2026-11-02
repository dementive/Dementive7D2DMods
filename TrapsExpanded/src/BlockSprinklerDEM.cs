using UnityEngine;

/// <summary>
/// Sprinkler block (XML class "SprinklerDEM, TrapsExpanded"). Sprays a cone ahead of its nozzle and soaks the
/// zombies in it; the work lives in SprinklerControllerDEM on the block's model.
///
/// XML properties: Range, ConeAngle (full angle in degrees), PulseDelay (seconds between sprays), SoakBuff,
/// SoakSeconds (how long zombies stay soaked; levels lengthen it), SpraySound. Upgrades (level 3): A Deluge
/// (DelugeAngle cone, DelugeSeconds soak), B Pressure Washer (a WasherAngle jet that shoves zombies WasherShove meters
/// for WasherDamage). Wear, levels and the rest come from BlockTrapDEM.
/// </summary>
public class BlockSprinklerDEM : BlockTrapDEM
{
    public float Range = 6f;
    public float ConeAngle = 60f;
    public float PulseDelay = 1f;
    public string SoakBuff = TrapStatusDEM.Soaked;
    public float SoakSeconds = 10f;
    public string SpraySound = "bucketbail_water";
    public float DelugeAngle = 90f;
    public float DelugeSeconds = 20f;
    public float WasherAngle = 20f;
    public float WasherShove = 1f;
    public float WasherDamage = 15f;

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("ConeAngle", ref ConeAngle);
        Properties.ParseFloat("PulseDelay", ref PulseDelay);
        Properties.ParseString("SoakBuff", ref SoakBuff);
        Properties.ParseFloat("SoakSeconds", ref SoakSeconds);
        Properties.ParseString("SpraySound", ref SpraySound);
        Properties.ParseFloat("DelugeAngle", ref DelugeAngle);
        Properties.ParseFloat("DelugeSeconds", ref DelugeSeconds);
        Properties.ParseFloat("WasherAngle", ref WasherAngle);
        Properties.ParseFloat("WasherShove", ref WasherShove);
        Properties.ParseFloat("WasherDamage", ref WasherDamage);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<SprinklerControllerDEM>();
    }
}
