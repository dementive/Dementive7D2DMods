using System.Collections.Generic;
using System.Text;
using UnityEngine;

/// <summary>
/// What every trap shows when you look at it (level, kills, upgrade, loaded ammo) and the commands it adds to its
/// radial menu: Load, Load all nearby and Unload for traps that use ammo or fuel, the two upgrades once it reaches
/// level 3, and its own (re-arm, light). The radial labels are the localization keys blockcommand_&lt;command&gt;.
/// </summary>
public static class TrapUiDEM
{
    public const string CmdLoad = "dem_load";
    public const string CmdLoadAll = "dem_loadall";
    public const string CmdUnload = "dem_unload";
    public const string CmdUpgradeA = "dem_upgradeA";
    public const string CmdUpgradeB = "dem_upgradeB";
    private const string UpgradePrefix = "dem_up_";

    /// <summary>How far Load all nearby reaches from the player, in meters.</summary>
    public const float LoadAllRange = 15f;

    /// <summary>The most traps one Load all nearby loads (its package counts them in a byte).</summary>
    private const int LoadAllMax = 255;

    /// <summary>Client: until when a Load all nearby waits for the server's answer before another one can go.</summary>
    private static float loadAllWait;

    /// <summary>The radial command for one of a trap's upgrades (its label names the upgrade).</summary>
    public static string UpgradeCommand(string blockName, char upgrade)
    {
        return UpgradePrefix + blockName + "_" + upgrade;
    }

    /// <summary>A multi-block trap's commands and records live at its parent block.</summary>
    public static Vector3i Parent(WorldBase world, Vector3i pos, ref BlockValue bv)
    {
        if (bv.ischild && bv.Block != null && bv.Block.multiBlockPos != null)
        {
            pos = bv.Block.multiBlockPos.GetParentPos(pos, bv);
            bv = world.GetBlock(pos);
        }
        return pos;
    }

    public static BlockActivationCommand[] Commands(ITrapDEM trap, BlockActivationCommand[] baseCommands,
        WorldBase world, BlockValue bv, Vector3i pos, EntityAlive focusing)
    {
        pos = Parent(world, pos, ref bv);
        List<BlockActivationCommand> list = new List<BlockActivationCommand>();
        if (baseCommands != null)
        {
            list.AddRange(baseCommands);
        }
        TrapSettingsDEM s = trap.Settings;
        TrapRecordDEM rec = TrapStoreDEM.View(pos);
        if (s.UsesAmmo)
        {
            bool full = rec != null && rec.AmmoTotal >= s.AmmoCapacity;
            list.Add(new BlockActivationCommand(CmdLoad, "add", !full && HasAmmo(focusing as EntityPlayerLocal, s)));
            list.Add(new BlockActivationCommand(CmdLoadAll, "store_all_down",
                HasAmmoNearby(focusing as EntityPlayerLocal)));
            list.Add(new BlockActivationCommand(CmdUnload, "backpack", rec != null && rec.AmmoTotal > 0));
        }
        trap.ExtraCommands(list, world, bv, pos, rec);
        if (s.HasUpgrades && rec != null && rec.Upgrade == 0 && rec.Level >= TrapLevelsDEM.UpgradeLevel)
        {
            list.Add(new BlockActivationCommand(UpgradeCommand(s.Name, 'A'), "block_upgrade", true));
            list.Add(new BlockActivationCommand(UpgradeCommand(s.Name, 'B'), "block_upgrade", true));
        }
        return list.ToArray();
    }

    /// <summary>Handles the mod's own commands. Returns false for the block's vanilla ones (take, light).</summary>
    public static bool OnCommand(ITrapDEM trap, string command, WorldBase world, Vector3i pos, BlockValue bv,
        EntityPlayerLocal player)
    {
        if (string.IsNullOrEmpty(command) || player == null || !command.StartsWith("dem_"))
        {
            return false;
        }
        pos = Parent(world, pos, ref bv);
        string prefix = UpgradePrefix + trap.Settings.Name + "_";
        if (command.StartsWith(prefix))
        {
            command = command.EndsWith("A") ? CmdUpgradeA : CmdUpgradeB;
            TrapStoreDEM.Command(pos, command, null, player);
            return true;
        }
        if (command == CmdLoad)
        {
            Load(trap.Settings, pos, player, true);
            return true;
        }
        if (command == CmdLoadAll)
        {
            LoadAll(player);
            return true;
        }
        TrapStoreDEM.Command(pos, command, null, player);
        return true;
    }

