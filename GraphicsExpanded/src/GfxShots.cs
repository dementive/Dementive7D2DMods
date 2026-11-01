using System;
using System.Collections;
using System.IO;
using UnityEngine;

/// <summary>
/// gfxe shots: two screenshots of the same view into the game's Screenshots folder, one with the mod's look and one as
/// if the compare key were held (the game's own look), with every feature's status written to the log alongside.
/// </summary>
public static class GfxShots
{
    private static bool running;

    public static string Take()
    {
        if (GameManager.Instance == null || GameManager.Instance.World == null)
            return "Load into a world first.";
        if (running)
            return "Already taking screenshots.";
        GameManager.Instance.StartCoroutine(Shots());
        return "Close the console and keep still: two screenshots over the next 5 seconds, with and without the mod's look.";
    }

    private static IEnumerator Shots()
    {
        running = true;
        string folder = Path.Combine(GameIO.GetUserGameDataDir(), "Screenshots");
        Directory.CreateDirectory(folder);
        string stamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
        yield return new WaitForSecondsRealtime(3f);
        Shoot(Path.Combine(folder, "GraphicsExpanded_" + stamp + "_on.png"));
        Log.Out("[GraphicsExpanded] " + GfxTerrain.Status() + " " + GfxTerrainTextures.Status());
        Log.Out("[GraphicsExpanded] " + GfxForest.Status());
        Log.Out("[GraphicsExpanded] " + GfxFarShadows.Status());
        Log.Out("[GraphicsExpanded] " + GfxHaze.Status());
        Log.Out("[GraphicsExpanded] " + GfxWater.Status());
        Log.Out("[GraphicsExpanded] " + GfxAtmosphere.Status());
        yield return null;
        GfxInput.ForceCompare = true;
        yield return new WaitForSecondsRealtime(1f);
        Shoot(Path.Combine(folder, "GraphicsExpanded_" + stamp + "_off.png"));
        yield return null;
        yield return null;
        GfxInput.ForceCompare = false;
        running = false;
    }

    private static void Shoot(string path)
    {
        ScreenCapture.CaptureScreenshot(path);
        Log.Out("[GraphicsExpanded] Screenshot: " + path);
    }
}
