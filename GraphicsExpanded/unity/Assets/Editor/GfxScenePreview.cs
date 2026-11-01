using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Renders the water and distance haze shaders outside the game, in a small made-up scene: a lake with a sloping
/// shore, pillars along the far bank to reflect, and hills further off for the haze. Writes Build/scene-preview.png:
/// rows are views (across the lake, looking down into the shallows), columns are the effects off, water only, water
/// with haze, and the water's debug view (red: screen-space reflections found something, green: the reflection's share,
/// blue: shore foam). Run from preview-scene.bat (batch mode with graphics: it needs the GPU).
///
/// The light and exposure are the game's measured clear-afternoon values (as GfxCloudPreview's); the water's and
/// haze's inputs mirror GfxWater.SetLight and GfxHaze.SetAir.
/// </summary>
public static class GfxScenePreview
{
    private const int Width = 640;
    private const int Height = 360;
    private const float Exposure = 1.85f;
    private static readonly Color SunLight = new Color(0.884f, 0.739f, 0.6f);
    private static readonly Color FogColor = new Color(0.32f, 0.36f, 0.42f);   // gamma, as RenderSettings holds it

    public static void Render()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        Shader waterShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/GraphicsExpanded/Water.shader");
        Shader hazeShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/GraphicsExpanded/Haze.shader");

