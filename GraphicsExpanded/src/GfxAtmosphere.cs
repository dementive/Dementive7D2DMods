using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Sunbeams and height fog (Volumetric.shader). The sun, or the moon at night, gets two command buffers while the
/// player camera renders: one grabs its shadow map as it's drawn, the other marches through the air at low
/// resolution right after the light's screen-space shadows, while its shadow cascades are still set up, so the beams
/// come from the game's real shadows. Those are the two slots the game's own sun effects use (its shadow map sharing,
/// NGSS soft shadows and contact shadows), and like its contact shadows they're added before the camera culls:
/// added any later, Unity doesn't run them that frame. A third,
/// on the camera after transparent objects, blurs that and lays it over the picture before the game's post-processing.
/// Only the sun and moon: lamps and torches are Torch's.
///
/// The fog is a layer sitting 15 m above the average ground around the player and thinning with height, thick in
/// valleys and over water. It follows the time of day and weather every client already has, so in multiplayer each
/// player works it out locally and nothing is sent.
/// </summary>
public static class GfxAtmosphere
{
    private const float ClearFog = 0.002f;          // extinction per meter of the fog layer on a clear day
    private const float FogFalloff = 0.077f;        // per meter above the base: half as thick every 9 m
    private const float FogAboveGround = 15f;
    private const float ClearAir = 0.0004f;
    private const float IndoorDust = 0.015f;        // at 100% indoor dust, within DustRange of the player
    private const float DustRange = 25f;
    private const float PhaseG = 0.5f;

    private static Shader shader;
    private static Material material;

    private static Camera camera;
    private static Light light;
    private static bool lightHooked;
    private static bool cameraHooked;
    private static CommandBuffer capture, march, composite;
    private static RenderTexture volume, blurred, lowDepth;
    private static int lowWidth, lowHeight;
    private static GfxVolumetricQuality builtFor;

    private static float groundHeight;
    private static float nextGroundTime;
    private static int frame;
    private static string state = "not started";

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("Volumetric") : null;
        if (shader != null && !shader.isSupported)
        {
            Log.Warning("[GraphicsExpanded] The sunbeam shader isn't supported on this graphics card; sunbeams and height fog are off");
            shader = null;
        }
        if (shader != null)
            material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        Shader.SetGlobalFloat("_GfxMarched", 0f);
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        GfxVolumetricQuality quality = GfxSettings.LookActive ? GfxSettings.VolumetricQuality : GfxVolumetricQuality.Off;
        Light source = player != null && playerCamera != null && quality != GfxVolumetricQuality.Off ? ShadowLight() : null;
        if (source == null)
        {
            state = quality == GfxVolumetricQuality.Off ? "off" : player == null ? "no world" : "no sun or moon shadows to work from";
            Unhook();
            return;
        }

        if (playerCamera != camera || quality != builtFor || RenderSize(playerCamera, quality, out int width, out int height))
        {
            Unhook();
            camera = playerCamera;
            builtFor = quality;
            Build(quality);
        }
        light = source;
        if (!cameraHooked)
        {
            camera.AddCommandBuffer(CameraEvent.AfterForwardAlpha, composite);
            Camera.onPreCull += OnPreCull;
            Camera.onPreRender += OnPreRender;
            Camera.onPostRender += OnPostRender;
            cameraHooked = true;
        }

