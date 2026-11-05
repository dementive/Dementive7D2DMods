using System;
using System.Collections.Generic;
using System.Globalization;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Adds the mod's grasses to the game's grass texture sheet as it loads, so they're drawn exactly like vanilla's tall
/// grass (in the chunk's own grass mesh: thousands cost no more than vanilla's).
///
/// The sheet (ta_grass, 4096 x 4096 DXT5, with ta_grass_n and ta_grass_s in the same layout) has 29 tiles of 512 and
/// an empty block from (1536, 2048) to its top-right corner. Each grass's three tiles (Resources/natureexpanded-
/// grass.unity3d, built by src/build-grass.bat) are copied into that block on the GPU, 5 across and 4 up in the
/// order of blender/grass/grasses.txt, mip by mip down to 4 x 4, and each gets a uv entry under its texture id (600
/// and up), like vanilla's tall grass's, so blocks.xml can name it. A dedicated server has no textures, so it only
/// gets the uv entries.
///
/// The sheets stream their mips (the game's "Texture streaming" option): when they load, often only the small mips
/// are on the GPU, and a full-size copy into them hung the game. So the patch only adds the uv entries and asks for
/// the sheets' full mips (and keeps asking, so they stay); GrassSheetKeeper copies the tiles in once a sheet is
/// fully loaded, and again if streaming ever drops and reloads it (which reloads it from disk, without them). If a
/// sheet can't be fully loaded (textures turned down to half size or less), the grasses show vanilla's tall grass's
/// tile instead of an empty one.
/// </summary>
[HarmonyPatch(typeof(TextureAtlasBlocks), nameof(TextureAtlasBlocks.LoadTextureAtlas))]
public static class GrassSheetDEM
{
    public const string BundleFile = "natureexpanded-grass.unity3d";
    private const int SheetX = 1536, SheetY = 2048, Tile = 512, Columns = 5, Slots = 20, FirstId = 600, Template = 39;
    // The tiles sit edge to edge with no gap (vanilla's have 68 px), so a grass's frame stops this far short of its
    // tile's top: filtering at a frame's top edge reached into the tile above, whose bottom is a solid band of grass
    // bases, and drew a thin line along the top of every grass block, strung between the plants
    private const int TopInset = 16;

    /// <summary>The mod's folder, set by the mod's InitMod.</summary>
    public static string ModPath;

    private static AssetBundle bundle;
    private static bool failed;
    private static TextureAtlas atlas;
    private static readonly List<Grass> grasses = new List<Grass>();

    private struct Grass
    {
        public int Id;
        public string Name;
        public Color Color;
    }

    public static void Postfix(TextureAtlasBlocks __instance, int _idx, MeshDescriptionCollection _tac)
    {
        if (failed || _tac == null || _tac.meshes == null || _idx >= _tac.meshes.Length || _tac.meshes[_idx].Name != "grass")
        {
            return;
        }
        try
        {
            if (!Load())
            {
                return;
            }
            atlas = __instance;
            AddUvs(true);
            if (__instance.diffuseTexture != null)
            {
                GrassSheetKeeper.Watch(new[]
                {
                    (__instance.diffuseTexture as Texture2D, "_D"), (__instance.normalTexture as Texture2D, "_N"),
                    (__instance.specularTexture as Texture2D, "_S"),
                });
            }
        }
        catch (Exception e)
        {
            failed = true;
            Log.Error("[NatureExpanded] Could not add the grasses to the grass sheet: " + e);
        }
    }

    private static bool Load()
    {
        if (bundle == null)
        {
            string path = System.IO.Path.Combine(ModPath ?? "", "Resources", BundleFile);
            bundle = AssetBundle.LoadFromFile(path);
            if (bundle == null)
            {
                failed = true;
                Log.Error("[NatureExpanded] Could not load " + path + "; the mod's grasses won't show");
                return false;
            }
        }
        if (grasses.Count > 0)
        {
            return true;
        }
        foreach (string line in bundle.LoadAsset<TextAsset>("GrassSheet").text.Split('\n'))
        {
            string[] p = line.Trim().Split(' ');
            if (p.Length < 5)
            {
                continue;
            }
            int id = int.Parse(p[0], CultureInfo.InvariantCulture);
            if (id < FirstId || id >= FirstId + Slots)
            {
                continue;
            }
            grasses.Add(new Grass
            {
                Id = id, Name = p[1],
                Color = new Color(float.Parse(p[2], CultureInfo.InvariantCulture), float.Parse(p[3], CultureInfo.InvariantCulture),
                    float.Parse(p[4], CultureInfo.InvariantCulture)),
            });
        }
        return grasses.Count > 0;
    }

