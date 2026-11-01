using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

/// <summary>
/// The terrain: sharper far-off terrain, and tools for looking at the ground's textures.
/// - The far terrain (Unity terrain tiles the game builds around the player) gets a lower pixel error, so hills keep
///   their shape, and its full textures reach further before it switches to its blurry base map. The game sets both
///   from its terrain quality; this scales whatever it set.
/// - gfxe terrain table writes MicroSplat's per-texture settings to the log, and gfxe terrain export saves the 24 ground
///   textures (color with height, normal with smoothness and AO, smoothness and AO) as images.
/// </summary>
public static class GfxTerrain
{
    private const int TerrainLayer = 5;             // MeshDescription.MESH_TERRAIN
    private const int ExportSize = 512;

    private class DistantState
    {
        public float BasePixel, SetPixel = -1f, BaseBasemap, SetBasemap = -1f;
    }

    private static readonly Dictionary<Terrain, DistantState> distant = new Dictionary<Terrain, DistantState>();
    private static float nextPrune;

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player)
    {
        GfxDistantTerrain level = player != null && GfxSettings.DetailActive ? GfxSettings.DistantTerrain : GfxDistantTerrain.Game;
        float pixelError = level == GfxDistantTerrain.Ultra ? 0.3f : level == GfxDistantTerrain.High ? 0.5f : 1f;
        float basemap = level == GfxDistantTerrain.Ultra ? 4f : level == GfxDistantTerrain.High ? 2f : 1f;
        foreach (Terrain terrain in Terrain.activeTerrains)
        {
            if (terrain == null)
                continue;
            if (!distant.TryGetValue(terrain, out DistantState s))
            {
                s = new DistantState { BasePixel = terrain.heightmapPixelError, BaseBasemap = terrain.basemapDistance };
                distant[terrain] = s;
            }
            // Whatever the game set since (it sets these as it builds around the player) is the new base
            if (terrain.heightmapPixelError != s.SetPixel)
                s.BasePixel = terrain.heightmapPixelError;
            if (terrain.basemapDistance != s.SetBasemap)
                s.BaseBasemap = terrain.basemapDistance;
            float wantPixel = Mathf.Max(1f, s.BasePixel * pixelError);
            float wantBasemap = s.BaseBasemap * basemap;
            if (terrain.heightmapPixelError != wantPixel)
                terrain.heightmapPixelError = wantPixel;
            if (terrain.basemapDistance != wantBasemap)
                terrain.basemapDistance = wantBasemap;
            s.SetPixel = terrain.heightmapPixelError;
            s.SetBasemap = terrain.basemapDistance;
        }
        if (Time.unscaledTime >= nextPrune)
        {
            List<Terrain> gone = new List<Terrain>();
            foreach (Terrain terrain in distant.Keys)
            {
                if (terrain == null)
                    gone.Add(terrain);
            }
            foreach (Terrain terrain in gone)
                distant.Remove(terrain);
            nextPrune = Time.unscaledTime + 10f;
        }
    }

    public static string Status()
    {
        string far = Terrain.activeTerrains.Length == 0 ? "no far terrain yet" : string.Format("{0} far terrain tiles at {1}",
            Terrain.activeTerrains.Length, GfxSettings.DetailActive ? GfxSettings.DistantTerrain : GfxDistantTerrain.Game);
        foreach (Terrain terrain in Terrain.activeTerrains)
        {
            if (terrain != null)
            {
                far += string.Format(" (pixel error {0:0.0}, full textures to {1:0} m)", terrain.heightmapPixelError, terrain.basemapDistance);
                break;
            }
        }
        return "Terrain: " + far + ".";
    }

    /// <summary>The material the nearby terrain draws with (MicroSplat), once a world is loaded.</summary>
    private static Material TerrainMaterial()
    {
        MeshDescription[] meshes = MeshDescription.meshes;
        return meshes != null && meshes.Length > TerrainLayer && meshes[TerrainLayer]?.materials != null
            && meshes[TerrainLayer].materials.Length > 0 ? meshes[TerrainLayer].materials[0] : null;
    }

    /// <summary>
    /// gfxe terrain table: writes MicroSplat's per-texture settings (a 32 by 32 float texture, one column per ground
    /// texture) to the game log. Row 0 is each texture's tiling.
    /// </summary>
    public static int LogTextureTable()
    {
        Material terrainMaterial = TerrainMaterial();
        Texture table = terrainMaterial != null && terrainMaterial.HasProperty("_PerTexProps") ? terrainMaterial.GetTexture("_PerTexProps") : null;
        if (table == null)
        {
            Log.Out("[GraphicsExpanded] No terrain texture table (load a world first).");
            return 1;
        }
        Texture2D read = Read(table, table.width, table.height, -1, RenderTextureFormat.ARGBFloat, TextureFormat.RGBAFloat, false);
        int lines = 0;
        for (int row = 0; row < table.height; row++)
        {
            StringBuilder text = new StringBuilder();
            bool any = false;
            for (int column = 0; column < 24 && column < table.width; column++)
            {
                Color c = read.GetPixel(column, row);
                any |= c != Color.clear;
                text.AppendFormat(" {0}:({1:0.###},{2:0.###},{3:0.###},{4:0.###})", column, c.r, c.g, c.b, c.a);
            }
            if (!any)
                continue;
            Log.Out("[GraphicsExpanded] Terrain table row " + row + text);
            lines++;
        }
        Object.Destroy(read);
        return lines;
    }

    /// <summary>
    /// gfxe terrain export: saves each layer of the ground's three texture arrays at 512 square, its color channels
    /// and its alpha as separate images, into GraphicsExpanded/TerrainExport in the game's user folder. Returns where.
    /// </summary>
    public static string ExportTextures()
    {
        Material terrainMaterial = TerrainMaterial();
        if (terrainMaterial == null)
            return "Load a world first.";
        string folder = Path.Combine(GameIO.GetUserGameDataDir(), "GraphicsExpanded", "TerrainExport");
        Directory.CreateDirectory(folder);
        int saved = 0;
        foreach (string property in new[] { "_Diffuse", "_NormalSAO", "_SmoothAO" })
        {
            Texture2DArray array = terrainMaterial.HasProperty(property) ? terrainMaterial.GetTexture(property) as Texture2DArray : null;
            if (array == null)
                continue;
            bool color = property == "_Diffuse";
            for (int layer = 0; layer < array.depth; layer++)
            {
                Texture2D read = Read(array, ExportSize, ExportSize, layer, RenderTextureFormat.ARGB32, TextureFormat.RGBA32, color);
                Color32[] pixels = read.GetPixels32();
                Color32[] rgb = new Color32[pixels.Length];
                Color32[] alpha = new Color32[pixels.Length];
                for (int i = 0; i < pixels.Length; i++)
                {
                    Color32 p = pixels[i];
                    rgb[i] = new Color32(p.r, p.g, p.b, 255);
                    alpha[i] = new Color32(p.a, p.a, p.a, 255);
                }
                string name = property.TrimStart('_') + "_" + layer.ToString("00");
                Save(rgb, Path.Combine(folder, name + "_rgb.png"), color);
                Save(alpha, Path.Combine(folder, name + "_a.png"), false);
                Object.Destroy(read);
                saved += 2;
            }
        }
        LogTextureTable();
        Log.Out("[GraphicsExpanded] Saved " + saved + " terrain texture images to " + folder);
        return "Saved " + saved + " images to " + folder + " (and the per-texture table to the game log).";
    }

    /// <summary>One texture (or one layer of an array) read back from the graphics card at the given size.</summary>
    internal static Texture2D Read(Texture source, int width, int height, int layer, RenderTextureFormat format, TextureFormat readFormat, bool color)
    {
        RenderTexture copy = RenderTexture.GetTemporary(width, height, 0, format, color ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear);
        if (layer >= 0)
            Graphics.Blit(source, copy, layer, 0);
        else
            Graphics.Blit(source, copy);
        Texture2D read = new Texture2D(width, height, readFormat, false, !color);
        RenderTexture active = RenderTexture.active;
        RenderTexture.active = copy;
        read.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
        read.Apply(false);
        RenderTexture.active = active;
        RenderTexture.ReleaseTemporary(copy);
        return read;
    }

    private static void Save(Color32[] pixels, string path, bool color)
    {
        Texture2D image = new Texture2D(ExportSize, ExportSize, TextureFormat.RGBA32, false, !color);
        image.SetPixels32(pixels);
        image.Apply(false);
        File.WriteAllBytes(path, image.EncodeToPNG());
        Object.Destroy(image);
    }
}
