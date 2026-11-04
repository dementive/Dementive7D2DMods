using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;

/// <summary>
/// Fill, restore or repair a whole run in one hit. When a repair tool's hit fills, restores or repairs a fortification
/// piece, the rest of its run gets the same: the pieces of its family joined to it through touching pieces of that
/// family. A fill or restore moves the undamaged pieces at the same stage (FortStage) on a stage; a repair mends the
/// damaged pieces, whatever their stage, gates included. At most MaxBlocks of them, nearest first, each paying its own
/// materials exactly as a hit on it would; the run stops at the first one the player can't pay for.
///
/// Where it runs: vanilla repairs and upgrades happen on the client holding the tool (ItemActionRepair works from the
/// local player's crosshair and inventory, and OnHoldingUpdate returns for anyone else), and the block's DamageBlock
/// sends the change to the server (SetBlockRPC), which passes it on to the other clients. The run does the same from
/// the same place: materials only ever come out of that player's own inventory, always before the piece changes, and
/// the changes sync like a vanilla hit. A dedicated server never runs ItemActionRepair, so it never starts a run; a
/// listen host runs its own player's runs and each client its own.
/// </summary>
public static class FortRunDEM
{
    public const int MaxBlocks = 32;
    // Pieces the search may look through to find them (filled or undamaged pieces in between count)
    private const int MaxSearch = 1024;

    public enum Kind
    {
        Repair,
        Upgrade,
    }

    /// <summary>What a patched ItemActionRepair call puts back when it ends. The calls nest: OnHoldingUpdate runs
    /// ExecuteAction while the button is held.</summary>
    public struct Scope
    {
        public bool Began;
        public Kind Kind;
        public ItemActionRepair Action;
        public ItemActionData Data;
    }

    private static readonly Vector3i[] Faces =
        { Vector3i.up, Vector3i.down, Vector3i.left, Vector3i.right, Vector3i.forward, Vector3i.back };

    // The innermost ItemActionRepair call running for the local player
    private static int depth;
    private static Kind kind;
    private static ItemActionRepair action;
    private static ItemActionData data;
    private static bool running;

    // The piece that call filled or repaired, waiting for the call to finish
    private static bool pending;
    private static Kind pendingKind;
    private static ItemActionRepair pendingAction;
    private static ItemActionData pendingData;
    private static Vector3i pendingPos;
    private static BlockValue pendingBefore;

    private static bool failedHook;
    private static bool failedRun;

    public static Scope Begin(ItemActionRepair _action, ItemActionData _data, Kind _kind)
    {
        try
        {
            if (running || !(_data?.invData?.holdingEntity is EntityPlayerLocal))
            {
                return default;
            }
            Scope scope = new Scope { Began = true, Kind = kind, Action = action, Data = data };
            if (depth++ == 0)
            {
                pending = false;
            }
            kind = _kind;
            action = _action;
            data = _data;
            return scope;
        }
        catch (Exception e)
        {
            Failed(ref failedHook, "the repair hook", e);
            return default;
        }
    }

    public static void End(Scope _scope, bool _finished)
    {
        if (!_scope.Began)
        {
            return;
        }
        try
        {
            kind = _scope.Kind;
            action = _scope.Action;
            data = _scope.Data;
            if (--depth > 0)
            {
                return;
            }
            depth = 0;
            if (!pending)
            {
                return;
            }
            pending = false;
            // A hit that threw part way doesn't start a run
            if (_finished)
            {
                running = true;
                try
                {
                    Run();
                }
                finally
                {
                    running = false;
                }
            }
            pendingAction = null;
            pendingData = null;
        }
        catch (Exception e)
        {
            Failed(ref failedRun, "a run", e);
        }
    }

