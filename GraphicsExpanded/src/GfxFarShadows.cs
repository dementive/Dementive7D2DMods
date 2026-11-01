using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

/// <summary>
/// Far shadows (FarShadows.shader). Past the sun's shadow distance the game has no shadows at all, so far hills look
/// flat, and at sunrise and sunset whole valleys stay lit that should lie in a ridge's shadow. This works out the
/// shadow of the land itself out there and puts it in the light's own screen-space shadow mask, so only the sun's (or
/// moon's) direct light dims and everything out there is shaded the same: ground, distant forests, far-off buildings.
///
/// The land comes from the game's far terrain tiles (Terrain.activeTerrains), each copied on the graphics card into one
/// world height map, made again when the tiles or the world's origin change and every so often. A command buffer on the
/// light after its screen-space mask (the slot the game's own contact shadows use) walks from each far pixel towards
/// the light over the height map, keeping the darker of that and the mask. It goes on only while the player camera
/// renders, and is added before the sunbeams' own, so the mask is still the active target. It fades in over the last
/// fifth of the shadow distance, where the shadow map's own shadows fade out. Nothing is sent in multiplayer.
/// </summary>
public static class GfxFarShadows
{
    private const int MapSize = 2048;
    private const float MaxHeight = 32766f / 65535f;    // Unity keeps terrain heights in 0 to this in heightmapTexture
    private const float Penumbra = 0.015f;               // how soft the edges are, per meter along the path to the light
    private const float RebuildEvery = 30f;

    private static Shader shader;
    private static Material material;
    private static RenderTexture heights;
    private static CommandBuffer shade;

    private static Camera camera;
    private static Light light;
    private static Light hookedLight;
    private static bool active;

    private static int tilesSignature;
    private static int tileCount;
    private static Vector3 builtOrigin;
    private static float nextCheck, nextRebuild, builtTime;
    private static Rect area;
    private static float lowest, highest;
    private static string state = "not started";

    /// <summary>
    /// gfxe farshadows debug: 1 lays the far shadow over the picture in red, to see where it falls; 2 shows in blue how
    /// far the height map is from the ground actually drawn, to check it lines up with the world.
    /// </summary>
    public static int Debug;
    private static CommandBuffer debugOverlay;
    private static Camera debugCamera;

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("FarShadows") : null;
        if (shader != null && !shader.isSupported)
        {
            Log.Warning("[GraphicsExpanded] The far shadow shader isn't supported on this graphics card; far shadows are off");
            shader = null;
        }
        if (!Loaded)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        shade = new CommandBuffer { name = "GraphicsExpanded far shadows" };
        shade.DrawProcedural(Matrix4x4.identity, material, 1, MeshTopology.Triangles, 3);
        debugOverlay = new CommandBuffer { name = "GraphicsExpanded far shadows debug" };
        debugOverlay.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
        debugOverlay.DrawProcedural(Matrix4x4.identity, material, 2, MeshTopology.Triangles, 3);
        // Subscribed once, now, so the pass is added to the light before the sunbeams' (which subscribe later) and
        // runs while the mask is still the active target
        Camera.onPreCull += OnPreCull;
        Camera.onPreRender += OnPreRender;
        Camera.onPostRender += OnPostRender;
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        active = false;
        UpdateDebug(null);
        bool wanted = GfxSettings.ShadowsActive && GfxSettings.FarShadows == GfxFarShadowMode.On;
        if (!wanted || player == null || playerCamera == null || QualitySettings.shadows == ShadowQuality.Disable)
        {
            state = !wanted ? "off" : player == null ? "no world" : "the game's shadows are off";
            return;
        }
        camera = playerCamera;
        light = GfxAtmosphere.ShadowLight();
        if (light == null)
        {
            state = "no sun or moon casting shadows";
            return;
        }
        Refresh();
        if (tileCount == 0)
        {
            state = "no far terrain";
            return;
        }

