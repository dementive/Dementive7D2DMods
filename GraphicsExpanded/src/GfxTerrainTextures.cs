using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

/// <summary>
/// Photoscanned ground textures: the 24 layers of the terrain's three texture arrays (color with height, normal, and
/// smoothness with AO), with most replaced by Poly Haven sets (CC0) from Resources/graphicsexpanded_terrain.bundle
/// (built by build-terrain.bat; see GfxTerrainPack in the Unity project).
///
/// It builds three new arrays in exactly the game's format, copying each layer on the graphics card from the bundle's
/// texture when there is one and from the game's own array otherwise, then puts them on the terrain material near and
/// far. The game's arrays stay as they were, so turning it off (or holding the compare key) just puts them back. The
/// bundle is loaded in the background and unloaded once its textures are copied in. Players see the textures locally;
/// nothing is sent.
///
/// The replaced layers can also repeat more often (GfxSettings.TerrainTiling): row 0 of the terrain's per-texture
/// settings (_PerTexProps) is each layer's UV scale, so a copy with theirs multiplied goes on the materials with the
/// arrays, and the game's goes back with them.
/// </summary>
public static class GfxTerrainTextures
{
    private const string BundleFile = "graphicsexpanded_terrain.bundle";
    private const int TerrainLayer = 5;             // MeshDescription.MESH_TERRAIN
    private static readonly string[] Properties = { "_Diffuse", "_NormalSAO", "_SmoothAO" };
    private static readonly string[] Suffixes = { "_diff", "_nor", "_sao" };
    private const string TableProperty = "_PerTexProps";

    private static string bundlePath;
    private static Texture2DArray[] built;          // ours, in the order of Properties
    private static bool[] ours;                     // which layers the pack replaced
    private static Texture[] originals;             // the game's, to put back
    private static Texture nearTable, farTable;     // the game's per-texture settings, to put back
    private static Texture2D tiledNear, tiledFar;   // copies with the replaced layers tiled by tiledFor and tiledFarFor
    private static float tiledFor, tiledFarFor;
    private static Material near, far;
    private static Material failed;                 // a terrain whose arrays weren't there, not tried again
    private static bool building;
    private static int replaced;
    private static string state = "not started";

    public static void Init(string modPath)
    {
        bundlePath = Path.Combine(modPath, "Resources", BundleFile);
        if (!File.Exists(bundlePath))
        {
            bundlePath = null;
            state = "no texture pack (" + BundleFile + " isn't in Resources; build it with build-terrain.bat)";
        }
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player)
    {
        Material terrain = TerrainMaterial(out Material distant);
        // The Prefab Editor and Playtesting worlds have no splat map, so their terrain (Game/Terrain Surface) has no
        // texture arrays to swap: treated like no world, so the pack still builds in the next real one
        if (terrain != null && !terrain.HasProperty(Properties[0]))
            terrain = null;
        bool wanted = bundlePath != null && GfxSettings.TerrainTextures == GfxTerrainTexturePack.Photoscanned;
        if (!wanted || player == null || terrain == null)
        {
            Restore();
            if (!wanted && built != null)
                Release();
            if (bundlePath != null)
                state = !wanted ? "the game's own" : "no world";
            return;
        }

        if (built == null)
        {
            if (!building && terrain != failed)
                GameManager.Instance.StartCoroutine(Build(terrain));
            return;
        }
        // The compare key shows the game's own
        if (!GfxSettings.LookActive)
        {
            Restore();
            return;
        }
        Apply(terrain, distant);
    }

    private static Material TerrainMaterial(out Material distant)
    {
        distant = null;
        MeshDescription[] meshes = MeshDescription.meshes;
        if (meshes == null || meshes.Length <= TerrainLayer || meshes[TerrainLayer] == null)
            return null;
        MeshDescription mesh = meshes[TerrainLayer];
        distant = mesh.materialDistant;
        return mesh.materials != null && mesh.materials.Length > 0 ? mesh.materials[0] : null;
    }

