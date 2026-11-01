using System;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Rain wetness, puddles and snow cover. How wet and snowy the world is builds up and wears off over time from the
/// weather every client already has, so in multiplayer each player works it out locally and nothing is sent.
///
/// - The sky map: for every block column around the player, the top of the highest block that stops rain (grass,
///   flowers and water don't), read from the world's blocks a few chunks a frame. A point lower than that is under
///   cover and stays dry. It comes from the block data rather than from rendering, so chunks the game has culled
///   (out of sight from inside a house, say) still count.
/// - The surface pass: a command buffer on the player camera, after the game has drawn every surface and before
///   reflections and lighting, redraws the surfaces wet, puddled or snowy (WeatherSurface.shader, from
///   Resources/graphicsexpanded.bundle, built by src/build-shaders.bat). The game's and Torch's lighting then light
///   them like anything else. It's only attached while something is wet or snowy.
/// </summary>
public static class GfxWeather
{
    /// <summary>The sky map covers this many chunks each way from the player's chunk: 13 x 13 chunks, 208 m across.</summary>
    private const int SkyChunkRange = 6;
    private const int SkyChunks = SkyChunkRange * 2 + 1;
    private const int SkySize = SkyChunks * 16;
    private const int ChunksPerFrame = 24;
    private const float NoCover = -100000f;

    /// <summary>How far down a column to look past plants and the like for something that stops rain.</summary>
    private const int ScanDepth = 12;

    private const float WetSeconds = 60f;       // to soak through in heavy rain (longer in light rain)
    private const float DrySeconds = 300f;
    private const float PuddleSeconds = 90f;    // to fill, once things are half wet
    private const float PuddleDrySeconds = 420f;
    private const float SnowSeconds = 180f;     // to cover in heavy snow
    private const float MeltSeconds = 600f;

    private static Shader surfaceShader;
    private static Material surfaceMaterial;

    private static float wet, puddles, snow, ripples;
    private static bool started;

    private static Camera camera;
    private static CommandBuffer commands;
    private static bool attached;

    private static Texture2D skyMap;
    private static float[] skyHeights;
    private static Vector2i fillCorner;         // world block x, z of texel (0, 0) for the pass being filled
    private static int fillChunk = -1;          // next chunk of the pass to fill, -1 between passes
    private static Vector2i shownCorner;
    private static bool skyValid;
    private static float nextSkyTime;
    private static sbyte[] stopsRain;           // per block type: 1 stops rain, 0 doesn't, -1 not looked at yet

    /// <summary>Show the sky map on screen instead (gfxe weather debug): cyan is open to the sky, magenta is covered.</summary>
    public static bool Debug;

    public static bool Loaded => surfaceShader != null;

    public static void Init(string modPath)
    {
        string path = Path.Combine(modPath, "Resources", "graphicsexpanded.bundle");
        try
        {
            AssetBundle bundle = AssetBundle.LoadFromFile(path);
            if (bundle == null)
            {
                Log.Warning("[GraphicsExpanded] Couldn't load " + path + "; rain wetness and snow cover are off");
                return;
            }
            surfaceShader = bundle.LoadAsset<Shader>("WeatherSurface");
            if (surfaceShader == null || !surfaceShader.isSupported)
            {
                Log.Warning("[GraphicsExpanded] The weather shader didn't load or isn't supported on this graphics card; rain wetness and snow cover are off");
                surfaceShader = null;
                return;
            }
            surfaceMaterial = new Material(surfaceShader) { hideFlags = HideFlags.HideAndDontSave };
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't load the weather shader: " + e.Message);
            surfaceShader = null;
        }
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera, float deltaTime)
    {
        if (!Loaded)
            return;
        if (player == null || playerCamera == null)
        {
            Detach();
            started = false;
            skyValid = false;
            fillChunk = -1;
            return;
        }

        Accumulate(deltaTime);

        bool active = GfxSettings.LookActive;
        float wetness = active ? wet * GfxSettings.RainWetness : 0f;
        float puddleCover = active ? puddles * GfxSettings.PuddleCoverage : 0f;
        float snowCover = active ? snow * GfxSettings.SnowCover : 0f;
        bool show = Debug || wetness > 0.001f || puddleCover > 0.001f || snowCover > 0.001f;
        if (!show)
        {
            Detach();
            return;
        }

        UpdateSkyMap(player);
        if (!skyValid)
            return;     // nothing drawn until the first map is in, or rooms would be wet for a moment
        Attach(playerCamera);

        // The map is in world coordinates; the shader works where things are drawn, which the floating origin shifts
        Vector3 origin = Origin.position;
        surfaceMaterial.SetVector("_GfxSkyArea", new Vector4(shownCorner.x - origin.x, shownCorner.y - origin.z, 1f / SkySize, -origin.y));
        surfaceMaterial.SetVector("_GfxWeather", new Vector4(wetness, PuddleFill(puddleCover), snowCover, ripples * Mathf.Clamp01(puddleCover * 4f)));
        surfaceMaterial.SetFloat("_GfxDebug", Debug ? 1f : 0f);
    }

