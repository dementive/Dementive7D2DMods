using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// How a zombie looks on a player's screen, drawn by an extra overlay material on its own mesh (so it works whatever
/// shader the zombie uses): weathering from where it walked (mud, dust, frost rime, soot, ash), how old it is, wet
/// in the rain, wounds where it was hit that move with the body, charring from fire, frost from cold, and blood dripping
/// from badly hurt zombies. Nothing here affects play.
/// </summary>
public class ZedLook : MonoBehaviour
{
    private struct Wound
    {
        public Transform Bone;
        public Vector3 Local;
        public float Radius;
        public float Kind;
    }

    private const int MaxWounds = 12;
    private const float FarAway = 80f;

    private static Material overlay;
    private static GameObject dripTemplate;
    private static bool loaded;

    private static readonly int BaseAlbedo = Shader.PropertyToID("_BaseAlbedo");
    private static readonly int HasBase = Shader.PropertyToID("_HasBase");
    private static readonly int GrimeId = Shader.PropertyToID("_Grime");
    private static readonly int GrimeColorId = Shader.PropertyToID("_GrimeColor");
    private static readonly int SettleId = Shader.PropertyToID("_Settle");
    private static readonly int SettleColorId = Shader.PropertyToID("_SettleColor");
    private static readonly int BleachId = Shader.PropertyToID("_Bleach");
    private static readonly int WetId = Shader.PropertyToID("_Wet");
    private static readonly int CharId = Shader.PropertyToID("_Char");
    private static readonly int FrostId = Shader.PropertyToID("_Frost");
    private static readonly int BloodId = Shader.PropertyToID("_Blood");
    private static readonly int WoundsId = Shader.PropertyToID("_Wounds");
    private static readonly int WoundCountId = Shader.PropertyToID("_WoundCount");
    private static readonly int SeedId = Shader.PropertyToID("_Seed");

    private EntityAlive zombie;
    private ZedProfile profile;
    private readonly List<SkinnedMeshRenderer> renderers = new List<SkinnedMeshRenderer>();
    private readonly List<Texture> albedos = new List<Texture>();
    private readonly List<int> overlayIndex = new List<int>();
    private MaterialPropertyBlock block;
    private readonly Dictionary<string, Transform> bones = new Dictionary<string, Transform>();
    private readonly List<Wound> wounds = new List<Wound>();
    private readonly Vector4[] woundArray = new Vector4[MaxWounds];
    private System.Random rng;

    private float grime, settle, bleach, blood, charBase, frostBase;
    private Color grimeColor, settleColor;
    private float wet, charAmount, frost;

    private GameObject drip;
    private float slowTimer, skyTimer, checkTimer;
    private bool openSky = true;

    public static void Attach(EntityAlive zombie, ZedProfile p)
    {
        if (!ZedSettings.Looks || zombie.GetComponent<ZedLook>() != null)
        {
            return;
        }
        LoadShared();
        if (overlay == null)
        {
            return;
        }
        zombie.gameObject.AddComponent<ZedLook>().Init(zombie, p);
    }

    /// <summary>The zombie's mutations changed (a champion room's promotion): redo its weathering and mutation looks.</summary>
    public static void Restyle(EntityAlive zombie, ZedProfile p)
    {
        ZedLook look = zombie != null ? zombie.GetComponent<ZedLook>() : null;
        if (look != null)
        {
            look.profile = p;
            look.charBase = look.frostBase = look.bleach = 0f;
            look.Weathering(p);
        }
    }

    public static void Damaged(EntityAlive zombie, DamageResponse dr)
    {
        ZedLook look = zombie != null ? zombie.GetComponent<ZedLook>() : null;
        if (look != null)
        {
            look.OnDamage(dr);
        }
    }

    private static void LoadShared()
    {
        if (loaded)
        {
            return;
        }
        loaded = true;
        overlay = ZedAssets.Get<Material>("ZombieOverlay");
        dripTemplate = ZedAssets.Get<GameObject>("BloodDrip");
    }

    private void Init(EntityAlive z, ZedProfile p)
    {
        zombie = z;
        profile = p;
        rng = new System.Random(p.Seed);
        block = new MaterialPropertyBlock();
        Transform model = z.emodel.GetModelTransform() ?? z.transform;
        foreach (Transform t in model.GetComponentsInChildren<Transform>(true))
        {
            if (!bones.ContainsKey(t.name))
            {
                bones[t.name] = t;
            }
        }
        Weathering(p);
        FindRenderers(model);
        Apply();
    }

    // ------------------------------------------------------------------ setup