    private static IEnumerator Build(Material terrain)
    {
        building = true;
        state = "loading the texture pack";
        AssetBundle bundle = null;
        Texture2DArray[] arrays = new Texture2DArray[Properties.Length];
        bool kept = false;
        // Leaving the world while this loads destroys the terrain material: the finally still frees the bundle and
        // lets the next world build again
        try
        {
            AssetBundleCreateRequest load = AssetBundle.LoadFromFileAsync(bundlePath);
            yield return load;
            bundle = load.assetBundle;
            if (bundle == null)
            {
                Log.Warning("[GraphicsExpanded] Couldn't load " + bundlePath + "; the terrain keeps the game's textures");
                state = "the texture pack didn't load (see the log)";
                bundlePath = null;
                yield break;
            }
            AssetBundleRequest all = bundle.LoadAllAssetsAsync<Texture2D>();
            yield return all;

            bool[] layers = null;
            replaced = 0;
            bool ok = true;
            for (int p = 0; p < Properties.Length && ok; p++)
            {
                if (terrain == null)
                {
                    state = "no world";
                    yield break;
                }
                Texture2DArray game = terrain.GetTexture(Properties[p]) as Texture2DArray;
                if (game == null)
                {
                    Log.Warning("[GraphicsExpanded] The terrain has no " + Properties[p] + " array; keeping the game's textures");
                    ok = false;
                    break;
                }
                Texture2DArray array = new Texture2DArray(game.width, game.height, game.depth, game.graphicsFormat, TextureCreationFlags.MipChain, game.mipmapCount)
                {
                    name = "GraphicsExpanded" + Properties[p],
                    filterMode = game.filterMode,
                    anisoLevel = game.anisoLevel,
                    wrapMode = game.wrapMode,
                    mipMapBias = game.mipMapBias,
                    hideFlags = HideFlags.HideAndDontSave,
                };
                // On the graphics card only: every layer is copied in there
                array.Apply(false, true);
                int count = 0;
                if (layers == null)
                    layers = new bool[game.depth];
                for (int layer = 0; layer < game.depth; layer++)
                {
                    Texture2D replacement = bundle.LoadAsset<Texture2D>("L" + layer + Suffixes[p]);
                    bool fits = replacement != null && replacement.width == game.width && replacement.height == game.height
                        && replacement.mipmapCount == game.mipmapCount && GraphicsFormatUtility.GetBlockSize(replacement.graphicsFormat)
                            == GraphicsFormatUtility.GetBlockSize(game.graphicsFormat);
                    if (replacement != null && !fits)
                        Log.Warning(string.Format("[GraphicsExpanded] Terrain texture L{0}{1} is {2}x{3} {4} with {5} mips, the game's are {6}x{7} {8} with {9}; keeping the game's layer",
                            layer, Suffixes[p], replacement.width, replacement.height, replacement.graphicsFormat, replacement.mipmapCount,
                            game.width, game.height, game.graphicsFormat, game.mipmapCount));
                    for (int mip = 0; mip < game.mipmapCount; mip++)
                    {
                        if (fits)
                            Graphics.CopyTexture(replacement, 0, mip, array, layer, mip);
                        else
                            Graphics.CopyTexture(game, layer, mip, array, layer, mip);
                    }
                    if (fits)
                    {
                        count++;
                        // Tiled by the color's layers: that's what shows
                        if (p == 0)
                            layers[layer] = true;
                    }
                }
                arrays[p] = array;
                replaced = Mathf.Max(replaced, count);
                yield return null;
            }

            if (!ok)
            {
                state = "the terrain's arrays weren't there (see the log)";
                failed = terrain;
            }
            else
            {
                built = arrays;
                ours = layers;
                kept = true;
                Log.Out(string.Format("[GraphicsExpanded] Terrain texture pack ready: {0} of {1} layers replaced ({2}, {3} mips)",
                    replaced, arrays[0].depth, arrays[0].graphicsFormat, arrays[0].mipmapCount));
            }
        }
        finally
        {
            // The copies live on the graphics card now; the bundle's own textures can go
            if (bundle != null)
                bundle.Unload(true);
            if (!kept)
            {
                foreach (Texture2DArray array in arrays)
                {
                    if (array != null)
                        Object.Destroy(array);
                }
            }
            building = false;
        }
    }

