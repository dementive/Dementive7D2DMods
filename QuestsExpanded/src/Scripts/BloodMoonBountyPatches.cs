using HarmonyLib;

/// <summary>
/// Traders only offer a Blood Moon Bounty (a quest with a BloodMoonBountyDEM objective) in the 2 days before a
/// blood moon and on the day of it, until it starts.
/// </summary>
public static class BloodMoonBountyPatches
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
                if (objective is ObjectiveBloodMoonBountyDEM)
                {
                    __result = BloodMoonComing();
                    return;
                }
            }
        }
    }

    public static bool BloodMoonComing()
    {
        World world = GameManager.Instance.World;
        if (world == null)
            return false;
        int day = GameUtils.WorldTimeToDays(world.worldTime);
        int bloodMoonDay = GameStats.GetInt(EnumGameStats.BloodMoonDay);
        return day >= bloodMoonDay - 2 && day <= bloodMoonDay && !WaveDirectorDEM.IsBloodMoonNow(world);
    }
}
