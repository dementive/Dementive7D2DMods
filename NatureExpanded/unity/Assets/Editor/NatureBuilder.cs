using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Turns the Blender exports in Assets/NatureExpanded/Models/&lt;Name&gt;/ (Name.fbx with the meshes Name and Name_LOD1,
/// and the baked Name_Albedo/_Normal/_RMOM maps) into block prefabs, builds them into Build/natureexpanded.unity3d,
/// and renders each plant in the game's own plant shader to Build/plants/&lt;Name&gt;.png (up close beside vanilla
/// cotton, and as a drift) plus Build/plants/contact-N.png: every plant framed on its own, near mesh beside far mesh.
/// Run from src/build-bundle.bat (batch mode with graphics). "-plants A,B" renders only those plants' previews.
///
/// Laid out like the game's own plants (vanilla cotton): the root carries the LODGroup and a BoxCollider (layer 16)
/// round the plant, clipped to its block column; each LOD is a child at y = -0.5 whose mesh has its origin on the
/// ground, because the plant shader sways a vertex by its height above the mesh's origin (_WindStartY 0). The
/// Blender meshes have their origin at the block's center (ground at -0.5), so each is baked with its import
/// transform and lifted 0.5 into a mesh asset of its own, doubled into two-sided sheets (see Grounded).
///
/// The materials are Standard ones carrying the plant shader's maps (albedo, normal, and RMOM in the unused
/// _DetailMask slot, its alpha cleared: the plant shader tints by it); the mod moves them to the game's
/// Game/EntityTintMaskSSS when a plant spawns (NatureShaderDEM), and tags the collider T_Block, since a bundle can't
/// carry the game's tags.
/// </summary>
public static class NatureBuilder
{
    private const string BundleName = "natureexpanded.unity3d";
    // The ground cover (leaf litter, stones, ash, ...): walk-through patches with textures baked at 1024 and 2048, which
    // the plants' 512 cap would smear and which would make the plants bundle too big to keep in git
    private const string GroundBundleName = "natureexpanded-ground.unity3d";
    private const string Models = "Assets/NatureExpanded/Models";
    private const string Prefabs = "Assets/NatureExpanded/Prefabs";
    private const string GameShader = "Game/EntityTintMaskSSS";

    private static readonly string[] GameBundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "automatic_assets_entities/plants.bundle",
    };

    /// <summary>Plants taller than one block (their collider and the block's MultiBlockDim reach up this many blocks).
    /// Everything else stands in one.</summary>
    public static int Height(Bounds b)
    {
        return Mathf.Clamp(Mathf.CeilToInt(b.max.y + 0.5f - 0.05f), 1, 4);
    }

    public static void BuildAndPreview()
    {
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[]
        {
            GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan,
            GraphicsDeviceType.OpenGLCore,
        });
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (!AssetDatabase.IsValidFolder(Prefabs))
        {
            AssetDatabase.CreateFolder("Assets/NatureExpanded", "Prefabs");
        }

        string[] args = System.Environment.GetCommandLineArgs();
        int only = System.Array.IndexOf(args, "-plants");
        HashSet<string> wanted = only >= 0 && only + 1 < args.Length ? new HashSet<string>(args[only + 1].Split(',')) : null;

        List<string> prefabs = new List<string>();
        List<string> problems = new List<string>();
        List<string> sizes = new List<string>();
        foreach (string dir in Directory.GetDirectories(Models).OrderBy(d => d))
        {
            string name = Path.GetFileName(dir);
            string folder = Models + "/" + name;
            string fbx = folder + "/" + name + ".fbx";
            if (!File.Exists(fbx))
            {
                Debug.LogWarning("[NatureBuilder] " + name + ": no " + fbx + " yet; skipped");
                continue;
            }
            string prefab = MakePrefab(folder, name, problems, sizes);
            if (prefab != null)
            {
                prefabs.Add(prefab);
            }
        }
        AssetDatabase.SaveAssets();
        foreach (string p in problems)
        {
            Debug.LogError("[NatureBuilder] PROBLEM " + p);
        }
        if (problems.Count > 0)
        {
            throw new System.Exception(problems.Count + " model problems; see the log above");
        }

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        // What the block XML needs from each plant (its height in blocks), for gen-blocks to read
        File.WriteAllLines(Path.Combine(output, "plant-sizes.txt"), sizes);
        AssetBundleBuild bundle = new AssetBundleBuild
        {
            assetBundleName = BundleName,
            assetNames = prefabs.Where(p => !GroundCover(Path.GetFileNameWithoutExtension(p))).ToArray(),
        };
        AssetBundleBuild ground = new AssetBundleBuild
        {
            assetBundleName = GroundBundleName,
            assetNames = prefabs.Where(p => GroundCover(Path.GetFileNameWithoutExtension(p))).ToArray(),
        };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle, ground },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode
                | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[NatureBuilder] Built " + Path.Combine(output, BundleName) + " with " + bundle.assetNames.Length + " plants ("
            + new FileInfo(Path.Combine(output, BundleName)).Length / 1048576 + " MB) and " + Path.Combine(output, GroundBundleName)
            + " with " + ground.assetNames.Length + " ground covers (" + new FileInfo(Path.Combine(output, GroundBundleName)).Length / 1048576 + " MB)");

        Previews(prefabs.Where(p => wanted == null || wanted.Contains(Path.GetFileNameWithoutExtension(p))).ToList(), prefabs,
            Path.Combine(output, "plants"));
    }

    // ------------------------------------------------------------------ prefabs

    private static string MakePrefab(string folder, string name, List<string> problems, List<string> sizes)
    {
        foreach (string path in Directory.GetFiles(folder, name + "_*.png").Select(p => p.Replace('\\', '/')))
        {
            ConfigureTexture(path, MaxTextureSize(name));
        }
        string fbx = folder + "/" + name + ".fbx";
        ModelImporter model = (ModelImporter)AssetImporter.GetAtPath(fbx);
        model.globalScale = 1f;
        model.useFileScale = true;
        model.importNormals = ModelImporterNormals.Import;
        model.importTangents = ModelImporterTangents.CalculateMikk;
        model.animationType = ModelImporterAnimationType.None;
        model.importAnimation = false;
        model.importCameras = false;
        model.importLights = false;
        model.isReadable = true;
        model.materialImportMode = ModelImporterMaterialImportMode.None;
        model.SaveAndReimport();

        GameObject source = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
        MeshFilter[] filters = source.GetComponentsInChildren<MeshFilter>(true);
        MeshFilter near = filters.FirstOrDefault(f => f.name == name);
        MeshFilter far = filters.FirstOrDefault(f => f.name == name + "_LOD1");
        if (near == null)
        {
            problems.Add(name + ": the FBX has no mesh named " + name + " (has " + string.Join(", ", filters.Select(f => f.name)) + ")");
            return null;
        }
        Material material = MakeMaterial(folder, name);

        GameObject root = new GameObject(name);
        List<Renderer> lods = new List<Renderer>();
        foreach (MeshFilter f in new[] { near, far }.Where(f => f != null))
        {
            Mesh mesh = Grounded(f, source.transform, Prefabs + "/" + f.name + ".asset", !Solid(name));
            GameObject part = new GameObject(f.name);
            part.transform.SetParent(root.transform, false);
            part.transform.localPosition = new Vector3(0f, -0.5f, 0f);
            part.AddComponent<MeshFilter>().sharedMesh = mesh;
            MeshRenderer r = part.AddComponent<MeshRenderer>();
            r.sharedMaterial = material;
            r.shadowCastingMode = ShadowCastingMode.On;
            r.receiveShadows = true;
            lods.Add(r);
        }
        if (far == null)
        {
            Debug.LogWarning("[NatureBuilder] " + name + ": no " + name + "_LOD1 mesh; one LOD only");
        }

        // As vanilla cotton: full detail down to 6% of the screen's height, the far mesh to 0.8%, then gone
        LODGroup group = root.AddComponent<LODGroup>();
        group.SetLODs(lods.Count > 1
            ? new[] { new LOD(0.06f, new[] { lods[0] }), new LOD(0.008f, new[] { lods[1] }) }
            : new[] { new LOD(0.008f, new[] { lods[0] }) });
        group.RecalculateBounds();

        // The collider: round the plant, clipped to its block column (a bush may spill over its neighbours)
        Bounds b = lods[0].bounds;
        int height = Height(b);
        BoxCollider collider = root.AddComponent<BoxCollider>();
        Vector3 lo = new Vector3(Mathf.Max(b.min.x, -0.5f), -0.5f, Mathf.Max(b.min.z, -0.5f));
        Vector3 hi = new Vector3(Mathf.Min(b.max.x, 0.5f), Mathf.Min(b.max.y, height - 0.5f), Mathf.Min(b.max.z, 0.5f));
        collider.center = (lo + hi) / 2f;
        // A patch lying on the ground is a few centimetres high: give the tool a box it can hit
        collider.size = Vector3.Max(hi - lo, new Vector3(0.2f, GroundCover(name) ? 0.14f : 0.1f, 0.2f));
        root.layer = 16;
        sizes.Add(name + " " + height + " " + b.size.x.ToString("F2") + " " + b.size.y.ToString("F2") + " " + b.size.z.ToString("F2"));
        Debug.Log("[NatureBuilder] " + name + " bounds " + b.center.ToString("F2") + " size " + b.size.ToString("F2") + ", "
            + height + " block(s) tall, " + lods.Count + " LODs, "
            + ((MeshRenderer)lods[0]).GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3 + " triangles drawn");

        string prefabPath = Prefabs + "/" + name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Object.DestroyImmediate(root);
        return prefabPath;
    }

    /// <summary>
    /// A copy of an imported mesh with its node's import transform baked in and lifted 0.5, so its origin sits on the
    /// ground (y 0) like the game's plants. Two-sided, every triangle is doubled back to back (reversed winding,
    /// flipped normal) for drawing with back faces culled: the plant shader lights a back face with its front's
    /// normal, so a single-sheet leaf seen from behind came out black.
    /// </summary>
    private static Mesh Grounded(MeshFilter filter, Transform fbxRoot, string path, bool twoSided)
    {
        Matrix4x4 m = Matrix4x4.Translate(new Vector3(0f, 0.5f, 0f)) * fbxRoot.worldToLocalMatrix * filter.transform.localToWorldMatrix;
        Mesh src = filter.sharedMesh;
        Vector3[] v = src.vertices.Select(x => m.MultiplyPoint3x4(x)).ToArray();
        Vector3[] n = src.normals.Select(x => m.MultiplyVector(x).normalized).ToArray();
        Vector4[] t = src.tangents.Select(x =>
        {
            Vector3 d = m.MultiplyVector(x).normalized;
            return new Vector4(d.x, d.y, d.z, x.w);
        }).ToArray();
        Vector2[] uv = src.uv;
        // Nothing may float: a piece more than 3 cm clear of everything (a flower or berry whose twig the far LOD
        // left out) reads as debris hanging over the plant
        int[] tris = NatureMeshCheck.WithoutFloaters(v, src.triangles, 0.03f, out int floaters);
        if (floaters > 0)
        {
            Debug.Log("[NatureBuilder] " + filter.name + ": took out " + floaters + " floating pieces");
        }
        if (twoSided)
        {
            int count = v.Length;
            int[] back = new int[tris.Length];
            for (int i = 0; i < tris.Length; i += 3)
            {
                back[i] = tris[i] + count;
                back[i + 1] = tris[i + 2] + count;
                back[i + 2] = tris[i + 1] + count;
            }
            v = v.Concat(v).ToArray();
            n = n.Concat(n.Select(x => -x)).ToArray();
            // Same U direction, so the binormal sign flips with the normal
            t = t.Concat(t.Select(x => new Vector4(x.x, x.y, x.z, -x.w))).ToArray();
            uv = uv.Concat(uv).ToArray();
            tris = tris.Concat(back).ToArray();
        }
        Mesh mesh = new Mesh { name = filter.name };
        mesh.indexFormat = v.Length > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
        mesh.vertices = v;
        mesh.normals = n;
        if (t.Length > 0)
        {
            mesh.tangents = t;
        }
        mesh.uv = uv;
        mesh.triangles = tris;
        mesh.RecalculateBounds();
        mesh.UploadMeshData(false);
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(mesh, path);
        return mesh;
    }

    /// <summary>The largest an atlas may stay in the bundle. Flowers and bushes are seen from a few meters and drop to
    /// 512; the solid plants (a log, mushrooms, cacti) are looked at from an arm's length, where 512 smeared a log's
    /// 2048 atlas to under 2 texels a centimeter, so they keep the size they were baked at (up to 2048).</summary>
    private static int MaxTextureSize(string plant)
    {
        return Solid(plant) || GroundCover(plant) ? 2048 : 512;
    }

    private static void ConfigureTexture(string path, int maxSize)
    {
        if (!(path.EndsWith("_Albedo.png") || path.EndsWith("_Normal.png") || path.EndsWith("_RMOM.png")))
        {
            return;
        }
        TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
        bool normal = path.EndsWith("_Normal.png");
        bool linear = path.EndsWith("_RMOM.png");
        importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        importer.sRGBTexture = !(normal || linear);
        importer.alphaSource = linear ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
        importer.alphaIsTransparency = false;
        importer.mipmapEnabled = true;
        importer.wrapMode = TextureWrapMode.Clamp;
        // Looked at along a log's side, a solid plant needs more anisotropic filtering than a flower
        importer.anisoLevel = maxSize > 512 ? 8 : 2;
        importer.maxTextureSize = maxSize;
        importer.textureCompression = TextureImporterCompression.Compressed;
        importer.SaveAndReimport();
    }

    /// <summary>The plant's RMOM map with its alpha cleared, as a texture of its own in Prefabs. The plant shader reads
    /// RMOM's alpha as a mask that turns the plant to its _TintColor (white): vanilla plants keep it at 0, and the
    /// Blender bake writes no alpha (so 1, which drew every plant white).</summary>
    private static Texture2D Unmasked(string folder, string name)
    {
        string path = Prefabs + "/" + name + "_RMOM.png";
        Texture2D src = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        src.LoadImage(File.ReadAllBytes(folder + "/" + name + "_RMOM.png"));
        Color32[] px = src.GetPixels32();
        for (int i = 0; i < px.Length; i++)
        {
            px[i].a = 0;
        }
        src.SetPixels32(px);
        File.WriteAllBytes(path, src.EncodeToPNG());
        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
        ConfigureTexture(path, MaxTextureSize(name));
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    private static Material MakeMaterial(string folder, string name)
    {
        string path = folder + "/" + name + ".mat";
        Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (material == null)
        {
            material = new Material(Shader.Find("Standard"));
            AssetDatabase.CreateAsset(material, path);
        }
        material.shader = Shader.Find("Standard");
        material.shaderKeywords = new string[0];
        material.name = name;
        Texture2D Tex(string suffix) => AssetDatabase.LoadAssetAtPath<Texture2D>(folder + "/" + name + "_" + suffix + ".png");
        material.SetTexture("_MainTex", Tex("Albedo"));
        material.SetTexture("_BumpMap", Tex("Normal"));
        material.EnableKeyword("_NORMALMAP");
        // Not read by Standard; the mod hands it to the plant shader as _RMOM
        material.SetTexture("_DetailMask", Unmasked(folder, name));
        material.SetFloat("_Glossiness", 0.2f);
        EditorUtility.SetDirty(material);
        return material;
    }

    // ------------------------------------------------------------------ in the game's shader

    /// <summary>
    /// A plant material in the game's plant shader, set up exactly as the mod's NatureShaderDEM does in game: the
    /// Standard material's maps, vanilla cotton's settings, back faces culled on the two-sided meshes, and the wind's
    /// strength for that plant.
    /// </summary>
    public static Material ToGame(Shader game, Material src)
    {
        Material m = new Material(game) { name = src.name + " (game)" };
        m.SetTexture("_Albedo", src.GetTexture("_MainTex"));
        m.SetTexture("_Normal", src.GetTexture("_BumpMap"));
        m.SetTexture("_RMOM", src.GetTexture("_DetailMask"));
        m.SetColor("_TintColor", new Color(1f, 1f, 1f, 0f));
        m.SetColor("_SSSColor", new Color(0f, 0f, 0f, 0f));
        m.SetFloat("_Cutoff", 0.5f);
        // Leaves, needles, moss and thin stems let light through; stone, wood, ice, ash, mud and metal ground cover do not
        bool opaque = GroundCover(src.name) && !Leafy(src.name);
        m.SetFloat("_Translucency", opaque ? 0f : 2f);
        m.SetFloat("_TransNormalDistortion", 0.1f);
        m.SetFloat("_TransScattering", 2f);
        m.SetFloat("_TransDirect", opaque ? 0f : 1f);
        m.SetFloat("_TransAmbient", opaque ? 0f : 0.2f);
        m.SetFloat("_TransShadow", 1f);
        // Two-sided meshes cull their back faces; solid ones draw both sides of their few thin bits
        m.SetFloat("_Cull", Solid(src.name) ? 0f : 2f);
        m.SetFloat("_WindStartY", 0f);
        m.SetFloat("_WindStrength", Wind(src.name));
        m.renderQueue = 2450;
        return m;
    }

    /// <summary>Plants built as solid shapes (cactus bodies, mushroom caps, a log): drawn as modelled, both sides,
    /// rather than doubled into two-sided sheets. Matches NatureShaderDEM.Solid.</summary>
    public static bool Solid(string plant)
    {
        switch (plant)
        {
            case "BarrelCactus": case "MossyLog": case "Bolete": case "FlyAgaric": case "Morels":
                return true;
            default:
                return false;
        }
    }

    /// <summary>The ground cover (walk-through patches lying on the ground: leaf litter, stones, ash, ...), built into
    /// their own bundle with their textures kept at the size they were baked at. Matches NatureShaderDEM.GroundCover.</summary>
    public static bool GroundCover(string plant)
    {
        switch (plant)
        {
            case "PineNeedleMat": case "BirchLeafLitter": case "MapleLeafLitter": case "OakLeafLitter": case "MossPatch":
            case "TwigPile": case "PineconeCluster": case "AcornScatter": case "LichenStone": case "PebblesA":
            case "PebblesB": case "PebblesC": case "FlatStones": case "Driftwood": case "RiverStones": case "CrackedMud":
            case "ShaleChips": case "BleachedBranch": case "IceCrust": case "FrostHeavedStones": case "AshPatch":
            case "CharredSticks": case "GravelPatch": case "RustFlakes": case "DeadTumbleweed":
                return true;
            default:
                return false;
        }
    }

    /// <summary>Ground cover made of leaves, needles, moss and thin stems (lets light through). Matches
    /// NatureShaderDEM.Leafy.</summary>
    public static bool Leafy(string plant)
    {
        switch (plant)
        {
            case "PineNeedleMat": case "BirchLeafLitter": case "MapleLeafLitter": case "OakLeafLitter": case "MossPatch":
            case "AcornScatter": case "DeadTumbleweed":
                return true;
            default:
                return false;
        }
    }

    /// <summary>How hard the wind sways a plant: woody and fleshy ones barely, mushrooms and logs not at all. Matches
    /// NatureShaderDEM.Wind.</summary>
    public static float Wind(string plant)
    {
        if (GroundCover(plant))
        {
            return plant == "DeadTumbleweed" ? 0.25f : 0f;
        }
        switch (plant)
        {
            case "MossyLog": case "FlyAgaric": case "Bolete": case "Morels": case "BarrelCactus": case "PricklyPear":
                return 0f;
            case "Sagebrush": case "FrostedJuniper": case "AgaveBloom": case "DeadBrush": case "CharredShrub":
            case "WildRose": case "Elderberry": case "Sumac": case "Winterberry": case "Ocotillo":
                return 0.4f;
            default:
                return 1f;
        }
    }

    // ------------------------------------------------------------------ previews

    private static void Previews(List<string> render, List<string> all, string output)
    {
        Directory.CreateDirectory(output);
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = GameBundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            AssetBundle plants = loaded.FirstOrDefault(b => b.GetAllAssetNames().Any(n => n.ToLowerInvariant().Contains("plantcotton")));
            string cottonName = plants?.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("plantcottonharvestprefab.prefab"));
            GameObject cotton = cottonName != null ? plants.LoadAsset<GameObject>(cottonName) : null;
            Shader shader = cotton != null ? cotton.GetComponentInChildren<MeshRenderer>(true).sharedMaterial.shader : null;
            if (shader == null || shader.name != GameShader)
            {
                Debug.LogError("[NatureBuilder] could not load the game's plant shader; previews skipped");
                return;
            }
            Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
            GameObject Spawn(string prefab, Vector3 at, float turn)
            {
                GameObject go = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(prefab));
                foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                {
                    Material src = r.sharedMaterial;
                    if (!converted.TryGetValue(src, out Material dst))
                    {
                        dst = ToGame(shader, src);
                        converted[src] = dst;
                    }
                    r.sharedMaterial = dst;
                }
                go.transform.position = at;
                go.transform.rotation = Quaternion.Euler(0f, turn, 0f);
                return go;
            }

            foreach (string prefab in render)
            {
                string name = Path.GetFileNameWithoutExtension(prefab);
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                converted.Clear();
                Stage(18f);
                Bounds b = AssetDatabase.LoadAssetAtPath<GameObject>(prefab).GetComponentInChildren<MeshRenderer>().bounds;
                float size = Mathf.Max(1f, b.size.y, b.size.x * 0.8f);
                // Up close, with vanilla cotton beside it for scale
                Spawn(prefab, Vector3.zero, 20f);
                Object.Instantiate(cotton, (GroundCover(name) ? new Vector3(-0.8f, 0f, 0.5f) : new Vector3(-0.6f - size * 0.6f, 0f, 0.4f)), Quaternion.identity);
                // A drift behind: the plant on most blocks of a 7 x 5 patch, each turned at random
                System.Random rnd = new System.Random(name.GetHashCode());
                for (int x = -3; x <= 3; x++)
                {
                    for (int z = 0; z < 5; z++)
                    {
                        if (rnd.NextDouble() < 0.75)
                        {
                            Spawn(prefab, new Vector3(x * Mathf.Max(1f, Mathf.Round(size * 0.7f)), 0f, 4f + z * Mathf.Max(1f, Mathf.Round(size * 0.7f))),
                                (float)rnd.NextDouble() * 360f);
                        }
                    }
                }
                const int width = 1100, height = 900;
                Texture2D sheet = new Texture2D(width * 2, height, TextureFormat.RGB24, false);
                Texture2D close = GroundCover(name)
                    ? Shot(new Vector3(0.45f, 0.62f, -1.05f), new Vector3(-0.1f, -0.44f, 0f), 50f, width, height)
                    : Shot(new Vector3(0.9f, 0.35f + size * 0.55f, -1.9f) * Mathf.Max(1f, size * 0.85f),
                        new Vector3(0f, -0.5f + size * 0.4f, 0f), 38f, width, height);
                Texture2D drift = Shot(new Vector3(2f, 2.6f, -6f) * Mathf.Max(1f, size * 0.6f), new Vector3(0f, -0.3f, 6f), 45f, width, height);
                sheet.SetPixels(0, 0, width, height, close.GetPixels());
                sheet.SetPixels(width, 0, width, height, drift.GetPixels());
                File.WriteAllBytes(Path.Combine(output, name + ".png"), sheet.EncodeToPNG());
                Debug.Log("[NatureBuilder] Wrote " + name + ".png");
            }

            // Contact sheets: each plant framed on its own, its near mesh beside its far mesh (which is what most of a
            // drift shows), four plants a row, 24 a sheet, in name order
            const int tile = 300, perRow = 4, perSheet = 24;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            // Materials converted before a new scene lose their shader
            converted.Clear();
            Stage(8f);
            for (int s = 0; s * perSheet < all.Count; s++)
            {
                List<string> batch = all.Skip(s * perSheet).Take(perSheet).ToList();
                int rows = (batch.Count + perRow - 1) / perRow;
                Texture2D sheet = new Texture2D(tile * 2 * perRow, tile * rows, TextureFormat.RGB24, false);
                sheet.SetPixels(Enumerable.Repeat(new Color(0.15f, 0.15f, 0.15f), sheet.width * sheet.height).ToArray());
                for (int i = 0; i < batch.Count; i++)
                {
                    GameObject go = Spawn(batch[i], Vector3.zero, 30f);
                    LODGroup group = go.GetComponent<LODGroup>();
                    Bounds b = go.GetComponentInChildren<MeshRenderer>().bounds;
                    float r = Mathf.Max(b.extents.x, b.extents.y, b.extents.z);
                    Vector3 eye = b.center + new Vector3(0.55f, 0.45f, -1f).normalized * r * 3.4f;
                    int x0 = i % perRow * tile * 2, y0 = (rows - 1 - i / perRow) * tile;
                    for (int lod = 0; lod < 2; lod++)
                    {
                        group.ForceLOD(Mathf.Min(lod, group.lodCount - 1));
                        sheet.SetPixels(x0 + lod * tile, y0, tile, tile, Shot(eye, b.center, 35f, tile, tile).GetPixels());
                    }
                    Object.DestroyImmediate(go);
                }
                File.WriteAllBytes(Path.Combine(output, "contact-" + (s + 1) + ".png"), sheet.EncodeToPNG());
            }
        }
        finally
        {
            foreach (AssetBundle bundle in loaded)
            {
                bundle.Unload(true);
            }
        }
    }

    /// <summary>Afternoon sun and sky over a patch of grassy ground (the plant shader is lit like the game's
    /// deferred models).</summary>
    internal static void Stage(float extent)
    {
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.94f, 0.85f);
        sun.intensity = 1.3f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(42f, -35f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.45f, 0.52f, 0.62f);
        RenderSettings.ambientEquatorColor = new Color(0.36f, 0.37f, 0.33f);
        RenderSettings.ambientGroundColor = new Color(0.16f, 0.16f, 0.12f);
        RenderSettings.fog = false;
        Camera probe = new GameObject("ProbeCam").AddComponent<Camera>();
        probe.clearFlags = CameraClearFlags.SolidColor;
        probe.backgroundColor = new Color(0.55f, 0.64f, 0.76f);
        probe.cullingMask = 0;
        Cubemap sky = new Cubemap(64, TextureFormat.RGBAHalf, false);
        probe.RenderToCubemap(sky);
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
        RenderSettings.customReflectionTexture = sky;
        Object.DestroyImmediate(probe.gameObject);
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.transform.position = new Vector3(0f, -0.5f, extent * 0.4f);
        ground.transform.localScale = new Vector3(extent / 5f, 1f, extent / 5f);
        ground.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard"))
        {
            color = new Color(0.2f, 0.22f, 0.12f),
        };
    }

    internal static Texture2D Shot(Vector3 from, Vector3 at, float fov, int width, int height)
    {
        Camera camera = new GameObject("ShotCam").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.55f, 0.64f, 0.76f);
        camera.fieldOfView = fov;
        camera.farClipPlane = 200f;
        camera.transform.position = from;
        camera.transform.LookAt(at);
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        Object.DestroyImmediate(camera.gameObject);
        target.Release();
        return read;
    }
}
