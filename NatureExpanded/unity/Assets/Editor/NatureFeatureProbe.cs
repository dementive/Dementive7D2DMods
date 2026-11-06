using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>Dumps how vanilla's solid scenery (resourceRock*, stone*, ore boulders) is put together: hierarchy, layers,
/// tags, colliders, materials. Build/probe-features.txt. Run: -executeMethod NatureFeatureProbe.Run</summary>
public static class NatureFeatureProbe
{
    public static void Run()
    {
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        string[] shared = { "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle" };
        var loaded = shared.Select(b => AssetBundle.LoadFromFile(System.IO.Path.Combine(root, b))).Where(b => b != null).ToList();
        StringBuilder sb = new StringBuilder();
        foreach (string bn in new[] { "minerals.bundle", "outdoordecor.bundle" })
        {
            AssetBundle bundle = AssetBundle.LoadFromFile(System.IO.Path.Combine(root, "automatic_assets_entities/" + bn));
            sb.AppendLine("##### " + bn);
            foreach (string n in bundle.GetAllAssetNames().Where(x => x.EndsWith(".prefab")))
            {
                string l = n.ToLowerInvariant();
                if (bn == "outdoordecor.bundle" && !l.Contains("stone")) { continue; }
                GameObject go = bundle.LoadAsset<GameObject>(n);
                sb.AppendLine("== " + n + " layer " + go.layer + " tag " + go.tag);
                foreach (Transform t in go.GetComponentsInChildren<Transform>(true))
                {
                    string comps = string.Join(", ", t.GetComponents<Component>().Select(c => c == null ? "MISSING" : c.GetType().Name));
                    sb.AppendLine("  " + PathOf(t, go.transform) + " pos " + t.localPosition.ToString("F2") + " rot " + t.localEulerAngles.ToString("F0") + " scale " + t.localScale.ToString("F2") + " layer " + t.gameObject.layer + " tag " + t.tag + " [" + comps + "]");
                }
                foreach (Collider c in go.GetComponentsInChildren<Collider>(true))
                {
                    string shape = c is BoxCollider b ? "box " + b.center.ToString("F2") + " " + b.size.ToString("F2")
                        : c is CapsuleCollider cc ? "capsule " + cc.center.ToString("F2") + " r " + cc.radius.ToString("F2") + " h " + cc.height.ToString("F2")
                        : c is SphereCollider sc ? "sphere " + sc.center.ToString("F2") + " r " + sc.radius.ToString("F2")
                        : c is MeshCollider mc ? "mesh " + (mc.sharedMesh != null ? mc.sharedMesh.name + " verts " + mc.sharedMesh.vertexCount : "none") + " convex " + mc.convex
                        : c.GetType().Name;
                    sb.AppendLine("  collider " + PathOf(c.transform, go.transform) + " " + shape + " layer " + c.gameObject.layer + " trigger " + c.isTrigger + " material " + (c.sharedMaterial != null ? c.sharedMaterial.name : "none"));
                }
                if (go.TryGetComponent(out LODGroup lg))
                {
                    sb.AppendLine("  LODGroup " + string.Join(", ", lg.GetLODs().Select(x => x.screenRelativeTransitionHeight.ToString("F3") + "(" + string.Join("+", x.renderers.Select(r => r == null ? "null" : r.name)) + ")")));
                }
                foreach (Renderer r in go.GetComponentsInChildren<Renderer>(true))
                {
                    Mesh mesh = r.TryGetComponent(out MeshFilter mf) ? mf.sharedMesh : null;
                    sb.AppendLine("  renderer " + PathOf(r.transform, go.transform) + (mesh != null ? " mesh " + mesh.name + " verts " + mesh.vertexCount + " bounds c " + mesh.bounds.center.ToString("F2") + " s " + mesh.bounds.size.ToString("F2") : ""));
                    foreach (Material m in r.sharedMaterials.Where(m => m != null))
                    {
                        sb.AppendLine("    material " + m.name + " shader " + (m.shader != null ? m.shader.name : "none") + " keywords [" + string.Join(" ", m.shaderKeywords) + "] textures [" + string.Join(" ", m.GetTexturePropertyNames().Where(p => m.GetTexture(p) != null).Select(p => p + "=" + m.GetTexture(p).name + " " + m.GetTexture(p).width)) + "]");
                    }
                }
            }
            bundle.Unload(true);
        }
        foreach (var b in loaded) { b.Unload(true); }
        File.WriteAllText(System.IO.Path.Combine(Directory.GetCurrentDirectory(), "Build", "probe-features.txt"), sb.ToString());
    }

    private static string PathOf(Transform t, Transform root)
    {
        string s = t.name;
        while (t.parent != null && t.parent != root) { t = t.parent; s = t.name + "/" + s; }
        return s;
    }
}
