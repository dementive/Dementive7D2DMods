using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Burn Barrel (XML class "BurnBarrelDEM, TrapsExpanded"): a fire in a drum, lit and put out from its radial menu.
/// While lit it burns FuelSeconds per wood loaded (it goes out when the wood runs out), lights the area at night, and
/// sets every zombie within Radius on fire for BurnSeconds (tarred zombies go up as Infernos; soaked ones won't light).
/// Upgrades (level 3): A Bellows (BellowsRadius), B Slow Burn (SlowBurnFactor times longer per wood).
///
/// XML properties: Radius, BellowsRadius, BurnSeconds, FuelSeconds, SlowBurnFactor, LightSound, and the shared ones.
/// </summary>
public class BlockBurnBarrelDEM : BlockPlainTrapDEM
{
    public const string CmdLight = "dem_light";
    public const string CmdDouse = "dem_douse";

    public float Radius = 1.5f;
    public float BellowsRadius = 2f;
    public float BurnSeconds = 8f;
    public float FuelSeconds = 20f;
    public float SlowBurnFactor = 3f;
    public string LightSound = "torch_swoosh";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Radius", ref Radius);
        Properties.ParseFloat("BellowsRadius", ref BellowsRadius);
        Properties.ParseFloat("BurnSeconds", ref BurnSeconds);
        Properties.ParseFloat("FuelSeconds", ref FuelSeconds);
        Properties.ParseFloat("SlowBurnFactor", ref SlowBurnFactor);
        Properties.ParseString("LightSound", ref LightSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<BurnBarrelControllerDEM>();
    }

    public override void ExtraCommands(List<BlockActivationCommand> commands, WorldBase world, BlockValue blockValue,
        Vector3i pos, TrapRecordDEM record)
    {
        if (GetState(blockValue))
        {
            commands.Add(new BlockActivationCommand(CmdDouse, "campfire", true));
        }
        else
        {
            commands.Add(new BlockActivationCommand(CmdLight, "campfire", record != null && record.AmmoTotal > 0));
        }
    }

    public override bool ServerCommand(World world, Vector3i pos, string command)
    {
        if (command == CmdLight)
        {
            TrapRecordDEM rec = TrapStoreDEM.Get(pos, Settings.Name);
            if (rec.AmmoTotal > 0)
            {
                SetState(world, pos, true);
                Audio.Manager.BroadcastPlay(pos.ToVector3() + Vector3.one * 0.5f, LightSound);
            }
            return true;
        }
        if (command == CmdDouse)
        {
            SetState(world, pos, false);
            return true;
        }
        return false;
    }

    public override string StateText(WorldBase world, BlockValue blockValue, Vector3i pos, TrapRecordDEM record)
    {
        return Localization.Get(GetState(blockValue) ? "dem_trapLit" : "dem_trapUnlit");
    }
}

public class BurnBarrelControllerDEM : TrapControllerDEM
{
    private BlockBurnBarrelDEM barrel;
    private Transform firePoint;
    private float fuelLeft = -1f;
    private float lastTick;

    // Visuals
    private bool shownLit;
    private float stateRefresh;
    private Transform fire;
    private Light glow;
    private Renderer[] glowRenderers;
    private MaterialPropertyBlock props;

    protected override float ActDelay => 0.5f;

