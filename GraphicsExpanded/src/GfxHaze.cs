using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Distance haze (Haze.shader, GfxHaze.cginc): the further away something is, the more of the air's own color it
/// takes on, the way far hills fade towards the sky. A camera command buffer after the solid world and before
/// transparent objects lays it over everything but the sky, and the water shader hazes its reflections the same way.
///
/// Nothing within the first 150 m is touched, so what's around the player stays crisp. The color is the sky's hue
/// (blue by day, warm at the ends of it) at the brightness of the game's fog, greying towards the fog's own color
/// under cloud, rain and snow, so it follows the biome, weather, time of day and Blood Moon, with a warm glow looking
/// towards the sun. It thins with height above the ground around the player, and rain and snow thicken it. All of it
/// comes from what every client already has, so in multiplayer nothing is sent.
/// </summary>
public static class GfxHaze
{
    private const float ClearHaze = 0.0003f;    // per meter past the clear stretch, at the ground, at 100%: a kilometer away lets 77% through
    private const float ClearStretch = 150f;    // meters of untouched air around the player
    private const float ThinsOver = 250f;       // meters up for the haze to thin to a third
    private const float SunGlow = 0.6f;
    private const float SkyTint = 0.7f;         // how much of the sky's hue the air takes on a clear day

    private static Shader shader;
    private static Material material;

    private static Camera camera;
    private static CommandBuffer commands;
    private static bool hooked;

    private static float groundHeight;
    private static float nextGroundTime;
    private static float thickness;
    private static string state = "not started";

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("Haze") : null;
        if (shader != null && !shader.isSupported)
        {
            Log.Warning("[GraphicsExpanded] The haze shader isn't supported on this graphics card; distance haze is off");
            shader = null;
        }
        if (shader != null)
            material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        Shader.SetGlobalVector("_GfxHazeParams", Vector4.zero);
    }

    /// <summary>Called every frame from GfxApply.Update, before GfxWater.Update, which uses the same haze.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        float amount = GfxSettings.LookActive ? GfxSettings.DistanceHaze : 0f;
        if (player == null || playerCamera == null || amount <= 0f)
        {
            state = amount <= 0f ? "off" : "no world";
            Unhook();
            Shader.SetGlobalVector("_GfxHazeParams", Vector4.zero);
            return;
        }

        if (playerCamera != camera)
        {
            Unhook();
            camera = playerCamera;
        }
        if (!hooked)
        {
            if (commands == null)
            {
                commands = new CommandBuffer { name = "GraphicsExpanded distance haze" };
                commands.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
                commands.DrawProcedural(Matrix4x4.identity, material, 0, MeshTopology.Triangles, 3);
            }
            camera.AddCommandBuffer(CameraEvent.BeforeForwardAlpha, commands);
            Camera.onPreRender += OnPreRender;
            hooked = true;
        }

        SetAir(player, amount);
        state = string.Format("{0:0%}, a kilometer away lets {1:0%} through at the ground", amount, Mathf.Exp(-thickness * (1000f - ClearStretch)));
    }

    private static void Unhook()
    {
        if (!hooked)
            return;
        if (camera != null)
            camera.RemoveCommandBuffer(CameraEvent.BeforeForwardAlpha, commands);
        Camera.onPreRender -= OnPreRender;
        hooked = false;
    }

    /// <summary>The camera's matrices this frame, after anti-aliasing has jittered them, to rebuild positions from depth.</summary>
    private static void OnPreRender(Camera rendering)
    {
        if (rendering != camera)
            return;
        material.SetMatrix("_GfxInvProjection", rendering.projectionMatrix.inverse);
        material.SetMatrix("_GfxCameraToWorld", rendering.cameraToWorldMatrix);
        material.SetVector("_GfxFullSize", new Vector4(rendering.pixelWidth, rendering.pixelHeight, 1f / rendering.pixelWidth, 1f / rendering.pixelHeight));
    }

    private static void SetAir(EntityPlayerLocal player, float amount)
    {
        if (Time.unscaledTime >= nextGroundTime)
        {
            groundHeight = GfxAtmosphere.AverageGround(GameManager.Instance.World, player);
            nextGroundTime = Time.unscaledTime + 5f;
        }
        WeatherManager weather = WeatherManager.Instance;
        float rain = weather != null ? GfxMood.Fraction(weather.GetCurrentRainfallPercent()) : 0f;
        float snowfall = weather != null ? GfxMood.Fraction(weather.GetCurrentSnowfallPercent()) : 0f;
        float overcast = weather != null ? GfxMood.Fraction(weather.GetCurrentCloudThicknessPercent()) : 0f;
        thickness = ClearHaze * amount * (1f + rain + 0.5f * snowfall);

        Shader.SetGlobalVector("_GfxHazeParams", new Vector4(thickness, groundHeight - Origin.position.y, 1f / ThinsOver, 1f));
        // The air takes the sky's hue (blue by day, gold and pink at the ends of it) at the fog's brightness; under
        // cloud, rain or snow it greys back towards the fog's own color
        Color fog = RenderSettings.fogColor.linear;
        Color sky = SkyManager.GetSkyColor().linear;
        float skyBrightness = Luminance(sky);
        Color skyHue = skyBrightness > 1e-4f ? sky * (Luminance(fog) / skyBrightness) : fog;
        float clear = 1f - Mathf.Max(Mathf.Max(overcast, rain), snowfall);
        Color air = Color.Lerp(fog, skyHue, SkyTint * clear);
        Shader.SetGlobalVector("_GfxHazeColor", new Vector4(air.r, air.g, air.b, ClearStretch));
        Light sun = SkyManager.sunLight;
        Color glow = sun != null && sun.isActiveAndEnabled ? sun.color.linear * sun.intensity * SunGlow : Color.black;
        Shader.SetGlobalVector("_GfxHazeSunDir", sun != null ? -sun.transform.forward : Vector3.up);
        Shader.SetGlobalVector("_GfxHazeSunColor", new Vector4(glow.r, glow.g, glow.b, 0f));
    }

    private static float Luminance(Color color)
    {
        return color.r * 0.2126f + color.g * 0.7152f + color.b * 0.0722f;
    }

    public static string Status()
    {
        if (!Loaded)
            return "Distance haze is off: the shader didn't load (see the log).";
        return "Distance haze: " + state + ".";
    }
}
