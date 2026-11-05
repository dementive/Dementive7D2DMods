using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Loads the game's own plants and animals straight from its asset bundles (built with this same Unity version) and
/// writes how they're put together to Build/probe-plants.txt and Build/probe-animals.txt: every prefab, its renderers,
/// meshes, materials, shader keywords and properties, and for animals the skeleton, animator and colliders. Reference
/// only: nothing from the game is copied into the mod.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.Run
/// </summary>
public static class NatureProbe
{
    private static readonly string[] Shared =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
    };

    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        List<AssetBundle> loaded = Shared.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        try
        {
            Dump(root, "automatic_assets_entities/plants.bundle", Path.Combine(output, "probe-plants.txt"), false);
            Dump(root, "automatic_assets_entities/animals.bundle", Path.Combine(output, "probe-animals.txt"), true);
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    private static void Dump(string root, string bundleName, string path, bool deep)
    {
        AssetBundle bundle = AssetBundle.LoadFromFile(Path.Combine(root, bundleName));
        StringBuilder sb = new StringBuilder();
        if (bundle == null)
        {
            File.WriteAllText(path, "Could not load " + bundleName);
            return;
        }
        try
        {
            string[] names = bundle.GetAllAssetNames();
            sb.AppendLine(bundleName + ": " + names.Length + " assets");
            foreach (string n in names)
            {
                sb.AppendLine("  " + n);
            }
            HashSet<Material> seen = new HashSet<Material>();
            foreach (string n in names.Where(x => x.EndsWith(".prefab")))
            {
                GameObject go = bundle.LoadAsset<GameObject>(n);
                if (go == null)
                {
                    continue;
                }
                sb.AppendLine();
                sb.AppendLine("== " + n);
                foreach (Component c in go.GetComponents<Component>())
                {
                    sb.AppendLine("  component " + (c == null ? "missing" : c.GetType().Name));
                }
                foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
                {
                    Mesh mesh = r is SkinnedMeshRenderer smr ? smr.sharedMesh : r.TryGetComponent(out MeshFilter mf) ? mf.sharedMesh : null;
                    sb.AppendLine("  renderer " + Where(r.transform, go.transform) + " (" + r.GetType().Name + ") mesh "
                        + (mesh != null ? mesh.name + " verts " + mesh.vertexCount + " bounds " + mesh.bounds.size.ToString("F2")
                            + (mesh.colors32 != null && mesh.isReadable && mesh.colors32.Length > 0 ? " vcolors" : "") : "none")
                        + (r is SkinnedMeshRenderer s2 ? " bones " + s2.bones.Length : ""));
                    foreach (Material m in r.sharedMaterials)
                    {
                        if (m == null)
                        {
                            continue;
                        }
                        sb.AppendLine("    material " + m.name + " shader " + (m.shader != null ? m.shader.name : "none") + " queue " + m.renderQueue
                            + " keywords [" + string.Join(" ", m.shaderKeywords) + "]");
                        if (seen.Add(m) && m.shader != null)
                        {
                            Shader sh = m.shader;
                            for (int i = 0; i < sh.GetPropertyCount(); i++)
                            {
                                string p = sh.GetPropertyName(i);
                                ShaderPropertyType t = sh.GetPropertyType(i);
                                string v = t == ShaderPropertyType.Texture ? (m.GetTexture(p) != null ? m.GetTexture(p).name : "null")
                                    : t == ShaderPropertyType.Color ? m.GetColor(p).ToString("F2")
                                    : t == ShaderPropertyType.Vector ? m.GetVector(p).ToString("F2")
                                    : m.GetFloat(p).ToString("F3");
                                sb.AppendLine("      " + p + " (" + t + ") = " + v);
                            }
                        }
                    }
                }
                if (deep)
                {
                    Animator a = go.GetComponentInChildren<Animator>(true);
                    if (a != null)
                    {
                        sb.AppendLine("  animator " + Where(a.transform, go.transform) + " controller "
                            + (a.runtimeAnimatorController != null ? a.runtimeAnimatorController.name : "none") + " avatar "
                            + (a.avatar != null ? a.avatar.name + (a.avatar.isHuman ? " human" : " generic") : "none"));
                    }
                    foreach (Collider col in go.GetComponentsInChildren<Collider>(true))
                    {
                        sb.AppendLine("  collider " + Where(col.transform, go.transform) + " " + col.GetType().Name + " layer "
                            + LayerMask.LayerToName(col.gameObject.layer) + "(" + col.gameObject.layer + ")");
                    }
                    sb.AppendLine("  transforms " + go.GetComponentsInChildren<Transform>(true).Length + ", scale " + go.transform.localScale.ToString("F2"));
                }
            }
        }
        finally
        {
            bundle.Unload(true);
        }
        File.WriteAllText(path, sb.ToString());
    }

    /// <summary>For matching our plants to vanilla's: where a few vanilla plants' meshes sit (bounds center and size),
    /// which vertex attributes they carry (the wind may be weighted by vertex color), and their LOD and collider
    /// setup. Writes Build/probe-detail.txt.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.Detail</summary>
    public static void Detail()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Concat(new[] { "automatic_assets_entities/plants.bundle" })
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        StringBuilder sb = new StringBuilder();
        try
        {
            AssetBundle plants = loaded.Last();
            // The game's bundles keep the assets' own capitals
            foreach (string n in plants.GetAllAssetNames().Where(x => x.EndsWith(".prefab")).Where(x => new[]
                { "cottonharvestprefab", "shrubprefab", "cactus01", "yucca_harvest", "plantfernprefab", "hedgeprefab" }
                .Any(k => x.ToLowerInvariant().Contains(k))))
            {
                GameObject go = plants.LoadAsset<GameObject>(n);
                sb.AppendLine("== " + n);
                if (go.TryGetComponent(out LODGroup lg))
                {
                    sb.AppendLine("  LODGroup size " + lg.size.ToString("F2") + " fade " + lg.fadeMode + " crossfade " + lg.animateCrossFading
                        + " heights " + string.Join(", ", lg.GetLODs().Select(l => l.screenRelativeTransitionHeight.ToString("F3")
                            + "(" + l.renderers.Length + ")")));
                }
                foreach (Collider c in go.GetComponentsInChildren<Collider>(true))
                {
                    string shape = c is BoxCollider b ? "box center " + b.center.ToString("F2") + " size " + b.size.ToString("F2") : c.GetType().Name;
                    sb.AppendLine("  collider " + Where(c.transform, go.transform) + " " + shape + " layer " + c.gameObject.layer
                        + " tag " + c.gameObject.tag + " trigger " + c.isTrigger);
                }
                foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                {
                    Mesh mesh = r.TryGetComponent(out MeshFilter mf) ? mf.sharedMesh : null;
                    if (mesh == null)
                    {
                        continue;
                    }
                    sb.AppendLine("  " + Where(r.transform, go.transform) + " pos " + r.transform.localPosition.ToString("F2") + " rot "
                        + r.transform.localEulerAngles.ToString("F0") + " scale " + r.transform.localScale.ToString("F2")
                        + " mesh center " + mesh.bounds.center.ToString("F2") + " size " + mesh.bounds.size.ToString("F2")
                        + " shadows " + r.shadowCastingMode + " layer " + r.gameObject.layer
                        + " attrs " + string.Join(" ", mesh.GetVertexAttributes().Select(a => a.attribute + ":" + a.format + "x" + a.dimension)));
                }
            }
        }
        finally
        {
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-detail.txt"), sb.ToString());
    }

    /// <summary>For building trees like vanilla's: a few of the game's tree prefabs (LODs, meshes and their sizes,
    /// materials and shaders, colliders, layers, tags, scripts) to Build/probe-trees.txt.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.Trees</summary>
    public static void Trees()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        StringBuilder sb = new StringBuilder();
        try
        {
            string[] names = trees.GetAllAssetNames();
            sb.AppendLine(names.Length + " assets; prefabs:");
            foreach (string n in names.Where(x => x.EndsWith(".prefab")))
            {
                sb.AppendLine("  " + n);
            }
            foreach (MonoScript s in trees.LoadAllAssets<MonoScript>())
            {
                sb.AppendLine("  script " + s.name);
            }
            foreach (string n in names.Where(x => new[] { "oaksml01gimbalprefab", "mountainpinemed01gimbalprefab", "white_oak42gimbalprefab", "oaklrg02gimbalprefab" }
                .Any(k => x.ToLowerInvariant().EndsWith(k + ".prefab"))))
            {
                GameObject go = trees.LoadAsset<GameObject>(n);
                sb.AppendLine();
                sb.AppendLine("== " + n + " layer " + go.layer + " tag " + go.tag + " scale " + go.transform.localScale.ToString("F2"));
                foreach (Transform t in go.GetComponentsInChildren<Transform>(true))
                {
                    string comps = string.Join(", ", t.GetComponents<Component>().Select(c => c == null ? "MISSING-SCRIPT" : c.GetType().Name));
                    sb.AppendLine("  " + Where(t, go.transform) + " pos " + t.localPosition.ToString("F2") + " rot " + t.localEulerAngles.ToString("F0")
                        + " scale " + t.localScale.ToString("F2") + " layer " + t.gameObject.layer + " tag " + t.tag + " active " + t.gameObject.activeSelf + " [" + comps + "]");
                }
                if (go.TryGetComponent(out LODGroup lg))
                {
                    sb.AppendLine("  LODGroup size " + lg.size.ToString("F2") + " fade " + lg.fadeMode + " crossfade " + lg.animateCrossFading + " heights "
                        + string.Join(", ", lg.GetLODs().Select(l => l.screenRelativeTransitionHeight.ToString("F3") + "(" + string.Join("+", l.renderers.Select(r => r == null ? "null" : r.name)) + ")")));
                }
                foreach (Collider c in go.GetComponentsInChildren<Collider>(true))
                {
                    string shape = c is BoxCollider b ? "box " + b.center.ToString("F2") + " " + b.size.ToString("F2")
                        : c is CapsuleCollider cc ? "capsule " + cc.center.ToString("F2") + " r " + cc.radius.ToString("F2") + " h " + cc.height.ToString("F2") + " dir " + cc.direction
                        : c is MeshCollider mc ? "mesh " + (mc.sharedMesh != null ? mc.sharedMesh.name + " verts " + mc.sharedMesh.vertexCount : "none") + " convex " + mc.convex
                        : c.GetType().Name;
                    sb.AppendLine("  collider " + Where(c.transform, go.transform) + " " + shape + " layer " + c.gameObject.layer + " trigger " + c.isTrigger);
                }
                foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
                {
                    Mesh mesh = r.TryGetComponent(out MeshFilter mf) ? mf.sharedMesh : null;
                    sb.AppendLine("  renderer " + Where(r.transform, go.transform) + " " + r.GetType().Name + " shadows " + r.shadowCastingMode
                        + (mesh != null ? " mesh " + mesh.name + " verts " + mesh.vertexCount + " tris " + (mesh.isReadable ? (mesh.triangles.Length / 3).ToString() : "?")
                            + " subs " + mesh.subMeshCount + " bounds c " + mesh.bounds.center.ToString("F1") + " s " + mesh.bounds.size.ToString("F1")
                            + " attrs " + string.Join(" ", mesh.GetVertexAttributes().Select(a => a.attribute + ":" + a.dimension)) : ""));
                    foreach (Material m in r.sharedMaterials.Where(m => m != null))
                    {
                        sb.AppendLine("    material " + m.name + " shader " + (m.shader != null ? m.shader.name : "none") + " queue " + m.renderQueue
                            + " keywords [" + string.Join(" ", m.shaderKeywords) + "] textures [" + string.Join(" ", m.GetTexturePropertyNames()
                                .Where(p => m.GetTexture(p) != null).Select(p => p + "=" + m.GetTexture(p).name + " " + m.GetTexture(p).width)) + "]");
                    }
                }
            }
        }
        finally
        {
            trees.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-trees.txt"), sb.ToString());
    }

    /// <summary>For giving our trees SpeedTree's own per-vertex data: what a few vanilla SpeedTrees carry per
    /// vertex (by geometry type: the ranges of uv0.zw, uv1-3 and color, and how the branch weight follows height and
    /// distance from the trunk), and every property of their materials. Writes Build/probe-speedtree.txt.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.SpeedTreeData</summary>
    public static void SpeedTreeData()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        StringBuilder sb = new StringBuilder();
        string F(Vector4 v) => v.ToString("F3");
        try
        {
            foreach (string end in new[] { "oaksml01gimbalprefab.prefab", "white_oak42gimbalprefab.prefab", "mountainpinemed01gimbalprefab.prefab" })
            {
                string n = trees.GetAllAssetNames().First(x => x.ToLowerInvariant().EndsWith(end));
                GameObject go = trees.LoadAsset<GameObject>(n);
                sb.AppendLine("==== " + n);
                foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true).Take(2))
                {
                    Mesh mesh = r.GetComponent<MeshFilter>().sharedMesh;
                    sb.AppendLine("-- " + r.name + " verts " + mesh.vertexCount + " readable " + mesh.isReadable + " bounds " + mesh.bounds.ToString("F2"));
                    Material m = r.sharedMaterial;
                    sb.AppendLine("  shader " + m.shader.name + " keywords [" + string.Join(" ", m.shaderKeywords) + "] queue " + m.renderQueue
                        + " passes " + m.passCount);
                    for (int i = 0; i < m.shader.GetPropertyCount(); i++)
                    {
                        string p = m.shader.GetPropertyName(i);
                        var t = m.shader.GetPropertyType(i);
                        sb.AppendLine("    " + p + " = " + (t == UnityEngine.Rendering.ShaderPropertyType.Texture ? (m.GetTexture(p) != null ? m.GetTexture(p).name : "null")
                            : t == UnityEngine.Rendering.ShaderPropertyType.Color ? m.GetColor(p).ToString("F3")
                            : t == UnityEngine.Rendering.ShaderPropertyType.Vector ? m.GetVector(p).ToString("F3") : m.GetFloat(p).ToString("F3")));
                    }
                    MaterialPropertyBlock mpb = new MaterialPropertyBlock();
                    r.GetPropertyBlock(mpb);
                    sb.AppendLine("  property block empty " + mpb.isEmpty);
                    if (!mesh.isReadable)
                    {
                        continue;
                    }
                    Vector3[] pos = mesh.vertices;
                    List<Vector4>[] uv = new List<Vector4>[4];
                    for (int c = 0; c < 4; c++)
                    {
                        uv[c] = new List<Vector4>();
                        mesh.GetUVs(c, uv[c]);
                    }
                    Color[] col = mesh.colors;
                    float top = mesh.bounds.max.y;
                    foreach (var group in Enumerable.Range(0, pos.Length).GroupBy(i => uv[3].Count > 0 ? Mathf.RoundToInt(uv[3][i].w) : -1))
                    {
                        int[] idx = group.ToArray();
                        sb.AppendLine("  geometry type " + group.Key + ": " + idx.Length + " verts");
                        for (int c = 0; c < 4; c++)
                        {
                            if (uv[c].Count == 0)
                            {
                                continue;
                            }
                            Vector4 lo = idx.Select(i => uv[c][i]).Aggregate(Vector4.Min), hi = idx.Select(i => uv[c][i]).Aggregate(Vector4.Max);
                            sb.AppendLine("    uv" + c + " min " + F(lo) + " max " + F(hi));
                        }
                        if (col.Length > 0)
                        {
                            Vector4 lo = idx.Select(i => (Vector4)col[i]).Aggregate(Vector4.Min), hi = idx.Select(i => (Vector4)col[i]).Aggregate(Vector4.Max);
                            sb.AppendLine("    color min " + F(lo) + " max " + F(hi) + " mean " + F(idx.Select(i => (Vector4)col[i]).Aggregate((a, b) => a + b) / idx.Length));
                        }
                        // The branch weight (uv0.z) against height and distance out from the trunk, in bands of each
                        foreach (int band in Enumerable.Range(0, 5))
                        {
                            int[] h = idx.Where(i => Mathf.Min(4, (int)(pos[i].y / top * 5f)) == band).ToArray();
                            int[] d = idx.Where(i => Mathf.Min(4, (int)(new Vector2(pos[i].x, pos[i].z).magnitude / (mesh.bounds.extents.x + 0.01f) * 5f)) == band).ToArray();
                            sb.AppendLine("    band " + band + ": by height " + h.Length + " verts, uv0.z mean " + (h.Length > 0 ? h.Average(i => uv[0][i].z).ToString("F3") : "-")
                                + " uv3.y mean " + (h.Length > 0 && uv[3].Count > 0 ? h.Average(i => uv[3][i].y).ToString("F3") : "-")
                                + "; by distance out " + d.Length + " verts, uv0.z mean " + (d.Length > 0 ? d.Average(i => uv[0][i].z).ToString("F3") : "-"));
                        }
                        // A few vertices whole
                        foreach (int i in idx.Where((x, k) => k % Mathf.Max(1, idx.Length / 6) == 0).Take(6))
                        {
                            sb.AppendLine("    v" + i + " pos " + pos[i].ToString("F2") + " uv0 " + F(uv[0][i]) + " uv1 " + (uv[1].Count > 0 ? F(uv[1][i]) : "-")
                                + " uv2 " + (uv[2].Count > 0 ? F(uv[2][i]) : "-") + " uv3 " + (uv[3].Count > 0 ? F(uv[3][i]) : "-") + " col " + (col.Length > 0 ? F(col[i]) : "-"));
                        }
                    }
                }
            }
        }
        finally
        {
            trees.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-speedtree.txt"), sb.ToString());
    }

    /// <summary>The average colour (sRGB 0-255) of the opaque parts of vanilla's tree atlases and of our trees' leaf
    /// and bark maps, to match our trees' colours to vanilla's. Writes Build/probe-treecolors.txt.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.TreeColors</summary>
    public static void TreeColors()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        StringBuilder sb = new StringBuilder();
        try
        {
            List<Texture2D> textures = trees.LoadAllAssets<Texture2D>().Where(t => new[] { "Oak_Atlas", "MountainPine_Atlas", "White_Oak", "ScotsPine" }
                .Any(k => t.name.StartsWith(k)) && !t.name.EndsWith("_n") && !t.name.Contains("SMO") && !t.name.Contains("Billboard")).ToList();
            textures.AddRange(Directory.GetFiles("Assets/NatureExpanded/Trees", "*_Albedo.png", SearchOption.AllDirectories)
                .Select(p => AssetDatabase.LoadAssetAtPath<Texture2D>(p.Replace('\\', '/'))).Where(t => t != null));
            foreach (Texture2D t in textures)
            {
                RenderTexture rt = RenderTexture.GetTemporary(512, 512, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                Graphics.Blit(t, rt);
                RenderTexture.active = rt;
                Texture2D read = new Texture2D(512, 512, TextureFormat.RGBA32, false);
                read.ReadPixels(new Rect(0, 0, 512, 512), 0, 0);
                RenderTexture.active = null;
                RenderTexture.ReleaseTemporary(rt);
                Color32[] px = read.GetPixels32().Where(p => p.a > 128).ToArray();
                Object.DestroyImmediate(read);
                if (px.Length == 0)
                {
                    continue;
                }
                // Green-dominant pixels are the foliage in a mixed atlas
                Color32[] green = px.Where(p => p.g > p.r && p.g > p.b).ToArray();
                string Avg(Color32[] a) => a.Length == 0 ? "-" : string.Format("{0:F0}, {1:F0}, {2:F0}", a.Average(p => p.r), a.Average(p => p.g), a.Average(p => p.b));
                sb.AppendLine(t.name + ": opaque " + Avg(px) + " (" + px.Length + " px); foliage " + Avg(green) + " (" + green.Length + " px)");
            }
        }
        finally
        {
            trees.Unload(true);
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-treecolors.txt"), sb.ToString());
    }

    /// <summary>Whether the game's wind pulls our plants apart: a few plants close up in the game's plant shader and
    /// in Torch's version of it, with the game's global _Wind (speed, time, previous speed, previous time) strong, at
    /// several moments, to Build/windtest.png (rows: game shader, Torch's; columns: moments).
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.WindTest</summary>
    public static void WindTest()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Concat(new[] { "automatic_assets_entities/plants.bundle" })
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle torch = AssetBundle.LoadFromFile(Path.Combine(game, "Mods/Torch/Resources/torchshaders.unity3d"));
        try
        {
            AssetBundle plants = loaded.Last();
            string cotton = plants.GetAllAssetNames().First(n => n.ToLowerInvariant().EndsWith("plantcottonharvestprefab.prefab"));
            Shader gameShader = plants.LoadAsset<GameObject>(cotton).GetComponentInChildren<MeshRenderer>(true).sharedMaterial.shader;
            Shader torchShader = torch != null ? torch.LoadAllAssets<Shader>().FirstOrDefault(s => s.name.Contains("EntityTintMaskSSS")) : null;
            Debug.Log("[WindTest] game shader " + gameShader.name + ", Torch's " + (torchShader != null ? torchShader.name : "none")
                + (torch != null ? " (Torch shaders: " + string.Join(", ", torch.LoadAllAssets<Shader>().Select(s => s.name)) + ")" : ""));
            string[] names = { "BlackEyedSusan", "Coneflower", "OxeyeDaisy", "Elderberry" };
            float[] moments = { 0f, 1.7f, 3.9f, 7.3f };
            const int tile = 420;
            UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Single);
            NatureBuilder.Stage(6f);
            // After the new scene, which destroys textures made before it
            Texture2D sheet = new Texture2D(tile * moments.Length, tile * 2 * names.Length, TextureFormat.RGB24, false);
            for (int p = 0; p < names.Length; p++)
            {
                for (int s = 0; s < 2; s++)
                {
                    Shader shader = s == 0 ? gameShader : torchShader ?? gameShader;
                    GameObject go = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/NatureExpanded/Prefabs/" + names[p] + ".prefab"));
                    foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                    {
                        r.sharedMaterial = NatureBuilder.ToGame(shader, r.sharedMaterial);
                    }
                    go.GetComponent<LODGroup>().ForceLOD(0);
                    Bounds b = go.GetComponentInChildren<MeshRenderer>().bounds;
                    for (int m = 0; m < moments.Length; m++)
                    {
                        Shader.SetGlobalVector("_Wind", new Vector4(0.6f, moments[m], 0.6f, moments[m]));
                        Texture2D shot = NatureBuilder.Shot(b.center + new Vector3(0.4f, 0.25f, -1f).normalized * b.extents.magnitude * 2.2f, b.center, 35f, tile, tile);
                        sheet.SetPixels(m * tile, (names.Length * 2 - 1 - (p * 2 + s)) * tile, tile, tile, shot.GetPixels());
                        Object.DestroyImmediate(shot);
                    }
                    Object.DestroyImmediate(go);
                }
            }
            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build", "windtest.png"), sheet.EncodeToPNG());
        }
        finally
        {
            torch?.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    /// <summary>The mod's tree conversion exactly as it runs in game: loads the built Resources/natureexpanded-trees.
    /// unity3d (not the project's assets), gives a birch copies of the vanilla oak's SpeedTree material with its own
    /// maps the way TreeShaderDEM does, renders it beside the oak, and writes what each material ended up with to
    /// Build/treeruntime.txt and Build/treeruntime.png.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.TreeRuntime</summary>
    public static void TreeRuntime()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        AssetBundle ours = AssetBundle.LoadFromFile(Path.Combine(game, "Mods/NatureExpanded/Resources/natureexpanded-trees.unity3d"));
        StringBuilder sb = new StringBuilder();
        string Describe(Material m) => m == null ? "null" : m.name + " shader " + (m.shader != null ? m.shader.name + " supported " + m.shader.isSupported
            + " passes " + m.passCount : "NULL") + " keywords [" + string.Join(" ", m.shaderKeywords) + "] queue " + m.renderQueue + " instancing "
            + m.enableInstancing + " maps " + string.Join(", ", new[] { "_MainTex", "_BumpMap", "_ExtraTex", "_DetailMask" }.Where(m.HasProperty)
                .Select(p => p + "=" + (m.GetTexture(p) != null ? m.GetTexture(p).name + " " + m.GetTexture(p).GetType().Name + " " + m.GetTexture(p).graphicsFormat : "none")));
        try
        {
            sb.AppendLine("our bundle: " + string.Join(", ", ours.GetAllAssetNames()));
            GameObject oak = trees.LoadAsset<GameObject>(trees.GetAllAssetNames().First(n => n.ToLowerInvariant().EndsWith("oaksml01gimbalprefab.prefab")));
            Material template = oak.GetComponentsInChildren<MeshRenderer>(true).Select(r => r.sharedMaterial).First(m => m.shader.name == "Game/SpeedTree8" && !m.IsKeywordEnabled("EFFECT_BILLBOARD"));
            sb.AppendLine("template: " + Describe(template));
            GameObject prefab = ours.LoadAsset<GameObject>(ours.GetAllAssetNames().First(n => n.ToLowerInvariant().Contains("birch01")));
            foreach (MeshRenderer r in prefab.GetComponentsInChildren<MeshRenderer>(true))
            {
                Mesh mesh = r.GetComponent<MeshFilter>().sharedMesh;
                sb.AppendLine("renderer " + r.name + " mesh " + mesh.name + " verts " + mesh.vertexCount + " attrs "
                    + string.Join(" ", mesh.GetVertexAttributes().Select(a => a.attribute + ":" + a.format + "x" + a.dimension)));
                foreach (Material m in r.sharedMaterials)
                {
                    sb.AppendLine("  bundle material: " + Describe(m));
                }
            }
            UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Single);
            NatureBuilder.Stage(160f);
            GameObject tree = Object.Instantiate(prefab, new Vector3(0f, -0.5f, 0f), Quaternion.identity);
            Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
            foreach (MeshRenderer r in tree.GetComponentsInChildren<MeshRenderer>(true))
            {
                r.sharedMaterials = r.sharedMaterials.Select(src =>
                {
                    if (!converted.TryGetValue(src, out Material dst))
                    {
                        dst = new Material(template) { name = src.name + " (SpeedTree)" };
                        dst.SetTexture("_MainTex", src.GetTexture("_MainTex"));
                        dst.SetTexture("_BumpMap", src.GetTexture("_BumpMap"));
                        dst.SetTexture("_ExtraTex", src.GetTexture("_DetailMask"));
                        converted[src] = dst;
                        sb.AppendLine("converted: " + Describe(dst));
                    }
                    return dst;
                }).ToArray();
            }
            Object.Instantiate(oak, new Vector3(14f, -0.5f, 3f), Quaternion.identity);
            Texture2D shot = NatureBuilder.Shot(new Vector3(4f, 8f, -50f), new Vector3(4f, 11f, 0f), 42f, 1200, 700);
            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build", "treeruntime.png"), shot.EncodeToPNG());
        }
        catch (System.Exception e)
        {
            sb.AppendLine("FAILED: " + e);
        }
        finally
        {
            ours.Unload(true);
            trees.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "treeruntime.txt"), sb.ToString());
    }

    /// <summary>Reproduces the mod's plants as the game draws them, from the installed plant bundle: each sample
    /// plant's bundle materials (shader, maps and their formats, the mean alpha of the RMOM map the plant shader tints
    /// by), then the plants converted as NatureShaderDEM converts them (NatureBuilder.ToGame), drawn with vanilla's
    /// plant shader (front row) and with Torch's replacement for it (back row). Writes Build/plantruntime.txt and
    /// Build/plantruntime.png.
    /// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureProbe.PlantRuntime</summary>
    public static void PlantRuntime()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = Shared.Concat(new[] { "automatic_assets_entities/plants.bundle" })
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle ours = AssetBundle.LoadFromFile(Path.Combine(game, "Mods/NatureExpanded/Resources/natureexpanded.unity3d"));
        AssetBundle torch = AssetBundle.LoadFromFile(Path.Combine(game, "Mods/Torch/Resources/torchshaders.unity3d"));
        StringBuilder sb = new StringBuilder();
        string[] sample = { "QueenAnnesLace", "Fireweed", "OxeyeDaisy", "Chicory", "Lupine", "Fern", "Bolete", "MossyLog" };
        float Mean(Texture t, int channel)
        {
            if (t == null)
            {
                return -1f;
            }
            RenderTexture rt = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            Graphics.Blit(t, rt);
            RenderTexture previous = RenderTexture.active;
            RenderTexture.active = rt;
            Texture2D read = new Texture2D(64, 64, TextureFormat.RGBA32, false, true);
            read.ReadPixels(new Rect(0, 0, 64, 64), 0, 0);
            read.Apply();
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(rt);
            float mean = read.GetPixels().Average(c => c[channel]);
            Object.DestroyImmediate(read);
            return mean;
        }
        string Map(Material m, string p) => !m.HasProperty(p) || m.GetTexture(p) == null ? p + "=none"
            : p + "=" + m.GetTexture(p).name + " " + m.GetTexture(p).graphicsFormat + " " + m.GetTexture(p).width + "px a" + Mean(m.GetTexture(p), 3).ToString("F2");
        try
        {
            AssetBundle plants = loaded.FirstOrDefault(b => b.GetAllAssetNames().Any(n => n.ToLowerInvariant().Contains("plantcotton")));
            GameObject cotton = plants.LoadAsset<GameObject>(plants.GetAllAssetNames().First(n => n.ToLowerInvariant().EndsWith("plantcottonharvestprefab.prefab")));
            Material cottonMat = cotton.GetComponentInChildren<MeshRenderer>(true).sharedMaterial;
            Shader vanilla = cottonMat.shader;
            Shader[] torchShaders = torch != null ? torch.LoadAllAssets<Shader>() : new Shader[0];
            Shader torchPlant = torchShaders.FirstOrDefault(s => s.name.Contains("EntityTintMask"));
            sb.AppendLine("vanilla cotton: shader " + vanilla.name + " supported " + vanilla.isSupported + " | " + Map(cottonMat, "_Albedo") + " " + Map(cottonMat, "_RMOM")
                + " tint " + (cottonMat.HasProperty("_TintColor") ? cottonMat.GetColor("_TintColor").ToString() : "none"));
            sb.AppendLine("torch shaders: " + string.Join(", ", torchShaders.Select(s => s.name)));
            List<GameObject> prefabs = new List<GameObject>();
            foreach (string name in sample)
            {
                string asset = ours.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + name.ToLowerInvariant() + ".prefab"));
                if (asset == null)
                {
                    sb.AppendLine(name + ": not in the bundle");
                    continue;
                }
                GameObject p = ours.LoadAsset<GameObject>(asset);
                prefabs.Add(p);
                foreach (Material m in p.GetComponentsInChildren<MeshRenderer>(true).SelectMany(r => r.sharedMaterials).Distinct())
                {
                    sb.AppendLine(name + ": " + m.name + " shader " + (m.shader != null ? m.shader.name + " supported " + m.shader.isSupported : "NULL")
                        + " | " + Map(m, "_MainTex") + " | " + Map(m, "_BumpMap") + " | " + Map(m, "_DetailMask"));
                }
            }
            UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Single);
            NatureBuilder.Stage(40f);
            for (int row = 0; row < 2; row++)
            {
                Shader shader = row == 0 ? vanilla : torchPlant;
                if (shader == null)
                {
                    continue;
                }
                for (int i = 0; i < prefabs.Count; i++)
                {
                    GameObject go = Object.Instantiate(prefabs[i], new Vector3(-5.25f + i * 1.5f, -0.5f, row * 2.5f), Quaternion.identity);
                    foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                    {
                        r.sharedMaterials = r.sharedMaterials.Select(src =>
                        {
                            Material dst = NatureBuilder.ToGame(vanilla, src);
                            dst.shader = shader;
                            return dst;
                        }).ToArray();
                    }
                }
            }
            Texture2D shot = NatureBuilder.Shot(new Vector3(0f, 2.2f, -6.5f), new Vector3(0f, 0.3f, 1.2f), 55f, 1600, 800);
            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build", "plantruntime.png"), shot.EncodeToPNG());
        }
        catch (System.Exception e)
        {
            sb.AppendLine("FAILED: " + e);
        }
        finally
        {
            ours.Unload(true);
            torch?.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "plantruntime.txt"), sb.ToString());
    }

    private static string Where(Transform t, Transform root)
    {
        List<string> parts = new List<string>();
        for (Transform x = t; x != null && x != root; x = x.parent)
        {
            parts.Add(x.name);
        }
        parts.Reverse();
        return parts.Count == 0 ? "(root)" : string.Join("/", parts);
    }
}
