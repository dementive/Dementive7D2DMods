using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Switches our block models to the game's own model shader (Game/Entity Tint Mask, the one every vanilla trap
/// uses) so they take the game's lighting the same way. The bundle's materials are Standard ones that carry the
/// shader's packed RMOM map (roughness, metallic, occlusion, mask) in their unused _DetailMask slot; converted
/// materials are made once and shared. Matches VanillaCompare.ToGame in the Unity project, which the build
/// preview uses. If the shader can't be found, the Standard materials stay.
/// </summary>
public static class GameShaderDEM
{
    private const string ShaderName = "Game/Entity Tint Mask";

    private static Shader shader;
    private static bool searched;
    private static bool warned;
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
            bool changed = false;
            for (int i = 0; i < mats.Length; i++)
            {
                Material src = mats[i];
                if (src == null || src.shader == game || src.GetTexture("_DetailMask") == null)
                {
                    continue;
                }
                if (!converted.TryGetValue(src, out Material dst))
                {
                    dst = Convert(game, src);
                    converted[src] = dst;
                }
                mats[i] = dst;
                changed = true;
            }
            if (changed)
            {
                r.sharedMaterials = mats;
            }
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
            // Lit per renderer by the trap's controller (power lamp)
            m.SetTexture("_Emissive", emission);
            m.EnableKeyword("_EMISSION");
        }
        m.SetColor("_EmissionColor", Color.black);
        return m;
    }

    private static Shader Find()
    {
        if (shader != null)
        {
            return shader;
        }
        shader = Shader.Find(ShaderName);
        if (shader == null && !searched)
        {
            searched = true;
            foreach (Shader s in Resources.FindObjectsOfTypeAll<Shader>())
            {
                if (s.name == ShaderName)
                {
                    shader = s;
                    break;
                }
            }
        }
        if (shader == null && !warned && !GameManager.IsDedicatedServer)
        {
            warned = true;
            Debug.LogWarning("[TrapsExpanded] Shader " + ShaderName + " not found; trap models keep their Standard materials");
        }
        return shader;
    }
}
