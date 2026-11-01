using System;
using GearsAPI.Settings;
using GearsAPI.Settings.Global;
using GearsAPI.Settings.World;
using UnityEngine;

/// <summary>
/// The settings page, when Gears is installed. This is the only class that uses GearsAPI: Gears finds it by scanning
/// and calls it, and without Gears nothing does, so the mod runs on its defaults (GearsAPI.dll ships in the mod
/// folder so the type still loads). All settings are Gears global settings, which belong to the player and are never
/// sent to the server.
///
/// Every row follows the value selected in the menu, not just the applied one, so changes preview live; Back and
/// closing the window put the selected values back, which previews the applied ones again.
/// </summary>
public class GfxGears : IGearsModApi
{
    private static ISwitchGlobalSetting<bool> enabled;
    private static ISelectorGlobalSetting<GfxPreset> preset;
    private static ISelectorGlobalSetting<GfxTonemapping> tonemapping;
    private static ISliderGlobalSetting<float> exposure;
    private static ISliderGlobalSetting<int> contrast;
    private static ISliderGlobalSetting<int> saturation;
    private static ISliderGlobalSetting<int> whiteBalance;
    private static IColorSelectorGlobalSetting tint;
    private static ISliderGlobalSetting<float> fogDensity;
    private static IColorSelectorGlobalSetting fogTint;
    private static ISliderGlobalSetting<float> vignette;
    private static ISliderGlobalSetting<float> grain;
    private static ISliderGlobalSetting<float> bloom;
    private static ISliderGlobalSetting<float> timeOfDay;
    private static ISliderGlobalSetting<float> weather;
    private static ISliderGlobalSetting<float> bloodMoon;

    private static ISelectorGlobalSetting<GfxShadowDistance> shadowDistance;
    private static ISelectorGlobalSetting<GfxShadowResolution> shadowResolution;
    private static ISelectorGlobalSetting<GfxContactShadows> contactShadows;
    private static ISliderGlobalSetting<float> contactShadowLength;

    private static ISliderGlobalSetting<float> lodDistance;
    private static ISelectorGlobalSetting<GfxTreeDistance> treeDistance;
    private static ISelectorGlobalSetting<GfxGrassDistance> grassDistance;
    private static ISwitchGlobalSetting<bool> anisotropic16x;

    private static ISliderGlobalSetting<float> rainWetness;
    private static ISliderGlobalSetting<float> puddleCoverage;
    private static ISliderGlobalSetting<float> snowCover;

    /// <summary>True while the preset is writing the rows it drives, so they don't turn it to Custom.</summary>
    private static bool applyingPreset;

