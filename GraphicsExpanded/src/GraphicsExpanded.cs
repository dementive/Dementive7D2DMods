using System;
using System.IO;
using System.Reflection;
using UnityEngine;

public class GraphicsExpanded : IModApi
{
    /// <summary>Set by <see cref="GfxGears"/>, which Gears only finds and calls when it's installed.</summary>
    public static bool GearsLoaded;

    public void InitMod(Mod _modInstance)
    {
        var harmony = new HarmonyLib.Harmony("com.dementive.GraphicsExpanded");
        harmony.PatchAll(Assembly.GetExecutingAssembly());
        GfxInput.Init();
        AssetBundle shaders = LoadShaders(_modInstance.Path);
        GfxWeather.Init(shaders);
        GfxAtmosphere.Init(shaders);
        GfxHaze.Init(shaders);
        GfxWater.Init(shaders);
        ModEvents.GameUpdate.RegisterHandler(Update);
    }

    /// <summary>The mod's shaders, built by src/build-shaders.bat. Without them the weather and sunbeams are off.</summary>
    private static AssetBundle LoadShaders(string modPath)
    {
        string path = Path.Combine(modPath, "Resources", "graphicsexpanded.bundle");
        try
        {
            AssetBundle bundle = AssetBundle.LoadFromFile(path);
            if (bundle == null)
                Log.Warning("[GraphicsExpanded] Couldn't load " + path + "; rain wetness, snow cover, sunbeams and height fog are off");
            return bundle;
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't load " + path + ": " + e.Message);
            return null;
        }
    }

    private static void Update(ref ModEvents.SGameUpdateData _data)
    {
        GfxApply.Update();
    }
}
