using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Solid natural features (boulders, rock formations, cairns, bones; see FEATURES.md): turns the Blender exports in
/// Assets/NatureExpanded/Features/&lt;Name&gt;/ (Name.fbx with the meshes Name and Name_LOD1, the baked
/// Name_Albedo/_Normal/_RMOM maps, and Name_colliders.txt) into block prefabs, builds them into
/// Build/features-bundle/natureexpanded-features.unity3d, writes Build/feature-sizes.txt for gen_nature.py, checks
/// every collider against its mesh, and renders Build/features/&lt;Name&gt;.png (the model in the game's own shader beside
/// vanilla's boulder and a 1.8 m figure) and &lt;Name&gt;_colliders.png (the model beside its colliders).
/// Run from src/build-features.bat. "-features A,B" renders only those features' previews.
///
/// Prefab layout (what the game's ModelEntity block expects, as vanilla's boulders): the root is on layer 16 with the
/// LODGroup and NO collider of its own (a collider on the root would become the block's one AABB, see FEATURES.md);
/// each LOD is a child at y = -0.5 whose mesh has its origin on the ground; "Colliders" holds one child per
/// collider line of the sidecar (convex primitives only). The game moves every collider to its movement layer when the
/// block has Collide movement, and BlockFeatureDEM tags them T_Block so harvesting finds the block.
/// The sidecar's lines are in Blender's coordinates (meters, Z up, the block center at the origin, the ground at
/// z = -0.5): box cx cy cz sx sy sz [ux uy uz vx vy vz wx wy wz] (the box's own axes in Blender), sphere cx cy cz r,
/// capsule x1 y1 z1 x2 y2 z2 r, probe x y z dx dy dz (a ray that must hit nothing: the opening of an arch).
/// </summary>
public static class NatureFeatureBuilder
{
    private const string BundleName = "natureexpanded-features.unity3d";
    private const string Features = "Assets/NatureExpanded/Features";
    private const string Prefabs = "Assets/NatureExpanded/FeaturePrefabs";
    private const string GameShader = "Game/EntityTintMaskSSS";
    private static int maxTexture = 2048;
    private static bool rectangular;

