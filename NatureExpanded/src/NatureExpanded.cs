using System.Reflection;
using UnityEngine;

public class NatureExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        GrassSheetDEM.ModPath = _modInstance.Path;
        new HarmonyLib.Harmony(GetType().ToString()).PatchAll(Assembly.GetExecutingAssembly());
        Debug.Log("[NatureExpanded] Loaded");
    }
}
