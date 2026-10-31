using System;
using System.IO;
using InControl;

/// <summary>The mod's one control: hold it to see vanilla. Home by default, which the game doesn't use.</summary>
public class GfxActions : PlayerActionSet
{
    public readonly PlayerAction Compare;

    public GfxActions()
    {
        Compare = CreatePlayerAction("GraphicsExpandedCompare");
        Compare.UserData = new PlayerActionData.ActionUserData("gfxeCompareKey", "gfxeCompareKeyDesc",
            PlayerActionData.GroupGlobalFunctions, PlayerActionData.EAppliesToInputType.KbdMouseOnly);
        Compare.AddDefaultBinding(Key.Home);
    }
}

/// <summary>
/// Owns the compare key. Gears rebinds it from the Mods menu but leaves saving the binding to the mod, so it's
/// kept in the user data folder, apart from the game's own controls.
/// </summary>
public static class GfxInput
{
    public static GfxActions Actions { get; private set; }

    private static string BindingsPath => Path.Combine(GameIO.GetUserGameDataDir(), "GraphicsExpanded", "Controls.txt");

    public static void Init()
    {
        try
        {
            Actions = new GfxActions();
            if (File.Exists(BindingsPath))
                Actions.Load(File.ReadAllText(BindingsPath));
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't set up the compare key: " + e.Message);
        }
    }

    public static void SaveBindings()
    {
        if (Actions == null)
            return;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(BindingsPath));
            File.WriteAllText(BindingsPath, Actions.Save());
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't save the compare key: " + e.Message);
        }
    }

    public static void Update()
    {
        bool held = Actions != null && Actions.Compare.IsPressed && !Typing();
        GfxSettings.CompareHeld = held;
    }

    /// <summary>True when there's no player UI (main menu) or a text field has the keyboard (chat, console, signs).</summary>
    private static bool Typing()
    {
        LocalPlayerUI ui = LocalPlayerUI.GetUIForPrimaryPlayer();
        return ui == null || ui.windowManager == null || ui.windowManager.IsInputActive();
    }
}
