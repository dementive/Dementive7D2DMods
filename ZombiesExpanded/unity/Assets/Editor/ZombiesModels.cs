using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// The gear and growth models (Assets/ZombiesExpanded/Models/&lt;Name&gt;/&lt;Name&gt;.fbx from blender/*.py, one child per bone,
/// modeled on Joe's bind pose) turned into prefabs the mod bolts onto any zombie: a root named &lt;Name&gt; with one child
/// per bone, named after it, holding that piece's pose relative to the bone. Materials are Standard ones carrying the
/// game shader's packed RMOM map in _DetailMask, swapped to the game's model shader at runtime (as the traps do).
/// Previews put each model on vanilla Joe, Cop and Nurse loaded from the game's bundles, in the game's shader.
/// </summary>
public static class ZombiesModels
{
    public const string Root = "Assets/ZombiesExpanded/Models";

    [System.Serializable]
    private class Bone
    {
        public string name;
        public string parent;
        public float[] pos;
        public float[] rot;
    }

    [System.Serializable]
    private class Skeleton
    {
        public Bone[] bones;
    }

    private static Dictionary<string, Bone> joe;

    private static Dictionary<string, Bone> Joe()
    {
        if (joe == null)
        {
            string path = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../blender/skeletons/joe.json"));
            Skeleton s = JsonUtility.FromJson<Skeleton>(File.ReadAllText(path));
            joe = s.bones.GroupBy(b => b.name).ToDictionary(g => g.Key, g => g.First());
        }
        return joe;
    }

    public static List<string> Names()
    {
        if (!AssetDatabase.IsValidFolder(Root))
        {
            return new List<string>();
        }
        return Directory.GetDirectories(Root).Select(Path.GetFileName)
            .Where(n => File.Exists(Path.Combine(Root, n, n + ".fbx"))).OrderBy(n => n).ToList();
    }

    public static List<string> BuildAll()
    {
        return Names().Select(MakePrefab).ToList();
    }

