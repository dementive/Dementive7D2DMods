using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Lives on a Tesla Coil's model. On the server it picks targets, deals the electrical damage (credited to the
/// coil's owner like vanilla traps) and tells nearby clients which zombies the bolt went through; every game that
/// draws the coil shows the arcs, the glow and the power lamp.
/// </summary>
public class TeslaCoilControllerDEM : MonoBehaviour
{
    private const float ArcLife = 0.22f;
    private const float JitterInterval = 0.035f;

    public bool IsOn;

    private BlockTeslaCoilDEM block;
    private Vector3i blockPos;
    private float cooldown;
    private Transform arcOrigin;
    private LineRenderer arcTemplate;
    private Light glow;
    private float flash;
    private Renderer[] renderers;
    private MaterialPropertyBlock props;
    private float lampRefresh;
    private readonly List<Arc> arcs = new List<Arc>();

    private static readonly List<Entity> found = new List<Entity>();
    private static readonly List<int> chain = new List<int>();

    private class Arc
    {
        public LineRenderer Main;
        public LineRenderer Branch;
        public EntityAlive From;
        public EntityAlive To;
        public float Age;
        public float NextJitter;
    }

    public void Setup(BlockTeslaCoilDEM _block, Vector3i _pos)
    {
        block = _block;
        blockPos = _pos;
        arcOrigin = FindDeep(transform, "ArcOrigin");
        Transform template = FindDeep(transform, "ArcTemplate");
        arcTemplate = template != null ? template.GetComponent<LineRenderer>() : null;
        renderers = GetComponentsInChildren<MeshRenderer>(true);
        if (glow == null)
        {
            GameObject light = new GameObject("TeslaGlow");
            light.transform.SetParent(arcOrigin != null ? arcOrigin : transform, false);
            glow = light.AddComponent<Light>();
            glow.type = LightType.Point;
            glow.color = new Color(0.55f, 0.75f, 1f);
            glow.range = 6f;
            glow.shadows = LightShadows.None;
            glow.intensity = 0f;
        }
        lampRefresh = 0f;
        // Spread neighbouring coils' zaps out instead of firing in lockstep
        cooldown = Random.Range(0.1f, block.FireDelay);
    }

    private void OnDisable()
    {
        foreach (Arc arc in arcs)
        {
            DestroyArc(arc);
        }
        arcs.Clear();
        flash = 0f;
    }

    private void Update()
    {
        if (block == null)
        {
            return;
        }
        float dt = Time.deltaTime;
        UpdateLamp(dt);
        UpdateArcs(dt);
        UpdateGlow(dt);

        if (!IsOn || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        cooldown -= dt;
        if (cooldown > 0f)
        {
            return;
        }
        if (WornOut())
        {
            cooldown = 1f;
            return;
        }
        cooldown = Zap() ? block.FireDelay : 0.25f;
    }

    private bool WornOut()
    {
        World world = GameManager.Instance.World;
        return world != null && block.IsWornOut(world.GetBlock(blockPos));
    }

    // ------------------------------------------------------------------ server

    private bool Zap()
    {
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return false;
        }

        Vector3 origin = blockPos.ToVector3() + BlockTeslaCoilDEM.ArcOffset;
        chain.Clear();
        EntityAlive target = Nearest(world, origin, block.Range, true);
        if (target == null)
        {
            return false;
        }

        int owner = Owner(world);
        float damage = block.EntityDamage;
        Vector3 from = origin;
        for (int jump = 0; target != null; jump++)
        {
            chain.Add(target.entityId);
            Vector3 chest = target.getChestPosition();
            Hit(target, from, damage, owner);
            if (jump >= block.Chains)
            {
                break;
            }
            damage *= block.ChainFalloff;
            from = chest;
            target = Nearest(world, chest, block.ChainRange, false);
        }

        Wear(world);
        Audio.Manager.BroadcastPlay(origin, block.ZapSound);
        int[] ids = chain.ToArray();
        if (!GameManager.IsDedicatedServer)
        {
            ShowArcs(ids);
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageTeslaArcDEM>().Setup(blockPos, ids),
            _entitiesInRangeOfWorldPos: origin, _range: 96);
        return true;
    }

