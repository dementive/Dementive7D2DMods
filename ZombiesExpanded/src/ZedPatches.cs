using System;
using HarmonyLib;
using UnityEngine;

/// <summary>Every zombie that's set up, on the server and on every player's game, gets its profile.</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.PostInit))]
public class ZedPostInitPatch
{
    public static void Postfix(EntityAlive __instance)
    {
        try
        {
            if (ZedStore.IsZombie(__instance))
            {
                ZedStore.Spawned(__instance);
            }
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }
}

[HarmonyPatch(typeof(World), nameof(World.unloadEntity))]
public class ZedUnloadPatch
{
    public static void Postfix(Entity _e, EnumRemoveEntityReason _reason)
    {
        if (_e is EntityAlive && ZedStore.IsZombie(_e))
        {
            ZedStore.Unloaded(_e, _reason == EnumRemoveEntityReason.Unloaded);
            ZedTemperament.Forget(_e.entityId);
            ZedCombat.Forget(_e.entityId);
        }
    }
}

/// <summary>Each zombie's own speed, on top of whatever the game worked out (day, night, rage, Blood Moon), and what
/// its brain is doing (out of breath, lunging, charging, near the Alpha). GetMoveSpeed calls GetMoveSpeedAggro when the
/// zombie is alert, and the Hulking's cap calls GetMoveSpeed, so only the outermost call applies the factors.</summary>
public static class ZedSpeed
{
    [ThreadStatic] public static int Depth;

    public static void Apply(EntityHuman z, ref float speed, bool aggro)
    {
        if (Depth != 1)
        {
            return;
        }
        ZedProfile p = ZedStore.Get(z.entityId);
        if (p == null)
        {
            return;
        }
        speed *= p.Speed;
        ZedBrain b = ZedBrain.Of(z);
        if (b == null)
        {
            return;
        }
        if (aggro && b.CapAtWalk)
        {
            // A Hulking never runs: it chases at its walk (the nested call returns the game's own value)
            speed = Mathf.Min(speed, z.GetMoveSpeed() * p.Speed * 1.15f);
        }
        speed *= b.SpeedFactor(aggro);
    }
}

[HarmonyPatch(typeof(EntityHuman), nameof(EntityHuman.GetMoveSpeed))]
public class ZedMoveSpeedPatch
{
    public static void Prefix()
    {
        ZedSpeed.Depth++;
    }

    public static void Postfix(EntityHuman __instance, ref float __result)
    {
        ZedSpeed.Apply(__instance, ref __result, false);
    }

    public static Exception Finalizer(Exception __exception)
    {
        ZedSpeed.Depth = Math.Max(0, ZedSpeed.Depth - 1);
        return __exception;
    }
}

[HarmonyPatch(typeof(EntityHuman), nameof(EntityHuman.GetMoveSpeedAggro))]
public class ZedMoveSpeedAggroPatch
{
    public static void Prefix()
    {
        ZedSpeed.Depth++;
    }

    public static void Postfix(EntityHuman __instance, ref float __result)
    {
        ZedSpeed.Apply(__instance, ref __result, true);
    }

    public static Exception Finalizer(Exception __exception)
    {
        ZedSpeed.Depth = Math.Max(0, ZedSpeed.Depth - 1);
        return __exception;
    }
}

/// <summary>Hits, on every game that draws them (the damage response reaches every player): wounds, char, frost.</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ProcessDamageResponseLocal))]
public class ZedDamagePatch
{
    public static void Postfix(EntityAlive __instance, DamageResponse _dmResponse)
    {
        try
        {
            if (ZedStore.DrawsLooks && ZedStore.IsZombie(__instance))
            {
                ZedLook.Damaged(__instance, _dmResponse);
            }
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }
}

/// <summary>
/// Voices: each zombie's sounds (groans, screams, footsteps) are pitched by its own factor, so a crowd doesn't sound
/// like one voice. The game picks a random pitch per sound in SetPitch; the zombie playing it is noted while its Play
/// runs.
/// </summary>
public static class ZedVoice
{
    [ThreadStatic] private static int depth;
    [ThreadStatic] private static float factor;

    public static void Begin(Entity e)
    {
        if (depth++ == 0)
        {
            factor = Factor(e);
        }
    }

    public static void Begin(int entityId)
    {
        if (depth++ == 0)
        {
            factor = entityId == -1 ? 1f : Factor(GameManager.Instance.World?.GetEntity(entityId));
        }
    }

    public static void End()
    {
        if (--depth <= 0)
        {
            depth = 0;
            factor = 1f;
        }
    }

    public static float Current => depth > 0 && factor > 0f ? factor : 1f;

    /// <summary>A Stalker that hasn't been seen, or a Possum playing dead, makes no sound at all.</summary>
    public static bool Silent => depth > 0 && factor < 0f;

    private static float Factor(Entity e)
    {
        if (e == null)
        {
            return 1f;
        }
        ZedProfile p = ZedStore.Get(e.entityId);
        if (p == null)
        {
            return 1f;
        }
        if ((p.Has(ZedMutation.Stalker) && !p.Revealed) || p.PlayingDead)
        {
            return -1f;
        }
        return ZedSettings.Voices ? p.Pitch : 1f;
    }
}

[HarmonyPatch(typeof(Audio.Manager), nameof(Audio.Manager.Play), new[] { typeof(Entity), typeof(string), typeof(float), typeof(bool) })]
public class ZedVoicePlayEntityPatch
{
    public static void Prefix(Entity _entity)
    {
        ZedVoice.Begin(_entity);
    }

    public static Exception Finalizer(Exception __exception)
    {
        ZedVoice.End();
        return __exception;
    }
}

[HarmonyPatch(typeof(Audio.Manager), nameof(Audio.Manager.Play), new[] { typeof(Vector3), typeof(string), typeof(int), typeof(bool), typeof(float) })]
public class ZedVoicePlayPositionPatch
{
    public static void Prefix(int entityId)
    {
        ZedVoice.Begin(entityId);
    }

    public static Exception Finalizer(Exception __exception)
    {
        ZedVoice.End();
        return __exception;
    }
}

[HarmonyPatch(typeof(Audio.Manager), nameof(Audio.Manager.SetPitch))]
public class ZedVoicePitchPatch
{
    public static void Postfix(AudioSource _src)
    {
        if (_src == null)
        {
            return;
        }
        if (ZedVoice.Silent)
        {
            _src.volume = 0f;
            return;
        }
        float f = ZedVoice.Current;
        if (Math.Abs(f - 1f) > 0.001f)
        {
            _src.pitch *= f;
        }
    }
}
