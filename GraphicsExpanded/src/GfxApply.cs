using System;
using PI.NGSS;
using UnityEngine;
using UnityEngine.Rendering.PostProcessing;

/// <summary>
/// Puts the settings on top of what the game's video menu set. Every frame it compares the settings with what was
/// last applied and only touches what changed, so dragging a slider in the Gears menu previews it live.
/// Fog is the exception: the game sets it every frame, so <see cref="GfxPatch_FogGlobals"/> adjusts it there.
/// </summary>
public static class GfxApply
{
    private struct SunState
    {
        public GfxShadowDistance Distance;
        public GfxShadowResolution Resolution;

        public bool SameAs(SunState other) => Distance == other.Distance && Resolution == other.Resolution;
    }

    private static Camera lookCamera;
    private static bool lookApplied;
    private static GfxLook lookValues;

    private static Camera contactCamera;
    private static GfxContactShadows contactMode;
    private static float contactLength = 1f;

    private static SunState sunApplied;
    private static float lodApplied = 1f;
    private static bool anisoApplied;
    private static GfxGrassDistance grassApplied;

    private static ColorBase colorBase;
    private static FilmBase filmBase;
    private static NGSS_FrustumShadows_7DTD baseFrustum;
    private static float baseRayScale;
    private static NGSS_Directional baseSunNgss;
    private static NGSS_Directional.ShadowMapResolution baseSunNgssResolution;
    private static bool filterLimitsChanged;

    /// <summary>Called every frame (ModEvents.GameUpdate).</summary>
    public static void Update()
    {
        if (GameManager.IsDedicatedServer)
            return;
        try
        {
            GfxInput.Update();

            Camera camera = PlayerCamera();
            GfxWeather.Update(Player(), camera, Time.deltaTime);
            GfxSettings.Effective = GfxMood.Apply(GfxSettings.CurrentLook, Time.deltaTime);
            if (camera != lookCamera || !lookApplied || !GfxSettings.Effective.SameAs(lookValues))
                ApplyColor(camera);

            GfxContactShadows mode = GfxSettings.ShadowsActive ? GfxSettings.ContactShadows : GfxContactShadows.Menu;
            float length = GfxSettings.ShadowsActive ? GfxSettings.ContactShadowLength : 1f;
            if (camera != contactCamera || mode != contactMode || length != contactLength)
                ApplyContactShadows(camera);

            if (!CurrentSun().SameAs(sunApplied))
            {
                // The postfix on it puts ours on top again, or leaves vanilla's
                GameOptionsManager.ApplyShadowQuality();
            }

            float lod = GfxSettings.DetailActive ? GfxSettings.LodDistance : 1f;
            if (lod != lodApplied)
            {
                lodApplied = lod;
                QualitySettings.lodBias = GameOptionsManager.GetLODBias();
            }

            bool aniso = GfxSettings.DetailActive && GfxSettings.Anisotropic16x;
            if (aniso != anisoApplied)
                GameOptionsManager.ApplyTextureFilter();

            GfxGrassDistance grass = GfxSettings.DetailActive ? GfxSettings.GrassDistance : GfxGrassDistance.Menu;
            if (grass != grassApplied)
            {
                grassApplied = grass;
                ApplyGrass();
            }
        }
        catch (Exception e)
        {
            Log.Error("[GraphicsExpanded] " + e);
        }
    }

    /// <summary>After the game applied its camera options (it resets the contact shadows and brightness then).</summary>
    public static void OnCameraOptionsApplied(Camera camera)
    {
        ApplyColor(camera);
        ApplyContactShadows(camera);
    }

    private static EntityPlayerLocal Player()
    {
        World world = GameManager.Instance != null ? GameManager.Instance.World : null;
        return world?.GetPrimaryPlayer();
    }

    private static Camera PlayerCamera()
    {
        EntityPlayerLocal player = Player();
        return player != null ? player.playerCamera : null;
    }

