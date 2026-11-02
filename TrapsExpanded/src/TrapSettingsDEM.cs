using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// What every trap block is (powered BlockTrapDEM, unpowered BlockPlainTrapDEM, the hopper's BlockHopperDEM): its
/// shared settings, the controller its model gets, and its own activation commands.
/// </summary>
public interface ITrapDEM
{
    TrapSettingsDEM Settings { get; }

    /// <summary>Adds this trap's controller to its model (or null for a trap without one).</summary>
    TrapControllerDEM AddController(GameObject model);

    /// <summary>Everyone: commands of this trap's own (re-arm, light) for the radial menu.</summary>
    void ExtraCommands(List<BlockActivationCommand> commands, WorldBase world, BlockValue blockValue, Vector3i pos,
        TrapRecordDEM record);

    /// <summary>Server: handles one of this trap's own commands. Returns false if it isn't one.</summary>
    bool ServerCommand(World world, Vector3i pos, string command);

    /// <summary>Everyone: an extra line for the trap's activation text (armed, lit), or null.</summary>
    string StateText(WorldBase world, BlockValue blockValue, Vector3i pos, TrapRecordDEM record);
}

/// <summary>
/// Settings every trap reads from its block XML:
/// WearPerUse and WornOutFraction (wear; see TrapControllerDEM.Wear), AmmoItems (comma list of the items it can be
/// loaded with, used in order), AmmoCapacity, AmmoPerUse (may be a fraction: fuel burned per use), StatusTrap (levels
/// lengthen its status instead of raising damage), UpgradeA and UpgradeB (names of its level-3 upgrades; the radial
/// menu shows blockcommand_dem_up_&lt;block&gt;_A and _B), PressItem and PressCount (what a Salvage Hopper's Ammo Press
/// adds to it per salvaged kill).
/// </summary>
public class TrapSettingsDEM
{
    public string Name;
    public int WearPerUse;
    public float WornOutFraction = 0.05f;
    public string[] AmmoItems = new string[0];
    public int AmmoCapacity;
    public float AmmoPerUse = 1f;
    public bool StatusTrap;
    public string UpgradeA;
    public string UpgradeB;
    public string PressItem;
    public int PressCount = 1;

    public bool UsesAmmo => AmmoItems.Length > 0 && AmmoCapacity > 0;

    public bool HasUpgrades => !string.IsNullOrEmpty(UpgradeA) && !string.IsNullOrEmpty(UpgradeB);

    public static TrapSettingsDEM Parse(Block block)
    {
        DynamicProperties p = block.Properties;
        TrapSettingsDEM s = new TrapSettingsDEM { Name = block.GetBlockName() };
        p.ParseInt("WearPerUse", ref s.WearPerUse);
        p.ParseFloat("WornOutFraction", ref s.WornOutFraction);
        string ammo = "";
        p.ParseString("AmmoItems", ref ammo);
        if (!string.IsNullOrEmpty(ammo))
        {
            s.AmmoItems = ammo.Split(',');
            for (int i = 0; i < s.AmmoItems.Length; i++)
            {
                s.AmmoItems[i] = s.AmmoItems[i].Trim();
            }
        }
        p.ParseInt("AmmoCapacity", ref s.AmmoCapacity);
        p.ParseFloat("AmmoPerUse", ref s.AmmoPerUse);
        p.ParseBool("StatusTrap", ref s.StatusTrap);
        p.ParseString("UpgradeA", ref s.UpgradeA);
        p.ParseString("UpgradeB", ref s.UpgradeB);
        p.ParseString("PressItem", ref s.PressItem);
        p.ParseInt("PressCount", ref s.PressCount);
        return s;
    }

    /// <summary>The level-3 upgrade's display name ('A' or 'B').</summary>
    public string UpgradeName(char upgrade)
    {
        return Localization.Get("blockcommand_" + TrapUiDEM.UpgradeCommand(Name, upgrade));
    }
}
