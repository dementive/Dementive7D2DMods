using System;
using System.IO;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Builds the photoscanned terrain textures into Build/terrain/graphicsexpanded_terrain.bundle, from Poly Haven sets
/// (CC0) that fetch-terrain-textures.ps1 downloads. Run from build-terrain.bat.
///
/// Each replaced ground layer becomes three 2048 square DXT5 textures with full mipmaps, packed the way the game's
/// terrain shader (MicroSplat) reads its three texture arrays, so GfxTerrainTextures can copy them straight into
/// arrays of the game's own format:
/// - L{n}_diff: color, with height in alpha (from the set's displacement);
/// - L{n}_nor: the normal's Y in green and X in alpha (the rest 0, as the game's are);
/// - L{n}_sao: smoothness (1 - roughness) in green and ambient occlusion in alpha.
/// Each set is matched to the game's layer it replaces (from the images gfxe terrain export saves): its average color,
/// its contrast at every scale from fine grain to the whole tile, how much its colors vary, the depth of its normals,
/// the spread of its height and its average smoothness and AO. So biomes keep their palette, the game's blending stays
/// balanced, the ground reads like the game's from near and far, and the photo brings its detail rather than its look.
/// </summary>
public static class GfxTerrainPack
{
    private const int Size = 2048;
    private const int Small = 512;              // the size gfxe terrain export saves at, which the statistics compare at
    private const float ColorMatch = 1f;        // how far each set's average color moves to the game layer's: all the way, so biomes keep their palette
    private const string Folder = "Assets/GraphicsExpanded/TerrainPack";
    private const string BundleName = "graphicsexpanded_terrain.bundle";

    /// <summary>
    /// The Poly Haven set for each of the game's 24 ground layers, or null to keep the game's. Keep in step with
    /// fetch-terrain-textures.ps1.
    /// </summary>
    public static readonly string[] Sets =
    {
        "snow_02",                  // 0 snow
        "rock_face_03",             // 1 dark cliff rock
        "forest_leaves_02",         // 2 green forest floor
        "rock_face_03",             // 3 red layered sandstone (the colors match the game's, so one rock can play several)
        "asphalt_02",               // 4 road asphalt
        "gravel_road",              // 5 gravel road
        null,                       // 6 plain grey, flat
        "red_laterite_soil_stones", // 7 desert dirt with weeds
        null,                       // 8 brick rubble
        "forest_ground_04",         // 9 grey-brown forest dirt
        "burned_ground_01",         // 10 burnt forest ground
        "sandy_gravel_02",          // 11 orange desert soil
        "tiger_rock",               // 12 red desert rock
        "brown_mud_rocks_01",       // 13 mossy brown ground
        "gravelly_sand",            // 14 light gravel
        "rock_ground",              // 15 charred black ground
        "road_damaged",             // 16 second asphalt
        "dry_ground_rocks",         // 17 dark rusty wasteland ground
        "tiger_rock",               // 18 icy snowy rock
        "tiger_rock",               // 19 dark rock, second
        "rock_06",                  // 20 red sandstone, second
        null,                       // 21 purple-orange
        "rocks_ground_06",          // 22 wasteland debris
        null,                       // 23 brick rubble, second
    };