    private static SunState CurrentSun()
    {
        if (!GfxSettings.ShadowsActive)
            return default;
        return new SunState { Distance = GfxSettings.ShadowDistance, Resolution = GfxSettings.ShadowResolution };
    }

    // ---- Color grading and film finish ----

    private static void ApplyColor(Camera camera)
    {
        lookCamera = camera;
        lookValues = GfxSettings.Effective;
        // Without a camera, try again next frame; a camera without color grading has nothing to apply to
        lookApplied = camera != null;
        if (camera == null)
            return;
        PostProcessVolume volume = camera.GetComponent<PostProcessVolume>();
        if (volume == null)
            return;
        // The volume's own copy of the profile, which the game edits too; the shared asset is never touched
        PostProcessProfile profile = volume.profile;
        if (profile == null || !profile.TryGetSettings(out ColorGrading grading))
            return;

        if (colorBase == null || colorBase.Profile != profile)
        {
            colorBase = new ColorBase(profile, grading);
            filmBase = new FilmBase(profile);
            Log.Out("[GraphicsExpanded] Vanilla color grading: " + colorBase);
            Log.Out("[GraphicsExpanded] Vanilla film effects: " + filmBase);
        }

        if (GfxSettings.LookActive)
        {
            colorBase.Apply(grading, lookValues);
            filmBase.Apply(lookValues);
        }
        else
        {
            colorBase.Restore(grading);
            filmBase.Restore();
        }
    }

    /// <summary>
    /// The vignette, film grain and bloom as vanilla had them, like <see cref="ColorBase"/>. A profile without a
    /// vignette or grain gets one, switched off, so it has something to turn on. Bloom is only scaled: whether it's on
    /// at all is the video menu's call.
    /// </summary>
    private class FilmBase
    {
        private readonly Vignette vignette;
        private readonly Grain grain;
        private readonly Bloom bloom;

        private readonly Saved<bool> vignetteOn, vignetteRounded;
        private readonly Saved<VignetteMode> vignetteMode;
        private readonly Saved<float> vignetteIntensity, vignetteSmoothness, vignetteRoundness;
        private readonly Saved<Color> vignetteColor;
        private readonly Saved<bool> grainOn, grainColored;
        private readonly Saved<float> grainIntensity, grainSize, grainLuminance;
        private readonly Saved<float> bloomIntensity;

        public FilmBase(PostProcessProfile profile)
        {
            if (!profile.TryGetSettings(out vignette))
            {
                vignette = profile.AddSettings<Vignette>();
                vignette.enabled.Override(false);
            }
            if (!profile.TryGetSettings(out grain))
            {
                grain = profile.AddSettings<Grain>();
                grain.enabled.Override(false);
            }
            profile.TryGetSettings(out bloom);

            Vignette vignetteDefaults = ScriptableObject.CreateInstance<Vignette>();
            Grain grainDefaults = ScriptableObject.CreateInstance<Grain>();
            Bloom bloomDefaults = ScriptableObject.CreateInstance<Bloom>();
            try
            {
                vignetteOn = new Saved<bool>(vignette.enabled, vignetteDefaults.enabled);
                vignetteRounded = new Saved<bool>(vignette.rounded, vignetteDefaults.rounded);
                vignetteMode = new Saved<VignetteMode>(vignette.mode, vignetteDefaults.mode);
                vignetteIntensity = new Saved<float>(vignette.intensity, vignetteDefaults.intensity);
                vignetteSmoothness = new Saved<float>(vignette.smoothness, vignetteDefaults.smoothness);
                vignetteRoundness = new Saved<float>(vignette.roundness, vignetteDefaults.roundness);
                vignetteColor = new Saved<Color>(vignette.color, vignetteDefaults.color);
                grainOn = new Saved<bool>(grain.enabled, grainDefaults.enabled);
                grainColored = new Saved<bool>(grain.colored, grainDefaults.colored);
                grainIntensity = new Saved<float>(grain.intensity, grainDefaults.intensity);
                grainSize = new Saved<float>(grain.size, grainDefaults.size);
                grainLuminance = new Saved<float>(grain.lumContrib, grainDefaults.lumContrib);
                if (bloom != null)
                    bloomIntensity = new Saved<float>(bloom.intensity, bloomDefaults.intensity);
            }
            finally
            {
                UnityEngine.Object.Destroy(vignetteDefaults);
                UnityEngine.Object.Destroy(grainDefaults);
                UnityEngine.Object.Destroy(bloomDefaults);
            }
        }

