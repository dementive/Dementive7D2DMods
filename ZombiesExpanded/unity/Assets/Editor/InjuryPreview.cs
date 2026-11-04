using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// The old injuries on vanilla zombies posed from the game's own animations (walks, a fat walk, the Lurker's hunch, an
/// attack, the Stalker's crouch), each posed by the mod's own ZedInjuryPose loaded from the built ZombiesExpanded.dll,
/// to Build/injuries/&lt;Injury&gt;.png (from the front, and from the left side below it), with how far the limp arm
/// clears the body's hit boxes in the log. The limp arm wears the arm remnants (cast and chain, or nails).
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod InjuryPreview.Run (after src\build.bat).
/// </summary>
public static class InjuryPreview
{
    private static readonly string[] Bundles =
    {
        "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle",
        "zombies_assets_entities/zombies/common.bundle", "zombies_assets_entities/zombies/joe.bundle",
        "zombies_assets_entities/zombies/cop.bundle", "zombies_assets_entities/zombies/nurse.bundle",
        "animations_assets_animations/zombie.bundle",
    };

    private class Setup
    {
        public string Zombie;
        public string Clip;
        public float Time;
        public bool Hunched;
        public float Attacking;
        public float Abduct = 13f;
        public string Label;
    }

    private static readonly Setup[] Setups =
    {
        new Setup { Zombie = "zjoe.prefab", Clip = "walkForwardA", Time = 0.15f, Label = "Joe walk 1" },
        new Setup { Zombie = "zjoe.prefab", Clip = "walkForwardA", Time = 0.65f, Label = "Joe walk 2" },
        new Setup { Zombie = "zcop.prefab", Clip = "walkForwardFat", Time = 0.3f, Abduct = 17f, Label = "Cop fat walk" },
        new Setup { Zombie = "znurse.prefab", Clip = "walkForwardB", Time = 0.4f, Label = "Nurse walk" },
        new Setup { Zombie = "zjoe.prefab", Clip = "walkForwardC", Time = 0.3f, Hunched = true, Label = "Joe hunched" },
        new Setup { Zombie = "zjoe.prefab", Clip = "meleeForwardA", Time = 0.45f, Attacking = 1f, Label = "Joe attack" },
        new Setup { Zombie = "zjoe.prefab", Clip = "crouchWalkForward", Time = 0.3f, Label = "Joe crouch" },
    };