    public static string Text(ITrapDEM trap, string baseText, WorldBase world, BlockValue bv, Vector3i pos)
    {
        pos = Parent(world, pos, ref bv);
        TrapSettingsDEM s = trap.Settings;
        TrapRecordDEM rec = TrapStoreDEM.View(pos);
        StringBuilder sb = new StringBuilder();
        if (!string.IsNullOrEmpty(baseText))
        {
            sb.Append(baseText);
        }
        int level = rec?.Level ?? 1;
        int kills = rec?.Kills ?? 0;
        int next = TrapLevelsDEM.NextAt(level);
        Line(sb, next > 0
            ? string.Format(Localization.Get("dem_trapLevel"), level, kills, next)
            : string.Format(Localization.Get("dem_trapLevelMax"), level, kills));
        if (rec != null && rec.Upgrade != 0)
        {
            Line(sb, string.Format(Localization.Get("dem_trapUpgrade"), s.UpgradeName((char)rec.Upgrade)));
        }
        else if (s.HasUpgrades && level >= TrapLevelsDEM.UpgradeLevel)
        {
            Line(sb, Localization.Get("dem_trapUpgradeReady"));
        }
        if (s.UsesAmmo)
        {
            int total = rec?.AmmoTotal ?? 0;
            Line(sb, total > 0
                ? string.Format(Localization.Get("dem_trapAmmo"), total, s.AmmoCapacity, ItemName(rec.CurrentAmmo))
                : string.Format(Localization.Get("dem_trapAmmoEmpty"), AmmoNames(s)));
        }
        string state = trap.StateText(world, bv, pos, rec);
        if (!string.IsNullOrEmpty(state))
        {
            Line(sb, state);
        }
        return sb.ToString();
    }

    private static void Line(StringBuilder sb, string text)
    {
        if (sb.Length > 0)
        {
            sb.Append('\n');
        }
        sb.Append(text);
    }

    public static string ItemName(string item)
    {
        ItemClass ic = string.IsNullOrEmpty(item) ? null : ItemClass.GetItemClass(item);
        return ic != null ? ic.GetLocalizedItemName() : item ?? "";
    }

    private static string AmmoNames(TrapSettingsDEM s)
    {
        List<string> names = new List<string>();
        foreach (string item in s.AmmoItems)
        {
            if (ItemClass.GetItemClass(item) != null)
            {
                names.Add(ItemName(item));
            }
        }
        return string.Join(", ", names);
    }

    private static XUiM_PlayerInventory Inventory(EntityPlayerLocal player)
    {
        if (player == null)
        {
            return null;
        }
        return LocalPlayerUI.GetUIForPlayer(player)?.xui?.PlayerInventory;
    }

    private static bool HasAmmo(EntityPlayerLocal player, TrapSettingsDEM s)
    {
        XUiM_PlayerInventory inv = Inventory(player);
        if (inv == null)
        {
            return true;
        }
        foreach (string item in s.AmmoItems)
        {
            ItemValue iv = ItemClass.GetItem(item);
            if (iv != null && !iv.IsEmpty() && inv.GetItemCount(iv) > 0)
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>Client: takes the trap's ammo from the player's inventory, up to what fits, and sends it to the
    /// server (which hands back anything that didn't fit after all). False if there was nothing to load (said in a
    /// tooltip if `tell` is set).</summary>
    private static bool Load(TrapSettingsDEM s, Vector3i pos, EntityPlayerLocal player, bool tell)
    {
        XUiM_PlayerInventory inv = Inventory(player);
        if (inv == null)
        {
            return false;
        }
        TrapRecordDEM rec = TrapStoreDEM.View(pos);
        int room = s.AmmoCapacity - (rec?.AmmoTotal ?? 0);
        List<TrapAmmoDEM> loaded = new List<TrapAmmoDEM>();
        foreach (string item in s.AmmoItems)
        {
            if (room <= 0)
            {
                break;
            }
            ItemValue iv = ItemClass.GetItem(item);
            if (iv == null || iv.IsEmpty())
            {
                continue;
            }
            int n = Mathf.Min(inv.GetItemCount(iv), room);
            if (n <= 0)
            {
                continue;
            }
            inv.RemoveItems(new[] { new ItemStack(iv, n) });
            loaded.Add(new TrapAmmoDEM(item, n));
            room -= n;
        }
        if (loaded.Count == 0)
        {
            if (tell)
            {
                GameManager.ShowTooltip(player, string.Format(Localization.Get("dem_trapNoAmmo"), AmmoNames(s)),
                    string.Empty, "ui_denied");
            }
            return false;
        }
        TrapStoreDEM.Command(pos, CmdLoad, loaded, player);
        return true;
    }

    /// <summary>
    /// Load all nearby: Load on every one of the mod's traps with a store within LoadAllRange of the player, closest
    /// first, until the inventory runs out. Each load is a plain Load (items taken here, sent to the server, anything
    /// that didn't fit handed back). The host's records are the server's own, so it loads at once. A client's copies
    /// are only kept fresh for the trap it's looking at, so it first asks the server for the others
    /// (NetPackageTrapLoadAllDEM) and loads them when they come (LoadAllReceived), so it takes only what fits.
    /// </summary>
    private static void LoadAll(EntityPlayerLocal player)
    {
        List<Vector3i> traps = NearbyStores(player);
        if (traps.Count == 0 || TrapStoreDEM.IsServer)
        {
            LoadEach(player, traps);
            return;
        }
        // Still waiting for the last answer: a second one would load from the same old records
        if (Time.time < loadAllWait)
        {
            return;
        }
        loadAllWait = Time.time + 3f;
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
            NetPackageManager.GetPackage<NetPackageTrapLoadAllDEM>().Setup(traps));
    }

    /// <summary>Client: the server sent the records a Load all nearby asked for (already in the cache): load the traps
    /// now.</summary>
    public static void LoadAllReceived(List<Vector3i> traps)
    {
        loadAllWait = 0f;
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player != null)
        {
            LoadEach(player, traps);
        }
    }