        public void Apply(GfxLook look)
        {
            if (look.Vignette > 0f)
            {
                // Added to vanilla's vignette if it has one; otherwise a plain, soft, black one
                float vanilla = vignetteOn.Effective ? vignetteIntensity.Effective : 0f;
                vignette.enabled.Override(true);
                vignette.intensity.Override(Mathf.Clamp01(vanilla + look.Vignette));
                if (!vignetteOn.Effective)
                {
                    vignette.mode.Override(VignetteMode.Classic);
                    vignette.smoothness.Override(0.4f);
                    vignette.roundness.Override(1f);
                    vignette.rounded.Override(false);
                    vignette.color.Override(Color.black);
                }
            }
            else
            {
                RestoreVignette();
            }

            if (look.Grain > 0f)
            {
                // Fine, black and white, and mostly in the darks and mid-tones
                float vanilla = grainOn.Effective ? grainIntensity.Effective : 0f;
                grain.enabled.Override(true);
                grain.intensity.Override(Mathf.Clamp01(vanilla + look.Grain));
                if (!grainOn.Effective)
                {
                    grain.colored.Override(false);
                    grain.size.Override(1f);
                    grain.lumContrib.Override(0.8f);
                }
            }
            else
            {
                RestoreGrain();
            }

            if (bloom != null)
            {
                if (look.Bloom != 1f)
                    bloom.intensity.Override(bloomIntensity.Effective * look.Bloom);
                else
                    bloomIntensity.Restore(bloom.intensity);
            }
        }

        public void Restore()
        {
            RestoreVignette();
            RestoreGrain();
            if (bloom != null)
                bloomIntensity.Restore(bloom.intensity);
        }

        private void RestoreVignette()
        {
            vignetteOn.Restore(vignette.enabled);
            vignetteRounded.Restore(vignette.rounded);
            vignetteMode.Restore(vignette.mode);
            vignetteIntensity.Restore(vignette.intensity);
            vignetteSmoothness.Restore(vignette.smoothness);
            vignetteRoundness.Restore(vignette.roundness);
            vignetteColor.Restore(vignette.color);
        }

        private void RestoreGrain()
        {
            grainOn.Restore(grain.enabled);
            grainColored.Restore(grain.colored);
            grainIntensity.Restore(grain.intensity);
            grainSize.Restore(grain.size);
            grainLuminance.Restore(grain.lumContrib);
        }

        public override string ToString()
        {
            return string.Format("vignette {0} at {1}, grain {2} at {3}, bloom intensity {4}",
                vignetteOn.Effective ? "on" : "off", vignetteIntensity.Effective,
                grainOn.Effective ? "on" : "off", grainIntensity.Effective,
                bloom != null ? bloomIntensity.Effective.ToString() : "(no bloom)");
        }
    }

    /// <summary>
    /// The color grading parameters as vanilla had them, so the look can be applied as adjustments on top and taken
    /// off again. A parameter the profile doesn't override shows its default value, so that's what counts as vanilla.
    /// </summary>
    private class ColorBase
    {
        public readonly PostProcessProfile Profile;

        private readonly Saved<bool> enabled;
        private readonly Saved<GradingMode> mode;
        private readonly Saved<Tonemapper> tonemapper;
        private readonly Saved<float> postExposure, brightness, contrast, saturation, temperature;
        private readonly Saved<Color> colorFilter;

