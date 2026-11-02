using System.Collections.Generic;
using UnityEngine;

/// <summary>The mod's own assets, from Resources/zombiesexpanded.unity3d (the overlay and eyeshine materials, the
/// blood drip effect, and later the gear and growth models).</summary>
public static class ZedAssets
{
    private const string Bundle = "#@modfolder(ZombiesExpanded):Resources/zombiesexpanded.unity3d?";

    private static readonly Dictionary<string, Object> cache = new Dictionary<string, Object>();
    private static readonly HashSet<string> failed = new HashSet<string>();
    private static Mesh quad;

    public static T Get<T>(string name) where T : Object
    {
        if (cache.TryGetValue(name, out Object o) && o != null)
        {
            return o as T;
        }
        if (failed.Contains(name))
        {
            return null;
        }
        T asset = DataLoader.LoadAsset<T>(Bundle + name);
        if (asset == null)
        {
            failed.Add(name);
            Debug.LogWarning("[ZombiesExpanded] Couldn't load " + name + " from the bundle");
            return null;
        }
        cache[name] = asset;
        return asset;
    }

    /// <summary>A 1 m quad facing +Z, for sprites the shader turns to the camera.</summary>
    public static Mesh Quad()
    {
        if (quad != null)
        {
            return quad;
        }
        quad = new Mesh { name = "ZedQuad" };
        quad.vertices = new[]
        {
            new Vector3(-0.5f, -0.5f, 0f), new Vector3(0.5f, -0.5f, 0f), new Vector3(0.5f, 0.5f, 0f), new Vector3(-0.5f, 0.5f, 0f),
        };
        quad.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
        quad.triangles = new[] { 0, 2, 1, 0, 3, 2 };
        quad.bounds = new Bounds(Vector3.zero, Vector3.one);
        return quad;
    }
}
