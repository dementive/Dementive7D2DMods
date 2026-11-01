using System.Collections.Generic;
using UnityEngine;

public enum GfxPreset
{
    Vanilla,
    Natural,
    Cinematic,
    Custom,
}

public enum GfxTonemapping
{
    Vanilla,
    Neutral,
    ACES,
}

public enum GfxShadowDistance
{
    Menu,
    Meters400,
    Meters500,
    Meters600,
    Meters800,
}

public enum GfxShadowResolution
{
    Menu,
    Res4096,
    Res8192,
}

public enum GfxContactShadows
{
    Menu,
    Off,
    On,
}

public enum GfxTreeDistance
{
    Menu,
    PlusOne,
    PlusTwo,
}

public enum GfxVolumetricQuality
{
    Off,
    Low,
    Medium,
    High,
}

public enum GfxWaterQuality
{
    Off,
    Medium,
    High,
}

public enum GfxGrassDistance
{
    Menu,
    Meters150,
    Meters200,
}

/// <summary>
/// Everything a preset sets. Every value is an adjustment on top of vanilla, so zeros, white and 100% are the
/// vanilla look. <see cref="GfxMood"/> adds the dynamic grading on top before it's applied.
/// </summary>
public struct GfxLook
{
    public GfxTonemapping Tonemapping;

    /// <summary>Exposure in EV (stops).</summary>
    public float Exposure;

    /// <summary>Added to the color grading's contrast, saturation and temperature (-100 to 100 there).</summary>
    public float Contrast;
    public float Saturation;
    public float WhiteBalance;

    /// <summary>Multiplies the color grading's color filter.</summary>
    public Color Tint;

    /// <summary>Fog density as a fraction of vanilla.</summary>
    public float FogDensity;

    /// <summary>Multiplies the fog color.</summary>
    public Color FogTint;

    /// <summary>Vignette intensity added (0 to 0.5) and film grain intensity added (0 to 1).</summary>
    public float Vignette;
    public float Grain;

    /// <summary>Bloom intensity as a fraction of vanilla.</summary>
    public float Bloom;

    /// <summary>How strongly the time of day, the weather and the Blood Moon shift the look (0 to 1).</summary>
    public float TimeOfDay;
    public float Weather;
    public float BloodMoon;

    public GfxLook(GfxTonemapping tonemapping, float exposure, float contrast, float saturation, float whiteBalance,
        Color tint, float fogDensity, Color fogTint, float vignette, float grain, float bloom,
        float timeOfDay, float weather, float bloodMoon)
    {
        Tonemapping = tonemapping;
        Exposure = exposure;
        Contrast = contrast;
        Saturation = saturation;
        WhiteBalance = whiteBalance;
        Tint = tint;
        FogDensity = fogDensity;
        FogTint = fogTint;
        Vignette = vignette;
        Grain = grain;
        Bloom = bloom;
        TimeOfDay = timeOfDay;
        Weather = weather;
        BloodMoon = bloodMoon;
    }

    public bool SameAs(GfxLook other)
    {
        return Tonemapping == other.Tonemapping && Exposure == other.Exposure && Contrast == other.Contrast
            && Saturation == other.Saturation && WhiteBalance == other.WhiteBalance && Tint == other.Tint
            && FogDensity == other.FogDensity && FogTint == other.FogTint && Vignette == other.Vignette
            && Grain == other.Grain && Bloom == other.Bloom && TimeOfDay == other.TimeOfDay
            && Weather == other.Weather && BloodMoon == other.BloodMoon;
    }
}

/// <summary>
/// The player's settings. Gears fills them in when it's installed (see <see cref="GfxGears"/>); otherwise they keep
/// these defaults, which the gfxe console command can change for the session. Nothing here is sent anywhere: it's
/// all per player, so every player in a multiplayer game can pick their own.
/// </summary>
public static class GfxSettings
{
    public static readonly Dictionary<GfxPreset, GfxLook> Presets = new Dictionary<GfxPreset, GfxLook>
    {
        { GfxPreset.Vanilla, new GfxLook(GfxTonemapping.Vanilla, 0f, 0, 0, 0, Color.white, 1f, Color.white,
            0f, 0f, 1f, 0f, 0f, 0f) },
        // A little more contrast and color, a touch warmer, less grey haze; half-strength dynamic grading
        { GfxPreset.Natural, new GfxLook(GfxTonemapping.Vanilla, 0f, 8, 6, 3, Color.white, 0.85f, Color.white,
            0f, 0f, 1f, 0.5f, 0.5f, 1f) },
        // Filmic tonemapping, warmer, with a slight amber tint, a film finish and full dynamic grading
        { GfxPreset.Cinematic, new GfxLook(GfxTonemapping.ACES, 0.25f, 12, 4, 6, new Color32(255, 246, 235, 255), 0.9f, Color.white,
            0.25f, 0.15f, 1.3f, 1f, 1f, 1f) },
    };

