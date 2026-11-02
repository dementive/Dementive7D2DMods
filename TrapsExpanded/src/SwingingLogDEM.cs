using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Swinging Log (XML class "SwingingLogDEM, TrapsExpanded"): a spiked log hung from an A-frame, pulled back and held by
/// a tripwire. When a zombie walks into its path it swings through the front: HitDamage (crushing, so frozen zombies
/// shatter) and Knockback meters to every zombie in the swing, then it's pulled back up over RecockSeconds. Each swing
/// wears it (WearPerUse). Upgrades (level 3): A Spiked Log (SpikedDamage times the damage), B Battering Log
/// (BatteringKnockback meters and a BatteringWidth wide swing).
///
/// XML properties: HitDamage, Knockback, RecockSeconds, Width (the swing's width), Reach (how far in front it hits),
/// SpikedDamage, BatteringKnockback, BatteringWidth, SwingSound, HitSound, and the shared ones.
/// </summary>
public class BlockSwingingLogDEM : BlockPlainTrapDEM
{
    public float HitDamage = 35f;
    public float Knockback = 3f;
    public float RecockSeconds = 5f;
    public float Width = 1.2f;
    public float Reach = 1.6f;
    public float SpikedDamage = 1.5f;
    public float BatteringKnockback = 6f;
    public float BatteringWidth = 1.8f;
    public string SwingSound = "SlowSwoosh";
    public string HitSound = "treelogimpact";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("HitDamage", ref HitDamage);
        Properties.ParseFloat("Knockback", ref Knockback);
        Properties.ParseFloat("RecockSeconds", ref RecockSeconds);
        Properties.ParseFloat("Width", ref Width);
        Properties.ParseFloat("Reach", ref Reach);
        Properties.ParseFloat("SpikedDamage", ref SpikedDamage);
        Properties.ParseFloat("BatteringKnockback", ref BatteringKnockback);
        Properties.ParseFloat("BatteringWidth", ref BatteringWidth);
        Properties.ParseString("SwingSound", ref SwingSound);
        Properties.ParseString("HitSound", ref HitSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<SwingingLogControllerDEM>();
    }
}

public class SwingingLogControllerDEM : TrapControllerDEM
{
    /// <summary>The log's angle about the pipe: positive pulls it back, negative swings it forward.</summary>
    private const float CockedAngle = 70f;
    private const float SwingAngle = -60f;
    private const float SwingTime = 0.28f;
    private const float SettleTime = 0.9f;

    private BlockSwingingLogDEM log;
    private TrapPartDEM part;
    private float swingAge = -1f;
    private float recock = 5f;

    private static readonly List<int> hit = new List<int>();
    private static readonly List<EntityAlive> inZone = new List<EntityAlive>();

    protected override float ActDelay => log.RecockSeconds;

    protected override float IdleDelay => 0.2f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        log = (BlockSwingingLogDEM)trap;
        base.Setup(trap, pos);
        // Found once: a reused model is already posed
        part = part ?? TrapPartDEM.Find(transform, "Log");
        recock = log.RecockSeconds;
        Cooldown = 0.5f;
        Pose(CockedAngle);
    }

    protected override bool Act(World world)
    {
        bool battering = Upgraded('B');
        float width = battering ? log.BatteringWidth : log.Width;
        Vector3 center = BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f);
        inZone.Clear();
        foreach (EntityAlive e in Enemies(world, center + Vector3.up, log.Reach + 1.5f))
        {
            // In the model's frame: x across, z ahead, y up from the ground
            Vector3 local = transform.InverseTransformPoint(e.position - Origin.position);
            float y = local.y + 0.5f;
            if (Mathf.Abs(local.x) <= width * 0.5f && local.z >= -0.4f && local.z <= log.Reach && y > -0.5f && y < 2f)
            {
                inZone.Add(e);
            }
        }
        if (inZone.Count == 0)
        {
            return false;
        }

        int owner = Owner(world);
        float damage = log.HitDamage * DamageMult * (Upgraded('A') ? log.SpikedDamage : 1f);
        float meters = battering ? log.BatteringKnockback : log.Knockback;
        Vector3 forward = Forward;
        hit.Clear();
        hit.Add(-Mathf.RoundToInt(ActDelay / TrapLevelsDEM.Speed(Level) * 10f));
        foreach (EntityAlive e in inZone)
        {
            if (Hit(e, damage, EnumDamageTypes.Crushing, forward, owner, 1f))
            {
                TrapStatusDEM.Knockback(e, forward, meters);
            }
            Touch(e, false);
            hit.Add(e.entityId);
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(center + Vector3.up, log.SwingSound);
        Audio.Manager.BroadcastPlay(center + Vector3.up, log.HitSound);
        Broadcast(center, hit.ToArray());
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        recock = ids.Length > 0 && ids[0] < 0 ? -ids[0] / 10f : log.RecockSeconds;
        swingAge = 0f;
    }

    protected override void Update()
    {
        base.Update();
        if (swingAge < 0f || part == null)
        {
            return;
        }
        swingAge += Time.deltaTime;
        float t = swingAge;
        float angle;
        if (t < SwingTime)
        {
            // Released: falls through faster and faster
            float k = t / SwingTime;
            angle = Mathf.Lerp(CockedAngle, SwingAngle, k * k);
        }
        else if (t < SwingTime + SettleTime)
        {
            // Swings back and settles hanging down
            float k = (t - SwingTime) / SettleTime;
            angle = SwingAngle * Mathf.Cos(k * Mathf.PI * 1.5f) * (1f - k);
        }
        else
        {
            // Hauled back up
            float pull = Mathf.Max(0.5f, recock - SwingTime - SettleTime);
            float k = Mathf.Clamp01((t - SwingTime - SettleTime) / pull);
            angle = Mathf.Lerp(0f, CockedAngle, Mathf.SmoothStep(0f, 1f, k));
            if (k >= 1f)
            {
                swingAge = -1f;
            }
        }
        Pose(angle);
    }

    private void Pose(float angle)
    {
        part?.Turn(Vector3.right, angle);
    }
}
