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
/// valleys and over water, broken into banks that drift with the wind. It comes with the time and the weather: night
/// and morning mist, rain, snow, overcast skies and the Blood Moon. A clear afternoon has next to none. All of it
/// follows what every client already has (the world time drives the drift), so in multiplayer each player works it
/// out locally, sees the same banks in the same places, and nothing is sent.
/// </summary>
public static class GfxAtmosphere
{
    private const float ClearFog = 0.002f;          // extinction per meter of the fog layer on a clear day
    private const float FogFalloff = 0.077f;        // per meter above the base: half as thick every 9 m
    private const float FogAboveGround = 15f;
    private const float ClearAir = 0.0003f;          // enough for sunbeams on a clear day, not enough to grey the view
    private const float ClearDayFog = 0.05f;         // the fog's share left on a clear afternoon
    private const float BankRepeat = 480f;           // the fog noise repeats every 480 m across, so banks are about 60 m
    private const float BankRepeatUp = 120f;         // and every 120 m up
    private static readonly Vector2 DriftPerTick = new Vector2(0.35f, 0.15f);   // a world tick is about 0.15 s at the default day length
    private const double DriftWrap = BankRepeat * 1000.0;
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
    private static Texture3D fogNoise;
    private static Vector2 drift;
    private static bool driftSet;
    private static float fogAmount = -1f;    // eases towards the weather's; below 0 until the first frame sets it
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
        {
            material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
            fogNoise = FogNoise();
            material.SetTexture("_GfxFogNoise", fogNoise);
        }
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
    internal static Light ShadowLight()
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
        material.SetFloat("_GfxFar", rendering.farClipPlane);
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
        float overcast = weather != null ? GfxMood.Fraction(weather.GetCurrentCloudThicknessPercent()) : 0f;
        float bloodMoon = Mathf.Clamp01(SkyManager.BloodMoonVisiblePercent());
        float hours = (world.worldTime % 24000UL) / 1000f;
        float mist = Mist(hours, SkyManager.GetDawnTime(), SkyManager.GetDuskTime()) * GfxSettings.MorningMist;
        // Next to nothing on a clear afternoon; the time of day and the weather bring it in
        float target = Mathf.Min(ClearDayFog + 6f * mist + 3f * rain + 2f * snowfall + overcast * overcast + 3f * bloodMoon, 8f);
        fogAmount = fogAmount < 0f ? target : Mathf.MoveTowards(fogAmount, target, Time.deltaTime * 0.1f);
        float fog = ClearFog * GfxSettings.HeightFog * fogAmount * GfxSettings.Effective.FogDensity;

        Vector3 origin = Origin.position;
        material.SetVector("_GfxMedium", new Vector4(fog, FogFalloff, groundHeight + FogAboveGround - origin.y, ClearAir));
        // Mist lies in banks with clear gaps between; steady rain fills them in
        Vector2 carried = Drift(world);
        material.SetVector("_GfxFogBanks", new Vector4(1f / BankRepeat, 1f / BankRepeatUp, Mathf.Lerp(0.9f, 0.4f, Mathf.Max(rain, snowfall)), 0f));
        material.SetVector("_GfxFogOffset", new Vector4(origin.x + carried.x, origin.y, origin.z + carried.y, 0f));
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

    /// <summary>
    /// Night and morning mist: from an hour after dusk it gathers in the low ground through the night, thickest at
    /// dawn, holds for 90 minutes after it, then burns off over an hour.
    /// </summary>
    private static float Mist(float hours, float dawn, float dusk)
    {
        float since = hours - dawn;
        if (since >= 0f && since < 1.5f)
            return 1f;
        if (since >= 1.5f && since < 2.5f)
            return Mathf.SmoothStep(1f, 0f, since - 1.5f);
        // Hours since an hour after dusk, through midnight to dawn
        float night = hours - (dusk + 1f);
        if (night < 0f)
            night += 24f;
        float nightLength = dawn + 24f - (dusk + 1f);
        if (night >= 0f && night < nightLength)
            return Mathf.SmoothStep(0f, 1f, night / nightLength);
        return 0f;
    }

