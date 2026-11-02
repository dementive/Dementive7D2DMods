using System;
using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Where game juice hears about things. Every hook here runs on each player's machine for what the game already sends
/// it, so in multiplayer everyone sees everyone's juice. None of them changes what the game does, and a failure in one
/// is logged once and otherwise ignored, so juice can never break a fight.
/// </summary>
public static class GfxJuicePatches
{
    private struct Known
    {
        public string device;           // for impacts: what hit (bullet, metal, stone, wood, organic); null for breaks
        public GfxJuiceEffects.Surface surface;
        public bool tree;
    }

    /// <summary>The game's particles we act on, by the id it sends them under (the name's hash).</summary>
    private static Dictionary<int, Known> particles;
    private static readonly HashSet<string> failed = new HashSet<string>();

    private static readonly string[] Devices = { "bullet", "metal", "stone", "wood", "organic" };
    private static readonly string[] Categories = { "cloth", "earth", "glass", "metal", "organic", "plant", "snow", "stone", "water", "wood", "xt_tallgrass" };
    private static readonly string[] Trees =
    {
        "treeGib_birch", "treeGib_birch_15m", "treeGib_birch_6m", "treeGib_birch_small", "treeGib_burnt", "treeGib_burnt_55m",
        "treeGib_burnt_75m", "treeGib_burnt_small", "treeGib_dead_01", "treeGib_dead_02", "treeGib_maple_13m", "treeGib_maple_15m",
        "treeGib_maple_17m", "treeGib_sapling", "treeGib_small_dust", "treeGib_winter01", "treeGib_winter02", "treeGib_winter03",
        "treeGib_winter_small",
    };

    private static void BuildParticles()
    {
        particles = new Dictionary<int, Known>();
        foreach (string device in Devices)
        {
            foreach (string category in Categories)
            {
                Known known = new Known { device = device, surface = GfxJuiceEffects.ParseCategory(category) };
                string name = "impact_" + device + "_on_" + category;
                particles[ParticleEffect.ToId(name)] = known;
                particles[ParticleEffect.ToId(name + "_harvest")] = known;
            }
        }
        foreach (string category in new[] { "boulder", "cloth", "earth", "glass", "metal", "organic", "plant", "snow", "stone", "water", "wood", "xt_tallgrass", "xt_leaves1", "xt_leaves2", "xt_leaves3" })
            particles[ParticleEffect.ToId("blockdestroy_" + category)] = new Known { surface = GfxJuiceEffects.ParseCategory(category) };
        particles[ParticleEffect.ToId("door_damage_metal")] = new Known { surface = GfxJuiceEffects.Surface.Metal };
        particles[ParticleEffect.ToId("door_damage_wood")] = new Known { surface = GfxJuiceEffects.Surface.Wood };
        for (int i = 1; i <= 6; i++)
            particles[ParticleEffect.ToId("car_destruction_dmg" + i)] = new Known { surface = GfxJuiceEffects.Surface.Metal };
        foreach (string tree in Trees)
            particles[ParticleEffect.ToId(tree)] = new Known { surface = GfxJuiceEffects.Surface.Wood, tree = true };
    }

    /// <summary>
    /// Every particle the game shows on any machine comes through ParticleEffect.SpawnParticleEffect, including the
    /// ones other machines send: impacts (impact_{device}_on_{surface}, at the point hit, turned to the block face it
    /// hit) and blocks breaking (blockdestroy_*, doors, trees, cars).
    /// </summary>
    public static void OnGameParticle(ParticleEffect effect, int causedBy, bool worldPosition)
    {
        if (effect == null || !GfxJuice.Loaded)
            return;
        if (particles == null)
            BuildParticles();
        if (!particles.TryGetValue(effect.ParticleId, out Known known))
            return;
        Vector3 at = worldPosition ? effect.pos : effect.pos + Origin.position;
        if (known.device != null)
        {
            if (!GfxJuiceEffects.IsCreatureSurface(known.surface))
                GfxJuiceEffects.Impact(known.device, known.surface, at, effect.rot * Vector3.up, effect.color, causedBy);
        }
        else
            GfxJuiceEffects.Broke(known.surface, at, effect.color, known.tree);
    }

    /// <summary>Logs the first failure of each hook, then stays quiet about it.</summary>
    public static void Failed(string hook, Exception e)
    {
        if (failed.Add(hook))
            Log.Warning("[GraphicsExpanded] Game juice skipped " + hook + ": " + e);
    }
}

[HarmonyPatch(typeof(ParticleEffect), nameof(ParticleEffect.SpawnParticleEffect))]
public class GfxPatch_JuiceParticles
{
    static void Postfix(ParticleEffect _pe, int _entityThatCausedIt, bool _isWorldPos)
    {
        try
        {
            GfxJuicePatches.OnGameParticle(_pe, _entityThatCausedIt, _isWorldPos);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a particle", e);
        }
    }
}

