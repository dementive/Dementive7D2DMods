using System.Collections.Generic;
using HarmonyLib;
using Platform;
using UnityEngine;

/// <summary>
/// Craft from storage: while a workstation's window is open, its recipes can also use what's in player storage within
/// <see cref="Range"/> m of the station. The backpack and toolbelt are used first.
///
/// Player storage is storage whose grid is PlayerOwned: the server sets that when a player places the block
/// (TEFeatureStorage.OnAdded), and it also keeps the box from refilling with loot. POI loot containers never have it,
/// and vehicles, backpacks and other stations' slots aren't block storage at all. Secure storage that's locked against
/// the player is skipped, and so is storage someone has open (the server's LockManager).
///
/// Who runs what:
/// <list type="bullet">
/// <item>The crafting player's game counts the storage for the recipe list, the ingredient counts, the craft count
/// and the craft button, from its own copy of the nearby containers (chunk data, kept current by the server's
/// NetPackageTileEntity updates). Only the server knows who has a box open, so on a client a box in use still counts
/// there, and the craft then fails with a message.</item>
/// <item>Only the server (the host, or the single player game) takes items out of storage, after checking again under
/// its own lock rules, and hands them to the player as a credit (NetPackageStorageRequestDEM and ReplyDEM). Requests
/// are handled one at a time on the server's main thread and each item goes to one player, so two players crafting
/// from the same box can't both use it. If the server can't supply everything, it takes nothing and the craft doesn't
/// start. Clients never write a container themselves.</item>
/// <item>The craft then starts as vanilla on the player's game, with the credit counted as if it were in the
/// backpack (backpack, then toolbelt, then credit). Anything left over (the queue filled up or the window closed in
/// the meantime) goes to the backpack, or on the ground if it's full.</item>
/// </list>
/// Only items without quality or mods come from storage (resources, parts, food and the like). At the forge, recipes
/// use the smelted materials in the forge's own grid, never the backpack, so storage doesn't apply there (it does at
/// a forge with smelting turned off, which crafts from the backpack).
/// </summary>
public static class StorageCraftingDEM
{
    /// <summary>How far from the station storage counts, in blocks (meters), center to center.</summary>
    public const int Range = 10;

    /// <summary>How close to the station the server wants the crafting player (the use range plus lag).</summary>
    private const float MaxPlayerDistance = 16f;

    private const float RescanSeconds = 1f;
    private const float ReplyTimeoutSeconds = 10f;

    /// <summary>The most item types one request may ask for (a recipe has a handful of ingredients).</summary>
    private const int MaxRequestTypes = 32;

    // ------------------------------------------------------------------ state on the crafting player's game

    /// <summary>The open workstation window whose recipes may use storage, if any.</summary>
    private static XUiC_WorkstationWindowGroup openGroup;

    /// <summary>Item type to the count in usable storage near the open station.</summary>
    private static readonly Dictionary<int, int> stored = new Dictionary<int, int>();
    private static readonly Dictionary<int, int> scanned = new Dictionary<int, int>();
    private static float nextScan;

    /// <summary>Items the server took from storage for the craft being started, used after the backpack and
    /// toolbelt.</summary>
    private static readonly List<ItemStack> credit = new List<ItemStack>();

    /// <summary>Set while vanilla starts a craft that may use the credit.</summary>
    private static bool crafting;

    /// <summary>Set while a craft is started again once the server's reply is in.</summary>
    private static bool resuming;

    /// <summary>Above 0 while the open station's crafting UI counts what the player has.</summary>
    private static int counting;

    /// <summary>A client's craft waiting for the server to take its items.</summary>
    private class Request
    {
        public int Id;
        public ItemActionEntryCraft Entry;
        public Recipe Recipe;
        public int Crafts;
        public XUiC_WorkstationWindowGroup Group;
        public float Deadline;
    }

    private static Request pending;
    private static int nextRequestId;

    /// <summary>A new world: nothing from the last one is open, owed or waiting.</summary>
    public static void Reset()
    {
        openGroup = null;
        stored.Clear();
        credit.Clear();
        crafting = false;
        resuming = false;
        counting = 0;
        pending = null;
    }