    /// <summary>How far the wind has carried the fog banks: from the synced world time, eased between ticks.</summary>
    private static Vector2 Drift(World world)
    {
        double ticks = world.worldTime;
        Vector2 target = new Vector2((float)(ticks * DriftPerTick.x % DriftWrap), (float)(ticks * DriftPerTick.y % DriftWrap));
        if (!driftSet || (target - drift).sqrMagnitude > 500f * 500f)
            drift = target;     // first frame, a wrap, or a time skip
        else
            drift = Vector2.Lerp(drift, target, 0.05f);
        driftSet = true;
        return drift;
    }

    /// <summary>
    /// The fog's noise: soft value noise on an 8 then a 16 cell lattice, both repeating, so the banks tile seamlessly.
    /// Made once at start up, 32 cubed.
    /// </summary>
    private static Texture3D FogNoise()
    {
        const int size = 32;
        System.Random random = new System.Random(7);
        float[] coarse = Lattice(random, 8);
        float[] fine = Lattice(random, 16);
        byte[] data = new byte[size * size * size];
        for (int z = 0; z < size; z++)
        {
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float value = Smooth(coarse, 8, x, y, z, size) * 0.65f + Smooth(fine, 16, x, y, z, size) * 0.35f;
                    data[(z * size + y) * size + x] = (byte)Mathf.Clamp(Mathf.RoundToInt(value * 255f), 0, 255);
                }
            }
        }
        Texture3D texture = new Texture3D(size, size, size, TextureFormat.R8, false)
        {
            name = "GraphicsExpanded fog noise",
            wrapMode = TextureWrapMode.Repeat,
            filterMode = FilterMode.Bilinear,
            hideFlags = HideFlags.HideAndDontSave,
        };
        texture.SetPixelData(data, 0);
        texture.Apply(false, true);
        return texture;
    }

    private static float[] Lattice(System.Random random, int cells)
    {
        float[] values = new float[cells * cells * cells];
        for (int i = 0; i < values.Length; i++)
            values[i] = (float)random.NextDouble();
        return values;
    }

    /// <summary>The lattice's values blended smoothly at a texel, wrapping at the edges.</summary>
    private static float Smooth(float[] lattice, int cells, int x, int y, int z, int size)
    {
        float fx = (x + 0.5f) * cells / size, fy = (y + 0.5f) * cells / size, fz = (z + 0.5f) * cells / size;
        int x0 = Mathf.FloorToInt(fx), y0 = Mathf.FloorToInt(fy), z0 = Mathf.FloorToInt(fz);
        float tx = Fade(fx - x0), ty = Fade(fy - y0), tz = Fade(fz - z0);
        float At(int i, int j, int k) => lattice[((k % cells) * cells + (j % cells)) * cells + (i % cells)];
        float x00 = Mathf.Lerp(At(x0, y0, z0), At(x0 + 1, y0, z0), tx);
        float x10 = Mathf.Lerp(At(x0, y0 + 1, z0), At(x0 + 1, y0 + 1, z0), tx);
        float x01 = Mathf.Lerp(At(x0, y0, z0 + 1), At(x0 + 1, y0, z0 + 1), tx);
        float x11 = Mathf.Lerp(At(x0, y0 + 1, z0 + 1), At(x0 + 1, y0 + 1, z0 + 1), tx);
        return Mathf.Lerp(Mathf.Lerp(x00, x10, ty), Mathf.Lerp(x01, x11, ty), tz);
    }

    private static float Fade(float t)
    {
        return t * t * t * (t * (t * 6f - 15f) + 10f);
    }

    /// <summary>The ground's average height over a 160 m square around the player, from the terrain heights.</summary>
    public static float AverageGround(World world, EntityPlayerLocal player)
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
        return string.Format("Sunbeams and height fog: {0}; ground {1:0} m, fog base {2:0} m, fog {3:0%} of a misty morning's; middle of the screen: {4}.",
            state, groundHeight, groundHeight + FogAboveGround, fogAmount / 6f, Probe());
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
