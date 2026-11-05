using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

/// <summary>
/// Turns the grass renders in Build/grass/ (blender/grass/grass_tiles.py) into tiles for the game's grass texture
/// sheet, builds them into Build/grass-bundle/natureexpanded-grass.unity3d, and tries the copy the mod does in game
/// on the real sheet, saving Build/grass/sheet.png, and draws them as the game does beside vanilla's tall grass
/// (Build/grass/look-*.png, see Look). Run from src/build-grass.bat (batch mode with graphics).
///
/// The game draws grass blocks from one 4096 x 4096 sheet (ta_grass, DXT5 sRGB, 13 mips) with two companions in the
/// same layout: ta_grass_n (linear; normals as DXT5nm: x in alpha, y in green and blue, red 1; tangent y is world up,
/// and vanilla's blades lean up about 0.4 to 0.5) and ta_grass_s (red smoothness, green occlusion, blue translucency;
/// RGBA_DXT5_SRGB, so the game reads every stored value darker, 0.5 as 0.21). Vanilla's tiles are shaded toward the
/// ground: occlusion stored about 0.07 + 1.35 x the height up the tile (black at the base, full by about 0.6) and
/// translucency rising from none at the base, and the game sinks each grass quad 0.15 m into the ground
/// (BlockShapeGrass), so the bottom of every tile is buried. Vanilla uses 29 tiles of 512 laid on a 580 pitch; the
/// block from (1536, 2048) to the top-right corner is empty, room for 20 tiles 5 across and 4 up, on 512 boundaries
/// so that each mip down to 4 x 4 copies whole DXT blocks. Each grass becomes three
/// 512 x 512 DXT5 textures with mips in those layouts (Name_D, Name_N, Name_S), and the bundle carries GrassSheet,
/// a text list of each grass's texture id, name and average color, which the mod gives its uv entry.
/// </summary>
public static class NatureGrassBuilder
{
    public const string BundleName = "natureexpanded-grass.unity3d";
    private const string Tiles = "Assets/NatureExpanded/GrassTiles";
    public const int SheetX = 1536, SheetY = 2048, Tile = 512, Columns = 5, Slots = 20, FirstId = 600;
    // Vanilla's grass normals lean up so a blade lights like the ground under it; ours are pulled most of the way to
    // this (which leaves a blade facing the camera leaning up about 0.47, like vanilla's: the 0.72 here was read off
    // an sRGB preview of vanilla's normals, where the stored value shows brighter)
    private static readonly Vector3 Lean = new Vector3(0f, 0.72f, 0.69f).normalized;
    private const float LeanAmount = 0.6f;

    private struct Grass
    {
        public int Id;
        public string Name;
        public byte Smooth, Translucency;
        // 0 to 1: how far the tile is shaded toward the ground like vanilla's (grasses.txt's optional fifth column)
        public float Ground;
    }

    public static void Build()
    {
        string project = Directory.GetCurrentDirectory();
        string renders = Path.Combine(project, "Build", "grass");
        List<Grass> grasses = File.ReadAllLines(Path.Combine(project, "..", "blender", "grass", "grasses.txt"))
            .Where(l => l.Trim().Length > 0 && !l.StartsWith("#"))
            .Select(l => l.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries))
            .Select(p => new Grass
            {
                Id = int.Parse(p[0]), Name = p[1], Smooth = byte.Parse(p[2]), Translucency = byte.Parse(p[3]),
                Ground = p.Length > 4 ? Mathf.Clamp01(float.Parse(p[4], CultureInfo.InvariantCulture)) : 0f,
            })
            .ToList();
        if (grasses.Any(g => g.Id < FirstId || g.Id >= FirstId + Slots) || grasses.Select(g => g.Id).Distinct().Count() != grasses.Count)
        {
            throw new System.Exception("grasses.txt: ids must be distinct, " + FirstId + " to " + (FirstId + Slots - 1));
        }
        if (!AssetDatabase.IsValidFolder(Tiles))
        {
            AssetDatabase.CreateFolder("Assets/NatureExpanded", "GrassTiles");
        }

        StringBuilder sheet = new StringBuilder();
        List<string> assets = new List<string>();
        foreach (Grass g in grasses)
        {
            Texture2D color = Load(Path.Combine(renders, g.Name + "_Color.png"));
            Texture2D normal = Load(Path.Combine(renders, g.Name + "_Normal.png"));
            Texture2D t = Load(Path.Combine(renders, g.Name + "_T.png"));
            Color32[] c = color.GetPixels32(), n = normal.GetPixels32(), tt = t.GetPixels32();
            Border(c);
            Color average = Albedo(c);
            Save(Tiles + "/" + g.Name + "_D.png", c);
            Save(Tiles + "/" + g.Name + "_N.png", Normals(n, c));
            Save(Tiles + "/" + g.Name + "_S.png", Surface(tt, c, g.Smooth, g.Translucency, g.Ground));
            sheet.AppendLine(string.Format(CultureInfo.InvariantCulture, "{0} {1} {2:F3} {3:F3} {4:F3}", g.Id, g.Name, average.r, average.g, average.b));
            Object.DestroyImmediate(color);
            Object.DestroyImmediate(normal);
            Object.DestroyImmediate(t);
        }
        File.WriteAllText(Tiles + "/GrassSheet.txt", sheet.ToString());
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        foreach (Grass g in grasses)
        {
            Configure(Tiles + "/" + g.Name + "_D.png", true, true);
            Configure(Tiles + "/" + g.Name + "_N.png", false, false);
            Configure(Tiles + "/" + g.Name + "_S.png", false, false);
            assets.AddRange(new[] { "_D", "_N", "_S" }.Select(s => Tiles + "/" + g.Name + s + ".png"));
        }
        assets.Add(Tiles + "/GrassSheet.txt");

