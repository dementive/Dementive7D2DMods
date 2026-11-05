using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Reference only: lists the game's mesh-description and block-atlas bundles and writes the grass atlas's uv metadata
/// and a small picture of each of its textures to Build/atlas/, to see how vanilla's grass is laid out.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureAtlasProbe.Run
/// </summary>
public static class NatureAtlasProbe
{
    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build", "atlas");
        Directory.CreateDirectory(output);
        StringBuilder sb = new StringBuilder();
        foreach (string name in new[] { "meshdescriptions_assets_all.bundle", "blocktextureatlases_assets_all.bundle" })
        {
            AssetBundle bundle = AssetBundle.LoadFromFile(Path.Combine(root, name));
            if (bundle == null)
            {
                sb.AppendLine("Could not load " + name);
                continue;
            }
            try
            {
                sb.AppendLine("== " + name);
                // The mesh descriptions hold their atlases and uv metadata as embedded objects, not named assets
                foreach (Texture2D t in bundle.LoadAllAssets<Texture2D>())
                {
                    sb.AppendLine("  texture " + t.name + " " + t.width + "x" + t.height + " " + t.format + " mips " + t.mipmapCount);
                    if (t.name.ToLowerInvariant().Contains("grass"))
                    {
                        Save(t, Path.Combine(output, t.name + ".png"), 2048);
                    }
                }
                foreach (TextAsset t in bundle.LoadAllAssets<TextAsset>())
                {
                    sb.AppendLine("  text " + t.name + " " + t.text.Length + " chars");
                    File.WriteAllText(Path.Combine(output, t.name + ".txt"), t.text);
                }
                foreach (Material m in bundle.LoadAllAssets<Material>())
                {
                    sb.AppendLine("  material " + m.name + " shader " + (m.shader != null ? m.shader.name : "none") + " textures ["
                        + string.Join(" ", m.GetTexturePropertyNames().Where(p => m.GetTexture(p) != null).Select(p => p + "=" + m.GetTexture(p).name)) + "]");
                }
                foreach (GameObject go in bundle.LoadAllAssets<GameObject>())
                {
                    foreach (MeshDescriptionCollection c in go.GetComponentsInChildren<MeshDescriptionCollection>(true))
                    {
                        sb.AppendLine("  collection " + go.name + ": " + (c.meshes == null ? "no meshes" : c.meshes.Length + " meshes"));
                        for (int i = 0; c.meshes != null && i < c.meshes.Length; i++)
                        {
                            MeshDescription m = c.meshes[i];
                            sb.AppendLine("    [" + i + "] " + m.Name + " tag " + m.Tag + " array " + m.bTextureArray + " class " + m.TextureAtlasClass
                                + " material " + (m.BaseMaterial != null ? m.BaseMaterial.name + "/" + m.BaseMaterial.shader.name : "none")
                                + " diffuse " + Describe(m.TexDiffuse) + " normal " + Describe(m.TexNormal) + " specular " + Describe(m.TexSpecular)
                                + " meta " + (m.MetaData != null ? m.MetaData.name : "none"));
                            if (m.Name == null || !m.Name.ToLowerInvariant().Contains("grass") || go.name.Contains("BlockVT"))
                            {
                                continue;
                            }
                            if (m.MetaData != null)
                            {
                                File.WriteAllText(Path.Combine(output, m.MetaData.name + ".xml"), m.MetaData.text);
                            }
                            foreach (Texture t in new[] { m.TexDiffuse, m.TexNormal, m.TexSpecular })
                            {
                                if (t is Texture2D t2)
                                {
                                    Save(t2, Path.Combine(output, t2.name + ".png"), 4096);
                                }
                            }
                            if (m.BaseMaterial != null)
                            {
                                Material bm = m.BaseMaterial;
                                Shader sh = bm.shader;
                                for (int p = 0; p < sh.GetPropertyCount(); p++)
                                {
                                    string pn = sh.GetPropertyName(p);
                                    var pt = sh.GetPropertyType(p);
                                    sb.AppendLine("      " + pn + " = " + (pt == UnityEngine.Rendering.ShaderPropertyType.Texture
                                        ? Describe(bm.GetTexture(pn)) : pt == UnityEngine.Rendering.ShaderPropertyType.Color
                                        ? bm.GetColor(pn).ToString("F2") : pt == UnityEngine.Rendering.ShaderPropertyType.Vector
                                        ? bm.GetVector(pn).ToString("F2") : bm.GetFloat(pn).ToString("F3")));
                                }
                            }
                        }
                    }
                }
                foreach (string n in bundle.GetAllAssetNames())
                {
                    Object o = bundle.LoadAsset(n);
                    string what = o == null ? "null" : o.GetType().Name;
                    if (o is Texture2D t)
                    {
                        what += " " + t.width + "x" + t.height + " " + t.format + " mips " + t.mipmapCount;
                    }
                    else if (o is Texture2DArray a)
                    {
                        what += " " + a.width + "x" + a.height + "x" + a.depth + " " + a.format;
                    }
                    sb.AppendLine("  " + n + " : " + what);
                    string lower = n.ToLowerInvariant();
                    if (!lower.Contains("grass"))
                    {
                        continue;
                    }
                    if (o is TextAsset text)
                    {
                        File.WriteAllText(Path.Combine(output, Path.GetFileName(n) + ".txt"), text.text);
                    }
                    else if (o is Texture2D tex)
                    {
                        Save(tex, Path.Combine(output, Path.GetFileNameWithoutExtension(n) + ".png"), 1024);
                    }
                }
            }
            finally
            {
                bundle.Unload(true);
            }
        }
        File.WriteAllText(Path.Combine(output, "bundles.txt"), sb.ToString());
    }

    private static string Describe(Texture t)
    {
        return t == null ? "none" : t is Texture2D t2 ? t2.name + " " + t2.width + "x" + t2.height + " " + t2.format + " mips " + t2.mipmapCount
            : t is Texture2DArray a ? a.name + " array " + a.width + "x" + a.height + "x" + a.depth + " " + a.format : t.name + " " + t.GetType().Name;
    }

    private static void Save(Texture tex, string path, int size)
    {
        RenderTexture rt = RenderTexture.GetTemporary(size, size, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        Graphics.Blit(tex, rt);
        RenderTexture prev = RenderTexture.active;
        RenderTexture.active = rt;
        Texture2D copy = new Texture2D(size, size, TextureFormat.RGBA32, false);
        copy.ReadPixels(new Rect(0, 0, size, size), 0, 0);
        RenderTexture.active = prev;
        RenderTexture.ReleaseTemporary(rt);
        File.WriteAllBytes(path, copy.EncodeToPNG());
        Object.DestroyImmediate(copy);
    }
}
