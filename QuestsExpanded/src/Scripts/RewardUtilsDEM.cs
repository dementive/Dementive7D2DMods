/// <summary>
/// Giving the local player experience and items, the way quest rewards do.
/// </summary>
public static class RewardUtilsDEM
{
    public const string Dukes = "casinoCoin";

    public static void GiveExp(EntityPlayerLocal player, int exp)
    {
        if (player != null && exp > 0)
            player.Progression.AddLevelExp(exp, "_xpFromQuest", Progression.XPTypes.Quest);
    }

    /// <summary>
    /// Puts the items in the player's inventory, dropping what doesn't fit at their feet.
    /// </summary>
    public static void GiveItem(EntityPlayerLocal player, ItemStack stack)
    {
        if (player == null || stack == null || stack.IsEmpty())
            return;
        XUiM_PlayerInventory inventory = LocalPlayerUI.GetUIForPlayer(player).xui.PlayerInventory;
        if (!inventory.AddItem(stack, true))
            inventory.DropItem(stack);
    }

    public static void GiveDukes(EntityPlayerLocal player, int dukes)
    {
        ItemValue coin = ItemClass.GetItem(Dukes);
        if (dukes <= 0 || coin == null || coin.type == ItemValue.None.type)
            return;
        int stackSize = coin.ItemClass.Stacknumber.Value;
        while (dukes > 0)
        {
            int count = System.Math.Min(dukes, stackSize);
            GiveItem(player, new ItemStack(coin.Clone(), count));
            dukes -= count;
        }
    }
}

/// <summary>
/// A reward that pays experience and dukes worked out when the quest is turned in (so a contract can hold them).
/// </summary>
public interface IPotRewardDEM
{
    int PotExp { get; }

    int PotDukes { get; }
}