    /// <summary>Closest living enemy within range that the bolt can reach and hasn't hit this zap.</summary>
    private EntityAlive Nearest(World world, Vector3 from, float range, bool fromCoil)
    {
        found.Clear();
        world.GetEntitiesInBounds(typeof(EntityEnemy), new Bounds(from, Vector3.one * (range * 2f)), found);
        EntityAlive best = null;
        float bestDist = range * range;
        foreach (Entity entity in found)
        {
            if (!(entity is EntityAlive alive) || !alive.IsAlive() || chain.Contains(alive.entityId))
            {
                continue;
            }
            Vector3 chest = alive.getChestPosition();
            float d = (chest - from).sqrMagnitude;
            if (d >= bestDist)
            {
                continue;
            }
            Vector3 start = from;
            if (fromCoil)
            {
                // Start outside the coil's own collider
                Vector3 flat = chest - from;
                flat.y = 0f;
                start += flat.sqrMagnitude > 0.0001f ? flat.normalized * 0.6f : Vector3.zero;
            }
            if (!Reachable(world, start, chest))
            {
                continue;
            }
            best = alive;
            bestDist = d;
        }
        return best;
    }

    /// <summary>True when no block or terrain is between the points (bodies in the way still conduct).</summary>
    private static bool Reachable(World world, Vector3 from, Vector3 to)
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

    /// <summary>
    /// Heat damage, not Electrical: the game starts its electrocute flinch on every electrical hit, which made each
    /// zap a stun. The flinch comes only with the occasional jolt instead (not on shock-immune charged zombies).
    /// </summary>
    private void Hit(EntityAlive target, Vector3 from, float damage, int owner)
    {
        Vector3 dir = (target.getChestPosition() - from).normalized;
        target.DamageEntity(new DamageSourceEntity(EnumDamageSource.External, EnumDamageTypes.Heat, owner, dir),
            Mathf.Max(1, Mathf.RoundToInt(damage)), false, 0.2f);
        if (string.IsNullOrEmpty(block.JoltBuff) || !target.IsAlive() || Random.value >= block.JoltChance
            || target.HasAnyTags(ChargedTags) || target.Buffs.HasBuff("buffShockImmune"))
        {
            return;
        }
        target.Buffs.AddBuff(block.JoltBuff, owner, true, true);
        target.Electrocuted = true;
    }

    private static readonly FastTags<TagGroup.Global> ChargedTags = FastTags<TagGroup.Global>.Parse("charged");

    /// <summary>Each zap wears the coil a little (block damage, repaired like any block), stopping short of
    /// breaking it.</summary>
    private void Wear(World world)
    {
        if (block.WearPerZap <= 0)
        {
            return;
        }
        BlockValue bv = world.GetBlock(blockPos);
        if (!(bv.Block is BlockTeslaCoilDEM))
        {
            return;
        }
        int damage = Mathf.Min(bv.damage + block.WearPerZap, block.MaxDamage - 1);
        if (damage == bv.damage)
        {
            return;
        }
        bv.damage = damage;
        world.SetBlockRPC(blockPos, bv);
    }

    private int Owner(World world)
    {
        TileEntityPoweredMeleeTrap te = world.GetTileEntity(blockPos) as TileEntityPoweredMeleeTrap;
        return te != null ? te.OwnerEntityID : -1;
    }

    // ------------------------------------------------------------------ visuals

    /// <summary>Draws a bolt from the toroid through each zombie in order.</summary>
    public void ShowArcs(int[] ids)
    {
        World world = GameManager.Instance.World;
        if (world == null || arcTemplate == null)
        {
            return;
        }
        EntityAlive previous = null;
        foreach (int id in ids)
        {
            if (!(world.GetEntity(id) is EntityAlive target))
            {
                continue;
            }
            arcs.Add(new Arc { Main = NewLine(1f), Branch = NewLine(0.45f), From = previous, To = target });
            previous = target;
        }
        flash = 1f;
    }