    public static void Build()
    {
        string sources = Environment.GetEnvironmentVariable("GFX_TERRAIN_SOURCES");
        string export = Environment.GetEnvironmentVariable("GFX_TERRAIN_EXPORT");
        if (string.IsNullOrEmpty(sources) || !Directory.Exists(sources))
            throw new Exception("Set GFX_TERRAIN_SOURCES to the folder fetch-terrain-textures.ps1 downloaded into");
        if (string.IsNullOrEmpty(export) || !Directory.Exists(export))
            throw new Exception("Set GFX_TERRAIN_EXPORT to the folder gfxe terrain export saved into");

        if (!AssetDatabase.IsValidFolder(Folder))
            AssetDatabase.CreateFolder("Assets/GraphicsExpanded", "TerrainPack");
        var assets = new System.Collections.Generic.List<string>();
        for (int layer = 0; layer < Sets.Length; layer++)
        {
            string set = Sets[layer];
            if (set == null)
                continue;
            string dir = Path.Combine(sources, set);
            Color32[] diffuse = Load(Path.Combine(dir, set + "_diff_2k.jpg"), false);
            Color32[] normal = Load(Path.Combine(dir, set + "_nor_gl_2k.jpg"), true);
            Color32[] arm = Load(Path.Combine(dir, set + "_arm_2k.jpg"), true);
            Color32[] height = Load(Path.Combine(dir, set + "_disp_2k.jpg"), true);
            string game = Path.Combine(export, "{0}_" + layer.ToString("00") + "_{1}.png");
            Color32[] gameColor = Load(string.Format(game, "Diffuse", "rgb"), false, Small);
            Color32[] gameHeight = Load(string.Format(game, "Diffuse", "a"), true, Small);
            Color32[] gameNormalY = Load(string.Format(game, "NormalSAO", "rgb"), true, Small);
            Color32[] gameNormalX = Load(string.Format(game, "NormalSAO", "a"), true, Small);
            Color32[] gameSmooth = Load(string.Format(game, "SmoothAO", "rgb"), true, Small);
            Color32[] gameAO = Load(string.Format(game, "SmoothAO", "a"), true, Small);

            // Color, in linear light: brought to the game's average, then to its contrast at every scale and its color
            // variety (which shift the average a little, so it's brought back)
            Color[] color = Linear(diffuse), gameLinear = Linear(gameColor);
            Color target = Average(gameLinear);
            Color scale = MatchAverage(color, target, ColorMatch);
            float[] octaves = MatchOctaves(color, gameLinear);
            float variety = MatchColorfulness(color, Colorfulness(gameLinear));
            MatchAverage(color, target, ColorMatch);

            // Height (which the game blends layers by) and normals spread as much as the game's; smoothness and AO
            // averaged the same
            float heightScale = MatchSpread(height, 0, Channel(gameHeight, 0), out byte[] heights);
            Color32[] reducedNormal = Reduce(normal);
            float normalScale = Ratio(NormalStrength(Channel(gameNormalX, 0), Channel(gameNormalY, 1)),
                NormalStrength(Channel(reducedNormal, 0), Channel(reducedNormal, 1)), 0.5f, 4f);
            int smoothShift = Mean(Channel(gameSmooth, 1)) - (255 - Mean(Channel(arm, 1)));
            int aoShift = Mean(Channel(gameAO, 0)) - Mean(Channel(arm, 0));

            Color32[] diff = new Color32[Size * Size], nor = new Color32[Size * Size], sao = new Color32[Size * Size];
            for (int i = 0; i < diff.Length; i++)
            {
                Color matched = color[i].gamma;
                diff[i] = new Color32(Byte(matched.r), Byte(matched.g), Byte(matched.b), heights[i]);
                nor[i] = Normal(normal[i], normalScale);
                sao[i] = new Color32(0, Clamp(255 - arm[i].g + smoothShift), 0, Clamp(arm[i].r + aoShift));
            }
            Preview(diff, Path.Combine(Directory.GetCurrentDirectory(), "Build", "terrain", "previews", "L" + layer.ToString("00") + ".png"));
            assets.Add(Save(diff, "L" + layer + "_diff", false));
            assets.Add(Save(nor, "L" + layer + "_nor", true));
            assets.Add(Save(sao, "L" + layer + "_sao", true));
            Debug.Log(string.Format("[GfxTerrainPack] layer {0}: {1}, color scaled by ({2:0.00}, {3:0.00}, {4:0.00}), contrast by octave (fine to coarse) x{5}, color variety x{6:0.00}, normals x{7:0.00}, height x{8:0.00}, smoothness {9:+0;-0}, AO {10:+0;-0}",
                layer, set, scale.r, scale.g, scale.b, string.Join(" ", Array.ConvertAll(octaves, o => o.ToString("0.00"))), variety, normalScale, heightScale, smoothShift, aoShift));
        }
        AssetDatabase.SaveAssets();

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build", "terrain");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = assets.ToArray() };
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
            throw new Exception("Building " + BundleName + " failed; see the log above");
        Debug.Log("[GfxTerrainPack] Built " + Path.Combine(output, BundleName) + " with " + assets.Count + " textures");
    }