        string output = Path.Combine(project, "Build", "grass-bundle");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = assets.ToArray() };
        if (BuildPipeline.BuildAssetBundles(output, new[] { bundle },
                BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode | BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64) == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[NatureGrassBuilder] Built " + Path.Combine(output, BundleName) + " with " + grasses.Count + " grasses");
        TrySheet(grasses, Path.Combine(renders, "sheet.png"));
    }

    // ------------------------------------------------------------------ tiles

    private static Texture2D Load(string path)
    {
        if (!File.Exists(path))
        {
            throw new System.Exception("No render " + path + "; run blender/grass/grass_tiles.py first");
        }
        Texture2D tex = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        tex.LoadImage(File.ReadAllBytes(path));
        if (tex.width != Tile || tex.height != Tile)
        {
            throw new System.Exception(path + " is " + tex.width + "x" + tex.height + ", not " + Tile);
        }
        return tex;
    }

    /// <summary>Clears a 12-pixel edge on the sides of a tile and 20 on its top (the bottom is the ground the grass
    /// stands on): the tiles sit side by side in the sheet with no gap, so anything reaching an edge would bleed into
    /// the next tile in the smaller mips. The mod's uv frame stops 16 pixels short of the top (GrassSheetDEM), so the
    /// tile above's grass bases never bleed in either.</summary>
    private static void Border(Color32[] c)
    {
        const int edge = 12, top = 20;
        for (int y = 0; y < Tile; y++)
        {
            for (int x = 0; x < Tile; x++)
            {
                if (x < edge || x >= Tile - edge || y >= Tile - top)
                {
                    c[y * Tile + x].a = 0;
                }
            }
        }
    }

    /// <summary>Spreads each blade's color out into the transparent pixels round it (so the mips don't fade the grass
    /// to a dark halo at a distance), and returns the average color of the grass itself, darkened like the uv
    /// entries' colors are against their tiles.</summary>
    private static Color Albedo(Color32[] c)
    {
        bool[] known = c.Select(p => p.a > 8).ToArray();
        Vector3 sum = Vector3.zero;
        int count = 0;
        for (int i = 0; i < c.Length; i++)
        {
            if (c[i].a > 128)
            {
                sum += new Vector3(c[i].r, c[i].g, c[i].b);
                count++;
            }
        }
        Vector3 avg = count > 0 ? sum / count : new Vector3(50, 60, 28);
        for (int pass = 0; pass < 24; pass++)
        {
            bool[] next = (bool[])known.Clone();
            for (int y = 0; y < Tile; y++)
            {
                for (int x = 0; x < Tile; x++)
                {
                    int i = y * Tile + x;
                    if (known[i])
                    {
                        continue;
                    }
                    Vector3 s = Vector3.zero;
                    int k = 0;
                    for (int dy = -1; dy <= 1; dy++)
                    {
                        for (int dx = -1; dx <= 1; dx++)
                        {
                            int xx = x + dx, yy = y + dy;
                            if (xx < 0 || yy < 0 || xx >= Tile || yy >= Tile || !known[yy * Tile + xx])
                            {
                                continue;
                            }
                            Color32 p = c[yy * Tile + xx];
                            s += new Vector3(p.r, p.g, p.b);
                            k++;
                        }
                    }
                    if (k > 0)
                    {
                        s /= k;
                        c[i] = new Color32((byte)s.x, (byte)s.y, (byte)s.z, c[i].a);
                        next[i] = true;
                    }
                }
            }
            known = next;
        }
        for (int i = 0; i < c.Length; i++)
        {
            if (!known[i])
            {
                c[i] = new Color32((byte)avg.x, (byte)avg.y, (byte)avg.z, c[i].a);
            }
        }
        return new Color(avg.x / 255f * 0.78f, avg.y / 255f * 0.78f, avg.z / 255f * 0.7f);
    }

    /// <summary>Camera-space render normals, leaned toward vanilla's up-leaning grass normals, packed DXT5nm.</summary>
    private static Color32[] Normals(Color32[] n, Color32[] c)
    {
        Color32[] o = new Color32[n.Length];
        for (int i = 0; i < n.Length; i++)
        {
            Vector3 v = c[i].a > 8 ? new Vector3(n[i].r / 127.5f - 1f, n[i].g / 127.5f - 1f, n[i].b / 127.5f - 1f) : Lean;
            if (v.sqrMagnitude < 0.01f)
            {
                v = Lean;
            }
            v = Vector3.Lerp(v.normalized, Lean, LeanAmount).normalized;
            byte y = (byte)Mathf.Clamp(Mathf.RoundToInt((v.y * 0.5f + 0.5f) * 255f), 0, 255);
            byte x = (byte)Mathf.Clamp(Mathf.RoundToInt((v.x * 0.5f + 0.5f) * 255f), 0, 255);
            o[i] = new Color32(255, y, y, x);
        }
        return o;
    }

    /// <summary>Smoothness, occlusion (darker toward each blade's base) and translucency (more toward the tips). With
    /// `ground` above 0 the tile is also shaded toward the ground the way vanilla's are, by height: occlusion from near
    /// black at the base to none by about two thirds of the grass's height (0.6 of the tile for one as tall as
    /// vanilla's tall grass; empty pixels too, from about half, so the smaller mips stay dark there), and translucency
    /// from none at the base to full by about a third of it. Without it a dense or pale base stays fully lit by the
    /// sky where vanilla's grass goes dark, and reads as a flat bright band along the ground.</summary>
    private static Color32[] Surface(Color32[] t, Color32[] c, byte smooth, byte translucency, float ground)
    {
        int top = 0;
        for (int i = c.Length - 1; i >= 0; i--)
        {
            if (c[i].a > 8)
            {
                top = i / Tile;
                break;
            }
        }
        // Where the shading toward the ground ends, scaled to the grass's own height so a low one isn't all in shade
        float reach = Mathf.Clamp(0.65f * (top + 1) / Tile, 0.2f, 0.6f);
        Color32[] o = new Color32[t.Length];
        for (int i = 0; i < t.Length; i++)
        {
            // Texture rows run bottom up; h is height up the tile, as far as vanilla's tall grass would have it
            float h = i / Tile / (float)Tile * 0.6f / reach;
            if (c[i].a <= 8)
            {
                float empty = Mathf.Lerp(1f, Mathf.Clamp01(0.45f + 0.8f * h), ground);
                o[i] = new Color32(0, (byte)Mathf.RoundToInt(255f * empty), (byte)Mathf.RoundToInt(translucency * Mathf.Lerp(1f, Mathf.Clamp01(h / 0.35f), ground)), 255);
                continue;
            }
            float f = Mathf.Pow(t[i].r / 255f, 0.7f);
            float occlusion = (0.55f + 0.45f * f) * Mathf.Lerp(1f, Mathf.Clamp01(0.08f + 1.5f * h), ground);
            float light = (0.7f + 0.3f * f) * Mathf.Lerp(1f, Mathf.Clamp01(0.05f + h / 0.35f), ground);
            o[i] = new Color32(smooth, (byte)Mathf.RoundToInt(255f * occlusion), (byte)Mathf.RoundToInt(translucency * light), 255);
        }
        return o;
    }

    private static void Save(string path, Color32[] pixels)
    {
        Texture2D tex = new Texture2D(Tile, Tile, TextureFormat.RGBA32, false, true);
        tex.SetPixels32(pixels);
        tex.Apply();
        File.WriteAllBytes(path, tex.EncodeToPNG());
        Object.DestroyImmediate(tex);
    }

    private static void Configure(string path, bool srgb, bool coverage)
    {
        TextureImporter ti = (TextureImporter)AssetImporter.GetAtPath(path);
        ti.textureType = TextureImporterType.Default;
        ti.sRGBTexture = srgb;
        ti.alphaSource = TextureImporterAlphaSource.FromInput;
        ti.alphaIsTransparency = false;
        ti.mipmapEnabled = true;
        ti.mipmapFilter = TextureImporterMipFilter.BoxFilter;
        ti.mipMapsPreserveCoverage = coverage;
        ti.alphaTestReferenceValue = 0.5f;
        ti.wrapMode = TextureWrapMode.Clamp;
        ti.filterMode = FilterMode.Trilinear;
        ti.npotScale = TextureImporterNPOTScale.None;
        ti.isReadable = false;
        ti.maxTextureSize = Tile;
        ti.textureCompression = TextureImporterCompression.CompressedHQ;
        ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
        {
            name = "Standalone", overridden = true, maxTextureSize = Tile, format = TextureImporterFormat.DXT5,
            textureCompression = TextureImporterCompression.CompressedHQ,
        });
        ti.SaveAndReimport();
    }

    // ------------------------------------------------------------------ the copy, as the mod does it

    /// <summary>Where a grass's tile goes in the sheet (pixels from the bottom left, as uvs run).</summary>
    public static Vector2Int Place(int id)
    {
        int slot = id - FirstId;
        return new Vector2Int(SheetX + slot % Columns * Tile, SheetY + slot / Columns * Tile);
    }

    /// <summary>Copies a tile into the sheet mip by mip, down to 4 x 4 (whole DXT blocks; the sheet's smaller mips
    /// keep vanilla's empty corner). The mod's GrassSheetDEM does the same.</summary>
    public static void Copy(Texture tile, Texture sheet, int id)
    {
        Vector2Int at = Place(id);
        for (int m = 0; m < tile.mipmapCount && m < sheet.mipmapCount; m++)
        {
            int size = Tile >> m;
            if (size < 4)
            {
                break;
            }
            Graphics.CopyTexture(tile, 0, m, 0, 0, size, size, sheet, 0, m, at.x >> m, at.y >> m);
        }
    }

    /// <summary>Loads the game's own grass sheets, copies the new tiles into copies of them, and saves the colour
    /// sheet (and a close-up of the new block and the normal sheet's) to check the copy lands where the uvs say.</summary>
    private static void TrySheet(List<Grass> grasses, string path)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        AssetBundle bundle = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Addressables/Standalone/meshdescriptions_assets_all.bundle"));
        try
        {
            MeshDescription grass = bundle.LoadAllAssets<GameObject>().Select(go => go.GetComponent<MeshDescriptionCollection>())
                .First(c => c != null && !c.name.Contains("BlockVT")).meshes.First(m => m.Name == "grass");
            List<Texture2D> copies = new List<Texture2D>();
            foreach ((Texture2D vanilla, string suffix, string file) in new[]
                     { ((Texture2D)grass.TexDiffuse, "_D", ""), ((Texture2D)grass.TexNormal, "_N", "-normal"), ((Texture2D)grass.TexSpecular, "_S", "-surface") })
            {
                // Read as the game reads them: the colour and surface sheets as sRGB (ta_grass_s is RGBA_DXT5_SRGB, so
                // its occlusion and translucency come out darker than their stored values), the normals as linear
                Texture2D copy = new Texture2D(vanilla.width, vanilla.height, vanilla.format, vanilla.mipmapCount, suffix == "_N")
                {
                    // Kept through the look previews' new scene, which unloads unused objects
                    filterMode = FilterMode.Trilinear, anisoLevel = 16, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.DontUnloadUnusedAsset,
                };
                Graphics.CopyTexture(vanilla, copy);
                foreach (Grass g in grasses)
                {
                    Copy(AssetDatabase.LoadAssetAtPath<Texture2D>(Tiles + "/" + g.Name + suffix + ".png"), copy, g.Id);
                }
                SavePart(copy, path.Replace(".png", file + ".png"), new Rect(0f, 0f, 1f, 1f), 1024);
                SavePart(copy, path.Replace(".png", file + "-block.png"), new Rect(0.375f, 0.5f, 0.625f, 0.5f), 1280);
                if (suffix == "_D")
                {
                    // Drawn this small the GPU reads a low mip, to see the tiles survive the smaller copies
                    SavePart(copy, path.Replace(".png", "-small.png"), new Rect(0f, 0f, 1f, 1f), 256);
                    TopEdges(copy, grasses, path.Replace("sheet.png", "top-edges.txt"));
                }
                copies.Add(copy);
            }
            Look(grasses, copies, Path.GetDirectoryName(path));
            copies.ForEach(Object.DestroyImmediate);
        }
        finally
        {
            bundle.Unload(true);
        }
    }

    // ------------------------------------------------------------------ the look in game

    /// <summary>Vanilla's tiles the look previews draw beside the new grasses (frames from ta_grassxml): tall grass
    /// (uv 39), the five forest grass tiles of treeForestGrassDiagonal (561-565) and the short grass carpet (573).</summary>
    private static readonly Dictionary<string, Rect> Vanilla = new Dictionary<string, Rect>
    {
        { "TallGrass", VanillaTile(0.008300781f, 0.008300781f) },
        { "561", VanillaTile(0.1499023f, 0.574707f) }, { "562", VanillaTile(0.1499023f, 0.7163086f) },
        { "563", VanillaTile(0.1499023f, 0.8579102f) }, { "564", VanillaTile(0.2915039f, 0.2915039f) },
        { "565", VanillaTile(0.4331055f, 0.2915039f) }, { "ShortGrass", VanillaTile(0.8579102f, 0.2915039f) },
    };

    private static Rect VanillaTile(float x, float y)
    {
        return new Rect(x, y, 0.125f, 0.125f);
    }

    private struct Block
    {
        public Vector3 At;
        public Rect Uv;
        public float Scale;
        public int Turn;
        public bool Short;
    }

    /// <summary>Renders the grasses as the game draws them, from the sheets with the tiles copied in, with Torch's
    /// grass shader (Torch/Grass, a forward surface shader reading _Albedo, _Normal and _Gloss_AO_SSS): each block is
    /// BlockShapeGrass's spin mesh (BlockShapeBillboardPlant.RenderSpinMesh: upright double-sided quads a block wide,
    /// turned in steps, sunk 0.15 m into the ground, every second and third one 0.15 and 0.3 m shorter). Saves
    /// look-sun.png (front lit), look-back.png (against the sun) and look-shade.png (sky light only, as under trees):
    /// vanilla's tall grass first, then each grass, then vanilla's forest grass tiles, a patch of six blocks each;
    /// look-field.png, the first grass mixed half and half with tall grass over a stretch of ground, in sun and in
    /// shade; and, for each [section] of Build/grass/look-mix.txt if there is one, look-mix-section.png: a stretch of
    /// ground decorated the way the game does it, each block taking the first of the section's "name probability"
    /// lines (in order) whose roll comes up (a grass's name, TallGrass, ShortGrass, ForestGrass or a vanilla uv id).
    /// The game's own lighting and post-processing differ, so these compare grasses with vanilla's rather than show
    /// exact colours.</summary>
    private static void Look(List<Grass> grasses, List<Texture2D> sheets, string folder)
    {
        Shader shader = Torch("Torch/Grass");
        if (shader == null)
        {
            Debug.LogWarning("[NatureGrassBuilder] Torch/Grass not found (Mods/Torch); no look previews");
            return;
        }
        // Drawn in the batch run's own empty scene: a new scene would unload the sheet copies
        Material mat = new Material(shader);
        mat.SetTexture("_Albedo", sheets[0]);
        mat.SetTexture("_Normal", sheets[1]);
        mat.SetTexture("_Gloss_AO_SSS", sheets[2]);
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.95f, 0.86f);
        sun.shadows = LightShadows.Soft;
        Color sky = new Color(0.42f, 0.5f, 0.62f), horizon = new Color(0.36f, 0.38f, 0.36f), ground = new Color(0.12f, 0.11f, 0.08f);
        // The sky light as spherical harmonics (a trilight setting isn't turned into them without a lighting bake)
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Custom;
        RenderSettings.ambientIntensity = 1f;
        UnityEngine.Rendering.SphericalHarmonicsL2 sh = new UnityEngine.Rendering.SphericalHarmonicsL2();
        sh.AddAmbientLight(horizon);
        sh.AddDirectionalLight(Vector3.up, sky - horizon, 1f);
        sh.AddDirectionalLight(Vector3.down, ground - horizon, 1f);
        RenderSettings.ambientProbe = sh;
        RenderSettings.fog = false;
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.transform.localScale = new Vector3(6f, 1f, 6f);
        floor.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = new Color(0.16f, 0.13f, 0.08f) };
        floor.GetComponent<Renderer>().sharedMaterial.SetFloat("_Glossiness", 0.05f);

        Dictionary<string, Rect> frames = new Dictionary<string, Rect>(Vanilla);
        foreach (Grass g in grasses)
        {
            Vector2Int at = Place(g.Id);
            frames[g.Name] = new Rect(at.x / 4096f, at.y / 4096f, Tile / 4096f, (Tile - 16) / 4096f);
        }
        List<string> entries = new List<string> { "TallGrass" };
        entries.AddRange(grasses.Select(g => g.Name));
        entries.AddRange(new[] { "561", "562", "563", "564", "565" });
        const int cell = 320, cellH = 240, perRow = 7;
        foreach ((string light, Vector3 angles, float intensity) in new[]
                 { ("sun", new Vector3(38f, 25f, 0f), 1.25f), ("back", new Vector3(28f, 200f, 0f), 1.25f), ("shade", new Vector3(60f, 0f, 0f), 0f) })
        {
            sun.transform.rotation = Quaternion.Euler(angles);
            sun.intensity = intensity;
            sun.enabled = intensity > 0f;
            int rows = (entries.Count + perRow - 1) / perRow;
            Texture2D sheet = new Texture2D(cell * perRow, cellH * rows, TextureFormat.RGB24, false);
            sheet.SetPixels(Enumerable.Repeat(new Color(0.1f, 0.1f, 0.1f), sheet.width * sheet.height).ToArray());
            for (int i = 0; i < entries.Count; i++)
            {
                System.Random rnd = new System.Random(i * 7919 + 13);
                List<Block> blocks = new List<Block>();
                for (int x = -1; x <= 1; x++)
                {
                    for (int z = 0; z < 2; z++)
                    {
                        blocks.Add(new Block { At = new Vector3(x - 0.5f, 0f, z - 0.5f), Uv = frames[entries[i]], Scale = 0.93f + rnd.Next(4) * 0.07f, Turn = rnd.Next(8) });
                    }
                }
                GameObject patch = Patch(blocks, mat);
                Texture2D shot = Shoot(new Vector3(0.6f, 1.45f, -3.1f), new Vector3(0f, 0.32f, 0.3f), 34f, cell, cellH);
                int x0 = i % perRow * cell, y0 = (rows - 1 - i / perRow) * cellH;
                sheet.SetPixels(x0, y0, cell, cellH, shot.GetPixels());
                Object.DestroyImmediate(shot);
                Object.DestroyImmediate(patch.GetComponent<MeshFilter>().sharedMesh);
                Object.DestroyImmediate(patch);
            }
            File.WriteAllBytes(Path.Combine(folder, "look-" + light + ".png"), sheet.EncodeToPNG());
            Object.DestroyImmediate(sheet);
        }

        // Stretches of ground: the first grass half and half with vanilla's tall grass, and look-mix.txt's mixes
        List<(string file, List<(string name, float prob)> mix)> fields = new List<(string, List<(string, float)>)>
        {
            ("look-field.png", new List<(string, float)> { (grasses[0].Name, 0.425f), ("TallGrass", 0.74f) }),
        };
        string mixes = Path.Combine(folder, "look-mix.txt");
        if (File.Exists(mixes))
        {
            foreach (string raw in File.ReadAllLines(mixes))
            {
                string line = raw.Trim();
                if (line.StartsWith("[") && line.EndsWith("]"))
                {
                    fields.Add(("look-mix-" + line.Substring(1, line.Length - 2) + ".png", new List<(string, float)>()));
                }
                else if (line.Length > 0 && !line.StartsWith("#") && fields.Count > 1)
                {
                    string[] p = line.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
                    fields[fields.Count - 1].mix.Add((p[0], float.Parse(p[1], CultureInfo.InvariantCulture)));
                }
            }
        }
        string[] forest = { "561", "562", "563", "564", "565", "563" };
        foreach ((string file, List<(string name, float prob)> mix) in fields)
        {
            System.Random rnd = new System.Random(5);
            List<Block> blocks = new List<Block>();
            for (int x = -9; x <= 9; x++)
            {
                for (int z = -2; z <= 16; z++)
                {
                    // The decorator's way: the first entry whose roll comes up
                    foreach ((string name, float prob) in mix)
                    {
                        if (rnd.NextDouble() >= prob)
                        {
                            continue;
                        }
                        string tile = name == "ForestGrass" ? forest[rnd.Next(forest.Length)] : name;
                        if (frames.TryGetValue(tile, out Rect uv))
                        {
                            blocks.Add(new Block { At = new Vector3(x, 0f, z), Uv = uv, Scale = 0.93f + rnd.Next(4) * 0.07f, Turn = rnd.Next(8), Short = tile == "ShortGrass" });
                        }
                        break;
                    }
                }
            }
            GameObject field = Patch(blocks, mat);
            const int w = 960, h = 540;
            Texture2D sheet = new Texture2D(w, h * 2, TextureFormat.RGB24, false);
            int k = 0;
            foreach (float intensity in new[] { 0f, 1.25f })
            {
                sun.transform.rotation = Quaternion.Euler(38f, 25f, 0f);
                sun.intensity = intensity;
                sun.enabled = intensity > 0f;
                Texture2D shot = Shoot(new Vector3(0.5f, 1.7f, -4.5f), new Vector3(0f, 0.2f, 4f), 50f, w, h);
                sheet.SetPixels(0, k++ * h, w, h, shot.GetPixels());
                Object.DestroyImmediate(shot);
            }
            File.WriteAllBytes(Path.Combine(folder, file), sheet.EncodeToPNG());
            Object.DestroyImmediate(sheet);
            Object.DestroyImmediate(field.GetComponent<MeshFilter>().sharedMesh);
            Object.DestroyImmediate(field);
        }
        Object.DestroyImmediate(mat);
        Object.DestroyImmediate(sun.gameObject);
        Object.DestroyImmediate(floor);
    }

    /// <summary>The spin meshes of grass blocks, as BlockShapeGrass.renderFull (or, for Short, the short grass
    /// carpet's BlockShapeGrassShort: a third as tall, sunk 0.09 m, showing the bottom third of its tile) and
    /// BlockShapeBillboardPlant.RenderSpinMesh build them (3 planes, the count at the lowest grass quality but
    /// one).</summary>
    private static GameObject Patch(List<Block> blocks, Material mat)
    {
        List<Vector3> v = new List<Vector3>(), n = new List<Vector3>();
        List<Vector4> t = new List<Vector4>();
        List<Vector2> uv = new List<Vector2>();
        List<int> tris = new List<int>();
        void Quad(Vector3[] p, Vector2[] q, Vector3 normal, Vector4 tangent, Rect frame)
        {
            int first = v.Count;
            for (int k = 0; k < 4; k++)
            {
                v.Add(p[k]);
                n.Add(normal);
                t.Add(tangent);
                uv.Add(new Vector2(frame.x + q[k].x * frame.width, frame.y + q[k].y * frame.height));
            }
            // Wound to face along its normal (Unity's front faces are clockwise as seen)
            bool flip = Vector3.Dot(Vector3.Cross(p[1] - p[0], p[2] - p[0]), normal) < 0f;
            tris.AddRange(flip ? new[] { first, first + 2, first + 1, first, first + 3, first + 2 } : new[] { first, first + 1, first + 2, first, first + 2, first + 3 });
        }
        foreach (Block b in blocks)
        {
            const int count = 3;
            float scale = b.Short ? 1f : b.Scale, height = b.Short ? 0.33f : b.Scale;
            float step = 180f / count + 180f, half = 0.5f * scale, shift = (b.Short ? 0.22f : 0.075f) * scale, rotation = 10f + b.Turn * 22.5f;
            float bottom = b.At.y - (b.Short ? 0.09f : 0.15f);
            Rect frame = b.Uv;
            if (b.Short)
            {
                frame.height *= 0.33f;
            }
            Vector3 c = b.At + new Vector3(0.5f, 0f, 0.5f);
            for (int i = 0; i < count; i++)
            {
                float a = (i * step + rotation) * Mathf.Deg2Rad, s = Mathf.Sin(a), co = Mathf.Cos(a);
                Vector3 p0 = new Vector3(c.x - half * co - shift * s, bottom, c.z - half * s + shift * co);
                Vector3 p1 = new Vector3(c.x + half * co - shift * s, bottom, c.z + half * s + shift * co);
                float top = bottom + height - i % 3 * 0.15f;
                Vector3 p2 = new Vector3(p1.x, top, p1.z), p3 = new Vector3(p0.x, top, p0.z);
                Vector3 normal = new Vector3(s, 0f, -co);
                Vector3 along = (p1 - p0).normalized;
                Quad(new[] { p0, p1, p2, p3 }, new[] { Vector2.zero, Vector2.right, Vector2.one, Vector2.up }, normal, new Vector4(along.x, along.y, along.z, -1f), frame);
                Quad(new[] { p0, p3, p2, p1 }, new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right }, -normal, new Vector4(along.x, along.y, along.z, 1f), frame);
            }
        }
        Mesh mesh = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
        mesh.SetVertices(v);
        mesh.SetNormals(n);
        mesh.SetTangents(t);
        mesh.SetUVs(0, uv);
        mesh.SetColors(Enumerable.Repeat(Color.white, v.Count).ToList());
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateBounds();
        GameObject go = new GameObject("GrassPatch");
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
        return go;
    }

    private static Texture2D Shoot(Vector3 from, Vector3 at, float fov, int width, int height)
    {
        Camera camera = new GameObject("LookCam").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.Forward;
        camera.allowHDR = false;
        camera.allowMSAA = false;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.55f, 0.64f, 0.76f);
        camera.fieldOfView = fov;
        camera.nearClipPlane = 0.05f;
        camera.farClipPlane = 200f;
        camera.transform.position = from;
        camera.transform.LookAt(at);
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        read.Apply();
        RenderTexture.active = null;
        camera.targetTexture = null;
        Object.DestroyImmediate(camera.gameObject);
        target.Release();
        Object.DestroyImmediate(target);
        return read;
    }

    /// <summary>For each grass, how many pixels along the top row of its frame come out opaque when the frame is drawn
    /// at a few sizes (smaller reads lower mips, as a block further off does), with the frame running to the tile's
    /// top and with the mod's 16-pixel inset. Opaque pixels on that row are the line strung across a grass block's
    /// top when the tile above bleeds in.</summary>
    private static void TopEdges(Texture sheet, List<Grass> grasses, string path)
    {
        StringBuilder sb = new StringBuilder("grass: opaque top-row pixels/highest alpha per drawn size 256/128/64/32/16, without inset | with 16 px inset\n");
        Shader torchGrass = Torch("Torch/Grass");
        if (torchGrass != null)
        {
            Material probe = new Material(torchGrass);
            sb.AppendLine("Torch/Grass defaults: " + string.Join(", ", Enumerable.Range(0, torchGrass.GetPropertyCount())
                .Where(i => torchGrass.GetPropertyType(i) == UnityEngine.Rendering.ShaderPropertyType.Float || torchGrass.GetPropertyType(i) == UnityEngine.Rendering.ShaderPropertyType.Range)
                .Select(i => torchGrass.GetPropertyName(i) + " " + probe.GetFloat(torchGrass.GetPropertyName(i)).ToString("F2"))));
            Object.DestroyImmediate(probe);
        }
        foreach (Grass g in grasses)
        {
            Vector2Int at = Place(g.Id);
            sb.Append(g.Name + ":");
            foreach (int inset in new[] { 0, 16 })
            {
                foreach (int size in new[] { 256, 128, 64, 32, 16 })
                {
                    RenderTexture rt = RenderTexture.GetTemporary(size, size, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                    // Stretched half a pixel so the top row samples exactly on the frame's top edge, where the game's
                    // anti-aliasing jitter and anisotropic filtering put samples
                    float h = (Tile - inset) / 4096f * size / (size - 0.5f);
                    Graphics.Blit(sheet, rt, new Vector2(Tile / 4096f, h), new Vector2(at.x / 4096f, at.y / 4096f));
                    RenderTexture.active = rt;
                    Texture2D read = new Texture2D(size, 1, TextureFormat.RGBA32, false);
                    read.ReadPixels(new Rect(0, size - 1, size, 1), 0, 0);
                    RenderTexture.active = null;
                    RenderTexture.ReleaseTemporary(rt);
                    Color32[] row = read.GetPixels32();
                    sb.Append(" " + row.Count(p => p.a > 127) + "/" + row.Max(p => p.a));
                    Object.DestroyImmediate(read);
                }
                sb.Append(inset == 0 ? " |" : "");
            }
            sb.AppendLine();
        }
        File.WriteAllText(path, sb.ToString());
    }

    private static AssetBundle torchBundle;

    /// <summary>One of Torch's shaders (the mod in Mods/Torch replaces the game's grass and plant shaders), or null.</summary>
    private static Shader Torch(string name)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string path = Path.Combine(game, "Mods/Torch/Resources/torchshaders.unity3d");
        if (torchBundle == null && File.Exists(path))
        {
            torchBundle = AssetBundle.LoadFromFile(path);
        }
        return torchBundle != null ? torchBundle.LoadAllAssets<Shader>().FirstOrDefault(s => s.name == name) : null;
    }

    /// <summary>Reference only: writes Build/grass/probe.txt, the game's grass sheets' formats (whether each is read
    /// as sRGB) and Torch/Grass's properties and passes.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureGrassBuilder.Probe</summary>
    public static void Probe()
    {
        StringBuilder sb = new StringBuilder();
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        AssetBundle bundle = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Addressables/Standalone/meshdescriptions_assets_all.bundle"));
        try
        {
            MeshDescription grass = bundle.LoadAllAssets<GameObject>().Select(go => go.GetComponent<MeshDescriptionCollection>())
                .First(c => c != null && !c.name.Contains("BlockVT")).meshes.First(m => m.Name == "grass");
            foreach (Texture t in new[] { grass.TexDiffuse, grass.TexNormal, grass.TexSpecular })
            {
                sb.AppendLine(t.name + ": " + t.graphicsFormat + " srgb " + GraphicsFormatUtility.IsSRGBFormat(t.graphicsFormat) + " mips " + t.mipmapCount
                    + " filter " + t.filterMode + " aniso " + t.anisoLevel + " bias " + t.mipMapBias);
            }
        }
        finally
        {
            bundle.Unload(true);
        }
        Shader torchGrass = Torch("Torch/Grass");
        if (torchGrass != null)
        {
            sb.AppendLine("Torch/Grass: passes " + torchGrass.passCount + ", queue " + torchGrass.renderQueue + ", supported " + torchGrass.isSupported);
            for (int i = 0; i < torchGrass.GetPropertyCount(); i++)
            {
                UnityEngine.Rendering.ShaderPropertyType type = torchGrass.GetPropertyType(i);
                string value = type == UnityEngine.Rendering.ShaderPropertyType.Texture ? torchGrass.GetPropertyTextureDefaultName(i)
                    : type == UnityEngine.Rendering.ShaderPropertyType.Color || type == UnityEngine.Rendering.ShaderPropertyType.Vector
                        ? torchGrass.GetPropertyDefaultVectorValue(i).ToString("F3") : torchGrass.GetPropertyDefaultFloatValue(i).ToString("F3");
                sb.AppendLine("  " + torchGrass.GetPropertyName(i) + " " + type + " \"" + torchGrass.GetPropertyDescription(i) + "\" "
                    + string.Join(",", torchGrass.GetPropertyAttributes(i)) + " default " + value);
            }
            Material probe = new Material(torchGrass);
            for (int p = 0; p < probe.passCount; p++)
            {
                sb.AppendLine("  pass " + p + " " + probe.GetPassName(p) + " LightMode " + probe.GetTag("LightMode", false, "") + " " + torchGrass.FindPassTagValue(p, new UnityEngine.Rendering.ShaderTagId("LightMode")).name);
            }
            sb.AppendLine("  keywords: " + string.Join(" ", torchGrass.keywordSpace.keywordNames));
            sb.AppendLine("  RenderType " + probe.GetTag("RenderType", false, "") + " Queue " + probe.GetTag("Queue", false, ""));
            Object.DestroyImmediate(probe);
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "grass", "probe.txt"), sb.ToString());
    }

    private static void SavePart(Texture tex, string path, Rect part, int width)
    {
        int height = Mathf.RoundToInt(width * part.height / part.width);
        RenderTexture rt = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        Graphics.Blit(tex, rt, new Vector2(part.width, part.height), new Vector2(part.x, part.y));
        RenderTexture prev = RenderTexture.active;
        RenderTexture.active = rt;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGBA32, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        RenderTexture.active = prev;
        RenderTexture.ReleaseTemporary(rt);
        // Show alpha as a backdrop, so the empty parts of the sheet read as empty
        Color32[] px = read.GetPixels32();
        for (int i = 0; i < px.Length; i++)
        {
            float a = px[i].a / 255f;
            px[i] = new Color32((byte)(px[i].r * a + 90 * (1 - a)), (byte)(px[i].g * a), (byte)(px[i].b * a + 90 * (1 - a)), 255);
        }
        read.SetPixels32(px);
        File.WriteAllBytes(path, read.EncodeToPNG());
        Object.DestroyImmediate(read);
    }
}