    /// <summary>
    /// From the pieces' OnBlockDamaged, before the game applies it: negative damage on a piece while the local
    /// player's repair tool is working. Remembers the first piece the hit repaired (ExecuteAction: damage taken off a
    /// damaged piece) or filled (OnHoldingUpdate: one point past full health, which moves it to its UpgradeBlock), and
    /// what it was. Zombie hits, other players' hits on the server and the run's own hits all leave at the first check.
    /// </summary>
    public static void Hit(Block _block, BlockValueRef _bvRef, BlockValue _before, int _points, int _entityId)
    {
        if (depth == 0 || running || pending)
        {
            return;
        }
        try
        {
            EntityAlive holder = data?.invData?.holdingEntity;
            if (holder == null || holder.entityId != _entityId || _before.ischild
                || !_bvRef.TryGetBlockPos(out Vector3i pos) || !(_block is IFortBlockDEM fort)
                || string.IsNullOrEmpty(fort.FortFamily))
            {
                return;
            }
            int left = _before.damage + _points;
            bool counts = kind == Kind.Repair
                ? _before.damage > 0 && left >= 0
                : left < 0 && !_block.UpgradeBlock.isair && !string.IsNullOrEmpty(fort.FortStage);
            if (!counts)
            {
                return;
            }
            pending = true;
            pendingKind = kind;
            pendingAction = action;
            pendingData = data;
            pendingPos = pos;
            pendingBefore = _before;
        }
        catch (Exception e)
        {
            Failed(ref failedHook, "the repair hook", e);
        }
    }

    /// <summary>Each world has its own pieces.</summary>
    public static void Reset()
    {
        credits.Clear();
    }

    private static void Run()
    {
        ItemInventoryData inv = pendingData?.invData;
        World world = inv?.world;
        EntityAlive player = inv?.holdingEntity;
        if (world == null || player == null || pendingAction == null || !(pendingBefore.Block is IFortBlockDEM fort))
        {
            return;
        }
        // Only once the game has done the hit: the piece moved on a stage, or lost damage
        BlockValue now = world.GetBlock(pendingPos);
        bool done = pendingKind == Kind.Upgrade
            ? now.type != pendingBefore.type
            : now.type == pendingBefore.type && now.damage < pendingBefore.damage;
        if (!done)
        {
            return;
        }
        List<Vector3i> run = Find(world, pendingPos, pendingBefore, fort.FortFamily, fort.FortStage, pendingKind);
        if (run.Count == 0)
        {
            return;
        }
        if (pendingKind == Kind.Upgrade)
        {
            Fill(world, player, run, fort.FortFamily, fort.FortStage);
        }
        else
        {
            Repair(world, player, run, fort.FortFamily);
        }
    }

    /// <summary>
    /// A fill or restore takes undamaged pieces at the same stage (a hit on a damaged one repairs it instead); a repair
    /// takes damaged pieces.
    /// </summary>
    private static bool Wanted(BlockValue _bv, string _family, string _stage, Kind _kind)
    {
        if (_bv.isair || _bv.ischild || !(_bv.Block is IFortBlockDEM fort) || fort.FortFamily != _family)
        {
            return false;
        }
        return _kind == Kind.Upgrade
            ? fort.FortStage == _stage && _bv.damage == 0 && !_bv.Block.UpgradeBlock.isair
            : _bv.Block.CanRepair(_bv);
    }

