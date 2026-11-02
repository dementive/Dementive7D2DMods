using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Renders vanilla zombies (loaded from the game's bundles, nothing copied) with the overlay looks to
/// Build/look-test.png: plain, wounded, charred, frosted and toxic.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod LookTest.Run (with graphics).
/// </summary>
public static class LookTest
{
    private static readonly string[] Bundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
        "zombies_assets_entities/zombies/cop.bundle",
    };

    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject joe = Load(loaded, "zjoe.prefab");
            GameObject cop = Load(loaded, "zcop.prefab");
            Shader overlay = AssetDatabase.LoadAssetAtPath<Shader>("Assets/ZombiesExpanded/Shaders/ZombieOverlay.shader");
            var looks = new (GameObject prefab, System.Action<Material, GameObject> setup)[]
            {
                (joe, null),
                (joe, (m, z) => { m.SetFloat("_Grime", 0.6f); m.SetFloat("_Blood", 0.5f); Wounds(m, z); }),
                (cop, (m, z) => { m.SetFloat("_Char", 0.75f); m.SetFloat("_Embers", 1f); }),
                (joe, (m, z) => { m.SetFloat("_Frost", 0.55f); m.SetFloat("_Wet", 0.3f); }),
                (cop, (m, z) => { m.SetFloat("_Veins", 0.7f); m.SetFloat("_Grime", 0.4f); m.SetColor("_GrimeColor", new Color(0.18f, 0.22f, 0.1f)); }),
                (joe, (m, z) => { m.SetFloat("_Wet", 0.8f); m.SetFloat("_Grime", 0.7f); m.SetColor("_GrimeColor", new Color(0.3f, 0.24f, 0.17f)); }),
            };
            List<GameObject> lineup = new List<GameObject>();
            for (int i = 0; i < looks.Length; i++)
            {
                GameObject z = Object.Instantiate(looks[i].prefab);
                z.transform.position = new Vector3((i - (looks.Length - 1) / 2f) * 1.25f, 0f, 0f);
                z.transform.rotation = Quaternion.Euler(0f, 180f, 0f);
                Pose(z);
                if (looks[i].setup != null)
                {
                    Material m = new Material(overlay);
                    m.SetFloat("_Seed", i * 3.1f);
                    looks[i].setup(m, z);
                    foreach (SkinnedMeshRenderer r in z.GetComponentsInChildren<SkinnedMeshRenderer>(true).Where(r => r.name.Contains("LOD")))
                    {
                        r.sharedMaterials = r.sharedMaterials.Concat(new[] { m }).ToArray();
                    }
                }
                lineup.Add(z);
            }
            Render(Path.Combine(Directory.GetCurrentDirectory(), "Build/look-test.png"));
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    /// <summary>Bone-scale body shapes on vanilla zombies to Build/body-test.png.</summary>
    public static void Bodies()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject joe = Load(loaded, "zjoe.prefab");
            var shapes = new System.Action<GameObject>[]
            {
                z => { },
                z => { // hulking
                    z.transform.localScale = Vector3.one * 1.12f;
                    Scale(z, "Spine2", new Vector3(1.18f, 1.05f, 1.15f));
                    Scale(z, "Neck", new Vector3(0.9f, 0.95f, 0.9f));
                    foreach (string a in new[] { "LeftArm", "RightArm" }) Scale(z, a, new Vector3(1.05f, 1.3f, 1.3f));
                    foreach (string a in new[] { "LeftHand", "RightHand" }) Scale(z, a, new Vector3(1.0f, 0.95f, 0.95f));
                },
                z => { // gaunt
                    Scale(z, "Spine1", new Vector3(0.86f, 1.0f, 0.82f));
                    Scale(z, "Neck", new Vector3(1.1f, 1.0f, 1.15f));
                    foreach (string a in new[] { "LeftArm", "RightArm" }) Scale(z, a, new Vector3(1.0f, 0.75f, 0.75f));
                    foreach (string a in new[] { "LeftHand", "RightHand" }) Scale(z, a, new Vector3(1.0f, 1.25f, 1.25f));
                    foreach (string a in new[] { "LeftUpLeg", "RightUpLeg" }) Scale(z, a, new Vector3(0.8f, 1.0f, 0.8f));
                },
                z => { // bloated
                    Scale(z, "Spine", new Vector3(1.3f, 1.0f, 1.45f));
                    Scale(z, "Spine2", new Vector3(0.9f, 1.0f, 0.82f));
                    Scale(z, "Neck", new Vector3(0.95f, 1.0f, 0.95f));
                },
                z => { // big head, hunched
                    Scale(z, "Head", Vector3.one * 1.18f);
                    Bone(z, "Spine3").localRotation *= Quaternion.Euler(18f, 0f, 0f);
                    Bone(z, "Neck").localRotation *= Quaternion.Euler(-14f, 0f, 0f);
                },
                z => { z.transform.localScale = Vector3.one * 0.9f; },
            };
            for (int i = 0; i < shapes.Length; i++)
            {
                GameObject z = Object.Instantiate(joe);
                z.transform.position = new Vector3((i - (shapes.Length - 1) / 2f) * 1.25f, 0f, 0f);
                z.transform.rotation = Quaternion.Euler(0f, 180f - 25f, 0f);
                Pose(z);
                shapes[i](z);
            }
            Render(Path.Combine(Directory.GetCurrentDirectory(), "Build/body-test.png"));
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    private static Transform Bone(GameObject z, string name) => z.GetComponentsInChildren<Transform>().First(t => t.name == name);

    private static void Scale(GameObject z, string name, Vector3 scale) => Bone(z, name).localScale = scale;

    /// <summary>The zombie models the game ships but no longer spawns, to Build/unused-zombies.png.</summary>
    public static void Unused()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string[] bundles =
        {
            "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
            "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
            "zombies_assets_entities/zombies/sand.bundle", "zombies_assets_entities/zombies/snow.bundle",
            "zombies_assets_entities/zombies/frostclaw.bundle", "zombies_assets_entities/zombies/plaguespitter.bundle",
            "zombies_assets_entities/zombies/crawler.bundle",
        };
        List<AssetBundle> loaded = bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        foreach (string f in Directory.GetFiles(Path.Combine(root, "zombies_assets_entities/zombies"), "*.bundle"))
        {
            if (!bundles.Any(b => f.Replace("\\", "/").EndsWith(b)))
            {
                AssetBundle extra = AssetBundle.LoadFromFile(f);
                if (extra != null)
                {
                    loaded.Add(extra);
                }
            }
        }
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            string[] names = { "zjoe.prefab", "zsand.prefab", "zsnow.prefab", "zfrostclaw.prefab", "zplaguespitter.prefab", "zcrawlerradiated.prefab" };
            for (int i = 0; i < names.Length; i++)
            {
                GameObject z = Object.Instantiate(Load(loaded, names[i]));
                foreach (Renderer r in z.GetComponentsInChildren<Renderer>(true))
                {
                    Debug.Log("UNUSED " + names[i] + " " + r.name + " enabled " + r.enabled + " active " + r.gameObject.activeInHierarchy
                        + " mesh " + (r is SkinnedMeshRenderer sm ? (sm.sharedMesh == null ? "NULL" : sm.sharedMesh.name + " " + sm.sharedMesh.vertexCount) : "-")
                        + " mats " + string.Join(",", r.sharedMaterials.Select(m => m == null ? "NULL" : m.name + "/" + m.shader.name)) + " bounds " + r.bounds);
                }
                z.transform.position = new Vector3((i - (names.Length - 1) / 2f) * 1.35f, 0f, 0f);
                z.transform.rotation = Quaternion.Euler(0f, 180f - 20f, 0f);
                Pose(z);
            }
            Render(Path.Combine(Directory.GetCurrentDirectory(), "Build/unused-zombies.png"));
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    /// <summary>Every vanilla zombie's head, to see which already wear something on it: Build/heads.png.</summary>
    public static void Heads()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = new[] { "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle" }
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        foreach (string f in Directory.GetFiles(Path.Combine(root, "zombies_assets_entities/zombies"), "*.bundle"))
        {
            AssetBundle b = AssetBundle.LoadFromFile(f);
            if (b != null)
            {
                loaded.Add(b);
            }
        }
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            List<string> names = new List<string>();
            foreach (AssetBundle b in loaded)
            {
                names.AddRange(b.GetAllAssetNames().Where(n =>
                {
                    string file = System.IO.Path.GetFileName(n).ToLowerInvariant();
                    return n.ToLowerInvariant().Contains("assets/assetbundles/zombies/") && file.StartsWith("z") && file.EndsWith(".prefab")
                        && !file.Contains("feral") && !file.Contains("radiated") && !n.ToLowerInvariant().Contains("dismember");
                }));
            }
            names = names.Distinct().OrderBy(n => n).ToList();
            int cols = 10;
            for (int i = 0; i < names.Count; i++)
            {
                GameObject prefab = null;
                foreach (AssetBundle b in loaded)
                {
                    if (b.GetAllAssetNames().Contains(names[i]))
                    {
                        prefab = b.LoadAsset<GameObject>(names[i]);
                        break;
                    }
                }
                if (prefab == null)
                {
                    continue;
                }
                GameObject z = Object.Instantiate(prefab);
                Transform head = z.GetComponentsInChildren<Transform>().FirstOrDefault(t => t.name == "Head");
                float hy = head != null ? head.position.y : 1.7f;
                z.transform.position = new Vector3((i % cols) * 0.8f, -(i / cols) * 0.75f - hy + 3f, -(i / cols) * 1.0f);
                z.transform.rotation = Quaternion.Euler(0f, 160f, 0f);
                Debug.Log("[Heads] " + i + " " + System.IO.Path.GetFileNameWithoutExtension(names[i]));
            }
            Light sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.intensity = 1.3f;
            sun.transform.rotation = Quaternion.Euler(30f, 20f, 0f);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.45f, 0.45f, 0.5f);
            const int width = 2400, height = 1000;
            Camera camera = new GameObject("Camera").AddComponent<Camera>();
            camera.renderingPath = RenderingPath.DeferredShading;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
            camera.orthographic = true;
            camera.orthographicSize = 2.05f;
            camera.transform.position = new Vector3((cols - 1) * 0.4f, 1.55f, -12f);
            RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
            read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
            RenderTexture.active = null;
            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build/heads.png"), read.EncodeToPNG());
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
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

    /// <summary>Arms down from the bind pose so the torso shows.</summary>
    private static void Pose(GameObject z)
    {
        foreach (Transform t in z.GetComponentsInChildren<Transform>())
        {
            if (t.name == "LeftArm")
            {
                t.localRotation *= Quaternion.Euler(0f, 0f, -65f);
            }
            else if (t.name == "RightArm")
            {
                t.localRotation *= Quaternion.Euler(0f, 0f, -65f);
            }
        }
    }

    private static void Wounds(Material m, GameObject z)
    {
        Transform[] bones = z.GetComponentsInChildren<Transform>();
        Transform Bone(string n) => bones.First(b => b.name == n);
        Vector3 front = z.transform.forward;
        Vector4[] w =
        {
            Bone("Spine2").position + front * 0.17f + Vector3.up * 0.05f,
            Bone("Spine1").position + front * 0.15f + z.transform.right * 0.1f,
            Bone("Head").position + front * 0.1f + Vector3.up * 0.08f,
            Bone("LeftUpLeg").position + front * 0.09f + Vector3.down * 0.2f,
        };
        float[] radius = { 0.09f, 0.06f, 0.05f, 0.07f };
        Vector4[] arr = new Vector4[8];
        for (int i = 0; i < w.Length; i++)
        {
            arr[i] = new Vector4(w[i].x, w[i].y, w[i].z, radius[i]);
        }
        m.SetVectorArray("_Wounds", arr);
        m.SetFloat("_WoundCount", w.Length);
    }

    private static void Render(string path)
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

        const int width = 2400, height = 1100;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 26f;
        camera.transform.position = new Vector3(0f, 1.25f, -8f);
        camera.transform.LookAt(new Vector3(0f, 1.0f, 0f));
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        File.WriteAllBytes(path, read.EncodeToPNG());
    }
}