        public ColorBase(PostProcessProfile profile, ColorGrading grading)
        {
            Profile = profile;
            ColorGrading defaults = ScriptableObject.CreateInstance<ColorGrading>();
            try
            {
                enabled = new Saved<bool>(grading.enabled, defaults.enabled);
                mode = new Saved<GradingMode>(grading.gradingMode, defaults.gradingMode);
                tonemapper = new Saved<Tonemapper>(grading.tonemapper, defaults.tonemapper);
                postExposure = new Saved<float>(grading.postExposure, defaults.postExposure);
                brightness = new Saved<float>(grading.brightness, defaults.brightness);
                contrast = new Saved<float>(grading.contrast, defaults.contrast);
                saturation = new Saved<float>(grading.saturation, defaults.saturation);
                temperature = new Saved<float>(grading.temperature, defaults.temperature);
                colorFilter = new Saved<Color>(grading.colorFilter, defaults.colorFilter);
            }
            finally
            {
                UnityEngine.Object.Destroy(defaults);
            }
        }

        public void Apply(ColorGrading grading, GfxLook look)
        {
            GradingMode gradingMode = mode.Effective;
            Tonemapper tonemap = tonemapper.Effective;
            if (look.Tonemapping != GfxTonemapping.Vanilla && gradingMode != GradingMode.External)
            {
                // Tonemapping only exists in the high definition range mode
                gradingMode = GradingMode.HighDefinitionRange;
                tonemap = look.Tonemapping == GfxTonemapping.ACES ? Tonemapper.ACES : Tonemapper.Neutral;
            }

            float exposure = look.Exposure;
            if (tonemapper.Effective == Tonemapper.Custom && tonemap != Tonemapper.Custom)
            {
                // The video menu's brightness bends the custom tone curve, which the other tonemappers don't use
                exposure += BrightnessAsExposure(grading.toneCurveGamma.value);
            }

            grading.enabled.Override(true);
            grading.gradingMode.Override(gradingMode);
            grading.tonemapper.Override(tonemap);
            if (gradingMode == GradingMode.HighDefinitionRange)
            {
                grading.postExposure.Override(postExposure.Effective + exposure);
                brightness.Restore(grading.brightness);
            }
            else
            {
                // Low definition range has no exposure; brightness (-100 to 100) is the closest it has
                grading.brightness.Override(Mathf.Clamp(brightness.Effective + exposure * 35f, -100f, 100f));
                postExposure.Restore(grading.postExposure);
            }
            grading.contrast.Override(Mathf.Clamp(contrast.Effective + look.Contrast, -100f, 100f));
            grading.saturation.Override(Mathf.Clamp(saturation.Effective + look.Saturation, -100f, 100f));
            grading.temperature.Override(Mathf.Clamp(temperature.Effective + look.WhiteBalance, -100f, 100f));
            Color filter = colorFilter.Effective;
            grading.colorFilter.Override(new Color(filter.r * look.Tint.r, filter.g * look.Tint.g, filter.b * look.Tint.b, filter.a));
        }

        public void Restore(ColorGrading grading)
        {
            enabled.Restore(grading.enabled);
            mode.Restore(grading.gradingMode);
            tonemapper.Restore(grading.tonemapper);
            postExposure.Restore(grading.postExposure);
            brightness.Restore(grading.brightness);
            contrast.Restore(grading.contrast);
            saturation.Restore(grading.saturation);
            temperature.Restore(grading.temperature);
            colorFilter.Restore(grading.colorFilter);
        }

        /// <summary>
        /// Roughly the exposure that matches the custom tone curve's gamma: the menu's brightness lowers it from 1 to
        /// 0.8 at most.
        /// </summary>
        private static float BrightnessAsExposure(float toneCurveGamma)
        {
            if (toneCurveGamma >= 1f || toneCurveGamma <= 0f)
                return 0f;
            return (1f / toneCurveGamma - 1f) * 2f;
        }

