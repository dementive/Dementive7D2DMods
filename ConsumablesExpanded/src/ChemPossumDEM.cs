using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

/// <summary>Possum Pills. Zombies think on the server, so everything here reads a cvar the buff sets: buffs run on the
/// server's copy of a player too.</summary>
public static class ChemPossumDEM
{
    private const string PlayingDeadCVar = "%dementivePlayingDead";
    private const float ScatterRange = 30f;
    private const float WalkOffMin = 15f;
    private const float WalkOffMax = 25f;
    private const int WalkOffTicks = 600;
    private const float CheckInterval = .25f;

    private static readonly HashSet<int> scattered = new HashSet<int>();
    private static readonly List<Entity> found = new List<Entity>();
    private static float nextCheck;

    public static bool AnyPlayingDead => scattered.Count > 0;

    public static bool IsPlayingDead(Entity _entity)
    {
        return _entity is EntityPlayer player && player.Buffs != null && player.Buffs.GetCustomVar(PlayingDeadCVar) > 0f;
    }

    public static void Update()
    {
        var connections = SingletonMonoBehaviour<ConnectionManager>.Instance;
        var world = GameManager.Instance.World;
        if (world == null || connections == null || !connections.IsServer || Time.unscaledTime < nextCheck)
            return;
        nextCheck = Time.unscaledTime + CheckInterval;

        foreach (var player in world.Players.list)
        {
            if (!IsPlayingDead(player))
                scattered.Remove(player.entityId);
            else if (scattered.Add(player.entityId))
                Scatter(world, player);
        }
    }

    public static void Reset()
    {
        scattered.Clear();
        found.Clear();
    }

    /// <summary>Losing a target alone leaves zombies standing over the spot they last saw the player, so they're also
    /// sent somewhere else, roughly away from the player so they don't walk across the body.</summary>
    private static void Scatter(World _world, EntityPlayer _player)
    {
        found.Clear();
        _world.GetEntitiesInBounds(typeof(EntityEnemy), new Bounds(_player.position, Vector3.one * ScatterRange * 2f), found);
        foreach (var entity in found)
        {
            var enemy = entity as EntityEnemy;
            if (enemy == null || enemy.IsDead())
                continue;
            if (enemy.GetAttackTarget() == _player)
                enemy.SetAttackTarget(null, 0);
            if (enemy.GetRevengeTarget() == _player)
                enemy.SetRevengeTarget(null);

            var away = enemy.position - _player.position;
            away.y = 0f;
            if (away.sqrMagnitude < .01f)
                away = Vector3.forward;
            away = Quaternion.Euler(0f, Random.Range(-50f, 50f), 0f) * away.normalized;
            enemy.ClearInvestigatePosition();
            enemy.SetInvestigatePosition(_player.position + away * Random.Range(WalkOffMin, WalkOffMax), WalkOffTicks, false);
        }
        found.Clear();
    }
}

/// <summary>The game already skips ignored players when zombies look for targets, hear noises or pick Blood Moon
/// targets, so this one check covers all of them.</summary>
[HarmonyPatch(typeof(Entity), nameof(Entity.IsIgnoredByAI))]
public static class IgnoredByAIPatchDEM
{
    public static void Postfix(Entity __instance, ref bool __result)
    {
        if (!__result && ChemPossumDEM.IsPlayingDead(__instance))
            __result = true;
    }
}

/// <summary>A Blood Moon zombie with no player to chase is killed if it's over 60 m away, so a solo player playing dead
/// would wipe out the far side of the horde. This leaves them as they are until the player gets up.</summary>
[HarmonyPatch(typeof(AIDirectorBloodMoonParty), nameof(AIDirectorBloodMoonParty.SeekTarget))]
public static class SeekTargetPatchDEM
{
    public static bool Prefix(ref bool __result)
    {
        if (!ChemPossumDEM.AnyPlayingDead)
            return true;
        __result = true;
        return false;
    }
}
