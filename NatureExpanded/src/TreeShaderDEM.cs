using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Readies the mod's trees: points each collider back at its tree, as vanilla's prefabs do, so hits land, and finds
/// their materials so SpeedTreeWindDEM can feed them the game's wind. The trees' materials are built
/// into Resources/natureexpanded-trees.unity3d in a copy of Unity's own SpeedTree 8 shader that also takes the game's
/// fade for a felled tree (NatureExpanded/SpeedTree8, NatureTreeBuilder), so nothing is
/// converted here: materials made at runtime from a vanilla oak's drew magenta in game. Every tree (decoration, block
/// entity, the falling tree made from one, and other mods borrowing models) comes from the game's object pool, keyed by
/// the model's asset name, and ours all start "NatureTree": their prefab is picked up as the pool takes it in, and any
/// copy as it's handed out (in case the prefab wasn't).
/// </summary>
[HarmonyPatch(typeof(GameObjectPool), nameof(GameObjectPool.GetObjectForType), new[] { typeof(string), typeof(Color) },
    new[] { ArgumentType.Normal, ArgumentType.Out })]
public static class TreeShaderDEM
{
    public const string Prefix = "NatureTree";

    /// <summary>The mod's tree materials, for SpeedTreeWindDEM to feed.</summary>
    public static readonly List<Material> Materials = new List<Material>();
    private static readonly HashSet<Material> known = new HashSet<Material>();

    public static void Postfix(GameObject __result, string objectType)
    {
        if (__result != null && objectType != null && objectType.StartsWith(Prefix, System.StringComparison.Ordinal))
        {
            Register(__result.transform);
        }
    }

    public static void Register(Transform root)
    {
        // A hit on a tree's collider finds the tree through this (RootTransformRefParent.FindRoot); vanilla trees
        // carry it on their collider, and without it a hit on ours finds no tree and does nothing
        foreach (Collider c in root.GetComponentsInChildren<Collider>(true))
        {
            if (c.GetComponent<RootTransformRefParent>() == null)
            {
                c.gameObject.AddComponent<RootTransformRefParent>().RootTransform = root;
            }
        }
        foreach (MeshRenderer r in root.GetComponentsInChildren<MeshRenderer>(true))
        {
            foreach (Material m in r.sharedMaterials)
            {
                if (m != null && known.Add(m))
                {
                    Materials.Add(m);
                    SpeedTreeWindDEM.Ensure();
                }
            }
        }
    }
}

/// <summary>Picks up a tree's prefab as the game's pool takes it in, the one place every copy comes from (most
/// decorations are made many at once by GetObjectsForTypeAsync, which the GetObjectForType patch never sees).</summary>
[HarmonyPatch(typeof(GameObjectPool), nameof(GameObjectPool.setItemPrefab))]
public static class TreePrefabDEM
{
    public static void Postfix(GameObjectPool.PoolItem item, GameObject go)
    {
        if (go != null && item?.name != null && item.name.StartsWith(TreeShaderDEM.Prefix, System.StringComparison.Ordinal))
        {
            TreeShaderDEM.Register(go.transform);
        }
    }
}

/// <summary>
/// Feeds the game's wind to the mod's SpeedTree materials. Unity gives each vanilla SpeedTree its wind (SpeedTree's
/// _ST_Wind* values, with their running times) through the renderer's property block, from the tree's own wind
/// asset, which ours don't have. Each frame this copies the values from a vanilla "palm" tree in view (an oak or a
/// pine, the same wind mode as ours) onto our materials, so ours sway with vanilla's in the same breeze. The shader
/// staggers each tree's sway by its position, so they don't move in step. Until a vanilla tree is in view (or if the
/// game doesn't expose its wind) ours stand still. Once, the first time one of ours is in view, it writes how that tree
/// is drawn to the log, beside a vanilla tree, for diagnosing drawing problems.
/// </summary>
public class SpeedTreeWindDEM : MonoBehaviour
{
    private static readonly string[] Names =
    {
        "_ST_WindVector", "_ST_WindGlobal", "_ST_WindBranch", "_ST_WindBranchTwitch", "_ST_WindBranchWhip", "_ST_WindBranchAnchor",
        "_ST_WindBranchAdherences", "_ST_WindTurbulences", "_ST_WindLeaf1Ripple", "_ST_WindLeaf1Tumble", "_ST_WindLeaf1Twitch",
        "_ST_WindLeaf2Ripple", "_ST_WindLeaf2Tumble", "_ST_WindLeaf2Twitch", "_ST_WindFrondRipple", "_ST_WindAnimation",
    };

    private static SpeedTreeWindDEM instance;
    private int[] ids;
    private int windEnabled;
    private Renderer source;
    private float nextSearch;
    private MaterialPropertyBlock block;
    private bool reported;
    private Tree[] trees;
    private float nextGather;
    private bool described;
    private float nextDescribe;

