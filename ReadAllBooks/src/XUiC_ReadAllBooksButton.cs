using System;
using UnityEngine;

/// <summary>
/// The Read All Books button (Config/XUi_InGame/windows.xml), in the loot window's and the backpack's title bars.
/// The button is its own controller, so it handles its clicks and the hotkey itself and the mod doesn't patch any
/// game code: child controllers update every frame their window is open, which is when the hotkey counts.
/// </summary>
public class XUiC_ReadAllBooksButton : XUiController
{
    XUiC_LootWindow lootWindow;
    XUiC_BackpackWindow backpackWindow;

    public override void Init()
    {
        base.Init();
        lootWindow = GetParentByType<XUiC_LootWindow>();
        if (lootWindow == null)
            backpackWindow = GetParentByType<XUiC_BackpackWindow>();

        if (lootWindow == null && backpackWindow == null)
            Log.Warning("[ReadAllBooks] A Read All Books button isn't in the loot window or the backpack, so it does nothing");
        else
            Log.Out("[ReadAllBooks] Button ready in the " + (lootWindow != null ? "loot window" : "backpack"));

        OnPress += (_sender, _mouseButton) => Read("button");
    }

    public override void Update(float _dt)
    {
        base.Update(_dt);
        try
        {
            if (!IsOpen || !Input.GetKeyDown(ReadAllBooks.Hotkey))
                return;
            GUIWindowManager windowManager = xui.playerUI.windowManager;
            // Typing in a search field
            if (windowManager.IsInputActive())
                return;
            // Looting opens the backpack too, and then the key reads the container
            if (backpackWindow != null && windowManager.IsWindowOpen(XUiC_LootWindowGroup.ID))
                return;
            Read(ReadAllBooks.Hotkey.ToString());
        }
        catch (Exception e)
        {
            Log.Error("[ReadAllBooks] Hotkey failed: " + e);
        }
    }

    void Read(string _source)
    {
        if (lootWindow != null)
            ReadAllBooksCore.ReadAll(lootWindow, _source);
        else if (backpackWindow != null)
            ReadAllBooksCore.ReadAll(backpackWindow, _source);
    }
}
