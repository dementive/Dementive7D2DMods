using HarmonyLib;

/// <summary>
/// Patches that make quests with Craft objectives (commissions) work: traders only offer them when the player can
/// craft the items, and in a party everyone's crafting counts toward a shared commission.
/// </summary>
public static class CommissionPatches
{
    /// <summary>
    /// Traders don't offer a quest with a Craft objective unless the player has unlocked the recipe of every item
    /// it asks for, so a commission is never impossible. The check runs wherever the trader builds its quest list
    /// (the server in multiplayer), which has the player's recipe unlocks.
    /// </summary>
    [HarmonyPatch(typeof(QuestEntry), nameof(QuestEntry.CheckRequirement))]
    public static class QuestEntryCheckRequirement
    {
        public static void Postfix(QuestEntry __instance, EntityPlayer player, ref bool __result)
        {
            if (!__result || player == null || __instance.QuestClass == null)
                return;

            foreach (BaseObjective objective in __instance.QuestClass.Objectives)
            {
                if (objective is ObjectiveCraft && !CanCraft(player, objective.ID))
                {
                    __result = false;
                    return;
                }
            }
        }
    }

    /// <summary>
    /// Vanilla's Craft objective only counts the player's own crafting. When the local player crafts something a
    /// quest is waiting for, this sends it to the party, and party members with the same shared quest get the
    /// credit too (see <see cref="NetPackageSharedCraftDEM"/>).
    /// </summary>
    [HarmonyPatch(typeof(QuestEventManager), nameof(QuestEventManager.CraftedItem))]
    public static class QuestEventManagerCraftedItem
    {
        public static void Postfix(ItemStack newStack)
        {
            EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
            if (player == null || player.Party == null || newStack == null || newStack.IsEmpty())
                return;

            string itemName = newStack.itemValue.ItemClass?.GetItemName();
            if (itemName == null)
                return;

            foreach (Quest quest in player.QuestJournal.quests)
            {
                if (quest.CurrentState != Quest.QuestState.InProgress || !WaitsForCraft(quest, itemName))
                    continue;

                NetPackageSharedCraftDEM package = NetPackageManager.GetPackage<NetPackageSharedCraftDEM>()
                    .Setup(player.entityId, quest.QuestCode, itemName, newStack.count);

                if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
                    package.Relay(GameManager.Instance.World);
                else
                    SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(package);
            }
        }
    }

    public static bool CanCraft(EntityPlayer player, string itemName)
    {
        Recipe recipe = CraftingManager.GetRecipe(itemName);
        return recipe != null && recipe.IsUnlocked(player);
    }

    /// <summary>
    /// Returns true if the quest has a Craft objective for the item in its current phase.
    /// </summary>
    public static bool WaitsForCraft(Quest quest, string itemName)
    {
        foreach (BaseObjective objective in quest.Objectives)
        {
            if (objective is ObjectiveCraft craft
                && craft.Phase == quest.CurrentPhase
                && craft.expectedItemClass != null
                && craft.expectedItemClass.GetItemName() == itemName)
            {
                return true;
            }
        }
        return false;
    }
}