    private static string MakePrefab(string name)
    {
        string folder = Root + "/" + name;
        foreach (string path in Directory.GetFiles(folder, "*.png"))
        {
            ConfigureTexture(path.Replace('\\', '/'));
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
        model.isReadable = false;
        model.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        model.materialLocation = ModelImporterMaterialLocation.InPrefab;
        model.SaveAndReimport();
        string[] names = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Material>().Select(m => m.name)
            .Concat(model.GetExternalObjectMap().Keys.Where(k => k.type == typeof(Material)).Select(k => k.name))
            .Distinct().ToArray();
        foreach (string n in names)
        {
            model.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), n), MakeMaterial(folder, name));
        }
        model.SaveAndReimport();

        GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
        PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        instance.transform.position = Vector3.zero;
        instance.transform.rotation = Quaternion.identity;
        GameObject root = new GameObject(name);
        Dictionary<string, Bone> bones = Joe();
        int pieces = 0;
        foreach (MeshFilter mf in instance.GetComponentsInChildren<MeshFilter>(true))
        {
            if (mf.sharedMesh == null || mf.sharedMesh.vertexCount == 0 || !bones.TryGetValue(BoneOf(mf.name), out Bone bone))
            {
                continue;
            }
            Vector3 bp = new Vector3(bone.pos[0], bone.pos[1], bone.pos[2]);
            Quaternion bq = new Quaternion(bone.rot[0], bone.rot[1], bone.rot[2], bone.rot[3]);
            GameObject piece = new GameObject(mf.name);
            piece.transform.SetParent(root.transform, false);
            piece.transform.localPosition = Quaternion.Inverse(bq) * (mf.transform.position - bp);
            // A part the game drags along the ground (ZedDrag: the cinder block and its chain) keeps its rotation in
            // the zombie model's own space (facing +Z, up +Y), so the game can stand it the way it was built
            piece.transform.localRotation = mf.name.EndsWith("Drag") ? mf.transform.rotation : Quaternion.Inverse(bq) * mf.transform.rotation;
            piece.transform.localScale = mf.transform.lossyScale;
            piece.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
            MeshRenderer r = piece.AddComponent<MeshRenderer>();
            r.sharedMaterials = mf.GetComponent<MeshRenderer>().sharedMaterials;
            r.shadowCastingMode = ShadowCastingMode.On;
            r.receiveShadows = true;
            pieces++;
        }
        Object.DestroyImmediate(instance);
        string prefabPath = folder + "/" + name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Object.DestroyImmediate(root);
        Debug.Log("[ZombiesModels] " + name + ": " + pieces + " pieces");
        return prefabPath;
    }

    /// <summary>A part's bone: its name up to '#' ("Spine2#Chest" rides on Spine2).</summary>
    public static string BoneOf(string part)
    {
        int i = part.IndexOf('#');
        return i < 0 ? part : part.Substring(0, i);
    }

    private static void ConfigureTexture(string path)
    {
        TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
        bool normal = path.EndsWith("_Normal.png");
        bool linear = path.EndsWith("_RMOM.png");
        importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        importer.sRGBTexture = !(normal || linear);
        importer.alphaSource = TextureImporterAlphaSource.None;
        importer.mipmapEnabled = true;
        importer.wrapMode = TextureWrapMode.Clamp;
        importer.anisoLevel = 4;
        importer.maxTextureSize = path.EndsWith("_Emission.png") ? 256 : linear ? 512 : 1024;
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
        // Not read by Standard; the mod hands it to the game's shader as _RMOM
        material.SetTexture("_DetailMask", Tex("RMOM"));
        material.SetFloat("_Glossiness", 0.35f);
        Texture2D emission = Tex("Emission");
        if (emission != null)
        {
            material.SetTexture("_EmissionMap", emission);
            material.SetColor("_EmissionColor", Color.white);
            material.EnableKeyword("_EMISSION");
            material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
        }
        EditorUtility.SetDirty(material);
        AssetDatabase.SaveAssets();
        return material;
    }

    // ------------------------------------------------------------------ fitting (mirrors ZedFit in the mod)

    /// <summary>Joe's hit box centers (in the bone's frame) for the bones whose pieces are also moved to match where
    /// the zombie's head or chest sits on its bone.</summary>
    public static readonly Dictionary<string, Vector3> JoeCenter = new Dictionary<string, Vector3>
    {
        { "Head", new Vector3(0f, 0.02f, 0f) }, { "Spine2", new Vector3(-0.00073f, 0.11f, -0.05f) },
    };

    /// <summary>Joe's hit box radius for the bones pieces fit by (the reference the models are built on).</summary>
    public static readonly Dictionary<string, float> JoeRadius = new Dictionary<string, float>
    {
        { "Head", 0.1f }, { "Spine2", 0.158f }, { "LeftArm", 0.06f }, { "RightArm", 0.06f }, { "LeftForeArm", 0.05f },
        { "RightForeArm", 0.05f }, { "LeftUpLeg", 0.1f }, { "RightUpLeg", 0.1f }, { "LeftLeg", 0.05f }, { "RightLeg", 0.05f },
    };

    /// <summary>Which hit box a bone's pieces are sized by.</summary>
    public static string FitBone(string bone)
    {
        switch (bone)
        {
            case "Neck":
            case "Jaw":
                return "Head";
            case "Hips":
            case "Spine":
            case "Spine1":
            case "Spine3":
            case "LeftShoulder":
            case "RightShoulder":
                return "Spine2";
            case "LeftHand":
                return "LeftForeArm";
            case "RightHand":
                return "RightForeArm";
            case "LeftFoot":
                return "LeftLeg";
            case "RightFoot":
                return "RightLeg";
        }
        return bone;
    }

    public static float Fit(Transform zombie, string bone)
    {
        string fit = FitBone(bone);
        if (!JoeRadius.TryGetValue(fit, out float reference))
        {
            return 1f;
        }
        Transform t = zombie.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == fit);
        Collider c = t != null ? t.GetComponent<Collider>() : null;
        float r = c is CapsuleCollider cc ? cc.radius : c is SphereCollider sc ? sc.radius : 0f;
        if (r <= 0f)
        {
            return 1f;
        }
        bool head = fit == "Head";
        return Mathf.Clamp(r / reference, head ? 0.85f : 0.8f, head ? 1.15f : 1.35f);
    }

    /// <summary>What the mod does in game: each piece onto its bone, at its pose, sized to the zombie.</summary>
    public static List<GameObject> Attach(GameObject prefab, Transform zombie)
    {
        List<GameObject> placed = new List<GameObject>();
        Transform[] all = zombie.GetComponentsInChildren<Transform>(true);
        foreach (Transform piece in prefab.transform)
        {
            string boneName = BoneOf(piece.name);
            Transform bone = all.FirstOrDefault(t => t.name == boneName);
            if (bone == null)
            {
                continue;
            }
            if (piece.name.EndsWith("Drag"))
            {
                // As ZedDrag does in game: in the zombie's own frame, the chain from the shackle where it was built,
                // and the block where it was built but down on the ground
                GameObject d = Object.Instantiate(piece.gameObject, zombie, false);
                Vector3 at = zombie.InverseTransformPoint(bone.TransformPoint(piece.localPosition));
                if (piece.name.EndsWith("BlockDrag"))
                {
                    at.y = 0.1f;
                }
                d.transform.localPosition = at;
                d.transform.localRotation = piece.localRotation;
                placed.Add(d);
                continue;
            }
            GameObject p = Object.Instantiate(piece.gameObject, bone, false);
            float s = Fit(zombie, boneName);
            Vector3 pos = piece.localPosition * s;
            Collider c = bone.GetComponent<Collider>();
            if (c != null && JoeCenter.TryGetValue(boneName, out Vector3 jc))
            {
                // Joe's head (or chest) mapped onto this zombie's: same place relative to the hit box, scaled
                pos = Center(c) + (piece.localPosition - jc) * s;
            }
            p.transform.localPosition = pos + Settle(all, bone, boneName);
            p.transform.localRotation = piece.localRotation;
            p.transform.localScale = piece.localScale * s;
            placed.Add(p);
        }
        return placed;
    }

    /// <summary>As ZedModels.Settle does in game: Neck parts come forward with the front of the chest (the fat cop's is
    /// 6 to 10 cm out from Joe's), Jaw parts move with the head's hit box.</summary>
    private static Vector3 Settle(Transform[] all, Transform bone, string boneName)
    {
        if (boneName == "Neck")
        {
            Transform chest = all.FirstOrDefault(t => t.name == "Spine2");
            if (chest != null)
            {
                Collider c = chest.GetComponent<Collider>();
                float front = c is CapsuleCollider cc ? cc.center.z + cc.radius : c is SphereCollider sc ? sc.center.z + sc.radius : 0f;
                float forward = front > 0f ? front - (JoeCenter["Spine2"].z + JoeRadius["Spine2"]) : 0f;
                // The game's fat zombies (fat walk) get at least 8 cm; in the preview, the one with a round (sphere)
                // chest hit box, the fat cop
                if (c is SphereCollider)
                {
                    forward = Mathf.Max(forward, 0.08f);
                }
                forward = Mathf.Clamp(forward, 0f, 0.12f);
                return bone.InverseTransformVector(chest.TransformVector(new Vector3(0f, 0f, forward)));
            }
        }
        if (boneName == "Jaw")
        {
            Transform head = all.FirstOrDefault(t => t.name == "Head");
            Collider c = head != null ? head.GetComponent<Collider>() : null;
            if (c != null)
            {
                return bone.InverseTransformVector(head.TransformVector(Center(c) - JoeCenter["Head"]));
            }
        }
        return Vector3.zero;
    }

    private static Vector3 Center(Collider c)
    {
        return c is CapsuleCollider cc ? cc.center : c is SphereCollider sc ? sc.center : c is BoxCollider bc ? bc.center : Vector3.zero;
    }

    // ------------------------------------------------------------------ previews

    private static readonly string[] Bundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
        "zombies_assets_entities/zombies/cop.bundle", "zombies_assets_entities/zombies/nurse.bundle",
    };

    /// <summary>Build/models/&lt;Name&gt;.png for each model (or just `only`): on Joe, Cop and Nurse, from the front and
    /// three-quarter back, in the game's model shader.</summary>
    public static void Preview(IEnumerable<string> only = null)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string bundleRoot = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(bundleRoot, b))).Where(b => b != null).ToList();
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build/models");
        Directory.CreateDirectory(output);
        try
        {
            Shader gameShader = loaded.SelectMany(b => b.LoadAllAssets<Shader>()).FirstOrDefault(s => s.name == "Game/Entity Tint Mask");
            foreach (string name in only ?? Names())
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/" + name + "/" + name + ".prefab");
                if (prefab == null)
                {
                    continue;
                }
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                List<GameObject> pieces = new List<GameObject>();
                string[] zombies = { "zjoe.prefab", "zcop.prefab", "znurse.prefab" };
                for (int i = 0; i < zombies.Length; i++)
                {
                    for (int view = 0; view < 2; view++)
                    {
                        GameObject z = Object.Instantiate(LoadVanilla(loaded, zombies[i]));
                        z.transform.position = new Vector3((i * 2 + view - 2.5f) * 1.05f, 0f, 0f);
                        z.transform.rotation = Quaternion.Euler(0f, view == 0 ? 160f : 20f, 0f);
                        pieces.AddRange(Attach(prefab, z.transform));
                    }
                }
                if (gameShader != null)
                {
                    foreach (MeshRenderer r in pieces.SelectMany(p => p.GetComponentsInChildren<MeshRenderer>()))
                    {
                        r.sharedMaterials = r.sharedMaterials.Select(m => ToGame(gameShader, m)).ToArray();
                    }
                }
                Bounds b = new Bounds(pieces[0].transform.position, Vector3.zero);
                foreach (GameObject p in pieces)
                {
                    foreach (Renderer r in p.GetComponentsInChildren<Renderer>())
                    {
                        b.Encapsulate(r.bounds);
                    }
                }
                Render(Path.Combine(output, name + ".png"), b);
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

    public static Material ToGame(Shader game, Material src)
    {
        Material m = new Material(game) { name = src.name + " (game)" };
        m.SetFloat("_Tint", 0f);
        m.SetColor("_Color", Color.white);
        m.SetFloat("_MacroAO", 1f);
        m.SetFloat("_EmissionMultiply", 1f);
        m.SetFloat("_Cutoff", 0.5f);
        m.SetTexture("_MainTex", src.GetTexture("_MainTex"));
        m.SetTexture("_Normal", src.GetTexture("_BumpMap"));
        m.SetTexture("_RMOM", src.GetTexture("_DetailMask"));
        m.EnableKeyword("_METALLICGLOSSMAP");
        m.EnableKeyword("_NORMALMAP");
        Texture emission = src.GetTexture("_EmissionMap");
        if (emission != null)
        {
            m.SetTexture("_Emissive", emission);
            m.EnableKeyword("_EMISSION");
            m.SetColor("_EmissionColor", new Color(2f, 2f, 2f));
        }
        else
        {
            m.SetColor("_EmissionColor", Color.black);
        }
        return m;
    }

    private static GameObject LoadVanilla(List<AssetBundle> loaded, string name)
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

    private static void Render(string path, Bounds focus)
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
        const int width = 2400, height = 900;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 24f;
        // Frame the pieces' height band across all six zombies
        float h = Mathf.Max(0.6f, focus.size.y * 1.6f);
        float w = 6.6f;
        float dist = Mathf.Max(h / (2f * Mathf.Tan(12f * Mathf.Deg2Rad)), w / (2f * Mathf.Tan(12f * Mathf.Deg2Rad) * width / height));
        camera.transform.position = new Vector3(0f, focus.center.y + 0.15f, -dist);
        camera.transform.LookAt(new Vector3(0f, focus.center.y, 0f));
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        File.WriteAllBytes(path, read.EncodeToPNG());
    }

    /// <summary>Command line: Build/closeups/&lt;Name&gt;.png for every model (or just `only`): a close look on Joe from
    /// the front and from behind, framed on the model (the Snatcher's sack shown full).</summary>
    public static void Closeups()
    {
        CloseupsOf(null);
    }

    public static void CloseupsOf(IEnumerable<string> only)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string bundleRoot = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(bundleRoot, b))).Where(b => b != null).ToList();
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build/closeups");
        Directory.CreateDirectory(output);
        const int size = 800;
        try
        {
            Shader gameShader = loaded.SelectMany(b => b.LoadAllAssets<Shader>()).FirstOrDefault(s => s.name == "Game/Entity Tint Mask");
            foreach (string name in only ?? Names())
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/" + name + "/" + name + ".prefab");
                if (prefab == null)
                {
                    continue;
                }
                // Kept through the new scenes below, which unload unused assets
                Texture2D sheet = new Texture2D(size * 2, size, TextureFormat.RGB24, false) { hideFlags = HideFlags.HideAndDontSave };
                for (int view = 0; view < 2; view++)
                {
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    GameObject z = Object.Instantiate(LoadVanilla(loaded, "zjoe.prefab"));
                    z.transform.rotation = Quaternion.Euler(0f, view == 0 ? 155f : 25f, 0f);
                    List<GameObject> pieces = Attach(prefab, z.transform);
                    foreach (GameObject empty in pieces.Where(p => p.name.EndsWith("#Sack")).ToList())
                    {
                        pieces.Remove(empty);
                        Object.DestroyImmediate(empty);
                    }
                    if (gameShader != null)
                    {
                        foreach (MeshRenderer r in pieces.SelectMany(p => p.GetComponentsInChildren<MeshRenderer>()))
                        {
                            r.sharedMaterials = r.sharedMaterials.Select(m => ToGame(gameShader, m)).ToArray();
                        }
                    }
                    Bounds b = new Bounds(pieces[0].transform.position, Vector3.zero);
                    foreach (Renderer r in pieces.SelectMany(p => p.GetComponentsInChildren<Renderer>()))
                    {
                        b.Encapsulate(r.bounds);
                    }
                    Texture2D shot = Shot(b, size);
                    sheet.SetPixels(view * size, 0, size, size, shot.GetPixels());
                }
                sheet.Apply();
                File.WriteAllBytes(Path.Combine(output, name + ".png"), sheet.EncodeToPNG());
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

    /// <summary>A square render framed on `focus` (at least 45 cm across, so a small prop shows where it sits).</summary>
    private static Texture2D Shot(Bounds focus, int size)
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
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 24f;
        float frame = Mathf.Max(0.45f, Mathf.Max(focus.size.x, focus.size.y) * 1.4f);
        float dist = frame / (2f * Mathf.Tan(12f * Mathf.Deg2Rad));
        camera.transform.position = focus.center + new Vector3(0f, 0.08f, -dist);
        camera.transform.LookAt(focus.center);
        RenderTexture target = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(size, size, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
        RenderTexture.active = null;
        return read;
    }

    /// <summary>Command line: build and preview only the models named in the ZED_MODELS environment variable
    /// (comma separated).</summary>
    public static void BuildAndPreviewSome()
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        List<string> some = (System.Environment.GetEnvironmentVariable("ZED_MODELS") ?? "").Split(',')
            .Select(x => x.Trim()).Where(x => x.Length > 0).ToList();
        foreach (string n in some)
        {
            MakePrefab(n);
        }
        AssetDatabase.SaveAssets();
        Preview(some);
        CloseupsOf(some);
    }

    /// <summary>Command line: build the model prefabs and preview them all.</summary>
    public static void BuildAndPreviewModels()
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        BuildAll();
        AssetDatabase.SaveAssets();
        Preview();
    }
}