        SetMedium(player, quality);
        state = string.Format("{0} at {1}x{2}, from the {3}", quality, lowWidth, lowHeight, light == SkyManager.sunLight ? "sun" : "moon");
    }

    /// <summary>The sun by day, the moon by night: whichever is up, casting shadows and brighter.</summary>
    private static Light ShadowLight()
    {
        Light best = null;
        foreach (Light candidate in new[] { SkyManager.sunLight, SkyManager.moonLight })
        {
            if (candidate == null || !candidate.isActiveAndEnabled || candidate.shadows == LightShadows.None || candidate.intensity <= 0.001f)
                continue;
            if (best == null || candidate.intensity > best.intensity)
                best = candidate;
        }
        return best;
    }

    /// <summary>True when the low resolution targets need making again for this camera size.</summary>
    private static bool RenderSize(Camera playerCamera, GfxVolumetricQuality quality, out int width, out int height)
    {
        int divisor = quality == GfxVolumetricQuality.Low ? 4 : 2;
        width = Mathf.Max(1, playerCamera.pixelWidth / divisor);
        height = Mathf.Max(1, playerCamera.pixelHeight / divisor);
        return volume == null || width != lowWidth || height != lowHeight;
    }

    private static void Build(GfxVolumetricQuality quality)
    {
        RenderSize(camera, quality, out lowWidth, out lowHeight);
        Release(ref volume);
        Release(ref blurred);
        Release(ref lowDepth);
        volume = Target(RenderTextureFormat.ARGBHalf, FilterMode.Bilinear, "volume");
        blurred = Target(RenderTextureFormat.ARGBHalf, FilterMode.Bilinear, "blurred");
        lowDepth = Target(RenderTextureFormat.RFloat, FilterMode.Point, "depth");
        material.SetTexture("_GfxVolume", volume);
        material.SetTexture("_GfxBlurred", blurred);
        material.SetTexture("_GfxLowDepth", lowDepth);

        capture = new CommandBuffer { name = "GraphicsExpanded shadow map" };
        capture.SetGlobalTexture("_GfxShadowMap", new RenderTargetIdentifier(BuiltinRenderTextureType.CurrentActive));

        march = new CommandBuffer { name = "GraphicsExpanded sunbeams" };
        // The composite only touches the picture on frames this ran, so a light that skips it can't leave stale or
        // empty data over the scene
        march.SetGlobalFloat("_GfxMarched", 1f);
        march.SetRenderTarget(lowDepth);
        march.DrawProcedural(Matrix4x4.identity, material, 0, MeshTopology.Triangles, 3);
        march.SetRenderTarget(volume);
        march.DrawProcedural(Matrix4x4.identity, material, 1, MeshTopology.Triangles, 3);

        composite = new CommandBuffer { name = "GraphicsExpanded sunbeams composite" };
        if (quality != GfxVolumetricQuality.Low)
        {
            composite.SetRenderTarget(blurred);
            composite.DrawProcedural(Matrix4x4.identity, material, 2, MeshTopology.Triangles, 3);
            composite.SetRenderTarget(volume);
            composite.DrawProcedural(Matrix4x4.identity, material, 3, MeshTopology.Triangles, 3);
        }
        composite.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
        composite.DrawProcedural(Matrix4x4.identity, material, 4, MeshTopology.Triangles, 3);
        composite.SetGlobalFloat("_GfxMarched", 0f);
    }

    private static RenderTexture Target(RenderTextureFormat format, FilterMode filter, string name)
    {
        RenderTexture texture = new RenderTexture(lowWidth, lowHeight, 0, format, RenderTextureReadWrite.Linear)
        {
            name = "GraphicsExpanded " + name,
            filterMode = filter,
            wrapMode = TextureWrapMode.Clamp,
            hideFlags = HideFlags.HideAndDontSave,
        };
        texture.Create();
        // Start as "no effect": nothing added, everything let through
        RenderTexture active = RenderTexture.active;
        RenderTexture.active = texture;
        GL.Clear(false, true, new Color(0f, 0f, 0f, 1f));
        RenderTexture.active = active;
        return texture;
    }

    private static void Release(ref RenderTexture texture)
    {
        if (texture != null)
        {
            texture.Release();
            Object.Destroy(texture);
            texture = null;
        }
    }

    private static void Unhook()
    {
        UnhookLight();
        if (cameraHooked)
        {
            if (camera != null)
                camera.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, composite);
            Camera.onPreCull -= OnPreCull;
            Camera.onPreRender -= OnPreRender;
            Camera.onPostRender -= OnPostRender;
            cameraHooked = false;
        }
    }

    private static void UnhookLight()
    {
        if (!lightHooked)
            return;
        if (light != null)
        {
            light.RemoveCommandBuffer(LightEvent.AfterShadowMap, capture);
            light.RemoveCommandBuffer(LightEvent.AfterScreenspaceMask, march);
        }
        lightHooked = false;
    }

    /// <summary>
    /// The light passes go on only while the player camera renders, so other cameras that render the sun's shadows
    /// (reflections, previews) don't march too.
    /// </summary>
    private static void OnPreCull(Camera rendering)
    {
        if (rendering != camera || light == null || lightHooked)
            return;
        light.AddCommandBuffer(LightEvent.AfterShadowMap, capture);
        light.AddCommandBuffer(LightEvent.AfterScreenspaceMask, march);
        lightHooked = true;
    }

    /// <summary>The camera's matrices this frame, after anti-aliasing has jittered them, to rebuild positions from depth.</summary>
    private static void OnPreRender(Camera rendering)
    {
        if (rendering != camera)
            return;
        material.SetMatrix("_GfxInvProjection", rendering.projectionMatrix.inverse);
        material.SetMatrix("_GfxCameraToWorld", rendering.cameraToWorldMatrix);
        material.SetVector("_GfxLowSize", new Vector4(lowWidth, lowHeight, 1f / lowWidth, 1f / lowHeight));
        material.SetVector("_GfxFullSize", new Vector4(rendering.pixelWidth, rendering.pixelHeight, 1f / rendering.pixelWidth, 1f / rendering.pixelHeight));
    }

    private static void OnPostRender(Camera rendering)
    {
        if (rendering == camera)
            UnhookLight();
    }

    // ---- The air ----

    private static void SetMedium(EntityPlayerLocal player, GfxVolumetricQuality quality)
    {
        World world = GameManager.Instance.World;
        if (Time.unscaledTime >= nextGroundTime)
        {
            groundHeight = AverageGround(world, player);
            nextGroundTime = Time.unscaledTime + 5f;
        }

        WeatherManager weather = WeatherManager.Instance;
        float rain = weather != null ? GfxMood.Fraction(weather.GetCurrentRainfallPercent()) : 0f;
        float snowfall = weather != null ? GfxMood.Fraction(weather.GetCurrentSnowfallPercent()) : 0f;
        float bloodMoon = Mathf.Clamp01(SkyManager.BloodMoonVisiblePercent());
        float mist = Mist((world.worldTime % 24000UL) / 1000f, SkyManager.GetDawnTime()) * GfxSettings.MorningMist;
        float thicker = Mathf.Min(1f + 5f * mist + 2f * rain + snowfall + 2f * bloodMoon, 8f);
        float fog = ClearFog * GfxSettings.HeightFog * thicker * GfxSettings.Effective.FogDensity;

        Vector3 origin = Origin.position;
        material.SetVector("_GfxMedium", new Vector4(fog, FogFalloff, groundHeight + FogAboveGround - origin.y, ClearAir));
        material.SetVector("_GfxDust", new Vector4(IndoorDust * GfxSettings.IndoorDust * (1f - GfxMood.Outdoors), DustRange, 0f, 0f));
        Color glow = light.color.linear * light.intensity * GfxSettings.Sunbeams;
        material.SetVector("_GfxLightColor", new Vector4(glow.r, glow.g, glow.b, 0f));
        material.SetVector("_GfxLightDir", -light.transform.forward);
        Color ambient = RenderSettings.fogColor.linear;
        material.SetVector("_GfxAmbient", new Vector4(ambient.r, ambient.g, ambient.b, 0f));
        int steps = quality == GfxVolumetricQuality.High ? 40 : quality == GfxVolumetricQuality.Medium ? 24 : 12;
        float reach = Mathf.Clamp(QualitySettings.shadowDistance, 60f, 300f);
        material.SetVector("_GfxMarch", new Vector4(steps, reach, PhaseG, frame++ % 64));
        material.SetFloat("_GfxSplitSpheres", QualitySettings.shadowProjection == ShadowProjection.StableFit ? 1f : 0f);
    }

    /// <summary>Morning mist: rises over the hour before dawn, holds for 90 minutes after it, then burns off over an hour.</summary>
    private static float Mist(float hours, float dawn)
    {
        float since = hours - dawn;
        if (since >= -1f && since < 0f)
            return Mathf.SmoothStep(0f, 1f, since + 1f);
        if (since >= 0f && since < 1.5f)
            return 1f;
        if (since >= 1.5f && since < 2.5f)
            return Mathf.SmoothStep(1f, 0f, since - 1.5f);
        return 0f;
    }

    /// <summary>The ground's average height over a 160 m square around the player, from the terrain heights.</summary>
    private static float AverageGround(World world, EntityPlayerLocal player)
    {
        Vector3i center = World.worldToBlockPos(player.position);
        float sum = 0f;
        int count = 0;
        for (int dz = -80; dz <= 80; dz += 20)
        {
            for (int dx = -80; dx <= 80; dx += 20)
            {
                int height = world.GetTerrainHeight(center.x + dx, center.z + dz);
                if (height > 0)
                {
                    sum += height;
                    count++;
                }
            }
        }
        return count > 0 ? sum / count : player.position.y - 2f;
    }

    public static string Status()
    {
        if (!Loaded)
            return "Sunbeams and height fog are off: the shader didn't load (see the log).";
        return string.Format("Sunbeams and height fog: {0}; ground {1:0} m, fog base {2:0} m; middle of the screen: {3}.",
            state, groundHeight, groundHeight + FogAboveGround, Probe());
    }

    /// <summary>
    /// What the effect holds in the middle of the screen, read back from the graphics card: the light it adds, how much
    /// it lets through, and the depth it marched to. (0, 0, 0) and 1 means the march hasn't written anything.
    /// </summary>
    private static string Probe()
    {
        if (volume == null || lowDepth == null)
            return "nothing yet";
        Color light = ReadMiddle(volume, TextureFormat.RGBAHalf);
        Color depth = ReadMiddle(lowDepth, TextureFormat.RFloat);
        return string.Format("light ({0:0.000}, {1:0.000}, {2:0.000}), lets through {3:0%}, depth {4:0.0} m",
            light.r, light.g, light.b, light.a, depth.r);
    }

    private static Color ReadMiddle(RenderTexture texture, TextureFormat format)
    {
        Texture2D pixel = new Texture2D(1, 1, format, false, true);
        RenderTexture active = RenderTexture.active;
        RenderTexture.active = texture;
        pixel.ReadPixels(new Rect(texture.width / 2, texture.height / 2, 1, 1), 0, 0, false);
        RenderTexture.active = active;
        Color color = pixel.GetPixel(0, 0);
        Object.Destroy(pixel);
        return color;
    }
}
