using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Loads vanilla zombies straight from the game's asset bundles (built with this same Unity version) and writes how
/// they're put together to Build/zombie-probe.txt: hierarchy, bones, renderers, materials and every shader property,
/// animator parameters and colliders. Renders them to Build/zombie-probe.png. Reference only: nothing from the game is
/// copied into the mod.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod ZombieProbe.Run (with graphics).
/// </summary>
public static class ZombieProbe
{
    private static readonly string[] Bundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "textures_assets_textures", "animations_assets_animations/zombie.bundle",
        "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
        "zombies_assets_entities/zombies/cop.bundle", "zombies_assets_entities/zombies/frostclaw.bundle",
        "zombies_assets_entities/zombies/plaguespitter.bundle", "zombies_assets_entities/zombies/burnt.bundle",
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
            string file = Path.Combine(root, b);
            if (Directory.Exists(file))
            {
                foreach (string f in Directory.GetFiles(file, "*.bundle"))
                {
                    Load(f, loaded, log);
                }
                continue;
            }
            Load(file, loaded, log);
        }

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        List<GameObject> lineup = new List<GameObject>();
        HashSet<Shader> shaders = new HashSet<Shader>();
        foreach (AssetBundle bundle in loaded)
        {
            foreach (string path in bundle.GetAllAssetNames().Where(x => x.ToLowerInvariant() is string n && n.StartsWith("assets/assetbundles/zombies/")
                && (System.IO.Path.GetFileName(n).StartsWith("z") && n.EndsWith(".prefab") || n.EndsWith("zcontroller.controller")
                    || n.EndsWith("dynamic_feral_eye.mat"))))
            {
                if (path.ToLowerInvariant().EndsWith(".controller"))
                {
                    log.AppendLine();
                    log.AppendLine("================ " + path);
                    Controller(bundle.LoadAsset<RuntimeAnimatorController>(path), log);
                    continue;
                }
                if (path.ToLowerInvariant().EndsWith(".mat"))
                {
                    log.AppendLine();
                    log.AppendLine("================ " + path);
                    GameObject holder = new GameObject("eye");
                    holder.AddComponent<MeshFilter>();
                    holder.AddComponent<MeshRenderer>().sharedMaterial = bundle.LoadAsset<Material>(path);
                    Describe(holder, log, shaders);
                    Object.DestroyImmediate(holder);
                    continue;
                }
                GameObject prefab = bundle.LoadAsset<GameObject>(path);
                if (prefab == null)
                {
                    log.AppendLine("could not load " + path);
                    continue;
                }
                log.AppendLine();
                log.AppendLine("================ " + path);
                Describe(prefab, log, shaders);
                if (lineup.Count < 6 && prefab.GetComponentInChildren<SkinnedMeshRenderer>(true) != null && !path.ToLowerInvariant().Contains("feral"))
                {
                    lineup.Add(Object.Instantiate(prefab));
                }
            }
        }

        foreach (Shader s in shaders)
        {
            log.AppendLine();
            log.AppendLine("================ shader " + s.name + " passes " + s.passCount);
            for (int i = 0; i < s.GetPropertyCount(); i++)
            {
                log.AppendLine("  " + s.GetPropertyName(i) + " (" + s.GetPropertyType(i) + ") \"" + s.GetPropertyDescription(i) + "\"");
            }
        }

        try
        {
            Render(lineup, Path.Combine(output, "zombie-probe.png"));
        }
        catch (System.Exception e)
        {
            log.AppendLine("render failed: " + e);
        }

        File.WriteAllText(Path.Combine(output, "zombie-probe.txt"), log.ToString());
        foreach (AssetBundle bundle in loaded)
        {
            bundle.Unload(true);
        }
    }

    private static void Load(string file, List<AssetBundle> loaded, StringBuilder log)
    {
        AssetBundle bundle = AssetBundle.LoadFromFile(file);
        log.AppendLine("bundle " + file + ": " + (bundle != null ? "loaded" : "FAILED"));
        if (bundle == null)
        {
            return;
        }
        loaded.Add(bundle);
        string[] names = bundle.GetAllAssetNames();
        log.AppendLine("  " + names.Length + " assets");
        if (file.Contains("zombies") || file.Contains("animations"))
        {
            foreach (string n in names.Where(n => !n.EndsWith(".png") && !n.EndsWith(".tga") && !n.EndsWith(".tif")).Take(150))
            {
                log.AppendLine("    " + n);
            }
        }
    }

    private static void Describe(GameObject prefab, StringBuilder log, HashSet<Shader> shaders)
    {
        log.AppendLine("hierarchy:");
        Hierarchy(prefab.transform, 0, log);
        foreach (Renderer r in prefab.GetComponentsInChildren<Renderer>(true))
        {
            log.Append("renderer " + PathOf(r.transform) + " (" + r.GetType().Name + ")");
            if (r is SkinnedMeshRenderer smr)
            {
                Mesh m = smr.sharedMesh;
                log.Append(" mesh " + (m == null ? "none" : m.name + " verts " + m.vertexCount + " submeshes " + m.subMeshCount
                    + " readable " + m.isReadable + " blendshapes " + m.blendShapeCount + " uv2 " + (m.uv2 != null && m.uv2.Length > 0) + " colors " + (m.colors != null && m.colors.Length > 0))
                    + " bones " + smr.bones.Length + " root " + (smr.rootBone == null ? "none" : smr.rootBone.name));
                if (m != null && m.blendShapeCount > 0)
                {
                    log.Append(" [" + string.Join(", ", Enumerable.Range(0, m.blendShapeCount).Select(i => m.GetBlendShapeName(i))) + "]");
                }
            }
            else if (r.TryGetComponent(out MeshFilter mf) && mf.sharedMesh != null)
            {
                log.Append(" mesh " + mf.sharedMesh.name + " verts " + mf.sharedMesh.vertexCount);
            }
            log.AppendLine(" enabled " + r.enabled + " active " + r.gameObject.activeSelf);
            foreach (Material mat in r.sharedMaterials)
            {
                if (mat == null)
                {
                    log.AppendLine("  material null");
                    continue;
                }
                Shader s = mat.shader;
                shaders.Add(s);
                log.AppendLine("  material " + mat.name + " shader '" + s.name + "' queue " + mat.renderQueue
                    + " keywords [" + string.Join(" ", mat.shaderKeywords) + "]");
                for (int i = 0; i < s.GetPropertyCount(); i++)
                {
                    string prop = s.GetPropertyName(i);
                    switch (s.GetPropertyType(i))
                    {
                        case ShaderPropertyType.Float:
                        case ShaderPropertyType.Range:
                            log.AppendLine("    " + prop + " = " + mat.GetFloat(prop).ToString("F3"));
                            break;
                        case ShaderPropertyType.Color:
                        case ShaderPropertyType.Vector:
                            log.AppendLine("    " + prop + " = " + mat.GetVector(prop).ToString("F3"));
                            break;
                        case ShaderPropertyType.Texture:
                            Texture t = mat.GetTexture(prop);
                            log.AppendLine("    " + prop + " = " + (t == null ? "none" : t.name + " " + t.width + "x" + t.height
                                + " " + (t is Texture2D t2 ? t2.format.ToString() : t.GetType().Name)));
                            break;
                    }
                }
            }
        }
        foreach (Animator a in prefab.GetComponentsInChildren<Animator>(true))
        {
            log.AppendLine("animator on " + PathOf(a.transform) + " avatar " + (a.avatar == null ? "none" : a.avatar.name + " human " + a.avatar.isHuman)
                + " controller " + (a.runtimeAnimatorController == null ? "none" : a.runtimeAnimatorController.name + " (" + a.runtimeAnimatorController.GetType().Name + ")"));
            Controller(a.runtimeAnimatorController, log);
        }
        foreach (Collider c in prefab.GetComponentsInChildren<Collider>(true))
        {
            log.AppendLine("collider " + PathOf(c.transform) + " " + c.GetType().Name + " layer " + c.gameObject.layer + " tag " + c.gameObject.tag
                + (c is CapsuleCollider cc ? " r " + cc.radius.ToString("F2") + " h " + cc.height.ToString("F2") : "")
                + (c.isTrigger ? " trigger" : ""));
        }
    }

    private static void Controller(RuntimeAnimatorController rac, StringBuilder log)
    {
        {
            if (rac is UnityEditor.Animations.AnimatorController ac)
            {
                foreach (AnimatorControllerParameter p in ac.parameters)
                {
                    log.AppendLine("  param " + p.name + " " + p.type);
                }
                foreach (var layer in ac.layers)
                {
                    log.AppendLine("  layer " + layer.name + " states: " + string.Join(", ", layer.stateMachine.states.Select(s => s.state.name))
                        + " | sub: " + string.Join(", ", layer.stateMachine.stateMachines.Select(s => s.stateMachine.name + "{" + string.Join(", ", s.stateMachine.states.Select(x => x.state.name)) + "}")));
                }
            }
            else if (rac is AnimatorOverrideController oc)
            {
                log.AppendLine("  override of " + (oc.runtimeAnimatorController == null ? "none" : oc.runtimeAnimatorController.name)
                    + " clips " + string.Join(", ", oc.animationClips.Select(c => c.name)));
            }
            else
            {
                log.AppendLine("  controller type " + (rac == null ? "null" : rac.GetType().Name) + " clips "
                    + (rac == null ? "" : string.Join(", ", rac.animationClips.Select(c => c.name).Distinct())));
            }
        }
    }

    private static void Hierarchy(Transform t, int depth, StringBuilder log)
    {
        if (depth > 14)
        {
            return;
        }
        string comps = string.Join(",", t.GetComponents<Component>().Where(c => !(c is Transform))
            .Select(c => c == null ? "MISSING" : c.GetType().Name));
        log.AppendLine(new string(' ', depth * 2) + t.name + (comps.Length > 0 ? " [" + comps + "]" : "")
            + (t.gameObject.activeSelf ? "" : " (inactive)") + " pos " + t.localPosition.ToString("F2"));
        foreach (Transform c in t)
        {
            Hierarchy(c, depth + 1, log);
        }
    }

    private static string PathOf(Transform t)
    {
        string p = t.name;
        while (t.parent != null)
        {
            t = t.parent;
            p = t.name + "/" + p;
        }
        return p;
    }

    private static void Render(List<GameObject> lineup, string path)
    {
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = new Color(1f, 0.93f, 0.84f);
        sun.intensity = 1.4f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(30f, 150f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.45f, 0.5f, 0.6f);
        RenderSettings.ambientEquatorColor = new Color(0.35f, 0.35f, 0.35f);
        RenderSettings.ambientGroundColor = new Color(0.18f, 0.17f, 0.15f);
        for (int i = 0; i < lineup.Count; i++)
        {
            lineup[i].transform.position = new Vector3((i - (lineup.Count - 1) / 2f) * 1.3f, 0f, 0f);
            lineup[i].transform.rotation = Quaternion.Euler(0f, 180f, 0f);
        }
        const int width = 2400, height = 1000;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 30f;
        camera.transform.position = new Vector3(0f, 1.2f, -7.5f);
        camera.transform.LookAt(new Vector3(0f, 0.95f, 0f));
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