    // ------------------------------------------------------------------ which storage counts (both sides)

    /// <summary>
    /// The storage near a station that a player may craft from, nearest first. Only the server can tell which boxes
    /// someone has open (<paramref name="skipOpen"/>; LockManager.IsLockedServer warns on a client).
    /// </summary>
    private static List<TEFeatureStorage> NearbyStorage(World world, Vector3i station, PlatformUserIdentifierAbs user,
        bool skipOpen)
    {
        List<KeyValuePair<int, TEFeatureStorage>> found = new List<KeyValuePair<int, TEFeatureStorage>>();
        for (int cx = World.toChunkXZ(station.x - Range); cx <= World.toChunkXZ(station.x + Range); cx++)
        {
            for (int cz = World.toChunkXZ(station.z - Range); cz <= World.toChunkXZ(station.z + Range); cz++)
            {
                List<TileEntity> tileEntities = (world.GetChunkSync(cx, cz) as Chunk)?.GetTileEntities()?.list;
                if (tileEntities == null)
                {
                    continue;
                }
                foreach (TileEntity te in tileEntities)
                {
                    // PlayerOwned is set (server side, then saved and synced) when a player places the block; the
                    // game's own server-side container actions (ActionBaseContainersAction) tell player storage by it
                    if (te == null || !TileEntityExtensions.TryGetSelfOrFeature(te, out TEFeatureStorage storage)
                        || storage.ItemGrid == null || !storage.ItemGrid.PlayerOwned)
                    {
                        continue;
                    }
                    Vector3i pos = te.ToWorldPos();
                    int dx = pos.x - station.x, dy = pos.y - station.y, dz = pos.z - station.z;
                    int distSq = dx * dx + dy * dy + dz * dz;
                    if (distSq > Range * Range)
                    {
                        continue;
                    }
                    // The same check the game makes before opening a box (TEFeatureStorage.OnBlockActivated)
                    if (TileEntityExtensions.TryGetSelfOrFeature(te, out TEFeatureLockable lockable)
                        && lockable.IsLocked() && !lockable.IsUserAllowed(user))
                    {
                        continue;
                    }
                    // Storage opens on lock channel 0; whoever has it open edits it on their own game
                    if (skipOpen && LockManager.Instance.IsLockedServer(te))
                    {
                        continue;
                    }
                    found.Add(new KeyValuePair<int, TEFeatureStorage>(distSq, storage));
                }
            }
        }
        found.Sort((a, b) => a.Key.CompareTo(b.Key));
        List<TEFeatureStorage> result = new List<TEFeatureStorage>(found.Count);
        foreach (KeyValuePair<int, TEFeatureStorage> f in found)
        {
            result.Add(f.Value);
        }
        return result;
    }

    /// <summary>Items storage can supply: no quality or mods, like the resources most recipes use.</summary>
    private static bool Usable(ItemStack stack)
    {
        return stack != null && !stack.IsEmpty() && !stack.itemValue.HasQuality
            && !(stack.itemValue.HasModSlots && stack.itemValue.HasMods());
    }

    // ------------------------------------------------------------------ taking the items (server only)

    /// <summary>
    /// Takes the wanted items out of the storage near a station into <paramref name="taken"/>, nearest box first.
    /// Server only (the host, or the single player game), on its main thread. Everything is checked before anything
    /// is taken, so a request that can't be met changes nothing.
    /// </summary>
    internal static bool Take(World world, Vector3i station, EntityPlayer player, PlatformUserIdentifierAbs user,
        List<ItemStack> wanted, List<ItemStack> taken)
    {
        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer || world == null || player == null
            || wanted == null || wanted.Count == 0 || wanted.Count > MaxRequestTypes
            || !(world.GetTileEntity(station) is TileEntityWorkstation)
            || (player.position - station.ToVector3Center()).sqrMagnitude > MaxPlayerDistance * MaxPlayerDistance)
        {
            return false;
        }
        Dictionary<int, int> need = new Dictionary<int, int>();
        foreach (ItemStack w in wanted)
        {
            if (w == null || w.count <= 0 || w.itemValue.ItemClass == null || w.itemValue.HasQuality)
            {
                return false;
            }
            need.TryGetValue(w.itemValue.type, out int n);
            need[w.itemValue.type] = n + w.count;
        }
        List<TEFeatureStorage> boxes = NearbyStorage(world, station, user, true);
        Dictionary<int, int> have = new Dictionary<int, int>();
        foreach (TEFeatureStorage box in boxes)
        {
            ItemStackGrid grid = box.ItemGrid;
            for (int i = 0; i < grid.Length; i++)
            {
                ItemStack stack = grid.GetItem(i);
                if (Usable(stack) && need.ContainsKey(stack.itemValue.type))
                {
                    have.TryGetValue(stack.itemValue.type, out int n);
                    have[stack.itemValue.type] = n + stack.count;
                }
            }
        }
        foreach (KeyValuePair<int, int> n in need)
        {
            if (!have.TryGetValue(n.Key, out int count) || count < n.Value)
            {
                return false;
            }
        }

