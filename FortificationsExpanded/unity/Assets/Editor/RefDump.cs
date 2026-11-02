using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>Dumps the vanilla models this mod's pieces are measured against (parts, bounds, materials and a render)
/// to Build/, as a reference for building the models. Run: Unity -batchmode -quit -projectPath unity -executeMethod
/// RefDump.Run</summary>
public static class RefDump
{
    private static readonly string[] Refs =
    {
        "sandbag_straight_01prefab.prefab", "chainlinkfencemiddleprefab.prefab", "chainlinkfencedoordoubleprefab.prefab",
        "doorwoodlargegateprefab.prefab", "shippingcontainerdoorframeprefab.prefab",
    };

    public static void Run()
    {
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string root = Path.Combine(game, "Data/Addressables/Standalone");
        foreach (string name in Refs)
        {
            string stem = name.Replace(".prefab", "");
            VanillaCompare.DumpVanilla(name, Path.Combine(output, "ref-" + stem + ".txt"), Path.Combine(output, "ref-" + stem + ".png"));
        }
        // Materials of the chain-link and the container (cutout wire mesh, tint mask)
        string[] bundles = { "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
            "automatic_assets_entities/buildings.bundle", "automatic_assets_entities/industrial.bundle", "automatic_assets_entities/doors.bundle", "automatic_assets_entities/sandbags.bundle" };
        var loaded = bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(root, b))).Where(b => b != null).ToList();
        StringBuilder log = new StringBuilder();
        foreach (string name in new[] { "sandbag_straight_01prefab.prefab", "chainlinkfencemiddleprefab.prefab", "shippingcontainerdoorframeprefab.prefab", "doorwoodlargegateprefab.prefab" })
        {
            foreach (AssetBundle bundle in loaded)
            {
                string asset = bundle.GetAllAssetNames().FirstOrDefault(n => n.ToLowerInvariant().EndsWith("/" + name));
                if (asset != null)
                {
                    log.AppendLine("==== " + name);
                    GameObject go = bundle.LoadAsset<GameObject>(asset);
                    VanillaCompare.DescribeRenderers(go, log);
                    Animator anim = go.GetComponentInChildren<Animator>(true);
                    log.AppendLine("animator: " + (anim != null ? anim.name + " controller " + (anim.runtimeAnimatorController != null ? anim.runtimeAnimatorController.name : "none") : "none"));
                    if (anim != null && anim.runtimeAnimatorController != null)
                    {
                        foreach (AnimationClip clip in anim.runtimeAnimatorController.animationClips)
                        {
                            log.AppendLine("  clip " + clip.name + " " + clip.length + "s");
                        }
                    }
                }
            }
        }
        File.WriteAllText(Path.Combine(output, "ref-materials.txt"), log.ToString());
        foreach (AssetBundle b in loaded)
        {
            b.Unload(true);
        }
    }
}
