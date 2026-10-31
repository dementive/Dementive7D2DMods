using HarmonyLib;
using UnityEngine;

/// <summary>
/// Hooks the button (Config/XUi_InGame/windows.xml) once, when the loot window is created, like vanilla hooks its
/// sort and take-all buttons.
/// </summary>
[HarmonyPatch(typeof(XUiC_LootWindow), nameof(XUiC_LootWindow.Init))]
public class ReadAllBooks_Init
{
    static void Postfix(XUiC_LootWindow __instance)
    {
        XUiController button = __instance.GetChildById("btnReadAllBooks");
        if (button != null)
            button.OnPress += (_sender, _mouseButton) => ReadAllBooksCore.ReadAll(__instance);
    }
}

/// <summary>
/// The hotkey, while a loot window is open.
/// </summary>
[HarmonyPatch(typeof(XUiC_LootWindow), nameof(XUiC_LootWindow.Update))]
public class ReadAllBooks_Update
{
    static void Postfix(XUiC_LootWindow __instance)
    {
        if (__instance.IsOpen && Input.GetKeyDown(ReadAllBooks.Hotkey))
            ReadAllBooksCore.ReadAll(__instance);
    }
}