    /// <summary>A uv entry per grass, a copy of vanilla's tall grass's: on the grass's own tile, or (`own` false) on
    /// the tall grass's tile, for when the tiles can't be copied in.</summary>
    public static void AddUvs(bool own)
    {
        if (atlas == null)
        {
            return;
        }
        int length = FirstId + Slots;
        if (atlas.uvMapping.Length < length)
        {
            UVRectTiling[] grown = new UVRectTiling[length];
            Array.Copy(atlas.uvMapping, grown, atlas.uvMapping.Length);
            atlas.uvMapping = grown;
        }
        UVRectTiling template = atlas.uvMapping[Template];
        foreach (Grass g in grasses)
        {
            UVRectTiling uv = template;
            if (own)
            {
                Vector2Int at = Place(g.Id);
                uv.uv = new Rect(at.x / 4096f, at.y / 4096f, Tile / 4096f, (Tile - TopInset) / 4096f);
                uv.color = g.Color;
                uv.textureName = g.Name;
            }
            atlas.uvMapping[g.Id] = uv;
        }
    }

    private static Vector2Int Place(int id)
    {
        int slot = id - FirstId;
        return new Vector2Int(SheetX + slot % Columns * Tile, SheetY + slot / Columns * Tile);
    }

    /// <summary>Copies every grass's tile of one kind (_D, _N or _S) into a sheet, mip by mip down to 4 x 4 (whole
    /// DXT blocks). Only for a sheet with all its mips on the GPU. Returns how many mips it copied.</summary>
    public static int CopyAll(Texture2D sheet, string kind)
    {
        int copied = 0;
        foreach (Grass g in grasses)
        {
            Texture2D tile = bundle.LoadAsset<Texture2D>(g.Name + kind);
            if (tile == null)
            {
                continue;
            }
            Vector2Int at = Place(g.Id);
            for (int m = 0; m < tile.mipmapCount && m < sheet.mipmapCount; m++)
            {
                int size = Tile >> m;
                if (size < 4)
                {
                    break;
                }
                Graphics.CopyTexture(tile, 0, m, 0, 0, size, size, sheet, 0, m, at.x >> m, at.y >> m);
                copied++;
            }
        }
        return copied;
    }
}

/// <summary>Keeps the grass sheets fully loaded and the mod's tiles in them (see GrassSheetDEM): twice a second it
/// re-asks for each sheet's full mips, and copies the tiles in whenever a sheet has come (back) to full detail.</summary>
public class GrassSheetKeeper : MonoBehaviour
{
    private class Sheet
    {
        public Texture2D Texture;
        public string Kind;
        public bool Copied;
        public float Since;
    }

    private static GrassSheetKeeper instance;
    private readonly List<Sheet> sheets = new List<Sheet>();
    private float next;
    private bool fellBack;

    public static void Watch((Texture2D, string)[] textures)
    {
        if (instance == null)
        {
            GameObject go = new GameObject("NatureExpandedGrassSheet");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<GrassSheetKeeper>();
        }
        instance.sheets.Clear();
        instance.fellBack = false;
        foreach ((Texture2D texture, string kind) in textures)
        {
            if (texture == null || texture.width != 4096 || texture.height != 4096)
            {
                Log.Warning("[NatureExpanded] A grass sheet isn't the 4096 x 4096 the grasses were made for; they show as tall grass");
                GrassSheetDEM.AddUvs(false);
                instance.sheets.Clear();
                return;
            }
            instance.sheets.Add(new Sheet { Texture = texture, Kind = kind, Since = Time.realtimeSinceStartup });
            if (texture.streamingMipmaps)
            {
                texture.requestedMipmapLevel = 0;
            }
        }
    }

    private void Update()
    {
        if (sheets.Count == 0 || Time.realtimeSinceStartup < next)
        {
            return;
        }
        next = Time.realtimeSinceStartup + 0.5f;
        bool streaming = QualitySettings.streamingMipmapsActive;
        foreach (Sheet s in sheets)
        {
            if (s.Texture == null)
            {
                continue;
            }
            bool full = QualitySettings.globalTextureMipmapLimit == 0
                && (!s.Texture.streamingMipmaps || !streaming || s.Texture.loadedMipmapLevel == 0);
            if (!full)
            {
                if (s.Copied)
                {
                    // Dropped mips are reloaded from disk, without the tiles
                    s.Copied = false;
                    s.Since = Time.realtimeSinceStartup;
                }
                if (s.Texture.streamingMipmaps)
                {
                    s.Texture.requestedMipmapLevel = 0;
                }
                if (!fellBack && Time.realtimeSinceStartup - s.Since > 30f)
                {
                    fellBack = true;
                    GrassSheetDEM.AddUvs(false);
                    Log.Warning("[NatureExpanded] The grass sheet " + s.Texture.name + " hasn't loaded in full (mip " + s.Texture.loadedMipmapLevel
                        + ", texture limit " + QualitySettings.globalTextureMipmapLimit + "); the mod's grasses show as tall grass until it does");
                }
                continue;
            }
            if (s.Copied)
            {
                continue;
            }
            try
            {
                int copied = GrassSheetDEM.CopyAll(s.Texture, s.Kind);
                s.Copied = true;
                if (fellBack)
                {
                    fellBack = false;
                    GrassSheetDEM.AddUvs(true);
                }
                Log.Out("[NatureExpanded] Copied the grasses into " + s.Texture.name + " (" + copied + " tile mips)");
            }
            catch (Exception e)
            {
                Log.Error("[NatureExpanded] Could not copy the grasses into " + s.Texture.name + ": " + e.Message);
                sheets.Clear();
                GrassSheetDEM.AddUvs(false);
                return;
            }
        }
    }
}
