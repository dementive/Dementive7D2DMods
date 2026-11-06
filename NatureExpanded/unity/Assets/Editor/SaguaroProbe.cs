using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>Reference for the saguaro tree (blender/trees/saguaro.py): vanilla's Saguaro_Cactus prefabs (structure,
/// colliders, materials, wind settings, mean albedo of their texture) to Build/probe-saguaro.txt and a render of them
/// to Build/trees/vanilla_saguaro.png. Run: Unity -batchmode -quit -projectPath unity -executeMethod SaguaroProbe.Run</summary>
public static class SaguaroProbe
{
    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = new[] { "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle" }
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        StringBuilder sb = new StringBuilder();
        try
        {
            string[] names = trees.GetAllAssetNames().Where(n => n.ToLowerInvariant().Contains("saguaro") || n.ToLowerInvariant().Contains("cactus")).ToArray();
            foreach (string n in names)
            {
                sb.AppendLine("asset " + n);
            }
            List<GameObject> prefabs = names.Where(n => n.ToLowerInvariant().EndsWith("gimbalprefab.prefab")).Select(n => trees.LoadAsset<GameObject>(n)).ToList();
            foreach (GameObject go in prefabs)
            {
                sb.AppendLine("== " + go.name + " layer " + go.layer + " scale " + go.transform.localScale.ToString("F2"));
                foreach (Transform t in go.GetComponentsInChildren<Transform>(true))
                {
                    sb.AppendLine("  " + t.name + " pos " + t.localPosition.ToString("F2") + " rot " + t.localEulerAngles.ToString("F0") + " layer " + t.gameObject.layer
                        + " [" + string.Join(", ", t.GetComponents<Component>().Select(c => c == null ? "MISSING" : c.GetType().Name)) + "]");
                }
                if (go.TryGetComponent(out LODGroup lg))
                {
                    sb.AppendLine("  LODGroup size " + lg.size.ToString("F2") + " heights " + string.Join(", ", lg.GetLODs().Select(l => l.screenRelativeTransitionHeight.ToString("F3"))));
                }
                foreach (Collider c in go.GetComponentsInChildren<Collider>(true))
                {
                    string shape = c is CapsuleCollider cc ? "capsule c " + cc.center.ToString("F2") + " r " + cc.radius.ToString("F2") + " h " + cc.height.ToString("F2") + " dir " + cc.direction
                        : c is BoxCollider b ? "box " + b.center.ToString("F2") + " " + b.size.ToString("F2") : c.GetType().Name;
                    sb.AppendLine("  collider " + c.name + " pos " + c.transform.localPosition.ToString("F2") + " rot " + c.transform.localEulerAngles.ToString("F0") + " " + shape);
                }
                foreach (MeshRenderer r in go.GetComponentsInChildren<MeshRenderer>(true))
                {
                    Mesh mesh = r.GetComponent<MeshFilter>().sharedMesh;
                    sb.AppendLine("  renderer " + r.name + " mesh " + mesh.name + " verts " + mesh.vertexCount + " tris " + (mesh.isReadable ? (mesh.triangles.Length / 3).ToString() : "?")
                        + " bounds " + mesh.bounds.center.ToString("F2") + " " + mesh.bounds.size.ToString("F2"));
                    foreach (Material m in r.sharedMaterials)
                    {
                        sb.AppendLine("    material " + m.name + " shader " + m.shader.name + " keywords [" + string.Join(" ", m.shaderKeywords) + "] textures ["
                            + string.Join(" ", m.GetTexturePropertyNames().Where(p => m.GetTexture(p) != null).Select(p => p + "=" + m.GetTexture(p).name + " " + m.GetTexture(p).width)) + "]");
                        for (int i = 0; i < m.shader.GetPropertyCount(); i++)
                        {
                            string p = m.shader.GetPropertyName(i);
                            var t = m.shader.GetPropertyType(i);
                            if (t == UnityEngine.Rendering.ShaderPropertyType.Float || t == UnityEngine.Rendering.ShaderPropertyType.Range)
                            {
                                sb.AppendLine("      " + p + " = " + m.GetFloat(p).ToString("F3"));
                            }
                            else if (t == UnityEngine.Rendering.ShaderPropertyType.Color)
                            {
                                sb.AppendLine("      " + p + " = " + m.GetColor(p).ToString("F3"));
                            }
                        }
                        Texture2D alb = m.GetTexture("_MainTex") as Texture2D;
                        if (alb != null)
                        {
                            RenderTexture rt = RenderTexture.GetTemporary(512, 512, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                            Graphics.Blit(alb, rt);
                            RenderTexture.active = rt;
                            Texture2D read = new Texture2D(512, 512, TextureFormat.RGBA32, false);
                            read.ReadPixels(new Rect(0, 0, 512, 512), 0, 0);
                            RenderTexture.active = null;
                            RenderTexture.ReleaseTemporary(rt);
                            Color32[] px = read.GetPixels32();
                            sb.AppendLine("    albedo mean (all) " + string.Format("{0:F0}, {1:F0}, {2:F0}", px.Average(q => q.r), px.Average(q => q.g), px.Average(q => q.b)) + " alpha mean " + px.Average(q => q.a).ToString("F0"));
                            Directory.CreateDirectory(Path.Combine(Directory.GetCurrentDirectory(), "Build", "trees"));
                            File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build", "trees", "vanilla_" + alb.name + ".png"), read.EncodeToPNG());
                            Object.DestroyImmediate(read);
                        }
                    }
                }
            }
            UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Single);
            NatureBuilder.Stage(120f);
            for (int i = 0; i < prefabs.Count; i++)
            {
                GameObject g = Object.Instantiate(prefabs[i], new Vector3(i * 12f - 12f, -0.5f, 10f), Quaternion.identity);
                MeshRenderer r = g.GetComponentInChildren<MeshRenderer>();
                sb.AppendLine("instance " + prefabs[i].name + " bounds " + r.bounds.size.ToString("F2"));
            }
            Save(NatureBuilder.Shot(new Vector3(0f, 4f, -22f), new Vector3(0f, 4f, 10f), 45f, 1600, 900), "vanilla_saguaro.png");
            Save(NatureBuilder.Shot(new Vector3(-4f, 1.7f, 3f), new Vector3(-12f, 3f, 10f), 55f, 1200, 900), "vanilla_saguaro_near.png");
            Save(NatureBuilder.Shot(new Vector3(-10f, 1.6f, 6f), new Vector3(-12f, 1.6f, 10f), 50f, 1000, 900), "vanilla_saguaro_close.png");
        }
        finally
        {
            File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-saguaro.txt"), sb.ToString());
            trees.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    private static void Save(Texture2D shot, string file)
    {
        File.WriteAllBytes(Path.Combine(Directory.GetCurrentDirectory(), "Build", "trees", file), shot.EncodeToPNG());
        Object.DestroyImmediate(shot);
    }
}