    private static readonly string[] GameBundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "automatic_assets_entities/plants.bundle", "automatic_assets_entities/minerals.bundle",
    };

    private class Collider3
    {
        public string Kind;
        public float[] V;
    }

    /// <summary>Blender's coordinates to the prefab's: the FBX importer turns (x, y, z) into (-x, z, -y).</summary>
    private static Vector3 B(float x, float y, float z)
    {
        return new Vector3(-x, z, -y);
    }

    public static void Build()
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
            AssetDatabase.CreateFolder("Assets/NatureExpanded", "FeaturePrefabs");
        }
        string[] args = System.Environment.GetCommandLineArgs();
        int only = System.Array.IndexOf(args, "-features");
        HashSet<string> wanted = only >= 0 && only + 1 < args.Length ? new HashSet<string>(args[only + 1].Split(',')) : null;

        List<string> prefabs = new List<string>();
        List<string> problems = new List<string>();
        List<string> sizes = new List<string>();
        if (Directory.Exists(Features))
        {
            foreach (string dir in Directory.GetDirectories(Features).OrderBy(d => d))
            {
                string name = Path.GetFileName(dir);
                if (!File.Exists(Features + "/" + name + "/" + name + ".fbx"))
                {
                    Debug.LogWarning("[NatureFeatureBuilder] " + name + ": no FBX yet; skipped");
                    continue;
                }
                string prefab = MakePrefab(Features + "/" + name, name, problems, sizes);
                if (prefab != null)
                {
                    prefabs.Add(prefab);
                }
            }
        }
        AssetDatabase.SaveAssets();
        foreach (string p in problems)
        {
            Debug.LogError("[NatureFeatureBuilder] PROBLEM " + p);
        }
        if (problems.Count > 0)
        {
            throw new System.Exception(problems.Count + " feature problems; see the log above");
        }

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        string bundleDir = Path.Combine(output, "features-bundle");
        Directory.CreateDirectory(bundleDir);
        File.WriteAllLines(Path.Combine(output, "feature-sizes.txt"), sizes);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = prefabs.ToArray() };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(bundleDir, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode
                | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[NatureFeatureBuilder] Built " + Path.Combine(bundleDir, BundleName) + " with " + prefabs.Count + " features");

        Previews(prefabs.Where(p => wanted == null || wanted.Contains(Path.GetFileNameWithoutExtension(p))).ToList(),
            Path.Combine(output, "features"));
    }

    // ------------------------------------------------------------------ prefabs

    private static List<Collider3> ReadColliders(string folder, string name, List<string> problems, List<float[]> probes)
    {
        List<Collider3> list = new List<Collider3>();
        string path = folder + "/" + name + "_colliders.txt";
        if (!File.Exists(path))
        {
            problems.Add(name + ": no " + path + " (a feature needs at least one collider)");
            return list;
        }
        foreach (string raw in File.ReadAllLines(path))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#"))
            {
                continue;
            }
            string[] p = line.Split(new[] { ' ', '\t' }, System.StringSplitOptions.RemoveEmptyEntries);
            float[] v = p.Skip(1).Select(s => float.Parse(s, CultureInfo.InvariantCulture)).ToArray();
            switch (p[0])
            {
                case "box": if (v.Length == 6 || v.Length == 15) { list.Add(new Collider3 { Kind = "box", V = v }); continue; } break;
                case "sphere": if (v.Length == 4) { list.Add(new Collider3 { Kind = "sphere", V = v }); continue; } break;
                case "capsule": if (v.Length == 7) { list.Add(new Collider3 { Kind = "capsule", V = v }); continue; } break;
                case "probe": if (v.Length == 6) { probes.Add(v); continue; } break;
                case "texture": if (v.Length == 1) { maxTexture = Mathf.Clamp((int)v[0], 256, 2048); continue; } break;
                case "rect": if (v.Length == 0) { rectangular = true; continue; } break;
            }
            problems.Add(name + ": bad collider line \"" + line + "\"");
        }
        if (list.Count == 0)
        {
            problems.Add(name + ": " + path + " has no colliders");
        }
        return list;
    }

    private static string MakePrefab(string folder, string name, List<string> problems, List<string> sizes)
    {
        maxTexture = 1024;
        rectangular = false;
        List<float[]> probes = new List<float[]>();
        List<Collider3> colliders = ReadColliders(folder, name, problems, probes);
        if (colliders.Count == 0)
        {
            return null;
        }
        foreach (string path in Directory.GetFiles(folder, name + "_*.png").Select(p => p.Replace('\\', '/')))
        {
            ConfigureTexture(path);
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
            Mesh mesh = Grounded(f, source.transform, Prefabs + "/" + f.name + ".asset");
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
            Debug.LogWarning("[NatureFeatureBuilder] " + name + ": no " + name + "_LOD1 mesh; one LOD only");
        }
        // Full detail down to 10% of the screen's height, the far mesh to 1%, then gone (the game rescales these by
        // the group's size, as for its own models)
        LODGroup group = root.AddComponent<LODGroup>();
        group.SetLODs(lods.Count > 1
            ? new[] { new LOD(0.10f, new[] { lods[0] }), new LOD(0.01f, new[] { lods[1] }) }
            : new[] { new LOD(0.01f, new[] { lods[0] }) });
        group.RecalculateBounds();
        root.layer = 16;

        GameObject holder = new GameObject("Colliders");
        holder.transform.SetParent(root.transform, false);
        holder.layer = 16;
        int n = 0;
        foreach (Collider3 c in colliders)
        {
            if (c.Kind == "box" && c.V.Length == 6)
            {
                BoxCollider shared = holder.AddComponent<BoxCollider>();
                shared.center = B(c.V[0], c.V[1], c.V[2]);
                shared.size = new Vector3(c.V[3], c.V[5], c.V[4]);
                continue;
            }
            if (c.Kind == "sphere")
            {
                SphereCollider shared = holder.AddComponent<SphereCollider>();
                shared.center = B(c.V[0], c.V[1], c.V[2]);
                shared.radius = c.V[3];
                continue;
            }
            GameObject go = new GameObject("Col" + n++);
            go.transform.SetParent(holder.transform, false);
            go.layer = 16;
            float[] v = c.V;
            if (c.Kind == "box")
            {
                BoxCollider box = go.AddComponent<BoxCollider>();
                go.transform.localPosition = B(v[0], v[1], v[2]);
                if (v.Length == 15)
                {
                    Vector3 u = B(v[6], v[7], v[8]), vv = B(v[9], v[10], v[11]);
                    Vector3 w = Vector3.Cross(u, vv);
                    go.transform.localRotation = Quaternion.LookRotation(w, vv);
                }
                // Sizes run along the box's own axes: its Blender x, y, z are the prefab's -x, -z, y when unrotated
                box.size = v.Length == 15 ? new Vector3(v[3], v[4], v[5]) : new Vector3(v[3], v[5], v[4]);
            }
            else if (c.Kind == "sphere")
            {
                go.transform.localPosition = B(v[0], v[1], v[2]);
                go.AddComponent<SphereCollider>().radius = v[3];
            }
            else
            {
                Vector3 a = B(v[0], v[1], v[2]), b = B(v[3], v[4], v[5]);
                go.transform.localPosition = (a + b) * 0.5f;
                go.transform.localRotation = Quaternion.FromToRotation(Vector3.up, (b - a).normalized);
                CapsuleCollider cap = go.AddComponent<CapsuleCollider>();
                cap.direction = 1;
                cap.radius = v[6];
                cap.height = (b - a).magnitude + 2f * v[6];
            }
        }

        // Footprint, from the mesh and the colliders in the prefab's coordinates (ground at y = -0.5): the block is
        // an odd number of cells across (the master cell centered, so a quarter turn leaves it where it was) and as
        // many tall as it takes
        Bounds mb = lods[0].bounds;
        Bounds all = mb;
        foreach (UnityEngine.Collider col in root.GetComponentsInChildren<UnityEngine.Collider>(true))
        {
            all.Encapsulate(col.bounds);
        }
        // A feature may be a rectangle (a windfall's long trunk): the game rotates a multi-block's child offsets with the
        // block (Block.MultiBlockArray.Get), so an odd-by-odd rectangle stays centered at any quarter turn. Only a
        // feature whose sidecar has a "rect" line gets one; the rest keep the rocks' square footprint.
        float halfX = Mathf.Max(Mathf.Abs(all.min.x), Mathf.Abs(all.max.x));
        float halfZ = Mathf.Max(Mathf.Abs(all.min.z), Mathf.Abs(all.max.z));
        int acrossX = 2 * Mathf.Max(0, Mathf.CeilToInt(halfX - 0.5f - 0.02f)) + 1;
        int acrossZ = 2 * Mathf.Max(0, Mathf.CeilToInt(halfZ - 0.5f - 0.02f)) + 1;
        if (!rectangular)
        {
            acrossX = acrossZ = Mathf.Max(acrossX, acrossZ);
        }
        int across = Mathf.Max(acrossX, acrossZ);
        int height = Mathf.Clamp(Mathf.CeilToInt(all.max.y + 0.5f - 0.02f), 1, 30);
        sizes.Add(name + " " + acrossX + " " + height + " " + acrossZ + " " + mb.size.x.ToString("F2", CultureInfo.InvariantCulture)
            + " " + mb.size.y.ToString("F2", CultureInfo.InvariantCulture) + " " + mb.size.z.ToString("F2", CultureInfo.InvariantCulture));
        string prefabPath = Prefabs + "/" + name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Check(root, name, mb, probes, problems, across, height);
        Debug.Log("[NatureFeatureBuilder] " + name + " mesh bounds " + mb.center.ToString("F2") + " size " + mb.size.ToString("F2") + ", "
            + colliders.Count + " colliders, block " + acrossX + "x" + height + "x" + acrossZ + ", "
            + ((MeshRenderer)lods[0]).GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3 + " triangles near, "
            + (lods.Count > 1 ? ((MeshRenderer)lods[1]).GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3 : 0) + " far");
        Object.DestroyImmediate(root);
        return prefabPath;
    }

    /// <summary>The collider check: every collider must sit inside the mesh's bounds (a few cm of slack), the mesh must
    /// not leave the block's footprint, and each probe ray (an arch's opening) must hit nothing. Raycasts against the
    /// colliders of a prefab instance in the open scene; the model is tested at its four quarter turns.</summary>
    private static void Check(GameObject prefabRoot, string name, Bounds mesh, List<float[]> probes, List<string> problems, int across, int height)
    {
        GameObject inst = Object.Instantiate(prefabRoot);
        inst.transform.position = new Vector3(0f, 100f, 0f);
        Physics.autoSyncTransforms = true;
        Physics.SyncTransforms();
        Bounds mb = new Bounds(mesh.center + inst.transform.position, mesh.size);
        mb.Expand(0.06f);
        StringBuilder sb = new StringBuilder();
        int count = 0;
        foreach (UnityEngine.Collider c in inst.GetComponentsInChildren<UnityEngine.Collider>(true))
        {
            Bounds cb = c.bounds;
            // Below the ground is the skirt: ignore
            bool inside = cb.min.x >= mb.min.x && cb.max.x <= mb.max.x && cb.min.z >= mb.min.z && cb.max.z <= mb.max.z && cb.max.y <= mb.max.y;
            if (!inside)
            {
                sb.AppendLine("    " + c.gameObject.name + " " + c.GetType().Name + " bounds " + (cb.center - inst.transform.position).ToString("F2")
                    + " size " + cb.size.ToString("F2") + "  OUTSIDE the mesh bounds");
            }
            count++;
            if (!inside)
            {
                Debug.LogWarning("[NatureFeatureBuilder] " + name + ": " + c.gameObject.name + " reaches outside the mesh's bounds");
            }
        }
        foreach (float[] p in probes)
        {
            Vector3 o = inst.transform.position + B(p[0], p[1], p[2]);
            Vector3 d = B(p[3], p[4], p[5]).normalized;
            bool hit = Physics.Raycast(o - d * 8f, d, out RaycastHit h, 16f);
            sb.AppendLine("    probe " + o.ToString("F2") + " dir " + d.ToString("F2") + (hit ? "  BLOCKED by " + h.collider.name + " at " + h.distance.ToString("F2") : "  clear"));
            if (hit)
            {
                problems.Add(name + ": the opening is blocked (probe from " + new Vector3(p[0], p[1], p[2]) + ") by " + h.collider.name);
            }
        }
        float reach = Mathf.Max(Mathf.Abs(mesh.min.x), Mathf.Abs(mesh.max.x), Mathf.Abs(mesh.min.z), Mathf.Abs(mesh.max.z));
        sb.AppendLine("    " + count + " colliders");
        sb.AppendLine("    mesh reaches " + reach.ToString("F2") + " m from the center; block is " + across + " wide (" + (across / 2f).ToString("F1") + " to a side)");
        Debug.Log("[NatureFeatureBuilder] collider check " + name + "\n" + sb);
        Object.DestroyImmediate(inst);
    }

    private static Mesh Grounded(MeshFilter filter, Transform fbxRoot, string path)
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
        Mesh mesh = new Mesh { name = filter.name };
        mesh.indexFormat = v.Length > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
        mesh.vertices = v;
        mesh.normals = n;
        if (t.Length > 0)
        {
            mesh.tangents = t;
        }
        mesh.uv = src.uv;
        mesh.triangles = src.triangles;
        mesh.RecalculateBounds();
        mesh.UploadMeshData(false);
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(mesh, path);
        return mesh;
    }

    private static void ConfigureTexture(string path)
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
        // Rocks are looked at from an arm's length and along their sides
        importer.anisoLevel = 8;
        importer.maxTextureSize = maxTexture;
        importer.textureCompression = TextureImporterCompression.Compressed;
        importer.SaveAndReimport();
    }

    /// <summary>The RMOM map with its alpha cleared (the plant shader reads that alpha as a tint mask), as a texture of
    /// its own in FeaturePrefabs.</summary>
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
        ConfigureTexture(path);
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    /// <summary>A Standard material carrying the maps; the mod moves it to the game's plant shader as the block spawns
    /// (NatureShaderDEM). Its name starts "Feature_": that is how the DLL knows a solid, closed, windless, non
    /// translucent surface from a plant.</summary>
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
        material.name = "Feature_" + name;
        Texture2D Tex(string suffix) => AssetDatabase.LoadAssetAtPath<Texture2D>(folder + "/" + name + "_" + suffix + ".png");
        material.SetTexture("_MainTex", Tex("Albedo"));
        material.SetTexture("_BumpMap", Tex("Normal"));
        material.EnableKeyword("_NORMALMAP");
        material.SetTexture("_DetailMask", Unmasked(folder, name));
        material.SetFloat("_Glossiness", 0.2f);
        EditorUtility.SetDirty(material);
        return material;
    }

    /// <summary>The material in the game's plant shader, as NatureShaderDEM.Convert does for a "Feature_" material.</summary>
    public static Material ToGame(Shader game, Material src)
    {
        Material m = new Material(game) { name = src.name + " (game)" };
        m.SetTexture("_Albedo", src.GetTexture("_MainTex"));
        m.SetTexture("_Normal", src.GetTexture("_BumpMap"));
        m.SetTexture("_RMOM", src.GetTexture("_DetailMask"));
        m.SetColor("_TintColor", new Color(1f, 1f, 1f, 0f));
        m.SetColor("_SSSColor", new Color(0f, 0f, 0f, 0f));
        m.SetFloat("_Cutoff", 0.5f);
        m.SetFloat("_Translucency", 0f);
        m.SetFloat("_TransNormalDistortion", 0.1f);
        m.SetFloat("_TransScattering", 2f);
        m.SetFloat("_TransDirect", 0f);
        m.SetFloat("_TransAmbient", 0f);
        m.SetFloat("_TransShadow", 1f);
        m.SetFloat("_Cull", 2f);
        m.SetFloat("_WindStartY", 0f);
        m.SetFloat("_WindStrength", 0f);
        m.renderQueue = 2450;
        return m;
    }

    // ------------------------------------------------------------------ previews

    private static void Previews(List<string> render, string output)
    {
        Directory.CreateDirectory(output);
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = GameBundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            AssetBundle plants = loaded.FirstOrDefault(b => b.GetAllAssetNames().Any(n => n.ToLowerInvariant().Contains("plantcotton")));
            string cottonName = plants?.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("plantcottonharvestprefab.prefab"));
            Shader shader = cottonName != null ? plants.LoadAsset<GameObject>(cottonName).GetComponentInChildren<MeshRenderer>(true).sharedMaterial.shader : null;
            if (shader == null || shader.name != GameShader)
            {
                Debug.LogError("[NatureFeatureBuilder] could not load the game's plant shader; previews skipped");
                return;
            }
            AssetBundle minerals = loaded.FirstOrDefault(b => b.GetAllAssetNames().Any(n => n.ToLowerInvariant().Contains("resourcerock01prefab")));
            string rockName = minerals?.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("resourcerock01prefab.prefab"));
            GameObject vanillaRock = rockName != null ? minerals.LoadAsset<GameObject>(rockName) : null;
            Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
            Material figure = null;
            foreach (string prefab in render)
            {
                string name = Path.GetFileNameWithoutExtension(prefab);
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                converted.Clear();
                NatureBuilder.Stage(60f);
                // Grazing sun on a big flat face shows shadow acne with Unity's default biases; the game's lights are tuned
                Light sun = GameObject.Find("Sun").GetComponent<Light>();
                sun.shadowBias = 0.12f;
                sun.shadowNormalBias = 1.2f;
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
                go.transform.rotation = Quaternion.Euler(0f, 20f, 0f);
                Bounds b = go.GetComponentInChildren<MeshRenderer>().bounds;
                float size = Mathf.Max(2f, b.size.y, b.size.x, b.size.z);
                // A 1.8 m figure to scale, and vanilla's boulder
                GameObject person = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                person.transform.localScale = new Vector3(0.5f, 0.9f, 0.5f);
                person.transform.position = new Vector3(b.max.x + 1.2f, -0.5f + 0.9f, -b.extents.z * 0.4f);
                Object.DestroyImmediate(person.GetComponent<UnityEngine.Collider>());
                if (figure == null)
                {
                    figure = new Material(Shader.Find("Standard")) { color = new Color(0.8f, 0.35f, 0.15f) };
                }
                person.GetComponent<Renderer>().sharedMaterial = figure;
                if (vanillaRock != null)
                {
                    GameObject vr = Object.Instantiate(vanillaRock, new Vector3(b.min.x - 2.8f - size * 0.2f, -0.5f + 0.28f, 0f), Quaternion.identity);
                    foreach (Collider c in vr.GetComponentsInChildren<UnityEngine.Collider>()) { c.enabled = false; }
                }
                const int width = 1100, height = 800;
                Vector3 center = b.center;
                Texture2D sheet = new Texture2D(width * 2, height * 2, TextureFormat.RGB24, false);
                float d = size * 1.9f + 3f;
                Texture2D a = NatureBuilder.Shot(center + new Vector3(0.6f, 0.25f, -1f).normalized * d, center, 38f, width, height);
                Texture2D c2 = NatureBuilder.Shot(center + new Vector3(-0.9f, 0.55f, -0.7f).normalized * d, center, 38f, width, height);
                Texture2D e = NatureBuilder.Shot(new Vector3(center.x + 1.5f, 1.2f, center.z - Mathf.Max(3f, size * 0.7f)), center + Vector3.up * 0.3f, 62f, width, height);
                Texture2D f = NatureBuilder.Shot(center + new Vector3(0.1f, 1.6f, -0.5f).normalized * d * 1.1f, center, 38f, width, height);
                sheet.SetPixels(0, height, width, height, a.GetPixels());
                sheet.SetPixels(width, height, width, height, c2.GetPixels());
                sheet.SetPixels(0, 0, width, height, e.GetPixels());
                sheet.SetPixels(width, 0, width, height, f.GetPixels());
                File.WriteAllBytes(Path.Combine(output, name + ".png"), sheet.EncodeToPNG());

                // Diagnostics: the same view with the game shader but no normal map, with RMOM occlusion cleared, and plain Standard
                if (System.Environment.GetEnvironmentVariable("NF_DEBUG") != null)
                {
                    Texture2D[] dbgShots = new Texture2D[3];
                    for (int mode = 0; mode < 3; mode++)
                    {
                        foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                        {
                            Material src0 = AssetDatabase.LoadAssetAtPath<GameObject>(prefab).GetComponentInChildren<MeshRenderer>().sharedMaterial;
                            Material m2;
                            if (mode == 2)
                            {
                                m2 = new Material(Shader.Find("Standard"));
                                m2.SetTexture("_MainTex", src0.GetTexture("_MainTex"));
                            }
                            else
                            {
                                m2 = ToGame(shader, src0);
                                if (mode == 0) { m2.SetTexture("_Normal", null); }
                                else { Texture2D white = new Texture2D(2, 2); white.SetPixels(new[] { Color.white, Color.white, Color.white, Color.white }); white.Apply(); m2.SetTexture("_RMOM", white); }
                            }
                            r.sharedMaterial = m2;
                        }
                        dbgShots[mode] = NatureBuilder.Shot(center + new Vector3(-0.9f, 0.55f, -0.7f).normalized * d, center, 38f, width, height);
                    }
                    Texture2D ds = new Texture2D(width * 3, height, TextureFormat.RGB24, false);
                    for (int mode = 0; mode < 3; mode++) { ds.SetPixels(mode * width, 0, width, height, dbgShots[mode].GetPixels()); }
                    File.WriteAllBytes(Path.Combine(output, name + "_debug.png"), ds.EncodeToPNG());
                }

                // The colliders beside the model: solid flat color, front and side
                GameObject twin = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(prefab));
                foreach (MeshRenderer r in twin.GetComponentsInChildren<MeshRenderer>(true)) { r.enabled = false; }
                float shift = Mathf.Max(b.size.x, b.size.z) * 1.15f + 0.5f;
                twin.transform.position = new Vector3(shift, 0f, 0f);
                Material flat = new Material(Shader.Find("Unlit/Color")) { color = new Color(0.9f, 0.4f, 0.1f) };
                foreach (UnityEngine.Collider col in twin.GetComponentsInChildren<UnityEngine.Collider>(true))
                {
                    PrimitiveType type = col is BoxCollider ? PrimitiveType.Cube : col is SphereCollider ? PrimitiveType.Sphere : PrimitiveType.Capsule;
                    GameObject prim = GameObject.CreatePrimitive(type);
                    Object.DestroyImmediate(prim.GetComponent<UnityEngine.Collider>());
                    prim.GetComponent<Renderer>().sharedMaterial = flat;
                    prim.transform.SetParent(col.transform, false);
                    if (col is BoxCollider bc) { prim.transform.localPosition = bc.center; prim.transform.localScale = bc.size; }
                    else if (col is SphereCollider sc) { prim.transform.localPosition = sc.center; prim.transform.localScale = Vector3.one * sc.radius * 2f; }
                    else if (col is CapsuleCollider cc) { prim.transform.localPosition = cc.center; prim.transform.localScale = new Vector3(cc.radius * 2f, cc.height * 0.5f, cc.radius * 2f); }
                }
                Vector3 mid = new Vector3(shift * 0.5f, b.center.y, 0f);
                float wide = shift + size;
                Texture2D g1 = NatureBuilder.Shot(mid + new Vector3(0f, 0.2f, -1f).normalized * (wide * 1.35f + 3f), mid, 40f, width, height);
                Texture2D g2 = NatureBuilder.Shot(mid + new Vector3(0f, 1.2f, -1f).normalized * (wide * 1.35f + 3f), mid, 40f, width, height);
                Texture2D cs = new Texture2D(width * 2, height, TextureFormat.RGB24, false);
                cs.SetPixels(0, 0, width, height, g1.GetPixels());
                cs.SetPixels(width, 0, width, height, g2.GetPixels());
                File.WriteAllBytes(Path.Combine(output, name + "_colliders.png"), cs.EncodeToPNG());
                Debug.Log("[NatureFeatureBuilder] Wrote " + name + ".png and " + name + "_colliders.png");
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
}
