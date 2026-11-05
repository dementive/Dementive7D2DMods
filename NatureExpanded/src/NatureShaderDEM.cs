using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Switches our plants to the game's own plant shader (Game/EntityTintMaskSSS, the one vanilla cotton and wild crops
/// use), so they sway in the wind and take the game's light the same way (and Torch's version of it, when Torch swaps
/// the shader). The bundle's materials are Standard ones carrying the plant shader's maps: albedo, normal, and RMOM
/// (roughness, metallic, occlusion, and a tint mask kept at 0) in the unused _DetailMask slot. Each converted material
/// is made once and shared by every plant of its kind, and made again when the shader goes (it's unloaded with the
/// world, and a second world loaded in the same session drew every reused plant magenta). Matches NatureBuilder.ToGame in the Unity project, which the
/// build previews use. If the shader can't be found yet, the plant keeps its Standard material and the next one tries
/// again (at most once a second).
/// </summary>
public static class NatureShaderDEM
{
    private const string ShaderName = "Game/EntityTintMaskSSS";

    private static Shader shader;
    private static float nextSearch;
    private static bool warned;
    private static readonly Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
    // Each converted material's bundle material, to convert again
    private static readonly Dictionary<Material, Material> sources = new Dictionary<Material, Material>();

    public static void Apply(Transform root)
    {
        Shader game = Find();
        if (game == null)
        {
            return;
        }
        foreach (MeshRenderer r in root.GetComponentsInChildren<MeshRenderer>(true))
        {
            // A tree's renderers carry several (bark, leaves)
            Material[] materials = r.sharedMaterials;
            bool changed = false;
            for (int i = 0; i < materials.Length; i++)
            {
                Material src = materials[i];
                if (src == null)
                {
                    continue;
                }
                // The game's plant shader goes with the world: leaving one unloads it, and every material converted
                // for that world loses its shader (drawn magenta) and must be made again from its bundle material,
                // whether it's still cached or a pooled plant still wears it
                if (sources.TryGetValue(src, out Material original))
                {
                    if (src.shader == game)
                    {
                        continue;
                    }
                    src = original;
                }
                else if (src.shader == game || src.GetTexture("_DetailMask") == null)
                {
                    continue;
                }
                if (!converted.TryGetValue(src, out Material dst) || dst == null || dst.shader != game)
                {
                    dst = Convert(game, src);
                    converted[src] = dst;
                    sources[dst] = src;
                }
                materials[i] = dst;
                changed = true;
            }
            if (changed)
            {
                r.sharedMaterials = materials;
            }
        }
    }

    private static Material Convert(Shader game, Material src)
    {
        Material m = new Material(game) { name = src.name + " (game)" };
        m.SetTexture("_Albedo", src.GetTexture("_MainTex"));
        m.SetTexture("_Normal", src.GetTexture("_BumpMap"));
        m.SetTexture("_RMOM", src.GetTexture("_DetailMask"));
        // Vanilla cotton's settings
        m.SetColor("_TintColor", new Color(1f, 1f, 1f, 0f));
        m.SetColor("_SSSColor", new Color(0f, 0f, 0f, 0f));
        m.SetFloat("_Cutoff", 0.5f);
        m.SetFloat("_Translucency", 2f);
        m.SetFloat("_TransNormalDistortion", 0.1f);
        m.SetFloat("_TransScattering", 2f);
        m.SetFloat("_TransDirect", 1f);
        m.SetFloat("_TransAmbient", 0.2f);
        m.SetFloat("_TransShadow", 1f);
        // Leaves and petals are built back to back (the shader lights a back face with its front's normal, so a single
        // sheet seen from behind is black): cull the back faces. Solid plants draw both sides of their few thin bits
        m.SetFloat("_Cull", Solid(src.name) ? 0f : 2f);
        m.SetFloat("_WindStartY", 0f);
        m.SetFloat("_WindStrength", Wind(src.name));
        m.renderQueue = 2450;
        return m;
    }

    /// <summary>Plants built as solid shapes (cactus bodies, mushroom caps, a log), not doubled into two-sided
    /// sheets. Matches NatureBuilder.Solid.</summary>
    public static bool Solid(string plant)
    {
        switch (plant)
        {
            case "BarrelCactus": case "MossyLog": case "Bolete": case "FlyAgaric": case "Morels":
                return true;
            default:
                return false;
        }
    }

    /// <summary>How hard the wind sways a plant: woody and fleshy ones barely, mushrooms, cacti and logs not at all.
    /// Matches NatureBuilder.Wind.</summary>
    public static float Wind(string plant)
    {
        switch (plant)
        {
            case "MossyLog": case "FlyAgaric": case "Bolete": case "Morels": case "BarrelCactus": case "PricklyPear":
                return 0f;
            case "Sagebrush": case "FrostedJuniper": case "AgaveBloom": case "DeadBrush": case "CharredShrub":
            case "WildRose": case "Elderberry": case "Sumac": case "Winterberry": case "Ocotillo":
                return 0.4f;
            default:
                return 1f;
        }
    }

    private static Shader Find()
    {
        if (shader != null)
        {
            return shader;
        }
        shader = Shader.Find(ShaderName);
        if (shader == null && Time.realtimeSinceStartup >= nextSearch)
        {
            nextSearch = Time.realtimeSinceStartup + 1f;
            foreach (Shader s in Resources.FindObjectsOfTypeAll<Shader>())
            {
                if (s.name == ShaderName)
                {
                    shader = s;
                    break;
                }
            }
            if (shader == null && !warned && !GameManager.IsDedicatedServer)
            {
                warned = true;
                Debug.LogWarning("[NatureExpanded] Shader " + ShaderName + " not found yet; plants keep their Standard materials until it is");
            }
        }
        return shader;
    }
}
