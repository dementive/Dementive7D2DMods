using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

/// <summary>
/// Distant grass (DistantGrass.shader). The game grows grass only on the chunks it has loaded, about 100 to 190 m out
/// depending on the view distance, so past that the ground goes bare and grass pops in chunk by chunk as you walk.
/// This draws grass on the far terrain out to 300 or 500 m, so the ground stays covered and a chunk's own grass takes
/// over grass that's already there.
///
/// Two DrawMeshInstancedIndirects a frame each draw a whole grid of cells around the camera: a fine one (1.25 m) of
/// small tufts near, and a coarse one (2.5 m) of tufts twice the size far, covering the ground the same and handing
/// over across a band. The shader works out each cell's tuft on a fixed world grid and drops it where no grass belongs.
/// What it reads, all made locally:
/// - the field, around the camera at 2 m and made again when the camera has moved far enough: how much grass grows
///   (by biome, from the game's biome provider, with a color per biome), and none on buildings' footprints;
/// - the chunks the game has loaded (their own grass is there), updated twice a second;
/// - GfxFarShadows' world height map (the ground as the far terrain is drawn), and its slope;
/// - the world's splat maps (ChunkProviderGenerateWorldFromRaw.splats): roads, and water.
/// Everything is read from what every client already has, so in multiplayer nothing is sent.
/// </summary>
public static class GfxDistantGrass
{
    private const float NearCell = 1.25f, FarCell = 2.5f;     // the far grid's tufts are twice the size, so they cover the same
    private const float BandStart = 170f, BandEnd = 230f;    // where the near grid hands over to the far one
    private const float FadeLength = 60f;       // it thins out over this before the outer edge
    private const float TuftWidth = 1.5f, TuftHeight = 0.45f;
    private const float FieldSize = 1280f;      // meters of field around the camera: the 500 m edge, plus room to move
    private const int FieldTexels = 640;        // 2 m each
    private const int ChunkTexels = 80;         // a chunk (16 m) each
    private const int BiomeStep = 8;            // meters between biome lookups
    private const float RecenterAfter = 120f;

    private struct BiomeLook
    {
        public string Match;                    // matched against the biome's name, in order; "" for anything else
        public Color32 Color;                   // the grass's color as a whole, sRGB
        public float Density;                   // how much of the ground it covers
    }

    private static readonly BiomeLook[] Looks =
    {
        new BiomeLook { Match = "burnt", Color = new Color32(64, 56, 40, 255), Density = 0.55f },
        new BiomeLook { Match = "desert", Color = new Color32(140, 122, 80, 255), Density = 0.3f },
        new BiomeLook { Match = "snow", Color = new Color32(130, 134, 122, 255), Density = 0.12f },
        new BiomeLook { Match = "waste", Color = new Color32(96, 86, 60, 255), Density = 0.4f },
        new BiomeLook { Match = "forest", Color = new Color32(64, 84, 38, 255), Density = 0.95f },
        new BiomeLook { Match = "", Color = new Color32(72, 86, 44, 255), Density = 0.6f },
    };

    private static Shader shader;
    private static Material material;
    private static Mesh card;
    private static Texture2D blades, field, chunks;
    private static byte[] chunkPixels = new byte[ChunkTexels * ChunkTexels];
    private static float[] chunkTaken = new float[ChunkTexels * ChunkTexels];     // per chunk, how far the game's grass has taken over
    private static bool[] chunkBuilt = new bool[ChunkTexels * ChunkTexels];
    private static bool chunksFresh;            // the field just moved: built chunks start fully taken over
    private static float lastChunks;
    private const float TuftsFade = 1f;         // seconds the tufts take to give way to a chunk's own grass
    private static ComputeBuffer nearArgs, farArgs;
    private static int nearCells, farCells;
    private static readonly MaterialPropertyBlock nearDraw = new MaterialPropertyBlock(), farDraw = new MaterialPropertyBlock();

    private static World world;
    private static int generation;
    private static bool building, fieldReady;
    private static Vector2 fieldCorner, fieldCenter;
    private static float nextChunks;
    private static int buildingsCleared, loadedChunks;
    private static bool splatMaps;
    private static readonly Dictionary<string, int> biomeCells = new Dictionary<string, int>();
    private static string state = "not started";