    private void Weathering(ZedProfile p)
    {
        switch (p.Biome)
        {
            case ZedBiome.Desert:
                grimeColor = new Color(0.45f, 0.36f, 0.24f);
                grime = 0.2f;
                settleColor = new Color(0.66f, 0.56f, 0.4f);
                settle = 0.5f;
                bleach = 0.35f;
                break;
            case ZedBiome.Snow:
                grimeColor = new Color(0.22f, 0.2f, 0.18f);
                grime = 0.15f;
                settleColor = new Color(0.88f, 0.92f, 0.97f);
                settle = 0.5f;
                bleach = 0.1f;
                break;
            case ZedBiome.Burnt:
                grimeColor = new Color(0.06f, 0.05f, 0.045f);
                grime = 0.4f;
                settleColor = new Color(0.08f, 0.07f, 0.06f);
                settle = 0.4f;
                charBase = 0.1f;
                break;
            case ZedBiome.Wasteland:
                grimeColor = new Color(0.3f, 0.3f, 0.26f);
                grime = 0.35f;
                settleColor = new Color(0.45f, 0.45f, 0.43f);
                settle = 0.45f;
                bleach = 0.15f;
                break;
            default:
                grimeColor = new Color(0.24f, 0.19f, 0.12f);
                grime = 0.25f;
                settleColor = new Color(0.2f, 0.22f, 0.12f);
                settle = 0.15f;
                break;
        }
        grime += 0.3f * p.Age;
        grimeColor = Color.Lerp(grimeColor, new Color(0.22f, 0.24f, 0.16f), p.Age * 0.4f);
        blood = 0.4f * (1f - p.Age);

        // What mutations show on the skin (nothing that glows: glowing veins and embers looked bad at night)
        foreach (ZedMutation m in p.Mutations)
        {
            switch (m)
            {
                case ZedMutation.Smoldering:
                    charBase = 0.55f;
                    break;
                case ZedMutation.Frostbitten:
                    frostBase = 0.45f;
                    break;
                case ZedMutation.Regenerator:
                    bleach = Mathf.Max(bleach, 0.35f);
                    break;
                case ZedMutation.Stalker:
                    grime = 0.8f;
                    grimeColor = new Color(0.07f, 0.065f, 0.06f);
                    blood = 0f;
                    break;
            }
        }
        charAmount = charBase;
        frost = frostBase;
    }

    /// <summary>The zombie's skinned meshes that take the overlay: not the eyes, not hair or anything else with
    /// see-through parts (the overlay would cover the whole card), and not a mesh of several parts (an extra material
    /// draws only the last part, which may not be skin).</summary>
    private void FindRenderers(Transform model)
    {
        foreach (SkinnedMeshRenderer r in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            Material m = r.sharedMaterial;
            if (m == null || r.sharedMesh == null || r.sharedMesh.subMeshCount > 1
                || r.name.IndexOf("eye", System.StringComparison.OrdinalIgnoreCase) >= 0
                || m.renderQueue >= 2450 || m.IsKeywordEnabled("_ALPHATEST_ON") || m.IsKeywordEnabled("_ALPHABLEND_ON")
                || m.shader.name.IndexOf("Hair", System.StringComparison.OrdinalIgnoreCase) >= 0)
            {
                continue;
            }
            renderers.Add(r);
            albedos.Add(Tex(m, "_Albedo", "_MainTex"));
            AddOverlay(r);
            overlayIndex.Add(OverlayIndex(r));
        }
    }

    private static Texture Tex(Material m, string a, string b)
    {
        if (m.HasProperty(a) && m.GetTexture(a) != null)
        {
            return m.GetTexture(a);
        }
        return m.HasProperty(b) ? m.GetTexture(b) : null;
    }

    private static int OverlayIndex(Renderer r)
    {
        Material[] mats = r.sharedMaterials;
        for (int i = 0; i < mats.Length; i++)
        {
            if (mats[i] == overlay)
            {
                return i;
            }
        }
        return -1;
    }

    private static void AddOverlay(Renderer r)
    {
        if (OverlayIndex(r) >= 0)
        {
            return;
        }
        Material[] mats = r.sharedMaterials;
        Material[] more = new Material[mats.Length + 1];
        mats.CopyTo(more, 0);
        more[mats.Length] = overlay;
        r.sharedMaterials = more;
    }

    // ------------------------------------------------------------------ hits