    /// <summary>
    /// Matches a linear color image's brightness detail to the game layer's at every scale: its brightness, in gamma
    /// space as the eye sees it (in log space the darkest gaps outweigh everything and the ground goes near black), is
    /// split into octaves (each the difference between it at one size and at half that size), the coarsest left
    /// over being the tile's broad bright and dark patches, and each is scaled to vary as much as the same octave of the
    /// game's layer. Each pixel's color is then scaled by how its brightness changed. Up close that gives the game's
    /// grain; from afar, where only the coarse octaves are left, its cracks and ledges, without the broad patches a
    /// photo has that tile into a camouflage pattern across a hillside. Returns each octave's scale, finest first.
    /// </summary>
    private static float[] MatchOctaves(Color[] color, Color[] game)
    {
        float[][] ours = Pyramid(Brightness(color), Size), theirs = Pyramid(Brightness(game), Small);
        int finer = ours.Length - theirs.Length;    // our octaves finer than the export's, which take its finest's scale
        float[] scales = new float[ours.Length];
        for (int k = ours.Length - 1; k >= 0; k--)
        {
            scales[k] = k < finer ? scales[finer]
                : Ratio(Deviation(Octave(theirs, k - finer, Small >> (k - finer))), Deviation(Octave(ours, k, Size >> k)), 0.25f, 3f);
        }

        // Rebuilt from the coarsest up, each octave scaled
        int coarsest = ours.Length - 1, size = Size >> coarsest;
        float[] rebuilt = new float[size * size];
        float mean = Mean(ours[coarsest]);
        for (int i = 0; i < rebuilt.Length; i++)
            rebuilt[i] = mean + (ours[coarsest][i] - mean) * scales[coarsest];
        for (int k = coarsest - 1; k >= 0; k--)
        {
            size = Size >> k;
            float[] octave = Octave(ours, k, size);
            rebuilt = Up(rebuilt, size / 2);
            for (int i = 0; i < rebuilt.Length; i++)
                rebuilt[i] += octave[i] * scales[k];
        }
        // Linear light goes as gamma brightness to the power 2.2
        for (int i = 0; i < color.Length; i++)
        {
            float gain = Mathf.Clamp(rebuilt[i], 0.002f, 1f) / Mathf.Max(ours[0][i], 0.002f);
            color[i] *= Mathf.Clamp(Mathf.Pow(gain, 2.2f), 0.05f, 20f);
        }
        return scales;
    }

    /// <summary>Each pixel's brightness in gamma space.</summary>
    private static float[] Brightness(Color[] color)
    {
        float[] values = new float[color.Length];
        for (int i = 0; i < color.Length; i++)
            values[i] = Luminance(color[i].gamma);
        return values;
    }

    /// <summary>A square image halved over and over, down to 4 square; the first is the image itself.</summary>
    private static float[][] Pyramid(float[] image, int size)
    {
        var levels = new System.Collections.Generic.List<float[]> { image };
        for (; size > 4; size /= 2)
        {
            int half = size / 2;
            float[] down = new float[half * half];
            for (int y = 0; y < half; y++)
            {
                for (int x = 0; x < half; x++)
                {
                    int i = 2 * y * size + 2 * x;
                    down[y * half + x] = (image[i] + image[i + 1] + image[i + size] + image[i + size + 1]) / 4f;
                }
            }
            levels.Add(down);
            image = down;
        }
        return levels.ToArray();
    }

    /// <summary>One octave of a pyramid: a level less the next one up-sized, or the coarsest level less its average.</summary>
    private static float[] Octave(float[][] pyramid, int k, int size)
    {
        float[] level = pyramid[k];
        float[] octave = new float[level.Length];
        if (k == pyramid.Length - 1)
        {
            float mean = Mean(level);
            for (int i = 0; i < level.Length; i++)
                octave[i] = level[i] - mean;
            return octave;
        }
        float[] coarser = Up(pyramid[k + 1], size / 2);
        for (int i = 0; i < level.Length; i++)
            octave[i] = level[i] - coarser[i];
        return octave;
    }

