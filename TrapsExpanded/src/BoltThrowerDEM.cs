using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Bolt Thrower (XML class "BoltThrowerDEM, TrapsExpanded"): a ballista from a car leaf spring and a winch, for the
/// big ones. Every FireDelay seconds it shoots a loaded rebar bolt at the zombie within Range with the most health that
/// it can reach: HitDamage (piercing) and a Knockdown meters knockback. Upgrades (level 3): A Skewer (the bolt goes on
/// through up to SkewerCount zombies in line), B Explosive Bolts (a SplashRadius blast for SplashDamage where it hits,
/// which doesn't damage blocks).
///
/// The model's Turret part turns toward the target; the bolt leaves from its tip, MuzzleRadius out from the turret's
/// axis (the model's center) and MuzzleHeight up. XML properties: Range, FireDelay, HitDamage, Knockdown, SkewerCount,
/// SkewerWidth, SplashRadius, SplashDamage, ExplosionItem (whose explosion effect the blast uses), MuzzleRadius,
/// MuzzleHeight, FireSound, and the shared ones.
/// </summary>
public class BlockBoltThrowerDEM : BlockTrapDEM
{
    public float Range = 30f;
    public float FireDelay = 3f;
    public float HitDamage = 800f;
    public float Knockdown = 1.5f;
    public int SkewerCount = 3;
    public float SkewerWidth = 0.8f;
    public float SplashRadius = 3f;
    public float SplashDamage = 150f;
    public string ExplosionItem = "ammoArrowExploding";
    public float MuzzleRadius = 0.443f;
    public float MuzzleHeight = 0.209f;
    public string FireSound = "crossbow2_fire";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseFloat("HitDamage", ref HitDamage);
        Properties.ParseFloat("Knockdown", ref Knockdown);
        Properties.ParseInt("SkewerCount", ref SkewerCount);
        Properties.ParseFloat("SkewerWidth", ref SkewerWidth);
        Properties.ParseFloat("SplashRadius", ref SplashRadius);
        Properties.ParseFloat("SplashDamage", ref SplashDamage);
        Properties.ParseString("ExplosionItem", ref ExplosionItem);
        Properties.ParseFloat("MuzzleRadius", ref MuzzleRadius);
        Properties.ParseFloat("MuzzleHeight", ref MuzzleHeight);
        Properties.ParseString("FireSound", ref FireSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<BoltThrowerControllerDEM>();
    }
}

public class BoltThrowerControllerDEM : TrapControllerDEM
{
    private BlockBoltThrowerDEM thrower;
    private TrapPartDEM turret;
    private float yaw;
    private float targetYaw;

    private static readonly List<int> hit = new List<int>();
    private static readonly List<KeyValuePair<float, EntityAlive>> line = new List<KeyValuePair<float, EntityAlive>>();

