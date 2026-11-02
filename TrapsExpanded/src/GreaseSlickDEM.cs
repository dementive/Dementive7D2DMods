using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Grease Slick (XML class "GreaseSlickDEM, TrapsExpanded"): a floor pan of grease. Zombies that walk through it are
/// Tarred for TarSeconds (levels lengthen it). Each zombie greased uses AmmoPerUse animal fat (1 per 4 zombies); a
/// zombie isn't greased again by the same slick for RegreaseSeconds. Upgrades (level 3): A Deep Grease (55% slower), B
/// Volatile Grease (its zombies' Infernos 50% stronger).
///
/// XML properties: Radius (from the block's center), TarSeconds, RegreaseSeconds, SplashSound, and the shared ones
/// (AmmoItems, AmmoCapacity, AmmoPerUse, StatusTrap, UpgradeA/B).
/// </summary>
public class BlockGreaseSlickDEM : BlockPlainTrapDEM
{
    public float Radius = 0.75f;
    public float TarSeconds = 12f;
    public float RegreaseSeconds = 6f;
    public string SplashSound = "vomitimpact";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Radius", ref Radius);
        Properties.ParseFloat("TarSeconds", ref TarSeconds);
        Properties.ParseFloat("RegreaseSeconds", ref RegreaseSeconds);
        Properties.ParseString("SplashSound", ref SplashSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<GreaseSlickControllerDEM>();
    }
}

public class GreaseSlickControllerDEM : TrapControllerDEM
{
    private BlockGreaseSlickDEM slick;
    private readonly Dictionary<int, float> greased = new Dictionary<int, float>();
    private static readonly List<int> hit = new List<int>();

    protected override float ActDelay => 0.25f;

    protected override float IdleDelay => 0.25f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        slick = (BlockGreaseSlickDEM)trap;
        base.Setup(trap, pos);
    }

    protected override bool Act(World world)
    {
        if (!HasAmmo)
        {
            Cooldown = 1f;
            return false;
        }
        Vector3 center = BlockPos.ToVector3() + new Vector3(0.5f, 0f, 0.5f);
        float seconds = slick.TarSeconds * DurationMult;
        int level = Upgraded('A') ? 2 : 1;
        bool volatileGrease = Upgraded('B');
        int owner = Owner(world);
        hit.Clear();
        hit.Add(-Mathf.RoundToInt(seconds * 10f));
        foreach (EntityAlive e in Enemies(world, center + Vector3.up, slick.Radius + 1f))
        {
            Vector3 p = e.position;
            Vector3 flat = p - center;
            float dy = flat.y;
            flat.y = 0f;
            if (flat.magnitude > slick.Radius || dy < -0.5f || dy > 1f)
            {
                continue;
            }
            if (greased.TryGetValue(e.entityId, out float at) && Time.time - at < slick.RegreaseSeconds)
            {
                continue;
            }
            if (!UseAmmo(Settings.AmmoPerUse, out _))
            {
                break;
            }
            greased[e.entityId] = Time.time;
            TrapStatusDEM.Tar(e, level, volatileGrease, false, seconds, owner);
            Touch(e, false);
            hit.Add(e.entityId);
        }
        if (hit.Count == 1)
        {
            return false;
        }
        if (greased.Count > 64)
        {
            greased.Clear();
        }
        Audio.Manager.BroadcastPlay(center, slick.SplashSound);
        Broadcast(center, hit.ToArray());
        return true;
    }

    /// <summary>Tar dripping off the greased zombies.</summary>
    public override void PlayFx(int[] ids)
    {
        World world = GameManager.Instance.World;
        if (world == null || ids.Length < 1)
        {
            return;
        }
        float seconds = ids[0] < 0 ? -ids[0] / 10f : slick.TarSeconds;
        for (int i = ids[0] < 0 ? 1 : 0; i < ids.Length; i++)
        {
            if (world.GetEntity(ids[i]) is EntityAlive e)
            {
                FxDEM.Attach(e, "TarDrip", seconds, 0.35f);
            }
        }
    }
}
