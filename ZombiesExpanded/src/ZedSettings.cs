using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Xml;

/// <summary>
/// The mod's settings, from Settings.xml in the mod's folder. Gameplay settings count on the server (in single player
/// and for the host, that's this game); look and sound settings count for each player on their own game. The console
/// command `ze set` changes them for the session.
/// </summary>
public static class ZedSettings
{
    private static readonly Dictionary<string, string> values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        // Gameplay (server)
        { "Preset", "Standard" },
        { "Individuals", "true" },
        { "InjuryShare", "33" },
        { "Temperament", "true" },
        { "Senses", "true" },
        { "Crowd", "true" },
        { "HitLocations", "true" },
        { "Mutations", "true" },
        { "Gear", "true" },
        { "Champions", "true" },
        { "Alpha", "true" },
        { "MutationRate", "1" },
        { "ChampionRate", "1" },
        { "GearRate", "1" },
        { "Remnants", "true" },
        { "RemnantRate", "1" },
        { "ShowpieceRate", "1" },
        // Looks and sounds (each player)
        { "Looks", "true" },
        { "Weathering", "true" },
        { "Wounds", "true" },
        { "BloodDrips", "true" },
        { "Swing", "true" },
        { "Flies", "true" },
        { "Breath", "true" },
        { "Drool", "true" },
        { "Voices", "true" },
        { "HordeAudio", "true" },
        { "Tips", "true" },
        { "ChampionBar", "true" },
    };

    public static IEnumerable<KeyValuePair<string, string>> All => values;

    public static bool Individuals => Bool("Individuals");
    public static bool Temperament => Bool("Temperament");
    public static bool Senses => Bool("Senses");
    public static bool Crowd => Bool("Crowd");
    public static bool HitLocations => Bool("HitLocations");
    public static bool Mutations => Bool("Mutations");
    public static bool Gear => Bool("Gear");
    public static bool Champions => Bool("Champions");
    public static bool Alpha => Bool("Alpha");
    public static bool Remnants => Bool("Remnants");
    public static bool HordeAudio => Bool("HordeAudio");
    public static bool Tips => Bool("Tips");
    public static bool ChampionBar => Bool("ChampionBar");
    public static bool Looks => Bool("Looks");
    public static bool Weathering => Looks && Bool("Weathering");
    public static bool Wounds => Looks && Bool("Wounds");
    public static bool BloodDrips => Looks && Bool("BloodDrips");
    public static bool Swing => Looks && Bool("Swing");
    public static bool Flies => Looks && Bool("Flies");
    public static bool Breath => Looks && Bool("Breath");
    public static bool Drool => Looks && Bool("Drool");
    public static bool Voices => Bool("Voices");
    public static bool Brutal => string.Equals(values["Preset"], "Brutal", StringComparison.OrdinalIgnoreCase);

    public static void Load()
    {
        string path = Path.Combine(ZombiesExpanded.ModPath ?? "", "Settings.xml");
        if (!File.Exists(path))
        {
            return;
        }
        try
        {
            XmlDocument doc = new XmlDocument();
            doc.Load(path);
            foreach (XmlElement e in doc.GetElementsByTagName("Setting"))
            {
                string name = e.GetAttribute("name");
                if (values.ContainsKey(name))
                {
                    values[name] = e.GetAttribute("value");
                }
                else
                {
                    Log.Warning($"[ZombiesExpanded] Unknown setting '{name}' in Settings.xml");
                }
            }
        }
        catch (Exception ex)
        {
            Log.Warning($"[ZombiesExpanded] Couldn't read Settings.xml: {ex.Message}");
        }
    }

    /// <summary>Changes a setting for this session. Returns false if there's no such setting.</summary>
    public static bool Set(string name, string value)
    {
        if (!values.ContainsKey(name))
        {
            return false;
        }
        values[name] = value;
        return true;
    }

    public static bool Bool(string name)
    {
        return values.TryGetValue(name, out string v) && (v == "1" || v.Equals("true", StringComparison.OrdinalIgnoreCase)
            || v.Equals("on", StringComparison.OrdinalIgnoreCase));
    }

    public static float Float(string name, float fallback)
    {
        return values.TryGetValue(name, out string v) && float.TryParse(v, NumberStyles.Float, CultureInfo.InvariantCulture, out float f)
            ? f : fallback;
    }
}
