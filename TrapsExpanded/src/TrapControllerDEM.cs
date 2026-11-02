using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Base for the component on each trap's model. On the server it calls Act whenever the trap is on (powered, or always
/// for unpowered traps), isn't worn out and its cooldown is up; Act does the trap's work and reports the entities
/// involved with Broadcast, which plays the trap's effects here and on nearby clients (PlayFx). Every game that draws
/// the trap also runs the power lamp: lit while powered, blinking when worn out.
///
/// Levels (from the trap's kills) make it hit harder (DamageMult) and act faster; an Overcharger nearby makes a powered
/// trap act faster still and wear faster. Damage goes through Hit so kills are credited to the trap.
/// </summary>
public abstract class TrapControllerDEM : MonoBehaviour
{
    public bool IsOn;

    protected ITrapDEM Trap;
    protected Block TrapBlock;
    protected TrapSettingsDEM Settings;
    protected Vector3i BlockPos;
    protected float Cooldown;

    private Renderer[] renderers;
    private MaterialPropertyBlock props;
    private float lampRefresh;
    private float wearDebt;
    private float overchargeRefresh;
    private float overSpeed = 1f;
    private float overWear = 1f;

    protected static readonly List<Entity> Found = new List<Entity>();

    /// <summary>Every trap controller whose model is loaded here (Overchargers and Salvage Hoppers look for each
    /// other through it).</summary>
    public static readonly List<TrapControllerDEM> Active = new List<TrapControllerDEM>();

    /// <summary>Seconds between uses at level 1.</summary>
    protected abstract float ActDelay { get; }

    /// <summary>Server: one use of the trap. Returns false when there was nothing to act on (it tries again
    /// shortly).</summary>
    protected abstract bool Act(World world);

    /// <summary>Everyone: the effects of one use, with the entities it involved.</summary>
    public abstract void PlayFx(int[] ids);

    /// <summary>Whether the power lamp and the Overcharger apply (powered traps).</summary>
    protected bool Powered => Trap is BlockTrapDEM;

    public bool IsPoweredTrap => Trap is BlockTrapDEM;

    public Vector3i Position => BlockPos;

    public string BlockName => Settings?.Name;

    public virtual void Setup(ITrapDEM trap, Vector3i pos)
    {
        Trap = trap;
        TrapBlock = trap as Block;
        Settings = trap.Settings;
        BlockPos = pos;
        renderers = GetComponentsInChildren<MeshRenderer>(true);
        lampRefresh = 0f;
        overchargeRefresh = 0f;
        // Spread neighbouring traps out instead of firing in lockstep
        Cooldown = Random.Range(0.1f, ActDelay);
        if (!Active.Contains(this))
        {
            Active.Add(this);
        }
    }

    protected virtual void OnDestroy()
    {
        Active.Remove(this);
    }

    /// <summary>A model put away (its chunk unloaded) stops counting for Overchargers and Salvage Hoppers until it's
    /// set up again.</summary>
    protected virtual void OnDisable()
    {
        Active.Remove(this);
        // The pool may hand this model to another block; it acts again only once Setup runs for it
        Trap = null;
    }

    protected virtual void Update()
    {
        if (Trap == null)
        {
            return;
        }
        UpdateLamp(Time.deltaTime);
        if (!IsOn || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        Cooldown -= Time.deltaTime;
        if (Cooldown > 0f)
        {
            return;
        }
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return;
        }
        if (WornOut(world))
        {
            Cooldown = 1f;
            return;
        }
        Cooldown = 0f;
        if (Act(world))
        {
            Cooldown = ActDelay / SpeedMult(world);
        }
        else if (Cooldown <= 0f)
        {
            // Act may set a longer wait itself (out of ammo, unlit)
            Cooldown = IdleDelay;
        }
    }

    /// <summary>How soon to look again after a use with nothing to act on.</summary>
    protected virtual float IdleDelay => 0.25f;

    protected bool WornOut(World world)
    {
        return world != null && TrapModelDEM.IsWornOut(TrapBlock, Settings, world.GetBlock(BlockPos));
    }

    // ------------------------------------------------------------------ records, levels, upgrades

    private static readonly TrapRecordDEM clientRecord = new TrapRecordDEM();

    /// <summary>Server: this trap's record (kills, upgrade, ammo). Clients get a blank one: they only draw.</summary>
    protected TrapRecordDEM Record => TrapStoreDEM.IsServer ? TrapStoreDEM.Get(BlockPos, Settings.Name) : clientRecord;

    protected int Level => Record.Level;

    /// <summary>Server: whether the owner picked this upgrade ('A' or 'B').</summary>
    protected bool Upgraded(char upgrade)
    {
        return Record.Has(upgrade);
    }

    /// <summary>Damage multiplier from the trap's level.</summary>
    protected float DamageMult => Settings.StatusTrap ? 1f : TrapLevelsDEM.Damage(Level);

    /// <summary>Status duration multiplier from the trap's level (status traps).</summary>
    protected float DurationMult => Settings.StatusTrap ? TrapLevelsDEM.Duration(Level) : 1f;