    /// <summary>
    /// The run: every piece of the family reachable from the one hit through face-touching cells of the family's pieces
    /// (each multi-block piece through all of its cells), nearest first, without the one hit.
    /// </summary>
    private static List<Vector3i> Find(World _world, Vector3i _origin, BlockValue _originBv, string _family,
        string _stage, Kind _kind)
    {
        List<Vector3i> found = new List<Vector3i>();
        HashSet<Vector3i> seen = new HashSet<Vector3i> { _origin };
        Queue<KeyValuePair<Vector3i, BlockValue>> open = new Queue<KeyValuePair<Vector3i, BlockValue>>();
        // The hit piece's cells as it was: a fill keeps the piece's footprint
        open.Enqueue(new KeyValuePair<Vector3i, BlockValue>(_origin, _originBv));
        while (open.Count > 0 && seen.Count < MaxSearch)
        {
            KeyValuePair<Vector3i, BlockValue> piece = open.Dequeue();
            Block block = piece.Value.Block;
            bool multi = block.isMultiBlock && block.multiBlockPos != null;
            int cells = multi ? block.multiBlockPos.Length : 1;
            for (int i = 0; i < cells; i++)
            {
                Vector3i cell = multi
                    ? piece.Key + block.multiBlockPos.Get(i, piece.Value.type, piece.Value.rotation)
                    : piece.Key;
                foreach (Vector3i face in Faces)
                {
                    Vector3i pos = cell + face;
                    BlockValue bv = _world.GetBlock(pos);
                    if (bv.isair || !(bv.Block is IFortBlockDEM fort) || fort.FortFamily != _family)
                    {
                        continue;
                    }
                    if (bv.ischild)
                    {
                        if (bv.Block.multiBlockPos == null)
                        {
                            continue;
                        }
                        pos = bv.Block.multiBlockPos.GetParentPos(pos, bv);
                        BlockValue parent = _world.GetBlock(pos);
                        if (parent.type != bv.type || parent.ischild)
                        {
                            continue;
                        }
                        bv = parent;
                    }
                    if (!seen.Add(pos))
                    {
                        continue;
                    }
                    open.Enqueue(new KeyValuePair<Vector3i, BlockValue>(pos, bv));
                    if (Wanted(bv, _family, _stage, _kind))
                    {
                        found.Add(pos);
                    }
                }
            }
        }
        // OrderBy is stable, so pieces as near as each other keep the search's order
        return found.OrderBy(p => DistanceSq(p, _origin)).Take(MaxBlocks).ToList();
    }

    private static int DistanceSq(Vector3i _a, Vector3i _b)
    {
        int x = _a.x - _b.x, y = _a.y - _b.y, z = _a.z - _b.z;
        return x * x + y * y + z * z;
    }

    /// <summary>
    /// Each piece as if the fill's last hit had landed on it (ItemActionRepair.OnHoldingUpdate): the same material
    /// check and removal, quest and challenge count, upgrade event and XP.
    /// </summary>
    private static void Fill(World _world, EntityAlive _player, List<Vector3i> _run, string _family, string _stage)
    {
        ItemActionRepair repair = pendingAction;
        ItemInventoryData inv = pendingData.invData;
        int xp = 0;
        foreach (Vector3i pos in _run)
        {
            // Read again: the piece could have changed since the search (a fill doesn't touch its neighbours, but
            // nothing here relies on that)
            BlockValue bv = _world.GetBlock(pos);
            if (!Wanted(bv, _family, _stage, Kind.Upgrade) || _world.IsWithinTraderArea(pos))
            {
                continue;
            }
            Block block = bv.Block;
            // The fill's own materials, through the call a hit makes: it checks the tool may use them, takes them from
            // the toolbelt or the backpack and shows them going. Out of them, the run ends here.
            if (!repair.RemoveRequiredResource(inv, bv))
            {
                ShowMissing(_player, repair.GetUpgradeItemName(block));
                break;
            }
            BlockValue upgraded = block.UpgradeBlock;
            upgraded.rotation = bv.rotation;
            upgraded.meta = bv.meta;
            QuestEventManager.Current.BlockUpgraded(block.GetBlockName(), pos);
            Fire(_player, MinEventTypes.onSelfUpgradedBlock, upgraded, pos);
            // One point past full health moves the piece to its UpgradeBlock, here and (SetBlockRPC) on the server
            block.DamageBlock(_world, pos, bv, -1, _player.entityId);
            if (int.TryParse(block.Properties.GetString(Block.PropUpgradeBlockClass, Block.PropUpgradeBlockItemCount),
                    out int count))
            {
                xp += (int)(upgraded.Block.blockMaterial.Experience * count);
            }
        }
        if (xp > 0)
        {
            _player.Progression.AddLevelExp(xp, "_xpFromUpgradeBlock", Progression.XPTypes.Upgrading);
        }
    }