/// <summary>A creature took damage: on every machine tracking it, once (the attacker's, the server's and every other client's).</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ProcessDamageResponseLocal))]
public class GfxPatch_JuiceDamage
{
    static void Prefix(EntityAlive __instance, out bool __state)
    {
        __state = __instance.IsDead();
    }

    static void Postfix(EntityAlive __instance, DamageResponse _dmResponse, bool __state)
    {
        try
        {
            GfxJuiceEffects.Damage(__instance, _dmResponse, __state);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a hit", e);
        }
    }
}

/// <summary>A gun fired: on the shooter's machine and every machine near them, once a shot.</summary>
[HarmonyPatch(typeof(ItemActionRanged), nameof(ItemActionRanged.ItemActionEffects))]
public class GfxPatch_JuiceGunfire
{
    static void Postfix(ItemActionData _actionData, int _firingState)
    {
        if (_firingState == 0)
            return;
        try
        {
            if (_actionData is ItemActionRanged.ItemActionDataRanged ranged && ranged.invData != null)
                GfxJuiceEffects.Fired(ranged.invData.holdingEntity, ranged.invData.itemValue, ranged.muzzle);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a shot", e);
        }
    }
}

/// <summary>Block changes, on every machine. Read before they apply, to tell a block taking damage from one being replaced.</summary>
[HarmonyPatch(typeof(GameManager), nameof(GameManager.ChangeBlocks))]
public class GfxPatch_JuiceBlockChanges
{
    static void Prefix(GameManager __instance, List<BlockChangeInfo> _blocksToChange)
    {
        if (_blocksToChange == null || _blocksToChange.Count == 0 || _blocksToChange.Count > 8 || !GfxJuice.On(GfxJuice.Area.Breaking))
            return;
        try
        {
            World world = __instance.World;
            foreach (BlockChangeInfo change in _blocksToChange)
            {
                if (!change.bChangeBlockValue && !change.bChangeDamage || !change.blockValueRef.TryGetBlockPos(out Vector3i pos))
                    continue;
                BlockValue old = world.GetBlock(pos);
                if (!old.isair && old.type == change.blockValue.type && change.blockValue.damage > old.damage)
                    GfxJuiceEffects.BlockDamaged(pos.ToVector3() + new Vector3(0.5f, 0.5f, 0.5f));
            }
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a block change", e);
        }
    }
}

/// <summary>An explosion, on every machine.</summary>
[HarmonyPatch(typeof(GameManager), nameof(GameManager.ExplosionClient))]
public class GfxPatch_JuiceExplosion
{
    static void Postfix(GameManager __instance, Vector3 _center, float _blastRadius)
    {
        try
        {
            GfxJuiceEffects.Exploded(_center, _blastRadius, __instance.World?.GetPrimaryPlayer());
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("an explosion", e);
        }
    }
}

/// <summary>A footstep with its surface: the local player's, other players', zombies' and animals', wherever they're heard.</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.PlayStepSound), new[] { typeof(string), typeof(float) })]
public class GfxPatch_JuiceStep
{
    static void Postfix(EntityAlive __instance, string stepSound)
    {
        try
        {
            GfxJuiceEffects.Step(__instance, stepSound);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a footstep", e);
        }
    }
}

[HarmonyPatch(typeof(EntityPlayerLocal), nameof(EntityPlayerLocal.FallImpact))]
public class GfxPatch_JuiceLanding
{
    static void Prefix(EntityPlayerLocal __instance, float speed)
    {
        try
        {
            GfxJuiceEffects.Landed(__instance, speed);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a landing", e);
        }
    }
}

/// <summary>Experience is added on the player's own machine; a level gained shows there.</summary>
[HarmonyPatch(typeof(Progression), nameof(Progression.AddLevelExp))]
public class GfxPatch_JuiceLevelUp
{
    static void Prefix(Progression __instance, out int __state)
    {
        __state = __instance.Level;
    }

    static void Postfix(Progression __instance, int __state)
    {
        try
        {
            if (__instance.Level > __state && __instance.parent is EntityPlayerLocal player)
                GfxJuiceEffects.LevelUp(player);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a level-up", e);
        }
    }
}

[HarmonyPatch(typeof(Quest), nameof(Quest.CloseQuest))]
public class GfxPatch_JuiceQuestDone
{
    static void Postfix(Quest __instance, Quest.QuestState finalState)
    {
        try
        {
            if (finalState == Quest.QuestState.Completed && __instance.OwnerJournal?.OwnerPlayer != null)
                GfxJuiceEffects.QuestDone(__instance.OwnerJournal.OwnerPlayer);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("a finished quest", e);
        }
    }
}

/// <summary>An item lying on the ground got its model, on every machine that sees it.</summary>
[HarmonyPatch(typeof(EntityItem), nameof(EntityItem.createMesh))]
public class GfxPatch_JuiceLoot
{
    static void Postfix(EntityItem __instance)
    {
        try
        {
            GfxJuiceEffects.ItemShown(__instance);
        }
        catch (Exception e)
        {
            GfxJuicePatches.Failed("an item", e);
        }
    }
}
