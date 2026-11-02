using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Loads vanilla trap models straight from the game's asset bundles (built with this same Unity version) and
/// compares them with ours: writes every material's shader, keywords and properties plus texture value statistics
/// to Build/vanilla-materials.txt, and renders the vanilla traps beside ours under one light to
/// Build/vanilla-compare.png. Reference only: nothing from the game is copied into the mod.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod VanillaCompare.Run (with graphics).
/// </summary>
public static class VanillaCompare
{
    private static readonly string[] Bundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "automatic_assets_entities/electrical.bundle", "automatic_assets_entities/traps.bundle",
    };

    private static readonly string[] Prefabs =
    {
        "arrowtrapprefab.prefab", "trapspinningbladeprefab.prefab", "autoturretsmgprefab.prefab",
        "generatorbankaprefab.prefab", "battery_bankprefab.prefab", "electric_fenceprefab.prefab",
    };

    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        StringBuilder log = new StringBuilder();

        List<AssetBundle> loaded = new List<AssetBundle>();
        foreach (string b in Bundles)
        {
            AssetBundle bundle = AssetBundle.LoadFromFile(Path.Combine(root, b));
            log.AppendLine("bundle " + b + ": " + (bundle != null ? "loaded" : "FAILED"));
            if (bundle != null)
            {
                loaded.Add(bundle);
                string[] names = bundle.GetAllAssetNames();
                log.AppendLine("  " + names.Length + " assets");
            }
        }

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        List<GameObject> lineup = new List<GameObject>();
        foreach (string name in Prefabs)
        {
            GameObject prefab = null;
            foreach (AssetBundle bundle in loaded)
            {
                string path = bundle.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + name));
                if (path != null)
                {
                    prefab = bundle.LoadAsset<GameObject>(path);
                    break;
                }
            }
            if (prefab == null)
            {
                log.AppendLine("prefab " + name + ": NOT FOUND");
                continue;
            }
            log.AppendLine();
            log.AppendLine("==== " + name);
            DescribeRenderers(prefab, log);
            lineup.Add(Object.Instantiate(prefab));
        }

        GameObject ours = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/TrapsExpanded/TeslaCoil/TeslaCoil.prefab");
        log.AppendLine();
        log.AppendLine("==== OURS TeslaCoil");
        DescribeRenderers(ours, log);
        GameObject oursInstance = Object.Instantiate(ours);

        File.WriteAllText(Path.Combine(output, "vanilla-materials.txt"), log.ToString());
        Render(lineup, oursInstance, Path.Combine(output, "vanilla-compare.png"));

        // The game's model shader, and how it reads _RMOM: spheres with one channel varied at a time
        Shader gameShader = lineup.SelectMany(o => o.GetComponentsInChildren<Renderer>(true)).SelectMany(r => r.sharedMaterials)
            .Where(m => m != null).Select(m => m.shader).FirstOrDefault(sh => sh.name == "Game/Entity Tint Mask");
        if (gameShader != null)
        {
            foreach (GameObject o in lineup)
            {
                o.SetActive(false);
            }
            oursInstance.SetActive(false);
            RmomTest(gameShader, Path.Combine(output, "rmom-test.png"));
            CloseCompare(lineup, ours, gameShader, Path.Combine(output, "close-compare.png"));
        }
        foreach (AssetBundle bundle in loaded)
        {
            bundle.Unload(false);
        }
        Debug.Log("[VanillaCompare] done");
    }

    /// <summary>
    /// Our material in the game's model shader, set up exactly as the mod's GameShaderDEM does in game: textures
    /// from the Standard material (albedo, normal, RMOM in _DetailMask, emission) and the property values the
    /// vanilla trap materials use.
    /// </summary>
    public static Material ToGame(Shader game, Material src, bool lampOn)
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
        }
        m.SetColor("_EmissionColor", emission != null && lampOn ? new Color(2.5f, 2.5f, 2.5f) : Color.black);
        return m;
    }

    /// <summary>
    /// The build preview: our prefab in the game's shader between the vanilla dart trap and generator, under one
    /// light, from the front and from behind.
    /// </summary>
    public static void Preview(string prefabPath, string path)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject Vanilla(string name)
            {
                foreach (AssetBundle bundle in loaded)
                {
                    string asset = bundle.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + name));
                    if (asset != null)
                    {
                        return Object.Instantiate(bundle.LoadAsset<GameObject>(asset));
                    }
                }
                return null;
            }
            GameObject dart = Vanilla("arrowtrapprefab.prefab");
            GameObject generator = Vanilla("generatorbankaprefab.prefab");
            Shader shader = dart.GetComponentInChildren<MeshRenderer>(true).sharedMaterial.shader;
            GameObject ours = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath));
            foreach (MeshRenderer r in ours.GetComponentsInChildren<MeshRenderer>(true))
            {
                r.sharedMaterials = r.sharedMaterials.Select(m => ToGame(shader, m, true)).ToArray();
            }
            // Effects mid-burst, as they look in game
            foreach (ParticleSystem ps in ours.GetComponentsInChildren<ParticleSystem>(true))
            {
                if (ps.transform.parent == null || ps.transform.parent.GetComponent<ParticleSystem>() == null)
                {
                    ps.Simulate(0.4f, true, true);
                }
            }
            dart.transform.position = new Vector3(-1.3f, 0f, 0f);
            ours.transform.position = Vector3.zero;
            generator.transform.position = new Vector3(1.3f, 0f, 0f);
            Stage();
            const int width = 1300, height = 1000;
            Texture2D sheet = new Texture2D(width * 2, height, TextureFormat.RGB24, false);
            Vector3[] views = { new Vector3(1.4f, 1.5f, -3.9f), new Vector3(-1.6f, 1.9f, 3.7f) };
            for (int i = 0; i < views.Length; i++)
            {
                Texture2D shot = Shot(views[i], new Vector3(0f, 0.4f, 0f), 34f, width, height, null);
                sheet.SetPixels(i * width, 0, width, height, shot.GetPixels());
            }
            File.WriteAllBytes(path, sheet.EncodeToPNG());
            Debug.Log("[VanillaCompare] Wrote " + path);
        }
        finally
        {
            foreach (AssetBundle bundle in loaded)
            {
                bundle.Unload(true);
            }
        }
    }

    /// <summary>
    /// Writes every transform of a vanilla prefab (position and rotation relative to its root, and its components)
    /// to a text file, and renders it like Preview: for traps that reuse a vanilla model, to find its parts.
    /// </summary>
    public static void DumpVanilla(string prefabFile, string textPath, string imagePath)
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject go = null;
            foreach (AssetBundle bundle in loaded)
            {
                string asset = bundle.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + prefabFile));
                if (asset != null)
                {
                    go = Object.Instantiate(bundle.LoadAsset<GameObject>(asset));
                    break;
                }
            }
            if (go == null)
            {
                File.WriteAllText(textPath, "not found: " + prefabFile);
                return;
            }
            StringBuilder log = new StringBuilder();
            foreach (Transform t in go.GetComponentsInChildren<Transform>(true))
            {
                string path = t.name;
                for (Transform p = t.parent; p != null && p != go.transform.parent; p = p.parent)
                {
                    path = p.name + "/" + path;
                }
                Vector3 pos = go.transform.InverseTransformPoint(t.position);
                Vector3 fwd = go.transform.InverseTransformDirection(t.forward);
                string comps = string.Join(", ", t.GetComponents<Component>().Where(c => c != null && !(c is Transform))
                    .Select(c => c.GetType().Name));
                Renderer r = t.GetComponent<Renderer>();
                string b = r != null ? " bounds " + r.bounds.center.ToString("F2") + " size " + r.bounds.size.ToString("F2") : "";
                log.AppendLine(path + " at " + pos.ToString("F3") + " fwd " + fwd.ToString("F2") + " [" + comps + "]" + b);
            }
            File.WriteAllText(textPath, log.ToString());
            Stage();
            go.transform.position = Vector3.zero;
            const int width = 1300, height = 1000;
            Texture2D sheet = new Texture2D(width * 2, height, TextureFormat.RGB24, false);
            Vector3[] views = { new Vector3(1.8f, 2.2f, -4.6f), new Vector3(3.5f, 1.6f, 1.5f) };
            for (int i = 0; i < views.Length; i++)
            {
                Texture2D shot = Shot(views[i], new Vector3(0f, 0.6f, 0.4f), 34f, width, height, null);
                sheet.SetPixels(i * width, 0, width, height, shot.GetPixels());
            }
            File.WriteAllBytes(imagePath, sheet.EncodeToPNG());
        }
        finally
        {
            foreach (AssetBundle bundle in loaded)
            {
                bundle.Unload(true);
            }
        }
    }

    /// <summary>
    /// Side and front views of the vanilla flamethrower trap with a 0.25 m grid and red markers where the Flame
    /// Vent's C# puts its nozzle (FlameVentDEM's NozzleOffset), to check the flame comes out of the nozzles.
    /// </summary>
    public static void FlameNozzles()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            Debug.Log("[FlameNozzles] root " + root + " loaded " + loaded.Count + ": " + string.Join(", ", loaded.Select(b => b.name)));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (AssetBundle bundle in loaded)
            {
                string asset = bundle.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/flamethrowertrapprefab.prefab"));
                if (asset != null)
                {
                    GameObject ft = Object.Instantiate(bundle.LoadAsset<GameObject>(asset));
                    foreach (Renderer r in ft.GetComponentsInChildren<Renderer>(true))
                    {
                        Debug.Log("[FlameNozzles] " + r.name + " enabled " + r.enabled + " active " + r.gameObject.activeInHierarchy
                            + " bounds " + r.bounds.center.ToString("F2") + " " + r.bounds.size.ToString("F2") + " shader "
                            + (r.sharedMaterial != null ? r.sharedMaterial.shader.name + " " + r.sharedMaterial.shader.isSupported : "none"));
                    }
                    LODGroup lod = ft.GetComponent<LODGroup>();
                    if (lod != null)
                    {
                        lod.ForceLOD(0);
                    }
                }
            }
            Material red = new Material(Shader.Find("Unlit/Color")) { color = Color.red };
            Material grid = new Material(Shader.Find("Unlit/Color")) { color = new Color(0f, 0.6f, 1f) };
            for (float v = -1.75f; v <= 1.76f; v += 0.25f)
            {
                GameObject h = GameObject.CreatePrimitive(PrimitiveType.Cube);
                h.transform.localScale = new Vector3(0.002f, 0.004f, 4f);
                h.transform.position = new Vector3(0.6f, v, 0f);
                h.GetComponent<Renderer>().sharedMaterial = grid;
                GameObject z = GameObject.CreatePrimitive(PrimitiveType.Cube);
                z.transform.localScale = new Vector3(0.002f, 4f, 0.004f);
                z.transform.position = new Vector3(0.6f, 0f, v);
                z.GetComponent<Renderer>().sharedMaterial = grid;
            }
            foreach (Vector3 p in new[] { new Vector3(0f, 0.38f, -1.45f), new Vector3(0f, 0.73f, -1.45f), new Vector3(0f, 1.02f, -1.45f) })
            {
                GameObject s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                s.transform.localScale = Vector3.one * 0.06f;
                s.transform.position = p;
                s.GetComponent<Renderer>().sharedMaterial = red;
            }
            Stage();
            const int size = 1000;
            Texture2D sheet = new Texture2D(size * 2, size, TextureFormat.RGB24, false);
            // From far away through a narrow lens: next to no perspective, so the grid can be read off
            Texture2D side = Shot(new Vector3(60f, 0.3f, -0.5f), new Vector3(0f, 0.3f, -0.5f), 2.2f, size, size, null);
            Texture2D front = Shot(new Vector3(0f, 0.3f, -60f), new Vector3(0f, 0.3f, -0.5f), 2.2f, size, size, null);
            sheet.SetPixels(0, 0, size, size, side.GetPixels());
            sheet.SetPixels(size, 0, size, size, front.GetPixels());
            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build/flamethrower-nozzles.png"), sheet.EncodeToPNG());
        }
        finally
        {
            foreach (AssetBundle bundle in loaded)
            {
                bundle.Unload(true);
            }
        }
    }

    /// <summary>Renders each of the mod's effect prefabs close up, mid-effect, by day and by night, in a grid of
    /// tiles (day left, night right), to check how they read before they go in game.</summary>
    public static void FxSheet(List<string> prefabPaths, string path)
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = new Color(0.32f, 0.3f, 0.27f) };
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
        Camera cam = new GameObject("FxCam").AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.fieldOfView = 40f;
        const int w = 420, h = 320, cols = 3;
        RenderTexture rt = new RenderTexture(w, h, 24);
        cam.targetTexture = rt;
        int rows = (prefabPaths.Count + cols - 1) / cols;
        Texture2D sheet = new Texture2D(w * 2 * cols, h * rows, TextureFormat.RGB24, false);
        for (int i = 0; i < prefabPaths.Count; i++)
        {
            string n = Path.GetFileNameWithoutExtension(prefabPaths[i]);
            GameObject fx = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPaths[i]));
            // Things that fly or hang on a zombie at chest height, the rest on the ground; jets and projectiles point
            // to the right so their length shows
            bool flying = n.StartsWith("Flame") || n.Contains("Arrow") || n.Contains("Bolt") || n.Contains("Glob");
            bool raised = flying || n.Contains("Drip") || n == "FrostCrust" || n == "FrostMist";
            // Jets start at their origin and go right; projectiles trail back from their tip at the origin
            float x = n.StartsWith("Flame") ? -1.2f : flying ? 0.45f : 0f;
            fx.transform.position = new Vector3(x, raised ? 1f : 0.02f, 0f);
            fx.transform.rotation = flying ? Quaternion.Euler(0f, 90f, 0f) : Quaternion.identity;
            foreach (ParticleSystem ps in fx.GetComponentsInChildren<ParticleSystem>(true))
            {
                if (ps.transform.parent == null || ps.transform.parent.GetComponent<ParticleSystem>() == null)
                {
                    ps.Simulate(n == "IcePatch" ? 1f : 0.6f, true, true);
                }
            }
            float dist = n.StartsWith("FlameJetLong") ? 9f : n.StartsWith("Flame") || n == "IcePatch" ? 5f : flying ? 1.3f : 3f;
            cam.transform.position = new Vector3(n.StartsWith("Flame") ? 1.5f : 0f, 1.6f, -dist);
            cam.transform.LookAt(new Vector3(cam.transform.position.x, raised ? 1f : 0.4f, 0f));
            for (int night = 0; night < 2; night++)
            {
                sun.intensity = night == 0 ? 1.3f : 0.05f;
                RenderSettings.ambientLight = night == 0 ? new Color(0.5f, 0.52f, 0.58f) : new Color(0.03f, 0.03f, 0.05f);
                cam.backgroundColor = night == 0 ? new Color(0.55f, 0.62f, 0.72f) : new Color(0.02f, 0.025f, 0.04f);
                cam.Render();
                RenderTexture.active = rt;
                Texture2D shot = new Texture2D(w, h, TextureFormat.RGB24, false);
                shot.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                int col = i % cols, row = rows - 1 - i / cols;
                sheet.SetPixels((col * 2 + night) * w, row * h, w, h, shot.GetPixels());
            }
            Object.DestroyImmediate(fx);
        }
        RenderTexture.active = null;
        File.WriteAllBytes(path, sheet.EncodeToPNG());
        Debug.Log("[VanillaCompare] Wrote " + path);
    }

    private static void Stage()
    {
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.93f, 0.84f);
        sun.intensity = 1.4f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.45f, 0.5f, 0.6f);
        RenderSettings.ambientEquatorColor = new Color(0.35f, 0.35f, 0.35f);
        RenderSettings.ambientGroundColor = new Color(0.18f, 0.17f, 0.15f);
        Camera probeCam = new GameObject("ProbeCam").AddComponent<Camera>();
        probeCam.clearFlags = CameraClearFlags.SolidColor;
        probeCam.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        probeCam.cullingMask = 0;
        Cubemap sky = new Cubemap(64, TextureFormat.RGBAHalf, false);
        probeCam.RenderToCubemap(sky);
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
        RenderSettings.customReflectionTexture = sky;
        Object.DestroyImmediate(probeCam.gameObject);
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.transform.position = new Vector3(0f, -0.5f, 0f);
        floor.transform.localScale = new Vector3(3f, 1f, 3f);
        floor.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = new Color(0.3f, 0.29f, 0.27f) };
    }

    private static Texture2D Flat(Color c)
    {
        Texture2D t = new Texture2D(4, 4, TextureFormat.RGBA32, false, true);
        t.SetPixels(Enumerable.Repeat(c, 16).ToArray());
        t.Apply();
        return t;
    }

    private static Material template;

    private static Material GameMaterial(Shader game, Texture albedo, Texture normal, Texture rmom)
    {
        Material m = template != null ? new Material(template) : new Material(game);
        m.SetTexture("_MainTex", albedo);
        m.SetTexture("_Normal", normal);
        m.SetTexture("_RMOM", rmom);
        m.EnableKeyword("_METALLICGLOSSMAP");
        m.EnableKeyword("_NORMALMAP");
        return m;
    }

    private static void RmomTest(Shader game, string path)
    {
        // Rows: R from 0 to 1 (metal 0), R from 0 to 1 (metal 1), B (occlusion?) from 0 to 1
        Texture2D grey = Flat(new Color(0.5f, 0.5f, 0.5f, 1f));
        List<GameObject> spheres = new List<GameObject>();
        for (int row = 0; row < 3; row++)
        {
            for (int i = 0; i < 5; i++)
            {
                float v = i / 4f;
                Color rmom = row == 0 ? new Color(v, 0f, 1f, 1f) : row == 1 ? new Color(v, 1f, 1f, 1f) : new Color(0.5f, 0f, v, 1f);
                GameObject s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                s.transform.position = new Vector3((i - 2) * 1.2f, 2.4f - row * 1.2f, 4f);
                s.GetComponent<Renderer>().sharedMaterial = GameMaterial(game, grey, Texture2D.normalTexture, Flat(rmom));
                spheres.Add(s);
            }
        }
        Shot(new Vector3(0f, 1.2f, -2.5f), new Vector3(0f, 1.2f, 4f), 40f, 1500, 900, path);
        foreach (GameObject s in spheres)
        {
            Object.DestroyImmediate(s);
        }
    }

    /// <summary>The dart trap, our coil in the game shader (both readings of the RMOM red channel), our coil in
    /// Standard, and the generator, up close.</summary>
    private static void CloseCompare(List<GameObject> lineup, GameObject ours, Shader game, string path)
    {
        template = lineup[0].GetComponentInChildren<MeshRenderer>(true).sharedMaterial;
        List<GameObject> row = new List<GameObject> { lineup[0] };
        foreach (bool unused in new[] { true })
        {
            GameObject coil = Object.Instantiate(ours);
            foreach (Renderer r in coil.GetComponentsInChildren<MeshRenderer>(true))
            {
                Material[] mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    mats[i] = ToGame(game, mats[i], true);
                }
                r.sharedMaterials = mats;
            }
            row.Add(coil);
        }
        row.Add(Object.Instantiate(ours));
        row.Add(lineup[3]);
        for (int i = 0; i < row.Count; i++)
        {
            row[i].SetActive(true);
            row[i].transform.position = new Vector3((i - (row.Count - 1) / 2f) * 1.25f, 0f, 0f);
        }
        Shot(new Vector3(0f, 1.6f, -5.2f), new Vector3(0f, 0.3f, 0f), 34f, 2400, 1100, path);
    }

    private static Texture2D Load(string assetPath)
    {
        Texture2D t = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        t.LoadImage(File.ReadAllBytes(assetPath));
        return t;
    }

    /// <summary>R = roughness (or smoothness), G = metallic, B = occlusion, A = 1, from our maps.</summary>
    private static Texture2D Rmom(Texture2D ms, Texture2D occ, bool roughness)
    {
        int w = ms.width, h = ms.height;
        Color[] a = ms.GetPixels();
        Color[] o = occ != null ? Resize(occ, w, h) : null;
        Color[] outp = new Color[a.Length];
        for (int i = 0; i < a.Length; i++)
        {
            float smooth = a[i].a;
            outp[i] = new Color(roughness ? 1f - smooth : smooth, a[i].r, o != null ? o[i].r : 1f, 1f);
        }
        Texture2D t = new Texture2D(w, h, TextureFormat.RGBA32, true, true);
        t.SetPixels(outp);
        t.Apply();
        return t;
    }

    private static Color[] Resize(Texture2D src, int w, int h)
    {
        RenderTexture rt = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        Graphics.Blit(src, rt);
        RenderTexture.active = rt;
        Texture2D read = new Texture2D(w, h, TextureFormat.RGBA32, false, true);
        read.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        RenderTexture.active = null;
        RenderTexture.ReleaseTemporary(rt);
        return read.GetPixels();
    }

    private static Texture2D Shot(Vector3 from, Vector3 at, float fov, int width, int height, string path)
    {
        Camera camera = new GameObject("ShotCam").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = fov;
        camera.transform.position = from;
        camera.transform.LookAt(at);
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        if (path != null)
        {
            File.WriteAllBytes(path, read.EncodeToPNG());
        }
        Object.DestroyImmediate(camera.gameObject);
        return read;
    }

    private static void DescribeRenderers(GameObject prefab, StringBuilder log)
    {
        foreach (Renderer r in prefab.GetComponentsInChildren<Renderer>(true))
        {
            log.AppendLine("renderer " + r.name + " (" + r.GetType().Name + ")");
            foreach (Material m in r.sharedMaterials)
            {
                if (m == null)
                {
                    continue;
                }
                Shader s = m.shader;
                log.AppendLine("  material " + m.name + " shader '" + s.name + "' queue " + m.renderQueue
                    + " keywords [" + string.Join(" ", m.shaderKeywords) + "]");
                for (int i = 0; i < s.GetPropertyCount(); i++)
                {
                    string prop = s.GetPropertyName(i);
                    switch (s.GetPropertyType(i))
                    {
                        case ShaderPropertyType.Float:
                        case ShaderPropertyType.Range:
                            log.AppendLine("    " + prop + " = " + m.GetFloat(prop).ToString("F3"));
                            break;
                        case ShaderPropertyType.Color:
                        case ShaderPropertyType.Vector:
                            log.AppendLine("    " + prop + " = " + m.GetVector(prop).ToString("F3"));
                            break;
                        case ShaderPropertyType.Texture:
                            Texture t = m.GetTexture(prop);
                            log.AppendLine("    " + prop + " = " + (t == null ? "none" : t.name + " " + t.width + "x"
                                + t.height + " " + (t is Texture2D t2 ? t2.format.ToString() : "")
                                + " st " + m.GetTextureScale(prop).ToString("F2")) + Stats(t));
                            break;
                    }
                }
            }
        }
    }

    /// <summary>Per-channel mean and 10th/90th percentiles of a texture (read back through a blit).</summary>
    private static string Stats(Texture t)
    {
        if (t == null || t.dimension != TextureDimension.Tex2D)
        {
            return "";
        }
        const int size = 128;
        RenderTexture rt = RenderTexture.GetTemporary(size, size, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        Graphics.Blit(t, rt);
        RenderTexture.active = rt;
        Texture2D read = new Texture2D(size, size, TextureFormat.RGBA32, false, true);
        read.ReadPixels(new Rect(0, 0, size, size), 0, 0);
        RenderTexture.active = null;
        RenderTexture.ReleaseTemporary(rt);
        Color[] px = read.GetPixels();
        Object.DestroyImmediate(read);
        StringBuilder sb = new StringBuilder("\n      stats");
        for (int c = 0; c < 4; c++)
        {
            float[] v = px.Select(p => p[c]).OrderBy(x => x).ToArray();
            sb.Append(" " + "RGBA"[c] + ": mean " + v.Average().ToString("F2") + " p10 " + v[v.Length / 10].ToString("F2")
                + " p90 " + v[v.Length * 9 / 10].ToString("F2"));
        }
        float[] sat = px.Select(p => Mathf.Max(p.r, Mathf.Max(p.g, p.b)) - Mathf.Min(p.r, Mathf.Min(p.g, p.b))).ToArray();
        sb.Append(" | chroma mean " + sat.Average().ToString("F2"));
        return sb.ToString();
    }

    private static void Render(List<GameObject> lineup, GameObject ours, string path)
    {
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.93f, 0.84f);
        sun.intensity = 1.4f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.45f, 0.5f, 0.6f);
        RenderSettings.ambientEquatorColor = new Color(0.35f, 0.35f, 0.35f);
        RenderSettings.ambientGroundColor = new Color(0.18f, 0.17f, 0.15f);

        Camera probeCam = new GameObject("ProbeCam").AddComponent<Camera>();
        probeCam.clearFlags = CameraClearFlags.SolidColor;
        probeCam.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        probeCam.cullingMask = 0;
        Cubemap sky = new Cubemap(64, TextureFormat.RGBAHalf, false);
        probeCam.RenderToCubemap(sky);
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
        RenderSettings.customReflectionTexture = sky;
        Object.DestroyImmediate(probeCam.gameObject);

        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.transform.position = new Vector3(0f, -0.5f, 0f);
        floor.transform.localScale = new Vector3(3f, 1f, 3f);
        floor.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = new Color(0.3f, 0.29f, 0.27f) };

        // Ours in the middle, the vanilla ones around it, 1.6 m apart
        List<GameObject> all = new List<GameObject>(lineup);
        all.Insert(all.Count / 2, ours);
        for (int i = 0; i < all.Count; i++)
        {
            all[i].transform.position = new Vector3((i - (all.Count - 1) / 2f) * 1.6f, 0f, 0f);
        }

        const int width = 2400, height = 900;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 30f;
        camera.transform.position = new Vector3(0f, 2.6f, -9.5f);
        camera.transform.LookAt(new Vector3(0f, 0.4f, 0f));
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
