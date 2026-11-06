using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Turns the Blender exports in Assets/FortificationsExpanded/&lt;Family&gt;/ into game prefabs (one per FBX, named
/// after it) and builds them into one asset bundle, then renders each finished piece with the game's shader beside
/// vanilla sandbags to Build/&lt;Piece&gt;-preview.png. Run from src/build-models.bat (batch mode with graphics).
///
/// A family folder holds its FBX files and the textures of the materials they share (M_Albedo, M_Normal, M_RMOM: the
/// packed map of the game's model shader). The materials are Standard ones that carry the RMOM map in their unused
/// _DetailMask slot; the mod switches them to the game's shader (Game/Entity Tint Mask) when a block spawns. A
/// material whose name ends in "Mesh" is wire mesh, cut out by its albedo's alpha (Standard Cutout, carried over to
/// the game shader's alpha test).
///
/// Pieces: the game finds damage stages and the burst point by name directly under the prefab root (MeshDamage
/// "DMG0,...": transform.Find), so the FBX's objects are moved up to the root: DMG0 starts active, DMG1 and DMG2
/// hidden, and FX gets the debris burst the game emits (10 particles) whenever a stage breaks. The root carries a
/// BoxCollider around the intact stage, kept inside the block's footprint (the game reads the block's bounds and
/// collision from it).
///
/// Gates: vanilla doors drive an Animator (bool IsOpen, trigger OpenTrigger, states Open and Close) and find their
/// single stage at Door/DMG0. So a gate's Frame and leaves go under Door/DMG0, the leaves get box colliders and the
/// frame a mesh collider (no root collider, so the opening is clear), and an Open and a Close clip swing the leaves
/// 90 degrees out about their hinges (origins) or slide the rolling leaf aside.
///
/// Tags and layers are set by the mod's C# when the block spawns, because a bundle stores tags as indexes into this
/// project's tag list.
/// </summary>
public static class FortBuilder
{
    private const string BundleName = "fortificationsexpanded.unity3d";
    private const string Root = "Assets/FortificationsExpanded";
    private const string Fx = Root + "/Fx";

    /// <summary>Each family and the colour of the debris that bursts out when one of its stages breaks.</summary>
    private static readonly (string Name, Color Debris)[] Families =
    {
        ("Sandbags", new Color(0.72f, 0.63f, 0.47f)),
        ("Palisade", new Color(0.45f, 0.34f, 0.22f)),
        ("ChainLink", new Color(0.5f, 0.5f, 0.5f)),
        ("Hesco", new Color(0.5f, 0.42f, 0.32f)),
        ("TankTraps", new Color(0.42f, 0.38f, 0.34f)),
        ("Container", new Color(0.45f, 0.4f, 0.36f)),
        ("PicketFence", new Color(0.55f, 0.52f, 0.46f)),
        ("PostRail", new Color(0.5f, 0.46f, 0.4f)),
        ("RazorWire", new Color(0.42f, 0.38f, 0.34f)),
        ("PalletWall", new Color(0.45f, 0.38f, 0.28f)),
        ("HedgeRow", new Color(0.28f, 0.34f, 0.14f)),
        ("StoneWorks", new Color(0.46f, 0.43f, 0.38f)),
    };

    /// <summary>Footprints in blocks (wide, deep) by piece name prefix, longest first; everything else is 1 by 1.</summary>
    private static readonly (string Prefix, float Wide, float Deep)[] Footprints =
    {
        ("TankTrapHedgehog", 2f, 2f), ("TankTrapLine", 3f, 1f), ("HescoDouble", 2f, 1f), ("ContainerWall", 3f, 1f),
        ("ContainerGate", 3f, 1f), ("PalisadeGate", 3f, 1f), ("ChainLinkGate", 3f, 1f),
        ("PicketFenceGate", 2f, 1f), ("PostRailGate", 2f, 1f),
    };

    /// <summary>How each gate leaf opens: degrees about the vertical hinge, or metres to slide along the gate's X
    /// axis. The FBX import mirrors X (Blender +X is Unity -X; Blender's front, -Y, is Unity +Z), so Blender's
    /// LeftLeaf hinges on Unity +X with its free end toward -X, and a positive angle (which turns -X toward +Z) swings
    /// it out to the front. The rolling leaf slides toward Blender +X, Unity -X. Checked in the open-state
    /// previews.</summary>
    private static readonly Dictionary<string, (float Swing, float Slide)> Leaves = new Dictionary<string, (float, float)>
    {
        { "LeftLeaf", (90f, 0f) }, { "RightLeaf", (-90f, 0f) }, { "SlideLeaf", (0f, -2.9f) },
    };

    private const float GateSeconds = 1.6f;

    public static void BuildAndPreview()
    {
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[]
        {
            GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan,
            GraphicsDeviceType.OpenGLCore,
        });
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (!AssetDatabase.IsValidFolder(Fx))
        {
            AssetDatabase.CreateFolder(Root, "Fx");
        }

        // "-fortFamilies A,B" on the command line builds only those families (to test one while others are made)
        string[] args = System.Environment.GetCommandLineArgs();
        int only = System.Array.IndexOf(args, "-fortFamilies");
        HashSet<string> wanted = only >= 0 && only + 1 < args.Length ? new HashSet<string>(args[only + 1].Split(',')) : null;

        List<string> prefabs = new List<string>();
        List<string> problems = new List<string>();
        foreach ((string family, Color debris) in Families)
        {
            if (wanted != null && !wanted.Contains(family))
            {
                continue;
            }
            string folder = Root + "/" + family;
            if (!AssetDatabase.IsValidFolder(folder))
            {
                Debug.LogWarning("[FortBuilder] no " + folder + " yet; skipped");
                continue;
            }
            foreach (string path in Directory.GetFiles(folder, "*.png"))
            {
                ConfigureTexture(path.Replace('\\', '/'));
            }
            foreach (string fbx in Directory.GetFiles(folder, "*.fbx").Select(p => p.Replace('\\', '/')).OrderBy(p => p))
            {
                prefabs.Add(MakePrefab(folder, fbx, family, debris, problems));
            }
        }
        AssetDatabase.SaveAssets();
        // Every model a block's MeshDamage names its stages in (written by gen_fortifications.py) must have all three:
        // the game finds them with transform.Find and no null check
        string staged = Path.Combine(Directory.GetCurrentDirectory(), "staged-models.txt");
        if (File.Exists(staged))
        {
            foreach (string model in File.ReadAllLines(staged).Select(l => l.Trim()).Where(l => l.Length > 0))
            {
                string prefab = prefabs.FirstOrDefault(p => Path.GetFileNameWithoutExtension(p) == model);
                if (prefab == null)
                {
                    if (wanted == null)
                    {
                        problems.Add(model + ": no model");
                    }
                    continue;
                }
                GameObject go = AssetDatabase.LoadAssetAtPath<GameObject>(prefab);
                foreach (string stage in new[] { "DMG0", "DMG1", "DMG2" })
                {
                    if (go.transform.Find(stage) == null)
                    {
                        problems.Add(model + ": its MeshDamage needs " + stage);
                    }
                }
            }
        }
        foreach (string p in problems)
        {
            Debug.LogError("[FortBuilder] PROBLEM " + p);
        }
        if (problems.Count > 0)
        {
            throw new System.Exception(problems.Count + " model problems; see the log above");
        }

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = prefabs.ToArray() };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode
                | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[FortBuilder] Built " + Path.Combine(output, BundleName) + " with " + prefabs.Count + " prefabs");

        // Previews: the finished stage of each piece, and every gate open and closed
        // "-fortPreview A,B" renders previews only for those families (the bundle always holds them all)
        int previewArg = System.Array.IndexOf(args, "-fortPreview");
        HashSet<string> previewFamilies = previewArg >= 0 && previewArg + 1 < args.Length
            ? new HashSet<string>(args[previewArg + 1].Split(',')) : null;
        foreach (string prefab in prefabs)
        {
            string stem = Path.GetFileNameWithoutExtension(prefab);
            if (previewFamilies != null && !previewFamilies.Contains(Path.GetFileName(Path.GetDirectoryName(prefab))))
            {
                continue;
            }
            bool finished = stem.EndsWith("Full") || stem.EndsWith("Taut") && stem.Contains("Light")
                || new[]
                {
                    "PalisadeSection", "PalisadeCorner", "TankTrapHedgehog", "TankTrapLine", "ContainerWall", "ContainerCorner",
                    "PicketFenceSection", "PicketFenceCorner", "PostRailSection", "PostRailCorner", "RazorWireSection",
                    "RazorWireCorner", "PalletWallSection", "PalletWallCorner", "HedgeRowFullB", "HedgeRowFullC",
                    "HedgeRowSaplingA", "HedgeRowSaplingB", "HedgeRowYoungA", "HedgeRowYoungB", "ArrowSlitWall",
                    "ArrowSlitCorner", "Battlement", "BattlementCorner",
                }.Contains(stem);
            if (finished || stem.EndsWith("Gate"))
            {
                bool tall = stem.StartsWith("ArrowSlit") || stem.StartsWith("PalletWall");
                VanillaCompare.Preview(prefab, Path.Combine(output, stem + "-preview.png"),
                    "sandbag_straight_01prefab.prefab", "sandbag_corner_01prefab.prefab", stem.EndsWith("Gate") ? 2.6f : 1.6f,
                    stem.EndsWith("Gate") || stem.StartsWith("Container") || stem.StartsWith("TankTrap") ? 1.8f
                        : stem.StartsWith("ArrowSlit") ? 2.1f : tall ? 1.5f : 1.25f);
            }
            if (stem.EndsWith("Gate"))
            {
                PreviewOpen(prefab, Path.Combine(output, stem + "-open-preview.png"));
            }
            // The damaged stages of the new families, to check none are swapped
            if (StagePreviews.Contains(stem))
            {
                foreach (string stage in new[] { "DMG1", "DMG2" })
                {
                    PreviewStage(prefab, stage, Path.Combine(output, stem + "-" + stage + "-preview.png"),
                        stem.StartsWith("ArrowSlit") ? 2.1f : stem.StartsWith("PalletWall") ? 1.5f : 1.25f);
                }
            }
        }
    }

    private static (float Wide, float Deep) Footprint(string piece)
    {
        foreach ((string prefix, float wide, float deep) in Footprints)
        {
            if (piece.StartsWith(prefix))
            {
                return (wide, deep);
            }
        }
        return (1f, 1f);
    }

    private static string MakePrefab(string folder, string fbx, string family, Color debris, List<string> problems)
    {
        string piece = Path.GetFileNameWithoutExtension(fbx);
        bool gate = piece.EndsWith("Gate");
        ModelImporter model = (ModelImporter)AssetImporter.GetAtPath(fbx);
        model.globalScale = 1f;
        model.useFileScale = true;
        model.importNormals = ModelImporterNormals.Import;
        model.importTangents = ModelImporterTangents.CalculateMikk;
        model.animationType = ModelImporterAnimationType.None;
        model.importAnimation = false;
        model.importCameras = false;
        model.importLights = false;
        // The gate frame's mesh collider needs its mesh
        model.isReadable = gate;
        model.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        model.materialLocation = ModelImporterMaterialLocation.InPrefab;
        model.SaveAndReimport();

        string[] names = AssetDatabase.LoadAllAssetsAtPath(fbx).OfType<Material>().Select(m => m.name)
            .Concat(model.GetExternalObjectMap().Keys.Where(k => k.type == typeof(Material)).Select(k => k.name))
            .Distinct().ToArray();
        foreach (string name in names)
        {
            model.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), name), MakeMaterial(folder, name));
        }
        model.SaveAndReimport();

        GameObject root = new GameObject(piece);
        GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));
        PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        // An FBX with one object imports as that object itself; with several, as a parent holding them
        List<Transform> parts = instance.GetComponent<Renderer>() != null
            ? new List<Transform> { instance.transform }
            : instance.transform.Cast<Transform>().ToList();
        Transform holder = root.transform;
        if (gate)
        {
            Transform door = new GameObject("Door").transform;
            door.SetParent(root.transform, false);
            holder = new GameObject("DMG0").transform;
            holder.SetParent(door, false);
        }
        foreach (Transform part in parts)
        {
            part.SetParent(holder, true);
        }
        if (!parts.Contains(instance.transform))
        {
            Object.DestroyImmediate(instance);
        }
        if (!gate && parts.Count == 1 && parts[0].name != "DMG0")
        {
            parts[0].name = "DMG0";
        }

        foreach (Renderer r in root.GetComponentsInChildren<Renderer>(true))
        {
            r.shadowCastingMode = ShadowCastingMode.On;
            r.receiveShadows = true;
        }
        (float wide, float deep) = Footprint(piece);

        if (gate)
        {
            BuildGate(folder, piece, root, holder, problems);
        }
        else
        {
            Transform intact = root.transform.Find("DMG0");
            if (intact == null || intact.GetComponent<Renderer>() == null)
            {
                problems.Add(piece + ": no DMG0 mesh");
                intact = root.transform.GetComponentsInChildren<Renderer>(true).First().transform;
            }
            foreach (string stage in new[] { "DMG1", "DMG2" })
            {
                Transform t = root.transform.Find(stage);
                if (t != null)
                {
                    t.gameObject.SetActive(false);
                }
            }
            if (root.transform.Find("DMG1") != null && root.transform.Find("DMG2") == null)
            {
                problems.Add(piece + ": has DMG1 but no DMG2");
            }
            Bounds bounds = intact.GetComponent<Renderer>().bounds;
            BoxCollider collider = root.AddComponent<BoxCollider>();
            // Around the intact stage (an L-shaped corner's box sits off-centre), clipped to the block's footprint so
            // spill piles, a leaning shovel or overhanging bags don't push it out of the cells
            Vector3 half = new Vector3(wide / 2f, 0f, deep / 2f);
            Vector3 lo = new Vector3(Mathf.Max(bounds.min.x, -half.x), bounds.min.y, Mathf.Max(bounds.min.z, -half.z));
            Vector3 hi = new Vector3(Mathf.Min(bounds.max.x, half.x), bounds.max.y, Mathf.Min(bounds.max.z, half.z));
            collider.center = (lo + hi) / 2f;
            collider.size = hi - lo;
            Debug.Log("[FortBuilder] " + piece + " bounds center " + bounds.center.ToString("F3") + " size "
                + bounds.size.ToString("F3") + ", parts " + string.Join(", ", root.transform.Cast<Transform>().Select(t => t.name))
                + ", materials " + string.Join(", ", names));
        }

        Transform fx = root.transform.Find("FX");
        if (fx != null)
        {
            DebrisBurst(fx.gameObject, family, debris);
        }

        string prefabPath = folder + "/" + piece + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Object.DestroyImmediate(root);
        return prefabPath;
    }

    // ------------------------------------------------------------------ gates

    private static void BuildGate(string folder, string piece, GameObject root, Transform holder, List<string> problems)
    {
        // Leaves may come nested (the rolling gate's leaf is a child of its frame); they move on their own, so they go
        // straight under DMG0 where the clips can find them by a fixed path
        List<Transform> leaves = holder.GetComponentsInChildren<Transform>(true).Where(t => Leaves.ContainsKey(t.name)).ToList();
        foreach (Transform leaf in leaves)
        {
            leaf.SetParent(holder, true);
        }
        if (leaves.Count == 0)
        {
            problems.Add(piece + ": no LeftLeaf/RightLeaf/SlideLeaf");
        }
        foreach (Transform part in holder.GetComponentsInChildren<Transform>(true).Where(t => t != holder))
        {
            MeshFilter mf = part.GetComponent<MeshFilter>();
            if (mf == null)
            {
                continue;
            }
            if (Leaves.ContainsKey(part.name))
            {
                // A box around the leaf in its own frame, so it turns or slides with it
                Bounds local = mf.sharedMesh.bounds;
                BoxCollider box = part.gameObject.AddComponent<BoxCollider>();
                box.center = local.center;
                box.size = local.size;
            }
            else
            {
                MeshCollider mc = part.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
            }
        }

        string path = folder + "/" + piece;
        AnimationClip open = LeafClip(root.transform, leaves, true);
        AnimationClip close = LeafClip(root.transform, leaves, false);
        SaveAsset(open, path + "_Open.anim");
        SaveAsset(close, path + "_Close.anim");

        string controllerPath = path + "_Controller.controller";
        AssetDatabase.DeleteAsset(controllerPath);
        AnimatorController controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
        controller.AddParameter("IsOpen", AnimatorControllerParameterType.Bool);
        controller.AddParameter("OpenTrigger", AnimatorControllerParameterType.Trigger);
        AnimatorStateMachine sm = controller.layers[0].stateMachine;
        AnimatorState closeState = sm.AddState("Close");
        closeState.motion = AssetDatabase.LoadAssetAtPath<AnimationClip>(path + "_Close.anim");
        AnimatorState openState = sm.AddState("Open");
        openState.motion = AssetDatabase.LoadAssetAtPath<AnimationClip>(path + "_Open.anim");
        sm.defaultState = closeState;
        AnimatorStateTransition toOpen = closeState.AddTransition(openState);
        toOpen.hasExitTime = false;
        toOpen.duration = 0f;
        toOpen.AddCondition(AnimatorConditionMode.If, 0f, "IsOpen");
        AnimatorStateTransition toClose = openState.AddTransition(closeState);
        toClose.hasExitTime = false;
        toClose.duration = 0f;
        toClose.AddCondition(AnimatorConditionMode.IfNot, 0f, "IsOpen");
        AssetDatabase.SaveAssets();

        Animator animator = root.AddComponent<Animator>();
        animator.runtimeAnimatorController = controller;
        // Always: the leaf colliders move with the animation, and a dedicated server (or a host looking away) has no
        // visible renderer, so a culled animator would leave an open gate's colliders shut
        animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
        Debug.Log("[FortBuilder] " + piece + " gate: leaves " + string.Join(", ", leaves.Select(l => l.name + " at "
            + root.transform.InverseTransformPoint(l.position).ToString("F3"))));
    }

    /// <summary>Opening (or closing) from one pose to the other, eased, for every leaf.</summary>
    private static AnimationClip LeafClip(Transform root, List<Transform> leaves, bool opening)
    {
        AnimationClip clip = new AnimationClip { name = opening ? "Open" : "Close" };
        foreach (Transform leaf in leaves)
        {
            string path = AnimationUtility.CalculateTransformPath(leaf, root);
            (float swing, float slide) = Leaves[leaf.name];
            Quaternion shut = leaf.localRotation;
            Quaternion wide = Quaternion.AngleAxis(swing, Vector3.up) * shut;
            Vector3 home = leaf.localPosition;
            Vector3 aside = home + new Vector3(slide, 0f, 0f);
            Quaternion r0 = opening ? shut : wide, r1 = opening ? wide : shut;
            Vector3 p0 = opening ? home : aside, p1 = opening ? aside : home;
            const int steps = 8;
            AnimationCurve[] rot = { new AnimationCurve(), new AnimationCurve(), new AnimationCurve(), new AnimationCurve() };
            AnimationCurve[] pos = { new AnimationCurve(), new AnimationCurve(), new AnimationCurve() };
            for (int i = 0; i <= steps; i++)
            {
                float t = i / (float)steps;
                float e = Mathf.SmoothStep(0f, 1f, t);
                Quaternion q = Quaternion.Slerp(r0, r1, e);
                Vector3 p = Vector3.Lerp(p0, p1, e);
                float time = t * GateSeconds;
                rot[0].AddKey(time, q.x);
                rot[1].AddKey(time, q.y);
                rot[2].AddKey(time, q.z);
                rot[3].AddKey(time, q.w);
                pos[0].AddKey(time, p.x);
                pos[1].AddKey(time, p.y);
                pos[2].AddKey(time, p.z);
            }
            string[] rotNames = { "localRotation.x", "localRotation.y", "localRotation.z", "localRotation.w" };
            string[] posNames = { "localPosition.x", "localPosition.y", "localPosition.z" };
            for (int i = 0; i < 4; i++)
            {
                clip.SetCurve(path, typeof(Transform), rotNames[i], rot[i]);
            }
            for (int i = 0; i < 3; i++)
            {
                clip.SetCurve(path, typeof(Transform), posNames[i], pos[i]);
            }
        }
        clip.EnsureQuaternionContinuity();
        return clip;
    }

    private static void SaveAsset(Object asset, string path)
    {
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(asset, path);
    }

    private static readonly HashSet<string> StagePreviews = new HashSet<string>
    {
        "PicketFenceSection", "PostRailSection", "RazorWireSection", "PalletWallSection", "HedgeRowFull", "HedgeRowFullB",
        "HedgeRowFullC", "ArrowSlitWall", "ArrowSlitCorner", "Battlement", "BattlementCorner", "PicketFenceCorner",
        "PostRailCorner", "RazorWireCorner", "PalletWallCorner",
    };

    /// <summary>One damage stage (DMG1 or DMG2) shown in place of the intact one, rendered like the other previews.</summary>
    private static void PreviewStage(string prefabPath, string stage, string output, float distance)
    {
        string temp = prefabPath.Replace(".prefab", "_" + stage + "Preview.prefab");
        GameObject go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath));
        PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        foreach (string s in new[] { "DMG0", "DMG1", "DMG2" })
        {
            Transform t = go.transform.Find(s);
            if (t != null)
            {
                t.gameObject.SetActive(s == stage);
            }
        }
        PrefabUtility.SaveAsPrefabAsset(go, temp);
        Object.DestroyImmediate(go);
        VanillaCompare.Preview(temp, output, "sandbag_straight_01prefab.prefab", "sandbag_corner_01prefab.prefab", 1.6f, distance);
        AssetDatabase.DeleteAsset(temp);
    }

    /// <summary>The gate with its Open clip played to the end, rendered like the other previews.</summary>
    private static void PreviewOpen(string prefabPath, string output)
    {
        string temp = prefabPath.Replace(".prefab", "_OpenPreview.prefab");
        GameObject go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath));
        AnimationClip open = AssetDatabase.LoadAssetAtPath<AnimationClip>(prefabPath.Replace(".prefab", "_Open.anim"));
        PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        open.SampleAnimation(go, open.length);
        Object.DestroyImmediate(go.GetComponent<Animator>());
        PrefabUtility.SaveAsPrefabAsset(go, temp);
        Object.DestroyImmediate(go);
        VanillaCompare.Preview(temp, output, "sandbag_straight_01prefab.prefab", "sandbag_corner_01prefab.prefab", 2.6f, 1.8f);
        AssetDatabase.DeleteAsset(temp);
    }

    // ------------------------------------------------------------------ effects

    /// <summary>
    /// The burst when a damage stage breaks: the game calls Emit(10) on the first particle system under FX, so each
    /// particle is a big soft clump of the family's debris (sand, dirt, splinter dust, rust and grit) that bursts out
    /// of the front face and falls.
    /// </summary>
    private static void DebrisBurst(GameObject go, string family, Color color)
    {
        ParticleSystem ps = go.AddComponent<ParticleSystem>();
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = DustMaterial(family + "Burst", color);
        r.renderMode = ParticleSystemRenderMode.Billboard;
        r.shadowCastingMode = ShadowCastingMode.Off;
        r.receiveShadows = false;
        ParticleSystem.MainModule main = ps.main;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.playOnAwake = false;
        main.loop = false;
        main.scalingMode = ParticleSystemScalingMode.Hierarchy;
        main.duration = 1f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.9f, 1.6f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.8f, 2.2f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.35f, 0.7f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.gravityModifier = 0.6f;
        main.maxParticles = 60;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.enabled = false;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 50f;
        shape.radius = 0.3f;
        // Out of the front face (+Z in Unity is the model's front)
        go.transform.localRotation = Quaternion.identity;
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient g = new Gradient();
        g.SetKeys(new[] { new GradientColorKey(color, 0f), new GradientColorKey(color * 0.9f, 1f) },
            new[] { new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0.55f, 0.4f), new GradientAlphaKey(0f, 1f) });
        col.color = new ParticleSystem.MinMaxGradient(g);
        ParticleSystem.SizeOverLifetimeModule size = ps.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.7f, 1f, 1.6f));
    }

    private static Texture2D Puff()
    {
        Directory.CreateDirectory(Fx);
        string path = Fx + "/Puff.png";
        if (!File.Exists(path))
        {
            const int size = 64;
            Texture2D t = new Texture2D(size, size, TextureFormat.RGBA32, false, true);
            System.Random rnd = new System.Random(7);
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f) / size - 0.5f, dy = (y + 0.5f) / size - 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy) * 2f;
                    float grain = 0.75f + 0.25f * (float)rnd.NextDouble();
                    float a = Mathf.Clamp01(1f - d);
                    t.SetPixel(x, y, new Color(grain, grain, grain, a * a * grain));
                }
            }
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
            importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.alphaIsTransparency = true;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.SaveAndReimport();
        }
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    /// <summary>A lit, alpha-faded particle material (Particles/Standard Surface in Fade mode), so the dust takes the
    /// scene's light instead of glowing at night.</summary>
    private static Material DustMaterial(string name, Color color)
    {
        string path = Fx + "/" + name + ".mat";
        Shader shader = Shader.Find("Particles/Standard Surface") ?? Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        m.shaderKeywords = new string[0];
        m.SetTexture("_MainTex", Puff());
        m.SetColor("_Color", color);
        m.SetFloat("_Mode", 2f);
        m.SetOverrideTag("RenderType", "Transparent");
        m.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        m.SetInt("_ZWrite", 0);
        m.SetFloat("_Glossiness", 0f);
        m.SetFloat("_Metallic", 0f);
        m.EnableKeyword("_ALPHABLEND_ON");
        m.renderQueue = 3000;
        EditorUtility.SetDirty(m);
        AssetDatabase.SaveAssets();
        return m;
    }

    // ------------------------------------------------------------------ textures and materials

    private static bool IsMesh(string materialName)
    {
        return materialName.EndsWith("Mesh");
    }

    private static void ConfigureTexture(string path)
    {
        TextureImporter importer = (TextureImporter)AssetImporter.GetAtPath(path);
        bool normal = path.EndsWith("_Normal.png");
        bool linear = path.EndsWith("_RMOM.png");
        string material = Path.GetFileNameWithoutExtension(path);
        material = material.Substring(0, material.LastIndexOf('_'));
        bool cutout = IsMesh(material) && path.EndsWith("_Albedo.png");
        importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        importer.sRGBTexture = !(normal || linear);
        // Wire mesh keeps its albedo alpha for the cutout; the container's RMOM alpha is its paint (tint) mask
        importer.alphaSource = cutout || linear ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
        importer.alphaIsTransparency = false;
        importer.mipmapEnabled = true;
        // Thin wire would fade out of the cutout at a distance without this
        importer.mipMapsPreserveCoverage = cutout;
        importer.alphaTestReferenceValue = 0.3f;
        importer.wrapMode = IsMesh(material) ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
        importer.anisoLevel = 4;
        // One atlas is shared by every piece of a family, so it keeps the full 2048
        importer.maxTextureSize = linear || IsMesh(material) ? 1024 : 2048;
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
        // Not read by Standard (no detail keyword); the mod hands it to the game's shader as _RMOM
        material.SetTexture("_DetailMask", Tex("RMOM"));
        material.SetFloat("_Glossiness", 0.2f);
        if (IsMesh(name))
        {
            // Standard in Cutout mode; the mod carries the alpha test over to the game's shader (vanilla chain-link
            // cuts out at 0.3)
            material.SetFloat("_Mode", 1f);
            material.SetFloat("_Cutoff", 0.3f);
            material.SetOverrideTag("RenderType", "TransparentCutout");
            material.EnableKeyword("_ALPHATEST_ON");
            material.renderQueue = (int)RenderQueue.AlphaTest;
        }
        else
        {
            material.SetFloat("_Mode", 0f);
            material.SetOverrideTag("RenderType", "");
            material.renderQueue = -1;
        }
        EditorUtility.SetDirty(material);
        AssetDatabase.SaveAssets();
        return material;
    }
}
