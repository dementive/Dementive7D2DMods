using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Supply crates: a trap with a store (ammo or fuel) refills itself from storage players placed within Range blocks
/// of any of its blocks, above, below or to the side (chests, crates, boxes, a Salvage Hopper's bin). Server only:
/// TrapControllerDEM calls Refill every Interval seconds while the trap's model is loaded and its store isn't full,
/// powered or not. It takes only the items the trap's Load takes, in the same order, up to its capacity, from the
/// nearest container first.
///
/// Storage is a TileEntityComposite with a TEFeatureStorage whose PlayerPlaced is set (it has an Owner: the game
/// records the placer for blocks players place, never for a prefab's, and TEFeatureStorage.UpdateTick uses it to keep
/// player storage out of loot respawns). Left alone: containers someone has open (the server's LockManager holds the
/// storage feature while any player has it open, the host included), locked slots, and a locked container the trap's
/// owner isn't allowed into. The server sends the container's new contents to every client within 192 m
/// (TileEntity.SetModified) and the trap's to players within 64 m, like a manual Load.
/// </summary>
public static class TrapSupplyDEM
{
    /// <summary>How far a container may be from the trap's blocks, in blocks on each axis.</summary>
    public const int Range = 3;

    /// <summary>Seconds between refills.</summary>
    public const float Interval = 3f;

    private class Crate
    {
        public TEFeatureStorage Storage;
        public int Gap;
        public bool Changed;
    }

    private static readonly List<Crate> crates = new List<Crate>();

    /// <summary>Server: tops up the trap at pos (its parent block) from the containers around it.</summary>
    public static void Refill(World world, Vector3i pos, TrapSettingsDEM s, int owner)
    {
        if (world == null || s == null || !s.UsesAmmo)
        {
            return;
        }
        TrapRecordDEM rec = TrapStoreDEM.Get(pos, s.Name);
        int room = s.AmmoCapacity - rec.AmmoTotal;
        if (room <= 0)
        {
            return;
        }
        Cells(world.GetBlock(pos), pos, out Vector3i min, out Vector3i max);
        FindCrates(world, min, max, owner);
        bool loaded = false;
        foreach (string item in s.AmmoItems)
        {
            ItemValue iv = room > 0 ? ItemClass.GetItem(item) : null;
            if (iv == null || iv.IsEmpty())
            {
                continue;
            }
            foreach (Crate crate in crates)
            {
                if (room <= 0)
                {
                    break;
                }
                // Taken out of the crate only as far as the trap has room, so AddAmmo takes all of it
                int n = Take(crate, iv.ItemClass, room);
                if (n > 0)
                {
                    rec.AddAmmo(item, n, s.AmmoCapacity);
                    room -= n;
                    loaded = true;
                }
            }
        }
        foreach (Crate crate in crates)
        {
            if (crate.Changed)
            {
                crate.Storage.SetModified();
            }
        }
        crates.Clear();
        if (loaded)
        {
            TrapStoreDEM.Changed(pos, true);
        }
    }

    /// <summary>Takes up to `max` of an item from a crate's unlocked slots. Returns how many it took.</summary>
    private static int Take(Crate crate, ItemClass itemClass, int max)
    {
        ItemStackGrid grid = crate.Storage.ItemGrid;
        int taken = 0;
        for (int i = 0; i < grid.Length && taken < max; i++)
        {
            ItemStack stack = grid[i];
            if (stack == null || stack.IsEmpty() || stack.itemValue.ItemClass != itemClass || grid.IsSlotLocked(i))
            {
                continue;
            }
            // ChangeCount clears the slot when it empties; the container is sent out once at the end (SetModified)
            taken -= grid.ChangeCount(i, taken - max);
        }
        if (taken > 0)
        {
            crate.Changed = true;
        }
        return taken;
    }

