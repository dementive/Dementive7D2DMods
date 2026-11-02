using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Overcharger (XML class "OverchargerDEM, TrapsExpanded"): car batteries and a capacitor bank in a shopping cart.
/// While powered, the mod's powered traps within Range act SpeedBoost times as fast and wear WearBoost times as fast
/// (the strongest Overcharger in range counts; they don't stack). Upgrades (level 3): A Capacitor Bank
/// (CapacitorRange), B Surge (SurgeSpeed and SurgeWear). It levels from the kills of the traps it's boosting.
///
/// The model's ArcPoint is where its sparks jump. XML properties: Range, SpeedBoost, WearBoost, CapacitorRange,
/// SurgeSpeed, SurgeWear, SparkSound, and the shared ones.
/// </summary>
public class BlockOverchargerDEM : BlockTrapDEM
{
    public float Range = 5f;
    public float SpeedBoost = 1.25f;
    public float WearBoost = 1.25f;
    public float CapacitorRange = 8f;
    public float SurgeSpeed = 1.5f;
    public float SurgeWear = 2f;
    public string SparkSound = "";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("SpeedBoost", ref SpeedBoost);
        Properties.ParseFloat("WearBoost", ref WearBoost);
        Properties.ParseFloat("CapacitorRange", ref CapacitorRange);
        Properties.ParseFloat("SurgeSpeed", ref SurgeSpeed);
        Properties.ParseFloat("SurgeWear", ref SurgeWear);
        Properties.ParseString("SparkSound", ref SparkSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<OverchargerControllerDEM>();
    }
}

public class OverchargerControllerDEM : TrapControllerDEM
{
    private BlockOverchargerDEM charger;
    private Transform arcPoint;
    private LineRenderer[] sparks;
    private float sparkAge = 99f;

    private static readonly List<int> boosted = new List<int>();

    protected override float ActDelay => 3f;

    protected override float IdleDelay => 3f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        charger = (BlockOverchargerDEM)trap;
        base.Setup(trap, pos);
        arcPoint = FindDeep(transform, "ArcPoint");
    }

    /// <summary>Server: what this Overcharger gives the traps in its range.</summary>
    public void Boost(out float range, out float speed, out float wear)
    {
        bool surge = Upgraded('B');
        range = Upgraded('A') ? charger.CapacitorRange : charger.Range;
        speed = surge ? charger.SurgeSpeed : charger.SpeedBoost;
        wear = surge ? charger.SurgeWear : charger.WearBoost;
    }

    /// <summary>Server: an Overcharger levels up from the kills of the traps it boosts.</summary>
    public static void ShareKill(World world, Vector3i trapPos)
    {
        Vector3 at = trapPos.ToVector3();
        foreach (TrapControllerDEM c in Active)
        {
            if (!(c is OverchargerControllerDEM o) || !o.IsOn || o.Position == trapPos)
            {
                continue;
            }
            o.Boost(out float range, out _, out _);
            if ((o.Position.ToVector3() - at).sqrMagnitude <= range * range)
            {
                TrapStoreDEM.AddKill(o.Position, o.BlockName);
            }
        }
    }

    /// <summary>Server: shows sparks while it's boosting something.</summary>
    protected override bool Act(World world)
    {
        Boost(out float range, out _, out _);
        Vector3 here = BlockPos.ToVector3();
        boosted.Clear();
        foreach (TrapControllerDEM c in Active)
        {
            if (c == this || c is OverchargerControllerDEM || !c.IsPoweredTrap || !c.IsOn)
            {
                continue;
            }
            if ((c.Position.ToVector3() - here).sqrMagnitude <= range * range)
            {
                boosted.Add(c.Position.x);
                boosted.Add(c.Position.y);
                boosted.Add(c.Position.z);
                if (boosted.Count >= 12)
                {
                    break;
                }
            }
        }
        if (boosted.Count == 0)
        {
            return false;
        }
        if (!string.IsNullOrEmpty(charger.SparkSound))
        {
            Audio.Manager.BroadcastPlay(here + Vector3.one * 0.5f, charger.SparkSound);
        }
        Broadcast(here, boosted.ToArray());
        return true;
    }

    /// <summary>Short arcs from the capacitors toward the traps it's boosting.</summary>
    public override void PlayFx(int[] ids)
    {
        if (GameManager.IsDedicatedServer)
        {
            return;
        }
        Vector3 from = WorldPoint(arcPoint, new Vector3(0f, 0.4f, 0f));
        FxDEM.Vanilla("p_wire_tool_sparks", from, Quaternion.identity, 1f);
        int count = ids.Length / 3;
        if (sparks == null)
        {
            sparks = new LineRenderer[4];
        }
        for (int i = 0; i < sparks.Length; i++)
        {
            if (i >= count)
            {
                if (sparks[i] != null)
                {
                    sparks[i].enabled = false;
                }
                continue;
            }
            Vector3 to = new Vector3(ids[i * 3], ids[i * 3 + 1], ids[i * 3 + 2]) + new Vector3(0.5f, 0.6f, 0.5f);
            // Only a short way out: a crackle, not a beam across the base
            Vector3 end = from + Vector3.ClampMagnitude(to - from, 0.8f);
            if (sparks[i] == null)
            {
                sparks[i] = NewSpark();
            }
            Jag(sparks[i], from - Origin.position, end - Origin.position);
            sparks[i].enabled = true;
        }
        sparkAge = 0f;
    }

    private LineRenderer NewSpark()
    {
        GameObject go = new GameObject("OverchargeSpark");
        go.transform.SetParent(transform, false);
        LineRenderer line = go.AddComponent<LineRenderer>();
        line.useWorldSpace = true;
        line.widthMultiplier = 0.025f;
        Shader shader = Shader.Find("Sprites/Default") ?? Shader.Find("Legacy Shaders/Particles/Additive");
        if (shader != null)
        {
            line.material = new Material(shader);
        }
        line.startColor = new Color(0.7f, 0.85f, 1f);
        line.endColor = new Color(0.4f, 0.6f, 1f, 0f);
        return line;
    }

    private static void Jag(LineRenderer line, Vector3 a, Vector3 b)
    {
        const int count = 7;
        line.positionCount = count;
        for (int i = 0; i < count; i++)
        {
            float t = i / (float)(count - 1);
            Vector3 p = Vector3.Lerp(a, b, t);
            if (i > 0 && i < count - 1)
            {
                p += Random.insideUnitSphere * 0.06f;
            }
            line.SetPosition(i, p);
        }
    }

    protected override void Update()
    {
        base.Update();
        if (sparks == null || sparkAge > 0.3f)
        {
            return;
        }
        sparkAge += Time.deltaTime;
        if (sparkAge > 0.25f)
        {
            foreach (LineRenderer l in sparks)
            {
                if (l != null)
                {
                    l.enabled = false;
                }
            }
        }
    }
}