    private static void Apply(Material terrain, Material distant)
    {
        if (near != terrain || far != distant)
            Restore();
        if (originals == null)
        {
            originals = new Texture[Properties.Length];
            for (int p = 0; p < Properties.Length; p++)
                originals[p] = terrain.GetTexture(Properties[p]);
            nearTable = terrain.HasProperty(TableProperty) ? terrain.GetTexture(TableProperty) : null;
            farTable = distant != null && distant.HasProperty(TableProperty) ? distant.GetTexture(TableProperty) : null;
            near = terrain;
            far = distant;
        }
        for (int p = 0; p < Properties.Length; p++)
        {
            Texture current = terrain.GetTexture(Properties[p]);
            if (current != built[p])
            {
                // The game puts new arrays on when Texture Quality changes (and unloads the old ones): they're the
                // ones to put back now
                if (current != null)
                    originals[p] = current;
                terrain.SetTexture(Properties[p], built[p]);
            }
            if (distant != null && distant.HasProperty(Properties[p]) && distant.GetTexture(Properties[p]) != built[p])
                distant.SetTexture(Properties[p], built[p]);
        }

        // The far terrain (past the loaded chunks) has its own tiling: what sharpens the ground underfoot repeats into
        // stripes across a field a hundred meters off
        float tiling = GfxSettings.TerrainTiling, farTiling = GfxSettings.DistantTiling;
        if (tiledFor != tiling || tiledFarFor != farTiling)
        {
            ReleaseTables();
            if (!Mathf.Approximately(tiling, 1f))
                tiledNear = Tiled(nearTable, tiling);
            if (!Mathf.Approximately(farTiling, 1f))
                tiledFar = Tiled(farTable, farTiling);
            tiledFor = tiling;
            tiledFarFor = farTiling;
        }
        SetTable(terrain, tiledNear != null ? tiledNear : nearTable);
        SetTable(distant, tiledFar != null ? tiledFar : farTable);
        state = string.Format("photoscanned, {0} of {1} layers replaced, tiled x{2:0.##} near and x{3:0.##} far", replaced, built[0].depth, tiling, farTiling);
    }

    /// <summary>A copy of the per-texture settings with the replaced layers' UV scale (row 0) multiplied by tiling.</summary>
    private static Texture2D Tiled(Texture table, float tiling)
    {
        if (table == null || ours == null)
            return null;
        Texture2D copy = GfxTerrain.Read(table, table.width, table.height, -1, RenderTextureFormat.ARGBFloat, TextureFormat.RGBAFloat, false);
        copy.name = "GraphicsExpanded" + TableProperty;
        copy.filterMode = FilterMode.Point;
        copy.wrapMode = TextureWrapMode.Clamp;
        copy.hideFlags = HideFlags.HideAndDontSave;
        for (int layer = 0; layer < ours.Length && layer < copy.width; layer++)
        {
            if (!ours[layer])
                continue;
            Color scale = copy.GetPixel(layer, 0);
            copy.SetPixel(layer, 0, new Color(scale.r * tiling, scale.g * tiling, scale.b, scale.a));
        }
        copy.Apply(false);
        return copy;
    }

    private static void SetTable(Material material, Texture table)
    {
        if (material != null && table != null && material.HasProperty(TableProperty) && material.GetTexture(TableProperty) != table)
            material.SetTexture(TableProperty, table);
    }

    private static void ReleaseTables()
    {
        if (tiledFar != null)
            Object.Destroy(tiledFar);
        if (tiledNear != null)
            Object.Destroy(tiledNear);
        tiledNear = tiledFar = null;
        tiledFor = tiledFarFor = 0f;
    }

    private static void Restore()
    {
        if (originals == null)
            return;
        for (int p = 0; p < Properties.Length; p++)
        {
            if (near != null)
                near.SetTexture(Properties[p], originals[p]);
            if (far != null && far.HasProperty(Properties[p]))
                far.SetTexture(Properties[p], originals[p]);
        }
        SetTable(near, nearTable);
        SetTable(far, farTable);
        // Made again from the game's table next time, in case the game has a new one by then
        ReleaseTables();
        nearTable = farTable = null;
        originals = null;
        near = far = null;
    }

    private static void Release()
    {
        foreach (Texture2DArray array in built)
        {
            if (array != null)
                Object.Destroy(array);
        }
        built = null;
    }

    public static string Status()
    {
        return "Ground textures: " + state + ".";
    }
}