    public const GfxPreset DefaultPreset = GfxPreset.Natural;

    public static bool Enabled = true;
    public static GfxPreset Preset = DefaultPreset;
    public static GfxLook Look = Presets[DefaultPreset];

    /// <summary>
    /// The look on screen this frame: <see cref="CurrentLook"/> with the dynamic grading added (see
    /// <see cref="GfxApply.Update"/>). Vanilla until the first frame works it out.
    /// </summary>
    public static GfxLook Effective = Presets[GfxPreset.Vanilla];

    public static GfxShadowDistance ShadowDistance = GfxShadowDistance.Menu;
    public static GfxShadowResolution ShadowResolution = GfxShadowResolution.Menu;
    public static GfxContactShadows ContactShadows = GfxContactShadows.Menu;

    /// <summary>Contact shadow length as a fraction of vanilla.</summary>
    public static float ContactShadowLength = 1f;

    /// <summary>Level of detail distance as a fraction of vanilla.</summary>
    public static float LodDistance = 1f;
    public static GfxTreeDistance TreeDistance = GfxTreeDistance.Menu;
    public static GfxGrassDistance GrassDistance = GfxGrassDistance.Menu;
    public static bool Anisotropic16x;

    /// <summary>Rain wetness and snow cover strength (0 to 1), and the share of flat ground puddles can cover (0 to 0.8).</summary>
    public static float RainWetness = 1f;
    public static float PuddleCoverage = 0.4f;
    public static float SnowCover = 1f;

    /// <summary>Sunbeams and height fog: quality, and strengths (sunbeams and height fog 0 to 2, the rest 0 to 1).</summary>
    public static GfxVolumetricQuality VolumetricQuality = GfxVolumetricQuality.Medium;
    public static float Sunbeams = 1f;
    public static float IndoorDust = 0.5f;
    public static float HeightFog = 1f;
    public static float MorningMist = 1f;

    /// <summary>Distance haze strength, 0 to 2.</summary>
    public static float DistanceHaze = 1f;

    /// <summary>The water: off (the game's), Medium (the game's reflection probe) or High (and screen-space reflections), and wave strength 0 to 2.</summary>
    public static GfxWaterQuality WaterQuality = GfxWaterQuality.High;
    public static float WaterWaves = 1f;

    /// <summary>
    /// True while the compare key is held. Look and shadows go back to vanilla so they can be compared; draw distances
    /// stay, since reloading trees and grass would stutter.
    /// </summary>
    public static bool CompareHeld;

    public static bool LookActive => Enabled && !CompareHeld;
    public static bool ShadowsActive => Enabled && !CompareHeld;
    public static bool DetailActive => Enabled;

    /// <summary>The look to use right now: the player's, or vanilla's while it's off or being compared.</summary>
    public static GfxLook CurrentLook => LookActive ? Look : Presets[GfxPreset.Vanilla];

    public static bool UsePreset(GfxPreset preset)
    {
        if (!Presets.TryGetValue(preset, out GfxLook look))
            return false;
        Preset = preset;
        Look = look;
        return true;
    }

    public static float ShadowDistanceMeters(GfxShadowDistance distance)
    {
        return distance switch
        {
            GfxShadowDistance.Meters400 => 400f,
            GfxShadowDistance.Meters500 => 500f,
            GfxShadowDistance.Meters600 => 600f,
            GfxShadowDistance.Meters800 => 800f,
            _ => 0f,
        };
    }

    public static int ShadowResolutionPixels(GfxShadowResolution resolution)
    {
        return resolution switch
        {
            GfxShadowResolution.Res4096 => 4096,
            GfxShadowResolution.Res8192 => 8192,
            _ => 0,
        };
    }

    /// <summary>Extra rings of 128 m decoration chunks around the player.</summary>
    public static int TreeRings(GfxTreeDistance distance)
    {
        return distance switch
        {
            GfxTreeDistance.PlusOne => 1,
            GfxTreeDistance.PlusTwo => 2,
            _ => 0,
        };
    }

    public static float GrassDistanceMeters(GfxGrassDistance distance)
    {
        return distance switch
        {
            GfxGrassDistance.Meters150 => 150f,
            GfxGrassDistance.Meters200 => 200f,
            _ => 0f,
        };
    }
}