    public void InitMod(IGearsMod modInstance)
    {
        GraphicsExpanded.GearsLoaded = true;
        IModGlobalSettings settings = modInstance.GlobalSettings;

        enabled = Get<ISwitchGlobalSetting<bool>>(settings, "Look", "General", "Enabled");
        preset = Get<ISelectorGlobalSetting<GfxPreset>>(settings, "Look", "General", "Preset");
        tonemapping = Get<ISelectorGlobalSetting<GfxTonemapping>>(settings, "Look", "Color", "Tonemapping");
        exposure = Get<ISliderGlobalSetting<float>>(settings, "Look", "Color", "Exposure");
        contrast = Get<ISliderGlobalSetting<int>>(settings, "Look", "Color", "Contrast");
        saturation = Get<ISliderGlobalSetting<int>>(settings, "Look", "Color", "Saturation");
        whiteBalance = Get<ISliderGlobalSetting<int>>(settings, "Look", "Color", "WhiteBalance");
        tint = Get<IColorSelectorGlobalSetting>(settings, "Look", "Color", "Tint");
        fogDensity = Get<ISliderGlobalSetting<float>>(settings, "Look", "Atmosphere", "FogDensity");
        fogTint = Get<IColorSelectorGlobalSetting>(settings, "Look", "Atmosphere", "FogTint");
        vignette = Get<ISliderGlobalSetting<float>>(settings, "Look", "Film", "Vignette");
        grain = Get<ISliderGlobalSetting<float>>(settings, "Look", "Film", "FilmGrain");
        bloom = Get<ISliderGlobalSetting<float>>(settings, "Look", "Film", "Bloom");
        timeOfDay = Get<ISliderGlobalSetting<float>>(settings, "Look", "Dynamic", "TimeOfDay");
        weather = Get<ISliderGlobalSetting<float>>(settings, "Look", "Dynamic", "Weather");
        bloodMoon = Get<ISliderGlobalSetting<float>>(settings, "Look", "Dynamic", "BloodMoon");

        shadowDistance = Get<ISelectorGlobalSetting<GfxShadowDistance>>(settings, "Shadows", "Sun", "ShadowDistance");
        shadowResolution = Get<ISelectorGlobalSetting<GfxShadowResolution>>(settings, "Shadows", "Sun", "ShadowResolution");
        contactShadows = Get<ISelectorGlobalSetting<GfxContactShadows>>(settings, "Shadows", "Contact", "ContactShadows");
        contactShadowLength = Get<ISliderGlobalSetting<float>>(settings, "Shadows", "Contact", "ContactShadowLength");

        lodDistance = Get<ISliderGlobalSetting<float>>(settings, "Detail", "Distance", "LodDistance");
        treeDistance = Get<ISelectorGlobalSetting<GfxTreeDistance>>(settings, "Detail", "Distance", "TreeDistance");
        grassDistance = Get<ISelectorGlobalSetting<GfxGrassDistance>>(settings, "Detail", "Distance", "GrassDistance");
        anisotropic16x = Get<ISwitchGlobalSetting<bool>>(settings, "Detail", "Textures", "Anisotropic16x");

        rainWetness = Get<ISliderGlobalSetting<float>>(settings, "Weather", "Surfaces", "RainWetness");
        puddleCoverage = Get<ISliderGlobalSetting<float>>(settings, "Weather", "Surfaces", "Puddles");
        snowCover = Get<ISliderGlobalSetting<float>>(settings, "Weather", "Surfaces", "SnowCover");

        Listen(enabled, v => GfxSettings.Enabled = v);
        Listen(preset, PresetSelected);
        Listen(tonemapping, v => { GfxSettings.Look.Tonemapping = v; LookEdited(); });
        Listen(exposure, v => { GfxSettings.Look.Exposure = v; LookEdited(); });
        Listen(contrast, v => { GfxSettings.Look.Contrast = v; LookEdited(); });
        Listen(saturation, v => { GfxSettings.Look.Saturation = v; LookEdited(); });
        Listen(whiteBalance, v => { GfxSettings.Look.WhiteBalance = v; LookEdited(); });
        Listen(tint, v => { GfxSettings.Look.Tint = v; LookEdited(); });
        Listen(fogDensity, v => { GfxSettings.Look.FogDensity = v; LookEdited(); });
        Listen(fogTint, v => { GfxSettings.Look.FogTint = v; LookEdited(); });
        Listen(vignette, v => { GfxSettings.Look.Vignette = v; LookEdited(); });
        Listen(grain, v => { GfxSettings.Look.Grain = v; LookEdited(); });
        Listen(bloom, v => { GfxSettings.Look.Bloom = v; LookEdited(); });
        Listen(timeOfDay, v => { GfxSettings.Look.TimeOfDay = v; LookEdited(); });
        Listen(weather, v => { GfxSettings.Look.Weather = v; LookEdited(); });
        Listen(bloodMoon, v => { GfxSettings.Look.BloodMoon = v; LookEdited(); });

        Listen(shadowDistance, v => GfxSettings.ShadowDistance = v);
        Listen(shadowResolution, v => GfxSettings.ShadowResolution = v);
        Listen(contactShadows, v => GfxSettings.ContactShadows = v);
        Listen(contactShadowLength, v => GfxSettings.ContactShadowLength = v);

        Listen(lodDistance, v => GfxSettings.LodDistance = v);
        Listen(treeDistance, v => GfxSettings.TreeDistance = v);
        Listen(grassDistance, v => GfxSettings.GrassDistance = v);
        Listen(anisotropic16x, v => GfxSettings.Anisotropic16x = v);

        Listen(rainWetness, v => GfxSettings.RainWetness = v);
        Listen(puddleCoverage, v => GfxSettings.PuddleCoverage = v);
        Listen(snowCover, v => GfxSettings.SnowCover = v);

        IControlBindingSetting compareKey = Get<IControlBindingSetting>(settings, "Look", "General", "CompareKey");
        if (compareKey != null && GfxInput.Actions != null)
        {
            compareKey.PlayerAction = GfxInput.Actions.Compare;
            compareKey.OnSettingApplied += _ => GfxInput.SaveBindings();
        }
    }