    private static void LoadEach(EntityPlayerLocal player, List<Vector3i> traps)
    {
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return;
        }
        int loaded = 0;
        foreach (Vector3i pos in traps)
        {
            BlockValue bv = world.GetBlock(pos);
            if (!bv.ischild && bv.Block is ITrapDEM trap && trap.Settings.UsesAmmo
                && Load(trap.Settings, pos, player, false))
            {
                loaded++;
            }
        }
        if (loaded == 0)
        {
            GameManager.ShowTooltip(player, Localization.Get("dem_trapLoadAllNone"), string.Empty, "ui_denied");
            return;
        }
        GameManager.ShowTooltip(player, string.Format(Localization.Get("dem_trapLoadAllDone"), loaded));
    }

    /// <summary>Whether the player carries ammo or fuel for any of the traps Load all nearby would load.</summary>
    private static bool HasAmmoNearby(EntityPlayerLocal player)
    {
        if (Inventory(player) == null)
        {
            return true;
        }
        World world = GameManager.Instance.World;
        foreach (Vector3i pos in NearbyStores(player))
        {
            if (world.GetBlock(pos).Block is ITrapDEM trap && HasAmmo(player, trap.Settings))
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>The mod's traps with a store within LoadAllRange of the player, closest first. Found through the trap
    /// models loaded here (TrapControllerDEM.Active), which every game that draws them has, client or host.</summary>
    private static List<Vector3i> NearbyStores(EntityPlayerLocal player)
    {
        List<Vector3i> found = new List<Vector3i>();
        World world = GameManager.Instance.World;
        if (world == null || player == null)
        {
            return found;
        }
        List<float> dists = new List<float>();
        Vector3 at = player.position;
        foreach (TrapControllerDEM c in TrapControllerDEM.Active)
        {
            if (c == null)
            {
                continue;
            }
            Vector3i pos = c.Position;
            float d = (pos.ToVector3() + new Vector3(0.5f, 0.5f, 0.5f) - at).sqrMagnitude;
            if (d > LoadAllRange * LoadAllRange || found.Contains(pos))
            {
                continue;
            }
            BlockValue bv = world.GetBlock(pos);
            if (bv.ischild || !(bv.Block is ITrapDEM trap) || !trap.Settings.UsesAmmo)
            {
                continue;
            }
            int i = 0;
            while (i < dists.Count && dists[i] <= d)
            {
                i++;
            }
            dists.Insert(i, d);
            found.Insert(i, pos);
        }
        if (found.Count > LoadAllMax)
        {
            found.RemoveRange(LoadAllMax, found.Count - LoadAllMax);
        }
        return found;
    }

    /// <summary>A player gets items back from a trap: into the inventory, or dropped if it's full.</summary>
    public static void Receive(EntityPlayerLocal player, List<TrapAmmoDEM> items)
    {
        XUiM_PlayerInventory inv = Inventory(player);
        foreach (TrapAmmoDEM a in items)
        {
            ItemValue iv = ItemClass.GetItem(a.Item);
            if (iv == null || iv.IsEmpty() || a.Count <= 0)
            {
                continue;
            }
            int stack = Mathf.Max(1, iv.ItemClass.Stacknumber.Value);
            int count = a.Count;
            while (count > 0)
            {
                int n = Mathf.Min(count, stack);
                count -= n;
                ItemStack itemStack = new ItemStack(iv, n);
                if (inv == null)
                {
                    if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
                    {
                        GameManager.Instance.ItemDropServer(itemStack, player.GetDropPosition(), Vector3.zero,
                            player.entityId, 600f);
                    }
                }
                else if (!inv.AddItemNoPartial(itemStack, true))
                {
                    inv.DropItem(itemStack);
                }
            }
        }
    }
}
