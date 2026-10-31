using UnityEngine;

/// <summary>
/// Reads every book and schematic in the open loot container, the same way the inventory's Read button reads one:
/// each copy goes through the item's own action (ItemActionEat.ExecuteInstantAction) with the container slot it is
/// in, so its effects fire as normal (perks, recipes, experience, challenges) and the slot updates the container
/// like taking an item out does, which also keeps it in sync in multiplayer.
/// Books the player already knows are left in the container (they're worth selling), and so are the spare copies
/// once one copy has been read. Slots the player has locked are skipped.
/// </summary>
public static class ReadAllBooksCore
{
    static readonly FastTags<TagGroup.Global> BookTags = FastTags<TagGroup.Global>.Parse("books");

    public static void ReadAll(XUiC_LootWindow window)
    {
        EntityPlayerLocal player = window?.xui?.playerUI?.entityPlayer;
        XUiC_LootContainer container = window?.lootContainer;
        if (player == null || container == null || player.IsDead())
            return;

        int read = 0;
        int known = 0;
        foreach (XUiC_ItemStack slot in container.GetItemStackControllers())
        {
            if (slot == null || slot.UserLockedSlot || slot.IsLocked)
                continue;
            ItemStack stack = slot.ItemStack;
            if (stack == null || stack.IsEmpty())
                continue;
            ItemClass itemClass = stack.itemValue.ItemClass;
            if (itemClass == null || !itemClass.HasAnyTags(BookTags) || itemClass.Actions == null
                || itemClass.Actions.Length == 0 || itemClass.Actions[0] == null)
                continue;

            int type = stack.itemValue.type;
            int copies = stack.count;
            for (int i = 0; i < copies; i++)
            {
                ItemStack current = slot.ItemStack;
                if (current == null || current.IsEmpty() || current.itemValue.type != type)
                    break;
                if (XUiM_ItemStack.CheckKnown(player, itemClass, current.itemValue))
                {
                    known += current.count;
                    break;
                }
                if (!itemClass.CanExecuteAction(0, player, current.itemValue))
                    break;

                // Like the Read button: the action uses up one copy from the slot itself, so it gets a copy of one
                // (giving it the slot's own stack would take two)
                itemClass.Actions[0].ExecuteInstantAction(player, new ItemStack(current.itemValue.Clone(), 1), false, slot);
                read++;
            }
        }

        if (read == 0 && known == 0)
            GameManager.ShowTooltip(player, Localization.Get("xuiReadAllBooksNone"));
        else if (known == 0)
            GameManager.ShowTooltip(player, string.Format(Localization.Get("xuiReadAllBooksDone"), read));
        else
            GameManager.ShowTooltip(player, string.Format(Localization.Get("xuiReadAllBooksDoneKnown"), read, known));
    }
}