    /// <summary>A square image at twice the size, smoothly (bilinear, wrapping around as the texture tiles).</summary>
    private static float[] Up(float[] image, int size)
    {
        int big = size * 2;
        float[] result = new float[big * big];
        for (int y = 0; y < big; y++)
            for (int x = 0; x < big; x++)
                result[y * big + x] = Bilinear(image, size, (x + 0.5f) / 2f - 0.5f, (y + 0.5f) / 2f - 0.5f);
        return result;
    }

    private static float Mean(float[] values)
    {
        double sum = 0;
        foreach (float v in values)
            sum += v;
        return (float)(sum / values.Length);
    }

    /// <summary>The standard deviation.</summary>
    private static float Deviation(float[] values)
    {
        double mean = Mean(values), squares = 0;
        foreach (float v in values)
            squares += (v - mean) * (v - mean);
        return (float)Math.Sqrt(squares / values.Length);
    }

    private static float Bilinear(float[] image, int size, float x, float y)
    {
        int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
        float fx = x - x0, fy = y - y0;
        float a = image[Wrap(y0, size) * size + Wrap(x0, size)], b = image[Wrap(y0, size) * size + Wrap(x0 + 1, size)];
        float c = image[Wrap(y0 + 1, size) * size + Wrap(x0, size)], d = image[Wrap(y0 + 1, size) * size + Wrap(x0 + 1, size)];
        return Mathf.Lerp(Mathf.Lerp(a, b, fx), Mathf.Lerp(c, d, fx), fy);
    }

    private static int Wrap(int i, int size)
    {
        return ((i % size) + size) % size;
    }

    /// <summary>
    /// Scales a linear color image per channel so its average moves (by amount) to target's; returns the scale.
    /// </summary>
    private static Color MatchAverage(Color[] color, Color target, float amount)
    {
        Color source = Average(color);
        Color scale = new Color(Mathf.Lerp(1f, Ratio(target.r, source.r, 0.04f, 6f), amount),
            Mathf.Lerp(1f, Ratio(target.g, source.g, 0.04f, 6f), amount), Mathf.Lerp(1f, Ratio(target.b, source.b, 0.04f, 6f), amount));
        for (int i = 0; i < color.Length; i++)
            color[i] = new Color(color[i].r * scale.r, color[i].g * scale.g, color[i].b * scale.b);
        return scale;
    }

    /// <summary>
    /// Pulls each pixel's color towards the image's average color (or pushes it away), keeping its brightness, in gamma
    /// space, until the colors vary as much as the game layer's at the export's size; returns the factor. Scaling a
    /// photo's channels to a very different average color otherwise turns its small color differences into blue and
    /// purple blotches.
    /// </summary>
    private static float MatchColorfulness(Color[] color, float target)
    {
        float factor = Ratio(target, Colorfulness(Reduce(color)), 0f, 1.5f);
        Color mean = AverageChroma(color);
        for (int i = 0; i < color.Length; i++)
        {
            Color c = color[i].gamma;
            float luma = Luminance(c);
            color[i] = new Color(Mathf.Clamp01(luma + mean.r + (c.r - luma - mean.r) * factor),
                Mathf.Clamp01(luma + mean.g + (c.g - luma - mean.g) * factor), Mathf.Clamp01(luma + mean.b + (c.b - luma - mean.b) * factor)).linear;
        }
        return factor;
    }

    /// <summary>How far a linear image's colors stray from its average color, in gamma space, brightness aside.</summary>
    private static float Colorfulness(Color[] color)
    {
        Color mean = AverageChroma(color);
        double squares = 0;
        foreach (Color linear in color)
        {
            Color c = linear.gamma;
            float luma = Luminance(c);
            float r = c.r - luma - mean.r, g = c.g - luma - mean.g, b = c.b - luma - mean.b;
            squares += r * r + g * g + b * b;
        }
        return (float)Math.Sqrt(squares / color.Length);
    }

