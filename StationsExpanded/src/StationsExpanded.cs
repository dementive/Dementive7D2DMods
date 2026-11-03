using System.Reflection;
using UnityEngine;

public class StationsExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        ModEvents.GameStartDone.RegisterHandler(GameStartDone);
        Debug.Log("[StationsExpanded] Loaded");
    }

    /// <summary>Each world loads its own blocks and items, so the bonuses read from the last one are dropped.</summary>
    private static void GameStartDone(ref ModEvents.SGameStartDoneData _data)
    {
        StationBonusDEM.Reset();
        CraftingPatchesDEM.Reset();
    }
}
