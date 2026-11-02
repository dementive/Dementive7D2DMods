using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Bear Trap (XML class "BearTrapDEM, TrapsExpanded"): a steel jaw trap. It snaps on the first zombie to step on it:
/// HitDamage and held in place for HoldSeconds (big zombies BigHoldSeconds). Then it stays sprung until re-armed from its
/// radial menu. Upgrades (level 3): A Spring Loader (re-arms itself after RearmSeconds), B Heavy Jaws (holds for
/// HeavyHoldSeconds, big zombies too).
///
/// The block's state bit is set while sprung, so a newly placed trap is armed. XML properties: Radius, HitDamage,
/// HoldSeconds, BigHoldSeconds, HeavyHoldSeconds, RearmSeconds, SnapSound, RearmSound, and the shared ones.
/// </summary>
public class BlockBearTrapDEM : BlockPlainTrapDEM
{
    public const string CmdRearm = "dem_rearm";

    public float Radius = 0.55f;
    public float HitDamage = 50f;
    public float HoldSeconds = 3f;
    public float BigHoldSeconds = 1f;
    public float HeavyHoldSeconds = 5f;
    public float RearmSeconds = 15f;
    public string SnapSound = "trapdoor_trigger";
    public string RearmSound = "spring_place";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Radius", ref Radius);
        Properties.ParseFloat("HitDamage", ref HitDamage);
        Properties.ParseFloat("HoldSeconds", ref HoldSeconds);
        Properties.ParseFloat("BigHoldSeconds", ref BigHoldSeconds);
        Properties.ParseFloat("HeavyHoldSeconds", ref HeavyHoldSeconds);
        Properties.ParseFloat("RearmSeconds", ref RearmSeconds);
        Properties.ParseString("SnapSound", ref SnapSound);
        Properties.ParseString("RearmSound", ref RearmSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<BearTrapControllerDEM>();
    }

    public static bool IsSprung(BlockValue bv)
    {
        return GetState(bv);
    }

    public override void ExtraCommands(List<BlockActivationCommand> commands, WorldBase world, BlockValue blockValue,
        Vector3i pos, TrapRecordDEM record)
    {
        commands.Add(new BlockActivationCommand(CmdRearm, "wrench", IsSprung(blockValue)));
    }

    public override bool ServerCommand(World world, Vector3i pos, string command)
    {
        if (command != CmdRearm)
        {
            return false;
        }
        if (IsSprung(world.GetBlock(pos)))
        {
            SetState(world, pos, false);
            Audio.Manager.BroadcastPlay(pos.ToVector3() + Vector3.one * 0.5f, RearmSound);
        }
        return true;
    }

    public override string StateText(WorldBase world, BlockValue blockValue, Vector3i pos, TrapRecordDEM record)
    {
        return Localization.Get(IsSprung(blockValue) ? "dem_trapSprung" : "dem_trapArmed");
    }
}

public class BearTrapControllerDEM : TrapControllerDEM
{
    private const float CloseTime = 0.08f;
    private const float OpenTime = 0.6f;

    private BlockBearTrapDEM bear;
    private TrapPartDEM jawA;
    private TrapPartDEM jawB;
    private float sprungAt = -1f;

    // 0 open, 1 closed
    private float shown;
    private float stateRefresh;
    private bool shownSprung;

    protected override float ActDelay => 0.15f;

    protected override float IdleDelay => 0.15f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        bear = (BlockBearTrapDEM)trap;
        base.Setup(trap, pos);
        jawA = jawA ?? TrapPartDEM.Find(transform, "JawA");
        jawB = jawB ?? TrapPartDEM.Find(transform, "JawB");
        World world = GameManager.Instance.World;
        shownSprung = world != null && BlockBearTrapDEM.IsSprung(world.GetBlock(pos));
        shown = shownSprung ? 1f : 0f;
        Pose(shown);
    }

    protected override bool Act(World world)
    {
        BlockValue bv = world.GetBlock(BlockPos);
        if (BlockBearTrapDEM.IsSprung(bv))
        {
            if (sprungAt < 0f)
            {
                sprungAt = Time.time;
            }
            if (Upgraded('A') && Time.time - sprungAt >= bear.RearmSeconds / TrapLevelsDEM.Speed(Level))
            {
                BlockPlainTrapDEM.SetState(world, BlockPos, false);
                Audio.Manager.BroadcastPlay(BlockPos.ToVector3() + Vector3.one * 0.5f, bear.RearmSound);
            }
            Cooldown = 0.5f;
            return false;
        }
        sprungAt = -1f;

        Vector3 center = BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f);
        EntityAlive victim = null;
        float best = bear.Radius;
        foreach (EntityAlive e in Enemies(world, center + Vector3.up * 0.5f, 1.5f))
        {
            Vector3 flat = e.position - center;
            float dy = flat.y;
            flat.y = 0f;
            float d = flat.magnitude;
            if (d <= best && dy > -0.4f && dy < 0.6f)
            {
                victim = e;
                best = d;
            }
        }
        if (victim == null)
        {
            return false;
        }

        int owner = Owner(world);
        bool heavy = Upgraded('B');
        bool big = TrapStatusDEM.IsBig(victim);
        if (Hit(victim, bear.HitDamage * DamageMult, EnumDamageTypes.Piercing, Vector3.down, owner, 0.1f))
        {
            float hold = heavy ? bear.HeavyHoldSeconds : big ? bear.BigHoldSeconds : bear.HoldSeconds;
            victim.Buffs.AddBuff(TrapStatusDEM.Held, owner, true, false, hold);
        }
        Touch(victim, false);
        BlockPlainTrapDEM.SetState(world, BlockPos, true);
        sprungAt = Time.time;
        Audio.Manager.BroadcastPlay(center, bear.SnapSound);
        Broadcast(center, new[] { victim.entityId });
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        // Snap shut now rather than at the next state check
        shownSprung = true;
        World world = GameManager.Instance.World;
        if (world != null && ids.Length > 0 && world.GetEntity(ids[0]) is EntityAlive e)
        {
            FxDEM.Vanilla("p_impact_metal_on_organic", e.position, Quaternion.identity, 2f);
        }
    }

    protected override void Update()
    {
        base.Update();
        stateRefresh -= Time.deltaTime;
        if (stateRefresh <= 0f)
        {
            stateRefresh = 0.25f;
            World world = GameManager.Instance.World;
            if (world != null)
            {
                shownSprung = BlockBearTrapDEM.IsSprung(world.GetBlock(BlockPos));
            }
        }
        float target = shownSprung ? 1f : 0f;
        if (!Mathf.Approximately(shown, target))
        {
            shown = Mathf.MoveTowards(shown, target, Time.deltaTime / (shownSprung ? CloseTime : OpenTime));
            Pose(shown);
        }
    }

    /// <summary>The jaws turn up about the hinge and meet in the middle.</summary>
    private void Pose(float closed)
    {
        jawA?.Turn(Vector3.right, -90f * closed);
        jawB?.Turn(Vector3.right, 90f * closed);
    }
}