    /// <summary>
    /// Each piece as if the hit had landed on it (ItemActionRepair.ExecuteAction): mends up to the tool's Repair_amount
    /// for that share of the piece's RepairItems, paid in whole items (at least one of each) against the piece's own
    /// credit, with the same repair event and XP. No extra tool wear: it's still one swing.
    /// </summary>
    private static void Repair(World _world, EntityAlive _player, List<Vector3i> _run, string _family)
    {
        ItemActionRepair repair = pendingAction;
        ItemInventoryData inv = pendingData.invData;
        int xp = 0;
        foreach (Vector3i pos in _run)
        {
            BlockValue bv = _world.GetBlock(pos);
            if (!Wanted(bv, _family, null, Kind.Repair) || _world.IsWithinTraderArea(pos))
            {
                continue;
            }
            Block block = bv.Block;
            int amount = Math.Min((int)repair.repairAmount, bv.damage);
            float share = (float)amount / block.MaxDamage;
            List<Block.SItemNameCount> items = block.RepairItems;
            if (block.RepairItemsMeshDamage != null && block.shape.UseRepairDamageState(bv))
            {
                amount = 1;
                share = 1f;
                items = block.RepairItemsMeshDamage;
            }
            if (items == null || amount <= 0)
            {
                continue;
            }
            float[] credit = CreditFor(pos, bv.type, items);
            // Every item is checked before any is taken, so a piece is paid for in full or left alone
            if (!CanPay(repair, inv, _player, block, items, share, credit))
            {
                break;
            }
            float itemXp = 0f;
            for (int i = 0; i < items.Count; i++)
            {
                float cost = items[i].Count * share * block.ResourceScale;
                if (credit[i] <= 0f)
                {
                    int count = Math.Max(1, (int)cost);
                    credit[i] += count;
                    ItemStack paid = new ItemStack(ItemClass.GetItem(items[i].ItemName), count);
                    itemXp += (paid.itemValue.ItemClass?.MadeOfMaterial?.Experience ?? 0f) * count;
                    repair.removeRequiredItem(inv, paid);
                    paid.count = -count;
                    _player.AddUIHarvestingItem(paid);
                }
                credit[i] -= cost;
            }
            block.DamageBlock(_world, pos, bv, -amount, _player.entityId);
            Fire(_player, MinEventTypes.onSelfRepairBlock, bv, pos);
            xp += (int)itemXp;
        }
        if (xp > 0)
        {
            _player.Progression.AddLevelExp(xp, "_xpFromRepairBlock", Progression.XPTypes.Repairing);
        }
    }

    /// <summary>The hit's own check: each item not covered by credit has to be there in full, in the toolbelt or the
    /// backpack. Missing ones show in the item list the way a hit shows them.</summary>
    private static bool CanPay(ItemActionRepair _repair, ItemInventoryData _inv, EntityAlive _player, Block _block,
        List<Block.SItemNameCount> _items, float _share, float[] _credit)
    {
        bool ok = true;
        for (int i = 0; i < _items.Count; i++)
        {
            if (_credit[i] > 0f)
            {
                continue;
            }
            int count = Math.Max(1, (int)(_items[i].Count * _share * _block.ResourceScale));
            ItemStack need = new ItemStack(ItemClass.GetItem(_items[i].ItemName), count);
            if (!_repair.canRemoveRequiredItem(_inv, need))
            {
                need.count = 0;
                _player.AddUIHarvestingItem(need, true);
                ok = false;
            }
        }
        return ok;
    }

    private static void ShowMissing(EntityAlive _player, string _item)
    {
        if (!string.IsNullOrEmpty(_item))
        {
            _player.AddUIHarvestingItem(new ItemStack(ItemClass.GetItem(_item), 0), true);
        }
    }

    private static void Fire(EntityAlive _player, MinEventTypes _event, BlockValue _bv, Vector3i _pos)
    {
        _player.MinEventContext.ItemActionData = pendingData;
        _player.MinEventContext.BlockValue = _bv;
        _player.MinEventContext.Position = _pos.ToVector3();
        _player.FireEvent(_event, true);
    }

