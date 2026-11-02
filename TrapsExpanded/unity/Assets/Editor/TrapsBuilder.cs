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
/// Effects are made here too: the Tesla Coil's arc template, the Sprinkler's spray (placed at the model's
/// SprayOrigin, aimed at SprayAim) and the SoakDrip effect the mod attaches to soaked zombies (Assets/TrapsExpanded/Fx).
/// </summary>
public static class TrapsBuilder
{
    private const string BundleName = "trapsexpanded.unity3d";
    private const string Root = "Assets/TrapsExpanded";

    private static readonly string[] Traps =
    {
        "TeslaCoil", "Sprinkler", "GreaseSlick", "BurnBarrel", "SwingingLog", "BearTrap", "TripBow", "TarSprayer",
        "SalvageHopper", "CryoVent", "Ram", "Overcharger", "BoltThrower",
    };
    private const string Fx = Root + "/Fx";

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
        if (!AssetDatabase.IsValidFolder(Fx))
        {
            AssetDatabase.CreateFolder(Root, "Fx");
        }

        List<string> prefabs = new List<string>();
        foreach (string trap in Traps)
        {
            prefabs.Add(MakePrefab(trap));
        }
        prefabs.Add(SoakDrip());
        List<string> effects = TrapsEffects.BuildAll();
        prefabs.AddRange(effects);
        AssetDatabase.SaveAssets();

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
        VanillaCompare.FxSheet(effects, Path.Combine(output, "Effects-preview.png"));
        // The Flame Vent reuses the game's unfinished flamethrower trap model: list its parts to find the nozzle
        VanillaCompare.DumpVanilla("flamethrowertrapprefab.prefab", Path.Combine(output, "flamethrower-parts.txt"),
            Path.Combine(output, "flamethrower-preview.png"));
    }

    /// <summary>Rebuilds only the effect prefabs and renders Build/Effects-preview.png (no bundle), for tuning
    /// them.</summary>
    public static void EffectsOnly()
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        List<string> effects = TrapsEffects.BuildAll();
        AssetDatabase.SaveAssets();
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        VanillaCompare.FxSheet(effects, Path.Combine(output, "Effects-preview.png"));
    }

    private static string MakePrefab(string trap)
    {
        string folder = Root + "/" + trap;
        // The big Tesla Coil gets 2048 color and normal maps like the vanilla turret; smaller traps 1024
        int maxSize = trap == "TeslaCoil" ? 2048 : 1024;
        foreach (string path in Directory.GetFiles(folder, "*.png"))
        {
            ConfigureTexture(path.Replace('\\', '/'), maxSize);
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
        if (trap == "Sprinkler")
        {
            Spray(root.transform);
        }
        foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
        {
            if (t.name.EndsWith("Origin") || t.name.EndsWith("Aim") || t.name.EndsWith("Point"))
            {
                Debug.Log("[TrapsBuilder] " + trap + " point " + t.name + " at " + root.transform.InverseTransformPoint(t.position).ToString("F3"));
            }
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

    // ------------------------------------------------------------------ water effects

    /// <summary>A soft round dot for particles.</summary>
    internal static Texture2D Dot()
    {
        Directory.CreateDirectory(Fx);
        string path = Fx + "/WaterDot.png";
        if (!File.Exists(path))
        {
            const int size = 32;
            Texture2D t = new Texture2D(size, size, TextureFormat.RGBA32, false, true);
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f) / size - 0.5f, dy = (y + 0.5f) / size - 0.5f;
                    float a = Mathf.Clamp01(1f - Mathf.Sqrt(dx * dx + dy * dy) * 2f);
                    t.SetPixel(x, y, new Color(1f, 1f, 1f, a * a));
                }
            }
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
            importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.alphaIsTransparency = true;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.SaveAndReimport();
        }
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    /// <summary>A lit, alpha-faded particle material (Particles/Standard Surface in Fade mode), so water isn't
    /// glowing at night.</summary>
    internal static Material WaterMaterial(string name, Color color, float smoothness)
    {
        string path = Fx + "/" + name + ".mat";
        Shader shader = Shader.Find("Particles/Standard Surface") ?? Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        m.shaderKeywords = new string[0];
        m.SetTexture("_MainTex", Dot());
        m.SetColor("_Color", color);
        m.SetColor("_TintColor", color);
        m.SetFloat("_Mode", 2f);
        m.SetOverrideTag("RenderType", "Transparent");
        m.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        m.SetInt("_ZWrite", 0);
        m.SetFloat("_Glossiness", smoothness);
        m.SetFloat("_Metallic", 0f);
        m.EnableKeyword("_ALPHABLEND_ON");
        m.renderQueue = 3000;
        EditorUtility.SetDirty(m);
        AssetDatabase.SaveAssets();
        return m;
    }

    internal static ParticleSystem Particles(GameObject go, Material material, ParticleSystemRenderMode mode)
    {
        ParticleSystem ps = go.AddComponent<ParticleSystem>();
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = material;
        r.renderMode = mode;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        ParticleSystem.MainModule main = ps.main;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.playOnAwake = false;
        main.scalingMode = ParticleSystemScalingMode.Hierarchy;
        return ps;
    }

    internal static ParticleSystem.MinMaxGradient Fade(Color c, float alpha)
    {
        Gradient g = new Gradient();
        g.SetKeys(new[] { new GradientColorKey(c, 0f), new GradientColorKey(c, 1f) },
            new[] { new GradientAlphaKey(alpha, 0f), new GradientAlphaKey(alpha * 0.8f, 0.6f), new GradientAlphaKey(0f, 1f) });
        return new ParticleSystem.MinMaxGradient(g);
    }

    /// <summary>
    /// The Sprinkler's spray: a 0.8 s burst of stretched droplets in a cone from the middle nozzle, falling under
    /// gravity, with a mist of bigger soft particles. Played by the mod each time the sprinkler soaks someone.
    /// </summary>
    private static void Spray(Transform root)
    {
        Transform origin = root.GetComponentsInChildren<Transform>(true).First(t => t.name == "SprayOrigin");
        Transform aim = root.GetComponentsInChildren<Transform>(true).First(t => t.name == "SprayAim");
        GameObject spray = new GameObject("SprayFx");
        spray.transform.SetParent(root, false);
        spray.transform.position = origin.position;
        spray.transform.rotation = Quaternion.LookRotation(aim.position - origin.position, Vector3.up);

        Color water = new Color(0.72f, 0.8f, 0.88f);
        ParticleSystem drops = Particles(spray, WaterMaterial("SprayDrops", water, 0.5f), ParticleSystemRenderMode.Stretch);
        ParticleSystemRenderer dr = spray.GetComponent<ParticleSystemRenderer>();
        dr.velocityScale = 0.025f;
        dr.lengthScale = 1f;
        ParticleSystem.MainModule main = drops.main;
        main.duration = 0.8f;
        main.loop = false;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.4f, 0.65f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(4.5f, 7.5f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.045f);
        main.gravityModifier = 1f;
        main.maxParticles = 700;
        ParticleSystem.EmissionModule emission = drops.emission;
        emission.rateOverTime = 600f;
        ParticleSystem.ShapeModule shape = drops.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 24f;
        shape.radius = 0.05f;
        ParticleSystem.ColorOverLifetimeModule col = drops.colorOverLifetime;
        col.enabled = true;
        col.color = Fade(water, 0.4f);

        GameObject mistGo = new GameObject("SprayMist");
        mistGo.transform.SetParent(spray.transform, false);
        ParticleSystem mist = Particles(mistGo, WaterMaterial("SprayMist", water, 0.3f), ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule mm = mist.main;
        mm.duration = 0.8f;
        mm.loop = false;
        mm.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 1.1f);
        mm.startSpeed = new ParticleSystem.MinMaxCurve(1.5f, 3.5f);
        mm.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.6f);
        mm.gravityModifier = 0.15f;
        mm.maxParticles = 120;
        ParticleSystem.EmissionModule me = mist.emission;
        me.rateOverTime = 70f;
        ParticleSystem.ShapeModule ms = mist.shape;
        ms.shapeType = ParticleSystemShapeType.Cone;
        ms.angle = 30f;
        ms.radius = 0.08f;
        ParticleSystem.ColorOverLifetimeModule mc = mist.colorOverLifetime;
        mc.enabled = true;
        mc.color = Fade(water, 0.12f);
        ParticleSystem.SizeOverLifetimeModule size = mist.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.6f, 1f, 1.6f));
    }

    /// <summary>
    /// Water dripping off a soaked zombie: a loose box of falling drops around the body, looping. The mod attaches
    /// it at chest height and stops it when the soak ends.
    /// </summary>
    private static string SoakDrip()
    {
        Directory.CreateDirectory(Fx);
        GameObject go = new GameObject("SoakDrip");
        Color water = new Color(0.8f, 0.88f, 1f);
        ParticleSystem ps = Particles(go, WaterMaterial("DripDrops", water, 0.9f), ParticleSystemRenderMode.Stretch);
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.velocityScale = 0.06f;
        r.lengthScale = 1.5f;
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.duration = 1f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.8f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0f, 0.2f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.015f, 0.03f);
        main.gravityModifier = 1.2f;
        main.maxParticles = 80;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 22f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.4f, 0.9f, 0.3f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Fade(water, 0.7f);
        string path = Fx + "/SoakDrip.prefab";
        PrefabUtility.SaveAsPrefabAsset(go, path);
        Object.DestroyImmediate(go);
        return path;
    }

    private static void ConfigureTexture(string path, int maxSize)
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
        importer.maxTextureSize = path.EndsWith("_Emission.png") ? 256 : linear ? 1024 : maxSize;
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
