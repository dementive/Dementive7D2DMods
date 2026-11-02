using System;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Senses, on the server. Sound carries: a player's loud noises (gunshots, explosions, breaking blocks) send the
/// zombies in range to look, the range following the game's own loudness for that sound (a pistol about 40 m, a
/// rifle 55, shotguns and explosions up to 80; a suppressor too quiet to count). Herd alert: when a zombie spots
/// someone, zombies within 12 m that can see it turn toward them too.
/// </summary>
public static class ZedSenses
{
    public static void Noise(Entity instigator, Vector3 pos, string clip, float volumeScale)
    {
        if (!ZedSettings.Senses || !(instigator is EntityPlayer) || !AIDirectorData.FindNoise(clip, out AIDirectorData.Noise noise))
        {
            return;
        }
        float volume = noise.volume * volumeScale;
        if (volume < 25f)
        {
            return;
        }
        float range = Mathf.Min(80f, Mathf.Sqrt(volume) * 7f);
        float r2 = range * range;
        World world = instigator.world;
        foreach (EntityAlive z in world.EntityAlives)
        {
            if (!z.IsDead() && ZedStore.IsZombie(z) && z.GetAttackTarget() == null && !z.IsSleeper
                && (z.position - pos).sqrMagnitude < r2)
            {
                Vector3 spot = pos + new Vector3(UnityEngine.Random.Range(-2f, 2f), 0f, UnityEngine.Random.Range(-2f, 2f));
                z.SetInvestigatePosition(spot, 600, true);
            }
        }
    }

    [ThreadStatic] private static bool alerting;

    public static void Spotted(EntityAlive zombie, EntityAlive target)
    {
        if (alerting || !ZedSettings.Senses || !(target is EntityPlayer) || !ZedStore.IsZombie(zombie))
        {
            return;
        }
        alerting = true;
        try
        {
            int alerted = 0;
            foreach (EntityAlive z in zombie.world.EntityAlives)
            {
                if (z == zombie || z.IsDead() || !ZedStore.IsZombie(z) || z.GetAttackTarget() != null || z.IsSleeper
                    || (z.position - zombie.position).sqrMagnitude > 144f)
                {
                    continue;
                }
                if (z.CanSee(zombie.getChestPosition()))
                {
                    z.SetAttackTarget(target, 600);
                    if (++alerted >= 6)
                    {
                        break;
                    }
                }
            }
        }
        finally
        {
            alerting = false;
        }
    }
}

[HarmonyPatch(typeof(AIDirector), nameof(AIDirector.NotifyNoise))]
public class ZedNoisePatch
{
    public static void Postfix(Entity instigator, Vector3 position, string clipName, float volumeScale)
    {
        try
        {
            if (ZedStore.IsServer)
            {
                ZedSenses.Noise(instigator, position, clipName, volumeScale);
            }
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }
}

[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.SetAttackTarget))]
public class ZedSpottedPatch
{
    public static void Prefix(EntityAlive __instance, out bool __state)
    {
        __state = __instance.GetAttackTarget() == null;
    }

    public static void Postfix(EntityAlive __instance, EntityAlive _attackTarget, bool __state)
    {
        if (__state && _attackTarget != null && ZedStore.IsServer)
        {
            ZedSenses.Spotted(__instance, _attackTarget);
        }
    }
}
