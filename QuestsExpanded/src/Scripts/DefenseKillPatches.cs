using HarmonyLib;

/// <summary>
/// Tells the wave director about every enemy that dies on the server, so a defense counts every kill in its area
/// toward the wave: zombies drawn in by gunfire count as much as the wave's own (see Defense.OnEnemyDied).
/// </summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.OnEntityDeath))]
public static class DefenseKillPatches
{
    public static void Postfix(EntityAlive __instance)
    {
        if (__instance is EntityEnemy && SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
            WaveDirectorDEM.EnemyDied(__instance);
    }
}