    /// <summary>A linear image's average color minus brightness, in gamma space.</summary>
    private static Color AverageChroma(Color[] color)
    {
        double r = 0, g = 0, b = 0;
        foreach (Color linear in color)
        {
            Color c = linear.gamma;
            float luma = Luminance(c);
            r += c.r - luma;
            g += c.g - luma;
            b += c.b - luma;
        }
        return new Color((float)(r / color.Length), (float)(g / color.Length), (float)(b / color.Length));
    }

    /// <summary>
    /// Spreads one channel of an image around its average until it spreads as far as target (at the export's size) and
    /// shares its average; returns the spread's scale.
    /// </summary>
    private static float MatchSpread(Color32[] pixels, int channel, byte[] target, out byte[] result)
    {
        Spread(Channel(Reduce(pixels), channel), out float mean, out float spread);
        Spread(target, out float targetMean, out float targetSpread);
        float scale = Ratio(targetSpread, spread, 0.5f, 4f);
        result = new byte[pixels.Length];
        byte[] values = Channel(pixels, channel);
        for (int i = 0; i < values.Length; i++)
            result[i] = Clamp(Mathf.RoundToInt(targetMean + (values[i] - mean) * scale));
        return scale;
    }

    private static void Spread(byte[] values, out float mean, out float spread)
    {
        double sum = 0, squares = 0;
        foreach (byte v in values)
        {
            sum += v;
            squares += v * v;
        }
        mean = (float)(sum / values.Length);
        spread = (float)Math.Sqrt(Math.Max(0, squares / values.Length - mean * mean));
    }

    /// <summary>How far a normal map's normals lean on average (root mean square of X and Y, from -1 to 1).</summary>
    private static float NormalStrength(byte[] x, byte[] y)
    {
        double squares = 0;
        for (int i = 0; i < x.Length; i++)
        {
            float nx = x[i] / 127.5f - 1f, ny = y[i] / 127.5f - 1f;
            squares += nx * nx + ny * ny;
        }
        return (float)Math.Sqrt(squares / x.Length);
    }

    /// <summary>A source normal (OpenGL: X in red, Y in green) leaning scale times as far, packed the game's way.</summary>
    private static Color32 Normal(Color32 source, float scale)
    {
        float nx = (source.r / 127.5f - 1f) * scale, ny = (source.g / 127.5f - 1f) * scale;
        float lean = nx * nx + ny * ny;
        if (lean > 0.95f)
        {
            // Never past flat on its side: Z is rebuilt from X and Y
            float shrink = Mathf.Sqrt(0.95f / lean);
            nx *= shrink;
            ny *= shrink;
        }
        return new Color32(0, Byte(ny * 0.5f + 0.5f), 0, Byte(nx * 0.5f + 0.5f));
    }

    private static byte[] Channel(Color32[] pixels, int channel)
    {
        byte[] values = new byte[pixels.Length];
        for (int i = 0; i < pixels.Length; i++)
            values[i] = channel == 0 ? pixels[i].r : channel == 1 ? pixels[i].g : channel == 2 ? pixels[i].b : pixels[i].a;
        return values;
    }

    private static int Mean(byte[] values)
    {
        long sum = 0;
        foreach (byte v in values)
            sum += v;
        return (int)(sum / values.Length);
    }

    /// <summary>Averaged 4 by 4 down to the export's size, on the CPU (the build runs without a graphics card).</summary>
    private static Color32[] Reduce(Color32[] pixels)
    {
        const int step = Size / Small;
        Color32[] reduced = new Color32[Small * Small];
        for (int y = 0; y < Small; y++)
        {
            for (int x = 0; x < Small; x++)
            {
                int r = 0, g = 0, b = 0, a = 0;
                for (int dy = 0; dy < step; dy++)
                {
                    for (int dx = 0; dx < step; dx++)
                    {
                        Color32 p = pixels[(y * step + dy) * Size + x * step + dx];
                        r += p.r;
                        g += p.g;
                        b += p.b;
                        a += p.a;
                    }
                }
                const int n = step * step;
                reduced[y * Small + x] = new Color32((byte)(r / n), (byte)(g / n), (byte)(b / n), (byte)(a / n));
            }
        }
        return reduced;
    }

