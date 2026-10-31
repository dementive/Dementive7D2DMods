using HarmonyLib;

/// <summary>
/// Traders only offer the NPC quests when the NPC mods they need are installed (see NpcCatalogDEM): Bandit Hideout
/// when one adds bandits, Rescue and Safehouse when one adds friendly NPCs that can follow a player.
/// </summary>
public static class NpcQuestPatches
{
    [HarmonyPatch(typeof(QuestEntry), nameof(QuestEntry.CheckRequirement))]
    public static class QuestEntryCheckRequirement
    {
        public static void Postfix(QuestEntry __instance, ref bool __result)
        {
            if (!__result || __instance.QuestClass == null)
                return;

            foreach (BaseObjective objective in __instance.QuestClass.Objectives)
            {
                if (objective is ObjectiveBanditHideoutDEM)
                {
                    __result = NpcCatalogDEM.HasHostile;
                    return;
                }
                if (objective is ObjectiveRescueDEM || objective is ObjectiveSafehouseDEM)
                {
                    __result = NpcCatalogDEM.HasFollowers;
                    return;
                }
            }
        }
    }
}
