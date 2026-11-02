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
        Log.Out("[GraphicsExpanded] " + GfxDistantGrass.Status());
        Log.Out("[GraphicsExpanded] " + GfxAmbience.Status());
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

    /// <summary>
    /// gfxe juice shot: after a moment to close the console, sets a juice test off where the player is looking and
    /// takes three screenshots of it, just after, at half a second and at two seconds.
    /// </summary>
    public static string Juice(string what)
    {
        if (GameManager.Instance == null || GameManager.Instance.World == null)
            return "Load into a world first.";
        if (running)
            return "Already taking screenshots.";
        GameManager.Instance.StartCoroutine(JuiceShots(what));
        return "Close the console and keep looking at the spot: " + what + " goes off in 3 seconds, with three screenshots over the next 2.";
    }

    private static IEnumerator JuiceShots(string what)
    {
        running = true;
        string folder = Path.Combine(GameIO.GetUserGameDataDir(), "Screenshots");
        Directory.CreateDirectory(folder);
        string stamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
        yield return new WaitForSecondsRealtime(3f);
        Log.Out("[GraphicsExpanded] juice test: " + GfxConsoleCmd.JuiceTest(what));
        yield return new WaitForSecondsRealtime(0.12f);
        Shoot(Path.Combine(folder, "GraphicsExpanded_juice_" + what + "_" + stamp + "_1.png"));
        yield return new WaitForSecondsRealtime(0.4f);
        Shoot(Path.Combine(folder, "GraphicsExpanded_juice_" + what + "_" + stamp + "_2.png"));
        yield return new WaitForSecondsRealtime(1.5f);
        Shoot(Path.Combine(folder, "GraphicsExpanded_juice_" + what + "_" + stamp + "_3.png"));
        Log.Out("[GraphicsExpanded] " + GfxJuice.Status());
        running = false;
    }

    private static void Shoot(string path)
    {
        ScreenCapture.CaptureScreenshot(path);
        Log.Out("[GraphicsExpanded] Screenshot: " + path);
    }
}