        // Light, sky and fog
        Light sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = SunLight;
        sun.intensity = 1f;
        sun.transform.rotation = Quaternion.Euler(28f, 160f, 0f);   // ahead and to the right, for a glint
        RenderSettings.sun = sun;
        RenderSettings.skybox = new Material(Shader.Find("Skybox/Procedural"));
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.35f, 0.42f, 0.55f);
        RenderSettings.ambientEquatorColor = new Color(0.3f, 0.32f, 0.33f);
        RenderSettings.ambientGroundColor = new Color(0.15f, 0.13f, 0.1f);
        RenderSettings.fog = true;
        RenderSettings.fogMode = FogMode.Exponential;
        RenderSettings.fogDensity = 0.0006f;
        RenderSettings.fogColor = FogColor;

        // A lake bed sloping up to the near shore, a far bank with pillars, and hills behind
        Material sand = Solid(new Color(0.45f, 0.4f, 0.3f));
        Material grass = Solid(new Color(0.18f, 0.28f, 0.1f));
        Material stone = Solid(new Color(0.5f, 0.48f, 0.45f));
        // The shore slopes from just above the water at z -5 to 4.5 m deep at z 40; the bed is flat past that
        Block("Lake bed", new Vector3(0f, -6.5f, 120f), new Vector3(400f, 1f, 200f), Quaternion.identity, sand);
        Block("Near shore", new Vector3(0f, -2.75f, 17.5f), new Vector3(200f, 2f, 120f), Quaternion.Euler(5.7f, 0f, 0f), sand);
        Block("Far bank", new Vector3(0f, 0f, 80f), new Vector3(200f, 6f, 20f), Quaternion.identity, grass);
        for (int k = -4; k <= 4; k++)
            Block("Pillar", new Vector3(k * 9f, 8f, 74f), new Vector3(2f, 10f, 2f), Quaternion.identity, stone);
        for (int k = -3; k <= 3; k++)
            Block("Hill", new Vector3(k * 500f, 40f, 1800f + (k & 1) * 600f), new Vector3(380f, 300f, 300f), Quaternion.Euler(0f, 30f * k, 0f), grass);

        // The water: a plain quad at height 0 with the mod's shader and a made-up wave normal map
        GameObject water = GameObject.CreatePrimitive(PrimitiveType.Quad);
        Object.DestroyImmediate(water.GetComponent<Collider>());
        water.transform.position = new Vector3(0f, 0f, 60f);
        water.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
        water.transform.localScale = new Vector3(400f, 400f, 1f);
        Material waterMaterial = new Material(waterShader);
        waterMaterial.SetTexture("_BumpMap", Waves());
        Renderer waterRenderer = water.GetComponent<Renderer>();
        waterRenderer.sharedMaterial = waterMaterial;

        Camera camera = new GameObject("Camera").AddComponent<Camera>();
        camera.renderingPath = RenderingPath.DeferredShading;
        camera.allowHDR = true;
        camera.depthTextureMode = DepthTextureMode.Depth;
        camera.nearClipPlane = 0.1f;
        camera.farClipPlane = 2800f;
        camera.fieldOfView = 60f;
        RenderTexture target = new RenderTexture(Width, Height, 24, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear);
        target.Create();
        camera.targetTexture = target;

        Material hazeMaterial = new Material(hazeShader);
        CommandBuffer haze = new CommandBuffer { name = "haze" };
        haze.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
        haze.DrawProcedural(Matrix4x4.identity, hazeMaterial, 0, MeshTopology.Triangles, 3);
        camera.AddCommandBuffer(CameraEvent.BeforeForwardAlpha, haze);

        Vector3[] positions = { new Vector3(0f, 1.8f, -6f), new Vector3(0f, 5f, -8f) };
        Quaternion[] rotations = { Quaternion.Euler(3f, 0f, 0f), Quaternion.Euler(25f, 0f, 0f) };
        Texture2D read = new Texture2D(Width, Height, TextureFormat.RGBAFloat, false, true);
        Texture2D sheet = new Texture2D(Width * 4, Height * positions.Length, TextureFormat.RGB24, false);
        for (int row = 0; row < positions.Length; row++)
        {
            camera.transform.SetPositionAndRotation(positions[row], rotations[row]);
            for (int column = 0; column < 4; column++)
            {
                bool waterOn = column > 0;
                bool hazeOn = column == 2;
                Shader.SetGlobalFloat("_GfxWaterDebug", column == 3 ? 1f : 0f);
                waterRenderer.sharedMaterial = waterOn ? waterMaterial : Solid(new Color(0.1f, 0.2f, 0.25f), true);
                SetGlobals(sun, hazeOn);
                hazeMaterial.SetMatrix("_GfxInvProjection", camera.projectionMatrix.inverse);
                hazeMaterial.SetMatrix("_GfxCameraToWorld", camera.cameraToWorldMatrix);
                hazeMaterial.SetVector("_GfxFullSize", new Vector4(Width, Height, 1f / Width, 1f / Height));
                camera.Render();
                RenderTexture.active = target;
                read.ReadPixels(new Rect(0, 0, Width, Height), 0, 0, false);
                read.Apply(false);
                RenderTexture.active = null;
                Color[] pixels = read.GetPixels();
                int nans = 0;
                for (int y = 0; y < Height; y++)
                {
                    for (int x = 0; x < Width; x++)
                    {
                        Color c = pixels[y * Width + x];
                        if (float.IsNaN(c.r) || float.IsNaN(c.g) || float.IsNaN(c.b))
                            nans++;
                        sheet.SetPixel(column * Width + x, (positions.Length - 1 - row) * Height + y,
                            column == 3 ? new Color(c.r, c.g, c.b) : new Color(Tonemap(c.r), Tonemap(c.g), Tonemap(c.b)));
                    }
                }
                Debug.Log(string.Format("[GfxScenePreview] view {0}, water {1}, haze {2}: {3} NaN pixels", row, waterOn, hazeOn, nans));
            }
        }

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        string path = Path.Combine(output, "scene-preview.png");
        File.WriteAllBytes(path, sheet.EncodeToPNG());
        Debug.Log("[GfxScenePreview] Wrote " + path);
    }

    /// <summary>GfxWater.SetLight's and GfxHaze.SetAir's globals for this little scene.</summary>
    private static void SetGlobals(Light sun, bool hazeOn)
    {
        Vector3 toSun = -sun.transform.forward;
        Color light = sun.color.linear * sun.intensity;
        Color horizon = FogColor.linear;
        Color sky = new Color(0.267f, 0.38f, 1f) * 0.15f;
        Shader.SetGlobalVector("_GfxWater", new Vector4(1f, 0f, 1f, 0f));
        Shader.SetGlobalVector("_GfxWaterOrigin", Vector4.zero);
        Shader.SetGlobalVector("_GfxWaterLightDir", new Vector4(toSun.x, toSun.y, toSun.z, 1f));
        Shader.SetGlobalVector("_GfxWaterLight", light);
        Shader.SetGlobalVector("_GfxWaterSky", sky);
        Shader.SetGlobalVector("_GfxWaterHorizon", horizon);
        // GfxHaze: the sky's hue at the fog's brightness on a clear day, nothing within 150 m
        Color skyColor = new Color(0.267f, 0.38f, 1f);
        float Luminance(Color c) => c.r * 0.2126f + c.g * 0.7152f + c.b * 0.0722f;
        Color air = Color.Lerp(horizon, skyColor * (Luminance(horizon) / Luminance(skyColor)), 0.7f);
        Shader.SetGlobalVector("_GfxHazeParams", hazeOn ? new Vector4(0.0003f, -2f, 1f / 250f, 1f) : Vector4.zero);
        Shader.SetGlobalVector("_GfxHazeColor", new Vector4(air.r, air.g, air.b, 150f));
        Shader.SetGlobalVector("_GfxHazeSunDir", toSun);
        Shader.SetGlobalVector("_GfxHazeSunColor", light * 0.6f);
    }

    private static Material Solid(Color color, bool see = false)
    {
        Material material = new Material(Shader.Find("Standard"));
        material.color = color;
        material.SetFloat("_Glossiness", see ? 0.9f : 0.1f);
        return material;
    }

    private static void Block(string name, Vector3 position, Vector3 size, Quaternion rotation, Material material)
    {
        GameObject block = GameObject.CreatePrimitive(PrimitiveType.Cube);
        block.name = name;
        block.transform.SetPositionAndRotation(position, rotation);
        block.transform.localScale = size;
        block.GetComponent<Renderer>().sharedMaterial = material;
    }

    /// <summary>A tiling normal map of soft random ripples, standing in for the game's water normals.</summary>
    private static Texture2D Waves()
    {
        const int size = 128;
        float[] height = new float[size * size];
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float u = x / (float)size * Mathf.PI * 2f;
                float v = y / (float)size * Mathf.PI * 2f;
                height[y * size + x] = Mathf.Sin(u * 3f + Mathf.Sin(v * 2f)) * 0.5f + Mathf.Sin(v * 5f + u) * 0.3f
                    + Mathf.Sin((u + v) * 7f) * 0.2f;
            }
        }
        Texture2D texture = new Texture2D(size, size, TextureFormat.RGBA32, true, true) { wrapMode = TextureWrapMode.Repeat };
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float dx = height[y * size + (x + 1) % size] - height[y * size + (x + size - 1) % size];
                float dy = height[((y + 1) % size) * size + x] - height[((y + size - 1) % size) * size + x];
                Vector3 n = new Vector3(-dx, -dy, 1f).normalized;
                texture.SetPixel(x, y, new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f, 1f));
            }
        }
        texture.Apply(true);
        return texture;
    }

    private static float Tonemap(float linear)
    {
        float x = Mathf.Max(float.IsNaN(linear) ? 0f : linear, 0f) * Exposure;
        float mapped = x * (2.51f * x + 0.03f) / (x * (2.43f * x + 0.59f) + 0.14f);
        return Mathf.Pow(Mathf.Clamp01(mapped), 1f / 2.2f);
    }
}