        public override string ToString()
        {
            return string.Format("enabled {0}, mode {1}, tonemapper {2}, exposure {3}, brightness {4}, contrast {5}, saturation {6}, temperature {7}, filter {8}",
                enabled.Effective, mode.Effective, tonemapper.Effective, postExposure.Effective, brightness.Effective,
                contrast.Effective, saturation.Effective, temperature.Effective, colorFilter.Effective);
        }
    }

    private readonly struct Saved<T>
    {
        private readonly T value;
        private readonly bool overridden;
        public readonly T Effective;

        public Saved(ParameterOverride<T> parameter, ParameterOverride<T> defaults)
        {
            value = parameter.value;
            overridden = parameter.overrideState;
            Effective = overridden ? value : defaults.value;
        }

        public void Restore(ParameterOverride<T> parameter)
        {
            parameter.value = value;
            parameter.overrideState = overridden;
        }
    }

    // ---- Contact shadows (the game's NGSS frustum shadows) ----

    private static void ApplyContactShadows(Camera camera)
    {
        contactCamera = camera;
        contactMode = GfxSettings.ShadowsActive ? GfxSettings.ContactShadows : GfxContactShadows.Menu;
        contactLength = GfxSettings.ShadowsActive ? GfxSettings.ContactShadowLength : 1f;
        if (camera == null)
            return;
        NGSS_FrustumShadows_7DTD frustum = camera.GetComponent<NGSS_FrustumShadows_7DTD>();
        if (frustum == null)
            return;
        if (frustum != baseFrustum)
        {
            baseFrustum = frustum;
            baseRayScale = frustum.m_rayScale;
        }

        // What GameRenderManager.ApplyCameraOptions does for each shadow quality: off below 3, then more samples
        int quality = GamePrefs.GetInt(EnumGamePrefs.OptionsGfxShadowQuality);
        bool vanillaOn = quality >= 3;
        int iterations, samples;
        switch (quality)
        {
            case 3: iterations = 1; samples = 32; break;
            case 4: iterations = 2; samples = 48; break;
            case 5: iterations = 4; samples = 64; break;
            default:
                // Off in vanilla (or a quality vanilla leaves alone): the middle setting
                iterations = vanillaOn ? frustum.m_shadowsBlurIterations : 2;
                samples = vanillaOn ? frustum.m_raySamples : 48;
                break;
        }

        bool on = contactMode == GfxContactShadows.On || (contactMode == GfxContactShadows.Menu && vanillaOn);
        frustum.m_rayScale = baseRayScale * contactLength;
        if (on)
        {
            // The blur iterations are only read when the effect starts, so restart it if they change
            bool restart = frustum.enabled && frustum.m_shadowsBlurIterations != iterations;
            frustum.m_shadowsBlurIterations = iterations;
            frustum.m_raySamples = samples;
            if (restart)
                frustum.enabled = false;
        }
        frustum.enabled = on;
    }

    // ---- Sun shadows ----

    /// <summary>
    /// Postfix of GameOptionsManager.ApplyShadowQuality, after the game (and Torch, which picks the cascade count)
    /// set the shadow distance and cascades. A longer distance keeps the near cascades where they were in meters, so
    /// close shadows stay as sharp, and stretches the far ones.
    /// </summary>
    public static void ApplySunShadows()
    {
        sunApplied = CurrentSun();
        float meters = GfxSettings.ShadowsActive ? GfxSettings.ShadowDistanceMeters(GfxSettings.ShadowDistance) : 0f;
        float vanilla = QualitySettings.shadowDistance;
        if (meters > vanilla && vanilla > 0f && QualitySettings.shadows != ShadowQuality.Disable)
        {
            if (QualitySettings.shadowCascades == 4)
            {
                Vector3 split = QualitySettings.shadowCascade4Split;
                float first = split.x * vanilla;
                float second = split.y * vanilla;
                float third = Mathf.Max(split.z * vanilla, Mathf.Sqrt(second * meters));
                QualitySettings.shadowCascade4Split = new Vector3(first / meters, second / meters, third / meters);
            }
            else if (QualitySettings.shadowCascades == 2)
            {
                QualitySettings.shadowCascade2Split = QualitySettings.shadowCascade2Split * vanilla / meters;
            }
            QualitySettings.shadowDistance = meters;
        }
        ApplySunResolution();
    }