    /// <summary>How wet, puddled and snowy things are, 0 to 1. Soaks in while it rains or snows and wears off after.</summary>
    private static void Accumulate(float deltaTime)
    {
        WeatherManager weather = WeatherManager.Instance;
        float rain = weather != null ? GfxMood.Fraction(weather.GetCurrentRainfallPercent()) : 0f;
        float snowfall = weather != null ? GfxMood.Fraction(weather.GetCurrentSnowfallPercent()) : 0f;

        if (!started)
        {
            // Joining in the middle of a storm shouldn't start with dry streets
            started = true;
            wet = puddles = rain > 0.3f ? 1f : 0f;
            snow = snowfall > 0.3f ? 1f : 0f;
            ripples = rain;
            return;
        }

        bool raining = rain > 0.05f;
        wet = Mathf.Clamp01(raining ? wet + deltaTime * rain / WetSeconds : wet - deltaTime / DrySeconds);
        if (raining && wet > 0.5f)
            puddles = Mathf.Clamp01(puddles + deltaTime * rain / PuddleSeconds);
        else if (!raining)
            puddles = Mathf.Clamp01(puddles - deltaTime / PuddleDrySeconds);
        snow = Mathf.Clamp01(snowfall > 0.05f ? snow + deltaTime * snowfall / SnowSeconds : snow - deltaTime / MeltSeconds);
        ripples = Mathf.MoveTowards(ripples, rain, deltaTime / 3f);
    }

    /// <summary>
    /// The shader puts puddles where its noise pattern is above 1 - fill. The pattern is roughly bell shaped around
    /// 0.5 (spread about 0.12), so turn the share of flat ground to cover into that threshold.
    /// </summary>
    private static float PuddleFill(float cover)
    {
        if (cover <= 0.001f)
            return 0f;
        float p = Mathf.Clamp(1f - cover, 0.001f, 0.999f);
        float probit = 4.91f * (Mathf.Pow(p, 0.14f) - Mathf.Pow(1f - p, 0.14f));   // inverse of the normal curve, closely
        return Mathf.Clamp01(1f - (0.5f + 0.123f * probit));
    }

    // ---- The surface pass ----

    private static void Attach(Camera playerCamera)
    {
        if (attached && camera == playerCamera)
            return;
        Detach();
        if (commands == null)
            commands = BuildCommands();
        camera = playerCamera;
        camera.AddCommandBuffer(CameraEvent.BeforeReflections, commands);
        Camera.onPreRender += OnPreRender;
        attached = true;
    }

    private static void Detach()
    {
        if (!attached)
            return;
        if (camera != null)
            camera.RemoveCommandBuffer(CameraEvent.BeforeReflections, commands);
        Camera.onPreRender -= OnPreRender;
        camera = null;
        attached = false;
    }