        foreach (TEFeatureStorage box in boxes)
        {
            ItemStackGrid grid = box.ItemGrid;
            bool changed = false;
            // One update per box instead of one per slot: a slot change only fires TEFeatureStorage.OnSlotChanged,
            // which is SetModified
            bool suppressed = grid.suppressChanged;
            grid.suppressChanged = true;
            try
            {
                for (int i = 0; i < grid.Length; i++)
                {
                    ItemStack stack = grid.GetItem(i);
                    if (!Usable(stack) || !need.TryGetValue(stack.itemValue.type, out int left) || left <= 0)
                    {
                        continue;
                    }
                    int n = Mathf.Min(left, stack.count);
                    // Cloned first: clearing a slot clears its ItemValue in place
                    taken.Add(new ItemStack(stack.itemValue.Clone(), n));
                    need[stack.itemValue.type] = left - n;
                    if (n < stack.count)
                    {
                        stack.count -= n;
                    }
                    else
                    {
                        grid.SetItem(i, null);
                    }
                    changed = true;
                }
            }
            finally
            {
                grid.suppressChanged = suppressed;
            }
            if (changed)
            {
                // Saves the chunk and sends the box to the clients near it
                box.SetModified();
            }
        }
        return true;
    }

    // ------------------------------------------------------------------ the open station (crafting player's game)

    [HarmonyPatch(typeof(XUiC_WorkstationWindowGroup), nameof(XUiC_WorkstationWindowGroup.OnOpen))]
    private static class WindowOpen
    {
        /// <summary>After the children open, before their first update builds the recipe list.</summary>
        private static void Postfix(XUiC_WorkstationWindowGroup __instance)
        {
            try
            {
                // A station with a material grid (the forge) crafts from that grid only, never the backpack
                // (ItemActionEntryCraft.OnActivated), so storage has nothing to add there
                openGroup = __instance.WorkstationData?.TileEntity != null
                    && __instance.GetChildByType<XUiC_WorkstationInputGrid>() == null ? __instance : null;
                stored.Clear();
                Scan();
            }
            catch (System.Exception e)
            {
                openGroup = null;
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
            }
        }
    }

    [HarmonyPatch(typeof(XUiC_WorkstationWindowGroup), nameof(XUiC_WorkstationWindowGroup.OnClose))]
    private static class WindowClose
    {
        private static void Postfix(XUiC_WorkstationWindowGroup __instance)
        {
            if (__instance == openGroup)
            {
                openGroup = null;
                stored.Clear();
            }
        }
    }

    /// <summary>Recounts the storage once a second; when it changed, the crafting UI refreshes as if the backpack
    /// had (every listener of that event is UI).</summary>
    [HarmonyPatch(typeof(XUiC_WorkstationWindowGroup), nameof(XUiC_WorkstationWindowGroup.Update))]
    private static class WindowUpdate
    {
        private static void Postfix(XUiC_WorkstationWindowGroup __instance)
        {
            if (__instance != openGroup || Time.time < nextScan)
            {
                return;
            }
            try
            {
                if (pending != null)
                {
                    if (Time.time <= pending.Deadline)
                    {
                        // Counted again once the reply is in: a recount now would lower the craft count's maximum
                        // (the backpack event recalculates it at once) and change the count the reply checks for
                        return;
                    }
                    pending = null;
                }
                if (Scan())
                {
                    __instance.xui.PlayerInventory.dispatchBackpackItemsChanged();
                }
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
            }
        }
    }

    /// <summary>Counts the usable storage near the open station; true if it changed.</summary>
    private static bool Scan()
    {
        nextScan = Time.time + RescanSeconds;
        scanned.Clear();
        TileEntityWorkstation te = openGroup?.WorkstationData?.TileEntity;
        World world = GameManager.Instance?.World;
        if (te != null && world != null)
        {
            bool server = SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer;
            PlatformUserIdentifierAbs user = PlatformManager.InternalLocalUserIdentifier;
            foreach (TEFeatureStorage box in NearbyStorage(world, te.ToWorldPos(), user, server))
            {
                ItemStackGrid grid = box.ItemGrid;
                for (int i = 0; i < grid.Length; i++)
                {
                    ItemStack stack = grid.GetItem(i);
                    if (Usable(stack))
                    {
                        scanned.TryGetValue(stack.itemValue.type, out int n);
                        scanned[stack.itemValue.type] = n + stack.count;
                    }
                }
            }
        }
        bool changed = scanned.Count != stored.Count;
        if (!changed)
        {
            foreach (KeyValuePair<int, int> s in scanned)
            {
                if (!stored.TryGetValue(s.Key, out int n) || n != s.Value)
                {
                    changed = true;
                    break;
                }
            }
        }
        if (changed)
        {
            stored.Clear();
            foreach (KeyValuePair<int, int> s in scanned)
            {
                stored[s.Key] = s.Value;
            }
        }
        return changed;
    }

    private static int Stored(ItemValue itemValue)
    {
        return itemValue == null || itemValue.HasQuality || !stored.TryGetValue(itemValue.type, out int n) ? 0 : n;
    }

    private static int Credited(int type)
    {
        int n = 0;
        foreach (ItemStack c in credit)
        {
            if (c.itemValue.type == type)
            {
                n += c.count;
            }
        }
        return n;
    }

    /// <summary>What the backpack and toolbelt hold, counted the way XUiM_PlayerInventory.HasItems counts.</summary>
    private static int InInventory(XUiM_PlayerInventory inventory, ItemValue itemValue)
    {
        return inventory.backpack.GetItemCount(itemValue, -1, -1, true)
            + inventory.toolbelt.GetItemCount(itemValue, false, -1, -1, true);
    }

    /// <summary>Whether a controller is part of the open station's window.</summary>
    private static bool InOpenStation(XUiController controller)
    {
        return openGroup != null && controller?.windowGroup != null && controller.windowGroup.Controller == openGroup;
    }

    // ------------------------------------------------------------------ the crafting UI counts storage

    /// <summary>Which recipes show as craftable (and sort first).</summary>
    [HarmonyPatch(typeof(XUiC_RecipeList), nameof(XUiC_RecipeList.BuildRecipeInfosList))]
    private static class RecipeList
    {
        // _items is the list's own scratch list, refilled from the backpack and toolbelt before each call
        private static void Prefix(XUiC_RecipeList __instance, List<ItemStack> _items)
        {
            try
            {
                if (_items != null && InOpenStation(__instance))
                {
                    AddStored(_items);
                }
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
            }
        }
    }

    /// <summary>The craft count's maximum (reads GetAllItemStacks).</summary>
    [HarmonyPatch(typeof(XUiC_RecipeCraftCount), nameof(XUiC_RecipeCraftCount.calcMaxCraftable))]
    private static class CraftCount
    {
        private static void Prefix(XUiC_RecipeCraftCount __instance, out bool __state)
        {
            __state = InOpenStation(__instance);
            if (__state)
            {
                counting++;
            }
        }

        private static void Finalizer(bool __state)
        {
            if (__state)
            {
                counting--;
            }
        }
    }

    /// <summary>The have/need counts beside each ingredient (read GetItemCount).</summary>
    [HarmonyPatch(typeof(XUiC_IngredientEntry), nameof(XUiC_IngredientEntry.GetBindingValueInternal))]
    private static class IngredientCount
    {
        private static void Prefix(XUiC_IngredientEntry __instance, out bool __state)
        {
            __state = InOpenStation(__instance);
            if (__state)
            {
                counting++;
            }
        }

        private static void Finalizer(bool __state)
        {
            if (__state)
            {
                counting--;
            }
        }
    }

    /// <summary>Whether the craft button is enabled (ItemActionEntryCraft.hasItems, which reads HasItems).</summary>
    [HarmonyPatch(typeof(ItemActionEntryCraft), nameof(ItemActionEntryCraft.RefreshEnabled))]
    private static class CraftButton
    {
        private static void Prefix(ItemActionEntryCraft __instance, out bool __state)
        {
            __state = InOpenStation(__instance.ItemController);
            if (__state)
            {
                counting++;
            }
        }

        private static void Finalizer(bool __state)
        {
            if (__state)
            {
                counting--;
            }
        }
    }

    /// <summary>One stack per stored item type: the crafting code sums stacks by type.</summary>
    private static void AddStored(List<ItemStack> items)
    {
        foreach (KeyValuePair<int, int> s in stored)
        {
            items.Add(new ItemStack(new ItemValue(s.Key), s.Value));
        }
    }

    [HarmonyPatch(typeof(XUiM_PlayerInventory), nameof(XUiM_PlayerInventory.GetAllItemStacks))]
    private static class AllItemStacks
    {
        // A new list each call, so adding to it changes nothing else
        private static void Postfix(List<ItemStack> __result)
        {
            if (counting > 0 && __result != null)
            {
                AddStored(__result);
            }
        }
    }

    [HarmonyPatch(typeof(XUiM_PlayerInventory), nameof(XUiM_PlayerInventory.GetItemCount), typeof(ItemValue))]
    private static class ItemCount
    {
        private static void Postfix(ItemValue _itemValue, ref int __result)
        {
            if (counting > 0)
            {
                __result += Stored(_itemValue);
            }
        }
    }

    /// <summary>Counts storage while the UI checks a craft, and the credit while a craft starts.</summary>
    [HarmonyPatch(typeof(XUiM_PlayerInventory), nameof(XUiM_PlayerInventory.HasItems))]
    private static class HasItems
    {
        private static void Postfix(XUiM_PlayerInventory __instance, IList<ItemStack> _itemStacks, int _multiplier,
            ref bool __result)
        {
            if (__result || _itemStacks == null || (!crafting && counting <= 0))
            {
                return;
            }
            try
            {
                for (int i = 0; i < _itemStacks.Count; i++)
                {
                    ItemStack stack = _itemStacks[i];
                    int need = stack.count * _multiplier - InInventory(__instance, stack.itemValue);
                    if (need > 0 && (stack.itemValue.HasQuality
                        || (crafting ? Credited(stack.itemValue.type) : Stored(stack.itemValue)) < need))
                    {
                        return;
                    }
                }
                __result = true;
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
            }
        }
    }

    /// <summary>
    /// Vanilla's removal (backpack, then toolbelt) with the credit after them, while a craft that uses storage starts.
    /// OnActivated has already checked everything is there (hasItems, with the credit counted).
    /// </summary>
    [HarmonyPatch(typeof(XUiM_PlayerInventory), nameof(XUiM_PlayerInventory.RemoveItems))]
    private static class RemoveItems
    {
        private static bool Prefix(XUiM_PlayerInventory __instance, IList<ItemStack> _itemStacks, int _multiplier,
            IList<ItemStack> _removedItems)
        {
            if (!crafting || credit.Count == 0 || _itemStacks == null)
            {
                return true;
            }
            bool started = false;
            try
            {
                int count = _itemStacks.Count;
                for (int i = 0; i < count; i++)
                {
                    ItemStack stack = _itemStacks[i];
                    int need = stack.count * _multiplier;
                    started = true;
                    need -= __instance.backpack.DecItem(stack.itemValue, need, true, _removedItems);
                    if (need > 0)
                    {
                        need -= __instance.toolbelt.DecItem(stack.itemValue, need, true, _removedItems);
                    }
                    if (need > 0)
                    {
                        UseCredit(stack.itemValue.type, need, _removedItems);
                    }
                }
                __instance.dispatchBackpackItemsChanged();
                __instance.dispatchToolbeltItemsChanged();
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
                // Run vanilla only if nothing was taken yet, or it would take some of it twice
                return !started;
            }
            return false;
        }
    }

    /// <summary>Uses up credit like Bag.DecItem: what's used goes into <paramref name="removed"/> (a queued craft
    /// with quality ingredients keeps that list, to hand back if it's cancelled).</summary>
    private static void UseCredit(int type, int count, IList<ItemStack> removed)
    {
        for (int i = 0; i < credit.Count && count > 0; i++)
        {
            ItemStack c = credit[i];
            if (c.itemValue.type != type)
            {
                continue;
            }
            int n = Mathf.Min(count, c.count);
            removed?.Add(new ItemStack(c.itemValue.Clone(), n));
            c.count -= n;
            count -= n;
        }
        credit.RemoveAll(c => c.count <= 0);
    }

    // ------------------------------------------------------------------ starting a craft

    [HarmonyPatch(typeof(ItemActionEntryCraft), nameof(ItemActionEntryCraft.OnActivated))]
    private static class Craft
    {
        private static bool Prefix(ItemActionEntryCraft __instance, out bool __state)
        {
            __state = false;
            if (resuming)
            {
                // The server's items are in: start the craft as vanilla, with the credit counted
                crafting = __state = true;
                return true;
            }
            try
            {
                return Start(__instance, ref __state);
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
                return true;
            }
        }

        private static void Finalizer(ItemActionEntryCraft __instance, bool __state)
        {
            if (!__state)
            {
                return;
            }
            crafting = false;
            try
            {
                GiveCreditBack(__instance.ItemController?.xui);
            }
            catch (System.Exception e)
            {
                Log.Warning("[StationsExpanded] Storage crafting: " + e);
            }
        }
    }

    /// <summary>
    /// Before vanilla starts a craft: when the backpack and toolbelt fall short and storage covers the rest, gets
    /// the rest from the server. On the server (host, single player) it's taken at once and the craft goes ahead; a
    /// client asks and skips this click, and the craft starts when the reply comes in (<see cref="Reply"/>).
    /// </summary>
    private static bool Start(ItemActionEntryCraft entry, ref bool state)
    {
        XUiC_WorkstationWindowGroup group = openGroup;
        if (group == null || !InOpenStation(entry.ItemController))
        {
            return true;
        }
        if (pending != null)
        {
            if (Time.time <= pending.Deadline)
            {
                // Still waiting for the server: extra clicks do nothing
                return false;
            }
            pending = null;
        }
        XUi xui = entry.ItemController.xui;
        Recipe recipe = (entry.ItemController as XUiC_RecipeEntry)?.Recipe;
        if (recipe == null || !XUiM_Recipes.GetRecipeIsUnlocked(xui, recipe)
            || !group.CraftingRequirementsValid(recipe))
        {
            return true;
        }
        // Vanilla's own check, which also fills tempIngredientList with what one craft takes after perks. It stops
        // early (a shorter list) when a quality ingredient is missing, which storage can't supply.
        if (entry.hasItems(xui, recipe) || entry.tempIngredientList.Count != recipe.ingredients.Count)
        {
            return true;
        }
        int crafts = entry.craftCountControl.Count;
        List<ItemStack> wanted = new List<ItemStack>();
        foreach (ItemStack ingredient in entry.tempIngredientList)
        {
            int need = ingredient.count * crafts - InInventory(xui.PlayerInventory, ingredient.itemValue);
            if (need <= 0)
            {
                continue;
            }
            if (Stored(ingredient.itemValue) < need)
            {
                // Not there: vanilla turns the craft down as usual
                return true;
            }
            ItemStack same = wanted.Find(w => w.itemValue.type == ingredient.itemValue.type);
            if (same != null)
            {
                same.count += need;
            }
            else
            {
                wanted.Add(new ItemStack(new ItemValue(ingredient.itemValue.type), need));
            }
        }
        if (wanted.Count == 0)
        {
            return true;
        }
        if (!QueueHasRoom(group))
        {
            entry.warnQueueFull();
            return false;
        }

        EntityPlayerLocal player = xui.playerUI.entityPlayer;
        Vector3i station = group.WorkstationData.TileEntity.ToWorldPos();
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            List<ItemStack> taken = new List<ItemStack>();
            bool ok = false;
            try
            {
                ok = Take(player.world, station, player, PlatformManager.InternalLocalUserIdentifier, wanted, taken);
            }
            finally
            {
                // Whatever was taken is the player's now, even if something went wrong: the finalizer hands back
                // what the craft doesn't use
                if (taken.Count > 0)
                {
                    credit.AddRange(taken);
                    crafting = state = true;
                }
            }
            if (!ok)
            {
                Failed(player);
                return false;
            }
            // The boxes have changed already: the UI refreshes when the craft takes from the backpack
            Scan();
            return true;
        }
        pending = new Request
        {
            Id = ++nextRequestId,
            Entry = entry,
            Recipe = recipe,
            Crafts = crafts,
            Group = group,
            Deadline = Time.time + ReplyTimeoutSeconds,
        };
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
            NetPackageManager.GetPackage<NetPackageStorageRequestDEM>().Setup(pending.Id, station, wanted));
        return false;
    }

    /// <summary>Whether the queue has a free slot (a slot takes a recipe only when it's empty:
    /// XUiC_RecipeStack.SetRecipe).</summary>
    private static bool QueueHasRoom(XUiC_WorkstationWindowGroup group)
    {
        // The base class's queue, the one AddItemToQueue uses (the workstation group declares its own field too)
        XUiController[] slots = ((XUiC_CraftingWindowGroup)group).craftingQueue?.queueItems;
        if (slots == null)
        {
            return true;
        }
        foreach (XUiController slot in slots)
        {
            if (slot is XUiC_RecipeStack stack && stack.recipe == null && !stack.isCrafting)
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>
    /// The server's reply to a client's request (client only). With the items in, the craft is started again from
    /// the same button, if the window, recipe and count are still the same; otherwise the items go to the backpack.
    /// A reply that comes after its request timed out also goes to the backpack: the items were taken for this player.
    /// </summary>
    internal static void Reply(int id, bool ok, List<ItemStack> items)
    {
        try
        {
            HandleReply(id, ok, items);
        }
        catch (System.Exception e)
        {
            Log.Warning("[StationsExpanded] Storage crafting: " + e);
        }
    }

    private static void HandleReply(int id, bool ok, List<ItemStack> items)
    {
        XUi xui = LocalPlayerUI.GetUIForPrimaryPlayer()?.xui;
        Request request = pending;
        if (request == null || request.Id != id)
        {
            Give(xui, items);
            Recount(xui);
            return;
        }
        pending = null;
        if (!ok)
        {
            Give(xui, items);
            Failed(xui?.playerUI.entityPlayer);
            return;
        }
        credit.AddRange(items);
        try
        {
            if (openGroup == request.Group
                && (request.Entry.ItemController as XUiC_RecipeEntry)?.Recipe == request.Recipe
                && request.Entry.craftCountControl.Count == request.Crafts)
            {
                resuming = true;
                request.Entry.OnActivated();
            }
        }
        catch (System.Exception e)
        {
            Log.Warning("[StationsExpanded] Storage crafting: " + e);
        }
        finally
        {
            resuming = false;
            crafting = false;
            GiveCreditBack(xui);
            Recount(xui);
        }
    }

    /// <summary>After a reply: the server sends the boxes' new contents just before it (if they come later, the next
    /// rescan picks them up).</summary>
    private static void Recount(XUi xui)
    {
        try
        {
            if (openGroup != null && Scan())
            {
                xui?.PlayerInventory.dispatchBackpackItemsChanged();
            }
        }
        catch (System.Exception e)
        {
            Log.Warning("[StationsExpanded] Storage crafting: " + e);
        }
    }

    /// <summary>Whatever credit the craft didn't use goes to the backpack.</summary>
    private static void GiveCreditBack(XUi xui)
    {
        if (credit.Count > 0)
        {
            List<ItemStack> items = new List<ItemStack>(credit);
            credit.Clear();
            Give(xui, items);
        }
    }

    /// <summary>Into the backpack or toolbelt, or on the ground when they're full (like a quest reward).</summary>
    private static void Give(XUi xui, List<ItemStack> items)
    {
        XUiM_PlayerInventory inventory = xui?.PlayerInventory;
        if (inventory == null || items == null)
        {
            return;
        }
        foreach (ItemStack stack in items)
        {
            if (stack != null && !stack.IsEmpty() && !inventory.AddItem(stack))
            {
                inventory.DropItem(stack);
            }
        }
    }

    private static void Failed(EntityPlayerLocal player)
    {
        nextScan = 0f;
        if (player != null)
        {
            GameManager.ShowTooltip(player, Localization.Get("DementiveStorageCraftFailed"));
            Audio.Manager.PlayInsidePlayerHead("ui_denied");
        }
    }
}

/// <summary>Client to server: take these items from the storage near a station for the sender's craft.</summary>
public class NetPackageStorageRequestDEM : NetPackage
{
    private int id;
    private Vector3i station;
    private List<ItemStack> wanted = new List<ItemStack>();

    public NetPackageStorageRequestDEM Setup(int _id, Vector3i _station, List<ItemStack> _wanted)
    {
        id = _id;
        station = _station;
        wanted = _wanted;
        return this;
    }

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public override void read(PooledBinaryReader _reader)
    {
        id = _reader.ReadInt32();
        station = StreamUtils.ReadVector3i(_reader);
        int count = _reader.ReadInt16();
        wanted = new List<ItemStack>(Mathf.Max(0, count));
        for (int i = 0; i < count; i++)
        {
            int type = _reader.ReadInt32();
            int n = _reader.ReadInt32();
            wanted.Add(new ItemStack(new ItemValue(type), n));
        }
    }

    public override void write(PooledBinaryWriter _writer)
    {
        base.write(_writer);
        _writer.Write(id);
        StreamUtils.Write(_writer, station);
        _writer.Write((short)wanted.Count);
        foreach (ItemStack w in wanted)
        {
            _writer.Write(w.itemValue.type);
            _writer.Write(w.count);
        }
    }

    /// <summary>On the server, on its main thread, so requests are handled one at a time.</summary>
    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null || Sender == null)
        {
            return;
        }
        List<ItemStack> taken = new List<ItemStack>();
        bool ok = false;
        try
        {
            ok = StorageCraftingDEM.Take(_world, station, _world.GetEntity(Sender.entityId) as EntityPlayer,
                Sender.InternalId, wanted, taken);
        }
        catch (System.Exception e)
        {
            Log.Warning("[StationsExpanded] Storage crafting: " + e);
        }
        // Whatever was taken goes to the player, even if something went wrong after
        Sender.SendPackage(NetPackageManager.GetPackage<NetPackageStorageReplyDEM>().Setup(id, ok || taken.Count > 0,
            taken));
    }
}

/// <summary>Server to client: the items taken for a request (none if it couldn't be met).</summary>
public class NetPackageStorageReplyDEM : NetPackage
{
    private int id;
    private bool ok;
    private List<ItemStack> items = new List<ItemStack>();

    public NetPackageStorageReplyDEM Setup(int _id, bool _ok, List<ItemStack> _items)
    {
        id = _id;
        ok = _ok;
        items = _items;
        return this;
    }

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public override void read(PooledBinaryReader _reader)
    {
        id = _reader.ReadInt32();
        ok = _reader.ReadBoolean();
        int count = _reader.ReadInt16();
        items = new List<ItemStack>(Mathf.Max(0, count));
        for (int i = 0; i < count; i++)
        {
            items.Add(new ItemStack().Read(_reader));
        }
    }

    public override void write(PooledBinaryWriter _writer)
    {
        base.write(_writer);
        _writer.Write(id);
        _writer.Write(ok);
        _writer.Write((short)items.Count);
        foreach (ItemStack stack in items)
        {
            stack.Write(_writer);
        }
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        StorageCraftingDEM.Reply(id, ok, items);
    }
}
