using HarmonyLib;
using System;
using System.Collections.Generic;

/// <summary>
/// Patches that make quests with Craft objectives (commissions) work: traders only offer them when the player can
/// craft the items, offer a different one each time, and in a party everyone's crafting counts toward a shared
/// commission.
/// </summary>
public static class CommissionPatches
{
    /// <summary>
    /// Unique keys of repeatable quests a trader offers one of at a time, picked at random: commissions and Blood Moon
    /// Bounties.
    /// </summary>
    public static readonly string[] ShuffledKeys = { "commission", "bloodmoonbounty" };

    /// <summary>True while a trader builds its quest offers (see <see cref="EntityTraderPopulateActiveQuests"/>).</summary>
    private static bool populating;

    /// <summary>
    /// Vanilla puts every quest with a unique_key in the trader's specialQuestList and offers, for each key, the first
    /// entry in list order the player hasn't completed (QuestJournal.FindCompletedQuest; completed quests stay in the
    /// journal for good). So the trader always offered the same commission or Blood Moon Bounty, and each one only
    /// once a game. While a trader builds its offers, those entries are shuffled among the places they already hold
    /// in the list (vanilla's own keyed quests keep their order), and having done one before doesn't rule it out.
    /// </summary>
    [HarmonyPatch(typeof(EntityTrader), nameof(EntityTrader.PopulateActiveQuests))]
    public static class EntityTraderPopulateActiveQuests
    {
        public static void Prefix(EntityTrader __instance)
        {
            populating = true;
            // The original builds the lists on first use; build them now so the first offer is shuffled too
            if (__instance.questDictionary != null && __instance.questDictionary.Count == 0)
                __instance.PopulateQuestList();
            ShuffleRepeatable(__instance.specialQuestList, __instance.rand);
        }

        public static Exception Finalizer(Exception __exception)
        {
            populating = false;
            return __exception;
        }
    }

    /// <summary>
    /// While a trader builds its offers, a completed commission or Blood Moon Bounty can be offered again (see
    /// <see cref="EntityTraderPopulateActiveQuests"/>).
    /// </summary>
    [HarmonyPatch(typeof(QuestJournal), nameof(QuestJournal.FindCompletedQuest))]
    public static class QuestJournalFindCompletedQuest
    {
        public static bool Prefix(string questName, ref bool __result)
        {
            if (!populating || questName == null || !IsShuffled(QuestClass.GetQuest(questName)))
                return true;
            __result = false;
            return false;
        }
    }

    /// <summary>
    /// Vanilla's Craft objective adds each crafted stack to its byte-sized count with no cap, so a big stack (a
    /// workstation that crafted with its window closed hands over everything it made at once) could wrap the count
    /// past 255 back to a small number. The same checks as vanilla, but the count stops at what the objective needs.
    /// </summary>
    [HarmonyPatch(typeof(ObjectiveCraft), nameof(ObjectiveCraft.Current_CraftItem))]
    public static class ObjectiveCraftCurrentCraftItem
    {
        public static bool Prefix(ObjectiveCraft __instance, ItemStack stack)
        {
            if (__instance.Complete || stack == null || stack.itemValue == null || __instance.expectedItem == null)
                return false;
            if (stack.itemValue.type != __instance.expectedItem.type || !__instance.OwnerQuest.CheckRequirements())
                return false;

            int count = Math.Min(Math.Min(__instance.CurrentValue + stack.count, __instance.itemCount), 255);
            __instance.CurrentValue = (byte)Math.Max(count, 0);
            __instance.Refresh();
            return false;
        }
    }

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

    /// <summary>
    /// Returns true for a repeatable quest whose unique key is one of <see cref="ShuffledKeys"/>.
    /// </summary>
    public static bool IsShuffled(QuestClass questClass)
    {
        return questClass != null && questClass.Repeatable && Array.IndexOf(ShuffledKeys, questClass.UniqueKey) >= 0;
    }

    /// <summary>
    /// Shuffles the entries of <see cref="ShuffledKeys"/> quests among the places they hold in the list (Fisher-Yates
    /// over just those places), leaving every other entry where it is.
    /// </summary>
    private static void ShuffleRepeatable(List<QuestEntry> list, GameRandom random)
    {
        if (list == null || random == null)
            return;

        var places = new List<int>();
        for (int i = 0; i < list.Count; i++)
        {
            if (IsShuffled(list[i]?.QuestClass))
                places.Add(i);
        }
        for (int i = places.Count - 1; i > 0; i--)
        {
            int j = random.RandomRange(i + 1);
            QuestEntry entry = list[places[i]];
            list[places[i]] = list[places[j]];
            list[places[j]] = entry;
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