    /// <summary>Player-placed storage within Range of the box min..max that the trap may use, nearest first.</summary>
    private static void FindCrates(World world, Vector3i min, Vector3i max, int owner)
    {
        crates.Clear();
        Vector3i lo = new Vector3i(min.x - Range, min.y - Range, min.z - Range);
        Vector3i hi = new Vector3i(max.x + Range, max.y + Range, max.z + Range);
        LockManager locks = LockManager.Instance;
        PlatformUserIdentifierAbs ownerId = null;
        bool ownerLooked = false;
        for (int cx = World.toChunkXZ(lo.x); cx <= World.toChunkXZ(hi.x); cx++)
        {
            for (int cz = World.toChunkXZ(lo.z); cz <= World.toChunkXZ(hi.z); cz++)
            {
                List<TileEntity> list = (world.GetChunkSync(cx, cz) as Chunk)?.GetTileEntities()?.list;
                if (list == null)
                {
                    continue;
                }
                for (int i = 0; i < list.Count; i++)
                {
                    if (!(list[i] is TileEntityComposite te) || !te.PlayerPlaced || te.IsRemoving)
                    {
                        continue;
                    }
                    Vector3i at = te.ToWorldPos();
                    // A container's tile entity is at its parent block; allow for a few blocks of multi-block
                    if (at.x < lo.x - 4 || at.x > hi.x + 4 || at.y < lo.y - 4 || at.y > hi.y + 4 || at.z < lo.z - 4
                        || at.z > hi.z + 4)
                    {
                        continue;
                    }
                    Cells(world.GetBlock(at), at, out Vector3i cmin, out Vector3i cmax);
                    int gx = Mathf.Max(0, Mathf.Max(cmin.x - max.x, min.x - cmax.x));
                    int gy = Mathf.Max(0, Mathf.Max(cmin.y - max.y, min.y - cmax.y));
                    int gz = Mathf.Max(0, Mathf.Max(cmin.z - max.z, min.z - cmax.z));
                    if (gx > Range || gy > Range || gz > Range)
                    {
                        continue;
                    }
                    TEFeatureStorage storage = te.GetFeature<TEFeatureStorage>();
                    if (storage == null || storage.ItemGrid == null)
                    {
                        continue;
                    }
                    // Someone has it open: their window holds its contents until they close it
                    if (locks != null && (locks.IsLockedServer(storage) || locks.IsLockedServer(te)))
                    {
                        continue;
                    }
                    // Locked: only for a trap whose owner may open it. The game maps entity ids to players only
                    // while they're in the game (UnmapPlayer on disconnect), so not while the owner is away.
                    if (storage.lockFeature != null && storage.lockFeature.IsLocked())
                    {
                        if (!ownerLooked)
                        {
                            ownerLooked = true;
                            ownerId = owner == -1 ? null
                                : GameManager.Instance.persistentPlayers?.GetPlayerDataFromEntityID(owner)?.PrimaryId;
                        }
                        if (ownerId == null || !storage.lockFeature.IsUserAllowed(ownerId))
                        {
                            continue;
                        }
                    }
                    crates.Add(new Crate { Storage = storage, Gap = gx * gx + gy * gy + gz * gz });
                }
            }
        }
        crates.Sort((a, b) => a.Gap.CompareTo(b.Gap));
    }

    /// <summary>The box of blocks a block takes up (a multi-block's parent and children).</summary>
    private static void Cells(BlockValue bv, Vector3i pos, out Vector3i min, out Vector3i max)
    {
        min = pos;
        max = pos;
        Block block = bv.Block;
        if (block == null || !block.isMultiBlock || block.multiBlockPos == null)
        {
            return;
        }
        for (int i = 0; i < block.multiBlockPos.Length; i++)
        {
            Vector3i cell = pos + block.multiBlockPos.Get(i, bv.type, bv.rotation);
            min = new Vector3i(Mathf.Min(min.x, cell.x), Mathf.Min(min.y, cell.y), Mathf.Min(min.z, cell.z));
            max = new Vector3i(Mathf.Max(max.x, cell.x), Mathf.Max(max.y, cell.y), Mathf.Max(max.z, cell.z));
        }
    }
}