    /// <summary>gfxe distantgrass debug: 1 draws the tufts magenta; 2 also draws those on roads and water, in red.</summary>
    public static int Debug;

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("DistantGrass") : null;
        if (shader != null && !shader.isSupported || !SystemInfo.supportsComputeShaders)
        {
            Log.Warning("[GraphicsExpanded] The distant grass shader isn't supported on this graphics card; distant grass is off");
            shader = null;
        }
        if (!Loaded)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave, enableInstancing = true };
        card = new Mesh { name = "GraphicsExpanded grass tuft", hideFlags = HideFlags.HideAndDontSave };
        card.vertices = new[] { new Vector3(-0.5f, 0f, 0f), new Vector3(0.5f, 0f, 0f), new Vector3(0.5f, 1f, 0f), new Vector3(-0.5f, 1f, 0f) };
        card.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
        card.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
        card.triangles = new[] { 0, 2, 1, 0, 3, 2 };
        card.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
        blades = MakeBlades();
        material.SetTexture("_GfxGrassBlades", blades);
        Vector4[] colors = new Vector4[16];
        for (int i = 0; i < Looks.Length; i++)
        {
            Color linear = ((Color)Looks[i].Color).linear;
            colors[i] = new Vector4(linear.r, linear.g, linear.b, 1f);
        }
        material.SetVectorArray("_GfxGrassColors", colors);
        nearArgs = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
        farArgs = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
    }

    /// <summary>Four patterns of grass blades side by side, 64 pixels square each, white with the blades in alpha.</summary>
    private static Texture2D MakeBlades()
    {
        const int width = 256, height = 64;
        Color32[] pixels = new Color32[width * height];
        for (int i = 0; i < pixels.Length; i++)
            pixels[i] = new Color32(255, 255, 255, 0);
        System.Random random = new System.Random(7);
        for (int pattern = 0; pattern < 4; pattern++)
        {
            int left = pattern * 64;
            for (int blade = 0; blade < 30; blade++)
            {
                float root = left + 3 + (float)random.NextDouble() * 58f;
                float top = (0.4f + 0.6f * (float)random.NextDouble()) * (height - 1);
                float lean = ((float)random.NextDouble() - 0.5f) * 0.6f;
                for (int y = 0; y < top; y++)
                {
                    float along = y / top;
                    float center = root + lean * y * (0.5f + along);
                    float half = Mathf.Lerp(1.5f, 0.35f, along);
                    for (int x = Mathf.FloorToInt(center - half - 1); x <= Mathf.CeilToInt(center + half + 1); x++)
                    {
                        if (x < left || x >= left + 64)
                            continue;
                        float cover = Mathf.Clamp01(half + 0.5f - Mathf.Abs(x + 0.5f - center));
                        int index = y * width + x;
                        pixels[index].a = (byte)Mathf.Max(pixels[index].a, Mathf.RoundToInt(cover * 255f));
                    }
                }
            }
        }
        Texture2D texture = new Texture2D(width, height, TextureFormat.RGBA32, true, true)
        {
            name = "GraphicsExpanded grass blades",
            wrapMode = TextureWrapMode.Clamp,
            filterMode = FilterMode.Trilinear,
            hideFlags = HideFlags.HideAndDontSave,
        };
        texture.SetPixels32(pixels);
        texture.Apply(true, true);
        return texture;
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        float outer = GfxSettings.DetailActive ? GfxSettings.DistantGrassMeters(GfxSettings.DistantGrass) : 0f;
        World current = GameManager.Instance != null ? GameManager.Instance.World : null;
        if (outer <= 0f || player == null || playerCamera == null || current == null)
        {
            if (outer <= 0f || current != world)
                Release();
            state = outer <= 0f ? "off" : "no world";
            return;
        }
        if (current != world)
        {
            Release();
            world = current;
        }
        Texture heights = GfxFarShadows.HeightMap(out Vector4 heightRect);
        if (heights == null)
        {
            state = "no far terrain";
            return;
        }

        Vector3 cameraWorld = playerCamera.transform.position + Origin.position;
        Vector2 here = new Vector2(cameraWorld.x, cameraWorld.z);
        if (!building && (!fieldReady || Vector2.Distance(here, fieldCenter) > RecenterAfter))
            GameManager.Instance.StartCoroutine(BuildField(here));
        if (!fieldReady)
        {
            state = "laying out the field";
            return;
        }
        UpdateChunks();

        // The near grid only reaches the end of the hand-over band, the far one the outer edge
        float nearReach = Mathf.Min(outer, BandEnd);
        Grid(nearDraw, nearArgs, ref nearCells, here, nearReach, NearCell, 1f, 0f);
        Grid(farDraw, farArgs, ref farCells, here, outer, FarCell, 2f, 1f);
        material.SetVector("_GfxGrassRange", new Vector4(0f, outer, FadeLength, 0f));
        material.SetVector("_GfxGrassCard", new Vector4(TuftWidth, TuftHeight, splatMaps ? 1f : 0f, Debug));
        material.SetVector("_GfxOrigin", Origin.position);
        material.SetTexture("_GfxGrassHeights", heights);
        material.SetVector("_GfxGrassHeightRect", heightRect);
        Bounds everywhere = new Bounds(playerCamera.transform.position, Vector3.one * 100000f);
        Graphics.DrawMeshInstancedIndirect(card, 0, material, everywhere, nearArgs, 0, nearDraw, ShadowCastingMode.Off, true, 0, playerCamera, LightProbeUsage.Off);
        if (outer > BandStart)
            Graphics.DrawMeshInstancedIndirect(card, 0, material, everywhere, farArgs, 0, farDraw, ShadowCastingMode.Off, true, 0, playerCamera, LightProbeUsage.Off);
        state = string.Format("out to {0:0} m, {1} near cells of {2} m and {3} far of {4} m", outer, nearCells * nearCells, NearCell,
            outer > BandStart ? farCells * farCells : 0, FarCell);
    }

    /// <summary>One draw's grid of cells around the camera, out to reach, with its tuft size and side of the band.</summary>
    private static void Grid(MaterialPropertyBlock draw, ComputeBuffer drawArgs, ref int cellsDrawn, Vector2 here, float reach, float cell, float size, float far)
    {
        int cells = Mathf.CeilToInt((2f * reach + 2f * cell) / cell);
        if (cells != cellsDrawn)
        {
            drawArgs.SetData(new uint[] { card.GetIndexCount(0), (uint)(cells * cells), 0, 0, 0 });
            cellsDrawn = cells;
        }
        Vector2 corner = new Vector2(Mathf.Floor((here.x - reach) / cell) * cell, Mathf.Floor((here.y - reach) / cell) * cell);
        draw.SetVector("_GfxGrassGrid", new Vector4(corner.x, corner.y, cell, cells));
        draw.SetVector("_GfxGrassRing", new Vector4(BandStart, BandEnd, far, size));
    }

    // ---- The field ----

    private static IEnumerator BuildField(Vector2 center)
    {
        building = true;
        int run = generation;
        // On whole chunks, so the loaded-chunk map lines up with the game's chunks
        Vector2 corner = new Vector2(Mathf.Floor((center.x - FieldSize / 2f) / 16f) * 16f, Mathf.Floor((center.y - FieldSize / 2f) / 16f) * 16f);

        // Biomes every few meters
        IBiomeProvider biomes = null;
        try
        {
            biomes = world.ChunkCache?.ChunkProvider?.GetBiomeProvider();
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Distant grass couldn't get the biome provider: " + e.Message);
        }
        int across = Mathf.RoundToInt(FieldSize / BiomeStep);
        byte[] look = new byte[across * across];
        Dictionary<BiomeDefinition, byte> lookOf = new Dictionary<BiomeDefinition, byte>();
        biomeCells.Clear();
        for (int row = 0; row < across; row++)
        {
            for (int column = 0; column < across; column++)
            {
                BiomeDefinition biome = null;
                try
                {
                    biome = biomes?.GetBiomeAt(Mathf.FloorToInt(corner.x + (column + 0.5f) * BiomeStep), Mathf.FloorToInt(corner.y + (row + 0.5f) * BiomeStep));
                }
                catch
                {
                    // Off the map: the default look
                }
                look[row * across + column] = LookOf(biome, lookOf);
            }
            if (row % 16 == 15)
            {
                yield return null;
                if (run != generation)
                    yield break;
            }
        }

        // How much grass grows, and the biome's color, every 2 m
        Color32[] pixels = new Color32[FieldTexels * FieldTexels];
        int perLook = FieldTexels / across;
        for (int y = 0; y < FieldTexels; y++)
        {
            for (int x = 0; x < FieldTexels; x++)
            {
                byte index = look[(y / perLook) * across + x / perLook];
                pixels[y * FieldTexels + x] = new Color32((byte)Mathf.RoundToInt(Looks[index].Density * 255f), index, 0, 255);
            }
        }
        yield return null;
        if (run != generation)
            yield break;

        // None on buildings' footprints (a little past them, for their yards' edges)
        buildingsCleared = 0;
        List<PrefabInstance> prefabs = GameManager.Instance.GetDynamicPrefabDecorator()?.allPrefabs;
        if (prefabs != null)
        {
            float texel = FieldSize / FieldTexels;
            foreach (PrefabInstance prefab in prefabs.ToArray())
            {
                if (prefab == null)
                    continue;
                int x0 = Mathf.FloorToInt((prefab.boundingBoxPosition.x - 3 - corner.x) / texel);
                int z0 = Mathf.FloorToInt((prefab.boundingBoxPosition.z - 3 - corner.y) / texel);
                int x1 = Mathf.CeilToInt((prefab.boundingBoxPosition.x + prefab.boundingBoxSize.x + 3 - corner.x) / texel);
                int z1 = Mathf.CeilToInt((prefab.boundingBoxPosition.z + prefab.boundingBoxSize.z + 3 - corner.y) / texel);
                if (x1 < 0 || z1 < 0 || x0 >= FieldTexels || z0 >= FieldTexels)
                    continue;
                for (int z = Mathf.Max(z0, 0); z < Mathf.Min(z1, FieldTexels); z++)
                    for (int x = Mathf.Max(x0, 0); x < Mathf.Min(x1, FieldTexels); x++)
                        pixels[z * FieldTexels + x].r = 0;
                buildingsCleared++;
            }
        }

        if (field == null)
        {
            // Point filtered: the color index mustn't blend between biomes
            field = new Texture2D(FieldTexels, FieldTexels, TextureFormat.RGBA32, false, true)
                { name = "GraphicsExpanded grass field", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.HideAndDontSave };
            chunks = new Texture2D(ChunkTexels, ChunkTexels, TextureFormat.R8, false, true)
                { name = "GraphicsExpanded grass chunks", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.HideAndDontSave };
        }
        field.SetPixels32(pixels);
        field.Apply(false);
        fieldCorner = corner;
        fieldCenter = center;
        nextChunks = 0f;
        chunksFresh = true;
        material.SetTexture("_GfxGrassField", field);
        material.SetTexture("_GfxGrassChunks", chunks);
        material.SetVector("_GfxGrassFieldRect", new Vector4(corner.x, corner.y, 1f / FieldSize, 0f));
        SetSplatMaps();
        fieldReady = true;
        building = false;
    }

    private static byte LookOf(BiomeDefinition biome, Dictionary<BiomeDefinition, byte> lookOf)
    {
        string name = biome?.m_sBiomeName ?? "";
        biomeCells[name] = biomeCells.TryGetValue(name, out int count) ? count + 1 : 1;
        if (biome != null && lookOf.TryGetValue(biome, out byte known))
            return known;
        string lower = name.ToLowerInvariant();
        byte index = (byte)(Looks.Length - 1);
        for (int i = 0; i < Looks.Length; i++)
        {
            if (Looks[i].Match.Length > 0 && lower.Contains(Looks[i].Match))
            {
                index = (byte)i;
                break;
            }
        }
        if (biome != null)
            lookOf[biome] = index;
        return index;
    }

    /// <summary>The world's road and water maps, which cover the whole world; without them grass grows on both.</summary>
    private static void SetSplatMaps()
    {
        splatMaps = false;
        try
        {
            if (world.ChunkCache?.ChunkProvider is ChunkProviderGenerateWorldFromRaw raw && raw.splats != null && raw.splats.Length >= 2
                && raw.splats[0] != null && raw.splats[1] != null)
            {
                Vector2i size = raw.GetWorldSize();
                material.SetTexture("_GfxGrassRoads", raw.splats[0]);
                material.SetTexture("_GfxGrassWater", raw.splats[1]);
                material.SetVector("_GfxGrassWorld", new Vector4(size.x, size.y, 0f, 0f));
                splatMaps = true;
            }
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Distant grass couldn't read the world's splat maps: " + e.Message);
        }
    }

    /// <summary>
    /// How far the game's own grass has taken over each chunk, ten times a second: only once a chunk's ground has a
    /// mesh (so a chunk that's loaded but not yet built keeps the distant grass instead of a bare gap), then rising over
    /// a second, the tufts dropping out one by one. A chunk the game stops drawing is back to none at once.
    /// </summary>
    private static void UpdateChunks()
    {
        if (Time.unscaledTime < nextChunks || world?.m_ChunkManager == null)
            return;
        float step = Mathf.Clamp(Time.unscaledTime - lastChunks, 0f, 0.5f) / TuftsFade;
        lastChunks = Time.unscaledTime;
        nextChunks = Time.unscaledTime + 0.1f;
        Array.Clear(chunkBuilt, 0, chunkBuilt.Length);
        loadedChunks = 0;
        Vector3 origin = Origin.position;
        foreach (ChunkGameObject chunk in world.m_ChunkManager.GetUsedChunkGameObjects())
        {
            if (chunk == null || !Built(chunk))
                continue;
            Vector3 corner = chunk.transform.position + origin;
            int x = Mathf.FloorToInt((corner.x + 8f - fieldCorner.x) / 16f), z = Mathf.FloorToInt((corner.z + 8f - fieldCorner.y) / 16f);
            if (x < 0 || z < 0 || x >= ChunkTexels || z >= ChunkTexels)
                continue;
            chunkBuilt[z * ChunkTexels + x] = true;
            loadedChunks++;
        }
        for (int i = 0; i < chunkTaken.Length; i++)
        {
            chunkTaken[i] = !chunkBuilt[i] ? 0f : chunksFresh ? 1f : Mathf.Min(1f, chunkTaken[i] + step);
            chunkPixels[i] = (byte)Mathf.RoundToInt(chunkTaken[i] * 255f);
        }
        chunksFresh = false;
        chunks.SetPixelData(chunkPixels, 0);
        chunks.Apply(false);
    }

    /// <summary>Whether any of the chunk's layers has its ground (terrain) or grass mesh built.</summary>
    private static bool Built(ChunkGameObject chunk)
    {
        if (chunk.layers == null)
            return false;
        foreach (ChunkGameObjectLayer layer in chunk.layers)
        {
            if (layer?.m_MeshFilter == null)
                continue;
            foreach (int mesh in new[] { MeshDescription.MESH_TERRAIN, MeshDescription.MESH_GRASS })
            {
                if (mesh < layer.m_MeshFilter.Length && layer.m_MeshFilter[mesh] != null && layer.m_MeshFilter[mesh].sharedMesh != null
                    && layer.m_MeshFilter[mesh].sharedMesh.vertexCount > 0)
                    return true;
            }
        }
        return false;
    }

    private static void Release()
    {
        generation++;
        building = false;
        fieldReady = false;
        world = null;
        if (field != null)
            Object.Destroy(field);
        if (chunks != null)
            Object.Destroy(chunks);
        field = chunks = null;
    }

    public static string Status()
    {
        if (!Loaded)
            return "Distant grass is off: the shader didn't load (see the log).";
        if (!fieldReady)
            return "Distant grass: " + state + ".";
        List<string> biomes = new List<string>();
        foreach (KeyValuePair<string, int> pair in biomeCells)
            biomes.Add((pair.Key.Length > 0 ? pair.Key : "none") + " " + pair.Value);
        return string.Format("Distant grass: {0}; field around ({1:0}, {2:0}) with biomes [{3}], {4} buildings kept clear, {5} loaded chunks, road and water maps {6}.",
            state, fieldCenter.x, fieldCenter.y, string.Join(", ", biomes), buildingsCleared, loadedChunks, splatMaps ? "found" : "missing");
    }
}