    public static void Run()
    {
        string here = Directory.GetCurrentDirectory();
        string game = Path.GetFullPath(Path.Combine(here, "../../../.."));
        string bundleRoot = Path.Combine(game, "Data/Addressables/Standalone");
        string output = Path.Combine(here, "Build/injuries");
        Directory.CreateDirectory(output);
        StringBuilder log = new StringBuilder();
        // The mod's own code, loaded from bytes so the DLL isn't locked
        Assembly mod = Assembly.Load(File.ReadAllBytes(Path.GetFullPath(Path.Combine(here, "../ZombiesExpanded.dll"))));
        System.Type poseType = mod.GetType("ZedInjuryPose", true);
        System.Type injuryType = mod.GetType("ZedInjury", true);
        MethodInfo create = poseType.GetMethod("Create");
        MethodInfo apply = poseType.GetMethod("Apply");
        List<AssetBundle> loaded = Bundles.Select(b => AssetBundle.LoadFromFile(Path.Combine(bundleRoot, b))).Where(b => b != null).ToList();
        try
        {
            Shader gameShader = loaded.SelectMany(b => b.LoadAllAssets<Shader>()).FirstOrDefault(s => s.name == "Game/Entity Tint Mask");
            Dictionary<string, AnimationClip> clips = new Dictionary<string, AnimationClip>();
            foreach (AssetBundle b in loaded)
            {
                foreach (string path in b.GetAllAssetNames())
                {
                    string name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
                    if ((Setups.Any(s => s.Clip.ToLowerInvariant() == name) || name == "runforwarda") && !clips.ContainsKey(name))
                    {
                        Object[] all = b.LoadAssetWithSubAssets(path);
                        log.AppendLine("[injury] " + path + ": " + string.Join(", ", all.Select(o => o.GetType().Name + " " + o.name)));
                        AnimationClip clip = all.OfType<AnimationClip>().FirstOrDefault(c => !c.name.StartsWith("__preview__"));
                        if (clip != null)
                        {
                            clips[name] = clip;
                        }
                    }
                }
            }
            log.AppendLine("[injury] clips: " + string.Join(", ", clips.Select(kv => kv.Key + " " + kv.Value.length.ToString("F2") + "s")));
            Sweep(loaded, clips, create, apply, injuryType, log);
            string[] injuries = { "None", "LimpArm", "DraggedFoot", "LolledHead", "TwistedBack" };
            bool[] lefts = { true, true, true, false, true };
            for (int k = 0; k < injuries.Length; k++)
            {
                Texture2D sheet = new Texture2D(2800, 2200, TextureFormat.RGB24, false) { hideFlags = HideFlags.HideAndDontSave };
                for (int view = 0; view < 2; view++)
                {
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    for (int i = 0; i < Setups.Length; i++)
                    {
                        Setup s = Setups[i];
                        GameObject z = Object.Instantiate(LoadVanilla(loaded, s.Zombie));
                        z.transform.position = new Vector3((i - (Setups.Length - 1) / 2f) * 1.1f, 0f, 0f);
                        z.transform.rotation = Quaternion.Euler(0f, view == 0 ? 165f : 270f, 0f);
                        if (clips.TryGetValue(s.Clip.ToLowerInvariant(), out AnimationClip clip))
                        {
                            // An attack at the moment its left arm swings highest
                            Sample(z, clip, s.Attacking > 0f ? Highest(z, clip, "LeftArm", "LeftForeArm") : s.Time * clip.length);
                        }
                        else
                        {
                            log.AppendLine("[injury] missing clip " + s.Clip);
                        }
                        if (s.Hunched)
                        {
                            // ZedBodyRig's hunched body, as the Lurker has
                            Bone(z, "Spine3").localRotation *= Quaternion.Euler(18f, 0f, 0f);
                            Bone(z, "Neck").localRotation *= Quaternion.Euler(-14f, 0f, 0f);
                        }
                        float abduct = s.Abduct;
                        if (injuries[k] == "LimpArm")
                        {
                            // Something on the arm: 3 degrees further out, as in game
                            abduct += 3f;
                            foreach (string remnant in i % 2 == 0 ? new[] { "ArmCast", "PadlockChain" } : new[] { "Nails" })
                            {
                                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(ZombiesModels.Root + "/" + remnant + "/" + remnant + ".prefab");
                                if (prefab == null)
                                {
                                    continue;
                                }
                                foreach (GameObject p in ZombiesModels.Attach(prefab, z.transform))
                                {
                                    if (gameShader != null)
                                    {
                                        foreach (MeshRenderer r in p.GetComponentsInChildren<MeshRenderer>())
                                        {
                                            r.sharedMaterials = r.sharedMaterials.Select(m => ZombiesModels.ToGame(gameShader, m)).ToArray();
                                        }
                                    }
                                }
                            }
                        }
                        if (injuries[k] != "None")
                        {
                            string before = view == 0 ? Measure(z, injuries[k], lefts[k]) : null;
                            object pose = create.Invoke(null, new object[] { z.transform, System.Enum.Parse(injuryType, injuries[k]), lefts[k], 0x00808000, abduct });
                            if (pose == null)
                            {
                                log.AppendLine("[injury] " + injuries[k] + " " + s.Label + ": no pose (missing bones)");
                            }
                            else
                            {
                                apply.Invoke(pose, new object[] { 1f, s.Attacking, 0f });
                                if (view == 0)
                                {
                                    log.AppendLine("[injury] " + injuries[k] + " " + s.Label + ": before " + before + " | after " + Measure(z, injuries[k], lefts[k]));
                                }
                            }
                        }
                    }
                    Texture2D shot = Shot(view);
                    sheet.SetPixels(0, (1 - view) * 1100, 2800, 1100, shot.GetPixels());
                }
                sheet.Apply();
                File.WriteAllBytes(Path.Combine(output, injuries[k] + ".png"), sheet.EncodeToPNG());
            }
        }
        finally
        {
            if (AnimationMode.InAnimationMode())
            {
                AnimationMode.StopAnimationMode();
            }
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
            File.WriteAllText(Path.Combine(output, "injuries.txt"), log.ToString());
            Debug.Log(log.ToString());
        }
    }