    private static CommandBuffer BuildCommands()
    {
        int g0 = Shader.PropertyToID("_GfxGBuffer0");
        int g1 = Shader.PropertyToID("_GfxGBuffer1");
        int g2 = Shader.PropertyToID("_GfxGBuffer2");
        CommandBuffer cb = new CommandBuffer { name = "GraphicsExpanded weather" };
        // The surface buffers can't be read while drawn to, so copy them, then draw over the real ones
        cb.GetTemporaryRT(g0, -1, -1, 0, FilterMode.Point, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        cb.GetTemporaryRT(g1, -1, -1, 0, FilterMode.Point, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        cb.GetTemporaryRT(g2, -1, -1, 0, FilterMode.Point, RenderTextureFormat.ARGB2101010, RenderTextureReadWrite.Linear);
        cb.Blit(BuiltinRenderTextureType.GBuffer0, g0);
        cb.Blit(BuiltinRenderTextureType.GBuffer1, g1);
        cb.Blit(BuiltinRenderTextureType.GBuffer2, g2);
        cb.SetRenderTarget(new RenderTargetIdentifier[]
        {
            BuiltinRenderTextureType.GBuffer0, BuiltinRenderTextureType.GBuffer1, BuiltinRenderTextureType.GBuffer2,
        }, BuiltinRenderTextureType.CameraTarget);
        cb.DrawProcedural(Matrix4x4.identity, surfaceMaterial, 0, MeshTopology.Triangles, 3);
        cb.ReleaseTemporaryRT(g0);
        cb.ReleaseTemporaryRT(g1);
        cb.ReleaseTemporaryRT(g2);
        return cb;
    }

    /// <summary>The camera's matrices this frame, after anti-aliasing has jittered them, to rebuild positions from depth.</summary>
    private static void OnPreRender(Camera rendering)
    {
        if (rendering != camera || surfaceMaterial == null)
            return;
        surfaceMaterial.SetMatrix("_GfxInvProjection", rendering.projectionMatrix.inverse);
        surfaceMaterial.SetMatrix("_GfxCameraToWorld", rendering.cameraToWorldMatrix);
    }

    // ---- The sky map ----

    /// <summary>
    /// Starts a pass every two seconds (blocks get built and broken), or at once when the player is two chunks from
    /// the middle of the map, and fills it a few chunks a frame. The finished pass replaces the map in one go.
    /// </summary>
    private static void UpdateSkyMap(EntityPlayerLocal player)
    {
        World world = GameManager.Instance.World;
        Vector3i block = World.worldToBlockPos(player.position);
        Vector2i playerChunk = new Vector2i(World.toChunkXZ(block.x), World.toChunkXZ(block.z));
        if (fillChunk < 0)
        {
            Vector2i center = new Vector2i(shownCorner.x / 16 + SkyChunkRange, shownCorner.y / 16 + SkyChunkRange);
            bool far = Math.Abs(playerChunk.x - center.x) > 1 || Math.Abs(playerChunk.y - center.y) > 1;
            if (skyValid && !far && Time.unscaledTime < nextSkyTime)
                return;
            fillCorner = new Vector2i((playerChunk.x - SkyChunkRange) * 16, (playerChunk.y - SkyChunkRange) * 16);
            fillChunk = 0;
            if (skyHeights == null)
                skyHeights = new float[SkySize * SkySize];
        }

        int end = Math.Min(fillChunk + ChunksPerFrame, SkyChunks * SkyChunks);
        for (; fillChunk < end; fillChunk++)
            FillChunk(world, fillChunk % SkyChunks, fillChunk / SkyChunks);
        if (fillChunk < SkyChunks * SkyChunks)
            return;

        if (skyMap == null)
        {
            skyMap = new Texture2D(SkySize, SkySize, TextureFormat.RFloat, false, true)
            {
                name = "GraphicsExpanded sky map",
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave,
            };
            surfaceMaterial.SetTexture("_GfxSkyHeight", skyMap);
        }
        skyMap.SetPixelData(skyHeights, 0);
        skyMap.Apply(false);
        shownCorner = fillCorner;
        skyValid = true;
        fillChunk = -1;
        nextSkyTime = Time.unscaledTime + 2f;
    }

    /// <summary>One chunk of the map: for each column, the top of the highest block that stops rain.</summary>
    private static void FillChunk(World world, int mapChunkX, int mapChunkZ)
    {
        Chunk chunk = world.GetChunkSync(fillCorner.x / 16 + mapChunkX, fillCorner.y / 16 + mapChunkZ) as Chunk;
        for (int z = 0; z < 16; z++)
        {
            int row = (mapChunkZ * 16 + z) * SkySize + mapChunkX * 16;
            for (int x = 0; x < 16; x++)
                skyHeights[row + x] = chunk != null ? ColumnCover(chunk, x, z) : NoCover;
        }
    }

    private static float ColumnCover(Chunk chunk, int x, int z)
    {
        int top = chunk.GetHeight(x, z);
        for (int y = top; y >= 0 && y > top - ScanDepth; y--)
        {
            BlockValue value = chunk.GetBlockNoDamage(x, y, z);
            if (!value.isair && StopsRain(value.type))
                return y + 1;
        }
        return NoCover;
    }

    /// <summary>Solid blocks stop rain; plants, ground cover like grass and flowers, and liquids don't.</summary>
    private static bool StopsRain(int type)
    {
        Block[] blocks = Block.list;
        if (stopsRain == null || stopsRain.Length != blocks.Length)
        {
            stopsRain = new sbyte[blocks.Length];
            for (int i = 0; i < stopsRain.Length; i++)
                stopsRain[i] = -1;
        }
        if (type < 0 || type >= blocks.Length)
            return false;
        if (stopsRain[type] < 0)
        {
            Block block = blocks[type];
            MaterialBlock material = block?.blockMaterial;
            bool stops = block != null && block.IsCollideMovement && !block.bIsPlant && !block.IsTerrainDecoration
                && (material == null || (!material.IsPlant && !material.IsLiquid));
            stopsRain[type] = (sbyte)(stops ? 1 : 0);
        }
        return stopsRain[type] == 1;
    }

    public static string Status()
    {
        if (!Loaded)
            return "Rain wetness and snow cover are off: the shader didn't load (see the log).";
        return string.Format("Weather surfaces: wet {0:0%}, puddles {1:0%}, snow {2:0%}, ripples {3:0%}; {4}; sky map {5} from block ({6}, {7}).",
            wet, puddles, snow, ripples, attached ? "drawing" : "idle", skyValid ? "ready" : "not built yet",
            shownCorner.x, shownCorner.y);
    }

    /// <summary>gfxe weather wet/snow: set how wet or snowy things are, to see it without waiting for the weather.</summary>
    public static void Force(float? wetness, float? snowCover)
    {
        if (wetness.HasValue)
            wet = puddles = Mathf.Clamp01(wetness.Value);
        if (snowCover.HasValue)
            snow = Mathf.Clamp01(snowCover.Value);
        started = true;
    }
}
