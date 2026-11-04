using System;
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
        try
        {
            XUiController button = __instance.GetChildById("btnReadAllBooks");
            if (button != null)
                button.OnPress += (_sender, _mouseButton) => ReadAllBooksCore.ReadAll(__instance);
        }
        catch (Exception e)
        {
            Debug.Log("[ReadAllBooks] Failed to hook the loot window's button: " + e);
        }
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
        try
        {
            if (__instance.IsOpen && Input.GetKeyDown(ReadAllBooks.Hotkey))
                ReadAllBooksCore.ReadAll(__instance);
        }
        catch (Exception e)
        {
            Debug.Log("[ReadAllBooks] Hotkey failed in the loot window: " + e);
        }
    }
}

/// <summary>
/// The backpack's button, hooked the same way (vanilla hooks its Clear Inventory button here too).
/// </summary>
[HarmonyPatch(typeof(XUiC_BackpackWindow), nameof(XUiC_BackpackWindow.Init))]
public class ReadAllBooks_BackpackInit
{
    static void Postfix(XUiC_BackpackWindow __instance)
    {
        try
        {
            XUiController button = __instance.GetChildById("btnReadAllBooks");
            if (button != null)
                button.OnPress += (_sender, _mouseButton) => ReadAllBooksCore.ReadAll(__instance);
        }
        catch (Exception e)
        {
            Debug.Log("[ReadAllBooks] Failed to hook the backpack's button: " + e);
        }
    }
}

/// <summary>
/// The hotkey, while the backpack is open without a loot window (looting opens the backpack too, and then the key
/// reads the container).
/// </summary>
[HarmonyPatch(typeof(XUiC_BackpackWindow), nameof(XUiC_BackpackWindow.Update))]
public class ReadAllBooks_BackpackUpdate
{
    static void Postfix(XUiC_BackpackWindow __instance)
    {
        try
        {
            if (__instance.IsOpen && Input.GetKeyDown(ReadAllBooks.Hotkey)
                && !__instance.xui.playerUI.windowManager.IsWindowOpen(XUiC_LootWindowGroup.ID))
                ReadAllBooksCore.ReadAll(__instance);
        }
        catch (Exception e)
        {
            Debug.Log("[ReadAllBooks] Hotkey failed in the backpack: " + e);
        }
    }
}
