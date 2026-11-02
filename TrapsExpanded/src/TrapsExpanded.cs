using System.Reflection;
using UnityEngine;

public class TrapsExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        ModEvents.GameUpdate.RegisterHandler(GameUpdate);
        ModEvents.WorldShuttingDown.RegisterHandler(WorldShuttingDown);
        Debug.Log("[TrapsExpanded] Loaded");
    }

    private static void GameUpdate(ref ModEvents.SGameUpdateData _data)
    {
        TrapStoreDEM.Update();
        BloodMoonDEM.Update();
    }

    private static void WorldShuttingDown(ref ModEvents.SWorldShuttingDownData _data)
    {
        TrapStoreDEM.Shutdown();
        BloodMoonDEM.Shutdown();
        TrapKillsDEM.Clear();
    }
}
