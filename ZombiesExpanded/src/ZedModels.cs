using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The gear and growth models on a zombie, on each player's game: each model's parts bolted to their bones (sized
/// and placed to the zombie's own head and chest), gear knocked off as a tumbling prop when it breaks, the Volatile's
/// tank dropped or gone, the Brood's sac pulsing, and the one-off effects (bile cloud, gore burst).
/// </summary>
public class ZedModels : MonoBehaviour
{
    /// <summary>Joe's hit box radius per bone, the size the models are built for.</summary>
    private static readonly Dictionary<string, float> JoeRadius = new Dictionary<string, float>
    {
        { "Head", 0.1f }, { "Spine2", 0.158f }, { "LeftArm", 0.06f }, { "RightArm", 0.06f }, { "LeftForeArm", 0.05f },
        { "RightForeArm", 0.05f }, { "LeftUpLeg", 0.1f }, { "RightUpLeg", 0.1f }, { "LeftLeg", 0.05f }, { "RightLeg", 0.05f },
    };

    /// <summary>Joe's head and chest hit box centers: pieces there are moved to where this zombie's head or chest sits.</summary>
    private static readonly Dictionary<string, Vector3> JoeCenter = new Dictionary<string, Vector3>
    {
        { "Head", new Vector3(0f, 0.02f, 0f) }, { "Spine2", new Vector3(-0.00073f, 0.11f, -0.05f) },
    };

    /// <summary>The bone each limb bone points at, which gives the limb's length axis.</summary>
    private static readonly Dictionary<string, string> LimbChild = new Dictionary<string, string>
    {
        { "LeftArm", "LeftForeArm" }, { "LeftForeArm", "LeftHand" }, { "LeftUpLeg", "LeftLeg" }, { "LeftLeg", "LeftFoot" },
        { "RightArm", "RightForeArm" }, { "RightForeArm", "RightHand" }, { "RightUpLeg", "RightLeg" }, { "RightLeg", "RightFoot" },
    };

    private EntityAlive zombie;
    private readonly Dictionary<string, GameObject> parts = new Dictionary<string, GameObject>();
    private readonly Dictionary<string, Transform> bones = new Dictionary<string, Transform>();
    private Transform sac;
    private Vector3 sacScale;

    public static void Attach(EntityAlive zombie, ZedProfile p)
    {
        if (!ZedSettings.Looks || !p.Humanoid || (p.Mutations.Count == 0 && p.Gear.Count == 0 && p.Remnants.Count == 0))
        {
            return;
        }
        ZedModels m = zombie.GetComponent<ZedModels>();
        if (m == null)
        {
            m = zombie.gameObject.AddComponent<ZedModels>();
            m.zombie = zombie;
            Transform model = zombie.emodel.GetModelTransform() ?? zombie.transform;
            foreach (Transform t in model.GetComponentsInChildren<Transform>(true))
            {
                if (!m.bones.ContainsKey(t.name))
                {
                    m.bones[t.name] = t;
                }
            }
        }
        m.Sync(p);
    }

    public static void Refresh(EntityAlive zombie, ZedProfile p)
    {
        if (zombie == null || p == null)
        {
            return;
        }
        ZedModels m = zombie.GetComponent<ZedModels>();
        if (m != null)
        {
            m.Sync(p);
        }
        else
        {
            Attach(zombie, p);
        }
    }

    private void Sync(ZedProfile p)
    {
        foreach (ZedMutation mu in p.Mutations)
        {
            string model = ZedMutationInfo.All[mu].Model;
            if (model == null)
            {
                continue;
            }
            if (mu == ZedMutation.Snatcher)
            {
                // Its sack: flat, or stuffed with what it took
                Remove(model + (p.Carrying ? "/Spine2#Sack" : "/Spine2#SackFull"));
                Ensure(model, p.Carrying ? "Spine2#SackFull" : "Spine2#Sack");
                continue;
            }
            if (mu == ZedMutation.Volatile)
            {
                if (p.Tank == 0)
                {
                    Ensure(model, null);
                }
                else
                {
                    KnockOff(model + "/Spine2#Tank", p.Tank == 2);
                    if (p.Tank == 2)
                    {
                        Remove(model + "/Spine2#Straps");
                    }
                }
                continue;
            }
            Ensure(model, null, false, p.Seed);
        }
        foreach (ZedGearPiece g in p.Gear)
        {
            string model = ZedGearInfo.All[g.Kind].Model;
            if (g.Broken)
            {
                KnockOff(model + "/" + g.Part, false);
            }
            else
            {
                Ensure(model, g.Part);
            }
        }
        foreach (ZedRemnant r in p.Remnants)
        {
            if (!ZedRemnantInfo.All[r].Cut)
            {
                Ensure(ZedRemnantInfo.All[r].Model, null, true, p.Seed);
            }
        }
    }

    /// <summary>Puts a model's parts (or just `only`) on the zombie, once. With `acrossLimb`, parts on an arm or leg
    /// are sized to the limb's thickness only and keep their length (a cast stays the length of a shin). With a
    /// `seed`, the model's variant parts (named with "Var") are a selection that seed picks (see Variants).</summary>
    private void Ensure(string model, string only, bool acrossLimb = false, int? seed = null)
    {
        GameObject prefab = ZedAssets.Get<GameObject>(model);
        if (prefab == null)
        {
            return;
        }
        HashSet<string> shown = seed.HasValue ? Variants(prefab, model, seed.Value) : null;
        foreach (Transform piece in prefab.transform)
        {
            string key = model + "/" + piece.name;
            if ((only != null && piece.name != only) || parts.ContainsKey(key) || (shown != null && !shown.Contains(piece.name)))
            {
                continue;
            }
            string boneName = BoneOf(piece.name);
            if (!bones.TryGetValue(boneName, out Transform bone) || bone == null)
            {
                continue;
            }
            if (piece.name.EndsWith("Drag"))
            {
                // Dragged along the ground behind the zombie (the cinder block and its chain), not carried on the bone
                parts[key] = ZedDrag.Add(zombie, bone, piece);
                continue;
            }
            float s = Fit(boneName, out Vector3? center);
            if (acrossLimb && Mathf.Abs(s - 1f) > 0.01f && AlongLimb(bone, boneName, out int axis))
            {
                // A holder scaled across the limb only; the piece keeps its own pose inside it
                GameObject holder = new GameObject(piece.name);
                holder.transform.SetParent(bone, false);
                Vector3 across = Vector3.one * s;
                across[axis] = 1f;
                holder.transform.localScale = across;
                GameObject inner = Instantiate(piece.gameObject, holder.transform, false);
                inner.transform.localPosition = piece.localPosition;
                inner.transform.localRotation = piece.localRotation;
                inner.transform.localScale = piece.localScale;
                ZedGameShader.Apply(inner.transform);
                Swing(inner, piece.name);
                parts[key] = holder;
                continue;
            }
            GameObject p = Instantiate(piece.gameObject, bone, false);
            Vector3 pos = piece.localPosition * s;
            if (center.HasValue && JoeCenter.TryGetValue(boneName, out Vector3 jc))
            {
                pos = center.Value + (piece.localPosition - jc) * s;
            }
            p.transform.localPosition = pos + Settle(bone, boneName);
            p.transform.localRotation = piece.localRotation;
            p.transform.localScale = piece.localScale * s;
            ZedGameShader.Apply(p.transform);
            Swing(p, piece.name);
            parts[key] = p;
            if (piece.name.EndsWith("#Sac"))
            {
                sac = p.transform;
                sacScale = p.transform.localScale;
            }
        }
    }

    /// <summary>
    /// How much further a Neck or Jaw part sits on this zombie than on Joe, in the bone's own space. Those are sized by
    /// the head but weren't moved like head and chest parts, so on the fat cop (throat and chest 6 to 10 cm forward of
    /// Joe's, his face higher on the jaw) beads, a lei or a bow tie sank into him and a cigar stuck out of his jowl.
    /// Neck parts come forward with the front of the chest (never back, at most 12 cm); Jaw parts move with the
    /// head's hit box.
    /// </summary>
    private Vector3 Settle(Transform bone, string boneName)
    {
        if (boneName == "Neck" && bones.TryGetValue("Spine2", out Transform chest) && chest != null)
        {
            // The chest hit box's front along the model's forward (+Z on the standard skeleton), against Joe's. A fat
            // zombie's body runs well past its hit box (the fat cop's sphere is 3 cm out, his chest and throat 6 to
            // 10 cm), so for them it's at least 8 cm
            Collider c = chest.GetComponent<Collider>();
            float front = c is CapsuleCollider cc ? cc.center.z + cc.radius : c is SphereCollider sc ? sc.center.z + sc.radius : 0f;
            float forward = front > 0f ? front - (JoeCenter["Spine2"].z + JoeRadius["Spine2"]) : 0f;
            if (zombie != null && zombie.GetWalkType() == EntityAlive.cWalkTypeFat)
            {
                forward = Mathf.Max(forward, 0.08f);
            }
            forward = Mathf.Clamp(forward, 0f, 0.12f);
            return bone.InverseTransformVector(chest.TransformVector(new Vector3(0f, 0f, forward)));
        }
        if (boneName == "Jaw" && bones.TryGetValue("Head", out Transform head) && head != null)
        {
            Collider c = head.GetComponent<Collider>();
            Vector3? at = c is CapsuleCollider hc ? hc.center : c is SphereCollider hs ? hs.center : (Vector3?)null;
            if (at.HasValue)
            {
                return bone.InverseTransformVector(head.TransformVector(at.Value - JoeCenter["Head"]));
            }
        }
        return Vector3.zero;
    }

    /// <summary>A part built to hang ("...Swing", with its origin where it hangs from) swings as the zombie moves.</summary>
    private static void Swing(GameObject part, string name)
    {
        if (name.EndsWith("Swing") && ZedSettings.Swing)
        {
            part.AddComponent<ZedSwing>();
        }
    }

    /// <summary>Which of a model's parts this zombie shows: every part without "Var" in its name, and each "Var" part
    /// about half the time (at least one when the model is nothing but variants). Drawn from the zombie's seed and the
    /// model's name, so every player sees the same selection.</summary>
    private static HashSet<string> Variants(GameObject prefab, string model, int seed)
    {
        HashSet<string> shown = new HashSet<string>();
        List<string> variants = new List<string>();
        foreach (Transform piece in prefab.transform)
        {
            if (piece.name.IndexOf("Var", System.StringComparison.Ordinal) >= 0)
            {
                variants.Add(piece.name);
            }
            else
            {
                shown.Add(piece.name);
            }
        }
        if (variants.Count == 0)
        {
            return shown;
        }
        variants.Sort(System.StringComparer.Ordinal);
        System.Random rng = new System.Random(seed ^ Stable(model));
        foreach (string v in variants)
        {
            if (rng.NextDouble() < 0.5)
            {
                shown.Add(v);
            }
        }
        if (shown.Count == 0)
        {
            shown.Add(variants[rng.Next(variants.Count)]);
        }
        return shown;
    }

    /// <summary>A string hash that's the same on every machine (string.GetHashCode isn't guaranteed to be).</summary>
    private static int Stable(string s)
    {
        unchecked
        {
            int h = 23;
            foreach (char c in s)
            {
                h = h * 31 + c;
            }
            return h;
        }
    }

    /// <summary>Which of a limb bone's own axes runs along the limb (toward the next bone), if one clearly does.</summary>
    private bool AlongLimb(Transform bone, string boneName, out int axis)
    {
        axis = -1;
        if (!LimbChild.TryGetValue(boneName, out string childName) || !bones.TryGetValue(childName, out Transform child) || child == null)
        {
            return false;
        }
        Vector3 d = bone.InverseTransformDirection(child.position - bone.position);
        if (d.sqrMagnitude < 1e-6f)
        {
            return false;
        }
        d = d.normalized;
        float ax = Mathf.Abs(d.x), ay = Mathf.Abs(d.y), az = Mathf.Abs(d.z);
        axis = ax >= ay && ax >= az ? 0 : ay >= az ? 1 : 2;
        return Mathf.Max(ax, Mathf.Max(ay, az)) > 0.85f;
    }

    private static string BoneOf(string part)
    {
        int i = part.IndexOf('#');
        return i < 0 ? part : part.Substring(0, i);
    }

    /// <summary>How much to scale pieces on `bone` for this zombie (its hit box against Joe's), and where its head
    /// or chest hit box sits on the bone.</summary>
    private float Fit(string bone, out Vector3? center)
    {
        center = null;
        string fit = FitBone(bone);
        if (!JoeRadius.TryGetValue(fit, out float reference) || !bones.TryGetValue(fit, out Transform t) || t == null)
        {
            return 1f;
        }
        Collider c = t.GetComponent<Collider>();
        float r = c is CapsuleCollider cc ? cc.radius : c is SphereCollider sc ? sc.radius : 0f;
        if (r <= 0f)
        {
            return 1f;
        }
        if (fit == bone)
        {
            center = c is CapsuleCollider cc2 ? cc2.center : c is SphereCollider sc2 ? sc2.center : (Vector3?)null;
        }
        bool head = fit == "Head";
        return Mathf.Clamp(r / reference, head ? 0.85f : 0.8f, head ? 1.15f : 1.35f);
    }

    private static string FitBone(string bone)
    {
        switch (bone)
        {
            case "Neck":
            case "Jaw":
                return "Head";
            case "Hips":
            case "Spine":
            case "Spine1":
            case "Spine3":
            case "LeftShoulder":
            case "RightShoulder":
                return "Spine2";
            case "LeftHand":
                return "LeftForeArm";
            case "RightHand":
                return "RightForeArm";
        }
        if (bone.StartsWith("LeftHand"))
        {
            return "LeftForeArm";
        }
        if (bone.StartsWith("RightHand"))
        {
            return "RightForeArm";
        }
        return bone;
    }

    /// <summary>A part comes off: it tumbles away as a physics prop and is gone after 30 s (or just vanishes).</summary>
    private void KnockOff(string key, bool vanish)
    {
        if (!parts.TryGetValue(key, out GameObject go))
        {
            return;
        }
        parts.Remove(key);
        if (go == null)
        {
            return;
        }
        if (vanish)
        {
            Destroy(go);
            return;
        }
        go.transform.SetParent(null, true);
        BoxCollider box = go.AddComponent<BoxCollider>();
        box.size = Vector3.Max(box.size, Vector3.one * 0.05f);
        Rigidbody rb = go.AddComponent<Rigidbody>();
        rb.mass = 2f;
        Vector3 back = zombie != null ? -zombie.transform.forward : Vector3.back;
        rb.velocity = (back + Random.insideUnitSphere * 0.5f) * 2f + Vector3.up * 2.5f;
        rb.angularVelocity = Random.insideUnitSphere * 8f;
        Destroy(go, 30f);
    }

    private void Remove(string key)
    {
        if (parts.TryGetValue(key, out GameObject go))
        {
            parts.Remove(key);
            if (go != null)
            {
                Destroy(go);
            }
        }
    }

    private void Update()
    {
        if (sac != null && zombie != null && !zombie.IsDead())
        {
            sac.localScale = sacScale * (1f + 0.04f * Mathf.Sin(Time.time * 3.1f + zombie.entityId));
        }
    }

    /// <summary>A one-off effect from the bundle at a world position, gone after `life` seconds.</summary>
    public static void Effect(string name, Vector3 worldPos, float life)
    {
        GameObject template = ZedAssets.Get<GameObject>(name);
        if (template == null)
        {
            return;
        }
        GameObject fx = Instantiate(template, worldPos - Origin.position, Quaternion.identity);
        foreach (ParticleSystem ps in fx.GetComponentsInChildren<ParticleSystem>())
        {
            ps.Play();
        }
        Destroy(fx, life);
    }
}

/// <summary>Switches the models' materials to the game's own model shader (as the vanilla gear and traps use), so they
/// take the game's lighting. The bundle's materials are Standard ones carrying the shader's packed RMOM map in their
/// unused _DetailMask slot; converted materials are made once and shared.</summary>
public static class ZedGameShader
{
    private const string ShaderName = "Game/Entity Tint Mask";

    private static Shader shader;
    private static bool searched;
    private static readonly Dictionary<Material, Material> converted = new Dictionary<Material, Material>();

    public static void Apply(Transform root)
    {
        Shader game = Find();
        if (game == null)
        {
            return;
        }
        foreach (MeshRenderer r in root.GetComponentsInChildren<MeshRenderer>(true))
        {
            Material[] mats = r.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
            {
                Material src = mats[i];
                if (src == null || src.shader == game || !src.HasProperty("_DetailMask") || src.GetTexture("_DetailMask") == null)
                {
                    continue;
                }
                if (!converted.TryGetValue(src, out Material dst))
                {
                    dst = Convert(game, src);
                    converted[src] = dst;
                }
                mats[i] = dst;
            }
            r.sharedMaterials = mats;
        }
    }

    private static Material Convert(Shader game, Material src)
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
            m.SetColor("_EmissionColor", new Color(2f, 2f, 2f));
        }
        else
        {
            m.SetColor("_EmissionColor", Color.black);
        }
        return m;
    }

    private static Shader Find()
    {
        if (shader != null || searched)
        {
            return shader;
        }
        searched = true;
        shader = Shader.Find(ShaderName);
        if (shader == null)
        {
            foreach (Shader s in Resources.FindObjectsOfTypeAll<Shader>())
            {
                if (s.name == ShaderName)
                {
                    shader = s;
                    break;
                }
            }
        }
        if (shader == null)
        {
            Debug.LogWarning("[ZombiesExpanded] Shader " + ShaderName + " not found; gear keeps its Standard materials");
        }
        return shader;
    }
}