    /// <summary>Poses the zombie as the clip has it at `time`: sampled in animation mode, kept, and animation mode
    /// left again (the next sampling would put this zombie back otherwise).</summary>
    private static void Sample(GameObject z, AnimationClip clip, float time)
    {
        Animator anim = z.GetComponentInChildren<Animator>();
        // Where it stands (the clip moves the animator's own transform to its root motion)
        Vector3 rootPosition = anim.transform.localPosition;
        Quaternion rootRotation = anim.transform.localRotation;
        Vector3 zPosition = z.transform.position;
        Quaternion zRotation = z.transform.rotation;
        AnimationMode.StartAnimationMode();
        AnimationMode.BeginSampling();
        AnimationMode.SampleAnimationClip(anim.gameObject, clip, time);
        AnimationMode.EndSampling();
        Transform[] all = z.GetComponentsInChildren<Transform>(true);
        Vector3[] positions = all.Select(t => t.localPosition).ToArray();
        Quaternion[] rotations = all.Select(t => t.localRotation).ToArray();
        AnimationMode.StopAnimationMode();
        for (int i = 0; i < all.Length; i++)
        {
            all[i].localPosition = positions[i];
            all[i].localRotation = rotations[i];
        }
        z.transform.SetPositionAndRotation(zPosition, zRotation);
        anim.transform.localPosition = rootPosition;
        anim.transform.localRotation = rootRotation;
    }

