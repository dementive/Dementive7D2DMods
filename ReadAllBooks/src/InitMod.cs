using System;
using System.IO;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

public class ReadAllBooks : IModApi
{
    public static string ModPath;
    public static KeyCode Hotkey = KeyCode.F2;
    public static bool HotkeyLoaded;

    public void InitMod(Mod _modInstance)
    {
        ModPath = _modInstance.Path;
        LoadHotkey();

        var harmony = new HarmonyLib.Harmony("com.dementive.ReadAllBooks");
        harmony.PatchAll(Assembly.GetExecutingAssembly());
    }

    static void LoadHotkey()
    {
        try
        {
            var path = Path.Combine(ModPath, "Config", "keybinding.json");
            if (!File.Exists(path)) { HotkeyLoaded = true; return; }
            var json = File.ReadAllText(path).Trim();
            var name = ExtractJsonString(json, "ReadAllBooks");
            if (!string.IsNullOrEmpty(name) && Enum.TryParse(name, true, out KeyCode kc))
            {
                Hotkey = kc;
            }
        }
        catch (Exception e)
        {
            Debug.Log("[ReadAllBooks] Failed to load keybinding: " + e);
        }
        finally
        {
            HotkeyLoaded = true;
        }
    }

    static string ExtractJsonString(string json, string key)
    {
        var idx = json.IndexOf("\"" + key + "\"", StringComparison.Ordinal);
        if (idx < 0) return null;
        var colon = json.IndexOf(':', idx);
        if (colon < 0) return null;
        var q1 = json.IndexOf('"', colon + 1);
        if (q1 < 0) return null;
        var q2 = json.IndexOf('"', q1 + 1);
        if (q2 < 0) return null;
        return json.Substring(q1 + 1, q2 - q1 - 1);
    }
}
