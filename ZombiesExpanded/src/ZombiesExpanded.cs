using System.Reflection;
using UnityEngine;

public class ZombiesExpanded : IModApi
{
    public static string ModPath { get; private set; }

    public void InitMod(Mod _modInstance)
    {
        ModPath = _modInstance.Path;
        ZedSettings.Load();
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        ModEvents.GameUpdate.RegisterHandler(GameUpdate);
        ModEvents.WorldShuttingDown.RegisterHandler(WorldShuttingDown);
        Debug.Log("[ZombiesExpanded] Loaded");
    }

    private static void GameUpdate(ref ModEvents.SGameUpdateData _data)
    {
        ZedStore.Update();
        ZedDeath.Update();
        ZedPossum.Update();
        ZedClient.Update();
    }

    private static void WorldShuttingDown(ref ModEvents.SWorldShuttingDownData _data)
    {
        ZedStore.Shutdown();
        ZedDeath.Clear();
        ZedPossum.Clear();
        ZedSnatch.Clear();
    }
}
