using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Close-ups of plants in the game's plant shader, framed the way a player sees one up close, for judging their
/// textures and materials (NatureBuilder's sheets frame a plant whole, from a few meters off): for each plant
/// Build/plants/&lt;Name&gt;_stand.png (standing an arm's length or two away, in sun), _crouch.png (crouched),
/// _macro.png (leaning in), _back.png (crouched on the far side) and _low.png (leaning in, the sun low and raking across, which shows what the normal map
/// carries), each 1600 x 900 at a 60 degree field of view, about what a 1080p screen shows. The editor stage's
/// ambient light is far weaker than the game's, so shade can't be judged here.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureCloseups.Run -plants MossyLog,Bolete
/// (it builds the bundle and NatureBuilder's previews of those plants first).
/// </summary>
public static class NatureCloseups
{
    private static readonly string[] GameBundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "automatic_assets_entities/plants.bundle",
    };

    public static void Run()
    {
        NatureBuilder.BuildAndPreview();
        string[] args = System.Environment.GetCommandLineArgs();
        int only = System.Array.IndexOf(args, "-plants");
        if (only < 0 || only + 1 >= args.Length)
        {
            Debug.LogWarning("[NatureCloseups] no -plants given; nothing to frame");
            return;
        }
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build", "plants");
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
            if (shader == null)
            {
                Debug.LogError("[NatureCloseups] could not load the game's plant shader");
                return;
            }
            foreach (string name in args[only + 1].Split(','))
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/NatureExpanded/Prefabs/" + name + ".prefab");
                if (prefab == null)
                {
                    Debug.LogWarning("[NatureCloseups] no prefab for " + name);
                    continue;
                }
                Frame(name, prefab, shader, output);
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

    private static void Frame(string name, GameObject prefab, Shader shader, string output)
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        NatureBuilder.Stage(10f);
        GameObject go = Object.Instantiate(prefab);
        go.transform.rotation = Quaternion.Euler(0f, 20f, 0f);
        Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
        foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
        {
            if (!converted.TryGetValue(r.sharedMaterial, out Material dst))
            {
                dst = NatureBuilder.ToGame(shader, r.sharedMaterial);
                converted[r.sharedMaterial] = dst;
            }
            r.sharedMaterial = dst;
        }
        go.GetComponent<LODGroup>()?.ForceLOD(0);
        Bounds b = go.GetComponentInChildren<MeshRenderer>().bounds;
        Vector3 c = b.center;
        float r0 = Mathf.Max(b.extents.x, b.extents.z);
        Vector3 away = new Vector3(0.35f, 0f, -1f).normalized;
        const float ground = -0.5f;
        Vector3 Eye(float dist, float height) => new Vector3(c.x, ground + height, c.z) + away * dist;
        const int width = 1600, height = 900;
        Light sun = Object.FindObjectsOfType<Light>().FirstOrDefault(l => l.type == LightType.Directional);

        Write(output, name + "_stand", NatureBuilder.Shot(Eye(r0 + 1.0f, 1.6f), c, 60f, width, height));
        Write(output, name + "_crouch", NatureBuilder.Shot(Eye(r0 * 0.6f + 0.55f, 0.85f), c, 60f, width, height));
        Write(output, name + "_macro", NatureBuilder.Shot(Eye(r0 * 0.25f + 0.32f, 0.45f), c, 60f, width, height));
        // The far side, crouched
        Write(output, name + "_back", NatureBuilder.Shot(new Vector3(c.x, ground + 0.85f, c.z) - away * (r0 * 0.6f + 0.55f), c, 60f,
            width, height));
        if (sun != null)
        {
            // Evening sun raking across from the side: shows what the normal maps carry
            Quaternion noon = sun.transform.rotation;
            sun.transform.rotation = Quaternion.Euler(14f, 75f, 0f);
            Write(output, name + "_low", NatureBuilder.Shot(Eye(r0 * 0.25f + 0.32f, 0.45f), c, 60f, width, height));
            sun.transform.rotation = noon;
        }
        Object.DestroyImmediate(go);
    }

    private static void Write(string output, string name, Texture2D shot)
    {
        File.WriteAllBytes(Path.Combine(output, name + ".png"), shot.EncodeToPNG());
        Debug.Log("[NatureCloseups] Wrote " + name + ".png");
    }
}