    public static void Ensure()
    {
        if (instance == null)
        {
            GameObject go = new GameObject("NatureExpandedTreeWind");
            DontDestroyOnLoad(go);
            instance = go.AddComponent<SpeedTreeWindDEM>();
        }
    }

    private void Awake()
    {
        ids = System.Array.ConvertAll(Names, Shader.PropertyToID);
        windEnabled = Shader.PropertyToID("_WindEnabled");
        block = new MaterialPropertyBlock();
    }

    private void LateUpdate()
    {
        if (TreeShaderDEM.Materials.Count == 0)
        {
            return;
        }
        if (!described && Time.realtimeSinceStartup >= nextDescribe)
        {
            nextDescribe = Time.realtimeSinceStartup + 5f;
            described = Describe();
        }
        if ((source == null || !source.isVisible) && Time.realtimeSinceStartup >= nextSearch)
        {
            nextSearch = Time.realtimeSinceStartup + 2f;
            source = Search();
        }
        if (source == null)
        {
            return;
        }
        source.GetPropertyBlock(block);
        bool empty = block.isEmpty || block.GetVector(ids[1]) == Vector4.zero;
        if (!reported)
        {
            reported = true;
            Log.Out("[NatureExpanded] Tree wind from " + source.name + ": " + (empty ? "no wind values in its property block; the mod's trees stand still"
                : "vector " + block.GetVector(ids[0]) + ", global " + block.GetVector(ids[1]) + ", branch " + block.GetVector(ids[2])
                    + ", frond ripple " + block.GetVector(ids[14])));
        }
        if (empty)
        {
            return;
        }
        float enabled = block.HasFloat(windEnabled) ? block.GetFloat(windEnabled) : 1f;
        foreach (Material m in TreeShaderDEM.Materials)
        {
            if (m == null)
            {
                continue;
            }
            for (int i = 0; i < ids.Length; i++)
            {
                m.SetVector(ids[i], block.GetVector(ids[i]));
            }
            m.SetFloat(windEnabled, enabled);
        }
    }

    /// <summary>A vanilla SpeedTree in view whose material sways in the "palm" mode ours use. The list of trees is
    /// gathered at most every 15 s (a forest holds thousands).</summary>
    private Renderer Search()
    {
        if (trees == null || Time.realtimeSinceStartup >= nextGather)
        {
            nextGather = Time.realtimeSinceStartup + 15f;
            trees = FindObjectsOfType<Tree>();
        }
        foreach (Tree tree in trees)
        {
            if (tree == null)
            {
                continue;
            }
            Renderer r = tree.GetComponent<Renderer>();
            if (r != null && r.isVisible && r.sharedMaterial != null && r.sharedMaterial.IsKeywordEnabled("_WINDQUALITY_PALM"))
            {
                return r;
            }
        }
        return null;
    }

    /// <summary>Logs how one of our trees in view is drawn (each renderer's materials, shader, keywords, maps and
    /// property block) beside a vanilla tree's. Returns false until one of ours is in view.</summary>
    private bool Describe()
    {
        Renderer ours = null;
        foreach (LODGroup g in FindObjectsOfType<LODGroup>())
        {
            if (g.name.StartsWith(TreeShaderDEM.Prefix, System.StringComparison.Ordinal))
            {
                ours = g.GetComponentsInChildren<Renderer>().FirstOrDefault(r => r.isVisible);
                if (ours != null)
                {
                    break;
                }
            }
        }
        if (ours == null)
        {
            return false;
        }
        Log.Out("[NatureExpanded] Tree drawing: ours " + Describe(ours));
        if (source != null)
        {
            Log.Out("[NatureExpanded] Tree drawing: vanilla " + Describe(source));
        }
        return true;
    }

    private string Describe(Renderer r)
    {
        r.GetPropertyBlock(block);
        string Map(Material m, string p) => m.HasProperty(p) && m.GetTexture(p) != null ? m.GetTexture(p).name + " " + m.GetTexture(p).graphicsFormat : "none";
        return r.transform.root.name + "/" + r.name + " layer " + r.gameObject.layer + " enabled " + r.enabled + " block " + (block.isEmpty ? "empty" : "set")
            + string.Concat(r.sharedMaterials.Select(m => m == null ? " | null material" : " | " + m.name + " shader "
                + (m.shader != null ? m.shader.name + " supported " + m.shader.isSupported + " passes " + m.passCount : "NULL")
                + " keywords [" + string.Join(" ", m.shaderKeywords) + "] queue " + m.renderQueue
                + " main " + Map(m, "_MainTex") + " normal " + Map(m, "_BumpMap")));
    }
}
