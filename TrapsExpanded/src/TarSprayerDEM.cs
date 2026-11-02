using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Tar Sprayer (XML class "TarSprayerDEM, TrapsExpanded"): a paint-sprayer gun on a swivel. Every FireDelay seconds it
/// lobs a glob of tar at the nearest zombie within Range it can reach: HitDamage to every zombie within Splash meters of
/// where it lands, and all of them Tarred for TarSeconds (levels lengthen it). Each glob uses AmmoPerUse tar.
/// Upgrades (level 3): A Sticky Tar (60% slower), B Volatile Tar (Infernos 50% stronger and spreading 5 m).
///
/// The model's Swivel part turns toward the target; globs leave from the gun's nozzle, MuzzleRadius out from the
/// swivel's axis (at MuzzlePivot, in the model's frame) and MuzzleHeight up. XML properties: Range, FireDelay,
/// HitDamage, Splash, TarSeconds, MuzzlePivot, MuzzleRadius, MuzzleHeight, FireSound, SplatSound, and the shared ones.
/// </summary>
public class BlockTarSprayerDEM : BlockTrapDEM
{
    public float Range = 10f;
    public float FireDelay = 2f;
    public float HitDamage = 5f;
    public float Splash = 2f;
    public float TarSeconds = 12f;
    public Vector3 MuzzlePivot = new Vector3(0f, 0f, -0.105f);
    public float MuzzleRadius = 0.314f;
    public float MuzzleHeight = 0.444f;
    public string FireSound = "darttrap_fire";
    public string SplatSound = "vomitimpact";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseFloat("HitDamage", ref HitDamage);
        Properties.ParseFloat("Splash", ref Splash);
        Properties.ParseFloat("TarSeconds", ref TarSeconds);
        if (Properties.Values.ContainsKey("MuzzlePivot"))
        {
            MuzzlePivot = StringParsers.ParseVector3(Properties.Values["MuzzlePivot"]);
        }
        Properties.ParseFloat("MuzzleRadius", ref MuzzleRadius);
        Properties.ParseFloat("MuzzleHeight", ref MuzzleHeight);
        Properties.ParseString("FireSound", ref FireSound);
        Properties.ParseString("SplatSound", ref SplatSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<TarSprayerControllerDEM>();
    }
}

public class TarSprayerControllerDEM : TrapControllerDEM
{
    private BlockTarSprayerDEM sprayer;
    private TrapPartDEM swivel;
    private float yaw;
    private float targetYaw;

    private static readonly List<int> hit = new List<int>();

    protected override float ActDelay => sprayer.FireDelay;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        sprayer = (BlockTarSprayerDEM)trap;
        base.Setup(trap, pos);
        swivel = swivel ?? TrapPartDEM.Find(transform, "Swivel");
    }

    /// <summary>The swivel's axis at the nozzle's height.</summary>
    private Vector3 Axis()
    {
        return transform.TransformPoint(new Vector3(sprayer.MuzzlePivot.x, sprayer.MuzzleHeight, sprayer.MuzzlePivot.z))
            + Origin.position;
    }

    /// <summary>The nozzle with the gun turned toward a point.</summary>
    private Vector3 Muzzle(Vector3 toward)
    {
        return SwivelMuzzle(sprayer.MuzzlePivot, sprayer.MuzzleRadius, sprayer.MuzzleHeight, toward - Axis());
    }

    protected override bool Act(World world)
    {
        if (!HasAmmo)
        {
            Cooldown = 1f;
            return false;
        }
        Vector3 axis = Axis();
        EntityAlive target = null;
        float best = sprayer.Range * sprayer.Range;
        foreach (EntityAlive e in Enemies(world, axis, sprayer.Range))
        {
            Vector3 chest = e.getChestPosition();
            float d = (chest - axis).sqrMagnitude;
            Vector3 from = Muzzle(chest);
            if (d >= best || !Reachable(world, from + (chest - from).normalized * 0.1f, chest))
            {
                continue;
            }
            target = e;
            best = d;
        }
        if (target == null)
        {
            return false;
        }

        UseAmmo(Settings.AmmoPerUse, out _);
        Vector3 origin = Muzzle(target.getChestPosition());
        int owner = Owner(world);
        bool sticky = Upgraded('A');
        bool volatileTar = Upgraded('B');
        float seconds = sprayer.TarSeconds * DurationMult;
        Vector3 impact = target.position + Vector3.up * 0.6f;
        hit.Clear();
        hit.Add(-Mathf.RoundToInt(seconds * 10f));
        hit.Add(target.entityId);
        foreach (EntityAlive e in Enemies(world, impact, sprayer.Splash))
        {
            if ((e.position - target.position).magnitude > sprayer.Splash)
            {
                continue;
            }
            TrapStatusDEM.Tar(e, sticky ? 3 : 1, volatileTar, volatileTar, seconds, owner);
            Touch(e, false);
            Hit(e, sprayer.HitDamage * DamageMult, EnumDamageTypes.Bashing, (e.position - origin).normalized, owner);
            if (e != target)
            {
                hit.Add(e.entityId);
            }
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(origin, sprayer.FireSound);
        Audio.Manager.BroadcastPlay(impact, sprayer.SplatSound);
        Broadcast(origin, hit.ToArray());
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        World world = GameManager.Instance.World;
        if (world == null || ids.Length < 2 || !(world.GetEntity(ids[1]) is EntityAlive target))
        {
            return;
        }
        float seconds = ids[0] < 0 ? -ids[0] / 10f : sprayer.TarSeconds;
        Vector3 to = target.position + Vector3.up * 0.6f;
        Vector3 from = Muzzle(to);
        if (swivel != null)
        {
            targetYaw = Yaw(to - from);
        }
        float dist = Vector3.Distance(from, to);
        ProjectileFxDEM.Launch("TarGlob", from, to, 14f, Mathf.Min(2.5f, dist * 0.18f), "TarSplat", 0f);
        for (int i = 1; i < ids.Length; i++)
        {
            if (world.GetEntity(ids[i]) is EntityAlive e)
            {
                FxDEM.Attach(e, "TarDrip", seconds, 0.6f);
            }
        }
    }

    private float Yaw(Vector3 worldDir)
    {
        Vector3 local = transform.InverseTransformDirection(worldDir);
        return Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
    }

    protected override void Update()
    {
        base.Update();
        if (swivel == null || Mathf.Approximately(yaw, targetYaw))
        {
            return;
        }
        yaw = Mathf.MoveTowardsAngle(yaw, targetYaw, 540f * Time.deltaTime);
        swivel.Turn(Vector3.up, yaw);
    }
}
