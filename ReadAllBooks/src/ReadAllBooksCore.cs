using System;

/// <summary>
/// Reads every book, skill magazine and schematic in the open loot container, or in the player's backpack, the same
/// way the inventory's Read button reads one: each copy goes through the item's own action
/// (ItemActionEat.ExecuteInstantAction) with the slot it is in, so its effects fire as normal (perks, recipes, crafting
/// skill levels, experience, challenges) and the slot updates its container like taking an item out does (the loot
/// container stays in sync in multiplayer, the backpack saves to the player's bag).
/// Books the player already knows are left where they are (they're worth selling), and so are the spare copies
/// once one copy has been read. Magazines are read copy by copy until their crafting skill is maxed (that's when the
/// game counts them as known). Slots the player has locked are skipped.
/// </summary>
public static class ReadAllBooksCore
{
    // "books": books and schematics; "csm": skill magazines, including BooksExpanded's, which extend them
    static readonly FastTags<TagGroup.Global> BookTags = FastTags<TagGroup.Global>.Parse("books,csm");

    public static void ReadAll(XUiC_LootWindow window, string source)
    {
        int read = Read(window, window?.lootContainer, "container", source, "xuiReadAllBooksNone", "xuiReadAllBooksDoneKnown");
        // Like Take All: when the books were all that was in it, the container closes (the game's own way, a frame later)
        if (read > 0 && IsEmpty(window.lootContainer))
        {
            Log.Out("[ReadAllBooks] " + source + ": the container is empty now, closing it");
            ThreadManager.StartCoroutine(window.closeInventoryLater());
        }
    }

    // Only the backpack's own grid: the toolbelt is a separate window
    public static void ReadAll(XUiC_BackpackWindow window, string source)
    {
        Read(window, window?.backpackGrid, "backpack", source, "xuiReadAllBooksBackpackNone", "xuiReadAllBooksBackpackDoneKnown");
    }

    // Called from the button and the hotkey, so an error is logged instead of breaking the window. Returns how many
    // copies were read
    static int Read(XUiController window, XUiC_ItemStackGrid grid, string gridName, string source, string noneKey,
        string doneKnownKey)
    {
        try
        {
            return ReadGrid(window, grid, gridName, source, noneKey, doneKnownKey);
        }
        catch (Exception e)
        {
            Log.Error("[ReadAllBooks] Failed to read books: " + e);
            return 0;
        }
    }

    static bool IsEmpty(XUiC_ItemStackGrid grid)
    {
        foreach (XUiC_ItemStack slot in grid.GetItemStackControllers())
        {
            if (slot?.ItemStack != null && !slot.ItemStack.IsEmpty())
                return false;
        }
        return true;
    }

    static int ReadGrid(XUiController window, XUiC_ItemStackGrid grid, string gridName, string source, string noneKey,
        string doneKnownKey)
    {
        EntityPlayerLocal player = window?.xui?.playerUI?.entityPlayer;
        if (player == null || grid == null || player.IsDead())
        {
            Log.Warning("[ReadAllBooks] " + source + " in the " + gridName + ": nothing to read from (player "
                + (player == null ? "missing" : player.IsDead() ? "dead" : "ok") + ", grid " + (grid == null ? "missing" : "ok") + ")");
            return 0;
        }

        int read = 0;
        int known = 0;
        int filled = 0;
        foreach (XUiC_ItemStack slot in grid.GetItemStackControllers())
        {
            if (slot == null || slot.UserLockedSlot || slot.IsLocked)
                continue;
            ItemStack stack = slot.ItemStack;
            if (stack == null || stack.IsEmpty())
                continue;
            filled++;
            ItemClass itemClass = stack.itemValue.ItemClass;
            if (itemClass == null || !itemClass.HasAnyTags(BookTags) || itemClass.Actions == null
                || itemClass.Actions.Length == 0 || itemClass.Actions[0] == null)
                continue;

            int type = stack.itemValue.type;
            int copies = stack.count;
            for (int i = 0; i < copies; i++)
            {
                // Re-read every copy: in the backpack each read rebuilds the grid's stacks from the bag
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

        // Like the Read button: the slots' counts redraw (a stack read down to its known copies would show the old count)
        if (read > 0)
            window.SetAllChildrenDirty();

        Log.Out("[ReadAllBooks] " + source + " in the " + gridName + ": read " + read + ", already known " + known
            + " (" + filled + " unlocked slots with items)");

        if (read == 0 && known == 0)
            GameManager.ShowTooltip(player, Localization.Get(noneKey));
        else if (known == 0)
            GameManager.ShowTooltip(player, string.Format(Localization.Get("xuiReadAllBooksDone"), read));
        else
            GameManager.ShowTooltip(player, string.Format(Localization.Get(doneKnownKey), read, known));
        return read;
    }
}
