using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The Safehouse checklist: what has to be within <see cref="Radius"/> of the flag before refugees can move in. A
/// bedroll for each refugee (each under a roof), a campfire, a light, a storage box and a door at every tier; a
/// workbench from tier 3, a dew collector from tier 4, a chemistry station from tier 5, and an electric light with
/// power at tier 6. Things are recognized by their kind (any bedroll, any door, any storage box), not by name, so
/// variants and other mods' blocks count too.
/// A scan is packed into an int: the <see cref="Items"/> found, plus the roofed bedrolls &lt;&lt; 16.
/// </summary>
public static class SafehouseChecklistDEM
{
    [Flags]
    public enum Items
    {
        Campfire = 1,
        Light = 2,
        Storage = 4,
        Door = 8,
        Workbench = 16,
        DewCollector = 32,
        ChemistryStation = 64,
        PoweredLight = 128,
    }

    /// <summary>How far from the flag everything has to be (and where the refugees settle in).</summary>
    public const int Radius = 10;

    /// <summary>Checked from this far below the flag to this far above it.</summary>
    private const int Below = 4;
    private const int Above = 10;

    public static Items Required(int tier)
    {
        Items items = Items.Campfire | Items.Light | Items.Storage | Items.Door;
        if (tier >= 3)
            items |= Items.Workbench;
        if (tier >= 4)
            items |= Items.DewCollector;
        if (tier >= 5)
            items |= Items.ChemistryStation;
        if (tier >= 6)
            items |= Items.PoweredLight;
        return items;
    }

    public static Items Found(int scan) => (Items)(scan & 0xffff);

    public static int Bedrolls(int scan) => scan >> 16;

    public static bool Passes(int scan, int tier, int refugees)
    {
        Items required = Required(tier);
        return (Found(scan) & required) == required && Bedrolls(scan) >= refugees;
    }

    /// <summary>Checks the blocks around the flag. Server side, with the flag's chunk loaded.</summary>
    public static int Scan(World world, Vector3 flag)
    {
        var center = new Vector3i(flag);
        Items items = 0;
        int bedrolls = 0;
        for (int dx = -Radius; dx <= Radius; dx++)
        {
            for (int dz = -Radius; dz <= Radius; dz++)
            {
                if (dx * dx + dz * dz > Radius * Radius)
                    continue;
                for (int dy = -Below; dy <= Above; dy++)
                {
                    var position = new Vector3i(center.x + dx, center.y + dy, center.z + dz);
                    BlockValue blockValue = world.GetBlock(position);
                    if (blockValue.isair || blockValue.ischild)
                        continue;
                    Block block = blockValue.Block;
                    if (block is BlockSleepingBag)
                    {
                        if (Roofed(world, position))
                            bedrolls++;
                    }
                    else
                    {
                        items |= Kind(world, block, position);
                    }
                }
            }
        }
        return (int)items | (bedrolls << 16);
    }

    private static Items Kind(World world, Block block, Vector3i position)
    {
        string name = block.GetBlockName() ?? "";
        switch (block)
        {
            case BlockCampfire _:
                // The chemistry station is a campfire to the game
                return name.StartsWith("chemistryStation", StringComparison.OrdinalIgnoreCase) ? Items.ChemistryStation : Items.Campfire;
            case BlockTorchHeatMap _:
                return Items.Light;
            case BlockLight _:
                return world.GetTileEntity(position) is TileEntityPowered powered && powered.IsPowered
                    ? Items.Light | Items.PoweredLight
                    : Items.Light;
            case BlockWorkstation _:
                return name.StartsWith("workbench", StringComparison.OrdinalIgnoreCase) ? Items.Workbench : 0;
            case BlockCollector _:
                return name.IndexOf("DewCollector", StringComparison.OrdinalIgnoreCase) >= 0
                    && name.IndexOf("Collapsed", StringComparison.OrdinalIgnoreCase) < 0 ? Items.DewCollector : 0;
            case BlockCompositeTileEntity _:
                if (!(world.GetTileEntity(position) is TileEntityComposite composite))
                    return 0;
                if (composite.GetFeature<TEFeatureDoor>() != null)
                    return Items.Door;
                return composite.GetFeature<TEFeatureStorage>() != null ? Items.Storage : 0;
            default:
                return 0;
        }
    }

    /// <summary>Something solid somewhere above the bedroll.</summary>
    private static bool Roofed(World world, Vector3i position)
    {
        for (int dy = 1; dy <= 12; dy++)
        {
            BlockValue above = world.GetBlock(new Vector3i(position.x, position.y + dy, position.z));
            if (!above.isair && !(above.Block is BlockSleepingBag))
                return true;
        }
        return false;
    }

    /// <summary>
    /// What's still missing, for the quest log ("2 more bedrolls under a roof, a door"), or "" when nothing is.
    /// </summary>
    public static string Missing(int scan, int tier, int refugees)
    {
        var missing = new List<string>();
        int bedrollsMissing = refugees - Bedrolls(scan);
        if (bedrollsMissing > 0)
            missing.Add(string.Format(Localization.Get(bedrollsMissing == 1 ? "SafehouseDEM_need_bedroll" : "SafehouseDEM_need_bedrolls"), bedrollsMissing));
        Items lacking = Required(tier) & ~Found(scan);
        foreach (Items item in Enum.GetValues(typeof(Items)))
        {
            if ((lacking & item) != 0)
                missing.Add(Localization.Get("SafehouseDEM_need_" + item));
        }
        return string.Join(", ", missing);
    }
}
