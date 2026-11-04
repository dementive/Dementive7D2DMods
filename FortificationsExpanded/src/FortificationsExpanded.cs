using System.Reflection;
using UnityEngine;

public class FortificationsExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        ModEvents.GameStartDone.RegisterHandler(GameStartDone);
        Debug.Log("[FortificationsExpanded] Loaded");
    }

    /// <summary>Each world has its own pieces, so the repair credit kept for the last one's is dropped.</summary>
    private static void GameStartDone(ref ModEvents.SGameStartDoneData _data)
    {
        FortRunDEM.Reset();
    }
}