    /// <summary>The player's saved values are in now (restoring them raised no events).</summary>
    public void OnGlobalSettingsLoaded(IModGlobalSettings modSettings)
    {
        Read(enabled, v => GfxSettings.Enabled = v);
        Read(preset, v => GfxSettings.Preset = v);
        Read(tonemapping, v => GfxSettings.Look.Tonemapping = v);
        Read(exposure, v => GfxSettings.Look.Exposure = v);
        Read(contrast, v => GfxSettings.Look.Contrast = v);
        Read(saturation, v => GfxSettings.Look.Saturation = v);
        Read(whiteBalance, v => GfxSettings.Look.WhiteBalance = v);
        Read(tint, v => GfxSettings.Look.Tint = v);
        Read(fogDensity, v => GfxSettings.Look.FogDensity = v);
        Read(fogTint, v => GfxSettings.Look.FogTint = v);
        Read(vignette, v => GfxSettings.Look.Vignette = v);
        Read(grain, v => GfxSettings.Look.Grain = v);
        Read(bloom, v => GfxSettings.Look.Bloom = v);
        Read(timeOfDay, v => GfxSettings.Look.TimeOfDay = v);
        Read(weather, v => GfxSettings.Look.Weather = v);
        Read(bloodMoon, v => GfxSettings.Look.BloodMoon = v);

        Read(shadowDistance, v => GfxSettings.ShadowDistance = v);
        Read(shadowResolution, v => GfxSettings.ShadowResolution = v);
        Read(contactShadows, v => GfxSettings.ContactShadows = v);
        Read(contactShadowLength, v => GfxSettings.ContactShadowLength = v);

        Read(lodDistance, v => GfxSettings.LodDistance = v);
        Read(treeDistance, v => GfxSettings.TreeDistance = v);
        Read(grassDistance, v => GfxSettings.GrassDistance = v);
        Read(anisotropic16x, v => GfxSettings.Anisotropic16x = v);

        Read(rainWetness, v => GfxSettings.RainWetness = v);
        Read(puddleCoverage, v => GfxSettings.PuddleCoverage = v);
        Read(snowCover, v => GfxSettings.SnowCover = v);

        // A preset other than Custom always matches its rows, since editing one turns it to Custom. Rows a mod update
        // added (saved values don't have them) or preset values it changed would otherwise keep their defaults, so
        // put the preset's values back on its rows and save them.
        if (GfxSettings.Presets.TryGetValue(GfxSettings.Preset, out GfxLook look) && !look.SameAs(GfxSettings.Look))
        {
            MoveRows(look, false);
            GfxSettings.Look = look;
            modSettings.SaveSettings();
        }
    }

    public void OnWorldSettingsLoaded(IModWorldSettings worldSettings)
    {
    }

    private static T Get<T>(IModGlobalSettings settings, string tab, string category, string name) where T : class, IGlobalModSetting
    {
        T setting = settings.GetTab(tab)?.GetCategory(category)?.GetSetting<T>(name);
        if (setting == null)
            Log.Warning(string.Format("[GraphicsExpanded] Gears has no setting {0}.{1}.{2}; check ModSettings.xml and the [Gears] lines above", tab, category, name));
        return setting;
    }

    private static void Listen<T>(IValueModSetting<T> setting, Action<T> apply)
    {
        if (setting != null)
            setting.OnSelectedChanged += (_setting, value) => apply(value);
    }

    private static void Read<T>(IValueModSetting<T> setting, Action<T> apply)
    {
        if (setting != null)
            apply(setting.SettingValue);
    }

    // ---- The preset, which moves the rows of the Look tab it sits on ----

    private static void PresetSelected(GfxPreset value)
    {
        GfxSettings.Preset = value;
        if (!GfxSettings.Presets.TryGetValue(value, out GfxLook look))
            return;     // Custom: whatever the rows say

        MoveRows(look, true);
        // In case a row is missing from ModSettings.xml, the preset still applies in full
        GfxSettings.Look = look;
    }

    /// <summary>
    /// Puts a preset's values on the rows it drives: as the menu's selection while the player picks (Apply then keeps
    /// them, Back undoes them), or as the applied values when the saved settings load.
    /// </summary>
    private static void MoveRows(GfxLook look, bool inMenu)
    {
        applyingPreset = true;
        try
        {
            Select(tonemapping, look.Tonemapping, inMenu);
            Select(exposure, look.Exposure, inMenu);
            Select(contrast, Mathf.RoundToInt(look.Contrast), inMenu);
            Select(saturation, Mathf.RoundToInt(look.Saturation), inMenu);
            Select(whiteBalance, Mathf.RoundToInt(look.WhiteBalance), inMenu);
            Select(tint, look.Tint, inMenu);
            Select(fogDensity, look.FogDensity, inMenu);
            Select(fogTint, look.FogTint, inMenu);
            Select(vignette, look.Vignette, inMenu);
            Select(grain, look.Grain, inMenu);
            Select(bloom, look.Bloom, inMenu);
            Select(timeOfDay, look.TimeOfDay, inMenu);
            Select(weather, look.Weather, inMenu);
            Select(bloodMoon, look.BloodMoon, inMenu);
        }
        finally
        {
            applyingPreset = false;
        }
    }

    private static void LookEdited()
    {
        if (applyingPreset || preset == null || preset.SelectedValue == GfxPreset.Custom)
            return;
        Select(preset, GfxPreset.Custom, true);
    }

    private static void Select<T>(IValueModSetting<T> setting, T value, bool inMenu)
    {
        if (setting == null)
            return;
        if (!inMenu)
            setting.SettingValue = value;
        setting.SelectedValue = value;
        if (inMenu)
            setting.RefreshUI();
    }
}