        float distance = QualitySettings.shadowDistance;
        material.SetVector("_GfxFarShadow", new Vector4(distance * 0.8f, 1f / Mathf.Max(distance * 0.2f, 1f), highest + 1f, Penumbra));
        material.SetVector("_GfxLightDir", -light.transform.forward);
        active = true;
        UpdateDebug(playerCamera);
        Vector3 toLight = -light.transform.forward;
        state = string.Format("from the {0} ({1:0} degrees up, towards {2:0} degrees from north), past {3:0} m", light == SkyManager.sunLight ? "sun" : "moon",
            Mathf.Asin(Mathf.Clamp(toLight.y, -1f, 1f)) * Mathf.Rad2Deg, (Mathf.Atan2(toLight.x, toLight.z) * Mathf.Rad2Deg + 360f) % 360f, distance * 0.8f);
    }

    private static void UpdateDebug(Camera playerCamera)
    {
        Camera wanted = Debug > 0 ? playerCamera : null;
        material.SetFloat("_GfxDebugMode", Debug);
        if (wanted == debugCamera)
            return;
        if (debugCamera != null)
            debugCamera.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, debugOverlay);
        if (wanted != null)
            wanted.AddCommandBuffer(CameraEvent.AfterForwardAlpha, debugOverlay);
        debugCamera = wanted;
    }

    // ---- The height map ----

    private static void Refresh()
    {
        if (Time.unscaledTime < nextCheck && heights != null)
            return;
        nextCheck = Time.unscaledTime + 1f;
        Terrain[] tiles = Terrain.activeTerrains;
        int signature = tiles.Length;
        foreach (Terrain tile in tiles)
        {
            if (tile != null)
                signature = signature * 31 + tile.GetInstanceID() * 17 + tile.GetPosition().GetHashCode();
        }
        if (heights != null && signature == tilesSignature && Origin.position == builtOrigin && Time.unscaledTime < nextRebuild)
            return;
        tilesSignature = signature;
        builtOrigin = Origin.position;
        nextRebuild = Time.unscaledTime + RebuildEvery;
        Build(tiles);
    }

    private static void Build(Terrain[] tiles)
    {
        tileCount = 0;
        float minX = float.MaxValue, minZ = float.MaxValue, maxX = float.MinValue, maxZ = float.MinValue;
        lowest = float.MaxValue;
        highest = float.MinValue;
        foreach (Terrain tile in tiles)
        {
            if (tile == null || tile.terrainData == null)
                continue;
            Vector3 corner = tile.GetPosition(), size = tile.terrainData.size;
            minX = Mathf.Min(minX, corner.x);
            minZ = Mathf.Min(minZ, corner.z);
            maxX = Mathf.Max(maxX, corner.x + size.x);
            maxZ = Mathf.Max(maxZ, corner.z + size.z);
            lowest = Mathf.Min(lowest, corner.y);
            highest = Mathf.Max(highest, corner.y + size.y);
        }
        if (minX >= maxX || minZ >= maxZ)
            return;
        area = Rect.MinMaxRect(minX, minZ, maxX, maxZ);

        if (heights == null)
        {
            heights = new RenderTexture(MapSize, MapSize, 0, RenderTextureFormat.RHalf, RenderTextureReadWrite.Linear)
            {
                name = "GraphicsExpanded far shadow heights",
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave,
            };
            heights.Create();
        }

        CommandBuffer copy = new CommandBuffer { name = "GraphicsExpanded far shadow heights" };
        copy.SetRenderTarget(heights);
        // Off the map: far below everything, so it never shades
        copy.ClearRenderTarget(false, true, new Color(-10000f, 0f, 0f, 0f));
        foreach (Terrain tile in tiles)
        {
            if (tile == null || tile.terrainData == null)
                continue;
            TerrainData data = tile.terrainData;
            Texture heightmap = data.heightmapTexture;
            if (heightmap == null)
                continue;
            Vector3 corner = tile.GetPosition(), size = data.size;
            MaterialPropertyBlock block = new MaterialPropertyBlock();
            block.SetTexture("_GfxTileHeight", heightmap);
            block.SetVector("_GfxTileRect", new Vector4((corner.x - area.xMin) / area.width, (corner.z - area.yMin) / area.height, size.x / area.width, size.z / area.height));
            block.SetVector("_GfxTileParams", new Vector4(corner.y, size.y / MaxHeight, data.heightmapResolution, 0f));
            copy.DrawProcedural(Matrix4x4.identity, material, 0, MeshTopology.Triangles, 6, 1, block);
            tileCount++;
        }
        Graphics.ExecuteCommandBuffer(copy);
        copy.Release();
        builtTime = Time.unscaledTime;

        material.SetTexture("_GfxHeight", heights);
        material.SetVector("_GfxHeightRect", new Vector4(area.xMin, area.yMin, 1f / area.width, 1f / area.height));
    }

    // ---- On the light, while the player camera renders ----

    private static void OnPreCull(Camera rendering)
    {
        if (rendering != camera || !active || hookedLight != null || light == null)
            return;
        light.AddCommandBuffer(LightEvent.AfterScreenspaceMask, shade);
        hookedLight = light;
    }

    private static void OnPreRender(Camera rendering)
    {
        if (rendering != camera || !active)
            return;
        material.SetMatrix("_GfxInvProjection", rendering.projectionMatrix.inverse);
        material.SetMatrix("_GfxCameraToWorld", rendering.cameraToWorldMatrix);
        material.SetVector("_GfxFullSize", new Vector4(rendering.pixelWidth, rendering.pixelHeight, 1f / rendering.pixelWidth, 1f / rendering.pixelHeight));
    }

    private static void OnPostRender(Camera rendering)
    {
        if (rendering != camera || hookedLight == null)
            return;
        hookedLight.RemoveCommandBuffer(LightEvent.AfterScreenspaceMask, shade);
        hookedLight = null;
    }

    /// <summary>gfxe farshadows save: writes the height map as a grey picture, low ground dark and high ground light.</summary>
    public static string SaveHeights()
    {
        if (heights == null)
            return "No height map yet (load a world with far shadows on).";
        RenderTexture copy = RenderTexture.GetTemporary(MapSize, MapSize, 0, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
        Graphics.Blit(heights, copy);
        Texture2D read = new Texture2D(MapSize, MapSize, TextureFormat.RGBAFloat, false, true);
        RenderTexture previous = RenderTexture.active;
        RenderTexture.active = copy;
        read.ReadPixels(new Rect(0, 0, MapSize, MapSize), 0, 0, false);
        read.Apply(false);
        RenderTexture.active = previous;
        RenderTexture.ReleaseTemporary(copy);

        Color[] pixels = read.GetPixels();
        float min = float.MaxValue, max = float.MinValue;
        foreach (Color p in pixels)
        {
            if (p.r < -9000f)
                continue;
            min = Mathf.Min(min, p.r);
            max = Mathf.Max(max, p.r);
        }
        Color32[] grey = new Color32[pixels.Length];
        for (int i = 0; i < pixels.Length; i++)
        {
            byte v = pixels[i].r < -9000f ? (byte)0 : (byte)Mathf.Clamp(Mathf.RoundToInt((pixels[i].r - min) / Mathf.Max(max - min, 1f) * 254f + 1f), 1, 255);
            grey[i] = new Color32(v, v, v, 255);
        }
        Object.Destroy(read);
        Texture2D picture = new Texture2D(MapSize, MapSize, TextureFormat.RGBA32, false);
        picture.SetPixels32(grey);
        string path = Path.Combine(GameIO.GetUserGameDataDir(), "GraphicsExpanded", "FarShadowHeights.png");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllBytes(path, picture.EncodeToPNG());
        Object.Destroy(picture);
        return string.Format("Saved the height map to {0} ({1:0} to {2:0} m, black is off the map).", path, min, max);
    }

    public static string Status()
    {
        if (!Loaded)
            return "Far shadows are off: the shader didn't load (see the log).";
        if (heights == null || tileCount == 0)
            return "Far shadows: " + state + ".";
        return string.Format("Far shadows: {0}; height map {1:0.0} by {2:0.0} km from {3} terrain tiles, ground up to {4:0} m; made {5:0} s ago.",
            state, area.width / 1000f, area.height / 1000f, tileCount, highest, Time.unscaledTime - builtTime);
    }
}
