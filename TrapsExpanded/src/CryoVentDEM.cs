using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Cryo Vent (XML class "CryoVentDEM, TrapsExpanded"): a frosty floor grate over fridge coils. Every PulseDelay seconds
/// each zombie over it (within Radius) takes ColdDamage and a Chilled stack (each stack slower, lasting ChillSeconds;
/// levels lengthen it); at FreezeAt stacks it freezes for FreezeSeconds, then can't freeze again for a while. Frozen
/// zombies take double damage from blunt and crushing hits. Big zombies never freeze. Upgrades (level 3): A Deep
/// Freeze (freezes at DeepFreezeAt stacks, for DeepFreezeSeconds), B Frost Field (an ice patch FrostRadius wide whose
/// chill lasts FrostExtraSeconds longer).
///
/// The model's VentPoint is the grate's top center. XML properties: Radius, PulseDelay, ColdDamage, ChillSeconds,
/// FreezeAt, FreezeSeconds, DeepFreezeAt, DeepFreezeSeconds, FrostRadius, FrostExtraSeconds, PulseSound, and the
/// shared ones.
/// </summary>
public class BlockCryoVentDEM : BlockTrapDEM
{
    public float Radius = 1f;
    public float PulseDelay = 1.5f;
    public float ColdDamage = 6f;
    public float ChillSeconds = 4f;
    public int FreezeAt = 3;
    public float FreezeSeconds = 2f;
    public int DeepFreezeAt = 2;
    public float DeepFreezeSeconds = 3f;
    public float FrostRadius = 2.5f;
    public float FrostExtraSeconds = 5f;
    public string PulseSound = "SlowSwoosh";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Radius", ref Radius);
        Properties.ParseFloat("PulseDelay", ref PulseDelay);
        Properties.ParseFloat("ColdDamage", ref ColdDamage);
        Properties.ParseFloat("ChillSeconds", ref ChillSeconds);
        Properties.ParseInt("FreezeAt", ref FreezeAt);
        Properties.ParseFloat("FreezeSeconds", ref FreezeSeconds);
        Properties.ParseInt("DeepFreezeAt", ref DeepFreezeAt);
        Properties.ParseFloat("DeepFreezeSeconds", ref DeepFreezeSeconds);
        Properties.ParseFloat("FrostRadius", ref FrostRadius);
        Properties.ParseFloat("FrostExtraSeconds", ref FrostExtraSeconds);
        Properties.ParseString("PulseSound", ref PulseSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<CryoVentControllerDEM>();
    }
}

public class CryoVentControllerDEM : TrapControllerDEM
{
    /// <summary>Between the chilled and the frozen zombies in an effect's id list.</summary>
    private const int FrozenMark = -99;

    private BlockCryoVentDEM vent;
    private Transform ventPoint;
    private float iceUntil;

    private static readonly List<int> chilled = new List<int>();
    private static readonly List<int> frozen = new List<int>();

    protected override float ActDelay => vent.PulseDelay;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        vent = (BlockCryoVentDEM)trap;
        base.Setup(trap, pos);
        ventPoint = FindDeep(transform, "VentPoint");
    }

    protected override bool Act(World world)
    {
        Vector3 center = WorldPoint(ventPoint, new Vector3(0f, -0.3f, 0f));
        bool deep = Upgraded('A');
        bool field = Upgraded('B');
        float radius = field ? vent.FrostRadius : vent.Radius;
        float chill = (vent.ChillSeconds + (field ? vent.FrostExtraSeconds : 0f)) * DurationMult;
        int freezeAt = deep ? vent.DeepFreezeAt : vent.FreezeAt;
        float freeze = (deep ? vent.DeepFreezeSeconds : vent.FreezeSeconds) * DurationMult;
        int owner = Owner(world);
        chilled.Clear();
        frozen.Clear();
        foreach (EntityAlive e in Enemies(world, center + Vector3.up, radius + 1f))
        {
            Vector3 flat = e.position - center;
            float dy = flat.y;
            flat.y = 0f;
            if (flat.magnitude > radius || dy < -0.6f || dy > 1.2f)
            {
                continue;
            }
            Touch(e, false);
            if (!Hit(e, vent.ColdDamage * DamageMult, EnumDamageTypes.Cold, Vector3.up, owner, 0f))
            {
                continue;
            }
            if (TrapStatusDEM.Chill(e, 1, freezeAt, freeze, chill, owner))
            {
                frozen.Add(e.entityId);
            }
            else
            {
                chilled.Add(e.entityId);
            }
        }
        if (chilled.Count + frozen.Count == 0)
        {
            return false;
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(center, vent.PulseSound);
        List<int> ids = new List<int>
        {
            -Mathf.RoundToInt(chill * 10f), -Mathf.RoundToInt(freeze * 10f), field ? -2 : -1
        };
        ids.AddRange(chilled);
        ids.Add(FrozenMark);
        ids.AddRange(frozen);
        Broadcast(center, ids.ToArray());
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        if (ids.Length < 3)
        {
            return;
        }
        float chill = -ids[0] / 10f;
        float freeze = -ids[1] / 10f;
        bool field = ids[2] == -2;
        Vector3 center = WorldPoint(ventPoint, new Vector3(0f, -0.3f, 0f));
        FxDEM.Spawn("ColdMist", center, Quaternion.identity, 0.6f);
        if (field && Time.time > iceUntil - 1f)
        {
            iceUntil = Time.time + 6f;
            FxDEM.Spawn("IcePatch", center + Vector3.up * 0.02f, Quaternion.identity, 6f);
        }
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return;
        }
        bool frozenPart = false;
        for (int i = 3; i < ids.Length; i++)
        {
            if (ids[i] == FrozenMark)
            {
                frozenPart = true;
                continue;
            }
            if (world.GetEntity(ids[i]) is EntityAlive e)
            {
                FxDEM.Attach(e, frozenPart ? "FrostCrust" : "FrostMist", frozenPart ? freeze : chill, 0.5f);
            }
        }
    }
}
