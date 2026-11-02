using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Ram (XML class "RamDEM, TrapsExpanded"): a log-splitter ram on a skid with a road sign for a striking plate. Every
/// FireDelay seconds, if a zombie is in front of it (within Reach, Width wide), it punches every zombie there for
/// HitDamage (blunt, so frozen zombies shatter) and knocks them back Knockback meters, with no stun. Upgrades (level 3):
/// A Piledriver (PiledriverDamage times the damage, no knockback), B Battering Ram (BatteringKnockback meters, reaching
/// BatteringReach).
///
/// The model's RamPart slides RamStroke meters forward and back when it punches. XML properties: Reach, Width,
/// FireDelay, HitDamage, Knockback, PiledriverDamage, BatteringKnockback, BatteringReach, RamPart, RamStroke, PunchSound,
/// HitSound, and the shared ones.
/// </summary>
public class BlockRamDEM : BlockTrapDEM
{
    public float Reach = 2f;
    public float Width = 1.2f;
    public float FireDelay = 2f;
    public float HitDamage = 60f;
    public float Knockback = 4f;
    public float PiledriverDamage = 2f;
    public float BatteringKnockback = 8f;
    public float BatteringReach = 3f;
    public string RamPart = "RamHead";
    public float RamStroke = 0.6f;
    public string PunchSound = "sledge_swingheavy";
    public string HitSound = "impactbodyheavy";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Reach", ref Reach);
        Properties.ParseFloat("Width", ref Width);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseFloat("HitDamage", ref HitDamage);
        Properties.ParseFloat("Knockback", ref Knockback);
        Properties.ParseFloat("PiledriverDamage", ref PiledriverDamage);
        Properties.ParseFloat("BatteringKnockback", ref BatteringKnockback);
        Properties.ParseFloat("BatteringReach", ref BatteringReach);
        Properties.ParseString("RamPart", ref RamPart);
        Properties.ParseFloat("RamStroke", ref RamStroke);
        Properties.ParseString("PunchSound", ref PunchSound);
        Properties.ParseString("HitSound", ref HitSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<RamControllerDEM>();
    }
}

public class RamControllerDEM : TrapControllerDEM
{
    private const float OutTime = 0.09f;
    private const float BackTime = 0.7f;

    private BlockRamDEM ram;
    private TrapPartDEM part;
    private float punchAge = -1f;

    private static readonly List<int> hit = new List<int>();
    private static readonly List<EntityAlive> inFront = new List<EntityAlive>();

    protected override float ActDelay => ram.FireDelay;

    protected override float IdleDelay => 0.2f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        ram = (BlockRamDEM)trap;
        base.Setup(trap, pos);
        part = part ?? TrapPartDEM.Find(transform, ram.RamPart);
    }

    protected override bool Act(World world)
    {
        bool piledriver = Upgraded('A');
        bool battering = Upgraded('B');
        float reach = battering ? ram.BatteringReach : ram.Reach;
        Vector3 center = BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f);
        inFront.Clear();
        foreach (EntityAlive e in Enemies(world, center + Vector3.up, reach + 1.5f))
        {
            Vector3 local = transform.InverseTransformPoint(e.position - Origin.position);
            float y = local.y + 0.5f;
            if (Mathf.Abs(local.x) <= ram.Width * 0.5f && local.z >= 0.2f && local.z <= reach + 0.5f && y > -0.6f
                && y < 1.6f)
            {
                inFront.Add(e);
            }
        }
        if (inFront.Count == 0)
        {
            return false;
        }
        int owner = Owner(world);
        float damage = ram.HitDamage * DamageMult * (piledriver ? ram.PiledriverDamage : 1f);
        float meters = piledriver ? 0f : battering ? ram.BatteringKnockback : ram.Knockback;
        Vector3 forward = Forward;
        hit.Clear();
        foreach (EntityAlive e in inFront)
        {
            Touch(e, false);
            if (Hit(e, damage, EnumDamageTypes.Bashing, forward, owner, 1.5f) && meters > 0f)
            {
                TrapStatusDEM.Knockback(e, forward, meters);
            }
            hit.Add(e.entityId);
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(center + Vector3.up * 0.5f, ram.PunchSound);
        Audio.Manager.BroadcastPlay(center + Vector3.up * 0.5f, ram.HitSound);
        Broadcast(center, hit.ToArray());
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        punchAge = 0f;
    }

    protected override void Update()
    {
        base.Update();
        if (punchAge < 0f || part == null)
        {
            return;
        }
        punchAge += Time.deltaTime;
        float stroke;
        if (punchAge < OutTime)
        {
            stroke = punchAge / OutTime;
        }
        else if (punchAge < OutTime + BackTime)
        {
            stroke = 1f - Mathf.SmoothStep(0f, 1f, (punchAge - OutTime) / BackTime);
        }
        else
        {
            stroke = 0f;
            punchAge = -1f;
        }
        part.Slide(Vector3.forward * (ram.RamStroke * stroke));
    }
}