    private void UpdateArcs(float dt)
    {
        for (int i = arcs.Count - 1; i >= 0; i--)
        {
            Arc arc = arcs[i];
            arc.Age += dt;
            if (arc.Age >= ArcLife || arc.To == null)
            {
                DestroyArc(arc);
                arcs.RemoveAt(i);
                continue;
            }
            float fade = 1f - arc.Age / ArcLife;
            arc.Main.widthMultiplier = arcTemplate.widthMultiplier * fade;
            arc.Branch.widthMultiplier = arcTemplate.widthMultiplier * 0.45f * fade;
            if (arc.Age < arc.NextJitter)
            {
                continue;
            }
            arc.NextJitter = arc.Age + JitterInterval;
            Vector3 end = arc.To.GetChestTransformPosition();
            Vector3 start;
            if (arc.From != null)
            {
                start = arc.From.GetChestTransformPosition();
            }
            else
            {
                // Leave from the toroid's rim on the side facing the target
                Vector3 center = arcOrigin != null ? arcOrigin.position : transform.position + Vector3.up * 1.12f;
                Vector3 flat = end - center;
                flat.y = 0f;
                start = center + (flat.sqrMagnitude > 0.0001f ? flat.normalized * 0.3f : Vector3.zero);
            }
            Jag(arc.Main, start, end, 0.09f);
            Vector3 mid = Vector3.Lerp(start, end, Random.Range(0.3f, 0.6f));
            Jag(arc.Branch, mid, mid + Random.onUnitSphere * Random.Range(0.4f, 0.9f), 0.12f);
        }
    }

    private static void Jag(LineRenderer line, Vector3 a, Vector3 b, float roughness)
    {
        float dist = Vector3.Distance(a, b);
        int count = Mathf.Clamp(Mathf.CeilToInt(dist * 4f), 6, 28);
        line.positionCount = count;
        float amp = Mathf.Min(0.4f, dist * roughness);
        for (int i = 0; i < count; i++)
        {
            float t = i / (float)(count - 1);
            Vector3 p = Vector3.Lerp(a, b, t);
            if (i > 0 && i < count - 1)
            {
                p += Random.insideUnitSphere * (amp * Mathf.Sin(t * Mathf.PI));
            }
            line.SetPosition(i, p);
        }
    }

    private LineRenderer NewLine(float width)
    {
        LineRenderer line = Instantiate(arcTemplate);
        line.gameObject.SetActive(true);
        line.enabled = true;
        line.useWorldSpace = true;
        line.widthMultiplier = arcTemplate.widthMultiplier * width;
        line.positionCount = 0;
        return line;
    }

    private static void DestroyArc(Arc arc)
    {
        if (arc.Main != null)
        {
            Destroy(arc.Main.gameObject);
        }
        if (arc.Branch != null)
        {
            Destroy(arc.Branch.gameObject);
        }
    }

    private void UpdateGlow(float dt)
    {
        if (glow == null)
        {
            return;
        }
        flash = Mathf.Max(0f, flash - dt * 6f);
        float idle = IsOn ? 0.35f + 0.25f * Mathf.PerlinNoise(Time.time * 9f, blockPos.x * 0.37f) : 0f;
        glow.intensity = idle + flash * 4f;
        glow.enabled = glow.intensity > 0.01f;
    }

    /// <summary>The red lamp on the junction box is lit while the coil has power, and blinks when it's worn out
    /// and needs repair. Re-applied now and then in case the game resets the renderers' property blocks (it sets
    /// block damage and tint through them).</summary>
    private void UpdateLamp(float dt)
    {
        lampRefresh -= dt;
        if (lampRefresh > 0f || renderers == null)
        {
            return;
        }
        lampRefresh = 0.5f;
        if (props == null)
        {
            props = new MaterialPropertyBlock();
        }
        bool lit = IsOn && (!WornOut() || Mathf.FloorToInt(Time.time * 2f) % 2 == 0);
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

    private static Transform FindDeep(Transform root, string name)
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
