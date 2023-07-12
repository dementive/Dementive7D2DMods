using HarmonyLib;
using System.Reflection;
using UnityEngine;

public class QuestsExpanded : IModApi
{
    public void InitMod(Mod _modInstance)
    {
        var harmony = new HarmonyLib.Harmony(GetType().ToString());
        harmony.PatchAll(Assembly.GetExecutingAssembly());
    }
}