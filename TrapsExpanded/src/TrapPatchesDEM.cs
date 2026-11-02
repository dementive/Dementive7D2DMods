using HarmonyLib;
using UnityEngine;

/// <summary>Kills: works out which trap or player killed each zombie (see TrapKillsDEM).</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ClientKill))]
public static class TrapKillPatch
{
    public static void Postfix(EntityAlive __instance, DamageResponse _dmResponse)
    {
        TrapKillsDEM.Killed(__instance, _dmResponse);
    }
}

/// <summary>
/// Frozen zombies take double damage from blunt and crushing hits (Shatter: the Ram, the Swinging Log, clubs and
/// sledges), wherever the hit is worked out. On the server, vanilla turrets and blade traps hit harder as they level
/// up, like the mod's own traps.
/// </summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.DamageEntity))]
public static class TrapDamagePatch
{
    public static void Prefix(EntityAlive __instance, DamageSource _damageSource, ref int _strength)
    {
        if (!(__instance is EntityEnemy) || _damageSource == null || _strength <= 0)
        {
            return;
        }
        EnumDamageTypes type = _damageSource.GetDamageType();
        if ((type == EnumDamageTypes.Bashing || type == EnumDamageTypes.Crushing) && TrapStatusDEM.IsFrozen(__instance))
        {
            _strength *= 2;
            if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
            {
                BloodMoonDEM.Combo(BloodMoonDEM.ComboShatter);
            }
        }
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer && TrapKillsDEM.InVanillaTrap(out Vector3i pos))
        {
            _strength = Mathf.RoundToInt(_strength * TrapLevelsDEM.Damage(TrapStoreDEM.LevelAt(pos)));
        }
    }
}

/// <summary>Counts Infernos and freezes for the Blood Moon report, however they started.</summary>
[HarmonyPatch(typeof(EntityBuffs), nameof(EntityBuffs.AddBuff),
    new[] { typeof(string), typeof(Vector3i), typeof(int), typeof(bool), typeof(bool), typeof(float) })]
public static class TrapBuffPatch
{
    public static void Prefix(EntityBuffs __instance, string _name, out bool __state)
    {
        __state = __instance != null && __instance.HasBuff(_name);
    }

    public static void Postfix(EntityBuffs __instance, string _name, EntityBuffs.BuffStatus __result, bool __state)
    {
        if (__state || __result != EntityBuffs.BuffStatus.Added
            || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        if (_name == TrapStatusDEM.Inferno)
        {
            BloodMoonDEM.Combo(BloodMoonDEM.ComboInferno);
        }
        else if (_name == TrapStatusDEM.Frozen)
        {
            BloodMoonDEM.Combo(BloodMoonDEM.ComboFrozen);
        }
    }
}

/// <summary>Vanilla turrets: their shots count for the turret. The finalizer runs even if the game's code throws, so
/// the turret's context can't stick.</summary>
[HarmonyPatch(typeof(AutoTurretFireController), nameof(AutoTurretFireController.Fire))]
public static class TrapTurretPatch
{
    public static void Prefix(AutoTurretFireController __instance, out bool __state)
    {
        __state = false;
        TileEntityPoweredRangedTrap te = __instance.TileEntity;
        if (te == null || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        Vector3i pos = te.ToWorldPos();
        TrapKillsDEM.Begin(pos, GameManager.Instance.World.GetBlock(pos).Block.GetBlockName(), false, true);
        __state = true;
    }

    public static void Finalizer(bool __state)
    {
        if (__state)
        {
            TrapKillsDEM.End();
        }
    }
}

/// <summary>Vanilla blade traps: their cuts count for the trap.</summary>
[HarmonyPatch(typeof(SpinningBladeTrapBladeController), nameof(SpinningBladeTrapBladeController.Update))]
public static class TrapBladePatch
{
    public static void Prefix(SpinningBladeTrapBladeController __instance, out bool __state)
    {
        __state = false;
        TileEntityPoweredMeleeTrap te = __instance.OwnerTE;
        if (te == null || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        Vector3i pos = te.ToWorldPos();
        TrapKillsDEM.Begin(pos, GameManager.Instance.World.GetBlock(pos).Block.GetBlockName(), false, true);
        __state = true;
    }

    public static void Finalizer(bool __state)
    {
        if (__state)
        {
            TrapKillsDEM.End();
        }
    }
}

/// <summary>A vanilla turret or blade trap that's picked up or destroyed loses its level, like the mod's traps.
/// BlockRanged doesn't override OnBlockRemoved; BlockBladeTrap does, so both are patched (Removed ignores a second
/// call).</summary>
[HarmonyPatch(typeof(BlockPowered), nameof(BlockPowered.OnBlockRemoved))]
public static class TrapVanillaRemovedPatch
{
    public static void Postfix(Block __instance, Vector3i _blockPos, BlockValue _blockValue)
    {
        if ((__instance is BlockRanged || __instance is BlockBladeTrap) && !_blockValue.ischild)
        {
            TrapStoreDEM.Removed(GameManager.Instance.World, _blockPos);
        }
    }
}

[HarmonyPatch(typeof(BlockBladeTrap), nameof(BlockBladeTrap.OnBlockRemoved))]
public static class TrapBladeRemovedPatch
{
    public static void Postfix(Vector3i _blockPos, BlockValue _blockValue)
    {
        if (!_blockValue.ischild)
        {
            TrapStoreDEM.Removed(GameManager.Instance.World, _blockPos);
        }
    }
}

/// <summary>Vanilla turrets show their level and kills when you look at them.</summary>
[HarmonyPatch(typeof(BlockRanged), nameof(BlockRanged.GetActivationText))]
public static class TrapTurretTextPatch
{
    public static void Postfix(WorldBase _world, BlockValue _blockValue, Vector3i _blockPos, ref string __result)
    {
        __result = VanillaTrapText.Add(__result, _world, _blockValue, _blockPos);
    }
}

/// <summary>Vanilla blade traps show their level and kills when you look at them.</summary>
[HarmonyPatch(typeof(BlockPowered), nameof(BlockPowered.GetActivationText))]
public static class TrapBladeTextPatch
{
    public static void Postfix(BlockPowered __instance, WorldBase _world, BlockValue _blockValue, Vector3i _blockPos,
        ref string __result)
    {
        if (__instance is BlockBladeTrap)
        {
            __result = VanillaTrapText.Add(__result, _world, _blockValue, _blockPos);
        }
    }
}

public static class VanillaTrapText
{
    public static string Add(string text, WorldBase world, BlockValue bv, Vector3i pos)
    {
        pos = TrapUiDEM.Parent(world, pos, ref bv);
        TrapRecordDEM rec = TrapStoreDEM.View(pos);
        int level = rec?.Level ?? 1;
        int kills = rec?.Kills ?? 0;
        int next = TrapLevelsDEM.NextAt(level);
        string line = next > 0
            ? string.Format(Localization.Get("dem_trapLevel"), level, kills, next)
            : string.Format(Localization.Get("dem_trapLevelMax"), level, kills);
        return string.IsNullOrEmpty(text) ? line : text + "\n" + line;
    }
}
