using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Turns the Blender exports in Assets/TrapsExpanded/&lt;Trap&gt;/ into game prefabs and builds them into one asset
/// bundle, then renders each prefab with the Standard shader to Build/&lt;Trap&gt;-preview.png. Run from
/// src/build-models.bat (batch mode with graphics, for the preview).
///
/// Each trap folder holds &lt;Trap&gt;.fbx and, for every material M the FBX uses, the textures M_Albedo, M_Normal,
/// M_RMOM (roughness, metallic, occlusion, mask: the packed map of the game's model shader) and optionally
/// M_Emission. The materials are Standard ones that carry the RMOM map in their unused _DetailMask slot; the mod
/// switches them to the game's own shader (Game/Entity Tint Mask) when a block spawns, like the vanilla traps use.
/// The prefab root carries a BoxCollider around the model (the game reads the block's bounds from it); tags and
/// layers are set by the mod's C# when the block spawns, because a bundle stores tags as indexes into this
/// project's tag list.
/// </summary>
public static class TrapsBuilder
{
    private const string BundleName = "trapsexpanded.unity3d";
    private const string Root = "Assets/TrapsExpanded";

    private static readonly string[] Traps = { "TeslaCoil" };

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

        List<string> prefabs = new List<string>();
        foreach (string trap in Traps)
        {
            prefabs.Add(MakePrefab(trap));
        }

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = prefabs.ToArray() };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode
                | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[TrapsBuilder] Built " + Path.Combine(output, BundleName));

        foreach (string trap in Traps)
        {
            VanillaCompare.Preview(Root + "/" + trap + "/" + trap + ".prefab", Path.Combine(output, trap + "-preview.png"));
        }
    }

    private static string MakePrefab(string trap)
    {
        string folder = Root + "/" + trap;
        foreach (string path in Directory.GetFiles(folder, "*.png"))
        {
            ConfigureTexture(path.Replace('\\', '/'));
        }

        string fbx = folder + "/" + trap + ".fbx";
        ModelImporter model = (ModelImporter)AssetImporter.GetAtPath(fbx);
        model.globalScale = 1f;
        model.useFileScale = true;
        model.importNormals = ModelImporterNormals.Import;
        model.importTangents = ModelImporterTangents.CalculateMikk;
        model.animationType = ModelImporterAnimationType.None;
        model.importAnimation = false;
        model.importCameras = false;
        model.importLights = false;
        model.isReadable = false;
        model.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        model.materialLocation = ModelImporterMaterialLocation.InPrefab;
        model.SaveAndReimport();

        // Swap each FBX material for a Standard material built from the baked textures of the same name
        // (once remapped, the FBX's own materials only show up in the importer's remap list)
        string[] names = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Material>().Select(m => m.name)
            .Concat(model.GetExternalObjectMap().Keys.Where(k => k.type == typeof(Material)).Select(k => k.name))
            .Distinct().ToArray();
        foreach (string name in names)
        {
            model.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), name), MakeMaterial(folder, name));
        }
        model.SaveAndReimport();

        GameObject root = new GameObject(trap);
        GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
        PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        instance.name = "Model";
        instance.transform.SetParent(root.transform, false);

        Bounds bounds = new Bounds();
        bool first = true;
        foreach (Renderer r in root.GetComponentsInChildren<Renderer>())
        {
            r.shadowCastingMode = ShadowCastingMode.On;
            r.receiveShadows = true;
            if (first)
            {
                bounds = r.bounds;
                first = false;
            }
            else
            {
                bounds.Encapsulate(r.bounds);
            }
        }
        // Keep the collider inside the block's footprint (cables and boards may overhang a little), centered on it
        BoxCollider collider = root.AddComponent<BoxCollider>();
        collider.center = new Vector3(0f, bounds.center.y, 0f);
        collider.size = new Vector3(Mathf.Min(bounds.size.x, 0.98f), bounds.size.y, Mathf.Min(bounds.size.z, 0.98f));
        if (trap == "TeslaCoil")
        {
            ArcTemplate(folder, root.transform);
        }
        Debug.Log("[TrapsBuilder] " + trap + " bounds center " + bounds.center.ToString("F3") + " size "
            + bounds.size.ToString("F3") + ", materials " + string.Join(", ", names));

        string prefabPath = folder + "/" + trap + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Object.DestroyImmediate(root);
        return prefabPath;
    }

    /// <summary>
    /// A disabled LineRenderer the coil's controller clones for each bolt: an additive particle material over a
    /// soft white-cored glow strip, tinted electric blue. Shipping it in the prefab means the game needs no
    /// shader lookups of its own.
    /// </summary>
    private static void ArcTemplate(string folder, Transform parent)
    {
        string texPath = folder + "/" + "ArcGlow.png";
        const int w = 32, h = 32;
        Texture2D glow = new Texture2D(w, h, TextureFormat.RGBA32, false, true);
        for (int y = 0; y < h; y++)
        {
            float v = (y + 0.5f) / h - 0.5f;
            float core = Mathf.Exp(-(v / 0.09f) * (v / 0.09f));
            float halo = 0.45f * Mathf.Exp(-(v / 0.28f) * (v / 0.28f));
            float a = Mathf.Clamp01(core + halo);
            Color c = new Color(Mathf.Lerp(0.5f, 1f, core), Mathf.Lerp(0.7f, 1f, core), 1f, a) * a;
            c.a = a;
            for (int x = 0; x < w; x++)
            {
                glow.SetPixel(x, y, c);
            }
        }
        File.WriteAllBytes(texPath, glow.EncodeToPNG());
        AssetDatabase.ImportAsset(texPath, ImportAssetOptions.ForceSynchronousImport);
        TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(texPath);
        importer.textureType = TextureImporterType.Default;
        importer.sRGBTexture = true;
        importer.alphaSource = TextureImporterAlphaSource.FromInput;
        importer.mipmapEnabled = false;
        importer.wrapMode = TextureWrapMode.Clamp;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.SaveAndReimport();

        string matPath = folder + "/" + "ArcGlow.mat";
        Material material = AssetDatabase.LoadAssetAtPath<Material>(matPath);
        if (material == null)
        {
            material = new Material(Shader.Find("Legacy Shaders/Particles/Additive"));
            AssetDatabase.CreateAsset(material, matPath);
        }
        material.shader = Shader.Find("Legacy Shaders/Particles/Additive");
        material.SetTexture("_MainTex", AssetDatabase.LoadAssetAtPath<Texture2D>(texPath));
        material.SetColor("_TintColor", new Color(0.55f, 0.75f, 1f, 1f));
        EditorUtility.SetDirty(material);
        AssetDatabase.SaveAssets();

        GameObject arc = new GameObject("ArcTemplate");
        arc.transform.SetParent(parent, false);
        LineRenderer line = arc.AddComponent<LineRenderer>();
        line.sharedMaterial = material;
        line.useWorldSpace = true;
        line.widthMultiplier = 0.09f;
        line.textureMode = LineTextureMode.Stretch;
        line.alignment = LineAlignment.View;
        line.numCapVertices = 2;
        line.shadowCastingMode = ShadowCastingMode.Off;
        line.receiveShadows = false;
        line.positionCount = 0;
        line.enabled = false;
        arc.SetActive(false);
    }

    private static void ConfigureTexture(string path)
    {
        if (path.EndsWith("/ArcGlow.png"))
        {
            return;
        }
        TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
        bool normal = path.EndsWith("_Normal.png");
        bool linear = path.EndsWith("_RMOM.png");
        importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        importer.sRGBTexture = !(normal || linear);
        importer.alphaSource = TextureImporterAlphaSource.None;
        importer.mipmapEnabled = true;
        importer.wrapMode = path.Contains("_Winding_") ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
        importer.anisoLevel = 4;
        // Like the vanilla turret: 2048 color and normal maps for a model with many parts, 1024 for the packed map
        importer.maxTextureSize = path.EndsWith("_Emission.png") ? 256 : linear ? 1024 : 2048;
        importer.textureCompression = TextureImporterCompression.Compressed;
        importer.SaveAndReimport();
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

        Texture2D Tex(string suffix) => AssetDatabase.LoadAssetAtPath<Texture2D>(folder + "/" + name + "_" + suffix + ".png");

        material.SetTexture("_MainTex", Tex("Albedo"));
        Texture2D normal = Tex("Normal");
        if (normal != null)
        {
            material.SetTexture("_BumpMap", normal);
            material.SetFloat("_BumpScale", 1f);
            material.EnableKeyword("_NORMALMAP");
        }
        // Not read by Standard (no detail keyword); the mod hands it to the game's shader as _RMOM
        material.SetTexture("_DetailMask", Tex("RMOM"));
        material.SetFloat("_Glossiness", 0.35f);
        Texture2D emission = Tex("Emission");
        if (emission != null)
        {
            // The mod drives _EmissionColor per renderer (lamp off/on); the keyword must be on for the variant to exist
            material.SetTexture("_EmissionMap", emission);
            material.SetColor("_EmissionColor", Color.white);
            material.EnableKeyword("_EMISSION");
            material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
        }
        EditorUtility.SetDirty(material);
        AssetDatabase.SaveAssets();
        return material;
    }
}
