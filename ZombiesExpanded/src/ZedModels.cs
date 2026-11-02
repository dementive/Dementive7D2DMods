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
            Ensure(model, null);
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
            Ensure(ZedRemnantInfo.All[r].Model, null);
        }
    }

    /// <summary>Puts a model's parts (or just `only`) on the zombie, once.</summary>
    private void Ensure(string model, string only)
    {
        GameObject prefab = ZedAssets.Get<GameObject>(model);
        if (prefab == null)
        {
            return;
        }
        foreach (Transform piece in prefab.transform)
        {
            string key = model + "/" + piece.name;
            if ((only != null && piece.name != only) || parts.ContainsKey(key))
            {
                continue;
            }
            string boneName = BoneOf(piece.name);
            if (!bones.TryGetValue(boneName, out Transform bone) || bone == null)
            {
                continue;
            }
            GameObject p = Instantiate(piece.gameObject, bone, false);
            float s = Fit(boneName, out Vector3? center);
            Vector3 pos = piece.localPosition * s;
            if (center.HasValue && JoeCenter.TryGetValue(boneName, out Vector3 jc))
            {
                pos = center.Value + (piece.localPosition - jc) * s;
            }
            p.transform.localPosition = pos;
            p.transform.localRotation = piece.localRotation;
            p.transform.localScale = piece.localScale * s;
            ZedGameShader.Apply(p.transform);
            parts[key] = p;
            if (piece.name.EndsWith("#Sac"))
            {
                sac = p.transform;
                sacScale = p.transform.localScale;
            }
        }
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