    private void OnDamage(DamageResponse dr)
    {
        if (dr.Strength <= 0 || dr.Source == null)
        {
            return;
        }
        if (dr.Source.getEntityId() == zombie.world?.GetPrimaryPlayerId())
        {
            ZedClient.HitByMe(zombie.entityId);
        }
        switch (dr.Source.GetDamageType())
        {
            case EnumDamageTypes.Heat:
                charAmount = Mathf.Min(0.9f, charAmount + 0.05f + dr.Strength / 200f);
                break;
            case EnumDamageTypes.Cold:
                frost = Mathf.Min(0.8f, frost + 0.1f + dr.Strength / 100f);
                break;
            case EnumDamageTypes.Electrical:
                charAmount = Mathf.Min(Mathf.Max(charAmount, 0.4f), charAmount + 0.04f);
                break;
            case EnumDamageTypes.Piercing:
                AddWound(dr, 0.045f, 0f);
                break;
            case EnumDamageTypes.Slashing:
                AddWound(dr, 0.07f, 0f);
                break;
            case EnumDamageTypes.Bashing:
            case EnumDamageTypes.Crushing:
                AddWound(dr, 0.08f, 1f);
                break;
        }
        slowTimer = 1f;
    }

    private void AddWound(DamageResponse dr, float radius, float kind)
    {
        string name = dr.Source.getHitTransformName();
        Vector3 pos = dr.Source.getHitTransformPosition();
        Transform bone = null;
        Vector3 hit;
        if (!string.IsNullOrEmpty(name) && pos != Vector3.zero && bones.TryGetValue(name, out bone))
        {
            hit = pos - Origin.position;
        }
        else
        {
            bone = BoneFor(dr.HitBodyPart);
            if (bone == null)
            {
                return;
            }
            // No hit point (an explosion, a client that wasn't told): the side of the bone facing where it came from
            Vector3 dir = dr.Source.getDirection();
            hit = bone.position - (dir.sqrMagnitude > 0.001f ? dir.normalized * 0.12f : zombie.transform.forward * -0.12f);
        }
        Vector3 local = bone.InverseTransformPoint(hit);
        for (int i = 0; i < wounds.Count; i++)
        {
            Wound w = wounds[i];
            if (w.Bone == bone && w.Kind == kind && (w.Local - local).magnitude < w.Radius)
            {
                w.Radius = Mathf.Min(w.Radius * 1.15f, 0.12f);
                wounds[i] = w;
                return;
            }
        }
        if (wounds.Count >= MaxWounds)
        {
            wounds.RemoveAt(0);
        }
        wounds.Add(new Wound { Bone = bone, Local = local, Radius = radius * (0.85f + 0.3f * (float)rng.NextDouble()), Kind = kind });
    }

    private Transform BoneFor(EnumBodyPartHit part)
    {
        string name = "Spine2";
        if ((part & EnumBodyPartHit.Head) != 0)
        {
            name = "Head";
        }
        else if ((part & EnumBodyPartHit.LeftLowerArm) != 0)
        {
            name = "LeftForeArm";
        }
        else if ((part & EnumBodyPartHit.LeftUpperArm) != 0)
        {
            name = "LeftArm";
        }
        else if ((part & EnumBodyPartHit.RightLowerArm) != 0)
        {
            name = "RightForeArm";
        }
        else if ((part & EnumBodyPartHit.RightUpperArm) != 0)
        {
            name = "RightArm";
        }
        else if ((part & EnumBodyPartHit.LeftLowerLeg) != 0)
        {
            name = "LeftLeg";
        }
        else if ((part & EnumBodyPartHit.LeftUpperLeg) != 0)
        {
            name = "LeftUpLeg";
        }
        else if ((part & EnumBodyPartHit.RightLowerLeg) != 0)
        {
            name = "RightLeg";
        }
        else if ((part & EnumBodyPartHit.RightUpperLeg) != 0)
        {
            name = "RightUpLeg";
        }
        if (bones.TryGetValue(name, out Transform t))
        {
            return t;
        }
        return zombie.emodel.GetPelvisTransform();
    }

    // ------------------------------------------------------------------ every frame

    private void Update()
    {
        if (zombie == null)
        {
            return;
        }
        float dt = Time.deltaTime;
        Camera cam = Camera.main;
        float dist = cam != null ? Vector3.Distance(cam.transform.position, transform.position) : 0f;
        bool near = dist < FarAway;

        slowTimer += dt;
        if (slowTimer >= (near ? 0.25f : 2f))
        {
            Tick(slowTimer);
            slowTimer = 0f;
            Apply();
        }
        if (near)
        {
            // Wounds move with the body, so they're placed every frame; the rest changes slowly
            if (wounds.Count > 0 && ZedSettings.Wounds)
            {
                Apply();
            }
        }
    }

