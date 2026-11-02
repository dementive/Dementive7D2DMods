using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Builds Resources/zombiesexpanded.unity3d (the overlay and eyeshine materials and the blood drip effect, in
/// Assets/ZombiesExpanded/Generated) and renders previews of them on vanilla zombies loaded from the game's own
/// bundles (nothing from the game is copied): Build/looks-day.png with each biome's weathering, wounds, fire and rain,
/// and Build/looks-night.png with eyeshine under a flashlight. Writes the zombie skeleton's bind pose to
/// Build/bones.txt.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod ZombiesBuilder.BuildAndPreview (with graphics).
/// </summary>
public static class ZombiesBuilder
{
    private const string BundleName = "zombiesexpanded.unity3d";
    private const string Generated = "Assets/ZombiesExpanded/Generated";

    private static readonly string[] GameBundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
        "zombies_assets_entities/zombies/cop.bundle", "zombies_assets_entities/zombies/nurse.bundle",
    };

    public static void BuildAndPreview()
    {
        Build();
        Preview();
        ZombiesModels.Preview();
        EffectsPreview();
    }

    public static void Build()
    {
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[]
        {
            GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLCore,
        });
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (!AssetDatabase.IsValidFolder(Generated))
        {
            AssetDatabase.CreateFolder("Assets/ZombiesExpanded", "Generated");
        }

        List<string> assets = new List<string>
        {
            MakeMaterial("ZombieOverlay", "Dementive/ZombieOverlay", 3000),
            MakeMaterial("ZombieEyeshine", "Dementive/ZombieEyeshine", 3010),
            BloodDrip(),
            BileCloud(),
            GoreBurst(),
        };
        assets.AddRange(ZombiesModels.BuildAll());
        AssetDatabase.SaveAssets();

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = assets.ToArray() };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[ZombiesBuilder] Built " + Path.Combine(output, BundleName));
    }

    private static string MakeMaterial(string name, string shaderName, int queue)
    {
        string path = Generated + "/" + name + ".mat";
        Shader shader = Shader.Find(shaderName);
        if (shader == null)
        {
            throw new System.Exception("Shader " + shaderName + " didn't compile; see the log above");
        }
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        m.renderQueue = queue;
        EditorUtility.SetDirty(m);
        return path;
    }

    /// <summary>Slow dark drops falling from a wound, a few a second.</summary>
    private static string BloodDrip()
    {
        string matPath = Generated + "/BloodDrop.mat";
        Shader shader = Shader.Find("Particles/Standard Surface") ?? Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(matPath);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, matPath);
        }
        m.shader = shader;
        m.shaderKeywords = new string[0];
        m.SetTexture("_MainTex", Dot());
        Color blood = new Color(0.22f, 0.01f, 0.01f, 1f);
        m.SetColor("_Color", blood);
        m.SetFloat("_Mode", 2f);
        m.SetOverrideTag("RenderType", "Transparent");
        m.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        m.SetInt("_ZWrite", 0);
        m.SetFloat("_Glossiness", 0.8f);
        m.SetFloat("_Metallic", 0f);
        m.EnableKeyword("_ALPHABLEND_ON");
        m.renderQueue = 3000;
        EditorUtility.SetDirty(m);

        GameObject go = new GameObject("BloodDrip");
        ParticleSystem ps = go.AddComponent<ParticleSystem>();
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = m;
        r.renderMode = ParticleSystemRenderMode.Stretch;
        r.lengthScale = 2.5f;
        r.velocityScale = 0.05f;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        ParticleSystem.MainModule main = ps.main;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.playOnAwake = true;
        main.loop = true;
        main.scalingMode = ParticleSystemScalingMode.Hierarchy;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 0.9f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0f, 0.15f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.012f, 0.02f);
        main.startColor = blood;
        main.gravityModifier = 1f;
        main.maxParticles = 20;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = new ParticleSystem.MinMaxCurve(2f, 4f);
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.03f;
        string path = Generated + "/BloodDrip.prefab";
        PrefabUtility.SaveAsPrefabAsset(go, path);
        Object.DestroyImmediate(go);
        return path;
    }

    private static Material ParticleMaterial(string name, Color color, float smoothness)
    {
        string matPath = Generated + "/" + name + ".mat";
        Shader shader = Shader.Find("Particles/Standard Surface") ?? Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(matPath);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, matPath);
        }
        m.shader = shader;
        m.shaderKeywords = new string[0];
        m.SetTexture("_MainTex", Dot());
        m.SetColor("_Color", color);
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
        return m;
    }

    private static ParticleSystem Particles(GameObject go, Material m, ParticleSystemRenderMode mode)
    {
        ParticleSystem ps = go.AddComponent<ParticleSystem>();
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = m;
        r.renderMode = mode;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        ParticleSystem.MainModule main = ps.main;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.playOnAwake = true;
        main.loop = false;
        main.scalingMode = ParticleSystemScalingMode.Hierarchy;
        return ps;
    }

    private static ParticleSystem.MinMaxGradient Fade(Color c, float alpha)
    {
        Gradient g = new Gradient();
        g.SetKeys(new[] { new GradientColorKey(c, 0f), new GradientColorKey(c, 1f) },
            new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(alpha, 0.15f), new GradientAlphaKey(alpha * 0.7f, 0.6f), new GradientAlphaKey(0f, 1f) });
        return new ParticleSystem.MinMaxGradient(g);
    }

    /// <summary>The Bloater's bile cloud: a sickly yellow-green haze about 3 m across that hangs for 5 s.</summary>
    private static string BileCloud()
    {
        Color bile = new Color(0.55f, 0.6f, 0.18f, 1f);
        GameObject go = new GameObject("BileCloud");
        ParticleSystem ps = Particles(go, ParticleMaterial("Bile", bile, 0.1f), ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule main = ps.main;
        main.duration = 5f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(2.5f, 4f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.6f);
        main.startSize = new ParticleSystem.MinMaxCurve(1.2f, 2.4f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, 6.28f);
        main.gravityModifier = -0.02f;
        main.maxParticles = 60;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 6f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 18) });
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 1.2f;
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Fade(bile, 0.45f);
        ParticleSystem.SizeOverLifetimeModule size = ps.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.7f, 1f, 1.3f));
        return Save(go);
    }

    /// <summary>The Brood's sac bursting: a spray of dark blood and bits.</summary>
    private static string GoreBurst()
    {
        Color blood = new Color(0.2f, 0.01f, 0.01f, 1f);
        GameObject go = new GameObject("GoreBurst");
        ParticleSystem ps = Particles(go, ParticleMaterial("Gore", blood, 0.8f), ParticleSystemRenderMode.Stretch);
        go.GetComponent<ParticleSystemRenderer>().lengthScale = 2f;
        ParticleSystem.MainModule main = ps.main;
        main.duration = 0.3f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.7f, 1.2f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(1.5f, 4f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.07f);
        main.startColor = blood;
        main.gravityModifier = 1f;
        main.maxParticles = 80;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 60) });
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Hemisphere;
        shape.radius = 0.15f;
        shape.rotation = new Vector3(0f, 0f, 0f);
        return Save(go);
    }

    private static string Save(GameObject go)
    {
        string path = Generated + "/" + go.name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(go, path);
        Object.DestroyImmediate(go);
        return path;
    }

    /// <summary>Build/effects.png: the bile cloud and gore burst half a second and a second in.</summary>
    public static void EffectsPreview()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        Day();
        string[] names = { "BileCloud", "GoreBurst" };
        for (int i = 0; i < names.Length; i++)
        {
            GameObject fx = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Generated + "/" + names[i] + ".prefab"));
            fx.transform.position = new Vector3(i * 4f - 2f, 1.2f, 0f);
            foreach (ParticleSystem ps in fx.GetComponentsInChildren<ParticleSystem>())
            {
                ps.Simulate(i == 0 ? 1.5f : 0.35f, true, true);
            }
        }
        Render(Path.Combine(Directory.GetCurrentDirectory(), "Build/effects.png"), new Vector3(0f, 1.6f, -9f), 30f, new Vector3(0f, 1.1f, 0f));
    }

    private static Texture2D Dot()
    {
        string path = Generated + "/Dot.png";
        if (!File.Exists(path))
        {
            const int size = 32;
            Texture2D t = new Texture2D(size, size, TextureFormat.RGBA32, false);
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f) / size * 2 - 1, dy = (y + 0.5f) / size * 2 - 1;
                    float a = Mathf.Clamp01(1f - Mathf.Sqrt(dx * dx + dy * dy));
                    t.SetPixel(x, y, new Color(1f, 1f, 1f, a * a));
                }
            }
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path);
        }
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    // ------------------------------------------------------------------ previews

    private class Look
    {
        public string Prefab;
        public float Grime, Settle, Bleach, Wet, Char, Embers, Frost, Blood;
        public Color GrimeColor = new Color(0.24f, 0.19f, 0.12f), SettleColor = new Color(0.2f, 0.22f, 0.12f);
        public bool Wounds;
        public bool Plain;
    }

    public static void Preview()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = GameBundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Material overlay = AssetDatabase.LoadAssetAtPath<Material>(Generated + "/ZombieOverlay.mat");
        Material eyes = AssetDatabase.LoadAssetAtPath<Material>(Generated + "/ZombieEyeshine.mat");
        try
        {
            Look[] looks =
            {
                new Look { Prefab = "zjoe.prefab", Plain = true },
                new Look { Prefab = "zjoe.prefab", Grime = 0.31f, Settle = 0.15f, Blood = 0.32f, Wounds = true },
                new Look { Prefab = "znurse.prefab", Grime = 0.38f, GrimeColor = new Color(0.45f, 0.36f, 0.24f), Settle = 0.5f,
                    SettleColor = new Color(0.66f, 0.56f, 0.4f), Bleach = 0.35f, Blood = 0.16f },
                new Look { Prefab = "zcop.prefab", Grime = 0.24f, GrimeColor = new Color(0.22f, 0.2f, 0.18f), Settle = 0.5f,
                    SettleColor = new Color(0.88f, 0.92f, 0.97f), Bleach = 0.1f, Blood = 0.28f },
                new Look { Prefab = "zcop.prefab", Grime = 0.5f, GrimeColor = new Color(0.06f, 0.05f, 0.045f), Settle = 0.4f,
                    SettleColor = new Color(0.08f, 0.07f, 0.06f), Char = 0.6f, Embers = 1f },
                new Look { Prefab = "zjoe.prefab", Grime = 0.62f, GrimeColor = new Color(0.27f, 0.28f, 0.22f), Settle = 0.45f,
                    SettleColor = new Color(0.45f, 0.45f, 0.43f), Bleach = 0.15f, Wet = 0.8f, Blood = 0.04f },
            };
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            List<GameObject> zombies = new List<GameObject>();
            for (int i = 0; i < looks.Length; i++)
            {
                GameObject z = Object.Instantiate(Load(loaded, looks[i].Prefab));
                z.transform.position = new Vector3((i - (looks.Length - 1) / 2f) * 1.3f, 0f, 0f);
                z.transform.rotation = Quaternion.Euler(0f, 180f - 15f, 0f);
                ArmsDown(z);
                if (!looks[i].Plain)
                {
                    Dress(z, looks[i], overlay, i);
                }
                zombies.Add(z);
            }
            Bones(zombies[0], Path.Combine(output, "bones.txt"));
            Day();
            Render(Path.Combine(output, "looks-day.png"), new Vector3(0f, 1.25f, -8f), 26f);
            Render(Path.Combine(output, "looks-close.png"), new Vector3(1.95f, 1.9f, -3.4f), 30f, new Vector3(1.95f, 1.15f, 0f));
            foreach (GameObject z in zombies)
            {
                Object.DestroyImmediate(z);
            }
            zombies.Clear();

            // Each layer alone at full strength on the same zombie, to judge them one by one
            Look[] layers =
            {
                new Look { Prefab = "zjoe.prefab", Grime = 0.8f },
                new Look { Prefab = "zjoe.prefab", Settle = 0.8f, SettleColor = new Color(0.88f, 0.92f, 0.97f) },
                new Look { Prefab = "zjoe.prefab", Char = 0.8f, Embers = 1f },
                new Look { Prefab = "zjoe.prefab", Frost = 0.6f },
                new Look { Prefab = "zjoe.prefab", Blood = 0.8f, Wounds = true },
                new Look { Prefab = "zjoe.prefab", Wet = 1f },
            };
            for (int i = 0; i < layers.Length; i++)
            {
                GameObject z = Object.Instantiate(Load(loaded, layers[i].Prefab));
                z.transform.position = new Vector3((i - (layers.Length - 1) / 2f) * 1.3f, 0f, 0f);
                z.transform.rotation = Quaternion.Euler(0f, 180f - 15f, 0f);
                ArmsDown(z);
                Dress(z, layers[i], overlay, i);
                zombies.Add(z);
            }
            Render(Path.Combine(output, "looks-layers.png"), new Vector3(0f, 1.25f, -8f), 26f);

            // Night: the same zombies in the dark, a flashlight from the camera, eyeshine on the middle ones
            Object.DestroyImmediate(GameObject.Find("Sun"));
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.02f, 0.025f, 0.035f);
            Light torch = new GameObject("Flashlight").AddComponent<Light>();
            torch.type = LightType.Spot;
            torch.spotAngle = 40f;
            torch.range = 30f;
            torch.intensity = 2.5f;
            torch.color = new Color(1f, 0.95f, 0.85f);
            torch.transform.position = new Vector3(0f, 1.5f, -7.8f);
            torch.transform.LookAt(new Vector3(0f, 1.3f, 0f));
            foreach (GameObject z in zombies)
            {
                Eyes(z, eyes);
            }
            Render(Path.Combine(output, "looks-night.png"), new Vector3(0f, 1.45f, -8f), 26f);
            Render(Path.Combine(output, "looks-night-close.png"), new Vector3(-3.0f, 1.75f, -1.6f), 30f, new Vector3(-3.25f, 1.65f, 0f));
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    /// <summary>What ZedLook does in game: the overlay on every body renderer, with the zombie's own textures.</summary>
    private static void Dress(GameObject z, Look look, Material overlay, int seed)
    {
        Vector4[] wounds = new Vector4[12];
        int count = 0;
        if (look.Wounds)
        {
            Transform Bone(string n) => z.GetComponentsInChildren<Transform>().First(t => t.name == n);
            Vector3 front = z.transform.forward;
            wounds[count++] = Pack(Bone("Spine2").position + front * 0.15f + Vector3.up * 0.05f, 0.05f, 0);
            wounds[count++] = Pack(Bone("Spine1").position + front * 0.14f + z.transform.right * 0.1f, 0.045f, 0);
            wounds[count++] = Pack(Bone("Head").position + front * 0.09f + Vector3.up * 0.08f, 0.045f, 0);
            wounds[count++] = Pack(Bone("LeftUpLeg").position + front * 0.08f + Vector3.down * 0.2f, 0.07f, 0);
            wounds[count++] = Pack(Bone("RightArm").position + front * 0.05f + z.transform.right * -0.15f, 0.08f, 1);
        }
        foreach (SkinnedMeshRenderer r in z.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            Material m = r.sharedMaterial;
            if (m == null || r.name.ToLowerInvariant().Contains("eye") || m.renderQueue >= 2450 || m.IsKeywordEnabled("_ALPHATEST_ON"))
            {
                continue;
            }
            r.sharedMaterials = r.sharedMaterials.Concat(new[] { overlay }).ToArray();
            MaterialPropertyBlock b = new MaterialPropertyBlock();
            Texture albedo = m.HasProperty("_Albedo") ? m.GetTexture("_Albedo") : m.mainTexture;
            Texture normal = m.HasProperty("_Normal") ? m.GetTexture("_Normal") : null;
            if (albedo != null)
            {
                b.SetTexture("_BaseAlbedo", albedo);
            }
            if (normal != null)
            {
                b.SetTexture("_BaseNormal", normal);
            }
            b.SetFloat("_HasBase", albedo != null ? 1f : 0f);
            b.SetFloat("_Grime", look.Grime);
            b.SetColor("_GrimeColor", look.GrimeColor);
            b.SetFloat("_Settle", look.Settle);
            b.SetColor("_SettleColor", look.SettleColor);
            b.SetFloat("_Bleach", look.Bleach);
            b.SetFloat("_Wet", look.Wet);
            b.SetFloat("_Char", look.Char);
            b.SetFloat("_Embers", look.Embers);
            b.SetFloat("_Frost", look.Frost);
            b.SetFloat("_Blood", look.Blood);
            b.SetVectorArray("_Wounds", wounds);
            b.SetFloat("_WoundCount", count);
            b.SetFloat("_Seed", seed * 13.7f);
            r.SetPropertyBlock(b, r.sharedMaterials.Length - 1);
        }
    }

    private static Vector4 Pack(Vector3 p, float radius, int kind)
    {
        return new Vector4(p.x, p.y, p.z, radius + kind * 10f);
    }

    /// <summary>What ZedLook does for the eyes: a glint under each brow bone, on the head bone, at full strength.</summary>
    private static void Eyes(GameObject z, Material eyes)
    {
        Transform[] all = z.GetComponentsInChildren<Transform>();
        Transform head = all.First(t => t.name == "Head");
        foreach (string brow in new[] { "LeftBrow", "RightBrow" })
        {
            Transform b = all.First(t => t.name == brow);
            GameObject eye = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(eye.GetComponent<Collider>());
            eye.transform.SetParent(head, false);
            Vector3 local = head.InverseTransformPoint(b.position - z.transform.up * 0.026f + z.transform.forward * 0.004f);
            local.x *= 0.9f;
            eye.transform.localPosition = local;
            eye.transform.localScale = Vector3.one * 0.03f;
            Renderer r = eye.GetComponent<Renderer>();
            r.sharedMaterial = eyes;
            r.shadowCastingMode = ShadowCastingMode.Off;
            MaterialPropertyBlock block = new MaterialPropertyBlock();
            block.SetFloat("_Intensity", 1f);
            r.SetPropertyBlock(block);
            Debug.Log("[ZombiesBuilder] eye at " + eye.transform.position.ToString("F3") + " lossy " + eye.transform.lossyScale.ToString("F3")
                + " head lossy " + head.lossyScale.ToString("F3") + " shader " + eyes.shader.name + " supported " + eyes.shader.isSupported + " queue " + eyes.renderQueue);
        }
    }

    private static void Bones(GameObject z, string path)
    {
        StringBuilder sb = new StringBuilder("Bind pose of " + z.name + " (local rotation as euler, local position)\n");
        foreach (string n in new[] { "Origin", "Hips", "Spine", "Spine1", "Spine2", "Spine3", "Neck", "Head", "LeftBrow", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftUpLeg", "LeftLeg" })
        {
            Transform t = z.GetComponentsInChildren<Transform>().FirstOrDefault(x => x.name == n);
            if (t != null)
            {
                sb.AppendLine(n + ": rot " + t.localRotation.eulerAngles.ToString("F1") + " pos " + t.localPosition.ToString("F3")
                    + " world up " + t.up.ToString("F2") + " fwd " + t.forward.ToString("F2") + " right " + t.right.ToString("F2"));
            }
        }
        File.WriteAllText(path, sb.ToString());
    }

    /// <summary>
    /// Writes each reference zombie's bind pose to blender/skeletons/&lt;name&gt;.json, for fitting gear and growths in
    /// Blender: every bone's position and rotation relative to the zombie's root (Unity space, meters), and every bone
    /// collider (the hit boxes, which give the body's size). Numbers only; no mesh is copied.
    /// </summary>
    public static void Skeletons()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string[] bundles =
        {
            "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
            "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
            "zombies_assets_entities/zombies/cop.bundle", "zombies_assets_entities/zombies/nurse.bundle",
            "zombies_assets_entities/zombies/soldier.bundle", "zombies_assets_entities/zombies/biker.bundle",
        };
        List<AssetBundle> loaded = bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        string outDir = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../blender/skeletons"));
        Directory.CreateDirectory(outDir);
        try
        {
            foreach (string name in new[] { "zjoe", "zcop", "znurse", "zsoldier", "zbiker" })
            {
                GameObject z = Object.Instantiate(Load(loaded, name + ".prefab"));
                z.transform.position = Vector3.zero;
                z.transform.rotation = Quaternion.identity;
                StringBuilder sb = new StringBuilder("{\n  \"bones\": [\n");
                List<string> bones = new List<string>();
                foreach (Transform t in z.GetComponentsInChildren<Transform>(true))
                {
                    if (t == z.transform || t.GetComponent<Renderer>() != null)
                    {
                        continue;
                    }
                    Vector3 p = t.position;
                    Quaternion q = t.rotation;
                    bones.Add("    {\"name\": \"" + t.name + "\", \"parent\": \"" + (t.parent == z.transform ? "" : t.parent.name)
                        + "\", \"pos\": [" + F(p.x) + ", " + F(p.y) + ", " + F(p.z) + "], \"rot\": [" + F(q.x) + ", " + F(q.y) + ", "
                        + F(q.z) + ", " + F(q.w) + "]}");
                }
                sb.Append(string.Join(",\n", bones)).Append("\n  ],\n  \"colliders\": [\n");
                List<string> cols = new List<string>();
                foreach (Collider c in z.GetComponentsInChildren<Collider>(true))
                {
                    if (c.transform == z.transform || c.transform.name == "Collider")
                    {
                        continue;
                    }
                    if (c is CapsuleCollider cc)
                    {
                        cols.Add("    {\"bone\": \"" + c.transform.name + "\", \"type\": \"capsule\", \"center\": [" + V(cc.center) + "], \"radius\": "
                            + F(cc.radius) + ", \"height\": " + F(cc.height) + ", \"axis\": " + cc.direction + "}");
                    }
                    else if (c is SphereCollider sc)
                    {
                        cols.Add("    {\"bone\": \"" + c.transform.name + "\", \"type\": \"sphere\", \"center\": [" + V(sc.center) + "], \"radius\": "
                            + F(sc.radius) + "}");
                    }
                    else if (c is BoxCollider bc)
                    {
                        cols.Add("    {\"bone\": \"" + c.transform.name + "\", \"type\": \"box\", \"center\": [" + V(bc.center) + "], \"size\": [" + V(bc.size) + "]}");
                    }
                }
                sb.Append(string.Join(",\n", cols)).Append("\n  ]\n}\n");
                File.WriteAllText(Path.Combine(outDir, name.Substring(1) + ".json"), sb.ToString());
                Object.DestroyImmediate(z);
            }
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    private static string F(float f)
    {
        return f.ToString("0.#####", System.Globalization.CultureInfo.InvariantCulture);
    }

    private static string V(Vector3 v)
    {
        return F(v.x) + ", " + F(v.y) + ", " + F(v.z);
    }

    private static GameObject Load(List<AssetBundle> loaded, string name)
    {
        foreach (AssetBundle b in loaded)
        {
            string path = b.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + name));
            if (path != null)
            {
                return b.LoadAsset<GameObject>(path);
            }
        }
        throw new System.Exception("missing " + name);
    }

    private static void ArmsDown(GameObject z)
    {
        foreach (Transform t in z.GetComponentsInChildren<Transform>())
        {
            if (t.name == "LeftArm")
            {
                t.localRotation *= Quaternion.Euler(0f, 0f, 70f);
            }
            else if (t.name == "RightArm")
            {
                t.localRotation *= Quaternion.Euler(0f, 0f, -70f);
            }
        }
    }

    private static void Day()
    {
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.93f, 0.84f);
        sun.intensity = 1.3f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(35f, 20f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.5f, 0.55f, 0.65f);
        RenderSettings.ambientEquatorColor = new Color(0.38f, 0.38f, 0.38f);
        RenderSettings.ambientGroundColor = new Color(0.2f, 0.19f, 0.17f);
        Camera probeCam = new GameObject("ProbeCam").AddComponent<Camera>();
        probeCam.clearFlags = CameraClearFlags.SolidColor;
        probeCam.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        probeCam.cullingMask = 0;
        Cubemap sky = new Cubemap(64, TextureFormat.RGBAHalf, false);
        probeCam.RenderToCubemap(sky);
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
        RenderSettings.customReflectionTexture = sky;
        Object.DestroyImmediate(probeCam.gameObject);
    }

    private static void Render(string path, Vector3 from, float fov, Vector3? at = null)
    {
        const int width = 2400, height = 1100;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = RenderSettings.ambientMode == AmbientMode.Flat ? new Color(0.01f, 0.012f, 0.02f) : new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = fov;
        camera.transform.position = from;
        camera.transform.LookAt(at ?? new Vector3(0f, 1.0f, 0f));
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        File.WriteAllBytes(path, read.EncodeToPNG());
        Object.DestroyImmediate(camera.gameObject);
    }
}
