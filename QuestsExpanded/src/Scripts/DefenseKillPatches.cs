using HarmonyLib;

/// <summary>
/// Tells the wave director about every enemy that dies on the server, so a defense counts every kill in its area
/// toward the wave: zombies drawn in by gunfire count as much as the wave's own (see Defense.OnEnemyDied). Other
/// deaths go to the NPC quests, so a survivor or refugee that dies is lost even if nobody finds the body.
/// </summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.OnEntityDeath))]
public static class DefenseKillPatches
{
    public static void Postfix(EntityAlive __instance)
    {
        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
            return;
        if (__instance is EntityEnemy)
            WaveDirectorDEM.EnemyDied(__instance);
        else if (!(__instance is EntityPlayer))
            WaveDirectorDEM.NpcDied(__instance);
    }
}