    // ------------------------------------------------------------------ repair credit

    /// <summary>
    /// A hit pays whole items, at least one of each, and keeps what it overpaid as credit against the next hit on the
    /// same piece (InventoryDataRepair.lastRepairItemsPercents, reset when the target changes). Vanilla keeps that for
    /// the one piece being hit; the run keeps it for each piece it mends, so mending a piece through the run costs what
    /// hitting it again and again would.
    /// </summary>
    private sealed class Credit
    {
        public int Type;
        public List<Block.SItemNameCount> Items;
        public float[] Left;
    }

    private static readonly Dictionary<Vector3i, Credit> credits = new Dictionary<Vector3i, Credit>();

    private static float[] CreditFor(Vector3i _pos, int _type, List<Block.SItemNameCount> _items)
    {
        if (!credits.TryGetValue(_pos, out Credit credit) || credit.Type != _type || credit.Items != _items)
        {
            if (credits.Count >= 4096)
            {
                credits.Clear();
            }
            credit = new Credit { Type = _type, Items = _items, Left = new float[_items.Count] };
            credits[_pos] = credit;
        }
        return credit.Left;
    }

    private static void Failed(ref bool _logged, string _what, Exception _e)
    {
        if (!_logged)
        {
            _logged = true;
            Log.Error("[FortificationsExpanded] " + _what + " failed (logged once): " + _e);
        }
    }
}

/// <summary>Repair hits: ExecuteAction, on the client holding the tool.</summary>
[HarmonyPatch(typeof(ItemActionRepair), nameof(ItemActionRepair.ExecuteAction))]
public static class FortRepairHitPatchDEM
{
    public static void Prefix(ItemActionRepair __instance, ItemActionData _actionData, out FortRunDEM.Scope __state)
    {
        __state = FortRunDEM.Begin(__instance, _actionData, FortRunDEM.Kind.Repair);
    }

    // A finalizer, so the context ends even if the game's code throws
    public static void Finalizer(FortRunDEM.Scope __state, Exception __exception)
    {
        FortRunDEM.End(__state, __exception == null);
    }
}

/// <summary>Fills and restores: OnHoldingUpdate finishes an upgrade once its hits are in, on the same client.</summary>
[HarmonyPatch(typeof(ItemActionRepair), nameof(ItemActionRepair.OnHoldingUpdate))]
public static class FortUpgradeHitPatchDEM
{
    public static void Prefix(ItemActionRepair __instance, ItemActionData _actionData, out FortRunDEM.Scope __state)
    {
        __state = FortRunDEM.Begin(__instance, _actionData, FortRunDEM.Kind.Upgrade);
    }

    public static void Finalizer(FortRunDEM.Scope __state, Exception __exception)
    {
        FortRunDEM.End(__state, __exception == null);
    }
}

/// <summary>
/// Sandbags fill with crushed sand, which isn't on any vanilla repair tool's Allowed_upgrade_items (the stone axe,
/// claw hammer and nail gun share one list), so no tool could fill them. This adds it, when the tool loads, to every
/// repair tool whose list takes clay (the other earth fill); an XML patch couldn't reach named tools that copy the
/// vanilla list in mods loaded later. Runs on the server and every client, which all read the items.
/// </summary>
[HarmonyPatch(typeof(ItemActionRepair), nameof(ItemActionRepair.ReadFrom))]
public static class FortSandToolPatchDEM
{
    private const string Sand = "resourceCrushedSand";
    private const string Clay = "resourceClayLump";

    public static void Postfix(ItemActionRepair __instance)
    {
        try
        {
            string allowed = __instance.allowedUpgradeItems;
            if (!string.IsNullOrEmpty(allowed) && allowed.ContainsCaseInsensitive(Clay)
                && !allowed.ContainsCaseInsensitive(Sand))
            {
                __instance.allowedUpgradeItems = allowed + "," + Sand;
            }
        }
        catch (Exception e)
        {
            Log.Error("[FortificationsExpanded] Adding crushed sand to a repair tool failed: " + e);
        }
    }
}