    /// <summary>The slow parts: fire, cold, rain, and blood dripping, a few times a second.</summary>
    private void Tick(float dt)
    {
        bool burning = !zombie.IsDead() && zombie.Buffs != null && zombie.Buffs.HasBuff("buffIsOnFire");
        if (burning)
        {
            charAmount = Mathf.Min(0.9f, charAmount + 0.08f * dt);
        }
        else
        {
            charAmount = Mathf.Max(charBase, charAmount - 0.003f * dt);
        }
        frost = Mathf.Max(frostBase, frost - 0.01f * dt);

        skyTimer -= dt;
        if (skyTimer <= 0f)
        {
            skyTimer = 4f + (float)rng.NextDouble();
            Vector3 top = zombie.getHeadPosition() + Vector3.up * 0.6f;
            openSky = !Voxel.Raycast(zombie.world, new Ray(top, Vector3.up), 40f, false, false);
        }
        float rain = WeatherManager.Instance != null ? WeatherManager.Instance.GetCurrentRainfallPercent() : 0f;
        float target = zombie.IsInWater() ? 1f : openSky ? rain : 0f;
        wet = target > wet ? Mathf.Min(target, wet + 0.05f * dt) : Mathf.Max(target, wet - 0.004f * dt);

        bool bleeding = ZedSettings.BloodDrips && !zombie.IsDead() && zombie.Health < zombie.GetMaxHealth() / 3;
        if (bleeding && drip == null && dripTemplate != null)
        {
            Transform at = wounds.Count > 0 ? wounds[wounds.Count - 1].Bone : bones.TryGetValue("Spine2", out Transform s) ? s : zombie.emodel.GetPelvisTransform();
            if (at != null)
            {
                drip = Instantiate(dripTemplate, at, false);
                drip.transform.localPosition = wounds.Count > 0 ? wounds[wounds.Count - 1].Local : Vector3.zero;
            }
        }
        else if (!bleeding && drip != null)
        {
            Destroy(drip);
            drip = null;
        }

        checkTimer -= dt;
        if (checkTimer <= 0f)
        {
            // The game sometimes rebuilds a renderer's materials (dismemberment, effects): put the overlay back
            checkTimer = 2f;
            for (int i = 0; i < renderers.Count; i++)
            {
                if (renderers[i] != null)
                {
                    AddOverlay(renderers[i]);
                    overlayIndex[i] = OverlayIndex(renderers[i]);
                }
            }
        }
    }

    private void Apply()
    {
        bool weathering = ZedSettings.Weathering;
        bool showWounds = ZedSettings.Wounds;
        int count = 0;
        if (showWounds)
        {
            for (int i = 0; i < wounds.Count; i++)
            {
                Wound w = wounds[i];
                if (w.Bone == null)
                {
                    continue;
                }
                Vector3 p = w.Bone.TransformPoint(w.Local);
                woundArray[count++] = new Vector4(p.x, p.y, p.z, w.Radius + w.Kind * 10f);
            }
        }
        for (int i = count; i < MaxWounds; i++)
        {
            woundArray[i] = Vector4.zero;
        }
        bool on = ZedSettings.Looks;
        for (int i = 0; i < renderers.Count; i++)
        {
            SkinnedMeshRenderer r = renderers[i];
            if (r == null || !r.isVisible)
            {
                continue;
            }
            int index = overlayIndex[i];
            if (index < 0)
            {
                continue;
            }
            block.Clear();
            if (albedos[i] != null)
            {
                block.SetTexture(BaseAlbedo, albedos[i]);
            }
            block.SetFloat(HasBase, albedos[i] != null ? 1f : 0f);
            block.SetFloat(GrimeId, on && weathering ? grime : 0f);
            block.SetColor(GrimeColorId, grimeColor);
            block.SetFloat(SettleId, on && weathering ? settle : 0f);
            block.SetColor(SettleColorId, settleColor);
            block.SetFloat(BleachId, on && weathering ? bleach : 0f);
            block.SetFloat(WetId, on ? wet : 0f);
            block.SetFloat(CharId, on ? charAmount : 0f);
            block.SetFloat(FrostId, on ? frost : 0f);
            block.SetFloat(BloodId, on && weathering ? blood : 0f);
            block.SetVectorArray(WoundsId, woundArray);
            block.SetFloat(WoundCountId, on ? count : 0);
            block.SetFloat(SeedId, (profile.Seed & 0x3ff) * 0.137f);
            r.SetPropertyBlock(block, index);
        }
    }

    private void OnDestroy()
    {
        if (drip != null)
        {
            Destroy(drip);
        }
    }
}
