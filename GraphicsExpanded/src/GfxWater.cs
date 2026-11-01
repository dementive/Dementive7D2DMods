using UnityEngine;

/// <summary>
/// Water (Water.shader): puts the mod's water shader on the game's two water materials, the one every chunk's water
/// mesh shares (MeshDescription layer 1) and the far, low-detail one the distant terrain draws its water with, and
/// gives the game's shaders back when it's off or the compare key is held. It keeps the materials' textures (the game's
/// water normal map makes the waves). The far water keeps the game's map of loaded chunks, so it still steps aside
/// where the near water is drawn, and draws in the same slot as the near water while it has the mod's shader. If the
/// game sets its own shader again (changing water quality in the video menu does), it's put back on the next frame.
///
/// Everything the shader needs comes from what every client already has, so in multiplayer each player sees it
/// locally and nothing is sent.
/// </summary>
public static class GfxWater
{
    private const float SkyRadiance = 0.15f;    // the game's sky color is several times brighter than the sky it draws

    /// <summary>One of the game's water materials while it has the mod's shader, and what to give back.</summary>
    private class Swap
    {
        public Material Material;
        public Shader Original;
        public int OriginalQueue;

        public void Apply(Material target, int queue, bool distant)
        {
            if (target != Material)
            {
                Restore();
                Material = target;
            }
            if (Material == null || Material.shader == shader)
                return;
            Original = Material.shader;
            OriginalQueue = Material.renderQueue;
            Material.shader = shader;
            Material.renderQueue = queue >= 0 ? queue : OriginalQueue;
            Material.SetFloat("_GfxDistant", distant ? 1f : 0f);
        }

        public void Restore()
        {
            if (Material != null && Original != null && Material.shader == shader)
            {
                Material.shader = Original;
                Material.renderQueue = OriginalQueue;
                Material.SetFloat("_GfxDistant", 0f);
            }
            Material = null;
            Original = null;
        }
    }

    private static Shader shader;
    private static readonly Swap near = new Swap();
    private static readonly Swap far = new Swap();
    private static float rain;

    /// <summary>gfxe water debug: red where screen-space reflections found something, green the reflection's share, blue the shore foam.</summary>
    public static bool Debug;
    private static string state = "not started";

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("Water") : null;
        if (shader != null && !shader.isSupported)
        {
            Log.Warning("[GraphicsExpanded] The water shader isn't supported on this graphics card; the game's water stays");
            shader = null;
        }
    }

    /// <summary>Called every frame from GfxApply.Update, after GfxHaze.Update, whose haze the water uses.</summary>
    public static void Update(EntityPlayerLocal player)
    {
        if (!Loaded)
            return;
        GfxWaterQuality quality = GfxSettings.LookActive ? GfxSettings.WaterQuality : GfxWaterQuality.Off;
        MeshDescription water = WaterMesh();
        Material nearMaterial = water != null && water.materials != null && water.materials.Length > 0 ? water.materials[0] : null;
        if (quality == GfxWaterQuality.Off || player == null || nearMaterial == null)
        {
            state = quality == GfxWaterQuality.Off ? "off, the game's own" : player == null ? "no world" : "no water material yet";
            near.Restore();
            far.Restore();
            return;
        }

        near.Apply(nearMaterial, -1, false);
        far.Apply(water.materialDistant, near.OriginalQueue, true);

        SetLight(quality);
        state = string.Format("{0}, in place of '{1}' near and '{2}' far, waves {3:0%}, rain rings {4:0%}, the game's reflection probe {5}",
            quality, near.Original != null ? near.Original.name : "?", far.Original != null ? far.Original.name : "none",
            GfxSettings.WaterWaves, rain, PlayerReflectionProbe.hasReflections ? "on" : "off");
    }

    /// <summary>The water layer of the chunk meshes, which holds both water materials.</summary>
    private static MeshDescription WaterMesh()
    {
        MeshDescription[] meshes = MeshDescription.meshes;
        return meshes != null && meshes.Length > MeshDescription.MESH_WATER ? meshes[MeshDescription.MESH_WATER] : null;
    }

    private static void SetLight(GfxWaterQuality quality)
    {
        WeatherManager weather = WeatherManager.Instance;
        float raining = weather != null ? GfxMood.Fraction(weather.GetCurrentRainfallPercent()) : 0f;
        rain = Mathf.MoveTowards(rain, raining, Time.deltaTime * 0.2f);
        Shader.SetGlobalFloat("_GfxWaterDebug", Debug ? 1f : 0f);
        Shader.SetGlobalVector("_GfxWater", new Vector4(GfxSettings.WaterWaves, rain,
            quality == GfxWaterQuality.High ? 1f : 0f, PlayerReflectionProbe.hasReflections ? 1f : 0f));
        Vector3 origin = Origin.position;
        Shader.SetGlobalVector("_GfxWaterOrigin", new Vector4(origin.x, origin.y, origin.z, 0f));

        // The sun by day, the moon by night: whichever is brighter
        Light sun = SkyManager.sunLight;
        Light moon = SkyManager.moonLight;
        float sunBrightness = sun != null && sun.isActiveAndEnabled ? sun.intensity : 0f;
        float moonBrightness = moon != null && moon.isActiveAndEnabled ? moon.intensity : 0f;
        Light light = moonBrightness > sunBrightness ? moon : sun;
        Vector3 toLight = light != null ? -light.transform.forward : Vector3.up;
        Color lightColor = light != null && light.isActiveAndEnabled ? light.color.linear * light.intensity : Color.black;
        Shader.SetGlobalVector("_GfxWaterLightDir", new Vector4(toLight.x, toLight.y, toLight.z, GfxMood.Outdoors));
        Shader.SetGlobalVector("_GfxWaterLight", new Vector4(lightColor.r, lightColor.g, lightColor.b, 0f));

        Color sky = SkyManager.GetSkyColor().linear * SkyRadiance;
        Color horizon = RenderSettings.fogColor.linear;
        Shader.SetGlobalVector("_GfxWaterSky", new Vector4(sky.r, sky.g, sky.b, 0f));
        Shader.SetGlobalVector("_GfxWaterHorizon", new Vector4(horizon.r, horizon.g, horizon.b, 0f));
    }

    public static string Status()
    {
        if (!Loaded)
            return "Water is the game's own: the shader didn't load (see the log).";
        return "Water: " + state + ".";
    }
}
