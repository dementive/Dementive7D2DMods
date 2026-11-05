using System.Reflection;
using UnityEngine;

public class ConsumablesExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        ModEvents.GameUpdate.RegisterHandler(GameUpdate);
        ModEvents.WorldShuttingDown.RegisterHandler(WorldShuttingDown);
        Debug.Log("[ConsumablesExpanded] Loaded");
    }

    private static void GameUpdate(ref ModEvents.SGameUpdateData _data)
    {
        ChemTimeDEM.Update();
        ChemPossumDEM.Update();
        ChemDamageDEM.Update();
    }

    private static void WorldShuttingDown(ref ModEvents.SWorldShuttingDownData _data)
    {
        ChemTimeDEM.Restore();
        ChemPossumDEM.Reset();
        ChemDamageDEM.Reset();
    }
}
