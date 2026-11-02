using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Lives on a Sprinkler's model. On the server, every PulseDelay seconds it soaks the enemies in its cone that the
/// water can reach (only spraying when there's someone to soak); everyone who draws it sees the spray and water
/// dripping off the soaked zombies. Deluge widens the cone and soaks longer; the Pressure Washer narrows it to a jet
/// that shoves and hurts.
/// The model's SprayOrigin and SprayAim points give the nozzle and its direction, so the cone turns with the block.
/// </summary>
public class SprinklerControllerDEM : TrapControllerDEM
{
    private BlockSprinklerDEM sprinkler;
    private Transform nozzle;
    private Transform aim;
    private ParticleSystem spray;
    private float sprayAngle;
    private float spraySpeed;

    private static readonly List<int> soaked = new List<int>();

    protected override float ActDelay => sprinkler.PulseDelay;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        sprinkler = (BlockSprinklerDEM)trap;
        base.Setup(trap, pos);
        nozzle = FindDeep(transform, "SprayOrigin");
        aim = FindDeep(transform, "SprayAim");
        Transform fx = FindDeep(transform, "SprayFx");
        spray = fx != null ? fx.GetComponent<ParticleSystem>() : null;
        if (spray != null)
        {
            sprayAngle = spray.shape.angle;
            spraySpeed = spray.main.startSpeedMultiplier;
        }
    }

    /// <summary>The nozzle in world space and the way it points.</summary>
    private void Nozzle(out Vector3 origin, out Vector3 dir)
    {
        if (nozzle != null && aim != null)
        {
            origin = nozzle.position + Origin.position;
            dir = (aim.position - nozzle.position).normalized;
        }
        else
        {
            origin = BlockPos.ToVector3() + new Vector3(0.5f, 0.9f, 0.5f);
            dir = transform.forward;
        }
    }

    protected override bool Act(World world)
    {
        Nozzle(out Vector3 origin, out Vector3 dir);
        bool deluge = Upgraded('A');
        bool washer = Upgraded('B');
        float angle = deluge ? sprinkler.DelugeAngle : washer ? sprinkler.WasherAngle : sprinkler.ConeAngle;
        float seconds = (deluge ? sprinkler.DelugeSeconds : sprinkler.SoakSeconds) * DurationMult;
        float minCos = Mathf.Cos(angle * 0.5f * Mathf.Deg2Rad);
        int owner = Owner(world);
        soaked.Clear();
        // Header for the clients: how long the soak lasts (tenths of a second) and the spray's shape
        soaked.Add(-Mathf.RoundToInt(seconds * 10f));
        soaked.Add(washer ? -2 : deluge ? -3 : -1);
        foreach (EntityAlive alive in Enemies(world, origin, sprinkler.Range))
        {
            Vector3 chest = alive.getChestPosition();
            Vector3 to = chest - origin;
            float dist = to.magnitude;
            if (dist > sprinkler.Range || dist < 0.01f || Vector3.Dot(to / dist, dir) < minCos)
            {
                continue;
            }
            // From just outside the sprinkler's own collider
            if (!Reachable(world, origin + dir * 0.35f, chest))
            {
                continue;
            }
            alive.Buffs.AddBuff(sprinkler.SoakBuff, owner, true, false, seconds);
            Touch(alive, false);
            if (washer)
            {
                if (Hit(alive, sprinkler.WasherDamage, EnumDamageTypes.Bashing, to / dist, owner))
                {
                    TrapStatusDEM.Knockback(alive, to, sprinkler.WasherShove);
                }
            }
            soaked.Add(alive.entityId);
        }
        if (soaked.Count == 2)
        {
            return false;
        }
        Wear(world);
        Audio.Manager.BroadcastPlay(origin, sprinkler.SpraySound);
        Broadcast(origin, soaked.ToArray());
        return true;
    }

    public override void PlayFx(int[] ids)
    {
        float seconds = sprinkler.SoakSeconds;
        int mode = 1;
        int start = 0;
        if (ids.Length >= 2 && ids[0] < 0 && ids[1] < 0)
        {
            seconds = -ids[0] / 10f;
            mode = -ids[1];
            start = 2;
        }
        if (spray != null)
        {
            ParticleSystem.ShapeModule shape = spray.shape;
            // Deluge sprays wider, the Pressure Washer a fast narrow jet
            shape.angle = sprayAngle * (mode == 2 ? 0.25f : mode == 3 ? 1.6f : 1f);
            ParticleSystem.MainModule main = spray.main;
            main.startSpeedMultiplier = spraySpeed * (mode == 2 ? 1.8f : 1f);
            spray.gameObject.SetActive(true);
            spray.Play(true);
        }
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return;
        }
        for (int i = start; i < ids.Length; i++)
        {
            if (world.GetEntity(ids[i]) is EntityAlive entity)
            {
                DripFxDEM.Attach(entity, seconds);
            }
        }
    }
}