    /// <summary>The dragged foot through whole cycles of walks, a run and the crouch on Joe: how its knee bend and its
    /// ankle's height change at 24 points in each, and whether the foot ever ends up higher than the walk had it.</summary>
    private static void Sweep(List<AssetBundle> loaded, Dictionary<string, AnimationClip> clips, MethodInfo create, MethodInfo apply,
        System.Type injuryType, StringBuilder log)
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        GameObject z = Object.Instantiate(LoadVanilla(loaded, "zjoe.prefab"));
        foreach (string name in new[] { "walkforwarda", "walkforwardb", "walkforwardfat", "runforwarda", "crouchwalkforward" })
        {
            if (!clips.TryGetValue(name, out AnimationClip clip))
            {
                continue;
            }
            float rise = 0f, lowest = 1f, bendBefore = 0f, bendAfter = 0f, maxBendCut = 0f;
            for (int i = 0; i < 24; i++)
            {
                Sample(z, clip, clip.length * i / 24f);
                Vector3 hip = Bone(z, "LeftUpLeg").position, knee = Bone(z, "LeftLeg").position, ankle = Bone(z, "LeftFoot").position;
                float before = ankle.y, bend = Vector3.Angle(knee - hip, ankle - knee);
                object pose = create.Invoke(null, new object[] { z.transform, System.Enum.Parse(injuryType, "DraggedFoot"), true, 0x00808000, 13f });
                apply.Invoke(pose, new object[] { 1f, 0f, 0f });
                hip = Bone(z, "LeftUpLeg").position;
                knee = Bone(z, "LeftLeg").position;
                ankle = Bone(z, "LeftFoot").position;
                float after = Vector3.Angle(knee - hip, ankle - knee);
                rise = Mathf.Max(rise, ankle.y - before);
                lowest = Mathf.Min(lowest, ankle.y);
                bendBefore += bend / 24f;
                bendAfter += after / 24f;
                maxBendCut = Mathf.Max(maxBendCut, bend - after);
            }
            log.AppendLine("[injury] sweep DraggedFoot " + name + ": knee bend " + bendBefore.ToString("F0") + " -> " + bendAfter.ToString("F0")
                + " deg on average (at most " + maxBendCut.ToString("F0") + " less), ankle rises at most " + (rise * 100f).ToString("F1")
                + " cm (hip turn), lowest ankle " + (lowest * 100f).ToString("F1") + " cm");
        }
    }

    /// <summary>When in the clip the arm is raised highest.</summary>
    private static float Highest(GameObject z, AnimationClip clip, string arm, string foreArm)
    {
        float best = 0f, bestAngle = -1f;
        for (int i = 0; i < 24; i++)
        {
            float t = clip.length * i / 24f;
            Sample(z, clip, t);
            float angle = Vector3.Angle(Bone(z, foreArm).position - Bone(z, arm).position, Vector3.down);
            if (angle > bestAngle)
            {
                bestAngle = angle;
                best = t;
            }
        }
        return best;
    }

    /// <summary>The numbers that show the injury: the limp arm's angle from straight down and how far it clears the
    /// body's hit boxes; the dragged leg's knee bend and ankle height; the head's or back's tilt from the hips' up.</summary>
    private static string Measure(GameObject z, string injury, bool left)
    {
        string near = left ? "Left" : "Right";
        switch (injury)
        {
            case "LimpArm":
            {
                Vector3 shoulder = Bone(z, near + "Arm").position, elbow = Bone(z, near + "ForeArm").position, wrist = Bone(z, near + "Hand").position;
                Physics.SyncTransforms();
                float clear = float.MaxValue;
                foreach (Collider c in z.GetComponentsInChildren<Collider>())
                {
                    string n = c.transform.name;
                    if (n.Contains("Arm") || n.Contains("Hand") || n.Contains("Shoulder") || n == "Head")
                    {
                        continue;
                    }
                    // From the lower upper arm (the shoulder always meets the body) down to the wrist
                    for (int i = 3; i <= 8; i++)
                    {
                        Vector3 point = i <= 4 ? Vector3.Lerp(shoulder, elbow, i / 4f) : Vector3.Lerp(elbow, wrist, (i - 4) / 4f);
                        Vector3 closest = c.ClosestPoint(point);
                        float d = (closest - point).magnitude;
                        if (d < 1e-5f)
                        {
                            d = -0.01f;
                        }
                        clear = Mathf.Min(clear, d);
                    }
                }
                return "upper arm " + Vector3.Angle(elbow - shoulder, Vector3.down).ToString("F0") + " deg off down, forearm "
                    + Vector3.Angle(wrist - elbow, Vector3.down).ToString("F0") + ", elbow bend " + Vector3.Angle(elbow - shoulder, wrist - elbow).ToString("F0")
                    + ", elbow to wrist clears torso/legs by " + (clear * 100f).ToString("F1") + " cm";
            }
            case "DraggedFoot":
            {
                Vector3 hip = Bone(z, near + "UpLeg").position, knee = Bone(z, near + "Leg").position, ankle = Bone(z, near + "Foot").position;
                Vector3 toe = Bone(z, near + "ToeBase").position;
                Vector3 fwd = z.transform.forward;
                Vector3 toes = Vector3.ProjectOnPlane(toe - ankle, Vector3.up);
                float turn = Vector3.SignedAngle(Vector3.ProjectOnPlane(fwd, Vector3.up), toes, Vector3.up);
                Vector3 side = z.transform.right;
                float thighPitch = Vector3.SignedAngle(Vector3.down, Vector3.ProjectOnPlane(knee - hip, side), side);
                float shinPitch = Vector3.SignedAngle(Vector3.down, Vector3.ProjectOnPlane(ankle - knee, side), side);
                return "thigh " + thighPitch.ToString("F0") + ", shin " + shinPitch.ToString("F0") + " deg off down (+ back), knee bend " + Vector3.Angle(knee - hip, ankle - knee).ToString("F0") + " deg, ankle " + (ankle.y * 100f).ToString("F1")
                    + " cm up, toe " + (toe.y * 100f).ToString("F1") + " cm up, toes turned " + turn.ToString("F0") + " deg (+ right)";
            }
            default:
            {
                Transform hips = Bone(z, "Hips");
                Transform top = injury == "LolledHead" ? Bone(z, "Head") : Bone(z, "Neck");
                Vector3 up = top.TransformDirection(Vector3.up);
                Vector3 r = z.transform.right, f = z.transform.forward;
                return "side tilt " + Vector3.SignedAngle(Vector3.ProjectOnPlane(Vector3.up, f), Vector3.ProjectOnPlane(up, f), f).ToString("F0")
                    + " deg, forward " + Vector3.SignedAngle(Vector3.ProjectOnPlane(Vector3.up, r), Vector3.ProjectOnPlane(up, r), r).ToString("F0")
                    + " deg, chest yaw " + Vector3.SignedAngle(Vector3.ProjectOnPlane(hips.TransformDirection(Vector3.forward), Vector3.up),
                        Vector3.ProjectOnPlane(Bone(z, "Spine3").TransformDirection(Vector3.forward), Vector3.up), Vector3.up).ToString("F0") + " deg";
            }
        }
    }

    private static Transform Bone(GameObject z, string name) => z.GetComponentsInChildren<Transform>().First(t => t.name == name);

    private static GameObject LoadVanilla(List<AssetBundle> loaded, string name)
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

    private static Texture2D Shot(int view)
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
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.transform.localScale = new Vector3(3f, 1f, 1f);
        const int width = 2800, height = 1100;
        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.5f, 0.56f, 0.66f);
        camera.fieldOfView = 24f;
        camera.transform.position = new Vector3(0f, 1.1f, -8.6f);
        camera.transform.LookAt(new Vector3(0f, 0.9f, 0f));
        RenderTexture target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        camera.targetTexture = target;
        camera.Render();
        RenderTexture.active = target;
        Texture2D read = new Texture2D(width, height, TextureFormat.RGB24, false);
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        RenderTexture.active = null;
        return read;
    }
}