    /// <summary>A linear image averaged 4 by 4 down to the export's size, as the game's mipmaps are made.</summary>
    private static Color[] Reduce(Color[] color)
    {
        const int step = Size / Small;
        Color[] reduced = new Color[Small * Small];
        for (int i = 0; i < color.Length; i++)
            reduced[(i / Size / step) * Small + i % Size / step] += color[i] / (step * step);
        return reduced;
    }

    private static float Luminance(Color c)
    {
        return 0.2126f * c.r + 0.7152f * c.g + 0.0722f * c.b;
    }

    /// <summary>The factor taking from to, kept within min and max.</summary>
    private static float Ratio(float to, float from, float min, float max)
    {
        return Mathf.Clamp(to / Mathf.Max(from, 1e-4f), min, max);
    }

    private static byte Byte(float value)
    {
        return (byte)Mathf.Clamp(Mathf.RoundToInt(value * 255f), 0, 255);
    }

    private static byte Clamp(int value)
    {
        return (byte)Mathf.Clamp(value, 0, 255);
    }

    /// <summary>An image's pixels at size square (resampled if it isn't), bottom row first as Unity keeps them.</summary>
    private static Color32[] Load(string path, bool linear, int size = Size)
    {
        if (!File.Exists(path))
            throw new Exception("Missing " + path);
        Texture2D image = new Texture2D(2, 2, TextureFormat.RGBA32, false, linear);
        image.LoadImage(File.ReadAllBytes(path));
        Color32[] source = image.GetPixels32();
        int width = image.width, height = image.height;
        UnityEngine.Object.DestroyImmediate(image);
        if (width == size && height == size)
            return source;
        // Nearest pixel, on the CPU (the build runs without a graphics card); every set should already be 2048
        Debug.LogWarning("[GfxTerrainPack] " + path + " is " + width + "x" + height + ", resampled to " + size);
        Color32[] pixels = new Color32[size * size];
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
                pixels[y * size + x] = source[(y * height / size) * width + x * width / size];
        return pixels;
    }

    /// <summary>sRGB pixels in linear light.</summary>
    private static Color[] Linear(Color32[] pixels)
    {
        Color[] color = new Color[pixels.Length];
        for (int i = 0; i < pixels.Length; i++)
            color[i] = ((Color)pixels[i]).linear;
        return color;
    }

    /// <summary>The average color of a linear image.</summary>
    private static Color Average(Color[] color)
    {
        double r = 0, g = 0, b = 0;
        foreach (Color c in color)
        {
            r += c.r;
            g += c.g;
            b += c.b;
        }
        return new Color((float)(r / color.Length), (float)(g / color.Length), (float)(b / color.Length));
    }

    /// <summary>The color at 512 square as a PNG, to compare with the game's (gfxe terrain export saves those).</summary>
    private static void Preview(Color32[] pixels, string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        Texture2D read = new Texture2D(Small, Small, TextureFormat.RGBA32, false, false);
        Color32[] reduced = Reduce(pixels);
        for (int i = 0; i < reduced.Length; i++)
            reduced[i].a = 255;
        read.SetPixels32(reduced);
        read.Apply(false);
        File.WriteAllBytes(path, read.EncodeToPNG());
        UnityEngine.Object.DestroyImmediate(read);
    }

    /// <summary>A 2048 square DXT5 texture with full mipmaps, saved as an asset; returns its path.</summary>
    private static string Save(Color32[] pixels, string name, bool linear)
    {
        Texture2D texture = new Texture2D(Size, Size, TextureFormat.RGBA32, true, linear) { name = name };
        texture.SetPixels32(pixels);
        texture.Apply(true);
        EditorUtility.CompressTexture(texture, TextureFormat.DXT5, TextureCompressionQuality.Best);
        string path = Folder + "/" + name + ".asset";
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(texture, path);
        return path;
    }
}
