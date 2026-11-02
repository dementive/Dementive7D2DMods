using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Lives on a Tesla Coil's model. On the server it picks targets and deals the damage (credited to the coil's owner
/// like vanilla traps); every game that draws the coil shows the arcs and the glow.
/// </summary>
public class TeslaCoilControllerDEM : TrapControllerDEM
{
    private const float ArcLife = 0.22f;
    private const float JitterInterval = 0.035f;

    private BlockTeslaCoilDEM coil;
    private Transform arcOrigin;
    private LineRenderer arcTemplate;
    private Light glow;
    private float flash;
    private readonly List<Arc> arcs = new List<Arc>();

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

    protected override float ActDelay => coil.FireDelay;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        coil = (BlockTeslaCoilDEM)trap;
        base.Setup(trap, pos);
        arcOrigin = FindDeep(transform, "ArcOrigin");
        Transform template = FindDeep(transform, "ArcTemplate");
        arcTemplate = template != null ? template.GetComponent<LineRenderer>() : null;
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
    }

    protected override void OnDisable()
    {
        base.OnDisable();
        foreach (Arc arc in arcs)
        {
            DestroyArc(arc);
        }
        arcs.Clear();
        flash = 0f;
    }

    protected override void Update()
    {
        base.Update();
        if (coil == null)
        {
            return;
        }
        UpdateArcs(Time.deltaTime);
        UpdateGlow(Time.deltaTime);
    }

    // ------------------------------------------------------------------ server

    protected override bool Act(World world)
    {
        Vector3 origin = BlockPos.ToVector3() + BlockTeslaCoilDEM.ArcOffset;
        chain.Clear();
        EntityAlive target = Nearest(world, origin, coil.Range, true);
        if (target == null)
        {
            return false;
        }

        int owner = Owner(world);
        bool storm = Upgraded('A');
        bool overload = Upgraded('B');
        float damage = coil.EntityDamage * DamageMult;
        int chains = coil.Chains;
        if (storm)
        {
            damage *= coil.StormDamage;
            chains += coil.StormChains;
        }
        else if (overload)
        {
            damage *= coil.OverloadDamage;
            chains = 0;
        }
        Vector3 from = origin;
        bool soakedHit = false;
        for (int jump = 0; target != null; jump++)
        {
            chain.Add(target.entityId);
            Vector3 chest = target.getChestPosition();
            soakedHit |= Zap(target, from, damage, owner, overload);
            if (jump >= chains + (soakedHit && !overload ? coil.SoakedChains : 0))
            {
                break;
            }
            damage *= coil.ChainFalloff;
            from = chest;
            target = Nearest(world, chest, coil.ChainRange, false);
        }

        Wear(world);
        Audio.Manager.BroadcastPlay(origin, coil.ZapSound);
        Broadcast(origin, chain.ToArray());
        return true;
    }

    /// <summary>Closest living enemy within range that the bolt can reach and hasn't hit this zap.</summary>
    private EntityAlive Nearest(World world, Vector3 from, float range, bool fromCoil)
    {
        EntityAlive best = null;
        float bestDist = range * range;
        foreach (EntityAlive alive in Enemies(world, from, range))
        {
            if (chain.Contains(alive.entityId))
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

    /// <summary>
    /// Heat damage, not Electrical: the game starts its electrocute flinch on every electrical hit, which made each
    /// zap a stun. The flinch comes only with the occasional jolt instead (not on shock-immune charged zombies).
    /// A soaked zombie takes SoakedDamage times the damage, and its jolt becomes a stun unless it was stunned
    /// recently or is a big zombie. Overload jolts on every hit, and its jolt is always a stun. Returns whether the
    /// zombie was soaked.
    /// </summary>
    private bool Zap(EntityAlive target, Vector3 from, float damage, int owner, bool overload)
    {
        bool soaked = TrapStatusDEM.IsSoaked(target);
        if (soaked)
        {
            damage *= coil.SoakedDamage;
            BloodMoonDEM.Combo(BloodMoonDEM.ComboSoakedShock);
        }
        Vector3 dir = (target.getChestPosition() - from).normalized;
        if (!Hit(target, damage, EnumDamageTypes.Heat, dir, owner))
        {
            return soaked;
        }
        if ((!overload && Random.value >= coil.JoltChance) || TrapStatusDEM.IsShockImmune(target))
        {
            return soaked;
        }
        if ((soaked || overload) && !string.IsNullOrEmpty(coil.SoakedStunBuff) && !TrapStatusDEM.IsBig(target)
            && !target.Buffs.HasBuff(coil.SoakedStunImmuneBuff))
        {
            target.Buffs.AddBuff(coil.SoakedStunBuff, owner, true, true);
            target.Buffs.AddBuff(coil.SoakedStunImmuneBuff, owner, true, true);
        }
        else if (!string.IsNullOrEmpty(coil.JoltBuff))
        {
            target.Buffs.AddBuff(coil.JoltBuff, owner, true, true);
        }
        target.Electrocuted = true;
        return soaked;
    }

    // ------------------------------------------------------------------ visuals

    /// <summary>Draws a bolt from the toroid through each zombie in order.</summary>
    public override void PlayFx(int[] ids)
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
        float idle = IsOn ? 0.35f + 0.25f * Mathf.PerlinNoise(Time.time * 9f, BlockPos.x * 0.37f) : 0f;
        glow.intensity = idle + flash * 4f;
        glow.enabled = glow.intensity > 0.01f;
    }
}
