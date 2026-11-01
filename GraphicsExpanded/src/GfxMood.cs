using UnityEngine;

/// <summary>
/// Dynamic grading: shifts the look with the time of day, the weather and the Blood Moon, on top of the player's
/// look. It only reads what every client already has (the world time and weather come from the server), so in
/// multiplayer each player works it out locally and nothing is sent.
/// Time of day and weather fade the more enclosed the player is, by the game's own measure (the sky light reaching
/// them), so a lit room at night doesn't turn blue. The Blood Moon stays: it's the mood of the whole night.
/// </summary>
public static class GfxMood
{
    /// <summary>Time constant of the easing, in seconds: a change is 95% done after three.</summary>
    private const float EaseSeconds = 1f;

    private static readonly Color NightTint = new Color32(230, 240, 255, 255);
    private static readonly Color BloodMoonTint = new Color32(255, 200, 190, 255);
    private static readonly Color BloodMoonFogTint = new Color32(255, 180, 170, 255);

    // How strongly each condition applies right now, 0 to 1
    private static float golden, night, rain, snow, bloodMoon, outdoors = 1f;
    private static bool started;

    /// <summary>The look with this frame's dynamic grading added.</summary>
    public static GfxLook Apply(GfxLook look, float deltaTime)
    {
        Update(deltaTime);
        float time = look.TimeOfDay * outdoors;
        float weather = look.Weather * outdoors;
        float g = golden * time;
        float n = night * time;
        float r = rain * weather;
        float s = snow * weather;
        float b = bloodMoon * look.BloodMoon;

        look.Exposure += 0.10f * g;
        look.WhiteBalance += 15f * g - 15f * n - 6f * r - 10f * s;
        look.Saturation += 8f * g - 20f * n - 20f * r - 8f * s - 15f * b;
        look.Contrast += -8f * r + 12f * b;
        look.Tint *= Color.Lerp(Color.white, NightTint, n) * Color.Lerp(Color.white, BloodMoonTint, b);
        look.FogTint *= Color.Lerp(Color.white, BloodMoonFogTint, b);
        look.FogDensity *= 1f + 0.3f * b;
        return look;
    }

    private static void Update(float deltaTime)
    {
        World world = GameManager.Instance != null ? GameManager.Instance.World : null;
        EntityPlayerLocal player = world?.GetPrimaryPlayer();
        if (player == null)
        {
            golden = night = rain = snow = bloodMoon = 0f;
            outdoors = 1f;
            started = false;
            return;
        }

        float hours = (world.worldTime % 24000UL) / 1000f;
        float dawn = SkyManager.GetDawnTime();
        float dusk = SkyManager.GetDuskTime();
        WeatherManager weather = WeatherManager.Instance;

        // Straight to the current values on the first frame in a world, eased after that
        float ease = started ? 1f - Mathf.Exp(-deltaTime / EaseSeconds) : 1f;
        started = true;
        golden = Ease(golden, GoldenHour(hours, dawn, dusk), ease);
        night = Ease(night, SkyManager.isAllTimeNight ? 1f : Night(hours, dawn, dusk), ease);
        rain = Ease(rain, weather != null ? Fraction(weather.GetCurrentRainfallPercent()) : 0f, ease);
        snow = Ease(snow, weather != null ? Fraction(weather.GetCurrentSnowfallPercent()) : 0f, ease);
        bloodMoon = Ease(bloodMoon, Mathf.Clamp01(SkyManager.BloodMoonVisiblePercent()), ease);
        outdoors = Ease(outdoors, 1f - Mathf.Clamp01(player.GetAmountEnclosed()), ease);
    }

    /// <summary>
    /// Warm light around sunrise and sunset: rises over the half hour before dawn and fades over the 90 minutes after
    /// it, then rises over the 90 minutes before dusk and fades over the half hour after it, crossing into night.
    /// </summary>
    private static float GoldenHour(float hours, float dawn, float dusk)
    {
        if (hours >= dawn - 0.5f && hours < dawn)
            return Mathf.SmoothStep(0f, 1f, (hours - (dawn - 0.5f)) / 0.5f);
        if (hours >= dawn && hours < dawn + 1.5f)
            return Mathf.SmoothStep(0f, 1f, 1f - (hours - dawn) / 1.5f);
        if (hours >= dusk - 1.5f && hours < dusk)
            return Mathf.SmoothStep(0f, 1f, (hours - (dusk - 1.5f)) / 1.5f);
        if (hours >= dusk && hours < dusk + 0.5f)
            return Mathf.SmoothStep(0f, 1f, 1f - (hours - dusk) / 0.5f);
        return 0f;
    }

    /// <summary>Dusk to dawn, fading in over the half hour after dusk and out over the half hour before dawn.</summary>
    private static float Night(float hours, float dawn, float dusk)
    {
        if (hours >= dusk && hours < dusk + 0.5f)
            return Mathf.SmoothStep(0f, 1f, (hours - dusk) / 0.5f);
        if (hours >= dusk + 0.5f || hours < dawn - 0.5f)
            return 1f;
        if (hours >= dawn - 0.5f && hours < dawn)
            return Mathf.SmoothStep(0f, 1f, (dawn - hours) / 0.5f);
        return 0f;
    }

    /// <summary>The weather's rainfall and snowfall, as 0 to 1 whether the game keeps them that way or as percent.</summary>
    public static float Fraction(float value)
    {
        return Mathf.Clamp01(value > 1f ? value / 100f : value);
    }

    private static float Ease(float current, float target, float amount)
    {
        return current + (target - current) * amount;
    }
}