    private float SpeedMult(World world)
    {
        RefreshOvercharge(world);
        return TrapLevelsDEM.Speed(Level) * overSpeed;
    }

    /// <summary>Overchargers within range make powered traps faster and wear them faster (the strongest one
    /// counts).</summary>
    private void RefreshOvercharge(World world)
    {
        if (Time.time < overchargeRefresh)
        {
            return;
        }
        overchargeRefresh = Time.time + 2f;
        overSpeed = 1f;
        overWear = 1f;
        if (!Powered || this is OverchargerControllerDEM)
        {
            return;
        }
        Vector3 here = BlockPos.ToVector3();
        foreach (TrapControllerDEM c in Active)
        {
            if (!(c is OverchargerControllerDEM o) || !o.IsOn || o.WornOut(world))
            {
                continue;
            }
            o.Boost(out float range, out float speed, out float wear);
            if ((o.BlockPos.ToVector3() - here).sqrMagnitude <= range * range && speed > overSpeed)
            {
                overSpeed = speed;
                overWear = wear;
            }
        }
    }

    /// <summary>Server: uses one shot (or a fraction, for fuel) of the loaded ammo. False when empty.</summary>
    protected bool UseAmmo(float amount, out string item)
    {
        bool used = Record.UseAmmo(amount, out item);
        if (used)
        {
            TrapStoreDEM.Changed(BlockPos);
        }
        return used;
    }

    /// <summary>Server: whether any ammo is loaded.</summary>
    protected bool HasAmmo => Record.AmmoTotal > 0;

    // ------------------------------------------------------------------ helpers

    /// <summary>Each use wears the trap a little (block damage, repaired like any block), stopping short of
    /// breaking it.</summary>
    protected void Wear(World world, float uses = 1f)
    {
        if (Settings.WearPerUse <= 0)
        {
            return;
        }
        wearDebt += Settings.WearPerUse * uses * overWear;
        int add = Mathf.FloorToInt(wearDebt);
        if (add <= 0)
        {
            return;
        }
        wearDebt -= add;
        BlockValue bv = world.GetBlock(BlockPos);
        if (bv.Block != TrapBlock)
        {
            return;
        }
        int damage = Mathf.Min(bv.damage + add, TrapBlock.MaxDamage - 1);
        if (damage == bv.damage)
        {
            return;
        }
        bv.damage = damage;
        world.SetBlockRPC(BlockPos, bv);
    }

    /// <summary>The player credited with the trap's damage and kills (the placer), or -1.</summary>
    protected int Owner(World world)
    {
        if (world.GetTileEntity(BlockPos) is TileEntityPoweredMeleeTrap te && te.OwnerEntityID != -1)
        {
            return te.OwnerEntityID;
        }
        return Record.Owner;
    }

    /// <summary>Server: damages a zombie as this trap (credited to the owner, kills counted for the trap).</summary>
    protected bool Hit(EntityAlive target, float damage, EnumDamageTypes type, Vector3 dir, int owner,
        float impulse = 0.2f)
    {
        TrapKillsDEM.Begin(BlockPos, Settings.Name, TrapStatusDEM.IsFire(type));
        try
        {
            target.DamageEntity(new DamageSourceEntity(EnumDamageSource.External, type, owner, dir),
                Mathf.Max(1, Mathf.RoundToInt(damage)), false, impulse);
        }
        finally
        {
            TrapKillsDEM.End();
        }
        return target.IsAlive();
    }

    /// <summary>Server: marks a zombie as touched by this trap (a status or fire it set), so a kill by that soon
    /// after counts for the trap.</summary>
    protected void Touch(EntityAlive target, bool fire)
    {
        TrapKillsDEM.Touch(target, BlockPos, Settings.Name, fire);
    }

    /// <summary>Server: plays the effects here (unless dedicated) and on clients within 96 m.</summary>
    protected void Broadcast(Vector3 origin, int[] ids)
    {
        if (!GameManager.IsDedicatedServer)
        {
            PlayFx(ids);
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageTrapFxDEM>().Setup(BlockPos, ids),
            _entitiesInRangeOfWorldPos: origin, _range: 96);
    }

    /// <summary>Living enemies (zombies and hostile animals) whose bounds center within range of a point.</summary>
    protected static IEnumerable<EntityAlive> Enemies(World world, Vector3 center, float range)
    {
        Found.Clear();
        world.GetEntitiesInBounds(typeof(EntityEnemy), new Bounds(center, Vector3.one * (range * 2f)), Found);
        // Copied, since callers may damage (and kill) entities while going through them
        List<EntityAlive> alive = new List<EntityAlive>(Found.Count);
        foreach (Entity entity in Found)
        {
            if (entity is EntityAlive a && a.IsAlive())
            {
                alive.Add(a);
            }
        }
        return alive;
    }