    /// <summary>Also a postfix of SkyManager.OnShadowDistanceChanged, which sets the sun's shadow map size.</summary>
    public static void ApplySunResolution()
    {
        int pixels = GfxSettings.ShadowsActive ? GfxSettings.ShadowResolutionPixels(GfxSettings.ShadowResolution) : 0;
        if (pixels > 0)
        {
            if (SkyManager.sunLight != null)
                SkyManager.sunLight.shadowCustomResolution = pixels;
            if (SkyManager.moonLight != null)
                SkyManager.moonLight.shadowCustomResolution = pixels;
        }
        UpdateSunNgss(pixels);
    }

    /// <summary>
    /// The sun can carry NGSS's soft shadows, which set the shadow map size and read the cascades when they set up.
    /// Have them set up again with ours, and put their own size back when ours is off.
    /// </summary>
    private static void UpdateSunNgss(int pixels)
    {
        NGSS_Directional ngss = SkyManager.sunLight != null ? SkyManager.sunLight.GetComponent<NGSS_Directional>() : null;
        if (ngss == null)
            return;
        if (ngss != baseSunNgss)
        {
            baseSunNgss = ngss;
            baseSunNgssResolution = ngss.NGSS_SHADOWS_RESOLUTION;
            Log.Out(string.Format("[GraphicsExpanded] Sun NGSS shadows: resolution {0}, update on play {1}", baseSunNgssResolution, !ngss.NGSS_NO_UPDATE_ON_PLAY));
        }
        if (pixels > 0)
            ngss.NGSS_SHADOWS_RESOLUTION = (NGSS_Directional.ShadowMapResolution)pixels;
        else
            ngss.NGSS_SHADOWS_RESOLUTION = baseSunNgssResolution;
        ngss.isSetup = false;
    }

    // ---- Detail ----

    /// <summary>Postfix of GameOptionsManager.ApplyTextureFilter.</summary>
    public static void ApplyTextureFilter()
    {
        anisoApplied = GfxSettings.DetailActive && GfxSettings.Anisotropic16x;
        if (anisoApplied)
        {
            QualitySettings.anisotropicFiltering = AnisotropicFiltering.ForceEnable;
            Texture.SetGlobalAnisotropicFilteringLimits(16, 16);
            filterLimitsChanged = true;
        }
        else if (filterLimitsChanged)
        {
            // Unity's defaults; the game never changes them
            Texture.SetGlobalAnisotropicFilteringLimits(9, 16);
            filterLimitsChanged = false;
        }
    }

    private static void ApplyGrass()
    {
        World world = GameManager.Instance != null ? GameManager.Instance.World : null;
        if (world?.m_ChunkManager == null)
            return;
        // The fade distance comes from SetGrassQuality (patched), the cut-off from each chunk's CheckLODs (patched)
        MeshDescription.SetGrassQuality();
        foreach (ChunkGameObject chunk in world.m_ChunkManager.GetUsedChunkGameObjects())
        {
            if (chunk != null)
                chunk.CheckLODs();
        }
    }

    /// <summary>Called by the transpiled ChunkGameObject.CheckLODs in place of its grass distances.</summary>
    public static float GrassCullDistance(float vanilla)
    {
        float meters = GfxSettings.DetailActive ? GfxSettings.GrassDistanceMeters(GfxSettings.GrassDistance) : 0f;
        return meters > 0f ? meters : vanilla;
    }

    /// <summary>Called by the transpiled DecoManager.UpdateTick in place of reading the tree distance option.</summary>
    public static int TreeRadius(EnumGamePrefs pref)
    {
        int radius = GamePrefs.GetInt(pref);
        return GfxSettings.DetailActive ? radius + GfxSettings.TreeRings(GfxSettings.TreeDistance) : radius;
    }
}