    protected override float IdleDelay => 0.5f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        barrel = (BlockBurnBarrelDEM)trap;
        base.Setup(trap, pos);
        firePoint = FindDeep(transform, "FirePoint");
        glowRenderers = GetComponentsInChildren<MeshRenderer>(true);
        shownLit = false;
        stateRefresh = 0f;
        lastTick = Time.time;
    }

    protected override bool Act(World world)
    {
        float now = Time.time;
        float dt = Mathf.Clamp(now - lastTick, 0f, 2f);
        lastTick = now;
        BlockValue bv = world.GetBlock(BlockPos);
        if (!BlockPlainTrapDEM.GetState(bv))
        {
            return false;
        }
        // Burning through the wood (fuelLeft is the current piece's seconds)
        fuelLeft -= dt;
        if (fuelLeft <= 0f)
        {
            if (!UseAmmo(1f, out _))
            {
                BlockPlainTrapDEM.SetState(world, BlockPos, false);
                return false;
            }
            fuelLeft = barrel.FuelSeconds * (Upgraded('B') ? barrel.SlowBurnFactor : 1f);
        }

        float radius = Upgraded('A') ? barrel.BellowsRadius : barrel.Radius;
        Vector3 center = BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f);
        int owner = Owner(world);
        float seconds = barrel.BurnSeconds * DamageMult;
        foreach (EntityAlive e in Enemies(world, center + Vector3.up, radius + 1f))
        {
            Vector3 flat = e.position - center;
            float dy = flat.y;
            flat.y = 0f;
            if (flat.magnitude > radius || dy < -1f || dy > 1.5f)
            {
                continue;
            }
            if (e.Buffs.HasBuff(TrapStatusDEM.Burning) && !TrapStatusDEM.IsTarred(e))
            {
                continue;
            }
            if (TrapStatusDEM.Ignite(e, seconds, owner))
            {
                Touch(e, true);
            }
        }
        return true;
    }

    public override void PlayFx(int[] ids)
    {
    }

    protected override void Update()
    {
        base.Update();
        stateRefresh -= Time.deltaTime;
        if (stateRefresh <= 0f)
        {
            stateRefresh = 0.3f;
            World world = GameManager.Instance.World;
            bool lit = world != null && BlockPlainTrapDEM.GetState(world.GetBlock(BlockPos));
            if (lit != shownLit)
            {
                shownLit = lit;
                ShowFire(lit);
            }
        }
        if (glow != null && shownLit)
        {
            glow.intensity = 1.6f + 0.5f * Mathf.PerlinNoise(Time.time * 6f, BlockPos.z * 0.31f);
        }
    }

    protected override void OnDisable()
    {
        base.OnDisable();
        if (fire != null)
        {
            Destroy(fire.gameObject);
            fire = null;
        }
        shownLit = false;
    }

    /// <summary>Flames out of the top, a flickering light and the holes glowing while lit.</summary>
    private void ShowFire(bool lit)
    {
        if (GameManager.IsDedicatedServer)
        {
            return;
        }
        Transform at = firePoint != null ? firePoint : transform;
        if (lit && fire == null)
        {
            Vector3 world = at.position + Origin.position;
            fire = FxDEM.Vanilla("p_burning_barrel", world, Quaternion.identity, 0f, at);
            if (fire == null)
            {
                GameObject own = FxDEM.Spawn("BarrelFire", world, Quaternion.identity, float.MaxValue, at);
                fire = own != null ? own.transform : null;
            }
        }
        else if (!lit && fire != null)
        {
            Destroy(fire.gameObject);
            fire = null;
        }
        if (glow == null)
        {
            GameObject l = new GameObject("BarrelGlow");
            l.transform.SetParent(at, false);
            l.transform.localPosition = Vector3.up * 0.3f;
            glow = l.AddComponent<Light>();
            glow.type = LightType.Point;
            glow.color = new Color(1f, 0.55f, 0.2f);
            glow.range = 9f;
            glow.shadows = LightShadows.None;
        }
        glow.enabled = lit;
        if (props == null)
        {
            props = new MaterialPropertyBlock();
        }
        Color c = lit ? new Color(3f, 3f, 3f) : new Color(0.03f, 0.03f, 0.03f);
        foreach (Renderer r in glowRenderers)
        {
            if (r == null)
            {
                continue;
            }
            r.GetPropertyBlock(props);
            props.SetColor("_EmissionColor", c);
            r.SetPropertyBlock(props);
        }
    }
}