    /// <summary>True when no block or terrain is between the points (bodies in the way don't block).</summary>
    protected static bool Reachable(World world, Vector3 from, Vector3 to)
    {
        Vector3 d = to - from;
        float dist = d.magnitude;
        if (dist < 0.05f)
        {
            return true;
        }
        // Same masks the vanilla turrets use for their line of sight
        if (!Voxel.Raycast(world, new Ray(from, d / dist), dist, unchecked((int)0xdfe34ff3), 8, 0f))
        {
            return true;
        }
        WorldRayHitInfo hit = Voxel.voxelRayHitInfo;
        if (hit.tag != null && hit.tag.StartsWith("E_"))
        {
            return true;
        }
        return Mathf.Sqrt(hit.hit.distanceSq) >= dist - 0.3f;
    }

    /// <summary>World-space point of a model transform (or the fallback, relative to the block's bottom
    /// center).</summary>
    protected Vector3 WorldPoint(Transform t, Vector3 fallback)
    {
        if (t != null)
        {
            return t.position + Origin.position;
        }
        return BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f) + transform.rotation * fallback;
    }

    /// <summary>
    /// Where a swivelling gun's muzzle is when it's turned toward `worldDir`: `radius` out from the swivel's vertical
    /// axis (at `pivot`, in the model's frame) and `height` up, in the model's frame. Worked out instead of read from
    /// a point on the moving part, because Blender's FBX export misplaces empties parented to a separated part.
    /// </summary>
    protected Vector3 SwivelMuzzle(Vector3 pivot, float radius, float height, Vector3 worldDir)
    {
        Vector3 axis = transform.TransformPoint(new Vector3(pivot.x, height, pivot.z)) + Origin.position;
        Vector3 flat = worldDir;
        flat.y = 0f;
        flat = flat.sqrMagnitude > 0.0001f ? flat.normalized : Forward;
        return axis + flat * radius;
    }

    /// <summary>The flat direction the trap faces (its model's forward).</summary>
    protected Vector3 Forward
    {
        get
        {
            Vector3 f = transform.forward;
            f.y = 0f;
            return f.sqrMagnitude > 0.0001f ? f.normalized : Vector3.forward;
        }
    }

    /// <summary>The red power lamp is lit while the trap has power and blinks when it's worn out. Re-applied now
    /// and then in case the game resets the renderers' property blocks (it sets block damage and tint through
    /// them).</summary>
    private void UpdateLamp(float dt)
    {
        lampRefresh -= dt;
        if (lampRefresh > 0f || renderers == null || !Powered)
        {
            return;
        }
        lampRefresh = 0.5f;
        if (props == null)
        {
            props = new MaterialPropertyBlock();
        }
        bool lit = IsOn && (!WornOut(GameManager.Instance.World) || Mathf.FloorToInt(Time.time * 2f) % 2 == 0);
        Color color = lit ? new Color(2.5f, 2.5f, 2.5f) : new Color(0.02f, 0.02f, 0.02f);
        foreach (Renderer r in renderers)
        {
            if (r == null)
            {
                continue;
            }
            r.GetPropertyBlock(props);
            props.SetColor("_EmissionColor", color);
            r.SetPropertyBlock(props);
        }
    }

    public static Transform FindDeep(Transform root, string name)
    {
        if (root.name == name)
        {
            return root;
        }
        foreach (Transform child in root)
        {
            Transform found = FindDeep(child, name);
            if (found != null)
            {
                return found;
            }
        }
        return null;
    }
}

/// <summary>
/// A moving part of a trap's model (a log, a jaw, a swivel), posed relative to the model's root so it works however
/// the block is turned and whatever rotation the FBX import gave the meshes. Its origin is the point it turns about.
/// In the root's frame +Z is the trap's front, +Y up.
/// </summary>
public class TrapPartDEM
{
    public readonly Transform T;
    private readonly Transform root;
    private readonly Quaternion restOffset;
    private readonly Vector3 restPos;

    private TrapPartDEM(Transform root, Transform part)
    {
        this.root = root;
        T = part;
        restOffset = Quaternion.Inverse(root.rotation) * part.rotation;
        restPos = root.InverseTransformPoint(part.position);
    }

    /// <summary>The named part under the model, or null if the model doesn't have it.</summary>
    public static TrapPartDEM Find(Transform root, string name)
    {
        Transform t = TrapControllerDEM.FindDeep(root, name);
        return t != null ? new TrapPartDEM(root, t) : null;
    }

    /// <summary>Turns the part `angle` degrees about one of the root's axes, from its rest pose.</summary>
    public void Turn(Vector3 axis, float angle)
    {
        T.rotation = root.rotation * Quaternion.AngleAxis(angle, axis) * restOffset;
    }

    /// <summary>Turns the part about the vertical so its front points along `worldDir` (flattened).</summary>
    public float Aim(Vector3 worldDir)
    {
        Vector3 local = root.InverseTransformDirection(worldDir);
        float yaw = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
        Turn(Vector3.up, yaw);
        return yaw;
    }

    /// <summary>Moves the part from its rest position by an offset in the root's frame.</summary>
    public void Slide(Vector3 offset)
    {
        T.position = root.TransformPoint(restPos + offset);
    }
}
