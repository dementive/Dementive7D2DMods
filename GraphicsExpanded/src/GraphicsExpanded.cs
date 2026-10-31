using System.Reflection;

public class GraphicsExpanded : IModApi
{
    /// <summary>Set by <see cref="GfxGears"/>, which Gears only finds and calls when it's installed.</summary>
    public static bool GearsLoaded;

    public void InitMod(Mod _modInstance)
    {
        var harmony = new HarmonyLib.Harmony("com.dementive.GraphicsExpanded");
        harmony.PatchAll(Assembly.GetExecutingAssembly());
        GfxInput.Init();
        ModEvents.GameUpdate.RegisterHandler(Update);
    }

    private static void Update(ref ModEvents.SGameUpdateData _data)
    {
        GfxApply.Update();
    }
}