    protected override float ActDelay => thrower.FireDelay;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        thrower = (BlockBoltThrowerDEM)trap;
        base.Setup(trap, pos);
        turret = turret ?? TrapPartDEM.Find(transform, "Turret");
    }

    /// <summary>The turret's axis at the bolt's height (where targets are judged from).</summary>
    private Vector3 Origin3()
    {
        return transform.TransformPoint(new Vector3(0f, thrower.MuzzleHeight, 0f)) + Origin.position;
    }

    /// <summary>The loaded bolt's tip with the turret turned toward a point.</summary>
    private Vector3 Muzzle(Vector3 toward)
    {
        return SwivelMuzzle(Vector3.zero, thrower.MuzzleRadius, thrower.MuzzleHeight, toward - Origin3());
    }

    protected override bool Act(World world)
    {
        if (!HasAmmo)
        {
            Cooldown = 1f;
            return false;
        }
        Vector3 origin = Origin3();
        EntityAlive target = null;
        float most = 0f;
        foreach (EntityAlive e in Enemies(world, origin, thrower.Range))
        {
            Vector3 chest = e.getChestPosition();
            Vector3 to = chest - origin;
            if (to.sqrMagnitude > thrower.Range * thrower.Range || e.Health <= most)
            {
                continue;
            }
            if (!Reachable(world, origin + to.normalized * 0.5f, chest))
            {
                continue;
            }
            target = e;
            most = e.Health;
        }
        if (target == null)
        {
            return false;
        }

        UseAmmo(1f, out _);
        int owner = Owner(world);
        bool skewer = Upgraded('A');
        bool explosive = Upgraded('B');
        Vector3 aim = target.getChestPosition();
        Vector3 dir = (aim - origin).normalized;
        float damage = thrower.HitDamage * DamageMult;
        hit.Clear();
        hit.Add(explosive ? -2 : -1);

        // The target, and with Skewer the zombies in line behind it
        line.Clear();
        line.Add(new KeyValuePair<float, EntityAlive>(Vector3.Dot(aim - origin, dir), target));
        if (skewer)
        {
            float reach = thrower.Range;
            foreach (EntityAlive e in Enemies(world, origin + dir * (reach * 0.5f), reach * 0.5f + 1f))
            {
                if (e == target)
                {
                    continue;
                }
                Vector3 to = e.getChestPosition() - origin;
                float along = Vector3.Dot(to, dir);
                if (along < 0.5f || along > reach || (to - dir * along).magnitude > thrower.SkewerWidth)
                {
                    continue;
                }
                line.Add(new KeyValuePair<float, EntityAlive>(along, e));
            }
            line.Sort((a, b) => a.Key.CompareTo(b.Key));
            if (line.Count > thrower.SkewerCount)
            {
                line.RemoveRange(thrower.SkewerCount, line.Count - thrower.SkewerCount);
            }
        }
        Vector3 end = aim;
        foreach (KeyValuePair<float, EntityAlive> kv in line)
        {
            EntityAlive e = kv.Value;
            Touch(e, false);
            if (Hit(e, damage, EnumDamageTypes.Piercing, dir, owner, 2f))
            {
                TrapStatusDEM.Knockback(e, dir, thrower.Knockdown);
            }
            hit.Add(e.entityId);
            end = e.getChestPosition();
        }
        if (explosive)
        {
            Explode(world, aim, owner);
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(origin, thrower.FireSound);
        // Where the bolt ends up, for the clients' streak
        hit.Add(Mathf.RoundToInt(end.x * 10f));
        hit.Add(Mathf.RoundToInt(end.y * 10f));
        hit.Add(Mathf.RoundToInt(end.z * 10f));
        Broadcast(origin, hit.ToArray());
        return true;
    }

    /// <summary>Explosive Bolts: the game's own explosion (its effect from ExplosionItem) for SplashDamage within
    /// SplashRadius, leaving the blocks alone.</summary>
    private void Explode(World world, Vector3 at, int owner)
    {
        ItemClass ic = ItemClass.GetItemClass(thrower.ExplosionItem);
        if (ic == null)
        {
            return;
        }
        ExplosionData data = new ExplosionData(ic.Properties, ic.Effects)
        {
            EntityDamage = thrower.SplashDamage * DamageMult,
            EntityRadius = Mathf.RoundToInt(thrower.SplashRadius),
            BlockDamage = 0f,
            BlockRadius = 0f
        };
        foreach (EntityAlive e in Enemies(world, at, thrower.SplashRadius + 0.5f))
        {
            Touch(e, false);
        }
        TrapKillsDEM.Begin(BlockPos, Settings.Name, false);
        try
        {
            GameManager.Instance.ExplosionServer(at, World.worldToBlockPos(at), Quaternion.identity, data, owner, 0f,
                false);
        }
        finally
        {
            TrapKillsDEM.End();
        }
    }

    public override void PlayFx(int[] ids)
    {
        if (ids.Length < 5)
        {
            return;
        }
        int n = ids.Length;
        Vector3 end = new Vector3(ids[n - 3], ids[n - 2], ids[n - 1]) / 10f;
        Vector3 from = Muzzle(end);
        targetYaw = Yaw(end - from);
        ProjectileFxDEM.Launch("BoltFx", from, end, 70f, 0f, null, 4f);
    }

    private float Yaw(Vector3 worldDir)
    {
        Vector3 local = transform.InverseTransformDirection(worldDir);
        return Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
    }

    protected override void Update()
    {
        base.Update();
        if (turret == null || Mathf.Approximately(yaw, targetYaw))
        {
            return;
        }
        yaw = Mathf.MoveTowardsAngle(yaw, targetYaw, 720f * Time.deltaTime);
        turret.Turn(Vector3.up, yaw);
    }
}
